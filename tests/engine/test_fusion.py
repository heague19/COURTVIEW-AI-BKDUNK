# -*- coding: utf-8 -*-
"""engine/pipeline/fusion/ 단위 테스트."""

from __future__ import annotations

import numpy as np
import pytest

from engine.pipeline.fusion.detection_fusion import (
    DetectionFusion,
    SceneFusionResult,
)
from engine.pipeline.fusion.pose_fusion import (
    CameraPoseData,
    FusedPose3D,
    PoseFusion,
    PoseFusionResult,
)
from engine.pipeline.fusion.tracking_fusion import (
    GlobalTrack,
    TrackingFusion,
    TrackingFusionResult,
)
from shared.constants.pose_constants import NUM_KEYPOINTS_COCO


# =============================================================================
# DetectionFusion 테스트
# =============================================================================
class TestDetectionFusion:
    """DetectionFusion 오케스트레이터."""

    def test_initial_state(self) -> None:
        df = DetectionFusion()
        assert df.total_fusions == 0
        assert df.avg_processing_time_ms == 0.0

    def test_fuse_no_detectors(self) -> None:
        """감지기 미주입 → 전부 None."""
        df = DetectionFusion()
        result = df.fuse({}, frame_index=5, timestamp=0.1)
        assert isinstance(result, SceneFusionResult)
        assert result.frame_index == 5
        assert result.timestamp == 0.1
        assert result.ball_result is None
        assert result.player_result is None
        assert result.court_result is None
        assert result.hoop_result is None
        assert result.total_fused_objects == 0
        assert result.processing_time_ms >= 0.0

    def test_fuse_increments_counter(self) -> None:
        df = DetectionFusion()
        df.fuse({})
        df.fuse({})
        assert df.total_fusions == 2

    def test_history_limit(self) -> None:
        df = DetectionFusion()
        for i in range(250):
            df.fuse({}, frame_index=i)
        assert df.total_fusions == 250
        assert len(df._history) <= 200

    def test_avg_processing_time(self) -> None:
        df = DetectionFusion()
        df.fuse({})
        df.fuse({})
        assert df.avg_processing_time_ms >= 0.0

    def test_reset(self) -> None:
        df = DetectionFusion()
        df.fuse({})
        df.fuse({})
        df.reset()
        assert df.total_fusions == 0
        assert df.avg_processing_time_ms == 0.0

    def test_repr(self) -> None:
        df = DetectionFusion()
        r = repr(df)
        assert "DetectionFusion" in r
        assert "fusions=0" in r

    def test_set_detectors_none(self) -> None:
        """None 감지기 주입 시 기존값 유지."""
        df = DetectionFusion()
        df.set_detectors()  # 전부 None
        assert df._ball_detector is None

    def test_scene_fusion_result_slots(self) -> None:
        result = SceneFusionResult()
        assert not hasattr(result, "__dict__")

    def test_detector_times_populated(self) -> None:
        """감지기 미주입 시 detector_times 빈 dict."""
        df = DetectionFusion()
        result = df.fuse({})
        assert isinstance(result.detector_times_ms, dict)
        assert len(result.detector_times_ms) == 0


