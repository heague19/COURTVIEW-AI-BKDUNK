# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis
파일: __init__.py
설명: Layer 4 동작 분석 모듈 루트 패키지 (Phase 15 H1-H3 이후 축소).
      - Tier 1 (detection/): 동작 감지 (WHEN)
      - Tier 2 (classification/): 동작 분류 (WHAT)
      - models.py: 내부 데이터 모델 (MotionSnapshot, PhaseResult 등)

      이전된 서브패키지 (Phase 15 H1-H3):
      - phase_analysis/   → biomechanics/phase_analysis/
      - form_evaluation/  → feedback_system/form_evaluation/
      - comparison/       → feedback_system/comparison/

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0

의존성:
    - shared/ (Layer 0): constants, dto, exceptions
    - core_foundation/ (Layer 0): config, monitoring
    - utils/ (Layer 0): math_utils, physics_utils
    - detection/ (Layer 1): ball/court/player detection 결과
    - pose_estimation/ (Layer 2): keypoint 결과
    - biomechanics/ (Layer 3): kinematics, dynamics, anthropometry 결과

소비자:
    - game_analysis/ (Layer 5): 경기 분석에 동작 품질 반영
    - ai_referee/ (Layer 6): AI 심판 규칙 적용
    - feedback_system/ (Layer 7): 피드백 생성
"""

from __future__ import annotations

# =============================================================================
# 내부 데이터 모델 (models.py)
# =============================================================================

from motion_analysis.models import (
    ComparisonResult,
    DetectionCandidate,
    FeedbackItem,
    FeedbackSeverity,
    FormEvaluation,
    FormGrade,
    FormScore,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
    DribblePhase,
    score_to_grade,
)

# =============================================================================
# Tier 1: 동작 감지 (detection/)
# =============================================================================

from motion_analysis.detection import (
    ShotDetectionConfig,
    ShotDetector,
    DribbleDetectionConfig,
    DribbleDetector,
    PassDetectionConfig,
    PassDetector,
    MovementDetectionConfig,
    MovementDetector,
    ReboundDetectionConfig,
    ReboundDetector,
)

# =============================================================================
# Tier 2: 동작 분류 (classification/)
# =============================================================================

from motion_analysis.classification import (
    ActionClassifier,
    ShotClassifier,
    DribbleClassifier,
)

# =============================================================================
# Tier 3-5는 Phase 15 H1-H3에서 이전됨:
#   phase_analysis   → biomechanics.phase_analysis
#   form_evaluation  → feedback_system.form_evaluation
#   comparison       → feedback_system.comparison
# 새 위치로 직접 import 하세요. 예: from biomechanics.phase_analysis import ShotPhaseAnalyzer
# =============================================================================


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # --- 내부 모델 (models.py) ---
    # 위상 열거형
    "ShotPhase",
    "DribblePhase",
    # 피드백 열거형
    "FeedbackSeverity",
    "FormGrade",
    "score_to_grade",
    # 데이터 모델
    "MotionSnapshot",
    "DetectionCandidate",
    "PhaseSegment",
    "PhaseResult",
    "FeedbackItem",
    "FormScore",
    "FormEvaluation",
    "ComparisonResult",
    # --- Tier 1: 동작 감지 ---
    "ShotDetectionConfig",
    "ShotDetector",
    "DribbleDetectionConfig",
    "DribbleDetector",
    "PassDetectionConfig",
    "PassDetector",
    "MovementDetectionConfig",
    "MovementDetector",
    "ReboundDetectionConfig",
    "ReboundDetector",
    # --- Tier 2: 동작 분류 ---
    "ActionClassifier",
    "ShotClassifier",
    "DribbleClassifier",
]

__version__ = "2.0.0"
