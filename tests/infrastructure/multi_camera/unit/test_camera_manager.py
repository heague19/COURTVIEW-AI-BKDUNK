# -*- coding: utf-8 -*-
"""infrastructure/multi_camera/camera_manager.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import time

import numpy as np
import pytest

from shared.constants.camera_constants import CameraState, MAX_CAMERAS
from shared.dto.calibration_dto import CalibrationStatus
from infrastructure.multi_camera.camera_config import (
    CameraConfig,
    CameraSetupConfig,
    create_4camera_setup,
)
from infrastructure.multi_camera.camera_manager import (
    CameraManager,
    CameraStatus,
    ManagerStats,
)


# =============================================================================
# Fixture: 매 테스트마다 Singleton 초기화
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """모든 테스트 전후 CameraManager Singleton 초기화."""
    CameraManager.reset()
    yield
    CameraManager.reset()


def _make_setup(n: int = 4) -> CameraSetupConfig:
    """n대 카메라 셋업 생성 헬퍼."""
    setup = CameraSetupConfig()
    for i in range(n):
        setup.add_camera(CameraConfig(camera_id=f"cam_{i}"))
    return setup


# =============================================================================
# CameraStatus 검증
# =============================================================================

class TestCameraStatus:
    def test_creation(self):
        s = CameraStatus(camera_id="cam_0")
        assert s.camera_id == "cam_0"
        assert s.state == CameraState.DISCONNECTED
        assert s.frame_count == 0
        assert s.dropped_frames == 0
        assert s.error_message == ""
        assert s.is_calibrated is False

    def test_drop_rate_zero(self):
        s = CameraStatus(camera_id="cam_0")
        assert s.drop_rate == 0.0

    def test_drop_rate_calculated(self):
        s = CameraStatus(camera_id="cam_0", frame_count=90, dropped_frames=10)
        assert abs(s.drop_rate - 0.1) < 0.001

    def test_is_active_disconnected(self):
        s = CameraStatus(camera_id="cam_0", state=CameraState.DISCONNECTED)
        assert s.is_active is False

    def test_is_active_streaming(self):
        s = CameraStatus(camera_id="cam_0", state=CameraState.STREAMING)
        assert s.is_active is True

    def test_seconds_since_last_frame_no_frame(self):
        s = CameraStatus(camera_id="cam_0")
        assert s.seconds_since_last_frame == float("inf")

    def test_seconds_since_last_frame_recent(self):
        s = CameraStatus(camera_id="cam_0", last_frame_time=time.monotonic())
        assert s.seconds_since_last_frame < 1.0

    def test_repr(self):
        s = CameraStatus(camera_id="cam_0", frame_count=100, dropped_frames=5)
        text = repr(s)
        assert "CameraStatus" in text
        assert "cam_0" in text
        assert "frames=100" in text
        assert "drops=5" in text

    def test_slots(self):
        assert hasattr(CameraStatus, "__slots__")


# =============================================================================
# ManagerStats 검증
# =============================================================================

class TestManagerStats:
    def test_defaults(self):
        m = ManagerStats()
        assert m.total_cameras == 0
        assert m.active_cameras == 0
        assert m.calibrated_cameras == 0
        assert m.total_frames == 0
        assert m.total_drops == 0

    def test_overall_drop_rate_zero(self):
        m = ManagerStats()
        assert m.overall_drop_rate == 0.0

    def test_overall_drop_rate_calculated(self):
        m = ManagerStats(total_frames=80, total_drops=20)
        assert abs(m.overall_drop_rate - 0.2) < 0.001

    def test_repr(self):
        m = ManagerStats(total_cameras=4, active_cameras=3)
        text = repr(m)
        assert "ManagerStats" in text
        assert "cameras=4" in text
        assert "active=3" in text

    def test_slots(self):
        assert hasattr(ManagerStats, "__slots__")


# =============================================================================
# CameraManager Singleton 검증
# =============================================================================

class TestCameraManagerSingleton:
    def test_get_instance(self):
        mgr = CameraManager.get_instance()
        assert isinstance(mgr, CameraManager)

    def test_singleton_same_instance(self):
        mgr1 = CameraManager.get_instance()
        mgr2 = CameraManager.get_instance()
        assert mgr1 is mgr2

    def test_reset_creates_new(self):
        mgr1 = CameraManager.get_instance()
        CameraManager.reset()
        mgr2 = CameraManager.get_instance()
        assert mgr1 is not mgr2


# =============================================================================
# CameraManager 초기화 검증
# =============================================================================

class TestCameraManagerInitialize:
    def test_not_initialized(self):
        mgr = CameraManager.get_instance()
        assert mgr.is_initialized is False
        assert mgr.camera_count == 0

    def test_initialize_success(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        errors = mgr.initialize(setup)
        assert errors == []
        assert mgr.is_initialized is True
        assert mgr.camera_count == 4

    def test_initialize_invalid_setup(self):
        mgr = CameraManager.get_instance()
        setup = CameraSetupConfig()  # 빈 셋업 → 유효성 오류
        errors = mgr.initialize(setup)
        assert len(errors) > 0
        assert mgr.is_initialized is False

    def test_camera_ids(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(3)
        mgr.initialize(setup)
        ids = mgr.camera_ids
        assert len(ids) == 3
        assert "cam_0" in ids
        assert "cam_1" in ids
        assert "cam_2" in ids

    def test_reinitialize(self):
        mgr = CameraManager.get_instance()
        setup1 = _make_setup(2)
        mgr.initialize(setup1)
        assert mgr.camera_count == 2

        setup2 = _make_setup(4)
        mgr.initialize(setup2)
        assert mgr.camera_count == 4


# =============================================================================
# CameraManager 상태 관리 검증
# =============================================================================

class TestCameraManagerStateManagement:
    def _init_manager(self, n: int = 4) -> CameraManager:
        mgr = CameraManager.get_instance()
        setup = _make_setup(n)
        mgr.initialize(setup)
        return mgr

    def test_get_camera_status(self):
        mgr = self._init_manager()
        status = mgr.get_camera_status("cam_0")
        assert status is not None
        assert status.camera_id == "cam_0"
        assert status.state == CameraState.DISCONNECTED

    def test_get_camera_status_unknown(self):
        mgr = self._init_manager()
        assert mgr.get_camera_status("nonexistent") is None

    def test_get_all_statuses(self):
        mgr = self._init_manager()
        statuses = mgr.get_all_statuses()
        assert len(statuses) == 4
        assert all(isinstance(v, CameraStatus) for v in statuses.values())

    def test_set_camera_state(self):
        mgr = self._init_manager()
        assert mgr.set_camera_state("cam_0", CameraState.READY) is True
        status = mgr.get_camera_status("cam_0")
        assert status.state == CameraState.READY

    def test_set_camera_state_error_sets_message(self):
        mgr = self._init_manager()
        mgr.set_camera_state("cam_0", CameraState.ERROR)
        status = mgr.get_camera_status("cam_0")
        assert status.state == CameraState.ERROR
        assert len(status.error_message) > 0

    def test_set_camera_state_unknown(self):
        mgr = self._init_manager()
        assert mgr.set_camera_state("nonexistent", CameraState.READY) is False

    def test_set_camera_error(self):
        mgr = self._init_manager()
        assert mgr.set_camera_error("cam_0", "연결 끊김") is True
        status = mgr.get_camera_status("cam_0")
        assert status.state == CameraState.ERROR
        assert "연결 끊김" in status.error_message

    def test_set_camera_error_truncates(self):
        mgr = self._init_manager()
        long_msg = "x" * 500
        mgr.set_camera_error("cam_0", long_msg)
        status = mgr.get_camera_status("cam_0")
        assert len(status.error_message) <= 256

    def test_set_camera_error_unknown(self):
        mgr = self._init_manager()
        assert mgr.set_camera_error("nonexistent", "err") is False

    def test_record_frame(self):
        mgr = self._init_manager()
        assert mgr.record_frame("cam_0") is True
        status = mgr.get_camera_status("cam_0")
        assert status.frame_count == 1
        assert status.last_frame_time > 0.0

    def test_record_frame_multiple(self):
        mgr = self._init_manager()
        for _ in range(10):
            mgr.record_frame("cam_0")
        status = mgr.get_camera_status("cam_0")
        assert status.frame_count == 10

    def test_record_frame_unknown(self):
        mgr = self._init_manager()
        assert mgr.record_frame("nonexistent") is False

    def test_record_drop(self):
        mgr = self._init_manager()
        assert mgr.record_drop("cam_0") is True
        status = mgr.get_camera_status("cam_0")
        assert status.dropped_frames == 1

    def test_record_drop_unknown(self):
        mgr = self._init_manager()
        assert mgr.record_drop("nonexistent") is False


# =============================================================================
# CameraManager 캘리브레이션 검증
# =============================================================================

class TestCameraManagerCalibration:
    def _init_manager(self) -> CameraManager:
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        mgr.initialize(setup)
        return mgr

    def test_add_calibration_image_not_initialized(self):
        mgr = CameraManager.get_instance()
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        assert mgr.add_calibration_image("cam_0", img) is False

    def test_add_calibration_image_no_chessboard(self):
        mgr = self._init_manager()
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # 검은 이미지 → 체스보드 없음 → False
        assert mgr.add_calibration_image("cam_0", img) is False

    def test_calibrate_camera_not_ready(self):
        mgr = self._init_manager()
        assert mgr.calibrate_camera("cam_0") is None

    def test_calibrate_all_empty(self):
        mgr = self._init_manager()
        results = mgr.calibrate_all()
        assert len(results) == 4
        assert all(v is None for v in results.values())

    def test_calibrate_all_not_initialized(self):
        mgr = CameraManager.get_instance()
        results = mgr.calibrate_all()
        assert results == {}

    def test_get_calibration_snapshot_not_initialized(self):
        mgr = CameraManager.get_instance()
        assert mgr.get_calibration_snapshot("cam_0") is None

    def test_get_calibration_snapshot_none(self):
        mgr = self._init_manager()
        assert mgr.get_calibration_snapshot("cam_0") is None


# =============================================================================
# CameraManager 좌표 변환 검증
# =============================================================================

class TestCameraManagerCoordinates:
    def _init_manager(self) -> CameraManager:
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        mgr.initialize(setup)
        return mgr

    def test_get_transformer_not_calibrated(self):
        mgr = self._init_manager()
        assert mgr.get_transformer("cam_0") is None

    def test_triangulate_insufficient(self):
        mgr = self._init_manager()
        # 뷰가 없으면 유효하지 않은 결과
        obs = {}
        result = mgr.triangulate(obs)
        assert result.is_valid is False

    def test_project_to_court(self):
        mgr = self._init_manager()
        point = np.array([7.0, 5.0, 0.0], dtype=np.float64)
        court = mgr.project_to_court(point)
        assert court.shape == (3,)

    def test_is_on_court_center(self):
        mgr = self._init_manager()
        center = np.array([14.0, 7.5, 0.0], dtype=np.float64)
        assert mgr.is_on_court(center) == True

    def test_is_on_court_outside(self):
        mgr = self._init_manager()
        outside = np.array([100.0, 100.0, 0.0], dtype=np.float64)
        assert mgr.is_on_court(outside) == False


# =============================================================================
# CameraManager Shutdown 검증
# =============================================================================

class TestCameraManagerShutdown:
    def test_shutdown(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        mgr.initialize(setup)
        assert mgr.is_initialized is True

        mgr.shutdown()
        assert mgr.is_initialized is False

    def test_shutdown_resets_states(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(2)
        mgr.initialize(setup)
        mgr.set_camera_state("cam_0", CameraState.STREAMING)

        mgr.shutdown()
        status = mgr.get_camera_status("cam_0")
        assert status.state == CameraState.DISCONNECTED


# =============================================================================
# CameraManager 통계 검증
# =============================================================================

class TestCameraManagerStats:
    def test_stats_empty(self):
        mgr = CameraManager.get_instance()
        stats = mgr.get_stats()
        assert stats.total_cameras == 0
        assert stats.active_cameras == 0

    def test_stats_initialized(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        mgr.initialize(setup)
        stats = mgr.get_stats()
        assert stats.total_cameras == 4
        assert stats.active_cameras == 0
        assert stats.calibrated_cameras == 0

    def test_stats_with_frames(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(2)
        mgr.initialize(setup)

        for _ in range(5):
            mgr.record_frame("cam_0")
        mgr.record_drop("cam_1")

        stats = mgr.get_stats()
        assert stats.total_frames == 5
        assert stats.total_drops == 1

    def test_stats_active_cameras(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(3)
        mgr.initialize(setup)

        mgr.set_camera_state("cam_0", CameraState.STREAMING)
        mgr.set_camera_state("cam_1", CameraState.READY)

        stats = mgr.get_stats()
        assert stats.active_cameras >= 1  # STREAMING은 active


# =============================================================================
# CameraManager repr 검증
# =============================================================================

class TestCameraManagerRepr:
    def test_repr_not_initialized(self):
        mgr = CameraManager.get_instance()
        text = repr(mgr)
        assert "CameraManager" in text
        assert "initialized=False" in text

    def test_repr_initialized(self):
        mgr = CameraManager.get_instance()
        setup = _make_setup(4)
        mgr.initialize(setup)
        text = repr(mgr)
        assert "CameraManager" in text
        assert "cameras=4" in text
        assert "initialized=True" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    pass


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.multi_camera.camera_manager as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.multi_camera.camera_manager as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} not found"

    def test_version(self):
        import infrastructure.multi_camera.camera_manager as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.multi_camera.camera_manager as mod
        assert len(mod.__all__) == 3
