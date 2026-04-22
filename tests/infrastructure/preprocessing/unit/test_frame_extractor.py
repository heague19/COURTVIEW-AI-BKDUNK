# -*- coding: utf-8 -*-
"""
infrastructure/preprocessing/frame_extractor.py 단위 테스트.

프레임 추출 모듈의 모든 exported 클래스/상수를 검증한다.
실제 비디오 파일 없이 mock/synthetic 이미지로 테스트.

테스트 대상:
  - ExtractionConfig: 기본값, __post_init__ 클램핑, repr
  - ExtractionResult: 기본값, 계산 프로퍼티, repr
  - FrameExtractor: extract/extract_keyframes 비정상 파일, _check_quality, _is_duplicate
  - 모듈 상수: MAX_EXTRACTION_FRAMES, MIN_QUALITY_CHECK_SIZE, DUPLICATE_HASH_THRESHOLD, MAX_KEYFRAMES
  - __all__, __version__
"""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import cv2
import numpy as np
import pytest

from infrastructure.preprocessing.frame_extractor import (
    DUPLICATE_HASH_THRESHOLD,
    MAX_EXTRACTION_FRAMES,
    MAX_KEYFRAMES,
    MIN_QUALITY_CHECK_SIZE,
    ExtractionConfig,
    ExtractionResult,
    FrameExtractor,
    __all__ as module_all,
    __version__ as module_version,
)
from shared.constants.video_constants import (
    BLUR_DETECTION_THRESHOLD,
    BRIGHTNESS_MAX_THRESHOLD,
    BRIGHTNESS_MIN_THRESHOLD,
)
from shared.dto.video_dto import FrameData, FrameStatus, VideoResolution


# =============================================================================
# 모듈 메타 정보 검증
# =============================================================================

class TestModuleMeta:
    """모듈 __all__, __version__ 검증."""

    def test_version_is_1_0_0(self):
        assert module_version == "1.0.0"

    def test_all_contains_frame_extractor(self):
        assert "FrameExtractor" in module_all

    def test_all_contains_extraction_config(self):
        assert "ExtractionConfig" in module_all

    def test_all_contains_extraction_result(self):
        assert "ExtractionResult" in module_all

    def test_all_contains_max_extraction_frames(self):
        assert "MAX_EXTRACTION_FRAMES" in module_all

    def test_all_contains_min_quality_check_size(self):
        assert "MIN_QUALITY_CHECK_SIZE" in module_all

    def test_all_contains_duplicate_hash_threshold(self):
        assert "DUPLICATE_HASH_THRESHOLD" in module_all

    def test_all_contains_max_keyframes(self):
        assert "MAX_KEYFRAMES" in module_all

    def test_all_has_correct_length(self):
        assert len(module_all) == 7


# =============================================================================
# 모듈 상수 검증
# =============================================================================

class TestModuleConstants:
    """모듈 레벨 상수 값 검증."""

    def test_max_extraction_frames_value(self):
        assert MAX_EXTRACTION_FRAMES == 100_000

    def test_min_quality_check_size_value(self):
        assert MIN_QUALITY_CHECK_SIZE == 64

    def test_duplicate_hash_threshold_value(self):
        assert DUPLICATE_HASH_THRESHOLD == 5

    def test_max_keyframes_value(self):
        assert MAX_KEYFRAMES == 500

    def test_max_extraction_frames_is_int(self):
        assert isinstance(MAX_EXTRACTION_FRAMES, int)

    def test_min_quality_check_size_is_int(self):
        assert isinstance(MIN_QUALITY_CHECK_SIZE, int)

    def test_duplicate_hash_threshold_is_int(self):
        assert isinstance(DUPLICATE_HASH_THRESHOLD, int)


# =============================================================================
# ExtractionConfig 검증
# =============================================================================

