# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation
파일: validation.py
설명: 해부학적 유효성 검증 (관절 각도 범위, 농구 자세)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

포함 내용:
    - 해부학적 관절 각도 범위 검증
    - 신체 비율 검증
    - 농구 동작별 자세 검증
    - 성별/연령별 기준 적용

설계 원칙:
    - Direct Import (순수 검증 함수)
    - 과학적 해부학 기준
    - 농구 동작에 최적화된 범위
    - 유소년/청소년/성인 구분
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NamedTuple
import logging
import math

import numpy as np
from numpy.typing import NDArray

# ============================================================
# 내부 모듈
# ============================================================
from pose_estimation.keypoint_types import (
    UnifiedKeypoint,
    get_joint_keypoints,
    BODY_PARTS,
    BASKETBALL_KEYPOINT_GROUPS,
)

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 설정 상수
# ============================================================
CONFIG_KEY_POSE_VALIDATOR = "pose.validation"

# 검증 임계값 상수
MIN_CONFIDENCE_FOR_ANGLE = 0.3  # 각도 계산에 필요한 최소 신뢰도
MAX_MISSING_KEYPOINTS = 3  # 검증 가능한 최대 누락 키포인트 수


# ============================================================
# 열거형 정의
# ============================================================
class ValidationLevel(Enum):
    """검증 레벨."""
    BASIC = auto()  # 기본 (필수 키포인트만)
    STANDARD = auto()  # 표준 (해부학적 검증)
    STRICT = auto()  # 엄격 (농구 자세 검증 포함)


class ViolationType(Enum):
    """위반 유형."""
    JOINT_ANGLE_OUT_OF_RANGE = auto()  # 관절 각도 범위 초과
    LIMB_RATIO_INVALID = auto()  # 사지 비율 이상
    KEYPOINT_MISSING = auto()  # 키포인트 누락
    ANATOMICALLY_IMPOSSIBLE = auto()  # 해부학적 불가능
    BASKETBALL_POSE_INVALID = auto()  # 농구 자세 부적합


class Severity(Enum):
    """심각도."""
    INFO = auto()  # 정보
    WARNING = auto()  # 경고
    ERROR = auto()  # 오류 (유효하지 않음)


class JointType(Enum):
    """관절 유형."""
    # 팔 관절
    LEFT_SHOULDER = auto()
    RIGHT_SHOULDER = auto()
    LEFT_ELBOW = auto()
    RIGHT_ELBOW = auto()
    LEFT_WRIST = auto()
    RIGHT_WRIST = auto()
    # 다리 관절
    LEFT_HIP = auto()
    RIGHT_HIP = auto()
    LEFT_KNEE = auto()
    RIGHT_KNEE = auto()
    # 몸통
    NECK = auto()
    SPINE = auto()


class BasketballAction(Enum):
    """농구 동작 유형."""
    SHOOTING = auto()  # 슈팅
    DRIBBLING = auto()  # 드리블
    PASSING = auto()  # 패스
    DEFENSE = auto()  # 수비
    REBOUNDING = auto()  # 리바운드
    JUMPING = auto()  # 점프
    PIVOT = auto()  # 피벗


class AgeGroup(Enum):
    """연령 그룹."""
    YOUTH = auto()  # 유소년 (7-12세)
    TEEN = auto()  # 청소년 (13-18세)
    ADULT = auto()  # 성인 (19세+)


class Gender(Enum):
    """성별."""
    MALE = auto()
    FEMALE = auto()


# ============================================================
# 데이터 클래스 정의
# ============================================================
@dataclass(frozen=True, slots=True)
class JointAngleRange:
    """
    관절 각도 허용 범위.

    Attributes:
        min_angle: 최소 각도 (도)
        max_angle: 최대 각도 (도)
        optimal_min: 최적 범위 최소 (선택)
        optimal_max: 최적 범위 최대 (선택)
    """
    min_angle: float
    max_angle: float
    optimal_min: float | None = None
    optimal_max: float | None = None

    def is_valid(self, angle: float) -> bool:
        """각도가 범위 내인지 확인."""
        return self.min_angle <= angle <= self.max_angle

    def is_optimal(self, angle: float) -> bool:
        """각도가 최적 범위 내인지 확인."""
        if self.optimal_min is None or self.optimal_max is None:
            return self.is_valid(angle)
        return self.optimal_min <= angle <= self.optimal_max


