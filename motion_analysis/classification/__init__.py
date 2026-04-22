# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/classification
파일: __init__.py

⚠️  **DEPRECATED 예고 (Phase 15 P15-09-L2)** ⚠️
    CV-action.pt 학습 가중치 배포 완료 후 본 규칙 기반 분류기는 제거 예정.
    현재 `ActionClassifier / ShotClassifier / DribbleClassifier` 는
    학습 가중치 배포 완료 전까지 fallback 로 유지.

설명: Tier 2 동작 분류 패키지 초기화
      - ActionClassifier: 11가지 ActionType 주 분류
      - ShotClassifier: SHOOTING → 13종 ShotType 세부 분류
      - DribbleClassifier: DRIBBLING → 13종 DribbleType 세부 분류

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20 (DEPRECATED 예고 추가)
버전: 1.0.0

의존성:
    - motion_analysis/models.py: DetectionCandidate, MotionSnapshot
    - shared/dto/motion_dto.py: ActionClassification, ActionType, MotionFeatureVector

소비자:
    - motion_analysis/phase_analysis/: Tier 3 위상 분석
    - game_analysis/event_detection/: 경기 이벤트 감지

대체 예정:
    - CV-action.pt 학습 가중치 (BiLSTM/Transformer, 7-class)
    - detection/action/ 레이어로 ML 기반 분류 이전
"""

from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "motion_analysis.classification is scheduled for DEPRECATION after "
    "CV-action.pt weight deployment. Use learned ML classifier instead.",
    PendingDeprecationWarning,
    stacklevel=2,
)

from motion_analysis.classification.action_classifier import ActionClassifier
from motion_analysis.classification.dribble_classifier import DribbleClassifier
from motion_analysis.classification.shot_classifier import ShotClassifier


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # Tier 2 주 분류기
    "ActionClassifier",
    # 세부 분류기 (슈팅)
    "ShotClassifier",
    # 세부 분류기 (드리블)
    "DribbleClassifier",
]

__version__ = "1.0.0"
