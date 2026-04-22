# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/anthropometry
파일: proportion_calculator.py
설명: 신체 비율 계산 모듈
      - 키포인트 간 거리로 신체 비율 추정
      - 윙스팬/신장 비율, 상/하체 비율 등
      - 세그먼트 길이 추정 및 좌우 비대칭 분석

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Pheasant, S. & Haslegrave, C. (2018). Bodyspace: Anthropometry,
      Ergonomics and the Design of Work.
    - Drillis, R. & Contini, R. (1966). Body Segment Parameters.

의존성:
    - shared/constants/biomechanics_constants.py: BodySegment, SEGMENT_LENGTH_RATIO
    - biomechanics/anthropometry/body_segment.py: SEGMENT_ENDPOINT_INDICES_25KP

사용처:
    - biomechanics/anthropometry/personal_adapter.py: 개인 신체 비율 반영
    - biomechanics/kinematics/: 세그먼트 길이 기반 속도 계산
    - motion_analysis/form_evaluation/: 체형 대비 폼 평가
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.pose_constants import (
    UK25_NECK as _KP_NECK,
    UK25_R_SHOULDER as _KP_R_SHOULDER,
    UK25_R_ELBOW as _KP_R_ELBOW,
    UK25_R_WRIST as _KP_R_WRIST,
    UK25_L_SHOULDER as _KP_L_SHOULDER,
    UK25_L_ELBOW as _KP_L_ELBOW,
    UK25_L_WRIST as _KP_L_WRIST,
    UK25_R_HIP as _KP_R_HIP,
    UK25_R_KNEE as _KP_R_KNEE,
    UK25_R_ANKLE as _KP_R_ANKLE,
    UK25_L_HIP as _KP_L_HIP,
    UK25_L_KNEE as _KP_L_KNEE,
    UK25_L_ANKLE as _KP_L_ANKLE,
    UK25_HEAD_TOP as _KP_HEAD_TOP,
    UK25_R_FINGERTIP as _KP_R_FINGERTIP,
    UK25_L_FINGERTIP as _KP_L_FINGERTIP,
    UK25_R_HEEL as _KP_R_HEEL,
    UK25_L_HEEL as _KP_L_HEEL,
)


# =============================================================================
# 상수
# =============================================================================
MIN_VALID_DISTANCE_M: Final[float] = 0.01   # 최소 유효 거리 (1cm)
MAX_ASYMMETRY_RATIO: Final[float] = 0.20    # 좌우 비대칭 최대 허용 비율 (20%)


# =============================================================================
# 신체 비율 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class BodyProportions:
    """
    신체 비율 측정 결과.

    키포인트 간 거리로 추정한 신체 비율입니다.

    Attributes:
        estimated_height_m: 추정 신장 (m)
        wingspan_m: 윙스팬 (m, 양 손끝 간 거리)
        wingspan_height_ratio: 윙스팬/신장 비율
        upper_body_m: 상체 길이 (m, 머리꼭대기~골반)
        lower_body_m: 하체 길이 (m, 골반~발목)
        upper_lower_ratio: 상하체 비율
        shoulder_width_m: 어깨 너비 (m)
        hip_width_m: 골반 너비 (m)
        shoulder_hip_ratio: 어깨/골반 비율
        right_arm_m: 우측 팔 길이 (m, 어깨~손끝)
        left_arm_m: 좌측 팔 길이 (m, 어깨~손끝)
        arm_asymmetry: 팔 좌우 비대칭도 (0-1, 0=완전 대칭)
        right_leg_m: 우측 다리 길이 (m, 골반~발목)
        left_leg_m: 좌측 다리 길이 (m, 골반~발목)
        leg_asymmetry: 다리 좌우 비대칭도 (0-1)
    """

    estimated_height_m: float
    wingspan_m: float
    wingspan_height_ratio: float
    upper_body_m: float
    lower_body_m: float
    upper_lower_ratio: float
    shoulder_width_m: float
    hip_width_m: float
    shoulder_hip_ratio: float
    right_arm_m: float
    left_arm_m: float
    arm_asymmetry: float
    right_leg_m: float
    left_leg_m: float
    leg_asymmetry: float


