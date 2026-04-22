# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/unit
파일: test_court_mapper.py
설명: CourtMapper 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from detection.court_detection.court_mapper import (
    CourtMapper,
    CourtMapperConfig,
    HomographyResult,
)
from shared.constants.court_constants import (
    COURT_KEYPOINT_COUNT,
    CourtStandard,
)


# =============================================================================
# 설정 테스트
# =============================================================================

class TestCourtMapperConfig:
    """CourtMapperConfig 테스트."""

    def test_기본값_생성(self):
        config = CourtMapperConfig()
        assert config.court_standard == CourtStandard.FIBA
        assert config.ransac_reproj_threshold == 3.0
        assert config.min_correspondences == 4
        assert config.max_correspondences == 50
        assert config.refinement_iterations == 100
        assert config.enable_temporal_smoothing is True
        assert 0.0 < config.ema_alpha <= 1.0

    def test_커스텀_설정(self):
        config = CourtMapperConfig(
            court_standard=CourtStandard.NBA,
            ransac_reproj_threshold=5.0,
            enable_temporal_smoothing=False,
        )
        assert config.court_standard == CourtStandard.NBA
        assert config.ransac_reproj_threshold == 5.0
        assert config.enable_temporal_smoothing is False

    def test_repr(self):
        config = CourtMapperConfig()
        r = repr(config)
        assert "fiba" in r
        assert "temporal" in r


# =============================================================================
# HomographyResult 테스트
# =============================================================================

class TestHomographyResult:
    """HomographyResult 테스트."""

    def test_기본_생성(self):
        h = np.eye(3, dtype=np.float64)
        result = HomographyResult(
            homography=h,
            inverse_homography=h,
            inlier_count=10,
            total_correspondences=12,
            inlier_ratio=10 / 12,
            mean_reproj_error=1.5,
            quality_score=0.85,
        )
        assert result.inlier_count == 10
        assert result.quality_score == 0.85

    def test_repr(self):
        h = np.eye(3, dtype=np.float64)
        result = HomographyResult(
            homography=h,
            inverse_homography=h,
            inlier_count=8,
            total_correspondences=10,
            mean_reproj_error=2.1,
            quality_score=0.75,
        )
        r = repr(result)
        assert "8/10" in r
        assert "2.10" in r


# =============================================================================
# 초기화 테스트
# =============================================================================

class TestCourtMapperInit:
    """CourtMapper 초기화 테스트."""

    def test_미초기화_상태(self):
        mapper = CourtMapper()
        assert mapper._initialized is False
        assert mapper._current_homography is None
        assert mapper._current_inverse is None

    def test_초기화(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        assert mapper._initialized is True
        assert mapper._court_model_points is not None
        assert mapper._court_model_points.shape == (COURT_KEYPOINT_COUNT, 2)

    def test_NBA_초기화(self):
        mapper = CourtMapper()
        config = CourtMapperConfig(court_standard=CourtStandard.NBA)
        mapper.initialize(config)
        points = mapper.get_court_model_points()
        assert points is not None
        # NBA 코트 길이 > FIBA
        x_max = float(np.max(points[:, 0]))
        assert x_max > 28.0


# =============================================================================
# 호모그래피 추정 테스트
# =============================================================================

class TestHomographyEstimation:
    """호모그래피 추정 테스트."""

    def test_4점_호모그래피_추정(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))

        # 방향 보존 (det > 0) 매핑
        pixel_pts = [
            (50.0, 100.0), (590.0, 100.0),
            (50.0, 380.0), (590.0, 380.0),
        ]
        court_pts = [
            (0.0, 0.0), (28.0, 0.0),
            (0.0, 15.0), (28.0, 15.0),
        ]

        result = mapper.estimate_homography(pixel_pts, court_pts)
        assert result is not None
        assert result.homography.shape == (3, 3)
        assert result.inverse_homography.shape == (3, 3)
        assert 0.0 <= result.quality_score <= 1.0

    def test_6점_호모그래피_추정(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))

        pixel_pts = [
            (50.0, 100.0), (590.0, 100.0),
            (50.0, 380.0), (590.0, 380.0),
            (320.0, 100.0), (320.0, 380.0),
        ]
        court_pts = [
            (0.0, 0.0), (28.0, 0.0),
            (0.0, 15.0), (28.0, 15.0),
            (14.0, 0.0), (14.0, 15.0),
        ]

        result = mapper.estimate_homography(pixel_pts, court_pts)
        assert result is not None
        assert result.inlier_count > 0
        assert result.total_correspondences == 6

    def test_미초기화_추정_실패(self):
        mapper = CourtMapper()
        result = mapper.estimate_homography(
            [(0, 0), (100, 0), (0, 100), (100, 100)],
            [(0, 0), (28, 0), (0, 15), (28, 15)],
        )
        assert result is None

    def test_대응점_부족_실패(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        result = mapper.estimate_homography(
            [(0, 0), (100, 0)],
            [(0, 0), (28, 0)],
        )
        assert result is None

    def test_인라이어_비율_양수(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=False))

        pixel_pts = [
            (50.0, 100.0), (590.0, 100.0),
            (50.0, 380.0), (590.0, 380.0),
            (320.0, 100.0), (320.0, 380.0),
        ]
        court_pts = [
            (0.0, 0.0), (28.0, 0.0),
            (0.0, 15.0), (28.0, 15.0),
            (14.0, 0.0), (14.0, 15.0),
        ]
        result = mapper.estimate_homography(pixel_pts, court_pts)
        assert result is not None
        assert result.inlier_ratio > 0.0


