# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: statistical_utils.py
설명: 고급 통계 분석 유틸리티
      - 분포 분석 (왜도, 첨도, 사분위)
      - 변동계수 및 일관성 메트릭
      - 이상값 검출 (Z-score, IQR, MAD)
      - 가중 집계 (트리밍, 베이지안, 조화)
      - 순위/백분위 순위
      - 신뢰구간 (z-기반)
      - 신뢰도 메트릭 (ICC, Cronbach α, Cohen's d)
      - 온라인/러닝 통계 (Welford 알고리즘)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - math_utils의 기본 통계를 확장하는 고급 분석 도구
    - 변동계수(CV) 기반 일관성 메트릭 (6+ 모듈에서 중복 사용됨)
    - 3가지 이상값 검출 방법 (Z-score, IQR, MAD)
    - ICC(2,1) 평가자 간 신뢰도
    - Welford 온라인 알고리즘 기반 러닝 통계
    - 순수 NumPy 구현 (외부 통계 라이브러리 무의존)

사용 예시:
    >>> from utils.statistical_utils import (
    ...     coefficient_of_variation,
    ...     detect_outliers_iqr,
    ...     confidence_interval_z,
    ... )
    >>> import numpy as np
    >>> data = np.array([2.0, 3.0, 5.0, 7.0, 11.0])
    >>> cv = coefficient_of_variation(data)
    >>> cv > 0
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

# 신뢰구간 기본 수준
DEFAULT_CONFIDENCE_LEVEL: float = 0.95

# z 임계값 (표준정규분포 양측 검정)
Z_CRITICAL_95: float = 1.959964  # 95% 양측
Z_CRITICAL_99: float = 2.575829  # 99% 양측

# 이상값 검출 기본 임계값
DEFAULT_OUTLIER_THRESHOLD: float = 3.0   # Z-score 기반
DEFAULT_IQR_MULTIPLIER: float = 1.5      # IQR 기반 (Tukey)

# 배치 최대 크기
_MAX_BATCH_SIZE: int = 10000

# z→백분위 변환용 상수 (math.erf 사용)
_SQRT2: float = math.sqrt(2.0)


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class OutlierMethod(Enum):
    """이상값 검출 방법."""
    Z_SCORE = "z_score"                # Z-score 기반 (|z| > threshold)
    IQR = "iqr"                        # IQR 기반 (Tukey 울타리)
    MAD = "mad"                        # MAD 기반 (중앙절대편차)
    MODIFIED_Z_SCORE = "modified_z"    # 수정 Z-score (MAD 기반)


@unique
class RankMethod(Enum):
    """순위 산정 방법."""
    AVERAGE = "average"     # 동점 시 평균 순위
    MIN = "min"             # 동점 시 최소 순위
    MAX = "max"             # 동점 시 최대 순위
    DENSE = "dense"         # 동점 후 다음 순위 = 현재 + 1
    ORDINAL = "ordinal"     # 동점 없음 (등장 순서)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class DistributionStats:
    """
    분포 통계량 (기본 통계 + 분포 형태).

    Attributes:
        mean: 평균
        std: 표준편차
        median: 중앙값
        min_val: 최솟값
        max_val: 최댓값
        count: 데이터 수
        q1: 1사분위수 (25%)
        q3: 3사분위수 (75%)
        iqr: 사분위 범위 (Q3 - Q1)
        skewness: 왜도 (Fisher's, 비대칭 정도)
        kurtosis: 첨도 (excess, 정규분포 = 0)
    """
    mean: float
    std: float
    median: float
    min_val: float
    max_val: float
    count: int
    q1: float
    q3: float
    iqr: float
    skewness: float
    kurtosis: float

    def __repr__(self) -> str:
        return (
            f"DistributionStats(mean={self.mean:.4f}, std={self.std:.4f}, "
            f"median={self.median:.4f}, n={self.count}, "
            f"skew={self.skewness:.4f}, kurt={self.kurtosis:.4f})"
        )


@dataclass(slots=True)
class ConfidenceInterval:
    """
    신뢰구간 결과.

    Attributes:
        lower: 하한
        upper: 상한
        confidence_level: 신뢰 수준 (0-1)
        sample_size: 표본 크기
        mean: 표본 평균
        margin_of_error: 오차 한계
    """
    lower: float
    upper: float
    confidence_level: float
    sample_size: int
    mean: float
    margin_of_error: float

    def __repr__(self) -> str:
        return (
            f"ConfidenceInterval([{self.lower:.4f}, {self.upper:.4f}], "
            f"level={self.confidence_level:.0%}, n={self.sample_size})"
        )


@dataclass(slots=True)
class OutlierResult:
    """
    이상값 검출 결과.

    Attributes:
        is_outlier: 각 데이터의 이상값 여부 (bool 배열)
        outlier_indices: 이상값 인덱스 배열
        scores: 각 데이터의 이상치 점수 (Z-score 등)
        threshold: 사용된 임계값
        n_outliers: 이상값 개수
        method: 사용된 검출 방법
    """
    is_outlier: NDArray
    outlier_indices: NDArray
    scores: NDArray
    threshold: float
    n_outliers: int
    method: str

    def __repr__(self) -> str:
        return (
            f"OutlierResult(n_outliers={self.n_outliers}, "
            f"method='{self.method}', threshold={self.threshold:.2f})"
        )


@dataclass(slots=True)
class RankingResult:
    """
    순위 산정 결과.

    Attributes:
        ranks: 순위 배열 (1-based)
        percentiles: 백분위 배열 (0-100)
        z_scores: Z-score 배열
    """
    ranks: NDArray
    percentiles: NDArray
    z_scores: NDArray

    def __repr__(self) -> str:
        return (
            f"RankingResult(n={len(self.ranks)}, "
            f"rank_range=[{np.min(self.ranks):.1f}, {np.max(self.ranks):.1f}])"
        )


@dataclass(slots=True)
class ICCResult:
    """
    ICC (급내 상관계수) 결과.

    Attributes:
        value: ICC 값 [-1, 1]
        f_value: F-통계량
        df_between: 집단 간 자유도
        df_within: 집단 내 자유도
        n_subjects: 피험자 수
        n_raters: 평가자 수
    """
    value: float
    f_value: float
    df_between: int
    df_within: int
    n_subjects: int
    n_raters: int

    def __repr__(self) -> str:
        return (
            f"ICCResult(icc={self.value:.4f}, F={self.f_value:.4f}, "
            f"subjects={self.n_subjects}, raters={self.n_raters})"
        )


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _validate_values(values: NDArray, name: str = "values") -> NDArray:
    """값 배열 검증 및 float64 1D 변환."""
    if not isinstance(values, np.ndarray):
        raise TypeError(
            f"{name}은 numpy.ndarray여야 합니다. "
            f"받은 타입: {type(values).__name__}"
        )
    arr = values.ravel().astype(np.float64, copy=False)
    if arr.size == 0:
        raise ValueError(f"{name}이 비어있습니다.")
    return arr


def _z_critical(confidence: float) -> float:
    """신뢰 수준에 대한 z 임계값 계산 (양측 검정)."""
    if confidence <= 0 or confidence >= 1:
        raise ValueError(
            f"신뢰 수준은 (0, 1) 범위여야 합니다: {confidence}"
        )
    # 역정규분포 근사: percentile_to_z 활용
    alpha = (1 - confidence) / 2
    return abs(percentile_to_z(1 - alpha))


# =============================================================================
# 분포 분석 (Distribution Analysis)
# =============================================================================

def calculate_distribution_stats(values: NDArray) -> DistributionStats:
    """
    포괄적 분포 통계량 계산.

    기본 통계(평균, 표준편차, 중앙값)에 더해
    사분위수, 왜도, 첨도를 계산합니다.

    Args:
        values: 데이터 배열

    Returns:
        DistributionStats 객체
    """
    arr = _validate_values(values, "values")
    n = len(arr)

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    median = float(np.median(arr))
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    skew = calculate_skewness(arr)
    kurt = calculate_kurtosis(arr)

    return DistributionStats(
        mean=mean,
        std=std,
        median=median,
        min_val=min_val,
        max_val=max_val,
        count=n,
        q1=q1,
        q3=q3,
        iqr=iqr,
        skewness=skew,
        kurtosis=kurt,
    )


def calculate_skewness(values: NDArray) -> float:
    """
    Fisher의 왜도(skewness) 계산.

    왜도는 분포의 비대칭 정도를 나타냅니다:
    - 0: 대칭 분포
    - > 0: 오른쪽 꼬리가 긴 분포 (right-skewed)
    - < 0: 왼쪽 꼬리가 긴 분포 (left-skewed)

    Fisher의 비편향 추정량:
    skew = [n / ((n-1)(n-2))] * Σ[(xi - mean) / std]³

    Args:
        values: 데이터 배열

    Returns:
        왜도 값
    """
    arr = _validate_values(values, "values")
    n = len(arr)

    if n < 3:
        return 0.0

    mean = np.mean(arr)
    std = np.std(arr, ddof=1)

    if std < _EPSILON:
        return 0.0

    # Fisher의 비편향 왜도
    # m3 = (1/n) Σ[(xi - mean)/s]³ (s = ddof=1 std)
    # G₁ = m3 × n² / ((n-1)(n-2)) — 정확한 변환 공식
    m3 = np.mean(((arr - mean) / std) ** 3)
    correction = (n * n) / ((n - 1) * (n - 2))
    return float(m3 * correction)


def calculate_kurtosis(values: NDArray, excess: bool = True) -> float:
    """
    첨도(kurtosis) 계산.

    첨도는 분포의 꼬리 두께를 나타냅니다:
    - excess=True: 정규분포 = 0 (초과 첨도)
    - excess=False: 정규분포 = 3

    Fisher의 비편향 추정량:
    kurt = [(n+1)*n / ((n-1)(n-2)(n-3))] * Σ[(xi-mean)/std]⁴ - 3*(n-1)²/((n-2)(n-3))

    Args:
        values: 데이터 배열
        excess: True면 초과 첨도 (정규분포 = 0)

    Returns:
        첨도 값
    """
    arr = _validate_values(values, "values")
    n = len(arr)

    if n < 4:
        return 0.0

    mean = np.mean(arr)
    std = np.std(arr, ddof=1)

    if std < _EPSILON:
        return 0.0

    # 4차 적률
    m4 = float(np.mean(((arr - mean) / std) ** 4))

    # Fisher의 비편향 추정량
    # G₂ = (n+1)×n²×m4 / ((n-1)(n-2)(n-3)) - 3(n-1)² / ((n-2)(n-3))
    # m4는 ddof=1 std 기준이므로 n² 인수 필요
    n1 = n - 1
    n2 = n - 2
    n3 = n - 3
    kurt = ((n + 1) * n * n * m4) / (n1 * n2 * n3)

    if excess:
        kurt -= 3.0 * (n1 * n1) / (n2 * n3)
    else:
        # 비초과 첨도 보정
        kurt -= 3.0 * (n1 * n1) / (n2 * n3)
        kurt += 3.0

    return kurt


def z_to_percentile(z_score: float) -> float:
    """
    Z-score를 백분위로 변환 (표준정규분포 CDF).

    Φ(z) = 0.5 * (1 + erf(z / √2))

    Args:
        z_score: Z-score 값

    Returns:
        백분위 (0-100)
    """
    cdf = 0.5 * (1.0 + math.erf(z_score / _SQRT2))
    return cdf * 100.0


def percentile_to_z(percentile: float) -> float:
    """
    백분위를 Z-score로 변환 (표준정규분포 역CDF).

    Beasley-Springer-Moro 알고리즘 사용.
    정밀도: |z| < 7.5 범위에서 절대오차 < 1e-8.

    Args:
        percentile: 백분위 (0-100) 또는 확률 (0-1)

    Returns:
        Z-score
    """
    # 0-100 범위이면 0-1로 변환
    p = percentile / 100.0 if percentile > 1.0 else percentile

    if p <= 0 or p >= 1:
        raise ValueError(
            f"백분위는 (0, 100) 범위여야 합니다: {percentile}"
        )

    # Beasley-Springer-Moro 알고리즘
    a = (
        -3.969683028665376e+01,  2.209460984245205e+02,
        -2.759285104469687e+02,  1.383577518672690e+02,
        -3.066479806614716e+01,  2.506628277459239e+00,
    )
    b = (
        -5.447609879822406e+01,  1.615858368580409e+02,
        -1.556989798598866e+02,  6.680131188771972e+01,
        -1.328068155288572e+01,
    )
    c = (
        -7.784894002430293e-03, -3.223964580411365e-01,
        -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00,  2.938163982698783e+00,
    )
    d = (
         7.784695709041462e-03,  3.224671290700398e-01,
         2.445134137142996e+00,  3.754408661907416e+00,
    )

    p_low = 0.02425
    p_high = 1 - p_low

    if p < p_low:
        # 왼쪽 꼬리 근사
        q = math.sqrt(-2 * math.log(p))
        z = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    elif p <= p_high:
        # 중앙 근사
        q = p - 0.5
        r = q * q
        z = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
            (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    else:
        # 오른쪽 꼬리 근사
        q = math.sqrt(-2 * math.log(1 - p))
        z = -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
             ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)

    return z


# =============================================================================
# 변동/일관성 (Variation & Consistency)
# =============================================================================

def coefficient_of_variation(values: NDArray) -> float:
    """
    변동계수 (CV, Coefficient of Variation) 계산.

    CV = σ / μ (표준편차 / 평균)

    동작 일관성, 타이밍 변동, 속도 안정성 등의 측정에 사용됩니다.
    6+ 모듈에서 중복 구현되어 있던 핵심 메트릭입니다.

    Args:
        values: 양수 데이터 배열 (평균이 0에 가까우면 부정확)

    Returns:
        변동계수 (0에 가까울수록 일관성 높음)
    """
    arr = _validate_values(values, "values")
    mean = float(np.mean(arr))

    if abs(mean) < _EPSILON:
        logger.debug("평균이 0에 가까워 CV 계산이 부정확합니다.")
        return float("inf") if float(np.std(arr)) > _EPSILON else 0.0

    return float(np.std(arr, ddof=1) / abs(mean)) if len(arr) > 1 else 0.0


def consistency_score(values: NDArray) -> float:
    """
    일관성 점수 계산 (0-100).

    CV 기반 일관성 메트릭:
    score = max(0, 100 * (1 - CV))

    CV = 0이면 100점 (완벽한 일관성),
    CV >= 1이면 0점 (매우 불규칙).

    슈팅 폼 일관성, 드리블 높이 일관성, 움직임 균일도 등에 사용됩니다.

    Args:
        values: 데이터 배열

    Returns:
        일관성 점수 (0-100)
    """
    arr = _validate_values(values, "values")

    if len(arr) < 2:
        return 100.0  # 단일 값은 완벽한 일관성

    cv = coefficient_of_variation(arr)

    if cv == float("inf"):
        return 0.0

    return max(0.0, min(100.0, 100.0 * (1.0 - cv)))


def temporal_consistency_index(
    sequence: NDArray,
    fps: float | None = None,
) -> float:
    """
    시간적 일관성 지수 (0-1).

    연속 프레임 간 변화량의 변동계수를 기반으로
    시간적 일관성을 측정합니다.
    값이 1에 가까울수록 안정적입니다.

    Args:
        sequence: (N,) 또는 (N, D) 시계열 데이터
        fps: 프레임 레이트 (None이면 프레임 단위)

    Returns:
        일관성 지수 (0-1, 1이 가장 일관적)
    """
    if not isinstance(sequence, np.ndarray):
        raise TypeError("sequence는 numpy.ndarray여야 합니다.")

    seq = sequence.astype(np.float64, copy=False)

    if seq.shape[0] < 3:
        return 1.0

    # 프레임 간 변화량 (1차 차분)
    if seq.ndim == 1:
        diffs = np.abs(np.diff(seq))
    else:
        diffs = np.sqrt(np.sum(np.diff(seq, axis=0) ** 2, axis=1))

    if fps is not None and fps > 0:
        diffs *= fps  # 속도로 변환

    mean_diff = float(np.mean(diffs))
    if mean_diff < _EPSILON:
        return 1.0  # 변화 없음 = 완벽한 일관성

    cv = float(np.std(diffs, ddof=1) / mean_diff) if len(diffs) > 1 else 0.0
    return 1.0 / (1.0 + cv)


# =============================================================================
# 이상값 검출 (Outlier Detection)
# =============================================================================

def detect_outliers_zscore(
    values: NDArray,
    threshold: float = DEFAULT_OUTLIER_THRESHOLD,
) -> OutlierResult:
    """
    Z-score 기반 이상값 검출.

    |z_i| > threshold인 데이터를 이상값으로 판정합니다.
    정규분포에 가까운 데이터에 적합합니다.

    Args:
        values: 데이터 배열
        threshold: Z-score 임계값 (기본 3.0)

    Returns:
        OutlierResult 객체
    """
    arr = _validate_values(values, "values")

    mean = np.mean(arr)
    std = np.std(arr, ddof=1) if len(arr) > 1 else _EPSILON

    if std < _EPSILON:
        # 모든 값이 동일 → 이상값 없음
        return OutlierResult(
            is_outlier=np.zeros(len(arr), dtype=bool),
            outlier_indices=np.array([], dtype=np.int64),
            scores=np.zeros(len(arr), dtype=np.float64),
            threshold=threshold,
            n_outliers=0,
            method="z_score",
        )

    scores = np.abs((arr - mean) / std)
    is_outlier = scores > threshold
    indices = np.where(is_outlier)[0]

    return OutlierResult(
        is_outlier=is_outlier,
        outlier_indices=indices,
        scores=scores,
        threshold=threshold,
        n_outliers=int(np.sum(is_outlier)),
        method="z_score",
    )


def detect_outliers_iqr(
    values: NDArray,
    multiplier: float = DEFAULT_IQR_MULTIPLIER,
) -> OutlierResult:
    """
    IQR (사분위 범위) 기반 이상값 검출.

    Tukey 울타리: [Q1 - k*IQR, Q3 + k*IQR] 범위를 벗어나면 이상값.
    비정규분포에도 로버스트하며, 기본 k=1.5 (일반 이상값).

    Args:
        values: 데이터 배열
        multiplier: IQR 배수 (기본 1.5, 극단값은 3.0)

    Returns:
        OutlierResult 객체
    """
    arr = _validate_values(values, "values")

    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    if iqr < _EPSILON:
        # IQR이 0이면 중앙값과 다른 모든 값이 이상값
        median = float(np.median(arr))
        is_outlier = np.abs(arr - median) > _EPSILON
        indices = np.where(is_outlier)[0]
        scores = np.abs(arr - median)
        return OutlierResult(
            is_outlier=is_outlier,
            outlier_indices=indices,
            scores=scores,
            threshold=multiplier,
            n_outliers=int(np.sum(is_outlier)),
            method="iqr",
        )

    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    is_outlier = (arr < lower_fence) | (arr > upper_fence)
    indices = np.where(is_outlier)[0]

    # 울타리까지의 정규화 거리를 점수로 사용
    scores = np.maximum(
        (lower_fence - arr) / iqr,
        (arr - upper_fence) / iqr,
    )
    scores = np.maximum(scores, 0.0)

    return OutlierResult(
        is_outlier=is_outlier,
        outlier_indices=indices,
        scores=scores,
        threshold=multiplier,
        n_outliers=int(np.sum(is_outlier)),
        method="iqr",
    )


def detect_outliers_mad(
    values: NDArray,
    threshold: float = 3.5,
) -> OutlierResult:
    """
    MAD (중앙절대편차) 기반 이상값 검출.

    수정 Z-score: M_i = 0.6745 * (x_i - median) / MAD
    |M_i| > threshold면 이상값.
    극단적 이상값에 대해 Z-score보다 로버스트합니다.

    Args:
        values: 데이터 배열
        threshold: 수정 Z-score 임계값 (기본 3.5, Iglewicz & Hoaglin 권장)

    Returns:
        OutlierResult 객체
    """
    arr = _validate_values(values, "values")

    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))

    if mad < _EPSILON:
        # MAD이 0이면 중앙값과 다른 값이 이상값
        is_outlier = np.abs(arr - median) > _EPSILON
        indices = np.where(is_outlier)[0]
        scores = np.abs(arr - median)
        return OutlierResult(
            is_outlier=is_outlier,
            outlier_indices=indices,
            scores=scores,
            threshold=threshold,
            n_outliers=int(np.sum(is_outlier)),
            method="mad",
        )

    # 0.6745 = 표준정규분포의 Q3 (MAD → σ 변환 상수)
    modified_z = 0.6745 * np.abs(arr - median) / mad
    is_outlier = modified_z > threshold
    indices = np.where(is_outlier)[0]

    return OutlierResult(
        is_outlier=is_outlier,
        outlier_indices=indices,
        scores=modified_z,
        threshold=threshold,
        n_outliers=int(np.sum(is_outlier)),
        method="mad",
    )


