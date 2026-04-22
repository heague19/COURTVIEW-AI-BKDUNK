# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection
파일: conftest.py
설명: ball_detection 모듈 테스트 공통 fixture
      - YOLO 모델 모킹
      - BallDetection / Track DTO 팩토리
      - 프레임 생성기
      - BallStateMachine / BallTracker 초기화 fixture

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.ball_constants import BallState
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import BoundingBox, Point2D
from shared.dto.tracking_dto import KalmanState, Track, TrackState, TrackedObjectType


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
def orange_ball_frame() -> NDArray[np.uint8]:
    """
    농구공 색상이 있는 테스트 프레임.

    중앙에 주황색 원(반지름 20px)이 있는 640x480 프레임.
    HSV 색상 검증 테스트용.
    """
    import cv2

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 농구공 색상 (BGR: 주황색)
    cv2.circle(frame, (320, 240), 20, (30, 100, 200), -1)
    return frame


# =============================================================================
# DTO 팩토리 fixture
# =============================================================================

@pytest.fixture()
def make_ball_detection():
    """BallDetection DTO 팩토리 함수."""

    def _factory(
        x: float = 320.0,
        y: float = 240.0,
        confidence: float = 0.9,
        w: float = 40.0,
        h: float = 40.0,
        frame_index: int = 0,
        camera_id: str | None = None,
        state: BallState = BallState.LOST,
    ) -> BallDetection:
        return BallDetection(
            position=Point2D(x=x, y=y),
            confidence=confidence,
            bbox=BoundingBox(
                x=x - w / 2, y=y - h / 2,
                width=w, height=h,
            ),
            radius_pixels=min(w, h) / 2.0,
            frame_index=frame_index,
            camera_id=camera_id,
            state=state,
        )

    return _factory


@pytest.fixture()
def single_detection(make_ball_detection) -> BallDetection:
    """단일 공 감지 DTO (중앙, 신뢰도 0.9)."""
    return make_ball_detection()


@pytest.fixture()
def make_kalman_state():
    """KalmanState DTO 팩토리 함수."""

    def _factory(
        cx: float = 320.0,
        cy: float = 240.0,
        w: float = 40.0,
        h: float = 40.0,
        vx: float = 0.0,
        vy: float = 0.0,
    ) -> KalmanState:
        mean = np.array(
            [cx, cy, w, h, vx, vy, 0.0, 0.0], dtype=np.float64,
        )
        cov = np.eye(8, dtype=np.float64)
        return KalmanState(
            mean=mean,
            covariance=cov,
            state_dim=8,
            measurement_dim=4,
        )

    return _factory


# =============================================================================
# 모델 모킹 fixture
# =============================================================================

@pytest.fixture()
def mock_yolo_model():
    """
    ultralytics.YOLO 모델 모킹.

    predict() 호출 시 빈 결과 반환.
    """
    model = MagicMock()
    # 기본: 빈 결과 반환
    result_mock = MagicMock()
    result_mock.boxes = MagicMock()
    result_mock.boxes.data = MagicMock()
    result_mock.boxes.data.cpu.return_value.numpy.return_value = np.empty(
        (0, 6), dtype=np.float32,
    )
    result_mock.boxes.xyxy = MagicMock()
    result_mock.boxes.xyxy.cpu.return_value.numpy.return_value = np.empty(
        (0, 4), dtype=np.float32,
    )
    result_mock.boxes.conf = MagicMock()
    result_mock.boxes.conf.cpu.return_value.numpy.return_value = np.empty(
        (0,), dtype=np.float32,
    )
    result_mock.boxes.cls = MagicMock()
    result_mock.boxes.cls.cpu.return_value.numpy.return_value = np.empty(
        (0,), dtype=np.float32,
    )
    model.predict.return_value = [result_mock]
    return model


@pytest.fixture()
def mock_yolo_with_detections():
    """
    감지 결과가 있는 YOLO 모델 모킹.

    중앙(300, 220, 340, 260) 위치에 신뢰도 0.92 감지 반환.
    """
    model = MagicMock()
    result_mock = MagicMock()

    # xyxy 형식: (x1, y1, x2, y2, conf, cls)
    boxes_data = np.array(
        [[300.0, 220.0, 340.0, 260.0, 0.92, 0.0]],
        dtype=np.float32,
    )
    result_mock.boxes = MagicMock()
    result_mock.boxes.data = MagicMock()
    result_mock.boxes.data.cpu.return_value.numpy.return_value = boxes_data

    xyxy = np.array([[300.0, 220.0, 340.0, 260.0]], dtype=np.float32)
    result_mock.boxes.xyxy = MagicMock()
    result_mock.boxes.xyxy.cpu.return_value.numpy.return_value = xyxy

    conf = np.array([0.92], dtype=np.float32)
    result_mock.boxes.conf = MagicMock()
    result_mock.boxes.conf.cpu.return_value.numpy.return_value = conf

    cls = np.array([0.0], dtype=np.float32)
    result_mock.boxes.cls = MagicMock()
    result_mock.boxes.cls.cpu.return_value.numpy.return_value = cls

    model.predict.return_value = [result_mock]
    return model


@pytest.fixture()
def temp_model_file(tmp_path: Path) -> Path:
    """임시 YOLO 모델 파일 (빈 파일)."""
    model_path = tmp_path / "test_model.pt"
    model_path.write_bytes(b"fake_model_data")
    return model_path


# =============================================================================
# BallTracker fixture
# =============================================================================

@pytest.fixture()
def tracker():
    """초기화된 BallTracker 인스턴스."""
    from detection.ball_detection.ball_tracker import (
        BallTracker,
        BallTrackerConfig,
    )

    t = BallTracker()
    t.initialize(BallTrackerConfig())
    return t


@pytest.fixture()
def tracker_config():
    """기본 BallTrackerConfig."""
    from detection.ball_detection.ball_tracker import BallTrackerConfig

    return BallTrackerConfig()


# =============================================================================
# BallStateMachine fixture
# =============================================================================

@pytest.fixture()
def state_machine():
    """초기화된 BallStateMachine 인스턴스."""
    from detection.ball_detection.ball_state import (
        BallStateMachine,
        BallStateMachineConfig,
    )

    fsm = BallStateMachine()
    fsm.initialize(BallStateMachineConfig())
    return fsm


@pytest.fixture()
def state_machine_config():
    """기본 BallStateMachineConfig."""
    from detection.ball_detection.ball_state import BallStateMachineConfig

    return BallStateMachineConfig()


# =============================================================================
# 선수 위치 fixture
# =============================================================================

@pytest.fixture()
def make_player_position():
    """PlayerPosition 팩토리 함수."""
    from detection.ball_detection.ball_state import PlayerPosition

    def _factory(
        player_id: int = 1,
        x: float = 300.0,
        y: float = 230.0,
        bbox_height: float = 200.0,
    ) -> PlayerPosition:
        return PlayerPosition(
            player_id=player_id,
            position=Point2D(x=x, y=y),
            bbox_height=bbox_height,
        )

    return _factory


# =============================================================================
# 임시 디렉토리 fixture (data_extraction용)
# =============================================================================

@pytest.fixture()
def extraction_output_dir(tmp_path: Path) -> Path:
    """데이터 추출기 출력 디렉토리."""
    output_dir = tmp_path / "extraction_output"
    output_dir.mkdir()
    return output_dir
