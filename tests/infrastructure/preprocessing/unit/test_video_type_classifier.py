# -*- coding: utf-8 -*-
"""infrastructure/preprocessing/video_type_classifier.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import os
import tempfile

import pytest
import cv2
import numpy as np

from infrastructure.preprocessing.video_type_classifier import (
    MAX_VALIDATION_ERRORS,
    ClassificationResult,
    VideoTypeClassifier,
    VideoValidator,
    __all__ as MODULE_ALL,
    __version__ as MODULE_VERSION,
)
from shared.dto.video_dto import (
    FrameData,
    FrameStatus,
    VideoFileMetadata,
    VideoResolution,
    VideoType,
)


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


def _make_temp_text_file() -> str:
    """임시 텍스트 파일 생성 (비디오가 아닌 파일 검증용)."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, b"This is not a video file.")
    os.close(fd)
    return path


# =============================================================================
# 상수 검증
# =============================================================================


class TestConstants:
    """모듈 상수 검증."""

    def test_max_validation_errors_type(self) -> None:
        assert isinstance(MAX_VALIDATION_ERRORS, int)

    def test_max_validation_errors_value(self) -> None:
        assert MAX_VALIDATION_ERRORS == 50

    def test_max_validation_errors_positive(self) -> None:
        assert MAX_VALIDATION_ERRORS > 0


# =============================================================================
# ClassificationResult
# =============================================================================


class TestClassificationResult:
    """ClassificationResult 단위 테스트."""

    def test_defaults(self) -> None:
        result = ClassificationResult()
        assert result.video_type == VideoType.RAW
        assert result.confidence == 0.0
        assert result.metadata is None
        assert result.validation_errors == []
        assert result.is_valid is False

    def test_confidence_clamping_upper(self) -> None:
        result = ClassificationResult(confidence=5.0)
        assert result.confidence == 1.0

    def test_confidence_clamping_lower(self) -> None:
        result = ClassificationResult(confidence=-1.0)
        assert result.confidence == 0.0

    def test_confidence_normal_value(self) -> None:
        result = ClassificationResult(confidence=0.75)
        assert abs(result.confidence - 0.75) < 1e-9

    def test_has_errors_true(self) -> None:
        result = ClassificationResult(validation_errors=["오류 1"])
        assert result.has_errors is True

    def test_has_errors_false(self) -> None:
        result = ClassificationResult(validation_errors=[])
        assert result.has_errors is False

    def test_repr_contains_type(self) -> None:
        result = ClassificationResult(video_type=VideoType.GAME, confidence=0.8)
        r = repr(result)
        assert VideoType.GAME.value in r

    def test_repr_contains_confidence(self) -> None:
        result = ClassificationResult(confidence=0.85)
        r = repr(result)
        assert "0.85" in r

    def test_repr_contains_valid(self) -> None:
        result = ClassificationResult(is_valid=True)
        r = repr(result)
        assert "valid=True" in r

    def test_repr_contains_error_count(self) -> None:
        result = ClassificationResult(
            validation_errors=["err1", "err2"]
        )
        r = repr(result)
        assert "errors=2" in r

    def test_slots_defined(self) -> None:
        result = ClassificationResult()
        assert hasattr(result, "__slots__")

    def test_with_metadata(self) -> None:
        meta = VideoFileMetadata(
            duration=120.0,
            fps=30.0,
            resolution=VideoResolution(width=1920, height=1080),
        )
        result = ClassificationResult(
            video_type=VideoType.TRAINING,
            confidence=0.7,
            metadata=meta,
            is_valid=True,
        )
        assert result.metadata is not None
        assert result.metadata.duration == 120.0

    def test_custom_video_type(self) -> None:
        result = ClassificationResult(video_type=VideoType.HIGHLIGHT)
        assert result.video_type == VideoType.HIGHLIGHT

    def test_multiple_validation_errors(self) -> None:
        errors = [f"오류 {i}" for i in range(10)]
        result = ClassificationResult(validation_errors=errors)
        assert len(result.validation_errors) == 10
        assert result.has_errors is True


# =============================================================================
# VideoValidator
# =============================================================================


class TestVideoValidator:
    """VideoValidator 단위 테스트."""

    def test_validate_nonexistent_file(self) -> None:
        """존재하지 않는 파일 검증 시 오류 반환."""
        validator = VideoValidator()
        errors = validator.validate("/nonexistent/path/video.mp4")
        assert len(errors) > 0
        # 파일 존재하지 않음 관련 오류 메시지
        assert any("존재" in e for e in errors)

    def test_validate_existing_non_video_file(self) -> None:
        """비디오가 아닌 파일 검증 시 확장자 오류 또는 열기 오류 반환."""
        txt_path = _make_temp_text_file()
        try:
            validator = VideoValidator()
            errors = validator.validate(txt_path)
            # .txt 확장자는 지원하지 않거나, 영상 열기 실패
            assert len(errors) > 0
        finally:
            os.unlink(txt_path)

    def test_validate_empty_file(self) -> None:
        """빈 파일 검증 시 오류 반환."""
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        try:
            validator = VideoValidator()
            errors = validator.validate(path)
            assert len(errors) > 0
        finally:
            os.unlink(path)

    def test_validate_returns_list(self) -> None:
        validator = VideoValidator()
        result = validator.validate("/nonexistent/file.mp4")
        assert isinstance(result, list)


