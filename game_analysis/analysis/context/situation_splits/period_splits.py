# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/situation_splits
파일: period_splits.py
설명: 쿼터/하프/OT별 효율 스플릿
      - 쿼터별 득실점, FG%, 턴오버율
      - 전반/후반 비교
      - OT 효율 별도 추적
      - SituationSplitData DTO 생성

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.tactical_dto (SituationSplitData)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import SituationSplitData

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PeriodSplitsConfig:
    """쿼터별 스플릿 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PeriodRecord:
    """쿼터별 점유 1건."""

    team_id: int
    period: int  # 1~4: 쿼터, 5+: OT
    points_scored: int = 0
    points_allowed: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False
    minutes: float = 0.0


# =============================================================================
# Analyzer
# =============================================================================

class PeriodSplitsAnalyzer:
    """쿼터/하프/OT별 효율 스플릿 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: PeriodSplitsConfig | None = None) -> None:
        self._config = config or PeriodSplitsConfig()
        self._lock = RLock()
        self._records: list[_PeriodRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PeriodSplitsAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        period: int,
        *,
        points_scored: int = 0,
        points_allowed: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
        minutes: float = 0.0,
    ) -> None:
        """쿼터별 점유 1건 기록."""
        rec = _PeriodRecord(
            team_id=team_id,
            period=period,
            points_scored=points_scored,
            points_allowed=points_allowed,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
            minutes=minutes,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("쿼터 스플릿 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 쿼터별 ──

    def _team_period_records(
        self, team_id: int, periods: list[int],
    ) -> list[_PeriodRecord]:
        with self._lock:
            return [
                r for r in self._records
                if r.team_id == team_id and r.period in periods
            ]

    def get_period_split(self, team_id: int, period: int) -> SituationSplitData:
        """특정 쿼터의 SituationSplitData."""
        recs = self._team_period_records(team_id, [period])
        return self._build_split(f"Q{period}", recs)

    def get_first_half(self, team_id: int) -> SituationSplitData:
        """전반 (Q1+Q2) 스플릿."""
        recs = self._team_period_records(team_id, [1, 2])
        return self._build_split("first_half", recs)

    def get_second_half(self, team_id: int) -> SituationSplitData:
        """후반 (Q3+Q4) 스플릿."""
        recs = self._team_period_records(team_id, [3, 4])
        return self._build_split("second_half", recs)

    def get_overtime(self, team_id: int) -> SituationSplitData:
        """OT 전체 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.period >= 5
            ]
        return self._build_split("overtime", recs)

    def compare_halves(self, team_id: int) -> dict[str, float]:
        """전반 vs 후반 넷레이팅 비교."""
        first = self.get_first_half(team_id)
        second = self.get_second_half(team_id)
        return {
            "first_half_net": first.net_rating,
            "second_half_net": second.net_rating,
            "difference": second.net_rating - first.net_rating,
        }

    # ── 내부 유틸 ──

    def _build_split(
        self, split_name: str, recs: list[_PeriodRecord],
    ) -> SituationSplitData:
        """기록 리스트로부터 SituationSplitData 생성."""
        if not recs:
            return SituationSplitData(split_name=split_name)
        n = len(recs)
        scored = sum(r.points_scored for r in recs)
        allowed = sum(r.points_allowed for r in recs)
        minutes = sum(r.minutes for r in recs)
        attempts = sum(1 for r in recs if r.shot_attempted)
        made = sum(1 for r in recs if r.shot_made)
        turnovers = sum(1 for r in recs if r.turnover)
        off_rtg = scored / n * 100.0
        def_rtg = allowed / n * 100.0
        fg_pct = made / attempts * 100.0 if attempts > 0 else 0.0
        to_rate = turnovers / n * 100.0
        return SituationSplitData(
            split_name=split_name,
            minutes=minutes,
            offensive_rating=off_rtg,
            defensive_rating=def_rtg,
            net_rating=off_rtg - def_rtg,
            fg_pct=fg_pct,
            turnover_rate=to_rate,
        )

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            periods = sorted({r.period for r in self._records})
            return {
                "total_records": len(self._records),
                "periods": periods,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"PeriodSplitsAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PeriodSplitsAnalyzer",
    "PeriodSplitsConfig",
]

__version__ = "1.0.0"
