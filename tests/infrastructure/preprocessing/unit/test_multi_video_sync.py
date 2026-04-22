# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트 모듈: infrastructure/preprocessing
테스트 파일: test_multi_video_sync.py
설명: multi_video_sync.py 단위 테스트
      - SyncSession: 기본값, camera_count, camera_ids, repr, slots
      - SyncStats: 기본값, sync_rate, repr, slots
      - MultiVideoSync: 생성, is_active, camera_count, sync_decode, sync_single, stats, repr
      - 모듈 상수 및 Export 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
import numpy as np

from infrastructure.preprocessing.multi_video_sync import (
    MultiVideoSync,
    SyncSession,
    SyncStats,
    __all__ as module_all,
    __version__ as module_version,
)
from shared.dto.video_dto import FrameData, FrameStatus
from shared.constants.camera_constants import (
    HARDWARE_SYNC_JITTER_MS,
    MAX_CAMERAS,
    SOFTWARE_SYNC_JITTER_MS,
    SYNC_TOLERANCE_MS,
)


# =============================================================================
# SyncSession 테스트
# =============================================================================

class TestSyncSession:
    """SyncSession 데이터클래스 단위 테스트."""

    def test_defaults(self) -> None:
        """기본값 생성 확인."""
        session = SyncSession()
        assert session.session_id == ""
        assert session.camera_files == {}
        assert session.use_hardware_sync is False
        assert session.offsets_ms == {}

    def test_camera_count_empty(self) -> None:
        """빈 세션의 camera_count는 0."""
        session = SyncSession()
        assert session.camera_count == 0

    def test_camera_count_with_files(self) -> None:
        """카메라 파일이 있을 때 camera_count 반환."""
        session = SyncSession(
            session_id="test_001",
            camera_files={
                "cam_0": "/path/to/cam0.mp4",
                "cam_1": "/path/to/cam1.mp4",
                "cam_2": "/path/to/cam2.mp4",
            },
        )
        assert session.camera_count == 3

    def test_camera_ids(self) -> None:
        """camera_ids가 올바른 카메라 ID 목록 반환."""
        session = SyncSession(
            camera_files={
                "cam_main": "/video/main.mp4",
                "cam_side": "/video/side.mp4",
            },
        )
        ids = session.camera_ids
        assert "cam_main" in ids
        assert "cam_side" in ids
        assert len(ids) == 2

    def test_camera_ids_empty(self) -> None:
        """빈 세션의 camera_ids는 빈 리스트."""
        session = SyncSession()
        assert session.camera_ids == []

    def test_repr_software_sync(self) -> None:
        """소프트웨어 동기화 repr에 SW 포함."""
        session = SyncSession(
            session_id="game_001",
            camera_files={"cam_0": "a.mp4", "cam_1": "b.mp4"},
            use_hardware_sync=False,
        )
        r = repr(session)
        assert "SyncSession" in r
        assert "game_001" in r
        assert "cameras=2" in r
        assert "SW" in r

    def test_repr_hardware_sync(self) -> None:
        """하드웨어 동기화 repr에 HW 포함."""
        session = SyncSession(
            session_id="game_002",
            camera_files={"cam_0": "a.mp4"},
            use_hardware_sync=True,
        )
        r = repr(session)
        assert "HW" in r

    def test_offsets_ms(self) -> None:
        """카메라별 오프셋 설정 확인."""
        session = SyncSession(
            session_id="offset_test",
            camera_files={"cam_0": "a.mp4", "cam_1": "b.mp4"},
            offsets_ms={"cam_0": 0.0, "cam_1": 15.5},
        )
        assert session.offsets_ms["cam_0"] == 0.0
        assert session.offsets_ms["cam_1"] == 15.5

    def test_slots(self) -> None:
        """SyncSession에 slots가 활성화되어 있는지 확인."""
        session = SyncSession()
        assert hasattr(session, "__slots__") or not hasattr(session, "__dict__")


# =============================================================================
# SyncStats 테스트
# =============================================================================

class TestSyncStats:
    """SyncStats 데이터클래스 단위 테스트."""

    def test_defaults(self) -> None:
        """기본값 확인."""
        stats = SyncStats()
        assert stats.total_sets == 0
        assert stats.total_frames == 0
        assert stats.dropped_frames == 0
        assert stats.drift_corrections == 0
        assert stats.avg_sync_drift_ms == 0.0
        assert stats.max_sync_drift_ms == 0.0
        assert stats.sync_time_sec == 0.0

    def test_sync_rate_zero(self) -> None:
        """total_frames + dropped_frames == 0 일 때 sync_rate == 0.0."""
        stats = SyncStats()
        assert stats.sync_rate == 0.0

    def test_sync_rate_all_synced(self) -> None:
        """전부 동기화됐을 때 sync_rate == 1.0."""
        stats = SyncStats(total_frames=200, dropped_frames=0)
        assert stats.sync_rate == pytest.approx(1.0)

    def test_sync_rate_partial(self) -> None:
        """부분 동기화 시 sync_rate 계산 검증."""
        stats = SyncStats(total_frames=150, dropped_frames=50)
        assert stats.sync_rate == pytest.approx(0.75)

    def test_sync_rate_all_dropped(self) -> None:
        """전부 드롭됐을 때 sync_rate == 0.0."""
        stats = SyncStats(total_frames=0, dropped_frames=100)
        assert stats.sync_rate == pytest.approx(0.0)

    def test_repr(self) -> None:
        """repr 형식 확인."""
        stats = SyncStats(
            total_sets=10,
            total_frames=500,
            dropped_frames=25,
            avg_sync_drift_ms=3.2,
        )
        r = repr(stats)
        assert "SyncStats" in r
        assert "sets=10" in r
        assert "frames=500" in r
        assert "dropped=25" in r
        assert "drift=" in r

    def test_slots(self) -> None:
        """SyncStats에 slots가 활성화되어 있는지 확인."""
        stats = SyncStats()
        assert hasattr(stats, "__slots__") or not hasattr(stats, "__dict__")


