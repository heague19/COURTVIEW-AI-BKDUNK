# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/transition_analysis
파일: transition_defense.py
설명: 전환 수비 분석기
      - 수비 복귀 시간 추적
      - 복귀 성공/실패율
      - 팀/선수별 전환 수비 품질

      Processing Cadence: 🟢 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.tactical_constants (DEFENSIVE_TRANSITION_TARGET_SEC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import DEFENSIVE_TRANSITION_TARGET_SEC

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class TransitionDefenseConfig:
    """전환 수비 분석 설정."""

    max_records: int = _MAX_RECORDS
    recovery_target_sec: float = DEFENSIVE_TRANSITION_TARGET_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _RecoveryRecord:
    """수비 복귀 1건 기록."""

    team_id: int
    recovery_time_sec: float  # 점유 전환 → 5인 하프코트 복귀 시간
    recovered: bool  # 목표 시간 내 복귀 여부
    points_allowed: int = 0
    shot_allowed: bool = False
    shot_made_by_opponent: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class TransitionDefenseAnalyzer:
    """전환 수비 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: TransitionDefenseConfig | None = None) -> None:
        self._config = config or TransitionDefenseConfig()
        self._lock = RLock()
        self._records: list[_RecoveryRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "TransitionDefenseAnalyzer"

    @property
    def total_recoveries(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_recovery(
        self,
        team_id: int,
        recovery_time_sec: float,
        *,
        points_allowed: int = 0,
        shot_allowed: bool = False,
        shot_made_by_opponent: bool = False,
    ) -> bool:
        """수비 복귀 1건 기록. 목표 시간 내 복귀 여부 반환."""
        recovered = recovery_time_sec <= self._config.recovery_target_sec
        rec = _RecoveryRecord(
            team_id=team_id,
            recovery_time_sec=recovery_time_sec,
            recovered=recovered,
            points_allowed=points_allowed,
            shot_allowed=shot_allowed,
            shot_made_by_opponent=shot_made_by_opponent,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning(
                    "전환 수비 기록 한도 도달 (%d), 이후 기록 무시",
                    self._config.max_records,
                )
                return recovered
            self._records.append(rec)
        return recovered

    # ── 조회 ──

    def _team_records(self, team_id: int) -> list[_RecoveryRecord]:
        with self._lock:
            return [r for r in self._records if r.team_id == team_id]

    def get_recovery_rate(self, team_id: int) -> float:
        """수비 복귀 성공률 (목표 시간 내 복귀 %)."""
        recs = self._team_records(team_id)
        if not recs:
            return 0.0
        ok = sum(1 for r in recs if r.recovered)
        return ok / len(recs) * 100.0

    def get_avg_recovery_time(self, team_id: int) -> float:
        """평균 수비 복귀 시간 (초)."""
        recs = self._team_records(team_id)
        if not recs:
            return 0.0
        return sum(r.recovery_time_sec for r in recs) / len(recs)

    def get_points_allowed_on_transition(self, team_id: int) -> float:
        """전환 수비 시 허용 PPP."""
        recs = self._team_records(team_id)
        if not recs:
            return 0.0
        return sum(r.points_allowed for r in recs) / len(recs)

    def get_opponent_fg_pct_on_transition(self, team_id: int) -> float:
        """전환 수비 시 상대 FG%."""
        recs = self._team_records(team_id)
        attempts = sum(1 for r in recs if r.shot_allowed)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made_by_opponent)
        return made / attempts * 100.0

    def get_late_recovery_penalty(self, team_id: int) -> dict[str, float]:
        """미복귀(late recovery) 시 vs 복귀 시 허용 PPP 비교."""
        recs = self._team_records(team_id)
        ok_recs = [r for r in recs if r.recovered]
        late_recs = [r for r in recs if not r.recovered]
        ok_ppp = (
            sum(r.points_allowed for r in ok_recs) / len(ok_recs)
            if ok_recs else 0.0
        )
        late_ppp = (
            sum(r.points_allowed for r in late_recs) / len(late_recs)
            if late_recs else 0.0
        )
        return {
            "recovered_ppp": ok_ppp,
            "late_ppp": late_ppp,
            "penalty": late_ppp - ok_ppp,
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_recoveries": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"TransitionDefenseAnalyzer(recoveries={self.total_recoveries})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TransitionDefenseAnalyzer",
    "TransitionDefenseConfig",
]

__version__ = "1.0.0"
