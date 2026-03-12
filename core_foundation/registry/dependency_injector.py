# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: dependency_injector.py
버전: 1.0.0
설명: DI 컨테이너, 의존성 주입 관리 - 엔터프라이즈급 의존성 주입 시스템

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-12

주요 기능:
    - 서비스 등록 및 해결 (Singleton, Transient, Scoped)
    - 자동 의존성 해결 (생성자 주입)
    - 라이프사이클 훅 (OnCreate, OnDestroy)
    - 순환 의존성 탐지
    - 스레드 안전 동시성 지원
    - 스코프 관리 (Request Scope 등)

=============================================================================
DI 초기화 순서 가이드 (Desktop Edition)
=============================================================================

COURTVIEW Desktop Edition의 DI 초기화는 순환 참조를 방지하기 위해
아래 순서를 반드시 준수해야 합니다.

Phase 1: Core Foundation (Layer 0) - 기반 서비스
    1. ConfigLoader (core_foundation/config)
    2. MetricsCollector (core_foundation/monitoring)
    3. ErrorTracker (core_foundation/monitoring)
    4. HealthChecker (core_foundation/monitoring)
    5. LogManager (core_foundation/monitoring)

Phase 2: Registry (Layer 0) - 레지스트리
    6. ModelRegistry (core_foundation/registry)
    7. ServiceRegistry (core_foundation/registry)
    8. PipelineCoordinator (core_foundation/registry)
    9. RuleSetManager (core_foundation/registry)

Phase 3: Infrastructure (Layer 0.5) - 인프라
    10. CacheManager (infrastructure/cache)
    11. EventBus (infrastructure/events)
    12. LocalStorage (infrastructure/storage)

Phase 4: Motion Analysis (Layer 4) - 동작 분석
    13. ShootingFormEvaluator (motion_analysis)
    14. DribblingFormEvaluator (motion_analysis)

Phase 5: Calibration (Layer 8) - 캘리브레이션 (순환 참조 주의)
    ⚠️ AgeGenderCalibrator → ThresholdAdjuster 순서 필수
    15. AgeGenderCalibrator  ← ThresholdAdjuster를 주입받지 않음
    16. ThresholdAdjuster    ← AgeGenderCalibrator를 DI로 주입
    17. AccuracyMonitor
    18. DriftDetector        ← AccuracyMonitor 필요
    19. ModelEvaluator       ← AccuracyMonitor, ValidationSplitter 필요

Phase 6: Self Learning (Layer 8) - 셀프 러닝
    20. PatternLearner
    21. FeedbackCollector
    22. ValidationSplitter
    23. UserProfileLearner   ← AgeGenderCalibrator, PatternLearner 필요
    24. ModelAdapter         ← PatternLearner, ThresholdAdjuster 필요

Phase 7: Adaptive Learning (Layer 8) - 적응형 학습
    25. CheckpointManager
    26. PerformanceTracker   ← AccuracyMonitor, DriftDetector 필요
    27. IncrementalTrainer   ← ModelEvaluator, ValidationSplitter, PerformanceTracker 필요
    28. UserFeedbackIntegrator ← FeedbackCollector, PatternLearner 필요
    29. LearningScheduler    ← PatternLearner, FeedbackCollector, IncrementalTrainer, CheckpointManager 필요

초기화 순서 검증 방법:
    >>> container = get_container()
    >>> graph = container.build_dependency_graph(LearningScheduler)
    >>> cycles = graph.detect_cycles()
    >>> if cycles:
    ...     raise CircularDependencyError(cycles)
    >>> order = graph.get_resolution_order()
    >>> print("초기화 순서:", [t.__name__ for t in order])
=============================================================================
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import inspect
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Iterator, TypeVar, get_type_hints

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.infrastructure_exceptions import InfrastructureException

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 공개 API 정의
# ============================================================
__all__ = [
    # Enum
    "Scope",
    "LifecycleHook",
    "ResolutionStatus",
    # 상수
    "DEFAULT_MAX_RESOLUTION_DEPTH",
    "DEFAULT_SCOPE_NAME",
    # 예외 클래스
    "DIException",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "ResolutionError",
    # 데이터 클래스
    "ServiceDescriptor",
    "DependencyNode",
    "DependencyGraph",
    "ScopeContext",
    # 메인 클래스
    "ServiceProvider",
    "ContainerBuilder",
    "DIContainer",
    # 데코레이터
    "injectable",
    "inject",
    "is_injectable",
    "get_injectable_metadata",
    # 전역 함수
    "get_container",
    "configure_container",
    # 내부 함수 (테스트용)
    "_reset_container",
]


# ============================================================
# 타입 변수
# ============================================================
T = TypeVar("T")
ServiceT = TypeVar("ServiceT")


# ============================================================
# 유틸리티 함수
# ============================================================
def _unwrap_optional(param_type: Any) -> tuple[Any, bool]:
    """
    Optional 타입 언래핑.

    Optional[T] 또는 Union[T, None] 형태의 타입에서 T를 추출합니다.

    Args:
        param_type: 검사할 타입

    Returns:
        (언래핑된 타입, Optional 여부) 튜플
    """
    import types
    origin = getattr(param_type, "__origin__", None)
    # Python 3.10+ 의 X | Y 형태 (types.UnionType) 및 typing.Union 모두 처리
    if origin is getattr(types, "UnionType", None) or str(origin) == "typing.Union":
        args = getattr(param_type, "__args__", ())
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0], True
    return param_type, False


