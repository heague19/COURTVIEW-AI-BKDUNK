# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: joint_angle_calculator.py
설명: 관절 각도 계산 모듈
      - 3D 키포인트로부터 관절 각도 산출 (벡터 내적 기반)
      - ACSM ROM 기준 유효성 검증
      - 농구 동작별 최적 범위 비교
      - 연령/성별 보정 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement.
    - ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.
    - Okazaki, V.H.A. & Rodacki, A.L.F. (2012). Basketball jump shot kinematics.
    - 3D 관절 각도: 두 벡터 사이 각도 θ = arccos(A·B / |A||B|)

의존성:
    - shared/constants/pose_constants.py: JointType, JOINT_CONFIDENCE_THRESHOLD
    - shared/constants/biomechanics_constants.py: JOINT_ROM_NORMAL, SHOOTING_OPTIMAL_ANGLES,
      DEFENSIVE_STANCE_ANGLES, DRIBBLING_STANCE_ANGLES, JUMP_LANDING_ANGLES
    - shared/constants/player_constants.py: AgeGroup, Gender

사용처:
    - biomechanics/kinematics/velocity_analyzer.py: 각속도 계산 시 프레임 간 각도 변화 참조
    - biomechanics/kinematics/body_orientation.py: 체간 각도 기반 자세 추정
    - biomechanics/kinematics/motion_pattern.py: 동작 패턴 분류 시 각도 조합 참조
    - biomechanics/dynamics/: 토크 계산 시 관절 각도 필요
    - motion_analysis/form_evaluation/: 동작 폼 평가 시 각도 참조
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    AGE_ANGLE_TOLERANCE,
    JOINT_ROM_NORMAL,
    SHOOTING_OPTIMAL_ANGLES,
    DEFENSIVE_STANCE_ANGLES,
    DRIBBLING_STANCE_ANGLES,
    JUMP_LANDING_ANGLES,
)
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.pose_constants import (
    JointType,
    UK25_R_SHOULDER as _KP_R_SHOULDER,
    UK25_R_ELBOW as _KP_R_ELBOW,
    UK25_R_WRIST as _KP_R_WRIST,
    UK25_L_SHOULDER as _KP_L_SHOULDER,
    UK25_L_ELBOW as _KP_L_ELBOW,
    UK25_L_WRIST as _KP_L_WRIST,
    UK25_R_HIP as _KP_R_HIP,
    UK25_R_KNEE as _KP_R_KNEE,
    UK25_R_ANKLE as _KP_R_ANKLE,
    UK25_L_HIP as _KP_L_HIP,
    UK25_L_KNEE as _KP_L_KNEE,
    UK25_L_ANKLE as _KP_L_ANKLE,
)


def get_adjusted_angle_range(
    optimal_range: tuple[float, float],
    age_group: AgeGroup = AgeGroup.ADULT,
) -> tuple[float, float]:
    """연령대별 tolerance 적용된 각도 범위 반환 (도)."""
    tolerance = AGE_ANGLE_TOLERANCE.get(age_group, 0.0)
    lo = max(0.0, optimal_range[0] - tolerance)
    hi = min(180.0, optimal_range[1] + tolerance)
    return (lo, hi)


# =============================================================================
# 상수
# =============================================================================

# 벡터 크기 최소 임계치 (0-벡터 방지)
_MIN_VECTOR_NORM: Final[float] = 1e-8

# 신뢰도 임계치 (이 값 미만이면 해당 키포인트 무시)
_MIN_CONFIDENCE: Final[float] = 0.3

# 각도 유효 범위 (물리적으로 불가능한 값 필터링)
_MIN_ANGLE_DEG: Final[float] = 0.0
_MAX_ANGLE_DEG: Final[float] = 180.0

# Unified 25kp 키포인트 인덱스 (SSOT: shared.constants.pose_constants)

