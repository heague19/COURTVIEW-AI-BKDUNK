# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: frame_extractor.py
설명: 프레임 추출 엔진
      - FrameExtractor: 비디오에서 프레임 추출 (순차/키프레임/시간 기반)
      - ExtractionConfig: 추출 설정 (FPS, 범위, 품질 필터)
      - ExtractionResult: 추출 결과 요약
      - 품질 필터링 (블러/밝기 검사), 중복 프레임 제거 (pHash)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
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
    BLUR_DETECTION_THRESHOLD,
    BRIGHTNESS_MAX_THRESHOLD,
    BRIGHTNESS_MIN_THRESHOLD,
)
from shared.dto.video_dto import (
    FrameData,
)

from infrastructure.preprocessing.video_decoder import (
    VideoDecoder,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 추출 프레임 수 (메모리 방어)
MAX_EXTRACTION_FRAMES: Final[int] = 100_000

# 품질 검사 최소 이미지 크기
MIN_QUALITY_CHECK_SIZE: Final[int] = 64

# 중복 제거 해시 차이 임계값
DUPLICATE_HASH_THRESHOLD: Final[int] = 5

# 키프레임 추출 최대 수
MAX_KEYFRAMES: Final[int] = 500


# =============================================================================
# ExtractionConfig: 추출 설정
# =============================================================================

@dataclass(slots=True)
class ExtractionConfig:
    """프레임 추출 설정.

    Attributes:
        target_fps: 추출 목표 FPS (None=원본 FPS 유지)
        start_time_sec: 시작 시간 (초)
        end_time_sec: 종료 시간 (초, None=끝까지)
        max_frames: 최대 추출 프레임 수
        enable_quality_filter: 품질 필터 활성화 (블러/밝기)
        enable_duplicate_filter: 중복 프레임 제거
        blur_threshold: 블러 판정 임계값 (라플라시안 분산)
        brightness_min: 최소 밝기
        brightness_max: 최대 밝기
        camera_id: 카메라 ID (멀티카메라용)
    """

    target_fps: float | None = None
    start_time_sec: float = 0.0
    end_time_sec: float | None = None
    max_frames: int = MAX_EXTRACTION_FRAMES
    enable_quality_filter: bool = False
    enable_duplicate_filter: bool = False
    blur_threshold: float = BLUR_DETECTION_THRESHOLD
    brightness_min: int = BRIGHTNESS_MIN_THRESHOLD
    brightness_max: int = BRIGHTNESS_MAX_THRESHOLD
    camera_id: str | None = None

    def __post_init__(self) -> None:
        self.start_time_sec = max(0.0, self.start_time_sec)
        self.max_frames = min(max(1, self.max_frames), MAX_EXTRACTION_FRAMES)
        self.blur_threshold = max(1.0, self.blur_threshold)
        self.brightness_min = max(0, min(255, self.brightness_min))
        self.brightness_max = max(self.brightness_min, min(255, self.brightness_max))

    def __repr__(self) -> str:
        fps_str = f"{self.target_fps:.1f}" if self.target_fps else "원본"
        return (
            f"ExtractionConfig(fps={fps_str}, "
            f"range=[{self.start_time_sec:.1f}s~"
            f"{'끝' if self.end_time_sec is None else f'{self.end_time_sec:.1f}s'}], "
            f"quality={'ON' if self.enable_quality_filter else 'OFF'})"
        )


# =============================================================================
# ExtractionResult: 추출 결과
# =============================================================================

@dataclass(slots=True)
class ExtractionResult:
    """프레임 추출 결과 요약.

    Attributes:
        total_extracted: 추출된 프레임 수
        total_skipped: 건너뛴 프레임 수
        total_filtered: 품질 필터로 제외된 프레임 수
        duplicates_removed: 중복 제거된 프레임 수
        extraction_time_sec: 추출 소요 시간
        source_fps: 원본 FPS
        effective_fps: 실제 적용 FPS
    """

    total_extracted: int = 0
    total_skipped: int = 0
    total_filtered: int = 0
    duplicates_removed: int = 0
    extraction_time_sec: float = 0.0
    source_fps: float = 0.0
    effective_fps: float = 0.0

    @property
    def total_processed(self) -> int:
        """처리된 총 프레임 수."""
        return (
            self.total_extracted
            + self.total_skipped
            + self.total_filtered
            + self.duplicates_removed
        )

    @property
    def extraction_rate(self) -> float:
        """추출 비율."""
        if self.total_processed == 0:
            return 0.0
        return self.total_extracted / self.total_processed

    def __repr__(self) -> str:
        return (
            f"ExtractionResult(extracted={self.total_extracted}, "
            f"skipped={self.total_skipped}, "
            f"filtered={self.total_filtered}, "
            f"dupes={self.duplicates_removed}, "
            f"time={self.extraction_time_sec:.2f}s)"
        )


# =============================================================================
# FrameExtractor: 프레임 추출 엔진
# =============================================================================

class FrameExtractor:
    """비디오에서 프레임 추출.

    VideoDecoder를 사용하여 비디오를 디코딩하고,
    FPS 조정/품질 필터/중복 제거를 적용하여 FrameData를 출력.

    사용 예시::

        config = ExtractionConfig(target_fps=30, enable_quality_filter=True)
        extractor = FrameExtractor(config)
        result = ExtractionResult()

        for frame_data in extractor.extract("game.mp4"):
            process(frame_data)

        print(extractor.result)
    """

    __slots__ = (
        "_lock",
        "_config",
        "_decoder",
        "_result",
        "_last_hash",
    )

    def __init__(self, config: ExtractionConfig | None = None) -> None:
        self._lock = threading.RLock()
        self._config = config or ExtractionConfig()
        self._decoder = VideoDecoder(camera_id=self._config.camera_id)
        self._result = ExtractionResult()
        self._last_hash: int = 0

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def config(self) -> ExtractionConfig:
        """추출 설정."""
        return self._config

    @property
    def result(self) -> ExtractionResult:
        """추출 결과 (방어적 복사)."""
        with self._lock:
            return ExtractionResult(
                total_extracted=self._result.total_extracted,
                total_skipped=self._result.total_skipped,
                total_filtered=self._result.total_filtered,
                duplicates_removed=self._result.duplicates_removed,
                extraction_time_sec=self._result.extraction_time_sec,
                source_fps=self._result.source_fps,
                effective_fps=self._result.effective_fps,
            )

    # =========================================================================
    # 프레임 추출
    # =========================================================================

    def extract(self, file_path: str) -> Generator[FrameData, None, None]:
        """비디오에서 프레임 추출 제너레이터.

        Args:
            file_path: 비디오 파일 경로

        Yields:
            FrameData (필터링 통과 프레임)
        """
        t0 = time.monotonic()

        with self._lock:
            self._result = ExtractionResult()
            self._last_hash = 0

        if not self._decoder.open(file_path):
            return

        try:
            source_fps = self._decoder.fps
            target_fps = self._config.target_fps or source_fps

            with self._lock:
                self._result.source_fps = source_fps
                self._result.effective_fps = target_fps

            # FPS 기반 프레임 간격 계산
            step = max(1, round(source_fps / target_fps)) if target_fps < source_fps else 1

            # 시작 프레임 계산
            start_frame = int(self._config.start_time_sec * source_fps)

            # 종료 프레임 계산
            end_frame: int | None = None
            if self._config.end_time_sec is not None:
                end_frame = int(self._config.end_time_sec * source_fps)

            count = 0

            for frame_data in self._decoder.decode_sequential(
                start_frame=start_frame, step=step
            ):
                # 종료 조건
                if end_frame is not None and frame_data.index >= end_frame:
                    break

                if count >= self._config.max_frames:
                    break

                # 품질 필터
                if self._config.enable_quality_filter:
                    if not self._check_quality(frame_data.image):
                        with self._lock:
                            self._result.total_filtered += 1
                        continue

                # 중복 필터
                if self._config.enable_duplicate_filter:
                    if self._is_duplicate(frame_data.image):
                        with self._lock:
                            self._result.duplicates_removed += 1
                        continue

                count += 1
                with self._lock:
                    self._result.total_extracted += 1

                yield frame_data

        finally:
            self._decoder.close()
            with self._lock:
                self._result.extraction_time_sec = time.monotonic() - t0

    def extract_keyframes(
        self,
        file_path: str,
        num_keyframes: int = 10,
    ) -> list[FrameData]:
        """키프레임 추출 (균등 간격).

        Args:
            file_path: 비디오 파일 경로
            num_keyframes: 추출할 키프레임 수

        Returns:
            FrameData 리스트
        """
        num_keyframes = min(max(1, num_keyframes), MAX_KEYFRAMES)

        if not self._decoder.open(file_path):
            return []

        try:
            total = self._decoder.total_frames
            if total <= 0:
                return []

            # 균등 간격 프레임 인덱스
            if num_keyframes >= total:
                indices = list(range(total))
            else:
                step = total / num_keyframes
                indices = [int(i * step) for i in range(num_keyframes)]

            result: list[FrameData] = []
            for idx in indices:
                frame_data = self._decoder.decode_frame(idx)
                if frame_data is not None:
                    result.append(frame_data)

            return result
        finally:
            self._decoder.close()

    def extract_at_times(
        self,
        file_path: str,
        times_sec: list[float],
    ) -> list[FrameData]:
        """특정 시간대 프레임 추출.

        Args:
            file_path: 비디오 파일 경로
            times_sec: 추출할 시간 목록 (초)

        Returns:
            FrameData 리스트
        """
        if not times_sec:
            return []

        if not self._decoder.open(file_path):
            return []

        try:
            fps = self._decoder.fps
            result: list[FrameData] = []

            for t in times_sec:
                frame_index = int(t * fps)
                frame_data = self._decoder.decode_frame(frame_index)
                if frame_data is not None:
                    result.append(frame_data)

            return result
        finally:
            self._decoder.close()

    # =========================================================================
    # 품질 검사
    # =========================================================================

    def _check_quality(self, image: NDArray[np.uint8]) -> bool:
        """프레임 품질 검사 (블러 + 밝기).

        Args:
            image: BGR 이미지

        Returns:
            품질 통과 여부
        """
        if image.size == 0:
            return False

        h, w = image.shape[:2]
        if h < MIN_QUALITY_CHECK_SIZE or w < MIN_QUALITY_CHECK_SIZE:
            return True  # 너무 작으면 검사 스킵

        # 그레이스케일 변환
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 블러 검사 (라플라시안 분산)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < self._config.blur_threshold:
            return False

        # 밝기 검사
        mean_brightness = float(np.mean(gray))
        if mean_brightness < self._config.brightness_min:
            return False
        if mean_brightness > self._config.brightness_max:
            return False

        return True

    def _is_duplicate(self, image: NDArray[np.uint8]) -> bool:
        """중복 프레임 판정 (간이 해시).

        Args:
            image: BGR 이미지

        Returns:
            중복 여부
        """
        # 간이 평균 해시 (8×8 → 64비트)
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        mean_val = np.mean(resized)
        hash_val = 0
        for i, pixel in enumerate(resized.flatten()):
            if pixel > mean_val:
                hash_val |= 1 << i

        with self._lock:
            if self._last_hash == 0:
                self._last_hash = hash_val
                return False

            # 해밍 거리
            diff = bin(hash_val ^ self._last_hash).count("1")
            self._last_hash = hash_val

            return diff <= DUPLICATE_HASH_THRESHOLD

    def __repr__(self) -> str:
        return (
            f"FrameExtractor(config={self._config!r}, "
            f"result={self._result!r})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "FrameExtractor",
    # 데이터 클래스
    "ExtractionConfig",
    "ExtractionResult",
    # 상수
    "MAX_EXTRACTION_FRAMES",
    "MIN_QUALITY_CHECK_SIZE",
    "DUPLICATE_HASH_THRESHOLD",
    "MAX_KEYFRAMES",
]

__version__ = "1.0.0"
