# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: heatmap_utils.py
설명: 히트맵 처리 및 키포인트 정밀화 유틸리티
      - 히트맵 피크 검출 (NMS 기반, 서브픽셀 정밀화)
      - 가우시안 히트맵 생성 (학습 타겟)
      - 히트맵 → 스켈레톤 변환
      - 다중 인스턴스 히트맵 디코딩
      - 히트맵 품질 메트릭 (선명도, SNR)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - 2D 히트맵 피크 검출 (NMS + 서브픽셀 정제)
    - 가우시안 커널 기반 히트맵 생성 (학습 타겟 제작)
    - 히트맵 앙상블/평균 (다중 스케일, 플립 증강)
    - COCO 17 키포인트 디코딩 (포즈 추정 후처리)
    - 히트맵 SNR, 선명도, 피크-평균 비율 메트릭
    - 순수 NumPy + OpenCV 구현

사용 예시:
    >>> from utils.heatmap_utils import (
    ...     extract_peaks, generate_gaussian_heatmap,
    ...     decode_heatmaps_to_skeleton, HeatmapConfig,
    ... )
    >>> import numpy as np
    >>> heatmap = np.random.rand(64, 48).astype(np.float32)
    >>> peaks = extract_peaks(heatmap, threshold=0.5)
    >>> len(peaks) >= 0
    True
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import math
from dataclasses import dataclass
from enum import Enum, unique

# === 서드파티 라이브러리 ===
import cv2
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

# 피크 검출 기본 임계값
DEFAULT_PEAK_THRESHOLD: float = 0.3

# 가우시안 시그마 기본값
DEFAULT_GAUSSIAN_SIGMA: float = 2.0

# NMS 커널 기본 크기 (홀수)
DEFAULT_NMS_KERNEL_SIZE: int = 3

# 서브픽셀 정밀화 인접 반경
_SUBPIXEL_RADIUS: int = 1

# 최대 히트맵 해상도 (메모리 보호)
_MAX_HEATMAP_SIZE: int = 512

# 최대 키포인트/피크 수
_MAX_PEAKS_PER_MAP: int = 100

# 가우시안 커널 트렁크 팩터 (sigma의 배수)
_GAUSSIAN_TRUNCATE: float = 3.0

# COCO 키포인트 수
COCO_NUM_KEYPOINTS: int = 17

# COCO 키포인트 이름 (순서 보장)
COCO_KEYPOINT_NAMES: tuple[str, ...] = (
    "nose",
    "left_eye", "right_eye",
    "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
)

# COCO 스켈레톤 연결 (인덱스 쌍)
COCO_SKELETON_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (0, 2),       # 코 → 눈
    (1, 3), (2, 4),       # 눈 → 귀
    (5, 6),                # 어깨-어깨
    (5, 7), (7, 9),       # 좌: 어깨→팔꿈치→손목
    (6, 8), (8, 10),      # 우: 어깨→팔꿈치→손목
    (11, 12),              # 힙-힙
    (5, 11), (6, 12),     # 어깨→힙
    (11, 13), (13, 15),   # 좌: 힙→무릎→발목
    (12, 14), (14, 16),   # 우: 힙→무릎→발목
)


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class SubpixelMethod(Enum):
    """서브픽셀 정밀화 방법."""

    NONE = "none"                   # 정수 좌표만
    QUADRATIC = "quadratic"         # 2차 다항식 피팅
    GAUSSIAN_LOG = "gaussian_log"   # 가우시안 로그 피팅


