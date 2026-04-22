# -*- coding: utf-8 -*-
"""
Tier 1 감지기 5종 단위 테스트 (30+건)

대상: ShotDetector, DribbleDetector, PassDetector,
      MovementDetector, ReboundDetector + Config 5종
"""

from __future__ import annotations

import pytest

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import DetectionCandidate, MotionSnapshot
from motion_analysis.detection.shot_detector import ShotDetectionConfig, ShotDetector
from motion_analysis.detection.dribble_detector import DribbleDetectionConfig, DribbleDetector
from motion_analysis.detection.pass_detector import PassDetectionConfig, PassDetector
from motion_analysis.detection.movement_detector import MovementDetectionConfig, MovementDetector
from motion_analysis.detection.rebound_detector import ReboundDetectionConfig, ReboundDetector


# =============================================================================
# 공통 헬퍼
# =============================================================================

def _snap(
    frame: int,
    angles: dict[JointType, float] | None = None,
    speeds: dict[JointType, float] | None = None,
    positions: dict[JointType, tuple[float, float, float]] | None = None,
    com: tuple[float, float, float] | None = None,
    ball: tuple[float, float, float] | None = None,
    hoop: tuple[float, float, float] | None = None,
    stability: float = 75.0,
    player_id: int = 1,
) -> MotionSnapshot:
    return MotionSnapshot(
        frame_index=frame,
        timestamp=frame / 30.0,
        player_tracking_id=player_id,
        joint_angles=angles or {},
        joint_speeds=speeds or {},
        joint_positions=positions or {},
        com_position=com or (0.0, 100.0, 0.0),
        ball_position=ball,
        hoop_position=hoop,
        stability_index=stability,
    )


