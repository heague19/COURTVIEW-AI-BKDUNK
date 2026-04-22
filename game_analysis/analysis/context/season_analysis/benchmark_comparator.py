# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/season_analysis
파일: benchmark_comparator.py
설명: 리그 벤치마크 비교 분석기
      - 리그 평균/백분위 등록
      - 선수/팀 성과를 백분위로 환산
      - PerformanceRating 등급 부여

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.constants.stats_constants (PerformanceRating, get_performance_rating)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.stats_constants import (
    PerformanceRating,
    get_performance_rating,
)

logger: Final = logging.getLogger(__name__)

_MAX_BENCHMARKS: Final[int] = 100  # 통계 항목 최대 수


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class BenchmarkComparatorConfig:
    """벤치마크 비교 설정."""

    max_benchmarks: int = _MAX_BENCHMARKS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _BenchmarkEntry:
    """벤치마크 1개 항목."""

    stat_key: str
    league_mean: float
    league_std: float  # 표준편차 (백분위 환산용)
    higher_is_better: bool = True  # True면 높을수록 좋음 (TO 등은 False)


# =============================================================================
# Analyzer
# =============================================================================

class BenchmarkComparator:
    """리그 벤치마크 비교 분석기."""

    __slots__ = ("_config", "_lock", "_benchmarks")

    def __init__(self, config: BenchmarkComparatorConfig | None = None) -> None:
        self._config = config or BenchmarkComparatorConfig()
        self._lock = RLock()
        # stat_key → _BenchmarkEntry
        self._benchmarks: dict[str, _BenchmarkEntry] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "BenchmarkComparator"

    @property
    def total_benchmarks(self) -> int:
        with self._lock:
            return len(self._benchmarks)

    # ── 벤치마크 등록 ──

    def register_benchmark(
        self,
        stat_key: str,
        league_mean: float,
        league_std: float,
        *,
        higher_is_better: bool = True,
    ) -> None:
        """리그 벤치마크 등록."""
        entry = _BenchmarkEntry(
            stat_key=stat_key,
            league_mean=league_mean,
            league_std=league_std,
            higher_is_better=higher_is_better,
        )
        with self._lock:
            if (stat_key not in self._benchmarks
                    and len(self._benchmarks) >= self._config.max_benchmarks):
                logger.warning("벤치마크 한도 도달 (%d)", self._config.max_benchmarks)
                return
            self._benchmarks[stat_key] = entry

    # ── 비교 ──

    def get_percentile(self, stat_key: str, value: float) -> float:
        """값의 백분위 (0~100). 정규분포 근사."""
        with self._lock:
            entry = self._benchmarks.get(stat_key)
        if entry is None or entry.league_std <= 0.0:
            return 50.0  # 기준 없으면 평균
        z = (value - entry.league_mean) / entry.league_std
        if not entry.higher_is_better:
            z = -z  # TO 등은 낮을수록 좋음 → z 반전
        # 정규분포 CDF 근사 (로지스틱 근사)
        percentile = 100.0 / (1.0 + 2.718281828 ** (-1.7 * z))
        return max(0.0, min(100.0, percentile))

    def get_rating(self, stat_key: str, value: float) -> PerformanceRating:
        """값의 성과 등급."""
        pct = self.get_percentile(stat_key, value)
        return get_performance_rating(pct)

    def compare_to_league(
        self, stat_key: str, value: float,
    ) -> dict[str, float | str]:
        """리그 대비 비교 결과."""
        with self._lock:
            entry = self._benchmarks.get(stat_key)
        if entry is None:
            return {
                "value": value,
                "league_mean": 0.0,
                "difference": 0.0,
                "percentile": 50.0,
                "rating": PerformanceRating.AVERAGE.value,
            }
        pct = self.get_percentile(stat_key, value)
        return {
            "value": value,
            "league_mean": entry.league_mean,
            "difference": value - entry.league_mean,
            "percentile": pct,
            "rating": get_performance_rating(pct).value,
        }

    def compare_multiple(
        self, stats: dict[str, float],
    ) -> dict[str, dict[str, float | str]]:
        """여러 통계 항목 일괄 비교."""
        return {key: self.compare_to_league(key, val) for key, val in stats.items()}

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_benchmarks": len(self._benchmarks),
                "stat_keys": list(self._benchmarks.keys()),
            }

    def reset(self) -> None:
        with self._lock:
            self._benchmarks.clear()

    def __repr__(self) -> str:
        return f"BenchmarkComparator(benchmarks={self.total_benchmarks})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "BenchmarkComparator",
    "BenchmarkComparatorConfig",
]

__version__ = "1.0.0"
