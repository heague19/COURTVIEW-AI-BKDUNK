# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/performance
파일: test_profiler_perf.py
설명: 성능 프로파일러 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [P1] 데이터 클래스 생성 성능 (3개)
    [P2] FunctionProfile update 처리량 (3개)
    [P3] ProfileResult 생성/to_dict 성능 (3개)
    [P4] PerformanceProfiler start/stop 처리량 (3개)
    [P5] profile_function_call 처리량 (3개)
    [P6] 프로파일 조회/관리 성능 (3개)
    [P7] 멀티스레드 동시 프로파일링 (3개)
    [P8] 메모리 사용량 (3개)

    총 24개 테스트
"""

import gc
import sys
import threading
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.profiler import (
    # 데이터 클래스
    MemorySnapshot,
    CPUSnapshot,
    GPUSnapshot,
    FunctionProfile,
    ProfileResult,
    # Enum
    ProfileType,
    # 메인 클래스
    PerformanceProfiler,
    # 싱글톤
    _reset_profiler,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        """테스트 통과."""
        self.passed += 1
        line = f"  [PASS] {test_name}"
        if metric:
            line += f"  |  {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(line)

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n주요 성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼 함수
# =============================================================================
def measure_ops(func, iterations: int = 10000) -> float:
    """초당 연산 수 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