@dataclass(frozen=True, slots=True)
class LimbRatioRange:
    """
    사지 길이 비율 허용 범위.

    Attributes:
        min_ratio: 최소 비율
        max_ratio: 최대 비율
        reference: 기준 부위
    """
    min_ratio: float
    max_ratio: float
    reference: str = "torso_height"

    def is_valid(self, ratio: float) -> bool:
        """비율이 범위 내인지 확인."""
        return self.min_ratio <= ratio <= self.max_ratio


@dataclass(slots=True)
class Violation:
    """
    검증 위반 정보.

    Attributes:
        violation_type: 위반 유형
        severity: 심각도
        joint_or_part: 관련 관절/부위
        message: 설명 메시지
        expected: 예상 값/범위
        actual: 실제 값
    """
    violation_type: ViolationType
    severity: Severity
    joint_or_part: str
    message: str
    expected: str | None = None
    actual: float | None = None


@dataclass(slots=True)
class AnatomicalConstraints:
    """해부학적 제약 조건."""
    joint_angle_limits: dict[str, JointAngleRange] = field(default_factory=dict)
    limb_ratios: dict[str, LimbRatioRange] = field(default_factory=dict)
    age_group: AgeGroup = AgeGroup.ADULT
    gender: Gender = Gender.MALE


@dataclass(slots=True)
class BasketballPoseConstraints:
    """농구 자세 제약 조건."""
    action: BasketballAction
    required_keypoints: frozenset
    joint_angle_ranges: dict[str, JointAngleRange]
    description: str = ""


@dataclass(slots=True)
class ValidationResult:
    """
    검증 결과.

    Attributes:
        is_valid: 유효성 여부
        violations: 위반 목록
        joint_angles: 계산된 관절 각도
        confidence_score: 전체 신뢰도 점수
    """
    is_valid: bool
    violations: list[Violation] = field(default_factory=list)
    joint_angles: dict[str, float] = field(default_factory=dict)
    confidence_score: float = 1.0
    message: str = ""


class AngleResult(NamedTuple):
    """관절 각도 계산 결과."""
    angle: float  # 각도 (도)
    confidence: float  # 신뢰도
    valid: bool  # 유효성


# ============================================================
# 해부학적 관절 각도 제한 (성인 기준)
# ============================================================
JOINT_ANGLE_LIMITS: dict[str, JointAngleRange] = {
    # =========================================================================
    # 팔 관절
    # =========================================================================
    "left_elbow": JointAngleRange(
        min_angle=0.0,  # 완전 신전
        max_angle=150.0,  # 최대 굴곡
        optimal_min=20.0,
        optimal_max=140.0,
    ),
    "right_elbow": JointAngleRange(
        min_angle=0.0,
        max_angle=150.0,
        optimal_min=20.0,
        optimal_max=140.0,
    ),
    "left_shoulder": JointAngleRange(
        min_angle=0.0,  # 팔 내림
        max_angle=180.0,  # 팔 들어올림
        optimal_min=10.0,
        optimal_max=170.0,
    ),
    "right_shoulder": JointAngleRange(
        min_angle=0.0,
        max_angle=180.0,
        optimal_min=10.0,
        optimal_max=170.0,
    ),
    "left_wrist": JointAngleRange(
        min_angle=90.0,  # 손목 펴짐
        max_angle=200.0,  # 손목 굴곡
        optimal_min=100.0,
        optimal_max=180.0,
    ),
    "right_wrist": JointAngleRange(
        min_angle=90.0,
        max_angle=200.0,
        optimal_min=100.0,
        optimal_max=180.0,
    ),

    # =========================================================================
    # 다리 관절
    # =========================================================================
    "left_knee": JointAngleRange(
        min_angle=0.0,  # 완전 신전
        max_angle=160.0,  # 최대 굴곡
        optimal_min=5.0,
        optimal_max=150.0,
    ),
    "right_knee": JointAngleRange(
        min_angle=0.0,
        max_angle=160.0,
        optimal_min=5.0,
        optimal_max=150.0,
    ),
    "left_hip": JointAngleRange(
        min_angle=0.0,  # 서있을 때
        max_angle=130.0,  # 최대 굴곡
        optimal_min=5.0,
        optimal_max=120.0,
    ),
    "right_hip": JointAngleRange(
        min_angle=0.0,
        max_angle=130.0,
        optimal_min=5.0,
        optimal_max=120.0,
    ),

    # =========================================================================
    # 몸통
    # =========================================================================
    "neck": JointAngleRange(
        min_angle=150.0,  # 고개 숙임
        max_angle=200.0,  # 고개 젖힘
        optimal_min=165.0,
        optimal_max=195.0,
    ),
    "torso_left": JointAngleRange(
        min_angle=140.0,  # 몸 굽힘
        max_angle=200.0,  # 젖힘
        optimal_min=160.0,
        optimal_max=190.0,
    ),
    "torso_right": JointAngleRange(
        min_angle=140.0,
        max_angle=200.0,
        optimal_min=160.0,
        optimal_max=190.0,
    ),
}


