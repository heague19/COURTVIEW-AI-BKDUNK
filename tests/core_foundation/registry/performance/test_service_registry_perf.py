# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/performance
파일: test_service_registry_perf.py
설명: ServiceRegistry 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [P1] Enum 연산 성능 (3개) - ServiceType/ServiceLifecycle/DependencyType
    [P2] 데이터 클래스 생성 성능 (3개) - ServiceDependency, ServiceMetrics, ServiceConfig, ServiceInfo
    [P3] ServiceRegistry 등록/조회 성능 (4개) - register, get, get_by_type, list
    [P4] ServiceRegistry 의존성 관리 성능 (3개) - dependency tracking, topological sort, dependency order
    [P5] ServiceMetrics 업데이트 성능 (3개) - metrics recording, status changes
    [P6] 싱글톤/헬퍼 함수 성능 (3개) - _get_registry, get_service, register_service
    [P7] 멀티스레드 동시 접근 (3개) - concurrent register, get, mixed operations
    [P8] 메모리 사용량 (3개) - single instance, bulk registrations, ServiceInfo batch

    총 25개 테스트
"""

import gc
import sys
import threading
import time
import tracemalloc
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.registry.service_registry import (
    # Enum (3개)
    ServiceType,
    ServiceLifecycle,
    DependencyType,
    # 상수 (4개)
    DEFAULT_MAX_SERVICES,
    DEFAULT_SERVICE_TIMEOUT,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    SERVICE_SHUTDOWN_GRACE_PERIOD,
    # 데이터 클래스 (5개)
    ServiceDependency,
    ServiceMetrics,
    ServiceConfig,
    ServiceInfo,
    RegisteredService,
    # 프로토콜 (1개)
    IService,
    # 메인 클래스 (1개)
    ServiceRegistry,
    # 헬퍼 함수 (4개)
    get_service,
    register_service,
    _get_registry,
    _reset_registry,
)


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
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" | {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

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
            print(f"\n성능 메트릭:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# Mock 서비스 (IService 프로토콜 만족)
# =============================================================================
class MockService:
    """IService 프로토콜을 만족하는 Mock 서비스 (성능 테스트용)."""

    def __init__(
        self,
        name: str = "mock",
        stype: ServiceType = ServiceType.UTILITY,
    ):
        self._service_name = name
        self._service_type = stype
        self._started = False
        self._initialized = False

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def service_type(self) -> ServiceType:
        return self._service_type

    def initialize(self) -> None:
        self._initialized = True

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def health_check(self) -> bool:
        return True


# =============================================================================
# 헬퍼: 테스트용 레지스트리 생성
# =============================================================================
def _make_registry(max_services: int = 500) -> ServiceRegistry:
    """테스트용 ServiceRegistry 생성 (메트릭 수집기 없이)."""
    return ServiceRegistry(
        config_loader=None,
        metrics_collector=None,
        max_services=max_services,
    )


def _register_mock(
    registry: ServiceRegistry,
    name: str,
    stype: ServiceType = ServiceType.UTILITY,
    dependencies=None,
) -> ServiceInfo:
    """레지스트리에 Mock 서비스를 등록하는 헬퍼."""
    mock = MockService(name=name, stype=stype)
    return registry.register(
        name=name,
        service_type=stype,
        instance=mock,
        dependencies=dependencies,
    )


def measure_ops(func, iterations: int) -> tuple:
    """
    반복 연산 성능 측정 헬퍼.

    Returns:
        (elapsed_seconds, ops_per_sec, us_per_call)
    """
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    ops = iterations / elapsed if elapsed > 0 else float("inf")
    us_per_call = (elapsed / iterations) * 1_000_000 if iterations > 0 else 0.0
    return elapsed, ops, us_per_call


# =============================================================================
# [P1] Enum 연산 성능
# =============================================================================
def test_enum_performance(result: PerformanceTestResult) -> None:
    """Enum 연산 성능 테스트."""
    print("\n[P1] Enum 연산 성능")

    # P1-1. ServiceType 순회 및 프로퍼티 접근
    try:
        all_types = list(ServiceType)
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            for st in all_types:
                _ = st.is_ai_service
                _ = st.is_infrastructure
                _ = st.priority
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_types) * 3  # 3개 프로퍼티
        ops = total_ops / elapsed
        per_call = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P1-1: ServiceType 프로퍼티 접근 (is_ai/is_infra/priority)",
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("P1-1: ServiceType 프로퍼티", str(e))

    # P1-2. ServiceLifecycle 프로퍼티 접근
    try:
        all_states = list(ServiceLifecycle)
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for sl in all_states:
                _ = sl.is_active
                _ = sl.is_transitioning
                _ = sl.can_start
                _ = sl.can_stop
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_states) * 4  # 4개 프로퍼티
        ops = total_ops / elapsed
        per_call = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P1-2: ServiceLifecycle 프로퍼티 접근 (is_active/can_start/can_stop)",
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("P1-2: ServiceLifecycle 프로퍼티", str(e))

    # P1-3. Enum 비교 및 멤버십 테스트
    try:
        iterations = 500_000
        a = ServiceType.DETECTOR
        b = ServiceType.ANALYZER
        c = DependencyType.REQUIRED
        d = DependencyType.OPTIONAL
        start = time.perf_counter()
        for _ in range(iterations):
            _ = a == b
            _ = a == ServiceType.DETECTOR
            _ = a != b
            _ = c == d
            _ = c == DependencyType.REQUIRED
        elapsed = time.perf_counter() - start
        total_ops = iterations * 5
        ops = total_ops / elapsed
        result.ok(
            "P1-3: Enum 비교 (ServiceType/DependencyType)",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P1-3: Enum 비교", str(e))


# =============================================================================
# [P2] 데이터 클래스 생성 성능
# =============================================================================
def test_dataclass_creation_performance(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능 테스트."""
    print("\n[P2] 데이터 클래스 생성 성능")

    # P2-1. ServiceDependency / ServiceConfig 생성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            ServiceDependency(
                service_id="storage:cache_store",
                dependency_type=DependencyType.REQUIRED,
                min_version="1.0.0",
                description="캐시 스토리지 의존성",
            )
        elapsed_dep = time.perf_counter() - start
        ops_dep = iterations / elapsed_dep
        us_dep = (elapsed_dep / iterations) * 1_000_000

        start = time.perf_counter()
        for _ in range(iterations):
            ServiceConfig(
                enabled=True,
                auto_start=True,
                auto_restart=True,
                max_restart_attempts=5,
                max_concurrent_requests=200,
            )
        elapsed_cfg = time.perf_counter() - start
        ops_cfg = iterations / elapsed_cfg
        us_cfg = (elapsed_cfg / iterations) * 1_000_000

        result.ok(
            "P2-1: ServiceDependency/ServiceConfig 생성",
            f"Dep: {ops_dep:,.0f} ops/sec ({us_dep:.2f}us), "
            f"Cfg: {ops_cfg:,.0f} ops/sec ({us_cfg:.2f}us)",
        )
    except Exception as e:
        result.fail("P2-1: ServiceDependency/Config", str(e))

    # P2-2. ServiceMetrics 생성 및 record_request
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            m = ServiceMetrics()
            m.record_request(15.5, success=True)
            m.record_request(20.3, success=False)
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P2-2: ServiceMetrics 생성 + record_request x2",
            f"{ops:,.0f} ops/sec, {us:.2f}us/cycle",
        )
    except Exception as e:
        result.fail("P2-2: ServiceMetrics 생성", str(e))

    # P2-3. ServiceInfo 생성 (전체 필드)
    try:
        iterations = 30_000
        deps = [
            ServiceDependency(service_id="storage:s3", dependency_type=DependencyType.REQUIRED),
            ServiceDependency(service_id="cache:redis", dependency_type=DependencyType.OPTIONAL),
        ]
        start = time.perf_counter()
        for i in range(iterations):
            ServiceInfo(
                service_id=f"analyzer:motion_{i}",
                name=f"motion_{i}",
                service_type=ServiceType.MOTION_ANALYZER,
                version="2.1.0",
                description="동작 분석 서비스",
                author="COURTVIEW AI",
                tags=["ai", "motion", "analysis"],
                dependencies=deps,
                metadata={"gpu_required": True, "batch_size": 32},
            )
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P2-3: ServiceInfo 전체 필드 생성",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-3: ServiceInfo 생성", str(e))


