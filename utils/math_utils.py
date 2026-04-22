# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: math_utils.py
설명: 수학 연산 유틸리티 - 각도 계산, 벡터 연산, 통계, 정규화

작성자: COURTVIEW AI Team
최종 수정: 2025-12-24

주요 기능:
    - 2D/3D 벡터 연산 (내적, 외적, 정규화)
    - 관절 각도 계산 (생체역학 분석용)
    - 통계 함수 (평균, 표준편차, 백분위수)
    - 값 정규화 및 클리핑
    - 보간 함수 (선형, 구면선형)
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

# ============================================================
# 서드파티 라이브러리
# ============================================================
import cv2
import numpy as np
from numpy.typing import NDArray


# ============================================================
# 타입 정의
# ============================================================
Vector2D = tuple[float, float]
Vector3D = tuple[float, float, float]
Point2D = Vector2D
Point3D = Vector3D


# ============================================================
# 상수 정의
# ============================================================
EPSILON: Final[float] = 1e-10  # 부동소수점 비교용 임계값
DEG_TO_RAD: Final[float] = math.pi / 180.0
RAD_TO_DEG: Final[float] = 180.0 / math.pi


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(frozen=True, slots=True)
class AngleResult:
    """각도 계산 결과."""

    degrees: float  # 각도 (도 단위)
    radians: float  # 각도 (라디안 단위)
    is_valid: bool  # 유효성 여부

    @classmethod
    def invalid(cls) -> "AngleResult":
        """유효하지 않은 각도 결과 생성."""
        return cls(degrees=0.0, radians=0.0, is_valid=False)


@dataclass(frozen=True, slots=True)
class StatisticsResult:
    """통계 계산 결과."""

    mean: float  # 평균
    std: float  # 표준편차
    min_val: float  # 최솟값
    max_val: float  # 최댓값
    median: float  # 중앙값
    count: int  # 데이터 개수

    @classmethod
    def empty(cls) -> "StatisticsResult":
        """빈 통계 결과 생성."""
        return cls(
            mean=0.0,
            std=0.0,
            min_val=0.0,
            max_val=0.0,
            median=0.0,
            count=0
        )


# ============================================================
# 각도 변환 함수
# ============================================================
def degrees_to_radians(degrees: float) -> float:
    """
    도(degree)를 라디안(radian)으로 변환.

    Args:
        degrees: 도 단위 각도

    Returns:
        라디안 단위 각도

    Example:
        >>> degrees_to_radians(180.0)
        3.141592653589793
    """
    return degrees * DEG_TO_RAD


def radians_to_degrees(radians: float) -> float:
    """
    라디안(radian)을 도(degree)로 변환.

    Args:
        radians: 라디안 단위 각도

    Returns:
        도 단위 각도

    Example:
        >>> radians_to_degrees(math.pi)
        180.0
    """
    return radians * RAD_TO_DEG


def normalize_angle_degrees(angle: float) -> float:
    """
    각도를 0-360 범위로 정규화.

    Args:
        angle: 정규화할 각도 (도 단위)

    Returns:
        0-360 범위의 각도

    Example:
        >>> normalize_angle_degrees(-90)
        270.0
        >>> normalize_angle_degrees(450)
        90.0
    """
    normalized = angle % 360.0
    if normalized < 0:
        normalized += 360.0
    return normalized


def normalize_angle_radians(angle: float) -> float:
    """
    각도를 0-2π 범위로 정규화.

    Args:
        angle: 정규화할 각도 (라디안 단위)

    Returns:
        0-2π 범위의 각도
    """
    two_pi = 2.0 * math.pi
    normalized = angle % two_pi
    if normalized < 0:
        normalized += two_pi
    return normalized


def angle_difference_degrees(angle1: float, angle2: float) -> float:
    """
    두 각도 간의 최소 차이 계산 (도 단위).

    Args:
        angle1: 첫 번째 각도 (도)
        angle2: 두 번째 각도 (도)

    Returns:
        -180 ~ 180 범위의 각도 차이

    Example:
        >>> angle_difference_degrees(350, 10)
        20.0
        >>> angle_difference_degrees(10, 350)
        -20.0
    """
    diff = (angle2 - angle1 + 180) % 360 - 180
    return diff


# ============================================================
# 벡터 연산 함수 (2D)
# ============================================================
def vector2d_magnitude(v: Vector2D) -> float:
    """
    2D 벡터의 크기(길이) 계산.

    Args:
        v: 2D 벡터 (x, y)

    Returns:
        벡터의 크기

    Example:
        >>> vector2d_magnitude((3.0, 4.0))
        5.0
    """
    return math.sqrt(v[0] ** 2 + v[1] ** 2)


def vector2d_normalize(v: Vector2D) -> Vector2D | None:
    """
    2D 벡터 정규화 (단위 벡터로 변환).

    Args:
        v: 2D 벡터 (x, y)

    Returns:
        정규화된 단위 벡터 또는 영벡터인 경우 None

    Example:
        >>> vector2d_normalize((3.0, 4.0))
        (0.6, 0.8)
    """
    magnitude = vector2d_magnitude(v)
    if magnitude < EPSILON:
        return None
    return (v[0] / magnitude, v[1] / magnitude)


def vector2d_dot(v1: Vector2D, v2: Vector2D) -> float:
    """
    2D 벡터의 내적(dot product) 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        내적 값

    Example:
        >>> vector2d_dot((1.0, 0.0), (0.0, 1.0))
        0.0
    """
    return v1[0] * v2[0] + v1[1] * v2[1]


def vector2d_cross(v1: Vector2D, v2: Vector2D) -> float:
    """
    2D 벡터의 외적(cross product) Z 성분 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        외적의 Z 성분 (스칼라)

    Note:
        양수: v1에서 v2로 반시계 방향
        음수: v1에서 v2로 시계 방향

    Example:
        >>> vector2d_cross((1.0, 0.0), (0.0, 1.0))
        1.0
    """
    return v1[0] * v2[1] - v1[1] * v2[0]


def vector2d_add(v1: Vector2D, v2: Vector2D) -> Vector2D:
    """
    2D 벡터 덧셈.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        합 벡터
    """
    return (v1[0] + v2[0], v1[1] + v2[1])


def vector2d_subtract(v1: Vector2D, v2: Vector2D) -> Vector2D:
    """
    2D 벡터 뺄셈 (v1 - v2).

    Args:
        v1: 피감수 벡터
        v2: 감수 벡터

    Returns:
        차 벡터
    """
    return (v1[0] - v2[0], v1[1] - v2[1])


