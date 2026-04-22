# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: feature_matching_utils.py
설명: 특징점 검출 및 매칭 유틸리티
      - 다중 검출기 지원 (ORB, SIFT, AKAZE, BRISK)
      - 디스크립터 매칭 (BF, FLANN)
      - 비율 테스트 (Lowe's ratio) 필터링
      - 에피폴라 제약 기반 매칭 필터
      - 호모그래피 기반 인라이어 필터
      - 매칭 품질 메트릭 및 통계

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - 4가지 특징점 검출기 통합 인터페이스 (ORB/SIFT/AKAZE/BRISK)
    - BruteForce / FLANN 매칭 전략
    - Lowe's ratio test 필터링 (default 0.75)
    - 에피폴라 제약 + 호모그래피 기반 이중 필터
    - 교차 검증 (cross-check) 매칭
    - 매칭 신뢰도 및 분포 통계
    - 순수 OpenCV + NumPy 구현

사용 예시:
    >>> from utils.feature_matching_utils import (
    ...     DetectorType, detect_keypoints,
    ...     match_descriptors, filter_matches_ratio,
    ... )
    >>> import numpy as np
    >>> image = np.random.randint(0, 255, (480, 640), dtype=np.uint8)
    >>> result = detect_keypoints(image, DetectorType.ORB)
    >>> result.num_keypoints > 0
    True
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


# =============================================================================
# 상수 정의
# =============================================================================

# 부동소수점 비교용 임계값
_EPSILON: float = 1e-10

# Lowe's ratio test 기본 임계값
DEFAULT_RATIO_THRESHOLD: float = 0.75

# 교차 검증 활성화 기본값
DEFAULT_CROSS_CHECK: bool = False

# ORB 기본 특징점 수
DEFAULT_ORB_FEATURES: int = 2000

# SIFT 기본 특징점 수
DEFAULT_SIFT_FEATURES: int = 2000

# AKAZE 기본 임계값
DEFAULT_AKAZE_THRESHOLD: float = 0.001

# BRISK 기본 임계값
DEFAULT_BRISK_THRESHOLD: int = 30

# RANSAC 호모그래피 임계값 (픽셀)
DEFAULT_HOMOGRAPHY_THRESHOLD: float = 3.0

# 에피폴라 거리 기본 임계값 (픽셀)
DEFAULT_EPIPOLAR_THRESHOLD: float = 2.0

# 최소 매칭 수 (유효 매칭 판별)
MIN_GOOD_MATCHES: int = 10

# 배치 최대 크기
_MAX_BATCH_SIZE: int = 50_000

# FLANN 인덱스 파라미터
_FLANN_INDEX_KDTREE: int = 1
_FLANN_INDEX_LSH: int = 6
_FLANN_KDTREE_TREES: int = 5
_FLANN_LSH_TABLE_NUMBER: int = 12
_FLANN_LSH_KEY_SIZE: int = 20
_FLANN_LSH_MULTI_PROBE: int = 2
_FLANN_SEARCH_CHECKS: int = 50


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class DetectorType(Enum):
    """특징점 검출기 유형."""

    ORB = "orb"       # Oriented FAST and Rotated BRIEF
    SIFT = "sift"     # Scale-Invariant Feature Transform
    AKAZE = "akaze"   # Accelerated KAZE
    BRISK = "brisk"   # Binary Robust Invariant Scalable Keypoints


@unique
class MatcherType(Enum):
    """디스크립터 매칭 전략."""

    BRUTE_FORCE = "brute_force"   # 전수 비교
    FLANN = "flann"               # Fast Library for Approximate Nearest Neighbors


@unique
class DescriptorNorm(Enum):
    """디스크립터 거리 메트릭."""

    L2 = "l2"             # L2 norm (SIFT 등 float 디스크립터)
    HAMMING = "hamming"   # 해밍 거리 (ORB, BRISK 등 바이너리 디스크립터)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class KeypointInfo:
    """
    단일 특징점 정보.

    Attributes:
        x: x좌표 (픽셀)
        y: y좌표 (픽셀)
        size: 특징점 크기 (직경)
        angle: 방향 (도)
        response: 반응 강도
        octave: 옥타브 (스케일 레벨)
    """

    x: float
    y: float
    size: float
    angle: float
    response: float
    octave: int

    def __repr__(self) -> str:
        return (
            f"KeypointInfo(x={self.x:.1f}, y={self.y:.1f}, "
            f"size={self.size:.1f}, response={self.response:.4f})"
        )


@dataclass(slots=True)
class DetectionResult:
    """
    특징점 검출 결과.

    Attributes:
        keypoints: OpenCV KeyPoint 목록 (cv2.KeyPoint)
        descriptors: 디스크립터 행렬 (N×D)
        detector_type: 사용된 검출기
        num_keypoints: 검출된 특징점 수
    """

    keypoints: list[cv2.KeyPoint]
    descriptors: NDArray | None
    detector_type: DetectorType
    num_keypoints: int

    def __repr__(self) -> str:
        return (
            f"DetectionResult(detector={self.detector_type.value}, "
            f"n_keypoints={self.num_keypoints})"
        )

    def get_points(self) -> NDArray[np.float64]:
        """특징점 좌표 배열 (N×2) 반환."""
        if self.num_keypoints == 0:
            return np.empty((0, 2), dtype=np.float64)
        return np.array(
            [kp.pt for kp in self.keypoints], dtype=np.float64,
        )

    def get_keypoint_info(self) -> list[KeypointInfo]:
        """KeypointInfo 목록 반환."""
        return [
            KeypointInfo(
                x=kp.pt[0],
                y=kp.pt[1],
                size=kp.size,
                angle=kp.angle,
                response=kp.response,
                octave=kp.octave,
            )
            for kp in self.keypoints
        ]


@dataclass(slots=True)
class MatchPair:
    """
    단일 매칭 쌍.

    Attributes:
        query_idx: 쿼리 디스크립터 인덱스
        train_idx: 훈련 디스크립터 인덱스
        distance: 매칭 거리
        ratio: 비율 테스트 값 (best/second-best)
    """

    query_idx: int
    train_idx: int
    distance: float
    ratio: float = 0.0

    def __repr__(self) -> str:
        return (
            f"MatchPair(q={self.query_idx}, t={self.train_idx}, "
            f"dist={self.distance:.4f}, ratio={self.ratio:.3f})"
        )


@dataclass(slots=True)
class MatchResult:
    """
    디스크립터 매칭 결과.

    Attributes:
        matches: 매칭 쌍 목록
        num_matches: 총 매칭 수
        matcher_type: 사용된 매칭 전략
        pts1: 매칭된 점 좌표 (쿼리 이미지)
        pts2: 매칭된 점 좌표 (훈련 이미지)
    """

    matches: list[MatchPair]
    num_matches: int
    matcher_type: MatcherType
    pts1: NDArray[np.float64]
    pts2: NDArray[np.float64]

    def __repr__(self) -> str:
        return (
            f"MatchResult(matcher={self.matcher_type.value}, "
            f"n_matches={self.num_matches})"
        )


@dataclass(slots=True)
class MatchQuality:
    """
    매칭 품질 통계.

    Attributes:
        num_total: 총 매칭 수
        num_good: 좋은 매칭 수 (ratio test 통과)
        num_inliers: 인라이어 수 (기하 검증 통과)
        inlier_ratio: 인라이어 비율
        mean_distance: 평균 매칭 거리
        std_distance: 거리 표준편차
        median_distance: 거리 중앙값
        confidence: 매칭 신뢰도 (0~1)
    """

    num_total: int
    num_good: int
    num_inliers: int
    inlier_ratio: float
    mean_distance: float
    std_distance: float
    median_distance: float
    confidence: float

    def __repr__(self) -> str:
        return (
            f"MatchQuality(good={self.num_good}, "
            f"inliers={self.num_inliers}/{self.num_total}, "
            f"confidence={self.confidence:.3f})"
        )


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _create_detector(
    detector_type: DetectorType,
    max_features: int = DEFAULT_ORB_FEATURES,
) -> cv2.Feature2D:
    """검출기 인스턴스 생성."""
    if detector_type == DetectorType.ORB:
        return cv2.ORB_create(nfeatures=max_features)
    elif detector_type == DetectorType.SIFT:
        return cv2.SIFT_create(nfeatures=max_features)
    elif detector_type == DetectorType.AKAZE:
        return cv2.AKAZE_create(threshold=DEFAULT_AKAZE_THRESHOLD)
    elif detector_type == DetectorType.BRISK:
        return cv2.BRISK_create(thresh=DEFAULT_BRISK_THRESHOLD)
    else:
        raise ValueError(f"지원하지 않는 검출기: {detector_type}")


def _get_descriptor_norm(detector_type: DetectorType) -> DescriptorNorm:
    """검출기 유형에 따른 디스크립터 거리 메트릭 결정."""
    if detector_type in (DetectorType.ORB, DetectorType.BRISK, DetectorType.AKAZE):
        return DescriptorNorm.HAMMING
    return DescriptorNorm.L2


def _create_bf_matcher(norm: DescriptorNorm, cross_check: bool) -> cv2.BFMatcher:
    """BruteForce 매처 생성."""
    if norm == DescriptorNorm.HAMMING:
        return cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=cross_check)
    return cv2.BFMatcher(cv2.NORM_L2, crossCheck=cross_check)


