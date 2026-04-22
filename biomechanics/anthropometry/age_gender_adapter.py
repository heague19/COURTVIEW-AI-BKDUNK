# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/anthropometry
파일: age_gender_adapter.py
설명: 연령/성별 기반 생체역학 파라미터 적응 모듈
      - 연령대 + 성별 조합의 통합 적응 프로파일 생성
      - 관절 각도 범위에 tolerance 적용
      - 기본 신체 파라미터 조회 (통일 인터페이스)
      - 적응된 BodyModel 생성 팩토리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Malina, R.M. et al. (2004). Growth, Maturation, and Physical Activity.
    - de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
      inertia parameters. Journal of Biomechanics, 29(9), 1223-1230.
    - ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender
    - biomechanics/standards/league_standards.py: get_standard, BiomechanicsStandard
    - biomechanics/standards/region_types.py: LeagueType, RegionType
    - biomechanics/anthropometry/body_segment.py: BodyModel, create_body_model

사용처:
    - biomechanics/kinematics/: 관절 각도 평가 시 적응 프로파일 참조
    - biomechanics/dynamics/: 힘/에너지 분석 시 적응된 body model 사용
    - motion_analysis/form_evaluation/: 연령/성별 적응 기준으로 폼 평가
    - feedback_system/: 연령/성별 맞춤 피드백 생성
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender

from biomechanics.standards.league_standards import (
    BiomechanicsStandard,
    get_standard,
    get_velocity_threshold,
)
from biomechanics.standards.region_types import LeagueType, RegionType
from biomechanics.standards import (
    youth_standards,
    teen_standards,
    adult_standards,
    senior_standards,
)
from biomechanics.anthropometry.body_segment import (
    BodyModel,
    create_body_model,
)


# =============================================================================
# 상수
# =============================================================================
# 관절 각도 해부학적 상/하한 (물리적으로 불가능한 범위 방지)
_ANGLE_FLOOR: Final[float] = 0.0      # 최소 각도 (도)
_ANGLE_CEILING: Final[float] = 180.0  # 최대 각도 (도)

# 비율형 값의 하한 (stance_width_shoulder_ratio 등)
_RATIO_FLOOR: Final[float] = 0.5
_RATIO_CEILING: Final[float] = 3.0

# 비율형 키 패턴 (각도가 아닌 비율 기준 키)
_RATIO_KEYS: frozenset[str] = frozenset({
    "stance_width_shoulder_ratio",
})


# =============================================================================
# 적응 프로파일 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class AgeGenderProfile:
    """
    연령/성별 통합 적응 프로파일.

    특정 연령/성별/리그 조합에 대해 모든 생체역학 파라미터를
    하나의 객체로 제공합니다. analysis 모듈에서 이 객체 하나로
    해당 선수 인구통계에 맞는 기준을 적용할 수 있습니다.

    Attributes:
        age: 나이 (세)
        age_group: 연령대
        gender: 성별
        league: 적용 리그
        default_height_cm: 기본 신장 (cm)
        default_weight_kg: 기본 체중 (kg)
        arm_span_ratio: 윙스팬/신장 비율
        leg_length_ratio: 다리 길이/신장 비율
        velocity_factor: 통합 속도 보정 계수 (연령 × 성별)
        rom_expansion_factor: ROM 확장/축소 계수
        angle_tolerance: 관절 각도 허용 마진 (도)
        max_jumps_per_session: 세션당 최대 점프 횟수
        max_shots_per_session: 세션당 최대 슛 횟수
        rest_between_high_impact: 고강도 동작 간 최소 휴식 (s)
        adapted_shooting_angles: tolerance 적용된 슈팅 각도 범위
        adapted_defensive_angles: tolerance 적용된 수비 각도 범위
        adapted_dribbling_angles: tolerance 적용된 드리블 각도 범위
        standard: 원본 BiomechanicsStandard 참조
    """

    age: int
    age_group: AgeGroup
    gender: Gender
    league: LeagueType

    # 신체 기본값
    default_height_cm: float
    default_weight_kg: float
    arm_span_ratio: float
    leg_length_ratio: float

    # 보정 계수
    velocity_factor: float
    rom_expansion_factor: float
    angle_tolerance: float

    # 안전 제한
    max_jumps_per_session: int
    max_shots_per_session: int
    rest_between_high_impact: float

    # tolerance 적용된 관절 각도
    adapted_shooting_angles: dict[str, tuple[float, float]]
    adapted_defensive_angles: dict[str, tuple[float, float]]
    adapted_dribbling_angles: dict[str, tuple[float, float]]

    # 원본 기준 참조 (상세 조회 시 사용)
    standard: BiomechanicsStandard


