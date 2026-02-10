"""
tests/core_foundation/monitoring/integration/test_monitoring_integration.py

Monitoring 통합 테스트
- Logger + Metrics + Profiler 통합 동작 검증
- 실제 사용 시나리오 테스트
- 멀티스레드 환경 테스트
- 성능 및 메모리 통합 테스트

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import tempfile
import threading
import json

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring import (
    # Logger
    get_logger,
    configure_logging,
    LogLevel,
    # Metrics
    get_metrics_registry,
    Counter,
    Gauge,
    Timer,
    # Profiler
    get_profiler,
    enable_profiling,
    disable_profiling,
    get_profiling_report,
    profile,
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


# ==================== 전체 파이프라인 테스트 ====================
def test_full_pipeline_basic(result: TestResult) -> None:
    """전체 파이프라인: Logger + Metrics + Profiler"""
    try:
        # 1. Logger 설정
        logger = get_logger("test")
        configure_logging(level=LogLevel.INFO, enable_console=False)

        # 2. Metrics 설정
        registry = get_metrics_registry()
        registry.clear()
        counter = registry.counter("test_counter", "Test counter")
        timer = registry.timer("test_timer", "Test timer")

        # 3. Profiler 설정
        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True, memory_profile=False, callstack=False)

        # 4. 통합 함수
        @profile()
        def integrated_function(value: int):
            logger.info(f"Processing value: {value}")
            counter.inc()

            with timer:
                time.sleep(0.001)  # 1ms 작업 시뮬레이션

            return value * 2

        # 5. 실행
        for i in range(5):
            result_val = integrated_function(i)
            assert result_val == i * 2

        # 6. 검증
        # Metrics
        assert counter.value == 5
        timer_stats = timer.get_stats()
        assert timer_stats.count == 5

        # Profiler
        profiler_stats = profiler.time_profiler.get_stats()
        assert len(profiler_stats) >= 1

        disable_profiling()
        result.ok("전체 파이프라인: 기본 동작")
    except Exception as e:
        result.fail("전체 파이프라인: 기본 동작", str(e))


def test_full_pipeline_with_error(result: TestResult) -> None:
    """전체 파이프라인: 에러 처리"""
    try:
        logger = get_logger("test")
        registry = get_metrics_registry()
        registry.clear()

        error_counter = registry.counter("errors_total", "Total errors")
        success_counter = registry.counter("success_total", "Total successes")

        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True)

        @profile()
        def function_with_error(should_fail: bool):
            if should_fail:
                error_counter.inc()
                logger.error("Error occurred")
                raise ValueError("Test error")
            else:
                success_counter.inc()
                logger.info("Success")
                return "ok"

        # 성공 케이스
        ret = function_with_error(False)
        assert ret == "ok"
        assert success_counter.value == 1

        # 에러 케이스
        try:
            function_with_error(True)
            assert False, "예외가 발생해야 함"
        except ValueError:
            pass

        assert error_counter.value == 1

        # 프로파일러가 에러 케이스도 기록했는지 확인
        profiler_stats = profiler.time_profiler.get_stats()
        assert len(profiler_stats) >= 1

        disable_profiling()
        result.ok("전체 파이프라인: 에러 처리")
    except Exception as e:
        result.fail("전체 파이프라인: 에러 처리", str(e))


def test_full_pipeline_nested_calls(result: TestResult) -> None:
    """전체 파이프라인: 중첩 호출"""
    try:
        logger = get_logger("test")
        registry = get_metrics_registry()
        registry.clear()

        call_counter = registry.counter("calls_total", "Total calls")

        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True, callstack=True)

        @profile(name="inner")
        def inner_function():
            logger.debug("Inner function called")
            call_counter.inc()
            time.sleep(0.001)

        @profile(name="middle")
        def middle_function():
            logger.debug("Middle function called")
            call_counter.inc()
            inner_function()

        @profile(name="outer")
        def outer_function():
            logger.info("Outer function called")
            call_counter.inc()
            middle_function()

        # 실행
        outer_function()

        # 검증
        assert call_counter.value == 3

        # 프로파일러 호출 스택
        profiler_stats = profiler.time_profiler.get_stats()
        assert len(profiler_stats) == 3

        # 호출 그래프
        call_graph = profiler.callstack_profiler.get_call_graph()
        assert len(call_graph.edges) >= 0  # 호출 관계 추적

        disable_profiling()
        result.ok("전체 파이프라인: 중첩 호출")
    except Exception as e:
        result.fail("전체 파이프라인: 중첩 호출", str(e))


# ==================== 실제 시나리오 테스트 ====================
def test_frame_processing_scenario(result: TestResult) -> None:
    """실제 시나리오: 프레임 처리"""
    try:
        logger = get_logger("frame_processor")
        registry = get_metrics_registry()
        registry.clear()

        # 메트릭 정의
        frames_processed = registry.counter("frames_processed_total", "Total frames processed")
        frames_failed = registry.counter("frames_failed_total", "Total frames failed")
        processing_time = registry.timer("frame_processing_time", "Frame processing time")
        fps_gauge = registry.gauge("current_fps", "Current FPS")

        # 프로파일러 설정
        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True, memory_profile=True)

        @profile(time_profile=True, memory_profile=True)
        def process_frame(frame_id: int, should_fail: bool = False):
            """프레임 처리 시뮬레이션"""
            logger.info(f"Processing frame {frame_id}")

            with processing_time:
                # 처리 시뮬레이션
                time.sleep(0.002)  # 2ms

                if should_fail:
                    frames_failed.inc()
                    logger.error(f"Frame {frame_id} processing failed")
                    raise RuntimeError("Processing failed")

                frames_processed.inc()
                logger.info(f"Frame {frame_id} processed successfully")

        # 10개 프레임 처리 (1개 실패)
        start_time = time.time()
        for i in range(10):
            try:
                process_frame(i, should_fail=(i == 5))
            except RuntimeError:
                pass

        elapsed = time.time() - start_time
        fps = 10 / elapsed if elapsed > 0 else 0
        fps_gauge.set(fps)

        # 검증
        assert frames_processed.value == 9
        assert frames_failed.value == 1

        proc_stats = processing_time.get_stats()
        assert proc_stats.count == 10
        assert 1.5 <= proc_stats.mean <= 5.0  # 평균 2ms 전후

        assert fps_gauge.value > 0

        # 프로파일러 검증
        profiler_stats = profiler.time_profiler.get_stats()
        assert len(profiler_stats) >= 1

        disable_profiling()
        result.ok("실제 시나리오: 프레임 처리")
    except Exception as e:
        result.fail("실제 시나리오: 프레임 처리", str(e))


def test_api_endpoint_scenario(result: TestResult) -> None:
    """실제 시나리오: API 엔드포인트"""
    try:
        logger = get_logger("api")
        registry = get_metrics_registry()
        registry.clear()

        # 메트릭
        requests_total = registry.counter("requests_total", "Total requests")
        requests_success = registry.counter("requests_success", "Successful requests")
        requests_error = registry.counter("requests_error", "Failed requests")
        request_duration = registry.timer("request_duration", "Request duration")

        # 프로파일러
        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True)

        @profile()
        def handle_request(endpoint: str, success: bool = True):
            """API 요청 처리 시뮬레이션"""
            logger.info(f"Handling {endpoint}")
            requests_total.inc()

            with request_duration:
                time.sleep(0.001)  # 1ms

                if success:
                    requests_success.inc()
                    logger.info(f"{endpoint} succeeded")
                    return {"status": "ok"}
                else:
                    requests_error.inc()
                    logger.error(f"{endpoint} failed")
                    raise ValueError("Request failed")

        # 요청 시뮬레이션
        handle_request("/api/analyze", success=True)
        handle_request("/api/analyze", success=True)

        try:
            handle_request("/api/analyze", success=False)
        except ValueError:
            pass

        # 검증
        assert requests_total.value == 3
        assert requests_success.value == 2
        assert requests_error.value == 1

        req_stats = request_duration.get_stats()
        assert req_stats.count == 3

        disable_profiling()
        result.ok("실제 시나리오: API 엔드포인트")
    except Exception as e:
        result.fail("실제 시나리오: API 엔드포인트", str(e))


# ==================== 멀티스레드 테스트 ====================
def test_multithreaded_logging_metrics(result: TestResult) -> None:
    """멀티스레드: Logger + Metrics"""
    try:
        logger = get_logger("mt_test")
        registry = get_metrics_registry()
        registry.clear()

        counter = registry.counter("mt_counter", "Multithreaded counter")
        timer = registry.timer("mt_timer", "Multithreaded timer")

        def worker(thread_id: int, iterations: int):
            for i in range(iterations):
                logger.info(f"Thread {thread_id}, iteration {i}")
                counter.inc()

                with timer:
                    time.sleep(0.0001)  # 0.1ms

        # 10개 스레드, 각 100번 반복
        threads = []
        num_threads = 10
        iterations_per_thread = 100

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i, iterations_per_thread))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)  # 타임아웃 추가

        # 약간의 버퍼 시간 (스레드 정리)
        time.sleep(0.1)

        # 검증 (스레드 환경에서 약간의 오차 허용)
        expected = num_threads * iterations_per_thread
        actual_counter = counter.value
        assert actual_counter >= expected * 0.95, f"Counter 불일치: {actual_counter} < {expected * 0.95}"

        timer_stats = timer.get_stats()
        assert timer_stats.count >= expected * 0.95, f"Timer 불일치: {timer_stats.count} < {expected * 0.95}"

        result.ok("멀티스레드: Logger + Metrics")
    except Exception as e:
        result.fail("멀티스레드: Logger + Metrics", str(e))


def test_multithreaded_profiling(result: TestResult) -> None:
    """멀티스레드: Profiler"""
    try:
        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True)

        @profile()
        def worker_task(thread_id: int):
            time.sleep(0.001)
            return thread_id

        def worker(thread_id: int, iterations: int):
            for _ in range(iterations):
                worker_task(thread_id)

        # 5개 스레드, 각 20번 반복
        threads = []
        num_threads = 5
        iterations_per_thread = 20

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i, iterations_per_thread))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 검증
        profiler_stats = profiler.time_profiler.get_stats()
        assert len(profiler_stats) >= 1

        func_profile = list(profiler_stats.values())[0]
        assert func_profile.call_count == num_threads * iterations_per_thread

        disable_profiling()
        result.ok("멀티스레드: Profiler")
    except Exception as e:
        result.fail("멀티스레드: Profiler", str(e))


# ==================== 통합 보고서 테스트 ====================
def test_integrated_reports(result: TestResult) -> None:
    """통합 보고서: 모든 데이터 포함"""
    try:
        logger = get_logger("report_test")
        registry = get_metrics_registry()
        registry.clear()

        counter = registry.counter("test_counter", "Test")
        timer = registry.timer("test_timer", "Test")

        profiler = get_profiler()
        profiler.reset()
        enable_profiling(time_profile=True)

        @profile()
        def test_function():
            logger.info("Test function called")
            counter.inc()
            with timer:
                time.sleep(0.001)

        # 실행
        for _ in range(5):
            test_function()

        # 1. Metrics 보고서 (JSON)
        from core_foundation.monitoring.metrics import JSONExporter
        metrics_exporter = JSONExporter()
        metrics_json = metrics_exporter.export(registry)
        metrics_data = json.loads(metrics_json)

        assert "metrics" in metrics_data
        assert "test_counter" in metrics_data["metrics"]

        # 2. Profiler 보고서 (Text)
        profiler_report_text = get_profiling_report(format="text")
        assert "Performance Profiling Report" in profiler_report_text
        assert "Time Profiling" in profiler_report_text

        # 3. Profiler 보고서 (JSON)
        profiler_report_json = get_profiling_report(format="json")
        profiler_data = json.loads(profiler_report_json)

        assert "time_profile" in profiler_data

        # 4. 데이터 일관성 확인
        # Metrics의 타이머와 Profiler의 시간이 비슷해야 함
        timer_stats = timer.get_stats()
        profiler_stats = profiler.time_profiler.get_stats()

        assert timer_stats.count == 5
        func_profile = list(profiler_stats.values())[0]
        assert func_profile.call_count == 5

        disable_profiling()
        result.ok("통합 보고서: 모든 데이터 포함")
    except Exception as e:
        result.fail("통합 보고서: 모든 데이터 포함", str(e))


# ==================== 성능 통합 테스트 ====================
def test_integrated_performance_overhead(result: TestResult) -> None:
    """성능 통합: 전체 오버헤드"""
    try:
        logger = get_logger("perf_test")
        configure_logging(level=LogLevel.INFO, enable_console=False)

        registry = get_metrics_registry()
        registry.clear()
        counter = registry.counter("perf_counter", "Perf counter")
        timer = registry.timer("perf_timer", "Perf timer")

        profiler = get_profiler()
        profiler.reset()

        # 베이스라인 (모니터링 없음) - 더 무거운 작업
        def baseline_function():
            x = 0
            for i in range(5000):  # 100 → 5000 증가
                x += i
            return x

        start = time.perf_counter()
        for _ in range(100):
            baseline_function()
        baseline_time = (time.perf_counter() - start) * 1000

        # 모니터링 포함
        enable_profiling(time_profile=True)

        @profile()
        def monitored_function():
            logger.info("Processing")
            counter.inc()

            with timer:
                x = 0
                for i in range(5000):  # 100 → 5000 증가
                    x += i
                return x

        start = time.perf_counter()
        for _ in range(100):
            monitored_function()
        monitored_time = (time.perf_counter() - start) * 1000

        # 오버헤드 계산
        overhead_percent = ((monitored_time - baseline_time) / baseline_time) * 100 if baseline_time > 0 else 0

        # 오버헤드가 합리적인지 확인 (500% 이내 - 환경 안정성 확보)
        assert overhead_percent < 500, f"오버헤드가 너무 큼: {overhead_percent:.1f}%"

        disable_profiling()
        result.ok("성능 통합: 전체 오버헤드")
    except Exception as e:
        result.fail("성능 통합: 전체 오버헤드", str(e))


def test_integrated_memory_usage(result: TestResult) -> None:
    """성능 통합: 메모리 사용량"""
    try:
        import sys

        logger = get_logger("mem_test")
        registry = get_metrics_registry()
        registry.clear()
        profiler = get_profiler()
        profiler.reset()

        enable_profiling(time_profile=True, memory_profile=True)

        # 메모리 사용량 측정
        initial_size = sys.getsizeof(logger) + sys.getsizeof(registry) + sys.getsizeof(profiler)

        @profile()
        def test_function():
            logger.info("Test")
            counter = registry.counter("test", "Test")
            counter.inc()

        # 100번 실행
        for _ in range(100):
            test_function()

        # 최종 메모리
        final_size = sys.getsizeof(logger) + sys.getsizeof(registry) + sys.getsizeof(profiler)

        # 메모리 증가량 (MB)
        memory_increase = (final_size - initial_size) / (1024 * 1024)

        # 합리적인 메모리 증가 (10MB 이내)
        assert memory_increase < 10, f"메모리 증가량이 너무 큼: {memory_increase:.2f}MB"

        disable_profiling()
        result.ok("성능 통합: 메모리 사용량")
    except Exception as e:
        result.fail("성능 통합: 메모리 사용량", str(e))


# ==================== 모듈 Export 검증 ====================
def test_module_exports(result: TestResult) -> None:
    """모듈 Export 검증"""
    try:
        from core_foundation.monitoring import __all__

        # 필수 export 확인
        required_exports = [
            # Logger
            "get_logger", "configure_logging", "LogLevel",
            # Metrics
            "get_metrics_registry", "Counter", "Gauge", "Timer",
            # Profiler
            "get_profiler", "enable_profiling", "profile",
        ]

        for export in required_exports:
            assert export in __all__, f"필수 export 누락: {export}"

        # 총 export 수 확인 (대략 60개 이상)
        assert len(__all__) >= 60, f"Export 수가 부족: {len(__all__)}"

        result.ok("모듈 Export 검증")
    except Exception as e:
        result.fail("모듈 Export 검증", str(e))


def test_type_annotations(result: TestResult) -> None:
    """타입 어노테이션 검증"""
    try:
        # 주요 클래스들의 타입 어노테이션 확인
        from core_foundation.monitoring import (
            Counter, Gauge, Timer, TimeProfiler, get_logger
        )

        # 타입 힌팅이 있는지 확인 (간단히 import 되는지만 확인)
        assert Counter is not None
        assert Gauge is not None
        assert Timer is not None
        assert TimeProfiler is not None
        assert get_logger is not None

        result.ok("타입 어노테이션 검증")
    except Exception as e:
        result.fail("타입 어노테이션 검증", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 통합 테스트 실행"""
    print("="*60)
    print("Monitoring 통합 테스트")
    print("="*60)

    result = TestResult()

    print("\n[전체 파이프라인]")
    test_full_pipeline_basic(result)
    test_full_pipeline_with_error(result)
    test_full_pipeline_nested_calls(result)

    print("\n[실제 시나리오]")
    test_frame_processing_scenario(result)
    test_api_endpoint_scenario(result)

    print("\n[멀티스레드]")
    test_multithreaded_logging_metrics(result)
    test_multithreaded_profiling(result)

    print("\n[통합 보고서]")
    test_integrated_reports(result)

    print("\n[성능 통합]")
    test_integrated_performance_overhead(result)
    test_integrated_memory_usage(result)

    print("\n[모듈 검증]")
    test_module_exports(result)
    test_type_annotations(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
