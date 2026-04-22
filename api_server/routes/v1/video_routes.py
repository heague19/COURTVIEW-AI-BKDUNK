# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: video_routes.py
설명: 영상 업로드/하이라이트 REST API 라우트
      - POST /api/v1/video/upload      영상 업로드 (배치 분석)
      - GET  /api/v1/video/highlights   하이라이트 목록

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_server.schemas.request_schemas import UploadVideoRequest
from api_server.schemas.response_schemas import APIResponse, HighlightResponse
from api_server.services.video_service import VideoService

router = APIRouter(prefix="/api/v1/video", tags=["영상"])

# VideoService 싱글턴 (main.py에서 주입)
_video_service: VideoService | None = None


def get_video_service() -> VideoService:
    """VideoService 의존성 주입."""
    if _video_service is None:
        raise RuntimeError("VideoService가 초기화되지 않았습니다.")
    return _video_service


def set_video_service(service: VideoService) -> None:
    """VideoService 싱글턴 설정 (main.py에서 호출)."""
    global _video_service
    _video_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.post("/upload", response_model=APIResponse)
async def upload_video(
    request: UploadVideoRequest,
    service: VideoService = Depends(get_video_service),
) -> APIResponse:
    """
    영상 업로드 (배치 분석).

    로컬 파일 경로 또는 S3 URL을 전달하면 BATCH 모드로 분석을 시작합니다.
    분석 진행률은 /api/v1/tasks/progress 또는 WebSocket으로 확인합니다.
    """
    return service.upload_video(request)


@router.get("/highlights", response_model=list[HighlightResponse])
async def get_highlights(
    limit: int = Query(default=10, ge=1, le=50, description="최대 반환 수"),
    game_id: str = Query(default="", description="게임 ID (클립 URL 생성용)"),
    service: VideoService = Depends(get_video_service),
) -> list[HighlightResponse]:
    """
    하이라이트 클립 목록 조회.

    흥미도(excitement_score) 순으로 정렬된 하이라이트 클립을 반환합니다.
    각 클립에는 이벤트 유형, 시작/종료 시각, video_url이 포함됩니다.
    video_url 패턴: /clips/{game_id}_{quarter}Q_{MMSS}.mp4
    """
    return service.get_highlights(limit=limit, game_id=game_id)
