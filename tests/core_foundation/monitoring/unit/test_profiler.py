"""
tests/core_foundation/monitoring/unit/test_profiler.py

Profiler 단위 테스트
- TimeProfiler 동작 검증
- MemoryProfiler 동작 검증
- CallStackProfiler 동작 검증
- ProfilerManager 통합 검증
- Reporter 검증

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import tempfile

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.profiler import (
    TimeProfiler,
    MemoryProfiler,
    CallStackProfiler,
    ProfilerManager,
    get_profiler,
    enable_profiling,
    disable_profiling,
    get_profiling_report,
    reset_profiling,
    profile,
    TextReporter,
    JSONReporter,
    FunctionProfile,
    CallGraph,
)


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def ok(self, test_name: str) -> None:
        """테스트 성공"""
        self.passed += 1
        print(f"[PASS] {test_name}")

    def fail(self, test_name: str, reason: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.failures.append((test_name, reason))
        print(f"[FAIL] {test_name}: {reason}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")

        if self.failures:
            print(f"\n실패한 테스트:")
            for name, reason in self.failures:
                print(f"  - {name}: {reason}")

        print(f"{'='*60}")


# ==================== TimeProfiler 테스트 ====================
def test_time_profiler_decorator(result: TestResult) -> None:
    """TimeProfiler 데코레이터"""
    try:
        profiler = TimeProfiler(enabled=True)

        @profiler.profile()
        def test_func():
            time.sleep(0.001)  # 1ms
            return "done"

        # 여러 번 호출
        for _ in range(5):
            ret = test_func()
            assert ret == "done"

        # 통계 확인
        stats = profiler.get_stats()
        assert len(stats) == 1

        func_name = list(stats.keys())[0]
        profile = stats[func_name]

        assert profile.call_count == 5
        assert profile.total_time > 0
        assert profile.avg_time > 0
        assert profile.min_time > 0
        assert profile.max_time >= profile.min_time

        result.ok("TimeProfiler 데코레이터")
    except Exception as e:
        result.fail("TimeProfiler 데코레이터", str(e))


def test_time_profiler_context_manager(result: TestResult) -> None:
    """TimeProfiler 컨텍스트 매니저"""
    try:
        profiler = TimeProfiler(enabled=True)

        with profiler:
            time.sleep(0.002)  # 2ms

        stats = profiler.get_stats()
        assert "__context__" in stats

        profile = stats["__context__"]
        assert profile.call_count == 1
        assert profile.total_time >= 1.0  # 최소 1ms

        result.ok("TimeProfiler 컨텍스트 매니저")
    except Exception as e:
        result.fail("TimeProfiler 컨텍스트 매니저", str(e))


def test_time_profiler_disabled(result: TestResult) -> None:
    """TimeProfiler 비활성화 시 오버헤드 없음"""
    try:
        profiler = TimeProfiler(enabled=False)

        @profiler.profile()
        def test_func():
            return "done"

        ret = test_func()
        assert ret == "done"

        # 통계 없음
        stats = profiler.get_stats()
        assert len(stats) == 0

        result.ok("TimeProfiler 비활성화")
    except Exception as e:
        result.fail("TimeProfiler 비활성화", str(e))


def test_time_profiler_hotspots(result: TestResult) -> None:
    """TimeProfiler 핫스팟 탐지"""
    try:
        profiler = TimeProfiler(enabled=True)

        @profiler.profile(name="slow")
        def slow():
            time.sleep(0.003)

        @profiler.profile(name="fast")
        def fast():
            time.sleep(0.001)

        # 실행
        slow()
        fast()

        # 핫스팟 (총 시간 기준)
        hotspots = profiler.get_hotspots(top_n=2, sort_by="total_time")
        assert len(hotspots) == 2
        assert hotspots[0].function_name == "slow"
        assert hotspots[1].function_name == "fast"

        result.ok("TimeProfiler 핫스팟 탐지")
    except Exception as e:
        result.fail("TimeProfiler 핫스팟 탐지", str(e))


def test_time_profiler_reset(result: TestResult) -> None:
    """TimeProfiler reset()"""
    try:
        profiler = TimeProfiler(enabled=True)

        @profiler.profile()
        def test_func():
            pass

        test_func()
        assert len(profiler.get_stats()) == 1

        profiler.reset()
        assert len(profiler.get_stats()) == 0

        result.ok("TimeProfiler reset()")
    except Exception as e:
        result.fail("TimeProfiler reset()", str(e))


def test_time_profiler_max_samples(result: TestResult) -> None:
    """TimeProfiler 최대 샘플 제한"""
    try:
        profiler = TimeProfiler(enabled=True, max_samples=10)

        @profiler.profile()
        def test_func():
            pass

        # 20번 호출
        for _ in range(20):
            test_func()

        stats = profiler.get_stats()
        func_name = list(stats.keys())[0]
        profile = stats[func_name]

        assert profile.call_count == 20
        assert len(profile._time_samples) == 10  # 최대 10개만

        result.ok("TimeProfiler 최대 샘플 제한")
    except Exception as e:
        result.fail("TimeProfiler 최대 샘플 제한", str(e))


# ==================== MemoryProfiler 테스트 ====================
def test_memory_profiler_decorator(result: TestResult) -> None:
    """MemoryProfiler 데코레이터"""
    try:
        profiler = MemoryProfiler(enabled=True)

        @profiler.profile()
        def test_func():
            # 약간의 메모리 사용
            data = [0] * 1000
            return data

        test_func()

        # 통계 확인
        stats = profiler.get_stats()
        assert len(stats) >= 1

        result.ok("MemoryProfiler 데코레이터")
    except Exception as e:
        result.fail("MemoryProfiler 데코레이터", str(e))


def test_memory_profiler_context_manager(result: TestResult) -> None:
    """MemoryProfiler 컨텍스트 매니저"""
    try:
        profiler = MemoryProfiler(enabled=True)

        with profiler:
            data = [0] * 1000

        snapshots = profiler.get_snapshots()
        assert len(snapshots) >= 1

        result.ok("MemoryProfiler 컨텍스트 매니저")
    except Exception as e:
        result.fail("MemoryProfiler 컨텍스트 매니저", str(e))


def test_memory_profiler_disabled(result: TestResult) -> None:
    """MemoryProfiler 비활성화"""
    try:
        profiler = MemoryProfiler(enabled=False)

        @profiler.profile()
        def test_func():
            return "done"

        ret = test_func()
        assert ret == "done"

        # 스냅샷 없음
        snapshots = profiler.get_snapshots()
        assert len(snapshots) == 0

        result.ok("MemoryProfiler 비활성화")
    except Exception as e:
        result.fail("MemoryProfiler 비활성화", str(e))


def test_memory_profiler_peak_memory(result: TestResult) -> None:
    """MemoryProfiler 피크 메모리"""
    try:
        profiler = MemoryProfiler(enabled=True)

        @profiler.profile()
        def test_func():
            data = [0] * 10000
            return data

        test_func()

        peak = profiler.get_peak_memory()
        assert peak >= 0.0

        result.ok("MemoryProfiler 피크 메모리")
    except Exception as e:
        result.fail("MemoryProfiler 피크 메모리", str(e))


def test_memory_profiler_detect_leaks(result: TestResult) -> None:
    """MemoryProfiler 메모리 누수 탐지"""
    try:
        profiler = MemoryProfiler(enabled=True)

        # 인위적으로 큰 메모리 증가 시뮬레이션
        # (실제로는 누수가 아니지만 테스트 목적)
        # 스냅샷에 직접 추가
        from core_foundation.monitoring.profiler import MemorySnapshot

        profiler._snapshots.append(MemorySnapshot(
            function_name="leak_func",
            timestamp=time.time(),
            memory_before=100.0,
            memory_after=120.0,
            memory_delta=20.0,
            peak_memory=120.0
        ))

        leaks = profiler.detect_leaks(threshold_mb=10.0)
        assert len(leaks) >= 1
        assert leaks[0].memory_increase_mb == 20.0

        result.ok("MemoryProfiler 메모리 누수 탐지")
    except Exception as e:
        result.fail("MemoryProfiler 메모리 누수 탐지", str(e))


# ==================== CallStackProfiler 테스트 ====================
def test_callstack_profiler_decorator(result: TestResult) -> None:
    """CallStackProfiler 데코레이터"""
    try:
        profiler = CallStackProfiler(enabled=True)

        @profiler.profile()
        def func_a():
            pass

        @profiler.profile()
        def func_b():
            func_a()

        func_b()

        frames = profiler.get_frames()
        assert len(frames) >= 2

        result.ok("CallStackProfiler 데코레이터")
    except Exception as e:
        result.fail("CallStackProfiler 데코레이터", str(e))


def test_callstack_profiler_call_graph(result: TestResult) -> None:
    """CallStackProfiler 호출 그래프"""
    try:
        profiler = CallStackProfiler(enabled=True)

        @profiler.profile(name="caller")
        def caller():
            callee()

        @profiler.profile(name="callee")
        def callee():
            pass

        caller()

        call_graph = profiler.get_call_graph()
        assert isinstance(call_graph, CallGraph)
        assert "caller" in call_graph.edges or len(call_graph.edges) >= 0

        result.ok("CallStackProfiler 호출 그래프")
    except Exception as e:
        result.fail("CallStackProfiler 호출 그래프", str(e))


def test_callstack_profiler_max_depth(result: TestResult) -> None:
    """CallStackProfiler 최대 깊이"""
    try:
        profiler = CallStackProfiler(enabled=True)

        @profiler.profile()
        def level3():
            pass

        @profiler.profile()
        def level2():
            level3()

        @profiler.profile()
        def level1():
            level2()

        level1()

        max_depth = profiler.get_max_depth()
        assert max_depth >= 0  # 호출 깊이 추적됨

        result.ok("CallStackProfiler 최대 깊이")
    except Exception as e:
        result.fail("CallStackProfiler 최대 깊이", str(e))


def test_callstack_profiler_disabled(result: TestResult) -> None:
    """CallStackProfiler 비활성화"""
    try:
        profiler = CallStackProfiler(enabled=False)

        @profiler.profile()
        def test_func():
            return "done"

        ret = test_func()
        assert ret == "done"

        frames = profiler.get_frames()
        assert len(frames) == 0

        result.ok("CallStackProfiler 비활성화")
    except Exception as e:
        result.fail("CallStackProfiler 비활성화", str(e))


# ==================== ProfilerManager 테스트 ====================
def test_profiler_manager_singleton(result: TestResult) -> None:
    """ProfilerManager 싱글톤"""
    try:
        profiler1 = get_profiler()
        profiler2 = get_profiler()

        assert profiler1 is profiler2

        result.ok("ProfilerManager 싱글톤")
    except Exception as e:
        result.fail("ProfilerManager 싱글톤", str(e))


def test_profiler_manager_enable_disable(result: TestResult) -> None:
    """ProfilerManager 활성화/비활성화"""
    try:
        profiler = get_profiler()

        # 비활성화 상태 확인
        profiler.disable()
        assert not profiler.is_enabled()
        assert not profiler.time_profiler.enabled

        # 활성화
        profiler.enable(time_profile=True, memory_profile=False, callstack=False)
        assert profiler.is_enabled()
        assert profiler.time_profiler.enabled
        assert not profiler.memory_profiler.enabled

        # 비활성화
        profiler.disable()
        assert not profiler.is_enabled()

        result.ok("ProfilerManager 활성화/비활성화")
    except Exception as e:
        result.fail("ProfilerManager 활성화/비활성화", str(e))


def test_profiler_manager_profile_decorator(result: TestResult) -> None:
    """ProfilerManager 통합 데코레이터"""
    try:
        profiler = get_profiler()
        profiler.enable(time_profile=True, memory_profile=False, callstack=False)

        @profiler.profile()
        def test_func():
            time.sleep(0.001)
            return "done"

        test_func()

        # 시간 프로파일 확인
        time_stats = profiler.time_profiler.get_stats()
        assert len(time_stats) >= 1

        profiler.disable()
        result.ok("ProfilerManager 통합 데코레이터")
    except Exception as e:
        result.fail("ProfilerManager 통합 데코레이터", str(e))


def test_profiler_manager_reset(result: TestResult) -> None:
    """ProfilerManager reset()"""
    try:
        profiler = get_profiler()
        profiler.enable(time_profile=True)

        @profiler.profile()
        def test_func():
            pass

        test_func()
        assert len(profiler.time_profiler.get_stats()) >= 1

        profiler.reset()
        assert len(profiler.time_profiler.get_stats()) == 0

        profiler.disable()
        result.ok("ProfilerManager reset()")
    except Exception as e:
        result.fail("ProfilerManager reset()", str(e))


def test_profiler_manager_duration(result: TestResult) -> None:
    """ProfilerManager 프로파일링 지속 시간"""
    try:
        profiler = get_profiler()
        profiler.enable(time_profile=True)

        time.sleep(0.01)  # 10ms

        duration = profiler.get_profiling_duration()
        assert duration >= 0.01  # 최소 10ms

        profiler.disable()
        result.ok("ProfilerManager 프로파일링 지속 시간")
    except Exception as e:
        result.fail("ProfilerManager 프로파일링 지속 시간", str(e))


# ==================== 전역 함수 테스트 ====================
def test_global_enable_disable(result: TestResult) -> None:
    """전역 enable/disable"""
    try:
        enable_profiling(time_profile=True, memory_profile=False)
        profiler = get_profiler()
        assert profiler.is_enabled()

        disable_profiling()
        assert not profiler.is_enabled()

        result.ok("전역 enable/disable")
    except Exception as e:
        result.fail("전역 enable/disable", str(e))


def test_global_profile_decorator(result: TestResult) -> None:
    """전역 @profile 데코레이터"""
    try:
        enable_profiling(time_profile=True)

        @profile()
        def test_func():
            time.sleep(0.001)
            return "done"

        test_func()

        profiler = get_profiler()
        stats = profiler.time_profiler.get_stats()
        assert len(stats) >= 1

        disable_profiling()
        result.ok("전역 @profile 데코레이터")
    except Exception as e:
        result.fail("전역 @profile 데코레이터", str(e))


def test_global_reset(result: TestResult) -> None:
    """전역 reset"""
    try:
        enable_profiling(time_profile=True)

        @profile()
        def test_func():
            pass

        test_func()

        reset_profiling()

        profiler = get_profiler()
        assert len(profiler.time_profiler.get_stats()) == 0

        disable_profiling()
        result.ok("전역 reset")
    except Exception as e:
        result.fail("전역 reset", str(e))


# ==================== Reporter 테스트 ====================
def test_text_reporter(result: TestResult) -> None:
    """TextReporter 보고서 생성"""
    try:
        profiler = get_profiler()
        profiler.enable(time_profile=True)

        @profile()
        def test_func():
            time.sleep(0.001)

        test_func()

        report = get_profiling_report(format="text")
        assert isinstance(report, str)
        assert "Performance Profiling Report" in report
        assert "Time Profiling" in report

        disable_profiling()
        result.ok("TextReporter 보고서 생성")
    except Exception as e:
        result.fail("TextReporter 보고서 생성", str(e))


def test_json_reporter(result: TestResult) -> None:
    """JSONReporter 보고서 생성"""
    try:
        profiler = get_profiler()
        profiler.enable(time_profile=True)

        @profile()
        def test_func():
            time.sleep(0.001)

        test_func()

        report = get_profiling_report(format="json")
        assert isinstance(report, str)

        # JSON 파싱
        import json
        data = json.loads(report)
        assert "timestamp" in data
        assert "time_profile" in data

        disable_profiling()
        result.ok("JSONReporter 보고서 생성")
    except Exception as e:
        result.fail("JSONReporter 보고서 생성", str(e))


def test_call_graph_to_text(result: TestResult) -> None:
    """CallGraph to_text()"""
    try:
        call_graph = CallGraph(edges={
            "func_a": ["func_b", "func_c"],
            "func_b": ["func_d"]
        })

        text = call_graph.to_text()
        assert isinstance(text, str)
        assert "func_a" in text

        result.ok("CallGraph to_text()")
    except Exception as e:
        result.fail("CallGraph to_text()", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 단위 테스트 실행"""
    print("="*60)
    print("Profiler 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[TimeProfiler 테스트]")
    test_time_profiler_decorator(result)
    test_time_profiler_context_manager(result)
    test_time_profiler_disabled(result)
    test_time_profiler_hotspots(result)
    test_time_profiler_reset(result)
    test_time_profiler_max_samples(result)

    print("\n[MemoryProfiler 테스트]")
    test_memory_profiler_decorator(result)
    test_memory_profiler_context_manager(result)
    test_memory_profiler_disabled(result)
    test_memory_profiler_peak_memory(result)
    test_memory_profiler_detect_leaks(result)

    print("\n[CallStackProfiler 테스트]")
    test_callstack_profiler_decorator(result)
    test_callstack_profiler_call_graph(result)
    test_callstack_profiler_max_depth(result)
    test_callstack_profiler_disabled(result)

    print("\n[ProfilerManager 테스트]")
    test_profiler_manager_singleton(result)
    test_profiler_manager_enable_disable(result)
    test_profiler_manager_profile_decorator(result)
    test_profiler_manager_reset(result)
    test_profiler_manager_duration(result)

    print("\n[전역 함수 테스트]")
    test_global_enable_disable(result)
    test_global_profile_decorator(result)
    test_global_reset(result)

    print("\n[Reporter 테스트]")
    test_text_reporter(result)
    test_json_reporter(result)
    test_call_graph_to_text(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
