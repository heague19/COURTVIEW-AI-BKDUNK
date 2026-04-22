# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: teen_standards.py
설명: 청소년(13-18세) 생체역학 기준값 정의
      - 사춘기 성장 급증(PHV) 반영
      - 관절 가동 범위/최적 각도 (청소년 허용 범위)
      - 이동 속도/가속도 임계치 (청소년 기준)
      - 균형/안정성/동역학 기준값

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Mirwald, R.L. et al. (2002). An assessment of maturity from
      anthropometric measurements. Medicine & Science in Sports & Exercise.
    - Lloyd, R.S. & Oliver, J.L. (2012). The Youth Physical Development Model.
    - Malina, R.M. et al. (2004). Growth, Maturation, and Physical Activity, 2nd Ed.
    - NSCA Position Statement on Long-Term Athletic Development (2016)

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender

사용처:
    - biomechanics/kinematics/: 청소년 관절 각도 평가 기준
    - biomechanics/dynamics/: 청소년 힘/에너지 평가 기준
    - motion_analysis/form_evaluation/: 청소년 폼 평가 기준
    - feedback_system/: 청소년 맞춤 피드백 참조
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender


# =============================================================================
# 연령대 메타데이터
# =============================================================================
TARGET_AGE_GROUP: Final[AgeGroup] = AgeGroup.TEEN
AGE_RANGE: Final[tuple[int, int]] = (13, 18)


# =============================================================================
# 청소년 신체 특성 기본값
# =============================================================================
@dataclass(frozen=True, slots=True)
class TeenBodyDefaults:
    """
    청소년 연령별 신체 기본값.

    사춘기 성장 급증(PHV: Peak Height Velocity)을 반영합니다.
    남: 약 13-14세, 여: 약 11-12세에 PHV 발생.
    참조: CDC 성장 곡선 50th percentile, Mirwald et al. (2002)

    Attributes:
        age: 대표 연령 (세)
        height_cm_male: 남성 평균 신장 (cm)
        height_cm_female: 여성 평균 신장 (cm)
        weight_kg_male: 남성 평균 체중 (kg)
        weight_kg_female: 여성 평균 체중 (kg)
        arm_span_ratio: 윙스팬/신장 비율
        leg_length_ratio: 다리 길이/신장 비율
    """

    age: int
    height_cm_male: float
    height_cm_female: float
    weight_kg_male: float
    weight_kg_female: float
    arm_span_ratio: float = 1.01    # 청소년: 사지 급성장으로 윙스팬 > 신장
    leg_length_ratio: float = 0.47   # 유소년 대비 다리 비율 증가


# CDC 50th percentile 기반 연령별 기본값
TEEN_BODY_DEFAULTS: Final[dict[int, TeenBodyDefaults]] = {
    13: TeenBodyDefaults(
        age=13,
        height_cm_male=156.0, height_cm_female=157.0,
        weight_kg_male=45.3, weight_kg_female=46.0,
        arm_span_ratio=1.00, leg_length_ratio=0.47,
    ),
    14: TeenBodyDefaults(
        age=14,
        height_cm_male=163.5, height_cm_female=159.5,  # 남 PHV 시기
        weight_kg_male=51.0, weight_kg_female=49.5,
        arm_span_ratio=1.01, leg_length_ratio=0.48,
    ),
    15: TeenBodyDefaults(
        age=15,
        height_cm_male=170.0, height_cm_female=161.5,
        weight_kg_male=57.0, weight_kg_female=52.5,
        arm_span_ratio=1.02, leg_length_ratio=0.48,
    ),
    16: TeenBodyDefaults(
        age=16,
        height_cm_male=174.0, height_cm_female=162.5,
        weight_kg_male=62.0, weight_kg_female=55.0,
        arm_span_ratio=1.02, leg_length_ratio=0.48,
    ),
    17: TeenBodyDefaults(
        age=17,
        height_cm_male=176.0, height_cm_female=163.0,
        weight_kg_male=66.0, weight_kg_female=56.5,
        arm_span_ratio=1.03, leg_length_ratio=0.48,
    ),
    18: TeenBodyDefaults(
        age=18,
        height_cm_male=177.5, height_cm_female=163.5,
        weight_kg_male=69.0, weight_kg_female=57.5,
        arm_span_ratio=1.03, leg_length_ratio=0.48,
    ),
}


