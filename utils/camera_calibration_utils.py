# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: camera_calibration_utils.py
설명: 카메라 캘리브레이션 및 3D 재구성 유틸리티
      - 내부/외부 파라미터 관리 및 검증
      - 렌즈 왜곡 보정 (방사형 + 접선형)
      - 기본 행렬(F) / 본질 행렬(E) 계산
      - 3D 삼각측량 (선형 DLT + 비선형 정제)
      - 에피폴 / 에피폴라 라인 계산
      - 투영 행렬 분해 및 합성
      - 배치 언디스토트 / 리프로젝션

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-16
버전: 1.0.0

주요 기능:
    - 내부행렬(K) 구성 및 검증 (fx, fy, cx, cy)
    - 왜곡계수 5/8/12/14 파라미터 지원
    - 방사형(k1-k6) + 접선형(p1,p2) + 박막프리즘(s1-s4) 왜곡 모델
    - 기본 행렬: 정규화 8점 알고리즘 + RANSAC
    - 본질 행렬: E = K'^T · F · K 및 분해 (4해 → 양의 깊이 선택)
    - DLT 삼각측량 + 중점법(midpoint) 삼각측량
    - 리프로젝션 오차 계산 (단일/배치)
    - 순수 NumPy + OpenCV 구현 (외부 3D 라이브러리 무의존)

사용 예시:
    >>> from utils.camera_calibration_utils import (
    ...     CameraIntrinsics, DistortionModel, undistort_points,
    ...     compute_fundamental_matrix, triangulate_points_dlt,
    ... )
    >>> import numpy as np
    >>> K = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0)
    >>> K.to_matrix().shape
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


# =============================================================================
# 상수 정의
# =============================================================================

# 부동소수점 비교용 임계값
_EPSILON: float = 1e-10

# RANSAC 기본 파라미터
DEFAULT_RANSAC_THRESHOLD: float = 3.0       # 인라이어 판별 임계값 (픽셀)
DEFAULT_RANSAC_CONFIDENCE: float = 0.999    # 성공 확률
DEFAULT_RANSAC_MAX_ITERS: int = 2000        # 최대 반복 횟수

# 리프로젝션 오차 허용 임계값
REPROJECTION_ERROR_THRESHOLD: float = 2.0   # 픽셀

# 정규화 8점 알고리즘 최소 대응점 수
MIN_POINTS_FUNDAMENTAL: int = 8
MIN_POINTS_ESSENTIAL: int = 5

# 배치 최대 크기
_MAX_BATCH_SIZE: int = 100_000

# 왜곡 모델 최대 계수 수
_MAX_DISTORTION_COEFFS: int = 14

# SVD 특이값 임계값 (랭크 판별)
_SVD_RANK_THRESHOLD: float = 1e-8

# 삼각측량 최소 시차 각도 (도)
MIN_PARALLAX_DEGREES: float = 1.0

# 양의 깊이 판별 임계값
_POSITIVE_DEPTH_THRESHOLD: float = 0.0


# =============================================================================
# Enum 정의
# =============================================================================

@unique
class DistortionModel(Enum):
    """렌즈 왜곡 모델 유형."""

    NONE = "none"                      # 왜곡 없음
    RADIAL_2 = "radial_2"             # k1, k2 (2 계수)
    RADIAL_3 = "radial_3"             # k1, k2, k3 (3 계수)
    BROWN_CONRADY = "brown_conrady"   # k1, k2, p1, p2, k3 (5 계수, OpenCV 표준)
    RATIONAL_6 = "rational_6"         # k1-k6 + p1, p2 (8 계수)
    FULL_14 = "full_14"               # k1-k6 + p1, p2 + s1-s4 + τx, τy (14 계수)


@unique
class FundamentalMethod(Enum):
    """기본 행렬 추정 방법."""

    EIGHT_POINT = "eight_point"   # 정규화 8점 알고리즘
    RANSAC = "ransac"             # RANSAC 기반 로버스트 추정
    LMEDS = "lmeds"               # 최소 중앙값 제곱 (LMedS)


@unique
class TriangulationMethod(Enum):
    """삼각측량 방법."""

    DLT = "dlt"             # Direct Linear Transform
    MIDPOINT = "midpoint"   # 중점법 (최근접점)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class CameraIntrinsics:
    """
    카메라 내부 파라미터.

    Attributes:
        fx: x축 초점거리 (픽셀)
        fy: y축 초점거리 (픽셀)
        cx: 주점 x좌표 (픽셀)
        cy: 주점 y좌표 (픽셀)
        skew: 축 비틀림 (보통 0)
    """

    fx: float
    fy: float
    cx: float
    cy: float
    skew: float = 0.0

    def __repr__(self) -> str:
        return (
            f"CameraIntrinsics(fx={self.fx:.2f}, fy={self.fy:.2f}, "
            f"cx={self.cx:.2f}, cy={self.cy:.2f}, skew={self.skew:.4f})"
        )

    def to_matrix(self) -> NDArray[np.float64]:
        """3×3 내부 행렬 K 반환."""
        return np.array([
            [self.fx, self.skew, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

    @classmethod
    def from_matrix(cls, K: NDArray[np.float64]) -> CameraIntrinsics:
        """3×3 행렬에서 내부 파라미터 추출."""
        if K.shape != (3, 3):
            raise ValueError(f"내부 행렬은 (3,3) 이어야 합니다: {K.shape}")
        return cls(
            fx=float(K[0, 0]),
            fy=float(K[1, 1]),
            cx=float(K[0, 2]),
            cy=float(K[1, 2]),
            skew=float(K[0, 1]),
        )

    def is_valid(self) -> bool:
        """내부 파라미터 유효성 검사."""
        return self.fx > 0 and self.fy > 0 and self.cx > 0 and self.cy > 0


@dataclass(slots=True)
class DistortionCoeffs:
    """
    렌즈 왜곡 계수.

    Brown-Conrady 모델 기준:
        방사형 왜곡: k1, k2, k3, k4, k5, k6
        접선형 왜곡: p1, p2
        박막 프리즘: s1, s2, s3, s4
        틸트: tau_x, tau_y

    Attributes:
        coeffs: 왜곡 계수 배열 (최대 14개)
        model: 왜곡 모델 유형
    """

    coeffs: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(5, dtype=np.float64)
    )
    model: DistortionModel = DistortionModel.BROWN_CONRADY

    def __repr__(self) -> str:
        arr = np.array2string(self.coeffs, precision=6, separator=", ")
        return f"DistortionCoeffs(model={self.model.value}, coeffs={arr})"

    def to_opencv_vector(self) -> NDArray[np.float64]:
        """OpenCV 호환 왜곡 벡터 반환."""
        return self.coeffs.astype(np.float64).ravel()

    @classmethod
    def from_opencv_vector(
        cls,
        vec: NDArray[np.float64],
        model: DistortionModel | None = None,
    ) -> DistortionCoeffs:
        """OpenCV 왜곡 벡터에서 생성."""
        flat = np.asarray(vec, dtype=np.float64).ravel()
        n = len(flat)
        if n > _MAX_DISTORTION_COEFFS:
            raise ValueError(f"왜곡 계수가 {_MAX_DISTORTION_COEFFS}개를 초과: {n}")
        if model is None:
            model = _infer_distortion_model(n)
        return cls(coeffs=flat, model=model)

    def is_zero(self) -> bool:
        """모든 계수가 0인지 확인."""
        return bool(np.all(np.abs(self.coeffs) < _EPSILON))


@dataclass(slots=True)
class CameraExtrinsics:
    """
    카메라 외부 파라미터 (월드 → 카메라 변환).

    Attributes:
        rotation: 회전 행렬 (3×3, SO(3))
        translation: 이동 벡터 (3,)
    """

    rotation: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )
    translation: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )

    def __repr__(self) -> str:
        r_str = np.array2string(self.rotation, precision=4, separator=", ")
        t_str = np.array2string(self.translation, precision=4, separator=", ")
        return f"CameraExtrinsics(R={r_str}, t={t_str})"

    def to_projection_matrix(self, K: NDArray[np.float64]) -> NDArray[np.float64]:
        """3×4 투영 행렬 P = K · [R | t] 반환."""
        Rt = np.hstack([self.rotation, self.translation.reshape(3, 1)])
        return K @ Rt

    def camera_position(self) -> NDArray[np.float64]:
        """월드 좌표계에서 카메라 위치: C = -R^T · t."""
        return -self.rotation.T @ self.translation

    def is_valid(self) -> bool:
        """외부 파라미터 유효성 검사 (SO(3) 확인)."""
        if self.rotation.shape != (3, 3):
            return False
        orth_err = np.linalg.norm(
            self.rotation.T @ self.rotation - np.eye(3)
        )
        det_err = abs(np.linalg.det(self.rotation) - 1.0)
        return bool(orth_err < 1e-4 and det_err < 1e-4)


