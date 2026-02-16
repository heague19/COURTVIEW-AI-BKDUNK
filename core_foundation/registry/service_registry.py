# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: service_registry.py
설명: 서비스 등록, 검색, 라이프사이클 관리 - 엔터프라이즈급 서비스 레지스트리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 서비스 등록 및 메타데이터 관리
    - 서비스 타입별 검색 및 조회
    - 서비스 라이프사이클 관리 (시작, 중지, 재시작)
    - 서비스 의존성 추적 및 관리
    - 서비스 상태 모니터링
    - 스레드 안전 동시성 지원
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterator,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode
from shared.constants.status_codes import ServiceStatus
from shared.exceptions.infrastructure_exceptions import InfrastructureException
from shared.interfaces.analyzer_interface import IAnalyzer
from shared.interfaces.detector_interface import IDetector

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import get_current_timestamp

# ============================================================
# core_foundation 내부 임포트 (Direct Import)
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.metrics import MetricsCollector


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 공개 API 정의
# ============================================================
__all__ = [
    # Enum (3개)
    "ServiceType",              # Enum: 서비스 타입 (17개 유형, is_ai_service/is_infrastructure/priority 프로퍼티)
    "ServiceLifecycle",         # Enum: 서비스 라이프사이클 (9개 상태, is_active/can_start/can_stop 프로퍼티)
    "DependencyType",           # Enum: 의존성 유형 (REQUIRED, OPTIONAL, LAZY)

    # 상수 - YAML 설정 기본값 (4개)
    "DEFAULT_MAX_SERVICES",           # int: 최대 서비스 수 (기본 100)
    "DEFAULT_SERVICE_TIMEOUT",        # float: 서비스 타임아웃 (기본 30.0초)
    "DEFAULT_HEALTH_CHECK_INTERVAL",  # float: 헬스 체크 간격 (기본 30.0초, YAML 동기화)
    "SERVICE_SHUTDOWN_GRACE_PERIOD",  # float: 종료 유예 기간 (기본 5.0초)

    # 데이터 클래스 (5개)
    "ServiceDependency",        # dataclass: 서비스 의존성 정의
    "ServiceMetrics",           # dataclass: 서비스 메트릭 (시작 횟수, 오류 수, 평균 응답 시간)
    "ServiceConfig",            # dataclass: 서비스 설정 (타임아웃, 재시도, 자동 시작)
    "ServiceInfo",              # dataclass: 서비스 정보 (상태, 메타데이터, 의존성)
    "RegisteredService",        # dataclass: 등록된 서비스 (인스턴스, 메트릭, 설정 포함)

    # 프로토콜 (1개)
    "IService",                 # Protocol: 서비스 인터페이스 (@runtime_checkable)

    # 메인 클래스 (1개)
    "ServiceRegistry",          # class: 서비스 레지스트리 (의존성 그래프, 위상 정렬, 스레드 안전)

    # 헬퍼 함수 (4개)
    "get_service",              # Callable: 서비스 조회 헬퍼 (전역 레지스트리 사용)
    "register_service",         # Callable: 서비스 등록 헬퍼 (전역 레지스트리 사용)
    "_get_registry",            # Callable: 전역 레지스트리 인스턴스 접근 (내부용)
    "_reset_registry",          # Callable: 전역 레지스트리 리셋 (테스트용)
]


