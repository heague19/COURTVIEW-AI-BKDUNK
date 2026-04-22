# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/middleware
설명: FastAPI 미들웨어 서브패키지
      - cors_middleware.py: CORS 설정 (로컬 desktop 전용)
      - error_handler.py: 3단 예외 핸들러 (CourtViewException/ValueError/Exception)
      - request_validator.py: 요청 크기 제한 + rate limiting

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