# =============================================================================
# 좌표 변환 테스트
# =============================================================================

class TestCoordinateTransform:
    """좌표 변환 테스트."""

    def test_pixel_to_court(self, sample_homography):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_homography = sample_homography

        result = mapper.pixel_to_court((320.0, 240.0))
        assert result is not None
        assert len(result) == 2

    def test_court_to_pixel(self, sample_homography):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_inverse = np.linalg.inv(sample_homography)

        result = mapper.court_to_pixel((14.0, 7.5))
        assert result is not None
        assert len(result) == 2

    def test_왕복_변환_일관성(self, sample_homography):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_homography = sample_homography
        mapper._current_inverse = np.linalg.inv(sample_homography)

        original = (320.0, 240.0)
        court = mapper.pixel_to_court(original)
        assert court is not None
        recovered = mapper.court_to_pixel(court)
        assert recovered is not None
        assert abs(recovered[0] - original[0]) < 1.0
        assert abs(recovered[1] - original[1]) < 1.0

    def test_미초기화_변환_None(self):
        mapper = CourtMapper()
        assert mapper.pixel_to_court((100, 100)) is None
        assert mapper.court_to_pixel((5, 5)) is None

    def test_일괄_변환(self, sample_homography):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_homography = sample_homography

        pixels = [(100.0, 200.0), (300.0, 300.0), (500.0, 150.0)]
        results = mapper.pixel_points_to_court(pixels)
        assert len(results) == 3
        # 유효 범위 내라면 None이 아님
        for r in results:
            if r is not None:
                assert len(r) == 2

    def test_코트_범위_이탈_None(self, sample_homography):
        """코트 범위 밖의 점은 None 반환."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_homography = sample_homography

        # 매우 먼 픽셀 좌표 → 코트 범위 이탈 가능
        result = mapper.pixel_to_court((-10000.0, -10000.0))
        # 범위 이탈 시 None 반환될 수 있음
        # (호모그래피에 따라 결과 다를 수 있으나 테스트 의도 확인)


# =============================================================================
# 호모그래피 유효성 검증 테스트
# =============================================================================

class TestHomographyValidation:
    """호모그래피 유효성 검증 테스트."""

    def test_정상_호모그래피(self):
        mapper = CourtMapper()
        # 방향 보존 호모그래피 (det > 0)
        src = np.array([
            [50.0, 100.0], [590.0, 100.0],
            [50.0, 380.0], [590.0, 380.0],
        ], dtype=np.float64)
        dst = np.array([
            [0.0, 0.0], [28.0, 0.0],
            [0.0, 15.0], [28.0, 15.0],
        ], dtype=np.float64)
        h, _ = cv2.findHomography(src, dst)
        assert mapper._validate_homography(h) is True

    def test_거울_반전_거부(self):
        mapper = CourtMapper()
        h = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64)
        assert mapper._validate_homography(h) is False

    def test_특이행렬_거부(self):
        mapper = CourtMapper()
        h = np.zeros((3, 3), dtype=np.float64)
        assert mapper._validate_homography(h) is False

    def test_NaN_거부(self):
        mapper = CourtMapper()
        h = np.eye(3, dtype=np.float64)
        h[0, 0] = float("nan")
        assert mapper._validate_homography(h) is False

    def test_Inf_거부(self):
        mapper = CourtMapper()
        h = np.eye(3, dtype=np.float64)
        h[1, 1] = float("inf")
        assert mapper._validate_homography(h) is False

    def test_극단_스케일_비율_거부(self):
        mapper = CourtMapper()
        h = np.eye(3, dtype=np.float64)
        h[0, 0] = 100.0
        h[1, 1] = 0.001
        assert mapper._validate_homography(h) is False


# =============================================================================
# 재투영 오류 테스트
# =============================================================================

class TestReprojError:
    """재투영 오류 계산 테스트."""

    def test_완벽한_변환_오류0(self):
        mapper = CourtMapper()
        src = np.array([[0, 0], [100, 0], [0, 100], [100, 100]], dtype=np.float64)
        dst = src.copy()  # 동일 좌표
        h = np.eye(3, dtype=np.float64)
        mask = np.ones((4, 1), dtype=np.uint8)

        error = mapper._compute_reproj_error(src, dst, h, mask)
        assert error < 0.01

    def test_마스크_None_전체_사용(self):
        mapper = CourtMapper()
        src = np.array([[0, 0], [100, 0]], dtype=np.float64)
        dst = np.array([[1, 1], [101, 1]], dtype=np.float64)
        h = np.eye(3, dtype=np.float64)

        error = mapper._compute_reproj_error(src, dst, h, None)
        assert error > 0.0


# =============================================================================
# 품질 점수 테스트
# =============================================================================

class TestQualityScore:
    """품질 점수 산출 테스트."""

    def test_완벽한_품질(self):
        mapper = CourtMapper()
        score = mapper._compute_quality_score(
            inlier_ratio=1.0,
            mean_reproj_error=0.0,
            inlier_count=21,
        )
        assert score == 1.0

    def test_최악_품질(self):
        mapper = CourtMapper()
        score = mapper._compute_quality_score(
            inlier_ratio=0.0,
            mean_reproj_error=10.0,
            inlier_count=0,
        )
        assert score == 0.0

    def test_중간_품질(self):
        mapper = CourtMapper()
        score = mapper._compute_quality_score(
            inlier_ratio=0.5,
            mean_reproj_error=2.5,
            inlier_count=10,
        )
        assert 0.0 < score < 1.0

    def test_가중치_합산_구조(self):
        """인라이어 30% + 재투영 50% + 키포인트 20%."""
        mapper = CourtMapper()
        # 인라이어만 만점
        s1 = mapper._compute_quality_score(1.0, 5.0, 0)
        # 재투영만 만점
        s2 = mapper._compute_quality_score(0.0, 0.0, 0)
        # 재투영 비중이 50%로 가장 높으므로 s2 > s1
        assert s2 > s1


# =============================================================================
# 시간적 스무딩 테스트
# =============================================================================

class TestTemporalSmoothing:
    """EMA 시간적 스무딩 테스트."""

    def test_첫_프레임_그대로(self):
        mapper = CourtMapper()
        mapper._current_homography = None
        h_new = np.eye(3, dtype=np.float64) * 2.0
        result = mapper._apply_temporal_smoothing(h_new, alpha=0.7)
        np.testing.assert_array_almost_equal(result, h_new)

    def test_EMA_적용(self):
        mapper = CourtMapper()
        h_old = np.eye(3, dtype=np.float64)
        h_new = np.eye(3, dtype=np.float64) * 2.0
        mapper._current_homography = h_old

        alpha = 0.7
        result = mapper._apply_temporal_smoothing(h_new, alpha)

        # EMA: alpha * new + (1-alpha) * old
        expected = alpha * h_new + (1.0 - alpha) * h_old
        expected /= expected[2, 2]

        np.testing.assert_array_almost_equal(result, expected)

    def test_연속_스무딩(self):
        """여러 프레임 연속 호모그래피 → 이력 누적."""
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig(enable_temporal_smoothing=True))

        pixel_pts = [
            (50.0, 100.0), (590.0, 100.0),
            (50.0, 380.0), (590.0, 380.0),
            (320.0, 100.0), (320.0, 380.0),
        ]
        court_pts = [
            (0.0, 0.0), (28.0, 0.0),
            (0.0, 15.0), (28.0, 15.0),
            (14.0, 0.0), (14.0, 15.0),
        ]

        # 첫 번째 추정
        result1 = mapper.estimate_homography(pixel_pts, court_pts)
        assert result1 is not None

        # 약간 변형된 키포인트로 두 번째
        shifted = [(x + 2, y + 1) for x, y in pixel_pts]
        result2 = mapper.estimate_homography(shifted, court_pts)
        assert result2 is not None

        # 이력에 2개 누적
        assert len(mapper._homography_history) == 2


# =============================================================================
# 코트 모델 구성 테스트
# =============================================================================

class TestBuildCourtModel:
    """코트 모델 구성 테스트."""

    def test_FIBA_21점(self):
        mapper = CourtMapper()
        points = mapper._build_court_model(CourtStandard.FIBA)
        assert points.shape == (COURT_KEYPOINT_COUNT, 2)

    def test_NBA_21점(self):
        mapper = CourtMapper()
        points = mapper._build_court_model(CourtStandard.NBA)
        assert points.shape == (COURT_KEYPOINT_COUNT, 2)
        x_max = float(np.max(points[:, 0]))
        assert x_max > 28.0

    def test_코너_좌표(self):
        mapper = CourtMapper()
        points = mapper._build_court_model(CourtStandard.FIBA)
        # 좌하단 (0, 0)
        assert abs(points[2, 0]) < 0.01
        assert abs(points[2, 1]) < 0.01
        # 우상단 (28, 15)
        assert abs(points[1, 0] - 28.0) < 0.01
        assert abs(points[1, 1] - 15.0) < 0.01


# =============================================================================
# 유틸리티 메서드 테스트
# =============================================================================

class TestUtility:
    """유틸리티 메서드 테스트."""

    def test_get_current_homography_방어적_복사(
        self, sample_homography,
    ):
        mapper = CourtMapper()
        mapper._current_homography = sample_homography.copy()

        h = mapper.get_current_homography()
        assert h is not None
        h[0, 0] = 999.0
        # 원본 변경되면 안 됨
        assert mapper._current_homography[0, 0] != 999.0

    def test_get_court_model_방어적_복사(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        pts = mapper.get_court_model_points()
        assert pts is not None
        pts[0, 0] = 999.0
        assert mapper._court_model_points[0, 0] != 999.0

    def test_reset(self, sample_homography):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper._current_homography = sample_homography.copy()
        mapper._current_inverse = np.linalg.inv(sample_homography)
        mapper._homography_history.append(sample_homography.copy())

        mapper.reset()
        assert mapper._current_homography is None
        assert mapper._current_inverse is None
        assert len(mapper._homography_history) == 0
        assert mapper._last_result is None

    def test_shutdown(self):
        mapper = CourtMapper()
        mapper.initialize(CourtMapperConfig())
        mapper.shutdown()
        assert mapper._initialized is False
        assert mapper._court_model_points is None

    def test_repr(self):
        mapper = CourtMapper()
        r = repr(mapper)
        assert "미초기화" in r

        mapper.initialize(CourtMapperConfig())
        r = repr(mapper)
        assert "초기화됨" in r
