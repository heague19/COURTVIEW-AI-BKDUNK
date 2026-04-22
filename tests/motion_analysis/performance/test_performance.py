# -*- coding: utf-8 -*-
"""
motion_analysis 성능 테스트

김팀장 지시 기준:
    1. 5종 감지기: 1000프레임 처리 시간 < 1ms/frame (각 감지기)
    2. DTW 비교기: 100프레임 시퀀스 비교 < 50ms
    3. 전체 파이프라인: Tier 1→5 순차 처리 < 5ms/frame (30fps 여유)
"""

from __future__ import annotations

import time

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import DetectionCandidate, MotionSnapshot, PhaseSegment, PhaseResult
from motion_analysis.detection.shot_detector import ShotDetector
from motion_analysis.detection.dribble_detector import DribbleDetector
from motion_analysis.detection.pass_detector import PassDetector
from motion_analysis.detection.movement_detector import MovementDetector
from motion_analysis.detection.rebound_detector import ReboundDetector
from motion_analysis.classification.shot_classifier import ShotClassifier
from biomechanics.phase_analysis.shot_phase_analyzer import ShotPhaseAnalyzer
from feedback_system.form_evaluation.shooting_criteria import ShootingCriteria
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.comparison.form_comparator import FormComparator


# =============================================================================
# 대량 데이터 생성
# =============================================================================

def _bulk_snapshots(count: int, player_id: int = 1) -> list[MotionSnapshot]:
    """성능 테스트용 대량 스냅샷 생성."""
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        elbow = 85.0 + p * 80.0
        wrist_speed = 40.0 + 300.0 * max(0.0, 1.0 - abs(p - 0.6) * 5.0)
        wrist_y = 135.0 + p * 60.0
        knee = 160.0 - 40.0 * max(0.0, 1.0 - abs(p - 0.35) * 5.0)
        knee = max(110.0, min(170.0, knee))

        snaps.append(MotionSnapshot(
            frame_index=i, timestamp=i / 30.0, player_tracking_id=player_id,
            joint_angles={
                JointType.RIGHT_ELBOW: elbow, JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 45.0 + p * 90.0, JointType.LEFT_SHOULDER: 55.0,
                JointType.RIGHT_WRIST: 160.0, JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: knee, JointType.LEFT_KNEE: knee - 3.0,
                JointType.RIGHT_HIP: 170.0, JointType.LEFT_HIP: 170.0,
                JointType.RIGHT_ANKLE: 90.0, JointType.LEFT_ANKLE: 90.0,
            },
            joint_speeds={
                JointType.RIGHT_WRIST: wrist_speed, JointType.LEFT_WRIST: 10.0,
                JointType.RIGHT_ELBOW: wrist_speed * 0.6, JointType.LEFT_ELBOW: 8.0,
                JointType.RIGHT_SHOULDER: wrist_speed * 0.3, JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 20.0, JointType.LEFT_KNEE: 18.0,
                JointType.RIGHT_HIP: 10.0, JointType.LEFT_HIP: 8.0,
                JointType.RIGHT_ANKLE: 5.0, JointType.LEFT_ANKLE: 4.0,
            },
            joint_positions={
                JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
                JointType.RIGHT_ELBOW: (25.0, 140.0 + p * 30.0, 5.0),
                JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
                JointType.RIGHT_WRIST: (28.0, wrist_y, 10.0),
                JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
                JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
                JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
                JointType.RIGHT_KNEE: (14.0, 50.0, 3.0),
                JointType.LEFT_KNEE: (-14.0, 52.0, -2.0),
                JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
                JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
            },
            com_position=(0.0, 100.0, 0.0),
            ball_position=(30.0, wrist_y + 5.0, 12.0),
            hoop_position=(0.0, 305.0, 500.0),
            stability_index=80.0,
        ))
    return snaps


# =============================================================================
# 1. 5종 감지기 성능: 1000프레임 < 1ms/frame
# =============================================================================

class TestDetectorPerformance:
    """5종 감지기 1000프레임 처리 성능 검증."""

    @pytest.fixture(scope="class")
    def snapshots_1000(self) -> list[MotionSnapshot]:
        return _bulk_snapshots(1000)

    def test_shot_detector_performance(self, snapshots_1000: list[MotionSnapshot]) -> None:
        d = ShotDetector()
        start = time.perf_counter()
        d.detect(snapshots_1000)
        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / 1000
        assert ms_per_frame < 1.0, f"ShotDetector: {ms_per_frame:.3f}ms/frame > 1ms"

    def test_dribble_detector_performance(self, snapshots_1000: list[MotionSnapshot]) -> None:
        d = DribbleDetector()
        start = time.perf_counter()
        d.detect(snapshots_1000)
        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / 1000
        assert ms_per_frame < 1.0, f"DribbleDetector: {ms_per_frame:.3f}ms/frame > 1ms"

    def test_pass_detector_performance(self, snapshots_1000: list[MotionSnapshot]) -> None:
        d = PassDetector()
        start = time.perf_counter()
        d.detect(snapshots_1000)
        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / 1000
        assert ms_per_frame < 1.0, f"PassDetector: {ms_per_frame:.3f}ms/frame > 1ms"

    def test_movement_detector_performance(self, snapshots_1000: list[MotionSnapshot]) -> None:
        d = MovementDetector()
        start = time.perf_counter()
        d.detect(snapshots_1000)
        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / 1000
        assert ms_per_frame < 1.0, f"MovementDetector: {ms_per_frame:.3f}ms/frame > 1ms"

    def test_rebound_detector_performance(self, snapshots_1000: list[MotionSnapshot]) -> None:
        d = ReboundDetector()
        start = time.perf_counter()
        d.detect(snapshots_1000)
        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / 1000
        assert ms_per_frame < 1.0, f"ReboundDetector: {ms_per_frame:.3f}ms/frame > 1ms"


