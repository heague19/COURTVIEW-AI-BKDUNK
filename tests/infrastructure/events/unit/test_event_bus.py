# -*- coding: utf-8 -*-
"""infrastructure/events/event_bus.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from shared.constants.event_types import EventCategory, EventType
from infrastructure.events.event_types import (
    Event,
    EventCallback,
    EventFilter,
    EventResult,
)
from infrastructure.events.event_bus import (
    DEFAULT_HANDLER_TIMEOUT_SEC,
    MAX_HANDLERS_PER_EVENT,
    MAX_SUBSCRIPTIONS,
    SUBSCRIPTION_ID_PREFIX,
    EventBus,
    EventBusStats,
    Subscription,
)


@pytest.fixture(autouse=True)
def reset_bus():
    EventBus.reset()
    yield
    EventBus.reset()


def _noop_handler(event: Event) -> EventResult | None:
    return None


def _counting_handler(counter: list[int]):
    """호출 횟수를 추적하는 핸들러 팩토리."""
    def handler(event: Event) -> EventResult | None:
        counter.append(1)
        return None
    return handler


# =============================================================================
# Subscription 검증
# =============================================================================

class TestSubscription:
    def test_slots(self):
        assert hasattr(Subscription, "__slots__")

    def test_creation(self):
        sub = Subscription(
            subscription_id="sub_test",
            handler=_noop_handler,
            handler_name="test",
            event_filter=EventFilter(),
        )
        assert sub.subscription_id == "sub_test"
        assert sub.handler_name == "test"
        assert sub.priority == 0

    def test_repr(self):
        sub = Subscription(
            subscription_id="sub_abc",
            handler=_noop_handler,
            handler_name="my_handler",
            event_filter=EventFilter(),
        )
        text = repr(sub)
        assert "sub_abc" in text
        assert "my_handler" in text


# =============================================================================
# EventBusStats 검증
# =============================================================================

class TestEventBusStats:
    def test_slots(self):
        assert hasattr(EventBusStats, "__slots__")

    def test_error_rate_zero(self):
        stats = EventBusStats(
            subscription_count=0, total_published=0,
            total_handled=0, total_errors=0, history_size=0,
        )
        assert stats.error_rate == 0.0

    def test_error_rate_calculated(self):
        stats = EventBusStats(
            subscription_count=1, total_published=10,
            total_handled=10, total_errors=3, history_size=10,
        )
        assert abs(stats.error_rate - 0.3) < 0.001

    def test_repr(self):
        stats = EventBusStats(
            subscription_count=2, total_published=5,
            total_handled=5, total_errors=1, history_size=5,
        )
        text = repr(stats)
        assert "subs=2" in text
        assert "published=5" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        b1 = EventBus.get_instance()
        b2 = EventBus.get_instance()
        assert b1 is b2

    def test_reset(self):
        b1 = EventBus.get_instance()
        EventBus.reset()
        b2 = EventBus.get_instance()
        assert b1 is not b2


# =============================================================================
# 구독 관리
# =============================================================================

class TestSubscribeManagement:
    def test_subscribe(self):
        bus = EventBus.get_instance()
        sub_id = bus.subscribe(_noop_handler, "test")
        assert sub_id.startswith(SUBSCRIPTION_ID_PREFIX)
        assert bus.subscription_count == 1

    def test_subscribe_with_filter(self):
        bus = EventBus.get_instance()
        f = EventFilter(event_types=frozenset({EventType.TASK_COMPLETED}))
        sub_id = bus.subscribe(_noop_handler, "test", event_filter=f)
        assert bus.has_subscription(sub_id) is True

    def test_subscribe_with_priority(self):
        bus = EventBus.get_instance()
        bus.subscribe(_noop_handler, "low", priority=10)
        bus.subscribe(_noop_handler, "high", priority=0)
        assert bus.subscription_count == 2

    def test_unsubscribe(self):
        bus = EventBus.get_instance()
        sub_id = bus.subscribe(_noop_handler, "test")
        assert bus.unsubscribe(sub_id) is True
        assert bus.has_subscription(sub_id) is False
        assert bus.subscription_count == 0

    def test_unsubscribe_nonexistent(self):
        bus = EventBus.get_instance()
        assert bus.unsubscribe("sub_nonexistent") is False

    def test_subscription_ids(self):
        bus = EventBus.get_instance()
        id1 = bus.subscribe(_noop_handler, "h1")
        id2 = bus.subscribe(_noop_handler, "h2")
        ids = bus.subscription_ids
        assert id1 in ids and id2 in ids

    def test_clear_subscriptions(self):
        bus = EventBus.get_instance()
        bus.subscribe(_noop_handler, "h1")
        bus.subscribe(_noop_handler, "h2")
        count = bus.clear_subscriptions()
        assert count == 2
        assert bus.subscription_count == 0

    def test_max_subscriptions_limit(self):
        bus = EventBus.get_instance()
        for i in range(MAX_SUBSCRIPTIONS):
            bus.subscribe(_noop_handler, f"h{i}")
        with pytest.raises(ValueError, match="최대 구독 수"):
            bus.subscribe(_noop_handler, "overflow")


# =============================================================================
# 발행
# =============================================================================

class TestPublish:
    def test_publish_no_subscribers(self):
        bus = EventBus.get_instance()
        evt = Event(event_type=EventType.TASK_COMPLETED)
        results = bus.publish(evt)
        assert results == []

    def test_publish_single_handler(self):
        bus = EventBus.get_instance()
        counter: list[int] = []
        bus.subscribe(_counting_handler(counter), "counter")

        evt = Event(event_type=EventType.TASK_COMPLETED)
        results = bus.publish(evt)
        assert len(results) == 1
        assert results[0].is_success is True
        assert len(counter) == 1

    def test_publish_multiple_handlers(self):
        bus = EventBus.get_instance()
        c1: list[int] = []
        c2: list[int] = []
        bus.subscribe(_counting_handler(c1), "h1")
        bus.subscribe(_counting_handler(c2), "h2")

        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert len(c1) == 1 and len(c2) == 1

    def test_publish_filtered(self):
        bus = EventBus.get_instance()
        counter: list[int] = []
        f = EventFilter(event_types=frozenset({EventType.TASK_COMPLETED}))
        bus.subscribe(_counting_handler(counter), "filtered", event_filter=f)

        # 매칭 이벤트
        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert len(counter) == 1

        # 비매칭 이벤트
        bus.publish(Event(event_type=EventType.TASK_FAILED))
        assert len(counter) == 1  # 변화 없음

    def test_publish_priority_order(self):
        bus = EventBus.get_instance()
        order: list[str] = []

        def make_handler(name: str):
            def handler(event: Event) -> EventResult | None:
                order.append(name)
                return None
            return handler

        bus.subscribe(make_handler("low"), "low", priority=10)
        bus.subscribe(make_handler("high"), "high", priority=0)
        bus.subscribe(make_handler("mid"), "mid", priority=5)

        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert order == ["high", "mid", "low"]

    def test_publish_handler_error_isolated(self):
        """한 핸들러 에러가 다른 핸들러에 영향 없음."""
        bus = EventBus.get_instance()
        counter: list[int] = []

        def error_handler(event: Event) -> EventResult | None:
            raise RuntimeError("test error")

        bus.subscribe(error_handler, "error_h", priority=0)
        bus.subscribe(_counting_handler(counter), "good_h", priority=1)

        results = bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert len(results) == 2
        # 에러 핸들러
        assert results[0].is_success is False
        assert "test error" in results[0].error
        # 정상 핸들러 (영향 없음)
        assert results[1].is_success is True
        assert len(counter) == 1

    def test_publish_handler_returns_result(self):
        bus = EventBus.get_instance()

        def custom_handler(event: Event) -> EventResult | None:
            return EventResult(handled=True, handler_name="custom")

        bus.subscribe(custom_handler, "custom")
        results = bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert results[0].handler_name == "custom"
        assert results[0].duration_ms >= 0.0

    def test_publish_max_handlers_limit(self):
        bus = EventBus.get_instance()
        counter: list[int] = []
        for i in range(MAX_HANDLERS_PER_EVENT + 10):
            bus.subscribe(_counting_handler(counter), f"h{i}")

        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert len(counter) == MAX_HANDLERS_PER_EVENT


# =============================================================================
# 히스토리
# =============================================================================

class TestHistory:
    def test_publish_adds_to_history(self):
        bus = EventBus.get_instance()
        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        assert bus.history_size == 1

    def test_get_history(self):
        bus = EventBus.get_instance()
        bus.publish(Event(event_type=EventType.TASK_STARTED, payload={"n": 1}))
        bus.publish(Event(event_type=EventType.TASK_COMPLETED, payload={"n": 2}))

        history = bus.get_history(limit=10)
        assert len(history) == 2
        # 최신 순
        assert history[0].payload["n"] == 2
        assert history[1].payload["n"] == 1

    def test_get_history_limit(self):
        bus = EventBus.get_instance()
        for i in range(10):
            bus.publish(Event(event_type=EventType.TASK_STARTED))

        history = bus.get_history(limit=3)
        assert len(history) == 3

    def test_clear_history(self):
        bus = EventBus.get_instance()
        for i in range(5):
            bus.publish(Event(event_type=EventType.TASK_STARTED))

        count = bus.clear_history()
        assert count == 5
        assert bus.history_size == 0

    def test_history_max_size(self):
        """deque maxlen으로 자동 제한."""
        from infrastructure.events.event_types import MAX_EVENT_HISTORY
        bus = EventBus.get_instance()
        # 직접 deque maxlen 확인
        assert bus._history.maxlen == MAX_EVENT_HISTORY


# =============================================================================
# 통계
# =============================================================================

class TestStats:
    def test_initial_stats(self):
        bus = EventBus.get_instance()
        stats = bus.get_stats()
        assert stats.subscription_count == 0
        assert stats.total_published == 0
        assert stats.total_handled == 0
        assert stats.total_errors == 0

    def test_stats_after_publish(self):
        bus = EventBus.get_instance()
        bus.subscribe(_noop_handler, "h1")
        bus.publish(Event(event_type=EventType.TASK_COMPLETED))

        stats = bus.get_stats()
        assert stats.total_published == 1
        assert stats.total_handled == 1
        assert stats.total_errors == 0

    def test_stats_error_counted(self):
        bus = EventBus.get_instance()

        def error_h(event: Event) -> EventResult | None:
            raise RuntimeError("fail")

        bus.subscribe(error_h, "error_h")
        bus.publish(Event(event_type=EventType.TASK_COMPLETED))

        stats = bus.get_stats()
        assert stats.total_errors == 1

    def test_reset_stats(self):
        bus = EventBus.get_instance()
        bus.subscribe(_noop_handler, "h")
        bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        bus.reset_stats()

        stats = bus.get_stats()
        assert stats.total_published == 0
        assert stats.total_handled == 0


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_subscribe_publish(self):
        bus = EventBus.get_instance()
        errors: list[Exception] = []

        def subscriber():
            try:
                for i in range(20):
                    sid = bus.subscribe(_noop_handler, f"t_{i}")
                    bus.unsubscribe(sid)
            except Exception as e:
                errors.append(e)

        def publisher():
            try:
                for i in range(20):
                    bus.publish(Event(event_type=EventType.TASK_STARTED))
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=subscriber) for _ in range(3)]
            + [threading.Thread(target=publisher) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0

    def test_concurrent_singleton(self):
        instances: list[EventBus] = []

        def get_inst():
            instances.append(EventBus.get_instance())

        threads = [threading.Thread(target=get_inst) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert all(inst is instances[0] for inst in instances)


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        bus = EventBus.get_instance()
        text = repr(bus)
        assert "EventBus" in text
        assert "subscriptions=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_subscriptions(self):
        assert MAX_SUBSCRIPTIONS == 500

    def test_max_handlers_per_event(self):
        assert MAX_HANDLERS_PER_EVENT == 50

    def test_subscription_id_prefix(self):
        assert SUBSCRIPTION_ID_PREFIX == "sub_"

    def test_default_handler_timeout(self):
        assert DEFAULT_HANDLER_TIMEOUT_SEC == 5.0


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.events.event_bus as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.events.event_bus as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import infrastructure.events.event_bus as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.events.event_bus as mod
        assert len(mod.__all__) == 7