# ============================================================
# 신체 부위 비율 범위
# ============================================================
BODY_SEGMENT_RATIOS: dict[str, LimbRatioRange] = {
    # 상완 / 몸통 높이
    "upper_arm_to_torso": LimbRatioRange(
        min_ratio=0.35,
        max_ratio=0.55,
        reference="torso_height",
    ),
    # 전완 / 상완
    "forearm_to_upper_arm": LimbRatioRange(
        min_ratio=0.85,
        max_ratio=1.15,
        reference="upper_arm",
    ),
    # 대퇴 / 몸통 높이
    "thigh_to_torso": LimbRatioRange(
        min_ratio=0.85,
        max_ratio=1.25,
        reference="torso_height",
    ),
    # 정강이 / 대퇴
    "shin_to_thigh": LimbRatioRange(
        min_ratio=0.85,
        max_ratio=1.15,
        reference="thigh",
    ),
    # 어깨 너비 / 골반 너비
    "shoulder_to_hip_width": LimbRatioRange(
        min_ratio=1.0,
        max_ratio=1.8,
        reference="hip_width",
    ),
}


# ============================================================
# 농구 동작별 관절 각도 상수
# ============================================================

# 슈팅 자세 관절 각도 범위
SHOOTING_JOINT_ANGLES: dict[str, JointAngleRange] = {
    # 슈팅 팔 (오른손잡이 기준)
    "right_elbow": JointAngleRange(
        min_angle=70.0,  # 준비 자세
        max_angle=150.0,  # 릴리즈 후
        optimal_min=85.0,  # 이상적 준비
        optimal_max=100.0,  # 이상적 릴리즈 직전
    ),
    "right_shoulder": JointAngleRange(
        min_angle=70.0,
        max_angle=170.0,
        optimal_min=90.0,  # 팔 수평 이상
        optimal_max=140.0,  # 과도한 뒤로 젖힘 방지
    ),
    "right_wrist": JointAngleRange(
        min_angle=100.0,  # 손목 굴곡
        max_angle=180.0,  # 손목 신전
        optimal_min=130.0,  # 적절한 스냅
        optimal_max=160.0,
    ),
    # 서포팅 팔
    "left_elbow": JointAngleRange(
        min_angle=30.0,
        max_angle=120.0,
        optimal_min=45.0,
        optimal_max=90.0,
    ),
    # 다리
    "right_knee": JointAngleRange(
        min_angle=10.0,  # 점프 시 펴짐
        max_angle=90.0,  # 준비 시 굽힘
        optimal_min=20.0,
        optimal_max=60.0,
    ),
    "left_knee": JointAngleRange(
        min_angle=10.0,
        max_angle=90.0,
        optimal_min=20.0,
        optimal_max=60.0,
    ),
}

# 드리블 자세 관절 각도 범위
DRIBBLING_JOINT_ANGLES: dict[str, JointAngleRange] = {
    # 드리블 팔
    "right_elbow": JointAngleRange(
        min_angle=40.0,
        max_angle=130.0,
        optimal_min=60.0,
        optimal_max=110.0,
    ),
    "left_elbow": JointAngleRange(
        min_angle=40.0,
        max_angle=130.0,
        optimal_min=60.0,
        optimal_max=110.0,
    ),
    # 자세 (낮은 자세 유지)
    "right_knee": JointAngleRange(
        min_angle=30.0,  # 낮은 자세
        max_angle=80.0,  # 높은 자세
        optimal_min=40.0,
        optimal_max=60.0,  # 적절히 낮춤
    ),
    "left_knee": JointAngleRange(
        min_angle=30.0,
        max_angle=80.0,
        optimal_min=40.0,
        optimal_max=60.0,
    ),
    "right_hip": JointAngleRange(
        min_angle=20.0,
        max_angle=70.0,
        optimal_min=30.0,
        optimal_max=55.0,
    ),
    "left_hip": JointAngleRange(
        min_angle=20.0,
        max_angle=70.0,
        optimal_min=30.0,
        optimal_max=55.0,
    ),
}

