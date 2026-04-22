# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/special_situation
파일: last_possession.py
설명: 라스트 포제션 분석기
      - 쿼터/하프/경기 종료 직전 마지막 점유 추적
      - 라스트 포제션 플레이 유형별 성과
      - 클러치 라스트 포제션 효율

      Processing Cadence: POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (is_clutch_situation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.stats_constants import is_clutch_situation

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 500
_LAST_POSSESSION_THRESHOLD_SEC: Final[int] = 24  # 슛클락 1회 이내


# =============================================================================
# Enum
# =============================================================================

@unique
class LastPossessionType(str, Enum):
    """라스트 포제션 상황."""

    END_OF_QUARTER = "end_of_quarter"
    END_OF_HALF = "end_of_half"
    END_OF_GAME = "end_of_game"
    END_OF_OT = "end_of_overtime"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class LastPossessionConfig:
    """라스트 포제션 분석 설정."""

    max_records: int = _MAX_RECORDS
    threshold_sec: int = _LAST_POSSESSION_THRESHOLD_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _LastPossRecord:
    """라스트 포제션 1건."""

    team_id: int
    possession_type: LastPossessionType
    period: int
    time_remaining_sec: int
    score_margin: int
    points_scored: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False
    is_clutch: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class LastPossessionAnalyzer:
    """라스트 포제션 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: LastPossessionConfig | None = None) -> None:
        self._config = config or LastPossessionConfig()
        self._lock = RLock()
        self._records: list[_LastPossRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "LastPossessionAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_last_possession(
        self,
        team_id: int,
        possession_type: LastPossessionType,
        period: int,
        time_remaining_sec: int,
        score_margin: int,
        *,
        points_scored: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
    ) -> None:
        """라스트 포제션 1건 기록."""
        clutch = is_clutch_situation(score_margin, time_remaining_sec, period)
        rec = _LastPossRecord(
            team_id=team_id,
            possession_type=possession_type,
            period=period,
            time_remaining_sec=time_remaining_sec,
            score_margin=score_margin,
            points_scored=points_scored,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
            is_clutch=clutch,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("라스트 포제션 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_last_poss_ppp(
        self, team_id: int, possession_type: LastPossessionType | None = None,
    ) -> float:
        """라스트 포제션 PPP."""
        recs = self._filter(team_id, possession_type)
        if not recs:
            return 0.0
        return sum(r.points_scored for r in recs) / len(recs)

    def get_last_poss_fg_pct(
        self, team_id: int, possession_type: LastPossessionType | None = None,
    ) -> float:
        """라스트 포제션 FG%."""
        recs = self._filter(team_id, possession_type)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_clutch_last_poss_ppp(self, team_id: int) -> float:
        """클러치 상황 라스트 포제션 PPP."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.is_clutch
            ]
        if not recs:
            return 0.0
        return sum(r.points_scored for r in recs) / len(recs)

    def get_turnover_rate(
        self, team_id: int, possession_type: LastPossessionType | None = None,
    ) -> float:
        """라스트 포제션 턴오버율 (%)."""
        recs = self._filter(team_id, possession_type)
        if not recs:
            return 0.0
        turnovers = sum(1 for r in recs if r.turnover)
        return turnovers / len(recs) * 100.0

    def get_type_distribution(self, team_id: int) -> dict[str, int]:
        """라스트 포제션 유형 분포."""
        with self._lock:
            team_recs = [r for r in self._records if r.team_id == team_id]
        dist: dict[str, int] = {}
        for r in team_recs:
            dist[r.possession_type.value] = dist.get(r.possession_type.value, 0) + 1
        return dist

    # ── 내부 ──

    def _filter(
        self, team_id: int, ptype: LastPossessionType | None,
    ) -> list[_LastPossRecord]:
        with self._lock:
            if ptype is None:
                return [r for r in self._records if r.team_id == team_id]
            return [
                r for r in self._records
                if r.team_id == team_id and r.possession_type == ptype
            ]

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            clutch = sum(1 for r in self._records if r.is_clutch)
            return {
                "total_records": len(self._records),
                "clutch_last_possessions": clutch,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"LastPossessionAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "LastPossessionAnalyzer",
    "LastPossessionConfig",
    "LastPossessionType",
]

__version__ = "1.0.0"
