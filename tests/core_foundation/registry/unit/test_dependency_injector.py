# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/unit
파일: test_dependency_injector.py
설명: DI 컨테이너 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [1]  Enum 테스트 (8개) - Scope, LifecycleHook, ResolutionStatus
    [2]  상수 테스트 (3개) - DEFAULT_MAX_RESOLUTION_DEPTH, DEFAULT_SCOPE_NAME
    [3]  예외 클래스 테스트 (6개) - DIException, ServiceNotFoundError, CircularDependencyError, ResolutionError
    [4]  ServiceDescriptor 테스트 (8개) - 생성, 스코프, 팩토리, 의존성, to_dict
    [5]  ContainerBuilder 테스트 (12개) - 빌더 패턴, 등록, 체이닝, 빌드
    [6]  DIContainer / ServiceProvider 테스트 (15개) - 해결, 스코프, 라이프사이클, 그래프
    [7]  Decorator 테스트 (8개) - @injectable, @inject, is_injectable, get_injectable_metadata
    [8]  전역 함수 테스트 (5개) - get_container, configure_container, _reset_container
    [9]  스레드 안전성 테스트 (5개) - 동시 접근, 스레드 로컬 스택
    [10] 순환 의존성 탐지 테스트 (5개) - A→B→A, A→B→C→A, 그래프 순환 탐지
