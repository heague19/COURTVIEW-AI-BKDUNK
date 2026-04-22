# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
파일: retry_mechanism.py
설명: 재시도 메커니즘
      - Exponential Backoff + Jitter
      - 재시도 가능 예외 필터링
      - 최대 재시도 횟수 제한
      - 재시도 이벤트 콜백
      - 동기 실행 (블로킹)
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, Final, TypeVar


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 최대 재시도 횟수
DEFAULT_MAX_RETRIES: Final[int] = 3

# 기본 초기 대기 시간 (초)
DEFAULT_INITIAL_DELAY_SEC: Final[float] = 1.0

# 기본 최대 대기 시간 (초)
DEFAULT_MAX_DELAY_SEC: Final[float] = 60.0

# 기본 백오프 배수
DEFAULT_BACKOFF_MULTIPLIER: Final[float] = 2.0

# 기본 지터 비율 (0.0 ~ 1.0, 대기 시간의 ±비율)
DEFAULT_JITTER_RATIO: Final[float] = 0.1

# 최대 등록 가능한 정책 수
MAX_POLICIES: Final[int] = 50

# 최대 이력 수 (정책당)
MAX_ATTEMPT_HISTORY: Final[int] = 100

# 최대 콜백 수 (정책당)
MAX_CALLBACKS_PER_POLICY: Final[int] = 20


# =============================================================================
# 백오프 전략 Enum
# =============================================================================

@unique
class BackoffStrategy(Enum):
    """백오프 전략.

    Members:
        EXPONENTIAL: 지수 백오프 (기본)
        LINEAR: 선형 백오프
        FIXED: 고정 대기
    """

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP = {
            BackoffStrategy.EXPONENTIAL: "지수 백오프",
            BackoffStrategy.LINEAR: "선형 백오프",
            BackoffStrategy.FIXED: "고정 대기",
        }
        return _MAP[self]


# =============================================================================
# 재시도 결과 Enum
# =============================================================================

@unique
class RetryOutcome(Enum):
    """재시도 결과.

    Members:
        SUCCESS: 성공 (재시도 포함)
        EXHAUSTED: 재시도 횟수 소진
        NON_RETRYABLE: 재시도 불가 예외
    """

    SUCCESS = "success"
    EXHAUSTED = "exhausted"
    NON_RETRYABLE = "non_retryable"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP = {
            RetryOutcome.SUCCESS: "성공",
            RetryOutcome.EXHAUSTED: "재시도 소진",
            RetryOutcome.NON_RETRYABLE: "재시도 불가",
        }
        return _MAP[self]

    @property
    def is_success(self) -> bool:
        """성공 여부."""
        return self == RetryOutcome.SUCCESS


# =============================================================================
# 시도 기록
# =============================================================================

@dataclass(slots=True)
class AttemptRecord:
    """개별 시도 기록.

    Attributes:
        attempt_number: 시도 번호 (1부터)
        success: 성공 여부
        duration_sec: 소요 시간 (초)
        error_type: 오류 타입명 (실패 시)
        error_message: 오류 메시지 (실패 시)
        delay_before_sec: 이 시도 전 대기 시간
    """

    attempt_number: int
    success: bool
    duration_sec: float = 0.0
    error_type: str = ""
    error_message: str = ""
    delay_before_sec: float = 0.0

    def __repr__(self) -> str:
        status = "성공" if self.success else f"실패({self.error_type})"
        return (
            f"AttemptRecord(#{self.attempt_number}, "
            f"{status}, {self.duration_sec:.3f}s)"
        )


# =============================================================================
# 재시도 결과
# =============================================================================

@dataclass(slots=True)
class RetryResult:
    """재시도 실행 결과.

    Attributes:
        outcome: 최종 결과
        value: 성공 시 반환값
        total_attempts: 총 시도 횟수
        total_duration_sec: 총 소요 시간
        attempts: 시도 이력
        last_error: 마지막 예외 (실패 시)
    """

    outcome: RetryOutcome
    value: Any = None
    total_attempts: int = 0
    total_duration_sec: float = 0.0
    attempts: list[AttemptRecord] = field(default_factory=list)
    last_error: Exception | None = None

    @property
    def is_success(self) -> bool:
        """성공 여부."""
        return self.outcome.is_success

    @property
    def retry_count(self) -> int:
        """재시도 횟수 (첫 시도 제외)."""
        return max(0, self.total_attempts - 1)

    def __repr__(self) -> str:
        return (
            f"RetryResult({self.outcome.value}, "
            f"attempts={self.total_attempts}, "
            f"duration={self.total_duration_sec:.3f}s)"
        )