def _create_flann_matcher(norm: DescriptorNorm) -> cv2.FlannBasedMatcher:
    """FLANN 매처 생성."""
    if norm == DescriptorNorm.HAMMING:
        index_params = {
            "algorithm": _FLANN_INDEX_LSH,
            "table_number": _FLANN_LSH_TABLE_NUMBER,
            "key_size": _FLANN_LSH_KEY_SIZE,
            "multi_probe_level": _FLANN_LSH_MULTI_PROBE,
        }
    else:
        index_params = {
            "algorithm": _FLANN_INDEX_KDTREE,
            "trees": _FLANN_KDTREE_TREES,
        }

    search_params = {"checks": _FLANN_SEARCH_CHECKS}
    return cv2.FlannBasedMatcher(index_params, search_params)


def _to_gray(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """이미지를 그레이스케일로 변환 (이미 그레이면 그대로)."""
    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0]
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _dmatch_to_match_pair(
    dm: cv2.DMatch,
    ratio: float = 0.0,
) -> MatchPair:
    """cv2.DMatch → MatchPair 변환."""
    return MatchPair(
        query_idx=dm.queryIdx,
        train_idx=dm.trainIdx,
        distance=dm.distance,
        ratio=ratio,
    )


def _compute_match_confidence(
    good_matches: int,
    total_matches: int,
    inlier_ratio: float,
    mean_distance: float,
    descriptor_norm: DescriptorNorm,
) -> float:
    """
    매칭 신뢰도 계산 (0~1).

    3가지 요소의 가중 평균:
    - 좋은 매칭 비율 (30%)
    - 인라이어 비율 (40%)
    - 거리 기반 품질 (30%)
    """
    # 좋은 매칭 비율
    good_ratio = good_matches / max(total_matches, 1)

    # 거리 기반 품질 (낮을수록 좋음)
    if descriptor_norm == DescriptorNorm.HAMMING:
        # 해밍 거리: 0-256 범위
        dist_quality = max(0.0, 1.0 - mean_distance / 128.0)
    else:
        # L2 거리: 0-∞, 시그모이드 변환
        dist_quality = math.exp(-mean_distance / 200.0)

    confidence = 0.30 * good_ratio + 0.40 * inlier_ratio + 0.30 * dist_quality
    return min(max(confidence, 0.0), 1.0)


