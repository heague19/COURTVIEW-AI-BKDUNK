# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: pick_and_roll.py
설명: 픽앤롤 분석기
      - 볼핸들러 효율 (PPP, FG%)
      - 롤맨/팝 효율
      - 스위치/ICE/드롭 수비 대응별 효율

      Processing Cadence: 🟢 POSSESSION (<100ms)

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

_MAX_RECORDS: Final[int] = 1500


# =============================================================================
# Enum
# =============================================================================

@unique
class PnRRole(str, Enum):
    """PnR 역할."""
    BALL_HANDLER = "ball_handler"
    ROLL_MAN = "roll_man"
    POP = "pop"


@unique
class PnRDefenseType(str, Enum):
    """PnR 수비 대응 유형."""
    DROP = "drop"
    SWITCH = "switch"
    ICE = "ice"
    HEDGE = "hedge"
    BLITZ = "blitz"
    UNKNOWN = "unknown"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class PickAndRollConfig:
    """픽앤롤 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_possessions: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PnRRecord:
    """PnR 1건 기록."""

    team_id: int
    handler_id: int
    screener_id: int
    role_result: PnRRole  # 마무리한 역할
    defense_type: PnRDefenseType
    shot_attempted: bool = False
    shot_made: bool = False
    points: int = 0
    turnover: bool = False
    foul_drawn: bool = False
    assist: bool = False


# =============================================================================
# Analyzer
# =============================================================================

class PickAndRollAnalyzer:
    """픽앤롤 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: PickAndRollConfig | None = None) -> None:
        self._config = config or PickAndRollConfig()
        self._lock = RLock()
        self._records: list[_PnRRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "PickAndRollAnalyzer"

    @property
    def total_pnr(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_pnr(
        self,
        team_id: int,
        handler_id: int,
        screener_id: int,
        role_result: PnRRole = PnRRole.BALL_HANDLER,
        defense_type: PnRDefenseType = PnRDefenseType.UNKNOWN,
        *,
        shot_attempted: bool = False,
        shot_made: bool = False,
        points: int = 0,
        turnover: bool = False,
        foul_drawn: bool = False,
        assist: bool = False,
    ) -> None:
        """PnR 1건 기록."""
        rec = _PnRRecord(
            team_id=team_id,
            handler_id=handler_id,
            screener_id=screener_id,
            role_result=role_result,
            defense_type=defense_type,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            points=points,
            turnover=turnover,
            foul_drawn=foul_drawn,
            assist=assist,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("PnR 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 역할별 ──

    def _team_role_records(
        self, team_id: int, role: PnRRole,
    ) -> list[_PnRRecord]:
        with self._lock:
            return [
                r for r in self._records
                if r.team_id == team_id and r.role_result == role
            ]

    def get_role_ppp(self, team_id: int, role: PnRRole) -> float:
        """역할별 PPP."""
        recs = self._team_role_records(team_id, role)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_role_fg_pct(self, team_id: int, role: PnRRole) -> float:
        """역할별 FG%."""
        recs = self._team_role_records(team_id, role)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_role_turnover_rate(self, team_id: int, role: PnRRole) -> float:
        """역할별 턴오버율 (%)."""
        recs = self._team_role_records(team_id, role)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.turnover) / len(recs) * 100.0

    # ── 조회: 수비 대응별 ──

    def get_defense_ppp(self, team_id: int, defense: PnRDefenseType) -> float:
        """수비 대응 유형별 PPP."""
        with self._lock:
            recs = [
                r for r in self._records
                if r.team_id == team_id and r.defense_type == defense
            ]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    # ── 조회: 전체 ──

    def get_team_pnr_ppp(self, team_id: int) -> float:
        """팀 전체 PnR PPP."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_team_pnr_frequency(self, team_id: int, total_possessions: int) -> float:
        """PnR 빈도 (%)."""
        if total_possessions <= 0:
            return 0.0
        with self._lock:
            count = sum(1 for r in self._records if r.team_id == team_id)
        return count / total_possessions * 100.0

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_pnr": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"PickAndRollAnalyzer(pnr={self.total_pnr})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PickAndRollAnalyzer",
    "PickAndRollConfig",
    "PnRRole",
    "PnRDefenseType",
]

__version__ = "1.0.0"
