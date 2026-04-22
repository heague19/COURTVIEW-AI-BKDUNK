# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: pose_utils.py
설명: 포즈/스켈레톤 처리 유틸리티
      - 스켈레톤 정규화, 필터링, numpy 변환
      - 운동학 체인 (부모-자식, 팔다리 벡터, 무게중심)
      - 관절 속도/가속도/저크 추정
      - 포즈 비교 (OKS, Procrustes, 거리 메트릭)
      - 신체 방향 (정면, 기울기, 경사)
      - 시계열 연산 (윈도잉, 부드러움, 키프레임)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - skeleton_to_numpy / numpy_to_keypoints: DTO ↔ NDArray 변환
    - normalize_skeleton_scale: 스케일 불변 정규화 (엉덩이 중심, 몸통 길이)
    - filter_keypoints_by_confidence: 신뢰도 기반 필터링
    - interpolate_missing_keypoints: 누락 키포인트 선형 보간
    - mirror_skeleton: 좌우 대칭 (좌우 반전 데이터 증강)
    - KINEMATIC_PARENT_MAP / get_limb_vector: 운동학 체인
    - calculate_keypoint_velocities / accelerations / jerk: 시간 미분
    - oks_similarity / procrustes_align: 포즈 비교
    - estimate_facing_direction / body_tilt / lateral_lean: 방향 분석
    - extract_temporal_window / motion_smoothness: 시계열 분석

사용 예시:
    >>> from utils.pose_utils import skeleton_to_numpy, normalize_skeleton_scale
    >>> import numpy as np
    >>> kps = np.random.rand(17, 3)  # x, y, confidence
    >>> kps_norm = normalize_skeleton_scale(kps, method="hip_center")
    >>> kps_norm.shape
    (17, 3)
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import math
from dataclasses import dataclass, field
from enum import Enum, unique

# === 서드파티 라이브러리 ===
import numpy as np
from numpy.typing import NDArray

# === 로거 설정 ===
import logging

logger = logging.getLogger(__name__)


# === 상수 정의 ===

# 부동소수점 임계값
_EPSILON: float = 1e-10

# 기본 신뢰도 임계값 (pose_constants.JOINT_CONFIDENCE_THRESHOLD와 동일)
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5

# 높은 신뢰도 임계값
HIGH_CONFIDENCE_THRESHOLD: float = 0.7

# COCO 키포인트 수
COCO_NUM_KEYPOINTS: int = 17

# 최대 시퀀스 길이 (메모리 보호)
_MAX_SEQUENCE_LENGTH: int = 100_000

# OKS 시그마 (COCO 기준, 키포인트별 표준편차)
OKS_SIGMAS: tuple[float, ...] = (
    0.026,  # 코
    0.025,  # 왼쪽 눈
    0.025,  # 오른쪽 눈
    0.035,  # 왼쪽 귀
    0.035,  # 오른쪽 귀
    0.079,  # 왼쪽 어깨
    0.079,  # 오른쪽 어깨
    0.072,  # 왼쪽 팔꿈치
    0.072,  # 오른쪽 팔꿈치
    0.062,  # 왼쪽 손목
    0.062,  # 오른쪽 손목
    0.107,  # 왼쪽 엉덩이
    0.107,  # 오른쪽 엉덩이
    0.087,  # 왼쪽 무릎
    0.087,  # 오른쪽 무릎
    0.089,  # 왼쪽 발목
    0.089,  # 오른쪽 발목
)

# COCO 스켈레톤 연결 (bone pairs)
SKELETON_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (0, 2),          # 코 → 눈
    (1, 3), (2, 4),          # 눈 → 귀
    (5, 6),                  # 어깨 연결
    (5, 7), (7, 9),          # 왼쪽 팔
    (6, 8), (8, 10),         # 오른쪽 팔
    (5, 11), (6, 12),        # 어깨 → 엉덩이
    (11, 12),                # 엉덩이 연결
    (11, 13), (13, 15),      # 왼쪽 다리
    (12, 14), (14, 16),      # 오른쪽 다리
)

# 키포인트 인덱스 (COCO 기준)
KP_NOSE: int = 0
KP_LEFT_EYE: int = 1
KP_RIGHT_EYE: int = 2
KP_LEFT_EAR: int = 3
KP_RIGHT_EAR: int = 4
KP_LEFT_SHOULDER: int = 5
KP_RIGHT_SHOULDER: int = 6
KP_LEFT_ELBOW: int = 7
KP_RIGHT_ELBOW: int = 8
KP_LEFT_WRIST: int = 9
KP_RIGHT_WRIST: int = 10
KP_LEFT_HIP: int = 11
KP_RIGHT_HIP: int = 12
KP_LEFT_KNEE: int = 13
KP_RIGHT_KNEE: int = 14
KP_LEFT_ANKLE: int = 15
KP_RIGHT_ANKLE: int = 16

# 좌우 대칭 매핑 (좌 → 우, 우 → 좌)
_MIRROR_MAP: dict[int, int] = {
    0: 0,   # 코 (중앙)
    1: 2, 2: 1,   # 눈
    3: 4, 4: 3,   # 귀
    5: 6, 6: 5,   # 어깨
    7: 8, 8: 7,   # 팔꿈치
    9: 10, 10: 9,  # 손목
    11: 12, 12: 11,  # 엉덩이
    13: 14, 14: 13,  # 무릎
    15: 16, 16: 15,  # 발목
}


# === Enum 정의 ===

@unique
class NormalizationMethod(Enum):
    """스켈레톤 정규화 방법."""

    HIP_CENTER = "hip_center"      # 엉덩이 중심을 원점으로
    TORSO_LENGTH = "torso_length"  # 몸통 길이로 스케일 정규화
    SHOULDER_CENTER = "shoulder_center"  # 어깨 중심을 원점으로
    BBOX = "bbox"                  # 바운딩 박스 기준 정규화


@unique
class SmoothingMethod(Enum):
    """시계열 스무딩 방법."""

    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"


@unique
class BodyPart(Enum):
    """신체 부위 그룹."""

    HEAD = "head"
    TORSO = "torso"
    LEFT_ARM = "left_arm"
    RIGHT_ARM = "right_arm"
    LEFT_LEG = "left_leg"
    RIGHT_LEG = "right_leg"


# === 데이터 클래스 ===

@dataclass(slots=True)
class SkeletonMetrics:
    """
    스켈레톤 메트릭 (통계 요약).

    Attributes:
        completeness: 유효 키포인트 비율 (0~1)
        avg_confidence: 평균 신뢰도
        num_valid: 유효 키포인트 수
        num_total: 전체 키포인트 수
        torso_length: 몸통 길이 (어깨중심→엉덩이중심)
        bbox_area: 바운딩 박스 면적
    """

    completeness: float = 0.0
    avg_confidence: float = 0.0
    num_valid: int = 0
    num_total: int = 0
    torso_length: float = 0.0
    bbox_area: float = 0.0

    def __repr__(self) -> str:
        return (
            f"SkeletonMetrics(완전성={self.completeness:.2%}, "
            f"평균신뢰도={self.avg_confidence:.3f}, "
            f"유효={self.num_valid}/{self.num_total})"
        )


