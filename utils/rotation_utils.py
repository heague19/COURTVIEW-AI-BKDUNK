# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: rotation_utils.py
설명: 3D 회전 연산 유틸리티
      - 5가지 회전 표현계 완전 상호 변환 (행렬, 쿼터니언, 오일러, 로드리게스, 축-각도)
      - 회전 합성, 보간(SLERP), 거리 메트릭
      - SO(3) 검증/정규화, 각속도 추정
      - 배치 연산 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - 축-각도 ↔ 회전행렬 ↔ 쿼터니언 ↔ 오일러 ↔ 로드리게스 상호 변환
    - 쿼터니언 대수 (곱, 역, 켤레, SLERP)
    - 회전 합성 및 상대 회전
    - 회전 거리 메트릭 (측지 거리, 각도 오차)
    - SO(3) 정규화 및 검증
    - 시간 기반 각속도 추정
    - 배치 변환 (N개 동시 처리)

사용 예시:
    >>> from utils.rotation_utils import (
    ...     axis_angle_to_rotation_matrix,
    ...     quaternion_slerp,
    ...     rotation_distance,
    ... )
    >>> import numpy as np
    >>> R = axis_angle_to_rotation_matrix(np.array([0, 0, 1]), np.pi / 4)
    >>> R.shape
    (3, 3)
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import math
from dataclasses import dataclass, field
from enum import Enum, unique

# === 서드파티 라이브러리 ===
import cv2
import numpy as np
from numpy.typing import NDArray


# === 로거 설정 ===
import logging

logger = logging.getLogger(__name__)


# === 상수 정의 ===

# 부동소수점 비교용 임계값
_EPSILON: float = 1e-10

# Gimbal lock 감지 임계값 (cos(pitch) ≈ 0)
GIMBAL_LOCK_THRESHOLD: float = 1e-6

# 쿼터니언 정규화 허용 오차
QUATERNION_NORM_TOLERANCE: float = 1e-6

# SO(3) 직교성 허용 오차
ORTHOGONALITY_TOLERANCE: float = 1e-6

# 행렬식 허용 오차 (det(R) ≈ 1)
DETERMINANT_TOLERANCE: float = 1e-6

# 최대 배치 크기 (메모리 보호)
_MAX_BATCH_SIZE: int = 100_000

# SLERP 선형 근사 임계값 (각도가 매우 작을 때)
_SLERP_LINEAR_THRESHOLD: float = 1e-6


# === Enum 정의 ===

@unique
class RotationOrder(Enum):
    """오일러 각도 회전 순서."""

    XYZ = "xyz"
    XZY = "xzy"
    YXZ = "yxz"
    YZX = "yzx"
    ZXY = "zxy"
    ZYX = "zyx"  # 항공/해양 관례


@unique
class RotationFormat(Enum):
    """회전 표현 형식."""

    MATRIX = "matrix"          # 3x3 회전 행렬
    QUATERNION = "quaternion"  # (w, x, y, z) 쿼터니언
    EULER = "euler"            # (roll, pitch, yaw) 오일러
    RODRIGUES = "rodrigues"    # 3D 로드리게스 벡터
    AXIS_ANGLE = "axis_angle"  # (axis, angle) 축-각도


# === 데이터 클래스 ===

@dataclass(slots=True)
class AxisAngle:
    """
    축-각도 회전 표현.

    Attributes:
        axis: 회전축 단위 벡터 (3,)
        angle: 회전 각도 (라디안)
    """

    axis: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0], dtype=np.float64)
    )
    angle: float = 0.0

    def __repr__(self) -> str:
        ax = np.array2string(self.axis, precision=4, separator=", ")
        return f"AxisAngle(axis={ax}, angle={self.angle:.4f} rad)"

    @classmethod
    def identity(cls) -> AxisAngle:
        """항등 회전 (회전 없음)."""
        return cls(
            axis=np.array([0.0, 0.0, 1.0], dtype=np.float64),
            angle=0.0,
        )


@dataclass(slots=True)
class Quaternion:
    """
    단위 쿼터니언 회전 표현 (스칼라-먼저 규약: w, x, y, z).

    Attributes:
        w: 스칼라 성분
        x: 벡터 i 성분
        y: 벡터 j 성분
        z: 벡터 k 성분
    """

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __repr__(self) -> str:
        return f"Quaternion(w={self.w:.6f}, x={self.x:.6f}, y={self.y:.6f}, z={self.z:.6f})"

    @property
    def norm(self) -> float:
        """쿼터니언 노름."""
        return math.sqrt(self.w ** 2 + self.x ** 2 + self.y ** 2 + self.z ** 2)

    @property
    def as_array(self) -> NDArray[np.float64]:
        """(w, x, y, z) numpy 배열로 변환."""
        return np.array([self.w, self.x, self.y, self.z], dtype=np.float64)

    @classmethod
    def identity(cls) -> Quaternion:
        """항등 쿼터니언 (회전 없음)."""
        return cls(w=1.0, x=0.0, y=0.0, z=0.0)

    @classmethod
    def from_array(cls, arr: NDArray[np.float64]) -> Quaternion:
        """(w, x, y, z) 배열에서 생성."""
        arr = np.asarray(arr, dtype=np.float64).flatten()
        if len(arr) != 4:
            raise ValueError(f"쿼터니언은 4개 요소 필요, {len(arr)}개 받음")
        return cls(w=float(arr[0]), x=float(arr[1]), y=float(arr[2]), z=float(arr[3]))


@dataclass(slots=True)
class AngularVelocity:
    """
    각속도 벡터.

    Attributes:
        omega: 각속도 벡터 (rad/s) — 방향이 회전축, 크기가 각속도
        magnitude: 각속도 크기 (rad/s)
        dt: 시간 간격 (s)
    """

    omega: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    magnitude: float = 0.0
    dt: float = 0.0

    def __repr__(self) -> str:
        om = np.array2string(self.omega, precision=4, separator=", ")
        return f"AngularVelocity(omega={om}, |ω|={self.magnitude:.4f} rad/s, dt={self.dt:.4f}s)"


