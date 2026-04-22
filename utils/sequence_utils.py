# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: sequence_utils.py
설명: 시퀀스/시계열 분석 유틸리티
      - DTW (Dynamic Time Warping) 시퀀스 정렬/비교
      - 프레셰 거리 메트릭
      - 위상 분할 및 전환 검출
      - 슬라이딩 윈도우 연산
      - 피크/밸리 검출
      - 주기성 분석 및 자기상관
      - 템플릿 매칭
      - 배치 시퀀스 처리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - DTW 기반 시퀀스 비교 (다차원 지원, O(NM) 동적 프로그래밍)
    - 이산 프레셰 거리 (커브 유사도 측정)
    - 위상 분할 (속도/곡률/영교차 기반)
    - 슬라이딩 윈도우 통계량 추출
    - 피크/밸리 검출 (프로미넌스 기반)
    - 자기상관/교차상관 분석
    - 주기성 검출
    - DTW 기반 시퀀스 정렬/워핑
    - 정규화 교차상관 템플릿 매칭
    - 배치 처리 지원

사용 예시:
    >>> from utils.sequence_utils import (
    ...     dtw_distance,
    ...     find_peaks,
    ...     detect_phase_transitions,
    ... )
    >>> import numpy as np
    >>> a = np.sin(np.linspace(0, 2 * np.pi, 50))
    >>> b = np.sin(np.linspace(0, 2 * np.pi, 60))
    >>> result = dtw_distance(a, b)
    >>> result.distance >= 0
    True
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import math
from dataclasses import dataclass
from enum import Enum, unique

# === 서드파티 라이브러리 ===
import numpy as np
from numpy.typing import NDArray

# === 로거 설정 ===
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 상수 정의
# =============================================================================

# 부동소수점 비교용 임계값
_EPSILON: float = 1e-10

# DTW 최대 시퀀스 길이 (메모리 보호, O(N*M) 비용 행렬)
MAX_DTW_SEQUENCE_LENGTH: int = 5000

# 위상 분할 기본값
DEFAULT_MIN_PHASE_LENGTH: int = 5

# 피크 검출 기본값
DEFAULT_PEAK_MIN_DISTANCE: int = 3
DEFAULT_PEAK_MIN_PROMINENCE: float = 0.1

# 슬라이딩 윈도우 기본값
DEFAULT_WINDOW_SIZE: int = 15
DEFAULT_WINDOW_STRIDE: int = 1

# 배치 처리 최대 크기
_MAX_BATCH_SIZE: int = 1000


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class PaddingMode(Enum):
    """시퀀스 패딩 모드."""
    ZERO = "zero"           # 0으로 패딩
    EDGE = "edge"           # 경계값 반복
    REFLECT = "reflect"     # 반사 패딩
    WRAP = "wrap"           # 순환 패딩


@unique
class DistanceMetric(Enum):
    """시퀀스 비교 거리 메트릭."""
    EUCLIDEAN = "euclidean"       # 유클리드 거리 (L2)
    MANHATTAN = "manhattan"       # 맨해튼 거리 (L1)
    COSINE = "cosine"             # 코사인 거리 (1 - 유사도)
    CHEBYSHEV = "chebyshev"       # 체비셰프 거리 (L∞)


@unique
class SegmentationMethod(Enum):
    """위상 분할 방법."""
    VELOCITY_THRESHOLD = "velocity_threshold"          # 속도 임계값 기반
    ACCELERATION_THRESHOLD = "acceleration_threshold"   # 가속도 임계값 기반
    CURVATURE = "curvature"                             # 곡률 기반
    ZERO_CROSSING = "zero_crossing"                     # 영교차 기반


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class DTWResult:
    """
    DTW (Dynamic Time Warping) 결과.

    Attributes:
        distance: DTW 누적 거리
        normalized_distance: 경로 길이로 정규화된 거리
        warping_path: 최적 워핑 경로 [(i, j), ...]
        cost_matrix: 누적 비용 행렬 (None이면 메모리 절약 모드)
    """
    distance: float
    normalized_distance: float
    warping_path: list[tuple[int, int]]
    cost_matrix: NDArray | None = None

    def __repr__(self) -> str:
        return (
            f"DTWResult(distance={self.distance:.6f}, "
            f"normalized={self.normalized_distance:.6f}, "
            f"path_length={len(self.warping_path)})"
        )


@dataclass(slots=True)
class PhaseSegment:
    """
    위상 분할 결과 세그먼트.

    Attributes:
        start_idx: 시작 프레임 인덱스
        end_idx: 종료 프레임 인덱스 (포함)
        label: 위상 라벨 (예: "ascending", "descending", "stationary")
        confidence: 분할 신뢰도 [0, 1]
        duration_frames: 프레임 수
        mean_value: 구간 평균값
    """
    start_idx: int
    end_idx: int
    label: str
    confidence: float
    duration_frames: int
    mean_value: float = 0.0

    def __repr__(self) -> str:
        return (
            f"PhaseSegment(label='{self.label}', "
            f"frames=[{self.start_idx}:{self.end_idx}], "
            f"duration={self.duration_frames}, "
            f"confidence={self.confidence:.3f})"
        )


@dataclass(slots=True)
class PeakInfo:
    """
    피크/밸리 검출 결과.

    Attributes:
        index: 피크 위치 인덱스
        value: 피크 값
        prominence: 프로미넌스 (주변 대비 돌출도)
        left_base: 왼쪽 베이스 인덱스
        right_base: 오른쪽 베이스 인덱스
    """
    index: int
    value: float
    prominence: float
    left_base: int
    right_base: int

    def __repr__(self) -> str:
        return (
            f"PeakInfo(index={self.index}, "
            f"value={self.value:.4f}, "
            f"prominence={self.prominence:.4f})"
        )


@dataclass(slots=True)
class SequenceAlignment:
    """
    시퀀스 정렬 결과.

    Attributes:
        aligned_a: 정렬된 시퀀스 A
        aligned_b: 정렬된 시퀀스 B
        warping_path: DTW 워핑 경로
        distance: 정렬 거리
        compression_ratio: 압축비 (정렬 후 길이 / 원본 평균 길이)
    """
    aligned_a: NDArray
    aligned_b: NDArray
    warping_path: list[tuple[int, int]]
    distance: float
    compression_ratio: float

    def __repr__(self) -> str:
        return (
            f"SequenceAlignment(distance={self.distance:.6f}, "
            f"path_length={len(self.warping_path)}, "
            f"compression_ratio={self.compression_ratio:.3f})"
        )


@dataclass(slots=True)
class PeriodicityResult:
    """
    주기성 분석 결과.

    Attributes:
        dominant_period: 지배적 주기 (프레임 단위, 0이면 주기 없음)
        strength: 주기 강도 [0, 1]
        autocorrelation_values: 자기상관 값 배열
        secondary_periods: 보조 주기 목록 [(period, strength), ...]
    """
    dominant_period: int
    strength: float
    autocorrelation_values: NDArray
    secondary_periods: list[tuple[int, float]]

    def __repr__(self) -> str:
        return (
            f"PeriodicityResult(period={self.dominant_period}, "
            f"strength={self.strength:.4f}, "
            f"secondary_count={len(self.secondary_periods)})"
        )


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _validate_sequence(sequence: NDArray, name: str = "sequence") -> NDArray:
    """시퀀스 입력 검증 및 float64 변환."""
    if not isinstance(sequence, np.ndarray):
        raise TypeError(
            f"{name}은 numpy.ndarray여야 합니다. "
            f"받은 타입: {type(sequence).__name__}"
        )
    if sequence.ndim == 0:
        raise ValueError(f"{name}은 최소 1차원이어야 합니다.")
    if sequence.size == 0:
        raise ValueError(f"{name}이 비어있습니다.")
    return sequence.astype(np.float64, copy=False)