@dataclass(slots=True)
class ProcrustesResult:
    """
    Procrustes 정렬 결과.

    Attributes:
        aligned: 정렬된 스켈레톤 (N, 2) 또는 (N, 3)
        scale: 스케일링 계수
        rotation: 회전 행렬 (2, 2) 또는 (3, 3)
        translation: 이동 벡터
        disparity: 잔차 (정렬 후 차이)
    """

    aligned: NDArray[np.float64] = field(
        default_factory=lambda: np.empty(0, dtype=np.float64)
    )
    scale: float = 1.0
    rotation: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(2, dtype=np.float64)
    )
    translation: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(2, dtype=np.float64)
    )
    disparity: float = 0.0

    def __repr__(self) -> str:
        return (
            f"ProcrustesResult(scale={self.scale:.4f}, "
            f"disparity={self.disparity:.6f})"
        )


@dataclass(slots=True)
class MotionSmoothness:
    """
    모션 부드러움 측정 결과.

    Attributes:
        smoothness: 전체 부드러움 점수 (0~1, 1이 가장 부드러움)
        jerk_rms: 저크 RMS (작을수록 부드러움)
        velocity_std: 속도 표준편차
        acceleration_std: 가속도 표준편차
    """

    smoothness: float = 0.0
    jerk_rms: float = 0.0
    velocity_std: float = 0.0
    acceleration_std: float = 0.0

    def __repr__(self) -> str:
        return (
            f"MotionSmoothness(부드러움={self.smoothness:.4f}, "
            f"jerk_rms={self.jerk_rms:.4f})"
        )


@dataclass(slots=True)
class BodyOrientation:
    """
    신체 방향 분석 결과.

    Attributes:
        facing_angle: 정면 방향 각도 (도, 0=오른쪽, 90=위, 반시계)
        tilt_forward: 전후 기울기 (도, 양수=앞으로)
        tilt_lateral: 좌우 기울기 (도, 양수=오른쪽)
        shoulder_angle: 어깨 라인 각도 (도, 수평 기준)
        hip_angle: 엉덩이 라인 각도 (도, 수평 기준)
    """

    facing_angle: float = 0.0
    tilt_forward: float = 0.0
    tilt_lateral: float = 0.0
    shoulder_angle: float = 0.0
    hip_angle: float = 0.0

    def __repr__(self) -> str:
        return (
            f"BodyOrientation(정면={self.facing_angle:.1f}°, "
            f"전후={self.tilt_forward:.1f}°, 좌우={self.tilt_lateral:.1f}°)"
        )


# =============================================================================
# 운동학 체인 정의 (COCO 기준)
# =============================================================================

# 부모 관절 매핑 (root = None)
KINEMATIC_PARENT_MAP: dict[int, int | None] = {
    KP_NOSE: None,              # 코 (루트)
    KP_LEFT_EYE: KP_NOSE,      # 왼쪽 눈 → 코
    KP_RIGHT_EYE: KP_NOSE,     # 오른쪽 눈 → 코
    KP_LEFT_EAR: KP_LEFT_EYE,  # 왼쪽 귀 → 왼쪽 눈
    KP_RIGHT_EAR: KP_RIGHT_EYE,  # 오른쪽 귀 → 오른쪽 눈
    KP_LEFT_SHOULDER: KP_NOSE,  # 왼쪽 어깨 → 코 (몸통 경유)
    KP_RIGHT_SHOULDER: KP_NOSE,  # 오른쪽 어깨 → 코
    KP_LEFT_ELBOW: KP_LEFT_SHOULDER,
    KP_RIGHT_ELBOW: KP_RIGHT_SHOULDER,
    KP_LEFT_WRIST: KP_LEFT_ELBOW,
    KP_RIGHT_WRIST: KP_RIGHT_ELBOW,
    KP_LEFT_HIP: KP_LEFT_SHOULDER,   # 왼쪽 엉덩이 → 왼쪽 어깨
    KP_RIGHT_HIP: KP_RIGHT_SHOULDER,
    KP_LEFT_KNEE: KP_LEFT_HIP,
    KP_RIGHT_KNEE: KP_RIGHT_HIP,
    KP_LEFT_ANKLE: KP_LEFT_KNEE,
    KP_RIGHT_ANKLE: KP_RIGHT_KNEE,
}

# 자식 관절 매핑 (부모→자식 역방향)
KINEMATIC_CHILDREN_MAP: dict[int, tuple[int, ...]] = {}
for _child, _parent in KINEMATIC_PARENT_MAP.items():
    if _parent is not None:
        if _parent not in KINEMATIC_CHILDREN_MAP:
            KINEMATIC_CHILDREN_MAP[_parent] = ()
        KINEMATIC_CHILDREN_MAP[_parent] = KINEMATIC_CHILDREN_MAP[_parent] + (_child,)

# 신체 부위별 키포인트 그룹
BODY_PART_KEYPOINTS: dict[BodyPart, tuple[int, ...]] = {
    BodyPart.HEAD: (KP_NOSE, KP_LEFT_EYE, KP_RIGHT_EYE, KP_LEFT_EAR, KP_RIGHT_EAR),
    BodyPart.TORSO: (KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER, KP_LEFT_HIP, KP_RIGHT_HIP),
    BodyPart.LEFT_ARM: (KP_LEFT_SHOULDER, KP_LEFT_ELBOW, KP_LEFT_WRIST),
    BodyPart.RIGHT_ARM: (KP_RIGHT_SHOULDER, KP_RIGHT_ELBOW, KP_RIGHT_WRIST),
    BodyPart.LEFT_LEG: (KP_LEFT_HIP, KP_LEFT_KNEE, KP_LEFT_ANKLE),
    BodyPart.RIGHT_LEG: (KP_RIGHT_HIP, KP_RIGHT_KNEE, KP_RIGHT_ANKLE),
}

# 키포인트 → 신체 부위 역매핑
KEYPOINT_TO_BODY_PART: dict[int, BodyPart] = {}
for _part, _indices in BODY_PART_KEYPOINTS.items():
    for _idx in _indices:
        # 중복 시 더 상위 부위 유지 (어깨/엉덩이는 TORSO에도 포함)
        if _idx not in KEYPOINT_TO_BODY_PART or _part == BodyPart.TORSO:
            KEYPOINT_TO_BODY_PART[_idx] = _part


# =============================================================================
# 스켈레톤 ↔ NDArray 변환
# =============================================================================

