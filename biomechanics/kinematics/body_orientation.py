# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: body_orientation.py
설명: 몸체 방위/자세 분석 모듈
      - 체간 롤/피치/요 각도 산출
      - 몸 정면 방향 벡터 계산
      - 상체/하체 회전 분리 (분리각)
      - 코트 기준 절대 방향 추정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Diebel, J. (2006). Representing Attitude: Euler Angles, Unit Quaternions,
      and Rotation Vectors. Stanford University.
    - Zatsiorsky, V.M. (2002). Kinetics of Human Motion.
    - Roll = 좌우 기울기, Pitch = 전후 기울기, Yaw = 회전(좌우 방향)
    - 체간 분리각: 상체-하체 회전 차이 = 코어 파워 지표

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/constants/biomechanics_constants.py: StanceType, SHOOTING_OPTIMAL_ANGLES

사용처:
    - biomechanics/kinematics/motion_pattern.py: 자세 기반 패턴 분류
    - motion_analysis/detection/: 슈팅/패스 방향 판정
    - ai_referee/: 공격/수비 방향 판단 (백코트 바이올레이션 등)
    - feedback_system/: 몸 얼라인먼트 피드백
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.pose_constants import (
    UK25_R_SHOULDER as _KP_R_SHOULDER,
    UK25_L_SHOULDER as _KP_L_SHOULDER,
    UK25_R_HIP as _KP_R_HIP,
    UK25_L_HIP as _KP_L_HIP,
)


# =============================================================================
# 상수
# =============================================================================

_MIN_NORM: Final[float] = 1e-8

# 분리각 기준치 (도)
# 높은 분리각 = 코어 파워 활용 (슈팅, 패스에서 중요)
_MIN_SEPARATION_NOTABLE: Final[float] = 15.0  # 주목할 만한 분리
_HIGH_SEPARATION_THRESHOLD: Final[float] = 30.0  # 높은 분리 (강력한 코어 사용)


# =============================================================================
# 방위 결과 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class BodyOrientation:
    """
    몸체 방위 (오일러 각도).

    좌표 규약: X=좌우, Y=상하, Z=전후.

    Attributes:
        roll_deg: 좌우 기울기 (도, 양수=오른쪽 기울기)
        pitch_deg: 전후 기울기 (도, 양수=전방 기울기)
        yaw_deg: 회전 (도, 양수=좌측 회전)
        facing_direction: 정면 방향 단위 벡터 (XZ 평면, 3D)
    """

    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    facing_direction: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class TrunkSeparation:
    """
    상체-하체 분리각.

    상체(어깨 축)와 하체(골반 축)의 수평면 회전 차이.
    코어 파워 활용 지표 — 슈팅, 패스, 방향 전환에서 중요.

    Attributes:
        separation_deg: 분리각 (도, 0~180)
        upper_yaw_deg: 상체 회전 (도)
        lower_yaw_deg: 하체 회전 (도)
        is_notable: 주목할 만한 분리 여부 (≥15도)
        is_high: 높은 분리 여부 (≥30도)
    """

    separation_deg: float
    upper_yaw_deg: float
    lower_yaw_deg: float
    is_notable: bool
    is_high: bool


# =============================================================================
# 핵심 계산 함수
# =============================================================================

def _compute_axis_vector(
    keypoints: NDArray[np.float64],
    left_idx: int,
    right_idx: int,
) -> NDArray[np.float64] | None:
    """
    두 키포인트로 축 벡터 계산 (좌 → 우 방향).

    Args:
        keypoints: 3D 키포인트 (25×3/4)
        left_idx: 왼쪽 키포인트 인덱스
        right_idx: 오른쪽 키포인트 인덱스

    Returns:
        단위 벡터 (3,) 또는 None
    """
    if left_idx >= keypoints.shape[0] or right_idx >= keypoints.shape[0]:
        return None

    left = keypoints[left_idx, :3].astype(np.float64)
    right = keypoints[right_idx, :3].astype(np.float64)

    axis = right - left
    norm = np.linalg.norm(axis)
    if norm < _MIN_NORM:
        return None

    return axis / norm


