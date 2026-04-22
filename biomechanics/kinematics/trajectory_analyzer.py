# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: biomechanics/kinematics
파일: trajectory_analyzer.py
설명: 관절 궤적 분석 모듈
      - 시간 시퀀스에서 관절 이동 궤적 추적
      - 궤적 매끄러움 (smoothness) 정량화
      - 궤적 곡률 (curvature) 계산
      - 동작 범위 (ROM) 사용률 산출

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

참조:
    - Balasubramanian, S. et al. (2015). Analysis of movement smoothness metrics.
      Journal of NeuroEngineering and Rehabilitation.
    - SPARC (Spectral Arc Length) smoothness metric.
    - 궤적 곡률: κ = |v × a| / |v|³

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/constants/biomechanics_constants.py: JOINT_ROM_NORMAL

사용처:
    - biomechanics/kinematics/motion_pattern.py: 궤적 형상 기반 패턴 분류
    - motion_analysis/form_evaluation/: 슈팅 아크 평가, 드리블 리듬 분석
    - feedback_system/: 궤적 매끄러움 기반 피드백
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

import numpy as np
from numpy.typing import NDArray

from shared.constants.biomechanics_constants import JOINT_ROM_NORMAL
from shared.constants.pose_constants import JointType


# =============================================================================
# 상수
# =============================================================================

# 궤적 버퍼 최대 크기 (프레임 수)
_MAX_TRAJECTORY_LENGTH: Final[int] = 300

# 최소 궤적 길이 (분석 가능 최소)
_MIN_TRAJECTORY_LENGTH: Final[int] = 3

# 벡터 크기 최소 임계치
_MIN_NORM: Final[float] = 1e-8

# 궤적 매끄러움 상수
_SMOOTHNESS_JERK_WINDOW: Final[int] = 5  # 저크 계산 윈도우

# ROM 키포인트 매핑 (JointType → JOINT_ROM_NORMAL 키)
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
# 궤적 분석 결과 데이터클래스
# =============================================================================

@dataclass(frozen=True, slots=True)
class TrajectoryMetrics:
    """
    관절 궤적 분석 지표.

    Attributes:
        joint_type: 관절 유형
        total_distance_cm: 총 이동 거리 (cm)
        displacement_cm: 시작→끝 직선 변위 (cm)
        path_efficiency: 궤적 효율성 (displacement / distance, 0~1)
        smoothness: 궤적 매끄러움 (0~1, 높을수록 매끄러움)
        mean_curvature: 평균 곡률 (1/cm, 낮을수록 직선적)
        rom_utilization: ROM 사용률 (0~1, 해당 관절의 가동 범위 중 사용 비율)
        frame_count: 분석 프레임 수
    """

    joint_type: JointType
    total_distance_cm: float
    displacement_cm: float
    path_efficiency: float
    smoothness: float
    mean_curvature: float
    rom_utilization: float
    frame_count: int


# =============================================================================
# 궤적 계산 함수
# =============================================================================

def _calculate_path_distance(
    positions: NDArray[np.float64],
) -> float:
    """
    궤적 총 이동 거리 (cm).

    Args:
        positions: 위치 시퀀스 (N×3)

    Returns:
        총 이동 거리 (cm)
    """
    if positions.shape[0] < 2:
        return 0.0

    diffs = np.diff(positions, axis=0)
    distances = np.linalg.norm(diffs, axis=1)
    return float(np.sum(distances))


def _calculate_displacement(
    positions: NDArray[np.float64],
) -> float:
    """
    시작→끝 직선 변위 (cm).

    Args:
        positions: 위치 시퀀스 (N×3)

    Returns:
        직선 변위 (cm)
    """
    if positions.shape[0] < 2:
        return 0.0
    return float(np.linalg.norm(positions[-1] - positions[0]))


def _calculate_smoothness_ndjl(
    positions: NDArray[np.float64],
    dt: float,
) -> float:
    """
    정규화 저크 제곱 적분 기반 매끄러움 계산.

    Normalized Dimensionless Jerk Logarithm (NDJL):
    매끄러운 동작 = 저크(가속도 변화율)가 작음.

    계산:
        1. 속도 = diff(position) / dt
        2. 가속도 = diff(velocity) / dt
        3. 저크 = diff(acceleration) / dt
        4. NDJL = -ln(√(T³/D² · ∫jerk²dt))
        5. 0~1 정규화

    Args:
        positions: 위치 시퀀스 (N×3)
        dt: 시간 간격 (초)

    Returns:
        매끄러움 (0~1)

    참조:
        Balasubramanian et al. (2015) — 운동 매끄러움 지표
    """
    n = positions.shape[0]
    if n < 4 or dt < 1e-6:
        return 0.5  # 데이터 부족 시 중립값

    # 속도 → 가속도 → 저크
    velocity = np.diff(positions, axis=0) / dt
    acceleration = np.diff(velocity, axis=0) / dt
    jerk = np.diff(acceleration, axis=0) / dt

    # 저크 제곱 적분
    jerk_sq = np.sum(jerk ** 2, axis=1)
    jerk_integral = float(np.sum(jerk_sq)) * dt

    # 정규화 계수
    duration = (n - 1) * dt
    distance = _calculate_path_distance(positions)

    if distance < _MIN_NORM or duration < _MIN_NORM:
        return 0.5

    # NDJL = -ln(√(T³/D² · ∫jerk²dt))
    normalized = (duration ** 3 / distance ** 2) * jerk_integral

    if normalized <= 0:
        return 1.0

    ndjl = -math.log(math.sqrt(normalized))

    # 0~1 스케일링 (경험적 범위: NDJL ∈ [-10, 2])
    smoothness = max(0.0, min(1.0, (ndjl + 10.0) / 12.0))
    return smoothness


