# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: kalman_utils.py
설명: 칼만 필터 유틸리티 (2D/3D 객체 추적용)
      - 등속/등가속 모션 모델
      - 2D/3D 칼만 필터 클래스
      - 확장 칼만 필터 (비선형)

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 1.0.0

참고:
    - PHASE_02_UTILS_IMPORT_SPEC.md 섹션 5
    - 순수 함수/클래스 모듈 (DI 없음)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto, unique
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 상수
# =============================================================================

# 기본 프로세스 노이즈 (모션 모델 불확실성)
DEFAULT_PROCESS_NOISE: float = 0.01

# 기본 측정 노이즈 (센서 노이즈)
DEFAULT_MEASUREMENT_NOISE: float = 0.1

# 기본 초기 공분산 (초기 불확실성)
DEFAULT_INITIAL_COVARIANCE: float = 1.0


# =============================================================================
# 열거형
# =============================================================================

@unique
class MotionModel(Enum):
    """
    모션 모델 열거형.

    칼만 필터에서 사용하는 객체 운동 모델입니다.
    """

    # 등속 모델 (Constant Velocity)
    # 상태: [x, y, vx, vy] (2D) 또는 [x, y, z, vx, vy, vz] (3D)
    CONSTANT_VELOCITY = auto()

    # 등가속 모델 (Constant Acceleration)
    # 상태: [x, y, vx, vy, ax, ay] (2D) 또는 [x, y, z, vx, vy, vz, ax, ay, az] (3D)
    CONSTANT_ACCELERATION = auto()


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class KalmanConfig:
    """
    칼만 필터 설정.

    Attributes:
        process_noise: 프로세스 노이즈 (Q 행렬 스케일)
        measurement_noise: 측정 노이즈 (R 행렬 스케일)
        initial_covariance: 초기 공분산 (P 행렬 스케일)
        motion_model: 모션 모델
        dt: 시간 간격 (초)
    """

    process_noise: float = DEFAULT_PROCESS_NOISE
    measurement_noise: float = DEFAULT_MEASUREMENT_NOISE
    initial_covariance: float = DEFAULT_INITIAL_COVARIANCE
    motion_model: MotionModel = MotionModel.CONSTANT_VELOCITY
    dt: float = 1.0 / 30.0  # 30 FPS 기본값


@dataclass(slots=True)
class KalmanState:
    """
    칼만 필터 상태.

    Attributes:
        mean: 상태 평균 벡터
        covariance: 상태 공분산 행렬
    """

    mean: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(4, dtype=np.float64)
    )
    covariance: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(4, dtype=np.float64)
    )

    @property
    def position(self) -> NDArray[np.float64]:
        """위치 벡터 (x, y) 또는 (x, y, z)."""
        if len(self.mean) >= 6:
            return self.mean[:3].copy()
        return self.mean[:2].copy()

    @property
    def velocity(self) -> NDArray[np.float64]:
        """속도 벡터."""
        if len(self.mean) >= 6:
            return self.mean[3:6].copy()
        return self.mean[2:4].copy()

    @property
    def position_uncertainty(self) -> float:
        """위치 불확실성 (표준편차)."""
        if len(self.mean) >= 6:
            return float(np.sqrt(
                self.covariance[0, 0] + self.covariance[1, 1] + self.covariance[2, 2]
            ))
        return float(np.sqrt(self.covariance[0, 0] + self.covariance[1, 1]))


@dataclass(slots=True)
class KalmanPrediction:
    """
    칼만 필터 예측 결과.

    Attributes:
        predicted_state: 예측된 상태
        predicted_measurement: 예측된 측정값
        innovation: 혁신 (실제 - 예측)
        innovation_covariance: 혁신 공분산
        mahalanobis_distance: 마할라노비스 거리 (이상치 검출용)
    """

    predicted_state: KalmanState = field(default_factory=KalmanState)
    predicted_measurement: NDArray[np.float64] | None = None
    innovation: NDArray[np.float64] | None = None
    innovation_covariance: NDArray[np.float64] | None = None
    mahalanobis_distance: float = 0.0


# =============================================================================
# 함수: 모션 모델 생성
# =============================================================================