# ============================================================
# 설정 로더 (YAML 기반)
# ============================================================
class _ServiceConfigProvider:
    """
    서비스 레지스트리 설정 제공자.

    registry.yaml에서 설정을 로드하여 제공합니다.
    하드코딩된 상수 대신 YAML 설정을 사용합니다.
    """

    _instance: _ServiceConfigProvider | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """초기화."""
        self._config_loader = ConfigLoader.get_instance()
        self._service_config: dict[str, Any] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> "_ServiceConfigProvider":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 초기화 (테스트용)."""
        with cls._lock:
            cls._instance = None

    def _load_config(self) -> None:
        """YAML 설정 로드."""
        try:
            # configs/core_foundation/registry.yaml에서 service_registry 섹션 로드
            registry_config = self._config_loader.get(
                "core_foundation.registry",
                default={}
            )
            self._service_config = registry_config.get("service_registry", {})
            logger.debug("서비스 레지스트리 설정 로드 완료")
        except Exception as e:
            logger.warning(f"서비스 레지스트리 설정 로드 실패, 기본값 사용: {e}")
            self._service_config = {}

    def reload(self) -> None:
        """설정 리로드."""
        self._load_config()

    @property
    def max_services(self) -> int:
        """최대 등록 가능 서비스 수."""
        return self._service_config.get("max_services", 100)

    @property
    def startup_timeout(self) -> float:
        """서비스 시작 타임아웃 (초)."""
        lifecycle = self._service_config.get("lifecycle", {})
        return float(lifecycle.get("startup_timeout", 30.0))

    @property
    def shutdown_timeout(self) -> float:
        """서비스 종료 타임아웃 (초)."""
        lifecycle = self._service_config.get("lifecycle", {})
        return float(lifecycle.get("shutdown_timeout", 15.0))

    @property
    def shutdown_grace_period(self) -> float:
        """종료 유예 기간 (초)."""
        lifecycle = self._service_config.get("lifecycle", {})
        return float(lifecycle.get("graceful_shutdown_delay", 5.0))

    @property
    def health_check_interval(self) -> float:
        """상태 체크 간격 (초)."""
        discovery = self._service_config.get("discovery", {})
        return float(discovery.get("health_check_interval", 60.0))

    @property
    def auto_register(self) -> bool:
        """자동 등록 여부."""
        discovery = self._service_config.get("discovery", {})
        return discovery.get("auto_register", True)

    @property
    def detect_circular(self) -> bool:
        """순환 의존성 감지 여부."""
        dependencies = self._service_config.get("dependencies", {})
        return dependencies.get("detect_circular", True)

    @property
    def allow_optional_deps(self) -> bool:
        """선택적 의존성 허용 여부."""
        dependencies = self._service_config.get("dependencies", {})
        return dependencies.get("allow_optional", True)

    @property
    def on_missing_dependency(self) -> str:
        """누락된 의존성 처리 방식."""
        dependencies = self._service_config.get("dependencies", {})
        return dependencies.get("on_missing", "error")

    @property
    def graceful_shutdown(self) -> bool:
        """그레이스풀 종료 활성화."""
        lifecycle = self._service_config.get("lifecycle", {})
        return lifecycle.get("graceful_shutdown", True)

    @property
    def shutdown_reverse_order(self) -> bool:
        """종료 시 역순 사용 여부."""
        lifecycle = self._service_config.get("lifecycle", {})
        return lifecycle.get("shutdown_reverse", True)

    def get_startup_order(self) -> dict[str, int]:
        """서비스 타입별 시작 순서."""
        lifecycle = self._service_config.get("lifecycle", {})
        return lifecycle.get("startup_order", {})

    def get_config(self) -> dict[str, Any]:
        """전체 설정 반환."""
        return self._service_config.copy()


# ============================================================
# 설정 접근 함수 (YAML 설정 기반)
# ============================================================
def _get_config_provider() -> _ServiceConfigProvider:
    """설정 제공자 인스턴스 반환."""
    return _ServiceConfigProvider.get_instance()


# YAML 설정에서 로드하는 동적 상수 접근 함수
def _get_default_max_services() -> int:
    """최대 등록 서비스 수 (YAML 설정)."""
    return _get_config_provider().max_services


def _get_default_service_timeout() -> float:
    """서비스 시작 타임아웃 (YAML 설정)."""
    return _get_config_provider().startup_timeout


def _get_default_health_check_interval() -> float:
    """상태 체크 간격 (YAML 설정)."""
    return _get_config_provider().health_check_interval


def _get_shutdown_grace_period() -> float:
    """종료 유예 기간 (YAML 설정)."""
    return _get_config_provider().shutdown_grace_period


# ============================================================
# 상수 (호환성 유지, 런타임에 YAML에서 재로드)
# ============================================================
DEFAULT_MAX_SERVICES: int = 100  # 초기값, 런타임에 YAML에서 재로드
DEFAULT_SERVICE_TIMEOUT: float = 30.0  # 초기값, 런타임에 YAML에서 재로드
DEFAULT_HEALTH_CHECK_INTERVAL: float = 30.0  # 초기값, 런타임에 YAML에서 재로드
SERVICE_SHUTDOWN_GRACE_PERIOD: float = 5.0  # 초기값, 런타임에 YAML에서 재로드


# ============================================================
# Enum 정의
# ============================================================
class ServiceType(str, Enum):
    """
    서비스 타입.

    플랫폼에서 사용되는 서비스 종류를 정의합니다.
    """

    # 핵심 AI 서비스
    DETECTOR = "detector"  # 객체 탐지기 (공, 사람, 코트)
    POSE_ESTIMATOR = "pose_estimator"  # 포즈 추정기
    TRACKER = "tracker"  # 객체 추적기

    # 분석 서비스
    ANALYZER = "analyzer"  # 일반 분석기
    MOTION_ANALYZER = "motion_analyzer"  # 동작 분석기
    GAME_ANALYZER = "game_analyzer"  # 경기 분석기
    SHOOTING_ANALYZER = "shooting_analyzer"  # 슈팅 분석기
    DRIBBLING_ANALYZER = "dribbling_analyzer"  # 드리블 분석기

    # 인프라 서비스
    STORAGE = "storage"  # 스토리지 서비스
    CACHE = "cache"  # 캐시 서비스
    QUEUE = "queue"  # 큐 서비스
    NOTIFICATION = "notification"  # 알림 서비스

    # 심판 서비스
    REFEREE = "referee"  # AI 심판
    FOUL_DETECTOR = "foul_detector"  # 파울 탐지기
    VIOLATION_DETECTOR = "violation_detector"  # 바이올레이션 탐지기

    # 피드백 서비스
    FEEDBACK_GENERATOR = "feedback_generator"  # 피드백 생성기
    REPORT_GENERATOR = "report_generator"  # 리포트 생성기

    # 기타
    UTILITY = "utility"  # 유틸리티 서비스
    CUSTOM = "custom"  # 커스텀 서비스

    @property
    def is_ai_service(self) -> bool:
        """AI 관련 서비스 여부."""
        ai_types = {
            ServiceType.DETECTOR,
            ServiceType.POSE_ESTIMATOR,
            ServiceType.TRACKER,
            ServiceType.ANALYZER,
            ServiceType.MOTION_ANALYZER,
            ServiceType.GAME_ANALYZER,
            ServiceType.SHOOTING_ANALYZER,
            ServiceType.DRIBBLING_ANALYZER,
            ServiceType.REFEREE,
            ServiceType.FOUL_DETECTOR,
            ServiceType.VIOLATION_DETECTOR,
        }
        return self in ai_types

    @property
    def is_infrastructure(self) -> bool:
        """인프라 서비스 여부."""
        infra_types = {
            ServiceType.STORAGE,
            ServiceType.CACHE,
            ServiceType.QUEUE,
            ServiceType.NOTIFICATION,
        }
        return self in infra_types

    @property
    def priority(self) -> int:
        """서비스 시작 우선순위 (낮을수록 먼저 시작)."""
        priorities = {
            ServiceType.STORAGE: 1,
            ServiceType.CACHE: 2,
            ServiceType.QUEUE: 3,
            ServiceType.NOTIFICATION: 4,
            ServiceType.DETECTOR: 10,
            ServiceType.POSE_ESTIMATOR: 11,
            ServiceType.TRACKER: 12,
            ServiceType.ANALYZER: 20,
            ServiceType.MOTION_ANALYZER: 21,
            ServiceType.SHOOTING_ANALYZER: 22,
            ServiceType.DRIBBLING_ANALYZER: 23,
            ServiceType.GAME_ANALYZER: 24,
            ServiceType.REFEREE: 30,
            ServiceType.FOUL_DETECTOR: 31,
            ServiceType.VIOLATION_DETECTOR: 32,
            ServiceType.FEEDBACK_GENERATOR: 40,
            ServiceType.REPORT_GENERATOR: 41,
            ServiceType.UTILITY: 50,
            ServiceType.CUSTOM: 100,
        }
        return priorities.get(self, 100)


class ServiceLifecycle(str, Enum):
    """
    서비스 라이프사이클 상태.

    서비스의 생명주기 상태를 정의합니다.
    """

    REGISTERED = "registered"  # 등록됨 (아직 시작 안함)
    INITIALIZING = "initializing"  # 초기화 중
    STARTING = "starting"  # 시작 중
    RUNNING = "running"  # 실행 중
    PAUSED = "paused"  # 일시 중지
    STOPPING = "stopping"  # 중지 중
    STOPPED = "stopped"  # 중지됨
    FAILED = "failed"  # 실패
    DEGRADED = "degraded"  # 성능 저하

    @property
    def is_active(self) -> bool:
        """활성 상태 여부."""
        return self in {
            ServiceLifecycle.RUNNING,
            ServiceLifecycle.DEGRADED,
        }

    @property
    def is_transitioning(self) -> bool:
        """전환 중 상태 여부."""
        return self in {
            ServiceLifecycle.INITIALIZING,
            ServiceLifecycle.STARTING,
            ServiceLifecycle.STOPPING,
        }

    @property
    def can_start(self) -> bool:
        """시작 가능 여부."""
        return self in {
            ServiceLifecycle.REGISTERED,
            ServiceLifecycle.STOPPED,
            ServiceLifecycle.FAILED,
        }

    @property
    def can_stop(self) -> bool:
        """중지 가능 여부."""
        return self in {
            ServiceLifecycle.RUNNING,
            ServiceLifecycle.PAUSED,
            ServiceLifecycle.DEGRADED,
        }


class DependencyType(str, Enum):
    """
    의존성 타입.

    서비스 간 의존성 종류를 정의합니다.
    """

    REQUIRED = "required"  # 필수 의존성 (없으면 시작 불가)
    OPTIONAL = "optional"  # 선택적 의존성 (없어도 시작 가능)
    LAZY = "lazy"  # 지연 로드 의존성 (필요할 때 로드)


# ============================================================
# 서비스 인터페이스 프로토콜
# ============================================================
@runtime_checkable
class IService(Protocol):
    """
    서비스 인터페이스 프로토콜.

    레지스트리에 등록되는 모든 서비스가 구현해야 하는 프로토콜입니다.
    """

    @property
    def service_name(self) -> str:
        """서비스 이름."""
        ...

    @property
    def service_type(self) -> ServiceType:
        """서비스 타입."""
        ...

    def initialize(self) -> None:
        """서비스 초기화."""
        ...

    def start(self) -> None:
        """서비스 시작."""
        ...

    def stop(self) -> None:
        """서비스 중지."""
        ...

    def health_check(self) -> bool:
        """상태 체크."""
        ...


ServiceT = TypeVar("ServiceT", bound=IService)


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class ServiceDependency:
    """
    서비스 의존성 정보.

    서비스 간의 의존 관계를 정의합니다.
    """

    service_id: str  # 의존하는 서비스 ID
    dependency_type: DependencyType = DependencyType.REQUIRED
    min_version: str | None = None  # 최소 버전 요구사항
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "service_id": self.service_id,
            "dependency_type": self.dependency_type.value,
            "min_version": self.min_version,
            "description": self.description,
        }


@dataclass
class ServiceMetrics:
    """
    서비스 메트릭.

    서비스의 성능 및 사용 통계를 추적합니다.
    """

    # 요청 통계
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # 처리 시간
    total_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float("inf")
    max_processing_time_ms: float = 0.0
    last_processing_time_ms: float = 0.0

    # 상태 체크
    health_check_count: int = 0
    health_check_failures: int = 0
    last_health_check: datetime | None = None
    last_health_status: bool = True

    # 라이프사이클
    start_count: int = 0
    stop_count: int = 0
    restart_count: int = 0
    failure_count: int = 0

    # 시간
    total_uptime_seconds: float = 0.0
    last_started_at: datetime | None = None
    last_stopped_at: datetime | None = None

    # 에러
    last_error: str | None = None
    last_error_at: datetime | None = None

    def record_request(
        self,
        duration_ms: float,
        success: bool = True,
    ) -> None:
        """요청 결과 기록."""
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_processing_time_ms += duration_ms
        self.last_processing_time_ms = duration_ms
        self.min_processing_time_ms = min(self.min_processing_time_ms, duration_ms)
        self.max_processing_time_ms = max(self.max_processing_time_ms, duration_ms)

    def record_health_check(self, healthy: bool) -> None:
        """상태 체크 결과 기록."""
        self.health_check_count += 1
        self.last_health_check = datetime.now(timezone.utc)
        self.last_health_status = healthy

        if not healthy:
            self.health_check_failures += 1

    def record_start(self) -> None:
        """서비스 시작 기록."""
        self.start_count += 1
        self.last_started_at = datetime.now(timezone.utc)

    def record_stop(self) -> None:
        """서비스 중지 기록."""
        self.stop_count += 1
        now = datetime.now(timezone.utc)
        self.last_stopped_at = now

        # 가동 시간 계산
        if self.last_started_at:
            uptime = (now - self.last_started_at).total_seconds()
            self.total_uptime_seconds += uptime

    def record_restart(self) -> None:
        """서비스 재시작 기록."""
        self.restart_count += 1

    def record_failure(self, error_message: str) -> None:
        """실패 기록."""
        self.failure_count += 1
        self.last_error = error_message
        self.last_error_at = datetime.now(timezone.utc)

    @property
    def average_processing_time_ms(self) -> float:
        """평균 처리 시간."""
        if self.total_requests == 0:
            return 0.0
        return self.total_processing_time_ms / self.total_requests

    @property
    def success_rate(self) -> float:
        """성공률 (0~1)."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def health_success_rate(self) -> float:
        """상태 체크 성공률."""
        if self.health_check_count == 0:
            return 1.0
        return 1.0 - (self.health_check_failures / self.health_check_count)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "average_processing_time_ms": round(self.average_processing_time_ms, 3),
            "min_processing_time_ms": round(self.min_processing_time_ms, 3)
            if self.min_processing_time_ms != float("inf")
            else None,
            "max_processing_time_ms": round(self.max_processing_time_ms, 3),
            "success_rate": round(self.success_rate, 4),
            "health_check_count": self.health_check_count,
            "health_success_rate": round(self.health_success_rate, 4),
            "start_count": self.start_count,
            "stop_count": self.stop_count,
            "restart_count": self.restart_count,
            "failure_count": self.failure_count,
            "total_uptime_seconds": round(self.total_uptime_seconds, 2),
            "last_error": self.last_error,
        }


