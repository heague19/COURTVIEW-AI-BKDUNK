# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/player_detection
파일: conftest.py
설명: player_detection 모듈 테스트 공통 fixture
      - 프레임 생성기
      - _PlayerCandidate 팩토리
      - 설정 fixture

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from shared.dto.player_dto import Team
from detection.player_detection.models import (
    JerseyOCRConfig,
    PlayerDetectorConfig,
    PlayerIDManagerConfig,
    PlayerTrackerConfig,
    ReIDConfig,
    TeamClassifierConfig,
    _PlayerCandidate,
    _TrackState,
)


# =============================================================================
# 프레임 생성 fixture
# =============================================================================

@pytest.fixture()
def dummy_frame_480p() -> NDArray[np.uint8]:
    """480p BGR 더미 프레임 (640x480)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture()
def dummy_frame_1080p() -> NDArray[np.uint8]:
    """1080p BGR 더미 프레임 (1920x1080)."""
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture()
def color_frame_1080p() -> NDArray[np.uint8]:
    """1080p 컬러 프레임 (피부색 + 유니폼 색상 시뮬레이션)."""
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # 녹색 코트 배경
    frame[:] = (34, 139, 34)  # BGR: ForestGreen
    return frame


# =============================================================================
# 후보 팩토리 fixture
# =============================================================================

@pytest.fixture()
def player_candidate() -> _PlayerCandidate:
    """기본 선수 후보."""
    return _PlayerCandidate(
        bbox_x=100.0,
        bbox_y=200.0,
        bbox_w=80.0,
        bbox_h=200.0,
        yolo_confidence=0.85,
        class_id=PLAYER_CLASS_ID_PLAYER,
        combined_score=0.82,
        camera_id="cam_0",
        frame_index=0,
    )


@pytest.fixture()
def referee_candidate() -> _PlayerCandidate:
    """심판 후보."""
    return _PlayerCandidate(
        bbox_x=300.0,
        bbox_y=250.0,
        bbox_w=70.0,
        bbox_h=180.0,
        yolo_confidence=0.78,
        class_id=PLAYER_CLASS_ID_REFEREE,
        combined_score=0.75,
        camera_id="cam_0",
        frame_index=0,
    )


@pytest.fixture()
def multiple_candidates() -> list[_PlayerCandidate]:
    """다수 선수 후보 (5명)."""
    candidates = []
    for i in range(5):
        c = _PlayerCandidate(
            bbox_x=100.0 + i * 150.0,
            bbox_y=200.0,
            bbox_w=80.0,
            bbox_h=200.0,
            yolo_confidence=0.80 + i * 0.02,
            class_id=PLAYER_CLASS_ID_PLAYER,
            combined_score=0.78 + i * 0.02,
            camera_id="cam_0",
            frame_index=0,
        )
        candidates.append(c)
    return candidates


# =============================================================================
# 설정 fixture
# =============================================================================

@pytest.fixture()
def default_detector_config() -> PlayerDetectorConfig:
    """기본 감지 설정."""
    return PlayerDetectorConfig(device="cpu", half_precision=False)


@pytest.fixture()
def default_classifier_config() -> TeamClassifierConfig:
    """기본 팀 분류 설정."""
    return TeamClassifierConfig()


@pytest.fixture()
def default_ocr_config() -> JerseyOCRConfig:
    """기본 OCR 설정."""
    return JerseyOCRConfig()


@pytest.fixture()
def default_reid_config() -> ReIDConfig:
    """기본 ReID 설정."""
    return ReIDConfig(device="cpu")


@pytest.fixture()
def default_tracker_config() -> PlayerTrackerConfig:
    """기본 추적 설정."""
    return PlayerTrackerConfig()


@pytest.fixture()
def default_id_manager_config() -> PlayerIDManagerConfig:
    """기본 ID 관리 설정."""
    return PlayerIDManagerConfig()