def skeleton_to_numpy(
    keypoints: list[tuple[float, float, float]],
) -> NDArray[np.float64]:
    """
    키포인트 리스트를 NDArray로 변환.

    Args:
        keypoints: [(x, y, confidence), ...] 리스트 (N개)

    Returns:
        키포인트 배열 (N, 3) — [x, y, confidence]

    Example:
        >>> kps = [(0.5, 0.3, 0.9), (0.6, 0.4, 0.8)]
        >>> arr = skeleton_to_numpy(kps)
        >>> arr.shape
        (2, 3)
    """
    if not keypoints:
        return np.empty((0, 3), dtype=np.float64)
    return np.array(keypoints, dtype=np.float64)


def skeleton_to_numpy_3d(
    keypoints: list[tuple[float, float, float, float]],
) -> NDArray[np.float64]:
    """
    3D 키포인트 리스트를 NDArray로 변환.

    Args:
        keypoints: [(x, y, z, confidence), ...] 리스트 (N개)

    Returns:
        키포인트 배열 (N, 4) — [x, y, z, confidence]

    Example:
        >>> kps = [(0.5, 0.3, 1.2, 0.9), (0.6, 0.4, 1.1, 0.8)]
        >>> arr = skeleton_to_numpy_3d(kps)
        >>> arr.shape
        (2, 4)
    """
    if not keypoints:
        return np.empty((0, 4), dtype=np.float64)
    return np.array(keypoints, dtype=np.float64)


def numpy_to_keypoints(
    arr: NDArray[np.float64],
) -> list[tuple[float, float, float]]:
    """
    NDArray를 키포인트 튜플 리스트로 변환.

    Args:
        arr: (N, 3) 배열 [x, y, confidence]

    Returns:
        [(x, y, confidence), ...] 리스트

    Example:
        >>> arr = np.array([[0.5, 0.3, 0.9]])
        >>> kps = numpy_to_keypoints(arr)
        >>> kps[0]
        (0.5, 0.3, 0.9)
    """
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0:
        return []
    return [(float(r[0]), float(r[1]), float(r[2])) for r in arr]


# =============================================================================
# 스켈레톤 메트릭 계산
# =============================================================================

def calculate_skeleton_metrics(
    keypoints: NDArray[np.float64],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> SkeletonMetrics:
    """
    스켈레톤 메트릭 계산.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        confidence_threshold: 유효 판정 신뢰도 임계값

    Returns:
        SkeletonMetrics 데이터클래스

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9  # 모두 높은 신뢰도
        >>> m = calculate_skeleton_metrics(kps)
        >>> m.completeness
        1.0
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)
    n = keypoints.shape[0]

    if n == 0:
        return SkeletonMetrics()

    confidences = keypoints[:, 2]
    valid_mask = confidences >= confidence_threshold
    num_valid = int(np.sum(valid_mask))

    # 몸통 길이 (어깨중심 → 엉덩이중심)
    torso_length = 0.0
    if n >= COCO_NUM_KEYPOINTS:
        ls, rs = keypoints[KP_LEFT_SHOULDER, :2], keypoints[KP_RIGHT_SHOULDER, :2]
        lh, rh = keypoints[KP_LEFT_HIP, :2], keypoints[KP_RIGHT_HIP, :2]
        shoulder_c = (ls + rs) / 2.0
        hip_c = (lh + rh) / 2.0
        torso_length = float(np.linalg.norm(shoulder_c - hip_c))

    # 바운딩 박스 면적
    valid_xy = keypoints[valid_mask, :2] if num_valid > 0 else keypoints[:, :2]
    if valid_xy.shape[0] >= 2:
        x_min, y_min = valid_xy.min(axis=0)
        x_max, y_max = valid_xy.max(axis=0)
        bbox_area = float((x_max - x_min) * (y_max - y_min))
    else:
        bbox_area = 0.0

    return SkeletonMetrics(
        completeness=num_valid / n if n > 0 else 0.0,
        avg_confidence=float(np.mean(confidences)),
        num_valid=num_valid,
        num_total=n,
        torso_length=torso_length,
        bbox_area=bbox_area,
    )


# =============================================================================
# 스켈레톤 정규화
# =============================================================================

def normalize_skeleton_scale(
    keypoints: NDArray[np.float64],
    method: str = "hip_center",
) -> NDArray[np.float64]:
    """
    스켈레톤 스케일 불변 정규화.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        method: 정규화 방법
            - "hip_center": 엉덩이 중심 원점, 몸통 길이 1로 정규화
            - "shoulder_center": 어깨 중심 원점
            - "bbox": 바운딩 박스 [0,1] 정규화

    Returns:
        정규화된 (N, 3) 배열

    Example:
        >>> kps = np.random.rand(17, 3) * 100
        >>> kps[:, 2] = 0.9
        >>> kps_n = normalize_skeleton_scale(kps, "hip_center")
        >>> kps_n.shape
        (17, 3)
    """
    keypoints = np.asarray(keypoints, dtype=np.float64).copy()
    n = keypoints.shape[0]

    if n < COCO_NUM_KEYPOINTS:
        logger.warning(f"키포인트 수 부족: {n} < {COCO_NUM_KEYPOINTS}")
        return keypoints

    result = keypoints.copy()

    if method == "hip_center" or method == NormalizationMethod.HIP_CENTER.value:
        # 엉덩이 중심 원점
        hip_center = (keypoints[KP_LEFT_HIP, :2] + keypoints[KP_RIGHT_HIP, :2]) / 2.0
        result[:, :2] -= hip_center

        # 몸통 길이 정규화
        shoulder_center = (keypoints[KP_LEFT_SHOULDER, :2] + keypoints[KP_RIGHT_SHOULDER, :2]) / 2.0
        torso = float(np.linalg.norm(shoulder_center - hip_center))
        if torso > _EPSILON:
            result[:, :2] /= torso

    elif method == "shoulder_center" or method == NormalizationMethod.SHOULDER_CENTER.value:
        # 어깨 중심 원점
        shoulder_center = (keypoints[KP_LEFT_SHOULDER, :2] + keypoints[KP_RIGHT_SHOULDER, :2]) / 2.0
        result[:, :2] -= shoulder_center

        # 어깨 너비 정규화
        shoulder_width = float(np.linalg.norm(
            keypoints[KP_LEFT_SHOULDER, :2] - keypoints[KP_RIGHT_SHOULDER, :2]
        ))
        if shoulder_width > _EPSILON:
            result[:, :2] /= shoulder_width

    elif method == "bbox" or method == NormalizationMethod.BBOX.value:
        # 바운딩 박스 정규화 [0, 1]
        valid_mask = keypoints[:, 2] >= DEFAULT_CONFIDENCE_THRESHOLD
        if np.any(valid_mask):
            xy = keypoints[valid_mask, :2]
            xy_min = xy.min(axis=0)
            xy_range = xy.max(axis=0) - xy_min
            xy_range = np.where(xy_range < _EPSILON, 1.0, xy_range)
            result[:, :2] = (keypoints[:, :2] - xy_min) / xy_range

    return result


# =============================================================================
# 키포인트 필터링 및 보간
# =============================================================================

def filter_keypoints_by_confidence(
    keypoints: NDArray[np.float64],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    fill_value: float = 0.0,
) -> NDArray[np.float64]:
    """
    신뢰도 임계값 미만 키포인트를 마스킹.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        threshold: 신뢰도 임계값
        fill_value: 마스킹 시 채울 값 (좌표에 적용)

    Returns:
        필터링된 (N, 3) 배열

    Example:
        >>> kps = np.array([[0.5, 0.3, 0.9], [0.2, 0.1, 0.1]])
        >>> filtered = filter_keypoints_by_confidence(kps, 0.5)
        >>> filtered[1, 0]  # 낮은 신뢰도 → fill_value
        0.0
    """
    keypoints = np.asarray(keypoints, dtype=np.float64).copy()
    low_conf = keypoints[:, 2] < threshold
    keypoints[low_conf, :2] = fill_value
    return keypoints


def interpolate_missing_keypoints(
    keypoints: NDArray[np.float64],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> NDArray[np.float64]:
    """
    누락 키포인트를 인접 유효 키포인트의 가중 평균으로 보간.

    운동학 체인(KINEMATIC_PARENT_MAP)을 활용하여
    부모/자식 관절로부터 누락 위치 추정.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        confidence_threshold: 유효 판정 임계값

    Returns:
        보간된 (N, 3) 배열

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[7, 2] = 0.0  # 왼쪽 팔꿈치 누락
        >>> kps_filled = interpolate_missing_keypoints(kps)
        >>> kps_filled[7, 2] > 0  # 보간됨
        True
    """
    keypoints = np.asarray(keypoints, dtype=np.float64).copy()
    n = keypoints.shape[0]

    for i in range(n):
        if keypoints[i, 2] >= confidence_threshold:
            continue

        # 부모 관절에서 보간 시도
        parent_idx = KINEMATIC_PARENT_MAP.get(i)
        # 자식 관절에서 보간 시도
        children_idx = KINEMATIC_CHILDREN_MAP.get(i, ())

        contributors: list[NDArray[np.float64]] = []
        weights: list[float] = []

        if parent_idx is not None and parent_idx < n:
            if keypoints[parent_idx, 2] >= confidence_threshold:
                contributors.append(keypoints[parent_idx, :2])
                weights.append(keypoints[parent_idx, 2])

        for child_idx in children_idx:
            if child_idx < n and keypoints[child_idx, 2] >= confidence_threshold:
                contributors.append(keypoints[child_idx, :2])
                weights.append(keypoints[child_idx, 2])

        if contributors:
            w = np.array(weights, dtype=np.float64)
            w_sum = w.sum()
            if w_sum > _EPSILON:
                interp_xy = sum(c * ww for c, ww in zip(contributors, weights)) / w_sum
                keypoints[i, :2] = interp_xy
                keypoints[i, 2] = w_sum / len(weights) * 0.5  # 보간 → 신뢰도 감소

    return keypoints


def mirror_skeleton(
    keypoints: NDArray[np.float64],
    image_width: float = 1.0,
) -> NDArray[np.float64]:
    """
    스켈레톤 좌우 대칭 변환 (데이터 증강/반전 비교용).

    X 좌표를 반전하고 좌/우 키포인트 인덱스를 교환.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        image_width: 이미지 너비 (정규화 좌표: 1.0, 픽셀: 이미지 너비)

    Returns:
        좌우 반전된 (N, 3) 배열

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> mirrored = mirror_skeleton(kps, image_width=1.0)
        >>> # 왼쪽 어깨 ↔ 오른쪽 어깨 교환됨
        >>> mirrored.shape
        (17, 3)
    """
    keypoints = np.asarray(keypoints, dtype=np.float64).copy()
    n = keypoints.shape[0]

    # X 좌표 반전
    keypoints[:, 0] = image_width - keypoints[:, 0]

    # 좌우 인덱스 교환
    result = keypoints.copy()
    for src, dst in _MIRROR_MAP.items():
        if src < n and dst < n:
            result[dst] = keypoints[src]

    return result


# =============================================================================
# 팔다리 벡터 및 길이
# =============================================================================

def get_limb_vector(
    keypoints: NDArray[np.float64],
    start_idx: int,
    end_idx: int,
) -> NDArray[np.float64] | None:
    """
    두 키포인트 사이의 팔다리 벡터.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence]
        start_idx: 시작 키포인트 인덱스
        end_idx: 끝 키포인트 인덱스

    Returns:
        방향 벡터 (2,) 또는 None (유효하지 않은 경우)

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9
        >>> v = get_limb_vector(kps, KP_LEFT_SHOULDER, KP_LEFT_ELBOW)
        >>> v.shape
        (2,)
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)
    n = keypoints.shape[0]

    if start_idx >= n or end_idx >= n:
        return None
    if keypoints[start_idx, 2] < DEFAULT_CONFIDENCE_THRESHOLD:
        return None
    if keypoints[end_idx, 2] < DEFAULT_CONFIDENCE_THRESHOLD:
        return None

    return keypoints[end_idx, :2] - keypoints[start_idx, :2]


