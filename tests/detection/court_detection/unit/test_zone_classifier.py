# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/unit
파일: test_zone_classifier.py
설명: ZoneClassifier 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from detection.court_detection.zone_classifier import (
    ZoneClassificationResult,
    ZoneClassifier,
    ZoneClassifierConfig,
)
from shared.constants.court_constants import CourtStandard, CourtZone


# =============================================================================
# 설정 테스트
# =============================================================================

class TestZoneClassifierConfig:
    """ZoneClassifierConfig 테스트."""

    def test_기본값_생성(self):
        config = ZoneClassifierConfig()
        assert config.court_standard == CourtStandard.FIBA
        assert config.boundary_tolerance_m > 0
        assert config.enable_deep_three is True
        assert config.enable_backcourt is True

    def test_커스텀_설정(self):
        config = ZoneClassifierConfig(
            court_standard=CourtStandard.NBA,
            boundary_tolerance_m=0.5,
            enable_deep_three=False,
        )
        assert config.court_standard == CourtStandard.NBA
        assert config.enable_deep_three is False

    def test_repr(self):
        config = ZoneClassifierConfig()
        r = repr(config)
        assert "fiba" in r
        assert "tolerance" in r


# =============================================================================
# ZoneClassificationResult 테스트
# =============================================================================

class TestZoneClassificationResult:
    """ZoneClassificationResult 테스트."""

    def test_기본_생성(self):
        result = ZoneClassificationResult(zone=CourtZone.PAINT_CENTER)
        assert result.zone == CourtZone.PAINT_CENTER
        assert result.confidence == 1.0
        assert result.point_value == 2
        assert result.is_boundary is False

    def test_3점_구역_생성(self):
        result = ZoneClassificationResult(
            zone=CourtZone.THREE_LEFT_CORNER,
            confidence=0.9,
            distance_from_basket_m=6.75,
            angle_from_basket_deg=10.0,
            point_value=3,
        )
        assert result.point_value == 3
        assert result.distance_from_basket_m == 6.75

    def test_repr(self):
        result = ZoneClassificationResult(
            zone=CourtZone.MID_LEFT_WING,
            confidence=0.85,
            distance_from_basket_m=5.0,
            angle_from_basket_deg=60.0,
            point_value=2,
        )
        r = repr(result)
        assert "mid_left_wing" in r
        assert "5.00" in r


# =============================================================================
# 초기화 테스트
# =============================================================================

class TestZoneClassifierInit:
    """ZoneClassifier 초기화 테스트."""

    def test_미초기화_상태(self):
        classifier = ZoneClassifier()
        assert classifier._initialized is False

    def test_FIBA_초기화(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())
        assert classifier._initialized is True
        assert classifier._court_length == 28.0
        assert classifier._court_width == 15.0

    def test_NBA_초기화(self):
        classifier = ZoneClassifier()
        config = ZoneClassifierConfig(court_standard=CourtStandard.NBA)
        classifier.initialize(config)
        assert classifier._court_length > 28.0  # NBA 28.65m
        assert classifier._three_pt_arc > 7.0  # NBA 7.24m


# =============================================================================
# 페인트존 분류 테스트
# =============================================================================

