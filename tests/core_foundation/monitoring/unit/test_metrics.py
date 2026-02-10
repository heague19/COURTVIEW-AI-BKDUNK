"""
tests/core_foundation/monitoring/unit/test_metrics.py

Metrics 단위 테스트
- Counter, Gauge, Histogram, Timer 동작 검증
- RollingWindow, TimeWindow 동작 검증
- MetricsRegistry 싱글톤 및 관리 검증
- Exporter (JSON, CSV, Prometheus) 검증

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import tempfile
import json
import csv as csv_module

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
    get_metrics_registry,
    JSONExporter,
    CSVExporter,
    PrometheusExporter,
    Statistics,
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


# ==================== Counter 테스트 ====================
def test_counter_creation(result: TestResult) -> None:
    """Counter 생성 및 초기값"""
    try:
        counter = Counter("test_counter", "Test counter")
        assert counter.name == "test_counter"
        assert counter.description == "Test counter"
        assert counter.value == 0.0

        result.ok("Counter 생성 및 초기값")
    except Exception as e:
        result.fail("Counter 생성 및 초기값", str(e))


def test_counter_inc(result: TestResult) -> None:
    """Counter inc() 증가"""
    try:
        counter = Counter("test", "Test")

        counter.inc()
        assert counter.value == 1.0

        counter.inc(5)
        assert counter.value == 6.0

        counter.inc(2.5)
        assert counter.value == 8.5

        result.ok("Counter inc() 증가")
    except Exception as e:
        result.fail("Counter inc() 증가", str(e))


def test_counter_negative(result: TestResult) -> None:
    """Counter 음수 증가 방지"""
    try:
        counter = Counter("test", "Test")

        try:
            counter.inc(-1)
            assert False, "음수 증가가 허용되면 안됨"
        except ValueError:
            pass  # 예상된 예외

        result.ok("Counter 음수 증가 방지")
    except Exception as e:
        result.fail("Counter 음수 증가 방지", str(e))


def test_counter_reset(result: TestResult) -> None:
    """Counter reset()"""
    try:
        counter = Counter("test", "Test")
        counter.inc(10)
        assert counter.value == 10.0

        counter.reset()
        assert counter.value == 0.0

        result.ok("Counter reset()")
    except Exception as e:
        result.fail("Counter reset()", str(e))


# ==================== Gauge 테스트 ====================
def test_gauge_creation(result: TestResult) -> None:
    """Gauge 생성 및 초기값"""
    try:
        gauge = Gauge("test_gauge", "Test gauge")
        assert gauge.name == "test_gauge"
        assert gauge.value == 0.0

        result.ok("Gauge 생성 및 초기값")
    except Exception as e:
        result.fail("Gauge 생성 및 초기값", str(e))


def test_gauge_set(result: TestResult) -> None:
    """Gauge set()"""
    try:
        gauge = Gauge("test", "Test")

        gauge.set(42.5)
        assert gauge.value == 42.5

        gauge.set(-10.0)
        assert gauge.value == -10.0

        result.ok("Gauge set()")
    except Exception as e:
        result.fail("Gauge set()", str(e))


def test_gauge_inc_dec(result: TestResult) -> None:
    """Gauge inc() / dec()"""
    try:
        gauge = Gauge("test", "Test")
        gauge.set(10)

        gauge.inc()
        assert gauge.value == 11.0

        gauge.inc(5)
        assert gauge.value == 16.0

        gauge.dec()
        assert gauge.value == 15.0

        gauge.dec(10)
        assert gauge.value == 5.0

        result.ok("Gauge inc() / dec()")
    except Exception as e:
        result.fail("Gauge inc() / dec()", str(e))


# ==================== Histogram 테스트 ====================
def test_histogram_creation(result: TestResult) -> None:
    """Histogram 생성 및 초기값"""
    try:
        histogram = Histogram("test_hist", "Test histogram")
        assert histogram.name == "test_hist"
        assert histogram.get_stats() is None  # 샘플 없음

        result.ok("Histogram 생성 및 초기값")
    except Exception as e:
        result.fail("Histogram 생성 및 초기값", str(e))


def test_histogram_observe(result: TestResult) -> None:
    """Histogram observe() 기록"""
    try:
        histogram = Histogram("test", "Test")

        for i in range(10):
            histogram.observe(i)

        stats = histogram.get_stats()
        assert stats is not None
        assert stats.count == 10
        assert stats.min == 0
        assert stats.max == 9

        result.ok("Histogram observe() 기록")
    except Exception as e:
        result.fail("Histogram observe() 기록", str(e))


def test_histogram_stats(result: TestResult) -> None:
    """Histogram 통계 계산"""
    try:
        histogram = Histogram("test", "Test")

        # 1-100 관찰
        for i in range(1, 101):
            histogram.observe(i)

        stats = histogram.get_stats()
        assert stats is not None
        assert stats.count == 100
        assert 49 <= stats.mean <= 51  # 평균 ~50
        assert 45 <= stats.median <= 55  # 중앙값 ~50
        assert stats.min == 1
        assert stats.max == 100
        assert 90 <= stats.p90 <= 95
        assert 95 <= stats.p95 <= 100
        assert 99 <= stats.p99 <= 100

        result.ok("Histogram 통계 계산")
    except Exception as e:
        result.fail("Histogram 통계 계산", str(e))


def test_histogram_percentiles(result: TestResult) -> None:
    """Histogram 백분위수 계산"""
    try:
        histogram = Histogram("test", "Test")

        # 0-99 (100개)
        for i in range(100):
            histogram.observe(i)

        stats = histogram.get_stats()
        assert stats is not None

        # P50 ~49.5
        assert 45 <= stats.p50 <= 55

        # P90 ~89.1
        assert 85 <= stats.p90 <= 95

        # P95 ~94.05
        assert 90 <= stats.p95 <= 100

        # P99 ~98.01
        assert 95 <= stats.p99 <= 100

        result.ok("Histogram 백분위수 계산")
    except Exception as e:
        result.fail("Histogram 백분위수 계산", str(e))


def test_histogram_buckets(result: TestResult) -> None:
    """Histogram 버킷 카운트"""
    try:
        histogram = Histogram(
            "test",
            "Test",
            buckets=[1, 5, 10, 50, 100]
        )

        # 0-100까지 관찰
        for i in range(101):
            histogram.observe(i)

        buckets = histogram.get_bucket_counts()
        assert buckets[1] == 2  # 0, 1
        assert buckets[5] == 6  # 0-5
        assert buckets[10] == 11  # 0-10
        assert buckets[50] == 51  # 0-50
        assert buckets[100] == 101  # 0-100
        assert buckets[float('inf')] == 101  # 전체

        result.ok("Histogram 버킷 카운트")
    except Exception as e:
        result.fail("Histogram 버킷 카운트", str(e))


def test_histogram_max_samples(result: TestResult) -> None:
    """Histogram 최대 샘플 제한"""
    try:
        histogram = Histogram("test", "Test", max_samples=100)

        # 200개 관찰
        for i in range(200):
            histogram.observe(i)

        stats = histogram.get_stats()
        assert stats is not None
        assert stats.count == 100  # 최대 100개만 유지

        result.ok("Histogram 최대 샘플 제한")
    except Exception as e:
        result.fail("Histogram 최대 샘플 제한", str(e))


def test_histogram_single_sample(result: TestResult) -> None:
    """Histogram 단일 샘플"""
    try:
        histogram = Histogram("test", "Test")
        histogram.observe(42.5)

        stats = histogram.get_stats()
        assert stats is not None
        assert stats.count == 1
        assert stats.mean == 42.5
        assert stats.min == 42.5
        assert stats.max == 42.5
        assert stats.std == 0.0

        result.ok("Histogram 단일 샘플")
    except Exception as e:
        result.fail("Histogram 단일 샘플", str(e))


# ==================== Timer 테스트 ====================
def test_timer_context_manager(result: TestResult) -> None:
    """Timer 컨텍스트 매니저"""
    try:
        timer = Timer("test_timer", "Test timer")

        with timer:
            time.sleep(0.01)  # 10ms

        stats = timer.get_stats()
        assert stats is not None
        assert stats.count == 1
        assert 8 <= stats.mean <= 20  # ~10ms (여유)

        result.ok("Timer 컨텍스트 매니저")
    except Exception as e:
        result.fail("Timer 컨텍스트 매니저", str(e))


def test_timer_decorator(result: TestResult) -> None:
    """Timer 데코레이터"""
    try:
        timer = Timer("test_timer", "Test timer")

        @timer.time()
        def test_func():
            time.sleep(0.005)  # 5ms
            return "done"

        # 3번 실행
        for _ in range(3):
            result_val = test_func()
            assert result_val == "done"

        stats = timer.get_stats()
        assert stats is not None
        assert stats.count == 3
        assert 3 <= stats.mean <= 10  # ~5ms (여유)

        result.ok("Timer 데코레이터")
    except Exception as e:
        result.fail("Timer 데코레이터", str(e))


def test_timer_manual_observe(result: TestResult) -> None:
    """Timer 수동 observe()"""
    try:
        timer = Timer("test", "Test")

        timer.observe(10.5)
        timer.observe(20.3)
        timer.observe(15.7)

        stats = timer.get_stats()
        assert stats is not None
        assert stats.count == 3
        assert 14 <= stats.mean <= 17  # (10.5+20.3+15.7)/3 = 15.5

        result.ok("Timer 수동 observe()")
    except Exception as e:
        result.fail("Timer 수동 observe()", str(e))


def test_timer_exception_handling(result: TestResult) -> None:
    """Timer 예외 발생 시에도 기록"""
    try:
        timer = Timer("test", "Test")

        try:
            with timer:
                time.sleep(0.005)
                raise ValueError("Test error")
        except ValueError:
            pass

        stats = timer.get_stats()
        assert stats is not None
        assert stats.count == 1  # 예외 발생해도 기록됨

        result.ok("Timer 예외 발생 시에도 기록")
    except Exception as e:
        result.fail("Timer 예외 발생 시에도 기록", str(e))


# ==================== RollingWindow 테스트 ====================
def test_rolling_window_basic(result: TestResult) -> None:
    """RollingWindow 기본 동작"""
    try:
        window = RollingWindow(max_size=100)

        for i in range(50):
            window.add(i)

        stats = window.get_stats()
        assert stats is not None
        assert stats.count == 50
        assert 24 <= stats.mean <= 26  # (0+49)/2 = 24.5

        result.ok("RollingWindow 기본 동작")
    except Exception as e:
        result.fail("RollingWindow 기본 동작", str(e))


def test_rolling_window_max_size(result: TestResult) -> None:
    """RollingWindow 최대 크기 제한"""
    try:
        window = RollingWindow(max_size=10)

        # 20개 추가
        for i in range(20):
            window.add(i)

        stats = window.get_stats()
        assert stats is not None
        assert stats.count == 10  # 최대 10개만 유지
        assert stats.min >= 10  # 최신 10개 (10-19)
        assert stats.max == 19

        result.ok("RollingWindow 최대 크기 제한")
    except Exception as e:
        result.fail("RollingWindow 최대 크기 제한", str(e))


def test_rolling_window_clear(result: TestResult) -> None:
    """RollingWindow clear()"""
    try:
        window = RollingWindow(max_size=100)

        for i in range(10):
            window.add(i)

        assert window.get_stats() is not None

        window.clear()
        assert window.get_stats() is None  # 샘플 없음

        result.ok("RollingWindow clear()")
    except Exception as e:
        result.fail("RollingWindow clear()", str(e))


def test_rolling_window_empty(result: TestResult) -> None:
    """RollingWindow 빈 윈도우"""
    try:
        window = RollingWindow(max_size=100)
        assert window.get_stats() is None

        result.ok("RollingWindow 빈 윈도우")
    except Exception as e:
        result.fail("RollingWindow 빈 윈도우", str(e))


# ==================== TimeWindow 테스트 ====================
def test_time_window_basic(result: TestResult) -> None:
    """TimeWindow 기본 동작"""
    try:
        window = TimeWindow(duration_seconds=1.0)
        current_time = time.time()

        for i in range(10):
            window.add(i, timestamp=current_time + i * 0.01)

        stats = window.get_stats()
        assert stats is not None
        assert stats.count == 10

        result.ok("TimeWindow 기본 동작")
    except Exception as e:
        result.fail("TimeWindow 기본 동작", str(e))


def test_time_window_cleanup(result: TestResult) -> None:
    """TimeWindow 오래된 데이터 제거"""
    try:
        window = TimeWindow(duration_seconds=0.5)
        current_time = time.time()

        # 오래된 데이터
        window.add(1.0, timestamp=current_time - 1.0)
        window.add(2.0, timestamp=current_time - 0.8)

        # 최근 데이터
        window.add(10.0, timestamp=current_time - 0.1)
        window.add(20.0, timestamp=current_time)

        stats = window.get_stats()
        assert stats is not None
        assert stats.count == 2  # 최근 2개만
        assert 14 <= stats.mean <= 16  # (10+20)/2 = 15

        result.ok("TimeWindow 오래된 데이터 제거")
    except Exception as e:
        result.fail("TimeWindow 오래된 데이터 제거", str(e))


def test_time_window_rate(result: TestResult) -> None:
    """TimeWindow get_rate()"""
    try:
        window = TimeWindow(duration_seconds=1.0)
        current_time = time.time()

        # 1초 동안 10개 추가
        for i in range(10):
            window.add(i, timestamp=current_time + i * 0.1)

        rate = window.get_rate()
        assert 8 <= rate <= 12  # ~10 samples/sec

        result.ok("TimeWindow get_rate()")
    except Exception as e:
        result.fail("TimeWindow get_rate()", str(e))


def test_time_window_empty(result: TestResult) -> None:
    """TimeWindow 빈 윈도우"""
    try:
        window = TimeWindow(duration_seconds=1.0)
        assert window.get_stats() is None
        assert window.get_rate() == 0.0

        result.ok("TimeWindow 빈 윈도우")
    except Exception as e:
        result.fail("TimeWindow 빈 윈도우", str(e))


# ==================== MetricsRegistry 테스트 ====================
def test_registry_singleton(result: TestResult) -> None:
    """MetricsRegistry 싱글톤"""
    try:
        registry1 = get_metrics_registry()
        registry2 = get_metrics_registry()

        assert registry1 is registry2  # 동일한 인스턴스

        result.ok("MetricsRegistry 싱글톤")
    except Exception as e:
        result.fail("MetricsRegistry 싱글톤", str(e))


def test_registry_counter(result: TestResult) -> None:
    """MetricsRegistry counter 등록"""
    try:
        registry = MetricsRegistry()

        counter1 = registry.counter("test_counter", "Test counter")
        assert isinstance(counter1, Counter)

        # 같은 이름으로 다시 조회
        counter2 = registry.counter("test_counter", "Test counter")
        assert counter1 is counter2  # 동일한 인스턴스

        result.ok("MetricsRegistry counter 등록")
    except Exception as e:
        result.fail("MetricsRegistry counter 등록", str(e))


def test_registry_gauge(result: TestResult) -> None:
    """MetricsRegistry gauge 등록"""
    try:
        registry = MetricsRegistry()

        gauge = registry.gauge("test_gauge", "Test gauge")
        assert isinstance(gauge, Gauge)

        result.ok("MetricsRegistry gauge 등록")
    except Exception as e:
        result.fail("MetricsRegistry gauge 등록", str(e))


def test_registry_histogram(result: TestResult) -> None:
    """MetricsRegistry histogram 등록"""
    try:
        registry = MetricsRegistry()

        histogram = registry.histogram("test_histogram", "Test histogram")
        assert isinstance(histogram, Histogram)

        result.ok("MetricsRegistry histogram 등록")
    except Exception as e:
        result.fail("MetricsRegistry histogram 등록", str(e))


def test_registry_timer(result: TestResult) -> None:
    """MetricsRegistry timer 등록"""
    try:
        registry = MetricsRegistry()

        timer = registry.timer("test_timer", "Test timer")
        assert isinstance(timer, Timer)

        result.ok("MetricsRegistry timer 등록")
    except Exception as e:
        result.fail("MetricsRegistry timer 등록", str(e))


def test_registry_get_metric(result: TestResult) -> None:
    """MetricsRegistry get_metric()"""
    try:
        registry = MetricsRegistry()

        counter = registry.counter("test_counter", "Test")
        counter.inc(5)

        retrieved = registry.get_metric("test_counter")
        assert retrieved is counter
        assert retrieved.value == 5.0

        # 존재하지 않는 메트릭
        assert registry.get_metric("nonexistent") is None

        result.ok("MetricsRegistry get_metric()")
    except Exception as e:
        result.fail("MetricsRegistry get_metric()", str(e))


def test_registry_get_all_metrics(result: TestResult) -> None:
    """MetricsRegistry get_all_metrics()"""
    try:
        registry = MetricsRegistry()

        registry.counter("counter1", "Test")
        registry.gauge("gauge1", "Test")
        registry.histogram("hist1", "Test")

        all_metrics = registry.get_all_metrics()
        assert len(all_metrics) == 3
        assert "counter1" in all_metrics
        assert "gauge1" in all_metrics
        assert "hist1" in all_metrics

        result.ok("MetricsRegistry get_all_metrics()")
    except Exception as e:
        result.fail("MetricsRegistry get_all_metrics()", str(e))


def test_registry_get_metrics_prefix(result: TestResult) -> None:
    """MetricsRegistry get_metrics() prefix 필터"""
    try:
        registry = MetricsRegistry()

        registry.counter("http_requests_total", "Test")
        registry.counter("http_errors_total", "Test")
        registry.gauge("cpu_usage", "Test")

        http_metrics = registry.get_metrics(prefix="http_")
        assert len(http_metrics) == 2
        assert "http_requests_total" in http_metrics
        assert "http_errors_total" in http_metrics
        assert "cpu_usage" not in http_metrics

        result.ok("MetricsRegistry get_metrics() prefix 필터")
    except Exception as e:
        result.fail("MetricsRegistry get_metrics() prefix 필터", str(e))


def test_registry_labels(result: TestResult) -> None:
    """MetricsRegistry 라벨"""
    try:
        registry = MetricsRegistry()

        counter1 = registry.counter("requests", "Requests", labels={"method": "GET"})
        counter2 = registry.counter("requests", "Requests", labels={"method": "POST"})

        counter1.inc(5)
        counter2.inc(3)

        assert counter1.value == 5.0
        assert counter2.value == 3.0
        assert counter1 is not counter2  # 다른 인스턴스

        result.ok("MetricsRegistry 라벨")
    except Exception as e:
        result.fail("MetricsRegistry 라벨", str(e))


def test_registry_remove_metric(result: TestResult) -> None:
    """MetricsRegistry remove_metric()"""
    try:
        registry = MetricsRegistry()

        registry.counter("test_counter", "Test")
        assert registry.get_metric("test_counter") is not None

        registry.remove_metric("test_counter")
        assert registry.get_metric("test_counter") is None

        result.ok("MetricsRegistry remove_metric()")
    except Exception as e:
        result.fail("MetricsRegistry remove_metric()", str(e))


def test_registry_clear(result: TestResult) -> None:
    """MetricsRegistry clear()"""
    try:
        registry = MetricsRegistry()

        registry.counter("counter1", "Test")
        registry.gauge("gauge1", "Test")

        assert len(registry.get_all_metrics()) == 2

        registry.clear()
        assert len(registry.get_all_metrics()) == 0

        result.ok("MetricsRegistry clear()")
    except Exception as e:
        result.fail("MetricsRegistry clear()", str(e))


# ==================== Exporter 테스트 ====================
def test_json_exporter(result: TestResult) -> None:
    """JSONExporter export()"""
    try:
        registry = MetricsRegistry()

        counter = registry.counter("test_counter", "Test counter")
        counter.inc(10)

        gauge = registry.gauge("test_gauge", "Test gauge")
        gauge.set(42.5)

        exporter = JSONExporter()
        json_str = exporter.export(registry)

        data = json.loads(json_str)
        assert "timestamp" in data
        assert "metrics" in data
        assert "test_counter" in data["metrics"]
        assert data["metrics"]["test_counter"]["value"] == 10.0
        assert data["metrics"]["test_gauge"]["value"] == 42.5

        result.ok("JSONExporter export()")
    except Exception as e:
        result.fail("JSONExporter export()", str(e))


def test_json_exporter_file(result: TestResult) -> None:
    """JSONExporter export_to_file()"""
    try:
        registry = MetricsRegistry()
        registry.counter("test", "Test").inc(5)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_file = f.name

        exporter = JSONExporter()
        exporter.export_to_file(registry, temp_file)

        # 파일 읽기
        with open(temp_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metrics" in data
        assert "test" in data["metrics"]

        Path(temp_file).unlink()

        result.ok("JSONExporter export_to_file()")
    except Exception as e:
        result.fail("JSONExporter export_to_file()", str(e))


def test_csv_exporter(result: TestResult) -> None:
    """CSVExporter export()"""
    try:
        registry = MetricsRegistry()

        counter = registry.counter("test_counter", "Test")
        counter.inc(10)

        exporter = CSVExporter()
        csv_str = exporter.export(registry)

        lines = csv_str.strip().split("\n")
        assert len(lines) >= 2  # 헤더 + 데이터

        # 헤더 확인
        header = lines[0]
        assert "metric_name" in header
        assert "metric_type" in header
        assert "value" in header

        result.ok("CSVExporter export()")
    except Exception as e:
        result.fail("CSVExporter export()", str(e))


def test_prometheus_exporter(result: TestResult) -> None:
    """PrometheusExporter export()"""
    try:
        registry = MetricsRegistry()

        counter = registry.counter("test_counter", "Test counter")
        counter.inc(10)

        gauge = registry.gauge("test_gauge", "Test gauge")
        gauge.set(42.5)

        exporter = PrometheusExporter()
        prom_str = exporter.export(registry)

        # Prometheus 포맷 확인
        assert "# HELP test_counter Test counter" in prom_str
        assert "# TYPE test_counter counter" in prom_str
        assert "test_counter 10" in prom_str
        assert "# HELP test_gauge Test gauge" in prom_str
        assert "# TYPE test_gauge gauge" in prom_str
        assert "test_gauge 42.5" in prom_str

        result.ok("PrometheusExporter export()")
    except Exception as e:
        result.fail("PrometheusExporter export()", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 단위 테스트 실행"""
    print("="*60)
    print("Metrics 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[Counter 테스트]")
    test_counter_creation(result)
    test_counter_inc(result)
    test_counter_negative(result)
    test_counter_reset(result)

    print("\n[Gauge 테스트]")
    test_gauge_creation(result)
    test_gauge_set(result)
    test_gauge_inc_dec(result)

    print("\n[Histogram 테스트]")
    test_histogram_creation(result)
    test_histogram_observe(result)
    test_histogram_stats(result)
    test_histogram_percentiles(result)
    test_histogram_buckets(result)
    test_histogram_max_samples(result)
    test_histogram_single_sample(result)

    print("\n[Timer 테스트]")
    test_timer_context_manager(result)
    test_timer_decorator(result)
    test_timer_manual_observe(result)
    test_timer_exception_handling(result)

    print("\n[RollingWindow 테스트]")
    test_rolling_window_basic(result)
    test_rolling_window_max_size(result)
    test_rolling_window_clear(result)
    test_rolling_window_empty(result)

    print("\n[TimeWindow 테스트]")
    test_time_window_basic(result)
    test_time_window_cleanup(result)
    test_time_window_rate(result)
    test_time_window_empty(result)

    print("\n[MetricsRegistry 테스트]")
    test_registry_singleton(result)
    test_registry_counter(result)
    test_registry_gauge(result)
    test_registry_histogram(result)
    test_registry_timer(result)
    test_registry_get_metric(result)
    test_registry_get_all_metrics(result)
    test_registry_get_metrics_prefix(result)
    test_registry_labels(result)
    test_registry_remove_metric(result)
    test_registry_clear(result)

    print("\n[Exporter 테스트]")
    test_json_exporter(result)
    test_json_exporter_file(result)
    test_csv_exporter(result)
    test_prometheus_exporter(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
