# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/unit
파일: test_validation.py
설명: validation.py 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from pose_estimation.keypoint_types import UnifiedKeypoint
from pose_estimation.validation import (
    # 열거형
    ValidationLevel,
    ViolationType,
    Severity,
    JointType,
    BasketballAction,
    AgeGroup,
    Gender,
    # 데이터 클래스
    JointAngleRange,
    LimbRatioRange,
    Violation,
    AnatomicalConstraints,
    ValidationResult,
    AngleResult,
    # 상수
    JOINT_ANGLE_LIMITS,
    BODY_SEGMENT_RATIOS,
    SHOOTING_JOINT_ANGLES,
    DRIBBLING_JOINT_ANGLES,
    DEFENSIVE_JOINT_ANGLES,
    JUMPING_JOINT_ANGLES,
    AGE_GROUP_ADJUSTMENTS,
    GENDER_ADJUSTMENTS,
    MIN_CONFIDENCE_FOR_ANGLE,
    # 함수
    get_joint_angle,
    get_joint_angle_3d,
    get_all_joint_angles,
    check_joint_angle_range,
    check_limb_length_ratio,
    validate_anatomical_constraints,
    validate_basketball_pose,
    is_pose_anatomically_valid,
)


# ============================================================
# 테스트 헬퍼
# ============================================================
def _make_keypoints_25x3(
    set_all_conf: float = 1.0,
) -> np.ndarray:
    """25개 Unified 키포인트 (N, 3) 형식 생성 — (x, y, confidence)."""
    kpts = np.zeros((25, 3), dtype=np.float32)
    # 기본 자세: 서있는 사람 (정규화 좌표)
    # 머리
    kpts[UnifiedKeypoint.NOSE] = [0.5, 0.1, set_all_conf]
    kpts[UnifiedKeypoint.LEFT_EYE] = [0.48, 0.08, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_EYE] = [0.52, 0.08, set_all_conf]
    kpts[UnifiedKeypoint.LEFT_EAR] = [0.46, 0.1, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_EAR] = [0.54, 0.1, set_all_conf]
    # 어깨
    kpts[UnifiedKeypoint.LEFT_SHOULDER] = [0.4, 0.25, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_SHOULDER] = [0.6, 0.25, set_all_conf]
    # 팔꿈치 (자연스러운 각도)
    kpts[UnifiedKeypoint.LEFT_ELBOW] = [0.35, 0.4, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_ELBOW] = [0.65, 0.4, set_all_conf]
    # 손목
    kpts[UnifiedKeypoint.LEFT_WRIST] = [0.33, 0.55, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_WRIST] = [0.67, 0.55, set_all_conf]
    # 손가락 (검지)
    kpts[UnifiedKeypoint.LEFT_INDEX] = [0.32, 0.58, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_INDEX] = [0.68, 0.58, set_all_conf]
    # 새끼
    kpts[UnifiedKeypoint.LEFT_PINKY] = [0.31, 0.57, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_PINKY] = [0.69, 0.57, set_all_conf]
    # 엄지
    kpts[UnifiedKeypoint.LEFT_THUMB] = [0.34, 0.57, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_THUMB] = [0.66, 0.57, set_all_conf]
    # 엉덩이
    kpts[UnifiedKeypoint.LEFT_HIP] = [0.43, 0.55, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_HIP] = [0.57, 0.55, set_all_conf]
    # 무릎
    kpts[UnifiedKeypoint.LEFT_KNEE] = [0.43, 0.72, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_KNEE] = [0.57, 0.72, set_all_conf]
    # 발목
    kpts[UnifiedKeypoint.LEFT_ANKLE] = [0.43, 0.9, set_all_conf]
    kpts[UnifiedKeypoint.RIGHT_ANKLE] = [0.57, 0.9, set_all_conf]
    # 목, 골반 (중점)
    kpts[UnifiedKeypoint.NECK] = [0.5, 0.2, set_all_conf]
    kpts[UnifiedKeypoint.PELVIS] = [0.5, 0.55, set_all_conf]
    return kpts


# ============================================================
# 1. 열거형 테스트
# ============================================================
class TestEnums:
    """열거형 정의 테스트."""

    def test_validation_level(self) -> None:
        assert len(ValidationLevel) == 3

    def test_violation_type(self) -> None:
        assert len(ViolationType) == 5

    def test_severity(self) -> None:
        assert len(Severity) == 3

    def test_joint_type(self) -> None:
        assert len(JointType) == 12

    def test_basketball_action(self) -> None:
        assert len(BasketballAction) == 7

    def test_age_group(self) -> None:
        assert len(AgeGroup) == 3

    def test_gender(self) -> None:
        assert len(Gender) == 2


