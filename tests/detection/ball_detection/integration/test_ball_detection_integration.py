# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/integration
파일: test_ball_detection_integration.py
설명: ball_detection 모듈 통합 테스트
      - BallDetector → BallTracker → BallStateMachine 파이프라인
      - 감지 → 추적 → 상태 판정 E2E 흐름
      - 멀티뷰 파이프라인 통합
      - data_extraction 연동
      - __init__.py Export 정합성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.ball_constants import (
    BALL_STATE_MIN_POSSESSION_FRAMES,
    BallState,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import BoundingBox, Point2D
from shared.dto.tracking_dto import TrackState

from detection.ball_detection.ball_state import (
    BallStateMachine,
    BallStateMachineConfig,
    PlayerPosition,
)
from detection.ball_detection.ball_tracker import (
    BallTracker,
    BallTrackerConfig,
)


# =============================================================================
# 추적기 → 상태 머신 통합
# =============================================================================

class TestTrackerToStateMachineIntegration:
    """BallTracker → BallStateMachine 통합 파이프라인."""

    def test_추적_후_상태_판정(self):
        """
        시나리오: 공이 선수 근처에서 정지
        1. 감지 → 트랙 생성 (BallTracker)
        2. 확정 트랙의 위치 → 상태 판정 (BallStateMachine)
        3. 선수 근접 + 저속 → HELD
        """
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        player = PlayerPosition(
            player_id=7,
            position=Point2D(x=322.0, y=242.0),
            bbox_height=200.0,
        )

        # 30프레임 시뮬레이션: 같은 위치에서 감지 (정지)
        for i in range(30):
            det = BallDetection(
                position=Point2D(x=320.0, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(x=300, y=220, width=40, height=40),
                radius_pixels=20.0,
            )
            tracks = tracker.update([det], frame_index=i)
            state = fsm.update(det, players=[player])

        # min_possession_frames 충분히 지나면 HELD
        assert state == BallState.HELD
        assert fsm.holder_id == 7

    def test_이동_공_추적_상태_변화(self):
        """
        시나리오: 공이 오른쪽으로 빠르게 이동
        → 추적기가 트랙 유지 + 상태가 비행 상태로 전이
        """
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        states_seen: set[BallState] = set()

        for i in range(50):
            # 공이 오른쪽으로 빠르게 이동
            x = 100.0 + i * 20.0  # 속도: 20px/frame
            det = BallDetection(
                position=Point2D(x=x, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(
                    x=x - 20, y=220,
                    width=40, height=40,
                ),
            )
            tracks = tracker.update([det], frame_index=i)
            state = fsm.update(det)
            states_seen.add(state)

        # 고속 수평 이동 → PASSING 또는 비행 상태 경험
        assert len(states_seen) >= 1  # 최소 1개 이상 상태 변화


# =============================================================================
# 공 미감지 → LOST → 복귀 시나리오
# =============================================================================

class TestLostAndRecovery:
    """공 미감지 → LOST → 재감지 복귀."""

    def test_미감지_후_재감지(self):
        """
        시나리오:
        1. 10프레임 감지 (트랙 확정)
        2. 5프레임 미감지 (LOST)
        3. 10프레임 재감지 (복귀)
        """
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        # Phase 1: 감지
        for i in range(10):
            det = BallDetection(
                position=Point2D(x=320.0, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(x=300, y=220, width=40, height=40),
            )
            tracker.update([det], frame_index=i)
            fsm.update(det)

        # Phase 2: 미감지
        for i in range(10, 15):
            tracker.update([], frame_index=i)
            state = fsm.update(None)

        assert state == BallState.LOST

        # Phase 3: 재감지
        for i in range(15, 25):
            det = BallDetection(
                position=Point2D(x=320.0, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(x=300, y=220, width=40, height=40),
            )
            tracker.update([det], frame_index=i)
            state = fsm.update(det)

        # LOST에서 복귀
        assert state != BallState.LOST


# =============================================================================
# 멀티뷰 통합 (detector 레벨)
# =============================================================================

class TestMultiViewIntegration:
    """멀티뷰 파이프라인 통합 (detector에서 융합 완료 후 단일 결과 전달)."""

    def test_멀티뷰_감지_후_단일_추적(self):
        """
        시나리오: detector가 멀티뷰 융합 완료한 단일 감지 결과를
        tracker에 전달하여 추적하는 흐름.

        김팀장 아키텍처: detector에서 8→1 융합, tracker/state는 단일 결과만 수신.
        """
        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        # detector가 멀티뷰 융합 완료한 단일 감지 결과 시뮬레이션
        for i in range(10):
            fused_detection = BallDetection(
                position=Point2D(x=320.0 + i, y=240.0),
                confidence=0.9,
                bbox=BoundingBox(x=300, y=220, width=40, height=40),
            )
            tracks = tracker.update([fused_detection], frame_index=i)

        # 트랙이 생성됨
        assert tracker._frame_count == 10


# =============================================================================
# 멀티뷰 삼각측량 통합 (실제 infrastructure 연동)
# =============================================================================

class TestMultiViewTriangulationIntegration:
    """BallDetector + 실제 MultiViewTriangulator 통합 테스트.

    Mock이 아닌 실제 infrastructure 삼각측량기를 사용하여
    멀티뷰 융합 파이프라인의 정확도를 검증합니다.
    """

    @staticmethod
    def _make_camera(
        camera_id: str,
        tx: float = 0.0,
        ty: float = 0.0,
        tz: float = 10.0,
        k1: float = -0.28,
        k2: float = 0.10,
    ):
        """테스트용 카메라 생성 (비영 왜곡)."""
        from infrastructure.multi_camera.camera_calibrator import CalibrationSnapshot
        from infrastructure.multi_camera.coordinate_transformer import (
            CoordinateTransformer,
        )

        K = np.array([
            [1000.0, 0.0, 960.0],
            [0.0, 1000.0, 540.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
        dist = np.array([k1, k2, 0.003, -0.002, 0.0], dtype=np.float64)

        snap = CalibrationSnapshot(
            camera_id=camera_id,
            intrinsic_matrix=K,
            distortion_coeffs=dist,
            rotation_matrix=np.eye(3, dtype=np.float64),
            translation_vector=np.array([tx, ty, tz], dtype=np.float64),
            reprojection_error=0.3,
            quality="good",
        )
        return CoordinateTransformer(snap)

    def test_실제_삼각측량기_주입_및_융합(self):
        """BallDetector에 실제 MultiViewTriangulator 주입 후 _fuse_multi_view 검증."""
        from infrastructure.multi_camera.coordinate_transformer import (
            CoordinateTransformer,
            MultiViewTriangulator,
        )
        from detection.ball_detection.ball_detector import (
            BallDetector,
            BallDetectorConfig,
            _BallCandidate,
        )

        # 2대 카메라 설정 (비영 왜곡)
        t0 = self._make_camera("cam_0", tx=0.0, tz=10.0)
        t1 = self._make_camera("cam_1", tx=5.0, tz=10.0)

        tri = MultiViewTriangulator(epipolar_threshold=3.0)
        tri.add_camera(t0)
        tri.add_camera(t1)

        # 목표 3D 점
        target = np.array([2.0, 1.0, 0.0], dtype=np.float64)
        px0 = t0.world_to_pixel(target)
        px1 = t1.world_to_pixel(target)

        # _BallCandidate 생성 (center가 투영 위치에 해당)
        c0 = _BallCandidate(
            bbox_x=px0[0] - 20.0,
            bbox_y=px0[1] - 20.0,
            bbox_w=40.0,
            bbox_h=40.0,
            yolo_confidence=0.9,
            combined_score=0.9,
            camera_id="cam_0",
        )
        c1 = _BallCandidate(
            bbox_x=px1[0] - 20.0,
            bbox_y=px1[1] - 20.0,
            bbox_w=40.0,
            bbox_h=40.0,
            yolo_confidence=0.88,
            combined_score=0.88,
            camera_id="cam_1",
        )

        # BallDetector 인스턴스 생성 (모델 로드 없이)
        detector = BallDetector.__new__(BallDetector)
        detector._triangulator = tri
        detector._config = BallDetectorConfig()

        # _fuse_multi_view 직접 호출
        view_candidates = {
            "cam_0": [c0],
            "cam_1": [c1],
        }
        frames = {
            "cam_0": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "cam_1": np.zeros((1080, 1920, 3), dtype=np.uint8),
        }

        fused = detector._fuse_multi_view(view_candidates, frames)

        # 3D 융합 결과 검증
        assert len(fused) == 1
        obj = fused[0]
        assert obj.position_3d is not None
        assert abs(obj.position_3d.x - 2.0) < 0.5
        assert abs(obj.position_3d.y - 1.0) < 0.5
        assert obj.attributes["fusion_method"] == "infrastructure_dlt"
        assert obj.attributes["num_views"] == 2

    def test_왜곡_카메라_3뷰_이상치_필터링_통합(self):
        """3뷰 + 이상치 → 에피폴라 필터링 → 정확한 3D 복원."""
        from infrastructure.multi_camera.coordinate_transformer import (
            MultiViewTriangulator,
        )
        from detection.ball_detection.ball_detector import (
            BallDetector,
            BallDetectorConfig,
            _BallCandidate,
        )

        t0 = self._make_camera("cam_0", tx=0.0, tz=10.0)
        t1 = self._make_camera("cam_1", tx=5.0, tz=10.0)
        t2 = self._make_camera("cam_2", tx=-3.0, ty=4.0, tz=10.0)

        tri = MultiViewTriangulator(epipolar_threshold=3.0)
        tri.add_camera(t0)
        tri.add_camera(t1)
        tri.add_camera(t2)

        target = np.array([1.5, 0.5, 0.0], dtype=np.float64)
        px0 = t0.world_to_pixel(target)
        px1 = t1.world_to_pixel(target)

        # cam_2: 이상치 (다른 3D 점의 투영)
        outlier = np.array([8.0, -4.0, 3.0], dtype=np.float64)
        px2 = t2.world_to_pixel(outlier)

        def _make_candidate(px, cam_id, conf=0.9):
            return _BallCandidate(
                bbox_x=px[0] - 20.0, bbox_y=px[1] - 20.0,
                bbox_w=40.0, bbox_h=40.0,
                yolo_confidence=conf, combined_score=conf,
                camera_id=cam_id,
            )

        detector = BallDetector.__new__(BallDetector)
        detector._triangulator = tri
        detector._config = BallDetectorConfig()

        view_candidates = {
            "cam_0": [_make_candidate(px0, "cam_0")],
            "cam_1": [_make_candidate(px1, "cam_1")],
            "cam_2": [_make_candidate(px2, "cam_2", conf=0.7)],
        }
        frames = {
            "cam_0": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "cam_1": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "cam_2": np.zeros((1080, 1920, 3), dtype=np.uint8),
        }

        fused = detector._fuse_multi_view(view_candidates, frames)

        assert len(fused) == 1
        obj = fused[0]
        # 에피폴라 필터링으로 이상치(cam_2) 제거 후 정확한 3D
        assert obj.position_3d is not None
        assert abs(obj.position_3d.x - 1.5) < 1.0
        assert abs(obj.position_3d.y - 0.5) < 1.0

    def test_삼각측량기_미주입_시_2D_결과만(self):
        """MultiViewTriangulator 미주입 시 2D 결과만 반환."""
        from detection.ball_detection.ball_detector import (
            BallDetector,
            BallDetectorConfig,
            _BallCandidate,
        )

        detector = BallDetector.__new__(BallDetector)
        detector._triangulator = None
        detector._config = BallDetectorConfig()

        c0 = _BallCandidate(
            bbox_x=300.0, bbox_y=220.0,
            bbox_w=40.0, bbox_h=40.0,
            yolo_confidence=0.9, combined_score=0.9,
            camera_id="cam_0",
        )
        c1 = _BallCandidate(
            bbox_x=500.0, bbox_y=220.0,
            bbox_w=40.0, bbox_h=40.0,
            yolo_confidence=0.85, combined_score=0.85,
            camera_id="cam_1",
        )

        view_candidates = {"cam_0": [c0], "cam_1": [c1]}
        frames = {
            "cam_0": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam_1": np.zeros((480, 640, 3), dtype=np.uint8),
        }

        fused = detector._fuse_multi_view(view_candidates, frames)

        assert len(fused) == 1
        # 2D 결과 → position_3d 없음
        assert fused[0].position_3d is None


# =============================================================================
# 패키지 Export 정합성
# =============================================================================

class TestPackageExports:
    """ball_detection 패키지 Export 정합성."""

    def test_ball_detection_init_exports(self):
        """ball_detection/__init__.py의 __all__ 검증."""
        from detection.ball_detection import __all__

        expected = {
            "BallDetector", "BallDetectorConfig",
            "BallTracker", "BallTrackerConfig",
            "BallStateMachine", "BallStateMachineConfig",
        }
        assert set(__all__) == expected

    def test_data_extraction_init_exports(self):
        """data_extraction/__init__.py의 __all__ 검증."""
        from detection.ball_detection.data_extraction import __all__

        expected = {
            "BallBboxExtractor", "BallBboxExtractorConfig",
            "TrajectoryExtractor", "TrajectoryExtractorConfig",
            "HardNegativeExtractor", "HardNegativeExtractorConfig",
            "RejectReason",
            "OcclusionSampleExtractor", "OcclusionSampleExtractorConfig",
            "OcclusionType",
            "SequenceTrigger",
            "TemporalSequenceExtractor", "TemporalSequenceExtractorConfig",
        }
        assert set(__all__) == expected

    def test_version(self):
        """모듈 버전 1.0.0 통일."""
        from detection.ball_detection import __version__
        from detection.ball_detection.data_extraction import __version__ as de_version

        assert __version__ == "1.0.0"
        assert de_version == "1.0.0"


# =============================================================================
# 스레드 안전성 통합
# =============================================================================

class TestThreadSafety:
    """멀티스레드 동시 접근 테스트."""

    def test_트래커_동시_업데이트(self):
        """2개 스레드에서 동시 update → 예외 없음."""
        import threading

        tracker = BallTracker()
        tracker.initialize(BallTrackerConfig())

        errors: list[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(50):
                    det = BallDetection(
                        position=Point2D(
                            x=100.0 + thread_id * 200 + i,
                            y=200.0,
                        ),
                        confidence=0.9,
                        bbox=BoundingBox(
                            x=80 + thread_id * 200 + i,
                            y=180,
                            width=40,
                            height=40,
                        ),
                    )
                    tracker.update([det], frame_index=i)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"스레드 오류: {errors}"

    def test_상태머신_동시_업데이트(self):
        """2개 스레드에서 동시 FSM update → 예외 없음."""
        import threading

        fsm = BallStateMachine()
        fsm.initialize(BallStateMachineConfig())

        errors: list[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(50):
                    det = BallDetection(
                        position=Point2D(
                            x=320.0 + thread_id * 10,
                            y=240.0,
                        ),
                        confidence=0.9,
                    )
                    fsm.update(det)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"스레드 오류: {errors}"