@dataclass
class ServiceConfig:
    """
    서비스 설정.

    서비스 실행에 필요한 설정을 정의합니다.
    """

    # 기본 설정
    enabled: bool = True
    auto_start: bool = False
    auto_restart: bool = True
    max_restart_attempts: int = 3
    restart_delay_seconds: float = 5.0

    # 타임아웃 설정
    start_timeout_seconds: float = DEFAULT_SERVICE_TIMEOUT
    stop_timeout_seconds: float = SERVICE_SHUTDOWN_GRACE_PERIOD
    health_check_interval_seconds: float = DEFAULT_HEALTH_CHECK_INTERVAL

    # 리소스 설정
    max_concurrent_requests: int = 100
    request_timeout_seconds: float = 30.0

    # 추가 파라미터
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "auto_restart": self.auto_restart,
            "max_restart_attempts": self.max_restart_attempts,
            "restart_delay_seconds": self.restart_delay_seconds,
            "start_timeout_seconds": self.start_timeout_seconds,
            "stop_timeout_seconds": self.stop_timeout_seconds,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "max_concurrent_requests": self.max_concurrent_requests,
            "request_timeout_seconds": self.request_timeout_seconds,
            "extra_params": self.extra_params,
        }


@dataclass
class ServiceInfo:
    """
    서비스 정보.

    서비스의 전체 메타데이터를 포함합니다.
    """

    # 식별 정보
    service_id: str
    name: str
    service_type: ServiceType
    version: str = "1.0.0"

    # 상태
    lifecycle: ServiceLifecycle = ServiceLifecycle.REGISTERED
    status_message: str | None = None

    # 메타데이터
    description: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 의존성
    dependencies: list[ServiceDependency] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)  # 이 서비스에 의존하는 서비스

    # 설정
    config: ServiceConfig = field(default_factory=ServiceConfig)

    # 메트릭
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)

    # 타임스탬프
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 재시작 카운터
    restart_attempts: int = 0

    def update_lifecycle(
        self,
        lifecycle: ServiceLifecycle,
        message: str | None = None,
    ) -> None:
        """라이프사이클 상태 업데이트."""
        self.lifecycle = lifecycle
        self.status_message = message
        self.updated_at = datetime.now(timezone.utc)

    def add_dependency(self, dependency: ServiceDependency) -> None:
        """의존성 추가."""
        # 중복 체크
        for dep in self.dependencies:
            if dep.service_id == dependency.service_id:
                return
        self.dependencies.append(dependency)
        self.updated_at = datetime.now(timezone.utc)

    def remove_dependency(self, service_id: str) -> bool:
        """의존성 제거."""
        for i, dep in enumerate(self.dependencies):
            if dep.service_id == service_id:
                self.dependencies.pop(i)
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False

    def add_dependent(self, service_id: str) -> None:
        """의존자 추가."""
        if service_id not in self.dependents:
            self.dependents.append(service_id)
            self.updated_at = datetime.now(timezone.utc)

    def remove_dependent(self, service_id: str) -> bool:
        """의존자 제거."""
        if service_id in self.dependents:
            self.dependents.remove(service_id)
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False

    @property
    def is_healthy(self) -> bool:
        """서비스 정상 여부."""
        return self.lifecycle == ServiceLifecycle.RUNNING

    @property
    def can_restart(self) -> bool:
        """재시작 가능 여부."""
        return (
            self.config.auto_restart
            and self.restart_attempts < self.config.max_restart_attempts
        )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "service_id": self.service_id,
            "name": self.name,
            "service_type": self.service_type.value,
            "version": self.version,
            "lifecycle": self.lifecycle.value,
            "status_message": self.status_message,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "metadata": self.metadata,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "dependents": self.dependents,
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_healthy": self.is_healthy,
        }


