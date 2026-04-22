# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: senior_standards.py
설명: 시니어(50세 이상) 생체역학 기준값 정의
      - 노화에 따른 근감소(Sarcopenia) 반영
      - 관절 가동 범위 감소 보정
      - 이동 속도/가속도 하향 조정
      - 균형/안정성 기준 완화
      - 부상 예방 중심 동역학 기준

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Cruz-Jentoft, A.J. et al. (2019). Sarcopenia: revised European consensus.
      Age and Ageing, 48(1), 16-31.
    - Shumway-Cook, A. & Woollacott, M. (2017). Motor Control: Translating
      Research into Clinical Practice, 5th Ed.
    - ACSM Guidelines for Exercise Testing (Older Adults Chapter)
    - Granacher, U. et al. (2013). Balance training in older adults.

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender

사용처:
    - biomechanics/kinematics/: 시니어 관절 각도 평가 기준
    - biomechanics/dynamics/: 시니어 힘/에너지 평가 기준
    - motion_analysis/form_evaluation/: 시니어 폼 평가 기준
    - feedback_system/: 시니어 안전 중심 피드백
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender


# =============================================================================
# 연령대 메타데이터
# =============================================================================
TARGET_AGE_GROUP: Final[AgeGroup] = AgeGroup.SENIOR
AGE_RANGE: Final[tuple[int, int]] = (50, 99)


# =============================================================================
# 시니어 신체 특성 기본값
# =============================================================================
@dataclass(frozen=True, slots=True)
class SeniorBodyDefaults:
    """
    시니어 연령 구간별 신체 기본값.

    노화에 따른 신장 감소(척추 압축), 체중 변화, 근감소를 반영합니다.
    참조: NHANES III Anthropometric Reference Data (1994), Cruz-Jentoft (2019)

    Attributes:
        age_range: 대표 연령 구간
        height_cm_male: 남성 평균 신장 (cm)
        height_cm_female: 여성 평균 신장 (cm)
        weight_kg_male: 남성 평균 체중 (kg)
        weight_kg_female: 여성 평균 체중 (kg)
        muscle_mass_ratio: 성인 대비 근육량 비율 (1.0 = 성인)
        arm_span_ratio: 윙스팬/신장 비율
        leg_length_ratio: 다리 길이/신장 비율
    """

    age_range: tuple[int, int]
    height_cm_male: float
    height_cm_female: float
    weight_kg_male: float
    weight_kg_female: float
    muscle_mass_ratio: float        # 성인 대비 근육량 비율
    arm_span_ratio: float = 1.04    # 시니어: 윙스팬 > 신장 (척추 단축)
    leg_length_ratio: float = 0.47


SENIOR_BODY_DEFAULTS: Final[dict[str, SeniorBodyDefaults]] = {
    "50s": SeniorBodyDefaults(
        age_range=(50, 59),
        height_cm_male=173.0, height_cm_female=160.0,
        weight_kg_male=76.0, weight_kg_female=65.0,
        muscle_mass_ratio=0.92,     # 8% 근감소
    ),
    "60s": SeniorBodyDefaults(
        age_range=(60, 69),
        height_cm_male=171.0, height_cm_female=158.0,
        weight_kg_male=74.0, weight_kg_female=64.0,
        muscle_mass_ratio=0.82,     # 18% 근감소
        leg_length_ratio=0.46,
    ),
    "70s": SeniorBodyDefaults(
        age_range=(70, 79),
        height_cm_male=168.5, height_cm_female=155.5,
        weight_kg_male=71.0, weight_kg_female=62.0,
        muscle_mass_ratio=0.72,     # 28% 근감소
        leg_length_ratio=0.46,
    ),
    "80+": SeniorBodyDefaults(
        age_range=(80, 99),
        height_cm_male=165.5, height_cm_female=153.0,
        weight_kg_male=67.0, weight_kg_female=58.0,
        muscle_mass_ratio=0.60,     # 40% 근감소
        leg_length_ratio=0.45,
    ),
}


