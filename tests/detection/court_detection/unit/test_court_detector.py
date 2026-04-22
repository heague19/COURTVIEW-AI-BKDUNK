# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/unit
파일: test_court_detector.py
설명: CourtDetector 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from detection.court_detection.court_detector import (
    CourtDetector,
    CourtDetectorConfig,
    _LineSegment,
)
from shared.constants.court_constants import CourtStandard, CourtZone
from shared.interfaces.detector_interface import (
    CourtDetectionResult,
    DetectionState,
    DetectionTarget,
)


# =============================================================================
# 설정 테스트
# =============================================================================

class TestCourtDetectorConfig:
    """CourtDetectorConfig 테스트."""

    def test_기본값_생성(self):
        config = CourtDetectorConfig()
        assert config.model_path == "weights/COURTVIEW_court.pt"
        assert config.court_standard == CourtStandard.FIBA
        assert config.input_size == 640
        assert config.confidence_threshold == 0.25
        assert config.device == "cuda"
        assert config.half_precision is True
        assert config.enable_hough_assist is True
        assert config.enable_clahe is True

    def test_커스텀_설정(self):
        config = CourtDetectorConfig(
            court_standard=CourtStandard.NBA,
            confidence_threshold=0.5,
            device="cpu",
        )
        assert config.court_standard == CourtStandard.NBA
        assert config.confidence_threshold == 0.5
        assert config.device == "cpu"

    def test_repr(self):
        config = CourtDetectorConfig()
        r = repr(config)
        assert "COURTVIEW_court.pt" in r
        assert "fiba" in r


# =============================================================================
# 라인 세그먼트 테스트
# =============================================================================

class TestLineSegment:
    """_LineSegment 내부 데이터 클래스 테스트."""

    def test_수평선_생성(self):
        line = _LineSegment(x1=0, y1=100, x2=500, y2=100)
        assert line.is_horizontal is True
        assert line.is_vertical is False
        assert abs(line.length - 500.0) < 0.1
        assert abs(line.angle_deg) < 1.0

    def test_수직선_생성(self):
        line = _LineSegment(x1=200, y1=0, x2=200, y2=400)
        assert line.is_horizontal is False
        assert line.is_vertical is True
        assert abs(line.length - 400.0) < 0.1
        assert abs(line.angle_deg - 90.0) < 1.0

    def test_대각선(self):
        line = _LineSegment(x1=0, y1=0, x2=100, y2=100)
        assert line.is_horizontal is False
        assert line.is_vertical is False
        assert abs(line.angle_deg - 45.0) < 0.1

    def test_중점_계산(self):
        line = _LineSegment(x1=0, y1=0, x2=200, y2=100)
        mx, my = line.midpoint
        assert abs(mx - 100.0) < 0.01
        assert abs(my - 50.0) < 0.01

    def test_repr(self):
        line = _LineSegment(x1=0, y1=0, x2=100, y2=0, source="hough")
        r = repr(line)
        assert "hough" in r


# =============================================================================
# CourtDetector 기본 테스트
# =============================================================================

class TestCourtDetectorBasic:
    """CourtDetector 기본 기능 테스트."""

    def test_초기_상태(self):
        detector = CourtDetector()
        assert detector.state == DetectionState.UNINITIALIZED
        assert detector.name == "CourtDetector"
        assert DetectionTarget.COURT in detector.supported_targets
        assert DetectionTarget.LINE in detector.supported_targets

    def test_미초기화_detect_실패(self, dummy_frame_480p):
        detector = CourtDetector()
        result = detector.detect(dummy_frame_480p)
        assert result.success is False
        assert "상태 이상" in result.error_message

    def test_잘못된_프레임_감지_실패(self):
        detector = CourtDetector()
        detector._state = DetectionState.READY
        detector._config = CourtDetectorConfig()

        # 2D 프레임 (유효하지 않음)
        bad_frame = np.zeros((480, 640), dtype=np.uint8)
        result = detector.detect(bad_frame)
        assert result.success is False

    def test_reset_초기화(self):
        detector = CourtDetector()
        detector._state = DetectionState.READY
        detector._model = MagicMock()
        detector._cached_homography = np.eye(3)
        detector.reset()
        assert detector._cached_homography is None
        assert detector.state == DetectionState.READY

    def test_shutdown(self):
        detector = CourtDetector()
        detector._model = MagicMock()
        detector.shutdown()
        assert detector.state == DetectionState.SHUTDOWN
        assert detector._model is None

    def test_모델_파일_없으면_에러(self):
        detector = CourtDetector()
        config = CourtDetectorConfig(model_path="nonexistent_model.pt")
        with pytest.raises(FileNotFoundError):
            detector.initialize(config)


