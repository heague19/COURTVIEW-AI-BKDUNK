# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: video_decoder.py
설명: 비디오 디코딩 엔진
      - VideoDecoder: OpenCV 기반 비디오 디코딩 (순차/랜덤 접근)
      - DecoderStats: 디코딩 통계 (프레임 수, 드롭, 시간)
      - DecoderState: 디코더 상태 Enum (IDLE → OPENING → DECODING → PAUSED → CLOSED → ERROR)
      - 메모리 안전 (DECODE_BUFFER_SIZE 제한, 자동 리소스 해제)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import logging
import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Final, Generator

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.video_constants import (
    ANALYSIS_NORMALIZED_RESOLUTION,
    DECODE_BUFFER_SIZE,
    DEFAULT_FPS,
    MAX_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
)
from shared.dto.video_dto import (
    FrameData,
    FrameStatus,
    VideoFileMetadata,
    VideoResolution,
)


_logger = logging.getLogger(__name__)


# =============================================================================
# 상수 정의
# =============================================================================

# Plan B (2026-05-13): ffmpeg HW 디코딩 모드.
#   - "d3d11va": Windows 디폴트, Intel/NVIDIA/AMD 호환 (기본값)
#   - "cuda":    NVIDIA 전용, NVDEC 사용 (약간 더 빠름)
#   - "off":     SW 디코딩 (롤백 안전망 — 기존 동작과 동일)
# 환경변수 COURTVIEW_HWACCEL 로 override.
_HWACCEL_VALID: Final[frozenset[str]] = frozenset({"d3d11va", "cuda", "off"})
_HWACCEL_MODE: str = os.environ.get("COURTVIEW_HWACCEL", "d3d11va").strip().lower()
if _HWACCEL_MODE not in _HWACCEL_VALID:
    _logger.warning(
        "COURTVIEW_HWACCEL=%r 인식 불가 — 'off' 로 강제 (유효값: %s)",
        _HWACCEL_MODE, sorted(_HWACCEL_VALID),
    )
    _HWACCEL_MODE = "off"

# 디코더 내부 버퍼 최대 크기
DECODER_BUFFER_MAX: Final[int] = DECODE_BUFFER_SIZE

# RTSP 연결 재시도 설정 (Phase 17 S1)
RTSP_OPEN_MAX_ATTEMPTS: Final[int] = 3       # 최대 시도 횟수
RTSP_OPEN_BACKOFF_BASE_SEC: Final[float] = 0.5  # 초기 백오프 (exponential: 0.5, 1.0, 2.0)
RTSP_OPEN_TIMEOUT_MS: Final[int] = 5000      # 단일 open 시도 timeout (ms)

# v0.2.2 — probe rate limit (카메라 펌웨어 보호)
# 배경: 저가 IPCam H80 은 세션 슬롯 4~8개 한계. probe/connect 가 반복되면
#       FIN 없이 dangling session 이 쌓여 카메라가 새 연결 거부 상태로 진입.
#       24.13 에서 이 패턴으로 펌웨어 상태 꼬여 15분 cold boot 복구 필요했음.
_PROBE_RATE_LIMIT_WINDOW_SEC: Final[float] = 600.0   # 10분
_PROBE_RATE_LIMIT_MAX_CALLS: Final[int] = 5          # 동일 host 에 5회 까지
_probe_history: dict[str, deque[float]] = {}
_probe_history_lock = threading.Lock()


def _check_probe_rate_limit(host: str) -> tuple[bool, float]:
    """
    호스트별 probe rate limit 체크 (v0.2.2).

    Returns:
        (allowed, wait_sec) — allowed=False 면 wait_sec 만큼 남은 쿨다운
    """
    now_mono = time.monotonic()
    with _probe_history_lock:
        hist = _probe_history.setdefault(host, deque(maxlen=_PROBE_RATE_LIMIT_MAX_CALLS * 2))
        cutoff = now_mono - _PROBE_RATE_LIMIT_WINDOW_SEC
        while hist and hist[0] < cutoff:
            hist.popleft()
        if len(hist) >= _PROBE_RATE_LIMIT_MAX_CALLS:
            return False, _PROBE_RATE_LIMIT_WINDOW_SEC - (now_mono - hist[0])
        hist.append(now_mono)
        return True, 0.0


def probe_rtsp(url: str, timeout_sec: float = 3.0, _bypass_rate_limit: bool = False) -> dict[str, object]:
    """
    RTSP URL 사전 검증 — TCP 연결 + DESCRIBE 요청 (Phase 17 S2).

    OpenCV/FFmpeg 호출 전에 빠르게 연결 가능성 확인.
    THE RECORD의 `EngineRtsp.cs:176-230` 패턴을 Python으로 포팅.

    Args:
        url: rtsp://user:pass@host:port/path
        timeout_sec: 소켓 타임아웃

    Returns:
        {
            "reachable": bool,           # TCP 연결 성공 여부
            "rtsp_ok": bool,             # DESCRIBE 200 OK 여부
            "status_code": int | None,
            "server": str,               # 응답 Server 헤더
            "elapsed_ms": float,
            "error": str | None,
        }
    """
    import socket
    from urllib.parse import urlparse

    result: dict[str, object] = {
        "reachable": False,
        "rtsp_ok": False,
        "status_code": None,
        "server": "",
        "elapsed_ms": 0.0,
        "error": None,
    }

    try:
        parsed = urlparse(url)
    except Exception as e:
        result["error"] = f"URL 파싱 실패: {e}"
        return result

    if parsed.scheme not in ("rtsp", "rtsps"):
        result["error"] = f"지원 안 하는 스킴: {parsed.scheme}"
        return result

    host = parsed.hostname or ""
    port = parsed.port or (322 if parsed.scheme == "rtsps" else 554)

    if not host:
        result["error"] = "호스트 없음"
        return result

    # v0.2.2 — rate limit: 동일 host 에 window 내 MAX_CALLS 초과 시 거부
    # (카메라 펌웨어 세션 슬롯 보호 + dangling session 축적 방지)
    # probe_rtsp_paths 는 자체에서 1회만 체크하고 내부 호출은 bypass.
    if not _bypass_rate_limit:
        allowed, wait_sec = _check_probe_rate_limit(host)
        if not allowed:
            result["error"] = (
                f"rate limit: {host} 에 {_PROBE_RATE_LIMIT_WINDOW_SEC:.0f}초 내 "
                f"{_PROBE_RATE_LIMIT_MAX_CALLS}회 초과 (남은 쿨다운 {wait_sec:.0f}s)"
            )
            _logger.warning(result["error"])
            return result

    t0 = time.perf_counter()
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout_sec)
        result["reachable"] = True

        # RTSP DESCRIBE 요청
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request = (
            f"DESCRIBE {url} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"Accept: application/sdp\r\n"
            f"User-Agent: CourtView/1.0\r\n"
            f"\r\n"
        ).encode("ascii", errors="replace")

        sock.settimeout(timeout_sec)
        sock.sendall(request)

        # 응답 헤더 읽기 (최대 2KB)
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 2048:
            chunk = sock.recv(512)
            if not chunk:
                break
            data += chunk

        # 상태 코드 파싱
        first_line = data.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        # "RTSP/1.0 200 OK"
        parts = first_line.split(" ", 2)
        if len(parts) >= 2 and parts[1].isdigit():
            code = int(parts[1])
            result["status_code"] = code
            # 200 OK 또는 401 Unauthorized(인증 요구, 서버는 살아있음) 전부 OK
            result["rtsp_ok"] = code in (200, 401)

        # Server 헤더 파싱
        for line in data.split(b"\r\n"):
            low = line.lower()
            if low.startswith(b"server:"):
                result["server"] = line.split(b":", 1)[1].strip().decode("ascii", errors="replace")
                break

    except socket.timeout:
        result["error"] = f"연결 타임아웃 ({timeout_sec}s)"
    except socket.gaierror as e:
        result["error"] = f"DNS 오류: {e}"
    except OSError as e:
        result["error"] = f"연결 오류: {e}"
    except Exception as e:
        result["error"] = f"예외: {e}"
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    return result


