# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/special_situation
파일: ato_play_analyzer.py
설명: ATO(After Timeout) 플레이 분석기
      - 타임아웃 직후 점유 성과 추적
      - ATO 성공률/PPP 계산
      - 타임아웃 유형별 분류

      Processing Cadence: POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 500
_ATO_WINDOW_SEC: Final[float] = 30.0  # 타임아웃 후 30초 이내 = ATO


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ATOPlayAnalyzerConfig:
    """ATO 분석 설정."""

    max_records: int = _MAX_RECORDS
    ato_window_sec: float = _ATO_WINDOW_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ATORecord:
    """ATO 점유 1건."""

    team_id: int
    time_since_timeout_sec: float
    points_scored: int = 0
    shot_attempted: bool = False
    shot_made: bool = False
    turnover: bool = False
    is_designed_play: bool = False  # 세트 플레이 여부


# =============================================================================
# Analyzer
# =============================================================================

class ATOPlayAnalyzer:
    """ATO 플레이 분석기."""

    __slots__ = ("_config", "_lock", "_records")

    def __init__(self, config: ATOPlayAnalyzerConfig | None = None) -> None:
        self._config = config or ATOPlayAnalyzerConfig()
        self._lock = RLock()
        self._records: list[_ATORecord] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ATOPlayAnalyzer"

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    # ── 기록 ──

    def record_ato_possession(
        self,
        team_id: int,
        time_since_timeout_sec: float,
        *,
        points_scored: int = 0,
        shot_attempted: bool = False,
        shot_made: bool = False,
        turnover: bool = False,
        is_designed_play: bool = False,
    ) -> None:
        """ATO 점유 1건 기록."""
        rec = _ATORecord(
            team_id=team_id,
            time_since_timeout_sec=time_since_timeout_sec,
            points_scored=points_scored,
            shot_attempted=shot_attempted,
            shot_made=shot_made,
            turnover=turnover,
            is_designed_play=is_designed_play,
        )
        with self._lock:
            if len(self._records) >= self._config.max_records:
                logger.warning("ATO 기록 한도 도달 (%d)", self._config.max_records)
                return
            self._records.append(rec)

    # ── 조회 ──

    def get_ato_ppp(self, team_id: int) -> float:
        """ATO PPP."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        return sum(r.points_scored for r in recs) / len(recs)

    def get_ato_fg_pct(self, team_id: int) -> float:
        """ATO FG%."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        attempts = sum(1 for r in recs if r.shot_attempted)
        if attempts == 0:
            return 0.0
        made = sum(1 for r in recs if r.shot_made)
        return made / attempts * 100.0

    def get_ato_turnover_rate(self, team_id: int) -> float:
        """ATO 턴오버율 (%)."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        turnovers = sum(1 for r in recs if r.turnover)
        return turnovers / len(recs) * 100.0

    def get_designed_play_rate(self, team_id: int) -> float:
        """세트 플레이 비율 (%)."""
        with self._lock:
            recs = [r for r in self._records if r.team_id == team_id]
        if not recs:
            return 0.0
        designed = sum(1 for r in recs if r.is_designed_play)
        return designed / len(recs) * 100.0

    def get_ato_summary(self, team_id: int) -> dict[str, float]:
        """ATO 종합 요약."""
        return {
            "ppp": self.get_ato_ppp(team_id),
            "fg_pct": self.get_ato_fg_pct(team_id),
            "turnover_rate": self.get_ato_turnover_rate(team_id),
            "designed_play_rate": self.get_designed_play_rate(team_id),
        }

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            teams = len({r.team_id for r in self._records})
            return {"total_records": len(self._records), "teams_tracked": teams}

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def __repr__(self) -> str:
        return f"ATOPlayAnalyzer(records={self.total_records})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ATOPlayAnalyzer",
    "ATOPlayAnalyzerConfig",
]

__version__ = "1.0.0"
