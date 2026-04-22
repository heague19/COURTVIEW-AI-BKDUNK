# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: force_estimator.py
설명: 역동역학 기반 관절 힘/토크 추정 모듈
      - Newton-Euler 역동역학: F = m·a (선형 힘), τ = I·α (회전 토크)
      - 지면반력(GRF) 추정: Newton 제2법칙 기반
      - 접촉력 분류: 파울 판정 보조
      - 관절 스트레스 평가: 부상 위험 판정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.5.
    - Robertson, D.G.E. et al. (2014). Research Methods in Biomechanics, Ch.4.
    - McNitt-Gray, J.L. (1993). Kinetics of the lower extremities during
      drop landings from three heights. J Biomech, 26(9), 1037-1046.
    - Newton 제2법칙: F = m·a (선형), τ = I·α (회전)
    - GRF 추정: F_grf = m·(g + a_vertical)

의존성:
    - shared/constants/biomechanics_constants.py: GRF/접촉력 임계치, BodySegment
    - shared/constants/pose_constants.py: JointType
    - biomechanics/anthropometry/body_segment.py: BodyModel, GRAVITY
    - biomechanics/kinematics/acceleration_analyzer.py: JointAcceleration, FrameAccelerations

사용처:
    - biomechanics/dynamics/momentum_calculator.py: 힘 데이터 참조
    - biomechanics/dynamics/impact_analyzer.py: GRF 기반 착지 충격 분석
    - biomechanics/data_extraction/: DTO 변환 시 ForceEstimate 생성
    - ai_referee/: 접촉 강도 판정
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    BodySegment,
    VERTICAL_GRF_WALKING_BW,
    VERTICAL_GRF_RUNNING_BW,
    VERTICAL_GRF_JUMP_LANDING_BW,
    VERTICAL_GRF_MAX_SAFE_BW,
    CONTACT_FORCE_LIGHT_BW,
    CONTACT_FORCE_MODERATE_BW,
    CONTACT_FORCE_HEAVY_BW,
    CONTACT_FORCE_EXCESSIVE_BW,
)
from shared.constants.pose_constants import (
    JointType,
    UK25_NECK,
    UK25_R_HIP,
    UK25_L_HIP,
)

from biomechanics.anthropometry.body_segment import (
    BodyModel,
    GRAVITY,
)
from biomechanics.kinematics.acceleration_analyzer import (
    JointAcceleration,
    BodyAcceleration,
    FrameAccelerations,
)


# =============================================================================
# 상수
# =============================================================================

# 최소 시간 간격 (0-division 방지)
_MIN_DT: Final[float] = 1e-6

# cm/s² → m/s² 변환 계수
_CM_TO_M: Final[float] = 0.01

# deg/s² → rad/s² 변환 계수
_DEG_TO_RAD: Final[float] = math.pi / 180.0

# 최대 관절 힘 (N) — 이상치 필터
# 인체 최대 관절 힘 ~5000N (역도 등 극한 상황)
# 참조: Zheng et al. (2000), knee joint forces during jumping
_MAX_JOINT_FORCE_N: Final[float] = 5000.0

# 최대 관절 토크 (N·m) — 이상치 필터
# 무릎 최대 토크 ~300 N·m (프로 운동선수 점프)
# 참조: Bisseling & Hof (2006), peak knee moments
_MAX_JOINT_TORQUE_NM: Final[float] = 500.0

# 최대 GRF (체중 배수) — 이상치 필터
# 10BW 초과는 측정 오류로 간주
_MAX_GRF_BW: Final[float] = 10.0

# 최대 수직 COM 가속도 (m/s²) — 이상치 필터
# ±50 m/s² 초과는 트래킹 노이즈
_MAX_VERTICAL_COM_ACCEL: Final[float] = 50.0

