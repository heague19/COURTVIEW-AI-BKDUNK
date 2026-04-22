# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/dynamics
파일: balance_analyzer.py
설명: 균형/안정성 분석 모듈
      - 무게중심(COM): 키포인트 기반 전신 COM 추정
      - 지지기저면(BoS): 양발 위치 기반 BoS 면적 산출
      - 안정성 지수: COM과 BoS 관계 기반 동적 안정성
      - 동요 속도(Sway): COM 이동 속도
      - 체중 분배: 좌/우 하지 분배 비율

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, Ch.7.
    - Hof, A.L. (2008). The 'extrapolated center of mass' concept.
      Human Movement Science, 27(1), 112-125.
    - 안정성 조건: COM의 수평 투영이 BoS 내부에 위치해야 안정

의존성:
    - shared/constants/biomechanics_constants.py: 안정성/BoS 임계치
    - biomechanics/anthropometry/body_segment.py: BodyModel, calculate_whole_body_com

사용처:
    - biomechanics/data_extraction/: BalanceMetrics DTO 생성
    - motion_analysis/form_evaluation/: 슛/수비 스탠스 안정성
    - ai_referee/: 밀침/넘어짐 판정 보조
    - feedback_system/: 균형 피드백
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import (
    STABILITY_INDEX_MIN_STABLE,
    COP_SWAY_STABLE_THRESHOLD_CM,
    COP_SWAY_UNSTABLE_THRESHOLD_CM,
    BASE_OF_SUPPORT_MIN_RATIO,
    BASE_OF_SUPPORT_OPTIMAL_RATIO,
    BASE_OF_SUPPORT_MAX_RATIO,
)

from biomechanics.anthropometry.body_segment import (
    BodyModel,
    calculate_whole_body_com,
    SEGMENT_ENDPOINT_INDICES_25KP,
)

from shared.constants.pose_constants import (
    UK25_R_ANKLE as _R_ANKLE_IDX,
    UK25_L_ANKLE as _L_ANKLE_IDX,
    UK25_R_BIG_TOE as _R_TOE_IDX,
    UK25_L_BIG_TOE as _L_TOE_IDX,
    UK25_R_SHOULDER as _R_SHOULDER_IDX,
    UK25_L_SHOULDER as _L_SHOULDER_IDX,
)


# =============================================================================
# 상수
# =============================================================================

# 최소 시간 간격 (0-division 방지)
_MIN_DT: Final[float] = 1e-6

# cm/s → m/s 변환
_CM_TO_M: Final[float] = 0.01

# 최소 BoS 면적 (cm², 한 발 서기 등)
_MIN_BOS_AREA: Final[float] = 50.0

# 최대 BoS 면적 (cm², 이상치 필터)
_MAX_BOS_AREA: Final[float] = 10000.0

# 키포인트 최소 행 수 (발끝 20 + 1 = 21)
_MIN_KP_ROWS: Final[int] = 21

# BoS 발 4점 (시계방향 순서로 배치: 우발목 → 우발끝 → 좌발끝 → 좌발목)
# Shoelace 공식이 올바르게 작동하려면 다각형 꼭짓점 순서가 중요
_FOOT_INDICES: Final[tuple[int, ...]] = (
    _R_ANKLE_IDX, _R_TOE_IDX, _L_TOE_IDX, _L_ANKLE_IDX,
)


# =============================================================================
# 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class BalanceState:
    """
    프레임 단위 균형 분석 결과.

    Attributes:
        com_position: COM 좌표 (x, y, z) cm
        com_height_m: COM 높이 (m, 발목 기준)
        bos_area_cm2: 지지기저면 면적 (cm²)
        bos_width_cm: BoS 폭 (cm, 좌우 발목 간 거리)
        bos_shoulder_ratio: BoS 폭 / 어깨 폭 비율
        stability_index: 안정성 지수 (0~100)
        is_stable: 안정 여부
        weight_distribution: 좌/우 체중 분배 (합=1.0)
    """

    com_position: tuple[float, float, float]
    com_height_m: float
    bos_area_cm2: float
    bos_width_cm: float
    bos_shoulder_ratio: float
    stability_index: float
    is_stable: bool
    weight_distribution: tuple[float, float]


@dataclass(frozen=True, slots=True)
class SwayMetrics:
    """
    동요(Sway) 분석 결과.

    프레임 간 COM 이동으로 산출.

    Attributes:
        sway_distance_cm: 동요 거리 (cm, 수평 COM 이동)
        sway_velocity_cm_s: 동요 속도 (cm/s)
        sway_category: 동요 분류 (stable/moderate/unstable)
    """

    sway_distance_cm: float
    sway_velocity_cm_s: float
    sway_category: str


