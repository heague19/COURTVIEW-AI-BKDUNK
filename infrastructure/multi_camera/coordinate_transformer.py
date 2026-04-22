# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/multi_camera
파일: coordinate_transformer.py
설명: 멀티카메라 좌표 변환
      - CoordinateTransformer: 2D↔3D 좌표 변환 (단일 카메라)
      - MultiViewTriangulator: 다중 뷰 3D 삼각측량
      - CourtProjector: 코트 평면 투영 (2D→코트좌표)
      - 월드↔카메라↔픽셀 좌표 변환 체인

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.camera_constants import (
    MAX_CAMERAS,
    MIN_CAMERAS_FOR_TRIANGULATION,
)
from shared.constants.court_constants import (
    COURT_LENGTH_M,
    COURT_WIDTH_M,
)

from infrastructure.multi_camera.camera_calibrator import CalibrationSnapshot


# =============================================================================
# 상수 정의
# =============================================================================

# 부동소수점 비교 임계값
_EPSILON: Final[float] = 1e-10

# 삼각측량 최대 배치 크기
MAX_TRIANGULATION_BATCH: Final[int] = 10_000

# 리프로젝션 오차 기본 임계값 (픽셀)
DEFAULT_REPROJECTION_THRESHOLD: Final[float] = 5.0

# 에피폴라 거리 기본 임계값 (픽셀) — 이상치 필터링
DEFAULT_EPIPOLAR_THRESHOLD: Final[float] = 3.0

# 코트 좌표 범위 (마진 포함, 미터)
COURT_MARGIN_M: Final[float] = 3.0

# 코트 높이 범위 (미터) — 선수/공 높이 가능 범위
COURT_HEIGHT_MIN_M: Final[float] = 0.0
COURT_HEIGHT_MAX_M: Final[float] = 5.0


# =============================================================================
# TriangulationResult: 삼각측량 결과
# =============================================================================

@dataclass(slots=True)
class TriangulatedPoint:
    """삼각측량된 3D 점.

    Attributes:
        point_3d: 3D 좌표 (x, y, z) 미터
        reprojection_error: 평균 리프로젝션 오차 (픽셀)
        num_views: 사용된 뷰 수
        is_valid: 유효성 여부
    """

    point_3d: NDArray[np.float64]
    reprojection_error: float = 0.0
    num_views: int = 0
    is_valid: bool = True

    @property
    def x(self) -> float:
        """X 좌표 (미터)."""
        return float(self.point_3d[0])

    @property
    def y(self) -> float:
        """Y 좌표 (미터)."""
        return float(self.point_3d[1])

    @property
    def z(self) -> float:
        """Z 좌표 (미터, 높이)."""
        return float(self.point_3d[2])

    def __repr__(self) -> str:
        return (
            f"TriangulatedPoint("
            f"x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f}, "
            f"error={self.reprojection_error:.2f}px, "
            f"views={self.num_views})"
        )


# =============================================================================
# CoordinateTransformer: 단일 카메라 좌표 변환
# =============================================================================