def create_constant_velocity_model(
    dim: int,
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    등속 모션 모델 생성.

    상태 전이 행렬(F)과 프로세스 노이즈 행렬(Q)을 생성합니다.

    Args:
        dim: 공간 차원 (2 또는 3)
        dt: 시간 간격 (초)

    Returns:
        (F, Q) 튜플
        - F: 상태 전이 행렬 (state_dim x state_dim)
        - Q: 프로세스 노이즈 행렬 (state_dim x state_dim)

    Example:
        >>> F, Q = create_constant_velocity_model(dim=2, dt=1/30)
        >>> F.shape
        (4, 4)
    """
    state_dim = dim * 2  # [pos, vel]

    # 상태 전이 행렬 F
    # [x, y, vx, vy] -> [x + vx*dt, y + vy*dt, vx, vy]
    F = np.eye(state_dim, dtype=np.float64)
    for i in range(dim):
        F[i, dim + i] = dt

    # 프로세스 노이즈 행렬 Q (이산 백색 노이즈 모델)
    # 가속도 분산 기반 노이즈
    q = 1.0  # 가속도 표준편차
    dt2 = dt ** 2
    dt3 = dt ** 3
    dt4 = dt ** 4

    Q = np.zeros((state_dim, state_dim), dtype=np.float64)
    for i in range(dim):
        # 위치 노이즈
        Q[i, i] = dt4 / 4.0 * q
        Q[i, dim + i] = dt3 / 2.0 * q
        Q[dim + i, i] = dt3 / 2.0 * q
        # 속도 노이즈
        Q[dim + i, dim + i] = dt2 * q

    return F, Q


def create_constant_acceleration_model(
    dim: int,
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    등가속 모션 모델 생성.

    Args:
        dim: 공간 차원 (2 또는 3)
        dt: 시간 간격 (초)

    Returns:
        (F, Q) 튜플

    Example:
        >>> F, Q = create_constant_acceleration_model(dim=3, dt=1/30)
        >>> F.shape
        (9, 9)
    """
    state_dim = dim * 3  # [pos, vel, acc]
    dt2 = dt ** 2

    # 상태 전이 행렬 F
    F = np.eye(state_dim, dtype=np.float64)
    for i in range(dim):
        # 위치 업데이트: x = x + vx*dt + 0.5*ax*dt^2
        F[i, dim + i] = dt
        F[i, 2 * dim + i] = 0.5 * dt2
        # 속도 업데이트: vx = vx + ax*dt
        F[dim + i, 2 * dim + i] = dt

    # 프로세스 노이즈 행렬 Q (저크 노이즈 모델)
    q = 1.0  # 저크 표준편차
    dt3 = dt ** 3
    dt4 = dt ** 4
    dt5 = dt ** 5

    Q = np.zeros((state_dim, state_dim), dtype=np.float64)
    for i in range(dim):
        # 위치
        Q[i, i] = dt5 / 20.0 * q
        Q[i, dim + i] = dt4 / 8.0 * q
        Q[i, 2 * dim + i] = dt3 / 6.0 * q
        # 속도
        Q[dim + i, i] = dt4 / 8.0 * q
        Q[dim + i, dim + i] = dt3 / 3.0 * q
        Q[dim + i, 2 * dim + i] = dt2 / 2.0 * q
        # 가속도
        Q[2 * dim + i, i] = dt3 / 6.0 * q
        Q[2 * dim + i, dim + i] = dt2 / 2.0 * q
        Q[2 * dim + i, 2 * dim + i] = dt * q

    return F, Q


# =============================================================================
# 함수: 거리/혁신 계산
# =============================================================================

def compute_mahalanobis_distance(
    innovation: NDArray[np.float64],
    innovation_covariance: NDArray[np.float64],
) -> float:
    """
    마할라노비스 거리 계산.

    측정값이 예측에서 얼마나 벗어났는지를 공분산 고려하여 계산합니다.
    이상치 검출에 사용됩니다.

    Args:
        innovation: 혁신 벡터 (측정 - 예측)
        innovation_covariance: 혁신 공분산 행렬

    Returns:
        마할라노비스 거리

    Example:
        >>> innovation = np.array([1.0, 2.0])
        >>> S = np.eye(2)
        >>> d = compute_mahalanobis_distance(innovation, S)
        >>> d > 0
        True
    """
    try:
        S_inv = np.linalg.inv(innovation_covariance)
        distance_sq = float(innovation.T @ S_inv @ innovation)
        return np.sqrt(max(0.0, distance_sq))
    except np.linalg.LinAlgError:
        # 공분산 행렬이 특이행렬인 경우 유클리드 거리 반환
        return float(np.linalg.norm(innovation))


def compute_innovation(
    measurement: NDArray[np.float64],
    predicted_measurement: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    혁신 (Innovation) 계산.

    실제 측정값과 예측 측정값의 차이를 계산합니다.

    Args:
        measurement: 실제 측정값
        predicted_measurement: 예측 측정값

    Returns:
        혁신 벡터
    """
    return measurement - predicted_measurement


# =============================================================================
# 클래스: 2D 칼만 필터
# =============================================================================

class KalmanFilter2D:
    """
    2D 칼만 필터.

    2D 평면에서 객체 추적을 위한 칼만 필터입니다.
    등속 모델: 상태 = [x, y, vx, vy]
    등가속 모델: 상태 = [x, y, vx, vy, ax, ay]

    Attributes:
        config: 칼만 필터 설정
        state: 현재 상태
        F: 상태 전이 행렬
        H: 측정 행렬
        Q: 프로세스 노이즈 행렬
        R: 측정 노이즈 행렬

    Example:
        >>> kf = KalmanFilter2D()
        >>> kf.initialize(np.array([100.0, 200.0]))
        >>> prediction = kf.predict()
        >>> kf.update(np.array([102.0, 198.0]))
    """

    def __init__(self, config: KalmanConfig | None = None):
        """
        초기화.

        Args:
            config: 칼만 필터 설정 (None이면 기본값)
        """
        self.config = config or KalmanConfig()

        # 차원 계산
        if self.config.motion_model == MotionModel.CONSTANT_VELOCITY:
            self._state_dim = 4  # [x, y, vx, vy]
            self._measurement_dim = 2  # [x, y]
            self.F, self.Q = create_constant_velocity_model(2, self.config.dt)
        else:
            self._state_dim = 6  # [x, y, vx, vy, ax, ay]
            self._measurement_dim = 2
            self.F, self.Q = create_constant_acceleration_model(2, self.config.dt)

        # Q 스케일링
        self.Q *= self.config.process_noise

        # 측정 행렬 H (위치만 관측)
        self.H = np.zeros((self._measurement_dim, self._state_dim), dtype=np.float64)
        self.H[0, 0] = 1.0  # x
        self.H[1, 1] = 1.0  # y

        # 측정 노이즈 행렬 R
        self.R = np.eye(self._measurement_dim, dtype=np.float64) * self.config.measurement_noise

        # 상태 초기화
        self.state = KalmanState(
            mean=np.zeros(self._state_dim, dtype=np.float64),
            covariance=np.eye(self._state_dim, dtype=np.float64) * self.config.initial_covariance,
        )

        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """초기화 여부."""
        return self._initialized

    def initialize(
        self,
        position: NDArray[np.float64],
        velocity: NDArray[np.float64] | None = None,
    ) -> None:
        """
        필터 초기화.

        Args:
            position: 초기 위치 [x, y]
            velocity: 초기 속도 [vx, vy] (선택적)
        """
        self.state.mean[:2] = position

        if velocity is not None:
            self.state.mean[2:4] = velocity

        self.state.covariance = np.eye(
            self._state_dim, dtype=np.float64
        ) * self.config.initial_covariance

        self._initialized = True

    def predict(self, dt: float | None = None) -> KalmanPrediction:
        """
        예측 단계.

        다음 시간 스텝의 상태를 예측합니다.

        Args:
            dt: 시간 간격 (None이면 config.dt 사용)

        Returns:
            예측 결과
        """
        if dt is not None and dt != self.config.dt:
            # dt가 변경된 경우 F, Q 재계산
            if self.config.motion_model == MotionModel.CONSTANT_VELOCITY:
                F, Q = create_constant_velocity_model(2, dt)
            else:
                F, Q = create_constant_acceleration_model(2, dt)
            Q *= self.config.process_noise
        else:
            F, Q = self.F, self.Q

        # 상태 예측
        predicted_mean = F @ self.state.mean

        # 공분산 예측
        predicted_covariance = F @ self.state.covariance @ F.T + Q

        # 예측 측정값
        predicted_measurement = self.H @ predicted_mean

        # 혁신 공분산
        innovation_covariance = self.H @ predicted_covariance @ self.H.T + self.R

        # 상태 업데이트
        self.state.mean = predicted_mean
        self.state.covariance = predicted_covariance

        return KalmanPrediction(
            predicted_state=KalmanState(
                mean=predicted_mean.copy(),
                covariance=predicted_covariance.copy(),
            ),
            predicted_measurement=predicted_measurement,
            innovation_covariance=innovation_covariance,
        )

    def update(self, measurement: NDArray[np.float64]) -> KalmanState:
        """
        업데이트 단계.

        측정값으로 상태를 보정합니다.

        Args:
            measurement: 측정값 [x, y]

        Returns:
            업데이트된 상태
        """
        # 혁신 계산
        predicted_measurement = self.H @ self.state.mean
        innovation = measurement - predicted_measurement

        # 혁신 공분산
        S = self.H @ self.state.covariance @ self.H.T + self.R

        # 칼만 게인
        try:
            K = self.state.covariance @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # 특이행렬인 경우 의사역행렬 사용
            K = self.state.covariance @ self.H.T @ np.linalg.pinv(S)

        # 상태 업데이트
        self.state.mean = self.state.mean + K @ innovation

        # 공분산 업데이트 (Joseph form - 수치 안정성)
        I_KH = np.eye(self._state_dim) - K @ self.H
        self.state.covariance = (
            I_KH @ self.state.covariance @ I_KH.T + K @ self.R @ K.T
        )

        return KalmanState(
            mean=self.state.mean.copy(),
            covariance=self.state.covariance.copy(),
        )

    def reset(self) -> None:
        """필터 리셋."""
        self.state.mean = np.zeros(self._state_dim, dtype=np.float64)
        self.state.covariance = np.eye(
            self._state_dim, dtype=np.float64
        ) * self.config.initial_covariance
        self._initialized = False


# =============================================================================
# 클래스: 3D 칼만 필터
# =============================================================================

class KalmanFilter3D:
    """
    3D 칼만 필터.

    3D 공간에서 객체 추적을 위한 칼만 필터입니다.
    등속 모델: 상태 = [x, y, z, vx, vy, vz]
    등가속 모델: 상태 = [x, y, z, vx, vy, vz, ax, ay, az]

    Example:
        >>> kf = KalmanFilter3D()
        >>> kf.initialize(np.array([1.0, 2.0, 3.0]))
        >>> prediction = kf.predict()
        >>> kf.update(np.array([1.1, 2.1, 2.9]))
    """

    def __init__(self, config: KalmanConfig | None = None):
        """
        초기화.

        Args:
            config: 칼만 필터 설정
        """
        self.config = config or KalmanConfig()

        # 차원 계산
        if self.config.motion_model == MotionModel.CONSTANT_VELOCITY:
            self._state_dim = 6  # [x, y, z, vx, vy, vz]
            self._measurement_dim = 3  # [x, y, z]
            self.F, self.Q = create_constant_velocity_model(3, self.config.dt)
        else:
            self._state_dim = 9  # [x, y, z, vx, vy, vz, ax, ay, az]
            self._measurement_dim = 3
            self.F, self.Q = create_constant_acceleration_model(3, self.config.dt)

        # Q 스케일링
        self.Q *= self.config.process_noise

        # 측정 행렬 H
        self.H = np.zeros((self._measurement_dim, self._state_dim), dtype=np.float64)
        self.H[0, 0] = 1.0  # x
        self.H[1, 1] = 1.0  # y
        self.H[2, 2] = 1.0  # z

        # 측정 노이즈 행렬 R
        self.R = np.eye(self._measurement_dim, dtype=np.float64) * self.config.measurement_noise

        # 상태 초기화
        self.state = KalmanState(
            mean=np.zeros(self._state_dim, dtype=np.float64),
            covariance=np.eye(self._state_dim, dtype=np.float64) * self.config.initial_covariance,
        )

        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """초기화 여부."""
        return self._initialized

    def initialize(
        self,
        position: NDArray[np.float64],
        velocity: NDArray[np.float64] | None = None,
    ) -> None:
        """
        필터 초기화.

        Args:
            position: 초기 위치 [x, y, z]
            velocity: 초기 속도 [vx, vy, vz] (선택적)
        """
        self.state.mean[:3] = position

        if velocity is not None:
            self.state.mean[3:6] = velocity

        self.state.covariance = np.eye(
            self._state_dim, dtype=np.float64
        ) * self.config.initial_covariance

        self._initialized = True

    def predict(self, dt: float | None = None) -> KalmanPrediction:
        """
        예측 단계.

        Args:
            dt: 시간 간격

        Returns:
            예측 결과
        """
        if dt is not None and dt != self.config.dt:
            if self.config.motion_model == MotionModel.CONSTANT_VELOCITY:
                F, Q = create_constant_velocity_model(3, dt)
            else:
                F, Q = create_constant_acceleration_model(3, dt)
            Q *= self.config.process_noise
        else:
            F, Q = self.F, self.Q

        # 상태 예측
        predicted_mean = F @ self.state.mean
        predicted_covariance = F @ self.state.covariance @ F.T + Q

        # 예측 측정값
        predicted_measurement = self.H @ predicted_mean

        # 혁신 공분산
        innovation_covariance = self.H @ predicted_covariance @ self.H.T + self.R

        # 상태 업데이트
        self.state.mean = predicted_mean
        self.state.covariance = predicted_covariance

        return KalmanPrediction(
            predicted_state=KalmanState(
                mean=predicted_mean.copy(),
                covariance=predicted_covariance.copy(),
            ),
            predicted_measurement=predicted_measurement,
            innovation_covariance=innovation_covariance,
        )

    def update(self, measurement: NDArray[np.float64]) -> KalmanState:
        """
        업데이트 단계.

        Args:
            measurement: 측정값 [x, y, z]

        Returns:
            업데이트된 상태
        """
        # 혁신 계산
        predicted_measurement = self.H @ self.state.mean
        innovation = measurement - predicted_measurement

        # 혁신 공분산
        S = self.H @ self.state.covariance @ self.H.T + self.R

        # 칼만 게인
        try:
            K = self.state.covariance @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.state.covariance @ self.H.T @ np.linalg.pinv(S)

        # 상태 업데이트
        self.state.mean = self.state.mean + K @ innovation

        # 공분산 업데이트 (Joseph form)
        I_KH = np.eye(self._state_dim) - K @ self.H
        self.state.covariance = (
            I_KH @ self.state.covariance @ I_KH.T + K @ self.R @ K.T
        )

        return KalmanState(
            mean=self.state.mean.copy(),
            covariance=self.state.covariance.copy(),
        )

    def reset(self) -> None:
        """필터 리셋."""
        self.state.mean = np.zeros(self._state_dim, dtype=np.float64)
        self.state.covariance = np.eye(
            self._state_dim, dtype=np.float64
        ) * self.config.initial_covariance
        self._initialized = False


# =============================================================================
# 클래스: 확장 칼만 필터
# =============================================================================

class ExtendedKalmanFilter:
    """
    확장 칼만 필터 (EKF).

    비선형 시스템에 대한 칼만 필터입니다.
    사용자 정의 상태 전이 함수와 측정 함수를 지원합니다.

    Attributes:
        state_dim: 상태 차원
        measurement_dim: 측정 차원
        f: 상태 전이 함수 f(x)
        h: 측정 함수 h(x)
        F_jacobian: 상태 전이 야코비안 함수
        H_jacobian: 측정 야코비안 함수

    Example:
        >>> def f(x): return x  # 항등 전이
        >>> def h(x): return x[:2]  # 위치만 관측
        >>> ekf = ExtendedKalmanFilter(
        ...     state_dim=4, measurement_dim=2, f=f, h=h
        ... )
    """

    def __init__(
        self,
        state_dim: int,
        measurement_dim: int,
        f: Callable[[NDArray[np.float64]], NDArray[np.float64]],
        h: Callable[[NDArray[np.float64]], NDArray[np.float64]],
        F_jacobian: Callable[[NDArray[np.float64]], NDArray[np.float64]] | None = None,
        H_jacobian: Callable[[NDArray[np.float64]], NDArray[np.float64]] | None = None,
        config: KalmanConfig | None = None,
    ):
        """
        초기화.

        Args:
            state_dim: 상태 차원
            measurement_dim: 측정 차원
            f: 상태 전이 함수
            h: 측정 함수
            F_jacobian: 상태 전이 야코비안 (None이면 수치 미분)
            H_jacobian: 측정 야코비안 (None이면 수치 미분)
            config: 칼만 필터 설정
        """
        self.state_dim = state_dim
        self.measurement_dim = measurement_dim
        self.f = f
        self.h = h
        self.config = config or KalmanConfig()

        # 야코비안 함수 (없으면 수치 미분 사용)
        self._F_jacobian = F_jacobian or self._numerical_jacobian_f
        self._H_jacobian = H_jacobian or self._numerical_jacobian_h

        # 노이즈 행렬
        self.Q = np.eye(state_dim, dtype=np.float64) * self.config.process_noise
        self.R = np.eye(measurement_dim, dtype=np.float64) * self.config.measurement_noise

        # 상태
        self.state = KalmanState(
            mean=np.zeros(state_dim, dtype=np.float64),
            covariance=np.eye(state_dim, dtype=np.float64) * self.config.initial_covariance,
        )

        self._initialized = False
        self._epsilon = 1e-7  # 수치 미분용

    def _numerical_jacobian_f(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """상태 전이 야코비안 수치 계산."""
        J = np.zeros((self.state_dim, self.state_dim), dtype=np.float64)
        for i in range(self.state_dim):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += self._epsilon
            x_minus[i] -= self._epsilon
            J[:, i] = (self.f(x_plus) - self.f(x_minus)) / (2 * self._epsilon)
        return J

    def _numerical_jacobian_h(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """측정 야코비안 수치 계산."""
        J = np.zeros((self.measurement_dim, self.state_dim), dtype=np.float64)
        for i in range(self.state_dim):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += self._epsilon
            x_minus[i] -= self._epsilon
            J[:, i] = (self.h(x_plus) - self.h(x_minus)) / (2 * self._epsilon)
        return J

    @property
    def is_initialized(self) -> bool:
        """초기화 여부."""
        return self._initialized

    def initialize(
        self,
        mean: NDArray[np.float64],
        covariance: NDArray[np.float64] | None = None,
    ) -> None:
        """
        필터 초기화.

        Args:
            mean: 초기 상태 평균
            covariance: 초기 공분산 (선택적)
        """
        self.state.mean = mean.copy()
        if covariance is not None:
            self.state.covariance = covariance.copy()
        else:
            self.state.covariance = np.eye(
                self.state_dim, dtype=np.float64
            ) * self.config.initial_covariance
        self._initialized = True

    def predict(self) -> KalmanPrediction:
        """
        예측 단계.

        Returns:
            예측 결과
        """
        # 야코비안 계산
        F = self._F_jacobian(self.state.mean)

        # 상태 예측 (비선형)
        predicted_mean = self.f(self.state.mean)

        # 공분산 예측 (선형화)
        predicted_covariance = F @ self.state.covariance @ F.T + self.Q

        # 상태 업데이트
        self.state.mean = predicted_mean
        self.state.covariance = predicted_covariance

        return KalmanPrediction(
            predicted_state=KalmanState(
                mean=predicted_mean.copy(),
                covariance=predicted_covariance.copy(),
            ),
            predicted_measurement=self.h(predicted_mean),
        )

    def update(self, measurement: NDArray[np.float64]) -> KalmanState:
        """
        업데이트 단계.

        Args:
            measurement: 측정값

        Returns:
            업데이트된 상태
        """
        # 야코비안 계산
        H = self._H_jacobian(self.state.mean)

        # 혁신 계산
        predicted_measurement = self.h(self.state.mean)
        innovation = measurement - predicted_measurement

        # 혁신 공분산
        S = H @ self.state.covariance @ H.T + self.R

        # 칼만 게인
        try:
            K = self.state.covariance @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.state.covariance @ H.T @ np.linalg.pinv(S)

        # 상태 업데이트
        self.state.mean = self.state.mean + K @ innovation

        # 공분산 업데이트
        I_KH = np.eye(self.state_dim) - K @ H
        self.state.covariance = (
            I_KH @ self.state.covariance @ I_KH.T + K @ self.R @ K.T
        )

        return KalmanState(
            mean=self.state.mean.copy(),
            covariance=self.state.covariance.copy(),
        )

    def reset(self) -> None:
        """필터 리셋."""
        self.state.mean = np.zeros(self.state_dim, dtype=np.float64)
        self.state.covariance = np.eye(
            self.state_dim, dtype=np.float64
        ) * self.config.initial_covariance
        self._initialized = False


# =============================================================================
# 모듈 Export 정의 (PHASE_02 정의서 준수)
# =============================================================================

__all__ = [
    # Enum
    "MotionModel",

    # 데이터 클래스
    "KalmanConfig",
    "KalmanState",
    "KalmanPrediction",

    # 클래스
    "KalmanFilter2D",
    "KalmanFilter3D",
    "ExtendedKalmanFilter",

    # 상수
    "DEFAULT_PROCESS_NOISE",
    "DEFAULT_MEASUREMENT_NOISE",
    "DEFAULT_INITIAL_COVARIANCE",

    # 함수
    "create_constant_velocity_model",
    "create_constant_acceleration_model",
    "compute_mahalanobis_distance",
    "compute_innovation",
]

# 모듈 버전 정보
__version__ = "1.0.0"
