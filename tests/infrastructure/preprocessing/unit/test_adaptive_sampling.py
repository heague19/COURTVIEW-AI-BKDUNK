# -*- coding: utf-8 -*-
"""infrastructure/preprocessing/adaptive_sampling.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
import cv2
import numpy as np

from infrastructure.preprocessing.adaptive_sampling import (
    HISTOGRAM_BINS,
    MAX_MOTION_HISTORY,
    MOTION_HIGH_THRESHOLD,
    MOTION_LOW_THRESHOLD,
    AdaptiveSampler,
    SamplingConfig,
    SamplingStats,
    __all__ as MODULE_ALL,
    __version__ as MODULE_VERSION,
)
from shared.constants.video_constants import (
    ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES,
    ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES,
    MOTION_DETECTION_THRESHOLD,
    SCENE_CHANGE_THRESHOLD,
)
from shared.dto.video_dto import FrameData, FrameStatus


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

    def test_max_motion_history_type(self) -> None:
        assert isinstance(MAX_MOTION_HISTORY, int)

    def test_max_motion_history_value(self) -> None:
        assert MAX_MOTION_HISTORY == 60

    def test_histogram_bins_type(self) -> None:
        assert isinstance(HISTOGRAM_BINS, int)

    def test_histogram_bins_value(self) -> None:
        assert HISTOGRAM_BINS == 64

    def test_motion_low_threshold_type(self) -> None:
        assert isinstance(MOTION_LOW_THRESHOLD, float)

    def test_motion_low_threshold_value(self) -> None:
        assert MOTION_LOW_THRESHOLD == 5.0

    def test_motion_high_threshold_type(self) -> None:
        assert isinstance(MOTION_HIGH_THRESHOLD, float)

    def test_motion_high_threshold_value(self) -> None:
        assert MOTION_HIGH_THRESHOLD == 30.0

    def test_low_less_than_high(self) -> None:
        assert MOTION_LOW_THRESHOLD < MOTION_HIGH_THRESHOLD


# =============================================================================
# SamplingConfig
# =============================================================================


class TestSamplingConfig:
    """SamplingConfig 단위 테스트."""

    def test_defaults(self) -> None:
        cfg = SamplingConfig()
        assert cfg.min_interval == ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES
        assert cfg.max_interval == ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES
        assert cfg.motion_threshold == MOTION_DETECTION_THRESHOLD
        assert cfg.scene_change_threshold == SCENE_CHANGE_THRESHOLD
        assert cfg.enable_motion_detection is True
        assert cfg.enable_scene_detection is True

    def test_clamping_min_interval_floor(self) -> None:
        cfg = SamplingConfig(min_interval=-5)
        assert cfg.min_interval >= 1

    def test_clamping_max_interval_ceiling(self) -> None:
        cfg = SamplingConfig(max_interval=99999)
        assert cfg.max_interval <= ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES

    def test_max_interval_at_least_min(self) -> None:
        cfg = SamplingConfig(min_interval=5, max_interval=2)
        assert cfg.max_interval >= cfg.min_interval

    def test_clamping_motion_threshold_floor(self) -> None:
        cfg = SamplingConfig(motion_threshold=-10.0)
        assert cfg.motion_threshold >= 1.0

    def test_clamping_scene_threshold_floor(self) -> None:
        cfg = SamplingConfig(scene_change_threshold=-1.0)
        assert cfg.scene_change_threshold >= 1.0

    def test_repr_contains_interval(self) -> None:
        cfg = SamplingConfig(min_interval=2, max_interval=10)
        r = repr(cfg)
        assert "2" in r
        assert "10" in r

    def test_repr_contains_motion_on(self) -> None:
        cfg = SamplingConfig(enable_motion_detection=True)
        assert "ON" in repr(cfg)

    def test_repr_contains_scene_off(self) -> None:
        cfg = SamplingConfig(enable_scene_detection=False)
        r = repr(cfg)
        assert "OFF" in r

    def test_slots_defined(self) -> None:
        cfg = SamplingConfig()
        assert hasattr(cfg, "__slots__")


# =============================================================================
# SamplingStats
# =============================================================================


class TestSamplingStats:
    """SamplingStats 단위 테스트."""

    def test_defaults_zero(self) -> None:
        stats = SamplingStats()
        assert stats.frames_accepted == 0
        assert stats.frames_skipped == 0
        assert stats.scene_changes == 0
        assert stats.avg_motion_score == 0.0
        assert stats.avg_interval == 1.0

    def test_total_frames_empty(self) -> None:
        stats = SamplingStats()
        assert stats.total_frames == 0

    def test_total_frames_sum(self) -> None:
        stats = SamplingStats(frames_accepted=5, frames_skipped=10)
        assert stats.total_frames == 15

    def test_sample_rate_empty(self) -> None:
        stats = SamplingStats()
        assert stats.sample_rate == 0.0

    def test_sample_rate_calculation(self) -> None:
        stats = SamplingStats(frames_accepted=3, frames_skipped=7)
        assert abs(stats.sample_rate - 0.3) < 1e-6

    def test_sample_rate_all_accepted(self) -> None:
        stats = SamplingStats(frames_accepted=10, frames_skipped=0)
        assert abs(stats.sample_rate - 1.0) < 1e-6

    def test_repr_contains_accepted(self) -> None:
        stats = SamplingStats(frames_accepted=5, frames_skipped=3)
        r = repr(stats)
        assert "accepted=5" in r
        assert "skipped=3" in r

    def test_slots_defined(self) -> None:
        stats = SamplingStats()
        assert hasattr(stats, "__slots__")


# =============================================================================
# AdaptiveSampler
# =============================================================================


class TestAdaptiveSampler:
    """AdaptiveSampler 단위 테스트."""

    def test_creation_default_config(self) -> None:
        sampler = AdaptiveSampler()
        assert sampler.config.min_interval == ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES
        assert sampler.config.max_interval == ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES

    def test_creation_custom_config(self) -> None:
        cfg = SamplingConfig(min_interval=2, max_interval=8)
        sampler = AdaptiveSampler(cfg)
        assert sampler.config.min_interval == 2
        assert sampler.config.max_interval == 8

    def test_first_frame_always_sampled(self) -> None:
        """첫 프레임은 항상 선택되어야 함."""
        sampler = AdaptiveSampler()
        frame = _make_frame(640, 480, index=0)
        assert sampler.should_sample(frame) is True

    def test_invalid_frame_not_sampled(self) -> None:
        """유효하지 않은 프레임은 선택하지 않음."""
        sampler = AdaptiveSampler()
        frame = _make_invalid_frame()
        assert sampler.should_sample(frame) is False

    def test_static_frames_eventually_skip(self) -> None:
        """동일한 정적 프레임 반복 시 일부 프레임을 건너뜀."""
        cfg = SamplingConfig(min_interval=1, max_interval=10)
        sampler = AdaptiveSampler(cfg)
        # 30개의 동일한 검정 프레임 전달
        results = []
        for i in range(30):
            frame = _make_frame(640, 480, index=i, timestamp=i / 30.0, fill=0)
            results.append(sampler.should_sample(frame))
        # 전부 True가 아니어야 함 (일부 건너뜀)
        assert not all(results), "정적 프레임에서 모두 선택되면 안 됨"
        # 적어도 첫 프레임은 선택
        assert results[0] is True

    def test_scene_change_triggers_sample(self) -> None:
        """흰색 -> 검정 장면 전환 시 프레임이 선택되어야 함."""
        cfg = SamplingConfig(min_interval=1, max_interval=15)
        sampler = AdaptiveSampler(cfg)

        # 첫 프레임: 흰색
        white_frame = _make_frame(640, 480, index=0, fill=255)
        sampler.should_sample(white_frame)

        # 두 번째 프레임도 흰색 (히스토그램 초기화)
        white_frame2 = _make_frame(640, 480, index=1, timestamp=0.033, fill=255)
        sampler.should_sample(white_frame2)

        # 세 번째 프레임: 검정 (장면 전환)
        black_frame = _make_frame(640, 480, index=2, timestamp=0.066, fill=0)
        result = sampler.should_sample(black_frame)
        assert result is True

    def test_current_interval_changes_with_motion(self) -> None:
        """모션 감지에 따라 현재 간격이 변경됨."""
        cfg = SamplingConfig(min_interval=1, max_interval=10)
        sampler = AdaptiveSampler(cfg)
        initial_interval = sampler.current_interval

        # 정적 프레임 여러 개 (모션 없음 -> 간격 증가 예상)
        for i in range(20):
            frame = _make_frame(640, 480, index=i, timestamp=i / 30.0, fill=0)
            sampler.should_sample(frame)

        after_static = sampler.current_interval
        # 정적 프레임 연속 후 간격이 최대 쪽으로 이동
        assert after_static >= initial_interval

    def test_reset_clears_state(self) -> None:
        sampler = AdaptiveSampler()
        # 몇 개 프레임 처리
        for i in range(5):
            sampler.should_sample(_make_frame(640, 480, index=i))
        sampler.reset()
        stats = sampler.stats
        assert stats.frames_accepted == 0
        assert stats.frames_skipped == 0
        assert stats.scene_changes == 0
        assert sampler.current_interval == sampler.config.min_interval

    def test_stats_accepted_increments(self) -> None:
        sampler = AdaptiveSampler()
        frame = _make_frame(640, 480, index=0)
        sampler.should_sample(frame)
        stats = sampler.stats
        assert stats.frames_accepted >= 1

    def test_stats_total_frames_match(self) -> None:
        sampler = AdaptiveSampler()
        n = 10
        for i in range(n):
            sampler.should_sample(_make_frame(640, 480, index=i, fill=i * 10))
        stats = sampler.stats
        assert stats.total_frames == n

    def test_repr_contains_interval(self) -> None:
        sampler = AdaptiveSampler()
        r = repr(sampler)
        assert "interval=" in r

    def test_repr_contains_stats(self) -> None:
        sampler = AdaptiveSampler()
        r = repr(sampler)
        assert "stats=" in r

    def test_grayscale_input_handled(self) -> None:
        """그레이스케일 입력도 정상 처리."""
        sampler = AdaptiveSampler()
        frame = _make_frame(640, 480, channels=1, index=0, fill=128)
        result = sampler.should_sample(frame)
        assert result is True

    def test_motion_detection_disabled(self) -> None:
        """모션 감지 비활성화 시에도 정상 작동."""
        cfg = SamplingConfig(enable_motion_detection=False)
        sampler = AdaptiveSampler(cfg)
        frame = _make_frame(640, 480, index=0)
        result = sampler.should_sample(frame)
        assert result is True


# =============================================================================
# 모듈 Export / 버전
# =============================================================================


class TestModuleExports:
    """모듈 __all__, __version__ 검증."""

    def test_all_contains_adaptive_sampler(self) -> None:
        assert "AdaptiveSampler" in MODULE_ALL

    def test_all_contains_sampling_config(self) -> None:
        assert "SamplingConfig" in MODULE_ALL

    def test_all_contains_sampling_stats(self) -> None:
        assert "SamplingStats" in MODULE_ALL

    def test_all_contains_max_motion_history(self) -> None:
        assert "MAX_MOTION_HISTORY" in MODULE_ALL

    def test_all_contains_histogram_bins(self) -> None:
        assert "HISTOGRAM_BINS" in MODULE_ALL

    def test_all_contains_motion_low_threshold(self) -> None:
        assert "MOTION_LOW_THRESHOLD" in MODULE_ALL

    def test_all_contains_motion_high_threshold(self) -> None:
        assert "MOTION_HIGH_THRESHOLD" in MODULE_ALL

    def test_version(self) -> None:
        assert MODULE_VERSION == "1.0.0"
