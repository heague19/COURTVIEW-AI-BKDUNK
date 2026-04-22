# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee
설명: AI 심판 시스템 (Layer 6)
      - rules/: 규칙 엔진 (Phase A) — 리그별 규칙 + 로더
      - violations/: 바이올레이션 12종 감지 (Phase B)
      - fouls/: 파울 11종 감지 (Phase C)
      - decisions/: 판정 결정 엔진 (Phase D)
      - data_extraction/: 자가학습용 데이터 추출 (Phase E)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

# === Phase A: rules/ ===
from ai_referee.rules import (
    BaseRule,
    ClearPathFoulRules,
    CoachChallengeRules,
    CourtDimensions,
    FIBARules,
    FlagrantFoulRules,
    ForeignPlayerRules,
    FoulRule,
    FoulRules,
    FrameContext,
    GameTimeRules,
    ImportPlayerRules,
    KBLRules,
    KBLSubstitutionRules,
    KBLTimeoutRules,
    KBLVideoReviewRules,
    LeagueSpecificRules,
    NBARules,
    NBATimeoutRules,
    NBLOvertimeRules,
    NBLRules,
    NBLVideoReviewRules,
    PenaltyType,
    ReplayCenterRules,
    RuleCategory,
    RuleLoader,
    RuleParameters,
    RuleResult,
    ThreeSecondRules,
    TimeoutRules,
    TransitionTakeFoulRules,
    TravelingRules,
    ViolationRule,
)

# === Phase B: violations/ ===
from ai_referee.violations import (
    BackcourtDetector,
    CarryDetector,
    DefensiveThreeSecDetector,
    DoubleDribbleDetector,
    EightSecondDetector,
    FiveSecondDetector,
    GoaltendingDetector,
    KickBallDetector,
    OutOfBoundsDetector,
    ThreeSecondDetector,
    TravelingDetector,
    TwentyFourSecondDetector,
)

# === Phase C: fouls/ ===
from ai_referee.fouls import (
    BlockingFoulDetector,
    ChargingFoulDetector,
    ContactDetector,
    ContactEvent,
    FlagrantDetector,
    FoulSeverityAnalyzer,
    HandCheckDetector,
    HoldingFoulDetector,
    IllegalScreenDetector,
    ReachInDetector,
    SeverityGrade,
    SeverityResult,
    ShootingFoulClassifier,
    ShootingFoulType,
    TechnicalType,
    TechnicalViolationDetector,
)

# === Phase D: decisions/ ===
from ai_referee.decisions import (
    CalibrationResult,
    ConfidenceScorer,
    ConsistencyReport,
    ConsistencyTracker,
    DecisionEngine,
    DecisionExplainer,
    DecisionExplanation,
    FinalDecision,
    MultiAngleValidator,
    ReplayEvent,
    ReplayManager,
    ReplayPriority,
    ReplayStatus,
    ValidationResult,
    ViewResult,
)

# === Phase E: data_extraction/ ===
from ai_referee.data_extraction import (
    ActualOutcome,
    CalibrationDataExtractor,
    CalibrationDataExtractorConfig,
    CorrectionPairExtractor,
    CorrectionPairExtractorConfig,
    CorrectionSource,
    DecisionRecordExtractor,
    DecisionRecordExtractorConfig,
    EdgeCaseExtractor,
    EdgeCaseExtractorConfig,
    ErrorCategory,
    FoulContactExtractor,
    FoulContactExtractorConfig,
    UncertaintyReason,
    ViolationSequenceExtractor,
    ViolationSequenceExtractorConfig,
)

__all__ = [
    # === Phase A: rules/ ===
    # Enum & 데이터
    "RuleCategory",
    "PenaltyType",
    "FrameContext",
    "RuleResult",
    "RuleParameters",
    # ABC
    "BaseRule",
    "ViolationRule",
    "FoulRule",
    # FIBA
    "GameTimeRules",
    "CourtDimensions",
    "FoulRules",
    "TimeoutRules",
    "ThreeSecondRules",
    "TravelingRules",
    "LeagueSpecificRules",
    "FIBARules",
    # NBA
    "FlagrantFoulRules",
    "CoachChallengeRules",
    "ClearPathFoulRules",
    "TransitionTakeFoulRules",
    "ReplayCenterRules",
    "NBATimeoutRules",
    "NBARules",
    # KBL
    "KBLVideoReviewRules",
    "ForeignPlayerRules",
    "KBLSubstitutionRules",
    "KBLTimeoutRules",
    "KBLRules",
    # NBL
    "NBLVideoReviewRules",
    "ImportPlayerRules",
    "NBLOvertimeRules",
    "NBLRules",
    # 로더
    "RuleLoader",
    # === Phase B: violations/ ===
    "TravelingDetector",
    "DoubleDribbleDetector",
    "CarryDetector",
    "KickBallDetector",
    "ThreeSecondDetector",
    "DefensiveThreeSecDetector",
    "FiveSecondDetector",
    "EightSecondDetector",
    "TwentyFourSecondDetector",
    "BackcourtDetector",
    "OutOfBoundsDetector",
    "GoaltendingDetector",
    # === Phase C: fouls/ ===
    "ContactDetector",
    "ContactEvent",
    "BlockingFoulDetector",
    "ChargingFoulDetector",
    "HandCheckDetector",
    "HoldingFoulDetector",
    "IllegalScreenDetector",
    "ReachInDetector",
    "FoulSeverityAnalyzer",
    "SeverityGrade",
    "SeverityResult",
    "ShootingFoulClassifier",
    "ShootingFoulType",
    "FlagrantDetector",
    "TechnicalViolationDetector",
    "TechnicalType",
    # === Phase D: decisions/ ===
    "ConfidenceScorer",
    "CalibrationResult",
    "MultiAngleValidator",
    "ViewResult",
    "ValidationResult",
    "ConsistencyTracker",
    "ConsistencyReport",
    "DecisionEngine",
    "FinalDecision",
    "DecisionExplainer",
    "DecisionExplanation",
    "ReplayManager",
    "ReplayEvent",
    "ReplayPriority",
    "ReplayStatus",
    # === Phase E: data_extraction/ ===
    "DecisionRecordExtractor",
    "DecisionRecordExtractorConfig",
    "CorrectionPairExtractor",
    "CorrectionPairExtractorConfig",
    "CorrectionSource",
    "ErrorCategory",
    "EdgeCaseExtractor",
    "EdgeCaseExtractorConfig",
    "UncertaintyReason",
    "CalibrationDataExtractor",
    "CalibrationDataExtractorConfig",
    "ActualOutcome",
    "FoulContactExtractor",
    "FoulContactExtractorConfig",
    "ViolationSequenceExtractor",
    "ViolationSequenceExtractorConfig",
]

__version__ = "1.0.0"