def calculate_limb_length(
    keypoints: NDArray[np.float64],
    start_idx: int,
    end_idx: int,
) -> float | None:
    """
    두 키포인트 사이의 팔다리 길이.

    Args:
        keypoints: (N, 3) 배열
        start_idx: 시작 키포인트 인덱스
        end_idx: 끝 키포인트 인덱스

    Returns:
        유클리드 거리 또는 None

    Example:
        >>> kps = np.array([[0, 0, 0.9], [3, 4, 0.9]], dtype=np.float64)
        >>> calculate_limb_length(kps, 0, 1)
        5.0
    """
    vec = get_limb_vector(keypoints, start_idx, end_idx)
    if vec is None:
        return None
    return float(np.linalg.norm(vec))


def calculate_all_limb_lengths(
    keypoints: NDArray[np.float64],
) -> dict[tuple[int, int], float]:
    """
    모든 스켈레톤 연결의 팔다리 길이 계산.

    Args:
        keypoints: (N, 3) 배열

    Returns:
        {(start, end): length} 딕셔너리

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9
        >>> lengths = calculate_all_limb_lengths(kps)
        >>> (5, 7) in lengths  # 왼쪽 어깨→팔꿈치
        True
    """
    result: dict[tuple[int, int], float] = {}
    for start, end in SKELETON_CONNECTIONS:
        length = calculate_limb_length(keypoints, start, end)
        if length is not None:
            result[(start, end)] = length
    return result


def get_body_part_center(
    keypoints: NDArray[np.float64],
    body_part: BodyPart,
) -> NDArray[np.float64] | None:
    """
    신체 부위의 중심 좌표 계산.

    Args:
        keypoints: (N, 3) 배열
        body_part: 신체 부위

    Returns:
        중심 좌표 (2,) 또는 None

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9
        >>> center = get_body_part_center(kps, BodyPart.TORSO)
        >>> center.shape
        (2,)
    """
    indices = BODY_PART_KEYPOINTS.get(body_part)
    if indices is None:
        return None

    keypoints = np.asarray(keypoints, dtype=np.float64)
    valid_points: list[NDArray[np.float64]] = []

    for idx in indices:
        if idx < keypoints.shape[0] and keypoints[idx, 2] >= DEFAULT_CONFIDENCE_THRESHOLD:
            valid_points.append(keypoints[idx, :2])

    if not valid_points:
        return None

    return np.mean(valid_points, axis=0).astype(np.float64)


