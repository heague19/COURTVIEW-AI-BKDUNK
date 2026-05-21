# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop Launcher

기동 시퀀스:
  1. 스플래시 표시 (tkinter, 경량)
  2. 첫 실행 또는 캐시 비어있음 → TensorRT 엔진 사전 빌드 (warmup)
  3. 엔진 서버(:8000) + UI 서버(:3000) 자식 프로세스로 기동
  4. 브라우저 자동 오픈 → 스플래시 종료

종료: Ctrl+C
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

# PyInstaller freeze 환경에서 multiprocessing 지원
multiprocessing.freeze_support()


# v0.5.4: frozen EXE 가 ultralytics 의 pip install 시도 등으로 자기 자신을
# `-m pip install ...` 인자로 호출당할 수 있음 → launcher.main() 새 창.
# 그것만 차단. multiprocessing.Process 자식은 freeze_support() 가 알아서 처리하므로
# 절대 차단하면 안 됨 (v0.5.3 regression: worker spawn 차단해서 engine/UI 서버 안 뜸).
def _is_pip_recursive_call() -> bool:
    """frozen EXE 가 ultralytics pip install 호출당했는지만 검사."""
    if not getattr(sys, "frozen", False):
        return False
    argv = sys.argv[1:]
    if not argv:
        return False
    # ultralytics 가 시도하는 `-m pip install ...` 만 차단
    if argv[0] == "-m" and "pip" in argv:
        return True
    return False


if _is_pip_recursive_call():
    # 새 launcher 창 안 뜨게 즉시 종료 — ultralytics 는 retry 후 폴백 진행.
    sys.exit(2147483651)  # STATUS_INVALID_INFO_CLASS

# =============================================================================
# 프로젝트 경로 설정 (frozen 환경 포함)
# =============================================================================
if getattr(sys, "frozen", False):
    # PyInstaller로 빌드된 exe 환경
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
else:
    # 개발 환경
    BASE_DIR = Path(__file__).parent
    EXE_DIR = BASE_DIR

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(BASE_DIR))

# UI 디렉토리 (데이터 번들에 포함됨)
UI_DIR = BASE_DIR / "courtview_ui"
if UI_DIR.exists():
    sys.path.insert(0, str(UI_DIR))

