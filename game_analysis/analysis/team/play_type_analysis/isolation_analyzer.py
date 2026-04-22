# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: isolation_analyzer.py
설명: 아이솔레이션 분석기
      - 선수별 ISO PPP / FG% / 턴오버율
      - 결과 유형별 분석 (슛/드라이브/패스아웃/턴오버)
      - 팀 ISO 빈도

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
class IsoResult(str, Enum):
    """ISO 결과 유형."""
    SHOT = "shot"
    DRIVE = "drive"
    PASS_OUT = "pass_out"
    TURNOVER = "turnover"
    FOUL_DRAWN = "foul_drawn"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class IsolationConfig:
    """아이솔레이션 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_possessions: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _IsoRecord:
    """ISO 1건 기록."""

    team_id: int
    player_id: int
    result_type: IsoResult
    shot_attempted: bool = False
    shot_made: bool = False
    points: int = 0


# =============================================================================
# Analyzer
# =============================================================================

class IsolationAnalyzer:
    """아이솔레이션 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: IsolationConfig | None = None) -> None:
        self._config = config or IsolationConfig()
        self._lock = RLock()
        self._records: list[_IsoRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "IsolationAnalyzer"

    @property
    def total_iso(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_iso(
        self,
        team_id: int,
        player_id: int,
        result_type: IsoResult = IsoResult.SHOT,
        *,
        shot_attempted: bool = False,
        shot_made: bool = False,
        points: int = 0,
    ) -> None:
        """ISO 1건 기록."""
        rec = _IsoRecord(
            team_id=team_id,
            player_id=player_id,
            result_type=result_type,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            points=points,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("ISO 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 선수별 ──

    def _player_records(self, player_id: int) -> list[_IsoRecord]:
        with self._lock:
            return [r for r in self._records if r.player_id == player_id]

    def get_player_ppp(self, player_id: int) -> float:
        """선수 ISO PPP."""
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_player_fg_pct(self, player_id: int) -> float:
        """선수 ISO FG%."""
        recs = self._player_records(player_id)
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_player_turnover_rate(self, player_id: int) -> float:
        """선수 ISO 턴오버율 (%)."""
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.result_type == IsoResult.TURNOVER) / len(recs) * 100.0

    def get_player_result_breakdown(self, player_id: int) -> dict[str, int]:
        """선수별 ISO 결과 유형 분포."""
        recs = self._player_records(player_id)
        result: dict[str, int] = {e.value: 0 for e in IsoResult}
        for r in recs:
            result[r.result_type.value] += 1
        return result

    # ── 조회: 팀별 ──

    def get_team_ppp(self, team_id: int) -> float:
        """팀 ISO PPP."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        return sum(r.points for r in recs) / len(recs)

    def get_team_frequency(self, team_id: int, total_possessions: int) -> float:
        """팀 ISO 빈도 (%)."""
        if total_possessions <= 0:
            return 0.0
        with self._lock:
            count = sum(1 for r in self._records if r.team_id == team_id)
        return count / total_possessions * 100.0

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_iso": len(self._records),
                "teams": list({r.team_id for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"IsolationAnalyzer(iso={self.total_iso})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "IsolationAnalyzer",
    "IsolationConfig",
    "IsoResult",
]

__version__ = "1.0.0"