def filter_outliers(
    values: NDArray,
    method: OutlierMethod = OutlierMethod.IQR,
    **kwargs: float,
) -> NDArray:
    """
    이상값을 제거한 정제 데이터 반환.

    Args:
        values: 데이터 배열
        method: 이상값 검출 방법
        **kwargs: 각 방법의 추가 인자 (threshold, multiplier)

    Returns:
        이상값이 제거된 1D 배열
    """
    arr = _validate_values(values, "values")

    if method == OutlierMethod.Z_SCORE:
        result = detect_outliers_zscore(arr, **kwargs)
    elif method == OutlierMethod.IQR:
        result = detect_outliers_iqr(arr, **kwargs)
    elif method == OutlierMethod.MAD or method == OutlierMethod.MODIFIED_Z_SCORE:
        result = detect_outliers_mad(arr, **kwargs)
    else:
        result = detect_outliers_iqr(arr, **kwargs)

    return arr[~result.is_outlier]


# =============================================================================
# 가중 집계 (Weighted Aggregation)
# =============================================================================

def weighted_score(
    scores: NDArray,
    weights: NDArray,
) -> float:
    """
    가중 점수 계산 (가중 합 / 가중치 합).

    슈팅 폼 평가, 동작 차원별 평가 등에서 사용됩니다.

    Args:
        scores: 점수 배열
        weights: 가중치 배열 (scores와 동일 길이)

    Returns:
        가중 점수
    """
    s = _validate_values(scores, "scores")
    w = _validate_values(weights, "weights")

    if len(s) != len(w):
        raise ValueError(
            f"scores({len(s)})와 weights({len(w)})의 길이가 다릅니다."
        )

    total_weight = float(np.sum(w))
    if total_weight < _EPSILON:
        logger.warning("가중치 합이 0에 가깝습니다.")
        return float(np.mean(s))

    return float(np.sum(s * w) / total_weight)


