# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation
파일: processing.py
설명: 포즈 처리 통합 (정규화, 스무딩, 필터링)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

포함 내용:
    - 포즈 정규화 (hip-center, torso, shoulder, bounding box)
    - 시간적 스무딩 (Kalman filter, EMA, moving average, One Euro Filter)
    - 신뢰도 필터링 및 보간
    - 통합 PoseProcessor 클래스

설계 원칙:
    - DI 패턴 (설정 딕셔너리 주입)
    - 칼만 필터를 통한 노이즈 제거
    - 실시간 처리 최적화
    - 농구 분석에 최적화된 파라미터
"""
from __future__ import annotations

from typing import TYPE_CHECKING

# ============================================================
# 표준 라이브러리
# ============================================================
from dataclasses import dataclass
from enum import Enum, auto
import logging
import math
import threading
import time

import numpy as np
from numpy.typing import NDArray

# ============================================================
# 외부 라이브러리 (선택적)
# ============================================================
try:
    from filterpy.kalman import KalmanFilter
    FILTERPY_AVAILABLE = True
except ImportError:
    FILTERPY_AVAILABLE = False

if TYPE_CHECKING:
    from filterpy.kalman import KalmanFilter

# ============================================================
# 내부 모듈
# ============================================================
from pose_estimation.keypoint_types import (
    UnifiedKeypoint,
    KeypointData,
    UNIFIED_SYMMETRIC_PAIRS,
    LEFT_SIDE_KEYPOINTS,
    RIGHT_SIDE_KEYPOINTS,
)


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 상수 정의
# ============================================================
CONFIG_KEY_POSE_PROCESSOR = "pose.processing"

# 기본 파라미터
DEFAULT_MIN_CONFIDENCE = 0.5
DEFAULT_SMOOTHING_FACTOR = 0.5  # EMA alpha
DEFAULT_PROCESS_NOISE = 0.01
DEFAULT_MEASUREMENT_NOISE = 0.1
DEFAULT_TORSO_LENGTH = 0.4  # 정규화 기준 몸통 길이

# 히스토리 및 유효성 상수
MAX_HISTORY_FRAMES = 30  # 스무딩 히스토리 최대 프레임
MIN_VALID_KEYPOINTS_FOR_POSE = 4  # 포즈 유효성 최소 키포인트
DEFAULT_VALID_CONFIDENCE = 0.3  # 유효 판단 기본 신뢰도
DEFAULT_CRITICAL_CONFIDENCE = 0.5  # 필수 키포인트 신뢰도

# 필수/선택 키포인트
CRITICAL_KEYPOINTS: frozenset = frozenset([
    UnifiedKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.LEFT_HIP,
    UnifiedKeypoint.RIGHT_HIP,
])

OPTIONAL_KEYPOINTS: frozenset = frozenset([
    UnifiedKeypoint.LEFT_EAR,
    UnifiedKeypoint.RIGHT_EAR,
    UnifiedKeypoint.LEFT_INDEX,
    UnifiedKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.LEFT_PINKY,
    UnifiedKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.LEFT_THUMB,
    UnifiedKeypoint.RIGHT_THUMB,
])


# ============================================================
# 열거형 정의
# ============================================================
class NormalizationMethod(Enum):
    """정규화 방법."""
    HIP_CENTER = auto()  # 골반 중심 기준
    TORSO = auto()  # 몸통 기준 (어깨-엉덩이)
    SHOULDER_CENTER = auto()  # 어깨 중심 기준
    BOUNDING_BOX = auto()  # 바운딩 박스 기준


class ScaleReference(Enum):
    """스케일 기준."""
    TORSO_HEIGHT = auto()  # 어깨-엉덩이 거리
    SHOULDER_WIDTH = auto()  # 어깨 너비
    HIP_WIDTH = auto()  # 엉덩이 너비
    FIXED = auto()  # 고정 스케일


class SmoothingMode(Enum):
    """스무딩 모드."""
    NONE = auto()  # 스무딩 없음
    EMA = auto()  # 지수 이동 평균
    KALMAN = auto()  # 칼만 필터
    MOVING_AVERAGE = auto()  # 단순 이동 평균
    ONE_EURO = auto()  # One Euro Filter (실시간 포즈 최적)


class TrackState(Enum):
    """트래킹 상태."""
    NEW = auto()  # 새로운 트랙
    TRACKED = auto()  # 트래킹 중
    LOST = auto()  # 잃어버림
    REACQUIRED = auto()  # 재획득


# ============================================================
# 데이터 클래스 정의
# ============================================================
@dataclass(slots=True)
class NormalizationConfig:
    """정규화 설정."""
    method: NormalizationMethod = NormalizationMethod.HIP_CENTER
    scale_reference: ScaleReference = ScaleReference.TORSO_HEIGHT
    target_scale: float = 1.0  # 목표 스케일
    center_on_hip: bool = True
    rotate_to_vertical: bool = False
    flip_for_handedness: bool = False  # 주사용 손 기준으로 뒤집기


@dataclass(slots=True)
class NormalizationResult:
    """정규화 결과."""
    keypoints: NDArray[np.float32]  # 정규화된 키포인트 (N, 4)
    center: tuple[float, float]  # 원본 중심점 (복원용)
    scale: float  # 원본 스케일 (복원용)
    rotation: float  # 원본 회전각 (복원용, 라디안)
    success: bool = True
    message: str = ""


@dataclass(slots=True)
class SmoothingConfig:
    """스무딩 설정."""
    mode: SmoothingMode = SmoothingMode.KALMAN
    ema_alpha: float = 0.5  # EMA 가중치
    window_size: int = 5  # 이동 평균 윈도우
    process_noise: float = 0.01  # 칼만 프로세스 노이즈
    measurement_noise: float = 0.1  # 칼만 측정 노이즈
    min_confidence_for_update: float = 0.3  # 업데이트 최소 신뢰도
    # One Euro Filter 파라미터
    one_euro_min_cutoff: float = 1.7  # 최소 차단 주파수 — 낮을수록 강한 스무딩
    one_euro_beta: float = 0.3  # 속도 민감도 — 높을수록 빠른 동작 추종
    one_euro_d_cutoff: float = 1.0  # 미분 차단 주파수 (대부분 1.0 고정)


@dataclass(slots=True)
class SmoothedPose:
    """스무딩된 포즈."""
    keypoints: NDArray[np.float32]
    velocities: NDArray[np.float32] | None = None
    track_state: TrackState = TrackState.TRACKED
    frame_count: int = 0
    timestamp: float = 0.0


@dataclass(slots=True)
class ConfidenceThresholds:
    """신뢰도 임계값."""
    critical: float = 0.5  # 필수 키포인트 최소 신뢰도
    normal: float = 0.3  # 일반 키포인트 최소 신뢰도
    optional: float = 0.2  # 선택적 키포인트 최소 신뢰도
    pose_validity: float = 0.4  # 포즈 전체 유효성 평균 신뢰도


@dataclass(slots=True)
class FilterResult:
    """필터링 결과."""
    keypoints: NDArray[np.float32]  # 필터링된 키포인트
    valid_mask: NDArray[np.bool_]  # 유효 키포인트 마스크
    average_confidence: float
    valid_count: int
    total_count: int
    is_valid: bool  # 포즈 전체 유효성


# ============================================================
# 칼만 필터 트래커 클래스
# ============================================================
class KeypointKalmanTracker:
    """
    개별 키포인트용 칼만 필터 트래커.

    2D 위치 + 속도를 추적합니다.
    상태 벡터: [x, y, vx, vy]
    """

    __slots__ = (
        "_initialized", "_kf", "_process_noise",
        "_measurement_noise", "_last_measurement", "_miss_count",
    )

    def __init__(
        self,
        process_noise: float = DEFAULT_PROCESS_NOISE,
        measurement_noise: float = DEFAULT_MEASUREMENT_NOISE,
    ) -> None:
        """
        칼만 필터 초기화.

        Args:
            process_noise: 프로세스 노이즈 (동작 불확실성)
            measurement_noise: 측정 노이즈 (관측 불확실성)
        """
        self._initialized = False
        self._kf: KalmanFilter | None = None
        self._process_noise = process_noise
        self._measurement_noise = measurement_noise
        self._last_measurement: NDArray | None = None
        self._miss_count = 0

        if FILTERPY_AVAILABLE:
            self._init_kalman_filter()

    def _init_kalman_filter(self) -> None:
        """칼만 필터 내부 초기화."""
        if not FILTERPY_AVAILABLE:
            return

        # 상태 차원: 4 (x, y, vx, vy)
        # 측정 차원: 2 (x, y)
        self._kf = KalmanFilter(dim_x=4, dim_z=2)

        # 상태 전이 행렬 (등속 모델)
        dt = 1.0 / 30.0  # 30 FPS 가정
        self._kf.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)

        # 측정 행렬
        self._kf.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float32)

        # 프로세스 노이즈 공분산
        q = self._process_noise
        self._kf.Q = np.array([
            [q, 0, 0, 0],
            [0, q, 0, 0],
            [0, 0, q * 10, 0],
            [0, 0, 0, q * 10],
        ], dtype=np.float32)

        # 측정 노이즈 공분산
        r = self._measurement_noise
        self._kf.R = np.array([
            [r, 0],
            [0, r],
        ], dtype=np.float32)

        # 초기 상태 공분산
        self._kf.P *= 10.0

    def initialize(self, x: float, y: float) -> None:
        """
        초기 위치로 초기화.

        Args:
            x: 초기 x 좌표
            y: 초기 y 좌표
        """
        if not FILTERPY_AVAILABLE or self._kf is None:
            self._last_measurement = np.array([x, y], dtype=np.float32)
            self._initialized = True
            return

        self._kf.x = np.array([[x], [y], [0], [0]], dtype=np.float32)
        self._last_measurement = np.array([x, y], dtype=np.float32)
        self._initialized = True
        self._miss_count = 0

    def predict(self) -> tuple[float, float]:
        """
        다음 위치 예측.

        Returns:
            예측된 (x, y) 좌표
        """
        if not self._initialized:
            return (0.0, 0.0)

        if not FILTERPY_AVAILABLE or self._kf is None:
            if self._last_measurement is not None:
                return (float(self._last_measurement[0]), float(self._last_measurement[1]))
            return (0.0, 0.0)

        self._kf.predict()
        return (float(self._kf.x[0, 0]), float(self._kf.x[1, 0]))

    def update(self, x: float, y: float) -> tuple[float, float]:
        """
        측정값으로 업데이트.

        Args:
            x: 측정된 x 좌표
            y: 측정된 y 좌표

        Returns:
            필터링된 (x, y) 좌표
        """
        if not self._initialized:
            self.initialize(x, y)
            return (x, y)

        if not FILTERPY_AVAILABLE or self._kf is None:
            # 단순 EMA 폴백
            if self._last_measurement is not None:
                alpha = 0.5
                fx = alpha * x + (1 - alpha) * self._last_measurement[0]
                fy = alpha * y + (1 - alpha) * self._last_measurement[1]
                self._last_measurement = np.array([fx, fy], dtype=np.float32)
                return (fx, fy)
            return (x, y)

        measurement = np.array([[x], [y]], dtype=np.float32)
        self._kf.update(measurement)
        self._last_measurement = np.array([x, y], dtype=np.float32)
        self._miss_count = 0

        return (float(self._kf.x[0, 0]), float(self._kf.x[1, 0]))

    def get_velocity(self) -> tuple[float, float]:
        """
        현재 속도 반환.

        Returns:
            (vx, vy) 속도
        """
        if not FILTERPY_AVAILABLE or self._kf is None:
            return (0.0, 0.0)

        if not self._initialized:
            return (0.0, 0.0)

        return (float(self._kf.x[2, 0]), float(self._kf.x[3, 0]))

    def mark_missed(self) -> None:
        """측정 누락 표시."""
        self._miss_count += 1

    @property
    def is_lost(self) -> bool:
        """트랙 손실 여부."""
        return self._miss_count > 5


# ============================================================
# One Euro Filter (Casiez et al. 2012)
# ============================================================
class _OneEuroFilter1D:
    """
    1차원 One Euro Filter.

    Casiez et al. 2012 — "1€ Filter: A Simple Speed-based Low-pass Filter
    for Noisy Input in Interactive Systems"

    느린 움직임 → 강하게 스무딩 (떨림 제거)
    빠른 움직임 → 약하게 스무딩 (동작 추종)

    Args:
        min_cutoff: 최소 차단 주파수 (Hz). 작을수록 강한 스무딩.
        beta: 속도 민감도. 클수록 빠른 동작 추종.
        d_cutoff: 미분 신호 차단 주파수 (대부분 1.0).
    """

    __slots__ = ("_min_cutoff", "_beta", "_d_cutoff",
                 "_x_prev", "_dx_prev", "_t_prev")

    def __init__(
        self,
        min_cutoff: float = 1.7,
        beta: float = 0.3,
        d_cutoff: float = 1.0,
    ) -> None:
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff
        self._x_prev: float | None = None
        self._dx_prev: float = 0.0
        self._t_prev: float | None = None

    @staticmethod
    def _alpha(t_e: float, cutoff: float) -> float:
        """저역 통과 스무딩 계수 계산."""
        r = 2.0 * math.pi * cutoff * t_e
        return r / (r + 1.0)

    def filter(self, x: float, t: float) -> float:
        """
        값 필터링.

        Args:
            x: 현재 측정값
            t: 현재 타임스탬프 (초)

        Returns:
            필터링된 값
        """
        if self._t_prev is None:
            self._x_prev = x
            self._t_prev = t
            return x

        t_e = t - self._t_prev
        if t_e <= 0:
            return self._x_prev  # type: ignore[return-value]

        # 속도 추정 (저역 통과)
        a_d = self._alpha(t_e, self._d_cutoff)
        dx = (x - self._x_prev) / t_e  # type: ignore[operator]
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev

        # 적응형 차단 주파수
        cutoff = self._min_cutoff + self._beta * abs(dx_hat)

        # 위치 저역 통과
        a = self._alpha(t_e, cutoff)
        x_hat = a * x + (1.0 - a) * self._x_prev  # type: ignore[operator]

        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = t

        return x_hat

    def reset(self) -> None:
        """필터 상태 초기화."""
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None


class _KeypointOneEuroBank:
    """
    N개 키포인트에 대한 One Euro Filter 뱅크.

    각 키포인트의 (x, y)에 독립적인 1D 필터를 적용.
    신뢰도(confidence)는 필터링하지 않고 원본 유지.
    """

    def __init__(
        self,
        n_keypoints: int,
        min_cutoff: float = 1.7,
        beta: float = 0.3,
        d_cutoff: float = 1.0,
    ) -> None:
        self._n_kps = n_keypoints
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff
        self._filters_x = [
            _OneEuroFilter1D(min_cutoff, beta, d_cutoff) for _ in range(n_keypoints)
        ]
        self._filters_y = [
            _OneEuroFilter1D(min_cutoff, beta, d_cutoff) for _ in range(n_keypoints)
        ]

    def smooth(
        self,
        kps: NDArray[np.float32],
        timestamp: float,
        min_confidence: float = 0.1,
    ) -> NDArray[np.float32]:
        """
        키포인트 배열 스무딩.

        Args:
            kps: (N, 3|4) 배열 [x, y, conf (, visibility)]
            timestamp: 현재 타임스탬프 (초)
            min_confidence: 이 값 미만이면 스킵 (필터 상태 유지)

        Returns:
            스무딩된 키포인트. confidence 원본 유지.
        """
        result = kps.copy()
        n = min(kps.shape[0], self._n_kps)
        conf_idx = 2 if kps.shape[1] == 3 else 3

        for i in range(n):
            if kps[i, conf_idx] < min_confidence:
                continue
            result[i, 0] = self._filters_x[i].filter(float(kps[i, 0]), timestamp)
            result[i, 1] = self._filters_y[i].filter(float(kps[i, 1]), timestamp)

        return result

    def reset(self) -> None:
        """모든 필터 초기화."""
        for f in self._filters_x:
            f.reset()
        for f in self._filters_y:
            f.reset()


# ============================================================
# 시간적 스무더 클래스
# ============================================================
class TemporalSmoother:
    """
    포즈 시퀀스 시간적 스무딩.

    여러 프레임에 걸친 키포인트 스무딩을 수행합니다.
    칼만 필터, EMA, 이동 평균, One Euro Filter 지원.

    Example:
        >>> smoother = TemporalSmoother(SmoothingConfig())
        >>> smoothed = smoother.smooth(keypoints, track_id="player_1")
    """

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        """
        스무더 초기화.

        Args:
            config: 스무딩 설정
        """
        self._config = config or SmoothingConfig()
        self._tracks: dict[str, dict[int, KeypointKalmanTracker]] = {}
        self._history: dict[str, list[NDArray]] = {}
        self._frame_counts: dict[str, int] = {}
        self._one_euro_banks: dict[str, _KeypointOneEuroBank] = {}
        self._lock = threading.Lock()

    def smooth(
        self,
        keypoints: NDArray[np.float32],
        track_id: str = "default",
        timestamp: float | None = None,
    ) -> SmoothedPose:
        """
        키포인트 스무딩.

        Args:
            keypoints: 키포인트 배열 (N, 3) 또는 (N, 4)
            track_id: 트랙 ID (인물별 구분)
            timestamp: 타임스탬프 (선택)

        Returns:
            스무딩된 포즈
        """
        if self._config.mode == SmoothingMode.NONE:
            return SmoothedPose(
                keypoints=keypoints.copy(),
                track_state=TrackState.TRACKED,
                timestamp=timestamp if timestamp is not None else time.time(),
            )

        with self._lock:
            # 트랙 초기화
            if track_id not in self._tracks:
                self._tracks[track_id] = {}
                self._history[track_id] = []
                self._frame_counts[track_id] = 0

            self._frame_counts[track_id] += 1
            frame_count = self._frame_counts[track_id]

            # 스무딩 적용
            if self._config.mode == SmoothingMode.KALMAN:
                smoothed = self._smooth_kalman(keypoints, track_id)
            elif self._config.mode == SmoothingMode.EMA:
                smoothed = self._smooth_ema(keypoints, track_id)
            elif self._config.mode == SmoothingMode.MOVING_AVERAGE:
                smoothed = self._smooth_moving_average(keypoints, track_id)
            elif self._config.mode == SmoothingMode.ONE_EURO:
                smoothed = self._smooth_one_euro(
                    keypoints, track_id,
                    timestamp if timestamp is not None else time.time(),
                )
            else:
                smoothed = keypoints.copy()

            # 속도 계산
            velocities = self._calculate_velocities(track_id)

            # 트랙 상태 결정
            track_state = TrackState.NEW if frame_count == 1 else TrackState.TRACKED

            return SmoothedPose(
                keypoints=smoothed,
                velocities=velocities,
                track_state=track_state,
                frame_count=frame_count,
                timestamp=timestamp if timestamp is not None else time.time(),
            )

    def _smooth_kalman(
        self,
        keypoints: NDArray[np.float32],
        track_id: str,
    ) -> NDArray[np.float32]:
        """칼만 필터 스무딩."""
        trackers = self._tracks[track_id]
        smoothed = keypoints.copy()
        num_keypoints = len(keypoints)

        for kp_idx in range(num_keypoints):
            # 신뢰도 확인
            conf_idx = 2 if keypoints.shape[1] == 3 else 3
            confidence = keypoints[kp_idx, conf_idx]

            if confidence < self._config.min_confidence_for_update:
                # 예측만 수행
                if kp_idx in trackers and trackers[kp_idx]._initialized:
                    px, py = trackers[kp_idx].predict()
                    smoothed[kp_idx, 0] = px
                    smoothed[kp_idx, 1] = py
                    trackers[kp_idx].mark_missed()
                continue

            # 트래커 초기화 또는 업데이트
            x, y = keypoints[kp_idx, 0], keypoints[kp_idx, 1]

            if kp_idx not in trackers:
                trackers[kp_idx] = KeypointKalmanTracker(
                    process_noise=self._config.process_noise,
                    measurement_noise=self._config.measurement_noise,
                )

            fx, fy = trackers[kp_idx].update(x, y)
            smoothed[kp_idx, 0] = fx
            smoothed[kp_idx, 1] = fy

        return smoothed

    def _smooth_ema(
        self,
        keypoints: NDArray[np.float32],
        track_id: str,
    ) -> NDArray[np.float32]:
        """지수 이동 평균 스무딩."""
        history = self._history[track_id]
        alpha = self._config.ema_alpha

        if len(history) == 0:
            history.append(keypoints.copy())
            return keypoints.copy()

        prev = history[-1]
        smoothed = alpha * keypoints + (1 - alpha) * prev

        # 신뢰도 보존
        conf_idx = 2 if keypoints.shape[1] == 3 else 3
        smoothed[:, conf_idx] = keypoints[:, conf_idx]

        history.append(smoothed.copy())
        if len(history) > MAX_HISTORY_FRAMES:
            history.pop(0)

        return smoothed

    def _smooth_moving_average(
        self,
        keypoints: NDArray[np.float32],
        track_id: str,
    ) -> NDArray[np.float32]:
        """단순 이동 평균 스무딩."""
        history = self._history[track_id]
        history.append(keypoints.copy())

        window = self._config.window_size
        if len(history) > window:
            history.pop(0)

        # 이동 평균 계산
        stacked = np.stack(history, axis=0)
        smoothed = np.mean(stacked, axis=0).astype(np.float32)

        # 신뢰도는 현재 값 유지
        conf_idx = 2 if keypoints.shape[1] == 3 else 3
        smoothed[:, conf_idx] = keypoints[:, conf_idx]

        return smoothed

    def _smooth_one_euro(
        self,
        keypoints: NDArray[np.float32],
        track_id: str,
        timestamp: float,
    ) -> NDArray[np.float32]:
        """
        One Euro Filter 스무딩.

        Casiez et al. 2012 — 실시간 포즈 스무딩에 최적.
        느린 동작에서 떨림을 강하게 제거하고,
        빠른 동작(슛, 드리블)은 지연 없이 추종합니다.

        Args:
            keypoints: (N, 3|4) 키포인트 배열
            track_id: 트랙 ID (인물별 독립 필터)
            timestamp: 타임스탬프 (초 단위)

        Returns:
            스무딩된 키포인트 (confidence 원본 유지)
        """
        # 트랙별 One Euro 필터 뱅크 생성 (lazy)
        if track_id not in self._one_euro_banks:
            n_kps = keypoints.shape[0]
            self._one_euro_banks[track_id] = _KeypointOneEuroBank(
                n_keypoints=n_kps,
                min_cutoff=self._config.one_euro_min_cutoff,
                beta=self._config.one_euro_beta,
                d_cutoff=self._config.one_euro_d_cutoff,
            )

        bank = self._one_euro_banks[track_id]
        return bank.smooth(
            keypoints,
            timestamp=timestamp,
            min_confidence=self._config.min_confidence_for_update,
        )

    def _calculate_velocities(
        self,
        track_id: str,
    ) -> NDArray[np.float32] | None:
        """속도 계산."""
        if self._config.mode != SmoothingMode.KALMAN:
            return None

        trackers = self._tracks.get(track_id, {})
        if not trackers:
            return None

        num_keypoints = max(trackers.keys()) + 1 if trackers else 0
        velocities = np.zeros((num_keypoints, 2), dtype=np.float32)

        for kp_idx, tracker in trackers.items():
            vx, vy = tracker.get_velocity()
            velocities[kp_idx] = [vx, vy]

        return velocities

    def reset_track(self, track_id: str) -> None:
        """트랙 초기화."""
        with self._lock:
            if track_id in self._tracks:
                del self._tracks[track_id]
            if track_id in self._history:
                del self._history[track_id]
            if track_id in self._frame_counts:
                del self._frame_counts[track_id]
            if track_id in self._one_euro_banks:
                del self._one_euro_banks[track_id]

    def reset_all(self) -> None:
        """모든 트랙 초기화."""
        with self._lock:
            self._tracks.clear()
            self._history.clear()
            self._frame_counts.clear()
            self._one_euro_banks.clear()


# ============================================================
# 정규화 함수
# ============================================================
def normalize_pose(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """
    포즈 정규화 (통합 함수).

    Args:
        keypoints: 키포인트 배열 (N, 3) 또는 (N, 4)
        config: 정규화 설정

    Returns:
        정규화 결과
    """
    if config is None:
        config = NormalizationConfig()

    if config.method == NormalizationMethod.HIP_CENTER:
        return normalize_to_hip_center(keypoints, config)
    elif config.method == NormalizationMethod.TORSO:
        return normalize_to_torso(keypoints, config)
    elif config.method == NormalizationMethod.SHOULDER_CENTER:
        return _normalize_to_shoulder_center(keypoints, config)
    elif config.method == NormalizationMethod.BOUNDING_BOX:
        return _normalize_to_bounding_box(keypoints, config)
    else:
        return NormalizationResult(
            keypoints=keypoints.copy(),
            center=(0.0, 0.0),
            scale=1.0,
            rotation=0.0,
            success=False,
            message=f"지원하지 않는 정규화 방법: {config.method}",
        )


def normalize_to_hip_center(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """
    골반 중심(hip center) 기준 정규화.

    Args:
        keypoints: 키포인트 배열
        config: 정규화 설정

    Returns:
        정규화 결과
    """
    normalized = keypoints.copy()
    num_kp = len(keypoints)

    # 엉덩이 인덱스
    left_hip_idx = UnifiedKeypoint.LEFT_HIP.value
    right_hip_idx = UnifiedKeypoint.RIGHT_HIP.value

    # 필수 키포인트 유효성 확인
    conf_idx = 2 if keypoints.shape[1] == 3 else 3
    left_valid = left_hip_idx < num_kp and keypoints[left_hip_idx, conf_idx] > 0.1
    right_valid = right_hip_idx < num_kp and keypoints[right_hip_idx, conf_idx] > 0.1

    if not (left_valid and right_valid):
        return NormalizationResult(
            keypoints=normalized,
            center=(0.0, 0.0),
            scale=1.0,
            rotation=0.0,
            success=False,
            message="엉덩이 키포인트 누락",
        )

    # 골반 중심 계산
    hip_center_x = (keypoints[left_hip_idx, 0] + keypoints[right_hip_idx, 0]) / 2
    hip_center_y = (keypoints[left_hip_idx, 1] + keypoints[right_hip_idx, 1]) / 2

    # 중심 이동
    normalized[:, 0] -= hip_center_x
    normalized[:, 1] -= hip_center_y

    # 스케일 정규화
    scale = _calculate_scale(keypoints, config)
    if scale > 0:
        target = config.target_scale if config else 1.0
        normalized[:, 0] *= target / scale
        normalized[:, 1] *= target / scale
        if keypoints.shape[1] > 3:
            normalized[:, 2] *= target / scale  # z 좌표도 스케일링

    return NormalizationResult(
        keypoints=normalized,
        center=(float(hip_center_x), float(hip_center_y)),
        scale=float(scale),
        rotation=0.0,
        success=True,
    )


def normalize_to_torso(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """
    몸통(torso) 기준 정규화.

    어깨-엉덩이 사각형을 기준으로 정규화합니다.

    Args:
        keypoints: 키포인트 배열
        config: 정규화 설정

    Returns:
        정규화 결과
    """
    normalized = keypoints.copy()

    # 몸통 키포인트 인덱스
    ls_idx = UnifiedKeypoint.LEFT_SHOULDER.value
    rs_idx = UnifiedKeypoint.RIGHT_SHOULDER.value
    lh_idx = UnifiedKeypoint.LEFT_HIP.value
    rh_idx = UnifiedKeypoint.RIGHT_HIP.value

    # 유효성 확인
    conf_idx = 2 if keypoints.shape[1] == 3 else 3
    indices = [ls_idx, rs_idx, lh_idx, rh_idx]

    for idx in indices:
        if idx >= len(keypoints) or keypoints[idx, conf_idx] < 0.1:
            return NormalizationResult(
                keypoints=normalized,
                center=(0.0, 0.0),
                scale=1.0,
                rotation=0.0,
                success=False,
                message="몸통 키포인트 누락",
            )

    # 몸통 중심 계산
    torso_x = (keypoints[ls_idx, 0] + keypoints[rs_idx, 0] +
               keypoints[lh_idx, 0] + keypoints[rh_idx, 0]) / 4
    torso_y = (keypoints[ls_idx, 1] + keypoints[rs_idx, 1] +
               keypoints[lh_idx, 1] + keypoints[rh_idx, 1]) / 4

    # 중심 이동
    normalized[:, 0] -= torso_x
    normalized[:, 1] -= torso_y

    # 스케일 계산 (몸통 높이 기준)
    shoulder_center_y = (keypoints[ls_idx, 1] + keypoints[rs_idx, 1]) / 2
    hip_center_y = (keypoints[lh_idx, 1] + keypoints[rh_idx, 1]) / 2
    torso_height = abs(hip_center_y - shoulder_center_y)

    if torso_height > 0.01:
        target = config.target_scale if config else DEFAULT_TORSO_LENGTH
        scale_factor = target / torso_height
        normalized[:, :2] *= scale_factor
        if keypoints.shape[1] > 3:
            normalized[:, 2] *= scale_factor
    else:
        torso_height = 1.0

    return NormalizationResult(
        keypoints=normalized,
        center=(float(torso_x), float(torso_y)),
        scale=float(torso_height),
        rotation=0.0,
        success=True,
    )


def _normalize_to_shoulder_center(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """어깨 중심 기준 정규화."""
    normalized = keypoints.copy()

    ls_idx = UnifiedKeypoint.LEFT_SHOULDER.value
    rs_idx = UnifiedKeypoint.RIGHT_SHOULDER.value

    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    if (ls_idx >= len(keypoints) or rs_idx >= len(keypoints) or
            keypoints[ls_idx, conf_idx] < 0.1 or keypoints[rs_idx, conf_idx] < 0.1):
        return NormalizationResult(
            keypoints=normalized,
            center=(0.0, 0.0),
            scale=1.0,
            rotation=0.0,
            success=False,
            message="어깨 키포인트 누락",
        )

    center_x = (keypoints[ls_idx, 0] + keypoints[rs_idx, 0]) / 2
    center_y = (keypoints[ls_idx, 1] + keypoints[rs_idx, 1]) / 2

    normalized[:, 0] -= center_x
    normalized[:, 1] -= center_y

    scale = _calculate_scale(keypoints, config)
    if scale > 0:
        target = config.target_scale if config else 1.0
        normalized[:, :2] *= target / scale

    return NormalizationResult(
        keypoints=normalized,
        center=(float(center_x), float(center_y)),
        scale=float(scale),
        rotation=0.0,
        success=True,
    )


def _normalize_to_bounding_box(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """바운딩 박스 기준 정규화."""
    normalized = keypoints.copy()
    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    # 유효한 키포인트만 사용
    valid_mask = keypoints[:, conf_idx] > 0.1
    if not np.any(valid_mask):
        return NormalizationResult(
            keypoints=normalized,
            center=(0.0, 0.0),
            scale=1.0,
            rotation=0.0,
            success=False,
            message="유효한 키포인트 없음",
        )

    valid_kp = keypoints[valid_mask]

    min_x, min_y = np.min(valid_kp[:, 0]), np.min(valid_kp[:, 1])
    max_x, max_y = np.max(valid_kp[:, 0]), np.max(valid_kp[:, 1])

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    normalized[:, 0] -= center_x
    normalized[:, 1] -= center_y

    width = max_x - min_x
    height = max_y - min_y
    scale = max(width, height)

    if scale > 0.01:
        target = config.target_scale if config else 1.0
        normalized[:, :2] *= target / scale

    return NormalizationResult(
        keypoints=normalized,
        center=(float(center_x), float(center_y)),
        scale=float(scale),
        rotation=0.0,
        success=True,
    )


def _calculate_scale(
    keypoints: NDArray[np.float32],
    config: NormalizationConfig | None = None,
) -> float:
    """스케일 기준값 계산."""
    if config is None:
        config = NormalizationConfig()

    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    if config.scale_reference == ScaleReference.TORSO_HEIGHT:
        ls_idx = UnifiedKeypoint.LEFT_SHOULDER.value
        rs_idx = UnifiedKeypoint.RIGHT_SHOULDER.value
        lh_idx = UnifiedKeypoint.LEFT_HIP.value
        rh_idx = UnifiedKeypoint.RIGHT_HIP.value

        if all(idx < len(keypoints) and keypoints[idx, conf_idx] > 0.1
               for idx in [ls_idx, rs_idx, lh_idx, rh_idx]):
            shoulder_y = (keypoints[ls_idx, 1] + keypoints[rs_idx, 1]) / 2
            hip_y = (keypoints[lh_idx, 1] + keypoints[rh_idx, 1]) / 2
            return abs(hip_y - shoulder_y)

    elif config.scale_reference == ScaleReference.SHOULDER_WIDTH:
        ls_idx = UnifiedKeypoint.LEFT_SHOULDER.value
        rs_idx = UnifiedKeypoint.RIGHT_SHOULDER.value

        if all(idx < len(keypoints) and keypoints[idx, conf_idx] > 0.1
               for idx in [ls_idx, rs_idx]):
            return abs(keypoints[ls_idx, 0] - keypoints[rs_idx, 0])

    elif config.scale_reference == ScaleReference.HIP_WIDTH:
        lh_idx = UnifiedKeypoint.LEFT_HIP.value
        rh_idx = UnifiedKeypoint.RIGHT_HIP.value

        if all(idx < len(keypoints) and keypoints[idx, conf_idx] > 0.1
               for idx in [lh_idx, rh_idx]):
            return abs(keypoints[lh_idx, 0] - keypoints[rh_idx, 0])

    elif config.scale_reference == ScaleReference.FIXED:
        return 1.0

    return 1.0


def normalize_scale(
    keypoints: NDArray[np.float32],
    target_scale: float = 1.0,
    reference: ScaleReference = ScaleReference.TORSO_HEIGHT,
) -> NDArray[np.float32]:
    """스케일만 정규화."""
    config = NormalizationConfig(
        method=NormalizationMethod.HIP_CENTER,
        scale_reference=reference,
        target_scale=target_scale,
        center_on_hip=False,
    )
    scale = _calculate_scale(keypoints, config)

    if scale > 0.01:
        normalized = keypoints.copy()
        normalized[:, :2] *= target_scale / scale
        return normalized

    return keypoints.copy()


def rotate_pose(
    keypoints: NDArray[np.float32],
    angle_rad: float,
    center: tuple[float, float] | None = None,
) -> NDArray[np.float32]:
    """
    포즈 회전.

    Args:
        keypoints: 키포인트 배열
        angle_rad: 회전 각도 (라디안)
        center: 회전 중심 (None이면 원점)

    Returns:
        회전된 키포인트
    """
    rotated = keypoints.copy()

    if center is None:
        cx, cy = 0.0, 0.0
    else:
        cx, cy = center

    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    for i in range(len(keypoints)):
        x = keypoints[i, 0] - cx
        y = keypoints[i, 1] - cy

        rotated[i, 0] = x * cos_a - y * sin_a + cx
        rotated[i, 1] = x * sin_a + y * cos_a + cy

    return rotated


def mirror_pose(
    keypoints: NDArray[np.float32],
    axis: str = "vertical",
    center_x: float = 0.5,
) -> NDArray[np.float32]:
    """
    포즈 미러링 (좌우 반전).

    Args:
        keypoints: 키포인트 배열
        axis: "vertical" (좌우), "horizontal" (상하)
        center_x: 미러링 축 x 좌표

    Returns:
        미러링된 키포인트
    """
    mirrored = keypoints.copy()

    if axis == "vertical":
        # x 좌표 반전
        mirrored[:, 0] = 2 * center_x - keypoints[:, 0]

        # 좌우 키포인트 교환
        for left_kp, right_kp in UNIFIED_SYMMETRIC_PAIRS.items():
            left_idx = left_kp.value
            right_idx = right_kp.value

            if left_idx < len(keypoints) and right_idx < len(keypoints):
                # 이미 대칭 쌍이므로 한번만 교환
                if left_idx < right_idx:
                    temp = mirrored[left_idx].copy()
                    mirrored[left_idx] = mirrored[right_idx]
                    mirrored[right_idx] = temp

    elif axis == "horizontal":
        center_y = 0.5
        mirrored[:, 1] = 2 * center_y - keypoints[:, 1]

    return mirrored


def denormalize_pose(
    normalized: NDArray[np.float32],
    result: NormalizationResult,
) -> NDArray[np.float32]:
    """
    정규화 역변환 (원본 좌표 복원).

    Args:
        normalized: 정규화된 키포인트
        result: 정규화 결과 (center, scale, rotation 포함)

    Returns:
        원본 좌표의 키포인트
    """
    denormalized = normalized.copy()

    # 회전 역변환
    if result.rotation != 0:
        denormalized = rotate_pose(denormalized, -result.rotation)

    # 스케일 역변환
    if result.scale > 0:
        denormalized[:, :2] *= result.scale
        if denormalized.shape[1] > 3:
            denormalized[:, 2] *= result.scale

    # 중심 이동 역변환
    denormalized[:, 0] += result.center[0]
    denormalized[:, 1] += result.center[1]

    return denormalized


# ============================================================
# 신뢰도 필터링 함수
# ============================================================
def filter_low_confidence(
    keypoints: NDArray[np.float32],
    threshold: float = DEFAULT_MIN_CONFIDENCE,
    thresholds: ConfidenceThresholds | None = None,
) -> FilterResult:
    """
    신뢰도 기반 필터링.

    낮은 신뢰도 키포인트를 마스킹합니다.

    Args:
        keypoints: 키포인트 배열 (N, 3) 또는 (N, 4)
        threshold: 기본 신뢰도 임계값
        thresholds: 세부 임계값 (키포인트별)

    Returns:
        필터링 결과
    """
    filtered = keypoints.copy()
    conf_idx = 2 if keypoints.shape[1] == 3 else 3
    num_kp = len(keypoints)

    valid_mask = np.zeros(num_kp, dtype=np.bool_)

    for i in range(num_kp):
        confidence = keypoints[i, conf_idx]

        # 키포인트별 임계값 결정
        if thresholds is not None:
            kp = UnifiedKeypoint(i) if i < len(UnifiedKeypoint) else None
            if kp in CRITICAL_KEYPOINTS:
                min_conf = thresholds.critical
            elif kp in OPTIONAL_KEYPOINTS:
                min_conf = thresholds.optional
            else:
                min_conf = thresholds.normal
        else:
            min_conf = threshold

        valid_mask[i] = confidence >= min_conf

    # 필터링된 키포인트의 신뢰도를 0으로 설정
    filtered[~valid_mask, conf_idx] = 0.0

    valid_count = int(np.sum(valid_mask))
    avg_conf = float(np.mean(keypoints[:, conf_idx]))

    # 포즈 유효성 판단
    validity_threshold = thresholds.pose_validity if thresholds else DEFAULT_MIN_CONFIDENCE
    is_valid = avg_conf >= validity_threshold and valid_count >= MIN_VALID_KEYPOINTS_FOR_POSE

    return FilterResult(
        keypoints=filtered,
        valid_mask=valid_mask,
        average_confidence=avg_conf,
        valid_count=valid_count,
        total_count=num_kp,
        is_valid=is_valid,
    )


def get_valid_keypoints(
    keypoints: NDArray[np.float32],
    threshold: float = DEFAULT_MIN_CONFIDENCE,
) -> list[tuple[int, KeypointData]]:
    """
    유효한 키포인트 목록 반환.

    Args:
        keypoints: 키포인트 배열
        threshold: 신뢰도 임계값

    Returns:
        (인덱스, KeypointData) 튜플 리스트
    """
    valid_list = []
    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    for i, kp in enumerate(keypoints):
        if kp[conf_idx] >= threshold:
            z = kp[2] if keypoints.shape[1] > 3 else 0.0
            conf = kp[conf_idx]
            valid_list.append((i, KeypointData(
                x=float(kp[0]),
                y=float(kp[1]),
                z=float(z),
                confidence=float(conf),
            )))

    return valid_list


def calculate_average_confidence(
    keypoints: NDArray[np.float32],
    keypoint_indices: list[int] | None = None,
) -> float:
    """
    평균 신뢰도 계산.

    Args:
        keypoints: 키포인트 배열
        keypoint_indices: 특정 인덱스만 계산 (None이면 전체)

    Returns:
        평균 신뢰도
    """
    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    if keypoint_indices is not None:
        valid_indices = [i for i in keypoint_indices if i < len(keypoints)]
        if not valid_indices:
            return 0.0
        return float(np.mean(keypoints[valid_indices, conf_idx]))

    return float(np.mean(keypoints[:, conf_idx]))


def interpolate_missing(
    keypoints: NDArray[np.float32],
    threshold: float = 0.1,
) -> NDArray[np.float32]:
    """
    누락된 키포인트 보간.

    스켈레톤 연결을 기반으로 누락된 키포인트를 추정합니다.

    Args:
        keypoints: 키포인트 배열
        threshold: 유효 판단 임계값

    Returns:
        보간된 키포인트
    """
    interpolated = keypoints.copy()
    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    # NECK 보간 (어깨 중심)
    neck_idx = UnifiedKeypoint.NECK.value
    ls_idx = UnifiedKeypoint.LEFT_SHOULDER.value
    rs_idx = UnifiedKeypoint.RIGHT_SHOULDER.value

    if (neck_idx < len(keypoints) and
            keypoints[neck_idx, conf_idx] < threshold):
        if (ls_idx < len(keypoints) and rs_idx < len(keypoints) and
                keypoints[ls_idx, conf_idx] >= threshold and
                keypoints[rs_idx, conf_idx] >= threshold):
            interpolated[neck_idx] = (keypoints[ls_idx] + keypoints[rs_idx]) / 2
            interpolated[neck_idx, conf_idx] = min(
                keypoints[ls_idx, conf_idx],
                keypoints[rs_idx, conf_idx]
            ) * 0.9  # 보간 신뢰도 약간 감소

    # PELVIS 보간 (엉덩이 중심)
    pelvis_idx = UnifiedKeypoint.PELVIS.value
    lh_idx = UnifiedKeypoint.LEFT_HIP.value
    rh_idx = UnifiedKeypoint.RIGHT_HIP.value

    if (pelvis_idx < len(keypoints) and
            keypoints[pelvis_idx, conf_idx] < threshold):
        if (lh_idx < len(keypoints) and rh_idx < len(keypoints) and
                keypoints[lh_idx, conf_idx] >= threshold and
                keypoints[rh_idx, conf_idx] >= threshold):
            interpolated[pelvis_idx] = (keypoints[lh_idx] + keypoints[rh_idx]) / 2
            interpolated[pelvis_idx, conf_idx] = min(
                keypoints[lh_idx, conf_idx],
                keypoints[rh_idx, conf_idx]
            ) * 0.9

    return interpolated


def is_pose_valid(
    keypoints: NDArray[np.float32],
    min_critical: int = 3,
    min_total: int = 8,
    min_avg_confidence: float = 0.4,
) -> bool:
    """
    포즈 전체 유효성 판단.

    Args:
        keypoints: 키포인트 배열
        min_critical: 최소 필수 키포인트 수
        min_total: 최소 전체 유효 키포인트 수
        min_avg_confidence: 최소 평균 신뢰도

    Returns:
        유효 여부
    """
    conf_idx = 2 if keypoints.shape[1] == 3 else 3

    # 전체 유효 키포인트 수
    valid_mask = keypoints[:, conf_idx] >= DEFAULT_VALID_CONFIDENCE
    valid_count = int(np.sum(valid_mask))

    if valid_count < min_total:
        return False

    # 필수 키포인트 확인
    critical_count = 0
    for kp in CRITICAL_KEYPOINTS:
        idx = kp.value
        if idx < len(keypoints) and keypoints[idx, conf_idx] >= DEFAULT_CRITICAL_CONFIDENCE:
            critical_count += 1

    if critical_count < min_critical:
        return False

    # 평균 신뢰도
    avg_conf = float(np.mean(keypoints[:, conf_idx]))
    if avg_conf < min_avg_confidence:
        return False

    return True


# ============================================================
# 시퀀스 처리 함수
# ============================================================
def smooth_sequence(
    sequence: list[NDArray[np.float32]],
    config: SmoothingConfig | None = None,
) -> list[NDArray[np.float32]]:
    """
    포즈 시퀀스 일괄 스무딩.

    Args:
        sequence: 키포인트 배열 리스트
        config: 스무딩 설정

    Returns:
        스무딩된 시퀀스
    """
    if not sequence:
        return []

    smoother = TemporalSmoother(config)
    smoothed_sequence = []

    for frame_kps in sequence:
        result = smoother.smooth(frame_kps)
        smoothed_sequence.append(result.keypoints)

    return smoothed_sequence


# ============================================================
# 통합 PoseProcessor 클래스
# ============================================================
class PoseProcessor:
    """
    포즈 처리기 (정규화 + 스무딩 + 필터링 통합).

    Example:
        >>> processor = PoseProcessor({"smoothing": {"mode": "KALMAN"}})
        >>> filtered = processor.filter(keypoints)
        >>> normalized = processor.normalize(filtered.keypoints)
        >>> smoothed = processor.smooth(normalized.keypoints, track_id="player_1")
    """

    def __init__(
        self,
        config: dict[str, object] | None = None,
    ) -> None:
        """
        포즈 처리기 초기화.

        Args:
            config: 포즈 처리 설정 딕셔너리 (DI)
        """
        # 기본 설정
        self._normalization_config = NormalizationConfig()
        self._smoothing_config = SmoothingConfig()
        self._confidence_thresholds = ConfidenceThresholds()

        # 스무더 인스턴스
        self._smoother = TemporalSmoother(self._smoothing_config)

        # 설정 적용
        if config is not None:
            self._apply_config(config)

    def _apply_config(self, config: dict[str, object]) -> None:
        """설정 딕셔너리에서 파라미터 적용."""
        try:
            # 정규화 설정
            if "normalization" in config:
                norm_cfg = config["normalization"]
                method_str = norm_cfg.get("method", "hip_center").upper()  # type: ignore[union-attr]
                self._normalization_config.method = NormalizationMethod[method_str]
                self._normalization_config.target_scale = norm_cfg.get("target_scale", 1.0)  # type: ignore[union-attr]

            # 스무딩 설정
            if "smoothing" in config:
                smooth_cfg = config["smoothing"]
                mode_str = smooth_cfg.get("mode", "kalman").upper()  # type: ignore[union-attr]
                self._smoothing_config.mode = SmoothingMode[mode_str]
                self._smoothing_config.ema_alpha = smooth_cfg.get("ema_alpha", 0.5)  # type: ignore[union-attr]
                self._smoothing_config.window_size = smooth_cfg.get("window_size", 5)  # type: ignore[union-attr]
                self._smoothing_config.process_noise = smooth_cfg.get("process_noise", 0.01)  # type: ignore[union-attr]
                self._smoothing_config.measurement_noise = smooth_cfg.get("measurement_noise", 0.1)  # type: ignore[union-attr]
                # One Euro Filter 파라미터
                if "one_euro" in smooth_cfg:  # type: ignore[operator]
                    oe_cfg = smooth_cfg["one_euro"]  # type: ignore[index]
                    self._smoothing_config.one_euro_min_cutoff = oe_cfg.get("min_cutoff", 1.7)
                    self._smoothing_config.one_euro_beta = oe_cfg.get("beta", 0.3)
                    self._smoothing_config.one_euro_d_cutoff = oe_cfg.get("d_cutoff", 1.0)

            # 신뢰도 설정
            if "confidence" in config:
                conf_cfg = config["confidence"]
                self._confidence_thresholds.critical = conf_cfg.get("critical", 0.5)  # type: ignore[union-attr]
                self._confidence_thresholds.normal = conf_cfg.get("normal", 0.3)  # type: ignore[union-attr]
                self._confidence_thresholds.optional = conf_cfg.get("optional", 0.2)  # type: ignore[union-attr]
                self._confidence_thresholds.pose_validity = conf_cfg.get("pose_validity", 0.4)  # type: ignore[union-attr]

            # 스무더 재생성
            self._smoother = TemporalSmoother(self._smoothing_config)

            logger.info("포즈 처리 설정 적용 완료")

        except Exception as e:
            logger.warning("포즈 처리 설정 적용 실패: %s", str(e))

    def filter(
        self,
        keypoints: NDArray[np.float32],
        threshold: float | None = None,
    ) -> FilterResult:
        """
        신뢰도 필터링.

        Args:
            keypoints: 키포인트 배열
            threshold: 임계값 (None이면 설정값 사용)

        Returns:
            필터링 결과
        """
        return filter_low_confidence(
            keypoints,
            threshold=threshold or self._confidence_thresholds.normal,
            thresholds=self._confidence_thresholds,
        )

    def normalize(
        self,
        keypoints: NDArray[np.float32],
        config: NormalizationConfig | None = None,
    ) -> NormalizationResult:
        """
        포즈 정규화.

        Args:
            keypoints: 키포인트 배열
            config: 정규화 설정 (None이면 기본 설정)

        Returns:
            정규화 결과
        """
        return normalize_pose(
            keypoints,
            config=config or self._normalization_config,
        )

    def smooth(
        self,
        keypoints: NDArray[np.float32],
        track_id: str = "default",
        timestamp: float | None = None,
    ) -> SmoothedPose:
        """
        시간적 스무딩.

        Args:
            keypoints: 키포인트 배열
            track_id: 트랙 ID
            timestamp: 타임스탬프

        Returns:
            스무딩된 포즈
        """
        return self._smoother.smooth(keypoints, track_id, timestamp)

    def process(
        self,
        keypoints: NDArray[np.float32],
        track_id: str = "default",
        normalize: bool = True,
        smooth: bool = True,
    ) -> tuple[NDArray[np.float32], dict[str, object]]:
        """
        전체 처리 파이프라인.

        Args:
            keypoints: 원본 키포인트
            track_id: 트랙 ID
            normalize: 정규화 적용 여부
            smooth: 스무딩 적용 여부

        Returns:
            (처리된 키포인트, 메타데이터 딕셔너리)
        """
        metadata: dict[str, object] = {}
        processed = keypoints.copy()

        # 1. 필터링
        filter_result = self.filter(processed)
        processed = filter_result.keypoints
        metadata["filter"] = {
            "valid_count": filter_result.valid_count,
            "average_confidence": filter_result.average_confidence,
            "is_valid": filter_result.is_valid,
        }

        if not filter_result.is_valid:
            metadata["error"] = "포즈 유효성 검증 실패"
            return processed, metadata

        # 2. 보간
        processed = interpolate_missing(processed)

        # 3. 정규화
        if normalize:
            norm_result = self.normalize(processed)
            if norm_result.success:
                processed = norm_result.keypoints
                metadata["normalization"] = {
                    "center": norm_result.center,
                    "scale": norm_result.scale,
                }
            else:
                metadata["normalization_error"] = norm_result.message

        # 4. 스무딩
        if smooth:
            smooth_result = self.smooth(processed, track_id)
            processed = smooth_result.keypoints
            metadata["smoothing"] = {
                "track_state": smooth_result.track_state.name,
                "frame_count": smooth_result.frame_count,
            }

        return processed, metadata

    def reset_track(self, track_id: str) -> None:
        """특정 트랙 초기화."""
        self._smoother.reset_track(track_id)

    def reset_all(self) -> None:
        """모든 트랙 초기화."""
        self._smoother.reset_all()


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # =========================================================================
    # 메인 클래스
    # =========================================================================
    "PoseProcessor",

    # =========================================================================
    # 정규화
    # =========================================================================
    "normalize_pose",
    "normalize_to_hip_center",
    "normalize_to_torso",
    "normalize_scale",
    "rotate_pose",
    "mirror_pose",
    "denormalize_pose",
    "NormalizationConfig",
    "NormalizationResult",
    "NormalizationMethod",
    "ScaleReference",

    # =========================================================================
    # 시간적 스무딩
    # =========================================================================
    "TemporalSmoother",
    "SmoothingConfig",
    "SmoothedPose",
    "SmoothingMode",
    "TrackState",
    "smooth_sequence",

    # =========================================================================
    # 신뢰도 필터링
    # =========================================================================
    "filter_low_confidence",
    "get_valid_keypoints",
    "calculate_average_confidence",
    "interpolate_missing",
    "is_pose_valid",
    "ConfidenceThresholds",
    "FilterResult",

    # =========================================================================
    # 상수
    # =========================================================================
    "CONFIG_KEY_POSE_PROCESSOR",
    "FILTERPY_AVAILABLE",
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_SMOOTHING_FACTOR",
    "DEFAULT_PROCESS_NOISE",
    "DEFAULT_MEASUREMENT_NOISE",
    "DEFAULT_TORSO_LENGTH",
    "MAX_HISTORY_FRAMES",
    "MIN_VALID_KEYPOINTS_FOR_POSE",
    "DEFAULT_VALID_CONFIDENCE",
    "DEFAULT_CRITICAL_CONFIDENCE",

    # =========================================================================
    # 중요 키포인트 집합
    # =========================================================================
    "CRITICAL_KEYPOINTS",
    "OPTIONAL_KEYPOINTS",
]

__version__ = "1.0.0"
