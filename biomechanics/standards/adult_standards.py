# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/standards
파일: adult_standards.py
설명: 성인(19-49세) 생체역학 기준값 정의
      - 모든 보정 계수의 기준 (1.0)
      - shared/constants/biomechanics_constants.py 값을 직접 재정의
      - 관절 가동 범위/최적 각도 (표준 범위)
      - 이동 속도/가속도/각속도/균형/동역학 기준값

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.
    - Okazaki, V.H.A. & Rodacki, A.L.F. (2012). Basketball jump shot kinematics.
    - Knudson, D. (2007). Fundamentals of Biomechanics, 2nd Ed.
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement.

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender

사용처:
    - biomechanics/kinematics/: 성인 관절 각도 평가 기준 (기본값)
    - biomechanics/dynamics/: 성인 힘/에너지 평가 기준
    - motion_analysis/form_evaluation/: 성인 폼 평가 기준
    - feedback_system/: 성인 맞춤 피드백 참조
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared.constants.player_constants import AgeGroup, Gender


# =============================================================================
# 연령대 메타데이터
# =============================================================================
TARGET_AGE_GROUP: Final[AgeGroup] = AgeGroup.ADULT
AGE_RANGE: Final[tuple[int, int]] = (19, 49)


# =============================================================================
# 성인 신체 특성 기본값
# =============================================================================
@dataclass(frozen=True, slots=True)
class AdultBodyDefaults:
    """
    성인 신체 기본값.

    성인은 연령 세분화 없이 성별로만 구분합니다.
    참조: NCD-RisC (2016), WHO Global Database

    Attributes:
        height_cm: 평균 신장 (cm)
        weight_kg: 평균 체중 (kg)
        arm_span_ratio: 윙스팬/신장 비율
        leg_length_ratio: 다리 길이/신장 비율
    """

    height_cm: float
    weight_kg: float
    arm_span_ratio: float = 1.03     # 성인 남성 평균
    leg_length_ratio: float = 0.48


ADULT_BODY_DEFAULTS: Final[dict[Gender, AdultBodyDefaults]] = {
    Gender.MALE: AdultBodyDefaults(
        height_cm=175.0,
        weight_kg=75.0,
        arm_span_ratio=1.03,
        leg_length_ratio=0.48,
    ),
    Gender.FEMALE: AdultBodyDefaults(
        height_cm=162.0,
        weight_kg=62.0,
        arm_span_ratio=1.01,
        leg_length_ratio=0.47,
    ),
}


# =============================================================================
# 성인 관절 가동 범위 (ROM) 보정
# =============================================================================
# 성인은 기준값이므로 보정 없음
ROM_EXPANSION_FACTOR: Final[float] = 1.00


# =============================================================================
# 성인 농구 동작별 최적 관절 각도
# =============================================================================
# 성인이 기준 (ANGLE_TOLERANCE = 0, biomechanics_constants 값과 동일)
ANGLE_TOLERANCE: Final[float] = 0.0

# 성인 슈팅 최적 각도 (= biomechanics_constants.SHOOTING_OPTIMAL_ANGLES)
SHOOTING_OPTIMAL_ANGLES_ADULT: Final[dict[str, tuple[float, float]]] = {
    # 릴리즈 시점 (Execution 페이즈)
    "release_shoulder_flexion": (85.0, 105.0),
    "release_elbow_angle": (150.0, 170.0),
    "release_wrist_flexion": (40.0, 65.0),
    "release_guide_hand_separation": (15.0, 45.0),
    # 세트 자세 (Preparation 페이즈)
    "set_knee_flexion": (100.0, 135.0),
    "set_hip_flexion": (155.0, 175.0),
    "set_elbow_angle": (70.0, 100.0),
    "set_shoulder_flexion": (45.0, 70.0),
    # 팔로스루 (Follow-through 페이즈)
    "followthrough_wrist_flexion": (60.0, 85.0),
    "followthrough_elbow_angle": (165.0, 180.0),
}

# 성인 수비 자세 최적 각도 (= biomechanics_constants.DEFENSIVE_STANCE_ANGLES)
DEFENSIVE_STANCE_ANGLES_ADULT: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (90.0, 135.0),
    "hip_flexion": (130.0, 160.0),
    "ankle_dorsiflexion": (5.0, 20.0),
    "trunk_forward_lean": (5.0, 20.0),
    "stance_width_shoulder_ratio": (1.2, 1.8),
}

# 성인 드리블 자세 최적 각도 (= biomechanics_constants.DRIBBLING_STANCE_ANGLES)
DRIBBLING_STANCE_ANGLES_ADULT: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (100.0, 140.0),
    "hip_flexion": (145.0, 170.0),
    "shoulder_flexion": (15.0, 45.0),
    "elbow_angle": (90.0, 140.0),
    "wrist_extension": (10.0, 35.0),
    "trunk_forward_lean": (5.0, 15.0),
}


# =============================================================================
# 성인 이동 속도 임계치 (m/s)
# =============================================================================
# 성인이 기준 (factor = 1.0)
VELOCITY_FACTOR: Final[float] = 1.00

GENDER_VELOCITY_FACTOR_ADULT: Final[dict[Gender, float]] = {
    Gender.MALE: 1.00,
    Gender.FEMALE: 0.90,
}


