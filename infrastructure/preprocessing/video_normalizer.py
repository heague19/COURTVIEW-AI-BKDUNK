# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: video_normalizer.py
설명: 해상도/색공간 정규화
      - NormalizationConfig: 정규화 설정 (목표 해상도, 색공간, 패딩)
      - FrameNormalizer: 프레임 정규화 (리사이즈, 색공간 변환, 패딩)
      - NormalizationStats: 정규화 통계
      - 분석 표준 해상도 (1920×1080) 기준, 종횡비 유지 + letterbox 패딩

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
from dataclasses import dataclass
from typing import Final

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
    MAX_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
    ColorSpace,
)
from shared.dto.video_dto import (
    FrameData,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 패딩 색상 (BGR)
DEFAULT_PAD_COLOR: Final[tuple[int, int, int]] = (114, 114, 114)

# 최대 배치 정규화 크기
MAX_NORMALIZE_BATCH: Final[int] = 1000

# stride 정렬 (모델 입력 호환)
DEFAULT_STRIDE: Final[int] = 32


# =============================================================================
# NormalizationConfig: 정규화 설정
# =============================================================================

@dataclass(slots=True)
class NormalizationConfig:
    """프레임 정규화 설정.

    Attributes:
        target_width: 목표 너비
        target_height: 목표 높이
        color_space: 출력 색공간
        keep_aspect_ratio: 종횡비 유지 여부
        pad_color: 패딩 색상 (BGR)
        stride: stride 정렬 값 (모델 호환)
        interpolation: 보간법
    """

    target_width: int = ANALYSIS_NORMALIZED_RESOLUTION[0]
    target_height: int = ANALYSIS_NORMALIZED_RESOLUTION[1]
    color_space: ColorSpace = ColorSpace.BGR
    keep_aspect_ratio: bool = True
    pad_color: tuple[int, int, int] = DEFAULT_PAD_COLOR
    stride: int = DEFAULT_STRIDE
    interpolation: int = cv2.INTER_LINEAR

    def __post_init__(self) -> None:
        self.target_width = max(
            MIN_VIDEO_WIDTH, min(self.target_width, MAX_VIDEO_WIDTH)
        )
        self.target_height = max(
            MIN_VIDEO_HEIGHT, min(self.target_height, MAX_VIDEO_HEIGHT)
        )
        self.stride = max(1, min(self.stride, 128))

    @property
    def target_resolution(self) -> tuple[int, int]:
        """목표 해상도 (width, height)."""
        return (self.target_width, self.target_height)

    def __repr__(self) -> str:
        return (
            f"NormalizationConfig({self.target_width}x{self.target_height}, "
            f"cs={self.color_space.value}, "
            f"aspect={'유지' if self.keep_aspect_ratio else '무시'})"
        )


# =============================================================================
# NormalizationStats: 정규화 통계
# =============================================================================

@dataclass(slots=True)
class NormalizationStats:
    """정규화 통계.

    Attributes:
        frames_normalized: 정규화된 프레임 수
        frames_passed: 변환 불필요 (이미 목표 크기)
        frames_failed: 정규화 실패 수
        total_time_sec: 총 소요 시간
    """

    frames_normalized: int = 0
    frames_passed: int = 0
    frames_failed: int = 0
    total_time_sec: float = 0.0

    @property
    def total_frames(self) -> int:
        """처리된 총 프레임."""
        return self.frames_normalized + self.frames_passed + self.frames_failed

    @property
    def avg_time_ms(self) -> float:
        """프레임당 평균 시간 (ms)."""
        processed = self.frames_normalized + self.frames_passed
        if processed == 0:
            return 0.0
        return (self.total_time_sec / processed) * 1000.0

    def __repr__(self) -> str:
        return (
            f"NormalizationStats(normalized={self.frames_normalized}, "
            f"passed={self.frames_passed}, "
            f"failed={self.frames_failed}, "
            f"avg={self.avg_time_ms:.1f}ms)"
        )


# =============================================================================
# FrameNormalizer: 프레임 정규화 엔진
# =============================================================================

class FrameNormalizer:
    """프레임 해상도/색공간 정규화.

    분석 파이프라인의 표준 입력(1920×1080, BGR)을 보장.
    종횡비 유지 + letterbox 패딩 기본 적용.

    사용 예시::

        config = NormalizationConfig(target_width=1920, target_height=1080)
        normalizer = FrameNormalizer(config)
        normalized = normalizer.normalize(frame_data)
    """

    __slots__ = ("_lock", "_config", "_stats")

    def __init__(self, config: NormalizationConfig | None = None) -> None:
        self._lock = threading.RLock()
        self._config = config or NormalizationConfig()
        self._stats = NormalizationStats()

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def config(self) -> NormalizationConfig:
        """정규화 설정."""
        return self._config

    @property
    def stats(self) -> NormalizationStats:
        """통계 (방어적 복사)."""
        with self._lock:
            return NormalizationStats(
                frames_normalized=self._stats.frames_normalized,
                frames_passed=self._stats.frames_passed,
                frames_failed=self._stats.frames_failed,
                total_time_sec=self._stats.total_time_sec,
            )

    # =========================================================================
    # 정규화
    # =========================================================================

    def normalize(self, frame: FrameData) -> FrameData:
        """단일 프레임 정규화.

        Args:
            frame: 원본 FrameData

        Returns:
            정규화된 FrameData
        """
        if not frame.is_valid:
            with self._lock:
                self._stats.frames_failed += 1
            return frame

        image = frame.image
        h, w = image.shape[:2]
        tw, th = self._config.target_width, self._config.target_height

        t0 = time.monotonic()

        # 이미 목표 크기이면 색공간만 체크
        if w == tw and h == th:
            converted = self._convert_color_space(image)
            with self._lock:
                self._stats.frames_passed += 1
                self._stats.total_time_sec += time.monotonic() - t0
            return FrameData(
                image=converted,
                index=frame.index,
                timestamp=frame.timestamp,
                status=frame.status,
                camera_id=frame.camera_id,
            )

        # 리사이즈
        if self._config.keep_aspect_ratio:
            resized = self._resize_letterbox(image, tw, th)
        else:
            resized = cv2.resize(
                image, (tw, th),
                interpolation=self._config.interpolation,
            )

        # 색공간 변환
        converted = self._convert_color_space(resized)

        with self._lock:
            self._stats.frames_normalized += 1
            self._stats.total_time_sec += time.monotonic() - t0

        return FrameData(
            image=converted,
            index=frame.index,
            timestamp=frame.timestamp,
            status=frame.status,
            camera_id=frame.camera_id,
        )

    def normalize_batch(self, frames: list[FrameData]) -> list[FrameData]:
        """배치 정규화.

        Args:
            frames: FrameData 리스트

        Returns:
            정규화된 FrameData 리스트
        """
        count = min(len(frames), MAX_NORMALIZE_BATCH)
        return [self.normalize(f) for f in frames[:count]]

    def normalize_image(
        self,
        image: NDArray[np.uint8],
    ) -> NDArray[np.uint8]:
        """이미지만 정규화 (FrameData 없이).

        Args:
            image: 입력 이미지

        Returns:
            정규화된 이미지
        """
        if image.size == 0:
            return image

        tw, th = self._config.target_width, self._config.target_height

        if self._config.keep_aspect_ratio:
            resized = self._resize_letterbox(image, tw, th)
        else:
            resized = cv2.resize(
                image, (tw, th),
                interpolation=self._config.interpolation,
            )

        return self._convert_color_space(resized)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _resize_letterbox(
        self,
        image: NDArray[np.uint8],
        target_w: int,
        target_h: int,
    ) -> NDArray[np.uint8]:
        """종횡비 유지 리사이즈 + letterbox 패딩.

        Args:
            image: 입력 이미지
            target_w: 목표 너비
            target_h: 목표 높이

        Returns:
            리사이즈 + 패딩된 이미지
        """
        h, w = image.shape[:2]

        # 스케일 계산
        scale = min(target_w / w, target_h / h)

        new_w = int(w * scale)
        new_h = int(h * scale)

        # stride 정렬
        stride = self._config.stride
        if stride > 1:
            new_w = (new_w // stride) * stride
            new_h = (new_h // stride) * stride

        # 최소 크기 보장
        new_w = max(stride, new_w)
        new_h = max(stride, new_h)

        # 리사이즈
        resized = cv2.resize(
            image, (new_w, new_h),
            interpolation=self._config.interpolation,
        )

        # 패딩 추가
        if new_w == target_w and new_h == target_h:
            return resized

        channels = image.shape[2] if image.ndim == 3 else 1
        if channels > 1:
            canvas = np.full(
                (target_h, target_w, channels),
                self._config.pad_color[:channels],
                dtype=np.uint8,
            )
        else:
            canvas = np.full(
                (target_h, target_w),
                self._config.pad_color[0],
                dtype=np.uint8,
            )

        # 중앙 배치
        pad_top = (target_h - new_h) // 2
        pad_left = (target_w - new_w) // 2

        if image.ndim == 3:
            canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w, :] = resized
        else:
            canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized

        return canvas

    def _convert_color_space(
        self,
        image: NDArray[np.uint8],
    ) -> NDArray[np.uint8]:
        """색공간 변환.

        Args:
            image: 입력 이미지

        Returns:
            변환된 이미지
        """
        target_cs = self._config.color_space

        # 기본 BGR → 변환 불필요
        if target_cs == ColorSpace.BGR:
            return image

        if image.ndim == 2:
            # 그레이스케일 입력
            if target_cs == ColorSpace.GRAY:
                return image
            if target_cs == ColorSpace.RGB:
                return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        # 3채널 BGR 입력
        if target_cs == ColorSpace.RGB:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if target_cs == ColorSpace.GRAY:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if target_cs == ColorSpace.YUV:
            return cv2.cvtColor(image, cv2.COLOR_BGR2YUV)

        return image

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = NormalizationStats()

    def __repr__(self) -> str:
        return (
            f"FrameNormalizer({self._config.target_width}x"
            f"{self._config.target_height}, "
            f"stats={self._stats!r})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "FrameNormalizer",
    # 데이터 클래스
    "NormalizationConfig",
    "NormalizationStats",
    # 상수
    "DEFAULT_PAD_COLOR",
    "MAX_NORMALIZE_BATCH",
    "DEFAULT_STRIDE",
]

__version__ = "1.0.0"