class CoordinateTransformer:
    """단일 카메라 좌표 변환.

    캘리브레이션 스냅샷을 사용하여 픽셀↔월드 좌표 변환.

    사용 예시::

        transformer = CoordinateTransformer(snapshot)
        pixel = transformer.world_to_pixel(np.array([5.0, 3.0, 0.0]))
        ray_dir = transformer.pixel_to_ray(np.array([960, 540]))
    """

    __slots__ = (
        "_camera_id",
        "_K",
        "_K_inv",
        "_dist",
        "_R",
        "_t",
        "_P",
        "_camera_pos",
    )

    def __init__(self, snapshot: CalibrationSnapshot) -> None:
        self._camera_id = snapshot.camera_id
        self._K = snapshot.intrinsic_matrix.copy()
        self._K_inv = np.linalg.inv(self._K)
        self._dist = snapshot.distortion_coeffs.copy()
        self._R = snapshot.rotation_matrix.copy()
        self._t = snapshot.translation_vector.copy()

        # 투영 행렬 P = K · [R | t]
        Rt = np.hstack([self._R, self._t.reshape(3, 1)])
        self._P = self._K @ Rt

        # 월드 좌표계에서 카메라 위치: C = -R^T · t
        self._camera_pos = -self._R.T @ self._t

    @property
    def camera_id(self) -> str:
        """카메라 ID."""
        return self._camera_id

    @property
    def projection_matrix(self) -> NDArray[np.float64]:
        """투영 행렬 (3×4) 복사본."""
        return self._P.copy()

    @property
    def camera_position(self) -> NDArray[np.float64]:
        """월드 좌표계에서 카메라 위치 (3,) 복사본."""
        return self._camera_pos.copy()

    @property
    def intrinsic_matrix(self) -> NDArray[np.float64]:
        """내부 행렬 (3×3) 복사본."""
        return self._K.copy()

    def world_to_pixel(self, point_3d: NDArray[np.float64]) -> NDArray[np.float64]:
        """월드 좌표 → 픽셀 좌표 변환 (렌즈 왜곡 적용).

        cv2.projectPoints를 사용하여 렌즈 왜곡이 반영된
        실제 픽셀 좌표를 반환합니다.

        Args:
            point_3d: 3D 월드 좌표 (3,) 또는 (N×3)

        Returns:
            2D 픽셀 좌표 (2,) 또는 (N×2)
        """
        single = point_3d.ndim == 1
        if single:
            point_3d = point_3d.reshape(1, 3)

        n = point_3d.shape[0]

        # 회전 벡터 (cv2.projectPoints 입력 형식)
        rvec, _ = cv2.Rodrigues(self._R)

        # cv2.projectPoints: 3D→2D + 렌즈 왜곡 적용
        projected, _ = cv2.projectPoints(
            point_3d.reshape(-1, 1, 3).astype(np.float64),
            rvec,
            self._t.reshape(3, 1),
            self._K,
            self._dist,
        )
        result = projected.reshape(n, 2)

        return result[0] if single else result

    def pixel_to_ray(self, pixel: NDArray[np.float64]) -> NDArray[np.float64]:
        """픽셀 좌표 → 월드 좌표계 광선 방향 (렌즈 왜곡 보정).

        cv2.undistortPoints로 왜곡을 제거한 정규화 좌표에서
        광선 방향을 계산합니다.

        Args:
            pixel: 2D 픽셀 좌표 (2,) 또는 (N×2)

        Returns:
            단위 광선 방향 (3,) 또는 (N×3)
        """
        single = pixel.ndim == 1
        if single:
            pixel = pixel.reshape(1, 2)

        n = pixel.shape[0]

        # cv2.undistortPoints: 왜곡 제거 + K 역변환 → 정규화 좌표
        undistorted = cv2.undistortPoints(
            pixel.reshape(-1, 1, 2).astype(np.float64),
            self._K,
            self._dist,
        )
        # 정규화 좌표 (x_n, y_n) → 카메라 좌표계 광선 (x_n, y_n, 1)
        rays_cam = np.hstack([
            undistorted.reshape(n, 2),
            np.ones((n, 1), dtype=np.float64),
        ])

        # 월드 좌표계로 변환
        rays_world = (self._R.T @ rays_cam.T).T

        # 단위 벡터화
        norms = np.linalg.norm(rays_world, axis=1, keepdims=True)
        norms = np.maximum(norms, _EPSILON)
        rays_unit = rays_world / norms

        return rays_unit[0] if single else rays_unit

    def undistort_pixel(self, pixel: NDArray[np.float64]) -> NDArray[np.float64]:
        """왜곡된 픽셀 좌표 → 이상적 핀홀 픽셀 좌표.

        렌즈 왜곡을 제거하되, K를 재적용하여
        DLT 투영 행렬 P = K·[R|t]와 호환되는 좌표를 반환합니다.

        Args:
            pixel: 왜곡된 2D 픽셀 좌표 (2,) 또는 (N×2)

        Returns:
            왜곡 보정된 픽셀 좌표 (2,) 또는 (N×2)
        """
        single = pixel.ndim == 1
        if single:
            pixel = pixel.reshape(1, 2)

        # cv2.undistortPoints(P=K): 왜곡 제거 후 K 재적용 → 이상적 픽셀 좌표
        undistorted = cv2.undistortPoints(
            pixel.reshape(-1, 1, 2).astype(np.float64),
            self._K,
            self._dist,
            P=self._K,
        )
        result = undistorted.reshape(-1, 2)

        return result[0] if single else result

    def pixel_to_court_plane(
        self,
        pixel: NDArray[np.float64],
        plane_height: float = 0.0,
    ) -> NDArray[np.float64] | None:
        """픽셀 좌표 → 코트 평면 좌표 (z=plane_height).

        광선과 수평 평면 z=plane_height의 교차점 계산.

        Args:
            pixel: 2D 픽셀 좌표 (2,)
            plane_height: 평면 높이 (미터, 기본 0 = 바닥)

        Returns:
            코트 좌표 (3,) 또는 None (교차 없음)
        """
        ray_dir = self.pixel_to_ray(pixel)
        cam_pos = self._camera_pos

        # 광선: P(t) = cam_pos + t * ray_dir
        # 평면: z = plane_height
        # cam_pos[2] + t * ray_dir[2] = plane_height
        denom = ray_dir[2]
        if abs(denom) < _EPSILON:
            return None

        t = (plane_height - cam_pos[2]) / denom
        if t < 0:
            # 카메라 뒤쪽
            return None

        intersection = cam_pos + t * ray_dir
        return intersection

    def compute_reprojection_error(
        self,
        point_3d: NDArray[np.float64],
        observed_pixel: NDArray[np.float64],
    ) -> float:
        """리프로젝션 오차 계산.

        Args:
            point_3d: 3D 점 (3,)
            observed_pixel: 관측된 픽셀 좌표 (2,)

        Returns:
            오차 (픽셀)
        """
        projected = self.world_to_pixel(point_3d)
        if np.any(np.isinf(projected)):
            return float("inf")
        return float(np.linalg.norm(projected - observed_pixel))

    def __repr__(self) -> str:
        pos = self._camera_pos
        return (
            f"CoordinateTransformer(camera='{self._camera_id}', "
            f"pos=[{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}])"
        )


