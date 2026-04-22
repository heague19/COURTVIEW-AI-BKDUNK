# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: feedback_routes.py
설명: 피드백/코칭 REST API 라우트
      - GET /api/v1/feedback/coaching  코칭 추천 조회
      - GET /api/v1/feedback/items     피드백 목록 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_server.schemas.response_schemas import APIResponse
from api_server.services.feedback_service import FeedbackService

router = APIRouter(prefix="/api/v1/feedback", tags=["피드백"])

# FeedbackService 싱글턴 (main.py에서 주입)
_feedback_service: FeedbackService | None = None


def get_feedback_service() -> FeedbackService:
    """FeedbackService 의존성 주입."""
    if _feedback_service is None:
        raise RuntimeError("FeedbackService가 초기화되지 않았습니다.")
    return _feedback_service


def set_feedback_service(service: FeedbackService) -> None:
    """FeedbackService 싱글턴 설정 (main.py에서 호출)."""
    global _feedback_service
    _feedback_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.get("/coaching", response_model=APIResponse)
async def get_coaching(
    player_id: int | None = Query(default=None, description="특정 선수 ID"),
    service: FeedbackService = Depends(get_feedback_service),
) -> APIResponse:
    """
    코칭 추천 조회.

    분석 결과를 기반으로 다음 훈련 추천, 약점 보강, 동작 교정 가이드를 제공합니다.
    player_id를 지정하면 해당 선수에 대한 맞춤 추천을 반환합니다.
    """
    return service.get_coaching(player_id=player_id)


@router.get("/items", response_model=APIResponse)
async def get_feedback_items(
    player_id: int | None = Query(default=None, description="특정 선수 ID"),
    category: str | None = Query(
        default=None,
        description="카테고리 필터 (shooting/dribbling/passing/defense/rebounding)",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="최대 반환 수"),
    service: FeedbackService = Depends(get_feedback_service),
) -> APIResponse:
    """
    세부 동작별 피드백 목록 조회.

    각 세부 동작(슈팅, 드리블, 패스, 수비, 리바운드 등)에 대해
    세분화된 피드백을 제공합니다.
    카테고리 필터로 특정 영역만 조회할 수 있습니다.
    """
    return service.get_feedback_items(
        player_id=player_id,
        category=category,
        limit=limit,
    )
