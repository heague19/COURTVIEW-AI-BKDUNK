# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection
파일: conftest.py
설명: court_detection 모듈 테스트 공통 fixture
      - YOLO 모델 모킹
      - 코트 라인 프레임 생성기
      - CourtDetector / CourtMapper / ZoneClassifier 초기화 fixture

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from shared.constants.court_constants import CourtStandard, CourtZone


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
def court_lines_frame() -> NDArray[np.uint8]:
    """
    코트 라인이 있는 테스트 프레임.

    나무 바닥(갈색) + 흰색 수평/수직 라인이 있는 640x480 프레임.
    """
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 나무 바닥 색상 (BGR: 갈색)
    frame[:] = (60, 100, 160)  # 갈색 톤

    # 흰색 라인 (수평)
    cv2.line(frame, (50, 100), (590, 100), (255, 255, 255), 3)
    cv2.line(frame, (50, 380), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (200, 240), (440, 240), (255, 255, 255), 3)

    # 흰색 라인 (수직)
    cv2.line(frame, (50, 100), (50, 380), (255, 255, 255), 3)
    cv2.line(frame, (590, 100), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (320, 100), (320, 380), (255, 255, 255), 3)

    return frame


@pytest.fixture()
def sample_keypoints() -> list[tuple[float, float]]:
    """테스트용 키포인트 목록 (6개)."""
    return [
        (50.0, 100.0),
        (590.0, 100.0),
        (50.0, 380.0),
        (590.0, 380.0),
        (320.0, 100.0),
        (320.0, 380.0),
    ]


@pytest.fixture()
def sample_court_points() -> list[tuple[float, float]]:
    """테스트용 코트 좌표 목록 (6개, FIBA 규격)."""
    return [
        (0.0, 15.0),   # 좌상단
        (28.0, 15.0),  # 우상단
        (0.0, 0.0),    # 좌하단
        (28.0, 0.0),   # 우하단
        (14.0, 15.0),  # 센터 상
        (14.0, 0.0),   # 센터 하
    ]


@pytest.fixture()
def sample_homography() -> NDArray[np.float64]:
    """테스트용 호모그래피 행렬 (6점 기반)."""
    src = np.array([
        [50.0, 100.0],
        [590.0, 100.0],
        [50.0, 380.0],
        [590.0, 380.0],
    ], dtype=np.float64)
    dst = np.array([
        [0.0, 15.0],
        [28.0, 15.0],
        [0.0, 0.0],
        [28.0, 0.0],
    ], dtype=np.float64)
    h, _ = cv2.findHomography(src, dst)
    return h


# =============================================================================
# YOLO 모킹 fixture
# =============================================================================

@pytest.fixture()
def mock_yolo_model():
    """YOLO 모델 모킹 (코트 라인 감지)."""
    mock_model = MagicMock()

    # 빈 감지 결과
    mock_result = MagicMock()
    mock_boxes = MagicMock()
    mock_boxes.xyxy = np.array([
        [50.0, 98.0, 590.0, 102.0],   # 수평 라인 1
        [50.0, 378.0, 590.0, 382.0],  # 수평 라인 2
        [48.0, 100.0, 52.0, 380.0],   # 수직 라인 1
    ])
    mock_boxes.conf = np.array([0.85, 0.80, 0.75])
    mock_boxes.cls = np.array([0, 0, 0])  # class 0 = court_line
    mock_boxes.__len__ = lambda self: 3

    # xyxy, conf, cls를 인덱싱 가능하게
    mock_boxes.xyxy.__getitem__ = lambda self, i: MagicMock(
        cpu=lambda: MagicMock(numpy=lambda: mock_boxes.xyxy[i]),
    )
    mock_boxes.conf.__getitem__ = lambda self, i: MagicMock(
        cpu=lambda: MagicMock(numpy=lambda: mock_boxes.conf[i]),
    )
    mock_boxes.cls.__getitem__ = lambda self, i: MagicMock(
        cpu=lambda: MagicMock(numpy=lambda: mock_boxes.cls[i]),
    )

    mock_result.boxes = mock_boxes
    mock_model.predict.return_value = [mock_result]

    return mock_model


@pytest.fixture()
def temp_output_dir():
    """임시 출력 디렉토리."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
