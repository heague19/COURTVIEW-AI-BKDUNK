# -*- coding: utf-8 -*-
"""
COURTVIEW - 런처 자식 프로세스 target 함수

launcher.py 가 multiprocessing.Process 로 이 모듈의 함수들을 target 으로 지정.
PyInstaller frozen 환경에서 자식 프로세스가 __main__ 을 reload 해도
이 모듈은 독립적으로 import 되어 target 함수를 찾을 수 있음.

(launcher.py 안에 함수를 두면 frozen 환경에서
 'AttributeError: Can\\'t get attribute ...' 발생)

작성자: SPOIN_COURTVIEW
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("launcher.workers")


ENGINE_HOST = "0.0.0.0"
ENGINE_PORT = 8000
UI_HOST = "0.0.0.0"
UI_PORT = 3000


# =============================================================================
# 경로 해석 (frozen 대응)
# =============================================================================
def _resolve_dirs() -> tuple[Path, Path]:
    """(BASE_DIR, EXE_DIR) 반환. launcher.py 와 동일 로직."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        exe = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
        exe = base
    return base, exe


# =============================================================================
# 엔진 서버
# =============================================================================
def run_engine_server() -> None:
    """COURTVIEW_DESK 엔진 API 서버 실행."""
    try:
        base, _ = _resolve_dirs()
        sys.path.insert(0, str(base))

        import uvicorn
        from api_server.main import app as engine_app

        logger.info("엔진 서버 시작: http://%s:%d", ENGINE_HOST, ENGINE_PORT)
        uvicorn.run(
            engine_app,
            host=ENGINE_HOST,
            port=ENGINE_PORT,
            log_level="info",
        )
    except Exception:
        logger.exception("엔진 서버 실행 실패")
        sys.exit(1)


# =============================================================================
# UI 서버
# =============================================================================
def run_ui_server() -> None:
    """COURTVIEW UI (Jinja2 + FastAPI) 실행."""
    try:
        base, _ = _resolve_dirs()

        # UI app.py 경로 결정 (frozen: courtview_ui/app.py, dev: ../COURTVIEW-UI/app.py)
        ui_candidates = [
            base / "courtview_ui" / "app.py",
            base.parent / "COURTVIEW-UI" / "app.py",
        ]
        app_path = None
        for p in ui_candidates:
            if p.exists():
                app_path = p
                break

        if app_path is None:
            logger.error("UI app.py 파일 없음. 후보: %s", ui_candidates)
            sys.exit(1)

        logger.info("UI 모듈 로드: %s", app_path)

        # app.py 디렉토리를 sys.path에 (templates/static 상대 경로 해결)
        sys.path.insert(0, str(app_path.parent))
        os.chdir(str(app_path.parent))

        import uvicorn
        spec = importlib.util.spec_from_file_location("courtview_ui_app", str(app_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ui_app = mod.app

        logger.info("UI 서버 시작: http://%s:%d", UI_HOST, UI_PORT)
        uvicorn.run(
            ui_app,
            host=UI_HOST,
            port=UI_PORT,
            log_level="info",
        )
    except Exception:
        logger.exception("UI 서버 실행 실패")
        sys.exit(1)


__all__ = [
    "run_engine_server",
    "run_ui_server",
    "ENGINE_HOST", "ENGINE_PORT",
    "UI_HOST", "UI_PORT",
]
