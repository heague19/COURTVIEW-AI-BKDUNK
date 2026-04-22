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

# 디코더 내부 버퍼 최대 크기
DECODER_BUFFER_MAX: Final[int] = DECODE_BUFFER_SIZE

# RTSP 연결 재시도 설정 (Phase 17 S1)
RTSP_OPEN_MAX_ATTEMPTS: Final[int] = 3       # 최대 시도 횟수
RTSP_OPEN_BACKOFF_BASE_SEC: Final[float] = 0.5  # 초기 백오프 (exponential: 0.5, 1.0, 2.0)
RTSP_OPEN_TIMEOUT_MS: Final[int] = 5000      # 단일 open 시도 timeout (ms)


def probe_rtsp(url: str, timeout_sec: float = 3.0) -> dict[str, object]:
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
        """비디오 파일 열기.

        Args:
            file_path: 비디오 파일 경로

        Returns:
            성공 여부
        """
        with self._lock:
            if not self._state.can_open:
                return False

            self._state = DecoderState.OPENING
            self._file_path = file_path

            # RTSP 실시간 스트림: TCP + 재시도 (Phase 17 S1)
            is_rtsp = file_path.startswith("rtsp://") or file_path.startswith("rtsps://")
            if is_rtsp:
                cap = _open_rtsp_with_retry(file_path)
            else:
                cap = cv2.VideoCapture(file_path)

            if cap is None or not cap.isOpened():
                self._state = DecoderState.ERROR
                return False

            # 메타데이터 추출
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps_raw = cap.get(cv2.CAP_PROP_FPS)

            # RTSP는 frame_count/duration 알 수 없음 (무한 스트림)
            if is_rtsp:
                frame_count = 0
                fps_val = fps_raw if fps_raw > 0.0 else float(DEFAULT_FPS)
                duration = 0.0
            else:
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps_val = fps_raw if fps_raw > 0.0 else float(DEFAULT_FPS)
                frame_count = max(frame_count, 0)
                duration = frame_count / fps_val if fps_val > 0 else 0.0

            # 유효성 검증
            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
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

            return True

    def close(self) -> None:
        """디코더 닫기 및 리소스 해제."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._state = DecoderState.CLOSED

    # =========================================================================
    # 프레임 디코딩
    # =========================================================================

    def decode_next(self) -> FrameData | None:
        """다음 프레임 디코딩.

        lock 스코프를 최소화하여 네트워크 대기 시간 동안 다른 스레드가
        블로킹되지 않도록 한다. 4K 입력은 분석 해상도(1080p)로 리사이즈.

        Returns:
            FrameData 또는 None (EOF/오류)
        """
        # lock 최소화: cap 참조만 복사
        with self._lock:
            if self._cap is None or self._state != DecoderState.DECODING:
                return None
            cap = self._cap

        # lock 밖에서 I/O 수행 (네트워크 대기 중 다른 스레드 블로킹 방지)
        t0 = time.monotonic()
        ret, frame = cap.read()
        dt = time.monotonic() - t0

        if not ret or frame is None:
            with self._lock:
                self._stats.frames_failed += 1
                self._stats.consecutive_failures += 1
                self._stats.decode_time_sec += dt
            return None

        # 4K → 1080p 리사이즈 (분석 정규화 해상도)
        h, w = frame.shape[:2]
        target_w, target_h = ANALYSIS_NORMALIZED_RESOLUTION
        if w > target_w or h > target_h:
            frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

        with self._lock:
            index = self._current_index
            self._current_index += 1
            self._stats.frames_decoded += 1
            self._stats.consecutive_failures = 0  # 성공 시 리셋
            self._stats.last_frame_time = time.monotonic()  # health 모니터링용
            self._stats.decode_time_sec += dt
            self._stats.bytes_read += frame.nbytes
            # Phase 17 S4: 최신 프레임 캐시 (MJPEG 공유용)
            self._latest_frame = frame
            self._latest_jpeg = None  # 무효화 — 다음 조회 시 재인코딩

        timestamp = index / self.fps if self.fps > 0 else 0.0

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