def _calculate_curvature(
    positions: NDArray[np.float64],
    dt: float,
) -> float:
    """
    궤적 평균 곡률 계산.

    κ = |v × a| / |v|³
    (3D 벡터 외적 기반 곡률)

    Args:
        positions: 위치 시퀀스 (N×3)
        dt: 시간 간격 (초)

    Returns:
        평균 곡률 (1/cm)
    """
    if positions.shape[0] < 3 or dt < 1e-6:
        return 0.0

    velocity = np.diff(positions, axis=0) / dt
    acceleration = np.diff(velocity, axis=0) / dt

    # velocity와 acceleration 길이 맞추기 (acceleration이 1개 적음)
    vel_trimmed = velocity[:-1]

    curvatures = []
    for i in range(vel_trimmed.shape[0]):
        v = vel_trimmed[i]
        a = acceleration[i]
        v_norm = np.linalg.norm(v)

        if v_norm < _MIN_NORM:
            continue

        # κ = |v × a| / |v|³
        cross = np.cross(v, a)
        cross_norm = np.linalg.norm(cross)
        kappa = cross_norm / (v_norm ** 3)
        curvatures.append(kappa)

    if not curvatures:
        return 0.0

    return float(np.mean(curvatures))


def _calculate_rom_utilization(
    angles: list[float],
    joint_type: JointType,
) -> float:
    """
    ROM 사용률 계산.

    동작 중 사용된 각도 범위 / 전체 ROM.

    Args:
        angles: 프레임별 관절 각도 시퀀스 (도)
        joint_type: 관절 유형

    Returns:
        ROM 사용률 (0~1)
    """
    if len(angles) < 2:
        return 0.0

    rom_key = _JOINT_ROM_KEYS.get(joint_type)
    if rom_key is None:
        return 0.0

    rom_range = JOINT_ROM_NORMAL.get(rom_key)
    if rom_range is None:
        return 0.0

    total_rom = rom_range[1] - rom_range[0]
    if total_rom <= 0:
        return 0.0

    used_range = max(angles) - min(angles)
    return min(1.0, used_range / total_rom)


# =============================================================================
# 공개 함수
# =============================================================================

def analyze_trajectory(
    positions: NDArray[np.float64],
    dt: float,
    joint_type: JointType,
    angles: list[float] | None = None,
) -> TrajectoryMetrics | None:
    """
    관절 궤적 종합 분석.

    Args:
        positions: 관절 위치 시퀀스 (N×3, cm)
        dt: 프레임 간 시간 간격 (초)
        joint_type: 관절 유형
        angles: 프레임별 관절 각도 (도, ROM 사용률 계산용)

    Returns:
        TrajectoryMetrics 객체 (데이터 부족 시 None)
    """
    if positions.shape[0] < _MIN_TRAJECTORY_LENGTH:
        return None

    total_dist = _calculate_path_distance(positions)
    displacement = _calculate_displacement(positions)

    # 경로 효율성
    path_eff = 0.0
    if total_dist > _MIN_NORM:
        path_eff = min(1.0, displacement / total_dist)

    smoothness = _calculate_smoothness_ndjl(positions, dt)
    curvature = _calculate_curvature(positions, dt)

    # ROM 사용률
    rom_util = 0.0
    if angles is not None and len(angles) >= 2:
        rom_util = _calculate_rom_utilization(angles, joint_type)

    return TrajectoryMetrics(
        joint_type=joint_type,
        total_distance_cm=total_dist,
        displacement_cm=displacement,
        path_efficiency=path_eff,
        smoothness=smoothness,
        mean_curvature=curvature,
        rom_utilization=rom_util,
        frame_count=positions.shape[0],
    )


# =============================================================================
# 궤적 버퍼 (실시간 스트리밍 분석용)
# =============================================================================

