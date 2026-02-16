# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/performance
파일: test_dependency_injector_perf.py
설명: DI 컨테이너 (dependency_injector) 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [P1] Enum 연산 성능 (3개) - Scope/LifecycleHook/ResolutionStatus 순회, 비교
    [P2] ServiceDescriptor 생성 성능 (3개) - 스코프별 생성, 팩토리 패턴
    [P3] ContainerBuilder 등록 성능 (4개) - register, register_instance, register_factory, 체이닝
    [P4] DIContainer 서비스 해결 성능 (4개) - 싱글톤 해결, 트랜지언트 해결, 반복 해결, 팩토리 해결
    [P5] DependencyGraph 성능 (3개) - 그래프 빌드, 순환 탐지, 해결 순서
    [P6] 데코레이터 성능 (3개) - injectable 적용, is_injectable 확인, get_injectable_metadata
    [P7] 멀티스레드 동시 접근 (3개) - 싱글톤 동시 해결, 트랜지언트 동시 해결, 혼합 연산
    [P8] 메모리 사용량 (3개) - 컨테이너 인스턴스, 100개 등록, 스코프 컨텍스트

    총 26개 테스트

실행 방법:
    set PYTHONIOENCODING=utf-8 && python -m tests.core_foundation.registry.performance.test_dependency_injector_perf
"""

import gc
import sys
import threading
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

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


# =============================================================================
# 테스트용 서비스 클래스 정의
# =============================================================================
class ServiceA:
    """테스트용 기본 서비스 A."""
    pass


class ServiceB:
    """테스트용 서비스 B - ServiceA 의존."""

    def __init__(self, a: ServiceA) -> None:
        self.a = a


class ServiceC:
    """테스트용 서비스 C - ServiceB 의존."""

    def __init__(self, b: ServiceB) -> None:
        self.b = b


class ServiceD:
    """테스트용 서비스 D - ServiceA, ServiceB 의존."""

    def __init__(self, a: ServiceA, b: ServiceB) -> None:
        self.a = a
        self.b = b


class SimpleService:
    """테스트용 단순 서비스 (의존성 없음)."""
    pass


class FactoryCreatedService:
    """팩토리로 생성되는 서비스."""

    def __init__(self, value: int = 0) -> None:
        self.value = value


class ScopedService:
    """스코프용 테스트 서비스."""
    pass


# 순환 의존성 테스트용
class CycleA:
    """순환 테스트 A -> B."""

    def __init__(self, b: "CycleB") -> None:
        self.b = b


class CycleB:
    """순환 테스트 B -> C."""

    def __init__(self, c: "CycleC") -> None:
        self.c = c


class CycleC:
    """순환 테스트 C -> A (순환)."""

    def __init__(self, a: CycleA) -> None:
        self.a = a


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        """테스트 통과."""
        self.passed += 1
        line = f"  [PASS] {test_name}"
        if metric:
            line += f"  |  {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(line)

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n주요 성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼 함수
# =============================================================================
def measure_ops(func, iterations: int = 10000) -> float:
    """초당 연산 수 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