# =============================================================================
# 성인 가속도 임계치 (m/s²)
# =============================================================================
ACCELERATION_NORMAL_RANGE: Final[tuple[float, float]] = (2.0, 5.0)
ACCELERATION_QUICK_RANGE: Final[tuple[float, float]] = (5.0, 10.0)
ACCELERATION_EXPLOSIVE_THRESHOLD: Final[float] = 10.0
DECELERATION_HARD_STOP_THRESHOLD: Final[float] = 8.0


# =============================================================================
# 성인 각속도 임계치 (°/s)
# =============================================================================
SHOOTING_ELBOW_ANGULAR_VELOCITY: Final[tuple[float, float]] = (1200.0, 1800.0)
SHOOTING_WRIST_ANGULAR_VELOCITY: Final[tuple[float, float]] = (400.0, 800.0)
PASSING_ARM_ANGULAR_VELOCITY: Final[tuple[float, float]] = (500.0, 1200.0)


# =============================================================================
# 성인 균형/안정성 기준
# =============================================================================
STABILITY_INDEX_MIN_STABLE: Final[float] = 50.0
COP_SWAY_STABLE_THRESHOLD_CM: Final[float] = 3.0
COP_SWAY_UNSTABLE_THRESHOLD_CM: Final[float] = 6.0

STABILIZATION_TIME_GOOD_S: Final[float] = 0.3
STABILIZATION_TIME_ACCEPTABLE_S: Final[float] = 0.5
STABILIZATION_TIME_POOR_S: Final[float] = 1.0


# =============================================================================
# 성인 동역학 기준
# =============================================================================
VERTICAL_GRF_WALKING_BW: Final[float] = 1.2
VERTICAL_GRF_RUNNING_BW: Final[float] = 2.5
VERTICAL_GRF_JUMP_LANDING_BW: Final[float] = 5.0
VERTICAL_GRF_MAX_SAFE_BW: Final[float] = 7.0

LANDING_IMPACT_ABSORPTION_GOOD_S: Final[float] = 0.08
LANDING_IMPACT_ABSORPTION_POOR_S: Final[float] = 0.04


# =============================================================================
# 성인 에너지 소비율 (kcal/kg/min)
# =============================================================================
ENERGY_RATE_STATIONARY: Final[float] = 0.017
ENERGY_RATE_WALKING: Final[float] = 0.057
ENERGY_RATE_JOGGING: Final[float] = 0.110
ENERGY_RATE_RUNNING: Final[float] = 0.168
ENERGY_RATE_SPRINTING: Final[float] = 0.252


# =============================================================================
# 성인 피드백 심각도 기준
# =============================================================================
@dataclass(frozen=True, slots=True)
class SeverityThreshold:
    """피드백 심각도 분류 임계치."""

    warning: float
    critical: float
    severe: float


SEVERITY_THRESHOLDS: Final[SeverityThreshold] = SeverityThreshold(
    warning=10.0,
    critical=20.0,
    severe=30.0,
)


# =============================================================================
# 성인 특수 고려사항
# =============================================================================
# 성인은 성장판 이슈 없음 → 반복 동작 제한 없음 (과사용 부상은 별도)
MAX_JUMP_LANDINGS_PER_SESSION: Final[int] = 300       # 사실상 무제한에 가까운 상한
MAX_SHOOTING_REPS_PER_SESSION: Final[int] = 500
REST_BETWEEN_HIGH_IMPACT_S: Final[float] = 10.0

# 무릎 외반 경고 기준
KNEE_VALGUS_WARNING_DEGREES: Final[float] = 10.0


# =============================================================================
# 유틸리티 함수
# =============================================================================
def get_body_defaults(gender: Gender) -> AdultBodyDefaults:
    """
    성별에 따른 성인 신체 기본값 반환.

    Args:
        gender: 성별

    Returns:
        해당 성별의 신체 기본값
    """
    return ADULT_BODY_DEFAULTS[gender]


def get_height_cm(gender: Gender) -> float:
    """성별에 따른 성인 평균 신장 반환 (cm)."""
    return ADULT_BODY_DEFAULTS[gender].height_cm


def get_weight_kg(gender: Gender) -> float:
    """성별에 따른 성인 평균 체중 반환 (kg)."""
    return ADULT_BODY_DEFAULTS[gender].weight_kg


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 메타데이터
    "TARGET_AGE_GROUP",
    "AGE_RANGE",
    # 신체 기본값
    "AdultBodyDefaults",
    "ADULT_BODY_DEFAULTS",
    # ROM 보정
    "ROM_EXPANSION_FACTOR",
    # 각도 기준
    "ANGLE_TOLERANCE",
    "SHOOTING_OPTIMAL_ANGLES_ADULT",
    "DEFENSIVE_STANCE_ANGLES_ADULT",
    "DRIBBLING_STANCE_ANGLES_ADULT",
    # 속도/가속도
    "VELOCITY_FACTOR",
    "GENDER_VELOCITY_FACTOR_ADULT",
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
    # 유틸리티 함수
    "get_body_defaults",
    "get_height_cm",
    "get_weight_kg",
]

__version__ = "1.0.0"
