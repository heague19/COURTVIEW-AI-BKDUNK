# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
파일: circuit_breaker.py
설명: 서킷 브레이커 패턴 구현
      - 3-State 상태머신 (CLOSED → OPEN → HALF_OPEN)
      - 실패율 기반 트립 (슬라이딩 윈도우)
      - 반열림 상태에서 시험 호출 허용
      - 상태 변경 콜백
      - 수동 트립/리셋
      - 스레드 안전 (RLock)

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
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 실패 임계치 (연속 실패 수)
DEFAULT_FAILURE_THRESHOLD: Final[int] = 5

# 기본 복구 대기 시간 (초)
DEFAULT_RECOVERY_TIMEOUT_SEC: Final[float] = 30.0

# 반열림 상태에서 허용할 시험 호출 수
DEFAULT_HALF_OPEN_MAX_CALLS: Final[int] = 3

# 슬라이딩 윈도우 크기 (최근 N개 호출 기준)
DEFAULT_WINDOW_SIZE: Final[int] = 20

# 실패율 임계치 (0.0 ~ 1.0)
DEFAULT_FAILURE_RATE_THRESHOLD: Final[float] = 0.5

# 최대 등록 가능한 브레이커 수
MAX_BREAKERS: Final[int] = 100

# 최대 콜백 수 (브레이커당)
MAX_CALLBACKS_PER_BREAKER: Final[int] = 20

# 최대 상태 이력 수
MAX_STATE_HISTORY: Final[int] = 50


# =============================================================================
# 상태 Enum
# =============================================================================

