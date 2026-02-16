# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/performance
파일: test_metrics_perf.py
설명: Prometheus 스타일 메트릭 수집 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [P1] MetricLabels 생성/해싱/직렬화 성능 (3개)
    [P2] Counter inc/get 처리량 (3개)
    [P3] Gauge set/inc/dec 처리량 (3개)
    [P4] Histogram observe 처리량 (3개)
    [P5] Summary observe 처리량 (3개)
    [P6] MetricsCollector 팩토리 메서드 처리량 (3개)
    [P7] 내보내기 성능 (export_prometheus, export_json) (3개)
    [P8] 멀티스레드 동시 연산 성능 (3개)
    [P9] 메모리 사용량 (3개)

    총 27개 테스트
"""

import gc
import sys
import threading
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.metrics import (
    # 상수
    DEFAULT_HISTOGRAM_BUCKETS,
    FPS_HISTOGRAM_BUCKETS,
    DEFAULT_QUANTILES,
    # Enum
    MetricType,
    MetricUnit,
    # 데이터 클래스
    MetricLabels,
    MetricValue,
    MetricSnapshot,
    # 메트릭 클래스
    Counter,
    Gauge,
    Histogram,
    Summary,
    # 메인 클래스
    MetricsCollector,
    # 싱글톤
    _reset_collector,
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


def _make_collector(**kwargs) -> MetricsCollector:
    """테스트용 MetricsCollector 생성."""
    defaults = {
        "prefix": "perf",
        "enabled": True,
        "max_metrics": 10000,
    }
    defaults.update(kwargs)
    return MetricsCollector(**defaults)


# =============================================================================
# [P1] MetricLabels 생성/해싱/직렬화 성능 (3개)
# =============================================================================
def test_p1_metric_labels_perf(result: PerformanceTestResult) -> None:
    """MetricLabels 성능 테스트."""
    print("\n[P1] MetricLabels 생성/해싱/직렬화 성능")

    # P1-1. from_dict 생성 처리량
    try:
        ops = measure_ops(
            lambda: MetricLabels.from_dict({"method": "GET", "status": "200", "path": "/api"}),
            iterations=50000,
        )
        assert ops > 50000, f"from_dict: {ops:.0f} ops/sec < 50000"
        result.ok("P1-1 from_dict 생성", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-1 from_dict 생성", str(e))

    # P1-2. __hash__ 처리량
    try:
        ml = MetricLabels.from_dict({"method": "GET", "status": "200"})
        ops = measure_ops(lambda: hash(ml), iterations=100000)
        assert ops > 500000, f"hash: {ops:.0f} ops/sec < 500000"
        result.ok("P1-2 __hash__", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-2 __hash__", str(e))

    # P1-3. to_prometheus_string 처리량
    try:
        ml = MetricLabels.from_dict({"method": "GET", "status": "200", "endpoint": "/api"})
        ops = measure_ops(lambda: ml.to_prometheus_string(), iterations=50000)
        assert ops > 50000, f"to_prometheus_string: {ops:.0f} ops/sec < 50000"
        result.ok("P1-3 to_prometheus_string", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P1-3 to_prometheus_string", str(e))


# =============================================================================
# [P2] Counter inc/get 처리량 (3개)
# =============================================================================
def test_p2_counter_perf(result: PerformanceTestResult) -> None:
    """Counter 성능 테스트."""
    print("\n[P2] Counter inc/get 처리량")

    # P2-1. inc (레이블 없음) 처리량
    try:
        c = Counter("perf_test")
        ops = measure_ops(lambda: c.inc(), iterations=100000)
        assert ops > 100000, f"inc: {ops:.0f} ops/sec < 100000"
        result.ok("P2-1 Counter.inc (레이블 없음)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-1 Counter.inc", str(e))

    # P2-2. inc (레이블 포함) 처리량
    try:
        c = Counter("perf_test_labels")
        ops = measure_ops(
            lambda: c.inc(1.0, {"method": "GET"}),
            iterations=50000,
        )
        assert ops > 30000, f"inc+labels: {ops:.0f} ops/sec < 30000"
        result.ok("P2-2 Counter.inc (레이블 포함)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-2 Counter.inc 레이블", str(e))

    # P2-3. get 처리량
    try:
        c = Counter("perf_test_get")
        c.inc(100.0)
        ops = measure_ops(lambda: c.get(), iterations=100000)
        assert ops > 100000, f"get: {ops:.0f} ops/sec < 100000"
        result.ok("P2-3 Counter.get", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P2-3 Counter.get", str(e))


# =============================================================================
# [P3] Gauge set/inc/dec 처리량 (3개)
# =============================================================================
def test_p3_gauge_perf(result: PerformanceTestResult) -> None:
    """Gauge 성능 테스트."""
    print("\n[P3] Gauge set/inc/dec 처리량")

    # P3-1. set 처리량
    try:
        g = Gauge("perf_gauge")
        ops = measure_ops(lambda: g.set(42.0), iterations=100000)
        assert ops > 100000, f"set: {ops:.0f} ops/sec < 100000"
        result.ok("P3-1 Gauge.set", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-1 Gauge.set", str(e))

    # P3-2. inc/dec 교대 처리량
    try:
        g = Gauge("perf_gauge_incdec")
        toggle = [True]

        def inc_dec():
            if toggle[0]:
                g.inc()
            else:
                g.dec()
            toggle[0] = not toggle[0]

        ops = measure_ops(inc_dec, iterations=100000)
        assert ops > 80000, f"inc/dec: {ops:.0f} ops/sec < 80000"
        result.ok("P3-2 Gauge.inc/dec 교대", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-2 Gauge.inc/dec", str(e))

    # P3-3. track_inprogress 처리량
    try:
        g = Gauge("perf_inprogress")
        count = [0]

        def track_op():
            with g.track_inprogress():
                count[0] += 1

        ops = measure_ops(track_op, iterations=50000)
        assert ops > 30000, f"track_inprogress: {ops:.0f} ops/sec < 30000"
        result.ok("P3-3 Gauge.track_inprogress", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P3-3 track_inprogress", str(e))


# =============================================================================
# [P4] Histogram observe 처리량 (3개)
# =============================================================================
def test_p4_histogram_perf(result: PerformanceTestResult) -> None:
    """Histogram 성능 테스트."""
    print("\n[P4] Histogram observe 처리량")

    # P4-1. observe (기본 15 버킷) 처리량
    try:
        h = Histogram("perf_hist")
        idx = [0]
        values = [0.001 * i for i in range(1, 101)]

        def observe_op():
            h.observe(values[idx[0] % 100])
            idx[0] += 1

        ops = measure_ops(observe_op, iterations=50000)
        assert ops > 30000, f"observe 15 buckets: {ops:.0f} ops/sec < 30000"
        result.ok("P4-1 Histogram.observe (15 버킷)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P4-1 observe 15 버킷", str(e))

    # P4-2. observe (커스텀 3 버킷) 처리량 - 더 빠를 것
    try:
        h = Histogram("perf_hist_small", buckets=(0.1, 0.5, 1.0))
        ops = measure_ops(lambda: h.observe(0.3), iterations=50000)
        assert ops > 50000, f"observe 3 buckets: {ops:.0f} ops/sec < 50000"
        result.ok("P4-2 Histogram.observe (3 버킷)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P4-2 observe 3 버킷", str(e))

    # P4-3. get_bucket_counts 처리량
    try:
        h = Histogram("perf_hist_bc")
        for i in range(1000):
            h.observe(float(i) * 0.01)
        ops = measure_ops(lambda: h.get_bucket_counts(), iterations=50000)
        assert ops > 50000, f"get_bucket_counts: {ops:.0f} ops/sec < 50000"
        result.ok("P4-3 get_bucket_counts (1000 관측 후)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P4-3 get_bucket_counts", str(e))


# =============================================================================
# [P5] Summary observe 처리량 (3개)
# =============================================================================
def test_p5_summary_perf(result: PerformanceTestResult) -> None:
    """Summary 성능 테스트."""
    print("\n[P5] Summary observe 처리량")

    # P5-1. observe 처리량
    try:
        s = Summary("perf_summary", max_age_seconds=600.0, max_observations=100000)
        idx = [0]
        values = [float(i) * 0.01 for i in range(100)]

        def observe_op():
            s.observe(values[idx[0] % 100])
            idx[0] += 1

        ops = measure_ops(observe_op, iterations=30000)
        assert ops > 10000, f"observe: {ops:.0f} ops/sec < 10000"
        result.ok("P5-1 Summary.observe", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P5-1 observe", str(e))

    # P5-2. get_quantile 처리량 (1000 관측 후)
    try:
        s = Summary("perf_summary_q", max_observations=10000)
        for i in range(1000):
            s.observe(float(i) * 0.01)
        ops = measure_ops(lambda: s.get_quantile(0.5), iterations=5000)
        # get_quantile은 정렬 필요하므로 상대적으로 느림
        assert ops > 500, f"get_quantile: {ops:.0f} ops/sec < 500"
        result.ok("P5-2 get_quantile (1000 관측)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P5-2 get_quantile", str(e))

    # P5-3. get_quantiles (전체 분위수) 처리량
    try:
        s = Summary("perf_summary_qs", max_observations=10000)
        for i in range(1000):
            s.observe(float(i) * 0.01)
        ops = measure_ops(lambda: s.get_quantiles(), iterations=2000)
        assert ops > 200, f"get_quantiles: {ops:.0f} ops/sec < 200"
        result.ok("P5-3 get_quantiles (1000 관측, 4 분위수)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P5-3 get_quantiles", str(e))


# =============================================================================
# [P6] MetricsCollector 팩토리 메서드 처리량 (3개)
# =============================================================================
def test_p6_collector_factory_perf(result: PerformanceTestResult) -> None:
    """MetricsCollector 팩토리 메서드 성능 테스트."""
    print("\n[P6] MetricsCollector 팩토리 메서드 처리량")

    # P6-1. counter() 재사용 (기존 메트릭 반환) 처리량
    try:
        mc = _make_collector()
        mc.counter("existing_counter")
        ops = measure_ops(lambda: mc.counter("existing_counter"), iterations=50000)
        assert ops > 50000, f"counter 재사용: {ops:.0f} ops/sec < 50000"
        result.ok("P6-1 counter() 재사용", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-1 counter 재사용", str(e))

    # P6-2. gauge() 재사용 처리량
    try:
        mc = _make_collector()
        mc.gauge("existing_gauge")
        ops = measure_ops(lambda: mc.gauge("existing_gauge"), iterations=50000)
        assert ops > 50000, f"gauge 재사용: {ops:.0f} ops/sec < 50000"
        result.ok("P6-2 gauge() 재사용", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-2 gauge 재사용", str(e))

    # P6-3. 새 메트릭 생성 처리량
    try:
        mc = _make_collector()
        idx = [0]

        def create_new():
            mc.counter(f"new_counter_{idx[0]}")
            idx[0] += 1

        ops = measure_ops(create_new, iterations=5000)
        assert ops > 3000, f"새 메트릭 생성: {ops:.0f} ops/sec < 3000"
        result.ok("P6-3 새 메트릭 생성", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P6-3 새 메트릭 생성", str(e))


# =============================================================================
# [P7] 내보내기 성능 (3개)
# =============================================================================
def test_p7_export_perf(result: PerformanceTestResult) -> None:
    """내보내기 성능 테스트."""
    print("\n[P7] 내보내기 성능")

    # 기본 메트릭 + 추가 메트릭으로 테스트
    mc = _make_collector()
    for i in range(10):
        c = mc.counter(f"export_counter_{i}")
        c.inc(float(i))
    for i in range(10):
        g = mc.gauge(f"export_gauge_{i}")
        g.set(float(i) * 10)

    # P7-1. export_prometheus 처리량
    try:
        ops = measure_ops(lambda: mc.export_prometheus(), iterations=1000)
        assert ops > 100, f"export_prometheus: {ops:.0f} ops/sec < 100"
        result.ok("P7-1 export_prometheus", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P7-1 export_prometheus", str(e))

    # P7-2. export_json 처리량
    try:
        ops = measure_ops(lambda: mc.export_json(), iterations=1000)
        assert ops > 100, f"export_json: {ops:.0f} ops/sec < 100"
        result.ok("P7-2 export_json", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P7-2 export_json", str(e))

    # P7-3. get_all_snapshots 처리량
    try:
        ops = measure_ops(lambda: mc.get_all_snapshots(), iterations=2000)
        assert ops > 200, f"get_all_snapshots: {ops:.0f} ops/sec < 200"
        result.ok("P7-3 get_all_snapshots", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P7-3 get_all_snapshots", str(e))


# =============================================================================
# [P8] 멀티스레드 동시 연산 성능 (3개)
# =============================================================================
def test_p8_multithread_perf(result: PerformanceTestResult) -> None:
    """멀티스레드 성능 테스트."""
    print("\n[P8] 멀티스레드 동시 연산 성능")

    # P8-1. Counter 동시 inc (4스레드 x 10000)
    try:
        c = Counter("mt_counter")
        errors = []
        n_threads = 4
        n_ops = 10000

        def inc_worker():
            try:
                for _ in range(n_ops):
                    c.inc()
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=inc_worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        expected = float(n_threads * n_ops)
        assert c.get() == expected, f"값: {c.get()} != {expected}"
        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok("P8-1 Counter 멀티스레드 inc (4x10000)", f"{ops:,.0f} ops/sec, 정확도: 100%")
    except AssertionError as e:
        result.fail("P8-1 Counter 멀티스레드", str(e))

    # P8-2. Gauge 동시 set/get (4스레드)
    try:
        g = Gauge("mt_gauge")
        errors = []
        n_threads = 4
        n_ops = 10000

        def gauge_worker(tid):
            try:
                for i in range(n_ops):
                    g.set(float(tid * 1000 + i), {"thread": str(tid)})
                    g.get({"thread": str(tid)})
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=gauge_worker, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        total_ops = n_threads * n_ops * 2  # set + get
        ops = total_ops / elapsed
        result.ok("P8-2 Gauge 멀티스레드 set/get (4x10000)", f"{ops:,.0f} ops/sec")
    except AssertionError as e:
        result.fail("P8-2 Gauge 멀티스레드", str(e))

    # P8-3. Histogram 동시 observe (4스레드)
    try:
        h = Histogram("mt_hist", buckets=(0.1, 0.5, 1.0, 5.0))
        errors = []
        n_threads = 4
        n_ops = 5000

        def hist_worker(tid):
            try:
                for i in range(n_ops):
                    h.observe(float(i % 100) * 0.05, {"thread": str(tid)})
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=hist_worker, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        # 각 스레드별 카운트 확인
        for tid in range(n_threads):
            cnt = h.get_count({"thread": str(tid)})
            assert cnt == n_ops, f"thread {tid}: {cnt} != {n_ops}"
        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok("P8-3 Histogram 멀티스레드 observe (4x5000)", f"{ops:,.0f} ops/sec, 정확도: 100%")
    except AssertionError as e:
        result.fail("P8-3 Histogram 멀티스레드", str(e))


# =============================================================================
# [P9] 메모리 사용량 (3개)
# =============================================================================
def test_p9_memory_perf(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P9] 메모리 사용량")

    # P9-1. MetricLabels 메모리 효율
    try:
        gc.collect()
        labels_list = []
        for i in range(10000):
            ml = MetricLabels.from_dict({"key": f"value_{i}"})
            labels_list.append(ml)

        # 평균 크기 추정 (객체 자체 + 튜플)
        sample_size = get_object_size(labels_list[0])
        total_estimated = sample_size * 10000
        # 10000개 MetricLabels < 5MB
        assert total_estimated < 5 * 1024 * 1024, f"{total_estimated / 1024:.1f}KB > 5MB"
        result.ok("P9-1 MetricLabels 메모리 (10000개)", f"개당 ~{sample_size}B, 추정 {total_estimated / 1024:.1f}KB")
    except AssertionError as e:
        result.fail("P9-1 MetricLabels 메모리", str(e))

    # P9-2. Counter 대량 레이블 메모리
    try:
        gc.collect()
        c = Counter("mem_counter")
        for i in range(5000):
            c.inc(1.0, {"key": f"val_{i}"})

        snap = c.snapshot()
        assert len(snap.values) == 5000
        # snapshot 크기 제한
        snap_size = get_object_size(snap)
        result.ok("P9-2 Counter 5000 레이블 snapshot", f"values={len(snap.values)}, snap_size~{snap_size}B")
    except (AssertionError, Exception) as e:
        result.fail("P9-2 Counter 대량 레이블", str(e))

    # P9-3. MetricsCollector 기본 메트릭 메모리
    try:
        gc.collect()
        mc = _make_collector()
        status = mc.get_status()
        total_metrics = status["total_metrics"]

        # 기본 메트릭 포함한 collector 크기
        collector_size = get_object_size(mc)
        result.ok(
            "P9-3 MetricsCollector 기본 메모리",
            f"총 {total_metrics}개 메트릭, collector~{collector_size}B"
        )
    except (AssertionError, Exception) as e:
        result.fail("P9-3 Collector 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - metrics.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [P1] MetricLabels 성능
    test_p1_metric_labels_perf(result)

    # [P2] Counter 성능
    test_p2_counter_perf(result)

    # [P3] Gauge 성능
    test_p3_gauge_perf(result)

    # [P4] Histogram 성능
    test_p4_histogram_perf(result)

    # [P5] Summary 성능
    test_p5_summary_perf(result)

    # [P6] MetricsCollector 팩토리 성능
    test_p6_collector_factory_perf(result)

    # [P7] 내보내기 성능
    test_p7_export_perf(result)

    # [P8] 멀티스레드 성능
    test_p8_multithread_perf(result)

    # [P9] 메모리 사용량
    test_p9_memory_perf(result)

    # 요약 출력
    result.summary()

    # 종료 코드
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
