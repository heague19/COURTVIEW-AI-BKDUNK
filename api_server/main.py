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
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

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
from api_server.services.go2rtc_service import Go2rtcService
from api_server.services.video_service import VideoService
from infrastructure.storage import (
    DEFAULT_DATASETS_BUCKET,
    DEFAULT_REGION,
    DEFAULT_VIDEO_BUCKET,
    ExtractionFinalizerService,
    S3Uploader,
    UploadQueue,
    UploadService,
)
from api_server.services.cloud_sync_service import CloudSyncService
from api_server.services.highlight_clip_service import HighlightClipService
from api_server.services.finalize_service import GameFinalizeService, UIFinalizePayload
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


def _resolve_vendor_dir() -> Path:
    """
    vendor/ 디렉토리 경로 해결 (dev + PyInstaller onedir 모두 지원).

    PyInstaller onedir 번들에서는 `sys._MEIPASS` 하위 `vendor/` 로 datas 가
    복사되며, 개발 모드에서는 프로젝트 루트의 `vendor/` 를 그대로 사용한다.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "vendor"


_go2rtc_dir = _resolve_vendor_dir() / "go2rtc"
_go2rtc_service = Go2rtcService(
    exe_path=_go2rtc_dir / "go2rtc.exe",
    config_path=_go2rtc_dir / "go2rtc.yaml",
)


def _resolve_appdata_dir() -> Path:
    """%APPDATA%\COURTVIEW (Windows) — 영속 데이터 루트."""
    import os
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "COURTVIEW"
    return Path.home() / ".courtview"


# v0.4.0: S3 자동 업로드 서비스 (녹화 영상 + 추출 데이터셋)
# 환경변수로 버킷명/리전 override 가능. 자격증명은 boto3 default chain.
import os as _os_for_uploader
_appdata = _resolve_appdata_dir()
_upload_service = UploadService(
    queue=UploadQueue(_appdata / "upload_queue.db"),
    uploader=S3Uploader(region=_os_for_uploader.environ.get("COURTVIEW_S3_REGION", DEFAULT_REGION)),
    work_dir=_appdata / "upload_work",
    video_bucket=_os_for_uploader.environ.get("COURTVIEW_S3_VIDEO_BUCKET", DEFAULT_VIDEO_BUCKET),
    datasets_bucket=_os_for_uploader.environ.get("COURTVIEW_S3_DATASETS_BUCKET", DEFAULT_DATASETS_BUCKET),
)
_extraction_finalizer = ExtractionFinalizerService(upload_service=_upload_service)
_video_service = VideoService()
_recording_service = RecordingService()
_cloud_sync_service = CloudSyncService()  # Phase 17 S4
_highlight_clip_service = HighlightClipService(_recording_service)  # Phase 18-B 하이라이트 추출
# v0.4.0: 하이라이트 mp4 → S3 자동 업로드 (실시간)
_highlight_clip_service.set_upload_service(
    _upload_service,
    game_id_provider=lambda: getattr(_game_service, "current_game_id", "") or "",
)
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

    # v0.4.0: ExtractionFinalizer 주입 — orchestrator / 추출기 register() 호출용
    _game_service.set_extraction_finalizer(_extraction_finalizer)

    # v0.4.0: S3 업로드 서비스 시작 + RecordingService 콜백 연동
    try:
        _upload_service.start()
        _logger.info("UploadService 활성화 (stats=%s)", _upload_service.stats())

        # 녹화 세션 종료 시 자동 업로드 등록 (v0.4.0: 쿼터 단위 + 통합본)
        def _on_recording_session_end(session) -> None:
            session_dir = Path(session.session_dir)
            game_id = session.session_id  # session_id = 폴더명, game_id 대용
            quarter_pattern = re.compile(r"^(?P<cam>[\w-]+)_Q(?P<q>\d+)\.mp4$")
            for cam_id in session.cameras.keys():
                # 1) 쿼터별 mp4 (cam_Q1.mp4, cam_Q2.mp4 ...) — 메인 산출물
                for q_path in sorted(session_dir.glob(f"{cam_id}_Q*.mp4")):
                    if "_full" in q_path.stem or "_part" in q_path.stem:
                        continue
                    m = quarter_pattern.match(q_path.name)
                    if not m or m.group("cam") != cam_id:
                        continue
                    q = int(m.group("q"))
                    try:
                        _upload_service.submit_video(
                            game_id=game_id, file_path=q_path,
                            role="raw", camera_id=cam_id, quarter=q,
                        )
                    except Exception:
                        _logger.exception("쿼터 mp4 업로드 큐잉 실패: %s", q_path)

                # 2) 통합본 (옵션) — cam_full.mp4 존재하면 함께 업로드
                full_mp4 = session_dir / f"{cam_id}_full.mp4"
                if full_mp4.exists():
                    try:
                        _upload_service.submit_video(
                            game_id=game_id, file_path=full_mp4,
                            role="raw", camera_id=cam_id,
                        )
                    except Exception:
                        _logger.exception("통합본 mp4 업로드 큐잉 실패: %s", full_mp4)

        _recording_service.set_session_end_callback(_on_recording_session_end)
    except Exception:
        _logger.exception("UploadService 시작 실패 — 업로드 비활성으로 계속 진행")

    # v0.3.0: go2rtc 시작 — UI WebRTC 스트림 게이트웨이
    # 실패해도 카메라 기능은 정상 동작 (UI 는 빈 <video> 로 fallback).
    # go2rtc 미포함 개발 환경도 허용.
    try:
        if _go2rtc_service.start():
            _camera_service.set_go2rtc_service(_go2rtc_service)
            _logger.info("go2rtc 활성화 — UI WebRTC 스트림 경로 사용")
        else:
            _logger.warning("go2rtc 시작 실패 — UI 스트림 경로 비활성 (카메라/AI 는 정상)")
    except Exception:
        _logger.exception("go2rtc 시작 중 예외 — UI 스트림 경로 비활성")

    # Plan A (2026-05-13): go2rtc 헬스 1줄 요약 — fallback 여부 즉시 가시화.
    try:
        _g_health = _go2rtc_service.get_health()
        _logger.info(
            "[STARTUP] go2rtc running=%s api_ready=%s api_base=%s",
            _g_health.get("running"), _g_health.get("api_ready"), _g_health.get("api_base"),
        )
        if not _g_health.get("running") or not _g_health.get("api_ready"):
            _logger.warning(
                "[STARTUP] ⚠ go2rtc 비정상 — 카메라가 직결 RTSP 로 fallback. "
                "단일 카메라에 다중 세션 연결 → 버벅임/끊김 위험. "
                "UI 헤더의 go2rtc 배너 또는 GET /api/v1/camera/go2rtc/health 로 확인.",
            )
    except Exception:
        _logger.exception("[STARTUP] go2rtc 헬스 조회 실패 (무시)")

    # Plan B (2026-05-13): ffmpeg HW 디코딩 모드 가시화.
    try:
        from infrastructure.preprocessing.video_decoder import _HWACCEL_MODE as _hw_mode
        _logger.info("[STARTUP] ffmpeg HW decode mode = %r", _hw_mode)
        if _hw_mode == "off":
            _logger.warning(
                "[STARTUP] ⚠ HW 디코딩 비활성 — CPU 만으로 RTSP 디코딩. "
                "8 카메라 × 1080p 환경에서 CPU 병목 위험. "
                "환경변수 COURTVIEW_HWACCEL=d3d11va 로 활성화 권장.",
            )
    except Exception:
        _logger.exception("[STARTUP] hwaccel 모드 조회 실패 (무시)")

    # Phase 17 S2: 카메라 헬스 워치도그 시작 (stalled 스트림 자동 재연결)
    _camera_service.start_watchdog()

    # Phase 17 S4: CloudSync 워커 시작 (오프라인 큐 재시도)
    _cloud_sync_service.start_worker()

    # Phase 17 S4: 경기 종료 시 ExportService 스냅샷을 CloudSync로 전송
    # v0.4.0: + 추출기 일괄 finalize → S3 자동 업로드 (background)
    def _on_game_end(_orch):
        try:
            snapshot = _export_service.collect_snapshot()
            _cloud_sync_service.sync_game_result(snapshot)
        except Exception:
            _logger.exception("경기 종료 CloudSync 훅 실패")

        # 등록된 추출기 일괄 finalize → upload_service 큐 적재 (background)
        # 등록 추출기 0개면 즉시 반환 (안전).
        try:
            game_id = getattr(_orch, "session_id", "") or getattr(_orch, "game_id", "")
            registered_count = _extraction_finalizer.count()
            if registered_count > 0:
                _logger.info(
                    "경기 종료 — %d 추출기 finalize → S3 업로드 (background)",
                    registered_count,
                )
                _extraction_finalizer.finalize_all_async(game_id=game_id)
        except Exception:
            _logger.exception("ExtractionFinalizer 트리거 실패")

        # 2026-05-21: 안전망 — UI 가 /api/v1/finalize/game 호출 안 해도
        # minimal manifest 라도 생성. LIVE 모드의 PLAN_REPLAY_STOP_FIX.md 형 누락 방어.
        #
        # 주의: recording_service.get_status() 는 _last_session 캐시를 들고 있을 수 있어
        # REPLAY 모드 (recording 없이 import_* 폴더 분석) 에서 이전 LIVE 세션의 session_dir
        # 가 stale 하게 잡힐 수 있음 → 잘못된 폴더에 minimal manifest 쓰면 진짜 LIVE
        # 결과를 덮어씀. 두 조건 중 하나만 safety 발동:
        #   (a) active=True   — 녹화 진행 중인 LIVE
        #   (b) ended_at 가 최근 (≤ 60s) — recording/stop 직후 game/stop 흐름
        # REPLAY 는 두 조건 모두 안 맞으므로 자연스럽게 skip.
        # REPLAY 의 finalize 누락은 별도 fix (UI 가 session_id 명시 전달) 로 처리.
        try:
            st = _recording_service.get_status()
            if not isinstance(st, dict):
                st = {}
            session_dir = st.get("session_dir")
            active = bool(st.get("active"))
            ended_at = st.get("ended_at") or 0
            recently_ended = False
            if isinstance(ended_at, (int, float)) and ended_at > 0:
                recently_ended = (time.time() - float(ended_at)) <= 60.0

            if not session_dir:
                _logger.debug("[SAFETY-FINALIZE] session_dir 없음 — skip")
            elif not (active or recently_ended):
                _logger.debug(
                    "[SAFETY-FINALIZE] stale session_dir (active=%s, ended_at=%s) — skip",
                    active, ended_at,
                )
            else:
                manifest_path = Path(session_dir) / "finalize" / "manifest.json"
                if manifest_path.exists():
                    _logger.debug("[SAFETY-FINALIZE] manifest 이미 존재 — skip: %s", manifest_path)
                else:
                    minimal = UIFinalizePayload(
                        match_id="",
                        league="fiba",
                        home_team={"name": "HOME", "short_code": "HOM", "players": []},
                        away_team={"name": "AWAY", "short_code": "AWA", "players": []},
                        ended_at=time.time(),
                    )
                    result = _finalize_service.finalize(minimal)
                    if result.success:
                        _logger.info(
                            "[SAFETY-FINALIZE] minimal manifest 생성 (UI 누락 보완): %s",
                            result.finalize_dir,
                        )
                    else:
                        _logger.warning("[SAFETY-FINALIZE] 실패: %s", result.error)
        except Exception:
            _logger.exception("[SAFETY-FINALIZE] 예외")
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

    # 2026-05-13: G — Orchestrator 사전 빌드 백그라운드 트리거
    #   엔진 서버는 즉시 응답 가능 상태로 두고, 사용자가 카메라 연결/캘리브 하는 동안
    #   모델/TRT 엔진 로딩이 미리 끝나도록. game/start 클릭 시 ~51초 → ~0초.
    _game_service.preload_orchestrator_async()

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

    # v0.3.0: go2rtc 종료
    try:
        _go2rtc_service.stop()
    except Exception:
        _logger.exception("go2rtc 종료 중 예외 (무시)")

    # v0.4.0: 업로드 서비스 종료 (in-flight 작업은 다음 부팅에서 큐에서 재개)
    try:
        _upload_service.stop()
    except Exception:
        _logger.exception("UploadService 종료 중 예외 (무시)")

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
# Plan E STEP 5 (2026-05-13): /health 호출 간격 + 응답 시간 측정.
#   UI 가 5초마다 /health 폴링 → engine 이 늦으면 UI 가 OFFLINE pill 표시.
#   gap > 6s = event loop 블로킹 의심 (GIL 컨텐션 / sync 호출 starve).
#   dt_ms > 100ms = /health 자체가 무거움 (정상 <1ms — 단순 속성 읽기).
_last_health_ts: float = 0.0


@app.get("/health")
async def health_check() -> dict:
    """서버 헬스 체크."""
    global _last_health_ts
    _now = time.monotonic()
    _gap = _now - _last_health_ts if _last_health_ts > 0 else 0.0
    _last_health_ts = _now
    if _gap > 6.0:
        _logger.warning(
            "[FLOW 0] HEALTH ⚠ /health 호출 간격 %.2fs (정상 ~5s) — "
            "engine event loop 블로킹 의심 (GIL 컨텐션 / sync 호출 starve)",
            _gap,
        )

    _t0 = time.perf_counter()
    payload = {
        "status": "ok",
        "version": "1.0.0",
        "game_active": _game_service.is_game_active,
        "ws_connections": _ws_manager.connection_count,
    }
    _dt_ms = (time.perf_counter() - _t0) * 1000
    if _dt_ms > 100.0:
        _logger.warning(
            "[FLOW 0] HEALTH ⚠ /health 응답 생성 %.1fms (정상 <1ms)",
            _dt_ms,
        )
    return payload


@app.get("/")
async def root() -> dict:
    """루트 엔드포인트."""
    return {
        "name": "COURTVIEW Desktop API",
        "version": "1.0.0",
        "docs": "/docs",
    }
