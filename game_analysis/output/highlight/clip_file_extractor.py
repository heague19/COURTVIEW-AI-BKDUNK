# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/highlight
파일: clip_file_extractor.py
설명: ClipExtractor 가 계산한 시간 구간을 실제 MP4 파일로 추출하는 ffmpeg 래퍼.

      ClipExtractor → ExtractedClip(start_time_sec, end_time_sec) → 시간 범위만 산출
      ClipFileExtractor → 소스 녹화 파일에서 ffmpeg 로 해당 구간을 잘라 로컬 MP4 생성

      stream copy (`-c copy`) 로 재인코딩 없이 1초 미만 추출.
      seek 를 `-ss` 전치로 두어 keyframe 기반 빠른 seek (현장 라이브 용).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from engine.io.recording import find_ffmpeg

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClipFileResult:
    """추출 결과."""

    output_path: Path
    duration_sec: float
    file_size_bytes: int
    ffmpeg_elapsed_sec: float


class ClipFileExtractionError(RuntimeError):
    """클립 추출 실패."""


class ClipFileExtractor:
    """
    ffmpeg 기반 클립 파일 추출기.

    스레드 안전 (상태 없음, 매 호출 독립 subprocess).
    """

    def __init__(
        self,
        ffmpeg_path: str | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        self._ffmpeg = ffmpeg_path or find_ffmpeg()
        self._timeout_sec = timeout_sec
        if not self._ffmpeg:
            _logger.warning("ffmpeg 실행파일을 찾을 수 없음 — ClipFileExtractor 비활성")

    @property
    def is_available(self) -> bool:
        """ffmpeg 사용 가능 여부."""
        return self._ffmpeg is not None

    def extract(
        self,
        source_path: str | Path,
        start_offset_sec: float,
        duration_sec: float,
        output_path: str | Path,
        overwrite: bool = False,
    ) -> ClipFileResult:
        """
        소스 녹화 파일에서 지정 구간을 잘라 MP4 로 저장.

        Args:
            source_path: 원본 녹화 파일 (.ts 또는 .mp4)
            start_offset_sec: 파일 내 시작 오프셋 (초)
            duration_sec: 추출 구간 길이 (초)
            output_path: 출력 MP4 경로
            overwrite: True 면 기존 파일 덮어쓰기, False 면 존재 시 그대로 반환

        Returns:
            ClipFileResult

        Raises:
            ClipFileExtractionError: ffmpeg 미발견 / 소스 없음 / 파라미터 오류 / subprocess 실패
        """
        if not self._ffmpeg:
            raise ClipFileExtractionError("ffmpeg 실행파일이 없음")

        src = Path(source_path)
        if not src.exists() or not src.is_file():
            raise ClipFileExtractionError(f"소스 파일을 찾을 수 없음: {src}")

        if duration_sec <= 0:
            raise ClipFileExtractionError(f"duration_sec 은 양수여야 함 (받음: {duration_sec})")

        if start_offset_sec < 0:
            start_offset_sec = 0.0

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # 멱등성: 이미 있고 크기 > 0 이면 재사용
        if out.exists() and out.stat().st_size > 0 and not overwrite:
            _logger.debug("기존 클립 재사용: %s (%d bytes)", out, out.stat().st_size)
            return ClipFileResult(
                output_path=out,
                duration_sec=duration_sec,
                file_size_bytes=out.stat().st_size,
                ffmpeg_elapsed_sec=0.0,
            )

        # ffmpeg 커맨드
        # -ss 를 -i 앞에 두어 input-seek (빠른 keyframe 기반)
        # -t 로 구간 길이 지정
        # -c copy 로 재인코딩 없이 스트림 복사
        # -avoid_negative_ts make_zero: 복사 시 타임스탬프 음수 방지
        # -y 로 기존 파일 덮어쓰기 허용 (위 멱등 체크 통과 시)
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-y",
            "-ss", f"{start_offset_sec:.3f}",
            "-i", str(src),
            "-t", f"{duration_sec:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(out),
        ]

        import time as _time
        t0 = _time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self._timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ClipFileExtractionError(
                f"ffmpeg 타임아웃 ({self._timeout_sec}s): {src}"
            ) from e
        except OSError as e:
            raise ClipFileExtractionError(f"ffmpeg 실행 실패: {e}") from e

        elapsed = _time.monotonic() - t0

        if proc.returncode != 0:
            stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise ClipFileExtractionError(
                f"ffmpeg returncode={proc.returncode}: {stderr[:400]}"
            )

        if not out.exists() or out.stat().st_size == 0:
            raise ClipFileExtractionError(f"출력 파일이 비어있음: {out}")

        size = out.stat().st_size
        _logger.info(
            "클립 추출 완료: %s (%.2fs, %d bytes, ffmpeg %.2fs)",
            out.name, duration_sec, size, elapsed,
        )
        return ClipFileResult(
            output_path=out,
            duration_sec=duration_sec,
            file_size_bytes=size,
            ffmpeg_elapsed_sec=elapsed,
        )


__all__ = [
    "ClipFileExtractor",
    "ClipFileResult",
    "ClipFileExtractionError",
]
