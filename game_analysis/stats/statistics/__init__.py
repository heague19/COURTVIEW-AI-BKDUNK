# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/stats/statistics
파일: __init__.py
설명: 통계 서브모듈 — Phase 2A 통계 산출 7개 모듈 통합 export
      Phase 1A(game_management) + Phase 1B(event_detection) 이벤트 데이터를
      소비하여 박스스코어, 고급 스탯, 슛 차트, 트래킹, 팀 통계, 점유 효율,
      Four Factors를 증분 산출합니다.

      Processing Cadence: EVENT (<10ms) — 이벤트당 O(1) 증분
      전체 재계산: 쿼터/경기 종료 시에만

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === 기본 스탯 집계기 ===
from game_analysis.stats.statistics.basic_stats import (
    BasicStatsConfig,
    BasicStatsCalculator,
)

# === 고급 스탯 산출기 ===
from game_analysis.stats.statistics.advanced_stats import (
    AdvancedStatsConfig,
    AdvancedStatsCalculator,
    AdvancedPlayerStats,
    TeamContext,
)

# === 슛 차트 분석기 ===
from game_analysis.stats.statistics.shot_chart import (
    ShotChartConfig,
    ShotChartCalculator,
    ZoneAccumulator,
)

# === 트래킹 스탯 집계기 ===
from game_analysis.stats.statistics.player_tracker_stats import (
    PlayerTrackerConfig,
    PlayerTrackerStatsCalculator,
    PlayerPositionInput,
)

# === 팀 통계 집계기 ===
from game_analysis.stats.statistics.team_stats_aggregator import (
    TeamStatsConfig,
    TeamStatsAggregator,
)

# === 점유 통계 분석기 ===
from game_analysis.stats.statistics.possession_stats import (
    PossessionStatsConfig,
    PossessionStatsCalculator,
    PossessionResult,
    PPPGrade,
    PossessionTiming,
)

# === Four Factors 분석기 ===
from game_analysis.stats.statistics.four_factors import (
    FourFactorsConfig,
    FourFactorsCalculator,
    FourFactorsInput,
    FourFactorsResult,
)


__all__ = [
    # 기본 스탯
    "BasicStatsConfig",
    "BasicStatsCalculator",
    # 고급 스탯
    "AdvancedStatsConfig",
    "AdvancedStatsCalculator",
    "AdvancedPlayerStats",
    "TeamContext",
    # 슛 차트
    "ShotChartConfig",
    "ShotChartCalculator",
    "ZoneAccumulator",
    # 트래킹 스탯
    "PlayerTrackerConfig",
    "PlayerTrackerStatsCalculator",
    "PlayerPositionInput",
    # 팀 통계
    "TeamStatsConfig",
    "TeamStatsAggregator",
    # 점유 통계
    "PossessionStatsConfig",
    "PossessionStatsCalculator",
    "PossessionResult",
    "PPPGrade",
    "PossessionTiming",
    # Four Factors
    "FourFactorsConfig",
    "FourFactorsCalculator",
    "FourFactorsInput",
    "FourFactorsResult",
]

__version__ = "1.0.0"
