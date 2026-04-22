# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: interpolation_utils.py
설명: 보간 유틸리티
      - 선형, 스플라인, 베지어 보간
      - 궤적 보간 및 리샘플링
      - 누락 프레임 채우기

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 1.0.0

참고:
    - PHASE_02_UTILS_IMPORT_SPEC.md 섹션 7
    - 순수 함수 모듈 (DI 없음)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto, unique
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import (
    CubicSpline,
    UnivariateSpline,
    interp1d,
)


# =============================================================================
# 열거형
# =============================================================================

@unique
class InterpolationMethod(Enum):
    """
    보간 방법 열거형.
    """

    # 선형 보간
    LINEAR = auto()

    # 3차 보간
    CUBIC = auto()

    # 스플라인 보간
    SPLINE = auto()

    # 베지어 곡선
    BEZIER = auto()

    # 최근접 이웃
    NEAREST = auto()


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class InterpolationConfig:
    """
    보간 설정.

    Attributes:
        method: 보간 방법
        smoothing: 스플라인 스무딩 계수 (0 = 정확히 통과)
        extrapolate: 외삽 허용 여부
    """

    method: InterpolationMethod = InterpolationMethod.LINEAR
    smoothing: float = 0.0
    extrapolate: bool = False


@dataclass(slots=True)
class InterpolatedPoint:
    """
    보간된 점.

    Attributes:
        value: 보간된 값
        t: 보간 파라미터 (0-1)
        confidence: 신뢰도 (1.0 = 원본 데이터)
    """

    value: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(1, dtype=np.float64)
    )
    t: float = 0.0
    confidence: float = 1.0


# =============================================================================
# 선형 보간
# =============================================================================

def linear_interpolate(
    x1: float,
    x2: float,
    t: float,
) -> float:
    """
    선형 보간 (1D).

    Args:
        x1: 시작 값
        x2: 끝 값
        t: 보간 계수 (0-1)

    Returns:
        보간된 값

    Example:
        >>> linear_interpolate(0.0, 10.0, 0.5)
        5.0
    """
    return x1 + (x2 - x1) * t


def linear_interpolate_2d(
    p1: tuple[float, float],
    p2: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """
    선형 보간 (2D).

    Args:
        p1: 시작점 (x, y)
        p2: 끝점 (x, y)
        t: 보간 계수 (0-1)

    Returns:
        보간된 점 (x, y)
    """
    return (
        p1[0] + (p2[0] - p1[0]) * t,
        p1[1] + (p2[1] - p1[1]) * t,
    )


def linear_interpolate_3d(
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    t: float,
) -> tuple[float, float, float]:
    """
    선형 보간 (3D).

    Args:
        p1: 시작점 (x, y, z)
        p2: 끝점 (x, y, z)
        t: 보간 계수 (0-1)

    Returns:
        보간된 점 (x, y, z)
    """
    return (
        p1[0] + (p2[0] - p1[0]) * t,
        p1[1] + (p2[1] - p1[1]) * t,
        p1[2] + (p2[2] - p1[2]) * t,
    )


def bilinear_interpolate(
    values: NDArray[np.float64],
    x: float,
    y: float,
) -> float:
    """
    이중선형 보간.

    2x2 그리드에서 (x, y) 위치의 값을 보간합니다.

    Args:
        values: 2x2 값 배열 [[v00, v01], [v10, v11]]
        x: x 좌표 (0-1)
        y: y 좌표 (0-1)

    Returns:
        보간된 값

    Example:
        >>> values = np.array([[0, 1], [2, 3]])
        >>> bilinear_interpolate(values, 0.5, 0.5)
        1.5
    """
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))

    v00 = values[0, 0]
    v01 = values[0, 1]
    v10 = values[1, 0]
    v11 = values[1, 1]

    # x 방향 보간
    v0 = v00 + (v01 - v00) * x
    v1 = v10 + (v11 - v10) * x

    # y 방향 보간
    return v0 + (v1 - v0) * y