class TrajectoryBuffer:
    """
    관절별 궤적 버퍼 (프레임 단위 축적, 주기적 분석).

    실시간 분석에서 프레임마다 키포인트를 추가하고,
    일정 프레임이 축적되면 궤적 분석을 수행한다.

    스레드 안전: RLock 기반.
    메모리 제한: deque(maxlen=_MAX_TRAJECTORY_LENGTH).

    사용 예시::

        >>> buffer = TrajectoryBuffer(dt=1/30)
        >>> buffer.add_frame(keypoints_3d, frame_angles)
        >>> metrics = buffer.analyze(JointType.RIGHT_WRIST)
    """

    __slots__ = ("_dt", "_positions", "_angles", "_lock")

    def __init__(self, dt: float) -> None:
        """
        Args:
            dt: 프레임 간 시간 간격 (초)
        """
        self._dt: float = dt
        self._positions: dict[JointType, deque[NDArray[np.float64]]] = {}
        self._angles: dict[JointType, deque[float]] = {}
        self._lock: RLock = RLock()

    # JointType → Unified 25kp 인덱스
    _JOINT_25KP: Final[dict[JointType, int]] = {
        JointType.NOSE: 0,
        JointType.LEFT_SHOULDER: 5,
        JointType.RIGHT_SHOULDER: 2,
        JointType.LEFT_ELBOW: 6,
        JointType.RIGHT_ELBOW: 3,
        JointType.LEFT_WRIST: 7,
        JointType.RIGHT_WRIST: 4,
        JointType.LEFT_HIP: 11,
        JointType.RIGHT_HIP: 8,
        JointType.LEFT_KNEE: 12,
        JointType.RIGHT_KNEE: 9,
        JointType.LEFT_ANKLE: 13,
        JointType.RIGHT_ANKLE: 10,
    }

    def add_frame(
        self,
        keypoints_3d: NDArray[np.float64],
        frame_angles: dict[JointType, float] | None = None,
    ) -> None:
        """
        프레임 키포인트 추가.

        Args:
            keypoints_3d: 3D 키포인트 (25×3 또는 25×4)
            frame_angles: 관절별 각도 (도, 선택)
        """
        with self._lock:
            for joint_type, kp_idx in self._JOINT_25KP.items():
                if kp_idx >= keypoints_3d.shape[0]:
                    continue

                # 신뢰도 검증
                conf = 1.0
                if keypoints_3d.shape[1] >= 4:
                    conf = float(keypoints_3d[kp_idx, 3])
                if conf < 0.3:
                    continue

                pos = keypoints_3d[kp_idx, :3].copy()

                if joint_type not in self._positions:
                    self._positions[joint_type] = deque(
                        maxlen=_MAX_TRAJECTORY_LENGTH
                    )
                self._positions[joint_type].append(pos)

                # 각도 저장
                if frame_angles is not None and joint_type in frame_angles:
                    if joint_type not in self._angles:
                        self._angles[joint_type] = deque(
                            maxlen=_MAX_TRAJECTORY_LENGTH
                        )
                    self._angles[joint_type].append(frame_angles[joint_type])

    def analyze(
        self,
        joint_type: JointType,
    ) -> TrajectoryMetrics | None:
        """
        특정 관절의 궤적 분석 수행.

        Args:
            joint_type: 관절 유형

        Returns:
            TrajectoryMetrics 또는 None (데이터 부족)
        """
        with self._lock:
            pos_deque = self._positions.get(joint_type)
            if pos_deque is None or len(pos_deque) < _MIN_TRAJECTORY_LENGTH:
                return None

            positions = np.array(list(pos_deque), dtype=np.float64)
            angles = None

            angle_deque = self._angles.get(joint_type)
            if angle_deque is not None and len(angle_deque) >= 2:
                angles = list(angle_deque)

        return analyze_trajectory(positions, self._dt, joint_type, angles)

    def analyze_all(self) -> dict[JointType, TrajectoryMetrics]:
        """모든 관절 궤적 분석."""
        results: dict[JointType, TrajectoryMetrics] = {}
        with self._lock:
            joint_types = list(self._positions.keys())

        for jt in joint_types:
            metrics = self.analyze(jt)
            if metrics is not None:
                results[jt] = metrics

        return results

    def reset(self) -> None:
        """전체 버퍼 초기화."""
        with self._lock:
            self._positions.clear()
            self._angles.clear()

    @property
    def frame_count(self) -> int:
        """현재 버퍼에 축적된 최대 프레임 수."""
        with self._lock:
            if not self._positions:
                return 0
            return max(len(d) for d in self._positions.values())


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터클래스
    "TrajectoryMetrics",
    # 분석 함수
    "analyze_trajectory",
    # 실시간 버퍼
    "TrajectoryBuffer",
]

__version__ = "1.0.0"
