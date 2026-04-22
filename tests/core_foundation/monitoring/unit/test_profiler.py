# -*- coding: utf-8 -*-
"""monitoring/profiler.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from core_foundation.monitoring.profiler import (
    BYTES_TO_MB,
    DEFAULT_PROFILE_HISTORY,
    MAX_PROFILE_COUNT,
    ProfileEntry,
    ProfileSummary,
    ProfileTracker,
    Profiler,
)


@pytest.fixture(autouse=True)
def reset_profiler():
    Profiler.reset()
    yield
    Profiler.reset()


# =============================================================================
# ProfileEntry 검증
# =============================================================================

class TestProfileEntry:
    def test_slots(self):
        assert hasattr(ProfileEntry, "__slots__")

    def test_creation(self):
        e = ProfileEntry(name="test", duration_sec=0.05, timestamp=0.0)
        assert e.duration_sec == pytest.approx(0.05)

    def test_duration_ms(self):
        e = ProfileEntry(name="test", duration_sec=0.033, timestamp=0.0)
        assert e.duration_ms == pytest.approx(33.0)

    def test_repr(self):
        e = ProfileEntry(name="fn", duration_sec=0.01, timestamp=0.0)
        assert "fn" in repr(e)
        assert "ms" in repr(e)

    def test_memory(self):
        e = ProfileEntry(
            name="test", duration_sec=0.01, timestamp=0.0,
            memory_mb=128.5,
        )
        assert e.memory_mb == pytest.approx(128.5)
        assert "MB" in repr(e)


# =============================================================================
# ProfileSummary 검증
# =============================================================================

class TestProfileSummary:
    def test_slots(self):
        assert hasattr(ProfileSummary, "__slots__")

    def test_mean_ms(self):
        s = ProfileSummary(
            name="test", call_count=10, total_sec=0.5,
            mean_sec=0.05, min_sec=0.01, max_sec=0.1,
            p50_sec=0.04, p95_sec=0.09, p99_sec=0.1,
            mean_memory_mb=None,
        )
        assert s.mean_ms == pytest.approx(50.0)
        assert s.p95_ms == pytest.approx(90.0)

    def test_repr(self):
        s = ProfileSummary(
            name="fn", call_count=5, total_sec=0.25,
            mean_sec=0.05, min_sec=0.01, max_sec=0.1,
            p50_sec=0.05, p95_sec=0.09, p99_sec=0.1,
            mean_memory_mb=None,
        )
        assert "fn" in repr(s)
        assert "calls=5" in repr(s)


# =============================================================================
# ProfileTracker 검증
# =============================================================================

class TestProfileTracker:
    def test_add_and_count(self):
        t = ProfileTracker("test")
        t.add(ProfileEntry("test", 0.01, 0.0))
        t.add(ProfileEntry("test", 0.02, 0.0))
        assert t.count == 2

    def test_summary_empty(self):
        t = ProfileTracker("empty")
        s = t.summary()
        assert s.call_count == 0
        assert s.mean_sec == 0.0

    def test_summary_with_data(self):
        t = ProfileTracker("fn")
        for i in range(10):
            t.add(ProfileEntry("fn", float(i) / 100.0, 0.0))

        s = t.summary()
        assert s.call_count == 10
        assert s.min_sec == 0.0
        assert s.max_sec == pytest.approx(0.09)

    def test_reset(self):
        t = ProfileTracker("test")
        t.add(ProfileEntry("test", 0.01, 0.0))
        t.reset()
        assert t.count == 0

    def test_repr(self):
        t = ProfileTracker("fn")
        assert "fn" in repr(t)


# =============================================================================
# Profiler — 컨텍스트 매니저
# =============================================================================

class TestProfilerContextManager:
    def test_measure(self):
        profiler = Profiler.get_instance()
        with profiler.measure("test_op"):
            time.sleep(0.01)

        summary = profiler.get_summary("test_op")
        assert summary is not None
        assert summary.call_count == 1
        assert summary.mean_sec > 0

    def test_measure_multiple(self):
        profiler = Profiler.get_instance()
        for _ in range(5):
            with profiler.measure("multi"):
                pass

        summary = profiler.get_summary("multi")
        assert summary is not None
        assert summary.call_count == 5

    def test_measure_with_memory(self):
        profiler = Profiler.get_instance()
        with profiler.measure("mem_test", track_memory=True):
            _ = [0] * 1000

        summary = profiler.get_summary("mem_test")
        assert summary is not None
        assert summary.call_count == 1

    def test_measure_exception(self):
        """예외 발생해도 프로파일 기록."""
        profiler = Profiler.get_instance()
        with pytest.raises(ValueError):
            with profiler.measure("exc_test"):
                raise ValueError("test")

        summary = profiler.get_summary("exc_test")
        assert summary is not None
        assert summary.call_count == 1


# =============================================================================
# Profiler — 데코레이터
# =============================================================================

class TestProfilerDecorator:
    def test_profile_decorator(self):
        profiler = Profiler.get_instance()

        @profiler.profile("decorated_fn")
        def my_function():
            return 42

        result = my_function()
        assert result == 42

        summary = profiler.get_summary("decorated_fn")
        assert summary is not None
        assert summary.call_count == 1

    def test_profile_auto_name(self):
        profiler = Profiler.get_instance()

        @profiler.profile()
        def another_function():
            pass

        another_function()

        # 자동 이름: module.qualname
        names = profiler.profile_names
        assert len(names) >= 1

    def test_profile_with_args(self):
        profiler = Profiler.get_instance()

        @profiler.profile("add_fn")
        def add(a: int, b: int) -> int:
            return a + b

        result = add(3, 4)
        assert result == 7


# =============================================================================
# Profiler — 수동 기록
# =============================================================================

class TestProfilerManualRecord:
    def test_record_duration(self):
        profiler = Profiler.get_instance()
        profiler.record_duration("manual", 0.123)

        summary = profiler.get_summary("manual")
        assert summary is not None
        assert summary.mean_sec == pytest.approx(0.123)


# =============================================================================
# Profiler — 조회 및 관리
# =============================================================================

class TestProfilerManagement:
    def test_singleton(self):
        p1 = Profiler.get_instance()
        p2 = Profiler.get_instance()
        assert p1 is p2

    def test_get_all_summaries(self):
        profiler = Profiler.get_instance()
        profiler.record_duration("a", 0.01)
        profiler.record_duration("b", 0.02)

        all_summaries = profiler.get_all_summaries()
        assert len(all_summaries) == 2
        assert "a" in all_summaries

    def test_get_summary_missing(self):
        profiler = Profiler.get_instance()
        assert profiler.get_summary("missing") is None

    def test_clear_all(self):
        profiler = Profiler.get_instance()
        profiler.record_duration("a", 0.01)
        profiler.record_duration("b", 0.02)
        cleared = profiler.clear()
        assert cleared == 2
        assert profiler.profile_count == 0

    def test_clear_specific(self):
        profiler = Profiler.get_instance()
        profiler.record_duration("a", 0.01)
        profiler.record_duration("b", 0.02)
        cleared = profiler.clear("a")
        assert cleared == 1
        assert profiler.profile_count == 2  # 트래커는 유지, 이력만 클리어

    def test_profile_names(self):
        profiler = Profiler.get_instance()
        profiler.record_duration("x", 0.01)
        assert "x" in profiler.profile_names

    def test_repr(self):
        profiler = Profiler.get_instance()
        assert "profiles=" in repr(profiler)


# =============================================================================
# 스레드 안전 검증
# =============================================================================

class TestThreadSafety:
    def test_concurrent_measure(self):
        profiler = Profiler.get_instance()
        errors: list[Exception] = []

        def measure():
            try:
                for _ in range(20):
                    with profiler.measure("thread_test"):
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=measure) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        summary = profiler.get_summary("thread_test")
        assert summary is not None
        assert summary.call_count == 200


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_history(self):
        assert DEFAULT_PROFILE_HISTORY == 200

    def test_max_count(self):
        assert MAX_PROFILE_COUNT == 500

    def test_bytes_to_mb(self):
        assert BYTES_TO_MB == pytest.approx(1.0 / (1024 * 1024))


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.monitoring.profiler as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.monitoring.profiler as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.monitoring.profiler as mod
        assert mod.__version__ == "1.0.0"
