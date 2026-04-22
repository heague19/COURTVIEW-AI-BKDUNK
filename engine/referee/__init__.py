# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/referee
파일: __init__.py
설명: AI 심판 전용 파이프라인
      - referee_orchestrator.py: violation + foul + decision 통합 판정 루프
      - multi_angle_pipeline.py: 4~8대 카메라 판정 교차검증 + 다수결

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
