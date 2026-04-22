# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: velocity_analyzer.py
설명: 관절 속도/각속도 분석 모듈
      - 프레임 간 유한차분법 기반 선속도 계산 (cm/s)
      - 프레임 간 각도 변화 기반 각속도 계산 (deg/s)
      - 이동 강도 분류 (STATIONARY ~ MAX_EFFORT)
      - 연령/성별 보정 속도 임계치 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.3.
    - 중앙차분법: v(t) ≈ [x(t+dt) - x(t-dt)] / (2·dt)
    - 전방차분법: v(t) ≈ [x(t+dt) - x(t)] / dt
    - Okazaki & Rodacki (2012). Basketball jump shot kinematics.

의존성:
    - shared/constants/biomechanics_constants.py: MovementIntensity, VELOCITY_THRESHOLDS,
      AGE_VELOCITY_FACTOR, GENDER_VELOCITY_FACTOR, JOINT_FAST_MOTION_SPEED_CM_S
    - shared/constants/player_constants.py: AgeGroup, Gender
    - shared/constants/pose_constants.py: JointType
    - biomechanics/kinematics/joint_angle_calculator.py: FrameAngles

사용처:
    - biomechanics/kinematics/acceleration_analyzer.py: 가속도 계산 시 속도 데이터 참조
    - biomechanics/kinematics/motion_pattern.py: 동작 패턴 분류 시 속도 특징 활용
    - biomechanics/dynamics/force_estimator.py: 힘 추정 시 속도 필요
    - motion_analysis/detection/: 동작 감지 시 속도 임계치 기반 트리거
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    AGE_VELOCITY_FACTOR,
    GENDER_VELOCITY_FACTOR,
    JOINT_FAST_MOTION_SPEED_CM_S,
    MovementIntensity,
    VELOCITY_THRESHOLDS_ADULT_MALE,
    VELOCITY_THRESHOLDS_ADULT_FEMALE,
)
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.pose_constants import (
    JointType,
    UK25_NECK as _KP_NECK,
    UK25_R_HIP as _KP_R_HIP,
    UK25_L_HIP as _KP_L_HIP,
)

from biomechanics.kinematics.joint_angle_calculator import FrameAngles


# =============================================================================
# 로컬 헬퍼 (shared에 미존재 함수)
# =============================================================================

def get_velocity_thresholds(
    intensity: MovementIntensity,
    age_group: AgeGroup = AgeGroup.ADULT,
    gender: Gender = Gender.MALE,
) -> tuple[float, float]:
    """성별/연령 적응된 속도 임계값 반환 (m/s)."""
    if gender == Gender.MALE:
        base = VELOCITY_THRESHOLDS_ADULT_MALE.get(intensity, (0.0, 0.0))
    else:
        base = VELOCITY_THRESHOLDS_ADULT_FEMALE.get(intensity, (0.0, 0.0))

    age_factor = AGE_VELOCITY_FACTOR.get(age_group, 1.0)
    return (base[0] * age_factor, base[1] * age_factor)


# =============================================================================
# 상수
# =============================================================================

# 최소 시간 간격 (0-division 방지, 초)
_MIN_DT: Final[float] = 1e-6

# 최소 키포인트 신뢰도
_MIN_CONFIDENCE: Final[float] = 0.3

# 속도 이상치 상한 (cm/s) — 물리적 한계 기반 필터링
# NBA 최대 전력질주 ~10m/s = 1000cm/s, 슛 릴리스 손 ~800cm/s
# 안전 마진 2배 적용
_MAX_JOINT_SPEED_CM_S: Final[float] = 2000.0

# 각속도 이상치 상한 (deg/s) — 팔꿈치 신전 최대 ~2500deg/s
_MAX_ANGULAR_VELOCITY_DEG_S: Final[float] = 3000.0

# Unified 25kp 키포인트 인덱스는 SSOT(shared.constants.pose_constants)에서 import