# =============================================================================
# 특징점 검출
# =============================================================================

def detect_keypoints(
    image: NDArray[np.uint8],
    detector_type: DetectorType = DetectorType.ORB,
    max_features: int = DEFAULT_ORB_FEATURES,
    mask: NDArray[np.uint8] | None = None,
) -> DetectionResult:
    """
    이미지에서 특징점 및 디스크립터 검출.

    Args:
        image: 입력 이미지 (그레이스케일 또는 컬러)
        detector_type: 검출기 유형
        max_features: 최대 특징점 수 (ORB, SIFT)
        mask: 검출 영역 마스크 (선택)

    Returns:
        DetectionResult
    """
    gray = _to_gray(image)
    detector = _create_detector(detector_type, max_features)

    keypoints, descriptors = detector.detectAndCompute(gray, mask)

    if keypoints is None:
        keypoints = []
    if descriptors is None:
        descriptors = None

    return DetectionResult(
        keypoints=list(keypoints),
        descriptors=descriptors,
        detector_type=detector_type,
        num_keypoints=len(keypoints),
    )


def detect_keypoints_multiscale(
    image: NDArray[np.uint8],
    detector_type: DetectorType = DetectorType.ORB,
    scales: tuple[float, ...] = (0.5, 1.0, 2.0),
    max_features_per_scale: int = 1000,
) -> DetectionResult:
    """
    다중 스케일 특징점 검출.

    각 스케일에서 독립적으로 검출 후 병합 (중복 제거).

    Args:
        image: 입력 이미지
        detector_type: 검출기 유형
        scales: 스케일 팩터 튜플
        max_features_per_scale: 스케일 당 최대 특징점 수

    Returns:
        병합된 DetectionResult
    """
    gray = _to_gray(image)
    h, w = gray.shape[:2]

    all_keypoints: list[cv2.KeyPoint] = []
    all_descriptors: list[NDArray] = []

    for scale in scales:
        if scale <= 0:
            continue

        if abs(scale - 1.0) < _EPSILON:
            scaled = gray
        else:
            new_h = max(1, int(h * scale))
            new_w = max(1, int(w * scale))
            scaled = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        detector = _create_detector(detector_type, max_features_per_scale)
        kps, descs = detector.detectAndCompute(scaled, None)

        if kps is None or len(kps) == 0:
            continue

        # 원래 스케일로 좌표 역변환
        inv_scale = 1.0 / scale
        for kp in kps:
            kp.pt = (kp.pt[0] * inv_scale, kp.pt[1] * inv_scale)
            kp.size *= inv_scale

        all_keypoints.extend(kps)
        if descs is not None:
            all_descriptors.append(descs)

    # 디스크립터 병합
    if all_descriptors:
        merged_desc = np.vstack(all_descriptors)
    else:
        merged_desc = None

    return DetectionResult(
        keypoints=all_keypoints,
        descriptors=merged_desc,
        detector_type=detector_type,
        num_keypoints=len(all_keypoints),
    )


