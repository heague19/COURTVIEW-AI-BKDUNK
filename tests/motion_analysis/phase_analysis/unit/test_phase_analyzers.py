# -*- coding: utf-8 -*-
"""
Tier 3 분석기 2종 단위 테스트 (20+건)

대상: ShotPhaseAnalyzer, DribblePhaseAnalyzer
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    DetectionCandidate,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
    DribblePhase,
)
from biomechanics.phase_analysis.shot_phase_analyzer import ShotPhaseAnalyzer
from biomechanics.phase_analysis.dribble_phase_analyzer import DribblePhaseAnalyzer


# =============================================================================
# 헬퍼
# =============================================================================

def _snap(frame: int, p: float, player_id: int = 1) -> MotionSnapshot:
    """슈팅 시뮬레이션 스냅샷."""
    elbow = 85.0 + p * 80.0
    wrist_speed = 40.0 + 300.0 * max(0.0, 1.0 - abs(p - 0.6) * 5.0)
    wrist_y = 135.0 + p * 60.0
    knee = 160.0 - 40.0 * max(0.0, 1.0 - abs(p - 0.35) * 5.0)
    return MotionSnapshot(
        frame_index=frame, timestamp=frame / 30.0, player_tracking_id=player_id,
        joint_angles={
            JointType.RIGHT_ELBOW: elbow, JointType.LEFT_ELBOW: 90.0,
            JointType.RIGHT_SHOULDER: 45.0 + p * 90.0, JointType.LEFT_SHOULDER: 55.0,
            JointType.RIGHT_WRIST: 160.0, JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: max(110.0, min(170.0, knee)),
            JointType.LEFT_KNEE: max(110.0, min(170.0, knee - 3)),
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
        ball_position=(30.0, wrist_y + 5.0, 12.0),
        hoop_position=(0.0, 305.0, 500.0),
        stability_index=80.0,
    )


def _shooting_snapshots(count: int = 30) -> list[MotionSnapshot]:
    return [_snap(i, i / max(1, count - 1)) for i in range(count)]


def _dribble_snap(frame: int, p: float) -> MotionSnapshot:
    hand_y = 95.0 - 65.0 * abs(p * 2 - 1.0) + 30.0
    wrist_speed = 80.0 + 120.0 * abs(p * 2 - 1.0)
    return MotionSnapshot(
        frame_index=frame, timestamp=frame / 30.0, player_tracking_id=2,
        joint_angles={
            JointType.RIGHT_ELBOW: 110.0, JointType.LEFT_ELBOW: 90.0,
            JointType.RIGHT_SHOULDER: 40.0, JointType.LEFT_SHOULDER: 35.0,
            JointType.RIGHT_WRIST: 140.0, JointType.LEFT_WRIST: 150.0,
            JointType.RIGHT_KNEE: 125.0, JointType.LEFT_KNEE: 122.0,
            JointType.RIGHT_HIP: 150.0, JointType.LEFT_HIP: 152.0,
            JointType.RIGHT_ANKLE: 85.0, JointType.LEFT_ANKLE: 85.0,
        },
        joint_speeds={
            JointType.RIGHT_WRIST: wrist_speed, JointType.LEFT_WRIST: 8.0,
            JointType.RIGHT_ELBOW: wrist_speed * 0.5, JointType.LEFT_ELBOW: 6.0,
            JointType.RIGHT_SHOULDER: 15.0, JointType.LEFT_SHOULDER: 5.0,
            JointType.RIGHT_KNEE: 12.0, JointType.LEFT_KNEE: 10.0,
            JointType.RIGHT_HIP: 8.0, JointType.LEFT_HIP: 7.0,
            JointType.RIGHT_ANKLE: 3.0, JointType.LEFT_ANKLE: 3.0,
        },
        joint_positions={
            JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
            JointType.RIGHT_WRIST: (28.0, hand_y, 15.0),
            JointType.LEFT_WRIST: (-28.0, 125.0, -8.0),
            JointType.RIGHT_ELBOW: (25.0, 125.0, 8.0),
            JointType.LEFT_ELBOW: (-25.0, 130.0, -5.0),
            JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
            JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
            JointType.RIGHT_KNEE: (14.0, 48.0, 3.0),
            JointType.LEFT_KNEE: (-14.0, 50.0, -2.0),
            JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
            JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
        },
        ball_position=(28.0, hand_y - 5.0, 15.0),
        stability_index=75.0,
    )


def _dribble_snapshots(count: int = 24) -> list[MotionSnapshot]:
    return [_dribble_snap(i, i / max(1, count - 1)) for i in range(count)]


def _shot_candidate(count: int = 30) -> DetectionCandidate:
    return DetectionCandidate(
        action_type=ActionType.SHOOTING, confidence=0.85,
        start_frame=0, end_frame=count - 1,
        start_time=0.0, end_time=(count - 1) / 30.0,
        player_tracking_id=1,
        evidence={"wrist_above_shoulder_m": 0.15},
    )


def _dribble_candidate(count: int = 24) -> DetectionCandidate:
    return DetectionCandidate(
        action_type=ActionType.DRIBBLING, confidence=0.80,
        start_frame=0, end_frame=count - 1,
        start_time=0.0, end_time=(count - 1) / 30.0,
        player_tracking_id=2,
        evidence={"hand_below_hip_ratio": 0.45},
    )


# =============================================================================
# ShotPhaseAnalyzer
# =============================================================================

class TestShotPhaseAnalyzer:
    def test_init(self) -> None:
        a = ShotPhaseAnalyzer()
        assert a is not None

    def test_analyze_returns_phase_result(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert isinstance(result, PhaseResult)

    def test_action_type_is_shooting(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert result.action_type == ActionType.SHOOTING

    def test_has_phases(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert result.phase_count > 0

    def test_phases_are_segments(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        for phase in result.phases:
            assert isinstance(phase, PhaseSegment)

    def test_kinetic_chain_score_range(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert 0.0 <= result.kinetic_chain_score <= 1.0

    def test_transition_smoothness_range(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert 0.0 <= result.transition_smoothness <= 1.0

    def test_phase_quality_range(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        for phase in result.phases:
            assert 0.0 <= phase.quality <= 1.0

    def test_total_duration_positive(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert result.total_duration_frames > 0

    def test_from_yaml(self) -> None:
        a = ShotPhaseAnalyzer.from_yaml({})
        assert a is not None

    def test_player_id_propagation(self) -> None:
        a = ShotPhaseAnalyzer()
        result = a.analyze(_shot_candidate(), _shooting_snapshots())
        assert result.player_tracking_id == 1


# =============================================================================
# DribblePhaseAnalyzer
# =============================================================================

class TestDribblePhaseAnalyzer:
    def test_init(self) -> None:
        a = DribblePhaseAnalyzer()
        assert a is not None

    def test_analyze_returns_phase_result(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert isinstance(result, PhaseResult)

    def test_action_type_is_dribbling(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert result.action_type == ActionType.DRIBBLING

    def test_has_phases(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert result.phase_count > 0

    def test_kinetic_chain_score_range(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert 0.0 <= result.kinetic_chain_score <= 1.0

    def test_total_duration_positive(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert result.total_duration_frames > 0

    def test_from_yaml(self) -> None:
        a = DribblePhaseAnalyzer.from_yaml({})
        assert a is not None

    def test_player_id_propagation(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        assert result.player_tracking_id == 2

    def test_phase_segments_have_key_metrics(self) -> None:
        a = DribblePhaseAnalyzer()
        result = a.analyze(_dribble_candidate(), _dribble_snapshots())
        for phase in result.phases:
            assert isinstance(phase.key_metrics, dict)
