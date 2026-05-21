# -*- coding: utf-8 -*-
"""GameOrchestrator 를 BATCH/REPLAY 모드로 가동 + 진행률 콜백.

전제: tools/replay/multi_file_ingestion.prepare_session 가 work_dir/cam_<id>.mp4 를
이미 만들어 둔 상태. 이 파일들을 source_urls dict 로 GameOrchestrator 에 공급.

분석 종료 후 산출물:
    %APPDATA%/COURTVIEW/games/<game_id>/        — gamesheet, report 등 (ExportService)
    <session_dir>/clips/<event_id>.mp4          — 하이라이트 클립 (HighlightClipService)
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from typing import Callable

from tools.replay.multi_file_ingestion import PreparedSession

_logger = logging.getLogger(__name__)


@dataclass
class ReplayResult:
    success: bool = False
    game_id: str = ""
    output_dir: Path | None = None
    highlights_dir: Path | None = None
    error: str = ""
    elapsed_sec: float = 0.0
    cameras: list[str] = field(default_factory=list)


ProgressCallback = Callable[[str, float], None]
"""(message, percent_0_to_100) — 분석 단계별 진행률."""


# =============================================================================
def run_replay(
    prepared: PreparedSession,
    home_team: str,
    away_team: str,
    progress: ProgressCallback | None = None,
    stop_event: Event | None = None,
) -> ReplayResult:
    """REPLAY 분석 실행 (블로킹).

    GUI 는 이 함수를 별도 스레드에서 호출하고 progress 콜백으로 진행률 반영.
    """
    started = time.time()
    if not prepared.cameras:
        return ReplayResult(success=False, error="합쳐진 카메라가 없습니다")

    if stop_event is None:
        stop_event = Event()

    _emit(progress, "GameOrchestrator 초기화 중…", 5.0)

    # late import — PyQt6 없는 환경/circular 방지
    from engine.config import EngineConfig
    from engine.orchestrator.game_orchestrator import GameOrchestrator

    cfg = EngineConfig()
    # BATCH/REPLAY 인지 명시 — 본 모듈은 REPLAY 모드 의도. 카메라 수도 실제 사용분으로.
    try:
        cfg.camera.num_cameras = len(prepared.cameras)
    except Exception:
        pass

    orch = GameOrchestrator.build_from_config(cfg)
    game_id = f"replay_{uuid.uuid4().hex[:8]}"
    # __slots__ 에 _game_id 없을 수 있음 — silent (game_service 와 동일 패턴)
    try:
        orch._game_id = game_id
    except AttributeError:
        _logger.debug("orch._game_id 슬롯 없음 — 기본값으로 진행")

    # source_urls — cam_id → 합쳐진 mp4 의 file:// URL 형식 또는 그냥 path
    source_urls: dict[str, str] = {
        cam.cam_id: str(cam.mp4_path) for cam in prepared.cameras
    }

    _emit(progress, "분석 파이프라인 시작 (모델 로드 + 캘리 적용)…", 10.0)

    started_ok = orch.start_game(source_urls=source_urls)
    if not started_ok:
        return ReplayResult(
            success=False, game_id=getattr(orch, "_game_id", game_id),
            error="orchestrator.start_game 실패 (로그 확인)",
        )

    _emit(progress, "프레임 처리 중…", 20.0)

    # 메인 루프 모니터링 — orchestrator.is_running 가 False 가 될 때까지 대기
    # 진행률은 시간 기반 추정 (정확한 frame_count 는 orchestrator 내부 stat 에서 가능하면 사용)
    try:
        last_pct = 20.0
        # 추정 길이 (seconds) = 카메라 mp4 중 가장 짧은 것
        est_total_sec = _estimate_session_seconds(prepared)
        while orch.is_running and not stop_event.is_set():
            elapsed = time.time() - started
            # 80% 까지 시간 기반으로 채우고 남은 20% 는 마무리 단계
            if est_total_sec > 0:
                pct = 20.0 + min(60.0, (elapsed / est_total_sec) * 60.0)
            else:
                pct = min(80.0, last_pct + 0.5)
            if pct - last_pct > 0.5:
                _emit(progress, f"프레임 처리 중… ({elapsed:.0f}s 경과)", pct)
                last_pct = pct
            time.sleep(2.0)

        if stop_event.is_set():
            _emit(progress, "사용자 중지 요청 — 정리 중…", 85.0)
            orch.stop_game()

        _emit(progress, "산출물 생성 중 (기록지/리포트)…", 90.0)
        # stop_game 호출 (이미 자연 종료됐어도 안전)
        try:
            orch.stop_game()
        except Exception:
            pass
    except Exception as exc:
        _logger.exception("REPLAY 실행 중 예외")
        try:
            orch.stop_game()
        except Exception:
            pass
        return ReplayResult(
            success=False, game_id=getattr(orch, "_game_id", game_id), error=str(exc),
        )

    # 산출물 위치
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "COURTVIEW" if appdata else Path.home() / ".courtview"
    output_dir = base / "games" / getattr(orch, "_game_id", game_id)

    elapsed = time.time() - started
    _emit(progress, "완료", 100.0)
    return ReplayResult(
        success=True,
        game_id=getattr(orch, "_game_id", game_id),
        output_dir=output_dir if output_dir.exists() else None,
        highlights_dir=_find_highlights_dir(output_dir),
        elapsed_sec=elapsed,
        cameras=[c.cam_id for c in prepared.cameras],
    )


# =============================================================================
def _emit(cb: ProgressCallback | None, msg: str, pct: float) -> None:
    if cb is None:
        return
    try:
        cb(msg, pct)
    except Exception:
        pass


def _estimate_session_seconds(prepared: PreparedSession) -> float:
    """가장 짧은 카메라 mp4 의 길이를 ffprobe 로 추정 (실패 시 0)."""
    import subprocess
    import shutil

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        try:
            import imageio_ffmpeg
            # imageio_ffmpeg 는 ffprobe 별도 없음 — ffmpeg 로 우회
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            return _duration_via_ffmpeg(ffmpeg_exe, prepared.cameras[0].mp4_path)
        except Exception:
            return 0.0

    durations: list[float] = []
    for cam in prepared.cameras:
        try:
            res = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(cam.mp4_path)],
                capture_output=True, timeout=15.0,
            )
            if res.returncode == 0:
                d = float((res.stdout or b"").decode("utf-8").strip() or "0")
                if d > 0:
                    durations.append(d)
        except Exception:
            continue
    return min(durations) if durations else 0.0


def _duration_via_ffmpeg(ffmpeg: str, path: Path) -> float:
    """ffmpeg -i 출력에서 Duration 파싱 (rough fallback)."""
    import re
    import subprocess
    try:
        res = subprocess.run(
            [ffmpeg, "-i", str(path)], capture_output=True, timeout=15.0,
        )
        out = (res.stderr or b"").decode("utf-8", errors="replace")
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mi * 60 + s
    except Exception:
        pass
    return 0.0


def _find_highlights_dir(output_dir: Path | None) -> Path | None:
    if output_dir is None:
        return None
    for candidate in (output_dir / "clips", output_dir / "highlights"):
        if candidate.exists():
            return candidate
    return None