# =============================================================================
# RTSP 경로 자동 탐지 (Phase 18 — v0.1.4)
# =============================================================================
# IP 카메라 벤더별 RTSP path 후보.
# priority:
#   0  = sub-stream (저해상도, 다중 카메라 현장용 최우선)
#   1  = 기타 sub-stream 계열
#   2  = main-stream (고해상도, fallback)
#   3  = generic / 미상 벤더
_RTSP_PATH_CANDIDATES: list[tuple[str, int]] = [
    # (path, priority) — priority 낮을수록 선호
    # --- sub-stream (저해상도, 지연 짧음, 다중 카메라 동시 처리 부담 ↓) ---
    ("/11", 0),                                        # IPCam H80 / 저가 중국산 sub
    ("/stream2", 1),                                   # Generic sub
    ("/Streaming/Channels/102", 1),                    # Hikvision sub
    ("/cam/realmonitor?channel=1&subtype=1", 1),       # Dahua sub
    ("/live/ch00_1", 1),                               # 일부 벤더 sub
    ("/videoSub", 1),                                  # Foscam sub
    # --- main-stream (고해상도, fallback) ---
    ("/12", 2),                                        # IPCam H80 main
    ("/stream1", 2),                                   # Generic main
    ("/Streaming/Channels/101", 2),                    # Hikvision main
    ("/cam/realmonitor?channel=1&subtype=0", 2),       # Dahua main
    ("/live/ch00_0", 2),                               # 일부 벤더 main
    ("/videoMain", 2),                                 # Foscam main
    # --- 마지막 수단 ---
    ("/", 3),
    ("/live", 3),
    ("/media", 3),
]


def probe_rtsp_paths(
    host: str,
    port: int = 554,
    timeout_sec: float = 0.6,
    username: str = "",
    password: str = "",
) -> list[dict[str, object]]:
    """
    RTSP 카메라의 재생 가능한 path 를 자동 탐지한다.

    `_RTSP_PATH_CANDIDATES` 의 후보들을 **모두 병렬** probe (DESCRIBE 200/401) 해서
    응답하는 URL 만 반환. **sub-stream 우선** 정렬 — AI 분석 + 다중 카메라 환경에서
    대역폭·디코딩 부담을 절반 이하로 줄인다 (예: 4K main 대신 640×480 sub).

    배경: 기존 discover 는 `/stream1` 로 하드코딩했는데 IPCam H80 같은 카메라는
          `/stream1` 에 404 반환 or 연결은 되지만 프레임이 안 오는 '유령 연결'.
          사용자가 수동으로 `/11`, `/12` 같은 벤더 고유 경로를 알아야 했음.
          이 함수로 노트북이 알아서 찾아준다.

    Args:
        host, port: 카메라 주소 (554 포트 이미 open 확인된 것)
        timeout_sec: per-path probe timeout (default 0.6s — 15개 병렬이라 총 ~0.6s)
        username/password: 인증 있으면 URL 에 포함

    Returns:
        [{path, url, priority, rtsp_ok, status_code, elapsed_ms, server}, ...]
        응답 성공 것만, priority 오름차순 (sub-stream 우선). 빈 리스트면 RTSP
        서비스는 열려있으나 유효한 경로 없음.
    """
    from concurrent.futures import ThreadPoolExecutor

    # v0.2.2 — 경로 탐지 사이클 전체를 rate limit 의 1회로 계산
    # (16개 path 병렬 probe 가 각각 1회로 카운트되면 1번 탐지로 전체 쿼터 소진)
    allowed, wait_sec = _check_probe_rate_limit(host)
    if not allowed:
        _logger.warning(
            "probe_rtsp_paths rate limit: %s (남은 쿨다운 %.0fs)", host, wait_sec,
        )
        return []

    auth = ""
    if username:
        auth = f"{username}:{password}@" if password else f"{username}@"

    def _test(item: tuple[str, int]) -> dict[str, object] | None:
        path, priority = item
        url = f"rtsp://{auth}{host}:{port}{path}"
        # _bypass_rate_limit=True — 이 사이클은 상위에서 이미 1회 카운트됨
        r = probe_rtsp(url, timeout_sec=timeout_sec, _bypass_rate_limit=True)
        if r.get("rtsp_ok"):
            return {
                "path": path,
                "url": url,
                "priority": priority,
                "status_code": r.get("status_code"),
                "elapsed_ms": r.get("elapsed_ms"),
                "server": r.get("server", ""),
            }
        return None

    with ThreadPoolExecutor(max_workers=len(_RTSP_PATH_CANDIDATES),
                             thread_name_prefix="rtsp-paths") as pool:
        futures = [pool.submit(_test, it) for it in _RTSP_PATH_CANDIDATES]
        results = [f.result() for f in futures]

    found = [r for r in results if r is not None]
    found.sort(key=lambda x: (x["priority"], x.get("elapsed_ms", 9999)))
    return found


def _open_rtsp_with_retry(url: str) -> cv2.VideoCapture | None:
    """
    RTSP URL을 TCP 전송 + 재시도 로직으로 연결.

    THE RECORD의 LibVLC `--rtsp-tcp` 패턴을 Python/OpenCV로 포팅.
    TCP 강제로 패킷 손실 자동 복구, 3회 exponential backoff로 일시적 장애 흡수.

    Args:
        url: RTSP URL (rtsp:// 또는 rtsps://)

    Returns:
        연결된 cv2.VideoCapture 또는 None (실패 시)
    """
    import os

    # FFmpeg capture options: TCP 전송 + 타임아웃 + 저지연 버퍼
    # stimeout: socket timeout in microseconds (5초)
    # rw_timeout: read/write timeout in microseconds (3초)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;tcp"              # TCP 강제 (UDP 손실 방지)
        f"|stimeout;{RTSP_OPEN_TIMEOUT_MS * 1000}"  # socket timeout (μs)
        f"|rw_timeout;3000000"             # read/write timeout (μs, 3초)
        f"|fflags;nobuffer"                # 버퍼 최소화
        f"|flags;low_delay"                # 저지연 모드
        f"|max_delay;500000"               # max demux delay 500ms
        f"|reorder_queue_size;0"           # 재정렬 큐 0
    )

    for attempt in range(1, RTSP_OPEN_MAX_ATTEMPTS + 1):
        t0 = time.perf_counter()
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        elapsed = (time.perf_counter() - t0) * 1000
        if cap.isOpened():
            _logger.info(
                "RTSP 연결 성공: %s (attempt %d/%d, %.0fms)",
                url, attempt, RTSP_OPEN_MAX_ATTEMPTS, elapsed,
            )
            return cap

        cap.release()
        _logger.warning(
            "RTSP 연결 실패: %s (attempt %d/%d, %.0fms)",
            url, attempt, RTSP_OPEN_MAX_ATTEMPTS, elapsed,
        )

        if attempt < RTSP_OPEN_MAX_ATTEMPTS:
            # exponential backoff: 0.5s, 1.0s, 2.0s
            backoff = RTSP_OPEN_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
            time.sleep(backoff)

    _logger.error("RTSP 연결 최종 실패: %s (%d회 시도)", url, RTSP_OPEN_MAX_ATTEMPTS)
    return None


# =============================================================================
# DecoderState: 디코더 상태
# =============================================================================

@unique
class DecoderState(Enum):
    """비디오 디코더 상태."""

    IDLE = "idle"
    OPENING = "opening"
    DECODING = "decoding"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"

    @property
    def is_active(self) -> bool:
        """디코딩 가능 상태 여부."""
        return self in (DecoderState.DECODING, DecoderState.PAUSED)

    @property
    def can_open(self) -> bool:
        """열기 가능 여부."""
        return self in (DecoderState.IDLE, DecoderState.CLOSED, DecoderState.ERROR)


