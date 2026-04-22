# -*- coding: utf-8 -*-
"""ExportManager 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.media_dto import ExportConfig, ExportFormat
from game_analysis.output.video_editing.export_manager import (
    ExportManager,
    ExportManagerConfig,
    ExportStatus,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mgr() -> ExportManager:
    return ExportManager()


@pytest.fixture
def small_mgr() -> ExportManager:
    return ExportManager(ExportManagerConfig(max_export_jobs=3))


def _queue(mgr: ExportManager, **kw):
    defaults = dict(
        clip_id=uuid4(),
        export_config=ExportConfig(format=ExportFormat.MP4),
    )
    defaults.update(kw)
    return mgr.queue_export(**defaults)


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, mgr: ExportManager) -> None:
        assert mgr.total_jobs == 0

    def test_name(self, mgr: ExportManager) -> None:
        assert mgr.name == "ExportManager"

    def test_repr(self, mgr: ExportManager) -> None:
        assert "ExportManager" in repr(mgr)


# =============================================================================
# Enum
# =============================================================================

class TestExportStatus:
    def test_values(self) -> None:
        assert ExportStatus.QUEUED.value == "queued"
        assert ExportStatus.IN_PROGRESS.value == "in_progress"
        assert ExportStatus.COMPLETED.value == "completed"
        assert ExportStatus.FAILED.value == "failed"


# =============================================================================
# 작업 큐잉
# =============================================================================

class TestQueueExport:
    def test_queue_returns_uuid(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        assert jid is not None
        assert mgr.total_jobs == 1

    def test_queue_with_output_path(self, mgr: ExportManager) -> None:
        jid = _queue(mgr, output_path="/exports/game01.mp4")
        info = mgr.get_job(jid)
        assert info["output_path"] == "/exports/game01.mp4"

    def test_queue_uses_config_path(self, mgr: ExportManager) -> None:
        cfg = ExportConfig(format=ExportFormat.MOV, output_path="/default/path.mov")
        jid = mgr.queue_export(uuid4(), cfg)
        info = mgr.get_job(jid)
        assert info["output_path"] == "/default/path.mov"

    def test_queue_explicit_overrides_config(self, mgr: ExportManager) -> None:
        cfg = ExportConfig(format=ExportFormat.MOV, output_path="/default.mov")
        jid = mgr.queue_export(uuid4(), cfg, output_path="/override.mov")
        info = mgr.get_job(jid)
        assert info["output_path"] == "/override.mov"

    def test_queue_max_jobs(self, small_mgr: ExportManager) -> None:
        for _ in range(3):
            assert _queue(small_mgr) is not None
        assert _queue(small_mgr) is None
        assert small_mgr.total_jobs == 3

    def test_initial_status_queued(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        info = mgr.get_job(jid)
        assert info["status"] == "queued"

    def test_format_in_job(self, mgr: ExportManager) -> None:
        cfg = ExportConfig(format=ExportFormat.GIF, resolution=(640, 480), fps=15)
        jid = mgr.queue_export(uuid4(), cfg)
        info = mgr.get_job(jid)
        assert info["format"] == "gif"
        assert info["resolution"] == (640, 480)
        assert info["fps"] == 15


# =============================================================================
# 상태 변경
# =============================================================================

class TestStateTransition:
    def test_start_export(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        assert mgr.start_export(jid)
        assert mgr.get_job(jid)["status"] == "in_progress"

    def test_start_nonexistent(self, mgr: ExportManager) -> None:
        assert not mgr.start_export(uuid4())

    def test_start_already_started(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        assert not mgr.start_export(jid)

    def test_complete_export(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        assert mgr.complete_export(jid, output_path="/done.mp4")
        info = mgr.get_job(jid)
        assert info["status"] == "completed"
        assert info["output_path"] == "/done.mp4"

    def test_complete_without_start(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        assert not mgr.complete_export(jid)

    def test_fail_export(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        assert mgr.fail_export(jid, error_message="인코딩 실패")
        info = mgr.get_job(jid)
        assert info["status"] == "failed"
        assert info["error_message"] == "인코딩 실패"

    def test_fail_without_start(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        assert not mgr.fail_export(jid)


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_job_nonexistent(self, mgr: ExportManager) -> None:
        assert mgr.get_job(uuid4()) is None

    def test_get_jobs_by_status(self, mgr: ExportManager) -> None:
        j1 = _queue(mgr)
        j2 = _queue(mgr)
        mgr.start_export(j1)
        queued = mgr.get_jobs_by_status(ExportStatus.QUEUED)
        assert j2 in queued
        assert j1 not in queued

    def test_get_queued_count(self, mgr: ExportManager) -> None:
        _queue(mgr)
        _queue(mgr)
        j3 = _queue(mgr)
        mgr.start_export(j3)
        assert mgr.get_queued_count() == 2

    def test_get_status_distribution(self, mgr: ExportManager) -> None:
        j1 = _queue(mgr)
        _queue(mgr)
        mgr.start_export(j1)
        mgr.complete_export(j1)
        dist = mgr.get_status_distribution()
        assert dist.get("queued", 0) == 1
        assert dist.get("completed", 0) == 1


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_remove_completed(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        mgr.complete_export(jid)
        assert mgr.remove_job(jid)
        assert mgr.total_jobs == 0

    def test_remove_failed(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        mgr.fail_export(jid)
        assert mgr.remove_job(jid)

    def test_remove_queued_blocked(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        assert not mgr.remove_job(jid)

    def test_remove_in_progress_blocked(self, mgr: ExportManager) -> None:
        jid = _queue(mgr)
        mgr.start_export(jid)
        assert not mgr.remove_job(jid)

    def test_clear_completed(self, mgr: ExportManager) -> None:
        j1 = _queue(mgr)
        j2 = _queue(mgr)
        _queue(mgr)
        mgr.start_export(j1)
        mgr.complete_export(j1)
        mgr.start_export(j2)
        mgr.complete_export(j2)
        removed = mgr.clear_completed()
        assert removed == 2
        assert mgr.total_jobs == 1


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, mgr: ExportManager) -> None:
        _queue(mgr)
        stats = mgr.get_stats()
        assert stats["total_jobs"] == 1

    def test_reset(self, mgr: ExportManager) -> None:
        _queue(mgr)
        mgr.reset()
        assert mgr.total_jobs == 0
