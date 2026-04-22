# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: dependency_injector.py
설명: 의존성 주입(DI) 컨테이너
      - 타입 기반 의존성 등록/해석
      - Singleton / Transient 라이프사이클
      - 자동 의존성 해석 (팩토리 인자 기반)
      - 스코프 관리 (글로벌, 요청별)
      - 순환 의존 탐지
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
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 바인딩 수
MAX_BINDINGS: Final[int] = 300

# 최대 해석 깊이 (순환 방지)
MAX_RESOLVE_DEPTH: Final[int] = 25

# 최대 스코프 수
MAX_SCOPES: Final[int] = 20


# =============================================================================
# 바인딩 스코프 열거형
# =============================================================================

@unique
class Scope(Enum):
    """의존성 바인딩 스코프.

    Attributes:
        SINGLETON: 전역 단일 인스턴스
        TRANSIENT: 매 해석 시 새 인스턴스
        SCOPED: 스코프 내 단일 인스턴스
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _SCOPE_KOREAN_MAP[self]


_SCOPE_KOREAN_MAP: Final[dict[Scope, str]] = {
    Scope.SINGLETON: "싱글턴",
    Scope.TRANSIENT: "일회성",
    Scope.SCOPED: "스코프",
}


# =============================================================================
# 바인딩 정보
# =============================================================================

@dataclass(slots=True)
class Binding:
    """의존성 바인딩 정보.

    Attributes:
        key: 바인딩 키 (문자열 식별자)
        scope: 라이프사이클 스코프
        factory: 인스턴스 생성 팩토리
        instance: 캐싱된 인스턴스 (Singleton)
        dependencies: 의존 바인딩 키 목록
        description: 설명
    """

    key: str
    scope: Scope
    factory: Callable[..., Any] | None = None
    instance: Any = None
    dependencies: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def is_resolved(self) -> bool:
        """인스턴스 해석 완료 여부."""
        return self.instance is not None

    def __repr__(self) -> str:
        return (
            f"Binding('{self.key}', "
            f"scope={self.scope.value}, "
            f"resolved={self.is_resolved})"
        )


# =============================================================================
# 핵심 클래스: DependencyInjector
# =============================================================================

class DependencyInjector:
    """의존성 주입(DI) 컨테이너.

    타입/이름 기반으로 의존성을 등록하고 해석한다.
    ServiceRegistry와 달리 팩토리의 인자명 기반 자동 해석을 지원한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        di = DependencyInjector.get_instance()

        # 인스턴스 바인딩
        di.bind_instance("config", config_obj)

        # 팩토리 바인딩 (Singleton)
        di.bind_singleton("metrics", create_metrics, dependencies=["config"])

        # 해석
        metrics = di.resolve("metrics")

        # 스코프 생성
        scope = di.create_scope("request_1")
        scope_metrics = di.resolve_in_scope("request_1", "metrics")
    """

    _instance: ClassVar[DependencyInjector | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bindings: dict[str, Binding] = {}
        self._scopes: dict[str, dict[str, Any]] = {}

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> DependencyInjector:
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
    # 바인딩 등록
    # =========================================================================

    def bind_instance(
        self,
        key: str,
        instance: Any,
        *,
        description: str = "",
    ) -> bool:
        """인스턴스 직접 바인딩.

        Args:
            key: 바인딩 키
            instance: 바인딩할 인스턴스
            description: 설명

        Returns:
            바인딩 성공 여부
        """
        return self._bind(
            key=key,
            scope=Scope.SINGLETON,
            factory=None,
            instance=instance,
            dependencies=[],
            description=description,
        )

    def bind_singleton(
        self,
        key: str,
        factory: Callable[..., Any],
        *,
        dependencies: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """Singleton 팩토리 바인딩.

        최초 해석 시 생성, 이후 캐싱.

        Args:
            key: 바인딩 키
            factory: 인스턴스 생성 팩토리
            dependencies: 의존 키 목록
            description: 설명

        Returns:
            바인딩 성공 여부
        """
        return self._bind(
            key=key,
            scope=Scope.SINGLETON,
            factory=factory,
            instance=None,
            dependencies=dependencies or [],
            description=description,
        )

    def bind_transient(
        self,
        key: str,
        factory: Callable[..., Any],
        *,
        dependencies: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """Transient 팩토리 바인딩.

        매 해석 시 새 인스턴스 생성.

        Args:
            key: 바인딩 키
            factory: 인스턴스 생성 팩토리
            dependencies: 의존 키 목록
            description: 설명

        Returns:
            바인딩 성공 여부
        """
        return self._bind(
            key=key,
            scope=Scope.TRANSIENT,
            factory=factory,
            instance=None,
            dependencies=dependencies or [],
            description=description,
        )

    def bind_scoped(
        self,
        key: str,
        factory: Callable[..., Any],
        *,
        dependencies: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """Scoped 팩토리 바인딩.

        스코프 내에서 단일 인스턴스, 스코프 간 별개.

        Args:
            key: 바인딩 키
            factory: 인스턴스 생성 팩토리
            dependencies: 의존 키 목록
            description: 설명

        Returns:
            바인딩 성공 여부
        """
        return self._bind(
            key=key,
            scope=Scope.SCOPED,
            factory=factory,
            instance=None,
            dependencies=dependencies or [],
            description=description,
        )

    def unbind(self, key: str) -> bool:
        """바인딩 해제.

        Args:
            key: 바인딩 키

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if key in self._bindings:
                del self._bindings[key]
                return True
            return False

    # =========================================================================
    # 해석
    # =========================================================================

    def resolve(self, key: str) -> Any:
        """의존성 해석.

        Args:
            key: 바인딩 키

        Returns:
            인스턴스

        Raises:
            KeyError: 미등록 키
            RuntimeError: 순환 의존 또는 팩토리 실패
        """
        with self._lock:
            return self._resolve(key, set())

    def resolve_optional(self, key: str) -> Any | None:
        """의존성 해석 (없으면 None).

        Args:
            key: 바인딩 키

        Returns:
            인스턴스 또는 None
        """
        with self._lock:
            try:
                return self._resolve(key, set())
            except (KeyError, RuntimeError):
                return None

    # =========================================================================
    # 스코프 관리
    # =========================================================================

    def create_scope(self, scope_id: str) -> bool:
        """스코프 생성.

        Args:
            scope_id: 스코프 ID

        Returns:
            생성 성공 여부
        """
        with self._lock:
            if scope_id in self._scopes:
                return False
            if len(self._scopes) >= MAX_SCOPES:
                return False
            self._scopes[scope_id] = {}
            return True

    def destroy_scope(self, scope_id: str) -> bool:
        """스코프 제거.

        Args:
            scope_id: 스코프 ID

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if scope_id in self._scopes:
                del self._scopes[scope_id]
                return True
            return False

    def resolve_in_scope(self, scope_id: str, key: str) -> Any:
        """스코프 내 의존성 해석.

        Scoped 바인딩은 스코프 내 캐싱.
        Singleton 바인딩은 글로벌 캐싱.
        Transient 바인딩은 매번 생성.

        Args:
            scope_id: 스코프 ID
            key: 바인딩 키

        Returns:
            인스턴스

        Raises:
            KeyError: 미등록 키 또는 미등록 스코프
            RuntimeError: 순환 의존 또는 팩토리 실패
        """
        with self._lock:
            if scope_id not in self._scopes:
                raise KeyError(f"미등록 스코프: '{scope_id}'")

            binding = self._bindings.get(key)
            if binding is None:
                raise KeyError(f"미등록 바인딩: '{key}'")

            # Scoped: 스코프 캐시에서 조회
            if binding.scope == Scope.SCOPED:
                scope_cache = self._scopes[scope_id]
                if key in scope_cache:
                    return scope_cache[key]

                # 생성 후 스코프 캐시에 저장
                instance = self._create_instance(binding, set())
                scope_cache[key] = instance
                return instance

            # Singleton / Transient: 일반 해석
            return self._resolve(key, set())

    @property
    def scope_count(self) -> int:
        """활성 스코프 수."""
        with self._lock:
            return len(self._scopes)

    @property
    def scope_ids(self) -> list[str]:
        """활성 스코프 ID 목록."""
        with self._lock:
            return list(self._scopes.keys())

    # =========================================================================
    # 조회
    # =========================================================================

    def has(self, key: str) -> bool:
        """바인딩 존재 여부.

        Args:
            key: 바인딩 키

        Returns:
            존재 여부
        """
        with self._lock:
            return key in self._bindings

    def get_binding(self, key: str) -> Binding | None:
        """바인딩 정보 조회.

        Args:
            key: 바인딩 키

        Returns:
            Binding 또는 None
        """
        with self._lock:
            binding = self._bindings.get(key)
            if binding is None:
                return None
            # 방어적 복사
            return Binding(
                key=binding.key,
                scope=binding.scope,
                factory=binding.factory,
                instance=binding.instance,
                dependencies=list(binding.dependencies),
                description=binding.description,
            )

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def binding_count(self) -> int:
        """등록된 바인딩 수."""
        with self._lock:
            return len(self._bindings)

    @property
    def binding_keys(self) -> list[str]:
        """등록된 바인딩 키 목록."""
        with self._lock:
            return list(self._bindings.keys())

    def clear(self) -> int:
        """전체 바인딩 및 스코프 제거.

        Returns:
            제거된 바인딩 수
        """
        with self._lock:
            count = len(self._bindings)
            self._bindings.clear()
            self._scopes.clear()
            return count

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _bind(
        self,
        key: str,
        scope: Scope,
        factory: Callable[..., Any] | None,
        instance: Any,
        dependencies: list[str],
        description: str,
    ) -> bool:
        """내부 바인딩 처리."""
        with self._lock:
            if (
                key not in self._bindings
                and len(self._bindings) >= MAX_BINDINGS
            ):
                return False

            self._bindings[key] = Binding(
                key=key,
                scope=scope,
                factory=factory,
                instance=instance,
                dependencies=list(dependencies),
                description=description,
            )
            return True

    def _resolve(self, key: str, resolving: set[str]) -> Any:
        """내부 해석 처리.

        Args:
            key: 바인딩 키
            resolving: 현재 해석 중인 키 세트 (순환 탐지)
        """
        binding = self._bindings.get(key)
        if binding is None:
            raise KeyError(f"미등록 바인딩: '{key}'")

        # 순환 의존 감지
        if key in resolving:
            raise RuntimeError(f"순환 의존 감지: '{key}'")

        if len(resolving) >= MAX_RESOLVE_DEPTH:
            raise RuntimeError(
                f"해석 깊이 초과 ({MAX_RESOLVE_DEPTH}): '{key}'"
            )

        # 이미 해석됨 (Singleton 캐시 또는 Instance)
        if binding.instance is not None and binding.scope != Scope.TRANSIENT:
            return binding.instance

        # 인스턴스 생성
        instance = self._create_instance(binding, resolving | {key})

        # Singleton 캐싱
        if binding.scope == Scope.SINGLETON:
            binding.instance = instance

        return instance

    def _create_instance(
        self,
        binding: Binding,
        resolving: set[str],
    ) -> Any:
        """팩토리를 통한 인스턴스 생성.

        Args:
            binding: 바인딩 정보
            resolving: 해석 중 키 세트

        Returns:
            생성된 인스턴스
        """
        if binding.factory is None:
            raise RuntimeError(f"팩토리 미등록: '{binding.key}'")

        # 의존성 해석
        deps: dict[str, Any] = {}
        for dep_key in binding.dependencies:
            deps[dep_key] = self._resolve(dep_key, resolving)

        # 팩토리 호출
        try:
            if deps:
                return binding.factory(**deps)
            return binding.factory()
        except Exception as exc:
            raise RuntimeError(
                f"인스턴스 생성 실패: '{binding.key}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"DependencyInjector("
            f"bindings={self.binding_count}, "
            f"scopes={self.scope_count})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "Scope",
    # 데이터 클래스
    "Binding",
    # 핵심 클래스
    "DependencyInjector",
    # 상수
    "MAX_BINDINGS",
    "MAX_RESOLVE_DEPTH",
    "MAX_SCOPES",
]

__version__ = "1.0.0"