# =============================================================================
# 디스크립터 매칭
# =============================================================================

def match_descriptors(
    desc1: NDArray,
    desc2: NDArray,
    matcher_type: MatcherType = MatcherType.BRUTE_FORCE,
    descriptor_norm: DescriptorNorm = DescriptorNorm.L2,
    cross_check: bool = DEFAULT_CROSS_CHECK,
    k: int = 2,
) -> list[list[cv2.DMatch]]:
    """
    디스크립터 매칭 수행.

    Args:
        desc1: 쿼리 디스크립터 (N×D)
        desc2: 훈련 디스크립터 (M×D)
        matcher_type: 매칭 전략
        descriptor_norm: 거리 메트릭
        cross_check: 교차 검증 (k=1에서만 유효)
        k: kNN에서 k값

    Returns:
        매칭 결과 리스트 (각 원소는 k개 DMatch 리스트)
    """
    if desc1 is None or desc2 is None:
        return []
    if len(desc1) == 0 or len(desc2) == 0:
        return []

    # k가 훈련 디스크립터 수보다 크면 조정
    actual_k = min(k, len(desc2))

    if matcher_type == MatcherType.BRUTE_FORCE:
        if actual_k == 1 and cross_check:
            matcher = _create_bf_matcher(descriptor_norm, cross_check=True)
            raw_matches = matcher.match(desc1, desc2)
            return [[m] for m in raw_matches]
        matcher = _create_bf_matcher(descriptor_norm, cross_check=False)
    elif matcher_type == MatcherType.FLANN:
        # FLANN은 float32 필요
        if desc1.dtype != np.float32:
            desc1 = desc1.astype(np.float32)
        if desc2.dtype != np.float32:
            desc2 = desc2.astype(np.float32)
        matcher = _create_flann_matcher(descriptor_norm)
    else:
        raise ValueError(f"지원하지 않는 매칭 전략: {matcher_type}")

    return matcher.knnMatch(desc1, desc2, k=actual_k)