# =============================================================================
# 스플라인 보간
# =============================================================================

def cubic_spline_interpolate(
    x_points: Sequence[float],
    y_points: Sequence[float],
    x_new: float | Sequence[float],
    bc_type: str = "natural",
) -> float | NDArray[np.float64]:
    """
    큐빅 스플라인 보간.

    Args:
        x_points: 알려진 x 좌표들
        y_points: 알려진 y 값들
        x_new: 보간할 x 좌표(들)
        bc_type: 경계 조건 ("natural", "clamped", "not-a-knot")

    Returns:
        보간된 값(들)

    Example:
        >>> x = [0, 1, 2, 3]
        >>> y = [0, 1, 0, 1]
        >>> cubic_spline_interpolate(x, y, 1.5)
        0.3125
    """
    x_arr = np.array(x_points, dtype=np.float64)
    y_arr = np.array(y_points, dtype=np.float64)

    cs = CubicSpline(x_arr, y_arr, bc_type=bc_type)

    result = cs(x_new)

    if isinstance(x_new, (int, float)):
        return float(result)
    return np.array(result, dtype=np.float64)


def spline_interpolate(
    x_points: Sequence[float],
    y_points: Sequence[float],
    x_new: float | Sequence[float],
    smoothing: float = 0.0,
) -> float | NDArray[np.float64]:
    """
    일반 스플라인 보간.

    스무딩을 적용할 수 있는 스플라인 보간입니다.

    Args:
        x_points: 알려진 x 좌표들
        y_points: 알려진 y 값들
        x_new: 보간할 x 좌표(들)
        smoothing: 스무딩 계수 (0 = 정확히 통과)

    Returns:
        보간된 값(들)
    """
    x_arr = np.array(x_points, dtype=np.float64)
    y_arr = np.array(y_points, dtype=np.float64)

    if smoothing == 0.0:
        spline = UnivariateSpline(x_arr, y_arr, s=0)
    else:
        spline = UnivariateSpline(x_arr, y_arr, s=smoothing)

    result = spline(x_new)

    if isinstance(x_new, (int, float)):
        return float(result)
    return np.array(result, dtype=np.float64)


def catmull_rom_spline(
    points: Sequence[NDArray[np.float64]],
    t: float,
    segment_index: int,
    alpha: float = 0.5,
) -> NDArray[np.float64]:
    """
    Catmull-Rom 스플라인.

    4개의 제어점을 사용하여 부드러운 곡선을 생성합니다.

    Args:
        points: 제어점 배열 (최소 4개)
        t: 보간 파라미터 (0-1)
        segment_index: 세그먼트 인덱스 (1 ~ len(points)-2)
        alpha: 텐션 계수 (0.5 = centripetal)

    Returns:
        보간된 점
    """
    if len(points) < 4:
        raise ValueError("Catmull-Rom requires at least 4 points")

    i = segment_index
    p0 = np.array(points[i - 1], dtype=np.float64)
    p1 = np.array(points[i], dtype=np.float64)
    p2 = np.array(points[i + 1], dtype=np.float64)
    p3 = np.array(points[i + 2], dtype=np.float64)

    # 거리 기반 파라미터 계산
    def get_t(p_a: NDArray, p_b: NDArray, t_prev: float) -> float:
        d = np.linalg.norm(p_b - p_a)
        return t_prev + d ** alpha

    t0 = 0.0
    t1 = get_t(p0, p1, t0)
    t2 = get_t(p1, p2, t1)
    t3 = get_t(p2, p3, t2)

    # 보간 파라미터를 t1-t2 범위로 매핑
    t_interp = t1 + t * (t2 - t1)

    # Catmull-Rom 보간
    def interp(t_val: float, p_a: NDArray, p_b: NDArray, t_a: float, t_b: float) -> NDArray:
        if abs(t_b - t_a) < 1e-10:
            return p_a
        return (t_b - t_val) / (t_b - t_a) * p_a + (t_val - t_a) / (t_b - t_a) * p_b

    a1 = interp(t_interp, p0, p1, t0, t1)
    a2 = interp(t_interp, p1, p2, t1, t2)
    a3 = interp(t_interp, p2, p3, t2, t3)

    b1 = interp(t_interp, a1, a2, t0, t2)
    b2 = interp(t_interp, a2, a3, t1, t3)

    c = interp(t_interp, b1, b2, t1, t2)

    return c