# =============================================================================
# 로깅 (v0.4.1: 파일 핸들러 추가 — %APPDATA%\COURTVIEW\logs\courtview.log)
# =============================================================================
def _setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # stream handler (콘솔)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    root.addHandler(sh)
    # file handler (영속)
    try:
        import os as _os_log
        _ad = _os_log.environ.get("APPDATA")
        log_dir = (
            Path(_ad) / "COURTVIEW" / "logs"
            if _ad else Path.home() / ".courtview" / "logs"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_dir / "courtview.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        ))
        root.addHandler(fh)
    except Exception as _exc:  # noqa: BLE001
        sys.stderr.write(f"[launcher] 파일 로그 핸들러 초기화 실패: {_exc}\n")

    # =========================================================================
    # 2026-05-11 진단 로그 일괄 침묵 (사용자 요청)
    #   - 모든 verbose 진단 로그 (SCORE-FLOW / BALL-FLOW / PIPE / DECODE /
    #     ORCH heartbeat / DISPATCH / WS-BROADCAST / GAME-SVC / PLAYER-FLOW
    #     / 카메라 connect / 녹화 등) 를 WARNING 레벨로 올려 INFO 묻음.
    #   - 되돌리려면: 아래 리스트 비우거나 _SILENCE_VERBOSE = False 로.
    # =========================================================================
    _SILENCE_VERBOSE: bool = True     # 2026-05-13: RTSP verbose 로그 비활성화 (사용자 요청)
    _silenced_loggers: list[str] = [
        # 새로 추가한 진단 로그 모듈
        "game_analysis.game_state.event_detection.score_detector",
        "detection.ball_detection.ball_detector",
        "detection.player_detection.player_detector",
        "infrastructure.preprocessing.video_decoder",
        "engine.pipeline.frame_pipeline",
        "engine.pipeline.fusion.detection_fusion",
        "engine.io.result_dispatcher",
        "api_server.websocket.progress_handler",
        "api_server.services.game_service",
        "api_server.services.camera_service",
        "api_server.services.go2rtc_service",
        "courtview-ui",
        # 녹화 / 카메라 관련
        "engine.io.recording",
        "api_server.routes.v1.recording_routes",
        "api_server.routes.v1.camera_routes",
        # orchestrator 의 [DET F#]/[SCORE F#]/[POSS F#]/[ORCH] 등
        "engine.orchestrator.game_orchestrator",
        # HTTP / WS 노이즈
        "httpx",
        "uvicorn.access",
    ]
    if _SILENCE_VERBOSE:
        for _name in _silenced_loggers:
            logging.getLogger(_name).setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("launcher")

ENGINE_HOST = "0.0.0.0"
ENGINE_PORT = 8000
UI_HOST = "0.0.0.0"
UI_PORT = 3000


# =============================================================================
# 빌드 버전 조회 (_build_version.json 또는 기본값)
# =============================================================================
def get_build_version() -> str:
    for candidate in (
        BASE_DIR / "_build_version.json",
        EXE_DIR / "_build_version.json",
    ):
        if candidate.exists():
            try:
                import json
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data.get("version", "0.0.0-dev")
            except Exception:
                pass
    return "0.0.0-dev"


BUILD_VERSION = get_build_version()


# =============================================================================
# 자식 프로세스 target 함수는 별도 모듈에 — PyInstaller frozen 에서 Process 가
# __main__ reload 시 target attribute 찾기 실패하는 이슈 회피.
# =============================================================================
from launcher_workers import run_engine_server, run_ui_server  # noqa: E402


# =============================================================================
# 스플래시 + 워밍업 통합
# =============================================================================
def _check_and_apply_update(splash) -> None:
    """스플래시 띄운 상태에서 auto-update 체크 + 적용."""
    try:
        from launcher_updater import check_for_update, apply_update
    except Exception:
        logger.debug("updater 모듈 없음 — 스킵")
        return

    try:
        splash.set_status("업데이트 확인 중...")
        info = check_for_update()
        if info is None:
            return  # 최신이거나 네트워크 실패 — 조용히 진행

        # 새 버전 있음 — 사용자에게 간단 알림 (Tk messagebox 쓰면 스플래시 블록)
        # 단순히 로그 + 스플래시 문구 로 진행
        logger.info("새 버전 적용 시작: %s → ...", info.version)

        def _progress(stage, ratio):
            label = {
                "download": "새 버전 다운로드",
                "verify": "무결성 검증",
                "extract": "압축 해제",
                "swap": "교체 중",
                "restart": "재시작 준비",
            }.get(stage, stage)
            splash.set_status(f"업데이트: {label}... {int(ratio * 100)}%")

        # apply_update 는 성공 시 sys.exit(0) — 아래로 안 내려옴
        ok = apply_update(info, on_progress=_progress)
        if not ok:
            logger.warning("업데이트 실패 — 현재 버전으로 계속 진행")
    except Exception:
        logger.exception("업데이트 중 예외 — 현재 버전으로 계속")


def _preflight_splash_and_warmup():
    """
    스플래시 표시 + 업데이트 체크 + 필요하면 TensorRT 워밍업.

    Returns:
        SplashController | None (None 이면 스플래시 없이 진행)
    """
    try:
        from launcher_splash import SplashController
        from launcher_warmup import warmup, should_warmup, mark_first_run_complete
        from infrastructure.storage.paths import dump_paths
    except Exception:
        logger.exception("스플래시/워밍업 모듈 임포트 실패 — 스킵")
        return None

    splash = SplashController()
    splash.start()
    splash.set_status("초기화 중...")

    # 1) Auto-update 체크 (frozen 에서만 실제 동작)
    _check_and_apply_update(splash)

    # 경로 정보 로깅 (진단용)
    try:
        paths = dump_paths()
        for k, v in paths.items():
            logger.info("path.%s = %s", k, v)
    except Exception:
        pass

    # 워밍업 필요 여부 판단
    need = False
    try:
        need = should_warmup()
    except Exception:
        logger.exception("should_warmup() 실패 — 건너뜀")
        need = False

    if need:
        splash.set_status("AI 엔진 최적화 중...")

        def _on_progress(cur, total, name, status):
            label = {
                "start": "준비",
                "cached": "캐시",
                "building": "빌드",
                "done": "완료",
                "error": "오류",
            }.get(status, status)
            splash.set_progress(cur + 1, total, f"{label} — {name}")

        try:
            result = warmup(on_progress=_on_progress)
            # 시도 자체는 완료 (성공 + 실패 + 캐시 == total) → 플래그 작성
            # 실패한 모델의 해시는 blocklist 에 기록되어 다음 실행 시 skip 됨
            # ONNX 파일이 업데이트되면 해시 바뀌어 자동 재시도
            total_attempted = result.built + result.cached + result.failed
            if result.total > 0 and total_attempted == result.total:
                mark_first_run_complete()
            if result.failed > 0:
                logger.warning(
                    "워밍업 일부 실패 (%d/%d) — PyTorch fallback 으로 서버 운영됨. 실패 모델: %s",
                    result.failed, result.total,
                    [name for name, _ in result.failures],
                )
        except Exception:
            logger.exception("워밍업 중 예외")

    splash.set_status("서버 기동 중...")
    return splash


# =============================================================================
# 메인
# =============================================================================
def _monitor_process_memory(
    engine_proc: multiprocessing.Process,
    ui_proc: multiprocessing.Process,
    interval_sec: float = 30.0,
    alert_threshold_mb: float = 6000.0,
) -> None:
    """
    2026-05-13: engine/UI 자식 프로세스 + 손자(ffmpeg, go2rtc) RSS 모니터링.

    interval_sec 마다 INFO 로 합계 로그. alert_threshold_mb 초과 시 WARNING.
    psutil 미설치 시 graceful skip — 코드 동작에 영향 없음.
    """
    logger = logging.getLogger("launcher.mem")
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("[MEM] psutil 미설치 — 메모리 모니터링 skip")
        return

    while engine_proc.is_alive() or ui_proc.is_alive():
        try:
            samples: list[str] = []
            total_mb = 0.0
            for label, proc in (("engine", engine_proc), ("ui", ui_proc)):
                if not proc.is_alive() or proc.pid is None:
                    continue
                try:
                    p = psutil.Process(proc.pid)
                    rss_mb = p.memory_info().rss / (1024 * 1024)
                    children_mb = 0.0
                    for c in p.children(recursive=True):
                        try:
                            children_mb += c.memory_info().rss / (1024 * 1024)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    samples.append(
                        f"{label}={rss_mb:.0f}MB(+{children_mb:.0f}MB 자식)"
                    )
                    total_mb += rss_mb + children_mb
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            logger.info("[MEM] %s total=%.0fMB", " ".join(samples), total_mb)
            if total_mb > alert_threshold_mb:
                logger.warning(
                    "[MEM ALERT] 총 메모리 %.0fMB > %.0fMB 초과 ⚠",
                    total_mb, alert_threshold_mb,
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("[MEM] 샘플링 예외: %s", e)
        time.sleep(interval_sec)


def main() -> None:
    # 버전 정보
    try:
        from launcher_version import current_version, get_version_info
        vinfo = get_version_info()
        ver = vinfo.get("version", "unknown")
        built = vinfo.get("built_at", "?")
    except Exception:
        ver = "unknown"
        built = "?"

    print("=" * 60)
    print(f"  COURTVIEW Desktop  v{ver}")
    print(f"  build: {built}")
    print("=" * 60)
    print(f"  Engine: http://localhost:{ENGINE_PORT}")
    print(f"  UI:     http://localhost:{UI_PORT}")
    print("=" * 60)
    logger.info("COURTVIEW 시작 — 버전 %s (build %s)", ver, built)

    # 스플래시 + 워밍업 (필요 시)
    splash = _preflight_splash_and_warmup()

    # 엔진 서버를 자식 프로세스로 시작
    engine_proc = multiprocessing.Process(
        target=run_engine_server,
        name="courtview-engine",
        daemon=False,
    )
    engine_proc.start()

    # 잠시 대기 (엔진 초기화)
    time.sleep(3)

    # UI 서버를 자식 프로세스로 시작
    ui_proc = multiprocessing.Process(
        target=run_ui_server,
        name="courtview-ui",
        daemon=False,
    )
    ui_proc.start()

    # 잠시 대기 후 브라우저 자동 오픈
    time.sleep(2)
    try:
        webbrowser.open(f"http://localhost:{UI_PORT}/")
    except Exception:
        pass

    # 스플래시 닫기 (서버 기동 완료 후)
    if splash is not None:
        try:
            splash.close()
        except Exception:
            pass

    def _shutdown(signum, frame):
        logger.info("종료 신호 수신, 서버 정리 중...")
        for proc in (ui_proc, engine_proc):
            if proc.is_alive():
                proc.terminate()
        for proc in (ui_proc, engine_proc):
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # 2026-05-13: RAM 모니터링 스레드 — 30초마다 자식 프로세스 RSS 로그.
    # psutil 미설치 시 graceful skip. 6GB 초과 시 [MEM ALERT] 경고.
    mem_monitor = threading.Thread(
        target=_monitor_process_memory,
        args=(engine_proc, ui_proc, 30.0, 6000.0),
        daemon=True,
        name="mem-monitor",
    )
    mem_monitor.start()

    # 자식 프로세스 대기
    try:
        engine_proc.join()
        ui_proc.join()
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
