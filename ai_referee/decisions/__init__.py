# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
설명: 판정 의사결정 엔진 (Phase D)
      - confidence_scorer: 신뢰도 보정
      - multi_angle_validator: 멀티앵글 교차 검증
      - consistency_tracker: 판정 일관성 추적
      - decision_engine: 판정 엔진 (통합 오케스트레이터)
      - replay_manager: 리플레이 관리
      - decision_explainer: 판정 근거 설명

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from ai_referee.decisions.confidence_scorer import (
    CalibrationResult,
    ConfidenceScorer,
)
from ai_referee.decisions.consistency_tracker import (
    ConsistencyReport,
    ConsistencyTracker,
)
from ai_referee.decisions.decision_engine import (
    DecisionEngine,
    FinalDecision,
)
from ai_referee.decisions.decision_explainer import (
    DecisionExplanation,
    DecisionExplainer,
)
from ai_referee.decisions.multi_angle_validator import (
    MultiAngleValidator,
    ValidationResult,
    ViewResult,
)
from ai_referee.decisions.replay_manager import (
    ReplayEvent,
    ReplayManager,
    ReplayPriority,
    ReplayStatus,
)

__all__ = [
    # confidence_scorer
    "ConfidenceScorer",
    "CalibrationResult",
    # multi_angle_validator
    "MultiAngleValidator",
    "ViewResult",
    "ValidationResult",
    # consistency_tracker
    "ConsistencyTracker",
    "ConsistencyReport",
    # decision_engine
    "DecisionEngine",
    "FinalDecision",
    # decision_explainer
    "DecisionExplainer",
    "DecisionExplanation",
    # replay_manager
    "ReplayManager",
    "ReplayEvent",
    "ReplayPriority",
    "ReplayStatus",
]

__version__ = "1.0.0"