# =============================================================================
# PoseFusion 테스트
# =============================================================================
class TestPoseFusion:
    """PoseFusion 오케스트레이터."""

    def test_initial_state(self) -> None:
        pf = PoseFusion()
        assert pf.total_fusions == 0

    def test_fuse_empty(self) -> None:
        pf = PoseFusion()
        result = pf.fuse([], frame_index=10)
        assert isinstance(result, PoseFusionResult)
        assert result.frame_index == 10
        assert result.num_persons == 0
        assert len(result.poses_3d) == 0

    def test_fuse_single_view_skipped(self) -> None:
        """1뷰만 → min_views=2 미달 → 결과 없음."""
        pf = PoseFusion(min_views=2)
        pose = CameraPoseData(
            camera_id="cam0",
            person_id=1,
            keypoints_2d=np.ones((NUM_KEYPOINTS_COCO, 2), dtype=np.float32),
            keypoint_scores=np.ones(NUM_KEYPOINTS_COCO, dtype=np.float32),
        )
        result = pf.fuse([pose])
        assert result.num_persons == 0

    def test_fuse_two_views_pseudo_3d(self) -> None:
        """2뷰, 삼각측량기 미주입 → pseudo-3D (z=0)."""
        pf = PoseFusion(min_views=2)
        pose1 = CameraPoseData(
            camera_id="cam0",
            person_id=1,
            keypoints_2d=np.full((NUM_KEYPOINTS_COCO, 2), 100.0, dtype=np.float32),
            keypoint_scores=np.ones(NUM_KEYPOINTS_COCO, dtype=np.float32),
        )
        pose2 = CameraPoseData(
            camera_id="cam1",
            person_id=1,
            keypoints_2d=np.full((NUM_KEYPOINTS_COCO, 2), 200.0, dtype=np.float32),
            keypoint_scores=np.ones(NUM_KEYPOINTS_COCO, dtype=np.float32),
        )
        result = pf.fuse([pose1, pose2])
        assert result.num_persons == 1
        fused = result.poses_3d[0]
        assert fused.person_id == 1
        assert fused.total_views == 2
        # pseudo-3D: (100+200)/2 = 150
        assert np.allclose(fused.keypoints_3d[0, :2], [150.0, 150.0], atol=1.0)
        assert fused.keypoints_3d[0, 2] == 0.0  # z=0

    def test_fuse_low_confidence_filtered(self) -> None:
        """낮은 신뢰도 키포인트 필터링."""
        pf = PoseFusion(min_views=2, min_confidence=0.5)
        pose1 = CameraPoseData(
            camera_id="cam0", person_id=1,
            keypoints_2d=np.ones((NUM_KEYPOINTS_COCO, 2), dtype=np.float32),
            keypoint_scores=np.full(NUM_KEYPOINTS_COCO, 0.1, dtype=np.float32),
        )
        pose2 = CameraPoseData(
            camera_id="cam1", person_id=1,
            keypoints_2d=np.ones((NUM_KEYPOINTS_COCO, 2), dtype=np.float32),
            keypoint_scores=np.full(NUM_KEYPOINTS_COCO, 0.1, dtype=np.float32),
        )
        result = pf.fuse([pose1, pose2])
        assert result.num_persons == 1
        # 전부 0.1 < 0.5 → 유효 관측 0 → views_per_kp 전부 0
        fused = result.poses_3d[0]
        assert fused.num_views_per_keypoint[0] == 0

    def test_fuse_multiple_persons(self) -> None:
        """2명 각 2뷰 → 2명 3D 복원."""
        pf = PoseFusion(min_views=2)
        poses = []
        for cam in ("cam0", "cam1"):
            for pid in (1, 2):
                poses.append(CameraPoseData(
                    camera_id=cam, person_id=pid,
                    keypoints_2d=np.full((NUM_KEYPOINTS_COCO, 2), pid * 50.0, dtype=np.float32),
                    keypoint_scores=np.ones(NUM_KEYPOINTS_COCO, dtype=np.float32),
                ))
        result = pf.fuse(poses)
        assert result.num_persons == 2

    def test_negative_person_id_skipped(self) -> None:
        """person_id < 0 → 무시."""
        pf = PoseFusion()
        pose = CameraPoseData(camera_id="cam0", person_id=-1)
        result = pf.fuse([pose])
        assert result.num_persons == 0

    def test_counter_increments(self) -> None:
        pf = PoseFusion()
        pf.fuse([])
        pf.fuse([])
        pf.fuse([])
        assert pf.total_fusions == 3

    def test_reset(self) -> None:
        pf = PoseFusion()
        pf.fuse([])
        pf.reset()
        assert pf.total_fusions == 0

    def test_repr(self) -> None:
        pf = PoseFusion()
        r = repr(pf)
        assert "PoseFusion" in r
        assert "min_views=" in r

    def test_camera_pose_data_slots(self) -> None:
        cpd = CameraPoseData()
        assert not hasattr(cpd, "__dict__")

    def test_fused_pose_3d_slots(self) -> None:
        fp = FusedPose3D()
        assert not hasattr(fp, "__dict__")


