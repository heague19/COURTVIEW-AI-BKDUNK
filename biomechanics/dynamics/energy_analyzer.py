# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: energy_analyzer.py
설명: 에너지 분석 모듈
      - 운동 에너지: KE = ½mv² (선형) + ½Iω² (회전)
      - 위치 에너지: PE = mgh (COM 높이 기반)
      - 총 에너지: E = KE + PE
      - 에너지 전달률: P = ΔE/Δt (와트)
      - 탄성 에너지 추정: 점프 착지 시 건/관절 저장분

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.6.
    - Robertson, D.G.E. et al. (2014). Research Methods in Biomechanics, Ch.5.
    - 운동 에너지: KE_linear = ½mv², KE_rotational = ½Iω²
    - 위치 에너지: PE = mgh (중력장)
    - 에너지 보존: E_total = KE + PE (보존계 기준)

의존성:
    - shared/constants/biomechanics_constants.py: BodySegment, 에너지 임계치
    - shared/constants/pose_constants.py: JointType
    - biomechanics/anthropometry/body_segment.py: BodyModel, GRAVITY
    - biomechanics/kinematics/velocity_analyzer.py: JointVelocity, FrameVelocities

사용처:
    - biomechanics/dynamics/impact_analyzer.py: 착지 에너지 분석
    - biomechanics/data_extraction/: EnergyMetrics DTO 생성
    - motion_analysis/: 고에너지 프레임 감지 (슛 릴리스, 점프)
    - feedback_system/: 에너지 효율성 피드백
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    BodySegment,
    HIGH_ENERGY_KINETIC_THRESHOLD_J,
)
from shared.constants.pose_constants import (
    JointType,
    UK25_NECK,
    UK25_R_HIP,
    UK25_L_HIP,
    UK25_R_ANKLE,
    UK25_L_ANKLE,
)

from biomechanics.anthropometry.body_segment import (
    BodyModel,
    GRAVITY,
)
from biomechanics.kinematics.velocity_analyzer import (
    JointVelocity,
    FrameVelocities,
)


# =============================================================================
# 상수
# =============================================================================

# cm/s → m/s 변환
_CM_TO_M: Final[float] = 0.01

# deg/s → rad/s 변환
_DEG_TO_RAD: Final[float] = math.pi / 180.0

# 최소 시간 간격 (0-division 방지)
_MIN_DT: Final[float] = 1e-6

# 최대 운동 에너지 (J) — 이상치 필터
# 120kg × (10m/s)² / 2 = 6000J (이론 상한)
_MAX_KINETIC_ENERGY_J: Final[float] = 10000.0

# 최대 에너지 전달률 (W) — 이상치 필터
# 프로 선수 순간 파워 ~5000W (점프 이륙)
_MAX_POWER_W: Final[float] = 8000.0

# COM 프록시 인덱스 (SSOT): 목 + 양쪽 골반 3점 평균
_COM_PROXY_INDICES: Final[tuple[int, ...]] = (UK25_NECK, UK25_R_HIP, UK25_L_HIP)

# COM 참조 높이: 발목 (지면 기준 높이 계산용)
_ANKLE_INDICES: Final[tuple[int, int]] = (UK25_R_ANKLE, UK25_L_ANKLE)

# 탄성 에너지 비율 (착지 시 건/관절이 흡수하는 에너지 비율)
# 참조: Farris & Sawicki (2012): 아킬레스건 탄성 에너지 ~35%
_ELASTIC_ENERGY_RATIO: Final[float] = 0.35

# 관절 → 원위 세그먼트 매핑
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
class SegmentEnergy:
    """
    단일 세그먼트의 에너지.

    Attributes:
        joint_type: 관절 유형 (세그먼트 대리)
        kinetic_linear_j: 선형 운동 에너지 ½mv² (J)
        kinetic_rotational_j: 회전 운동 에너지 ½Iω² (J)
        kinetic_total_j: 총 운동 에너지 (J)
    """

    joint_type: JointType
    kinetic_linear_j: float
    kinetic_rotational_j: float
    kinetic_total_j: float