def vector2d_scale(v: Vector2D, scalar: float) -> Vector2D:
    """
    2D 벡터 스칼라 곱.

    Args:
        v: 벡터
        scalar: 스칼라 값

    Returns:
        스케일된 벡터
    """
    return (v[0] * scalar, v[1] * scalar)


def vector2d_angle(v: Vector2D) -> float:
    """
    2D 벡터의 각도 계산 (x축 양의 방향 기준, 반시계 방향).

    Args:
        v: 2D 벡터

    Returns:
        각도 (도 단위, 0-360)
    """
    angle_rad = math.atan2(v[1], v[0])
    angle_deg = radians_to_degrees(angle_rad)
    return normalize_angle_degrees(angle_deg)


def vector2d_angle_between(v1: Vector2D, v2: Vector2D) -> AngleResult:
    """
    두 2D 벡터 사이의 각도 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        AngleResult: 각도 결과 (0-180도)

    Note:
        영벡터가 포함된 경우 is_valid=False 반환
    """
    mag1 = vector2d_magnitude(v1)
    mag2 = vector2d_magnitude(v2)

    if mag1 < EPSILON or mag2 < EPSILON:
        return AngleResult.invalid()

    dot = vector2d_dot(v1, v2)
    cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))  # 수치 안정성
    angle_rad = math.acos(cos_angle)
    angle_deg = radians_to_degrees(angle_rad)

    return AngleResult(degrees=angle_deg, radians=angle_rad, is_valid=True)


def vector2d_rotate(v: Vector2D, angle_degrees: float) -> Vector2D:
    """
    2D 벡터를 원점 기준으로 회전.

    Args:
        v: 회전할 벡터
        angle_degrees: 회전 각도 (도 단위, 반시계 방향 양수)

    Returns:
        회전된 벡터
    """
    angle_rad = degrees_to_radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    return (
        v[0] * cos_a - v[1] * sin_a,
        v[0] * sin_a + v[1] * cos_a
    )


def vector2d_perpendicular(v: Vector2D, clockwise: bool = False) -> Vector2D:
    """
    2D 벡터의 수직 벡터 계산.

    Args:
        v: 원본 벡터
        clockwise: True면 시계방향, False면 반시계방향 수직 벡터

    Returns:
        수직 벡터
    """
    if clockwise:
        return (v[1], -v[0])
    return (-v[1], v[0])


def vector2d_project(v: Vector2D, onto: Vector2D) -> Vector2D | None:
    """
    벡터 v를 onto 벡터에 투영.

    Args:
        v: 투영할 벡터
        onto: 투영 대상 벡터

    Returns:
        투영된 벡터 또는 onto가 영벡터인 경우 None
    """
    onto_mag_sq = vector2d_dot(onto, onto)
    if onto_mag_sq < EPSILON:
        return None

    scalar = vector2d_dot(v, onto) / onto_mag_sq
    return vector2d_scale(onto, scalar)


# ============================================================
# 벡터 연산 함수 (3D)
# ============================================================
def vector3d_magnitude(v: Vector3D) -> float:
    """
    3D 벡터의 크기(길이) 계산.

    Args:
        v: 3D 벡터 (x, y, z)

    Returns:
        벡터의 크기
    """
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def vector3d_normalize(v: Vector3D) -> Vector3D | None:
    """
    3D 벡터 정규화 (단위 벡터로 변환).

    Args:
        v: 3D 벡터 (x, y, z)

    Returns:
        정규화된 단위 벡터 또는 영벡터인 경우 None
    """
    magnitude = vector3d_magnitude(v)
    if magnitude < EPSILON:
        return None
    return (v[0] / magnitude, v[1] / magnitude, v[2] / magnitude)


def vector3d_dot(v1: Vector3D, v2: Vector3D) -> float:
    """
    3D 벡터의 내적(dot product) 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        내적 값
    """
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]


def vector3d_cross(v1: Vector3D, v2: Vector3D) -> Vector3D:
    """
    3D 벡터의 외적(cross product) 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        외적 벡터
    """
    return (
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0]
    )


def vector3d_add(v1: Vector3D, v2: Vector3D) -> Vector3D:
    """
    3D 벡터 덧셈.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        합 벡터
    """
    return (v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2])


def vector3d_subtract(v1: Vector3D, v2: Vector3D) -> Vector3D:
    """
    3D 벡터 뺄셈 (v1 - v2).

    Args:
        v1: 피감수 벡터
        v2: 감수 벡터

    Returns:
        차 벡터
    """
    return (v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2])


def vector3d_scale(v: Vector3D, scalar: float) -> Vector3D:
    """
    3D 벡터 스칼라 곱.

    Args:
        v: 벡터
        scalar: 스칼라 값

    Returns:
        스케일된 벡터
    """
    return (v[0] * scalar, v[1] * scalar, v[2] * scalar)


def vector3d_angle_between(v1: Vector3D, v2: Vector3D) -> AngleResult:
    """
    두 3D 벡터 사이의 각도 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        AngleResult: 각도 결과 (0-180도)
    """
    mag1 = vector3d_magnitude(v1)
    mag2 = vector3d_magnitude(v2)

    if mag1 < EPSILON or mag2 < EPSILON:
        return AngleResult.invalid()

    dot = vector3d_dot(v1, v2)
    cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    angle_rad = math.acos(cos_angle)
    angle_deg = radians_to_degrees(angle_rad)

    return AngleResult(degrees=angle_deg, radians=angle_rad, is_valid=True)


# ============================================================
# 관절 각도 계산 (생체역학)
# ============================================================
def calculate_joint_angle_2d(
    point_a: Point2D,
    point_b: Point2D,
    point_c: Point2D
) -> AngleResult:
    """
    세 점으로 정의되는 관절 각도 계산 (2D).

    point_b가 관절 위치이며, point_a-point_b-point_c가 이루는 각도 계산.

    Args:
        point_a: 첫 번째 끝점 (예: 어깨)
        point_b: 관절점 (예: 팔꿈치)
        point_c: 두 번째 끝점 (예: 손목)

    Returns:
        AngleResult: 관절 각도 (0-180도)

    Example:
        팔꿈치 각도 계산:
        >>> shoulder = (0.0, 0.0)
        >>> elbow = (1.0, 0.0)
        >>> wrist = (2.0, 1.0)
        >>> result = calculate_joint_angle_2d(shoulder, elbow, wrist)
        >>> result.degrees  # 약 45도
    """
    # 관절에서 각 끝점으로 향하는 벡터
    vec_ba = vector2d_subtract(point_a, point_b)
    vec_bc = vector2d_subtract(point_c, point_b)

    return vector2d_angle_between(vec_ba, vec_bc)