def _compute_yaw_from_axis(
    axis_xz: NDArray[np.float64],
) -> float:
    """
    어깨 축(L→R, XZ 평면)에서 선수의 정면(facing) 방향 Yaw 각도 산출.

    규약:
      - 0°   : 선수가 +Z 방향을 바라봄 (카메라 뒤쪽)
      - +90° : 선수가 +X 방향을 바라봄 (코트 우측)
      - -90° : 선수가 -X 방향을 바라봄 (코트 좌측)

    어깨 축 (sx, sz)을 Y축 기준 -90° 회전하면 정면 벡터 (-sz, sx)가 됩니다.
    atan2(facing_x, facing_z) = atan2(-sz, sx)로 정면 방향각 반환.

    Args:
        axis_xz: 어깨 축의 XZ 평면 성분 [sx, sz] (정규화 불필요)

    Returns:
        정면 방향 Yaw (도, -180~180)
    """
    sx = float(axis_xz[0])
    sz = float(axis_xz[1])
    # 정면 = shoulder_axis를 Y축 기준 -90° 회전
    facing_x = -sz
    facing_z = sx
    return math.degrees(math.atan2(facing_x, facing_z))


def calculate_body_orientation(
    keypoints_3d: NDArray[np.float64],
) -> BodyOrientation | None:
    """
    몸체 방위 (Roll, Pitch, Yaw) 계산.

    어깨 축 + 체간 벡터로 3축 방위 산출.

    Roll: 어깨 축의 Y축 기울기 (좌우 기울기)
    Pitch: 체간 벡터의 수직 대비 각도 (전후 기울기)
    Yaw: 어깨 축의 XZ 평면 방향 (회전)

    Args:
        keypoints_3d: 3D 키포인트 (25×3 또는 25×4)

    Returns:
        BodyOrientation 객체 (계산 불가 시 None)
    """
    # 어깨 축 (L→R)
    shoulder_axis = _compute_axis_vector(
        keypoints_3d, _KP_L_SHOULDER, _KP_R_SHOULDER
    )
    if shoulder_axis is None:
        return None

    # 체간 벡터 (골반 중점 → 어깨 중점)
    required = [_KP_L_SHOULDER, _KP_R_SHOULDER, _KP_L_HIP, _KP_R_HIP]
    for idx in required:
        if idx >= keypoints_3d.shape[0]:
            return None

    shoulder_mid = (
        keypoints_3d[_KP_L_SHOULDER, :3] + keypoints_3d[_KP_R_SHOULDER, :3]
    ) / 2.0
    hip_mid = (
        keypoints_3d[_KP_L_HIP, :3] + keypoints_3d[_KP_R_HIP, :3]
    ) / 2.0

    trunk_vec = shoulder_mid - hip_mid
    trunk_norm = np.linalg.norm(trunk_vec)
    if trunk_norm < _MIN_NORM:
        return None

    trunk_unit = trunk_vec / trunk_norm

    # Roll: 어깨 축의 Y 성분으로 좌우 기울기 산출
    # 수평이면 shoulder_axis[1] ≈ 0
    roll_deg = math.degrees(math.asin(
        max(-1.0, min(1.0, float(shoulder_axis[1])))
    ))

    # Pitch: 체간 벡터와 수직축(Y)의 각도
    vertical = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    cos_pitch = float(np.dot(trunk_unit, vertical))
    cos_pitch = max(-1.0, min(1.0, cos_pitch))
    pitch_deg = math.degrees(math.acos(cos_pitch))

    # Yaw: 어깨 축의 XZ 평면 방향
    shoulder_xz = np.array([shoulder_axis[0], shoulder_axis[2]], dtype=np.float64)
    xz_norm = np.linalg.norm(shoulder_xz)
    if xz_norm < _MIN_NORM:
        yaw_deg = 0.0
    else:
        shoulder_xz_unit = shoulder_xz / xz_norm
        yaw_deg = _compute_yaw_from_axis(shoulder_xz_unit)

    # 정면 방향: 어깨 축에 수직 (XZ 평면)
    # 어깨 좌→우가 (sx, sz)이면 정면 = (-sz, 0, sx) 정규화
    facing = np.array([-shoulder_axis[2], 0.0, shoulder_axis[0]], dtype=np.float64)
    facing_norm = np.linalg.norm(facing)
    if facing_norm > _MIN_NORM:
        facing = facing / facing_norm

    return BodyOrientation(
        roll_deg=roll_deg,
        pitch_deg=pitch_deg,
        yaw_deg=yaw_deg,
        facing_direction=(float(facing[0]), float(facing[1]), float(facing[2])),
    )