# 관절 각도 계산용 삼중점 정의: (proximal, joint, distal)
# 각도 = proximal-joint-distal 꼭지점에서의 각도
_JOINT_TRIPLETS: Final[dict[JointType, tuple[int, int, int]]] = {
    # 어깨: 엉덩이 → 어깨 → 팔꿈치
    JointType.LEFT_SHOULDER: (_KP_L_HIP, _KP_L_SHOULDER, _KP_L_ELBOW),
    JointType.RIGHT_SHOULDER: (_KP_R_HIP, _KP_R_SHOULDER, _KP_R_ELBOW),
    # 팔꿈치: 어깨 → 팔꿈치 → 손목
    JointType.LEFT_ELBOW: (_KP_L_SHOULDER, _KP_L_ELBOW, _KP_L_WRIST),
    JointType.RIGHT_ELBOW: (_KP_R_SHOULDER, _KP_R_ELBOW, _KP_R_WRIST),
    # 엉덩이: 어깨 → 엉덩이 → 무릎
    JointType.LEFT_HIP: (_KP_L_SHOULDER, _KP_L_HIP, _KP_L_KNEE),
    JointType.RIGHT_HIP: (_KP_R_SHOULDER, _KP_R_HIP, _KP_R_KNEE),
    # 무릎: 엉덩이 → 무릎 → 발목
    JointType.LEFT_KNEE: (_KP_L_HIP, _KP_L_KNEE, _KP_L_ANKLE),
    JointType.RIGHT_KNEE: (_KP_R_HIP, _KP_R_KNEE, _KP_R_ANKLE),
}

# JointType → JOINT_ROM_NORMAL 키 매핑
_JOINT_ROM_KEYS: Final[dict[JointType, str]] = {
    JointType.LEFT_SHOULDER: "shoulder_flexion",
    JointType.RIGHT_SHOULDER: "shoulder_flexion",
    JointType.LEFT_ELBOW: "elbow_flexion",
    JointType.RIGHT_ELBOW: "elbow_flexion",
    JointType.LEFT_HIP: "hip_flexion",
    JointType.RIGHT_HIP: "hip_flexion",
    JointType.LEFT_KNEE: "knee_flexion",
    JointType.RIGHT_KNEE: "knee_flexion",
}


# =============================================================================
# 관절 각도 결과 데이터클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class JointAngle:
    """
    단일 관절 각도 측정 결과.

    Attributes:
        joint_type: 관절 유형 (JointType)
        angle_deg: 관절 각도 (도, 0~180)
        confidence: 측정 신뢰도 (0~1, 구성 키포인트의 최소 신뢰도)
        is_within_rom: ACSM ROM 범위 내 여부
    """

    joint_type: JointType
    angle_deg: float
    confidence: float
    is_within_rom: bool


@dataclass(frozen=True, slots=True)
class FrameAngles:
    """
    프레임 단위 전체 관절 각도 결과.

    Attributes:
        angles: 관절별 각도 매핑
        valid_count: 유효하게 계산된 관절 수
        total_joints: 계산 대상 관절 수
    """

    angles: dict[JointType, JointAngle]
    valid_count: int
    total_joints: int

    @property
    def completeness(self) -> float:
        """유효 관절 비율 (0~1)."""
        if self.total_joints == 0:
            return 0.0
        return self.valid_count / self.total_joints

    def get_angle(self, joint_type: JointType) -> float | None:
        """특정 관절 각도 반환 (없으면 None)."""
        angle = self.angles.get(joint_type)
        if angle is None:
            return None
        return angle.angle_deg


@dataclass(frozen=True, slots=True)
class AngleDeviation:
    """
    관절 각도의 기준 범위 대비 편차.

    Attributes:
        joint_key: 동작별 기준키 (예: "release_elbow_angle")
        measured_deg: 측정 각도
        optimal_min: 기준 최소
        optimal_max: 기준 최대
        deviation_deg: 편차 (범위 내이면 0, 범위 밖이면 가장 가까운 경계와의 차이)
        within_range: 기준 범위 내 여부
    """

    joint_key: str
    measured_deg: float
    optimal_min: float
    optimal_max: float
    deviation_deg: float
    within_range: bool


# =============================================================================
# 핵심 각도 계산 함수
# =============================================================================

