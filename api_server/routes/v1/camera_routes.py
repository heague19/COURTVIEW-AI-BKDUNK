# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: camera_routes.py
설명: 카메라 관리 REST API 라우트
      - POST /api/v1/camera/connect          개별 카메라 연결
      - POST /api/v1/camera/connect-all      전체 카메라 일괄 연결
      - POST /api/v1/camera/reconnect-all    저장된 URL로 전체 재연결
      - POST /api/v1/camera/disconnect-all   전체 연결 해제
      - GET  /api/v1/camera/status-all       전체 카메라 상태
      - GET  /api/v1/camera/{camera_id}/status   개별 상태
      - GET  /api/v1/camera/{camera_id}/snapshot 스냅샷 (JPEG)
      - GET  /api/v1/camera/{camera_id}/stream   MJPEG 실시간 스트림
      - POST /api/v1/camera/{camera_id}/calibrate   캘리브레이션
      - POST /api/v1/camera/{camera_id}/ai-test      AI 감지 테스트
      - POST /api/v1/camera/ai-test-all      전체 AI 테스트
      - POST /api/v1/camera/config           설정 저장
      - GET  /api/v1/camera/config           설정 불러오기

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-28
버전: 1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse

from api_server.schemas.request_schemas import (
    CameraAITestRequest,
    CameraCalibrationRequest,
    CameraConnectAllRequest,
    CameraConnectRequest,
    CameraSaveConfigRequest,
    ManualCalibrationRequest,
)
from api_server.schemas.response_schemas import (
    APIResponse,
    CameraAITestResponse,
    CameraCalibrationResponse,
    CameraStatusAllResponse,
    CameraStatusResponse,
    ManualCalibrationResponse,
)
from api_server.services.camera_service import CameraService

router = APIRouter(prefix="/api/v1/camera", tags=["카메라"])

# CameraService 싱글턴 (main.py에서 주입)
_camera_service: CameraService | None = None


def get_camera_service() -> CameraService:
    """CameraService 의존성 주입."""
    if _camera_service is None:
        raise RuntimeError("CameraService가 초기화되지 않았습니다.")
    return _camera_service


def set_camera_service(service: CameraService) -> None:
    """CameraService 싱글턴 설정 (main.py에서 호출)."""
    global _camera_service
    _camera_service = service


# =============================================================================
# 자동 탐색
# =============================================================================