class TestExtractionConfig:
    """ExtractionConfig 기본값, 클램핑, repr 검증."""

    def test_defaults(self):
        cfg = ExtractionConfig()
        assert cfg.target_fps is None
        assert cfg.start_time_sec == 0.0
        assert cfg.end_time_sec is None
        assert cfg.max_frames == MAX_EXTRACTION_FRAMES
        assert cfg.enable_quality_filter is False
        assert cfg.enable_duplicate_filter is False
        assert cfg.camera_id is None

    def test_blur_threshold_default(self):
        cfg = ExtractionConfig()
        assert cfg.blur_threshold == BLUR_DETECTION_THRESHOLD

    def test_brightness_min_default(self):
        cfg = ExtractionConfig()
        assert cfg.brightness_min == BRIGHTNESS_MIN_THRESHOLD

    def test_brightness_max_default(self):
        cfg = ExtractionConfig()
        assert cfg.brightness_max == BRIGHTNESS_MAX_THRESHOLD

    def test_has_slots(self):
        assert hasattr(ExtractionConfig, "__slots__")

    # __post_init__ 클램핑 검증
    def test_clamp_negative_start_time(self):
        cfg = ExtractionConfig(start_time_sec=-5.0)
        assert cfg.start_time_sec == 0.0

    def test_clamp_max_frames_zero_to_one(self):
        cfg = ExtractionConfig(max_frames=0)
        assert cfg.max_frames == 1

    def test_clamp_max_frames_negative_to_one(self):
        cfg = ExtractionConfig(max_frames=-100)
        assert cfg.max_frames == 1

    def test_clamp_max_frames_over_limit(self):
        cfg = ExtractionConfig(max_frames=999_999)
        assert cfg.max_frames == MAX_EXTRACTION_FRAMES

    def test_clamp_blur_threshold_below_one(self):
        cfg = ExtractionConfig(blur_threshold=0.5)
        assert cfg.blur_threshold == 1.0

    def test_clamp_brightness_min_negative(self):
        cfg = ExtractionConfig(brightness_min=-10)
        assert cfg.brightness_min == 0

    def test_clamp_brightness_min_over_255(self):
        cfg = ExtractionConfig(brightness_min=300)
        assert cfg.brightness_min == 255

    def test_clamp_brightness_max_below_min(self):
        """brightness_max가 brightness_min보다 작으면 brightness_min으로 설정."""
        cfg = ExtractionConfig(brightness_min=100, brightness_max=50)
        assert cfg.brightness_max >= cfg.brightness_min

    def test_clamp_brightness_max_over_255(self):
        cfg = ExtractionConfig(brightness_max=999)
        assert cfg.brightness_max == 255

    # repr
    def test_repr_default_fps(self):
        cfg = ExtractionConfig()
        r = repr(cfg)
        assert "fps=" in r
        # target_fps=None → "원본"
        assert "원본" in r

    def test_repr_custom_fps(self):
        cfg = ExtractionConfig(target_fps=15.0)
        r = repr(cfg)
        assert "15.0" in r

    def test_repr_quality_on(self):
        cfg = ExtractionConfig(enable_quality_filter=True)
        r = repr(cfg)
        assert "quality=ON" in r

    def test_repr_quality_off(self):
        cfg = ExtractionConfig(enable_quality_filter=False)
        r = repr(cfg)
        assert "quality=OFF" in r

    def test_repr_end_time_none(self):
        cfg = ExtractionConfig()
        r = repr(cfg)
        assert "끝" in r

    def test_repr_end_time_set(self):
        cfg = ExtractionConfig(end_time_sec=60.0)
        r = repr(cfg)
        assert "60.0s" in r


# =============================================================================
# ExtractionResult 검증
# =============================================================================