# =============================================================================
# 신체 기본값 조회 (통일 인터페이스)
# =============================================================================
def get_default_body_params(
    age: int,
    gender: Gender,
) -> tuple[float, float, float, float]:
    """
    연령/성별에 따른 기본 신체 파라미터 조회.

    4개 standards 모듈의 서로 다른 인터페이스를 통합하여
    단일 인터페이스로 제공합니다.

    Args:
        age: 나이 (세)
        gender: 성별

    Returns:
        (height_cm, weight_kg, arm_span_ratio, leg_length_ratio) 튜플
    """
    age_group = AgeGroup.from_age(age)

    if age_group == AgeGroup.YOUTH:
        return _get_youth_params(age, gender)
    if age_group == AgeGroup.TEEN:
        return _get_teen_params(age, gender)
    if age_group == AgeGroup.SENIOR:
        return _get_senior_params(age, gender)
    # ADULT
    return _get_adult_params(gender)


def _get_youth_params(
    age: int,
    gender: Gender,
) -> tuple[float, float, float, float]:
    """유소년 신체 파라미터 조회."""
    clamped = max(6, min(12, age))
    defaults = youth_standards.YOUTH_BODY_DEFAULTS[clamped]
    if gender == Gender.MALE:
        height = defaults.height_cm_male
        weight = defaults.weight_kg_male
    else:
        height = defaults.height_cm_female
        weight = defaults.weight_kg_female
    return (height, weight, defaults.arm_span_ratio, defaults.leg_length_ratio)


def _get_teen_params(
    age: int,
    gender: Gender,
) -> tuple[float, float, float, float]:
    """청소년 신체 파라미터 조회."""
    clamped = max(13, min(18, age))
    defaults = teen_standards.TEEN_BODY_DEFAULTS[clamped]
    if gender == Gender.MALE:
        height = defaults.height_cm_male
        weight = defaults.weight_kg_male
    else:
        height = defaults.height_cm_female
        weight = defaults.weight_kg_female
    return (height, weight, defaults.arm_span_ratio, defaults.leg_length_ratio)


def _get_adult_params(
    gender: Gender,
) -> tuple[float, float, float, float]:
    """성인 신체 파라미터 조회."""
    defaults = adult_standards.ADULT_BODY_DEFAULTS[gender]
    return (
        defaults.height_cm,
        defaults.weight_kg,
        defaults.arm_span_ratio,
        defaults.leg_length_ratio,
    )


def _get_senior_params(
    age: int,
    gender: Gender,
) -> tuple[float, float, float, float]:
    """시니어 신체 파라미터 조회."""
    # 시니어는 decade 기반 키로 조회
    if age < 60:
        key = "50s"
    elif age < 70:
        key = "60s"
    elif age < 80:
        key = "70s"
    else:
        key = "80+"
    defaults = senior_standards.SENIOR_BODY_DEFAULTS[key]
    if gender == Gender.MALE:
        height = defaults.height_cm_male
        weight = defaults.weight_kg_male
    else:
        height = defaults.height_cm_female
        weight = defaults.weight_kg_female
    return (height, weight, defaults.arm_span_ratio, defaults.leg_length_ratio)