@unique
class HeatmapAggregation(Enum):
    """히트맵 앙상블 집계 방법."""

    MEAN = "mean"       # 평균
    MAX = "max"         # 최댓값
    WEIGHTED = "weighted"  # 가중 평균


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class HeatmapConfig:
    """
    히트맵 처리 설정.

    Attributes:
        peak_threshold: 피크 검출 임계값 (0~1)
        nms_kernel_size: NMS 커널 크기 (홀수)
        gaussian_sigma: 가우시안 시그마
        subpixel_method: 서브픽셀 정밀화 방법
        max_peaks: 히트맵 당 최대 피크 수
    """

    peak_threshold: float = DEFAULT_PEAK_THRESHOLD
    nms_kernel_size: int = DEFAULT_NMS_KERNEL_SIZE
    gaussian_sigma: float = DEFAULT_GAUSSIAN_SIGMA
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC
    max_peaks: int = _MAX_PEAKS_PER_MAP

    def __repr__(self) -> str:
        return (
            f"HeatmapConfig(threshold={self.peak_threshold:.3f}, "
            f"nms_k={self.nms_kernel_size}, sigma={self.gaussian_sigma:.2f}, "
            f"subpixel={self.subpixel_method.value})"
        )


@dataclass(slots=True)
class PeakInfo:
    """
    히트맵 피크 정보.

    Attributes:
        x: x좌표 (서브픽셀 정밀)
        y: y좌표 (서브픽셀 정밀)
        score: 피크 값 (신뢰도)
        channel: 히트맵 채널 인덱스
    """

    x: float
    y: float
    score: float
    channel: int = 0

    def __repr__(self) -> str:
        return (
            f"PeakInfo(x={self.x:.2f}, y={self.y:.2f}, "
            f"score={self.score:.4f}, ch={self.channel})"
        )


@dataclass(slots=True)
class SkeletonResult:
    """
    스켈레톤 디코딩 결과.

    Attributes:
        keypoints: 키포인트 좌표 (K×2)
        scores: 각 키포인트 신뢰도 (K,)
        num_valid: 유효 키포인트 수 (score > threshold)
        mean_score: 평균 신뢰도
    """

    keypoints: NDArray[np.float64]
    scores: NDArray[np.float64]
    num_valid: int
    mean_score: float

    def __repr__(self) -> str:
        return (
            f"SkeletonResult(valid={self.num_valid}/{len(self.scores)}, "
            f"mean_score={self.mean_score:.4f})"
        )


@dataclass(slots=True)
class HeatmapQuality:
    """
    히트맵 품질 메트릭.

    Attributes:
        sharpness: 선명도 (라플라시안 분산)
        snr: 신호대잡음비 (피크/배경)
        peak_mean_ratio: 피크-평균 비율
        entropy: 정보 엔트로피
        num_peaks: 검출된 피크 수
    """

    sharpness: float
    snr: float
    peak_mean_ratio: float
    entropy: float
    num_peaks: int

    def __repr__(self) -> str:
        return (
            f"HeatmapQuality(sharpness={self.sharpness:.2f}, "
            f"snr={self.snr:.2f}dB, peaks={self.num_peaks})"
        )


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _nms_2d(
    heatmap: NDArray[np.float32],
    kernel_size: int,
) -> NDArray[np.float32]:
    """2D Non-Maximum Suppression (최대 풀링 기반)."""
    if kernel_size % 2 == 0:
        kernel_size += 1

    pad = kernel_size // 2
    max_pool = cv2.dilate(
        heatmap,
        cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size)),
    )

    # 로컬 최대값인 위치만 유지
    suppressed = np.where(heatmap >= max_pool, heatmap, 0.0).astype(np.float32)
    return suppressed


def _refine_subpixel_quadratic(
    heatmap: NDArray[np.float32],
    y_int: int,
    x_int: int,
) -> tuple[float, float]:
    """2차 다항식 피팅으로 서브픽셀 좌표 정밀화."""
    h, w = heatmap.shape

    # x축 정밀화
    if 0 < x_int < w - 1:
        left = float(heatmap[y_int, x_int - 1])
        center = float(heatmap[y_int, x_int])
        right = float(heatmap[y_int, x_int + 1])
        denom = 2.0 * (2.0 * center - left - right)
        if abs(denom) > _EPSILON:
            dx = (right - left) / denom
            dx = max(-0.5, min(0.5, dx))
        else:
            dx = 0.0
    else:
        dx = 0.0

    # y축 정밀화
    if 0 < y_int < h - 1:
        top = float(heatmap[y_int - 1, x_int])
        center = float(heatmap[y_int, x_int])
        bottom = float(heatmap[y_int + 1, x_int])
        denom = 2.0 * (2.0 * center - top - bottom)
        if abs(denom) > _EPSILON:
            dy = (bottom - top) / denom
            dy = max(-0.5, min(0.5, dy))
        else:
            dy = 0.0
    else:
        dy = 0.0

    return x_int + dx, y_int + dy


