# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/rotation_analysis
파일: rotation_tracker.py
설명: 교체 패턴 추적기
      - 교체 이벤트 기록 (IN/OUT)
      - 선수별 출전 스틴트 관리
      - 스틴트별 출전시간 계산

      Processing Cadence: PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.game_management_constants (SUBSTITUTION_MIN_STAY_SEC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_management_constants import SUBSTITUTION_MIN_STAY_SEC

logger: Final = logging.getLogger(__name__)

_MAX_EVENTS: Final[int] = 2000


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class RotationTrackerConfig:
    """교체 추적 설정."""

    max_events: int = _MAX_EVENTS
    min_stint_sec: float = SUBSTITUTION_MIN_STAY_SEC


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _SubstitutionEvent:
    """교체 이벤트 1건."""

    game_time_sec: float  # 경과 시간 (초)
    period: int
    player_in: int  # 투입 선수 ID
    player_out: int  # 교체 선수 ID
    team_id: int


@dataclass(slots=True)
class _Stint:
    """선수 1회 출전 구간."""

    player_id: int
    team_id: int
    start_sec: float
    end_sec: float = 0.0
    period_start: int = 1
    period_end: int = 1

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


# =============================================================================
# Analyzer
# =============================================================================

class RotationTracker:
    """교체 패턴 추적기."""

    __slots__ = ("_config", "_lock", "_events", "_stints", "_on_court")

    def __init__(self, config: RotationTrackerConfig | None = None) -> None:
        self._config = config or RotationTrackerConfig()
        self._lock = RLock()
        self._events: list[_SubstitutionEvent] = []
        # player_id → list[_Stint]
        self._stints: dict[int, list[_Stint]] = {}
        # 현재 코트 위 선수: player_id → (start_sec, period)
        self._on_court: dict[int, tuple[float, int]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "RotationTracker"

    @property
    def total_events(self) -> int:
        with self._lock:
            return len(self._events)

    # ── 기록 ──

    def set_initial_lineup(
        self, team_id: int, player_ids: list[int], game_time_sec: float = 0.0,
    ) -> None:
        """경기 시작 라인업 등록."""
        with self._lock:
            for pid in player_ids:
                self._on_court[pid] = (game_time_sec, 1)
                stints = self._stints.setdefault(pid, [])
                stints.append(_Stint(
                    player_id=pid, team_id=team_id,
                    start_sec=game_time_sec, period_start=1,
                ))

    def record_substitution(
        self,
        game_time_sec: float,
        period: int,
        player_in: int,
        player_out: int,
        team_id: int,
    ) -> None:
        """교체 이벤트 기록."""
        evt = _SubstitutionEvent(
            game_time_sec=game_time_sec,
            period=period,
            player_in=player_in,
            player_out=player_out,
            team_id=team_id,
        )
        with self._lock:
            if len(self._events) >= self._config.max_events:
                logger.warning("교체 이벤트 한도 도달 (%d)", self._config.max_events)
                return
            self._events.append(evt)
            # OUT 선수 스틴트 종료
            if player_out in self._on_court:
                start_sec, period_start = self._on_court.pop(player_out)
                stints = self._stints.get(player_out, [])
                if stints and stints[-1].end_sec == 0.0:
                    stints[-1].end_sec = game_time_sec
                    stints[-1].period_end = period
            # IN 선수 스틴트 시작
            self._on_court[player_in] = (game_time_sec, period)
            stints_in = self._stints.setdefault(player_in, [])
            stints_in.append(_Stint(
                player_id=player_in, team_id=team_id,
                start_sec=game_time_sec, period_start=period,
            ))

    def finalize_game(self, final_time_sec: float, final_period: int) -> None:
        """경기 종료 시 열린 스틴트 닫기."""
        with self._lock:
            for pid in list(self._on_court.keys()):
                stints = self._stints.get(pid, [])
                if stints and stints[-1].end_sec == 0.0:
                    stints[-1].end_sec = final_time_sec
                    stints[-1].period_end = final_period
            self._on_court.clear()

    # ── 조회 ──

    def get_player_stints(self, player_id: int) -> list[dict[str, float | int]]:
        """선수의 스틴트 목록."""
        with self._lock:
            stints = list(self._stints.get(player_id, []))
        return [
            {
                "start_sec": s.start_sec,
                "end_sec": s.end_sec,
                "duration_sec": s.duration_sec,
                "period_start": s.period_start,
                "period_end": s.period_end,
            }
            for s in stints if s.duration_sec >= self._config.min_stint_sec
        ]

    def get_player_total_minutes(self, player_id: int) -> float:
        """선수 총 출전시간 (분)."""
        with self._lock:
            stints = list(self._stints.get(player_id, []))
        total_sec = sum(s.duration_sec for s in stints)
        return total_sec / 60.0

    def get_substitution_count(self, team_id: int) -> int:
        """팀의 교체 횟수."""
        with self._lock:
            return sum(1 for e in self._events if e.team_id == team_id)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "players_tracked": len(self._stints),
                "on_court_now": len(self._on_court),
            }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._stints.clear()
            self._on_court.clear()

    def __repr__(self) -> str:
        return f"RotationTracker(events={self.total_events})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "RotationTracker",
    "RotationTrackerConfig",
]

__version__ = "1.0.0"
