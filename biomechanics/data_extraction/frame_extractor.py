# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/data_extraction
파일: frame_extractor.py
설명: 프레임 단위 생체역학 내부 데이터 → DTO 변환 모듈
      - kinematics 내부 데이터클래스 → JointKinematics DTO
      - dynamics 내부 데이터클래스 → BalanceMetrics, EnergyMetrics, ForceEstimate DTO
      - anthropometry 내부 데이터클래스 → AnthropometryData DTO
      - 관절 각도/방위/배치 변환
      - 프레임/시퀀스 단위 종합 조립: BiomechanicalFrame, BiomechanicalResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/biomechanics_dto.py: 출력 DTO 인터페이스 정의
    - biomechanics/kinematics/: 내부 운동학 데이터
    - biomechanics/dynamics/: 내부 동역학 데이터
    - biomechanics/anthropometry/: 내부 인체측정 데이터

의존성:
    - shared/dto/biomechanics_dto.py: 모든 DTO 클래스
    - shared/constants/pose_constants.py: JointType
    - shared/constants/biomechanics_constants.py: BodySegment
    - biomechanics/kinematics/: JointVelocity, JointAcceleration, FrameAngles 등
    - biomechanics/dynamics/: JointForce, BalanceState, FrameEnergy, FrameForces 등
    - biomechanics/anthropometry/: BodyModel, BodyProportions 등

사용처:
    - motion_analysis/: BiomechanicalFrame 소비
    - game_analysis/: BiomechanicalResult 소비
    - feedback_system/: 피드백 생성 시 참조
    - api_server/: API 응답 직렬화
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.constants.biomechanics_constants import BodySegment
from shared.constants.pose_constants import JointType
from shared.dto.biomechanics_dto import (
    AnthropometryData,
    BalanceMetrics,
    BiomechanicalFrame,
    BiomechanicalResult,
    BodySegmentData,
    EnergyMetrics,
    ForceEstimate,
    JointKinematics,
    MotionPatternData,
)

if TYPE_CHECKING:
    from biomechanics.anthropometry.body_segment import BodyModel
    from biomechanics.anthropometry.proportion_calculator import BodyProportions
    from biomechanics.dynamics.balance_analyzer import BalanceState, SwayMetrics
    from biomechanics.dynamics.energy_analyzer import FrameEnergy
    from biomechanics.dynamics.force_estimator import FrameForces, JointForce
    from biomechanics.kinematics.acceleration_analyzer import (
        FrameAccelerations,
        JointAcceleration,
    )
    from biomechanics.kinematics.body_orientation import BodyOrientation
    from biomechanics.kinematics.joint_angle_calculator import FrameAngles
    from biomechanics.kinematics.motion_pattern import MotionState
    from biomechanics.kinematics.velocity_analyzer import (
        FrameVelocities,
        JointVelocity,
    )


# =============================================================================
# 운동학 변환 (개별)
# =============================================================================

def extract_joint_kinematics(
    joint_vel: JointVelocity,
    joint_accel: JointAcceleration | None = None,
) -> JointKinematics:
    """
    kinematics 내부 속도/가속도 → JointKinematics DTO 변환.

    Args:
        joint_vel: 관절 속도 (kinematics 내부)
        joint_accel: 관절 가속도 (kinematics 내부, 선택)

    Returns:
        JointKinematics DTO
    """
    accel_tuple = (0.0, 0.0, 0.0)
    angular_accel = 0.0

    if joint_accel is not None:
        accel_tuple = joint_accel.acceleration
        angular_accel = joint_accel.angular_acceleration

    return JointKinematics(
        joint_type=joint_vel.joint_type,
        velocity=joint_vel.velocity,
        speed=joint_vel.speed,
        acceleration=accel_tuple,
        angular_velocity=joint_vel.angular_velocity,
        angular_acceleration=angular_accel,
    )


def extract_joint_angles(
    frame_angles: FrameAngles,
) -> dict[JointType, float]:
    """
    kinematics 내부 FrameAngles → dict[JointType, float] 변환.

    FrameAngles.angles는 dict[JointType, JointAngle] 형태이며,
    각 JointAngle.angle_deg (도) 값을 추출하여 BiomechanicalFrame의
    joint_angles 필드에 사용할 수 있는 dict로 변환한다.

    Args:
        frame_angles: 프레임 단위 관절 각도 결과 (kinematics 내부)

    Returns:
        관절별 각도 dict (도 단위)
    """
    return {
        joint_type: joint_angle.angle_deg
        for joint_type, joint_angle in frame_angles.angles.items()
    }