def normalize_weights(weights: NDArray) -> NDArray:
    """
    가중치를 합 = 1로 정규화.

    Args:
        weights: 가중치 배열 (양수)

    Returns:
        정규화된 가중치 배열 (합 = 1)
    """
    w = _validate_values(weights, "weights")

    total = float(np.sum(w))
    if total < _EPSILON:
        logger.warning("가중치 합이 0에 가까워 균등 가중치를 반환합니다.")
        return np.full(len(w), 1.0 / len(w), dtype=np.float64)

    return w / total


def trimmed_mean(
    values: NDArray,
    proportion: float = 0.1,
) -> float:
    """
    절사 평균 (Trimmed Mean) 계산.

    양쪽 극단값을 일정 비율만큼 제거한 후 평균을 계산합니다.
    이상값에 로버스트한 중심 경향 측정입니다.

    Args:
        values: 데이터 배열
        proportion: 각 쪽에서 제거할 비율 (0-0.5, 기본 10%)

    Returns:
        절사 평균
    """
    arr = _validate_values(values, "values")

    if proportion < 0 or proportion >= 0.5:
        raise ValueError(
            f"proportion은 [0, 0.5) 범위여야 합니다: {proportion}"
        )

    n = len(arr)
    trim_count = int(n * proportion)

    if trim_count == 0:
        return float(np.mean(arr))

    sorted_arr = np.sort(arr)
    trimmed = sorted_arr[trim_count:n - trim_count]

    if len(trimmed) == 0:
        return float(np.median(arr))

    return float(np.mean(trimmed))