# =============================================================================
# CLAHE 전처리 테스트
# =============================================================================

class TestPreprocessing:
    """CLAHE 전처리 테스트."""

    def test_clahe_적용(self, court_lines_frame):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(enable_clahe=True)
        detector._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        result = detector._preprocess_frame(court_lines_frame)
        assert result.shape == court_lines_frame.shape
        # CLAHE 적용 후 동일하지 않아야 함
        assert not np.array_equal(result, court_lines_frame)

    def test_clahe_비활성화(self, court_lines_frame):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(enable_clahe=False)
        result = detector._preprocess_frame(court_lines_frame)
        assert np.array_equal(result, court_lines_frame)


# =============================================================================
# Hough 라인 감지 테스트
# =============================================================================

class TestHoughLineDetection:
    """Hough 라인 감지 테스트."""

    def test_코트_라인_프레임_감지(self, court_lines_frame):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()
        lines = detector._hough_line_detection(court_lines_frame)
        # 코트 라인이 있는 프레임에서 라인이 감지되어야 함
        assert isinstance(lines, list)

    def test_검은_프레임_라인_없음(self, dummy_frame_480p):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()
        lines = detector._hough_line_detection(dummy_frame_480p)
        assert len(lines) == 0


# =============================================================================
# 라인 병합 테스트
# =============================================================================

class TestLineMerging:
    """라인 병합 테스트."""

    def test_유사_라인_병합(self):
        detector = CourtDetector()
        yolo_lines = [
            _LineSegment(x1=0, y1=100, x2=500, y2=100, source="yolo", confidence=0.9),
        ]
        hough_lines = [
            _LineSegment(x1=5, y1=102, x2=498, y2=102, source="hough", confidence=0.7),
        ]
        merged = detector._merge_lines(yolo_lines, hough_lines)
        # 유사한 라인이므로 1개로 병합
        assert len(merged) == 1
        assert merged[0].source == "merged"

    def test_상이한_라인_유지(self):
        detector = CourtDetector()
        yolo_lines = [
            _LineSegment(x1=0, y1=100, x2=500, y2=100, source="yolo", confidence=0.9),
        ]
        hough_lines = [
            _LineSegment(x1=0, y1=400, x2=500, y2=400, source="hough", confidence=0.7),
        ]
        merged = detector._merge_lines(yolo_lines, hough_lines)
        assert len(merged) == 2

    def test_빈_라인_목록(self):
        detector = CourtDetector()
        merged = detector._merge_lines([], [])
        assert len(merged) == 0


# =============================================================================
# 라인 분류 테스트
# =============================================================================

class TestLineClassification:
    """라인 분류 테스트."""

    def test_수평_수직_분류(self):
        detector = CourtDetector()
        lines = [
            _LineSegment(x1=0, y1=100, x2=500, y2=100),  # 수평
            _LineSegment(x1=200, y1=0, x2=200, y2=400),  # 수직
            _LineSegment(x1=0, y1=0, x2=100, y2=100),    # 대각선 (무시)
        ]
        h_lines, v_lines = detector._classify_lines(lines)
        assert len(h_lines) == 1
        assert len(v_lines) == 1


# =============================================================================
# 키포인트 추출 테스트
# =============================================================================

class TestKeypointExtraction:
    """키포인트 추출 테스트."""

    def test_교차점_계산(self):
        detector = CourtDetector()
        h_lines = [
            _LineSegment(x1=0, y1=100, x2=500, y2=100),
        ]
        v_lines = [
            _LineSegment(x1=200, y1=0, x2=200, y2=400),
        ]
        keypoints = detector._extract_keypoints(h_lines, v_lines, 640, 480)
        assert len(keypoints) == 1
        assert abs(keypoints[0][0] - 200.0) < 1.0
        assert abs(keypoints[0][1] - 100.0) < 1.0

    def test_중복_키포인트_제거(self):
        detector = CourtDetector()
        keypoints = [
            (100.0, 100.0),
            (102.0, 101.0),  # 근접 (제거 대상)
            (300.0, 200.0),
        ]
        unique = detector._deduplicate_keypoints(keypoints, min_distance=15.0)
        assert len(unique) == 2


# =============================================================================
# 호모그래피 테스트
# =============================================================================

