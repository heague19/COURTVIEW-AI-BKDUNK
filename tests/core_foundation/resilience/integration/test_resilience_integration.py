# -*- coding: utf-8 -*-
"""
COURTVIEW - resilience 모듈 통합 테스트

12개 카테고리, 80개 테스트

검증 범위:
    [1]  __init__.py 임포트 무결성 (circuit_breaker, retry_mechanism)
    [2]  __all__ 전체 Export 검증
    [3]  Enum 상호 호환성 / 교차 참조
    [4]  CircuitBreaker 독립 워크플로우
    [5]  RetryMechanism 독립 워크플로우
    [6]  CircuitBreakerRegistry 워크플로우
    [7]  RetryMechanism 레지스트리 워크플로우
    [8]  CircuitBreaker + RetryMechanism 연동 (재시도 + 서킷 보호)
    [9]  데코레이터 연동 (@circuit_protected + @retry)
    [10] 폴백 + 서킷 상태 전이 시나리오
    [11] 전체 파이프라인 (외부 서비스 장애 시뮬레이션)
    [12] 싱글톤 격리 / 스레드 안전성 / 리셋

실행:
    python tests/core_foundation/resilience/integration/test_resilience_integration.py
"""

from __future__ import annotations

import io
import sys
import threading
import time
from pathlib import Path
from typing import List

# ============================================================
# 프로젝트 루트 + 인코딩
# ============================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ============================================================
# 모듈 임포트 (실제 의존성 사용)
# ============================================================
from core_foundation.config.loader import ConfigLoader
from shared.exceptions.base_exception import RetryableException
from shared.exceptions.infrastructure_exceptions import (
    CircuitBreakerOpenException,
    TimeoutException as InfraTimeoutException,
)

import core_foundation.resilience as resilience_mod
from core_foundation.resilience import (
    # Enum
    CircuitState,
    FailureType,
    BackoffStrategy,
    RetryOutcome,
    # 상수
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_SUCCESS_THRESHOLD,
    DEFAULT_OPEN_TIMEOUT,
    DEFAULT_HALF_OPEN_MAX_REQUESTS,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_MINIMUM_REQUESTS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_EXPONENTIAL_BASE,
    DEFAULT_JITTER_FACTOR,
    # 데이터 클래스
    CircuitBreakerConfig,
    CircuitBreakerStats,
    RequestRecord,
    StateChangeEvent,
    RetryConfig,
    RetryAttempt,
    RetryResult,
    # 메인 클래스
    CircuitBreaker,
    CircuitBreakerRegistry,
    RetryMechanism,
    # 데코레이터
    circuit_protected,
    retry,
    async_retry,
    # 함수
    get_circuit_breaker,
    get_all_circuit_status,
    calculate_backoff,
    create_retry_mechanism,
    get_retry_mechanism,
    register_retry_mechanism,
    # 유틸리티
    _get_circuit_registry,
    _reset_circuit_registry,
    _reset_retry_registry,
)