def extract_body_orientation(
    orientation: BodyOrientation,
) -> tuple[float, float, float]:
    """
    kinematics 내부 BodyOrientation → (roll, pitch, yaw) 튜플 변환.

    BiomechanicalFrame의 body_orientation 필드에 직접 대입 가능한
    (roll_deg, pitch_deg, yaw_deg) 튜플을 반환한다.

    Args:
        orientation: 몸체 방위 분석 결과 (kinematics 내부)

    Returns:
        (roll_deg, pitch_deg, yaw_deg) 튜플
    """
    return (orientation.roll_deg, orientation.pitch_deg, orientation.yaw_deg)


# =============================================================================
# 운동학 배치 변환
# =============================================================================

def extract_all_kinematics(
    frame_velocities: FrameVelocities,
    frame_accelerations: FrameAccelerations | None = None,
) -> dict[JointType, JointKinematics]:
    """
    프레임 단위 전체 관절 속도/가속도 → dict[JointType, JointKinematics] 배치 변환.

    FrameVelocities의 모든 관절에 대해 extract_joint_kinematics를 적용하고,
    FrameAccelerations가 있으면 관절별로 매칭하여 가속도를 포함한다.

    Args:
        frame_velocities: 프레임 단위 전체 관절 속도 (kinematics 내부)
        frame_accelerations: 프레임 단위 전체 관절 가속도 (선택)

    Returns:
        관절별 JointKinematics DTO dict
    """
    accel_map: dict[JointType, JointAcceleration] = {}
    if frame_accelerations is not None:
        accel_map = frame_accelerations.joint_accelerations

    result: dict[JointType, JointKinematics] = {}
    for joint_type, joint_vel in frame_velocities.joint_velocities.items():
        joint_accel = accel_map.get(joint_type)
        result[joint_type] = extract_joint_kinematics(joint_vel, joint_accel)

    return result


# =============================================================================
# 동역학 변환 (개별)
# =============================================================================

def extract_balance_metrics(
    balance: BalanceState,
    sway: SwayMetrics | None = None,
) -> BalanceMetrics:
    """
    dynamics 내부 BalanceState → BalanceMetrics DTO 변환.

    Args:
        balance: 균형 분석 결과 (dynamics 내부)
        sway: 동요 분석 결과 (선택)

    Returns:
        BalanceMetrics DTO
    """
    sway_vel = sway.sway_velocity_cm_s if sway is not None else 0.0

    return BalanceMetrics(
        center_of_mass=balance.com_position,
        base_of_support_area=balance.bos_area_cm2,
        stability_index=balance.stability_index,
        sway_velocity=sway_vel,
        weight_distribution=balance.weight_distribution,
    )


def extract_energy_metrics(
    frame_energy: FrameEnergy,
    energy_transfer_rate: float = 0.0,
) -> EnergyMetrics:
    """
    dynamics 내부 FrameEnergy → EnergyMetrics DTO 변환.

    Args:
        frame_energy: 에너지 분석 결과 (dynamics 내부)
        energy_transfer_rate: 에너지 전달률 W (선택)

    Returns:
        EnergyMetrics DTO
    """
    return EnergyMetrics(
        kinetic_energy=frame_energy.kinetic_energy_j,
        potential_energy=frame_energy.potential_energy_j,
        total_energy=frame_energy.total_energy_j,
        energy_transfer_rate=energy_transfer_rate,
        elastic_energy=frame_energy.elastic_energy_j,
    )


def extract_force_estimate(joint_force: JointForce) -> ForceEstimate:
    """
    dynamics 내부 JointForce → ForceEstimate DTO 변환.

    Args:
        joint_force: 관절 힘 추정 (dynamics 내부)

    Returns:
        ForceEstimate DTO
    """
    return ForceEstimate(
        joint_type=joint_force.joint_type,
        force_vector=joint_force.force_vector,
        magnitude=joint_force.magnitude,
        torque=joint_force.torque_nm,
    )


# =============================================================================
# 동역학 배치 변환
# =============================================================================

def extract_all_forces(
    frame_forces: FrameForces,
) -> list[ForceEstimate]:
    """
    프레임 단위 전체 관절 힘 → list[ForceEstimate] 배치 변환.

    FrameForces의 모든 관절에 대해 extract_force_estimate를 적용하여
    BiomechanicalFrame의 forces 필드에 사용할 수 있는 리스트를 반환한다.

    Args:
        frame_forces: 프레임 단위 모든 힘 데이터 (dynamics 내부)

    Returns:
        ForceEstimate DTO 리스트
    """
    return [
        extract_force_estimate(joint_force)
        for joint_force in frame_forces.joint_forces.values()
    ]


# =============================================================================
# 동작 패턴 변환
# =============================================================================

def extract_motion_pattern(
    motion_state: MotionState,
) -> MotionPatternData | None:
    """
    kinematics 내부 MotionState → MotionPatternData DTO 변환.

    Args:
        motion_state: 동작 패턴 분석 결과 (kinematics 내부)

    Returns:
        MotionPatternData DTO (패턴 미감지 시 None)
    """
    primary = motion_state.primary_pattern
    if primary is None:
        return None

    return MotionPatternData(
        pattern_type=primary.pattern_type,
        phase=primary.phase,
        confidence=primary.confidence,
    )


