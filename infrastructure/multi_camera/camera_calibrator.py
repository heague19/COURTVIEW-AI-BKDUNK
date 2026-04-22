# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/multi_camera
파일: camera_calibrator.py
설명: 카메라 캘리브레이션 오케스트레이터
      - SingleCameraCalibrator: 개별 카메라 내부/외부 파라미터 캘리브레이션
      - StereoCalibratorPair: 두 카메라 간 스테레오 캘리브레이션
      - MultiCameraCalibrator: 전체 멀티카메라 시스템 캘리브레이션
      - CalibrationSnapshot: 캘리브레이션 결과 스냅샷 (직렬화/캐싱용)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID, uuid4

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
    CALIBRATION_COVERAGE_RATIO,
    CALIBRATION_MIN_IMAGES,
    CHESSBOARD_SIZE,
    CHESSBOARD_SQUARE_SIZE_MM,
    MAX_CAMERAS,
    MIN_CAMERAS_FOR_TRIANGULATION,
    REPROJECTION_EXCELLENT,
    REPROJECTION_FAIR,
    REPROJECTION_GOOD,
    REPROJECTION_POOR,
)
from shared.dto.calibration_dto import (
    CalibrationMethod,
    CalibrationResult,
    CalibrationStatus,
    DistortionCoeffs,
    ExtrinsicParams,
    IntrinsicParams,
    MultiCameraCalibration,
    RotationMatrix,
    StereoCalibration,
    TranslationVector,
)

from infrastructure.multi_camera.camera_config import CameraConfig


# =============================================================================
# 상수 정의
# =============================================================================

# 캘리브레이션 이미지 최대 보관 수 (메모리 방어)
MAX_CALIBRATION_IMAGES: Final[int] = 200

# 캘리브레이션 결과 캐시 수명 (초)
CALIBRATION_CACHE_TTL_SEC: Final[float] = 3600.0

# 체스보드 검출 플래그
_CHESSBOARD_FLAGS: Final[int] = (
    cv2.CALIB_CB_ADAPTIVE_THRESH
    | cv2.CALIB_CB_NORMALIZE_IMAGE
    | cv2.CALIB_CB_FAST_CHECK
)

# 캘리브레이션 플래그 (기본)
_CALIBRATE_FLAGS: Final[int] = 0

# 코너 서브픽셀 정제 기준
_SUBPIX_CRITERIA: Final[tuple[int, int, float]] = (
    cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
    30,
    0.001,
)

# 코너 서브픽셀 윈도우 크기
_SUBPIX_WINDOW: Final[tuple[int, int]] = (11, 11)
_SUBPIX_ZERO_ZONE: Final[tuple[int, int]] = (-1, -1)


# =============================================================================
# CalibrationQuality: 품질 등급 평가
# =============================================================================

def evaluate_calibration_quality(reprojection_error: float) -> str:
    """리프로젝션 오차로 캘리브레이션 품질 등급 평가.

    Args:
        reprojection_error: 리프로젝션 오차 (픽셀)

    Returns:
        품질 등급 문자열
    """
    if reprojection_error <= REPROJECTION_EXCELLENT:
        return "excellent"
    if reprojection_error <= REPROJECTION_GOOD:
        return "good"
    if reprojection_error <= REPROJECTION_FAIR:
        return "fair"
    if reprojection_error <= REPROJECTION_POOR:
        return "poor"
    return "unacceptable"


# =============================================================================
# CalibrationSnapshot: 캘리브레이션 스냅샷
# =============================================================================

