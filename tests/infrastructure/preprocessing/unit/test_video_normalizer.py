# -*- coding: utf-8 -*-
"""infrastructure/preprocessing/video_normalizer.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
import cv2
import numpy as np

from infrastructure.preprocessing.video_normalizer import (
    DEFAULT_PAD_COLOR,
    DEFAULT_STRIDE,
    MAX_NORMALIZE_BATCH,
    FrameNormalizer,
    NormalizationConfig,
    NormalizationStats,
    __all__ as MODULE_ALL,
    __version__ as MODULE_VERSION,
)
from shared.constants.video_constants import (
    ANALYSIS_NORMALIZED_RESOLUTION,
    MAX_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
    ColorSpace,
)
from shared.dto.video_dto import FrameData, FrameStatus, VideoResolution


# =============================================================================
# 헬퍼
# =============================================================================

def _make_frame(
    width: int = 640,
    height: int = 480,
    channels: int = 3,
    index: int = 0,
    timestamp: float = 0.0,
    status: FrameStatus = FrameStatus.VALID,
    fill: int = 0,
) -> FrameData:
    """테스트용 합성 FrameData 생성."""
    if channels == 1:
        image = np.full((height, width), fill, dtype=np.uint8)
    else:
        image = np.full((height, width, channels), fill, dtype=np.uint8)
    return FrameData(
        image=image,
        index=index,
        timestamp=timestamp,
        status=status,
    )


def _make_invalid_frame() -> FrameData:
    """유효하지 않은 프레임 생성 (status=CORRUPT)."""
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return FrameData(
        image=image,
        index=0,
        timestamp=0.0,
        status=FrameStatus.CORRUPT,
    )


# =============================================================================
# 상수 검증
# =============================================================================


class TestConstants:
    """모듈 상수 검증."""

    def test_default_pad_color_type(self) -> None:
        assert isinstance(DEFAULT_PAD_COLOR, tuple)

    def test_default_pad_color_length(self) -> None:
        assert len(DEFAULT_PAD_COLOR) == 3

    def test_default_pad_color_values(self) -> None:
        assert DEFAULT_PAD_COLOR == (114, 114, 114)

    def test_max_normalize_batch_type(self) -> None:
        assert isinstance(MAX_NORMALIZE_BATCH, int)

    def test_max_normalize_batch_value(self) -> None:
        assert MAX_NORMALIZE_BATCH == 1000

    def test_default_stride_type(self) -> None:
        assert isinstance(DEFAULT_STRIDE, int)

    def test_default_stride_value(self) -> None:
        assert DEFAULT_STRIDE == 32


# =============================================================================
# NormalizationConfig
# =============================================================================


class TestNormalizationConfig:
    """NormalizationConfig 단위 테스트."""

    def test_defaults(self) -> None:
        cfg = NormalizationConfig()
        assert cfg.target_width == ANALYSIS_NORMALIZED_RESOLUTION[0]
        assert cfg.target_height == ANALYSIS_NORMALIZED_RESOLUTION[1]
        assert cfg.color_space == ColorSpace.BGR
        assert cfg.keep_aspect_ratio is True
        assert cfg.pad_color == DEFAULT_PAD_COLOR
        assert cfg.stride == DEFAULT_STRIDE
        assert cfg.interpolation == cv2.INTER_LINEAR

    def test_clamping_min_width(self) -> None:
        cfg = NormalizationConfig(target_width=1, target_height=MIN_VIDEO_HEIGHT)
        assert cfg.target_width == MIN_VIDEO_WIDTH

    def test_clamping_max_width(self) -> None:
        cfg = NormalizationConfig(target_width=99999, target_height=1080)
        assert cfg.target_width == MAX_VIDEO_WIDTH

    def test_clamping_min_height(self) -> None:
        cfg = NormalizationConfig(target_width=1920, target_height=1)
        assert cfg.target_height == MIN_VIDEO_HEIGHT

    def test_clamping_max_height(self) -> None:
        cfg = NormalizationConfig(target_width=1920, target_height=99999)
        assert cfg.target_height == MAX_VIDEO_HEIGHT

    def test_clamping_stride_min(self) -> None:
        cfg = NormalizationConfig(stride=-5)
        assert cfg.stride >= 1

    def test_clamping_stride_max(self) -> None:
        cfg = NormalizationConfig(stride=9999)
        assert cfg.stride <= 128

    def test_target_resolution_property(self) -> None:
        cfg = NormalizationConfig(target_width=1280, target_height=720)
        assert cfg.target_resolution == (1280, 720)

    def test_repr_contains_resolution(self) -> None:
        cfg = NormalizationConfig(target_width=1920, target_height=1080)
        r = repr(cfg)
        assert "1920" in r
        assert "1080" in r

    def test_repr_contains_color_space(self) -> None:
        cfg = NormalizationConfig(color_space=ColorSpace.RGB)
        r = repr(cfg)
        assert ColorSpace.RGB.value in r

    def test_slots_defined(self) -> None:
        cfg = NormalizationConfig()
        assert hasattr(cfg, "__slots__")


# =============================================================================
# NormalizationStats
# =============================================================================


class TestNormalizationStats:
    """NormalizationStats 단위 테스트."""

    def test_defaults_zero(self) -> None:
        stats = NormalizationStats()
        assert stats.frames_normalized == 0
        assert stats.frames_passed == 0
        assert stats.frames_failed == 0
        assert stats.total_time_sec == 0.0

    def test_total_frames_empty(self) -> None:
        stats = NormalizationStats()
        assert stats.total_frames == 0

    def test_total_frames_sum(self) -> None:
        stats = NormalizationStats(
            frames_normalized=10, frames_passed=5, frames_failed=2
        )
        assert stats.total_frames == 17

    def test_avg_time_ms_zero_division(self) -> None:
        stats = NormalizationStats()
        assert stats.avg_time_ms == 0.0

    def test_avg_time_ms_calculation(self) -> None:
        stats = NormalizationStats(
            frames_normalized=8, frames_passed=2, total_time_sec=0.5
        )
        # 처리된 = 8 + 2 = 10, avg = (0.5 / 10) * 1000 = 50ms
        assert abs(stats.avg_time_ms - 50.0) < 1e-6

    def test_repr_contains_counts(self) -> None:
        stats = NormalizationStats(
            frames_normalized=3, frames_passed=1, frames_failed=1
        )
        r = repr(stats)
        assert "normalized=3" in r
        assert "passed=1" in r
        assert "failed=1" in r

    def test_slots_defined(self) -> None:
        stats = NormalizationStats()
        assert hasattr(stats, "__slots__")


# =============================================================================
# FrameNormalizer
# =============================================================================


class TestFrameNormalizer:
    """FrameNormalizer 단위 테스트."""

    def test_creation_default_config(self) -> None:
        normalizer = FrameNormalizer()
        assert normalizer.config.target_width == ANALYSIS_NORMALIZED_RESOLUTION[0]
        assert normalizer.config.target_height == ANALYSIS_NORMALIZED_RESOLUTION[1]

    def test_creation_custom_config(self) -> None:
        cfg = NormalizationConfig(target_width=1280, target_height=720)
        normalizer = FrameNormalizer(cfg)
        assert normalizer.config.target_width == 1280
        assert normalizer.config.target_height == 720

    def test_normalize_resizes_frame(self) -> None:
        """640x480 -> 1920x1080 정규화 검증."""
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1920, target_height=1080)
        )
        frame = _make_frame(640, 480)
        result = normalizer.normalize(frame)
        assert result.image.shape[1] == 1920
        assert result.image.shape[0] == 1080

    def test_normalize_preserves_index(self) -> None:
        normalizer = FrameNormalizer()
        frame = _make_frame(640, 480, index=42)
        result = normalizer.normalize(frame)
        assert result.index == 42

    def test_normalize_preserves_timestamp(self) -> None:
        normalizer = FrameNormalizer()
        frame = _make_frame(640, 480, timestamp=1.5)
        result = normalizer.normalize(frame)
        assert result.timestamp == 1.5

    def test_normalize_invalid_frame_returns_original(self) -> None:
        normalizer = FrameNormalizer()
        frame = _make_invalid_frame()
        result = normalizer.normalize(frame)
        assert result is frame

    def test_normalize_invalid_increments_failed(self) -> None:
        normalizer = FrameNormalizer()
        frame = _make_invalid_frame()
        normalizer.normalize(frame)
        assert normalizer.stats.frames_failed == 1

    def test_normalize_batch_multiple_frames(self) -> None:
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1920, target_height=1080)
        )
        frames = [_make_frame(640, 480, index=i) for i in range(5)]
        results = normalizer.normalize_batch(frames)
        assert len(results) == 5
        for r in results:
            assert r.image.shape[1] == 1920
            assert r.image.shape[0] == 1080

    def test_normalize_batch_respects_max(self) -> None:
        normalizer = FrameNormalizer()
        # MAX_NORMALIZE_BATCH 보다 많은 리스트 전달 시 잘림 확인
        frames = [_make_frame(640, 480, index=i) for i in range(MAX_NORMALIZE_BATCH + 5)]
        results = normalizer.normalize_batch(frames)
        assert len(results) == MAX_NORMALIZE_BATCH

    def test_normalize_image_standalone(self) -> None:
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1280, target_height=720)
        )
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = normalizer.normalize_image(image)
        assert result.shape[1] == 1280
        assert result.shape[0] == 720

    def test_normalize_image_empty_returns_empty(self) -> None:
        normalizer = FrameNormalizer()
        image = np.array([], dtype=np.uint8)
        result = normalizer.normalize_image(image)
        assert result.size == 0

    def test_letterbox_padding_corner_color(self) -> None:
        """letterbox 패딩 시 모서리 색상이 pad_color인지 검증."""
        pad_color = (50, 100, 150)
        cfg = NormalizationConfig(
            target_width=1920,
            target_height=1080,
            keep_aspect_ratio=True,
            pad_color=pad_color,
        )
        normalizer = FrameNormalizer(cfg)
        # 극단적 종횡비: 640x100 -> 1920x1080에서 상하 패딩 발생
        frame = _make_frame(640, 100, fill=200)
        result = normalizer.normalize(frame)
        # 상단 좌측 모서리는 패딩 영역이어야 함
        corner_pixel = result.image[0, 0]
        assert tuple(corner_pixel) == pad_color

    def test_color_space_bgr_to_rgb(self) -> None:
        """BGR -> RGB 변환 검증."""
        cfg = NormalizationConfig(
            target_width=640, target_height=480,
            color_space=ColorSpace.RGB,
            keep_aspect_ratio=False,
        )
        normalizer = FrameNormalizer(cfg)
        # BGR 이미지: 파란색(255, 0, 0)
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        image[:, :] = (255, 0, 0)  # BGR에서 파란색
        frame = FrameData(image=image, index=0, timestamp=0.0)
        result = normalizer.normalize(frame)
        # RGB로 변환 후: (0, 0, 255) 이어야 함
        pixel = result.image[0, 0]
        assert pixel[0] == 0    # R
        assert pixel[1] == 0    # G
        assert pixel[2] == 255  # B

    def test_color_space_bgr_to_gray(self) -> None:
        """BGR -> GRAY 변환 검증."""
        cfg = NormalizationConfig(
            target_width=640, target_height=480,
            color_space=ColorSpace.GRAY,
            keep_aspect_ratio=False,
        )
        normalizer = FrameNormalizer(cfg)
        image = np.full((480, 640, 3), 128, dtype=np.uint8)
        frame = FrameData(image=image, index=0, timestamp=0.0)
        result = normalizer.normalize(frame)
        # 그레이스케일 결과는 2차원
        assert result.image.ndim == 2

    def test_stats_tracking_normalized_count(self) -> None:
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1920, target_height=1080)
        )
        for i in range(3):
            normalizer.normalize(_make_frame(640, 480, index=i))
        stats = normalizer.stats
        assert stats.frames_normalized == 3

    def test_stats_tracking_passed_count(self) -> None:
        """이미 목표 크기인 프레임은 passed로 카운트."""
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1920, target_height=1080)
        )
        frame = _make_frame(1920, 1080)
        normalizer.normalize(frame)
        stats = normalizer.stats
        assert stats.frames_passed == 1
        assert stats.frames_normalized == 0

    def test_stats_total_time_positive(self) -> None:
        normalizer = FrameNormalizer()
        normalizer.normalize(_make_frame(640, 480))
        stats = normalizer.stats
        assert stats.total_time_sec >= 0.0

    def test_reset_stats(self) -> None:
        normalizer = FrameNormalizer()
        normalizer.normalize(_make_frame(640, 480))
        normalizer.reset_stats()
        stats = normalizer.stats
        assert stats.frames_normalized == 0
        assert stats.frames_passed == 0
        assert stats.frames_failed == 0
        assert stats.total_time_sec == 0.0

    def test_repr_contains_resolution(self) -> None:
        normalizer = FrameNormalizer(
            NormalizationConfig(target_width=1920, target_height=1080)
        )
        r = repr(normalizer)
        assert "1920" in r
        assert "1080" in r

    def test_normalize_same_size_no_resize(self) -> None:
        """이미 목표 해상도인 프레임은 리사이즈 없이 통과."""
        cfg = NormalizationConfig(target_width=640, target_height=480)
        normalizer = FrameNormalizer(cfg)
        frame = _make_frame(640, 480, fill=77)
        result = normalizer.normalize(frame)
        assert result.image.shape == (480, 640, 3)
        # 값이 보존되어야 함
        assert result.image[0, 0, 0] == 77

    def test_no_aspect_ratio_stretch(self) -> None:
        """keep_aspect_ratio=False 시 정확히 목표 크기로 늘림."""
        cfg = NormalizationConfig(
            target_width=1920, target_height=1080,
            keep_aspect_ratio=False,
        )
        normalizer = FrameNormalizer(cfg)
        frame = _make_frame(320, 240)
        result = normalizer.normalize(frame)
        assert result.image.shape[1] == 1920
        assert result.image.shape[0] == 1080


# =============================================================================
# 모듈 Export / 버전
# =============================================================================


class TestModuleExports:
    """모듈 __all__, __version__ 검증."""

    def test_all_contains_frame_normalizer(self) -> None:
        assert "FrameNormalizer" in MODULE_ALL

    def test_all_contains_normalization_config(self) -> None:
        assert "NormalizationConfig" in MODULE_ALL

    def test_all_contains_normalization_stats(self) -> None:
        assert "NormalizationStats" in MODULE_ALL

    def test_all_contains_default_pad_color(self) -> None:
        assert "DEFAULT_PAD_COLOR" in MODULE_ALL

    def test_all_contains_max_normalize_batch(self) -> None:
        assert "MAX_NORMALIZE_BATCH" in MODULE_ALL

    def test_all_contains_default_stride(self) -> None:
        assert "DEFAULT_STRIDE" in MODULE_ALL

    def test_version(self) -> None:
        assert MODULE_VERSION == "1.0.0"
