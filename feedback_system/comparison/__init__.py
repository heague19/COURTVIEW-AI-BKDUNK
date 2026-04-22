# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/comparison
파일: __init__.py
설명: 폼 비교 패키지 (Phase 15 H3: motion_analysis/comparison → feedback_system/comparison 이전).
      - FormComparator: DTW 기반 폼 유사도 비교기

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0

의존성:
    - motion_analysis/models.py: ComparisonResult, MotionSnapshot, PhaseResult

소비자:
    - feedback_system/: 비교 결과 피드백 반영
    - game_analysis/: 동작 품질 비교 통계
"""

from __future__ import annotations

from feedback_system.comparison.form_comparator import FormComparator


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "FormComparator",
]

__version__ = "2.0.0"