# 수비 자세 관절 각도 범위
DEFENSIVE_JOINT_ANGLES: dict[str, JointAngleRange] = {
    # 낮은 자세 유지
    "right_knee": JointAngleRange(
        min_angle=40.0,
        max_angle=90.0,
        optimal_min=50.0,
        optimal_max=70.0,
    ),
    "left_knee": JointAngleRange(
        min_angle=40.0,
        max_angle=90.0,
        optimal_min=50.0,
        optimal_max=70.0,
    ),
    "right_hip": JointAngleRange(
        min_angle=30.0,
        max_angle=80.0,
        optimal_min=40.0,
        optimal_max=60.0,
    ),
    "left_hip": JointAngleRange(
        min_angle=30.0,
        max_angle=80.0,
        optimal_min=40.0,
        optimal_max=60.0,
    ),
    # 팔 위치 (양 팔 옆으로)
    "right_elbow": JointAngleRange(
        min_angle=90.0,
        max_angle=170.0,
        optimal_min=120.0,
        optimal_max=160.0,
    ),
    "left_elbow": JointAngleRange(
        min_angle=90.0,
        max_angle=170.0,
        optimal_min=120.0,
        optimal_max=160.0,
    ),
}

# 점프 자세 관절 각도 범위
JUMPING_JOINT_ANGLES: dict[str, JointAngleRange] = {
    # 이륙 전 (무릎 굽힘)
    "right_knee": JointAngleRange(
        min_angle=5.0,  # 공중
        max_angle=110.0,  # 준비
        optimal_min=10.0,
        optimal_max=80.0,
    ),
    "left_knee": JointAngleRange(
        min_angle=5.0,
        max_angle=110.0,
        optimal_min=10.0,
        optimal_max=80.0,
    ),
    # 엉덩이 굴곡
    "right_hip": JointAngleRange(
        min_angle=5.0,
        max_angle=80.0,
        optimal_min=10.0,
        optimal_max=60.0,
    ),
    "left_hip": JointAngleRange(
        min_angle=5.0,
        max_angle=80.0,
        optimal_min=10.0,
        optimal_max=60.0,
    ),
}


# ============================================================
# 연령/성별별 조정 계수
# ============================================================
AGE_GROUP_ADJUSTMENTS: dict[AgeGroup, dict[str, float]] = {
    AgeGroup.YOUTH: {
        "flexibility_factor": 1.15,  # 유연성 더 높음
        "strength_factor": 0.7,  # 근력 낮음
        "range_expansion": 1.1,  # 범위 확장
    },
    AgeGroup.TEEN: {
        "flexibility_factor": 1.1,
        "strength_factor": 0.85,
        "range_expansion": 1.05,
    },
    AgeGroup.ADULT: {
        "flexibility_factor": 1.0,
        "strength_factor": 1.0,
        "range_expansion": 1.0,
    },
}

GENDER_ADJUSTMENTS: dict[Gender, dict[str, float]] = {
    Gender.FEMALE: {
        "flexibility_factor": 1.1,  # 일반적으로 더 유연
        "shoulder_ratio": 0.95,  # 어깨 너비 비율
        "hip_ratio": 1.05,  # 골반 너비 비율
    },
    Gender.MALE: {
        "flexibility_factor": 1.0,
        "shoulder_ratio": 1.0,
        "hip_ratio": 1.0,
    },
}


