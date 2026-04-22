# -*- coding: utf-8 -*-
"""
Tier 2 분류기 3종 단위 테스트 (25+건)

대상: ActionClassifier, ShotClassifier, DribbleClassifier
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import DetectionCandidate, MotionSnapshot
from motion_analysis.classification.action_classifier import ActionClassifier
from motion_analysis.classification.shot_classifier import ShotClassifier
from motion_analysis.classification.dribble_classifier import DribbleClassifier


# =============================================================================
# 헬퍼
# =============================================================================

def _snap(frame: int, **kw) -> MotionSnapshot:
    return MotionSnapshot(frame_index=frame, timestamp=frame / 30.0, **kw)


def _shooting_candidate() -> DetectionCandidate:
    return DetectionCandidate(
        action_type=ActionType.SHOOTING,
        confidence=0.85,
        start_frame=0, end_frame=29,
        start_time=0.0, end_time=1.0,
        player_tracking_id=1,
        evidence={"wrist_above_shoulder_m": 0.15, "elbow_angle_deg": 145.0, "release_speed_ms": 3.5},
    )


def _dribble_candidate() -> DetectionCandidate:
    return DetectionCandidate(
        action_type=ActionType.DRIBBLING,
        confidence=0.80,
        start_frame=0, end_frame=23,
        start_time=0.0, end_time=0.8,
        player_tracking_id=2,
        evidence={"hand_below_hip_ratio": 0.45, "frequency_hz": 3.2, "vertical_oscillation_cm": 50.0},
    )


def _shooting_snapshots(count: int = 30) -> list[MotionSnapshot]:
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        snaps.append(_snap(
            frame=i,
            player_tracking_id=1,
            joint_angles={
                JointType.RIGHT_ELBOW: 85.0 + p * 80.0,
                JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 45.0 + p * 90.0,
                JointType.LEFT_SHOULDER: 55.0,
                JointType.RIGHT_WRIST: 160.0 + p * 20.0,
                JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: 140.0,
                JointType.LEFT_KNEE: 137.0,
                JointType.RIGHT_HIP: 170.0,
                JointType.LEFT_HIP: 170.0,
                JointType.RIGHT_ANKLE: 90.0,
                JointType.LEFT_ANKLE: 90.0,
            },
            joint_speeds={
                JointType.RIGHT_WRIST: 40.0 + 300.0 * max(0, 1.0 - abs(p - 0.6) * 5),
                JointType.LEFT_WRIST: 10.0,
                JointType.RIGHT_ELBOW: 30.0,
                JointType.LEFT_ELBOW: 8.0,
                JointType.RIGHT_SHOULDER: 20.0,
                JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 15.0,
                JointType.LEFT_KNEE: 12.0,
                JointType.RIGHT_HIP: 8.0,
                JointType.LEFT_HIP: 7.0,
                JointType.RIGHT_ANKLE: 3.0,
                JointType.LEFT_ANKLE: 3.0,
            },
            joint_positions={
                JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
                JointType.RIGHT_ELBOW: (25.0, 140.0 + p * 30.0, 5.0),
                JointType.LEFT_ELBOW: (-25.0, 140.0, -3.0),
                JointType.RIGHT_WRIST: (28.0, 135.0 + p * 60.0, 10.0),
                JointType.LEFT_WRIST: (-28.0, 135.0, -5.0),
                JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
                JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
                JointType.RIGHT_KNEE: (14.0, 50.0, 3.0),
                JointType.LEFT_KNEE: (-14.0, 52.0, -2.0),
                JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
                JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
            },
            ball_position=(30.0, 135.0 + p * 60.0, 12.0),
            hoop_position=(0.0, 305.0, 500.0),
        ))
    return snaps


def _dribble_snapshots(count: int = 24) -> list[MotionSnapshot]:
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        hand_y = 95.0 - 55.0 * abs(p * 2 - 1.0)
        snaps.append(_snap(
            frame=i,
            player_tracking_id=2,
            joint_angles={
                JointType.RIGHT_ELBOW: 110.0,
                JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 40.0,
                JointType.LEFT_SHOULDER: 35.0,
                JointType.RIGHT_WRIST: 140.0,
                JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: 125.0,
                JointType.LEFT_KNEE: 122.0,
                JointType.RIGHT_HIP: 150.0,
                JointType.LEFT_HIP: 152.0,
                JointType.RIGHT_ANKLE: 85.0,
                JointType.LEFT_ANKLE: 85.0,
            },
            joint_speeds={
                JointType.RIGHT_WRIST: 100.0 + 100.0 * abs(p * 2 - 1.0),
                JointType.LEFT_WRIST: 8.0,
                JointType.RIGHT_ELBOW: 50.0,
                JointType.LEFT_ELBOW: 6.0,
                JointType.RIGHT_SHOULDER: 15.0,
                JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 12.0,
                JointType.LEFT_KNEE: 10.0,
                JointType.RIGHT_HIP: 8.0,
                JointType.LEFT_HIP: 7.0,
                JointType.RIGHT_ANKLE: 3.0,
                JointType.LEFT_ANKLE: 3.0,
            },
            joint_positions={
                JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
                JointType.RIGHT_ELBOW: (25.0, 125.0, 8.0),
                JointType.LEFT_ELBOW: (-25.0, 130.0, -5.0),
                JointType.RIGHT_WRIST: (28.0, hand_y, 15.0),
                JointType.LEFT_WRIST: (-28.0, 125.0, -8.0),
                JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
                JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
                JointType.RIGHT_KNEE: (14.0, 48.0, 3.0),
                JointType.LEFT_KNEE: (-14.0, 50.0, -2.0),
                JointType.RIGHT_ANKLE: (15.0, 5.0, 5.0),
                JointType.LEFT_ANKLE: (-15.0, 5.0, -3.0),
            },
            ball_position=(28.0, hand_y - 5.0, 15.0),
        ))
    return snaps


# =============================================================================
# ActionClassifier
# =============================================================================

class TestActionClassifier:
    def test_init(self) -> None:
        c = ActionClassifier()
        assert c is not None

    def test_classify_shooting_candidates(self) -> None:
        c = ActionClassifier()
        candidates = [_shooting_candidate()]
        results = c.classify(candidates, _shooting_snapshots())
        assert len(results) > 0

    def test_classify_empty_candidates(self) -> None:
        c = ActionClassifier()
        results = c.classify([], _shooting_snapshots())
        assert results == []

    def test_classify_multiple_candidates(self) -> None:
        c = ActionClassifier()
        candidates = [_shooting_candidate(), _dribble_candidate()]
        results = c.classify(candidates, _shooting_snapshots())
        assert len(results) >= 1

    def test_classify_returns_correct_types(self) -> None:
        from shared.dto.motion_dto import ActionClassification
        c = ActionClassifier()
        candidates = [_shooting_candidate()]
        results = c.classify(candidates, _shooting_snapshots())
        for r in results:
            assert isinstance(r, ActionClassification)

    def test_from_yaml(self) -> None:
        c = ActionClassifier.from_yaml({})
        assert c is not None


# =============================================================================
# ShotClassifier
# =============================================================================

class TestShotClassifier:
    def test_init(self) -> None:
        c = ShotClassifier()
        assert c is not None

    def test_classify_shooting(self) -> None:
        c = ShotClassifier()
        shot_type, confidence = c.classify(_shooting_candidate(), _shooting_snapshots())
        assert confidence > 0.0

    def test_classify_returns_tuple(self) -> None:
        c = ShotClassifier()
        result = c.classify(_shooting_candidate(), _shooting_snapshots())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_classify_confidence_range(self) -> None:
        c = ShotClassifier()
        _type, conf = c.classify(_shooting_candidate(), _shooting_snapshots())
        assert 0.0 <= conf <= 1.0

    def test_direct_instantiation(self) -> None:
        c = ShotClassifier()
        assert c is not None

    def test_classify_with_empty_snapshots(self) -> None:
        c = ShotClassifier()
        _type, conf = c.classify(_shooting_candidate(), [])
        assert conf >= 0.0


# =============================================================================
# DribbleClassifier
# =============================================================================

class TestDribbleClassifier:
    def test_init(self) -> None:
        c = DribbleClassifier()
        assert c is not None

    def test_classify_dribble(self) -> None:
        c = DribbleClassifier()
        dribble_type, confidence = c.classify(_dribble_candidate(), _dribble_snapshots())
        assert confidence > 0.0

    def test_classify_returns_tuple(self) -> None:
        c = DribbleClassifier()
        result = c.classify(_dribble_candidate(), _dribble_snapshots())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_classify_confidence_range(self) -> None:
        c = DribbleClassifier()
        _type, conf = c.classify(_dribble_candidate(), _dribble_snapshots())
        assert 0.0 <= conf <= 1.0

    def test_direct_instantiation(self) -> None:
        c = DribbleClassifier()
        assert c is not None

    def test_classify_with_empty_snapshots(self) -> None:
        c = DribbleClassifier()
        _type, conf = c.classify(_dribble_candidate(), [])
        assert conf >= 0.0


# =============================================================================
# 공통
# =============================================================================

class TestClassifiersCommon:
    def test_all_have_classify(self) -> None:
        assert hasattr(ActionClassifier, "classify")
        assert hasattr(ShotClassifier, "classify")
        assert hasattr(DribbleClassifier, "classify")

    def test_action_classifier_has_from_yaml(self) -> None:
        assert hasattr(ActionClassifier, "from_yaml")