# =============================================================================
# 청소년 관절 가동 범위 (ROM) 보정
# =============================================================================
# 청소년은 사춘기 급성장으로 일시적 유연성 감소 가능
# 그러나 전반적 ROM은 성인과 유사하거나 약간 넓음
ROM_EXPANSION_FACTOR: Final[float] = 1.05   # 성인 대비 5% 확장


# =============================================================================
# 청소년 농구 동작별 최적 관절 각도
# =============================================================================
# 성인 기준 대비 ±8° 허용 (biomechanics_constants.AGE_ANGLE_TOLERANCE)
# 유소년(±15°)보다 좁고 성인(±0°)보다 넓음
ANGLE_TOLERANCE: Final[float] = 8.0

# 청소년 슈팅 최적 각도
SHOOTING_OPTIMAL_ANGLES_TEEN: Final[dict[str, tuple[float, float]]] = {
    # 릴리즈 시점
    "release_shoulder_flexion": (77.0, 113.0),       # 성인 85-105 → ±8
    "release_elbow_angle": (142.0, 178.0),           # 성인 150-170 → ±8
    "release_wrist_flexion": (32.0, 73.0),           # 성인 40-65 → ±8
    "release_guide_hand_separation": (7.0, 53.0),    # 성인 15-45 → ±8
    # 세트 자세
    "set_knee_flexion": (92.0, 143.0),               # 성인 100-135 → ±8
    "set_hip_flexion": (147.0, 180.0),               # 성인 155-175 → ±8 (상한 cap)
    "set_elbow_angle": (62.0, 108.0),                # 성인 70-100 → ±8
    "set_shoulder_flexion": (37.0, 78.0),             # 성인 45-70 → ±8
    # 팔로스루
    "followthrough_wrist_flexion": (52.0, 93.0),     # 성인 60-85 → ±8
    "followthrough_elbow_angle": (157.0, 180.0),     # 성인 165-180 → ±8 (하한만)
}

# 청소년 수비 자세 최적 각도
DEFENSIVE_STANCE_ANGLES_TEEN: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (82.0, 143.0),                    # 성인 90-135 → ±8
    "hip_flexion": (122.0, 168.0),                    # 성인 130-160 → ±8
    "ankle_dorsiflexion": (0.0, 28.0),                # 성인 5-20 → ±8 (하한 cap)
    "trunk_forward_lean": (0.0, 28.0),                # 성인 5-20 → ±8 (하한 cap)
    "stance_width_shoulder_ratio": (1.1, 1.9),        # 성인 1.2-1.8 약간 확장
}

# 청소년 드리블 자세 최적 각도
DRIBBLING_STANCE_ANGLES_TEEN: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (92.0, 148.0),                    # 성인 100-140 → ±8
    "hip_flexion": (137.0, 178.0),                    # 성인 145-170 → ±8
    "shoulder_flexion": (7.0, 53.0),                  # 성인 15-45 → ±8
    "elbow_angle": (82.0, 148.0),                     # 성인 90-140 → ±8
    "wrist_extension": (2.0, 43.0),                   # 성인 10-35 → ±8
    "trunk_forward_lean": (0.0, 23.0),                # 성인 5-15 → ±8 (하한 cap)
}


# =============================================================================
# 청소년 이동 속도 임계치 (m/s)
# =============================================================================
# 성인 남성 기준 × 0.85 (AGE_VELOCITY_FACTOR[TEEN])
VELOCITY_FACTOR: Final[float] = 0.85

# 성별 보정 (청소년은 사춘기 후 성별 차이 뚜렷)
GENDER_VELOCITY_FACTOR_TEEN: Final[dict[Gender, float]] = {
    Gender.MALE: 1.00,
    Gender.FEMALE: 0.92,     # 성인 0.90보다 약간 높음
}


# =============================================================================
# 청소년 가속도 임계치 (m/s²)
# =============================================================================
ACCELERATION_NORMAL_RANGE: Final[tuple[float, float]] = (1.8, 4.5)       # 성인 2.0-5.0
ACCELERATION_QUICK_RANGE: Final[tuple[float, float]] = (4.5, 9.0)        # 성인 5.0-10.0
ACCELERATION_EXPLOSIVE_THRESHOLD: Final[float] = 9.0                      # 성인 10.0
DECELERATION_HARD_STOP_THRESHOLD: Final[float] = 7.0                     # 성인 8.0


