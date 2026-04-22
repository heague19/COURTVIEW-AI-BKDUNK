# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/anthropometry
파일: personal_adapter.py
설명: 개인 신체 측정 기반 파라미터 적응 모듈 (DESK 버전)
      - 영상 분석으로 추정한 신체 비율을 반영
      - 연령/성별 기본값 대비 개인 편차 계산
      - 신체 비율 기반 분석 기준 개인화
      - 다중 프레임 측정값 안정화 (이동 평균)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Pheasant, S. & Haslegrave, C. (2018). Bodyspace: Anthropometry,
      Ergonomics and the Design of Work.
    - Norton, K. & Olds, T. (1996). Anthropometrica.
    - de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
      inertia parameters. Journal of Biomechanics, 29(9), 1223-1230.

의존성:
    - shared/constants/player_constants.py: AgeGroup, Gender
    - biomechanics/anthropometry/proportion_calculator.py: BodyProportions, SegmentLengths
    - biomechanics/anthropometry/body_segment.py: BodyModel, create_body_model
    - biomechanics/anthropometry/age_gender_adapter.py: AgeGenderProfile, get_default_body_params

사용처:
    - biomechanics/kinematics/: 개인 세그먼트 길이 기반 관절 속도 계산
    - biomechanics/dynamics/: 개인 질량 분포 기반 힘/토크 계산
    - motion_analysis/form_evaluation/: 개인 체형 대비 폼 평가
    - feedback_system/: 체형 특성 반영 개인화 피드백

비고:
    DESK 버전은 앱에서 전송하는 UserProfile DTO가 아니라,
    영상 기반 포즈 추정에서 추출한 BodyProportions를 사용합니다.
    앱 서버 연동 시에는 UserProfile → PersonalProfile 변환이 별도 필요합니다.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.player_constants import AgeGroup, Gender

from biomechanics.anthropometry.proportion_calculator import (
    BodyProportions,
    SegmentLengths,
)
from biomechanics.anthropometry.body_segment import (
    BodyModel,
    create_body_model,
    estimate_body_mass_from_height,
)
from biomechanics.anthropometry.age_gender_adapter import (
    AgeGenderProfile,
    get_default_body_params,
)


# =============================================================================
# 상수
# =============================================================================
# 측정값 안정화 윈도우 크기
STABILIZATION_WINDOW: Final[int] = 30    # 최근 30프레임 이동 평균
MIN_SAMPLES_FOR_STABLE: Final[int] = 5   # 최소 5개 샘플이어야 안정

# 신체 비율 유효 범위 (물리적으로 가능한 범위)
MIN_HEIGHT_M: Final[float] = 0.90        # 최소 신장 (m, 유소년 하한)
MAX_HEIGHT_M: Final[float] = 2.40        # 최대 신장 (m)
MIN_WINGSPAN_RATIO: Final[float] = 0.85  # 최소 윙스팬/신장 비율
MAX_WINGSPAN_RATIO: Final[float] = 1.20  # 최대 윙스팬/신장 비율
MIN_UPPER_LOWER_RATIO: Final[float] = 0.60  # 최소 상하체 비율
MAX_UPPER_LOWER_RATIO: Final[float] = 1.50  # 최대 상하체 비율

# 편차 유의 수준 (이 이상이면 개인화 적용)
SIGNIFICANT_DEVIATION_THRESHOLD: Final[float] = 0.05  # 5%


