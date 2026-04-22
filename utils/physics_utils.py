# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: physics_utils.py
설명: 물리 계산 유틸리티
      - 발사체 운동 (포물선)
      - 중력, 공기저항, 마그누스 효과
      - 슛 궤적 분석

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 1.0.0

참고:
    - PHASE_02_UTILS_IMPORT_SPEC.md 섹션 6
    - 과학적 정확성을 위한 실제 물리 상수 사용
    - 순수 함수 모듈 (DI 없음)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

# === shared.constants SSOT (Phase 15 H5) ===
from shared.constants.ball_constants import (
    AIR_DENSITY as _AIR_DENSITY,
    BASKETBALL_DRAG_COEFFICIENT as _BASKETBALL_DRAG_COEFFICIENT,
    BASKETBALL_MASS_KG as _BASKETBALL_MASS_KG,
    BASKETBALL_RADIUS_M as _BASKETBALL_RADIUS_M,
    GRAVITY_ACCELERATION as _GRAVITY_ACCELERATION,
)
from shared.constants.court_constants import (
    FREE_THROW_LINE_DISTANCE_M as _FREE_THROW_LINE_DISTANCE_M,
    HOOP_HEIGHT_M as _HOOP_HEIGHT_M,
    HOOP_RADIUS_M as _HOOP_RADIUS_M,
    THREE_POINT_LINE_DISTANCE_M as _THREE_POINT_LINE_DISTANCE_M,
)


# =============================================================================
# 물리 상수 — shared.constants SSOT re-export (Phase 15 H5)
# =============================================================================

# 중력 가속도 (m/s²) — ISO 표준중력 g₀
GRAVITY: float = _GRAVITY_ACCELERATION

# 농구공 물리 특성 (FIBA 규격) — shared.constants.ball_constants SSOT
BASKETBALL_MASS: float = _BASKETBALL_MASS_KG          # 질량 (kg)
BASKETBALL_RADIUS: float = _BASKETBALL_RADIUS_M       # 반지름 (m)
BASKETBALL_DRAG_COEFFICIENT: float = _BASKETBALL_DRAG_COEFFICIENT  # 항력 계수
BASKETBALL_CROSS_SECTION: float = math.pi * BASKETBALL_RADIUS ** 2  # 단면적 (m²)

# 공기 특성 — shared.constants.ball_constants SSOT
AIR_DENSITY: float = _AIR_DENSITY  # 공기 밀도 (kg/m³)

# 농구 골대/라인 규격 — shared.constants.court_constants SSOT
HOOP_HEIGHT: float = _HOOP_HEIGHT_M                    # 림 높이 (m)
HOOP_RADIUS: float = _HOOP_RADIUS_M                    # 림 반지름 (m) — 9 inch
FREE_THROW_DISTANCE: float = _FREE_THROW_LINE_DISTANCE_M  # 자유투 거리 (m)
THREE_POINT_DISTANCE: float = _THREE_POINT_LINE_DISTANCE_M  # 3점 라인 (m, FIBA)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ProjectileState:
    """
    발사체 상태.

    Attributes:
        position: 3D 위치 [x, y, z] (m)
        velocity: 3D 속도 [vx, vy, vz] (m/s)
        time: 경과 시간 (s)
    """

    position: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    velocity: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    time: float = 0.0

    @property
    def speed(self) -> float:
        """속력 (m/s)."""
        return float(np.linalg.norm(self.velocity))

    @property
    def height(self) -> float:
        """높이 (z 좌표) (m)."""
        return float(self.position[2])


@dataclass(slots=True)
class TrajectoryPoint:
    """
    궤적 점.

    Attributes:
        time: 시간 (s)
        position: 3D 위치 (m)
        velocity: 3D 속도 (m/s)
    """

    time: float = 0.0
    position: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    velocity: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )


@dataclass(slots=True)
class ImpactResult:
    """
    충돌/착지 결과.

    Attributes:
        impact_point: 충돌/착지 지점
        impact_time: 충돌/착지 시간 (s)
        impact_velocity: 충돌 시 속도 (m/s)
        impact_angle: 진입 각도 (도)
    """

    impact_point: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    impact_time: float = 0.0
    impact_velocity: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    impact_angle: float = 0.0


# =============================================================================
# 기본 물리 계산
# =============================================================================

def calculate_gravity_force(
    mass: float = BASKETBALL_MASS,
    gravity: float = GRAVITY,
) -> NDArray[np.float64]:
    """
    중력 계산.

    Args:
        mass: 질량 (kg)
        gravity: 중력 가속도 (m/s²)

    Returns:
        중력 벡터 [0, 0, -mg] (N)
    """
    return np.array([0.0, 0.0, -mass * gravity], dtype=np.float64)


def calculate_drag_force(
    velocity: NDArray[np.float64],
    drag_coefficient: float = BASKETBALL_DRAG_COEFFICIENT,
    cross_section: float = BASKETBALL_CROSS_SECTION,
    air_density: float = AIR_DENSITY,
) -> NDArray[np.float64]:
    """
    공기 저항력 계산 (항력).

    F_drag = -0.5 * ρ * C_d * A * v² * v̂

    Args:
        velocity: 속도 벡터 (m/s)
        drag_coefficient: 항력 계수
        cross_section: 단면적 (m²)
        air_density: 공기 밀도 (kg/m³)

    Returns:
        항력 벡터 (N)
    """
    speed = np.linalg.norm(velocity)
    if speed < 1e-10:
        return np.zeros(3, dtype=np.float64)

    # 항력 크기
    drag_magnitude = 0.5 * air_density * drag_coefficient * cross_section * speed ** 2

    # 속도 반대 방향
    velocity_unit = velocity / speed

    return -drag_magnitude * velocity_unit


def calculate_magnus_force(
    velocity: NDArray[np.float64],
    angular_velocity: NDArray[np.float64],
    radius: float = BASKETBALL_RADIUS,
    air_density: float = AIR_DENSITY,
) -> NDArray[np.float64]:
    """
    마그누스 효과 (스핀에 의한 힘) 계산.

    F_magnus = 0.5 * ρ * C_L * A * v² * (ω × v̂)

    Args:
        velocity: 선속도 벡터 (m/s)
        angular_velocity: 각속도 벡터 (rad/s)
        radius: 공 반지름 (m)
        air_density: 공기 밀도 (kg/m³)

    Returns:
        마그누스 힘 벡터 (N)
    """
    speed = np.linalg.norm(velocity)
    if speed < 1e-10:
        return np.zeros(3, dtype=np.float64)

    # 마그누스 계수 (경험적 값)
    magnus_coefficient = 0.385

    # 단면적
    cross_section = math.pi * radius ** 2

    # 마그누스 힘 방향 (ω × v)
    velocity_unit = velocity / speed
    magnus_direction = np.cross(angular_velocity, velocity_unit)
    magnus_direction_norm = np.linalg.norm(magnus_direction)

    if magnus_direction_norm < 1e-10:
        return np.zeros(3, dtype=np.float64)

    magnus_direction /= magnus_direction_norm

    # 마그누스 힘 크기
    spin_factor = np.linalg.norm(angular_velocity) * radius / speed
    lift_coefficient = magnus_coefficient * spin_factor
    magnus_magnitude = 0.5 * air_density * lift_coefficient * cross_section * speed ** 2

    return magnus_magnitude * magnus_direction


# =============================================================================
# 발사체 운동
# =============================================================================

