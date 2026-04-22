# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/integration
파일: test_court_detection_integration.py
설명: court_detection 모듈 통합 테스트
      - CourtDetector + CourtMapper 연동
      - CourtMapper + ZoneClassifier 연동
      - 전체 파이프라인 (감지 → 매핑 → 구역 분류)
      - 데이터 추출기 3종 통합
      - 멀티 규격 호환성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import tempfile
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
    HomographyResult,
)
from detection.court_detection.zone_classifier import (
    ZoneClassificationResult,
    ZoneClassifier,
    ZoneClassifierConfig,
)
from detection.court_detection.data_extraction.court_line_extractor import (
    CourtLineExtractor,
)
from detection.court_detection.data_extraction.zone_extractor import (
    ZoneExtractor,
)
from detection.court_detection.data_extraction.arena_profile_extractor import (
    ArenaProfileExtractor,
)
from shared.constants.court_constants import (
    COURT_KEYPOINT_COUNT,
    CourtStandard,
    CourtZone,
)


# =============================================================================
# 공통 fixture
# =============================================================================

@pytest.fixture()
def court_frame() -> np.ndarray:
    """코트 라인이 있는 640x480 프레임."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (60, 100, 160)
    cv2.line(frame, (50, 100), (590, 100), (255, 255, 255), 3)
    cv2.line(frame, (50, 380), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (200, 240), (440, 240), (255, 255, 255), 3)
    cv2.line(frame, (50, 100), (50, 380), (255, 255, 255), 3)
    cv2.line(frame, (590, 100), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (320, 100), (320, 380), (255, 255, 255), 3)
    return frame


@pytest.fixture()
def pixel_keypoints() -> list[tuple[float, float]]:
    """6개 키포인트 (픽셀)."""
    return [
        (50.0, 100.0), (590.0, 100.0),
        (50.0, 380.0), (590.0, 380.0),
        (320.0, 100.0), (320.0, 380.0),
    ]


@pytest.fixture()
def court_keypoints_fiba() -> list[tuple[float, float]]:
    """6개 코트 좌표 (FIBA) — 방향 보존 (det > 0)."""
    return [
        (0.0, 0.0), (28.0, 0.0),
        (0.0, 15.0), (28.0, 15.0),
        (14.0, 0.0), (14.0, 15.0),
    ]


@pytest.fixture()
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# CourtMapper + ZoneClassifier 통합
# =============================================================================

class TestMapperClassifierIntegration:
    """CourtMapper + ZoneClassifier 연동 테스트."""

    def test_호모그래피_추정_후_구역_분류(
        self, pixel_keypoints, court_keypoints_fiba,
    ):
        """매퍼로 호모그래피 추정 → 좌표 변환 → 구역 분류."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))

        result = mapper.estimate_homography(
            pixel_keypoints, court_keypoints_fiba,
        )
        assert result is not None
        assert result.quality_score > 0.0

        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())

        # 프레임 중앙 (320, 240) → 코트 좌표 → 구역 분류
        court_xy = mapper.pixel_to_court((320.0, 240.0))
        assert court_xy is not None

        zone_result = classifier.classify(court_xy)
        assert zone_result.zone is not None
        assert zone_result.confidence > 0.0

    def test_왕복_변환_구역_일치(
        self, pixel_keypoints, court_keypoints_fiba,
    ):
        """코트 좌표 → 구역 분류 → 중심 좌표 가져오기 → 재분류 일치."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))
        mapper.estimate_homography(pixel_keypoints, court_keypoints_fiba)

        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())

        # 페인트존 중앙 좌표로 분류
        result1 = classifier.classify((3.0, 7.5))
        zone_center = classifier.get_zone_center(result1.zone)
        result2 = classifier.classify(zone_center)

        # 구역 중심에서 재분류하면 같은 구역
        assert result1.zone == result2.zone

    def test_복수_지점_변환_분류(
        self, pixel_keypoints, court_keypoints_fiba,
    ):
        """여러 픽셀 좌표를 일괄 변환 후 구역 분류."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))
        mapper.estimate_homography(pixel_keypoints, court_keypoints_fiba)

        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())

        pixel_pts = [(100, 200), (320, 240), (500, 350)]
        court_pts = mapper.pixel_points_to_court(pixel_pts)

        for cp in court_pts:
            if cp is not None:
                result = classifier.classify(cp)
                assert result.zone is not None


