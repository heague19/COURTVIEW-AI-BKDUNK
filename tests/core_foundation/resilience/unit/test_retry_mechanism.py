# -*- coding: utf-8 -*-
"""resilience/retry_mechanism.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

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


@pytest.fixture(autouse=True)
def reset_registry():
    RetryPolicyRegistry.reset()
    yield
    RetryPolicyRegistry.reset()


# =============================================================================
# BackoffStrategy 검증
# =============================================================================

class TestBackoffStrategy:
    def test_member_count(self):
        assert len(BackoffStrategy) == 3

    def test_values(self):
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.FIXED.value == "fixed"

    def test_to_korean(self):
        assert BackoffStrategy.EXPONENTIAL.to_korean() == "지수 백오프"
        assert BackoffStrategy.LINEAR.to_korean() == "선형 백오프"
        assert BackoffStrategy.FIXED.to_korean() == "고정 대기"


# =============================================================================
# RetryOutcome 검증
# =============================================================================

class TestRetryOutcome:
    def test_member_count(self):
        assert len(RetryOutcome) == 3

    def test_values(self):
        assert RetryOutcome.SUCCESS.value == "success"
        assert RetryOutcome.EXHAUSTED.value == "exhausted"
        assert RetryOutcome.NON_RETRYABLE.value == "non_retryable"

    def test_to_korean(self):
        assert RetryOutcome.SUCCESS.to_korean() == "성공"
        assert RetryOutcome.EXHAUSTED.to_korean() == "재시도 소진"
        assert RetryOutcome.NON_RETRYABLE.to_korean() == "재시도 불가"

    def test_is_success(self):
        assert RetryOutcome.SUCCESS.is_success is True
        assert RetryOutcome.EXHAUSTED.is_success is False
        assert RetryOutcome.NON_RETRYABLE.is_success is False


# =============================================================================
# AttemptRecord 검증
# =============================================================================

class TestAttemptRecord:
    def test_slots(self):
        assert hasattr(AttemptRecord, "__slots__")

    def test_creation(self):
        r = AttemptRecord(attempt_number=1, success=True, duration_sec=0.5)
        assert r.attempt_number == 1
        assert r.success is True
        assert r.duration_sec == pytest.approx(0.5)

    def test_repr_success(self):
        r = AttemptRecord(attempt_number=1, success=True, duration_sec=0.123)
        text = repr(r)
        assert "#1" in text
        assert "성공" in text

    def test_repr_failure(self):
        r = AttemptRecord(
            attempt_number=2,
            success=False,
            error_type="RuntimeError",
        )
        text = repr(r)
        assert "#2" in text
        assert "RuntimeError" in text


# =============================================================================
# RetryResult 검증
# =============================================================================

class TestRetryResult:
    def test_slots(self):
        assert hasattr(RetryResult, "__slots__")

    def test_is_success(self):
        r = RetryResult(outcome=RetryOutcome.SUCCESS)
        assert r.is_success is True

    def test_retry_count(self):
        r = RetryResult(outcome=RetryOutcome.SUCCESS, total_attempts=3)
        assert r.retry_count == 2

    def test_retry_count_first_try(self):
        r = RetryResult(outcome=RetryOutcome.SUCCESS, total_attempts=1)
        assert r.retry_count == 0

    def test_repr(self):
        r = RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            total_attempts=4,
            total_duration_sec=5.678,
        )
        text = repr(r)
        assert "exhausted" in text
        assert "attempts=4" in text


# =============================================================================
# RetryPolicy 기본
# =============================================================================

class TestRetryPolicyBasic:
    def test_creation(self):
        p = RetryPolicy("test")
        assert p.name == "test"
        assert p.max_retries == DEFAULT_MAX_RETRIES
        assert p.backoff == BackoffStrategy.EXPONENTIAL

    def test_success_first_try(self):
        p = RetryPolicy("test", max_retries=3, initial_delay_sec=0.0)
        result = p.execute(lambda: 42)

        assert result.is_success is True
        assert result.value == 42
        assert result.total_attempts == 1
        assert result.retry_count == 0

    def test_success_after_retries(self):
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("일시적 실패")
            return "성공"

        p = RetryPolicy(
            "test",
            max_retries=5,
            initial_delay_sec=0.001,
            jitter_ratio=0.0,
        )
        result = p.execute(flaky)

        assert result.is_success is True
        assert result.value == "성공"
        assert result.total_attempts == 3
        assert result.retry_count == 2

    def test_exhausted(self):
        p = RetryPolicy(
            "test",
            max_retries=2,
            initial_delay_sec=0.001,
            jitter_ratio=0.0,
        )
        result = p.execute(lambda: (_ for _ in ()).throw(RuntimeError("항상 실패")))

        assert result.outcome == RetryOutcome.EXHAUSTED
        assert result.total_attempts == 3  # 1 + 2 retries
        assert result.last_error is not None

    def test_zero_retries(self):
        p = RetryPolicy("test", max_retries=0)
        result = p.execute(lambda: (_ for _ in ()).throw(RuntimeError("실패")))

        assert result.outcome == RetryOutcome.EXHAUSTED
        assert result.total_attempts == 1


# =============================================================================
# 재시도 불가 예외
# =============================================================================

class TestNonRetryable:
    def test_non_retryable_exception(self):
        """재시도 불가 예외는 즉시 중단."""
        p = RetryPolicy(
            "test",
            max_retries=5,
            initial_delay_sec=0.001,
            retryable_exceptions=[RuntimeError],
        )
        result = p.execute(lambda: (_ for _ in ()).throw(ValueError("타입 오류")))

        assert result.outcome == RetryOutcome.NON_RETRYABLE
        assert result.total_attempts == 1

    def test_retryable_checker(self):
        """커스텀 체커로 재시도 여부 결정."""
        call_count = [0]

        def checker(e: Exception) -> bool:
            # "temporary" 포함 시에만 재시도
            return "temporary" in str(e)

        def failing():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("temporary error")
            raise RuntimeError("permanent error")

        p = RetryPolicy(
            "test",
            max_retries=5,
            initial_delay_sec=0.001,
            retryable_checker=checker,
        )
        result = p.execute(failing)

        assert result.outcome == RetryOutcome.NON_RETRYABLE
        assert result.total_attempts == 2  # 1번 재시도 후 permanent에서 중단


# =============================================================================
# 백오프 전략
# =============================================================================

class TestBackoffStrategies:
    def test_exponential_delay(self):
        p = RetryPolicy(
            "test",
            backoff=BackoffStrategy.EXPONENTIAL,
            initial_delay_sec=1.0,
            backoff_multiplier=2.0,
            jitter_ratio=0.0,
        )
        assert p._calculate_delay(1) == pytest.approx(1.0)
        assert p._calculate_delay(2) == pytest.approx(2.0)
        assert p._calculate_delay(3) == pytest.approx(4.0)

    def test_linear_delay(self):
        p = RetryPolicy(
            "test",
            backoff=BackoffStrategy.LINEAR,
            initial_delay_sec=1.0,
            jitter_ratio=0.0,
        )
        assert p._calculate_delay(1) == pytest.approx(1.0)
        assert p._calculate_delay(2) == pytest.approx(2.0)
        assert p._calculate_delay(3) == pytest.approx(3.0)

    def test_fixed_delay(self):
        p = RetryPolicy(
            "test",
            backoff=BackoffStrategy.FIXED,
            initial_delay_sec=1.0,
            jitter_ratio=0.0,
        )
        assert p._calculate_delay(1) == pytest.approx(1.0)
        assert p._calculate_delay(5) == pytest.approx(1.0)

    def test_max_delay_cap(self):
        p = RetryPolicy(
            "test",
            backoff=BackoffStrategy.EXPONENTIAL,
            initial_delay_sec=10.0,
            max_delay_sec=30.0,
            backoff_multiplier=2.0,
            jitter_ratio=0.0,
        )
        # 10 * 2^3 = 80 → capped to 30
        assert p._calculate_delay(4) == pytest.approx(30.0)

    def test_jitter_adds_variance(self):
        p = RetryPolicy(
            "test",
            backoff=BackoffStrategy.FIXED,
            initial_delay_sec=10.0,
            jitter_ratio=0.5,
        )
        delays = [p._calculate_delay(1) for _ in range(20)]
        # 지터가 적용되면 값이 다양해야 함
        unique_delays = set(round(d, 6) for d in delays)
        assert len(unique_delays) > 1

    def test_parameter_clamping(self):
        p = RetryPolicy(
            "test",
            max_retries=-1,
            initial_delay_sec=-1.0,
            backoff_multiplier=0.5,
            jitter_ratio=2.0,
        )
        assert p._max_retries >= 0
        assert p._initial_delay_sec >= 0.0
        assert p._backoff_multiplier >= 1.0
        assert p._jitter_ratio <= 1.0


# =============================================================================
# 통계
# =============================================================================

class TestStatistics:
    def test_total_executions(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: 1)
        p.execute(lambda: 2)
        assert p.total_executions == 2

    def test_total_successes(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: 1)
        p.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert p.total_successes == 1

    def test_total_exhausted(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert p.total_exhausted == 1

    def test_success_rate(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: 1)
        p.execute(lambda: 1)
        p.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert p.success_rate == pytest.approx(2 / 3)

    def test_success_rate_empty(self):
        p = RetryPolicy("test")
        assert p.success_rate == 0.0


# =============================================================================
# 콜백
# =============================================================================

class TestCallbacks:
    def test_callback_called(self):
        p = RetryPolicy("test", max_retries=1, initial_delay_sec=0.001)
        records: list[AttemptRecord] = []

        p.add_callback(lambda r: records.append(r))

        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("임시 실패")
            return "ok"

        p.execute(flaky)

        assert len(records) == 2
        assert records[0].success is False
        assert records[1].success is True

    def test_callback_exception_isolation(self):
        p = RetryPolicy("test", max_retries=0)

        def bad_cb(r: AttemptRecord):
            raise RuntimeError("콜백 폭발")

        p.add_callback(bad_cb)
        result = p.execute(lambda: 42)
        assert result.is_success is True

    def test_remove_callback(self):
        p = RetryPolicy("test")

        def my_cb(r: AttemptRecord):
            pass

        p.add_callback(my_cb)
        assert p.remove_callback(my_cb) is True
        assert p.remove_callback(my_cb) is False

    def test_max_callbacks(self):
        p = RetryPolicy("test")
        for _ in range(MAX_CALLBACKS_PER_POLICY):
            p.add_callback(lambda r: None)

        assert p.add_callback(lambda r: None) is False


# =============================================================================
# 이력
# =============================================================================

class TestHistory:
    def test_get_history(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: 1)
        p.execute(lambda: 2)

        history = p.get_history()
        assert len(history) == 2
        assert history[0].is_success is True

    def test_history_defensive_copy(self):
        p = RetryPolicy("test", max_retries=0)
        p.execute(lambda: 1)

        h1 = p.get_history()
        h1.append(None)  # type: ignore
        h2 = p.get_history()
        assert len(h2) == 1

    def test_attempt_details(self):
        p = RetryPolicy(
            "test",
            max_retries=1,
            initial_delay_sec=0.001,
            jitter_ratio=0.0,
        )

        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("실패")
            return "ok"

        result = p.execute(flaky)
        assert len(result.attempts) == 2

        # 첫 시도
        assert result.attempts[0].attempt_number == 1
        assert result.attempts[0].success is False
        assert result.attempts[0].error_type == "RuntimeError"
        assert result.attempts[0].delay_before_sec == 0.0  # 첫 시도는 대기 없음

        # 두 번째 시도
        assert result.attempts[1].attempt_number == 2
        assert result.attempts[1].success is True
        assert result.attempts[1].delay_before_sec > 0.0


# =============================================================================
# RetryPolicyRegistry Singleton
# =============================================================================

class TestRetryPolicyRegistrySingleton:
    def test_get_instance(self):
        r1 = RetryPolicyRegistry.get_instance()
        r2 = RetryPolicyRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = RetryPolicyRegistry.get_instance()
        RetryPolicyRegistry.reset()
        r2 = RetryPolicyRegistry.get_instance()
        assert r1 is not r2


# =============================================================================
# RetryPolicyRegistry 관리
# =============================================================================

class TestRetryPolicyRegistryManagement:
    def test_get_or_create(self):
        reg = RetryPolicyRegistry.get_instance()
        p = reg.get_or_create("gpu")
        assert p is not None
        assert p.name == "gpu"
        assert reg.policy_count == 1

    def test_get_or_create_returns_existing(self):
        reg = RetryPolicyRegistry.get_instance()
        p1 = reg.get_or_create("gpu")
        p2 = reg.get_or_create("gpu")
        assert p1 is p2

    def test_get_or_create_max_limit(self):
        reg = RetryPolicyRegistry.get_instance()
        for i in range(MAX_POLICIES):
            reg.get_or_create(f"p_{i}")

        result = reg.get_or_create("overflow")
        assert result is None

    def test_get(self):
        reg = RetryPolicyRegistry.get_instance()
        reg.get_or_create("test")
        assert reg.get("test") is not None
        assert reg.get("missing") is None

    def test_remove(self):
        reg = RetryPolicyRegistry.get_instance()
        reg.get_or_create("tmp")
        assert reg.remove("tmp") is True
        assert reg.policy_count == 0

    def test_remove_nonexistent(self):
        reg = RetryPolicyRegistry.get_instance()
        assert reg.remove("missing") is False

    def test_has(self):
        reg = RetryPolicyRegistry.get_instance()
        reg.get_or_create("test")
        assert reg.has("test") is True
        assert reg.has("missing") is False

    def test_policy_names(self):
        reg = RetryPolicyRegistry.get_instance()
        reg.get_or_create("a")
        reg.get_or_create("b")
        names = reg.policy_names
        assert "a" in names and "b" in names

    def test_clear(self):
        reg = RetryPolicyRegistry.get_instance()
        reg.get_or_create("a")
        reg.get_or_create("b")
        count = reg.clear()
        assert count == 2
        assert reg.policy_count == 0


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_execute(self):
        p = RetryPolicy("test", max_retries=1, initial_delay_sec=0.001)
        errors: list[Exception] = []

        def execute_many():
            try:
                for _ in range(10):
                    p.execute(lambda: 42)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=execute_many)
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert p.total_executions == 50


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_policy_repr(self):
        p = RetryPolicy("test")
        text = repr(p)
        assert "test" in text
        assert "max_retries=" in text
        assert "backoff=" in text

    def test_registry_repr(self):
        reg = RetryPolicyRegistry.get_instance()
        text = repr(reg)
        assert "policies=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_initial_delay(self):
        assert DEFAULT_INITIAL_DELAY_SEC == 1.0

    def test_default_max_delay(self):
        assert DEFAULT_MAX_DELAY_SEC == 60.0

    def test_default_backoff_multiplier(self):
        assert DEFAULT_BACKOFF_MULTIPLIER == 2.0

    def test_default_jitter_ratio(self):
        assert DEFAULT_JITTER_RATIO == 0.1

    def test_max_policies(self):
        assert MAX_POLICIES == 50

    def test_max_attempt_history(self):
        assert MAX_ATTEMPT_HISTORY == 100

    def test_max_callbacks(self):
        assert MAX_CALLBACKS_PER_POLICY == 20


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.resilience.retry_mechanism as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.resilience.retry_mechanism as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.resilience.retry_mechanism as mod
        assert mod.__version__ == "1.0.0"