def _point_distance(a: NDArray, b: NDArray, metric: DistanceMetric) -> float:
    """두 포인트 간 거리 계산 (단일 프레임)."""
    diff = a - b
    if metric == DistanceMetric.EUCLIDEAN:
        return float(np.sqrt(np.sum(diff ** 2)))
    elif metric == DistanceMetric.MANHATTAN:
        return float(np.sum(np.abs(diff)))
    elif metric == DistanceMetric.COSINE:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < _EPSILON or norm_b < _EPSILON:
            return 1.0
        return float(1.0 - np.dot(a.ravel(), b.ravel()) / (norm_a * norm_b))
    elif metric == DistanceMetric.CHEBYSHEV:
        return float(np.max(np.abs(diff)))
    # 기본: 유클리드
    return float(np.sqrt(np.sum(diff ** 2)))


def _ensure_2d(sequence: NDArray) -> NDArray:
    """1D 시퀀스를 (N, 1) 형태로 변환."""
    if sequence.ndim == 1:
        return sequence.reshape(-1, 1)
    return sequence


def _apply_padding(
    sequence: NDArray,
    pad_before: int,
    pad_after: int,
    mode: PaddingMode,
) -> NDArray:
    """시퀀스 양쪽에 패딩 적용."""
    if pad_before == 0 and pad_after == 0:
        return sequence

    if mode == PaddingMode.ZERO:
        np_mode = "constant"
        kwargs: dict = {"constant_values": 0}
    elif mode == PaddingMode.EDGE:
        np_mode = "edge"
        kwargs = {}
    elif mode == PaddingMode.REFLECT:
        # reflect 모드는 시퀀스 길이 - 1보다 작은 패딩만 가능
        max_reflect = sequence.shape[0] - 1
        if pad_before > max_reflect or pad_after > max_reflect:
            np_mode = "edge"
            kwargs = {}
            logger.warning(
                "reflect 패딩이 시퀀스 길이를 초과하여 edge 모드로 폴백합니다."
            )
        else:
            np_mode = "reflect"
            kwargs = {}
    elif mode == PaddingMode.WRAP:
        np_mode = "wrap"
        kwargs = {}
    else:
        np_mode = "constant"
        kwargs = {"constant_values": 0}

    if sequence.ndim == 1:
        return np.pad(sequence, (pad_before, pad_after), mode=np_mode, **kwargs)
    else:
        pad_widths = [(pad_before, pad_after)] + [(0, 0)] * (sequence.ndim - 1)
        return np.pad(sequence, pad_widths, mode=np_mode, **kwargs)


def _compute_phase_confidence(values: NDArray) -> float:
    """위상 세그먼트의 신뢰도 계산 (변화율 일관성 기반)."""
    if len(values) < 2:
        return 0.5
    diffs = np.diff(values)
    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs))
    # 일관성: 변화율의 표준편차가 작을수록 높음
    consistency = 1.0 - min(1.0, std_diff / (abs(mean_diff) + _EPSILON))
    return max(0.0, consistency)


def _merge_short_segments(
    segments: list[PhaseSegment],
    min_length: int,
    sequence: NDArray,
) -> list[PhaseSegment]:
    """최소 길이 미만의 세그먼트를 인접 세그먼트에 병합."""
    if len(segments) <= 1:
        return segments

    merged: list[PhaseSegment] = [segments[0]]

    for seg in segments[1:]:
        if seg.duration_frames < min_length and merged:
            # 이전 세그먼트에 병합
            prev = merged[-1]
            new_end = seg.end_idx
            new_duration = new_end - prev.start_idx + 1
            new_mean = float(np.mean(sequence[prev.start_idx:new_end + 1]))
            new_conf = _compute_phase_confidence(
                sequence[prev.start_idx:new_end + 1]
            )
            merged[-1] = PhaseSegment(
                start_idx=prev.start_idx,
                end_idx=new_end,
                label=prev.label,
                confidence=new_conf,
                duration_frames=new_duration,
                mean_value=new_mean,
            )
        else:
            merged.append(seg)

    return merged


# =============================================================================
# 시퀀스 정규화 (Sequence Normalization)
# =============================================================================

def z_normalize_sequence(sequence: NDArray) -> NDArray:
    """
    시퀀스 Z-정규화 (평균 0, 표준편차 1).

    다차원 시퀀스의 경우 각 특성(열) 별로 독립 정규화합니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스

    Returns:
        Z-정규화된 시퀀스 (동일 형태)

    Raises:
        TypeError: 입력이 ndarray가 아닌 경우
        ValueError: 빈 시퀀스인 경우
    """
    seq = _validate_sequence(sequence, "sequence")

    if seq.ndim == 1:
        std = np.std(seq)
        if std < _EPSILON:
            logger.debug("시퀀스 표준편차가 0에 가까워 0 벡터를 반환합니다.")
            return np.zeros_like(seq)
        return (seq - np.mean(seq)) / std
    else:
        # 각 특성별 정규화
        mean = np.mean(seq, axis=0, keepdims=True)
        std = np.std(seq, axis=0, keepdims=True)
        mask = std < _EPSILON
        std_safe = np.where(mask, 1.0, std)
        result = (seq - mean) / std_safe
        # 표준편차 0인 열은 0으로
        result[:, mask.ravel()] = 0.0
        return result


def min_max_normalize_sequence(
    sequence: NDArray,
    feature_range: tuple[float, float] = (0.0, 1.0),
) -> NDArray:
    """
    시퀀스 Min-Max 정규화.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        feature_range: 출력 범위 (min, max)

    Returns:
        정규화된 시퀀스

    Raises:
        TypeError: 입력이 ndarray가 아닌 경우
        ValueError: feature_range[0] >= feature_range[1]인 경우
    """
    seq = _validate_sequence(sequence, "sequence")

    r_min, r_max = feature_range
    if r_min >= r_max:
        raise ValueError(
            f"feature_range의 min({r_min})이 max({r_max}) 이상입니다."
        )

    if seq.ndim == 1:
        s_min = np.min(seq)
        s_max = np.max(seq)
        if s_max - s_min < _EPSILON:
            return np.full_like(seq, (r_min + r_max) / 2.0)
        return (seq - s_min) / (s_max - s_min) * (r_max - r_min) + r_min
    else:
        s_min = np.min(seq, axis=0, keepdims=True)
        s_max = np.max(seq, axis=0, keepdims=True)
        denom = s_max - s_min
        mask = denom < _EPSILON
        denom_safe = np.where(mask, 1.0, denom)
        result = (seq - s_min) / denom_safe * (r_max - r_min) + r_min
        result[:, mask.ravel()] = (r_min + r_max) / 2.0
        return result