def calculate_trunk_separation(
    keypoints_3d: NDArray[np.float64],
) -> TrunkSeparation | None:
    """
    상체-하체 분리각 계산.

    상체(어깨) 축과 하체(골반) 축의 수평면 회전 차이.
    코어 파워 활용 지표: 슈팅 시 분리각 ~20-40도가 일반적.

    Args:
        keypoints_3d: 3D 키포인트 (25×3 또는 25×4)

    Returns:
        TrunkSeparation 객체 (계산 불가 시 None)

    참조:
        Zatsiorsky (2002) - 인체 운동 역학: 체간 분리각과 에너지 전달
    """
    # 어깨 축
    shoulder_axis = _compute_axis_vector(
        keypoints_3d, _KP_L_SHOULDER, _KP_R_SHOULDER
    )
    if shoulder_axis is None:
        return None

    # 골반 축
    hip_axis = _compute_axis_vector(
        keypoints_3d, _KP_L_HIP, _KP_R_HIP
    )
    if hip_axis is None:
        return None

    # XZ 평면 투영 후 각도 산출
    shoulder_xz = np.array([shoulder_axis[0], shoulder_axis[2]], dtype=np.float64)
    hip_xz = np.array([hip_axis[0], hip_axis[2]], dtype=np.float64)

    s_norm = np.linalg.norm(shoulder_xz)
    h_norm = np.linalg.norm(hip_xz)

    if s_norm < _MIN_NORM or h_norm < _MIN_NORM:
        return None

    shoulder_xz /= s_norm
    hip_xz /= h_norm

    upper_yaw = _compute_yaw_from_axis(shoulder_xz)
    lower_yaw = _compute_yaw_from_axis(hip_xz)

    # 분리각: 상체-하체 회전 차이
    raw_sep = abs(upper_yaw - lower_yaw)
    # 180도 초과 보정 (최단 각도 사용)
    if raw_sep > 180.0:
        raw_sep = 360.0 - raw_sep

    return TrunkSeparation(
        separation_deg=raw_sep,
        upper_yaw_deg=upper_yaw,
        lower_yaw_deg=lower_yaw,
        is_notable=raw_sep >= _MIN_SEPARATION_NOTABLE,
        is_high=raw_sep >= _HIGH_SEPARATION_THRESHOLD,
    )


def calculate_facing_angle_to_target(
    orientation: BodyOrientation,
    target_direction: tuple[float, float, float],
) -> float:
    """
    정면 방향과 목표 방향 간 각도 계산.

    바스켓 방향, 패스 대상 방향 등과의 정렬 평가.

    Args:
        orientation: 몸체 방위
        target_direction: 목표 방향 벡터 (x, y, z, 정규화 불필요)

    Returns:
        각도 (도, 0~180, 0=완전 정렬)
    """
    facing = np.array(orientation.facing_direction, dtype=np.float64)
    target = np.array(target_direction, dtype=np.float64)

    # XZ 평면 투영
    facing_xz = np.array([facing[0], facing[2]], dtype=np.float64)
    target_xz = np.array([target[0], target[2]], dtype=np.float64)

    f_norm = np.linalg.norm(facing_xz)
    t_norm = np.linalg.norm(target_xz)

    if f_norm < _MIN_NORM or t_norm < _MIN_NORM:
        return 0.0

    cos_angle = float(np.dot(facing_xz, target_xz) / (f_norm * t_norm))
    cos_angle = max(-1.0, min(1.0, cos_angle))

    return math.degrees(math.acos(cos_angle))


def get_orientation_tuple(
    orientation: BodyOrientation,
) -> tuple[float, float, float]:
    """
    BodyOrientation → BiomechanicalFrame.body_orientation 변환.

    Returns:
        (roll, pitch, yaw) 도
    """
    return (orientation.roll_deg, orientation.pitch_deg, orientation.yaw_deg)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "BodyOrientation",
    "TrunkSeparation",
    # 핵심 함수
    "calculate_body_orientation",
    "calculate_trunk_separation",
    "calculate_facing_angle_to_target",
    # 변환 유틸
    "get_orientation_tuple",
]

__version__ = "1.0.0"