@dataclass
class RegisteredService(Generic[ServiceT]):
    """
    등록된 서비스 래퍼.

    서비스 인스턴스와 메타데이터를 래핑합니다.
    """

    service_info: ServiceInfo
    service_instance: ServiceT | None = None
    service_factory: Callable[[], ServiceT] | None = None

    # 락 (동시 접근 제어)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def service_id(self) -> str:
        """서비스 ID."""
        return self.service_info.service_id

    @property
    def lifecycle(self) -> ServiceLifecycle:
        """라이프사이클 상태."""
        return self.service_info.lifecycle

    @property
    def is_running(self) -> bool:
        """실행 중 여부."""
        return self.service_info.lifecycle.is_active

    def get_instance(self) -> ServiceT | None:
        """서비스 인스턴스 가져오기."""
        with self._lock:
            if self.service_instance is None and self.service_factory:
                self.service_instance = self.service_factory()
            return self.service_instance

    @contextmanager
    def acquire(self) -> Iterator[ServiceT | None]:
        """서비스 사용을 위한 컨텍스트 매니저."""
        with self._lock:
            yield self.get_instance()


# ============================================================
# 서비스 레지스트리 메인 클래스
# ============================================================
class ServiceRegistry:
    """
    서비스 레지스트리.

    서비스의 등록, 검색, 라이프사이클 관리를 담당합니다.
    싱글톤 패턴은 사용하지 않고 DI 컨테이너를 통해 관리됩니다.

    Args:
        config_loader: 설정 로더 (Direct Import)
        metrics_collector: 메트릭 수집기 (DI 주입, Optional)
        max_services: 최대 등록 서비스 수
        enable_health_check: 상태 체크 활성화

    Example:
        >>> registry = ServiceRegistry(
        ...     config_loader=config_loader,
        ...     metrics_collector=metrics_collector,
        ... )
        >>> registry.register(
        ...     name="ball_detector",
        ...     service_type=ServiceType.DETECTOR,
        ...     instance=detector,
        ... )
        >>> registry.start("ball_detector")
        >>> service = registry.get("ball_detector")
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        metrics_collector: MetricsCollector | None = None,
        max_services: int | None = None,
        enable_health_check: bool | None = None,
    ) -> None:
        """초기화."""
        # 설정 제공자
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._config_provider = _get_config_provider()
        self._metrics_collector = metrics_collector

        # YAML 설정에서 로드 (명시적 값이 없으면)
        self._max_services = (
            max_services if max_services is not None
            else self._config_provider.max_services
        )
        self._enable_health_check = (
            enable_health_check if enable_health_check is not None
            else True  # 기본값
        )

        # 저장소
        self._services: dict[str, RegisteredService] = {}
        self._by_type: dict[ServiceType, set[str]] = {}
        self._by_name: dict[str, str] = {}  # name -> service_id

        # 의존성 그래프
        self._dependency_graph: dict[str, set[str]] = {}  # service_id -> dependencies
        self._reverse_graph: dict[str, set[str]] = {}  # service_id -> dependents

        # 상태
        self._enabled = True
        self._shutdown = False

        # 스레드 안전성
        self._lock = threading.RLock()
        self._service_locks: dict[str, threading.RLock] = {}

        # 상태 체크 스레드
        self._health_check_thread: threading.Thread | None = None
        self._health_check_stop_event = threading.Event()

        # 메트릭 설정
        self._setup_metrics()

        logger.info(
            f"ServiceRegistry 초기화 완료: "
            f"max_services={self._max_services}, "
            f"health_check={self._enable_health_check}, "
            f"startup_timeout={self._config_provider.startup_timeout}s, "
            f"graceful_shutdown={self._config_provider.graceful_shutdown}"
        )

    def reload_config(self) -> None:
        """설정 리로드."""
        self._config_provider.reload()
        logger.info("서비스 레지스트리 설정 리로드 완료")

    def _setup_metrics(self) -> None:
        """메트릭 설정."""
        if self._metrics_collector is None:
            return

        # 카운터
        self._register_counter = self._metrics_collector.counter(
            "service_registry_registrations_total",
            "Total service registrations",
        )
        self._start_counter = self._metrics_collector.counter(
            "service_registry_starts_total",
            "Total service starts",
        )
        self._stop_counter = self._metrics_collector.counter(
            "service_registry_stops_total",
            "Total service stops",
        )

        # 게이지
        self._registered_gauge = self._metrics_collector.gauge(
            "service_registry_registered_services",
            "Number of registered services",
        )
        self._running_gauge = self._metrics_collector.gauge(
            "service_registry_running_services",
            "Number of running services",
        )

    def _get_service_lock(self, service_id: str) -> threading.RLock:
        """서비스별 락 가져오기."""
        with self._lock:
            if service_id not in self._service_locks:
                self._service_locks[service_id] = threading.RLock()
            return self._service_locks[service_id]

    def _generate_service_id(self, name: str, service_type: ServiceType) -> str:
        """서비스 ID 생성."""
        return f"{service_type.value}:{name}"

    # ============================================================
    # 등록 관리
    # ============================================================
    def register(
        self,
        name: str,
        service_type: ServiceType,
        instance: IService | None = None,
        factory: Callable[[], IService] | None = None,
        version: str = "1.0.0",
        description: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        config: ServiceConfig | None = None,
        dependencies: list[ServiceDependency] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ServiceInfo:
        """
        서비스 등록.

        Args:
            name: 서비스 이름
            service_type: 서비스 타입
            instance: 서비스 인스턴스 (instance 또는 factory 중 하나 필수)
            factory: 서비스 팩토리 함수
            version: 버전
            description: 설명
            author: 작성자
            tags: 태그 목록
            config: 서비스 설정
            dependencies: 의존성 목록
            metadata: 추가 메타데이터

        Returns:
            등록된 서비스 정보

        Raises:
            ValueError: 중복 등록 또는 최대 개수 초과
        """
        if instance is None and factory is None:
            raise ValueError("instance 또는 factory 중 하나는 필수입니다")

        with self._lock:
            # 서비스 ID 생성
            service_id = self._generate_service_id(name, service_type)

            # 중복 체크
            if service_id in self._services:
                raise ValueError(f"서비스가 이미 등록되어 있습니다: {service_id}")

            # 최대 개수 체크
            if len(self._services) >= self._max_services:
                raise ValueError(
                    f"최대 등록 가능 서비스 수 초과: {self._max_services}"
                )

            # ServiceInfo 생성
            service_info = ServiceInfo(
                service_id=service_id,
                name=name,
                service_type=service_type,
                version=version,
                description=description,
                author=author,
                tags=tags or [],
                config=config or ServiceConfig(),
                dependencies=dependencies or [],
                metadata=metadata or {},
            )

            # RegisteredService 생성
            registered = RegisteredService(
                service_info=service_info,
                service_instance=instance,
                service_factory=factory,
            )

            # 저장
            self._services[service_id] = registered

            # 타입별 인덱스
            if service_type not in self._by_type:
                self._by_type[service_type] = set()
            self._by_type[service_type].add(service_id)

            # 이름 인덱스
            self._by_name[name] = service_id

            # 의존성 그래프 업데이트
            self._update_dependency_graph(service_info)

            # 메트릭 업데이트
            if self._metrics_collector:
                self._register_counter.inc(1, {"service_type": service_type.value})
                self._registered_gauge.set(len(self._services))

            logger.info(f"서비스 등록 완료: {service_id}")
            return service_info

    def _update_dependency_graph(self, service_info: ServiceInfo) -> None:
        """의존성 그래프 업데이트."""
        service_id = service_info.service_id

        # 이 서비스의 의존성 추가
        self._dependency_graph[service_id] = set()
        for dep in service_info.dependencies:
            self._dependency_graph[service_id].add(dep.service_id)

            # 역방향 그래프 업데이트
            if dep.service_id not in self._reverse_graph:
                self._reverse_graph[dep.service_id] = set()
            self._reverse_graph[dep.service_id].add(service_id)

            # 의존 대상 서비스의 dependents 업데이트
            if dep.service_id in self._services:
                self._services[dep.service_id].service_info.add_dependent(service_id)

    def unregister(self, service_id: str) -> bool:
        """
        서비스 등록 해제.

        실행 중인 서비스는 먼저 중지됩니다.

        Args:
            service_id: 서비스 ID

        Returns:
            성공 여부
        """
        with self._lock:
            if service_id not in self._services:
                return False

            registered = self._services[service_id]
            service_info = registered.service_info

            # 의존자 체크
            if service_info.dependents:
                logger.warning(
                    f"서비스 {service_id}에 의존하는 서비스가 있습니다: "
                    f"{service_info.dependents}"
                )

            # 실행 중이면 중지
            if registered.is_running:
                self.stop(service_id)

            # 저장소에서 제거
            del self._services[service_id]

            # 타입별 인덱스에서 제거
            if service_info.service_type in self._by_type:
                self._by_type[service_info.service_type].discard(service_id)

            # 이름 인덱스에서 제거
            if service_info.name in self._by_name:
                del self._by_name[service_info.name]

            # 의존성 그래프에서 제거
            if service_id in self._dependency_graph:
                del self._dependency_graph[service_id]
            if service_id in self._reverse_graph:
                del self._reverse_graph[service_id]

            # 다른 서비스의 의존성에서 제거
            for other_id, deps in self._dependency_graph.items():
                deps.discard(service_id)
            for other_id, deps in self._reverse_graph.items():
                deps.discard(service_id)

            # 락 정리
            if service_id in self._service_locks:
                del self._service_locks[service_id]

            # 메트릭 업데이트
            if self._metrics_collector:
                self._registered_gauge.set(len(self._services))

            logger.info(f"서비스 등록 해제: {service_id}")
            return True

    # ============================================================
    # 조회
    # ============================================================
    def get(self, service_id: str) -> ServiceInfo | None:
        """
        서비스 정보 조회.

        Args:
            service_id: 서비스 ID

        Returns:
            서비스 정보 (없으면 None)
        """
        registered = self._services.get(service_id)
        return registered.service_info if registered else None

    def get_instance(self, service_id: str) -> IService | None:
        """
        서비스 인스턴스 조회.

        Args:
            service_id: 서비스 ID

        Returns:
            서비스 인스턴스 (없으면 None)
        """
        registered = self._services.get(service_id)
        if registered:
            return registered.get_instance()
        return None

    def get_by_name(self, name: str) -> ServiceInfo | None:
        """
        이름으로 서비스 조회.

        Args:
            name: 서비스 이름

        Returns:
            서비스 정보 (없으면 None)
        """
        service_id = self._by_name.get(name)
        if service_id:
            return self.get(service_id)
        return None

    def list_all(self) -> list[ServiceInfo]:
        """
        모든 등록된 서비스 목록.

        Returns:
            서비스 정보 목록
        """
        return [r.service_info for r in self._services.values()]

    def list_by_type(self, service_type: ServiceType) -> list[ServiceInfo]:
        """
        타입별 서비스 목록.

        Args:
            service_type: 서비스 타입

        Returns:
            해당 타입의 서비스 정보 목록
        """
        service_ids = self._by_type.get(service_type, set())
        return [
            self._services[sid].service_info
            for sid in service_ids
            if sid in self._services
        ]

    def list_by_lifecycle(self, lifecycle: ServiceLifecycle) -> list[ServiceInfo]:
        """
        라이프사이클 상태별 서비스 목록.

        Args:
            lifecycle: 라이프사이클 상태

        Returns:
            해당 상태의 서비스 정보 목록
        """
        return [
            r.service_info
            for r in self._services.values()
            if r.service_info.lifecycle == lifecycle
        ]

    def list_running(self) -> list[str]:
        """
        실행 중인 서비스 ID 목록.

        Returns:
            서비스 ID 목록
        """
        return [
            sid for sid, r in self._services.items() if r.service_info.lifecycle.is_active
        ]

    # ============================================================
    # 라이프사이클 관리
    # ============================================================
    def start(self, service_id: str) -> bool:
        """
        서비스 시작.

        Args:
            service_id: 서비스 ID

        Returns:
            성공 여부
        """
        service_lock = self._get_service_lock(service_id)

        with service_lock:
            registered = self._services.get(service_id)
            if not registered:
                logger.error(f"등록되지 않은 서비스: {service_id}")
                return False

            service_info = registered.service_info

            # 시작 가능 여부 체크
            if not service_info.lifecycle.can_start:
                logger.warning(
                    f"서비스를 시작할 수 없는 상태: {service_id} "
                    f"(현재: {service_info.lifecycle.value})"
                )
                return False

            # 의존성 체크
            if not self._check_dependencies(service_id):
                logger.error(f"의존성 체크 실패: {service_id}")
                return False

            try:
                # 초기화
                service_info.update_lifecycle(
                    ServiceLifecycle.INITIALIZING, "서비스 초기화 중..."
                )

                instance = registered.get_instance()
                if instance and hasattr(instance, "initialize"):
                    instance.initialize()

                # 시작
                service_info.update_lifecycle(
                    ServiceLifecycle.STARTING, "서비스 시작 중..."
                )

                if instance and hasattr(instance, "start"):
                    instance.start()

                # 시작 완료
                service_info.update_lifecycle(
                    ServiceLifecycle.RUNNING, "서비스 실행 중"
                )
                service_info.metrics.record_start()
                service_info.restart_attempts = 0  # 재시작 카운터 초기화

                # 메트릭 업데이트
                if self._metrics_collector:
                    self._start_counter.inc(
                        1, {"service_type": service_info.service_type.value}
                    )
                    self._running_gauge.set(len(self.list_running()))

                logger.info(f"서비스 시작 완료: {service_id}")
                return True

            except Exception as e:
                error_msg = str(e)
                service_info.update_lifecycle(ServiceLifecycle.FAILED, error_msg)
                service_info.metrics.record_failure(error_msg)
                logger.error(f"서비스 시작 실패: {service_id} - {error_msg}")
                return False

    def stop(self, service_id: str, grace_period: float | None = None) -> bool:
        """
        서비스 중지.

        Args:
            service_id: 서비스 ID
            grace_period: 종료 유예 기간 (초)

        Returns:
            성공 여부
        """
        service_lock = self._get_service_lock(service_id)

        with service_lock:
            registered = self._services.get(service_id)
            if not registered:
                logger.error(f"등록되지 않은 서비스: {service_id}")
                return False

            service_info = registered.service_info

            # 중지 가능 여부 체크
            if not service_info.lifecycle.can_stop:
                logger.warning(
                    f"서비스를 중지할 수 없는 상태: {service_id} "
                    f"(현재: {service_info.lifecycle.value})"
                )
                return False

            # 의존자 경고
            if service_info.dependents:
                running_dependents = [
                    d
                    for d in service_info.dependents
                    if d in self._services
                    and self._services[d].service_info.lifecycle.is_active
                ]
                if running_dependents:
                    logger.warning(
                        f"서비스 {service_id}에 의존하는 실행 중인 서비스가 있습니다: "
                        f"{running_dependents}"
                    )

            try:
                # 중지
                service_info.update_lifecycle(
                    ServiceLifecycle.STOPPING, "서비스 중지 중..."
                )

                instance = registered.get_instance()
                if instance and hasattr(instance, "stop"):
                    instance.stop()

                # 유예 기간 대기
                actual_grace = (
                    grace_period
                    if grace_period is not None
                    else service_info.config.stop_timeout_seconds
                )
                if actual_grace > 0:
                    time.sleep(min(actual_grace, 1.0))  # 최대 1초만 대기

                # 중지 완료
                service_info.update_lifecycle(ServiceLifecycle.STOPPED, "서비스 중지됨")
                service_info.metrics.record_stop()

                # 메트릭 업데이트
                if self._metrics_collector:
                    self._stop_counter.inc(
                        1, {"service_type": service_info.service_type.value}
                    )
                    self._running_gauge.set(len(self.list_running()))

                logger.info(f"서비스 중지 완료: {service_id}")
                return True

            except Exception as e:
                error_msg = str(e)
                service_info.update_lifecycle(ServiceLifecycle.FAILED, error_msg)
                service_info.metrics.record_failure(error_msg)
                logger.error(f"서비스 중지 실패: {service_id} - {error_msg}")
                return False

    def restart(self, service_id: str) -> bool:
        """
        서비스 재시작.

        Args:
            service_id: 서비스 ID

        Returns:
            성공 여부
        """
        registered = self._services.get(service_id)
        if not registered:
            logger.error(f"등록되지 않은 서비스: {service_id}")
            return False

        service_info = registered.service_info
        service_info.restart_attempts += 1
        service_info.metrics.record_restart()

        # 중지
        if service_info.lifecycle.is_active:
            if not self.stop(service_id):
                return False

        # 재시작 지연
        time.sleep(service_info.config.restart_delay_seconds)

        # 시작
        return self.start(service_id)

    def _check_dependencies(self, service_id: str) -> bool:
        """의존성 체크."""
        registered = self._services.get(service_id)
        if not registered:
            return False

        for dep in registered.service_info.dependencies:
            if dep.dependency_type == DependencyType.OPTIONAL:
                continue

            dep_service = self._services.get(dep.service_id)
            if not dep_service:
                if dep.dependency_type == DependencyType.REQUIRED:
                    logger.error(
                        f"필수 의존성이 등록되지 않음: {dep.service_id}"
                    )
                    return False
                continue

            if dep.dependency_type == DependencyType.REQUIRED:
                if not dep_service.service_info.lifecycle.is_active:
                    logger.error(
                        f"필수 의존성이 실행 중이 아님: {dep.service_id}"
                    )
                    return False

        return True

    # ============================================================
    # 일괄 관리
    # ============================================================
    def start_all(self, service_type: ServiceType | None = None) -> dict[str, bool]:
        """
        모든 서비스 시작 (우선순위 순서).

        Args:
            service_type: 특정 타입만 시작 (None이면 전체)

        Returns:
            서비스 ID별 성공 여부
        """
        results = {}

        # 대상 서비스 선택
        if service_type:
            services = self.list_by_type(service_type)
        else:
            services = self.list_all()

        # 우선순위 순서로 정렬
        sorted_services = sorted(services, key=lambda s: s.service_type.priority)

        for service_info in sorted_services:
            if service_info.config.enabled and service_info.lifecycle.can_start:
                results[service_info.service_id] = self.start(service_info.service_id)

        return results

    def stop_all(self, service_type: ServiceType | None = None) -> dict[str, bool]:
        """
        모든 서비스 중지 (역우선순위 순서).

        Args:
            service_type: 특정 타입만 중지 (None이면 전체)

        Returns:
            서비스 ID별 성공 여부
        """
        results = {}

        # 대상 서비스 선택
        if service_type:
            services = self.list_by_type(service_type)
        else:
            services = self.list_all()

        # 역우선순위 순서로 정렬 (높은 우선순위부터 중지)
        sorted_services = sorted(
            services, key=lambda s: s.service_type.priority, reverse=True
        )

        for service_info in sorted_services:
            if service_info.lifecycle.can_stop:
                results[service_info.service_id] = self.stop(service_info.service_id)

        return results

    # ============================================================
    # 상태 체크
    # ============================================================
    def health_check(self, service_id: str) -> bool:
        """
        서비스 상태 체크.

        Args:
            service_id: 서비스 ID

        Returns:
            상태 정상 여부
        """
        registered = self._services.get(service_id)
        if not registered:
            return False

        service_info = registered.service_info

        if not service_info.lifecycle.is_active:
            return False

        try:
            instance = registered.get_instance()
            if instance and hasattr(instance, "health_check"):
                healthy = instance.health_check()
            else:
                healthy = True

            service_info.metrics.record_health_check(healthy)

            if not healthy:
                service_info.update_lifecycle(
                    ServiceLifecycle.DEGRADED, "상태 체크 실패"
                )

            return healthy

        except Exception as e:
            service_info.metrics.record_health_check(False)
            service_info.update_lifecycle(
                ServiceLifecycle.DEGRADED, f"상태 체크 예외: {e}"
            )
            return False

    def health_check_all(self) -> dict[str, bool]:
        """
        모든 실행 중인 서비스 상태 체크.

        Returns:
            서비스 ID별 상태
        """
        results = {}

        for service_id in self.list_running():
            results[service_id] = self.health_check(service_id)

        return results

    # ============================================================
    # 의존성 관리
    # ============================================================
    def get_dependencies(self, service_id: str) -> list[ServiceDependency]:
        """
        서비스의 의존성 목록.

        Args:
            service_id: 서비스 ID

        Returns:
            의존성 목록
        """
        registered = self._services.get(service_id)
        if not registered:
            return []
        return registered.service_info.dependencies

    def get_dependents(self, service_id: str) -> list[str]:
        """
        서비스에 의존하는 서비스 목록.

        Args:
            service_id: 서비스 ID

        Returns:
            의존자 서비스 ID 목록
        """
        registered = self._services.get(service_id)
        if not registered:
            return []
        return registered.service_info.dependents

    def get_start_order(self) -> list[str]:
        """
        의존성을 고려한 시작 순서.

        Returns:
            서비스 ID 목록 (시작 순서)
        """
        # 위상 정렬
        visited = set()
        order = []

        def visit(service_id: str) -> None:
            if service_id in visited:
                return
            visited.add(service_id)

            # 의존성 먼저 방문
            for dep_id in self._dependency_graph.get(service_id, set()):
                if dep_id in self._services:
                    visit(dep_id)

            order.append(service_id)

        # 우선순위 순서로 방문
        sorted_services = sorted(
            self._services.values(),
            key=lambda r: r.service_info.service_type.priority,
        )

        for registered in sorted_services:
            visit(registered.service_id)

        return order

    def get_stop_order(self) -> list[str]:
        """
        의존성을 고려한 중지 순서.

        Returns:
            서비스 ID 목록 (중지 순서)
        """
        return list(reversed(self.get_start_order()))

    # ============================================================
    # 상태 조회
    # ============================================================
    @property
    def enabled(self) -> bool:
        """활성화 여부."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """활성화 설정."""
        self._enabled = value

    @property
    def service_count(self) -> int:
        """등록된 서비스 수."""
        return len(self._services)

    @property
    def running_count(self) -> int:
        """실행 중인 서비스 수."""
        return len(self.list_running())

    def get_status(self) -> dict[str, Any]:
        """
        레지스트리 상태 조회.

        Returns:
            상태 정보 딕셔너리
        """
        with self._lock:
            type_counts = {}
            for service_type in ServiceType:
                count = len(self._by_type.get(service_type, set()))
                if count > 0:
                    type_counts[service_type.value] = count

            lifecycle_counts = {}
            for registered in self._services.values():
                lifecycle = registered.service_info.lifecycle.value
                lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1

            return {
                "enabled": self._enabled,
                "registered_services": len(self._services),
                "running_services": self.running_count,
                "max_services": self._max_services,
                "service_types": type_counts,
                "lifecycle_counts": lifecycle_counts,
                "health_check_enabled": self._enable_health_check,
                # YAML 설정에서 로드된 값
                "config": {
                    "startup_timeout": self._config_provider.startup_timeout,
                    "shutdown_timeout": self._config_provider.shutdown_timeout,
                    "shutdown_grace_period": self._config_provider.shutdown_grace_period,
                    "health_check_interval": self._config_provider.health_check_interval,
                    "graceful_shutdown": self._config_provider.graceful_shutdown,
                    "detect_circular": self._config_provider.detect_circular,
                    "allow_optional_deps": self._config_provider.allow_optional_deps,
                },
            }

    # ============================================================
    # 종료
    # ============================================================
    def shutdown(self) -> None:
        """레지스트리 종료."""
        with self._lock:
            if self._shutdown:
                return

            self._shutdown = True
            self._enabled = False

            # 상태 체크 스레드 중지
            if self._health_check_thread and self._health_check_thread.is_alive():
                self._health_check_stop_event.set()
                self._health_check_thread.join(timeout=2.0)

            # 모든 서비스 중지
            self.stop_all()

            logger.info("ServiceRegistry 종료 완료")

    def __enter__(self) -> "ServiceRegistry":
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료."""
        self.shutdown()