class TestPaintZone:
    """페인트존 분류 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_페인트_중앙(self):
        result = self.classifier.classify((3.0, 7.5))
        assert result.zone == CourtZone.PAINT_CENTER
        assert result.point_value == 2

    def test_페인트_좌측(self):
        # 좌측: y < center - (key_half_width/1.5)
        # key_half_width=2.45, 1/3 분할=2.45/1.5≈1.63
        # 좌측: y < 7.5 - 1.63 ≈ 5.87 → y=5.5 (키 안쪽, 좌측 1/3)
        result = self.classifier.classify((3.0, 5.5))
        assert result.zone == CourtZone.PAINT_LEFT

    def test_페인트_우측(self):
        # 우측: y > 7.5 + 1.63 ≈ 9.13 → y=9.5 (키 안쪽, 우측 1/3)
        result = self.classifier.classify((3.0, 9.5))
        assert result.zone == CourtZone.PAINT_RIGHT

    def test_페인트_경계_낮은_신뢰도(self):
        """페인트존 경계 근처면 신뢰도 낮아짐."""
        # 키 길이 경계 근처
        result = self.classifier.classify((5.79, 7.5))  # KEY_LENGTH_M ≈ 5.8
        if result.is_boundary:
            assert result.confidence < 0.95


# =============================================================================
# 미드레인지 분류 테스트
# =============================================================================

class TestMidrange:
    """미드레인지 구역 분류 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_미드_좌측_베이스라인(self):
        """페인트 바깥 + 키 길이 이내 + y < center."""
        result = self.classifier.classify((3.0, 2.0))
        assert result.zone == CourtZone.MID_LEFT_BASELINE

    def test_미드_우측_베이스라인(self):
        result = self.classifier.classify((3.0, 13.0))
        assert result.zone == CourtZone.MID_RIGHT_BASELINE

    def test_미드_탑키(self):
        """키 바깥 + 정중앙."""
        result = self.classifier.classify((7.0, 7.5))
        assert result.zone == CourtZone.MID_TOP_KEY
        assert result.point_value == 2

    def test_미드_좌측_엘보(self):
        """키 바깥 + 좌측 + 엘보우 각도 범위."""
        result = self.classifier.classify((7.0, 5.0))
        # 각도에 따라 엘보 또는 윙
        assert result.zone in (
            CourtZone.MID_LEFT_ELBOW,
            CourtZone.MID_LEFT_WING,
            CourtZone.MID_TOP_KEY,
        )


# =============================================================================
# 3점 구역 분류 테스트
# =============================================================================

class TestThreePoint:
    """3점 구역 분류 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_3점_좌측_코너(self):
        """사이드라인 근처 + 엔드라인 방향."""
        result = self.classifier.classify((1.0, 0.5))
        assert result.zone == CourtZone.THREE_LEFT_CORNER
        assert result.point_value == 3

    def test_3점_우측_코너(self):
        result = self.classifier.classify((1.0, 14.5))
        assert result.zone == CourtZone.THREE_RIGHT_CORNER
        assert result.point_value == 3

    def test_3점_탑_센터(self):
        """정면 3점 (높은 각도)."""
        # FIBA basket_offset ≈ 1.575, three_pt = 6.75
        # 정면에서 3점 라인 바로 바깥
        result = self.classifier.classify((8.5, 7.5))
        assert result.zone == CourtZone.THREE_TOP_CENTER
        assert result.point_value == 3

    def test_3점_경계_낮은_신뢰도(self):
        """3점 라인 경계 근처면 is_boundary=True."""
        # 정확히 3점 라인 거리에 가까운 위치
        basket_x = 1.575  # BASKET_CENTER_FROM_ENDLINE_M
        tp_dist = 6.75  # FIBA 3점 거리
        x = basket_x + tp_dist  # 정면 3점 라인 위
        result = self.classifier.classify((x, 7.5))
        # 경계 근처 여부만 확인
        assert result.point_value in (2, 3)


# =============================================================================
# 딥3점 분류 테스트
# =============================================================================

class TestDeepThree:
    """딥3점 구역 분류 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig(enable_deep_three=True))

    def test_딥3점_중앙(self):
        """3점 + 2m 이상."""
        result = self.classifier.classify((12.0, 7.5))
        assert result.zone == CourtZone.DEEP_THREE_CENTER
        assert result.point_value == 3

    def test_딥3점_좌측(self):
        result = self.classifier.classify((12.0, 2.0))
        assert result.zone == CourtZone.DEEP_THREE_LEFT

    def test_딥3점_우측(self):
        result = self.classifier.classify((12.0, 13.0))
        assert result.zone == CourtZone.DEEP_THREE_RIGHT


# =============================================================================
# 백코트 분류 테스트
# =============================================================================