# =============================================================================
# COM 계산
# =============================================================================

def calculate_com_position(
    keypoints_3d: NDArray[np.float64],
    body_model: BodyModel,
) -> tuple[float, float, float] | None:
    """
    전신 무게중심(COM) 좌표 계산.

    body_segment.py의 calculate_whole_body_com을 활용하되,
    세그먼트 엔드포인트 인덱스를 자동 매핑합니다.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3/4, cm)
        body_model: 신체 모델

    Returns:
        COM 좌표 (x, y, z) cm, 계산 불가 시 None

    참조:
        de Leva (1996): 세그먼트별 질량 가중 COM
    """
    if keypoints_3d.shape[0] < _MIN_KP_ROWS:
        return None

    # BodySegment → (proximal_idx, distal_idx) 변환
    # SEGMENT_ENDPOINT_INDICES_25KP는 str 키이므로
    # calculate_whole_body_com이 사용하는 BodySegment 키로 변환
    from shared.constants.biomechanics_constants import BodySegment

    # 문자열 → BodySegment 매핑
    _name_to_seg: dict[str, BodySegment] = {
        "head": BodySegment.HEAD,
        "neck": BodySegment.NECK,
        "trunk_upper": BodySegment.TRUNK_UPPER,
        "r_upper_arm": BodySegment.UPPER_ARM,
        "r_forearm": BodySegment.FOREARM,
        "r_hand": BodySegment.HAND,
        "l_upper_arm": BodySegment.UPPER_ARM,
        "l_forearm": BodySegment.FOREARM,
        "l_hand": BodySegment.HAND,
        "r_thigh": BodySegment.THIGH,
        "r_shank": BodySegment.SHANK,
        "r_foot": BodySegment.FOOT,
        "l_thigh": BodySegment.THIGH,
        "l_shank": BodySegment.SHANK,
        "l_foot": BodySegment.FOOT,
    }

    # 각 세그먼트를 개별적으로 처리 (양측성 세그먼트 포함)
    coords = keypoints_3d[:, :3] if keypoints_3d.shape[1] > 3 else keypoints_3d
    total_mass = 0.0
    weighted_sum = np.zeros(3, dtype=np.float64)

    for name, (prox_idx, dist_idx) in SEGMENT_ENDPOINT_INDICES_25KP.items():
        seg_type = _name_to_seg.get(name)
        if seg_type is None:
            continue

        props = body_model.segments.get(seg_type)
        if props is None:
            continue

        if prox_idx >= coords.shape[0] or dist_idx >= coords.shape[0]:
            continue

        proximal = coords[prox_idx]
        distal = coords[dist_idx]

        # COM = proximal + ratio × (distal - proximal)
        seg_com = proximal + props.com_proximal_ratio * (distal - proximal)

        mass = props.mass_kg
        weighted_sum += mass * seg_com
        total_mass += mass

    if total_mass <= 0:
        return None

    com = weighted_sum / total_mass
    return (float(com[0]), float(com[1]), float(com[2]))


# =============================================================================
# 지지기저면 (BoS) 계산
# =============================================================================

def calculate_bos_area(
    keypoints_3d: NDArray[np.float64],
) -> float:
    """
    지지기저면(BoS) 면적 계산.

    양발 4점 (좌/우 발목, 좌/우 발끝)으로 형성되는
    사각형의 면적을 Shoelace 공식으로 산출합니다.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3/4, cm)

    Returns:
        BoS 면적 (cm²), 계산 불가 시 0.0

    참조:
        Winter (2009) Ch.7: Balance and posture
    """
    if keypoints_3d.shape[0] < _MIN_KP_ROWS:
        return 0.0

    # 4개 발 포인트의 수평 좌표 (x, z)
    points: list[tuple[float, float]] = []
    for idx in _FOOT_INDICES:
        if idx < keypoints_3d.shape[0]:
            x = float(keypoints_3d[idx, 0])
            z = float(keypoints_3d[idx, 2]) if keypoints_3d.shape[1] > 2 else 0.0
            points.append((x, z))

    if len(points) < 3:
        return 0.0

    # Shoelace 공식 (다각형 면적)
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    area = abs(area) / 2.0

    if area < _MIN_BOS_AREA or area > _MAX_BOS_AREA:
        return 0.0

    return area


