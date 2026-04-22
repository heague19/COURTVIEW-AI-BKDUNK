# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: youth_standards.py
설명: 유소년(6-12세) 생체역학 기준값 정의
      - 관절 가동 범위 (ROM) 보정
      - 농구 동작별 최적 관절 각도 (유소년 허용 범위)
      - 이동 속도/가속도 임계치 (유소년 기준)
      - 균형/안정성 기준값
      - 동역학 힘/충격 임계치

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Quatman-Yates, C.C. et al. (2012). A systematic review of sensorimotor
      function during adolescence. Pediatric Physical Therapy.
    - Malina, R.M. et al. (2004). Growth, Maturation, and Physical Activity, 2nd Ed.
    - Lloyd, R.S. & Oliver, J.L. (2012). The Youth Physical Development Model.
    - ACSM Pediatric Exercise Guidelines

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender
    - shared/constants/biomechanics_constants.py: AGE_VELOCITY_FACTOR, AGE_ANGLE_TOLERANCE 등

사용처:
    - biomechanics/kinematics/: 유소년 관절 각도 평가 시 기준
    - biomechanics/dynamics/: 유소년 힘/에너지 평가 시 기준
    - motion_analysis/form_evaluation/: 유소년 폼 평가 시 기준
    - feedback_system/: 유소년 맞춤 피드백 참조
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender


# =============================================================================
# 연령대 메타데이터
# =============================================================================
TARGET_AGE_GROUP: Final[AgeGroup] = AgeGroup.YOUTH
AGE_RANGE: Final[tuple[int, int]] = (6, 12)


# =============================================================================
# 유소년 신체 특성 기본값
# =============================================================================
@dataclass(frozen=True, slots=True)
class YouthBodyDefaults:
    """
    유소년 연령대별 신체 기본값.

    농구 분석 시 개인 데이터가 없을 때 적용하는 기본값입니다.
    참조: Malina et al. (2004), CDC 성장 곡선 50th percentile

    Attributes:
        age: 대표 연령 (세)
        height_cm_male: 남아 평균 신장 (cm)
        height_cm_female: 여아 평균 신장 (cm)
        weight_kg_male: 남아 평균 체중 (kg)
        weight_kg_female: 여아 평균 체중 (kg)
        arm_span_ratio: 윙스팬/신장 비율
        leg_length_ratio: 다리 길이/신장 비율
    """

    age: int
    height_cm_male: float
    height_cm_female: float
    weight_kg_male: float
    weight_kg_female: float
    arm_span_ratio: float = 0.99   # 유소년은 윙스팬 ≈ 신장
    leg_length_ratio: float = 0.44  # 유소년은 상대적으로 짧은 다리


# CDC 50th percentile 기반 연령별 기본값
YOUTH_BODY_DEFAULTS: Final[dict[int, YouthBodyDefaults]] = {
    6: YouthBodyDefaults(
        age=6,
        height_cm_male=116.0, height_cm_female=115.5,
        weight_kg_male=20.7, weight_kg_female=20.2,
    ),
    7: YouthBodyDefaults(
        age=7,
        height_cm_male=122.0, height_cm_female=121.5,
        weight_kg_male=22.9, weight_kg_female=22.4,
    ),
    8: YouthBodyDefaults(
        age=8,
        height_cm_male=128.0, height_cm_female=127.5,
        weight_kg_male=25.5, weight_kg_female=25.0,
        arm_span_ratio=0.99, leg_length_ratio=0.45,
    ),
    9: YouthBodyDefaults(
        age=9,
        height_cm_male=133.5, height_cm_female=133.0,
        weight_kg_male=28.6, weight_kg_female=28.8,
        arm_span_ratio=1.00, leg_length_ratio=0.45,
    ),
    10: YouthBodyDefaults(
        age=10,
        height_cm_male=138.5, height_cm_female=138.5,
        weight_kg_male=32.0, weight_kg_female=32.5,
        arm_span_ratio=1.00, leg_length_ratio=0.46,
    ),
    11: YouthBodyDefaults(
        age=11,
        height_cm_male=143.5, height_cm_female=144.5,
        weight_kg_male=35.6, weight_kg_female=37.0,
        arm_span_ratio=1.00, leg_length_ratio=0.46,
    ),
    12: YouthBodyDefaults(
        age=12,
        height_cm_male=149.0, height_cm_female=151.0,
        weight_kg_male=39.9, weight_kg_female=41.5,
        arm_span_ratio=1.00, leg_length_ratio=0.47,
    ),
}


