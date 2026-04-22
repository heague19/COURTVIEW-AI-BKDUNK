# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/events
파일: event_types.py
설명: 이벤트 런타임 타입 정의
      - Event: 이벤트 엔벨로프 (타입 + 페이로드 + 메타데이터)
      - EventFilter: 구독 필터 (타입/카테고리/소스/우선순위)
      - EventResult: 핸들러 처리 결과
      - EventCallback: 핸들러 콜백 타입 정의

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.event_types import (
    EventCategory,
    EventType,
)


def get_event_priority(event_type: EventType) -> int:
    """이벤트 타입에서 우선순위 추출.

    에러 이벤트는 높은 우선순위(0), 일반 이벤트는 기본(2).

    Args:
        event_type: 이벤트 타입

    Returns:
        우선순위 (0=최우선, 4=최저)
    """
    if event_type.is_error_event:
        return 0
    # 카테고리 기반 우선순위
    _CATEGORY_PRIORITY: dict[EventCategory, int] = {
        EventCategory.SYSTEM: 1,
        EventCategory.INFRASTRUCTURE: 1,
        EventCategory.ANALYSIS: 2,
        EventCategory.GAME: 2,
        EventCategory.REFEREE: 2,
        EventCategory.FEEDBACK: 3,
        EventCategory.LEARNING: 3,
        EventCategory.USER: 3,
    }
    return _CATEGORY_PRIORITY.get(event_type.category, 2)


# =============================================================================
# 상수 정의
# =============================================================================

# 페이로드 최대 크기 (바이트 기준 추정)
MAX_PAYLOAD_SIZE: Final[int] = 65536

# 이벤트 히스토리 최대 보관 수
MAX_EVENT_HISTORY: Final[int] = 10000

# 이벤트 ID 접두사
EVENT_ID_PREFIX: Final[str] = "evt_"

# 기본 이벤트 소스
DEFAULT_EVENT_SOURCE: Final[str] = "unknown"

# 소스 이름 최대 길이
MAX_SOURCE_LENGTH: Final[int] = 128

# 상관 ID 최대 길이
MAX_CORRELATION_ID_LENGTH: Final[int] = 64


# =============================================================================
# Event: 이벤트 엔벨로프
# =============================================================================

@dataclass(slots=True)
class Event:
    """이벤트 엔벨로프.

    시스템 내에서 전달되는 이벤트의 표준 구조.
    모든 이벤트는 EventType(shared 정의)을 포함하며,
    페이로드에 도메인별 데이터를 담는다.

    Attributes:
        event_type: 이벤트 타입 (shared.constants.event_types.EventType)
        payload: 이벤트 데이터 (키-값 쌍)
        event_id: 고유 식별자 (자동 생성)
        timestamp: 생성 시각 (time.monotonic)
        source: 발생 모듈/컴포넌트
        correlation_id: 추적용 상관 ID (None이면 독립 이벤트)
        priority: 우선순위 (0=최우선, 4=최저, -1이면 자동 설정)
    """

    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(
        default_factory=lambda: f"{EVENT_ID_PREFIX}{uuid.uuid4().hex[:16]}",
    )
    timestamp: float = field(default_factory=time.monotonic)
    source: str = DEFAULT_EVENT_SOURCE
    correlation_id: str | None = None
    priority: int = field(default=-1)

    def __post_init__(self) -> None:
        """우선순위 자동 설정 + 입력 검증."""
        # 우선순위 미설정(-1) 시 EventType에서 자동 추출
        if self.priority < 0:
            self.priority = get_event_priority(self.event_type)

        # 소스 길이 제한
        if len(self.source) > MAX_SOURCE_LENGTH:
            self.source = self.source[:MAX_SOURCE_LENGTH]

        # 상관 ID 길이 제한
        if (
            self.correlation_id is not None
            and len(self.correlation_id) > MAX_CORRELATION_ID_LENGTH
        ):
            self.correlation_id = self.correlation_id[:MAX_CORRELATION_ID_LENGTH]

        # 페이로드 크기 제한 (직렬화 근사 바이트)
        if self.payload:
            estimated_size = len(str(self.payload).encode("utf-8"))
            if estimated_size > MAX_PAYLOAD_SIZE:
                self.payload = {"_truncated": True, "_original_size": estimated_size}

    @property
    def category(self) -> EventCategory:
        """이벤트 카테고리."""
        return self.event_type.category

    @property
    def is_error(self) -> bool:
        """에러 이벤트 여부."""
        return self.event_type.is_error_event

    @property
    def type_name(self) -> str:
        """이벤트 타입 문자열 값."""
        return self.event_type.value

    def __repr__(self) -> str:
        return (
            f"Event(type={self.event_type.name}, "
            f"id='{self.event_id}', "
            f"source='{self.source}', "
            f"priority={self.priority})"
        )