def estimate_center_of_mass(
    keypoints: NDArray[np.float64],
    segment_weights: dict[int, float] | None = None,
) -> NDArray[np.float64] | None:
    """
    간이 무게중심 추정 (De Leva 기반 비율).

    실제 인체역학의 세그먼트 무게 비율을 사용하여
    키포인트 위치의 가중 평균으로 무게중심 근사.

    Args:
        keypoints: (N, 3) 배열
        segment_weights: 커스텀 키포인트별 가중치 {idx: weight}
                        None이면 De Leva 기반 기본값 사용

    Returns:
        무게중심 (2,) 또는 None

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9
        >>> com = estimate_center_of_mass(kps)
        >>> com.shape
        (2,)
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)

    if segment_weights is None:
        # De Leva (1996) 기반 간이 비율 (COCO 키포인트 매핑)
        segment_weights = {
            KP_NOSE: 0.081,          # 머리
            KP_LEFT_SHOULDER: 0.04,  KP_RIGHT_SHOULDER: 0.04,   # 상체
            KP_LEFT_ELBOW: 0.022,    KP_RIGHT_ELBOW: 0.022,     # 전완
            KP_LEFT_WRIST: 0.013,    KP_RIGHT_WRIST: 0.013,     # 손
            KP_LEFT_HIP: 0.12,      KP_RIGHT_HIP: 0.12,        # 골반/대퇴
            KP_LEFT_KNEE: 0.048,    KP_RIGHT_KNEE: 0.048,       # 하퇴
            KP_LEFT_ANKLE: 0.017,   KP_RIGHT_ANKLE: 0.017,      # 발
        }

    total_weight = 0.0
    weighted_pos = np.zeros(2, dtype=np.float64)

    for idx, weight in segment_weights.items():
        if idx < keypoints.shape[0] and keypoints[idx, 2] >= DEFAULT_CONFIDENCE_THRESHOLD:
            weighted_pos += keypoints[idx, :2] * weight
            total_weight += weight

    if total_weight < _EPSILON:
        return None

    return weighted_pos / total_weight


# =============================================================================
# 관절 속도/가속도/저크
# =============================================================================

def calculate_keypoint_velocities(
    keypoints_seq: NDArray[np.float64],
    dt: float,
) -> NDArray[np.float64]:
    """
    키포인트 시퀀스에서 각 키포인트의 속도 계산.

    중앙 차분법: v[t] = (x[t+1] - x[t-1]) / (2·dt)
    양 끝은 전방/후방 차분.

    Args:
        keypoints_seq: (T, N, 3) 배열 — T 프레임, N 키포인트
        dt: 프레임 간격 (초)

    Returns:
        속도 배열 (T, N, 2) — [vx, vy]

    Example:
        >>> seq = np.random.rand(30, 17, 3)
        >>> vel = calculate_keypoint_velocities(seq, 1/30)
        >>> vel.shape
        (30, 17, 2)
    """
    keypoints_seq = np.asarray(keypoints_seq, dtype=np.float64)
    T = keypoints_seq.shape[0]

    if T < 2:
        return np.zeros((*keypoints_seq.shape[:2], 2), dtype=np.float64)
    if dt <= 0:
        raise ValueError(f"시간 간격은 양수여야 합니다: dt={dt}")

    positions = keypoints_seq[:, :, :2]  # (T, N, 2)
    velocities = np.zeros_like(positions)

    # 중앙 차분 (내부 프레임)
    if T > 2:
        velocities[1:-1] = (positions[2:] - positions[:-2]) / (2.0 * dt)

    # 전방 차분 (첫 프레임)
    velocities[0] = (positions[1] - positions[0]) / dt

    # 후방 차분 (마지막 프레임)
    velocities[-1] = (positions[-1] - positions[-2]) / dt

    return velocities


def calculate_keypoint_accelerations(
    velocities: NDArray[np.float64],
    dt: float,
) -> NDArray[np.float64]:
    """
    속도 시퀀스에서 가속도 계산.

    Args:
        velocities: (T, N, 2) 속도 배열
        dt: 프레임 간격 (초)

    Returns:
        가속도 배열 (T, N, 2)

    Example:
        >>> vel = np.random.rand(30, 17, 2)
        >>> acc = calculate_keypoint_accelerations(vel, 1/30)
        >>> acc.shape
        (30, 17, 2)
    """
    velocities = np.asarray(velocities, dtype=np.float64)
    T = velocities.shape[0]

    if T < 2:
        return np.zeros_like(velocities)
    if dt <= 0:
        raise ValueError(f"시간 간격은 양수여야 합니다: dt={dt}")

    accel = np.zeros_like(velocities)

    if T > 2:
        accel[1:-1] = (velocities[2:] - velocities[:-2]) / (2.0 * dt)

    accel[0] = (velocities[1] - velocities[0]) / dt
    accel[-1] = (velocities[-1] - velocities[-2]) / dt

    return accel


def calculate_jerk(
    accelerations: NDArray[np.float64],
    dt: float,
) -> NDArray[np.float64]:
    """
    가속도 시퀀스에서 저크(jerk) 계산 (가속도의 변화율).

    저크가 작을수록 모션이 부드러움.

    Args:
        accelerations: (T, N, 2) 가속도 배열
        dt: 프레임 간격 (초)

    Returns:
        저크 배열 (T, N, 2)

    Example:
        >>> acc = np.random.rand(30, 17, 2)
        >>> j = calculate_jerk(acc, 1/30)
        >>> j.shape
        (30, 17, 2)
    """
    return calculate_keypoint_accelerations(accelerations, dt)


def calculate_keypoint_speed(
    velocities: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    속도 벡터에서 속력 (크기) 계산.

    Args:
        velocities: (T, N, 2) 속도 배열

    Returns:
        속력 배열 (T, N) — 스칼라

    Example:
        >>> vel = np.array([[[3, 4], [0, 5]]], dtype=np.float64)
        >>> spd = calculate_keypoint_speed(vel)
        >>> np.isclose(spd[0, 0], 5.0)
        True
    """
    velocities = np.asarray(velocities, dtype=np.float64)
    return np.linalg.norm(velocities, axis=-1)


# =============================================================================
# 포즈 비교 (OKS, Procrustes, 거리)
# =============================================================================

