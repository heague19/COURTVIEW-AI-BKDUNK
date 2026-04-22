# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/events
파일: event_bus.py
설명: 인메모리 Pub/Sub 이벤트 버스
      - 구독(subscribe) / 발행(publish) 패턴
      - EventFilter 기반 선택적 구독
      - 우선순위 기반 핸들러 실행 순서
      - 이벤트 히스토리 관리 (deque, 최대 MAX_EVENT_HISTORY)
      - 핸들러 실행 에러 격리 (한 핸들러 실패가 나머지에 영향 없음)
      - Singleton + 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from infrastructure.events.event_types import (
    Event,
    EventCallback,
    EventFilter,
    EventResult,
    MAX_EVENT_HISTORY,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 구독 수
MAX_SUBSCRIPTIONS: Final[int] = 500

# 단일 이벤트에 대한 최대 핸들러 실행 수
MAX_HANDLERS_PER_EVENT: Final[int] = 50

# 구독 ID 접두사
SUBSCRIPTION_ID_PREFIX: Final[str] = "sub_"

# 기본 핸들러 타임아웃 (초)
DEFAULT_HANDLER_TIMEOUT_SEC: Final[float] = 5.0


# =============================================================================
# Subscription: 구독 정보
# =============================================================================

@dataclass(slots=True)
class Subscription:
    """이벤트 구독 정보.

    Attributes:
        subscription_id: 구독 고유 ID
        handler: 이벤트 콜백
        handler_name: 핸들러 이름 (디버깅/통계용)
        event_filter: 이벤트 필터
        priority: 핸들러 실행 우선순위 (낮을수록 먼저 실행)
        created_at: 구독 생성 시각
    """

    subscription_id: str
    handler: EventCallback
    handler_name: str
    event_filter: EventFilter
    priority: int = 0
    created_at: float = field(default_factory=time.monotonic)

    def __repr__(self) -> str:
        return (
            f"Subscription(id='{self.subscription_id}', "
            f"handler='{self.handler_name}', "
            f"filter={self.event_filter})"
        )


# =============================================================================
# EventBusStats: 통계
# =============================================================================

@dataclass(slots=True)
class EventBusStats:
    """이벤트 버스 통계.

    Attributes:
        subscription_count: 현재 구독 수
        total_published: 총 발행 수
        total_handled: 총 처리 수
        total_errors: 총 에러 수
        history_size: 히스토리 크기
    """

    subscription_count: int
    total_published: int
    total_handled: int
    total_errors: int
    history_size: int

    @property
    def error_rate(self) -> float:
        """에러율 (0.0 ~ 1.0)."""
        if self.total_handled == 0:
            return 0.0
        return self.total_errors / self.total_handled

    def __repr__(self) -> str:
        return (
            f"EventBusStats(subs={self.subscription_count}, "
            f"published={self.total_published}, "
            f"errors={self.total_errors}, "
            f"error_rate={self.error_rate:.1%})"
        )


# =============================================================================
# 핵심 클래스: EventBus
# =============================================================================

class EventBus:
    """인메모리 Pub/Sub 이벤트 버스.

    시스템 내 모듈 간 느슨한 결합을 위한 이벤트 발행/구독 시스템.
    모든 핸들러는 동기 실행되며, 실행 순서는 priority 값으로 결정.

    사용 예시::

        bus = EventBus.get_instance()

        # 구독
        def on_task_done(event: Event) -> EventResult | None:
            print(f"완료: {event.payload}")
            return None

        sub_id = bus.subscribe(
            handler=on_task_done,
            handler_name="task_logger",
            event_filter=EventFilter(
                event_types=frozenset({EventType.TASK_COMPLETED}),
            ),
        )

        # 발행
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            payload={"task_id": "123"},
        )
        results = bus.publish(event)

        # 구독 해제
        bus.unsubscribe(sub_id)

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: EventBus | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._history: deque[Event] = deque(maxlen=MAX_EVENT_HISTORY)
        self._lock = threading.RLock()
        self._total_published: int = 0
        self._total_handled: int = 0
        self._total_errors: int = 0

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> EventBus:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 구독 관리
    # =========================================================================

    def subscribe(
        self,
        handler: EventCallback,
        handler_name: str,
        *,
        event_filter: EventFilter | None = None,
        priority: int = 0,
    ) -> str:
        """이벤트 구독 등록.

        Args:
            handler: 이벤트 콜백 함수
            handler_name: 핸들러 이름
            event_filter: 이벤트 필터 (None이면 전체 수신)
            priority: 핸들러 실행 우선순위 (낮을수록 먼저)

        Returns:
            구독 ID

        Raises:
            ValueError: 최대 구독 수 초과
        """
        with self._lock:
            if len(self._subscriptions) >= MAX_SUBSCRIPTIONS:
                raise ValueError(
                    f"최대 구독 수 초과: {MAX_SUBSCRIPTIONS}"
                )

            sub_id = f"{SUBSCRIPTION_ID_PREFIX}{uuid.uuid4().hex[:12]}"
            subscription = Subscription(
                subscription_id=sub_id,
                handler=handler,
                handler_name=handler_name,
                event_filter=event_filter or EventFilter(),
                priority=priority,
            )
            self._subscriptions[sub_id] = subscription
            return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """구독 해제.

        Args:
            subscription_id: 구독 ID

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                return True
            return False

    def has_subscription(self, subscription_id: str) -> bool:
        """구독 존재 여부."""
        with self._lock:
            return subscription_id in self._subscriptions

    @property
    def subscription_count(self) -> int:
        """현재 구독 수."""
        with self._lock:
            return len(self._subscriptions)

    @property
    def subscription_ids(self) -> list[str]:
        """구독 ID 목록."""
        with self._lock:
            return list(self._subscriptions.keys())

    def clear_subscriptions(self) -> int:
        """전체 구독 해제.

        Returns:
            해제된 구독 수
        """
        with self._lock:
            count = len(self._subscriptions)
            self._subscriptions.clear()
            return count

    # =========================================================================
    # 발행
    # =========================================================================

    def publish(self, event: Event) -> list[EventResult]:
        """이벤트 동기 발행.

        등록된 핸들러를 우선순위 순으로 실행하고 결과를 반환.
        한 핸들러의 예외가 다른 핸들러 실행에 영향을 주지 않는다.

        Args:
            event: 발행할 이벤트

        Returns:
            핸들러 처리 결과 목록
        """
        # 1단계: lock 하에서 통계 갱신 + 매칭 구독 목록 스냅샷
        with self._lock:
            self._total_published += 1
            self._history.append(event)

            matched = [
                sub for sub in self._subscriptions.values()
                if sub.event_filter.matches(event)
            ]
            matched.sort(key=lambda s: s.priority)

            # 최대 핸들러 수 제한
            if len(matched) > MAX_HANDLERS_PER_EVENT:
                matched = matched[:MAX_HANDLERS_PER_EVENT]

        # 2단계: lock 해제 후 핸들러 실행 (블로킹 방지)
        results: list[EventResult] = []
        for sub in matched:
            result = self._execute_handler(sub, event)
            results.append(result)

        return results

    def _execute_handler(
        self,
        subscription: Subscription,
        event: Event,
    ) -> EventResult:
        """단일 핸들러 실행 (에러 격리).

        Args:
            subscription: 구독 정보
            event: 이벤트

        Returns:
            처리 결과
        """
        start = time.monotonic()
        try:
            result = subscription.handler(event)
            elapsed = (time.monotonic() - start) * 1000.0

            # 타임아웃 초과 경고
            timed_out = elapsed > (DEFAULT_HANDLER_TIMEOUT_SEC * 1000.0)

            if result is None:
                result = EventResult(
                    handled=True,
                    handler_name=subscription.handler_name,
                    duration_ms=elapsed,
                    error=f"handler exceeded timeout ({elapsed:.1f}ms > {DEFAULT_HANDLER_TIMEOUT_SEC * 1000.0:.0f}ms)" if timed_out else None,
                )
            else:
                result.duration_ms = elapsed

            with self._lock:
                self._total_handled += 1
            return result

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000.0
            with self._lock:
                self._total_handled += 1
                self._total_errors += 1

            return EventResult(
                handled=False,
                handler_name=subscription.handler_name,
                duration_ms=elapsed,
                error=str(exc),
            )

    # =========================================================================
    # 히스토리
    # =========================================================================

    @property
    def history_size(self) -> int:
        """히스토리 크기."""
        with self._lock:
            return len(self._history)

    def get_history(self, limit: int = 100) -> list[Event]:
        """최근 이벤트 히스토리.

        Args:
            limit: 최대 반환 수

        Returns:
            최근 이벤트 목록 (최신 순)
        """
        with self._lock:
            clamped = max(1, min(limit, len(self._history)))
            items = list(self._history)
            return items[-clamped:][::-1]

    def clear_history(self) -> int:
        """히스토리 초기화.

        Returns:
            삭제된 이벤트 수
        """
        with self._lock:
            count = len(self._history)
            self._history.clear()
            return count

    # =========================================================================
    # 통계
    # =========================================================================

    def get_stats(self) -> EventBusStats:
        """이벤트 버스 통계."""
        with self._lock:
            return EventBusStats(
                subscription_count=len(self._subscriptions),
                total_published=self._total_published,
                total_handled=self._total_handled,
                total_errors=self._total_errors,
                history_size=len(self._history),
            )

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._total_published = 0
            self._total_handled = 0
            self._total_errors = 0

    def __repr__(self) -> str:
        return (
            f"EventBus(subscriptions={self.subscription_count}, "
            f"published={self._total_published}, "
            f"history={self.history_size})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
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
]

__version__ = "1.0.0"
