# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/multi_camera
파일: camera_manager.py
설명: 멀티카메라 수명주기 관리
      - CameraManager: 4~8대 카메라 시스템의 상태/캘리브레이션/좌표변환 통합 관리
      - Singleton 패턴 (DCL + RLock)
      - 카메라 등록/해제, 상태 추적, 캘리브레이션 오케스트레이션

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

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.camera_constants import (
    CAMERA_HEALTH_CHECK_INTERVAL_SEC,
    CameraState,
    MAX_CAMERAS,
    MIN_CAMERAS,
)

from infrastructure.multi_camera.camera_config import (
    CameraConfig,
    CameraSetupConfig,
)
from infrastructure.multi_camera.camera_calibrator import (
    CalibrationSnapshot,
    MultiCameraCalibrator,
)
from infrastructure.multi_camera.coordinate_transformer import (
    CoordinateTransformer,
    CourtProjector,
    MultiViewTriangulator,
    TriangulatedPoint,
)


# =============================================================================
# 상수 정의
# =============================================================================



# =============================================================================
# CameraStatus: 개별 카메라 런타임 상태
# =============================================================================

@dataclass(slots=True)
class CameraStatus:
    """개별 카메라 런타임 상태.

    Attributes:
        camera_id: 카메라 ID
        state: 현재 상태
        frame_count: 수신된 총 프레임 수
        dropped_frames: 드롭된 프레임 수
        last_frame_time: 마지막 프레임 수신 시각 (monotonic)
        error_message: 최근 오류 메시지
        is_calibrated: 캘리브레이션 완료 여부
    """

    camera_id: str
    state: CameraState = CameraState.DISCONNECTED
    frame_count: int = 0
    dropped_frames: int = 0
    last_frame_time: float = 0.0
    error_message: str = ""
    is_calibrated: bool = False

    @property
    def drop_rate(self) -> float:
        """프레임 드롭률."""
        total = self.frame_count + self.dropped_frames
        if total == 0:
            return 0.0
        return self.dropped_frames / total

    @property
    def is_active(self) -> bool:
        """활성 상태 여부."""
        return self.state.is_active

    @property
    def seconds_since_last_frame(self) -> float:
        """마지막 프레임 이후 경과 시간 (초)."""
        if self.last_frame_time == 0.0:
            return float("inf")
        return time.monotonic() - self.last_frame_time

    def __repr__(self) -> str:
        return (
            f"CameraStatus('{self.camera_id}', "
            f"state={self.state.value}, "
            f"frames={self.frame_count}, "
            f"drops={self.dropped_frames}, "
            f"calibrated={self.is_calibrated})"
        )


# =============================================================================
# ManagerStats: 매니저 전체 통계
# =============================================================================

@dataclass(slots=True)
class ManagerStats:
    """멀티카메라 매니저 통계.

    Attributes:
        total_cameras: 등록된 카메라 수
        active_cameras: 활성 카메라 수
        calibrated_cameras: 캘리브레이션 완료 카메라 수
        total_frames: 전체 수신 프레임 수
        total_drops: 전체 드롭 프레임 수
    """

    total_cameras: int = 0
    active_cameras: int = 0
    calibrated_cameras: int = 0
    total_frames: int = 0
    total_drops: int = 0

    @property
    def overall_drop_rate(self) -> float:
        """전체 드롭률."""
        total = self.total_frames + self.total_drops
        if total == 0:
            return 0.0
        return self.total_drops / total

    def __repr__(self) -> str:
        return (
            f"ManagerStats(cameras={self.total_cameras}, "
            f"active={self.active_cameras}, "
            f"calibrated={self.calibrated_cameras}, "
            f"frames={self.total_frames}, "
            f"drops={self.total_drops})"
        )


# =============================================================================
# CameraManager: Singleton 멀티카메라 매니저
# =============================================================================