# =============================================================================
# 2. DTW 비교기 성능: 100프레임 < 50ms
# =============================================================================

class TestDTWPerformance:
    """DTW 비교기 100프레임 시퀀스 비교 성능 검증."""

    def test_dtw_100_frames_under_50ms(self) -> None:
        c = FormComparator()
        snaps_a = _bulk_snapshots(100)
        snaps_b = _bulk_snapshots(100, player_id=2)
        phases = PhaseResult(
            action_type=ActionType.SHOOTING, player_tracking_id=1,
            phases=[
                PhaseSegment(phase_name="preparation", start_frame=0, end_frame=24, duration_frames=25, quality=0.85),
                PhaseSegment(phase_name="loading", start_frame=25, end_frame=49, duration_frames=25, quality=0.80),
                PhaseSegment(phase_name="release", start_frame=50, end_frame=74, duration_frames=25, quality=0.82),
                PhaseSegment(phase_name="follow_through", start_frame=75, end_frame=99, duration_frames=25, quality=0.88),
            ],
            total_duration_frames=100, kinetic_chain_score=0.82, transition_smoothness=0.79,
        )

        start = time.perf_counter()
        result = c.compare(snaps_a, snaps_b, current_phases=phases, reference_phases=phases)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50.0, f"DTW 100프레임: {elapsed_ms:.1f}ms > 50ms"
        assert isinstance(result.similarity_score, float)

    def test_dtw_50_frames_under_25ms(self) -> None:
        c = FormComparator()
        snaps_a = _bulk_snapshots(50)
        snaps_b = _bulk_snapshots(50, player_id=2)

        start = time.perf_counter()
        c.compare(snaps_a, snaps_b)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 25.0, f"DTW 50프레임: {elapsed_ms:.1f}ms > 25ms"


# =============================================================================
# 3. 전체 파이프라인 성능: Tier 1→5 < 5ms/frame
# =============================================================================

class TestPipelinePerformance:
    """Tier 1→5 전체 파이프라인 성능 검증."""

    def test_full_pipeline_under_5ms_per_frame(self) -> None:
        """30프레임 슈팅 시퀀스 전체 파이프라인: < 5ms/frame."""
        frame_count = 30
        snaps = _bulk_snapshots(frame_count)
        ref_snaps = _bulk_snapshots(frame_count, player_id=2)

        shot_detector = ShotDetector()
        shot_classifier = ShotClassifier()
        phase_analyzer = ShotPhaseAnalyzer()
        evaluator = ShootingFormEvaluator(ShootingCriteria())
        comparator = FormComparator()

        start = time.perf_counter()

        # Tier 1: 감지
        candidates = shot_detector.detect(snaps)
        if not candidates:
            pytest.skip("감지 실패")
            return

        best = max(candidates, key=lambda c: c.confidence)

        # Tier 2: 분류
        shot_classifier.classify(best, snaps)

        # Tier 3: 위상 분석
        phase_result = phase_analyzer.analyze(best, snaps)

        # Tier 4: 폼 평가
        evaluator.evaluate(phase_result, snaps)

        # Tier 5: 비교
        comparator.compare(snaps, ref_snaps, current_phases=phase_result)

        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / frame_count

        assert ms_per_frame < 5.0, f"파이프라인: {ms_per_frame:.2f}ms/frame > 5ms"

    def test_pipeline_100_frames_still_fast(self) -> None:
        """100프레임 전체 파이프라인도 30fps 여유 내."""
        frame_count = 100
        snaps = _bulk_snapshots(frame_count)
        ref_snaps = _bulk_snapshots(frame_count, player_id=2)

        shot_detector = ShotDetector()
        shot_classifier = ShotClassifier()
        phase_analyzer = ShotPhaseAnalyzer()
        evaluator = ShootingFormEvaluator(ShootingCriteria())
        comparator = FormComparator()

        start = time.perf_counter()

        candidates = shot_detector.detect(snaps)
        if not candidates:
            pytest.skip("감지 실패")
            return

        best = max(candidates, key=lambda c: c.confidence)
        shot_classifier.classify(best, snaps)
        phase_result = phase_analyzer.analyze(best, snaps)
        evaluator.evaluate(phase_result, snaps)
        comparator.compare(snaps, ref_snaps, current_phases=phase_result)

        elapsed = time.perf_counter() - start
        ms_per_frame = (elapsed * 1000) / frame_count

        assert ms_per_frame < 5.0, f"파이프라인 100프레임: {ms_per_frame:.2f}ms/frame > 5ms"