@dataclass(frozen=True, slots=True)
class SegmentLengths:
    """
    개별 세그먼트 추정 길이.

    Attributes:
        r_upper_arm_m: 우측 상완 길이 (m)
        l_upper_arm_m: 좌측 상완 길이 (m)
        r_forearm_m: 우측 전완 길이 (m)
        l_forearm_m: 좌측 전완 길이 (m)
        r_thigh_m: 우측 대퇴 길이 (m)
        l_thigh_m: 좌측 대퇴 길이 (m)
        r_shank_m: 우측 하퇴 길이 (m)
        l_shank_m: 좌측 하퇴 길이 (m)
        trunk_m: 체간 길이 (m, 목~골반 중심)
    """

    r_upper_arm_m: float
    l_upper_arm_m: float
    r_forearm_m: float
    l_forearm_m: float
    r_thigh_m: float
    l_thigh_m: float
    r_shank_m: float
    l_shank_m: float
    trunk_m: float


# =============================================================================
# 유틸리티 함수
# =============================================================================
def _distance_3d(
    keypoints: NDArray[np.float64],
    idx_a: int,
    idx_b: int,
) -> float:
    """두 키포인트 간 3D 유클리드 거리 (m)."""
    coords = keypoints[:, :3] if keypoints.shape[1] > 3 else keypoints
    diff = coords[idx_a] - coords[idx_b]
    return float(np.linalg.norm(diff))


def _safe_ratio(numerator: float, denominator: float) -> float:
    """안전한 비율 계산 (분모 0 방지)."""
    if abs(denominator) < 1e-9:
        return 0.0
    return numerator / denominator


def _asymmetry(left: float, right: float) -> float:
    """
    좌우 비대칭도 계산 (0 = 완전 대칭, 1 = 최대 비대칭).

    |L - R| / max(L, R)
    """
    max_val = max(left, right)
    if max_val < MIN_VALID_DISTANCE_M:
        return 0.0
    return abs(left - right) / max_val


# 발목-지면 해부학적 거리 (Winter 2009): 신장의 약 3.9%
_ANKLE_TO_GROUND_RATIO: Final[float] = 0.039


def _estimate_height(
    keypoints_3d: NDArray[np.float64],
    head_top: NDArray[np.float64] | None = None,
) -> float:
    """
    신장 추정 (m).

    우선순위:
      1. heel(발뒤꿈치)이 유효 → head_top ~ heel_center 수직거리 = 신장
      2. heel 무효 → head_top ~ ankle_center + 해부학적 발목-지면 보정

    Args:
        keypoints_3d: 25×3+ 키포인트 배열
        head_top: 미리 계산된 머리꼭대기 좌표 (없으면 내부 조회)

    Returns:
        추정 신장 (m)
    """
    coords = keypoints_3d[:, :3] if keypoints_3d.shape[1] > 3 else keypoints_3d
    if head_top is None:
        head_top = coords[_KP_HEAD_TOP]

    r_heel = coords[_KP_R_HEEL]
    l_heel = coords[_KP_L_HEEL]
    r_heel_valid = bool(np.all(np.isfinite(r_heel)) and np.linalg.norm(r_heel) > MIN_VALID_DISTANCE_M)
    l_heel_valid = bool(np.all(np.isfinite(l_heel)) and np.linalg.norm(l_heel) > MIN_VALID_DISTANCE_M)

    if r_heel_valid and l_heel_valid:
        heel_center = (r_heel + l_heel) / 2.0
        return float(np.linalg.norm(head_top - heel_center))
    if r_heel_valid:
        return float(np.linalg.norm(head_top - r_heel))
    if l_heel_valid:
        return float(np.linalg.norm(head_top - l_heel))

    # heel 무효 → ankle 폴백
    r_ankle = coords[_KP_R_ANKLE]
    l_ankle = coords[_KP_L_ANKLE]
    ankle_center = (r_ankle + l_ankle) / 2.0
    vertical_height = float(np.linalg.norm(head_top - ankle_center))
    return vertical_height / (1.0 - _ANKLE_TO_GROUND_RATIO)


# =============================================================================
# 핵심 계산 함수
# =============================================================================
def calculate_segment_lengths(
    keypoints_3d: NDArray[np.float64],
) -> SegmentLengths:
    """
    키포인트로부터 세그먼트 길이 추정.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        SegmentLengths 객체
    """
    d = lambda a, b: _distance_3d(keypoints_3d, a, b)

    # 골반 중심
    hip_center = (keypoints_3d[_KP_R_HIP, :3] + keypoints_3d[_KP_L_HIP, :3]) / 2.0
    # 목에서 골반 중심까지 거리 = 체간
    neck_pos = keypoints_3d[_KP_NECK, :3]
    trunk_m = float(np.linalg.norm(neck_pos - hip_center))

    return SegmentLengths(
        r_upper_arm_m=d(_KP_R_SHOULDER, _KP_R_ELBOW),
        l_upper_arm_m=d(_KP_L_SHOULDER, _KP_L_ELBOW),
        r_forearm_m=d(_KP_R_ELBOW, _KP_R_WRIST),
        l_forearm_m=d(_KP_L_ELBOW, _KP_L_WRIST),
        r_thigh_m=d(_KP_R_HIP, _KP_R_KNEE),
        l_thigh_m=d(_KP_L_HIP, _KP_L_KNEE),
        r_shank_m=d(_KP_R_KNEE, _KP_R_ANKLE),
        l_shank_m=d(_KP_L_KNEE, _KP_L_ANKLE),
        trunk_m=trunk_m,
    )


