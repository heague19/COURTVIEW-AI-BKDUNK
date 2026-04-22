# -*- coding: utf-8 -*-
"""infrastructure/cache/cache_strategies.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import time

import pytest

from infrastructure.cache.cache_strategies import (
    DEFAULT_MAX_ENTRIES,
    DEFAULT_TTL_SEC,
    MAX_CACHE_ENTRIES,
    MIN_CACHE_ENTRIES,
    BaseCacheStrategy,
    CacheEntry,
    CombinedStrategy,
    EvictionResult,
    EvictionStrategy,
    LFUStrategy,
    LRUStrategy,
    TTLStrategy,
    create_strategy,
)


# =============================================================================
# 헬퍼
# =============================================================================

def _make_entry(
    key: str,
    value: str = "val",
    *,
    ttl_sec: float = 0.0,
    access_count: int = 0,
    last_accessed_offset: float = 0.0,
) -> CacheEntry:
    """테스트용 CacheEntry 생성."""
    now = time.monotonic()
    return CacheEntry(
        key=key,
        value=value,
        created_at=now,
        last_accessed_at=now + last_accessed_offset,
        access_count=access_count,
        ttl_sec=ttl_sec,
    )


def _make_entries(count: int, **kwargs) -> dict[str, CacheEntry]:
    """테스트용 다수 CacheEntry 생성."""
    entries: dict[str, CacheEntry] = {}
    for i in range(count):
        key = f"key_{i}"
        entry = _make_entry(key, f"val_{i}", **kwargs)
        # 접근 순서 구분을 위해 offset
        entry.last_accessed_at = time.monotonic() + i * 0.001
        entries[key] = entry
    return entries


# =============================================================================
# EvictionStrategy 검증
# =============================================================================

class TestEvictionStrategy:
    def test_member_count(self):
        assert len(EvictionStrategy) == 4

    def test_values(self):
        assert EvictionStrategy.LRU.value == "lru"
        assert EvictionStrategy.TTL.value == "ttl"
        assert EvictionStrategy.LFU.value == "lfu"
        assert EvictionStrategy.COMBINED.value == "combined"

    def test_to_korean(self):
        assert EvictionStrategy.LRU.to_korean() == "최근 최소 사용"
        assert EvictionStrategy.TTL.to_korean() == "만료 시각 기반"
        assert EvictionStrategy.LFU.to_korean() == "최소 빈도 사용"
        assert EvictionStrategy.COMBINED.to_korean() == "TTL+LRU 복합"


# =============================================================================
# CacheEntry 검증
# =============================================================================

class TestCacheEntry:
    def test_slots(self):
        assert hasattr(CacheEntry, "__slots__")

    def test_creation(self):
        entry = _make_entry("test")
        assert entry.key == "test"
        assert entry.value == "val"
        assert entry.access_count == 0

    def test_is_expired_no_ttl(self):
        entry = _make_entry("k", ttl_sec=0.0)
        assert entry.is_expired is False

    def test_is_expired_future(self):
        entry = _make_entry("k", ttl_sec=3600.0)
        assert entry.is_expired is False

    def test_is_expired_past(self):
        entry = _make_entry("k", ttl_sec=0.001)
        entry.created_at = time.monotonic() - 1.0  # 1초 전 생성
        assert entry.is_expired is True

    def test_expires_at_no_ttl(self):
        entry = _make_entry("k", ttl_sec=0.0)
        assert entry.expires_at == 0.0

    def test_expires_at_with_ttl(self):
        entry = _make_entry("k", ttl_sec=60.0)
        assert entry.expires_at > 0
        assert entry.expires_at == entry.created_at + 60.0

    def test_touch(self):
        entry = _make_entry("k")
        assert entry.access_count == 0
        old_accessed = entry.last_accessed_at

        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed_at >= old_accessed

        entry.touch()
        assert entry.access_count == 2

    def test_repr(self):
        entry = _make_entry("test_key")
        text = repr(entry)
        assert "test_key" in text
        assert "access_count=" in text


# =============================================================================
# EvictionResult 검증
# =============================================================================

class TestEvictionResult:
    def test_slots(self):
        assert hasattr(EvictionResult, "__slots__")

    def test_creation(self):
        result = EvictionResult(
            evicted_keys=["a", "b"],
            evicted_count=2,
            reason="test",
        )
        assert result.evicted_count == 2
        assert len(result.evicted_keys) == 2

    def test_repr(self):
        result = EvictionResult(evicted_keys=[], evicted_count=0, reason="none")
        assert "count=0" in repr(result)


# =============================================================================
# LRUStrategy 검증
# =============================================================================

class TestLRUStrategy:
    def test_strategy_type(self):
        s = LRUStrategy()
        assert s.strategy_type == EvictionStrategy.LRU

    def test_should_evict_under_limit(self):
        s = LRUStrategy()
        entries = _make_entries(5)
        assert s.should_evict(entries, 10) is False

    def test_should_evict_over_limit(self):
        s = LRUStrategy()
        entries = _make_entries(5)
        assert s.should_evict(entries, 3) is True

    def test_evict_no_overflow(self):
        s = LRUStrategy()
        entries = _make_entries(3)
        result = s.evict(entries, 5)
        assert result.evicted_count == 0
        assert len(entries) == 3

    def test_evict_overflow(self):
        s = LRUStrategy()
        entries = _make_entries(5)
        result = s.evict(entries, 3)
        assert result.evicted_count == 2
        assert len(entries) == 3

    def test_evict_removes_oldest_accessed(self):
        s = LRUStrategy()
        entries: dict[str, CacheEntry] = {}

        now = time.monotonic()
        for i, key in enumerate(["old", "medium", "recent"]):
            entry = _make_entry(key)
            entry.last_accessed_at = now + i * 0.1  # old < medium < recent
            entries[key] = entry

        result = s.evict(entries, 1)
        assert result.evicted_count == 2
        assert "old" in result.evicted_keys
        assert "medium" in result.evicted_keys
        assert "recent" in entries

    def test_evict_exact_limit(self):
        s = LRUStrategy()
        entries = _make_entries(5)
        result = s.evict(entries, 5)
        assert result.evicted_count == 0

    def test_repr(self):
        s = LRUStrategy()
        assert "lru" in repr(s).lower()


# =============================================================================
# TTLStrategy 검증
# =============================================================================

class TestTTLStrategy:
    def test_strategy_type(self):
        s = TTLStrategy()
        assert s.strategy_type == EvictionStrategy.TTL

    def test_should_evict_no_expired(self):
        s = TTLStrategy()
        entries = _make_entries(3, ttl_sec=3600.0)
        assert s.should_evict(entries, 100) is False

    def test_should_evict_with_expired(self):
        s = TTLStrategy()
        entries = _make_entries(3, ttl_sec=3600.0)
        # 하나를 만료시킴
        key = list(entries.keys())[0]
        entries[key].created_at = time.monotonic() - 7200
        assert s.should_evict(entries, 100) is True

    def test_evict_no_expired(self):
        s = TTLStrategy()
        entries = _make_entries(3, ttl_sec=3600.0)
        result = s.evict(entries, 100)
        assert result.evicted_count == 0
        assert len(entries) == 3

    def test_evict_expired(self):
        s = TTLStrategy()
        entries = _make_entries(5, ttl_sec=0.001)
        # 전부 만료시킴
        for entry in entries.values():
            entry.created_at = time.monotonic() - 1.0

        result = s.evict(entries, 100)
        assert result.evicted_count == 5
        assert len(entries) == 0

    def test_evict_partial_expired(self):
        s = TTLStrategy()
        entries: dict[str, CacheEntry] = {}

        # 만료 2개
        for i in range(2):
            e = _make_entry(f"expired_{i}", ttl_sec=0.001)
            e.created_at = time.monotonic() - 1.0
            entries[e.key] = e

        # 유효 3개
        for i in range(3):
            e = _make_entry(f"valid_{i}", ttl_sec=3600.0)
            entries[e.key] = e

        result = s.evict(entries, 100)
        assert result.evicted_count == 2
        assert len(entries) == 3

    def test_evict_no_ttl_entries(self):
        s = TTLStrategy()
        entries = _make_entries(3, ttl_sec=0.0)
        result = s.evict(entries, 100)
        assert result.evicted_count == 0  # ttl=0 → 만료 없음


# =============================================================================
# LFUStrategy 검증
# =============================================================================

class TestLFUStrategy:
    def test_strategy_type(self):
        s = LFUStrategy()
        assert s.strategy_type == EvictionStrategy.LFU

    def test_should_evict_under_limit(self):
        s = LFUStrategy()
        entries = _make_entries(3)
        assert s.should_evict(entries, 5) is False

    def test_should_evict_over_limit(self):
        s = LFUStrategy()
        entries = _make_entries(5)
        assert s.should_evict(entries, 3) is True

    def test_evict_no_overflow(self):
        s = LFUStrategy()
        entries = _make_entries(3)
        result = s.evict(entries, 5)
        assert result.evicted_count == 0

    def test_evict_removes_least_frequent(self):
        s = LFUStrategy()
        entries: dict[str, CacheEntry] = {}

        # 접근 빈도 다르게
        for i, (key, count) in enumerate([("rare", 1), ("medium", 5), ("popular", 10)]):
            entry = _make_entry(key, access_count=count)
            entry.last_accessed_at = time.monotonic() + i * 0.1
            entries[key] = entry

        result = s.evict(entries, 1)
        assert result.evicted_count == 2
        assert "rare" in result.evicted_keys
        assert "medium" in result.evicted_keys
        assert "popular" in entries

    def test_evict_tiebreak_by_access_time(self):
        """동일 빈도 시 마지막 접근 시각이 오래된 것 우선 퇴거."""
        s = LFUStrategy()
        entries: dict[str, CacheEntry] = {}
        now = time.monotonic()

        # 모두 access_count=1, 접근 시각만 다름
        for i, key in enumerate(["oldest", "middle", "newest"]):
            entry = _make_entry(key, access_count=1)
            entry.last_accessed_at = now + i * 0.1
            entries[key] = entry

        result = s.evict(entries, 1)
        assert result.evicted_count == 2
        assert "oldest" in result.evicted_keys
        assert "middle" in result.evicted_keys
        assert "newest" in entries


# =============================================================================
# CombinedStrategy 검증
# =============================================================================

class TestCombinedStrategy:
    def test_strategy_type(self):
        s = CombinedStrategy()
        assert s.strategy_type == EvictionStrategy.COMBINED

    def test_should_evict_no_need(self):
        s = CombinedStrategy()
        entries = _make_entries(3, ttl_sec=3600.0)
        assert s.should_evict(entries, 5) is False

    def test_should_evict_ttl(self):
        s = CombinedStrategy()
        entries = _make_entries(3, ttl_sec=0.001)
        for e in entries.values():
            e.created_at = time.monotonic() - 1.0
        assert s.should_evict(entries, 100) is True

    def test_should_evict_overflow(self):
        s = CombinedStrategy()
        entries = _make_entries(5)
        assert s.should_evict(entries, 3) is True

    def test_evict_no_need(self):
        s = CombinedStrategy()
        entries = _make_entries(3, ttl_sec=3600.0)
        result = s.evict(entries, 5)
        assert result.evicted_count == 0

    def test_evict_ttl_only(self):
        s = CombinedStrategy()
        entries: dict[str, CacheEntry] = {}

        # 만료 2개 + 유효 2개 (용량 미초과)
        for i in range(2):
            e = _make_entry(f"expired_{i}", ttl_sec=0.001)
            e.created_at = time.monotonic() - 1.0
            entries[e.key] = e
        for i in range(2):
            e = _make_entry(f"valid_{i}", ttl_sec=3600.0)
            entries[e.key] = e

        result = s.evict(entries, 5)
        assert result.evicted_count == 2
        assert len(entries) == 2
        assert "TTL:2" in result.reason

    def test_evict_lru_only(self):
        s = CombinedStrategy()
        entries = _make_entries(5)  # ttl=0 → 만료 없음
        result = s.evict(entries, 3)
        assert result.evicted_count == 2
        assert len(entries) == 3
        assert "LRU:2" in result.reason

    def test_evict_ttl_then_lru(self):
        """TTL 퇴거 후에도 용량 초과면 LRU 추가 퇴거."""
        s = CombinedStrategy()
        entries: dict[str, CacheEntry] = {}
        now = time.monotonic()

        # 만료 1개
        e = _make_entry("expired_0", ttl_sec=0.001)
        e.created_at = now - 1.0
        entries[e.key] = e

        # 유효 5개 (용량 3 초과)
        for i in range(5):
            e = _make_entry(f"valid_{i}", ttl_sec=3600.0)
            e.last_accessed_at = now + i * 0.1
            entries[e.key] = e

        result = s.evict(entries, 3)
        assert len(entries) == 3
        assert "TTL:1" in result.reason
        assert "LRU:2" in result.reason


# =============================================================================
# create_strategy 팩토리
# =============================================================================

class TestCreateStrategy:
    def test_create_lru(self):
        s = create_strategy(EvictionStrategy.LRU)
        assert isinstance(s, LRUStrategy)

    def test_create_ttl(self):
        s = create_strategy(EvictionStrategy.TTL)
        assert isinstance(s, TTLStrategy)

    def test_create_lfu(self):
        s = create_strategy(EvictionStrategy.LFU)
        assert isinstance(s, LFUStrategy)

    def test_create_combined(self):
        s = create_strategy(EvictionStrategy.COMBINED)
        assert isinstance(s, CombinedStrategy)


# =============================================================================
# BaseCacheStrategy 추상 검증
# =============================================================================

class TestBaseCacheStrategy:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseCacheStrategy()  # type: ignore[abstract]


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_default_ttl(self):
        assert DEFAULT_TTL_SEC == 300.0

    def test_default_max_entries(self):
        assert DEFAULT_MAX_ENTRIES == 1000

    def test_min_cache_entries(self):
        assert MIN_CACHE_ENTRIES == 10

    def test_max_cache_entries(self):
        assert MAX_CACHE_ENTRIES == 100000


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import infrastructure.cache.cache_strategies as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import infrastructure.cache.cache_strategies as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"__all__ 항목 '{name}' 누락"

    def test_version(self):
        import infrastructure.cache.cache_strategies as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import infrastructure.cache.cache_strategies as mod
        assert len(mod.__all__) == 13
