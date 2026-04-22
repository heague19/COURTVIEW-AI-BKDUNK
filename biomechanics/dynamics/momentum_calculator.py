# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: momentum_calculator.py
설명: 운동량 (선형/각운동량) 계산 모듈
      - 선형 운동량: p = m·v
      - 각운동량: L = I·ω
      - 충격량: J = Δp (프레임 간 운동량 변화)
      - 세그먼트별 + 전신 운동량 산출

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.5.
    - Enoka, R.M. (2015). Neuromechanics of Human Movement, Ch.5.
    - 선형 운동량: p = m·v (kg·m/s)
    - 각운동량: L = I·ω (kg·m²/s)
    - 충격량-운동량 정리: J = F·Δt = Δp

의존성:
    - shared/constants/biomechanics_constants.py: BodySegment
    - shared/constants/pose_constants.py: JointType
    - biomechanics/anthropometry/body_segment.py: BodyModel, SegmentProperties
    - biomechanics/kinematics/velocity_analyzer.py: JointVelocity, FrameVelocities

사용처:
    - biomechanics/dynamics/energy_analyzer.py: 운동 에너지 = p²/(2m)
    - biomechanics/dynamics/impact_analyzer.py: 충격량 기반 충격 분석
    - ai_referee/: 접촉 시 운동량 교환으로 접촉 강도 판정
    - motion_analysis/: 동작 연쇄(kinetic chain) 분석
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from shared.constants.biomechanics_constants import BodySegment
from shared.constants.pose_constants import JointType

from biomechanics.anthropometry.body_segment import BodyModel
from biomechanics.kinematics.velocity_analyzer import (
    JointVelocity,
    FrameVelocities,
)


# =============================================================================
# 상수
# =============================================================================

# cm/s → m/s 변환 계수
_CM_TO_M: Final[float] = 0.01

# deg/s → rad/s 변환 계수
_DEG_TO_RAD: Final[float] = math.pi / 180.0

# 최대 선형 운동량 (kg·m/s) — 이상치 필터
# 120kg × 10m/s (전력질주) = 1200 kg·m/s
_MAX_LINEAR_MOMENTUM: Final[float] = 1500.0

# 최대 각운동량 (kg·m²/s) — 이상치 필터
_MAX_ANGULAR_MOMENTUM: Final[float] = 200.0

# 관절 → 원위 세그먼트 매핑 (force_estimator와 동일)
_JOINT_TO_DISTAL_SEGMENT: Final[dict[JointType, BodySegment]] = {
    JointType.RIGHT_SHOULDER: BodySegment.UPPER_ARM,
    JointType.RIGHT_ELBOW: BodySegment.FOREARM,
    JointType.RIGHT_WRIST: BodySegment.HAND,
    JointType.LEFT_SHOULDER: BodySegment.UPPER_ARM,
    JointType.LEFT_ELBOW: BodySegment.FOREARM,
    JointType.LEFT_WRIST: BodySegment.HAND,
    JointType.RIGHT_HIP: BodySegment.THIGH,
    JointType.RIGHT_KNEE: BodySegment.SHANK,
    JointType.RIGHT_ANKLE: BodySegment.FOOT,
    JointType.LEFT_HIP: BodySegment.THIGH,
    JointType.LEFT_KNEE: BodySegment.SHANK,
    JointType.LEFT_ANKLE: BodySegment.FOOT,
}


# =============================================================================
# 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class SegmentMomentum:
    """
    단일 세그먼트의 운동량.

    Attributes:
        joint_type: 관절 유형 (세그먼트 대리)
        linear_momentum: 선형 운동량 벡터 (px, py, pz) kg·m/s
        linear_magnitude: 선형 운동량 크기 kg·m/s
        angular_momentum: 각운동량 크기 kg·m²/s
    """

    joint_type: JointType
    linear_momentum: tuple[float, float, float]
    linear_magnitude: float
    angular_momentum: float


@dataclass(frozen=True, slots=True)
class FrameMomentum:
    """
    프레임 단위 전체 운동량.

    Attributes:
        segment_momenta: 관절별 세그먼트 운동량
        total_linear: 전신 선형 운동량 벡터 (px, py, pz) kg·m/s
        total_linear_magnitude: 전신 선형 운동량 크기 kg·m/s
        total_angular_magnitude: 전신 각운동량 크기 합 kg·m²/s
        body_momentum_magnitude: 전신 COM 기반 운동량 kg·m/s
    """

    segment_momenta: dict[JointType, SegmentMomentum]
    total_linear: tuple[float, float, float]
    total_linear_magnitude: float
    total_angular_magnitude: float
    body_momentum_magnitude: float


# =============================================================================
# 세그먼트 운동량 계산
# =============================================================================