# =============================================================================
# VideoTypeClassifier
# =============================================================================


class TestVideoTypeClassifier:
    """VideoTypeClassifier 단위 테스트."""

    def test_classify_nonexistent_file(self) -> None:
        """존재하지 않는 파일 분류 시 RAW + 오류."""
        classifier = VideoTypeClassifier()
        result = classifier.classify("/nonexistent/path/video.mp4")
        assert result.video_type == VideoType.RAW
        assert result.confidence == 0.0
        assert result.is_valid is False
        assert result.has_errors is True

    def test_classify_nonexistent_has_validation_errors(self) -> None:
        classifier = VideoTypeClassifier()
        result = classifier.classify("/nonexistent/path/video.mp4")
        assert len(result.validation_errors) > 0

    def test_classify_with_hint_nonexistent(self) -> None:
        """힌트 분류에서도 존재하지 않는 파일은 실패."""
        classifier = VideoTypeClassifier()
        result = classifier.classify_with_hint(
            "/nonexistent/path/video.mp4",
            VideoType.GAME,
        )
        assert result.is_valid is False
        assert result.has_errors is True

    def test_classify_empty_file(self) -> None:
        """빈 파일 분류 시 오류."""
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        try:
            classifier = VideoTypeClassifier()
            result = classifier.classify(path)
            assert result.is_valid is False
            assert result.has_errors is True
        finally:
            os.unlink(path)

    def test_classify_non_video_file(self) -> None:
        """비디오가 아닌 파일 분류 시 오류."""
        txt_path = _make_temp_text_file()
        try:
            classifier = VideoTypeClassifier()
            result = classifier.classify(txt_path)
            assert result.is_valid is False
        finally:
            os.unlink(txt_path)

    def test_repr(self) -> None:
        classifier = VideoTypeClassifier()
        r = repr(classifier)
        assert "VideoTypeClassifier" in r

    def test_classifier_has_validator(self) -> None:
        """분류기가 내부에 VideoValidator를 가짐."""
        classifier = VideoTypeClassifier()
        # _validator 속성 존재 확인 (slots 포함)
        assert hasattr(classifier, "_validator")


# =============================================================================
# FrameData 합성 테스트
# =============================================================================


class TestSyntheticFrameData:
    """합성 FrameData 생성 및 속성 검증."""

    def test_zeros_frame(self) -> None:
        frame = _make_frame(640, 480, fill=0)
        assert frame.width == 640
        assert frame.height == 480
        assert frame.channels == 3
        assert frame.is_valid is True
        assert np.all(frame.image == 0)

    def test_ones_frame(self) -> None:
        frame = _make_frame(320, 240, fill=255)
        assert frame.width == 320
        assert frame.height == 240
        assert np.all(frame.image == 255)

    def test_grayscale_frame(self) -> None:
        frame = _make_frame(100, 100, channels=1, fill=128)
        assert frame.channels == 1
        assert frame.image.ndim == 2

    def test_frame_status_valid(self) -> None:
        frame = _make_frame(640, 480, status=FrameStatus.VALID)
        assert frame.is_valid is True

    def test_frame_status_corrupt(self) -> None:
        frame = _make_frame(640, 480, status=FrameStatus.CORRUPT)
        assert frame.is_valid is False

    def test_frame_status_skipped(self) -> None:
        frame = _make_frame(640, 480, status=FrameStatus.SKIPPED)
        assert frame.is_valid is False

    def test_frame_resolution_property(self) -> None:
        frame = _make_frame(1920, 1080)
        res = frame.resolution
        assert res.width == 1920
        assert res.height == 1080


# =============================================================================
# 모듈 Export / 버전
# =============================================================================


class TestModuleExports:
    """모듈 __all__, __version__ 검증."""

    def test_all_contains_video_type_classifier(self) -> None:
        assert "VideoTypeClassifier" in MODULE_ALL

    def test_all_contains_video_validator(self) -> None:
        assert "VideoValidator" in MODULE_ALL

    def test_all_contains_classification_result(self) -> None:
        assert "ClassificationResult" in MODULE_ALL

    def test_all_contains_max_validation_errors(self) -> None:
        assert "MAX_VALIDATION_ERRORS" in MODULE_ALL

    def test_version(self) -> None:
        assert MODULE_VERSION == "1.0.0"