# COM 프록시 인덱스 (SSOT): 목 + 양쪽 골반 3점 평균
# 참조: Gard et al. (2004), COM proxy validation
_COM_PROXY_INDICES: Final[tuple[int, ...]] = (UK25_NECK, UK25_R_HIP, UK25_L_HIP)

# 관절 → 원위 세그먼트 매핑
# 해당 관절 아래(distal) 방향의 세그먼트
# F_joint ≈ m_segment × a_joint (단일 세그먼트 근사)
# 참조: Winter (2009) Ch.5: simplified inverse dynamics
_JOINT_TO_DISTAL_SEGMENT: Final[dict[JointType, BodySegment]] = {
    # 우측 상지
    JointType.RIGHT_SHOULDER: BodySegment.UPPER_ARM,
    JointType.RIGHT_ELBOW: BodySegment.FOREARM,
    JointType.RIGHT_WRIST: BodySegment.HAND,
    # 좌측 상지
    JointType.LEFT_SHOULDER: BodySegment.UPPER_ARM,
    JointType.LEFT_ELBOW: BodySegment.FOREARM,
    JointType.LEFT_WRIST: BodySegment.HAND,
    # 우측 하지
    JointType.RIGHT_HIP: BodySegment.THIGH,
    JointType.RIGHT_KNEE: BodySegment.SHANK,
    JointType.RIGHT_ANKLE: BodySegment.FOOT,
    # 좌측 하지
    JointType.LEFT_HIP: BodySegment.THIGH,
    JointType.LEFT_KNEE: BodySegment.SHANK,
    JointType.LEFT_ANKLE: BodySegment.FOOT,
}


# =============================================================================
# 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class JointForce:
    """
    단일 관절의 힘/토크 추정값.

    Newton-Euler 역동역학 기반 (단일 세그먼트 근사):
    - F = m_distal × a (선형 힘)
    - τ = I_distal × α (토크)

    Attributes:
        joint_type: 관절 유형
        force_vector: 힘 벡터 (Fx, Fy, Fz) N
        magnitude: 힘 크기 N
        torque_nm: 관절 토크 N·m
        body_weight_ratio: 체중 대비 힘 비율 (무차원)
    """

    joint_type: JointType
    force_vector: tuple[float, float, float]
    magnitude: float
    torque_nm: float
    body_weight_ratio: float


@dataclass(frozen=True, slots=True)
class GroundReactionForce:
    """
    지면반력 (GRF) 추정값.

    Newton 제2법칙 기반:
        GRF_vertical = m × (g + a_vertical)
    양발 합력 (단일 힘 벡터).

    Attributes:
        vertical_n: 수직 GRF (N, +위)
        horizontal_n: 수평 GRF (N)
        magnitude_n: GRF 크기 (N)
        body_weight_multiple: 체중 대비 배수 (무차원)
        is_safe: 안전 범위 여부 (< VERTICAL_GRF_MAX_SAFE_BW)

    참조:
        McNitt-Gray (1993): 착지 시 GRF 2~11BW
        Bressel & Cronin (2005): 농구 착지 평균 4.6BW
    """

    vertical_n: float
    horizontal_n: float
    magnitude_n: float
    body_weight_multiple: float
    is_safe: bool


@dataclass(frozen=True, slots=True)
class FrameForces:
    """
    프레임 단위 모든 힘 데이터.

    Attributes:
        joint_forces: 관절별 힘 추정값
        ground_reaction: 지면반력 (추정 가능 시)
        total_internal_force_n: 내부 관절 힘 합계 (N)
        max_joint_force_n: 최대 관절 힘 (N)
        dt: 시간 간격 (초)
    """

    joint_forces: dict[JointType, JointForce]
    ground_reaction: GroundReactionForce | None
    total_internal_force_n: float
    max_joint_force_n: float
    dt: float


# =============================================================================
# 관절 힘/토크 계산
# =============================================================================

