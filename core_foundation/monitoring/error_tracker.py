# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: error_tracker.py
설명: 에러 추적/집계 엔진
      - 에러 이벤트 기록 (타임스탬프, 모듈, 예외 정보)
      - 에러율 계산 (분당, 시간당)
      - 에러 패턴 감지 (동일 에러 반복)
      - 카테고리/모듈별 집계
      - 링 버퍼 기반 이력 관리 (메모리 상한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import collections
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 에러 이력 최대 보관 수 (링 버퍼)
MAX_ERROR_HISTORY: Final[int] = 1000

# 에러율 계산 시간 창 (초)
RATE_WINDOW_1MIN: Final[float] = 60.0
RATE_WINDOW_1HOUR: Final[float] = 3600.0

# 에러 패턴 감지 임계값 — 같은 에러가 이 횟수 이상 발생하면 패턴 감지
PATTERN_THRESHOLD: Final[int] = 5

# 에러 패턴 감지 시간 창 (초)
PATTERN_WINDOW: Final[float] = 300.0

# 카테고리별 집계 최대 키 수
MAX_CATEGORY_KEYS: Final[int] = 500


# =============================================================================
# 에러 심각도 열거형
# =============================================================================

@unique
class ErrorSeverity(Enum):
    """에러 심각도."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _SEVERITY_KOREAN_MAP[self]


_SEVERITY_KOREAN_MAP: Final[dict[ErrorSeverity, str]] = {
    ErrorSeverity.LOW: "낮음",
    ErrorSeverity.MEDIUM: "보통",
    ErrorSeverity.HIGH: "높음",
    ErrorSeverity.CRITICAL: "치명적",
}


# =============================================================================
# 에러 이벤트 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ErrorEvent:
    """단일 에러 이벤트.

    Attributes:
        error_type: 예외 클래스 이름 (예: "ValueError")
        message: 에러 메시지
        module: 발생 모듈/컴포넌트
        severity: 심각도
        timestamp: 발생 시각 (monotonic)
        wall_time: 발생 시각 (wall clock, epoch)
        traceback_str: 스택 트레이스 문자열 (None이면 미수집)
        context: 추가 컨텍스트 정보
    """

    error_type: str
    message: str
    module: str
    severity: ErrorSeverity
    timestamp: float
    wall_time: float
    traceback_str: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        module: str = "unknown",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        capture_traceback: bool = True,
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """예외 객체에서 ErrorEvent 생성.

        Args:
            exc: 예외 객체
            module: 발생 모듈
            severity: 심각도
            capture_traceback: 스택 트레이스 캡처 여부
            context: 추가 컨텍스트

        Returns:
            ErrorEvent 인스턴스
        """
        tb_str: str | None = None
        if capture_traceback:
            tb_str = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )

        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            module=module,
            severity=severity,
            timestamp=time.monotonic(),
            wall_time=time.time(),
            traceback_str=tb_str,
            context=context or {},
        )

    def __repr__(self) -> str:
        return (
            f"ErrorEvent("
            f"[{self.severity.value}] {self.error_type}: "
            f"{self.message[:50]})"
        )


# =============================================================================
# 에러 집계 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ErrorSummary:
    """에러 집계 요약.

    Attributes:
        total_count: 총 에러 수
        rate_per_minute: 분당 에러율
        rate_per_hour: 시간당 에러율
        by_type: 에러 타입별 건수
        by_module: 모듈별 건수
        by_severity: 심각도별 건수
        patterns: 감지된 반복 패턴 목록
    """

    total_count: int
    rate_per_minute: float
    rate_per_hour: float
    by_type: dict[str, int]
    by_module: dict[str, int]
    by_severity: dict[str, int]
    patterns: list[str]

    def __repr__(self) -> str:
        return (
            f"ErrorSummary("
            f"total={self.total_count}, "
            f"rate/min={self.rate_per_minute:.1f}, "
            f"patterns={len(self.patterns)})"
        )


# =============================================================================
# 핵심 클래스: ErrorTracker
# =============================================================================

class ErrorTracker:
    """에러 추적/집계 엔진.

    에러 이벤트를 링 버퍼에 기록하고, 에러율 계산과
    반복 패턴 감지를 제공한다.

    스레드 안전:
        모든 기록/조회 메서드는 RLock 보호.

    사용 예시::

        tracker = ErrorTracker.get_instance()

        # 에러 기록
        try:
            risky_operation()
        except Exception as exc:
            tracker.record(exc, module="detection.ball")

        # 집계 조회
        summary = tracker.get_summary()
        print(f"분당 에러율: {summary.rate_per_minute}")
    """

    _instance: ClassVar[ErrorTracker | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, *, max_history: int = MAX_ERROR_HISTORY) -> None:
        """ErrorTracker 초기화.

        Args:
            max_history: 에러 이력 최대 보관 수
        """
        self._lock = threading.RLock()
        self._max_history = max_history

        # 에러 이력 (deque = 링 버퍼)
        self._history: collections.deque[ErrorEvent] = collections.deque(
            maxlen=max_history,
        )

        # 카테고리별 집계 (타입, 모듈, 심각도)
        self._count_by_type: dict[str, int] = {}
        self._count_by_module: dict[str, int] = {}
        self._count_by_severity: dict[str, int] = {}

        # 총 에러 수 (이력 용량 초과해도 유지)
        self._total_count: int = 0

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> ErrorTracker:
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
    # 에러 기록
    # =========================================================================

    def record(
        self,
        error: Exception | ErrorEvent,
        *,
        module: str = "unknown",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        capture_traceback: bool = True,
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """에러 기록.

        Args:
            error: 예외 객체 또는 ErrorEvent
            module: 발생 모듈 (Exception일 때만 사용)
            severity: 심각도 (Exception일 때만 사용)
            capture_traceback: 스택 트레이스 캡처 여부
            context: 추가 컨텍스트

        Returns:
            기록된 ErrorEvent
        """
        if isinstance(error, ErrorEvent):
            event = error
        else:
            event = ErrorEvent.from_exception(
                error,
                module=module,
                severity=severity,
                capture_traceback=capture_traceback,
                context=context,
            )

        with self._lock:
            self._history.append(event)
            self._total_count += 1

            # 카테고리별 집계 (무한 성장 방지)
            if len(self._count_by_type) < MAX_CATEGORY_KEYS:
                self._count_by_type[event.error_type] = (
                    self._count_by_type.get(event.error_type, 0) + 1
                )

            if len(self._count_by_module) < MAX_CATEGORY_KEYS:
                self._count_by_module[event.module] = (
                    self._count_by_module.get(event.module, 0) + 1
                )

            sev_key = event.severity.value
            self._count_by_severity[sev_key] = (
                self._count_by_severity.get(sev_key, 0) + 1
            )

        return event

    # =========================================================================
    # 에러율 계산
    # =========================================================================

    def get_rate(self, window_seconds: float = RATE_WINDOW_1MIN) -> float:
        """지정된 시간 창 내 에러율 (건/분) 계산.

        Args:
            window_seconds: 시간 창 (초)

        Returns:
            분당 에러율
        """
        with self._lock:
            now = time.monotonic()
            cutoff = now - window_seconds
            count = sum(1 for e in self._history if e.timestamp >= cutoff)

            if window_seconds <= 0:
                return 0.0

            # 분당 환산
            minutes = window_seconds / 60.0
            return count / minutes

    # =========================================================================
    # 패턴 감지
    # =========================================================================

    def detect_patterns(
        self,
        *,
        threshold: int = PATTERN_THRESHOLD,
        window_seconds: float = PATTERN_WINDOW,
    ) -> list[str]:
        """반복 에러 패턴 감지.

        지정된 시간 창 내에서 같은 에러 타입이
        threshold 이상 발생하면 패턴으로 감지.

        Args:
            threshold: 반복 임계값
            window_seconds: 시간 창 (초)

        Returns:
            패턴 감지된 에러 타입 목록
        """
        with self._lock:
            now = time.monotonic()
            cutoff = now - window_seconds

            recent_counts: dict[str, int] = {}
            for event in self._history:
                if event.timestamp >= cutoff:
                    key = f"{event.module}:{event.error_type}"
                    recent_counts[key] = recent_counts.get(key, 0) + 1

            return [
                key for key, count in recent_counts.items()
                if count >= threshold
            ]

    # =========================================================================
    # 집계 조회
    # =========================================================================

    def get_summary(self) -> ErrorSummary:
        """에러 집계 요약 생성.

        Returns:
            ErrorSummary
        """
        with self._lock:
            return ErrorSummary(
                total_count=self._total_count,
                rate_per_minute=self.get_rate(RATE_WINDOW_1MIN),
                rate_per_hour=self.get_rate(RATE_WINDOW_1HOUR),
                by_type=dict(self._count_by_type),
                by_module=dict(self._count_by_module),
                by_severity=dict(self._count_by_severity),
                patterns=self.detect_patterns(),
            )

    def get_recent(self, count: int = 10) -> list[ErrorEvent]:
        """최근 에러 이벤트 조회.

        Args:
            count: 조회할 이벤트 수

        Returns:
            최근 에러 이벤트 목록 (최신순)
        """
        with self._lock:
            items = list(self._history)
            return items[-count:][::-1]

    def get_by_module(self, module: str) -> list[ErrorEvent]:
        """특정 모듈의 에러 이벤트 조회.

        Args:
            module: 모듈 이름

        Returns:
            해당 모듈 에러 목록
        """
        with self._lock:
            return [e for e in self._history if e.module == module]

    def get_by_severity(self, severity: ErrorSeverity) -> list[ErrorEvent]:
        """특정 심각도의 에러 이벤트 조회.

        Args:
            severity: 심각도

        Returns:
            해당 심각도 에러 목록
        """
        with self._lock:
            return [e for e in self._history if e.severity == severity]

    # =========================================================================
    # 관리
    # =========================================================================

    def clear(self) -> int:
        """에러 이력 초기화.

        Returns:
            초기화된 이벤트 수
        """
        with self._lock:
            count = len(self._history)
            self._history.clear()
            self._count_by_type.clear()
            self._count_by_module.clear()
            self._count_by_severity.clear()
            self._total_count = 0
            return count

    @property
    def total_count(self) -> int:
        """누적 에러 수."""
        return self._total_count

    @property
    def history_size(self) -> int:
        """현재 이력 크기."""
        with self._lock:
            return len(self._history)

    @property
    def max_history(self) -> int:
        """이력 최대 크기."""
        return self._max_history

    def __repr__(self) -> str:
        return (
            f"ErrorTracker("
            f"total={self._total_count}, "
            f"history={self.history_size}/{self._max_history})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ErrorSeverity",
    # 데이터 클래스
    "ErrorEvent",
    "ErrorSummary",
    # 핵심 클래스
    "ErrorTracker",
    # 상수
    "MAX_ERROR_HISTORY",
    "RATE_WINDOW_1MIN",
    "RATE_WINDOW_1HOUR",
    "PATTERN_THRESHOLD",
    "PATTERN_WINDOW",
    "MAX_CATEGORY_KEYS",
]

__version__ = "1.0.0"
