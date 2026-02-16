# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/resilience/performance
파일: test_retry_mechanism_perf.py
설명: 재시도 메커니즘 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1] BackoffStrategy Enum 연산 성능 (3개)
    [2] RetryConfig 생성 성능 (3개)
    [3] calculate_backoff 함수 성능 (4개)
    [4] RetryMechanism 초기화 성능 (3개)
    [5] execute 성공 처리량 (3개)
    [6] execute 재시도 오버헤드 (3개)
    [7] execute_with_result 성능 (3개)
    [8] 데코레이터 오버헤드 (3개)
    [9] 멀티스레드 동시 접근 (4개)
    [10] 메모리 사용량 (3개)
    [11] 레지스트리 성능 (3개)
    [12] RetryResult / RetryAttempt 직렬화 성능 (3개)
"""

import asyncio
import io
import sys
import time
import threading
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.resilience.retry_mechanism import (
    BackoffStrategy,
    RetryOutcome,
    RetryConfig,
    RetryAttempt,
    RetryResult,
    RetryMechanism,
    retry,
    async_retry,
    calculate_backoff,
    create_retry_mechanism,
    get_retry_mechanism,
    register_retry_mechanism,
    _reset_registry,
    _RetryRegistry,
    _registry,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" | {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n성능 메트릭:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# [1] BackoffStrategy Enum 연산 성능
# =============================================================================
def test_backoff_strategy_perf(result: PerfResult) -> None:
    """BackoffStrategy Enum 연산 성능."""
    print("\n[1] BackoffStrategy Enum 연산 성능")

    # 1-1: 멤버 접근
    try:
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = BackoffStrategy.CONSTANT
            _ = BackoffStrategy.LINEAR
            _ = BackoffStrategy.EXPONENTIAL
            _ = BackoffStrategy.DECORRELATED_JITTER
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 4) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-1: 멤버 접근 (800K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-1: 멤버 접근", str(e))

    # 1-2: korean_label 속성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = BackoffStrategy.CONSTANT.korean_label
            _ = BackoffStrategy.EXPONENTIAL.korean_label
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-2: korean_label (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-2: korean_label", str(e))

    # 1-3: 이름으로 접근
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = BackoffStrategy["EXPONENTIAL"]
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-3: 이름 접근 (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-3: 이름 접근", str(e))


# =============================================================================
# [2] RetryConfig 생성 성능
# =============================================================================
def test_config_creation_perf(result: PerfResult) -> None:
    """RetryConfig 생성 성능."""
    print("\n[2] RetryConfig 생성 성능")

    # 2-1: 기본값 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = RetryConfig()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-1: 기본값 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-1: 기본값 생성", str(e))

    # 2-2: 커스텀 값 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = RetryConfig(
                max_attempts=i % 10 + 1,
                backoff_strategy=BackoffStrategy.LINEAR,
                initial_delay=0.5,
                jitter_enabled=False,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-2: 커스텀 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-2: 커스텀 생성", str(e))

    # 2-3: to_dict 변환
    try:
        config = RetryConfig()
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = config.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-3: to_dict (50K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-3: to_dict", str(e))


# =============================================================================
# [3] calculate_backoff 함수 성능
# =============================================================================
def test_calculate_backoff_perf(result: PerfResult) -> None:
    """calculate_backoff 함수 성능."""
    print("\n[3] calculate_backoff 함수 성능")

    # 3-1: CONSTANT 전략
    try:
        iterations = 100_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = calculate_backoff(i % 10 + 1, BackoffStrategy.CONSTANT, 1.0, 30.0, jitter_enabled=False)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-1: CONSTANT (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-1: CONSTANT", str(e))

    # 3-2: EXPONENTIAL 전략
    try:
        iterations = 100_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = calculate_backoff(i % 10 + 1, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, 2.0, jitter_enabled=False)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-2: EXPONENTIAL (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-2: EXPONENTIAL", str(e))

    # 3-3: EXPONENTIAL + 지터
    try:
        iterations = 100_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = calculate_backoff(i % 10 + 1, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, 2.0, jitter_enabled=True, jitter_factor=0.1)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-3: EXPONENTIAL + 지터 (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-3: EXPONENTIAL 지터", str(e))

    # 3-4: DECORRELATED_JITTER
    try:
        iterations = 100_000
        prev = 1.0
        start = time.perf_counter()
        for _ in range(iterations):
            prev = calculate_backoff(1, BackoffStrategy.DECORRELATED_JITTER, 1.0, 30.0, previous_delay=prev)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-4: DECORRELATED_JITTER (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-4: DECORRELATED", str(e))


# =============================================================================
# [4] RetryMechanism 초기화 성능
# =============================================================================
def test_mechanism_init_perf(result: PerfResult) -> None:
    """RetryMechanism 초기화 성능."""
    print("\n[4] RetryMechanism 초기화 성능")

    # 4-1: 기본 초기화
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = RetryMechanism(name=f"init_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-1: 기본 초기화 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-1: 초기화", str(e))

    # 4-2: 커스텀 설정 초기화
    try:
        iterations = 5_000
        start = time.perf_counter()
        for i in range(iterations):
            config = RetryConfig(max_attempts=5, backoff_strategy=BackoffStrategy.LINEAR)
            _ = RetryMechanism(config=config, name=f"custom_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-2: 커스텀 초기화 (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-2: 커스텀 초기화", str(e))

    # 4-3: 속성 접근
    try:
        rm = RetryMechanism(name="prop_test")
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = rm.name
            _ = rm.config
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-3: 속성 접근 (400K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-3: 속성 접근", str(e))


# =============================================================================
# [5] execute 성공 처리량
# =============================================================================
def test_execute_success_perf(result: PerfResult) -> None:
    """execute 성공 처리량."""
    print("\n[5] execute 성공 처리량")

    # 5-1: noop 함수 실행
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        noop = lambda: 42
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            rm.execute(noop)
        elapsed = (time.perf_counter() - start) * 1000
        overhead = elapsed / iterations * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-1: noop execute (10K)", f"{elapsed:.1f}ms, {overhead:.1f}μs/call, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-1: noop execute", str(e))

    # 5-2: 인수 전달 실행
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            rm.execute(lambda x, y: x + y, i, i + 1)
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-2: 인수 전달 execute (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-2: 인수 전달", str(e))

    # 5-3: 오버헤드 비교 (직접 실행 vs retry 래핑)
    try:
        func = lambda: 42
        iterations = 50_000

        # 직접 실행
        start = time.perf_counter()
        for _ in range(iterations):
            func()
        direct_ms = (time.perf_counter() - start) * 1000

        # retry 래핑 실행
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        start = time.perf_counter()
        for _ in range(iterations):
            rm.execute(func)
        wrapped_ms = (time.perf_counter() - start) * 1000

        overhead_ratio = wrapped_ms / max(direct_ms, 0.001)
        result.ok(
            "5-3: 오버헤드 비교 (50K)",
            f"직접: {direct_ms:.1f}ms, 래핑: {wrapped_ms:.1f}ms, 비율: {overhead_ratio:.1f}x"
        )
    except Exception as e:
        result.fail("5-3: 오버헤드 비교", str(e))


# =============================================================================
# [6] execute 재시도 오버헤드
# =============================================================================
def test_execute_retry_overhead(result: PerfResult) -> None:
    """execute 재시도 오버헤드."""
    print("\n[6] execute 재시도 오버헤드")

    # 6-1: 1회 재시도 후 성공
    try:
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.001,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        iterations = 1_000

        start = time.perf_counter()
        for _ in range(iterations):
            call_count = [0]

            def once_fail():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise ConnectionError("fail")
                return "ok"

            rm.execute(once_fail)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        result.ok("6-1: 1회 재시도 성공 (1K)", f"{elapsed:.1f}ms, {per_op:.2f}ms/op")
    except Exception as e:
        result.fail("6-1: 1회 재시도", str(e))

    # 6-2: 2회 재시도 후 성공
    try:
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.001,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        iterations = 500

        start = time.perf_counter()
        for _ in range(iterations):
            call_count = [0]

            def twice_fail():
                call_count[0] += 1
                if call_count[0] <= 2:
                    raise ConnectionError("fail")
                return "ok"

            rm.execute(twice_fail)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        result.ok("6-2: 2회 재시도 성공 (500)", f"{elapsed:.1f}ms, {per_op:.2f}ms/op")
    except Exception as e:
        result.fail("6-2: 2회 재시도", str(e))

    # 6-3: execute_with_result 오버헤드
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = rm.execute_with_result(lambda: 42)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-3: execute_with_result (5K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("6-3: with_result", str(e))


# =============================================================================
# [7] execute_with_result 성능
# =============================================================================
def test_execute_with_result_perf(result: PerfResult) -> None:
    """execute_with_result 성능."""
    print("\n[7] execute_with_result 성능")

    # 7-1: 성공 결과 생성
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            rr = rm.execute_with_result(lambda: "val")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-1: 성공 결과 생성 (5K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("7-1: 성공 결과", str(e))

    # 7-2: 실패 결과 생성
    try:
        config = RetryConfig(
            max_attempts=2,
            initial_delay=0.001,
            max_delay=0.001,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        iterations = 1_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = rm.execute_with_result(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        result.ok("7-2: 실패 결과 2회 재시도 (1K)", f"{elapsed:.1f}ms, {per_op:.2f}ms/op")
    except Exception as e:
        result.fail("7-2: 실패 결과", str(e))

    # 7-3: to_dict 직렬화
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: "val")
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = rr.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-3: RetryResult.to_dict (50K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("7-3: to_dict", str(e))


# =============================================================================
# [8] 데코레이터 오버헤드
# =============================================================================
def test_decorator_overhead(result: PerfResult) -> None:
    """데코레이터 오버헤드."""
    print("\n[8] 데코레이터 오버헤드")

    # 8-1: @retry 데코레이터 성능
    try:
        @retry(max_attempts=1, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        def decorated():
            return 42

        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            decorated()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-1: @retry 데코레이터 (10K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/call")
    except Exception as e:
        result.fail("8-1: @retry", str(e))

    # 8-2: @async_retry 데코레이터 성능
    try:
        @async_retry(max_attempts=1, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        async def async_decorated():
            return 42

        loop = asyncio.new_event_loop()
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            loop.run_until_complete(async_decorated())
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        loop.close()
        result.ok("8-2: @async_retry 데코레이터 (5K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/call")
    except Exception as e:
        result.fail("8-2: @async_retry", str(e))

    # 8-3: 데코레이터 vs 직접 실행 비교
    try:
        def plain():
            return 42

        @retry(max_attempts=1, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        def wrapped():
            return 42

        iterations = 20_000

        start = time.perf_counter()
        for _ in range(iterations):
            plain()
        plain_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        for _ in range(iterations):
            wrapped()
        wrapped_ms = (time.perf_counter() - start) * 1000

        overhead_ratio = wrapped_ms / max(plain_ms, 0.001)
        result.ok(
            "8-3: 데코레이터 vs 직접 (20K)",
            f"직접: {plain_ms:.1f}ms, 래핑: {wrapped_ms:.1f}ms, 비율: {overhead_ratio:.1f}x"
        )
    except Exception as e:
        result.fail("8-3: 비교", str(e))


# =============================================================================
# [9] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_perf(result: PerfResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[9] 멀티스레드 동시 접근")

    # 9-1: 4스레드 execute
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        ops_per_thread = 2_000
        results_list = []
        errors = []

        def worker():
            try:
                for _ in range(ops_per_thread):
                    val = rm.execute(lambda: 42)
                    results_list.append(val)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-1: 4스레드 execute (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-1: 4스레드 execute", str(e))

    # 9-2: 8스레드 execute
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        ops_per_thread = 1_000
        errors = []

        def worker():
            try:
                for _ in range(ops_per_thread):
                    rm.execute(lambda: 42)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 8
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-2: 8스레드 execute (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-2: 8스레드", str(e))

    # 9-3: 레지스트리 동시 접근
    try:
        _reset_registry()
        errors = []
        ops_per_thread = 500

        def registry_worker(thread_id):
            try:
                for i in range(ops_per_thread):
                    name = f"thread_{thread_id}_svc_{i % 10}"
                    _registry.get_or_create(name)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=registry_worker, args=(i,)) for i in range(8)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        assert len(errors) == 0
        result.ok("9-3: 8스레드 레지스트리 (4K)", f"{elapsed:.1f}ms")
    except Exception as e:
        result.fail("9-3: 레지스트리 동시", str(e))

    # 9-4: calculate_backoff 동시 호출
    try:
        errors = []
        ops_per_thread = 10_000

        def backoff_worker():
            try:
                for i in range(ops_per_thread):
                    _ = calculate_backoff(
                        i % 10 + 1, BackoffStrategy.EXPONENTIAL,
                        1.0, 30.0, 2.0,
                        jitter_enabled=True, jitter_factor=0.1,
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=backoff_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-4: 4스레드 calculate_backoff (40K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-4: backoff 동시", str(e))


# =============================================================================
# [10] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerfResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[10] 메모리 사용량")

    # 10-1: RetryMechanism 인스턴스 메모리
    try:
        tracemalloc.start()
        mechanisms = []
        for i in range(500):
            mechanisms.append(RetryMechanism(name=f"mem_{i}"))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_instance_kb = current / 500 / 1024
        result.ok("10-1: 500개 인스턴스 메모리", f"총: {current/1024:.1f}KB, 인스턴스당: {per_instance_kb:.1f}KB")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-1: 인스턴스 메모리", str(e))

    # 10-2: RetryResult 메모리 (시도 기록 포함)
    try:
        tracemalloc.start()
        config = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.001, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        results = []
        for _ in range(100):
            call_count = [0]

            def flaky():
                call_count[0] += 1
                if call_count[0] < 4:
                    raise ConnectionError("fail")
                return "ok"

            results.append(rm.execute_with_result(flaky))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_result_kb = current / 100 / 1024
        result.ok("10-2: 100개 RetryResult (4시도)", f"총: {current/1024:.1f}KB, 개당: {per_result_kb:.2f}KB")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-2: RetryResult 메모리", str(e))

    # 10-3: RetryConfig 메모리
    try:
        tracemalloc.start()
        configs = [RetryConfig() for _ in range(1_000)]
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_config = current / 1_000
        result.ok("10-3: 1K RetryConfig 메모리", f"총: {current/1024:.1f}KB, 개당: {per_config:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-3: RetryConfig 메모리", str(e))


# =============================================================================
# [11] 레지스트리 성능
# =============================================================================
def test_registry_perf(result: PerfResult) -> None:
    """레지스트리 성능."""
    print("\n[11] 레지스트리 성능")
    _reset_registry()

    # 11-1: get_or_create 새 생성
    try:
        _reset_registry()
        iterations = 1_000
        start = time.perf_counter()
        for i in range(iterations):
            _registry.get_or_create(f"reg_svc_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-1: get_or_create 생성 (1K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("11-1: get_or_create", str(e))

    # 11-2: get_or_create 기존 조회
    try:
        iterations = 50_000
        start = time.perf_counter()
        for i in range(iterations):
            _registry.get_or_create(f"reg_svc_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-2: get_or_create 조회 (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("11-2: 조회", str(e))

    # 11-3: list_all
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = _registry.list_all()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-3: list_all (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("11-3: list_all", str(e))


# =============================================================================
# [12] RetryResult / RetryAttempt 직렬화 성능
# =============================================================================
def test_serialization_perf(result: PerfResult) -> None:
    """RetryResult / RetryAttempt 직렬화 성능."""
    print("\n[12] RetryResult / RetryAttempt 직렬화 성능")

    now = datetime.now(timezone.utc)

    # 12-1: RetryAttempt to_dict
    try:
        attempt = RetryAttempt(
            attempt_number=1,
            start_time=now,
            end_time=now,
            duration_ms=50.0,
            success=True,
        )
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = attempt.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-1: RetryAttempt.to_dict (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-1: attempt to_dict", str(e))

    # 12-2: RetryResult to_dict (시도 포함)
    try:
        rr = RetryResult(
            outcome=RetryOutcome.SUCCESS,
            success=True,
            value="val",
            total_attempts=3,
            total_duration_ms=150.0,
            total_delay_ms=30.0,
        )
        for i in range(3):
            rr.attempts.append(RetryAttempt(
                attempt_number=i + 1,
                start_time=now,
                end_time=now,
                duration_ms=50.0,
                success=(i == 2),
                exception=ConnectionError("fail") if i < 2 else None,
            ))
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = rr.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-2: RetryResult.to_dict 3시도 (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-2: result to_dict", str(e))

    # 12-3: RetryConfig to_dict
    try:
        config = RetryConfig()
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = config.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-3: RetryConfig.to_dict (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-3: config to_dict", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """성능 테스트 실행."""
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("RetryMechanism 성능 테스트")
    print("=" * 60)

    r = PerfResult()

    test_backoff_strategy_perf(r)
    test_config_creation_perf(r)
    test_calculate_backoff_perf(r)
    test_mechanism_init_perf(r)
    test_execute_success_perf(r)
    test_execute_retry_overhead(r)
    test_execute_with_result_perf(r)
    test_decorator_overhead(r)
    test_multithread_perf(r)
    test_memory_usage(r)
    test_registry_perf(r)
    test_serialization_perf(r)

    r.summary()

    _reset_registry()


if __name__ == "__main__":
    main()
