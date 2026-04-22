# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: service_registry.py
설명: 서비스 레지스트리
      - 서비스 등록/조회/해제 (이름 기반)
      - 서비스 라이프사이클 관리 (Singleton, Transient, Factory)
      - 의존성 그래프 검증 (순환 의존 탐지)
      - 서비스 상태 조회
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

# 최대 서비스 등록 수
MAX_SERVICES: Final[int] = 200

# 최대 의존성 깊이 (순환 탐지용)
MAX_DEPENDENCY_DEPTH: Final[int] = 20

# 최대 태그 수 (서비스당)
MAX_TAGS_PER_SERVICE: Final[int] = 10


# =============================================================================
# 서비스 라이프사이클 열거형
# =============================================================================

@unique
class ServiceLifecycle(Enum):
    """서비스 라이프사이클 타입.

    Attributes:
        SINGLETON: 단일 인스턴스 (최초 조회 시 생성, 이후 캐싱)
        TRANSIENT: 매 조회 시 새 인스턴스 생성
        INSTANCE: 미리 생성된 인스턴스 직접 등록
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    INSTANCE = "instance"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _LIFECYCLE_KOREAN_MAP[self]


_LIFECYCLE_KOREAN_MAP: Final[dict[ServiceLifecycle, str]] = {
    ServiceLifecycle.SINGLETON: "싱글턴",
    ServiceLifecycle.TRANSIENT: "일회성",
    ServiceLifecycle.INSTANCE: "인스턴스",
}


# =============================================================================
# 서비스 등록 정보 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ServiceDescriptor:
    """서비스 등록 정보.

    Attributes:
        name: 서비스 이름
        lifecycle: 라이프사이클 타입
        factory: 인스턴스 생성 팩토리 (SINGLETON, TRANSIENT)
        instance: 등록된 인스턴스 (INSTANCE, 또는 SINGLETON 캐시)
        dependencies: 의존하는 서비스 이름 목록
        tags: 서비스 분류 태그
        description: 서비스 설명
    """

    name: str
    lifecycle: ServiceLifecycle
    factory: Callable[..., Any] | None = None
    instance: Any = None
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def is_resolved(self) -> bool:
        """인스턴스가 이미 생성되었는지 여부."""
        return self.instance is not None

    def __repr__(self) -> str:
        return (
            f"ServiceDescriptor("
            f"'{self.name}', "
            f"lifecycle={self.lifecycle.value}, "
            f"resolved={self.is_resolved})"
        )


# =============================================================================
# 핵심 클래스: ServiceRegistry
# =============================================================================

class ServiceRegistry:
    """서비스 레지스트리.

    서비스를 이름으로 등록하고 조회한다.
    라이프사이클(Singleton/Transient/Instance)에 따라
    인스턴스 생성 전략이 결정된다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        registry = ServiceRegistry.get_instance()

        # 인스턴스 직접 등록
        registry.register_instance("config", config_obj)

        # 팩토리(Singleton) 등록
        registry.register_singleton("metrics", MetricsCollector)

        # 조회
        config = registry.resolve("config")
        metrics = registry.resolve("metrics")

        # 태그로 조회
        analyzers = registry.resolve_by_tag("analyzer")
    """

    _instance: ClassVar[ServiceRegistry | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: dict[str, ServiceDescriptor] = {}

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> ServiceRegistry:
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
    # 서비스 등록
    # =========================================================================

    def register_instance(
        self,
        name: str,
        instance: Any,
        *,
        tags: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """인스턴스 직접 등록.

        Args:
            name: 서비스 이름
            instance: 등록할 인스턴스
            tags: 분류 태그
            description: 설명

        Returns:
            등록 성공 여부
        """
        return self._register(
            name=name,
            lifecycle=ServiceLifecycle.INSTANCE,
            factory=None,
            instance=instance,
            dependencies=[],
            tags=tags,
            description=description,
        )

    def register_singleton(
        self,
        name: str,
        factory: Callable[..., Any],
        *,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """Singleton 서비스 등록 (지연 생성).

        Args:
            name: 서비스 이름
            factory: 인스턴스 생성 팩토리
            dependencies: 의존 서비스 이름 목록
            tags: 분류 태그
            description: 설명

        Returns:
            등록 성공 여부
        """
        return self._register(
            name=name,
            lifecycle=ServiceLifecycle.SINGLETON,
            factory=factory,
            instance=None,
            dependencies=dependencies or [],
            tags=tags,
            description=description,
        )

    def register_transient(
        self,
        name: str,
        factory: Callable[..., Any],
        *,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        description: str = "",
    ) -> bool:
        """Transient 서비스 등록 (매번 새 인스턴스).

        Args:
            name: 서비스 이름
            factory: 인스턴스 생성 팩토리
            dependencies: 의존 서비스 이름 목록
            tags: 분류 태그
            description: 설명

        Returns:
            등록 성공 여부
        """
        return self._register(
            name=name,
            lifecycle=ServiceLifecycle.TRANSIENT,
            factory=factory,
            instance=None,
            dependencies=dependencies or [],
            tags=tags,
            description=description,
        )

    def unregister(self, name: str) -> bool:
        """서비스 등록 해제.

        Args:
            name: 서비스 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if name in self._services:
                del self._services[name]
                return True
            return False

    # =========================================================================
    # 서비스 조회
    # =========================================================================

    def resolve(self, name: str) -> Any:
        """서비스 인스턴스 조회.

        라이프사이클에 따라:
        - INSTANCE: 등록된 인스턴스 반환
        - SINGLETON: 최초 호출 시 생성 후 캐싱
        - TRANSIENT: 매번 새 인스턴스 생성

        Args:
            name: 서비스 이름

        Returns:
            서비스 인스턴스

        Raises:
            KeyError: 미등록 서비스
            RuntimeError: 순환 의존 또는 팩토리 실패
        """
        with self._lock:
            descriptor = self._services.get(name)
            if descriptor is None:
                raise KeyError(f"미등록 서비스: '{name}'")

            return self._resolve_descriptor(descriptor, set())

    def resolve_optional(self, name: str) -> Any | None:
        """서비스 인스턴스 조회 (없으면 None).

        Args:
            name: 서비스 이름

        Returns:
            서비스 인스턴스 또는 None
        """
        with self._lock:
            descriptor = self._services.get(name)
            if descriptor is None:
                return None

            try:
                return self._resolve_descriptor(descriptor, set())
            except (RuntimeError, KeyError):
                return None

    def resolve_by_tag(self, tag: str) -> list[Any]:
        """태그로 서비스 목록 조회.

        Args:
            tag: 검색 태그

        Returns:
            해당 태그의 서비스 인스턴스 목록
        """
        with self._lock:
            results: list[Any] = []
            for descriptor in self._services.values():
                if tag in descriptor.tags:
                    try:
                        instance = self._resolve_descriptor(descriptor, set())
                        results.append(instance)
                    except (RuntimeError, KeyError):
                        pass
            return results

    def has(self, name: str) -> bool:
        """서비스 등록 여부 확인.

        Args:
            name: 서비스 이름

        Returns:
            등록 여부
        """
        with self._lock:
            return name in self._services

    def get_descriptor(self, name: str) -> ServiceDescriptor | None:
        """서비스 등록 정보 조회.

        Args:
            name: 서비스 이름

        Returns:
            ServiceDescriptor 또는 None
        """
        with self._lock:
            descriptor = self._services.get(name)
            if descriptor is None:
                return None
            # 방어적 복사 (dependencies, tags)
            return ServiceDescriptor(
                name=descriptor.name,
                lifecycle=descriptor.lifecycle,
                factory=descriptor.factory,
                instance=descriptor.instance,
                dependencies=list(descriptor.dependencies),
                tags=list(descriptor.tags),
                description=descriptor.description,
            )

    # =========================================================================
    # 의존성 검증
    # =========================================================================

    def validate_dependencies(self) -> list[str]:
        """전체 서비스 의존성 검증.

        Returns:
            에러 메시지 목록 (빈 리스트 = 정상)
        """
        with self._lock:
            errors: list[str] = []

            for name, descriptor in self._services.items():
                # 미등록 의존성 검증
                for dep in descriptor.dependencies:
                    if dep not in self._services:
                        errors.append(
                            f"'{name}' → 미등록 의존성: '{dep}'"
                        )

                # 순환 의존 검증
                cycle = self._detect_cycle(name, set(), [])
                if cycle:
                    path = " → ".join(cycle)
                    errors.append(f"순환 의존: {path}")

            return errors

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def service_count(self) -> int:
        """등록된 서비스 수."""
        with self._lock:
            return len(self._services)

    @property
    def service_names(self) -> list[str]:
        """등록된 서비스 이름 목록."""
        with self._lock:
            return list(self._services.keys())

    def clear(self) -> int:
        """전체 서비스 제거.

        Returns:
            제거된 서비스 수
        """
        with self._lock:
            count = len(self._services)
            self._services.clear()
            return count

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _register(
        self,
        name: str,
        lifecycle: ServiceLifecycle,
        factory: Callable[..., Any] | None,
        instance: Any,
        dependencies: list[str],
        tags: list[str] | None,
        description: str,
    ) -> bool:
        """내부 등록 처리."""
        safe_tags = (tags or [])[:MAX_TAGS_PER_SERVICE]

        with self._lock:
            # 동일 이름 재등록 허용 (덮어쓰기)
            if (
                name not in self._services
                and len(self._services) >= MAX_SERVICES
            ):
                return False

            self._services[name] = ServiceDescriptor(
                name=name,
                lifecycle=lifecycle,
                factory=factory,
                instance=instance,
                dependencies=list(dependencies),
                tags=list(safe_tags),
                description=description,
            )
            return True

    def _resolve_descriptor(
        self,
        descriptor: ServiceDescriptor,
        resolving: set[str],
    ) -> Any:
        """디스크립터에서 인스턴스 해석.

        Args:
            descriptor: 서비스 등록 정보
            resolving: 현재 해석 중인 서비스 (순환 탐지)

        Returns:
            서비스 인스턴스

        Raises:
            RuntimeError: 순환 의존 또는 팩토리 실패
        """
        # 순환 의존 감지
        if descriptor.name in resolving:
            raise RuntimeError(
                f"순환 의존 감지: '{descriptor.name}'"
            )

        if len(resolving) >= MAX_DEPENDENCY_DEPTH:
            raise RuntimeError(
                f"의존성 깊이 초과 ({MAX_DEPENDENCY_DEPTH}): "
                f"'{descriptor.name}'"
            )

        # INSTANCE: 바로 반환
        if descriptor.lifecycle == ServiceLifecycle.INSTANCE:
            return descriptor.instance

        # SINGLETON: 캐시된 인스턴스 반환
        if (
            descriptor.lifecycle == ServiceLifecycle.SINGLETON
            and descriptor.instance is not None
        ):
            return descriptor.instance

        # 팩토리 실행
        if descriptor.factory is None:
            raise RuntimeError(
                f"팩토리 미등록: '{descriptor.name}'"
            )

        resolving_copy = resolving | {descriptor.name}

        # 의존성 먼저 해석
        deps: dict[str, Any] = {}
        for dep_name in descriptor.dependencies:
            dep_descriptor = self._services.get(dep_name)
            if dep_descriptor is None:
                raise KeyError(
                    f"미등록 의존성: '{dep_name}' "
                    f"(서비스 '{descriptor.name}'에서 필요)"
                )
            deps[dep_name] = self._resolve_descriptor(
                dep_descriptor, resolving_copy,
            )

        # 팩토리 호출
        try:
            if deps:
                instance = descriptor.factory(**deps)
            else:
                instance = descriptor.factory()
        except Exception as exc:
            raise RuntimeError(
                f"서비스 생성 실패: '{descriptor.name}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # SINGLETON: 캐싱
        if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
            descriptor.instance = instance

        return instance

    def _detect_cycle(
        self,
        name: str,
        visited: set[str],
        path: list[str],
    ) -> list[str] | None:
        """DFS 순환 의존 탐지.

        Returns:
            순환 경로 (없으면 None)
        """
        if name in visited:
            cycle_start = path.index(name) if name in path else 0
            return path[cycle_start:] + [name]

        descriptor = self._services.get(name)
        if descriptor is None:
            return None

        visited_copy = visited | {name}
        path_copy = path + [name]

        for dep in descriptor.dependencies:
            cycle = self._detect_cycle(dep, visited_copy, path_copy)
            if cycle is not None:
                return cycle

        return None

    def __repr__(self) -> str:
        return f"ServiceRegistry(services={self.service_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ServiceLifecycle",
    # 데이터 클래스
    "ServiceDescriptor",
    # 핵심 클래스
    "ServiceRegistry",
    # 상수
    "MAX_SERVICES",
    "MAX_DEPENDENCY_DEPTH",
    "MAX_TAGS_PER_SERVICE",
]

__version__ = "1.0.0"