@dataclass(slots=True)
class RotationDistance:
    """
    두 회전 사이의 거리 측정 결과.

    Attributes:
        geodesic: 측지 거리 (라디안, 0 ~ π)
        degrees: 각도 차이 (도)
        frobenius: 프로베니우스 노름 거리
    """

    geodesic: float = 0.0
    degrees: float = 0.0
    frobenius: float = 0.0

    def __repr__(self) -> str:
        return (
            f"RotationDistance(geodesic={self.geodesic:.6f} rad, "
            f"degrees={self.degrees:.2f}°, frobenius={self.frobenius:.6f})"
        )


# =============================================================================
# 축-각도 변환
# =============================================================================

def axis_angle_to_rotation_matrix(
    axis: NDArray[np.float64],
    angle: float,
) -> NDArray[np.float64]:
    """
    축-각도를 회전 행렬로 변환 (Rodrigues 공식).

    Args:
        axis: 회전축 벡터 (3,) — 자동 정규화됨
        angle: 회전 각도 (라디안)

    Returns:
        회전 행렬 (3, 3)

    Example:
        >>> axis = np.array([0.0, 0.0, 1.0])
        >>> R = axis_angle_to_rotation_matrix(axis, np.pi / 2)
        >>> np.allclose(R @ np.array([1, 0, 0]), np.array([0, 1, 0]), atol=1e-10)
        True
    """
    axis = np.asarray(axis, dtype=np.float64).flatten()
    if axis.shape[0] != 3:
        raise ValueError(f"축 벡터는 3차원이어야 합니다, {axis.shape[0]}차원 받음")

    # 축 정규화
    norm = np.linalg.norm(axis)
    if norm < _EPSILON:
        return np.eye(3, dtype=np.float64)
    k = axis / norm

    # Rodrigues 공식: R = I + sin(θ)·K + (1 - cos(θ))·K²
    # K = skew-symmetric matrix of k
    K = np.array([
        [0.0, -k[2], k[1]],
        [k[2], 0.0, -k[0]],
        [-k[1], k[0], 0.0],
    ], dtype=np.float64)

    c = math.cos(angle)
    s = math.sin(angle)

    R = np.eye(3, dtype=np.float64) + s * K + (1.0 - c) * (K @ K)
    return R