# ============================================================
# 상수 (YAML 설정 키 및 기본값)
# ============================================================
# YAML 설정 키 (registry.yaml의 dependency_injection 섹션)
CONFIG_KEY_DI: str = "dependency_injection"
CONFIG_KEY_SCOPES: str = "scopes"
CONFIG_KEY_DEFAULT_SCOPE: str = "default_scope"
CONFIG_KEY_AUTO_WIRING: str = "auto_wiring"
CONFIG_KEY_LIFECYCLE_HOOKS: str = "lifecycle_hooks"
CONFIG_KEY_CIRCULAR_DEPENDENCY: str = "circular_dependency"
CONFIG_KEY_THREAD_SAFETY: str = "thread_safety"

# 기본값 (YAML에서 오버라이드 가능)
DEFAULT_MAX_RESOLUTION_DEPTH: int = 50  # 최대 의존성 해결 깊이
DEFAULT_SCOPE_NAME: str = "default"  # 기본 스코프 이름
DEFAULT_LOCK_TIMEOUT: int = 10  # 락 타임아웃 (초)


# ============================================================
# Enum 정의
# ============================================================
class Scope(str, Enum):
    """
    서비스 스코프.

    서비스 인스턴스의 생명주기를 정의합니다.
    """

    SINGLETON = "singleton"  # 애플리케이션 전체에서 단일 인스턴스
    TRANSIENT = "transient"  # 매번 새 인스턴스 생성
    SCOPED = "scoped"  # 스코프 내에서 단일 인스턴스 (예: 요청 스코프)

    @property
    def is_cached(self) -> bool:
        """인스턴스 캐싱 여부."""
        return self in {Scope.SINGLETON, Scope.SCOPED}


class LifecycleHook(str, Enum):
    """
    라이프사이클 훅.

    서비스 생명주기 이벤트를 정의합니다.
    """

    ON_CREATE = "on_create"  # 인스턴스 생성 후
    ON_DESTROY = "on_destroy"  # 인스턴스 파괴 전
    ON_ACTIVATE = "on_activate"  # 서비스 활성화
    ON_DEACTIVATE = "on_deactivate"  # 서비스 비활성화


class ResolutionStatus(str, Enum):
    """
    의존성 해결 상태.

    의존성 해결 과정의 상태를 정의합니다.
    """

    PENDING = "pending"  # 해결 대기
    RESOLVING = "resolving"  # 해결 중
    RESOLVED = "resolved"  # 해결 완료
    FAILED = "failed"  # 해결 실패


