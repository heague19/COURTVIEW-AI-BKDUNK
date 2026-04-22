# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/transition_analysis
파일: transition_offense.py
설명: 전환 공격 분석기
      - 1차 속공 (Primary Break)
      - 2차 속공 (Secondary Break)
      - 얼리 오펜스 (Early Offense)
      - 전환 PPP / FG% / 성공률

      Processing Cadence: 🟢 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.tactical_constants (PRIMARY_BREAK_MAX_SEC, SECONDARY_BREAK_MAX_SEC, classify_transition_phase)
  shared.constants.tactical_constants (TransitionPhase)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    PRIMARY_BREAK_MAX_SEC,
    SECONDARY_BREAK_MAX_SEC,
    TransitionPhase,
    classify_transition_phase,
)

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class TransitionOffenseConfig:
    """전환 공격 분석 설정."""

    max_records: int = _MAX_RECORDS
    primary_break_max_sec: float = PRIMARY_BREAK_MAX_SEC
    secondary_break_max_sec: float = SECONDARY_BREAK_MAX_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _TransitionRecord:
    """전환 공격 1건 기록."""

    team_id: int
    time_since_possession_sec: float
    phase: TransitionPhase
    shot_attempted: bool = False
    shot_made: bool = False
    points: int = 0
    turnover: bool = False
    foul_drawn: bool = False
    advantage: int = 0  # 공격인원 - 수비인원


# =============================================================================
# Analyzer
# =============================================================================

class TransitionOffenseAnalyzer:
    """전환 공격 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: TransitionOffenseConfig | None = None) -> None:
        self._config = config or TransitionOffenseConfig()
        self._lock = RLock()
        self._records: list[_TransitionRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "TransitionOffenseAnalyzer"

    @property
    def total_transitions(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_transition(
        self,
        team_id: int,
        time_since_possession_sec: float,
        *,
        shot_attempted: bool = False,
        shot_made: bool = False,
        points: int = 0,
        turnover: bool = False,
        foul_drawn: bool = False,
        advantage: int = 0,
    ) -> TransitionPhase:
        """전환 공격 1건 기록. 분류된 phase 반환."""
        phase = classify_transition_phase(time_since_possession_sec)
        rec = _TransitionRecord(
            team_id=team_id,
            time_since_possession_sec=time_since_possession_sec,
            phase=phase,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            points=points,
            turnover=turnover,
            foul_drawn=foul_drawn,
            advantage=advantage,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning(
                    "전환 공격 기록 한도 도달 (%d), 이후 기록 무시",
                    self._config.max_records,
                )
                return phase
            self._records.append(rec)
        return phase

    # ── 조회: 위상별 ──

    def _team_phase_records(
        self, team_id: int, phase: TransitionPhase,
    ) -> list[_TransitionRecord]:
        """팀 + phase 필터링."""
        with self._lock:
            return [
                r for r in self._records
                if r.team_id == team_id and r.phase == phase
            ]

    def _team_records(self, team_id: int) -> list[_TransitionRecord]:
        with self._lock:
            return [r for r in self._records if r.team_id == team_id]

    def get_phase_ppp(self, team_id: int, phase: TransitionPhase) -> float:
        """특정 전환 위상의 PPP (Points Per Possession)."""
        recs = self._team_phase_records(team_id, phase)
        if not recs:
            return 0.0
        total_pts = sum(r.points for r in recs)
        return total_pts / len(recs)

    def get_phase_fg_pct(self, team_id: int, phase: TransitionPhase) -> float:
        """특정 위상의 FG%."""
        recs = self._team_phase_records(team_id, phase)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_phase_success_rate(self, team_id: int, phase: TransitionPhase) -> float:
        """위상별 성공률 (득점 점유 / 전체 점유 %)."""
        recs = self._team_phase_records(team_id, phase)
        if not recs:
            return 0.0
        scored = sum(1 for r in recs if r.points > 0)
        return scored / len(recs) * 100.0

    # ── 조회: 전체 전환 ──

    def get_transition_ppp(self, team_id: int) -> float:
        """전체 전환 공격 PPP."""
        recs = self._team_records(team_id)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_transition_frequency(self, team_id: int, total_possessions: int) -> float:
        """전환 빈도 (전환 점유 / 전체 점유 %)."""
        if total_possessions <= 0:
            return 0.0
        recs = self._team_records(team_id)
        return len(recs) / total_possessions * 100.0

    def get_phase_breakdown(self, team_id: int) -> dict[str, int]:
        """위상별 전환 횟수."""
        recs = self._team_records(team_id)
        result: dict[str, int] = {
            TransitionPhase.PRIMARY_BREAK.value: 0,
            TransitionPhase.SECONDARY_BREAK.value: 0,
            TransitionPhase.EARLY_OFFENSE.value: 0,
        }
        for r in recs:
            result[r.phase.value] = result.get(r.phase.value, 0) + 1
        return result

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_transitions": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"TransitionOffenseAnalyzer(transitions={self.total_transitions})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TransitionOffenseAnalyzer",
    "TransitionOffenseConfig",
]

__version__ = "1.0.0"