def bayesian_average(
    values: NDArray,
    prior_mean: float,
    prior_weight: float = 1.0,
) -> float:
    """
    베이지안 평균 계산.

    사전 평균(prior_mean)과 관측 데이터의 가중 평균으로,
    데이터가 적을수록 사전 평균에 가깝고,
    많을수록 관측 평균에 수렴합니다.

    bayesian_avg = (prior_weight * prior_mean + n * sample_mean) / (prior_weight + n)

    선수 평가, 시즌 통계 등 데이터 부족 시 안정적인 추정에 유용합니다.

    Args:
        values: 관측 데이터 배열
        prior_mean: 사전 평균 (예: 리그 평균)
        prior_weight: 사전 가중치 (사전 지식의 강도)

    Returns:
        베이지안 평균
    """
    arr = _validate_values(values, "values")

    if prior_weight < 0:
        raise ValueError(f"prior_weight는 음수일 수 없습니다: {prior_weight}")

    n = len(arr)
    sample_mean = float(np.mean(arr))

    return (prior_weight * prior_mean + n * sample_mean) / (prior_weight + n)


def harmonic_mean(values: NDArray) -> float:
    """
    조화 평균 계산.

    H = n / Σ(1/xi)

    비율, 속도, 효율성 등의 평균에 적합합니다.
    모든 값이 양수여야 합니다.

    Args:
        values: 양수 데이터 배열

    Returns:
        조화 평균
    """
    arr = _validate_values(values, "values")

    if np.any(arr <= 0):
        raise ValueError("조화 평균은 모든 값이 양수여야 합니다.")

    return float(len(arr) / np.sum(1.0 / arr))