# =============================================================================
# 시니어 관절 가동 범위 (ROM) 보정
# =============================================================================
# 시니어는 관절 유연성 감소로 ROM이 좁아짐
# 참조: ACSM, Shumway-Cook & Woollacott (2017)
ROM_EXPANSION_FACTOR: Final[float] = 0.90   # 성인 대비 10% 축소


# =============================================================================
# 시니어 농구 동작별 최적 관절 각도
# =============================================================================
# 성인 기준 대비 ±10° 허용 (biomechanics_constants.AGE_ANGLE_TOLERANCE)
# 시니어는 관절 경직도 증가로 허용 범위 확대
ANGLE_TOLERANCE: Final[float] = 10.0

# 시니어 슈팅 최적 각도
SHOOTING_OPTIMAL_ANGLES_SENIOR: Final[dict[str, tuple[float, float]]] = {
    # 릴리즈 시점
    "release_shoulder_flexion": (75.0, 115.0),       # 성인 85-105 → ±10
    "release_elbow_angle": (140.0, 180.0),           # 성인 150-170 → ±10
    "release_wrist_flexion": (30.0, 75.0),           # 성인 40-65 → ±10
    "release_guide_hand_separation": (5.0, 55.0),    # 성인 15-45 → ±10
    # 세트 자세
    "set_knee_flexion": (90.0, 145.0),               # 성인 100-135 → ±10
    "set_hip_flexion": (145.0, 180.0),               # 성인 155-175 → ±10 (상한 cap)
    "set_elbow_angle": (60.0, 110.0),                # 성인 70-100 → ±10
    "set_shoulder_flexion": (35.0, 80.0),             # 성인 45-70 → ±10
    # 팔로스루
    "followthrough_wrist_flexion": (50.0, 95.0),     # 성인 60-85 → ±10
    "followthrough_elbow_angle": (155.0, 180.0),     # 성인 165-180 → ±10 (하한만)
}

# 시니어 수비 자세 최적 각도
DEFENSIVE_STANCE_ANGLES_SENIOR: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (80.0, 145.0),                    # 성인 90-135 → ±10
    "hip_flexion": (120.0, 170.0),                    # 성인 130-160 → ±10
    "ankle_dorsiflexion": (0.0, 30.0),                # 성인 5-20 → ±10
    "trunk_forward_lean": (0.0, 30.0),                # 성인 5-20 → ±10
    "stance_width_shoulder_ratio": (1.0, 2.0),        # 넓은 스탠스 허용 (균형 보정)
}

# 시니어 드리블 자세 최적 각도
DRIBBLING_STANCE_ANGLES_SENIOR: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (90.0, 150.0),                    # 성인 100-140 → ±10
    "hip_flexion": (135.0, 180.0),                    # 성인 145-170 → ±10
    "shoulder_flexion": (5.0, 55.0),                  # 성인 15-45 → ±10
    "elbow_angle": (80.0, 150.0),                     # 성인 90-140 → ±10
    "wrist_extension": (0.0, 45.0),                   # 성인 10-35 → ±10
    "trunk_forward_lean": (0.0, 25.0),                # 성인 5-15 → ±10
}


# =============================================================================
# 시니어 이동 속도 임계치 (m/s)
# =============================================================================
# 성인 남성 기준 × 0.78 (AGE_VELOCITY_FACTOR[SENIOR])
VELOCITY_FACTOR: Final[float] = 0.78

GENDER_VELOCITY_FACTOR_SENIOR: Final[dict[Gender, float]] = {
    Gender.MALE: 1.00,
    Gender.FEMALE: 0.88,     # 성인 0.90보다 약간 낮음
}