# 선수 무게중심(대리) 키포인트: 목, 좌골반, 우골반의 평균
_COM_PROXY_INDICES: Final[tuple[int, ...]] = (_KP_NECK, _KP_R_HIP, _KP_L_HIP)

# COCO 17kp → Unified 25kp 매핑 (선속도 계산 대상)
_JOINT_TO_25KP: Final[dict[JointType, int]] = {
    JointType.NOSE: 0,
    JointType.LEFT_SHOULDER: 5,
    JointType.RIGHT_SHOULDER: 2,
    JointType.LEFT_ELBOW: 6,
    JointType.RIGHT_ELBOW: 3,
    JointType.LEFT_WRIST: 7,
    JointType.RIGHT_WRIST: 4,
    JointType.LEFT_HIP: 11,
    JointType.RIGHT_HIP: 8,
    JointType.LEFT_KNEE: 12,
    JointType.RIGHT_KNEE: 9,
    JointType.LEFT_ANKLE: 13,
    JointType.RIGHT_ANKLE: 10,
}


# =============================================================================
# 속도 결과 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class JointVelocity:
    """
    단일 관절의 선속도 데이터.

    Attributes:
        joint_type: 관절 유형
        velocity: 속도 벡터 (vx, vy, vz) cm/s
        speed: 속력 (크기) cm/s
        angular_velocity: 각속도 deg/s (프레임 간 각도 변화율)
        is_fast_motion: 빠른 동작 여부 (슛 릴리스 등)
    """

    joint_type: JointType
    velocity: tuple[float, float, float]
    speed: float
    angular_velocity: float
    is_fast_motion: bool


@dataclass(frozen=True, slots=True)
class FrameVelocities:
    """
    프레임 단위 모든 관절 속도.

    Attributes:
        joint_velocities: 관절별 속도
        body_speed_m_s: 선수 이동 속력 (m/s, 체 중심 기준)
        movement_intensity: 이동 강도 분류
        dt: 프레임 간 시간 간격 (초)
    """

    joint_velocities: dict[JointType, JointVelocity]
    body_speed_m_s: float
    movement_intensity: MovementIntensity
    dt: float

    @property
    def max_joint_speed(self) -> float:
        """최대 관절 속력 (cm/s)."""
        if not self.joint_velocities:
            return 0.0
        return max(jv.speed for jv in self.joint_velocities.values())

    @property
    def fast_motion_joints(self) -> list[JointType]:
        """빠른 동작 관절 목록."""
        return [
            jv.joint_type
            for jv in self.joint_velocities.values()
            if jv.is_fast_motion
        ]


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _get_confidence(
    keypoints: NDArray[np.float64],
    idx: int,
) -> float:
    """키포인트 신뢰도 추출."""
    if idx < 0 or idx >= keypoints.shape[0]:
        return 0.0
    if keypoints.shape[1] >= 4:
        return float(keypoints[idx, 3])
    return 1.0


def _is_valid(
    keypoints: NDArray[np.float64],
    idx: int,
) -> bool:
    """키포인트 유효성 검증."""
    return _get_confidence(keypoints, idx) >= _MIN_CONFIDENCE


# =============================================================================
# 핵심 속도 계산 함수
# =============================================================================

