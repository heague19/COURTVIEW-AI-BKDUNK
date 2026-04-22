# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/multi_camera
설명: 멀티카메라 서브모듈
      - camera_config: 카메라별 설정 및 셋업 구성
      - camera_calibrator: 내부/외부 파라미터 캘리브레이션
      - coordinate_transformer: 2D↔3D 좌표 변환 및 삼각측량
      - camera_manager: 4~8대 카메라 수명주기 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# camera_config
# =============================================================================
from infrastructure.multi_camera.camera_config import (
    CAMERA_ID_PREFIX,
    CAMERA_NAME_MAX_LENGTH,
    CAMERA_SOURCE_MAX_LENGTH,
    DEFAULT_CAMERA_NAME_FORMAT,
    PLACEMENT_LABEL_MAX_LENGTH,
    SETUP_ID_PREFIX,
    CameraConfig,
    CameraPlacement,
    CameraSetupConfig,
    SyncConfig,
    create_4camera_setup,
    create_8camera_setup,
    create_default_camera_config,
    create_file_input_setup,
)

# =============================================================================
# camera_calibrator
# =============================================================================
from infrastructure.multi_camera.camera_calibrator import (
    CALIBRATION_CACHE_TTL_SEC,
    MAX_CALIBRATION_IMAGES,
    CalibrationSnapshot,
    MultiCameraCalibrator,
    SingleCameraCalibrator,
    StereoCalibratorPair,
    evaluate_calibration_quality,
)

# =============================================================================
# coordinate_transformer
# =============================================================================
from infrastructure.multi_camera.coordinate_transformer import (
    COURT_HEIGHT_MAX_M,
    COURT_HEIGHT_MIN_M,
    COURT_MARGIN_M,
    DEFAULT_EPIPOLAR_THRESHOLD,
    DEFAULT_REPROJECTION_THRESHOLD,
    MAX_TRIANGULATION_BATCH,
    CoordinateTransformer,
    CourtProjector,
    MultiViewTriangulator,
    TriangulatedPoint,
)

# =============================================================================
# camera_manager
# =============================================================================
from infrastructure.multi_camera.camera_manager import (
    CameraManager,
    CameraStatus,
    ManagerStats,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- camera_config ---
    # 데이터 클래스
    "CameraPlacement",
    "CameraConfig",
    "SyncConfig",
    "CameraSetupConfig",
    # 팩토리 함수
    "create_default_camera_config",
    "create_4camera_setup",
    "create_8camera_setup",
    "create_file_input_setup",
    # 상수
    "CAMERA_NAME_MAX_LENGTH",
    "CAMERA_SOURCE_MAX_LENGTH",
    "CAMERA_ID_PREFIX",
    "PLACEMENT_LABEL_MAX_LENGTH",
    "DEFAULT_CAMERA_NAME_FORMAT",
    "SETUP_ID_PREFIX",
    # --- camera_calibrator ---
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
    # --- coordinate_transformer ---
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
    # --- camera_manager ---
    # 핵심 클래스
    "CameraManager",
    # 데이터 클래스
    "CameraStatus",
    "ManagerStats",
]

__version__ = "1.0.0"