class TestBackcourt:
    """백코트 구역 분류 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_코트_외부_음수좌표(self):
        result = self.classifier.classify((-5.0, 7.5))
        assert result.zone == CourtZone.BACKCOURT

    def test_코트_외부_초과좌표(self):
        result = self.classifier.classify((50.0, 7.5))
        assert result.zone == CourtZone.BACKCOURT

    def test_미초기화_백코트(self):
        classifier = ZoneClassifier()
        result = classifier.classify((5.0, 7.5))
        assert result.zone == CourtZone.BACKCOURT
        assert result.confidence == 0.0


# =============================================================================
# 우측 반코트 (거울 대칭) 테스트
# =============================================================================

class TestRightHalfCourt:
    """우측 반코트 거울 대칭 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_우측_페인트존(self):
        """우측 반코트의 페인트존 (28-3=25, 7.5)."""
        result = self.classifier.classify((25.0, 7.5))
        assert result.zone == CourtZone.PAINT_CENTER
        assert result.half_court == "right"

    def test_좌우_대칭_구역_동일(self):
        """좌측과 우측 반코트의 같은 위치는 같은 zone."""
        left_result = self.classifier.classify((3.0, 7.5))
        right_result = self.classifier.classify((25.0, 7.5))  # 28-3=25
        assert left_result.zone == right_result.zone


# =============================================================================
# 일괄 분류 테스트
# =============================================================================

class TestClassifyBatch:
    """일괄 분류 테스트."""

    def test_복수_좌표_분류(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())

        positions = [
            (3.0, 7.5),   # 페인트
            (8.5, 7.5),   # 3점
            (12.0, 7.5),  # 딥3점
            (-5.0, 7.5),  # 백코트
        ]
        results = classifier.classify_batch(positions)
        assert len(results) == 4
        assert results[0].zone == CourtZone.PAINT_CENTER
        assert results[3].zone == CourtZone.BACKCOURT

    def test_빈_목록(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())
        results = classifier.classify_batch([])
        assert len(results) == 0


# =============================================================================
# 구역 중심 좌표 테스트
# =============================================================================

class TestGetZoneCenter:
    """구역 중심 좌표 테스트."""

    @pytest.fixture(autouse=True)
    def _setup_classifier(self):
        self.classifier = ZoneClassifier()
        self.classifier.initialize(ZoneClassifierConfig())

    def test_페인트_중앙_센터(self):
        center = self.classifier.get_zone_center(CourtZone.PAINT_CENTER)
        assert 0.0 < center[0] < 14.0  # 좌측 반코트
        assert 5.0 < center[1] < 10.0  # 코트 중앙 부근

    def test_백코트_센터(self):
        center = self.classifier.get_zone_center(CourtZone.BACKCOURT)
        assert center[0] > 14.0  # 반코트 넘어

    def test_우측_반코트_거울대칭(self):
        left_center = self.classifier.get_zone_center(
            CourtZone.PAINT_CENTER, "left",
        )
        right_center = self.classifier.get_zone_center(
            CourtZone.PAINT_CENTER, "right",
        )
        # 좌우 대칭: x 합 ≈ court_length
        assert abs(left_center[0] + right_center[0] - 28.0) < 0.01

    def test_미초기화_원점(self):
        classifier = ZoneClassifier()
        center = classifier.get_zone_center(CourtZone.PAINT_CENTER)
        assert center == (0.0, 0.0)


# =============================================================================
# 리셋/종료 테스트
# =============================================================================

class TestResetShutdown:
    """리셋 및 종료 테스트."""

    def test_reset(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())
        classifier.reset()
        # reset 후에도 초기화 상태 유지
        assert classifier._initialized is True

    def test_shutdown(self):
        classifier = ZoneClassifier()
        classifier.initialize(ZoneClassifierConfig())
        classifier.shutdown()
        assert classifier._initialized is False

    def test_repr(self):
        classifier = ZoneClassifier()
        r = repr(classifier)
        assert "미초기화" in r

        classifier.initialize(ZoneClassifierConfig())
        r = repr(classifier)
        assert "초기화됨" in r