# ============================================================
# 예외 클래스
# ============================================================
class DIException(InfrastructureException):
    """DI 관련 예외 기본 클래스."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, error_code=error_code, **kwargs)


class ServiceNotFoundError(DIException):
    """서비스를 찾을 수 없을 때 발생."""

    def __init__(self, service_type: type, **kwargs: Any) -> None:
        super().__init__(
            f"서비스를 찾을 수 없습니다: {service_type.__name__}",
            error_code=ErrorCode.MISSING_DEPENDENCY,
            **kwargs,
        )
        self.service_type = service_type


class CircularDependencyError(DIException):
    """순환 의존성 발견 시 발생."""

    def __init__(self, chain: list[type], **kwargs: Any) -> None:
        chain_str = " -> ".join(t.__name__ for t in chain)
        super().__init__(
            f"순환 의존성 발견: {chain_str}",
            error_code=ErrorCode.CIRCULAR_DEPENDENCY,
            **kwargs,
        )
        self.chain = chain


class ResolutionError(DIException):
    """의존성 해결 실패 시 발생."""

    def __init__(self, service_type: type, reason: str, **kwargs: Any) -> None:
        super().__init__(
            f"서비스 해결 실패 ({service_type.__name__}): {reason}",
            error_code=ErrorCode.INTERNAL_ERROR,
            **kwargs,
        )
        self.service_type = service_type
        self.reason = reason


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class ServiceDescriptor(Generic[T]):
    """
    서비스 설명자.

    등록된 서비스의 메타데이터와 설정을 포함합니다.
    """

    # 서비스 식별
    service_type: type[T]
    implementation_type: type[T] | None = None

    # 생성 방식
    factory: Callable[..., T] | None = None
    instance: T | None = None

    # 스코프 및 라이프사이클
    scope: Scope = Scope.SINGLETON

    # 라이프사이클 훅
    on_create: Callable[[T], None] | None = None
    on_destroy: Callable[[T], None] | None = None

    # 메타데이터
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 의존성 오버라이드
    dependencies: dict[str, type] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if self.implementation_type is None and self.factory is None and self.instance is None:
            # 인터페이스와 구현이 동일한 경우
            self.implementation_type = self.service_type

    @property
    def is_instance_provided(self) -> bool:
        """인스턴스 직접 제공 여부."""
        return self.instance is not None

    @property
    def is_factory_provided(self) -> bool:
        """팩토리 제공 여부."""
        return self.factory is not None

    def get_implementation(self) -> type[T]:
        """구현 타입 가져오기."""
        return self.implementation_type or self.service_type

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "service_type": self.service_type.__name__,
            "implementation_type": (
                self.implementation_type.__name__
                if self.implementation_type
                else None
            ),
            "scope": self.scope.value,
            "has_factory": self.factory is not None,
            "has_instance": self.instance is not None,
            "name": self.name,
            "tags": self.tags,
        }


@dataclass(slots=True)
class DependencyNode:
    """
    의존성 그래프 노드.

    의존성 그래프의 각 노드를 표현합니다.
    """

    service_type: type
    dependencies: list[type] = field(default_factory=list)
    depth: int = 0
    status: ResolutionStatus = ResolutionStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "service_type": self.service_type.__name__,
            "dependencies": [d.__name__ for d in self.dependencies],
            "depth": self.depth,
            "status": self.status.value,
        }


@dataclass(slots=True)
class DependencyGraph:
    """
    의존성 그래프.

    전체 의존성 관계를 표현하는 그래프입니다.
    """

    nodes: dict[type, DependencyNode] = field(default_factory=dict)
    root: type | None = None

    def add_node(
        self,
        service_type: type,
        dependencies: list[type] | None = None,
        depth: int = 0,
    ) -> DependencyNode:
        """노드 추가."""
        if service_type not in self.nodes:
            node = DependencyNode(
                service_type=service_type,
                dependencies=dependencies or [],
                depth=depth,
            )
            self.nodes[service_type] = node
        else:
            node = self.nodes[service_type]
            if dependencies:
                node.dependencies = dependencies
            node.depth = max(node.depth, depth)
        return node

    def get_node(self, service_type: type) -> DependencyNode | None:
        """노드 조회."""
        return self.nodes.get(service_type)

    def get_resolution_order(self) -> list[type]:
        """해결 순서 (위상 정렬)."""
        visited: set[type] = set()
        order: list[type] = []

        def visit(service_type: type) -> None:
            if service_type in visited:
                return
            visited.add(service_type)

            node = self.nodes.get(service_type)
            if node:
                for dep in node.dependencies:
                    visit(dep)

            order.append(service_type)

        for service_type in self.nodes:
            visit(service_type)

        return order

    def detect_cycles(self) -> list[type] | None:
        """순환 의존성 탐지."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[type, int] = {t: WHITE for t in self.nodes}
        parent: dict[type, type | None] = {t: None for t in self.nodes}

        def dfs(node_type: type, path: list[type]) -> list[type] | None:
            color[node_type] = GRAY
            path.append(node_type)

            node = self.nodes.get(node_type)
            if node:
                for dep in node.dependencies:
                    if dep not in color:
                        continue

                    if color[dep] == GRAY:
                        # 순환 발견
                        cycle_start = path.index(dep)
                        return path[cycle_start:] + [dep]

                    if color[dep] == WHITE:
                        parent[dep] = node_type
                        result = dfs(dep, path)
                        if result:
                            return result

            color[node_type] = BLACK
            path.pop()
            return None

        for service_type in self.nodes:
            if color[service_type] == WHITE:
                result = dfs(service_type, [])
                if result:
                    return result

        return None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "nodes": {
                t.__name__: n.to_dict() for t, n in self.nodes.items()
            },
            "root": self.root.__name__ if self.root else None,
            "resolution_order": [t.__name__ for t in self.get_resolution_order()],
        }


@dataclass(slots=True)
class ScopeContext:
    """
    스코프 컨텍스트.

    스코프 내에서 생성된 인스턴스를 관리합니다.
    """

    name: str
    instances: dict[type, Any] = field(default_factory=dict)
    parent: ScopeContext | None = None
    children: list[ScopeContext] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def get(self, service_type: type[T]) -> T | None:
        """스코프 내 인스턴스 조회."""
        with self._lock:
            if service_type in self.instances:
                return self.instances[service_type]
            if self.parent:
                return self.parent.get(service_type)
            return None

    def set(self, service_type: type[T], instance: T) -> None:
        """스코프 내 인스턴스 저장."""
        with self._lock:
            self.instances[service_type] = instance

    def clear(self) -> None:
        """스코프 정리."""
        with self._lock:
            self.instances.clear()
            for child in self.children:
                child.clear()
            self.children.clear()