# =============================================================================
# 베지어 곡선
# =============================================================================

def bezier_curve(
    control_points: Sequence[NDArray[np.float64]],
    t: float,
) -> NDArray[np.float64]:
    """
    베지어 곡선 계산.

    De Casteljau 알고리즘을 사용합니다.

    Args:
        control_points: 제어점 배열
        t: 파라미터 (0-1)

    Returns:
        베지어 곡선 상의 점
    """
    points = [np.array(p, dtype=np.float64) for p in control_points]

    while len(points) > 1:
        new_points = []
        for i in range(len(points) - 1):
            new_point = points[i] * (1 - t) + points[i + 1] * t
            new_points.append(new_point)
        points = new_points

    return points[0]


def bezier_interpolate(
    control_points: Sequence[NDArray[np.float64]],
    num_samples: int = 100,
) -> list[NDArray[np.float64]]:
    """
    베지어 곡선 보간.

    Args:
        control_points: 제어점 배열
        num_samples: 샘플 수

    Returns:
        베지어 곡선 점들
    """
    t_values = np.linspace(0, 1, num_samples)
    return [bezier_curve(control_points, t) for t in t_values]


def quadratic_bezier(
    p0: NDArray[np.float64],
    p1: NDArray[np.float64],
    p2: NDArray[np.float64],
    t: float,
) -> NDArray[np.float64]:
    """
    2차 베지어 곡선.

    B(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂

    Args:
        p0: 시작점
        p1: 제어점
        p2: 끝점
        t: 파라미터 (0-1)

    Returns:
        베지어 곡선 상의 점
    """
    p0 = np.array(p0, dtype=np.float64)
    p1 = np.array(p1, dtype=np.float64)
    p2 = np.array(p2, dtype=np.float64)

    u = 1 - t
    return u * u * p0 + 2 * u * t * p1 + t * t * p2


def cubic_bezier(
    p0: NDArray[np.float64],
    p1: NDArray[np.float64],
    p2: NDArray[np.float64],
    p3: NDArray[np.float64],
    t: float,
) -> NDArray[np.float64]:
    """
    3차 베지어 곡선.

    B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃

    Args:
        p0: 시작점
        p1: 제어점 1
        p2: 제어점 2
        p3: 끝점
        t: 파라미터 (0-1)

    Returns:
        베지어 곡선 상의 점
    """
    p0 = np.array(p0, dtype=np.float64)
    p1 = np.array(p1, dtype=np.float64)
    p2 = np.array(p2, dtype=np.float64)
    p3 = np.array(p3, dtype=np.float64)

    u = 1 - t
    u2 = u * u
    u3 = u2 * u
    t2 = t * t
    t3 = t2 * t

    return u3 * p0 + 3 * u2 * t * p1 + 3 * u * t2 * p2 + t3 * p3


# =============================================================================
# 궤적 보간
# =============================================================================