# =============================================================================
# 개인 신체 편차 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class ProportionDeviation:
    """
    기본값 대비 개인 신체 비율 편차.

    양수 = 기본값보다 큼, 음수 = 기본값보다 작음.
    각 필드는 비율 편차 (예: 0.05 = 5% 큼).

    Attributes:
        height_deviation: 신장 편차 비율
        wingspan_ratio_deviation: 윙스팬/신장 비율 편차
        upper_lower_ratio_deviation: 상/하체 비율 편차
        shoulder_hip_ratio_deviation: 어깨/골반 비율 편차
        arm_length_deviation: 팔 길이 편차 비율
        leg_length_deviation: 다리 길이 편차 비율
        arm_asymmetry: 팔 좌우 비대칭도 (0-1)
        leg_asymmetry: 다리 좌우 비대칭도 (0-1)
    """

    height_deviation: float
    wingspan_ratio_deviation: float
    upper_lower_ratio_deviation: float
    shoulder_hip_ratio_deviation: float
    arm_length_deviation: float
    leg_length_deviation: float
    arm_asymmetry: float
    leg_asymmetry: float


# =============================================================================
# 개인 프로파일 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class PersonalProfile:
    """
    개인 신체 측정 기반 적응 프로파일.

    영상 기반 추정 신체 비율을 바탕으로 생성됩니다.
    개인 측정값 + 기본값 대비 편차 + 적응된 body model을 포함합니다.

    Attributes:
        age: 나이 (세)
        age_group: 연령대
        gender: 성별
        height_m: 추정 신장 (m)
        weight_kg: 추정 체중 (kg)
        proportions: 측정된 신체 비율
        deviation: 기본값 대비 편차
        body_model: 개인화된 BodyModel
        is_stable: 측정값이 안정화되었는지 여부
        sample_count: 누적 샘플 수
    """

    age: int
    age_group: AgeGroup
    gender: Gender
    height_m: float
    weight_kg: float
    proportions: BodyProportions
    deviation: ProportionDeviation
    body_model: BodyModel
    is_stable: bool
    sample_count: int


# =============================================================================
# 편차 계산
# =============================================================================
def _safe_deviation(measured: float, default: float) -> float:
    """기본값 대비 편차 비율 계산 (0 방지)."""
    if abs(default) < 1e-9:
        return 0.0
    return (measured - default) / default


def calculate_proportion_deviation(
    proportions: BodyProportions,
    age: int,
    gender: Gender,
) -> ProportionDeviation:
    """
    기본값 대비 개인 신체 비율 편차 계산.

    Args:
        proportions: 측정된 신체 비율
        age: 나이 (세)
        gender: 성별

    Returns:
        ProportionDeviation 객체
    """
    height_cm_default, weight_kg_default, arm_span_ratio_default, leg_ratio_default = (
        get_default_body_params(age, gender)
    )
    height_m_default = height_cm_default / 100.0

    # 기본 상/하체 비율 추정: 상체 ≈ (1 - leg_ratio) × height, 하체 ≈ leg_ratio × height
    default_upper_lower = (1.0 - leg_ratio_default) / leg_ratio_default if leg_ratio_default > 0 else 1.0

    # 기본 어깨/골반 비율 (인체측정 평균치)
    # 참조: Norton & Olds (1996), 남성 1.7, 여성 1.4
    default_shoulder_hip = 1.70 if gender == Gender.MALE else 1.40

    # 기본 팔 길이: arm_span × 0.5 (한쪽 팔 ≈ 윙스팬/2)
    default_arm_m = height_m_default * arm_span_ratio_default * 0.5

    # 기본 다리 길이: height × leg_ratio
    default_leg_m = height_m_default * leg_ratio_default

    # 측정값 평균 (좌/우 평균)
    measured_arm = (proportions.right_arm_m + proportions.left_arm_m) / 2.0
    measured_leg = (proportions.right_leg_m + proportions.left_leg_m) / 2.0

    return ProportionDeviation(
        height_deviation=_safe_deviation(proportions.estimated_height_m, height_m_default),
        wingspan_ratio_deviation=_safe_deviation(
            proportions.wingspan_height_ratio, arm_span_ratio_default,
        ),
        upper_lower_ratio_deviation=_safe_deviation(
            proportions.upper_lower_ratio, default_upper_lower,
        ),
        shoulder_hip_ratio_deviation=_safe_deviation(
            proportions.shoulder_hip_ratio, default_shoulder_hip,
        ),
        arm_length_deviation=_safe_deviation(measured_arm, default_arm_m),
        leg_length_deviation=_safe_deviation(measured_leg, default_leg_m),
        arm_asymmetry=proportions.arm_asymmetry,
        leg_asymmetry=proportions.leg_asymmetry,
    )