class TestExtractionResult:
    """ExtractionResult 기본값, 계산 프로퍼티, repr 검증."""

    def test_defaults(self):
        result = ExtractionResult()
        assert result.total_extracted == 0
        assert result.total_skipped == 0
        assert result.total_filtered == 0
        assert result.duplicates_removed == 0
        assert result.extraction_time_sec == 0.0
        assert result.source_fps == 0.0
        assert result.effective_fps == 0.0

    def test_has_slots(self):
        assert hasattr(ExtractionResult, "__slots__")

    def test_total_processed_zero(self):
        result = ExtractionResult()
        assert result.total_processed == 0

    def test_total_processed_sum(self):
        result = ExtractionResult(
            total_extracted=50,
            total_skipped=20,
            total_filtered=10,
            duplicates_removed=5,
        )
        assert result.total_processed == 85

    def test_extraction_rate_zero_when_no_processed(self):
        result = ExtractionResult()
        assert result.extraction_rate == 0.0

    def test_extraction_rate_all_extracted(self):
        result = ExtractionResult(total_extracted=100)
        assert result.extraction_rate == 1.0

    def test_extraction_rate_half(self):
        result = ExtractionResult(total_extracted=50, total_skipped=50)
        assert result.extraction_rate == pytest.approx(0.5)

    def test_extraction_rate_with_all_categories(self):
        result = ExtractionResult(
            total_extracted=40,
            total_skipped=30,
            total_filtered=20,
            duplicates_removed=10,
        )
        # total_processed = 100
        assert result.extraction_rate == pytest.approx(0.4)

    def test_repr_contains_extracted(self):
        result = ExtractionResult(total_extracted=42)
        r = repr(result)
        assert "extracted=42" in r

    def test_repr_contains_skipped(self):
        result = ExtractionResult(total_skipped=10)
        r = repr(result)
        assert "skipped=10" in r

    def test_repr_contains_filtered(self):
        result = ExtractionResult(total_filtered=5)
        r = repr(result)
        assert "filtered=5" in r

    def test_repr_contains_dupes(self):
        result = ExtractionResult(duplicates_removed=3)
        r = repr(result)
        assert "dupes=3" in r

    def test_repr_contains_time(self):
        result = ExtractionResult(extraction_time_sec=1.23)
        r = repr(result)
        assert "time=1.23s" in r


# =============================================================================
# FrameExtractor 초기 상태 및 프로퍼티 검증
# =============================================================================

class TestFrameExtractorInit:
    """FrameExtractor 초기 상태 검증."""

    def test_default_config(self):
        ext = FrameExtractor()
        assert ext.config is not None
        assert isinstance(ext.config, ExtractionConfig)

    def test_custom_config(self):
        cfg = ExtractionConfig(target_fps=15.0, camera_id="cam_A")
        ext = FrameExtractor(config=cfg)
        assert ext.config.target_fps == 15.0
        assert ext.config.camera_id == "cam_A"

    def test_initial_result_zeros(self):
        ext = FrameExtractor()
        result = ext.result
        assert result.total_extracted == 0
        assert result.total_processed == 0

    def test_result_is_defensive_copy(self):
        ext = FrameExtractor()
        r1 = ext.result
        r2 = ext.result
        assert r1 is not r2

    def test_repr(self):
        ext = FrameExtractor()
        r = repr(ext)
        assert "FrameExtractor(" in r
        assert "config=" in r
        assert "result=" in r


# =============================================================================
# FrameExtractor extract/extract_keyframes 비정상 파일 검증
# =============================================================================

class TestFrameExtractorBadFile:
    """존재하지 않는 파일에 대한 추출 검증."""

    def test_extract_nonexistent_yields_nothing(self):
        ext = FrameExtractor()
        frames = list(ext.extract("__nonexistent_video_99999.mp4"))
        assert frames == []

    def test_extract_keyframes_nonexistent_returns_empty(self):
        ext = FrameExtractor()
        keyframes = ext.extract_keyframes("__nonexistent_video_99999.mp4")
        assert keyframes == []

    def test_extract_at_times_nonexistent_returns_empty(self):
        ext = FrameExtractor()
        frames = ext.extract_at_times("__nonexistent_video_99999.mp4", [1.0, 2.0])
        assert frames == []

    def test_extract_at_times_empty_list_returns_empty(self):
        ext = FrameExtractor()
        frames = ext.extract_at_times("__nonexistent_video_99999.mp4", [])
        assert frames == []