def _compute_angle_3d(
    p_proximal: NDArray[np.float64],
    p_joint: NDArray[np.float64],
    p_distal: NDArray[np.float64],
) -> float:
    """
    3D 공간에서 세 점이 이루는 관절 각도 계산.

    벡터 내적 공식: θ = arccos( (A·B) / (|A|·|B|) )
    A = proximal - joint, B = distal - joint

    Args:
        p_proximal: 근위 관절 좌표 (3,)
        p_joint: 중심 관절 좌표 (3,)
        p_distal: 원위 관절 좌표 (3,)

    Returns:
        관절 각도 (도, 0~180)

    참조:
        Winter (2009) Ch.2: 2D and 3D kinematics
    """
    vec_a = p_proximal - p_joint
    vec_b = p_distal - p_joint

    # NaN/Inf guard — 키포인트에 비유효 값 포함 시 0 반환
    if not (np.all(np.isfinite(vec_a)) and np.all(np.isfinite(vec_b))):
        return 0.0

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a < _MIN_VECTOR_NORM or norm_b < _MIN_VECTOR_NORM:
        return 0.0

    cos_theta = np.dot(vec_a, vec_b) / (norm_a * norm_b)
    if not np.isfinite(cos_theta):
        return 0.0
    # 수치 안정성: [-1, 1] 클램핑
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))

    return math.degrees(math.acos(cos_theta))


def _get_keypoint_confidence(
    keypoints: NDArray[np.float64],
    idx: int,
) -> float:
    """
    키포인트의 신뢰도 추출.

    Args:
        keypoints: 키포인트 배열 (N×3 또는 N×4, 4번째 열이 신뢰도)
        idx: 키포인트 인덱스

    Returns:
        신뢰도 (0~1). 신뢰도 열이 없으면 1.0 반환.
    """
    if idx < 0 or idx >= keypoints.shape[0]:
        return 0.0

    if keypoints.shape[1] >= 4:
        return float(keypoints[idx, 3])
    return 1.0


def _is_valid_keypoint(
    keypoints: NDArray[np.float64],
    idx: int,
    min_confidence: float = _MIN_CONFIDENCE,
) -> bool:
    """키포인트 유효성 검증 (범위 + 신뢰도)."""
    if idx < 0 or idx >= keypoints.shape[0]:
        return False
    conf = _get_keypoint_confidence(keypoints, idx)
    return conf >= min_confidence


def _check_rom(joint_type: JointType, angle_deg: float) -> bool:
    """
    ACSM ROM 기준 유효성 검증.

    Args:
        joint_type: 관절 유형
        angle_deg: 측정 각도 (도)

    Returns:
        ROM 범위 내 여부
    """
    rom_key = _JOINT_ROM_KEYS.get(joint_type)
    if rom_key is None:
        # ROM 데이터 미정의 관절은 물리적 범위(0~180)만 검증
        return _MIN_ANGLE_DEG <= angle_deg <= _MAX_ANGLE_DEG

    rom_range = JOINT_ROM_NORMAL.get(rom_key)
    if rom_range is None:
        return _MIN_ANGLE_DEG <= angle_deg <= _MAX_ANGLE_DEG

    return rom_range[0] <= angle_deg <= rom_range[1]


# =============================================================================
# 공개 함수: 관절 각도 계산
# =============================================================================