# ============================================================
# TestResult
# ============================================================
class TestResult:
    """테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str = "") -> None:
        self.failed += 1
        self.failures.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> None:
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"통합 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"통합 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)


# ============================================================
# 헬퍼 함수
# ============================================================
class _SimpleConfigLoader:
    """통합테스트용 경량 ConfigLoader 스텁 (실제 파일 로드 불필요)."""

    def get(self, key: str, default=None) -> object:
        return default


_test_config_loader = _SimpleConfigLoader()


def _make_cb(
    name: str = "test_cb",
    failure_threshold: int = 3,
    success_threshold: int = 2,
    open_timeout: float = 0.1,
    minimum_requests: int = 3,
    **kwargs,
) -> CircuitBreaker:
    """테스트용 CircuitBreaker 생성."""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        open_timeout=open_timeout,
        minimum_requests=minimum_requests,
        **kwargs,
    )
    return CircuitBreaker(name=name, config=config, config_loader=_test_config_loader)


def _make_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.001,
    max_delay: float = 0.01,
    jitter_enabled: bool = False,
    **kwargs,
) -> RetryMechanism:
    """테스트용 RetryMechanism 생성."""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        jitter_enabled=jitter_enabled,
        retryable_exceptions=(ConnectionError, TimeoutError, RetryableException),
        log_retries=False,
        **kwargs,
    )
    return RetryMechanism(config=config, name="test_retry")


# =============================================================================
# [1] __init__.py 임포트 무결성 (8개)
# =============================================================================
def test_import_integrity(result: TestResult) -> None:
    """__init__.py에서 모든 서브모듈 임포트가 정상적으로 동작하는지 검증."""
    print("\n[1] __init__.py 임포트 무결성")

    # 1-1. 패키지 임포트
    try:
        assert resilience_mod is not None
        result.ok("1-1 core_foundation.resilience 패키지 임포트")
    except Exception as e:
        result.fail("1-1 패키지 임포트", str(e))
        return

    # 1-2. circuit_breaker 심볼
    try:
        from core_foundation.resilience import (
            CircuitState, FailureType,
            DEFAULT_FAILURE_THRESHOLD, DEFAULT_SUCCESS_THRESHOLD,
            DEFAULT_OPEN_TIMEOUT, DEFAULT_HALF_OPEN_MAX_REQUESTS,
            DEFAULT_WINDOW_SIZE, DEFAULT_MINIMUM_REQUESTS,
            CircuitBreakerConfig, CircuitBreakerStats,
            RequestRecord, StateChangeEvent,
            CircuitBreaker, CircuitBreakerRegistry,
            circuit_protected, get_circuit_breaker, get_all_circuit_status,
            _get_circuit_registry, _reset_circuit_registry,
        )
        assert CircuitBreaker is not None
        result.ok("1-2 circuit_breaker 심볼 (19개)")
    except ImportError as e:
        result.fail("1-2 circuit_breaker 임포트", str(e))

    # 1-3. retry_mechanism 심볼
    try:
        from core_foundation.resilience import (
            BackoffStrategy, RetryOutcome,
            DEFAULT_MAX_ATTEMPTS, DEFAULT_INITIAL_DELAY,
            DEFAULT_MAX_DELAY, DEFAULT_EXPONENTIAL_BASE, DEFAULT_JITTER_FACTOR,
            RetryConfig, RetryAttempt, RetryResult,
            RetryMechanism, retry, async_retry,
            calculate_backoff, create_retry_mechanism,
            get_retry_mechanism, register_retry_mechanism,
            _reset_retry_registry,
        )
        assert RetryMechanism is not None
        result.ok("1-3 retry_mechanism 심볼 (18개)")
    except ImportError as e:
        result.fail("1-3 retry_mechanism 임포트", str(e))

    # 1-4. __version__ 존재
    try:
        assert hasattr(resilience_mod, "__version__")
        assert resilience_mod.__version__ == "1.0.0"
        result.ok("1-4 __version__ == '1.0.0'")
    except Exception as e:
        result.fail("1-4 __version__", str(e))

    # 1-5. 순환 참조 없음 (reload)
    try:
        import importlib
        importlib.reload(sys.modules["core_foundation.resilience"])
        result.ok("1-5 순환 참조 없음 (reload 성공)")
    except Exception as e:
        result.fail("1-5 순환 참조", str(e))

    # 1-6. 서브모듈 직접 임포트
    try:
        import core_foundation.resilience.circuit_breaker
        import core_foundation.resilience.retry_mechanism
        result.ok("1-6 서브모듈 직접 임포트 (2개)")
    except ImportError as e:
        result.fail("1-6 서브모듈 직접", str(e))

    # 1-7. 상수 값 검증
    try:
        assert DEFAULT_FAILURE_THRESHOLD == 5
        assert DEFAULT_SUCCESS_THRESHOLD == 3
        assert DEFAULT_OPEN_TIMEOUT == 30.0
        assert DEFAULT_MAX_ATTEMPTS == 3
        assert DEFAULT_INITIAL_DELAY == 1.0
        result.ok("1-7 상수 기본값 검증")
    except AssertionError as e:
        result.fail("1-7 상수 값", str(e))

    # 1-8. _get_circuit_registry / _reset_circuit_registry 존재
    try:
        assert callable(_get_circuit_registry)
        assert callable(_reset_circuit_registry)
        assert callable(_reset_retry_registry)
        result.ok("1-8 유틸리티 함수 존재 (3개)")
    except Exception as e:
        result.fail("1-8 유틸리티", str(e))


# =============================================================================
# [2] __all__ 전체 Export 검증 (6개)
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__init__.py __all__ 전체 Export 검증."""
    print("\n[2] __all__ Export 검증")

    # 2-1. __all__ 존재
    try:
        assert hasattr(resilience_mod, "__all__")
        result.ok("2-1 __all__ 존재")
    except Exception as e:
        result.fail("2-1 __all__", str(e))

    # 2-2. __all__ 개수 = 서브모듈 합
    try:
        total = len(resilience_mod.__all__)
        from core_foundation.resilience.circuit_breaker import __all__ as cb_all
        from core_foundation.resilience.retry_mechanism import __all__ as rm_all
        expected = len(cb_all) + len(rm_all)
        assert total == expected, f"__init__.__all__={total}, 서브합={expected}"
        result.ok(f"2-2 __all__ 개수 일치 ({total}개)")
    except Exception as e:
        result.fail("2-2 __all__ 개수", str(e))

    # 2-3. 모든 심볼 접근 가능
    try:
        missing = [n for n in resilience_mod.__all__ if not hasattr(resilience_mod, n)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-3 __all__ 모든 심볼 접근 가능 ({len(resilience_mod.__all__)}개)")
    except Exception as e:
        result.fail("2-3 심볼 접근", str(e))

    # 2-4. circuit_breaker 핵심 심볼
    try:
        required = ["CircuitBreaker", "CircuitBreakerRegistry", "CircuitState", "circuit_protected"]
        for sym in required:
            assert sym in resilience_mod.__all__, f"'{sym}' 누락"
        result.ok("2-4 circuit_breaker 핵심 심볼 포함")
    except Exception as e:
        result.fail("2-4 CB 심볼", str(e))

    # 2-5. retry_mechanism 핵심 심볼
    try:
        required = ["RetryMechanism", "RetryConfig", "BackoffStrategy", "retry"]
        for sym in required:
            assert sym in resilience_mod.__all__, f"'{sym}' 누락"
        result.ok("2-5 retry_mechanism 핵심 심볼 포함")
    except Exception as e:
        result.fail("2-5 RM 심볼", str(e))

    # 2-6. 중복 없음
    try:
        all_list = resilience_mod.__all__
        assert len(all_list) == len(set(all_list)), \
            f"중복: {[x for x in all_list if all_list.count(x) > 1]}"
        result.ok("2-6 __all__ 중복 없음")
    except Exception as e:
        result.fail("2-6 중복", str(e))


# =============================================================================
# [3] Enum 상호 호환성 / 교차 참조 (6개)
# =============================================================================
def test_enum_cross_reference(result: TestResult) -> None:
    """서로 다른 모듈의 Enum이 독립적이고 충돌 없이 사용 가능한지 검증."""
    print("\n[3] Enum 상호 호환성")

    # 3-1. 모든 Enum 타입 독립
    try:
        enums = [CircuitState, FailureType, BackoffStrategy, RetryOutcome]
        for i in range(len(enums)):
            for j in range(i + 1, len(enums)):
                assert enums[i] is not enums[j]
        result.ok(f"3-1 Enum 타입 독립성 ({len(enums)}개)")
    except Exception as e:
        result.fail("3-1 Enum 독립성", str(e))

    # 3-2. CircuitState 멤버 검증
    try:
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
        assert CircuitState.CLOSED.is_allowing_requests is True
        assert CircuitState.OPEN.is_allowing_requests is False
        result.ok("3-2 CircuitState 멤버 + is_allowing_requests")
    except Exception as e:
        result.fail("3-2 CircuitState", str(e))

    # 3-3. BackoffStrategy 멤버 검증
    try:
        members = list(BackoffStrategy)
        assert len(members) == 4  # CONSTANT, LINEAR, EXPONENTIAL, DECORRELATED_JITTER
        for m in members:
            assert hasattr(m, "korean_label")
        result.ok("3-3 BackoffStrategy 4개 + korean_label")
    except Exception as e:
        result.fail("3-3 BackoffStrategy", str(e))

    # 3-4. RetryOutcome 멤버 검증
    try:
        outcomes = list(RetryOutcome)
        assert len(outcomes) == 5  # SUCCESS, EXHAUSTED, NON_RETRYABLE, TIMEOUT, CANCELLED
        result.ok("3-4 RetryOutcome 5개 멤버")
    except Exception as e:
        result.fail("3-4 RetryOutcome", str(e))

    # 3-5. FailureType 멤버 검증
    try:
        ftypes = list(FailureType)
        assert len(ftypes) == 4  # EXCEPTION, TIMEOUT, ERROR_RESPONSE, REJECTION
        assert FailureType.EXCEPTION.value == "exception"
        assert FailureType.TIMEOUT.value == "timeout"
        result.ok("3-5 FailureType 4개 멤버")
    except Exception as e:
        result.fail("3-5 FailureType", str(e))

    # 3-6. Enum 값 타입 일관성
    try:
        # CircuitState, FailureType → str
        for member in CircuitState:
            assert isinstance(member.value, str)
        for member in FailureType:
            assert isinstance(member.value, str)
        # BackoffStrategy, RetryOutcome → int(auto)
        for member in BackoffStrategy:
            assert isinstance(member.value, int)
        for member in RetryOutcome:
            assert isinstance(member.value, int)
        result.ok("3-6 Enum 값 타입 일관성 (str 2개 + int 2개)")
    except Exception as e:
        result.fail("3-6 Enum 값 타입", str(e))


# =============================================================================
# [4] CircuitBreaker 독립 워크플로우 (7개)
# =============================================================================
def test_circuit_breaker_workflow(result: TestResult) -> None:
    """CircuitBreaker 생성 -> 성공/실패 -> 상태전이 -> 리셋."""
    print("\n[4] CircuitBreaker 독립 워크플로우")

    _reset_circuit_registry()

    # 4-1. 기본 생성
    try:
        cb = _make_cb("workflow_cb")
        assert cb.name == "workflow_cb"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        result.ok("4-1 CB 생성 + CLOSED 상태")
    except Exception as e:
        result.fail("4-1 생성", str(e))

    # 4-2. 성공 기록
    try:
        cb = _make_cb("success_cb")
        cb.record_success(duration_ms=5.0)
        cb.record_success(duration_ms=3.0)
        stats = cb.stats
        assert stats.total_successes == 2
        assert stats.total_failures == 0
        assert stats.is_healthy is True
        result.ok("4-2 성공 기록 (2회)")
    except Exception as e:
        result.fail("4-2 성공 기록", str(e))

    # 4-3. 실패 임계값 -> OPEN 전환
    try:
        cb = _make_cb("fail_cb", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ValueError("err"))
        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True
        result.ok("4-3 실패 3회 -> OPEN 전환")
    except Exception as e:
        result.fail("4-3 OPEN 전환", str(e))

    # 4-4. OPEN -> HALF_OPEN (timeout 경과)
    try:
        cb = _make_cb("half_cb", failure_threshold=3, minimum_requests=3, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ValueError("err"))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        state = cb.state  # 자동 전환 트리거
        assert state == CircuitState.HALF_OPEN
        result.ok("4-4 OPEN -> HALF_OPEN (timeout 경과)")
    except Exception as e:
        result.fail("4-4 HALF_OPEN 전환", str(e))

    # 4-5. HALF_OPEN -> CLOSED (성공 임계)
    try:
        cb = _make_cb("recover_cb", failure_threshold=3, minimum_requests=3,
                       success_threshold=2, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ValueError("err"))
        time.sleep(0.1)
        _ = cb.state  # HALF_OPEN 트리거
        cb.record_success(1.0)
        cb.record_success(1.0)
        assert cb.state == CircuitState.CLOSED
        result.ok("4-5 HALF_OPEN -> CLOSED (성공 2회)")
    except Exception as e:
        result.fail("4-5 복구", str(e))

    # 4-6. execute() 성공
    try:
        cb = _make_cb("exec_cb")
        val = cb.execute(lambda: 42)
        assert val == 42
        assert cb.stats.total_successes >= 1
        result.ok("4-6 execute() 성공")
    except Exception as e:
        result.fail("4-6 execute 성공", str(e))

    # 4-7. get_status()
    try:
        cb = _make_cb("status_cb")
        status = cb.get_status()
        assert "name" in status
        assert "state" in status
        assert "config" in status
        assert "stats" in status
        assert status["name"] == "status_cb"
        assert status["state"] == "closed"
        result.ok("4-7 get_status() 딕셔너리")
    except Exception as e:
        result.fail("4-7 get_status", str(e))


# =============================================================================
# [5] RetryMechanism 독립 워크플로우 (8개)
# =============================================================================
def test_retry_mechanism_workflow(result: TestResult) -> None:
    """RetryMechanism 생성 -> 실행 -> 재시도 -> 결과."""
    print("\n[5] RetryMechanism 독립 워크플로우")

    # 5-1. 즉시 성공
    try:
        rm = _make_retry()
        val = rm.execute(lambda: "ok")
        assert val == "ok"
        result.ok("5-1 즉시 성공")
    except Exception as e:
        result.fail("5-1 즉시 성공", str(e))

    # 5-2. 재시도 후 성공
    try:
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "recovered"

        rm = _make_retry(max_attempts=5)
        val = rm.execute(flaky)
        assert val == "recovered"
        assert call_count[0] == 3
        result.ok("5-2 재시도 후 성공 (3번째 시도)")
    except Exception as e:
        result.fail("5-2 재시도 성공", str(e))

    # 5-3. 재시도 소진
    try:
        rm = _make_retry(max_attempts=3)

        def always_fail():
            raise ConnectionError("always")

        try:
            rm.execute(always_fail)
            result.fail("5-3 재시도 소진", "예외 미발생")
        except ConnectionError:
            result.ok("5-3 재시도 소진 -> 예외 발생")
    except Exception as e:
        result.fail("5-3 재시도 소진", str(e))

    # 5-4. execute_with_result
    try:
        rm = _make_retry(max_attempts=2)
        rr = rm.execute_with_result(lambda: 42)
        assert isinstance(rr, RetryResult)
        assert rr.success is True
        assert rr.outcome == RetryOutcome.SUCCESS
        assert rr.value == 42
        assert rr.total_attempts == 1
        result.ok("5-4 execute_with_result (성공)")
    except Exception as e:
        result.fail("5-4 execute_with_result", str(e))

    # 5-5. 재시도 불가 예외
    try:
        rm = _make_retry(max_attempts=5)

        def non_retryable():
            raise ValueError("not retryable")

        rr = rm.execute_with_result(non_retryable)
        assert rr.success is False
        assert rr.outcome == RetryOutcome.NON_RETRYABLE
        assert rr.total_attempts == 1
        result.ok("5-5 재시도 불가 예외 -> 1회만 시도")
    except Exception as e:
        result.fail("5-5 재시도 불가", str(e))

    # 5-6. 백오프 전략별 계산
    try:
        # CONSTANT
        d1 = calculate_backoff(1, BackoffStrategy.CONSTANT, 1.0, 30.0, jitter_enabled=False)
        d2 = calculate_backoff(5, BackoffStrategy.CONSTANT, 1.0, 30.0, jitter_enabled=False)
        assert d1 == d2 == 1.0

        # EXPONENTIAL
        d1 = calculate_backoff(1, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, jitter_enabled=False)
        d2 = calculate_backoff(2, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, jitter_enabled=False)
        d3 = calculate_backoff(3, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, jitter_enabled=False)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0

        # LINEAR
        d1 = calculate_backoff(1, BackoffStrategy.LINEAR, 1.0, 30.0, jitter_enabled=False)
        d2 = calculate_backoff(3, BackoffStrategy.LINEAR, 1.0, 30.0, jitter_enabled=False)
        assert d1 == 1.0
        assert d2 == 3.0
        result.ok("5-6 백오프 전략별 계산 (CONSTANT/EXPONENTIAL/LINEAR)")
    except Exception as e:
        result.fail("5-6 백오프 계산", str(e))

    # 5-7. RetryResult.to_dict()
    try:
        rm = _make_retry()
        rr = rm.execute_with_result(lambda: "val")
        d = rr.to_dict()
        assert "outcome" in d
        assert "success" in d
        assert "total_attempts" in d
        assert "attempts" in d
        assert d["outcome"] == "SUCCESS"
        result.ok("5-7 RetryResult.to_dict()")
    except Exception as e:
        result.fail("5-7 to_dict", str(e))

    # 5-8. 콜백 실행
    try:
        retry_calls = []
        success_calls = []

        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            retryable_exceptions=(ConnectionError,),
            on_retry=lambda attempt, exc, delay: retry_calls.append(attempt),
            on_success=lambda attempt, duration: success_calls.append(attempt),
            log_retries=False,
        )
        rm = RetryMechanism(config=config, name="cb_test")
        call_count = [0]

        def flaky2():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("fail")
            return "ok"

        rm.execute(flaky2)
        assert len(retry_calls) == 1
        assert len(success_calls) == 1
        result.ok("5-8 on_retry/on_success 콜백")
    except Exception as e:
        result.fail("5-8 콜백", str(e))