# ============================================================
# 관절 각도 계산 함수
# ============================================================
def get_joint_angle(
    keypoints: NDArray[np.float32],
    joint_name: str,
    use_3d: bool = False,
) -> AngleResult:
    """
    관절 각도 계산 (2D/3D).

    세 점 A-B-C가 주어졌을 때 B에서의 각도를 계산합니다.

    Args:
        keypoints: 키포인트 배열 (N, 3) 또는 (N, 4)
        joint_name: 관절 이름 (예: "left_elbow", "right_knee")
        use_3d: 3D 각도 계산 여부 (z 좌표 사용)

    Returns:
        AngleResult (각도, 신뢰도, 유효성)

    Example:
        >>> result = get_joint_angle(keypoints, "left_elbow")
        >>> print(f"팔꿈치 각도: {result.angle:.1f}°")
    """
    try:
        parent, joint, child = get_joint_keypoints(joint_name)
    except ValueError as e:
        logger.warning("관절 정의 오류: %s", str(e))
        return AngleResult(angle=0.0, confidence=0.0, valid=False)

    p_idx = parent.value
    j_idx = joint.value
    c_idx = child.value

    # 인덱스 범위 확인
    num_kp = len(keypoints)
    if any(idx >= num_kp for idx in [p_idx, j_idx, c_idx]):
        return AngleResult(angle=0.0, confidence=0.0, valid=False)

    # 신뢰도 확인
    conf_idx = 2 if keypoints.shape[1] == 3 else 3
    confidences = [keypoints[p_idx, conf_idx], keypoints[j_idx, conf_idx], keypoints[c_idx, conf_idx]]
    avg_conf = float(np.mean(confidences))

    if avg_conf < MIN_CONFIDENCE_FOR_ANGLE:
        return AngleResult(angle=0.0, confidence=avg_conf, valid=False)

    # 벡터 계산
    if use_3d and keypoints.shape[1] >= 4:
        # 3D 각도
        vec1 = keypoints[p_idx, :3] - keypoints[j_idx, :3]
        vec2 = keypoints[c_idx, :3] - keypoints[j_idx, :3]
    else:
        # 2D 각도
        vec1 = keypoints[p_idx, :2] - keypoints[j_idx, :2]
        vec2 = keypoints[c_idx, :2] - keypoints[j_idx, :2]

    # 각도 계산
    angle = _calculate_angle_between_vectors(vec1, vec2)

    return AngleResult(angle=angle, confidence=avg_conf, valid=True)


def get_joint_angle_3d(
    keypoints: NDArray[np.float32],
    joint_name: str,
) -> AngleResult:
    """3D 관절 각도 계산 (z 좌표 사용)."""
    return get_joint_angle(keypoints, joint_name, use_3d=True)


def get_all_joint_angles(
    keypoints: NDArray[np.float32],
    use_3d: bool = False,
) -> dict[str, AngleResult]:
    """
    모든 관절 각도 계산.

    Args:
        keypoints: 키포인트 배열
        use_3d: 3D 각도 계산 여부

    Returns:
        관절 이름 → AngleResult 딕셔너리
    """
    joint_names = [
        "left_elbow", "right_elbow",
        "left_shoulder", "right_shoulder",
        "left_wrist", "right_wrist",
        "left_knee", "right_knee",
        "left_hip", "right_hip",
        "neck", "torso_left", "torso_right",
    ]

    results = {}
    for joint_name in joint_names:
        results[joint_name] = get_joint_angle(keypoints, joint_name, use_3d)

    return results


def _calculate_angle_between_vectors(
    vec1: NDArray,
    vec2: NDArray,
) -> float:
    """두 벡터 사이의 각도 계산 (도)."""
    # 벡터 정규화
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 < 1e-6 or norm2 < 1e-6:
        return 0.0

    unit1 = vec1 / norm1
    unit2 = vec2 / norm2

    # 내적으로 코사인 계산
    cos_angle = np.clip(np.dot(unit1, unit2), -1.0, 1.0)

    # 라디안 → 도
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)

    return angle_deg


def _calculate_limb_length(
    keypoints: NDArray[np.float32],
    start_idx: int,
    end_idx: int,
) -> float:
    """두 키포인트 사이 거리 계산."""
    if start_idx >= len(keypoints) or end_idx >= len(keypoints):
        return 0.0

    diff = keypoints[start_idx, :2] - keypoints[end_idx, :2]
    return float(np.linalg.norm(diff))