def calculate_joint_angle(
    keypoints_3d: NDArray[np.float64],
    joint_type: JointType,
) -> JointAngle | None:
    """
    단일 관절 각도 계산.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)
        joint_type: 계산 대상 관절

    Returns:
        JointAngle 객체 (계산 불가 시 None)
    """
    triplet = _JOINT_TRIPLETS.get(joint_type)
    if triplet is None:
        return None

    prox_idx, joint_idx, dist_idx = triplet

    # 세 키포인트 모두 유효한지 검증
    if not all(
        _is_valid_keypoint(keypoints_3d, idx)
        for idx in (prox_idx, joint_idx, dist_idx)
    ):
        return None

    # 3D 좌표 추출 (처음 3열만)
    p_proximal = keypoints_3d[prox_idx, :3].astype(np.float64)
    p_joint = keypoints_3d[joint_idx, :3].astype(np.float64)
    p_distal = keypoints_3d[dist_idx, :3].astype(np.float64)

    angle_deg = _compute_angle_3d(p_proximal, p_joint, p_distal)

    # 신뢰도: 세 키포인트 중 최소값
    confidence = min(
        _get_keypoint_confidence(keypoints_3d, prox_idx),
        _get_keypoint_confidence(keypoints_3d, joint_idx),
        _get_keypoint_confidence(keypoints_3d, dist_idx),
    )

    is_valid = _check_rom(joint_type, angle_deg)

    return JointAngle(
        joint_type=joint_type,
        angle_deg=angle_deg,
        confidence=confidence,
        is_within_rom=is_valid,
    )


def calculate_all_joint_angles(
    keypoints_3d: NDArray[np.float64],
) -> FrameAngles:
    """
    프레임 내 모든 관절 각도 일괄 계산.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        FrameAngles 객체
    """
    angles: dict[JointType, JointAngle] = {}
    total = len(_JOINT_TRIPLETS)

    for joint_type in _JOINT_TRIPLETS:
        result = calculate_joint_angle(keypoints_3d, joint_type)
        if result is not None:
            angles[joint_type] = result

    return FrameAngles(
        angles=angles,
        valid_count=len(angles),
        total_joints=total,
    )


# =============================================================================
# 체간 각도 계산 (특수 계산)
# =============================================================================

def calculate_trunk_forward_lean(
    keypoints_3d: NDArray[np.float64],
) -> float | None:
    """
    체간 전방 경사각 계산 (도).

    수직축 대비 체간의 전방 기울기.
    양수 = 전방 경사 (수비, 드리블 시 일반적).

    계산: 어깨 중점 → 엉덩이 중점 벡터와 수직축 사이의 각도.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        전방 경사각 (도), 계산 불가 시 None

    참조:
        Knudson (2007) - 농구 수비 자세 분석
    """
    required = [_KP_L_SHOULDER, _KP_R_SHOULDER, _KP_L_HIP, _KP_R_HIP]
    if not all(_is_valid_keypoint(keypoints_3d, idx) for idx in required):
        return None

    shoulder_mid = (
        keypoints_3d[_KP_L_SHOULDER, :3] + keypoints_3d[_KP_R_SHOULDER, :3]
    ) / 2.0
    hip_mid = (
        keypoints_3d[_KP_L_HIP, :3] + keypoints_3d[_KP_R_HIP, :3]
    ) / 2.0

    # 체간 벡터: 엉덩이 → 어깨 (상방향)
    trunk_vec = shoulder_mid - hip_mid
    trunk_norm = np.linalg.norm(trunk_vec)
    if trunk_norm < _MIN_VECTOR_NORM:
        return None

    # 수직축 (양의 Y축 = 위 방향으로 가정)
    vertical = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    cos_theta = float(np.dot(trunk_vec, vertical) / trunk_norm)
    cos_theta = max(-1.0, min(1.0, cos_theta))

    return math.degrees(math.acos(cos_theta))


def calculate_stance_width_ratio(
    keypoints_3d: NDArray[np.float64],
) -> float | None:
    """
    보폭/어깨너비 비율 계산.

    수비 스탠스 평가에서 핵심 지표.
    비율 > 1.0 = 어깨보다 넓은 스탠스.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3 또는 25×4)

    Returns:
        보폭/어깨너비 비율 (무차원), 계산 불가 시 None
    """
    required = [
        _KP_L_SHOULDER, _KP_R_SHOULDER,
        _KP_L_ANKLE, _KP_R_ANKLE,
    ]
    if not all(_is_valid_keypoint(keypoints_3d, idx) for idx in required):
        return None

    shoulder_width = float(np.linalg.norm(
        keypoints_3d[_KP_L_SHOULDER, :3] - keypoints_3d[_KP_R_SHOULDER, :3]
    ))
    ankle_width = float(np.linalg.norm(
        keypoints_3d[_KP_L_ANKLE, :3] - keypoints_3d[_KP_R_ANKLE, :3]
    ))

    if shoulder_width < _MIN_VECTOR_NORM:
        return None

    return ankle_width / shoulder_width


