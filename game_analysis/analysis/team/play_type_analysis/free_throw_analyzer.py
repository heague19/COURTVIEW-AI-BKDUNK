# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/play_type_analysis
파일: free_throw_analyzer.py
설명: 자유투 심층 분석기
      - 선수별 자유투 성공률
      - 상황별 분석 (클러치/비클러치, 앤드원, 테크니컬)
      - 자유투 루틴 시간
      - 팀 자유투 통계

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

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# Enum
# =============================================================================

@unique
class FreeThrowContext(str, Enum):
    """자유투 상황 유형."""
    NORMAL = "normal"
    AND_ONE = "and_one"
    TECHNICAL = "technical"
    FLAGRANT = "flagrant"
    CLUTCH = "clutch"  # 4Q/OT 5분 이내, 5점 이내


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class FreeThrowAnalyzerConfig:
    """자유투 분석 설정."""

    max_records: int = _MAX_RECORDS
    min_attempts: int = 5


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _FreeThrowRecord:
    """자유투 1건 기록."""

    team_id: int
    player_id: int
    made: bool
    context: FreeThrowContext
    attempt_number: int = 1  # N번째 자유투 (1, 2, 3)
    total_attempts: int = 2  # 해당 세트 총 시도 수
    routine_time_sec: float = 0.0  # 루틴 시간 (공 받기 ~ 릴리스)


# =============================================================================
# Analyzer
# =============================================================================

class FreeThrowAnalyzer:
    """자유투 심층 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: FreeThrowAnalyzerConfig | None = None) -> None:
        self._config = config or FreeThrowAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_FreeThrowRecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "FreeThrowAnalyzer"

    @property
    def total_attempts(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_free_throw(
        self,
        team_id: int,
        player_id: int,
        made: bool,
        context: FreeThrowContext = FreeThrowContext.NORMAL,
        *,
        attempt_number: int = 1,
        total_attempts: int = 2,
        routine_time_sec: float = 0.0,
    ) -> None:
        """자유투 1건 기록."""
        rec = _FreeThrowRecord(
            team_id=team_id,
            player_id=player_id,
            made=made,
            context=context,
            attempt_number=attempt_number,
            total_attempts=total_attempts,
            routine_time_sec=routine_time_sec,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("자유투 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회: 선수별 ──

    def _player_records(self, player_id: int) -> list[_FreeThrowRecord]:
        with self._lock:
            return [r for r in self._records if r.player_id == player_id]

    def get_player_ft_pct(self, player_id: int) -> float:
        """선수 전체 자유투 성공률 (%)."""
        recs = self._player_records(player_id)
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.made)
        return made / len(recs) * 100.0

    def get_player_context_ft_pct(
        self, player_id: int, context: FreeThrowContext,
    ) -> float:
        """상황별 자유투 성공률."""
        recs = [r for r in self._player_records(player_id) if r.context == context]
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.made)
        return made / len(recs) * 100.0

    def get_player_avg_routine_time(self, player_id: int) -> float:
        """선수 평균 루틴 시간 (초)."""
        recs = self._player_records(player_id)
        timed = [r for r in recs if r.routine_time_sec > 0]
        if not timed:
            return 0.0
        return sum(r.routine_time_sec for r in timed) / len(timed)

    def get_player_first_vs_last(self, player_id: int) -> dict[str, float]:
        """첫 번째 자유투 vs 마지막 자유투 성공률 비교."""
        recs = self._player_records(player_id)
        first = [r for r in recs if r.attempt_number == 1]
        last = [r for r in recs if r.attempt_number == r.total_attempts]
        first_pct = (
            sum(1 for r in first if r.made) / len(first) * 100.0
            if first else 0.0
        )
        last_pct = (
            sum(1 for r in last if r.made) / len(last) * 100.0
            if last else 0.0
        )
        return {"first_ft_pct": first_pct, "last_ft_pct": last_pct}

    # ── 조회: 팀별 ──

    def get_team_ft_pct(self, team_id: int) -> float:
        """팀 자유투 성공률."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        made = sum(1 for r in recs if r.made)
        return made / len(recs) * 100.0

    def get_team_ft_attempts(self, team_id: int) -> int:
        """팀 자유투 시도 수."""
        with self._lock:
            return sum(1 for r in self._records if r.team_id == team_id)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            made = sum(1 for r in self._records if r.made)
            return {
                "total_attempts": len(self._records),
                "total_made": made,
                "overall_pct": (
                    made / len(self._records) * 100.0
                    if self._records else 0.0
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"FreeThrowAnalyzer(attempts={self.total_attempts})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "FreeThrowAnalyzer",
    "FreeThrowAnalyzerConfig",
    "FreeThrowContext",
]

__version__ = "1.0.0"
