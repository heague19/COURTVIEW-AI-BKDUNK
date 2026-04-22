# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server
설명: Desktop API 서버 (Layer 9)
      - FastAPI 앱 조립 (main.py)
      - middleware/: CORS + 에러 핸들러 + 요청 검증
      - schemas/: Pydantic v2 요청/응답 스키마 35종
      - routes/v1/: 11 라우터 × 37+ HTTP 엔드포인트
      - services/: 13 비즈니스 로직 + 5 facade
      - websocket/: 연결 관리 + 진행률 브로드캐스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
