# -*- coding: utf-8 -*-
"""config/watcher.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import os
import tempfile
import threading
import time

import pytest

from core_foundation.config.watcher import (
    ChangeCallback,
    ConfigWatcher,
    DEFAULT_POLL_INTERVAL,
    FileChangeEvent,
    FileChangeType,
    MAX_CALLBACKS,
    MAX_CHANGE_HISTORY,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)


# =============================================================================
# FileChangeType 검증
# =============================================================================

class TestFileChangeType:
    """FileChangeType Enum 검증."""

    def test_member_count(self):
        assert len(FileChangeType) == 3

    def test_values(self):
        assert FileChangeType.MODIFIED.value == "modified"
        assert FileChangeType.CREATED.value == "created"
        assert FileChangeType.DELETED.value == "deleted"

    def test_to_korean(self):
        assert FileChangeType.MODIFIED.to_korean() == "수정"
        assert FileChangeType.CREATED.to_korean() == "생성"
        assert FileChangeType.DELETED.to_korean() == "삭제"


# =============================================================================
# FileChangeEvent 검증
# =============================================================================

class TestFileChangeEvent:
    """FileChangeEvent 데이터클래스 검증."""

    def test_slots(self):
        assert hasattr(FileChangeEvent, "__slots__")

    def test_creation(self):
        event = FileChangeEvent(
            file_path="/test/config.yaml",
            change_type=FileChangeType.MODIFIED,
            timestamp=time.monotonic(),
        )
        assert event.file_path == "/test/config.yaml"
        assert event.change_type == FileChangeType.MODIFIED

    def test_defaults(self):
        event = FileChangeEvent(
            file_path="test.yaml",
            change_type=FileChangeType.CREATED,
            timestamp=0.0,
        )
        assert event.old_mtime is None
        assert event.new_size is None

    def test_repr(self):
        event = FileChangeEvent(
            file_path="test.yaml",
            change_type=FileChangeType.DELETED,
            timestamp=0.0,
        )
        assert "deleted" in repr(event)
        assert "test.yaml" in repr(event)


# =============================================================================
# ConfigWatcher — 생성 검증
# =============================================================================

class TestWatcherCreation:
    """ConfigWatcher 생성 검증."""

    def test_default_creation(self):
        w = ConfigWatcher()
        assert w.poll_interval == DEFAULT_POLL_INTERVAL
        assert w.watched_count == 0
        assert w.is_running is False

    def test_custom_interval(self):
        w = ConfigWatcher(poll_interval=5.0)
        assert w.poll_interval == 5.0

    def test_interval_clamped_min(self):
        w = ConfigWatcher(poll_interval=0.01)
        assert w.poll_interval == MIN_POLL_INTERVAL

    def test_interval_clamped_max(self):
        w = ConfigWatcher(poll_interval=999.0)
        assert w.poll_interval == MAX_POLL_INTERVAL

    def test_repr(self):
        w = ConfigWatcher()
        r = repr(w)
        assert "files=0" in r
        assert "running=False" in r


# =============================================================================
# ConfigWatcher — 감시 대상 관리
# =============================================================================

class TestWatchManagement:
    """감시 대상 파일 관리 검증."""

    def test_watch_file(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        assert w.watch(f) is True
        assert w.watched_count == 1

    def test_watch_duplicate(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        assert w.watch(f) is True
        assert w.watch(f) is False  # 이미 감시 중
        assert w.watched_count == 1

    def test_unwatch(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        assert w.unwatch(f) is True
        assert w.watched_count == 0

    def test_unwatch_nonexistent(self):
        w = ConfigWatcher()
        assert w.unwatch("/nonexistent/file.yaml") is False

    def test_watch_directory(self, tmp_path):
        (tmp_path / "a.yaml").write_text("a: 1")
        (tmp_path / "b.yaml").write_text("b: 2")
        (tmp_path / "c.txt").write_text("not yaml")

        w = ConfigWatcher()
        added = w.watch_directory(tmp_path, pattern="*.yaml")
        assert added == 2
        assert w.watched_count == 2

    def test_watch_directory_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.yaml").write_text("a: 1")
        (sub / "b.yaml").write_text("b: 2")

        w = ConfigWatcher()
        added = w.watch_directory(tmp_path)
        assert added == 2

    def test_watch_directory_nonexistent(self):
        w = ConfigWatcher()
        assert w.watch_directory("/nonexistent/dir") == 0

    def test_watched_files_list(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        files = w.watched_files
        assert len(files) == 1
        assert str(f.resolve()) in files[0]


# =============================================================================
# ConfigWatcher — 콜백 관리
# =============================================================================

class TestCallbackManagement:
    """콜백 관리 검증."""

    def test_add_callback(self):
        w = ConfigWatcher()
        cb = lambda event: None
        assert w.add_callback(cb) is True
        assert w.callback_count == 1

    def test_remove_callback(self):
        w = ConfigWatcher()
        cb = lambda event: None
        w.add_callback(cb)
        assert w.remove_callback(cb) is True
        assert w.callback_count == 0

    def test_remove_nonexistent_callback(self):
        w = ConfigWatcher()
        assert w.remove_callback(lambda e: None) is False

    def test_clear_callbacks(self):
        w = ConfigWatcher()
        for i in range(5):
            w.add_callback(lambda e, i=i: None)
        w.clear_callbacks()
        assert w.callback_count == 0

    def test_max_callbacks(self):
        w = ConfigWatcher()
        for i in range(MAX_CALLBACKS):
            assert w.add_callback(lambda e, i=i: None) is True
        assert w.add_callback(lambda e: None) is False


# =============================================================================
# ConfigWatcher — 변경 감지 (poll_once)
# =============================================================================

class TestChangeDetection:
    """변경 감지 검증 (수동 폴링)."""

    def test_detect_modification(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value1")

        w = ConfigWatcher()
        w.watch(f)

        # 초기 폴링 — 변경 없음
        events = w.poll_once()
        assert len(events) == 0

        # 파일 수정
        time.sleep(0.05)  # mtime 변경 보장
        f.write_text("key: value2")

        events = w.poll_once()
        assert len(events) == 1
        assert events[0].change_type == FileChangeType.MODIFIED
        assert str(f.resolve()) in events[0].file_path

    def test_detect_deletion(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        w.poll_once()  # 초기 상태 캡처

        # 파일 삭제
        f.unlink()

        events = w.poll_once()
        assert len(events) == 1
        assert events[0].change_type == FileChangeType.DELETED

    def test_detect_creation(self, tmp_path):
        f = tmp_path / "test.yaml"

        w = ConfigWatcher()
        w.watch(f)  # 아직 존재하지 않는 파일

        # 파일 생성
        f.write_text("key: new")

        events = w.poll_once()
        assert len(events) == 1
        assert events[0].change_type == FileChangeType.CREATED

    def test_no_change(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        w.poll_once()  # 초기 상태

        events = w.poll_once()
        assert len(events) == 0

    def test_multiple_file_changes(self, tmp_path):
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        f1.write_text("a: 1")
        f2.write_text("b: 2")

        w = ConfigWatcher()
        w.watch(f1)
        w.watch(f2)
        w.poll_once()

        # 둘 다 수정
        time.sleep(0.05)
        f1.write_text("a: 10")
        f2.write_text("b: 20")

        events = w.poll_once()
        assert len(events) == 2


# =============================================================================
# ConfigWatcher — 변경 이력
# =============================================================================

class TestChangeHistory:
    """변경 이력 검증."""

    def test_history_recorded(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        w.poll_once()

        time.sleep(0.05)
        f.write_text("key: changed")
        w.poll_once()

        assert w.change_count == 1
        history = w.change_history
        assert len(history) == 1
        assert history[0].change_type == FileChangeType.MODIFIED

    def test_clear_history(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        w.poll_once()

        time.sleep(0.05)
        f.write_text("key: changed")
        w.poll_once()

        w.clear_history()
        assert w.change_count == 0

    def test_history_defensive_copy(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        w = ConfigWatcher()
        w.watch(f)
        w.poll_once()
        time.sleep(0.05)
        f.write_text("key: changed")
        w.poll_once()

        h1 = w.change_history
        h2 = w.change_history
        assert h1 is not h2


# =============================================================================
# ConfigWatcher — 콜백 실행
# =============================================================================

class TestCallbackExecution:
    """콜백 실행 검증."""

    def test_callback_called(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        events_received: list[FileChangeEvent] = []

        w = ConfigWatcher()
        w.watch(f)
        w.add_callback(lambda e: events_received.append(e))
        w.poll_once()

        time.sleep(0.05)
        f.write_text("key: changed")

        # poll_once는 콜백을 직접 호출하지 않음 (내부 _check_all_files만 호출)
        # 콜백 테스트는 start/stop 통합 또는 _fire_callbacks 직접 테스트
        events = w.poll_once()
        # 수동 콜백 발화
        for event in events:
            w._fire_callbacks(event)

        assert len(events_received) == 1

    def test_callback_exception_isolated(self, tmp_path):
        """콜백 예외가 다른 콜백에 영향 없음."""
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        results: list[str] = []

        def bad_callback(e: FileChangeEvent) -> None:
            raise ValueError("의도적 예외")

        def good_callback(e: FileChangeEvent) -> None:
            results.append("ok")

        w = ConfigWatcher()
        w.watch(f)
        w.add_callback(bad_callback)
        w.add_callback(good_callback)
        w.poll_once()

        time.sleep(0.05)
        f.write_text("key: changed")
        events = w.poll_once()
        for event in events:
            w._fire_callbacks(event)

        assert len(results) == 1  # good_callback 정상 실행


# =============================================================================
# ConfigWatcher — start/stop
# =============================================================================

class TestStartStop:
    """감시 스레드 시작/중지 검증."""

    def test_start_stop(self):
        w = ConfigWatcher(poll_interval=MIN_POLL_INTERVAL)
        assert w.start() is True
        assert w.is_running is True
        assert w.stop() is True
        assert w.is_running is False

    def test_start_twice(self):
        w = ConfigWatcher(poll_interval=MIN_POLL_INTERVAL)
        assert w.start() is True
        assert w.start() is False  # 이미 실행 중
        w.stop()

    def test_pause_resume(self):
        w = ConfigWatcher(poll_interval=MIN_POLL_INTERVAL)
        w.start()
        assert w.is_paused is False

        w.pause()
        assert w.is_paused is True

        w.resume()
        assert w.is_paused is False

        w.stop()

    def test_daemon_thread(self):
        """감시 스레드는 daemon이어야 함."""
        w = ConfigWatcher(poll_interval=MIN_POLL_INTERVAL)
        w.start()
        assert w._thread is not None
        assert w._thread.daemon is True
        w.stop()

    def test_background_detection(self, tmp_path):
        """백그라운드 감시로 변경 감지."""
        f = tmp_path / "test.yaml"
        f.write_text("key: value")

        detected: list[FileChangeEvent] = []

        w = ConfigWatcher(poll_interval=MIN_POLL_INTERVAL)
        w.watch(f)
        w.add_callback(lambda e: detected.append(e))
        w.start()

        # 초기 폴링 대기
        time.sleep(MIN_POLL_INTERVAL + 0.3)

        # 파일 수정
        f.write_text("key: changed")

        # 변경 감지 대기
        time.sleep(MIN_POLL_INTERVAL * 2 + 0.3)

        w.stop()

        assert len(detected) >= 1
        assert any(e.change_type == FileChangeType.MODIFIED for e in detected)


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    """상수 검증."""

    def test_default_poll_interval(self):
        assert DEFAULT_POLL_INTERVAL == 2.0

    def test_min_poll_interval(self):
        assert MIN_POLL_INTERVAL == 0.5

    def test_max_poll_interval(self):
        assert MAX_POLL_INTERVAL == 60.0

    def test_max_callbacks(self):
        assert MAX_CALLBACKS == 100

    def test_max_change_history(self):
        assert MAX_CHANGE_HISTORY == 200


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    """__all__ 및 __version__ 검증."""

    def test_all_exists(self):
        import core_foundation.config.watcher as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.config.watcher as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not in module"

    def test_version(self):
        import core_foundation.config.watcher as mod
        assert mod.__version__ == "1.0.0"