def resample_sequence(
    sequence: NDArray,
    target_length: int,
    method: str = "linear",
) -> NDArray:
    """
    시퀀스를 목표 길이로 리샘플링.

    선형/최근접 보간을 사용하여 시퀀스의 시간 해상도를 변경합니다.
    DTW 비교 전 길이 맞춤이나, 다른 FPS 시퀀스 통합에 사용됩니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        target_length: 목표 프레임 수 (양수)
        method: 보간 방법 ("linear", "nearest")

    Returns:
        리샘플링된 시퀀스

    Raises:
        ValueError: target_length <= 0인 경우
    """
    seq = _validate_sequence(sequence, "sequence")

    if target_length <= 0:
        raise ValueError(f"target_length는 양수여야 합니다: {target_length}")

    n = seq.shape[0]
    if n == target_length:
        return seq.copy()

    if target_length == 1:
        if seq.ndim == 1:
            return np.array([seq[n // 2]], dtype=seq.dtype)
        return seq[n // 2:n // 2 + 1].copy()

    # 원본/목표 시간축
    x_original = np.linspace(0.0, 1.0, n)
    x_target = np.linspace(0.0, 1.0, target_length)

    if seq.ndim == 1:
        if method == "nearest":
            indices = np.round(x_target * (n - 1)).astype(int)
            return seq[indices].copy()
        # 선형 보간 (기본)
        return np.interp(x_target, x_original, seq)
    else:
        d = seq.shape[1]
        result = np.empty((target_length, d), dtype=np.float64)
        if method == "nearest":
            indices = np.round(x_target * (n - 1)).astype(int)
            return seq[indices].copy()
        for col in range(d):
            result[:, col] = np.interp(x_target, x_original, seq[:, col])
        return result


def pad_or_truncate(
    sequence: NDArray,
    target_length: int,
    mode: PaddingMode = PaddingMode.ZERO,
) -> NDArray:
    """
    시퀀스를 목표 길이로 패딩 또는 잘라냄.

    시퀀스가 길면 중앙 기준으로 잘라내고,
    짧으면 뒤쪽에 패딩을 추가합니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        target_length: 목표 길이 (양수)
        mode: 패딩 모드 (시퀀스가 짧은 경우)

    Returns:
        길이가 조정된 시퀀스
    """
    seq = _validate_sequence(sequence, "sequence")

    if target_length <= 0:
        raise ValueError(f"target_length는 양수여야 합니다: {target_length}")

    n = seq.shape[0]

    if n == target_length:
        return seq.copy()
    elif n > target_length:
        # 중앙 기준 잘라냄
        start = (n - target_length) // 2
        return seq[start:start + target_length].copy()
    else:
        # 뒤쪽 패딩
        pad_total = target_length - n
        return _apply_padding(seq, 0, pad_total, mode)


def standardize_lengths(
    sequences: list[NDArray],
    target_length: int | None = None,
    mode: PaddingMode = PaddingMode.ZERO,
) -> list[NDArray]:
    """
    여러 시퀀스의 길이를 동일하게 표준화.

    Args:
        sequences: 시퀀스 리스트
        target_length: 목표 길이 (None이면 최대 길이 사용)
        mode: 패딩 모드

    Returns:
        동일 길이의 시퀀스 리스트

    Raises:
        ValueError: 빈 리스트인 경우
    """
    if not sequences:
        raise ValueError("시퀀스 리스트가 비어있습니다.")

    if target_length is None:
        target_length = max(seq.shape[0] for seq in sequences)

    return [pad_or_truncate(seq, target_length, mode) for seq in sequences]


# =============================================================================
# 시퀀스 비교/거리 (Sequence Distance)
# =============================================================================

def dtw_distance(
    seq_a: NDArray,
    seq_b: NDArray,
    distance_metric: DistanceMetric = DistanceMetric.EUCLIDEAN,
    return_cost_matrix: bool = False,
) -> DTWResult:
    """
    DTW (Dynamic Time Warping) 거리 계산.

    동적 프로그래밍으로 두 시퀀스 간의 최적 정렬 경로와 거리를 계산합니다.
    시간 축의 비선형 워핑을 허용하여 속도 차이에 강건한 비교가 가능합니다.

    비용 행렬 크기: (N+1) x (M+1), 경계는 INF로 초기화하여
    경로가 반드시 (0,0) → (N-1,M-1)을 통과하도록 보장합니다.

    시간 복잡도: O(N * M), 공간 복잡도: O(N * M)

    Args:
        seq_a: (N,) 또는 (N, D) 시퀀스 A
        seq_b: (M,) 또는 (M, D) 시퀀스 B
        distance_metric: 프레임 간 거리 메트릭
        return_cost_matrix: True면 비용 행렬도 반환

    Returns:
        DTWResult 객체

    Raises:
        ValueError: 시퀀스가 MAX_DTW_SEQUENCE_LENGTH를 초과하는 경우
    """
    a = _ensure_2d(_validate_sequence(seq_a, "seq_a"))
    b = _ensure_2d(_validate_sequence(seq_b, "seq_b"))

    n, m = a.shape[0], b.shape[0]

    if n > MAX_DTW_SEQUENCE_LENGTH or m > MAX_DTW_SEQUENCE_LENGTH:
        raise ValueError(
            f"시퀀스 길이({n}, {m})가 최대 허용치"
            f"({MAX_DTW_SEQUENCE_LENGTH})를 초과합니다. "
            "리샘플링 후 사용하세요."
        )

    # 비용 행렬 초기화 (경계 INF → 경로가 내부만 통과)
    cost = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    cost[0, 0] = 0.0

    # DP 테이블 채우기
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = _point_distance(a[i - 1], b[j - 1], distance_metric)
            cost[i, j] = d + min(
                cost[i - 1, j],      # 삽입 (seq_a 프레임 확장)
                cost[i, j - 1],      # 삭제 (seq_b 프레임 확장)
                cost[i - 1, j - 1],  # 대각선 (1:1 매칭)
            )

    total_distance = float(cost[n, m])

    # 역추적: (n, m) → (1, 1) → (0, 0)에서 종료
    # 경계 INF 덕분에 경로는 항상 (1,1)을 통과한 뒤 (0,0)으로 이동
    path: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))  # 0-indexed로 변환
        # 이전 셀 중 최소 비용 선택
        candidates = [
            (cost[i - 1, j - 1], i - 1, j - 1),
            (cost[i - 1, j], i - 1, j),
            (cost[i, j - 1], i, j - 1),
        ]
        _, i, j = min(candidates, key=lambda x: x[0])
    path.reverse()

    path_length = len(path) if path else 1
    normalized = total_distance / path_length

    return DTWResult(
        distance=total_distance,
        normalized_distance=normalized,
        warping_path=path,
        cost_matrix=cost[1:, 1:] if return_cost_matrix else None,
    )


def frechet_distance(seq_a: NDArray, seq_b: NDArray) -> float:
    """
    이산 프레셰 거리 계산.

    두 커브(시퀀스) 간의 최대 최소 거리를 계산합니다.
    DTW와 달리 순서를 보존하면서 가장 나쁜 경우의 거리를 측정합니다.
    "개 산책 거리"(dog-walking distance)로도 알려져 있습니다.

    반복적 DP로 구현하여 RecursionError를 방지합니다.

    시간 복잡도: O(N * M)

    Args:
        seq_a: (N,) 또는 (N, D) 시퀀스 A
        seq_b: (M,) 또는 (M, D) 시퀀스 B

    Returns:
        프레셰 거리 (float, >= 0)
    """
    a = _ensure_2d(_validate_sequence(seq_a, "seq_a"))
    b = _ensure_2d(_validate_sequence(seq_b, "seq_b"))

    n, m = a.shape[0], b.shape[0]

    # 반복적 DP 테이블
    ca = np.full((n, m), np.inf, dtype=np.float64)

    for i in range(n):
        for j in range(m):
            d = float(np.sqrt(np.sum((a[i] - b[j]) ** 2)))
            if i == 0 and j == 0:
                ca[i, j] = d
            elif i > 0 and j == 0:
                ca[i, j] = max(ca[i - 1, 0], d)
            elif i == 0 and j > 0:
                ca[i, j] = max(ca[0, j - 1], d)
            else:
                ca[i, j] = max(
                    min(ca[i - 1, j], ca[i - 1, j - 1], ca[i, j - 1]),
                    d,
                )

    return float(ca[n - 1, m - 1])


def sequence_cosine_similarity(seq_a: NDArray, seq_b: NDArray) -> float:
    """
    두 시퀀스 간 코사인 유사도.

    시퀀스를 평탄화한 벡터로 취급하여 코사인 유사도를 계산합니다.
    길이가 다르면 긴 쪽에 맞춰 리샘플링합니다.

    Args:
        seq_a: 시퀀스 A
        seq_b: 시퀀스 B

    Returns:
        코사인 유사도 [-1, 1]
    """
    a = _validate_sequence(seq_a, "seq_a")
    b = _validate_sequence(seq_b, "seq_b")

    # 길이 맞춤 (리샘플링)
    if a.shape[0] != b.shape[0]:
        target_len = max(a.shape[0], b.shape[0])
        a = resample_sequence(a, target_len)
        b = resample_sequence(b, target_len)

    a_flat = a.ravel()
    b_flat = b.ravel()

    norm_a = np.linalg.norm(a_flat)
    norm_b = np.linalg.norm(b_flat)

    if norm_a < _EPSILON or norm_b < _EPSILON:
        return 0.0

    return float(np.dot(a_flat, b_flat) / (norm_a * norm_b))


def sequence_pearson_correlation(seq_a: NDArray, seq_b: NDArray) -> float:
    """
    두 시퀀스 간 피어슨 상관계수.

    1D 시퀀스 간의 선형 상관을 측정합니다.
    다차원인 경우 각 차원의 상관을 평균합니다.
    리듬/타이밍 유사도 측정에 유용합니다.

    Args:
        seq_a: (N,) 또는 (N, D) 시퀀스 A
        seq_b: (M,) 또는 (M, D) 시퀀스 B

    Returns:
        피어슨 상관계수 [-1, 1]
    """
    a = _validate_sequence(seq_a, "seq_a")
    b = _validate_sequence(seq_b, "seq_b")

    # 길이 맞춤
    if a.shape[0] != b.shape[0]:
        target_len = max(a.shape[0], b.shape[0])
        a = resample_sequence(a, target_len)
        b = resample_sequence(b, target_len)

    if a.ndim == 1:
        a_centered = a - np.mean(a)
        b_centered = b - np.mean(b)

        norm_a = np.linalg.norm(a_centered)
        norm_b = np.linalg.norm(b_centered)

        if norm_a < _EPSILON or norm_b < _EPSILON:
            return 0.0

        return float(np.dot(a_centered, b_centered) / (norm_a * norm_b))
    else:
        # 다차원: 각 차원별 상관계수의 평균
        d = min(a.shape[1], b.shape[1])
        correlations = []
        for col in range(d):
            a_col = a[:, col] - np.mean(a[:, col])
            b_col = b[:, col] - np.mean(b[:, col])
            norm_a = np.linalg.norm(a_col)
            norm_b = np.linalg.norm(b_col)
            if norm_a < _EPSILON or norm_b < _EPSILON:
                correlations.append(0.0)
            else:
                correlations.append(
                    float(np.dot(a_col, b_col) / (norm_a * norm_b))
                )
        return float(np.mean(correlations))


def sequence_euclidean_distance(
    seq_a: NDArray,
    seq_b: NDArray,
    normalized: bool = False,
) -> float:
    """
    두 시퀀스 간 유클리드 거리.

    Args:
        seq_a: 시퀀스 A
        seq_b: 시퀀스 B
        normalized: True면 시퀀스 길이의 제곱근으로 정규화

    Returns:
        유클리드 거리
    """
    a = _validate_sequence(seq_a, "seq_a")
    b = _validate_sequence(seq_b, "seq_b")

    # 길이 맞춤
    if a.shape[0] != b.shape[0]:
        target_len = max(a.shape[0], b.shape[0])
        a = resample_sequence(a, target_len)
        b = resample_sequence(b, target_len)

    dist = float(np.sqrt(np.sum((a - b) ** 2)))

    if normalized and a.shape[0] > 0:
        dist /= math.sqrt(a.shape[0])

    return dist


# =============================================================================
# 위상 분할 (Phase Segmentation)
# =============================================================================

def detect_phase_transitions(
    sequence: NDArray,
    threshold: float,
    min_phase_length: int = DEFAULT_MIN_PHASE_LENGTH,
) -> list[PhaseSegment]:
    """
    시퀀스의 위상 전환점을 검출하고 세그먼트를 생성.

    1차 차분(속도)의 부호 변화와 크기를 기반으로 위상을 분류합니다:
    - "ascending": 상승 구간 (양의 변화율)
    - "descending": 하강 구간 (음의 변화율)
    - "stationary": 정지 구간 (변화율 < threshold)

    Args:
        sequence: (N,) 1D 시퀀스
        threshold: 정지 판정 임계값 (변화율의 절대값)
        min_phase_length: 최소 위상 길이 (프레임)

    Returns:
        PhaseSegment 리스트
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("detect_phase_transitions은 1D 시퀀스만 지원합니다.")

    n = len(seq)
    if n < 2:
        return [PhaseSegment(
            start_idx=0, end_idx=0, label="stationary",
            confidence=1.0, duration_frames=1, mean_value=float(seq[0]),
        )]

    # 1차 차분
    diff = np.diff(seq)

    # 각 프레임의 위상 라벨 결정
    labels: list[str] = ["stationary"]  # 첫 프레임
    for i in range(len(diff)):
        if abs(diff[i]) < threshold:
            labels.append("stationary")
        elif diff[i] > 0:
            labels.append("ascending")
        else:
            labels.append("descending")

    # 연속 동일 라벨을 세그먼트로 그룹화
    raw_segments: list[PhaseSegment] = []
    current_label = labels[0]
    start = 0

    for i in range(1, n):
        if labels[i] != current_label:
            duration = i - start
            seg_data = seq[start:i]
            raw_segments.append(PhaseSegment(
                start_idx=start,
                end_idx=i - 1,
                label=current_label,
                confidence=_compute_phase_confidence(seg_data),
                duration_frames=duration,
                mean_value=float(np.mean(seg_data)),
            ))
            start = i
            current_label = labels[i]

    # 마지막 세그먼트
    duration = n - start
    seg_data = seq[start:]
    raw_segments.append(PhaseSegment(
        start_idx=start,
        end_idx=n - 1,
        label=current_label,
        confidence=_compute_phase_confidence(seg_data),
        duration_frames=duration,
        mean_value=float(np.mean(seg_data)),
    ))

    # 최소 길이 미만 세그먼트 병합
    return _merge_short_segments(raw_segments, min_phase_length, seq)


def segment_by_velocity(
    sequence: NDArray,
    fps: float,
    velocity_threshold: float,
    min_segment_length: int = DEFAULT_MIN_PHASE_LENGTH,
) -> list[PhaseSegment]:
    """
    속도 기반 위상 분할.

    프레임 간 변화율(속도)을 계산하고, 임계값을 기준으로
    고속/저속/정지 구간을 분류합니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        fps: 프레임 레이트 (양수)
        velocity_threshold: 속도 임계값 (units/second)
        min_segment_length: 최소 세그먼트 길이 (프레임)

    Returns:
        PhaseSegment 리스트 (라벨: "fast", "slow", "stationary")
    """
    seq = _validate_sequence(sequence, "sequence")

    if fps <= 0:
        raise ValueError(f"fps는 양수여야 합니다: {fps}")

    n = seq.shape[0]
    if n < 2:
        return [PhaseSegment(
            start_idx=0, end_idx=0, label="stationary",
            confidence=1.0, duration_frames=1,
            mean_value=float(seq[0]) if seq.ndim == 1 else 0.0,
        )]

    dt = 1.0 / fps

    # 속도 계산
    if seq.ndim == 1:
        velocity = np.abs(np.diff(seq)) / dt
    else:
        diffs = np.diff(seq, axis=0)
        velocity = np.sqrt(np.sum(diffs ** 2, axis=1)) / dt

    # 정지 임계값 = 전체 임계값의 10%
    stationary_threshold = velocity_threshold * 0.1

    # 프레임별 라벨 할당
    labels: list[str] = ["stationary"]  # 첫 프레임
    for i in range(len(velocity)):
        if velocity[i] < stationary_threshold:
            labels.append("stationary")
        elif velocity[i] < velocity_threshold:
            labels.append("slow")
        else:
            labels.append("fast")

    # 세그먼트 생성
    raw_segments: list[PhaseSegment] = []
    current_label = labels[0]
    start = 0

    for i in range(1, n):
        if labels[i] != current_label:
            duration = i - start
            # 구간 평균 속도
            vel_start = max(0, start - 1)
            vel_end = min(len(velocity), i)
            mean_vel = float(np.mean(velocity[vel_start:vel_end])) if vel_end > vel_start else 0.0
            # 라벨 일관성 기반 신뢰도
            same_count = sum(1 for lbl in labels[start:i] if lbl == current_label)
            confidence = same_count / duration if duration > 0 else 0.5

            raw_segments.append(PhaseSegment(
                start_idx=start,
                end_idx=i - 1,
                label=current_label,
                confidence=confidence,
                duration_frames=duration,
                mean_value=mean_vel,
            ))
            start = i
            current_label = labels[i]

    # 마지막 세그먼트
    duration = n - start
    vel_start = max(0, start - 1)
    mean_vel = float(np.mean(velocity[vel_start:])) if vel_start < len(velocity) else 0.0
    raw_segments.append(PhaseSegment(
        start_idx=start,
        end_idx=n - 1,
        label=current_label,
        confidence=1.0,
        duration_frames=duration,
        mean_value=mean_vel,
    ))

    # 최소 길이 미만 세그먼트 병합
    if seq.ndim == 1:
        return _merge_short_segments(raw_segments, min_segment_length, seq)
    else:
        # 다차원: 속도 시퀀스 기반 병합
        vel_padded = np.concatenate([[velocity[0]], velocity])
        return _merge_short_segments(raw_segments, min_segment_length, vel_padded)


def segment_by_curvature(
    sequence: NDArray,
    threshold: float,
    min_segment_length: int = DEFAULT_MIN_PHASE_LENGTH,
) -> list[PhaseSegment]:
    """
    곡률 기반 위상 분할.

    시퀀스의 2차 차분(가속도/곡률)을 기반으로
    "linear"(직선적) / "curved"(곡선적) 구간을 분류합니다.

    Args:
        sequence: (N,) 1D 시퀀스
        threshold: 곡률 임계값
        min_segment_length: 최소 세그먼트 길이

    Returns:
        PhaseSegment 리스트 (라벨: "linear", "curved")
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("segment_by_curvature는 1D 시퀀스만 지원합니다.")

    n = len(seq)
    if n < 3:
        return [PhaseSegment(
            start_idx=0, end_idx=n - 1, label="linear",
            confidence=1.0, duration_frames=n,
            mean_value=float(np.mean(seq)),
        )]

    # 2차 차분 (곡률 근사)
    curvature = np.abs(np.diff(seq, n=2))
    # 앞뒤 패딩으로 원본 길이 맞춤
    curv_padded = np.concatenate([[curvature[0]], curvature, [curvature[-1]]])

    # 라벨링
    labels: list[str] = []
    for c in curv_padded:
        labels.append("linear" if c < threshold else "curved")

    # 세그먼트 생성
    raw_segments: list[PhaseSegment] = []
    current_label = labels[0]
    start = 0

    for i in range(1, n):
        if labels[i] != current_label:
            duration = i - start
            seg_data = seq[start:i]
            # 해당 라벨과 일치하는 비율로 신뢰도 산출
            seg_curv = curv_padded[start:i]
            if current_label == "linear":
                conf = float(np.mean(seg_curv < threshold))
            else:
                conf = float(np.mean(seg_curv >= threshold))

            raw_segments.append(PhaseSegment(
                start_idx=start,
                end_idx=i - 1,
                label=current_label,
                confidence=conf,
                duration_frames=duration,
                mean_value=float(np.mean(seg_data)),
            ))
            start = i
            current_label = labels[i]

    # 마지막 세그먼트
    duration = n - start
    raw_segments.append(PhaseSegment(
        start_idx=start,
        end_idx=n - 1,
        label=current_label,
        confidence=1.0,
        duration_frames=duration,
        mean_value=float(np.mean(seq[start:])),
    ))

    return _merge_short_segments(raw_segments, min_segment_length, seq)


def find_zero_crossings(sequence: NDArray) -> NDArray:
    """
    시퀀스의 영교차점(zero-crossing) 인덱스를 검출.

    값이 0을 가로지르는 지점을 찾습니다.
    연속된 두 값의 부호가 다른 위치를 반환합니다.
    드리블 리듬, 진동 패턴 분석에 활용됩니다.

    Args:
        sequence: (N,) 1D 시퀀스

    Returns:
        영교차 인덱스 배열 (각 인덱스는 교차 직전 위치)
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("find_zero_crossings는 1D 시퀀스만 지원합니다.")

    if len(seq) < 2:
        return np.array([], dtype=np.int64)

    # 부호 계산 (0인 지점은 이전 부호 유지)
    signs = np.sign(seq)
    for i in range(1, len(signs)):
        if signs[i] == 0:
            signs[i] = signs[i - 1]

    # 부호 변화 검출
    sign_changes = np.diff(signs)
    crossings = np.where(sign_changes != 0)[0]

    return crossings.astype(np.int64)


# =============================================================================
# 슬라이딩 윈도우 (Sliding Window)
# =============================================================================

def sliding_window(
    sequence: NDArray,
    window_size: int,
    stride: int = DEFAULT_WINDOW_STRIDE,
) -> NDArray:
    """
    슬라이딩 윈도우로 시퀀스를 분할.

    NumPy stride tricks를 사용하여 메모리 효율적으로 윈도우를 생성합니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        window_size: 윈도우 크기 (프레임)
        stride: 윈도우 이동 간격 (프레임)

    Returns:
        1D 입력: (num_windows, window_size)
        2D 입력: (num_windows, window_size, D)

    Raises:
        ValueError: window_size > N이거나 stride <= 0인 경우
    """
    seq = _validate_sequence(sequence, "sequence")

    n = seq.shape[0]

    if window_size <= 0:
        raise ValueError(f"window_size는 양수여야 합니다: {window_size}")
    if stride <= 0:
        raise ValueError(f"stride는 양수여야 합니다: {stride}")
    if window_size > n:
        raise ValueError(
            f"window_size({window_size})가 시퀀스 길이({n})보다 큽니다."
        )

    num_windows = (n - window_size) // stride + 1

    if seq.ndim == 1:
        shape = (num_windows, window_size)
        strides = (seq.strides[0] * stride, seq.strides[0])
        windows = np.lib.stride_tricks.as_strided(
            seq, shape=shape, strides=strides
        )
        return windows.copy()  # 안전을 위해 복사 (stride_tricks 뷰 보호)
    else:
        shape = (num_windows, window_size, seq.shape[1])
        strides = (seq.strides[0] * stride, seq.strides[0], seq.strides[1])
        windows = np.lib.stride_tricks.as_strided(
            seq, shape=shape, strides=strides
        )
        return windows.copy()


def sliding_window_statistics(
    sequence: NDArray,
    window_size: int,
    stride: int = DEFAULT_WINDOW_STRIDE,
) -> NDArray:
    """
    슬라이딩 윈도우 통계량 추출.

    각 윈도우에 대해 [평균, 표준편차, 최솟값, 최댓값]을 계산합니다.

    Args:
        sequence: (N,) 1D 시퀀스
        window_size: 윈도우 크기
        stride: 이동 간격

    Returns:
        (num_windows, 4) 배열 - 각 행: [mean, std, min, max]
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("sliding_window_statistics는 1D 시퀀스만 지원합니다.")

    windows = sliding_window(seq, window_size, stride)

    stats = np.column_stack([
        np.mean(windows, axis=1),
        np.std(windows, axis=1),
        np.min(windows, axis=1),
        np.max(windows, axis=1),
    ])

    return stats


def extract_subsequences(
    sequence: NDArray,
    center_indices: NDArray,
    window_size: int,
    mode: PaddingMode = PaddingMode.ZERO,
) -> NDArray:
    """
    지정된 중심 인덱스 주변의 부분 시퀀스 추출.

    경계를 벗어나는 부분은 지정된 패딩 모드로 채웁니다.

    Args:
        sequence: (N,) 또는 (N, D) 시퀀스
        center_indices: 중심 인덱스 배열
        window_size: 윈도우 크기 (홀수 권장)
        mode: 경계 패딩 모드

    Returns:
        (len(center_indices), window_size) 또는
        (len(center_indices), window_size, D)
    """
    seq = _validate_sequence(sequence, "sequence")
    indices = np.asarray(center_indices, dtype=np.int64)

    if window_size <= 0:
        raise ValueError(f"window_size는 양수여야 합니다: {window_size}")

    half = window_size // 2

    # 패딩 적용 (앞뒤 half만큼)
    padded = _apply_padding(seq, half, half, mode)

    subsequences = []
    for idx in indices:
        # 패딩된 배열에서: 원래 idx는 padded[idx + half]
        # 윈도우 시작 = idx + half - half = idx
        start = int(idx)
        end = start + window_size
        subsequences.append(padded[start:end])

    return np.array(subsequences, dtype=np.float64)


# =============================================================================
# 피크 검출 (Peak Detection)
# =============================================================================

def find_peaks(
    sequence: NDArray,
    min_prominence: float = DEFAULT_PEAK_MIN_PROMINENCE,
    min_distance: int = DEFAULT_PEAK_MIN_DISTANCE,
) -> list[PeakInfo]:
    """
    시퀀스에서 피크(극대값) 검출.

    프로미넌스(prominence) 기반 필터링으로 의미있는 피크만 반환합니다.
    프로미넌스는 피크가 주변 계곡 대비 얼마나 돌출되었는지를 나타냅니다.

    슈팅 릴리스 포인트, 점프 최고점 검출 등에 활용됩니다.

    Args:
        sequence: (N,) 1D 시퀀스
        min_prominence: 최소 프로미넌스 (이 값 미만의 피크는 제외)
        min_distance: 피크 간 최소 거리 (프레임)

    Returns:
        PeakInfo 리스트 (인덱스 오름차순 정렬)
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("find_peaks는 1D 시퀀스만 지원합니다.")

    n = len(seq)
    if n < 3:
        return []

    # 1단계: 로컬 극대점 검출
    candidates: list[int] = []
    for i in range(1, n - 1):
        if seq[i] > seq[i - 1] and seq[i] > seq[i + 1]:
            candidates.append(i)

    if not candidates:
        return []

    # 2단계: 프로미넌스 계산
    peaks_with_prominence: list[PeakInfo] = []

    for peak_idx in candidates:
        peak_val = float(seq[peak_idx])

        # 왼쪽 탐색: 피크보다 높은 점 또는 시퀀스 시작까지
        left_min = peak_val
        left_base = peak_idx
        for j in range(peak_idx - 1, -1, -1):
            if seq[j] > peak_val:
                break
            if seq[j] < left_min:
                left_min = float(seq[j])
                left_base = j

        # 오른쪽 탐색: 피크보다 높은 점 또는 시퀀스 끝까지
        right_min = peak_val
        right_base = peak_idx
        for j in range(peak_idx + 1, n):
            if seq[j] > peak_val:
                break
            if seq[j] < right_min:
                right_min = float(seq[j])
                right_base = j

        # 프로미넌스 = 피크값 - max(좌측 최소, 우측 최소)
        prominence = peak_val - max(left_min, right_min)

        if prominence >= min_prominence:
            peaks_with_prominence.append(PeakInfo(
                index=peak_idx,
                value=peak_val,
                prominence=prominence,
                left_base=left_base,
                right_base=right_base,
            ))

    # 3단계: 최소 거리 필터링 (프로미넌스 높은 것 우선)
    if min_distance > 1 and len(peaks_with_prominence) > 1:
        peaks_with_prominence.sort(key=lambda p: p.prominence, reverse=True)

        selected: list[PeakInfo] = []
        occupied: set[int] = set()

        for peak in peaks_with_prominence:
            too_close = any(
                abs(peak.index - occ_idx) < min_distance
                for occ_idx in occupied
            )
            if not too_close:
                selected.append(peak)
                occupied.add(peak.index)

        peaks_with_prominence = selected

    # 인덱스 순으로 정렬하여 반환
    peaks_with_prominence.sort(key=lambda p: p.index)

    return peaks_with_prominence


def find_valleys(
    sequence: NDArray,
    min_prominence: float = DEFAULT_PEAK_MIN_PROMINENCE,
    min_distance: int = DEFAULT_PEAK_MIN_DISTANCE,
) -> list[PeakInfo]:
    """
    시퀀스에서 밸리(극소값) 검출.

    시퀀스를 반전시킨 후 피크 검출을 적용합니다.

    Args:
        sequence: (N,) 1D 시퀀스
        min_prominence: 최소 프로미넌스
        min_distance: 밸리 간 최소 거리 (프레임)

    Returns:
        PeakInfo 리스트 (value는 원본 값, prominence는 양수)
    """
    seq = _validate_sequence(sequence, "sequence")

    # 반전하여 피크 검출
    peaks = find_peaks(-seq, min_prominence, min_distance)

    # 원본 값으로 복원
    valleys: list[PeakInfo] = []
    for peak in peaks:
        valleys.append(PeakInfo(
            index=peak.index,
            value=-peak.value,
            prominence=peak.prominence,
            left_base=peak.left_base,
            right_base=peak.right_base,
        ))

    return valleys


# =============================================================================
# 주기성/상관 (Periodicity/Correlation)
# =============================================================================

def compute_autocorrelation(
    sequence: NDArray,
    max_lag: int | None = None,
) -> NDArray:
    """
    시퀀스의 자기상관 함수 계산.

    FFT 기반으로 O(N log N)에 정규화된 자기상관을 계산합니다.
    lag=0에서 1.0이며, 주기적 패턴의 lag에서 피크가 나타납니다.

    Args:
        sequence: (N,) 1D 시퀀스
        max_lag: 최대 래그 (None이면 N//2)

    Returns:
        (max_lag + 1,) 자기상관 값 배열
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("compute_autocorrelation은 1D 시퀀스만 지원합니다.")

    n = len(seq)

    if max_lag is None:
        max_lag = n // 2
    max_lag = min(max_lag, n - 1)

    # 평균 제거
    centered = seq - np.mean(seq)

    # FFT 기반 자기상관 (패딩으로 순환 상관 방지)
    padded_len = 1 << int(np.ceil(np.log2(2 * n)))
    fft_result = np.fft.rfft(centered, n=padded_len)
    power_spectrum = np.abs(fft_result) ** 2
    acf_full = np.fft.irfft(power_spectrum)[:n]

    # 정규화 (lag=0에서 1.0)
    if acf_full[0] > _EPSILON:
        acf_full /= acf_full[0]

    return acf_full[:max_lag + 1]


def compute_cross_correlation(
    seq_a: NDArray,
    seq_b: NDArray,
    max_lag: int | None = None,
    normalized: bool = True,
) -> NDArray:
    """
    두 시퀀스 간 교차상관 함수 계산.

    FFT 기반으로 효율적으로 계산하며, 양의 lag는
    seq_b가 seq_a보다 뒤처지는(lagging) 것을 의미합니다.

    Args:
        seq_a: (N,) 시퀀스 A
        seq_b: (M,) 시퀀스 B
        max_lag: 최대 래그 (None이면 max(N, M) // 2)
        normalized: True면 정규화된 교차상관 반환

    Returns:
        (2 * max_lag + 1,) 교차상관 값 배열
        인덱스 max_lag이 lag=0에 해당
    """
    a = _validate_sequence(seq_a, "seq_a")
    b = _validate_sequence(seq_b, "seq_b")

    if a.ndim != 1 or b.ndim != 1:
        raise ValueError("compute_cross_correlation은 1D 시퀀스만 지원합니다.")

    n = max(len(a), len(b))

    if max_lag is None:
        max_lag = n // 2

    # 평균 제거
    a_centered = a - np.mean(a)
    b_centered = b - np.mean(b)

    # FFT 기반 교차상관
    padded_len = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    fft_a = np.fft.rfft(a_centered, n=padded_len)
    fft_b = np.fft.rfft(b_centered, n=padded_len)

    # 교차상관 = IFFT(FFT(a) * conj(FFT(b)))
    cross = np.fft.irfft(fft_a * np.conj(fft_b))

    if normalized:
        norm_factor = np.sqrt(np.sum(a_centered ** 2) * np.sum(b_centered ** 2))
        if norm_factor > _EPSILON:
            cross /= norm_factor

    # [-max_lag, ..., 0, ..., max_lag] 순서로 재배열
    total_len = len(cross)
    result = np.empty(2 * max_lag + 1, dtype=np.float64)

    for lag in range(-max_lag, max_lag + 1):
        idx = lag % total_len
        result[lag + max_lag] = cross[idx]

    return result


def detect_periodicity(
    sequence: NDArray,
    min_period: int = 2,
    max_period: int | None = None,
) -> PeriodicityResult:
    """
    시퀀스의 주기성 검출.

    자기상관 함수의 피크를 분석하여 지배적 주기와 보조 주기를 검출합니다.
    드리블 리듬, 반복 동작 주기 분석에 활용됩니다.

    Args:
        sequence: (N,) 1D 시퀀스
        min_period: 최소 주기 (프레임)
        max_period: 최대 주기 (None이면 N//2)

    Returns:
        PeriodicityResult 객체
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("detect_periodicity는 1D 시퀀스만 지원합니다.")

    n = len(seq)

    if max_period is None:
        max_period = n // 2
    max_period = min(max_period, n // 2)

    if min_period < 2:
        min_period = 2

    # 자기상관 계산
    acf = compute_autocorrelation(seq, max_lag=max_period)

    # min_period 이상의 범위에서 피크 검출
    search_acf = acf[min_period:]

    if len(search_acf) < 3:
        return PeriodicityResult(
            dominant_period=0,
            strength=0.0,
            autocorrelation_values=acf,
            secondary_periods=[],
        )

    # 자기상관 피크 검출
    peaks = find_peaks(search_acf, min_prominence=0.05, min_distance=2)

    if not peaks:
        return PeriodicityResult(
            dominant_period=0,
            strength=0.0,
            autocorrelation_values=acf,
            secondary_periods=[],
        )

    # 자기상관 값 기준 정렬 (가장 강한 피크 = 지배적 주기)
    peaks_sorted = sorted(peaks, key=lambda p: p.value, reverse=True)

    dominant_peak = peaks_sorted[0]
    dominant_period = dominant_peak.index + min_period
    strength = max(0.0, min(1.0, dominant_peak.value))

    # 보조 주기 (최대 4개)
    secondary: list[tuple[int, float]] = []
    for peak in peaks_sorted[1:5]:
        period = peak.index + min_period
        s = max(0.0, min(1.0, peak.value))
        secondary.append((period, s))

    return PeriodicityResult(
        dominant_period=dominant_period,
        strength=strength,
        autocorrelation_values=acf,
        secondary_periods=secondary,
    )


def calculate_sequence_entropy(
    sequence: NDArray,
    num_bins: int = 10,
) -> float:
    """
    시퀀스의 섀넌 엔트로피 계산.

    히스토그램 기반으로 값의 분포 엔트로피를 계산합니다.
    균일 분포면 최대(log2(num_bins)), 단일 값이면 0입니다.

    동작 복잡도, 움직임 다양성 측정에 활용됩니다.

    Args:
        sequence: (N,) 1D 시퀀스
        num_bins: 히스토그램 빈 수

    Returns:
        엔트로피 값 (bits)
    """
    seq = _validate_sequence(sequence, "sequence")
    if seq.ndim != 1:
        raise ValueError("calculate_sequence_entropy는 1D 시퀀스만 지원합니다.")

    if num_bins <= 0:
        raise ValueError(f"num_bins는 양수여야 합니다: {num_bins}")

    # 히스토그램 계산
    hist, _ = np.histogram(seq, bins=num_bins)

    # 확률 분포
    probs = hist / np.sum(hist)

    # 0이 아닌 확률만 사용 (log(0) 방지)
    nonzero = probs[probs > 0]

    # 섀넌 엔트로피 (bits)
    entropy = -float(np.sum(nonzero * np.log2(nonzero)))

    return entropy


# =============================================================================
# 정렬/워핑 (Alignment/Warping)
# =============================================================================

def align_sequences_dtw(
    seq_a: NDArray,
    seq_b: NDArray,
    distance_metric: DistanceMetric = DistanceMetric.EUCLIDEAN,
) -> SequenceAlignment:
    """
    DTW 기반 시퀀스 정렬.

    두 시퀀스를 DTW로 정렬하여 동일 시간축에 매핑합니다.
    워핑 경로를 따라 프레임을 복제/생략하여 정렬합니다.

    동작 비교(예: 선수 슛 vs 레퍼런스 슛)에서 시간 차이를 제거한
    프레임 단위 비교에 사용됩니다.

    Args:
        seq_a: (N,) 또는 (N, D) 시퀀스 A
        seq_b: (M,) 또는 (M, D) 시퀀스 B
        distance_metric: 거리 메트릭

    Returns:
        SequenceAlignment 객체
    """
    a = _validate_sequence(seq_a, "seq_a")
    b = _validate_sequence(seq_b, "seq_b")

    # DTW 계산
    dtw_result = dtw_distance(a, b, distance_metric)
    path = dtw_result.warping_path

    if not path:
        return SequenceAlignment(
            aligned_a=a.copy(),
            aligned_b=b.copy(),
            warping_path=path,
            distance=dtw_result.distance,
            compression_ratio=1.0,
        )

    # 워핑 경로를 따라 정렬된 시퀀스 생성
    aligned_a_list = [a[i_a] for i_a, _ in path]
    aligned_b_list = [b[i_b] for _, i_b in path]

    aligned_a = np.array(aligned_a_list, dtype=np.float64)
    aligned_b = np.array(aligned_b_list, dtype=np.float64)

    # 압축비 (정렬 후 길이 / 원본 평균 길이)
    original_avg_len = (a.shape[0] + b.shape[0]) / 2.0
    compression_ratio = (
        len(path) / original_avg_len if original_avg_len > 0 else 1.0
    )

    return SequenceAlignment(
        aligned_a=aligned_a,
        aligned_b=aligned_b,
        warping_path=path,
        distance=dtw_result.distance,
        compression_ratio=compression_ratio,
    )


def warp_sequence(
    sequence: NDArray,
    warping_path: list[tuple[int, int]],
    source_index: int = 0,
) -> NDArray:
    """
    워핑 경로를 사용하여 시퀀스를 변형.

    DTW 워핑 경로의 한쪽 인덱스를 기준으로 시퀀스를 재매핑합니다.

    Args:
        sequence: 원본 시퀀스
        warping_path: DTW 워핑 경로 [(i, j), ...]
        source_index: 경로에서 사용할 인덱스 (0: 첫번째, 1: 두번째)

    Returns:
        워핑된 시퀀스
    """
    seq = _validate_sequence(sequence, "sequence")

    if not warping_path:
        return seq.copy()

    if source_index not in (0, 1):
        raise ValueError(f"source_index는 0 또는 1이어야 합니다: {source_index}")

    indices = [pair[source_index] for pair in warping_path]

    return seq[indices].copy()


def template_match(
    sequence: NDArray,
    template: NDArray,
    threshold: float = 0.8,
) -> list[tuple[int, float]]:
    """
    시퀀스에서 템플릿과 유사한 구간 검출.

    정규화 교차상관(NCC)을 사용하여 템플릿과 유사한 위치를 찾습니다.
    동작 패턴 검출(슛 모션, 드리블 패턴 등)에 활용됩니다.

    Args:
        sequence: (N,) 검색 대상 시퀀스
        template: (M,) 템플릿 시퀀스 (M <= N)
        threshold: 유사도 임계값 [0, 1]

    Returns:
        매칭 위치 리스트 [(start_index, similarity_score), ...]
        유사도 내림차순 정렬
    """
    seq = _validate_sequence(sequence, "sequence")
    tmpl = _validate_sequence(template, "template")

    if seq.ndim != 1 or tmpl.ndim != 1:
        raise ValueError("template_match는 1D 시퀀스만 지원합니다.")

    n = len(seq)
    m = len(tmpl)

    if m > n:
        raise ValueError(
            f"템플릿 길이({m})가 시퀀스 길이({n})보다 큽니다."
        )

    # 템플릿 정규화
    tmpl_centered = tmpl - np.mean(tmpl)
    tmpl_norm = np.linalg.norm(tmpl_centered)

    if tmpl_norm < _EPSILON:
        logger.warning("템플릿의 분산이 0에 가까워 매칭이 불가능합니다.")
        return []

    matches: list[tuple[int, float]] = []

    # 슬라이딩 윈도우 NCC
    for i in range(n - m + 1):
        window = seq[i:i + m]
        window_centered = window - np.mean(window)
        window_norm = np.linalg.norm(window_centered)

        if window_norm < _EPSILON:
            continue

        ncc = float(
            np.dot(tmpl_centered, window_centered) / (tmpl_norm * window_norm)
        )

        if ncc >= threshold:
            matches.append((i, ncc))

    # 유사도 내림차순 정렬
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches


# =============================================================================
# 배치 연산 (Batch Operations)
# =============================================================================

def batch_dtw_distances(
    sequences: list[NDArray],
    reference: NDArray,
    distance_metric: DistanceMetric = DistanceMetric.EUCLIDEAN,
) -> NDArray:
    """
    여러 시퀀스와 참조 시퀀스 간 DTW 거리 일괄 계산.

    Args:
        sequences: 시퀀스 리스트
        reference: 참조 시퀀스
        distance_metric: 거리 메트릭

    Returns:
        (len(sequences),) DTW 정규화 거리 배열
    """
    if not sequences:
        return np.array([], dtype=np.float64)

    ref = _validate_sequence(reference, "reference")

    if len(sequences) > _MAX_BATCH_SIZE:
        logger.warning(
            f"배치 크기({len(sequences)})가 최대치({_MAX_BATCH_SIZE})를 초과합니다. "
            f"처음 {_MAX_BATCH_SIZE}개만 처리합니다."
        )
        sequences = sequences[:_MAX_BATCH_SIZE]

    distances = np.empty(len(sequences), dtype=np.float64)

    for i, seq in enumerate(sequences):
        result = dtw_distance(seq, ref, distance_metric)
        distances[i] = result.normalized_distance

    return distances


def batch_normalize_sequences(
    sequences: list[NDArray],
    method: str = "z_score",
) -> list[NDArray]:
    """
    여러 시퀀스를 일괄 정규화.

    Args:
        sequences: 시퀀스 리스트
        method: 정규화 방법 ("z_score", "min_max")

    Returns:
        정규화된 시퀀스 리스트
    """
    if not sequences:
        return []

    if method == "z_score":
        return [z_normalize_sequence(seq) for seq in sequences]
    elif method == "min_max":
        return [min_max_normalize_sequence(seq) for seq in sequences]
    else:
        raise ValueError(
            f"지원하지 않는 정규화 방법: {method}. "
            "'z_score' 또는 'min_max'를 사용하세요."
        )


# =============================================================================
# Export 목록
# =============================================================================

__all__ = [
    # =========================================================================
    # 상수
    # =========================================================================
    "MAX_DTW_SEQUENCE_LENGTH",
    "DEFAULT_MIN_PHASE_LENGTH",
    "DEFAULT_PEAK_MIN_DISTANCE",
    "DEFAULT_PEAK_MIN_PROMINENCE",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_WINDOW_STRIDE",
    # =========================================================================
    # Enum
    # =========================================================================
    "PaddingMode",
    "DistanceMetric",
    "SegmentationMethod",
    # =========================================================================
    # 데이터 클래스
    # =========================================================================
    "DTWResult",
    "PhaseSegment",
    "PeakInfo",
    "SequenceAlignment",
    "PeriodicityResult",
    # =========================================================================
    # 시퀀스 정규화
    # =========================================================================
    "z_normalize_sequence",
    "min_max_normalize_sequence",
    "resample_sequence",
    "pad_or_truncate",
    "standardize_lengths",
    # =========================================================================
    # 시퀀스 비교/거리
    # =========================================================================
    "dtw_distance",
    "frechet_distance",
    "sequence_cosine_similarity",
    "sequence_pearson_correlation",
    "sequence_euclidean_distance",
    # =========================================================================
    # 위상 분할
    # =========================================================================
    "detect_phase_transitions",
    "segment_by_velocity",
    "segment_by_curvature",
    "find_zero_crossings",
    # =========================================================================
    # 슬라이딩 윈도우
    # =========================================================================
    "sliding_window",
    "sliding_window_statistics",
    "extract_subsequences",
    # =========================================================================
    # 피크 검출
    # =========================================================================
    "find_peaks",
    "find_valleys",
    # =========================================================================
    # 주기성/상관
    # =========================================================================
    "compute_autocorrelation",
    "compute_cross_correlation",
    "detect_periodicity",
    "calculate_sequence_entropy",
    # =========================================================================
    # 정렬/워핑
    # =========================================================================
    "align_sequences_dtw",
    "warp_sequence",
    "template_match",
    # =========================================================================
    # 배치 연산
    # =========================================================================
    "batch_dtw_distances",
    "batch_normalize_sequences",
]

__version__ = "1.0.0"
__author__ = "SPOIN_COURTVIEW"
