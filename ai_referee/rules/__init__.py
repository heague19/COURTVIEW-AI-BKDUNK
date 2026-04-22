# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
설명: 규칙 엔진 서브모듈
      - Phase A: base_rule (ABC) + 리그별 규칙 + rule_loader
      - BaseRule → ViolationRule / FoulRule → 리그별 detector
      - FIBA(기반) → NBA/KBL/NBL 상속 구조
      - YAML 기반 규칙 파라미터 로딩

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === base_rule: 규칙 ABC + 공통 데이터 ===
from ai_referee.rules.base_rule import (
    BaseRule,
    FoulRule,
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleParameters,
    RuleResult,
    ViolationRule,
)

# === 리그별 규칙 ===
from ai_referee.rules.fiba_rules import (
    CourtDimensions,
    FIBARules,
    FoulRules,
    GameTimeRules,
    LeagueSpecificRules,
    ThreeSecondRules,
    TimeoutRules,
    TravelingRules,
)
from ai_referee.rules.kbl_rules import (
    ForeignPlayerRules,
    KBLRules,
    KBLSubstitutionRules,
    KBLTimeoutRules,
    KBLVideoReviewRules,
)
from ai_referee.rules.nba_rules import (
    ClearPathFoulRules,
    CoachChallengeRules,
    FlagrantFoulRules,
    NBARules,
    NBATimeoutRules,
    ReplayCenterRules,
    TransitionTakeFoulRules,
)
from ai_referee.rules.nbl_rules import (
    ImportPlayerRules,
    NBLOvertimeRules,
    NBLRules,
    NBLVideoReviewRules,
)

# === 규칙 로더 ===
from ai_referee.rules.rule_loader import RuleLoader

__all__ = [
    # === base_rule ===
    "RuleCategory",
    "PenaltyType",
    "FrameContext",
    "RuleResult",
    "RuleParameters",
    "BaseRule",
    "ViolationRule",
    "FoulRule",
    # === FIBA (기반) ===
    "GameTimeRules",
    "CourtDimensions",
    "FoulRules",
    "TimeoutRules",
    "ThreeSecondRules",
    "TravelingRules",
    "LeagueSpecificRules",
    "FIBARules",
    # === NBA ===
    "FlagrantFoulRules",
    "CoachChallengeRules",
    "ClearPathFoulRules",
    "TransitionTakeFoulRules",
    "ReplayCenterRules",
    "NBATimeoutRules",
    "NBARules",
    # === KBL ===
    "KBLVideoReviewRules",
    "ForeignPlayerRules",
    "KBLSubstitutionRules",
    "KBLTimeoutRules",
    "KBLRules",
    # === NBL ===
    "NBLVideoReviewRules",
    "ImportPlayerRules",
    "NBLOvertimeRules",
    "NBLRules",
    # === 로더 ===
    "RuleLoader",
]

__version__ = "1.0.0"
