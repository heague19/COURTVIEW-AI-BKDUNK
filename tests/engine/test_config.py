# -*- coding: utf-8 -*-
"""engine/config.py 단위 테스트."""

from __future__ import annotations

import pytest

from engine.config import (
    CadenceConfig,
    CadenceLevel,
    CameraConfig,
    EngineConfig,
    EngineMode,
    GPUConfig,
    IOConfig,
    PipelineConfig,
    RefereeConfig,
    RTX_4060_PROFILE,
    RTX_4090_PROFILE,
    RTX_5070_PROFILE,
    TRTPrecision,
)
from shared.constants.referee_rule_constants import RuleSet


# =============================================================================
# Enum 테스트
# =============================================================================
class TestEngineMode:
    """EngineMode 열거형."""

    def test_member_count(self) -> None:
        assert len(EngineMode) == 3

    def test_values(self) -> None:
        assert EngineMode.LIVE.value == "live"
        assert EngineMode.BATCH.value == "batch"
        assert EngineMode.REPLAY.value == "replay"

    def test_str(self) -> None:
        assert str(EngineMode.LIVE) == "live"


class TestTRTPrecision:
    """TRTPrecision 열거형."""

    def test_member_count(self) -> None:
        assert len(TRTPrecision) == 3

    def test_values(self) -> None:
        assert TRTPrecision.FP32.value == "fp32"
        assert TRTPrecision.FP16.value == "fp16"
        assert TRTPrecision.INT8.value == "int8"


class TestCadenceLevel:
    """CadenceLevel 열거형."""

    def test_member_count(self) -> None:
        assert len(CadenceLevel) == 5

    def test_order(self) -> None:
        levels = [
            CadenceLevel.FRAME,
            CadenceLevel.EVENT,
            CadenceLevel.POSSESSION,
            CadenceLevel.PERIOD,
            CadenceLevel.POSTGAME,
        ]
        assert all(isinstance(lv, CadenceLevel) for lv in levels)


# =============================================================================
# Config dataclass 테스트
# =============================================================================
class TestGPUConfig:
    """GPUConfig 데이터 클래스."""

    def test_defaults(self) -> None:
        cfg = GPUConfig()
        assert cfg.vram_limit_mb == 0
        assert cfg.trt_precision == TRTPrecision.FP16
        assert cfg.num_cuda_streams == 2
        assert cfg.thermal_warning_celsius == 85.0
        assert cfg.thermal_critical_celsius == 95.0
        assert cfg.detection_batch_size == 8
        assert cfg.pose_stage1_batch_size == 16
        assert cfg.pose_stage2_batch_size == 4

    def test_slots(self) -> None:
        cfg = GPUConfig()
        assert not hasattr(cfg, "__dict__")


class TestCameraConfig:
    """CameraConfig 데이터 클래스."""

    def test_asecam_defaults(self) -> None:
        """ASECAM 듀얼 스트림 기본값 확인."""
        cfg = CameraConfig()
        assert cfg.num_cameras == 8
        assert cfg.analysis_width == 1920
        assert cfg.analysis_height == 1080
        assert cfg.target_fps == 30
        assert cfg.sync_tolerance_ms == 1.0
        assert cfg.input_source == "rtsp"
        assert cfg.recording_enabled is True
        assert cfg.recording_width == 3840
        assert cfg.recording_height == 2160
        assert cfg.recording_codec == "h265"

    def test_slots(self) -> None:
        cfg = CameraConfig()
        assert not hasattr(cfg, "__dict__")


class TestCadenceConfig:
    """CadenceConfig 데이터 클래스."""

    def test_frame_budget_33ms(self) -> None:
        """30fps 기준 프레임 예산 33ms."""
        cfg = CadenceConfig()
        assert cfg.frame_budget_ms == 33.0

    def test_thread_counts(self) -> None:
        cfg = CadenceConfig()
        assert cfg.possession_threads == 4
        assert cfg.period_threads == 2