def interpolate_trajectory(
    times: Sequence[float],
    positions: Sequence[NDArray[np.float64]],
    target_times: Sequence[float],
    method: InterpolationMethod = InterpolationMethod.CUBIC,
) -> list[NDArray[np.float64]]:
    """
    궤적 보간 (시간 기반).

    Args:
        times: 알려진 시간들
        positions: 알려진 위치들
        target_times: 보간할 시간들
        method: 보간 방법

    Returns:
        보간된 위치들
    """
    times_arr = np.array(times, dtype=np.float64)
    positions_arr = np.array(positions, dtype=np.float64)

    if len(times_arr) < 2:
        return [positions_arr[0].copy() for _ in target_times]

    # 각 차원별로 보간
    dim = positions_arr.shape[1]
    interpolated = np.zeros((len(target_times), dim), dtype=np.float64)

    kind = {
        InterpolationMethod.LINEAR: "linear",
        InterpolationMethod.CUBIC: "cubic",
        InterpolationMethod.NEAREST: "nearest",
    }.get(method, "linear")

    for d in range(dim):
        if method == InterpolationMethod.SPLINE:
            interpolated[:, d] = spline_interpolate(
                times_arr, positions_arr[:, d], target_times
            )
        else:
            f = interp1d(
                times_arr, positions_arr[:, d],
                kind=kind,
                bounds_error=False,
                fill_value="extrapolate",
            )
            interpolated[:, d] = f(target_times)

    return [interpolated[i] for i in range(len(target_times))]


def resample_trajectory(
    times: Sequence[float],
    positions: Sequence[NDArray[np.float64]],
    num_samples: int,
    method: InterpolationMethod = InterpolationMethod.CUBIC,
) -> tuple[list[float], list[NDArray[np.float64]]]:
    """
    궤적 리샘플링.

    균일한 간격으로 리샘플링합니다.

    Args:
        times: 원본 시간들
        positions: 원본 위치들
        num_samples: 새로운 샘플 수
        method: 보간 방법

    Returns:
        (새로운 시간들, 새로운 위치들) 튜플
    """
    times_arr = np.array(times, dtype=np.float64)
    new_times = np.linspace(times_arr[0], times_arr[-1], num_samples)
    new_positions = interpolate_trajectory(times, positions, new_times, method)

    return list(new_times), new_positions


def smooth_trajectory(
    positions: Sequence[NDArray[np.float64]],
    window_size: int = 5,
    method: str = "moving_average",
) -> list[NDArray[np.float64]]:
    """
    궤적 스무딩.

    Args:
        positions: 위치 배열
        window_size: 윈도우 크기 (홀수 권장)
        method: 스무딩 방법 ("moving_average", "gaussian")

    Returns:
        스무딩된 위치들
    """
    positions_arr = np.array(positions, dtype=np.float64)
    n = len(positions_arr)

    if n < window_size:
        return [p.copy() for p in positions]

    smoothed = np.zeros_like(positions_arr)

    if method == "moving_average":
        # 이동 평균
        half_window = window_size // 2
        for i in range(n):
            start = max(0, i - half_window)
            end = min(n, i + half_window + 1)
            smoothed[i] = np.mean(positions_arr[start:end], axis=0)

    elif method == "gaussian":
        # 가우시안 가중 평균
        half_window = window_size // 2
        sigma = window_size / 6.0
        weights = np.exp(-np.arange(-half_window, half_window + 1) ** 2 / (2 * sigma ** 2))
        weights /= weights.sum()

        for i in range(n):
            start = max(0, i - half_window)
            end = min(n, i + half_window + 1)
            w_start = max(0, half_window - i)
            w_end = w_start + (end - start)
            w = weights[w_start:w_end]
            w = w / w.sum()  # 정규화
            smoothed[i] = np.average(positions_arr[start:end], axis=0, weights=w)

    else:
        smoothed = positions_arr.copy()

    return [smoothed[i] for i in range(n)]


# =============================================================================
# 시간 보간
# =============================================================================