# =============================================================================
# [6] CircuitBreakerRegistry 워크플로우 (6개)
# =============================================================================
def test_circuit_registry_workflow(result: TestResult) -> None:
    """CircuitBreakerRegistry 등록 -> 조회 -> 상태 -> 리셋."""
    print("\n[6] CircuitBreakerRegistry 워크플로우")

    _reset_circuit_registry()

    config = CircuitBreakerConfig(failure_threshold=3, minimum_requests=3, open_timeout=0.1)
    registry = CircuitBreakerRegistry(config_loader=_test_config_loader)

    # 6-1. get_or_create
    try:
        cb1 = registry.get_or_create("service_a", config=config)
        cb2 = registry.get_or_create("service_b", config=config)
        assert cb1.name == "service_a"
        assert cb2.name == "service_b"
        assert cb1 is not cb2
        result.ok("6-1 get_or_create (2개)")
    except Exception as e:
        result.fail("6-1 get_or_create", str(e))

    # 6-2. 같은 이름 -> 동일 인스턴스
    try:
        cb1_again = registry.get_or_create("service_a")
        assert cb1_again is cb1
        result.ok("6-2 동일 이름 -> 동일 인스턴스")
    except Exception as e:
        result.fail("6-2 동일 인스턴스", str(e))

    # 6-3. get
    try:
        found = registry.get("service_a")
        assert found is cb1
        not_found = registry.get("nonexistent")
        assert not_found is None
        result.ok("6-3 get (존재/미존재)")
    except Exception as e:
        result.fail("6-3 get", str(e))

    # 6-4. list_all
    try:
        names = registry.list_all()
        assert "service_a" in names
        assert "service_b" in names
        assert len(names) == 2
        result.ok("6-4 list_all (2개)")
    except Exception as e:
        result.fail("6-4 list_all", str(e))

    # 6-5. get_all_status
    try:
        statuses = registry.get_all_status()
        assert len(statuses) == 2
        assert "service_a" in statuses
        assert statuses["service_a"]["state"] == "closed"
        result.ok("6-5 get_all_status (2개)")
    except Exception as e:
        result.fail("6-5 get_all_status", str(e))

    # 6-6. reset_all
    try:
        # service_a를 OPEN으로 만들기
        for _ in range(3):
            cb1.record_failure(exception=ValueError("err"))
        assert cb1.state == CircuitState.OPEN
        registry.reset_all()
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED
        result.ok("6-6 reset_all -> 모두 CLOSED")
    except Exception as e:
        result.fail("6-6 reset_all", str(e))