def projectile_motion(
    initial_position: NDArray[np.float64],
    initial_velocity: NDArray[np.float64],
    time: float,
    gravity: float = GRAVITY,
) -> ProjectileState:
    """
    발사체 운동 시뮬레이션 (공기저항 무시).

    기본 포물선 운동 방정식:
    x(t) = x₀ + vx₀*t
    y(t) = y₀ + vy₀*t
    z(t) = z₀ + vz₀*t - 0.5*g*t²

    Args:
        initial_position: 초기 위치 [x, y, z] (m)
        initial_velocity: 초기 속도 [vx, vy, vz] (m/s)
        time: 경과 시간 (s)
        gravity: 중력 가속도 (m/s²)

    Returns:
        지정 시간에서의 발사체 상태
    """
    # 위치 계산
    position = initial_position.copy()
    position[0] += initial_velocity[0] * time  # x
    position[1] += initial_velocity[1] * time  # y
    position[2] += initial_velocity[2] * time - 0.5 * gravity * time ** 2  # z

    # 속도 계산
    velocity = initial_velocity.copy()
    velocity[2] -= gravity * time

    return ProjectileState(
        position=position,
        velocity=velocity,
        time=time,
    )


def projectile_motion_with_drag(
    initial_position: NDArray[np.float64],
    initial_velocity: NDArray[np.float64],
    total_time: float,
    dt: float = 0.001,
    mass: float = BASKETBALL_MASS,
    gravity: float = GRAVITY,
    include_spin: bool = False,
    angular_velocity: NDArray[np.float64] | None = None,
) -> list[TrajectoryPoint]:
    """
    공기저항 포함 발사체 운동 시뮬레이션.

    4차 Runge-Kutta 방법으로 수치 적분합니다.

    Args:
        initial_position: 초기 위치 (m)
        initial_velocity: 초기 속도 (m/s)
        total_time: 총 시뮬레이션 시간 (s)
        dt: 시간 스텝 (s)
        mass: 질량 (kg)
        gravity: 중력 가속도 (m/s²)
        include_spin: 마그누스 효과 포함 여부
        angular_velocity: 각속도 (rad/s) - include_spin=True 시 필요

    Returns:
        궤적 점 리스트
    """
    trajectory: list[TrajectoryPoint] = []

    position = initial_position.astype(np.float64).copy()
    velocity = initial_velocity.astype(np.float64).copy()
    t = 0.0

    # 초기 상태 저장
    trajectory.append(TrajectoryPoint(
        time=t,
        position=position.copy(),
        velocity=velocity.copy(),
    ))

    spin = angular_velocity if include_spin and angular_velocity is not None else None

    def acceleration(pos: NDArray[np.float64], vel: NDArray[np.float64]) -> NDArray[np.float64]:
        """가속도 계산."""
        # 중력
        a = np.array([0.0, 0.0, -gravity], dtype=np.float64)

        # 공기저항
        drag = calculate_drag_force(vel)
        a += drag / mass

        # 마그누스 효과
        if spin is not None:
            magnus = calculate_magnus_force(vel, spin)
            a += magnus / mass

        return a

    while t < total_time:
        # 4차 Runge-Kutta
        k1_v = acceleration(position, velocity)
        k1_x = velocity

        k2_v = acceleration(position + 0.5 * dt * k1_x, velocity + 0.5 * dt * k1_v)
        k2_x = velocity + 0.5 * dt * k1_v

        k3_v = acceleration(position + 0.5 * dt * k2_x, velocity + 0.5 * dt * k2_v)
        k3_x = velocity + 0.5 * dt * k2_v

        k4_v = acceleration(position + dt * k3_x, velocity + dt * k3_v)
        k4_x = velocity + dt * k3_v

        # 업데이트
        velocity += (dt / 6.0) * (k1_v + 2 * k2_v + 2 * k3_v + k4_v)
        position += (dt / 6.0) * (k1_x + 2 * k2_x + 2 * k3_x + k4_x)
        t += dt

        # 지면 아래로 내려가면 중단
        if position[2] < 0:
            break

        trajectory.append(TrajectoryPoint(
            time=t,
            position=position.copy(),
            velocity=velocity.copy(),
        ))

    return trajectory


