# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
파일: stream_routes.py
설명: MJPEG 영상 스트림 라우트
      - GET /api/v1/stream/{camera_id}  개별 카메라 MJPEG 스트림
      - GET /api/v1/stream/mosaic/all   8뷰 모자이크 MJPEG 스트림

      백그라운드 스레드에서 카메라별 연속 재생 → 최신 프레임 버퍼 유지.
      카메라 전환 시 영상이 처음으로 돌아가지 않습니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-06
버전: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["영상 스트림"])


# MJPEG 스트림 FPS 상한 (Config 후보) — 카메라 성능 초과 방지 + 대역폭 제어
_DEFAULT_MJPEG_FPS_CAP: float = 20.0


# =============================================================================
# 카메라 프레임 버퍼 — 백그라운드 연속 재생
# =============================================================================
class _CameraBuffer:
    """카메라별 연속 재생. 백그라운드 스레드에서 프레임을 읽어 최신 JPEG 유지."""

    __slots__ = ("cam_id", "path", "_cap", "_jpeg", "_lock", "_running", "_thread", "_fps")

    def __init__(self, cam_id: str, path: str, fps_cap: float = _DEFAULT_MJPEG_FPS_CAP) -> None:
        self.cam_id = cam_id
        self.path = path
        self._cap: cv2.VideoCapture | None = None
        self._jpeg: bytes | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._fps: float = fps_cap

    def start(self) -> bool:
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            _logger.warning("카메라 열기 실패: %s → %s", self.cam_id, self.path)
            return False
        # 카메라 실제 FPS vs Config 상한 중 작은 값 (카메라 성능 초과 방지)
        self._fps = min(self._cap.get(cv2.CAP_PROP_FPS) or self._fps, self._fps)
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name=f"stream-{self.cam_id}",
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
            self._cap = None

    def _read_loop(self) -> None:
        delay = 1.0 / self._fps
        params = [cv2.IMWRITE_JPEG_QUALITY, 70]
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
            _, jpg = cv2.imencode(".jpg", frame, params)
            with self._lock:
                self._jpeg = jpg.tobytes()
            time.sleep(delay)

    @property
    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg


# =============================================================================
# 전역 상태
# =============================================================================
_video_paths: dict[str, str] = {}
_buffers: dict[str, _CameraBuffer] = {}
_running = False


def set_video_sources(sources: dict[str, str]) -> None:
    """영상 소스 등록 + 백그라운드 재생 시작."""
    global _video_paths, _running
    stop_streams()
    _video_paths = {}
    for cam_id, path in sources.items():
        if path.startswith("rtsp://") or Path(path).exists():
            _video_paths[cam_id] = path
            buf = _CameraBuffer(cam_id, path)
            if buf.start():
                _buffers[cam_id] = buf
                _logger.info("스트림 시작: %s → %s", cam_id, path)
        else:
            _logger.warning("소스 누락: %s → %s", cam_id, path)
    _running = True


def stop_streams() -> None:
    global _running
    _running = False
    for buf in _buffers.values():
        buf.stop()
    _buffers.clear()
    _video_paths.clear()


# =============================================================================
# MJPEG 생성기
# =============================================================================
async def _generate_mjpeg(cam_id: str):
    """최신 프레임 버퍼에서 MJPEG 전송 — 카메라 전환해도 연속 재생."""
    buf = _buffers.get(cam_id)
    if not buf:
        return
    while _running:
        jpeg = buf.jpeg
        if jpeg:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
        await asyncio.sleep(0.05)


async def _generate_mosaic():
    """8뷰 모자이크 — 버퍼에서 합성."""
    cam_ids = sorted(_buffers.keys())
    if not cam_ids:
        return
    cell_w, cell_h = 480, 270
    cols, rows = 4, 2
    w, h = cell_w * cols, cell_h * rows

    while _running:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        for idx, cam_id in enumerate(cam_ids[:8]):
            buf = _buffers.get(cam_id)
            if not buf or not buf.jpeg:
                continue
            arr = np.frombuffer(buf.jpeg, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            r, c = idx // cols, idx % cols
            resized = cv2.resize(frame, (cell_w, cell_h))
            cv2.putText(resized, f"CAM {idx+1}", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            canvas[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w] = resized

        _, jpeg = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 65])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes()
            + b"\r\n"
        )
        await asyncio.sleep(0.05)


# =============================================================================
# 엔드포인트
# =============================================================================
@router.post("/setup")
async def setup_streams(sources: dict[str, str]):
    """영상 소스 등록 + 백그라운드 재생 시작."""
    set_video_sources(sources)
    return {"success": True, "cameras": len(_buffers), "message": f"{len(_buffers)}대 스트림 시작 완료"}


@router.get("/mosaic/all")
async def stream_mosaic():
    return StreamingResponse(_generate_mosaic(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/{camera_id}")
async def stream_camera(camera_id: str):
    if camera_id not in _buffers:
        return {"error": f"카메라 {camera_id} 없음", "registered": list(_buffers.keys())}
    return StreamingResponse(_generate_mjpeg(camera_id), media_type="multipart/x-mixed-replace; boundary=frame")