# =============================================================================
# [7] RetryMechanism 레지스트리 워크플로우 (5개)
# =============================================================================
def test_retry_registry_workflow(result: TestResult) -> None:
    """전역 RetryMechanism 레지스트리 등록/조회."""
    print("\n[7] RetryMechanism 레지스트리 워크플로우")

    _reset_retry_registry()

    # 7-1. register + get
    try:
        rm = _make_retry(max_attempts=5)
        register_retry_mechanism("api_calls", rm)
        found = get_retry_mechanism("api_calls")
        assert found is rm
        result.ok("7-1 register + get")
    except Exception as e:
        result.fail("7-1 register/get", str(e))

    # 7-2. 미등록 조회 -> None
    try:
        found = get_retry_mechanism("nonexistent")
        assert found is None
        result.ok("7-2 미등록 -> None")
    except Exception as e:
        result.fail("7-2 미등록", str(e))

    # 7-3. create_retry_mechanism
    try:
        rm = create_retry_mechanism(operation="db_query", name="db_retry")
        assert rm.name == "db_retry"
        assert rm.config.max_attempts >= 1
        result.ok("7-3 create_retry_mechanism")
    except Exception as e:
        result.fail("7-3 create", str(e))

    # 7-4. 등록 후 실행
    try:
        _reset_retry_registry()
        rm = _make_retry(max_attempts=3)
        register_retry_mechanism("compute", rm)
        found = get_retry_mechanism("compute")
        val = found.execute(lambda: 100)
        assert val == 100
        result.ok("7-4 등록 후 실행 성공")
    except Exception as e:
        result.fail("7-4 등록 후 실행", str(e))

    # 7-5. 리셋
    try:
        _reset_retry_registry()
        found = get_retry_mechanism("compute")
        assert found is None
        result.ok("7-5 리셋 후 조회 -> None")
    except Exception as e:
        result.fail("7-5 리셋", str(e))