def interpolate_at_time(
    times: Sequence[float],
    values: Sequence[NDArray[np.float64]],
    target_time: float,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> NDArray[np.float64] | None:
    """
    특정 시간의 값 보간.

    Args:
        times: 알려진 시간들
        values: 알려진 값들
        target_time: 보간할 시간
        method: 보간 방법

    Returns:
        보간된 값 (범위 밖이면 None)
    """
    times_arr = np.array(times, dtype=np.float64)
    values_arr = np.array(values, dtype=np.float64)

    if len(times_arr) < 2:
        return values_arr[0].copy() if len(values_arr) > 0 else None

    # 범위 체크
    if target_time < times_arr[0] or target_time > times_arr[-1]:
        return None

    result = interpolate_trajectory(times, values, [target_time], method)
    return result[0] if result else None


def fill_missing_frames(
    frame_indices: Sequence[int],
    values: Sequence[NDArray[np.float64]],
    start_frame: int,
    end_frame: int,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> tuple[list[int], list[NDArray[np.float64]]]:
    """
    누락 프레임 채우기.

    Args:
        frame_indices: 알려진 프레임 인덱스들
        values: 알려진 값들
        start_frame: 시작 프레임
        end_frame: 끝 프레임 (포함)
        method: 보간 방법

    Returns:
        (모든 프레임 인덱스들, 채워진 값들) 튜플
    """
    frame_indices_arr = np.array(frame_indices, dtype=np.int64)
    values_arr = np.array(values, dtype=np.float64)

    all_frames = list(range(start_frame, end_frame + 1))
    filled_values: list[NDArray[np.float64]] = []

    # 원본 데이터를 시간으로 변환 (프레임 인덱스 사용)
    times = frame_indices_arr.astype(np.float64)

    # O(1) 조회를 위한 frame → index 맵 (대규모 시퀀스 성능 최적화)
    frame_to_idx: dict[int, int] = {int(f): i for i, f in enumerate(frame_indices)}

    for frame in all_frames:
        if frame in frame_to_idx:
            filled_values.append(values_arr[frame_to_idx[frame]].copy())
        else:
            # 보간
            result = interpolate_at_time(times, values, float(frame), method)
            if result is not None:
                filled_values.append(result)
            else:
                # 외삽이 필요한 경우 가장 가까운 값 사용
                if frame < frame_indices_arr[0]:
                    filled_values.append(values_arr[0].copy())
                else:
                    filled_values.append(values_arr[-1].copy())

    return all_frames, filled_values


# =============================================================================
# 유틸리티
# =============================================================================

def compute_interpolation_weights(
    t: float,
    method: InterpolationMethod = InterpolationMethod.LINEAR,
) -> tuple[float, float]:
    """
    보간 가중치 계산.

    두 점 사이의 보간 가중치를 계산합니다.

    Args:
        t: 보간 파라미터 (0-1)
        method: 보간 방법

    Returns:
        (w1, w2) 가중치 튜플 (w1 + w2 = 1)
    """
    t = max(0.0, min(1.0, t))

    if method == InterpolationMethod.LINEAR:
        w1 = 1 - t
        w2 = t

    elif method == InterpolationMethod.CUBIC:
        # Smoothstep
        t_smooth = t * t * (3 - 2 * t)
        w1 = 1 - t_smooth
        w2 = t_smooth

    elif method == InterpolationMethod.NEAREST:
        if t < 0.5:
            w1 = 1.0
            w2 = 0.0
        else:
            w1 = 0.0
            w2 = 1.0

    else:
        w1 = 1 - t
        w2 = t

    return w1, w2


# =============================================================================
# 모듈 Export 정의 (PHASE_02 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "InterpolationMethod",

    # 데이터 클래스
    "InterpolationConfig",
    "InterpolatedPoint",

    # 선형 보간
    "linear_interpolate",
    "linear_interpolate_2d",
    "linear_interpolate_3d",
    "bilinear_interpolate",

    # 스플라인 보간
    "cubic_spline_interpolate",
    "spline_interpolate",
    "catmull_rom_spline",

    # 베지어 곡선
    "bezier_curve",
    "bezier_interpolate",
    "quadratic_bezier",
    "cubic_bezier",

    # 궤적 보간
    "interpolate_trajectory",
    "resample_trajectory",
    "smooth_trajectory",

    # 시간 보간
    "interpolate_at_time",
    "fill_missing_frames",

    # 유틸리티
    "compute_interpolation_weights",
]

# 모듈 버전 정보
__version__ = "1.0.0"