def oks_similarity(
    predicted: NDArray[np.float64],
    ground_truth: NDArray[np.float64],
    area: float,
    sigmas: tuple[float, ...] | None = None,
) -> float:
    """
    Object Keypoint Similarity (OKS) 계산.

    COCO 평가 표준. 값이 1에 가까울수록 정확.

    Args:
        predicted: (N, 3) 예측 키포인트 [x, y, confidence]
        ground_truth: (N, 3) 정답 키포인트 [x, y, visibility]
        area: 인물 바운딩 박스 면적
        sigmas: 키포인트별 시그마 (None이면 COCO 기본값)

    Returns:
        OKS 점수 (0~1)

    Example:
        >>> pred = np.random.rand(17, 3)
        >>> gt = pred.copy()
        >>> oks = oks_similarity(pred, gt, area=10000.0)
        >>> np.isclose(oks, 1.0, atol=0.01)
        True
    """
    predicted = np.asarray(predicted, dtype=np.float64)
    ground_truth = np.asarray(ground_truth, dtype=np.float64)

    if sigmas is None:
        sigmas = OKS_SIGMAS

    n = min(predicted.shape[0], ground_truth.shape[0], len(sigmas))
    if n == 0 or area < _EPSILON:
        return 0.0

    sigma_arr = np.array(sigmas[:n], dtype=np.float64)
    visibility = ground_truth[:n, 2]

    # 가시 키포인트만 사용
    visible_mask = visibility > 0
    if not np.any(visible_mask):
        return 0.0

    dx = predicted[:n, 0] - ground_truth[:n, 0]
    dy = predicted[:n, 1] - ground_truth[:n, 1]
    d_sq = dx ** 2 + dy ** 2

    # OKS = Σ exp(-d² / (2·σ²·s²)) · δ(v>0) / Σ δ(v>0)
    var = 2.0 * (sigma_arr ** 2) * area
    var = np.where(var < _EPSILON, _EPSILON, var)

    exp_vals = np.exp(-d_sq / var)
    oks_val = float(np.sum(exp_vals[visible_mask]) / np.sum(visible_mask))
    return oks_val


def procrustes_align(
    source: NDArray[np.float64],
    target: NDArray[np.float64],
) -> ProcrustesResult:
    """
    Procrustes 정렬 (최적 스케일 + 회전 + 이동).

    source를 target에 가장 가깝게 정렬.

    Args:
        source: (N, D) 소스 포인트 (D=2 또는 3)
        target: (N, D) 타겟 포인트

    Returns:
        ProcrustesResult 데이터클래스

    Example:
        >>> src = np.random.rand(17, 2)
        >>> tgt = src * 2.0 + 3.0  # 스케일 + 이동
        >>> result = procrustes_align(src, tgt)
        >>> np.isclose(result.scale, 2.0, atol=0.1)
        True
    """
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)

    if source.shape != target.shape:
        raise ValueError(f"형태 불일치: source={source.shape}, target={target.shape}")

    # 중심 이동
    mu_s = source.mean(axis=0)
    mu_t = target.mean(axis=0)
    s_centered = source - mu_s
    t_centered = target - mu_t

    # 스케일 정규화
    ss = np.sum(s_centered ** 2)
    st = np.sum(t_centered ** 2)

    if ss < _EPSILON or st < _EPSILON:
        return ProcrustesResult(
            aligned=source.copy(),
            disparity=float(np.sum((source - target) ** 2)),
        )

    norm_s = np.sqrt(ss)
    norm_t = np.sqrt(st)

    s_normalized = s_centered / norm_s
    t_normalized = t_centered / norm_t

    # 최적 회전 (SVD)
    M = t_normalized.T @ s_normalized
    U, _, Vt = np.linalg.svd(M)

    # 반사 보정
    d = np.linalg.det(U @ Vt)
    D = np.eye(M.shape[0], dtype=np.float64)
    if d < 0:
        D[-1, -1] = -1.0

    R = U @ D @ Vt
    scale = norm_t / norm_s
    translation = mu_t - scale * (R @ mu_s)

    # 정렬된 포인트
    aligned = scale * (source @ R.T) + translation
    disparity = float(np.sum((aligned - target) ** 2) / target.shape[0])

    return ProcrustesResult(
        aligned=aligned,
        scale=float(scale),
        rotation=R,
        translation=translation,
        disparity=disparity,
    )


def pose_distance(
    kps1: NDArray[np.float64],
    kps2: NDArray[np.float64],
    weighted: bool = True,
) -> float:
    """
    두 포즈 사이의 가중 유클리드 거리.

    Args:
        kps1: (N, 3) 첫 번째 키포인트 [x, y, confidence]
        kps2: (N, 3) 두 번째 키포인트 [x, y, confidence]
        weighted: True이면 신뢰도로 가중

    Returns:
        거리 스칼라

    Example:
        >>> kps1 = np.array([[0, 0, 0.9], [1, 0, 0.9]])
        >>> kps2 = np.array([[0, 0, 0.9], [1, 1, 0.9]])
        >>> d = pose_distance(kps1, kps2)
        >>> d > 0
        True
    """
    kps1 = np.asarray(kps1, dtype=np.float64)
    kps2 = np.asarray(kps2, dtype=np.float64)

    n = min(kps1.shape[0], kps2.shape[0])
    if n == 0:
        return 0.0

    diff = kps1[:n, :2] - kps2[:n, :2]
    dists = np.linalg.norm(diff, axis=1)

    if weighted:
        # 양쪽 신뢰도의 최소값으로 가중
        weights = np.minimum(kps1[:n, 2], kps2[:n, 2])
        w_sum = weights.sum()
        if w_sum < _EPSILON:
            return float(np.mean(dists))
        return float(np.sum(dists * weights) / w_sum)

    return float(np.mean(dists))


# =============================================================================
# 신체 방향 분석
# =============================================================================

