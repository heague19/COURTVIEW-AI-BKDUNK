# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/lineup_analysis
파일: lineup_efficiency.py
설명: 라인업 효율 분석기
      - 라인업별 넷레이팅, +/-
      - 최고/최저 효율 라인업 식별
      - 라인업 비교 (A vs B)

      Processing Cadence: 🔵 POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: (없음 — 순수 계산)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_LINEUP_RECORDS: Final[int] = 200


@dataclass(slots=True)
class LineupEfficiencyConfig:
    """라인업 효율 분석 설정."""

    max_records: int = _MAX_LINEUP_RECORDS
    # 유의미 판정 최소 점유 수
    min_possessions: int = 10


@dataclass(slots=True)
class _LineupEffRecord:
    """라인업 효율 누적."""

    lineup_id: str
    possessions: int = 0
    points_scored: int = 0
    points_allowed: int = 0


class LineupEfficiencyAnalyzer:
    """라인업 효율 분석기."""

    __slots__ = ("_config", "_lock", "_lineups")

    def __init__(self, config: LineupEfficiencyConfig | None = None) -> None:
        self._config = config or LineupEfficiencyConfig()
        self._lock = RLock()
        self._lineups: dict[str, _LineupEffRecord] = {}

    @property
    def name(self) -> str:
        return "LineupEfficiencyAnalyzer"

    @property
    def total_lineups(self) -> int:
        with self._lock:
            return len(self._lineups)

    def record_possession(
        self,
        lineup_id: str,
        points_scored: int = 0,
        points_allowed: int = 0,
    ) -> None:
        """라인업 점유 결과 누적."""
        with self._lock:
            rec = self._lineups.get(lineup_id)
            if rec is None:
                rec = _LineupEffRecord(lineup_id=lineup_id)
                self._lineups[lineup_id] = rec
            rec.possessions += 1
            rec.points_scored += points_scored
            rec.points_allowed += points_allowed

    def get_net_rating(self, lineup_id: str) -> float:
        """넷레이팅 (per 100 possessions)."""
        with self._lock:
            rec = self._lineups.get(lineup_id)
            if rec is None or rec.possessions == 0:
                return 0.0
            return (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0

    def get_plus_minus(self, lineup_id: str) -> int:
        """+/- 절대값."""
        with self._lock:
            rec = self._lineups.get(lineup_id)
            if rec is None:
                return 0
            return rec.points_scored - rec.points_allowed

    def get_best_lineup(self) -> str:
        """최고 넷레이팅 라인업 ID. 최소 점유 조건 적용."""
        with self._lock:
            best_id = ""
            best_rating = float("-inf")
            for lid, rec in self._lineups.items():
                if rec.possessions < self._config.min_possessions:
                    continue
                nr = (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0
                if nr > best_rating:
                    best_rating = nr
                    best_id = lid
            return best_id

    def get_worst_lineup(self) -> str:
        """최저 넷레이팅 라인업 ID."""
        with self._lock:
            worst_id = ""
            worst_rating = float("inf")
            for lid, rec in self._lineups.items():
                if rec.possessions < self._config.min_possessions:
                    continue
                nr = (rec.points_scored - rec.points_allowed) / rec.possessions * 100.0
                if nr < worst_rating:
                    worst_rating = nr
                    worst_id = lid
            return worst_id

    def compare_lineups(self, lineup_a: str, lineup_b: str) -> dict[str, float]:
        """두 라인업 비교."""
        nr_a = self.get_net_rating(lineup_a)
        nr_b = self.get_net_rating(lineup_b)
        return {
            "net_rating_a": nr_a,
            "net_rating_b": nr_b,
            "difference": nr_a - nr_b,
        }

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {"total_lineups": len(self._lineups)}

    def reset(self) -> None:
        with self._lock:
            self._lineups.clear()

    def __repr__(self) -> str:
        return f"LineupEfficiencyAnalyzer(lineups={len(self._lineups)})"


__all__ = ["LineupEfficiencyAnalyzer", "LineupEfficiencyConfig"]
__version__ = "1.0.0"
