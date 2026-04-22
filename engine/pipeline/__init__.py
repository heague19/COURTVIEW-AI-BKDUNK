# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: __init__.py
설명: Cadence별 5등급 파이프라인 + 멀티카메라 융합 서브패키지
      - fusion/: 8cam 감지/포즈/트래킹 융합 (4단계, 현재 구축)
      - frame_pipeline.py: 🔴 FRAME (감지→포즈→트래킹, 33ms)
      - event_pipeline.py: 🟠 EVENT (이벤트감지→통계증분)
      - possession_pipeline.py: 🟡 POSSESSION (전술→개인→하이라이트)
      - period_pipeline.py: 🟢 PERIOD (쿼터요약→추세→로테이션)
      - postgame_pipeline.py: 🔵 POST-GAME (보고서→추출→동기화)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
