# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/analysis/team/tactical_analysis
파일: __init__.py
설명: 전술 분석 서브모듈 — Phase 2 전술 분석 6개 모듈 통합 export
      Phase 1 (game_management + event_detection + statistics) 데이터를
      소비하여 PnR, 속공, 세트 플레이, 패싱 네트워크, 점유, 턴오버
      전술 분석을 수행합니다.

      Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === PnR / 볼스크린 분석기 ===
from game_analysis.analysis.team.tactical_analysis.screen_analyzer import (
    ScreenAnalyzerConfig,
    ScreenAnalyzer,
    PnREventInput,
    PnRCoverageType,
    PnRActionType,
)

# === 속공 / 전환 공격 분석기 ===
from game_analysis.analysis.team.tactical_analysis.fast_break_analyzer import (
    FastBreakAnalyzerConfig,
    FastBreakAnalyzer,
    FastBreakEventInput,
    FastBreakOutcome,
)

# === 세트 플레이 인식기 ===
from game_analysis.analysis.team.tactical_analysis.set_play_recognizer import (
    SetPlayRecognizerConfig,
    SetPlayRecognizer,
    SetPlayEventInput,
)

# === 패싱 네트워크 분석기 ===
from game_analysis.analysis.team.tactical_analysis.passing_network import (
    PassingNetworkConfig,
    PassingNetworkAnalyzer,
    PassEventInput,
)

# === 점유 전술 분석기 ===
from game_analysis.analysis.team.tactical_analysis.possession_analyzer import (
    PossessionAnalyzerConfig,
    PossessionAnalyzer,
    PossessionInput,
    PossessionType,
    PossessionOutcome,
    ClockSegment,
)

# === 턴오버 심층 분석기 ===
from game_analysis.analysis.team.tactical_analysis.turnover_analyzer import (
    TurnoverAnalyzerConfig,
    TurnoverAnalyzer,
    TurnoverEventInput,
    TurnoverCause,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # screen_analyzer
    "ScreenAnalyzerConfig",
    "ScreenAnalyzer",
    "PnREventInput",
    "PnRCoverageType",
    "PnRActionType",
    # fast_break_analyzer
    "FastBreakAnalyzerConfig",
    "FastBreakAnalyzer",
    "FastBreakEventInput",
    "FastBreakOutcome",
    # set_play_recognizer
    "SetPlayRecognizerConfig",
    "SetPlayRecognizer",
    "SetPlayEventInput",
    # passing_network
    "PassingNetworkConfig",
    "PassingNetworkAnalyzer",
    "PassEventInput",
    # possession_analyzer
    "PossessionAnalyzerConfig",
    "PossessionAnalyzer",
    "PossessionInput",
    "PossessionType",
    "PossessionOutcome",
    "ClockSegment",
    # turnover_analyzer
    "TurnoverAnalyzerConfig",
    "TurnoverAnalyzer",
    "TurnoverEventInput",
    "TurnoverCause",
]

__version__ = "1.0.0"
