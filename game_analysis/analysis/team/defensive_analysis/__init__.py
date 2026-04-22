# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/analysis/team/defensive_analysis
설명: Phase 3 — 수비 분석 (5개 모듈)
      - defense_type_classifier: 수비 스킴 분류 (맨투맨/존/프레스/특수)
      - defensive_rotation: 수비 로테이션 품질 분석
      - box_out_analyzer: 박스아웃 효과 분석
      - closeout_analyzer: 클로즈아웃 속도/효과 분석
      - help_recovery: 헬프 수비 → 리커버리 품질

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

from game_analysis.analysis.team.defensive_analysis.defense_type_classifier import (
    DefenseTypeClassifier,
    DefenseTypeClassifierConfig,
)
from game_analysis.analysis.team.defensive_analysis.defensive_rotation import (
    DefensiveRotationAnalyzer,
    DefensiveRotationConfig,
)
from game_analysis.analysis.team.defensive_analysis.box_out_analyzer import (
    BoxOutAnalyzer,
    BoxOutAnalyzerConfig,
)
from game_analysis.analysis.team.defensive_analysis.closeout_analyzer import (
    CloseoutAnalyzer,
    CloseoutAnalyzerConfig,
)
from game_analysis.analysis.team.defensive_analysis.help_recovery import (
    HelpRecoveryAnalyzer,
    HelpRecoveryConfig,
)

__all__ = [
    # defense_type_classifier
    "DefenseTypeClassifier",
    "DefenseTypeClassifierConfig",
    # defensive_rotation
    "DefensiveRotationAnalyzer",
    "DefensiveRotationConfig",
    # box_out_analyzer
    "BoxOutAnalyzer",
    "BoxOutAnalyzerConfig",
    # closeout_analyzer
    "CloseoutAnalyzer",
    "CloseoutAnalyzerConfig",
    # help_recovery
    "HelpRecoveryAnalyzer",
    "HelpRecoveryConfig",
]

__version__ = "1.0.0"
