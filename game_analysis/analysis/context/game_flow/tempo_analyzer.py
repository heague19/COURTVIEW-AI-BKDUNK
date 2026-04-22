# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_flow
파일: tempo_analyzer.py
설명: 템포 분석기
      - 점유당 평균 소요 시간
      - 빠른/느린 템포 분류
      - 팀별 페이스 비교

      Processing Cadence: 🟡 PERIOD

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성: shared.constants.tactical_constants (TEMPO_FAST_THRESHOLD_SEC, TEMPO_SLOW_THRESHOLD_SEC)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    TEMPO_FAST_THRESHOLD_SEC,
    TEMPO_SLOW_THRESHOLD_SEC,
)

logger: Final = logging.getLogger(__name__)

_MAX_POSSESSION_TIMES: Final[int] = 500


@dataclass(slots=True)
class TempoAnalyzerConfig:
    """템포 분석 설정."""

    max_records: int = _MAX_POSSESSION_TIMES
    fast_threshold_sec: float = TEMPO_FAST_THRESHOLD_SEC
    slow_threshold_sec: float = TEMPO_SLOW_THRESHOLD_SEC


class TempoAnalyzer:
    """템포 분석기."""

    __slots__ = ("_config", "_lock", "_team_times")

    def __init__(self, config: TempoAnalyzerConfig | None = None) -> None:
        self._config = config or TempoAnalyzerConfig()
        self._lock = RLock()
        # {team_id: list[possession_duration_sec]}
        self._team_times: dict[int, list[float]] = {}

    @property
    def name(self) -> str:
        return "TempoAnalyzer"

    @property
    def total_possessions(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._team_times.values())

    def record_possession_time(self, team_id: int, duration_sec: float) -> None:
        """점유 시간 기록."""
        with self._lock:
            times = self._team_times.setdefault(team_id, [])
            times.append(duration_sec)
            if len(times) > self._config.max_records:
                overflow = len(times) - self._config.max_records
                self._team_times[team_id] = times[overflow:]

    def get_avg_possession_time(self, team_id: int) -> float:
        """팀별 평균 점유 시간 (초)."""
        with self._lock:
            times = self._team_times.get(team_id, [])
            if not times:
                return 0.0
            return sum(times) / len(times)

    def get_tempo_category(self, team_id: int) -> str:
        """
        팀 템포 분류.

        Returns:
            "fast" / "normal" / "slow"
        """
        avg = self.get_avg_possession_time(team_id)
        if avg <= 0:
            return "normal"
        if avg <= self._config.fast_threshold_sec:
            return "fast"
        if avg >= self._config.slow_threshold_sec:
            return "slow"
        return "normal"

    def get_pace(self, team_id: int, game_minutes: float) -> float:
        """
        페이스 (점유 수 per 48분).

        Args:
            team_id: 팀 ID
            game_minutes: 경기 경과 시간 (분)
        """
        with self._lock:
            times = self._team_times.get(team_id, [])
            if not times or game_minutes <= 0:
                return 0.0
            return len(times) / game_minutes * 48.0

    def compare_tempo(self, team_a: int, team_b: int) -> dict[str, float]:
        """두 팀 템포 비교."""
        avg_a = self.get_avg_possession_time(team_a)
        avg_b = self.get_avg_possession_time(team_b)
        return {
            "team_a_avg_sec": avg_a,
            "team_b_avg_sec": avg_b,
            "difference_sec": avg_a - avg_b,
        }

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "teams_tracked": len(self._team_times),
                "total_possessions": sum(len(v) for v in self._team_times.values()),
            }

    def reset(self) -> None:
        with self._lock:
            self._team_times.clear()

    def __repr__(self) -> str:
        return f"TempoAnalyzer(teams={len(self._team_times)})"


__all__ = ["TempoAnalyzer", "TempoAnalyzerConfig"]
__version__ = "1.0.0"