# =============================================================================
# 순위/백분위 (Ranking/Percentile)
# =============================================================================

def percentile_rank(value: float, data: NDArray) -> float:
    """
    데이터셋 내에서 값의 백분위 순위 계산.

    주어진 값보다 작거나 같은 데이터의 비율을 반환합니다.

    Args:
        value: 순위를 구할 값
        data: 참조 데이터셋

    Returns:
        백분위 순위 (0-100)
    """
    arr = _validate_values(data, "data")
    count_below = float(np.sum(arr <= value))
    return (count_below / len(arr)) * 100.0


def rank_values(
    values: NDArray,
    method: RankMethod = RankMethod.AVERAGE,
) -> NDArray:
    """
    데이터의 순위 산정.

    Args:
        values: 데이터 배열
        method: 동점 처리 방법

    Returns:
        순위 배열 (1-based)
    """
    arr = _validate_values(values, "values")
    n = len(arr)

    # 정렬된 인덱스
    sorted_indices = np.argsort(arr)
    ranks = np.empty(n, dtype=np.float64)

    if method == RankMethod.ORDINAL:
        ranks[sorted_indices] = np.arange(1, n + 1, dtype=np.float64)
        return ranks

    # 동점 처리
    sorted_arr = arr[sorted_indices]
    i = 0
    while i < n:
        j = i
        # 동점 그룹 찾기
        while j < n - 1 and np.isclose(sorted_arr[j], sorted_arr[j + 1]):
            j += 1

        # 동점 그룹의 순위 할당
        group_size = j - i + 1
        if method == RankMethod.AVERAGE:
            rank_val = (2 * i + group_size + 1) / 2.0
        elif method == RankMethod.MIN:
            rank_val = float(i + 1)
        elif method == RankMethod.MAX:
            rank_val = float(j + 1)
        elif method == RankMethod.DENSE:
            # dense 순위는 별도 로직
            rank_val = -1.0  # 아래에서 처리
        else:
            rank_val = (2 * i + group_size + 1) / 2.0

        for k in range(i, j + 1):
            ranks[sorted_indices[k]] = rank_val

        i = j + 1

    # DENSE 순위: 동점 후 다음 순위 = 현재 + 1
    if method == RankMethod.DENSE:
        sorted_arr = arr[sorted_indices]
        dense_rank = 1
        ranks[sorted_indices[0]] = 1.0
        for i in range(1, n):
            if not np.isclose(sorted_arr[i], sorted_arr[i - 1]):
                dense_rank += 1
            ranks[sorted_indices[i]] = float(dense_rank)

    return ranks