# =============================================================================
# 동작별 최적 범위 비교
# =============================================================================

def _evaluate_against_range(
    measured_deg: float,
    optimal_min: float,
    optimal_max: float,
    joint_key: str,
) -> AngleDeviation:
    """측정값과 기준 범위 비교 → AngleDeviation 생성."""
    if measured_deg < optimal_min:
        deviation = optimal_min - measured_deg
        within = False
    elif measured_deg > optimal_max:
        deviation = measured_deg - optimal_max
        within = False
    else:
        deviation = 0.0
        within = True

    return AngleDeviation(
        joint_key=joint_key,
        measured_deg=measured_deg,
        optimal_min=optimal_min,
        optimal_max=optimal_max,
        deviation_deg=deviation,
        within_range=within,
    )


def evaluate_shooting_angles(
    frame_angles: FrameAngles,
    keypoints_3d: NDArray[np.float64],
    age_group: AgeGroup = AgeGroup.ADULT,
) -> list[AngleDeviation]:
    """
    슈팅 동작 관절 각도 평가.

    측정 관절 각도를 SHOOTING_OPTIMAL_ANGLES 기준과 비교하여
    각 항목의 편차를 산출한다.

    Args:
        frame_angles: 프레임 관절 각도
        keypoints_3d: 3D 키포인트 (체간 경사 계산용)
        age_group: 연령대 (기준 범위 보정)

    Returns:
        AngleDeviation 리스트
    """
    deviations: list[AngleDeviation] = []

    # 관절 각도 키 → (JointType, SHOOTING_OPTIMAL_ANGLES 키) 매핑
    angle_map: dict[str, JointType] = {
        "release_elbow_angle": JointType.RIGHT_ELBOW,
        "set_elbow_angle": JointType.RIGHT_ELBOW,
        "set_knee_flexion": JointType.RIGHT_KNEE,
        "release_shoulder_flexion": JointType.RIGHT_SHOULDER,
        "set_shoulder_flexion": JointType.RIGHT_SHOULDER,
        "followthrough_elbow_angle": JointType.RIGHT_ELBOW,
    }

    for key, joint_type in angle_map.items():
        optimal = SHOOTING_OPTIMAL_ANGLES.get(key)
        if optimal is None:
            continue

        measured = frame_angles.get_angle(joint_type)
        if measured is None:
            continue

        adjusted = get_adjusted_angle_range(optimal, age_group)
        deviations.append(
            _evaluate_against_range(measured, adjusted[0], adjusted[1], key)
        )

    # 체간 경사 (set_hip_flexion 대리 지표)
    trunk_lean = calculate_trunk_forward_lean(keypoints_3d)
    if trunk_lean is not None:
        hip_key = "set_hip_flexion"
        hip_optimal = SHOOTING_OPTIMAL_ANGLES.get(hip_key)
        if hip_optimal is not None:
            adjusted = get_adjusted_angle_range(hip_optimal, age_group)
            deviations.append(
                _evaluate_against_range(trunk_lean, adjusted[0], adjusted[1], hip_key)
            )

    return deviations