class TestPipelineConfig:
    """PipelineConfig 데이터 클래스."""

    def test_model_paths(self) -> None:
        cfg = PipelineConfig()
        assert "yolov8" in cfg.model_yolov8_det
        assert "pose" in cfg.model_yolov8_pose
        assert "vitpose" in cfg.model_vitpose
        assert "osnet" in cfg.model_reid

    def test_stage2_triggers(self) -> None:
        cfg = PipelineConfig()
        assert len(cfg.stage2_triggers) == 4
        assert "shooting_detected" in cfg.stage2_triggers

    def test_fusion_thresholds(self) -> None:
        cfg = PipelineConfig()
        assert 0.0 < cfg.fusion_nms_threshold < 1.0
        assert cfg.fusion_triangulation_error_m > 0
        assert 0.0 < cfg.fusion_tracking_iou_threshold < 1.0


class TestRefereeConfig:
    """RefereeConfig 데이터 클래스."""

    def test_defaults(self) -> None:
        cfg = RefereeConfig()
        assert cfg.rule_set == RuleSet.FIBA
        assert cfg.min_confidence == 0.75
        assert cfg.multi_angle_agreement == 0.75
        assert cfg.replay_window_sec == 10.0
        assert cfg.auto_confirm_threshold == 0.95


class TestIOConfig:
    """IOConfig 데이터 클래스."""

    def test_defaults(self) -> None:
        cfg = IOConfig()
        assert cfg.websocket_host == "localhost"
        assert cfg.websocket_port == 8000
        assert cfg.cloud_sync_enabled is False


class TestEngineConfig:
    """EngineConfig 통합 설정."""

    def test_defaults(self) -> None:
        cfg = EngineConfig()
        assert cfg.mode == EngineMode.LIVE
        assert isinstance(cfg.gpu, GPUConfig)
        assert isinstance(cfg.camera, CameraConfig)
        assert isinstance(cfg.cadence, CadenceConfig)
        assert isinstance(cfg.pipeline, PipelineConfig)
        assert isinstance(cfg.referee, RefereeConfig)
        assert isinstance(cfg.io, IOConfig)
        assert cfg.debug is False
        assert cfg.profiling is False

    def test_custom_mode(self) -> None:
        cfg = EngineConfig(mode=EngineMode.BATCH)
        assert cfg.mode == EngineMode.BATCH

    def test_slots(self) -> None:
        cfg = EngineConfig()
        assert not hasattr(cfg, "__dict__")


# =============================================================================
# GPU 프로파일 테스트
# =============================================================================
class TestGPUProfiles:
    """GPU 프로파일 프리셋."""

    def test_rtx_4060(self) -> None:
        p = RTX_4060_PROFILE
        assert p.vram_limit_mb == 8192
        assert p.detection_batch_size == 4
        assert p.pose_stage1_batch_size == 8
        assert p.pose_stage2_batch_size == 2

    def test_rtx_5070(self) -> None:
        p = RTX_5070_PROFILE
        assert p.vram_limit_mb == 16384
        assert p.detection_batch_size == 8
        assert p.pose_stage1_batch_size == 16
        assert p.pose_stage2_batch_size == 4

    def test_rtx_4090(self) -> None:
        p = RTX_4090_PROFILE
        assert p.vram_limit_mb == 24576
        assert p.detection_batch_size == 8
        assert p.pose_stage1_batch_size == 32
        assert p.pose_stage2_batch_size == 8

    def test_all_fp16(self) -> None:
        """모든 프로파일 FP16 기본."""
        for p in (RTX_4060_PROFILE, RTX_5070_PROFILE, RTX_4090_PROFILE):
            assert p.trt_precision == TRTPrecision.FP16

    def test_all_2_streams(self) -> None:
        """모든 프로파일 2 CUDA 스트림."""
        for p in (RTX_4060_PROFILE, RTX_5070_PROFILE, RTX_4090_PROFILE):
            assert p.num_cuda_streams == 2


# =============================================================================
# __all__ / __version__ 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_all_count(self) -> None:
        import engine.config as mod
        assert len(mod.__all__) == 13

    def test_version(self) -> None:
        import engine.config as mod
        assert mod.__version__ == "1.0.0"