def estimate_body_orientation(
    keypoints: NDArray[np.float64],
) -> BodyOrientation:
    """
    스켈레톤에서 신체 방향 분석.

    Args:
        keypoints: (N, 3) 배열 [x, y, confidence] (N >= 17)

    Returns:
        BodyOrientation 데이터클래스

    Example:
        >>> kps = np.random.rand(17, 3)
        >>> kps[:, 2] = 0.9
        >>> orient = estimate_body_orientation(kps)
        >>> isinstance(orient, BodyOrientation)
        True
    """
    keypoints = np.asarray(keypoints, dtype=np.float64)

    if keypoints.shape[0] < COCO_NUM_KEYPOINTS:
        logger.warning(f"키포인트 수 부족: {keypoints.shape[0]} < {COCO_NUM_KEYPOINTS}")
        return BodyOrientation()

    # 어깨/엉덩이 좌표 추출
    ls = keypoints[KP_LEFT_SHOULDER, :2]
    rs = keypoints[KP_RIGHT_SHOULDER, :2]
    lh = keypoints[KP_LEFT_HIP, :2]
    rh = keypoints[KP_RIGHT_HIP, :2]

    # 어깨/엉덩이 중심
    shoulder_c = (ls + rs) / 2.0
    hip_c = (lh + rh) / 2.0

    # 정면 방향 (어깨 라인의 법선)
    shoulder_vec = rs - ls
    facing_vec = np.array([-shoulder_vec[1], shoulder_vec[0]])  # 90° 회전
    facing_angle = math.degrees(math.atan2(facing_vec[1], facing_vec[0]))

    # 어깨 라인 각도 (수평 기준)
    shoulder_angle = math.degrees(math.atan2(
        rs[1] - ls[1], rs[0] - ls[0]
    ))

    # 엉덩이 라인 각도 (수평 기준)
    hip_angle = math.degrees(math.atan2(
        rh[1] - lh[1], rh[0] - lh[0]
    ))

    # 전후 기울기 (몸통 벡터의 수직 성분)
    torso_vec = shoulder_c - hip_c
    torso_len = np.linalg.norm(torso_vec)
    if torso_len > _EPSILON:
        # Y축 기준 기울기 (양수 = 앞으로)
        tilt_forward = math.degrees(math.atan2(torso_vec[0], -torso_vec[1]))
    else:
        tilt_forward = 0.0

    # 좌우 기울기 (어깨/엉덩이 중심의 X 오프셋)
    tilt_lateral = shoulder_angle - hip_angle

    return BodyOrientation(
        facing_angle=facing_angle,
        tilt_forward=tilt_forward,
        tilt_lateral=tilt_lateral,
        shoulder_angle=shoulder_angle,
        hip_angle=hip_angle,
    )


def estimate_facing_direction(
    keypoints: NDArray[np.float64],
) -> float:
    """
    정면 방향 각도 추정 (도, 어깨 라인 법선).

    Args:
        keypoints: (N, 3) 배열

    Returns:
        정면 방향 각도 (도)

    Example:
        >>> kps = np.zeros((17, 3))
        >>> kps[:, 2] = 0.9
        >>> kps[5] = [0, 0, 0.9]   # 왼쪽 어깨
        >>> kps[6] = [1, 0, 0.9]   # 오른쪽 어깨
        >>> angle = estimate_facing_direction(kps)
        >>> np.isclose(angle, -90.0) or np.isclose(angle, 270.0)  # 아래 방향
        True
    """
    orient = estimate_body_orientation(keypoints)
    return orient.facing_angle


# =============================================================================
# 시계열 연산
# =============================================================================

def extract_temporal_window(
    sequence: NDArray[np.float64],
    center_frame: int,
    window_size: int,
    pad_mode: str = "edge",
) -> NDArray[np.float64]:
    """
    시계열에서 특정 프레임 중심의 윈도우 추출.

    Args:
        sequence: (T, ...) 시계열 배열
        center_frame: 중심 프레임 인덱스
        window_size: 윈도우 크기 (홀수 권장)
        pad_mode: 경계 패딩 ("edge", "zero", "reflect")

    Returns:
        (window_size, ...) 윈도우 배열

    Example:
        >>> seq = np.arange(100).reshape(100, 1)
        >>> w = extract_temporal_window(seq, 5, 11)
        >>> w.shape
        (11, 1)
    """
    sequence = np.asarray(sequence, dtype=np.float64)
    T = sequence.shape[0]

    half = window_size // 2
    start = center_frame - half
    end = center_frame + half + 1

    if start >= 0 and end <= T:
        return sequence[start:end].copy()

    # 패딩 필요
    indices = np.arange(start, end)

    if pad_mode == "edge":
        indices = np.clip(indices, 0, T - 1)
    elif pad_mode == "reflect":
        indices = np.where(indices < 0, -indices, indices)
        indices = np.where(indices >= T, 2 * T - 2 - indices, indices)
        indices = np.clip(indices, 0, T - 1)
    else:  # "zero"
        valid = (indices >= 0) & (indices < T)
        result = np.zeros((window_size, *sequence.shape[1:]), dtype=np.float64)
        result[valid] = sequence[indices[valid]]
        return result

    return sequence[indices].copy()


def calculate_motion_smoothness(
    keypoints_seq: NDArray[np.float64],
    dt: float,
    joint_idx: int | None = None,
) -> MotionSmoothness:
    """
    모션 부드러움 측정 (저크 기반).

    Args:
        keypoints_seq: (T, N, 3) 키포인트 시퀀스
        dt: 프레임 간격 (초)
        joint_idx: 특정 관절만 측정 (None이면 전체 평균)

    Returns:
        MotionSmoothness 데이터클래스

    Example:
        >>> seq = np.random.rand(30, 17, 3)
        >>> sm = calculate_motion_smoothness(seq, 1/30)
        >>> 0 <= sm.smoothness <= 1
        True
    """
    keypoints_seq = np.asarray(keypoints_seq, dtype=np.float64)
    T = keypoints_seq.shape[0]

    if T < 3:
        return MotionSmoothness(smoothness=1.0)

    vel = calculate_keypoint_velocities(keypoints_seq, dt)
    acc = calculate_keypoint_accelerations(vel, dt)
    jrk = calculate_jerk(acc, dt)

    if joint_idx is not None:
        vel = vel[:, joint_idx:joint_idx + 1]
        acc = acc[:, joint_idx:joint_idx + 1]
        jrk = jrk[:, joint_idx:joint_idx + 1]

    # RMS 값 계산
    vel_mag = np.linalg.norm(vel, axis=-1)
    acc_mag = np.linalg.norm(acc, axis=-1)
    jerk_mag = np.linalg.norm(jrk, axis=-1)

    jerk_rms = float(np.sqrt(np.mean(jerk_mag ** 2)))
    vel_std = float(np.std(vel_mag))
    acc_std = float(np.std(acc_mag))

    # 부드러움 점수: 1 / (1 + normalized_jerk)
    # 속도 크기로 정규화하여 스케일 불변
    vel_mean = float(np.mean(vel_mag))
    if vel_mean > _EPSILON:
        normalized_jerk = jerk_rms / vel_mean
    else:
        normalized_jerk = jerk_rms

    smoothness = 1.0 / (1.0 + normalized_jerk)

    return MotionSmoothness(
        smoothness=float(np.clip(smoothness, 0.0, 1.0)),
        jerk_rms=jerk_rms,
        velocity_std=vel_std,
        acceleration_std=acc_std,
    )