# =============================================================================
# [8] CircuitBreaker + RetryMechanism 연동 (8개)
# =============================================================================
def test_circuit_retry_integration(result: TestResult) -> None:
    """재시도 + 서킷 보호 연동 시나리오."""
    print("\n[8] CircuitBreaker + RetryMechanism 연동")

    # 8-1. 서킷 CLOSED + 재시도 성공
    try:
        cb = _make_cb("integ_1")
        rm = _make_retry(max_attempts=3)
        call_count = [0]

        def op():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("transient")
            return "ok"

        val = rm.execute(lambda: cb.execute(op))
        assert val == "ok"
        assert cb.stats.total_successes >= 1
        result.ok("8-1 CB CLOSED + Retry 성공")
    except Exception as e:
        result.fail("8-1 CB+Retry 성공", str(e))

    # 8-2. 재시도로 서킷 OPEN 유발
    try:
        cb = _make_cb("integ_2", failure_threshold=3, minimum_requests=3)
        rm = _make_retry(max_attempts=5)

        def always_fail():
            return cb.execute(lambda: (_ for _ in ()).throw(ConnectionError("fail")))

        rr = rm.execute_with_result(always_fail)
        assert rr.success is False
        # CB가 3회 실패 후 OPEN -> 이후 시도는 CircuitBreakerOpenException
        assert cb.state == CircuitState.OPEN
        result.ok("8-2 재시도로 CB OPEN 유발")
    except Exception as e:
        result.fail("8-2 CB OPEN 유발", str(e))

    # 8-3. 서킷 OPEN 시 폴백 + 재시도 불요
    try:
        cb = _make_cb("integ_3", failure_threshold=2, minimum_requests=2)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        fallback_val = cb.execute(lambda: "normal", fallback=lambda: "fallback")
        assert fallback_val == "fallback"
        result.ok("8-3 CB OPEN -> 폴백 반환")
    except Exception as e:
        result.fail("8-3 폴백", str(e))

    # 8-4. 상태 변경 콜백 + 재시도
    try:
        events = []
        cb = _make_cb("integ_4", failure_threshold=2, minimum_requests=2, open_timeout=0.05)
        cb.add_state_change_callback(lambda e: events.append(e))

        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        # CLOSED -> OPEN 이벤트
        assert len(events) >= 1
        assert events[-1].current_state == CircuitState.OPEN
        result.ok("8-4 상태 변경 콜백 수신")
    except Exception as e:
        result.fail("8-4 콜백", str(e))

    # 8-5. 서킷 복구 후 재시도 정상화
    try:
        cb = _make_cb("integ_5", failure_threshold=2, minimum_requests=2,
                       open_timeout=0.05, success_threshold=1)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)  # HALF_OPEN 전환 대기
        _ = cb.state  # HALF_OPEN 자동 전환 트리거
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success(1.0)  # HALF_OPEN -> CLOSED
        assert cb.state == CircuitState.CLOSED

        rm = _make_retry(max_attempts=2)
        val = rm.execute(lambda: cb.execute(lambda: "restored"))
        assert val == "restored"
        result.ok("8-5 서킷 복구 후 재시도 정상화")
    except Exception as e:
        result.fail("8-5 복구 후 정상화", str(e))

    # 8-6. RetryConfig.to_dict() + CircuitBreakerConfig.to_dict() 호환
    try:
        rc = RetryConfig(max_attempts=5, backoff_strategy=BackoffStrategy.LINEAR)
        cbc = CircuitBreakerConfig(failure_threshold=10)
        rd = rc.to_dict()
        cbd = cbc.to_dict()
        assert isinstance(rd, dict) and isinstance(cbd, dict)
        assert "max_attempts" in rd
        assert "failure_threshold" in cbd
        result.ok("8-6 Config.to_dict() 호환")
    except Exception as e:
        result.fail("8-6 to_dict", str(e))

    # 8-7. CircuitBreakerStats.to_dict()
    try:
        cb = _make_cb("integ_7")
        cb.record_success(5.0)
        cb.record_failure(exception=ValueError("x"))
        sd = cb.stats.to_dict()
        assert "state" in sd
        assert "failure_rate" in sd
        assert "success_rate" in sd
        assert sd["total_requests"] >= 2
        result.ok("8-7 stats.to_dict() 필드 검증")
    except Exception as e:
        result.fail("8-7 stats dict", str(e))

    # 8-8. StateChangeEvent.to_dict()
    try:
        evt = StateChangeEvent(
            circuit_name="test",
            previous_state=CircuitState.CLOSED,
            current_state=CircuitState.OPEN,
            reason="test",
        )
        ed = evt.to_dict()
        assert ed["circuit_name"] == "test"
        assert ed["previous_state"] == "closed"
        assert ed["current_state"] == "open"
        result.ok("8-8 StateChangeEvent.to_dict()")
    except Exception as e:
        result.fail("8-8 event dict", str(e))