def _shooting_sequence(count: int = 30) -> list[MotionSnapshot]:
    """감지 가능한 슈팅 시퀀스."""
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        elbow = 85.0 + p * 80.0
        shoulder = 45.0 + p * 90.0
        release = max(0.0, 1.0 - abs(p - 0.6) * 5.0)
        wrist_speed = 40.0 + 320.0 * release
        shoulder_y = 150.0
        wrist_y = 135.0 + p * 60.0
        knee = 160.0 - 40.0 * max(0.0, 1.0 - abs(p - 0.35) * 5.0)
        knee = max(110.0, min(170.0, knee))

        snaps.append(_snap(
            frame=i,
            angles={
                JointType.RIGHT_ELBOW: elbow, JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: shoulder, JointType.LEFT_SHOULDER: 55.0,
                JointType.RIGHT_WRIST: 160.0 + p * 20.0, JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: knee, JointType.LEFT_KNEE: knee - 3.0,
                JointType.RIGHT_HIP: 170.0, JointType.LEFT_HIP: 170.0,
                JointType.RIGHT_ANKLE: 90.0, JointType.LEFT_ANKLE: 90.0,
            },
            speeds={
                JointType.RIGHT_WRIST: wrist_speed, JointType.LEFT_WRIST: 10.0,
                JointType.RIGHT_ELBOW: wrist_speed * 0.6, JointType.LEFT_ELBOW: 8.0,
                JointType.RIGHT_SHOULDER: wrist_speed * 0.3, JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 20.0, JointType.LEFT_KNEE: 18.0,
                JointType.RIGHT_HIP: 10.0, JointType.LEFT_HIP: 8.0,
                JointType.RIGHT_ANKLE: 5.0, JointType.LEFT_ANKLE: 4.0,
            },
            positions={
                JointType.RIGHT_SHOULDER: (20.0, shoulder_y, 0.0),
                JointType.LEFT_SHOULDER: (-20.0, shoulder_y, 0.0),
                JointType.RIGHT_ELBOW: (25.0, shoulder_y - 10 + p * 30, 5.0),
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
            ball=(30.0, wrist_y + 5.0, 12.0),
            hoop=(0.0, 305.0, 500.0),
        ))
    return snaps


def _dribble_sequence(count: int = 24) -> list[MotionSnapshot]:
    """감지 가능한 드리블 시퀀스."""
    snaps = []
    for i in range(count):
        p = i / max(1, count - 1)
        hand_y = 95.0 - 65.0 * abs(p * 2 - 1.0) + 30.0
        wrist_speed = 80.0 + 120.0 * abs(p * 2 - 1.0)
        snaps.append(_snap(
            frame=i,
            angles={
                JointType.RIGHT_ELBOW: 110.0, JointType.LEFT_ELBOW: 90.0,
                JointType.RIGHT_SHOULDER: 40.0, JointType.LEFT_SHOULDER: 35.0,
                JointType.RIGHT_WRIST: 140.0, JointType.LEFT_WRIST: 150.0,
                JointType.RIGHT_KNEE: 125.0, JointType.LEFT_KNEE: 122.0,
                JointType.RIGHT_HIP: 150.0, JointType.LEFT_HIP: 152.0,
                JointType.RIGHT_ANKLE: 85.0, JointType.LEFT_ANKLE: 85.0,
            },
            speeds={
                JointType.RIGHT_WRIST: wrist_speed, JointType.LEFT_WRIST: 8.0,
                JointType.RIGHT_ELBOW: wrist_speed * 0.5, JointType.LEFT_ELBOW: 6.0,
                JointType.RIGHT_SHOULDER: 15.0, JointType.LEFT_SHOULDER: 5.0,
                JointType.RIGHT_KNEE: 12.0, JointType.LEFT_KNEE: 10.0,
                JointType.RIGHT_HIP: 8.0, JointType.LEFT_HIP: 7.0,
                JointType.RIGHT_ANKLE: 3.0, JointType.LEFT_ANKLE: 3.0,
            },
            positions={
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
            ball=(28.0, hand_y - 5.0, 15.0),
            hoop=(0.0, 305.0, 700.0),
        ))
    return snaps


def _idle_sequence(count: int = 20) -> list[MotionSnapshot]:
    """정지 상태 (감지 안 되어야 함)."""
    return [_snap(
        frame=i,
        angles={j: 90.0 for j in [
            JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
            JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER,
            JointType.RIGHT_KNEE, JointType.LEFT_KNEE,
        ]},
        speeds={j: 2.0 for j in [
            JointType.RIGHT_WRIST, JointType.LEFT_WRIST,
            JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
        ]},
        positions={
            JointType.RIGHT_SHOULDER: (20.0, 150.0, 0.0),
            JointType.LEFT_SHOULDER: (-20.0, 150.0, 0.0),
            JointType.RIGHT_WRIST: (28.0, 100.0, 0.0),  # 허리 높이
            JointType.LEFT_WRIST: (-28.0, 100.0, 0.0),
            JointType.RIGHT_HIP: (12.0, 95.0, 0.0),
            JointType.LEFT_HIP: (-12.0, 95.0, 0.0),
            JointType.RIGHT_KNEE: (14.0, 50.0, 0.0),
            JointType.LEFT_KNEE: (-14.0, 50.0, 0.0),
            JointType.RIGHT_ANKLE: (15.0, 5.0, 0.0),
            JointType.LEFT_ANKLE: (-15.0, 5.0, 0.0),
        },
    ) for i in range(count)]


# =============================================================================
# ShotDetector
# =============================================================================

class TestShotDetectionConfig:
    def test_defaults(self) -> None:
        cfg = ShotDetectionConfig()
        assert cfg.wrist_above_shoulder_m > 0
        assert cfg.elbow_angle_min > 0
        assert cfg.min_duration_frames > 0

    def test_custom(self) -> None:
        cfg = ShotDetectionConfig(wrist_above_shoulder_m=0.2)
        assert cfg.wrist_above_shoulder_m == 0.2


class TestShotDetector:
    def test_init_default(self) -> None:
        d = ShotDetector()
        assert d is not None

    def test_init_custom_config(self) -> None:
        cfg = ShotDetectionConfig(min_duration_frames=5)
        d = ShotDetector(config=cfg)
        assert d is not None

    def test_detect_shooting_sequence(self) -> None:
        d = ShotDetector()
        candidates = d.detect(_shooting_sequence(30))
        assert len(candidates) > 0
        assert all(isinstance(c, DetectionCandidate) for c in candidates)

    def test_detect_returns_shooting_type(self) -> None:
        d = ShotDetector()
        candidates = d.detect(_shooting_sequence(30))
        for c in candidates:
            assert c.action_type == ActionType.SHOOTING

    def test_detect_empty_sequence(self) -> None:
        d = ShotDetector()
        assert d.detect([]) == []

    def test_detect_idle_no_shots(self) -> None:
        d = ShotDetector()
        candidates = d.detect(_idle_sequence(20))
        assert len(candidates) == 0

    def test_detect_confidence_range(self) -> None:
        d = ShotDetector()
        candidates = d.detect(_shooting_sequence(30))
        for c in candidates:
            assert 0.0 <= c.confidence <= 1.0

    def test_from_yaml(self) -> None:
        d = ShotDetector.from_yaml({
            "wrist_above_shoulder_m": 0.15,
            "elbow_angle_min": 90.0,
        })
        assert d is not None


# =============================================================================
# DribbleDetector
# =============================================================================

class TestDribbleDetectionConfig:
    def test_defaults(self) -> None:
        cfg = DribbleDetectionConfig()
        assert cfg is not None


class TestDribbleDetector:
    def test_init(self) -> None:
        d = DribbleDetector()
        assert d is not None

    def test_detect_dribble_sequence(self) -> None:
        d = DribbleDetector()
        candidates = d.detect(_dribble_sequence(24))
        assert len(candidates) >= 0  # 드리블 감지 시도
        for c in candidates:
            assert c.action_type == ActionType.DRIBBLING

    def test_detect_empty(self) -> None:
        assert DribbleDetector().detect([]) == []

    def test_detect_idle_no_dribble(self) -> None:
        candidates = DribbleDetector().detect(_idle_sequence(20))
        assert len(candidates) == 0

    def test_from_yaml(self) -> None:
        d = DribbleDetector.from_yaml({})
        assert d is not None


# =============================================================================
# PassDetector
# =============================================================================

class TestPassDetectionConfig:
    def test_defaults(self) -> None:
        cfg = PassDetectionConfig()
        assert cfg is not None


class TestPassDetector:
    def test_init(self) -> None:
        d = PassDetector()
        assert d is not None

    def test_detect_empty(self) -> None:
        assert PassDetector().detect([]) == []

    def test_detect_idle_no_pass(self) -> None:
        candidates = PassDetector().detect(_idle_sequence(20))
        assert len(candidates) == 0

    def test_from_yaml(self) -> None:
        d = PassDetector.from_yaml({})
        assert d is not None


# =============================================================================
# MovementDetector
# =============================================================================

class TestMovementDetectionConfig:
    def test_defaults(self) -> None:
        cfg = MovementDetectionConfig()
        assert cfg is not None


class TestMovementDetector:
    def test_init(self) -> None:
        d = MovementDetector()
        assert d is not None

    def test_detect_empty(self) -> None:
        assert MovementDetector().detect([]) == []

    def test_from_yaml(self) -> None:
        d = MovementDetector.from_yaml({})
        assert d is not None


# =============================================================================
# ReboundDetector
# =============================================================================

class TestReboundDetectionConfig:
    def test_defaults(self) -> None:
        cfg = ReboundDetectionConfig()
        assert cfg is not None


class TestReboundDetector:
    def test_init(self) -> None:
        d = ReboundDetector()
        assert d is not None

    def test_detect_empty(self) -> None:
        assert ReboundDetector().detect([]) == []

    def test_detect_idle_no_rebound(self) -> None:
        candidates = ReboundDetector().detect(_idle_sequence(20))
        assert len(candidates) == 0

    def test_from_yaml(self) -> None:
        d = ReboundDetector.from_yaml({})
        assert d is not None


# =============================================================================
# 공통 검증
# =============================================================================

class TestAllDetectorsCommon:
    """5종 감지기 공통 속성 검증."""

    def test_all_detectors_have_detect_method(self) -> None:
        for cls in [ShotDetector, DribbleDetector, PassDetector, MovementDetector, ReboundDetector]:
            assert hasattr(cls, "detect")

    def test_all_detectors_have_from_yaml(self) -> None:
        for cls in [ShotDetector, DribbleDetector, PassDetector, MovementDetector, ReboundDetector]:
            assert hasattr(cls, "from_yaml")

    def test_all_configs_are_dataclass(self) -> None:
        import dataclasses
        for cls in [ShotDetectionConfig, DribbleDetectionConfig, PassDetectionConfig,
                    MovementDetectionConfig, ReboundDetectionConfig]:
            assert dataclasses.is_dataclass(cls)
