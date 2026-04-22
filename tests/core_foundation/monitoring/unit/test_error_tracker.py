# -*- coding: utf-8 -*-
"""monitoring/error_tracker.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from core_foundation.monitoring.error_tracker import (
    ErrorEvent,
    ErrorSeverity,
    ErrorSummary,
    ErrorTracker,
    MAX_CATEGORY_KEYS,
    MAX_ERROR_HISTORY,
    PATTERN_THRESHOLD,
    PATTERN_WINDOW,
    RATE_WINDOW_1HOUR,
    RATE_WINDOW_1MIN,
)


# =============================================================================
# 테스트 설정
# =============================================================================

@pytest.fixture(autouse=True)
def reset_tracker():
    ErrorTracker.reset()
    yield
    ErrorTracker.reset()


# =============================================================================
# ErrorSeverity 검증
# =============================================================================

class TestErrorSeverity:
    def test_member_count(self):
        assert len(ErrorSeverity) == 4

    def test_values(self):
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_to_korean(self):
        assert ErrorSeverity.LOW.to_korean() == "낮음"
        assert ErrorSeverity.CRITICAL.to_korean() == "치명적"


# =============================================================================
# ErrorEvent 검증
# =============================================================================

class TestErrorEvent:
    def test_slots(self):
        assert hasattr(ErrorEvent, "__slots__")

    def test_creation(self):
        event = ErrorEvent(
            error_type="ValueError",
            message="테스트",
            module="test",
            severity=ErrorSeverity.MEDIUM,
            timestamp=time.monotonic(),
            wall_time=time.time(),
        )
        assert event.error_type == "ValueError"
        assert event.severity == ErrorSeverity.MEDIUM

    def test_from_exception(self):
        try:
            raise ValueError("테스트 에러")
        except ValueError as exc:
            event = ErrorEvent.from_exception(
                exc,
                module="detection.ball",
                severity=ErrorSeverity.HIGH,
            )

        assert event.error_type == "ValueError"
        assert event.message == "테스트 에러"
        assert event.module == "detection.ball"
        assert event.traceback_str is not None
        assert "ValueError" in event.traceback_str

    def test_from_exception_no_traceback(self):
        try:
            raise RuntimeError("no tb")
        except RuntimeError as exc:
            event = ErrorEvent.from_exception(exc, capture_traceback=False)

        assert event.traceback_str is None

    def test_from_exception_with_context(self):
        try:
            raise TypeError("ctx test")
        except TypeError as exc:
            event = ErrorEvent.from_exception(
                exc, context={"camera_id": 1},
            )

        assert event.context["camera_id"] == 1

    def test_repr(self):
        event = ErrorEvent(
            error_type="KeyError",
            message="missing key",
            module="config",
            severity=ErrorSeverity.LOW,
            timestamp=0.0,
            wall_time=0.0,
        )
        r = repr(event)
        assert "low" in r
        assert "KeyError" in r


# =============================================================================
# ErrorSummary 검증
# =============================================================================

class TestErrorSummary:
    def test_slots(self):
        assert hasattr(ErrorSummary, "__slots__")

    def test_repr(self):
        summary = ErrorSummary(
            total_count=10,
            rate_per_minute=2.5,
            rate_per_hour=150.0,
            by_type={"ValueError": 5},
            by_module={"test": 10},
            by_severity={"medium": 10},
            patterns=[],
        )
        assert "total=10" in repr(summary)


# =============================================================================
# ErrorTracker — 기본 기록
# =============================================================================

class TestTrackerRecord:
    def test_record_exception(self):
        tracker = ErrorTracker.get_instance()
        try:
            raise ValueError("record test")
        except ValueError as exc:
            event = tracker.record(exc, module="test")

        assert event.error_type == "ValueError"
        assert tracker.total_count == 1

    def test_record_event(self):
        tracker = ErrorTracker.get_instance()
        event = ErrorEvent(
            error_type="CustomError",
            message="직접 이벤트",
            module="custom",
            severity=ErrorSeverity.HIGH,
            timestamp=time.monotonic(),
            wall_time=time.time(),
        )
        tracker.record(event)
        assert tracker.total_count == 1

    def test_multiple_records(self):
        tracker = ErrorTracker.get_instance()
        for i in range(10):
            try:
                raise RuntimeError(f"error {i}")
            except RuntimeError as exc:
                tracker.record(exc, module="loop")
        assert tracker.total_count == 10

    def test_ring_buffer_limit(self):
        tracker = ErrorTracker(max_history=5)
        for i in range(10):
            try:
                raise ValueError(f"overflow {i}")
            except ValueError as exc:
                tracker.record(exc)
        assert tracker.history_size == 5
        assert tracker.total_count == 10


# =============================================================================
# ErrorTracker — 에러율 계산
# =============================================================================

class TestTrackerRate:
    def test_rate_empty(self):
        tracker = ErrorTracker.get_instance()
        assert tracker.get_rate() == 0.0

    def test_rate_with_events(self):
        tracker = ErrorTracker.get_instance()
        for _ in range(6):
            try:
                raise ValueError("rate test")
            except ValueError as exc:
                tracker.record(exc)

        rate = tracker.get_rate(window_seconds=60.0)
        # 6건 / 1분 = 6.0
        assert rate == pytest.approx(6.0, abs=0.5)

    def test_rate_zero_window(self):
        tracker = ErrorTracker.get_instance()
        assert tracker.get_rate(window_seconds=0) == 0.0


# =============================================================================
# ErrorTracker — 패턴 감지
# =============================================================================

class TestTrackerPatterns:
    def test_no_pattern(self):
        tracker = ErrorTracker.get_instance()
        try:
            raise ValueError("once")
        except ValueError as exc:
            tracker.record(exc, module="test")

        patterns = tracker.detect_patterns(threshold=5)
        assert len(patterns) == 0

    def test_pattern_detected(self):
        tracker = ErrorTracker.get_instance()
        for _ in range(PATTERN_THRESHOLD):
            try:
                raise ValueError("repeated")
            except ValueError as exc:
                tracker.record(exc, module="detection")

        patterns = tracker.detect_patterns()
        assert len(patterns) == 1
        assert "detection:ValueError" in patterns[0]

    def test_multiple_patterns(self):
        tracker = ErrorTracker.get_instance()
        for _ in range(PATTERN_THRESHOLD):
            try:
                raise ValueError("v")
            except ValueError as exc:
                tracker.record(exc, module="mod_a")

        for _ in range(PATTERN_THRESHOLD):
            try:
                raise TypeError("t")
            except TypeError as exc:
                tracker.record(exc, module="mod_b")

        patterns = tracker.detect_patterns()
        assert len(patterns) == 2


# =============================================================================
# ErrorTracker — 집계 조회
# =============================================================================

class TestTrackerSummary:
    def test_get_summary(self):
        tracker = ErrorTracker.get_instance()
        for _ in range(3):
            try:
                raise ValueError("sum")
            except ValueError as exc:
                tracker.record(exc, module="test", severity=ErrorSeverity.HIGH)

        summary = tracker.get_summary()
        assert isinstance(summary, ErrorSummary)
        assert summary.total_count == 3
        assert summary.by_type["ValueError"] == 3
        assert summary.by_module["test"] == 3
        assert summary.by_severity["high"] == 3

    def test_get_recent(self):
        tracker = ErrorTracker.get_instance()
        for i in range(5):
            try:
                raise ValueError(f"recent {i}")
            except ValueError as exc:
                tracker.record(exc)

        recent = tracker.get_recent(3)
        assert len(recent) == 3
        # 최신순
        assert "recent 4" in recent[0].message

    def test_get_by_module(self):
        tracker = ErrorTracker.get_instance()
        try:
            raise ValueError("a")
        except ValueError as exc:
            tracker.record(exc, module="mod_a")
        try:
            raise ValueError("b")
        except ValueError as exc:
            tracker.record(exc, module="mod_b")

        results = tracker.get_by_module("mod_a")
        assert len(results) == 1

    def test_get_by_severity(self):
        tracker = ErrorTracker.get_instance()
        try:
            raise ValueError("critical")
        except ValueError as exc:
            tracker.record(exc, severity=ErrorSeverity.CRITICAL)
        try:
            raise ValueError("low")
        except ValueError as exc:
            tracker.record(exc, severity=ErrorSeverity.LOW)

        results = tracker.get_by_severity(ErrorSeverity.CRITICAL)
        assert len(results) == 1


# =============================================================================
# ErrorTracker — 관리
# =============================================================================

class TestTrackerManagement:
    def test_clear(self):
        tracker = ErrorTracker.get_instance()
        for _ in range(5):
            try:
                raise ValueError("clear")
            except ValueError as exc:
                tracker.record(exc)

        cleared = tracker.clear()
        assert cleared == 5
        assert tracker.total_count == 0
        assert tracker.history_size == 0

    def test_singleton(self):
        t1 = ErrorTracker.get_instance()
        t2 = ErrorTracker.get_instance()
        assert t1 is t2

    def test_repr(self):
        tracker = ErrorTracker.get_instance()
        assert "total=0" in repr(tracker)


# =============================================================================
# 스레드 안전 검증
# =============================================================================

class TestThreadSafety:
    def test_concurrent_record(self):
        tracker = ErrorTracker.get_instance()
        errors: list[Exception] = []

        def record_errors():
            try:
                for _ in range(20):
                    try:
                        raise ValueError("concurrent")
                    except ValueError as exc:
                        tracker.record(exc, module="thread")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_errors) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert tracker.total_count == 200


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_history(self):
        assert MAX_ERROR_HISTORY == 1000

    def test_rate_windows(self):
        assert RATE_WINDOW_1MIN == 60.0
        assert RATE_WINDOW_1HOUR == 3600.0

    def test_pattern_constants(self):
        assert PATTERN_THRESHOLD == 5
        assert PATTERN_WINDOW == 300.0


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.monitoring.error_tracker as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.monitoring.error_tracker as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.monitoring.error_tracker as mod
        assert mod.__version__ == "1.0.0"
