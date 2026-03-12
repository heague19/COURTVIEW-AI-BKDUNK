# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
파일: retry_mechanism.py
버전: 1.0.0
설명: 재시도 메커니즘 - 지수 백오프, 지터, 조건부 재시도

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-12

주요 기능:
    - 다양한 백오프 전략 (고정, 선형, 지수)
    - 지터를 통한 thundering herd 방지
    - 재시도 가능 예외 기반 필터링
    - 동기/비동기 재시도 지원
    - 상세 재시도 결과 및 메트릭
"""

from __future__ import annotations

__version__: str = "1.0.0"

# ============================================================
# 표준 라이브러리
# ============================================================

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from functools import wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Generic, TypeVar

# ============================================================
# shared 임포트
# ============================================================
from shared.exceptions.base_exception import RetryableException
from shared.exceptions.infrastructure_exceptions import TimeoutException

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import Timer

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# TYPE_CHECKING (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.metrics import MetricsCollector

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 타입 변수
# ============================================================
T = TypeVar("T")
ExceptionTypes = type[Exception] | tuple[type[Exception], ...]

# ============================================================
# 상수 정의
# ============================================================
# 기본 설정값
DEFAULT_MAX_ATTEMPTS: int = 3
DEFAULT_INITIAL_DELAY: float = 1.0
DEFAULT_MAX_DELAY: float = 30.0
DEFAULT_EXPONENTIAL_BASE: float = 2.0
DEFAULT_JITTER_FACTOR: float = 0.1
DEFAULT_TIMEOUT: float = 60.0

# 최소/최대 제한
MIN_DELAY: float = 0.001  # 1ms
MAX_DELAY_CAP: float = 300.0  # 5분
MIN_JITTER_FACTOR: float = 0.0
MAX_JITTER_FACTOR: float = 1.0


# ============================================================
# Enum 정의
# ============================================================
class BackoffStrategy(Enum):
    """
    백오프 전략.

    재시도 간 대기 시간 계산 방식을 정의합니다.
    """

    CONSTANT = auto()  # 고정 대기 시간
    LINEAR = auto()  # 선형 증가
    EXPONENTIAL = auto()  # 지수 증가
    DECORRELATED_JITTER = auto()  # 상관관계 없는 지터 (AWS 권장)

    @property
    def korean_label(self) -> str:
        """한글 라벨 반환."""
        labels = {
            BackoffStrategy.CONSTANT: "고정",
            BackoffStrategy.LINEAR: "선형",
            BackoffStrategy.EXPONENTIAL: "지수",
            BackoffStrategy.DECORRELATED_JITTER: "디코릴레이티드 지터",
        }
        return labels.get(self, "알 수 없음")


class RetryOutcome(Enum):
    """재시도 결과."""

    SUCCESS = auto()  # 성공
    EXHAUSTED = auto()  # 재시도 횟수 소진
    NON_RETRYABLE = auto()  # 재시도 불가 예외
    TIMEOUT = auto()  # 타임아웃
    CANCELLED = auto()  # 취소됨


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class RetryConfig:
    """
    재시도 설정.

    재시도 동작을 구성하는 모든 설정을 담습니다.
    """

    # 기본 설정
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay: float = DEFAULT_INITIAL_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE

    # 지터 설정
    jitter_enabled: bool = True
    jitter_factor: float = DEFAULT_JITTER_FACTOR

    # 타임아웃 설정
    timeout: float | None = None
    per_attempt_timeout: float | None = None

    # 예외 필터링
    retryable_exceptions: tuple[type[Exception], ...] = (
        RetryableException,
        ConnectionError,
        TimeoutError,
    )
    non_retryable_exceptions: tuple[type[Exception], ...] = ()

    # 콜백
    on_retry: Callable[[int, Exception, float], None] | None = None
    on_success: Callable[[int, float], None] | None = None
    on_failure: Callable[[int, Exception], None] | None = None

    # 로깅
    log_retries: bool = True
    log_level: int = logging.WARNING

    def __post_init__(self) -> None:
        """설정 유효성 검증."""
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts는 1 이상이어야 합니다: {self.max_attempts}")

        if self.initial_delay < MIN_DELAY:
            raise ValueError(f"initial_delay는 {MIN_DELAY}초 이상이어야 합니다: {self.initial_delay}")

        if self.max_delay < self.initial_delay:
            raise ValueError(
                f"max_delay({self.max_delay})는 initial_delay({self.initial_delay}) 이상이어야 합니다"
            )

        if self.max_delay > MAX_DELAY_CAP:
            logger.warning(
                f"max_delay({self.max_delay})가 최대값({MAX_DELAY_CAP})을 초과하여 제한됩니다"
            )
            self.max_delay = MAX_DELAY_CAP

        if self.exponential_base < 1.0:
            raise ValueError(f"exponential_base는 1.0 이상이어야 합니다: {self.exponential_base}")

        if not MIN_JITTER_FACTOR <= self.jitter_factor <= MAX_JITTER_FACTOR:
            raise ValueError(
                f"jitter_factor는 {MIN_JITTER_FACTOR}~{MAX_JITTER_FACTOR} 사이여야 합니다: {self.jitter_factor}"
            )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "max_attempts": self.max_attempts,
            "backoff_strategy": self.backoff_strategy.name,
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "exponential_base": self.exponential_base,
            "jitter_enabled": self.jitter_enabled,
            "jitter_factor": self.jitter_factor,
            "timeout": self.timeout,
            "per_attempt_timeout": self.per_attempt_timeout,
            "log_retries": self.log_retries,
        }

    @classmethod
    def from_yaml(cls, operation: str | None = None) -> "RetryConfig":
        """
        YAML 설정에서 RetryConfig 생성.

        Args:
            operation: 작업명 (operations 설정에서 조회)

        Returns:
            RetryConfig 인스턴스
        """
        try:
            config_loader = ConfigLoader()
            retry_config = config_loader.get("resilience.retry", {})

            defaults = retry_config.get("defaults", {})

            # 작업별 설정 오버라이드
            if operation:
                operations = retry_config.get("operations", {})
                if operation in operations:
                    op_config = operations[operation]
                    defaults = {**defaults, **op_config}

            # 백오프 전략 변환
            strategy_str = defaults.get("backoff_strategy", "exponential").upper()
            try:
                strategy = BackoffStrategy[strategy_str]
            except KeyError:
                strategy = BackoffStrategy.EXPONENTIAL

            # 지터 설정
            jitter_config = defaults.get("jitter", {})
            jitter_enabled = jitter_config.get("enabled", True) if isinstance(jitter_config, dict) else True
            jitter_factor = jitter_config.get("factor", DEFAULT_JITTER_FACTOR) if isinstance(jitter_config, dict) else DEFAULT_JITTER_FACTOR

            return cls(
                max_attempts=defaults.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
                backoff_strategy=strategy,
                initial_delay=defaults.get("initial_delay", DEFAULT_INITIAL_DELAY),
                max_delay=defaults.get("max_delay", DEFAULT_MAX_DELAY),
                exponential_base=defaults.get("exponential_base", DEFAULT_EXPONENTIAL_BASE),
                jitter_enabled=jitter_enabled,
                jitter_factor=jitter_factor,
            )

        except Exception as e:
            logger.warning(f"YAML 설정 로드 실패, 기본값 사용: {e}")
            return cls()


@dataclass(slots=True)
class RetryAttempt:
    """재시도 시도 정보."""

    attempt_number: int
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    success: bool = False
    exception: Exception | None = None
    delay_before: float = 0.0  # 이 시도 전 대기 시간

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "attempt_number": self.attempt_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "exception_type": type(self.exception).__name__ if self.exception else None,
            "exception_message": str(self.exception) if self.exception else None,
            "delay_before": self.delay_before,
        }


@dataclass(slots=True)
class RetryResult(Generic[T]):
    """
    재시도 결과.

    전체 재시도 과정의 결과를 담습니다.
    """

    # 결과
    outcome: RetryOutcome
    success: bool
    value: T | None = None
    final_exception: Exception | None = None

    # 시도 정보
    total_attempts: int = 0
    attempts: list[RetryAttempt] = field(default_factory=list)

    # 시간 정보
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    total_duration_ms: float = 0.0
    total_delay_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "outcome": self.outcome.name,
            "success": self.success,
            "total_attempts": self.total_attempts,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "total_delay_ms": self.total_delay_ms,
            "final_exception_type": type(self.final_exception).__name__ if self.final_exception else None,
            "final_exception_message": str(self.final_exception) if self.final_exception else None,
            "attempts": [a.to_dict() for a in self.attempts],
        }


# ============================================================
# 백오프 계산 함수
# ============================================================
def calculate_backoff(
    attempt: int,
    strategy: BackoffStrategy,
    initial_delay: float,
    max_delay: float,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter_enabled: bool = True,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
    previous_delay: float | None = None,
) -> float:
    """
    백오프 대기 시간 계산.

    Args:
        attempt: 현재 시도 번호 (1부터 시작)
        strategy: 백오프 전략
        initial_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_base: 지수 백오프 배수
        jitter_enabled: 지터 활성화 여부
        jitter_factor: 지터 계수 (0.0 ~ 1.0)
        previous_delay: 이전 대기 시간 (디코릴레이티드 지터용)

    Returns:
        계산된 대기 시간 (초)
    """
    if attempt < 1:
        return 0.0

    # 기본 대기 시간 계산
    if strategy == BackoffStrategy.CONSTANT:
        base_delay = initial_delay

    elif strategy == BackoffStrategy.LINEAR:
        base_delay = initial_delay * attempt

    elif strategy == BackoffStrategy.EXPONENTIAL:
        # 지수 백오프: initial_delay * base^(attempt-1)
        base_delay = initial_delay * (exponential_base ** (attempt - 1))

    elif strategy == BackoffStrategy.DECORRELATED_JITTER:
        # AWS 권장 디코릴레이티드 지터
        # sleep = min(cap, random_between(base, previous_sleep * 3))
        if previous_delay is None:
            previous_delay = initial_delay
        base_delay = random.uniform(initial_delay, previous_delay * 3)
        jitter_enabled = False  # 이미 랜덤 포함

    else:
        base_delay = initial_delay

    # 최대값 제한
    delay = min(base_delay, max_delay)

    # 지터 적용
    if jitter_enabled and jitter_factor > 0:
        # 지터 범위: delay * (1 - jitter_factor) ~ delay * (1 + jitter_factor)
        jitter_range = delay * jitter_factor
        delay = delay + random.uniform(-jitter_range, jitter_range)
        # 음수 방지
        delay = max(MIN_DELAY, delay)

    return delay


def _calculate_backoff_from_config(
    attempt: int,
    config: RetryConfig,
    previous_delay: float | None = None,
) -> float:
    """RetryConfig 기반 백오프 계산."""
    return calculate_backoff(
        attempt=attempt,
        strategy=config.backoff_strategy,
        initial_delay=config.initial_delay,
        max_delay=config.max_delay,
        exponential_base=config.exponential_base,
        jitter_enabled=config.jitter_enabled,
        jitter_factor=config.jitter_factor,
        previous_delay=previous_delay,
    )


# ============================================================
# 예외 판별 함수
# ============================================================
def _is_retryable(
    exception: Exception,
    retryable_exceptions: tuple[type[Exception], ...],
    non_retryable_exceptions: tuple[type[Exception], ...],
) -> bool:
    """
    예외가 재시도 가능한지 판별.

    Args:
        exception: 발생한 예외
        retryable_exceptions: 재시도 가능 예외 타입들
        non_retryable_exceptions: 재시도 불가 예외 타입들

    Returns:
        재시도 가능 여부
    """
    # non_retryable 우선 체크
    if non_retryable_exceptions and isinstance(exception, non_retryable_exceptions):
        return False

    # retryable 체크
    if retryable_exceptions and isinstance(exception, retryable_exceptions):
        return True

    # RetryableException 하위 클래스 체크
    if isinstance(exception, RetryableException):
        return True

    return False


# ============================================================
# 메인 클래스: RetryMechanism
# ============================================================
class RetryMechanism:
    """
    재시도 메커니즘.

    다양한 백오프 전략과 예외 필터링을 지원하는 재시도 메커니즘입니다.
    동기/비동기 함수 모두 지원합니다.

    Example:
        # 기본 사용
        retry = RetryMechanism()
        result = retry.execute(my_function, arg1, arg2)

        # 커스텀 설정
        config = RetryConfig(max_attempts=5, backoff_strategy=BackoffStrategy.LINEAR)
        retry = RetryMechanism(config)

        # 비동기 사용
        result = await retry.execute_async(my_async_function)
    """

    def __init__(
        self,
        config: RetryConfig | None = None,
        name: str | None = None,
        metrics_collector: "MetricsCollector" | None = None,
    ) -> None:
        """
        RetryMechanism 초기화.

        Args:
            config: 재시도 설정
            name: 메커니즘 이름 (메트릭/로깅용)
            metrics_collector: 메트릭 수집기 (DI)
        """
        self._config = config or RetryConfig()
        self._name = name or "default"
        self._metrics_collector = metrics_collector

        logger.debug(
            f"RetryMechanism '{self._name}' 생성: "
            f"max_attempts={self._config.max_attempts}, "
            f"strategy={self._config.backoff_strategy.name}"
        )

    def __repr__(self) -> str:
        """RetryMechanism 인스턴스 표현."""
        return (
            f"RetryMechanism(name={self._name!r}, "
            f"max_attempts={self._config.max_attempts}, "
            f"strategy={self._config.backoff_strategy.name})"
        )

    @property
    def config(self) -> RetryConfig:
        """현재 설정 반환."""
        return self._config

    @property
    def name(self) -> str:
        """이름 반환."""
        return self._name

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        config_override: RetryConfig | None = None,
        **kwargs: Any,
    ) -> T:
        """
        동기 함수 재시도 실행.

        Args:
            func: 실행할 함수
            *args: 함수 인수
            config_override: 설정 오버라이드
            **kwargs: 함수 키워드 인수

        Returns:
            함수 반환값

        Raises:
            마지막 예외 또는 TimeoutException
        """
        result = self._execute_with_retry(func, args, kwargs, config_override)

        if result.success:
            return result.value  # type: ignore

        if result.final_exception:
            raise result.final_exception

        raise RuntimeError("재시도 실패: 알 수 없는 오류")

    def execute_with_result(
        self,
        func: Callable[..., T],
        *args: Any,
        config_override: RetryConfig | None = None,
        **kwargs: Any,
    ) -> RetryResult[T]:
        """
        동기 함수 재시도 실행 (상세 결과 반환).

        Args:
            func: 실행할 함수
            *args: 함수 인수
            config_override: 설정 오버라이드
            **kwargs: 함수 키워드 인수

        Returns:
            RetryResult 객체
        """
        return self._execute_with_retry(func, args, kwargs, config_override)

    def _execute_with_retry(
        self,
        func: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        config_override: RetryConfig | None,
    ) -> RetryResult[T]:
        """내부 재시도 실행 로직."""
        config = config_override or self._config

        result = RetryResult[T](
            outcome=RetryOutcome.EXHAUSTED,
            success=False,
            start_time=datetime.now(timezone.utc),
        )

        previous_delay: float | None = None
        total_start = time.perf_counter()
        timeout_deadline = total_start + config.timeout if config.timeout else None

        for attempt in range(1, config.max_attempts + 1):
            # 타임아웃 체크
            if timeout_deadline and time.perf_counter() >= timeout_deadline:
                result.outcome = RetryOutcome.TIMEOUT
                result.final_exception = TimeoutException(
                    message=f"전체 타임아웃 초과: {config.timeout}초",
                    timeout_seconds=config.timeout,
                    operation=func.__name__,
                )
                break

            # 재시도 대기 (첫 시도는 대기 없음)
            delay = 0.0
            if attempt > 1:
                delay = _calculate_backoff_from_config(attempt - 1, config, previous_delay)
                previous_delay = delay

                # 타임아웃 고려한 대기 시간 조정
                if timeout_deadline:
                    remaining = timeout_deadline - time.perf_counter()
                    if remaining <= 0:
                        result.outcome = RetryOutcome.TIMEOUT
                        result.final_exception = TimeoutException(
                            message=f"전체 타임아웃 초과: {config.timeout}초",
                            timeout_seconds=config.timeout,
                            operation=func.__name__,
                        )
                        break
                    delay = min(delay, remaining)

                if config.log_retries:
                    logger.log(
                        config.log_level,
                        f"[{self._name}] 재시도 #{attempt - 1} → #{attempt}, "
                        f"대기: {delay:.3f}초"
                    )

                time.sleep(delay)
                result.total_delay_ms += delay * 1000

            # 시도 정보 생성
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                start_time=datetime.now(timezone.utc),
                delay_before=delay,
            )

            timer = Timer()
            try:
                timer.start()
                value = func(*args, **kwargs)
                timer_result = timer.stop()

                # 성공
                attempt_info.end_time = datetime.now(timezone.utc)
                attempt_info.duration_ms = timer_result.elapsed_ms
                attempt_info.success = True
                result.attempts.append(attempt_info)

                result.outcome = RetryOutcome.SUCCESS
                result.success = True
                result.value = value
                result.total_attempts = attempt

                # 성공 콜백
                if config.on_success:
                    try:
                        config.on_success(attempt, timer_result.elapsed_ms)
                    except Exception as cb_err:
                        logger.warning(f"on_success 콜백 오류: {cb_err}")

                # 메트릭 기록
                self._record_metrics(attempt, timer_result.elapsed_ms, True)

                if attempt > 1:
                    logger.info(
                        f"[{self._name}] 재시도 #{attempt}에서 성공, "
                        f"총 시간: {timer_result.elapsed_ms:.2f}ms"
                    )

                break

            except Exception as e:
                if timer._running:
                    timer_result = timer.stop()
                    attempt_info.duration_ms = timer_result.elapsed_ms

                attempt_info.end_time = datetime.now(timezone.utc)
                attempt_info.exception = e
                result.attempts.append(attempt_info)
                result.final_exception = e
                result.total_attempts = attempt

                # 재시도 가능 여부 체크
                if not _is_retryable(
                    e,
                    config.retryable_exceptions,
                    config.non_retryable_exceptions,
                ):
                    result.outcome = RetryOutcome.NON_RETRYABLE

                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"[{self._name}] 재시도 불가 예외 발생: {type(e).__name__}: {e}"
                        )
                    break

                # 재시도 콜백
                if config.on_retry and attempt < config.max_attempts:
                    try:
                        next_delay = _calculate_backoff_from_config(attempt, config, previous_delay)
                        config.on_retry(attempt, e, next_delay)
                    except Exception as cb_err:
                        logger.warning(f"on_retry 콜백 오류: {cb_err}")

                if config.log_retries:
                    logger.log(
                        config.log_level,
                        f"[{self._name}] 시도 #{attempt} 실패: {type(e).__name__}: {e}"
                    )

        # 종료 처리
        result.end_time = datetime.now(timezone.utc)
        result.total_duration_ms = (time.perf_counter() - total_start) * 1000

        # 실패 콜백
        if not result.success and config.on_failure and result.final_exception:
            try:
                config.on_failure(result.total_attempts, result.final_exception)
            except Exception as cb_err:
                logger.warning(f"on_failure 콜백 오류: {cb_err}")

        # 메트릭 기록 (실패 시)
        if not result.success:
            self._record_metrics(result.total_attempts, result.total_duration_ms, False)

        return result

    async def execute_async(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        config_override: RetryConfig | None = None,
        **kwargs: Any,
    ) -> T:
        """
        비동기 함수 재시도 실행.

        Args:
            func: 실행할 비동기 함수
            *args: 함수 인수
            config_override: 설정 오버라이드
            **kwargs: 함수 키워드 인수

        Returns:
            함수 반환값

        Raises:
            마지막 예외 또는 TimeoutException
        """
        result = await self._execute_async_with_retry(func, args, kwargs, config_override)

        if result.success:
            return result.value  # type: ignore

        if result.final_exception:
            raise result.final_exception

        raise RuntimeError("재시도 실패: 알 수 없는 오류")

    async def execute_async_with_result(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        config_override: RetryConfig | None = None,
        **kwargs: Any,
    ) -> RetryResult[T]:
        """
        비동기 함수 재시도 실행 (상세 결과 반환).

        Args:
            func: 실행할 비동기 함수
            *args: 함수 인수
            config_override: 설정 오버라이드
            **kwargs: 함수 키워드 인수

        Returns:
            RetryResult 객체
        """
        return await self._execute_async_with_retry(func, args, kwargs, config_override)

    async def _execute_async_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        config_override: RetryConfig | None,
    ) -> RetryResult[T]:
        """내부 비동기 재시도 실행 로직."""
        config = config_override or self._config

        result = RetryResult[T](
            outcome=RetryOutcome.EXHAUSTED,
            success=False,
            start_time=datetime.now(timezone.utc),
        )

        previous_delay: float | None = None
        total_start = time.perf_counter()
        timeout_deadline = total_start + config.timeout if config.timeout else None

        for attempt in range(1, config.max_attempts + 1):
            # 타임아웃 체크
            if timeout_deadline and time.perf_counter() >= timeout_deadline:
                result.outcome = RetryOutcome.TIMEOUT
                result.final_exception = TimeoutException(
                    message=f"전체 타임아웃 초과: {config.timeout}초",
                    timeout_seconds=config.timeout,
                    operation=func.__name__,
                )
                break

            # 재시도 대기 (첫 시도는 대기 없음)
            delay = 0.0
            if attempt > 1:
                delay = _calculate_backoff_from_config(attempt - 1, config, previous_delay)
                previous_delay = delay

                # 타임아웃 고려한 대기 시간 조정
                if timeout_deadline:
                    remaining = timeout_deadline - time.perf_counter()
                    if remaining <= 0:
                        result.outcome = RetryOutcome.TIMEOUT
                        result.final_exception = TimeoutException(
                            message=f"전체 타임아웃 초과: {config.timeout}초",
                            timeout_seconds=config.timeout,
                            operation=func.__name__,
                        )
                        break
                    delay = min(delay, remaining)

                if config.log_retries:
                    logger.log(
                        config.log_level,
                        f"[{self._name}] 비동기 재시도 #{attempt - 1} → #{attempt}, "
                        f"대기: {delay:.3f}초"
                    )

                await asyncio.sleep(delay)
                result.total_delay_ms += delay * 1000

            # 시도 정보 생성
            attempt_info = RetryAttempt(
                attempt_number=attempt,
                start_time=datetime.now(timezone.utc),
                delay_before=delay,
            )

            start_time = time.perf_counter()
            try:
                # 개별 시도 타임아웃 적용
                if config.per_attempt_timeout:
                    value = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.per_attempt_timeout,
                    )
                else:
                    value = await func(*args, **kwargs)

                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # 성공
                attempt_info.end_time = datetime.now(timezone.utc)
                attempt_info.duration_ms = elapsed_ms
                attempt_info.success = True
                result.attempts.append(attempt_info)

                result.outcome = RetryOutcome.SUCCESS
                result.success = True
                result.value = value
                result.total_attempts = attempt

                # 성공 콜백
                if config.on_success:
                    try:
                        config.on_success(attempt, elapsed_ms)
                    except Exception as cb_err:
                        logger.warning(f"on_success 콜백 오류: {cb_err}")

                # 메트릭 기록
                self._record_metrics(attempt, elapsed_ms, True)

                if attempt > 1:
                    logger.info(
                        f"[{self._name}] 비동기 재시도 #{attempt}에서 성공, "
                        f"총 시간: {elapsed_ms:.2f}ms"
                    )

                break

            except asyncio.TimeoutError as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                attempt_info.end_time = datetime.now(timezone.utc)
                attempt_info.duration_ms = elapsed_ms

                timeout_exc = TimeoutException(
                    message=f"개별 시도 타임아웃: {config.per_attempt_timeout}초",
                    timeout_seconds=config.per_attempt_timeout,
                    operation=func.__name__,
                )
                attempt_info.exception = timeout_exc
                result.attempts.append(attempt_info)
                result.final_exception = timeout_exc
                result.total_attempts = attempt

                if config.log_retries:
                    logger.log(
                        config.log_level,
                        f"[{self._name}] 시도 #{attempt} 타임아웃"
                    )

            except asyncio.CancelledError:
                result.outcome = RetryOutcome.CANCELLED
                result.final_exception = None
                result.total_attempts = attempt
                break

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                attempt_info.end_time = datetime.now(timezone.utc)
                attempt_info.duration_ms = elapsed_ms
                attempt_info.exception = e
                result.attempts.append(attempt_info)
                result.final_exception = e
                result.total_attempts = attempt

                # 재시도 가능 여부 체크
                if not _is_retryable(
                    e,
                    config.retryable_exceptions,
                    config.non_retryable_exceptions,
                ):
                    result.outcome = RetryOutcome.NON_RETRYABLE

                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"[{self._name}] 재시도 불가 예외 발생: {type(e).__name__}: {e}"
                        )
                    break

                # 재시도 콜백
                if config.on_retry and attempt < config.max_attempts:
                    try:
                        next_delay = _calculate_backoff_from_config(attempt, config, previous_delay)
                        config.on_retry(attempt, e, next_delay)
                    except Exception as cb_err:
                        logger.warning(f"on_retry 콜백 오류: {cb_err}")

                if config.log_retries:
                    logger.log(
                        config.log_level,
                        f"[{self._name}] 시도 #{attempt} 실패: {type(e).__name__}: {e}"
                    )

        # 종료 처리
        result.end_time = datetime.now(timezone.utc)
        result.total_duration_ms = (time.perf_counter() - total_start) * 1000

        # 실패 콜백
        if not result.success and config.on_failure and result.final_exception:
            try:
                config.on_failure(result.total_attempts, result.final_exception)
            except Exception as cb_err:
                logger.warning(f"on_failure 콜백 오류: {cb_err}")

        # 메트릭 기록 (실패 시)
        if not result.success:
            self._record_metrics(result.total_attempts, result.total_duration_ms, False)

        return result

    def _record_metrics(self, attempts: int, duration_ms: float, success: bool) -> None:
        """메트릭 기록."""
        if not self._metrics_collector:
            return

        try:
            labels = {"name": self._name, "success": str(success).lower()}

            # 시도 횟수 히스토그램
            self._metrics_collector.observe(
                "retry_attempts",
                attempts,
                labels=labels,
            )

            # 소요 시간 히스토그램
            self._metrics_collector.observe(
                "retry_duration_ms",
                duration_ms,
                labels=labels,
            )

            # 성공/실패 카운터
            if success:
                self._metrics_collector.increment("retry_success_total", labels={"name": self._name})
            else:
                self._metrics_collector.increment("retry_failure_total", labels={"name": self._name})

        except Exception as e:
            logger.debug(f"메트릭 기록 오류: {e}")


# ============================================================
# 데코레이터
# ============================================================
def retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter_enabled: bool = True,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
    retryable_exceptions: ExceptionTypes = (RetryableException, ConnectionError, TimeoutError),
    non_retryable_exceptions: ExceptionTypes = (),
    on_retry: Callable[[int, Exception, float], None] | None = None,
    log_retries: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    동기 함수 재시도 데코레이터.

    Args:
        max_attempts: 최대 시도 횟수
        backoff_strategy: 백오프 전략
        initial_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_base: 지수 백오프 배수
        jitter_enabled: 지터 활성화
        jitter_factor: 지터 계수
        retryable_exceptions: 재시도 가능 예외
        non_retryable_exceptions: 재시도 불가 예외
        on_retry: 재시도 콜백
        log_retries: 재시도 로깅 여부

    Returns:
        데코레이터 함수

    Example:
        @retry(max_attempts=3, backoff_strategy=BackoffStrategy.EXPONENTIAL)
        def fetch_data():
            return requests.get(url)
    """
    # 튜플로 변환
    if isinstance(retryable_exceptions, type):
        retryable_exceptions = (retryable_exceptions,)
    if isinstance(non_retryable_exceptions, type):
        non_retryable_exceptions = (non_retryable_exceptions,)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = RetryConfig(
            max_attempts=max_attempts,
            backoff_strategy=backoff_strategy,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter_enabled=jitter_enabled,
            jitter_factor=jitter_factor,
            retryable_exceptions=retryable_exceptions,
            non_retryable_exceptions=non_retryable_exceptions,
            on_retry=on_retry,
            log_retries=log_retries,
        )

        mechanism = RetryMechanism(config=config, name=func.__name__)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return mechanism.execute(func, *args, **kwargs)

        # 원본 함수와 메커니즘 참조 저장
        wrapper._retry_mechanism = mechanism  # type: ignore
        wrapper._original_func = func  # type: ignore

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter_enabled: bool = True,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
    retryable_exceptions: ExceptionTypes = (RetryableException, ConnectionError, TimeoutError),
    non_retryable_exceptions: ExceptionTypes = (),
    per_attempt_timeout: float | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
    log_retries: bool = True,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    비동기 함수 재시도 데코레이터.

    Args:
        max_attempts: 최대 시도 횟수
        backoff_strategy: 백오프 전략
        initial_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exponential_base: 지수 백오프 배수
        jitter_enabled: 지터 활성화
        jitter_factor: 지터 계수
        retryable_exceptions: 재시도 가능 예외
        non_retryable_exceptions: 재시도 불가 예외
        per_attempt_timeout: 개별 시도 타임아웃 (초)
        on_retry: 재시도 콜백
        log_retries: 재시도 로깅 여부

    Returns:
        데코레이터 함수

    Example:
        @async_retry(max_attempts=3, per_attempt_timeout=5.0)
        async def fetch_data():
            return await aiohttp.get(url)
    """
    # 튜플로 변환
    if isinstance(retryable_exceptions, type):
        retryable_exceptions = (retryable_exceptions,)
    if isinstance(non_retryable_exceptions, type):
        non_retryable_exceptions = (non_retryable_exceptions,)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        config = RetryConfig(
            max_attempts=max_attempts,
            backoff_strategy=backoff_strategy,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter_enabled=jitter_enabled,
            jitter_factor=jitter_factor,
            retryable_exceptions=retryable_exceptions,
            non_retryable_exceptions=non_retryable_exceptions,
            per_attempt_timeout=per_attempt_timeout,
            on_retry=on_retry,
            log_retries=log_retries,
        )

        mechanism = RetryMechanism(config=config, name=func.__name__)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await mechanism.execute_async(func, *args, **kwargs)

        # 원본 함수와 메커니즘 참조 저장
        wrapper._retry_mechanism = mechanism  # type: ignore
        wrapper._original_func = func  # type: ignore

        return wrapper

    return decorator


# ============================================================
# 헬퍼 함수
# ============================================================
def create_retry_mechanism(
    operation: str | None = None,
    name: str | None = None,
    **config_overrides: Any,
) -> RetryMechanism:
    """
    YAML 설정 기반 RetryMechanism 생성.

    Args:
        operation: 작업명 (YAML operations에서 조회)
        name: 메커니즘 이름
        **config_overrides: 설정 오버라이드

    Returns:
        RetryMechanism 인스턴스
    """
    config = RetryConfig.from_yaml(operation)

    # 오버라이드 적용
    for key, value in config_overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return RetryMechanism(config=config, name=name or operation or "default")


# ============================================================
# 글로벌 레지스트리 (싱글톤 패턴)
# ============================================================
class _RetryRegistry:
    """재시도 메커니즘 레지스트리."""

    _instance: "_RetryRegistry" | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "_RetryRegistry":
        """싱글톤 인스턴스 생성 (이중 검사 잠금)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._mechanisms = {}
        return cls._instance

    def get_or_create(
        self,
        name: str,
        config: RetryConfig | None = None,
    ) -> RetryMechanism:
        """이름으로 메커니즘 조회 또는 생성."""
        if name not in self._mechanisms:
            with self._lock:
                if name not in self._mechanisms:
                    self._mechanisms[name] = RetryMechanism(
                        config=config or RetryConfig(),
                        name=name,
                    )
        return self._mechanisms[name]

    def get(self, name: str) -> RetryMechanism | None:
        """이름으로 메커니즘 조회."""
        return self._mechanisms.get(name)

    def register(self, name: str, mechanism: RetryMechanism) -> None:
        """메커니즘 등록."""
        with self._lock:
            self._mechanisms[name] = mechanism

    def unregister(self, name: str) -> None:
        """메커니즘 등록 해제."""
        with self._lock:
            self._mechanisms.pop(name, None)

    def clear(self) -> None:
        """모든 메커니즘 제거."""
        with self._lock:
            self._mechanisms.clear()

    def list_all(self) -> list[str]:
        """모든 메커니즘 이름 반환."""
        return list(self._mechanisms.keys())