# =============================================================================
# [9] 데코레이터 연동 (6개)
# =============================================================================
def test_decorator_integration(result: TestResult) -> None:
    """@circuit_protected + @retry 데코레이터."""
    print("\n[9] 데코레이터 연동")

    _reset_circuit_registry()
    _reset_retry_registry()

    # 9-1. @retry 데코레이터 성공
    try:
        call_count = [0]

        @retry(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            retryable_exceptions=(ConnectionError,),
            log_retries=False,
        )
        def fetch_data():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("retry")
            return "data"

        val = fetch_data()
        assert val == "data"
        assert call_count[0] == 2
        result.ok("9-1 @retry 데코레이터 성공")
    except Exception as e:
        result.fail("9-1 @retry", str(e))

    # 9-2. @circuit_protected 데코레이터 성공
    try:
        _reset_circuit_registry()
        config = CircuitBreakerConfig(failure_threshold=5, minimum_requests=5)

        @circuit_protected("deco_test", config=config)
        def safe_call():
            return "safe"

        val = safe_call()
        assert val == "safe"
        result.ok("9-2 @circuit_protected 데코레이터 성공")
    except Exception as e:
        result.fail("9-2 @circuit_protected", str(e))

    # 9-3. @circuit_protected 폴백
    try:
        _reset_circuit_registry()
        config = CircuitBreakerConfig(failure_threshold=2, minimum_requests=2, open_timeout=0.1)
        cb = _get_circuit_registry().get_or_create("fb_test", config=config)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))

        @circuit_protected("fb_test", config=config, fallback=lambda: "fb")
        def will_fail():
            return "never"

        val = will_fail()
        assert val == "fb"
        result.ok("9-3 @circuit_protected 폴백")
    except Exception as e:
        result.fail("9-3 폴백", str(e))

    # 9-4. @retry 원본 함수 참조
    try:
        @retry(max_attempts=2, initial_delay=0.001, max_delay=0.01, log_retries=False)
        def original_func():
            return "orig"

        assert hasattr(original_func, "_retry_mechanism")
        assert hasattr(original_func, "_original_func")
        result.ok("9-4 @retry 원본 함수 참조 보존")
    except Exception as e:
        result.fail("9-4 원본 참조", str(e))

    # 9-5. @retry 재시도 소진
    try:
        @retry(
            max_attempts=2,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=(ConnectionError,),
            log_retries=False,
        )
        def always_fails():
            raise ConnectionError("permanent")

        try:
            always_fails()
            result.fail("9-5 소진", "예외 미발생")
        except ConnectionError:
            result.ok("9-5 @retry 소진 -> 예외 전파")
    except Exception as e:
        result.fail("9-5 소진", str(e))

    # 9-6. 중첩 사용 (@retry 내부에 @circuit_protected)
    try:
        _reset_circuit_registry()
        config = CircuitBreakerConfig(failure_threshold=10, minimum_requests=10)
        call_count = [0]

        @retry(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=(ConnectionError,),
            log_retries=False,
        )
        @circuit_protected("nested_test", config=config)
        def nested_call():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("transient")
            return "nested_ok"

        val = nested_call()
        assert val == "nested_ok"
        result.ok("9-6 @retry + @circuit_protected 중첩")
    except Exception as e:
        result.fail("9-6 중첩", str(e))

    _reset_circuit_registry()
    _reset_retry_registry()


# =============================================================================
# [10] 폴백 + 서킷 상태 전이 시나리오 (7개)
# =============================================================================
def test_fallback_state_scenarios(result: TestResult) -> None:
    """다양한 폴백 및 상태 전이 시나리오."""
    print("\n[10] 폴백 + 서킷 상태 전이 시나리오")

    # 10-1. force_open
    try:
        cb = _make_cb("force_1")
        assert cb.state == CircuitState.CLOSED
        cb.force_open("수동 오픈")
        assert cb.state == CircuitState.OPEN
        result.ok("10-1 force_open")
    except Exception as e:
        result.fail("10-1 force_open", str(e))

    # 10-2. force_close
    try:
        cb = _make_cb("force_2", failure_threshold=2, minimum_requests=2)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN
        cb.force_close("수동 클로즈")
        assert cb.state == CircuitState.CLOSED
        result.ok("10-2 force_close")
    except Exception as e:
        result.fail("10-2 force_close", str(e))

    # 10-3. reset 후 통계 초기화
    try:
        cb = _make_cb("reset_1", failure_threshold=2, minimum_requests=2)
        cb.record_success(1.0)
        cb.record_failure(exception=ValueError("x"))
        cb.reset()
        stats = cb.stats
        assert stats.total_requests == 0
        assert stats.total_failures == 0
        assert stats.state == CircuitState.CLOSED
        result.ok("10-3 reset 후 통계 초기화")
    except Exception as e:
        result.fail("10-3 reset", str(e))

    # 10-4. HALF_OPEN에서 실패 -> 다시 OPEN
    try:
        cb = _make_cb("half_fail", failure_threshold=2, minimum_requests=2, open_timeout=0.05)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        time.sleep(0.1)
        _ = cb.state  # HALF_OPEN 트리거
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure(exception=ValueError("c"))
        assert cb.state == CircuitState.OPEN
        result.ok("10-4 HALF_OPEN 실패 -> 다시 OPEN")
    except Exception as e:
        result.fail("10-4 HALF_OPEN 실패", str(e))

    # 10-5. execute OPEN 시 CircuitBreakerOpenException
    try:
        cb = _make_cb("open_exc", failure_threshold=2, minimum_requests=2)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        try:
            cb.execute(lambda: "never")
            result.fail("10-5 OPEN 예외", "예외 미발생")
        except CircuitBreakerOpenException:
            result.ok("10-5 OPEN -> CircuitBreakerOpenException")
    except Exception as e:
        result.fail("10-5 OPEN 예외", str(e))

    # 10-6. 다수 콜백 등록
    try:
        cb = _make_cb("multi_cb", failure_threshold=2, minimum_requests=2)
        events_1, events_2 = [], []
        cb.add_state_change_callback(lambda e: events_1.append(e.current_state))
        cb.add_state_change_callback(lambda e: events_2.append(e.current_state))
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert len(events_1) >= 1
        assert len(events_2) >= 1
        assert events_1[-1] == CircuitState.OPEN
        result.ok("10-6 다수 콜백 동시 수신")
    except Exception as e:
        result.fail("10-6 다수 콜백", str(e))

    # 10-7. 콜백 제거
    try:
        cb = _make_cb("rm_cb")
        events = []
        cb_fn = lambda e: events.append(e)
        cb.add_state_change_callback(cb_fn)
        removed = cb.remove_state_change_callback(cb_fn)
        assert removed is True
        cb.force_open("test")
        assert len(events) == 0  # 콜백 제거 후 이벤트 미수신
        result.ok("10-7 콜백 제거 후 미수신")
    except Exception as e:
        result.fail("10-7 콜백 제거", str(e))


