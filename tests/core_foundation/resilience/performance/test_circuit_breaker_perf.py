# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/resilience/performance
파일: test_circuit_breaker_perf.py
설명: 서킷 브레이커 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1] CircuitState Enum 연산 성능 (3개)
    [2] CircuitBreakerConfig 생성 성능 (3개)
    [3] CircuitBreakerStats 연산 성능 (3개)
    [4] CircuitBreaker 초기화 성능 (3개)
    [5] allow_request 처리량 (3개)
    [6] record_success / record_failure 처리량 (4개)
    [7] execute 래퍼 성능 (3개)
    [8] 상태 전환 성능 (3개)
    [9] 멀티스레드 동시 접근 (4개)
    [10] 메모리 사용량 (3개)
    [11] CircuitBreakerRegistry 성능 (3개)
    [12] get_status / to_dict 성능 (3개)
"""

import io
import sys
import time
import threading
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.resilience.circuit_breaker import (
    CircuitState,
    FailureType,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    RequestRecord,
    StateChangeEvent,
    CircuitBreaker,
    CircuitBreakerRegistry,
    _reset_registry,
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
# 헬퍼
# =============================================================================
def _make_circuit(name="perf", **kwargs) -> CircuitBreaker:
    """테스트용 서킷 브레이커 생성."""
    config = CircuitBreakerConfig(
        failure_threshold=kwargs.get("failure_threshold", 100),
        success_threshold=kwargs.get("success_threshold", 3),
        open_timeout=kwargs.get("open_timeout", 30.0),
        half_open_max_requests=kwargs.get("half_open_max_requests", 10),
        window_size=kwargs.get("window_size", 60.0),
        minimum_requests=kwargs.get("minimum_requests", 100),
    )
    mock_loader = MagicMock()
    mock_loader.get.return_value = {}
    return CircuitBreaker(name=name, config=config, config_loader=mock_loader)


# =============================================================================
# [1] CircuitState Enum 연산 성능
# =============================================================================
def test_circuit_state_perf(result: PerfResult) -> None:
    """CircuitState Enum 연산 성능."""
    print("\n[1] CircuitState Enum 연산 성능")

    # 1-1: 멤버 접근
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = CircuitState.CLOSED
            _ = CircuitState.OPEN
            _ = CircuitState.HALF_OPEN
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 3) * 1000  # μs
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-1: 멤버 접근 (300K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-1: 멤버 접근", str(e))

    # 1-2: is_allowing_requests 속성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = CircuitState.CLOSED.is_allowing_requests
            _ = CircuitState.OPEN.is_allowing_requests
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-2: is_allowing_requests (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-2: is_allowing_requests", str(e))

    # 1-3: korean_label 속성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = CircuitState.CLOSED.korean_label
            _ = CircuitState.OPEN.korean_label
            _ = CircuitState.HALF_OPEN.korean_label
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 3) * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-3: korean_label (150K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-3: korean_label", str(e))


# =============================================================================
# [2] CircuitBreakerConfig 생성 성능
# =============================================================================
def test_config_creation_perf(result: PerfResult) -> None:
    """CircuitBreakerConfig 생성 성능."""
    print("\n[2] CircuitBreakerConfig 생성 성능")

    # 2-1: 기본값 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = CircuitBreakerConfig()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-1: 기본값 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-1: 기본값 생성", str(e))

    # 2-2: 커스텀 값 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = CircuitBreakerConfig(
                failure_threshold=i % 10 + 1,
                success_threshold=3,
                open_timeout=30.0,
                critical=True,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-2: 커스텀 값 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-2: 커스텀 생성", str(e))

    # 2-3: to_dict 변환
    try:
        config = CircuitBreakerConfig()
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = config.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-3: to_dict (50K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-3: to_dict", str(e))


# =============================================================================
# [3] CircuitBreakerStats 연산 성능
# =============================================================================
def test_stats_perf(result: PerfResult) -> None:
    """CircuitBreakerStats 연산 성능."""
    print("\n[3] CircuitBreakerStats 연산 성능")

    # 3-1: failure_rate 계산
    try:
        stats = CircuitBreakerStats(failure_count=30, success_count=70)
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = stats.failure_rate
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-1: failure_rate (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-1: failure_rate", str(e))

    # 3-2: to_dict 변환
    try:
        stats = CircuitBreakerStats(failure_count=5, success_count=95)
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = stats.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-2: stats.to_dict (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-2: stats to_dict", str(e))

    # 3-3: is_healthy 속성
    try:
        stats = CircuitBreakerStats(state=CircuitState.CLOSED)
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = stats.is_healthy
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-3: is_healthy (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-3: is_healthy", str(e))


# =============================================================================
# [4] CircuitBreaker 초기화 성능
# =============================================================================
def test_circuit_breaker_init_perf(result: PerfResult) -> None:
    """CircuitBreaker 초기화 성능."""
    print("\n[4] CircuitBreaker 초기화 성능")

    # 4-1: 설정 제공 초기화
    try:
        config = CircuitBreakerConfig()
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        iterations = 1_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = CircuitBreaker(name=f"init_{i}", config=config, config_loader=mock_loader)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-1: 초기화 (1K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-1: 초기화", str(e))

    # 4-2: YAML 로드 실패 시 초기화
    try:
        mock_loader = MagicMock()
        mock_loader.get.side_effect = Exception("yaml error")
        iterations = 500
        start = time.perf_counter()
        for i in range(iterations):
            _ = CircuitBreaker(name=f"yaml_fail_{i}", config_loader=mock_loader)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-2: YAML 실패 초기화 (500)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-2: YAML 실패", str(e))

    # 4-3: 속성 접근 속도
    try:
        cb = _make_circuit("prop_perf")
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.name
            _ = cb.config
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-3: 속성 접근 (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-3: 속성 접근", str(e))


# =============================================================================
# [5] allow_request 처리량
# =============================================================================
def test_allow_request_perf(result: PerfResult) -> None:
    """allow_request 처리량."""
    print("\n[5] allow_request 처리량")

    # 5-1: CLOSED 상태
    try:
        cb = _make_circuit("allow_1")
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.allow_request()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-1: CLOSED allow_request (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-1: CLOSED", str(e))

    # 5-2: OPEN 상태
    try:
        cb = _make_circuit("allow_2", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.allow_request()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-2: OPEN allow_request (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-2: OPEN", str(e))

    # 5-3: state 속성 접근 (자동 전환 포함)
    try:
        cb = _make_circuit("allow_3")
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.state
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-3: state 속성 접근 (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-3: state 속성", str(e))


# =============================================================================
# [6] record_success / record_failure 처리량
# =============================================================================
def test_record_perf(result: PerfResult) -> None:
    """record_success / record_failure 처리량."""
    print("\n[6] record_success / record_failure 처리량")

    # 6-1: record_success
    try:
        cb = _make_circuit("record_1")
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.record_success(duration_ms=1.0)
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-1: record_success (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-1: record_success", str(e))

    # 6-2: record_failure
    try:
        cb = _make_circuit("record_2", failure_threshold=100_000, minimum_requests=100_000)
        exc = ConnectionError("fail")
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.record_failure(exception=exc, duration_ms=1.0)
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-2: record_failure (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-2: record_failure", str(e))

    # 6-3: 혼합 기록
    try:
        cb = _make_circuit("record_3", failure_threshold=100_000, minimum_requests=100_000)
        exc = ConnectionError("fail")
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            if i % 3 == 0:
                cb.record_failure(exception=exc)
            else:
                cb.record_success()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-3: 혼합 기록 (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-3: 혼합", str(e))

    # 6-4: stats 접근 (윈도우 집계)
    try:
        cb = _make_circuit("record_4")
        for _ in range(100):
            cb.record_success()
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.stats
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-4: stats 접근 (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-4: stats 접근", str(e))


# =============================================================================
# [7] execute 래퍼 성능
# =============================================================================
def test_execute_perf(result: PerfResult) -> None:
    """execute 래퍼 성능."""
    print("\n[7] execute 래퍼 성능")

    # 7-1: execute 성공 (오버헤드 측정)
    try:
        cb = _make_circuit("exec_1")
        noop = lambda: 42
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.execute(noop)
        elapsed = (time.perf_counter() - start) * 1000
        overhead_per_call = elapsed / iterations * 1000  # μs
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-1: execute 성공 오버헤드 (10K)", f"{elapsed:.1f}ms, {overhead_per_call:.1f}μs/call")
    except Exception as e:
        result.fail("7-1: execute 오버헤드", str(e))

    # 7-2: execute 폴백
    try:
        cb = _make_circuit("exec_2", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        fb = lambda: "fb"
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.execute(lambda: 42, fallback=fb)
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-2: execute 폴백 (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("7-2: execute 폴백", str(e))

    # 7-3: 컨텍스트 매니저 성능
    try:
        cb = _make_circuit("exec_3")
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            with cb:
                pass
        elapsed = (time.perf_counter() - start) * 1000
        overhead_per_call = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-3: 컨텍스트 매니저 (10K)", f"{elapsed:.1f}ms, {overhead_per_call:.1f}μs/call")
    except Exception as e:
        result.fail("7-3: 컨텍스트 매니저", str(e))


# =============================================================================
# [8] 상태 전환 성능
# =============================================================================
def test_state_transition_perf(result: PerfResult) -> None:
    """상태 전환 성능."""
    print("\n[8] 상태 전환 성능")

    # 8-1: force_open / force_close 반복
    try:
        cb = _make_circuit("trans_1")
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.force_open("perf test")
            cb.force_close("perf test")
        elapsed = (time.perf_counter() - start) * 1000
        per_transition = elapsed / (iterations * 2) * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-1: 상태 전환 반복 (10K)", f"{elapsed:.1f}ms, {per_transition:.1f}μs/transition")
    except Exception as e:
        result.fail("8-1: 상태 전환", str(e))

    # 8-2: reset 성능
    try:
        cb = _make_circuit("trans_2")
        for _ in range(100):
            cb.record_success()
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.reset()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-2: reset (5K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("8-2: reset", str(e))

    # 8-3: 콜백 포함 상태 전환
    try:
        events = []
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig()
        cb = CircuitBreaker(
            name="trans_3",
            config=config,
            config_loader=mock_loader,
            on_state_change=lambda evt: events.append(1),
        )
        iterations = 2_000
        start = time.perf_counter()
        for _ in range(iterations):
            cb.force_open("test")
            cb.force_close("test")
        elapsed = (time.perf_counter() - start) * 1000
        per_transition = elapsed / (iterations * 2) * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-3: 콜백 포함 전환 (4K)", f"{elapsed:.1f}ms, {per_transition:.1f}μs/transition")
    except Exception as e:
        result.fail("8-3: 콜백 전환", str(e))


# =============================================================================
# [9] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_perf(result: PerfResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[9] 멀티스레드 동시 접근")

    # 9-1: 4스레드 동시 기록
    try:
        cb = _make_circuit("mt_1", failure_threshold=100_000, minimum_requests=100_000)
        ops_per_thread = 5_000
        errors = []

        def worker():
            try:
                for _ in range(ops_per_thread):
                    cb.record_success()
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
        result.ok("9-1: 4스레드 record_success (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-1: 4스레드", str(e))

    # 9-2: 8스레드 혼합 연산
    try:
        cb = _make_circuit("mt_2", failure_threshold=100_000, minimum_requests=100_000)
        exc = ConnectionError("fail")
        ops_per_thread = 2_000
        errors = []

        def mixed_worker():
            try:
                for i in range(ops_per_thread):
                    if i % 3 == 0:
                        cb.record_failure(exception=exc)
                    else:
                        cb.record_success()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=mixed_worker) for _ in range(8)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 8
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-2: 8스레드 혼합 (16K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-2: 8스레드 혼합", str(e))

    # 9-3: 스레드 경합 (allow_request)
    try:
        cb = _make_circuit("mt_3")
        ops_per_thread = 10_000
        errors = []

        def allow_worker():
            try:
                for _ in range(ops_per_thread):
                    _ = cb.allow_request()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=allow_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-3: 4스레드 allow_request (40K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-3: allow_request 경합", str(e))

    # 9-4: execute 동시 실행
    try:
        cb = _make_circuit("mt_4")
        ops_per_thread = 2_000
        errors = []

        def exec_worker():
            try:
                for _ in range(ops_per_thread):
                    cb.execute(lambda: 42)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=exec_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0
        result.ok("9-4: 4스레드 execute (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-4: execute 동시", str(e))


# =============================================================================
# [10] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerfResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[10] 메모리 사용량")

    # 10-1: CircuitBreaker 인스턴스 메모리
    try:
        tracemalloc.start()
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig()
        circuits = []
        for i in range(100):
            circuits.append(CircuitBreaker(name=f"mem_{i}", config=config, config_loader=mock_loader))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_instance_kb = current / 100 / 1024
        assert per_instance_kb < 50, f"인스턴스당 메모리 과다: {per_instance_kb:.1f}KB"
        result.ok("10-1: 100개 인스턴스 메모리", f"총: {current/1024:.1f}KB, 인스턴스당: {per_instance_kb:.1f}KB")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-1: 인스턴스 메모리", str(e))

    # 10-2: 슬라이딩 윈도우 메모리 (대량 기록)
    try:
        tracemalloc.start()
        cb = _make_circuit("mem_window", window_size=60.0)
        for _ in range(10_000):
            cb.record_success()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert current / 1024 < 2048, f"윈도우 메모리 과다: {current/1024:.1f}KB"
        result.ok("10-2: 10K 기록 후 윈도우 메모리", f"현재: {current/1024:.1f}KB, 피크: {peak/1024:.1f}KB")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-2: 윈도우 메모리", str(e))

    # 10-3: CircuitBreakerConfig 메모리
    try:
        tracemalloc.start()
        configs = [CircuitBreakerConfig() for _ in range(1_000)]
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_config = current / 1_000
        result.ok("10-3: 1K Config 메모리", f"총: {current/1024:.1f}KB, 개당: {per_config:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("10-3: Config 메모리", str(e))


# =============================================================================
# [11] CircuitBreakerRegistry 성능
# =============================================================================
def test_registry_perf(result: PerfResult) -> None:
    """CircuitBreakerRegistry 성능."""
    print("\n[11] CircuitBreakerRegistry 성능")

    # 11-1: get_or_create 성능
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        iterations = 1_000
        start = time.perf_counter()
        for i in range(iterations):
            registry.get_or_create(f"svc_{i}", config=config)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-1: get_or_create 새 생성 (1K)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("11-1: get_or_create", str(e))

    # 11-2: get_or_create 기존 조회
    try:
        iterations = 50_000
        start = time.perf_counter()
        for i in range(iterations):
            registry.get_or_create(f"svc_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-2: get_or_create 조회 (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("11-2: 조회", str(e))

    # 11-3: get_all_status
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        for i in range(50):
            registry.get_or_create(f"status_svc_{i}", config=config)
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            _ = registry.get_all_status()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("11-3: get_all_status 50서킷 (100회)", f"{elapsed:.1f}ms, {per_op:.1f}ms/op")
    except Exception as e:
        result.fail("11-3: get_all_status", str(e))


# =============================================================================
# [12] get_status / to_dict 성능
# =============================================================================
def test_get_status_perf(result: PerfResult) -> None:
    """get_status / to_dict 성능."""
    print("\n[12] get_status / to_dict 성능")

    # 12-1: get_status
    try:
        cb = _make_circuit("status_1")
        for _ in range(50):
            cb.record_success()
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cb.get_status()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-1: get_status (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("12-1: get_status", str(e))

    # 12-2: StateChangeEvent to_dict
    try:
        from datetime import datetime, timezone
        stats = CircuitBreakerStats(failure_count=3)
        event = StateChangeEvent(
            circuit_name="test",
            previous_state=CircuitState.CLOSED,
            current_state=CircuitState.OPEN,
            reason="test",
            stats=stats,
        )
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = event.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-2: StateChangeEvent.to_dict (50K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-2: event to_dict", str(e))

    # 12-3: RequestRecord 생성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = RequestRecord(timestamp=time.monotonic(), success=True, duration_ms=1.0)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-3: RequestRecord 생성 (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-3: RequestRecord", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """성능 테스트 실행."""
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("CircuitBreaker 성능 테스트")
    print("=" * 60)

    r = PerfResult()

    test_circuit_state_perf(r)
    test_config_creation_perf(r)
    test_stats_perf(r)
    test_circuit_breaker_init_perf(r)
    test_allow_request_perf(r)
    test_record_perf(r)
    test_execute_perf(r)
    test_state_transition_perf(r)
    test_multithread_perf(r)
    test_memory_usage(r)
    test_registry_perf(r)
    test_get_status_perf(r)

    r.summary()

    _reset_registry()


if __name__ == "__main__":
    main()
