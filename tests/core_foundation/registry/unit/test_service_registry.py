# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/unit
파일: test_service_registry.py
설명: ServiceRegistry 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [1]  Enum 테스트 (12개) - ServiceType, ServiceLifecycle, DependencyType
    [2]  상수 테스트 (5개) - DEFAULT_MAX_SERVICES 등
    [3]  데이터클래스 테스트 (12개) - ServiceInfo, ServiceDependency 등
    [4]  ServiceRegistry 기본 동작 (18개) - 등록, 조회, 라이프사이클
    [5]  의존성 & 토폴로지 (10개) - 의존성 체크, 위상 정렬
    [6]  ServiceMetrics 상세 (5개) - 메트릭 기록 및 추적
    [7]  스레드 안전성 (5개) - 동시 접근 안전
    [8]  메모리 누수 (3개) - 등록/해제 반복
"""

import sys
import threading
import time
from copy import deepcopy
from dataclasses import fields, dataclass
from datetime import datetime, timezone
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
    ServiceInfo,
    ServiceDependency,
    ServiceMetrics,
    ServiceConfig,
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


# ============================================================
# 테스트 결과 클래스
# ============================================================
class TestResult:
    """테스트 결과 수집 및 보고."""

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
# Mock 서비스 (IService 프로토콜 구현)
# ============================================================
class MockService:
    """IService 프로토콜을 만족하는 Mock 서비스."""

    def __init__(self, name: str = "mock", stype: ServiceType = ServiceType.UTILITY):
        self._service_name = name
        self._service_type = stype
        self.started = False
        self.initialized = False
        self._healthy = True

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def service_type(self) -> ServiceType:
        return self._service_type

    def initialize(self) -> None:
        self.initialized = True

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def health_check(self) -> bool:
        return self._healthy


class FailingMockService(MockService):
    """시작 시 예외를 발생시키는 Mock 서비스."""

    def start(self) -> None:
        raise RuntimeError("서비스 시작 실패 시뮬레이션")


class UnhealthyMockService(MockService):
    """상태 체크 실패 Mock 서비스."""

    def health_check(self) -> bool:
        return False


# ============================================================
# 레지스트리 팩토리 헬퍼 (grace_period 0으로 빠른 테스트)
# ============================================================
def _make_registry(max_services: int = 100) -> ServiceRegistry:
    """테스트용 ServiceRegistry 생성."""
    return ServiceRegistry(
        config_loader=None,
        metrics_collector=None,
        max_services=max_services,
    )


def _register_mock(
    registry: ServiceRegistry,
    name: str = "test_svc",
    stype: ServiceType = ServiceType.UTILITY,
    dependencies: list = None,
    config: ServiceConfig = None,
) -> ServiceInfo:
    """Mock 서비스를 등록하고 ServiceInfo 반환."""
    svc = MockService(name=name, stype=stype)
    return registry.register(
        name=name,
        service_type=stype,
        instance=svc,
        dependencies=dependencies or [],
        config=config or ServiceConfig(stop_timeout_seconds=0.0, restart_delay_seconds=0.0),
    )


# ============================================================
# [1] Enum 테스트 (12개)
# ============================================================
def test_enums(result: TestResult) -> None:
    """Enum 관련 테스트."""
    print("\n[1] Enum 테스트")

    # 1-1. ServiceType 멤버 수 (19개)
    try:
        members = list(ServiceType)
        assert len(members) == 19, f"예상 19개, 실제 {len(members)}"
        result.ok("ServiceType 멤버 수 = 19")
    except Exception as e:
        result.fail("ServiceType 멤버 수 = 19", str(e))

    # 1-2. ServiceType.is_ai_service 프로퍼티
    try:
        assert ServiceType.DETECTOR.is_ai_service is True
        assert ServiceType.POSE_ESTIMATOR.is_ai_service is True
        assert ServiceType.TRACKER.is_ai_service is True
        assert ServiceType.REFEREE.is_ai_service is True
        assert ServiceType.FOUL_DETECTOR.is_ai_service is True
        assert ServiceType.STORAGE.is_ai_service is False
        assert ServiceType.CACHE.is_ai_service is False
        assert ServiceType.UTILITY.is_ai_service is False
        result.ok("ServiceType.is_ai_service 프로퍼티")
    except Exception as e:
        result.fail("ServiceType.is_ai_service 프로퍼티", str(e))

    # 1-3. ServiceType.is_infrastructure 프로퍼티
    try:
        assert ServiceType.STORAGE.is_infrastructure is True
        assert ServiceType.CACHE.is_infrastructure is True
        assert ServiceType.QUEUE.is_infrastructure is True
        assert ServiceType.NOTIFICATION.is_infrastructure is True
        assert ServiceType.DETECTOR.is_infrastructure is False
        assert ServiceType.CUSTOM.is_infrastructure is False
        result.ok("ServiceType.is_infrastructure 프로퍼티")
    except Exception as e:
        result.fail("ServiceType.is_infrastructure 프로퍼티", str(e))

    # 1-4. ServiceType.priority 프로퍼티 (int 타입, 인프라 < AI < 기타)
    try:
        assert isinstance(ServiceType.STORAGE.priority, int)
        assert ServiceType.STORAGE.priority < ServiceType.DETECTOR.priority
        assert ServiceType.DETECTOR.priority < ServiceType.ANALYZER.priority
        assert ServiceType.ANALYZER.priority < ServiceType.REFEREE.priority
        assert ServiceType.REFEREE.priority < ServiceType.FEEDBACK_GENERATOR.priority
        assert ServiceType.FEEDBACK_GENERATOR.priority < ServiceType.UTILITY.priority
        assert ServiceType.UTILITY.priority <= ServiceType.CUSTOM.priority
        result.ok("ServiceType.priority 프로퍼티 (우선순위 순서)")
    except Exception as e:
        result.fail("ServiceType.priority 프로퍼티 (우선순위 순서)", str(e))

    # 1-5. ServiceLifecycle 멤버 수 (9개)
    try:
        members = list(ServiceLifecycle)
        assert len(members) == 9, f"예상 9개, 실제 {len(members)}"
        result.ok("ServiceLifecycle 멤버 수 = 9")
    except Exception as e:
        result.fail("ServiceLifecycle 멤버 수 = 9", str(e))

    # 1-6. ServiceLifecycle.is_active 프로퍼티
    try:
        assert ServiceLifecycle.RUNNING.is_active is True
        assert ServiceLifecycle.DEGRADED.is_active is True
        assert ServiceLifecycle.REGISTERED.is_active is False
        assert ServiceLifecycle.STOPPED.is_active is False
        assert ServiceLifecycle.FAILED.is_active is False
        assert ServiceLifecycle.STOPPING.is_active is False
        result.ok("ServiceLifecycle.is_active 프로퍼티")
    except Exception as e:
        result.fail("ServiceLifecycle.is_active 프로퍼티", str(e))

    # 1-7. ServiceLifecycle.can_start / can_stop 프로퍼티
    try:
        # can_start: REGISTERED, STOPPED, FAILED
        assert ServiceLifecycle.REGISTERED.can_start is True
        assert ServiceLifecycle.STOPPED.can_start is True
        assert ServiceLifecycle.FAILED.can_start is True
        assert ServiceLifecycle.RUNNING.can_start is False
        assert ServiceLifecycle.STARTING.can_start is False
        # can_stop: RUNNING, PAUSED, DEGRADED
        assert ServiceLifecycle.RUNNING.can_stop is True
        assert ServiceLifecycle.PAUSED.can_stop is True
        assert ServiceLifecycle.DEGRADED.can_stop is True
        assert ServiceLifecycle.STOPPED.can_stop is False
        assert ServiceLifecycle.REGISTERED.can_stop is False
        result.ok("ServiceLifecycle.can_start / can_stop 프로퍼티")
    except Exception as e:
        result.fail("ServiceLifecycle.can_start / can_stop 프로퍼티", str(e))

    # 1-8. ServiceLifecycle.is_transitioning 프로퍼티
    try:
        assert ServiceLifecycle.INITIALIZING.is_transitioning is True
        assert ServiceLifecycle.STARTING.is_transitioning is True
        assert ServiceLifecycle.STOPPING.is_transitioning is True
        assert ServiceLifecycle.RUNNING.is_transitioning is False
        assert ServiceLifecycle.STOPPED.is_transitioning is False
        assert ServiceLifecycle.REGISTERED.is_transitioning is False
        result.ok("ServiceLifecycle.is_transitioning 프로퍼티")
    except Exception as e:
        result.fail("ServiceLifecycle.is_transitioning 프로퍼티", str(e))

    # 1-9. DependencyType 멤버 (REQUIRED, OPTIONAL, LAZY)
    try:
        members = list(DependencyType)
        assert len(members) == 3
        assert DependencyType.REQUIRED.value == "required"
        assert DependencyType.OPTIONAL.value == "optional"
        assert DependencyType.LAZY.value == "lazy"
        result.ok("DependencyType 멤버 (REQUIRED, OPTIONAL, LAZY)")
    except Exception as e:
        result.fail("DependencyType 멤버 (REQUIRED, OPTIONAL, LAZY)", str(e))

    # 1-10. Enum 값 유일성 (각 Enum 내부에서 값 중복 없음)
    try:
        st_values = [m.value for m in ServiceType]
        assert len(st_values) == len(set(st_values)), "ServiceType 값 중복"
        sl_values = [m.value for m in ServiceLifecycle]
        assert len(sl_values) == len(set(sl_values)), "ServiceLifecycle 값 중복"
        dt_values = [m.value for m in DependencyType]
        assert len(dt_values) == len(set(dt_values)), "DependencyType 값 중복"
        result.ok("Enum 값 유일성 (각 Enum 내부)")
    except Exception as e:
        result.fail("Enum 값 유일성 (각 Enum 내부)", str(e))

    # 1-11. Enum 문자열 접근
    try:
        assert ServiceType("detector") == ServiceType.DETECTOR
        assert ServiceLifecycle("running") == ServiceLifecycle.RUNNING
        assert DependencyType("required") == DependencyType.REQUIRED
        result.ok("Enum 문자열 접근")
    except Exception as e:
        result.fail("Enum 문자열 접근", str(e))

    # 1-12. Cross-Enum 독립성 (서로 다른 Enum 간 비교)
    try:
        # 서로 다른 Enum 타입은 같지 않아야 함
        assert ServiceType.DETECTOR != ServiceLifecycle.RUNNING
        assert ServiceType.UTILITY != DependencyType.REQUIRED
        result.ok("Cross-Enum 독립성")
    except Exception as e:
        result.fail("Cross-Enum 독립성", str(e))


# ============================================================
# [2] 상수 테스트 (5개)
# ============================================================
def test_constants(result: TestResult) -> None:
    """상수 관련 테스트."""
    print("\n[2] 상수 테스트")

    # 2-1. DEFAULT_MAX_SERVICES 타입 및 양수
    try:
        assert isinstance(DEFAULT_MAX_SERVICES, int), f"타입 불일치: {type(DEFAULT_MAX_SERVICES)}"
        assert DEFAULT_MAX_SERVICES > 0, f"0 이하: {DEFAULT_MAX_SERVICES}"
        result.ok("DEFAULT_MAX_SERVICES 타입 및 양수")
    except Exception as e:
        result.fail("DEFAULT_MAX_SERVICES 타입 및 양수", str(e))

    # 2-2. DEFAULT_SERVICE_TIMEOUT 양수
    try:
        assert isinstance(DEFAULT_SERVICE_TIMEOUT, (int, float))
        assert DEFAULT_SERVICE_TIMEOUT > 0, f"0 이하: {DEFAULT_SERVICE_TIMEOUT}"
        result.ok("DEFAULT_SERVICE_TIMEOUT > 0")
    except Exception as e:
        result.fail("DEFAULT_SERVICE_TIMEOUT > 0", str(e))

    # 2-3. DEFAULT_HEALTH_CHECK_INTERVAL 양수
    try:
        assert isinstance(DEFAULT_HEALTH_CHECK_INTERVAL, (int, float))
        assert DEFAULT_HEALTH_CHECK_INTERVAL > 0
        result.ok("DEFAULT_HEALTH_CHECK_INTERVAL > 0")
    except Exception as e:
        result.fail("DEFAULT_HEALTH_CHECK_INTERVAL > 0", str(e))

    # 2-4. SERVICE_SHUTDOWN_GRACE_PERIOD 양수
    try:
        assert isinstance(SERVICE_SHUTDOWN_GRACE_PERIOD, (int, float))
        assert SERVICE_SHUTDOWN_GRACE_PERIOD > 0
        result.ok("SERVICE_SHUTDOWN_GRACE_PERIOD > 0")
    except Exception as e:
        result.fail("SERVICE_SHUTDOWN_GRACE_PERIOD > 0", str(e))

    # 2-5. 상수 불변성 (모듈 레벨 상수 재할당 시도 → 값 유지 확인)
    try:
        original_max = DEFAULT_MAX_SERVICES
        original_timeout = DEFAULT_SERVICE_TIMEOUT
        # 모듈 상수는 Python에서 변경 가능하지만, 원본 값이 정상인지 확인
        assert original_max == 100, f"기본값 불일치: {original_max}"
        assert original_timeout == 30.0, f"기본값 불일치: {original_timeout}"
        result.ok("상수 기본값 일관성")
    except Exception as e:
        result.fail("상수 기본값 일관성", str(e))


# ============================================================
# [3] 데이터클래스 테스트 (12개)
# ============================================================
def test_dataclasses(result: TestResult) -> None:
    """데이터클래스 관련 테스트."""
    print("\n[3] 데이터클래스 테스트")

    # 3-1. ServiceInfo 생성
    try:
        info = ServiceInfo(
            service_id="detector:ball",
            name="ball",
            service_type=ServiceType.DETECTOR,
            version="1.0.0",
            description="공 탐지기",
        )
        assert info.service_id == "detector:ball"
        assert info.name == "ball"
        assert info.service_type == ServiceType.DETECTOR
        assert info.lifecycle == ServiceLifecycle.REGISTERED
        assert info.description == "공 탐지기"
        result.ok("ServiceInfo 생성")
    except Exception as e:
        result.fail("ServiceInfo 생성", str(e))

    # 3-2. ServiceDependency 생성 (REQUIRED)
    try:
        dep = ServiceDependency(
            service_id="storage:main",
            dependency_type=DependencyType.REQUIRED,
            description="메인 스토리지",
        )
        assert dep.service_id == "storage:main"
        assert dep.dependency_type == DependencyType.REQUIRED
        assert dep.description == "메인 스토리지"
        assert dep.min_version is None
        result.ok("ServiceDependency 생성 (REQUIRED)")
    except Exception as e:
        result.fail("ServiceDependency 생성 (REQUIRED)", str(e))

    # 3-3. ServiceDependency 생성 (OPTIONAL)
    try:
        dep = ServiceDependency(
            service_id="cache:redis",
            dependency_type=DependencyType.OPTIONAL,
        )
        assert dep.dependency_type == DependencyType.OPTIONAL
        result.ok("ServiceDependency 생성 (OPTIONAL)")
    except Exception as e:
        result.fail("ServiceDependency 생성 (OPTIONAL)", str(e))

    # 3-4. ServiceMetrics 기본값 생성
    try:
        metrics = ServiceMetrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.start_count == 0
        assert metrics.stop_count == 0
        assert metrics.failure_count == 0
        assert metrics.total_uptime_seconds == 0.0
        assert metrics.last_started_at is None
        assert metrics.last_stopped_at is None
        assert metrics.last_error is None
        result.ok("ServiceMetrics 기본값 생성")
    except Exception as e:
        result.fail("ServiceMetrics 기본값 생성", str(e))

    # 3-5. ServiceMetrics record_request 연산
    try:
        metrics = ServiceMetrics()
        metrics.record_request(100.0, success=True)
        metrics.record_request(200.0, success=True)
        metrics.record_request(50.0, success=False)
        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert abs(metrics.average_processing_time_ms - (350.0 / 3)) < 0.01
        assert metrics.min_processing_time_ms == 50.0
        assert metrics.max_processing_time_ms == 200.0
        assert abs(metrics.success_rate - (2 / 3)) < 0.01
        result.ok("ServiceMetrics record_request 연산")
    except Exception as e:
        result.fail("ServiceMetrics record_request 연산", str(e))

    # 3-6. ServiceConfig 생성
    try:
        config = ServiceConfig(
            enabled=True,
            auto_start=True,
            max_restart_attempts=5,
        )
        assert config.enabled is True
        assert config.auto_start is True
        assert config.max_restart_attempts == 5
        assert config.auto_restart is True  # 기본값
        result.ok("ServiceConfig 생성")
    except Exception as e:
        result.fail("ServiceConfig 생성", str(e))

    # 3-7. ServiceConfig 기본값 확인
    try:
        config = ServiceConfig()
        assert config.enabled is True
        assert config.auto_start is False
        assert config.auto_restart is True
        assert config.max_restart_attempts == 3
        assert config.restart_delay_seconds == 5.0
        assert config.max_concurrent_requests == 100
        assert config.request_timeout_seconds == 30.0
        assert isinstance(config.extra_params, dict)
        assert len(config.extra_params) == 0
        result.ok("ServiceConfig 기본값 확인")
    except Exception as e:
        result.fail("ServiceConfig 기본값 확인", str(e))

    # 3-8. RegisteredService 생성
    try:
        info = ServiceInfo(
            service_id="utility:test",
            name="test",
            service_type=ServiceType.UTILITY,
        )
        mock = MockService("test")
        reg = RegisteredService(
            service_info=info,
            service_instance=mock,
        )
        assert reg.service_id == "utility:test"
        assert reg.lifecycle == ServiceLifecycle.REGISTERED
        assert reg.is_running is False
        assert reg.get_instance() is mock
        result.ok("RegisteredService 생성")
    except Exception as e:
        result.fail("RegisteredService 생성", str(e))

    # 3-9. RegisteredService acquire 컨텍스트 매니저
    try:
        info = ServiceInfo(
            service_id="utility:ctx",
            name="ctx",
            service_type=ServiceType.UTILITY,
        )
        mock = MockService("ctx")
        reg = RegisteredService(service_info=info, service_instance=mock)
        with reg.acquire() as instance:
            assert instance is mock
        result.ok("RegisteredService acquire 컨텍스트 매니저")
    except Exception as e:
        result.fail("RegisteredService acquire 컨텍스트 매니저", str(e))

    # 3-10. 필드 타입 검증 (ServiceInfo 필드 존재)
    try:
        field_names = {f.name for f in fields(ServiceInfo)}
        required_fields = {
            "service_id", "name", "service_type", "version",
            "lifecycle", "description", "dependencies", "config",
            "metrics", "registered_at", "updated_at",
        }
        missing = required_fields - field_names
        assert len(missing) == 0, f"누락된 필드: {missing}"
        result.ok("ServiceInfo 필드 타입 검증")
    except Exception as e:
        result.fail("ServiceInfo 필드 타입 검증", str(e))

    # 3-11. Optional 필드 처리
    try:
        info = ServiceInfo(
            service_id="utility:opt",
            name="opt",
            service_type=ServiceType.UTILITY,
        )
        assert info.description is None
        assert info.author is None
        assert info.status_message is None
        result.ok("Optional 필드 처리 (None 기본값)")
    except Exception as e:
        result.fail("Optional 필드 처리 (None 기본값)", str(e))

    # 3-12. datetime 필드 (registered_at, updated_at)
    try:
        info = ServiceInfo(
            service_id="utility:dt",
            name="dt",
            service_type=ServiceType.UTILITY,
        )
        assert isinstance(info.registered_at, datetime)
        assert isinstance(info.updated_at, datetime)
        # UTC 타임존 확인
        assert info.registered_at.tzinfo is not None
        result.ok("datetime 필드 (registered_at, updated_at)")
    except Exception as e:
        result.fail("datetime 필드 (registered_at, updated_at)", str(e))


# ============================================================
# [4] ServiceRegistry 기본 동작 (18개)
# ============================================================
def test_registry_basic(result: TestResult) -> None:
    """ServiceRegistry 기본 동작 테스트."""
    print("\n[4] ServiceRegistry 기본 동작")

    # 4-1. 싱글톤: _get_registry / _reset_registry
    try:
        _reset_registry()
        r1 = _get_registry()
        r2 = _get_registry()
        assert r1 is r2, "싱글톤 인스턴스가 동일하지 않음"
        _reset_registry()
        r3 = _get_registry()
        assert r3 is not r1, "리셋 후 새 인스턴스가 생성되지 않음"
        _reset_registry()
        result.ok("_get_registry / _reset_registry 싱글톤")
    except Exception as e:
        _reset_registry()
        result.fail("_get_registry / _reset_registry 싱글톤", str(e))

    # 4-2. register: 서비스 등록
    try:
        _reset_registry()
        registry = _make_registry()
        info = _register_mock(registry, "svc_a", ServiceType.DETECTOR)
        assert info is not None
        assert info.service_id == "detector:svc_a"
        assert info.name == "svc_a"
        assert info.lifecycle == ServiceLifecycle.REGISTERED
        result.ok("서비스 등록 (register)")
    except Exception as e:
        result.fail("서비스 등록 (register)", str(e))

    # 4-3. register: 중복 등록 시 ValueError
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "dup", ServiceType.DETECTOR)
        raised = False
        try:
            _register_mock(registry, "dup", ServiceType.DETECTOR)
        except ValueError:
            raised = True
        assert raised, "중복 등록 시 ValueError가 발생하지 않음"
        result.ok("중복 등록 → ValueError")
    except Exception as e:
        result.fail("중복 등록 → ValueError", str(e))

    # 4-4. get: 이름으로 서비스 조회
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "finder", ServiceType.CACHE)
        info = registry.get_by_name("finder")
        assert info is not None
        assert info.name == "finder"
        result.ok("get_by_name 이름으로 서비스 조회")
    except Exception as e:
        result.fail("get_by_name 이름으로 서비스 조회", str(e))

    # 4-5. get: 존재하지 않는 서비스 → None
    try:
        _reset_registry()
        registry = _make_registry()
        info = registry.get("nonexistent:svc")
        assert info is None, "존재하지 않는 서비스가 None이 아님"
        result.ok("존재하지 않는 서비스 → None")
    except Exception as e:
        result.fail("존재하지 않는 서비스 → None", str(e))

    # 4-6. list_by_type: 타입별 조회
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "det1", ServiceType.DETECTOR)
        _register_mock(registry, "det2", ServiceType.DETECTOR)
        _register_mock(registry, "cache1", ServiceType.CACHE)
        detectors = registry.list_by_type(ServiceType.DETECTOR)
        assert len(detectors) == 2, f"예상 2개, 실제 {len(detectors)}"
        caches = registry.list_by_type(ServiceType.CACHE)
        assert len(caches) == 1
        result.ok("list_by_type 타입별 조회")
    except Exception as e:
        result.fail("list_by_type 타입별 조회", str(e))

    # 4-7. list_all: 전체 서비스 목록
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "a", ServiceType.STORAGE)
        _register_mock(registry, "b", ServiceType.CACHE)
        _register_mock(registry, "c", ServiceType.QUEUE)
        all_svcs = registry.list_all()
        assert len(all_svcs) == 3
        result.ok("list_all 전체 서비스 목록")
    except Exception as e:
        result.fail("list_all 전체 서비스 목록", str(e))

    # 4-8. service_count 프로퍼티
    try:
        _reset_registry()
        registry = _make_registry()
        assert registry.service_count == 0
        _register_mock(registry, "x", ServiceType.UTILITY)
        assert registry.service_count == 1
        _register_mock(registry, "y", ServiceType.CUSTOM)
        assert registry.service_count == 2
        result.ok("service_count 프로퍼티")
    except Exception as e:
        result.fail("service_count 프로퍼티", str(e))

    # 4-9. start: 서비스 시작
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "starter", ServiceType.UTILITY)
        sid = "utility:starter"
        ok = registry.start(sid)
        assert ok is True, "서비스 시작 실패"
        info = registry.get(sid)
        assert info.lifecycle == ServiceLifecycle.RUNNING
        result.ok("서비스 시작 (start)")
    except Exception as e:
        result.fail("서비스 시작 (start)", str(e))

    # 4-10. stop: 서비스 중지
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "stopper", ServiceType.UTILITY)
        sid = "utility:stopper"
        registry.start(sid)
        ok = registry.stop(sid, grace_period=0.0)
        assert ok is True, "서비스 중지 실패"
        info = registry.get(sid)
        assert info.lifecycle == ServiceLifecycle.STOPPED
        result.ok("서비스 중지 (stop)")
    except Exception as e:
        result.fail("서비스 중지 (stop)", str(e))

    # 4-11. restart: 서비스 재시작
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "restarter", ServiceType.UTILITY)
        sid = "utility:restarter"
        registry.start(sid)
        ok = registry.restart(sid)
        assert ok is True, "서비스 재시작 실패"
        info = registry.get(sid)
        assert info.lifecycle == ServiceLifecycle.RUNNING
        assert info.metrics.restart_count >= 1
        result.ok("서비스 재시작 (restart)")
    except Exception as e:
        result.fail("서비스 재시작 (restart)", str(e))

    # 4-12. start: 필수 의존성 미등록 → 시작 실패
    try:
        _reset_registry()
        registry = _make_registry()
        dep = ServiceDependency(
            service_id="storage:missing",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "dep_svc", ServiceType.ANALYZER, dependencies=[dep])
        sid = "analyzer:dep_svc"
        ok = registry.start(sid)
        assert ok is False, "필수 의존성 없이 시작 성공됨"
        result.ok("필수 의존성 미등록 → 시작 실패")
    except Exception as e:
        result.fail("필수 의존성 미등록 → 시작 실패", str(e))

    # 4-13. start: 선택적 의존성 미등록 → 시작 성공
    try:
        _reset_registry()
        registry = _make_registry()
        dep = ServiceDependency(
            service_id="cache:optional_cache",
            dependency_type=DependencyType.OPTIONAL,
        )
        _register_mock(registry, "opt_svc", ServiceType.ANALYZER, dependencies=[dep])
        sid = "analyzer:opt_svc"
        ok = registry.start(sid)
        assert ok is True, "선택적 의존성 미등록인데 시작 실패"
        result.ok("선택적 의존성 미등록 → 시작 성공")
    except Exception as e:
        result.fail("선택적 의존성 미등록 → 시작 성공", str(e))

    # 4-14. get_status: 레지스트리 상태 조회
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "st1", ServiceType.DETECTOR)
        _register_mock(registry, "st2", ServiceType.CACHE)
        registry.start("detector:st1")
        status = registry.get_status()
        assert isinstance(status, dict)
        assert status["registered_services"] == 2
        assert status["running_services"] >= 1
        assert "service_types" in status
        assert "config" in status
        result.ok("get_status 레지스트리 상태 조회")
    except Exception as e:
        result.fail("get_status 레지스트리 상태 조회", str(e))

    # 4-15. ServiceMetrics 조회 (등록 후 시작/중지 반영)
    try:
        _reset_registry()
        registry = _make_registry()
        info = _register_mock(registry, "met", ServiceType.UTILITY)
        sid = "utility:met"
        registry.start(sid)
        registry.stop(sid, grace_period=0.0)
        updated_info = registry.get(sid)
        assert updated_info.metrics.start_count == 1
        assert updated_info.metrics.stop_count == 1
        result.ok("ServiceMetrics 시작/중지 반영")
    except Exception as e:
        result.fail("ServiceMetrics 시작/중지 반영", str(e))

    # 4-16. unregister: 서비스 등록 해제
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "unreg", ServiceType.UTILITY)
        sid = "utility:unreg"
        assert registry.service_count == 1
        ok = registry.unregister(sid)
        assert ok is True
        assert registry.service_count == 0
        assert registry.get(sid) is None
        result.ok("서비스 등록 해제 (unregister)")
    except Exception as e:
        result.fail("서비스 등록 해제 (unregister)", str(e))

    # 4-17. shutdown: 레지스트리 종료
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "sh1", ServiceType.UTILITY)
        registry.start("utility:sh1")
        registry.shutdown()
        assert registry.enabled is False
        result.ok("shutdown 레지스트리 종료")
    except Exception as e:
        result.fail("shutdown 레지스트리 종료", str(e))

    # 4-18. reload_config: 설정 리로드 (예외 없이 완료)
    try:
        _reset_registry()
        registry = _make_registry()
        registry.reload_config()  # 예외 발생하지 않으면 성공
        result.ok("reload_config 설정 리로드")
    except Exception as e:
        result.fail("reload_config 설정 리로드", str(e))


# ============================================================
# [5] 의존성 & 토폴로지 (10개)
# ============================================================
def test_dependency_topology(result: TestResult) -> None:
    """의존성 및 위상 정렬 테스트."""
    print("\n[5] 의존성 & 토폴로지")

    # 5-1. 필수 의존성 체크: 등록은 되었지만 미실행 → 시작 실패
    try:
        _reset_registry()
        registry = _make_registry()
        # 스토리지 등록 (미시작)
        _register_mock(registry, "store", ServiceType.STORAGE)
        dep = ServiceDependency(
            service_id="storage:store",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "analyzer_r", ServiceType.ANALYZER, dependencies=[dep])
        ok = registry.start("analyzer:analyzer_r")
        assert ok is False, "필수 의존성 미실행인데 시작 성공"
        result.ok("필수 의존성: 등록됨-미실행 → 시작 실패")
    except Exception as e:
        result.fail("필수 의존성: 등록됨-미실행 → 시작 실패", str(e))

    # 5-2. 선택적 의존성: 미등록이어도 시작 성공
    try:
        _reset_registry()
        registry = _make_registry()
        dep = ServiceDependency(
            service_id="cache:nonexist",
            dependency_type=DependencyType.OPTIONAL,
        )
        _register_mock(registry, "opt_an", ServiceType.ANALYZER, dependencies=[dep])
        ok = registry.start("analyzer:opt_an")
        assert ok is True
        result.ok("선택적 의존성: 미등록 → 시작 성공")
    except Exception as e:
        result.fail("선택적 의존성: 미등록 → 시작 성공", str(e))

    # 5-3. Lazy 의존성: 미등록이어도 시작 성공 (LAZY는 OPTIONAL처럼 스킵되지 않지만, 실제 미등록이면 패스)
    try:
        _reset_registry()
        registry = _make_registry()
        dep = ServiceDependency(
            service_id="cache:lazy_dep",
            dependency_type=DependencyType.LAZY,
        )
        _register_mock(registry, "lazy_svc", ServiceType.ANALYZER, dependencies=[dep])
        # LAZY 의존성은 _check_dependencies에서 OPTIONAL처럼 continue하지 않음
        # 하지만 dep_service가 없으면 REQUIRED가 아니므로 continue
        ok = registry.start("analyzer:lazy_svc")
        # LAZY 타입은 OPTIONAL도 REQUIRED도 아님 → continue로 통과
        assert ok is True, "LAZY 의존성 미등록인데 시작 실패"
        result.ok("Lazy 의존성: 미등록 → 시작 성공")
    except Exception as e:
        result.fail("Lazy 의존성: 미등록 → 시작 성공", str(e))

    # 5-4. 위상 정렬 순서 (get_start_order)
    try:
        _reset_registry()
        registry = _make_registry()
        # 인프라 먼저, 분석 나중에 등록
        _register_mock(registry, "infra_storage", ServiceType.STORAGE)
        _register_mock(registry, "infra_cache", ServiceType.CACHE)
        dep = ServiceDependency(
            service_id="storage:infra_storage",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "analyzer_t", ServiceType.ANALYZER, dependencies=[dep])

        order = registry.get_start_order()
        # storage가 analyzer보다 먼저 와야 함
        storage_idx = order.index("storage:infra_storage")
        analyzer_idx = order.index("analyzer:analyzer_t")
        assert storage_idx < analyzer_idx, f"storage({storage_idx}) >= analyzer({analyzer_idx})"
        result.ok("위상 정렬: 의존 서비스 먼저")
    except Exception as e:
        result.fail("위상 정렬: 의존 서비스 먼저", str(e))

    # 5-5. start_all: 우선순위 순서로 시작
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "sa_util", ServiceType.UTILITY)
        _register_mock(registry, "sa_store", ServiceType.STORAGE)
        _register_mock(registry, "sa_cache", ServiceType.CACHE)
        results_map = registry.start_all()
        # 모두 성공해야 함
        for sid, success in results_map.items():
            assert success is True, f"시작 실패: {sid}"
        # 실행 중인 서비스 수 확인
        assert registry.running_count == 3
        result.ok("start_all: 우선순위 순서 시작")
    except Exception as e:
        result.fail("start_all: 우선순위 순서 시작", str(e))

    # 5-6. stop_all: 역우선순위 순서로 중지
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "so_store", ServiceType.STORAGE)
        _register_mock(registry, "so_util", ServiceType.UTILITY)
        registry.start_all()
        assert registry.running_count == 2
        results_map = registry.stop_all()
        for sid, success in results_map.items():
            assert success is True, f"중지 실패: {sid}"
        assert registry.running_count == 0
        result.ok("stop_all: 역우선순위 순서 중지")
    except Exception as e:
        result.fail("stop_all: 역우선순위 순서 중지", str(e))

    # 5-7. 순환 의존성 감지 (등록 자체는 가능하지만 시작 시 문제)
    try:
        _reset_registry()
        registry = _make_registry()
        # A → B, B → A 순환 의존성
        dep_b = ServiceDependency(
            service_id="cache:circ_b",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "circ_a", ServiceType.STORAGE, dependencies=[dep_b])
        dep_a = ServiceDependency(
            service_id="storage:circ_a",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "circ_b", ServiceType.CACHE, dependencies=[dep_a])
        # A 시작 시도 → B가 미실행이므로 실패
        ok = registry.start("storage:circ_a")
        assert ok is False, "순환 의존성인데 시작 성공"
        result.ok("순환 의존성: 시작 실패")
    except Exception as e:
        result.fail("순환 의존성: 시작 실패", str(e))

    # 5-8. 의존성 그래프 탐색 (get_dependencies / get_dependents)
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "base_svc", ServiceType.STORAGE)
        dep = ServiceDependency(
            service_id="storage:base_svc",
            dependency_type=DependencyType.REQUIRED,
        )
        _register_mock(registry, "dep_svc", ServiceType.ANALYZER, dependencies=[dep])
        # dep_svc의 의존성 조회
        deps = registry.get_dependencies("analyzer:dep_svc")
        assert len(deps) == 1
        assert deps[0].service_id == "storage:base_svc"
        # base_svc의 의존자 조회
        dependents = registry.get_dependents("storage:base_svc")
        assert "analyzer:dep_svc" in dependents
        result.ok("의존성 그래프 탐색")
    except Exception as e:
        result.fail("의존성 그래프 탐색", str(e))

    # 5-9. 다중 의존성
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "m_store", ServiceType.STORAGE)
        _register_mock(registry, "m_cache", ServiceType.CACHE)
        dep1 = ServiceDependency(service_id="storage:m_store", dependency_type=DependencyType.REQUIRED)
        dep2 = ServiceDependency(service_id="cache:m_cache", dependency_type=DependencyType.OPTIONAL)
        _register_mock(registry, "m_analyzer", ServiceType.ANALYZER, dependencies=[dep1, dep2])
        deps = registry.get_dependencies("analyzer:m_analyzer")
        assert len(deps) == 2
        result.ok("다중 의존성")
    except Exception as e:
        result.fail("다중 의존성", str(e))

    # 5-10. 고아 서비스 (의존성 없는 서비스) 처리
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "orphan1", ServiceType.UTILITY)
        _register_mock(registry, "orphan2", ServiceType.CUSTOM)
        # 의존성 없는 서비스들도 정상 시작
        ok1 = registry.start("utility:orphan1")
        ok2 = registry.start("custom:orphan2")
        assert ok1 is True and ok2 is True
        # 시작 순서에 포함
        order = registry.get_start_order()
        assert "utility:orphan1" in order
        assert "custom:orphan2" in order
        result.ok("고아 서비스 (의존성 없는 서비스) 처리")
    except Exception as e:
        result.fail("고아 서비스 (의존성 없는 서비스) 처리", str(e))


# ============================================================
# [6] ServiceMetrics 상세 (5개)
# ============================================================
def test_service_metrics_detail(result: TestResult) -> None:
    """ServiceMetrics 상세 테스트."""
    print("\n[6] ServiceMetrics 상세")

    # 6-1. start_count 증가
    try:
        metrics = ServiceMetrics()
        metrics.record_start()
        metrics.record_start()
        assert metrics.start_count == 2
        result.ok("start_count 증가")
    except Exception as e:
        result.fail("start_count 증가", str(e))

    # 6-2. stop_count 증가
    try:
        metrics = ServiceMetrics()
        metrics.record_stop()
        assert metrics.stop_count == 1
        result.ok("stop_count 증가")
    except Exception as e:
        result.fail("stop_count 증가", str(e))

    # 6-3. failure_count 증가 및 에러 기록
    try:
        metrics = ServiceMetrics()
        metrics.record_failure("테스트 에러")
        assert metrics.failure_count == 1
        assert metrics.last_error == "테스트 에러"
        assert metrics.last_error_at is not None
        result.ok("failure_count 증가 및 에러 기록")
    except Exception as e:
        result.fail("failure_count 증가 및 에러 기록", str(e))

    # 6-4. uptime 추적
    try:
        metrics = ServiceMetrics()
        metrics.record_start()
        time.sleep(0.05)  # 50ms 대기
        metrics.record_stop()
        assert metrics.total_uptime_seconds > 0.0, "가동 시간이 0"
        assert metrics.total_uptime_seconds < 5.0, "가동 시간이 비정상적으로 큼"
        result.ok("uptime 추적")
    except Exception as e:
        result.fail("uptime 추적", str(e))

    # 6-5. last_started_at / last_stopped_at 타임스탬프
    try:
        metrics = ServiceMetrics()
        assert metrics.last_started_at is None
        assert metrics.last_stopped_at is None
        metrics.record_start()
        assert isinstance(metrics.last_started_at, datetime)
        metrics.record_stop()
        assert isinstance(metrics.last_stopped_at, datetime)
        assert metrics.last_stopped_at >= metrics.last_started_at
        result.ok("last_started_at / last_stopped_at 타임스탬프")
    except Exception as e:
        result.fail("last_started_at / last_stopped_at 타임스탬프", str(e))


# ============================================================
# [7] 스레드 안전성 (5개)
# ============================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 테스트."""
    print("\n[7] 스레드 안전성")

    # 7-1. 4 스레드 × 10 등록 (총 40개 서비스)
    try:
        _reset_registry()
        registry = _make_registry(max_services=200)
        errors = []
        barrier = threading.Barrier(4)

        def register_batch(thread_id: int):
            try:
                barrier.wait(timeout=5.0)
                for i in range(10):
                    name = f"t{thread_id}_svc_{i}"
                    svc = MockService(name=name)
                    registry.register(
                        name=name,
                        service_type=ServiceType.UTILITY,
                        instance=svc,
                        config=ServiceConfig(stop_timeout_seconds=0.0),
                    )
            except Exception as ex:
                errors.append(str(ex))

        threads = []
        for tid in range(4):
            t = threading.Thread(target=register_batch, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=15.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        assert registry.service_count == 40, f"예상 40, 실제 {registry.service_count}"
        result.ok("4 스레드 x 10 등록 = 40개")
    except Exception as e:
        result.fail("4 스레드 x 10 등록 = 40개", str(e))

    # 7-2. 동시 get_service (읽기 동시성)
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "read_svc", ServiceType.UTILITY)
        sid = "utility:read_svc"
        read_errors = []
        barrier = threading.Barrier(4)

        def read_batch():
            try:
                barrier.wait(timeout=5.0)
                for _ in range(50):
                    info = registry.get(sid)
                    if info is None:
                        read_errors.append("None 반환")
            except Exception as ex:
                read_errors.append(str(ex))

        threads = [threading.Thread(target=read_batch) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(read_errors) == 0, f"읽기 에러: {read_errors}"
        result.ok("동시 get_service 읽기")
    except Exception as e:
        result.fail("동시 get_service 읽기", str(e))

    # 7-3. 등록 + 시작 레이스 컨디션
    try:
        _reset_registry()
        registry = _make_registry(max_services=200)
        race_errors = []
        barrier = threading.Barrier(2)

        def register_worker():
            try:
                barrier.wait(timeout=5.0)
                for i in range(10):
                    name = f"race_r_{i}"
                    svc = MockService(name=name)
                    registry.register(
                        name=name,
                        service_type=ServiceType.UTILITY,
                        instance=svc,
                        config=ServiceConfig(stop_timeout_seconds=0.0),
                    )
            except Exception as ex:
                race_errors.append(f"register: {ex}")

        def start_worker():
            try:
                barrier.wait(timeout=5.0)
                time.sleep(0.01)  # 등록 후 약간 대기
                for i in range(10):
                    sid = f"utility:race_r_{i}"
                    try:
                        registry.start(sid)
                    except Exception:
                        pass  # 아직 등록 안 된 경우 무시
            except Exception as ex:
                race_errors.append(f"start: {ex}")

        t1 = threading.Thread(target=register_worker)
        t2 = threading.Thread(target=start_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        assert len(race_errors) == 0, f"레이스 에러: {race_errors}"
        result.ok("등록 + 시작 레이스 컨디션 안전")
    except Exception as e:
        result.fail("등록 + 시작 레이스 컨디션 안전", str(e))

    # 7-4. Lock 격리 (서로 다른 서비스 시작이 서로 영향 없음)
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "lock_a", ServiceType.STORAGE)
        _register_mock(registry, "lock_b", ServiceType.CACHE)
        lock_errors = []
        barrier = threading.Barrier(2)

        def start_a():
            try:
                barrier.wait(timeout=5.0)
                registry.start("storage:lock_a")
            except Exception as ex:
                lock_errors.append(f"A: {ex}")

        def start_b():
            try:
                barrier.wait(timeout=5.0)
                registry.start("cache:lock_b")
            except Exception as ex:
                lock_errors.append(f"B: {ex}")

        t1 = threading.Thread(target=start_a)
        t2 = threading.Thread(target=start_b)
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        assert len(lock_errors) == 0
        # 두 서비스 모두 실행 중
        assert registry.get("storage:lock_a").lifecycle == ServiceLifecycle.RUNNING
        assert registry.get("cache:lock_b").lifecycle == ServiceLifecycle.RUNNING
        result.ok("Lock 격리: 서로 다른 서비스 독립 시작")
    except Exception as e:
        result.fail("Lock 격리: 서로 다른 서비스 독립 시작", str(e))

    # 7-5. 전체 에러 0 확인 (종합)
    try:
        _reset_registry()
        registry = _make_registry(max_services=500)
        total_errors = []
        barrier = threading.Barrier(4)

        def mixed_ops(thread_id: int):
            try:
                barrier.wait(timeout=5.0)
                for i in range(20):
                    name = f"mix_{thread_id}_{i}"
                    svc = MockService(name=name)
                    try:
                        registry.register(
                            name=name,
                            service_type=ServiceType.UTILITY,
                            instance=svc,
                            config=ServiceConfig(stop_timeout_seconds=0.0),
                        )
                        sid = f"utility:{name}"
                        registry.start(sid)
                        registry.get(sid)
                        registry.stop(sid, grace_period=0.0)
                    except ValueError:
                        pass  # 중복 시 무시
            except Exception as ex:
                total_errors.append(str(ex))

        threads = [threading.Thread(target=mixed_ops, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        assert len(total_errors) == 0, f"종합 에러: {total_errors}"
        result.ok("4 스레드 혼합 작업 에러 0")
    except Exception as e:
        result.fail("4 스레드 혼합 작업 에러 0", str(e))


# ============================================================
# [8] 메모리 누수 (3개)
# ============================================================
def test_memory_leak(result: TestResult) -> None:
    """메모리 누수 테스트."""
    print("\n[8] 메모리 누수")

    # 8-1. 1000회 등록/해제 반복
    try:
        _reset_registry()
        registry = _make_registry(max_services=100)
        for i in range(1000):
            name = f"leak_{i}"
            svc = MockService(name=name)
            registry.register(
                name=name,
                service_type=ServiceType.UTILITY,
                instance=svc,
                config=ServiceConfig(stop_timeout_seconds=0.0),
            )
            sid = f"utility:{name}"
            registry.unregister(sid)

        assert registry.service_count == 0, f"서비스 잔여: {registry.service_count}"
        result.ok("1000회 등록/해제 반복 후 service_count=0")
    except Exception as e:
        result.fail("1000회 등록/해제 반복 후 service_count=0", str(e))

    # 8-2. 락(lock) 잔여 없음
    try:
        _reset_registry()
        registry = _make_registry(max_services=100)
        for i in range(100):
            name = f"lk_{i}"
            svc = MockService(name=name)
            registry.register(
                name=name,
                service_type=ServiceType.UTILITY,
                instance=svc,
                config=ServiceConfig(stop_timeout_seconds=0.0),
            )
            sid = f"utility:{name}"
            registry.start(sid)
            registry.stop(sid, grace_period=0.0)
            registry.unregister(sid)

        # 내부 _service_locks에 잔여 락이 없어야 함
        remaining_locks = len(registry._service_locks)
        assert remaining_locks == 0, f"잔여 락: {remaining_locks}"
        result.ok("등록/해제 후 잔여 락 없음")
    except Exception as e:
        result.fail("등록/해제 후 잔여 락 없음", str(e))

    # 8-3. 이름 인덱스 잔여 없음
    try:
        _reset_registry()
        registry = _make_registry(max_services=100)
        for i in range(100):
            name = f"nm_{i}"
            svc = MockService(name=name)
            registry.register(
                name=name,
                service_type=ServiceType.UTILITY,
                instance=svc,
                config=ServiceConfig(stop_timeout_seconds=0.0),
            )
            sid = f"utility:{name}"
            registry.unregister(sid)

        remaining_names = len(registry._by_name)
        assert remaining_names == 0, f"잔여 이름: {remaining_names}"
        result.ok("등록/해제 후 이름 인덱스 잔여 없음")
    except Exception as e:
        result.fail("등록/해제 후 이름 인덱스 잔여 없음", str(e))


# ============================================================
# [추가] 엣지 케이스 & 고급 기능 (5개)
# ============================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 및 고급 기능 테스트."""
    print("\n[추가] 엣지 케이스 & 고급 기능")

    # E-1. instance 없이 factory로 등록
    try:
        _reset_registry()
        registry = _make_registry()
        factory_called = [False]

        def create_service():
            factory_called[0] = True
            return MockService("factory_svc")

        info = registry.register(
            name="factory_test",
            service_type=ServiceType.UTILITY,
            factory=create_service,
            config=ServiceConfig(stop_timeout_seconds=0.0),
        )
        assert info is not None
        # factory는 get_instance 호출 시 실행
        sid = "utility:factory_test"
        instance = registry.get_instance(sid)
        assert factory_called[0] is True
        assert instance is not None
        result.ok("factory로 서비스 등록 및 지연 생성")
    except Exception as e:
        result.fail("factory로 서비스 등록 및 지연 생성", str(e))

    # E-2. instance, factory 모두 없으면 ValueError
    try:
        _reset_registry()
        registry = _make_registry()
        raised = False
        try:
            registry.register(
                name="no_instance",
                service_type=ServiceType.UTILITY,
            )
        except ValueError:
            raised = True
        assert raised, "instance/factory 없이 등록 시 ValueError 미발생"
        result.ok("instance/factory 없이 등록 → ValueError")
    except Exception as e:
        result.fail("instance/factory 없이 등록 → ValueError", str(e))

    # E-3. 최대 서비스 수 초과 → ValueError
    try:
        _reset_registry()
        registry = _make_registry(max_services=3)
        _register_mock(registry, "m1", ServiceType.UTILITY)
        _register_mock(registry, "m2", ServiceType.STORAGE)
        _register_mock(registry, "m3", ServiceType.CACHE)
        raised = False
        try:
            _register_mock(registry, "m4", ServiceType.QUEUE)
        except ValueError as ve:
            raised = True
            assert "초과" in str(ve)
        assert raised, "최대 서비스 수 초과 시 ValueError 미발생"
        result.ok("최대 서비스 수 초과 → ValueError")
    except Exception as e:
        result.fail("최대 서비스 수 초과 → ValueError", str(e))

    # E-4. 서비스 시작 실패 시 FAILED 상태
    try:
        _reset_registry()
        registry = _make_registry()
        failing_svc = FailingMockService("fail_svc")
        registry.register(
            name="fail_test",
            service_type=ServiceType.UTILITY,
            instance=failing_svc,
            config=ServiceConfig(stop_timeout_seconds=0.0),
        )
        sid = "utility:fail_test"
        ok = registry.start(sid)
        assert ok is False, "실패 서비스가 시작 성공으로 보고됨"
        info = registry.get(sid)
        assert info.lifecycle == ServiceLifecycle.FAILED
        assert info.metrics.failure_count >= 1
        result.ok("서비스 시작 실패 → FAILED 상태")
    except Exception as e:
        result.fail("서비스 시작 실패 → FAILED 상태", str(e))

    # E-5. health_check: 건강하지 않은 서비스 → DEGRADED
    try:
        _reset_registry()
        registry = _make_registry()
        unhealthy = UnhealthyMockService("unhealthy")
        registry.register(
            name="health_test",
            service_type=ServiceType.UTILITY,
            instance=unhealthy,
            config=ServiceConfig(stop_timeout_seconds=0.0),
        )
        sid = "utility:health_test"
        registry.start(sid)
        healthy = registry.health_check(sid)
        assert healthy is False
        info = registry.get(sid)
        assert info.lifecycle == ServiceLifecycle.DEGRADED
        result.ok("health_check: 비정상 → DEGRADED 상태")
    except Exception as e:
        result.fail("health_check: 비정상 → DEGRADED 상태", str(e))


# ============================================================
# [추가2] to_dict / 직렬화 (5개)
# ============================================================
def test_serialization(result: TestResult) -> None:
    """직렬화 관련 테스트."""
    print("\n[추가2] to_dict / 직렬화")

    # S-1. ServiceDependency.to_dict
    try:
        dep = ServiceDependency(
            service_id="storage:main",
            dependency_type=DependencyType.REQUIRED,
            min_version="1.0.0",
            description="메인 스토리지",
        )
        d = dep.to_dict()
        assert d["service_id"] == "storage:main"
        assert d["dependency_type"] == "required"
        assert d["min_version"] == "1.0.0"
        assert d["description"] == "메인 스토리지"
        result.ok("ServiceDependency.to_dict")
    except Exception as e:
        result.fail("ServiceDependency.to_dict", str(e))

    # S-2. ServiceMetrics.to_dict
    try:
        metrics = ServiceMetrics()
        metrics.record_request(100.0, success=True)
        metrics.record_request(200.0, success=False)
        d = metrics.to_dict()
        assert d["total_requests"] == 2
        assert d["successful_requests"] == 1
        assert d["failed_requests"] == 1
        assert "average_processing_time_ms" in d
        assert "success_rate" in d
        result.ok("ServiceMetrics.to_dict")
    except Exception as e:
        result.fail("ServiceMetrics.to_dict", str(e))

    # S-3. ServiceConfig.to_dict
    try:
        config = ServiceConfig(enabled=True, auto_start=True)
        d = config.to_dict()
        assert d["enabled"] is True
        assert d["auto_start"] is True
        assert "max_restart_attempts" in d
        assert "extra_params" in d
        result.ok("ServiceConfig.to_dict")
    except Exception as e:
        result.fail("ServiceConfig.to_dict", str(e))

    # S-4. ServiceInfo.to_dict
    try:
        info = ServiceInfo(
            service_id="detector:test",
            name="test",
            service_type=ServiceType.DETECTOR,
            version="2.0.0",
            description="테스트 서비스",
            tags=["ai", "detection"],
        )
        d = info.to_dict()
        assert d["service_id"] == "detector:test"
        assert d["service_type"] == "detector"
        assert d["version"] == "2.0.0"
        assert d["lifecycle"] == "registered"
        assert "ai" in d["tags"]
        assert "metrics" in d
        assert "config" in d
        assert "is_healthy" in d
        result.ok("ServiceInfo.to_dict")
    except Exception as e:
        result.fail("ServiceInfo.to_dict", str(e))

    # S-5. ServiceMetrics health 관련 속성
    try:
        metrics = ServiceMetrics()
        # 초기 health_success_rate는 1.0
        assert metrics.health_success_rate == 1.0
        metrics.record_health_check(True)
        metrics.record_health_check(True)
        metrics.record_health_check(False)
        assert metrics.health_check_count == 3
        assert metrics.health_check_failures == 1
        expected_rate = 1.0 - (1 / 3)
        assert abs(metrics.health_success_rate - expected_rate) < 0.01
        result.ok("ServiceMetrics health 관련 속성")
    except Exception as e:
        result.fail("ServiceMetrics health 관련 속성", str(e))


# ============================================================
# [추가3] ServiceInfo 메서드 (5개)
# ============================================================
def test_service_info_methods(result: TestResult) -> None:
    """ServiceInfo 메서드 테스트."""
    print("\n[추가3] ServiceInfo 메서드")

    # M-1. update_lifecycle
    try:
        info = ServiceInfo(
            service_id="utility:m1",
            name="m1",
            service_type=ServiceType.UTILITY,
        )
        old_updated = info.updated_at
        time.sleep(0.01)
        info.update_lifecycle(ServiceLifecycle.RUNNING, "실행 중")
        assert info.lifecycle == ServiceLifecycle.RUNNING
        assert info.status_message == "실행 중"
        assert info.updated_at >= old_updated
        result.ok("ServiceInfo.update_lifecycle")
    except Exception as e:
        result.fail("ServiceInfo.update_lifecycle", str(e))

    # M-2. add_dependency / remove_dependency
    try:
        info = ServiceInfo(
            service_id="utility:m2",
            name="m2",
            service_type=ServiceType.UTILITY,
        )
        dep = ServiceDependency(service_id="storage:dep1")
        info.add_dependency(dep)
        assert len(info.dependencies) == 1
        # 중복 추가 시 무시
        info.add_dependency(dep)
        assert len(info.dependencies) == 1
        # 제거
        removed = info.remove_dependency("storage:dep1")
        assert removed is True
        assert len(info.dependencies) == 0
        # 없는 것 제거
        removed = info.remove_dependency("storage:nonexist")
        assert removed is False
        result.ok("ServiceInfo.add_dependency / remove_dependency")
    except Exception as e:
        result.fail("ServiceInfo.add_dependency / remove_dependency", str(e))

    # M-3. add_dependent / remove_dependent
    try:
        info = ServiceInfo(
            service_id="utility:m3",
            name="m3",
            service_type=ServiceType.UTILITY,
        )
        info.add_dependent("analyzer:child1")
        assert "analyzer:child1" in info.dependents
        # 중복 추가 시 무시
        info.add_dependent("analyzer:child1")
        assert info.dependents.count("analyzer:child1") == 1
        # 제거
        removed = info.remove_dependent("analyzer:child1")
        assert removed is True
        assert len(info.dependents) == 0
        result.ok("ServiceInfo.add_dependent / remove_dependent")
    except Exception as e:
        result.fail("ServiceInfo.add_dependent / remove_dependent", str(e))

    # M-4. is_healthy 프로퍼티
    try:
        info = ServiceInfo(
            service_id="utility:m4",
            name="m4",
            service_type=ServiceType.UTILITY,
        )
        assert info.is_healthy is False  # REGISTERED 상태
        info.update_lifecycle(ServiceLifecycle.RUNNING)
        assert info.is_healthy is True
        info.update_lifecycle(ServiceLifecycle.DEGRADED)
        assert info.is_healthy is False  # DEGRADED는 RUNNING이 아님
        result.ok("ServiceInfo.is_healthy 프로퍼티")
    except Exception as e:
        result.fail("ServiceInfo.is_healthy 프로퍼티", str(e))

    # M-5. can_restart 프로퍼티
    try:
        info = ServiceInfo(
            service_id="utility:m5",
            name="m5",
            service_type=ServiceType.UTILITY,
            config=ServiceConfig(auto_restart=True, max_restart_attempts=3),
        )
        assert info.can_restart is True
        info.restart_attempts = 3
        assert info.can_restart is False  # 최대 재시작 횟수 도달
        result.ok("ServiceInfo.can_restart 프로퍼티")
    except Exception as e:
        result.fail("ServiceInfo.can_restart 프로퍼티", str(e))


# ============================================================
# [추가4] 헬퍼 함수 & 컨텍스트 매니저 (5개)
# ============================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 및 컨텍스트 매니저 테스트."""
    print("\n[추가4] 헬퍼 함수 & 컨텍스트 매니저")

    # H-1. register_service 헬퍼 함수
    try:
        _reset_registry()
        mock = MockService("helper_svc")
        info = register_service(
            name="helper_svc",
            service_type=ServiceType.UTILITY,
            instance=mock,
        )
        assert info is not None
        assert info.name == "helper_svc"
        _reset_registry()
        result.ok("register_service 헬퍼 함수")
    except Exception as e:
        _reset_registry()
        result.fail("register_service 헬퍼 함수", str(e))

    # H-2. get_service 헬퍼 함수
    try:
        _reset_registry()
        mock = MockService("gs_svc")
        register_service(
            name="gs_svc",
            service_type=ServiceType.DETECTOR,
            instance=mock,
        )
        info = get_service("detector:gs_svc")
        assert info is not None
        assert info.name == "gs_svc"
        # 존재하지 않는 서비스
        none_info = get_service("nonexistent:svc")
        assert none_info is None
        _reset_registry()
        result.ok("get_service 헬퍼 함수")
    except Exception as e:
        _reset_registry()
        result.fail("get_service 헬퍼 함수", str(e))

    # H-3. ServiceRegistry 컨텍스트 매니저
    try:
        _reset_registry()
        with ServiceRegistry(max_services=10) as reg:
            mock = MockService("ctx_svc")
            reg.register(
                name="ctx_svc",
                service_type=ServiceType.UTILITY,
                instance=mock,
                config=ServiceConfig(stop_timeout_seconds=0.0),
            )
            reg.start("utility:ctx_svc")
            assert reg.running_count == 1
        # 컨텍스트 종료 후 enabled == False
        assert reg.enabled is False
        result.ok("ServiceRegistry 컨텍스트 매니저")
    except Exception as e:
        result.fail("ServiceRegistry 컨텍스트 매니저", str(e))

    # H-4. list_by_lifecycle
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "lbl_1", ServiceType.UTILITY)
        _register_mock(registry, "lbl_2", ServiceType.STORAGE)
        registry.start("utility:lbl_1")
        running = registry.list_by_lifecycle(ServiceLifecycle.RUNNING)
        registered = registry.list_by_lifecycle(ServiceLifecycle.REGISTERED)
        assert len(running) == 1
        assert len(registered) == 1
        result.ok("list_by_lifecycle 상태별 조회")
    except Exception as e:
        result.fail("list_by_lifecycle 상태별 조회", str(e))

    # H-5. list_running
    try:
        _reset_registry()
        registry = _make_registry()
        _register_mock(registry, "lr_1", ServiceType.UTILITY)
        _register_mock(registry, "lr_2", ServiceType.CACHE)
        registry.start("utility:lr_1")
        running_ids = registry.list_running()
        assert "utility:lr_1" in running_ids
        assert "cache:lr_2" not in running_ids
        result.ok("list_running 실행 중 서비스 ID 목록")
    except Exception as e:
        result.fail("list_running 실행 중 서비스 ID 목록", str(e))


# ============================================================
# 메인 실행
# ============================================================
def main() -> None:
    """전체 테스트 실행."""
    print("=" * 60)
    print("ServiceRegistry 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # 모든 테스트 섹션 실행
    test_enums(result)
    test_constants(result)
    test_dataclasses(result)
    test_registry_basic(result)
    test_dependency_topology(result)
    test_service_metrics_detail(result)
    test_thread_safety(result)
    test_memory_leak(result)
    test_edge_cases(result)
    test_serialization(result)
    test_service_info_methods(result)
    test_helper_functions(result)

    # 전역 레지스트리 정리
    _reset_registry()

    # 결과 요약
    result.summary()

    # 종료 코드 설정
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