# =============================================================================
# [11] 전체 파이프라인 (외부 서비스 장애 시뮬레이션) (8개)
# =============================================================================
def test_full_pipeline(result: TestResult) -> None:
    """실제 서비스 호출 패턴 시뮬레이션: 재시도 + 서킷 + 복구."""
    print("\n[11] 전체 파이프라인 (외부 서비스 장애 시뮬레이션)")

    _reset_circuit_registry()
    _reset_retry_registry()

    config = CircuitBreakerConfig(
        failure_threshold=3, minimum_requests=3,
        success_threshold=2, open_timeout=0.1,
    )
    registry = CircuitBreakerRegistry(config_loader=_test_config_loader)
    db_circuit = registry.get_or_create("database", config=config)
    api_circuit = registry.get_or_create("external_api", config=config)
    rm = _make_retry(max_attempts=3)

    # 서비스 시뮬레이터
    db_fail_until = [0]
    api_fail_until = [0]

    def db_query(query: str) -> dict:
        if db_fail_until[0] > 0:
            db_fail_until[0] -= 1
            raise ConnectionError("DB connection lost")
        return {"result": query, "rows": 10}

    def api_call(endpoint: str) -> dict:
        if api_fail_until[0] > 0:
            api_fail_until[0] -= 1
            raise TimeoutError("API timeout")
        return {"status": 200, "data": endpoint}

    # 11-1. 정상 상태 (모두 CLOSED)
    try:
        db_result = db_circuit.execute(db_query, "SELECT 1")
        api_result = api_circuit.execute(api_call, "/health")
        assert db_result["rows"] == 10
        assert api_result["status"] == 200
        assert db_circuit.state == CircuitState.CLOSED
        assert api_circuit.state == CircuitState.CLOSED
        result.ok("11-1 정상 상태 (DB + API CLOSED)")
    except Exception as e:
        result.fail("11-1 정상", str(e))

    # 11-2. DB 일시 장애 -> 재시도로 복구
    try:
        db_fail_until[0] = 2  # 2회 실패 후 성공
        db_result = rm.execute(lambda: db_circuit.execute(db_query, "SELECT *"))
        assert db_result["result"] == "SELECT *"
        result.ok("11-2 DB 일시 장애 -> 재시도 복구")
    except Exception as e:
        result.fail("11-2 DB 재시도", str(e))

    # 11-3. API 지속 장애 -> 서킷 OPEN
    try:
        api_circuit.reset()
        api_fail_until[0] = 100  # 지속 실패
        for _ in range(5):
            try:
                api_circuit.execute(api_call, "/data")
            except (TimeoutError, CircuitBreakerOpenException):
                pass
        assert api_circuit.state == CircuitState.OPEN
        result.ok("11-3 API 지속 장애 -> OPEN")
    except Exception as e:
        result.fail("11-3 API OPEN", str(e))

    # 11-4. 서킷 OPEN 시 폴백
    try:
        cached = api_circuit.execute(
            api_call, "/data",
            fallback=lambda *a, **kw: {"status": 200, "data": "cached", "cached": True},
        )
        assert cached["cached"] is True
        result.ok("11-4 OPEN 폴백 -> 캐시 데이터")
    except Exception as e:
        result.fail("11-4 폴백", str(e))

    # 11-5. 전체 상태 조회
    try:
        all_status = registry.get_all_status()
        assert "database" in all_status
        assert "external_api" in all_status
        assert all_status["database"]["state"] == "closed"
        assert all_status["external_api"]["state"] == "open"
        result.ok("11-5 전체 상태 조회")
    except Exception as e:
        result.fail("11-5 상태 조회", str(e))

    # 11-6. API 복구 (HALF_OPEN -> CLOSED)
    try:
        api_fail_until[0] = 0  # 복구
        time.sleep(0.15)  # open_timeout 대기
        _ = api_circuit.state  # HALF_OPEN 트리거
        assert api_circuit.state == CircuitState.HALF_OPEN
        api_circuit.execute(api_call, "/recover1")
        api_circuit.execute(api_call, "/recover2")
        assert api_circuit.state == CircuitState.CLOSED
        result.ok("11-6 API 복구 (HALF_OPEN -> CLOSED)")
    except Exception as e:
        result.fail("11-6 API 복구", str(e))

    # 11-7. 복구 후 정상 운영
    try:
        db_result = db_circuit.execute(db_query, "SELECT final")
        api_result = api_circuit.execute(api_call, "/final")
        assert db_result["result"] == "SELECT final"
        assert api_result["data"] == "/final"
        result.ok("11-7 복구 후 정상 운영")
    except Exception as e:
        result.fail("11-7 정상 운영", str(e))

    # 11-8. 전체 리셋 + 통계 확인
    try:
        db_stats = db_circuit.stats
        api_stats = api_circuit.stats
        assert db_stats.total_requests > 0
        assert api_stats.total_requests > 0
        registry.reset_all()
        assert db_circuit.stats.total_requests == 0
        assert api_circuit.stats.total_requests == 0
        result.ok("11-8 전체 리셋 후 통계 0")
    except Exception as e:
        result.fail("11-8 리셋 통계", str(e))

    _reset_circuit_registry()
    _reset_retry_registry()


