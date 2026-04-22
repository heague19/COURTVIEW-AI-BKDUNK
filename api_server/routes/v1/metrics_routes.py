# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: metrics_routes.py
설명: GPU/시스템 메트릭 REST API 라우트 (서비스 없이 직접 engine 조회)
      - GET /api/v1/metrics/gpu     GPU 메트릭
      - GET /api/v1/metrics/system  시스템 메트릭

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from api_server.schemas.response_schemas import GPUMetricsResponse, SystemMetricsResponse

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

router = APIRouter(prefix="/api/v1/metrics", tags=["메트릭"])

# GameOrchestrator 직접 참조 (main.py에서 주입)
_orchestrator_ref: GameOrchestrator | None = None


def get_orchestrator() -> GameOrchestrator | None:
    """GameOrchestrator 의존성 주입 (None 허용 — 미초기화 시 기본값 반환)."""
    return _orchestrator_ref


def set_orchestrator(orchestrator: GameOrchestrator | None) -> None:
    """GameOrchestrator 참조 설정 (main.py에서 호출)."""
    global _orchestrator_ref
    _orchestrator_ref = orchestrator


# =============================================================================
# 엔드포인트
# =============================================================================

@router.get("/gpu", response_model=GPUMetricsResponse)
async def get_gpu_metrics(
    orchestrator: GameOrchestrator | None = Depends(get_orchestrator),
) -> GPUMetricsResponse:
    """
    GPU 메트릭 조회.

    VRAM 사용량/잔여량, 사용률(%), 온도, 건강 상태,
    로드된 모델 수, 총 추론 횟수를 반환합니다.
    pynvml 미설치 시 시뮬레이션 모드 값을 반환합니다.
    """
    if orchestrator is None or orchestrator.gpu_manager is None:
        return GPUMetricsResponse()

    gpu_mgr = orchestrator.gpu_manager
    snap = gpu_mgr.snapshot()

    # TensorRT 풀에서 로드된 모델 수 조회
    models_loaded = 0
    if orchestrator.trt_pool is not None:
        from engine.gpu.tensorrt_pool import ModelID
        models_loaded = sum(
            1 for mid in ModelID
            if orchestrator.trt_pool.is_model_ready(mid)
        )

    # 총 추론 횟수: BatchAccumulator에서 조회
    total_inferences = 0
    if orchestrator.batch_accumulator is not None:
        total_inferences = orchestrator.batch_accumulator.total_batches

    return GPUMetricsResponse(
        vram_total_mb=int(snap.total_vram_mb),
        vram_used_mb=int(snap.used_vram_mb),
        vram_utilization=snap.utilization_pct,
        temperature_celsius=snap.temperature_celsius,
        health_status=snap.health.value,
        models_loaded=models_loaded,
        total_inferences=total_inferences,
    )


@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(
    orchestrator: GameOrchestrator | None = Depends(get_orchestrator),
) -> SystemMetricsResponse:
    """
    시스템 메트릭 조회.

    GPU 상태, 엔진 상태, 실시간 FPS, 처리된 총 프레임 수,
    감지된 총 이벤트 수, 업타임을 반환합니다.
    """
    if orchestrator is None:
        return SystemMetricsResponse()

    # GPU 메트릭 구성
    gpu_response = GPUMetricsResponse()
    if orchestrator.gpu_manager is not None:
        snap = orchestrator.gpu_manager.snapshot()
        gpu_response = GPUMetricsResponse(
            vram_total_mb=int(snap.total_vram_mb),
            vram_used_mb=int(snap.used_vram_mb),
            vram_utilization=snap.utilization_pct,
            temperature_celsius=snap.temperature_celsius,
            health_status=snap.health.value,
        )

    # 엔진 상태
    sm = orchestrator.state_manager
    engine_state = sm.engine_state.value

    # FPS (ProgressReporter에서 조회)
    fps = 0.0
    total_frames = 0
    if orchestrator.progress_reporter is not None:
        snap_prog = orchestrator.progress_reporter.snapshot()
        fps = snap_prog.fps
        total_frames = snap_prog.frame_current

    # 총 이벤트 수 (referee에서 조회)
    total_events = 0
    if orchestrator.referee is not None:
        total_events = orchestrator.referee.total_evaluations

    return SystemMetricsResponse(
        gpu=gpu_response,
        engine_state=engine_state,
        fps=fps,
        total_frames=total_frames,
        total_events=total_events,
        uptime_sec=sm.uptime_sec,
    )