def calculate_joint_velocity(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    dt: float,
    joint_type: JointType,
    angles_prev: FrameAngles | None = None,
    angles_curr: FrameAngles | None = None,
) -> JointVelocity | None:
    """
    단일 관절의 선속도 및 각속도 계산.

    전방차분법: v = (x_curr - x_prev) / dt

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3 또는 25×4)
        kp_curr: 현재 프레임 키포인트
        dt: 시간 간격 (초)
        joint_type: 관절 유형
        angles_prev: 이전 프레임 관절 각도 (각속도 계산용)
        angles_curr: 현재 프레임 관절 각도

    Returns:
        JointVelocity 객체 (계산 불가 시 None)
    """
    if dt < _MIN_DT:
        return None

    kp_idx = _JOINT_TO_25KP.get(joint_type)
    if kp_idx is None:
        return None

    # 양쪽 프레임 모두 유효한지 검증
    if not (_is_valid(kp_prev, kp_idx) and _is_valid(kp_curr, kp_idx)):
        return None

    # 선속도 (cm/s) = (현재 좌표 - 이전 좌표) / dt
    pos_prev = kp_prev[kp_idx, :3].astype(np.float64)
    pos_curr = kp_curr[kp_idx, :3].astype(np.float64)

    displacement = pos_curr - pos_prev
    velocity = displacement / dt
    speed = float(np.linalg.norm(velocity))

    # 이상치 필터링
    if speed > _MAX_JOINT_SPEED_CM_S:
        return None

    # 각속도 (deg/s) = (현재 각도 - 이전 각도) / dt
    angular_vel = 0.0
    if angles_prev is not None and angles_curr is not None:
        prev_angle = angles_prev.get_angle(joint_type)
        curr_angle = angles_curr.get_angle(joint_type)
        if prev_angle is not None and curr_angle is not None:
            raw_angular = abs(curr_angle - prev_angle) / dt
            if raw_angular <= _MAX_ANGULAR_VELOCITY_DEG_S:
                angular_vel = raw_angular

    return JointVelocity(
        joint_type=joint_type,
        velocity=(float(velocity[0]), float(velocity[1]), float(velocity[2])),
        speed=speed,
        angular_velocity=angular_vel,
        is_fast_motion=speed > JOINT_FAST_MOTION_SPEED_CM_S,
    )


def calculate_body_speed(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    dt: float,
) -> float | None:
    """
    선수 이동 속력 계산 (m/s).

    목 + 좌우 골반 중점을 체 중심(COM) 대리 지표로 사용.
    수평면(XZ) 이동만 계산 (Y축 = 수직 방향 제외).

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3 또는 25×4)
        kp_curr: 현재 프레임 키포인트
        dt: 시간 간격 (초)

    Returns:
        이동 속력 (m/s), 계산 불가 시 None
    """
    if dt < _MIN_DT:
        return None

    # COM 대리: 목/좌골반/우골반 평균
    valid_prev = []
    valid_curr = []
    for idx in _COM_PROXY_INDICES:
        if _is_valid(kp_prev, idx) and _is_valid(kp_curr, idx):
            valid_prev.append(kp_prev[idx, :3])
            valid_curr.append(kp_curr[idx, :3])

    if len(valid_prev) < 2:
        return None

    com_prev = np.mean(valid_prev, axis=0)
    com_curr = np.mean(valid_curr, axis=0)

    # 수평면 변위 (XZ)
    displacement_xz = np.array([
        com_curr[0] - com_prev[0],
        com_curr[2] - com_prev[2],
    ], dtype=np.float64)

    distance_cm = float(np.linalg.norm(displacement_xz))
    # cm/s → m/s
    speed_m_s = (distance_cm / dt) / 100.0

    return speed_m_s


def classify_movement_intensity(
    speed_m_s: float,
    age_group: AgeGroup = AgeGroup.ADULT,
    gender: Gender = Gender.MALE,
) -> MovementIntensity:
    """
    이동 속력 기반 강도 분류.

    Args:
        speed_m_s: 이동 속력 (m/s)
        age_group: 연령대
        gender: 성별

    Returns:
        MovementIntensity 열거형
    """
    # 역순으로 검사 (MAX_EFFORT부터)
    intensities = [
        MovementIntensity.MAX_EFFORT,
        MovementIntensity.SPRINTING,
        MovementIntensity.RUNNING,
        MovementIntensity.JOGGING,
        MovementIntensity.WALKING,
        MovementIntensity.STATIONARY,
    ]

    for intensity in intensities:
        low, high = get_velocity_thresholds(intensity, age_group, gender)
        if speed_m_s >= low:
            return intensity

    return MovementIntensity.STATIONARY


