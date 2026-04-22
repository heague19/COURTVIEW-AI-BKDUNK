# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: referee_routes.py
설명: AI 심판 판정 REST API 라우트
      - GET  /api/v1/referee/decisions  판정 목록 조회
      - POST /api/v1/referee/challenge  코치 챌린지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_server.schemas.request_schemas import ChallengeRequest
from api_server.schemas.response_schemas import APIResponse, RefereeDecisionResponse, RefereeListResponse
from api_server.services.referee_service import RefereeService

router = APIRouter(prefix="/api/v1/referee", tags=["심판"])

_referee_service: RefereeService | None = None


def get_referee_service() -> RefereeService:
    if _referee_service is None:
        raise RuntimeError("RefereeService가 초기화되지 않았습니다.")
    return _referee_service


def set_referee_service(service: RefereeService) -> None:
    global _referee_service
    _referee_service = service


@router.get("/decisions", response_model=RefereeListResponse)
async def get_decisions(
    limit: int = Query(default=20, ge=1, le=100),
    service: RefereeService = Depends(get_referee_service),
) -> RefereeListResponse:
    """판정 목록 조회."""
    return service.get_decisions(limit=limit)


@router.post("/challenge", response_model=APIResponse)
async def challenge(
    request: ChallengeRequest,
    service: RefereeService = Depends(get_referee_service),
) -> APIResponse:
    """코치 챌린지."""
    return service.challenge(request)