def calculate_bos_width(
    keypoints_3d: NDArray[np.float64],
) -> float:
    """
    BoS 폭 계산 (좌/우 발목 간 수평 거리).

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3/4, cm)

    Returns:
        BoS 폭 (cm), 계산 불가 시 0.0
    """
    if keypoints_3d.shape[0] <= max(_R_ANKLE_IDX, _L_ANKLE_IDX):
        return 0.0

    r_ankle = keypoints_3d[_R_ANKLE_IDX, :3]
    l_ankle = keypoints_3d[_L_ANKLE_IDX, :3]

    # 수평 거리 (x, z 평면)
    dx = float(r_ankle[0] - l_ankle[0])
    dz = float(r_ankle[2] - l_ankle[2]) if keypoints_3d.shape[1] > 2 else 0.0

    return (dx ** 2 + dz ** 2) ** 0.5


# =============================================================================
# 안정성 지수 계산
# =============================================================================

def calculate_stability_index(
    com_position: tuple[float, float, float],
    keypoints_3d: NDArray[np.float64],
    bos_width: float,
) -> float:
    """
    동적 안정성 지수 계산 (0~100 스케일).

    COM의 수평 투영이 BoS 중심에 가까울수록 높은 안정성.

    안정성 지수 = 100 × (1 - d_com / d_max)
    - d_com: COM 수평 투영과 BoS 중심 간 거리
    - d_max: BoS 반폭 (BoS 경계까지 최대 허용 거리)

    Args:
        com_position: COM 좌표 (x, y, z) cm
        keypoints_3d: 키포인트 3D (발목 위치 참조)
        bos_width: BoS 폭 (cm)

    Returns:
        안정성 지수 (0~100)

    참조:
        Hof (2008): Extrapolated center of mass concept
    """
    if bos_width <= 0:
        return 0.0

    if keypoints_3d.shape[0] <= max(_R_ANKLE_IDX, _L_ANKLE_IDX):
        return 0.0

    # BoS 중심 (양 발목 중점, 수평 = x, z)
    r_ankle = keypoints_3d[_R_ANKLE_IDX]
    l_ankle = keypoints_3d[_L_ANKLE_IDX]
    bos_center_x = float(r_ankle[0] + l_ankle[0]) / 2.0
    bos_center_z = float(r_ankle[2] + l_ankle[2]) / 2.0 if keypoints_3d.shape[1] > 2 else 0.0

    # COM 수평 투영
    com_x = com_position[0]
    com_z = com_position[2]

    # COM ↔ BoS 중심 수평 거리
    d_com = ((com_x - bos_center_x) ** 2 + (com_z - bos_center_z) ** 2) ** 0.5

    # d_max = BoS 반폭
    d_max = bos_width / 2.0
    if d_max <= 0:
        return 0.0

    # 안정성 지수: 100 × (1 - d/d_max), 0~100 클램핑
    ratio = d_com / d_max
    index = 100.0 * (1.0 - min(ratio, 1.0))

    return max(0.0, index)


# =============================================================================
# 체중 분배
# =============================================================================

def estimate_weight_distribution(
    com_position: tuple[float, float, float],
    keypoints_3d: NDArray[np.float64],
) -> tuple[float, float]:
    """
    좌/우 체중 분배 추정.

    COM의 좌우 위치로 체중 분배를 역비례 추정합니다.
    COM이 우측에 가까우면 우측 하중↑, 좌측 하중↓.

    Args:
        com_position: COM 좌표 (x, y, z) cm
        keypoints_3d: 키포인트 3D (발목 위치)

    Returns:
        (좌측 비율, 우측 비율), 합 = 1.0

    참조:
        Winter (2009) Ch.7: Weight distribution estimation
    """
    if keypoints_3d.shape[0] <= max(_R_ANKLE_IDX, _L_ANKLE_IDX):
        return (0.5, 0.5)

    r_ankle_x = float(keypoints_3d[_R_ANKLE_IDX, 0])
    l_ankle_x = float(keypoints_3d[_L_ANKLE_IDX, 0])
    com_x = com_position[0]

    total_width = abs(r_ankle_x - l_ankle_x)
    if total_width < 1.0:  # 양발이 거의 같은 위치
        return (0.5, 0.5)

    # 좌/우 발목 결정 (x 좌표 기준 — 카메라 좌표계 독립)
    if l_ankle_x >= r_ankle_x:
        left_x, right_x = l_ankle_x, r_ankle_x
    else:
        left_x, right_x = r_ankle_x, l_ankle_x

    # COM 위치를 BoS 안으로 클램프 — 외부일 때 가까운 발에 100% 체중
    clamped_x = max(right_x, min(left_x, com_x))

    # 선형 보간 계수 (0=우, 1=좌)
    t = (clamped_x - right_x) / (left_x - right_x)
    w_left = float(t)
    w_right = float(1.0 - t)

    return (w_left, w_right)


