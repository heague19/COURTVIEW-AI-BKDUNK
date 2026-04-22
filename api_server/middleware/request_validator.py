# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/middleware
파일: request_validator.py
설명: 요청 검증 미들웨어
      - 요청 크기 제한
      - 요청 속도 제한 (기본적 rate limiting)
      - 요청 로깅

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import time
from threading import RLock
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api_server.schemas.response_schemas import APIResponse

_logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH: Final[int] = 100 * 1024 * 1024  # 100MB
_RATE_LIMIT_PER_SEC: Final[int] = 100
_RATE_WINDOW_SEC: Final[float] = 1.0


class RequestValidatorMiddleware(BaseHTTPMiddleware):
    """요청 검증 미들웨어."""

    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)
        # defaultdict 대신 일반 dict — 조회만으로 빈 entry 자동 생성 방지
        self._request_counts: dict[str, list[float]] = {}
        self._lock: RLock = RLock()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # 1. 요청 크기 검증
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_CONTENT_LENGTH:
            return JSONResponse(
                status_code=413,
                content=APIResponse(
                    success=False,
                    message=f"요청 크기 초과: {int(content_length)} > {_MAX_CONTENT_LENGTH}",
                    error_code=413,
                ).model_dump(),
            )

        # 2. 속도 제한 (IP 기반)
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            existing = self._request_counts.get(client_ip)
            if existing is None:
                timestamps: list[float] = []
            else:
                # 윈도우 외 타임스탬프 제거
                timestamps = [t for t in existing if now - t < _RATE_WINDOW_SEC]
            if len(timestamps) >= _RATE_LIMIT_PER_SEC:
                self._request_counts[client_ip] = timestamps
                return JSONResponse(
                    status_code=429,
                    content=APIResponse(
                        success=False,
                        message="요청 속도 제한 초과",
                        error_code=429,
                    ).model_dump(),
                )
            timestamps.append(now)
            self._request_counts[client_ip] = timestamps

        # 3. 요청 처리 + 로깅
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        _logger.debug(
            "%s %s → %d (%.1fms)",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )

        return response


def setup_request_validator(app: FastAPI) -> None:
    """요청 검증 미들웨어 등록."""
    app.add_middleware(RequestValidatorMiddleware)
