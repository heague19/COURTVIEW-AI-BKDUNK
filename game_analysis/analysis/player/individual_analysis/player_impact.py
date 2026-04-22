# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: player_impact.py
설명: 선수 영향력 분석기
      - 온코트/오프코트 넷레이팅 계산
      - 온코트 vs 오프코트 차이 (Impact Differential)
      - IndividualAnalysis DTO 내 on/off_court_net_rating 제공

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.dto.tactical_dto (IndividualAnalysis DTO — on/off_court_net_rating)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)


@dataclass(slots=True)
class PlayerImpactConfig:
    """선수 영향력 분석 설정."""

    # 유의미한 판단을 위한 최소 점유 수
    min_possessions: int = 10


@dataclass(slots=True)
class _StintAccumulator:
    """온코트/오프코트 누적기."""

    possessions: int = 0
    points_scored: int = 0
    points_allowed: int = 0


class PlayerImpactAnalyzer:
    """선수 영향력 (온/오프코트 넷레이팅) 분석기."""

    __slots__ = ("_config", "_lock", "_on_court", "_off_court")

    def __init__(self, config: PlayerImpactConfig | None = None) -> None:
        self._config = config or PlayerImpactConfig()
        self._lock = RLock()
        # {player_id: _StintAccumulator}
        self._on_court: dict[int, _StintAccumulator] = {}
        self._off_court: dict[int, _StintAccumulator] = {}

    @property
    def name(self) -> str:
        return "PlayerImpactAnalyzer"

    @property
    def players_tracked(self) -> int:
        with self._lock:
            return len(self._on_court)

    def record_possession(
        self,
        on_court_ids: list[int],
        all_team_ids: list[int],
        points_scored: int,
        points_allowed: int,
    ) -> None:
        """
        점유 결과를 온코트/오프코트에 각각 누적.

        Args:
            on_court_ids: 현재 코트 위 5명 tracking_id
            all_team_ids: 팀 전체 선수 목록
            points_scored: 아군 득점
            points_allowed: 상대 득점
        """
        with self._lock:
            on_set = set(on_court_ids)

            for pid in all_team_ids:
                if pid in on_set:
                    acc = self._on_court.setdefault(pid, _StintAccumulator())
                    acc.possessions += 1
                    acc.points_scored += points_scored
                    acc.points_allowed += points_allowed
                else:
                    acc = self._off_court.setdefault(pid, _StintAccumulator())
                    acc.possessions += 1
                    acc.points_scored += points_scored
                    acc.points_allowed += points_allowed

    def get_on_court_net_rating(self, player_id: int) -> float:
        """온코트 넷레이팅 (per 100 possessions)."""
        with self._lock:
            return self._net_rating(self._on_court.get(player_id))

    def get_off_court_net_rating(self, player_id: int) -> float:
        """오프코트 넷레이팅 (per 100 possessions)."""
        with self._lock:
            return self._net_rating(self._off_court.get(player_id))

    def get_impact_differential(self, player_id: int) -> float:
        """온코트 - 오프코트 차이."""
        return self.get_on_court_net_rating(player_id) - self.get_off_court_net_rating(player_id)

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "players_tracked": len(self._on_court),
            }

    def reset(self) -> None:
        with self._lock:
            self._on_court.clear()
            self._off_court.clear()

    def __repr__(self) -> str:
        return f"PlayerImpactAnalyzer(players={self.players_tracked})"

    @staticmethod
    def _net_rating(acc: _StintAccumulator | None) -> float:
        if acc is None or acc.possessions == 0:
            return 0.0
        return (acc.points_scored - acc.points_allowed) / acc.possessions * 100.0


__all__ = ["PlayerImpactAnalyzer", "PlayerImpactConfig"]
__version__ = "1.0.0"
