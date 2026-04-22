# -*- coding: utf-8 -*-
"""game_analysis/analysis/context/situation_splits 패키지 — 상황별 스플릿 분석."""

from __future__ import annotations

from game_analysis.analysis.context.situation_splits.period_splits import (
    PeriodSplitsAnalyzer,
    PeriodSplitsConfig,
)
from game_analysis.analysis.context.situation_splits.score_margin_splits import (
    ScoreMarginSplitsAnalyzer,
    ScoreMarginSplitsConfig,
    MarginBucket,
)
from game_analysis.analysis.context.situation_splits.shot_clock_splits import (
    ShotClockSplitsAnalyzer,
    ShotClockSplitsConfig,
    ShotClockSegment,
)
from game_analysis.analysis.context.situation_splits.game_context_analyzer import (
    GameContextAnalyzer,
    GameContextConfig,
)

__all__ = [
    "PeriodSplitsAnalyzer",
    "PeriodSplitsConfig",
    "ScoreMarginSplitsAnalyzer",
    "ScoreMarginSplitsConfig",
    "MarginBucket",
    "ShotClockSplitsAnalyzer",
    "ShotClockSplitsConfig",
    "ShotClockSegment",
    "GameContextAnalyzer",
    "GameContextConfig",
]

__version__ = "1.0.0"
