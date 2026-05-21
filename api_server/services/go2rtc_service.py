# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: go2rtc_service.py
설명: go2rtc 서브프로세스 + WebRTC 스트림 관리 (v0.3.0).

      배경:
        v0.2.x 까지 쓰던 `stream_mjpeg()` 파이프라인 (백엔드 ffmpeg 재인코딩 + MJPEG)
        은 ffmpeg 서브프로세스가 조용히 죽으면 프레임이 얼어붙는 고질적 문제가 있었다.
        watchdog 을 붙여도 복구 안정성이 낮아 경기 중 스냅샷 증상이 재발.

      해결 전략:
        브라우저 표시용 스트림을 **go2rtc** 에 전담시키고 <video> + WebRTC 로 수신.
        go2rtc 는 Home Assistant / Frigate 등 수만 대 배포에서 검증된 RTSP→WebRTC
        전용 서버로, 재연결·코덱 협상·네트워크 glitch 복구가 battle-tested.

      이 서비스는:
        1. go2rtc.exe 서브프로세스 수명 관리 (시작/종료/감시)
        2. REST API (PUT/DELETE /api/streams) 로 카메라 URL 등록/해제
        3. UI 용 WebRTC URL 반환 (http://host:1984/api/webrtc?src=<name>)

      AI 파이프라인(`VideoDecoder`)은 **변경 없음** — 기존 ffmpeg pipe 유지.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-24
버전: 1.0.0
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Final

_logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
DEFAULT_API_HOST: Final[str] = "127.0.0.1"
DEFAULT_API_PORT: Final[int] = 1984
DEFAULT_WEBRTC_PORT: Final[int] = 8555
STARTUP_WAIT_TIMEOUT_SEC: Final[float] = 10.0
API_REQUEST_TIMEOUT_SEC: Final[float] = 2.0


# =============================================================================
# Go2rtcService
# =============================================================================
class Go2rtcService:
    """go2rtc 서브프로세스 수명 + 스트림 관리."""

    __slots__ = (
        "_exe",
        "_config",
        "_api_base",
        "_proc",
        "_lock",
        # Plan A (2026-05-13): 헬스 가시화용 카운터.
        "_health_lock",
        "_add_attempts",
        "_add_successes",
        "_add_failures",
        "_last_failure_msg",
        "_last_failure_time",
    )

    def __init__(
        self,
        exe_path: Path,
        config_path: Path,
        api_host: str = DEFAULT_API_HOST,
        api_port: int = DEFAULT_API_PORT,
    ) -> None:
        self._exe = exe_path
        self._config = config_path
        self._api_base = f"http://{api_host}:{api_port}"
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        # Plan A: add_stream 호출 통계 — fallback 발생 시 UI/로그에서 확인.
        self._health_lock = threading.Lock()
        self._add_attempts: int = 0
        self._add_successes: int = 0
        self._add_failures: int = 0
        self._last_failure_msg: str | None = None
        self._last_failure_time: float | None = None

    # =========================================================================
    # 서브프로세스 수명
    # =========================================================================
    def start(self) -> bool:
        """go2rtc.exe 실행. 이미 실행 중이면 True 반환."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True

            if not self._exe.exists():
                _logger.error("go2rtc 실행 파일 없음: %s", self._exe)
                return False
            if not self._config.exists():
                _logger.error("go2rtc 설정 파일 없음: %s", self._config)
                return False

            creationflags = 0
            if sys.platform == "win32":
                creationflags = 0x08000000  # CREATE_NO_WINDOW

            # v0.3.3: imageio_ffmpeg 의 ffmpeg.exe 를 PATH 에 주입.
            # go2rtc 가 `ffmpeg:rtsp://...` source 처리 시 PATH 에서 ffmpeg 검색.
            # 저가 IPCam 은 go2rtc 의 native Go RTSP client 와 호환 안 되는 경우가
            # 많아 ffmpeg 경유가 안정적. AI 백엔드와 동일한 ffmpeg 바이너리 사용.
            #
            # v0.5.7: 시스템에 ffmpeg 가 이미 있으면 그걸 우선 사용. 번들 ffmpeg 는
            # fallback. v0.5.5 → v0.5.6 회귀 사례: imageio_ffmpeg 신규 번들로 인해
            # PATH 맨 앞에 v7.1 ffmpeg 가 박혔는데, 노트북에 설치된 v8.0 system
            # ffmpeg 로 정상 동작하던 RTSP 가 v7.1 + 환경 차이로 silent fail →
            # go2rtc add_stream 등록 실패 → cam_x DESCRIBE 404 무한 재시도.
            import os as _os
            import shutil as _shutil
            env = _os.environ.copy()
            system_ffmpeg = _shutil.which("ffmpeg")
            if system_ffmpeg:
                _logger.info("go2rtc: 시스템 ffmpeg 사용 → %s", system_ffmpeg)
            else:
                try:
                    from imageio_ffmpeg import get_ffmpeg_exe
                    ffmpeg_exe = get_ffmpeg_exe()
                    ffmpeg_dir = str(Path(ffmpeg_exe).parent)
                    # go2rtc 는 'ffmpeg' 이름을 찾으므로 별칭 (.exe → ffmpeg.exe) 필요.
                    ffmpeg_alias = Path(ffmpeg_dir) / "ffmpeg.exe"
                    if not ffmpeg_alias.exists():
                        try:
                            _shutil.copy2(ffmpeg_exe, str(ffmpeg_alias))
                        except OSError as e:
                            _logger.warning("ffmpeg.exe alias 생성 실패 (계속 진행): %s", e)
                    env["PATH"] = ffmpeg_dir + _os.pathsep + env.get("PATH", "")
                    _logger.info("go2rtc: 시스템 ffmpeg 미발견 → 번들 ffmpeg fallback: %s", ffmpeg_dir)
                except Exception:
                    _logger.warning("imageio_ffmpeg 경로 해결 실패 — go2rtc 가 시스템 PATH 의 ffmpeg 사용", exc_info=True)

            # 2026-05-13: go2rtc stderr/stdout 을 파일로 저장 (8대 add_stream 400 Bad Request
            # 원인 파악용). 파일 위치: %APPDATA%\COURTVIEW\logs\go2rtc.log.
            # 새 launcher 시작 시 파일 truncate (이전 세션 잔재 제거 — append 가 아니라 write).
            try:
                from infrastructure.storage.paths import app_data_dir
                go2rtc_log_path = app_data_dir() / "logs" / "go2rtc.log"
                go2rtc_log_path.parent.mkdir(parents=True, exist_ok=True)
                go2rtc_log_fp = open(go2rtc_log_path, "wb")  # truncate
                _logger.info("go2rtc stderr/stdout → %s", go2rtc_log_path)
            except Exception:
                _logger.exception("go2rtc 로그 파일 생성 실패 — DEVNULL fallback")
                go2rtc_log_fp = None  # type: ignore[assignment]

            try:
                self._proc = subprocess.Popen(
                    [str(self._exe), "--config", str(self._config)],
                    stdout=go2rtc_log_fp if go2rtc_log_fp else subprocess.DEVNULL,
                    stderr=subprocess.STDOUT if go2rtc_log_fp else subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags,
                    env=env,
                )
            except OSError as e:
                _logger.exception("go2rtc 시작 실패: %s", e)
                return False

            _logger.info(
                "go2rtc 시작: pid=%d exe=%s config=%s",
                self._proc.pid, self._exe, self._config,
            )

        return self.wait_ready(timeout_sec=STARTUP_WAIT_TIMEOUT_SEC)

    def stop(self) -> None:
        """go2rtc 서브프로세스 종료."""
        with self._lock:
            proc = self._proc
            self._proc = None

        if proc is None:
            return
        if proc.poll() is not None:
            return  # 이미 종료됨

        try:
            proc.terminate()
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
        except OSError:
            pass
        _logger.info("go2rtc 종료 완료")

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def wait_ready(self, timeout_sec: float = STARTUP_WAIT_TIMEOUT_SEC) -> bool:
        """
        /api 엔드포인트 응답 확인. startup race condition 방지 — stream
        등록 이전에 API 서버가 listen 상태인지 확인한다.
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if not self.is_running():
                return False
            try:
                with urllib.request.urlopen(
                    f"{self._api_base}/api", timeout=0.5,
                ) as resp:
                    if resp.status == 200:
                        _logger.info("go2rtc API ready")
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.2)
        _logger.error("go2rtc API 응답 없음 (%.1fs)", timeout_sec)
        return False

    # =========================================================================
    # Stream 관리 (REST API 래퍼)
    # =========================================================================
    def add_stream(self, name: str, src: str) -> bool:
        """
        카메라 RTSP URL 을 go2rtc 에 등록.

        go2rtc 가 실제 RTSP 연결·디코딩·재연결 전부 책임. 브라우저는
        `webrtc_url(name)` 를 <video> 로 재생하면 native H.264 로 수신.

        v0.3.3: rtsp:// URL 은 자동으로 `ffmpeg:` prefix 부착.
        저가 IPCam 은 go2rtc 의 native Go RTSP 와 호환 안 되는 경우 많아
        ffmpeg 경유가 안정적. video=copy 로 재인코딩 부담도 없음.

        Args:
            name: 스트림 이름 (ex. "cam_0")
            src:  카메라 RTSP URL (rtsp://host/path)

        Returns:
            등록 성공 여부
        """
        if src.startswith("rtsp://") or src.startswith("rtsps://"):
            # v0.3.4: 저가 IPCam 은 H.265 + G.722 출력하는 경우 많은데 브라우저
            # WebRTC 는 H.264/VP8/VP9/AV1 + OPUS/PCMU 만 지원. 무조건 H.264 로
            # 트랜스코드해 호환성 확보. audio 는 드롭 (체육관 무성).
            #
            # v0.5.7.3: 빈 `#audio=` 는 go2rtc 1.9.14 가 400 Bad Request 로 거절
            # (codec 이름 필수 — `#audio=copy` 같은 형태). 옵션 자체를 빼면
            # go2rtc 가 카메라가 audio 를 보낼 때만 자동 협상 → audio 없으면 그대로
            # 드롭, 있으면 passthrough.
            go2rtc_src = f"ffmpeg:{src}#video=h264"
        else:
            go2rtc_src = src
        qs = urllib.parse.urlencode({"name": name, "src": go2rtc_src})
        url = f"{self._api_base}/api/streams?{qs}"
        req = urllib.request.Request(url, method="PUT")
        with self._health_lock:
            self._add_attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=API_REQUEST_TIMEOUT_SEC) as resp:
                ok = resp.status in (200, 201, 204)
                if ok:
                    _logger.info("go2rtc add_stream: %s <- %s", name, src)
                    with self._health_lock:
                        self._add_successes += 1
                else:
                    msg = f"status={resp.status}"
                    _logger.warning("go2rtc add_stream 실패: %s %s", name, msg)
                    with self._health_lock:
                        self._add_failures += 1
                        self._last_failure_msg = f"{name}: {msg}"
                        self._last_failure_time = time.time()
                return ok
        except urllib.error.HTTPError as e:
            # 2026-05-13: HTTP 400 등 응답의 body 에 go2rtc 가 진짜 거절 사유를 적음.
            # 이전엔 e.read() 안 해서 사유가 사라졌음. body 를 읽어 launcher 콘솔에 출력.
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            _logger.warning(
                "go2rtc add_stream 실패: %s HTTP %d %s body=%r src=%s",
                name, e.code, e.reason, body, go2rtc_src,
            )
            with self._health_lock:
                self._add_failures += 1
                self._last_failure_msg = f"{name}: HTTP {e.code} {body[:200]}"
                self._last_failure_time = time.time()
            return False
        except (urllib.error.URLError, OSError) as e:
            _logger.warning("go2rtc add_stream 예외: %s (%s)", name, e)
            with self._health_lock:
                self._add_failures += 1
                self._last_failure_msg = f"{name}: {e}"
                self._last_failure_time = time.time()
            return False

    def remove_stream(self, name: str) -> bool:
        """스트림 제거."""
        qs = urllib.parse.urlencode({"src": name})
        url = f"{self._api_base}/api/streams?{qs}"
        req = urllib.request.Request(url, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=API_REQUEST_TIMEOUT_SEC) as resp:
                return resp.status in (200, 204)
        except (urllib.error.URLError, OSError) as e:
            _logger.debug("go2rtc remove_stream 예외: %s (%s)", name, e)
            return False

    # =========================================================================
    # Plan A (2026-05-13): 헬스 가시화
    # =========================================================================
    def get_health(self) -> dict:
        """
        go2rtc 현재 상태 1회 스냅샷.

        UI/launcher 가 fallback 발생 여부를 즉시 판별할 수 있게 만든다.
        api_ready 는 매 호출마다 짧은 HTTP HEAD 로 확인 — 캐싱 안 함.
        """
        running = self.is_running()
        api_ready = False
        if running:
            try:
                with urllib.request.urlopen(
                    f"{self._api_base}/api", timeout=0.3,
                ) as resp:
                    api_ready = (resp.status == 200)
            except (urllib.error.URLError, OSError):
                api_ready = False

        with self._health_lock:
            return {
                "running": running,
                "api_ready": api_ready,
                "api_base": self._api_base,
                "add_attempts": self._add_attempts,
                "add_successes": self._add_successes,
                "add_failures": self._add_failures,
                "last_failure_msg": self._last_failure_msg,
                "last_failure_time": self._last_failure_time,
            }

    def webrtc_url(self, name: str) -> str:
        """
        UI <video> 태그용 WebRTC WHEP endpoint.
        브라우저 JS 가 이 URL 에 SDP offer POST 하면 go2rtc 가 answer 반환.
        """
        return f"{self._api_base}/api/webrtc?src={urllib.parse.quote(name)}"


__all__ = ["Go2rtcService"]
__version__ = "1.0.0"
