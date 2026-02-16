# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/shared/constants/unit
파일: test_biomechanics_constants.py
설명: biomechanics_constants.py 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-15

테스트 범위:
    [A] Enum 완전성 - BodySegment(10), MotionPhase(4), MovementIntensity(6), StanceType(8)
    [B] Enum str 상속 - 모든 열거형이 str을 상속
    [C] Enum 고유성 - 중복 값 없음
    [D] Enum 다국어 - get_name() 5개 언어 전수 검증
    [E] BodySegment.is_bilateral - 양측성 세그먼트 확인
    [F] BodySegment.mass_ratio_male/female 프로퍼티
    [G] 인체측정 모델 커버리지 - 모든 딕셔너리가 10개 세그먼트 보유
    [H] 질량비 과학적 검증 - 남/여 합산 ~1.0 (양측성 ×2)
    [I] 길이비 검증 - 모두 양수, 합 합리적
    [J] 무게중심 근위비 - 모두 0.0~1.0 범위
    [K] 회전 반경비 - 모두 양수 & < 1.0
    [L] JOINT_ROM_NORMAL - 모두 튜플, min <= max, 비음수
    [M] 농구 동작 각도 딕셔너리 - 4종 구조 검증
    [N] 속도 임계치 - 단조 증가, 성인 남성 > 성인 여성
    [O] 연령/성별 속도 계수 - 합리적 범위
    [P] 가속도 상수 - 적절한 순서 및 양수
    [Q] 각속도 범위 - min < max, 양수
    [R] 균형/안정성 상수 - 합리적 양수
    [S] 동역학 힘/충격 상수 - 적절한 순서 및 양수
    [T] 에너지 소비율 - 강도 증가에 따라 단조 증가
    [U] 연령대별 보정 계수 - 합리적 값
    [V] 유틸리티 함수 - get_segment_mass_ratio, get_segment_com_proximal,
                        get_velocity_thresholds, get_adjusted_angle_range
    [W] __all__ 완전성
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants.biomechanics_constants import (
    # 열거형
    BodySegment,
    MotionPhase,
    MovementIntensity,
    StanceType,
    # 인체측정 모델: 질량비
    SEGMENT_MASS_RATIO_MALE,
    SEGMENT_MASS_RATIO_FEMALE,
    # 인체측정 모델: 길이비
    SEGMENT_LENGTH_RATIO,
    # 인체측정 모델: 무게중심 근위 비율
    SEGMENT_COM_PROXIMAL_MALE,
    SEGMENT_COM_PROXIMAL_FEMALE,
    # 인체측정 모델: 회전 반경비
    SEGMENT_GYRATION_RADIUS_MALE,
    SEGMENT_GYRATION_RADIUS_FEMALE,
    # 관절 가동 범위
    JOINT_ROM_NORMAL,
    # 농구 동작 각도
    SHOOTING_OPTIMAL_ANGLES,
    DEFENSIVE_STANCE_ANGLES,
    DRIBBLING_STANCE_ANGLES,
    JUMP_LANDING_ANGLES,
    # 속도 임계치
    VELOCITY_THRESHOLDS_ADULT_MALE,
    VELOCITY_THRESHOLDS_ADULT_FEMALE,
    AGE_VELOCITY_FACTOR,
    GENDER_VELOCITY_FACTOR,
    # 가속도 상수
    ACCELERATION_NORMAL_MIN,
    ACCELERATION_NORMAL_MAX,
    ACCELERATION_QUICK_MIN,
    ACCELERATION_QUICK_MAX,
    ACCELERATION_EXPLOSIVE_THRESHOLD,
    DECELERATION_HARD_STOP_THRESHOLD,
    # 각속도 범위
    SHOOTING_ELBOW_ANGULAR_VELOCITY,
    SHOOTING_WRIST_ANGULAR_VELOCITY,
    SHOOTING_HIP_ROTATION_VELOCITY,
    PASSING_ARM_ANGULAR_VELOCITY,
    # 균형/안정성
    COP_SWAY_STABLE_THRESHOLD_CM,
    COP_SWAY_UNSTABLE_THRESHOLD_CM,
    STABILIZATION_TIME_GOOD_S,
    STABILIZATION_TIME_ACCEPTABLE_S,
    STABILIZATION_TIME_POOR_S,
    BASE_OF_SUPPORT_MIN_RATIO,
    BASE_OF_SUPPORT_OPTIMAL_RATIO,
    BASE_OF_SUPPORT_MAX_RATIO,
    COM_HEIGHT_CHANGE_JUMP_THRESHOLD,
    COM_HEIGHT_CHANGE_LANDING_THRESHOLD,
    # 동역학
    VERTICAL_GRF_WALKING_BW,
    VERTICAL_GRF_RUNNING_BW,
    VERTICAL_GRF_JUMP_LANDING_BW,
    VERTICAL_GRF_MAX_SAFE_BW,
    LANDING_IMPACT_ABSORPTION_GOOD_S,
    LANDING_IMPACT_ABSORPTION_POOR_S,
    CONTACT_FORCE_LIGHT_BW,
    CONTACT_FORCE_MODERATE_BW,
    CONTACT_FORCE_HEAVY_BW,
    CONTACT_FORCE_EXCESSIVE_BW,
    # 에너지 소비
    ENERGY_RATE_STATIONARY,
    ENERGY_RATE_WALKING,
    ENERGY_RATE_JOGGING,
    ENERGY_RATE_RUNNING,
    ENERGY_RATE_SPRINTING,
    ENERGY_RATE_BASKETBALL_GAME,
    # 연령대별 보정 계수
    AGE_TRUNK_MASS_FACTOR,
    AGE_LIMB_LENGTH_FACTOR,
    AGE_ANGLE_TOLERANCE,
    # 유틸리티 함수
    get_segment_mass_ratio,
    get_segment_com_proximal,
    get_velocity_thresholds,
    get_adjusted_angle_range,
)

from shared.constants.localization import SupportedLanguage
from shared.constants.player_constants import AgeGroup, Gender

