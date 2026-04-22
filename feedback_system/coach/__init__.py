# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/coach
파일: __init__.py
설명: 코치 역할 피드백 서브모듈 export.
      - motion_feedback: 동작 폼 코칭 (슈팅/드리블/패스/수비/이동)
      - biomechanics_feedback: 생체역학 코칭 (관절/균형/에너지/착지/인체측정)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from feedback_system.coach.motion_feedback import (
    MotionFeedbackConfig,
    MotionFeedbackGenerator,
)
from feedback_system.coach.biomechanics_feedback import (
    BiomechanicsFeedbackConfig,
    BiomechanicsFeedbackGenerator,
)


__all__ = [
    # === motion_feedback ===
    "MotionFeedbackGenerator",
    "MotionFeedbackConfig",
    # === biomechanics_feedback ===
    "BiomechanicsFeedbackGenerator",
    "BiomechanicsFeedbackConfig",
]

__version__ = "1.0.0"
