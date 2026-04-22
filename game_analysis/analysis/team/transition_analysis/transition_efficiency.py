# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/transition_analysis
파일: transition_efficiency.py
설명: 전환 vs 하프코트 효율 집계
      - 전환/하프코트 PPP 비교
      - TransitionData DTO 생성
      - 팀별 전환 의존도 분석

      Processing Cadence: 🟢 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.tactical_dto (TransitionData)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import TransitionData

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 3000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class TransitionEfficiencyConfig:
    """전환 효율 집계 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PossessionRecord:
    """점유 1건 기록 (전환 or 하프코트)."""

    team_id: int
    is_transition: bool
    points: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class TransitionEfficiencyAnalyzer:
    """전환 vs 하프코트 효율 비교 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: TransitionEfficiencyConfig | None = None) -> None:
        self._config = config or TransitionEfficiencyConfig()
        self._lock = RLock()
        self._records: list[_PossessionRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "TransitionEfficiencyAnalyzer"

    @property
    def total_possessions(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_possession(
        self,
        team_id: int,
        is_transition: bool,
        *,
        points: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
    ) -> None:
        """점유 1건 기록 (전환 여부 포함)."""
        rec = _PossessionRecord(
            team_id=team_id,
            is_transition=is_transition,
            points=points,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning(
                    "점유 기록 한도 도달 (%d), 이후 기록 무시",
                    self._config.max_records,
                )
                return
            self._records.append(rec)

    # ── 조회: PPP ──

    def _filter(self, team_id: int, is_transition: bool) -> list[_PossessionRecord]:
        with self._lock:
            return [
                r for r in self._records
                if r.team_id == team_id and r.is_transition == is_transition
            ]

    def _team_records(self, team_id: int) -> list[_PossessionRecord]:
        with self._lock:
            return [r for r in self._records if r.team_id == team_id]

    def get_transition_ppp(self, team_id: int) -> float:
        """전환 공격 PPP."""
        recs = self._filter(team_id, True)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_halfcourt_ppp(self, team_id: int) -> float:
        """하프코트 공격 PPP."""
        recs = self._filter(team_id, False)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_transition_frequency(self, team_id: int) -> float:
        """전환 빈도 (전환 점유 / 전체 점유 %)."""
        team_recs = self._team_records(team_id)
        if not team_recs:
            return 0.0
        trans = sum(1 for r in team_recs if r.is_transition)
        return trans / len(team_recs) * 100.0

    def get_fg_pct(self, team_id: int, is_transition: bool) -> float:
        """전환/하프코트 FG%."""
        recs = self._filter(team_id, is_transition)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_turnover_rate(self, team_id: int, is_transition: bool) -> float:
        """전환/하프코트 턴오버율 (%)."""
        recs = self._filter(team_id, is_transition)
        if not recs:
            return 0.0
        turnovers = sum(1 for r in recs if r.turnover)
        return turnovers / len(recs) * 100.0

    # ── DTO 생성 ──

    def get_transition_data(
        self,
        team_id: int,
        *,
        first_wave_success_rate: float = 0.0,
        second_wave_success_rate: float = 0.0,
        defensive_recovery_rate: float = 0.0,
    ) -> TransitionData:
        """TransitionData DTO 생성. 외부 데이터(속공 성공률, 수비 복귀율) 주입."""
        return TransitionData(
            transition_ppp=self.get_transition_ppp(team_id),
            halfcourt_ppp=self.get_halfcourt_ppp(team_id),
            transition_frequency=self.get_transition_frequency(team_id),
            first_wave_success_rate=first_wave_success_rate,
            second_wave_success_rate=second_wave_success_rate,
            defensive_recovery_rate=defensive_recovery_rate,
        )

    def compare_efficiency(self, team_id: int) -> dict[str, float]:
        """전환 vs 하프코트 효율 비교."""
        t_ppp = self.get_transition_ppp(team_id)
        h_ppp = self.get_halfcourt_ppp(team_id)
        return {
            "transition_ppp": t_ppp,
            "halfcourt_ppp": h_ppp,
            "ppp_difference": t_ppp - h_ppp,
            "transition_frequency": self.get_transition_frequency(team_id),
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            trans = sum(1 for r in self._records if r.is_transition)
            return {
                "total_possessions": len(self._records),
                "transition_possessions": trans,
                "halfcourt_possessions": len(self._records) - trans,
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"TransitionEfficiencyAnalyzer(possessions={self.total_possessions})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TransitionEfficiencyAnalyzer",
    "TransitionEfficiencyConfig",
]

__version__ = "1.0.0"
