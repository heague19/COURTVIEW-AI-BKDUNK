# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: league_standards.py
설명: 리그별 생체역학 기준 통합 제공 모듈
      - 리그 + 연령대 + 성별 조합으로 기준값 조회
      - 4개 연령대 기준 모듈을 통합하여 단일 API 제공
      - 리그별 코트 규격 보정 (3점 거리, 코트 크기 등)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - biomechanics/standards/youth_standards.py
    - biomechanics/standards/teen_standards.py
    - biomechanics/standards/adult_standards.py
    - biomechanics/standards/senior_standards.py
    - biomechanics/standards/region_types.py

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender
    - biomechanics/standards/region_types.py: LeagueType, RegionType 등

사용처:
    - biomechanics/ 전체: 분석 시 기준값 조회 진입점
    - motion_analysis/form_evaluation/: 동작 평가 기준 조회
    - ai_referee/: 리그별 규칙 기반 생체역학 판정 기준
    - feedback_system/: 맞춤형 피드백 생성 시 기준 참조
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender

from biomechanics.standards.region_types import (
    LeagueType,
    RegionType,
    get_default_region,
    get_region_profile,
)
from biomechanics.standards import youth_standards
from biomechanics.standards import teen_standards
from biomechanics.standards import adult_standards
from biomechanics.standards import senior_standards


# =============================================================================
# 연령대 → 모듈 매핑
# =============================================================================
_AGE_MODULE_MAP = {
    AgeGroup.YOUTH: youth_standards,
    AgeGroup.TEEN: teen_standards,
    AgeGroup.ADULT: adult_standards,
    AgeGroup.SENIOR: senior_standards,
}


# =============================================================================
# 통합 기준 데이터 클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class BiomechanicsStandard:
    """
    특정 조건(연령대/성별/리그)에 대한 생체역학 기준 세트.

    각 분석 모듈에서 이 객체를 받아 해당 기준으로 평가합니다.

    Attributes:
        age_group: 연령대
        gender: 성별
        league: 적용 리그
        region: 지역 유형

        velocity_factor: 속도 보정 계수 (성인 남성 = 1.0)
        gender_velocity_factor: 성별 속도 보정 계수
        rom_expansion_factor: ROM 확장/축소 계수
        angle_tolerance: 각도 허용 마진 (도)

        shooting_angles: 슈팅 최적 관절 각도
        defensive_angles: 수비 자세 최적 각도
        dribbling_angles: 드리블 자세 최적 각도

        acceleration_normal: 일반 가속 범위 (m/s²)
        acceleration_quick: 빠른 가속 범위 (m/s²)
        acceleration_explosive: 폭발적 가속 임계치 (m/s²)
        deceleration_hard_stop: 급제동 임계치 (m/s²)

        shooting_elbow_angular_vel: 슈팅 팔꿈치 각속도 범위 (°/s)
        shooting_wrist_angular_vel: 슈팅 손목 각속도 범위 (°/s)
        passing_arm_angular_vel: 패스 팔 각속도 범위 (°/s)

        stability_min: 안정성 최소값
        cop_sway_stable: COP 동요 안정 임계치 (cm)
        cop_sway_unstable: COP 동요 불안정 임계치 (cm)
        stabilization_good: 착지 안정화 양호 시간 (s)
        stabilization_acceptable: 착지 안정화 보통 시간 (s)
        stabilization_poor: 착지 안정화 불량 시간 (s)

        grf_walking: 보행 GRF (체중 배수)
        grf_running: 달리기 GRF (체중 배수)
        grf_jump_landing: 점프 착지 GRF (체중 배수)
        grf_max_safe: 안전 GRF 상한 (체중 배수)
        impact_absorption_good: 충격 흡수 양호 (s)
        impact_absorption_poor: 충격 흡수 불량 (s)

        severity_warning: 심각도 경고 임계치 (도)
        severity_critical: 심각도 위험 임계치 (도)
        severity_severe: 심각도 심각 임계치 (도)

        max_jumps_per_session: 세션당 최대 점프 횟수
        max_shots_per_session: 세션당 최대 슛 횟수
        rest_between_high_impact: 고강도 동작 간 최소 휴식 (s)
    """

    age_group: AgeGroup
    gender: Gender
    league: LeagueType
    region: RegionType

    # 보정 계수
    velocity_factor: float
    gender_velocity_factor: float
    rom_expansion_factor: float
    angle_tolerance: float

    # 최적 관절 각도
    shooting_angles: dict[str, tuple[float, float]]
    defensive_angles: dict[str, tuple[float, float]]
    dribbling_angles: dict[str, tuple[float, float]]

    # 가속도
    acceleration_normal: tuple[float, float]
    acceleration_quick: tuple[float, float]
    acceleration_explosive: float
    deceleration_hard_stop: float

    # 각속도
    shooting_elbow_angular_vel: tuple[float, float]
    shooting_wrist_angular_vel: tuple[float, float]
    passing_arm_angular_vel: tuple[float, float]

    # 균형/안정성
    stability_min: float
    cop_sway_stable: float
    cop_sway_unstable: float
    stabilization_good: float
    stabilization_acceptable: float
    stabilization_poor: float

    # 동역학
    grf_walking: float
    grf_running: float
    grf_jump_landing: float
    grf_max_safe: float
    impact_absorption_good: float
    impact_absorption_poor: float

    # 피드백 심각도
    severity_warning: float
    severity_critical: float
    severity_severe: float

    # 세션 제한
    max_jumps_per_session: int
    max_shots_per_session: int
    rest_between_high_impact: float


