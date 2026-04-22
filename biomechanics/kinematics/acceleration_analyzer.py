# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: acceleration_analyzer.py
설명: 관절 가속도/각가속도 분석 모듈
      - 속도 데이터 기반 유한차분법 가속도 산출 (cm/s²)
      - 각속도 변화율 기반 각가속도 산출 (deg/s²)
      - 폭발적 가속/급제동 감지
      - 방향 전환 가속도 분류

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.3.
    - 가속도: a(t) = [v(t+dt) - v(t)] / dt
    - 중앙차분: a(t) = [x(t+dt) - 2·x(t) + x(t-dt)] / dt²
    - NBA/FIBA 트래킹 데이터 기반 가속도 임계치

의존성:
    - shared/constants/biomechanics_constants.py: 가속도 임계치 상수
    - shared/constants/pose_constants.py: JointType
    - biomechanics/kinematics/velocity_analyzer.py: JointVelocity, FrameVelocities

사용처:
    - biomechanics/dynamics/force_estimator.py: F = m·a 기반 힘 추정
    - biomechanics/kinematics/motion_pattern.py: 급가속/급감속 패턴 감지
    - motion_analysis/detection/: 방향 전환, 풀업 점퍼 감지
    - ai_referee/: 접촉 시 가속도 변화로 접촉 강도 판정
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    ACCELERATION_NORMAL_MIN,
    ACCELERATION_NORMAL_MAX,
    ACCELERATION_QUICK_MIN,
    ACCELERATION_QUICK_MAX,
    ACCELERATION_EXPLOSIVE_THRESHOLD,
    DECELERATION_HARD_STOP_THRESHOLD,
)
from shared.constants.pose_constants import JointType

from biomechanics.kinematics.velocity_analyzer import (
    JointVelocity,
    FrameVelocities,
)


# =============================================================================
# 상수
# =============================================================================

# 최소 시간 간격 (0-division 방지)
_MIN_DT: Final[float] = 1e-6

# 가속도 이상치 상한 (cm/s²)
# 인체 관절 최대 가속도 ~5000cm/s² (스냅 동작)
_MAX_JOINT_ACCEL_CM_S2: Final[float] = 8000.0

# 각가속도 이상치 상한 (deg/s²)
_MAX_ANGULAR_ACCEL_DEG_S2: Final[float] = 50000.0

# 체 중심 가속도 이상치 상한 (m/s²)
# 최대 인체 가속도 ~15m/s² (단거리 스프린트 출발)
_MAX_BODY_ACCEL_M_S2: Final[float] = 20.0


# =============================================================================
# 가속도 결과 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class JointAcceleration:
    """
    단일 관절의 가속도 데이터.

    Attributes:
        joint_type: 관절 유형
        acceleration: 가속도 벡터 (ax, ay, az) cm/s²
        magnitude: 가속도 크기 cm/s²
        angular_acceleration: 각가속도 deg/s²
    """

    joint_type: JointType
    acceleration: tuple[float, float, float]
    magnitude: float
    angular_acceleration: float


@dataclass(frozen=True, slots=True)
class BodyAcceleration:
    """
    선수 체 중심 가속도 데이터.

    Attributes:
        acceleration_m_s2: 가속도 크기 (m/s²)
        acceleration_category: 가속도 분류
        is_accelerating: 양의 가속 여부
        direction_change_deg: 이동 방향 변화각 (도, 0=직진)
    """

    acceleration_m_s2: float
    acceleration_category: str
    is_accelerating: bool
    direction_change_deg: float


@dataclass(frozen=True, slots=True)
class FrameAccelerations:
    """
    프레임 단위 모든 가속도.

    Attributes:
        joint_accelerations: 관절별 가속도
        body_acceleration: 선수 체 중심 가속도
        dt: 프레임 간 시간 간격 (초)
    """

    joint_accelerations: dict[JointType, JointAcceleration]
    body_acceleration: BodyAcceleration | None
    dt: float

    @property
    def max_joint_acceleration(self) -> float:
        """최대 관절 가속도 크기 (cm/s²)."""
        if not self.joint_accelerations:
            return 0.0
        return max(ja.magnitude for ja in self.joint_accelerations.values())


# =============================================================================
# 핵심 가속도 계산 함수
# =============================================================================

