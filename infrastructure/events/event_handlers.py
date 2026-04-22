# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/events
파일: event_handlers.py
설명: 이벤트 핸들러 추상화 및 기본 구현
      - BaseEventHandler: 핸들러 추상 기반 클래스 (EventCallback 호환)
      - CallbackHandler: 단순 콜백 래퍼
      - LoggingHandler: 이벤트 로깅 (내부 로그 리스트)
      - MetricCollectorHandler: 이벤트 타입별 메트릭 수집
      - FilteredHandler: 자체 EventFilter 적용 핸들러

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.event_types import EventCategory, EventType

from infrastructure.events.event_types import (
    Event,
    EventCallback,
    EventFilter,
    EventResult,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 로깅 핸들러 최대 보관 수
MAX_LOG_ENTRIES: Final[int] = 5000

# 메트릭 핸들러 최대 추적 타입 수
MAX_METRIC_TYPES: Final[int] = 200

# 핸들러 이름 최대 길이
HANDLER_NAME_MAX_LENGTH: Final[int] = 64


# =============================================================================
# 추상 기반 핸들러
# =============================================================================

class BaseEventHandler(ABC):
    """이벤트 핸들러 추상 기반 클래스.

    모든 이벤트 핸들러는 이 클래스를 상속한다.
    ``handle()`` 메서드만 구현하면 ``__call__``로 EventCallback 호환.

    사용 예시::

        class MyHandler(BaseEventHandler):
            def handle(self, event: Event) -> EventResult | None:
                print(event)
                return None

        handler = MyHandler("my_handler")
        bus.subscribe(handler, handler.handler_name)
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        if len(name) > HANDLER_NAME_MAX_LENGTH:
            name = name[:HANDLER_NAME_MAX_LENGTH]
        self._name = name

    @property
    def handler_name(self) -> str:
        """핸들러 이름."""
        return self._name

    @abstractmethod
    def handle(self, event: Event) -> EventResult | None:
        """이벤트 처리.

        Args:
            event: 처리할 이벤트

        Returns:
            처리 결과 (None이면 기본 성공 처리)
        """

    def __call__(self, event: Event) -> EventResult | None:
        """EventCallback 호환 호출."""
        return self.handle(event)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}')"


# =============================================================================
# CallbackHandler: 단순 콜백 래퍼
# =============================================================================

class CallbackHandler(BaseEventHandler):
    """단순 콜백 함수를 핸들러로 래핑.

    사용 예시::

        def my_callback(event: Event) -> EventResult | None:
            print(event)
            return None

        handler = CallbackHandler("my_handler", my_callback)
        bus.subscribe(handler, handler.handler_name)
    """

    __slots__ = ("_callback",)

    def __init__(self, name: str, callback: EventCallback) -> None:
        super().__init__(name)
        self._callback = callback

    def handle(self, event: Event) -> EventResult | None:
        """콜백 실행."""
        return self._callback(event)


# =============================================================================
# LogEntry: 로그 항목
# =============================================================================

@dataclass(slots=True)
class LogEntry:
    """로그 항목.

    Attributes:
        event_type: 이벤트 타입
        event_id: 이벤트 ID
        source: 이벤트 소스
        timestamp: 수신 시각
        category: 이벤트 카테고리
        is_error: 에러 여부
    """

    event_type: EventType
    event_id: str
    source: str
    timestamp: float
    category: EventCategory
    is_error: bool

    def __repr__(self) -> str:
        status = "ERROR" if self.is_error else "OK"
        return (
            f"LogEntry({self.event_type.name}, "
            f"source='{self.source}', {status})"
        )


# =============================================================================
# LoggingHandler: 이벤트 로깅
# =============================================================================

class LoggingHandler(BaseEventHandler):
    """이벤트 로깅 핸들러.

    수신한 이벤트를 내부 로그에 기록.
    최대 MAX_LOG_ENTRIES 개까지 보관 (FIFO).
    """

    __slots__ = ("_entries", "_lock", "_max_entries")

    def __init__(
        self,
        name: str = "logging_handler",
        *,
        max_entries: int = MAX_LOG_ENTRIES,
    ) -> None:
        super().__init__(name)
        self._max_entries = max(100, min(max_entries, MAX_LOG_ENTRIES))
        self._entries: list[LogEntry] = []
        self._lock = threading.RLock()

    def handle(self, event: Event) -> EventResult | None:
        """이벤트 로그 기록."""
        entry = LogEntry(
            event_type=event.event_type,
            event_id=event.event_id,
            source=event.source,
            timestamp=event.timestamp,
            category=event.category,
            is_error=event.is_error,
        )

        with self._lock:
            self._entries.append(entry)
            # FIFO 제한
            if len(self._entries) > self._max_entries:
                overflow = len(self._entries) - self._max_entries
                self._entries = self._entries[overflow:]

        return EventResult(
            handled=True,
            handler_name=self._name,
        )

    @property
    def entry_count(self) -> int:
        """로그 항목 수."""
        with self._lock:
            return len(self._entries)

    def get_entries(self, limit: int = 100) -> list[LogEntry]:
        """로그 항목 조회 (최신 순).

        Args:
            limit: 최대 반환 수

        Returns:
            로그 항목 목록
        """
        with self._lock:
            if not self._entries:
                return []
            clamped = max(1, min(limit, len(self._entries)))
            return list(reversed(self._entries[-clamped:]))

    def get_error_entries(self, limit: int = 100) -> list[LogEntry]:
        """에러 로그 항목 조회.

        Args:
            limit: 최대 반환 수

        Returns:
            에러 로그 항목 목록
        """
        with self._lock:
            errors = [e for e in self._entries if e.is_error]
            if not errors:
                return []
            clamped = max(1, min(limit, len(errors)))
            return list(reversed(errors[-clamped:]))

    def clear(self) -> int:
        """로그 초기화.

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count


# =============================================================================
# EventMetric: 이벤트 타입별 메트릭
# =============================================================================

@dataclass(slots=True)
class EventMetric:
    """이벤트 타입별 메트릭.

    Attributes:
        event_type: 이벤트 타입
        count: 발생 횟수
        error_count: 에러 발생 수
        last_seen: 마지막 수신 시각
    """

    event_type: EventType
    count: int = 0
    error_count: int = 0
    last_seen: float = 0.0

    @property
    def error_rate(self) -> float:
        """에러율."""
        if self.count == 0:
            return 0.0
        return self.error_count / self.count

    def __repr__(self) -> str:
        return (
            f"EventMetric({self.event_type.name}, "
            f"count={self.count}, errors={self.error_count})"
        )


# =============================================================================
# MetricCollectorHandler: 이벤트 메트릭 수집
# =============================================================================

class MetricCollectorHandler(BaseEventHandler):
    """이벤트 메트릭 수집 핸들러.

    이벤트 타입별 발생 횟수, 에러 수, 최근 발생 시각을 추적.
    최대 MAX_METRIC_TYPES 개 타입까지 추적 (초과 시 무시).
    """

    __slots__ = ("_metrics", "_lock", "_total_count")

    def __init__(self, name: str = "metric_collector") -> None:
        super().__init__(name)
        self._metrics: dict[EventType, EventMetric] = {}
        self._lock = threading.RLock()
        self._total_count: int = 0

    def handle(self, event: Event) -> EventResult | None:
        """메트릭 수집."""
        with self._lock:
            self._total_count += 1

            metric = self._metrics.get(event.event_type)
            if metric is None:
                if len(self._metrics) >= MAX_METRIC_TYPES:
                    return EventResult(
                        handled=True,
                        handler_name=self._name,
                    )
                metric = EventMetric(event_type=event.event_type)
                self._metrics[event.event_type] = metric

            metric.count += 1
            metric.last_seen = event.timestamp
            if event.is_error:
                metric.error_count += 1

        return EventResult(
            handled=True,
            handler_name=self._name,
        )

    def get_metric(self, event_type: EventType) -> EventMetric | None:
        """특정 이벤트 타입 메트릭 조회.

        Args:
            event_type: 이벤트 타입

        Returns:
            메트릭 또는 None
        """
        with self._lock:
            metric = self._metrics.get(event_type)
            if metric is None:
                return None
            # 방어적 복사
            return EventMetric(
                event_type=metric.event_type,
                count=metric.count,
                error_count=metric.error_count,
                last_seen=metric.last_seen,
            )

    def get_all_metrics(self) -> list[EventMetric]:
        """전체 메트릭 조회 (발생 횟수 내림차순).

        Returns:
            메트릭 목록
        """
        with self._lock:
            return sorted(
                [
                    EventMetric(
                        event_type=m.event_type,
                        count=m.count,
                        error_count=m.error_count,
                        last_seen=m.last_seen,
                    )
                    for m in self._metrics.values()
                ],
                key=lambda m: m.count,
                reverse=True,
            )

    @property
    def total_count(self) -> int:
        """총 수집 이벤트 수."""
        with self._lock:
            return self._total_count

    @property
    def tracked_types(self) -> int:
        """추적 중인 이벤트 타입 수."""
        with self._lock:
            return len(self._metrics)

    def reset(self) -> None:
        """메트릭 초기화."""
        with self._lock:
            self._metrics.clear()
            self._total_count = 0


# =============================================================================
# FilteredHandler: 자체 필터 적용 핸들러
# =============================================================================

class FilteredHandler(BaseEventHandler):
    """자체 EventFilter를 가진 핸들러.

    EventBus의 구독 필터와 별개로, 핸들러 내부에서 추가 필터링.
    내부 필터를 통과한 이벤트만 inner 핸들러로 전달.

    사용 예시::

        inner = CallbackHandler("inner", my_callback)
        filtered = FilteredHandler(
            "filtered",
            inner=inner,
            event_filter=EventFilter(error_only=True),
        )
        bus.subscribe(filtered, filtered.handler_name)
    """

    __slots__ = ("_inner", "_filter")

    def __init__(
        self,
        name: str,
        inner: BaseEventHandler | EventCallback,
        event_filter: EventFilter,
    ) -> None:
        super().__init__(name)
        self._inner = inner
        self._filter = event_filter

    def handle(self, event: Event) -> EventResult | None:
        """필터 적용 후 내부 핸들러 호출."""
        if not self._filter.matches(event):
            return EventResult(
                handled=False,
                handler_name=self._name,
            )

        if callable(self._inner):
            return self._inner(event)
        return None

    @property
    def event_filter(self) -> EventFilter:
        """내부 필터."""
        return self._filter


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
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