def rotation_matrix_to_axis_angle(
    R: NDArray[np.float64],
) -> AxisAngle:
    """
    회전 행렬을 축-각도로 변환.

    Args:
        R: 회전 행렬 (3, 3)

    Returns:
        AxisAngle 데이터클래스

    Example:
        >>> R = np.eye(3)
        >>> aa = rotation_matrix_to_axis_angle(R)
        >>> np.isclose(aa.angle, 0.0)
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)

    # 회전 각도: cos(θ) = (tr(R) - 1) / 2
    trace_val = np.trace(R)
    cos_angle = np.clip((trace_val - 1.0) / 2.0, -1.0, 1.0)
    angle = math.acos(cos_angle)

    if abs(angle) < _EPSILON:
        # 거의 항등 회전
        return AxisAngle.identity()

    if abs(angle - math.pi) < _EPSILON:
        # 180도 회전 — 특수 처리
        # R + I의 열 중 노름이 가장 큰 것을 사용
        S = R + np.eye(3, dtype=np.float64)
        col_norms = np.linalg.norm(S, axis=0)
        best_col = int(np.argmax(col_norms))
        axis = S[:, best_col]
        axis = axis / np.linalg.norm(axis)
        return AxisAngle(axis=axis, angle=math.pi)

    # 일반 케이스: k = (R - R^T) / (2·sin(θ))의 비대칭 성분 추출
    sin_angle = math.sin(angle)
    axis = np.array([
        R[2, 1] - R[1, 2],
        R[0, 2] - R[2, 0],
        R[1, 0] - R[0, 1],
    ], dtype=np.float64) / (2.0 * sin_angle)

    return AxisAngle(axis=axis, angle=angle)


def axis_angle_to_quaternion(
    axis: NDArray[np.float64],
    angle: float,
) -> Quaternion:
    """
    축-각도를 쿼터니언으로 변환.

    Args:
        axis: 회전축 벡터 (3,) — 자동 정규화
        angle: 회전 각도 (라디안)

    Returns:
        Quaternion 데이터클래스

    Example:
        >>> q = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi / 2)
        >>> np.isclose(q.w, np.cos(np.pi / 4))
        True
    """
    axis = np.asarray(axis, dtype=np.float64).flatten()
    norm = np.linalg.norm(axis)
    if norm < _EPSILON:
        return Quaternion.identity()
    k = axis / norm

    half = angle / 2.0
    s = math.sin(half)
    return Quaternion(
        w=math.cos(half),
        x=k[0] * s,
        y=k[1] * s,
        z=k[2] * s,
    )


def axis_angle_to_rodrigues(
    axis: NDArray[np.float64],
    angle: float,
) -> NDArray[np.float64]:
    """
    축-각도를 로드리게스 벡터로 변환.

    로드리게스 벡터 = axis * angle (방향이 축, 크기가 각도).

    Args:
        axis: 회전축 벡터 (3,) — 자동 정규화
        angle: 회전 각도 (라디안)

    Returns:
        로드리게스 벡터 (3,)

    Example:
        >>> rvec = axis_angle_to_rodrigues(np.array([0, 0, 1.0]), np.pi)
        >>> np.isclose(np.linalg.norm(rvec), np.pi)
        True
    """
    axis = np.asarray(axis, dtype=np.float64).flatten()
    norm = np.linalg.norm(axis)
    if norm < _EPSILON:
        return np.zeros(3, dtype=np.float64)
    return (axis / norm) * angle


# =============================================================================
# 쿼터니언 대수
# =============================================================================

def quaternion_normalize(q: Quaternion | NDArray[np.float64]) -> Quaternion:
    """
    쿼터니언 정규화 (단위 쿼터니언으로 변환).

    Args:
        q: 쿼터니언 (Quaternion 또는 (w,x,y,z) 배열)

    Returns:
        정규화된 Quaternion

    Example:
        >>> q = Quaternion(w=2.0, x=0.0, y=0.0, z=0.0)
        >>> qn = quaternion_normalize(q)
        >>> np.isclose(qn.norm, 1.0)
        True
    """
    if isinstance(q, Quaternion):
        arr = q.as_array
    else:
        arr = np.asarray(q, dtype=np.float64).flatten()

    n = np.linalg.norm(arr)
    if n < _EPSILON:
        logger.warning("영 노름 쿼터니언 — 항등 쿼터니언 반환")
        return Quaternion.identity()

    arr = arr / n
    return Quaternion(w=float(arr[0]), x=float(arr[1]), y=float(arr[2]), z=float(arr[3]))


def quaternion_conjugate(q: Quaternion) -> Quaternion:
    """
    쿼터니언 켤레 (벡터 부분 부호 반전).

    단위 쿼터니언의 경우 켤레 = 역.

    Args:
        q: 입력 쿼터니언

    Returns:
        켤레 쿼터니언

    Example:
        >>> q = Quaternion(w=0.707, x=0.0, y=0.707, z=0.0)
        >>> qc = quaternion_conjugate(q)
        >>> np.isclose(qc.y, -0.707)
        True
    """
    return Quaternion(w=q.w, x=-q.x, y=-q.y, z=-q.z)


def quaternion_inverse(q: Quaternion) -> Quaternion:
    """
    쿼터니언 역.

    q^{-1} = q* / |q|² (단위 쿼터니언이면 켤레와 동일).

    Args:
        q: 입력 쿼터니언

    Returns:
        역 쿼터니언

    Example:
        >>> q = Quaternion(w=0.707, x=0.707, y=0.0, z=0.0)
        >>> qi = quaternion_inverse(q)
        >>> p = quaternion_multiply(q, qi)
        >>> np.isclose(p.w, 1.0, atol=1e-3)
        True
    """
    norm_sq = q.w ** 2 + q.x ** 2 + q.y ** 2 + q.z ** 2
    if norm_sq < _EPSILON:
        logger.warning("영 노름 쿼터니언 역 — 항등 반환")
        return Quaternion.identity()

    inv_norm_sq = 1.0 / norm_sq
    return Quaternion(
        w=q.w * inv_norm_sq,
        x=-q.x * inv_norm_sq,
        y=-q.y * inv_norm_sq,
        z=-q.z * inv_norm_sq,
    )


def quaternion_multiply(q1: Quaternion, q2: Quaternion) -> Quaternion:
    """
    쿼터니언 곱 (Hamilton product).

    결합 회전: 먼저 q2 적용 후 q1 적용 → q1 * q2.

    Args:
        q1: 왼쪽 쿼터니언
        q2: 오른쪽 쿼터니언

    Returns:
        곱 쿼터니언

    Example:
        >>> q1 = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi / 2)
        >>> q2 = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi / 2)
        >>> q12 = quaternion_multiply(q1, q2)
        >>> # 90° + 90° = 180° around z
        >>> np.isclose(q12.w, 0.0, atol=1e-10)
        True
    """
    w = q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z
    x = q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y
    y = q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x
    z = q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w
    return Quaternion(w=w, x=x, y=y, z=z)


def quaternion_rotate_point(
    q: Quaternion,
    point: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    쿼터니언으로 3D 점 회전.

    p' = q * p * q^{-1} (p를 순수 쿼터니언으로 임베딩).

    Args:
        q: 회전 쿼터니언
        point: 3D 점 (3,)

    Returns:
        회전된 3D 점 (3,)

    Example:
        >>> q = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi / 2)
        >>> p = np.array([1.0, 0.0, 0.0])
        >>> p_rot = quaternion_rotate_point(q, p)
        >>> np.allclose(p_rot, [0, 1, 0], atol=1e-10)
        True
    """
    point = np.asarray(point, dtype=np.float64).flatten()
    if point.shape[0] != 3:
        raise ValueError(f"3D 점 필요, {point.shape[0]}차원 받음")

    p = Quaternion(w=0.0, x=float(point[0]), y=float(point[1]), z=float(point[2]))
    q_inv = quaternion_inverse(q)
    result = quaternion_multiply(quaternion_multiply(q, p), q_inv)
    return np.array([result.x, result.y, result.z], dtype=np.float64)


def quaternion_slerp(
    q1: Quaternion,
    q2: Quaternion,
    t: float,
) -> Quaternion:
    """
    쿼터니언 구면 선형 보간 (SLERP).

    t=0 → q1, t=1 → q2. 일정 각속도 보장.

    Args:
        q1: 시작 쿼터니언
        q2: 끝 쿼터니언
        t: 보간 매개변수 [0, 1]

    Returns:
        보간된 쿼터니언

    Example:
        >>> q1 = Quaternion.identity()
        >>> q2 = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi)
        >>> qm = quaternion_slerp(q1, q2, 0.5)
        >>> # 중간점: 90도 회전
        >>> np.isclose(qm.w, np.cos(np.pi / 4), atol=1e-6)
        True
    """
    t = float(np.clip(t, 0.0, 1.0))

    a1 = q1.as_array
    a2 = q2.as_array

    # 내적 (최단 경로 보장)
    dot = float(np.dot(a1, a2))
    if dot < 0.0:
        a2 = -a2
        dot = -dot

    dot = min(dot, 1.0)

    if dot > 1.0 - _SLERP_LINEAR_THRESHOLD:
        # 거의 동일 — 선형 보간 후 정규화
        result = a1 + t * (a2 - a1)
        result = result / np.linalg.norm(result)
        return Quaternion.from_array(result)

    theta = math.acos(dot)
    sin_theta = math.sin(theta)

    s1 = math.sin((1.0 - t) * theta) / sin_theta
    s2 = math.sin(t * theta) / sin_theta

    result = s1 * a1 + s2 * a2
    return Quaternion.from_array(result)