def filter_matches_ratio(
    knn_matches: list[list[cv2.DMatch]],
    ratio_threshold: float = DEFAULT_RATIO_THRESHOLD,
) -> list[MatchPair]:
    """
    Lowe's ratio test 필터링.

    best_distance / second_best_distance < threshold

    Args:
        knn_matches: kNN 매칭 결과 (k=2)
        ratio_threshold: 비율 임계값 (기본 0.75)

    Returns:
        필터링된 MatchPair 목록
    """
    good_matches: list[MatchPair] = []

    for match_group in knn_matches:
        if len(match_group) < 2:
            if len(match_group) == 1:
                good_matches.append(_dmatch_to_match_pair(match_group[0], ratio=0.0))
            continue

        best = match_group[0]
        second = match_group[1]

        if second.distance < _EPSILON:
            ratio = 1.0
        else:
            ratio = best.distance / second.distance

        if ratio < ratio_threshold:
            good_matches.append(_dmatch_to_match_pair(best, ratio=ratio))

    return good_matches


def filter_matches_symmetric(
    matches_1to2: list[MatchPair],
    matches_2to1: list[MatchPair],
) -> list[MatchPair]:
    """
    대칭 매칭 필터 (양방향 일치하는 매칭만 유지).

    Args:
        matches_1to2: 이미지1→이미지2 매칭
        matches_2to1: 이미지2→이미지1 매칭

    Returns:
        양방향 일치 매칭 목록
    """
    # 역방향 매칭을 딕셔너리로
    reverse_map: dict[int, int] = {}
    for m in matches_2to1:
        reverse_map[m.query_idx] = m.train_idx

    symmetric: list[MatchPair] = []
    for m in matches_1to2:
        # 1→2 매칭의 train_idx가 역방향에서 query_idx
        rev_train = reverse_map.get(m.train_idx)
        if rev_train is not None and rev_train == m.query_idx:
            symmetric.append(m)

    return symmetric


# =============================================================================
# 기하학적 필터링
# =============================================================================

def filter_matches_homography(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    matches: list[MatchPair],
    ransac_threshold: float = DEFAULT_HOMOGRAPHY_THRESHOLD,
) -> tuple[list[MatchPair], NDArray[np.float64] | None]:
    """
    호모그래피 기반 인라이어 필터링.

    Args:
        pts1: 쿼리 이미지 점 (N×2)
        pts2: 훈련 이미지 점 (N×2)
        matches: 매칭 쌍 목록
        ransac_threshold: RANSAC 임계값

    Returns:
        (인라이어 매칭 목록, 호모그래피 행렬 3×3 | None)
    """
    if len(matches) < 4:
        logger.warning("호모그래피 추정에 최소 4개 매칭 필요: %d개", len(matches))
        return matches, None

    src_pts = np.array([pts1[m.query_idx] for m in matches], dtype=np.float64)
    dst_pts = np.array([pts2[m.train_idx] for m in matches], dtype=np.float64)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransac_threshold)

    if mask is None:
        return matches, H

    inlier_mask = mask.ravel().astype(bool)
    inlier_matches = [m for m, is_inlier in zip(matches, inlier_mask) if is_inlier]

    return inlier_matches, H


def filter_matches_epipolar(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    matches: list[MatchPair],
    F: NDArray[np.float64],
    threshold: float = DEFAULT_EPIPOLAR_THRESHOLD,
) -> list[MatchPair]:
    """
    에피폴라 제약 기반 매칭 필터링.

    x2^T · F · x1 ≈ 0 인 매칭만 유지.

    Args:
        pts1: 쿼리 이미지 점 (N×2)
        pts2: 훈련 이미지 점 (N×2)
        matches: 매칭 쌍 목록
        F: 기본 행렬 (3×3)
        threshold: 에피폴라 거리 임계값 (픽셀)

    Returns:
        필터링된 매칭 목록
    """
    if len(matches) == 0:
        return []

    filtered: list[MatchPair] = []

    for m in matches:
        p1 = np.array([pts1[m.query_idx][0], pts1[m.query_idx][1], 1.0])
        p2 = np.array([pts2[m.train_idx][0], pts2[m.train_idx][1], 1.0])

        # 에피폴라 라인
        l2 = F @ p1     # 2뷰에서의 에피폴라 라인
        l1 = F.T @ p2   # 1뷰에서의 에피폴라 라인

        # 점-직선 거리
        d2 = abs(float(p2 @ l2)) / (math.sqrt(l2[0] ** 2 + l2[1] ** 2) + _EPSILON)
        d1 = abs(float(p1 @ l1)) / (math.sqrt(l1[0] ** 2 + l1[1] ** 2) + _EPSILON)

        avg_dist = (d1 + d2) / 2.0

        if avg_dist < threshold:
            filtered.append(m)

    return filtered


