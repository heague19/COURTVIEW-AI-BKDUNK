# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/coaching_intelligence
파일: substitution_optimizer.py
설명: 교체 타이밍 최적화기
      - 선수 피로도 기반 교체 추천
      - 출전 시간 관리 (과다/과소)
      - 교체 임팩트 추적 (교체 전후 효율 변화)

      Processing Cadence: EVENT (캐시 기반)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.game_management_constants (SUBSTITUTION_MIN_STAY_SEC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_management_constants import SUBSTITUTION_MIN_STAY_SEC

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 300
_FATIGUE_THRESHOLD_MIN: Final[float] = 8.0    # 연속 8분 이상 → 교체 추천
_MAX_PLAYING_TIME_MIN: Final[float] = 38.0     # 총 38분 이상 → 휴식 필요
_MIN_PLAYING_TIME_MIN: Final[float] = 10.0     # 총 10분 미만 → 활용도 낮음


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class SubstitutionOptimizerConfig:
    """교체 최적화 설정."""

    max_records: int = _MAX_RECORDS
    fatigue_threshold_min: float = _FATIGUE_THRESHOLD_MIN
    max_playing_time_min: float = _MAX_PLAYING_TIME_MIN
    min_playing_time_min: float = _MIN_PLAYING_TIME_MIN


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _PlayerStatus:
    """선수 출전 상태."""

    player_id: int
    total_minutes: float = 0.0
    current_stint_min: float = 0.0
    is_on_court: bool = False
    stints: int = 0
    ppm_before_sub: float = 0.0  # 교체 직전 분당 득점
    ppm_after_sub: float = 0.0   # 교체 직후 분당 득점


@dataclass(slots=True)
class _SubEvent:
    """교체 이벤트 기록."""

    player_in: int
    player_out: int
    game_clock_sec: float
    period: int
    score_margin: int


# =============================================================================
# Optimizer
# =============================================================================

class SubstitutionOptimizer:
    """교체 타이밍 최적화기."""

    __slots__ = ("_config", "_lock", "_players", "_sub_events")

    def __init__(self, config: SubstitutionOptimizerConfig | None = None) -> None:
        self._config = config or SubstitutionOptimizerConfig()
        self._lock = RLock()
        self._players: dict[int, _PlayerStatus] = {}
        self._sub_events: list[_SubEvent] = []

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "SubstitutionOptimizer"

    @property
    def total_events(self) -> int:
        with self._lock:
            return len(self._sub_events)

    # ── 선수 등록/갱신 ──

    def register_player(self, player_id: int, *, on_court: bool = False) -> None:
        """선수 등록."""
        with self._lock:
            if player_id not in self._players:
                self._players[player_id] = _PlayerStatus(
                    player_id=player_id,
                    is_on_court=on_court,
                )

    def update_playing_time(
        self, player_id: int, elapsed_min: float,
    ) -> None:
        """선수 출전 시간 갱신."""
        with self._lock:
            p = self._players.get(player_id)
            if p is None:
                return
            p.total_minutes = elapsed_min
            if p.is_on_court:
                p.current_stint_min = elapsed_min

    # ── 교체 기록 ──

    def record_substitution(
        self,
        player_in: int,
        player_out: int,
        game_clock_sec: float,
        period: int,
        score_margin: int = 0,
    ) -> None:
        """교체 이벤트 기록."""
        with self._lock:
            if len(self._sub_events) >= self._config.max_records:
                logger.warning("교체 기록 한도 도달 (%d)", self._config.max_records)
                return

            self._sub_events.append(_SubEvent(
                player_in=player_in,
                player_out=player_out,
                game_clock_sec=game_clock_sec,
                period=period,
                score_margin=score_margin,
            ))

            # 나가는 선수
            p_out = self._players.get(player_out)
            if p_out is not None:
                p_out.is_on_court = False
                p_out.current_stint_min = 0.0
                p_out.stints += 1

            # 들어오는 선수
            p_in = self._players.get(player_in)
            if p_in is not None:
                p_in.is_on_court = True
                p_in.current_stint_min = 0.0

    # ── 교체 추천 ──

    def get_fatigue_alerts(self) -> list[dict[str, object]]:
        """피로도 기반 교체 추천 목록."""
        with self._lock:
            alerts: list[dict[str, object]] = []
            for p in self._players.values():
                if not p.is_on_court:
                    continue
                if p.current_stint_min >= self._config.fatigue_threshold_min:
                    alerts.append({
                        "player_id": p.player_id,
                        "current_stint_min": p.current_stint_min,
                        "total_minutes": p.total_minutes,
                        "reason": "consecutive_minutes",
                    })
                elif p.total_minutes >= self._config.max_playing_time_min:
                    alerts.append({
                        "player_id": p.player_id,
                        "current_stint_min": p.current_stint_min,
                        "total_minutes": p.total_minutes,
                        "reason": "total_minutes_exceeded",
                    })
            return alerts

    def get_underutilized_players(self) -> list[dict[str, object]]:
        """활용도 낮은 선수 (벤치에서 오래 대기)."""
        with self._lock:
            under: list[dict[str, object]] = []
            for p in self._players.values():
                if p.is_on_court:
                    continue
                if p.total_minutes < self._config.min_playing_time_min:
                    under.append({
                        "player_id": p.player_id,
                        "total_minutes": p.total_minutes,
                        "stints": p.stints,
                    })
            return under

    # ── 조회 ──

    def get_player_minutes(self, player_id: int) -> float:
        """선수 총 출전 시간 (분)."""
        with self._lock:
            p = self._players.get(player_id)
            return p.total_minutes if p is not None else 0.0

    def get_substitution_count(self) -> int:
        """총 교체 횟수."""
        with self._lock:
            return len(self._sub_events)

    def get_substitution_by_period(self) -> dict[int, int]:
        """쿼터별 교체 횟수."""
        with self._lock:
            dist: dict[int, int] = {}
            for e in self._sub_events:
                dist[e.period] = dist.get(e.period, 0) + 1
            return dist

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_events": len(self._sub_events),
                "registered_players": len(self._players),
                "on_court": sum(1 for p in self._players.values() if p.is_on_court),
            }

    def reset(self) -> None:
        with self._lock:
            self._players.clear()
            self._sub_events.clear()

    def __repr__(self) -> str:
        return f"SubstitutionOptimizer(events={self.total_events})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SubstitutionOptimizer",
    "SubstitutionOptimizerConfig",
]

__version__ = "1.0.0"
