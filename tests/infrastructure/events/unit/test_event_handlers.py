# -*- coding: utf-8 -*-
"""infrastructure/events/event_handlers.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from shared.constants.event_types import EventCategory, EventType
from infrastructure.events.event_types import (
    Event,
    EventCallback,
    EventFilter,
    EventResult,
)
from infrastructure.events.event_handlers import (
    HANDLER_NAME_MAX_LENGTH,
    MAX_LOG_ENTRIES,
    MAX_METRIC_TYPES,
    BaseEventHandler,
    CallbackHandler,
    EventMetric,
    FilteredHandler,
    LogEntry,
    LoggingHandler,
    MetricCollectorHandler,
)


# =============================================================================
# BaseEventHandler 검증
# =============================================================================

class TestBaseEventHandler:
    def test_abstract(self):
        with pytest.raises(TypeError):
            BaseEventHandler("test")  # type: ignore[abstract]

    def test_concrete_subclass(self):
        class ConcreteHandler(BaseEventHandler):
            def handle(self, event: Event) -> EventResult | None:
                return None

        h = ConcreteHandler("my_handler")
        assert h.handler_name == "my_handler"

    def test_name_clamped(self):
        class ConcreteHandler(BaseEventHandler):
            def handle(self, event: Event) -> EventResult | None:
                return None

        long_name = "x" * 100
        h = ConcreteHandler(long_name)
        assert len(h.handler_name) == HANDLER_NAME_MAX_LENGTH

    def test_callable(self):
        class ConcreteHandler(BaseEventHandler):
            def handle(self, event: Event) -> EventResult | None:
                return EventResult(handled=True, handler_name="c")

        h = ConcreteHandler("test")
        evt = Event(event_type=EventType.TASK_COMPLETED)
        result = h(evt)
        assert result is not None
        assert result.handled is True

    def test_repr(self):
        class ConcreteHandler(BaseEventHandler):
            def handle(self, event: Event) -> EventResult | None:
                return None

        h = ConcreteHandler("test")
        assert "ConcreteHandler" in repr(h)
        assert "test" in repr(h)


# =============================================================================
# CallbackHandler 검증
# =============================================================================

class TestCallbackHandler:
    def test_creation(self):
        def cb(event: Event) -> EventResult | None:
            return None

        h = CallbackHandler("cb_handler", cb)
        assert h.handler_name == "cb_handler"

    def test_handle_delegates(self):
        received: list[Event] = []

        def cb(event: Event) -> EventResult | None:
            received.append(event)
            return EventResult(handled=True, handler_name="cb")

        h = CallbackHandler("cb_handler", cb)
        evt = Event(event_type=EventType.TASK_COMPLETED)
        result = h.handle(evt)

        assert len(received) == 1
        assert received[0] is evt
        assert result.is_success is True

    def test_callable_compat(self):
        def cb(event: Event) -> EventResult | None:
            return None

        h = CallbackHandler("cb", cb)
        assert callable(h)


# =============================================================================
# LogEntry 검증
# =============================================================================

class TestLogEntry:
    def test_slots(self):
        assert hasattr(LogEntry, "__slots__")

    def test_creation(self):
        entry = LogEntry(
            event_type=EventType.TASK_COMPLETED,
            event_id="evt_123",
            source="test",
            timestamp=1.0,
            category=EventCategory.ANALYSIS,
            is_error=False,
        )
        assert entry.event_type == EventType.TASK_COMPLETED
        assert entry.is_error is False

    def test_repr_ok(self):
        entry = LogEntry(
            event_type=EventType.TASK_COMPLETED,
            event_id="e1",
            source="s",
            timestamp=0.0,
            category=EventCategory.ANALYSIS,
            is_error=False,
        )
        assert "OK" in repr(entry)

    def test_repr_error(self):
        entry = LogEntry(
            event_type=EventType.TASK_FAILED,
            event_id="e1",
            source="s",
            timestamp=0.0,
            category=EventCategory.ANALYSIS,
            is_error=True,
        )
        assert "ERROR" in repr(entry)


# =============================================================================
# LoggingHandler 검증
# =============================================================================

class TestLoggingHandler:
    def test_handle_records(self):
        h = LoggingHandler()
        evt = Event(event_type=EventType.TASK_COMPLETED, source="test")
        result = h.handle(evt)
        assert result.is_success is True
        assert h.entry_count == 1

    def test_get_entries(self):
        h = LoggingHandler()
        h.handle(Event(event_type=EventType.TASK_STARTED, source="a"))
        h.handle(Event(event_type=EventType.TASK_COMPLETED, source="b"))

        entries = h.get_entries(limit=10)
        assert len(entries) == 2
        # 최신 순
        assert entries[0].source == "b"
        assert entries[1].source == "a"

    def test_get_entries_limit(self):
        h = LoggingHandler()
        for _ in range(10):
            h.handle(Event(event_type=EventType.TASK_STARTED))

        entries = h.get_entries(limit=3)
        assert len(entries) == 3

    def test_get_entries_empty(self):
        h = LoggingHandler()
        assert h.get_entries() == []

    def test_get_error_entries(self):
        h = LoggingHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        h.handle(Event(event_type=EventType.TASK_FAILED))
        h.handle(Event(event_type=EventType.SYSTEM_ERROR))

        errors = h.get_error_entries()
        assert len(errors) == 2
        assert all(e.is_error for e in errors)

    def test_get_error_entries_empty(self):
        h = LoggingHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        assert h.get_error_entries() == []

    def test_clear(self):
        h = LoggingHandler()
        for _ in range(5):
            h.handle(Event(event_type=EventType.TASK_STARTED))

        count = h.clear()
        assert count == 5
        assert h.entry_count == 0

    def test_max_entries_fifo(self):
        h = LoggingHandler(max_entries=100)
        for _ in range(150):
            h.handle(Event(event_type=EventType.TASK_STARTED))
        assert h.entry_count == 100

    def test_max_entries_clamped_min(self):
        h = LoggingHandler(max_entries=1)
        # 최소 100으로 클램핑
        assert h._max_entries == 100

    def test_custom_name(self):
        h = LoggingHandler("my_logger")
        assert h.handler_name == "my_logger"

    def test_thread_safe(self):
        h = LoggingHandler()
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(50):
                    h.handle(Event(event_type=EventType.TASK_STARTED))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert h.entry_count == 250


# =============================================================================
# EventMetric 검증
# =============================================================================

class TestEventMetric:
    def test_slots(self):
        assert hasattr(EventMetric, "__slots__")

    def test_creation(self):
        m = EventMetric(event_type=EventType.TASK_COMPLETED)
        assert m.count == 0
        assert m.error_count == 0

    def test_error_rate_zero(self):
        m = EventMetric(event_type=EventType.TASK_COMPLETED, count=0)
        assert m.error_rate == 0.0

    def test_error_rate(self):
        m = EventMetric(
            event_type=EventType.TASK_COMPLETED,
            count=10,
            error_count=3,
        )
        assert abs(m.error_rate - 0.3) < 0.001

    def test_repr(self):
        m = EventMetric(event_type=EventType.TASK_COMPLETED, count=5, error_count=1)
        text = repr(m)
        assert "TASK_COMPLETED" in text
        assert "count=5" in text


# =============================================================================
# MetricCollectorHandler 검증
# =============================================================================

class TestMetricCollectorHandler:
    def test_handle_counts(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        h.handle(Event(event_type=EventType.TASK_FAILED))

        assert h.total_count == 3
        assert h.tracked_types == 2

    def test_get_metric(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        h.handle(Event(event_type=EventType.TASK_COMPLETED))

        m = h.get_metric(EventType.TASK_COMPLETED)
        assert m is not None
        assert m.count == 2
        assert m.error_count == 0

    def test_get_metric_defensive_copy(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))

        m1 = h.get_metric(EventType.TASK_COMPLETED)
        m2 = h.get_metric(EventType.TASK_COMPLETED)
        assert m1 is not m2  # 방어적 복사

    def test_get_metric_nonexistent(self):
        h = MetricCollectorHandler()
        assert h.get_metric(EventType.TASK_COMPLETED) is None

    def test_error_tracking(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_FAILED))
        h.handle(Event(event_type=EventType.TASK_FAILED))

        m = h.get_metric(EventType.TASK_FAILED)
        assert m is not None
        assert m.error_count == 2
        assert m.count == 2

    def test_get_all_metrics_sorted(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_STARTED))
        for _ in range(5):
            h.handle(Event(event_type=EventType.TASK_COMPLETED))
        for _ in range(3):
            h.handle(Event(event_type=EventType.TASK_FAILED))

        metrics = h.get_all_metrics()
        assert len(metrics) == 3
        # 내림차순
        assert metrics[0].count >= metrics[1].count >= metrics[2].count

    def test_reset(self):
        h = MetricCollectorHandler()
        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        h.reset()
        assert h.total_count == 0
        assert h.tracked_types == 0

    def test_max_metric_types(self):
        """최대 추적 타입 수 초과 시 새 타입 무시."""
        h = MetricCollectorHandler()
        # EventType에 충분한 멤버가 있으므로 직접 테스트
        all_types = list(EventType)
        for et in all_types[:MAX_METRIC_TYPES]:
            h.handle(Event(event_type=et))

        assert h.tracked_types == min(len(all_types), MAX_METRIC_TYPES)

        # 추가 타입이 있다면 무시 확인
        if len(all_types) > MAX_METRIC_TYPES:
            overflow_type = all_types[MAX_METRIC_TYPES]
            h.handle(Event(event_type=overflow_type))
            assert h.get_metric(overflow_type) is None

    def test_thread_safe(self):
        h = MetricCollectorHandler()
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(50):
                    h.handle(Event(event_type=EventType.TASK_STARTED))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert h.total_count == 250


# =============================================================================
# FilteredHandler 검증
# =============================================================================

class TestFilteredHandler:
    def test_passes_matching_event(self):
        received: list[Event] = []

        def inner_cb(event: Event) -> EventResult | None:
            received.append(event)
            return EventResult(handled=True, handler_name="inner")

        f = EventFilter(event_types=frozenset({EventType.TASK_COMPLETED}))
        h = FilteredHandler("filtered", inner=inner_cb, event_filter=f)

        evt = Event(event_type=EventType.TASK_COMPLETED)
        result = h.handle(evt)
        assert result.is_success is True
        assert len(received) == 1

    def test_blocks_non_matching_event(self):
        received: list[Event] = []

        def inner_cb(event: Event) -> EventResult | None:
            received.append(event)
            return None

        f = EventFilter(event_types=frozenset({EventType.TASK_COMPLETED}))
        h = FilteredHandler("filtered", inner=inner_cb, event_filter=f)

        evt = Event(event_type=EventType.TASK_FAILED)
        result = h.handle(evt)
        assert result.handled is False
        assert len(received) == 0

    def test_with_base_handler_inner(self):
        class InnerHandler(BaseEventHandler):
            def __init__(self):
                super().__init__("inner")
                self.called = False

            def handle(self, event: Event) -> EventResult | None:
                self.called = True
                return EventResult(handled=True, handler_name="inner")

        inner = InnerHandler()
        f = EventFilter()  # 모든 이벤트 통과
        h = FilteredHandler("filtered", inner=inner, event_filter=f)

        h.handle(Event(event_type=EventType.TASK_COMPLETED))
        assert inner.called is True

    def test_event_filter_property(self):
        f = EventFilter(error_only=True)
        h = FilteredHandler("f", inner=lambda e: None, event_filter=f)
        assert h.event_filter is f

    def test_callable_compat(self):
        h = FilteredHandler(
            "f",
            inner=lambda e: None,
            event_filter=EventFilter(),
        )
        assert callable(h)


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_log_entries(self):
        assert MAX_LOG_ENTRIES == 5000

    def test_max_metric_types(self):
        assert MAX_METRIC_TYPES == 200

    def test_handler_name_max_length(self):
        assert HANDLER_NAME_MAX_LENGTH == 64


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.events.event_handlers as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.events.event_handlers as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import infrastructure.events.event_handlers as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.events.event_handlers as mod
        assert len(mod.__all__) == 10
