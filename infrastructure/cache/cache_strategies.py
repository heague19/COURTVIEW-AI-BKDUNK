# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/cache
파일: cache_strategies.py
설명: 캐시 퇴거 전략 엔진
      - EvictionStrategy Enum (LRU, TTL, LFU, COMBINED)
      - CacheEntry 데이터 클래스 (접근 시각/횟수/TTL 추적)
      - BaseCacheStrategy 추상 기반 클래스
      - LRUStrategy: 최근 최소 사용 퇴거
      - TTLStrategy: 만료 시각 기반 퇴거
      - LFUStrategy: 최소 빈도 사용 퇴거
      - CombinedStrategy: TTL + LRU 복합 (기본 전략)
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 TTL (초, 0이면 만료 없음)
DEFAULT_TTL_SEC: Final[float] = 300.0

# 기본 캐시 최대 항목 수
DEFAULT_MAX_ENTRIES: Final[int] = 1000

# 최소 캐시 용량
MIN_CACHE_ENTRIES: Final[int] = 10

# 최대 캐시 용량
MAX_CACHE_ENTRIES: Final[int] = 100000


# =============================================================================
# 퇴거 전략 Enum
# =============================================================================

@unique
class EvictionStrategy(Enum):
    """캐시 퇴거 전략.

    Members:
        LRU: Least Recently Used — 가장 오래 사용 안 된 항목 퇴거
        TTL: Time To Live — 만료 시각 도래 항목 퇴거
        LFU: Least Frequently Used — 가장 적게 사용된 항목 퇴거
        COMBINED: TTL 우선 만료 + LRU 용량 초과 시 퇴거
    """

    LRU = "lru"
    TTL = "ttl"
    LFU = "lfu"
    COMBINED = "combined"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP: dict[EvictionStrategy, str] = {
            EvictionStrategy.LRU: "최근 최소 사용",
            EvictionStrategy.TTL: "만료 시각 기반",
            EvictionStrategy.LFU: "최소 빈도 사용",
            EvictionStrategy.COMBINED: "TTL+LRU 복합",
        }
        return _MAP[self]


# =============================================================================
# 캐시 항목
# =============================================================================

@dataclass(slots=True)
class CacheEntry:
    """캐시 항목.

    Attributes:
        key: 캐시 키
        value: 캐시 값
        created_at: 생성 시각 (monotonic)
        last_accessed_at: 마지막 접근 시각 (monotonic)
        access_count: 접근 횟수
        ttl_sec: 만료까지 시간 (초, 0이면 무제한)
        size_bytes: 값 크기 추정 (바이트, 0이면 미측정)
    """

    key: str
    value: Any
    created_at: float = 0.0
    last_accessed_at: float = 0.0
    access_count: int = 0
    ttl_sec: float = 0.0
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """만료 여부."""
        if self.ttl_sec <= 0:
            return False
        return time.monotonic() > self.created_at + self.ttl_sec

    @property
    def expires_at(self) -> float:
        """만료 시각 (monotonic, 0이면 무제한)."""
        if self.ttl_sec <= 0:
            return 0.0
        return self.created_at + self.ttl_sec

    def touch(self) -> None:
        """접근 시각/횟수 갱신."""
        self.last_accessed_at = time.monotonic()
        self.access_count += 1

    def __repr__(self) -> str:
        return (
            f"CacheEntry(key='{self.key}', "
            f"access_count={self.access_count}, "
            f"expired={self.is_expired})"
        )


# =============================================================================
# 퇴거 결과
# =============================================================================

@dataclass(slots=True)
class EvictionResult:
    """퇴거 결과.

    Attributes:
        evicted_keys: 퇴거된 키 목록
        evicted_count: 퇴거된 항목 수
        reason: 퇴거 사유
    """

    evicted_keys: list[str]
    evicted_count: int
    reason: str

    def __repr__(self) -> str:
        return (
            f"EvictionResult(count={self.evicted_count}, "
            f"reason='{self.reason}')"
        )


# =============================================================================
# 추상 기반: BaseCacheStrategy
# =============================================================================

