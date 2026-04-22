# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/anthropometry
파일: body_segment.py
설명: 신체 세그먼트 모델링 모듈
      - de Leva (1996) 인체측정 모델 기반 세그먼트 물리량 계산
      - 세그먼트별 질량, 길이, 무게중심, 관성 모멘트 산출
      - 전신 무게중심(COM) 계산
      - 연령대/성별 보정 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia
      parameters. Journal of Biomechanics, 29(9), 1223-1230.
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement.
    - Drillis, R. & Contini, R. (1966). Body Segment Parameters.

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender
    - shared/constants/biomechanics_constants.py: BodySegment, 세그먼트 데이터
    - biomechanics/standards/: 연령대별 보정 계수

사용처:
    - biomechanics/dynamics/: 힘/토크 계산 시 세그먼트 질량/관성 필요
    - biomechanics/kinematics/: 관절 위치 → 세그먼트 COM 추정
    - biomechanics/anthropometry/proportion_calculator.py: 신체 비율 계산
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.biomechanics_constants import (
    BodySegment,
    SEGMENT_MASS_RATIO_MALE,
    SEGMENT_MASS_RATIO_FEMALE,
    SEGMENT_LENGTH_RATIO,
    SEGMENT_COM_PROXIMAL_MALE,
    SEGMENT_COM_PROXIMAL_FEMALE,
    SEGMENT_GYRATION_RADIUS_MALE,
    SEGMENT_GYRATION_RADIUS_FEMALE,
    AGE_TRUNK_MASS_FACTOR,
    AGE_LIMB_LENGTH_FACTOR,
)
from shared.constants.pose_constants import (
    UK25_NECK,
    UK25_R_SHOULDER, UK25_R_ELBOW, UK25_R_WRIST,
    UK25_L_SHOULDER, UK25_L_ELBOW, UK25_L_WRIST,
    UK25_R_HIP, UK25_R_KNEE, UK25_R_ANKLE,
    UK25_L_HIP, UK25_L_KNEE, UK25_L_ANKLE,
    UK25_L_BIG_TOE, UK25_R_BIG_TOE,
    UK25_HEAD_TOP, UK25_R_FINGERTIP, UK25_L_FINGERTIP,
)


def get_segment_mass_ratio(segment: BodySegment, gender: Gender) -> float:
    """성별에 따른 세그먼트 질량비 반환 (de Leva 1996)."""
    if gender == Gender.MALE:
        return SEGMENT_MASS_RATIO_MALE[segment]
    return SEGMENT_MASS_RATIO_FEMALE[segment]


def get_segment_com_proximal(segment: BodySegment, gender: Gender) -> float:
    """성별에 따른 세그먼트 근위단 기준 COM 비율 반환."""
    if gender == Gender.MALE:
        return SEGMENT_COM_PROXIMAL_MALE[segment]
    return SEGMENT_COM_PROXIMAL_FEMALE[segment]


# =============================================================================
# 상수
# =============================================================================
GRAVITY: Final[float] = 9.80665          # 표준 중력가속도 (m/s²)
DEFAULT_BODY_MASS: Final[float] = 75.0   # 기본 체중 (kg)
DEFAULT_HEIGHT: Final[float] = 175.0     # 기본 신장 (cm)
MIN_BODY_MASS: Final[float] = 15.0      # 최소 체중 (kg, 유소년 하한)
MAX_BODY_MASS: Final[float] = 200.0     # 최대 체중 (kg)
MIN_HEIGHT: Final[float] = 90.0         # 최소 신장 (cm, 유소년 하한)
MAX_HEIGHT: Final[float] = 240.0        # 최대 신장 (cm)

# 체간 세그먼트 (질량 보정에 사용)
_TRUNK_SEGMENTS: frozenset[BodySegment] = frozenset({
    BodySegment.HEAD,
    BodySegment.NECK,
    BodySegment.TRUNK_UPPER,
    BodySegment.TRUNK_LOWER,
})

# 사지 세그먼트 (길이 보정에 사용)
_LIMB_SEGMENTS: frozenset[BodySegment] = frozenset({
    BodySegment.UPPER_ARM,
    BodySegment.FOREARM,
    BodySegment.HAND,
    BodySegment.THIGH,
    BodySegment.SHANK,
    BodySegment.FOOT,
})