def smooth_keypoint_sequence(
    keypoints_seq: NDArray[np.float64],
    method: str = "moving_average",
    window_size: int = 5,
    alpha: float = 0.3,
) -> NDArray[np.float64]:
    """
    키포인트 시퀀스 시간축 스무딩.

    Args:
        keypoints_seq: (T, N, 3) 키포인트 시퀀스
        method: 스무딩 방법 ("moving_average", "exponential", "gaussian")
        window_size: 이동 평균 윈도우 크기 (홀수)
        alpha: EMA 계수 (0~1, 클수록 현재 값에 가중)

    Returns:
        스무딩된 (T, N, 3) 배열

    Example:
        >>> seq = np.random.rand(30, 17, 3)
        >>> smoothed = smooth_keypoint_sequence(seq, "moving_average", 5)
        >>> smoothed.shape
        (30, 17, 3)
    """
    keypoints_seq = np.asarray(keypoints_seq, dtype=np.float64)
    T, N, C = keypoints_seq.shape

    if T < 2:
        return keypoints_seq.copy()

    result = keypoints_seq.copy()

    if method == "moving_average" or method == SmoothingMethod.MOVING_AVERAGE.value:
        half = window_size // 2
        for t in range(T):
            start = max(0, t - half)
            end = min(T, t + half + 1)
            result[t, :, :2] = keypoints_seq[start:end, :, :2].mean(axis=0)

    elif method == "exponential" or method == SmoothingMethod.EXPONENTIAL.value:
        for t in range(1, T):
            result[t, :, :2] = alpha * keypoints_seq[t, :, :2] + (1 - alpha) * result[t - 1, :, :2]

    elif method == "gaussian" or method == SmoothingMethod.GAUSSIAN.value:
        half = window_size // 2
        kernel = np.exp(-0.5 * (np.arange(-half, half + 1) / (half / 2.5)) ** 2)
        kernel /= kernel.sum()

        for t in range(T):
            start = max(0, t - half)
            end = min(T, t + half + 1)
            k_start = max(0, half - t)
            k_end = k_start + (end - start)
            k = kernel[k_start:k_end]
            k = k / k.sum()  # 재정규화
            result[t, :, :2] = np.tensordot(k, keypoints_seq[start:end, :, :2], axes=([0], [0]))

    # 신뢰도는 원본 유지
    result[:, :, 2] = keypoints_seq[:, :, 2]

    return result


def detect_keyframe_indices(
    keypoints_seq: NDArray[np.float64],
    threshold: float = 0.1,
) -> list[int]:
    """
    모션 변화가 큰 프레임(키프레임) 인덱스 추출.

    인접 프레임 간 포즈 변화량이 임계값을 초과하는 프레임.

    Args:
        keypoints_seq: (T, N, 3) 키포인트 시퀀스
        threshold: 변화량 임계값 (정규화 거리)

    Returns:
        키프레임 인덱스 리스트

    Example:
        >>> seq = np.random.rand(100, 17, 3)
        >>> kf = detect_keyframe_indices(seq, 0.5)
        >>> isinstance(kf, list)
        True
    """
    keypoints_seq = np.asarray(keypoints_seq, dtype=np.float64)
    T = keypoints_seq.shape[0]

    if T < 2:
        return [0] if T > 0 else []

    keyframes = [0]  # 첫 프레임은 항상 키프레임
    for t in range(1, T):
        diff = keypoints_seq[t, :, :2] - keypoints_seq[t - 1, :, :2]
        change = float(np.mean(np.linalg.norm(diff, axis=1)))
        if change > threshold:
            keyframes.append(t)

    # 마지막 프레임
    if keyframes[-1] != T - 1:
        keyframes.append(T - 1)

    return keyframes


def calculate_temporal_consistency(
    keypoints_seq: NDArray[np.float64],
) -> float:
    """
    시계열 일관성 점수 (0~1, 1이 가장 일관적).

    인접 프레임 간 키포인트 이동 분산이 작을수록 일관적.

    Args:
        keypoints_seq: (T, N, 3) 키포인트 시퀀스

    Returns:
        일관성 점수

    Example:
        >>> seq = np.ones((30, 17, 3))  # 정적 포즈
        >>> calculate_temporal_consistency(seq)
        1.0
    """
    keypoints_seq = np.asarray(keypoints_seq, dtype=np.float64)
    T = keypoints_seq.shape[0]

    if T < 2:
        return 1.0

    diffs = keypoints_seq[1:, :, :2] - keypoints_seq[:-1, :, :2]
    frame_changes = np.mean(np.linalg.norm(diffs, axis=-1), axis=-1)  # (T-1,)

    # 변화의 분산이 작을수록 일관적
    change_var = float(np.var(frame_changes))
    change_mean = float(np.mean(frame_changes))

    if change_mean < _EPSILON:
        return 1.0  # 정적 포즈

    cv = change_var / (change_mean ** 2)  # 변동 계수 제곱
    consistency = 1.0 / (1.0 + cv)
    return float(np.clip(consistency, 0.0, 1.0))


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # === 상수 ===
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "HIGH_CONFIDENCE_THRESHOLD",
    "COCO_NUM_KEYPOINTS",
    "OKS_SIGMAS",
    "SKELETON_CONNECTIONS",
    # 키포인트 인덱스
    "KP_NOSE", "KP_LEFT_EYE", "KP_RIGHT_EYE",
    "KP_LEFT_EAR", "KP_RIGHT_EAR",
    "KP_LEFT_SHOULDER", "KP_RIGHT_SHOULDER",
    "KP_LEFT_ELBOW", "KP_RIGHT_ELBOW",
    "KP_LEFT_WRIST", "KP_RIGHT_WRIST",
    "KP_LEFT_HIP", "KP_RIGHT_HIP",
    "KP_LEFT_KNEE", "KP_RIGHT_KNEE",
    "KP_LEFT_ANKLE", "KP_RIGHT_ANKLE",

    # === 운동학 체인 ===
    "KINEMATIC_PARENT_MAP",
    "KINEMATIC_CHILDREN_MAP",
    "BODY_PART_KEYPOINTS",
    "KEYPOINT_TO_BODY_PART",

    # === Enum ===
    "NormalizationMethod",
    "SmoothingMethod",
    "BodyPart",

    # === 데이터 클래스 ===
    "SkeletonMetrics",
    "ProcrustesResult",
    "MotionSmoothness",
    "BodyOrientation",

    # === 변환 ===
    "skeleton_to_numpy",
    "skeleton_to_numpy_3d",
    "numpy_to_keypoints",

    # === 메트릭 ===
    "calculate_skeleton_metrics",

    # === 정규화 ===
    "normalize_skeleton_scale",

    # === 필터링/보간 ===
    "filter_keypoints_by_confidence",
    "interpolate_missing_keypoints",
    "mirror_skeleton",

    # === 팔다리/운동학 ===
    "get_limb_vector",
    "calculate_limb_length",
    "calculate_all_limb_lengths",
    "get_body_part_center",
    "estimate_center_of_mass",

    # === 속도/가속도/저크 ===
    "calculate_keypoint_velocities",
    "calculate_keypoint_accelerations",
    "calculate_jerk",
    "calculate_keypoint_speed",

    # === 포즈 비교 ===
    "oks_similarity",
    "procrustes_align",
    "pose_distance",

    # === 신체 방향 ===
    "estimate_body_orientation",
    "estimate_facing_direction",

    # === 시계열 ===
    "extract_temporal_window",
    "calculate_motion_smoothness",
    "smooth_keypoint_sequence",
    "detect_keyframe_indices",
    "calculate_temporal_consistency",
]

__version__: str = "1.0.0"