# ============================================================
# 서비스 프로바이더
# ============================================================
class ServiceProvider:
    """
    서비스 프로바이더.

    등록된 서비스를 해결하고 인스턴스를 제공합니다.
    """

    def __init__(
        self,
        descriptors: dict[type, ServiceDescriptor],
        singletons: dict[type, Any],
        root_scope: ScopeContext,
    ) -> None:
        """초기화."""
        self._descriptors = descriptors
        self._singletons = singletons
        self._root_scope = root_scope
        self._current_scope: ScopeContext | None = None
        self._lock = threading.RLock()
        # 스레드별 독립 해결 스택 (threading.local 기반)
        self._local = threading.local()

    @property
    def _resolution_stack(self) -> list[type]:
        """스레드별 독립적인 의존성 해결 스택 반환."""
        if not hasattr(self._local, "stack"):
            self._local.stack = []
        return self._local.stack

    def get(self, service_type: type[T]) -> T:
        """
        서비스 인스턴스 조회.

        Args:
            service_type: 서비스 타입

        Returns:
            서비스 인스턴스

        Raises:
            ServiceNotFoundError: 서비스를 찾을 수 없을 때
            CircularDependencyError: 순환 의존성 발견 시
        """
        return self._resolve(service_type)

    def get_optional(self, service_type: type[T]) -> T | None:
        """
        서비스 인스턴스 조회 (Optional).

        등록되지 않은 서비스는 None 반환.
        """
        try:
            return self._resolve(service_type)
        except ServiceNotFoundError:
            return None

    def get_all(self, service_type: type[T]) -> list[T]:
        """
        특정 타입의 모든 서비스 인스턴스 조회.

        태그나 기타 조건으로 필터링된 서비스 목록 반환.
        """
        instances = []
        for desc_type, descriptor in self._descriptors.items():
            if issubclass(desc_type, service_type) or desc_type == service_type:
                try:
                    instance = self._resolve(desc_type)
                    instances.append(instance)
                except Exception as e:
                    logger.warning(
                        f"서비스 해석 실패 [{desc_type.__name__}]: {e}"
                    )
        return instances

    def _resolve(
        self,
        service_type: type[T],
        depth: int = 0,
    ) -> T:
        """내부 의존성 해결."""
        if depth > DEFAULT_MAX_RESOLUTION_DEPTH:
            raise ResolutionError(
                service_type,
                f"최대 해결 깊이 초과 ({DEFAULT_MAX_RESOLUTION_DEPTH})",
            )

        # 순환 의존성 체크
        if service_type in self._resolution_stack:
            raise CircularDependencyError(
                self._resolution_stack + [service_type]
            )

        descriptor = self._descriptors.get(service_type)
        if not descriptor:
            raise ServiceNotFoundError(service_type)

        # 싱글톤 캐시 확인
        if descriptor.scope == Scope.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

        # 스코프 캐시 확인
        if descriptor.scope == Scope.SCOPED:
            scope = self._current_scope or self._root_scope
            cached = scope.get(service_type)
            if cached is not None:
                return cached

        # 인스턴스 직접 제공
        if descriptor.is_instance_provided:
            return descriptor.instance

        try:
            self._resolution_stack.append(service_type)

            # 인스턴스 생성
            if descriptor.is_factory_provided:
                instance = self._create_from_factory(descriptor, depth)
            else:
                instance = self._create_from_type(descriptor, depth)

            # 라이프사이클 훅 호출
            if descriptor.on_create:
                descriptor.on_create(instance)

            # 캐싱
            if descriptor.scope == Scope.SINGLETON:
                with self._lock:
                    self._singletons[service_type] = instance

            elif descriptor.scope == Scope.SCOPED:
                scope = self._current_scope or self._root_scope
                scope.set(service_type, instance)

            return instance

        finally:
            self._resolution_stack.pop()

    def _create_from_factory(
        self,
        descriptor: ServiceDescriptor[T],
        depth: int,
    ) -> T:
        """팩토리로 인스턴스 생성."""
        factory = descriptor.factory
        if factory is None:
            raise ResolutionError(
                descriptor.service_type,
                "팩토리가 None입니다",
            )

        # 팩토리 파라미터 분석 및 주입
        sig = inspect.signature(factory)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param.annotation == inspect.Parameter.empty:
                continue

            # 의존성 오버라이드 확인
            param_type = descriptor.dependencies.get(param_name, param.annotation)

            # 기본값이 있으면 Optional
            if param.default != inspect.Parameter.empty:
                try:
                    kwargs[param_name] = self._resolve(param_type, depth + 1)
                except ServiceNotFoundError:
                    kwargs[param_name] = param.default
            else:
                kwargs[param_name] = self._resolve(param_type, depth + 1)

        return factory(**kwargs)

    def _create_from_type(
        self,
        descriptor: ServiceDescriptor[T],
        depth: int,
    ) -> T:
        """타입에서 인스턴스 생성."""
        impl_type = descriptor.get_implementation()

        # 생성자 파라미터 분석
        try:
            hints = get_type_hints(impl_type.__init__)
        except Exception:
            hints = {}

        sig = inspect.signature(impl_type.__init__)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # 타입 힌트 가져오기
            param_type = hints.get(param_name, param.annotation)
            if param_type == inspect.Parameter.empty:
                continue

            # 의존성 오버라이드 확인
            param_type = descriptor.dependencies.get(param_name, param_type)

            # Optional 타입 언래핑
            unwrapped_type, is_optional = _unwrap_optional(param_type)

            # Optional 또는 기본값 처리
            if param.default != inspect.Parameter.empty or is_optional:
                try:
                    kwargs[param_name] = self._resolve(unwrapped_type, depth + 1)
                except ServiceNotFoundError:
                    # Optional이거나 기본값이 있으면 기본값 사용
                    if param.default != inspect.Parameter.empty:
                        kwargs[param_name] = param.default
                    else:
                        kwargs[param_name] = None
            else:
                try:
                    kwargs[param_name] = self._resolve(unwrapped_type, depth + 1)
                except ServiceNotFoundError:
                    # 등록되지 않은 필수 의존성
                    type_name = getattr(unwrapped_type, "__name__", str(unwrapped_type))
                    raise ResolutionError(
                        descriptor.service_type,
                        f"필수 의존성 '{param_name}' ({type_name})을 해결할 수 없습니다",
                    )

        return impl_type(**kwargs)

    @contextmanager
    def create_scope(self, name: str = "request") -> Iterator["ServiceProvider"]:
        """
        새 스코프 생성.

        Args:
            name: 스코프 이름

        Yields:
            스코프 컨텍스트를 가진 ServiceProvider
        """
        parent_scope = self._current_scope or self._root_scope
        scope = ScopeContext(name=name, parent=parent_scope)
        parent_scope.children.append(scope)

        old_scope = self._current_scope
        self._current_scope = scope

        try:
            yield self
        finally:
            self._current_scope = old_scope
            scope.clear()
            parent_scope.children.remove(scope)


