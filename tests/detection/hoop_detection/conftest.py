# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection
파일: conftest.py
설명: hoop_detection 모듈 테스트 공통 fixture
      - YOLO 모델 모킹 (2-class: rim/backboard)
      - HoopDetection DTO 팩토리
      - 프레임 생성기 (림/백보드 시뮬레이션)
      - HoopDetector / NetAnalyzer 초기화 fixture

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.hoop_constants import (
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_RIM,
)
from shared.interfaces.detector_interface import (
    BoundingBox as InterfaceBBox,
    HoopDetection,
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
def rim_frame() -> NDArray[np.uint8]:
    """
    림(오렌지 원) + 백보드가 있는 테스트 프레임.

    상단 중앙에 오렌지 원(림)과 그 위 직사각형(백보드)을 시뮬레이션.
    HSV 색상 검증 및 Hough Circle 테스트용.
    """
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 백보드 (흰색 직사각형)
    cv2.rectangle(frame, (270, 50), (370, 100), (255, 255, 255), -1)
    # 림 (주황색 원, 반지름 25px)
    cv2.circle(frame, (320, 130), 25, (30, 100, 230), 3)
    # 네트 (흰색 세로줄 패턴)
    for x in range(300, 345, 5):
        cv2.line(frame, (x, 155), (x, 200), (240, 240, 240), 1)
    return frame


@pytest.fixture()
def net_motion_frame_pair() -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    """
    네트 움직임 분석용 프레임 쌍 (before/after).

    before: 네트 정지 상태
    after: 네트가 아래로 이동 (스위시 시뮬레이션)
    """
    h, w = 60, 80

    before = np.full((h, w, 3), 30, dtype=np.uint8)
    # 정지 상태 네트: 수직선 패턴
    for x in range(10, 70, 8):
        cv2.line(before, (x, 5), (x, 50), (230, 230, 230), 2)

    after = np.full((h, w, 3), 30, dtype=np.uint8)
    # 아래로 이동된 네트: y +10px
    for x in range(10, 70, 8):
        cv2.line(after, (x, 15), (x, 55), (230, 230, 230), 2)

    return before, after


# =============================================================================
# HoopDetection DTO 팩토리 fixture
# =============================================================================

@pytest.fixture()
def make_hoop_detection():
    """HoopDetection DTO 팩토리 함수."""

    def _factory(
        x: float = 290.0,
        y: float = 100.0,
        width: float = 60.0,
        height: float = 40.0,
        rim_cx: float = 320.0,
        rim_cy: float = 130.0,
        rim_radius: float = 25.0,
        hoop_side: str = "left",
        net_visible: bool = True,
    ) -> HoopDetection:
        return HoopDetection(
            bounding_box=InterfaceBBox(
                x=x, y=y, width=width, height=height,
            ),
            rim_center=(rim_cx, rim_cy),
            rim_radius=rim_radius,
            hoop_side=hoop_side,
            net_visible=net_visible,
        )

    return _factory


@pytest.fixture()
def left_hoop(make_hoop_detection) -> HoopDetection:
    """왼쪽 골대 HoopDetection (기본값)."""
    return make_hoop_detection(hoop_side="left")


@pytest.fixture()
def right_hoop(make_hoop_detection) -> HoopDetection:
    """오른쪽 골대 HoopDetection."""
    return make_hoop_detection(
        x=520.0, rim_cx=550.0, hoop_side="right",
    )


# =============================================================================
# 모델 모킹 fixture
# =============================================================================

@pytest.fixture()
def mock_yolo_model():
    """
    ultralytics.YOLO 모델 모킹 (빈 결과).

    predict() 호출 시 림/백보드 0개 반환.
    """
    model = MagicMock()
    result_mock = MagicMock()
    result_mock.boxes = MagicMock()
    result_mock.boxes.__len__ = MagicMock(return_value=0)
    model.predict.return_value = [result_mock]
    return model


@pytest.fixture()
def mock_yolo_with_rim():
    """
    림 1개 감지 YOLO 모델 모킹.

    (290, 110, 350, 150) 위치에 신뢰도 0.92 림 감지.
    """
    model = MagicMock()
    result_mock = MagicMock()

    import torch

    boxes = MagicMock()
    boxes.__len__ = MagicMock(return_value=1)
    boxes.xyxy = [torch.tensor([290.0, 110.0, 350.0, 150.0])]
    boxes.conf = [torch.tensor(0.92)]
    boxes.cls = [torch.tensor(float(HOOP_CLASS_ID_RIM))]
    result_mock.boxes = boxes
    model.predict.return_value = [result_mock]
    return model


@pytest.fixture()
def mock_yolo_with_rim_and_backboard():
    """
    림 1개 + 백보드 1개 감지 YOLO 모델 모킹.
    """
    model = MagicMock()
    result_mock = MagicMock()

    import torch

    boxes = MagicMock()
    boxes.__len__ = MagicMock(return_value=2)
    boxes.xyxy = [
        torch.tensor([290.0, 110.0, 350.0, 150.0]),
        torch.tensor([270.0, 50.0, 370.0, 100.0]),
    ]
    boxes.conf = [torch.tensor(0.92), torch.tensor(0.88)]
    boxes.cls = [
        torch.tensor(float(HOOP_CLASS_ID_RIM)),
        torch.tensor(float(HOOP_CLASS_ID_BACKBOARD)),
    ]
    result_mock.boxes = boxes
    model.predict.return_value = [result_mock]
    return model


@pytest.fixture()
def temp_model_file(tmp_path: Path) -> Path:
    """임시 YOLO 모델 파일 (빈 파일)."""
    model_path = tmp_path / "COURTVIEW_hoop.pt"
    model_path.write_bytes(b"fake_model_data")
    return model_path


# =============================================================================
# NetAnalyzer fixture
# =============================================================================

@pytest.fixture()
def net_analyzer():
    """초기화된 NetAnalyzer 인스턴스."""
    from detection.hoop_detection.net_analyzer import (
        NetAnalyzer,
        NetAnalyzerConfig,
    )

    analyzer = NetAnalyzer()
    analyzer.initialize(NetAnalyzerConfig())
    return analyzer


@pytest.fixture()
def net_analyzer_config():
    """기본 NetAnalyzerConfig."""
    from detection.hoop_detection.net_analyzer import NetAnalyzerConfig

    return NetAnalyzerConfig()


# =============================================================================
# 임시 디렉토리 fixture (data_extraction용)
# =============================================================================

@pytest.fixture()
def extraction_output_dir(tmp_path: Path) -> Path:
    """데이터 추출기 출력 디렉토리."""
    output_dir = tmp_path / "extraction_output"
    output_dir.mkdir()
    return output_dir