def evaluate_defensive_stance(
    frame_angles: FrameAngles,
    keypoints_3d: NDArray[np.float64],
    age_group: AgeGroup = AgeGroup.ADULT,
) -> list[AngleDeviation]:
    """
    수비 자세 관절 각도 평가.

    Args:
        frame_angles: 프레임 관절 각도
        keypoints_3d: 3D 키포인트
        age_group: 연령대

    Returns:
        AngleDeviation 리스트
    """
    deviations: list[AngleDeviation] = []

    # 무릎 굽힘 (좌우 평균)
    left_knee = frame_angles.get_angle(JointType.LEFT_KNEE)
    right_knee = frame_angles.get_angle(JointType.RIGHT_KNEE)
    if left_knee is not None and right_knee is not None:
        avg_knee = (left_knee + right_knee) / 2.0
        optimal = DEFENSIVE_STANCE_ANGLES["knee_flexion"]
        adjusted = get_adjusted_angle_range(optimal, age_group)
        deviations.append(
            _evaluate_against_range(avg_knee, adjusted[0], adjusted[1], "knee_flexion")
        )

    # 엉덩이 굽힘 (좌우 평균)
    left_hip = frame_angles.get_angle(JointType.LEFT_HIP)
    right_hip = frame_angles.get_angle(JointType.RIGHT_HIP)
    if left_hip is not None and right_hip is not None:
        avg_hip = (left_hip + right_hip) / 2.0
        optimal = DEFENSIVE_STANCE_ANGLES["hip_flexion"]
        adjusted = get_adjusted_angle_range(optimal, age_group)
        deviations.append(
            _evaluate_against_range(avg_hip, adjusted[0], adjusted[1], "hip_flexion")
        )

    # 체간 전방 경사
    trunk_lean = calculate_trunk_forward_lean(keypoints_3d)
    if trunk_lean is not None:
        optimal = DEFENSIVE_STANCE_ANGLES["trunk_forward_lean"]
        adjusted = get_adjusted_angle_range(optimal, age_group)
        deviations.append(
            _evaluate_against_range(
                trunk_lean, adjusted[0], adjusted[1], "trunk_forward_lean"
            )
        )

    # 보폭/어깨너비 비율 (비율이므로 연령 보정 미적용)
    stance_ratio = calculate_stance_width_ratio(keypoints_3d)
    if stance_ratio is not None:
        optimal = DEFENSIVE_STANCE_ANGLES["stance_width_shoulder_ratio"]
        deviations.append(
            _evaluate_against_range(
                stance_ratio, optimal[0], optimal[1], "stance_width_shoulder_ratio"
            )
        )

    return deviations


def evaluate_dribbling_stance(
    frame_angles: FrameAngles,
    keypoints_3d: NDArray[np.float64],
    age_group: AgeGroup = AgeGroup.ADULT,
) -> list[AngleDeviation]:
    """
    드리블 자세 관절 각도 평가.

    Args:
        frame_angles: 프레임 관절 각도
        keypoints_3d: 3D 키포인트
        age_group: 연령대

    Returns:
        AngleDeviation 리스트
    """
    deviations: list[AngleDeviation] = []

    # 무릎/엉덩이 (좌우 평균)
    for key, left_jt, right_jt in [
        ("knee_flexion", JointType.LEFT_KNEE, JointType.RIGHT_KNEE),
        ("hip_flexion", JointType.LEFT_HIP, JointType.RIGHT_HIP),
    ]:
        left_angle = frame_angles.get_angle(left_jt)
        right_angle = frame_angles.get_angle(right_jt)
        if left_angle is not None and right_angle is not None:
            avg = (left_angle + right_angle) / 2.0
            optimal = DRIBBLING_STANCE_ANGLES.get(key)
            if optimal is not None:
                adjusted = get_adjusted_angle_range(optimal, age_group)
                deviations.append(
                    _evaluate_against_range(avg, adjusted[0], adjusted[1], key)
                )

    # 드리블 손 어깨/팔꿈치 (우측 우선, 좌측 대체)
    for key, jt_r, jt_l in [
        ("shoulder_flexion", JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER),
        ("elbow_angle", JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW),
    ]:
        angle = frame_angles.get_angle(jt_r) or frame_angles.get_angle(jt_l)
        if angle is not None:
            optimal = DRIBBLING_STANCE_ANGLES.get(key)
            if optimal is not None:
                adjusted = get_adjusted_angle_range(optimal, age_group)
                deviations.append(
                    _evaluate_against_range(angle, adjusted[0], adjusted[1], key)
                )

    # 체간 전방 경사
    trunk_lean = calculate_trunk_forward_lean(keypoints_3d)
    if trunk_lean is not None:
        optimal = DRIBBLING_STANCE_ANGLES.get("trunk_forward_lean")
        if optimal is not None:
            adjusted = get_adjusted_angle_range(optimal, age_group)
            deviations.append(
                _evaluate_against_range(
                    trunk_lean, adjusted[0], adjusted[1], "trunk_forward_lean"
                )
            )

    return deviations