# ============================================================
# DI 컨테이너 빌더
# ============================================================
class ContainerBuilder:
    """
    컨테이너 빌더.

    서비스 등록을 위한 빌더 패턴 구현.
    YAML 설정(registry.yaml)을 통해 DI 컨테이너 동작을 구성합니다.
    """

    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        """
        초기화.

        Args:
            config_loader: YAML 설정 로더 (None이면 기본 인스턴스 사용)
        """
        self._descriptors: dict[type, ServiceDescriptor] = {}
        self._config_loader = config_loader

    def register(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        scope: Scope = Scope.SINGLETON,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> ContainerBuilder:
        """
        서비스 타입 등록.

        Args:
            service_type: 서비스 타입 (인터페이스)
            implementation_type: 구현 타입
            scope: 스코프
            name: 이름
            tags: 태그 목록

        Returns:
            빌더 (체이닝용)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            scope=scope,
            name=name,
            tags=tags or [],
        )
        self._descriptors[service_type] = descriptor
        return self

    def register_instance(
        self,
        service_type: type[T],
        instance: T,
        name: str | None = None,
    ) -> ContainerBuilder:
        """
        인스턴스 직접 등록.

        Args:
            service_type: 서비스 타입
            instance: 인스턴스
            name: 이름

        Returns:
            빌더 (체이닝용)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            scope=Scope.SINGLETON,
            name=name,
        )
        self._descriptors[service_type] = descriptor
        return self

    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
        scope: Scope = Scope.SINGLETON,
        name: str | None = None,
    ) -> ContainerBuilder:
        """
        팩토리 함수 등록.

        Args:
            service_type: 서비스 타입
            factory: 팩토리 함수
            scope: 스코프
            name: 이름

        Returns:
            빌더 (체이닝용)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=scope,
            name=name,
        )
        self._descriptors[service_type] = descriptor
        return self

    def register_with_dependencies(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        dependencies: dict[str, type] | None = None,
        scope: Scope = Scope.SINGLETON,
    ) -> ContainerBuilder:
        """
        의존성 오버라이드와 함께 등록.

        Args:
            service_type: 서비스 타입
            implementation_type: 구현 타입
            dependencies: 파라미터명 -> 타입 매핑
            scope: 스코프

        Returns:
            빌더 (체이닝용)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            scope=scope,
            dependencies=dependencies or {},
        )
        self._descriptors[service_type] = descriptor
        return self

    def register_with_hooks(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        on_create: Callable[[T], None] | None = None,
        on_destroy: Callable[[T], None] | None = None,
        scope: Scope = Scope.SINGLETON,
    ) -> ContainerBuilder:
        """
        라이프사이클 훅과 함께 등록.

        Args:
            service_type: 서비스 타입
            implementation_type: 구현 타입
            on_create: 생성 후 콜백
            on_destroy: 파괴 전 콜백
            scope: 스코프

        Returns:
            빌더 (체이닝용)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            on_create=on_create,
            on_destroy=on_destroy,
            scope=scope,
        )
        self._descriptors[service_type] = descriptor
        return self

    def build(self) -> DIContainer:
        """
        컨테이너 빌드.

        Returns:
            구성된 DIContainer (YAML 설정 적용)
        """
        return DIContainer(
            descriptors=self._descriptors.copy(),
            config_loader=self._config_loader,
        )


# ============================================================
# DI 컨테이너 메인 클래스
# ============================================================
class DIContainer:
    """
    DI 컨테이너.

    의존성 주입의 핵심 컨테이너입니다.
    서비스 등록, 해결, 라이프사이클 관리를 담당합니다.

    YAML 설정 (registry.yaml):
        dependency_injection:
            default_scope: "singleton"
            auto_wiring:
                enabled: true
                by_type_hint: true
            circular_dependency:
                detect: true
                strategy: "error"
            thread_safety:
                enabled: true
                lock_timeout: 10

    Example:
        >>> # 빌더로 컨테이너 구성
        >>> builder = ContainerBuilder()
        >>> builder.register(ILogger, ConsoleLogger)
        >>> builder.register(IDatabase, PostgresDatabase)
        >>> container = builder.build()
        >>>
        >>> # 서비스 해결
        >>> logger = container.resolve(ILogger)
        >>>
        >>> # 또는 직접 등록
        >>> container.register(ICache, RedisCache)
    """

    def __init__(
        self,
        descriptors: dict[type, ServiceDescriptor] | None = None,
        config_loader: ConfigLoader | None = None,
    ) -> None:
        """
        초기화.

        Args:
            descriptors: 초기 서비스 설명자 딕셔너리
            config_loader: YAML 설정 로더 (None이면 기본 인스턴스 사용)
        """
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._descriptors: dict[type, ServiceDescriptor] = descriptors or {}
        self._singletons: dict[type, Any] = {}

        # YAML 설정 로드
        config = self._load_di_config()

        # 설정 적용
        self._default_scope_name: str = config.get("default_scope", DEFAULT_SCOPE_NAME)
        self._auto_wiring_enabled: bool = config.get("auto_wiring_enabled", True)
        self._auto_wiring_by_type_hint: bool = config.get("auto_wiring_by_type_hint", True)
        self._circular_dependency_detect: bool = config.get("circular_dependency_detect", True)
        self._circular_dependency_strategy: str = config.get("circular_dependency_strategy", "error")
        self._thread_safety_enabled: bool = config.get("thread_safety_enabled", True)
        self._lock_timeout: int = config.get("lock_timeout", DEFAULT_LOCK_TIMEOUT)

        # 루트 스코프 및 동기화
        self._root_scope = ScopeContext(name=self._default_scope_name)
        self._lock = threading.RLock()
        self._provider: ServiceProvider | None = None
        self._shutdown = False

        logger.info(
            f"DIContainer 초기화 완료 "
            f"(default_scope={self._default_scope_name}, "
            f"auto_wiring={self._auto_wiring_enabled}, "
            f"circular_detect={self._circular_dependency_detect})"
        )

    def __repr__(self) -> str:
        """DIContainer 인스턴스 표현."""
        with self._lock:
            registered = len(self._descriptors)
            singletons = len(self._singletons)
        return (
            f"DIContainer(registered={registered}, "
            f"singletons={singletons}, "
            f"scope={self._default_scope_name!r}, "
            f"auto_wiring={self._auto_wiring_enabled})"
        )

    def _load_di_config(self) -> dict[str, Any]:
        """
        YAML 설정에서 DI 컨테이너 설정 로드.

        YAML 구조 (registry.yaml):
            dependency_injection:
                default_scope: "singleton"
                auto_wiring:
                    enabled: true
                    by_type_hint: true
                circular_dependency:
                    detect: true
                    strategy: "error"
                thread_safety:
                    enabled: true
                    lock_timeout: 10

        Returns:
            설정 딕셔너리
        """
        try:
            di_config = self._config_loader.get(CONFIG_KEY_DI, {})
            if not isinstance(di_config, dict):
                di_config = {}

            # auto_wiring 섹션
            auto_wiring = di_config.get(CONFIG_KEY_AUTO_WIRING, {})

            # circular_dependency 섹션
            circular_dep = di_config.get(CONFIG_KEY_CIRCULAR_DEPENDENCY, {})

            # thread_safety 섹션
            thread_safety = di_config.get(CONFIG_KEY_THREAD_SAFETY, {})

            return {
                # 기본 스코프
                "default_scope": di_config.get(CONFIG_KEY_DEFAULT_SCOPE, DEFAULT_SCOPE_NAME),

                # 자동 와이어링 설정
                "auto_wiring_enabled": auto_wiring.get("enabled", True),
                "auto_wiring_by_type_hint": auto_wiring.get("by_type_hint", True),

                # 순환 의존성 설정
                "circular_dependency_detect": circular_dep.get("detect", True),
                "circular_dependency_strategy": circular_dep.get("strategy", "error"),

                # 스레드 안전 설정
                "thread_safety_enabled": thread_safety.get("enabled", True),
                "lock_timeout": thread_safety.get("lock_timeout", DEFAULT_LOCK_TIMEOUT),
            }
        except Exception as e:
            logger.warning(f"DI 설정 로드 실패, 기본값 사용: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """기본 설정 반환."""
        return {
            "default_scope": DEFAULT_SCOPE_NAME,
            "auto_wiring_enabled": True,
            "auto_wiring_by_type_hint": True,
            "circular_dependency_detect": True,
            "circular_dependency_strategy": "error",
            "thread_safety_enabled": True,
            "lock_timeout": DEFAULT_LOCK_TIMEOUT,
        }

    # ============================================================
    # 등록 메서드
    # ============================================================
    def register(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        scope: Scope = Scope.SINGLETON,
        name: str | None = None,
    ) -> None:
        """
        서비스 등록.

        Args:
            service_type: 서비스 타입 (인터페이스)
            implementation_type: 구현 타입
            scope: 스코프
            name: 이름
        """
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation_type,
                scope=scope,
                name=name,
            )
            self._descriptors[service_type] = descriptor
            self._provider = None  # 프로바이더 무효화

            logger.debug(f"서비스 등록: {service_type.__name__}")

    def register_instance(
        self,
        service_type: type[T],
        instance: T,
    ) -> None:
        """
        인스턴스 직접 등록.

        Args:
            service_type: 서비스 타입
            instance: 인스턴스
        """
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                instance=instance,
                scope=Scope.SINGLETON,
            )
            self._descriptors[service_type] = descriptor
            self._singletons[service_type] = instance
            self._provider = None

            logger.debug(f"인스턴스 등록: {service_type.__name__}")

    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
        scope: Scope = Scope.SINGLETON,
    ) -> None:
        """
        팩토리 함수 등록.

        Args:
            service_type: 서비스 타입
            factory: 팩토리 함수
            scope: 스코프
        """
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                factory=factory,
                scope=scope,
            )
            self._descriptors[service_type] = descriptor
            self._provider = None

            logger.debug(f"팩토리 등록: {service_type.__name__}")

    # ============================================================
    # 해결 메서드
    # ============================================================
    def resolve(self, service_type: type[T]) -> T:
        """
        서비스 해결.

        Args:
            service_type: 서비스 타입

        Returns:
            서비스 인스턴스

        Raises:
            ServiceNotFoundError: 서비스를 찾을 수 없을 때
        """
        return self._get_provider().get(service_type)

    def resolve_optional(self, service_type: type[T]) -> T | None:
        """
        서비스 해결 (Optional).

        등록되지 않은 서비스는 None 반환.
        """
        return self._get_provider().get_optional(service_type)

    def resolve_all(self, service_type: type[T]) -> list[T]:
        """
        특정 타입의 모든 서비스 해결.
        """
        return self._get_provider().get_all(service_type)

    def _get_provider(self) -> ServiceProvider:
        """서비스 프로바이더 가져오기."""
        if self._provider is None:
            with self._lock:
                if self._provider is None:
                    self._provider = ServiceProvider(
                        self._descriptors,
                        self._singletons,
                        self._root_scope,
                    )
        return self._provider

    # ============================================================
    # 스코프 관리
    # ============================================================
    @contextmanager
    def create_scope(self, name: str = "request") -> Iterator[ServiceProvider]:
        """
        새 스코프 생성.

        Args:
            name: 스코프 이름

        Yields:
            스코프 내 ServiceProvider
        """
        provider = self._get_provider()
        with provider.create_scope(name) as scoped_provider:
            yield scoped_provider

    # ============================================================
    # 조회 메서드
    # ============================================================
    def is_registered(self, service_type: type) -> bool:
        """
        서비스 등록 여부 확인.

        Args:
            service_type: 서비스 타입

        Returns:
            등록 여부
        """
        return service_type in self._descriptors

    def get_descriptor(self, service_type: type[T]) -> ServiceDescriptor[T] | None:
        """
        서비스 설명자 조회.

        Args:
            service_type: 서비스 타입

        Returns:
            서비스 설명자 (없으면 None)
        """
        return self._descriptors.get(service_type)

    def get_all_descriptors(self) -> dict[type, ServiceDescriptor]:
        """
        모든 서비스 설명자 조회.

        Returns:
            타입 -> 설명자 딕셔너리
        """
        return self._descriptors.copy()

    def get_registered_types(self) -> list[type]:
        """
        등록된 모든 타입 조회.

        Returns:
            타입 목록
        """
        return list(self._descriptors.keys())

    def get_by_tag(self, tag: str) -> list[type]:
        """
        태그로 서비스 타입 조회.

        Args:
            tag: 태그

        Returns:
            해당 태그를 가진 서비스 타입 목록
        """
        return [
            t for t, d in self._descriptors.items() if tag in d.tags
        ]

    # ============================================================
    # 의존성 그래프
    # ============================================================
    def build_dependency_graph(self, root_type: type) -> DependencyGraph:
        """
        의존성 그래프 빌드.

        Args:
            root_type: 루트 타입

        Returns:
            의존성 그래프
        """
        graph = DependencyGraph(root=root_type)

        def analyze(service_type: type, depth: int = 0) -> None:
            if service_type in graph.nodes:
                return

            descriptor = self._descriptors.get(service_type)
            if not descriptor:
                graph.add_node(service_type, [], depth)
                return

            # 의존성 분석
            dependencies: list[type] = []
            impl_type = descriptor.get_implementation()

            try:
                hints = get_type_hints(impl_type.__init__)
            except Exception:
                hints = {}

            sig = inspect.signature(impl_type.__init__)

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                param_type = hints.get(param_name, param.annotation)
                if param_type != inspect.Parameter.empty:
                    param_type = descriptor.dependencies.get(param_name, param_type)
                    # Optional 타입 언래핑
                    unwrapped_type, _ = _unwrap_optional(param_type)
                    dependencies.append(unwrapped_type)

            graph.add_node(service_type, dependencies, depth)

            for dep_type in dependencies:
                analyze(dep_type, depth + 1)

        analyze(root_type)
        return graph

    def validate(self) -> list[str]:
        """
        컨테이너 유효성 검증.

        Returns:
            에러 메시지 목록 (빈 리스트면 유효)
        """
        errors: list[str] = []

        for service_type in self._descriptors:
            try:
                graph = self.build_dependency_graph(service_type)
                cycles = graph.detect_cycles()
                if cycles:
                    cycle_str = " -> ".join(t.__name__ for t in cycles)
                    errors.append(f"순환 의존성: {cycle_str}")
            except Exception as e:
                errors.append(f"{service_type.__name__} 분석 실패: {e}")

        return errors

    # ============================================================
    # 상태 조회
    # ============================================================
    @property
    def service_count(self) -> int:
        """등록된 서비스 수."""
        return len(self._descriptors)

    @property
    def singleton_count(self) -> int:
        """생성된 싱글톤 수."""
        return len(self._singletons)

    def get_status(self) -> dict[str, Any]:
        """
        컨테이너 상태 조회 (모든 YAML 설정 포함).

        Returns:
            상태 정보 딕셔너리
        """
        scope_counts = {Scope.SINGLETON: 0, Scope.TRANSIENT: 0, Scope.SCOPED: 0}
        for descriptor in self._descriptors.values():
            scope_counts[descriptor.scope] += 1

        return {
            # 서비스 상태
            "registered_services": len(self._descriptors),
            "created_singletons": len(self._singletons),
            "scope_counts": {s.value: c for s, c in scope_counts.items()},

            # YAML 설정값
            "default_scope": self._default_scope_name,
            "auto_wiring_enabled": self._auto_wiring_enabled,
            "auto_wiring_by_type_hint": self._auto_wiring_by_type_hint,
            "circular_dependency_detect": self._circular_dependency_detect,
            "circular_dependency_strategy": self._circular_dependency_strategy,
            "thread_safety_enabled": self._thread_safety_enabled,
            "lock_timeout": self._lock_timeout,

            # 상태 플래그
            "shutdown": self._shutdown,

            # 서비스 목록
            "services": [
                {
                    "type": t.__name__,
                    "scope": d.scope.value,
                    "has_instance": d.is_instance_provided,
                }
                for t, d in self._descriptors.items()
            ],
        }

    # ============================================================
    # 종료
    # ============================================================
    def shutdown(self) -> None:
        """컨테이너 종료."""
        with self._lock:
            if self._shutdown:
                return

            self._shutdown = True

            # on_destroy 훅 호출
            for service_type, instance in self._singletons.items():
                descriptor = self._descriptors.get(service_type)
                if descriptor and descriptor.on_destroy:
                    try:
                        descriptor.on_destroy(instance)
                    except Exception as e:
                        logger.warning(f"on_destroy 훅 실패 ({service_type.__name__}): {e}")

            # 정리
            self._singletons.clear()
            self._root_scope.clear()
            self._provider = None

            logger.info("DIContainer 종료 완료")

    def __enter__(self) -> "DIContainer":
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료."""
        self.shutdown()