# =============================================================================
# 청소년 각속도 임계치 (°/s)
# =============================================================================
SHOOTING_ELBOW_ANGULAR_VELOCITY: Final[tuple[float, float]] = (1000.0, 1650.0)  # 성인 1200-1800
SHOOTING_WRIST_ANGULAR_VELOCITY: Final[tuple[float, float]] = (350.0, 750.0)    # 성인 400-800
PASSING_ARM_ANGULAR_VELOCITY: Final[tuple[float, float]] = (430.0, 1100.0)      # 성인 500-1200


# =============================================================================
# 청소년 균형/안정성 기준
# =============================================================================
# 사춘기 급성장 시 일시적 협응력 저하 (Adolescent Awkwardness)
# 참조: Quatman-Yates et al. (2012)
STABILITY_INDEX_MIN_STABLE: Final[float] = 45.0     # 성인 50.0
COP_SWAY_STABLE_THRESHOLD_CM: Final[float] = 3.5    # 성인 3.0
COP_SWAY_UNSTABLE_THRESHOLD_CM: Final[float] = 7.0  # 성인 6.0

# 착지 안정화 시간
STABILIZATION_TIME_GOOD_S: Final[float] = 0.4       # 성인 0.3
STABILIZATION_TIME_ACCEPTABLE_S: Final[float] = 0.6  # 성인 0.5
STABILIZATION_TIME_POOR_S: Final[float] = 1.1        # 성인 1.0


# =============================================================================
# 청소년 동역학 기준
# =============================================================================
VERTICAL_GRF_WALKING_BW: Final[float] = 1.18        # 성인 1.2
VERTICAL_GRF_RUNNING_BW: Final[float] = 2.4         # 성인 2.5
VERTICAL_GRF_JUMP_LANDING_BW: Final[float] = 4.8    # 성인 5.0
VERTICAL_GRF_MAX_SAFE_BW: Final[float] = 6.5        # 성인 7.0

LANDING_IMPACT_ABSORPTION_GOOD_S: Final[float] = 0.09   # 성인 0.08
LANDING_IMPACT_ABSORPTION_POOR_S: Final[float] = 0.045  # 성인 0.04


# =============================================================================
# 청소년 에너지 소비율 (kcal/kg/min)
# =============================================================================
# 청소년은 성인 대비 약간 높은 대사율
ENERGY_RATE_STATIONARY: Final[float] = 0.019         # 성인 0.017
ENERGY_RATE_WALKING: Final[float] = 0.063            # 성인 0.057
ENERGY_RATE_JOGGING: Final[float] = 0.121            # 성인 0.110
ENERGY_RATE_RUNNING: Final[float] = 0.185            # 성인 0.168
ENERGY_RATE_SPRINTING: Final[float] = 0.270          # 성인 0.252


# =============================================================================
# 청소년 피드백 심각도 기준
# =============================================================================
@dataclass(frozen=True, slots=True)
class SeverityThreshold:
    """피드백 심각도 분류 임계치."""

    warning: float
    critical: float
    severe: float


SEVERITY_THRESHOLDS: Final[SeverityThreshold] = SeverityThreshold(
    warning=13.0,    # 성인 10.0 → 청소년 약간 완화
    critical=25.0,   # 성인 20.0
    severe=40.0,     # 성인 30.0+
)


# =============================================================================
# 청소년 특수 고려사항
# =============================================================================
# 성장판 보호 + 과사용 부상 예방
# 참조: NSCA Long-Term Athletic Development (2016)
MAX_JUMP_LANDINGS_PER_SESSION: Final[int] = 120       # 유소년 80, 성인 무제한
MAX_SHOOTING_REPS_PER_SESSION: Final[int] = 250       # 유소년 150, 성인 무제한
REST_BETWEEN_HIGH_IMPACT_S: Final[float] = 20.0       # 유소년 30.0

# 사춘기 급성장 시 ACL 부상 위험 증가 (특히 여성)
# 무릎 외반 모니터링 강화 기준
KNEE_VALGUS_WARNING_DEGREES: Final[float] = 8.0       # 유소년 10.0, 성인 10.0
KNEE_VALGUS_CRITICAL_DEGREES_FEMALE: Final[float] = 6.0  # 여성 청소년 더 엄격