def standardize_scores(
    values: NDArray,
    target_mean: float = 50.0,
    target_std: float = 10.0,
) -> NDArray:
    """
    데이터를 목표 평균/표준편차로 표준화.

    T-score 변환: T = target_mean + target_std * z_score
    기본값(50, 10)은 T-score 표준입니다.

    Args:
        values: 데이터 배열
        target_mean: 목표 평균 (기본 50)
        target_std: 목표 표준편차 (기본 10)

    Returns:
        표준화된 점수 배열
    """
    arr = _validate_values(values, "values")

    mean = np.mean(arr)
    std = np.std(arr, ddof=1) if len(arr) > 1 else _EPSILON

    if std < _EPSILON:
        return np.full(len(arr), target_mean, dtype=np.float64)

    z_scores = (arr - mean) / std
    return target_mean + target_std * z_scores


# =============================================================================
# 신뢰구간 (Confidence Intervals)
# =============================================================================

def confidence_interval_z(
    values: NDArray,
    confidence: float = DEFAULT_CONFIDENCE_LEVEL,
) -> ConfidenceInterval:
    """
    z-기반 신뢰구간 계산.

    대표본(n >= 30) 또는 모분산 알려진 경우에 적합합니다.
    CI = mean ± z * (σ / √n)

    Args:
        values: 데이터 배열
        confidence: 신뢰 수준 (기본 0.95)

    Returns:
        ConfidenceInterval 객체
    """
    arr = _validate_values(values, "values")
    n = len(arr)

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    z = _z_critical(confidence)
    se = std / math.sqrt(n) if n > 0 else 0.0
    moe = z * se

    return ConfidenceInterval(
        lower=mean - moe,
        upper=mean + moe,
        confidence_level=confidence,
        sample_size=n,
        mean=mean,
        margin_of_error=moe,
    )


def margin_of_error(
    std: float,
    n: int,
    confidence: float = DEFAULT_CONFIDENCE_LEVEL,
) -> float:
    """
    오차 한계 계산.

    MOE = z * (σ / √n)

    Args:
        std: 표준편차
        n: 표본 크기
        confidence: 신뢰 수준

    Returns:
        오차 한계
    """
    if n <= 0:
        raise ValueError(f"표본 크기는 양수여야 합니다: {n}")
    if std < 0:
        raise ValueError(f"표준편차는 음수일 수 없습니다: {std}")

    z = _z_critical(confidence)
    return z * std / math.sqrt(n)


# =============================================================================
# 신뢰도 메트릭 (Reliability Metrics)
# =============================================================================

def icc_two_way(raters_data: NDArray) -> ICCResult:
    """
    ICC(2,1) 계산 — 이원 혼합 모형, 절대 합치도, 단일 측정.

    여러 평가자(또는 측정)의 일관성을 측정합니다.
    ICC 값 해석:
    - < 0.50: 나쁨 (poor)
    - 0.50-0.75: 보통 (moderate)
    - 0.75-0.90: 좋음 (good)
    - > 0.90: 우수 (excellent)

    ANOVA 기반 공식:
    ICC(2,1) = (BMS - EMS) / (BMS + (k-1)*EMS + k*(JMS - EMS)/n)

    Args:
        raters_data: (n_subjects, n_raters) 평가 데이터 행렬

    Returns:
        ICCResult 객체
    """
    if not isinstance(raters_data, np.ndarray):
        raise TypeError("raters_data는 numpy.ndarray여야 합니다.")
    if raters_data.ndim != 2:
        raise ValueError("raters_data는 2차원(subjects × raters)이어야 합니다.")

    data = raters_data.astype(np.float64, copy=False)
    n, k = data.shape  # n: 피험자, k: 평가자

    if n < 2:
        raise ValueError(f"최소 2명의 피험자가 필요합니다: {n}")
    if k < 2:
        raise ValueError(f"최소 2명의 평가자가 필요합니다: {k}")

    # 전체 평균
    grand_mean = np.mean(data)

    # 피험자별 평균, 평가자별 평균
    subject_means = np.mean(data, axis=1)
    rater_means = np.mean(data, axis=0)

    # 제곱합 (Sum of Squares)
    ss_between = k * np.sum((subject_means - grand_mean) ** 2)  # SSr (행)
    ss_raters = n * np.sum((rater_means - grand_mean) ** 2)     # SSc (열)
    ss_total = np.sum((data - grand_mean) ** 2)
    ss_error = ss_total - ss_between - ss_raters                 # SSe (잔차)

    # 평균 제곱 (Mean Squares)
    df_between = n - 1
    df_raters = k - 1
    df_error = (n - 1) * (k - 1)

    bms = ss_between / df_between if df_between > 0 else 0.0   # BMS
    jms = ss_raters / df_raters if df_raters > 0 else 0.0      # JMS (평가자)
    ems = ss_error / df_error if df_error > 0 else _EPSILON     # EMS (잔차)

    # ICC(2,1) 공식
    denom = bms + (k - 1) * ems + k * (jms - ems) / n
    if abs(denom) < _EPSILON:
        icc_value = 0.0
    else:
        icc_value = (bms - ems) / denom

    # F-통계량
    f_value = bms / ems if ems > _EPSILON else 0.0

    return ICCResult(
        value=float(icc_value),
        f_value=float(f_value),
        df_between=df_between,
        df_within=df_error,
        n_subjects=n,
        n_raters=k,
    )