def predict_landing_point(
    initial_position: NDArray[np.float64],
    initial_velocity: NDArray[np.float64],
    target_height: float = 0.0,
    gravity: float = GRAVITY,
) -> ImpactResult | None:
    """
    착지 지점 예측 (공기저항 무시).

    2차 방정식으로 목표 높이에 도달하는 시간을 계산합니다.

    Args:
        initial_position: 초기 위치 (m)
        initial_velocity: 초기 속도 (m/s)
        target_height: 목표 높이 (m) - 기본값 0 (지면)
        gravity: 중력 가속도 (m/s²)

    Returns:
        착지 결과 (도달 불가능하면 None)
    """
    z0 = initial_position[2]
    vz0 = initial_velocity[2]

    # z = z0 + vz0*t - 0.5*g*t² = target_height
    # -0.5*g*t² + vz0*t + (z0 - target_height) = 0
    a = -0.5 * gravity
    b = vz0
    c = z0 - target_height

    discriminant = b ** 2 - 4 * a * c

    if discriminant < 0:
        return None  # 목표 높이에 도달 불가

    sqrt_discriminant = math.sqrt(discriminant)
    t1 = (-b + sqrt_discriminant) / (2 * a)
    t2 = (-b - sqrt_discriminant) / (2 * a)

    # 양수 시간 중 더 큰 값 선택 (하강 시점)
    impact_time = max(t for t in [t1, t2] if t > 0) if t1 > 0 or t2 > 0 else None

    if impact_time is None:
        return None

    # 착지 지점 계산
    impact_position = initial_position.copy()
    impact_position[0] += initial_velocity[0] * impact_time
    impact_position[1] += initial_velocity[1] * impact_time
    impact_position[2] = target_height

    # 착지 시 속도
    impact_velocity = initial_velocity.copy()
    impact_velocity[2] -= gravity * impact_time

    # 진입 각도 (수평면과의 각도)
    horizontal_speed = math.sqrt(impact_velocity[0] ** 2 + impact_velocity[1] ** 2)
    impact_angle = math.degrees(math.atan2(-impact_velocity[2], horizontal_speed))

    return ImpactResult(
        impact_point=impact_position,
        impact_time=impact_time,
        impact_velocity=impact_velocity,
        impact_angle=impact_angle,
    )


def predict_trajectory(
    initial_position: NDArray[np.float64],
    initial_velocity: NDArray[np.float64],
    duration: float = 2.0,
    num_points: int = 50,
    gravity: float = GRAVITY,
) -> list[TrajectoryPoint]:
    """
    전체 궤적 예측 (공기저항 무시).

    Args:
        initial_position: 초기 위치 (m)
        initial_velocity: 초기 속도 (m/s)
        duration: 예측 시간 (s)
        num_points: 궤적 점 수
        gravity: 중력 가속도 (m/s²)

    Returns:
        궤적 점 리스트
    """
    trajectory: list[TrajectoryPoint] = []
    times = np.linspace(0, duration, num_points)

    for t in times:
        state = projectile_motion(initial_position, initial_velocity, t, gravity)

        # 지면 아래로 내려가면 중단
        if state.height < 0:
            break

        trajectory.append(TrajectoryPoint(
            time=t,
            position=state.position.copy(),
            velocity=state.velocity.copy(),
        ))

    return trajectory


# =============================================================================
# 속도/가속도 추정
# =============================================================================

def estimate_initial_velocity(
    point1: NDArray[np.float64],
    point2: NDArray[np.float64],
    time_interval: float,
) -> NDArray[np.float64]:
    """
    두 점에서 초기 속도 추정.

    Args:
        point1: 첫 번째 위치 (m)
        point2: 두 번째 위치 (m)
        time_interval: 시간 간격 (s)

    Returns:
        추정 속도 (m/s)
    """
    if time_interval <= 0:
        return np.zeros(3, dtype=np.float64)

    return (point2 - point1) / time_interval