@unique
class CircuitState(Enum):
    """서킷 브레이커 상태.

    Members:
        CLOSED: 정상 — 요청 허용, 실패 카운트 중
        OPEN: 차단 — 요청 거부, 복구 대기
        HALF_OPEN: 시험 — 제한된 요청 허용, 성공 시 CLOSED 복귀
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP = {
            CircuitState.CLOSED: "닫힘 (정상)",
            CircuitState.OPEN: "열림 (차단)",
            CircuitState.HALF_OPEN: "반열림 (시험)",
        }
        return _MAP[self]

    @property
    def is_allowing_requests(self) -> bool:
        """요청 허용 상태인지."""
        return self in _ALLOWING_STATES


_ALLOWING_STATES: Final[frozenset[CircuitState]] = frozenset({
    CircuitState.CLOSED,
    CircuitState.HALF_OPEN,
})


# =============================================================================
# 호출 결과
# =============================================================================

@unique
class CallResult(Enum):
    """호출 결과.

    Members:
        SUCCESS: 성공
        FAILURE: 실패
        REJECTED: 서킷 열림으로 거부됨
    """

    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP = {
            CallResult.SUCCESS: "성공",
            CallResult.FAILURE: "실패",
            CallResult.REJECTED: "거부",
        }
        return _MAP[self]


# =============================================================================
# 상태 전환 이벤트
# =============================================================================

@dataclass(slots=True)
class StateTransition:
    """상태 전환 이벤트.

    Attributes:
        breaker_name: 브레이커 이름
        from_state: 이전 상태
        to_state: 새 상태
        timestamp: 전환 시각 (epoch)
        reason: 전환 사유
    """

    breaker_name: str
    from_state: CircuitState
    to_state: CircuitState
    timestamp: float
    reason: str = ""

    def __repr__(self) -> str:
        return (
            f"StateTransition('{self.breaker_name}', "
            f"{self.from_state.value}→{self.to_state.value})"
        )


# =============================================================================
# 브레이커 스냅샷
# =============================================================================

@dataclass(slots=True)
class BreakerSnapshot:
    """서킷 브레이커 현재 상태 스냅샷.

    Attributes:
        name: 브레이커 이름
        state: 현재 상태
        failure_count: 현재 윈도우 내 실패 수
        success_count: 현재 윈도우 내 성공 수
        failure_rate: 현재 실패율
        total_calls: 누적 호출 수
        total_failures: 누적 실패 수
        total_rejections: 누적 거부 수
        last_failure_time: 마지막 실패 시각
        opened_at: OPEN 전환 시각 (None이면 미전환)
    """

    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    failure_rate: float
    total_calls: int
    total_failures: int
    total_rejections: int
    last_failure_time: float | None
    opened_at: float | None

    def __repr__(self) -> str:
        return (
            f"BreakerSnapshot('{self.name}', "
            f"state={self.state.value}, "
            f"failure_rate={self.failure_rate:.1%})"
        )


# =============================================================================
# 타입 정의
# =============================================================================

# 상태 전환 콜백: (transition) -> None
StateChangeCallback = Callable[[StateTransition], None]


# =============================================================================
# 핵심 클래스: CircuitBreaker
# =============================================================================

class CircuitBreaker:
    """서킷 브레이커.

    슬라이딩 윈도우 기반으로 실패율을 추적하고,
    임계치 초과 시 요청을 차단한다.

    사용 예시::

        breaker = CircuitBreaker("gpu_inference")

        if breaker.allow_request():
            try:
                result = gpu_inference(frame)
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            # 폴백 로직
            result = cached_result()

    Args:
        name: 브레이커 이름
        failure_threshold: 연속 실패 임계치 (OPEN 전환 기준)
        recovery_timeout_sec: OPEN → HALF_OPEN 대기 시간
        half_open_max_calls: HALF_OPEN에서 허용할 시험 호출 수
        window_size: 슬라이딩 윈도우 크기
        failure_rate_threshold: 실패율 임계치 (0.0 ~ 1.0)
    """

    __slots__ = (
        "_name",
        "_failure_threshold",
        "_recovery_timeout_sec",
        "_half_open_max_calls",
        "_window_size",
        "_failure_rate_threshold",
        "_state",
        "_window",
        "_half_open_successes",
        "_half_open_calls",
        "_total_calls",
        "_total_failures",
        "_total_rejections",
        "_last_failure_time",
        "_opened_at",
        "_state_history",
        "_callbacks",
        "_lock",
    )

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout_sec: float = DEFAULT_RECOVERY_TIMEOUT_SEC,
        half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS,
        window_size: int = DEFAULT_WINDOW_SIZE,
        failure_rate_threshold: float = DEFAULT_FAILURE_RATE_THRESHOLD,
    ) -> None:
        self._name = name
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout_sec = max(1.0, recovery_timeout_sec)
        self._half_open_max_calls = max(1, half_open_max_calls)
        self._window_size = max(1, window_size)
        self._failure_rate_threshold = max(0.0, min(1.0, failure_rate_threshold))

        self._state = CircuitState.CLOSED
        self._window: deque[CallResult] = deque(maxlen=self._window_size)
        self._half_open_successes = 0
        self._half_open_calls = 0

        self._total_calls = 0
        self._total_failures = 0
        self._total_rejections = 0
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None

        self._state_history: deque[StateTransition] = deque(
            maxlen=MAX_STATE_HISTORY,
        )
        self._callbacks: list[StateChangeCallback] = []
        self._lock = threading.RLock()

    # =========================================================================
    # 속성
    # =========================================================================

    @property
    def name(self) -> str:
        """브레이커 이름."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """현재 상태 (OPEN→HALF_OPEN 자동 전환 포함)."""
        with self._lock:
            self._check_recovery_timeout()
            return self._state

    @property
    def failure_count(self) -> int:
        """현재 윈도우 내 실패 수."""
        with self._lock:
            return sum(1 for r in self._window if r == CallResult.FAILURE)

    @property
    def success_count(self) -> int:
        """현재 윈도우 내 성공 수."""
        with self._lock:
            return sum(1 for r in self._window if r == CallResult.SUCCESS)

    @property
    def failure_rate(self) -> float:
        """현재 실패율 (0.0 ~ 1.0)."""
        with self._lock:
            total = len(self._window)
            if total == 0:
                return 0.0
            failures = sum(1 for r in self._window if r == CallResult.FAILURE)
            return failures / total

    @property
    def total_calls(self) -> int:
        """누적 호출 수."""
        with self._lock:
            return self._total_calls

    @property
    def total_failures(self) -> int:
        """누적 실패 수."""
        with self._lock:
            return self._total_failures

    @property
    def total_rejections(self) -> int:
        """누적 거부 수."""
        with self._lock:
            return self._total_rejections

    # =========================================================================
    # 요청 허용 여부
    # =========================================================================

    def allow_request(self) -> bool:
        """현재 요청을 허용할지 판단.

        Returns:
            허용 시 True, 거부 시 False
        """
        with self._lock:
            self._check_recovery_timeout()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._half_open_max_calls:
                    return True
                return False

            # OPEN
            return False

    # =========================================================================
    # 결과 기록
    # =========================================================================

    def record_success(self) -> None:
        """호출 성공 기록."""
        with self._lock:
            self._total_calls += 1
            self._window.append(CallResult.SUCCESS)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                self._half_open_calls += 1

                # 시험 호출 모두 성공 → CLOSED 복귀
                if self._half_open_successes >= self._half_open_max_calls:
                    self._transition_to(
                        CircuitState.CLOSED,
                        reason=f"반열림 시험 {self._half_open_successes}회 성공",
                    )

    def record_failure(self, error_msg: str = "") -> None:
        """호출 실패 기록.

        Args:
            error_msg: 오류 메시지 (선택)
        """
        with self._lock:
            self._total_calls += 1
            self._total_failures += 1
            self._last_failure_time = time.monotonic()
            self._window.append(CallResult.FAILURE)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                # 반열림에서 실패 → 다시 OPEN
                reason = f"반열림 시험 실패"
                if error_msg:
                    reason += f": {error_msg}"
                self._transition_to(CircuitState.OPEN, reason=reason)
                return

            if self._state == CircuitState.CLOSED:
                self._evaluate_trip()

    def record_rejection(self) -> None:
        """요청 거부 기록 (OPEN 상태에서 호출 시)."""
        with self._lock:
            self._total_rejections += 1

    # =========================================================================
    # 수동 제어
    # =========================================================================

    def trip(self, reason: str = "수동 트립") -> None:
        """수동으로 서킷을 OPEN 상태로 전환.

        Args:
            reason: 트립 사유
        """
        with self._lock:
            if self._state != CircuitState.OPEN:
                self._transition_to(CircuitState.OPEN, reason=reason)

    def reset(self) -> None:
        """수동으로 서킷을 CLOSED 상태로 리셋."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                self._transition_to(
                    CircuitState.CLOSED,
                    reason="수동 리셋",
                )
            self._window.clear()
            self._half_open_successes = 0
            self._half_open_calls = 0

    # =========================================================================
    # 콜백
    # =========================================================================

    def add_callback(self, callback: StateChangeCallback) -> bool:
        """상태 전환 콜백 등록.

        Args:
            callback: (StateTransition) -> None

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if len(self._callbacks) >= MAX_CALLBACKS_PER_BREAKER:
                return False
            self._callbacks.append(callback)
            return True

    def remove_callback(self, callback: StateChangeCallback) -> bool:
        """상태 전환 콜백 해제.

        Returns:
            해제 성공 여부
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    # =========================================================================
    # 스냅샷 / 이력
    # =========================================================================

    def snapshot(self) -> BreakerSnapshot:
        """현재 상태 스냅샷.

        Returns:
            BreakerSnapshot
        """
        with self._lock:
            self._check_recovery_timeout()
            total_window = len(self._window)
            failures = sum(1 for r in self._window if r == CallResult.FAILURE)
            successes = sum(1 for r in self._window if r == CallResult.SUCCESS)
            rate = failures / total_window if total_window > 0 else 0.0

            return BreakerSnapshot(
                name=self._name,
                state=self._state,
                failure_count=failures,
                success_count=successes,
                failure_rate=rate,
                total_calls=self._total_calls,
                total_failures=self._total_failures,
                total_rejections=self._total_rejections,
                last_failure_time=self._last_failure_time,
                opened_at=self._opened_at,
            )

    def get_state_history(self) -> list[StateTransition]:
        """상태 전환 이력 (방어적 복사).

        Returns:
            StateTransition 리스트 (최근 순)
        """
        with self._lock:
            return list(self._state_history)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _evaluate_trip(self) -> None:
        """실패 조건 평가 후 OPEN 전환 여부 결정.

        트립 조건 (OR):
        1. 윈도우 내 연속 실패가 failure_threshold 이상
        2. 윈도우가 충분히 찼고 (≥ failure_threshold) 실패율이 임계치 이상
        """
        # 조건 1: 연속 실패
        consecutive = 0
        for result in reversed(self._window):
            if result == CallResult.FAILURE:
                consecutive += 1
            else:
                break

        if consecutive >= self._failure_threshold:
            self._transition_to(
                CircuitState.OPEN,
                reason=f"연속 실패 {consecutive}회 (임계치 {self._failure_threshold})",
            )
            return

        # 조건 2: 실패율 초과
        total = len(self._window)
        if total >= self._failure_threshold:
            failures = sum(1 for r in self._window if r == CallResult.FAILURE)
            rate = failures / total
            if rate >= self._failure_rate_threshold:
                self._transition_to(
                    CircuitState.OPEN,
                    reason=f"실패율 {rate:.1%} (임계치 {self._failure_rate_threshold:.1%})",
                )

    def _check_recovery_timeout(self) -> None:
        """OPEN 상태에서 복구 대기 시간 경과 시 HALF_OPEN 전환."""
        if self._state != CircuitState.OPEN:
            return
        if self._opened_at is None:
            return

        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self._recovery_timeout_sec:
            self._transition_to(
                CircuitState.HALF_OPEN,
                reason=f"복구 대기 {self._recovery_timeout_sec}초 경과",
            )

    def _transition_to(self, new_state: CircuitState, *, reason: str = "") -> None:
        """상태 전환 실행.

        Args:
            new_state: 새 상태
            reason: 전환 사유
        """
        old_state = self._state
        self._state = new_state

        # OPEN 진입 시 시각 기록
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_successes = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None

        # 이력 기록
        transition = StateTransition(
            breaker_name=self._name,
            from_state=old_state,
            to_state=new_state,
            timestamp=time.monotonic(),
            reason=reason,
        )
        self._state_history.append(transition)

        # 콜백 실행 (예외 격리)
        callbacks = list(self._callbacks)
        for callback in callbacks:
            try:
                callback(transition)
            except Exception:
                pass

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker('{self._name}', "
            f"state={self._state.value}, "
            f"failures={self.failure_count})"
        )