@dataclass(frozen=True, slots=True)
class FrameEnergy:
    """
    프레임 단위 에너지 분석 결과.

    Attributes:
        segment_energies: 세그먼트별 에너지
        kinetic_energy_j: 전신 운동 에너지 합계 (J)
        potential_energy_j: 전신 위치 에너지 (J, COM 높이 기반)
        total_energy_j: 총 에너지 (J)
        elastic_energy_j: 탄성 에너지 추정 (J)
        is_high_energy: 고에너지 프레임 여부
    """

    segment_energies: dict[JointType, SegmentEnergy]
    kinetic_energy_j: float
    potential_energy_j: float
    total_energy_j: float
    elastic_energy_j: float
    is_high_energy: bool


# =============================================================================
# 세그먼트 운동 에너지
# =============================================================================

def calculate_segment_kinetic_energy(
    joint_type: JointType,
    joint_vel: JointVelocity,
    body_model: BodyModel,
) -> SegmentEnergy | None:
    """
    단일 세그먼트의 운동 에너지 계산.

    KE_linear = ½ × m × v² (선형)
    KE_rotational = ½ × I × ω² (회전)

    Args:
        joint_type: 관절 유형
        joint_vel: 관절 속도 데이터 (cm/s, deg/s)
        body_model: 신체 모델

    Returns:
        SegmentEnergy 객체 (매핑 없을 시 None)

    참조:
        Winter (2009) Ch.6: Mechanical energy of body segments
    """
    segment_type = _JOINT_TO_DISTAL_SEGMENT.get(joint_type)
    if segment_type is None:
        return None

    props = body_model.segments.get(segment_type)
    if props is None:
        return None

    # 선형 운동 에너지: KE = ½mv²
    speed_m_s = joint_vel.speed * _CM_TO_M
    ke_linear = 0.5 * props.mass_kg * speed_m_s ** 2

    # 회전 운동 에너지: KE = ½Iω²
    omega_rad = joint_vel.angular_velocity * _DEG_TO_RAD
    ke_rotational = 0.5 * props.moment_of_inertia * omega_rad ** 2

    ke_total = ke_linear + ke_rotational

    # 이상치 필터
    if ke_total > _MAX_KINETIC_ENERGY_J:
        return None

    return SegmentEnergy(
        joint_type=joint_type,
        kinetic_linear_j=ke_linear,
        kinetic_rotational_j=ke_rotational,
        kinetic_total_j=ke_total,
    )


# =============================================================================
# 위치 에너지
# =============================================================================

def calculate_potential_energy(
    body_mass_kg: float,
    keypoints_3d: NDArray[np.float64],
) -> float:
    """
    전신 위치 에너지 계산 (COM 높이 기반).

    PE = m × g × h_com
    h_com: COM 프록시 높이 - 발목(지면 기준) 높이

    Args:
        body_mass_kg: 체질량 (kg)
        keypoints_3d: 키포인트 3D 좌표 (25×3/4, cm 단위)

    Returns:
        위치 에너지 (J), 계산 불가 시 0.0

    참조:
        Winter (2009): 중력 위치 에너지
    """
    if body_mass_kg <= 0:
        return 0.0

    min_rows = max(max(_COM_PROXY_INDICES), max(_ANKLE_INDICES)) + 1
    if keypoints_3d.shape[0] < min_rows:
        return 0.0

    # COM 프록시 높이 (y좌표)
    com_y = 0.0
    for idx in _COM_PROXY_INDICES:
        com_y += float(keypoints_3d[idx, 1])
    com_y /= len(_COM_PROXY_INDICES)

    # 지면 기준 (발목 평균 높이)
    ground_y = 0.0
    for idx in _ANKLE_INDICES:
        ground_y += float(keypoints_3d[idx, 1])
    ground_y /= len(_ANKLE_INDICES)

    # COM 높이 (cm → m)
    h_m = (com_y - ground_y) * _CM_TO_M

    # 음의 높이는 0으로 (발목 아래 = 지면)
    if h_m < 0:
        h_m = 0.0

    return body_mass_kg * GRAVITY * h_m