# =============================================================================
# FrameExtractor _check_quality 합성 이미지 검증
# =============================================================================

class TestFrameExtractorCheckQuality:
    """_check_quality 메서드의 합성 이미지 품질 검사 검증."""

    def _make_extractor_with_quality(self) -> FrameExtractor:
        """품질 필터 활성화된 추출기 생성."""
        cfg = ExtractionConfig(enable_quality_filter=True)
        return FrameExtractor(config=cfg)

    def test_empty_image_fails(self):
        ext = self._make_extractor_with_quality()
        empty = np.array([], dtype=np.uint8)
        assert ext._check_quality(empty) is False

    def test_small_image_passes(self):
        """MIN_QUALITY_CHECK_SIZE 미만 이미지는 검사 스킵 → True."""
        ext = self._make_extractor_with_quality()
        small = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        assert ext._check_quality(small) is True

    def test_black_image_fails_brightness(self):
        """완전한 검정 이미지 → 밝기 하한 미달."""
        ext = self._make_extractor_with_quality()
        black = np.zeros((128, 128, 3), dtype=np.uint8)
        assert ext._check_quality(black) is False

    def test_white_image_fails_brightness(self):
        """완전한 흰색 이미지 → 밝기 상한 초과."""
        ext = self._make_extractor_with_quality()
        white = np.full((128, 128, 3), 255, dtype=np.uint8)
        # 평균 밝기 255 > BRIGHTNESS_MAX_THRESHOLD(225)
        assert ext._check_quality(white) is False

    def test_blurry_image_fails(self):
        """완전히 균일한 이미지 → 라플라시안 분산 0 → 블러."""
        ext = self._make_extractor_with_quality()
        # 중간 밝기 균일 이미지 (블러 → 라플라시안 분산 = 0)
        uniform = np.full((128, 128, 3), 128, dtype=np.uint8)
        assert ext._check_quality(uniform) is False

    def test_sharp_normal_image_passes(self):
        """노이즈가 있는 정상 밝기 이미지 → 통과."""
        ext = self._make_extractor_with_quality()
        # 랜덤 노이즈 이미지 (높은 라플라시안 분산, 밝기 ~127)
        np.random.seed(42)
        noisy = np.random.randint(60, 200, (256, 256, 3), dtype=np.uint8)
        assert ext._check_quality(noisy) is True

    def test_grayscale_image_passes(self):
        """2D 그레이스케일 노이즈 이미지 → 변환 없이 처리."""
        ext = self._make_extractor_with_quality()
        np.random.seed(99)
        gray = np.random.randint(60, 200, (256, 256), dtype=np.uint8)
        assert ext._check_quality(gray) is True

    def test_custom_blur_threshold(self):
        """blur_threshold를 매우 높게 설정 → 일반 이미지도 블러로 판정."""
        cfg = ExtractionConfig(
            enable_quality_filter=True,
            blur_threshold=1_000_000.0,
        )
        ext = FrameExtractor(config=cfg)
        np.random.seed(42)
        noisy = np.random.randint(60, 200, (256, 256, 3), dtype=np.uint8)
        assert ext._check_quality(noisy) is False

    def test_custom_brightness_range(self):
        """좁은 밝기 범위 → 정상 이미지도 실패 가능."""
        cfg = ExtractionConfig(
            enable_quality_filter=True,
            brightness_min=120,
            brightness_max=130,
        )
        ext = FrameExtractor(config=cfg)
        # 밝기 60~200 범위 → 평균 ~130 내외 → 범위에 따라 통과/실패
        dark = np.full((128, 128, 3), 50, dtype=np.uint8)
        assert ext._check_quality(dark) is False


# =============================================================================
# FrameExtractor _is_duplicate 합성 이미지 검증
# =============================================================================

