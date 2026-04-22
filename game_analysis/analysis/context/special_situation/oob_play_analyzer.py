# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/special_situation
파일: oob_play_analyzer.py
설명: 아웃오브바운드(OOB) 플레이 분석기
      - 사이드라인/베이스라인 인바운드 플레이 성과
      - OOB 유형별 성공률/PPP
      - 턴오버율 분석

      Processing Cadence: POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 500


# =============================================================================
# Enum
# =============================================================================

@unique
class OOBType(str, Enum):
    """아웃오브바운드 유형."""

    SIDELINE = "sideline"    # 사이드라인 인바운드
    BASELINE = "baseline"    # 베이스라인 인바운드


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class OOBPlayAnalyzerConfig:
    """OOB 분석 설정."""

    max_records: int = _MAX_RECORDS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _OOBRecord:
    """OOB 점유 1건."""

    team_id: int
    oob_type: OOBType
    points_scored: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False
    five_sec_violation: bool = False  # 5초 바이올레이션


# =============================================================================
# Analyzer
# =============================================================================

class OOBPlayAnalyzer:
    """아웃오브바운드 플레이 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: OOBPlayAnalyzerConfig | None = None) -> None:
        self._config = config or OOBPlayAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_OOBRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "OOBPlayAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_oob_play(
        self,
        team_id: int,
        oob_type: OOBType,
        *,
        points_scored: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
        five_sec_violation: bool = False,
    ) -> None:
        """OOB 점유 1건 기록."""
        rec = _OOBRecord(
            team_id=team_id,
            oob_type=oob_type,
            points_scored=points_scored,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
            five_sec_violation=five_sec_violation,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("OOB 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_oob_ppp(self, team_id: int, oob_type: OOBType | None = None) -> float:
        """OOB PPP. oob_type=None이면 전체."""
        recs = self._filter(team_id, oob_type)
        if not recs:
            return 0.0
        return sum(r.points_scored for r in recs) / len(recs)

    def get_oob_fg_pct(self, team_id: int, oob_type: OOBType | None = None) -> float:
        """OOB FG%."""
        recs = self._filter(team_id, oob_type)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_turnover_rate(self, team_id: int, oob_type: OOBType | None = None) -> float:
        """OOB 턴오버율 (%)."""
        recs = self._filter(team_id, oob_type)
        if not recs:
            return 0.0
        turnovers = sum(1 for r in recs if r.turnover)
        return turnovers / len(recs) * 100.0

    def get_five_sec_violation_count(self, team_id: int) -> int:
        """5초 바이올레이션 횟수."""
        with self._lock:
            return sum(
                1 for r in self._records
                if r.team_id == team_id and r.five_sec_violation
            )

    def compare_oob_types(self, team_id: int) -> dict[str, float]:
        """사이드라인 vs 베이스라인 PPP 비교."""
        side = self.get_oob_ppp(team_id, OOBType.SIDELINE)
        base = self.get_oob_ppp(team_id, OOBType.BASELINE)
        return {
            "sideline_ppp": side,
            "baseline_ppp": base,
            "difference": side - base,
        }

    # ── 내부 ──

    def _filter(
        self, team_id: int, oob_type: OOBType | None,
    ) -> list[_OOBRecord]:
        with self._lock:
            if oob_type is None:
                return [r for r in self._records if r.team_id == team_id]
            return [
                r for r in self._records
                if r.team_id == team_id and r.oob_type == oob_type
            ]

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {"total_records": len(self._records)}

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"OOBPlayAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "OOBPlayAnalyzer",
    "OOBPlayAnalyzerConfig",
    "OOBType",
]

__version__ = "1.0.0"