# =============================================================================
# 관절 각도 범위 적응
# =============================================================================
def adapt_angle_range(
    angles: dict[str, tuple[float, float]],
    tolerance: float,
) -> dict[str, tuple[float, float]]:
    """
    관절 각도 범위에 tolerance를 적용하여 확장.

    성인 기준 각도에서 연령대별 tolerance를 적용합니다.
    하한은 tolerance만큼 줄이고, 상한은 tolerance만큼 늘립니다.
    해부학적 범위(0-180°)를 초과하지 않도록 클램핑합니다.

    비율형 값(stance_width_shoulder_ratio)은 각도가 아니므로
    별도 처리합니다.

    Args:
        angles: 원본 관절 각도 범위 {키: (하한, 상한)}
        tolerance: 허용 마진 (도)

    Returns:
        tolerance 적용된 각도 범위
    """
    if tolerance == 0.0:
        # 성인 기준: 보정 없음
        return dict(angles)

    adapted: dict[str, tuple[float, float]] = {}
    for key, (lo, hi) in angles.items():
        if key in _RATIO_KEYS:
            # 비율형 값: tolerance를 비율로 변환 (tolerance/100 만큼 확장)
            ratio_margin = tolerance / 100.0
            new_lo = max(_RATIO_FLOOR, lo - ratio_margin)
            new_hi = min(_RATIO_CEILING, hi + ratio_margin)
        else:
            # 각도형 값: tolerance 만큼 확장
            new_lo = max(_ANGLE_FLOOR, lo - tolerance)
            new_hi = min(_ANGLE_CEILING, hi + tolerance)
        adapted[key] = (new_lo, new_hi)

    return adapted


# =============================================================================
# 통합 프로파일 생성
# =============================================================================
def create_age_gender_profile(
    age: int,
    gender: Gender = Gender.MALE,
    league: LeagueType = LeagueType.FIBA,
    region: RegionType | None = None,
) -> AgeGenderProfile:
    """
    연령/성별/리그 조합의 통합 적응 프로파일 생성.

    이 함수가 age_gender_adapter 모듈의 핵심 진입점입니다.
    standards/ 모듈에서 기준값을 조회하고, tolerance를 적용하여
    바로 사용 가능한 적응 프로파일을 반환합니다.

    Args:
        age: 나이 (세)
        gender: 성별 (기본: 남성)
        league: 적용 리그 (기본: FIBA)
        region: 지역 유형 (None이면 리그 기본 지역)

    Returns:
        AgeGenderProfile 객체
    """
    age_group = AgeGroup.from_age(age)

    # 신체 기본값
    height_cm, weight_kg, arm_span_ratio, leg_length_ratio = (
        get_default_body_params(age, gender)
    )

    # 통합 생체역학 기준
    standard = get_standard(age_group, gender, league, region)

    # 통합 속도 보정 계수
    velocity_factor = get_velocity_threshold(age_group, gender)

    # tolerance 적용 관절 각도
    tol = standard.angle_tolerance
    adapted_shooting = adapt_angle_range(standard.shooting_angles, tol)
    adapted_defensive = adapt_angle_range(standard.defensive_angles, tol)
    adapted_dribbling = adapt_angle_range(standard.dribbling_angles, tol)

    return AgeGenderProfile(
        age=age,
        age_group=age_group,
        gender=gender,
        league=league,
        default_height_cm=height_cm,
        default_weight_kg=weight_kg,
        arm_span_ratio=arm_span_ratio,
        leg_length_ratio=leg_length_ratio,
        velocity_factor=velocity_factor,
        rom_expansion_factor=standard.rom_expansion_factor,
        angle_tolerance=tol,
        max_jumps_per_session=standard.max_jumps_per_session,
        max_shots_per_session=standard.max_shots_per_session,
        rest_between_high_impact=standard.rest_between_high_impact,
        adapted_shooting_angles=adapted_shooting,
        adapted_defensive_angles=adapted_defensive,
        adapted_dribbling_angles=adapted_dribbling,
        standard=standard,
    )