def calculate_joint_force(
    joint_type: JointType,
    joint_accel: JointAcceleration,
    body_model: BodyModel,
) -> JointForce | None:
    """
    단일 관절 힘/토크 계산 (Newton-Euler 역동역학).

    단일 세그먼트 근사 (simplified inverse dynamics):
    - F = m_distal × a_joint (선형 힘)
    - τ = I_distal × α_joint (토크)

    전체 역동역학 체인(모든 원위 세그먼트 합산)과 달리
    단일 세그먼트만 고려하므로 실제값보다 과소추정.
    ±15~25% 오차 범위 (Winter, 2009).

    Args:
        joint_type: 관절 유형
        joint_accel: 해당 관절의 가속도 데이터 (cm/s², deg/s²)
        body_model: 신체 모델 (세그먼트 질량/관성 포함)

    Returns:
        JointForce 객체 (매핑 없거나 이상치일 때 None)

    참조:
        Winter (2009) Ch.5: Inverse dynamics
        Robertson et al. (2014) Ch.4: Force estimation
    """
    segment_type = _JOINT_TO_DISTAL_SEGMENT.get(joint_type)
    if segment_type is None:
        return None

    props = body_model.segments.get(segment_type)
    if props is None:
        return None

    # 선가속도: cm/s² → m/s²
    ax_m = joint_accel.acceleration[0] * _CM_TO_M
    ay_m = joint_accel.acceleration[1] * _CM_TO_M
    az_m = joint_accel.acceleration[2] * _CM_TO_M

    # F = m × a (N)
    mass = props.mass_kg
    fx = mass * ax_m
    fy = mass * ay_m
    fz = mass * az_m
    magnitude = (fx ** 2 + fy ** 2 + fz ** 2) ** 0.5

    if magnitude > _MAX_JOINT_FORCE_N:
        return None

    # τ = I × α (N·m)
    # angular_acceleration: deg/s² → rad/s²
    alpha_rad = joint_accel.angular_acceleration * _DEG_TO_RAD
    torque = props.moment_of_inertia * alpha_rad

    # 토크 이상치: 힘은 유효하되 토크만 무효화
    if abs(torque) > _MAX_JOINT_TORQUE_NM:
        torque = 0.0

    # 체중 대비 비율
    body_weight = body_model.body_mass_kg * GRAVITY
    bw_ratio = magnitude / body_weight if body_weight > 0 else 0.0

    return JointForce(
        joint_type=joint_type,
        force_vector=(fx, fy, fz),
        magnitude=magnitude,
        torque_nm=abs(torque),
        body_weight_ratio=bw_ratio,
    )


# =============================================================================
# 지면반력 (GRF) 추정
# =============================================================================

def estimate_vertical_com_acceleration(
    kp_prev: NDArray[np.float64],
    kp_curr: NDArray[np.float64],
    kp_next: NDArray[np.float64],
    dt: float,
) -> float | None:
    """
    수직 COM 가속도 추정 (중앙차분법).

    COM 프록시: 목(1) + 양쪽 골반(8, 11) 평균의 y좌표.
    a_y = [y(t+dt) - 2·y(t) + y(t-dt)] / dt²

    양의 값 = 위로 가속 (점프 push-off)
    음의 값 = 아래로 가속 (착지, 하강)

    Args:
        kp_prev: 이전 프레임 키포인트 (25×3/4)
        kp_curr: 현재 프레임 키포인트
        kp_next: 다음 프레임 키포인트
        dt: 프레임 간 시간 간격 (초)

    Returns:
        수직 COM 가속도 (m/s², +위, -아래), 계산 불가 시 None

    참조:
        Winter (2009) Ch.3: 중앙차분법
        Gard et al. (2004): COM 프록시 유효성
    """
    if dt < _MIN_DT:
        return None

    min_rows = max(_COM_PROXY_INDICES) + 1
    if (kp_prev.shape[0] < min_rows
            or kp_curr.shape[0] < min_rows
            or kp_next.shape[0] < min_rows):
        return None

    # COM 프록시: 목 + 양쪽 골반의 y좌표 평균 (y = 수직축)
    def _com_y(kp: NDArray[np.float64]) -> float:
        total = 0.0
        for idx in _COM_PROXY_INDICES:
            total += float(kp[idx, 1])
        return total / len(_COM_PROXY_INDICES)

    y_prev = _com_y(kp_prev)
    y_curr = _com_y(kp_curr)
    y_next = _com_y(kp_next)

    # 중앙차분: a = [y(t+dt) - 2·y(t) + y(t-dt)] / dt²
    # 키포인트 단위 cm → m 변환
    accel_cm_s2 = (y_next - 2.0 * y_curr + y_prev) / (dt ** 2)
    accel_m_s2 = accel_cm_s2 * _CM_TO_M

    # 이상치 필터
    if abs(accel_m_s2) > _MAX_VERTICAL_COM_ACCEL:
        return None

    return accel_m_s2