@router.get("/discover", response_model=APIResponse)
async def discover_cameras(
    subnet: str = "",
    port: int = 554,
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """
    네트워크에서 RTSP 카메라 자동 탐색.

    감지된(혹은 명시된) 서브넷들의 1~254 IP 를 **한 풀에 병렬 스캔**하여
    RTSP 포트(554) 가 열린 장비를 반환합니다.

    subnet 을 비워두면 현재 PC 의 모든 네트워크 인터페이스 대역을 자동 감지합니다.
    다중 인터페이스 환경(WiFi + 유선 등) 은 쉼표로 구분해 입력할 수 있고, 내부에서
    전체 IP 를 단일 풀에 던지므로 서브넷 수와 무관하게 ≈1–2 초 내 완료됩니다.

    Args:
        subnet: "192.168.24" 또는 "192.168.1,169.254.24" 형식. 비우면 자동 감지
        port:   RTSP 포트 (기본 554)
    """
    from fastapi.concurrency import run_in_threadpool

    if not subnet:
        subnet = service.detect_local_subnet()

    subnets = [s.strip() for s in subnet.split(",") if s.strip()]

    # 블로킹 스캔은 threadpool 로 offload → 이벤트 루프 유지
    all_cameras = await run_in_threadpool(
        service.discover_many, subnets, port,
    )

    return APIResponse(
        data=all_cameras,
        message=f"{len(all_cameras)}대 카메라 발견 ({', '.join(subnets)})",
    )


# =============================================================================
# 연결
# =============================================================================

@router.post("/connect", response_model=CameraStatusResponse)
async def connect_camera(
    request: CameraConnectRequest,
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusResponse:
    """개별 카메라 RTSP 연결."""
    return service.connect_camera(request)


@router.post("/connect-all", response_model=CameraStatusAllResponse)
async def connect_all(
    request: CameraConnectAllRequest,
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusAllResponse:
    """전체 카메라 일괄 연결."""
    return service.connect_all(request)


@router.post("/reconnect-all", response_model=CameraStatusAllResponse)
async def reconnect_all(
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusAllResponse:
    """저장된 URL로 전체 재연결."""
    return service.reconnect_all()


@router.post("/{camera_id}/reconnect", response_model=CameraStatusResponse)
async def reconnect_one(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusResponse:
    """단일 카메라 재연결 (Phase 17 S2)."""
    status = service.reconnect_camera(camera_id)
    if status is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"카메라 미등록: {camera_id}")
    return status


@router.post("/disconnect-all", response_model=APIResponse)
async def disconnect_all(
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """전체 카메라 연결 해제."""
    service.disconnect_all()
    return APIResponse(message="전체 카메라 연결 해제 완료")


# =============================================================================
# 헬스 모니터링 (Phase 17 S2)
# =============================================================================
@router.get("/health", response_model=APIResponse)
async def get_health_all(
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """전체 카메라 헬스 상태 조회."""
    return APIResponse(
        message="헬스 조회 완료",
        data={"cameras": service.get_health_all()},
    )


@router.post("/probe", response_model=APIResponse)
async def probe_url(
    request: CameraConnectRequest,
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """
    RTSP URL 사전 검증 — TCP 연결 + RTSP DESCRIBE (Phase 17 S2).

    OpenCV 호출 전 빠르게 연결 가능성 확인. UI가 카메라 URL 입력 시 즉시 유효성 피드백용.
    """
    from infrastructure.preprocessing.video_decoder import probe_rtsp
    result = probe_rtsp(request.url, timeout_sec=3.0)
    return APIResponse(
        success=bool(result.get("reachable") and result.get("rtsp_ok")),
        message=f"probe {'OK' if result.get('rtsp_ok') else 'FAIL'}: {request.url}",
        data=result,
    )


# =============================================================================
# 상태
# =============================================================================

@router.get("/status-all", response_model=CameraStatusAllResponse)
async def get_status_all(
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusAllResponse:
    """전체 카메라 상태 조회."""
    return service.get_status_all()


@router.get("/{camera_id}/status", response_model=CameraStatusResponse)
async def get_camera_status(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> CameraStatusResponse:
    """개별 카메라 상태 조회."""
    return service.get_status(camera_id)


# =============================================================================
# 미리보기
# =============================================================================

@router.get("/{camera_id}/snapshot")
async def get_snapshot(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> Response:
    """카메라 스냅샷 (JPEG 이미지)."""
    # 1. CameraService에서 시도
    jpeg_bytes = service.get_snapshot(camera_id)
    if jpeg_bytes is not None:
        return Response(content=jpeg_bytes, media_type="image/jpeg")

    # 2. stream_routes 프레임 버퍼에서 폴백 (데모/파일 모드)
    try:
        from api_server.routes.v1.stream_routes import _buffers
        buf = _buffers.get(camera_id)
        if buf and buf.jpeg:
            return Response(content=buf.jpeg, media_type="image/jpeg")
    except Exception:
        pass

    return Response(content=b"", status_code=404)


@router.get("/{camera_id}/stream")
async def stream_camera(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> StreamingResponse:
    """카메라 MJPEG 실시간 스트림.

    브라우저 <img src="..."> 태그에서 직접 소비할 수 있는
    multipart/x-mixed-replace 스트림을 반환한다.
    """
    return StreamingResponse(
        service.stream_mjpeg(camera_id, quality=70, max_fps=15.0),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# =============================================================================
# 캘리브레이션
# =============================================================================

@router.post("/{camera_id}/calibrate", response_model=CameraCalibrationResponse)
async def calibrate_camera(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> CameraCalibrationResponse:
    """카메라 캘리브레이션 (자동 — ML 기반)."""
    request = CameraCalibrationRequest(camera_id=camera_id)
    return service.calibrate(request)


@router.post("/{camera_id}/calibrate/manual", response_model=ManualCalibrationResponse)
async def calibrate_camera_manual(
    camera_id: str,
    request: ManualCalibrationRequest,
    service: CameraService = Depends(get_camera_service),
) -> ManualCalibrationResponse:
    """
    수동 캘리브레이션 — UI에서 사용자 클릭 좌표 기반.

    고정 카메라 설치 시 1회 실행. 사용자가 카메라 화면에서
    코트 교차점을 클릭하면 호모그래피를 계산하여 저장합니다.
    """
    return service.calibrate_manual(request)


# =============================================================================
# AI 테스트
# =============================================================================

@router.post("/{camera_id}/ai-test", response_model=CameraAITestResponse)
async def ai_test_camera(
    camera_id: str,
    service: CameraService = Depends(get_camera_service),
) -> CameraAITestResponse:
    """개별 카메라 AI 감지 테스트."""
    request = CameraAITestRequest(camera_id=camera_id)
    return service.ai_test(request)


@router.post("/ai-test-all", response_model=APIResponse)
async def ai_test_all(
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """전체 카메라 AI 감지 테스트."""
    status_all = service.get_status_all()
    results = []
    for cam_status in status_all.cameras:
        if cam_status.connected:
            req = CameraAITestRequest(camera_id=cam_status.camera_id)
            result = service.ai_test(req)
            results.append(result.model_dump())
    return APIResponse(data=results, message=f"{len(results)}대 테스트 완료")


# =============================================================================
# 설정 저장/불러오기
# =============================================================================

@router.post("/config", response_model=APIResponse)
async def save_config(
    request: CameraSaveConfigRequest,
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """카메라 설정 저장."""
    success = service.save_config(request)
    return APIResponse(
        success=success,
        message="설정 저장 완료" if success else "설정 저장 실패",
    )


@router.get("/config", response_model=APIResponse)
async def load_config(
    service: CameraService = Depends(get_camera_service),
) -> APIResponse:
    """저장된 카메라 설정 불러오기."""
    cameras = service.load_config()
    return APIResponse(data=cameras, message=f"{len(cameras)}대 설정 로드")


__all__ = ["router", "set_camera_service"]
__version__ = "1.0.0"