def estimate_velocity_from_trajectory(
    trajectory: list[TrajectoryPoint],
    method: str = "central",
) -> list[NDArray[np.float64]]:
    """
    궤적에서 속도 추정.

    Args:
        trajectory: 궤적 점 리스트
        method: 미분 방법 ("forward", "backward", "central")

    Returns:
        각 점의 속도 리스트
    """
    n = len(trajectory)
    velocities: list[NDArray[np.float64]] = []

    if n < 2:
        return velocities

    for i in range(n):
        if method == "forward" or (method == "central" and i == 0):
            if i < n - 1:
                dt = trajectory[i + 1].time - trajectory[i].time
                if dt > 0:
                    v = (trajectory[i + 1].position - trajectory[i].position) / dt
                else:
                    v = np.zeros(3, dtype=np.float64)
            else:
                v = velocities[-1] if velocities else np.zeros(3, dtype=np.float64)

        elif method == "backward" or (method == "central" and i == n - 1):
            if i > 0:
                dt = trajectory[i].time - trajectory[i - 1].time
                if dt > 0:
                    v = (trajectory[i].position - trajectory[i - 1].position) / dt
                else:
                    v = np.zeros(3, dtype=np.float64)
            else:
                v = np.zeros(3, dtype=np.float64)

        else:  # central
            dt = trajectory[i + 1].time - trajectory[i - 1].time
            if dt > 0:
                v = (trajectory[i + 1].position - trajectory[i - 1].position) / dt
            else:
                v = np.zeros(3, dtype=np.float64)

        velocities.append(v)

    return velocities


def estimate_acceleration(
    velocity1: NDArray[np.float64],
    velocity2: NDArray[np.float64],
    time_interval: float,
) -> NDArray[np.float64]:
    """
    두 속도에서 가속도 추정.

    Args:
        velocity1: 첫 번째 속도 (m/s)
        velocity2: 두 번째 속도 (m/s)
        time_interval: 시간 간격 (s)

    Returns:
        추정 가속도 (m/s²)
    """
    if time_interval <= 0:
        return np.zeros(3, dtype=np.float64)

    return (velocity2 - velocity1) / time_interval


# =============================================================================
# 스핀/회전
# =============================================================================

def calculate_spin_effect(
    spin_rate: float,
    axis: NDArray[np.float64],
    velocity: NDArray[np.float64],
) -> tuple[NDArray[np.float64], float]:
    """
    스핀 효과 계산.

    Args:
        spin_rate: 회전 속도 (rpm)
        axis: 회전축 (단위 벡터)
        velocity: 공 속도 (m/s)

    Returns:
        (편향 방향, 편향 크기) 튜플
    """
    # rpm → rad/s
    omega = spin_rate * (2 * math.pi / 60)
    angular_velocity = omega * axis / np.linalg.norm(axis)

    # 마그누스 힘 계산
    magnus = calculate_magnus_force(velocity, angular_velocity)
    magnitude = float(np.linalg.norm(magnus))

    if magnitude < 1e-10:
        return np.zeros(3, dtype=np.float64), 0.0

    direction = magnus / magnitude
    return direction, magnitude