def calculate_joint_angle_3d(
    point_a: Point3D,
    point_b: Point3D,
    point_c: Point3D
) -> AngleResult:
    """
    세 점으로 정의되는 관절 각도 계산 (3D).

    Args:
        point_a: 첫 번째 끝점
        point_b: 관절점
        point_c: 두 번째 끝점

    Returns:
        AngleResult: 관절 각도 (0-180도)
    """
    vec_ba = vector3d_subtract(point_a, point_b)
    vec_bc = vector3d_subtract(point_c, point_b)

    return vector3d_angle_between(vec_ba, vec_bc)


def calculate_flexion_angle(
    proximal: Point2D,
    joint: Point2D,
    distal: Point2D
) -> float:
    """
    굴곡 각도(flexion angle) 계산.

    해부학적 위치에서의 굴곡 정도를 계산.
    완전히 펴진 상태(180도)에서 얼마나 굽혔는지 반환.

    Args:
        proximal: 몸통에 가까운 점
        joint: 관절점
        distal: 몸통에서 먼 점

    Returns:
        굴곡 각도 (0 = 완전 신전, 180 = 완전 굴곡)
    """
    result = calculate_joint_angle_2d(proximal, joint, distal)
    if not result.is_valid:
        return 0.0

    # 180도에서 관절 각도를 빼서 굴곡 정도 계산
    return 180.0 - result.degrees


def calculate_abduction_angle(
    body_midline: Point2D,
    joint: Point2D,
    limb_point: Point2D
) -> float:
    """
    외전 각도(abduction angle) 계산.

    신체 중심선에서 사지가 벌어진 정도를 계산.

    Args:
        body_midline: 신체 중심선 상의 점
        joint: 관절점 (예: 어깨)
        limb_point: 사지 끝점 (예: 팔꿈치)

    Returns:
        외전 각도 (0 = 몸에 붙어있음, 90 = 수평으로 벌림)
    """
    result = calculate_joint_angle_2d(body_midline, joint, limb_point)
    if not result.is_valid:
        return 0.0

    # 관절 각도가 외전 각도
    # 팔이 아래로 내려가면 0도에 가깝고, 수평이면 90도
    return min(result.degrees, 180.0 - result.degrees)


# ============================================================
# 통계 함수
# ============================================================
def calculate_statistics(values: Sequence[float]) -> StatisticsResult:
    """
    데이터 시퀀스의 기본 통계량 계산.

    Args:
        values: 숫자 시퀀스

    Returns:
        StatisticsResult: 통계 결과

    Example:
        >>> stats = calculate_statistics([1, 2, 3, 4, 5])
        >>> stats.mean
        3.0
        >>> stats.std  # 표준편차
        1.4142...
    """
    if not values:
        return StatisticsResult.empty()

    arr = np.array(values, dtype=np.float64)

    return StatisticsResult(
        mean=float(np.mean(arr)),
        std=float(np.std(arr)),
        min_val=float(np.min(arr)),
        max_val=float(np.max(arr)),
        median=float(np.median(arr)),
        count=len(values)
    )


def calculate_weighted_mean(
    values: Sequence[float],
    weights: Sequence[float]
) -> float | None:
    """
    가중 평균 계산.

    Args:
        values: 값 시퀀스
        weights: 가중치 시퀀스 (values와 길이 동일해야 함)

    Returns:
        가중 평균 또는 계산 불가 시 None
    """
    if not values or not weights or len(values) != len(weights):
        return None

    total_weight = sum(weights)
    if total_weight < EPSILON:
        return None

    weighted_sum = sum(v * w for v, w in zip(values, weights))
    return weighted_sum / total_weight


def calculate_percentile(values: Sequence[float], percentile: float) -> float | None:
    """
    백분위수 계산.

    Args:
        values: 값 시퀀스
        percentile: 백분위수 (0-100)

    Returns:
        해당 백분위수 값 또는 계산 불가 시 None
    """
    if not values or not (0 <= percentile <= 100):
        return None

    return float(np.percentile(values, percentile))


def calculate_moving_average(
    values: Sequence[float],
    window_size: int
) -> list[float]:
    """
    이동 평균 계산.

    Args:
        values: 값 시퀀스
        window_size: 윈도우 크기

    Returns:
        이동 평균 리스트 (원본보다 window_size-1 만큼 짧음)
    """
    if not values or window_size < 1 or window_size > len(values):
        return []

    arr = np.array(values, dtype=np.float64)
    cumsum = np.cumsum(arr)
    cumsum = np.insert(cumsum, 0, 0)

    return list((cumsum[window_size:] - cumsum[:-window_size]) / window_size)


def calculate_exponential_moving_average(
    values: Sequence[float],
    alpha: float
) -> list[float]:
    """
    지수 이동 평균(EMA) 계산.

    Args:
        values: 값 시퀀스
        alpha: 스무딩 계수 (0-1, 높을수록 최근 값에 가중치)

    Returns:
        지수 이동 평균 리스트
    """
    if not values or not (0 < alpha <= 1):
        return []

    result = []
    ema = values[0]
    result.append(ema)

    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema
        result.append(ema)

    return result


# ============================================================
# 정규화 및 클리핑 함수
# ============================================================
def normalize_value(
    value: float,
    min_val: float,
    max_val: float,
    new_min: float = 0.0,
    new_max: float = 1.0
) -> float:
    """
    값을 새로운 범위로 정규화.

    Args:
        value: 정규화할 값
        min_val: 원본 최솟값
        max_val: 원본 최댓값
        new_min: 새 범위 최솟값 (기본값: 0)
        new_max: 새 범위 최댓값 (기본값: 1)

    Returns:
        정규화된 값

    Example:
        >>> normalize_value(50, 0, 100, 0, 1)
        0.5
        >>> normalize_value(75, 0, 100, 0, 10)
        7.5
    """
    if abs(max_val - min_val) < EPSILON:
        return new_min

    normalized = (value - min_val) / (max_val - min_val)
    return new_min + normalized * (new_max - new_min)