def calculate_joint_acceleration(
    vel_prev: JointVelocity,
    vel_curr: JointVelocity,
    dt: float,
) -> JointAcceleration | None:
    """
    속도 차분 기반 관절 가속도 계산.

    a = (v_curr - v_prev) / dt

    Args:
        vel_prev: 이전 프레임 관절 속도
        vel_curr: 현재 프레임 관절 속도
        dt: 시간 간격 (초)

    Returns:
        JointAcceleration 객체 (이상치 시 None)
    """
    if dt < _MIN_DT:
        return None

    if vel_prev.joint_type != vel_curr.joint_type:
        return None

    # 선가속도
    ax = (vel_curr.velocity[0] - vel_prev.velocity[0]) / dt
    ay = (vel_curr.velocity[1] - vel_prev.velocity[1]) / dt
    az = (vel_curr.velocity[2] - vel_prev.velocity[2]) / dt
    magnitude = (ax ** 2 + ay ** 2 + az ** 2) ** 0.5

    if magnitude > _MAX_JOINT_ACCEL_CM_S2:
        return None

    # 각가속도
    angular_accel = abs(vel_curr.angular_velocity - vel_prev.angular_velocity) / dt
    if angular_accel > _MAX_ANGULAR_ACCEL_DEG_S2:
        angular_accel = 0.0

    return JointAcceleration(
        joint_type=vel_curr.joint_type,
        acceleration=(ax, ay, az),
        magnitude=magnitude,
        angular_acceleration=angular_accel,
    )


def calculate_position_acceleration(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    kp_next: NDArray[np.float64],
    dt: float,
    joint_type: JointType,
    kp_idx: int,
) -> JointAcceleration | None:
    """
    중앙차분법 기반 위치 직접 가속도 계산.

    a(t) = [x(t+dt) - 2·x(t) + x(t-dt)] / dt²

    속도 데이터 없이도 3-프레임 키포인트로 직접 가속도 산출.
    2차 정확도 (O(dt²)).

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3/4)
        kp_curr: 현재 프레임 키포인트
        kp_next: 다음 프레임 키포인트
        dt: 프레임 간 시간 간격 (초, 등간격)
        joint_type: 관절 유형
        kp_idx: 해당 관절의 Unified 25kp 인덱스

    Returns:
        JointAcceleration 객체 (이상치 시 None)

    참조:
        Winter (2009) Ch.3: 2차 중앙차분법
    """
    if dt < _MIN_DT:
        return None

    if kp_idx < 0 or kp_idx >= min(kp_prev.shape[0], kp_curr.shape[0], kp_next.shape[0]):
        return None

    pos_prev = kp_prev[kp_idx, :3].astype(np.float64)
    pos_curr = kp_curr[kp_idx, :3].astype(np.float64)
    pos_next = kp_next[kp_idx, :3].astype(np.float64)

    # a = (x_{n+1} - 2·x_n + x_{n-1}) / dt²
    accel = (pos_next - 2.0 * pos_curr + pos_prev) / (dt ** 2)
    ax, ay, az = float(accel[0]), float(accel[1]), float(accel[2])
    magnitude = (ax ** 2 + ay ** 2 + az ** 2) ** 0.5

    if magnitude > _MAX_JOINT_ACCEL_CM_S2:
        return None

    return JointAcceleration(
        joint_type=joint_type,
        acceleration=(ax, ay, az),
        magnitude=magnitude,
        angular_acceleration=0.0,
    )


# =============================================================================
# 체 중심 가속도
# =============================================================================

def _classify_acceleration(accel_m_s2: float, is_accel: bool) -> str:
    """
    가속도 크기 기반 분류.

    Args:
        accel_m_s2: 가속도 크기 (m/s²)
        is_accel: 양의 가속 여부 (False=감속)

    Returns:
        분류 문자열
    """
    abs_accel = abs(accel_m_s2)

    if abs_accel >= ACCELERATION_EXPLOSIVE_THRESHOLD:
        return "explosive_acceleration" if is_accel else "hard_stop"
    if abs_accel >= ACCELERATION_QUICK_MIN:
        return "quick_acceleration" if is_accel else "quick_deceleration"
    if abs_accel >= ACCELERATION_NORMAL_MIN:
        return "normal_acceleration" if is_accel else "normal_deceleration"
    return "steady"