@dataclass(slots=True)
class FundamentalResult:
    """
    기본 행렬 추정 결과.

    Attributes:
        F: 기본 행렬 (3×3, rank 2)
        inlier_mask: 인라이어 마스크 (N,) boolean
        num_inliers: 인라이어 수
        method: 사용된 추정 방법
    """

    F: NDArray[np.float64]
    inlier_mask: NDArray[np.bool_]
    num_inliers: int
    method: FundamentalMethod

    def __repr__(self) -> str:
        return (
            f"FundamentalResult(method={self.method.value}, "
            f"inliers={self.num_inliers}/{len(self.inlier_mask)})"
        )


@dataclass(slots=True)
class EssentialDecomposition:
    """
    본질 행렬 분해 결과.

    Attributes:
        R: 회전 행렬 (3×3)
        t: 이동 벡터 (3,) — 정규화됨 (단위벡터)
        num_positive_depth: 양의 깊이 점 수 (4해 중 최적 선택 기준)
    """

    R: NDArray[np.float64]
    t: NDArray[np.float64]
    num_positive_depth: int

    def __repr__(self) -> str:
        t_str = np.array2string(self.t, precision=4, separator=", ")
        return (
            f"EssentialDecomposition(t={t_str}, "
            f"positive_depth={self.num_positive_depth})"
        )


@dataclass(slots=True)
class TriangulationResult:
    """
    삼각측량 결과.

    Attributes:
        points_3d: 3D 점 좌표 (N×3)
        reprojection_errors: 각 점의 리프로젝션 오차 (N,)
        mean_error: 평균 리프로젝션 오차
        method: 사용된 삼각측량 방법
    """

    points_3d: NDArray[np.float64]
    reprojection_errors: NDArray[np.float64]
    mean_error: float
    method: TriangulationMethod

    def __repr__(self) -> str:
        n = self.points_3d.shape[0] if self.points_3d.ndim == 2 else 1
        return (
            f"TriangulationResult(n_points={n}, "
            f"mean_error={self.mean_error:.4f}px, "
            f"method={self.method.value})"
        )


@dataclass(slots=True)
class ReprojectionError:
    """
    리프로젝션 오차 통계.

    Attributes:
        mean: 평균 오차 (픽셀)
        std: 표준편차
        max_error: 최대 오차
        median: 중앙값
        errors: 개별 오차 배열 (N,)
    """

    mean: float
    std: float
    max_error: float
    median: float
    errors: NDArray[np.float64]

    def __repr__(self) -> str:
        return (
            f"ReprojectionError(mean={self.mean:.4f}px, "
            f"std={self.std:.4f}, max={self.max_error:.4f})"
        )


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================

def _infer_distortion_model(n_coeffs: int) -> DistortionModel:
    """왜곡 계수 개수로 모델 유형 추론."""
    if n_coeffs == 0:
        return DistortionModel.NONE
    if n_coeffs <= 2:
        return DistortionModel.RADIAL_2
    if n_coeffs == 3:
        return DistortionModel.RADIAL_3
    if n_coeffs <= 5:
        return DistortionModel.BROWN_CONRADY
    if n_coeffs <= 8:
        return DistortionModel.RATIONAL_6
    return DistortionModel.FULL_14