def calculate_segment_momentum(
    joint_type: JointType,
    joint_vel: JointVelocity,
    body_model: BodyModel,
) -> SegmentMomentum | None:
    """
    단일 세그먼트의 선형/각운동량 계산.

    단일 세그먼트 근사:
    - p = m_segment × v_joint (선형 운동량)
    - L = I_segment × ω_joint (각운동량)

    Args:
        joint_type: 관절 유형
        joint_vel: 해당 관절의 속도 데이터 (cm/s, deg/s)
        body_model: 신체 모델

    Returns:
        SegmentMomentum 객체 (매핑 없을 시 None)

    참조:
        Winter (2009) Ch.5: Segmental momentum
        Enoka (2015) Ch.5: Angular momentum of body segments
    """
    segment_type = _JOINT_TO_DISTAL_SEGMENT.get(joint_type)
    if segment_type is None:
        return None

    props = body_model.segments.get(segment_type)
    if props is None:
        return None

    mass = props.mass_kg

    # 선형 운동량: p = m × v (cm/s → m/s)
    vx_m = joint_vel.velocity[0] * _CM_TO_M
    vy_m = joint_vel.velocity[1] * _CM_TO_M
    vz_m = joint_vel.velocity[2] * _CM_TO_M

    px = mass * vx_m
    py = mass * vy_m
    pz = mass * vz_m
    p_mag = (px ** 2 + py ** 2 + pz ** 2) ** 0.5

    # 이상치 필터 (세그먼트 단위)
    if p_mag > _MAX_LINEAR_MOMENTUM:
        return None

    # 각운동량: L = I × ω (deg/s → rad/s)
    omega_rad = joint_vel.angular_velocity * _DEG_TO_RAD
    angular_mom = props.moment_of_inertia * abs(omega_rad)

    if angular_mom > _MAX_ANGULAR_MOMENTUM:
        angular_mom = 0.0  # 이상치 시 무효화

    return SegmentMomentum(
        joint_type=joint_type,
        linear_momentum=(px, py, pz),
        linear_magnitude=p_mag,
        angular_momentum=angular_mom,
    )


# =============================================================================
# 전신 운동량 계산
# =============================================================================

def calculate_body_linear_momentum(
    body_mass_kg: float,
    body_speed_m_s: float,
) -> float:
    """
    전신 선형 운동량 크기 계산 (COM 기반).

    p = m_body × v_body (스칼라)

    Args:
        body_mass_kg: 체질량 (kg)
        body_speed_m_s: 체 중심 속력 (m/s)

    Returns:
        전신 선형 운동량 크기 (kg·m/s)

    참조:
        Newton 제2법칙: 전신 운동량 = 질량 × COM 속도
    """
    if body_mass_kg <= 0 or body_speed_m_s < 0:
        return 0.0

    momentum = body_mass_kg * body_speed_m_s

    if momentum > _MAX_LINEAR_MOMENTUM:
        return 0.0

    return momentum


def calculate_frame_momentum(
    body_model: BodyModel,
    frame_velocities: FrameVelocities,
) -> FrameMomentum:
    """
    프레임 단위 전체 운동량 계산.

    세그먼트별 운동량을 산출하고 전신 합산.

    Args:
        body_model: 신체 모델
        frame_velocities: 프레임 속도 데이터

    Returns:
        FrameMomentum 객체
    """
    segment_momenta: dict[JointType, SegmentMomentum] = {}

    for joint_type, vel in frame_velocities.joint_velocities.items():
        momentum = calculate_segment_momentum(joint_type, vel, body_model)
        if momentum is not None:
            segment_momenta[joint_type] = momentum

    # 세그먼트 합산 (벡터 합)
    total_px = sum(sm.linear_momentum[0] for sm in segment_momenta.values())
    total_py = sum(sm.linear_momentum[1] for sm in segment_momenta.values())
    total_pz = sum(sm.linear_momentum[2] for sm in segment_momenta.values())
    total_mag = (total_px ** 2 + total_py ** 2 + total_pz ** 2) ** 0.5

    total_angular = sum(sm.angular_momentum for sm in segment_momenta.values())

    # 전신 COM 기반 운동량
    body_mom = calculate_body_linear_momentum(
        body_model.body_mass_kg,
        frame_velocities.body_speed_m_s,
    )

    return FrameMomentum(
        segment_momenta=segment_momenta,
        total_linear=(total_px, total_py, total_pz),
        total_linear_magnitude=total_mag,
        total_angular_magnitude=total_angular,
        body_momentum_magnitude=body_mom,
    )


# =============================================================================
# 충격량 (운동량 변화)
# =============================================================================

def calculate_impulse(
    momentum_prev: FrameMomentum,
    momentum_curr: FrameMomentum,
) -> float:
    """
    프레임 간 충격량 계산 (선형 운동량 변화).

    J = Δp = p_curr - p_prev (벡터 차의 크기)

    충격량은 힘의 시간 적분: J = ∫F dt ≈ F_avg × Δt
    운동량 변화가 클수록 큰 힘이 작용했음을 의미합니다.

    Args:
        momentum_prev: 이전 프레임 운동량
        momentum_curr: 현재 프레임 운동량

    Returns:
        충격량 크기 (kg·m/s, = N·s)

    참조:
        충격량-운동량 정리: J = Δp = F·Δt
        Enoka (2015) Ch.5: Impulse-momentum relationship
    """
    dpx = momentum_curr.total_linear[0] - momentum_prev.total_linear[0]
    dpy = momentum_curr.total_linear[1] - momentum_prev.total_linear[1]
    dpz = momentum_curr.total_linear[2] - momentum_prev.total_linear[2]

    return (dpx ** 2 + dpy ** 2 + dpz ** 2) ** 0.5


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "SegmentMomentum",
    "FrameMomentum",
    # 세그먼트 운동량
    "calculate_segment_momentum",
    # 전신 운동량
    "calculate_body_linear_momentum",
    "calculate_frame_momentum",
    # 충격량
    "calculate_impulse",
]

__version__ = "1.0.0"