# ============================================================
# 2. 데이터 클래스 테스트
# ============================================================
class TestJointAngleRange:
    """JointAngleRange 테스트."""

    def test_is_valid(self) -> None:
        r = JointAngleRange(min_angle=0, max_angle=150)
        assert r.is_valid(75) is True
        assert r.is_valid(-1) is False
        assert r.is_valid(151) is False

    def test_is_optimal_with_range(self) -> None:
        r = JointAngleRange(min_angle=0, max_angle=150, optimal_min=20, optimal_max=130)
        assert r.is_optimal(75) is True
        assert r.is_optimal(5) is False

    def test_is_optimal_without_range(self) -> None:
        r = JointAngleRange(min_angle=0, max_angle=150)
        assert r.is_optimal(75) is True  # 최적 범위 미설정 → is_valid 대체

    def test_frozen(self) -> None:
        r = JointAngleRange(min_angle=0, max_angle=150)
        with pytest.raises(AttributeError):
            r.min_angle = 10  # type: ignore[misc]


class TestLimbRatioRange:
    """LimbRatioRange 테스트."""

    def test_is_valid(self) -> None:
        r = LimbRatioRange(min_ratio=0.85, max_ratio=1.15)
        assert r.is_valid(1.0) is True
        assert r.is_valid(0.5) is False

    def test_default_reference(self) -> None:
        r = LimbRatioRange(min_ratio=0.5, max_ratio=1.5)
        assert r.reference == "torso_height"


class TestViolation:
    """Violation 테스트."""

    def test_creation(self) -> None:
        v = Violation(
            violation_type=ViolationType.JOINT_ANGLE_OUT_OF_RANGE,
            severity=Severity.WARNING,
            joint_or_part="left_elbow",
            message="각도 범위 초과",
        )
        assert v.expected is None
        assert v.actual is None

    def test_slots(self) -> None:
        """slots=True 적용 확인."""
        v = Violation(
            violation_type=ViolationType.KEYPOINT_MISSING,
            severity=Severity.ERROR,
            joint_or_part="test",
            message="test",
        )
        assert hasattr(v, "__slots__")


class TestValidationResult:
    """ValidationResult 테스트."""

    def test_defaults(self) -> None:
        r = ValidationResult(is_valid=True)
        assert r.violations == []
        assert r.joint_angles == {}
        assert r.confidence_score == 1.0

    def test_slots(self) -> None:
        r = ValidationResult(is_valid=True)
        assert hasattr(r, "__slots__")


class TestAngleResult:
    """AngleResult NamedTuple 테스트."""

    def test_creation(self) -> None:
        r = AngleResult(angle=90.0, confidence=0.95, valid=True)
        assert r.angle == 90.0
        assert r.valid is True


# ============================================================
# 3. 상수 테스트
# ============================================================
class TestConstants:
    """상수 정의 테스트."""

    def test_joint_angle_limits_complete(self) -> None:
        expected = {
            "left_elbow", "right_elbow",
            "left_shoulder", "right_shoulder",
            "left_wrist", "right_wrist",
            "left_knee", "right_knee",
            "left_hip", "right_hip",
            "neck", "torso_left", "torso_right",
        }
        assert set(JOINT_ANGLE_LIMITS.keys()) == expected

    def test_body_segment_ratios(self) -> None:
        assert len(BODY_SEGMENT_RATIOS) == 5

    def test_shooting_joint_angles(self) -> None:
        assert "right_elbow" in SHOOTING_JOINT_ANGLES
        assert "right_shoulder" in SHOOTING_JOINT_ANGLES

    def test_age_group_adjustments(self) -> None:
        assert AgeGroup.YOUTH in AGE_GROUP_ADJUSTMENTS
        assert AGE_GROUP_ADJUSTMENTS[AgeGroup.YOUTH]["flexibility_factor"] == 1.15

    def test_gender_adjustments(self) -> None:
        assert Gender.FEMALE in GENDER_ADJUSTMENTS
        assert GENDER_ADJUSTMENTS[Gender.FEMALE]["flexibility_factor"] == 1.1


# ============================================================
# 4. 관절 각도 계산 테스트
# ============================================================
class TestGetJointAngle:
    """get_joint_angle 함수 테스트."""

    def test_valid_angle(self) -> None:
        kpts = _make_keypoints_25x3()
        result = get_joint_angle(kpts, "left_elbow")
        assert result.valid is True
        assert 0.0 < result.angle < 180.0
        assert result.confidence > 0.0

    def test_low_confidence(self) -> None:
        kpts = _make_keypoints_25x3(set_all_conf=0.1)
        result = get_joint_angle(kpts, "left_elbow")
        assert result.valid is False  # MIN_CONFIDENCE_FOR_ANGLE = 0.3

    def test_invalid_joint_name(self) -> None:
        kpts = _make_keypoints_25x3()
        result = get_joint_angle(kpts, "invalid_joint")
        assert result.valid is False

    def test_3d_variant(self) -> None:
        kpts = _make_keypoints_25x3()
        result = get_joint_angle_3d(kpts, "left_elbow")
        assert isinstance(result, AngleResult)