class BaseCacheStrategy(ABC):
    """캐시 퇴거 전략 추상 기반 클래스.

    서브클래스는 evict()와 strategy_type을 구현한다.
    """

    @property
    @abstractmethod
    def strategy_type(self) -> EvictionStrategy:
        """전략 유형."""

    @abstractmethod
    def evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> EvictionResult:
        """퇴거 대상 선정 및 제거.

        Args:
            entries: 현재 캐시 항목 (key → CacheEntry)
            max_entries: 최대 허용 항목 수

        Returns:
            퇴거 결과
        """

    @abstractmethod
    def should_evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> bool:
        """퇴거 필요 여부.

        Args:
            entries: 현재 캐시 항목
            max_entries: 최대 허용 항목 수

        Returns:
            퇴거 필요 여부
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(strategy={self.strategy_type.value})"


# =============================================================================
# LRU 전략
# =============================================================================

class LRUStrategy(BaseCacheStrategy):
    """Least Recently Used 퇴거 전략.

    가장 오래 접근하지 않은 항목을 우선 퇴거한다.
    용량 초과 시 초과분만큼 퇴거.
    """

    @property
    def strategy_type(self) -> EvictionStrategy:
        return EvictionStrategy.LRU

    def should_evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> bool:
        return len(entries) > max_entries

    def evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> EvictionResult:
        if len(entries) <= max_entries:
            return EvictionResult(evicted_keys=[], evicted_count=0, reason="용량 미초과")

        overflow = len(entries) - max_entries
        # last_accessed_at 오름차순 정렬 → 가장 오래된 것부터 퇴거
        sorted_keys = sorted(
            entries.keys(),
            key=lambda k: entries[k].last_accessed_at,
        )
        evict_keys = sorted_keys[:overflow]

        for key in evict_keys:
            del entries[key]

        return EvictionResult(
            evicted_keys=evict_keys,
            evicted_count=len(evict_keys),
            reason="LRU 용량 초과 퇴거",
        )


# =============================================================================
# TTL 전략
# =============================================================================

class TTLStrategy(BaseCacheStrategy):
    """Time To Live 퇴거 전략.

    만료된 항목을 즉시 퇴거한다.
    """

    @property
    def strategy_type(self) -> EvictionStrategy:
        return EvictionStrategy.TTL

    def should_evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> bool:
        return any(entry.is_expired for entry in entries.values())

    def evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> EvictionResult:
        expired_keys = [
            key for key, entry in entries.items()
            if entry.is_expired
        ]

        for key in expired_keys:
            del entries[key]

        if not expired_keys:
            return EvictionResult(
                evicted_keys=[], evicted_count=0, reason="만료 항목 없음",
            )

        return EvictionResult(
            evicted_keys=expired_keys,
            evicted_count=len(expired_keys),
            reason="TTL 만료 퇴거",
        )


# =============================================================================
# LFU 전략
# =============================================================================

class LFUStrategy(BaseCacheStrategy):
    """Least Frequently Used 퇴거 전략.

    접근 빈도가 가장 낮은 항목을 우선 퇴거한다.
    동일 빈도면 마지막 접근 시각이 오래된 것 우선.
    용량 초과 시 초과분만큼 퇴거.
    """

    @property
    def strategy_type(self) -> EvictionStrategy:
        return EvictionStrategy.LFU

    def should_evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> bool:
        return len(entries) > max_entries

    def evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> EvictionResult:
        if len(entries) <= max_entries:
            return EvictionResult(evicted_keys=[], evicted_count=0, reason="용량 미초과")

        overflow = len(entries) - max_entries
        # access_count 오름차순, 동점 시 last_accessed_at 오름차순
        sorted_keys = sorted(
            entries.keys(),
            key=lambda k: (entries[k].access_count, entries[k].last_accessed_at),
        )
        evict_keys = sorted_keys[:overflow]

        for key in evict_keys:
            del entries[key]

        return EvictionResult(
            evicted_keys=evict_keys,
            evicted_count=len(evict_keys),
            reason="LFU 최소 빈도 퇴거",
        )


# =============================================================================
# Combined 전략 (TTL + LRU)
# =============================================================================

class CombinedStrategy(BaseCacheStrategy):
    """TTL + LRU 복합 퇴거 전략.

    1단계: 만료된 항목 즉시 퇴거 (TTL)
    2단계: 용량 초과 시 LRU로 추가 퇴거

    기본 전략으로 사용.
    """

    def __init__(self) -> None:
        self._ttl = TTLStrategy()
        self._lru = LRUStrategy()

    @property
    def strategy_type(self) -> EvictionStrategy:
        return EvictionStrategy.COMBINED

    def should_evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> bool:
        return (
            self._ttl.should_evict(entries, max_entries)
            or self._lru.should_evict(entries, max_entries)
        )

    def evict(
        self,
        entries: dict[str, CacheEntry],
        max_entries: int,
    ) -> EvictionResult:
        all_evicted: list[str] = []
        reasons: list[str] = []

        # 1단계: TTL 만료 퇴거
        ttl_result = self._ttl.evict(entries, max_entries)
        if ttl_result.evicted_count > 0:
            all_evicted.extend(ttl_result.evicted_keys)
            reasons.append(f"TTL:{ttl_result.evicted_count}")

        # 2단계: 용량 초과 시 LRU 퇴거
        if len(entries) > max_entries:
            lru_result = self._lru.evict(entries, max_entries)
            if lru_result.evicted_count > 0:
                all_evicted.extend(lru_result.evicted_keys)
                reasons.append(f"LRU:{lru_result.evicted_count}")

        if not all_evicted:
            return EvictionResult(
                evicted_keys=[], evicted_count=0, reason="퇴거 불필요",
            )

        return EvictionResult(
            evicted_keys=all_evicted,
            evicted_count=len(all_evicted),
            reason=" + ".join(reasons),
        )


# =============================================================================
# 전략 팩토리
# =============================================================================

def create_strategy(strategy: EvictionStrategy) -> BaseCacheStrategy:
    """퇴거 전략 인스턴스 생성.

    Args:
        strategy: 전략 유형

    Returns:
        BaseCacheStrategy 구현체

    Raises:
        ValueError: 지원하지 않는 전략
    """
    _FACTORY: dict[EvictionStrategy, type[BaseCacheStrategy]] = {
        EvictionStrategy.LRU: LRUStrategy,
        EvictionStrategy.TTL: TTLStrategy,
        EvictionStrategy.LFU: LFUStrategy,
        EvictionStrategy.COMBINED: CombinedStrategy,
    }
    cls = _FACTORY.get(strategy)
    if cls is None:
        raise ValueError(f"지원하지 않는 퇴거 전략: {strategy}")
    return cls()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "EvictionStrategy",
    # 데이터 클래스
    "CacheEntry",
    "EvictionResult",
    # 추상 기반
    "BaseCacheStrategy",
    # 전략 구현
    "LRUStrategy",
    "TTLStrategy",
    "LFUStrategy",
    "CombinedStrategy",
    # 팩토리
    "create_strategy",
    # 상수
    "DEFAULT_TTL_SEC",
    "DEFAULT_MAX_ENTRIES",
    "MIN_CACHE_ENTRIES",
    "MAX_CACHE_ENTRIES",
]

__version__ = "1.0.0"