def estimate_ground_reaction_force(
    body_mass_kg: float,
    vertical_accel_m_s2: float | None = None,
    body_accel: BodyAcceleration | None = None,
) -> GroundReactionForce | None:
    """
    지면반력 (GRF) 추정.

    방법 1 (우선): 수직 COM 가속도 기반 (Newton 제2법칙)
        GRF_vertical = m × (g + a_vertical)

    방법 2 (대안): 이동 가속도 범주 기반 근사
        GRF ≈ m × g × 예상_배수

    Args:
        body_mass_kg: 체질량 (kg)
        vertical_accel_m_s2: 수직 COM 가속도 (m/s², +위, 선택)
        body_accel: 체 중심 가속도 (kinematics, 선택)

    Returns:
        GroundReactionForce 객체, 계산 불가 시 None

    참조:
        Newton 제2법칙: ΣF = m·a → GRF - mg = m·a_v → GRF = m(g + a_v)
        McNitt-Gray (1993): 착지 GRF 범위
    """
    if body_mass_kg <= 0:
        return None

    body_weight = body_mass_kg * GRAVITY

    if vertical_accel_m_s2 is not None:
        # 방법 1: Newton 제2법칙 직접 적용
        grf_vertical = body_mass_kg * (GRAVITY + vertical_accel_m_s2)

        # 음의 GRF = 공중 상태 (발이 지면에서 떨어짐)
        if grf_vertical < 0:
            grf_vertical = 0.0

        # 수평 GRF: 수평 가속도 기반 추정
        grf_horizontal = 0.0
        if body_accel is not None:
            grf_horizontal = body_mass_kg * abs(body_accel.acceleration_m_s2)

    elif body_accel is not None:
        # 방법 2: 가속도 범주 → GRF 배수 근사
        category = body_accel.acceleration_category
        grf_multiplier = 1.0  # 기본: 정지 (1BW)

        if "explosive" in category or "hard_stop" in category:
            grf_multiplier = VERTICAL_GRF_JUMP_LANDING_BW
        elif "quick" in category:
            grf_multiplier = VERTICAL_GRF_RUNNING_BW
        elif "normal" in category:
            grf_multiplier = VERTICAL_GRF_WALKING_BW

        grf_vertical = body_weight * grf_multiplier
        grf_horizontal = body_mass_kg * abs(body_accel.acceleration_m_s2)

    else:
        return None

    magnitude = (grf_vertical ** 2 + grf_horizontal ** 2) ** 0.5
    bw_multiple = magnitude / body_weight if body_weight > 0 else 0.0

    # 이상치 필터
    if bw_multiple > _MAX_GRF_BW:
        return None

    is_safe = bw_multiple <= VERTICAL_GRF_MAX_SAFE_BW

    return GroundReactionForce(
        vertical_n=grf_vertical,
        horizontal_n=grf_horizontal,
        magnitude_n=magnitude,
        body_weight_multiple=bw_multiple,
        is_safe=is_safe,
    )