# ============================================================
# 해부학적 검증 함수
# ============================================================
def validate_anatomical_constraints(
    keypoints: NDArray[np.float32],
    constraints: AnatomicalConstraints | None = None,
    level: ValidationLevel = ValidationLevel.STANDARD,
) -> ValidationResult:
    """
    해부학적 제약 조건 검증.

    Args:
        keypoints: 키포인트 배열
        constraints: 해부학적 제약 (None이면 기본값)
        level: 검증 레벨

    Returns:
        검증 결과
    """
    violations: list[Violation] = []
    joint_angles: dict[str, float] = {}

    # 기본 제약 조건
    if constraints is None:
        constraints = AnatomicalConstraints(
            joint_angle_limits=JOINT_ANGLE_LIMITS,
            limb_ratios=BODY_SEGMENT_RATIOS,
        )

    # 연령/성별 조정
    age_adj = AGE_GROUP_ADJUSTMENTS.get(constraints.age_group, {})
    gender_adj = GENDER_ADJUSTMENTS.get(constraints.gender, {})
    range_expansion = age_adj.get("range_expansion", 1.0)

    # 1. 관절 각도 검증
    all_angles = get_all_joint_angles(keypoints)

    for joint_name, result in all_angles.items():
        if not result.valid:
            continue

        joint_angles[joint_name] = result.angle

        # 제한 범위 가져오기
        limits = constraints.joint_angle_limits.get(joint_name)
        if limits is None:
            limits = JOINT_ANGLE_LIMITS.get(joint_name)

        if limits is None:
            continue

        # 연령별 범위 조정
        adjusted_min = limits.min_angle - (5 * range_expansion)
        adjusted_max = limits.max_angle + (5 * range_expansion)

        # 범위 검사
        if result.angle < adjusted_min or result.angle > adjusted_max:
            severity = Severity.ERROR if level == ValidationLevel.STRICT else Severity.WARNING
            violations.append(Violation(
                violation_type=ViolationType.JOINT_ANGLE_OUT_OF_RANGE,
                severity=severity,
                joint_or_part=joint_name,
                message=f"{joint_name} 각도 범위 초과",
                expected=f"{adjusted_min:.1f}° - {adjusted_max:.1f}°",
                actual=result.angle,
            ))

    # 2. 신체 비율 검증 (표준 레벨 이상)
    if level in [ValidationLevel.STANDARD, ValidationLevel.STRICT]:
        ratio_violations = _check_limb_ratios(keypoints, constraints)
        violations.extend(ratio_violations)

    # 3. 최종 결과
    error_count = sum(1 for v in violations if v.severity == Severity.ERROR)
    is_valid = error_count == 0

    confidence = 1.0 - (len(violations) * 0.1)
    confidence = max(0.0, min(1.0, confidence))

    return ValidationResult(
        is_valid=is_valid,
        violations=violations,
        joint_angles=joint_angles,
        confidence_score=confidence,
    )


def check_joint_angle_range(
    keypoints: NDArray[np.float32],
    joint_name: str,
    custom_range: JointAngleRange | None = None,
) -> tuple[bool, float, str]:
    """
    단일 관절 각도 범위 검사.

    Args:
        keypoints: 키포인트 배열
        joint_name: 관절 이름
        custom_range: 커스텀 범위 (None이면 기본값)

    Returns:
        (유효 여부, 각도, 메시지)
    """
    result = get_joint_angle(keypoints, joint_name)

    if not result.valid:
        return (False, 0.0, f"{joint_name} 키포인트 누락")

    limits = custom_range or JOINT_ANGLE_LIMITS.get(joint_name)

    if limits is None:
        return (True, result.angle, "범위 정의 없음")

    if limits.is_valid(result.angle):
        if limits.is_optimal(result.angle):
            return (True, result.angle, "최적 범위")
        return (True, result.angle, "허용 범위")
    else:
        return (False, result.angle, f"범위 초과 ({limits.min_angle}°-{limits.max_angle}°)")


def check_limb_length_ratio(
    keypoints: NDArray[np.float32],
    limb_name: str,
    ratio_range: LimbRatioRange | None = None,
) -> tuple[bool, float, str]:
    """
    사지 길이 비율 검사.

    Args:
        keypoints: 키포인트 배열
        limb_name: 사지 이름
        ratio_range: 비율 범위

    Returns:
        (유효 여부, 비율, 메시지)
    """
    if ratio_range is None:
        ratio_range = BODY_SEGMENT_RATIOS.get(limb_name)

    if ratio_range is None:
        return (True, 0.0, "비율 정의 없음")

    # 사지별 계산
    ratio = 0.0

    if limb_name == "upper_arm_to_torso":
        # 상완 / 몸통 높이
        upper_arm = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_SHOULDER.value,
            UnifiedKeypoint.LEFT_ELBOW.value,
        )
        torso = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_SHOULDER.value,
            UnifiedKeypoint.LEFT_HIP.value,
        )
        if torso > 0.01:
            ratio = upper_arm / torso

    elif limb_name == "forearm_to_upper_arm":
        # 전완 / 상완
        forearm = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_ELBOW.value,
            UnifiedKeypoint.LEFT_WRIST.value,
        )
        upper_arm = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_SHOULDER.value,
            UnifiedKeypoint.LEFT_ELBOW.value,
        )
        if upper_arm > 0.01:
            ratio = forearm / upper_arm

    elif limb_name == "thigh_to_torso":
        # 대퇴 / 몸통
        thigh = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_HIP.value,
            UnifiedKeypoint.LEFT_KNEE.value,
        )
        torso = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_SHOULDER.value,
            UnifiedKeypoint.LEFT_HIP.value,
        )
        if torso > 0.01:
            ratio = thigh / torso

    elif limb_name == "shin_to_thigh":
        # 정강이 / 대퇴
        shin = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_KNEE.value,
            UnifiedKeypoint.LEFT_ANKLE.value,
        )
        thigh = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_HIP.value,
            UnifiedKeypoint.LEFT_KNEE.value,
        )
        if thigh > 0.01:
            ratio = shin / thigh

    elif limb_name == "shoulder_to_hip_width":
        # 어깨 너비 / 골반 너비
        shoulder_width = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_SHOULDER.value,
            UnifiedKeypoint.RIGHT_SHOULDER.value,
        )
        hip_width = _calculate_limb_length(
            keypoints,
            UnifiedKeypoint.LEFT_HIP.value,
            UnifiedKeypoint.RIGHT_HIP.value,
        )
        if hip_width > 0.01:
            ratio = shoulder_width / hip_width

    if ratio < 0.01:
        return (True, ratio, "측정 불가")

    if ratio_range.is_valid(ratio):
        return (True, ratio, "정상 범위")
    else:
        return (False, ratio, f"범위 초과 ({ratio_range.min_ratio:.2f}-{ratio_range.max_ratio:.2f})")