# =============================================================================
# MultiViewTriangulator: 다중 뷰 삼각측량
# =============================================================================

class MultiViewTriangulator:
    """다중 뷰 DLT 삼각측량 + 에피폴라 검증.

    2대 이상 카메라의 관측으로 3D 위치 추정.
    삼각측량 전 에피폴라 제약으로 이상치(오감지)를 자동 필터링.

    사용 예시::

        triangulator = MultiViewTriangulator()
        triangulator.add_camera(transformer1)
        triangulator.add_camera(transformer2)
        result = triangulator.triangulate({
            "cam_0": np.array([500.0, 300.0]),
            "cam_1": np.array([800.0, 310.0]),
        })
    """

    __slots__ = ("_transformers", "_lock", "_epipolar_threshold")

    def __init__(
        self,
        epipolar_threshold: float = DEFAULT_EPIPOLAR_THRESHOLD,
    ) -> None:
        self._transformers: dict[str, CoordinateTransformer] = {}
        self._lock = threading.RLock()
        self._epipolar_threshold = epipolar_threshold

    @property
    def camera_count(self) -> int:
        """등록된 카메라 수."""
        with self._lock:
            return len(self._transformers)

    def add_camera(self, transformer: CoordinateTransformer) -> bool:
        """카메라 추가.

        Args:
            transformer: 좌표 변환기

        Returns:
            추가 성공 여부
        """
        with self._lock:
            if len(self._transformers) >= MAX_CAMERAS:
                return False
            self._transformers[transformer.camera_id] = transformer
            return True

    def remove_camera(self, camera_id: str) -> bool:
        """카메라 제거.

        Args:
            camera_id: 카메라 ID

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if camera_id in self._transformers:
                del self._transformers[camera_id]
                return True
            return False

    def triangulate(
        self,
        observations: dict[str, NDArray[np.float64]],
        reprojection_threshold: float = DEFAULT_REPROJECTION_THRESHOLD,
    ) -> TriangulatedPoint:
        """다중 뷰 삼각측량 (렌즈 왜곡 자동 보정).

        입력 픽셀 좌표에서 렌즈 왜곡을 제거한 후 DLT 삼각측량을
        수행합니다. 리프로젝션 오차는 왜곡 적용된 픽셀 공간에서 계산.

        Args:
            observations: 카메라 ID → 2D 관측점 (왜곡된 픽셀) 매핑
            reprojection_threshold: 최대 허용 리프로젝션 오차 (픽셀)

        Returns:
            TriangulatedPoint
        """
        with self._lock:
            # 유효한 관측 수집 + 왜곡 보정
            # 3-tuple: (변환기, 왜곡 보정된 좌표, 원본 왜곡 좌표)
            valid_entries: list[
                tuple[CoordinateTransformer, NDArray[np.float64], NDArray[np.float64]]
            ] = []

            for cam_id, pixel in observations.items():
                transformer = self._transformers.get(cam_id)
                if transformer is not None:
                    # 왜곡 제거 → 이상적 핀홀 픽셀 좌표
                    undistorted = transformer.undistort_pixel(pixel)
                    valid_entries.append((transformer, undistorted, pixel.copy()))

            if len(valid_entries) < MIN_CAMERAS_FOR_TRIANGULATION:
                return TriangulatedPoint(
                    point_3d=np.array([0.0, 0.0, 0.0], dtype=np.float64),
                    is_valid=False,
                    num_views=len(valid_entries),
                )

            # 에피폴라 제약으로 이상치 필터링 (3뷰 이상일 때)
            if len(valid_entries) >= 3:
                # 에피폴라 필터링은 (transformer, undistorted) 쌍 사용
                cameras_for_filter = [
                    (t, u) for t, u, _ in valid_entries
                ]
                filtered_cameras = self._filter_epipolar_outliers(
                    cameras_for_filter,
                )
                # 필터링 후에도 최소 뷰 수 충족 확인
                if len(filtered_cameras) >= MIN_CAMERAS_FOR_TRIANGULATION:
                    # 필터링 결과와 동기화된 3-tuple 재구축
                    filtered_set = set(id(t) for t, _ in filtered_cameras)
                    valid_entries = [
                        entry for entry in valid_entries
                        if id(entry[0]) in filtered_set
                    ]

            # DLT 삼각측량용 (transformer, undistorted) 쌍
            valid_cameras = [(t, u) for t, u, _ in valid_entries]
            point_3d = self._dlt_triangulate(valid_cameras)

            # 리프로젝션 오차: 3D→왜곡된 픽셀 vs 원본 관측
            total_error = 0.0
            for transformer, _, original in valid_entries:
                total_error += transformer.compute_reprojection_error(
                    point_3d, original,
                )
            mean_error = total_error / len(valid_entries)

            is_valid = mean_error < reprojection_threshold

            return TriangulatedPoint(
                point_3d=point_3d,
                reprojection_error=mean_error,
                num_views=len(valid_cameras),
                is_valid=is_valid,
            )

    def triangulate_batch(
        self,
        observations_batch: list[dict[str, NDArray[np.float64]]],
        reprojection_threshold: float = DEFAULT_REPROJECTION_THRESHOLD,
    ) -> list[TriangulatedPoint]:
        """배치 삼각측량.

        Args:
            observations_batch: 관측 목록
            reprojection_threshold: 최대 허용 리프로젝션 오차

        Returns:
            TriangulatedPoint 목록
        """
        count = min(len(observations_batch), MAX_TRIANGULATION_BATCH)
        results: list[TriangulatedPoint] = []
        for i in range(count):
            results.append(self.triangulate(
                observations_batch[i],
                reprojection_threshold,
            ))
        return results

    def _dlt_triangulate(
        self,
        cameras: list[tuple[CoordinateTransformer, NDArray[np.float64]]],
    ) -> NDArray[np.float64]:
        """DLT (Direct Linear Transform) 삼각측량.

        Args:
            cameras: (변환기, 관측점) 쌍 목록

        Returns:
            3D 점 (3,)
        """
        n = len(cameras)
        # 각 관측에서 2개 방정식 → 2n×4 행렬
        A = np.empty((2 * n, 4), dtype=np.float64)

        for i, (transformer, pixel) in enumerate(cameras):
            P = transformer.projection_matrix
            x, y = pixel[0], pixel[1]
            A[2 * i] = x * P[2] - P[0]
            A[2 * i + 1] = y * P[2] - P[1]

        # SVD 해법
        _, _, Vt = np.linalg.svd(A)
        X = Vt[-1]

        if abs(X[3]) < _EPSILON:
            return np.array([np.inf, np.inf, np.inf], dtype=np.float64)

        return (X[:3] / X[3]).astype(np.float64)

    def _filter_epipolar_outliers(
        self,
        cameras: list[tuple[CoordinateTransformer, NDArray[np.float64]]],
    ) -> list[tuple[CoordinateTransformer, NDArray[np.float64]]]:
        """에피폴라 제약으로 이상치 관측 필터링.

        기준 뷰(첫 번째)에 대해 나머지 뷰의 에피폴라 거리를
        계산하고, 임계값을 초과하는 관측을 제거합니다.

        기본 행렬 F는 두 카메라의 투영 행렬 P1, P2로부터
        직접 계산합니다 (Hartley & Zisserman, Algorithm 9.1).

        Args:
            cameras: (변환기, 왜곡 보정된 관측점) 쌍 목록

        Returns:
            이상치 제거된 (변환기, 관측점) 쌍 목록
        """
        if len(cameras) < 3:
            # 2개 뷰에서는 필터링하면 삼각측량 불가
            return cameras

        # 기준 뷰: 첫 번째 카메라
        ref_transformer, ref_pixel = cameras[0]
        ref_P = ref_transformer.projection_matrix

        filtered: list[tuple[CoordinateTransformer, NDArray[np.float64]]] = [
            cameras[0],
        ]

        for i in range(1, len(cameras)):
            other_transformer, other_pixel = cameras[i]
            other_P = other_transformer.projection_matrix

            # P1, P2로부터 F 계산: F = [e']_x · P' · P^+
            F = self._fundamental_from_projections(ref_P, other_P)

            # 에피폴라 거리 계산
            distance = self._epipolar_distance(F, ref_pixel, other_pixel)

            if distance <= self._epipolar_threshold:
                filtered.append(cameras[i])

        return filtered

    @staticmethod
    def _fundamental_from_projections(
        P1: NDArray[np.float64],
        P2: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """두 투영 행렬로부터 기본 행렬 F 계산.

        F = [e']_x · P2 · P1^+
        여기서 e' = P2 · C1 (C1은 P1의 null space = 카메라 1 중심)

        학술 근거: Hartley & Zisserman (2004), Result 9.1

        Args:
            P1: 첫 번째 투영 행렬 (3×4)
            P2: 두 번째 투영 행렬 (3×4)

        Returns:
            기본 행렬 F (3×3)
        """
        # P1의 null space → 카메라 1 중심 (동차 좌표)
        _, _, Vt = np.linalg.svd(P1)
        C1 = Vt[-1]  # (4,)

        # e' = P2 · C1 (에피폴)
        e_prime = P2 @ C1
        e_prime = e_prime / (np.linalg.norm(e_prime) + _EPSILON)

        # [e']_x (반대칭 행렬)
        ex = np.array([
            [0.0, -e_prime[2], e_prime[1]],
            [e_prime[2], 0.0, -e_prime[0]],
            [-e_prime[1], e_prime[0], 0.0],
        ], dtype=np.float64)

        # P1^+ (유사 역행렬)
        P1_pinv = np.linalg.pinv(P1)

        # F = [e']_x · P2 · P1^+
        F = ex @ P2 @ P1_pinv

        # 정규화: ||F|| = 1
        norm = np.linalg.norm(F)
        if norm > _EPSILON:
            F = F / norm

        return F

    @staticmethod
    def _epipolar_distance(
        F: NDArray[np.float64],
        pt1: NDArray[np.float64],
        pt2: NDArray[np.float64],
    ) -> float:
        """양방향 에피폴라 거리 계산.

        Sampson 거리의 근사: 양방향 점-선 거리의 평균.

        Args:
            F: 기본 행렬 (3×3)
            pt1: 첫 번째 뷰 관측점 (2,)
            pt2: 두 번째 뷰 관측점 (2,)

        Returns:
            평균 에피폴라 거리 (픽셀)
        """
        pt1_h = np.array([pt1[0], pt1[1], 1.0], dtype=np.float64)
        pt2_h = np.array([pt2[0], pt2[1], 1.0], dtype=np.float64)

        # 순방향: l' = F · x1 → pt2와의 거리
        line_fwd = F @ pt1_h
        denom_fwd = np.sqrt(line_fwd[0] ** 2 + line_fwd[1] ** 2)
        dist_fwd = abs(pt2_h @ line_fwd) / max(denom_fwd, _EPSILON)

        # 역방향: l = F^T · x2 → pt1과의 거리
        line_bwd = F.T @ pt2_h
        denom_bwd = np.sqrt(line_bwd[0] ** 2 + line_bwd[1] ** 2)
        dist_bwd = abs(pt1_h @ line_bwd) / max(denom_bwd, _EPSILON)

        return float((dist_fwd + dist_bwd) / 2.0)

    def __repr__(self) -> str:
        return f"MultiViewTriangulator(cameras={self.camera_count})"


# =============================================================================
# CourtProjector: 코트 평면 투영
# =============================================================================

class CourtProjector:
    """코트 평면 투영.

    멀티카메라 관측을 코트 좌표계(바닥 평면)로 변환.
    삼각측량 결과를 코트 좌표로 정규화.

    사용 예시::

        projector = CourtProjector(court_length=28.0, court_width=15.0)
        court_pos = projector.to_court_coordinates(
            np.array([14.0, 7.5, 0.0])
        )
    """

    __slots__ = (
        "_court_length",
        "_court_width",
        "_court_margin",
        "_x_min",
        "_x_max",
        "_y_min",
        "_y_max",
    )

    def __init__(
        self,
        court_length: float = COURT_LENGTH_M,
        court_width: float = COURT_WIDTH_M,
        margin: float = COURT_MARGIN_M,
    ) -> None:
        self._court_length = court_length
        self._court_width = court_width
        self._court_margin = margin
        self._x_min = -margin
        self._x_max = court_length + margin
        self._y_min = -margin
        self._y_max = court_width + margin

    @property
    def court_length(self) -> float:
        """코트 길이 (미터)."""
        return self._court_length

    @property
    def court_width(self) -> float:
        """코트 너비 (미터)."""
        return self._court_width

    def is_on_court(self, point_3d: NDArray[np.float64]) -> bool:
        """점이 코트 위에 있는지 확인 (마진 포함).

        Args:
            point_3d: 3D 좌표 (3,)

        Returns:
            코트 영역 내 여부
        """
        x, y, z = point_3d[0], point_3d[1], point_3d[2]
        return (
            self._x_min <= x <= self._x_max
            and self._y_min <= y <= self._y_max
            and COURT_HEIGHT_MIN_M <= z <= COURT_HEIGHT_MAX_M
        )

    def to_court_coordinates(
        self,
        point_3d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """월드 3D → 코트 좌표 변환 (바닥 투영).

        z좌표를 유지하면서 x, y를 코트 경계로 클램핑.

        Args:
            point_3d: 3D 좌표 (3,) 또는 (N×3)

        Returns:
            코트 좌표 (3,) 또는 (N×3) — 클램핑된
        """
        single = point_3d.ndim == 1
        if single:
            point_3d = point_3d.reshape(1, 3)

        result = point_3d.copy()
        result[:, 0] = np.clip(result[:, 0], self._x_min, self._x_max)
        result[:, 1] = np.clip(result[:, 1], self._y_min, self._y_max)
        result[:, 2] = np.clip(result[:, 2], COURT_HEIGHT_MIN_M, COURT_HEIGHT_MAX_M)

        return result[0] if single else result

    def to_normalized_coordinates(
        self,
        point_3d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """코트 좌표 → 정규화 좌표 [0, 1] 변환.

        Args:
            point_3d: 3D 코트 좌표 (3,) 또는 (N×3)

        Returns:
            정규화 좌표 (3,) 또는 (N×3)
        """
        single = point_3d.ndim == 1
        if single:
            point_3d = point_3d.reshape(1, 3)

        result = np.empty_like(point_3d)
        result[:, 0] = point_3d[:, 0] / self._court_length if self._court_length > 0 else 0.0
        result[:, 1] = point_3d[:, 1] / self._court_width if self._court_width > 0 else 0.0
        height_range = COURT_HEIGHT_MAX_M - COURT_HEIGHT_MIN_M
        result[:, 2] = (
            (point_3d[:, 2] - COURT_HEIGHT_MIN_M) / height_range
            if height_range > 0 else 0.0
        )

        return result[0] if single else result

    def from_normalized_coordinates(
        self,
        normalized: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """정규화 좌표 [0, 1] → 코트 좌표 변환.

        Args:
            normalized: 정규화 좌표 (3,) 또는 (N×3)

        Returns:
            코트 좌표 (3,) 또는 (N×3)
        """
        single = normalized.ndim == 1
        if single:
            normalized = normalized.reshape(1, 3)

        result = np.empty_like(normalized)
        result[:, 0] = normalized[:, 0] * self._court_length
        result[:, 1] = normalized[:, 1] * self._court_width
        height_range = COURT_HEIGHT_MAX_M - COURT_HEIGHT_MIN_M
        result[:, 2] = normalized[:, 2] * height_range + COURT_HEIGHT_MIN_M

        return result[0] if single else result

    def compute_court_distance(
        self,
        point1: NDArray[np.float64],
        point2: NDArray[np.float64],
    ) -> float:
        """코트 위 두 점 사이 거리 (바닥 평면, 미터).

        Args:
            point1: 첫 번째 점 (3,)
            point2: 두 번째 점 (3,)

        Returns:
            2D 거리 (미터, z 무시)
        """
        dx = point1[0] - point2[0]
        dy = point1[1] - point2[1]
        return float(np.sqrt(dx * dx + dy * dy))

    def __repr__(self) -> str:
        return (
            f"CourtProjector({self._court_length:.1f}m×{self._court_width:.1f}m, "
            f"margin={self._court_margin:.1f}m)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "CoordinateTransformer",
    "MultiViewTriangulator",
    "CourtProjector",
    # 데이터 클래스
    "TriangulatedPoint",
    # 상수
    "MAX_TRIANGULATION_BATCH",
    "DEFAULT_REPROJECTION_THRESHOLD",
    "DEFAULT_EPIPOLAR_THRESHOLD",
    "COURT_MARGIN_M",
    "COURT_HEIGHT_MIN_M",
    "COURT_HEIGHT_MAX_M",
]

__version__ = "1.0.0"