def filter_matches_distance(
    matches: list[MatchPair],
    max_distance: float | None = None,
    percentile: float = 75.0,
) -> list[MatchPair]:
    """
    매칭 거리 기반 필터링.

    Args:
        matches: 매칭 쌍 목록
        max_distance: 최대 허용 거리 (None → percentile 기반)
        percentile: 사용할 백분위수 (max_distance가 None일 때)

    Returns:
        필터링된 매칭 목록
    """
    if len(matches) == 0:
        return []

    distances = np.array([m.distance for m in matches])

    if max_distance is None:
        max_distance = float(np.percentile(distances, percentile))

    return [m for m in matches if m.distance <= max_distance]


# =============================================================================
# 통합 매칭 파이프라인
# =============================================================================

def match_images(
    image1: NDArray[np.uint8],
    image2: NDArray[np.uint8],
    detector_type: DetectorType = DetectorType.ORB,
    matcher_type: MatcherType = MatcherType.BRUTE_FORCE,
    max_features: int = DEFAULT_ORB_FEATURES,
    ratio_threshold: float = DEFAULT_RATIO_THRESHOLD,
    use_homography_filter: bool = True,
    homography_threshold: float = DEFAULT_HOMOGRAPHY_THRESHOLD,
) -> MatchResult:
    """
    두 이미지 간 통합 매칭 파이프라인.

    검출 → 매칭 → 비율 테스트 → (선택) 호모그래피 필터

    Args:
        image1: 쿼리 이미지
        image2: 훈련 이미지
        detector_type: 검출기 유형
        matcher_type: 매칭 전략
        max_features: 최대 특징점 수
        ratio_threshold: Lowe's ratio 임계값
        use_homography_filter: 호모그래피 필터 사용 여부
        homography_threshold: 호모그래피 RANSAC 임계값

    Returns:
        MatchResult
    """
    # 검출
    det1 = detect_keypoints(image1, detector_type, max_features)
    det2 = detect_keypoints(image2, detector_type, max_features)

    if det1.descriptors is None or det2.descriptors is None:
        logger.warning("디스크립터가 비어있어 매칭 불가")
        return MatchResult(
            matches=[],
            num_matches=0,
            matcher_type=matcher_type,
            pts1=np.empty((0, 2), dtype=np.float64),
            pts2=np.empty((0, 2), dtype=np.float64),
        )

    # 매칭
    norm = _get_descriptor_norm(detector_type)
    knn_matches = match_descriptors(
        det1.descriptors, det2.descriptors,
        matcher_type=matcher_type,
        descriptor_norm=norm,
        k=2,
    )

    # 비율 테스트
    good_matches = filter_matches_ratio(knn_matches, ratio_threshold)

    if len(good_matches) == 0:
        return MatchResult(
            matches=[],
            num_matches=0,
            matcher_type=matcher_type,
            pts1=np.empty((0, 2), dtype=np.float64),
            pts2=np.empty((0, 2), dtype=np.float64),
        )

    # 점 좌표 추출
    pts1 = det1.get_points()
    pts2 = det2.get_points()

    # 호모그래피 필터링 (선택)
    if use_homography_filter and len(good_matches) >= 4:
        good_matches, _ = filter_matches_homography(
            pts1, pts2, good_matches, homography_threshold,
        )

    # 매칭된 점 좌표
    matched_pts1 = np.array(
        [pts1[m.query_idx] for m in good_matches], dtype=np.float64,
    ) if good_matches else np.empty((0, 2), dtype=np.float64)
    matched_pts2 = np.array(
        [pts2[m.train_idx] for m in good_matches], dtype=np.float64,
    ) if good_matches else np.empty((0, 2), dtype=np.float64)

    return MatchResult(
        matches=good_matches,
        num_matches=len(good_matches),
        matcher_type=matcher_type,
        pts1=matched_pts1,
        pts2=matched_pts2,
    )


