# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
파일: circuit_breaker.py
설명: 서킷 브레이커 패턴 구현 - 장애 전파 방지, 폴백 처리, 자동 복구

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 서킷 브레이커 상태 머신 (CLOSED, OPEN, HALF_OPEN)
    - 실패 임계값 기반 서킷 전환
    - 슬라이딩 윈도우 기반 실패율 추적
    - 자동 복구 (half-open 상태)
    - 폴백 전략 지원
    - 이벤트 콜백 (상태 변경 알림)
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 메모리 효율: 슬라이딩 윈도우
    - 확장성: 커스텀 폴백 및 콜백 지원

사용 예시:
    # 기본 사용
    circuit = CircuitBreaker(
        name="database",
        config=CircuitBreakerConfig(failure_threshold=5),
    )

    @circuit_protected("database")
    def call_database():
        return db.query("SELECT * FROM users")

    # 폴백 사용
    @circuit_protected("api", fallback=lambda: {"cached": True})
    def call_external_api():
        return api.get("/data")
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import asyncio
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Generator,
    TypeVar,
)

# ============================================================
# shared 임포트
# ============================================================
from shared.exceptions.infrastructure_exceptions import CircuitBreakerOpenException

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import Timer

# ============================================================
# core_foundation 내부 임포트 (Direct Import)
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.error_tracker import ErrorTracker
    from core_foundation.monitoring.metrics import MetricsCollector


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 타입 변수
# ============================================================
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# ============================================================
# 상수 정의
# ============================================================
# 기본 서킷 브레이커 설정
DEFAULT_FAILURE_THRESHOLD: int = 5
DEFAULT_SUCCESS_THRESHOLD: int = 3
DEFAULT_OPEN_TIMEOUT: float = 30.0
DEFAULT_HALF_OPEN_MAX_REQUESTS: int = 3
DEFAULT_WINDOW_SIZE: float = 60.0
DEFAULT_MINIMUM_REQUESTS: int = 10

# 이벤트 타입
EVENT_ON_OPEN: str = "on_open"
EVENT_ON_CLOSE: str = "on_close"
EVENT_ON_HALF_OPEN: str = "on_half_open"
EVENT_ON_SUCCESS: str = "on_success"
EVENT_ON_FAILURE: str = "on_failure"

# YAML 설정 키
CONFIG_KEY_CIRCUIT_BREAKER: str = "circuit_breaker"
CONFIG_KEY_ENABLED: str = "enabled"
CONFIG_KEY_DEFAULTS: str = "defaults"
CONFIG_KEY_SERVICES: str = "services"