def calculate_proportions(
    keypoints_3d: NDArray[np.float64],
) -> BodyProportions:
    """
    키포인트로부터 신체 비율 계산.

    신장 추정은 발뒤꿈치(heel) ~ 머리꼭대기 수직거리로 산출됩니다.
    heel이 유효하지 않으면 발목(ankle)에 해부학적 보정(ankle-ground ~0.039H,
    Winter 2009)을 적용합니다.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        BodyProportions 객체
    """
    d = lambda a, b: _distance_3d(keypoints_3d, a, b)

    # 신장 추정: heel 기준 (지면 접촉점) → 머리꼭대기
    head_top = keypoints_3d[_KP_HEAD_TOP, :3]
    estimated_height = _estimate_height(keypoints_3d, head_top)

    # 윙스팬
    wingspan = d(_KP_R_FINGERTIP, _KP_L_FINGERTIP)

    # 상체: 머리꼭대기 → 골반 중심
    hip_center = (keypoints_3d[_KP_R_HIP, :3] + keypoints_3d[_KP_L_HIP, :3]) / 2.0
    upper_body = float(np.linalg.norm(head_top - hip_center))

    # 하체: 골반 중심 → 발목 중심
    r_ankle = keypoints_3d[_KP_R_ANKLE, :3]
    l_ankle = keypoints_3d[_KP_L_ANKLE, :3]
    ankle_center = (r_ankle + l_ankle) / 2.0
    lower_body = float(np.linalg.norm(hip_center - ankle_center))

    # 어깨/골반 너비
    shoulder_width = d(_KP_R_SHOULDER, _KP_L_SHOULDER)
    hip_width = d(_KP_R_HIP, _KP_L_HIP)

    # 팔 길이 (어깨 → 손끝)
    right_arm = d(_KP_R_SHOULDER, _KP_R_ELBOW) + d(_KP_R_ELBOW, _KP_R_WRIST) + d(_KP_R_WRIST, _KP_R_FINGERTIP)
    left_arm = d(_KP_L_SHOULDER, _KP_L_ELBOW) + d(_KP_L_ELBOW, _KP_L_WRIST) + d(_KP_L_WRIST, _KP_L_FINGERTIP)

    # 다리 길이 (골반 → 발목)
    right_leg = d(_KP_R_HIP, _KP_R_KNEE) + d(_KP_R_KNEE, _KP_R_ANKLE)
    left_leg = d(_KP_L_HIP, _KP_L_KNEE) + d(_KP_L_KNEE, _KP_L_ANKLE)

    return BodyProportions(
        estimated_height_m=estimated_height,
        wingspan_m=wingspan,
        wingspan_height_ratio=_safe_ratio(wingspan, estimated_height),
        upper_body_m=upper_body,
        lower_body_m=lower_body,
        upper_lower_ratio=_safe_ratio(upper_body, lower_body),
        shoulder_width_m=shoulder_width,
        hip_width_m=hip_width,
        shoulder_hip_ratio=_safe_ratio(shoulder_width, hip_width),
        right_arm_m=right_arm,
        left_arm_m=left_arm,
        arm_asymmetry=_asymmetry(left_arm, right_arm),
        right_leg_m=right_leg,
        left_leg_m=left_leg,
        leg_asymmetry=_asymmetry(left_leg, right_leg),
    )


def estimate_height_from_keypoints(
    keypoints_3d: NDArray[np.float64],
) -> float:
    """
    키포인트로부터 신장 추정 (m).

    heel(발뒤꿈치)이 유효하면 head_top~heel 수직거리, 아니면 ankle에
    해부학적 보정(~3.9%)을 적용합니다. calculate_proportions와 동일 로직.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        추정 신장 (m)
    """
    return _estimate_height(keypoints_3d)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 상수
    "MIN_VALID_DISTANCE_M",
    "MAX_ASYMMETRY_RATIO",
    # 데이터클래스
    "BodyProportions",
    "SegmentLengths",
    # 함수
    "calculate_segment_lengths",
    "calculate_proportions",
    "estimate_height_from_keypoints",
]

__version__ = "1.0.0"