# =============================================================================
# 타입 정의
# =============================================================================

T = TypeVar("T")

# 재시도 이벤트 콜백: (attempt_record) -> None
RetryEventCallback = Callable[[AttemptRecord], None]

# 재시도 가능 예외 판정 함수: (exception) -> bool
RetryableChecker = Callable[[Exception], bool]


# =============================================================================
# 재시도 정책
# =============================================================================

class RetryPolicy:
    """재시도 정책.

    특정 작업에 대한 재시도 전략을 정의한다.

    사용 예시::

        policy = RetryPolicy(
            name="gpu_inference",
            max_retries=3,
            backoff=BackoffStrategy.EXPONENTIAL,
            initial_delay_sec=0.5,
            retryable_exceptions=[RuntimeError, TimeoutError],
        )

        result = policy.execute(lambda: gpu_model.predict(frame))
        if result.is_success:
            predictions = result.value

    Args:
        name: 정책 이름
        max_retries: 최대 재시도 횟수
        backoff: 백오프 전략
        initial_delay_sec: 초기 대기 시간
        max_delay_sec: 최대 대기 시간
        backoff_multiplier: 백오프 배수 (지수/선형)
        jitter_ratio: 지터 비율
        retryable_exceptions: 재시도 가능 예외 타입 리스트
        retryable_checker: 재시도 가능 예외 판정 함수 (추가 조건)
    """

    __slots__ = (
        "_name",
        "_max_retries",
        "_backoff",
        "_initial_delay_sec",
        "_max_delay_sec",
        "_backoff_multiplier",
        "_jitter_ratio",
        "_retryable_exceptions",
        "_retryable_checker",
        "_callbacks",
        "_history",
        "_total_executions",
        "_total_successes",
        "_total_exhausted",
        "_lock",
    )

    def __init__(
        self,
        name: str,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        initial_delay_sec: float = DEFAULT_INITIAL_DELAY_SEC,
        max_delay_sec: float = DEFAULT_MAX_DELAY_SEC,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        jitter_ratio: float = DEFAULT_JITTER_RATIO,
        retryable_exceptions: list[type[Exception]] | None = None,
        retryable_checker: RetryableChecker | None = None,
    ) -> None:
        self._name = name
        self._max_retries = max(0, max_retries)
        self._backoff = backoff
        self._initial_delay_sec = max(0.0, initial_delay_sec)
        self._max_delay_sec = max(self._initial_delay_sec, max_delay_sec)
        self._backoff_multiplier = max(1.0, backoff_multiplier)
        self._jitter_ratio = max(0.0, min(1.0, jitter_ratio))
        self._retryable_exceptions: tuple[type[Exception], ...] = (
            tuple(retryable_exceptions) if retryable_exceptions else (Exception,)
        )
        self._retryable_checker = retryable_checker

        self._callbacks: list[RetryEventCallback] = []
        self._history: deque[RetryResult] = deque(maxlen=MAX_ATTEMPT_HISTORY)
        self._total_executions = 0
        self._total_successes = 0
        self._total_exhausted = 0
        self._lock = threading.RLock()

    # =========================================================================
    # 속성
    # =========================================================================

    @property
    def name(self) -> str:
        """정책 이름."""
        return self._name

    @property
    def max_retries(self) -> int:
        """최대 재시도 횟수."""
        return self._max_retries

    @property
    def backoff(self) -> BackoffStrategy:
        """백오프 전략."""
        return self._backoff

    @property
    def total_executions(self) -> int:
        """총 실행 횟수."""
        with self._lock:
            return self._total_executions

    @property
    def total_successes(self) -> int:
        """총 성공 횟수."""
        with self._lock:
            return self._total_successes

    @property
    def total_exhausted(self) -> int:
        """총 재시도 소진 횟수."""
        with self._lock:
            return self._total_exhausted

    @property
    def success_rate(self) -> float:
        """성공률 (0.0 ~ 1.0)."""
        with self._lock:
            if self._total_executions == 0:
                return 0.0
            return self._total_successes / self._total_executions

    # =========================================================================
    # 실행
    # =========================================================================

    def execute(self, fn: Callable[[], T]) -> RetryResult:
        """재시도 정책에 따라 함수를 실행.

        Args:
            fn: 실행할 함수 (인자 없음, 반환값 있음)

        Returns:
            RetryResult
        """
        start_time = time.monotonic()
        attempts: list[AttemptRecord] = []
        last_error: Exception | None = None
        max_attempts = 1 + self._max_retries  # 첫 시도 + 재시도

        for attempt_num in range(1, max_attempts + 1):
            # 재시도 대기 (첫 시도는 즉시)
            delay = 0.0
            if attempt_num > 1:
                delay = self._calculate_delay(attempt_num - 1)
                time.sleep(delay)

            attempt_start = time.monotonic()
            try:
                result_value = fn()
                duration = time.monotonic() - attempt_start

                record = AttemptRecord(
                    attempt_number=attempt_num,
                    success=True,
                    duration_sec=duration,
                    delay_before_sec=delay,
                )
                attempts.append(record)
                self._notify_callbacks(record)

                total_duration = time.monotonic() - start_time
                result = RetryResult(
                    outcome=RetryOutcome.SUCCESS,
                    value=result_value,
                    total_attempts=attempt_num,
                    total_duration_sec=total_duration,
                    attempts=attempts,
                )
                self._record_result(result)
                return result

            except Exception as e:
                duration = time.monotonic() - attempt_start
                last_error = e

                record = AttemptRecord(
                    attempt_number=attempt_num,
                    success=False,
                    duration_sec=duration,
                    error_type=type(e).__name__,
                    error_message=str(e)[:200],
                    delay_before_sec=delay,
                )
                attempts.append(record)
                self._notify_callbacks(record)

                # 재시도 불가 예외인지 판단
                if not self._is_retryable(e):
                    total_duration = time.monotonic() - start_time
                    result = RetryResult(
                        outcome=RetryOutcome.NON_RETRYABLE,
                        total_attempts=attempt_num,
                        total_duration_sec=total_duration,
                        attempts=attempts,
                        last_error=e,
                    )
                    self._record_result(result)
                    return result

        # 재시도 소진
        total_duration = time.monotonic() - start_time
        result = RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            total_attempts=max_attempts,
            total_duration_sec=total_duration,
            attempts=attempts,
            last_error=last_error,
        )
        self._record_result(result)
        return result

    # =========================================================================
    # 콜백
    # =========================================================================

    def add_callback(self, callback: RetryEventCallback) -> bool:
        """재시도 이벤트 콜백 등록.

        Args:
            callback: (AttemptRecord) -> None

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if len(self._callbacks) >= MAX_CALLBACKS_PER_POLICY:
                return False
            self._callbacks.append(callback)
            return True

    def remove_callback(self, callback: RetryEventCallback) -> bool:
        """재시도 이벤트 콜백 해제.

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
    # 이력
    # =========================================================================

    def get_history(self) -> list[RetryResult]:
        """실행 이력 (방어적 복사).

        Returns:
            RetryResult 리스트
        """
        with self._lock:
            return list(self._history)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _calculate_delay(self, retry_number: int) -> float:
        """대기 시간 계산.

        Args:
            retry_number: 재시도 번호 (1부터)

        Returns:
            대기 시간 (초)
        """
        if self._backoff == BackoffStrategy.EXPONENTIAL:
            delay = self._initial_delay_sec * (
                self._backoff_multiplier ** (retry_number - 1)
            )
        elif self._backoff == BackoffStrategy.LINEAR:
            delay = self._initial_delay_sec * retry_number
        else:  # FIXED
            delay = self._initial_delay_sec

        # 최대 대기 시간 제한
        delay = min(delay, self._max_delay_sec)

        # 지터 적용
        if self._jitter_ratio > 0.0:
            jitter_range = delay * self._jitter_ratio
            delay += random.uniform(-jitter_range, jitter_range)  # noqa: S311
            delay = max(0.0, delay)

        return delay

    def _is_retryable(self, error: Exception) -> bool:
        """예외가 재시도 가능한지 판단.

        Args:
            error: 발생한 예외

        Returns:
            재시도 가능 여부
        """
        # 타입 검사
        if not isinstance(error, self._retryable_exceptions):
            return False

        # 커스텀 체커
        if self._retryable_checker is not None:
            try:
                return self._retryable_checker(error)
            except Exception:
                return False

        return True

    def _notify_callbacks(self, record: AttemptRecord) -> None:
        """콜백 실행 (예외 격리).

        Args:
            record: 시도 기록
        """
        with self._lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(record)
            except Exception:
                pass

    def _record_result(self, result: RetryResult) -> None:
        """실행 결과 기록.

        Args:
            result: 실행 결과
        """
        with self._lock:
            self._history.append(result)
            self._total_executions += 1
            if result.is_success:
                self._total_successes += 1
            elif result.outcome == RetryOutcome.EXHAUSTED:
                self._total_exhausted += 1

    def __repr__(self) -> str:
        return (
            f"RetryPolicy('{self._name}', "
            f"max_retries={self._max_retries}, "
            f"backoff={self._backoff.value})"
        )