# =============================================================================
# 유틸리티 함수
# =============================================================================
def get_body_defaults(age: int) -> TeenBodyDefaults:
    """
    연령별 청소년 신체 기본값 반환.

    Args:
        age: 나이 (13-18)

    Returns:
        해당 연령의 신체 기본값

    Raises:
        ValueError: 13-18세 범위 밖
    """
    clamped = max(AGE_RANGE[0], min(AGE_RANGE[1], age))
    if clamped != age:
        raise ValueError(
            f"청소년 연령 범위는 {AGE_RANGE[0]}-{AGE_RANGE[1]}세입니다. "
            f"입력값: {age}"
        )
    return TEEN_BODY_DEFAULTS[clamped]


def get_height_cm(age: int, gender: Gender) -> float:
    """연령/성별에 따른 청소년 평균 신장 반환 (cm)."""
    defaults = get_body_defaults(age)
    if gender == Gender.MALE:
        return defaults.height_cm_male
    return defaults.height_cm_female


def get_weight_kg(age: int, gender: Gender) -> float:
    """연령/성별에 따른 청소년 평균 체중 반환 (kg)."""
    defaults = get_body_defaults(age)
    if gender == Gender.MALE:
        return defaults.weight_kg_male
    return defaults.weight_kg_female


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 메타데이터
    "TARGET_AGE_GROUP",
    "AGE_RANGE",
    # 신체 기본값
    "TeenBodyDefaults",
    "TEEN_BODY_DEFAULTS",
    # ROM 보정
    "ROM_EXPANSION_FACTOR",
    # 각도 기준
    "ANGLE_TOLERANCE",
    "SHOOTING_OPTIMAL_ANGLES_TEEN",
    "DEFENSIVE_STANCE_ANGLES_TEEN",
    "DRIBBLING_STANCE_ANGLES_TEEN",
    # 속도/가속도
    "VELOCITY_FACTOR",
    "GENDER_VELOCITY_FACTOR_TEEN",
    "ACCELERATION_NORMAL_RANGE",
    "ACCELERATION_QUICK_RANGE",
    "ACCELERATION_EXPLOSIVE_THRESHOLD",
    "DECELERATION_HARD_STOP_THRESHOLD",
    # 각속도
    "SHOOTING_ELBOW_ANGULAR_VELOCITY",
    "SHOOTING_WRIST_ANGULAR_VELOCITY",
    "PASSING_ARM_ANGULAR_VELOCITY",
    # 균형/안정성
    "STABILITY_INDEX_MIN_STABLE",
    "COP_SWAY_STABLE_THRESHOLD_CM",
    "COP_SWAY_UNSTABLE_THRESHOLD_CM",
    "STABILIZATION_TIME_GOOD_S",
    "STABILIZATION_TIME_ACCEPTABLE_S",
    "STABILIZATION_TIME_POOR_S",
    # 동역학
    "VERTICAL_GRF_WALKING_BW",
    "VERTICAL_GRF_RUNNING_BW",
    "VERTICAL_GRF_JUMP_LANDING_BW",
    "VERTICAL_GRF_MAX_SAFE_BW",
    "LANDING_IMPACT_ABSORPTION_GOOD_S",
    "LANDING_IMPACT_ABSORPTION_POOR_S",
    # 에너지
    "ENERGY_RATE_STATIONARY",
    "ENERGY_RATE_WALKING",
    "ENERGY_RATE_JOGGING",
    "ENERGY_RATE_RUNNING",
    "ENERGY_RATE_SPRINTING",
    # 피드백 심각도
    "SeverityThreshold",
    "SEVERITY_THRESHOLDS",
    # 특수 고려사항
    "MAX_JUMP_LANDINGS_PER_SESSION",
    "MAX_SHOOTING_REPS_PER_SESSION",
    "REST_BETWEEN_HIGH_IMPACT_S",
    "KNEE_VALGUS_WARNING_DEGREES",
    "KNEE_VALGUS_CRITICAL_DEGREES_FEMALE",
    # 유틸리티 함수
    "get_body_defaults",
    "get_height_cm",
    "get_weight_kg",
]

__version__ = "1.0.0"
