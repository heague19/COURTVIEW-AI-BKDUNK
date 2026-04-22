# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/scouting
설명: 상대팀 스카우팅 분석 패키지
      - opponent_profiler: 상대팀 프로필 (효율/전술/핵심선수)
      - tendency_analyzer: 성향 분석 (슛존/플레이유형/전환/방향)
      - weakness_finder: 약점 발견 (수비갭/전환/리바운드/매치업)
      - head_to_head_analyzer: 상대 전적 분석
      - scouting_report_builder: 종합 스카우팅 리포트
      - play_pattern_matcher: 세트플레이 패턴 인식
      - referee_tendency_analyzer: 심판 성향 분석

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.scouting.head_to_head_analyzer import (
    H2HGameInput,
    H2HStrategyInput,
    HeadToHeadAnalyzer,
    HeadToHeadConfig,
)
from game_analysis.output.scouting.opponent_profiler import (
    GameDataInput,
    OpponentProfiler,
    OpponentProfilerConfig,
    PlayerSeasonInput,
)
from game_analysis.output.scouting.scouting_report_builder import (
    ScoutingReport,
    ScoutingReportBuilder,
    ScoutingReportConfig,
)
from game_analysis.output.scouting.tendency_analyzer import (
    PossessionRecordInput,
    ShotRecordInput,
    TendencyAnalyzer,
    TendencyAnalyzerConfig,
)
from game_analysis.output.scouting.play_pattern_matcher import (
    PlayPatternMatcher,
    PlayPatternMatcherConfig,
)
from game_analysis.output.scouting.referee_tendency_analyzer import (
    RefereeTendencyAnalyzer,
    RefereeTendencyConfig,
)
from game_analysis.output.scouting.weakness_finder import (
    MatchupDefenseInput,
    ReboundInput,
    ThreePointDefenseInput,
    TransitionDefenseInput,
    WeaknessFinder,
    WeaknessFinderConfig,
    ZoneDefenseInput,
)

__all__ = [
    # opponent_profiler
    "OpponentProfilerConfig",
    "OpponentProfiler",
    "GameDataInput",
    "PlayerSeasonInput",
    # tendency_analyzer
    "TendencyAnalyzerConfig",
    "TendencyAnalyzer",
    "ShotRecordInput",
    "PossessionRecordInput",
    # weakness_finder
    "WeaknessFinderConfig",
    "WeaknessFinder",
    "ZoneDefenseInput",
    "TransitionDefenseInput",
    "ReboundInput",
    "MatchupDefenseInput",
    "ThreePointDefenseInput",
    # head_to_head_analyzer
    "HeadToHeadConfig",
    "HeadToHeadAnalyzer",
    "H2HGameInput",
    "H2HStrategyInput",
    # scouting_report_builder
    "ScoutingReportConfig",
    "ScoutingReportBuilder",
    "ScoutingReport",
    # play_pattern_matcher
    "PlayPatternMatcher",
    "PlayPatternMatcherConfig",
    # referee_tendency_analyzer
    "RefereeTendencyAnalyzer",
    "RefereeTendencyConfig",
]

__version__ = "1.0.0"