def cronbach_alpha(items_scores: NDArray) -> float:
    """
    Cronbach's α (내적 일관성) 계산.

    항목들이 동일한 구성 개념을 측정하는지 평가합니다.
    α = (k/(k-1)) * (1 - Σ(항목 분산) / 전체 분산)

    해석:
    - < 0.60: 불충분
    - 0.60-0.70: 의문
    - 0.70-0.80: 수용 가능
    - 0.80-0.90: 좋음
    - > 0.90: 우수

    Args:
        items_scores: (n_observations, n_items) 항목별 점수 행렬

    Returns:
        Cronbach's α 값
    """
    if not isinstance(items_scores, np.ndarray):
        raise TypeError("items_scores는 numpy.ndarray여야 합니다.")
    if items_scores.ndim != 2:
        raise ValueError("items_scores는 2차원(observations × items)이어야 합니다.")

    data = items_scores.astype(np.float64, copy=False)
    n, k = data.shape

    if k < 2:
        raise ValueError(f"최소 2개 항목이 필요합니다: {k}")
    if n < 2:
        raise ValueError(f"최소 2개 관측이 필요합니다: {n}")

    # 각 항목의 분산
    item_variances = np.var(data, axis=0, ddof=1)
    sum_item_var = float(np.sum(item_variances))

    # 전체 합산 점수의 분산
    total_scores = np.sum(data, axis=1)
    total_var = float(np.var(total_scores, ddof=1))

    if total_var < _EPSILON:
        return 0.0

    alpha = (k / (k - 1)) * (1.0 - sum_item_var / total_var)
    return float(alpha)


def cohens_d(group_a: NDArray, group_b: NDArray) -> float:
    """
    Cohen's d (효과 크기) 계산.

    두 그룹 간 차이의 실질적 크기를 표준편차 단위로 나타냅니다.
    d = (mean_a - mean_b) / pooled_std

    해석:
    - |d| < 0.2: 무시 가능
    - 0.2 ≤ |d| < 0.5: 작은 효과
    - 0.5 ≤ |d| < 0.8: 중간 효과
    - |d| ≥ 0.8: 큰 효과

    훈련 전/후 비교, 그룹 간 성능 비교에 사용됩니다.

    Args:
        group_a: 그룹 A 데이터
        group_b: 그룹 B 데이터

    Returns:
        Cohen's d 값
    """
    a = _validate_values(group_a, "group_a")
    b = _validate_values(group_b, "group_b")

    n_a = len(a)
    n_b = len(b)
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))

    var_a = float(np.var(a, ddof=1)) if n_a > 1 else 0.0
    var_b = float(np.var(b, ddof=1)) if n_b > 1 else 0.0

    # 합동 표준편차 (pooled std)
    denom = n_a + n_b - 2
    if denom <= 0:
        return 0.0

    pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / denom
    pooled_std = math.sqrt(pooled_var)

    if pooled_std < _EPSILON:
        return 0.0

    return (mean_a - mean_b) / pooled_std


# =============================================================================
# 러닝/온라인 통계 (Running/Online Statistics)
# =============================================================================

class RunningStatistics:
    """
    Welford 온라인 알고리즘 기반 러닝 통계.

    한 번에 하나의 값을 추가하면서 평균, 분산, 표준편차를
    O(1)에 업데이트합니다. 메모리 사용량이 일정합니다.

    프레임 단위 실시간 통계 수집에 적합합니다.

    사용 예시:
        >>> stats = RunningStatistics()
        >>> for val in [1.0, 2.0, 3.0, 4.0, 5.0]:
        ...     stats.update(val)
        >>> stats.get_mean()
        3.0
    """

    __slots__ = ("_count", "_mean", "_m2", "_min", "_max")

    def __init__(self) -> None:
        self._count: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0
        self._min: float = float("inf")
        self._max: float = float("-inf")

    def update(self, value: float) -> None:
        """
        새 값을 추가하고 통계를 업데이트.

        Welford 알고리즘: 수치 안정성이 높은 온라인 분산 계산.
        """
        self._count += 1
        delta = value - self._mean
        self._mean += delta / self._count
        delta2 = value - self._mean
        self._m2 += delta * delta2

        if value < self._min:
            self._min = value
        if value > self._max:
            self._max = value

    def get_mean(self) -> float:
        """현재 평균."""
        return self._mean if self._count > 0 else 0.0

    def get_variance(self, ddof: int = 1) -> float:
        """현재 분산 (ddof: 자유도 보정, 기본 1=비편향)."""
        if self._count < 2:
            return 0.0
        return self._m2 / (self._count - ddof)

    def get_std(self, ddof: int = 1) -> float:
        """현재 표준편차."""
        return math.sqrt(self.get_variance(ddof))

    def get_count(self) -> int:
        """현재 데이터 수."""
        return self._count

    def get_min(self) -> float:
        """현재 최솟값."""
        return self._min if self._count > 0 else 0.0

    def get_max(self) -> float:
        """현재 최댓값."""
        return self._max if self._count > 0 else 0.0

    def get_cv(self) -> float:
        """현재 변동계수."""
        mean = self.get_mean()
        if abs(mean) < _EPSILON:
            return 0.0
        return self.get_std() / abs(mean)

    def reset(self) -> None:
        """통계 초기화."""
        self._count = 0
        self._mean = 0.0
        self._m2 = 0.0
        self._min = float("inf")
        self._max = float("-inf")

    def merge(self, other: RunningStatistics) -> None:
        """
        두 RunningStatistics를 병합 (Chan 알고리즘).

        병렬 처리 결과를 합칠 때 사용합니다.
        """
        if other._count == 0:
            return
        if self._count == 0:
            self._count = other._count
            self._mean = other._mean
            self._m2 = other._m2
            self._min = other._min
            self._max = other._max
            return

        combined_count = self._count + other._count
        delta = other._mean - self._mean
        combined_mean = (
            (self._count * self._mean + other._count * other._mean)
            / combined_count
        )
        combined_m2 = (
            self._m2 + other._m2
            + delta * delta * self._count * other._count / combined_count
        )

        self._count = combined_count
        self._mean = combined_mean
        self._m2 = combined_m2
        self._min = min(self._min, other._min)
        self._max = max(self._max, other._max)

    def __repr__(self) -> str:
        return (
            f"RunningStatistics(n={self._count}, "
            f"mean={self.get_mean():.4f}, "
            f"std={self.get_std():.4f})"
        )


