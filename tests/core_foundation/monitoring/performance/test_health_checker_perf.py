# -*- coding: utf-8 -*-
"""
COURTVIEW - health_checker.py 성능 테스트

8개 카테고리, 24개 테스트

실행:
    python tests/core_foundation/monitoring/performance/test_health_checker_perf.py
"""

from __future__ import annotations

import sys
import threading
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable, List

# 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================
# PerformanceTestResult
# ============================================================
class PerformanceTestResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: List[str] = []
        self.metrics: List[str] = []

    def ok(self, name: str, metric: str = "") -> None:
        self.passed += 1
        line = f"  [PASS] {name}"
        if metric:
            line += f"  |  {metric}"
            self.metrics.append(f"  - {name}: {metric}")
        print(line)

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
            print(f"성능 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"성능 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print(f"\n주요 성능 지표:")
        for m in self.metrics:
            print(m)
        print("=" * 60)


# ============================================================
# 측정 헬퍼
# ============================================================
def measure_ops(func: Callable[[], Any], iterations: int) -> float:
    """초당 연산 수 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    if elapsed == 0:
        return float("inf")
    return iterations / elapsed


def measure_time_ms(func: Callable[[], Any]) -> float:
    """단일 호출 시간 (ms)."""
    start = time.perf_counter()
    func()
    return (time.perf_counter() - start) * 1000


# ============================================================
# 임포트
# ============================================================
from core_foundation.monitoring.health_checker import (
    HealthStatus,
    DependencyType,
    HealthCheckResult,
    DependencyHealth,
    SystemHealth,
    HealthCheckConfig,
    HealthChecker,
    aggregate_health_status,
    create_health_check,
    _get_health_checker,
    _reset_health_checker,
)


# ============================================================
# 헬퍼
# ============================================================
def _fast_healthy() -> HealthCheckResult:
    """빠른 HEALTHY 결과 (오버헤드 최소화)."""
    return HealthCheckResult(
        name="fast",
        status=HealthStatus.HEALTHY,
        dependency_type=DependencyType.CUSTOM,
        response_time_ms=0.1,
    )


def _make_checker(**kwargs) -> HealthChecker:
    """성능 테스트용 HealthChecker (시스템 체크 비활성)."""
    defaults = dict(
        enabled=True,
        enable_system_checks=False,
        max_history=1000,
        default_timeout=5.0,
    )
    defaults.update(kwargs)
    return HealthChecker(**defaults)


def _reset_singleton() -> None:
    try:
        _reset_health_checker()
    except Exception:
        pass


# =============================================================================
# [P1] 데이터 클래스 생성 속도 (3개)
# =============================================================================
def test_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 속도 측정."""
    print("\n[P1] 데이터 클래스 생성 속도")

    # P1-1. HealthCheckResult 생성
    try:
        iters = 100000
        ops = measure_ops(
            lambda: HealthCheckResult(
                name="test",
                status=HealthStatus.HEALTHY,
                dependency_type=DependencyType.CUSTOM,
                message="OK",
                response_time_ms=1.5,
            ),
            iters,
        )
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-1 HealthCheckResult 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-1 HealthCheckResult", str(e))

    # P1-2. DependencyHealth 생성
    try:
        iters = 100000
        ops = measure_ops(
            lambda: DependencyHealth(name="test", dependency_type=DependencyType.GPU),
            iters,
        )
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-2 DependencyHealth 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-2 DependencyHealth", str(e))

    # P1-3. SystemHealth 생성
    try:
        iters = 100000
        ops = measure_ops(
            lambda: SystemHealth(overall_status=HealthStatus.HEALTHY),
            iters,
        )
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-3 SystemHealth 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-3 SystemHealth", str(e))


# =============================================================================
# [P2] DependencyHealth.update 처리량 (3개)
# =============================================================================
def test_dependency_health_update(result: PerformanceTestResult) -> None:
    """DependencyHealth.update 성능 측정."""
    print("\n[P2] DependencyHealth.update 처리량")

    # P2-1. update HEALTHY
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        healthy_result = HealthCheckResult.healthy(
            "test", DependencyType.CUSTOM, response_time_ms=1.0,
        )
        iters = 100000
        ops = measure_ops(lambda: dh.update(healthy_result), iters)
        assert ops > 200000, f"느림: {ops:.0f} ops/sec"
        result.ok("P2-1 update HEALTHY", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-1 update", str(e))

    # P2-2. update UNHEALTHY
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        unhealthy_result = HealthCheckResult.unhealthy(
            "test", DependencyType.CUSTOM, "fail",
        )
        iters = 100000
        ops = measure_ops(lambda: dh.update(unhealthy_result), iters)
        assert ops > 200000, f"느림: {ops:.0f} ops/sec"
        result.ok("P2-2 update UNHEALTHY", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-2 update UNHEALTHY", str(e))

    # P2-3. uptime_percentage 계산
    try:
        dh = DependencyHealth(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            total_checks=10000,
            successful_checks=9500,
        )
        iters = 500000
        ops = measure_ops(lambda: dh.uptime_percentage, iters)
        assert ops > 1000000, f"느림: {ops:.0f} ops/sec"
        result.ok("P2-3 uptime_percentage", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-3 uptime", str(e))


# =============================================================================
# [P3] aggregate_health_status 처리량 (3개)
# =============================================================================
def test_aggregate_speed(result: PerformanceTestResult) -> None:
    """aggregate_health_status 성능 측정."""
    print("\n[P3] aggregate_health_status 처리량")

    # P3-1. 3개 결과
    try:
        results_3 = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.degraded("b", DependencyType.SYSTEM_RESOURCE, "high"),
            HealthCheckResult.unhealthy("c", DependencyType.CAMERA, "fail"),
        ]
        iters = 100000
        ops = measure_ops(lambda: aggregate_health_status(results_3), iters)
        assert ops > 200000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-1 aggregate (3개)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-1 aggregate 3", str(e))

    # P3-2. 20개 결과
    try:
        results_20 = [
            HealthCheckResult.healthy(f"check_{i}", DependencyType.CUSTOM)
            for i in range(20)
        ]
        iters = 50000
        ops = measure_ops(lambda: aggregate_health_status(results_20), iters)
        assert ops > 50000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-2 aggregate (20개)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-2 aggregate 20", str(e))

    # P3-3. to_dict 직렬화 (SystemHealth 10 results)
    try:
        results_10 = [
            HealthCheckResult.healthy(f"check_{i}", DependencyType.CUSTOM, response_time_ms=float(i))
            for i in range(10)
        ]
        sh = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            total_checks=10,
            healthy_checks=10,
            results=results_10,
            check_duration_ms=50.0,
        )
        iters = 10000
        ops = measure_ops(lambda: sh.to_dict(), iters)
        assert ops > 5000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-3 SystemHealth.to_dict (10 results)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-3 to_dict", str(e))


# =============================================================================
# [P4] HealthChecker register_check 속도 (3개)
# =============================================================================
def test_register_speed(result: PerformanceTestResult) -> None:
    """HealthChecker register_check 성능 측정."""
    print("\n[P4] HealthChecker register_check 속도")

    # P4-1. register 100개
    try:
        hc = _make_checker()
        iters = 100

        def register_one():
            import random
            name = f"check_{random.randint(0, 999999)}"
            hc.register_check(name, _fast_healthy, DependencyType.CUSTOM)

        ops = measure_ops(register_one, iters)
        assert ops > 1000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-1 register_check (100개)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-1 register", str(e))

    # P4-2. list_checks (100개 등록 후)
    try:
        hc = _make_checker()
        for i in range(100):
            hc.register_check(f"c{i}", _fast_healthy, DependencyType.CUSTOM)
        iters = 10000
        ops = measure_ops(lambda: hc.list_checks(), iters)
        assert ops > 10000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-2 list_checks (100개)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-2 list_checks", str(e))

    # P4-3. get_check (100개 중 조회)
    try:
        hc = _make_checker()
        for i in range(100):
            hc.register_check(f"c{i}", _fast_healthy, DependencyType.CUSTOM)
        iters = 100000
        ops = measure_ops(lambda: hc.get_check("c50"), iters)
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-3 get_check (100개 중)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-3 get_check", str(e))


# =============================================================================
# [P5] HealthChecker check 실행 속도 (3개)
# =============================================================================
def test_check_execution_speed(result: PerformanceTestResult) -> None:
    """HealthChecker check() 실행 성능 측정."""
    print("\n[P5] HealthChecker check 실행 속도")

    # P5-1. 단일 check (fast healthy)
    try:
        hc = _make_checker()
        hc.register_check("fast", _fast_healthy, DependencyType.CUSTOM)
        iters = 1000
        ops = measure_ops(lambda: hc.check("fast"), iters)
        assert ops > 500, f"느림: {ops:.0f} ops/sec"
        hc.shutdown()
        result.ok("P5-1 check (fast healthy)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-1 check", str(e))

    # P5-2. disabled check (바이패스)
    try:
        hc = _make_checker()
        hc.register_check("dis", _fast_healthy, DependencyType.CUSTOM, enabled=False)
        iters = 50000
        ops = measure_ops(lambda: hc.check("dis"), iters)
        assert ops > 50000, f"느림: {ops:.0f} ops/sec"
        result.ok("P5-2 disabled check (바이패스)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-2 disabled", str(e))

    # P5-3. check -> DependencyHealth 업데이트 오버헤드
    try:
        hc = _make_checker()
        hc.register_check("dep", _fast_healthy, DependencyType.CUSTOM)
        # 워밍업
        hc.check("dep")
        iters = 1000
        ops = measure_ops(lambda: hc.check("dep"), iters)
        dep = hc.get_dependency_status("dep")
        assert dep.total_checks > iters
        assert ops > 500, f"느림: {ops:.0f} ops/sec"
        hc.shutdown()
        result.ok("P5-3 check + dep update", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-3 dep update", str(e))


# =============================================================================
# [P6] HealthChecker check_all 속도 (3개)
# =============================================================================
def test_check_all_speed(result: PerformanceTestResult) -> None:
    """HealthChecker check_all() 성능 측정."""
    print("\n[P6] HealthChecker check_all 속도")

    # P6-1. check_all 5개 체크 (순차)
    try:
        hc = _make_checker()
        for i in range(5):
            hc.register_check(f"c{i}", _fast_healthy, DependencyType.CUSTOM)
        iters = 200
        ops = measure_ops(lambda: hc.check_all(parallel=False), iters)
        assert ops > 50, f"느림: {ops:.0f} ops/sec"
        hc.shutdown()
        result.ok("P6-1 check_all 5개 (순차)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-1 check_all 순차", str(e))

    # P6-2. check_all 5개 체크 (병렬)
    try:
        hc = _make_checker()
        for i in range(5):
            hc.register_check(f"c{i}", _fast_healthy, DependencyType.CUSTOM)
        iters = 200
        ops = measure_ops(lambda: hc.check_all(parallel=True), iters)
        assert ops > 30, f"느림: {ops:.0f} ops/sec"
        hc.shutdown()
        result.ok("P6-2 check_all 5개 (병렬)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-2 check_all 병렬", str(e))

    # P6-3. check_all disabled (바이패스)
    try:
        hc = _make_checker(enabled=False)
        for i in range(10):
            hc.register_check(f"c{i}", _fast_healthy, DependencyType.CUSTOM)
        iters = 100000
        ops = measure_ops(lambda: hc.check_all(), iters)
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P6-3 check_all disabled (바이패스)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-3 disabled", str(e))


# =============================================================================
# [P7] 멀티스레드 체크 (3개)
# =============================================================================
def test_multithread(result: PerformanceTestResult) -> None:
    """멀티스레드 헬스 체크 성능 측정."""
    print("\n[P7] 멀티스레드 체크")

    # P7-1. 4스레드 x 100 check 동시 실행
    try:
        hc = _make_checker()
        hc.register_check("mt", _fast_healthy, DependencyType.CUSTOM)
        errors = []
        check_count = 100
        thread_count = 4

        def worker():
            try:
                for _ in range(check_count):
                    r = hc.check("mt")
                    if not isinstance(r, HealthCheckResult):
                        errors.append("Invalid result type")
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        total_ops = thread_count * check_count
        ops = total_ops / elapsed if elapsed > 0 else 0
        assert len(errors) == 0, f"에러: {errors[:3]}"
        hc.shutdown()
        result.ok(f"P7-1 멀티스레드 check ({thread_count}x{check_count})", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P7-1 멀티스레드", str(e))

    # P7-2. 4스레드 register + check 동시
    try:
        hc = _make_checker()
        errors = []

        def register_worker():
            try:
                for i in range(50):
                    hc.register_check(
                        f"rw_{threading.current_thread().name}_{i}",
                        _fast_healthy,
                        DependencyType.CUSTOM,
                    )
            except Exception as ex:
                errors.append(str(ex))

        def check_worker():
            try:
                # register 이후에 check 시도
                time.sleep(0.01)
                checks = hc.list_checks()
                for name in checks[:10]:
                    hc.check(name)
            except Exception as ex:
                errors.append(str(ex))

        threads = []
        for _ in range(2):
            threads.append(threading.Thread(target=register_worker))
            threads.append(threading.Thread(target=check_worker))

        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors[:3]}"
        hc.shutdown()
        result.ok(f"P7-2 register+check 동시 (4스레드)", f"{elapsed*1000:.1f}ms")
    except Exception as e:
        result.fail("P7-2 동시", str(e))

    # P7-3. 싱글톤 멀티스레드 접근 (10스레드)
    try:
        _reset_singleton()
        instances = []
        errors = []

        def get_inst():
            try:
                inst = _get_health_checker()
                instances.append(id(inst))
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=get_inst) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0
        assert len(set(instances)) == 1
        _reset_singleton()
        result.ok("P7-3 싱글톤 10스레드", f"{elapsed*1000:.1f}ms")
    except Exception as e:
        result.fail("P7-3 싱글톤", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_memory(result: PerformanceTestResult) -> None:
    """메모리 사용량 측정."""
    print("\n[P8] 메모리 사용량")

    # P8-1. HealthCheckResult 10000개
    try:
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        items = [
            HealthCheckResult(
                name=f"check_{i}",
                status=HealthStatus.HEALTHY,
                dependency_type=DependencyType.CUSTOM,
                response_time_ms=float(i),
            )
            for i in range(10000)
        ]
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap2.compare_to(snap1, "lineno")
        total_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
        per_item = total_bytes / 10000 if total_bytes > 0 else 0
        assert len(items) == 10000
        result.ok("P8-1 HealthCheckResult 10000개", f"개당 ~{per_item:.0f}B")
    except Exception as e:
        result.fail("P8-1 메모리", str(e))

    # P8-2. HealthChecker 히스토리 500건
    try:
        hc = _make_checker(max_history=500)
        hc.register_check("a", _fast_healthy, DependencyType.CUSTOM)

        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        for _ in range(500):
            hc.check_all(parallel=False)
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        history = hc.get_history(limit=500)
        assert len(history) == 500
        stats = snap2.compare_to(snap1, "lineno")
        total_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
        hc.shutdown()
        result.ok("P8-2 히스토리 500건", f"history={len(history)}")
    except Exception as e:
        result.fail("P8-2 히스토리", str(e))

    # P8-3. HealthChecker 기본 메모리
    try:
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        hc = _make_checker()
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap2.compare_to(snap1, "lineno")
        total_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
        per_item = total_bytes if total_bytes > 0 else 0
        result.ok("P8-3 HealthChecker 기본 메모리", f"~{per_item:.0f}B")
    except Exception as e:
        result.fail("P8-3 기본 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - health_checker.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    test_dataclass_creation(result)
    test_dependency_health_update(result)
    test_aggregate_speed(result)
    test_register_speed(result)
    test_check_execution_speed(result)
    test_check_all_speed(result)
    test_multithread(result)
    test_memory(result)

    result.summary()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
