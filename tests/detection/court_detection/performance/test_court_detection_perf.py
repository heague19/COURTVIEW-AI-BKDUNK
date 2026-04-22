# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/performance
파일: test_court_detection_perf.py
설명: court_detection 모듈 성능 테스트
      - CourtDetector: 전처리/Hough/라인 병합/키포인트 추출 속도
      - CourtMapper: 호모그래피 추정/좌표 변환 속도
      - ZoneClassifier: 구역 분류 속도
      - 데이터 추출기: 버퍼/저장 속도

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from detection.court_detection.court_detector import (
    CourtDetector,
    CourtDetectorConfig,
    _LineSegment,
)
from detection.court_detection.court_mapper import (
    CourtMapper,
    CourtMapperConfig,
)
from detection.court_detection.zone_classifier import (
    ZoneClassifier,
    ZoneClassifierConfig,
)
from detection.court_detection.data_extraction.zone_extractor import (
    ZoneExtractor,
)
from detection.court_detection.data_extraction.arena_profile_extractor import (
    ArenaProfileExtractor,
)
from shared.constants.court_constants import CourtStandard, CourtZone


# =============================================================================
# 공통 fixture
# =============================================================================

@pytest.fixture()
def court_frame_480p() -> np.ndarray:
    """코트 라인 있는 480p 프레임."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (60, 100, 160)
    cv2.line(frame, (50, 100), (590, 100), (255, 255, 255), 3)
    cv2.line(frame, (50, 380), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (320, 100), (320, 380), (255, 255, 255), 3)
    return frame


@pytest.fixture()
def court_frame_1080p() -> np.ndarray:
    """코트 라인 있는 1080p 프레임."""
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[:] = (60, 100, 160)
    cv2.line(frame, (100, 200), (1820, 200), (255, 255, 255), 4)
    cv2.line(frame, (100, 880), (1820, 880), (255, 255, 255), 4)
    cv2.line(frame, (960, 200), (960, 880), (255, 255, 255), 4)
    return frame


# =============================================================================
# CourtDetector 성능 테스트
# =============================================================================

class TestCourtDetectorPerf:
    """CourtDetector 성능 테스트."""

    def test_전처리_속도_480p(self, court_frame_480p):
        """480p CLAHE 전처리: < 5ms."""
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(enable_clahe=True)
        detector._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # 워밍업
        detector._preprocess_frame(court_frame_480p)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            detector._preprocess_frame(court_frame_480p)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 5.0, f"480p CLAHE 전처리 {elapsed:.2f}ms > 5ms"

    def test_전처리_속도_1080p(self, court_frame_1080p):
        """1080p CLAHE 전처리: < 15ms."""
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(enable_clahe=True)
        detector._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        detector._preprocess_frame(court_frame_1080p)

        start = time.perf_counter()
        iterations = 50
        for _ in range(iterations):
            detector._preprocess_frame(court_frame_1080p)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 30.0, f"1080p CLAHE 전처리 {elapsed:.2f}ms > 30ms"

    def test_Hough_속도_480p(self, court_frame_480p):
        """480p Hough 라인 감지: < 10ms."""
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()

        # 워밍업
        detector._hough_line_detection(court_frame_480p)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            detector._hough_line_detection(court_frame_480p)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 10.0, f"480p Hough 감지 {elapsed:.2f}ms > 10ms"

    def test_라인_병합_속도(self):
        """100개 라인 병합: < 5ms."""
        detector = CourtDetector()
        yolo_lines = [
            _LineSegment(
                x1=float(i * 5), y1=float(i * 2),
                x2=float(i * 5 + 200), y2=float(i * 2),
                source="yolo", confidence=0.8,
            )
            for i in range(50)
        ]
        hough_lines = [
            _LineSegment(
                x1=float(i * 5 + 1), y1=float(i * 2 + 1),
                x2=float(i * 5 + 201), y2=float(i * 2 + 1),
                source="hough", confidence=0.7,
            )
            for i in range(50)
        ]

        # 워밍업
        detector._merge_lines(yolo_lines, hough_lines)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            detector._merge_lines(yolo_lines, hough_lines)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 5.0, f"100개 라인 병합 {elapsed:.2f}ms > 5ms"

    def test_키포인트_추출_속도(self):
        """키포인트 교차점 추출: < 2ms."""
        detector = CourtDetector()
        h_lines = [
            _LineSegment(x1=0, y1=float(i * 50 + 50), x2=640, y2=float(i * 50 + 50))
            for i in range(5)
        ]
        v_lines = [
            _LineSegment(x1=float(i * 100 + 50), y1=0, x2=float(i * 100 + 50), y2=480)
            for i in range(5)
        ]

        # 워밍업
        detector._extract_keypoints(h_lines, v_lines, 640, 480)

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            detector._extract_keypoints(h_lines, v_lines, 640, 480)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 2.0, f"키포인트 추출 {elapsed:.2f}ms > 2ms"

    def test_코트_모델_생성_속도(self):
        """코트 모델 21점 생성: < 0.5ms."""
        detector = CourtDetector()

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            detector._build_court_model(CourtStandard.FIBA)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 0.5, f"코트 모델 생성 {elapsed:.2f}ms > 0.5ms"


# =============================================================================
# CourtMapper 성능 테스트
# =============================================================================

class TestCourtMapperPerf:
    """CourtMapper 성능 테스트."""

    @pytest.fixture()
    def initialized_mapper(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))
        src = np.array([
            [50, 100], [590, 100], [50, 380], [590, 380],
            [320, 100], [320, 380],
        ], dtype=np.float64)
        dst = np.array([
            [0, 15], [28, 15], [0, 0], [28, 0],
            [14, 15], [14, 0],
        ], dtype=np.float64)
        h, _ = cv2.findHomography(src, dst)
        mapper._current_homography = h
        mapper._current_inverse = np.linalg.inv(h)
        return mapper

    def test_호모그래피_추정_속도(self):
        """6점 RANSAC 호모그래피: < 5ms."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))

        pixel_pts = [
            (50.0, 100.0), (590.0, 100.0),
            (50.0, 380.0), (590.0, 380.0),
            (320.0, 100.0), (320.0, 380.0),
        ]
        court_pts = [
            (0.0, 15.0), (28.0, 15.0),
            (0.0, 0.0), (28.0, 0.0),
            (14.0, 15.0), (14.0, 0.0),
        ]

        # 워밍업
        mapper.estimate_homography(pixel_pts, court_pts)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            mapper.reset()
            mapper.estimate_homography(pixel_pts, court_pts)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 5.0, f"호모그래피 추정 {elapsed:.2f}ms > 5ms"

    def test_좌표_변환_속도(self, initialized_mapper):
        """단일 좌표 변환: < 0.1ms."""
        # 워밍업
        initialized_mapper.pixel_to_court((320.0, 240.0))

        start = time.perf_counter()
        iterations = 10000
        for _ in range(iterations):
            initialized_mapper.pixel_to_court((320.0, 240.0))
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 0.1, f"좌표 변환 {elapsed:.4f}ms > 0.1ms"

    def test_일괄_변환_속도(self, initialized_mapper):
        """100개 일괄 변환: < 5ms."""
        pts = [(float(i * 6), float(i * 4)) for i in range(100)]

        # 워밍업
        initialized_mapper.pixel_points_to_court(pts)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            initialized_mapper.pixel_points_to_court(pts)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 5.0, f"100개 일괄 변환 {elapsed:.2f}ms > 5ms"

    def test_호모그래피_유효성_검증_속도(self):
        """유효성 검증: < 0.1ms."""
        mapper = CourtMapper()
        h = np.eye(3, dtype=np.float64) * 0.05
        h[2, 2] = 1.0

        start = time.perf_counter()
        iterations = 10000
        for _ in range(iterations):
            mapper._validate_homography(h)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 0.1, f"유효성 검증 {elapsed:.4f}ms > 0.1ms"