# =============================================================================
# 매칭 품질 분석
# =============================================================================

def compute_match_quality(
    matches: list[MatchPair],
    total_keypoints: int,
    inlier_count: int | None = None,
    descriptor_norm: DescriptorNorm = DescriptorNorm.L2,
) -> MatchQuality:
    """
    매칭 품질 통계 계산.

    Args:
        matches: 매칭 쌍 목록
        total_keypoints: 전체 검출 특징점 수
        inlier_count: 인라이어 수 (None → matches 전체를 인라이어로 가정)
        descriptor_norm: 디스크립터 거리 메트릭

    Returns:
        MatchQuality 통계
    """
    n_good = len(matches)

    if inlier_count is None:
        inlier_count = n_good

    inlier_ratio = inlier_count / max(n_good, 1)

    if n_good == 0:
        return MatchQuality(
            num_total=total_keypoints,
            num_good=0,
            num_inliers=0,
            inlier_ratio=0.0,
            mean_distance=float("inf"),
            std_distance=0.0,
            median_distance=float("inf"),
            confidence=0.0,
        )

    distances = np.array([m.distance for m in matches])
    mean_dist = float(np.mean(distances))
    std_dist = float(np.std(distances))
    median_dist = float(np.median(distances))

    confidence = _compute_match_confidence(
        n_good, total_keypoints, inlier_ratio, mean_dist, descriptor_norm,
    )

    return MatchQuality(
        num_total=total_keypoints,
        num_good=n_good,
        num_inliers=inlier_count,
        inlier_ratio=inlier_ratio,
        mean_distance=mean_dist,
        std_distance=std_dist,
        median_distance=median_dist,
        confidence=confidence,
    )


def compute_descriptor_distance(
    desc1: NDArray,
    desc2: NDArray,
    norm: DescriptorNorm = DescriptorNorm.L2,
) -> float:
    """
    두 디스크립터 간 거리 계산.

    Args:
        desc1: 디스크립터 벡터 (D,)
        desc2: 디스크립터 벡터 (D,)
        norm: 거리 메트릭

    Returns:
        거리 값
    """
    if norm == DescriptorNorm.HAMMING:
        # 바이너리 디스크립터 → XOR 후 비트 카운트
        xor_result = np.bitwise_xor(desc1.astype(np.uint8), desc2.astype(np.uint8))
        return float(np.sum(np.unpackbits(xor_result)))

    # L2 norm
    diff = desc1.astype(np.float64) - desc2.astype(np.float64)
    return float(np.sqrt(np.sum(diff * diff)))


def compute_descriptor_distance_matrix(
    descriptors1: NDArray,
    descriptors2: NDArray,
    norm: DescriptorNorm = DescriptorNorm.L2,
) -> NDArray[np.float64]:
    """
    디스크립터 간 거리 행렬 계산 (N×M).

    Args:
        descriptors1: 쿼리 디스크립터 (N×D)
        descriptors2: 훈련 디스크립터 (M×D)
        norm: 거리 메트릭

    Returns:
        거리 행렬 (N×M)
    """
    if norm == DescriptorNorm.L2:
        d1 = descriptors1.astype(np.float64)
        d2 = descriptors2.astype(np.float64)

        # ||a - b||² = ||a||² + ||b||² - 2·a·b
        sq1 = np.sum(d1 * d1, axis=1, keepdims=True)  # (N, 1)
        sq2 = np.sum(d2 * d2, axis=1, keepdims=True)  # (M, 1)
        dot = d1 @ d2.T                                 # (N, M)

        dist_sq = sq1 + sq2.T - 2.0 * dot
        dist_sq = np.maximum(dist_sq, 0.0)  # 수치 오차 보정

        return np.sqrt(dist_sq)

    # 해밍 거리 — 루프 (바이너리 디스크립터)
    n, m = len(descriptors1), len(descriptors2)
    result = np.empty((n, m), dtype=np.float64)

    for i in range(n):
        for j in range(m):
            result[i, j] = compute_descriptor_distance(
                descriptors1[i], descriptors2[j], norm,
            )

    return result


# =============================================================================
# 유틸리티 함수
# =============================================================================