# =============================================================================
# 브레이커 레지스트리
# =============================================================================

class BreakerRegistry:
    """서킷 브레이커 중앙 레지스트리.

    모든 브레이커를 중앙에서 관리하고 모니터링한다.

    사용 예시::

        registry = BreakerRegistry.get_instance()

        # 브레이커 생성 및 등록
        breaker = registry.get_or_create("gpu_inference",
            failure_threshold=3,
            recovery_timeout_sec=60.0,
        )

        # 전체 상태 조회
        snapshots = registry.all_snapshots()
    """

    _instance: type[BreakerRegistry] | BreakerRegistry | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> BreakerRegistry:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 브레이커 관리
    # =========================================================================

    def get_or_create(
        self,
        name: str,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout_sec: float = DEFAULT_RECOVERY_TIMEOUT_SEC,
        half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS,
        window_size: int = DEFAULT_WINDOW_SIZE,
        failure_rate_threshold: float = DEFAULT_FAILURE_RATE_THRESHOLD,
    ) -> CircuitBreaker | None:
        """브레이커 조회 또는 생성.

        이미 존재하면 기존 반환, 없으면 생성.

        Args:
            name: 브레이커 이름
            failure_threshold: 연속 실패 임계치
            recovery_timeout_sec: 복구 대기 시간
            half_open_max_calls: 반열림 시험 호출 수
            window_size: 슬라이딩 윈도우 크기
            failure_rate_threshold: 실패율 임계치

        Returns:
            CircuitBreaker 또는 한도 초과 시 None
        """
        with self._lock:
            if name in self._breakers:
                return self._breakers[name]

            if len(self._breakers) >= MAX_BREAKERS:
                return None

            breaker = CircuitBreaker(
                name,
                failure_threshold=failure_threshold,
                recovery_timeout_sec=recovery_timeout_sec,
                half_open_max_calls=half_open_max_calls,
                window_size=window_size,
                failure_rate_threshold=failure_rate_threshold,
            )
            self._breakers[name] = breaker
            return breaker

    def get(self, name: str) -> CircuitBreaker | None:
        """브레이커 조회.

        Args:
            name: 브레이커 이름

        Returns:
            CircuitBreaker 또는 None
        """
        with self._lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """브레이커 제거.

        Args:
            name: 브레이커 이름

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False

    def has(self, name: str) -> bool:
        """브레이커 존재 여부."""
        with self._lock:
            return name in self._breakers

    # =========================================================================
    # 일괄 조회
    # =========================================================================

    def all_snapshots(self) -> dict[str, BreakerSnapshot]:
        """전체 브레이커 스냅샷.

        Returns:
            이름 → BreakerSnapshot
        """
        with self._lock:
            return {
                name: breaker.snapshot()
                for name, breaker in self._breakers.items()
            }

    def get_open_breakers(self) -> list[str]:
        """OPEN 상태 브레이커 이름 목록.

        Returns:
            OPEN 상태 브레이커 이름 리스트
        """
        with self._lock:
            return [
                name
                for name, breaker in self._breakers.items()
                if breaker.state == CircuitState.OPEN
            ]

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def breaker_count(self) -> int:
        """등록된 브레이커 수."""
        with self._lock:
            return len(self._breakers)

    @property
    def breaker_names(self) -> list[str]:
        """등록된 브레이커 이름 목록."""
        with self._lock:
            return list(self._breakers.keys())

    def clear(self) -> int:
        """전체 브레이커 제거.

        Returns:
            제거된 수
        """
        with self._lock:
            count = len(self._breakers)
            self._breakers.clear()
            return count

    def reset_all(self) -> int:
        """전체 브레이커를 CLOSED 상태로 리셋.

        Returns:
            리셋된 수
        """
        with self._lock:
            count = 0
            for breaker in self._breakers.values():
                if breaker.state != CircuitState.CLOSED:
                    breaker.reset()
                    count += 1
            return count

    def __repr__(self) -> str:
        return f"BreakerRegistry(breakers={self.breaker_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "CircuitState",
    "CallResult",
    # 데이터 클래스
    "StateTransition",
    "BreakerSnapshot",
    # 타입
    "StateChangeCallback",
    # 핵심 클래스
    "CircuitBreaker",
    "BreakerRegistry",
    # 상수
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_RECOVERY_TIMEOUT_SEC",
    "DEFAULT_HALF_OPEN_MAX_CALLS",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_FAILURE_RATE_THRESHOLD",
    "MAX_BREAKERS",
    "MAX_CALLBACKS_PER_BREAKER",
    "MAX_STATE_HISTORY",
]

__version__ = "1.0.0"
