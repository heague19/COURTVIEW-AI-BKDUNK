# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server
파일: main.py
설명: FastAPI 앱 생성 + 전체 조립
      - 라이프사이클 (startup/shutdown)
      - 미들웨어 등록
      - 라우트 등록
      - WebSocket 설정
      - GameOrchestrator 빌드 + 서비스 주입

      실행:
        uvicorn api_server.main:app --host 0.0.0.0 --port 8000

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# 미들웨어
from api_server.middleware.cors_middleware import setup_cors
from api_server.middleware.error_handler import setup_error_handlers
from api_server.middleware.request_validator import setup_request_validator

# 라우트
from api_server.routes.v1 import (
    camera_routes,
    clips_routes,
    export_routes,
    finalize_routes,
    game_routes,
    referee_routes,
    recording_routes,
    stream_routes,
    tactical_routes,
    video_routes,
    feedback_routes,
    report_routes,
    task_routes,
    metrics_routes,
)

# WebSocket
from api_server.websocket.connection_manager import ConnectionManager
from api_server.websocket import progress_handler

# 서비스
from api_server.services.game_service import GameService
from api_server.services.referee_service import RefereeService
from api_server.services.tactical_service import TacticalService
from api_server.services.feedback_service import FeedbackService
from api_server.services.report_service import ReportService
from api_server.services.task_service import TaskService
from api_server.services.export_service import ExportService
from api_server.services.camera_service import CameraService
from api_server.services.video_service import VideoService
from api_server.services.cloud_sync_service import CloudSyncService
from api_server.services.highlight_clip_service import HighlightClipService
from api_server.services.finalize_service import GameFinalizeService
from engine.io.recording import RecordingService

_logger = logging.getLogger(__name__)

# =============================================================================
# 글로벌 서비스 인스턴스
# =============================================================================
_game_service = GameService()
_referee_service = RefereeService()
_tactical_service = TacticalService()
_feedback_service = FeedbackService()
_report_service = ReportService()
_task_service = TaskService()
_export_service = ExportService()
_camera_service = CameraService()
_video_service = VideoService()
_recording_service = RecordingService()
_cloud_sync_service = CloudSyncService()  # Phase 17 S4
_highlight_clip_service = HighlightClipService(_recording_service)  # Phase 18-B 하이라이트 추출
_finalize_service = GameFinalizeService(_recording_service, _export_service)  # Phase 18-C 경기 종료 패키지
_ws_manager = ConnectionManager()


