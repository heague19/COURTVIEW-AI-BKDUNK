# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/situation_splits
파일: game_context_analyzer.py
설명: 종합 상황 분석기
      - 클러치 상황 효율 (is_clutch_situation 활용)
      - 가비지 타임 효율
      - 종합 상황 데이터 집계

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (is_clutch_situation, WP_CLUTCH_MARGIN_POINTS, WP_CLUTCH_TIME_REMAINING_SEC)
  shared.dto.tactical_dto (SituationSplitData)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.stats_constants import (
    WP_CLUTCH_MARGIN_POINTS,
    WP_CLUTCH_TIME_REMAINING_SEC,
    is_clutch_situation,
)
from shared.dto.tactical_dto import SituationSplitData

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000
_GARBAGE_MARGIN: Final[int] = 25  # 25점 차 이상 = 가비지 타임


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class GameContextConfig:
    """종합 상황 분석 설정."""

    max_records: int = _MAX_RECORDS
    garbage_margin: int = _GARBAGE_MARGIN


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ContextRecord:
    """상황별 점유 1건."""

    team_id: int
    period: int
    time_remaining_sec: int
    score_margin: int  # 팀 기준 (양수=리드)
    is_clutch: bool
    is_garbage: bool
    points_scored: int = 0
    points_allowed: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class GameContextAnalyzer:
    """종합 상황 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: GameContextConfig | None = None) -> None:
        self._config = config or GameContextConfig()
        self._lock = RLock()
        self._records: list[_ContextRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "GameContextAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        period: int,
        time_remaining_sec: int,
        score_margin: int,
        *,
        points_scored: int = 0,
        points_allowed: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
    ) -> None:
        """상황별 점유 1건 기록."""
        clutch = is_clutch_situation(score_margin, time_remaining_sec, period)
        garbage = abs(score_margin) >= self._config.garbage_margin
        rec = _ContextRecord(
            team_id=team_id,
            period=period,
            time_remaining_sec=time_remaining_sec,
            score_margin=score_margin,
            is_clutch=clutch,
            is_garbage=garbage,
            points_scored=points_scored,
            points_allowed=points_allowed,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("상황 분석 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_clutch_split(self, team_id: int) -> SituationSplitData:
        """클러치 상황 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.is_clutch
            ]
        return self._build_split("clutch", recs)

    def get_non_clutch_split(self, team_id: int) -> SituationSplitData:
        """비클러치 상황 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and not r.is_clutch and not r.is_garbage
            ]
        return self._build_split("non_clutch", recs)

    def get_garbage_split(self, team_id: int) -> SituationSplitData:
        """가비지 타임 스플릿."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.is_garbage
            ]
        return self._build_split("garbage_time", recs)

    def get_clutch_count(self, team_id: int) -> int:
        """클러치 상황 점유 수."""
        with self._lock:
            return sum(
                1 for r in self._records
                if r.team_id == team_id and r.is_clutch
            )

    def compare_clutch_vs_normal(self, team_id: int) -> dict[str, float]:
        """클러치 vs 비클러치 넷레이팅 비교."""
        clutch = self.get_clutch_split(team_id)
        normal = self.get_non_clutch_split(team_id)
        return {
            "clutch_net": clutch.net_rating,
            "non_clutch_net": normal.net_rating,
            "difference": clutch.net_rating - normal.net_rating,
        }

    # ── 내부 유틸 ──

    def _build_split(
        self, split_name: str, recs: list[_ContextRecord],
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
            clutch = sum(1 for r in self._records if r.is_clutch)
            garbage = sum(1 for r in self._records if r.is_garbage)
            return {
                "total_records": len(self._records),
                "clutch_possessions": clutch,
                "garbage_possessions": garbage,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"GameContextAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "GameContextAnalyzer",
    "GameContextConfig",
]

__version__ = "1.0.0"