def calculate_body_acceleration(
    speed_prev_m_s: float,
    speed_curr_m_s: float,
    velocity_prev: tuple[float, float] | None,
    velocity_curr: tuple[float, float] | None,
    dt: float,
) -> BodyAcceleration | None:
    """
    선수 체 중심 가속도 및 방향 변화 계산.

    Args:
        speed_prev_m_s: 이전 프레임 속력 (m/s)
        speed_curr_m_s: 현재 프레임 속력 (m/s)
        velocity_prev: 이전 프레임 수평 속도 벡터 (vx, vz) — 방향 계산용
        velocity_curr: 현재 프레임 수평 속도 벡터 (vx, vz)
        dt: 시간 간격 (초)

    Returns:
        BodyAcceleration 객체 (계산 불가 시 None)
    """
    if dt < _MIN_DT:
        return None

    # 가속도 벡터 크기 계산 — 벡터 차분(Δv) 기반으로 구심 성분 포함
    # 속도 벡터가 있으면 |Δv|/dt (진짜 가속도 크기), 없으면 속력 스칼라 차분 폴백
    if velocity_prev is not None and velocity_curr is not None:
        dvx = velocity_curr[0] - velocity_prev[0]
        dvz = velocity_curr[1] - velocity_prev[1]
        accel_magnitude = (dvx * dvx + dvz * dvz) ** 0.5 / dt
        # 부호: 속력 변화율로 가속/감속 판단 (탄젠셜 성분)
        tangential_accel = (speed_curr_m_s - speed_prev_m_s) / dt
        accel = accel_magnitude if tangential_accel >= 0 else -accel_magnitude
    else:
        # 폴백: 속력 차분 (탄젠셜만, 구심 성분 누락 — 덜 정확)
        accel = (speed_curr_m_s - speed_prev_m_s) / dt

    if abs(accel) > _MAX_BODY_ACCEL_M_S2:
        return None

    is_accel = accel >= 0
    category = _classify_acceleration(accel, is_accel)

    # 방향 변화각
    direction_change = 0.0
    if velocity_prev is not None and velocity_curr is not None:
        norm_prev = (velocity_prev[0] ** 2 + velocity_prev[1] ** 2) ** 0.5
        norm_curr = (velocity_curr[0] ** 2 + velocity_curr[1] ** 2) ** 0.5

        if norm_prev > 1e-4 and norm_curr > 1e-4:
            cos_angle = (
                velocity_prev[0] * velocity_curr[0]
                + velocity_prev[1] * velocity_curr[1]
            ) / (norm_prev * norm_curr)
            cos_angle = max(-1.0, min(1.0, cos_angle))
            direction_change = abs(np.degrees(np.arccos(cos_angle)))

    return BodyAcceleration(
        acceleration_m_s2=accel,
        acceleration_category=category,
        is_accelerating=is_accel,
        direction_change_deg=direction_change,
    )


# =============================================================================
# 일괄 계산 함수
# =============================================================================

def calculate_all_accelerations(
    vel_prev: FrameVelocities,
    vel_curr: FrameVelocities,
) -> FrameAccelerations:
    """
    프레임 간 모든 관절 가속도 일괄 계산.

    Args:
        vel_prev: 이전 프레임 속도 데이터
        vel_curr: 현재 프레임 속도 데이터

    Returns:
        FrameAccelerations 객체
    """
    dt = vel_curr.dt
    joint_accels: dict[JointType, JointAcceleration] = {}

    for joint_type, curr_vel in vel_curr.joint_velocities.items():
        prev_vel = vel_prev.joint_velocities.get(joint_type)
        if prev_vel is None:
            continue

        result = calculate_joint_acceleration(prev_vel, curr_vel, dt)
        if result is not None:
            joint_accels[joint_type] = result

    # 체 중심 가속도 (속력 차분)
    body_accel = calculate_body_acceleration(
        speed_prev_m_s=vel_prev.body_speed_m_s,
        speed_curr_m_s=vel_curr.body_speed_m_s,
        velocity_prev=None,  # 속도 벡터는 상위 파이프라인에서 제공
        velocity_curr=None,
        dt=dt,
    )

    return FrameAccelerations(
        joint_accelerations=joint_accels,
        body_acceleration=body_accel,
        dt=dt,
    )


# =============================================================================
# 감지 함수
# =============================================================================

def detect_explosive_acceleration(
    body_accel: BodyAcceleration,
) -> bool:
    """폭발적 가속 감지 (스프린트 시작, 크로스오버 등)."""
    return (
        body_accel.is_accelerating
        and body_accel.acceleration_m_s2 >= ACCELERATION_EXPLOSIVE_THRESHOLD
    )


def detect_hard_stop(
    body_accel: BodyAcceleration,
) -> bool:
    """급제동 감지 (풀업 점퍼, 급정지 등)."""
    return (
        not body_accel.is_accelerating
        and abs(body_accel.acceleration_m_s2) >= DECELERATION_HARD_STOP_THRESHOLD
    )


def detect_direction_change(
    body_accel: BodyAcceleration,
    min_angle_deg: float = 45.0,
) -> bool:
    """
    방향 전환 감지.

    Args:
        body_accel: 체 중심 가속도 데이터
        min_angle_deg: 방향 전환 최소 각도 (기본 45도)

    Returns:
        방향 전환 여부
    """
    return body_accel.direction_change_deg >= min_angle_deg


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "JointAcceleration",
    "BodyAcceleration",
    "FrameAccelerations",
    # 관절 가속도
    "calculate_joint_acceleration",
    "calculate_position_acceleration",
    # 체 중심 가속도
    "calculate_body_acceleration",
    # 일괄 계산
    "calculate_all_accelerations",
    # 감지 함수
    "detect_explosive_acceleration",
    "detect_hard_stop",
    "detect_direction_change",
]

__version__ = "1.0.0"