def estimate_spin_from_trajectory(
    trajectory: list[TrajectoryPoint],
    mass: float = BASKETBALL_MASS,
    gravity: float = GRAVITY,
) -> NDArray[np.float64] | None:
    """
    궤적에서 스핀 추정.

    예상 포물선 궤적과의 편차를 분석하여 스핀을 추정합니다.

    Args:
        trajectory: 궤적 점 리스트
        mass: 질량 (kg)
        gravity: 중력 가속도 (m/s²)

    Returns:
        추정 각속도 (rad/s) 또는 None (추정 불가)
    """
    if len(trajectory) < 3:
        return None

    # 첫 두 점에서 초기 조건 추정
    initial_pos = trajectory[0].position
    initial_vel = estimate_initial_velocity(
        trajectory[0].position,
        trajectory[1].position,
        trajectory[1].time - trajectory[0].time,
    )

    # 이상적인 포물선과 비교하여 편차 계산
    deviations: list[NDArray[np.float64]] = []

    for point in trajectory[2:]:
        # 이상적인 포물선 위치
        ideal_state = projectile_motion(initial_pos, initial_vel, point.time, gravity)
        deviation = point.position - ideal_state.position
        deviations.append(deviation)

    if not deviations:
        return None

    # 평균 편차
    mean_deviation = np.mean(deviations, axis=0)

    # 편차가 매우 작으면 스핀 없음으로 판단
    if np.linalg.norm(mean_deviation) < 0.01:
        return None

    # 편차 방향에서 대략적인 스핀 축 추정
    # (실제로는 더 복잡한 역문제 풀이 필요)
    spin_axis = np.cross(initial_vel, mean_deviation)
    spin_axis_norm = np.linalg.norm(spin_axis)

    if spin_axis_norm < 1e-10:
        return None

    spin_axis /= spin_axis_norm

    # 대략적인 스핀 크기 추정 (단순화)
    avg_speed = np.mean([np.linalg.norm(p.velocity) for p in trajectory])
    deviation_magnitude = np.linalg.norm(mean_deviation)
    estimated_spin_rate = deviation_magnitude * avg_speed / (BASKETBALL_RADIUS ** 2)

    return estimated_spin_rate * spin_axis


# =============================================================================
# 슛 분석
# =============================================================================

def analyze_shot_trajectory(
    trajectory: list[TrajectoryPoint],
    hoop_position: NDArray[np.float64],
    hoop_radius: float = HOOP_RADIUS,
) -> dict:
    """
    슛 궤적 분석.

    Args:
        trajectory: 궤적 점 리스트
        hoop_position: 골대 림 중심 위치 [x, y, z] (m)
        hoop_radius: 림 반지름 (m)

    Returns:
        분석 결과 딕셔너리
    """
    if len(trajectory) < 2:
        return {"valid": False, "error": "insufficient_data"}

    # 릴리스 포인트 (첫 번째 점)
    release_point = trajectory[0]

    # 최고점 찾기
    peak_index = max(range(len(trajectory)), key=lambda i: trajectory[i].position[2])
    peak_point = trajectory[peak_index]

    # 릴리스 각도
    release_angle = calculate_release_angle(release_point.velocity)

    # 림 평면 통과 지점 찾기
    rim_crossing = None
    for i in range(len(trajectory) - 1):
        z1 = trajectory[i].position[2]
        z2 = trajectory[i + 1].position[2]

        if z1 >= hoop_position[2] >= z2:  # 하강 중 림 높이 통과
            # 선형 보간
            t_ratio = (z1 - hoop_position[2]) / (z1 - z2) if z1 != z2 else 0
            crossing_pos = trajectory[i].position + t_ratio * (
                trajectory[i + 1].position - trajectory[i].position
            )
            crossing_vel = trajectory[i].velocity + t_ratio * (
                trajectory[i + 1].velocity - trajectory[i].velocity
            )
            rim_crossing = {"position": crossing_pos, "velocity": crossing_vel}
            break

    # 진입 각도
    entry_angle = 0.0
    if rim_crossing is not None:
        entry_angle = calculate_entry_angle(rim_crossing["velocity"])

    # 림과의 거리
    distance_to_rim = 0.0
    if rim_crossing is not None:
        horizontal_offset = np.linalg.norm(
            rim_crossing["position"][:2] - hoop_position[:2]
        )
        distance_to_rim = horizontal_offset

    # 성공 여부 예측
    made = distance_to_rim <= hoop_radius if rim_crossing is not None else False

    return {
        "valid": True,
        "release_point": release_point.position.copy(),
        "release_velocity": release_point.velocity.copy(),
        "release_angle": release_angle,
        "peak_height": peak_point.position[2],
        "entry_angle": entry_angle,
        "distance_to_rim": distance_to_rim,
        "predicted_made": made,
    }


