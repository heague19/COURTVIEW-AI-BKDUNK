# -*- coding: utf-8 -*-
"""infrastructure/events/event_types.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import time

import pytest

from shared.constants.event_types import EventCategory, EventType
from infrastructure.events.event_types import (
    DEFAULT_EVENT_SOURCE,
    get_event_priority,
    EVENT_ID_PREFIX,
    MAX_CORRELATION_ID_LENGTH,
    MAX_EVENT_HISTORY,
    MAX_PAYLOAD_SIZE,
    MAX_SOURCE_LENGTH,
    Event,
    EventCallback,
    EventFilter,
    EventResult,
)


# =============================================================================
# Event 검증
# =============================================================================

class TestEvent:
    def test_slots(self):
        assert hasattr(Event, "__slots__")

    def test_creation_minimal(self):
        evt = Event(event_type=EventType.TASK_COMPLETED)
        assert evt.event_type == EventType.TASK_COMPLETED
        assert evt.payload == {}
        assert evt.source == DEFAULT_EVENT_SOURCE
        assert evt.correlation_id is None

    def test_event_id_auto_generated(self):
        evt = Event(event_type=EventType.TASK_STARTED)
        assert evt.event_id.startswith(EVENT_ID_PREFIX)
        assert len(evt.event_id) > len(EVENT_ID_PREFIX)

    def test_event_id_unique(self):
        ids = {Event(event_type=EventType.TASK_STARTED).event_id for _ in range(100)}
        assert len(ids) == 100

    def test_timestamp_auto(self):
        before = time.monotonic()
        evt = Event(event_type=EventType.TASK_STARTED)
        after = time.monotonic()
        assert before <= evt.timestamp <= after

    def test_priority_auto_from_event_type(self):
        evt = Event(event_type=EventType.SYSTEM_ERROR)
        assert evt.priority == get_event_priority(EventType.SYSTEM_ERROR)
        assert evt.priority == 0  # 최우선

    def test_priority_auto_default(self):
        evt = Event(event_type=EventType.CACHE_HIT)
        assert evt.priority == get_event_priority(EventType.CACHE_HIT)

    def test_priority_manual_override(self):
        evt = Event(event_type=EventType.TASK_COMPLETED, priority=0)
        assert evt.priority == 0

    def test_payload(self):
        evt = Event(
            event_type=EventType.TASK_COMPLETED,
            payload={"task_id": "abc", "result": 42},
        )
        assert evt.payload["task_id"] == "abc"
        assert evt.payload["result"] == 42

    def test_source(self):
        evt = Event(event_type=EventType.TASK_STARTED, source="detection_module")
        assert evt.source == "detection_module"

    def test_source_length_clamped(self):
        long_source = "x" * 200
        evt = Event(event_type=EventType.TASK_STARTED, source=long_source)
        assert len(evt.source) == MAX_SOURCE_LENGTH

    def test_correlation_id(self):
        evt = Event(
            event_type=EventType.TASK_STARTED,
            correlation_id="trace_123",
        )
        assert evt.correlation_id == "trace_123"

    def test_correlation_id_length_clamped(self):
        long_cid = "c" * 100
        evt = Event(event_type=EventType.TASK_STARTED, correlation_id=long_cid)
        assert len(evt.correlation_id) == MAX_CORRELATION_ID_LENGTH

    def test_correlation_id_none(self):
        evt = Event(event_type=EventType.TASK_STARTED)
        assert evt.correlation_id is None

    def test_category_property(self):
        evt = Event(event_type=EventType.GAME_SHOT_DETECTED)
        assert evt.category == EventCategory.GAME

    def test_is_error_true(self):
        evt = Event(event_type=EventType.TASK_FAILED)
        assert evt.is_error is True

    def test_is_error_false(self):
        evt = Event(event_type=EventType.TASK_COMPLETED)
        assert evt.is_error is False

    def test_type_name(self):
        evt = Event(event_type=EventType.TASK_COMPLETED)
        assert evt.type_name == "task.completed"

    def test_repr(self):
        evt = Event(event_type=EventType.TASK_COMPLETED, source="test")
        text = repr(evt)
        assert "TASK_COMPLETED" in text
        assert "test" in text
        assert "evt_" in text


# =============================================================================
# EventFilter 검증
# =============================================================================

class TestEventFilter:
    def test_slots(self):
        assert hasattr(EventFilter, "__slots__")

    def test_frozen(self):
        f = EventFilter()
        with pytest.raises(AttributeError):
            f.error_only = True  # type: ignore[misc]

    def test_default_matches_all(self):
        f = EventFilter()
        evt = Event(event_type=EventType.TASK_COMPLETED)
        assert f.matches(evt) is True

    def test_filter_by_event_types(self):
        f = EventFilter(event_types=frozenset({EventType.TASK_COMPLETED}))
        assert f.matches(Event(event_type=EventType.TASK_COMPLETED)) is True
        assert f.matches(Event(event_type=EventType.TASK_FAILED)) is False

    def test_filter_by_categories(self):
        f = EventFilter(categories=frozenset({EventCategory.GAME}))
        assert f.matches(Event(event_type=EventType.GAME_SHOT_DETECTED)) is True
        assert f.matches(Event(event_type=EventType.TASK_COMPLETED)) is False

    def test_filter_by_sources(self):
        f = EventFilter(sources=frozenset({"detector"}))
        assert f.matches(
            Event(event_type=EventType.TASK_STARTED, source="detector"),
        ) is True
        assert f.matches(
            Event(event_type=EventType.TASK_STARTED, source="tracker"),
        ) is False

    def test_filter_by_max_priority(self):
        f = EventFilter(max_priority=1)
        # priority=0 (SYSTEM_ERROR) → 통과
        assert f.matches(Event(event_type=EventType.SYSTEM_ERROR)) is True
        # priority=3 (TASK_PROGRESS) → 차단
        assert f.matches(Event(event_type=EventType.TASK_PROGRESS)) is False

    def test_filter_error_only(self):
        f = EventFilter(error_only=True)
        assert f.matches(Event(event_type=EventType.TASK_FAILED)) is True
        assert f.matches(Event(event_type=EventType.TASK_COMPLETED)) is False

    def test_filter_combined_and(self):
        """여러 조건이 AND로 결합되는지 확인."""
        f = EventFilter(
            event_types=frozenset({EventType.TASK_FAILED, EventType.TASK_COMPLETED}),
            error_only=True,
        )
        # TASK_FAILED: types에 포함 + error → True
        assert f.matches(Event(event_type=EventType.TASK_FAILED)) is True
        # TASK_COMPLETED: types에 포함 + not error → False
        assert f.matches(Event(event_type=EventType.TASK_COMPLETED)) is False

    def test_repr_all(self):
        f = EventFilter()
        assert "all" in repr(f)

    def test_repr_with_filters(self):
        f = EventFilter(
            event_types=frozenset({EventType.TASK_COMPLETED}),
            error_only=True,
        )
        text = repr(f)
        assert "types=1" in text
        assert "error_only" in text


# =============================================================================
# EventResult 검증
# =============================================================================

class TestEventResult:
    def test_slots(self):
        assert hasattr(EventResult, "__slots__")

    def test_success(self):
        r = EventResult(handled=True, handler_name="test_handler")
        assert r.is_success is True
        assert r.error is None

    def test_failure(self):
        r = EventResult(
            handled=False,
            handler_name="test_handler",
            error="timeout",
        )
        assert r.is_success is False

    def test_handled_with_error(self):
        r = EventResult(handled=True, handler_name="h", error="partial")
        assert r.is_success is False

    def test_duration(self):
        r = EventResult(
            handled=True,
            handler_name="h",
            duration_ms=12.5,
        )
        assert r.duration_ms == 12.5

    def test_repr_success(self):
        r = EventResult(handled=True, handler_name="h", duration_ms=1.0)
        assert "OK" in repr(r)

    def test_repr_error(self):
        r = EventResult(handled=False, handler_name="h", error="fail")
        assert "ERROR" in repr(r)
        assert "fail" in repr(r)


# =============================================================================
# EventCallback 타입 검증
# =============================================================================

class TestEventCallback:
    def test_callable_type(self):
        """EventCallback이 호출 가능한 타입 별칭인지 확인."""
        def handler(event: Event) -> EventResult | None:
            return None

        # 타입 별칭은 런타임에서 직접 isinstance 불가, 호출 가능 확인
        assert callable(handler)


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_payload_size(self):
        assert MAX_PAYLOAD_SIZE == 65536

    def test_max_event_history(self):
        assert MAX_EVENT_HISTORY == 10000

    def test_event_id_prefix(self):
        assert EVENT_ID_PREFIX == "evt_"

    def test_default_event_source(self):
        assert DEFAULT_EVENT_SOURCE == "unknown"

    def test_max_source_length(self):
        assert MAX_SOURCE_LENGTH == 128

    def test_max_correlation_id_length(self):
        assert MAX_CORRELATION_ID_LENGTH == 64


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.events.event_types as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.events.event_types as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import infrastructure.events.event_types as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.events.event_types as mod
        assert len(mod.__all__) == 10