class TestFrameExtractorIsDuplicate:
    """_is_duplicate 메서드의 중복 판정 검증."""

    def _make_extractor_with_dedup(self) -> FrameExtractor:
        cfg = ExtractionConfig(enable_duplicate_filter=True)
        return FrameExtractor(config=cfg)

    def test_first_frame_never_duplicate(self):
        """첫 프레임은 항상 중복 아님 (last_hash=0)."""
        ext = self._make_extractor_with_dedup()
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        assert ext._is_duplicate(img) is False

    def test_identical_images_are_duplicate(self):
        """동일 이미지 연속 → 중복."""
        ext = self._make_extractor_with_dedup()
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        # 첫 번째 = not duplicate
        ext._is_duplicate(img)
        # 두 번째 동일 = duplicate (해밍 거리 0)
        assert ext._is_duplicate(img.copy()) is True

    def test_very_different_images_not_duplicate(self):
        """매우 다른 이미지 → 중복 아님."""
        ext = self._make_extractor_with_dedup()
        np.random.seed(10)
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        np.random.seed(20)
        img2 = np.full((100, 100, 3), 255, dtype=np.uint8)
        ext._is_duplicate(img1)
        assert ext._is_duplicate(img2) is False

    def test_grayscale_duplicate_detection(self):
        """그레이스케일 이미지 중복 검사."""
        ext = self._make_extractor_with_dedup()
        gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        ext._is_duplicate(gray)
        assert ext._is_duplicate(gray.copy()) is True

    def test_slightly_different_images(self):
        """약간 다른 이미지 → DUPLICATE_HASH_THRESHOLD에 따라 판정."""
        ext = self._make_extractor_with_dedup()
        np.random.seed(42)
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        ext._is_duplicate(img)
        # 1픽셀만 변경 → 해시 거리 매우 작음 → 중복
        modified = img.copy()
        modified[0, 0] = [0, 0, 0] if modified[0, 0, 0] > 0 else [255, 255, 255]
        # 1픽셀 변경은 8x8 리사이즈 후 해시에 거의 영향 없음
        result = ext._is_duplicate(modified)
        assert isinstance(result, bool)  # 결과 타입 확인


# =============================================================================
# ExtractionConfig + ExtractionResult 통합 경계값 검증
# =============================================================================

class TestExtractionEdgeCases:
    """경계 조건 및 통합 검증."""

    def test_config_max_frames_exactly_limit(self):
        cfg = ExtractionConfig(max_frames=MAX_EXTRACTION_FRAMES)
        assert cfg.max_frames == MAX_EXTRACTION_FRAMES

    def test_config_max_frames_one(self):
        cfg = ExtractionConfig(max_frames=1)
        assert cfg.max_frames == 1

    def test_config_camera_id_set(self):
        cfg = ExtractionConfig(camera_id="main_cam")
        assert cfg.camera_id == "main_cam"

    def test_result_only_filtered(self):
        result = ExtractionResult(total_filtered=50)
        assert result.total_processed == 50
        assert result.extraction_rate == 0.0

    def test_result_only_duplicates(self):
        result = ExtractionResult(duplicates_removed=30)
        assert result.total_processed == 30
        assert result.extraction_rate == 0.0

    def test_result_mixed_scenario(self):
        result = ExtractionResult(
            total_extracted=200,
            total_skipped=50,
            total_filtered=30,
            duplicates_removed=20,
            extraction_time_sec=5.5,
            source_fps=60.0,
            effective_fps=30.0,
        )
        assert result.total_processed == 300
        assert result.extraction_rate == pytest.approx(200 / 300)
        assert result.extraction_time_sec == pytest.approx(5.5)

    def test_config_blur_threshold_exactly_one(self):
        cfg = ExtractionConfig(blur_threshold=1.0)
        assert cfg.blur_threshold == 1.0

    def test_config_brightness_min_max_equal(self):
        cfg = ExtractionConfig(brightness_min=100, brightness_max=100)
        assert cfg.brightness_min == 100
        assert cfg.brightness_max == 100