@dataclass(slots=True)
class CalibrationSnapshot:
    """캘리브레이션 결과 스냅샷.

    직렬화/캐싱에 사용되는 불변 스냅샷.

    Attributes:
        camera_id: 카메라 ID
        intrinsic_matrix: 내부 행렬 (3x3)
        distortion_coeffs: 왜곡 계수 배열
        rotation_matrix: 회전 행렬 (3x3, 외부 파라미터)
        translation_vector: 이동 벡터 (3,)
        reprojection_error: 리프로젝션 오차
        quality: 품질 등급
        timestamp: 생성 시각 (monotonic)
    """

    camera_id: str
    intrinsic_matrix: NDArray[np.float64]
    distortion_coeffs: NDArray[np.float64]
    rotation_matrix: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )
    translation_vector: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    reprojection_error: float = 0.0
    quality: str = "unknown"
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def is_expired(self) -> bool:
        """캐시 만료 여부."""
        return (time.monotonic() - self.timestamp) > CALIBRATION_CACHE_TTL_SEC

    @property
    def age_seconds(self) -> float:
        """스냅샷 나이 (초)."""
        return time.monotonic() - self.timestamp

    def to_calibration_result(self, camera_uuid: UUID) -> CalibrationResult:
        """CalibrationResult DTO로 변환.

        Args:
            camera_uuid: 카메라 UUID

        Returns:
            CalibrationResult 인스턴스
        """
        intrinsic = IntrinsicParams.from_matrix(self.intrinsic_matrix)
        distortion = DistortionCoeffs.from_array(self.distortion_coeffs)
        extrinsic = ExtrinsicParams(
            rotation=RotationMatrix(self.rotation_matrix.copy()),
            translation=TranslationVector(self.translation_vector.copy()),
        )

        return CalibrationResult(
            camera_id=camera_uuid,
            intrinsic=intrinsic,
            distortion=distortion,
            extrinsic=extrinsic,
            reprojection_error=self.reprojection_error,
            status=CalibrationStatus.CALIBRATED,
            method=CalibrationMethod.CHESSBOARD,
        )

    def __repr__(self) -> str:
        return (
            f"CalibrationSnapshot(camera='{self.camera_id}', "
            f"error={self.reprojection_error:.4f}px, "
            f"quality={self.quality}, "
            f"age={self.age_seconds:.0f}s)"
        )


# =============================================================================
# SingleCameraCalibrator: 개별 카메라 캘리브레이션
# =============================================================================