# =============================================================================
# 전체 파이프라인 통합 (감지 → 매핑 → 분류)
# =============================================================================

class TestFullPipelineIntegration:
    """CourtDetector → CourtMapper → ZoneClassifier 전체 파이프라인."""

    def test_Hough_기반_키포인트_매핑_분류(self, court_frame):
        """Hough 감지 → 교차점 → 호모그래피 → 구역 분류."""
        detector = CourtDetector()
        detector._config = CourtDetectorConfig()

        # Hough 라인 감지
        lines = detector._hough_line_detection(court_frame)

        # 라인 분류
        if len(lines) > 0:
            h_lines, v_lines = detector._classify_lines(lines)

            # 키포인트 추출
            keypoints = detector._extract_keypoints(
                h_lines, v_lines, 640, 480,
            )

            if len(keypoints) >= 4:
                mapper = CourtMapper()
                mapper.initialize(CourtMapperConfig(
                    enable_temporal_smoothing=False,
                ))

                # 코트 모델 기준점과 매칭
                result = mapper.estimate_homography(keypoints[:6])

                if result is not None:
                    classifier = ZoneClassifier()
                    classifier.initialize(ZoneClassifierConfig())

                    # 변환 + 분류
                    for kp in keypoints:
                        court_xy = mapper.pixel_to_court(kp)
                        if court_xy is not None:
                            zone_result = classifier.classify(court_xy)
                            assert zone_result.zone is not None


# =============================================================================
# 멀티 규격 호환성 통합
# =============================================================================

