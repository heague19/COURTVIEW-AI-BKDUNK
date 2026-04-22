# -*- coding: utf-8 -*-
"""infrastructure/cache/cache_manager.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
import time

import pytest

from infrastructure.cache.cache_manager import (
    DEFAULT_ENTRY_SIZE_BYTES,
    DEFAULT_NAMESPACE,
    MAX_NAMESPACES,
    CacheManager,
    CacheStats,
)
from infrastructure.cache.cache_strategies import (
    DEFAULT_MAX_ENTRIES,
    DEFAULT_TTL_SEC,
    EvictionStrategy,
)


@pytest.fixture(autouse=True)
def reset_manager():
    CacheManager.reset()
    yield
    CacheManager.reset()


# =============================================================================
# CacheStats 검증
# =============================================================================

class TestCacheStats:
    def test_slots(self):
        assert hasattr(CacheStats, "__slots__")

    def test_hit_rate_zero(self):
        stats = CacheStats(
            namespace="test", entry_count=0, max_entries=100,
            hits=0, misses=0, evictions=0, total_size_bytes=0,
            strategy=EvictionStrategy.LRU,
        )
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculated(self):
        stats = CacheStats(
            namespace="test", entry_count=0, max_entries=100,
            hits=7, misses=3, evictions=0, total_size_bytes=0,
            strategy=EvictionStrategy.LRU,
        )
        assert abs(stats.hit_rate - 0.7) < 0.001

    def test_repr(self):
        stats = CacheStats(
            namespace="ns", entry_count=5, max_entries=100,
            hits=10, misses=2, evictions=1, total_size_bytes=1024,
            strategy=EvictionStrategy.COMBINED,
        )
        text = repr(stats)
        assert "ns" in text
        assert "5/100" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        m1 = CacheManager.get_instance()
        m2 = CacheManager.get_instance()
        assert m1 is m2

    def test_reset(self):
        m1 = CacheManager.get_instance()
        CacheManager.reset()
        m2 = CacheManager.get_instance()
        assert m1 is not m2


# =============================================================================
# 기본 네임스페이스
# =============================================================================

class TestDefaultNamespace:
    def test_default_exists(self):
        mgr = CacheManager.get_instance()
        assert mgr.has_namespace(DEFAULT_NAMESPACE) is True

    def test_default_in_names(self):
        mgr = CacheManager.get_instance()
        assert DEFAULT_NAMESPACE in mgr.namespace_names

    def test_cannot_remove_default(self):
        mgr = CacheManager.get_instance()
        assert mgr.remove_namespace(DEFAULT_NAMESPACE) is False


# =============================================================================
# 네임스페이스 관리
# =============================================================================

class TestNamespaceManagement:
    def test_create_namespace(self):
        mgr = CacheManager.get_instance()
        assert mgr.create_namespace("detection") is True
        assert mgr.has_namespace("detection") is True

    def test_create_duplicate(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("ns1")
        assert mgr.create_namespace("ns1") is False

    def test_create_with_strategy(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("lru_ns", strategy=EvictionStrategy.LRU)
        stats = mgr.get_stats(namespace="lru_ns")
        assert len(stats) == 1
        assert stats[0].strategy == EvictionStrategy.LRU

    def test_remove_namespace(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("temp")
        assert mgr.remove_namespace("temp") is True
        assert mgr.has_namespace("temp") is False

    def test_remove_nonexistent(self):
        mgr = CacheManager.get_instance()
        assert mgr.remove_namespace("nonexistent") is False

    def test_namespace_count(self):
        mgr = CacheManager.get_instance()
        assert mgr.namespace_count == 1  # default
        mgr.create_namespace("ns1")
        assert mgr.namespace_count == 2

    def test_max_namespaces_limit(self):
        mgr = CacheManager.get_instance()
        for i in range(MAX_NAMESPACES - 1):  # default 이미 1개
            mgr.create_namespace(f"ns_{i}")
        assert mgr.namespace_count == MAX_NAMESPACES
        assert mgr.create_namespace("overflow") is False

    def test_max_entries_clamped(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("small", max_entries=1)
        # MIN_CACHE_ENTRIES(10)로 클램프됨
        stats = mgr.get_stats(namespace="small")
        assert stats[0].max_entries == 10


# =============================================================================
# get / set / has / delete
# =============================================================================

class TestCoreAPI:
    def test_set_and_get(self):
        mgr = CacheManager.get_instance()
        mgr.set("key1", "value1")
        assert mgr.get("key1") == "value1"

    def test_get_missing(self):
        mgr = CacheManager.get_instance()
        assert mgr.get("missing") is None

    def test_get_nonexistent_namespace(self):
        mgr = CacheManager.get_instance()
        assert mgr.get("key", namespace="nonexistent") is None

    def test_set_nonexistent_namespace(self):
        mgr = CacheManager.get_instance()
        assert mgr.set("key", "val", namespace="nonexistent") is False

    def test_has(self):
        mgr = CacheManager.get_instance()
        mgr.set("exists", "val")
        assert mgr.has("exists") is True
        assert mgr.has("missing") is False

    def test_has_nonexistent_namespace(self):
        mgr = CacheManager.get_instance()
        assert mgr.has("key", namespace="nope") is False

    def test_delete(self):
        mgr = CacheManager.get_instance()
        mgr.set("key", "val")
        assert mgr.delete("key") is True
        assert mgr.has("key") is False

    def test_delete_missing(self):
        mgr = CacheManager.get_instance()
        assert mgr.delete("missing") is False

    def test_delete_nonexistent_namespace(self):
        mgr = CacheManager.get_instance()
        assert mgr.delete("key", namespace="nope") is False

    def test_overwrite(self):
        mgr = CacheManager.get_instance()
        mgr.set("key", "v1")
        mgr.set("key", "v2")
        assert mgr.get("key") == "v2"

    def test_set_with_custom_ttl(self):
        mgr = CacheManager.get_instance()
        mgr.set("key", "val", ttl_sec=0.01)
        assert mgr.get("key") == "val"
        time.sleep(0.05)
        assert mgr.get("key") is None  # 만료

    def test_set_in_custom_namespace(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("custom")
        mgr.set("key", "custom_val", namespace="custom")

        assert mgr.get("key", namespace="custom") == "custom_val"
        assert mgr.get("key") is None  # default에는 없음


# =============================================================================
# clear / cleanup
# =============================================================================

class TestClearAndCleanup:
    def test_clear_specific(self):
        mgr = CacheManager.get_instance()
        for i in range(5):
            mgr.set(f"k{i}", f"v{i}")
        count = mgr.clear(namespace=DEFAULT_NAMESPACE)
        assert count == 5
        assert mgr.total_entry_count == 0

    def test_clear_all(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("ns1")
        mgr.set("k1", "v1")
        mgr.set("k2", "v2", namespace="ns1")

        count = mgr.clear()
        assert count == 2
        assert mgr.total_entry_count == 0

    def test_clear_nonexistent(self):
        mgr = CacheManager.get_instance()
        assert mgr.clear(namespace="nope") == 0

    def test_cleanup_expired(self):
        mgr = CacheManager.get_instance()
        mgr.set("alive", "v1", ttl_sec=3600.0)
        mgr.set("dead", "v2", ttl_sec=0.01)

        time.sleep(0.05)
        count = mgr.cleanup_expired()
        assert count == 1
        assert mgr.has("alive") is True
        assert mgr.has("dead") is False

    def test_cleanup_nonexistent(self):
        mgr = CacheManager.get_instance()
        assert mgr.cleanup_expired(namespace="nope") == 0

    def test_cleanup_all_namespaces(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("ns1")
        mgr.set("dead1", "v", ttl_sec=0.01)
        mgr.set("dead2", "v", ttl_sec=0.01, namespace="ns1")

        time.sleep(0.05)
        count = mgr.cleanup_expired()
        assert count == 2


# =============================================================================
# keys
# =============================================================================

class TestKeys:
    def test_keys(self):
        mgr = CacheManager.get_instance()
        mgr.set("a", 1)
        mgr.set("b", 2)
        keys = mgr.keys()
        assert "a" in keys and "b" in keys

    def test_keys_nonexistent(self):
        mgr = CacheManager.get_instance()
        assert mgr.keys(namespace="nope") == []


# =============================================================================
# 통계
# =============================================================================

class TestStats:
    def test_stats_default(self):
        mgr = CacheManager.get_instance()
        stats = mgr.get_stats()
        assert len(stats) == 1
        assert stats[0].namespace == DEFAULT_NAMESPACE

    def test_stats_specific(self):
        mgr = CacheManager.get_instance()
        stats = mgr.get_stats(namespace=DEFAULT_NAMESPACE)
        assert len(stats) == 1

    def test_stats_nonexistent(self):
        mgr = CacheManager.get_instance()
        stats = mgr.get_stats(namespace="nope")
        assert len(stats) == 0

    def test_hit_miss_tracking(self):
        mgr = CacheManager.get_instance()
        mgr.set("key", "val")
        mgr.get("key")   # hit
        mgr.get("key")   # hit
        mgr.get("miss")  # miss

        stats = mgr.get_stats(namespace=DEFAULT_NAMESPACE)
        assert stats[0].hits == 2
        assert stats[0].misses == 1

    def test_reset_stats(self):
        mgr = CacheManager.get_instance()
        mgr.set("key", "val")
        mgr.get("key")
        mgr.get("miss")

        mgr.reset_stats()
        stats = mgr.get_stats(namespace=DEFAULT_NAMESPACE)
        assert stats[0].hits == 0
        assert stats[0].misses == 0

    def test_reset_stats_specific(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("ns1")
        mgr.set("k", "v")
        mgr.get("k")
        mgr.set("k", "v", namespace="ns1")
        mgr.get("k", namespace="ns1")

        mgr.reset_stats(namespace="ns1")

        stats_default = mgr.get_stats(namespace=DEFAULT_NAMESPACE)
        stats_ns1 = mgr.get_stats(namespace="ns1")
        assert stats_default[0].hits == 1  # 리셋 안 됨
        assert stats_ns1[0].hits == 0  # 리셋 됨

    def test_total_entry_count(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace("ns1")
        mgr.set("a", 1)
        mgr.set("b", 2, namespace="ns1")
        assert mgr.total_entry_count == 2


# =============================================================================
# 퇴거 동작
# =============================================================================

class TestEviction:
    def test_lru_eviction(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace(
            "lru_test",
            strategy=EvictionStrategy.LRU,
            max_entries=10,
            default_ttl=0.0,
        )
        for i in range(15):
            mgr.set(f"k{i}", f"v{i}", namespace="lru_test")

        stats = mgr.get_stats(namespace="lru_test")
        assert stats[0].entry_count == 10
        assert stats[0].evictions == 5

    def test_ttl_eviction_on_set(self):
        mgr = CacheManager.get_instance()
        mgr.create_namespace(
            "ttl_test",
            strategy=EvictionStrategy.TTL,
            max_entries=100,
            default_ttl=0.01,
        )
        mgr.set("k1", "v1", namespace="ttl_test")
        time.sleep(0.05)
        # set 시 TTL 전략이 트리거되지만 TTL은 capacity와 무관
        # 직접 get으로 확인
        assert mgr.get("k1", namespace="ttl_test") is None


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_set_and_get(self):
        mgr = CacheManager.get_instance()
        errors: list[Exception] = []

        def worker(prefix: str):
            try:
                for i in range(50):
                    key = f"{prefix}_{i}"
                    mgr.set(key, f"val_{key}")
                    mgr.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"t{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0

    def test_concurrent_singleton(self):
        instances: list[CacheManager] = []
        errors: list[Exception] = []

        def get_inst():
            try:
                instances.append(CacheManager.get_instance())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_inst) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert all(inst is instances[0] for inst in instances)


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        mgr = CacheManager.get_instance()
        text = repr(mgr)
        assert "CacheManager" in text
        assert "namespaces=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_namespaces(self):
        assert MAX_NAMESPACES == 50

    def test_default_namespace(self):
        assert DEFAULT_NAMESPACE == "default"

    def test_default_entry_size_bytes(self):
        assert DEFAULT_ENTRY_SIZE_BYTES == 256


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.cache.cache_manager as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.cache.cache_manager as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import infrastructure.cache.cache_manager as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.cache.cache_manager as mod
        assert len(mod.__all__) == 5