# =============================================================================
# 기준 생성 팩토리 함수
# =============================================================================
def get_standard(
    age_group: AgeGroup,
    gender: Gender = Gender.MALE,
    league: LeagueType = LeagueType.FIBA,
    region: RegionType | None = None,
) -> BiomechanicsStandard:
    """
    연령대/성별/리그/지역 조합에 맞는 생체역학 기준 생성.

    이 함수가 standards/ 모듈의 핵심 진입점입니다.
    호출 측에서는 이 함수 하나로 모든 기준을 조회합니다.

    Args:
        age_group: 연령대
        gender: 성별 (기본: 남성)
        league: 적용 리그 (기본: FIBA)
        region: 지역 유형 (None이면 리그 기본 지역)

    Returns:
        해당 조건의 통합 기준 세트
    """
    mod = _AGE_MODULE_MAP[age_group]
    effective_region = region if region is not None else get_default_region(league)

    # 성별 속도 보정 계수 조회
    gender_vel_map = getattr(mod, f"GENDER_VELOCITY_FACTOR_{age_group.value.upper()}", None)
    if gender_vel_map is None:
        # fallback: 성인 기준
        gender_vel_factor = 1.0 if gender == Gender.MALE else 0.90
    else:
        gender_vel_factor = gender_vel_map[gender]

    # 슈팅 각도 조회
    shooting_key = f"SHOOTING_OPTIMAL_ANGLES_{age_group.value.upper()}"
    shooting_angles = getattr(mod, shooting_key)

    defensive_key = f"DEFENSIVE_STANCE_ANGLES_{age_group.value.upper()}"
    defensive_angles = getattr(mod, defensive_key)

    dribbling_key = f"DRIBBLING_STANCE_ANGLES_{age_group.value.upper()}"
    dribbling_angles = getattr(mod, dribbling_key)

    return BiomechanicsStandard(
        age_group=age_group,
        gender=gender,
        league=league,
        region=effective_region,
        # 보정 계수
        velocity_factor=mod.VELOCITY_FACTOR,
        gender_velocity_factor=gender_vel_factor,
        rom_expansion_factor=mod.ROM_EXPANSION_FACTOR,
        angle_tolerance=mod.ANGLE_TOLERANCE,
        # 최적 관절 각도
        shooting_angles=shooting_angles,
        defensive_angles=defensive_angles,
        dribbling_angles=dribbling_angles,
        # 가속도
        acceleration_normal=mod.ACCELERATION_NORMAL_RANGE,
        acceleration_quick=mod.ACCELERATION_QUICK_RANGE,
        acceleration_explosive=mod.ACCELERATION_EXPLOSIVE_THRESHOLD,
        deceleration_hard_stop=mod.DECELERATION_HARD_STOP_THRESHOLD,
        # 각속도
        shooting_elbow_angular_vel=mod.SHOOTING_ELBOW_ANGULAR_VELOCITY,
        shooting_wrist_angular_vel=mod.SHOOTING_WRIST_ANGULAR_VELOCITY,
        passing_arm_angular_vel=mod.PASSING_ARM_ANGULAR_VELOCITY,
        # 균형/안정성
        stability_min=mod.STABILITY_INDEX_MIN_STABLE,
        cop_sway_stable=mod.COP_SWAY_STABLE_THRESHOLD_CM,
        cop_sway_unstable=mod.COP_SWAY_UNSTABLE_THRESHOLD_CM,
        stabilization_good=mod.STABILIZATION_TIME_GOOD_S,
        stabilization_acceptable=mod.STABILIZATION_TIME_ACCEPTABLE_S,
        stabilization_poor=mod.STABILIZATION_TIME_POOR_S,
        # 동역학
        grf_walking=mod.VERTICAL_GRF_WALKING_BW,
        grf_running=mod.VERTICAL_GRF_RUNNING_BW,
        grf_jump_landing=mod.VERTICAL_GRF_JUMP_LANDING_BW,
        grf_max_safe=mod.VERTICAL_GRF_MAX_SAFE_BW,
        impact_absorption_good=mod.LANDING_IMPACT_ABSORPTION_GOOD_S,
        impact_absorption_poor=mod.LANDING_IMPACT_ABSORPTION_POOR_S,
        # 피드백 심각도
        severity_warning=mod.SEVERITY_THRESHOLDS.warning,
        severity_critical=mod.SEVERITY_THRESHOLDS.critical,
        severity_severe=mod.SEVERITY_THRESHOLDS.severe,
        # 세션 제한
        max_jumps_per_session=mod.MAX_JUMP_LANDINGS_PER_SESSION,
        max_shots_per_session=mod.MAX_SHOOTING_REPS_PER_SESSION,
        rest_between_high_impact=mod.REST_BETWEEN_HIGH_IMPACT_S,
    )