def has_significant_deviation(deviation: ProportionDeviation) -> bool:
    """
    유의미한 편차가 있는지 확인.

    편차 절대값이 SIGNIFICANT_DEVIATION_THRESHOLD 이상인 항목이
    하나라도 있으면 True.

    Args:
        deviation: 편차 정보

    Returns:
        유의미한 편차 존재 여부
    """
    return (
        abs(deviation.height_deviation) >= SIGNIFICANT_DEVIATION_THRESHOLD
        or abs(deviation.wingspan_ratio_deviation) >= SIGNIFICANT_DEVIATION_THRESHOLD
        or abs(deviation.arm_length_deviation) >= SIGNIFICANT_DEVIATION_THRESHOLD
        or abs(deviation.leg_length_deviation) >= SIGNIFICANT_DEVIATION_THRESHOLD
    )


# =============================================================================
# PersonalProfile 생성
# =============================================================================
def create_personal_profile(
    proportions: BodyProportions,
    age: int,
    gender: Gender,
    weight_kg: float | None = None,
    is_stable: bool = False,
    sample_count: int = 1,
) -> PersonalProfile:
    """
    영상 추정 신체 비율로부터 개인 프로파일 생성.

    체중이 제공되지 않으면 BMI 기반으로 추정합니다.

    Args:
        proportions: 측정된 신체 비율 (BodyProportions)
        age: 나이 (세)
        gender: 성별
        weight_kg: 실제 체중 (kg). None이면 BMI 추정.
        is_stable: 측정값 안정화 여부
        sample_count: 누적 샘플 수

    Returns:
        PersonalProfile 객체
    """
    height_m = proportions.estimated_height_m
    height_cm = height_m * 100.0

    # 체중: 제공되지 않으면 BMI 기반 추정
    age_group = AgeGroup.from_age(age)
    effective_weight = (
        weight_kg
        if weight_kg is not None
        else estimate_body_mass_from_height(height_cm, gender, age_group)
    )

    # 편차 계산
    deviation = calculate_proportion_deviation(proportions, age, gender)

    # 개인화된 BodyModel
    body_model = create_body_model(
        body_mass_kg=effective_weight,
        height_cm=height_cm,
        gender=gender,
        age_group=age_group,
    )

    return PersonalProfile(
        age=age,
        age_group=age_group,
        gender=gender,
        height_m=height_m,
        weight_kg=effective_weight,
        proportions=proportions,
        deviation=deviation,
        body_model=body_model,
        is_stable=is_stable,
        sample_count=sample_count,
    )