# =============================================================================
# 라이프사이클
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 라이프사이클."""
    _logger.info("COURTVIEW API 서버 시작")

    # 서비스 → 라우트 주입
    game_routes.set_game_service(_game_service)
    camera_routes.set_camera_service(_camera_service)
    referee_routes.set_referee_service(_referee_service)
    tactical_routes.set_tactical_service(_tactical_service)
    feedback_routes.set_feedback_service(_feedback_service)
    report_routes.set_report_service(_report_service)
    task_routes.set_task_service(_task_service)
    video_routes.set_video_service(_video_service)
    export_routes.set_export_service(_export_service)
    recording_routes.set_recording_service(_recording_service)
    clips_routes.set_recording_service(_recording_service)
    _video_service.bind_recording_service(_recording_service)
    finalize_routes.set_finalize_service(_finalize_service)

    # 카메라 → 게임 서비스 연동
    # 경기 시작 시 source_urls가 비어 있으면 연결된 카메라에서 자동으로 URL을 가져온다.
    _game_service.set_camera_service(_camera_service)

    # Phase 17 S2: 카메라 헬스 워치도그 시작 (stalled 스트림 자동 재연결)
    _camera_service.start_watchdog()

    # Phase 17 S4: CloudSync 워커 시작 (오프라인 큐 재시도)
    _cloud_sync_service.start_worker()

    # Phase 17 S4: 경기 종료 시 ExportService 스냅샷을 CloudSync로 전송
    def _on_game_end(_orch):
        try:
            snapshot = _export_service.collect_snapshot()
            _cloud_sync_service.sync_game_result(snapshot)
        except Exception:
            _logger.exception("경기 종료 CloudSync 훅 실패")
    _game_service.on_game_end(_on_game_end)

    # 경기 시작 시 서비스들에 orchestrator 바인딩
    def _bind_orchestrator(orch):
        _referee_service.bind_orchestrator(orch)
        _tactical_service.bind_orchestrator(orch)
        _feedback_service.bind_orchestrator(orch)
        _report_service.bind_orchestrator(orch)
        _task_service.bind_orchestrator(orch)
        _video_service.bind_orchestrator(orch)
        _export_service.bind_orchestrator(orch)
        metrics_routes.set_orchestrator(orch)

        # Phase 18-B: PossessionPipeline 에 클립 옵저버 연결 → 하이라이트 감지 시 자동 MP4 추출
        try:
            possession_pipeline = getattr(orch, "_possession_pipeline", None)
            if possession_pipeline is not None and hasattr(possession_pipeline, "set_clip_observer"):
                possession_pipeline.set_clip_observer(_highlight_clip_service.on_clip)
                _logger.info("하이라이트 클립 옵저버 연결 완료")
            else:
                _logger.warning("PossessionPipeline 에 set_clip_observer 없음 — 자동 추출 비활성")
        except Exception:
            _logger.exception("하이라이트 옵저버 연결 실패 (무시)")
    _game_service.on_game_start(_bind_orchestrator)

    # WebSocket 의존성 주입
    progress_handler.set_ws_dependencies(_ws_manager, _game_service)

    # WebSocket 브로드캐스트 루프 (백그라운드)
    broadcast_task = asyncio.create_task(
        progress_handler.broadcast_loop(interval_ms=500.0)
    )

    yield

    # 종료
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass

    # 경기 진행 중이면 중지
    if _game_service.is_game_active:
        _game_service.stop_game()

    # Phase 17 S2: 워치도그 종료
    _camera_service.stop_watchdog()

    # Phase 17 S3: 녹화 세션 안전 종료
    if _recording_service.is_recording:
        try:
            _recording_service.stop_session()
        except Exception:
            _logger.exception("녹화 세션 종료 중 오류")

    # Phase 17 S4: CloudSync 워커 종료
    _cloud_sync_service.stop_worker()

    # Phase 18-B: 하이라이트 클립 추출 스레드풀 정리
    try:
        _highlight_clip_service.shutdown()
    except Exception:
        _logger.exception("HighlightClipService 종료 중 오류 (무시)")

    _logger.info("COURTVIEW API 서버 종료")


# =============================================================================
# FastAPI 앱 생성
# =============================================================================
app = FastAPI(
    title="COURTVIEW Desktop API",
    description="AI 농구 분석 + AI 심판 로컬 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)

# =============================================================================
# 미들웨어 등록
# =============================================================================
setup_cors(app)
setup_error_handlers(app)
setup_request_validator(app)

# =============================================================================
# 라우트 등록
# =============================================================================
app.include_router(camera_routes.router)
app.include_router(export_routes.router)
app.include_router(game_routes.router)
app.include_router(stream_routes.router)
app.include_router(referee_routes.router)
app.include_router(tactical_routes.router)
app.include_router(video_routes.router)
app.include_router(feedback_routes.router)
app.include_router(report_routes.router)
app.include_router(task_routes.router)
app.include_router(metrics_routes.router)
app.include_router(recording_routes.router)
app.include_router(clips_routes.router)
app.include_router(finalize_routes.router)

# WebSocket 라우트
app.include_router(progress_handler.router)


# =============================================================================
# 데모 페이지
# =============================================================================
@app.get("/demo")
async def demo_page():
    """데모 전용 페이지 (IOConfig.demo_page_path 기반)."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    from engine.config import IOConfig
    demo_file = Path(__file__).parent.parent / IOConfig().demo_page_path
    return FileResponse(str(demo_file), media_type="text/html")


# =============================================================================
# 헬스 체크
# =============================================================================
@app.get("/health")
async def health_check() -> dict:
    """서버 헬스 체크."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "game_active": _game_service.is_game_active,
        "ws_connections": _ws_manager.connection_count,
    }


@app.get("/")
async def root() -> dict:
    """루트 엔드포인트."""
    return {
        "name": "COURTVIEW Desktop API",
        "version": "1.0.0",
        "docs": "/docs",
    }
