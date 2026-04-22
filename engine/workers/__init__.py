# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/workers
파일: __init__.py
설명: 비동기 워커 서브모듈
      - analysis_worker: 🟡POSSESSION(4T) + 🟢PERIOD(2T) 비동기 분석
      - export_worker: 🔵POST-GAME 내보내기/데이터추출
      - sync_worker: 클라우드 동기화

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []
__version__ = "1.0.0"
