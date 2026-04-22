# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/matchup_analysis
설명: 매치업 분석 패키지
      - matchup_tracker: 1v1 매치업 추적 (수비자-공격자 대결)
      - contest_analyzer: 슛 컨테스트 분석 (거리별 효과)
      - matchup_evaluator: 매치업 평가 (등급/어드밴티지/최적 추천)

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.matchup_analysis.contest_analyzer import (
    ContestAnalyzer,
    ContestAnalyzerConfig,
    ContestEventInput,
    ContestResult,
    ContestSummary,
)
from game_analysis.output.matchup_analysis.matchup_evaluator import (
    MatchupEvaluation,
    MatchupEvaluator,
    MatchupEvaluatorConfig,
    MatchupRecommendation,
    PositionMatchupSummary,
)
from game_analysis.output.matchup_analysis.matchup_tracker import (
    MatchupEventInput,
    MatchupTracker,
    MatchupTrackerConfig,
)

__all__ = [
    # matchup_tracker
    "MatchupTrackerConfig",
    "MatchupTracker",
    "MatchupEventInput",
    # contest_analyzer
    "ContestAnalyzerConfig",
    "ContestAnalyzer",
    "ContestEventInput",
    "ContestResult",
    "ContestSummary",
    # matchup_evaluator
    "MatchupEvaluatorConfig",
    "MatchupEvaluator",
    "MatchupEvaluation",
    "PositionMatchupSummary",
    "MatchupRecommendation",
]

__version__ = "1.0.0"