# =============================================================================
# 측정값 안정화 (다중 프레임 이동 평균)
# =============================================================================
class ProportionStabilizer:
    """
    다중 프레임 신체 비율 안정화기.

    포즈 추정의 프레임별 노이즈를 줄이기 위해
    이동 평균으로 안정적인 BodyProportions를 생성합니다.
    스레드 안전합니다.

    사용 흐름:
        1. 앱 시작 시 스캔 모드 진입 (정면/측면 촬영)
        2. 매 프레임 add_sample() 호출
        3. is_stable == True이면 get_stable_profile() 호출
        4. 이후 분석에서 안정화된 프로파일 사용

    Attributes:
        _age: 나이
        _gender: 성별
        _weight_kg: 체중 (None이면 자동 추정)
        _window_size: 이동 평균 윈도우 크기
        _min_samples: 안정화 최소 샘플 수
    """

    __slots__ = (
        "_age",
        "_gender",
        "_weight_kg",
        "_window_size",
        "_min_samples",
        "_height_buf",
        "_wingspan_ratio_buf",
        "_upper_lower_buf",
        "_shoulder_hip_buf",
        "_r_arm_buf",
        "_l_arm_buf",
        "_r_leg_buf",
        "_l_leg_buf",
        "_shoulder_width_buf",
        "_hip_width_buf",
        "_upper_body_buf",
        "_lower_body_buf",
        "_total_count",
        "_lock",
    )

    def __init__(
        self,
        age: int,
        gender: Gender,
        weight_kg: float | None = None,
        window_size: int = STABILIZATION_WINDOW,
        min_samples: int = MIN_SAMPLES_FOR_STABLE,
    ) -> None:
        self._age = age
        self._gender = gender
        self._weight_kg = weight_kg
        self._window_size = window_size
        self._min_samples = min_samples

        self._height_buf: deque[float] = deque(maxlen=window_size)
        self._wingspan_ratio_buf: deque[float] = deque(maxlen=window_size)
        self._upper_lower_buf: deque[float] = deque(maxlen=window_size)
        self._shoulder_hip_buf: deque[float] = deque(maxlen=window_size)
        self._r_arm_buf: deque[float] = deque(maxlen=window_size)
        self._l_arm_buf: deque[float] = deque(maxlen=window_size)
        self._r_leg_buf: deque[float] = deque(maxlen=window_size)
        self._l_leg_buf: deque[float] = deque(maxlen=window_size)
        self._shoulder_width_buf: deque[float] = deque(maxlen=window_size)
        self._hip_width_buf: deque[float] = deque(maxlen=window_size)
        self._upper_body_buf: deque[float] = deque(maxlen=window_size)
        self._lower_body_buf: deque[float] = deque(maxlen=window_size)
        self._total_count = 0
        self._lock = threading.RLock()

    @property
    def sample_count(self) -> int:
        """누적 샘플 수."""
        return self._total_count

    @property
    def is_stable(self) -> bool:
        """측정값이 안정화되었는지 여부."""
        return self._total_count >= self._min_samples

    def add_sample(self, proportions: BodyProportions) -> None:
        """
        프레임별 신체 비율 측정값 추가.

        유효하지 않은 측정값(비정상 범위)은 무시합니다.

        Args:
            proportions: 단일 프레임 신체 비율
        """
        # 유효성 검증
        if not self._is_valid_proportions(proportions):
            return

        with self._lock:
            self._height_buf.append(proportions.estimated_height_m)
            self._wingspan_ratio_buf.append(proportions.wingspan_height_ratio)
            self._upper_lower_buf.append(proportions.upper_lower_ratio)
            self._shoulder_hip_buf.append(proportions.shoulder_hip_ratio)
            self._r_arm_buf.append(proportions.right_arm_m)
            self._l_arm_buf.append(proportions.left_arm_m)
            self._r_leg_buf.append(proportions.right_leg_m)
            self._l_leg_buf.append(proportions.left_leg_m)
            self._shoulder_width_buf.append(proportions.shoulder_width_m)
            self._hip_width_buf.append(proportions.hip_width_m)
            self._upper_body_buf.append(proportions.upper_body_m)
            self._lower_body_buf.append(proportions.lower_body_m)
            self._total_count += 1

    def get_stabilized_proportions(self) -> BodyProportions | None:
        """
        안정화된 신체 비율 반환.

        최소 샘플 수 미달이면 None 반환.

        Returns:
            안정화된 BodyProportions 또는 None
        """
        with self._lock:
            if not self.is_stable:
                return None
            return self._compute_average()

    def get_personal_profile(self) -> PersonalProfile | None:
        """
        안정화된 측정값으로 PersonalProfile 생성.

        안정화 전이면 None 반환.

        Returns:
            PersonalProfile 또는 None
        """
        proportions = self.get_stabilized_proportions()
        if proportions is None:
            return None

        return create_personal_profile(
            proportions=proportions,
            age=self._age,
            gender=self._gender,
            weight_kg=self._weight_kg,
            is_stable=True,
            sample_count=self._total_count,
        )

    def reset(self) -> None:
        """모든 측정값 초기화."""
        with self._lock:
            self._height_buf.clear()
            self._wingspan_ratio_buf.clear()
            self._upper_lower_buf.clear()
            self._shoulder_hip_buf.clear()
            self._r_arm_buf.clear()
            self._l_arm_buf.clear()
            self._r_leg_buf.clear()
            self._l_leg_buf.clear()
            self._shoulder_width_buf.clear()
            self._hip_width_buf.clear()
            self._upper_body_buf.clear()
            self._lower_body_buf.clear()
            self._total_count = 0

    def _is_valid_proportions(self, p: BodyProportions) -> bool:
        """측정값 유효성 검증."""
        if not MIN_HEIGHT_M <= p.estimated_height_m <= MAX_HEIGHT_M:
            return False
        if not MIN_WINGSPAN_RATIO <= p.wingspan_height_ratio <= MAX_WINGSPAN_RATIO:
            return False
        if not MIN_UPPER_LOWER_RATIO <= p.upper_lower_ratio <= MAX_UPPER_LOWER_RATIO:
            return False
        return True

    def _compute_average(self) -> BodyProportions:
        """버퍼 내 측정값의 이동 평균 계산."""
        height = _mean(self._height_buf)
        wingspan_ratio = _mean(self._wingspan_ratio_buf)
        upper_body = _mean(self._upper_body_buf)
        lower_body = _mean(self._lower_body_buf)
        shoulder_width = _mean(self._shoulder_width_buf)
        hip_width = _mean(self._hip_width_buf)
        r_arm = _mean(self._r_arm_buf)
        l_arm = _mean(self._l_arm_buf)
        r_leg = _mean(self._r_leg_buf)
        l_leg = _mean(self._l_leg_buf)

        wingspan = height * wingspan_ratio

        return BodyProportions(
            estimated_height_m=height,
            wingspan_m=wingspan,
            wingspan_height_ratio=wingspan_ratio,
            upper_body_m=upper_body,
            lower_body_m=lower_body,
            upper_lower_ratio=_safe_ratio(upper_body, lower_body),
            shoulder_width_m=shoulder_width,
            hip_width_m=hip_width,
            shoulder_hip_ratio=_safe_ratio(shoulder_width, hip_width),
            right_arm_m=r_arm,
            left_arm_m=l_arm,
            arm_asymmetry=_asymmetry(l_arm, r_arm),
            right_leg_m=r_leg,
            left_leg_m=l_leg,
            leg_asymmetry=_asymmetry(l_leg, r_leg),
        )


# =============================================================================
# 유틸리티 함수
# =============================================================================
def _mean(buf: deque[float]) -> float:
    """deque 평균 계산."""
    if not buf:
        return 0.0
    return sum(buf) / len(buf)


def _safe_ratio(numerator: float, denominator: float) -> float:
    """안전한 비율 계산."""
    if abs(denominator) < 1e-9:
        return 0.0
    return numerator / denominator


def _asymmetry(left: float, right: float) -> float:
    """좌우 비대칭도 (0=대칭, 1=최대비대칭)."""
    max_val = max(left, right)
    if max_val < 0.01:
        return 0.0
    return abs(left - right) / max_val


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 상수
    "STABILIZATION_WINDOW",
    "MIN_SAMPLES_FOR_STABLE",
    "SIGNIFICANT_DEVIATION_THRESHOLD",
    # 데이터클래스
    "ProportionDeviation",
    "PersonalProfile",
    # 핵심 함수
    "create_personal_profile",
    "calculate_proportion_deviation",
    "has_significant_deviation",
    # 안정화 클래스
    "ProportionStabilizer",
]

__version__ = "1.0.0"