# =============================================================================
# 접촉력 분류 (AI 심판 보조)
# =============================================================================

def classify_contact_force(
    force_magnitude_n: float,
    body_weight_n: float,
) -> str:
    """
    접촉력 분류 (파울 판정 보조).

    체중 대비 접촉력 비율로 강도 분류.
    ai_referee 모듈에서 접촉 이벤트 시 호출하여
    파울 유형 판정에 활용합니다.

    Args:
        force_magnitude_n: 접촉력 크기 (N)
        body_weight_n: 피접촉자 체중 (N)

    Returns:
        접촉력 분류:
        - "negligible": 무시할 수준 (<0.3BW)
        - "light": 경미 접촉 (0.3~0.8BW)
        - "moderate": 보통 접촉 (0.8~1.5BW)
        - "heavy": 강한 접촉 (1.5~3.0BW, 파울 의심)
        - "excessive": 과도한 접촉 (≥3.0BW, 플래그런트 의심)

    참조:
        FIBA/NBA 규정: 접촉 강도에 따른 파울 등급
    """
    if body_weight_n <= 0:
        return "negligible"

    ratio = force_magnitude_n / body_weight_n

    if ratio >= CONTACT_FORCE_EXCESSIVE_BW:
        return "excessive"
    if ratio >= CONTACT_FORCE_HEAVY_BW:
        return "heavy"
    if ratio >= CONTACT_FORCE_MODERATE_BW:
        return "moderate"
    if ratio >= CONTACT_FORCE_LIGHT_BW:
        return "light"
    return "negligible"


# =============================================================================
# 일괄 계산
# =============================================================================

def calculate_all_forces(
    body_model: BodyModel,
    frame_accelerations: FrameAccelerations,
    kp_prev: NDArray[np.float64] | None = None,
    kp_curr: NDArray[np.float64] | None = None,
    kp_next: NDArray[np.float64] | None = None,
) -> FrameForces:
    """
    프레임 단위 모든 관절 힘 + GRF 일괄 계산.

    Args:
        body_model: 신체 모델
        frame_accelerations: 프레임 가속도 데이터
        kp_prev: 이전 프레임 키포인트 (GRF용, 선택)
        kp_curr: 현재 프레임 키포인트 (선택)
        kp_next: 다음 프레임 키포인트 (선택)

    Returns:
        FrameForces 객체
    """
    dt = frame_accelerations.dt
    joint_forces: dict[JointType, JointForce] = {}

    for joint_type, accel in frame_accelerations.joint_accelerations.items():
        force = calculate_joint_force(joint_type, accel, body_model)
        if force is not None:
            joint_forces[joint_type] = force

    # GRF 추정
    vertical_accel: float | None = None

    if kp_prev is not None and kp_curr is not None and kp_next is not None:
        vertical_accel = estimate_vertical_com_acceleration(
            kp_prev, kp_curr, kp_next, dt,
        )

    grf = estimate_ground_reaction_force(
        body_model.body_mass_kg,
        vertical_accel,
        frame_accelerations.body_acceleration,
    )

    # 집계
    total_force = sum(jf.magnitude for jf in joint_forces.values())
    max_force = max(
        (jf.magnitude for jf in joint_forces.values()),
        default=0.0,
    )

    return FrameForces(
        joint_forces=joint_forces,
        ground_reaction=grf,
        total_internal_force_n=total_force,
        max_joint_force_n=max_force,
        dt=dt,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "JointForce",
    "GroundReactionForce",
    "FrameForces",
    # 관절 힘 계산
    "calculate_joint_force",
    # 지면반력 추정
    "estimate_ground_reaction_force",
    "estimate_vertical_com_acceleration",
    # 일괄 계산
    "calculate_all_forces",
    # 접촉력 분류
    "classify_contact_force",
]

__version__ = "1.0.0"
