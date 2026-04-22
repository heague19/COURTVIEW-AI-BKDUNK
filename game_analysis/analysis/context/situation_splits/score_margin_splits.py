# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/situation_splits
파일: score_margin_splits.py
설명: 점수차별 효율 스플릿
      - 점수차 구간별 효율 (큰 리드/근접/역전)
      - 클러치 상황 효율
      - 블로우아웃 vs 접전 비교

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


# =============================================================================
# Enum
# =============================================================================

@unique
class MarginBucket(str, Enum):
    """점수차 구간."""
    BLOWOUT_AHEAD = "blowout_ahead"       # +16 이상
    COMFORTABLE_AHEAD = "comfortable_ahead"  # +11 ~ +15
    AHEAD = "ahead"                         # +6 ~ +10
    CLOSE_AHEAD = "close_ahead"             # +1 ~ +5
    TIED = "tied"                           # 0
    CLOSE_BEHIND = "close_behind"           # -1 ~ -5
    BEHIND = "behind"                       # -6 ~ -10
    COMFORTABLE_BEHIND = "comfortable_behind"  # -11 ~ -15
    BLOWOUT_BEHIND = "blowout_behind"       # -16 이하


def _classify_margin(margin: int) -> MarginBucket:
    """점수차 → 구간 분류."""
    if margin >= 16:
        return MarginBucket.BLOWOUT_AHEAD
    if margin >= 11:
        return MarginBucket.COMFORTABLE_AHEAD
    if margin >= 6:
        return MarginBucket.AHEAD
    if margin >= 1:
        return MarginBucket.CLOSE_AHEAD
    if margin == 0:
        return MarginBucket.TIED
    if margin >= -5:
        return MarginBucket.CLOSE_BEHIND
    if margin >= -10:
        return MarginBucket.BEHIND
    if margin >= -15:
        return MarginBucket.COMFORTABLE_BEHIND
    return MarginBucket.BLOWOUT_BEHIND


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ScoreMarginSplitsConfig:
    """점수차별 스플릿 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _MarginRecord:
    """점수차별 점유 1건."""

    team_id: int
    margin: int  # 홈팀 기준 (양수=리드, 음수=뒤짐)
    bucket: MarginBucket
    points_scored: int = 0
    points_allowed: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class ScoreMarginSplitsAnalyzer:
    """점수차별 효율 스플릿 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: ScoreMarginSplitsConfig | None = None) -> None:
        self._config = config or ScoreMarginSplitsConfig()
        self._lock = RLock()
        self._records: list[_MarginRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ScoreMarginSplitsAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        margin: int,
        *,
        points_scored: int = 0,
        points_allowed: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
    ) -> MarginBucket:
        """점수차별 점유 1건 기록. 분류된 bucket 반환."""
        bucket = _classify_margin(margin)
        rec = _MarginRecord(
            team_id=team_id,
            margin=margin,
            bucket=bucket,
            points_scored=points_scored,
            points_allowed=points_allowed,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("점수차 스플릿 기록 한도 도달 (%d)", self._config.max_records)
                return bucket
            self._records.append(rec)
        return bucket

    # ── 조회 ──

    def get_bucket_split(
        self, team_id: int, bucket: MarginBucket,
    ) -> SituationSplitData:
        """특정 점수차 구간의 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.bucket == bucket
            ]
        return self._build_split(bucket.value, recs)

    def get_close_game_split(self, team_id: int) -> SituationSplitData:
        """접전 구간 (±5점 + 동점) 종합."""
        close_buckets = {
            MarginBucket.CLOSE_AHEAD,
            MarginBucket.TIED,
            MarginBucket.CLOSE_BEHIND,
        }
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.bucket in close_buckets
            ]
        return self._build_split("close_game", recs)

    def get_leading_split(self, team_id: int) -> SituationSplitData:
        """리드 중 종합 (양수 구간)."""
        lead_buckets = {
            MarginBucket.BLOWOUT_AHEAD,
            MarginBucket.COMFORTABLE_AHEAD,
            MarginBucket.AHEAD,
            MarginBucket.CLOSE_AHEAD,
        }
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.bucket in lead_buckets
            ]
        return self._build_split("leading", recs)

    def get_trailing_split(self, team_id: int) -> SituationSplitData:
        """뒤지는 중 종합 (음수 구간)."""
        trail_buckets = {
            MarginBucket.CLOSE_BEHIND,
            MarginBucket.BEHIND,
            MarginBucket.COMFORTABLE_BEHIND,
            MarginBucket.BLOWOUT_BEHIND,
        }
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.bucket in trail_buckets
            ]
        return self._build_split("trailing", recs)

    # ── 내부 유틸 ──

    def _build_split(
        self, split_name: str, recs: list[_MarginRecord],
    ) -> SituationSplitData:
        if not recs:
            return SituationSplitData(split_name=split_name)
        n = len(recs)
        scored = sum(r.points_scored for r in recs)
        allowed = sum(r.points_allowed for r in recs)
        attempts = sum(1 for r in recs if r.shot_attempted)
        made = sum(1 for r in recs if r.shot_made)
        turnovers = sum(1 for r in recs if r.turnover)
        off_rtg = scored / n * 100.0
        def_rtg = allowed / n * 100.0
        fg_pct = made / attempts * 100.0 if attempts > 0 else 0.0
        to_rate = turnovers / n * 100.0
        return SituationSplitData(
            split_name=split_name,
            offensive_rating=off_rtg,
            defensive_rating=def_rtg,
            net_rating=off_rtg - def_rtg,
            fg_pct=fg_pct,
            turnover_rate=to_rate,
        )

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "buckets": list({r.bucket.value for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ScoreMarginSplitsAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ScoreMarginSplitsAnalyzer",
    "ScoreMarginSplitsConfig",
    "MarginBucket",
]

__version__ = "1.0.0"
