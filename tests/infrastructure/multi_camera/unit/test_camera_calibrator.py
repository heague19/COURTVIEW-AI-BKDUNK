# -*- coding: utf-8 -*-
"""infrastructure/multi_camera/camera_calibrator.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import time

import numpy as np
import pytest

from shared.constants.camera_constants import (
    CALIBRATION_MIN_IMAGES,
    REPROJECTION_EXCELLENT,
    REPROJECTION_FAIR,
    REPROJECTION_GOOD,
    REPROJECTION_POOR,
)
from shared.dto.calibration_dto import CalibrationStatus
from infrastructure.multi_camera.camera_config import CameraConfig
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
# evaluate_calibration_quality 검증
# =============================================================================

class TestEvaluateCalibrationQuality:
    def test_excellent(self):
        assert evaluate_calibration_quality(0.1) == "excellent"

    def test_good(self):
        assert evaluate_calibration_quality(0.4) == "good"

    def test_fair(self):
        assert evaluate_calibration_quality(0.8) == "fair"

    def test_poor(self):
        assert evaluate_calibration_quality(1.5) == "poor"

    def test_unacceptable(self):
        assert evaluate_calibration_quality(5.0) == "unacceptable"

    def test_boundary_excellent(self):
        assert evaluate_calibration_quality(REPROJECTION_EXCELLENT) == "excellent"

    def test_boundary_good(self):
        assert evaluate_calibration_quality(REPROJECTION_GOOD) == "good"


# =============================================================================
# CalibrationSnapshot 검증
# =============================================================================

class TestCalibrationSnapshot:
    def test_creation(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64) * 1000.0,
            distortion_coeffs=np.zeros(5, dtype=np.float64),
            reprojection_error=0.3,
            quality="good",
        )
        assert snap.camera_id == "cam_0"
        assert snap.quality == "good"

    def test_slots(self):
        assert hasattr(CalibrationSnapshot, "__slots__")

    def test_default_rotation_translation(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64),
            distortion_coeffs=np.zeros(5, dtype=np.float64),
        )
        assert snap.rotation_matrix.shape == (3, 3)
        assert snap.translation_vector.shape == (3,)

    def test_age_seconds(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64),
            distortion_coeffs=np.zeros(5, dtype=np.float64),
        )
        assert snap.age_seconds >= 0.0
        assert snap.age_seconds < 5.0

    def test_is_expired(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64),
            distortion_coeffs=np.zeros(5, dtype=np.float64),
        )
        assert snap.is_expired is False

    def test_is_expired_old(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64),
            distortion_coeffs=np.zeros(5, dtype=np.float64),
            timestamp=time.monotonic() - CALIBRATION_CACHE_TTL_SEC - 1.0,
        )
        assert snap.is_expired is True

    def test_to_calibration_result(self):
        from uuid import uuid4

        K = np.array([
            [1000.0, 0.0, 960.0],
            [0.0, 1000.0, 540.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=K,
            distortion_coeffs=np.zeros(5, dtype=np.float64),
            reprojection_error=0.3,
            quality="good",
        )

        result = snap.to_calibration_result(uuid4())
        assert result.status == CalibrationStatus.CALIBRATED
        assert result.intrinsic is not None
        assert abs(result.intrinsic.fx - 1000.0) < 0.001

    def test_repr(self):
        snap = CalibrationSnapshot(
            camera_id="cam_0",
            intrinsic_matrix=np.eye(3, dtype=np.float64),
            distortion_coeffs=np.zeros(5, dtype=np.float64),
            quality="good",
        )
        text = repr(snap)
        assert "CalibrationSnapshot" in text
        assert "cam_0" in text
        assert "good" in text


# =============================================================================
# SingleCameraCalibrator 검증
# =============================================================================

class TestSingleCameraCalibrator:
    def test_creation(self):
        cal = SingleCameraCalibrator("cam_0")
        assert cal.camera_id == "cam_0"
        assert cal.image_count == 0
        assert cal.is_ready is False

    def test_add_image_no_chessboard(self):
        """체스보드가 없는 이미지 → 실패."""
        cal = SingleCameraCalibrator("cam_0")
        # 검은색 이미지 (체스보드 없음)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        assert cal.add_image(img) is False
        assert cal.image_count == 0

    def test_add_image_grayscale(self):
        """그레이스케일 이미지도 처리 가능."""
        cal = SingleCameraCalibrator("cam_0")
        gray = np.zeros((480, 640), dtype=np.uint8)
        assert cal.add_image(gray) is False  # 체스보드 없으니 False
        assert cal.image_count == 0

    def test_calibrate_not_ready(self):
        cal = SingleCameraCalibrator("cam_0")
        assert cal.calibrate() is None

    def test_clear(self):
        cal = SingleCameraCalibrator("cam_0")
        # 직접 접근하여 이미지 추가 시뮬레이션
        assert cal.clear() == 0

    def test_snapshot_initially_none(self):
        cal = SingleCameraCalibrator("cam_0")
        assert cal.snapshot is None

    def test_repr(self):
        cal = SingleCameraCalibrator("cam_0")
        text = repr(cal)
        assert "SingleCameraCalibrator" in text
        assert "cam_0" in text

    def test_max_images_limit(self):
        """MAX_CALIBRATION_IMAGES 초과 시 거부."""
        cal = SingleCameraCalibrator("cam_0")
        # 수동으로 image_points를 채워서 테스트
        dummy_corners = np.zeros((54, 1, 2), dtype=np.float32)
        cal._image_points = [dummy_corners] * MAX_CALIBRATION_IMAGES
        # 이미 가득 찬 상태에서 추가 시도
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        assert cal.add_image(img) is False


# =============================================================================
# StereoCalibratorPair 검증
# =============================================================================

class TestStereoCalibratorPair:
    def _make_pair(self):
        K = np.eye(3, dtype=np.float64) * 1000.0
        K[0, 2] = 960.0
        K[1, 2] = 540.0
        K[2, 2] = 1.0
        d = np.zeros(5, dtype=np.float64)
        return StereoCalibratorPair("cam_0", "cam_1", K, d, K, d)

    def test_creation(self):
        pair = self._make_pair()
        assert pair.pair_count == 0
        assert pair.is_ready is False

    def test_add_pair_no_chessboard(self):
        pair = self._make_pair()
        img1 = np.zeros((480, 640, 3), dtype=np.uint8)
        img2 = np.zeros((480, 640, 3), dtype=np.uint8)
        assert pair.add_image_pair(img1, img2) is False

    def test_calibrate_not_ready(self):
        pair = self._make_pair()
        assert pair.calibrate() is None

    def test_clear(self):
        pair = self._make_pair()
        assert pair.clear() == 0

    def test_result_initially_none(self):
        pair = self._make_pair()
        assert pair.result is None

    def test_repr(self):
        pair = self._make_pair()
        text = repr(pair)
        assert "StereoCalibratorPair" in text
        assert "cam_0" in text
        assert "cam_1" in text


# =============================================================================
# MultiCameraCalibrator 검증
# =============================================================================

class TestMultiCameraCalibrator:
    def _make_configs(self, n=4):
        return [CameraConfig(camera_id=f"cam_{i}") for i in range(n)]

    def test_creation(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        assert cal.camera_count == 4
        assert cal.calibrated_count == 0
        assert cal.all_calibrated is False

    def test_max_cameras_limit(self):
        configs = self._make_configs(n=10)
        with pytest.raises(ValueError, match="최대"):
            MultiCameraCalibrator(configs)

    def test_add_single_image_unknown_camera(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        assert cal.add_single_image("nonexistent", img) is False

    def test_calibrate_single_not_ready(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        assert cal.calibrate_single("cam_0") is None

    def test_calibrate_all_single_empty(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        results = cal.calibrate_all_single()
        assert len(results) == 4
        assert all(v is None for v in results.values())

    def test_get_snapshot_none(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        assert cal.get_snapshot("cam_0") is None

    def test_get_all_snapshots_empty(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        assert cal.get_all_snapshots() == {}

    def test_setup_stereo_pair_not_calibrated(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        assert cal.setup_stereo_pair("cam_0", "cam_1") is None

    def test_get_result_in_progress(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        result = cal.get_result()
        assert result.status == CalibrationStatus.IN_PROGRESS

    def test_clear_all(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        cal.clear_all()
        assert cal.calibrated_count == 0

    def test_repr(self):
        configs = self._make_configs()
        cal = MultiCameraCalibrator(configs)
        text = repr(cal)
        assert "MultiCameraCalibrator" in text
        assert "cameras=4" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_calibration_images(self):
        assert MAX_CALIBRATION_IMAGES == 200

    def test_calibration_cache_ttl(self):
        assert CALIBRATION_CACHE_TTL_SEC == 3600.0


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.multi_camera.camera_calibrator as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.multi_camera.camera_calibrator as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} not found"

    def test_version(self):
        import infrastructure.multi_camera.camera_calibrator as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.multi_camera.camera_calibrator as mod
        assert len(mod.__all__) == 7
