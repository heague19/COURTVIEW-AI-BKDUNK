# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/phase_analysis
파일: __init__.py
설명: 위상 분석 패키지 (Phase 15 H1: motion_analysis/phase_analysis → biomechanics/phase_analysis 이전).
      - ShotPhaseAnalyzer: 슈팅 4단계 위상 분해
      - DribblePhaseAnalyzer: 드리블 4단계 위상 분해

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0

의존성:
    - motion_analysis/models.py: ShotPhase, DribblePhase, PhaseSegment, PhaseResult

소비자:
    - feedback_system/form_evaluation/: 폼 평가
    - ai_referee/: 위상 기반 바이올레이션 판정
"""

from __future__ import annotations

from biomechanics.phase_analysis.dribble_phase_analyzer import (
    DribblePhaseAnalyzer,
)
from biomechanics.phase_analysis.shot_phase_analyzer import (
    ShotPhaseAnalyzer,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 슈팅 위상 분석
    "ShotPhaseAnalyzer",
    # 드리블 위상 분석
    "DribblePhaseAnalyzer",
]

__version__ = "2.0.0"