# =============================================================================
# 프레임 에너지 일괄 계산
# =============================================================================

def calculate_frame_energy(
    body_model: BodyModel,
    frame_velocities: FrameVelocities,
    keypoints_3d: NDArray[np.float64] | None = None,
) -> FrameEnergy:
    """
    프레임 단위 전체 에너지 계산.

    Args:
        body_model: 신체 모델
        frame_velocities: 프레임 속도 데이터
        keypoints_3d: 현재 프레임 키포인트 (위치 에너지용, 선택)

    Returns:
        FrameEnergy 객체
    """
    segment_energies: dict[JointType, SegmentEnergy] = {}

    for joint_type, vel in frame_velocities.joint_velocities.items():
        energy = calculate_segment_kinetic_energy(joint_type, vel, body_model)
        if energy is not None:
            segment_energies[joint_type] = energy

    # 세그먼트 개별 KE 합 (각 세그먼트의 절대속도 기반 ½m_i v_i² + ½I_i ω_i²)
    ke_segments = sum(se.kinetic_total_j for se in segment_energies.values())
    # 전신 COM 병진 KE = ½ M v_COM²
    body_com_ke = 0.5 * body_model.body_mass_kg * frame_velocities.body_speed_m_s ** 2

    # König 정리: Σ½m_i v_i² = ½M v_COM² + Σ½m_i |v_i - v_COM|²
    # 좌변(절대속도 기반 합) = 우변(COM 병진 + 상대운동)
    #
    # ke_segments 는 "전체 세그먼트에 대한 좌변"이며, 이미 König 합계 그 자체.
    # body_com_ke 는 그 중 COM 병진 성분만.
    # 따라서 전체 에너지 = ke_segments (세그먼트 데이터 완전 시).
    # 세그먼트 데이터가 불완전할 때만 body_com_ke 가 하한선으로 작용.
    ke_total = max(ke_segments, body_com_ke)

    # 위치 에너지
    pe = 0.0
    if keypoints_3d is not None:
        pe = calculate_potential_energy(body_model.body_mass_kg, keypoints_3d)

    total = ke_total + pe

    # 탄성 에너지 추정 (운동 에너지 기반)
    # 착지/감속 시 건/관절이 흡수하는 에너지
    elastic = ke_total * _ELASTIC_ENERGY_RATIO

    is_high = ke_total > HIGH_ENERGY_KINETIC_THRESHOLD_J

    return FrameEnergy(
        segment_energies=segment_energies,
        kinetic_energy_j=ke_total,
        potential_energy_j=pe,
        total_energy_j=total,
        elastic_energy_j=elastic,
        is_high_energy=is_high,
    )


# =============================================================================
# 에너지 전달률 (파워)
# =============================================================================

def calculate_energy_transfer_rate(
    energy_prev: FrameEnergy,
    energy_curr: FrameEnergy,
    dt: float,
) -> float:
    """
    에너지 전달률 (파워) 계산.

    P = ΔE / Δt (W)

    양의 값: 에너지 증가 (근육이 에너지 생성)
    음의 값: 에너지 감소 (에너지 흡수/소산)

    Args:
        energy_prev: 이전 프레임 에너지
        energy_curr: 현재 프레임 에너지
        dt: 시간 간격 (초)

    Returns:
        에너지 전달률 (W), 이상치/dt 부족 시 0.0

    참조:
        Robertson et al. (2014) Ch.5: Joint power analysis
    """
    if dt < _MIN_DT:
        return 0.0

    delta_e = energy_curr.total_energy_j - energy_prev.total_energy_j
    power = delta_e / dt

    if abs(power) > _MAX_POWER_W:
        return 0.0

    return power


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "SegmentEnergy",
    "FrameEnergy",
    # 세그먼트 에너지
    "calculate_segment_kinetic_energy",
    # 위치 에너지
    "calculate_potential_energy",
    # 일괄 계산
    "calculate_frame_energy",
    # 에너지 전달률
    "calculate_energy_transfer_rate",
]

__version__ = "1.0.0"