# =============================================================================
# 세그먼트 물리량 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class SegmentProperties:
    """
    단일 세그먼트의 물리적 특성.

    Attributes:
        segment: 세그먼트 유형
        mass_kg: 질량 (kg)
        length_m: 길이 (m)
        com_proximal_ratio: 근위단 기준 COM 위치 비율 (0-1)
        com_position_m: 근위단 기준 COM 위치 (m)
        gyration_radius_ratio: 회전 반경 / 세그먼트 길이
        moment_of_inertia: 관성 모멘트 (kg·m²)
        weight_n: 무게 (N)
    """

    segment: BodySegment
    mass_kg: float
    length_m: float
    com_proximal_ratio: float
    com_position_m: float
    gyration_radius_ratio: float
    moment_of_inertia: float
    weight_n: float


@dataclass(slots=True)
class BodyModel:
    """
    전신 신체 모델.

    모든 세그먼트의 물리적 특성을 포함하며,
    전신 무게중심(COM) 계산의 기반 데이터입니다.

    Attributes:
        body_mass_kg: 전체 체중 (kg)
        height_cm: 신장 (cm)
        gender: 성별
        age_group: 연령대
        segments: 세그먼트별 물리적 특성
    """

    body_mass_kg: float
    height_cm: float
    gender: Gender
    age_group: AgeGroup
    segments: dict[BodySegment, SegmentProperties]


