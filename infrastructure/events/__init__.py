# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/events
설명: 이벤트 서브모듈
      - event_types: 이벤트 런타임 타입 (Event, EventFilter, EventResult)
      - event_bus: 인메모리 Pub/Sub 이벤트 버스
      - event_handlers: 핸들러 추상화 및 기본 구현

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# event_types
# =============================================================================
from infrastructure.events.event_types import (
    DEFAULT_EVENT_SOURCE,
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
# event_bus
# =============================================================================
from infrastructure.events.event_bus import (
    DEFAULT_HANDLER_TIMEOUT_SEC,
    MAX_HANDLERS_PER_EVENT,
    MAX_SUBSCRIPTIONS,
    SUBSCRIPTION_ID_PREFIX,
    EventBus,
    EventBusStats,
    Subscription,
)

# =============================================================================
# event_handlers
# =============================================================================
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
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- event_types ---
    # 데이터 클래스
    "Event",
    "EventFilter",
    "EventResult",
    # 타입 별칭
    "EventCallback",
    # 상수
    "MAX_PAYLOAD_SIZE",
    "MAX_EVENT_HISTORY",
    "EVENT_ID_PREFIX",
    "DEFAULT_EVENT_SOURCE",
    "MAX_SOURCE_LENGTH",
    "MAX_CORRELATION_ID_LENGTH",
    # --- event_bus ---
    # 데이터 클래스
    "Subscription",
    "EventBusStats",
    # 핵심 클래스
    "EventBus",
    # 상수
    "MAX_SUBSCRIPTIONS",
    "MAX_HANDLERS_PER_EVENT",
    "SUBSCRIPTION_ID_PREFIX",
    "DEFAULT_HANDLER_TIMEOUT_SEC",
    # --- event_handlers ---
    # 추상 기반
    "BaseEventHandler",
    # 핸들러 구현
    "CallbackHandler",
    "LoggingHandler",
    "MetricCollectorHandler",
    "FilteredHandler",
    # 데이터 클래스
    "LogEntry",
    "EventMetric",
    # 상수
    "MAX_LOG_ENTRIES",
    "MAX_METRIC_TYPES",
    "HANDLER_NAME_MAX_LENGTH",
]

__version__ = "1.0.0"