def measure_time_ms(func, iterations: int = 1000) -> float:
    """평균 실행 시간 (밀리초) 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000


def get_object_size(obj) -> int:
    """객체 대략적 메모리 크기 (바이트) 측정."""
    return sys.getsizeof(obj)


def _make_container_with_services() -> DIContainer:
    """테스트용 DIContainer 생성 (서비스 등록 포함)."""
    builder = ContainerBuilder()
    builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)
    builder.register(ServiceB, ServiceB, scope=Scope.SINGLETON)
    builder.register(SimpleService, SimpleService, scope=Scope.TRANSIENT)
    container = builder.build()
    return container


# =============================================================================
# [P1] Enum 연산 성능 (3개)
# =============================================================================
def test_p1_enum_perf(result: PerformanceTestResult) -> None:
    """Enum 연산 성능 테스트."""
    print("\n[P1] Enum 연산 성능")

    # P1-1. Scope/LifecycleHook/ResolutionStatus 순회 처리량
    try:
        def iterate_all_enums():
            for _ in Scope:
                pass
            for _ in LifecycleHook:
                pass
            for _ in ResolutionStatus:
                pass

        ops = measure_ops(iterate_all_enums, iterations=50000)
        assert ops > 50000, f"Enum 순회: {ops:.0f} ops/sec < 50000"
        result.ok("P1-1 Enum 전체 순회", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-1 Enum 전체 순회", str(e))

    # P1-2. Scope 값 비교 처리량
    try:
        s1 = Scope.SINGLETON
        s2 = Scope.TRANSIENT

        def compare_scope():
            _ = s1 == Scope.SINGLETON
            _ = s2 != Scope.SINGLETON
            _ = s1.is_cached

        ops = measure_ops(compare_scope, iterations=100000)
        assert ops > 100000, f"Scope 비교: {ops:.0f} ops/sec < 100000"
        result.ok("P1-2 Scope 값 비교 / is_cached", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-2 Scope 값 비교", str(e))

    # P1-3. ResolutionStatus 문자열 변환 처리량
    try:
        statuses = list(ResolutionStatus)

        def status_value_access():
            for s in statuses:
                _ = s.value
                _ = s.name

        ops = measure_ops(status_value_access, iterations=50000)
        assert ops > 50000, f"ResolutionStatus 변환: {ops:.0f} ops/sec < 50000"
        result.ok("P1-3 ResolutionStatus value/name 접근", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-3 ResolutionStatus 변환", str(e))


# =============================================================================
# [P2] ServiceDescriptor 생성 성능 (3개)
# =============================================================================
def test_p2_service_descriptor_perf(result: PerformanceTestResult) -> None:
    """ServiceDescriptor 생성 성능 테스트."""
    print("\n[P2] ServiceDescriptor 생성 성능")

    # P2-1. 기본 ServiceDescriptor 생성 (각 스코프별)
    try:
        def create_descriptors():
            _ = ServiceDescriptor(service_type=ServiceA, scope=Scope.SINGLETON)
            _ = ServiceDescriptor(service_type=ServiceA, scope=Scope.TRANSIENT)
            _ = ServiceDescriptor(service_type=ServiceA, scope=Scope.SCOPED)

        ops = measure_ops(create_descriptors, iterations=30000)
        assert ops > 10000, f"ServiceDescriptor 생성: {ops:.0f} ops/sec < 10000"
        result.ok("P2-1 ServiceDescriptor 스코프별 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-1 ServiceDescriptor 생성", str(e))

    # P2-2. ServiceDescriptor 팩토리 패턴 생성
    try:
        factory_fn = lambda: FactoryCreatedService(value=42)

        def create_factory_descriptor():
            _ = ServiceDescriptor(
                service_type=FactoryCreatedService,
                factory=factory_fn,
                scope=Scope.TRANSIENT,
                name="factory_service",
                tags=["test", "factory"],
            )

        ops = measure_ops(create_factory_descriptor, iterations=30000)
        assert ops > 10000, f"팩토리 ServiceDescriptor: {ops:.0f} ops/sec < 10000"
        result.ok("P2-2 ServiceDescriptor 팩토리 패턴 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-2 ServiceDescriptor 팩토리", str(e))

    # P2-3. ServiceDescriptor to_dict 직렬화
    try:
        desc = ServiceDescriptor(
            service_type=ServiceA,
            implementation_type=ServiceA,
            scope=Scope.SINGLETON,
            name="test_a",
            tags=["core", "test"],
        )

        ops = measure_ops(lambda: desc.to_dict(), iterations=50000)
        assert ops > 30000, f"to_dict: {ops:.0f} ops/sec < 30000"
        result.ok("P2-3 ServiceDescriptor to_dict 직렬화", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-3 to_dict 직렬화", str(e))


# =============================================================================
# [P3] ContainerBuilder 등록 성능 (4개)
# =============================================================================
def test_p3_container_builder_perf(result: PerformanceTestResult) -> None:
    """ContainerBuilder 등록 성능 테스트."""
    print("\n[P3] ContainerBuilder 등록 성능")

    # P3-1. register (싱글톤) 처리량
    try:
        def register_singleton():
            builder = ContainerBuilder()
            builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)

        ops = measure_ops(register_singleton, iterations=10000)
        assert ops > 5000, f"register singleton: {ops:.0f} ops/sec < 5000"
        result.ok("P3-1 register 싱글톤", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-1 register 싱글톤", str(e))

    # P3-2. register_instance 처리량
    try:
        instance_a = ServiceA()

        def register_inst():
            builder = ContainerBuilder()
            builder.register_instance(ServiceA, instance_a)

        ops = measure_ops(register_inst, iterations=10000)
        assert ops > 5000, f"register_instance: {ops:.0f} ops/sec < 5000"
        result.ok("P3-2 register_instance", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-2 register_instance", str(e))

    # P3-3. register_factory 처리량
    try:
        factory_fn = lambda: FactoryCreatedService(value=99)

        def register_fact():
            builder = ContainerBuilder()
            builder.register_factory(FactoryCreatedService, factory_fn, scope=Scope.TRANSIENT)

        ops = measure_ops(register_fact, iterations=10000)
        assert ops > 5000, f"register_factory: {ops:.0f} ops/sec < 5000"
        result.ok("P3-3 register_factory", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-3 register_factory", str(e))

    # P3-4. 체이닝 등록 (5개 서비스 연속 등록) 처리량
    try:
        def chained_register():
            builder = ContainerBuilder()
            (
                builder
                .register(ServiceA, ServiceA, scope=Scope.SINGLETON)
                .register(ServiceB, ServiceB, scope=Scope.SINGLETON)
                .register(ServiceC, ServiceC, scope=Scope.SINGLETON)
                .register(SimpleService, SimpleService, scope=Scope.TRANSIENT)
                .register_factory(
                    FactoryCreatedService,
                    lambda: FactoryCreatedService(value=1),
                    scope=Scope.TRANSIENT,
                )
            )

        ops = measure_ops(chained_register, iterations=5000)
        assert ops > 2000, f"체이닝 5개: {ops:.0f} ops/sec < 2000"
        result.ok("P3-4 체이닝 등록 (5개 서비스)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-4 체이닝 등록", str(e))


# =============================================================================
# [P4] DIContainer 서비스 해결 성능 (4개)
# =============================================================================
def test_p4_container_resolve_perf(result: PerformanceTestResult) -> None:
    """DIContainer 서비스 해결 성능 테스트."""
    print("\n[P4] DIContainer 서비스 해결 성능")

    # P4-1. 싱글톤 서비스 해결 처리량 (첫 번째 해결 후 캐시 히트)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)
        container = builder.build()
        # 첫 번째 해결로 싱글톤 캐시 생성
        _ = container.resolve(ServiceA)

        ops = measure_ops(lambda: container.resolve(ServiceA), iterations=50000)
        assert ops > 30000, f"싱글톤 해결 (캐시 히트): {ops:.0f} ops/sec < 30000"
        result.ok("P4-1 싱글톤 해결 (캐시 히트)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-1 싱글톤 해결", str(e))

    # P4-2. 트랜지언트 서비스 해결 처리량 (매번 새 인스턴스)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(SimpleService, SimpleService, scope=Scope.TRANSIENT)
        container = builder.build()

        ops = measure_ops(lambda: container.resolve(SimpleService), iterations=10000)
        assert ops > 3000, f"트랜지언트 해결: {ops:.0f} ops/sec < 3000"
        result.ok("P4-2 트랜지언트 해결 (매번 새 인스턴스)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-2 트랜지언트 해결", str(e))

    # P4-3. 반복 해결 (의존성 체인: C -> B -> A)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)
        builder.register(ServiceB, ServiceB, scope=Scope.SINGLETON)
        builder.register(ServiceC, ServiceC, scope=Scope.SINGLETON)
        container = builder.build()
        # 첫 해결로 전체 체인 캐시
        _ = container.resolve(ServiceC)

        ops = measure_ops(lambda: container.resolve(ServiceC), iterations=50000)
        assert ops > 20000, f"의존성 체인 해결: {ops:.0f} ops/sec < 20000"
        result.ok("P4-3 의존성 체인 해결 (C->B->A, 캐시)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-3 의존성 체인 해결", str(e))

    # P4-4. 팩토리 서비스 해결 처리량
    try:
        _reset_container()
        counter = [0]

        def factory_fn():
            counter[0] += 1
            return FactoryCreatedService(value=counter[0])

        builder = ContainerBuilder()
        builder.register_factory(FactoryCreatedService, factory_fn, scope=Scope.TRANSIENT)
        container = builder.build()

        ops = measure_ops(lambda: container.resolve(FactoryCreatedService), iterations=10000)
        assert ops > 3000, f"팩토리 해결: {ops:.0f} ops/sec < 3000"
        result.ok("P4-4 팩토리 서비스 해결 (트랜지언트)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-4 팩토리 서비스 해결", str(e))


# =============================================================================
# [P5] DependencyGraph 성능 (3개)
# =============================================================================
def test_p5_dependency_graph_perf(result: PerformanceTestResult) -> None:
    """DependencyGraph 성능 테스트."""
    print("\n[P5] DependencyGraph 성능")

    # P5-1. 그래프 빌드 처리량 (노드 추가)
    try:
        def build_graph():
            graph = DependencyGraph()
            graph.add_node(ServiceA, [], depth=0)
            graph.add_node(ServiceB, [ServiceA], depth=1)
            graph.add_node(ServiceC, [ServiceB], depth=2)
            graph.add_node(ServiceD, [ServiceA, ServiceB], depth=2)
            graph.add_node(SimpleService, [], depth=0)

        ops = measure_ops(build_graph, iterations=20000)
        assert ops > 10000, f"그래프 빌드: {ops:.0f} ops/sec < 10000"
        result.ok("P5-1 DependencyGraph 빌드 (5노드)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-1 그래프 빌드", str(e))

    # P5-2. 순환 의존성 탐지 처리량
    try:
        # 순환 없는 그래프
        graph_no_cycle = DependencyGraph()
        graph_no_cycle.add_node(ServiceA, [], depth=0)
        graph_no_cycle.add_node(ServiceB, [ServiceA], depth=1)
        graph_no_cycle.add_node(ServiceC, [ServiceB], depth=2)
        graph_no_cycle.add_node(ServiceD, [ServiceA, ServiceB], depth=2)
        graph_no_cycle.add_node(SimpleService, [], depth=0)

        ops = measure_ops(lambda: graph_no_cycle.detect_cycles(), iterations=20000)
        assert ops > 10000, f"순환 탐지 (정상): {ops:.0f} ops/sec < 10000"
        result.ok("P5-2 순환 탐지 (순환 없는 5노드)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-2 순환 탐지", str(e))

    # P5-3. 해결 순서 (위상 정렬) 처리량
    try:
        graph = DependencyGraph()
        graph.add_node(ServiceA, [], depth=0)
        graph.add_node(ServiceB, [ServiceA], depth=1)
        graph.add_node(ServiceC, [ServiceB], depth=2)
        graph.add_node(ServiceD, [ServiceA, ServiceB], depth=2)

        ops = measure_ops(lambda: graph.get_resolution_order(), iterations=20000)
        assert ops > 10000, f"해결 순서: {ops:.0f} ops/sec < 10000"

        # 순서 정확성 검증
        order = graph.get_resolution_order()
        a_idx = order.index(ServiceA)
        b_idx = order.index(ServiceB)
        c_idx = order.index(ServiceC)
        assert a_idx < b_idx < c_idx, f"순서 부정확: A={a_idx}, B={b_idx}, C={c_idx}"

        result.ok("P5-3 해결 순서 (위상 정렬 4노드)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-3 해결 순서", str(e))


# =============================================================================
# [P6] 데코레이터 성능 (3개)
# =============================================================================
def test_p6_decorator_perf(result: PerformanceTestResult) -> None:
    """데코레이터 성능 테스트."""
    print("\n[P6] 데코레이터 성능")

    # P6-1. @injectable 데코레이터 적용 처리량
    try:
        def apply_injectable():
            @injectable(scope=Scope.SINGLETON, name="perf_test", tags=["perf"])
            class _TempService:
                pass
            return _TempService

        ops = measure_ops(apply_injectable, iterations=30000)
        assert ops > 10000, f"injectable 적용: {ops:.0f} ops/sec < 10000"
        result.ok("P6-1 @injectable 데코레이터 적용", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-1 @injectable 적용", str(e))

    # P6-2. is_injectable 확인 처리량
    try:
        @injectable(scope=Scope.SINGLETON)
        class InjectableService:
            pass

        class NonInjectableService:
            pass

        def check_injectable():
            _ = is_injectable(InjectableService)
            _ = is_injectable(NonInjectableService)

        ops = measure_ops(check_injectable, iterations=100000)
        assert ops > 100000, f"is_injectable: {ops:.0f} ops/sec < 100000"
        result.ok("P6-2 is_injectable 확인", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-2 is_injectable", str(e))

    # P6-3. get_injectable_metadata 조회 처리량
    try:
        @injectable(scope=Scope.TRANSIENT, name="meta_test", tags=["a", "b"])
        class MetaService:
            pass

        ops = measure_ops(lambda: get_injectable_metadata(MetaService), iterations=100000)
        assert ops > 100000, f"get_injectable_metadata: {ops:.0f} ops/sec < 100000"

        # 결과 검증
        meta = get_injectable_metadata(MetaService)
        assert meta is not None, "메타데이터 None"
        assert meta["scope"] == Scope.TRANSIENT, f"스코프 불일치: {meta['scope']}"
        assert meta["name"] == "meta_test", f"이름 불일치: {meta['name']}"

        result.ok("P6-3 get_injectable_metadata 조회", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P6-3 get_injectable_metadata", str(e))


# =============================================================================
# [P7] 멀티스레드 동시 접근 (3개)
# =============================================================================
def test_p7_multithread_perf(result: PerformanceTestResult) -> None:
    """멀티스레드 성능 테스트."""
    print("\n[P7] 멀티스레드 동시 접근")

    # P7-1. 싱글톤 동시 해결 (4스레드 x 5000)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)
        container = builder.build()
        # 첫 해결로 캐시 프라이밍
        _ = container.resolve(ServiceA)

        errors = []
        instances = []
        n_threads = 4
        n_ops = 5000

        def singleton_worker():
            try:
                local_instances = []
                for _ in range(n_ops):
                    inst = container.resolve(ServiceA)
                    local_instances.append(inst)
                instances.extend(local_instances)
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=singleton_worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"

        # 싱글톤: 모든 인스턴스가 동일 객체여야 함
        unique_ids = set(id(inst) for inst in instances)
        assert len(unique_ids) == 1, f"싱글톤 인스턴스 불일치: {len(unique_ids)}개 고유 객체"

        total_ops = n_threads * n_ops
        ops_per_sec = total_ops / elapsed
        result.ok(
            "P7-1 싱글톤 동시 해결 (4x5000)",
            f"{ops_per_sec:,.0f} ops/sec, 싱글톤 정합성: 100%",
        )
    except Exception as e:
        result.fail("P7-1 싱글톤 동시 해결", str(e))

    # P7-2. 트랜지언트 동시 해결 (4스레드 x 3000)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(SimpleService, SimpleService, scope=Scope.TRANSIENT)
        container = builder.build()

        errors = []
        instances = []
        n_threads = 4
        n_ops = 3000

        def transient_worker():
            try:
                local_instances = []
                for _ in range(n_ops):
                    inst = container.resolve(SimpleService)
                    local_instances.append(inst)
                instances.extend(local_instances)
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [threading.Thread(target=transient_worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"

        # 트랜지언트: 총 인스턴스 수 확인
        assert len(instances) == n_threads * n_ops, (
            f"인스턴스 수 불일치: {len(instances)} != {n_threads * n_ops}"
        )

        total_ops = n_threads * n_ops
        ops_per_sec = total_ops / elapsed
        result.ok(
            "P7-2 트랜지언트 동시 해결 (4x3000)",
            f"{ops_per_sec:,.0f} ops/sec, 총 {len(instances)}개 인스턴스",
        )
    except Exception as e:
        result.fail("P7-2 트랜지언트 동시 해결", str(e))

    # P7-3. 혼합 연산 (싱글톤 + 트랜지언트 + 등록 확인)
    try:
        _reset_container()
        builder = ContainerBuilder()
        builder.register(ServiceA, ServiceA, scope=Scope.SINGLETON)
        builder.register(SimpleService, SimpleService, scope=Scope.TRANSIENT)
        container = builder.build()
        # 프라이밍
        _ = container.resolve(ServiceA)

        errors = []
        n_threads = 4
        n_ops = 2000

        def mixed_worker(tid):
            try:
                for i in range(n_ops):
                    if i % 3 == 0:
                        # 싱글톤 해결
                        _ = container.resolve(ServiceA)
                    elif i % 3 == 1:
                        # 트랜지언트 해결
                        _ = container.resolve(SimpleService)
                    else:
                        # 등록 여부 확인
                        _ = container.is_registered(ServiceA)
                        _ = container.is_registered(SimpleService)
            except Exception as ex:
                errors.append(f"thread-{tid}: {ex}")

        start = time.perf_counter()
        threads = [threading.Thread(target=mixed_worker, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러: {errors}"
        total_ops = n_threads * n_ops
        ops_per_sec = total_ops / elapsed
        result.ok(
            "P7-3 혼합 연산 동시 수행 (4x2000)",
            f"{ops_per_sec:,.0f} ops/sec, 에러 없음",
        )
    except Exception as e:
        result.fail("P7-3 혼합 연산", str(e))


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_p8_memory_perf(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. DIContainer 인스턴스 기본 메모리
    try:
        gc.collect()
        _reset_container()
        builder = ContainerBuilder()
        container = builder.build()

        container_size = get_object_size(container)
        status = container.get_status()
        registered = status["registered_services"]

        result.ok(
            "P8-1 DIContainer 기본 메모리",
            f"container~{container_size}B, 등록={registered}개 서비스",
        )
    except Exception as e:
        result.fail("P8-1 DIContainer 메모리", str(e))

    # P8-2. 100개 서비스 등록 후 메모리
    try:
        gc.collect()
        _reset_container()
        builder = ContainerBuilder()

        # 100개의 고유 서비스 클래스 동적 생성 및 등록
        service_classes = []
        for i in range(100):
            cls = type(f"DynService_{i}", (), {})
            service_classes.append(cls)
            builder.register(cls, cls, scope=Scope.TRANSIENT)

        container = builder.build()
        container_size = get_object_size(container)
        status = container.get_status()
        registered = status["registered_services"]

        # _descriptors 딕셔너리 크기 추정
        descriptors_size = get_object_size(container._descriptors)

        assert registered == 100, f"등록 수 불일치: {registered} != 100"
        result.ok(
            "P8-2 100개 서비스 등록 메모리",
            f"container~{container_size}B, descriptors~{descriptors_size}B, 등록={registered}개",
        )
    except Exception as e:
        result.fail("P8-2 100개 등록 메모리", str(e))

    # P8-3. ScopeContext 메모리 (중첩 스코프)
    try:
        gc.collect()

        # 루트 스코프
        root = ScopeContext(name="root")
        root_size = get_object_size(root)

        # 자식 스코프 추가 및 인스턴스 저장
        child = ScopeContext(name="child", parent=root)
        root.children.append(child)

        for i in range(50):
            cls = type(f"ScopedSvc_{i}", (), {})
            child.set(cls, cls())

        child_size = get_object_size(child)
        instances_size = get_object_size(child.instances)

        # 정리
        root.clear()

        # 정리 후 확인
        assert len(child.instances) == 0, f"정리 후 인스턴스 남음: {len(child.instances)}"

        result.ok(
            "P8-3 ScopeContext 메모리 (50 인스턴스)",
            f"root~{root_size}B, child~{child_size}B, instances_dict~{instances_size}B",
        )
    except Exception as e:
        result.fail("P8-3 ScopeContext 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - dependency_injector.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [P1] Enum 연산 성능
    test_p1_enum_perf(result)

    # [P2] ServiceDescriptor 생성 성능
    test_p2_service_descriptor_perf(result)

    # [P3] ContainerBuilder 등록 성능
    test_p3_container_builder_perf(result)

    # [P4] DIContainer 서비스 해결 성능
    test_p4_container_resolve_perf(result)

    # [P5] DependencyGraph 성능
    test_p5_dependency_graph_perf(result)

    # [P6] 데코레이터 성능
    test_p6_decorator_perf(result)

    # [P7] 멀티스레드 동시 접근
    test_p7_multithread_perf(result)

    # [P8] 메모리 사용량
    test_p8_memory_perf(result)

    # 요약 출력
    result.summary()

    # 전역 컨테이너 정리
    _reset_container()

    # 종료 코드
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