def _check_limb_ratios(
    keypoints: NDArray[np.float32],
    constraints: AnatomicalConstraints,
) -> list[Violation]:
    """모든 사지 비율 검사."""
    violations = []

    for limb_name, ratio_range in constraints.limb_ratios.items():
        valid, ratio, message = check_limb_length_ratio(keypoints, limb_name, ratio_range)

        if not valid and ratio > 0.01:
            violations.append(Violation(
                violation_type=ViolationType.LIMB_RATIO_INVALID,
                severity=Severity.WARNING,
                joint_or_part=limb_name,
                message=f"{limb_name} 비율 이상: {message}",
                expected=f"{ratio_range.min_ratio:.2f} - {ratio_range.max_ratio:.2f}",
                actual=ratio,
            ))

    return violations


# ============================================================
# 농구 자세 검증 함수
# ============================================================
def validate_basketball_pose(
    keypoints: NDArray[np.float32],
    action: BasketballAction,
    strict: bool = False,
) -> ValidationResult:
    """
    농구 동작별 자세 검증.

    Args:
        keypoints: 키포인트 배열
        action: 농구 동작 유형
        strict: 엄격 모드

    Returns:
        검증 결과
    """
    violations: list[Violation] = []
    joint_angles: dict[str, float] = {}

    # 동작별 관절 각도 범위 가져오기
    action_angles = _get_action_joint_angles(action)
    required_kps = BASKETBALL_KEYPOINT_GROUPS.get(action.name.lower(), frozenset())

    # 필수 키포인트 확인
    conf_idx = 2 if keypoints.shape[1] == 3 else 3
    missing_kps = []

    for kp in required_kps:
        idx = kp.value
        if idx >= len(keypoints) or keypoints[idx, conf_idx] < MIN_CONFIDENCE_FOR_ANGLE:
            missing_kps.append(kp.name)

    if len(missing_kps) > MAX_MISSING_KEYPOINTS:  # MAX_MISSING_KEYPOINTS개 초과 누락 시 검증 불가
        return ValidationResult(
            is_valid=False,
            violations=[Violation(
                violation_type=ViolationType.KEYPOINT_MISSING,
                severity=Severity.ERROR,
                joint_or_part="multiple",
                message=f"필수 키포인트 누락: {', '.join(missing_kps[:5])}...",
            )],
            confidence_score=0.0,
        )

    # 관절 각도 검증
    for joint_name, angle_range in action_angles.items():
        result = get_joint_angle(keypoints, joint_name)

        if not result.valid:
            continue

        joint_angles[joint_name] = result.angle

        # 범위 검사
        if not angle_range.is_valid(result.angle):
            severity = Severity.ERROR if strict else Severity.WARNING
            violations.append(Violation(
                violation_type=ViolationType.BASKETBALL_POSE_INVALID,
                severity=severity,
                joint_or_part=joint_name,
                message=f"{action.name} 자세 부적합: {joint_name}",
                expected=f"{angle_range.min_angle:.1f}° - {angle_range.max_angle:.1f}°",
                actual=result.angle,
            ))
        elif not angle_range.is_optimal(result.angle):
            violations.append(Violation(
                violation_type=ViolationType.BASKETBALL_POSE_INVALID,
                severity=Severity.INFO,
                joint_or_part=joint_name,
                message=f"{action.name} 자세 개선 권장: {joint_name}",
                expected=f"최적: {angle_range.optimal_min:.1f}° - {angle_range.optimal_max:.1f}°",
                actual=result.angle,
            ))

    # 결과 계산
    error_count = sum(1 for v in violations if v.severity == Severity.ERROR)
    warning_count = sum(1 for v in violations if v.severity == Severity.WARNING)

    is_valid = error_count == 0
    confidence = 1.0 - (error_count * 0.2) - (warning_count * 0.05)
    confidence = max(0.0, min(1.0, confidence))

    return ValidationResult(
        is_valid=is_valid,
        violations=violations,
        joint_angles=joint_angles,
        confidence_score=confidence,
        message=f"{action.name} 자세 검증: {'통과' if is_valid else '미통과'}",
    )