def quaternion_to_axis_angle(q: Quaternion) -> AxisAngle:
    """
    쿼터니언을 축-각도로 변환.

    Args:
        q: 입력 쿼터니언

    Returns:
        AxisAngle 데이터클래스

    Example:
        >>> q = axis_angle_to_quaternion(np.array([0, 0, 1.0]), np.pi / 3)
        >>> aa = quaternion_to_axis_angle(q)
        >>> np.isclose(aa.angle, np.pi / 3)
        True
    """
    q = quaternion_normalize(q)

    # angle = 2·acos(|w|)
    w_clamped = float(np.clip(abs(q.w), 0.0, 1.0))
    angle = 2.0 * math.acos(w_clamped)

    sin_half = math.sin(angle / 2.0)
    if abs(sin_half) < _EPSILON:
        return AxisAngle.identity()

    # w < 0이면 반구 보정 (최단 경로)
    sign = 1.0 if q.w >= 0 else -1.0
    axis = np.array([
        sign * q.x / sin_half,
        sign * q.y / sin_half,
        sign * q.z / sin_half,
    ], dtype=np.float64)

    return AxisAngle(axis=axis, angle=angle)


def quaternion_to_euler(
    q: Quaternion,
    order: str = "xyz",
) -> tuple[float, float, float]:
    """
    쿼터니언을 오일러 각도로 변환.

    중간 단계로 회전 행렬 경유 (수치 안정성).

    Args:
        q: 입력 쿼터니언
        order: 회전 순서 ("xyz", "zyx" 등)

    Returns:
        (roll, pitch, yaw) 라디안 튜플

    Example:
        >>> q = Quaternion.identity()
        >>> r, p, y = quaternion_to_euler(q)
        >>> np.isclose(r, 0) and np.isclose(p, 0) and np.isclose(y, 0)
        True
    """
    R = quaternion_to_matrix(q)
    return _matrix_to_euler_internal(R, order)


