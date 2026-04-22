# -*- coding: utf-8 -*-
"""
player_detection/models.py 단위 테스트.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_STAFF,
)
from detection.player_detection.models import (
    JerseyOCRConfig,
    PlayerDetectorConfig,
    PlayerIDManagerConfig,
    PlayerTrackerConfig,
    ReIDConfig,
    TeamClassifierConfig,
    _JerseyRegion,
    _PlayerCandidate,
    _TrackState,
    _UniformROI,
)


# =============================================================================
# PlayerDetectorConfig
# =============================================================================

class Test_PlayerDetectorConfig:
    """PlayerDetectorConfig 테스트."""

    def test_기본값_생성(self) -> None:
        config = PlayerDetectorConfig()
        assert config.input_size == 640
        assert config.confidence_threshold == 0.4
        assert config.device == "cuda"

    def test_repr(self) -> None:
        config = PlayerDetectorConfig()
        r = repr(config)
        assert "PlayerDetectorConfig" in r
        assert "640" in r


# =============================================================================
# _PlayerCandidate
# =============================================================================

class Test_PlayerCandidate:
    """_PlayerCandidate 테스트."""

    def test_중심좌표_계산(self) -> None:
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=200, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9,
        )
        assert c.center_x == pytest.approx(140.0)
        assert c.center_y == pytest.approx(300.0)

    def test_종횡비_계산(self) -> None:
        c = _PlayerCandidate(
            bbox_x=0, bbox_y=0, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == pytest.approx(0.4)

    def test_높이_0_종횡비_안전(self) -> None:
        c = _PlayerCandidate(
            bbox_x=0, bbox_y=0, bbox_w=80, bbox_h=0,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == 0.0

    def test_면적(self) -> None:
        c = _PlayerCandidate(
            bbox_x=0, bbox_y=0, bbox_w=100, bbox_h=200,
            yolo_confidence=0.9,
        )
        assert c.area == pytest.approx(20000.0)

    def test_사람_클래스_판별(self) -> None:
        for cls_id in [PLAYER_CLASS_ID_PLAYER, PLAYER_CLASS_ID_REFEREE,
                       PLAYER_CLASS_ID_COACH, PLAYER_CLASS_ID_STAFF]:
            c = _PlayerCandidate(
                bbox_x=0, bbox_y=0, bbox_w=1, bbox_h=1,
                yolo_confidence=0.5, class_id=cls_id,
            )
            assert c.is_person_class is True

    def test_to_xyxy(self) -> None:
        c = _PlayerCandidate(
            bbox_x=10, bbox_y=20, bbox_w=30, bbox_h=40,
            yolo_confidence=0.9,
        )
        assert c.to_xyxy() == (10, 20, 40, 60)

    def test_repr(self) -> None:
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=200, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9, combined_score=0.85,
        )
        r = repr(c)
        assert "_PlayerCandidate" in r
        assert "0.900" in r


# =============================================================================
# _UniformROI
# =============================================================================

class Test_UniformROI:
    """_UniformROI 테스트."""

    def test_기본값(self) -> None:
        roi = _UniformROI()
        assert roi.is_valid is False
        assert roi.dominant_hue == 0.0

    def test_유효_ROI(self) -> None:
        roi = _UniformROI(
            dominant_hue=120, dominant_saturation=180,
            dominant_value=200, roi_pixel_count=500,
            is_valid=True,
        )
        assert roi.is_valid is True
        assert roi.dominant_hue == 120.0


# =============================================================================
# _JerseyRegion
# =============================================================================

class Test_JerseyRegion:
    """_JerseyRegion 테스트."""

    def test_유효_등번호(self) -> None:
        jr = _JerseyRegion(number=23, confidence=0.9)
        assert jr.is_valid is True

    def test_미인식(self) -> None:
        jr = _JerseyRegion()
        assert jr.is_valid is False

    def test_낮은_신뢰도(self) -> None:
        jr = _JerseyRegion(number=5, confidence=0.1)
        assert jr.is_valid is False

    def test_범위_초과(self) -> None:
        jr = _JerseyRegion(number=100, confidence=0.9)
        assert jr.is_valid is False


# =============================================================================
# _TrackState
# =============================================================================

class Test_TrackState:
    """_TrackState 테스트."""

    def test_확정_여부(self) -> None:
        ts = _TrackState(hits=3)
        assert ts.is_confirmed is True

    def test_미확정(self) -> None:
        ts = _TrackState(hits=1)
        assert ts.is_confirmed is False

    def test_사망_여부(self) -> None:
        ts = _TrackState(time_since_update=31)
        assert ts.is_dead is True

    def test_생존(self) -> None:
        ts = _TrackState(time_since_update=5)
        assert ts.is_dead is False

    def test_중심좌표(self) -> None:
        ts = _TrackState(bbox_x=10, bbox_y=20, bbox_w=30, bbox_h=40)
        cx, cy = ts.center
        assert cx == pytest.approx(25.0)
        assert cy == pytest.approx(40.0)


# =============================================================================
# Config 가중치 합 검증
# =============================================================================

class Test_ConfigWeightValidation:
    """설정 가중치 합 검증."""

    def test_ID관리_가중치합(self) -> None:
        config = PlayerIDManagerConfig()
        weight_sum = config.ocr_weight + config.reid_weight + config.tracking_weight
        assert weight_sum == pytest.approx(1.0)

    def test_ReID_기본차원(self) -> None:
        config = ReIDConfig()
        assert config.feature_dim == 512