# ============================================================
# 데코레이터
# ============================================================
# 주입 가능 표시용 메타데이터 키
_INJECTABLE_MARKER = "__di_injectable__"
_INJECT_MARKER = "__di_inject__"


def injectable(
    scope: Scope = Scope.SINGLETON,
    name: str | None = None,
    tags: list[str] | None = None,
) -> Callable[[type[T]], type[T]]:
    """
    주입 가능 서비스 표시 데코레이터.

    클래스를 주입 가능한 서비스로 표시합니다.

    Args:
        scope: 스코프
        name: 이름
        tags: 태그 목록

    Returns:
        데코레이터

    Example:
        >>> @injectable(scope=Scope.SINGLETON)
        ... class MyService:
        ...     pass
    """
    def decorator(cls: type[T]) -> type[T]:
        setattr(cls, _INJECTABLE_MARKER, {
            "scope": scope,
            "name": name,
            "tags": tags or [],
        })
        return cls

    return decorator


def inject(
    service_type: type | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    의존성 주입 데코레이터.

    메서드나 함수에 의존성 주입을 표시합니다.

    Args:
        service_type: 주입할 서비스 타입 (None이면 타입 힌트 사용)

    Returns:
        데코레이터

    Example:
        >>> class MyController:
        ...     @inject()
        ...     def __init__(self, logger: ILogger, db: IDatabase):
        ...         self.logger = logger
        ...         self.db = db
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        inject_info = getattr(func, _INJECT_MARKER, {})
        if service_type:
            inject_info["explicit_type"] = service_type
        setattr(func, _INJECT_MARKER, inject_info)
        return func

    return decorator


def is_injectable(cls: type) -> bool:
    """클래스가 주입 가능한지 확인."""
    return hasattr(cls, _INJECTABLE_MARKER)


def get_injectable_metadata(cls: type) -> dict[str, Any] | None:
    """주입 가능 메타데이터 가져오기."""
    return getattr(cls, _INJECTABLE_MARKER, None)


# ============================================================
# 전역 인스턴스 관리
# ============================================================
_global_container: DIContainer | None = None
_container_lock = threading.Lock()


def get_container() -> DIContainer:
    """
    전역 컨테이너 가져오기.

    Returns:
        전역 DIContainer 인스턴스
    """
    global _global_container
    with _container_lock:
        if _global_container is None:
            _global_container = DIContainer()
        return _global_container


def configure_container(
    configurator: Callable[[DIContainer], None],
) -> DIContainer:
    """
    전역 컨테이너 설정.

    Args:
        configurator: 컨테이너 설정 함수

    Returns:
        설정된 컨테이너

    Example:
        >>> def setup(container: DIContainer):
        ...     container.register(ILogger, ConsoleLogger)
        ...     container.register(IDatabase, PostgresDatabase)
        >>>
        >>> container = configure_container(setup)
    """
    container = get_container()
    configurator(container)
    return container


def _reset_container() -> None:
    """전역 컨테이너 초기화 (테스트용)."""
    global _global_container
    with _container_lock:
        if _global_container is not None:
            _global_container.shutdown()
            _global_container = None


# 모듈 버전 정보
__version__: str = "1.0.0"