def quaternion_to_matrix(q: Quaternion) -> NDArray[np.float64]:
    """
    쿼터니언을 회전 행렬로 변환.

    Args:
        q: 입력 쿼터니언

    Returns:
        회전 행렬 (3, 3)

    Example:
        >>> q = Quaternion.identity()
        >>> R = quaternion_to_matrix(q)
        >>> np.allclose(R, np.eye(3))
        True
    """
    q = quaternion_normalize(q)
    w, x, y, z = q.w, q.x, q.y, q.z

    R = np.array([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
        [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
        [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
    ], dtype=np.float64)

    return R


def quaternion_to_rodrigues(q: Quaternion) -> NDArray[np.float64]:
    """
    쿼터니언을 로드리게스 벡터로 변환.

    Args:
        q: 입력 쿼터니언

    Returns:
        로드리게스 벡터 (3,)

    Example:
        >>> q = Quaternion.identity()
        >>> rvec = quaternion_to_rodrigues(q)
        >>> np.allclose(rvec, [0, 0, 0])
        True
    """
    aa = quaternion_to_axis_angle(q)
    return aa.axis * aa.angle


# =============================================================================
# 회전행렬 → 기타 표현계 변환
# =============================================================================

def rotation_matrix_to_quaternion(R: NDArray[np.float64]) -> Quaternion:
    """
    회전 행렬을 쿼터니언으로 변환 (Shepperd 방법).

    수치적으로 안정적인 방법: 대각 요소 중 가장 큰 것을 기준으로 계산.

    Args:
        R: 회전 행렬 (3, 3)

    Returns:
        Quaternion 데이터클래스

    Example:
        >>> R = np.eye(3)
        >>> q = rotation_matrix_to_quaternion(R)
        >>> np.isclose(q.w, 1.0)
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)

    trace_val = np.trace(R)

    if trace_val > 0:
        s = 0.5 / math.sqrt(trace_val + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s

    q = Quaternion(w=w, x=x, y=y, z=z)
    return quaternion_normalize(q)


def rodrigues_to_axis_angle(rvec: NDArray[np.float64]) -> AxisAngle:
    """
    로드리게스 벡터를 축-각도로 변환.

    Args:
        rvec: 로드리게스 벡터 (3,)

    Returns:
        AxisAngle 데이터클래스

    Example:
        >>> rvec = np.array([0, 0, np.pi / 2])
        >>> aa = rodrigues_to_axis_angle(rvec)
        >>> np.isclose(aa.angle, np.pi / 2)
        True
    """
    rvec = np.asarray(rvec, dtype=np.float64).flatten()
    angle = float(np.linalg.norm(rvec))

    if angle < _EPSILON:
        return AxisAngle.identity()

    axis = rvec / angle
    return AxisAngle(axis=axis, angle=angle)


def rodrigues_to_quaternion(rvec: NDArray[np.float64]) -> Quaternion:
    """
    로드리게스 벡터를 쿼터니언으로 변환.

    Args:
        rvec: 로드리게스 벡터 (3,)

    Returns:
        Quaternion 데이터클래스

    Example:
        >>> rvec = np.array([0, 0, np.pi / 2])
        >>> q = rodrigues_to_quaternion(rvec)
        >>> np.isclose(q.w, np.cos(np.pi / 4))
        True
    """
    aa = rodrigues_to_axis_angle(rvec)
    return axis_angle_to_quaternion(aa.axis, aa.angle)


def euler_to_quaternion(
    roll: float,
    pitch: float,
    yaw: float,
    order: str = "xyz",
) -> Quaternion:
    """
    오일러 각도를 쿼터니언으로 변환.

    Args:
        roll: X축 회전 (라디안)
        pitch: Y축 회전 (라디안)
        yaw: Z축 회전 (라디안)
        order: 회전 순서

    Returns:
        Quaternion 데이터클래스

    Example:
        >>> q = euler_to_quaternion(0.0, 0.0, np.pi / 2)
        >>> np.isclose(q.w, np.cos(np.pi / 4))
        True
    """
    R = _euler_to_matrix_internal(roll, pitch, yaw, order)
    return rotation_matrix_to_quaternion(R)


# =============================================================================
# 회전 합성 및 상대 회전
# =============================================================================

def compose_rotations(
    R1: NDArray[np.float64],
    R2: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    두 회전 합성 (먼저 R2, 그 다음 R1 적용).

    Args:
        R1: 두 번째로 적용할 회전 행렬 (3, 3)
        R2: 먼저 적용할 회전 행렬 (3, 3)

    Returns:
        합성 회전 행렬 R1 @ R2 (3, 3)

    Example:
        >>> R1 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 4)
        >>> R2 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 4)
        >>> R12 = compose_rotations(R1, R2)
        >>> # 45° + 45° = 90°
        >>> R90 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 2)
        >>> np.allclose(R12, R90, atol=1e-10)
        True
    """
    R1 = np.asarray(R1, dtype=np.float64).reshape(3, 3)
    R2 = np.asarray(R2, dtype=np.float64).reshape(3, 3)
    return R1 @ R2


def relative_rotation(
    R_from: NDArray[np.float64],
    R_to: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    상대 회전 계산 (R_from에서 R_to로 가는 회전).

    R_rel = R_to @ R_from^T

    Args:
        R_from: 출발 회전 행렬 (3, 3)
        R_to: 도착 회전 행렬 (3, 3)

    Returns:
        상대 회전 행렬 (3, 3)

    Example:
        >>> R1 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 4)
        >>> R2 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 2)
        >>> R_rel = relative_rotation(R1, R2)
        >>> # 45° → 90° = 45° 차이
        >>> aa = rotation_matrix_to_axis_angle(R_rel)
        >>> np.isclose(aa.angle, np.pi / 4, atol=1e-10)
        True
    """
    R_from = np.asarray(R_from, dtype=np.float64).reshape(3, 3)
    R_to = np.asarray(R_to, dtype=np.float64).reshape(3, 3)
    return R_to @ R_from.T


def rotation_matrix_slerp(
    R1: NDArray[np.float64],
    R2: NDArray[np.float64],
    t: float,
) -> NDArray[np.float64]:
    """
    회전 행렬 SLERP (쿼터니언 경유).

    t=0 → R1, t=1 → R2. 일정 각속도 보간.

    Args:
        R1: 시작 회전 행렬 (3, 3)
        R2: 끝 회전 행렬 (3, 3)
        t: 보간 매개변수 [0, 1]

    Returns:
        보간된 회전 행렬 (3, 3)

    Example:
        >>> R1 = np.eye(3)
        >>> R2 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi)
        >>> Rm = rotation_matrix_slerp(R1, R2, 0.5)
        >>> aa = rotation_matrix_to_axis_angle(Rm)
        >>> np.isclose(aa.angle, np.pi / 2, atol=1e-6)
        True
    """
    q1 = rotation_matrix_to_quaternion(R1)
    q2 = rotation_matrix_to_quaternion(R2)
    q_interp = quaternion_slerp(q1, q2, t)
    return quaternion_to_matrix(q_interp)


# =============================================================================
# SO(3) 검증 및 정규화
# =============================================================================

def is_valid_rotation_matrix(
    R: NDArray[np.float64],
    tolerance: float = ORTHOGONALITY_TOLERANCE,
) -> bool:
    """
    행렬이 유효한 SO(3) 회전 행렬인지 검증.

    조건: R^T·R ≈ I, det(R) ≈ +1.

    Args:
        R: 검사할 행렬 (3, 3)
        tolerance: 허용 오차

    Returns:
        유효하면 True

    Example:
        >>> R = axis_angle_to_rotation_matrix(np.array([1, 0, 0.0]), 0.5)
        >>> is_valid_rotation_matrix(R)
        True
        >>> is_valid_rotation_matrix(np.ones((3, 3)))
        False
    """
    R = np.asarray(R, dtype=np.float64)
    if R.shape != (3, 3):
        return False

    # 직교성: R^T R ≈ I
    eye_check = R.T @ R
    if not np.allclose(eye_check, np.eye(3), atol=tolerance):
        return False

    # 행렬식: det(R) ≈ +1
    det_val = np.linalg.det(R)
    if abs(det_val - 1.0) > DETERMINANT_TOLERANCE:
        return False

    return True


def normalize_rotation_matrix(R: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    회전 행렬을 가장 가까운 SO(3) 행렬로 정규화 (SVD 기반).

    R_normalized = U @ V^T (det > 0 보장).

    Args:
        R: 정규화할 행렬 (3, 3)

    Returns:
        SO(3) 정규화된 회전 행렬 (3, 3)

    Example:
        >>> R = np.eye(3) + np.random.randn(3, 3) * 0.01
        >>> R_norm = normalize_rotation_matrix(R)
        >>> is_valid_rotation_matrix(R_norm)
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    U, _, Vt = np.linalg.svd(R)
    R_norm = U @ Vt

    # det = -1이면 반사 → 보정
    if np.linalg.det(R_norm) < 0:
        U[:, -1] *= -1
        R_norm = U @ Vt

    return R_norm


def is_near_gimbal_lock(
    R: NDArray[np.float64],
    order: str = "xyz",
    threshold: float = GIMBAL_LOCK_THRESHOLD,
) -> bool:
    """
    회전 행렬이 Gimbal lock 근처인지 감지.

    Args:
        R: 회전 행렬 (3, 3)
        order: 오일러 분해 순서
        threshold: 감지 임계값

    Returns:
        Gimbal lock 근처이면 True

    Example:
        >>> # pitch = 90도 (XYZ gimbal lock)
        >>> R = axis_angle_to_rotation_matrix(np.array([0, 1, 0.0]), np.pi / 2)
        >>> is_near_gimbal_lock(R, "xyz")
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    order_lower = order.lower()

    if order_lower == "xyz":
        # gimbal lock: R[2, 0] ≈ ±1 (sin(pitch) ≈ ±1)
        return abs(abs(R[2, 0]) - 1.0) < threshold
    elif order_lower == "zyx":
        # gimbal lock: R[0, 2] ≈ ±1
        return abs(abs(R[0, 2]) - 1.0) < threshold
    else:
        # 보수적: XYZ 기준
        return abs(abs(R[2, 0]) - 1.0) < threshold


