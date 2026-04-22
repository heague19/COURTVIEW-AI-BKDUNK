# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/analysis/context/season_analysis
설명: 시즌 분석 패키지
      - season_aggregator: 시즌 누적 통계
      - trend_tracker: N경기 이동평균 추세
      - benchmark_comparator: 리그 벤치마크 비교

Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.analysis.context.season_analysis.benchmark_comparator import (
    BenchmarkComparator,
    BenchmarkComparatorConfig,
)
from game_analysis.analysis.context.season_analysis.season_aggregator import (
    SeasonAggregator,
    SeasonAggregatorConfig,
)
from game_analysis.analysis.context.season_analysis.trend_tracker import (
    TrendDirection,
    TrendTracker,
    TrendTrackerConfig,
)

__all__ = [
    # season_aggregator
    "SeasonAggregator",
    "SeasonAggregatorConfig",
    # trend_tracker
    "TrendTracker",
    "TrendTrackerConfig",
    "TrendDirection",
    # benchmark_comparator
    "BenchmarkComparator",
    "BenchmarkComparatorConfig",
]

__version__ = "1.0.0"