def get_standard_by_age(
    age: int,
    gender: Gender = Gender.MALE,
    league: LeagueType = LeagueType.FIBA,
    region: RegionType | None = None,
) -> BiomechanicsStandard:
    """
    나이로부터 연령대를 자동 결정하여 기준 생성.

    Args:
        age: 나이 (세)
        gender: 성별
        league: 적용 리그
        region: 지역 유형

    Returns:
        해당 나이/성별/리그의 기준 세트
    """
    age_group = AgeGroup.from_age(age)
    return get_standard(age_group, gender, league, region)


def get_velocity_threshold(
    age_group: AgeGroup,
    gender: Gender = Gender.MALE,
) -> float:
    """
    연령대/성별 조합 속도 보정 계수 반환.

    성인 남성 기준 속도에 이 값을 곱하면 해당 조건의 속도 임계치가 됩니다.

    Args:
        age_group: 연령대
        gender: 성별

    Returns:
        통합 속도 보정 계수 (0.0~1.0)
    """
    mod = _AGE_MODULE_MAP[age_group]
    age_factor = mod.VELOCITY_FACTOR

    gender_vel_map = getattr(mod, f"GENDER_VELOCITY_FACTOR_{age_group.value.upper()}", None)
    if gender_vel_map is None:
        gender_factor = 1.0 if gender == Gender.MALE else 0.90
    else:
        gender_factor = gender_vel_map[gender]

    return age_factor * gender_factor


def get_angle_tolerance(age_group: AgeGroup) -> float:
    """
    연령대별 관절 각도 허용 마진 반환 (도).

    Args:
        age_group: 연령대

    Returns:
        허용 마진 (도). 성인 = 0.0
    """
    return _AGE_MODULE_MAP[age_group].ANGLE_TOLERANCE


def get_severity_thresholds(
    age_group: AgeGroup,
) -> tuple[float, float, float]:
    """
    연령대별 피드백 심각도 임계치 반환.

    Args:
        age_group: 연령대

    Returns:
        (warning, critical, severe) 임계치 튜플
    """
    st = _AGE_MODULE_MAP[age_group].SEVERITY_THRESHOLDS
    return (st.warning, st.critical, st.severe)


# =============================================================================
# 리그별 코트 보정 유틸리티
# =============================================================================
def get_three_point_factor(league: LeagueType) -> float:
    """
    리그별 3점 거리 보정 계수 반환.

    FIBA 기준(6.75m)에 대한 비율로, 슈팅 분석 시
    발사 각도/힘 기준을 리그별로 보정합니다.

    Args:
        league: 리그 유형

    Returns:
        3점 거리 보정 계수 (FIBA = 1.0)
    """
    fiba_dist = 6.75   # FIBA 기준 3점 거리
    league_dist = league.three_point_distance_m
    return league_dist / fiba_dist


def get_court_area_factor(league: LeagueType) -> float:
    """
    리그별 코트 면적 보정 계수 반환.

    FIBA 기준(28×15 = 420m²)에 대한 비율로,
    이동 거리/속도 분석 시 코트 크기 차이를 보정합니다.

    Args:
        league: 리그 유형

    Returns:
        코트 면적 보정 계수 (FIBA = 1.0)
    """
    fiba_area = 28.0 * 15.0   # 420 m²
    league_area = league.court_length_m * league.court_width_m
    return league_area / fiba_area


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "BiomechanicsStandard",
    # 핵심 조회 함수
    "get_standard",
    "get_standard_by_age",
    # 개별 조회 함수
    "get_velocity_threshold",
    "get_angle_tolerance",
    "get_severity_thresholds",
    # 리그 보정 함수
    "get_three_point_factor",
    "get_court_area_factor",
]

__version__ = "1.0.0"