def clip_value(value: float, min_val: float, max_val: float) -> float:
    """
    값을 지정된 범위로 클리핑.

    Args:
        value: 클리핑할 값
        min_val: 최솟값
        max_val: 최댓값

    Returns:
        클리핑된 값
    """
    return max(min_val, min(max_val, value))


def normalize_to_percentage(value: float, max_val: float) -> float:
    """
    값을 백분율(0-100)로 변환.

    Args:
        value: 변환할 값
        max_val: 최댓값 (100%에 해당)

    Returns:
        백분율 값 (0-100, 클리핑됨)
    """
    if max_val < EPSILON:
        return 0.0

    percentage = (value / max_val) * 100.0
    return clip_value(percentage, 0.0, 100.0)


def z_score_normalize(values: Sequence[float]) -> list[float]:
    """
    Z-score 정규화 (표준화).

    각 값을 (값 - 평균) / 표준편차로 변환.

    Args:
        values: 값 시퀀스

    Returns:
        Z-score 정규화된 값 리스트
    """
    if not values:
        return []

    arr = np.array(values, dtype=np.float64)
    mean = np.mean(arr)
    std = np.std(arr)

    if std < EPSILON:
        return [0.0] * len(values)

    return list((arr - mean) / std)


def min_max_normalize(values: Sequence[float]) -> list[float]:
    """
    Min-Max 정규화 (0-1 범위).

    Args:
        values: 값 시퀀스

    Returns:
        정규화된 값 리스트 (0-1 범위)
    """
    if not values:
        return []

    arr = np.array(values, dtype=np.float64)
    min_v = np.min(arr)
    max_v = np.max(arr)

    if abs(max_v - min_v) < EPSILON:
        return [0.5] * len(values)

    return list((arr - min_v) / (max_v - min_v))


# ============================================================
# 보간 함수
# ============================================================
def lerp(a: float, b: float, t: float) -> float:
    """
    선형 보간 (Linear Interpolation).

    Args:
        a: 시작 값
        b: 끝 값
        t: 보간 계수 (0-1)

    Returns:
        보간된 값

    Example:
        >>> lerp(0, 100, 0.5)
        50.0
        >>> lerp(0, 100, 0.25)
        25.0
    """
    return a + (b - a) * t


def lerp_vector2d(a: Vector2D, b: Vector2D, t: float) -> Vector2D:
    """
    2D 벡터의 선형 보간.

    Args:
        a: 시작 벡터
        b: 끝 벡터
        t: 보간 계수 (0-1)

    Returns:
        보간된 벡터
    """
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def lerp_vector3d(a: Vector3D, b: Vector3D, t: float) -> Vector3D:
    """
    3D 벡터의 선형 보간.

    Args:
        a: 시작 벡터
        b: 끝 벡터
        t: 보간 계수 (0-1)

    Returns:
        보간된 벡터
    """
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def inverse_lerp(a: float, b: float, value: float) -> float:
    """
    역 선형 보간 - 값이 a에서 b 사이 어디에 위치하는지 비율 계산.

    Args:
        a: 시작 값
        b: 끝 값
        value: 위치를 찾을 값

    Returns:
        비율 (0-1, 범위 밖이면 클리핑되지 않음)
    """
    if abs(b - a) < EPSILON:
        return 0.0
    return (value - a) / (b - a)


def smooth_step(edge0: float, edge1: float, x: float) -> float:
    """
    부드러운 보간 (Hermite 보간 기반).

    선형 보간보다 시작과 끝에서 부드러운 전환 제공.

    Args:
        edge0: 시작 에지
        edge1: 끝 에지
        x: 보간할 값

    Returns:
        부드럽게 보간된 값 (0-1)
    """
    t = clip_value((x - edge0) / (edge1 - edge0 + EPSILON), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def slerp_2d(a: Vector2D, b: Vector2D, t: float) -> Vector2D | None:
    """
    2D 벡터의 구면 선형 보간 (Spherical Linear Interpolation).

    회전 보간에 적합. 일정한 각속도로 보간됨.

    Args:
        a: 시작 벡터
        b: 끝 벡터
        t: 보간 계수 (0-1)

    Returns:
        보간된 단위 벡터 또는 영벡터인 경우 None
    """
    a_norm = vector2d_normalize(a)
    b_norm = vector2d_normalize(b)

    if a_norm is None or b_norm is None:
        return None

    dot = clip_value(vector2d_dot(a_norm, b_norm), -1.0, 1.0)

    # 거의 같은 방향이면 선형 보간
    if dot > 0.9995:
        result = lerp_vector2d(a_norm, b_norm, t)
        return vector2d_normalize(result)

    theta_0 = math.acos(dot)
    theta = theta_0 * t

    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)

    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0

    return (
        a_norm[0] * s0 + b_norm[0] * s1,
        a_norm[1] * s0 + b_norm[1] * s1
    )


# ============================================================
# 거리 및 유사도 함수
# ============================================================
def euclidean_distance_2d(p1: Point2D, p2: Point2D) -> float:
    """
    2D 유클리드 거리 계산.

    Args:
        p1: 첫 번째 점
        p2: 두 번째 점

    Returns:
        유클리드 거리
    """
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def euclidean_distance_3d(p1: Point3D, p2: Point3D) -> float:
    """
    3D 유클리드 거리 계산.

    Args:
        p1: 첫 번째 점
        p2: 두 번째 점

    Returns:
        유클리드 거리
    """
    return math.sqrt(
        (p2[0] - p1[0]) ** 2 +
        (p2[1] - p1[1]) ** 2 +
        (p2[2] - p1[2]) ** 2
    )


def manhattan_distance_2d(p1: Point2D, p2: Point2D) -> float:
    """
    2D 맨해튼 거리 계산.

    Args:
        p1: 첫 번째 점
        p2: 두 번째 점

    Returns:
        맨해튼 거리
    """
    return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float | None:
    """
    코사인 유사도 계산.

    Args:
        v1: 첫 번째 벡터
        v2: 두 번째 벡터

    Returns:
        코사인 유사도 (-1 ~ 1) 또는 계산 불가 시 None
    """
    if len(v1) != len(v2) or not v1:
        return None

    arr1 = np.array(v1, dtype=np.float64)
    arr2 = np.array(v2, dtype=np.float64)

    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 < EPSILON or norm2 < EPSILON:
        return None

    return float(np.dot(arr1, arr2) / (norm1 * norm2))


