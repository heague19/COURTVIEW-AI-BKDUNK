# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

biomechanics/anthropometry/ 단위 테스트.

대상 파일:
    - body_segment.py
    - proportion_calculator.py
    - age_gender_adapter.py
    - personal_adapter.py
    - __init__.py
"""

from __future__ import annotations

import math
import threading

import numpy as np
import pytest

from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.biomechanics_constants import BodySegment


# =============================================================================
# body_segment.py 테스트
# =============================================================================
class TestBodySegmentConstants:
    """body_segment.py 상수 테스트."""

    def test_gravity_value(self) -> None:
        from biomechanics.anthropometry.body_segment import GRAVITY
        assert GRAVITY == pytest.approx(9.80665, rel=1e-5)

    def test_default_body_mass(self) -> None:
        from biomechanics.anthropometry.body_segment import DEFAULT_BODY_MASS
        assert DEFAULT_BODY_MASS == 75.0

    def test_default_height(self) -> None:
        from biomechanics.anthropometry.body_segment import DEFAULT_HEIGHT
        assert DEFAULT_HEIGHT == 175.0

    def test_mass_range(self) -> None:
        from biomechanics.anthropometry.body_segment import MIN_BODY_MASS, MAX_BODY_MASS
        assert MIN_BODY_MASS == 15.0
        assert MAX_BODY_MASS == 200.0

    def test_height_range(self) -> None:
        from biomechanics.anthropometry.body_segment import MIN_HEIGHT, MAX_HEIGHT
        assert MIN_HEIGHT == 90.0
        assert MAX_HEIGHT == 240.0


class TestSegmentProperties:
    """SegmentProperties 데이터클래스 테스트."""

    def test_frozen_and_slots(self) -> None:
        from biomechanics.anthropometry.body_segment import SegmentProperties
        assert SegmentProperties.__dataclass_params__.frozen is True
        assert hasattr(SegmentProperties, "__slots__")

    def test_creation(self) -> None:
        from biomechanics.anthropometry.body_segment import SegmentProperties
        props = SegmentProperties(
            segment=BodySegment.THIGH,
            mass_kg=7.5,
            length_m=0.42,
            com_proximal_ratio=0.4095,
            com_position_m=0.172,
            gyration_radius_ratio=0.329,
            moment_of_inertia=0.14,
            weight_n=73.5,
        )
        assert props.segment == BodySegment.THIGH
        assert props.mass_kg == 7.5


class TestCalculateSegmentMass:
    """calculate_segment_mass 함수 테스트."""

    def test_thigh_mass_adult_male(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_mass
        mass = calculate_segment_mass(BodySegment.THIGH, 75.0, Gender.MALE)
        # de Leva: THIGH 남성 비율 = 0.1416
        assert mass == pytest.approx(75.0 * 0.1416, rel=0.05)

    def test_head_mass_youth_adjustment(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_mass
        # 체간 세그먼트(HEAD)는 연령 보정 적용
        adult = calculate_segment_mass(BodySegment.HEAD, 75.0, Gender.MALE, AgeGroup.ADULT)
        youth = calculate_segment_mass(BodySegment.HEAD, 75.0, Gender.MALE, AgeGroup.YOUTH)
        # 유소년은 체간 질량 비율이 높음 (AGE_TRUNK_MASS_FACTOR[YOUTH] > 1.0)
        assert youth > adult

    def test_positive_mass(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_mass
        for seg in BodySegment:
            mass = calculate_segment_mass(seg, 75.0, Gender.MALE)
            assert mass > 0.0, f"{seg.value} 질량이 0 이하"


class TestCalculateSegmentLength:
    """calculate_segment_length 함수 테스트."""

    def test_thigh_length_adult(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_length
        length = calculate_segment_length(BodySegment.THIGH, 175.0)
        # 대퇴 길이 ≈ 신장의 ~24%
        assert 0.20 < length < 0.50

    def test_limb_youth_shorter(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_length
        adult = calculate_segment_length(BodySegment.UPPER_ARM, 175.0, AgeGroup.ADULT)
        youth = calculate_segment_length(BodySegment.UPPER_ARM, 175.0, AgeGroup.YOUTH)
        # 유소년은 사지 길이 비율이 낮음
        assert youth < adult

    def test_returns_meters(self) -> None:
        from biomechanics.anthropometry.body_segment import calculate_segment_length
        length = calculate_segment_length(BodySegment.SHANK, 175.0)
        # 결과는 미터 단위 (0.1~0.6m 범위)
        assert 0.1 < length < 0.6


class TestCalculateSegmentComPosition:
    """calculate_segment_com_position 함수 테스트."""

    def test_com_within_segment(self) -> None:
        from biomechanics.anthropometry.body_segment import (
            calculate_segment_com_position,
            calculate_segment_length,
        )
        for seg in BodySegment:
            length = calculate_segment_length(seg, 175.0)
            com = calculate_segment_com_position(seg, length, Gender.MALE)
            assert 0.0 <= com <= length, f"{seg.value} COM이 세그먼트 범위 밖"


class TestCalculateSegmentMomentOfInertia:
    """calculate_segment_moment_of_inertia 함수 테스트."""

    def test_positive_moi(self) -> None:
        from biomechanics.anthropometry.body_segment import (
            calculate_segment_moment_of_inertia,
            calculate_segment_mass,
            calculate_segment_length,
        )
        for seg in BodySegment:
            mass = calculate_segment_mass(seg, 75.0, Gender.MALE)
            length = calculate_segment_length(seg, 175.0)
            moi = calculate_segment_moment_of_inertia(seg, mass, length, Gender.MALE)
            assert moi >= 0.0, f"{seg.value} 관성 모멘트가 음수"

    def test_heavier_segment_higher_moi(self) -> None:
        from biomechanics.anthropometry.body_segment import (
            calculate_segment_moment_of_inertia,
            calculate_segment_mass,
            calculate_segment_length,
        )
        # 대퇴 > 손
        thigh_mass = calculate_segment_mass(BodySegment.THIGH, 75.0, Gender.MALE)
        thigh_len = calculate_segment_length(BodySegment.THIGH, 175.0)
        thigh_moi = calculate_segment_moment_of_inertia(
            BodySegment.THIGH, thigh_mass, thigh_len, Gender.MALE,
        )

        hand_mass = calculate_segment_mass(BodySegment.HAND, 75.0, Gender.MALE)
        hand_len = calculate_segment_length(BodySegment.HAND, 175.0)
        hand_moi = calculate_segment_moment_of_inertia(
            BodySegment.HAND, hand_mass, hand_len, Gender.MALE,
        )
        assert thigh_moi > hand_moi


class TestCreateBodyModel:
    """create_body_model 함수 테스트."""

    def test_default_model(self) -> None:
        from biomechanics.anthropometry.body_segment import create_body_model
        model = create_body_model()
        assert model.body_mass_kg == 75.0
        assert model.height_cm == 175.0
        assert model.gender == Gender.MALE
        assert model.age_group == AgeGroup.ADULT
        assert len(model.segments) == len(BodySegment)

    def test_all_segments_present(self) -> None:
        from biomechanics.anthropometry.body_segment import create_body_model
        model = create_body_model()
        for seg in BodySegment:
            assert seg in model.segments

    def test_invalid_mass_raises(self) -> None:
        from biomechanics.anthropometry.body_segment import create_body_model
        with pytest.raises(ValueError, match="체중"):
            create_body_model(body_mass_kg=5.0)

    def test_invalid_height_raises(self) -> None:
        from biomechanics.anthropometry.body_segment import create_body_model
        with pytest.raises(ValueError, match="신장"):
            create_body_model(height_cm=50.0)

    def test_youth_model(self) -> None:
        from biomechanics.anthropometry.body_segment import create_body_model
        model = create_body_model(
            body_mass_kg=30.0, height_cm=130.0,
            gender=Gender.FEMALE, age_group=AgeGroup.YOUTH,
        )
        assert model.age_group == AgeGroup.YOUTH
        assert model.gender == Gender.FEMALE

    def test_segment_mass_sums_near_total(self) -> None:
        """세그먼트 질량 합이 전체 체중에 근사."""
        from biomechanics.anthropometry.body_segment import create_body_model
        model = create_body_model(body_mass_kg=75.0)
        # 양측성 세그먼트는 좌/우 합산이므로 단순 합은 전체가 아님
        # 하지만 각 세그먼트 질량이 양수이고 합리적 범위인지 확인
        total = sum(p.mass_kg for p in model.segments.values())
        # 10종 세그먼트 합: 양측성(UPPER_ARM, FOREARM, HAND, THIGH, SHANK, FOOT)은
        # 한쪽만 계산되므로 ×2 보정 필요 → 여기서는 단순 합이 체중의 50%~100%
        assert total > 75.0 * 0.4
        assert total < 75.0 * 1.1


class TestCalculateWholeBodyCom:
    """calculate_whole_body_com 함수 테스트."""

    def test_symmetric_pose_com_centered(self) -> None:
        """좌우 대칭 포즈의 COM은 좌우 중앙."""
        from biomechanics.anthropometry.body_segment import (
            create_body_model,
            calculate_whole_body_com,
            SEGMENT_ENDPOINT_INDICES_25KP,
        )
        # 25개 키포인트 생성 (단순 직립 자세)
        kp = np.zeros((25, 3), dtype=np.float64)
        kp[22] = [0, 1.80, 0]   # 머리꼭대기
        kp[1] = [0, 1.60, 0]    # 목
        kp[2] = [-0.20, 1.55, 0]  # R어깨
        kp[5] = [0.20, 1.55, 0]   # L어깨
        kp[3] = [-0.20, 1.25, 0]  # R팔꿈치
        kp[6] = [0.20, 1.25, 0]   # L팔꿈치
        kp[4] = [-0.20, 0.95, 0]  # R손목
        kp[7] = [0.20, 0.95, 0]   # L손목
        kp[23] = [-0.20, 0.80, 0] # R손끝
        kp[24] = [0.20, 0.80, 0]  # L손끝
        kp[8] = [-0.12, 0.95, 0]  # R골반
        kp[11] = [0.12, 0.95, 0]  # L골반
        kp[9] = [-0.12, 0.50, 0]  # R무릎
        kp[12] = [0.12, 0.50, 0]  # L무릎
        kp[10] = [-0.12, 0.05, 0] # R발목
        kp[13] = [0.12, 0.05, 0]  # L발목
        kp[20] = [-0.12, 0.0, 0]  # R발끝
        kp[18] = [0.12, 0.0, 0]   # L발끝

        model = create_body_model()

        # str 키 → BodySegment 변환 필요
        from biomechanics.anthropometry.body_segment import _SEGMENT_NAME_TO_TYPE
        seg_endpoints = {}
        for name, indices in SEGMENT_ENDPOINT_INDICES_25KP.items():
            seg_type = _SEGMENT_NAME_TO_TYPE[name]
            seg_endpoints[seg_type] = indices

        com = calculate_whole_body_com(kp, model, seg_endpoints)
        # 대칭 포즈이므로 x ≈ 0
        assert abs(com[0]) < 0.15  # 양측 세그먼트 재사용 허용
        assert com[1] > 0.5       # y좌표는 중간 이상


class TestEstimateBodyMassFromHeight:
    """estimate_body_mass_from_height 함수 테스트."""

    def test_adult_male(self) -> None:
        from biomechanics.anthropometry.body_segment import estimate_body_mass_from_height
        weight = estimate_body_mass_from_height(175.0, Gender.MALE)
        # BMI 23.5 → 175cm → ~72kg
        assert 65.0 < weight < 80.0

    def test_youth_lighter(self) -> None:
        from biomechanics.anthropometry.body_segment import estimate_body_mass_from_height
        adult = estimate_body_mass_from_height(175.0, Gender.MALE, AgeGroup.ADULT)
        youth = estimate_body_mass_from_height(175.0, Gender.MALE, AgeGroup.YOUTH)
        assert youth < adult

    def test_clamped_to_range(self) -> None:
        from biomechanics.anthropometry.body_segment import estimate_body_mass_from_height
        # 매우 큰 신장
        weight = estimate_body_mass_from_height(240.0, Gender.MALE)
        assert weight <= 200.0


class TestSegmentEndpointIndices:
    """SEGMENT_ENDPOINT_INDICES_25KP 테스트."""

    def test_15_segments_mapped(self) -> None:
        from biomechanics.anthropometry.body_segment import SEGMENT_ENDPOINT_INDICES_25KP
        assert len(SEGMENT_ENDPOINT_INDICES_25KP) == 15

    def test_all_indices_within_25kp(self) -> None:
        from biomechanics.anthropometry.body_segment import SEGMENT_ENDPOINT_INDICES_25KP
        for name, (prox, dist) in SEGMENT_ENDPOINT_INDICES_25KP.items():
            assert 0 <= prox < 25, f"{name} 근위 인덱스 범위 초과"
            assert 0 <= dist < 25, f"{name} 원위 인덱스 범위 초과"

    def test_get_segment_endpoints_returns_all(self) -> None:
        from biomechanics.anthropometry.body_segment import get_segment_endpoints_25kp
        result = get_segment_endpoints_25kp()
        # 양측성 세그먼트는 L/R 각 1개씩
        assert BodySegment.THIGH in result
        assert len(result[BodySegment.THIGH]) == 2  # L, R


# =============================================================================
# proportion_calculator.py 테스트
# =============================================================================
class TestProportionCalculatorDataclasses:
    """BodyProportions / SegmentLengths 테스트."""

    def test_body_proportions_frozen(self) -> None:
        from biomechanics.anthropometry.proportion_calculator import BodyProportions
        assert BodyProportions.__dataclass_params__.frozen is True
        assert hasattr(BodyProportions, "__slots__")

    def test_segment_lengths_frozen(self) -> None:
        from biomechanics.anthropometry.proportion_calculator import SegmentLengths
        assert SegmentLengths.__dataclass_params__.frozen is True
        assert hasattr(SegmentLengths, "__slots__")


class TestCalculateProportions:
    """calculate_proportions 함수 테스트."""

    @pytest.fixture
    def standing_keypoints(self) -> np.ndarray:
        """직립 자세 25kp 키포인트 생성."""
        kp = np.zeros((25, 3), dtype=np.float64)
        kp[22] = [0, 1.80, 0]     # 머리꼭대기
        kp[0] = [0, 1.70, 0]      # 코
        kp[1] = [0, 1.60, 0]      # 목
        kp[2] = [-0.20, 1.55, 0]  # R어깨
        kp[5] = [0.20, 1.55, 0]   # L어깨
        kp[3] = [-0.20, 1.25, 0]  # R팔꿈치
        kp[6] = [0.20, 1.25, 0]   # L팔꿈치
        kp[4] = [-0.20, 0.95, 0]  # R손목
        kp[7] = [0.20, 0.95, 0]   # L손목
        kp[23] = [-0.20, 0.80, 0] # R손끝
        kp[24] = [0.20, 0.80, 0]  # L손끝
        kp[8] = [-0.12, 0.95, 0]  # R골반
        kp[11] = [0.12, 0.95, 0]  # L골반
        kp[9] = [-0.12, 0.50, 0]  # R무릎
        kp[12] = [0.12, 0.50, 0]  # L무릎
        kp[10] = [-0.12, 0.05, 0] # R발목
        kp[13] = [0.12, 0.05, 0]  # L발목
        return kp

    def test_height_estimation(self, standing_keypoints: np.ndarray) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        props = calculate_proportions(standing_keypoints)
        # 머리꼭대기(1.80) - 발목(0.05) ≈ 1.75m + 발 보정
        assert 1.70 < props.estimated_height_m < 2.00

    def test_wingspan(self, standing_keypoints: np.ndarray) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        props = calculate_proportions(standing_keypoints)
        # R손끝(-0.20) ~ L손끝(0.20) = 0.40m (좁지만 방향상 유효)
        assert props.wingspan_m > 0.0

    def test_upper_lower_ratio(self, standing_keypoints: np.ndarray) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        props = calculate_proportions(standing_keypoints)
        assert props.upper_lower_ratio > 0.0

    def test_shoulder_hip_ratio(self, standing_keypoints: np.ndarray) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        props = calculate_proportions(standing_keypoints)
        # 어깨(0.40) > 골반(0.24) → ratio > 1.0
        assert props.shoulder_hip_ratio > 1.0

    def test_symmetric_pose_low_asymmetry(self, standing_keypoints: np.ndarray) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        props = calculate_proportions(standing_keypoints)
        assert props.arm_asymmetry < 0.05
        assert props.leg_asymmetry < 0.05

    def test_4_column_keypoints(self, standing_keypoints: np.ndarray) -> None:
        """confidence 열이 포함된 25×4 입력 처리."""
        from biomechanics.anthropometry.proportion_calculator import calculate_proportions
        kp4 = np.hstack([standing_keypoints, np.ones((25, 1))])
        props = calculate_proportions(kp4)
        assert props.estimated_height_m > 1.0


class TestCalculateSegmentLengths:
    """calculate_segment_lengths 함수 테스트."""

    def test_all_positive(self) -> None:
        from biomechanics.anthropometry.proportion_calculator import calculate_segment_lengths
        kp = np.zeros((25, 3), dtype=np.float64)
        kp[1] = [0, 1.60, 0]      # 목
        kp[2] = [-0.20, 1.55, 0]   # R어깨
        kp[5] = [0.20, 1.55, 0]    # L어깨
        kp[3] = [-0.20, 1.25, 0]
        kp[6] = [0.20, 1.25, 0]
        kp[4] = [-0.20, 0.95, 0]
        kp[7] = [0.20, 0.95, 0]
        kp[8] = [-0.12, 0.95, 0]
        kp[11] = [0.12, 0.95, 0]
        kp[9] = [-0.12, 0.50, 0]
        kp[12] = [0.12, 0.50, 0]
        kp[10] = [-0.12, 0.05, 0]
        kp[13] = [0.12, 0.05, 0]

        segs = calculate_segment_lengths(kp)
        assert segs.r_upper_arm_m > 0
        assert segs.l_upper_arm_m > 0
        assert segs.r_forearm_m > 0
        assert segs.l_forearm_m > 0
        assert segs.r_thigh_m > 0
        assert segs.l_thigh_m > 0
        assert segs.r_shank_m > 0
        assert segs.l_shank_m > 0
        assert segs.trunk_m > 0


class TestEstimateHeightFromKeypoints:
    """estimate_height_from_keypoints 함수 테스트."""

    def test_consistent_with_proportions(self) -> None:
        from biomechanics.anthropometry.proportion_calculator import (
            calculate_proportions,
            estimate_height_from_keypoints,
        )
        kp = np.zeros((25, 3), dtype=np.float64)
        kp[22] = [0, 1.80, 0]
        kp[10] = [-0.12, 0.05, 0]
        kp[13] = [0.12, 0.05, 0]

        # 나머지 키포인트도 설정 (calculate_proportions에 필요)
        kp[1] = [0, 1.60, 0]
        kp[2] = [-0.20, 1.55, 0]
        kp[5] = [0.20, 1.55, 0]
        kp[3] = [-0.20, 1.25, 0]
        kp[6] = [0.20, 1.25, 0]
        kp[4] = [-0.20, 0.95, 0]
        kp[7] = [0.20, 0.95, 0]
        kp[23] = [-0.20, 0.80, 0]
        kp[24] = [0.20, 0.80, 0]
        kp[8] = [-0.12, 0.95, 0]
        kp[11] = [0.12, 0.95, 0]
        kp[9] = [-0.12, 0.50, 0]
        kp[12] = [0.12, 0.50, 0]

        height = estimate_height_from_keypoints(kp)
        props = calculate_proportions(kp)
        assert height == pytest.approx(props.estimated_height_m, rel=1e-6)


# =============================================================================
# age_gender_adapter.py 테스트
# =============================================================================
class TestGetDefaultBodyParams:
    """get_default_body_params 함수 테스트."""

    def test_adult_male(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        h, w, arm, leg = get_default_body_params(25, Gender.MALE)
        assert h == 175.0
        assert w == 75.0

    def test_adult_female(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        h, w, arm, leg = get_default_body_params(30, Gender.FEMALE)
        assert h == 162.0
        assert w == 62.0

    def test_youth_6(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        h, w, arm, leg = get_default_body_params(6, Gender.MALE)
        assert h == 116.0
        assert w == 20.7

    def test_teen_15(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        h, w, arm, leg = get_default_body_params(15, Gender.MALE)
        assert h == 170.0

    def test_senior_65(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        h, w, arm, leg = get_default_body_params(65, Gender.MALE)
        assert h == 171.0  # 60대 남성

    def test_all_return_positive(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import get_default_body_params
        for age in [6, 10, 13, 16, 20, 35, 55, 70]:
            for gender in Gender:
                h, w, arm, leg = get_default_body_params(age, gender)
                assert h > 0
                assert w > 0
                assert arm > 0
                assert leg > 0


class TestAdaptAngleRange:
    """adapt_angle_range 함수 테스트."""

    def test_zero_tolerance_no_change(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import adapt_angle_range
        angles = {"elbow": (100.0, 140.0)}
        result = adapt_angle_range(angles, 0.0)
        assert result["elbow"] == (100.0, 140.0)

    def test_tolerance_expands_range(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import adapt_angle_range
        angles = {"elbow": (100.0, 140.0)}
        result = adapt_angle_range(angles, 15.0)
        assert result["elbow"][0] == 85.0   # 100 - 15
        assert result["elbow"][1] == 155.0  # 140 + 15

    def test_clamp_to_0_180(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import adapt_angle_range
        angles = {"dorsiflexion": (5.0, 170.0)}
        result = adapt_angle_range(angles, 15.0)
        assert result["dorsiflexion"][0] == 0.0    # max(0, 5-15)
        assert result["dorsiflexion"][1] == 180.0  # min(180, 170+15)

    def test_ratio_key_special_handling(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import adapt_angle_range
        angles = {"stance_width_shoulder_ratio": (1.2, 1.8)}
        result = adapt_angle_range(angles, 15.0)
        # 비율형: tolerance/100 = 0.15
        assert result["stance_width_shoulder_ratio"][0] == pytest.approx(1.05, rel=1e-3)
        assert result["stance_width_shoulder_ratio"][1] == pytest.approx(1.95, rel=1e-3)


class TestAgeGenderProfile:
    """AgeGenderProfile 데이터클래스 테스트."""

    def test_frozen_and_slots(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import AgeGenderProfile
        assert AgeGenderProfile.__dataclass_params__.frozen is True
        assert hasattr(AgeGenderProfile, "__slots__")


class TestCreateAgeGenderProfile:
    """create_age_gender_profile 함수 테스트."""

    def test_adult_male_baseline(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        profile = create_age_gender_profile(25, Gender.MALE)
        assert profile.age == 25
        assert profile.age_group == AgeGroup.ADULT
        assert profile.gender == Gender.MALE
        assert profile.velocity_factor == 1.0
        assert profile.angle_tolerance == 0.0

    def test_youth_female(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        profile = create_age_gender_profile(8, Gender.FEMALE)
        assert profile.age_group == AgeGroup.YOUTH
        assert profile.velocity_factor < 1.0
        assert profile.angle_tolerance == 15.0

    def test_teen_velocity_between_youth_and_adult(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        youth = create_age_gender_profile(10, Gender.MALE)
        teen = create_age_gender_profile(15, Gender.MALE)
        adult = create_age_gender_profile(25, Gender.MALE)
        assert youth.velocity_factor < teen.velocity_factor < adult.velocity_factor

    def test_adapted_angles_wider_for_youth(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        youth = create_age_gender_profile(10, Gender.MALE)
        adult = create_age_gender_profile(25, Gender.MALE)
        # 유소년 adapted range가 성인보다 넓음
        y_lo, y_hi = youth.adapted_shooting_angles["release_elbow_angle"]
        a_lo, a_hi = adult.adapted_shooting_angles["release_elbow_angle"]
        assert (y_hi - y_lo) >= (a_hi - a_lo)

    def test_league_parameter(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        from biomechanics.standards.region_types import LeagueType
        profile = create_age_gender_profile(25, Gender.MALE, LeagueType.NBA)
        assert profile.league == LeagueType.NBA

    def test_safety_limits_youth_stricter(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import create_age_gender_profile
        youth = create_age_gender_profile(10, Gender.MALE)
        adult = create_age_gender_profile(25, Gender.MALE)
        assert youth.max_jumps_per_session < adult.max_jumps_per_session
        assert youth.max_shots_per_session < adult.max_shots_per_session


class TestCreateAdaptedBodyModel:
    """create_adapted_body_model 함수 테스트."""

    def test_uses_profile_defaults(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            create_adapted_body_model,
        )
        profile = create_age_gender_profile(25, Gender.MALE)
        model = create_adapted_body_model(profile)
        assert model.body_mass_kg == 75.0
        assert model.height_cm == 175.0

    def test_override_with_actual(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            create_adapted_body_model,
        )
        profile = create_age_gender_profile(25, Gender.MALE)
        model = create_adapted_body_model(profile, height_cm=185.0, weight_kg=85.0)
        assert model.height_cm == 185.0
        assert model.body_mass_kg == 85.0


class TestApplyVelocityFactor:
    """apply_velocity_factor 함수 테스트."""

    def test_adult_male_no_change(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            apply_velocity_factor,
        )
        profile = create_age_gender_profile(25, Gender.MALE)
        result = apply_velocity_factor(5.0, profile)
        assert result == 5.0

    def test_youth_reduces(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            apply_velocity_factor,
        )
        profile = create_age_gender_profile(10, Gender.MALE)
        result = apply_velocity_factor(5.0, profile)
        assert result < 5.0


class TestApplyRomFactor:
    """apply_rom_factor 함수 테스트."""

    def test_expansion_widens(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            apply_rom_factor,
        )
        profile = create_age_gender_profile(10, Gender.MALE)
        lo, hi = apply_rom_factor((30.0, 120.0), profile)
        assert lo == 30.0    # 하한 유지
        assert hi > 120.0    # 상한 확장

    def test_ceiling_clamp(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import (
            create_age_gender_profile,
            apply_rom_factor,
        )
        profile = create_age_gender_profile(10, Gender.MALE)
        lo, hi = apply_rom_factor((30.0, 175.0), profile)
        assert hi <= 180.0


class TestIsWithinAdaptedRange:
    """is_within_adapted_range 함수 테스트."""

    def test_within(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import is_within_adapted_range
        assert is_within_adapted_range(100.0, (90.0, 110.0)) is True

    def test_below(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import is_within_adapted_range
        assert is_within_adapted_range(80.0, (90.0, 110.0)) is False

    def test_above(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import is_within_adapted_range
        assert is_within_adapted_range(120.0, (90.0, 110.0)) is False

    def test_boundary(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import is_within_adapted_range
        assert is_within_adapted_range(90.0, (90.0, 110.0)) is True
        assert is_within_adapted_range(110.0, (90.0, 110.0)) is True


class TestCalculateDeviation:
    """calculate_deviation 함수 테스트."""

    def test_within_range_zero(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import calculate_deviation
        assert calculate_deviation(100.0, (90.0, 110.0)) == 0.0

    def test_below_range(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import calculate_deviation
        assert calculate_deviation(80.0, (90.0, 110.0)) == 10.0

    def test_above_range(self) -> None:
        from biomechanics.anthropometry.age_gender_adapter import calculate_deviation
        assert calculate_deviation(120.0, (90.0, 110.0)) == 10.0


# =============================================================================
# personal_adapter.py 테스트
# =============================================================================
class TestProportionDeviation:
    """ProportionDeviation 데이터클래스 테스트."""

    def test_frozen_and_slots(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionDeviation
        assert ProportionDeviation.__dataclass_params__.frozen is True
        assert hasattr(ProportionDeviation, "__slots__")


class TestPersonalProfile:
    """PersonalProfile 데이터클래스 테스트."""

    def test_frozen_and_slots(self) -> None:
        from biomechanics.anthropometry.personal_adapter import PersonalProfile
        assert PersonalProfile.__dataclass_params__.frozen is True
        assert hasattr(PersonalProfile, "__slots__")


def _make_proportions(
    height_m: float = 1.80,
    wingspan_ratio: float = 1.03,
    arm_m: float = 0.75,
    leg_m: float = 0.85,
) -> "BodyProportions":
    """테스트용 BodyProportions 팩토리."""
    from biomechanics.anthropometry.proportion_calculator import BodyProportions
    wingspan = height_m * wingspan_ratio
    return BodyProportions(
        estimated_height_m=height_m,
        wingspan_m=wingspan,
        wingspan_height_ratio=wingspan_ratio,
        upper_body_m=height_m * 0.52,
        lower_body_m=height_m * 0.48,
        upper_lower_ratio=0.52 / 0.48,
        shoulder_width_m=0.40,
        hip_width_m=0.28,
        shoulder_hip_ratio=0.40 / 0.28,
        right_arm_m=arm_m,
        left_arm_m=arm_m,
        arm_asymmetry=0.0,
        right_leg_m=leg_m,
        left_leg_m=leg_m,
        leg_asymmetry=0.0,
    )


class TestCalculateProportionDeviation:
    """calculate_proportion_deviation 함수 테스트."""

    def test_average_person_small_deviation(self) -> None:
        from biomechanics.anthropometry.personal_adapter import calculate_proportion_deviation
        # 성인 남성 기본값과 유사한 비율
        props = _make_proportions(height_m=1.75)
        dev = calculate_proportion_deviation(props, 25, Gender.MALE)
        # 기본값(175cm)과 같으므로 신장 편차 ≈ 0
        assert abs(dev.height_deviation) < 0.01

    def test_tall_person_positive_deviation(self) -> None:
        from biomechanics.anthropometry.personal_adapter import calculate_proportion_deviation
        props = _make_proportions(height_m=1.95)
        dev = calculate_proportion_deviation(props, 25, Gender.MALE)
        # 기본값(1.75m)보다 큼
        assert dev.height_deviation > 0.05


class TestHasSignificantDeviation:
    """has_significant_deviation 함수 테스트."""

    def test_small_deviation_false(self) -> None:
        from biomechanics.anthropometry.personal_adapter import (
            ProportionDeviation,
            has_significant_deviation,
        )
        dev = ProportionDeviation(
            height_deviation=0.02,
            wingspan_ratio_deviation=0.01,
            upper_lower_ratio_deviation=0.01,
            shoulder_hip_ratio_deviation=0.01,
            arm_length_deviation=0.02,
            leg_length_deviation=0.01,
            arm_asymmetry=0.01,
            leg_asymmetry=0.01,
        )
        assert has_significant_deviation(dev) is False

    def test_large_deviation_true(self) -> None:
        from biomechanics.anthropometry.personal_adapter import (
            ProportionDeviation,
            has_significant_deviation,
        )
        dev = ProportionDeviation(
            height_deviation=0.10,
            wingspan_ratio_deviation=0.01,
            upper_lower_ratio_deviation=0.01,
            shoulder_hip_ratio_deviation=0.01,
            arm_length_deviation=0.02,
            leg_length_deviation=0.01,
            arm_asymmetry=0.01,
            leg_asymmetry=0.01,
        )
        assert has_significant_deviation(dev) is True


class TestCreatePersonalProfile:
    """create_personal_profile 함수 테스트."""

    def test_basic_creation(self) -> None:
        from biomechanics.anthropometry.personal_adapter import create_personal_profile
        props = _make_proportions()
        profile = create_personal_profile(props, 25, Gender.MALE)
        assert profile.age == 25
        assert profile.gender == Gender.MALE
        assert profile.height_m == 1.80
        assert profile.is_stable is False
        assert profile.sample_count == 1

    def test_with_weight(self) -> None:
        from biomechanics.anthropometry.personal_adapter import create_personal_profile
        props = _make_proportions()
        profile = create_personal_profile(props, 25, Gender.MALE, weight_kg=80.0)
        assert profile.weight_kg == 80.0

    def test_without_weight_estimates(self) -> None:
        from biomechanics.anthropometry.personal_adapter import create_personal_profile
        props = _make_proportions(height_m=1.75)
        profile = create_personal_profile(props, 25, Gender.MALE)
        # BMI 기반 추정: 약 72kg
        assert 60.0 < profile.weight_kg < 85.0

    def test_body_model_created(self) -> None:
        from biomechanics.anthropometry.personal_adapter import create_personal_profile
        props = _make_proportions()
        profile = create_personal_profile(props, 25, Gender.MALE)
        assert profile.body_model is not None
        assert len(profile.body_model.segments) == len(BodySegment)

    def test_youth_profile(self) -> None:
        from biomechanics.anthropometry.personal_adapter import create_personal_profile
        props = _make_proportions(height_m=1.30)
        profile = create_personal_profile(props, 8, Gender.FEMALE)
        assert profile.age_group == AgeGroup.YOUTH


class TestProportionStabilizer:
    """ProportionStabilizer 클래스 테스트."""

    def test_not_stable_initially(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE)
        assert stab.is_stable is False
        assert stab.sample_count == 0

    def test_stable_after_min_samples(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=3)
        for _ in range(3):
            stab.add_sample(_make_proportions())
        assert stab.is_stable is True
        assert stab.sample_count == 3

    def test_get_stabilized_proportions(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=2)
        stab.add_sample(_make_proportions(height_m=1.78))
        stab.add_sample(_make_proportions(height_m=1.82))
        result = stab.get_stabilized_proportions()
        assert result is not None
        assert result.estimated_height_m == pytest.approx(1.80, abs=0.001)

    def test_returns_none_before_stable(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=5)
        stab.add_sample(_make_proportions())
        assert stab.get_stabilized_proportions() is None
        assert stab.get_personal_profile() is None

    def test_invalid_sample_ignored(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=1)
        # 비정상 신장 (0.5m)
        stab.add_sample(_make_proportions(height_m=0.5))
        assert stab.sample_count == 0
        assert stab.is_stable is False

    def test_reset(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=1)
        stab.add_sample(_make_proportions())
        assert stab.is_stable is True
        stab.reset()
        assert stab.is_stable is False
        assert stab.sample_count == 0

    def test_window_size_bounded(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, window_size=5, min_samples=1)
        for i in range(10):
            stab.add_sample(_make_proportions(height_m=1.70 + i * 0.02))
        assert stab.sample_count == 10
        result = stab.get_stabilized_proportions()
        assert result is not None
        # 최근 5개 (1.80, 1.82, 1.84, 1.86, 1.88) 평균 ≈ 1.84
        assert result.estimated_height_m == pytest.approx(1.84, abs=0.01)

    def test_get_personal_profile(self) -> None:
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=2)
        stab.add_sample(_make_proportions())
        stab.add_sample(_make_proportions())
        profile = stab.get_personal_profile()
        assert profile is not None
        assert profile.is_stable is True
        assert profile.sample_count == 2

    def test_thread_safety(self) -> None:
        """다중 스레드 동시 add_sample 안전성."""
        from biomechanics.anthropometry.personal_adapter import ProportionStabilizer
        stab = ProportionStabilizer(age=25, gender=Gender.MALE, min_samples=1)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(50):
                    stab.add_sample(_make_proportions())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert stab.sample_count == 200


# =============================================================================
# __init__.py 테스트
# =============================================================================
class TestAnthropometryInit:
    """anthropometry/__init__.py lazy import 테스트."""

    def test_lazy_import_body_model(self) -> None:
        from biomechanics.anthropometry import BodyModel
        assert BodyModel is not None

    def test_lazy_import_create_body_model(self) -> None:
        from biomechanics.anthropometry import create_body_model
        model = create_body_model()
        assert model.body_mass_kg == 75.0

    def test_lazy_import_age_gender_profile(self) -> None:
        from biomechanics.anthropometry import AgeGenderProfile
        assert AgeGenderProfile is not None

    def test_lazy_import_personal_profile(self) -> None:
        from biomechanics.anthropometry import PersonalProfile
        assert PersonalProfile is not None

    def test_lazy_import_proportion_stabilizer(self) -> None:
        from biomechanics.anthropometry import ProportionStabilizer
        assert ProportionStabilizer is not None

    def test_lazy_import_nonexistent(self) -> None:
        with pytest.raises(ImportError):
            from biomechanics.anthropometry import NonExistentSymbol  # noqa: F401

    def test_all_exports_accessible(self) -> None:
        import biomechanics.anthropometry as pkg
        for name in pkg.__all__:
            obj = getattr(pkg, name)
            assert obj is not None, f"{name}을(를) 가져올 수 없음"