# =============================================================================
# 유소년 관절 가동 범위 (ROM) 보정
# =============================================================================
# 유소년은 성인 대비 유연성이 높아 ROM이 넓음
# 참조: Quatman-Yates et al. (2012)
# 값: 성인 ROM 대비 상한 확장 비율

ROM_EXPANSION_FACTOR: Final[float] = 1.10  # 성인 대비 10% 확장


# =============================================================================
# 유소년 농구 동작별 최적 관절 각도
# =============================================================================
# 성인 기준 대비 ±15° 허용 (biomechanics_constants.AGE_ANGLE_TOLERANCE)
# 유소년은 체격 미성숙으로 정확한 폼 재현이 어려우므로 넓은 허용 범위
ANGLE_TOLERANCE: Final[float] = 15.0

# 유소년 슈팅 최적 각도 (성인 기준에서 허용 범위 확대)
# 유소년은 공 크기가 작고(5호) 림 높이가 낮은 경우 있어 보정
SHOOTING_OPTIMAL_ANGLES_YOUTH: Final[dict[str, tuple[float, float]]] = {
    # 릴리즈 시점
    "release_shoulder_flexion": (70.0, 120.0),      # 성인 85-105 → ±15
    "release_elbow_angle": (135.0, 180.0),           # 성인 150-170 → ±15 (하한만)
    "release_wrist_flexion": (25.0, 80.0),           # 성인 40-65 → ±15
    "release_guide_hand_separation": (0.0, 60.0),    # 성인 15-45 → ±15
    # 세트 자세
    "set_knee_flexion": (85.0, 150.0),               # 성인 100-135 → ±15
    "set_hip_flexion": (140.0, 180.0),               # 성인 155-175 → ±15 (상한 cap)
    "set_elbow_angle": (55.0, 115.0),                # 성인 70-100 → ±15
    "set_shoulder_flexion": (30.0, 85.0),             # 성인 45-70 → ±15
    # 팔로스루
    "followthrough_wrist_flexion": (45.0, 100.0),    # 성인 60-85 → ±15
    "followthrough_elbow_angle": (150.0, 180.0),     # 성인 165-180 → ±15 (하한만)
}

# 유소년 수비 자세 최적 각도
DEFENSIVE_STANCE_ANGLES_YOUTH: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (75.0, 150.0),                    # 성인 90-135 → ±15
    "hip_flexion": (115.0, 175.0),                    # 성인 130-160 → ±15
    "ankle_dorsiflexion": (0.0, 35.0),                # 성인 5-20 → ±15
    "trunk_forward_lean": (0.0, 35.0),                # 성인 5-20 → ±15
    "stance_width_shoulder_ratio": (1.0, 2.0),        # 유소년은 넓은 스탠스 허용
}

# 유소년 드리블 자세 최적 각도
DRIBBLING_STANCE_ANGLES_YOUTH: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (85.0, 155.0),                    # 성인 100-140 → ±15
    "hip_flexion": (130.0, 180.0),                    # 성인 145-170 → ±15
    "shoulder_flexion": (0.0, 60.0),                  # 성인 15-45 → ±15
    "elbow_angle": (75.0, 155.0),                     # 성인 90-140 → ±15
    "wrist_extension": (0.0, 50.0),                   # 성인 10-35 → ±15
    "trunk_forward_lean": (0.0, 30.0),                # 성인 5-15 → ±15
}


# =============================================================================
# 유소년 이동 속도 임계치 (m/s)
# =============================================================================
# 성인 남성 기준 × 0.65 (AGE_VELOCITY_FACTOR[YOUTH])
VELOCITY_FACTOR: Final[float] = 0.65

