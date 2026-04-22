# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics
파일: __init__.py
설명: 생체역학 패키지 루트 초기화 (Lazy Import)
      - standards/: 연령대/리그별 생체역학 기준값
      - anthropometry/: 인체측정학 (신체 모델, 비율, 연령/성별 적응)
      - kinematics/: 운동학 (관절 각도, 속도, 가속도, 궤적, 방위, 동작 패턴)
      - dynamics/: 동역학 (힘, 운동량, 에너지, 균형, 착지 충격)
      - data_extraction/: 내부 데이터 → DTO 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

사용 예시:
    >>> from biomechanics import create_body_model, BodyModel
    >>> model = create_body_model(body_mass_kg=75.0, height_cm=180.0)

    >>> from biomechanics import calculate_all_joint_angles, FrameAngles
    >>> angles = calculate_all_joint_angles(keypoints_3d)

    >>> from biomechanics import analyze_balance, BalanceState
    >>> state = analyze_balance(keypoints_3d, model)

    >>> from biomechanics import build_biomechanical_frame
    >>> frame = build_biomechanical_frame(0, 0.0, 1)
"""

from __future__ import annotations

import importlib
from typing import Any


__version__ = "1.0.0"

# =============================================================================
# 서브패키지 → 심볼 매핑 (Lazy Import)
#
# 총 심볼 수:
#   standards:        18 (region_types 10 + league_standards 8)
#   anthropometry:    45 (body_segment 20 + proportion 7 + age_gender 9 + personal 9)
#   kinematics:       42 (angle 12 + velocity 7 + accel 10 + trajectory 3 + orient 6 + motion 4)
#   dynamics:         37 (force 8 + momentum 6 + energy 6 + balance 9 + impact 8)
#   data_extraction:  20 (frame_extractor 12 + event_extractor 4 + sequence_extractor 4)
#   합계:           162
# =============================================================================

_SUBPACKAGE_MAP: dict[str, str] = {
    # === standards/ (18) ===
    # region_types (10)
    "LeagueType": "biomechanics.standards",
    "RegionType": "biomechanics.standards",
    "LeagueCourtSpec": "biomechanics.standards",
    "RegionBodyProfile": "biomechanics.standards",
    "LeagueAgeBoundary": "biomechanics.standards",
    "get_default_region": "biomechanics.standards",
    "get_age_boundary": "biomechanics.standards",
    "get_region_profile": "biomechanics.standards",
    "get_court_spec": "biomechanics.standards",
    "age_to_league_category": "biomechanics.standards",
    # league_standards (8)
    "BiomechanicsStandard": "biomechanics.standards",
    "get_standard": "biomechanics.standards",
    "get_standard_by_age": "biomechanics.standards",
    "get_velocity_threshold": "biomechanics.standards",
    "get_angle_tolerance": "biomechanics.standards",
    "get_severity_thresholds": "biomechanics.standards",
    "get_three_point_factor": "biomechanics.standards",
    "get_court_area_factor": "biomechanics.standards",

    # === anthropometry/ (40) ===
    # body_segment (20)
    "GRAVITY": "biomechanics.anthropometry",
    "DEFAULT_BODY_MASS": "biomechanics.anthropometry",
    "DEFAULT_HEIGHT": "biomechanics.anthropometry",
    "MIN_BODY_MASS": "biomechanics.anthropometry",
    "MAX_BODY_MASS": "biomechanics.anthropometry",
    "MIN_HEIGHT": "biomechanics.anthropometry",
    "MAX_HEIGHT": "biomechanics.anthropometry",
    "SegmentProperties": "biomechanics.anthropometry",
    "BodyModel": "biomechanics.anthropometry",
    "calculate_segment_mass": "biomechanics.anthropometry",
    "calculate_segment_length": "biomechanics.anthropometry",
    "calculate_segment_com_position": "biomechanics.anthropometry",
    "calculate_segment_moment_of_inertia": "biomechanics.anthropometry",
    "calculate_segment_properties": "biomechanics.anthropometry",
    "create_body_model": "biomechanics.anthropometry",
    "calculate_whole_body_com": "biomechanics.anthropometry",
    "calculate_segment_weight": "biomechanics.anthropometry",
    "estimate_body_mass_from_height": "biomechanics.anthropometry",
    "SEGMENT_ENDPOINT_INDICES_25KP": "biomechanics.anthropometry",
    "get_segment_endpoints_25kp": "biomechanics.anthropometry",
    # proportion_calculator (7)
    "MIN_VALID_DISTANCE_M": "biomechanics.anthropometry",
    "MAX_ASYMMETRY_RATIO": "biomechanics.anthropometry",
    "BodyProportions": "biomechanics.anthropometry",
    "SegmentLengths": "biomechanics.anthropometry",
    "calculate_segment_lengths": "biomechanics.anthropometry",
    "calculate_proportions": "biomechanics.anthropometry",
    "estimate_height_from_keypoints": "biomechanics.anthropometry",
    # age_gender_adapter (9)
    "AgeGenderProfile": "biomechanics.anthropometry",
    "create_age_gender_profile": "biomechanics.anthropometry",
    "create_adapted_body_model": "biomechanics.anthropometry",
    "get_default_body_params": "biomechanics.anthropometry",
    "adapt_angle_range": "biomechanics.anthropometry",
    "apply_velocity_factor": "biomechanics.anthropometry",
    "apply_rom_factor": "biomechanics.anthropometry",
    "is_within_adapted_range": "biomechanics.anthropometry",
    "calculate_deviation": "biomechanics.anthropometry",
    # personal_adapter (4)
    "STABILIZATION_WINDOW": "biomechanics.anthropometry",
    "MIN_SAMPLES_FOR_STABLE": "biomechanics.anthropometry",
    "SIGNIFICANT_DEVIATION_THRESHOLD": "biomechanics.anthropometry",
    "ProportionDeviation": "biomechanics.anthropometry",
    "PersonalProfile": "biomechanics.anthropometry",
    "create_personal_profile": "biomechanics.anthropometry",
    "calculate_proportion_deviation": "biomechanics.anthropometry",
    "has_significant_deviation": "biomechanics.anthropometry",
    "ProportionStabilizer": "biomechanics.anthropometry",

    # === kinematics/ (42) ===
    # joint_angle_calculator (12)
    "JointAngle": "biomechanics.kinematics",
    "FrameAngles": "biomechanics.kinematics",
    "AngleDeviation": "biomechanics.kinematics",
    "calculate_joint_angle": "biomechanics.kinematics",
    "calculate_all_joint_angles": "biomechanics.kinematics",
    "calculate_trunk_forward_lean": "biomechanics.kinematics",
    "calculate_stance_width_ratio": "biomechanics.kinematics",
    "evaluate_shooting_angles": "biomechanics.kinematics",
    "evaluate_defensive_stance": "biomechanics.kinematics",
    "evaluate_dribbling_stance": "biomechanics.kinematics",
    "evaluate_jump_landing": "biomechanics.kinematics",
    "get_bilateral_difference": "biomechanics.kinematics",
    # velocity_analyzer (7)
    "JointVelocity": "biomechanics.kinematics",
    "FrameVelocities": "biomechanics.kinematics",
    "calculate_joint_velocity": "biomechanics.kinematics",
    "calculate_central_velocity": "biomechanics.kinematics",
    "calculate_all_velocities": "biomechanics.kinematics",
    "calculate_body_speed": "biomechanics.kinematics",
    "classify_movement_intensity": "biomechanics.kinematics",
    # acceleration_analyzer (10)
    "JointAcceleration": "biomechanics.kinematics",
    "BodyAcceleration": "biomechanics.kinematics",
    "FrameAccelerations": "biomechanics.kinematics",
    "calculate_joint_acceleration": "biomechanics.kinematics",
    "calculate_position_acceleration": "biomechanics.kinematics",
    "calculate_body_acceleration": "biomechanics.kinematics",
    "calculate_all_accelerations": "biomechanics.kinematics",
    "detect_explosive_acceleration": "biomechanics.kinematics",
    "detect_hard_stop": "biomechanics.kinematics",
    "detect_direction_change": "biomechanics.kinematics",
    # trajectory_analyzer (3)
    "TrajectoryMetrics": "biomechanics.kinematics",
    "analyze_trajectory": "biomechanics.kinematics",
    "TrajectoryBuffer": "biomechanics.kinematics",
    # body_orientation (6)
    "BodyOrientation": "biomechanics.kinematics",
    "TrunkSeparation": "biomechanics.kinematics",
    "calculate_body_orientation": "biomechanics.kinematics",
    "calculate_trunk_separation": "biomechanics.kinematics",
    "calculate_facing_angle_to_target": "biomechanics.kinematics",
    "get_orientation_tuple": "biomechanics.kinematics",
    # motion_pattern (4)
    "PatternMatch": "biomechanics.kinematics",
    "MotionState": "biomechanics.kinematics",
    "detect_motion_patterns": "biomechanics.kinematics",
    "determine_phase_from_angles": "biomechanics.kinematics",

    # === dynamics/ (37) ===
    # force_estimator (8)
    "JointForce": "biomechanics.dynamics",
    "GroundReactionForce": "biomechanics.dynamics",
    "FrameForces": "biomechanics.dynamics",
    "calculate_joint_force": "biomechanics.dynamics",
    "estimate_ground_reaction_force": "biomechanics.dynamics",
    "estimate_vertical_com_acceleration": "biomechanics.dynamics",
    "calculate_all_forces": "biomechanics.dynamics",
    "classify_contact_force": "biomechanics.dynamics",
    # momentum_calculator (6)
    "SegmentMomentum": "biomechanics.dynamics",
    "FrameMomentum": "biomechanics.dynamics",
    "calculate_segment_momentum": "biomechanics.dynamics",
    "calculate_body_linear_momentum": "biomechanics.dynamics",
    "calculate_frame_momentum": "biomechanics.dynamics",
    "calculate_impulse": "biomechanics.dynamics",
    # energy_analyzer (6)
    "SegmentEnergy": "biomechanics.dynamics",
    "FrameEnergy": "biomechanics.dynamics",
    "calculate_segment_kinetic_energy": "biomechanics.dynamics",
    "calculate_potential_energy": "biomechanics.dynamics",
    "calculate_frame_energy": "biomechanics.dynamics",
    "calculate_energy_transfer_rate": "biomechanics.dynamics",
    # balance_analyzer (9)
    "BalanceState": "biomechanics.dynamics",
    "SwayMetrics": "biomechanics.dynamics",
    "calculate_com_position": "biomechanics.dynamics",
    "calculate_bos_area": "biomechanics.dynamics",
    "calculate_bos_width": "biomechanics.dynamics",
    "calculate_stability_index": "biomechanics.dynamics",
    "estimate_weight_distribution": "biomechanics.dynamics",
    "calculate_sway": "biomechanics.dynamics",
    "analyze_balance": "biomechanics.dynamics",
    # impact_analyzer (8)
    "LandingImpact": "biomechanics.dynamics",
    "ContactEvent": "biomechanics.dynamics",
    "classify_absorption_quality": "biomechanics.dynamics",
    "classify_injury_risk": "biomechanics.dynamics",
    "analyze_landing_impact": "biomechanics.dynamics",
    "analyze_contact_event": "biomechanics.dynamics",
    "is_landing_frame": "biomechanics.dynamics",
    "estimate_absorption_time": "biomechanics.dynamics",

    # === data_extraction/ (20) ===
    # frame_extractor (12)
    "extract_joint_kinematics": "biomechanics.data_extraction",
    "extract_joint_angles": "biomechanics.data_extraction",
    "extract_body_orientation": "biomechanics.data_extraction",
    "extract_all_kinematics": "biomechanics.data_extraction",
    "extract_balance_metrics": "biomechanics.data_extraction",
    "extract_energy_metrics": "biomechanics.data_extraction",
    "extract_force_estimate": "biomechanics.data_extraction",
    "extract_all_forces": "biomechanics.data_extraction",
    "extract_motion_pattern": "biomechanics.data_extraction",
    "extract_anthropometry": "biomechanics.data_extraction",
    "build_biomechanical_frame": "biomechanics.data_extraction",
    "build_biomechanical_result": "biomechanics.data_extraction",
    # event_extractor (4)
    "extract_landing_impact": "biomechanics.data_extraction",
    "extract_contact_event": "biomechanics.data_extraction",
    "extract_explosive_event": "biomechanics.data_extraction",
    "extract_direction_change": "biomechanics.data_extraction",
    # sequence_extractor (4)
    "extract_trajectory_summary": "biomechanics.data_extraction",
    "extract_momentum_profile": "biomechanics.data_extraction",
    "extract_energy_profile": "biomechanics.data_extraction",
    "extract_balance_history": "biomechanics.data_extraction",
}

__all__ = list(_SUBPACKAGE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import: 심볼 접근 시 해당 서브패키지를 통해 로드."""
    if name in _SUBPACKAGE_MAP:
        module = importlib.import_module(_SUBPACKAGE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module 'biomechanics' has no attribute {name!r}")