class SingleCameraCalibrator:
    """개별 카메라 캘리브레이션.

    체스보드 패턴 기반 내부/왜곡 파라미터 추정.

    사용 예시::

        calibrator = SingleCameraCalibrator("cam_0")
        for frame in calibration_frames:
            calibrator.add_image(frame)
        snapshot = calibrator.calibrate()
    """

    __slots__ = (
        "_camera_id",
        "_image_points",
        "_image_size",
        "_board_size",
        "_square_size_mm",
        "_lock",
        "_snapshot",
    )

    def __init__(
        self,
        camera_id: str,
        board_size: tuple[int, int] = CHESSBOARD_SIZE,
        square_size_mm: float = CHESSBOARD_SQUARE_SIZE_MM,
    ) -> None:
        self._camera_id = camera_id
        self._board_size = board_size
        self._square_size_mm = square_size_mm
        self._image_points: list[NDArray[np.float32]] = []
        self._image_size: tuple[int, int] | None = None
        self._lock = threading.RLock()
        self._snapshot: CalibrationSnapshot | None = None

    @property
    def camera_id(self) -> str:
        """카메라 ID."""
        return self._camera_id

    @property
    def image_count(self) -> int:
        """수집된 캘리브레이션 이미지 수."""
        with self._lock:
            return len(self._image_points)

    @property
    def is_ready(self) -> bool:
        """캘리브레이션 실행 가능 여부."""
        with self._lock:
            return len(self._image_points) >= CALIBRATION_MIN_IMAGES

    @property
    def snapshot(self) -> CalibrationSnapshot | None:
        """최근 캘리브레이션 스냅샷."""
        with self._lock:
            return self._snapshot

    def add_image(self, image: NDArray[np.uint8]) -> bool:
        """캘리브레이션 이미지 추가 (체스보드 검출 시도).

        Args:
            image: 입력 이미지 (BGR 또는 Grayscale)

        Returns:
            체스보드 검출 성공 여부
        """
        with self._lock:
            if len(self._image_points) >= MAX_CALIBRATION_IMAGES:
                return False

            # 그레이스케일 변환
            if image.ndim == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # 이미지 크기 기록
            h, w = gray.shape[:2]
            if self._image_size is None:
                self._image_size = (w, h)

            # 체스보드 코너 검출
            found, corners = cv2.findChessboardCorners(
                gray, self._board_size, _CHESSBOARD_FLAGS,
            )

            if not found or corners is None:
                return False

            # 서브픽셀 정제
            corners_refined = cv2.cornerSubPix(
                gray, corners, _SUBPIX_WINDOW, _SUBPIX_ZERO_ZONE, _SUBPIX_CRITERIA,
            )

            self._image_points.append(corners_refined)
            return True

    def calibrate(self) -> CalibrationSnapshot | None:
        """캘리브레이션 실행.

        Returns:
            성공 시 CalibrationSnapshot, 실패 시 None
        """
        with self._lock:
            if not self.is_ready or self._image_size is None:
                return None

            # 3D 오브젝트 포인트 생성
            obj_points = self._generate_object_points()
            obj_points_list = [obj_points] * len(self._image_points)

            # OpenCV 캘리브레이션
            ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
                obj_points_list,
                self._image_points,
                self._image_size,
                None,
                None,
                flags=_CALIBRATE_FLAGS,
            )

            if not ret or K is None:
                return None

            # 외부 파라미터: 첫 번째 이미지 기준
            R_mat = np.eye(3, dtype=np.float64)
            t_vec = np.zeros(3, dtype=np.float64)
            if rvecs and tvecs:
                R_mat, _ = cv2.Rodrigues(rvecs[0])
                t_vec = tvecs[0].ravel()

            quality = evaluate_calibration_quality(ret)

            self._snapshot = CalibrationSnapshot(
                camera_id=self._camera_id,
                intrinsic_matrix=K.astype(np.float64),
                distortion_coeffs=dist.ravel().astype(np.float64),
                rotation_matrix=R_mat.astype(np.float64),
                translation_vector=t_vec.astype(np.float64),
                reprojection_error=float(ret),
                quality=quality,
            )

            return self._snapshot

    def clear(self) -> int:
        """수집된 이미지 초기화.

        Returns:
            삭제된 이미지 수
        """
        with self._lock:
            count = len(self._image_points)
            self._image_points.clear()
            self._image_size = None
            self._snapshot = None
            return count

    def _generate_object_points(self) -> NDArray[np.float32]:
        """3D 체스보드 오브젝트 포인트 생성."""
        cols, rows = self._board_size
        objp = np.zeros((cols * rows, 3), dtype=np.float32)
        objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        objp *= self._square_size_mm
        return objp

    def __repr__(self) -> str:
        status = "ready" if self.is_ready else f"{self.image_count}/{CALIBRATION_MIN_IMAGES}"
        return (
            f"SingleCameraCalibrator(camera='{self._camera_id}', "
            f"images={status})"
        )


# =============================================================================
# StereoCalibratorPair: 스테레오 캘리브레이션
# =============================================================================

