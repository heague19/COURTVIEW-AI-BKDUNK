# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/form_evaluation
파일: __init__.py
설명: 폼 평가 패키지 (Phase 15 H2: motion_analysis/form_evaluation → feedback_system/form_evaluation 이전).
      - ShootingCriteria / DribbleCriteria: YAML 기반 평가 기준
      - ShootingFormEvaluator / DribbleFormEvaluator: 8카테고리 100점 채점
      - RangeJudgment: 기준 범위 판정 결과

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0

의존성:
    - motion_analysis/models.py: FormEvaluation, FormScore, FeedbackItem

소비자:
    - feedback_system/comparison/: 비교
    - game_analysis/: shot_quality, dribble_quality
    - feedback_system/: 피드백 생성
"""

from __future__ import annotations

from feedback_system.form_evaluation.dribble_criteria import DribbleCriteria
from feedback_system.form_evaluation.dribble_form_evaluator import (
    DribbleFormEvaluator,
)
from feedback_system.form_evaluation.shooting_criteria import (
    RangeJudgment,
    ShootingCriteria,
)
from feedback_system.form_evaluation.shooting_form_evaluator import (
    ShootingFormEvaluator,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 기준 관리
    "ShootingCriteria",
    "DribbleCriteria",
    "RangeJudgment",
    # 폼 평가기
    "ShootingFormEvaluator",
    "DribbleFormEvaluator",
]

__version__ = "2.0.0"