# =============================================================================
# DecoderStats: 디코딩 통계
# =============================================================================

@dataclass(slots=True)
class DecoderStats:
    """디코딩 통계.

    Attributes:
        frames_decoded: 성공적으로 디코딩된 프레임 수
        frames_failed: 디코딩 실패 프레임 수
        bytes_read: 읽은 바이트 수 (추정)
        decode_time_sec: 총 디코딩 소요 시간
        seek_count: seek 횟수
        last_frame_time: 마지막 성공 프레임 타임스탬프 (Phase 17 S2)
        consecutive_failures: 연속 실패 횟수 (Phase 17 S2)
    """

    frames_decoded: int = 0
    frames_failed: int = 0
    bytes_read: int = 0
    decode_time_sec: float = 0.0
    seek_count: int = 0
    last_frame_time: float = 0.0
    consecutive_failures: int = 0

    @property
    def total_frames(self) -> int:
        """처리된 총 프레임 수."""
        return self.frames_decoded + self.frames_failed

    @property
    def success_rate(self) -> float:
        """디코딩 성공률."""
        if self.total_frames == 0:
            return 0.0
        return self.frames_decoded / self.total_frames

    @property
    def avg_decode_ms(self) -> float:
        """프레임당 평균 디코딩 시간 (ms)."""
        if self.frames_decoded == 0:
            return 0.0
        return (self.decode_time_sec / self.frames_decoded) * 1000.0

    def __repr__(self) -> str:
        return (
            f"DecoderStats(decoded={self.frames_decoded}, "
            f"failed={self.frames_failed}, "
            f"rate={self.success_rate:.2%}, "
            f"avg={self.avg_decode_ms:.1f}ms)"
        )


# =============================================================================
# VideoDecoder: 비디오 디코딩 엔진
# =============================================================================