# =============================================================================
# 회전 거리 메트릭
# =============================================================================

def rotation_distance(
    R1: NDArray[np.float64],
    R2: NDArray[np.float64],
) -> RotationDistance:
    """
    두 회전 행렬 사이의 거리 계산.

    Args:
        R1: 첫 번째 회전 행렬 (3, 3)
        R2: 두 번째 회전 행렬 (3, 3)

    Returns:
        RotationDistance (측지 거리, 각도, 프로베니우스)

    Example:
        >>> R1 = np.eye(3)
        >>> R2 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), np.pi / 6)
        >>> dist = rotation_distance(R1, R2)
        >>> np.isclose(dist.geodesic, np.pi / 6, atol=1e-6)
        True
    """
    R1 = np.asarray(R1, dtype=np.float64).reshape(3, 3)
    R2 = np.asarray(R2, dtype=np.float64).reshape(3, 3)

    # 상대 회전
    R_rel = R2 @ R1.T

    # 측지 거리 (SO(3) 상의 최단 경로 각도)
    trace_val = np.trace(R_rel)
    cos_angle = np.clip((trace_val - 1.0) / 2.0, -1.0, 1.0)
    geodesic = math.acos(cos_angle)

    # 프로베니우스 노름
    frobenius = float(np.linalg.norm(R1 - R2, "fro"))

    return RotationDistance(
        geodesic=geodesic,
        degrees=math.degrees(geodesic),
        frobenius=frobenius,
    )


def rotation_error(
    R_true: NDArray[np.float64],
    R_est: NDArray[np.float64],
) -> float:
    """
    회전 추정 오차 (각도, 도 단위).

    Args:
        R_true: 실제 회전 행렬 (3, 3)
        R_est: 추정 회전 행렬 (3, 3)

    Returns:
        오차 각도 (도)

    Example:
        >>> R_true = np.eye(3)
        >>> R_est = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), 0.01)
        >>> err = rotation_error(R_true, R_est)
        >>> err < 1.0  # 1도 미만
        True
    """
    dist = rotation_distance(R_true, R_est)
    return dist.degrees


# =============================================================================
# 각속도 추정
# =============================================================================

def angular_velocity_from_matrices(
    R1: NDArray[np.float64],
    R2: NDArray[np.float64],
    dt: float,
) -> AngularVelocity:
    """
    두 시점의 회전 행렬로부터 각속도 추정.

    ω = axis * (angle / dt)

    Args:
        R1: 시간 t의 회전 행렬 (3, 3)
        R2: 시간 t+dt의 회전 행렬 (3, 3)
        dt: 시간 간격 (초). 양수 필수.

    Returns:
        AngularVelocity 데이터클래스

    Example:
        >>> R1 = np.eye(3)
        >>> R2 = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), 0.1)
        >>> av = angular_velocity_from_matrices(R1, R2, 1.0 / 30)
        >>> av.magnitude > 0
        True
    """
    if dt <= 0:
        raise ValueError(f"시간 간격은 양수여야 합니다: dt={dt}")

    R_rel = relative_rotation(R1, R2)
    aa = rotation_matrix_to_axis_angle(R_rel)

    omega = aa.axis * (aa.angle / dt)
    magnitude = aa.angle / dt

    return AngularVelocity(omega=omega, magnitude=magnitude, dt=dt)


def angular_velocity_from_quaternions(
    q1: Quaternion,
    q2: Quaternion,
    dt: float,
) -> AngularVelocity:
    """
    두 시점의 쿼터니언으로부터 각속도 추정.

    Args:
        q1: 시간 t의 쿼터니언
        q2: 시간 t+dt의 쿼터니언
        dt: 시간 간격 (초). 양수 필수.

    Returns:
        AngularVelocity 데이터클래스

    Example:
        >>> q1 = Quaternion.identity()
        >>> q2 = axis_angle_to_quaternion(np.array([0, 0, 1.0]), 0.1)
        >>> av = angular_velocity_from_quaternions(q1, q2, 1.0 / 30)
        >>> av.magnitude > 0
        True
    """
    if dt <= 0:
        raise ValueError(f"시간 간격은 양수여야 합니다: dt={dt}")

    q_rel = quaternion_multiply(q2, quaternion_inverse(q1))
    q_rel = quaternion_normalize(q_rel)
    aa = quaternion_to_axis_angle(q_rel)

    omega = aa.axis * (aa.angle / dt)
    magnitude = aa.angle / dt

    return AngularVelocity(omega=omega, magnitude=magnitude, dt=dt)