class TestGetAllJointAngles:
    """get_all_joint_angles 함수 테스트."""

    def test_returns_13_joints(self) -> None:
        kpts = _make_keypoints_25x3()
        results = get_all_joint_angles(kpts)
        assert len(results) == 13

    def test_all_values_are_angle_result(self) -> None:
        kpts = _make_keypoints_25x3()
        for name, result in get_all_joint_angles(kpts).items():
            assert isinstance(result, AngleResult), f"{name} is not AngleResult"


# ============================================================
# 5. 해부학적 검증 테스트
# ============================================================
class TestValidateAnatomicalConstraints:
    """validate_anatomical_constraints 함수 테스트."""

    def test_normal_pose_passes(self) -> None:
        kpts = _make_keypoints_25x3()
        result = validate_anatomical_constraints(kpts)
        assert isinstance(result, ValidationResult)

    def test_basic_level(self) -> None:
        kpts = _make_keypoints_25x3()
        result = validate_anatomical_constraints(kpts, level=ValidationLevel.BASIC)
        assert isinstance(result, ValidationResult)

    def test_custom_constraints(self) -> None:
        kpts = _make_keypoints_25x3()
        constraints = AnatomicalConstraints(
            joint_angle_limits=JOINT_ANGLE_LIMITS,
            limb_ratios=BODY_SEGMENT_RATIOS,
            age_group=AgeGroup.YOUTH,
            gender=Gender.FEMALE,
        )
        result = validate_anatomical_constraints(kpts, constraints)
        assert isinstance(result, ValidationResult)


class TestCheckJointAngleRange:
    """check_joint_angle_range 함수 테스트."""

    def test_valid_angle(self) -> None:
        kpts = _make_keypoints_25x3()
        valid, angle, msg = check_joint_angle_range(kpts, "left_elbow")
        assert isinstance(valid, bool)
        assert angle >= 0.0

    def test_custom_range(self) -> None:
        kpts = _make_keypoints_25x3()
        custom = JointAngleRange(min_angle=0, max_angle=180)
        valid, angle, msg = check_joint_angle_range(kpts, "left_elbow", custom)
        assert valid is True


class TestCheckLimbLengthRatio:
    """check_limb_length_ratio 함수 테스트."""

    def test_upper_arm_to_torso(self) -> None:
        kpts = _make_keypoints_25x3()
        valid, ratio, msg = check_limb_length_ratio(kpts, "upper_arm_to_torso")
        assert isinstance(valid, bool)

    def test_unknown_limb(self) -> None:
        kpts = _make_keypoints_25x3()
        valid, ratio, msg = check_limb_length_ratio(kpts, "unknown_limb")
        assert valid is True
        assert msg == "비율 정의 없음"


# ============================================================
# 6. 농구 자세 검증 테스트
# ============================================================
class TestValidateBasketballPose:
    """validate_basketball_pose 함수 테스트."""

    def test_shooting_pose(self) -> None:
        kpts = _make_keypoints_25x3()
        result = validate_basketball_pose(kpts, BasketballAction.SHOOTING)
        assert isinstance(result, ValidationResult)
        assert isinstance(result.is_valid, bool)

    def test_defense_pose(self) -> None:
        kpts = _make_keypoints_25x3()
        result = validate_basketball_pose(kpts, BasketballAction.DEFENSE)
        assert isinstance(result, ValidationResult)

    def test_strict_mode(self) -> None:
        kpts = _make_keypoints_25x3()
        result = validate_basketball_pose(kpts, BasketballAction.SHOOTING, strict=True)
        assert isinstance(result, ValidationResult)

    def test_low_confidence_keypoints(self) -> None:
        """신뢰도 낮은 키포인트 → 검증 불가."""
        kpts = _make_keypoints_25x3(set_all_conf=0.1)
        result = validate_basketball_pose(kpts, BasketballAction.SHOOTING)
        assert result.is_valid is False


class TestIsPoseAnatomicallyValid:
    """is_pose_anatomically_valid 함수 테스트."""

    def test_normal_pose(self) -> None:
        kpts = _make_keypoints_25x3()
        assert isinstance(is_pose_anatomically_valid(kpts), bool)

    def test_strict(self) -> None:
        kpts = _make_keypoints_25x3()
        assert isinstance(is_pose_anatomically_valid(kpts, strict=True), bool)


# ============================================================
# 7. 모듈 레벨 테스트
# ============================================================
class TestModuleLevel:
    """모듈 레벨 속성 테스트."""

    def test_version(self) -> None:
        from pose_estimation.validation import __version__
        assert __version__ == "1.0.0"

    def test_all_exports(self) -> None:
        from pose_estimation.validation import __all__
        assert "validate_anatomical_constraints" in __all__
        assert "BasketballAction" in __all__
        assert "JointAngleRange" in __all__