# ============================================================
# 기타 수학 함수
# ============================================================
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    안전한 나눗셈 (0으로 나누기 방지).

    Args:
        numerator: 분자
        denominator: 분모
        default: 분모가 0일 때 반환할 기본값

    Returns:
        나눗셈 결과 또는 기본값
    """
    if abs(denominator) < EPSILON:
        return default
    return numerator / denominator


def clamp_angle_degrees(angle: float, min_angle: float, max_angle: float) -> float:
    """
    각도를 지정된 범위로 제한 (각도 래핑 고려).

    Args:
        angle: 제한할 각도
        min_angle: 최소 각도
        max_angle: 최대 각도

    Returns:
        제한된 각도
    """
    # 먼저 0-360 범위로 정규화
    angle = normalize_angle_degrees(angle)
    min_angle = normalize_angle_degrees(min_angle)
    max_angle = normalize_angle_degrees(max_angle)

    # min이 max보다 크면 (예: 350-10 범위), 래핑 처리
    if min_angle > max_angle:
        if angle >= min_angle or angle <= max_angle:
            return angle
        # 가장 가까운 경계로 클램핑
        if angle - max_angle < min_angle - angle:
            return max_angle
        return min_angle

    return clip_value(angle, min_angle, max_angle)


def is_approximately_equal(
    a: float,
    b: float,
    tolerance: float = EPSILON
) -> bool:
    """
    두 부동소수점 값이 근사적으로 같은지 확인.

    Args:
        a: 첫 번째 값
        b: 두 번째 값
        tolerance: 허용 오차

    Returns:
        근사적으로 같으면 True
    """
    return abs(a - b) < tolerance


def sign(value: float) -> int:
    """
    값의 부호 반환.

    Args:
        value: 부호를 확인할 값

    Returns:
        1 (양수), -1 (음수), 0 (영)
    """
    if value > EPSILON:
        return 1
    elif value < -EPSILON:
        return -1
    return 0


def wrap_value(value: float, min_val: float, max_val: float) -> float:
    """
    값을 범위 내로 래핑 (순환).

    Args:
        value: 래핑할 값
        min_val: 최솟값
        max_val: 최댓값

    Returns:
        래핑된 값

    Example:
        >>> wrap_value(370, 0, 360)
        10.0
        >>> wrap_value(-10, 0, 360)
        350.0
    """
    range_val = max_val - min_val
    if range_val < EPSILON:
        return min_val

    wrapped = (value - min_val) % range_val
    if wrapped < 0:
        wrapped += range_val
    return wrapped + min_val


# ============================================================
# 3D 변환 및 투영 함수 (v3.0.0 멀티카메라 지원)
# ============================================================

def rodrigues_to_rotation_matrix(rvec: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    Rodrigues 벡터를 회전 행렬로 변환.

    Args:
        rvec: Rodrigues 회전 벡터 (3,) 또는 (3, 1)

    Returns:
        회전 행렬 (3, 3)

    Example:
        >>> rvec = np.array([0.1, 0.2, 0.3])
        >>> R = rodrigues_to_rotation_matrix(rvec)
        >>> R.shape
        (3, 3)
    """
    rvec = np.asarray(rvec, dtype=np.float64).reshape(3, 1)
    R, _ = cv2.Rodrigues(rvec)
    return R