# =============================================================================
# 배치 연산
# =============================================================================

def batch_axis_angle_to_matrices(
    axes: NDArray[np.float64],
    angles: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    N개의 축-각도를 회전 행렬 배치로 변환.

    Args:
        axes: 회전축 배열 (N, 3)
        angles: 회전 각도 배열 (N,) — 라디안

    Returns:
        회전 행렬 배열 (N, 3, 3)

    Example:
        >>> axes = np.array([[0, 0, 1], [1, 0, 0]], dtype=np.float64)
        >>> angles = np.array([np.pi / 4, np.pi / 6])
        >>> Rs = batch_axis_angle_to_matrices(axes, angles)
        >>> Rs.shape
        (2, 3, 3)
    """
    axes = np.asarray(axes, dtype=np.float64)
    angles = np.asarray(angles, dtype=np.float64).flatten()

    if axes.ndim == 1:
        axes = axes.reshape(1, 3)
    n = axes.shape[0]

    if n != len(angles):
        raise ValueError(f"축 개수({n})와 각도 개수({len(angles)}) 불일치")
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    results = np.empty((n, 3, 3), dtype=np.float64)
    for i in range(n):
        results[i] = axis_angle_to_rotation_matrix(axes[i], float(angles[i]))

    return results


def batch_rodrigues_to_matrices(
    rvecs: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    N개의 로드리게스 벡터를 회전 행렬 배치로 변환.

    Args:
        rvecs: 로드리게스 벡터 배열 (N, 3)

    Returns:
        회전 행렬 배열 (N, 3, 3)

    Example:
        >>> rvecs = np.array([[0, 0, 0.1], [0.2, 0, 0]], dtype=np.float64)
        >>> Rs = batch_rodrigues_to_matrices(rvecs)
        >>> Rs.shape
        (2, 3, 3)
    """
    rvecs = np.asarray(rvecs, dtype=np.float64)
    if rvecs.ndim == 1:
        rvecs = rvecs.reshape(1, 3)

    n = rvecs.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    results = np.empty((n, 3, 3), dtype=np.float64)
    for i in range(n):
        vec = rvecs[i].reshape(3, 1)
        R, _ = cv2.Rodrigues(vec)
        results[i] = R

    return results


def batch_matrices_to_rodrigues(
    Rs: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    N개의 회전 행렬을 로드리게스 벡터 배치로 변환.

    Args:
        Rs: 회전 행렬 배열 (N, 3, 3)

    Returns:
        로드리게스 벡터 배열 (N, 3)

    Example:
        >>> Rs = np.stack([np.eye(3), np.eye(3)])
        >>> rvecs = batch_matrices_to_rodrigues(Rs)
        >>> rvecs.shape
        (2, 3)
    """
    Rs = np.asarray(Rs, dtype=np.float64)
    if Rs.ndim == 2:
        Rs = Rs.reshape(1, 3, 3)

    n = Rs.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    results = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        rvec, _ = cv2.Rodrigues(Rs[i])
        results[i] = rvec.flatten()

    return results


def batch_transform_points(
    R: NDArray[np.float64],
    t: NDArray[np.float64],
    points: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    회전 + 이동 변환을 점 배치에 적용.

    p' = R @ p + t

    Args:
        R: 회전 행렬 (3, 3)
        t: 이동 벡터 (3,)
        points: 3D 점 배열 (N, 3)

    Returns:
        변환된 점 배열 (N, 3)

    Example:
        >>> R = np.eye(3)
        >>> t = np.array([1, 2, 3], dtype=np.float64)
        >>> pts = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float64)
        >>> pts_t = batch_transform_points(R, t, pts)
        >>> np.allclose(pts_t[0], [1, 2, 3])
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    t = np.asarray(t, dtype=np.float64).flatten()
    points = np.asarray(points, dtype=np.float64)

    if points.ndim == 1:
        points = points.reshape(1, 3)

    if points.shape[0] > _MAX_BATCH_SIZE:
        raise ValueError(f"점 배치 크기 초과: {points.shape[0]} > {_MAX_BATCH_SIZE}")

    # 행렬 곱으로 일괄 변환: (3,3) @ (3,N) + (3,1) → (3,N) → (N,3)
    return (R @ points.T).T + t


# =============================================================================
# 좌표 프레임 변환
# =============================================================================

def skew_symmetric(v: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    3D 벡터의 비대칭 행렬 (skew-symmetric / hat operator).

    [v]× 는 외적 v × u = [v]× @ u 를 행렬 곱으로 표현.

    Args:
        v: 3D 벡터 (3,)

    Returns:
        비대칭 행렬 (3, 3)

    Example:
        >>> v = np.array([1, 2, 3], dtype=np.float64)
        >>> K = skew_symmetric(v)
        >>> u = np.array([4, 5, 6], dtype=np.float64)
        >>> np.allclose(K @ u, np.cross(v, u))
        True
    """
    v = np.asarray(v, dtype=np.float64).flatten()
    if v.shape[0] != 3:
        raise ValueError(f"3D 벡터 필요, {v.shape[0]}차원 받음")

    return np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0],
    ], dtype=np.float64)