def _refine_subpixel_gaussian_log(
    heatmap: NDArray[np.float32],
    y_int: int,
    x_int: int,
) -> tuple[float, float]:
    """가우시안 로그 피팅으로 서브픽셀 좌표 정밀화."""
    h, w = heatmap.shape

    # x축 정밀화
    if 0 < x_int < w - 1:
        left = max(float(heatmap[y_int, x_int - 1]), _EPSILON)
        center = max(float(heatmap[y_int, x_int]), _EPSILON)
        right = max(float(heatmap[y_int, x_int + 1]), _EPSILON)

        log_left = math.log(left)
        log_center = math.log(center)
        log_right = math.log(right)

        denom = 2.0 * (2.0 * log_center - log_left - log_right)
        if abs(denom) > _EPSILON:
            dx = (log_right - log_left) / denom
            dx = max(-0.5, min(0.5, dx))
        else:
            dx = 0.0
    else:
        dx = 0.0

    # y축 정밀화
    if 0 < y_int < h - 1:
        top = max(float(heatmap[y_int - 1, x_int]), _EPSILON)
        center = max(float(heatmap[y_int, x_int]), _EPSILON)
        bottom = max(float(heatmap[y_int + 1, x_int]), _EPSILON)

        log_top = math.log(top)
        log_center = math.log(center)
        log_bottom = math.log(bottom)

        denom = 2.0 * (2.0 * log_center - log_top - log_bottom)
        if abs(denom) > _EPSILON:
            dy = (log_bottom - log_top) / denom
            dy = max(-0.5, min(0.5, dy))
        else:
            dy = 0.0
    else:
        dy = 0.0

    return x_int + dx, y_int + dy


def _refine_peak(
    heatmap: NDArray[np.float32],
    y_int: int,
    x_int: int,
    method: SubpixelMethod,
) -> tuple[float, float]:
    """서브픽셀 정밀화 디스패치."""
    if method == SubpixelMethod.NONE:
        return float(x_int), float(y_int)
    elif method == SubpixelMethod.QUADRATIC:
        return _refine_subpixel_quadratic(heatmap, y_int, x_int)
    elif method == SubpixelMethod.GAUSSIAN_LOG:
        return _refine_subpixel_gaussian_log(heatmap, y_int, x_int)
    return float(x_int), float(y_int)


# =============================================================================
# 피크 검출
# =============================================================================

def extract_peaks(
    heatmap: NDArray[np.float32],
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    nms_kernel_size: int = DEFAULT_NMS_KERNEL_SIZE,
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC,
    max_peaks: int = _MAX_PEAKS_PER_MAP,
    channel: int = 0,
) -> list[PeakInfo]:
    """
    2D 히트맵에서 피크 검출.

    NMS → 임계값 필터 → 서브픽셀 정밀화 → 점수 정렬

    Args:
        heatmap: 2D 히트맵 (H×W), 값 범위 [0, 1]
        threshold: 최소 피크 값
        nms_kernel_size: NMS 커널 크기
        subpixel_method: 서브픽셀 정밀화 방법
        max_peaks: 최대 피크 수
        channel: 채널 인덱스 (다중 히트맵에서 식별용)

    Returns:
        PeakInfo 목록 (점수 내림차순)
    """
    if heatmap.ndim != 2:
        raise ValueError(f"히트맵은 2D여야 합니다: ndim={heatmap.ndim}")

    hm = heatmap.astype(np.float32)

    # NMS 적용
    nms_map = _nms_2d(hm, nms_kernel_size)

    # 임계값 필터
    peaks_mask = nms_map >= threshold
    ys, xs = np.where(peaks_mask)

    if len(ys) == 0:
        return []

    # 점수 기준 내림차순 정렬
    scores = nms_map[ys, xs]
    order = np.argsort(-scores)

    # 최대 피크 수 제한
    n = min(len(order), max_peaks)
    order = order[:n]

    peaks: list[PeakInfo] = []
    for idx in order:
        y_int = int(ys[idx])
        x_int = int(xs[idx])
        score = float(scores[idx])

        # 서브픽셀 정밀화
        x_sub, y_sub = _refine_peak(hm, y_int, x_int, subpixel_method)

        peaks.append(PeakInfo(x=x_sub, y=y_sub, score=score, channel=channel))

    return peaks


