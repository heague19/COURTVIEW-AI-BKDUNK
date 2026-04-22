# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/gpu
파일: __init__.py
설명: GPU 리소스 관리 서브패키지
      - gpu_manager.py: VRAM 할당/모니터링/발열 스로틀링/OOM 방어
      - cuda_stream_manager.py: CUDA Stream #1(Stage1) / #2(Stage2) 관리
      - tensorrt_pool.py: 다중 TRT 엔진 풀 (YOLOv8/ViTPose/ReID)
      - batch_accumulator.py: 8카메라 CPU큐 → GPU 배치 텐서 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
