# -*- coding: utf-8 -*-
"""infrastructure/cache/model_cache.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import hashlib
import threading
import time

import pytest

from infrastructure.cache.cache_manager import CacheManager
from infrastructure.cache.cache_strategies import EvictionStrategy
from infrastructure.cache.model_cache import (
    FRAME_HASH_ALGORITHM,
    MAX_CACHED_MODELS,
    MODEL_CACHE_DEFAULT_MAX_ENTRIES,
    MODEL_CACHE_DEFAULT_TTL_SEC,
    MODEL_CACHE_PREFIX,
    ModelCache,
    ModelCacheStats,
)


@pytest.fixture(autouse=True)
def reset_all():
    ModelCache.reset()
    CacheManager.reset()
    yield
    ModelCache.reset()
    CacheManager.reset()


# =============================================================================
# ModelCacheStats 검증
# =============================================================================

class TestModelCacheStats:
    def test_slots(self):
        assert hasattr(ModelCacheStats, "__slots__")

    def test_creation(self):
        stats = ModelCacheStats(
            model_name="yolo",
            entry_count=10,
            max_entries=100,
            hits=8,
            misses=2,
            hit_rate=0.8,
            total_size_bytes=4096,
            evictions=1,
        )
        assert stats.model_name == "yolo"
        assert stats.hit_rate == 0.8

    def test_repr(self):
        stats = ModelCacheStats(
            model_name="test",
            entry_count=5, max_entries=50,
            hits=3, misses=1, hit_rate=0.75,
            total_size_bytes=0, evictions=0,
        )
        text = repr(stats)
        assert "test" in text
        assert "5/50" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        c1 = ModelCache.get_instance()
        c2 = ModelCache.get_instance()
        assert c1 is c2

    def test_reset(self):
        c1 = ModelCache.get_instance()
        ModelCache.reset()
        CacheManager.reset()
        c2 = ModelCache.get_instance()
        assert c1 is not c2


# =============================================================================
# 모델 등록
# =============================================================================

class TestRegisterModel:
    def test_register(self):
        cache = ModelCache.get_instance()
        assert cache.register_model("yolo_ball") is True
        assert cache.is_registered("yolo_ball") is True

    def test_register_duplicate(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo_ball")
        assert cache.register_model("yolo_ball") is False

    def test_register_with_options(self):
        cache = ModelCache.get_instance()
        cache.register_model(
            "custom_model",
            max_entries=200,
            ttl_sec=30.0,
            strategy=EvictionStrategy.LRU,
        )
        assert cache.is_registered("custom_model") is True

    def test_unregister(self):
        cache = ModelCache.get_instance()
        cache.register_model("temp_model")
        assert cache.unregister_model("temp_model") is True
        assert cache.is_registered("temp_model") is False

    def test_unregister_nonexistent(self):
        cache = ModelCache.get_instance()
        assert cache.unregister_model("missing") is False

    def test_registered_models(self):
        cache = ModelCache.get_instance()
        cache.register_model("m1")
        cache.register_model("m2")
        models = cache.registered_models
        assert "m1" in models and "m2" in models

    def test_model_count(self):
        cache = ModelCache.get_instance()
        assert cache.model_count == 0
        cache.register_model("m1")
        assert cache.model_count == 1

    def test_max_models_limit(self):
        cache = ModelCache.get_instance()
        for i in range(MAX_CACHED_MODELS):
            cache.register_model(f"model_{i}")
        assert cache.register_model("overflow") is False


# =============================================================================
# get / set / has / delete
# =============================================================================

class TestCoreAPI:
    def test_set_and_get(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        cache.set("yolo", "hash_abc", {"boxes": [1, 2, 3]})
        result = cache.get("yolo", "hash_abc")
        assert result == {"boxes": [1, 2, 3]}

    def test_get_missing(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        assert cache.get("yolo", "missing_hash") is None

    def test_get_unregistered_model(self):
        cache = ModelCache.get_instance()
        assert cache.get("unregistered", "hash") is None

    def test_set_unregistered_model(self):
        cache = ModelCache.get_instance()
        assert cache.set("unregistered", "hash", "val") is False

    def test_has(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        cache.set("yolo", "h1", "val")
        assert cache.has("yolo", "h1") is True
        assert cache.has("yolo", "h2") is False

    def test_has_unregistered(self):
        cache = ModelCache.get_instance()
        assert cache.has("nope", "h") is False

    def test_delete(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        cache.set("yolo", "h1", "val")
        assert cache.delete("yolo", "h1") is True
        assert cache.has("yolo", "h1") is False

    def test_delete_unregistered(self):
        cache = ModelCache.get_instance()
        assert cache.delete("nope", "h") is False

    def test_custom_ttl(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo", ttl_sec=3600.0)
        cache.set("yolo", "h1", "val", ttl_sec=0.01)
        assert cache.get("yolo", "h1") == "val"
        time.sleep(0.05)
        assert cache.get("yolo", "h1") is None

    def test_model_isolation(self):
        """모델 간 캐시 격리."""
        cache = ModelCache.get_instance()
        cache.register_model("model_a")
        cache.register_model("model_b")

        cache.set("model_a", "hash1", "result_a")
        cache.set("model_b", "hash1", "result_b")

        assert cache.get("model_a", "hash1") == "result_a"
        assert cache.get("model_b", "hash1") == "result_b"


# =============================================================================
# 일괄 작업
# =============================================================================

class TestBatchOps:
    def test_clear_model(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        for i in range(5):
            cache.set("yolo", f"h{i}", f"v{i}")
        count = cache.clear_model("yolo")
        assert count == 5
        assert cache.total_entry_count == 0

    def test_clear_model_unregistered(self):
        cache = ModelCache.get_instance()
        assert cache.clear_model("nope") == 0

    def test_clear_all(self):
        cache = ModelCache.get_instance()
        cache.register_model("m1")
        cache.register_model("m2")
        cache.set("m1", "h1", "v1")
        cache.set("m2", "h2", "v2")

        count = cache.clear_all()
        assert count == 2
        assert cache.total_entry_count == 0

    def test_cleanup_expired_specific(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo", ttl_sec=3600.0)
        cache.set("yolo", "alive", "v1")
        cache.set("yolo", "dead", "v2", ttl_sec=0.01)

        time.sleep(0.05)
        count = cache.cleanup_expired("yolo")
        assert count == 1

    def test_cleanup_expired_all(self):
        cache = ModelCache.get_instance()
        cache.register_model("m1", ttl_sec=0.01)
        cache.register_model("m2", ttl_sec=0.01)
        cache.set("m1", "h1", "v1")
        cache.set("m2", "h2", "v2")

        time.sleep(0.05)
        count = cache.cleanup_expired()
        assert count == 2

    def test_cleanup_unregistered(self):
        cache = ModelCache.get_instance()
        assert cache.cleanup_expired("nope") == 0


# =============================================================================
# 프레임 해시
# =============================================================================

class TestFrameHash:
    def test_compute_frame_hash(self):
        data = b"frame_data_bytes"
        h = ModelCache.compute_frame_hash(data)
        assert len(h) == 64
        assert h == hashlib.sha256(data).hexdigest()

    def test_deterministic(self):
        data = b"same_data"
        assert ModelCache.compute_frame_hash(data) == ModelCache.compute_frame_hash(data)

    def test_different_data(self):
        h1 = ModelCache.compute_frame_hash(b"frame1")
        h2 = ModelCache.compute_frame_hash(b"frame2")
        assert h1 != h2

    def test_composite_hash(self):
        h = ModelCache.compute_composite_hash("base_hash", roi="0,0,100,100")
        assert len(h) == 64

    def test_composite_hash_different_roi(self):
        h1 = ModelCache.compute_composite_hash("base", roi="0,0,100,100")
        h2 = ModelCache.compute_composite_hash("base", roi="50,50,200,200")
        assert h1 != h2

    def test_composite_hash_different_params(self):
        h1 = ModelCache.compute_composite_hash("base", params="conf=0.5")
        h2 = ModelCache.compute_composite_hash("base", params="conf=0.8")
        assert h1 != h2

    def test_composite_hash_deterministic(self):
        h1 = ModelCache.compute_composite_hash("base", roi="r", params="p")
        h2 = ModelCache.compute_composite_hash("base", roi="r", params="p")
        assert h1 == h2


# =============================================================================
# 통계
# =============================================================================

class TestStats:
    def test_get_model_stats(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        cache.set("yolo", "h1", "v1")
        cache.get("yolo", "h1")  # hit
        cache.get("yolo", "h2")  # miss

        stats = cache.get_model_stats("yolo")
        assert stats is not None
        assert stats.model_name == "yolo"
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.entry_count == 1

    def test_get_model_stats_unregistered(self):
        cache = ModelCache.get_instance()
        assert cache.get_model_stats("nope") is None

    def test_get_all_stats(self):
        cache = ModelCache.get_instance()
        cache.register_model("m1")
        cache.register_model("m2")

        all_stats = cache.get_all_stats()
        assert len(all_stats) == 2

    def test_total_entry_count(self):
        cache = ModelCache.get_instance()
        cache.register_model("m1")
        cache.register_model("m2")
        cache.set("m1", "h1", "v1")
        cache.set("m2", "h2", "v2")
        assert cache.total_entry_count == 2


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_set_get(self):
        cache = ModelCache.get_instance()
        cache.register_model("yolo")
        errors: list[Exception] = []

        def worker(tid: int):
            try:
                for i in range(30):
                    key = f"t{tid}_f{i}"
                    cache.set("yolo", key, f"result_{key}")
                    cache.get("yolo", key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        cache = ModelCache.get_instance()
        text = repr(cache)
        assert "ModelCache" in text
        assert "models=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_model_cache_prefix(self):
        assert MODEL_CACHE_PREFIX == "model_cache:"

    def test_default_ttl(self):
        assert MODEL_CACHE_DEFAULT_TTL_SEC == 60.0

    def test_default_max_entries(self):
        assert MODEL_CACHE_DEFAULT_MAX_ENTRIES == 500

    def test_max_cached_models(self):
        assert MAX_CACHED_MODELS == 30

    def test_frame_hash_algorithm(self):
        assert FRAME_HASH_ALGORITHM == "sha256"


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.cache.model_cache as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.cache.model_cache as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import infrastructure.cache.model_cache as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.cache.model_cache as mod
        assert len(mod.__all__) == 7