# =============================================================================
# [P3] ServiceRegistry 등록/조회 성능
# =============================================================================
def test_registry_register_get_performance(result: PerformanceTestResult) -> None:
    """ServiceRegistry 등록/조회 성능 테스트."""
    print("\n[P3] ServiceRegistry 등록/조회 성능")

    # P3-1. 서비스 등록 처리량
    try:
        registry = _make_registry(max_services=5000)
        service_types = list(ServiceType)
        num_services = 200
        mocks = [
            MockService(name=f"svc_{i}", stype=service_types[i % len(service_types)])
            for i in range(num_services)
        ]

        start = time.perf_counter()
        for i, mock in enumerate(mocks):
            registry.register(
                name=f"svc_{i}",
                service_type=mock.service_type,
                instance=mock,
                version="1.0.0",
                tags=["perf-test"],
            )
        elapsed = time.perf_counter() - start
        ops = num_services / elapsed
        us = (elapsed / num_services) * 1_000_000
        result.ok(
            "P3-1: 서비스 등록 처리량 (200개)",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-1: 서비스 등록", str(e))

    # P3-2. get() 조회 처리량
    try:
        # 위에서 등록한 레지스트리 재사용
        service_ids = [r.service_id for r in registry.list_all()]
        iterations = 100_000
        sid_count = len(service_ids)
        start = time.perf_counter()
        for i in range(iterations):
            registry.get(service_ids[i % sid_count])
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P3-2: get() 조회 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-2: get 조회", str(e))

    # P3-3. list_by_type() 처리량
    try:
        iterations = 50_000
        types_to_query = list(ServiceType)
        type_count = len(types_to_query)
        start = time.perf_counter()
        for i in range(iterations):
            registry.list_by_type(types_to_query[i % type_count])
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P3-3: list_by_type() 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-3: list_by_type", str(e))

    # P3-4. list_all() 처리량
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            registry.list_all()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P3-4: list_all() 처리량 (200개 서비스)",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-4: list_all", str(e))