# 성별 보정 계수 (유소년은 성별 차이가 작음)
GENDER_VELOCITY_FACTOR_YOUTH: Final[dict[Gender, float]] = {
    Gender.MALE: 1.00,
    Gender.FEMALE: 0.95,     # 성인 0.90보다 차이 작음 (사춘기 전)
}


# =============================================================================
# 유소년 가속도 임계치 (m/s²)
# =============================================================================
# 유소년은 체중이 가벼워 가속이 빠르지만 절대 속도는 낮음
ACCELERATION_NORMAL_RANGE: Final[tuple[float, float]] = (1.5, 4.0)       # 성인 2.0-5.0
ACCELERATION_QUICK_RANGE: Final[tuple[float, float]] = (4.0, 7.5)       # 성인 5.0-10.0
ACCELERATION_EXPLOSIVE_THRESHOLD: Final[float] = 7.5                     # 성인 10.0
DECELERATION_HARD_STOP_THRESHOLD: Final[float] = 6.0                    # 성인 8.0


# =============================================================================
# 유소년 각속도 임계치 (°/s)
# =============================================================================
# 유소년은 팔 길이가 짧아 각속도가 상대적으로 높을 수 있음
# 그러나 근력 부족으로 절대 속도는 낮음
SHOOTING_ELBOW_ANGULAR_VELOCITY: Final[tuple[float, float]] = (800.0, 1400.0)   # 성인 1200-1800
SHOOTING_WRIST_ANGULAR_VELOCITY: Final[tuple[float, float]] = (300.0, 650.0)    # 성인 400-800
PASSING_ARM_ANGULAR_VELOCITY: Final[tuple[float, float]] = (350.0, 900.0)       # 성인 500-1200


# =============================================================================
# 유소년 균형/안정성 기준
# =============================================================================
# 유소년은 전정계/고유감각이 미성숙하여 안정성이 낮음
# 참조: Quatman-Yates et al. (2012) 소아 감각운동 발달
STABILITY_INDEX_MIN_STABLE: Final[float] = 40.0     # 성인 50.0 (낮은 기준)
COP_SWAY_STABLE_THRESHOLD_CM: Final[float] = 4.5    # 성인 3.0 (넓은 허용)
COP_SWAY_UNSTABLE_THRESHOLD_CM: Final[float] = 8.0  # 성인 6.0

# 착지 안정화 시간 (유소년은 느린 안정화 허용)
STABILIZATION_TIME_GOOD_S: Final[float] = 0.5       # 성인 0.3
STABILIZATION_TIME_ACCEPTABLE_S: Final[float] = 0.8  # 성인 0.5
STABILIZATION_TIME_POOR_S: Final[float] = 1.3        # 성인 1.0


# =============================================================================
# 유소년 동역학 기준
# =============================================================================
# 유소년은 체중이 가벼우므로 절대 힘은 작지만, 체중 대비 비율은 유사
VERTICAL_GRF_WALKING_BW: Final[float] = 1.15        # 성인 1.2 (약간 낮음)
VERTICAL_GRF_RUNNING_BW: Final[float] = 2.3         # 성인 2.5
VERTICAL_GRF_JUMP_LANDING_BW: Final[float] = 4.5    # 성인 5.0
VERTICAL_GRF_MAX_SAFE_BW: Final[float] = 6.0        # 성인 7.0 (낮은 안전 상한)

# 착지 충격 흡수 시간 (유소년은 짧은 흡수 시간 → 부상 위험 높음)
LANDING_IMPACT_ABSORPTION_GOOD_S: Final[float] = 0.10   # 성인 0.08 (더 긴 시간 필요)
LANDING_IMPACT_ABSORPTION_POOR_S: Final[float] = 0.05   # 성인 0.04