# =============================================================================
# 정책 레지스트리
# =============================================================================

class RetryPolicyRegistry:
    """재시도 정책 중앙 레지스트리.

    사용 예시::

        registry = RetryPolicyRegistry.get_instance()

        # 정책 생성 및 등록
        policy = registry.get_or_create("gpu_inference",
            max_retries=3,
            backoff=BackoffStrategy.EXPONENTIAL,
        )

        # 정책으로 실행
        result = policy.execute(lambda: gpu_model.predict(frame))
    """

    _instance: type[RetryPolicyRegistry] | RetryPolicyRegistry | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._policies: dict[str, RetryPolicy] = {}
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> RetryPolicyRegistry:
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
    # 정책 관리
    # =========================================================================

    def get_or_create(
        self,
        name: str,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        initial_delay_sec: float = DEFAULT_INITIAL_DELAY_SEC,
        max_delay_sec: float = DEFAULT_MAX_DELAY_SEC,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        jitter_ratio: float = DEFAULT_JITTER_RATIO,
        retryable_exceptions: list[type[Exception]] | None = None,
        retryable_checker: RetryableChecker | None = None,
    ) -> RetryPolicy | None:
        """정책 조회 또는 생성.

        Args:
            name: 정책 이름
            (나머지: RetryPolicy 생성자와 동일)

        Returns:
            RetryPolicy 또는 한도 초과 시 None
        """
        with self._lock:
            if name in self._policies:
                return self._policies[name]

            if len(self._policies) >= MAX_POLICIES:
                return None

            policy = RetryPolicy(
                name,
                max_retries=max_retries,
                backoff=backoff,
                initial_delay_sec=initial_delay_sec,
                max_delay_sec=max_delay_sec,
                backoff_multiplier=backoff_multiplier,
                jitter_ratio=jitter_ratio,
                retryable_exceptions=retryable_exceptions,
                retryable_checker=retryable_checker,
            )
            self._policies[name] = policy
            return policy

    def get(self, name: str) -> RetryPolicy | None:
        """정책 조회.

        Returns:
            RetryPolicy 또는 None
        """
        with self._lock:
            return self._policies.get(name)

    def remove(self, name: str) -> bool:
        """정책 제거.

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if name in self._policies:
                del self._policies[name]
                return True
            return False

    def has(self, name: str) -> bool:
        """정책 존재 여부."""
        with self._lock:
            return name in self._policies

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def policy_count(self) -> int:
        """등록된 정책 수."""
        with self._lock:
            return len(self._policies)

    @property
    def policy_names(self) -> list[str]:
        """등록된 정책 이름 목록."""
        with self._lock:
            return list(self._policies.keys())

    def clear(self) -> int:
        """전체 정책 제거.

        Returns:
            제거된 수
        """
        with self._lock:
            count = len(self._policies)
            self._policies.clear()
            return count

    def __repr__(self) -> str:
        return f"RetryPolicyRegistry(policies={self.policy_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "BackoffStrategy",
    "RetryOutcome",
    # 데이터 클래스
    "AttemptRecord",
    "RetryResult",
    # 타입
    "RetryEventCallback",
    "RetryableChecker",
    # 핵심 클래스
    "RetryPolicy",
    "RetryPolicyRegistry",
    # 상수
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_INITIAL_DELAY_SEC",
    "DEFAULT_MAX_DELAY_SEC",
    "DEFAULT_BACKOFF_MULTIPLIER",
    "DEFAULT_JITTER_RATIO",
    "MAX_POLICIES",
    "MAX_ATTEMPT_HISTORY",
    "MAX_CALLBACKS_PER_POLICY",
]

__version__ = "1.0.0"