# =============================================================================
# 시니어 가속도 임계치 (m/s²)
# =============================================================================
# 근감소로 가속/감속 능력 저하
ACCELERATION_NORMAL_RANGE: Final[tuple[float, float]] = (1.5, 3.8)       # 성인 2.0-5.0
ACCELERATION_QUICK_RANGE: Final[tuple[float, float]] = (3.8, 7.5)       # 성인 5.0-10.0
ACCELERATION_EXPLOSIVE_THRESHOLD: Final[float] = 7.5                     # 성인 10.0
DECELERATION_HARD_STOP_THRESHOLD: Final[float] = 6.0                    # 성인 8.0


# =============================================================================
# 시니어 각속도 임계치 (°/s)
# =============================================================================
SHOOTING_ELBOW_ANGULAR_VELOCITY: Final[tuple[float, float]] = (900.0, 1500.0)   # 성인 1200-1800
SHOOTING_WRIST_ANGULAR_VELOCITY: Final[tuple[float, float]] = (300.0, 650.0)    # 성인 400-800
PASSING_ARM_ANGULAR_VELOCITY: Final[tuple[float, float]] = (380.0, 950.0)       # 성인 500-1200


# =============================================================================
# 시니어 균형/안정성 기준
# =============================================================================
# 시니어는 전정 기능/고유감각 저하로 균형 능력 감소
# 참조: Granacher et al. (2013), Shumway-Cook & Woollacott (2017)
STABILITY_INDEX_MIN_STABLE: Final[float] = 38.0     # 성인 50.0 (크게 완화)
COP_SWAY_STABLE_THRESHOLD_CM: Final[float] = 5.0    # 성인 3.0
COP_SWAY_UNSTABLE_THRESHOLD_CM: Final[float] = 9.0  # 성인 6.0

# 착지 안정화 시간 (시니어는 느린 안정화)
STABILIZATION_TIME_GOOD_S: Final[float] = 0.6        # 성인 0.3
STABILIZATION_TIME_ACCEPTABLE_S: Final[float] = 1.0  # 성인 0.5
STABILIZATION_TIME_POOR_S: Final[float] = 1.5        # 성인 1.0


# =============================================================================
# 시니어 동역학 기준
# =============================================================================
# 부상 예방 중심: 낮은 안전 상한
VERTICAL_GRF_WALKING_BW: Final[float] = 1.1         # 성인 1.2
VERTICAL_GRF_RUNNING_BW: Final[float] = 2.0         # 성인 2.5
VERTICAL_GRF_JUMP_LANDING_BW: Final[float] = 3.5    # 성인 5.0 (크게 하향)
VERTICAL_GRF_MAX_SAFE_BW: Final[float] = 5.0        # 성인 7.0 (엄격한 상한)

LANDING_IMPACT_ABSORPTION_GOOD_S: Final[float] = 0.12   # 성인 0.08 (느린 흡수 허용)
LANDING_IMPACT_ABSORPTION_POOR_S: Final[float] = 0.06   # 성인 0.04


# =============================================================================
# 시니어 에너지 소비율 (kcal/kg/min)
# =============================================================================
# 기초대사율 감소, 운동 효율 저하
# 참조: ACSM Older Adults Guidelines
ENERGY_RATE_STATIONARY: Final[float] = 0.015         # 성인 0.017
ENERGY_RATE_WALKING: Final[float] = 0.052            # 성인 0.057
ENERGY_RATE_JOGGING: Final[float] = 0.100            # 성인 0.110
ENERGY_RATE_RUNNING: Final[float] = 0.148            # 성인 0.168
ENERGY_RATE_SPRINTING: Final[float] = 0.215          # 성인 0.252


# =============================================================================
# 시니어 피드백 심각도 기준
# =============================================================================
@dataclass(frozen=True, slots=True)
class SeverityThreshold:
    """피드백 심각도 분류 임계치."""

    warning: float
    critical: float
    severe: float


# 시니어는 유소년과 유사하게 넓은 허용 범위
SEVERITY_THRESHOLDS: Final[SeverityThreshold] = SeverityThreshold(
    warning=18.0,    # 성인 10.0
    critical=30.0,   # 성인 20.0
    severe=45.0,     # 성인 30.0
)