# =============================================================================
# 유소년 에너지 소비율 (kcal/kg/min)
# =============================================================================
# 유소년은 대사 효율이 낮아 단위 체중당 에너지 소비가 높음
# 참조: Bar-Or, O. (1983) Pediatric Sports Medicine
ENERGY_RATE_STATIONARY: Final[float] = 0.020         # 성인 0.017
ENERGY_RATE_WALKING: Final[float] = 0.068            # 성인 0.057
ENERGY_RATE_JOGGING: Final[float] = 0.132            # 성인 0.110
ENERGY_RATE_RUNNING: Final[float] = 0.202            # 성인 0.168
ENERGY_RATE_SPRINTING: Final[float] = 0.290          # 성인 0.252


# =============================================================================
# 유소년 피드백 심각도 기준
# =============================================================================
@dataclass(frozen=True, slots=True)
class SeverityThreshold:
    """
    피드백 심각도 분류 임계치.

    최적 범위로부터의 편차(도)에 따라 심각도를 분류합니다.

    Attributes:
        warning: 경고 임계치 (최적 범위 이탈 각도)
        critical: 위험 임계치
        severe: 심각 임계치
    """

    warning: float
    critical: float
    severe: float


# 유소년은 넓은 경고 범위 (발달 과정에서 폼 편차가 자연스러움)
SEVERITY_THRESHOLDS: Final[SeverityThreshold] = SeverityThreshold(
    warning=20.0,    # 성인 10.0 → 유소년 2배
    critical=35.0,   # 성인 20.0
    severe=50.0,     # 성인 30.0+
)


# =============================================================================
# 유소년 특수 고려사항
# =============================================================================
# 성장판 보호를 위한 반복 동작 제한 기준
# 참조: NSCA Position Statement on Youth Resistance Training (2009)
MAX_JUMP_LANDINGS_PER_SESSION: Final[int] = 80       # 세션당 최대 점프-착지 횟수
MAX_SHOOTING_REPS_PER_SESSION: Final[int] = 150      # 세션당 최대 슛 시도
REST_BETWEEN_HIGH_IMPACT_S: Final[float] = 30.0      # 고강도 동작 간 최소 휴식 (초)


# =============================================================================
# 유틸리티 함수
# =============================================================================
def get_body_defaults(age: int) -> YouthBodyDefaults:
    """
    연령별 유소년 신체 기본값 반환.

    Args:
        age: 나이 (6-12)

    Returns:
        해당 연령의 신체 기본값

    Raises:
        ValueError: 6-12세 범위 밖
    """
    clamped = max(AGE_RANGE[0], min(AGE_RANGE[1], age))
    if clamped != age:
        raise ValueError(
            f"유소년 연령 범위는 {AGE_RANGE[0]}-{AGE_RANGE[1]}세입니다. "
            f"입력값: {age}"
        )
    return YOUTH_BODY_DEFAULTS[clamped]


def get_height_cm(age: int, gender: Gender) -> float:
    """
    연령/성별에 따른 유소년 평균 신장 반환 (cm).

    Args:
        age: 나이 (6-12)
        gender: 성별

    Returns:
        평균 신장 (cm)
    """
    defaults = get_body_defaults(age)
    if gender == Gender.MALE:
        return defaults.height_cm_male
    return defaults.height_cm_female


def get_weight_kg(age: int, gender: Gender) -> float:
    """
    연령/성별에 따른 유소년 평균 체중 반환 (kg).

    Args:
        age: 나이 (6-12)
        gender: 성별

    Returns:
        평균 체중 (kg)
    """
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
    "YouthBodyDefaults",
    "YOUTH_BODY_DEFAULTS",
    # ROM 보정
    "ROM_EXPANSION_FACTOR",
    # 각도 기준
    "ANGLE_TOLERANCE",
    "SHOOTING_OPTIMAL_ANGLES_YOUTH",
    "DEFENSIVE_STANCE_ANGLES_YOUTH",
    "DRIBBLING_STANCE_ANGLES_YOUTH",
    # 속도/가속도
    "VELOCITY_FACTOR",
    "GENDER_VELOCITY_FACTOR_YOUTH",
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
    # 유틸리티 함수
    "get_body_defaults",
    "get_height_cm",
    "get_weight_kg",
]

__version__ = "1.0.0"