def rotation_matrix_to_rodrigues(R: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    회전 행렬을 Rodrigues 벡터로 변환.

    Args:
        R: 회전 행렬 (3, 3)

    Returns:
        Rodrigues 회전 벡터 (3,)

    Example:
        >>> R = np.eye(3)
        >>> rvec = rotation_matrix_to_rodrigues(R)
        >>> rvec.shape
        (3,)
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    rvec, _ = cv2.Rodrigues(R)
    return rvec.flatten()


def homogeneous_to_cartesian(point_h: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    동차 좌표를 카테시안 좌표로 변환.

    Args:
        point_h: 동차 좌표 (n+1,) 예: [x, y, w] 또는 [x, y, z, w]

    Returns:
        카테시안 좌표 (n,) 예: [x/w, y/w] 또는 [x/w, y/w, z/w]

    Example:
        >>> point_h = np.array([100, 200, 2])
        >>> point = homogeneous_to_cartesian(point_h)
        >>> point
        array([50., 100.])
    """
    point_h = np.asarray(point_h, dtype=np.float64)
    w = point_h[-1]
    if abs(w) < EPSILON:
        return point_h[:-1]  # w가 0에 가까우면 그대로 반환
    return point_h[:-1] / w


def cartesian_to_homogeneous(point: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    카테시안 좌표를 동차 좌표로 변환.

    Args:
        point: 카테시안 좌표 (n,) 예: [x, y] 또는 [x, y, z]

    Returns:
        동차 좌표 (n+1,) 예: [x, y, 1] 또는 [x, y, z, 1]

    Example:
        >>> point = np.array([50, 100])
        >>> point_h = cartesian_to_homogeneous(point)
        >>> point_h
        array([50., 100., 1.])
    """
    point = np.asarray(point, dtype=np.float64)
    return np.append(point, 1.0)


def apply_homography(
    H: NDArray[np.float64],
    point: NDArray[np.float32],
) -> NDArray[np.float32]:
    """
    호모그래피 변환 적용.

    Args:
        H: 호모그래피 행렬 (3, 3)
        point: 2D 포인트 (2,) 또는 (N, 2)

    Returns:
        변환된 2D 포인트 (2,) 또는 (N, 2)

    Example:
        >>> H = np.eye(3)
        >>> point = np.array([100, 200], dtype=np.float32)
        >>> result = apply_homography(H, point)
        >>> result
        array([100., 200.], dtype=float32)
    """
    point = np.asarray(point, dtype=np.float32)
    H = np.asarray(H, dtype=np.float64)

    if point.ndim == 1:
        # 단일 포인트
        point_h = np.array([point[0], point[1], 1.0], dtype=np.float64)
        result_h = H @ point_h
        if abs(result_h[2]) < EPSILON:
            return point
        result = result_h[:2] / result_h[2]
        return result.astype(np.float32)
    else:
        # 다중 포인트
        ones = np.ones((point.shape[0], 1), dtype=np.float64)
        points_h = np.hstack([point.astype(np.float64), ones])
        results_h = (H @ points_h.T).T
        w = results_h[:, 2:3]
        w[np.abs(w) < EPSILON] = 1.0
        results = results_h[:, :2] / w
        return results.astype(np.float32)


def apply_affine_transform(
    matrix: NDArray[np.float64],
    point: NDArray[np.float32],
) -> NDArray[np.float32]:
    """
    아핀 변환 적용.

    Args:
        matrix: 아핀 변환 행렬 (2, 3) 또는 (3, 3)
        point: 2D 포인트 (2,) 또는 (N, 2)

    Returns:
        변환된 2D 포인트 (2,) 또는 (N, 2)

    Example:
        >>> # 평행이동 행렬 (x+10, y+20)
        >>> M = np.array([[1, 0, 10], [0, 1, 20]], dtype=np.float64)
        >>> point = np.array([100, 200], dtype=np.float32)
        >>> result = apply_affine_transform(M, point)
        >>> result
        array([110., 220.], dtype=float32)
    """
    point = np.asarray(point, dtype=np.float32)
    matrix = np.asarray(matrix, dtype=np.float64)

    # (3, 3) 행렬인 경우 (2, 3)으로 변환
    if matrix.shape == (3, 3):
        matrix = matrix[:2, :]

    if point.ndim == 1:
        # 단일 포인트
        point_h = np.array([point[0], point[1], 1.0], dtype=np.float64)
        result = matrix @ point_h
        return result.astype(np.float32)
    else:
        # 다중 포인트
        ones = np.ones((point.shape[0], 1), dtype=np.float64)
        points_h = np.hstack([point.astype(np.float64), ones])
        results = (matrix @ points_h.T).T
        return results.astype(np.float32)


# ============================================================
# 회전 변환 함수 (오일러, 쿼터니언)
# ============================================================

def euler_to_rotation_matrix(
    roll: float,
    pitch: float,
    yaw: float,
    order: str = "xyz"
) -> NDArray[np.float64]:
    """
    오일러 각도를 회전 행렬로 변환.

    Args:
        roll: X축 회전 (라디안)
        pitch: Y축 회전 (라디안)
        yaw: Z축 회전 (라디안)
        order: 회전 순서 ("xyz", "zyx", "zxy" 등)

    Returns:
        회전 행렬 (3, 3)

    Note:
        내적 회전(intrinsic rotation) 사용.
        오른손 좌표계 기준.

    Example:
        >>> R = euler_to_rotation_matrix(0.1, 0.2, 0.3)
        >>> R.shape
        (3, 3)
        >>> np.allclose(np.linalg.det(R), 1.0)
        True
    """
    # 각 축별 회전 행렬
    cos_r, sin_r = math.cos(roll), math.sin(roll)
    cos_p, sin_p = math.cos(pitch), math.sin(pitch)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    # X축 회전 (Roll)
    Rx = np.array([
        [1, 0, 0],
        [0, cos_r, -sin_r],
        [0, sin_r, cos_r]
    ], dtype=np.float64)

    # Y축 회전 (Pitch)
    Ry = np.array([
        [cos_p, 0, sin_p],
        [0, 1, 0],
        [-sin_p, 0, cos_p]
    ], dtype=np.float64)

    # Z축 회전 (Yaw)
    Rz = np.array([
        [cos_y, -sin_y, 0],
        [sin_y, cos_y, 0],
        [0, 0, 1]
    ], dtype=np.float64)

    # 회전 순서에 따라 조합
    rotation_map = {"x": Rx, "y": Ry, "z": Rz}
    order_lower = order.lower()

    if len(order_lower) != 3 or not all(c in "xyz" for c in order_lower):
        # 기본값 xyz
        return Rz @ Ry @ Rx

    R = np.eye(3, dtype=np.float64)
    for axis in order_lower:
        R = R @ rotation_map[axis]

    return R


def rotation_matrix_to_euler(
    R: NDArray[np.float64],
    order: str = "xyz"
) -> tuple[float, float, float]:
    """
    회전 행렬을 오일러 각도로 변환.

    Args:
        R: 회전 행렬 (3, 3)
        order: 회전 순서 ("xyz", "zyx" 등)

    Returns:
        (roll, pitch, yaw) 라디안 튜플

    Note:
        Gimbal lock 근처에서는 수치 불안정성 발생 가능.

    Example:
        >>> R = np.eye(3)
        >>> roll, pitch, yaw = rotation_matrix_to_euler(R)
        >>> np.isclose(roll, 0) and np.isclose(pitch, 0) and np.isclose(yaw, 0)
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    order_lower = order.lower()

    if order_lower == "xyz":
        # XYZ 오일러 각도 추출
        # R = Rz * Ry * Rx
        sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

        if sy > EPSILON:
            roll = math.atan2(R[2, 1], R[2, 2])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = math.atan2(R[1, 0], R[0, 0])
        else:
            # Gimbal lock
            roll = math.atan2(-R[1, 2], R[1, 1])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = 0.0

        return (roll, pitch, yaw)

    elif order_lower == "zyx":
        # ZYX 오일러 각도 추출 (항공/해양 관례)
        cy = math.sqrt(R[0, 0] ** 2 + R[0, 1] ** 2)

        if cy > EPSILON:
            roll = math.atan2(R[1, 2], R[2, 2])
            pitch = math.atan2(-R[0, 2], cy)
            yaw = math.atan2(R[0, 1], R[0, 0])
        else:
            # Gimbal lock
            roll = math.atan2(-R[2, 1], R[1, 1])
            pitch = math.atan2(-R[0, 2], cy)
            yaw = 0.0

        return (roll, pitch, yaw)

    else:
        # 기본값: XYZ
        return rotation_matrix_to_euler(R, "xyz")


def quaternion_to_rotation_matrix(
    q: tuple[float, float, float, float] | NDArray[np.float64]
) -> NDArray[np.float64]:
    """
    쿼터니언을 회전 행렬로 변환.

    Args:
        q: 쿼터니언 (w, x, y, z) 또는 (x, y, z, w) 형식 배열
           기본적으로 (w, x, y, z) 형식 사용 (스칼라 먼저)

    Returns:
        회전 행렬 (3, 3)

    Note:
        쿼터니언은 자동으로 정규화됩니다.

    Example:
        >>> q = (1.0, 0.0, 0.0, 0.0)  # 항등 회전
        >>> R = quaternion_to_rotation_matrix(q)
        >>> np.allclose(R, np.eye(3))
        True
    """
    q = np.asarray(q, dtype=np.float64).flatten()

    if len(q) != 4:
        raise ValueError("쿼터니언은 4개의 요소를 가져야 합니다.")

    # 정규화
    norm = np.linalg.norm(q)
    if norm < EPSILON:
        return np.eye(3, dtype=np.float64)
    q = q / norm

    w, x, y, z = q[0], q[1], q[2], q[3]

    # 회전 행렬 계산
    R = np.array([
        [1 - 2*(y**2 + z**2), 2*(x*y - w*z), 2*(x*z + w*y)],
        [2*(x*y + w*z), 1 - 2*(x**2 + z**2), 2*(y*z - w*x)],
        [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x**2 + y**2)]
    ], dtype=np.float64)

    return R


# ============================================================
# 행렬 분해 및 선형대수 함수 (멀티카메라 3D 분석용)
# ============================================================

def svd_decomposition(
    matrix: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """
    특이값 분해 (Singular Value Decomposition).

    행렬 A를 U @ S @ Vt로 분해.

    Args:
        matrix: 분해할 행렬 (M, N)

    Returns:
        (U, S, Vt) 튜플
        - U: 좌 특이벡터 (M, M) 또는 (M, K) full_matrices=False
        - S: 특이값 (min(M, N),)
        - Vt: 우 특이벡터의 전치 (N, N) 또는 (K, N)

    Example:
        >>> A = np.array([[1, 2], [3, 4], [5, 6]], dtype=np.float64)
        >>> U, S, Vt = svd_decomposition(A)
        >>> reconstructed = U @ np.diag(S) @ Vt[:2, :]
        >>> np.allclose(A, reconstructed)
        True
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    U, S, Vt = np.linalg.svd(matrix, full_matrices=False)
    return U, S, Vt


def matrix_rank(
    matrix: NDArray[np.float64],
    tolerance: float | None = None
) -> int:
    """
    행렬의 랭크(계수) 계산.

    특이값을 기반으로 수치적 랭크 결정.

    Args:
        matrix: 랭크를 계산할 행렬
        tolerance: 특이값 임계치 (None이면 자동 계산)

    Returns:
        행렬 랭크

    Example:
        >>> A = np.array([[1, 2], [2, 4]], dtype=np.float64)  # 랭크 1
        >>> matrix_rank(A)
        1
        >>> B = np.array([[1, 0], [0, 1]], dtype=np.float64)  # 랭크 2
        >>> matrix_rank(B)
        2
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    return int(np.linalg.matrix_rank(matrix, tol=tolerance))


def enforce_rank_constraint(
    matrix: NDArray[np.float64],
    target_rank: int
) -> NDArray[np.float64]:
    """
    행렬에 랭크 제약 강제 (SVD 기반).

    기본 행렬(Fundamental Matrix) 또는 필수 행렬(Essential Matrix)의
    랭크 2 제약 등에 사용.

    Args:
        matrix: 원본 행렬
        target_rank: 목표 랭크

    Returns:
        목표 랭크로 제약된 행렬

    Example:
        >>> # 랭크 2로 제약
        >>> F = np.random.randn(3, 3)
        >>> F_constrained = enforce_rank_constraint(F, 2)
        >>> matrix_rank(F_constrained)
        2
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    U, S, Vt = np.linalg.svd(matrix, full_matrices=True)

    # 목표 랭크 이후의 특이값을 0으로 설정
    S_constrained = np.zeros_like(S)
    actual_rank = min(target_rank, len(S))
    S_constrained[:actual_rank] = S[:actual_rank]

    # 재구성
    m, n = matrix.shape
    S_matrix = np.zeros((m, n), dtype=np.float64)
    np.fill_diagonal(S_matrix, S_constrained)

    return U @ S_matrix @ Vt


def pseudo_inverse(
    matrix: NDArray[np.float64],
    rcond: float = 1e-15
) -> NDArray[np.float64]:
    """
    무어-펜로즈 의사역행렬 계산.

    비정방행렬 또는 특이행렬의 역행렬 근사.

    Args:
        matrix: 의사역행렬을 계산할 행렬
        rcond: 상대적 조건수 임계치 (작은 특이값 무시)

    Returns:
        의사역행렬

    Example:
        >>> A = np.array([[1, 2], [3, 4], [5, 6]], dtype=np.float64)
        >>> A_pinv = pseudo_inverse(A)
        >>> A_pinv.shape
        (2, 3)
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    return np.linalg.pinv(matrix, rcond=rcond)


def covariance_intersection(
    mean1: NDArray[np.float64],
    cov1: NDArray[np.float64],
    mean2: NDArray[np.float64],
    cov2: NDArray[np.float64],
    omega: float | None = None
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    공분산 교차 (Covariance Intersection) 알고리즘.

    상관관계를 알 수 없는 두 추정치를 융합.
    멀티카메라 센서 융합에 사용.

    Args:
        mean1: 첫 번째 추정 평균 (n,)
        cov1: 첫 번째 추정 공분산 (n, n)
        mean2: 두 번째 추정 평균 (n,)
        cov2: 두 번째 추정 공분산 (n, n)
        omega: 가중치 (0-1), None이면 최적값 자동 계산

    Returns:
        (fused_mean, fused_cov) 융합된 평균과 공분산

    Example:
        >>> mean1 = np.array([1.0, 2.0])
        >>> cov1 = np.eye(2) * 0.5
        >>> mean2 = np.array([1.2, 1.8])
        >>> cov2 = np.eye(2) * 0.3
        >>> fused_mean, fused_cov = covariance_intersection(mean1, cov1, mean2, cov2)
    """
    mean1 = np.asarray(mean1, dtype=np.float64).flatten()
    mean2 = np.asarray(mean2, dtype=np.float64).flatten()
    cov1 = np.asarray(cov1, dtype=np.float64)
    cov2 = np.asarray(cov2, dtype=np.float64)

    if omega is None:
        # 최적 omega 탐색 (트레이스 최소화)
        # 간단한 그리드 서치
        best_omega = 0.5
        best_trace = float('inf')

        for w in np.linspace(0.01, 0.99, 99):
            try:
                cov_inv1 = np.linalg.inv(cov1)
                cov_inv2 = np.linalg.inv(cov2)
                fused_cov_inv = w * cov_inv1 + (1 - w) * cov_inv2
                fused_cov = np.linalg.inv(fused_cov_inv)
                trace = np.trace(fused_cov)
                if trace < best_trace:
                    best_trace = trace
                    best_omega = w
            except np.linalg.LinAlgError:
                continue

        omega = best_omega

    try:
        cov_inv1 = np.linalg.inv(cov1)
        cov_inv2 = np.linalg.inv(cov2)

        # 융합된 공분산
        fused_cov_inv = omega * cov_inv1 + (1 - omega) * cov_inv2
        fused_cov = np.linalg.inv(fused_cov_inv)

        # 융합된 평균
        fused_mean = fused_cov @ (omega * cov_inv1 @ mean1 + (1 - omega) * cov_inv2 @ mean2)

        return fused_mean, fused_cov

    except np.linalg.LinAlgError:
        # 역행렬 계산 실패 시 단순 가중평균
        fused_mean = omega * mean1 + (1 - omega) * mean2
        fused_cov = omega * cov1 + (1 - omega) * cov2
        return fused_mean, fused_cov


# ============================================================
# NDArray 벡터 연산 함수
# ============================================================

def normalize_vector(v: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    NDArray 벡터 정규화 (단위 벡터로 변환).

    Args:
        v: 정규화할 벡터 (n,)

    Returns:
        정규화된 단위 벡터 (n,)
        영벡터인 경우 원본 반환

    Example:
        >>> v = np.array([3.0, 4.0])
        >>> v_norm = normalize_vector(v)
        >>> np.allclose(v_norm, [0.6, 0.8])
        True
    """
    v = np.asarray(v, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm < EPSILON:
        return v
    return v / norm


def cross_product(v1: NDArray[np.float64], v2: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    3D 벡터 외적 (NDArray 버전).

    Args:
        v1: 첫 번째 3D 벡터 (3,)
        v2: 두 번째 3D 벡터 (3,)

    Returns:
        외적 결과 벡터 (3,)

    Example:
        >>> v1 = np.array([1.0, 0.0, 0.0])
        >>> v2 = np.array([0.0, 1.0, 0.0])
        >>> cross = cross_product(v1, v2)
        >>> np.allclose(cross, [0, 0, 1])
        True
    """
    v1 = np.asarray(v1, dtype=np.float64).flatten()[:3]
    v2 = np.asarray(v2, dtype=np.float64).flatten()[:3]
    return np.cross(v1, v2)


def dot_product(v1: NDArray[np.float64], v2: NDArray[np.float64]) -> float:
    """
    벡터 내적 (NDArray 버전).

    Args:
        v1: 첫 번째 벡터 (n,)
        v2: 두 번째 벡터 (n,)

    Returns:
        내적 값 (스칼라)

    Example:
        >>> v1 = np.array([1.0, 2.0, 3.0])
        >>> v2 = np.array([4.0, 5.0, 6.0])
        >>> dot_product(v1, v2)
        32.0
    """
    v1 = np.asarray(v1, dtype=np.float64).flatten()
    v2 = np.asarray(v2, dtype=np.float64).flatten()
    return float(np.dot(v1, v2))


def weighted_average(
    values: NDArray[np.float64],
    weights: NDArray[np.float64],
    axis: int | None = None
) -> NDArray[np.float64]:
    """
    가중 평균 계산 (NDArray 버전).

    Args:
        values: 값 배열 (n,) 또는 (m, n)
        weights: 가중치 배열 (values와 동일 형태 또는 브로드캐스트 가능)
        axis: 평균 계산 축 (None이면 전체 평균)

    Returns:
        가중 평균 결과

    Example:
        >>> values = np.array([1.0, 2.0, 3.0, 4.0])
        >>> weights = np.array([1.0, 2.0, 3.0, 4.0])
        >>> weighted_average(values, weights)
        array(3.)
    """
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)

    # 가중치 합이 0인 경우 처리
    weight_sum = np.sum(weights, axis=axis, keepdims=True)
    weight_sum = np.where(np.abs(weight_sum) < EPSILON, 1.0, weight_sum)

    return np.sum(values * weights, axis=axis) / weight_sum.squeeze()


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # 타입
    "Vector2D",
    "Vector3D",
    "Point2D",
    "Point3D",
    # 상수
    "EPSILON",
    "DEG_TO_RAD",
    "RAD_TO_DEG",
    # 데이터 클래스
    "AngleResult",
    "StatisticsResult",
    # 각도 변환
    "degrees_to_radians",
    "radians_to_degrees",
    "normalize_angle_degrees",
    "normalize_angle_radians",
    "angle_difference_degrees",
    # 2D 벡터
    "vector2d_magnitude",
    "vector2d_normalize",
    "vector2d_dot",
    "vector2d_cross",
    "vector2d_add",
    "vector2d_subtract",
    "vector2d_scale",
    "vector2d_angle",
    "vector2d_angle_between",
    "vector2d_rotate",
    "vector2d_perpendicular",
    "vector2d_project",
    # 3D 벡터
    "vector3d_magnitude",
    "vector3d_normalize",
    "vector3d_dot",
    "vector3d_cross",
    "vector3d_add",
    "vector3d_subtract",
    "vector3d_scale",
    "vector3d_angle_between",
    # 관절 각도
    "calculate_joint_angle_2d",
    "calculate_joint_angle_3d",
    "calculate_flexion_angle",
    "calculate_abduction_angle",
    # 통계
    "calculate_statistics",
    "calculate_weighted_mean",
    "calculate_percentile",
    "calculate_moving_average",
    "calculate_exponential_moving_average",
    # 정규화
    "normalize_value",
    "clip_value",
    "normalize_to_percentage",
    "z_score_normalize",
    "min_max_normalize",
    # 보간
    "lerp",
    "lerp_vector2d",
    "lerp_vector3d",
    "inverse_lerp",
    "smooth_step",
    "slerp_2d",
    # 거리/유사도
    "euclidean_distance_2d",
    "euclidean_distance_3d",
    "manhattan_distance_2d",
    "cosine_similarity",
    # 기타
    "safe_divide",
    "clamp_angle_degrees",
    "is_approximately_equal",
    "sign",
    "wrap_value",
    # 3D 변환 및 투영 (v3.0.0)
    "rodrigues_to_rotation_matrix",
    "rotation_matrix_to_rodrigues",
    "homogeneous_to_cartesian",
    "cartesian_to_homogeneous",
    "apply_homography",
    "apply_affine_transform",
    # 회전 변환 (오일러, 쿼터니언)
    "euler_to_rotation_matrix",
    "rotation_matrix_to_euler",
    "quaternion_to_rotation_matrix",
    # 행렬 분해 및 선형대수 (멀티카메라 3D 분석)
    "svd_decomposition",
    "matrix_rank",
    "enforce_rank_constraint",
    "pseudo_inverse",
    "covariance_intersection",
    # NDArray 벡터 연산
    "normalize_vector",
    "cross_product",
    "dot_product",
    "weighted_average",
]

__version__: str = "1.0.0"