# =============================================================================
# 세그먼트 물리량 계산 함수
# =============================================================================
def calculate_segment_mass(
    segment: BodySegment,
    body_mass_kg: float,
    gender: Gender,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> float:
    """
    세그먼트 질량 계산 (kg).

    Args:
        segment: 신체 세그먼트
        body_mass_kg: 전체 체중 (kg)
        gender: 성별
        age_group: 연령대 (보정 적용)

    Returns:
        세그먼트 질량 (kg)
    """
    ratio = get_segment_mass_ratio(segment, gender)

    # 연령대별 체간/사지 질량 보정
    if segment in _TRUNK_SEGMENTS:
        ratio *= AGE_TRUNK_MASS_FACTOR[age_group]
    # 사지는 보정 없음 (de Leva 모델의 사지 질량비는 연령 불변)

    return body_mass_kg * ratio


def calculate_segment_length(
    segment: BodySegment,
    height_cm: float,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> float:
    """
    세그먼트 길이 계산 (m).

    Args:
        segment: 신체 세그먼트
        height_cm: 신장 (cm)
        age_group: 연령대

    Returns:
        세그먼트 길이 (m)
    """
    height_m = height_cm / 100.0
    ratio = SEGMENT_LENGTH_RATIO[segment]

    # 연령대별 사지 길이 보정
    if segment in _LIMB_SEGMENTS:
        ratio *= AGE_LIMB_LENGTH_FACTOR[age_group]

    return height_m * ratio


def calculate_segment_com_position(
    segment: BodySegment,
    segment_length_m: float,
    gender: Gender,
) -> float:
    """
    세그먼트 무게중심 위치 계산 (m, 근위단 기준).

    Args:
        segment: 신체 세그먼트
        segment_length_m: 세그먼트 길이 (m)
        gender: 성별

    Returns:
        근위단으로부터 COM까지 거리 (m)
    """
    ratio = get_segment_com_proximal(segment, gender)
    return segment_length_m * ratio


def calculate_segment_moment_of_inertia(
    segment: BodySegment,
    segment_mass_kg: float,
    segment_length_m: float,
    gender: Gender,
) -> float:
    """
    세그먼트 관성 모멘트 계산 (kg·m², COM 기준).

    I = m × (k × L)²
    여기서 k = 회전 반경 / 세그먼트 길이, L = 세그먼트 길이

    Args:
        segment: 신체 세그먼트
        segment_mass_kg: 세그먼트 질량 (kg)
        segment_length_m: 세그먼트 길이 (m)
        gender: 성별

    Returns:
        관성 모멘트 (kg·m²)
    """
    if gender == Gender.MALE:
        k = SEGMENT_GYRATION_RADIUS_MALE[segment]
    else:
        k = SEGMENT_GYRATION_RADIUS_FEMALE[segment]

    radius = k * segment_length_m
    return segment_mass_kg * radius * radius


def calculate_segment_properties(
    segment: BodySegment,
    body_mass_kg: float,
    height_cm: float,
    gender: Gender,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> SegmentProperties:
    """
    세그먼트의 모든 물리적 특성 계산.

    Args:
        segment: 신체 세그먼트
        body_mass_kg: 전체 체중 (kg)
        height_cm: 신장 (cm)
        gender: 성별
        age_group: 연령대

    Returns:
        SegmentProperties 객체
    """
    mass = calculate_segment_mass(segment, body_mass_kg, gender, age_group)
    length = calculate_segment_length(segment, height_cm, age_group)
    com_ratio = get_segment_com_proximal(segment, gender)
    com_pos = length * com_ratio

    if gender == Gender.MALE:
        gyration_ratio = SEGMENT_GYRATION_RADIUS_MALE[segment]
    else:
        gyration_ratio = SEGMENT_GYRATION_RADIUS_FEMALE[segment]

    moi = calculate_segment_moment_of_inertia(segment, mass, length, gender)
    weight = mass * GRAVITY

    return SegmentProperties(
        segment=segment,
        mass_kg=mass,
        length_m=length,
        com_proximal_ratio=com_ratio,
        com_position_m=com_pos,
        gyration_radius_ratio=gyration_ratio,
        moment_of_inertia=moi,
        weight_n=weight,
    )


# =============================================================================
# 전신 모델 생성
# =============================================================================
def create_body_model(
    body_mass_kg: float = DEFAULT_BODY_MASS,
    height_cm: float = DEFAULT_HEIGHT,
    gender: Gender = Gender.MALE,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> BodyModel:
    """
    전신 신체 모델 생성.

    모든 10개 세그먼트의 물리적 특성을 계산하여 반환합니다.

    Args:
        body_mass_kg: 전체 체중 (kg)
        height_cm: 신장 (cm)
        gender: 성별
        age_group: 연령대

    Returns:
        BodyModel 객체

    Raises:
        ValueError: 체중/신장 범위 초과
    """
    if not MIN_BODY_MASS <= body_mass_kg <= MAX_BODY_MASS:
        raise ValueError(
            f"체중은 {MIN_BODY_MASS}~{MAX_BODY_MASS}kg 범위여야 합니다. "
            f"입력값: {body_mass_kg}kg"
        )
    if not MIN_HEIGHT <= height_cm <= MAX_HEIGHT:
        raise ValueError(
            f"신장은 {MIN_HEIGHT}~{MAX_HEIGHT}cm 범위여야 합니다. "
            f"입력값: {height_cm}cm"
        )

    segments: dict[BodySegment, SegmentProperties] = {}
    for seg in BodySegment:
        segments[seg] = calculate_segment_properties(
            seg, body_mass_kg, height_cm, gender, age_group,
        )

    return BodyModel(
        body_mass_kg=body_mass_kg,
        height_cm=height_cm,
        gender=gender,
        age_group=age_group,
        segments=segments,
    )


# =============================================================================
# 전신 무게중심 (COM) 계산
# =============================================================================
def calculate_whole_body_com(
    keypoints_3d: NDArray[np.float64],
    body_model: BodyModel,
    segment_endpoint_indices: dict[str, tuple[int, int]] | None = None,
) -> NDArray[np.float64]:
    """
    전신 무게중심 (COM) 좌표 계산.

    각 세그먼트의 COM 위치를 질량 가중 평균하여 전신 COM을 구합니다.
    양측성 세그먼트(팔, 다리)는 좌/우 각각 기여합니다.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (N×3 또는 N×4, 마지막 열이 confidence인 경우)
        body_model: 신체 모델
        segment_endpoint_indices: 세그먼트 이름 → (근위, 원위) 키포인트 인덱스
            None이면 SEGMENT_ENDPOINT_INDICES_25KP (기본 Unified 25kp) 사용

    Returns:
        전신 COM 좌표 [x, y, z] (float64).
        양측성 세그먼트(팔/다리)는 좌/우 각각 절반 질량으로 기여하여
        총 질량이 body_mass_kg와 일치하도록 유지됩니다.
    """
    if segment_endpoint_indices is None:
        segment_endpoint_indices = SEGMENT_ENDPOINT_INDICES_25KP

    coords = keypoints_3d[:, :3] if keypoints_3d.shape[1] > 3 else keypoints_3d

    total_mass = 0.0
    weighted_sum = np.zeros(3, dtype=np.float64)

    for name, (proximal_idx, distal_idx) in segment_endpoint_indices.items():
        seg_type = _SEGMENT_NAME_TO_TYPE.get(name)
        if seg_type is None:
            continue

        props = body_model.segments.get(seg_type)
        if props is None:
            continue

        proximal = coords[proximal_idx]
        distal = coords[distal_idx]

        # NaN/Inf guard
        if not (np.all(np.isfinite(proximal)) and np.all(np.isfinite(distal))):
            continue

        # 세그먼트 COM 위치 = 근위 + ratio × (원위 - 근위)
        seg_com = proximal + props.com_proximal_ratio * (distal - proximal)

        # 양측 분할 세그먼트(L/R 쌍)는 한쪽당 질량 절반 기여 — 총 질량 보존
        mass = props.mass_kg * 0.5 if name in _BILATERAL_SEGMENT_NAMES else props.mass_kg

        weighted_sum += mass * seg_com
        total_mass += mass

    if total_mass > 0:
        return weighted_sum / total_mass
    return np.zeros(3, dtype=np.float64)


def calculate_segment_weight(
    segment: BodySegment,
    body_mass_kg: float,
    gender: Gender,
) -> float:
    """
    세그먼트 무게 계산 (N).

    Args:
        segment: 신체 세그먼트
        body_mass_kg: 전체 체중 (kg)
        gender: 성별

    Returns:
        세그먼트 무게 (N)
    """
    mass = body_mass_kg * get_segment_mass_ratio(segment, gender)
    return mass * GRAVITY


def estimate_body_mass_from_height(
    height_cm: float,
    gender: Gender,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> float:
    """
    신장으로부터 체중 추정 (BMI 기반).

    개인 체중 데이터가 없을 때 사용합니다.
    평균 BMI 기반: 남성 23.5, 여성 22.0

    Args:
        height_cm: 신장 (cm)
        gender: 성별
        age_group: 연령대

    Returns:
        추정 체중 (kg)
    """
    height_m = height_cm / 100.0

    if gender == Gender.MALE:
        bmi = 23.5
    else:
        bmi = 22.0

    # 연령대별 BMI 보정
    bmi_adjustment: dict[AgeGroup, float] = {
        AgeGroup.YOUTH: -3.5,      # 유소년: BMI가 낮음
        AgeGroup.TEEN: -1.0,       # 청소년: 약간 낮음
        AgeGroup.ADULT: 0.0,       # 기준
        AgeGroup.SENIOR: 0.5,      # 시니어: 약간 높음
    }
    adjusted_bmi = bmi + bmi_adjustment[age_group]

    weight = adjusted_bmi * height_m * height_m
    return max(MIN_BODY_MASS, min(MAX_BODY_MASS, weight))


# =============================================================================
# 키포인트-세그먼트 매핑 (Unified 25 키포인트 기준)
# =============================================================================
# 키포인트 인덱스 → BodySegment 매핑 (SSOT: shared.constants.pose_constants)
#
# 모든 인덱스는 UK25_* 상수에서 import. 하드코딩 금지.
# =============================================================================

# 세그먼트 → (근위 인덱스, 원위 인덱스) 매핑 (좌/우 분리)
# 양측성 세그먼트(상지/하지)는 좌/우 엔드포인트를 각각 정의합니다.
SEGMENT_ENDPOINT_INDICES_25KP: Final[dict[str, tuple[int, int]]] = {
    # 체간 (머리/목)
    "head":        (UK25_NECK, UK25_HEAD_TOP),       # 목 → 머리꼭대기
    "neck":        (UK25_NECK, UK25_NECK),           # 단일점 (길이 0)
    # 체간(상부): 좌/우 골반을 각각 엔드포인트로 두고 절반 질량씩 배분
    # → calculate_whole_body_com에서 대칭 평균으로 중심선 근사
    "trunk_upper_r": (UK25_NECK, UK25_R_HIP),
    "trunk_upper_l": (UK25_NECK, UK25_L_HIP),
    # 우측 상지
    "r_upper_arm": (UK25_R_SHOULDER, UK25_R_ELBOW),
    "r_forearm":   (UK25_R_ELBOW, UK25_R_WRIST),
    "r_hand":      (UK25_R_WRIST, UK25_R_FINGERTIP),
    # 좌측 상지
    "l_upper_arm": (UK25_L_SHOULDER, UK25_L_ELBOW),
    "l_forearm":   (UK25_L_ELBOW, UK25_L_WRIST),
    "l_hand":      (UK25_L_WRIST, UK25_L_FINGERTIP),
    # 우측 하지
    "r_thigh":     (UK25_R_HIP, UK25_R_KNEE),
    "r_shank":     (UK25_R_KNEE, UK25_R_ANKLE),
    "r_foot":      (UK25_R_ANKLE, UK25_R_BIG_TOE),
    # 좌측 하지
    "l_thigh":     (UK25_L_HIP, UK25_L_KNEE),
    "l_shank":     (UK25_L_KNEE, UK25_L_ANKLE),
    "l_foot":      (UK25_L_ANKLE, UK25_L_BIG_TOE),
}

# 세그먼트 이름 → BodySegment 매핑
# 양측성 세그먼트는 좌/우 각각 엔트리를 가지며 COM 계산 시 질량 절반씩 배분
_SEGMENT_NAME_TO_TYPE: Final[dict[str, BodySegment]] = {
    "head": BodySegment.HEAD,
    "neck": BodySegment.NECK,
    "trunk_upper_r": BodySegment.TRUNK_UPPER,
    "trunk_upper_l": BodySegment.TRUNK_UPPER,
    "r_upper_arm": BodySegment.UPPER_ARM,
    "r_forearm": BodySegment.FOREARM,
    "r_hand": BodySegment.HAND,
    "l_upper_arm": BodySegment.UPPER_ARM,
    "l_forearm": BodySegment.FOREARM,
    "l_hand": BodySegment.HAND,
    "r_thigh": BodySegment.THIGH,
    "r_shank": BodySegment.SHANK,
    "r_foot": BodySegment.FOOT,
    "l_thigh": BodySegment.THIGH,
    "l_shank": BodySegment.SHANK,
    "l_foot": BodySegment.FOOT,
}

# 양측 분할 세그먼트 (각 엔트리가 질량 절반만 기여)
_BILATERAL_SEGMENT_NAMES: Final[frozenset[str]] = frozenset({
    "trunk_upper_r", "trunk_upper_l",
    "r_upper_arm", "l_upper_arm",
    "r_forearm", "l_forearm",
    "r_hand", "l_hand",
    "r_thigh", "l_thigh",
    "r_shank", "l_shank",
    "r_foot", "l_foot",
})


def get_segment_endpoints_25kp() -> dict[BodySegment, list[tuple[int, int]]]:
    """
    Unified 25kp 기준 세그먼트별 (근위, 원위) 인덱스 목록 반환.

    양측성 세그먼트는 좌/우 각각 포함됩니다.

    Returns:
        {BodySegment: [(proximal_idx, distal_idx), ...]}
    """
    result: dict[BodySegment, list[tuple[int, int]]] = {}
    for name, (prox, dist) in SEGMENT_ENDPOINT_INDICES_25KP.items():
        seg_type = _SEGMENT_NAME_TO_TYPE[name]
        if seg_type not in result:
            result[seg_type] = []
        result[seg_type].append((prox, dist))
    return result


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 상수
    "GRAVITY",
    "DEFAULT_BODY_MASS",
    "DEFAULT_HEIGHT",
    "MIN_BODY_MASS",
    "MAX_BODY_MASS",
    "MIN_HEIGHT",
    "MAX_HEIGHT",
    # 데이터클래스
    "SegmentProperties",
    "BodyModel",
    # 세그먼트 계산 함수
    "calculate_segment_mass",
    "calculate_segment_length",
    "calculate_segment_com_position",
    "calculate_segment_moment_of_inertia",
    "calculate_segment_properties",
    # 전신 모델
    "create_body_model",
    # COM 계산
    "calculate_whole_body_com",
    "calculate_segment_weight",
    "estimate_body_mass_from_height",
    # 키포인트-세그먼트 매핑
    "SEGMENT_ENDPOINT_INDICES_25KP",
    "get_segment_endpoints_25kp",
]

__version__ = "1.0.0"
