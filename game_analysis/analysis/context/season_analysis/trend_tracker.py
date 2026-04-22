# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/season_analysis
파일: trend_tracker.py
설명: N경기 이동평균 추세 분석기
      - 최근 N경기 이동평균 계산
      - 추세 방향 판정 (상승/하강/유지)
      - 이상치 감지

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (TREND_WINDOW_*, TREND_*_SLOPE, TREND_OUTLIER_SIGMA, MIN_GAMES_FOR_TREND)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.stats_constants import (
    MIN_GAMES_FOR_TREND,
    TREND_DECLINING_SLOPE_MAX,
    TREND_OUTLIER_SIGMA,
    TREND_RISING_SLOPE_MIN,
    TREND_WINDOW_LONG,
    TREND_WINDOW_MEDIUM,
    TREND_WINDOW_SHORT,
)

logger: Final = logging.getLogger(__name__)

_MAX_DATA_POINTS: Final[int] = 300


# =============================================================================
# Enum
# =============================================================================

@unique
class TrendDirection(str, Enum):
    """추세 방향."""

    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class TrendTrackerConfig:
    """추세 분석 설정."""

    max_data_points: int = _MAX_DATA_POINTS
    window_short: int = TREND_WINDOW_SHORT
    window_medium: int = TREND_WINDOW_MEDIUM
    window_long: int = TREND_WINDOW_LONG
    min_games: int = MIN_GAMES_FOR_TREND


# =============================================================================
# Analyzer
# =============================================================================

class TrendTracker:
    """N경기 이동평균 추세 분석기."""

    __slots__ = ("_config", "_lock", "_series")

    def __init__(self, config: TrendTrackerConfig | None = None) -> None:
        self._config = config or TrendTrackerConfig()
        self._lock = RLock()
        # entity_id → stat_key → list[float] (시간순)
        self._series: dict[int, dict[str, list[float]]] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "TrendTracker"

    @property
    def total_data_points(self) -> int:
        with self._lock:
            return sum(
                len(vals)
                for entity in self._series.values()
                for vals in entity.values()
            )

    # ── 기록 ──

    def record_stat(
        self, entity_id: int, stat_key: str, value: float,
    ) -> None:
        """통계 값 1건 추가 (시간순)."""
        with self._lock:
            entity_series = self._series.setdefault(entity_id, {})
            series = entity_series.setdefault(stat_key, [])
            if len(series) >= self._config.max_data_points:
                logger.warning("추세 데이터 한도 도달 (%d) entity=%d stat=%s",
                               self._config.max_data_points, entity_id, stat_key)
                return
            series.append(value)

    # ── 이동평균 ──

    def get_moving_average(
        self, entity_id: int, stat_key: str, window: int | None = None,
    ) -> float:
        """최근 N경기 이동평균. window=None이면 short 윈도우."""
        w = window or self._config.window_short
        with self._lock:
            series = self._series.get(entity_id, {}).get(stat_key, [])
            if len(series) < self._config.min_games:
                return 0.0
            recent = series[-w:]
        return sum(recent) / len(recent) if recent else 0.0

    def get_all_windows(
        self, entity_id: int, stat_key: str,
    ) -> dict[str, float]:
        """3개 윈도우(short/medium/long) 이동평균."""
        return {
            "short": self.get_moving_average(entity_id, stat_key, self._config.window_short),
            "medium": self.get_moving_average(entity_id, stat_key, self._config.window_medium),
            "long": self.get_moving_average(entity_id, stat_key, self._config.window_long),
        }

    # ── 추세 방향 ──

    def get_trend_direction(
        self, entity_id: int, stat_key: str, window: int | None = None,
    ) -> TrendDirection:
        """추세 방향 판정 (선형 기울기 기반)."""
        w = window or self._config.window_medium
        with self._lock:
            series = self._series.get(entity_id, {}).get(stat_key, [])
            if len(series) < self._config.min_games:
                return TrendDirection.STABLE
            recent = list(series[-w:])
        slope = self._calculate_slope(recent)
        if slope >= TREND_RISING_SLOPE_MIN:
            return TrendDirection.RISING
        elif slope <= TREND_DECLINING_SLOPE_MAX:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    # ── 이상치 감지 ──

    def is_outlier(
        self, entity_id: int, stat_key: str, value: float,
    ) -> bool:
        """값이 이상치인지 판별 (Z-score 기반)."""
        with self._lock:
            series = self._series.get(entity_id, {}).get(stat_key, [])
            if len(series) < self._config.min_games:
                return False
            data = list(series)
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = math.sqrt(variance) if variance > 0.0 else 0.0
        if std == 0.0:
            return False
        z_score = abs(value - mean) / std
        return z_score > TREND_OUTLIER_SIGMA

    # ── 내부 ──

    @staticmethod
    def _calculate_slope(values: list[float]) -> float:
        """단순 선형 회귀 기울기."""
        n = len(values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0.0:
            return 0.0
        return numerator / denominator

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "entities_tracked": len(self._series),
                "total_data_points": sum(
                    len(vals)
                    for entity in self._series.values()
                    for vals in entity.values()
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self._series.clear()

    def __repr__(self) -> str:
        return f"TrendTracker(data_points={self.total_data_points})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TrendTracker",
    "TrendTrackerConfig",
    "TrendDirection",
]

__version__ = "1.0.0"