# =============================================================================
# 동요(Sway) 분석
# =============================================================================

def calculate_sway(
    com_prev: tuple[float, float, float],
    com_curr: tuple[float, float, float],
    dt: float,
) -> SwayMetrics:
    """
    COM 동요 분석 (프레임 간).

    동요 거리/속도로 정적/동적 균형 상태를 판정합니다.

    Args:
        com_prev: 이전 프레임 COM (x, y, z) cm
        com_curr: 현재 프레임 COM (x, y, z) cm
        dt: 시간 간격 (초)

    Returns:
        SwayMetrics 객체

    참조:
        Prieto et al. (1996): COP/COM sway measures
    """
    # 수평 이동 거리 (x, z 평면)
    dx = com_curr[0] - com_prev[0]
    dz = com_curr[2] - com_prev[2]
    distance = (dx ** 2 + dz ** 2) ** 0.5

    velocity = distance / dt if dt >= _MIN_DT else 0.0

    # 분류
    if velocity <= COP_SWAY_STABLE_THRESHOLD_CM:
        category = "stable"
    elif velocity <= COP_SWAY_UNSTABLE_THRESHOLD_CM:
        category = "moderate"
    else:
        category = "unstable"

    return SwayMetrics(
        sway_distance_cm=distance,
        sway_velocity_cm_s=velocity,
        sway_category=category,
    )


# =============================================================================
# 통합 균형 분석
# =============================================================================

def analyze_balance(
    keypoints_3d: NDArray[np.float64],
    body_model: BodyModel,
) -> BalanceState | None:
    """
    프레임 단위 균형 분석.

    COM, BoS, 안정성 지수, 체중 분배를 종합적으로 산출합니다.

    Args:
        keypoints_3d: 3D 키포인트 좌표 (25×3/4, cm)
        body_model: 신체 모델

    Returns:
        BalanceState 객체, 계산 불가 시 None
    """
    com = calculate_com_position(keypoints_3d, body_model)
    if com is None:
        return None

    bos_area = calculate_bos_area(keypoints_3d)
    bos_width = calculate_bos_width(keypoints_3d)

    # BoS/어깨폭 비율
    shoulder_ratio = 0.0
    if keypoints_3d.shape[0] > max(_R_SHOULDER_IDX, _L_SHOULDER_IDX):
        r_sh = keypoints_3d[_R_SHOULDER_IDX, :3]
        l_sh = keypoints_3d[_L_SHOULDER_IDX, :3]
        shoulder_width = float(np.linalg.norm(r_sh - l_sh))
        if shoulder_width > 1.0:
            shoulder_ratio = bos_width / shoulder_width

    stability = calculate_stability_index(com, keypoints_3d, bos_width)
    is_stable = stability >= STABILITY_INDEX_MIN_STABLE
    weight_dist = estimate_weight_distribution(com, keypoints_3d)

    # COM 높이 (발목 기준, m)
    ankle_y = 0.0
    if keypoints_3d.shape[0] > max(_R_ANKLE_IDX, _L_ANKLE_IDX):
        ankle_y = (
            float(keypoints_3d[_R_ANKLE_IDX, 1])
            + float(keypoints_3d[_L_ANKLE_IDX, 1])
        ) / 2.0
    com_height_m = (com[1] - ankle_y) * _CM_TO_M
    if com_height_m < 0:
        com_height_m = 0.0

    return BalanceState(
        com_position=com,
        com_height_m=com_height_m,
        bos_area_cm2=bos_area,
        bos_width_cm=bos_width,
        bos_shoulder_ratio=shoulder_ratio,
        stability_index=stability,
        is_stable=is_stable,
        weight_distribution=weight_dist,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "BalanceState",
    "SwayMetrics",
    # COM 계산
    "calculate_com_position",
    # BoS 계산
    "calculate_bos_area",
    "calculate_bos_width",
    # 안정성
    "calculate_stability_index",
    # 체중 분배
    "estimate_weight_distribution",
    # 동요 분석
    "calculate_sway",
    # 통합 분석
    "analyze_balance",
]

__version__ = "1.0.0"
