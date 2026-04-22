# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/situation_splits
파일: shot_clock_splits.py
설명: 슛클락 구간별 효율 스플릿
      - 얼리 클락 (18~24초)
      - 미드 클락 (7~17초)
      - 레이트 클락 (0~6초)
      - 구간별 FG%, PPP, 턴오버율

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
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import SituationSplitData

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000

# 슛클락 구간 경계 (FIBA/NBA 공통 24초 기준)
_EARLY_CLOCK_MIN: Final[float] = 18.0
_MID_CLOCK_MIN: Final[float] = 7.0


# =============================================================================
# Enum
# =============================================================================

@unique
class ShotClockSegment(str, Enum):
    """슛클락 구간."""
    EARLY = "early_clock"   # 18~24초 (속공/얼리 오펜스)
    MID = "mid_clock"       # 7~17초 (세트 오펜스)
    LATE = "late_clock"     # 0~6초 (클락 만료 임박)


def _classify_shot_clock(remaining_sec: float) -> ShotClockSegment:
    """남은 슛클락 → 구간 분류."""
    if remaining_sec >= _EARLY_CLOCK_MIN:
        return ShotClockSegment.EARLY
    if remaining_sec >= _MID_CLOCK_MIN:
        return ShotClockSegment.MID
    return ShotClockSegment.LATE


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ShotClockSplitsConfig:
    """슛클락 스플릿 설정."""

    max_records: int = _MAX_RECORDS
    early_clock_min: float = _EARLY_CLOCK_MIN
    mid_clock_min: float = _MID_CLOCK_MIN


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ShotClockRecord:
    """슛클락별 점유 1건."""

    team_id: int
    shot_clock_remaining: float
    segment: ShotClockSegment
    points: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class ShotClockSplitsAnalyzer:
    """슛클락 구간별 효율 스플릿 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: ShotClockSplitsConfig | None = None) -> None:
        self._config = config or ShotClockSplitsConfig()
        self._lock = RLock()
        self._records: list[_ShotClockRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ShotClockSplitsAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        shot_clock_remaining: float,
        *,
        points: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
    ) -> ShotClockSegment:
        """슛클락별 점유 1건 기록. 분류된 segment 반환."""
        segment = _classify_shot_clock(shot_clock_remaining)
        rec = _ShotClockRecord(
            team_id=team_id,
            shot_clock_remaining=shot_clock_remaining,
            segment=segment,
            points=points,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("슛클락 스플릿 기록 한도 도달 (%d)", self._config.max_records)
                return segment
            self._records.append(rec)
        return segment

    # ── 조회 ──

    def get_segment_split(
        self, team_id: int, segment: ShotClockSegment,
    ) -> SituationSplitData:
        """특정 슛클락 구간의 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.segment == segment
            ]
        return self._build_split(segment.value, recs)

    def get_segment_ppp(self, team_id: int, segment: ShotClockSegment) -> float:
        """구간별 PPP."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.segment == segment
            ]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_segment_distribution(self, team_id: int) -> dict[str, int]:
        """구간별 점유 분포."""
        with self._lock:
            team_recs = [r for r in self._records if r.team_id == team_id]
        dist: dict[str, int] = {s.value: 0 for s in ShotClockSegment}
        for r in team_recs:
            dist[r.segment.value] += 1
        return dist

    def compare_segments(self, team_id: int) -> dict[str, float]:
        """구간별 PPP 비교."""
        return {
            seg.value: self.get_segment_ppp(team_id, seg)
            for seg in ShotClockSegment
        }

    # ── 내부 유틸 ──

    def _build_split(
        self, split_name: str, recs: list[_ShotClockRecord],
    ) -> SituationSplitData:
        if not recs:
            return SituationSplitData(split_name=split_name)
        n = len(recs)
        scored = sum(r.points for r in recs)
        attempts = sum(1 for r in recs if r.shot_attempted)
        made = sum(1 for r in recs if r.shot_made)
        turnovers = sum(1 for r in recs if r.turnover)
        off_rtg = scored / n * 100.0
        fg_pct = made / attempts * 100.0 if attempts > 0 else 0.0
        to_rate = turnovers / n * 100.0
        return SituationSplitData(
            split_name=split_name,
            offensive_rating=off_rtg,
            fg_pct=fg_pct,
            turnover_rate=to_rate,
        )

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "segments": list({r.segment.value for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ShotClockSplitsAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ShotClockSplitsAnalyzer",
    "ShotClockSplitsConfig",
    "ShotClockSegment",
]

__version__ = "1.0.0"
