# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/performance
파일: test_ball_detection_perf.py
설명: ball_detection 모듈 성능 테스트
      - 칼만 필터 예측/업데이트 속도
      - BallTracker 프레임 처리 지연
      - BallStateMachine 상태 전이 지연
      - 대량 트랙 메모리 사용량
      - data_extraction 초기화/finalize 지연

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import BoundingBox, Point2D
from shared.dto.tracking_dto import KalmanState

from detection.ball_detection.ball_tracker import (
    BallKalmanFilter,
    BallTracker,
    BallTrackerConfig,
)
from detection.ball_detection.ball_state import (
    BallStateMachine,
    BallStateMachineConfig,
    PlayerPosition,
)


# =============================================================================
# 칼만 필터 성능
# =============================================================================

class TestKalmanFilterPerformance:
    """칼만 필터 연산 성능."""

    def test_initiate_속도(self):
        """initiate 1000회 < 50ms."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)

        start = time.perf_counter()
        for _ in range(1000):
            kf.initiate(meas)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 50.0, f"initiate 1000회: {elapsed_ms:.1f}ms > 50ms"

    def test_predict_속도(self):
        """predict 1000회 < 50ms."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas)

        start = time.perf_counter()
        for _ in range(1000):
            state = kf.predict(state)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 50.0, f"predict 1000회: {elapsed_ms:.1f}ms > 50ms"

    def test_update_속도(self):
        """update 1000회 < 100ms."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas)

        start = time.perf_counter()
        for i in range(1000):
            predicted = kf.predict(state)
            meas_new = np.array(
                [100.0 + i * 0.1, 200.0, 40.0, 40.0], dtype=np.float64,
            )
            state = kf.update(predicted, meas_new)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 100.0, f"update 1000회: {elapsed_ms:.1f}ms > 100ms"


# =============================================================================
# BallTracker 성능
# =============================================================================

class TestBallTrackerPerformance:
    """BallTracker 처리 성능."""

    def _make_detection(self, x: float, y: float, conf: float = 0.9) -> BallDetection:
        return BallDetection(
            position=Point2D(x=x, y=y),
            confidence=conf,
            bbox=BoundingBox(
                x=x - 20, y=y - 20,
                width=40, height=40,
            ),
            radius_pixels=20.0,
        )

    def test_단일_트랙_100프레임_지연(self):
        """단일 트랙 100프레임 처리 < 100ms."""
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        start = time.perf_counter()
        for i in range(100):
            det = self._make_detection(320.0 + i * 2.0, 240.0)
            tracker.update([det], frame_index=i)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 100.0, f"100프레임: {elapsed_ms:.1f}ms > 100ms"

    def test_다수_감지_20프레임_지연(self):
        """5개 동시 감지 × 20프레임 < 200ms."""
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        start = time.perf_counter()
        for i in range(20):
            dets = [
                self._make_detection(100.0 + i * 2, 100.0),
                self._make_detection(300.0 + i * 2, 200.0),
                self._make_detection(500.0 + i * 2, 300.0),
                self._make_detection(700.0 + i * 2, 400.0),
                self._make_detection(900.0 + i * 2, 500.0),
            ]
            tracker.update(dets, frame_index=i)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 200.0, f"20프레임×5감지: {elapsed_ms:.1f}ms > 200ms"

    def test_IoU_계산_10만회(self):
        """IoU 계산 100,000회 < 500ms."""
        start = time.perf_counter()
        for _ in range(100_000):
            BallTracker._compute_iou(
                100, 100, 40, 40,
                120, 100, 40, 40,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 500.0, f"IoU 100K회: {elapsed_ms:.1f}ms > 500ms"


# =============================================================================
# BallStateMachine 성능
# =============================================================================

class TestBallStateMachinePerformance:
    """BallStateMachine 처리 성능."""

    def test_상태_전이_1000프레임(self):
        """1000프레임 연속 update < 100ms."""
        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        player = PlayerPosition(
            player_id=1,
            position=Point2D(x=322.0, y=242.0),
            bbox_height=200.0,
        )

        start = time.perf_counter()
        for i in range(1000):
            det = BallDetection(
                position=Point2D(x=320.0 + i * 0.5, y=240.0),
                confidence=0.9,
            )
            fsm.update(det, players=[player])
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 100.0, f"1000프레임: {elapsed_ms:.1f}ms > 100ms"

    def test_단일뷰_상태판정_10000회(self):
        """단일뷰 상태 판정 10,000회 < 200ms."""
        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        det = BallDetection(
            position=Point2D(x=320.0, y=240.0),
            confidence=0.9,
        )

        start = time.perf_counter()
        for _ in range(10_000):
            fsm.update(det)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 200.0, f"단일뷰 10K회: {elapsed_ms:.1f}ms > 200ms"


# =============================================================================
# 메모리 안정성 (deque maxlen)
# =============================================================================

class TestMemoryStability:
    """장시간 운용 메모리 안정성."""

    def test_위치_이력_maxlen_제한(self):
        """BallStateMachine 위치 이력이 무한 성장하지 않음."""
        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        for i in range(500):
            det = BallDetection(
                position=Point2D(x=float(i), y=float(i)),
                confidence=0.9,
            )
            fsm.update(det)

        # deque maxlen에 의해 제한됨
        assert len(fsm._position_history) <= 10  # _VELOCITY_SMOOTHING_WINDOW=5
        assert len(fsm._state_history) <= 90  # _STATE_HISTORY_MAX=90

    def test_트랙_궤적_maxlen_제한(self):
        """BallTracker 궤적 이력이 무한 성장하지 않음."""
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig(trajectory_length=50))

        for i in range(200):
            det = BallDetection(
                position=Point2D(x=320.0 + i, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(
                    x=300.0 + i, y=220.0,
                    width=40.0, height=40.0,
                ),
            )
            tracker.update([det], frame_index=i)

        for track in tracker._tracks:
            assert len(track.trajectory) <= 50