_ACTION_JOINT_ANGLES_MAP: dict[BasketballAction, dict[str, JointAngleRange]] = {
    BasketballAction.SHOOTING: SHOOTING_JOINT_ANGLES,
    BasketballAction.DRIBBLING: DRIBBLING_JOINT_ANGLES,
    BasketballAction.DEFENSE: DEFENSIVE_JOINT_ANGLES,
    BasketballAction.JUMPING: JUMPING_JOINT_ANGLES,
    BasketballAction.REBOUNDING: JUMPING_JOINT_ANGLES,  # 점프와 유사
    BasketballAction.PASSING: SHOOTING_JOINT_ANGLES,  # 슈팅과 유사
    BasketballAction.PIVOT: DRIBBLING_JOINT_ANGLES,  # 드리블과 유사
}


def _get_action_joint_angles(action: BasketballAction) -> dict[str, JointAngleRange]:
    """동작별 관절 각도 범위 반환."""
    return _ACTION_JOINT_ANGLES_MAP.get(action, {})


def is_pose_anatomically_valid(
    keypoints: NDArray[np.float32],
    strict: bool = False,
) -> bool:
    """
    포즈 해부학적 유효성 간단 확인.

    Args:
        keypoints: 키포인트 배열
        strict: 엄격 모드

    Returns:
        유효 여부
    """
    level = ValidationLevel.STRICT if strict else ValidationLevel.STANDARD
    result = validate_anatomical_constraints(keypoints, level=level)
    return result.is_valid


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # =========================================================================
    # 설정 상수
    # =========================================================================
    "CONFIG_KEY_POSE_VALIDATOR",
    "MIN_CONFIDENCE_FOR_ANGLE",
    "MAX_MISSING_KEYPOINTS",

    # =========================================================================
    # 열거형
    # =========================================================================
    "ValidationLevel",
    "ViolationType",
    "Severity",
    "JointType",
    "BasketballAction",
    "AgeGroup",
    "Gender",

    # =========================================================================
    # 데이터 클래스
    # =========================================================================
    "JointAngleRange",
    "LimbRatioRange",
    "Violation",
    "AnatomicalConstraints",
    "BasketballPoseConstraints",
    "ValidationResult",
    "AngleResult",

    # =========================================================================
    # 핵심 함수
    # =========================================================================
    "validate_anatomical_constraints",
    "check_joint_angle_range",
    "check_limb_length_ratio",
    "validate_basketball_pose",
    "is_pose_anatomically_valid",

    # =========================================================================
    # 관절 각도 함수
    # =========================================================================
    "get_joint_angle",
    "get_joint_angle_3d",
    "get_all_joint_angles",

    # =========================================================================
    # 농구 동작별 관절 각도 상수
    # =========================================================================
    "SHOOTING_JOINT_ANGLES",
    "DRIBBLING_JOINT_ANGLES",
    "DEFENSIVE_JOINT_ANGLES",
    "JUMPING_JOINT_ANGLES",

    # =========================================================================
    # 관절 각도 범위 (해부학적 제한)
    # =========================================================================
    "JOINT_ANGLE_LIMITS",
    "BODY_SEGMENT_RATIOS",

    # =========================================================================
    # 연령/성별 조정
    # =========================================================================
    "AGE_GROUP_ADJUSTMENTS",
    "GENDER_ADJUSTMENTS",
]

__version__ = "1.0.0"
