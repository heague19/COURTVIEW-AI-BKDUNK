# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline/fusion
파일: __init__.py
설명: 멀티카메라 융합 오케스트레이션
      - 기존 detection/ 모듈의 detect_multi_view() API를 호출하여 결과 통합
      - NMS, 삼각측량, IoU 등은 기존 모듈에 구현 완료 — 여기서 재구현하지 않음
      - engine은 오케스트레이션 계층 — 기존 모듈 변경 0건 원칙

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