# =============================================================================
# 일괄 계산 함수
# =============================================================================

def calculate_all_velocities(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    dt: float,
    angles_prev: FrameAngles | None = None,
    angles_curr: FrameAngles | None = None,
    age_group: AgeGroup = AgeGroup.ADULT,
    gender: Gender = Gender.MALE,
) -> FrameVelocities:
    """
    프레임 간 모든 관절 속도 일괄 계산.

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3 또는 25×4)
        kp_curr: 현재 프레임 키포인트
        dt: 시간 간격 (초)
        angles_prev: 이전 프레임 관절 각도 (선택)
        angles_curr: 현재 프레임 관절 각도 (선택)
        age_group: 연령대
        gender: 성별

    Returns:
        FrameVelocities 객체
    """
    joint_velocities: dict[JointType, JointVelocity] = {}

    for joint_type in _JOINT_TO_25KP:
        result = calculate_joint_velocity(
            kp_prev, kp_curr, dt, joint_type,
            angles_prev, angles_curr,
        )
        if result is not None:
            joint_velocities[joint_type] = result

    # 선수 이동 속력
    body_speed = calculate_body_speed(kp_prev, kp_curr, dt)
    if body_speed is None:
        body_speed = 0.0

    intensity = classify_movement_intensity(body_speed, age_group, gender)

    return FrameVelocities(
        joint_velocities=joint_velocities,
        body_speed_m_s=body_speed,
        movement_intensity=intensity,
        dt=dt,
    )


def calculate_central_velocity(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    kp_next: NDArray[np.float64],
    dt: float,
    joint_type: JointType,
) -> JointVelocity | None:
    """
    중앙차분법 기반 관절 속도 계산 (정확도 향상).

    v(t) = [x(t+dt) - x(t-dt)] / (2·dt)

    3-프레임 사용 시 2차 정확도 (O(dt²)) 달성.
    시퀀스 양 끝 프레임에서는 전방/후방 차분법 사용.

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3/4)
        kp_curr: 현재 프레임 키포인트 (사용하지 않으나 인터페이스 통일)
        kp_next: 다음 프레임 키포인트 (25×3/4)
        dt: 프레임 간 시간 간격 (초, 등간격 가정)
        joint_type: 관절 유형

    Returns:
        JointVelocity 객체 (계산 불가 시 None)

    참조:
        Winter (2009) Ch.3: Kinematics, 중앙차분 수식
    """
    if dt < _MIN_DT:
        return None

    kp_idx = _JOINT_TO_25KP.get(joint_type)
    if kp_idx is None:
        return None

    if not (_is_valid(kp_prev, kp_idx) and _is_valid(kp_next, kp_idx)):
        return None

    pos_prev = kp_prev[kp_idx, :3].astype(np.float64)
    pos_next = kp_next[kp_idx, :3].astype(np.float64)

    # 중앙차분: v = (x_next - x_prev) / (2*dt)
    displacement = pos_next - pos_prev
    velocity = displacement / (2.0 * dt)
    speed = float(np.linalg.norm(velocity))

    if speed > _MAX_JOINT_SPEED_CM_S:
        return None

    return JointVelocity(
        joint_type=joint_type,
        velocity=(float(velocity[0]), float(velocity[1]), float(velocity[2])),
        speed=speed,
        angular_velocity=0.0,  # 중앙차분 각속도는 별도 계산 필요
        is_fast_motion=speed > JOINT_FAST_MOTION_SPEED_CM_S,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "JointVelocity",
    "FrameVelocities",
    # 단일 관절 속도
    "calculate_joint_velocity",
    "calculate_central_velocity",
    # 전체 속도
    "calculate_all_velocities",
    # 선수 이동
    "calculate_body_speed",
    "classify_movement_intensity",
]

__version__ = "1.0.0"
