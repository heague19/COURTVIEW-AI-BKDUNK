"""
tests/core_foundation/monitoring/performance/test_metrics_perf.py

Metrics 성능 테스트
- 메트릭 기록 오버헤드: <0.01ms
- 초당 메트릭 수집: >100,000 metrics/sec
- 통계 계산: <1ms (1000 샘플)
- 데이터 내보내기: <100ms (1000 메트릭)
- 메모리 사용량: <10MB (1000 메트릭)

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import statistics
import threading
import tempfile

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.metrics import (
    Counter,
    Gauge,
    Histogram,
    Timer,
    RollingWindow,
    TimeWindow,
    MetricsRegistry,
    JSONExporter,
    CSVExporter,
    PrometheusExporter,
)


# ==================== 성능 측정 유틸리티 ====================
def measure_time_ms(func, iterations: int = 1000) -> float:
    """
    함수 실행 시간 측정 (밀리초)

    Args:
        func: 측정할 함수
        iterations: 반복 횟수

    Returns:
        평균 실행 시간 (ms)
    """
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # ms로 변환

    return statistics.mean(times)


def measure_throughput(func, duration_sec: float = 1.0) -> float:
    """
    처리량 측정 (ops/sec)

    Args:
        func: 측정할 함수
        duration_sec: 측정 시간

    Returns:
        초당 처리량
    """
    count = 0
    start = time.perf_counter()
    end_time = start + duration_sec

    while time.perf_counter() < end_time:
        func()
        count += 1

    elapsed = time.perf_counter() - start
    return count / elapsed


def measure_memory_mb(obj) -> float:
    """
    객체 메모리 사용량 측정 (MB)

    Args:
        obj: 측정할 객체

    Returns:
        메모리 사용량 (MB)
    """
    import sys

    # 기본 객체 크기
    size = sys.getsizeof(obj)

    # __dict__ 크기 (있다면)
    if hasattr(obj, '__dict__'):
        size += sys.getsizeof(obj.__dict__)
        for key, value in obj.__dict__.items():
            size += sys.getsizeof(key)
            if isinstance(value, (str, int, float, bool)):
                size += sys.getsizeof(value)
            elif isinstance(value, (list, dict)):
                size += sys.getsizeof(value)
                # 리스트/딕셔너리 내부 샘플링
                if isinstance(value, list) and len(value) > 0:
                    size += sys.getsizeof(value[0]) * min(len(value), 100)
                elif isinstance(value, dict) and len(value) > 0:
                    sample_items = list(value.items())[:100]
                    for k, v in sample_items:
                        size += sys.getsizeof(k) + sys.getsizeof(v)

    return size / (1024 * 1024)  # MB로 변환


# ==================== 성능 테스트 결과 ====================
class PerformanceTestResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def record(self, test_name: str, actual: float, target: float, unit: str, passed: bool) -> None:
        """테스트 결과 기록"""
        self.results.append({
            "test": test_name,
            "actual": actual,
            "target": target,
            "unit": unit,
            "passed": passed
        })

        if passed:
            self.passed += 1
            status = "[PASS]"
        else:
            self.failed += 1
            status = "[FAIL]"

        print(f"{status} {test_name}: {actual:.4f}{unit} (목표: {'>' if 'throughput' in test_name.lower() or '/sec' in unit else '<'}{target}{unit})")

    def summary(self) -> None:
        """성능 테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")

        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for result in self.results:
                if not result["passed"]:
                    comp = ">" if "throughput" in result["test"].lower() else "<"
                    print(f"  - {result['test']}: {result['actual']:.4f}{result['unit']} (목표: {comp}{result['target']}{result['unit']})")

        print(f"{'='*70}")


