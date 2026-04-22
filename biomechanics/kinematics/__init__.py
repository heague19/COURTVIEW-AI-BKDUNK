# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: __init__.py
설명: 운동학 패키지 초기화 (Lazy Import)
      - 관절 각도 계산: joint_angle_calculator
      - 속도/각속도 분석: velocity_analyzer
      - 가속도/각가속도 분석: acceleration_analyzer
      - 궤적 분석: trajectory_analyzer
      - 몸체 방위: body_orientation
      - 동작 패턴: motion_pattern

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

사용 예시:
    >>> from biomechanics.kinematics import calculate_all_joint_angles, FrameAngles
    >>> frame_angles = calculate_all_joint_angles(keypoints_3d)
    >>> frame_angles.completeness
    1.0

    >>> from biomechanics.kinematics import detect_motion_patterns, MotionState
    >>> state = detect_motion_patterns(angles, velocities)
    >>> state.primary_pattern.pattern_type
    'shooting'
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# Lazy Import 매핑: 심볼명 → 소스 모듈
# =============================================================================
_SUBMODULE_MAP: dict[str, str] = {
    # === joint_angle_calculator (12) ===
    "JointAngle": "biomechanics.kinematics.joint_angle_calculator",
    "FrameAngles": "biomechanics.kinematics.joint_angle_calculator",
    "AngleDeviation": "biomechanics.kinematics.joint_angle_calculator",
    "calculate_joint_angle": "biomechanics.kinematics.joint_angle_calculator",
    "calculate_all_joint_angles": "biomechanics.kinematics.joint_angle_calculator",
    "calculate_trunk_forward_lean": "biomechanics.kinematics.joint_angle_calculator",
    "calculate_stance_width_ratio": "biomechanics.kinematics.joint_angle_calculator",
    "evaluate_shooting_angles": "biomechanics.kinematics.joint_angle_calculator",
    "evaluate_defensive_stance": "biomechanics.kinematics.joint_angle_calculator",
    "evaluate_dribbling_stance": "biomechanics.kinematics.joint_angle_calculator",
    "evaluate_jump_landing": "biomechanics.kinematics.joint_angle_calculator",
    "get_bilateral_difference": "biomechanics.kinematics.joint_angle_calculator",

    # === velocity_analyzer (7) ===
    "JointVelocity": "biomechanics.kinematics.velocity_analyzer",
    "FrameVelocities": "biomechanics.kinematics.velocity_analyzer",
    "calculate_joint_velocity": "biomechanics.kinematics.velocity_analyzer",
    "calculate_central_velocity": "biomechanics.kinematics.velocity_analyzer",
    "calculate_all_velocities": "biomechanics.kinematics.velocity_analyzer",
    "calculate_body_speed": "biomechanics.kinematics.velocity_analyzer",
    "classify_movement_intensity": "biomechanics.kinematics.velocity_analyzer",

    # === acceleration_analyzer (10) ===
    "JointAcceleration": "biomechanics.kinematics.acceleration_analyzer",
    "BodyAcceleration": "biomechanics.kinematics.acceleration_analyzer",
    "FrameAccelerations": "biomechanics.kinematics.acceleration_analyzer",
    "calculate_joint_acceleration": "biomechanics.kinematics.acceleration_analyzer",
    "calculate_position_acceleration": "biomechanics.kinematics.acceleration_analyzer",
    "calculate_body_acceleration": "biomechanics.kinematics.acceleration_analyzer",
    "calculate_all_accelerations": "biomechanics.kinematics.acceleration_analyzer",
    "detect_explosive_acceleration": "biomechanics.kinematics.acceleration_analyzer",
    "detect_hard_stop": "biomechanics.kinematics.acceleration_analyzer",
    "detect_direction_change": "biomechanics.kinematics.acceleration_analyzer",

    # === trajectory_analyzer (3) ===
    "TrajectoryMetrics": "biomechanics.kinematics.trajectory_analyzer",
    "analyze_trajectory": "biomechanics.kinematics.trajectory_analyzer",
    "TrajectoryBuffer": "biomechanics.kinematics.trajectory_analyzer",

    # === body_orientation (6) ===
    "BodyOrientation": "biomechanics.kinematics.body_orientation",
    "TrunkSeparation": "biomechanics.kinematics.body_orientation",
    "calculate_body_orientation": "biomechanics.kinematics.body_orientation",
    "calculate_trunk_separation": "biomechanics.kinematics.body_orientation",
    "calculate_facing_angle_to_target": "biomechanics.kinematics.body_orientation",
    "get_orientation_tuple": "biomechanics.kinematics.body_orientation",

    # === motion_pattern (4) ===
    "PatternMatch": "biomechanics.kinematics.motion_pattern",
    "MotionState": "biomechanics.kinematics.motion_pattern",
    "detect_motion_patterns": "biomechanics.kinematics.motion_pattern",
    "determine_phase_from_angles": "biomechanics.kinematics.motion_pattern",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브모듈만 로드."""
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics.kinematics' has no attribute {name!r}")
