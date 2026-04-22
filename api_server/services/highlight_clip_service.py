# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: highlight_clip_service.py
설명: HighlightDetector/ClipExtractor 의 ExtractedClip 결과를
      활성 녹화 세션에서 실제 MP4 파일로 추출하는 옵저버 서비스.

      PossessionPipeline.set_clip_observer(service.on_clip) 로 연결.

      타이밍 전략:
        - 이벤트는 `now` 시점에 발생했다고 가정 (pipeline 지연은 수백 ms 수준).
        - post-roll 만큼 기다렸다가 ffmpeg 로 [now - duration_sec, now] 구간 추출.
        - 세그먼트 경계 넘어가는 경우: 현재 세그먼트 시작 이후만 추출 (부분 클립).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from game_analysis.output.highlight.clip_file_extractor import (
    ClipFileExtractionError,
    ClipFileExtractor,
)

if TYPE_CHECKING:
    from engine.io.recording import RecordingService
    from game_analysis.output.highlight.clip_extractor import ExtractedClip

_logger = logging.getLogger(__name__)

# 기본 post-roll 대기 (초) — 이벤트 발생 후 추출까지 기다리는 시간
_DEFAULT_POST_BUFFER_SEC = 4.0
# ThreadPoolExecutor worker 수
_DEFAULT_MAX_WORKERS = 2


class HighlightClipService:
    """
    PossessionPipeline observer → MP4 파일 추출.

    스레드 안전. 이벤트 중복 방지 (event_id 기준).
    """

    __slots__ = (
        "_recording_service",
        "_extractor",
        "_post_buffer_sec",
        "_executor",
        "_pending",
        "_lock",
        "_master_camera_id",
    )

    def __init__(
        self,
        recording_service: RecordingService,
        extractor: ClipFileExtractor | None = None,
        post_buffer_sec: float = _DEFAULT_POST_BUFFER_SEC,
        max_workers: int = _DEFAULT_MAX_WORKERS,
        master_camera_id: str | None = None,
    ) -> None:
        self._recording_service = recording_service
        self._extractor = extractor or ClipFileExtractor()
        self._post_buffer_sec = post_buffer_sec
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="clip-extract",
        )
        self._pending: dict[str, Future[Any]] = {}
        self._lock: RLock = RLock()
        # None 이면 첫 번째 카메라 자동 선택
        self._master_camera_id = master_camera_id

    # =========================================================================
    # Observer 콜백 (파이프라인에서 호출)
    # =========================================================================
    def on_clip(self, clip: ExtractedClip) -> None:
        """PossessionPipeline observer 콜백. 비차단."""
        if not self._extractor.is_available:
            return

        # 녹화 세션 없으면 스킵 (배치 분석 등)
        if not getattr(self._recording_service, "is_recording", False):
            return

        event_id = getattr(clip, "event_id", "") or ""
        if not event_id:
            _logger.debug("event_id 없는 클립 — 건너뜀")
            return

        with self._lock:
            if event_id in self._pending:
                return  # 중복 방지
            fut = self._executor.submit(self._extract_with_delay, clip)
            self._pending[event_id] = fut

            def _cleanup(_f: Future[Any], _id: str = event_id) -> None:
                with self._lock:
                    self._pending.pop(_id, None)

            fut.add_done_callback(_cleanup)

    # =========================================================================
    # 내부: 추출 실행
    # =========================================================================
    def _extract_with_delay(self, clip: ExtractedClip) -> None:
        try:
            # post-roll 프레임이 녹화 파일에 기록될 때까지 대기
            time.sleep(self._post_buffer_sec)
            self._do_extract(clip)
        except Exception:
            _logger.exception("클립 추출 워커 실패: %s", getattr(clip, "event_id", "?"))

    def _do_extract(self, clip: ExtractedClip) -> None:
        status = self._recording_service.get_status()
        if not status.get("active"):
            _logger.debug("녹화 비활성 — 클립 추출 스킵")
            return

        cameras: dict[str, dict[str, Any]] = status.get("cameras", {}) or {}
        if not cameras:
            _logger.debug("녹화 카메라 없음 — 클립 추출 스킵")
            return

        # 마스터 카메라 선택
        if self._master_camera_id and self._master_camera_id in cameras:
            cam_id = self._master_camera_id
        else:
            cam_id = next(iter(cameras.keys()))
        cam = cameras[cam_id]

        source_path = cam.get("output") or ""
        if not source_path or not Path(source_path).exists():
            _logger.warning("소스 파일 없음: %s", source_path)
            return

        # 세그먼트 기준 offset 계산
        # cam["duration_sec"] = now - segment.start_time (RecordingService 에서 계산됨)
        # 이벤트는 약 clip.duration_sec 전에 시작했다고 가정 (post_buffer 이미 지연됨)
        segment_age = float(cam.get("duration_sec", 0.0))
        duration_sec = max(1.0, float(getattr(clip, "duration_sec", 6.0)))
        offset = segment_age - duration_sec
        if offset < 0:
            # 세그먼트 경계를 넘어감 → 가능한 만큼만 (시작부터)
            _logger.info(
                "클립이 세그먼트 시작 이전부터 시작 (offset=%.2f) — 부분 추출",
                offset,
            )
            # duration 도 줄여서 세그먼트 내에 맞춤
            duration_sec = segment_age
            offset = 0.0

        # 출력 경로
        session_dir = Path(status.get("session_dir", ""))
        if not session_dir.exists():
            _logger.warning("세션 디렉토리 없음: %s", session_dir)
            return
        out_dir = session_dir / "clips"
        event_id = clip.event_id or "unknown"
        # event_id 에 안전하지 않은 문자 제거 (파일명 보안)
        safe_name = "".join(c for c in event_id if c.isalnum() or c in "-_")
        out_path = out_dir / f"{safe_name}.mp4"

        try:
            result = self._extractor.extract(
                source_path=source_path,
                start_offset_sec=offset,
                duration_sec=duration_sec,
                output_path=out_path,
            )
            _logger.info(
                "하이라이트 클립 생성: %s (cam=%s, offset=%.2fs, dur=%.2fs, %d bytes)",
                out_path.name, cam_id, offset, duration_sec, result.file_size_bytes,
            )
        except ClipFileExtractionError as e:
            _logger.warning("클립 추출 실패 (%s): %s", event_id, e)
        except Exception:
            _logger.exception("클립 추출 중 예외 (%s)", event_id)

    # =========================================================================
    # 라이프사이클
    # =========================================================================
    def shutdown(self) -> None:
        """pending 작업 정리 + executor 종료."""
        self._executor.shutdown(wait=False, cancel_futures=True)


__all__ = ["HighlightClipService"]