def extract_matched_points(
    keypoints1: list[cv2.KeyPoint],
    keypoints2: list[cv2.KeyPoint],
    matches: list[MatchPair],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    매칭 결과에서 대응점 좌표 추출.

    Args:
        keypoints1: 쿼리 키포인트 목록
        keypoints2: 훈련 키포인트 목록
        matches: 매칭 쌍 목록

    Returns:
        (쿼리 점 N×2, 훈련 점 N×2)
    """
    if len(matches) == 0:
        return (
            np.empty((0, 2), dtype=np.float64),
            np.empty((0, 2), dtype=np.float64),
        )

    pts1 = np.array(
        [keypoints1[m.query_idx].pt for m in matches], dtype=np.float64,
    )
    pts2 = np.array(
        [keypoints2[m.train_idx].pt for m in matches], dtype=np.float64,
    )

    return pts1, pts2


def spatial_consistency_filter(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    matches: list[MatchPair],
    neighbor_radius: float = 50.0,
    min_consistent_neighbors: int = 3,
) -> list[MatchPair]:
    """
    공간 일관성 기반 매칭 필터.

    각 매칭의 이웃 매칭들이 유사한 변위 벡터를 가져야 함.

    Args:
        pts1: 쿼리 점 좌표 (전체 N×2)
        pts2: 훈련 점 좌표 (전체 M×2)
        matches: 매칭 쌍 목록
        neighbor_radius: 이웃 검색 반경 (픽셀)
        min_consistent_neighbors: 최소 일관 이웃 수

    Returns:
        공간적으로 일관된 매칭 목록
    """
    if len(matches) < min_consistent_neighbors:
        return matches

    # 매칭 변위 벡터 계산
    src = np.array([pts1[m.query_idx] for m in matches], dtype=np.float64)
    dst = np.array([pts2[m.train_idx] for m in matches], dtype=np.float64)
    displacements = dst - src

    n = len(matches)
    consistent = np.zeros(n, dtype=bool)

    for i in range(n):
        # 이웃 찾기 (쿼리 점 기준)
        dists = np.linalg.norm(src - src[i], axis=1)
        neighbors = np.where((dists < neighbor_radius) & (dists > _EPSILON))[0]

        if len(neighbors) < min_consistent_neighbors:
            continue

        # 변위 일관성 검사 (중앙값 기반)
        neighbor_disps = displacements[neighbors]
        median_disp = np.median(neighbor_disps, axis=0)
        disp_errors = np.linalg.norm(neighbor_disps - median_disp, axis=1)
        my_error = np.linalg.norm(displacements[i] - median_disp)

        # 이웃의 변위 오차 중앙값 대비 3배 이내
        median_error = float(np.median(disp_errors))
        if my_error < 3.0 * (median_error + _EPSILON):
            consistent[i] = True

    return [m for m, c in zip(matches, consistent) if c]


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # === 상수 ===
    "DEFAULT_RATIO_THRESHOLD",
    "DEFAULT_CROSS_CHECK",
    "DEFAULT_ORB_FEATURES",
    "DEFAULT_SIFT_FEATURES",
    "DEFAULT_AKAZE_THRESHOLD",
    "DEFAULT_BRISK_THRESHOLD",
    "DEFAULT_HOMOGRAPHY_THRESHOLD",
    "DEFAULT_EPIPOLAR_THRESHOLD",
    "MIN_GOOD_MATCHES",

    # === Enum ===
    "DetectorType",
    "MatcherType",
    "DescriptorNorm",

    # === 데이터 클래스 ===
    "KeypointInfo",
    "DetectionResult",
    "MatchPair",
    "MatchResult",
    "MatchQuality",

    # === 특징점 검출 ===
    "detect_keypoints",
    "detect_keypoints_multiscale",

    # === 디스크립터 매칭 ===
    "match_descriptors",
    "filter_matches_ratio",
    "filter_matches_symmetric",

    # === 기하학적 필터링 ===
    "filter_matches_homography",
    "filter_matches_epipolar",
    "filter_matches_distance",

    # === 통합 파이프라인 ===
    "match_images",

    # === 품질 분석 ===
    "compute_match_quality",
    "compute_descriptor_distance",
    "compute_descriptor_distance_matrix",

    # === 유틸리티 ===
    "extract_matched_points",
    "spatial_consistency_filter",
]

__version__: str = "1.0.0"