def calculate_release_angle(velocity: NDArray[np.float64]) -> float:
    """
    릴리스 각도 계산.

    수평면과 이루는 각도 (도).

    Args:
        velocity: 릴리스 속도 (m/s)

    Returns:
        릴리스 각도 (도)
    """
    horizontal_speed = math.sqrt(velocity[0] ** 2 + velocity[1] ** 2)
    vertical_speed = velocity[2]

    if horizontal_speed < 1e-10:
        return 90.0 if vertical_speed > 0 else -90.0

    return math.degrees(math.atan2(vertical_speed, horizontal_speed))


def calculate_entry_angle(velocity: NDArray[np.float64]) -> float:
    """
    진입 각도 계산.

    수평면 아래로 이루는 각도 (양수 값).

    Args:
        velocity: 진입 속도 (m/s)

    Returns:
        진입 각도 (도)
    """
    horizontal_speed = math.sqrt(velocity[0] ** 2 + velocity[1] ** 2)
    vertical_speed = -velocity[2]  # 하강이므로 부호 반전

    if horizontal_speed < 1e-10:
        return 90.0

    return math.degrees(math.atan2(vertical_speed, horizontal_speed))


def predict_shot_result(
    release_position: NDArray[np.float64],
    release_velocity: NDArray[np.float64],
    hoop_position: NDArray[np.float64],
    hoop_radius: float = HOOP_RADIUS,
    ball_radius: float = BASKETBALL_RADIUS,
) -> tuple[bool, float]:
    """
    슛 결과 예측.

    Args:
        release_position: 릴리스 위치 (m)
        release_velocity: 릴리스 속도 (m/s)
        hoop_position: 골대 위치 (m)
        hoop_radius: 림 반지름 (m)
        ball_radius: 공 반지름 (m)

    Returns:
        (성공 여부, 림 중심과의 거리) 튜플
    """
    # 림 높이에 도달하는 시점 계산
    result = predict_landing_point(
        release_position,
        release_velocity,
        target_height=hoop_position[2],
    )

    if result is None:
        return False, float("inf")

    # 림 중심과의 수평 거리
    horizontal_distance = np.linalg.norm(
        result.impact_point[:2] - hoop_position[:2]
    )

    # 공이 림을 통과할 수 있는 여유 공간
    clearance = hoop_radius - ball_radius

    made = horizontal_distance <= clearance

    return made, horizontal_distance


# =============================================================================
# 모듈 Export 정의 (PHASE_02 정의서 준수)
# =============================================================================

__all__ = [
    # 상수 (물리 상수)
    "GRAVITY",
    "BASKETBALL_MASS",
    "BASKETBALL_RADIUS",
    "BASKETBALL_DRAG_COEFFICIENT",
    "AIR_DENSITY",

    # 데이터 클래스
    "ProjectileState",
    "TrajectoryPoint",
    "ImpactResult",

    # 기본 물리
    "calculate_gravity_force",
    "calculate_drag_force",
    "calculate_magnus_force",

    # 발사체 운동
    "projectile_motion",
    "projectile_motion_with_drag",
    "predict_landing_point",
    "predict_trajectory",

    # 속도/가속도 추정
    "estimate_initial_velocity",
    "estimate_velocity_from_trajectory",
    "estimate_acceleration",

    # 스핀/회전
    "calculate_spin_effect",
    "estimate_spin_from_trajectory",

    # 슛 분석
    "analyze_shot_trajectory",
    "calculate_release_angle",
    "calculate_entry_angle",
    "predict_shot_result",
]

# 모듈 버전 정보
__version__ = "1.0.0"
