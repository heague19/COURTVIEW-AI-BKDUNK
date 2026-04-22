# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: __init__.py
설명: 전력분석원 역할 피드백 서브모듈 export.
      - 기존 8개 생성기 (경기/전술/수비/개인/공간/라인업/심판/시각)
      - 확장 7개 생성기 (쿼터모멘텀/클러치/페이스/슛퀄리티/상대경향/로테이션/전략권고)
      - 고급 3개 생성기 (원인추론/맥락/스카우팅)
      - 잔여 6개 생성기 (자유투/파울/드릴처방/플레이바이플레이/포지션/피니시)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

# === 기존 생성기 (generators/에서 이동) ===
from feedback_system.analysis.game_feedback import (
    GameFeedbackConfig,
    GameFeedbackGenerator,
)
from feedback_system.analysis.tactical_feedback import (
    TacticalFeedbackConfig,
    TacticalFeedbackGenerator,
)
from feedback_system.analysis.defensive_feedback import (
    DefensiveFeedbackConfig,
    DefensiveFeedbackGenerator,
)
from feedback_system.analysis.individual_feedback import (
    IndividualFeedbackConfig,
    IndividualFeedbackGenerator,
)
from feedback_system.analysis.spatial_feedback import (
    SpatialFeedbackConfig,
    SpatialFeedbackGenerator,
)
from feedback_system.analysis.lineup_feedback import (
    LineupFeedbackConfig,
    LineupFeedbackGenerator,
)
from feedback_system.analysis.referee_feedback import (
    RefereeFeedbackConfig,
    RefereeFeedbackGenerator,
)
from feedback_system.analysis.visual_feedback_generator import (
    VisualElement,
    VisualFeedbackConfig,
    VisualFeedbackGenerator,
)

# === 신규 생성기 ===
from feedback_system.analysis.quarter_momentum_feedback import (
    QuarterMomentumFeedbackConfig,
    QuarterMomentumFeedbackGenerator,
)
from feedback_system.analysis.clutch_feedback import (
    ClutchFeedbackConfig,
    ClutchFeedbackGenerator,
)
from feedback_system.analysis.pace_tempo_feedback import (
    PaceTempoFeedbackConfig,
    PaceTempoFeedbackGenerator,
)
from feedback_system.analysis.shot_quality_feedback import (
    ShotQualityFeedbackConfig,
    ShotQualityFeedbackGenerator,
)
from feedback_system.analysis.opponent_tendency_feedback import (
    OpponentTendencyFeedbackConfig,
    OpponentTendencyFeedbackGenerator,
)
from feedback_system.analysis.rotation_feedback import (
    RotationFeedbackConfig,
    RotationFeedbackGenerator,
)
from feedback_system.analysis.strategic_recommendation_feedback import (
    StrategicRecommendationFeedbackConfig,
    StrategicRecommendationFeedbackGenerator,
)

# === 고급 분석 생성기 (원인추론/맥락/스카우팅) ===
from feedback_system.analysis.causal_feedback import (
    CausalFeedbackConfig,
    CausalFeedbackGenerator,
)
from feedback_system.analysis.game_context_feedback import (
    GameContextFeedbackConfig,
    GameContextFeedbackGenerator,
)
from feedback_system.analysis.scouting_feedback import (
    ScoutingFeedbackConfig,
    ScoutingFeedbackGenerator,
)

# === 잔여 과제 생성기 (김팀장 Phase 1-2) ===
from feedback_system.analysis.free_throw_feedback import (
    FreeThrowFeedbackConfig,
    FreeThrowFeedbackGenerator,
)
from feedback_system.analysis.foul_trouble_feedback import (
    FoulTroubleFeedbackConfig,
    FoulTroubleFeedbackGenerator,
)
from feedback_system.analysis.drill_prescription_feedback import (
    DrillPrescriptionFeedbackConfig,
    DrillPrescriptionFeedbackGenerator,
    DrillSpec,
)
from feedback_system.analysis.play_by_play_feedback import (
    PlayByPlayFeedbackConfig,
    PlayByPlayFeedbackGenerator,
)
from feedback_system.analysis.position_feedback import (
    PositionFeedbackConfig,
    PositionFeedbackGenerator,
)
from feedback_system.analysis.finish_repertoire_feedback import (
    FinishRepertoireFeedbackConfig,
    FinishRepertoireFeedbackGenerator,
)


__all__ = [
    # === 기존 생성기 ===
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
    # === 신규 생성기 ===
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
    # === 고급 분석 생성기 ===
    "CausalFeedbackGenerator",
    "CausalFeedbackConfig",
    "GameContextFeedbackGenerator",
    "GameContextFeedbackConfig",
    "ScoutingFeedbackGenerator",
    "ScoutingFeedbackConfig",
    # === 잔여 과제 생성기 ===
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
]

__version__ = "1.0.0"