def running_variance(
    values: NDArray,
    window_size: int,
) -> NDArray:
    """
    슬라이딩 윈도우 기반 러닝 분산.

    각 윈도우 내의 분산을 계산합니다.

    Args:
        values: (N,) 1D 배열
        window_size: 윈도우 크기

    Returns:
        (N - window_size + 1,) 분산 배열
    """
    arr = _validate_values(values, "values")

    if arr.ndim != 1:
        raise ValueError("running_variance는 1D 배열만 지원합니다.")

    n = len(arr)
    if window_size <= 0 or window_size > n:
        raise ValueError(
            f"window_size({window_size})는 (0, {n}] 범위여야 합니다."
        )

    num_windows = n - window_size + 1
    result = np.empty(num_windows, dtype=np.float64)

    # 효율적 구현: 누적합 기반 O(N)
    cumsum = np.cumsum(arr)
    cumsum2 = np.cumsum(arr ** 2)

    # 0 삽입으로 인덱스 간편화
    cumsum = np.insert(cumsum, 0, 0.0)
    cumsum2 = np.insert(cumsum2, 0, 0.0)

    for i in range(num_windows):
        s = cumsum[i + window_size] - cumsum[i]
        s2 = cumsum2[i + window_size] - cumsum2[i]
        mean = s / window_size
        var = s2 / window_size - mean * mean
        # 비편향 분산 보정
        result[i] = var * window_size / (window_size - 1) if window_size > 1 else 0.0

    return result


def exponential_decay_average(
    values: NDArray,
    decay_rate: float,
) -> NDArray:
    """
    지수 감쇠 평균 계산.

    최근 값에 더 높은 가중치를 부여하는 이동 평균입니다.
    EDA[i] = (1 - decay_rate) * EDA[i-1] + decay_rate * values[i]

    Args:
        values: (N,) 데이터 배열
        decay_rate: 감쇠율 (0-1, 1에 가까울수록 최근 값 중시)

    Returns:
        (N,) 지수 감쇠 평균 배열
    """
    arr = _validate_values(values, "values")

    if decay_rate <= 0 or decay_rate > 1:
        raise ValueError(
            f"decay_rate는 (0, 1] 범위여야 합니다: {decay_rate}"
        )

    n = len(arr)
    result = np.empty(n, dtype=np.float64)
    result[0] = arr[0]

    for i in range(1, n):
        result[i] = (1.0 - decay_rate) * result[i - 1] + decay_rate * arr[i]

    return result


# =============================================================================
# 배치 연산 (Batch Operations)
# =============================================================================

def batch_distribution_stats(
    datasets: list[NDArray],
) -> list[DistributionStats]:
    """
    여러 데이터셋의 분포 통계를 일괄 계산.

    Args:
        datasets: 데이터 배열 리스트

    Returns:
        DistributionStats 리스트
    """
    if not datasets:
        return []

    if len(datasets) > _MAX_BATCH_SIZE:
        logger.warning(
            f"배치 크기({len(datasets)})가 최대치({_MAX_BATCH_SIZE})를 초과합니다. "
            f"처음 {_MAX_BATCH_SIZE}개만 처리합니다."
        )
        datasets = datasets[:_MAX_BATCH_SIZE]

    return [calculate_distribution_stats(d) for d in datasets]


# =============================================================================
# Export 목록
# =============================================================================

__all__ = [
    # =========================================================================
    # 상수
    # =========================================================================
    "DEFAULT_CONFIDENCE_LEVEL",
    "Z_CRITICAL_95",
    "Z_CRITICAL_99",
    "DEFAULT_OUTLIER_THRESHOLD",
    "DEFAULT_IQR_MULTIPLIER",
    # =========================================================================
    # Enum
    # =========================================================================
    "OutlierMethod",
    "RankMethod",
    # =========================================================================
    # 데이터 클래스
    # =========================================================================
    "DistributionStats",
    "ConfidenceInterval",
    "OutlierResult",
    "RankingResult",
    "ICCResult",
    # =========================================================================
    # 클래스
    # =========================================================================
    "RunningStatistics",
    # =========================================================================
    # 분포 분석
    # =========================================================================
    "calculate_distribution_stats",
    "calculate_skewness",
    "calculate_kurtosis",
    "z_to_percentile",
    "percentile_to_z",
    # =========================================================================
    # 변동/일관성
    # =========================================================================
    "coefficient_of_variation",
    "consistency_score",
    "temporal_consistency_index",
    # =========================================================================
    # 이상값 검출
    # =========================================================================
    "detect_outliers_zscore",
    "detect_outliers_iqr",
    "detect_outliers_mad",
    "filter_outliers",
    # =========================================================================
    # 가중 집계
    # =========================================================================
    "weighted_score",
    "normalize_weights",
    "trimmed_mean",
    "bayesian_average",
    "harmonic_mean",
    # =========================================================================
    # 순위/백분위
    # =========================================================================
    "percentile_rank",
    "rank_values",
    "standardize_scores",
    # =========================================================================
    # 신뢰구간
    # =========================================================================
    "confidence_interval_z",
    "margin_of_error",
    # =========================================================================
    # 신뢰도 메트릭
    # =========================================================================
    "icc_two_way",
    "cronbach_alpha",
    "cohens_d",
    # =========================================================================
    # 러닝/온라인 통계
    # =========================================================================
    "running_variance",
    "exponential_decay_average",
    # =========================================================================
    # 배치 연산
    # =========================================================================
    "batch_distribution_stats",
]

__version__ = "1.0.0"
__author__ = "SPOIN_COURTVIEW"