# =============================================================================
# 시니어 특수 고려사항 — 부상 예방
# =============================================================================
# 시니어는 낙상/골절 위험이 높으므로 고강도 동작 제한
# 참조: ACSM Position Stand on Exercise for Older Adults
MAX_JUMP_LANDINGS_PER_SESSION: Final[int] = 40        # 유소년 80, 성인 300
MAX_SHOOTING_REPS_PER_SESSION: Final[int] = 100       # 유소년 150, 성인 500
REST_BETWEEN_HIGH_IMPACT_S: Final[float] = 45.0       # 유소년 30.0, 성인 10.0

# 무릎 외반 경고 기준 (관절염 위험)
KNEE_VALGUS_WARNING_DEGREES: Final[float] = 8.0

# 고강도 동작 경고 임계치 (체중의 N배 이상 → 경고)
HIGH_IMPACT_WARNING_GRF_BW: Final[float] = 3.0       # 성인에게는 적용 안 함

# 심박수 안전 상한 (220 - 나이 기준 85%)
# 시니어 분석 시 고강도 동작이 지속되면 경고
MAX_EXERCISE_HR_PERCENT: Final[float] = 0.85


# =============================================================================
# 유틸리티 함수
# =============================================================================
def _age_to_decade_key(age: int) -> str:
    """나이를 연대 키로 변환."""
    if age < 60:
        return "50s"
    if age < 70:
        return "60s"
    if age < 80:
        return "70s"
    return "80+"


def get_body_defaults(age: int) -> SeniorBodyDefaults:
    """
    연령별 시니어 신체 기본값 반환.

    Args:
        age: 나이 (50 이상)

    Returns:
        해당 연령대의 신체 기본값

    Raises:
        ValueError: 50세 미만
    """
    if age < AGE_RANGE[0]:
        raise ValueError(
            f"시니어 연령 범위는 {AGE_RANGE[0]}세 이상입니다. 입력값: {age}"
        )
    key = _age_to_decade_key(age)
    return SENIOR_BODY_DEFAULTS[key]


def get_height_cm(age: int, gender: Gender) -> float:
    """연령/성별에 따른 시니어 평균 신장 반환 (cm)."""
    defaults = get_body_defaults(age)
    if gender == Gender.MALE:
        return defaults.height_cm_male
    return defaults.height_cm_female


def get_weight_kg(age: int, gender: Gender) -> float:
    """연령/성별에 따른 시니어 평균 체중 반환 (kg)."""
    defaults = get_body_defaults(age)
    if gender == Gender.MALE:
        return defaults.weight_kg_male
    return defaults.weight_kg_female


def get_muscle_mass_ratio(age: int) -> float:
    """연령에 따른 근육량 비율 반환 (성인 대비)."""
    return get_body_defaults(age).muscle_mass_ratio


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 메타데이터
    "TARGET_AGE_GROUP",
    "AGE_RANGE",
    # 신체 기본값
    "SeniorBodyDefaults",
    "SENIOR_BODY_DEFAULTS",
    # ROM 보정
    "ROM_EXPANSION_FACTOR",
    # 각도 기준
    "ANGLE_TOLERANCE",
    "SHOOTING_OPTIMAL_ANGLES_SENIOR",
    "DEFENSIVE_STANCE_ANGLES_SENIOR",
    "DRIBBLING_STANCE_ANGLES_SENIOR",
    # 속도/가속도
    "VELOCITY_FACTOR",
    "GENDER_VELOCITY_FACTOR_SENIOR",
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
    "HIGH_IMPACT_WARNING_GRF_BW",
    "MAX_EXERCISE_HR_PERCENT",
    # 유틸리티 함수
    "get_body_defaults",
    "get_height_cm",
    "get_weight_kg",
    "get_muscle_mass_ratio",
]

__version__ = "1.0.0"
