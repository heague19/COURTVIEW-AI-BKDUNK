# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: recording_routes.py
설명: RTSP 녹화 REST API (Phase 17 S3).

      엔드포인트:
        POST /api/v1/recording/start    녹화 세션 시작 (모든 연결된 카메라)
        POST /api/v1/recording/stop     녹화 세션 종료 + 세그먼트 머지
        GET  /api/v1/recording/status   현재 세션 상태
        GET  /api/v1/recording/health   녹화 가능성 (ffmpeg + 디스크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api_server.schemas.response_schemas import APIResponse
from engine.io.recording import (
    MIN_FREE_BYTES_FOR_RECORDING,
    RecordingService,
    find_ffmpeg,
    has_sufficient_disk_space,
)

router = APIRouter(prefix="/api/v1/recording", tags=["녹화"])

_recording_service: RecordingService | None = None


def get_recording_service() -> RecordingService:
    if _recording_service is None:
        raise RuntimeError("RecordingService가 초기화되지 않았습니다.")
    return _recording_service


def set_recording_service(service: RecordingService) -> None:
    global _recording_service
    _recording_service = service


# =============================================================================
# 스키마
# =============================================================================
class RecordingStartRequest(BaseModel):
    """녹화 시작 요청."""

    quarter: int = Field(default=1, ge=1, le=10, description="시작 쿼터")
    camera_urls: dict[str, str] | None = Field(
        default=None,
        description="{camera_id: rtsp_url} — None이면 CameraService에서 연결된 카메라 자동 사용",
    )
    allow_empty: bool = Field(
        default=False,
        description="True 면 카메라 0대여도 세션 디렉토리 생성 (오퍼레이터 전용 모드, finalize 스켈레톤 용)",
    )


# =============================================================================
# 엔드포인트
# =============================================================================
@router.post("/start", response_model=APIResponse)
async def start_recording(
    request: RecordingStartRequest,
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """
    녹화 세션 시작.

    camera_urls 가 없으면 CameraService에서 연결된 카메라 URL 자동 조회.
    ffmpeg/디스크 공간 검증 후 카메라별 subprocess 시작.
    """
    urls: dict[str, str] = request.camera_urls or {}

    if not urls:
        # CameraService에서 자동 조회
        try:
            from api_server.routes.v1.camera_routes import get_camera_service
            cam_svc = get_camera_service()
            status_all = cam_svc.get_status_all()
            for cam in status_all.cameras:
                if cam.connected and cam.url:
                    urls[cam.camera_id] = cam.url
        except Exception:
            pass

    if not urls and not request.allow_empty:
        raise HTTPException(
            status_code=400,
            detail="연결된 카메라가 없거나 camera_urls 를 명시적으로 제공해야 합니다. "
                   "카메라 없이 세션만 필요하면 allow_empty=true 로 호출하세요.",
        )

    try:
        session = service.start_session(urls, quarter=request.quarter)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return APIResponse(
        success=True,
        message="녹화 시작",
        data={
            "session_id": session.session_id,
            "session_dir": session.session_dir,
            "cameras": list(session.cameras.keys()),
        },
    )


@router.post("/stop", response_model=APIResponse)
async def stop_recording(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """녹화 세션 종료 + 세그먼트 머지."""
    session = service.stop_session()
    if session is None:
        raise HTTPException(status_code=404, detail="진행 중인 녹화 세션이 없습니다.")

    return APIResponse(
        success=True,
        message="녹화 종료 + 머지 완료",
        data={
            "session_id": session.session_id,
            "session_dir": session.session_dir,
            "duration_sec": round(session.ended_at - session.started_at, 1),
            "cameras": [
                {
                    "camera_id": cid,
                    "output": st.output_path,
                }
                for cid, st in session.cameras.items()
            ],
        },
    )


@router.get("/status", response_model=APIResponse)
async def status_recording(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """현재 녹화 세션 상태."""
    return APIResponse(
        success=True,
        message="상태 조회 완료",
        data=service.get_status(),
    )


@router.get("/health", response_model=APIResponse)
async def health_check(
    service: RecordingService = Depends(get_recording_service),
) -> APIResponse:
    """녹화 가능성 점검 (ffmpeg + 디스크)."""
    ffmpeg_path = find_ffmpeg()
    session_root = service._config.session_root
    has_space, free_bytes = has_sufficient_disk_space(session_root)

    ok = ffmpeg_path is not None and has_space
    data: dict[str, Any] = {
        "ffmpeg_available": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
        "disk_space_ok": has_space,
        "free_bytes": free_bytes,
        "free_gb": round(free_bytes / 1024**3, 2),
        "min_required_gb": round(MIN_FREE_BYTES_FOR_RECORDING / 1024**3, 2),
        "session_root": session_root,
    }
    return APIResponse(success=ok, message="녹화 헬스 체크", data=data)


__all__ = ["router", "set_recording_service", "get_recording_service"]