def _normalize_points_2d(
    points: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    2D 점 정규화 (Hartley 정규화).

    중심을 원점으로 이동하고, 평균 거리를 sqrt(2)로 스케일링.

    Returns:
        (정규화된 점 Nx2, 정규화 변환 행렬 3×3)
    """
    centroid = np.mean(points, axis=0)
    shifted = points - centroid

    mean_dist = np.mean(np.sqrt(np.sum(shifted ** 2, axis=1)))
    if mean_dist < _EPSILON:
        scale = 1.0
    else:
        scale = math.sqrt(2.0) / mean_dist

    T = np.array([
        [scale, 0.0, -scale * centroid[0]],
        [0.0, scale, -scale * centroid[1]],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    pts_h = np.column_stack([points, np.ones(len(points))])
    normalized = (T @ pts_h.T).T[:, :2]

    return normalized, T


def _enforce_rank2(F: NDArray[np.float64]) -> NDArray[np.float64]:
    """기본 행렬의 rank-2 제약 적용 (최소 특이값 → 0)."""
    U, S, Vt = np.linalg.svd(F)
    S[2] = 0.0
    return U @ np.diag(S) @ Vt


def _positive_depth_count(
    R: NDArray[np.float64],
    t: NDArray[np.float64],
    pts1_norm: NDArray[np.float64],
    pts2_norm: NDArray[np.float64],
) -> int:
    """양의 깊이를 가진 점의 수 계산 (E 분해 해 선택용)."""
    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = np.hstack([R, t.reshape(3, 1)])

    count = 0
    n = min(len(pts1_norm), 50)  # 최대 50점만 사용 (속도)

    for i in range(n):
        x1 = pts1_norm[i]
        x2 = pts2_norm[i]

        A = np.array([
            x1[0] * P1[2] - P1[0],
            x1[1] * P1[2] - P1[1],
            x2[0] * P2[2] - P2[0],
            x2[1] * P2[2] - P2[1],
        ], dtype=np.float64)

        _, _, Vt_a = np.linalg.svd(A)
        X = Vt_a[-1]
        X = X / (X[3] + _EPSILON)

        # 첫 번째 카메라에서 깊이
        depth1 = X[2]
        # 두 번째 카메라에서 깊이
        X_cam2 = R @ X[:3] + t
        depth2 = X_cam2[2]

        if depth1 > _POSITIVE_DEPTH_THRESHOLD and depth2 > _POSITIVE_DEPTH_THRESHOLD:
            count += 1

    return count


def _project_point(
    point_3d: NDArray[np.float64],
    K: NDArray[np.float64],
    R: NDArray[np.float64],
    t: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """단일 3D 점을 2D 이미지 좌표로 투영."""
    # 카메라 좌표계로 변환
    p_cam = R @ point_3d + t

    if abs(p_cam[2]) < _EPSILON:
        return np.array([np.inf, np.inf], dtype=np.float64)

    # 정규화 좌표
    x_n = p_cam[0] / p_cam[2]
    y_n = p_cam[1] / p_cam[2]

    # 왜곡 적용
    if dist_coeffs is not None and len(dist_coeffs) > 0:
        x_d, y_d = _apply_distortion(x_n, y_n, dist_coeffs)
    else:
        x_d, y_d = x_n, y_n

    # 픽셀 좌표로 변환
    u = K[0, 0] * x_d + K[0, 1] * y_d + K[0, 2]
    v = K[1, 1] * y_d + K[1, 2]

    return np.array([u, v], dtype=np.float64)


def _apply_distortion(
    x: float,
    y: float,
    coeffs: NDArray[np.float64],
) -> tuple[float, float]:
    """Brown-Conrady 왜곡 모델 적용."""
    r2 = x * x + y * y
    r4 = r2 * r2
    r6 = r2 * r4

    n = len(coeffs)
    k1 = coeffs[0] if n > 0 else 0.0
    k2 = coeffs[1] if n > 1 else 0.0
    p1 = coeffs[2] if n > 2 else 0.0
    p2 = coeffs[3] if n > 3 else 0.0
    k3 = coeffs[4] if n > 4 else 0.0
    k4 = coeffs[5] if n > 5 else 0.0
    k5 = coeffs[6] if n > 6 else 0.0
    k6 = coeffs[7] if n > 7 else 0.0

    # 방사형 왜곡
    radial_num = 1.0 + k1 * r2 + k2 * r4 + k3 * r6
    radial_den = 1.0 + k4 * r2 + k5 * r4 + k6 * r6
    if abs(radial_den) < _EPSILON:
        radial_den = 1.0
    radial = radial_num / radial_den

    # 접선형 왜곡
    x_d = x * radial + 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
    y_d = y * radial + p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y

    return x_d, y_d


# =============================================================================
# 내부 파라미터 함수
# =============================================================================

def build_intrinsic_matrix(
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    skew: float = 0.0,
) -> NDArray[np.float64]:
    """
    3×3 내부 행렬 K 구성.

    Args:
        fx: x축 초점거리 (픽셀)
        fy: y축 초점거리 (픽셀)
        cx: 주점 x좌표
        cy: 주점 y좌표
        skew: 축 비틀림 (기본 0)

    Returns:
        3×3 내부 행렬
    """
    if fx <= 0 or fy <= 0:
        raise ValueError(f"초점거리는 양수여야 합니다: fx={fx}, fy={fy}")
    if cx < 0 or cy < 0:
        raise ValueError(f"주점은 음수일 수 없습니다: cx={cx}, cy={cy}")

    return np.array([
        [fx, skew, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)


def decompose_intrinsic_matrix(
    K: NDArray[np.float64],
) -> CameraIntrinsics:
    """
    3×3 내부 행렬에서 파라미터 추출.

    Args:
        K: 3×3 상삼각 행렬

    Returns:
        CameraIntrinsics 인스턴스
    """
    if K.shape != (3, 3):
        raise ValueError(f"내부 행렬은 (3,3) 이어야 합니다: {K.shape}")
    if abs(K[2, 2]) < _EPSILON:
        raise ValueError("K[2,2]이 0에 가깝습니다 (정규화 오류)")

    # 정규화 (K[2,2] = 1)
    K_norm = K / K[2, 2]

    return CameraIntrinsics(
        fx=float(K_norm[0, 0]),
        fy=float(K_norm[1, 1]),
        cx=float(K_norm[0, 2]),
        cy=float(K_norm[1, 2]),
        skew=float(K_norm[0, 1]),
    )


def validate_intrinsic_matrix(
    K: NDArray[np.float64],
) -> bool:
    """
    내부 행렬 유효성 검사.

    조건: 상삼각, K[2,2]≈1, fx>0, fy>0, cx>0, cy>0

    Args:
        K: 3×3 행렬

    Returns:
        유효 여부
    """
    if not isinstance(K, np.ndarray) or K.shape != (3, 3):
        return False

    # 하삼각 요소 확인
    if abs(K[1, 0]) > _EPSILON or abs(K[2, 0]) > _EPSILON or abs(K[2, 1]) > _EPSILON:
        return False

    # K[2,2] ≈ 1
    if abs(K[2, 2] - 1.0) > 1e-4:
        return False

    # 양수 초점거리
    if K[0, 0] <= 0 or K[1, 1] <= 0:
        return False

    return True


# =============================================================================
# 왜곡 보정 함수
# =============================================================================

def undistort_points(
    points: NDArray[np.float64],
    K: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64],
    new_K: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """
    2D 점 왜곡 보정.

    Args:
        points: 왜곡된 2D 점 (N×2)
        K: 내부 행렬 (3×3)
        dist_coeffs: 왜곡 계수
        new_K: 보정 후 적용할 새 내부 행렬 (None → K 사용)

    Returns:
        보정된 2D 점 (N×2)
    """
    if points.ndim == 1:
        points = points.reshape(1, 2)

    if points.shape[1] != 2:
        raise ValueError(f"점은 (N,2) 형태여야 합니다: {points.shape}")

    n = points.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    # OpenCV 호환 형태로 변환
    pts_cv = points.reshape(-1, 1, 2).astype(np.float64)
    d = dist_coeffs.ravel().astype(np.float64)

    undistorted = cv2.undistortPoints(
        pts_cv, K, d, P=new_K if new_K is not None else K,
    )

    return undistorted.reshape(-1, 2)


def undistort_image(
    image: NDArray[np.uint8],
    K: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64],
    new_K: NDArray[np.float64] | None = None,
) -> NDArray[np.uint8]:
    """
    이미지 왜곡 보정.

    Args:
        image: 입력 이미지 (H×W×C 또는 H×W)
        K: 내부 행렬 (3×3)
        dist_coeffs: 왜곡 계수
        new_K: 보정 후 새 내부 행렬 (None → K 사용)

    Returns:
        왜곡 보정된 이미지
    """
    if image.ndim < 2:
        raise ValueError(f"이미지는 최소 2차원이어야 합니다: ndim={image.ndim}")

    d = dist_coeffs.ravel().astype(np.float64)

    return cv2.undistort(
        image, K, d, newCameraMatrix=new_K,
    )


def distort_points(
    points_undistorted: NDArray[np.float64],
    K: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    보정된 점에 왜곡 재적용 (역변환).

    정규화 좌표에서 왜곡 모델을 적용 후 K로 투영.

    Args:
        points_undistorted: 보정된 2D 점 (N×2)
        K: 내부 행렬 (3×3)
        dist_coeffs: 왜곡 계수

    Returns:
        왜곡된 2D 점 (N×2)
    """
    if points_undistorted.ndim == 1:
        points_undistorted = points_undistorted.reshape(1, 2)

    n = points_undistorted.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    coeffs = dist_coeffs.ravel().astype(np.float64)
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    skew = K[0, 1]

    result = np.empty_like(points_undistorted)

    for i in range(n):
        # 정규화 좌표로 변환
        x_n = (points_undistorted[i, 0] - cx - skew * (points_undistorted[i, 1] - cy) / fy) / fx
        y_n = (points_undistorted[i, 1] - cy) / fy

        # 왜곡 적용
        x_d, y_d = _apply_distortion(x_n, y_n, coeffs)

        # 픽셀 좌표로
        result[i, 0] = fx * x_d + skew * y_d + cx
        result[i, 1] = fy * y_d + cy

    return result


# =============================================================================
# 기본 행렬 / 본질 행렬 추정
# =============================================================================

def compute_fundamental_matrix(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    method: FundamentalMethod = FundamentalMethod.RANSAC,
    ransac_threshold: float = DEFAULT_RANSAC_THRESHOLD,
    confidence: float = DEFAULT_RANSAC_CONFIDENCE,
) -> FundamentalResult:
    """
    두 뷰의 대응점으로 기본 행렬 F 추정.

    x2^T · F · x1 = 0

    Args:
        pts1: 첫 번째 뷰 2D 점 (N×2)
        pts2: 두 번째 뷰 2D 점 (N×2)
        method: 추정 방법
        ransac_threshold: RANSAC 인라이어 임계값 (픽셀)
        confidence: RANSAC 신뢰도

    Returns:
        FundamentalResult
    """
    if pts1.shape != pts2.shape:
        raise ValueError(
            f"대응점 크기 불일치: {pts1.shape} vs {pts2.shape}"
        )
    n = pts1.shape[0]
    if n < MIN_POINTS_FUNDAMENTAL:
        raise ValueError(
            f"최소 {MIN_POINTS_FUNDAMENTAL}개 대응점 필요: {n}개 제공"
        )

    if method == FundamentalMethod.EIGHT_POINT:
        F, mask = _compute_fundamental_8point(pts1, pts2)
    elif method == FundamentalMethod.RANSAC:
        F, mask = cv2.findFundamentalMat(
            pts1.astype(np.float64),
            pts2.astype(np.float64),
            cv2.FM_RANSAC,
            ransac_threshold,
            confidence,
        )
        if mask is None:
            mask = np.ones(n, dtype=np.uint8)
        mask = mask.ravel().astype(bool)
    elif method == FundamentalMethod.LMEDS:
        F, mask = cv2.findFundamentalMat(
            pts1.astype(np.float64),
            pts2.astype(np.float64),
            cv2.FM_LMEDS,
            confidence,
        )
        if mask is None:
            mask = np.ones(n, dtype=np.uint8)
        mask = mask.ravel().astype(bool)
    else:
        raise ValueError(f"지원하지 않는 기본 행렬 추정 방법: {method}")

    if F is None or F.shape != (3, 3):
        logger.warning("기본 행렬 추정 실패, 영행렬 반환")
        F = np.zeros((3, 3), dtype=np.float64)
        mask = np.zeros(n, dtype=bool)

    return FundamentalResult(
        F=F,
        inlier_mask=mask,
        num_inliers=int(np.sum(mask)),
        method=method,
    )


def _compute_fundamental_8point(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """정규화 8점 알고리즘으로 기본 행렬 계산."""
    # Hartley 정규화
    pts1_norm, T1 = _normalize_points_2d(pts1)
    pts2_norm, T2 = _normalize_points_2d(pts2)

    n = pts1_norm.shape[0]

    # 계수 행렬 A 구성 (Nx9)
    A = np.empty((n, 9), dtype=np.float64)
    for i in range(n):
        x1, y1 = pts1_norm[i]
        x2, y2 = pts2_norm[i]
        A[i] = [
            x2 * x1, x2 * y1, x2,
            y2 * x1, y2 * y1, y2,
            x1, y1, 1.0,
        ]

    # SVD로 해 구하기
    _, _, Vt = np.linalg.svd(A)
    F_norm = Vt[-1].reshape(3, 3)

    # Rank-2 강제
    F_norm = _enforce_rank2(F_norm)

    # 역정규화
    F = T2.T @ F_norm @ T1

    # 스케일 정규화
    f_norm = np.linalg.norm(F)
    if f_norm > _EPSILON:
        F = F / f_norm

    mask = np.ones(n, dtype=bool)
    return F, mask


def compute_essential_matrix(
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    K1: NDArray[np.float64],
    K2: NDArray[np.float64] | None = None,
    method: FundamentalMethod = FundamentalMethod.RANSAC,
    ransac_threshold: float = DEFAULT_RANSAC_THRESHOLD,
) -> NDArray[np.float64]:
    """
    본질 행렬 E 계산.

    E = K2^T · F · K1

    Args:
        pts1: 첫 번째 뷰 2D 점 (N×2)
        pts2: 두 번째 뷰 2D 점 (N×2)
        K1: 첫 번째 카메라 내부 행렬
        K2: 두 번째 카메라 내부 행렬 (None → K1과 동일)
        method: F 추정 방법
        ransac_threshold: RANSAC 임계값

    Returns:
        본질 행렬 E (3×3)
    """
    if K2 is None:
        K2 = K1

    result = compute_fundamental_matrix(
        pts1, pts2, method=method, ransac_threshold=ransac_threshold,
    )
    E = K2.T @ result.F @ K1

    # 특이값 정규화 (σ, σ, 0)
    U, S, Vt = np.linalg.svd(E)
    s_mean = (S[0] + S[1]) / 2.0
    E_corrected = U @ np.diag([s_mean, s_mean, 0.0]) @ Vt

    return E_corrected


def decompose_essential_matrix(
    E: NDArray[np.float64],
    pts1_normalized: NDArray[np.float64],
    pts2_normalized: NDArray[np.float64],
) -> EssentialDecomposition:
    """
    본질 행렬을 R, t로 분해 (4해 중 양의 깊이 해 선택).

    Args:
        E: 본질 행렬 (3×3)
        pts1_normalized: 정규화된 1뷰 점 (N×2) — K^-1 적용 후
        pts2_normalized: 정규화된 2뷰 점 (N×2) — K^-1 적용 후

    Returns:
        EssentialDecomposition (최적 R, t)
    """
    U, _, Vt = np.linalg.svd(E)

    # det(U), det(Vt) = +1 보장
    if np.linalg.det(U) < 0:
        U[:, 2] *= -1
    if np.linalg.det(Vt) < 0:
        Vt[2, :] *= -1

    # W 행렬 (90도 회전)
    W = np.array([
        [0, -1, 0],
        [1, 0, 0],
        [0, 0, 1],
    ], dtype=np.float64)

    # 4가지 가능한 해
    R1 = U @ W @ Vt
    R2 = U @ W.T @ Vt
    t1 = U[:, 2]
    t2 = -U[:, 2]

    candidates = [(R1, t1), (R1, t2), (R2, t1), (R2, t2)]

    best_R, best_t, best_count = R1, t1, 0

    for R_cand, t_cand in candidates:
        count = _positive_depth_count(R_cand, t_cand, pts1_normalized, pts2_normalized)
        if count > best_count:
            best_count = count
            best_R = R_cand
            best_t = t_cand

    return EssentialDecomposition(
        R=best_R,
        t=best_t,
        num_positive_depth=best_count,
    )


# =============================================================================
# 에피폴라 기하학
# =============================================================================

def compute_epipole(F: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    기본 행렬 F에서 에피폴 계산.

    F·e = 0 → e는 F의 우측 영공간 (SVD 최소 특이값 벡터).

    Args:
        F: 기본 행렬 (3×3)

    Returns:
        에피폴 좌표 (2,) — 비동차 좌표
    """
    _, _, Vt = np.linalg.svd(F)
    e_homog = Vt[-1]

    if abs(e_homog[2]) < _EPSILON:
        logger.warning("에피폴이 무한원점에 위치 (평행 카메라)")
        return np.array([np.inf, np.inf], dtype=np.float64)

    return (e_homog[:2] / e_homog[2]).astype(np.float64)


def compute_epipolar_line(
    F: NDArray[np.float64],
    point: NDArray[np.float64],
    from_first_view: bool = True,
) -> NDArray[np.float64]:
    """
    한 뷰의 점에 대응하는 에피폴라 라인 계산.

    Args:
        F: 기본 행렬 (3×3)
        point: 점 좌표 (2,)
        from_first_view: True → l' = F·x, False → l = F^T·x'

    Returns:
        에피폴라 라인 (3,) — ax + by + c = 0
    """
    pt_h = np.array([point[0], point[1], 1.0], dtype=np.float64)

    if from_first_view:
        line = F @ pt_h
    else:
        line = F.T @ pt_h

    # 정규화 (a² + b² = 1)
    norm = math.sqrt(line[0] ** 2 + line[1] ** 2)
    if norm > _EPSILON:
        line = line / norm

    return line


def point_to_epipolar_distance(
    point: NDArray[np.float64],
    epipolar_line: NDArray[np.float64],
) -> float:
    """
    점과 에피폴라 라인 사이 거리.

    d = |a·x + b·y + c| / sqrt(a² + b²)

    Args:
        point: 2D 점 (2,)
        epipolar_line: 라인 (a, b, c)

    Returns:
        거리 (픽셀)
    """
    a, b, c = epipolar_line
    denom = math.sqrt(a * a + b * b)
    if denom < _EPSILON:
        return float("inf")

    return abs(a * point[0] + b * point[1] + c) / denom


# =============================================================================
# 삼각측량
# =============================================================================

def triangulate_points_dlt(
    P1: NDArray[np.float64],
    P2: NDArray[np.float64],
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    DLT (Direct Linear Transform) 삼각측량.

    Args:
        P1: 첫 번째 투영 행렬 (3×4)
        P2: 두 번째 투영 행렬 (3×4)
        pts1: 첫 번째 뷰 점 (N×2)
        pts2: 두 번째 뷰 점 (N×2)

    Returns:
        3D 점 (N×3)
    """
    if pts1.shape != pts2.shape:
        raise ValueError(f"대응점 크기 불일치: {pts1.shape} vs {pts2.shape}")

    n = pts1.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    points_3d = np.empty((n, 3), dtype=np.float64)

    for i in range(n):
        x1, y1 = pts1[i]
        x2, y2 = pts2[i]

        A = np.array([
            x1 * P1[2] - P1[0],
            y1 * P1[2] - P1[1],
            x2 * P2[2] - P2[0],
            y2 * P2[2] - P2[1],
        ], dtype=np.float64)

        _, _, Vt = np.linalg.svd(A)
        X = Vt[-1]

        if abs(X[3]) < _EPSILON:
            points_3d[i] = [np.inf, np.inf, np.inf]
        else:
            points_3d[i] = X[:3] / X[3]

    return points_3d


def triangulate_points_midpoint(
    camera_pos1: NDArray[np.float64],
    ray_dir1: NDArray[np.float64],
    camera_pos2: NDArray[np.float64],
    ray_dir2: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    중점법 삼각측량 (두 광선의 최근접점의 중점).

    Args:
        camera_pos1: 첫 번째 카메라 위치 (3,)
        ray_dir1: 첫 번째 광선 방향 (N×3, 단위벡터)
        camera_pos2: 두 번째 카메라 위치 (3,)
        ray_dir2: 두 번째 광선 방향 (N×3, 단위벡터)

    Returns:
        3D 점 (N×3)
    """
    if ray_dir1.ndim == 1:
        ray_dir1 = ray_dir1.reshape(1, 3)
        ray_dir2 = ray_dir2.reshape(1, 3)

    n = ray_dir1.shape[0]
    points_3d = np.empty((n, 3), dtype=np.float64)

    for i in range(n):
        d1 = ray_dir1[i]
        d2 = ray_dir2[i]
        w = camera_pos1 - camera_pos2

        a = float(np.dot(d1, d1))
        b = float(np.dot(d1, d2))
        c = float(np.dot(d2, d2))
        d = float(np.dot(d1, w))
        e = float(np.dot(d2, w))

        denom = a * c - b * b
        if abs(denom) < _EPSILON:
            # 평행 광선 → 중점
            points_3d[i] = (camera_pos1 + camera_pos2) / 2.0
            continue

        s = (b * e - c * d) / denom
        t = (a * e - b * d) / denom

        closest1 = camera_pos1 + s * d1
        closest2 = camera_pos2 + t * d2

        points_3d[i] = (closest1 + closest2) / 2.0

    return points_3d


def triangulate_points(
    P1: NDArray[np.float64],
    P2: NDArray[np.float64],
    pts1: NDArray[np.float64],
    pts2: NDArray[np.float64],
    method: TriangulationMethod = TriangulationMethod.DLT,
    K1: NDArray[np.float64] | None = None,
    K2: NDArray[np.float64] | None = None,
    dist_coeffs1: NDArray[np.float64] | None = None,
    dist_coeffs2: NDArray[np.float64] | None = None,
) -> TriangulationResult:
    """
    삼각측량 통합 인터페이스.

    Args:
        P1: 첫 번째 투영 행렬 (3×4)
        P2: 두 번째 투영 행렬 (3×4)
        pts1: 첫 번째 뷰 점 (N×2)
        pts2: 두 번째 뷰 점 (N×2)
        method: 삼각측량 방법
        K1: 첫 번째 카메라 내부 행렬 (왜곡 보정용)
        K2: 두 번째 카메라 내부 행렬 (왜곡 보정용)
        dist_coeffs1: 첫 번째 카메라 왜곡 계수
        dist_coeffs2: 두 번째 카메라 왜곡 계수

    Returns:
        TriangulationResult
    """
    # 왜곡 보정 (선택적)
    pts1_corr = pts1
    pts2_corr = pts2

    if K1 is not None and dist_coeffs1 is not None:
        pts1_corr = undistort_points(pts1, K1, dist_coeffs1)
    if K2 is not None and dist_coeffs2 is not None:
        pts2_corr = undistort_points(pts2, K2, dist_coeffs2)

    if method == TriangulationMethod.DLT:
        points_3d = triangulate_points_dlt(P1, P2, pts1_corr, pts2_corr)
    elif method == TriangulationMethod.MIDPOINT:
        # P → [R|t] 추출 후 중점법
        R1_ext, t1_ext, R2_ext, t2_ext = _extract_Rt_from_P(P1, P2)
        cam1_pos = -R1_ext.T @ t1_ext
        cam2_pos = -R2_ext.T @ t2_ext

        # 광선 방향 계산
        K1_mat = P1[:, :3]
        K2_mat = P2[:, :3]
        rays1 = _compute_ray_directions(pts1_corr, K1_mat, R1_ext)
        rays2 = _compute_ray_directions(pts2_corr, K2_mat, R2_ext)

        points_3d = triangulate_points_midpoint(cam1_pos, rays1, cam2_pos, rays2)
    else:
        raise ValueError(f"지원하지 않는 삼각측량 방법: {method}")

    # 리프로젝션 오차 계산
    errors = compute_reprojection_errors(points_3d, pts1, P1, pts2, P2)

    return TriangulationResult(
        points_3d=points_3d,
        reprojection_errors=errors,
        mean_error=float(np.mean(errors)) if len(errors) > 0 else 0.0,
        method=method,
    )


def _extract_Rt_from_P(
    P1: NDArray[np.float64],
    P2: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """투영 행렬에서 [R|t] 추출 (RQ 분해)."""
    # P = K[R|t] → M = P[:,:3] = KR, KR → RQ 분해
    def _rq_decompose(M: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        Q, R_mat = np.linalg.qr(np.flipud(M).T)
        R_out = np.flipud(R_mat.T)
        R_out = np.fliplr(R_out)
        Q_out = Q.T
        Q_out = np.flipud(Q_out)

        # K 대각 양수 보장
        for i in range(3):
            if R_out[i, i] < 0:
                R_out[:, i] *= -1
                Q_out[i, :] *= -1
        return R_out, Q_out

    K1_mat, R1 = _rq_decompose(P1[:, :3])
    t1 = np.linalg.solve(K1_mat, P1[:, 3])

    K2_mat, R2 = _rq_decompose(P2[:, :3])
    t2 = np.linalg.solve(K2_mat, P2[:, 3])

    return R1, t1, R2, t2


def _compute_ray_directions(
    pts: NDArray[np.float64],
    K: NDArray[np.float64],
    R: NDArray[np.float64],
) -> NDArray[np.float64]:
    """2D 점으로부터 월드 좌표계 광선 방향 계산."""
    K_inv = np.linalg.inv(K)
    pts_h = np.column_stack([pts, np.ones(len(pts))])
    rays_cam = (K_inv @ pts_h.T).T
    rays_world = (R.T @ rays_cam.T).T

    norms = np.linalg.norm(rays_world, axis=1, keepdims=True)
    norms = np.maximum(norms, _EPSILON)
    return rays_world / norms


# =============================================================================
# 리프로젝션 오차
# =============================================================================

def compute_reprojection_errors(
    points_3d: NDArray[np.float64],
    pts_view1: NDArray[np.float64],
    P1: NDArray[np.float64],
    pts_view2: NDArray[np.float64],
    P2: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    리프로젝션 오차 계산 (두 뷰 평균).

    Args:
        points_3d: 3D 점 (N×3)
        pts_view1: 뷰1 관측 점 (N×2)
        P1: 뷰1 투영 행렬 (3×4)
        pts_view2: 뷰2 관측 점 (N×2)
        P2: 뷰2 투영 행렬 (3×4)

    Returns:
        각 점의 리프로젝션 오차 (N,)
    """
    n = points_3d.shape[0]
    errors = np.empty(n, dtype=np.float64)

    pts_h = np.column_stack([points_3d, np.ones(n)])

    # 뷰 1 리프로젝션
    proj1 = (P1 @ pts_h.T).T
    valid1 = np.abs(proj1[:, 2]) > _EPSILON
    proj1_2d = np.zeros((n, 2), dtype=np.float64)
    proj1_2d[valid1, 0] = proj1[valid1, 0] / proj1[valid1, 2]
    proj1_2d[valid1, 1] = proj1[valid1, 1] / proj1[valid1, 2]

    # 뷰 2 리프로젝션
    proj2 = (P2 @ pts_h.T).T
    valid2 = np.abs(proj2[:, 2]) > _EPSILON
    proj2_2d = np.zeros((n, 2), dtype=np.float64)
    proj2_2d[valid2, 0] = proj2[valid2, 0] / proj2[valid2, 2]
    proj2_2d[valid2, 1] = proj2[valid2, 1] / proj2[valid2, 2]

    err1 = np.linalg.norm(proj1_2d - pts_view1, axis=1)
    err2 = np.linalg.norm(proj2_2d - pts_view2, axis=1)

    errors = (err1 + err2) / 2.0

    # 무효 점 처리
    invalid = ~(valid1 & valid2)
    errors[invalid] = np.inf

    return errors


def compute_reprojection_stats(
    points_3d: NDArray[np.float64],
    pts_observed: NDArray[np.float64],
    P: NDArray[np.float64],
) -> ReprojectionError:
    """
    단일 뷰 리프로젝션 오차 통계.

    Args:
        points_3d: 3D 점 (N×3)
        pts_observed: 관측 2D 점 (N×2)
        P: 투영 행렬 (3×4)

    Returns:
        ReprojectionError 통계
    """
    n = points_3d.shape[0]
    pts_h = np.column_stack([points_3d, np.ones(n)])
    proj = (P @ pts_h.T).T

    valid = np.abs(proj[:, 2]) > _EPSILON
    proj_2d = np.full((n, 2), np.inf, dtype=np.float64)
    proj_2d[valid, 0] = proj[valid, 0] / proj[valid, 2]
    proj_2d[valid, 1] = proj[valid, 1] / proj[valid, 2]

    errors = np.linalg.norm(proj_2d - pts_observed, axis=1)
    errors[~valid] = np.inf

    # 유효 오차만 통계 계산
    valid_errors = errors[valid]
    if len(valid_errors) == 0:
        return ReprojectionError(
            mean=float("inf"),
            std=0.0,
            max_error=float("inf"),
            median=float("inf"),
            errors=errors,
        )

    return ReprojectionError(
        mean=float(np.mean(valid_errors)),
        std=float(np.std(valid_errors)),
        max_error=float(np.max(valid_errors)),
        median=float(np.median(valid_errors)),
        errors=errors,
    )


# =============================================================================
# 투영 행렬 유틸리티
# =============================================================================

def build_projection_matrix(
    K: NDArray[np.float64],
    R: NDArray[np.float64],
    t: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    투영 행렬 P = K · [R | t] 구성.

    Args:
        K: 내부 행렬 (3×3)
        R: 회전 행렬 (3×3)
        t: 이동 벡터 (3,)

    Returns:
        투영 행렬 (3×4)
    """
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


def decompose_projection_matrix(
    P: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """
    투영 행렬 P를 K, R, t로 분해 (RQ 분해).

    Args:
        P: 투영 행렬 (3×4)

    Returns:
        (K, R, t) — 내부행렬, 회전행렬, 이동벡터
    """
    if P.shape != (3, 4):
        raise ValueError(f"투영 행렬은 (3,4) 이어야 합니다: {P.shape}")

    # OpenCV decomposeProjectionMatrix 사용
    ret_vals = cv2.decomposeProjectionMatrix(P)
    K = ret_vals[0]
    R = ret_vals[1]
    t_homog = ret_vals[2]

    # K 정규화
    K = K / K[2, 2]

    # t 비동차화
    if abs(t_homog[3]) > _EPSILON:
        t = (t_homog[:3] / t_homog[3]).ravel()
    else:
        t = t_homog[:3].ravel()

    return K, R, t


# =============================================================================
# 좌표 변환 유틸리티
# =============================================================================

def pixel_to_normalized(
    points: NDArray[np.float64],
    K: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    픽셀 좌표 → 정규화 카메라 좌표 변환.

    x_n = K^(-1) · [u, v, 1]^T

    Args:
        points: 픽셀 좌표 (N×2)
        K: 내부 행렬 (3×3)

    Returns:
        정규화 좌표 (N×2)
    """
    if points.ndim == 1:
        points = points.reshape(1, 2)

    K_inv = np.linalg.inv(K)
    pts_h = np.column_stack([points, np.ones(len(points))])
    normalized = (K_inv @ pts_h.T).T

    return normalized[:, :2]


def normalized_to_pixel(
    points_normalized: NDArray[np.float64],
    K: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    정규화 카메라 좌표 → 픽셀 좌표 변환.

    [u, v, 1]^T = K · [x_n, y_n, 1]^T

    Args:
        points_normalized: 정규화 좌표 (N×2)
        K: 내부 행렬 (3×3)

    Returns:
        픽셀 좌표 (N×2)
    """
    if points_normalized.ndim == 1:
        points_normalized = points_normalized.reshape(1, 2)

    pts_h = np.column_stack([points_normalized, np.ones(len(points_normalized))])
    pixels = (K @ pts_h.T).T

    return pixels[:, :2]


def world_to_pixel(
    points_3d: NDArray[np.float64],
    K: NDArray[np.float64],
    R: NDArray[np.float64],
    t: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """
    월드 좌표 → 픽셀 좌표 변환 (투영).

    Args:
        points_3d: 3D 월드 좌표 (N×3)
        K: 내부 행렬 (3×3)
        R: 회전 행렬 (3×3)
        t: 이동 벡터 (3,)
        dist_coeffs: 왜곡 계수 (선택)

    Returns:
        픽셀 좌표 (N×2)
    """
    if points_3d.ndim == 1:
        points_3d = points_3d.reshape(1, 3)

    n = points_3d.shape[0]
    if n > _MAX_BATCH_SIZE:
        raise ValueError(f"배치 크기 초과: {n} > {_MAX_BATCH_SIZE}")

    result = np.empty((n, 2), dtype=np.float64)
    d = dist_coeffs if dist_coeffs is not None else None

    for i in range(n):
        result[i] = _project_point(points_3d[i], K, R, t, d)

    return result


def pixel_to_ray(
    points: NDArray[np.float64],
    K: NDArray[np.float64],
    R: NDArray[np.float64],
    dist_coeffs: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """
    픽셀 좌표 → 월드 좌표계 광선 방향 변환.

    Args:
        points: 픽셀 좌표 (N×2)
        K: 내부 행렬 (3×3)
        R: 회전 행렬 (3×3) — 월드→카메라
        dist_coeffs: 왜곡 계수 (선택)

    Returns:
        광선 방향 (N×3, 단위벡터)
    """
    if points.ndim == 1:
        points = points.reshape(1, 2)

    # 왜곡 보정
    if dist_coeffs is not None:
        points_corrected = undistort_points(points, K, dist_coeffs)
    else:
        points_corrected = points

    # 정규화 좌표로 변환
    pts_norm = pixel_to_normalized(points_corrected, K)

    # 카메라 좌표계 광선
    rays_cam = np.column_stack([pts_norm, np.ones(len(pts_norm))])

    # 월드 좌표계로 변환
    rays_world = (R.T @ rays_cam.T).T

    # 정규화
    norms = np.linalg.norm(rays_world, axis=1, keepdims=True)
    norms = np.maximum(norms, _EPSILON)

    return rays_world / norms


# =============================================================================
# 배치 연산
# =============================================================================

def batch_undistort_points(
    points_list: list[NDArray[np.float64]],
    K_list: list[NDArray[np.float64]],
    dist_list: list[NDArray[np.float64]],
) -> list[NDArray[np.float64]]:
    """
    다중 카메라 일괄 왜곡 보정.

    Args:
        points_list: 각 카메라의 점 목록
        K_list: 각 카메라의 내부 행렬 목록
        dist_list: 각 카메라의 왜곡 계수 목록

    Returns:
        보정된 점 목록
    """
    if not (len(points_list) == len(K_list) == len(dist_list)):
        raise ValueError("모든 리스트의 길이가 동일해야 합니다")

    results = []
    for pts, K, d in zip(points_list, K_list, dist_list):
        results.append(undistort_points(pts, K, d))

    return results


def batch_project_points(
    points_3d: NDArray[np.float64],
    cameras: list[tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]],
) -> list[NDArray[np.float64]]:
    """
    3D 점을 다중 카메라에 일괄 투영.

    Args:
        points_3d: 3D 점 (N×3)
        cameras: [(K, R, t), ...] 카메라 파라미터 튜플 목록

    Returns:
        각 카메라의 2D 투영 점 목록
    """
    results = []
    for K, R, t in cameras:
        projected = world_to_pixel(points_3d, K, R, t)
        results.append(projected)

    return results


# =============================================================================
# 카메라 시야각 / 해상도 유틸리티
# =============================================================================

def compute_field_of_view(
    focal_length: float,
    sensor_size: float,
) -> float:
    """
    시야각 (Field of View) 계산.

    FOV = 2 · arctan(sensor_size / (2 · focal_length))

    Args:
        focal_length: 초점거리 (픽셀 또는 mm)
        sensor_size: 센서 크기 (같은 단위: 픽셀 → 이미지 크기, mm → 물리 센서)

    Returns:
        시야각 (라디안)
    """
    if focal_length <= 0:
        raise ValueError(f"초점거리는 양수여야 합니다: {focal_length}")
    if sensor_size <= 0:
        raise ValueError(f"센서 크기는 양수여야 합니다: {sensor_size}")

    return 2.0 * math.atan(sensor_size / (2.0 * focal_length))


def compute_focal_from_fov(
    fov_radians: float,
    sensor_size: float,
) -> float:
    """
    시야각에서 초점거리 역산.

    f = sensor_size / (2 · tan(FOV / 2))

    Args:
        fov_radians: 시야각 (라디안)
        sensor_size: 센서/이미지 크기

    Returns:
        초점거리
    """
    if fov_radians <= 0 or fov_radians >= math.pi:
        raise ValueError(f"시야각은 (0, π) 범위여야 합니다: {fov_radians}")

    half_tan = math.tan(fov_radians / 2.0)
    if half_tan < _EPSILON:
        raise ValueError("시야각이 너무 작아 초점거리를 계산할 수 없습니다")

    return sensor_size / (2.0 * half_tan)


def estimate_depth_accuracy(
    baseline: float,
    focal_length: float,
    disparity: float,
    disparity_error: float = 1.0,
) -> float:
    """
    스테레오 깊이 추정 정확도.

    depth = baseline · f / disparity
    Δdepth ≈ depth² · Δd / (baseline · f)

    Args:
        baseline: 카메라 간 거리 (미터)
        focal_length: 초점거리 (픽셀)
        disparity: 시차 (픽셀)
        disparity_error: 시차 오차 (기본 1 픽셀)

    Returns:
        깊이 오차 (미터)
    """
    if baseline <= 0 or focal_length <= 0:
        raise ValueError("baseline과 focal_length는 양수여야 합니다")
    if disparity < _EPSILON:
        return float("inf")

    depth = baseline * focal_length / disparity
    depth_error = depth * depth * disparity_error / (baseline * focal_length)

    return depth_error


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # === 상수 ===
    "DEFAULT_RANSAC_THRESHOLD",
    "DEFAULT_RANSAC_CONFIDENCE",
    "DEFAULT_RANSAC_MAX_ITERS",
    "REPROJECTION_ERROR_THRESHOLD",
    "MIN_POINTS_FUNDAMENTAL",
    "MIN_POINTS_ESSENTIAL",
    "MIN_PARALLAX_DEGREES",

    # === Enum ===
    "DistortionModel",
    "FundamentalMethod",
    "TriangulationMethod",

    # === 데이터 클래스 ===
    "CameraIntrinsics",
    "DistortionCoeffs",
    "CameraExtrinsics",
    "FundamentalResult",
    "EssentialDecomposition",
    "TriangulationResult",
    "ReprojectionError",

    # === 내부 파라미터 ===
    "build_intrinsic_matrix",
    "decompose_intrinsic_matrix",
    "validate_intrinsic_matrix",

    # === 왜곡 보정 ===
    "undistort_points",
    "undistort_image",
    "distort_points",

    # === 기본 행렬 / 본질 행렬 ===
    "compute_fundamental_matrix",
    "compute_essential_matrix",
    "decompose_essential_matrix",

    # === 에피폴라 기하학 ===
    "compute_epipole",
    "compute_epipolar_line",
    "point_to_epipolar_distance",

    # === 삼각측량 ===
    "triangulate_points_dlt",
    "triangulate_points_midpoint",
    "triangulate_points",

    # === 리프로젝션 오차 ===
    "compute_reprojection_errors",
    "compute_reprojection_stats",

    # === 투영 행렬 ===
    "build_projection_matrix",
    "decompose_projection_matrix",

    # === 좌표 변환 ===
    "pixel_to_normalized",
    "normalized_to_pixel",
    "world_to_pixel",
    "pixel_to_ray",

    # === 배치 연산 ===
    "batch_undistort_points",
    "batch_project_points",

    # === 카메라 시야각 / 깊이 ===
    "compute_field_of_view",
    "compute_focal_from_fov",
    "estimate_depth_accuracy",
]

__version__: str = "1.0.0"