# =============================================================================
# [12] 싱글톤 격리 / 스레드 안전성 / 리셋 (9개)
# =============================================================================
def test_singleton_and_threads(result: TestResult) -> None:
    """전역 레지스트리 싱글톤, 스레드 안전성, 리셋."""
    print("\n[12] 싱글톤 격리 / 스레드 안전성")

    _reset_circuit_registry()
    _reset_retry_registry()

    # 12-1. 전역 레지스트리 싱글톤
    try:
        reg1 = _get_circuit_registry()
        reg2 = _get_circuit_registry()
        assert reg1 is reg2
        result.ok("12-1 CB 전역 레지스트리 싱글톤")
    except Exception as e:
        result.fail("12-1 싱글톤", str(e))

    # 12-2. 리셋 후 새 인스턴스
    try:
        reg1 = _get_circuit_registry()
        _reset_circuit_registry()
        reg2 = _get_circuit_registry()
        assert reg1 is not reg2
        result.ok("12-2 CB 리셋 후 새 인스턴스")
    except Exception as e:
        result.fail("12-2 리셋", str(e))

    # 12-3. get_circuit_breaker 전역 함수
    try:
        _reset_circuit_registry()
        config = CircuitBreakerConfig(failure_threshold=5, minimum_requests=5)
        cb = get_circuit_breaker("global_test", config=config)
        cb2 = get_circuit_breaker("global_test")
        assert cb is cb2
        result.ok("12-3 get_circuit_breaker 전역 함수")
    except Exception as e:
        result.fail("12-3 전역 함수", str(e))

    # 12-4. get_all_circuit_status 전역 함수
    try:
        status = get_all_circuit_status()
        assert isinstance(status, dict)
        assert "global_test" in status
        result.ok("12-4 get_all_circuit_status")
    except Exception as e:
        result.fail("12-4 전역 status", str(e))

    # 12-5. 멀티스레드 CB 레지스트리 접근
    try:
        _reset_circuit_registry()
        errors = []
        ids_collected = []
        config = CircuitBreakerConfig(failure_threshold=5, minimum_requests=5)

        def thread_fn():
            try:
                cb = get_circuit_breaker("mt_test", config=config)
                ids_collected.append(id(cb))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=thread_fn) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        assert len(set(ids_collected)) == 1, "동일 CB 인스턴스 아님"
        result.ok("12-5 멀티스레드 CB 레지스트리 (8스레드)")
    except Exception as e:
        result.fail("12-5 멀티스레드 CB", str(e))

    # 12-6. 멀티스레드 CB record_success/failure
    try:
        _reset_circuit_registry()
        config = CircuitBreakerConfig(failure_threshold=100, minimum_requests=100)
        cb = _make_cb("mt_record", failure_threshold=100, minimum_requests=100)
        errors = []

        def record_fn(is_success: bool):
            try:
                for _ in range(50):
                    if is_success:
                        cb.record_success(1.0)
                    else:
                        cb.record_failure(exception=ValueError("x"))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=record_fn, args=(i % 2 == 0,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        stats = cb.stats
        assert stats.total_requests == 400  # 8 * 50
        result.ok(f"12-6 멀티스레드 record (총 {stats.total_requests}건)")
    except Exception as e:
        result.fail("12-6 멀티스레드 record", str(e))

    # 12-7. 멀티스레드 RetryMechanism
    try:
        rm = _make_retry(max_attempts=2)
        errors = []
        results_list = []

        def retry_fn():
            try:
                val = rm.execute(lambda: threading.current_thread().name)
                results_list.append(val)
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=retry_fn, name=f"T-{i}") for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results_list) == 8
        result.ok("12-7 멀티스레드 RetryMechanism (8스레드)")
    except Exception as e:
        result.fail("12-7 멀티스레드 Retry", str(e))

    # 12-8. CB 리셋이 Retry에 영향 없음
    try:
        _reset_circuit_registry()
        rm = _make_retry()
        val = rm.execute(lambda: "still_works")
        assert val == "still_works"
        result.ok("12-8 CB 리셋 -> Retry 무영향")
    except Exception as e:
        result.fail("12-8 격리", str(e))

    # 12-9. 전체 리셋 안전
    try:
        _reset_circuit_registry()
        _reset_retry_registry()
        # 재생성 가능
        reg = _get_circuit_registry()
        assert reg is not None
        rm = _make_retry()
        val = rm.execute(lambda: "ok")
        assert val == "ok"
        result.ok("12-9 전체 리셋 후 재생성 안전")
    except Exception as e:
        result.fail("12-9 전체 리셋", str(e))
    finally:
        _reset_circuit_registry()
        _reset_retry_registry()


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - resilience 모듈 통합 테스트")
    print("=" * 60)

    r = TestResult()

    test_import_integrity(r)              # [1] 8개
    test_all_exports(r)                   # [2] 6개
    test_enum_cross_reference(r)          # [3] 6개
    test_circuit_breaker_workflow(r)       # [4] 7개
    test_retry_mechanism_workflow(r)       # [5] 8개
    test_circuit_registry_workflow(r)      # [6] 6개
    test_retry_registry_workflow(r)        # [7] 5개
    test_circuit_retry_integration(r)     # [8] 8개
    test_decorator_integration(r)         # [9] 6개
    test_fallback_state_scenarios(r)      # [10] 7개
    test_full_pipeline(r)                 # [11] 8개
    test_singleton_and_threads(r)         # [12] 9개

    r.summary()
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