# ============================================================
# 전역 인스턴스 관리 (싱글톤 대안)
# ============================================================
_global_registry: ServiceRegistry | None = None
_registry_lock = threading.Lock()


def _get_registry() -> ServiceRegistry:
    """전역 레지스트리 가져오기."""
    global _global_registry
    with _registry_lock:
        if _global_registry is None:
            _global_registry = ServiceRegistry()
        return _global_registry


def _reset_registry() -> None:
    """전역 레지스트리 초기화 (테스트용)."""
    global _global_registry
    with _registry_lock:
        if _global_registry is not None:
            _global_registry.shutdown()
            _global_registry = None
    # 설정 제공자도 초기화
    _ServiceConfigProvider.reset_instance()


# ============================================================
# 헬퍼 함수
# ============================================================
def get_service(service_id: str) -> ServiceInfo | None:
    """
    서비스 정보 조회 헬퍼.

    Args:
        service_id: 서비스 ID

    Returns:
        서비스 정보 (없으면 None)
    """
    return _get_registry().get(service_id)


def register_service(
    name: str,
    service_type: ServiceType,
    instance: IService | None = None,
    factory: Callable[[], IService] | None = None,
    **kwargs: Any,
) -> ServiceInfo:
    """
    서비스 등록 헬퍼.

    Args:
        name: 서비스 이름
        service_type: 서비스 타입
        instance: 서비스 인스턴스
        factory: 서비스 팩토리
        **kwargs: 추가 인자

    Returns:
        등록된 서비스 정보
    """
    return _get_registry().register(
        name=name,
        service_type=service_type,
        instance=instance,
        factory=factory,
        **kwargs,
    )


# 모듈 버전 정보
__version__: str = "1.0.0"