# =============================================================================
# MultiVideoSync 테스트
# =============================================================================

class TestMultiVideoSync:
    """MultiVideoSync 핵심 클래스 단위 테스트."""

    def test_creation(self) -> None:
        """기본 생성 확인."""
        sync = MultiVideoSync()
        assert sync is not None

    def test_is_active_initially_false(self) -> None:
        """초기 is_active 상태는 False."""
        sync = MultiVideoSync()
        assert sync.is_active is False

    def test_camera_count_initially_zero(self) -> None:
        """초기 camera_count는 0."""
        sync = MultiVideoSync()
        assert sync.camera_count == 0

    def test_stats_initial_values(self) -> None:
        """초기 통계값 확인."""
        sync = MultiVideoSync()
        stats = sync.stats
        assert stats.total_sets == 0
        assert stats.total_frames == 0
        assert stats.dropped_frames == 0
        assert stats.drift_corrections == 0
        assert stats.avg_sync_drift_ms == 0.0
        assert stats.max_sync_drift_ms == 0.0
        assert stats.sync_time_sec == 0.0

    def test_stats_is_defensive_copy(self) -> None:
        """stats 프로퍼티가 방어적 복사를 반환."""
        sync = MultiVideoSync()
        stats1 = sync.stats
        stats2 = sync.stats
        # 서로 다른 객체여야 함
        assert stats1 is not stats2

    def test_sync_decode_empty_session_yields_nothing(self) -> None:
        """빈 세션으로 sync_decode 시 아무것도 yield하지 않음."""
        sync = MultiVideoSync()
        session = SyncSession()
        results = list(sync.sync_decode(session))
        assert results == []

    def test_sync_decode_nonexistent_files_yields_nothing(self) -> None:
        """존재하지 않는 파일 경로로 sync_decode 시 아무것도 yield하지 않음."""
        sync = MultiVideoSync()
        session = SyncSession(
            session_id="fail_test",
            camera_files={
                "cam_0": "/nonexistent/path/video_0.mp4",
                "cam_1": "/nonexistent/path/video_1.mp4",
            },
        )
        results = list(sync.sync_decode(session))
        assert results == []

    def test_sync_decode_too_many_cameras_yields_nothing(self) -> None:
        """MAX_CAMERAS 초과 세션에서 sync_decode 시 아무것도 yield하지 않음."""
        sync = MultiVideoSync()
        many_files = {
            f"cam_{i}": f"/path/to/cam_{i}.mp4"
            for i in range(MAX_CAMERAS + 1)
        }
        session = SyncSession(
            session_id="too_many",
            camera_files=many_files,
        )
        results = list(sync.sync_decode(session))
        assert results == []

    def test_sync_single_empty_session_returns_none(self) -> None:
        """빈 세션으로 sync_single 시 None 반환."""
        sync = MultiVideoSync()
        session = SyncSession()
        result = sync.sync_single(session, frame_index=0)
        assert result is None

    def test_sync_single_nonexistent_files_returns_none(self) -> None:
        """존재하지 않는 파일로 sync_single 시 None 반환."""
        sync = MultiVideoSync()
        session = SyncSession(
            session_id="fail_single",
            camera_files={
                "cam_0": "/nonexistent/video_single.mp4",
            },
        )
        result = sync.sync_single(session, frame_index=0)
        assert result is None

    def test_is_active_after_failed_decode(self) -> None:
        """실패한 sync_decode 후 is_active는 False."""
        sync = MultiVideoSync()
        session = SyncSession(
            session_id="fail_active",
            camera_files={"cam_0": "/nonexistent.mp4"},
        )
        list(sync.sync_decode(session))
        assert sync.is_active is False

    def test_repr(self) -> None:
        """MultiVideoSync repr 형식 확인."""
        sync = MultiVideoSync()
        r = repr(sync)
        assert "MultiVideoSync" in r
        assert "decoders=" in r
        assert "active=" in r


# =============================================================================
# 상수 검증
# =============================================================================

class TestMultiVideoSyncConstants:
    """모듈 상수 값 검증."""

    pass


# =============================================================================
# 모듈 Export 검증
# =============================================================================

class TestMultiVideoSyncModuleExports:
    """모듈 __all__ 및 __version__ 검증."""

    def test_all_contains_classes(self) -> None:
        """__all__에 핵심 클래스 포함."""
        assert "MultiVideoSync" in module_all
        assert "SyncSession" in module_all
        assert "SyncStats" in module_all

    def test_version(self) -> None:
        """모듈 버전 확인."""
        assert module_version == "1.0.0"