# =============================================================================
# EventFilter: 구독 필터
# =============================================================================

@dataclass(slots=True, frozen=True)
class EventFilter:
    """이벤트 구독 필터.

    None 필드는 "모든 값 허용"을 의미.
    여러 필드가 설정된 경우 AND 조건 적용.

    Attributes:
        event_types: 허용할 이벤트 타입 집합 (None=전체)
        categories: 허용할 카테고리 집합 (None=전체)
        sources: 허용할 소스 집합 (None=전체)
        max_priority: 최대 우선순위 값 (이 값 이하만 허용, 0=최우선)
        error_only: True이면 에러 이벤트만 통과
    """

    event_types: frozenset[EventType] | None = None
    categories: frozenset[EventCategory] | None = None
    sources: frozenset[str] | None = None
    max_priority: int | None = None
    error_only: bool = False

    def matches(self, event: Event) -> bool:
        """이벤트가 필터 조건에 부합하는지 확인.

        Args:
            event: 검사할 이벤트

        Returns:
            필터 통과 여부 (모든 조건 AND)
        """
        if self.event_types is not None and event.event_type not in self.event_types:
            return False
        if self.categories is not None and event.category not in self.categories:
            return False
        if self.sources is not None and event.source not in self.sources:
            return False
        if self.max_priority is not None and event.priority > self.max_priority:
            return False
        if self.error_only and not event.is_error:
            return False
        return True

    def __repr__(self) -> str:
        parts: list[str] = []
        if self.event_types is not None:
            parts.append(f"types={len(self.event_types)}")
        if self.categories is not None:
            parts.append(f"categories={len(self.categories)}")
        if self.sources is not None:
            parts.append(f"sources={len(self.sources)}")
        if self.max_priority is not None:
            parts.append(f"max_priority={self.max_priority}")
        if self.error_only:
            parts.append("error_only")
        detail = ", ".join(parts) if parts else "all"
        return f"EventFilter({detail})"


# =============================================================================
# EventResult: 핸들러 처리 결과
# =============================================================================

@dataclass(slots=True)
class EventResult:
    """이벤트 핸들러 처리 결과.

    Attributes:
        handled: 처리 완료 여부
        handler_name: 핸들러 이름
        duration_ms: 처리 소요 시간 (밀리초)
        error: 에러 메시지 (None이면 정상)
    """

    handled: bool
    handler_name: str
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """성공 여부 (처리 완료 + 에러 없음)."""
        return self.handled and self.error is None

    def __repr__(self) -> str:
        status = "OK" if self.is_success else f"ERROR: {self.error}"
        return (
            f"EventResult(handler='{self.handler_name}', "
            f"{status}, {self.duration_ms:.1f}ms)"
        )


# =============================================================================
# 타입 별칭
# =============================================================================

# 이벤트 콜백 타입 (핸들러 함수 시그니처)
EventCallback = Callable[[Event], EventResult | None]


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
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
]

__version__ = "1.0.0"