# =============================================================================
# 적응된 BodyModel 생성
# =============================================================================
def create_adapted_body_model(
    profile: AgeGenderProfile,
    height_cm: float | None = None,
    weight_kg: float | None = None,
) -> BodyModel:
    """
    적응 프로파일 기반 BodyModel 생성.

    개인 측정값이 없으면 프로파일의 기본값을 사용합니다.

    Args:
        profile: 연령/성별 적응 프로파일
        height_cm: 실제 신장 (cm). None이면 기본값 사용.
        weight_kg: 실제 체중 (kg). None이면 기본값 사용.

    Returns:
        BodyModel 객체
    """
    effective_height = height_cm if height_cm is not None else profile.default_height_cm
    effective_weight = weight_kg if weight_kg is not None else profile.default_weight_kg

    return create_body_model(
        body_mass_kg=effective_weight,
        height_cm=effective_height,
        gender=profile.gender,
        age_group=profile.age_group,
    )


# =============================================================================
# 유틸리티: 보정 계수 적용 헬퍼
# =============================================================================
def apply_velocity_factor(
    adult_velocity: float,
    profile: AgeGenderProfile,
) -> float:
    """
    성인 기준 속도에 연령/성별 보정 적용.

    Args:
        adult_velocity: 성인 남성 기준 속도 (m/s)
        profile: 적응 프로파일

    Returns:
        보정된 속도 (m/s)
    """
    return adult_velocity * profile.velocity_factor


def apply_rom_factor(
    adult_rom: tuple[float, float],
    profile: AgeGenderProfile,
) -> tuple[float, float]:
    """
    성인 기준 ROM에 연령별 확장/축소 적용.

    ROM 확장은 상한만 확장하고, ROM 축소는 상한을 줄입니다.
    하한은 유지합니다 (최소 가동 범위).

    참조: Quatman-Yates et al. (2012), 유소년 ROM은
          성인 대비 넓고, 시니어 ROM은 성인 대비 좁음.

    Args:
        adult_rom: 성인 ROM 범위 (하한, 상한) (도)
        profile: 적응 프로파일

    Returns:
        보정된 ROM 범위 (하한, 상한) (도)
    """
    lo, hi = adult_rom
    factor = profile.rom_expansion_factor
    rom_range = hi - lo
    adjusted_hi = lo + rom_range * factor
    # 해부학적 상한 제한
    adjusted_hi = min(_ANGLE_CEILING, adjusted_hi)
    return (lo, adjusted_hi)


def is_within_adapted_range(
    value: float,
    adapted_range: tuple[float, float],
) -> bool:
    """
    값이 적응된 범위 내에 있는지 확인.

    Args:
        value: 측정값
        adapted_range: 적응된 범위 (하한, 상한)

    Returns:
        범위 내이면 True
    """
    return adapted_range[0] <= value <= adapted_range[1]


def calculate_deviation(
    value: float,
    adapted_range: tuple[float, float],
) -> float:
    """
    값의 적응 범위로부터의 편차 계산.

    범위 내이면 0.0, 범위 밖이면 가장 가까운 경계로부터의 거리를 반환합니다.

    Args:
        value: 측정값
        adapted_range: 적응된 범위 (하한, 상한)

    Returns:
        편차 (도 또는 해당 단위). 범위 내 = 0.0
    """
    lo, hi = adapted_range
    if value < lo:
        return lo - value
    if value > hi:
        return value - hi
    return 0.0


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "AgeGenderProfile",
    # 핵심 함수
    "create_age_gender_profile",
    "create_adapted_body_model",
    # 신체 파라미터 조회
    "get_default_body_params",
    # 각도 적응
    "adapt_angle_range",
    # 보정 유틸리티
    "apply_velocity_factor",
    "apply_rom_factor",
    "is_within_adapted_range",
    "calculate_deviation",
]

__version__ = "1.0.0"