class StereoCalibratorPair:
    """두 카메라 간 스테레오 캘리브레이션.

    두 카메라의 상대 위치/방향 추정.

    사용 예시::

        stereo = StereoCalibratorPair("cam_0", "cam_1", K1, d1, K2, d2)
        for frame1, frame2 in paired_frames:
            stereo.add_image_pair(frame1, frame2)
        result = stereo.calibrate()
    """

    __slots__ = (
        "_camera1_id",
        "_camera2_id",
        "_K1",
        "_d1",
        "_K2",
        "_d2",
        "_image_points1",
        "_image_points2",
        "_image_size",
        "_board_size",
        "_square_size_mm",
        "_lock",
        "_result",
    )

    def __init__(
        self,
        camera1_id: str,
        camera2_id: str,
        K1: NDArray[np.float64],
        d1: NDArray[np.float64],
        K2: NDArray[np.float64],
        d2: NDArray[np.float64],
        board_size: tuple[int, int] = CHESSBOARD_SIZE,
        square_size_mm: float = CHESSBOARD_SQUARE_SIZE_MM,
    ) -> None:
        self._camera1_id = camera1_id
        self._camera2_id = camera2_id
        self._K1 = K1.astype(np.float64)
        self._d1 = d1.ravel().astype(np.float64)
        self._K2 = K2.astype(np.float64)
        self._d2 = d2.ravel().astype(np.float64)
        self._image_points1: list[NDArray[np.float32]] = []
        self._image_points2: list[NDArray[np.float32]] = []
        self._image_size: tuple[int, int] | None = None
        self._board_size = board_size
        self._square_size_mm = square_size_mm
        self._lock = threading.RLock()
        self._result: StereoCalibration | None = None

    @property
    def pair_count(self) -> int:
        """수집된 이미지 쌍 수."""
        with self._lock:
            return len(self._image_points1)

    @property
    def is_ready(self) -> bool:
        """캘리브레이션 실행 가능 여부."""
        with self._lock:
            return len(self._image_points1) >= CALIBRATION_MIN_IMAGES

    @property
    def result(self) -> StereoCalibration | None:
        """최근 캘리브레이션 결과."""
        with self._lock:
            return self._result

    def add_image_pair(
        self,
        image1: NDArray[np.uint8],
        image2: NDArray[np.uint8],
    ) -> bool:
        """동기화된 이미지 쌍 추가.

        Args:
            image1: 카메라 1 이미지
            image2: 카메라 2 이미지

        Returns:
            양쪽 모두 체스보드 검출 성공 여부
        """
        with self._lock:
            if len(self._image_points1) >= MAX_CALIBRATION_IMAGES:
                return False

            # 그레이스케일 변환
            gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY) if image1.ndim == 3 else image1
            gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY) if image2.ndim == 3 else image2

            if self._image_size is None:
                h, w = gray1.shape[:2]
                self._image_size = (w, h)

            # 양쪽 체스보드 검출
            found1, corners1 = cv2.findChessboardCorners(
                gray1, self._board_size, _CHESSBOARD_FLAGS,
            )
            found2, corners2 = cv2.findChessboardCorners(
                gray2, self._board_size, _CHESSBOARD_FLAGS,
            )

            if not found1 or not found2 or corners1 is None or corners2 is None:
                return False

            # 서브픽셀 정제
            corners1 = cv2.cornerSubPix(
                gray1, corners1, _SUBPIX_WINDOW, _SUBPIX_ZERO_ZONE, _SUBPIX_CRITERIA,
            )
            corners2 = cv2.cornerSubPix(
                gray2, corners2, _SUBPIX_WINDOW, _SUBPIX_ZERO_ZONE, _SUBPIX_CRITERIA,
            )

            self._image_points1.append(corners1)
            self._image_points2.append(corners2)
            return True

    def calibrate(self) -> StereoCalibration | None:
        """스테레오 캘리브레이션 실행.

        Returns:
            성공 시 StereoCalibration, 실패 시 None
        """
        with self._lock:
            if not self.is_ready or self._image_size is None:
                return None

            obj_points = self._generate_object_points()
            obj_points_list = [obj_points] * len(self._image_points1)

            # 스테레오 캘리브레이션
            ret, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
                obj_points_list,
                self._image_points1,
                self._image_points2,
                self._K1,
                self._d1,
                self._K2,
                self._d2,
                self._image_size,
                flags=cv2.CALIB_FIX_INTRINSIC,
                criteria=_SUBPIX_CRITERIA,
            )

            if not ret:
                return None

            status = CalibrationStatus.CALIBRATED if ret < REPROJECTION_FAIR else CalibrationStatus.FAILED

            self._result = StereoCalibration(
                camera1_id=uuid4(),
                camera2_id=uuid4(),
                rotation=RotationMatrix(R.astype(np.float64)),
                translation=TranslationVector(T.ravel().astype(np.float64)),
                reprojection_error=float(ret),
                status=status,
            )

            return self._result

    def clear(self) -> int:
        """수집된 이미지 쌍 초기화.

        Returns:
            삭제된 이미지 쌍 수
        """
        with self._lock:
            count = len(self._image_points1)
            self._image_points1.clear()
            self._image_points2.clear()
            self._image_size = None
            self._result = None
            return count

    def _generate_object_points(self) -> NDArray[np.float32]:
        """3D 체스보드 오브젝트 포인트 생성."""
        cols, rows = self._board_size
        objp = np.zeros((cols * rows, 3), dtype=np.float32)
        objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        objp *= self._square_size_mm
        return objp

    def __repr__(self) -> str:
        return (
            f"StereoCalibratorPair('{self._camera1_id}'↔'{self._camera2_id}', "
            f"pairs={self.pair_count})"
        )