# =============================================================================
# 인체측정 변환
# =============================================================================

def extract_anthropometry(
    body_model: BodyModel,
    proportions: BodyProportions | None = None,
) -> AnthropometryData:
    """
    anthropometry 내부 BodyModel → AnthropometryData DTO 변환.

    Args:
        body_model: 신체 모델 (anthropometry 내부)
        proportions: 신체 비율 (선택)

    Returns:
        AnthropometryData DTO
    """
    # 세그먼트 데이터 변환
    segments: list[BodySegmentData] = []
    for seg_type, props in body_model.segments.items():
        segments.append(BodySegmentData(
            segment_name=seg_type.name.lower(),
            length_cm=props.length_m * 100.0,  # m → cm
            mass_ratio=props.mass_kg / body_model.body_mass_kg if body_model.body_mass_kg > 0 else 0.0,
            center_of_mass_offset=props.com_proximal_ratio,
            inertia_estimate=props.moment_of_inertia,
        ))

    # 비율 데이터
    arm_span = 0.0
    shoulder_width = 0.0
    torso_length = 0.0
    leg_length = 0.0

    if proportions is not None:
        arm_span = proportions.wingspan_m * 100.0
        shoulder_width = proportions.shoulder_width_m * 100.0
        torso_length = proportions.upper_body_m * 100.0
        leg_length = proportions.lower_body_m * 100.0

    return AnthropometryData(
        height_cm=body_model.height_cm,
        weight_kg=body_model.body_mass_kg,
        arm_span_cm=arm_span,
        shoulder_width_cm=shoulder_width,
        torso_length_cm=torso_length,
        leg_length_cm=leg_length,
        segments=segments,
    )


# =============================================================================
# 프레임/결과 조립
# =============================================================================

def build_biomechanical_frame(
    frame_index: int,
    timestamp: float,
    person_id: int,
    joint_kinematics: dict[JointType, JointKinematics] | None = None,
    joint_angles: dict[JointType, float] | None = None,
    balance: BalanceMetrics | None = None,
    energy: EnergyMetrics | None = None,
    forces: list[ForceEstimate] | None = None,
    motion_pattern: MotionPatternData | None = None,
    body_orientation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> BiomechanicalFrame:
    """
    BiomechanicalFrame DTO 조립.

    각 변환 함수(extract_*)의 출력을 받아
    프레임 단위 종합 결과를 구성합니다.

    Args:
        frame_index: 프레임 번호
        timestamp: 타임스탬프 (초)
        person_id: 선수 ID
        joint_kinematics: 관절별 운동학 DTO
        joint_angles: 관절별 각도 (도)
        balance: 균형 지표 DTO
        energy: 에너지 지표 DTO
        forces: 관절별 힘 추정 DTO 리스트
        motion_pattern: 동작 패턴 DTO
        body_orientation: 몸체 방위 (roll, pitch, yaw) 도

    Returns:
        BiomechanicalFrame DTO
    """
    return BiomechanicalFrame(
        frame_index=frame_index,
        timestamp=timestamp,
        person_id=person_id,
        joint_kinematics=joint_kinematics if joint_kinematics is not None else {},
        joint_angles=joint_angles if joint_angles is not None else {},
        balance=balance,
        energy=energy,
        forces=forces if forces is not None else [],
        motion_pattern=motion_pattern,
        body_orientation=body_orientation,
    )


def build_biomechanical_result(
    person_id: int,
    frames: list[BiomechanicalFrame],
    anthropometry: AnthropometryData | None = None,
    processing_time_ms: float = 0.0,
) -> BiomechanicalResult:
    """
    BiomechanicalResult DTO 조립.

    여러 프레임 결과를 종합하여 시퀀스 단위 최종 결과를 생성합니다.

    Args:
        person_id: 선수 ID
        frames: 프레임별 분석 결과 리스트
        anthropometry: 인체측정 데이터 DTO (선택)
        processing_time_ms: 처리 시간 (ms)

    Returns:
        BiomechanicalResult DTO
    """
    return BiomechanicalResult(
        person_id=person_id,
        anthropometry=anthropometry,
        frames=frames,
        processing_time_ms=processing_time_ms,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 운동학 변환 (개별)
    "extract_joint_kinematics",
    "extract_joint_angles",
    "extract_body_orientation",
    # 운동학 배치 변환
    "extract_all_kinematics",
    # 동역학 변환 (개별)
    "extract_balance_metrics",
    "extract_energy_metrics",
    "extract_force_estimate",
    # 동역학 배치 변환
    "extract_all_forces",
    # 동작 패턴 변환
    "extract_motion_pattern",
    # 인체측정 변환
    "extract_anthropometry",
    # 조립
    "build_biomechanical_frame",
    "build_biomechanical_result",
]

__version__ = "1.0.0"