class VideoDecoder:
    """OpenCV 기반 비디오 디코딩 엔진.

    순차 디코딩과 랜덤 접근(seek)을 지원하며,
    FrameData DTO로 프레임을 출력한다.

    사용 예시::

        decoder = VideoDecoder()
        decoder.open("game.mp4")
        for frame_data in decoder.decode_sequential(max_frames=100):
            process(frame_data)
        decoder.close()

    Context Manager::

        with VideoDecoder() as decoder:
            decoder.open("game.mp4")
            frame = decoder.decode_frame(42)
    """

    __slots__ = (
        "_lock",
        "_cap",
        "_state",
        "_file_path",
        "_metadata",
        "_stats",
        "_current_index",
        "_camera_id",
        # Phase 17 S4: 프레임 브로커 (최신 프레임 캐시)
        "_latest_frame",
        "_latest_jpeg",
        "_latest_jpeg_quality",
        # Phase 18 (v0.1.5): RTSP 배경 리더 스레드 — OpenCV 내부 버퍼 지연 제거
        "_is_rtsp",
        "_reader_thread",
        "_reader_stop",
        "_new_frame_event",
        "_reader_frame_counter",
        # Phase 19 (v0.2.0): RTSP = ffmpeg subprocess pipe (THE RECORD 수준 지연)
        "_ffmpeg_proc",
        "_ffmpeg_width",
        "_ffmpeg_height",
        "_ffmpeg_stderr_fp",
    )

    def __init__(self, camera_id: str | None = None) -> None:
        self._lock = threading.RLock()
        self._cap: cv2.VideoCapture | None = None
        self._state = DecoderState.IDLE
        self._file_path: str = ""
        self._metadata: VideoFileMetadata | None = None
        self._stats = DecoderStats()
        self._current_index: int = 0
        self._camera_id = camera_id
        # Phase 17 S4: 최신 프레임 공유 캐시 (MJPEG 스트리밍용)
        self._latest_frame: NDArray[np.uint8] | None = None
        self._latest_jpeg: bytes | None = None
        self._latest_jpeg_quality: int = 0
        # Phase 18 (v0.1.5): RTSP 배경 리더 (cap.read() 를 OpenCV 내부 버퍼
        # 에서 계속 꺼내 drop — decode_next() 가 언제 불려도 지연 누적 없이
        # 최신 프레임 반환. 실질 latency ~0.3 s 목표.
        self._is_rtsp: bool = False
        self._reader_thread: threading.Thread | None = None
        self._reader_stop: threading.Event = threading.Event()
        self._new_frame_event: threading.Event = threading.Event()
        self._reader_frame_counter: int = 0
        # Phase 19 (v0.2.0): RTSP = ffmpeg subprocess pipe
        #   - ffmpeg -rtsp_transport tcp -i URL -f rawvideo -pix_fmt bgr24 -
        #   - low_delay + nobuffer 플래그 — OpenCV FFmpeg backend 의 내부
        #     버퍼·상태 관리 오버헤드 제거, THE RECORD LibVLC 수준 지연 달성
        self._ffmpeg_proc = None   # subprocess.Popen
        self._ffmpeg_stderr_fp = None  # type: ignore[assignment]  # 진단: ffmpeg stderr 파일 핸들
        self._ffmpeg_width: int = 0
        self._ffmpeg_height: int = 0

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def state(self) -> DecoderState:
        """현재 디코더 상태."""
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        """디코더가 열려있는지 여부."""
        with self._lock:
            return self._state.is_active

    @property
    def file_path(self) -> str:
        """현재 열린 파일 경로."""
        with self._lock:
            return self._file_path

    @property
    def metadata(self) -> VideoFileMetadata | None:
        """비디오 메타데이터."""
        with self._lock:
            return self._metadata

    @property
    def latest_frame(self) -> NDArray[np.uint8] | None:
        """
        최신 프레임 (background reader 가 유지).

        RTSP 모드 (Phase 18/19) 에서 background reader 가 ffmpeg stdout 에서
        계속 pull 하는 프레임. stream_mjpeg / get_snapshot 이 decode_next() 를
        따로 호출하지 않고 이 캐시만 읽으면 decoder 경합 없이 O(1) 반환.

        파일 모드에서는 최근 decode_next 가 반환한 프레임 (있을 경우).

        Returns:
            최신 BGR 프레임 ndarray 또는 None
        """
        with self._lock:
            return self._latest_frame

    @property
    def current_index(self) -> int:
        """현재 프레임 인덱스."""
        with self._lock:
            return self._current_index

    @property
    def stats(self) -> DecoderStats:
        """디코딩 통계 (방어적 복사)."""
        with self._lock:
            return DecoderStats(
                frames_decoded=self._stats.frames_decoded,
                frames_failed=self._stats.frames_failed,
                bytes_read=self._stats.bytes_read,
                decode_time_sec=self._stats.decode_time_sec,
                seek_count=self._stats.seek_count,
                last_frame_time=self._stats.last_frame_time,
                consecutive_failures=self._stats.consecutive_failures,
            )

    def get_or_decode_latest_jpeg(
        self,
        quality: int = 60,
        max_width: int = 1280,
        max_height: int = 720,
        max_age_sec: float = 0.5,
    ) -> bytes | None:
        """
        최신 프레임을 JPEG 바이트로 반환 (Phase 17 S4 — MJPEG 공유).

        동작:
          1. 캐시된 _latest_jpeg 이 max_age_sec 이내면 그대로 반환 (zero-work)
          2. 캐시된 _latest_frame 이 max_age_sec 이내면 JPEG 인코딩만 수행
          3. 둘 다 오래됐으면 decode_next() 호출 + 인코딩

        여러 MJPEG 클라이언트가 같은 decoder를 공유할 때 디코드 중복 방지.

        Args:
            quality: JPEG 품질 (1-100)
            max_width/height: 다운스케일 상한
            max_age_sec: 캐시 유효 시간

        Returns:
            JPEG 바이트 또는 None
        """
        now = time.monotonic()
        with self._lock:
            # 1. JPEG 캐시 히트
            if (
                self._latest_jpeg is not None
                and self._latest_jpeg_quality == quality
                and self._stats.last_frame_time > 0.0
                and (now - self._stats.last_frame_time) <= max_age_sec
            ):
                return self._latest_jpeg

            # 2. BGR 프레임 캐시 히트 (JPEG만 재인코딩)
            frame = None
            if (
                self._latest_frame is not None
                and self._stats.last_frame_time > 0.0
                and (now - self._stats.last_frame_time) <= max_age_sec
            ):
                frame = self._latest_frame

        # 3. 캐시 만료 → decode_next()로 새 프레임 획득
        if frame is None:
            data = self.decode_next()
            if data is None or not data.is_valid:
                return None
            frame = data.image

        # 다운스케일
        h, w = frame.shape[:2]
        if w > max_width or h > max_height:
            scale = min(max_width / w, max_height / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
        if not ok:
            return None

        jpeg_bytes = buf.tobytes()
        with self._lock:
            self._latest_jpeg = jpeg_bytes
            self._latest_jpeg_quality = quality
        return jpeg_bytes

    def seconds_since_last_frame(self) -> float:
        """
        마지막 성공 프레임 이후 경과 시간 (초) — Phase 17 S2 헬스 체크용.

        프레임이 한 번도 없었다면 0.0 반환 (연결 직후 유예).
        """
        with self._lock:
            if self._stats.last_frame_time <= 0.0:
                return 0.0
            return time.monotonic() - self._stats.last_frame_time

    def is_stalled(self, threshold_sec: float = 3.0) -> bool:
        """
        스트림이 stalled 상태인지 판정.

        기준:
          1. 연결 상태 DECODING 이어야 함
          2. 최소 1프레임 이상 디코드됨 (연결 직후 유예)
          3. 마지막 프레임으로부터 threshold_sec 이상 경과
          4. OR consecutive_failures >= 30 (30 프레임 연속 실패 = ~1초 @ 30fps)
        """
        with self._lock:
            if self._state != DecoderState.DECODING:
                return False
            if self._stats.frames_decoded == 0:
                return False  # 아직 시작 안 됨
            if self._stats.consecutive_failures >= 30:
                return True
            if self._stats.last_frame_time <= 0.0:
                return False
            elapsed = time.monotonic() - self._stats.last_frame_time
            return elapsed >= threshold_sec

    @property
    def total_frames(self) -> int:
        """총 프레임 수."""
        with self._lock:
            if self._metadata is not None and self._metadata.total_frames is not None:
                return self._metadata.total_frames
            return 0

    @property
    def fps(self) -> float:
        """FPS."""
        with self._lock:
            if self._metadata is not None:
                return self._metadata.fps
            return float(DEFAULT_FPS)

    @property
    def resolution(self) -> tuple[int, int]:
        """해상도 (width, height)."""
        with self._lock:
            if self._metadata is not None:
                return self._metadata.resolution.to_tuple()
            return ANALYSIS_NORMALIZED_RESOLUTION

    # =========================================================================
    # 열기 / 닫기
    # =========================================================================

    def open(self, file_path: str) -> bool:
        """비디오 파일 / RTSP 스트림 열기.

        Phase 19 (v0.2.0):
          - RTSP → OpenCV 로 메타(해상도/fps) 한 번 조회 → release →
                   ffmpeg subprocess pipe 로 실제 스트림 시작 (저지연 모드).
                   OpenCV FFmpeg backend 의 내부 버퍼·재인코딩 오버헤드를
                   완전히 우회해 THE RECORD (LibVLC) 수준 지연 달성.
          - 파일 → 기존 cv2.VideoCapture (순차 재생 보장).

        Returns:
            성공 여부
        """
        is_rtsp = file_path.startswith("rtsp://") or file_path.startswith("rtsps://")

        # ===== DECODE 1️⃣ open 진입 =====
        _logger.info(
            "[DECODE %s] 1️⃣ open 호출 → path=%s 종류=%s",
            self._camera_id or "?", file_path, "RTSP" if is_rtsp else "FILE",
        )

        # ---------- RTSP 경로 ----------
        if is_rtsp:
            with self._lock:
                if not self._state.can_open:
                    return False
                self._state = DecoderState.OPENING
                self._file_path = file_path

            # 1) OpenCV 로 메타 조회 — 실제 프레임 read 후 frame.shape 에서 해상도 추출.
            #    (RTSP 는 첫 read 전까지 CAP_PROP_FRAME_WIDTH/HEIGHT 가 0 을 반환하는
            #     OpenCV+FFmpeg backend 특성 때문에 read 먼저 해야 한다 — v0.2.0 에서
            #     width=0 으로 ffmpeg pipe 가 frame_size=0 으로 EOF 즉시 처리되던 버그.)
            probe_cap = _open_rtsp_with_retry(file_path)
            if probe_cap is None or not probe_cap.isOpened():
                with self._lock:
                    self._state = DecoderState.ERROR
                return False
            try:
                fps_raw = probe_cap.get(cv2.CAP_PROP_FPS)
                fps_val = fps_raw if fps_raw > 0.0 else float(DEFAULT_FPS)
                # 실제 첫 프레임 — shape 에서 해상도 추출
                ret, first_frame = probe_cap.read()
                if not ret or first_frame is None:
                    with self._lock:
                        self._state = DecoderState.ERROR
                    return False
                height, width = first_frame.shape[:2]
            finally:
                probe_cap.release()

            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
                _logger.error(
                    "RTSP 해상도 유효하지 않음: %dx%d (url=%s)", width, height, file_path,
                )
                with self._lock:
                    self._state = DecoderState.ERROR
                return False

            width = min(width, MAX_VIDEO_WIDTH)
            height = min(height, MAX_VIDEO_HEIGHT)
            _logger.info(
                "[DECODE %s] 2️⃣ RTSP 메타 조회 완료 → %dx%d @ %.1f fps (url=%s)",
                self._camera_id or "?", width, height, fps_val, file_path,
            )

            # 2) ffmpeg subprocess pipe 시작
            _logger.info(
                "[DECODE %s] 3️⃣ ffmpeg subprocess pipe 시작 호출",
                self._camera_id or "?",
            )
            try:
                # Plan D (2026-05-13): native 가 target 보다 크면 ffmpeg 단에서 사전 스케일.
                _target_w, _target_h = ANALYSIS_NORMALIZED_RESOLUTION
                self._start_ffmpeg_pipe(
                    file_path, width, height, _target_w, _target_h,
                )
            except Exception as exc:
                _logger.exception(
                    "[DECODE %s] ❌ ffmpeg pipe 시작 실패 → %s",
                    self._camera_id or "?", file_path,
                )
                with self._lock:
                    self._state = DecoderState.ERROR
                return False

            # 3) 상태 확정
            with self._lock:
                self._metadata = VideoFileMetadata(
                    duration=0.0,
                    fps=fps_val,
                    resolution=VideoResolution(width=width, height=height),
                    total_frames=0,
                )
                self._cap = None                  # OpenCV cap 사용 안 함
                self._current_index = 0
                self._stats = DecoderStats()
                self._state = DecoderState.DECODING
                self._is_rtsp = True
                self._reader_frame_counter = 0

            # 4) background reader 시작 — ffmpeg stdout 을 읽는 루프
            _logger.info(
                "[DECODE %s] 4️⃣ background reader 시작 호출",
                self._camera_id or "?",
            )
            self._start_rtsp_reader()
            _logger.info(
                "[DECODE %s] 5️⃣ RTSP open 전체 완료 → state=DECODING, "
                "ffmpeg+reader 활성, 이후 _latest_frame 캐시로 frame 공급",
                self._camera_id or "?",
            )
            return True

        # ---------- 파일 경로 ----------
        with self._lock:
            if not self._state.can_open:
                _logger.warning(
                    "[DECODE %s] ❌ open 거부 — 현재 state=%s (can_open=False)",
                    self._camera_id or "?", self._state.name,
                )
                return False

            self._state = DecoderState.OPENING
            self._file_path = file_path

            cap = cv2.VideoCapture(file_path)
            if cap is None or not cap.isOpened():
                _logger.error(
                    "[DECODE %s] ❌ cv2.VideoCapture 열기 실패 → %s",
                    self._camera_id or "?", file_path,
                )
                self._state = DecoderState.ERROR
                return False

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps_raw = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_val = fps_raw if fps_raw > 0.0 else float(DEFAULT_FPS)
            frame_count = max(frame_count, 0)
            duration = frame_count / fps_val if fps_val > 0 else 0.0

            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
                _logger.error(
                    "[DECODE %s] ❌ 해상도 너무 작음 %dx%d (min=%dx%d)",
                    self._camera_id or "?", width, height,
                    MIN_VIDEO_WIDTH, MIN_VIDEO_HEIGHT,
                )
                cap.release()
                self._state = DecoderState.ERROR
                return False

            width = min(width, MAX_VIDEO_WIDTH)
            height = min(height, MAX_VIDEO_HEIGHT)

            self._metadata = VideoFileMetadata(
                duration=duration,
                fps=fps_val,
                resolution=VideoResolution(width=width, height=height),
                total_frames=frame_count,
            )

            self._cap = cap
            self._current_index = 0
            self._stats = DecoderStats()
            self._state = DecoderState.DECODING
            self._is_rtsp = False
            self._reader_frame_counter = 0

        # ===== DECODE 2️⃣ FILE 모드 open 완료 =====
        _logger.info(
            "[DECODE %s] 2️⃣ FILE 열기 완료 → %dx%d @ %.2f fps, "
            "frames=%d, duration=%.1fs (%s)",
            self._camera_id or "?", width, height, fps_val,
            frame_count, duration, file_path,
        )
        return True

    def close(self) -> None:
        """디코더 닫기 및 리소스 해제."""
        # reader thread 먼저 정리 (lock 밖, join timeout 2s)
        self._stop_rtsp_reader()
        # ffmpeg subprocess 종료
        self._stop_ffmpeg_pipe()
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._state = DecoderState.CLOSED
            self._is_rtsp = False

    # =========================================================================
    # FFmpeg Subprocess Pipe (Phase 19 v0.2.0) — THE RECORD 수준 저지연 RTSP
    # =========================================================================
    def _start_ffmpeg_pipe(
        self,
        url: str,
        width: int,
        height: int,
        target_width: int | None = None,
        target_height: int | None = None,
    ) -> None:
        """
        ffmpeg 을 subprocess 로 띄워 RTSP 프레임을 raw BGR 로 stdout 에 흘린다.

        플래그 조합은 THE RECORD LibVLC 의 `--rtsp-tcp + network-caching 20ms`
        효과를 ffmpeg 에서 재현:
          -rtsp_transport tcp   : UDP 손실 재전송 회피
          -fflags nobuffer      : 프레임 버퍼 생성 안 함
          -fflags +discardcorrupt: 손상 프레임 즉시 drop
          -flags low_delay      : 디코더 저지연 모드
          -max_delay 0          : demuxer 재정렬 대기 0
          -reorder_queue_size 0 : RTP 재정렬 큐 0
          -probesize 32         : 스트림 분석 최소화 (첫 프레임 지연 ↓)
          -analyzeduration 0    : 분석 시간 0 (첫 프레임 지연 ↓)
          -f rawvideo -pix_fmt bgr24 : OpenCV 호환 raw frame

        번들: imageio-ffmpeg 패키지가 제공하는 ffmpeg.exe 사용. courtview.spec
              의 collect_all("imageio_ffmpeg") 이 binary 를 번들에 포함.
        """
        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg_exe = get_ffmpeg_exe()
        cmd = [ffmpeg_exe]
        # Plan B (2026-05-13): HW 디코딩 옵션은 -i 보다 앞에 와야 함 (input 옵션).
        # 출력 포맷은 그대로 bgr24 라서 ffmpeg 가 자동으로 GPU→CPU 다운로드 + 변환.
        if _HWACCEL_MODE == "d3d11va":
            cmd += ["-hwaccel", "d3d11va"]
        elif _HWACCEL_MODE == "cuda":
            cmd += ["-hwaccel", "cuda"]
        # _HWACCEL_MODE == "off" → 옵션 추가 안 함 (= 기존 SW 디코딩 경로)
        cmd += [
            "-rtsp_transport", "tcp",
            "-fflags", "nobuffer+discardcorrupt",
            "-flags", "low_delay",
            "-max_delay", "0",
            "-reorder_queue_size", "0",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-i", url,
        ]
        # Plan D (2026-05-13): native 가 target 보다 큰 경우 ffmpeg 단에서 사전 스케일.
        # reader thread 의 cv2.resize 를 제거해 GIL 점유 시간 단축 + 메모리 복사 절약.
        # native ≤ target 이면 옵션 안 붙임 (영향 0).
        out_w, out_h = width, height
        if (
            target_width is not None and target_height is not None
            and (width > target_width or height > target_height)
        ):
            cmd += ["-s", f"{target_width}x{target_height}"]
            out_w, out_h = target_width, target_height
        cmd += [
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-an", "-sn",           # audio/subtitle 제거
            "-loglevel", "info",    # 진단: stream metadata + fail 사유 가시화
            "-",
        ]
        creationflags = 0
        if sys.platform == "win32":
            # CREATE_NO_WINDOW — 콘솔 창 뜨지 않게
            creationflags = 0x08000000

        # 진단: ffmpeg stderr 를 카메라별 파일로 redirect (DEVNULL → file).
        # 첫 frame 못 받고 die 하는 진짜 원인 (codec init / probe / hwaccel) 식별용.
        try:
            from infrastructure.storage import paths as _paths
            _logs_dir = _paths.path.logs_dir
        except Exception:
            _logs_dir = os.path.join(os.getcwd(), "_appdata", "logs")
        try:
            os.makedirs(_logs_dir, exist_ok=True)
        except Exception:
            pass
        _stderr_path = os.path.join(_logs_dir, f"ffmpeg_{self._camera_id or 'unknown'}.log")
        try:
            self._ffmpeg_stderr_fp = open(_stderr_path, "w", encoding="utf-8", buffering=1)
        except Exception as _e:
            _logger.warning("[DECODE %s] ffmpeg stderr file open 실패: %s — DEVNULL 사용",
                            self._camera_id, _e)
            self._ffmpeg_stderr_fp = None

        self._ffmpeg_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=(self._ffmpeg_stderr_fp if self._ffmpeg_stderr_fp else subprocess.DEVNULL),
            bufsize=0,              # unbuffered pipe
            creationflags=creationflags,
        )
        # Plan D: 출력 해상도 (ffmpeg -s 적용 후) — reader frame_size 계산 기준.
        self._ffmpeg_width = out_w
        self._ffmpeg_height = out_h

        # stderr polling 제거 (2026-05-14): event loop 블로킹 부작용. 진단은 STEP 8/9 로 대체.

        _logger.info(
            "[DECODE %s] ffmpeg pipe 시작 → pid=%d native=%dx%d output=%dx%d "
            "(hwaccel=%s, transport=tcp, pix=bgr24, frame_bytes=%d)",
            self._camera_id, self._ffmpeg_proc.pid, width, height,
            out_w, out_h, _HWACCEL_MODE, out_w * out_h * 3,
        )

    def _stop_ffmpeg_pipe(self) -> None:
        """ffmpeg subprocess 정리.

        v0.2.2: Windows `terminate()` 는 TerminateProcess → ffmpeg 가 RTSP
        TEARDOWN 을 카메라에 못 보내고 죽음. 저가 IPCam 은 dangling session
        이 세션 슬롯을 계속 점유해 새 연결 거부 상태로 진입 (24.13 사례).
        → 킬 직전에 **우리가 직접** 별도 소켓으로 TEARDOWN 을 보내 카메라
           측 세션 정리를 강제한다.
        """
        if self._ffmpeg_proc is None:
            return
        proc = self._ffmpeg_proc
        self._ffmpeg_proc = None

        # v0.2.2 — camera-side session teardown (must happen BEFORE killing ffmpeg)
        try:
            self._send_rtsp_teardown(self._file_path, timeout_sec=1.0)
        except Exception as e:
            _logger.debug("TEARDOWN 발송 실패 (무시): %s", e)

        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        # 진단: ffmpeg stderr fp 정리
        if self._ffmpeg_stderr_fp is not None:
            try:
                self._ffmpeg_stderr_fp.close()
            except Exception:
                pass
            self._ffmpeg_stderr_fp = None
        _logger.info("ffmpeg pipe 종료: camera=%s", self._camera_id)

    @staticmethod
    def _send_rtsp_teardown(url: str, timeout_sec: float = 1.0) -> None:
        """
        카메라에 RTSP TEARDOWN 을 별도 소켓으로 직접 전송한다 (v0.2.2).

        ffmpeg 가 하드 킬 되기 전 camera-side 세션을 확실히 반환시키기 위함.
        저가 IPCam 펌웨어는 TCP FIN 만으론 세션을 즉시 해제하지 않고 keep-alive
        타임아웃 (30~60s) 까지 슬롯을 점유. 명시적 TEARDOWN 이 가장 안전.
        """
        import socket
        from urllib.parse import urlparse

        if not url or not (url.startswith("rtsp://") or url.startswith("rtsps://")):
            return
        try:
            parsed = urlparse(url)
        except Exception:
            return
        host = parsed.hostname
        port = parsed.port or (322 if parsed.scheme == "rtsps" else 554)
        if not host:
            return

        request = (
            f"TEARDOWN {url} RTSP/1.0\r\n"
            f"CSeq: 99\r\n"
            f"User-Agent: CourtView/1.0\r\n"
            f"\r\n"
        ).encode("ascii", errors="replace")

        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=timeout_sec)
            sock.settimeout(timeout_sec)
            sock.sendall(request)
            try:
                sock.recv(512)  # 응답 안 와도 상관없음
            except socket.timeout:
                pass
        except OSError:
            pass
        finally:
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass

    # =========================================================================
    # RTSP Background Reader (Phase 18 v0.1.5) — OpenCV 내부 버퍼 지연 제거
    # =========================================================================
    def _start_rtsp_reader(self) -> None:
        """
        RTSP 전용: cap.read() 를 끊임없이 호출해 OpenCV/FFmpeg 내부 버퍼의
        오래된 프레임을 계속 drop 하면서 최신 프레임만 `_latest_frame` 에 유지.
        decode_next() 는 이 캐시를 O(1) 로 반환 → 사용자 체감 지연은 카메라
        발행 ~ reader 수신 시점차 (네트워크 + OpenCV 디코드 1 프레임 분).
        """
        if self._reader_thread is not None and self._reader_thread.is_alive():
            _logger.info(
                "[DECODE %s] reader thread 이미 활성 — 재시작 스킵",
                self._camera_id or "?",
            )
            return
        self._reader_stop.clear()
        self._new_frame_event.clear()
        self._reader_thread = threading.Thread(
            target=self._rtsp_reader_loop,
            name=f"rtsp-reader-{self._camera_id or 'n/a'}",
            daemon=True,
        )
        self._reader_thread.start()
        _logger.info(
            "[DECODE %s] RTSP reader thread 시작 → name=%s daemon=True",
            self._camera_id or "?", self._reader_thread.name,
        )

    def _stop_rtsp_reader(self) -> None:
        if self._reader_thread is not None:
            self._reader_stop.set()
            try:
                self._reader_thread.join(timeout=2.0)
            except Exception:
                pass
            self._reader_thread = None
            _logger.info("RTSP reader 종료: camera_id=%s", self._camera_id)

    def _rtsp_reader_loop(self) -> None:
        """
        ffmpeg subprocess stdout 에서 raw BGR 프레임을 연속 수신.

        Phase 19 (v0.2.0): OpenCV VideoCapture 대신 ffmpeg 직접 pipe.
        ffmpeg 가 RTSP → 디코드 → raw BGR bytes 를 stdout 에 연속 흘려보냄.
        각 프레임은 width × height × 3 바이트 (bgr24).

        프레임 경계 결정:
          ffmpeg 는 각 프레임을 **정확히** frame_size 바이트로 출력 (rawvideo 특성).
          fread(frame_size) 가 bgr24 해상도 프레임 1개 완성 보장.

        오래된 프레임 drop:
          decode_next() 호출이 느려도 이 루프가 계속 pipe 에서 pull 하므로
          kernel pipe buffer (기본 64 KB, 프레임 ~ MB 단위라 1 프레임 이하)
          에 누적이 안 된다. 카메라가 보내는 프레임을 거의 실시간으로 수신.
        """
        if self._ffmpeg_proc is None or self._ffmpeg_proc.stdout is None:
            _logger.error(
                "[DECODE %s] reader loop 진입 실패 — ffmpeg_proc=None or stdout=None",
                self._camera_id or "?",
            )
            return

        proc = self._ffmpeg_proc
        # Plan D (2026-05-13): _ffmpeg_width/height 는 이미 ffmpeg -s 가 적용된
        # 출력 해상도. native > target 이면 사전 스케일된 값, 아니면 native 그대로.
        # → reader 단의 cv2.resize 가 불필요해짐.
        w = self._ffmpeg_width
        h = self._ffmpeg_height
        frame_size = w * h * 3  # bgr24 — 3 bytes per pixel

        _logger.info(
            "[DECODE %s] 🎥 RTSP reader loop 진입 → frame_size=%d bytes (%dx%d×3)",
            self._camera_id or "?", frame_size, w, h,
        )
        # STEP 8 진단: reader 진입 사실을 silence-immune flow_logger 로도 기록.
        try:
            from infrastructure.diagnostics.flow_logger import log_flow
            log_flow(
                "READ-ENTER",
                "cam=%s reader 진입 — frame_size=%d (%dx%d)",
                self._camera_id or "?", frame_size, w, h,
                first_n=8,
            )
        except Exception:
            pass

        stdout = proc.stdout
        local_frame_count = 0  # heartbeat 카운터

        while not self._reader_stop.is_set():
            t0 = time.monotonic()
            # Read exactly frame_size bytes — ffmpeg 는 항상 완전 프레임 출력
            data = bytearray()
            need = frame_size
            while need > 0 and not self._reader_stop.is_set():
                try:
                    chunk = stdout.read(need)
                except Exception as e:
                    _logger.warning(
                        "[DECODE %s] ❌ ffmpeg stdout read 예외: %s",
                        self._camera_id or "?", e,
                    )
                    try:
                        from infrastructure.diagnostics.flow_logger import log_flow
                        log_flow("READ-EXC", "cam=%s stdout.read 예외: %s",
                                 self._camera_id or "?", e, first_n=3)
                    except Exception:
                        pass
                    chunk = b""
                if not chunk:
                    # EOF — ffmpeg 종료됨 (RTSP 끊김 or crash)
                    _logger.warning(
                        "[DECODE %s] 🛑 ffmpeg pipe EOF — ffmpeg 종료됨 "
                        "(RTSP 끊김 or ffmpeg crash, 누적 frame=%d)",
                        self._camera_id or "?", local_frame_count,
                    )
                    try:
                        from infrastructure.diagnostics.flow_logger import log_flow
                        log_flow("READ-EOF",
                                 "cam=%s EOF — ffmpeg 종료. 누적 frame=%d",
                                 self._camera_id or "?", local_frame_count,
                                 first_n=8)
                    except Exception:
                        pass
                    return
                data.extend(chunk)
                # STEP 8 진단: 첫 chunk 도착 시점 가시화 (첫 frame 만)
                if local_frame_count == 0 and len(data) == len(chunk):
                    try:
                        from infrastructure.diagnostics.flow_logger import log_flow
                        log_flow(
                            "READ-FIRST-CHUNK",
                            "cam=%s 첫 chunk 도착 → %d bytes (need=%d)",
                            self._camera_id or "?", len(chunk), frame_size,
                            first_n=8,
                        )
                    except Exception:
                        pass
                need = frame_size - len(data)

            if self._reader_stop.is_set():
                _logger.info(
                    "[DECODE %s] 🛑 reader stop signal → loop 종료 "
                    "(누적 frame=%d)",
                    self._camera_id or "?", local_frame_count,
                )
                return

            dt = time.monotonic() - t0

            # raw bytes → numpy ndarray (copy=True via .copy() 아래 _latest_frame)
            try:
                frame = np.frombuffer(bytes(data), dtype=np.uint8).reshape(h, w, 3)
            except Exception as e:
                _logger.warning(
                    "[DECODE %s] ❌ 프레임 reshape 실패 → %s (frame_size=%d)",
                    self._camera_id or "?", e, len(data),
                )
                try:
                    from infrastructure.diagnostics.flow_logger import log_flow
                    log_flow(
                        "READ-RESHAPE-FAIL",
                        "cam=%s reshape 실패: %s (got=%d, expect=%d, %dx%dx3)",
                        self._camera_id or "?", e, len(data), frame_size, h, w,
                        first_n=5,
                    )
                except Exception:
                    pass
                with self._lock:
                    self._stats.frames_failed += 1
                continue
            # STEP 8 진단: 첫 frame reshape 성공 시점
            if local_frame_count == 0:
                try:
                    from infrastructure.diagnostics.flow_logger import log_flow
                    log_flow(
                        "READ-FIRST-FRAME",
                        "cam=%s 첫 frame 완성 → shape=%s dtype=%s read_time=%.1fms",
                        self._camera_id or "?", frame.shape, frame.dtype,
                        (time.monotonic() - t0) * 1000.0,
                        first_n=8,
                    )
                except Exception:
                    pass

            # Plan D (2026-05-13): cv2.resize 제거 — ffmpeg 가 사전 스케일.

            with self._lock:
                # frombuffer 는 읽기 전용 view — copy 해서 external 사용 안전
                self._latest_frame = frame.copy()
                self._latest_jpeg = None
                self._reader_frame_counter += 1
                self._stats.frames_decoded += 1
                self._stats.consecutive_failures = 0
                self._stats.last_frame_time = time.monotonic()
                self._stats.decode_time_sec += dt
                self._stats.bytes_read += frame.nbytes
                decoded_total = self._stats.frames_decoded
            self._new_frame_event.set()
            local_frame_count += 1

            # heartbeat — 첫 5프레임 + 100프레임마다 1번
            if local_frame_count <= 5 or local_frame_count % 100 == 0:
                _logger.info(
                    "[DECODE %s] 🎥 RTSP frame #%d read 완료 → %dx%d "
                    "read_time=%.1fms (누적=%d, failed=%d)",
                    self._camera_id or "?", local_frame_count,
                    frame.shape[1], frame.shape[0],
                    dt * 1000.0, decoded_total, self._stats.frames_failed,
                )

    # =========================================================================
    # 프레임 디코딩
    # =========================================================================

    def decode_next(self) -> FrameData | None:
        """다음 프레임 디코딩.

        Phase 18 v0.1.5:
          - RTSP: background reader 가 유지하는 _latest_frame 을 O(1) 반환.
                  새 프레임 없으면 최대 100 ms 대기. 지연 ≈ OpenCV 1 프레임 분.
          - 파일: 기존 sync 방식 — cap.read() 로 순차 프레임 (순차 재생 보장).

        Returns:
            FrameData 또는 None (EOF/오류/timeout)
        """
        with self._lock:
            # 2026-05-14 fix: _cap 가드를 RTSP 분기 이후로 이동.
            # RTSP 모드는 OpenCV _cap 안 쓰고 ffmpeg subprocess pipe 사용 → _cap=None 정상.
            # 기존 가드는 RTSP 일 때도 None 즉시 반환시켜 _fetch_latest_rtsp_frame 미진입.
            if self._state != DecoderState.DECODING:
                return None
            is_rtsp = self._is_rtsp
            cap = self._cap

        if is_rtsp:
            return self._fetch_latest_rtsp_frame()

        # --- 파일 경로: cap 필수 ---
        if cap is None:
            return None

        # --- 파일 경로: 기존 sync 동작 유지 ---
        t0 = time.monotonic()
        ret, frame = cap.read()
        dt = time.monotonic() - t0

        if not ret or frame is None:
            with self._lock:
                self._stats.frames_failed += 1
                self._stats.consecutive_failures += 1
                self._stats.decode_time_sec += dt
                fail_streak = self._stats.consecutive_failures
                total_failed = self._stats.frames_failed
                cur_idx = self._current_index
            # DECODE 실패 — 100회마다 또는 첫 실패 시 로그 (EOF 가까울 때 자주 발생)
            if fail_streak == 1 or fail_streak % 100 == 0:
                _logger.warning(
                    "[DECODE %s] ❌ FILE read 실패 #%d (연속=%d, 다음_idx=%d) "
                    "→ EOF 또는 손상",
                    self._camera_id or "?", total_failed, fail_streak, cur_idx,
                )
            return None

        # 4K → 1080p 리사이즈
        h, w = frame.shape[:2]
        target_w, target_h = ANALYSIS_NORMALIZED_RESOLUTION
        resized = False
        if w > target_w or h > target_h:
            frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
            resized = True

        with self._lock:
            index = self._current_index
            self._current_index += 1
            self._stats.frames_decoded += 1
            self._stats.consecutive_failures = 0
            self._stats.last_frame_time = time.monotonic()
            self._stats.decode_time_sec += dt
            self._stats.bytes_read += frame.nbytes
            self._latest_frame = frame
            self._latest_jpeg = None
            decoded_count = self._stats.frames_decoded

        # DECODE heartbeat — 100프레임마다 + 첫 5프레임
        if decoded_count <= 5 or decoded_count % 100 == 0:
            _logger.info(
                "[DECODE %s] 🎞 FILE decode #%d → %dx%d %s "
                "decode_time=%.1fms (누적 decoded=%d, failed=%d)",
                self._camera_id or "?", index, frame.shape[1], frame.shape[0],
                "[resized]" if resized else "",
                dt * 1000.0, decoded_count, self._stats.frames_failed,
            )

        timestamp = index / self.fps if self.fps > 0 else 0.0

        return FrameData(
            image=frame,
            index=index,
            timestamp=timestamp,
            status=FrameStatus.VALID,
            camera_id=self._camera_id,
        )

    def _fetch_latest_rtsp_frame(self) -> FrameData | None:
        """
        RTSP 모드: background reader 가 유지하는 최신 프레임 반환.

        호출 시점엔 lock 보유하지 않은 상태 (caller 가 release 후 진입).
        프레임 아직 없으면 new_frame_event 로 최대 100 ms 대기.
        """
        with self._lock:
            frame = self._latest_frame
            last_t = self._stats.last_frame_time

        if frame is None:
            # 새 프레임 올 때까지 대기 (lock 밖)
            got = self._new_frame_event.wait(timeout=0.1)
            if not got:
                # 100ms 안에 새 프레임 안 옴 — ffmpeg 또는 카메라 문제
                self._fetch_wait_fail_count = getattr(self, "_fetch_wait_fail_count", 0) + 1
                if self._fetch_wait_fail_count <= 5 or self._fetch_wait_fail_count % 50 == 0:
                    _logger.warning(
                        "[DECODE %s] ⏳ fetch 대기 timeout (100ms) #%d — "
                        "background reader 가 frame 못 받음 (ffmpeg 죽었거나 카메라 끊김?)",
                        self._camera_id or "?", self._fetch_wait_fail_count,
                    )
                try:
                    from infrastructure.diagnostics.flow_logger import log_flow
                    log_flow(
                        "FETCH-WAIT-TIMEOUT",
                        "cam=%s fetch 대기 timeout #%d (reader_count=%d, frames_decoded=%d, frames_failed=%d)",
                        self._camera_id or "?", self._fetch_wait_fail_count,
                        getattr(self, "_reader_frame_counter", -1),
                        self._stats.frames_decoded, self._stats.frames_failed,
                        first_n=8, every=200,
                    )
                except Exception:
                    pass
                return None
            with self._lock:
                frame = self._latest_frame
                last_t = self._stats.last_frame_time
            if frame is None:
                _logger.warning(
                    "[DECODE %s] ⏳ event 받았으나 _latest_frame=None — race 또는 reset",
                    self._camera_id or "?",
                )
                return None

        # decode_next 1 회당 external index 1 증가 (기존 계약 유지)
        with self._lock:
            index = self._current_index
            self._current_index += 1

        # stale frame 감지 — 같은 frame 을 반복 반환 중이면 reader 가 멈춘 것
        # last_frame_time 이 1초 이상 지났으면 stale
        now = time.monotonic()
        stale_age_sec = now - last_t if last_t > 0 else 0.0
        is_stale = stale_age_sec > 1.0

        # heartbeat — 첫 5번 + 100번마다 + stale 감지 시
        if index <= 5 or index % 100 == 0 or is_stale:
            _logger.info(
                "[DECODE %s] 🔄 fetch #%d → %dx%d age=%.2fs %s"
                "(reader_count=%d)",
                self._camera_id or "?", index,
                frame.shape[1], frame.shape[0], stale_age_sec,
                "⚠STALE " if is_stale else "",
                getattr(self, "_reader_frame_counter", -1),
            )

        # 2026-05-13: RTSP timestamp 는 실제 수신 시각(monotonic)으로 사용.
        # 이전 값(index/fps)은 각 카메라 decoder 의 frame_counter 가 독립 증가
        # 하므로 카메라마다 timestamp 가 수십~수백 초 어긋남 → frame_aligner 가
        # 어떤 tolerance 로도 align 성공 못 함. 모든 카메라가 같은 monotonic 시계
        # 를 공유해야 33ms 단위 비교가 의미 있음.
        timestamp = last_t if last_t > 0 else time.monotonic()

        return FrameData(
            image=frame,
            index=index,
            timestamp=timestamp,
            status=FrameStatus.VALID,
            camera_id=self._camera_id,
        )

    def decode_frame(self, frame_index: int) -> FrameData | None:
        """특정 프레임 디코딩 (seek + read).

        Args:
            frame_index: 대상 프레임 인덱스 (0-based)

        Returns:
            FrameData 또는 None
        """
        with self._lock:
            if self._cap is None or not self._state.is_active:
                return None

            if frame_index < 0:
                return None

            total = self.total_frames
            if total > 0 and frame_index >= total:
                return None

            # seek
            if self._current_index != frame_index:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_index))
                self._stats.seek_count += 1
                self._current_index = frame_index

            # 디코딩 상태 보장
            if self._state == DecoderState.PAUSED:
                self._state = DecoderState.DECODING

            t0 = time.monotonic()
            ret, frame = self._cap.read()
            dt = time.monotonic() - t0

            self._stats.decode_time_sec += dt

            if not ret or frame is None:
                self._stats.frames_failed += 1
                return None

            timestamp = frame_index / self.fps if self.fps > 0 else 0.0

            self._current_index = frame_index + 1
            self._stats.frames_decoded += 1
            self._stats.bytes_read += frame.nbytes

            return FrameData(
                image=frame,
                index=frame_index,
                timestamp=timestamp,
                status=FrameStatus.VALID,
                camera_id=self._camera_id,
            )

    def decode_sequential(
        self,
        start_frame: int = 0,
        max_frames: int | None = None,
        step: int = 1,
    ) -> Generator[FrameData, None, None]:
        """순차 프레임 디코딩 제너레이터.

        Args:
            start_frame: 시작 프레임 인덱스
            max_frames: 최대 디코딩 프레임 수 (None=전체)
            step: 프레임 간격 (1=매 프레임, 2=격 프레임)

        Yields:
            FrameData
        """
        step = max(1, step)

        # 시작 위치로 seek
        if start_frame > 0:
            with self._lock:
                if self._cap is None or not self._state.is_active:
                    return
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(start_frame))
                self._current_index = start_frame
                self._stats.seek_count += 1

        count = 0

        while True:
            if max_frames is not None and count >= max_frames:
                break

            frame_data = self.decode_next()
            if frame_data is None:
                break

            # step > 1: 중간 프레임 건너뛰기
            if step > 1:
                skip_target = frame_data.index + step - 1
                with self._lock:
                    if self._cap is not None:
                        self._cap.set(
                            cv2.CAP_PROP_POS_FRAMES, float(skip_target + 1)
                        )
                        self._current_index = skip_target + 1

            count += 1
            yield frame_data

    def decode_range(
        self,
        start_frame: int,
        end_frame: int,
    ) -> list[FrameData]:
        """프레임 범위 디코딩.

        Args:
            start_frame: 시작 프레임 (포함)
            end_frame: 종료 프레임 (미포함)

        Returns:
            FrameData 리스트
        """
        if start_frame < 0 or end_frame <= start_frame:
            return []

        max_count = min(end_frame - start_frame, DECODER_BUFFER_MAX)
        result: list[FrameData] = []

        for frame_data in self.decode_sequential(
            start_frame=start_frame, max_frames=max_count
        ):
            result.append(frame_data)

        return result

    # =========================================================================
    # 제어
    # =========================================================================

    def pause(self) -> bool:
        """디코딩 일시 정지.

        Returns:
            성공 여부
        """
        with self._lock:
            if self._state != DecoderState.DECODING:
                return False
            self._state = DecoderState.PAUSED
            return True

    def resume(self) -> bool:
        """디코딩 재개.

        Returns:
            성공 여부
        """
        with self._lock:
            if self._state != DecoderState.PAUSED:
                return False
            self._state = DecoderState.DECODING
            return True

    def seek(self, frame_index: int) -> bool:
        """특정 프레임으로 이동.

        Args:
            frame_index: 대상 프레임 인덱스

        Returns:
            성공 여부
        """
        with self._lock:
            if self._cap is None or not self._state.is_active:
                return False

            if frame_index < 0:
                return False

            total = self.total_frames
            if total > 0 and frame_index >= total:
                return False

            self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_index))
            self._current_index = frame_index
            self._stats.seek_count += 1
            return True

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = DecoderStats()

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self) -> VideoDecoder:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"VideoDecoder(state={self._state.value}, "
                f"file='{self._file_path}', "
                f"frame={self._current_index})"
            )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "VideoDecoder",
    # 데이터 클래스
    "DecoderStats",
    # Enum
    "DecoderState",
    # 상수
    "DECODER_BUFFER_MAX",
    "RTSP_OPEN_MAX_ATTEMPTS",
    "RTSP_OPEN_BACKOFF_BASE_SEC",
    "RTSP_OPEN_TIMEOUT_MS",
    # 헬퍼 (Phase 17 S2)
    "probe_rtsp",
]

__version__ = "1.0.0"