# =============================================================================
# MultiCameraCalibrator: 멀티카메라 시스템 캘리브레이션
# =============================================================================

class MultiCameraCalibrator:
    """멀티카메라 시스템 캘리브레이션 오케스트레이터.

    4~8대 카메라의 개별 + 스테레오 캘리브레이션을 관리.

    사용 예시::

        calibrator = MultiCameraCalibrator(camera_configs)
        # 개별 캘리브레이션
        for cam_id, frames in camera_frames.items():
            for frame in frames:
                calibrator.add_single_image(cam_id, frame)
        calibrator.calibrate_all_single()
        # 스테레오 캘리브레이션 (인접 카메라 쌍)
        calibrator.calibrate_stereo_pairs(paired_frames)
        result = calibrator.get_result()
    """

    __slots__ = (
        "_single_calibrators",
        "_stereo_pairs",
        "_camera_configs",
        "_snapshots",
        "_lock",
        "_reference_camera_id",
    )

    def __init__(
        self,
        camera_configs: list[CameraConfig],
        reference_camera_id: str | None = None,
    ) -> None:
        if len(camera_configs) > MAX_CAMERAS:
            raise ValueError(f"카메라 수가 최대({MAX_CAMERAS})를 초과: {len(camera_configs)}")

        self._camera_configs: dict[str, CameraConfig] = {
            c.camera_id: c for c in camera_configs
        }
        self._single_calibrators: dict[str, SingleCameraCalibrator] = {
            c.camera_id: SingleCameraCalibrator(c.camera_id)
            for c in camera_configs
        }
        self._stereo_pairs: dict[tuple[str, str], StereoCalibratorPair] = {}
        self._snapshots: dict[str, CalibrationSnapshot] = {}
        self._lock = threading.RLock()
        self._reference_camera_id = reference_camera_id or (
            camera_configs[0].camera_id if camera_configs else None
        )

    @property
    def camera_count(self) -> int:
        """카메라 수."""
        return len(self._camera_configs)

    @property
    def calibrated_count(self) -> int:
        """캘리브레이션 완료된 카메라 수."""
        with self._lock:
            return len(self._snapshots)

    @property
    def all_calibrated(self) -> bool:
        """전체 카메라 캘리브레이션 완료 여부."""
        with self._lock:
            return len(self._snapshots) == len(self._camera_configs)

    def add_single_image(self, camera_id: str, image: NDArray[np.uint8]) -> bool:
        """개별 카메라에 캘리브레이션 이미지 추가.

        Args:
            camera_id: 카메라 ID
            image: 입력 이미지

        Returns:
            체스보드 검출 성공 여부
        """
        calibrator = self._single_calibrators.get(camera_id)
        if calibrator is None:
            return False
        return calibrator.add_image(image)

    def calibrate_single(self, camera_id: str) -> CalibrationSnapshot | None:
        """개별 카메라 캘리브레이션 실행.

        Args:
            camera_id: 카메라 ID

        Returns:
            성공 시 CalibrationSnapshot
        """
        calibrator = self._single_calibrators.get(camera_id)
        if calibrator is None:
            return None

        snapshot = calibrator.calibrate()
        if snapshot is not None:
            with self._lock:
                self._snapshots[camera_id] = snapshot
        return snapshot

    def calibrate_all_single(self) -> dict[str, CalibrationSnapshot | None]:
        """전체 개별 카메라 캘리브레이션 실행.

        Returns:
            카메라 ID → CalibrationSnapshot 매핑
        """
        results: dict[str, CalibrationSnapshot | None] = {}
        for camera_id in self._single_calibrators:
            results[camera_id] = self.calibrate_single(camera_id)
        return results

    def setup_stereo_pair(
        self,
        camera1_id: str,
        camera2_id: str,
    ) -> StereoCalibratorPair | None:
        """스테레오 캘리브레이션 쌍 설정.

        개별 캘리브레이션이 완료된 두 카메라에 대해 스테레오 쌍을 생성.

        Args:
            camera1_id: 카메라 1 ID
            camera2_id: 카메라 2 ID

        Returns:
            성공 시 StereoCalibratorPair
        """
        with self._lock:
            snap1 = self._snapshots.get(camera1_id)
            snap2 = self._snapshots.get(camera2_id)

            if snap1 is None or snap2 is None:
                return None

            pair_key = (camera1_id, camera2_id)
            pair = StereoCalibratorPair(
                camera1_id=camera1_id,
                camera2_id=camera2_id,
                K1=snap1.intrinsic_matrix,
                d1=snap1.distortion_coeffs,
                K2=snap2.intrinsic_matrix,
                d2=snap2.distortion_coeffs,
            )
            self._stereo_pairs[pair_key] = pair
            return pair

    def get_snapshot(self, camera_id: str) -> CalibrationSnapshot | None:
        """카메라별 캘리브레이션 스냅샷 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            CalibrationSnapshot 또는 None
        """
        with self._lock:
            return self._snapshots.get(camera_id)

    def get_all_snapshots(self) -> dict[str, CalibrationSnapshot]:
        """전체 캘리브레이션 스냅샷 조회 (방어적 복사).

        Returns:
            카메라 ID → CalibrationSnapshot 매핑
        """
        with self._lock:
            return dict(self._snapshots)

    def get_result(self) -> MultiCameraCalibration:
        """멀티카메라 캘리브레이션 결과 DTO 생성.

        Returns:
            MultiCameraCalibration DTO
        """
        with self._lock:
            camera_calibrations: dict[UUID, CalibrationResult] = {}

            for camera_id, snapshot in self._snapshots.items():
                cam_uuid = uuid4()
                camera_calibrations[cam_uuid] = snapshot.to_calibration_result(cam_uuid)

            stereo_calibrations: list[StereoCalibration] = []
            for pair in self._stereo_pairs.values():
                if pair.result is not None:
                    stereo_calibrations.append(pair.result)

            # 전역 리프로젝션 오차 (평균)
            errors = [s.reprojection_error for s in self._snapshots.values()]
            global_error = sum(errors) / len(errors) if errors else 0.0

            # 전체 상태
            status = CalibrationStatus.CALIBRATED if self.all_calibrated else CalibrationStatus.IN_PROGRESS

            return MultiCameraCalibration(
                camera_calibrations=camera_calibrations,
                stereo_calibrations=stereo_calibrations,
                global_reprojection_error=global_error,
                status=status,
            )

    def clear_all(self) -> None:
        """전체 캘리브레이션 데이터 초기화."""
        with self._lock:
            for cal in self._single_calibrators.values():
                cal.clear()
            self._stereo_pairs.clear()
            self._snapshots.clear()

    def __repr__(self) -> str:
        return (
            f"MultiCameraCalibrator(cameras={self.camera_count}, "
            f"calibrated={self.calibrated_count}, "
            f"stereo_pairs={len(self._stereo_pairs)})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 클래스
    "SingleCameraCalibrator",
    "StereoCalibratorPair",
    "MultiCameraCalibrator",
    # 데이터 클래스
    "CalibrationSnapshot",
    # 함수
    "evaluate_calibration_quality",
    # 상수
    "MAX_CALIBRATION_IMAGES",
    "CALIBRATION_CACHE_TTL_SEC",
]

__version__ = "1.0.0"
