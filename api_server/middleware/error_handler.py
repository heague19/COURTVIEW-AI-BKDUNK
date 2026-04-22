# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/middleware
파일: error_handler.py
설명: 전역 에러 핸들러
      - CourtViewException → HTTP 응답 매핑
      - 예상치 못한 예외 → 500 Internal Server Error
      - 에러 로깅

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.exceptions.base_exception import CourtViewException
from api_server.schemas.response_schemas import APIResponse

_logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI) -> None:
    """전역 에러 핸들러 등록."""

    @app.exception_handler(CourtViewException)
    async def courtview_exception_handler(
        request: Request, exc: CourtViewException,
    ) -> JSONResponse:
        """CourtViewException → HTTP 응답."""
        _logger.warning(
            "CourtViewException: %s (code=%s, path=%s)",
            exc.message, exc.error_code, request.url.path,
        )
        response = APIResponse(
            success=False,
            message=exc.message,
            error_code=exc.error_code.code if exc.error_code else None,
        )
        http_status = exc.error_code.http_status if exc.error_code else 500
        return JSONResponse(
            status_code=http_status,
            content=response.model_dump(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError,
    ) -> JSONResponse:
        """ValueError → 400 Bad Request."""
        _logger.warning("ValueError: %s (path=%s)", exc, request.url.path)
        response = APIResponse(
            success=False,
            message=str(exc),
            error_code=400,
        )
        return JSONResponse(status_code=400, content=response.model_dump())

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception,
    ) -> JSONResponse:
        """예상치 못한 예외 → 500."""
        _logger.error(
            "Unhandled exception: %s (path=%s)\n%s",
            exc, request.url.path, traceback.format_exc(),
        )
        response = APIResponse(
            success=False,
            message="서버 내부 오류가 발생했습니다.",
            error_code=500,
        )
        return JSONResponse(status_code=500, content=response.model_dump())
