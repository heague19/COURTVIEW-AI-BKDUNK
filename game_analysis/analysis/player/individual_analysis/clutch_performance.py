# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/individual_analysis
파일: clutch_performance.py
설명: 클러치 상황 성과 분석기
      - 클러치 상황 (4Q/OT + 5분 이내 + 5점차 이내) 자동 판별
      - 클러치 FG%, FT%, 턴오버, +/- 추적
      - 선수별 ClutchStats DTO 산출

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.stats_constants (WP_CLUTCH_*, is_clutch_situation)
         shared.dto.tactical_dto (ClutchStats DTO)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.stats_constants import (
    WP_CLUTCH_MARGIN_POINTS,
    WP_CLUTCH_TIME_REMAINING_SEC,
    is_clutch_situation,
)
from shared.dto.tactical_dto import ClutchStats

logger: Final = logging.getLogger(__name__)

_MAX_CLUTCH_RECORDS: Final[int] = 300


@dataclass(slots=True)
class ClutchPerformanceConfig:
    """클러치 성과 분석 설정."""

    max_records: int = _MAX_CLUTCH_RECORDS
    clutch_margin: int = WP_CLUTCH_MARGIN_POINTS
    clutch_time_sec: int = WP_CLUTCH_TIME_REMAINING_SEC


@dataclass(slots=True)
class _ClutchEvent:
    """클러치 상황 이벤트."""

    player_id: int
    event_type: str  # fg_made/fg_missed/ft_made/ft_missed/turnover
    points: int = 0
    plus_minus: int = 0


class ClutchPerformanceAnalyzer:
    """클러치 상황 성과 분석기."""

    __slots__ = ("_config", "_lock", "_events", "_player_events")

    def __init__(self, config: ClutchPerformanceConfig | None = None) -> None:
        self._config = config or ClutchPerformanceConfig()
        self._lock = RLock()
        self._events: list[_ClutchEvent] = []
        self._player_events: dict[int, list[_ClutchEvent]] = {}

    @property
    def name(self) -> str:
        return "ClutchPerformanceAnalyzer"

    @property
    def total_clutch_events(self) -> int:
        with self._lock:
            return len(self._events)

    def is_clutch(
        self, quarter: int, time_remaining_sec: float, score_margin: int,
    ) -> bool:
        """현재 상황이 클러치인지 판별."""
        return is_clutch_situation(score_margin, int(time_remaining_sec), quarter)

    def record_event(
        self,
        player_id: int,
        event_type: str,
        points: int = 0,
        plus_minus: int = 0,
    ) -> _ClutchEvent:
        """클러치 이벤트 기록 (호출 전 is_clutch 확인 필요)."""
        with self._lock:
            ev = _ClutchEvent(
                player_id=player_id,
                event_type=event_type,
                points=points,
                plus_minus=plus_minus,
            )
            self._events.append(ev)
            self._player_events.setdefault(player_id, []).append(ev)

            if len(self._events) > self._config.max_records:
                overflow = len(self._events) - self._config.max_records
                self._events = self._events[overflow:]

            return ev

    def get_player_clutch_stats(self, player_id: int) -> ClutchStats:
        """선수별 ClutchStats DTO 산출."""
        with self._lock:
            evs = self._player_events.get(player_id, [])
            if not evs:
                return ClutchStats()

            fg_made = sum(1 for e in evs if e.event_type == "fg_made")
            fg_missed = sum(1 for e in evs if e.event_type == "fg_missed")
            ft_made = sum(1 for e in evs if e.event_type == "ft_made")
            ft_missed = sum(1 for e in evs if e.event_type == "ft_missed")
            turnovers = sum(1 for e in evs if e.event_type == "turnover")
            total_pts = sum(e.points for e in evs)
            total_pm = sum(e.plus_minus for e in evs)

            fg_total = fg_made + fg_missed
            ft_total = ft_made + ft_missed

            return ClutchStats(
                points=total_pts,
                fg_pct=(fg_made / fg_total * 100.0) if fg_total > 0 else 0.0,
                ft_pct=(ft_made / ft_total * 100.0) if ft_total > 0 else 0.0,
                turnovers=turnovers,
                plus_minus=total_pm,
            )

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_clutch_events": len(self._events),
                "players_tracked": len(self._player_events),
            }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._player_events.clear()

    def __repr__(self) -> str:
        return f"ClutchPerformanceAnalyzer(events={len(self._events)})"


__all__ = ["ClutchPerformanceAnalyzer", "ClutchPerformanceConfig"]
__version__ = "1.0.0"