# biomechanics_constants 모듈 자체 참조 (for __all__ 검증)
import shared.constants.biomechanics_constants as _bmc_module


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과"""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# [A] Enum 완전성 테스트
# =============================================================================
def test_body_segment_completeness(result: TestResult) -> None:
    """BodySegment Enum 10개 멤버 완전성 테스트."""
    try:
        expected = {
            "HEAD", "NECK", "TRUNK_UPPER", "TRUNK_LOWER",
            "UPPER_ARM", "FOREARM", "HAND",
            "THIGH", "SHANK", "FOOT",
        }
        actual = {m.name for m in BodySegment}
        assert actual == expected, f"멤버 불일치: 누락={expected - actual}, 초과={actual - expected}"
        assert len(list(BodySegment)) == 10, f"멤버 수 불일치: {len(list(BodySegment))} != 10"
        result.ok("BodySegment 완전성 (10개 멤버)")
    except AssertionError as e:
        result.fail("BodySegment 완전성 (10개 멤버)", str(e))


def test_motion_phase_completeness(result: TestResult) -> None:
    """MotionPhase Enum 4개 멤버 완전성 테스트."""
    try:
        expected = {"PREPARATION", "EXECUTION", "FOLLOW_THROUGH", "RECOVERY"}
        actual = {m.name for m in MotionPhase}
        assert actual == expected, f"멤버 불일치: 누락={expected - actual}, 초과={actual - expected}"
        assert len(list(MotionPhase)) == 4, f"멤버 수 불일치: {len(list(MotionPhase))} != 4"
        result.ok("MotionPhase 완전성 (4개 멤버)")
    except AssertionError as e:
        result.fail("MotionPhase 완전성 (4개 멤버)", str(e))


def test_movement_intensity_completeness(result: TestResult) -> None:
    """MovementIntensity Enum 6개 멤버 완전성 테스트."""
    try:
        expected = {
            "STATIONARY", "WALKING", "JOGGING",
            "RUNNING", "SPRINTING", "MAX_EFFORT",
        }
        actual = {m.name for m in MovementIntensity}
        assert actual == expected, f"멤버 불일치: 누락={expected - actual}, 초과={actual - expected}"
        assert len(list(MovementIntensity)) == 6, f"멤버 수 불일치: {len(list(MovementIntensity))} != 6"
        result.ok("MovementIntensity 완전성 (6개 멤버)")
    except AssertionError as e:
        result.fail("MovementIntensity 완전성 (6개 멤버)", str(e))


def test_stance_type_completeness(result: TestResult) -> None:
    """StanceType Enum 8개 멤버 완전성 테스트."""
    try:
        expected = {
            "ATHLETIC_READY", "TRIPLE_THREAT", "DEFENSIVE_STANCE",
            "SHOOTING_SET", "POST_UP", "BOXING_OUT",
            "SPRINT_LEAN", "JUMP_READY",
        }
        actual = {m.name for m in StanceType}
        assert actual == expected, f"멤버 불일치: 누락={expected - actual}, 초과={actual - expected}"
        assert len(list(StanceType)) == 8, f"멤버 수 불일치: {len(list(StanceType))} != 8"
        result.ok("StanceType 완전성 (8개 멤버)")
    except AssertionError as e:
        result.fail("StanceType 완전성 (8개 멤버)", str(e))


# =============================================================================
# [B] Enum str 상속 테스트
# =============================================================================
def test_body_segment_str_inheritance(result: TestResult) -> None:
    """BodySegment가 str을 상속하는지 테스트."""
    try:
        assert issubclass(BodySegment, str), "BodySegment가 str을 상속하지 않음"
        # 인스턴스도 str
        for seg in BodySegment:
            assert isinstance(seg, str), f"{seg.name}이 str 인스턴스가 아님"
            assert str(seg) == seg.value, f"{seg.name}: str() = {str(seg)} != value = {seg.value}"
        result.ok("BodySegment str 상속")
    except AssertionError as e:
        result.fail("BodySegment str 상속", str(e))


def test_motion_phase_str_inheritance(result: TestResult) -> None:
    """MotionPhase가 str을 상속하는지 테스트."""
    try:
        assert issubclass(MotionPhase, str), "MotionPhase가 str을 상속하지 않음"
        for phase in MotionPhase:
            assert isinstance(phase, str), f"{phase.name}이 str 인스턴스가 아님"
            assert str(phase) == phase.value, f"{phase.name}: str() != value"
        result.ok("MotionPhase str 상속")
    except AssertionError as e:
        result.fail("MotionPhase str 상속", str(e))


def test_movement_intensity_str_inheritance(result: TestResult) -> None:
    """MovementIntensity가 str을 상속하는지 테스트."""
    try:
        assert issubclass(MovementIntensity, str), "MovementIntensity가 str을 상속하지 않음"
        for intensity in MovementIntensity:
            assert isinstance(intensity, str), f"{intensity.name}이 str 인스턴스가 아님"
            assert str(intensity) == intensity.value, f"{intensity.name}: str() != value"
        result.ok("MovementIntensity str 상속")
    except AssertionError as e:
        result.fail("MovementIntensity str 상속", str(e))


def test_stance_type_str_inheritance(result: TestResult) -> None:
    """StanceType이 str을 상속하는지 테스트."""
    try:
        assert issubclass(StanceType, str), "StanceType이 str을 상속하지 않음"
        for stance in StanceType:
            assert isinstance(stance, str), f"{stance.name}이 str 인스턴스가 아님"
            assert str(stance) == stance.value, f"{stance.name}: str() != value"
        result.ok("StanceType str 상속")
    except AssertionError as e:
        result.fail("StanceType str 상속", str(e))


# =============================================================================
# [C] Enum 고유성 테스트
# =============================================================================
def test_body_segment_uniqueness(result: TestResult) -> None:
    """BodySegment 값 고유성 테스트."""
    try:
        values = [m.value for m in BodySegment]
        assert len(values) == len(set(values)), f"중복 값 존재: {[v for v in values if values.count(v) > 1]}"
        result.ok("BodySegment 값 고유성")
    except AssertionError as e:
        result.fail("BodySegment 값 고유성", str(e))


def test_motion_phase_uniqueness(result: TestResult) -> None:
    """MotionPhase 값 고유성 테스트."""
    try:
        values = [m.value for m in MotionPhase]
        assert len(values) == len(set(values)), "중복 값 존재"
        result.ok("MotionPhase 값 고유성")
    except AssertionError as e:
        result.fail("MotionPhase 값 고유성", str(e))


def test_movement_intensity_uniqueness(result: TestResult) -> None:
    """MovementIntensity 값 고유성 테스트."""
    try:
        values = [m.value for m in MovementIntensity]
        assert len(values) == len(set(values)), "중복 값 존재"
        result.ok("MovementIntensity 값 고유성")
    except AssertionError as e:
        result.fail("MovementIntensity 값 고유성", str(e))


def test_stance_type_uniqueness(result: TestResult) -> None:
    """StanceType 값 고유성 테스트."""
    try:
        values = [m.value for m in StanceType]
        assert len(values) == len(set(values)), "중복 값 존재"
        result.ok("StanceType 값 고유성")
    except AssertionError as e:
        result.fail("StanceType 값 고유성", str(e))


# =============================================================================
# [D] Enum 다국어(i18n) 테스트
# =============================================================================
_ALL_LANGS = list(SupportedLanguage)


def test_body_segment_i18n(result: TestResult) -> None:
    """BodySegment get_name() 5개 언어 전수 테스트."""
    try:
        for seg in BodySegment:
            for lang in _ALL_LANGS:
                name = seg.get_name(lang)
                assert isinstance(name, str), f"{seg.name}/{lang.value}: 반환 타입 오류"
                assert len(name) > 0, f"{seg.name}/{lang.value}: 빈 문자열"
        result.ok("BodySegment 다국어 (5개 언어 × 10개 세그먼트)")
    except AssertionError as e:
        result.fail("BodySegment 다국어", str(e))


def test_motion_phase_i18n(result: TestResult) -> None:
    """MotionPhase get_name() 5개 언어 전수 테스트."""
    try:
        for phase in MotionPhase:
            for lang in _ALL_LANGS:
                name = phase.get_name(lang)
                assert isinstance(name, str), f"{phase.name}/{lang.value}: 반환 타입 오류"
                assert len(name) > 0, f"{phase.name}/{lang.value}: 빈 문자열"
        result.ok("MotionPhase 다국어 (5개 언어 × 4개 페이즈)")
    except AssertionError as e:
        result.fail("MotionPhase 다국어", str(e))


def test_movement_intensity_i18n(result: TestResult) -> None:
    """MovementIntensity get_name() 5개 언어 전수 테스트."""
    try:
        for intensity in MovementIntensity:
            for lang in _ALL_LANGS:
                name = intensity.get_name(lang)
                assert isinstance(name, str), f"{intensity.name}/{lang.value}: 반환 타입 오류"
                assert len(name) > 0, f"{intensity.name}/{lang.value}: 빈 문자열"
        result.ok("MovementIntensity 다국어 (5개 언어 × 6개 강도)")
    except AssertionError as e:
        result.fail("MovementIntensity 다국어", str(e))


def test_stance_type_i18n(result: TestResult) -> None:
    """StanceType get_name() 5개 언어 전수 테스트."""
    try:
        for stance in StanceType:
            for lang in _ALL_LANGS:
                name = stance.get_name(lang)
                assert isinstance(name, str), f"{stance.name}/{lang.value}: 반환 타입 오류"
                assert len(name) > 0, f"{stance.name}/{lang.value}: 빈 문자열"
        result.ok("StanceType 다국어 (5개 언어 × 8개 스탠스)")
    except AssertionError as e:
        result.fail("StanceType 다국어", str(e))


# =============================================================================
# [E] BodySegment.is_bilateral 테스트
# =============================================================================
def test_is_bilateral_property(result: TestResult) -> None:
    """BodySegment.is_bilateral 양측성 세그먼트 검증."""
    try:
        # 양측성(좌/우 대칭) 세그먼트: 상완, 전완, 손, 대퇴, 하퇴, 발
        expected_bilateral = {
            BodySegment.UPPER_ARM,
            BodySegment.FOREARM,
            BodySegment.HAND,
            BodySegment.THIGH,
            BodySegment.SHANK,
            BodySegment.FOOT,
        }
        # 비양측성: 머리, 목, 상부체간, 하부체간
        expected_non_bilateral = {
            BodySegment.HEAD,
            BodySegment.NECK,
            BodySegment.TRUNK_UPPER,
            BodySegment.TRUNK_LOWER,
        }

        for seg in expected_bilateral:
            assert seg.is_bilateral is True, f"{seg.name}: is_bilateral이 True여야 함"

        for seg in expected_non_bilateral:
            assert seg.is_bilateral is False, f"{seg.name}: is_bilateral이 False여야 함"

        # 양측성 세그먼트 수 = 6
        bilateral_count = sum(1 for s in BodySegment if s.is_bilateral)
        assert bilateral_count == 6, f"양측성 세그먼트 수 불일치: {bilateral_count} != 6"

        result.ok("BodySegment.is_bilateral 양측성 세그먼트")
    except AssertionError as e:
        result.fail("BodySegment.is_bilateral 양측성 세그먼트", str(e))


# =============================================================================
# [F] BodySegment.mass_ratio_male/female 프로퍼티 테스트
# =============================================================================
def test_mass_ratio_properties(result: TestResult) -> None:
    """BodySegment.mass_ratio_male / mass_ratio_female 프로퍼티 테스트."""
    try:
        for seg in BodySegment:
            male_ratio = seg.mass_ratio_male
            female_ratio = seg.mass_ratio_female
            # 양수이고 1.0 이하
            assert 0.0 < male_ratio < 1.0, f"{seg.name} 남성 질량비 범위 오류: {male_ratio}"
            assert 0.0 < female_ratio < 1.0, f"{seg.name} 여성 질량비 범위 오류: {female_ratio}"
            # 딕셔너리 값과 일치
            assert male_ratio == SEGMENT_MASS_RATIO_MALE[seg], \
                f"{seg.name} 남성 프로퍼티-딕셔너리 불일치"
            assert female_ratio == SEGMENT_MASS_RATIO_FEMALE[seg], \
                f"{seg.name} 여성 프로퍼티-딕셔너리 불일치"
        result.ok("BodySegment.mass_ratio_male/female 프로퍼티")
    except AssertionError as e:
        result.fail("BodySegment.mass_ratio_male/female 프로퍼티", str(e))


# =============================================================================
# [G] 인체측정 모델 커버리지 테스트 (모든 딕셔너리 × 10 세그먼트)
# =============================================================================
def test_anthropometric_model_coverage(result: TestResult) -> None:
    """모든 인체측정 딕셔너리가 10개 세그먼트를 모두 포함하는지 테스트."""
    try:
        all_segments = set(BodySegment)
        dicts_to_check = {
            "SEGMENT_MASS_RATIO_MALE": SEGMENT_MASS_RATIO_MALE,
            "SEGMENT_MASS_RATIO_FEMALE": SEGMENT_MASS_RATIO_FEMALE,
            "SEGMENT_LENGTH_RATIO": SEGMENT_LENGTH_RATIO,
            "SEGMENT_COM_PROXIMAL_MALE": SEGMENT_COM_PROXIMAL_MALE,
            "SEGMENT_COM_PROXIMAL_FEMALE": SEGMENT_COM_PROXIMAL_FEMALE,
            "SEGMENT_GYRATION_RADIUS_MALE": SEGMENT_GYRATION_RADIUS_MALE,
            "SEGMENT_GYRATION_RADIUS_FEMALE": SEGMENT_GYRATION_RADIUS_FEMALE,
        }

        for name, d in dicts_to_check.items():
            keys = set(d.keys())
            assert keys == all_segments, f"{name}: 키 불일치 — 누락={all_segments - keys}, 초과={keys - all_segments}"
            assert len(d) == 10, f"{name}: 항목 수 불일치: {len(d)} != 10"

        result.ok("인체측정 모델 커버리지 (7개 딕셔너리 × 10 세그먼트)")
    except AssertionError as e:
        result.fail("인체측정 모델 커버리지", str(e))


# =============================================================================
# [H] 질량비 과학적 검증 (합산 ~1.0, 양측성 ×2)
# =============================================================================
def test_mass_ratio_sum_male(result: TestResult) -> None:
    """남성 세그먼트 질량비 합산 검증 (양측성 ×2 반영 시 ~1.0)."""
    try:
        total = 0.0
        for seg in BodySegment:
            ratio = SEGMENT_MASS_RATIO_MALE[seg]
            if seg.is_bilateral:
                total += ratio * 2.0  # 양쪽
            else:
                total += ratio
        # de Leva 1996 모델: 합산이 1.0에 매우 가까움 (±0.05 허용)
        assert abs(total - 1.0) < 0.05, f"남성 질량비 합: {total:.4f} (1.0과 차이: {abs(total-1.0):.4f})"
        result.ok(f"남성 질량비 합산 = {total:.4f} (~1.0)")
    except AssertionError as e:
        result.fail("남성 질량비 합산 ~1.0", str(e))


def test_mass_ratio_sum_female(result: TestResult) -> None:
    """여성 세그먼트 질량비 합산 검증 (양측성 ×2 반영 시 ~1.0)."""
    try:
        total = 0.0
        for seg in BodySegment:
            ratio = SEGMENT_MASS_RATIO_FEMALE[seg]
            if seg.is_bilateral:
                total += ratio * 2.0
            else:
                total += ratio
        assert abs(total - 1.0) < 0.05, f"여성 질량비 합: {total:.4f} (1.0과 차이: {abs(total-1.0):.4f})"
        result.ok(f"여성 질량비 합산 = {total:.4f} (~1.0)")
    except AssertionError as e:
        result.fail("여성 질량비 합산 ~1.0", str(e))


# =============================================================================
# [I] 길이비 검증
# =============================================================================
def test_length_ratio_positive(result: TestResult) -> None:
    """세그먼트 길이비가 모두 양수이고 합이 합리적인지 테스트."""
    try:
        for seg, ratio in SEGMENT_LENGTH_RATIO.items():
            assert ratio > 0.0, f"{seg.name} 길이비 <= 0: {ratio}"
            assert ratio < 1.0, f"{seg.name} 길이비 >= 1.0: {ratio}"

        # 전체 합산 (양측성 세그먼트는 한 쪽만 포함이므로 단순 합)
        # 인체에서 각 세그먼트 길이 합은 ~1.3 정도 (사지 중복 포함)
        total = sum(SEGMENT_LENGTH_RATIO.values())
        assert 1.0 < total < 2.0, f"길이비 합 범위 이탈: {total:.4f}"
        result.ok(f"세그먼트 길이비 양수 & 합 = {total:.4f}")
    except AssertionError as e:
        result.fail("세그먼트 길이비 양수 & 합 합리적", str(e))


# =============================================================================
# [J] 무게중심 근위비 검증 (0.0~1.0)
# =============================================================================
def test_com_proximal_range(result: TestResult) -> None:
    """무게중심 근위 비율이 모두 0.0~1.0 범위인지 테스트."""
    try:
        for seg in BodySegment:
            male_val = SEGMENT_COM_PROXIMAL_MALE[seg]
            female_val = SEGMENT_COM_PROXIMAL_FEMALE[seg]
            assert 0.0 < male_val < 1.0, f"{seg.name} 남성 COM 근위비 범위 오류: {male_val}"
            assert 0.0 < female_val < 1.0, f"{seg.name} 여성 COM 근위비 범위 오류: {female_val}"
        result.ok("무게중심 근위비 (0.0~1.0 범위)")
    except AssertionError as e:
        result.fail("무게중심 근위비 (0.0~1.0)", str(e))


# =============================================================================
# [K] 회전 반경비 검증 (양수, < 1.0)
# =============================================================================
def test_gyration_radius_range(result: TestResult) -> None:
    """회전 반경비가 모두 양수이고 1.0 미만인지 테스트."""
    try:
        for seg in BodySegment:
            male_val = SEGMENT_GYRATION_RADIUS_MALE[seg]
            female_val = SEGMENT_GYRATION_RADIUS_FEMALE[seg]
            assert 0.0 < male_val < 1.0, f"{seg.name} 남성 회전반경비 범위 오류: {male_val}"
            assert 0.0 < female_val < 1.0, f"{seg.name} 여성 회전반경비 범위 오류: {female_val}"
        result.ok("회전 반경비 (양수 & < 1.0)")
    except AssertionError as e:
        result.fail("회전 반경비 (양수 & < 1.0)", str(e))


# =============================================================================
# [L] JOINT_ROM_NORMAL 검증
# =============================================================================
def test_joint_rom_normal(result: TestResult) -> None:
    """JOINT_ROM_NORMAL: 모든 항목이 튜플, min <= max, 비음수인지 테스트."""
    try:
        assert len(JOINT_ROM_NORMAL) > 0, "JOINT_ROM_NORMAL이 비어 있음"
        for joint, rom in JOINT_ROM_NORMAL.items():
            assert isinstance(rom, tuple), f"{joint}: 튜플이 아님 — {type(rom)}"
            assert len(rom) == 2, f"{joint}: 길이 != 2 — {len(rom)}"
            min_val, max_val = rom
            assert isinstance(min_val, (int, float)), f"{joint} min: 숫자 아님"
            assert isinstance(max_val, (int, float)), f"{joint} max: 숫자 아님"
            assert min_val >= 0.0, f"{joint} min < 0: {min_val}"
            assert max_val >= 0.0, f"{joint} max < 0: {max_val}"
            assert min_val <= max_val, f"{joint}: min({min_val}) > max({max_val})"
        result.ok(f"JOINT_ROM_NORMAL ({len(JOINT_ROM_NORMAL)}개 항목 구조 검증)")
    except AssertionError as e:
        result.fail("JOINT_ROM_NORMAL 구조 검증", str(e))


# =============================================================================
# [M] 농구 동작 각도 딕셔너리 구조 검증
# =============================================================================
def test_basketball_angle_dicts(result: TestResult) -> None:
    """4종 농구 동작 각도 딕셔너리 구조 검증."""
    try:
        angle_dicts = {
            "SHOOTING_OPTIMAL_ANGLES": SHOOTING_OPTIMAL_ANGLES,
            "DEFENSIVE_STANCE_ANGLES": DEFENSIVE_STANCE_ANGLES,
            "DRIBBLING_STANCE_ANGLES": DRIBBLING_STANCE_ANGLES,
            "JUMP_LANDING_ANGLES": JUMP_LANDING_ANGLES,
        }
        for name, d in angle_dicts.items():
            assert len(d) > 0, f"{name}이 비어 있음"
            for key, val in d.items():
                assert isinstance(key, str), f"{name}[{key}]: 키가 문자열 아님"
                assert isinstance(val, tuple), f"{name}[{key}]: 값이 튜플 아님 — {type(val)}"
                assert len(val) == 2, f"{name}[{key}]: 튜플 길이 != 2"
                min_v, max_v = val
                assert isinstance(min_v, (int, float)), f"{name}[{key}] min: 숫자 아님"
                assert isinstance(max_v, (int, float)), f"{name}[{key}] max: 숫자 아님"
                assert min_v <= max_v, f"{name}[{key}]: min({min_v}) > max({max_v})"
                assert min_v >= 0.0, f"{name}[{key}]: min < 0"

        # 항목 수 확인
        assert len(SHOOTING_OPTIMAL_ANGLES) >= 10, \
            f"SHOOTING_OPTIMAL_ANGLES 항목 부족: {len(SHOOTING_OPTIMAL_ANGLES)}"
        assert len(DEFENSIVE_STANCE_ANGLES) >= 4, \
            f"DEFENSIVE_STANCE_ANGLES 항목 부족: {len(DEFENSIVE_STANCE_ANGLES)}"
        assert len(DRIBBLING_STANCE_ANGLES) >= 5, \
            f"DRIBBLING_STANCE_ANGLES 항목 부족: {len(DRIBBLING_STANCE_ANGLES)}"
        assert len(JUMP_LANDING_ANGLES) >= 6, \
            f"JUMP_LANDING_ANGLES 항목 부족: {len(JUMP_LANDING_ANGLES)}"

        result.ok("농구 동작 각도 딕셔너리 (4종 구조 검증)")
    except AssertionError as e:
        result.fail("농구 동작 각도 딕셔너리 구조 검증", str(e))


# =============================================================================
# [N] 속도 임계치 검증 (단조 증가, 남성 > 여성)
# =============================================================================
def test_velocity_thresholds_monotonic(result: TestResult) -> None:
    """속도 임계치 단조 증가 검증."""
    try:
        intensity_order = [
            MovementIntensity.STATIONARY,
            MovementIntensity.WALKING,
            MovementIntensity.JOGGING,
            MovementIntensity.RUNNING,
            MovementIntensity.SPRINTING,
            MovementIntensity.MAX_EFFORT,
        ]

        # 남성: 각 단계 상한이 다음 단계 하한과 동일 (연속)
        for i in range(len(intensity_order) - 1):
            curr = VELOCITY_THRESHOLDS_ADULT_MALE[intensity_order[i]]
            nxt = VELOCITY_THRESHOLDS_ADULT_MALE[intensity_order[i + 1]]
            assert curr[1] <= nxt[1], \
                f"남성 단조증가 위반: {intensity_order[i].name} 상한 {curr[1]} > {intensity_order[i+1].name} 상한 {nxt[1]}"
            assert curr[0] < nxt[0], \
                f"남성 단조증가 위반: {intensity_order[i].name} 하한 {curr[0]} >= {intensity_order[i+1].name} 하한 {nxt[0]}"

        # 여성도 동일 단조 증가
        for i in range(len(intensity_order) - 1):
            curr = VELOCITY_THRESHOLDS_ADULT_FEMALE[intensity_order[i]]
            nxt = VELOCITY_THRESHOLDS_ADULT_FEMALE[intensity_order[i + 1]]
            assert curr[1] <= nxt[1], \
                f"여성 단조증가 위반: {intensity_order[i].name}"
            assert curr[0] < nxt[0], \
                f"여성 단조증가 위반 (하한): {intensity_order[i].name}"

        result.ok("속도 임계치 단조 증가")
    except AssertionError as e:
        result.fail("속도 임계치 단조 증가", str(e))


def test_velocity_male_greater_than_female(result: TestResult) -> None:
    """성인 남성 속도 임계치 >= 성인 여성 검증."""
    try:
        for intensity in MovementIntensity:
            male = VELOCITY_THRESHOLDS_ADULT_MALE[intensity]
            female = VELOCITY_THRESHOLDS_ADULT_FEMALE[intensity]
            # 남성 상한 >= 여성 상한 (STATIONARY 하한은 동일)
            assert male[1] >= female[1], \
                f"{intensity.name}: 남성 상한({male[1]}) < 여성 상한({female[1]})"
        result.ok("속도 임계치: 성인 남성 >= 성인 여성")
    except AssertionError as e:
        result.fail("속도 임계치: 성인 남성 >= 성인 여성", str(e))


# =============================================================================
# [O] 연령/성별 속도 계수 검증
# =============================================================================
def test_age_gender_velocity_factors(result: TestResult) -> None:
    """연령/성별 속도 보정 계수의 합리적 범위 테스트."""
    try:
        # 모든 AgeGroup 커버리지
        for ag in AgeGroup:
            factor = AGE_VELOCITY_FACTOR[ag]
            assert 0.5 <= factor <= 1.2, f"AGE_VELOCITY_FACTOR[{ag.name}] 범위 이탈: {factor}"

        # ADULT = 1.0 기준
        assert AGE_VELOCITY_FACTOR[AgeGroup.ADULT] == 1.0, "성인 속도계수 != 1.0"

        # YOUTH < TEEN < ADULT
        assert AGE_VELOCITY_FACTOR[AgeGroup.YOUTH] < AGE_VELOCITY_FACTOR[AgeGroup.TEEN], \
            "유소년 >= 청소년 속도계수"
        assert AGE_VELOCITY_FACTOR[AgeGroup.TEEN] < AGE_VELOCITY_FACTOR[AgeGroup.ADULT], \
            "청소년 >= 성인 속도계수"

        # 성별 계수
        for g in Gender:
            factor = GENDER_VELOCITY_FACTOR[g]
            assert 0.5 <= factor <= 1.2, f"GENDER_VELOCITY_FACTOR[{g.name}] 범위 이탈: {factor}"

        assert GENDER_VELOCITY_FACTOR[Gender.MALE] == 1.0, "남성 속도계수 != 1.0"
        assert GENDER_VELOCITY_FACTOR[Gender.FEMALE] < GENDER_VELOCITY_FACTOR[Gender.MALE], \
            "여성 속도계수 >= 남성"

        result.ok("연령/성별 속도 계수 합리적 범위")
    except AssertionError as e:
        result.fail("연령/성별 속도 계수", str(e))


# =============================================================================
# [P] 가속도 상수 검증
# =============================================================================
def test_acceleration_constants(result: TestResult) -> None:
    """가속도 임계치 순서 및 양수 검증."""
    try:
        # 양수 확인
        assert ACCELERATION_NORMAL_MIN > 0, f"NORMAL_MIN <= 0: {ACCELERATION_NORMAL_MIN}"
        assert ACCELERATION_NORMAL_MAX > 0, f"NORMAL_MAX <= 0: {ACCELERATION_NORMAL_MAX}"
        assert ACCELERATION_QUICK_MIN > 0, f"QUICK_MIN <= 0: {ACCELERATION_QUICK_MIN}"
        assert ACCELERATION_QUICK_MAX > 0, f"QUICK_MAX <= 0: {ACCELERATION_QUICK_MAX}"
        assert ACCELERATION_EXPLOSIVE_THRESHOLD > 0, f"EXPLOSIVE <= 0"
        assert DECELERATION_HARD_STOP_THRESHOLD > 0, f"DECELERATION <= 0"

        # 순서: NORMAL_MIN < NORMAL_MAX <= QUICK_MIN < QUICK_MAX <= EXPLOSIVE
        assert ACCELERATION_NORMAL_MIN < ACCELERATION_NORMAL_MAX, \
            f"NORMAL: min({ACCELERATION_NORMAL_MIN}) >= max({ACCELERATION_NORMAL_MAX})"
        assert ACCELERATION_NORMAL_MAX <= ACCELERATION_QUICK_MIN, \
            f"NORMAL_MAX({ACCELERATION_NORMAL_MAX}) > QUICK_MIN({ACCELERATION_QUICK_MIN})"
        assert ACCELERATION_QUICK_MIN < ACCELERATION_QUICK_MAX, \
            f"QUICK: min({ACCELERATION_QUICK_MIN}) >= max({ACCELERATION_QUICK_MAX})"
        assert ACCELERATION_QUICK_MAX <= ACCELERATION_EXPLOSIVE_THRESHOLD, \
            f"QUICK_MAX({ACCELERATION_QUICK_MAX}) > EXPLOSIVE({ACCELERATION_EXPLOSIVE_THRESHOLD})"

        result.ok("가속도 상수 순서 및 양수")
    except AssertionError as e:
        result.fail("가속도 상수", str(e))


# =============================================================================
# [Q] 각속도 범위 검증
# =============================================================================
def test_angular_velocity_ranges(result: TestResult) -> None:
    """각속도 범위: min < max, 양수 검증."""
    try:
        av_dicts = {
            "SHOOTING_ELBOW": SHOOTING_ELBOW_ANGULAR_VELOCITY,
            "SHOOTING_WRIST": SHOOTING_WRIST_ANGULAR_VELOCITY,
            "SHOOTING_HIP_ROTATION": SHOOTING_HIP_ROTATION_VELOCITY,
            "PASSING_ARM": PASSING_ARM_ANGULAR_VELOCITY,
        }
        for name, (min_v, max_v) in av_dicts.items():
            assert min_v > 0, f"{name}: min <= 0 ({min_v})"
            assert max_v > 0, f"{name}: max <= 0 ({max_v})"
            assert min_v < max_v, f"{name}: min({min_v}) >= max({max_v})"

        result.ok("각속도 범위 (양수 & min < max)")
    except AssertionError as e:
        result.fail("각속도 범위", str(e))


# =============================================================================
# [R] 균형/안정성 상수 검증
# =============================================================================
def test_balance_stability_constants(result: TestResult) -> None:
    """균형/안정성 상수의 합리적 양수값 검증."""
    try:
        # COP 동요 임계치
        assert COP_SWAY_STABLE_THRESHOLD_CM > 0, f"COP stable <= 0"
        assert COP_SWAY_UNSTABLE_THRESHOLD_CM > COP_SWAY_STABLE_THRESHOLD_CM, \
            f"COP unstable({COP_SWAY_UNSTABLE_THRESHOLD_CM}) <= stable({COP_SWAY_STABLE_THRESHOLD_CM})"

        # 안정화 시간: GOOD < ACCEPTABLE < POOR
        assert STABILIZATION_TIME_GOOD_S > 0, "GOOD <= 0"
        assert STABILIZATION_TIME_GOOD_S < STABILIZATION_TIME_ACCEPTABLE_S, \
            f"GOOD({STABILIZATION_TIME_GOOD_S}) >= ACCEPTABLE({STABILIZATION_TIME_ACCEPTABLE_S})"
        assert STABILIZATION_TIME_ACCEPTABLE_S < STABILIZATION_TIME_POOR_S, \
            f"ACCEPTABLE({STABILIZATION_TIME_ACCEPTABLE_S}) >= POOR({STABILIZATION_TIME_POOR_S})"

        # 지지 기저면 비율: MIN < OPTIMAL < MAX
        assert BASE_OF_SUPPORT_MIN_RATIO > 0, "BOS MIN <= 0"
        assert BASE_OF_SUPPORT_MIN_RATIO < BASE_OF_SUPPORT_OPTIMAL_RATIO, \
            f"BOS MIN({BASE_OF_SUPPORT_MIN_RATIO}) >= OPTIMAL({BASE_OF_SUPPORT_OPTIMAL_RATIO})"
        assert BASE_OF_SUPPORT_OPTIMAL_RATIO < BASE_OF_SUPPORT_MAX_RATIO, \
            f"BOS OPTIMAL({BASE_OF_SUPPORT_OPTIMAL_RATIO}) >= MAX({BASE_OF_SUPPORT_MAX_RATIO})"

        # COM 높이 변화 임계치
        assert COM_HEIGHT_CHANGE_JUMP_THRESHOLD > 0, "COM JUMP <= 0"
        assert COM_HEIGHT_CHANGE_LANDING_THRESHOLD > 0, "COM LANDING <= 0"
        # 점프 임계치가 착지 임계치보다 큰 것이 논리적 (더 큰 변화 필요)
        assert COM_HEIGHT_CHANGE_JUMP_THRESHOLD >= COM_HEIGHT_CHANGE_LANDING_THRESHOLD, \
            f"COM JUMP({COM_HEIGHT_CHANGE_JUMP_THRESHOLD}) < LANDING({COM_HEIGHT_CHANGE_LANDING_THRESHOLD})"

        result.ok("균형/안정성 상수 합리적 양수값")
    except AssertionError as e:
        result.fail("균형/안정성 상수", str(e))


# =============================================================================
# [S] 동역학 힘/충격 상수 검증
# =============================================================================
def test_force_dynamics_constants(result: TestResult) -> None:
    """동역학 힘/충격 상수의 순서 및 양수 검증."""
    try:
        # 수직 지면반력: WALKING < RUNNING < JUMP_LANDING < MAX_SAFE
        assert VERTICAL_GRF_WALKING_BW > 0, "GRF WALKING <= 0"
        assert VERTICAL_GRF_WALKING_BW < VERTICAL_GRF_RUNNING_BW, \
            f"GRF WALKING({VERTICAL_GRF_WALKING_BW}) >= RUNNING({VERTICAL_GRF_RUNNING_BW})"
        assert VERTICAL_GRF_RUNNING_BW < VERTICAL_GRF_JUMP_LANDING_BW, \
            f"GRF RUNNING({VERTICAL_GRF_RUNNING_BW}) >= JUMP_LANDING({VERTICAL_GRF_JUMP_LANDING_BW})"
        assert VERTICAL_GRF_JUMP_LANDING_BW < VERTICAL_GRF_MAX_SAFE_BW, \
            f"GRF JUMP_LANDING({VERTICAL_GRF_JUMP_LANDING_BW}) >= MAX_SAFE({VERTICAL_GRF_MAX_SAFE_BW})"

        # 착지 충격 흡수 시간: GOOD > POOR (좋은 흡수 = 더 긴 시간)
        assert LANDING_IMPACT_ABSORPTION_GOOD_S > 0, "ABSORPTION GOOD <= 0"
        assert LANDING_IMPACT_ABSORPTION_POOR_S > 0, "ABSORPTION POOR <= 0"
        assert LANDING_IMPACT_ABSORPTION_GOOD_S > LANDING_IMPACT_ABSORPTION_POOR_S, \
            f"GOOD({LANDING_IMPACT_ABSORPTION_GOOD_S}) <= POOR({LANDING_IMPACT_ABSORPTION_POOR_S})"

        # 접촉 힘: LIGHT < MODERATE < HEAVY < EXCESSIVE
        assert CONTACT_FORCE_LIGHT_BW > 0, "CONTACT LIGHT <= 0"
        assert CONTACT_FORCE_LIGHT_BW < CONTACT_FORCE_MODERATE_BW, \
            f"CONTACT LIGHT({CONTACT_FORCE_LIGHT_BW}) >= MODERATE({CONTACT_FORCE_MODERATE_BW})"
        assert CONTACT_FORCE_MODERATE_BW < CONTACT_FORCE_HEAVY_BW, \
            f"CONTACT MODERATE({CONTACT_FORCE_MODERATE_BW}) >= HEAVY({CONTACT_FORCE_HEAVY_BW})"
        assert CONTACT_FORCE_HEAVY_BW < CONTACT_FORCE_EXCESSIVE_BW, \
            f"CONTACT HEAVY({CONTACT_FORCE_HEAVY_BW}) >= EXCESSIVE({CONTACT_FORCE_EXCESSIVE_BW})"

        result.ok("동역학 힘/충격 상수 순서 및 양수")
    except AssertionError as e:
        result.fail("동역학 힘/충격 상수", str(e))


# =============================================================================
# [T] 에너지 소비율 검증 (단조 증가)
# =============================================================================
def test_energy_rates_monotonic(result: TestResult) -> None:
    """에너지 소비율이 강도 증가에 따라 단조 증가하는지 테스트."""
    try:
        rates = [
            ("STATIONARY", ENERGY_RATE_STATIONARY),
            ("WALKING", ENERGY_RATE_WALKING),
            ("JOGGING", ENERGY_RATE_JOGGING),
            ("RUNNING", ENERGY_RATE_RUNNING),
            ("SPRINTING", ENERGY_RATE_SPRINTING),
        ]
        for name, rate in rates:
            assert rate > 0, f"ENERGY_RATE_{name} <= 0: {rate}"

        for i in range(len(rates) - 1):
            curr_name, curr_rate = rates[i]
            next_name, next_rate = rates[i + 1]
            assert curr_rate < next_rate, \
                f"단조증가 위반: {curr_name}({curr_rate}) >= {next_name}({next_rate})"

        # 농구 경기 평균은 조깅~달리기 사이
        assert ENERGY_RATE_BASKETBALL_GAME > 0, "BASKETBALL_GAME <= 0"
        assert ENERGY_RATE_JOGGING <= ENERGY_RATE_BASKETBALL_GAME <= ENERGY_RATE_RUNNING, \
            f"BASKETBALL_GAME({ENERGY_RATE_BASKETBALL_GAME})이 JOGGING~RUNNING 범위 이탈"

        result.ok("에너지 소비율 단조 증가")
    except AssertionError as e:
        result.fail("에너지 소비율 단조 증가", str(e))


# =============================================================================
# [U] 연령대별 보정 계수 검증
# =============================================================================
def test_age_correction_factors(result: TestResult) -> None:
    """연령대별 보정 계수의 합리적 값 검증."""
    try:
        # AGE_TRUNK_MASS_FACTOR: 모든 AgeGroup 존재, ADULT = 1.0
        for ag in AgeGroup:
            val = AGE_TRUNK_MASS_FACTOR[ag]
            assert 0.5 <= val <= 1.5, f"AGE_TRUNK_MASS_FACTOR[{ag.name}] 범위 이탈: {val}"
        assert AGE_TRUNK_MASS_FACTOR[AgeGroup.ADULT] == 1.0, "체간 질량 보정 성인 != 1.0"

        # AGE_LIMB_LENGTH_FACTOR: 모든 AgeGroup 존재, ADULT = 1.0
        for ag in AgeGroup:
            val = AGE_LIMB_LENGTH_FACTOR[ag]
            assert 0.5 <= val <= 1.5, f"AGE_LIMB_LENGTH_FACTOR[{ag.name}] 범위 이탈: {val}"
        assert AGE_LIMB_LENGTH_FACTOR[AgeGroup.ADULT] == 1.0, "사지 길이 보정 성인 != 1.0"

        # YOUTH < TEEN < ADULT (사지 길이)
        assert AGE_LIMB_LENGTH_FACTOR[AgeGroup.YOUTH] < AGE_LIMB_LENGTH_FACTOR[AgeGroup.TEEN], \
            "유소년 >= 청소년 사지 길이 보정"
        assert AGE_LIMB_LENGTH_FACTOR[AgeGroup.TEEN] < AGE_LIMB_LENGTH_FACTOR[AgeGroup.ADULT], \
            "청소년 >= 성인 사지 길이 보정"

        # AGE_ANGLE_TOLERANCE: ADULT = 0.0, 나머지는 양수
        assert AGE_ANGLE_TOLERANCE[AgeGroup.ADULT] == 0.0, "성인 각도 허용 범위 != 0.0"
        for ag in AgeGroup:
            val = AGE_ANGLE_TOLERANCE[ag]
            assert val >= 0.0, f"AGE_ANGLE_TOLERANCE[{ag.name}] < 0: {val}"
            assert val <= 30.0, f"AGE_ANGLE_TOLERANCE[{ag.name}] 과도: {val}"

        result.ok("연령대별 보정 계수 합리적 값")
    except AssertionError as e:
        result.fail("연령대별 보정 계수", str(e))


# =============================================================================
# [V] 유틸리티 함수 테스트
# =============================================================================
def test_get_segment_mass_ratio(result: TestResult) -> None:
    """get_segment_mass_ratio 함수 테스트."""
    try:
        # 남성
        for seg in BodySegment:
            val = get_segment_mass_ratio(seg, Gender.MALE)
            assert val == SEGMENT_MASS_RATIO_MALE[seg], \
                f"{seg.name} 남성: 함수({val}) != 딕셔너리({SEGMENT_MASS_RATIO_MALE[seg]})"

        # 여성
        for seg in BodySegment:
            val = get_segment_mass_ratio(seg, Gender.FEMALE)
            assert val == SEGMENT_MASS_RATIO_FEMALE[seg], \
                f"{seg.name} 여성: 함수({val}) != 딕셔너리({SEGMENT_MASS_RATIO_FEMALE[seg]})"

        result.ok("get_segment_mass_ratio 함수")
    except AssertionError as e:
        result.fail("get_segment_mass_ratio", str(e))


def test_get_segment_com_proximal(result: TestResult) -> None:
    """get_segment_com_proximal 함수 테스트."""
    try:
        for seg in BodySegment:
            male_val = get_segment_com_proximal(seg, Gender.MALE)
            female_val = get_segment_com_proximal(seg, Gender.FEMALE)
            assert male_val == SEGMENT_COM_PROXIMAL_MALE[seg], \
                f"{seg.name} 남성: 불일치"
            assert female_val == SEGMENT_COM_PROXIMAL_FEMALE[seg], \
                f"{seg.name} 여성: 불일치"
        result.ok("get_segment_com_proximal 함수")
    except AssertionError as e:
        result.fail("get_segment_com_proximal", str(e))


def test_get_velocity_thresholds(result: TestResult) -> None:
    """get_velocity_thresholds 함수 테스트 (연령/성별 보정)."""
    try:
        # 성인 남성 = 기본값 그대로 (factor = 1.0 × 1.0)
        for intensity in MovementIntensity:
            expected = VELOCITY_THRESHOLDS_ADULT_MALE[intensity]
            actual = get_velocity_thresholds(intensity, AgeGroup.ADULT, Gender.MALE)
            assert abs(actual[0] - expected[0]) < 1e-6, \
                f"{intensity.name} 성인남성 하한: {actual[0]} != {expected[0]}"
            assert abs(actual[1] - expected[1]) < 1e-6, \
                f"{intensity.name} 성인남성 상한: {actual[1]} != {expected[1]}"

        # 유소년 여성: factor = 0.65 * 0.90 = 0.585
        youth_female = get_velocity_thresholds(
            MovementIntensity.RUNNING, AgeGroup.YOUTH, Gender.FEMALE
        )
        base = VELOCITY_THRESHOLDS_ADULT_MALE[MovementIntensity.RUNNING]
        expected_factor = AGE_VELOCITY_FACTOR[AgeGroup.YOUTH] * GENDER_VELOCITY_FACTOR[Gender.FEMALE]
        expected_min = base[0] * expected_factor
        expected_max = base[1] * expected_factor
        assert abs(youth_female[0] - expected_min) < 1e-6, \
            f"유소년여성 하한: {youth_female[0]} != {expected_min}"
        assert abs(youth_female[1] - expected_max) < 1e-6, \
            f"유소년여성 상한: {youth_female[1]} != {expected_max}"

        # 보정된 값은 원본보다 작아야 함 (factor < 1)
        assert youth_female[0] < base[0], "유소년여성 하한이 성인남성 이상"
        assert youth_female[1] < base[1], "유소년여성 상한이 성인남성 이상"

        result.ok("get_velocity_thresholds 함수 (연령/성별 보정)")
    except AssertionError as e:
        result.fail("get_velocity_thresholds", str(e))


def test_get_adjusted_angle_range(result: TestResult) -> None:
    """get_adjusted_angle_range 함수 테스트 (연령대별 허용 범위 확장)."""
    try:
        optimal = (100.0, 135.0)

        # 성인: tolerance = 0.0 → 그대로
        adult_range = get_adjusted_angle_range(optimal, AgeGroup.ADULT)
        assert adult_range == optimal, f"성인 범위 변경: {adult_range} != {optimal}"

        # 유소년: tolerance = 15.0 → (85.0, 150.0)
        youth_range = get_adjusted_angle_range(optimal, AgeGroup.YOUTH)
        tolerance = AGE_ANGLE_TOLERANCE[AgeGroup.YOUTH]
        expected_min = max(0.0, optimal[0] - tolerance)
        expected_max = min(180.0, optimal[1] + tolerance)
        assert abs(youth_range[0] - expected_min) < 1e-6, \
            f"유소년 min: {youth_range[0]} != {expected_min}"
        assert abs(youth_range[1] - expected_max) < 1e-6, \
            f"유소년 max: {youth_range[1]} != {expected_max}"

        # 유소년 범위가 성인보다 넓어야 함
        assert youth_range[0] <= adult_range[0], "유소년 min > 성인 min"
        assert youth_range[1] >= adult_range[1], "유소년 max < 성인 max"

        # 하한 0 클램핑 테스트: optimal = (5.0, 30.0) + 청소년 tolerance=8
        small_range = (5.0, 30.0)
        teen_range = get_adjusted_angle_range(small_range, AgeGroup.TEEN)
        teen_tol = AGE_ANGLE_TOLERANCE[AgeGroup.TEEN]
        assert teen_range[0] == max(0.0, small_range[0] - teen_tol), \
            f"하한 클램핑 실패: {teen_range[0]}"

        # 상한 180 클램핑 테스트: optimal = (160.0, 178.0) + 유소년 tolerance=15
        high_range = (160.0, 178.0)
        youth_high = get_adjusted_angle_range(high_range, AgeGroup.YOUTH)
        assert youth_high[1] == 180.0, f"상한 180 클램핑 실패: {youth_high[1]}"

        result.ok("get_adjusted_angle_range 함수 (연령대별 허용 범위)")
    except AssertionError as e:
        result.fail("get_adjusted_angle_range", str(e))


# =============================================================================
# [W] __all__ 완전성 테스트
# =============================================================================
def test_all_completeness(result: TestResult) -> None:
    """__all__ 리스트가 모든 공개 심볼을 포함하는지 테스트."""
    try:
        module_all = _bmc_module.__all__

        # __all__ 에 정의된 모든 이름이 실제 모듈에 존재하는지
        missing_in_module = []
        for name in module_all:
            if not hasattr(_bmc_module, name):
                missing_in_module.append(name)
        assert len(missing_in_module) == 0, \
            f"__all__에 정의되었지만 모듈에 없음: {missing_in_module}"

        # 필수 항목이 __all__에 포함되는지
        required_exports = [
            # 열거형
            "BodySegment", "MotionPhase", "MovementIntensity", "StanceType",
            # 인체측정 질량비
            "SEGMENT_MASS_RATIO_MALE", "SEGMENT_MASS_RATIO_FEMALE",
            # 길이비
            "SEGMENT_LENGTH_RATIO",
            # COM 근위비
            "SEGMENT_COM_PROXIMAL_MALE", "SEGMENT_COM_PROXIMAL_FEMALE",
            # 회전 반경비
            "SEGMENT_GYRATION_RADIUS_MALE", "SEGMENT_GYRATION_RADIUS_FEMALE",
            # ROM
            "JOINT_ROM_NORMAL",
            # 농구 각도
            "SHOOTING_OPTIMAL_ANGLES", "DEFENSIVE_STANCE_ANGLES",
            "DRIBBLING_STANCE_ANGLES", "JUMP_LANDING_ANGLES",
            # 속도
            "VELOCITY_THRESHOLDS_ADULT_MALE", "VELOCITY_THRESHOLDS_ADULT_FEMALE",
            "AGE_VELOCITY_FACTOR", "GENDER_VELOCITY_FACTOR",
            # 가속도
            "ACCELERATION_NORMAL_MIN", "ACCELERATION_NORMAL_MAX",
            "ACCELERATION_QUICK_MIN", "ACCELERATION_QUICK_MAX",
            "ACCELERATION_EXPLOSIVE_THRESHOLD", "DECELERATION_HARD_STOP_THRESHOLD",
            # 각속도
            "SHOOTING_ELBOW_ANGULAR_VELOCITY", "SHOOTING_WRIST_ANGULAR_VELOCITY",
            "SHOOTING_HIP_ROTATION_VELOCITY", "PASSING_ARM_ANGULAR_VELOCITY",
            # 균형/안정성
            "COP_SWAY_STABLE_THRESHOLD_CM", "COP_SWAY_UNSTABLE_THRESHOLD_CM",
            "STABILIZATION_TIME_GOOD_S", "STABILIZATION_TIME_ACCEPTABLE_S",
            "STABILIZATION_TIME_POOR_S",
            "BASE_OF_SUPPORT_MIN_RATIO", "BASE_OF_SUPPORT_OPTIMAL_RATIO",
            "BASE_OF_SUPPORT_MAX_RATIO",
            "COM_HEIGHT_CHANGE_JUMP_THRESHOLD", "COM_HEIGHT_CHANGE_LANDING_THRESHOLD",
            # 동역학
            "VERTICAL_GRF_WALKING_BW", "VERTICAL_GRF_RUNNING_BW",
            "VERTICAL_GRF_JUMP_LANDING_BW", "VERTICAL_GRF_MAX_SAFE_BW",
            "LANDING_IMPACT_ABSORPTION_GOOD_S", "LANDING_IMPACT_ABSORPTION_POOR_S",
            "CONTACT_FORCE_LIGHT_BW", "CONTACT_FORCE_MODERATE_BW",
            "CONTACT_FORCE_HEAVY_BW", "CONTACT_FORCE_EXCESSIVE_BW",
            # 에너지
            "ENERGY_RATE_STATIONARY", "ENERGY_RATE_WALKING",
            "ENERGY_RATE_JOGGING", "ENERGY_RATE_RUNNING",
            "ENERGY_RATE_SPRINTING", "ENERGY_RATE_BASKETBALL_GAME",
            # 보정 계수
            "AGE_TRUNK_MASS_FACTOR", "AGE_LIMB_LENGTH_FACTOR",
            "AGE_ANGLE_TOLERANCE",
            # 유틸리티 함수
            "get_segment_mass_ratio", "get_segment_com_proximal",
            "get_velocity_thresholds", "get_adjusted_angle_range",
        ]

        missing_in_all = [name for name in required_exports if name not in module_all]
        assert len(missing_in_all) == 0, \
            f"__all__에 누락된 필수 항목: {missing_in_all}"

        result.ok(f"__all__ 완전성 ({len(module_all)}개 심볼)")
    except AssertionError as e:
        result.fail("__all__ 완전성", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main():
    """모든 biomechanics_constants 단위 테스트 실행."""
    print("=" * 60)
    print("biomechanics_constants.py 단위 테스트")
    print("=" * 60)

    result = TestResult()

    print("\n[A] Enum 완전성 테스트")
    test_body_segment_completeness(result)
    test_motion_phase_completeness(result)
    test_movement_intensity_completeness(result)
    test_stance_type_completeness(result)

    print("\n[B] Enum str 상속 테스트")
    test_body_segment_str_inheritance(result)
    test_motion_phase_str_inheritance(result)
    test_movement_intensity_str_inheritance(result)
    test_stance_type_str_inheritance(result)

    print("\n[C] Enum 고유성 테스트")
    test_body_segment_uniqueness(result)
    test_motion_phase_uniqueness(result)
    test_movement_intensity_uniqueness(result)
    test_stance_type_uniqueness(result)

    print("\n[D] Enum 다국어(i18n) 테스트")
    test_body_segment_i18n(result)
    test_motion_phase_i18n(result)
    test_movement_intensity_i18n(result)
    test_stance_type_i18n(result)

    print("\n[E] BodySegment.is_bilateral 테스트")
    test_is_bilateral_property(result)

    print("\n[F] BodySegment.mass_ratio_male/female 프로퍼티 테스트")
    test_mass_ratio_properties(result)

    print("\n[G] 인체측정 모델 커버리지 테스트")
    test_anthropometric_model_coverage(result)

    print("\n[H] 질량비 과학적 검증 (합산 ~1.0)")
    test_mass_ratio_sum_male(result)
    test_mass_ratio_sum_female(result)

    print("\n[I] 길이비 검증")
    test_length_ratio_positive(result)

    print("\n[J] 무게중심 근위비 검증")
    test_com_proximal_range(result)

    print("\n[K] 회전 반경비 검증")
    test_gyration_radius_range(result)

    print("\n[L] JOINT_ROM_NORMAL 검증")
    test_joint_rom_normal(result)

    print("\n[M] 농구 동작 각도 딕셔너리 검증")
    test_basketball_angle_dicts(result)

    print("\n[N] 속도 임계치 검증")
    test_velocity_thresholds_monotonic(result)
    test_velocity_male_greater_than_female(result)

    print("\n[O] 연령/성별 속도 계수 검증")
    test_age_gender_velocity_factors(result)

    print("\n[P] 가속도 상수 검증")
    test_acceleration_constants(result)

    print("\n[Q] 각속도 범위 검증")
    test_angular_velocity_ranges(result)

    print("\n[R] 균형/안정성 상수 검증")
    test_balance_stability_constants(result)

    print("\n[S] 동역학 힘/충격 상수 검증")
    test_force_dynamics_constants(result)

    print("\n[T] 에너지 소비율 검증")
    test_energy_rates_monotonic(result)

    print("\n[U] 연령대별 보정 계수 검증")
    test_age_correction_factors(result)

    print("\n[V] 유틸리티 함수 테스트")
    test_get_segment_mass_ratio(result)
    test_get_segment_com_proximal(result)
    test_get_velocity_thresholds(result)
    test_get_adjusted_angle_range(result)

    print("\n[W] __all__ 완전성 테스트")
    test_all_completeness(result)

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