class TestHomography:
    """호모그래피 관련 테스트."""

    def test_호모그래피_유효성_검증_정상(self):
        detector = CourtDetector()
        # 방향 보존 호모그래피 (det > 0, 적절한 스케일)
        src = np.array([
            [50.0, 100.0], [590.0, 100.0],
            [50.0, 380.0], [590.0, 380.0],
        ], dtype=np.float64)
        dst = np.array([
            [0.0, 0.0], [28.0, 0.0],
            [0.0, 15.0], [28.0, 15.0],
        ], dtype=np.float64)
        h, _ = cv2.findHomography(src, dst)
        assert detector._validate_homography(h) is True

    def test_호모그래피_유효성_검증_뒤집힘(self):
        detector = CourtDetector()
        # 행렬식 < 0 (거울 반전)
        h = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64)
        assert detector._validate_homography(h) is False


# =============================================================================
# 좌표 변환 테스트
# =============================================================================

class TestCoordinateTransform:
    """좌표 변환 테스트."""

    def test_pixel_to_court(self, sample_homography):
        detector = CourtDetector()
        court_xy = detector.pixel_to_court((320.0, 240.0), sample_homography)
        assert isinstance(court_xy, tuple)
        assert len(court_xy) == 2

    def test_court_to_pixel(self, sample_homography):
        detector = CourtDetector()
        pixel_xy = detector.court_to_pixel((14.0, 7.5), sample_homography)
        assert isinstance(pixel_xy, tuple)
        assert len(pixel_xy) == 2

    def test_왕복_변환_일관성(self, sample_homography):
        detector = CourtDetector()
        original_pixel = (320.0, 240.0)
        court_xy = detector.pixel_to_court(original_pixel, sample_homography)
        recovered_pixel = detector.court_to_pixel(court_xy, sample_homography)
        assert abs(recovered_pixel[0] - original_pixel[0]) < 1.0
        assert abs(recovered_pixel[1] - original_pixel[1]) < 1.0


# =============================================================================
# 구역 판별 테스트
# =============================================================================

class TestGetZoneAtPosition:
    """get_zone_at_position 테스트."""

    def test_페인트존_중앙(self):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(court_standard=CourtStandard.FIBA)
        zone = detector.get_zone_at_position((3.0, 7.5))
        assert zone == CourtZone.PAINT_CENTER.value

    def test_백코트_범위외(self):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()
        zone = detector.get_zone_at_position((-5.0, 7.5))
        assert zone == CourtZone.BACKCOURT.value

    def test_3점_아크_중앙(self):
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()
        # 바스켓에서 3점 거리 이상 + 정면
        zone = detector.get_zone_at_position((8.5, 7.5))
        assert "three" in zone or "mid" in zone


# =============================================================================
# 코트 모델 테스트
# =============================================================================

class TestCourtModel:
    """코트 모델 구성 테스트."""

    def test_FIBA_모델_21점(self):
        detector = CourtDetector()
        points = detector._build_court_model(CourtStandard.FIBA)
        assert points.shape == (21, 2)

    def test_NBA_모델_21점(self):
        detector = CourtDetector()
        points = detector._build_court_model(CourtStandard.NBA)
        assert points.shape == (21, 2)
        # NBA 코트는 FIBA보다 길다
        x_max = float(np.max(points[:, 0]))
        assert x_max > 28.0  # NBA 28.65m

    def test_코너_키포인트_좌표(self):
        detector = CourtDetector()
        points = detector._build_court_model(CourtStandard.FIBA)
        # corner_bottom_left = (0, 0)
        assert abs(points[2, 0]) < 0.01
        assert abs(points[2, 1]) < 0.01
        # corner_top_right = (28, 15)
        assert abs(points[1, 0] - 28.0) < 0.01
        assert abs(points[1, 1] - 15.0) < 0.01


# =============================================================================
# detect_court 테스트
# =============================================================================

class TestDetectCourt:
    """detect_court (ICourtDetector 인터페이스) 테스트."""

    def test_미초기화_실패(self, dummy_frame_480p):
        detector = CourtDetector()
        result = detector.detect_court(dummy_frame_480p)
        assert result.success is False

    def test_코트_유형_판별(self):
        detector = CourtDetector()
        # 넓은 분포 → full court
        wide_kps = [(50, 100), (590, 100), (50, 380), (590, 380)]
        court_type = detector._determine_court_type(wide_kps, 640, 480)
        assert court_type == "full"

        # 좁은 분포 → half court
        narrow_kps = [(50, 100), (200, 100), (50, 380), (200, 380)]
        court_type = detector._determine_court_type(narrow_kps, 640, 480)
        assert court_type == "half"

    def test_캘리브레이션_품질_키포인트_없으면_0(self):
        detector = CourtDetector()
        quality = detector._evaluate_calibration_quality([], None)
        assert quality == 0.0
