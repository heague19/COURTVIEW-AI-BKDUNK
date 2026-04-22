# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system
파일: __init__.py
설명: 피드백 시스템 (Layer 7) 루트 모듈 export.
      - templates/: 심각도 매핑, 포맷팅, 한글 템플릿, 변형 엔진
      - coach/: 코치 역할 피드백 (동작 폼 + 생체역학)
      - analysis/: 전력분석원 역할 피드백 (8기존 + 7확장 + 3고급 + 6잔여 = 24 생성기)
      - report/: 코치/경기 리포트, 세션 요약, 진행 추적, 추세 분석

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

# === templates ===
from feedback_system.templates import (
    FeedbackFormatter,
    FormatterConfig,
    FormattedResult,
    KoreanTemplates,
    TemplateEntry,
    TemplateVariationEngine,
    SeverityMapper,
    SeverityMapperConfig,
    SeverityResult,
    ThresholdSet,
)

# === coach (코치 역할 — 동작 폼 + 생체역학 피드백) ===
from feedback_system.coach import (
    MotionFeedbackGenerator,
    MotionFeedbackConfig,
    BiomechanicsFeedbackGenerator,
    BiomechanicsFeedbackConfig,
)

# === analysis (전력분석원 역할 — 경기/전술/전략 피드백) ===
from feedback_system.analysis import (
    # 기존 8개 생성기
    GameFeedbackGenerator,
    GameFeedbackConfig,
    TacticalFeedbackGenerator,
    TacticalFeedbackConfig,
    DefensiveFeedbackGenerator,
    DefensiveFeedbackConfig,
    IndividualFeedbackGenerator,
    IndividualFeedbackConfig,
    SpatialFeedbackGenerator,
    SpatialFeedbackConfig,
    LineupFeedbackGenerator,
    LineupFeedbackConfig,
    RefereeFeedbackGenerator,
    RefereeFeedbackConfig,
    VisualFeedbackGenerator,
    VisualFeedbackConfig,
    VisualElement,
    # 신규 7개 생성기
    QuarterMomentumFeedbackGenerator,
    QuarterMomentumFeedbackConfig,
    ClutchFeedbackGenerator,
    ClutchFeedbackConfig,
    PaceTempoFeedbackGenerator,
    PaceTempoFeedbackConfig,
    ShotQualityFeedbackGenerator,
    ShotQualityFeedbackConfig,
    OpponentTendencyFeedbackGenerator,
    OpponentTendencyFeedbackConfig,
    RotationFeedbackGenerator,
    RotationFeedbackConfig,
    StrategicRecommendationFeedbackGenerator,
    StrategicRecommendationFeedbackConfig,
    # 고급 분석 생성기
    CausalFeedbackGenerator,
    CausalFeedbackConfig,
    GameContextFeedbackGenerator,
    GameContextFeedbackConfig,
    ScoutingFeedbackGenerator,
    ScoutingFeedbackConfig,
    # 잔여 과제 생성기
    FreeThrowFeedbackGenerator,
    FreeThrowFeedbackConfig,
    FoulTroubleFeedbackGenerator,
    FoulTroubleFeedbackConfig,
    DrillPrescriptionFeedbackGenerator,
    DrillPrescriptionFeedbackConfig,
    DrillSpec,
    PlayByPlayFeedbackGenerator,
    PlayByPlayFeedbackConfig,
    PositionFeedbackGenerator,
    PositionFeedbackConfig,
    FinishRepertoireFeedbackGenerator,
    FinishRepertoireFeedbackConfig,
)

# === report ===
from feedback_system.report import (
    CoachReportGenerator,
    CoachReportConfig,
    GameReportGenerator,
    GameReportConfig,
    SessionSummary,
    SessionSummaryConfig,
    ProgressTracker,
    ProgressTrackerConfig,
    TrendAnalyzer,
    TrendAnalyzerConfig,
)


__all__ = [
    # === templates/ ===
    "FeedbackFormatter",
    "FormatterConfig",
    "FormattedResult",
    "KoreanTemplates",
    "TemplateEntry",
    "TemplateVariationEngine",
    "SeverityMapper",
    "SeverityMapperConfig",
    "SeverityResult",
    "ThresholdSet",
    # === coach/ (코치 역할) ===
    "MotionFeedbackGenerator",
    "MotionFeedbackConfig",
    "BiomechanicsFeedbackGenerator",
    "BiomechanicsFeedbackConfig",
    # === analysis/ (전력분석원 역할 — 기존 8개) ===
    "GameFeedbackGenerator",
    "GameFeedbackConfig",
    "TacticalFeedbackGenerator",
    "TacticalFeedbackConfig",
    "DefensiveFeedbackGenerator",
    "DefensiveFeedbackConfig",
    "IndividualFeedbackGenerator",
    "IndividualFeedbackConfig",
    "SpatialFeedbackGenerator",
    "SpatialFeedbackConfig",
    "LineupFeedbackGenerator",
    "LineupFeedbackConfig",
    "RefereeFeedbackGenerator",
    "RefereeFeedbackConfig",
    "VisualFeedbackGenerator",
    "VisualFeedbackConfig",
    "VisualElement",
    # === analysis/ (전력분석원 역할 — 신규 7개) ===
    "QuarterMomentumFeedbackGenerator",
    "QuarterMomentumFeedbackConfig",
    "ClutchFeedbackGenerator",
    "ClutchFeedbackConfig",
    "PaceTempoFeedbackGenerator",
    "PaceTempoFeedbackConfig",
    "ShotQualityFeedbackGenerator",
    "ShotQualityFeedbackConfig",
    "OpponentTendencyFeedbackGenerator",
    "OpponentTendencyFeedbackConfig",
    "RotationFeedbackGenerator",
    "RotationFeedbackConfig",
    "StrategicRecommendationFeedbackGenerator",
    "StrategicRecommendationFeedbackConfig",
    # === analysis/ (고급 분석 3개) ===
    "CausalFeedbackGenerator",
    "CausalFeedbackConfig",
    "GameContextFeedbackGenerator",
    "GameContextFeedbackConfig",
    "ScoutingFeedbackGenerator",
    "ScoutingFeedbackConfig",
    # === analysis/ (잔여 과제 6개) ===
    "FreeThrowFeedbackGenerator",
    "FreeThrowFeedbackConfig",
    "FoulTroubleFeedbackGenerator",
    "FoulTroubleFeedbackConfig",
    "DrillPrescriptionFeedbackGenerator",
    "DrillPrescriptionFeedbackConfig",
    "DrillSpec",
    "PlayByPlayFeedbackGenerator",
    "PlayByPlayFeedbackConfig",
    "PositionFeedbackGenerator",
    "PositionFeedbackConfig",
    "FinishRepertoireFeedbackGenerator",
    "FinishRepertoireFeedbackConfig",
    # === report/ ===
    "CoachReportGenerator",
    "CoachReportConfig",
    "GameReportGenerator",
    "GameReportConfig",
    "SessionSummary",
    "SessionSummaryConfig",
    "ProgressTracker",
    "ProgressTrackerConfig",
    "TrendAnalyzer",
    "TrendAnalyzerConfig",
]

__version__ = "1.0.0"
