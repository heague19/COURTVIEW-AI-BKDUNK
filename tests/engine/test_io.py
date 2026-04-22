# -*- coding: utf-8 -*-
"""engine/io/frame_ingestion.py 단위 테스트."""

from __future__ import annotations

import pytest

from engine.config import CameraConfig
from engine.io.frame_ingestion import (
    FrameIngestion,
    IngestionSource,
    IngestionStats,
    RecordingCallback,
    _MAX_RECORDING_CALLBACKS,
)


# =============================================================================
# IngestionSource Enum 테스트
# =============================================================================
class TestIngestionSource:
    """IngestionSource 열거형."""

    def test_member_count(self) -> None:
        assert len(IngestionSource) == 3

    def test_values(self) -> None:
        assert IngestionSource.CAMERA.value == "camera"
        assert IngestionSource.FILE.value == "file"
        assert IngestionSource.RTSP.value == "rtsp"

    def test_str(self) -> None:
        assert str(IngestionSource.RTSP) == "rtsp"


# =============================================================================
# IngestionStats 테스트
# =============================================================================
class TestIngestionStats:
    """IngestionStats 데이터 클래스."""

    def test_defaults(self) -> None:
        s = IngestionStats()
        assert s.total_captured == 0
        assert s.total_normalized == 0
        assert s.total_aligned_sets == 0
        assert s.total_dropped == 0
        assert s.total_recording_frames == 0
        assert s.total_decode_errors == 0
        assert s.total_normalize_errors == 0

    def test_slots(self) -> None:
        s = IngestionStats()
        assert not hasattr(s, "__dict__")


# =============================================================================
# FrameIngestion 테스트
# =============================================================================
class TestFrameIngestion:
    """FrameIngestion 핵심 기능."""

    def test_default_creation(self) -> None:
        fi = FrameIngestion()
        assert fi.is_initialized is False
        assert len(fi.camera_ids) == 8

    def test_custom_camera_count(self) -> None:
        cfg = CameraConfig(num_cameras=4)
        fi = FrameIngestion(cfg)
        assert len(fi.camera_ids) == 4
        assert fi.camera_ids == ["cam_0", "cam_1", "cam_2", "cam_3"]

    def test_initialize_offline(self) -> None:
        """소스 URL 없이 초기화 (오프라인 모드)."""
        fi = FrameIngestion()
        fi.initialize()
        assert fi.is_initialized is True

    def test_double_initialize(self) -> None:
        """중복 초기화 무시."""
        fi = FrameIngestion()
        fi.initialize()
        fi.initialize()
        assert fi.is_initialized is True

    def test_shutdown(self) -> None:
        fi = FrameIngestion()
        fi.initialize()
        fi.shutdown()
        assert fi.is_initialized is False

    def test_capture_before_init_returns_none(self) -> None:
        """초기화 전 캡처 시도 → None."""
        fi = FrameIngestion()
        assert fi.capture_and_align() is None

    def test_decode_all_before_init_returns_empty(self) -> None:
        """초기화 전 배치 디코딩 → 빈 리스트."""
        fi = FrameIngestion()
        assert fi.decode_all() == []

    def test_stats_defensive_copy(self) -> None:
        """통계는 방어적 복사."""
        fi = FrameIngestion()
        s1 = fi.stats
        s2 = fi.stats
        assert s1 is not s2

    def test_frame_counter_initial(self) -> None:
        fi = FrameIngestion()
        assert fi.frame_counter == 0

    def test_reset(self) -> None:
        fi = FrameIngestion()
        fi.initialize()
        fi.reset()
        assert fi.frame_counter == 0
        assert fi.stats.total_captured == 0

    def test_repr(self) -> None:
        fi = FrameIngestion()
        r = repr(fi)
        assert "cameras=8" in r
        assert "initialized=False" in r

    # --- 녹화 콜백 ---

    def test_register_recording_callback(self) -> None:
        fi = FrameIngestion()
        result = fi.register_recording_callback(lambda cid, f, ts: None)
        assert result is True

    def test_recording_callback_limit(self) -> None:
        fi = FrameIngestion()
        for _ in range(_MAX_RECORDING_CALLBACKS):
            assert fi.register_recording_callback(lambda cid, f, ts: None) is True
        assert fi.register_recording_callback(lambda cid, f, ts: None) is False

    def test_capture_recording_disabled(self) -> None:
        """녹화 비활성 시 capture_recording_frames 무동작."""
        cfg = CameraConfig(recording_enabled=False)
        fi = FrameIngestion(cfg)
        fi.initialize()
        fi.capture_recording_frames()
        assert fi.stats.total_recording_frames == 0

    # --- extract_frames 유틸 ---

    def test_extract_frames_static(self) -> None:
        """extract_frames 정적 메서드 — 빈 AlignedFrameSet."""
        from infrastructure.preprocessing.frame_aligner import AlignedFrameSet
        aligned = AlignedFrameSet()
        frames, cam_ids = FrameIngestion.extract_frames(aligned)
        assert frames == []
        assert cam_ids == []


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_all_count(self) -> None:
        import engine.io.frame_ingestion as mod
        assert len(mod.__all__) == 4

    def test_version(self) -> None:
        import engine.io.frame_ingestion as mod
        assert mod.__version__ == "1.0.0"