# 글로벌 레지스트리 인스턴스
_registry = _RetryRegistry()


def get_retry_mechanism(name: str) -> RetryMechanism | None:
    """
    이름으로 RetryMechanism 조회.

    Args:
        name: 메커니즘 이름

    Returns:
        RetryMechanism 또는 None
    """
    return _registry.get(name)


def register_retry_mechanism(name: str, mechanism: RetryMechanism) -> None:
    """
    RetryMechanism 등록.

    Args:
        name: 메커니즘 이름
        mechanism: RetryMechanism 인스턴스
    """
    _registry.register(name, mechanism)


# ============================================================
# 유틸리티 함수 (테스트용)
# ============================================================
def _reset_registry() -> None:
    """레지스트리 초기화 (테스트용)."""
    _registry.clear()


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "BackoffStrategy",
    "RetryOutcome",
    # 상수
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_EXPONENTIAL_BASE",
    "DEFAULT_JITTER_FACTOR",
    # 데이터 클래스
    "RetryConfig",
    "RetryAttempt",
    "RetryResult",
    # 메인 클래스
    "RetryMechanism",
    # 데코레이터
    "retry",
    "async_retry",
    # 함수
    "calculate_backoff",
    "create_retry_mechanism",
    "get_retry_mechanism",
    "register_retry_mechanism",
    # 유틸리티 (테스트용)
    "_reset_registry",
]