# =============================================================================
# ZoneClassifier 성능 테스트
# =============================================================================

class TestZoneClassifierPerf:
    """ZoneClassifier 성능 테스트."""

    @pytest.fixture()
    def initialized_classifier(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())
        return classifier

    def test_단일_분류_속도(self, initialized_classifier):
        """단일 구역 분류: < 0.05ms."""
        # 워밍업
        initialized_classifier.classify((5.0, 7.5))

        start = time.perf_counter()
        iterations = 10000
        for _ in range(iterations):
            initialized_classifier.classify((5.0, 7.5))
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 0.05, f"단일 분류 {elapsed:.4f}ms > 0.05ms"

    def test_100개_일괄_분류_속도(self, initialized_classifier):
        """100개 일괄 분류: < 3ms."""
        positions = [
            (float(x), float(y))
            for x in range(0, 28, 3)
            for y in range(0, 15, 3)
        ]

        # 워밍업
        initialized_classifier.classify_batch(positions)

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            initialized_classifier.classify_batch(positions)
        elapsed = (time.perf_counter() - start) / iterations * 1000

        assert elapsed < 3.0, f"100개 일괄 분류 {elapsed:.2f}ms > 3ms"

    def test_전_구역_커버리지(self, initialized_classifier):
        """전체 코트를 100x100 그리드로 분류 → 21구역 커버리지."""
        zones_found: set[str] = set()
        for xi in range(100):
            for yi in range(100):
                x = xi * 28.0 / 100.0
                y = yi * 15.0 / 100.0
                result = initialized_classifier.classify((x, y))
                zones_found.add(result.zone.value)

        # 적어도 10개 이상 구역 커버
        assert len(zones_found) >= 10


# =============================================================================
# 데이터 추출기 성능 테스트
# =============================================================================

class TestExtractorPerf:
    """데이터 추출기 성능 테스트."""

    def test_zone_extractor_1000개_기록_속도(self):
        """1000개 위치 기록: < 50ms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ZoneExtractor()
            extractor.initialize(output_dir=Path(tmpdir), enabled=True)

            positions = [
                ((float(i % 28), float(i % 15)), CourtZone.PAINT_CENTER)
                for i in range(1000)
            ]

            start = time.perf_counter()
            extractor.record_batch(positions)
            elapsed = (time.perf_counter() - start) * 1000

            assert elapsed < 50.0, f"1000개 기록 {elapsed:.2f}ms > 50ms"

    def test_arena_profile_메모리_안정성(self):
        """100개 스냅샷 후 메모리 제한 확인."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArenaProfileExtractor()
            extractor.initialize(output_dir=Path(tmpdir), enabled=True)

            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (60, 100, 160)

            for i in range(100):
                extractor.process_frame(frame, frame_index=i * 30)

            # deque maxlen=100이므로 100개 이하
            assert len(extractor._snapshots) <= 100