def measure_time_ms(func, iterations: int = 1000) -> float:
    """평균 실행 시간 (밀리초) 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000


def get_object_size(obj) -> int:
    """객체 대략적 메모리 크기 (바이트) 측정."""
    return sys.getsizeof(obj)


def _make_profiler(**kwargs) -> PerformanceProfiler:
    """테스트용 PerformanceProfiler 생성."""
    defaults = {
        "enabled": True,
        "cpu_enabled": False,   # 성능 테스트에서는 cProfile 비활성화
        "memory_enabled": False,  # tracemalloc 비활성화
        "gpu_enabled": False,
        "max_profiles": 10000,
    }
    defaults.update(kwargs)
    return PerformanceProfiler(**defaults)


# =============================================================================
# [P1] 데이터 클래스 생성 성능 (3개)
# =============================================================================
def test_p1_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능."""
    print("\n[P1] 데이터 클래스 생성 성능")

    # P1-1. MemorySnapshot 생성 처리량
    try:
        ops = measure_ops(
            lambda: MemorySnapshot(current_mb=512.0, peak_mb=1024.0, percent=50.0),
            iterations=50000,
        )
        assert ops > 50000, f"MemorySnapshot 생성: {ops:.0f} ops/sec < 50000"
        result.ok("P1-1 MemorySnapshot 생성", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-1 MemorySnapshot 생성", str(e))

    # P1-2. FunctionProfile 생성 처리량
    try:
        ops = measure_ops(
            lambda: FunctionProfile(name="test", module="mod", filename="test.py"),
            iterations=50000,
        )
        assert ops > 50000, f"FunctionProfile 생성: {ops:.0f} ops/sec < 50000"
        result.ok("P1-2 FunctionProfile 생성", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-2 FunctionProfile 생성", str(e))

    # P1-3. ProfileResult 생성 처리량
    try:
        ops = measure_ops(
            lambda: ProfileResult(profile_id="test", profile_type=ProfileType.TIME, name="perf"),
            iterations=30000,
        )
        assert ops > 20000, f"ProfileResult 생성: {ops:.0f} ops/sec < 20000"
        result.ok("P1-3 ProfileResult 생성", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-3 ProfileResult 생성", str(e))


# =============================================================================
# [P2] FunctionProfile update 처리량 (3개)
# =============================================================================
def test_p2_function_profile_update(result: PerformanceTestResult) -> None:
    """FunctionProfile update 성능."""
    print("\n[P2] FunctionProfile update 처리량")

    # P2-1. update 처리량
    try:
        fp = FunctionProfile(name="test")
        ops = measure_ops(lambda: fp.update(10.0), iterations=100000)
        assert ops > 200000, f"update: {ops:.0f} ops/sec < 200000"
        result.ok("P2-1 FunctionProfile.update", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-1 update", str(e))

    # P2-2. update + memory_delta 처리량
    try:
        fp = FunctionProfile(name="test")
        ops = measure_ops(lambda: fp.update(10.0, 0.5), iterations=100000)
        assert ops > 200000, f"update+mem: {ops:.0f} ops/sec < 200000"
        result.ok("P2-2 FunctionProfile.update + memory_delta", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-2 update+mem", str(e))

    # P2-3. is_slow 체크 처리량
    try:
        fp = FunctionProfile(name="test")
        fp.update(25.0)
        ops = measure_ops(lambda: fp.is_slow(), iterations=200000)
        assert ops > 500000, f"is_slow: {ops:.0f} ops/sec < 500000"
        result.ok("P2-3 FunctionProfile.is_slow", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-3 is_slow", str(e))


# =============================================================================
# [P3] ProfileResult 생성/to_dict 성능 (3개)
# =============================================================================
def test_p3_profile_result_perf(result: PerformanceTestResult) -> None:
    """ProfileResult 성능."""
    print("\n[P3] ProfileResult 생성/to_dict 성능")

    # P3-1. to_dict (빈 ProfileResult)
    try:
        pr = ProfileResult(profile_id="test", profile_type=ProfileType.TIME)
        ops = measure_ops(lambda: pr.to_dict(), iterations=30000)
        assert ops > 20000, f"to_dict 빈: {ops:.0f} ops/sec < 20000"
        result.ok("P3-1 ProfileResult.to_dict (빈)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-1 to_dict 빈", str(e))

    # P3-2. to_dict (스냅샷 포함)
    try:
        cpu = CPUSnapshot(percent=50.0, per_core_percent=[25.0, 75.0])
        mem = MemorySnapshot(current_mb=512.0)
        pr = ProfileResult(
            profile_id="test",
            profile_type=ProfileType.COMBINED,
            cpu_snapshot=cpu,
            memory_snapshot=mem,
        )
        ops = measure_ops(lambda: pr.to_dict(), iterations=20000)
        assert ops > 10000, f"to_dict 스냅샷: {ops:.0f} ops/sec < 10000"
        result.ok("P3-2 ProfileResult.to_dict (스냅샷 포함)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-2 to_dict 스냅샷", str(e))

    # P3-3. get_top_functions (20개 함수 프로파일)
    try:
        fps = []
        for i in range(20):
            fp = FunctionProfile(name=f"func_{i}")
            fp.update(float(i * 5))
            fps.append(fp)
        pr = ProfileResult(
            profile_id="test",
            profile_type=ProfileType.CPU,
            function_profiles=fps,
        )
        ops = measure_ops(lambda: pr.get_top_functions(10), iterations=30000)
        assert ops > 10000, f"get_top_functions: {ops:.0f} ops/sec < 10000"
        result.ok("P3-3 get_top_functions (20개 중 10개)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-3 get_top_functions", str(e))


# =============================================================================
# [P4] PerformanceProfiler start/stop 처리량 (3개)
# =============================================================================
def test_p4_profiler_start_stop(result: PerformanceTestResult) -> None:
    """PerformanceProfiler start/stop 성능."""
    print("\n[P4] PerformanceProfiler start/stop 처리량")

    # P4-1. start + stop (TIME 모드, cProfile/tracemalloc 비활성)
    try:
        p = _make_profiler()

        def start_stop():
            p.start_profiling(ProfileType.TIME, "perf")
            p.stop_profiling()

        ops = measure_ops(start_stop, iterations=5000)
        assert ops > 1000, f"start/stop TIME: {ops:.0f} ops/sec < 1000"
        result.ok("P4-1 start+stop TIME 모드", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P4-1 start/stop TIME", str(e))

    # P4-2. disabled 모드 start/stop
    try:
        p = _make_profiler(enabled=False)

        def disabled_start_stop():
            p.start_profiling(ProfileType.TIME)
            p.stop_profiling()

        ops = measure_ops(disabled_start_stop, iterations=50000)
        assert ops > 100000, f"disabled start/stop: {ops:.0f} ops/sec < 100000"
        result.ok("P4-2 disabled start+stop", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P4-2 disabled start/stop", str(e))

    # P4-3. _generate_profile_id 처리량
    try:
        p = _make_profiler()
        ops = measure_ops(lambda: p._generate_profile_id(), iterations=30000)
        assert ops > 10000, f"generate_id: {ops:.0f} ops/sec < 10000"
        result.ok("P4-3 _generate_profile_id", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P4-3 generate_id", str(e))


# =============================================================================
# [P5] profile_function_call 처리량 (3개)
# =============================================================================
def test_p5_function_call_perf(result: PerformanceTestResult) -> None:
    """profile_function_call 성능."""
    print("\n[P5] profile_function_call 처리량")

    # P5-1. 새 함수 등록 처리량
    try:
        p = _make_profiler()
        idx = [0]

        def new_func():
            p.profile_function_call(f"func_{idx[0]}", 10.0)
            idx[0] += 1

        ops = measure_ops(new_func, iterations=10000)
        assert ops > 5000, f"새 함수 등록: {ops:.0f} ops/sec < 5000"
        result.ok("P5-1 새 함수 등록", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P5-1 새 함수 등록", str(e))

    # P5-2. 기존 함수 업데이트 처리량
    try:
        p = _make_profiler()
        p.profile_function_call("existing", 1.0)  # 등록

        ops = measure_ops(
            lambda: p.profile_function_call("existing", 1.0),
            iterations=50000,
        )
        assert ops > 50000, f"기존 함수 업데이트: {ops:.0f} ops/sec < 50000"
        result.ok("P5-2 기존 함수 업데이트", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P5-2 기존 함수 업데이트", str(e))

    # P5-3. get_function_profile 조회 처리량
    try:
        p = _make_profiler()
        for i in range(100):
            p.profile_function_call(f"func_{i}", 1.0)

        ops = measure_ops(
            lambda: p.get_function_profile("func_50"),
            iterations=100000,
        )
        assert ops > 100000, f"get_function_profile: {ops:.0f} ops/sec < 100000"
        result.ok("P5-3 get_function_profile (100개 중 조회)", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P5-3 get_function_profile", str(e))


# =============================================================================
# [P6] 프로파일 조회/관리 성능 (3개)
# =============================================================================
def test_p6_profile_management(result: PerformanceTestResult) -> None:
    """프로파일 조회/관리 성능."""
    print("\n[P6] 프로파일 조회/관리 성능")

    # P6-1. get_profile (100개 저장 후 조회)
    try:
        p = _make_profiler()
        pids = []
        for _ in range(100):
            pid = p.start_profiling(ProfileType.TIME)
            p.stop_profiling()
            pids.append(pid)

        target = pids[50]
        ops = measure_ops(lambda: p.get_profile(target), iterations=100000)
        assert ops > 100000, f"get_profile: {ops:.0f} ops/sec < 100000"
        result.ok("P6-1 get_profile (100개 중 조회)", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-1 get_profile", str(e))

    # P6-2. get_all_profiles (100개)
    try:
        p = _make_profiler()
        for _ in range(100):
            p.start_profiling(ProfileType.TIME)
            p.stop_profiling()

        ops = measure_ops(lambda: p.get_all_profiles(), iterations=10000)
        assert ops > 5000, f"get_all_profiles: {ops:.0f} ops/sec < 5000"
        result.ok("P6-2 get_all_profiles (100개)", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-2 get_all_profiles", str(e))

    # P6-3. get_recent_profiles (100개 중 10개)
    try:
        p = _make_profiler()
        for _ in range(100):
            p.start_profiling(ProfileType.TIME)
            p.stop_profiling()

        ops = measure_ops(lambda: p.get_recent_profiles(10), iterations=5000)
        assert ops > 1000, f"get_recent_profiles: {ops:.0f} ops/sec < 1000"
        result.ok("P6-3 get_recent_profiles (100개 중 10개)", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-3 get_recent_profiles", str(e))


# =============================================================================
# [P7] 멀티스레드 동시 프로파일링 (3개)
# =============================================================================
def test_p7_multithread(result: PerformanceTestResult) -> None:
    """멀티스레드 성능."""
    print("\n[P7] 멀티스레드 동시 프로파일링")

    # P7-1. profile_function_call 멀티스레드 (4스레드 x 5000)
    try:
        p = _make_profiler()
        errors = []
        n_threads = 4
        n_ops = 5000

        def func_call_worker(tid):
            try:
                for i in range(n_ops):
                    p.profile_function_call(f"thread_{tid}_func", float(i) * 0.1)
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=func_call_worker, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        # 각 스레드별 함수 프로파일 존재 확인
        for tid in range(n_threads):
            fp = p.get_function_profile(f"thread_{tid}_func")
            assert fp is not None
            assert fp.call_count == n_ops, f"thread_{tid}: {fp.call_count} != {n_ops}"

        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok("P7-1 profile_function_call 멀티스레드 (4x5000)", f"{ops:,.0f} ops/sec, 정확도 100%")
    except AssertionError as e:
        result.fail("P7-1 멀티스레드 function_call", str(e))

    # P7-2. get_slow_functions 멀티스레드
    try:
        p = _make_profiler()
        for i in range(50):
            p.profile_function_call(f"func_{i}", float(i) * 2)
        errors = []

        def slow_query_worker():
            try:
                for _ in range(1000):
                    p.get_slow_functions(40.0)
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=slow_query_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        total_ops = 4 * 1000
        ops = total_ops / elapsed
        result.ok("P7-2 get_slow_functions 멀티스레드 (4x1000)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P7-2 멀티스레드 slow_functions", str(e))

    # P7-3. get_status 멀티스레드
    try:
        p = _make_profiler()
        errors = []

        def status_worker():
            try:
                for _ in range(2000):
                    p.get_status()
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=status_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        total_ops = 4 * 2000
        ops = total_ops / elapsed
        result.ok("P7-3 get_status 멀티스레드 (4x2000)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P7-3 멀티스레드 get_status", str(e))


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_p8_memory(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. FunctionProfile 대량 생성 메모리
    try:
        gc.collect()
        fps = []
        for i in range(10000):
            fp = FunctionProfile(name=f"func_{i}", module="mod", filename="test.py")
            fp.update(float(i) * 0.01)
            fps.append(fp)

        sample_size = get_object_size(fps[0])
        result.ok("P8-1 FunctionProfile 10000개", f"개당 ~{sample_size}B")
    except Exception as e:
        result.fail("P8-1 FunctionProfile 메모리", str(e))

    # P8-2. ProfileResult 대량 저장 메모리
    try:
        gc.collect()
        p = _make_profiler()
        for i in range(500):
            p.start_profiling(ProfileType.TIME, f"test_{i}")
            p.stop_profiling()

        status = p.get_status()
        assert status["profiles_count"] == 500
        result.ok("P8-2 ProfileResult 500개 저장", f"profiles={status['profiles_count']}")
    except (AssertionError, Exception) as e:
        result.fail("P8-2 ProfileResult 메모리", str(e))

    # P8-3. PerformanceProfiler 기본 메모리
    try:
        gc.collect()
        p = _make_profiler()
        obj_size = get_object_size(p)
        result.ok("P8-3 PerformanceProfiler 기본 메모리", f"~{obj_size}B")
    except Exception as e:
        result.fail("P8-3 Profiler 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - profiler.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    test_p1_dataclass_creation(result)
    test_p2_function_profile_update(result)
    test_p3_profile_result_perf(result)
    test_p4_profiler_start_stop(result)
    test_p5_function_call_perf(result)
    test_p6_profile_management(result)
    test_p7_multithread(result)
    test_p8_memory(result)

    result.summary()
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
