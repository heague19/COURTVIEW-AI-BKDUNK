# -*- coding: utf-8 -*-
"""monitoring/metrics.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from core_foundation.monitoring.metrics import (
    DEFAULT_HISTOGRAM_BUCKETS,
    DEFAULT_HISTORY_SIZE,
    MAX_METRIC_COUNT,
    Metric,
    MetricPoint,
    MetricSnapshot,
    MetricType,
    MetricsCollector,
)


@pytest.fixture(autouse=True)
def reset_collector():
    MetricsCollector.reset()
    yield
    MetricsCollector.reset()


# =============================================================================
# MetricType 검증
# =============================================================================

class TestMetricType:
    def test_member_count(self):
        assert len(MetricType) == 3

    def test_values(self):
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"

    def test_to_korean(self):
        assert MetricType.COUNTER.to_korean() == "카운터"
        assert MetricType.GAUGE.to_korean() == "게이지"
        assert MetricType.HISTOGRAM.to_korean() == "히스토그램"


# =============================================================================
# MetricPoint 검증
# =============================================================================

class TestMetricPoint:
    def test_slots(self):
        assert hasattr(MetricPoint, "__slots__")

    def test_creation(self):
        p = MetricPoint(value=3.14, timestamp=0.0)
        assert p.value == pytest.approx(3.14)

    def test_repr(self):
        p = MetricPoint(value=1.5, timestamp=0.0)
        assert "1.5" in repr(p)


# =============================================================================
# MetricSnapshot 검증
# =============================================================================

class TestMetricSnapshot:
    def test_slots(self):
        assert hasattr(MetricSnapshot, "__slots__")

    def test_repr(self):
        snap = MetricSnapshot(
            name="test", metric_type=MetricType.GAUGE,
            current=60.0, count=10, mean=55.0,
            min_value=30.0, max_value=60.0,
            p50=55.0, p95=59.0, p99=60.0,
        )
        assert "test" in repr(snap)
        assert "60.00" in repr(snap)


# =============================================================================
# Metric — Counter 검증
# =============================================================================

class TestMetricCounter:
    def test_increment(self):
        m = Metric("req_count", MetricType.COUNTER)
        m.increment()
        assert m.current == 1.0
        m.increment(5.0)
        assert m.current == 6.0

    def test_increment_negative_ignored(self):
        m = Metric("counter", MetricType.COUNTER)
        m.increment(10.0)
        m.increment(-5.0)  # 음수는 0으로 처리
        assert m.current == 10.0

    def test_count(self):
        m = Metric("c", MetricType.COUNTER)
        m.increment()
        m.increment()
        assert m.count == 2


# =============================================================================
# Metric — Gauge 검증
# =============================================================================

class TestMetricGauge:
    def test_set(self):
        m = Metric("temp", MetricType.GAUGE)
        m.set(72.5)
        assert m.current == pytest.approx(72.5)

    def test_set_overwrite(self):
        m = Metric("fps", MetricType.GAUGE)
        m.set(30.0)
        m.set(60.0)
        assert m.current == pytest.approx(60.0)

    def test_negative_gauge(self):
        m = Metric("delta", MetricType.GAUGE)
        m.set(-10.0)
        assert m.current == pytest.approx(-10.0)


# =============================================================================
# Metric — Histogram 검증
# =============================================================================

class TestMetricHistogram:
    def test_observe(self):
        m = Metric("latency", MetricType.HISTOGRAM)
        m.observe(0.033)
        m.observe(0.050)
        assert m.count == 2

    def test_snapshot_percentiles(self):
        m = Metric("latency", MetricType.HISTOGRAM)
        for i in range(100):
            m.observe(float(i))

        snap = m.snapshot()
        assert snap.p50 == pytest.approx(49.5, abs=1.0)
        assert snap.p95 == pytest.approx(94.05, abs=1.0)
        assert snap.min_value == 0.0
        assert snap.max_value == 99.0


# =============================================================================
# Metric — 범용 record 검증
# =============================================================================

class TestMetricRecord:
    def test_record_counter(self):
        m = Metric("c", MetricType.COUNTER)
        m.record(5.0)
        assert m.current == 5.0

    def test_record_gauge(self):
        m = Metric("g", MetricType.GAUGE)
        m.record(42.0)
        assert m.current == 42.0

    def test_record_histogram(self):
        m = Metric("h", MetricType.HISTOGRAM)
        m.record(0.1)
        assert m.current == pytest.approx(0.1)


# =============================================================================
# Metric — Snapshot 검증
# =============================================================================

class TestMetricSnapshotCalc:
    def test_empty_snapshot(self):
        m = Metric("empty", MetricType.GAUGE)
        snap = m.snapshot()
        assert snap.count == 0
        assert snap.mean == 0.0

    def test_single_value(self):
        m = Metric("single", MetricType.GAUGE)
        m.set(42.0)
        snap = m.snapshot()
        assert snap.count == 1
        assert snap.mean == 42.0
        assert snap.p50 == 42.0

    def test_reset(self):
        m = Metric("reset", MetricType.COUNTER)
        m.increment(10)
        m.reset()
        assert m.current == 0.0
        assert m.count == 0

    def test_repr(self):
        m = Metric("test", MetricType.GAUGE)
        m.set(5.0)
        assert "test" in repr(m)
        assert "gauge" in repr(m)


# =============================================================================
# MetricsCollector 검증
# =============================================================================

class TestMetricsCollector:
    def test_singleton(self):
        c1 = MetricsCollector.get_instance()
        c2 = MetricsCollector.get_instance()
        assert c1 is c2

    def test_register(self):
        c = MetricsCollector.get_instance()
        m = c.register("fps", MetricType.GAUGE, "카메라 FPS")
        assert isinstance(m, Metric)
        assert m.name == "fps"

    def test_register_cached(self):
        c = MetricsCollector.get_instance()
        m1 = c.register("fps", MetricType.GAUGE)
        m2 = c.register("fps", MetricType.GAUGE)
        assert m1 is m2

    def test_get(self):
        c = MetricsCollector.get_instance()
        c.register("test", MetricType.COUNTER)
        assert c.get("test") is not None
        assert c.get("nonexistent") is None

    def test_unregister(self):
        c = MetricsCollector.get_instance()
        c.register("temp", MetricType.GAUGE)
        assert c.unregister("temp") is True
        assert c.unregister("temp") is False

    def test_snapshot_all(self):
        c = MetricsCollector.get_instance()
        c.register("a", MetricType.GAUGE).set(1.0)
        c.register("b", MetricType.COUNTER).increment(2.0)
        snaps = c.snapshot_all()
        assert len(snaps) == 2
        assert snaps["a"].current == 1.0

    def test_snapshot_single(self):
        c = MetricsCollector.get_instance()
        c.register("x", MetricType.GAUGE).set(99.0)
        snap = c.snapshot("x")
        assert snap is not None
        assert snap.current == 99.0
        assert c.snapshot("missing") is None

    def test_clear(self):
        c = MetricsCollector.get_instance()
        c.register("a", MetricType.GAUGE)
        c.register("b", MetricType.GAUGE)
        assert c.clear() == 2
        assert c.metric_count == 0

    def test_metric_names(self):
        c = MetricsCollector.get_instance()
        c.register("x", MetricType.GAUGE)
        c.register("y", MetricType.COUNTER)
        names = c.metric_names
        assert "x" in names and "y" in names

    def test_repr(self):
        c = MetricsCollector.get_instance()
        assert "metrics=0" in repr(c)


# =============================================================================
# 스레드 안전 검증
# =============================================================================

class TestThreadSafety:
    def test_concurrent_record(self):
        m = Metric("concurrent", MetricType.COUNTER)
        errors: list[Exception] = []

        def inc():
            try:
                for _ in range(100):
                    m.increment(1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inc) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert m.current == pytest.approx(1000.0)


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_history(self):
        assert DEFAULT_HISTORY_SIZE == 300

    def test_max_metric_count(self):
        assert MAX_METRIC_COUNT == 500

    def test_histogram_buckets(self):
        assert len(DEFAULT_HISTOGRAM_BUCKETS) == 11


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.monitoring.metrics as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.monitoring.metrics as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.monitoring.metrics as mod
        assert mod.__version__ == "1.0.0"