class CameraManager:
    """멀티카메라 수명주기 매니저.

    4~8대 카메라의 등록, 상태 추적, 캘리브레이션, 좌표 변환을 통합 관리.
    Singleton 패턴 (DCL + RLock).

    사용 예시::

        manager = CameraManager.get_instance()
        manager.initialize(setup_config)
        manager.set_camera_state("cam_0", CameraState.READY)
        manager.record_frame("cam_0")
        point = manager.triangulate({"cam_0": px1, "cam_1": px2})
    """

    _instance: CameraManager | None = None
    _instance_lock: threading.Lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> CameraManager:
        """Singleton 인스턴스 반환 (DCL)."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """인스턴스 초기화 (테스트용)."""
        with cls._instance_lock:
            cls._instance = None

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._setup: CameraSetupConfig | None = None
        self._statuses: dict[str, CameraStatus] = {}
        self._calibrator: MultiCameraCalibrator | None = None
        self._transformers: dict[str, CoordinateTransformer] = {}
        self._triangulator: MultiViewTriangulator = MultiViewTriangulator()
        self._court_projector: CourtProjector = CourtProjector()
        self._initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        with self._lock:
            return self._initialized

    @property
    def camera_count(self) -> int:
        """등록된 카메라 수."""
        with self._lock:
            return len(self._statuses)

    @property
    def camera_ids(self) -> list[str]:
        """등록된 카메라 ID 목록."""
        with self._lock:
            return list(self._statuses.keys())

    # =========================================================================
    # 초기화
    # =========================================================================

    def initialize(self, setup: CameraSetupConfig) -> list[str]:
        """셋업 구성으로 매니저 초기화.

        Args:
            setup: 멀티카메라 셋업 설정

        Returns:
            유효성 검사 오류 목록 (빈 리스트 = 성공)
        """
        errors = setup.validate()
        if errors:
            return errors

        with self._lock:
            self._setup = setup
            self._statuses.clear()
            self._transformers.clear()

            # 각 카메라 상태 초기화
            for cam in setup.cameras:
                self._statuses[cam.camera_id] = CameraStatus(
                    camera_id=cam.camera_id,
                    state=CameraState.DISCONNECTED,
                )

            # 캘리브레이터 초기화
            reference_id = None
            if setup.reference_camera is not None:
                reference_id = setup.reference_camera.camera_id

            self._calibrator = MultiCameraCalibrator(
                setup.cameras,
                reference_camera_id=reference_id,
            )

            # 삼각측량기 초기화
            self._triangulator = MultiViewTriangulator()

            self._initialized = True

        return []

    def shutdown(self) -> None:
        """매니저 종료."""
        with self._lock:
            # 모든 카메라 상태 → DISCONNECTED
            for status in self._statuses.values():
                status.state = CameraState.DISCONNECTED

            self._transformers.clear()
            self._triangulator = MultiViewTriangulator()
            self._initialized = False

    # =========================================================================
    # 상태 관리
    # =========================================================================

    def get_camera_status(self, camera_id: str) -> CameraStatus | None:
        """카메라 상태 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            CameraStatus 또는 None
        """
        with self._lock:
            return self._statuses.get(camera_id)

    def get_all_statuses(self) -> dict[str, CameraStatus]:
        """전체 카메라 상태 조회 (방어적 복사).

        Returns:
            카메라 ID → CameraStatus 매핑
        """
        with self._lock:
            return dict(self._statuses)

    def set_camera_state(self, camera_id: str, state: CameraState) -> bool:
        """카메라 상태 변경.

        Args:
            camera_id: 카메라 ID
            state: 새 상태

        Returns:
            변경 성공 여부
        """
        with self._lock:
            status = self._statuses.get(camera_id)
            if status is None:
                return False
            status.state = state
            if state == CameraState.ERROR:
                status.error_message = "상태가 ERROR로 전환됨"
            return True

    def set_camera_error(self, camera_id: str, error_message: str) -> bool:
        """카메라 오류 상태 설정.

        Args:
            camera_id: 카메라 ID
            error_message: 오류 메시지

        Returns:
            설정 성공 여부
        """
        with self._lock:
            status = self._statuses.get(camera_id)
            if status is None:
                return False
            status.state = CameraState.ERROR
            status.error_message = error_message[:256]
            return True

    def record_frame(self, camera_id: str) -> bool:
        """프레임 수신 기록.

        Args:
            camera_id: 카메라 ID

        Returns:
            기록 성공 여부
        """
        with self._lock:
            status = self._statuses.get(camera_id)
            if status is None:
                return False
            status.frame_count += 1
            status.last_frame_time = time.monotonic()
            return True

    def record_drop(self, camera_id: str) -> bool:
        """프레임 드롭 기록.

        Args:
            camera_id: 카메라 ID

        Returns:
            기록 성공 여부
        """
        with self._lock:
            status = self._statuses.get(camera_id)
            if status is None:
                return False
            status.dropped_frames += 1
            return True

    # =========================================================================
    # 캘리브레이션
    # =========================================================================

    def add_calibration_image(
        self,
        camera_id: str,
        image: NDArray[np.uint8],
    ) -> bool:
        """개별 카메라에 캘리브레이션 이미지 추가.

        Args:
            camera_id: 카메라 ID
            image: 캘리브레이션 이미지

        Returns:
            체스보드 검출 성공 여부
        """
        with self._lock:
            if self._calibrator is None:
                return False
            return self._calibrator.add_single_image(camera_id, image)

    def calibrate_camera(self, camera_id: str) -> CalibrationSnapshot | None:
        """개별 카메라 캘리브레이션 실행.

        Args:
            camera_id: 카메라 ID

        Returns:
            성공 시 CalibrationSnapshot
        """
        with self._lock:
            if self._calibrator is None:
                return None

            snapshot = self._calibrator.calibrate_single(camera_id)
            if snapshot is not None:
                # 상태 업데이트
                status = self._statuses.get(camera_id)
                if status is not None:
                    status.is_calibrated = True

                # 좌표 변환기 생성 및 삼각측량기에 등록
                transformer = CoordinateTransformer(snapshot)
                self._transformers[camera_id] = transformer
                self._triangulator.add_camera(transformer)

            return snapshot

    def calibrate_all(self) -> dict[str, CalibrationSnapshot | None]:
        """전체 카메라 캘리브레이션 실행.

        Returns:
            카메라 ID → CalibrationSnapshot 매핑
        """
        with self._lock:
            if self._calibrator is None:
                return {}

            results = self._calibrator.calibrate_all_single()

            for camera_id, snapshot in results.items():
                if snapshot is not None:
                    status = self._statuses.get(camera_id)
                    if status is not None:
                        status.is_calibrated = True

                    transformer = CoordinateTransformer(snapshot)
                    self._transformers[camera_id] = transformer
                    self._triangulator.add_camera(transformer)

            return results

    def get_calibration_snapshot(
        self,
        camera_id: str,
    ) -> CalibrationSnapshot | None:
        """카메라 캘리브레이션 스냅샷 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            CalibrationSnapshot 또는 None
        """
        with self._lock:
            if self._calibrator is None:
                return None
            return self._calibrator.get_snapshot(camera_id)

    # =========================================================================
    # 좌표 변환
    # =========================================================================

    def get_transformer(self, camera_id: str) -> CoordinateTransformer | None:
        """카메라별 좌표 변환기 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            CoordinateTransformer 또는 None
        """
        with self._lock:
            return self._transformers.get(camera_id)

    def triangulate(
        self,
        observations: dict[str, NDArray[np.float64]],
    ) -> TriangulatedPoint:
        """다중 뷰 삼각측량.

        Args:
            observations: 카메라 ID → 2D 관측점 매핑

        Returns:
            TriangulatedPoint
        """
        return self._triangulator.triangulate(observations)

    def project_to_court(
        self,
        point_3d: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """3D 점을 코트 좌표로 변환.

        Args:
            point_3d: 3D 좌표 (3,)

        Returns:
            코트 좌표 (3,)
        """
        return self._court_projector.to_court_coordinates(point_3d)

    def is_on_court(self, point_3d: NDArray[np.float64]) -> bool:
        """점이 코트 위에 있는지 확인.

        Args:
            point_3d: 3D 좌표 (3,)

        Returns:
            코트 내 여부
        """
        return self._court_projector.is_on_court(point_3d)

    # =========================================================================
    # 통계
    # =========================================================================

    def get_stats(self) -> ManagerStats:
        """매니저 통계 조회.

        Returns:
            ManagerStats
        """
        with self._lock:
            total = len(self._statuses)
            active = sum(1 for s in self._statuses.values() if s.is_active)
            calibrated = sum(1 for s in self._statuses.values() if s.is_calibrated)
            frames = sum(s.frame_count for s in self._statuses.values())
            drops = sum(s.dropped_frames for s in self._statuses.values())

            return ManagerStats(
                total_cameras=total,
                active_cameras=active,
                calibrated_cameras=calibrated,
                total_frames=frames,
                total_drops=drops,
            )

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CameraManager(cameras={len(self._statuses)}, "
                f"initialized={self._initialized})"
            )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "CameraManager",
    # 데이터 클래스
    "CameraStatus",
    "ManagerStats",
    # 상수
]

__version__ = "1.0.0"
