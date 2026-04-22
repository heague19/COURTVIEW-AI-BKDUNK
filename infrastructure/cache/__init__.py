# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/cache
설명: 캐시 관리 서브모듈
      - cache_strategies: LRU/TTL/LFU/Combined 퇴거 전략
      - cache_manager: 네임스페이스별 캐시 수명주기 관리
      - model_cache: 모델 추론 결과 전용 캐시

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# cache_strategies
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
    LFUStrategy,
    LRUStrategy,
    TTLStrategy,
    create_strategy,
)

# =============================================================================
# cache_manager
# =============================================================================
from infrastructure.cache.cache_manager import (
    DEFAULT_ENTRY_SIZE_BYTES,
    DEFAULT_NAMESPACE,
    MAX_NAMESPACES,
    CacheManager,
    CacheStats,
)

# =============================================================================
# model_cache
# =============================================================================
from infrastructure.cache.model_cache import (
    FRAME_HASH_ALGORITHM,
    MAX_CACHED_MODELS,
    MODEL_CACHE_DEFAULT_MAX_ENTRIES,
    MODEL_CACHE_DEFAULT_TTL_SEC,
    MODEL_CACHE_PREFIX,
    ModelCache,
    ModelCacheStats,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- cache_strategies ---
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
    # --- cache_manager ---
    # 데이터 클래스
    "CacheStats",
    # 핵심 클래스
    "CacheManager",
    # 상수
    "MAX_NAMESPACES",
    "DEFAULT_NAMESPACE",
    "DEFAULT_ENTRY_SIZE_BYTES",
    # --- model_cache ---
    # 데이터 클래스
    "ModelCacheStats",
    # 핵심 클래스
    "ModelCache",
    # 상수
    "MODEL_CACHE_PREFIX",
    "MODEL_CACHE_DEFAULT_TTL_SEC",
    "MODEL_CACHE_DEFAULT_MAX_ENTRIES",
    "MAX_CACHED_MODELS",
    "FRAME_HASH_ALGORITHM",
]

__version__ = "1.0.0"
