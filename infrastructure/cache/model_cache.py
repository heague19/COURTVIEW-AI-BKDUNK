# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/cache
파일: model_cache.py
설명: 모델 추론 결과 캐시
      - 프레임 해시 기반 추론 결과 캐싱 (동일 프레임 재추론 방지)
      - 모델별 네임스페이스 자동 격리
      - VRAM/메모리 사용량 추적
      - 캐시 워밍업 지원
      - 모델별 히트율 통계
      - Singleton + 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from infrastructure.cache.cache_manager import CacheManager, CacheStats
from infrastructure.cache.cache_strategies import (
    DEFAULT_MAX_ENTRIES,
    EvictionStrategy,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 모델 캐시 네임스페이스 접두사
MODEL_CACHE_PREFIX: Final[str] = "model_cache:"

# 모델 캐시 기본 TTL (초, 추론 결과는 프레임 단위로 짧게)
MODEL_CACHE_DEFAULT_TTL_SEC: Final[float] = 60.0

# 모델 캐시 기본 최대 항목 수
MODEL_CACHE_DEFAULT_MAX_ENTRIES: Final[int] = 500

# 최대 등록 가능 모델 수
MAX_CACHED_MODELS: Final[int] = 30

# 프레임 해시 알고리즘
FRAME_HASH_ALGORITHM: Final[str] = "sha256"


# =============================================================================
# 모델 캐시 통계
# =============================================================================

@dataclass(slots=True)
class ModelCacheStats:
    """모델별 캐시 통계.

    Attributes:
        model_name: 모델 이름
        entry_count: 현재 항목 수
        max_entries: 최대 항목 수
        hits: 히트 수
        misses: 미스 수
        hit_rate: 히트율 (0.0 ~ 1.0)
        total_size_bytes: 총 사이즈 추정
        evictions: 퇴거 수
    """

    model_name: str
    entry_count: int
    max_entries: int
    hits: int
    misses: int
    hit_rate: float
    total_size_bytes: int
    evictions: int

    def __repr__(self) -> str:
        return (
            f"ModelCacheStats(model='{self.model_name}', "
            f"entries={self.entry_count}/{self.max_entries}, "
            f"hit_rate={self.hit_rate:.1%})"
        )


# =============================================================================
# 핵심 클래스: ModelCache
# =============================================================================

class ModelCache:
    """모델 추론 결과 캐시.

    각 모델에 대해 프레임 해시 기반 추론 결과를 캐싱한다.
    동일 프레임에 대한 재추론을 방지하여 GPU 자원을 절약한다.

    사용 예시::

        cache = ModelCache.get_instance()

        # 모델 등록
        cache.register_model("yolov8_ball", max_entries=200, ttl_sec=30.0)

        # 추론 결과 캐싱
        frame_hash = cache.compute_frame_hash(frame_bytes)
        cached = cache.get("yolov8_ball", frame_hash)
        if cached is None:
            result = model.inference(frame)
            cache.set("yolov8_ball", frame_hash, result)

        # 통계 확인
        stats = cache.get_model_stats("yolov8_ball")

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: ModelCache | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._cache_manager = CacheManager.get_instance()
        self._registered_models: dict[str, str] = {}  # model_name → namespace
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> ModelCache:
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
    # 모델 등록
    # =========================================================================

    def register_model(
        self,
        model_name: str,
        *,
        max_entries: int = MODEL_CACHE_DEFAULT_MAX_ENTRIES,
        ttl_sec: float = MODEL_CACHE_DEFAULT_TTL_SEC,
        strategy: EvictionStrategy = EvictionStrategy.COMBINED,
    ) -> bool:
        """추론 캐시에 모델 등록.

        Args:
            model_name: 모델 이름
            max_entries: 최대 캐시 항목 수
            ttl_sec: 기본 TTL (초)
            strategy: 퇴거 전략

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if model_name in self._registered_models:
                return False
            if len(self._registered_models) >= MAX_CACHED_MODELS:
                return False

            namespace = f"{MODEL_CACHE_PREFIX}{model_name}"
            success = self._cache_manager.create_namespace(
                namespace,
                strategy=strategy,
                max_entries=max_entries,
                default_ttl=ttl_sec,
            )
            if success:
                self._registered_models[model_name] = namespace
            return success

    def unregister_model(self, model_name: str) -> bool:
        """모델 캐시 해제.

        Args:
            model_name: 모델 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return False

            self._cache_manager.remove_namespace(namespace)
            del self._registered_models[model_name]
            return True

    def is_registered(self, model_name: str) -> bool:
        """모델 등록 여부."""
        with self._lock:
            return model_name in self._registered_models

    @property
    def registered_models(self) -> list[str]:
        """등록된 모델 목록."""
        with self._lock:
            return list(self._registered_models.keys())

    @property
    def model_count(self) -> int:
        """등록된 모델 수."""
        with self._lock:
            return len(self._registered_models)

    # =========================================================================
    # 핵심 API: get / set / has / delete
    # =========================================================================

    def get(self, model_name: str, frame_hash: str) -> Any | None:
        """추론 결과 조회.

        Args:
            model_name: 모델 이름
            frame_hash: 프레임 해시

        Returns:
            추론 결과 또는 None (미스)
        """
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return None
            return self._cache_manager.get(frame_hash, namespace=namespace)

    def set(
        self,
        model_name: str,
        frame_hash: str,
        result: Any,
        *,
        ttl_sec: float | None = None,
    ) -> bool:
        """추론 결과 저장.

        Args:
            model_name: 모델 이름
            frame_hash: 프레임 해시
            result: 추론 결과
            ttl_sec: TTL (초, None이면 모델 기본값)

        Returns:
            저장 성공 여부
        """
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return False
            return self._cache_manager.set(
                frame_hash, result, namespace=namespace, ttl_sec=ttl_sec,
            )

    def has(self, model_name: str, frame_hash: str) -> bool:
        """추론 결과 존재 여부."""
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return False
            return self._cache_manager.has(frame_hash, namespace=namespace)

    def delete(self, model_name: str, frame_hash: str) -> bool:
        """추론 결과 삭제."""
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return False
            return self._cache_manager.delete(frame_hash, namespace=namespace)

    # =========================================================================
    # 일괄 작업
    # =========================================================================

    def clear_model(self, model_name: str) -> int:
        """특정 모델 캐시 초기화.

        Args:
            model_name: 모델 이름

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return 0
            return self._cache_manager.clear(namespace=namespace)

    def clear_all(self) -> int:
        """전체 모델 캐시 초기화.

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            total = 0
            for namespace in self._registered_models.values():
                total += self._cache_manager.clear(namespace=namespace)
            return total

    def cleanup_expired(self, model_name: str | None = None) -> int:
        """만료 항목 정리.

        Args:
            model_name: 특정 모델 (None이면 전체)

        Returns:
            정리된 항목 수
        """
        with self._lock:
            if model_name is not None:
                namespace = self._registered_models.get(model_name)
                if namespace is None:
                    return 0
                return self._cache_manager.cleanup_expired(namespace=namespace)

            total = 0
            for namespace in self._registered_models.values():
                total += self._cache_manager.cleanup_expired(namespace=namespace)
            return total

    # =========================================================================
    # 프레임 해시
    # =========================================================================

    @staticmethod
    def compute_frame_hash(frame_bytes: bytes) -> str:
        """프레임 바이트에서 해시 생성.

        Args:
            frame_bytes: 프레임 원본 바이트

        Returns:
            SHA-256 해시 (hex)
        """
        return hashlib.new(FRAME_HASH_ALGORITHM, frame_bytes).hexdigest()

    @staticmethod
    def compute_composite_hash(
        frame_hash: str,
        *,
        roi: str = "",
        params: str = "",
    ) -> str:
        """복합 해시 생성 (프레임 + ROI + 파라미터).

        동일 프레임이라도 ROI나 모델 파라미터가 다르면
        다른 결과가 나오므로 복합 해시 사용.

        Args:
            frame_hash: 프레임 해시
            roi: ROI 문자열 (예: "x1,y1,x2,y2")
            params: 추가 파라미터 문자열

        Returns:
            SHA-256 복합 해시 (hex)
        """
        payload = f"{frame_hash}|{roi}|{params}"
        return hashlib.new(FRAME_HASH_ALGORITHM, payload.encode("utf-8")).hexdigest()

    # =========================================================================
    # 통계
    # =========================================================================

    def get_model_stats(self, model_name: str) -> ModelCacheStats | None:
        """모델별 캐시 통계.

        Args:
            model_name: 모델 이름

        Returns:
            ModelCacheStats 또는 None
        """
        with self._lock:
            namespace = self._registered_models.get(model_name)
            if namespace is None:
                return None

            stats_list = self._cache_manager.get_stats(namespace=namespace)
            if not stats_list:
                return None

            stats = stats_list[0]
            return ModelCacheStats(
                model_name=model_name,
                entry_count=stats.entry_count,
                max_entries=stats.max_entries,
                hits=stats.hits,
                misses=stats.misses,
                hit_rate=stats.hit_rate,
                total_size_bytes=stats.total_size_bytes,
                evictions=stats.evictions,
            )

    def get_all_stats(self) -> list[ModelCacheStats]:
        """전체 모델 캐시 통계."""
        with self._lock:
            results: list[ModelCacheStats] = []
            for model_name in self._registered_models:
                stats = self.get_model_stats(model_name)
                if stats is not None:
                    results.append(stats)
            return results

    @property
    def total_entry_count(self) -> int:
        """전체 캐시 항목 수."""
        with self._lock:
            total = 0
            for namespace in self._registered_models.values():
                stats_list = self._cache_manager.get_stats(namespace=namespace)
                if stats_list:
                    total += stats_list[0].entry_count
            return total

    def __repr__(self) -> str:
        return (
            f"ModelCache(models={self.model_count}, "
            f"total_entries={self.total_entry_count})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
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
