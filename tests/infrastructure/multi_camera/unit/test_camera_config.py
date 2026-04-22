# -*- coding: utf-8 -*-
"""infrastructure/multi_camera/camera_config.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest

from shared.constants.camera_constants import (
    CAMERA_FOV_MAX_DEG,
    CAMERA_FOV_MIN_DEG,
    CAMERA_HEIGHT_MAX_M,
    CAMERA_HEIGHT_MIN_M,
    CameraQualityPreset,
    CameraType,
    DEFAULT_FRAME_RATE,
    DEFAULT_RESOLUTION,
    MAX_CAMERAS,
    MAX_FRAME_BUFFER_SIZE,
    MAX_FRAME_RATE,
    MAX_RESOLUTION,
    MIN_CAMERAS,
    MIN_FRAME_RATE,
    MIN_RESOLUTION,
    OPTIMAL_CAMERA_COUNT,
)
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
# CameraPlacement 검증
# =============================================================================

class TestCameraPlacement:
    def test_defaults(self):
        p = CameraPlacement()
        assert p.height_m > 0
        assert p.distance_m > 0
        assert p.fov_deg > 0

    def test_height_clamped_min(self):
        p = CameraPlacement(height_m=0.1)
        assert p.height_m == CAMERA_HEIGHT_MIN_M

    def test_height_clamped_max(self):
        p = CameraPlacement(height_m=100.0)
        assert p.height_m == CAMERA_HEIGHT_MAX_M

    def test_fov_clamped(self):
        p = CameraPlacement(fov_deg=10.0)
        assert p.fov_deg == CAMERA_FOV_MIN_DEG
        p2 = CameraPlacement(fov_deg=300.0)
        assert p2.fov_deg == CAMERA_FOV_MAX_DEG

    def test_angle_wrap(self):
        p = CameraPlacement(angle_deg=450.0)
        assert p.angle_deg == 90.0

    def test_label_clamped(self):
        long_label = "x" * 200
        p = CameraPlacement(label=long_label)
        assert len(p.label) == PLACEMENT_LABEL_MAX_LENGTH

    def test_is_optimal(self):
        p = CameraPlacement()  # 기본값이 optimal
        assert p.is_optimal is True

    def test_is_not_optimal(self):
        p = CameraPlacement(height_m=CAMERA_HEIGHT_MIN_M, fov_deg=CAMERA_FOV_MIN_DEG)
        assert p.is_optimal is False

    def test_repr(self):
        p = CameraPlacement(label="test")
        text = repr(p)
        assert "CameraPlacement" in text
        assert "test" in text

    def test_slots(self):
        assert hasattr(CameraPlacement, "__slots__")


# =============================================================================
# CameraConfig 검증
# =============================================================================

class TestCameraConfig:
    def test_auto_id(self):
        c = CameraConfig()
        assert c.camera_id.startswith(CAMERA_ID_PREFIX)

    def test_custom_id(self):
        c = CameraConfig(camera_id="my_cam")
        assert c.camera_id == "my_cam"

    def test_name_clamped(self):
        long_name = "x" * 100
        c = CameraConfig(name=long_name)
        assert len(c.name) == CAMERA_NAME_MAX_LENGTH

    def test_source_clamped(self):
        long_source = "x" * 600
        c = CameraConfig(source=long_source)
        assert len(c.source) == CAMERA_SOURCE_MAX_LENGTH

    def test_quality_preset_overrides(self):
        c = CameraConfig(
            quality_preset=CameraQualityPreset.ULTRA,
            resolution=(640, 480),
            frame_rate=15,
        )
        assert c.resolution == CameraQualityPreset.ULTRA.resolution
        assert c.frame_rate == CameraQualityPreset.ULTRA.fps

    def test_resolution_clamped_min(self):
        c = CameraConfig(resolution=(100, 100))
        assert c.resolution[0] >= MIN_RESOLUTION[0]
        assert c.resolution[1] >= MIN_RESOLUTION[1]

    def test_resolution_clamped_max(self):
        c = CameraConfig(resolution=(10000, 10000))
        assert c.resolution[0] <= MAX_RESOLUTION[0]
        assert c.resolution[1] <= MAX_RESOLUTION[1]

    def test_fps_clamped(self):
        c1 = CameraConfig(frame_rate=1)
        assert c1.frame_rate == MIN_FRAME_RATE
        c2 = CameraConfig(frame_rate=999)
        assert c2.frame_rate == MAX_FRAME_RATE

    def test_buffer_clamped(self):
        c = CameraConfig(buffer_size=0)
        assert c.buffer_size >= 1
        c2 = CameraConfig(buffer_size=9999)
        assert c2.buffer_size <= MAX_FRAME_BUFFER_SIZE

    def test_pixel_count(self):
        c = CameraConfig(resolution=(1920, 1080))
        assert c.pixel_count == 1920 * 1080

    def test_is_network_camera(self):
        c = CameraConfig(camera_type=CameraType.RTSP)
        assert c.is_network_camera is True
        c2 = CameraConfig(camera_type=CameraType.USB)
        assert c2.is_network_camera is False

    def test_is_file_input(self):
        c = CameraConfig(camera_type=CameraType.FILE)
        assert c.is_file_input is True

    def test_estimated_frame_bytes(self):
        c = CameraConfig(resolution=(1920, 1080))
        assert c.estimated_frame_bytes == 1920 * 1080 * 3

    def test_estimated_buffer_memory(self):
        c = CameraConfig(resolution=(1920, 1080), buffer_size=30)
        assert c.estimated_buffer_memory_bytes == 1920 * 1080 * 3 * 30

    def test_validate_valid(self):
        c = CameraConfig(camera_type=CameraType.USB)
        errors = c.validate()
        assert len(errors) == 0

    def test_validate_network_no_source(self):
        c = CameraConfig(camera_type=CameraType.RTSP, source="")
        errors = c.validate()
        assert any("소스 URL" in e for e in errors)

    def test_validate_file_no_source(self):
        c = CameraConfig(camera_type=CameraType.FILE, source="")
        errors = c.validate()
        assert any("소스 경로" in e for e in errors)

    def test_repr(self):
        c = CameraConfig(name="test")
        text = repr(c)
        assert "CameraConfig" in text
        assert "test" in text

    def test_slots(self):
        assert hasattr(CameraConfig, "__slots__")

    def test_defaults(self):
        c = CameraConfig()
        assert c.resolution == DEFAULT_RESOLUTION
        assert c.frame_rate == DEFAULT_FRAME_RATE
        assert c.enabled is True
        assert c.priority == 0


# =============================================================================
# SyncConfig 검증
# =============================================================================

class TestSyncConfig:
    def test_defaults(self):
        s = SyncConfig()
        assert s.tolerance_ms > 0
        assert s.use_hardware_sync is False

    def test_hardware_sync(self):
        s = SyncConfig(use_hardware_sync=True)
        assert s.jitter_limit_ms < SyncConfig().jitter_limit_ms

    def test_tolerance_clamped(self):
        s = SyncConfig(tolerance_ms=0.001)
        assert s.tolerance_ms >= 1.0  # SOFTWARE_SYNC_JITTER_MS 이상

    def test_repr(self):
        s = SyncConfig()
        text = repr(s)
        assert "SyncConfig" in text
        assert "SW" in text

    def test_repr_hw(self):
        s = SyncConfig(use_hardware_sync=True)
        assert "HW" in repr(s)

    def test_slots(self):
        assert hasattr(SyncConfig, "__slots__")


# =============================================================================
# CameraSetupConfig 검증
# =============================================================================

class TestCameraSetupConfig:
    def test_auto_id(self):
        s = CameraSetupConfig()
        assert s.setup_id.startswith(SETUP_ID_PREFIX)

    def test_empty_setup(self):
        s = CameraSetupConfig()
        assert s.camera_count == 0
        assert s.enabled_count == 0

    def test_add_camera(self):
        s = CameraSetupConfig()
        c = CameraConfig()
        assert s.add_camera(c) is True
        assert s.camera_count == 1

    def test_add_duplicate_id(self):
        s = CameraSetupConfig()
        c = CameraConfig(camera_id="cam_1")
        s.add_camera(c)
        c2 = CameraConfig(camera_id="cam_1")
        assert s.add_camera(c2) is False

    def test_add_over_max(self):
        s = CameraSetupConfig()
        for i in range(MAX_CAMERAS):
            s.add_camera(CameraConfig(camera_id=f"c_{i}"))
        assert s.add_camera(CameraConfig(camera_id="overflow")) is False

    def test_remove_camera(self):
        s = CameraSetupConfig()
        c = CameraConfig(camera_id="cam_1")
        s.add_camera(c)
        assert s.remove_camera("cam_1") is True
        assert s.camera_count == 0

    def test_remove_nonexistent(self):
        s = CameraSetupConfig()
        assert s.remove_camera("nope") is False

    def test_get_camera_by_id(self):
        s = CameraSetupConfig()
        c = CameraConfig(camera_id="cam_1", name="Test")
        s.add_camera(c)
        found = s.get_camera_by_id("cam_1")
        assert found is not None
        assert found.name == "Test"

    def test_get_camera_by_id_missing(self):
        s = CameraSetupConfig()
        assert s.get_camera_by_id("nope") is None

    def test_get_camera_ids(self):
        s = CameraSetupConfig()
        for i in range(3):
            s.add_camera(CameraConfig(camera_id=f"c_{i}"))
        ids = s.get_camera_ids()
        assert len(ids) == 3

    def test_enabled_cameras(self):
        s = CameraSetupConfig()
        c1 = CameraConfig(camera_id="c1", enabled=True)
        c2 = CameraConfig(camera_id="c2", enabled=False)
        s.add_camera(c1)
        s.add_camera(c2)
        assert s.enabled_count == 1

    def test_reference_camera(self):
        s = CameraSetupConfig()
        c = CameraConfig(camera_id="cam_0")
        s.add_camera(c)
        assert s.reference_camera is not None
        assert s.reference_camera.camera_id == "cam_0"

    def test_reference_camera_out_of_range(self):
        s = CameraSetupConfig(reference_camera_index=99)
        assert s.reference_camera is None

    def test_validate_empty(self):
        s = CameraSetupConfig()
        errors = s.validate()
        assert len(errors) > 0

    def test_validate_valid(self):
        s = create_4camera_setup()
        errors = s.validate()
        assert len(errors) == 0

    def test_validate_id_duplicate(self):
        s = CameraSetupConfig()
        c1 = CameraConfig(camera_id="dup")
        s.cameras.append(c1)
        c2 = CameraConfig(camera_id="dup")
        s.cameras.append(c2)
        errors = s.validate()
        assert any("중복" in e for e in errors)

    def test_validate_master_missing(self):
        s = CameraSetupConfig()
        s.add_camera(CameraConfig(camera_id="c1"))
        s.sync.master_camera_id = "nonexistent"
        errors = s.validate()
        assert any("마스터 카메라" in e for e in errors)

    def test_total_estimated_memory(self):
        s = create_4camera_setup()
        assert s.total_estimated_memory_bytes > 0

    def test_repr(self):
        s = CameraSetupConfig()
        text = repr(s)
        assert "CameraSetupConfig" in text

    def test_remove_adjusts_reference(self):
        s = CameraSetupConfig(reference_camera_index=2)
        for i in range(3):
            s.add_camera(CameraConfig(camera_id=f"c_{i}"))
        s.remove_camera("c_2")
        assert s.reference_camera_index <= len(s.cameras) - 1


# =============================================================================
# 팩토리 함수 검증
# =============================================================================

class TestFactoryFunctions:
    def test_create_default_camera(self):
        c = create_default_camera_config(0)
        assert c.name == DEFAULT_CAMERA_NAME_FORMAT.format(index=0)
        assert c.priority == 0

    def test_create_default_usb_auto_source(self):
        c = create_default_camera_config(2, camera_type=CameraType.USB)
        assert c.source == "2"

    def test_create_4camera_setup(self):
        s = create_4camera_setup()
        assert s.camera_count == OPTIMAL_CAMERA_COUNT
        angles = [c.placement.angle_deg for c in s.cameras]
        assert 0.0 in angles
        assert 90.0 in angles
        assert 180.0 in angles
        assert 270.0 in angles

    def test_create_4camera_setup_with_sources(self):
        s = create_4camera_setup(sources=["rtsp://1", "rtsp://2", "rtsp://3", "rtsp://4"])
        assert s.cameras[0].source == "rtsp://1"

    def test_create_8camera_setup(self):
        s = create_8camera_setup()
        assert s.camera_count == MAX_CAMERAS
        # 45도 간격
        angles = [c.placement.angle_deg for c in s.cameras]
        assert angles[1] == 45.0

    def test_create_file_input_setup(self):
        s = create_file_input_setup(["video1.mp4", "video2.mp4"])
        assert s.camera_count == 2
        assert s.cameras[0].camera_type == CameraType.FILE
        assert s.cameras[0].source == "video1.mp4"
        assert s.sync.use_hardware_sync is False

    def test_create_file_input_max_cameras(self):
        paths = [f"v{i}.mp4" for i in range(20)]
        s = create_file_input_setup(paths)
        assert s.camera_count == MAX_CAMERAS


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_camera_name_max(self):
        assert CAMERA_NAME_MAX_LENGTH == 64

    def test_camera_source_max(self):
        assert CAMERA_SOURCE_MAX_LENGTH == 512

    def test_camera_id_prefix(self):
        assert CAMERA_ID_PREFIX == "cam_"

    def test_setup_id_prefix(self):
        assert SETUP_ID_PREFIX == "setup_"


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.multi_camera.camera_config as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.multi_camera.camera_config as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} not found"

    def test_version(self):
        import infrastructure.multi_camera.camera_config as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.multi_camera.camera_config as mod
        assert len(mod.__all__) == 14
