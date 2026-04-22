# -*- coding: utf-8 -*-
"""
tests/detection/player_detection/unit/test_multiview_tracker.py
MultiViewPlayerTracker 단위 테스트.

대상:
  - CalibrationLoader: 호모그래피 로드 + cam_id 매핑 (picker 규약)
  - project_bbox_to_court: 발 위치 투영
  - cluster_court_observations: DBSCAN 동작
  - KalmanTrack: 예측/업데이트 수식
  - MultiViewPlayerTracker: update 흐름, permanent_id_map, reset, game state
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from detection.player_detection.multiview_tracker import (
    CalibrationLoader,
    CameraDetection,
    CourtObservation,
    GameState,
    KalmanTrack,
    MultiViewPlayerTracker,
    cluster_centroids,
    cluster_court_observations,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def calib_dir(tmp_path: Path) -> str:
    """단위 테스트용 가짜 캘리브 디렉토리 (항등 호모그래피)."""
    # cam_0 = 항등 매트릭스 (픽셀 = 미터 그대로)
    # cam_1 = y축 반전 + 스케일 (픽셀의 (100, 200) → 미터의 (10, 20))
    for i, H in enumerate([
        np.eye(3).tolist(),  # cam_0
        [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]],  # cam_1: 1/10 스케일
    ]):
        H_arr = np.array(H, dtype=np.float64)
        data = {
            "homography": H_arr.tolist(),
            "inverse_homography": np.linalg.inv(H_arr).tolist(),
        }
        (tmp_path / f"cam_{i}.json").write_text(json.dumps(data))
    return str(tmp_path)


@pytest.fixture
def det_factory():
    """CameraDetection 팩토리.

    기본 bbox (10, 10, 14, 14) → 발 위치 (12, 14) → 항등 호모그래피에서
    코트 좌표 (12, 14) = 28x15 코트 내부.
    """
    def make(
        cam_id: int = 1,
        bbox=(10, 10, 14, 14),
        jersey_number: int | None = None,
        team: str | None = None,
        jersey_conf: float = 0.0,
        team_conf: float = 0.0,
    ) -> CameraDetection:
        return CameraDetection(
            cam_id=cam_id,
            bbox=bbox,
            jersey_number=jersey_number,
            jersey_conf=jersey_conf,
            team=team,
            team_conf=team_conf,
        )
    return make


# =============================================================================
# CalibrationLoader
# =============================================================================

class TestCalibrationLoader:
    def test_loads_homographies(self, calib_dir):
        loader = CalibrationLoader(calib_dir)
        # picker 규약: cam_0.json → cam_id 1
        assert 1 in loader.homographies
        assert 2 in loader.homographies
        assert 3 not in loader.homographies  # cam_2.json 없음

    def test_picker_cam_id_offset(self, calib_dir):
        """cam_0.json이 영상 cam1에 매핑됨 (picker 규약)."""
        loader = CalibrationLoader(calib_dir)
        H1 = loader.homographies[1]
        assert np.allclose(H1, np.eye(3))  # cam_0.json = 항등

    def test_project_bbox_identity(self, calib_dir):
        """항등 호모그래피: 발 위치 그대로."""
        loader = CalibrationLoader(calib_dir)
        # bbox (100, 100, 200, 300) → 발 위치 (150, 300)
        result = loader.project_bbox_to_court(1, (100, 100, 200, 300))
        assert result is not None
        x, y = result
        assert x == pytest.approx(150.0)
        assert y == pytest.approx(300.0)

    def test_project_bbox_missing_cam(self, calib_dir):
        loader = CalibrationLoader(calib_dir)
        assert loader.project_bbox_to_court(99, (0, 0, 10, 10)) is None

    def test_project_bbox_scaling(self, calib_dir):
        """cam_1.json = 1/10 스케일."""
        loader = CalibrationLoader(calib_dir)
        result = loader.project_bbox_to_court(2, (100, 100, 200, 300))
        assert result is not None
        x, y = result
        assert x == pytest.approx(15.0)  # 150 * 0.1
        assert y == pytest.approx(30.0)


# =============================================================================
# DBSCAN 클러스터링
# =============================================================================

class TestClustering:
    def test_single_cluster_close_points(self, det_factory):
        """2개 카메라의 같은 위치 → 1 클러스터."""
        obs = [
            CourtObservation(cam_id=1, det_idx=0, court_x=10.0, court_y=5.0,
                             detection=det_factory()),
            CourtObservation(cam_id=2, det_idx=0, court_x=10.2, court_y=5.1,
                             detection=det_factory()),
        ]
        cluster_court_observations(obs, eps_m=1.0)
        assert obs[0].cluster_id == obs[1].cluster_id
        assert obs[0].cluster_id >= 0

    def test_separate_clusters_far_points(self, det_factory):
        """떨어진 관측은 별도 클러스터."""
        obs = [
            CourtObservation(cam_id=1, det_idx=0, court_x=5.0, court_y=5.0,
                             detection=det_factory()),
            CourtObservation(cam_id=2, det_idx=0, court_x=20.0, court_y=10.0,
                             detection=det_factory()),
        ]
        cluster_court_observations(obs, eps_m=1.0)
        assert obs[0].cluster_id != obs[1].cluster_id

    def test_empty_input(self):
        cluster_court_observations([], eps_m=1.0)  # 예외 안 터지면 OK

    def test_centroids_calculation(self, det_factory):
        obs = [
            CourtObservation(cam_id=1, det_idx=0, court_x=10.0, court_y=5.0,
                             detection=det_factory(), cluster_id=0),
            CourtObservation(cam_id=2, det_idx=0, court_x=11.0, court_y=6.0,
                             detection=det_factory(), cluster_id=0),
        ]
        centroids = cluster_centroids(obs)
        assert 0 in centroids
        cx, cy, members = centroids[0]
        assert cx == pytest.approx(10.5)
        assert cy == pytest.approx(5.5)
        assert len(members) == 2


# =============================================================================
# Kalman
# =============================================================================

class TestKalmanTrack:
    def test_predict_static(self):
        kf = KalmanTrack(init_x=10.0, init_y=5.0)
        px, py = kf.predict()
        # 초기 속도 0 → 위치 그대로
        assert px == pytest.approx(10.0)
        assert py == pytest.approx(5.0)

    def test_update_converges(self):
        """관측 반복 시 상태가 관측값에 수렴."""
        kf = KalmanTrack(init_x=0.0, init_y=0.0)
        for _ in range(20):
            kf.predict()
            kf.update(10.0, 5.0)
        px, py = kf.position
        assert px == pytest.approx(10.0, abs=0.5)
        assert py == pytest.approx(5.0, abs=0.5)

    def test_velocity_estimate(self):
        """연속 이동 → 속도 추정값이 음수 아닌 방향."""
        kf = KalmanTrack(init_x=0.0, init_y=0.0, dt=1.0)
        # 매 1초마다 +1m 이동
        for i in range(1, 10):
            kf.predict()
            kf.update(float(i), 0.0)
        vx, _ = kf.velocity
        assert vx > 0  # 양의 속도


# =============================================================================
# MultiViewPlayerTracker
# =============================================================================

class TestMultiViewPlayerTracker:
    def test_empty_update(self, calib_dir):
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir)
        result = tracker.update(0, {})
        assert result == {}
        assert len(tracker.tracks) == 0

    def test_single_camera_detection_creates_track(self, calib_dir, det_factory):
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir, cluster_eps_m=1.0)
        dets = {1: [det_factory(cam_id=1)]}  # 기본 bbox → 코트 (12, 14)
        result = tracker.update(0, dets)
        assert len(tracker.tracks) == 1
        assert (1, 0) in result

    def test_multi_camera_same_player_one_track(self, calib_dir, det_factory):
        """두 카메라에서 같은 코트 위치 → 1 트랙."""
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir, cluster_eps_m=1.5)
        # cam1 (항등): bbox 발 (12, 14) → 코트 (12, 14)
        # cam2 (스케일 0.1): bbox 발 (120, 140) → 코트 (12, 14)
        dets = {
            1: [det_factory(cam_id=1, bbox=(10, 10, 14, 14))],
            2: [det_factory(cam_id=2, bbox=(100, 100, 140, 140))],
        }
        tracker.update(0, dets)
        # 두 관측이 같은 코트 위치 → 1 트랙
        assert len(tracker.tracks) == 1

    def test_permanent_id_reuse_on_rejoin(self, calib_dir, det_factory):
        """jersey+team 확정된 트랙이 제거돼도 재등장 시 같은 ID 재사용."""
        tracker = MultiViewPlayerTracker(
            calib_dir=calib_dir, cluster_eps_m=1.0,
            max_miss_frames=2,
        )
        det = det_factory(cam_id=1, jersey_number=23, team="team_a",
                          jersey_conf=0.9, team_conf=0.9)
        tracker.update(0, {1: [det]})
        gid_first = list(tracker.tracks.keys())[0]
        assert ("team_a", 23) in tracker.permanent_id_map
        # 3프레임 미검출 → 트랙 제거
        for f in range(1, 5):
            tracker.update(f, {})
        assert len(tracker.tracks) == 0
        # 재등장 → 같은 global_id
        tracker.update(5, {1: [det]})
        gid_again = list(tracker.tracks.keys())[0]
        assert gid_again == gid_first

    def test_reset_clears_all(self, calib_dir, det_factory):
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir)
        tracker.update(0, {1: [det_factory(jersey_number=23, team="team_a",
                                            jersey_conf=0.9, team_conf=0.9)]})
        assert len(tracker.tracks) > 0
        tracker.reset()
        assert len(tracker.tracks) == 0
        assert len(tracker.permanent_id_map) == 0
        assert tracker.next_id == 1
        assert tracker.game_state == GameState.ACTIVE

    def test_game_state_paused_to_active_triggers_resume_window(self, calib_dir):
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir, dt=1.0)
        tracker.set_game_state(GameState.PAUSED)
        assert tracker.game_state == GameState.PAUSED
        tracker.set_game_state(GameState.ACTIVE)
        # PAUSED → ACTIVE는 RESUME_WINDOW로 전환
        assert tracker.game_state == GameState.RESUME_WINDOW
        assert tracker.resume_frames_left == 10  # 10초 / dt=1 = 10

    def test_paused_preserves_confirmed_tracks(self, calib_dir, det_factory):
        """PAUSED 상태에서 확정 트랙은 max_miss 초과해도 유지."""
        tracker = MultiViewPlayerTracker(
            calib_dir=calib_dir, max_miss_frames=2,
        )
        det = det_factory(jersey_number=23, team="team_a",
                          jersey_conf=0.9, team_conf=0.9)
        tracker.update(0, {1: [det]})
        gid = list(tracker.tracks.keys())[0]
        assert tracker.tracks[gid].confirmed
        # PAUSED 상태
        tracker.set_game_state(GameState.PAUSED)
        for f in range(1, 10):  # 많이 미검출
            tracker.update(f, {})
        # 확정 트랙은 유지
        assert gid in tracker.tracks

    def test_get_camera_detections_returns_latest(self, calib_dir, det_factory):
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir)
        det = det_factory(cam_id=1, jersey_number=7, team="team_b",
                          jersey_conf=0.9, team_conf=0.9)
        tracker.update(0, {1: [det]})
        gid = list(tracker.tracks.keys())[0]
        cam_dets = tracker.get_camera_detections(gid)
        assert 1 in cam_dets
        assert cam_dets[1].jersey_number == 7

    def test_off_court_projection_filtered(self, calib_dir, det_factory):
        """코트 ±2m 밖으로 투영되는 감지는 제외."""
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir)
        # cam1 항등: bbox 발 (500, 500) → 코트 (500, 500) = 코트 x>30 완전 밖
        dets = {1: [det_factory(cam_id=1, bbox=(400, 400, 600, 500))]}
        tracker.update(0, dets)
        assert len(tracker.tracks) == 0  # 필터됨

    def test_track_id_assigned_to_observations(self, calib_dir, det_factory):
        """update 반환값: (cam_id, det_idx) → global_id."""
        tracker = MultiViewPlayerTracker(calib_dir=calib_dir, cluster_eps_m=1.0)
        dets = {
            1: [det_factory(cam_id=1, bbox=(10, 10, 14, 14))],
            2: [det_factory(cam_id=2, bbox=(100, 100, 140, 140))],
        }
        result = tracker.update(0, dets)
        # 두 카메라 관측이 같은 코트 위치 → 같은 global_id
        assert result.get((1, 0)) == result.get((2, 0))
        assert result.get((1, 0)) is not None