# =============================================================================
# [P4] ServiceRegistry 의존성 관리 성능
# =============================================================================
def test_dependency_management_performance(result: PerformanceTestResult) -> None:
    """의존성 관리 성능 테스트."""
    print("\n[P4] ServiceRegistry 의존성 관리 성능")

    # P4-1. 의존성 있는 서비스 등록 처리량
    try:
        registry = _make_registry(max_services=500)

        # 기반 서비스 등록 (의존성 없음)
        base_names = ["storage_svc", "cache_svc", "queue_svc"]
        base_types = [ServiceType.STORAGE, ServiceType.CACHE, ServiceType.QUEUE]
        base_ids = []
        for name, stype in zip(base_names, base_types):
            info = _register_mock(registry, name=name, stype=stype)
            base_ids.append(info.service_id)

        # 의존성을 가진 서비스 50개 등록 (시간 측정)
        dep_list = [
            ServiceDependency(service_id=base_ids[0], dependency_type=DependencyType.REQUIRED),
            ServiceDependency(service_id=base_ids[1], dependency_type=DependencyType.OPTIONAL),
        ]
        num_dep_services = 50
        start = time.perf_counter()
        for i in range(num_dep_services):
            mock = MockService(name=f"dep_svc_{i}", stype=ServiceType.ANALYZER)
            registry.register(
                name=f"dep_svc_{i}",
                service_type=ServiceType.ANALYZER,
                instance=mock,
                dependencies=dep_list,
            )
        elapsed = time.perf_counter() - start
        ops = num_dep_services / elapsed
        us = (elapsed / num_dep_services) * 1_000_000
        result.ok(
            "P4-1: 의존성 있는 서비스 등록 (50개, 각 2개 의존)",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P4-1: 의존성 등록", str(e))

    # P4-2. get_start_order() 위상 정렬 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            registry.get_start_order()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        service_count = registry.service_count
        result.ok(
            "P4-2: get_start_order() 위상 정렬 ({0}개 서비스)".format(service_count),
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P4-2: 위상 정렬", str(e))

    # P4-3. get_dependencies() / get_dependents() 처리량
    try:
        service_ids = [info.service_id for info in registry.list_all()]
        iterations = 50_000
        sid_count = len(service_ids)
        start = time.perf_counter()
        for i in range(iterations):
            sid = service_ids[i % sid_count]
            registry.get_dependencies(sid)
            registry.get_dependents(sid)
        elapsed = time.perf_counter() - start
        total_ops = iterations * 2  # get_dependencies + get_dependents
        ops = total_ops / elapsed
        us = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P4-3: get_dependencies/get_dependents 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P4-3: 의존성 조회", str(e))


# =============================================================================
# [P5] ServiceMetrics 업데이트 성능
# =============================================================================
def test_metrics_update_performance(result: PerformanceTestResult) -> None:
    """ServiceMetrics 업데이트 성능 테스트."""
    print("\n[P5] ServiceMetrics 업데이트 성능")

    # P5-1. record_request 대량 호출
    try:
        metrics = ServiceMetrics()
        iterations = 500_000
        start = time.perf_counter()
        for i in range(iterations):
            metrics.record_request(
                duration_ms=float(i % 100) + 0.5,
                success=(i % 10 != 0),
            )
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P5-1: record_request 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P5-1: record_request", str(e))

    # P5-2. record_health_check / record_start / record_stop
    try:
        metrics = ServiceMetrics()
        iterations = 200_000
        start = time.perf_counter()
        for i in range(iterations):
            if i % 3 == 0:
                metrics.record_health_check(healthy=(i % 7 != 0))
            elif i % 3 == 1:
                metrics.record_start()
            else:
                metrics.record_stop()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P5-2: health_check/start/stop 혼합 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P5-2: health/start/stop", str(e))

    # P5-3. ServiceMetrics 프로퍼티 접근 (avg, success_rate, health_success_rate)
    try:
        # 사전에 데이터 채움
        metrics = ServiceMetrics()
        for i in range(1000):
            metrics.record_request(float(i) + 0.1, success=(i % 5 != 0))
            if i % 10 == 0:
                metrics.record_health_check(healthy=(i % 20 != 0))

        iterations = 500_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = metrics.average_processing_time_ms
            _ = metrics.success_rate
            _ = metrics.health_success_rate
        elapsed = time.perf_counter() - start
        total_ops = iterations * 3
        ops = total_ops / elapsed
        result.ok(
            "P5-3: ServiceMetrics 프로퍼티 접근 (avg/rate/health)",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P5-3: 프로퍼티 접근", str(e))


# =============================================================================
# [P6] 싱글톤/헬퍼 함수 성능
# =============================================================================
def test_singleton_helper_performance(result: PerformanceTestResult) -> None:
    """싱글톤 및 헬퍼 함수 성능 테스트."""
    print("\n[P6] 싱글톤/헬퍼 함수 성능")

    # P6-1. _get_registry() 처리량 (이미 생성된 상태)
    try:
        _reset_registry()
        # 처음 호출로 생성
        _get_registry()

        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _get_registry()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P6-1: _get_registry() 처리량 (생성 완료 후)",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P6-1: _get_registry", str(e))

    # P6-2. register_service() 헬퍼 처리량
    try:
        _reset_registry()
        num_services = 50
        mocks = [
            MockService(name=f"helper_svc_{i}", stype=ServiceType.UTILITY)
            for i in range(num_services)
        ]

        start = time.perf_counter()
        for i, mock in enumerate(mocks):
            register_service(
                name=f"helper_svc_{i}",
                service_type=ServiceType.UTILITY,
                instance=mock,
            )
        elapsed = time.perf_counter() - start
        ops = num_services / elapsed
        us = (elapsed / num_services) * 1_000_000
        result.ok(
            "P6-2: register_service() 헬퍼 처리량 (50개)",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P6-2: register_service", str(e))

    # P6-3. get_service() 헬퍼 처리량
    try:
        # 위에서 등록한 서비스 조회
        reg = _get_registry()
        service_ids = [info.service_id for info in reg.list_all()]

        iterations = 100_000
        sid_count = len(service_ids)
        start = time.perf_counter()
        for i in range(iterations):
            get_service(service_ids[i % sid_count])
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P6-3: get_service() 헬퍼 처리량",
            f"{ops:,.0f} ops/sec, {us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P6-3: get_service", str(e))
    finally:
        _reset_registry()


# =============================================================================
# [P7] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_performance(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 성능 테스트."""
    print("\n[P7] 멀티스레드 동시 접근")

    # P7-1. 동시 등록 (각 스레드가 고유 서비스 등록)
    try:
        registry = _make_registry(max_services=5000)
        num_threads = 4
        services_per_thread = 50
        barrier = threading.Barrier(num_threads)
        results_list = []
        errors = []

        def register_worker(tid: int) -> None:
            try:
                barrier.wait(timeout=5)
                start = time.perf_counter()
                for i in range(services_per_thread):
                    name = f"thread_{tid}_svc_{i}"
                    mock = MockService(name=name, stype=ServiceType.UTILITY)
                    registry.register(
                        name=name,
                        service_type=ServiceType.UTILITY,
                        instance=mock,
                    )
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=register_worker, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        if errors:
            result.fail("P7-1: 동시 등록", f"{len(errors)}개 오류: {errors[0]}")
        else:
            total_ops = num_threads * services_per_thread
            max_elapsed = max(results_list)
            ops = total_ops / max_elapsed
            result.ok(
                "P7-1: 동시 등록 ({0}스레드 x {1}개)".format(num_threads, services_per_thread),
                f"{ops:,.0f} ops/sec (total {total_ops} ops)",
            )
    except Exception as e:
        result.fail("P7-1: 동시 등록", str(e))

    # P7-2. 동시 조회 (get)
    try:
        # 위에서 등록된 서비스 ID 수집
        all_service_ids = [info.service_id for info in registry.list_all()]
        sid_count = len(all_service_ids)
        num_threads = 4
        iterations_per_thread = 50_000
        barrier = threading.Barrier(num_threads)
        results_list = []

        def get_worker(tid: int) -> None:
            barrier.wait(timeout=5)
            start = time.perf_counter()
            for i in range(iterations_per_thread):
                registry.get(all_service_ids[i % sid_count])
            elapsed = time.perf_counter() - start
            results_list.append(elapsed)

        threads = [
            threading.Thread(target=get_worker, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        total_ops = num_threads * iterations_per_thread
        max_elapsed = max(results_list)
        ops = total_ops / max_elapsed
        result.ok(
            "P7-2: 동시 조회 ({0}스레드 x {1}회)".format(num_threads, iterations_per_thread),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P7-2: 동시 조회", str(e))

    # P7-3. 혼합 작업 (등록 + 조회 + list_by_type 동시 수행)
    try:
        mixed_registry = _make_registry(max_services=5000)
        # 사전 등록
        for i in range(100):
            mock = MockService(name=f"mixed_svc_{i}", stype=ServiceType.UTILITY)
            mixed_registry.register(
                name=f"mixed_svc_{i}",
                service_type=ServiceType.UTILITY,
                instance=mock,
            )

        all_ids = [info.service_id for info in mixed_registry.list_all()]
        num_threads = 4
        iterations_per_thread = 10_000
        barrier = threading.Barrier(num_threads)
        results_list = []
        errors = []

        def mixed_worker(tid: int) -> None:
            try:
                barrier.wait(timeout=5)
                start = time.perf_counter()
                for i in range(iterations_per_thread):
                    op = i % 3
                    if op == 0:
                        # 조회
                        mixed_registry.get(all_ids[i % len(all_ids)])
                    elif op == 1:
                        # 타입별 목록
                        mixed_registry.list_by_type(ServiceType.UTILITY)
                    else:
                        # 새 서비스 등록 (고유 이름)
                        name = f"mixed_thread_{tid}_extra_{i}"
                        mock = MockService(name=name, stype=ServiceType.CUSTOM)
                        try:
                            mixed_registry.register(
                                name=name,
                                service_type=ServiceType.CUSTOM,
                                instance=mock,
                            )
                        except ValueError:
                            pass  # 최대 수 초과 시 무시
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=mixed_worker, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        if errors:
            result.fail("P7-3: 혼합 작업", f"{len(errors)}개 오류: {errors[0]}")
        else:
            total_ops = num_threads * iterations_per_thread
            max_elapsed = max(results_list)
            ops = total_ops / max_elapsed
            result.ok(
                "P7-3: 혼합 작업 (등록+조회+list, {0}스레드)".format(num_threads),
                f"{ops:,.0f} ops/sec",
            )
    except Exception as e:
        result.fail("P7-3: 혼합 작업", str(e))


# =============================================================================
# [P8] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. ServiceRegistry 인스턴스 메모리
    try:
        gc.collect()
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        registry = _make_registry()
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        result.ok(
            "P8-1: ServiceRegistry 인스턴스 메모리",
            f"{total / 1024:.1f}KB",
        )
    except Exception as e:
        result.fail("P8-1: 인스턴스 메모리", str(e))

    # P8-2. 대량 서비스 등록 메모리 (100개)
    try:
        gc.collect()
        registry = _make_registry(max_services=500)
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()

        for i in range(100):
            mock = MockService(
                name=f"mem_svc_{i}",
                stype=ServiceType.ANALYZER,
            )
            registry.register(
                name=f"mem_svc_{i}",
                service_type=ServiceType.ANALYZER,
                instance=mock,
                version="1.0.0",
                description=f"메모리 테스트 서비스 {i}",
                tags=["memory", "test"],
                metadata={"index": i},
            )

        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        per_service = total / 100
        result.ok(
            "P8-2: 100개 서비스 등록 메모리",
            f"총 {total / 1024:.1f}KB, 개당 {per_service:.0f}B ({per_service / 1024:.2f}KB)",
        )
    except Exception as e:
        result.fail("P8-2: 대량 등록 메모리", str(e))

    # P8-3. ServiceInfo 배치 생성 메모리 (200개)
    try:
        gc.collect()
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()

        infos = []
        for i in range(200):
            info = ServiceInfo(
                service_id=f"analyzer:mem_info_{i}",
                name=f"mem_info_{i}",
                service_type=ServiceType.SHOOTING_ANALYZER,
                version="1.0.0",
                description="메모리 테스트용 ServiceInfo",
                tags=["perf", "memory"],
                dependencies=[
                    ServiceDependency(
                        service_id=f"storage:dep_{i}",
                        dependency_type=DependencyType.REQUIRED,
                    ),
                ],
                metadata={"idx": i, "gpu": True},
            )
            infos.append(info)

        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        per_info = total / 200
        result.ok(
            "P8-3: ServiceInfo 200개 배치 메모리",
            f"총 {total / 1024:.1f}KB, 개당 {per_info:.0f}B ({per_info / 1024:.2f}KB)",
        )
    except Exception as e:
        result.fail("P8-3: ServiceInfo 배치 메모리", str(e))


# =============================================================================
# 메인
# =============================================================================
def main() -> bool:
    """성능 테스트 메인 실행."""
    result = PerformanceTestResult()

    print("=" * 60)
    print("COURTVIEW - service_registry.py 성능 테스트")
    print("=" * 60)

    test_enum_performance(result)
    test_dataclass_creation_performance(result)
    test_registry_register_get_performance(result)
    test_dependency_management_performance(result)
    test_metrics_update_performance(result)
    test_singleton_helper_performance(result)
    test_multithread_performance(result)
    test_memory_usage(result)

    # 최종 정리
    _reset_registry()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
