# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/lineup_analysis
파일: player_synergy.py
설명: 선수 시너지 분석기
      - 2인 조합 시너지 (Co-play 넷레이팅)
      - 3인 조합 시너지
      - 최고/최저 시너지 조합 식별

      Processing Cadence: 🔵 POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: (없음 — 순수 계산)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_COMBOS: Final[int] = 500


@dataclass(slots=True)
class PlayerSynergyConfig:
    """시너지 분석 설정."""

    max_combos: int = _MAX_COMBOS
    min_possessions: int = 5


@dataclass(slots=True)
class _ComboRecord:
    """조합 누적 기록."""

    player_ids: tuple[int, ...]
    possessions: int = 0
    points_scored: int = 0
    points_allowed: int = 0


class PlayerSynergyAnalyzer:
    """선수 시너지 분석기."""

    __slots__ = ("_config", "_lock", "_pairs", "_triples")

    def __init__(self, config: PlayerSynergyConfig | None = None) -> None:
        self._config = config or PlayerSynergyConfig()
        self._lock = RLock()
        # {(pid1, pid2): _ComboRecord} — 정렬된 튜플
        self._pairs: dict[tuple[int, int], _ComboRecord] = {}
        self._triples: dict[tuple[int, int, int], _ComboRecord] = {}

    @property
    def name(self) -> str:
        return "PlayerSynergyAnalyzer"

    @property
    def total_pairs(self) -> int:
        with self._lock:
            return len(self._pairs)

    def record_possession(
        self,
        on_court_ids: list[int],
        points_scored: int = 0,
        points_allowed: int = 0,
    ) -> None:
        """
        현재 온코트 5인의 모든 2인/3인 조합에 점유 누적.

        Args:
            on_court_ids: 코트 위 선수 ID 리스트
            points_scored: 아군 득점
            points_allowed: 상대 득점
        """
        with self._lock:
            sorted_ids = sorted(on_court_ids)

            # 2인 조합
            for combo in combinations(sorted_ids, 2):
                key = (combo[0], combo[1])
                rec = self._pairs.get(key)
                if rec is None:
                    rec = _ComboRecord(player_ids=key)
                    self._pairs[key] = rec
                rec.possessions += 1
                rec.points_scored += points_scored
                rec.points_allowed += points_allowed

            # 3인 조합
            for combo in combinations(sorted_ids, 3):
                key = (combo[0], combo[1], combo[2])
                rec = self._triples.get(key)
                if rec is None:
                    rec = _ComboRecord(player_ids=key)
                    self._triples[key] = rec
                rec.possessions += 1
                rec.points_scored += points_scored
                rec.points_allowed += points_allowed

    def get_pair_net_rating(self, pid_a: int, pid_b: int) -> float:
        """2인 조합 넷레이팅 (per 100 possessions)."""
        with self._lock:
            key = tuple(sorted((pid_a, pid_b)))
            rec = self._pairs.get(key)  # type: ignore[arg-type]
            if rec is None or rec.possessions == 0:
                return 0.0
            return (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0

    def get_triple_net_rating(self, pid_a: int, pid_b: int, pid_c: int) -> float:
        """3인 조합 넷레이팅."""
        with self._lock:
            key = tuple(sorted((pid_a, pid_b, pid_c)))
            rec = self._triples.get(key)  # type: ignore[arg-type]
            if rec is None or rec.possessions == 0:
                return 0.0
            return (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0

    def get_best_pair(self) -> tuple[int, int] | None:
        """최고 시너지 2인 조합. 최소 점유 조건."""
        with self._lock:
            best: tuple[int, int] | None = None
            best_rating = float("-inf")
            for key, rec in self._pairs.items():
                if rec.possessions < self._config.min_possessions:
                    continue
                nr = (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0
                if nr > best_rating:
                    best_rating = nr
                    best = key
            return best

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_pairs": len(self._pairs),
                "total_triples": len(self._triples),
            }

    def reset(self) -> None:
        with self._lock:
            self._pairs.clear()
            self._triples.clear()

    def __repr__(self) -> str:
        return f"PlayerSynergyAnalyzer(pairs={len(self._pairs)})"


__all__ = ["PlayerSynergyAnalyzer", "PlayerSynergyConfig"]
__version__ = "1.0.0"