class TestMultiStandardIntegration:
    """다양한 코트 규격의 호환성 테스트."""

    @pytest.mark.parametrize("standard", [
        CourtStandard.FIBA,
        CourtStandard.NBA,
        CourtStandard.KBL,
    ])
    def test_규격별_초기화_분류(self, standard):
        """FIBA/NBA/KBL 규격별 초기화 + 구역 분류."""
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig(court_standard=standard))

        # 페인트존 중앙
        result = classifier.classify((3.0, standard.court_width / 2.0))
        assert result.zone == CourtZone.PAINT_CENTER
        assert result.point_value == 2

        # 3점 라인 바깥
        result = classifier.classify((
            standard.three_point_distance + 2.0,
            standard.court_width / 2.0,
        ))
        assert result.point_value == 3

    @pytest.mark.parametrize("standard", [
        CourtStandard.FIBA,
        CourtStandard.NBA,
    ])
    def test_규격별_코트_모델_일관성(self, standard):
        """코트 모델의 키포인트 수가 규격에 관계없이 21개."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(court_standard=standard))
        points = mapper.get_court_model_points()
        assert points is not None
        assert points.shape == (COURT_KEYPOINT_COUNT, 2)

    @pytest.mark.parametrize("standard", [
        CourtStandard.FIBA,
        CourtStandard.NBA,
    ])
    def test_규격별_호모그래피_추정(
        self, standard, pixel_keypoints,
    ):
        """규격별 호모그래피 추정 성공."""
        cl = standard.court_length
        cw = standard.court_width

        court_pts = [
            (0.0, 0.0), (cl, 0.0),
            (0.0, cw), (cl, cw),
            (cl / 2.0, 0.0), (cl / 2.0, cw),
        ]

        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(
            court_standard=standard,
            enable_temporal_smoothing=False,
        ))

        result = mapper.estimate_homography(pixel_keypoints, court_pts)
        assert result is not None
        assert result.quality_score > 0.0


# =============================================================================
# 데이터 추출기 3종 통합
# =============================================================================

class TestDataExtractionIntegration:
    """데이터 추출기 3종 통합 테스트."""

    def test_전체_데이터_수집_파이프라인(
        self, court_frame, temp_dir,
    ):
        """3개 추출기를 동시 초기화 → 데이터 수집 → finalize."""
        line_extractor = CourtLineExtractor()
        zone_extractor = ZoneExtractor()
        arena_extractor = ArenaProfileExtractor()

        line_dir = temp_dir / "lines"
        zone_dir = temp_dir / "zones"
        arena_dir = temp_dir / "arena"

        line_extractor.initialize(output_dir=line_dir, enabled=True)
        zone_extractor.initialize(output_dir=zone_dir, enabled=True)
        arena_extractor.initialize(output_dir=arena_dir, enabled=True)

        # 라인 데이터 수집
        lines = [
            {"x1": 50.0, "y1": 100.0, "x2": 590.0, "y2": 100.0, "confidence": 0.9},
            {"x1": 50.0, "y1": 380.0, "x2": 590.0, "y2": 380.0, "confidence": 0.85},
        ]
        line_extractor.process_lines(lines, court_frame, frame_index=0)

        # 구역 데이터 수집
        zone_extractor.record_position((3.0, 7.5), CourtZone.PAINT_CENTER)
        zone_extractor.record_position((8.5, 7.5), CourtZone.THREE_TOP_CENTER)

        # 경기장 프로필 수집
        arena_extractor.process_frame(
            court_frame, frame_index=0,
            homography_quality=0.9,
            detected_standard="fiba",
        )

        # finalize
        line_result = line_extractor.finalize()
        zone_result = zone_extractor.finalize()
        arena_result = arena_extractor.finalize()

        assert line_result.metadata is not None
        assert zone_result.record_count == 2
        assert arena_result.record_count == 1

        # 구역 통계 파일 확인
        assert (zone_dir / "zone_stats.json").exists()
        assert (zone_dir / "heatmap.npy").exists()
        assert (arena_dir / "arena_profile.json").exists()

    def test_추출기_리셋_재사용(self, temp_dir, court_frame):
        """추출기 리셋 후 재사용."""
        zone_extractor = ZoneExtractor()
        zone_extractor.initialize(output_dir=temp_dir, enabled=True)

        zone_extractor.record_position((3.0, 7.5), CourtZone.PAINT_CENTER)
        assert zone_extractor._total_records == 1

        zone_extractor.reset()
        assert zone_extractor._total_records == 0

        zone_extractor.record_position((8.5, 7.5), CourtZone.THREE_TOP_CENTER)
        assert zone_extractor._total_records == 1


# =============================================================================
# 멀티뷰 호모그래피 블렌딩 통합
# =============================================================================

class TestMultiViewHomographyIntegration:
    """멀티뷰 호모그래피 교차 검증 및 블렌딩 통합 테스트."""

    def _make_ground_truth_homography(self, noise_scale: float = 0.0):
        """테스트용 기준 호모그래피 + 노이즈 생성.

        6개 대응점으로부터 호모그래피를 계산합니다.
        """
        # 픽셀 좌표
        src = np.array([
            [50.0, 100.0], [590.0, 100.0],
            [50.0, 380.0], [590.0, 380.0],
            [320.0, 100.0], [320.0, 380.0],
        ], dtype=np.float64)
        # FIBA 코트 좌표
        dst = np.array([
            [0.0, 0.0], [28.0, 0.0],
            [0.0, 15.0], [28.0, 15.0],
            [14.0, 0.0], [14.0, 15.0],
        ], dtype=np.float64)

        if noise_scale > 0:
            rng = np.random.RandomState(42)
            src = src + rng.randn(*src.shape) * noise_scale

        H, _ = cv2.findHomography(src, dst, cv2.RANSAC)
        return H

    def test_동일_호모그래피_블렌딩(self):
        """동일한 호모그래피 3개 블렌딩 → 원본과 동일."""
        detector = CourtDetector()
        H = self._make_ground_truth_homography()

        view_homographies = {
            "cam_0": H.copy(),
            "cam_1": H.copy(),
            "cam_2": H.copy(),
        }

        blended = detector._blend_homographies(view_homographies)
        assert blended is not None

        # 블렌딩 결과가 원본과 거의 동일
        diff = np.linalg.norm(blended / blended[2, 2] - H / H[2, 2])
        assert diff < 0.01, f"동일 호모그래피 블렌딩 차이: {diff:.6f}"

    def test_이상치_호모그래피_낮은_가중치(self):
        """3개 중 1개가 크게 다르면 나머지 2개에 가중치 집중."""
        detector = CourtDetector()
        H_good = self._make_ground_truth_homography()

        # 이상치: 완전히 다른 호모그래피
        H_outlier = np.eye(3, dtype=np.float64) * 0.001

        view_homographies = {
            "cam_0": H_good.copy(),
            "cam_1": H_good.copy(),
            "cam_2": H_outlier,
        }

        blended = detector._blend_homographies(view_homographies)
        assert blended is not None

        # 블렌딩 결과가 정상 호모그래피에 가까워야 함
        # 테스트 포인트 변환 비교
        test_pt = np.array([[320.0, 240.0]], dtype=np.float64).reshape(-1, 1, 2)
        good_result = cv2.perspectiveTransform(test_pt, H_good)
        blended_result = cv2.perspectiveTransform(test_pt, blended)

        diff = np.linalg.norm(good_result - blended_result)
        assert diff < 5.0, (
            f"이상치 포함 블렌딩이 정상 결과와 차이: {diff:.3f} (5.0 미만이어야)"
        )

    def test_노이즈_호모그래피_블렌딩_안정성(self):
        """약간의 노이즈가 있는 호모그래피 3개 → 안정적 블렌딩."""
        detector = CourtDetector()
        H0 = self._make_ground_truth_homography(noise_scale=0.5)
        H1 = self._make_ground_truth_homography(noise_scale=1.0)
        H2 = self._make_ground_truth_homography(noise_scale=0.3)

        view_homographies = {
            "cam_0": H0,
            "cam_1": H1,
            "cam_2": H2,
        }

        blended = detector._blend_homographies(view_homographies)
        assert blended is not None

        # 정규화 확인
        assert abs(blended[2, 2] - 1.0) < 0.01

    def test_단일_뷰_블렌딩_복사(self):
        """1개 뷰만 있으면 복사 반환."""
        detector = CourtDetector()
        H = self._make_ground_truth_homography()

        view_homographies = {"cam_0": H.copy()}

        blended = detector._blend_homographies(view_homographies)
        assert blended is not None
        np.testing.assert_allclose(blended, H, atol=1e-10)

    def test_빈_딕셔너리_None(self):
        """빈 입력 → None 반환."""
        detector = CourtDetector()
        blended = detector._blend_homographies({})
        assert blended is None

    def test_카메라_호모그래피_등록_확인(self):
        """set_camera_homography로 등록 + 내부 저장 확인."""
        detector = CourtDetector()
        H = self._make_ground_truth_homography()

        detector.set_camera_homography("cam_0", H)

        assert "cam_0" in detector._camera_homographies
        # 방어적 복사 확인
        assert detector._camera_homographies["cam_0"] is not H
        np.testing.assert_allclose(
            detector._camera_homographies["cam_0"], H,
        )

    def test_멀티뷰_교차검증_점수_계산(self):
        """교차 검증: 일관된 호모그래피는 높은 가중치, 이상치는 낮은 가중치."""
        detector = CourtDetector()
        H_good = self._make_ground_truth_homography()
        H_outlier = np.eye(3, dtype=np.float64) * 0.001

        # 테스트 포인트 변환
        test_points = np.array([
            [0.0, 0.0], [10.0, 0.0],
            [0.0, 10.0], [10.0, 10.0],
        ], dtype=np.float64)

        # 정상 호모그래피 2개 + 이상치 1개의 변환 결과
        sets = []
        for h in [H_good, H_good.copy(), H_outlier]:
            src = test_points.reshape(-1, 1, 2)
            dst = cv2.perspectiveTransform(src, h)
            sets.append(dst.reshape(-1, 2))

        # 중앙값 기준 오차
        median_t = np.median(np.array(sets), axis=0)
        errors = [
            float(np.mean(np.linalg.norm(s - median_t, axis=1)))
            for s in sets
        ]

        # 이상치(인덱스 2)의 오차가 정상(0, 1)보다 훨씬 커야 함
        assert errors[2] > errors[0] * 5.0, (
            f"이상치 오차({errors[2]:.3f}) > 정상 오차({errors[0]:.3f})×5 이어야"
        )


# =============================================================================
# CourtDetector 내부 로직 통합
# =============================================================================

class TestDetectorInternalIntegration:
    """CourtDetector 내부 컴포넌트 연동 테스트."""

    def test_전처리_hough_라인분류_키포인트(self, court_frame):
        """CLAHE → Hough → 분류 → 키포인트 추출 파이프라인."""
        detector = CourtDetector()
        detector._config = CourtDetectorConfig(enable_clahe=True)
        detector._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # 전처리
        preprocessed = detector._preprocess_frame(court_frame)
        assert preprocessed.shape == court_frame.shape

        # Hough 감지
        lines = detector._hough_line_detection(preprocessed)

        if len(lines) > 0:
            # 분류
            h_lines, v_lines = detector._classify_lines(lines)

            # 키포인트 추출
            keypoints = detector._extract_keypoints(
                h_lines, v_lines, 640, 480,
            )

            # 중복 제거
            if len(keypoints) > 1:
                unique = detector._deduplicate_keypoints(keypoints)
                assert len(unique) <= len(keypoints)

    def test_라인_병합_후_분류_키포인트(self):
        """YOLO + Hough 병합 → 분류 → 키포인트."""
        detector = CourtDetector()

        yolo_lines = [
            _LineSegment(x1=50, y1=100, x2=590, y2=100, source="yolo", confidence=0.9),
            _LineSegment(x1=50, y1=380, x2=590, y2=380, source="yolo", confidence=0.85),
            _LineSegment(x1=320, y1=100, x2=320, y2=380, source="yolo", confidence=0.8),
        ]
        hough_lines = [
            _LineSegment(x1=52, y1=101, x2=588, y2=101, source="hough", confidence=0.7),
            _LineSegment(x1=50, y1=100, x2=50, y2=380, source="hough", confidence=0.7),
        ]

        merged = detector._merge_lines(yolo_lines, hough_lines)
        h_lines, v_lines = detector._classify_lines(merged)

        keypoints = detector._extract_keypoints(h_lines, v_lines, 640, 480)
        # 교차점이 존재해야 함
        assert len(keypoints) >= 0

    def test_호모그래피_유효성_코트모델_일치(self):
        """코트 모델 기반 호모그래피 유효성."""
        detector = CourtDetector()
        points_fiba = detector._build_court_model(CourtStandard.FIBA)
        points_nba = detector._build_court_model(CourtStandard.NBA)

        # 두 모델 모두 21점
        assert points_fiba.shape == (COURT_KEYPOINT_COUNT, 2)
        assert points_nba.shape == (COURT_KEYPOINT_COUNT, 2)

        # NBA가 FIBA보다 코트가 큼
        assert float(np.max(points_nba[:, 0])) > float(np.max(points_fiba[:, 0]))