# ============================================================
# Enum 정의
# ============================================================
class CircuitState(str, Enum):
    """
    서킷 브레이커 상태.

    서킷 브레이커의 상태 머신 상태를 정의합니다.

    Attributes:
        CLOSED: 닫힘 - 정상 동작, 모든 요청 통과
        OPEN: 열림 - 장애 상태, 모든 요청 차단
        HALF_OPEN: 반열림 - 복구 테스트 중, 제한된 요청 허용
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    @property
    def is_allowing_requests(self) -> bool:
        """요청 허용 여부."""
        return self != CircuitState.OPEN

    @property
    def korean_label(self) -> str:
        """한글 라벨."""
        labels = {
            CircuitState.CLOSED: "닫힘",
            CircuitState.OPEN: "열림",
            CircuitState.HALF_OPEN: "반열림",
        }
        return labels.get(self, "알 수 없음")


class FailureType(str, Enum):
    """
    실패 유형.

    서킷 브레이커가 추적하는 실패 유형을 정의합니다.
    """

    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    ERROR_RESPONSE = "error_response"
    REJECTION = "rejection"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class CircuitBreakerConfig:
    """
    서킷 브레이커 설정.

    서킷 브레이커의 동작 파라미터를 정의합니다.

    Attributes:
        failure_threshold: 실패 임계값 (OPEN 전환 조건)
        success_threshold: 성공 임계값 (HALF_OPEN에서 CLOSED 전환)
        open_timeout: OPEN 상태 유지 시간 (초)
        half_open_max_requests: HALF_OPEN에서 허용되는 최대 요청 수
        window_size: 슬라이딩 윈도우 크기 (초)
        minimum_requests: 통계 계산에 필요한 최소 요청 수
        timeout: 요청 타임아웃 (초)
        excluded_exceptions: 실패로 카운트하지 않을 예외 타입
        include_exceptions: 실패로 카운트할 예외 타입 (None이면 모든 예외)
        critical: 중요 서비스 여부 (알림 우선순위)
    """

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    success_threshold: int = DEFAULT_SUCCESS_THRESHOLD
    open_timeout: float = DEFAULT_OPEN_TIMEOUT
    half_open_max_requests: int = DEFAULT_HALF_OPEN_MAX_REQUESTS
    window_size: float = DEFAULT_WINDOW_SIZE
    minimum_requests: int = DEFAULT_MINIMUM_REQUESTS
    timeout: float | None = None
    excluded_exceptions: set[type[Exception]] = field(default_factory=set)
    include_exceptions: set[type[Exception]] | None = None
    critical: bool = False

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold는 1 이상이어야 합니다")
        if self.success_threshold < 1:
            raise ValueError("success_threshold는 1 이상이어야 합니다")
        if self.open_timeout <= 0:
            raise ValueError("open_timeout은 0보다 커야 합니다")
        if self.half_open_max_requests < 1:
            raise ValueError("half_open_max_requests는 1 이상이어야 합니다")
        if self.window_size <= 0:
            raise ValueError("window_size는 0보다 커야 합니다")

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "open_timeout": self.open_timeout,
            "half_open_max_requests": self.half_open_max_requests,
            "window_size": self.window_size,
            "minimum_requests": self.minimum_requests,
            "timeout": self.timeout,
            "critical": self.critical,
        }


@dataclass
class CircuitBreakerStats:
    """
    서킷 브레이커 통계.

    서킷 브레이커의 현재 상태 및 통계를 저장합니다.

    Attributes:
        state: 현재 서킷 상태
        failure_count: 현재 윈도우 내 실패 횟수
        success_count: 현재 윈도우 내 성공 횟수
        total_requests: 전체 요청 횟수
        total_failures: 전체 실패 횟수
        total_successes: 전체 성공 횟수
        total_rejections: 서킷 OPEN으로 인한 거부 횟수
        consecutive_failures: 연속 실패 횟수
        consecutive_successes: 연속 성공 횟수 (HALF_OPEN에서)
        last_failure_time: 마지막 실패 시간
        last_success_time: 마지막 성공 시간
        last_state_change_time: 마지막 상태 변경 시간
        state_change_count: 상태 변경 횟수
        open_count: OPEN 상태 전환 횟수
    """

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    last_state_change_time: datetime | None = None
    state_change_count: int = 0
    open_count: int = 0

    @property
    def failure_rate(self) -> float:
        """실패율 (0~1)."""
        total = self.failure_count + self.success_count
        if total == 0:
            return 0.0
        return self.failure_count / total

    @property
    def success_rate(self) -> float:
        """성공률 (0~1)."""
        return 1.0 - self.failure_rate

    @property
    def total_failure_rate(self) -> float:
        """전체 실패율 (0~1)."""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests

    @property
    def is_healthy(self) -> bool:
        """정상 상태 여부."""
        return self.state == CircuitState.CLOSED

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "state": self.state.value,
            "state_label": self.state.korean_label,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": round(self.failure_rate, 4),
            "success_rate": round(self.success_rate, 4),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejections": self.total_rejections,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "last_state_change_time": (
                self.last_state_change_time.isoformat()
                if self.last_state_change_time
                else None
            ),
            "state_change_count": self.state_change_count,
            "open_count": self.open_count,
            "is_healthy": self.is_healthy,
        }


@dataclass
class RequestRecord:
    """
    요청 기록.

    슬라이딩 윈도우에서 사용하는 개별 요청 기록입니다.
    """

    timestamp: float  # time.monotonic()
    success: bool
    duration_ms: float = 0.0
    failure_type: FailureType | None = None


@dataclass
class StateChangeEvent:
    """
    상태 변경 이벤트.

    서킷 브레이커 상태 변경 시 발생하는 이벤트입니다.
    """

    circuit_name: str
    previous_state: CircuitState
    current_state: CircuitState
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None
    stats: CircuitBreakerStats | None = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "circuit_name": self.circuit_name,
            "previous_state": self.previous_state.value,
            "current_state": self.current_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "stats": self.stats.to_dict() if self.stats else None,
        }


# ============================================================
# 콜백 타입 정의
# ============================================================
StateChangeCallback = Callable[[StateChangeEvent], None]
FallbackHandler = Callable[..., Any]
AsyncFallbackHandler = Callable[..., Coroutine[Any, Any, Any]]


# ============================================================
# 메인 클래스: CircuitBreaker
# ============================================================
class CircuitBreaker:
    """
    서킷 브레이커.

    장애 전파를 방지하기 위한 서킷 브레이커 패턴 구현입니다.
    CLOSED, OPEN, HALF_OPEN 세 가지 상태로 동작하며,
    실패 임계값 초과 시 서킷을 열어 요청을 차단합니다.

    Args:
        name: 서킷 브레이커 이름
        config: 서킷 브레이커 설정
        config_loader: 설정 로더 (Direct Import)
        metrics_collector: 메트릭 수집기 (DI 주입, Optional)
        error_tracker: 에러 추적기 (DI 주입, Optional)
        fallback: 폴백 핸들러
        on_state_change: 상태 변경 콜백

    Example:
        >>> circuit = CircuitBreaker(
        ...     name="external_api",
        ...     config=CircuitBreakerConfig(failure_threshold=5),
        ... )
        >>>
        >>> with circuit:
        ...     result = call_external_service()
        >>>
        >>> # 또는 데코레이터 사용
        >>> @circuit
        ... def call_service():
        ...     return api.get_data()
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        config_loader: ConfigLoader | None = None,
        metrics_collector: MetricsCollector | None = None,
        error_tracker: ErrorTracker | None = None,
        fallback: FallbackHandler | None = None,
        on_state_change: StateChangeCallback | None = None,
    ) -> None:
        """초기화."""
        self._name = name
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._metrics_collector = metrics_collector
        self._error_tracker = error_tracker
        self._fallback = fallback
        self._on_state_change = on_state_change

        # 설정 로드
        self._config = config or self._load_config_from_yaml()

        # 상태
        self._state = CircuitState.CLOSED
        self._last_state_change_time = time.monotonic()
        self._open_start_time: float | None = None

        # 슬라이딩 윈도우 (요청 기록)
        self._request_window: deque[RequestRecord] = deque()

        # 통계
        self._stats = CircuitBreakerStats()

        # HALF_OPEN 상태 추적
        self._half_open_requests = 0
        self._half_open_successes = 0

        # 콜백
        self._state_change_callbacks: list[StateChangeCallback] = []
        if on_state_change:
            self._state_change_callbacks.append(on_state_change)

        # 스레드 안전성
        self._lock = threading.RLock()

        # 메트릭 설정
        self._setup_metrics()

        logger.info(
            f"CircuitBreaker '{name}' 초기화: "
            f"failure_threshold={self._config.failure_threshold}, "
            f"open_timeout={self._config.open_timeout}s"
        )

    def _load_config_from_yaml(self) -> CircuitBreakerConfig:
        """YAML에서 설정 로드."""
        try:
            cb_config = self._config_loader.get(
                f"resilience.{CONFIG_KEY_CIRCUIT_BREAKER}",
                default={},
            )

            # 서비스별 설정 확인
            services_config = cb_config.get(CONFIG_KEY_SERVICES, {})
            service_config = services_config.get(self._name, {})

            # 기본값과 병합
            defaults = cb_config.get(CONFIG_KEY_DEFAULTS, {})

            return CircuitBreakerConfig(
                failure_threshold=service_config.get(
                    "failure_threshold",
                    defaults.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD),
                ),
                success_threshold=service_config.get(
                    "success_threshold",
                    defaults.get("success_threshold", DEFAULT_SUCCESS_THRESHOLD),
                ),
                open_timeout=service_config.get(
                    "open_timeout",
                    defaults.get("open_timeout", DEFAULT_OPEN_TIMEOUT),
                ),
                half_open_max_requests=service_config.get(
                    "half_open_max_requests",
                    defaults.get("half_open_max_requests", DEFAULT_HALF_OPEN_MAX_REQUESTS),
                ),
                window_size=service_config.get(
                    "window_size",
                    defaults.get("window_size", DEFAULT_WINDOW_SIZE),
                ),
                minimum_requests=service_config.get(
                    "minimum_requests",
                    defaults.get("minimum_requests", DEFAULT_MINIMUM_REQUESTS),
                ),
                critical=service_config.get("critical", False),
            )

        except Exception as e:
            logger.warning(f"설정 로드 실패, 기본값 사용: {e}")
            return CircuitBreakerConfig()

    def _setup_metrics(self) -> None:
        """메트릭 설정."""
        if self._metrics_collector is None:
            return

        # 카운터
        self._request_counter = self._metrics_collector.counter(
            "circuit_breaker_requests_total",
            f"Total requests for circuit breaker {self._name}",
        )
        self._failure_counter = self._metrics_collector.counter(
            "circuit_breaker_failures_total",
            f"Total failures for circuit breaker {self._name}",
        )
        self._rejection_counter = self._metrics_collector.counter(
            "circuit_breaker_rejections_total",
            f"Total rejections for circuit breaker {self._name}",
        )
        self._state_change_counter = self._metrics_collector.counter(
            "circuit_breaker_state_changes_total",
            f"State changes for circuit breaker {self._name}",
        )

        # 게이지
        self._state_gauge = self._metrics_collector.gauge(
            "circuit_breaker_state",
            f"Current state of circuit breaker {self._name}",
        )
        self._failure_rate_gauge = self._metrics_collector.gauge(
            "circuit_breaker_failure_rate",
            f"Failure rate for circuit breaker {self._name}",
        )

    # ============================================================
    # 속성
    # ============================================================
    @property
    def name(self) -> str:
        """서킷 브레이커 이름."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """현재 서킷 상태."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def config(self) -> CircuitBreakerConfig:
        """서킷 브레이커 설정."""
        return self._config

    @property
    def stats(self) -> CircuitBreakerStats:
        """서킷 브레이커 통계."""
        with self._lock:
            self._cleanup_window()
            self._stats.state = self._state
            self._stats.failure_count = sum(
                1 for r in self._request_window if not r.success
            )
            self._stats.success_count = sum(
                1 for r in self._request_window if r.success
            )
            return self._stats

    @property
    def is_closed(self) -> bool:
        """CLOSED 상태 여부."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """OPEN 상태 여부."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """HALF_OPEN 상태 여부."""
        return self.state == CircuitState.HALF_OPEN

    # ============================================================
    # 상태 전환
    # ============================================================
    def _check_state_transition(self) -> None:
        """상태 전환 확인 및 처리."""
        if self._state == CircuitState.OPEN:
            # OPEN -> HALF_OPEN 전환 확인
            if self._open_start_time is not None:
                elapsed = time.monotonic() - self._open_start_time
                if elapsed >= self._config.open_timeout:
                    self._transition_to_half_open()

    def _transition_to_open(self, reason: str = "실패 임계값 초과") -> None:
        """OPEN 상태로 전환."""
        if self._state == CircuitState.OPEN:
            return

        previous_state = self._state
        self._state = CircuitState.OPEN
        self._open_start_time = time.monotonic()
        self._last_state_change_time = time.monotonic()
        self._stats.state_change_count += 1
        self._stats.open_count += 1
        self._stats.last_state_change_time = datetime.now(timezone.utc)

        logger.warning(
            f"CircuitBreaker '{self._name}' OPEN: {reason} "
            f"(failures={self._stats.consecutive_failures})"
        )

        self._fire_state_change_event(previous_state, CircuitState.OPEN, reason)
        self._update_metrics_state(CircuitState.OPEN)

    def _transition_to_half_open(self, reason: str = "타임아웃 만료") -> None:
        """HALF_OPEN 상태로 전환."""
        if self._state == CircuitState.HALF_OPEN:
            return

        previous_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._half_open_requests = 0
        self._half_open_successes = 0
        self._last_state_change_time = time.monotonic()
        self._stats.state_change_count += 1
        self._stats.last_state_change_time = datetime.now(timezone.utc)

        logger.info(f"CircuitBreaker '{self._name}' HALF_OPEN: {reason}")

        self._fire_state_change_event(previous_state, CircuitState.HALF_OPEN, reason)
        self._update_metrics_state(CircuitState.HALF_OPEN)

    def _transition_to_closed(self, reason: str = "복구 성공") -> None:
        """CLOSED 상태로 전환."""
        if self._state == CircuitState.CLOSED:
            return

        previous_state = self._state
        self._state = CircuitState.CLOSED
        self._open_start_time = None
        self._last_state_change_time = time.monotonic()
        self._stats.state_change_count += 1
        self._stats.last_state_change_time = datetime.now(timezone.utc)

        # 윈도우 초기화
        self._request_window.clear()
        self._stats.consecutive_failures = 0

        logger.info(f"CircuitBreaker '{self._name}' CLOSED: {reason}")

        self._fire_state_change_event(previous_state, CircuitState.CLOSED, reason)
        self._update_metrics_state(CircuitState.CLOSED)

    def _fire_state_change_event(
        self,
        previous_state: CircuitState,
        current_state: CircuitState,
        reason: str,
    ) -> None:
        """상태 변경 이벤트 발생."""
        event = StateChangeEvent(
            circuit_name=self._name,
            previous_state=previous_state,
            current_state=current_state,
            reason=reason,
            stats=CircuitBreakerStats(
                state=current_state,
                failure_count=self._stats.failure_count,
                success_count=self._stats.success_count,
                consecutive_failures=self._stats.consecutive_failures,
                open_count=self._stats.open_count,
            ),
        )

        for callback in self._state_change_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"상태 변경 콜백 실행 실패: {e}")

        # 메트릭 카운터 업데이트
        if self._metrics_collector:
            self._state_change_counter.inc(
                1,
                {
                    "circuit": self._name,
                    "from": previous_state.value,
                    "to": current_state.value,
                },
            )

    def _update_metrics_state(self, state: CircuitState) -> None:
        """메트릭 상태 업데이트."""
        if self._metrics_collector:
            state_value = {"closed": 0, "half_open": 1, "open": 2}.get(state.value, -1)
            self._state_gauge.set(state_value, {"circuit": self._name})

    # ============================================================
    # 슬라이딩 윈도우 관리
    # ============================================================
    def _cleanup_window(self) -> None:
        """윈도우에서 만료된 기록 제거."""
        current_time = time.monotonic()
        cutoff = current_time - self._config.window_size

        while self._request_window and self._request_window[0].timestamp < cutoff:
            self._request_window.popleft()

    def _record_request(
        self,
        success: bool,
        duration_ms: float = 0.0,
        failure_type: FailureType | None = None,
    ) -> None:
        """요청 기록."""
        record = RequestRecord(
            timestamp=time.monotonic(),
            success=success,
            duration_ms=duration_ms,
            failure_type=failure_type,
        )

        self._request_window.append(record)
        self._stats.total_requests += 1

        if success:
            self._stats.total_successes += 1
            self._stats.last_success_time = datetime.now(timezone.utc)
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes += 1
        else:
            self._stats.total_failures += 1
            self._stats.last_failure_time = datetime.now(timezone.utc)
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0

        # 메트릭 업데이트
        if self._metrics_collector:
            self._request_counter.inc(
                1,
                {"circuit": self._name, "success": str(success).lower()},
            )
            if not success:
                self._failure_counter.inc(1, {"circuit": self._name})

            # 실패율 업데이트
            self._cleanup_window()
            total = len(self._request_window)
            if total > 0:
                failures = sum(1 for r in self._request_window if not r.success)
                self._failure_rate_gauge.set(
                    failures / total,
                    {"circuit": self._name},
                )

    # ============================================================
    # 요청 실행
    # ============================================================
    def allow_request(self) -> bool:
        """
        요청 허용 여부 확인.

        Returns:
            True면 요청 허용, False면 차단
        """
        with self._lock:
            self._check_state_transition()
            self._cleanup_window()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                return False

            # HALF_OPEN: 제한된 수의 요청 허용
            if self._half_open_requests < self._config.half_open_max_requests:
                self._half_open_requests += 1
                return True

            return False

    def record_success(self, duration_ms: float = 0.0) -> None:
        """
        성공 기록.

        Args:
            duration_ms: 요청 소요 시간 (밀리초)
        """
        with self._lock:
            self._record_request(success=True, duration_ms=duration_ms)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._config.success_threshold:
                    self._transition_to_closed("HALF_OPEN에서 충분한 성공")

    def record_failure(
        self,
        exception: Exception | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        """
        실패 기록.

        Args:
            exception: 발생한 예외
            duration_ms: 요청 소요 시간 (밀리초)
        """
        with self._lock:
            # 제외할 예외 체크
            if exception and self._config.excluded_exceptions:
                if type(exception) in self._config.excluded_exceptions:
                    self._record_request(success=True, duration_ms=duration_ms)
                    return

            # 포함할 예외 체크
            if exception and self._config.include_exceptions:
                if type(exception) not in self._config.include_exceptions:
                    self._record_request(success=True, duration_ms=duration_ms)
                    return

            # 실패 유형 결정
            failure_type = FailureType.EXCEPTION
            if exception:
                if isinstance(exception, TimeoutError):
                    failure_type = FailureType.TIMEOUT

            self._record_request(
                success=False,
                duration_ms=duration_ms,
                failure_type=failure_type,
            )

            # 에러 추적
            if self._error_tracker and exception:
                from core_foundation.monitoring.error_tracker import ErrorSeverity

                self._error_tracker.track(
                    error=exception,
                    severity=ErrorSeverity.WARNING,
                    context={"circuit_name": self._name, "state": self._state.value},
                )

            # 상태 전환 확인
            if self._state == CircuitState.HALF_OPEN:
                # HALF_OPEN에서 실패 시 즉시 OPEN
                self._transition_to_open("HALF_OPEN에서 실패 발생")
            elif self._state == CircuitState.CLOSED:
                # 실패 임계값 확인
                self._cleanup_window()
                total = len(self._request_window)
                failures = sum(1 for r in self._request_window if not r.success)

                if (
                    total >= self._config.minimum_requests
                    and failures >= self._config.failure_threshold
                ):
                    self._transition_to_open(
                        f"실패 임계값 초과 ({failures}/{total})"
                    )

    def record_rejection(self) -> None:
        """거부 기록 (서킷 OPEN으로 인한)."""
        with self._lock:
            self._stats.total_rejections += 1

            if self._metrics_collector:
                self._rejection_counter.inc(1, {"circuit": self._name})

    # ============================================================
    # 실행 래퍼
    # ============================================================
    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback: FallbackHandler | None = None,
        **kwargs: Any,
    ) -> T:
        """
        함수 실행 (서킷 브레이커 보호).

        Args:
            func: 실행할 함수
            *args: 함수 인수
            fallback: 폴백 핸들러 (없으면 인스턴스 기본값 사용)
            **kwargs: 함수 키워드 인수

        Returns:
            함수 반환값 또는 폴백 결과

        Raises:
            CircuitBreakerOpenException: 서킷이 열린 상태일 때
        """
        effective_fallback = fallback or self._fallback

        if not self.allow_request():
            self.record_rejection()

            if effective_fallback:
                logger.debug(f"CircuitBreaker '{self._name}': 폴백 실행")
                return effective_fallback(*args, **kwargs)

            raise CircuitBreakerOpenException(
                circuit_name=self._name,
                reset_timeout_seconds=self._config.open_timeout,
                failure_count=self._stats.consecutive_failures,
            )

        timer = Timer()
        try:
            timer.start()
            result = func(*args, **kwargs)
            timer_result = timer.stop()
            self.record_success(duration_ms=timer_result.elapsed_ms)
            return result

        except Exception as e:
            # 타이머가 시작된 경우에만 정지
            if timer._running:
                timer_result = timer.stop()
                duration_ms = timer_result.elapsed_ms
            else:
                duration_ms = 0.0
            self.record_failure(exception=e, duration_ms=duration_ms)
            raise

    async def execute_async(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        fallback: AsyncFallbackHandler | None = None,
        **kwargs: Any,
    ) -> T:
        """
        비동기 함수 실행 (서킷 브레이커 보호).

        Args:
            func: 실행할 비동기 함수
            *args: 함수 인수
            fallback: 비동기 폴백 핸들러
            **kwargs: 함수 키워드 인수

        Returns:
            함수 반환값 또는 폴백 결과

        Raises:
            CircuitBreakerOpenException: 서킷이 열린 상태일 때
        """
        if not self.allow_request():
            self.record_rejection()

            if fallback:
                logger.debug(f"CircuitBreaker '{self._name}': 비동기 폴백 실행")
                return await fallback(*args, **kwargs)

            raise CircuitBreakerOpenException(
                circuit_name=self._name,
                reset_timeout_seconds=self._config.open_timeout,
                failure_count=self._stats.consecutive_failures,
            )

        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.record_success(duration_ms=elapsed_ms)
            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.record_failure(exception=e, duration_ms=elapsed_ms)
            raise

    # ============================================================
    # 컨텍스트 매니저
    # ============================================================
    @contextmanager
    def __call__(self) -> Generator[CircuitBreaker, None, None]:
        """컨텍스트 매니저로 사용."""
        if not self.allow_request():
            self.record_rejection()
            raise CircuitBreakerOpenException(
                circuit_name=self._name,
                reset_timeout_seconds=self._config.open_timeout,
                failure_count=self._stats.consecutive_failures,
            )

        start_time = time.perf_counter()
        try:
            yield self
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.record_success(duration_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.record_failure(exception=e, duration_ms=elapsed_ms)
            raise

    def __enter__(self) -> "CircuitBreaker":
        """컨텍스트 진입."""
        if not self.allow_request():
            self.record_rejection()
            raise CircuitBreakerOpenException(
                circuit_name=self._name,
                reset_timeout_seconds=self._config.open_timeout,
                failure_count=self._stats.consecutive_failures,
            )
        self._context_start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """컨텍스트 종료."""
        elapsed_ms = (time.perf_counter() - self._context_start_time) * 1000

        if exc_type is None:
            self.record_success(duration_ms=elapsed_ms)
        else:
            if isinstance(exc_val, Exception):
                self.record_failure(exception=exc_val, duration_ms=elapsed_ms)

        return False  # 예외 전파

    # ============================================================
    # 관리 메서드
    # ============================================================
    def reset(self) -> None:
        """서킷 브레이커 리셋 (CLOSED 상태로 초기화)."""
        with self._lock:
            previous_state = self._state
            self._state = CircuitState.CLOSED
            self._open_start_time = None
            self._request_window.clear()
            self._half_open_requests = 0
            self._half_open_successes = 0
            self._stats = CircuitBreakerStats()
            self._last_state_change_time = time.monotonic()

            logger.info(f"CircuitBreaker '{self._name}' 리셋 (이전 상태: {previous_state.value})")

            self._update_metrics_state(CircuitState.CLOSED)

    def force_open(self, reason: str = "수동 오픈") -> None:
        """서킷을 강제로 OPEN 상태로 전환."""
        with self._lock:
            self._transition_to_open(reason)

    def force_close(self, reason: str = "수동 클로즈") -> None:
        """서킷을 강제로 CLOSED 상태로 전환."""
        with self._lock:
            self._transition_to_closed(reason)

    def add_state_change_callback(self, callback: StateChangeCallback) -> None:
        """상태 변경 콜백 추가."""
        self._state_change_callbacks.append(callback)

    def remove_state_change_callback(self, callback: StateChangeCallback) -> bool:
        """상태 변경 콜백 제거."""
        try:
            self._state_change_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    def get_status(self) -> dict[str, Any]:
        """서킷 브레이커 상태 조회."""
        with self._lock:
            self._check_state_transition()
            self._cleanup_window()

            return {
                "name": self._name,
                "state": self._state.value,
                "state_label": self._state.korean_label,
                "config": self._config.to_dict(),
                "stats": self.stats.to_dict(),
                "is_healthy": self._state == CircuitState.CLOSED,
                "time_in_current_state": time.monotonic() - self._last_state_change_time,
            }


# ============================================================
# 서킷 브레이커 레지스트리 (전역 관리)
# ============================================================
class CircuitBreakerRegistry:
    """
    서킷 브레이커 레지스트리.

    여러 서킷 브레이커를 중앙에서 관리합니다.
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        metrics_collector: MetricsCollector | None = None,
        error_tracker: ErrorTracker | None = None,
    ) -> None:
        """초기화."""
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._metrics_collector = metrics_collector
        self._error_tracker = error_tracker
        self._circuits: dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        fallback: FallbackHandler | None = None,
    ) -> CircuitBreaker:
        """
        서킷 브레이커 조회 또는 생성.

        Args:
            name: 서킷 브레이커 이름
            config: 설정 (없으면 YAML에서 로드)
            fallback: 폴백 핸들러

        Returns:
            CircuitBreaker 인스턴스
        """
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitBreaker(
                    name=name,
                    config=config,
                    config_loader=self._config_loader,
                    metrics_collector=self._metrics_collector,
                    error_tracker=self._error_tracker,
                    fallback=fallback,
                )
            return self._circuits[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """서킷 브레이커 조회."""
        return self._circuits.get(name)

    def list_all(self) -> list[str]:
        """모든 서킷 브레이커 이름 목록."""
        return list(self._circuits.keys())

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """모든 서킷 브레이커 상태 조회."""
        return {name: cb.get_status() for name, cb in self._circuits.items()}

    def reset_all(self) -> None:
        """모든 서킷 브레이커 리셋."""
        for circuit in self._circuits.values():
            circuit.reset()


# ============================================================
# 전역 레지스트리 인스턴스
# ============================================================
_registry: CircuitBreakerRegistry | None = None
_registry_lock = threading.Lock()


def _get_registry() -> CircuitBreakerRegistry:
    """전역 레지스트리 인스턴스 가져오기."""
    global _registry

    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CircuitBreakerRegistry()

    return _registry


def _reset_registry() -> None:
    """전역 레지스트리 리셋 (테스트용)."""
    global _registry

    with _registry_lock:
        _registry = None


# ============================================================
# 데코레이터: circuit_protected
# ============================================================
def circuit_protected(
    name: str,
    config: CircuitBreakerConfig | None = None,
    fallback: FallbackHandler | None = None,
    async_fallback: AsyncFallbackHandler | None = None,
) -> Callable[[F], F]:
    """
    서킷 브레이커 보호 데코레이터.

    함수를 서킷 브레이커로 보호합니다.

    Args:
        name: 서킷 브레이커 이름
        config: 서킷 브레이커 설정 (없으면 YAML에서 로드)
        fallback: 동기 폴백 핸들러
        async_fallback: 비동기 폴백 핸들러

    Returns:
        데코레이터 함수

    Example:
        >>> @circuit_protected("database")
        ... def query_database():
        ...     return db.query("SELECT * FROM users")
        >>>
        >>> @circuit_protected("api", fallback=lambda: {"cached": True})
        ... def call_api():
        ...     return api.get("/data")
        >>>
        >>> @circuit_protected("external")
        ... async def async_call():
        ...     return await client.fetch()
    """

    def decorator(func: F) -> F:
        circuit = _get_registry().get_or_create(
            name=name,
            config=config,
            fallback=fallback,
        )

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await circuit.execute_async(
                    func,
                    *args,
                    fallback=async_fallback,
                    **kwargs,
                )

            return async_wrapper  # type: ignore
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return circuit.execute(func, *args, fallback=fallback, **kwargs)

            return sync_wrapper  # type: ignore

    return decorator


# ============================================================
# 헬퍼 함수
# ============================================================
def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """
    서킷 브레이커 가져오기.

    전역 레지스트리에서 서킷 브레이커를 조회하거나 생성합니다.

    Args:
        name: 서킷 브레이커 이름
        config: 설정 (없으면 YAML에서 로드)

    Returns:
        CircuitBreaker 인스턴스

    Example:
        >>> circuit = get_circuit_breaker("database")
        >>> with circuit:
        ...     result = db.query("SELECT 1")
    """
    return _get_registry().get_or_create(name, config)


def get_all_circuit_status() -> dict[str, dict[str, Any]]:
    """
    모든 서킷 브레이커 상태 조회.

    Returns:
        서킷 이름별 상태 딕셔너리

    Example:
        >>> status = get_all_circuit_status()
        >>> for name, info in status.items():
        ...     print(f"{name}: {info['state']}")
    """
    return _get_registry().get_all_status()


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "CircuitState",
    "FailureType",
    # 상수
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_SUCCESS_THRESHOLD",
    "DEFAULT_OPEN_TIMEOUT",
    "DEFAULT_HALF_OPEN_MAX_REQUESTS",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_MINIMUM_REQUESTS",
    # 데이터 클래스
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "RequestRecord",
    "StateChangeEvent",
    # 메인 클래스
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    # 데코레이터
    "circuit_protected",
    # 함수
    "get_circuit_breaker",
    "get_all_circuit_status",
    # 유틸리티 (테스트용)
    "_get_registry",
    "_reset_registry",
]

__version__ = "1.0.0"