def rotation_matrix_to_homogeneous(
    R: NDArray[np.float64],
    t: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """
    회전 행렬 (+ 이동)을 4x4 동차 변환 행렬로 변환.

    Args:
        R: 회전 행렬 (3, 3)
        t: 이동 벡터 (3,) — None이면 영벡터

    Returns:
        동차 변환 행렬 (4, 4)

    Example:
        >>> R = np.eye(3)
        >>> t = np.array([1, 2, 3], dtype=np.float64)
        >>> H = rotation_matrix_to_homogeneous(R, t)
        >>> H.shape
        (4, 4)
        >>> np.allclose(H[:3, 3], [1, 2, 3])
        True
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    H = np.eye(4, dtype=np.float64)
    H[:3, :3] = R

    if t is not None:
        t = np.asarray(t, dtype=np.float64).flatten()
        H[:3, 3] = t

    return H


def homogeneous_to_rotation(
    H: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    4x4 동차 변환 행렬에서 회전 행렬과 이동 벡터 추출.

    Args:
        H: 동차 변환 행렬 (4, 4)

    Returns:
        (R, t) 튜플 — R: (3, 3), t: (3,)

    Example:
        >>> H = np.eye(4)
        >>> H[:3, 3] = [1, 2, 3]
        >>> R, t = homogeneous_to_rotation(H)
        >>> np.allclose(t, [1, 2, 3])
        True
    """
    H = np.asarray(H, dtype=np.float64).reshape(4, 4)
    R = H[:3, :3].copy()
    t = H[:3, 3].copy()
    return R, t


# =============================================================================
# 내부 헬퍼 (오일러 변환 — math_utils와 동일 로직, 내부 전용)
# =============================================================================

def _euler_to_matrix_internal(
    roll: float,
    pitch: float,
    yaw: float,
    order: str = "xyz",
) -> NDArray[np.float64]:
    """오일러 → 회전행렬 (내부 전용, math_utils 동일 로직)."""
    cos_r, sin_r = math.cos(roll), math.sin(roll)
    cos_p, sin_p = math.cos(pitch), math.sin(pitch)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    Rx = np.array([[1, 0, 0], [0, cos_r, -sin_r], [0, sin_r, cos_r]], dtype=np.float64)
    Ry = np.array([[cos_p, 0, sin_p], [0, 1, 0], [-sin_p, 0, cos_p]], dtype=np.float64)
    Rz = np.array([[cos_y, -sin_y, 0], [sin_y, cos_y, 0], [0, 0, 1]], dtype=np.float64)

    rotation_map = {"x": Rx, "y": Ry, "z": Rz}
    order_lower = order.lower()

    if len(order_lower) != 3 or not all(c in "xyz" for c in order_lower):
        return Rz @ Ry @ Rx

    R = np.eye(3, dtype=np.float64)
    for axis_char in order_lower:
        R = R @ rotation_map[axis_char]
    return R


def _matrix_to_euler_internal(
    R: NDArray[np.float64],
    order: str = "xyz",
) -> tuple[float, float, float]:
    """회전행렬 → 오일러 (내부 전용, math_utils 동일 로직)."""
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    order_lower = order.lower()

    if order_lower == "xyz":
        sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
        if sy > _EPSILON:
            roll = math.atan2(R[2, 1], R[2, 2])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = math.atan2(R[1, 0], R[0, 0])
        else:
            roll = math.atan2(-R[1, 2], R[1, 1])
            pitch = math.atan2(-R[2, 0], sy)
            yaw = 0.0
        return (roll, pitch, yaw)

    elif order_lower == "zyx":
        cy = math.sqrt(R[0, 0] ** 2 + R[0, 1] ** 2)
        if cy > _EPSILON:
            roll = math.atan2(R[1, 2], R[2, 2])
            pitch = math.atan2(-R[0, 2], cy)
            yaw = math.atan2(R[0, 1], R[0, 0])
        else:
            roll = math.atan2(-R[2, 1], R[1, 1])
            pitch = math.atan2(-R[0, 2], cy)
            yaw = 0.0
        return (roll, pitch, yaw)

    else:
        return _matrix_to_euler_internal(R, "xyz")


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # === 상수 ===
    "GIMBAL_LOCK_THRESHOLD",
    "QUATERNION_NORM_TOLERANCE",
    "ORTHOGONALITY_TOLERANCE",
    "DETERMINANT_TOLERANCE",

    # === Enum ===
    "RotationOrder",
    "RotationFormat",

    # === 데이터 클래스 ===
    "AxisAngle",
    "Quaternion",
    "AngularVelocity",
    "RotationDistance",

    # === 축-각도 변환 ===
    "axis_angle_to_rotation_matrix",
    "rotation_matrix_to_axis_angle",
    "axis_angle_to_quaternion",
    "axis_angle_to_rodrigues",

    # === 쿼터니언 대수 ===
    "quaternion_normalize",
    "quaternion_conjugate",
    "quaternion_inverse",
    "quaternion_multiply",
    "quaternion_rotate_point",
    "quaternion_slerp",

    # === 쿼터니언 변환 ===
    "quaternion_to_axis_angle",
    "quaternion_to_euler",
    "quaternion_to_matrix",
    "quaternion_to_rodrigues",

    # === 회전행렬 변환 ===
    "rotation_matrix_to_quaternion",

    # === 로드리게스 변환 ===
    "rodrigues_to_axis_angle",
    "rodrigues_to_quaternion",

    # === 오일러 변환 ===
    "euler_to_quaternion",

    # === 회전 합성/보간 ===
    "compose_rotations",
    "relative_rotation",
    "rotation_matrix_slerp",

    # === SO(3) 검증/정규화 ===
    "is_valid_rotation_matrix",
    "normalize_rotation_matrix",
    "is_near_gimbal_lock",

    # === 거리 메트릭 ===
    "rotation_distance",
    "rotation_error",

    # === 각속도 ===
    "angular_velocity_from_matrices",
    "angular_velocity_from_quaternions",

    # === 배치 연산 ===
    "batch_axis_angle_to_matrices",
    "batch_rodrigues_to_matrices",
    "batch_matrices_to_rodrigues",
    "batch_transform_points",

    # === 좌표 프레임 ===
    "skew_symmetric",
    "rotation_matrix_to_homogeneous",
    "homogeneous_to_rotation",
]

__version__: str = "1.0.0"
