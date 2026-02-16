# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
파일: __init__.py
설명: 복원력 모듈 초기화 - 서킷 브레이커, 재시도 메커니즘

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

모듈 구성:
    - circuit_breaker: 서킷 브레이커 패턴 구현
    - retry_mechanism: 재시도 로직 구현 (지수 백오프, 지터)
"""

__version__: str = "1.0.0"

# ============================================================
# circuit_breaker 임포트
# ============================================================
from core_foundation.resilience.circuit_breaker import (
    # Enum
    CircuitState,
    FailureType,
    # 상수
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_SUCCESS_THRESHOLD,
    DEFAULT_OPEN_TIMEOUT,
    DEFAULT_HALF_OPEN_MAX_REQUESTS,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_MINIMUM_REQUESTS,
    # 데이터 클래스
    CircuitBreakerConfig,
    CircuitBreakerStats,
    RequestRecord,
    StateChangeEvent,
    # 메인 클래스
    CircuitBreaker,
    CircuitBreakerRegistry,
    # 데코레이터
    circuit_protected,
    # 함수
    get_circuit_breaker,
    get_all_circuit_status,
    # 유틸리티 (테스트용)
    _get_registry as _get_circuit_registry,
    _reset_registry as _reset_circuit_registry,
)

# ============================================================
# retry_mechanism 임포트
# ============================================================
from core_foundation.resilience.retry_mechanism import (
    # Enum
    BackoffStrategy,
    RetryOutcome,
    # 상수
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_EXPONENTIAL_BASE,
    DEFAULT_JITTER_FACTOR,
    # 데이터 클래스
    RetryConfig,
    RetryAttempt,
    RetryResult,
    # 메인 클래스
    RetryMechanism,
    # 데코레이터
    retry,
    async_retry,
    # 함수
    calculate_backoff,
    create_retry_mechanism,
    get_retry_mechanism,
    register_retry_mechanism,
    # 유틸리티 (테스트용)
    _reset_registry as _reset_retry_registry,
)

# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # circuit_breaker - Enum
    "CircuitState",
    "FailureType",
    # circuit_breaker - 상수
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_SUCCESS_THRESHOLD",
    "DEFAULT_OPEN_TIMEOUT",
    "DEFAULT_HALF_OPEN_MAX_REQUESTS",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_MINIMUM_REQUESTS",
    # circuit_breaker - 데이터 클래스
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "RequestRecord",
    "StateChangeEvent",
    # circuit_breaker - 메인 클래스
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    # circuit_breaker - 데코레이터
    "circuit_protected",
    # circuit_breaker - 함수
    "get_circuit_breaker",
    "get_all_circuit_status",
    # circuit_breaker - 유틸리티 (테스트용)
    "_get_circuit_registry",
    "_reset_circuit_registry",
    # retry_mechanism - Enum
    "BackoffStrategy",
    "RetryOutcome",
    # retry_mechanism - 상수
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_EXPONENTIAL_BASE",
    "DEFAULT_JITTER_FACTOR",
    # retry_mechanism - 데이터 클래스
    "RetryConfig",
    "RetryAttempt",
    "RetryResult",
    # retry_mechanism - 메인 클래스
    "RetryMechanism",
    # retry_mechanism - 데코레이터
    "retry",
    "async_retry",
    # retry_mechanism - 함수
    "calculate_backoff",
    "create_retry_mechanism",
    "get_retry_mechanism",
    "register_retry_mechanism",
    # retry_mechanism - 유틸리티 (테스트용)
    "_reset_retry_registry",
]