# =============================================================================
# TrackingFusion 테스트
# =============================================================================
class TestTrackingFusion:
    """TrackingFusion 오케스트레이터."""

    def _make_player(
        self, x1: float, y1: float, x2: float, y2: float, **kwargs: object
    ) -> dict[str, float]:
        d: dict[str, object] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        d.update(kwargs)
        return d  # type: ignore[return-value]

    def test_initial_state(self) -> None:
        tf = TrackingFusion()
        assert tf.num_active_tracks == 0
        assert tf.total_fusions == 0

    def test_new_track_created(self) -> None:
        tf = TrackingFusion()
        result = tf.fuse([self._make_player(10, 20, 50, 100)])
        assert result.new_tracks == 1
        assert len(result.active_tracks) == 1
        assert result.active_tracks[0].global_id == 1

    def test_track_matched_same_position(self) -> None:
        """동일 위치 → 기존 트랙 매칭, 신규 0."""
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100)])
        result = tf.fuse([self._make_player(12, 22, 52, 102)])
        assert result.new_tracks == 0
        assert len(result.active_tracks) == 1

    def test_track_not_matched_distant(self) -> None:
        """먼 위치 → 매칭 실패, 신규 트랙."""
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100)])
        result = tf.fuse([self._make_player(500, 500, 600, 600)])
        assert result.new_tracks == 1
        assert len(result.active_tracks) == 2

    def test_track_lost_after_max_age(self) -> None:
        """max_age 초과 → 트랙 삭제."""
        tf = TrackingFusion(max_age=3)
        tf.fuse([self._make_player(10, 20, 50, 100)])
        # 4프레임 동안 미관측
        for _ in range(4):
            tf.fuse([])
        result = tf.fuse([])
        assert tf.num_active_tracks == 0
        assert result.lost_tracks >= 0  # 삭제 시점에 따라

    def test_multiple_players(self) -> None:
        """3명 동시 → 3개 트랙."""
        tf = TrackingFusion()
        players = [
            self._make_player(10, 10, 50, 50),
            self._make_player(100, 100, 150, 150),
            self._make_player(200, 200, 250, 250),
        ]
        result = tf.fuse(players)
        assert result.new_tracks == 3
        assert len(result.active_tracks) == 3

    def test_team_id_updated(self) -> None:
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100, team_id="home")])
        result = tf.fuse([self._make_player(12, 22, 52, 102, team_id="away")])
        assert result.active_tracks[0].team_id == "away"

    def test_jersey_number_updated(self) -> None:
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100, jersey_number=23)])
        assert tf._active_globals[1].jersey_number == 23

    def test_position_3d_updated(self) -> None:
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100, x3d=1.0, y3d=2.0, z3d=0.5)])
        assert tf._active_globals[1].last_position_3d == (1.0, 2.0, 0.5)

    def test_iou_computation(self) -> None:
        """IoU 정확도 검증."""
        # 완전 겹침
        assert TrackingFusion._compute_iou(
            (0, 0, 10, 10), (0, 0, 10, 10)
        ) == pytest.approx(1.0)

        # 겹침 없음
        assert TrackingFusion._compute_iou(
            (0, 0, 10, 10), (20, 20, 30, 30)
        ) == pytest.approx(0.0)

        # 50% 겹침 (가로)
        iou = TrackingFusion._compute_iou(
            (0, 0, 10, 10), (5, 0, 15, 10)
        )
        # inter=50, union=200-50=150 → 50/150=0.333
        assert iou == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_iou_zero_area(self) -> None:
        """면적 0 bbox → IoU 0."""
        assert TrackingFusion._compute_iou(
            (5, 5, 5, 5), (5, 5, 5, 5)
        ) == pytest.approx(0.0)

    def test_global_id_auto_increment(self) -> None:
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 10, 50, 50)])
        tf.fuse([self._make_player(500, 500, 600, 600)])
        ids = sorted(tf._active_globals.keys())
        assert ids == [1, 2]

    def test_reset(self) -> None:
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 10, 50, 50)])
        tf.reset()
        assert tf.num_active_tracks == 0
        assert tf.total_fusions == 0
        assert tf._next_global_id == 1

    def test_history_limit(self) -> None:
        tf = TrackingFusion()
        for i in range(250):
            tf.fuse([], frame_index=i)
        assert len(tf._history) <= 200

    def test_repr(self) -> None:
        tf = TrackingFusion()
        r = repr(tf)
        assert "TrackingFusion" in r
        assert "active=0" in r

    def test_global_track_slots(self) -> None:
        gt = GlobalTrack()
        assert not hasattr(gt, "__dict__")

    def test_total_frames_incremented(self) -> None:
        """매칭 시 total_frames 증가."""
        tf = TrackingFusion()
        tf.fuse([self._make_player(10, 20, 50, 100)])
        tf.fuse([self._make_player(12, 22, 52, 102)])
        tf.fuse([self._make_player(14, 24, 54, 104)])
        assert tf._active_globals[1].total_frames == 3


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_detection_fusion_all(self) -> None:
        import engine.pipeline.fusion.detection_fusion as mod
        assert len(mod.__all__) == 2
        assert mod.__version__ == "1.0.0"

    def test_pose_fusion_all(self) -> None:
        import engine.pipeline.fusion.pose_fusion as mod
        assert len(mod.__all__) == 4
        assert mod.__version__ == "1.0.0"

    def test_tracking_fusion_all(self) -> None:
        import engine.pipeline.fusion.tracking_fusion as mod
        assert len(mod.__all__) == 3
        assert mod.__version__ == "1.0.0"