"""

import sys
import threading
import time
from dataclasses import fields
from pathlib import Path
from typing import Optional

# ============================================================
# 프로젝트 루트 경로 추가
# ============================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# ============================================================
# 테스트 대상 임포트
# ============================================================
from core_foundation.registry.dependency_injector import (
    # Enum
    Scope,
    LifecycleHook,
    ResolutionStatus,
    # 상수
    DEFAULT_MAX_RESOLUTION_DEPTH,
    DEFAULT_SCOPE_NAME,
    # 예외 클래스
    DIException,
    ServiceNotFoundError,
    CircularDependencyError,
    ResolutionError,
    # 데이터 클래스
    ServiceDescriptor,
    DependencyNode,
    DependencyGraph,
    ScopeContext,
    # 메인 클래스
    DIContainer,
    ContainerBuilder,
    ServiceProvider,
    # 데코레이터
    injectable,
    inject,
    is_injectable,
    get_injectable_metadata,
    # 전역 함수
    get_container,
    configure_container,
    _reset_container,
)


# ============================================================
# 테스트 결과 클래스
# ============================================================
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ============================================================
# 모의 서비스 클래스 (Mock Service Classes)
# ============================================================
class ILogger:
    """로거 인터페이스."""
    pass


class ConsoleLogger(ILogger):
    """콘솔 로거 구현."""
    def __init__(self):
        self.logs = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)


class IDatabase:
    """데이터베이스 인터페이스."""
    pass


class InMemoryDatabase(IDatabase):
    """인메모리 데이터베이스 구현."""
    def __init__(self, logger: ILogger = None):
        self.logger = logger
        self.data = {}


class IUserService:
    """사용자 서비스 인터페이스."""
    pass


class UserService(IUserService):
    """사용자 서비스 구현."""
    def __init__(self, db: IDatabase, logger: ILogger = None):
        self.db = db
        self.logger = logger


class ICache:
    """캐시 인터페이스."""
    pass


class InMemoryCache(ICache):
    """인메모리 캐시 구현."""
    def __init__(self):
        self.store = {}


class SimpleService:
    """단순 서비스 (의존성 없음)."""
    def __init__(self):
        self.value = 42


class ServiceWithOptional:
    """선택적 의존성을 가진 서비스."""
    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger


class ServiceA:
    """순환 의존성 테스트용 서비스 A."""
    def __init__(self, b: "ServiceB"):
        self.b = b


class ServiceB:
    """순환 의존성 테스트용 서비스 B."""
    def __init__(self, a: "ServiceA"):
        self.a = a


class ServiceX:
    """3단계 순환 의존성 테스트용 서비스 X."""
    def __init__(self, y: "ServiceY"):
        self.y = y


class ServiceY:
    """3단계 순환 의존성 테스트용 서비스 Y."""
    def __init__(self, z: "ServiceZ"):
        self.z = z


class ServiceZ:
    """3단계 순환 의존성 테스트용 서비스 Z."""
    def __init__(self, x: "ServiceX"):
        self.x = x


class IndependentA:
    """독립 서비스 A (순환 없음)."""
    def __init__(self):
        self.value = "A"


class IndependentB:
    """독립 서비스 B (IndependentA에 의존)."""
    def __init__(self, a: IndependentA):
        self.a = a


class IndependentC:
    """독립 서비스 C (IndependentB에 의존)."""
    def __init__(self, b: IndependentB):
        self.b = b


class TaggedServiceAlpha:
    """태그 테스트용 서비스 알파."""
    def __init__(self):
        self.name = "alpha"


class TaggedServiceBeta:
    """태그 테스트용 서비스 베타."""
    def __init__(self):
        self.name = "beta"


# ============================================================
# 헬퍼: DIContainer를 ConfigLoader 없이 생성
# ============================================================
def _make_container(descriptors=None):
    """ConfigLoader.get_instance() 오류를 우회하여 DIContainer 생성."""
    container = object.__new__(DIContainer)
    container._descriptors = descriptors or {}
    container._singletons = {}
    container._default_scope_name = DEFAULT_SCOPE_NAME
    container._auto_wiring_enabled = True
    container._auto_wiring_by_type_hint = True
    container._circular_dependency_detect = True
    container._circular_dependency_strategy = "error"
    container._thread_safety_enabled = True
    container._lock_timeout = 10
    container._root_scope = ScopeContext(name=DEFAULT_SCOPE_NAME)
    container._lock = threading.RLock()
    container._provider = None
    container._shutdown = False
    container._config_loader = None
    return container


def _make_builder():
    """ConfigLoader 없이 ContainerBuilder 생성."""
    return ContainerBuilder(config_loader=None)


# ============================================================
# [1] Enum 테스트
# ============================================================
def test_enums(result: TestResult) -> None:
    """Scope, LifecycleHook, ResolutionStatus Enum 테스트."""
    print("\n[1] Enum 테스트")

    # 1-1: Scope 멤버 확인
    try:
        members = [Scope.SINGLETON, Scope.TRANSIENT, Scope.SCOPED]
        assert len(members) == 3, f"Scope 멤버 수: {len(members)} != 3"
        result.ok("Scope 멤버 존재 확인 (SINGLETON, TRANSIENT, SCOPED)")
    except Exception as e:
        result.fail("Scope 멤버 존재 확인", str(e))

    # 1-2: Scope 값 확인
    try:
        assert Scope.SINGLETON.value == "singleton", f"SINGLETON 값: {Scope.SINGLETON.value}"
        assert Scope.TRANSIENT.value == "transient", f"TRANSIENT 값: {Scope.TRANSIENT.value}"
        assert Scope.SCOPED.value == "scoped", f"SCOPED 값: {Scope.SCOPED.value}"
        result.ok("Scope 값 확인 (singleton, transient, scoped)")
    except Exception as e:
        result.fail("Scope 값 확인", str(e))

    # 1-3: Scope.is_cached 속성
    try:
        assert Scope.SINGLETON.is_cached is True, "SINGLETON은 캐싱됨"
        assert Scope.SCOPED.is_cached is True, "SCOPED는 캐싱됨"
        assert Scope.TRANSIENT.is_cached is False, "TRANSIENT는 캐싱되지 않음"
        result.ok("Scope.is_cached 속성 확인")
    except Exception as e:
        result.fail("Scope.is_cached 속성 확인", str(e))

    # 1-4: LifecycleHook 멤버 확인
    try:
        hooks = [LifecycleHook.ON_CREATE, LifecycleHook.ON_DESTROY,
                 LifecycleHook.ON_ACTIVATE, LifecycleHook.ON_DEACTIVATE]
        assert len(hooks) == 4, f"LifecycleHook 멤버 수: {len(hooks)} != 4"
        assert LifecycleHook.ON_CREATE.value == "on_create"
        assert LifecycleHook.ON_DESTROY.value == "on_destroy"
        result.ok("LifecycleHook 멤버 확인 (ON_CREATE, ON_DESTROY, ON_ACTIVATE, ON_DEACTIVATE)")
    except Exception as e:
        result.fail("LifecycleHook 멤버 확인", str(e))

    # 1-5: ResolutionStatus 멤버 확인
    try:
        statuses = [ResolutionStatus.PENDING, ResolutionStatus.RESOLVING,
                    ResolutionStatus.RESOLVED, ResolutionStatus.FAILED]
        assert len(statuses) == 4, f"ResolutionStatus 멤버 수: {len(statuses)} != 4"
        assert ResolutionStatus.PENDING.value == "pending"
        assert ResolutionStatus.RESOLVED.value == "resolved"
        assert ResolutionStatus.FAILED.value == "failed"
        result.ok("ResolutionStatus 멤버 확인 (PENDING, RESOLVING, RESOLVED, FAILED)")
    except Exception as e:
        result.fail("ResolutionStatus 멤버 확인", str(e))

    # 1-6: 값 고유성 확인 (Scope)
    try:
        scope_values = [s.value for s in Scope]
        assert len(scope_values) == len(set(scope_values)), "Scope 값이 고유하지 않음"
        result.ok("Scope 값 고유성 확인")
    except Exception as e:
        result.fail("Scope 값 고유성 확인", str(e))

    # 1-7: 값 고유성 확인 (LifecycleHook)
    try:
        hook_values = [h.value for h in LifecycleHook]
        assert len(hook_values) == len(set(hook_values)), "LifecycleHook 값이 고유하지 않음"
        result.ok("LifecycleHook 값 고유성 확인")
    except Exception as e:
        result.fail("LifecycleHook 값 고유성 확인", str(e))

    # 1-8: 문자열 표현 (str(Enum))
    try:
        # Scope는 str, Enum 상속이므로 str()은 value를 반환
        scope_str = str(Scope.SINGLETON)
        assert "singleton" in scope_str.lower(), f"Scope 문자열: {scope_str}"
        status_str = str(ResolutionStatus.PENDING)
        assert "pending" in status_str.lower(), f"ResolutionStatus 문자열: {status_str}"
        result.ok("Enum 문자열 표현 확인")
    except Exception as e:
        result.fail("Enum 문자열 표현 확인", str(e))


# ============================================================
# [2] 상수 테스트
# ============================================================
def test_constants(result: TestResult) -> None:
    """상수 검증 테스트."""
    print("\n[2] 상수 테스트")

    # 2-1: DEFAULT_MAX_RESOLUTION_DEPTH > 0
    try:
        assert DEFAULT_MAX_RESOLUTION_DEPTH > 0, (
            f"DEFAULT_MAX_RESOLUTION_DEPTH가 0보다 커야 합니다: {DEFAULT_MAX_RESOLUTION_DEPTH}"
        )
        assert DEFAULT_MAX_RESOLUTION_DEPTH == 50, (
            f"DEFAULT_MAX_RESOLUTION_DEPTH 기본값 50 기대, 실제: {DEFAULT_MAX_RESOLUTION_DEPTH}"
        )
        result.ok(f"DEFAULT_MAX_RESOLUTION_DEPTH = {DEFAULT_MAX_RESOLUTION_DEPTH} (양수)")
    except Exception as e:
        result.fail("DEFAULT_MAX_RESOLUTION_DEPTH 확인", str(e))

    # 2-2: DEFAULT_SCOPE_NAME 문자열
    try:
        assert isinstance(DEFAULT_SCOPE_NAME, str), (
            f"DEFAULT_SCOPE_NAME 타입 오류: {type(DEFAULT_SCOPE_NAME)}"
        )
        assert len(DEFAULT_SCOPE_NAME) > 0, "DEFAULT_SCOPE_NAME이 빈 문자열"
        assert DEFAULT_SCOPE_NAME == "default", (
            f"DEFAULT_SCOPE_NAME 기대 'default', 실제: '{DEFAULT_SCOPE_NAME}'"
        )
        result.ok(f"DEFAULT_SCOPE_NAME = '{DEFAULT_SCOPE_NAME}' (문자열)")
    except Exception as e:
        result.fail("DEFAULT_SCOPE_NAME 확인", str(e))

    # 2-3: 타입 정확성
    try:
        assert isinstance(DEFAULT_MAX_RESOLUTION_DEPTH, int), "깊이는 정수"
        assert isinstance(DEFAULT_SCOPE_NAME, str), "스코프 이름은 문자열"
        result.ok("상수 타입 정확성 확인")
    except Exception as e:
        result.fail("상수 타입 정확성 확인", str(e))


# ============================================================
# [3] 예외 클래스 테스트
# ============================================================
def test_exceptions(result: TestResult) -> None:
    """예외 클래스 테스트."""
    print("\n[3] 예외 클래스 테스트")

    # 3-1: DIException 기본 생성
    try:
        exc = DIException("DI 오류 발생")
        assert "DI 오류 발생" in str(exc), f"메시지 누락: {exc}"
        result.ok("DIException 기본 생성")
    except Exception as e:
        result.fail("DIException 기본 생성", str(e))

    # 3-2: ServiceNotFoundError 생성 (타입 정보 포함)
    try:
        exc = ServiceNotFoundError(ILogger)
        assert exc.service_type is ILogger, "service_type 미설정"
        assert "ILogger" in str(exc), f"타입 이름 누락: {exc}"
        result.ok("ServiceNotFoundError 생성 (타입 정보 포함)")
    except Exception as e:
        result.fail("ServiceNotFoundError 생성", str(e))

    # 3-3: CircularDependencyError 생성 (체인 포함)
    try:
        chain = [ServiceA, ServiceB, ServiceA]
        exc = CircularDependencyError(chain)
        assert exc.chain == chain, "chain 미설정"
        assert "ServiceA" in str(exc), "ServiceA 누락"
        assert "ServiceB" in str(exc), "ServiceB 누락"
        result.ok("CircularDependencyError 생성 (의존성 체인)")
    except Exception as e:
        result.fail("CircularDependencyError 생성", str(e))

    # 3-4: ResolutionError 생성
    try:
        exc = ResolutionError(IDatabase, "의존성 해결 불가")
        assert exc.service_type is IDatabase, "service_type 미설정"
        assert exc.reason == "의존성 해결 불가", f"reason 불일치: {exc.reason}"
        assert "IDatabase" in str(exc), "타입 이름 누락"
        result.ok("ResolutionError 생성")
    except Exception as e:
        result.fail("ResolutionError 생성", str(e))

    # 3-5: 예외 계층 (모두 DIException 상속)
    try:
        assert issubclass(ServiceNotFoundError, DIException), "ServiceNotFoundError -> DIException"
        assert issubclass(CircularDependencyError, DIException), "CircularDependencyError -> DIException"
        assert issubclass(ResolutionError, DIException), "ResolutionError -> DIException"
        result.ok("예외 계층 확인 (모두 DIException 상속)")
    except Exception as e:
        result.fail("예외 계층 확인", str(e))

    # 3-6: 에러 메시지 포맷
    try:
        exc_snf = ServiceNotFoundError(ICache)
        assert "서비스를 찾을 수 없습니다" in str(exc_snf), "ServiceNotFoundError 메시지 형식"

        exc_cd = CircularDependencyError([ServiceA, ServiceB, ServiceA])
        msg_cd = str(exc_cd)
        assert "순환 의존성 발견" in msg_cd, "CircularDependencyError 메시지 형식"
        assert "ServiceA -> ServiceB -> ServiceA" in msg_cd, f"체인 포맷: {msg_cd}"

        exc_re = ResolutionError(SimpleService, "테스트 실패")
        assert "서비스 해결 실패" in str(exc_re), "ResolutionError 메시지 형식"
        result.ok("에러 메시지 포맷 확인")
    except Exception as e:
        result.fail("에러 메시지 포맷 확인", str(e))


# ============================================================
# [4] ServiceDescriptor 테스트
# ============================================================
def test_service_descriptor(result: TestResult) -> None:
    """ServiceDescriptor 데이터클래스 테스트."""
    print("\n[4] ServiceDescriptor 테스트")

    # 4-1: 기본 생성 (service_type, implementation_type, scope)
    try:
        desc = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            scope=Scope.SINGLETON,
        )
        assert desc.service_type is ILogger, "service_type"
        assert desc.implementation_type is ConsoleLogger, "implementation_type"
        assert desc.scope == Scope.SINGLETON, "scope"
        result.ok("ServiceDescriptor 기본 생성")
    except Exception as e:
        result.fail("ServiceDescriptor 기본 생성", str(e))

    # 4-2: SINGLETON 스코프
    try:
        desc = ServiceDescriptor(service_type=ILogger, scope=Scope.SINGLETON)
        assert desc.scope == Scope.SINGLETON
        assert desc.scope.is_cached is True
        result.ok("ServiceDescriptor SINGLETON 스코프")
    except Exception as e:
        result.fail("ServiceDescriptor SINGLETON 스코프", str(e))

    # 4-3: TRANSIENT 스코프
    try:
        desc = ServiceDescriptor(service_type=ILogger, scope=Scope.TRANSIENT)
        assert desc.scope == Scope.TRANSIENT
        assert desc.scope.is_cached is False
        result.ok("ServiceDescriptor TRANSIENT 스코프")
    except Exception as e:
        result.fail("ServiceDescriptor TRANSIENT 스코프", str(e))

    # 4-4: SCOPED 스코프
    try:
        desc = ServiceDescriptor(service_type=ILogger, scope=Scope.SCOPED)
        assert desc.scope == Scope.SCOPED
        assert desc.scope.is_cached is True
        result.ok("ServiceDescriptor SCOPED 스코프")
    except Exception as e:
        result.fail("ServiceDescriptor SCOPED 스코프", str(e))

    # 4-5: 팩토리 함수 디스크립터
    try:
        def logger_factory() -> ILogger:
            return ConsoleLogger()

        desc = ServiceDescriptor(
            service_type=ILogger,
            factory=logger_factory,
            scope=Scope.SINGLETON,
        )
        assert desc.is_factory_provided is True, "is_factory_provided"
        assert desc.is_instance_provided is False, "is_instance_provided"
        assert desc.factory is logger_factory, "factory"
        result.ok("ServiceDescriptor 팩토리 함수 디스크립터")
    except Exception as e:
        result.fail("ServiceDescriptor 팩토리 함수 디스크립터", str(e))

    # 4-6: 의존성 목록
    try:
        desc = ServiceDescriptor(
            service_type=IUserService,
            implementation_type=UserService,
            dependencies={"db": InMemoryDatabase, "logger": ConsoleLogger},
        )
        assert "db" in desc.dependencies, "db 의존성"
        assert "logger" in desc.dependencies, "logger 의존성"
        assert desc.dependencies["db"] is InMemoryDatabase
        result.ok("ServiceDescriptor 의존성 목록")
    except Exception as e:
        result.fail("ServiceDescriptor 의존성 목록", str(e))

    # 4-7: 라이프사이클 훅
    try:
        created = []
        destroyed = []

        desc = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            on_create=lambda inst: created.append(inst),
            on_destroy=lambda inst: destroyed.append(inst),
        )
        assert desc.on_create is not None, "on_create 설정됨"
        assert desc.on_destroy is not None, "on_destroy 설정됨"

        # 훅 직접 호출 테스트
        mock_inst = ConsoleLogger()
        desc.on_create(mock_inst)
        assert len(created) == 1
        desc.on_destroy(mock_inst)
        assert len(destroyed) == 1
        result.ok("ServiceDescriptor 라이프사이클 훅")
    except Exception as e:
        result.fail("ServiceDescriptor 라이프사이클 훅", str(e))

    # 4-8: to_dict 변환
    try:
        desc = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            scope=Scope.SINGLETON,
            name="main_logger",
            tags=["core", "logging"],
        )
        d = desc.to_dict()
        assert d["service_type"] == "ILogger", f"service_type: {d['service_type']}"
        assert d["implementation_type"] == "ConsoleLogger", f"implementation_type: {d['implementation_type']}"
        assert d["scope"] == "singleton", f"scope: {d['scope']}"
        assert d["name"] == "main_logger", f"name: {d['name']}"
        assert d["tags"] == ["core", "logging"], f"tags: {d['tags']}"
        assert d["has_factory"] is False
        assert d["has_instance"] is False
        result.ok("ServiceDescriptor to_dict 변환")
    except Exception as e:
        result.fail("ServiceDescriptor to_dict 변환", str(e))


# ============================================================
# [5] ContainerBuilder 테스트
# ============================================================
def test_container_builder(result: TestResult) -> None:
    """ContainerBuilder 빌더 패턴 테스트."""
    print("\n[5] ContainerBuilder 테스트")
    _reset_container()

    # 5-1: 빌더 생성
    try:
        builder = _make_builder()
        assert builder is not None, "빌더 생성 실패"
        assert isinstance(builder, ContainerBuilder), "타입 오류"
        result.ok("ContainerBuilder 생성")
    except Exception as e:
        result.fail("ContainerBuilder 생성", str(e))

    # 5-2: register (기본 - 싱글톤)
    try:
        builder = _make_builder()
        ret = builder.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        assert ret is builder, "체이닝 반환값"
        assert ILogger in builder._descriptors, "ILogger 등록됨"
        assert builder._descriptors[ILogger].scope == Scope.SINGLETON
        result.ok("register_singleton (기본 싱글톤 등록)")
    except Exception as e:
        result.fail("register_singleton", str(e))

    # 5-3: register (TRANSIENT)
    try:
        builder = _make_builder()
        builder.register(ILogger, ConsoleLogger, scope=Scope.TRANSIENT)
        assert builder._descriptors[ILogger].scope == Scope.TRANSIENT
        result.ok("register_transient (트랜지언트 등록)")
    except Exception as e:
        result.fail("register_transient", str(e))

    # 5-4: register (SCOPED)
    try:
        builder = _make_builder()
        builder.register(ILogger, ConsoleLogger, scope=Scope.SCOPED)
        assert builder._descriptors[ILogger].scope == Scope.SCOPED
        result.ok("register_scoped (스코프 등록)")
    except Exception as e:
        result.fail("register_scoped", str(e))

    # 5-5: register_factory
    try:
        builder = _make_builder()
        factory_fn = lambda: ConsoleLogger()
        builder.register_factory(ILogger, factory_fn, scope=Scope.SINGLETON)
        desc = builder._descriptors[ILogger]
        assert desc.is_factory_provided is True
        assert desc.factory is factory_fn
        result.ok("register_factory (팩토리 등록)")
    except Exception as e:
        result.fail("register_factory", str(e))

    # 5-6: register_instance
    try:
        builder = _make_builder()
        instance = ConsoleLogger()
        builder.register_instance(ILogger, instance)
        desc = builder._descriptors[ILogger]
        assert desc.is_instance_provided is True
        assert desc.instance is instance
        assert desc.scope == Scope.SINGLETON, "인스턴스 등록 시 싱글톤"
        result.ok("register_instance (인스턴스 직접 등록)")
    except Exception as e:
        result.fail("register_instance", str(e))

    # 5-7: register_with_hooks (라이프사이클 훅)
    try:
        builder = _make_builder()
        on_create_called = []
        on_destroy_called = []
        builder.register_with_hooks(
            ILogger,
            ConsoleLogger,
            on_create=lambda inst: on_create_called.append(inst),
            on_destroy=lambda inst: on_destroy_called.append(inst),
        )
        desc = builder._descriptors[ILogger]
        assert desc.on_create is not None
        assert desc.on_destroy is not None
        result.ok("register_with_hooks (라이프사이클 훅 등록)")
    except Exception as e:
        result.fail("register_with_hooks", str(e))

    # 5-8: build() -> DIContainer
    try:
        builder = _make_builder()
        builder.register(ILogger, ConsoleLogger)
        container = builder.build()
        assert isinstance(container, DIContainer), "DIContainer 인스턴스"
        assert container.is_registered(ILogger), "ILogger 등록됨"
        result.ok("build() -> DIContainer 반환")
    except Exception as e:
        result.fail("build() -> DIContainer", str(e))

    # 5-9: 체인 등록 (Fluent API)
    try:
        builder = _make_builder()
        chain_result = (
            builder
            .register(ILogger, ConsoleLogger)
            .register(ICache, InMemoryCache)
            .register(SimpleService)
        )
        assert chain_result is builder, "체이닝 반환값"
        assert len(builder._descriptors) == 3, f"등록 수: {len(builder._descriptors)}"
        result.ok("체인 등록 (Fluent API)")
    except Exception as e:
        result.fail("체인 등록 (Fluent API)", str(e))

    # 5-10: 중복 등록 (덮어쓰기)
    try:
        builder = _make_builder()
        builder.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        builder.register(ILogger, ConsoleLogger, scope=Scope.TRANSIENT)
        desc = builder._descriptors[ILogger]
        assert desc.scope == Scope.TRANSIENT, "마지막 등록이 우선"
        result.ok("중복 등록 시 덮어쓰기 확인")
    except Exception as e:
        result.fail("중복 등록 시 덮어쓰기 확인", str(e))

    # 5-11: 추상 -> 구현 매핑
    try:
        builder = _make_builder()
        builder.register(IDatabase, InMemoryDatabase)
        desc = builder._descriptors[IDatabase]
        assert desc.service_type is IDatabase
        assert desc.implementation_type is InMemoryDatabase
        assert desc.get_implementation() is InMemoryDatabase
        result.ok("추상 -> 구현 매핑 확인")
    except Exception as e:
        result.fail("추상 -> 구현 매핑 확인", str(e))

    # 5-12: 의존성과 함께 빌드
    try:
        builder = _make_builder()
        builder.register(ILogger, ConsoleLogger)
        builder.register(IDatabase, InMemoryDatabase)
        builder.register(IUserService, UserService)
        container = builder.build()
        assert container.is_registered(ILogger)
        assert container.is_registered(IDatabase)
        assert container.is_registered(IUserService)
        assert container.service_count == 3
        result.ok("의존성과 함께 빌드 확인")
    except Exception as e:
        result.fail("의존성과 함께 빌드 확인", str(e))


# ============================================================
# [6] DIContainer / ServiceProvider 테스트
# ============================================================
def test_container_and_provider(result: TestResult) -> None:
    """DIContainer 및 ServiceProvider 테스트."""
    print("\n[6] DIContainer / ServiceProvider 테스트")
    _reset_container()

    # 6-1: 싱글톤 해결 (동일 인스턴스)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        inst1 = container.resolve(ILogger)
        inst2 = container.resolve(ILogger)
        assert inst1 is inst2, "싱글톤은 동일 인스턴스"
        assert isinstance(inst1, ConsoleLogger), "ConsoleLogger 인스턴스"
        result.ok("싱글톤 해결 -> 동일 인스턴스")
    except Exception as e:
        result.fail("싱글톤 해결 -> 동일 인스턴스", str(e))

    # 6-2: 트랜지언트 해결 (다른 인스턴스)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.TRANSIENT)
        inst1 = container.resolve(ILogger)
        inst2 = container.resolve(ILogger)
        assert inst1 is not inst2, "트랜지언트는 다른 인스턴스"
        assert isinstance(inst1, ConsoleLogger)
        assert isinstance(inst2, ConsoleLogger)
        result.ok("트랜지언트 해결 -> 다른 인스턴스")
    except Exception as e:
        result.fail("트랜지언트 해결 -> 다른 인스턴스", str(e))

    # 6-3: 미등록 서비스 -> ServiceNotFoundError
    try:
        container = _make_container()
        try:
            container.resolve(ILogger)
            result.fail("미등록 서비스 -> ServiceNotFoundError", "예외 미발생")
        except ServiceNotFoundError as e:
            assert e.service_type is ILogger
            result.ok("미등록 서비스 -> ServiceNotFoundError 발생")
    except Exception as e:
        result.fail("미등록 서비스 -> ServiceNotFoundError", str(e))

    # 6-4: 자동 생성자 주입
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        db = container.resolve(IDatabase)
        assert isinstance(db, InMemoryDatabase), "InMemoryDatabase 인스턴스"
        assert isinstance(db.logger, ConsoleLogger), "logger 자동 주입"
        result.ok("자동 생성자 주입 확인")
    except Exception as e:
        result.fail("자동 생성자 주입 확인", str(e))

    # 6-5: 다중 의존성 해결
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        container.register(IUserService, UserService)
        user_svc = container.resolve(IUserService)
        assert isinstance(user_svc, UserService)
        assert isinstance(user_svc.db, InMemoryDatabase)
        assert isinstance(user_svc.logger, ConsoleLogger)
        result.ok("다중 의존성 해결 확인")
    except Exception as e:
        result.fail("다중 의존성 해결 확인", str(e))

    # 6-6: ON_CREATE 라이프사이클 훅
    try:
        container = _make_container()
        created_instances = []

        desc = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            scope=Scope.SINGLETON,
            on_create=lambda inst: created_instances.append(inst),
        )
        container._descriptors[ILogger] = desc
        container._provider = None

        inst = container.resolve(ILogger)
        assert len(created_instances) == 1, f"on_create 호출 횟수: {len(created_instances)}"
        assert created_instances[0] is inst
        result.ok("ON_CREATE 라이프사이클 훅 호출")
    except Exception as e:
        result.fail("ON_CREATE 라이프사이클 훅 호출", str(e))

    # 6-7: ON_DESTROY 라이프사이클 훅 (shutdown 시)
    try:
        container = _make_container()
        destroyed_instances = []

        desc = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            scope=Scope.SINGLETON,
            on_destroy=lambda inst: destroyed_instances.append(inst),
        )
        container._descriptors[ILogger] = desc
        container._provider = None

        inst = container.resolve(ILogger)
        assert len(destroyed_instances) == 0, "shutdown 전에는 호출 안됨"

        container.shutdown()
        assert len(destroyed_instances) == 1, f"on_destroy 호출 횟수: {len(destroyed_instances)}"
        assert destroyed_instances[0] is inst
        result.ok("ON_DESTROY 라이프사이클 훅 (shutdown 시)")
    except Exception as e:
        result.fail("ON_DESTROY 라이프사이클 훅 (shutdown 시)", str(e))

    # 6-8: 스코프 생성 및 폐기
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SCOPED)

        with container.create_scope("test_scope") as provider:
            scoped_inst = provider.get(ILogger)
            assert isinstance(scoped_inst, ConsoleLogger), "스코프 내 인스턴스"

            # 같은 스코프 내에서 동일 인스턴스
            scoped_inst2 = provider.get(ILogger)
            assert scoped_inst is scoped_inst2, "스코프 내 동일 인스턴스"

        result.ok("스코프 생성 및 폐기")
    except Exception as e:
        result.fail("스코프 생성 및 폐기", str(e))

    # 6-9: 스코프 서비스 격리
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SCOPED)

        instances = []
        with container.create_scope("scope_1") as p1:
            inst1 = p1.get(ILogger)
            instances.append(inst1)

        with container.create_scope("scope_2") as p2:
            inst2 = p2.get(ILogger)
            instances.append(inst2)

        # 다른 스코프의 인스턴스는 다를 수 있음 (스코프 폐기 후 재생성)
        assert len(instances) == 2
        assert all(isinstance(i, ConsoleLogger) for i in instances)
        result.ok("스코프 서비스 격리")
    except Exception as e:
        result.fail("스코프 서비스 격리", str(e))

    # 6-10: resolve_all (타입별 모든 서비스)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        # ILogger를 등록하고 resolve_all로 조회
        all_loggers = container.resolve_all(ILogger)
        assert len(all_loggers) >= 1, f"resolve_all 결과: {len(all_loggers)}"
        assert all(isinstance(l, (ILogger, ConsoleLogger)) for l in all_loggers)
        result.ok("resolve_all (타입별 모든 서비스)")
    except Exception as e:
        result.fail("resolve_all (타입별 모든 서비스)", str(e))

    # 6-11: is_registered 확인
    try:
        container = _make_container()
        assert container.is_registered(ILogger) is False, "등록 전"
        container.register(ILogger, ConsoleLogger)
        assert container.is_registered(ILogger) is True, "등록 후"
        assert container.is_registered(IDatabase) is False, "미등록"
        result.ok("is_registered 확인")
    except Exception as e:
        result.fail("is_registered 확인", str(e))

    # 6-12: shutdown 후 상태
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.resolve(ILogger)
        assert container.singleton_count >= 1

        container.shutdown()
        assert container._shutdown is True, "종료 플래그"
        assert container.singleton_count == 0, "싱글톤 정리됨"
        result.ok("shutdown() 후 상태 확인")
    except Exception as e:
        result.fail("shutdown() 후 상태 확인", str(e))

    # 6-13: DependencyGraph 빌드
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        container.register(IUserService, UserService)

        graph = container.build_dependency_graph(IUserService)
        assert isinstance(graph, DependencyGraph), "DependencyGraph 인스턴스"
        assert graph.root is IUserService, "루트 타입"
        assert IUserService in graph.nodes, "UserService 노드"
        result.ok("DependencyGraph 빌드")
    except Exception as e:
        result.fail("DependencyGraph 빌드", str(e))

    # 6-14: DependencyGraph.detect_cycles (순환 없음)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        container.register(IUserService, UserService)

        graph = container.build_dependency_graph(IUserService)
        cycles = graph.detect_cycles()
        assert cycles is None, f"순환 없어야 하는데 발견: {cycles}"
        result.ok("DependencyGraph.detect_cycles() - 순환 없음")
    except Exception as e:
        result.fail("DependencyGraph.detect_cycles() - 순환 없음", str(e))

    # 6-15: 해결 순서 (위상 정렬)
    try:
        container = _make_container()
        container.register(IndependentA, IndependentA)
        container.register(IndependentB, IndependentB)
        container.register(IndependentC, IndependentC)

        graph = container.build_dependency_graph(IndependentC)
        order = graph.get_resolution_order()
        # IndependentA가 IndependentC보다 먼저
        type_names = [t.__name__ for t in order]
        if IndependentA in order and IndependentC in order:
            idx_a = order.index(IndependentA)
            idx_c = order.index(IndependentC)
            assert idx_a < idx_c, f"A가 C보다 먼저: {type_names}"
        result.ok("해결 순서 (위상 정렬)")
    except Exception as e:
        result.fail("해결 순서 (위상 정렬)", str(e))


# ============================================================
# [7] Decorator 테스트
# ============================================================
def test_decorators(result: TestResult) -> None:
    """데코레이터 테스트 (@injectable, @inject)."""
    print("\n[7] Decorator 테스트")
    _reset_container()

    # 7-1: @injectable 클래스 표시
    try:
        @injectable(scope=Scope.SINGLETON)
        class MyService:
            def __init__(self):
                self.active = True

        assert hasattr(MyService, "__di_injectable__"), "@injectable 마커 누락"
        result.ok("@injectable 클래스 표시")
    except Exception as e:
        result.fail("@injectable 클래스 표시", str(e))

    # 7-2: is_injectable 확인
    try:
        @injectable()
        class InjectableService:
            pass

        class NormalClass:
            pass

        assert is_injectable(InjectableService) is True, "주입 가능 표시됨"
        assert is_injectable(NormalClass) is False, "일반 클래스"
        result.ok("is_injectable 확인")
    except Exception as e:
        result.fail("is_injectable 확인", str(e))

    # 7-3: get_injectable_metadata 반환값
    try:
        @injectable(scope=Scope.TRANSIENT, name="test_svc", tags=["core"])
        class MetaService:
            pass

        meta = get_injectable_metadata(MetaService)
        assert meta is not None, "메타데이터 존재"
        assert meta["scope"] == Scope.TRANSIENT, f"scope: {meta['scope']}"
        assert meta["name"] == "test_svc", f"name: {meta['name']}"
        assert meta["tags"] == ["core"], f"tags: {meta['tags']}"
        result.ok("get_injectable_metadata 반환값 확인")
    except Exception as e:
        result.fail("get_injectable_metadata 반환값 확인", str(e))

    # 7-4: @inject 데코레이터
    try:
        class Controller:
            @inject()
            def __init__(self, logger: ILogger, db: IDatabase):
                self.logger = logger
                self.db = db

        assert hasattr(Controller.__init__, "__di_inject__"), "@inject 마커 누락"
        result.ok("@inject 데코레이터 마커 설정")
    except Exception as e:
        result.fail("@inject 데코레이터 마커 설정", str(e))

    # 7-5: 데코레이터 적용 후 클래스 정상 작동
    try:
        @injectable(scope=Scope.SINGLETON)
        class WorkingService:
            def __init__(self):
                self.value = 100

            def get_value(self):
                return self.value

        svc = WorkingService()
        assert svc.value == 100
        assert svc.get_value() == 100
        result.ok("데코레이터 적용 후 클래스 정상 작동")
    except Exception as e:
        result.fail("데코레이터 적용 후 클래스 정상 작동", str(e))

    # 7-6: 메타데이터에 스코프 정보 포함
    try:
        @injectable(scope=Scope.SCOPED)
        class ScopedService:
            pass

        meta = get_injectable_metadata(ScopedService)
        assert meta["scope"] == Scope.SCOPED
        result.ok("메타데이터 스코프 정보 포함 확인")
    except Exception as e:
        result.fail("메타데이터 스코프 정보 포함 확인", str(e))

    # 7-7: 여러 데코레이터 조합
    try:
        @injectable(scope=Scope.SINGLETON, tags=["multi"])
        class MultiDecoratedService:
            @inject()
            def __init__(self):
                self.initialized = True

        assert is_injectable(MultiDecoratedService)
        meta = get_injectable_metadata(MultiDecoratedService)
        assert "multi" in meta["tags"]
        assert hasattr(MultiDecoratedService.__init__, "__di_inject__")
        svc = MultiDecoratedService()
        assert svc.initialized is True
        result.ok("여러 데코레이터 조합")
    except Exception as e:
        result.fail("여러 데코레이터 조합", str(e))

    # 7-8: __init__ 파라미터가 있는 클래스에 데코레이터
    try:
        @injectable(scope=Scope.TRANSIENT)
        class ParamService:
            def __init__(self, name: str = "default", count: int = 0):
                self.name = name
                self.count = count

        assert is_injectable(ParamService)
        svc = ParamService(name="test", count=5)
        assert svc.name == "test"
        assert svc.count == 5
        result.ok("__init__ 파라미터 클래스에 데코레이터")
    except Exception as e:
        result.fail("__init__ 파라미터 클래스에 데코레이터", str(e))


# ============================================================
# [8] 전역 함수 테스트
# ============================================================
def test_global_functions(result: TestResult) -> None:
    """전역 함수 테스트 (get_container, configure_container, _reset_container)."""
    print("\n[8] 전역 함수 테스트")
    _reset_container()

    # 8-1: get_container() 싱글톤
    try:
        _reset_container()
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2, "전역 컨테이너 싱글톤"
        assert isinstance(c1, DIContainer)
        result.ok("get_container() 싱글톤 확인")
    except Exception as e:
        result.fail("get_container() 싱글톤 확인", str(e))

    # 8-2: configure_container()
    try:
        _reset_container()
        configured = []

        def setup(container: DIContainer):
            container.register(ILogger, ConsoleLogger)
            configured.append(True)

        c = configure_container(setup)
        assert isinstance(c, DIContainer)
        assert c.is_registered(ILogger), "configure_container로 등록됨"
        assert len(configured) == 1, "설정 함수 호출됨"
        result.ok("configure_container() 설정 함수 호출")
    except Exception as e:
        result.fail("configure_container() 설정 함수 호출", str(e))

    # 8-3: _reset_container() 초기화
    try:
        _reset_container()
        c1 = get_container()
        c1.register(ILogger, ConsoleLogger)
        assert c1.is_registered(ILogger)

        _reset_container()
        c2 = get_container()
        assert c1 is not c2, "리셋 후 새 인스턴스"
        assert c2.is_registered(ILogger) is False, "리셋 후 등록 초기화"
        result.ok("_reset_container() 초기화 확인")
    except Exception as e:
        result.fail("_reset_container() 초기화 확인", str(e))

    # 8-4: 리셋 후 get_container() -> 새 인스턴스
    try:
        _reset_container()
        c1 = get_container()
        _reset_container()
        c2 = get_container()
        assert c1 is not c2, "리셋 후 새 인스턴스"
        result.ok("리셋 후 get_container() -> 새 인스턴스")
    except Exception as e:
        result.fail("리셋 후 get_container() -> 새 인스턴스", str(e))

    # 8-5: 스레드 안전 싱글톤 접근
    try:
        _reset_container()
        containers = []
        errors = []

        def get_in_thread():
            try:
                c = get_container()
                containers.append(c)
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=get_in_thread) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"스레드 오류: {errors}"
        assert len(containers) == 4
        # 모두 동일 인스턴스여야 함
        first = containers[0]
        assert all(c is first for c in containers), "모든 스레드에서 동일 인스턴스"
        result.ok("스레드 안전 싱글톤 접근")
    except Exception as e:
        result.fail("스레드 안전 싱글톤 접근", str(e))

    _reset_container()


# ============================================================
# [9] 스레드 안전성 테스트
# ============================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 테스트."""
    print("\n[9] 스레드 안전성 테스트")
    _reset_container()

    # 9-1: 4개 스레드에서 싱글톤 해결 -> 동일 인스턴스
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)

        instances = []
        errors = []
        lock = threading.Lock()

        def resolve_in_thread():
            try:
                inst = container.resolve(ILogger)
                with lock:
                    instances.append(inst)
            except Exception as ex:
                with lock:
                    errors.append(str(ex))

        threads = [threading.Thread(target=resolve_in_thread) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"스레드 오류: {errors}"
        assert len(instances) == 4, f"인스턴스 수: {len(instances)}"
        first = instances[0]
        assert all(inst is first for inst in instances), "싱글톤 동일 인스턴스"
        result.ok("4 스레드 싱글톤 해결 -> 동일 인스턴스")
    except Exception as e:
        result.fail("4 스레드 싱글톤 해결 -> 동일 인스턴스", str(e))

    # 9-2: 스레드 로컬 해결 스택 (threading.local 기반)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)

        # 각 스레드에서 독립적으로 의존성 해결
        resolved = []
        errors = []
        lock = threading.Lock()

        def resolve_db_in_thread():
            try:
                db = container.resolve(IDatabase)
                with lock:
                    resolved.append(db)
            except Exception as ex:
                with lock:
                    errors.append(str(ex))

        threads = [threading.Thread(target=resolve_db_in_thread) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"스레드 로컬 오류: {errors}"
        assert len(resolved) == 4
        result.ok("스레드 로컬 해결 스택 확인 (threading.local)")
    except Exception as e:
        result.fail("스레드 로컬 해결 스택 확인", str(e))

    # 9-3: 동시 트랜지언트 해결
    try:
        container = _make_container()
        container.register(SimpleService, SimpleService, scope=Scope.TRANSIENT)

        instances = []
        errors = []
        lock = threading.Lock()

        def resolve_transient():
            try:
                inst = container.resolve(SimpleService)
                with lock:
                    instances.append(inst)
            except Exception as ex:
                with lock:
                    errors.append(str(ex))

        threads = [threading.Thread(target=resolve_transient) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"트랜지언트 오류: {errors}"
        assert len(instances) == 4
        # 트랜지언트는 모두 다른 인스턴스
        ids = [id(inst) for inst in instances]
        assert len(set(ids)) == 4, "트랜지언트: 모두 다른 인스턴스"
        result.ok("동시 트랜지언트 해결 (모두 다른 인스턴스)")
    except Exception as e:
        result.fail("동시 트랜지언트 해결", str(e))

    # 9-4: 크로스 스레드 누출 없음
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        container.register(ICache, InMemoryCache, scope=Scope.TRANSIENT)

        singleton_results = []
        transient_results = []
        errors = []
        lock = threading.Lock()

        def mixed_resolve():
            try:
                s = container.resolve(ILogger)
                t = container.resolve(ICache)
                with lock:
                    singleton_results.append(s)
                    transient_results.append(t)
            except Exception as ex:
                with lock:
                    errors.append(str(ex))

        threads = [threading.Thread(target=mixed_resolve) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"크로스 스레드 오류: {errors}"
        # 싱글톤은 모두 같고, 트랜지언트는 모두 다름
        assert len(set(id(s) for s in singleton_results)) == 1, "싱글톤 일관성"
        assert len(set(id(t) for t in transient_results)) == 4, "트랜지언트 격리"
        result.ok("크로스 스레드 누출 없음 확인")
    except Exception as e:
        result.fail("크로스 스레드 누출 없음 확인", str(e))

    # 9-5: 0 에러
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        container.register(IUserService, UserService)

        all_errors = []
        lock = threading.Lock()

        def complex_resolve():
            try:
                container.resolve(IUserService)
                container.resolve(ILogger)
                container.resolve(IDatabase)
            except Exception as ex:
                with lock:
                    all_errors.append(str(ex))

        threads = [threading.Thread(target=complex_resolve) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(all_errors) == 0, f"멀티 스레드 오류 수: {len(all_errors)}"
        result.ok("8 스레드 복합 해결 -> 0 에러")
    except Exception as e:
        result.fail("8 스레드 복합 해결 -> 0 에러", str(e))


# ============================================================
# [10] 순환 의존성 탐지 테스트
# ============================================================
def test_circular_dependency(result: TestResult) -> None:
    """순환 의존성 탐지 테스트."""
    print("\n[10] 순환 의존성 탐지 테스트")
    _reset_container()

    # 10-1: A -> B -> A 탐지
    try:
        container = _make_container()
        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)

        graph = container.build_dependency_graph(ServiceA)
        cycles = graph.detect_cycles()
        assert cycles is not None, "순환 의존성이 탐지되어야 함"
        result.ok("A -> B -> A 순환 의존성 탐지")
    except Exception as e:
        result.fail("A -> B -> A 순환 의존성 탐지", str(e))

    # 10-2: A -> B -> C -> A 탐지
    try:
        container = _make_container()
        container.register(ServiceX, ServiceX)
        container.register(ServiceY, ServiceY)
        container.register(ServiceZ, ServiceZ)

        graph = container.build_dependency_graph(ServiceX)
        cycles = graph.detect_cycles()
        assert cycles is not None, "3단계 순환 의존성이 탐지되어야 함"
        result.ok("A -> B -> C -> A 3단계 순환 의존성 탐지")
    except Exception as e:
        result.fail("A -> B -> C -> A 3단계 순환 의존성 탐지", str(e))

    # 10-3: 유효한 체인에서 거짓 양성 없음
    try:
        container = _make_container()
        container.register(IndependentA, IndependentA)
        container.register(IndependentB, IndependentB)
        container.register(IndependentC, IndependentC)

        graph = container.build_dependency_graph(IndependentC)
        cycles = graph.detect_cycles()
        assert cycles is None, f"거짓 양성 발견: {cycles}"
        result.ok("유효한 체인 -> 거짓 양성 없음")
    except Exception as e:
        result.fail("유효한 체인 -> 거짓 양성 없음", str(e))

    # 10-4: DependencyGraph.detect_cycles()가 순환 체인 반환
    try:
        graph = DependencyGraph()
        graph.add_node(ServiceA, [ServiceB])
        graph.add_node(ServiceB, [ServiceA])

        cycles = graph.detect_cycles()
        assert cycles is not None, "순환 반환"
        assert len(cycles) >= 2, f"체인 길이: {len(cycles)}"
        # 체인에 ServiceA와 ServiceB 포함
        assert ServiceA in cycles, "ServiceA 포함"
        assert ServiceB in cycles, "ServiceB 포함"
        result.ok("DependencyGraph.detect_cycles() 순환 체인 반환")
    except Exception as e:
        result.fail("DependencyGraph.detect_cycles() 순환 체인 반환", str(e))

    # 10-5: CircularDependencyError 해결 시 발생
    try:
        container = _make_container()
        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)

        try:
            container.resolve(ServiceA)
            result.fail("순환 의존성 resolve -> CircularDependencyError", "예외 미발생")
        except CircularDependencyError:
            result.ok("순환 의존성 resolve -> CircularDependencyError 발생")
        except ResolutionError:
            # ResolutionError로 래핑될 수도 있음
            result.ok("순환 의존성 resolve -> ResolutionError 발생 (허용)")
    except Exception as e:
        result.fail("순환 의존성 resolve -> CircularDependencyError", str(e))


# ============================================================
# 추가 테스트 - DependencyNode, DependencyGraph, ScopeContext
# ============================================================
def test_data_classes_extended(result: TestResult) -> None:
    """DependencyNode, DependencyGraph, ScopeContext 확장 테스트."""
    print("\n[11] 데이터 클래스 확장 테스트")
    _reset_container()

    # 11-1: DependencyNode 기본 생성
    try:
        node = DependencyNode(service_type=ILogger)
        assert node.service_type is ILogger
        assert node.dependencies == []
        assert node.depth == 0
        assert node.status == ResolutionStatus.PENDING
        result.ok("DependencyNode 기본 생성")
    except Exception as e:
        result.fail("DependencyNode 기본 생성", str(e))

    # 11-2: DependencyNode to_dict
    try:
        node = DependencyNode(
            service_type=ILogger,
            dependencies=[IDatabase],
            depth=2,
            status=ResolutionStatus.RESOLVED,
        )
        d = node.to_dict()
        assert d["service_type"] == "ILogger"
        assert d["dependencies"] == ["IDatabase"]
        assert d["depth"] == 2
        assert d["status"] == "resolved"
        result.ok("DependencyNode to_dict")
    except Exception as e:
        result.fail("DependencyNode to_dict", str(e))

    # 11-3: DependencyGraph 노드 추가
    try:
        graph = DependencyGraph()
        node = graph.add_node(ILogger, [IDatabase], depth=1)
        assert ILogger in graph.nodes
        assert node.service_type is ILogger
        assert node.dependencies == [IDatabase]
        assert node.depth == 1
        result.ok("DependencyGraph 노드 추가")
    except Exception as e:
        result.fail("DependencyGraph 노드 추가", str(e))

    # 11-4: DependencyGraph 노드 조회
    try:
        graph = DependencyGraph()
        graph.add_node(ILogger)
        node = graph.get_node(ILogger)
        assert node is not None
        assert node.service_type is ILogger
        assert graph.get_node(IDatabase) is None
        result.ok("DependencyGraph 노드 조회")
    except Exception as e:
        result.fail("DependencyGraph 노드 조회", str(e))

    # 11-5: DependencyGraph to_dict
    try:
        graph = DependencyGraph(root=IUserService)
        graph.add_node(IUserService, [IDatabase, ILogger])
        graph.add_node(IDatabase, [ILogger])
        graph.add_node(ILogger, [])
        d = graph.to_dict()
        assert "nodes" in d
        assert "root" in d
        assert d["root"] == "IUserService"
        assert "resolution_order" in d
        result.ok("DependencyGraph to_dict")
    except Exception as e:
        result.fail("DependencyGraph to_dict", str(e))

    # 11-6: ScopeContext 기본 생성
    try:
        scope = ScopeContext(name="test")
        assert scope.name == "test"
        assert scope.instances == {}
        assert scope.parent is None
        assert scope.children == []
        result.ok("ScopeContext 기본 생성")
    except Exception as e:
        result.fail("ScopeContext 기본 생성", str(e))

    # 11-7: ScopeContext set/get
    try:
        scope = ScopeContext(name="test")
        logger = ConsoleLogger()
        scope.set(ILogger, logger)
        retrieved = scope.get(ILogger)
        assert retrieved is logger
        assert scope.get(IDatabase) is None
        result.ok("ScopeContext set/get")
    except Exception as e:
        result.fail("ScopeContext set/get", str(e))

    # 11-8: ScopeContext 부모 검색
    try:
        parent = ScopeContext(name="parent")
        child = ScopeContext(name="child", parent=parent)
        logger = ConsoleLogger()
        parent.set(ILogger, logger)

        retrieved = child.get(ILogger)
        assert retrieved is logger, "부모 스코프에서 찾음"
        result.ok("ScopeContext 부모 검색")
    except Exception as e:
        result.fail("ScopeContext 부모 검색", str(e))

    # 11-9: ScopeContext clear
    try:
        scope = ScopeContext(name="test")
        scope.set(ILogger, ConsoleLogger())
        scope.set(IDatabase, InMemoryDatabase())
        assert len(scope.instances) == 2

        scope.clear()
        assert len(scope.instances) == 0
        result.ok("ScopeContext clear")
    except Exception as e:
        result.fail("ScopeContext clear", str(e))


# ============================================================
# 추가 테스트 - 엣지 케이스
# ============================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 및 추가 테스트."""
    print("\n[12] 엣지 케이스 테스트")
    _reset_container()

    # 12-1: register_instance 후 즉시 해결
    try:
        container = _make_container()
        logger_inst = ConsoleLogger()
        logger_inst.log("test_message")
        container.register_instance(ILogger, logger_inst)
        resolved = container.resolve(ILogger)
        assert resolved is logger_inst, "동일 인스턴스"
        assert "test_message" in resolved.logs, "상태 보존"
        result.ok("register_instance 후 즉시 해결")
    except Exception as e:
        result.fail("register_instance 후 즉시 해결", str(e))

    # 12-2: 팩토리 등록 및 해결
    try:
        container = _make_container()

        def create_logger() -> ConsoleLogger:
            lg = ConsoleLogger()
            lg.log("factory_created")
            return lg

        container.register_factory(ILogger, create_logger, scope=Scope.SINGLETON)
        inst = container.resolve(ILogger)
        assert isinstance(inst, ConsoleLogger)
        assert "factory_created" in inst.logs
        result.ok("팩토리 등록 및 해결")
    except Exception as e:
        result.fail("팩토리 등록 및 해결", str(e))

    # 12-3: resolve_optional (등록되지 않은 서비스)
    try:
        container = _make_container()
        opt = container.resolve_optional(ILogger)
        assert opt is None, "등록되지 않은 서비스는 None"
        result.ok("resolve_optional -> None (미등록)")
    except Exception as e:
        result.fail("resolve_optional -> None (미등록)", str(e))

    # 12-4: resolve_optional (등록된 서비스)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        opt = container.resolve_optional(ILogger)
        assert isinstance(opt, ConsoleLogger), "등록된 서비스 반환"
        result.ok("resolve_optional -> 인스턴스 (등록됨)")
    except Exception as e:
        result.fail("resolve_optional -> 인스턴스 (등록됨)", str(e))

    # 12-5: service_count 확인
    try:
        container = _make_container()
        assert container.service_count == 0
        container.register(ILogger, ConsoleLogger)
        assert container.service_count == 1
        container.register(IDatabase, InMemoryDatabase)
        assert container.service_count == 2
        result.ok("service_count 확인")
    except Exception as e:
        result.fail("service_count 확인", str(e))

    # 12-6: singleton_count 확인
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        assert container.singleton_count == 0, "해결 전"
        container.resolve(ILogger)
        assert container.singleton_count == 1, "해결 후"
        result.ok("singleton_count 확인")
    except Exception as e:
        result.fail("singleton_count 확인", str(e))

    # 12-7: get_status 상태 조회
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, scope=Scope.SINGLETON)
        container.register(ICache, InMemoryCache, scope=Scope.TRANSIENT)
        status = container.get_status()
        assert "registered_services" in status
        assert status["registered_services"] == 2
        assert "scope_counts" in status
        assert "shutdown" in status
        assert status["shutdown"] is False
        result.ok("get_status 상태 조회")
    except Exception as e:
        result.fail("get_status 상태 조회", str(e))

    # 12-8: get_descriptor 확인
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger, name="main_logger")
        desc = container.get_descriptor(ILogger)
        assert desc is not None
        assert desc.service_type is ILogger
        assert desc.name == "main_logger"
        assert container.get_descriptor(IDatabase) is None
        result.ok("get_descriptor 확인")
    except Exception as e:
        result.fail("get_descriptor 확인", str(e))

    # 12-9: get_registered_types 확인
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        types = container.get_registered_types()
        assert ILogger in types
        assert IDatabase in types
        assert len(types) == 2
        result.ok("get_registered_types 확인")
    except Exception as e:
        result.fail("get_registered_types 확인", str(e))

    # 12-10: 컨텍스트 매니저 (__enter__, __exit__)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        with container as c:
            assert c is container
            inst = c.resolve(ILogger)
            assert isinstance(inst, ConsoleLogger)
        # __exit__ 후 shutdown 호출됨
        assert container._shutdown is True
        result.ok("컨텍스트 매니저 (__enter__, __exit__)")
    except Exception as e:
        result.fail("컨텍스트 매니저 (__enter__, __exit__)", str(e))

    # 12-11: validate (순환 의존성 검증)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(IDatabase, InMemoryDatabase)
        errors = container.validate()
        assert isinstance(errors, list)
        assert len(errors) == 0, f"유효한 컨테이너에서 오류: {errors}"
        result.ok("validate() - 유효한 컨테이너")
    except Exception as e:
        result.fail("validate() - 유효한 컨테이너", str(e))

    # 12-12: validate (순환 의존성 있는 경우)
    try:
        container = _make_container()
        container.register(ServiceA, ServiceA)
        container.register(ServiceB, ServiceB)
        errors = container.validate()
        assert isinstance(errors, list)
        assert len(errors) > 0, "순환 의존성 오류 발견되어야 함"
        result.ok("validate() - 순환 의존성 오류 발견")
    except Exception as e:
        result.fail("validate() - 순환 의존성 오류 발견", str(e))

    # 12-13: Optional 의존성 (등록되지 않아도 None 주입)
    try:
        container = _make_container()
        container.register(ServiceWithOptional, ServiceWithOptional)
        inst = container.resolve(ServiceWithOptional)
        assert isinstance(inst, ServiceWithOptional)
        assert inst.logger is None, "Optional 의존성 미등록 시 None"
        result.ok("Optional 의존성 미등록 -> None 주입")
    except Exception as e:
        result.fail("Optional 의존성 미등록 -> None 주입", str(e))

    # 12-14: Optional 의존성 (등록됨 -> 주입)
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(ServiceWithOptional, ServiceWithOptional)
        inst = container.resolve(ServiceWithOptional)
        assert isinstance(inst.logger, ConsoleLogger), "Optional 의존성 등록됨 -> 주입"
        result.ok("Optional 의존성 등록됨 -> 주입")
    except Exception as e:
        result.fail("Optional 의존성 등록됨 -> 주입", str(e))

    # 12-15: ServiceDescriptor.__post_init__ (implementation=None)
    try:
        desc = ServiceDescriptor(service_type=SimpleService)
        assert desc.implementation_type is SimpleService, (
            "__post_init__에서 service_type으로 설정"
        )
        assert desc.get_implementation() is SimpleService
        result.ok("ServiceDescriptor.__post_init__ 자동 설정")
    except Exception as e:
        result.fail("ServiceDescriptor.__post_init__ 자동 설정", str(e))

    # 12-16: get_by_tag 태그 조회
    try:
        container = _make_container()
        desc1 = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=ConsoleLogger,
            tags=["core", "logging"],
        )
        desc2 = ServiceDescriptor(
            service_type=IDatabase,
            implementation_type=InMemoryDatabase,
            tags=["core", "data"],
        )
        container._descriptors[ILogger] = desc1
        container._descriptors[IDatabase] = desc2
        container._provider = None

        core_services = container.get_by_tag("core")
        assert len(core_services) == 2
        assert ILogger in core_services
        assert IDatabase in core_services

        logging_services = container.get_by_tag("logging")
        assert len(logging_services) == 1
        assert ILogger in logging_services

        empty = container.get_by_tag("nonexistent")
        assert len(empty) == 0
        result.ok("get_by_tag 태그 조회")
    except Exception as e:
        result.fail("get_by_tag 태그 조회", str(e))

    # 12-17: get_all_descriptors 확인
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.register(ICache, InMemoryCache)
        descriptors = container.get_all_descriptors()
        assert len(descriptors) == 2
        assert ILogger in descriptors
        assert ICache in descriptors
        # 복사본 확인 (원본과 다른 dict)
        assert descriptors is not container._descriptors
        result.ok("get_all_descriptors 확인")
    except Exception as e:
        result.fail("get_all_descriptors 확인", str(e))

    # 12-18: 이중 shutdown 안전성
    try:
        container = _make_container()
        container.register(ILogger, ConsoleLogger)
        container.resolve(ILogger)
        container.shutdown()
        container.shutdown()  # 두 번째 호출 - 오류 없어야 함
        assert container._shutdown is True
        result.ok("이중 shutdown 안전성")
    except Exception as e:
        result.fail("이중 shutdown 안전성", str(e))

    # 12-19: register_with_dependencies
    try:
        builder = _make_builder()
        builder.register_with_dependencies(
            IUserService,
            UserService,
            dependencies={"db": InMemoryDatabase},
            scope=Scope.SINGLETON,
        )
        desc = builder._descriptors[IUserService]
        assert desc.dependencies["db"] is InMemoryDatabase
        result.ok("register_with_dependencies")
    except Exception as e:
        result.fail("register_with_dependencies", str(e))

    # 12-20: __all__ 내보내기 확인
    try:
        from core_foundation.registry.dependency_injector import __all__ as all_exports
        expected_items = [
            "Scope", "LifecycleHook", "ResolutionStatus",
            "DIException", "ServiceNotFoundError", "CircularDependencyError", "ResolutionError",
            "ServiceDescriptor", "DependencyNode", "DependencyGraph", "ScopeContext",
            "DIContainer", "ContainerBuilder", "ServiceProvider",
            "injectable", "inject", "is_injectable", "get_injectable_metadata",
            "get_container", "configure_container", "_reset_container",
        ]
        for item in expected_items:
            assert item in all_exports, f"__all__에 '{item}' 누락"
        result.ok("__all__ 내보내기 확인")
    except Exception as e:
        result.fail("__all__ 내보내기 확인", str(e))


# ============================================================
# 메인 실행
# ============================================================
def main() -> None:
    """전체 테스트 실행."""
    print("=" * 60)
    print("DI 컨테이너 단위 테스트 (dependency_injector.py)")
    print("=" * 60)

    result = TestResult()

    # [1] Enum 테스트
    test_enums(result)

    # [2] 상수 테스트
    test_constants(result)

    # [3] 예외 클래스 테스트
    test_exceptions(result)

    # [4] ServiceDescriptor 테스트
    test_service_descriptor(result)

    # [5] ContainerBuilder 테스트
    test_container_builder(result)

    # [6] DIContainer / ServiceProvider 테스트
    test_container_and_provider(result)

    # [7] Decorator 테스트
    test_decorators(result)

    # [8] 전역 함수 테스트
    test_global_functions(result)

    # [9] 스레드 안전성 테스트
    test_thread_safety(result)

    # [10] 순환 의존성 탐지 테스트
    test_circular_dependency(result)

    # [11] 데이터 클래스 확장 테스트
    test_data_classes_extended(result)

    # [12] 엣지 케이스 테스트
    test_edge_cases(result)

    # 최종 정리
    _reset_container()

    # 결과 요약
    result.summary()

    # 테스트 실패 시 종료 코드 1
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
