# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/cache
파일: cache_manager.py
설명: 캐시 수명주기 관리자
      - 네임스페이스별 캐시 격리
      - get/set/delete/clear 핵심 API
      - 전략 기반 퇴거 (LRU/TTL/LFU/Combined)
      - 캐시 히트/미스 통계
      - 주기적 만료 정리 (cleanup)
      - 사이즈 추정
      - Singleton + 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
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
    create_strategy,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 네임스페이스 수
MAX_NAMESPACES: Final[int] = 50

# 기본 네임스페이스 이름
DEFAULT_NAMESPACE: Final[str] = "default"

# 사이즈 추정 불가 시 기본값 (바이트)
DEFAULT_ENTRY_SIZE_BYTES: Final[int] = 256


# =============================================================================
# 캐시 통계
# =============================================================================

@dataclass(slots=True)
class CacheStats:
    """캐시 통계.

    Attributes:
        namespace: 네임스페이스 이름
        entry_count: 현재 항목 수
        max_entries: 최대 항목 수
        hits: 히트 수
        misses: 미스 수
        evictions: 퇴거 수
        total_size_bytes: 총 사이즈 추정 (바이트)
        strategy: 퇴거 전략
    """

    namespace: str
    entry_count: int
    max_entries: int
    hits: int
    misses: int
    evictions: int
    total_size_bytes: int
    strategy: EvictionStrategy

    @property
    def hit_rate(self) -> float:
        """히트율 (0.0 ~ 1.0)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def __repr__(self) -> str:
        return (
            f"CacheStats(ns='{self.namespace}', "
            f"entries={self.entry_count}/{self.max_entries}, "
            f"hit_rate={self.hit_rate:.1%})"
        )


# =============================================================================
# 네임스페이스 캐시
# =============================================================================

class _NamespaceCache:
    """네임스페이스별 내부 캐시.

    단일 네임스페이스의 항목 관리 + 전략 기반 퇴거.
    """

    __slots__ = (
        "_name",
        "_entries",
        "_strategy",
        "_max_entries",
        "_default_ttl",
        "_hits",
        "_misses",
        "_evictions",
    )

    def __init__(
        self,
        name: str,
        *,
        strategy: BaseCacheStrategy,
        max_entries: int,
        default_ttl: float,
    ) -> None:
        self._name = name
        self._entries: dict[str, CacheEntry] = {}
        self._strategy = strategy
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Any | None:
        """값 조회 (None이면 미스)."""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._entries[key]
            self._misses += 1
            return None

        entry.touch()
        self._hits += 1
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl_sec: float | None = None,
    ) -> None:
        """값 저장."""
        ttl = ttl_sec if ttl_sec is not None else self._default_ttl
        now = time.monotonic()

        size = self._estimate_size(value)
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            last_accessed_at=now,
            access_count=1,
            ttl_sec=ttl,
            size_bytes=size,
        )
        self._entries[key] = entry

        # 용량 초과 시 퇴거
        if self._strategy.should_evict(self._entries, self._max_entries):
            result = self._strategy.evict(self._entries, self._max_entries)
            self._evictions += result.evicted_count

    def delete(self, key: str) -> bool:
        """항목 삭제."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def has(self, key: str) -> bool:
        """존재 여부 (만료 검사 포함)."""
        entry = self._entries.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            del self._entries[key]
            return False
        return True

    def clear(self) -> int:
        """전체 삭제."""
        count = len(self._entries)
        self._entries.clear()
        return count

    def cleanup_expired(self) -> int:
        """만료 항목 정리."""
        expired_keys = [
            key for key, entry in self._entries.items()
            if entry.is_expired
        ]
        for key in expired_keys:
            del self._entries[key]
        return len(expired_keys)

    def get_stats(self) -> CacheStats:
        """통계 조회."""
        total_size = sum(e.size_bytes for e in self._entries.values())
        return CacheStats(
            namespace=self._name,
            entry_count=len(self._entries),
            max_entries=self._max_entries,
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            total_size_bytes=total_size,
            strategy=self._strategy.strategy_type,
        )

    def reset_stats(self) -> None:
        """통계 초기화."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def keys(self) -> list[str]:
        return list(self._entries.keys())

    @staticmethod
    def _estimate_size(value: Any) -> int:
        """값 사이즈 추정 (바이트)."""
        try:
            return sys.getsizeof(value)
        except TypeError:
            return DEFAULT_ENTRY_SIZE_BYTES


# =============================================================================
# 핵심 클래스: CacheManager
# =============================================================================

class CacheManager:
    """캐시 수명주기 관리자.

    네임스페이스 기반 다중 캐시를 관리한다.
    각 네임스페이스는 독립적인 전략, 용량, TTL을 가진다.

    사용 예시::

        manager = CacheManager.get_instance()

        # 기본 네임스페이스에 저장
        manager.set("frame_hash", hash_value)
        result = manager.get("frame_hash")

        # 전용 네임스페이스 생성
        manager.create_namespace(
            "detection",
            strategy=EvictionStrategy.COMBINED,
            max_entries=500,
            default_ttl=60.0,
        )
        manager.set("bbox_result", data, namespace="detection")

        # 통계
        stats = manager.get_stats()

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: CacheManager | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._namespaces: dict[str, _NamespaceCache] = {}
        self._lock = threading.RLock()

        # 기본 네임스페이스 자동 생성
        self._namespaces[DEFAULT_NAMESPACE] = _NamespaceCache(
            DEFAULT_NAMESPACE,
            strategy=CombinedStrategy(),
            max_entries=DEFAULT_MAX_ENTRIES,
            default_ttl=DEFAULT_TTL_SEC,
        )

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> CacheManager:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 네임스페이스 관리
    # =========================================================================

    def create_namespace(
        self,
        name: str,
        *,
        strategy: EvictionStrategy = EvictionStrategy.COMBINED,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        default_ttl: float = DEFAULT_TTL_SEC,
    ) -> bool:
        """네임스페이스 생성.

        Args:
            name: 네임스페이스 이름
            strategy: 퇴거 전략
            max_entries: 최대 항목 수
            default_ttl: 기본 TTL (초)

        Returns:
            생성 성공 여부 (이미 존재하면 False)
        """
        with self._lock:
            if name in self._namespaces:
                return False
            if len(self._namespaces) >= MAX_NAMESPACES:
                return False

            clamped = max(MIN_CACHE_ENTRIES, min(max_entries, MAX_CACHE_ENTRIES))
            self._namespaces[name] = _NamespaceCache(
                name,
                strategy=create_strategy(strategy),
                max_entries=clamped,
                default_ttl=default_ttl,
            )
            return True

    def has_namespace(self, name: str) -> bool:
        """네임스페이스 존재 여부."""
        with self._lock:
            return name in self._namespaces

    def remove_namespace(self, name: str) -> bool:
        """네임스페이스 삭제 (default는 삭제 불가).

        Args:
            name: 네임스페이스 이름

        Returns:
            삭제 성공 여부
        """
        with self._lock:
            if name == DEFAULT_NAMESPACE:
                return False
            if name not in self._namespaces:
                return False
            del self._namespaces[name]
            return True

    @property
    def namespace_names(self) -> list[str]:
        """네임스페이스 목록."""
        with self._lock:
            return list(self._namespaces.keys())

    @property
    def namespace_count(self) -> int:
        """네임스페이스 수."""
        with self._lock:
            return len(self._namespaces)

    # =========================================================================
    # 핵심 API: get / set / delete / has
    # =========================================================================

    def get(self, key: str, *, namespace: str = DEFAULT_NAMESPACE) -> Any | None:
        """캐시 값 조회.

        Args:
            key: 캐시 키
            namespace: 네임스페이스

        Returns:
            값 또는 None (미스)
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return None
            return ns.get(key)

    def set(
        self,
        key: str,
        value: Any,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        ttl_sec: float | None = None,
    ) -> bool:
        """캐시 값 저장.

        Args:
            key: 캐시 키
            value: 캐시 값
            namespace: 네임스페이스
            ttl_sec: TTL (초, None이면 네임스페이스 기본값)

        Returns:
            저장 성공 여부
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return False
            ns.set(key, value, ttl_sec=ttl_sec)
            return True

    def delete(self, key: str, *, namespace: str = DEFAULT_NAMESPACE) -> bool:
        """캐시 항목 삭제.

        Args:
            key: 캐시 키
            namespace: 네임스페이스

        Returns:
            삭제 성공 여부
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return False
            return ns.delete(key)

    def has(self, key: str, *, namespace: str = DEFAULT_NAMESPACE) -> bool:
        """캐시 항목 존재 여부.

        Args:
            key: 캐시 키
            namespace: 네임스페이스

        Returns:
            존재 여부
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return False
            return ns.has(key)

    # =========================================================================
    # 일괄 작업
    # =========================================================================

    def clear(self, *, namespace: str | None = None) -> int:
        """캐시 초기화.

        Args:
            namespace: 특정 네임스페이스 (None이면 전체)

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            if namespace is not None:
                ns = self._namespaces.get(namespace)
                if ns is None:
                    return 0
                return ns.clear()

            total = 0
            for ns in self._namespaces.values():
                total += ns.clear()
            return total

    def cleanup_expired(self, *, namespace: str | None = None) -> int:
        """만료 항목 정리.

        Args:
            namespace: 특정 네임스페이스 (None이면 전체)

        Returns:
            정리된 항목 수
        """
        with self._lock:
            if namespace is not None:
                ns = self._namespaces.get(namespace)
                if ns is None:
                    return 0
                return ns.cleanup_expired()

            total = 0
            for ns in self._namespaces.values():
                total += ns.cleanup_expired()
            return total

    def keys(self, *, namespace: str = DEFAULT_NAMESPACE) -> list[str]:
        """캐시 키 목록.

        Args:
            namespace: 네임스페이스

        Returns:
            키 목록
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return []
            return ns.keys

    # =========================================================================
    # 통계
    # =========================================================================

    def get_stats(self, *, namespace: str | None = None) -> list[CacheStats]:
        """캐시 통계 조회.

        Args:
            namespace: 특정 네임스페이스 (None이면 전체)

        Returns:
            통계 목록
        """
        with self._lock:
            if namespace is not None:
                ns = self._namespaces.get(namespace)
                if ns is None:
                    return []
                return [ns.get_stats()]

            return [ns.get_stats() for ns in self._namespaces.values()]

    def reset_stats(self, *, namespace: str | None = None) -> None:
        """통계 초기화.

        Args:
            namespace: 특정 네임스페이스 (None이면 전체)
        """
        with self._lock:
            if namespace is not None:
                ns = self._namespaces.get(namespace)
                if ns is not None:
                    ns.reset_stats()
                return

            for ns in self._namespaces.values():
                ns.reset_stats()

    @property
    def total_entry_count(self) -> int:
        """전체 항목 수."""
        with self._lock:
            return sum(ns.entry_count for ns in self._namespaces.values())

    def __repr__(self) -> str:
        return (
            f"CacheManager(namespaces={self.namespace_count}, "
            f"total_entries={self.total_entry_count})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터 클래스
    "CacheStats",
    # 핵심 클래스
    "CacheManager",
    # 상수
    "MAX_NAMESPACES",
    "DEFAULT_NAMESPACE",
    "DEFAULT_ENTRY_SIZE_BYTES",
]

__version__ = "1.0.0"
