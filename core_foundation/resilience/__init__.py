# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/resilience
설명: 장애 복원력 통합 패키지.
     - CircuitBreaker: 서킷 브레이커 (3-State 상태머신)
     - BreakerRegistry: 서킷 브레이커 중앙 레지스트리
     - RetryPolicy: 재시도 정책 (Exponential Backoff + Jitter)
     - RetryPolicyRegistry: 재시도 정책 중앙 레지스트리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations


# =============================================================================
# circuit_breaker
# =============================================================================
from core_foundation.resilience.circuit_breaker import (
    DEFAULT_FAILURE_RATE_THRESHOLD,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_HALF_OPEN_MAX_CALLS,
    DEFAULT_RECOVERY_TIMEOUT_SEC,
    DEFAULT_WINDOW_SIZE,
    MAX_BREAKERS,
    MAX_CALLBACKS_PER_BREAKER,
    MAX_STATE_HISTORY,
    BreakerRegistry,
    BreakerSnapshot,
    CallResult,
    CircuitBreaker,
    CircuitState,
    StateChangeCallback,
    StateTransition,
)

# =============================================================================
# retry_mechanism
# =============================================================================
from core_foundation.resilience.retry_mechanism import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_INITIAL_DELAY_SEC,
    DEFAULT_JITTER_RATIO,
    DEFAULT_MAX_DELAY_SEC,
    DEFAULT_MAX_RETRIES,
    MAX_ATTEMPT_HISTORY,
    MAX_CALLBACKS_PER_POLICY,
    MAX_POLICIES,
    AttemptRecord,
    BackoffStrategy,
    RetryEventCallback,
    RetryOutcome,
    RetryPolicy,
    RetryPolicyRegistry,
    RetryResult,
    RetryableChecker,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- circuit_breaker ---
    "CircuitState",
    "CallResult",
    "StateTransition",
    "BreakerSnapshot",
    "StateChangeCallback",
    "CircuitBreaker",
    "BreakerRegistry",
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_RECOVERY_TIMEOUT_SEC",
    "DEFAULT_HALF_OPEN_MAX_CALLS",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_FAILURE_RATE_THRESHOLD",
    "MAX_BREAKERS",
    "MAX_CALLBACKS_PER_BREAKER",
    "MAX_STATE_HISTORY",
    # --- retry_mechanism ---
    "BackoffStrategy",
    "RetryOutcome",
    "AttemptRecord",
    "RetryResult",
    "RetryEventCallback",
    "RetryableChecker",
    "RetryPolicy",
    "RetryPolicyRegistry",
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
