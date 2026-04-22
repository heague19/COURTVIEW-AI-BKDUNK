# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: task_routes.py
설명: 작업 진행률/상태 REST API 라우트
      - GET /api/v1/tasks/progress  분석 진행률 조회
      - GET /api/v1/tasks/status    작업 상태 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_server.schemas.response_schemas import APIResponse, ProgressResponse
from api_server.services.task_service import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["작업"])

# TaskService 싱글턴 (main.py에서 주입)
_task_service: TaskService | None = None


def get_task_service() -> TaskService:
    """TaskService 의존성 주입."""
    if _task_service is None:
        raise RuntimeError("TaskService가 초기화되지 않았습니다.")
    return _task_service


def set_task_service(service: TaskService) -> None:
    """TaskService 싱글턴 설정 (main.py에서 호출)."""
    global _task_service
    _task_service = service


# =============================================================================
# 엔드포인트
# =============================================================================

@router.get("/progress", response_model=ProgressResponse)
async def get_progress(
    service: TaskService = Depends(get_task_service),
) -> ProgressResponse:
    """
    분석 진행률 조회.

    프레임 현재/전체, 진행률(%), 분석 단계, FPS, ETA를 반환합니다.
    LIVE 모드: frame_total=0, progress_pct=0 (무한 스트림)
    BATCH 모드: 전체 프레임 대비 진행률 표시
    """
    return service.get_progress()


@router.get("/status", response_model=APIResponse)
async def get_task_status(
    service: TaskService = Depends(get_task_service),
) -> APIResponse:
    """
    현재 엔진 작업 상태 조회.

    엔진 상태(idle/loading/running/paused/stopped/error),
    활성 파이프라인 목록, 경기 상태, 업타임을 반환합니다.
    """
    status = service.get_status()
    return APIResponse(
        success=True,
        message="작업 상태 조회 완료",
        data=status,
    )