def evaluate_jump_landing(
    frame_angles: FrameAngles,
    age_group: AgeGroup = AgeGroup.ADULT,
) -> list[AngleDeviation]:
    """
    점프/착지 관절 각도 평가.

    부상 예방 관점에서 착지 시 무릎/엉덩이 각도를 JUMP_LANDING_ANGLES 기준과 비교.

    Args:
        frame_angles: 프레임 관절 각도
        age_group: 연령대

    Returns:
        AngleDeviation 리스트
    """
    deviations: list[AngleDeviation] = []

    # 착지 무릎 굽힘 (좌우 평균)
    left_knee = frame_angles.get_angle(JointType.LEFT_KNEE)
    right_knee = frame_angles.get_angle(JointType.RIGHT_KNEE)
    if left_knee is not None and right_knee is not None:
        avg_knee = (left_knee + right_knee) / 2.0

        for key in ("landing_knee_flexion", "landing_knee_flexion_peak"):
            optimal = JUMP_LANDING_ANGLES.get(key)
            if optimal is not None:
                adjusted = get_adjusted_angle_range(optimal, age_group)
                deviations.append(
                    _evaluate_against_range(avg_knee, adjusted[0], adjusted[1], key)
                )

    # 이륙/착지 엉덩이 (좌우 평균)
    left_hip = frame_angles.get_angle(JointType.LEFT_HIP)
    right_hip = frame_angles.get_angle(JointType.RIGHT_HIP)
    if left_hip is not None and right_hip is not None:
        avg_hip = (left_hip + right_hip) / 2.0

        for key in ("takeoff_hip_flexion", "landing_hip_flexion"):
            optimal = JUMP_LANDING_ANGLES.get(key)
            if optimal is not None:
                adjusted = get_adjusted_angle_range(optimal, age_group)
                deviations.append(
                    _evaluate_against_range(avg_hip, adjusted[0], adjusted[1], key)
                )

    return deviations


# =============================================================================
# 편의 함수
# =============================================================================

def get_bilateral_difference(
    frame_angles: FrameAngles,
    joint_name: str,
) -> float | None:
    """
    좌우 대칭 관절의 각도 차이 반환.

    Args:
        frame_angles: 프레임 관절 각도
        joint_name: 관절명 ("shoulder", "elbow", "hip", "knee")

    Returns:
        |좌 - 우| (도), 어느 쪽이든 없으면 None
    """
    mapping: dict[str, tuple[JointType, JointType]] = {
        "shoulder": (JointType.LEFT_SHOULDER, JointType.RIGHT_SHOULDER),
        "elbow": (JointType.LEFT_ELBOW, JointType.RIGHT_ELBOW),
        "hip": (JointType.LEFT_HIP, JointType.RIGHT_HIP),
        "knee": (JointType.LEFT_KNEE, JointType.RIGHT_KNEE),
    }

    pair = mapping.get(joint_name)
    if pair is None:
        return None

    left = frame_angles.get_angle(pair[0])
    right = frame_angles.get_angle(pair[1])
    if left is None or right is None:
        return None

    return abs(left - right)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "JointAngle",
    "FrameAngles",
    "AngleDeviation",
    # 핵심 함수
    "calculate_joint_angle",
    "calculate_all_joint_angles",
    # 체간 특수 계산
    "calculate_trunk_forward_lean",
    "calculate_stance_width_ratio",
    # 동작별 평가
    "evaluate_shooting_angles",
    "evaluate_defensive_stance",
    "evaluate_dribbling_stance",
    "evaluate_jump_landing",
    # 편의 함수
    "get_bilateral_difference",
]

__version__ = "1.0.0"
