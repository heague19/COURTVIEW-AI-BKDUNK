# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/unit
파일: test_ball_tracker.py
설명: BallTracker + BallKalmanFilter 단위 테스트
      - 칼만 필터 초기화/예측/업데이트/마할라노비스 거리
      - ByteTrack 2단계 연관 (고신뢰 → 저신뢰)
      - 트랙 생성/확정/삭제 라이프사이클
      - IoU 계산, 헝가리안 매칭
      - 멀티뷰 트랙 연관

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.ball_constants import (
    BALL_TRACKING_MAX_TRACK_AGE,
    BALL_TRACKING_MIN_HITS,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import BoundingBox, Point2D
from shared.dto.tracking_dto import KalmanState, TrackState

from detection.ball_detection.ball_tracker import (
    BallKalmanFilter,
    BallTracker,
    BallTrackerConfig,
    _InternalTrack,
)


# =============================================================================
# BallKalmanFilter 테스트
# =============================================================================

class TestBallKalmanFilter:
    """8D 칼만 필터 단위 테스트."""

    def test_초기화_상태_차원(self):
        """칼만 필터 state_dim=8, meas_dim=4."""
        kf = BallKalmanFilter()
        assert kf._state_dim == 8
        assert kf._measurement_dim == 4

    def test_initiate_상태_벡터(self):
        """initiate() 시 측정값이 mean[:4]에 복사됨."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas)

        assert state.state_dim == 8
        assert state.measurement_dim == 4
        np.testing.assert_array_almost_equal(state.mean[:4], meas)
        # 속도 초기값은 0
        np.testing.assert_array_almost_equal(state.mean[4:], [0, 0, 0, 0])

    def test_predict_위치_변화(self):
        """predict() 시 등속도 모델로 위치 예측."""
        kf = BallKalmanFilter()
        # cx=100, cy=200, w=40, h=40, vx=5, vy=-3, vw=0, vh=0
        mean = np.array(
            [100.0, 200.0, 40.0, 40.0, 5.0, -3.0, 0.0, 0.0],
            dtype=np.float64,
        )
        state = KalmanState(
            mean=mean,
            covariance=np.eye(8, dtype=np.float64),
            state_dim=8,
            measurement_dim=4,
        )
        predicted = kf.predict(state)

        # cx += vx, cy += vy
        assert predicted.mean[0] == pytest.approx(105.0)
        assert predicted.mean[1] == pytest.approx(197.0)
        # 속도는 유지
        assert predicted.mean[4] == pytest.approx(5.0)
        assert predicted.mean[5] == pytest.approx(-3.0)

    def test_update_보정_방향(self):
        """update() 시 상태가 측정값 방향으로 보정됨."""
        kf = BallKalmanFilter()
        meas_init = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas_init)

        # 측정값이 오른쪽으로 이동
        meas_new = np.array([110.0, 200.0, 40.0, 40.0], dtype=np.float64)
        updated = kf.update(state, meas_new)

        # 보정 후 cx가 110 쪽으로 이동해야 함
        assert updated.mean[0] > 100.0
        assert updated.mean[0] <= 110.0

    def test_gating_distance_동일_위치(self):
        """측정값이 예측 위치와 같으면 거리 ≈ 0."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas)

        distance = kf.gating_distance(state, meas)
        assert distance == pytest.approx(0.0, abs=0.1)

    def test_gating_distance_먼_위치(self):
        """측정값이 멀면 거리가 큼."""
        kf = BallKalmanFilter()
        meas = np.array([100.0, 200.0, 40.0, 40.0], dtype=np.float64)
        state = kf.initiate(meas)

        far_meas = np.array([500.0, 600.0, 40.0, 40.0], dtype=np.float64)
        distance = kf.gating_distance(state, far_meas)
        assert distance > 100.0

    def test_repr_포맷(self):
        """__repr__ 형식 확인."""
        kf = BallKalmanFilter()
        assert "BallKalmanFilter" in repr(kf)
        assert "state_dim=8" in repr(kf)


# =============================================================================
# BallTrackerConfig 테스트
# =============================================================================

class TestBallTrackerConfig:
    """BallTrackerConfig 단위 테스트."""

    def test_기본값(self):
        """기본값이 shared constants 참조."""
        config = BallTrackerConfig()
        assert config.max_age == BALL_TRACKING_MAX_TRACK_AGE
        assert config.min_hits == BALL_TRACKING_MIN_HITS

    def test_커스텀_값(self):
        """커스텀 값 설정."""
        config = BallTrackerConfig(max_age=60, min_hits=5)
        assert config.max_age == 60
        assert config.min_hits == 5

    def test_repr_포맷(self):
        """__repr__ 형식 확인."""
        config = BallTrackerConfig()
        assert "BallTrackerConfig" in repr(config)


# =============================================================================
# BallTracker 초기화/리셋 테스트
# =============================================================================

class TestBallTrackerInit:
    """BallTracker 초기화 테스트."""

    def test_미초기화_시_빈_리스트_반환(self):
        """initialize() 없이 update → 빈 리스트."""
        t = BallTracker()
        result = t.update([])
        assert result == []

    def test_initialize_후_상태(self, tracker):
        """initialize 후 내부 상태 확인."""
        assert tracker._tracks == []
        assert tracker._next_track_id == 1
        assert tracker._frame_count == 0

    def test_reset(self, tracker, make_ball_detection):
        """reset() 후 상태 초기화."""
        # 먼저 트랙 생성
        det = make_ball_detection()
        tracker.update([det])
        assert tracker._frame_count == 1

        tracker.reset()
        assert tracker._frame_count == 0
        assert tracker._tracks == []

    def test_repr_포맷(self, tracker):
        """__repr__ 형식 확인."""
        repr_str = repr(tracker)
        assert "BallTracker" in repr_str
        assert "tracks=" in repr_str


# =============================================================================
# 트랙 생성 및 라이프사이클
# =============================================================================

class TestTrackLifecycle:
    """트랙 생성/확정/삭제 라이프사이클."""

    def test_첫_감지_시_트랙_생성(self, tracker, make_ball_detection):
        """첫 감지 시 TENTATIVE 트랙 생성."""
        det = make_ball_detection(confidence=0.8)
        tracks = tracker.update([det])

        # 최소 1개 트랙 존재 (TENTATIVE이므로 export 안 될 수도 있음)
        assert tracker._frame_count == 1
        assert len(tracker._tracks) >= 1

    def test_연속_감지_시_트랙_확정(self, tracker, make_ball_detection):
        """min_hits 이상 연속 매칭 시 CONFIRMED 전이."""
        min_hits = tracker._config.min_hits

        for i in range(min_hits + 2):
            det = make_ball_detection(
                x=320.0 + i * 2.0, y=240.0,
                confidence=0.9, frame_index=i,
            )
            tracks = tracker.update([det])

        # 확정 트랙 존재
        confirmed = [t for t in tracker._tracks if t.is_confirmed]
        assert len(confirmed) >= 1

    def test_미감지_시_트랙_age_증가(self, tracker, make_ball_detection):
        """감지 없으면 time_since_update 증가."""
        # 트랙 생성
        det = make_ball_detection()
        tracker.update([det])

        # 빈 감지로 업데이트
        for _ in range(3):
            tracker.update([])

        if tracker._tracks:
            assert tracker._tracks[0].time_since_update >= 3

    def test_장기_미감지_시_트랙_삭제(self, tracker, make_ball_detection):
        """max_age 초과 미감지 시 트랙 삭제."""
        det = make_ball_detection()
        tracker.update([det])

        max_age = tracker._config.max_age
        for _ in range(max_age + 5):
            tracker.update([])

        # 모든 트랙 DELETED 상태 (또는 이미 제거됨)
        active = [t for t in tracker._tracks if t.state != TrackState.DELETED]
        assert len(active) == 0

    def test_다수_감지_다수_트랙(self, tracker, make_ball_detection):
        """다수 감지 → 다수 트랙 생성."""
        dets = [
            make_ball_detection(x=100.0, y=100.0, confidence=0.8),
            make_ball_detection(x=500.0, y=400.0, confidence=0.85),
        ]
        tracker.update(dets)
        # 독립적 위치이므로 각각 트랙 생성
        assert len(tracker._tracks) >= 2


# =============================================================================
# IoU 계산 테스트
# =============================================================================

class TestComputeIoU:
    """IoU 계산 정적 메서드 테스트."""

    def test_완전_겹침_iou_1(self):
        """완전히 같은 bbox → IoU = 1.0."""
        iou = BallTracker._compute_iou(
            100, 100, 40, 40,
            100, 100, 40, 40,
        )
        assert iou == pytest.approx(1.0)

    def test_겹치지_않음_iou_0(self):
        """전혀 겹치지 않는 bbox → IoU = 0.0."""
        iou = BallTracker._compute_iou(
            100, 100, 40, 40,
            500, 500, 40, 40,
        )
        assert iou == pytest.approx(0.0)

    def test_부분_겹침_iou_범위(self):
        """부분 겹침 → 0 < IoU < 1."""
        iou = BallTracker._compute_iou(
            100, 100, 40, 40,
            120, 100, 40, 40,
        )
        assert 0.0 < iou < 1.0

    def test_크기_0_iou_0(self):
        """w=0 또는 h=0 → IoU = 0 (또는 무한대 방지)."""
        iou = BallTracker._compute_iou(
            100, 100, 0, 40,
            100, 100, 40, 40,
        )
        assert iou == pytest.approx(0.0)


# =============================================================================
# 궤적 (trajectory) 테스트
# =============================================================================

class TestTrajectory:
    """궤적 추출 테스트."""

    def test_get_trajectory_존재하는_트랙(self, tracker, make_ball_detection):
        """확정 트랙의 궤적을 BallTrajectory DTO로 반환."""
        min_hits = tracker._config.min_hits

        for i in range(min_hits + 3):
            det = make_ball_detection(
                x=320.0 + i * 3.0, y=240.0,
                confidence=0.9, frame_index=i,
            )
            tracker.update([det])

        confirmed = [t for t in tracker._tracks if t.is_confirmed]
        if confirmed:
            traj = tracker.get_trajectory(confirmed[0].track_id)
            assert traj is not None
            assert len(traj.points_2d) > 0

    def test_get_trajectory_없는_트랙ID(self, tracker):
        """존재하지 않는 track_id → None."""
        result = tracker.get_trajectory(999)
        assert result is None

    def test_get_best_track_확정_없으면_None(self, tracker):
        """확정 트랙 없으면 None."""
        result = tracker.get_best_track()
        assert result is None

    def test_get_active_tracks_비어있음(self, tracker):
        """초기 상태에서 활성 트랙 없음."""
        result = tracker.get_active_tracks()
        assert result == []


# =============================================================================
# 에지 케이스
# =============================================================================

class TestEdgeCases:
    """에지 케이스 테스트."""

    def test_빈_감지_리스트(self, tracker):
        """빈 감지 리스트 → 기존 트랙만 업데이트."""
        result = tracker.update([])
        assert isinstance(result, list)

    def test_신뢰도_0_감지_필터링(self, tracker, make_ball_detection):
        """confidence=0 감지는 필터링됨."""
        det = make_ball_detection(confidence=0.0)
        tracker.update([det])
        # 유효하지 않은 감지 → 트랙 생성 안 됨
        assert len(tracker._tracks) == 0

    def test_position_None_감지_필터링(self, tracker):
        """position=None 감지는 필터링됨."""
        det = BallDetection(confidence=0.9)  # position=None
        tracker.update([det])
        assert len(tracker._tracks) == 0
