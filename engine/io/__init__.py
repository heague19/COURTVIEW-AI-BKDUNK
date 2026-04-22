# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/io
파일: __init__.py
설명: 엔진 입출력 서브패키지
      - frame_ingestion.py: 멀티카메라 프레임 수집 + 동기화 + 전처리 연동
      - result_dispatcher.py: 결과 분배 (WS/JSON/Cloud) — 후속 구축
      - progress_reporter.py: 진행률 보고 — 후속 구축

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

# 3단계: frame_ingestion만 구축, 나머지는 후속 단계
__all__: list[str] = []

__version__ = "1.0.0"
