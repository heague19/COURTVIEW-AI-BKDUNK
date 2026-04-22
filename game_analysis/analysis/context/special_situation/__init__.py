# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/analysis/context/special_situation
설명: 특수 상황 분석 패키지
      - ato_play_analyzer: ATO 플레이 분석
      - oob_play_analyzer: 아웃오브바운드 플레이 분석
      - foul_game_analyzer: 파울 게임 전략 분석
      - last_possession: 라스트 포제션 분석

Processing Cadence: POSSESSION (조건부)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.analysis.context.special_situation.ato_play_analyzer import (
    ATOPlayAnalyzer,
    ATOPlayAnalyzerConfig,
)
from game_analysis.analysis.context.special_situation.foul_game_analyzer import (
    FoulGameAnalyzer,
    FoulGameAnalyzerConfig,
)
from game_analysis.analysis.context.special_situation.last_possession import (
    LastPossessionAnalyzer,
    LastPossessionConfig,
    LastPossessionType,
)
from game_analysis.analysis.context.special_situation.oob_play_analyzer import (
    OOBPlayAnalyzer,
    OOBPlayAnalyzerConfig,
    OOBType,
)

__all__ = [
    # ato_play_analyzer
    "ATOPlayAnalyzer",
    "ATOPlayAnalyzerConfig",
    # oob_play_analyzer
    "OOBPlayAnalyzer",
    "OOBPlayAnalyzerConfig",
    "OOBType",
    # foul_game_analyzer
    "FoulGameAnalyzer",
    "FoulGameAnalyzerConfig",
    # last_possession
    "LastPossessionAnalyzer",
    "LastPossessionConfig",
    "LastPossessionType",
]

__version__ = "1.0.0"