# ==================== 메트릭 기록 오버헤드 ====================
def test_counter_overhead(result: PerformanceTestResult) -> None:
    """Counter.inc() 오버헤드 (목표: <0.001ms)"""
    test_name = "Counter.inc() 오버헤드"

    counter = Counter("test", "Test")

    def inc_counter():
        counter.inc()

    avg_time = measure_time_ms(inc_counter, iterations=10000)
    target = 0.001  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_gauge_overhead(result: PerformanceTestResult) -> None:
    """Gauge.set() 오버헤드 (목표: <0.001ms)"""
    test_name = "Gauge.set() 오버헤드"

    gauge = Gauge("test", "Test")

    def set_gauge():
        gauge.set(42.5)

    avg_time = measure_time_ms(set_gauge, iterations=10000)
    target = 0.001  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_histogram_overhead(result: PerformanceTestResult) -> None:
    """Histogram.observe() 오버헤드 (목표: <0.01ms)"""
    test_name = "Histogram.observe() 오버헤드"

    histogram = Histogram("test", "Test")

    def observe_histogram():
        histogram.observe(42.5)

    avg_time = measure_time_ms(observe_histogram, iterations=10000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_timer_overhead(result: PerformanceTestResult) -> None:
    """Timer 측정 오버헤드 (목표: <0.01ms)"""
    test_name = "Timer 측정 오버헤드"

    timer = Timer("test", "Test")

    def use_timer():
        with timer:
            pass  # 빈 동작

    avg_time = measure_time_ms(use_timer, iterations=1000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 처리량 테스트 ====================
def test_counter_throughput(result: PerformanceTestResult) -> None:
    """Counter 처리량 (목표: >100,000 ops/sec)"""
    test_name = "Counter 처리량"

    counter = Counter("test", "Test")

    def inc_counter():
        counter.inc()

    throughput = measure_throughput(inc_counter, duration_sec=0.5)
    target = 100000.0  # ops/sec
    passed = throughput > target

    result.record(test_name, throughput, target, " ops/sec", passed)


def test_gauge_throughput(result: PerformanceTestResult) -> None:
    """Gauge 처리량 (목표: >100,000 ops/sec)"""
    test_name = "Gauge 처리량"

    gauge = Gauge("test", "Test")

    def set_gauge():
        gauge.set(42.5)

    throughput = measure_throughput(set_gauge, duration_sec=0.5)
    target = 100000.0  # ops/sec
    passed = throughput > target

    result.record(test_name, throughput, target, " ops/sec", passed)


def test_histogram_throughput(result: PerformanceTestResult) -> None:
    """Histogram 처리량 (목표: >10,000 obs/sec)"""
    test_name = "Histogram 처리량"

    histogram = Histogram("test", "Test")

    def observe_histogram():
        histogram.observe(42.5)

    throughput = measure_throughput(observe_histogram, duration_sec=0.5)
    target = 10000.0  # obs/sec
    passed = throughput > target

    result.record(test_name, throughput, target, " obs/sec", passed)


# ==================== 통계 계산 성능 ====================
def test_statistics_calculation(result: PerformanceTestResult) -> None:
    """Statistics 계산 (1000 샘플, 목표: <1ms)"""
    test_name = "Statistics 계산 (1000 샘플)"

    histogram = Histogram("test", "Test")

    # 1000개 샘플 추가
    for i in range(1000):
        histogram.observe(i)

    def calc_stats():
        histogram.get_stats()

    avg_time = measure_time_ms(calc_stats, iterations=100)
    target = 1.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_rolling_window_stats(result: PerformanceTestResult) -> None:
    """RollingWindow 통계 (1000 샘플, 목표: <1ms)"""
    test_name = "RollingWindow 통계 (1000 샘플)"

    window = RollingWindow(max_size=1000)

    # 1000개 샘플 추가
    for i in range(1000):
        window.add(i)

    def calc_stats():
        window.get_stats()

    avg_time = measure_time_ms(calc_stats, iterations=100)
    target = 1.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 내보내기 성능 ====================
def test_json_export_performance(result: PerformanceTestResult) -> None:
    """JSONExporter (1000 메트릭, 목표: <100ms)"""
    test_name = "JSONExporter (1000 메트릭)"

    registry = MetricsRegistry()

    # 1000개 메트릭 생성
    for i in range(1000):
        counter = registry.counter(f"metric_{i}", f"Metric {i}")
        counter.inc(i)

    exporter = JSONExporter()

    def export_json():
        exporter.export(registry)

    avg_time = measure_time_ms(export_json, iterations=10)
    target = 100.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_csv_export_performance(result: PerformanceTestResult) -> None:
    """CSVExporter (1000 메트릭, 목표: <100ms)"""
    test_name = "CSVExporter (1000 메트릭)"

    registry = MetricsRegistry()

    # 1000개 메트릭 생성
    for i in range(1000):
        counter = registry.counter(f"metric_{i}", f"Metric {i}")
        counter.inc(i)

    exporter = CSVExporter()

    def export_csv():
        exporter.export(registry)

    avg_time = measure_time_ms(export_csv, iterations=10)
    target = 100.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_prometheus_export_performance(result: PerformanceTestResult) -> None:
    """PrometheusExporter (1000 메트릭, 목표: <100ms)"""
    test_name = "PrometheusExporter (1000 메트릭)"

    registry = MetricsRegistry()

    # 1000개 메트릭 생성
    for i in range(1000):
        counter = registry.counter(f"metric_{i}", f"Metric {i}")
        counter.inc(i)

    exporter = PrometheusExporter()

    def export_prometheus():
        exporter.export(registry)

    avg_time = measure_time_ms(export_prometheus, iterations=10)
    target = 100.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메모리 사용량 ====================
def test_registry_memory(result: PerformanceTestResult) -> None:
    """MetricsRegistry 메모리 (1000 메트릭, 목표: <10MB)"""
    test_name = "MetricsRegistry 메모리 (1000 메트릭)"

    registry = MetricsRegistry()

    # 1000개 메트릭 생성
    for i in range(1000):
        counter = registry.counter(f"metric_{i}", f"Metric {i}")
        counter.inc(i)

    memory_mb = measure_memory_mb(registry)
    target = 10.0  # MB
    passed = memory_mb < target

    result.record(test_name, memory_mb, target, "MB", passed)


# ==================== 멀티스레드 안전성 ====================
def test_multithreaded_counter(result: PerformanceTestResult) -> None:
    """멀티스레드 Counter (동시성)"""
    test_name = "멀티스레드 Counter"

    counter = Counter("test", "Test")
    num_threads = 10
    increments_per_thread = 1000

    def increment():
        for _ in range(increments_per_thread):
            counter.inc()

    start = time.perf_counter()

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=increment)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = (time.perf_counter() - start) * 1000  # ms

    # 정확성 검증
    expected = num_threads * increments_per_thread
    actual = counter.value
    accuracy = (actual / expected) * 100 if expected > 0 else 0

    # 성능 검증 (1초 이내)
    target = 1000.0  # ms
    passed = elapsed < target and accuracy >= 99.0

    result.record(test_name, elapsed, target, "ms", passed)


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("Metrics 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[메트릭 기록 오버헤드]")
    test_counter_overhead(result)
    test_gauge_overhead(result)
    test_histogram_overhead(result)
    test_timer_overhead(result)

    print("\n[처리량]")
    test_counter_throughput(result)
    test_gauge_throughput(result)
    test_histogram_throughput(result)

    print("\n[통계 계산]")
    test_statistics_calculation(result)
    test_rolling_window_stats(result)

    print("\n[내보내기 성능]")
    test_json_export_performance(result)
    test_csv_export_performance(result)
    test_prometheus_export_performance(result)

    print("\n[메모리 사용량]")
    test_registry_memory(result)

    print("\n[멀티스레드]")
    test_multithreaded_counter(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