def extract_peaks_batch(
    heatmaps: NDArray[np.float32],
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    nms_kernel_size: int = DEFAULT_NMS_KERNEL_SIZE,
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC,
    max_peaks: int = _MAX_PEAKS_PER_MAP,
) -> list[list[PeakInfo]]:
    """
    다중 채널 히트맵 일괄 피크 검출.

    Args:
        heatmaps: 다중 히트맵 (C×H×W)
        threshold: 피크 임계값
        nms_kernel_size: NMS 커널 크기
        subpixel_method: 서브픽셀 정밀화 방법
        max_peaks: 채널 당 최대 피크 수

    Returns:
        채널별 PeakInfo 목록의 목록
    """
    if heatmaps.ndim != 3:
        raise ValueError(f"히트맵은 (C,H,W) 3D여야 합니다: shape={heatmaps.shape}")

    c = heatmaps.shape[0]
    results: list[list[PeakInfo]] = []

    for ch in range(c):
        peaks = extract_peaks(
            heatmaps[ch],
            threshold=threshold,
            nms_kernel_size=nms_kernel_size,
            subpixel_method=subpixel_method,
            max_peaks=max_peaks,
            channel=ch,
        )
        results.append(peaks)

    return results


def extract_top_peak(
    heatmap: NDArray[np.float32],
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC,
) -> PeakInfo | None:
    """
    히트맵에서 최고 점수 피크 1개 추출.

    Args:
        heatmap: 2D 히트맵 (H×W)
        subpixel_method: 서브픽셀 정밀화 방법

    Returns:
        최고 점수 PeakInfo 또는 None (빈 히트맵)
    """
    if heatmap.ndim != 2:
        raise ValueError(f"히트맵은 2D여야 합니다: ndim={heatmap.ndim}")

    hm = heatmap.astype(np.float32)
    flat_idx = np.argmax(hm)
    y_int = int(flat_idx // hm.shape[1])
    x_int = int(flat_idx % hm.shape[1])
    score = float(hm[y_int, x_int])

    if score < _EPSILON:
        return None

    x_sub, y_sub = _refine_peak(hm, y_int, x_int, subpixel_method)

    return PeakInfo(x=x_sub, y=y_sub, score=score, channel=0)


# =============================================================================
# 가우시안 히트맵 생성
# =============================================================================

def generate_gaussian_heatmap(
    height: int,
    width: int,
    center_x: float,
    center_y: float,
    sigma: float = DEFAULT_GAUSSIAN_SIGMA,
) -> NDArray[np.float32]:
    """
    2D 가우시안 히트맵 생성 (학습 타겟).

    G(x,y) = exp(-((x-cx)² + (y-cy)²) / (2·σ²))

    Args:
        height: 히트맵 높이
        width: 히트맵 너비
        center_x: 중심 x좌표
        center_y: 중심 y좌표
        sigma: 가우시안 표준편차

    Returns:
        가우시안 히트맵 (H×W), 값 범위 [0, 1]
    """
    if height <= 0 or width <= 0:
        raise ValueError(f"히트맵 크기는 양수여야 합니다: {height}×{width}")
    if height > _MAX_HEATMAP_SIZE or width > _MAX_HEATMAP_SIZE:
        raise ValueError(
            f"히트맵 크기 초과: {height}×{width} > {_MAX_HEATMAP_SIZE}×{_MAX_HEATMAP_SIZE}"
        )
    if sigma <= 0:
        raise ValueError(f"시그마는 양수여야 합니다: {sigma}")

    # 효율적 생성: 트렁크 반경 내부만 계산
    radius = int(math.ceil(_GAUSSIAN_TRUNCATE * sigma))

    # 정수 중심
    cx_int = int(round(center_x))
    cy_int = int(round(center_y))

    # 유효 범위 계산
    x_min = max(0, cx_int - radius)
    x_max = min(width, cx_int + radius + 1)
    y_min = max(0, cy_int - radius)
    y_max = min(height, cy_int + radius + 1)

    if x_min >= x_max or y_min >= y_max:
        return np.zeros((height, width), dtype=np.float32)

    # 좌표 그리드
    xs = np.arange(x_min, x_max, dtype=np.float64) - center_x
    ys = np.arange(y_min, y_max, dtype=np.float64) - center_y

    # 외적 (분리가능 가우시안)
    exp_x = np.exp(-xs * xs / (2.0 * sigma * sigma))
    exp_y = np.exp(-ys * ys / (2.0 * sigma * sigma))
    patch = np.outer(exp_y, exp_x).astype(np.float32)

    heatmap = np.zeros((height, width), dtype=np.float32)
    heatmap[y_min:y_max, x_min:x_max] = patch

    return heatmap


def generate_multi_keypoint_heatmap(
    height: int,
    width: int,
    keypoints: NDArray[np.float64],
    sigma: float = DEFAULT_GAUSSIAN_SIGMA,
) -> NDArray[np.float32]:
    """
    다중 키포인트 히트맵 생성 (C×H×W).

    Args:
        height: 히트맵 높이
        width: 히트맵 너비
        keypoints: 키포인트 좌표 (K×2) 또는 (K×3, [x, y, visibility])
        sigma: 가우시안 표준편차

    Returns:
        다중 채널 히트맵 (K×H×W)
    """
    k = keypoints.shape[0]
    heatmaps = np.zeros((k, height, width), dtype=np.float32)

    for i in range(k):
        x = float(keypoints[i, 0])
        y = float(keypoints[i, 1])

        # visibility 확인 (3열이 있으면)
        if keypoints.shape[1] >= 3 and keypoints[i, 2] <= 0:
            continue  # 비가시 키포인트 → 빈 히트맵

        # 범위 밖 검사
        if x < -sigma or x > width + sigma or y < -sigma or y > height + sigma:
            continue

        heatmaps[i] = generate_gaussian_heatmap(height, width, x, y, sigma)

    return heatmaps


# =============================================================================
# 히트맵 → 스켈레톤 디코딩
# =============================================================================

def decode_heatmaps_to_skeleton(
    heatmaps: NDArray[np.float32],
    output_size: tuple[int, int] | None = None,
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC,
) -> SkeletonResult:
    """
    다중 채널 히트맵 → 스켈레톤 좌표 변환.

    각 채널에서 최고 피크를 키포인트로 추출.

    Args:
        heatmaps: 포즈 히트맵 (K×H×W)
        output_size: 출력 좌표 스케일 (target_w, target_h) — None이면 히트맵 크기 그대로
        threshold: 최소 유효 신뢰도
        subpixel_method: 서브픽셀 정밀화 방법

    Returns:
        SkeletonResult
    """
    if heatmaps.ndim != 3:
        raise ValueError(f"히트맵은 (K,H,W) 3D여야 합니다: shape={heatmaps.shape}")

    k, hm_h, hm_w = heatmaps.shape
    keypoints = np.zeros((k, 2), dtype=np.float64)
    scores = np.zeros(k, dtype=np.float64)

    for ch in range(k):
        peak = extract_top_peak(heatmaps[ch], subpixel_method)
        if peak is not None:
            keypoints[ch, 0] = peak.x
            keypoints[ch, 1] = peak.y
            scores[ch] = peak.score

    # 출력 스케일 적용
    if output_size is not None:
        target_w, target_h = output_size
        scale_x = target_w / hm_w
        scale_y = target_h / hm_h
        keypoints[:, 0] *= scale_x
        keypoints[:, 1] *= scale_y

    num_valid = int(np.sum(scores >= threshold))
    valid_scores = scores[scores >= threshold]
    mean_score = float(np.mean(valid_scores)) if len(valid_scores) > 0 else 0.0

    return SkeletonResult(
        keypoints=keypoints,
        scores=scores,
        num_valid=num_valid,
        mean_score=mean_score,
    )


def decode_multi_person_heatmaps(
    heatmaps: NDArray[np.float32],
    max_persons: int = 10,
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    nms_kernel_size: int = DEFAULT_NMS_KERNEL_SIZE,
    subpixel_method: SubpixelMethod = SubpixelMethod.QUADRATIC,
) -> list[SkeletonResult]:
    """
    다중 인스턴스 히트맵 디코딩 (Bottom-up 방식).

    각 채널에서 다중 피크 → 가장 가까운 피크를 그룹핑.

    Args:
        heatmaps: 포즈 히트맵 (K×H×W)
        max_persons: 최대 인원 수
        threshold: 피크 임계값
        nms_kernel_size: NMS 커널 크기
        subpixel_method: 서브픽셀 정밀화 방법

    Returns:
        인원별 SkeletonResult 목록
    """
    if heatmaps.ndim != 3:
        raise ValueError(f"히트맵은 (K,H,W) 3D여야 합니다: shape={heatmaps.shape}")

    k = heatmaps.shape[0]

    # 모든 채널에서 피크 추출
    all_peaks = extract_peaks_batch(
        heatmaps, threshold, nms_kernel_size, subpixel_method, max_peaks=max_persons,
    )

    # 참조 채널 선택 (가장 많은 피크를 가진 채널)
    ref_ch = max(range(k), key=lambda c: len(all_peaks[c]))
    ref_peaks = all_peaks[ref_ch]

    if len(ref_peaks) == 0:
        return []

    # 각 참조 피크에 대해 가장 가까운 피크 그룹핑
    results: list[SkeletonResult] = []

    for ref_peak in ref_peaks[:max_persons]:
        keypoints = np.zeros((k, 2), dtype=np.float64)
        scores = np.zeros(k, dtype=np.float64)

        for ch in range(k):
            if ch == ref_ch:
                keypoints[ch] = [ref_peak.x, ref_peak.y]
                scores[ch] = ref_peak.score
                continue

            # 참조 피크에 가장 가까운 피크 선택
            best_peak: PeakInfo | None = None
            best_dist = float("inf")

            for peak in all_peaks[ch]:
                d = math.sqrt(
                    (peak.x - ref_peak.x) ** 2 + (peak.y - ref_peak.y) ** 2
                )
                if d < best_dist:
                    best_dist = d
                    best_peak = peak

            if best_peak is not None:
                keypoints[ch] = [best_peak.x, best_peak.y]
                scores[ch] = best_peak.score

        num_valid = int(np.sum(scores >= threshold))
        valid_scores = scores[scores >= threshold]
        mean_score = float(np.mean(valid_scores)) if len(valid_scores) > 0 else 0.0

        results.append(SkeletonResult(
            keypoints=keypoints,
            scores=scores,
            num_valid=num_valid,
            mean_score=mean_score,
        ))

    return results


# =============================================================================
# 히트맵 앙상블
# =============================================================================

def aggregate_heatmaps(
    heatmap_list: list[NDArray[np.float32]],
    method: HeatmapAggregation = HeatmapAggregation.MEAN,
    weights: NDArray[np.float64] | None = None,
) -> NDArray[np.float32]:
    """
    다중 히트맵 앙상블/집계.

    Args:
        heatmap_list: 히트맵 목록 (동일 shape)
        method: 집계 방법
        weights: 가중치 (WEIGHTED 방법 시)

    Returns:
        집계된 히트맵
    """
    if len(heatmap_list) == 0:
        raise ValueError("히트맵 목록이 비어있습니다")
    if len(heatmap_list) == 1:
        return heatmap_list[0].copy()

    stacked = np.stack(heatmap_list, axis=0)

    if method == HeatmapAggregation.MEAN:
        return np.mean(stacked, axis=0).astype(np.float32)
    elif method == HeatmapAggregation.MAX:
        return np.max(stacked, axis=0).astype(np.float32)
    elif method == HeatmapAggregation.WEIGHTED:
        if weights is None:
            raise ValueError("WEIGHTED 방법은 weights가 필요합니다")
        w = np.asarray(weights, dtype=np.float64)
        if len(w) != len(heatmap_list):
            raise ValueError(
                f"가중치 수 불일치: {len(w)} vs {len(heatmap_list)}"
            )
        w_sum = np.sum(w)
        if w_sum < _EPSILON:
            return np.mean(stacked, axis=0).astype(np.float32)
        w_norm = w / w_sum

        # (N,) → (N, 1, 1, ...) 브로드캐스팅
        shape = [len(w)] + [1] * (stacked.ndim - 1)
        w_shaped = w_norm.reshape(shape)

        return np.sum(stacked * w_shaped, axis=0).astype(np.float32)
    else:
        raise ValueError(f"지원하지 않는 집계 방법: {method}")


def flip_heatmap_horizontal(
    heatmaps: NDArray[np.float32],
    flip_pairs: tuple[tuple[int, int], ...] | None = None,
) -> NDArray[np.float32]:
    """
    히트맵 좌우 반전 (좌/우 키포인트 채널 교환 포함).

    Args:
        heatmaps: 히트맵 (C×H×W) 또는 (H×W)
        flip_pairs: 좌/우 교환할 채널 쌍 (None → COCO 기본)

    Returns:
        반전된 히트맵
    """
    if flip_pairs is None:
        # COCO 좌/우 쌍
        flip_pairs = (
            (1, 2),    # left_eye ↔ right_eye
            (3, 4),    # left_ear ↔ right_ear
            (5, 6),    # left_shoulder ↔ right_shoulder
            (7, 8),    # left_elbow ↔ right_elbow
            (9, 10),   # left_wrist ↔ right_wrist
            (11, 12),  # left_hip ↔ right_hip
            (13, 14),  # left_knee ↔ right_knee
            (15, 16),  # left_ankle ↔ right_ankle
        )

    flipped = np.flip(heatmaps, axis=-1).copy()

    if heatmaps.ndim == 3:
        for left, right in flip_pairs:
            if left < heatmaps.shape[0] and right < heatmaps.shape[0]:
                temp = flipped[left].copy()
                flipped[left] = flipped[right]
                flipped[right] = temp

    return flipped


# =============================================================================
# 히트맵 품질 분석
# =============================================================================

def compute_heatmap_quality(
    heatmap: NDArray[np.float32],
    threshold: float = DEFAULT_PEAK_THRESHOLD,
    nms_kernel_size: int = DEFAULT_NMS_KERNEL_SIZE,
) -> HeatmapQuality:
    """
    히트맵 품질 메트릭 계산.

    Args:
        heatmap: 2D 히트맵 (H×W)
        threshold: 피크 검출 임계값
        nms_kernel_size: NMS 커널 크기

    Returns:
        HeatmapQuality
    """
    if heatmap.ndim != 2:
        raise ValueError(f"히트맵은 2D여야 합니다: ndim={heatmap.ndim}")

    hm = heatmap.astype(np.float64)

    # 선명도 (라플라시안 분산)
    lap = cv2.Laplacian(hm, cv2.CV_64F)
    sharpness = float(np.var(lap))

    # SNR (피크 vs 배경)
    peak_val = float(np.max(hm))
    bg_mask = hm < threshold * 0.5
    if np.any(bg_mask):
        bg_std = float(np.std(hm[bg_mask]))
        if bg_std > _EPSILON:
            snr = 20.0 * math.log10(peak_val / bg_std)
        else:
            snr = float("inf") if peak_val > _EPSILON else 0.0
    else:
        snr = 0.0

    # 피크-평균 비율
    mean_val = float(np.mean(hm))
    peak_mean_ratio = peak_val / (mean_val + _EPSILON)

    # 정보 엔트로피
    hm_pos = hm[hm > _EPSILON]
    if len(hm_pos) > 0:
        p = hm_pos / np.sum(hm_pos)
        entropy = -float(np.sum(p * np.log2(p)))
    else:
        entropy = 0.0

    # 피크 수
    peaks = extract_peaks(
        heatmap, threshold=threshold,
        nms_kernel_size=nms_kernel_size,
        subpixel_method=SubpixelMethod.NONE,
    )

    return HeatmapQuality(
        sharpness=sharpness,
        snr=snr,
        peak_mean_ratio=peak_mean_ratio,
        entropy=entropy,
        num_peaks=len(peaks),
    )


# =============================================================================
# 히트맵 리사이즈/변환
# =============================================================================

def resize_heatmap(
    heatmap: NDArray[np.float32],
    target_width: int,
    target_height: int,
) -> NDArray[np.float32]:
    """
    히트맵 크기 조정 (쌍선형 보간).

    Args:
        heatmap: 입력 히트맵 (H×W) 또는 (C×H×W)
        target_width: 목표 너비
        target_height: 목표 높이

    Returns:
        리사이즈된 히트맵
    """
    if target_width <= 0 or target_height <= 0:
        raise ValueError(f"목표 크기는 양수여야 합니다: {target_width}×{target_height}")

    if heatmap.ndim == 2:
        return cv2.resize(
            heatmap, (target_width, target_height),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32)

    if heatmap.ndim == 3:
        c = heatmap.shape[0]
        result = np.empty((c, target_height, target_width), dtype=np.float32)
        for ch in range(c):
            result[ch] = cv2.resize(
                heatmap[ch], (target_width, target_height),
                interpolation=cv2.INTER_LINEAR,
            ).astype(np.float32)
        return result

    raise ValueError(f"히트맵은 2D 또는 3D여야 합니다: ndim={heatmap.ndim}")


def normalize_heatmap(
    heatmap: NDArray[np.float32],
    method: str = "minmax",
) -> NDArray[np.float32]:
    """
    히트맵 정규화.

    Args:
        heatmap: 입력 히트맵
        method: "minmax" (0~1) 또는 "sigmoid"

    Returns:
        정규화된 히트맵
    """
    if method == "minmax":
        hm_min = float(np.min(heatmap))
        hm_max = float(np.max(heatmap))
        if hm_max - hm_min < _EPSILON:
            return np.zeros_like(heatmap)
        return ((heatmap - hm_min) / (hm_max - hm_min)).astype(np.float32)

    elif method == "sigmoid":
        return (1.0 / (1.0 + np.exp(-heatmap.astype(np.float64)))).astype(np.float32)

    else:
        raise ValueError(f"지원하지 않는 정규화 방법: {method}")


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # === 상수 ===
    "DEFAULT_PEAK_THRESHOLD",
    "DEFAULT_GAUSSIAN_SIGMA",
    "DEFAULT_NMS_KERNEL_SIZE",
    "COCO_NUM_KEYPOINTS",
    "COCO_KEYPOINT_NAMES",
    "COCO_SKELETON_CONNECTIONS",

    # === Enum ===
    "SubpixelMethod",
    "HeatmapAggregation",

    # === 데이터 클래스 ===
    "HeatmapConfig",
    "PeakInfo",
    "SkeletonResult",
    "HeatmapQuality",

    # === 피크 검출 ===
    "extract_peaks",
    "extract_peaks_batch",
    "extract_top_peak",

    # === 가우시안 히트맵 생성 ===
    "generate_gaussian_heatmap",
    "generate_multi_keypoint_heatmap",

    # === 스켈레톤 디코딩 ===
    "decode_heatmaps_to_skeleton",
    "decode_multi_person_heatmaps",

    # === 히트맵 앙상블 ===
    "aggregate_heatmaps",
    "flip_heatmap_horizontal",

    # === 품질 분석 ===
    "compute_heatmap_quality",

    # === 리사이즈/변환 ===
    "resize_heatmap",
    "normalize_heatmap",
]

__version__: str = "1.0.0"
