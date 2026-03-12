# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: health_checker.py
설명: 시스템 및 로컬 의존성 헬스 체크 - Desktop Edition

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-11
버전: 1.0.0

주요 기능:
    - 시스템 리소스 헬스 체크 (CPU, 메모리, 디스크)
    - GPU 헬스 체크 (CUDA 가용성, VRAM, 온도)
    - 카메라 헬스 체크 (연결 상태, 프레임 캡처)
    - AI 모델 헬스 체크 (로드 상태, 추론 가능 여부)
    - 로컬 DB(SQLite) 헬스 체크
    - 헬스 상태 집계 및 전체 시스템 상태 판단
    - 헬스 체크 결과 히스토리 관리
    - 비동기 헬스 체크 지원
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상
    - YAML 설정 기반 구성

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 메모리 효율: 히스토리 크기 제한 (FIFO)
    - 확장성: 커스텀 헬스 체크 등록 방식
    - 비동기 지원: asyncio 기반 동시 체크

Desktop 특화:
    - GPU 장애 감지 (CUDA OOM, 드라이버 오류, 과열)
    - 카메라 연결 해제 감지
    - 로컬 디스크 용량 경고 (Windows 경로 자동 감지)
    - AI 모델 로드 실패 감지

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    health_checker = HealthChecker(config_loader)

    # 커스텀 체크 등록
    health_checker.register_check("sqlite", check_sqlite, DependencyType.DATABASE)

    # 전체 헬스 체크 실행
    system_health = health_checker.check_all()

    # 특정 의존성 체크
    result = health_checker.check("gpu")
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import asyncio
import logging
import platform
import socket
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

# ============================================================
# 서드파티 (선택적)
# ============================================================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# CUDA 지원 (GPU 헬스 체크용, 선택적)
try:
    import torch
    TORCH_AVAILABLE = torch.cuda.is_available()
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

# OpenCV 지원 (카메라 헬스 체크용, 선택적)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False


# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 타입 정의
# ============================================================
# 헬스 체크 함수 타입: () -> HealthCheckResult
HealthCheckFunc = Callable[[], "HealthCheckResult"]
# 비동기 헬스 체크 함수 타입
AsyncHealthCheckFunc = Callable[[], Coroutine[Any, Any, "HealthCheckResult"]]

# ============================================================
# 상수 정의
# ============================================================
# 기본 헬스 체크 타임아웃 (초)
DEFAULT_CHECK_TIMEOUT: float = 5.0

# 최대 헬스 히스토리 크기
MAX_HEALTH_HISTORY: int = 1000

# 기본 체크 간격 (초)
DEFAULT_CHECK_INTERVAL: float = 30.0

# 시스템 리소스 임계치 (기본값)
DEFAULT_CPU_WARNING_THRESHOLD: float = 80.0  # %
DEFAULT_CPU_CRITICAL_THRESHOLD: float = 95.0  # %
DEFAULT_MEMORY_WARNING_THRESHOLD: float = 80.0  # %
DEFAULT_MEMORY_CRITICAL_THRESHOLD: float = 95.0  # %
DEFAULT_DISK_WARNING_THRESHOLD: float = 80.0  # %
DEFAULT_DISK_CRITICAL_THRESHOLD: float = 95.0  # %

# 헬스 체크 스레드풀 크기
HEALTH_CHECK_THREAD_POOL_SIZE: int = 8

# GPU 임계치 (Desktop 특화)
DEFAULT_GPU_TEMP_WARNING: float = 80.0  # °C
DEFAULT_GPU_TEMP_CRITICAL: float = 90.0  # °C
DEFAULT_GPU_MEMORY_WARNING: float = 85.0  # %
DEFAULT_GPU_MEMORY_CRITICAL: float = 95.0  # %

# 기본 디스크 경로 (OS 자동 감지)
DEFAULT_DISK_PATH: str = "C:\\" if platform.system() == "Windows" else "/"

# 연속 실패 임계치 (DEGRADED 판정)
CONSECUTIVE_FAILURE_THRESHOLD: int = 3


# ============================================================
# Enum 정의
# ============================================================
class HealthStatus(Enum):
    """
    헬스 상태.

    시스템 또는 의존성의 건강 상태를 나타냅니다.

    Attributes:
        HEALTHY: 정상 (모든 체크 통과)
        DEGRADED: 성능 저하 (일부 체크 실패 또는 경고 상태)
        UNHEALTHY: 비정상 (중요 체크 실패)
        UNKNOWN: 알 수 없음 (체크 실패 또는 타임아웃)
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    @property
    def is_ok(self) -> bool:
        """정상 또는 저하 상태인지 확인."""
        return self in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def __lt__(self, other: HealthStatus) -> bool:
        """상태 비교 (심각도 순서)."""
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.UNHEALTHY: 3,
        }
        if not isinstance(other, HealthStatus):
            return NotImplemented
        return order[self] < order[other]


class DependencyType(Enum):
    """
    의존성 타입.

    헬스 체크 대상의 유형을 분류합니다.

    Desktop Edition Attributes:
        DATABASE: 로컬 데이터베이스 (SQLite)
        CACHE: 로컬 캐시 (파일 캐시, 메모리 캐시)
        STORAGE: 로컬 스토리지 (비디오, 분석 결과 저장)
        GPU: GPU 장치 (CUDA, TensorRT)
        CAMERA: 카메라 장치 (USB, 네트워크 카메라)
        SYSTEM_RESOURCE: 시스템 리소스 (CPU, 메모리, 디스크)
        MODEL: AI 모델 (포즈 추정, 객체 감지 등)
        EXTERNAL_API: 외부 API (앱 백엔드 통신, 선택적)
        CUSTOM: 커스텀 의존성
    """

    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    GPU = "gpu"
    CAMERA = "camera"
    SYSTEM_RESOURCE = "system_resource"
    MODEL = "model"
    EXTERNAL_API = "external_api"
    CUSTOM = "custom"

    @property
    def is_critical(self) -> bool:
        """중요 의존성 여부 (실패 시 UNHEALTHY)."""
        return self in (
            DependencyType.DATABASE,
            DependencyType.GPU,
            DependencyType.MODEL,
        )


# ============================================================
# 데이터 클래스 정의
# ============================================================
@dataclass(slots=True)
class HealthCheckResult:
    """
    헬스 체크 결과.

    개별 헬스 체크 실행 결과를 저장합니다.

    Attributes:
        name: 체크 이름
        status: 헬스 상태
        dependency_type: 의존성 타입
        message: 상세 메시지
        response_time_ms: 응답 시간 (밀리초)
        timestamp: 체크 시간
        metadata: 추가 메타데이터
        error: 에러 정보 (실패 시)
    """

    name: str
    status: HealthStatus
    dependency_type: DependencyType
    message: str = ""
    response_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "name": self.name,
            "status": self.status.value,
            "dependency_type": self.dependency_type.value,
            "message": self.message,
            "response_time_ms": round(self.response_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "error": self.error,
        }

    @classmethod
    def healthy(
        cls,
        name: str,
        dependency_type: DependencyType,
        message: str = "OK",
        response_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """정상 상태 결과 생성."""
        return cls(
            name=name,
            status=HealthStatus.HEALTHY,
            dependency_type=dependency_type,
            message=message,
            response_time_ms=response_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def degraded(
        cls,
        name: str,
        dependency_type: DependencyType,
        message: str,
        response_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """성능 저하 상태 결과 생성."""
        return cls(
            name=name,
            status=HealthStatus.DEGRADED,
            dependency_type=dependency_type,
            message=message,
            response_time_ms=response_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def unhealthy(
        cls,
        name: str,
        dependency_type: DependencyType,
        message: str,
        error: str | None = None,
        response_time_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> HealthCheckResult:
        """비정상 상태 결과 생성."""
        return cls(
            name=name,
            status=HealthStatus.UNHEALTHY,
            dependency_type=dependency_type,
            message=message,
            error=error,
            response_time_ms=response_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def unknown(
        cls,
        name: str,
        dependency_type: DependencyType,
        message: str = "Check failed or timed out",
        error: str | None = None,
    ) -> HealthCheckResult:
        """알 수 없는 상태 결과 생성."""
        return cls(
            name=name,
            status=HealthStatus.UNKNOWN,
            dependency_type=dependency_type,
            message=message,
            error=error,
        )


@dataclass(slots=True)
class DependencyHealth:
    """
    의존성 헬스 상태.

    단일 의존성에 대한 헬스 체크 결과 및 히스토리를 관리합니다.

    Attributes:
        name: 의존성 이름
        dependency_type: 의존성 타입
        current_status: 현재 상태
        last_check: 마지막 체크 결과
        consecutive_failures: 연속 실패 횟수
        total_checks: 총 체크 횟수
        successful_checks: 성공 체크 횟수
        average_response_time_ms: 평균 응답 시간
        last_healthy_time: 마지막 정상 시간
    """

    name: str
    dependency_type: DependencyType
    current_status: HealthStatus = HealthStatus.UNKNOWN
    last_check: HealthCheckResult | None = None
    consecutive_failures: int = 0
    total_checks: int = 0
    successful_checks: int = 0
    average_response_time_ms: float = 0.0
    last_healthy_time: datetime | None = None

    def update(self, result: HealthCheckResult) -> None:
        """체크 결과로 상태 업데이트."""
        self.last_check = result
        self.total_checks += 1

        if result.status == HealthStatus.HEALTHY:
            self.consecutive_failures = 0
            self.successful_checks += 1
            self.last_healthy_time = result.timestamp
            self.current_status = HealthStatus.HEALTHY
        elif result.status == HealthStatus.DEGRADED:
            self.consecutive_failures = 0
            self.successful_checks += 1
            self.current_status = HealthStatus.DEGRADED
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
                self.current_status = HealthStatus.UNHEALTHY
            else:
                self.current_status = HealthStatus.DEGRADED

        # 평균 응답 시간 업데이트 (지수 이동 평균)
        if result.response_time_ms > 0:
            alpha = 0.2  # 스무딩 팩터
            if self.average_response_time_ms == 0:
                self.average_response_time_ms = result.response_time_ms
            else:
                self.average_response_time_ms = (
                    alpha * result.response_time_ms +
                    (1 - alpha) * self.average_response_time_ms
                )

    @property
    def uptime_percentage(self) -> float:
        """가용률 (%)."""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "name": self.name,
            "dependency_type": self.dependency_type.value,
            "current_status": self.current_status.value,
            "consecutive_failures": self.consecutive_failures,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "uptime_percentage": round(self.uptime_percentage, 2),
            "average_response_time_ms": round(self.average_response_time_ms, 2),
            "last_healthy_time": self.last_healthy_time.isoformat() if self.last_healthy_time else None,
            "last_check": self.last_check.to_dict() if self.last_check else None,
        }


@dataclass(slots=True)
class SystemHealth:
    """
    시스템 전체 헬스 상태.

    모든 헬스 체크 결과를 집계한 전체 시스템 상태입니다.

    Attributes:
        overall_status: 전체 상태
        timestamp: 체크 시간
        total_checks: 총 체크 수
        healthy_checks: 정상 체크 수
        degraded_checks: 저하 체크 수
        unhealthy_checks: 비정상 체크 수
        unknown_checks: 알 수 없는 체크 수
        results: 개별 체크 결과 목록
        check_duration_ms: 전체 체크 소요 시간
        metadata: 추가 메타데이터
    """

    overall_status: HealthStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_checks: int = 0
    healthy_checks: int = 0
    degraded_checks: int = 0
    unhealthy_checks: int = 0
    unknown_checks: int = 0
    results: list[HealthCheckResult] = field(default_factory=list)
    check_duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "total_checks": self.total_checks,
                "healthy": self.healthy_checks,
                "degraded": self.degraded_checks,
                "unhealthy": self.unhealthy_checks,
                "unknown": self.unknown_checks,
            },
            "check_duration_ms": round(self.check_duration_ms, 2),
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }

    @property
    def is_healthy(self) -> bool:
        """전체 시스템이 정상인지 확인."""
        return self.overall_status == HealthStatus.HEALTHY

    @property
    def is_operational(self) -> bool:
        """시스템이 운영 가능한지 확인 (정상 또는 저하)."""
        return self.overall_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


@dataclass(slots=True)
class HealthCheckConfig:
    """
    헬스 체크 설정.

    개별 헬스 체크의 설정을 저장합니다.

    Attributes:
        name: 체크 이름
        dependency_type: 의존성 타입
        check_func: 체크 함수
        timeout: 타임아웃 (초)
        interval: 체크 간격 (초)
        critical: 필수 의존성 여부
        enabled: 활성화 여부
        tags: 태그 목록
    """

    name: str
    dependency_type: DependencyType
    check_func: HealthCheckFunc | AsyncHealthCheckFunc
    timeout: float = DEFAULT_CHECK_TIMEOUT
    interval: float = DEFAULT_CHECK_INTERVAL
    critical: bool = False
    enabled: bool = True
    tags: set[str] = field(default_factory=set)
    is_async: bool = False


# ============================================================
# 유틸리티 함수
# ============================================================
def aggregate_health_status(results: list[HealthCheckResult]) -> HealthStatus:
    """
    헬스 체크 결과들을 집계하여 전체 상태 결정.

    판정 로직:
        - 모든 체크가 HEALTHY -> HEALTHY
        - 하나라도 UNHEALTHY + 중요 의존성 -> UNHEALTHY
        - 하나라도 UNHEALTHY (비중요) -> DEGRADED
        - 하나라도 DEGRADED -> DEGRADED
        - 결과 없음 -> UNKNOWN

    Args:
        results: 헬스 체크 결과 목록

    Returns:
        집계된 전체 HealthStatus
    """
    if not results:
        return HealthStatus.UNKNOWN

    has_critical_unhealthy = False
    has_unhealthy = False
    has_degraded = False
    has_unknown = False

    for result in results:
        if result.status == HealthStatus.UNHEALTHY:
            if result.dependency_type.is_critical:
                has_critical_unhealthy = True
            else:
                has_unhealthy = True
        elif result.status == HealthStatus.DEGRADED:
            has_degraded = True
        elif result.status == HealthStatus.UNKNOWN:
            has_unknown = True

    # 판정
    if has_critical_unhealthy:
        return HealthStatus.UNHEALTHY
    elif has_unhealthy or has_degraded:
        return HealthStatus.DEGRADED
    elif has_unknown:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.HEALTHY


def create_health_check(
    name: str,
    dependency_type: DependencyType,
    check_func: Callable[[], bool],
    success_message: str = "OK",
    failure_message: str = "Check failed",
) -> HealthCheckFunc:
    """
    간단한 헬스 체크 함수 생성 헬퍼.

    bool 반환 함수를 HealthCheckResult 반환 함수로 래핑합니다.

    Args:
        name: 체크 이름
        dependency_type: 의존성 타입
        check_func: bool 반환 체크 함수
        success_message: 성공 메시지
        failure_message: 실패 메시지

    Returns:
        HealthCheckFunc 타입의 함수
    """
    def wrapped_check() -> HealthCheckResult:
        start_time = time.perf_counter()
        try:
            is_healthy = check_func()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if is_healthy:
                return HealthCheckResult.healthy(
                    name=name,
                    dependency_type=dependency_type,
                    message=success_message,
                    response_time_ms=elapsed_ms,
                )
            else:
                return HealthCheckResult.unhealthy(
                    name=name,
                    dependency_type=dependency_type,
                    message=failure_message,
                    response_time_ms=elapsed_ms,
                )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=failure_message,
                error=str(e),
                response_time_ms=elapsed_ms,
            )

    return wrapped_check


# ============================================================
# 빌트인 헬스 체크 함수
# ============================================================
def check_cpu_health(
    warning_threshold: float = DEFAULT_CPU_WARNING_THRESHOLD,
    critical_threshold: float = DEFAULT_CPU_CRITICAL_THRESHOLD,
) -> HealthCheckResult:
    """
    CPU 사용률 헬스 체크.

    Args:
        warning_threshold: 경고 임계치 (%)
        critical_threshold: 심각 임계치 (%)

    Returns:
        HealthCheckResult
    """
    name = "cpu"
    dependency_type = DependencyType.SYSTEM_RESOURCE

    if not PSUTIL_AVAILABLE:
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="psutil not available",
        )

    start_time = time.perf_counter()
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "cpu_percent": cpu_percent,
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
        }

        if cpu_percent >= critical_threshold:
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"CPU usage critical: {cpu_percent:.1f}% >= {critical_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        elif cpu_percent >= warning_threshold:
            return HealthCheckResult.degraded(
                name=name,
                dependency_type=dependency_type,
                message=f"CPU usage high: {cpu_percent:.1f}% >= {warning_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        else:
            return HealthCheckResult.healthy(
                name=name,
                dependency_type=dependency_type,
                message=f"CPU usage: {cpu_percent:.1f}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="Failed to check CPU",
            error=str(e),
        )


def check_memory_health(
    warning_threshold: float = DEFAULT_MEMORY_WARNING_THRESHOLD,
    critical_threshold: float = DEFAULT_MEMORY_CRITICAL_THRESHOLD,
) -> HealthCheckResult:
    """
    메모리 사용률 헬스 체크.

    Args:
        warning_threshold: 경고 임계치 (%)
        critical_threshold: 심각 임계치 (%)

    Returns:
        HealthCheckResult
    """
    name = "memory"
    dependency_type = DependencyType.SYSTEM_RESOURCE

    if not PSUTIL_AVAILABLE:
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="psutil not available",
        )

    start_time = time.perf_counter()
    try:
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "memory_percent": memory_percent,
            "total_mb": round(memory.total / (1024 * 1024), 2),
            "available_mb": round(memory.available / (1024 * 1024), 2),
            "used_mb": round(memory.used / (1024 * 1024), 2),
        }

        if memory_percent >= critical_threshold:
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Memory usage critical: {memory_percent:.1f}% >= {critical_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        elif memory_percent >= warning_threshold:
            return HealthCheckResult.degraded(
                name=name,
                dependency_type=dependency_type,
                message=f"Memory usage high: {memory_percent:.1f}% >= {warning_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        else:
            return HealthCheckResult.healthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Memory usage: {memory_percent:.1f}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="Failed to check memory",
            error=str(e),
        )


def check_disk_health(
    path: str = DEFAULT_DISK_PATH,
    warning_threshold: float = DEFAULT_DISK_WARNING_THRESHOLD,
    critical_threshold: float = DEFAULT_DISK_CRITICAL_THRESHOLD,
) -> HealthCheckResult:
    """
    디스크 사용률 헬스 체크.

    Args:
        path: 체크할 디스크 경로
        warning_threshold: 경고 임계치 (%)
        critical_threshold: 심각 임계치 (%)

    Returns:
        HealthCheckResult
    """
    name = "disk"
    dependency_type = DependencyType.SYSTEM_RESOURCE

    if not PSUTIL_AVAILABLE:
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="psutil not available",
        )

    start_time = time.perf_counter()
    try:
        disk = psutil.disk_usage(path)
        disk_percent = disk.percent
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "path": path,
            "disk_percent": disk_percent,
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
        }

        if disk_percent >= critical_threshold:
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Disk usage critical: {disk_percent:.1f}% >= {critical_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        elif disk_percent >= warning_threshold:
            return HealthCheckResult.degraded(
                name=name,
                dependency_type=dependency_type,
                message=f"Disk usage high: {disk_percent:.1f}% >= {warning_threshold}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        else:
            return HealthCheckResult.healthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Disk usage: {disk_percent:.1f}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message=f"Failed to check disk at {path}",
            error=str(e),
        )


def check_tcp_port(
    host: str,
    port: int,
    name: str,
    dependency_type: DependencyType,
    timeout: float = 5.0,
) -> HealthCheckResult:
    """
    TCP 포트 연결 헬스 체크.

    Args:
        host: 호스트 주소
        port: 포트 번호
        name: 체크 이름
        dependency_type: 의존성 타입
        timeout: 연결 타임아웃 (초)

    Returns:
        HealthCheckResult
    """
    start_time = time.perf_counter()
    sock: socket.socket | None = None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if result == 0:
            return HealthCheckResult.healthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Connected to {host}:{port}",
                response_time_ms=elapsed_ms,
                metadata={"host": host, "port": port},
            )
        else:
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"Cannot connect to {host}:{port}",
                error=f"Connection failed with code {result}",
                response_time_ms=elapsed_ms,
                metadata={"host": host, "port": port},
            )

    except socket.timeout:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unhealthy(
            name=name,
            dependency_type=dependency_type,
            message=f"Connection timeout to {host}:{port}",
            error="Socket timeout",
            response_time_ms=elapsed_ms,
            metadata={"host": host, "port": port},
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message=f"Failed to check {host}:{port}",
            error=str(e),
        )

    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


# ============================================================
# Desktop 특화 빌트인 헬스 체크
# ============================================================
def check_gpu_health(
    temp_warning: float = DEFAULT_GPU_TEMP_WARNING,
    temp_critical: float = DEFAULT_GPU_TEMP_CRITICAL,
    memory_warning: float = DEFAULT_GPU_MEMORY_WARNING,
    memory_critical: float = DEFAULT_GPU_MEMORY_CRITICAL,
) -> HealthCheckResult:
    """
    GPU 헬스 체크 (CUDA/TensorRT).

    체크 항목:
        - CUDA 가용성
        - GPU 메모리 사용률
        - GPU 온도 (pynvml 가용 시)

    Args:
        temp_warning: 온도 경고 임계치 (°C)
        temp_critical: 온도 심각 임계치 (°C)
        memory_warning: 메모리 사용률 경고 임계치 (%)
        memory_critical: 메모리 사용률 심각 임계치 (%)

    Returns:
        HealthCheckResult
    """
    name = "gpu"
    dependency_type = DependencyType.GPU

    if not TORCH_AVAILABLE:
        return HealthCheckResult.unhealthy(
            name=name,
            dependency_type=dependency_type,
            message="CUDA not available",
            error="torch.cuda.is_available() returned False",
        )

    start_time = time.perf_counter()
    try:
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)

        # GPU 메모리 상태
        memory_allocated = torch.cuda.memory_allocated(current_device)
        memory_reserved = torch.cuda.memory_reserved(current_device)
        props = torch.cuda.get_device_properties(current_device)
        memory_total = props.total_memory

        memory_percent = (memory_allocated / memory_total * 100) if memory_total > 0 else 0.0

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "device_count": device_count,
            "current_device": current_device,
            "device_name": device_name,
            "memory_allocated_mb": round(memory_allocated / (1024 * 1024), 2),
            "memory_reserved_mb": round(memory_reserved / (1024 * 1024), 2),
            "memory_total_mb": round(memory_total / (1024 * 1024), 2),
            "memory_percent": round(memory_percent, 2),
        }

        # GPU 온도 체크 (pynvml 가용 시)
        gpu_temp = _get_gpu_temperature(current_device)
        if gpu_temp is not None:
            metadata["temperature_celsius"] = gpu_temp

            # 온도 기반 판정
            if gpu_temp >= temp_critical:
                return HealthCheckResult.unhealthy(
                    name=name,
                    dependency_type=dependency_type,
                    message=f"GPU overheating: {gpu_temp:.1f}°C >= {temp_critical}°C",
                    response_time_ms=elapsed_ms,
                    metadata=metadata,
                )
            elif gpu_temp >= temp_warning:
                return HealthCheckResult.degraded(
                    name=name,
                    dependency_type=dependency_type,
                    message=f"GPU temperature high: {gpu_temp:.1f}°C >= {temp_warning}°C",
                    response_time_ms=elapsed_ms,
                    metadata=metadata,
                )

        # 메모리 기반 판정
        if memory_percent >= memory_critical:
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"GPU memory critical: {memory_percent:.1f}% >= {memory_critical}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        elif memory_percent >= memory_warning:
            return HealthCheckResult.degraded(
                name=name,
                dependency_type=dependency_type,
                message=f"GPU memory high: {memory_percent:.1f}% >= {memory_warning}%",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )

        return HealthCheckResult.healthy(
            name=name,
            dependency_type=dependency_type,
            message=f"GPU OK: {device_name}, VRAM {memory_percent:.1f}%",
            response_time_ms=elapsed_ms,
            metadata=metadata,
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unhealthy(
            name=name,
            dependency_type=dependency_type,
            message="GPU health check failed",
            error=str(e),
            response_time_ms=elapsed_ms,
        )


def _get_gpu_temperature(device_id: int = 0) -> float | None:
    """
    GPU 온도 조회 (pynvml 기반).

    Args:
        device_id: GPU 장치 ID

    Returns:
        온도 (°C) 또는 None (조회 불가 시)
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        pynvml.nvmlShutdown()
        return float(temp)
    except Exception:
        return None


def check_camera_health(
    camera_indices: list[int] | None = None,
    timeout_ms: float = 2000.0,
) -> HealthCheckResult:
    """
    카메라 연결 상태 헬스 체크.

    Args:
        camera_indices: 체크할 카메라 인덱스 목록 (None이면 [0])
        timeout_ms: 카메라 오픈 타임아웃 (ms)

    Returns:
        HealthCheckResult
    """
    name = "camera"
    dependency_type = DependencyType.CAMERA

    if not CV2_AVAILABLE:
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="OpenCV (cv2) not available",
        )

    indices = camera_indices or [0]
    start_time = time.perf_counter()

    try:
        connected = []
        failed = []

        for idx in indices:
            cap = cv2.VideoCapture(idx)
            try:
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        connected.append(idx)
                    else:
                        failed.append(idx)
                else:
                    failed.append(idx)
            finally:
                cap.release()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "checked_indices": indices,
            "connected": connected,
            "failed": failed,
            "connected_count": len(connected),
            "total_checked": len(indices),
        }

        if len(failed) == len(indices):
            # 모든 카메라 실패
            return HealthCheckResult.unhealthy(
                name=name,
                dependency_type=dependency_type,
                message=f"All cameras failed: {failed}",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        elif failed:
            # 일부 카메라 실패
            return HealthCheckResult.degraded(
                name=name,
                dependency_type=dependency_type,
                message=f"Some cameras failed: {failed}, connected: {connected}",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )
        else:
            return HealthCheckResult.healthy(
                name=name,
                dependency_type=dependency_type,
                message=f"All cameras OK: {connected}",
                response_time_ms=elapsed_ms,
                metadata=metadata,
            )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return HealthCheckResult.unknown(
            name=name,
            dependency_type=dependency_type,
            message="Camera health check failed",
            error=str(e),
        )


# ============================================================
# 메인 클래스: HealthChecker
# ============================================================
class HealthChecker:
    """
    헬스 체커.

    시스템 및 외부 의존성의 헬스 상태를 체크하고 관리합니다.

    Features:
        - 커스텀 헬스 체크 등록
        - 동기/비동기 체크 지원
        - 병렬 체크 실행
        - 결과 히스토리 관리
        - 의존성별 상태 추적
        - YAML 설정 기반 구성

    설정 예시 (YAML):
        health_check:
          enabled: true
          default_timeout: 5.0
          default_interval: 30.0
          system_checks:
            cpu: true
            memory: true
            disk: true
          thresholds:
            cpu:
              warning: 80.0
              critical: 95.0
            memory:
              warning: 80.0
              critical: 95.0
            disk:
              warning: 80.0
              critical: 95.0

    Attributes:
        config_loader: 설정 로더
        enabled: 활성화 여부
        default_timeout: 기본 타임아웃
        checks: 등록된 헬스 체크
        dependencies: 의존성 상태
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        *,
        enabled: bool | None = None,
        default_timeout: float | None = None,
        default_interval: float | None = None,
        max_history: int | None = None,
        enable_system_checks: bool | None = None,
    ) -> None:
        """
        HealthChecker 초기화.

        우선순위: 파라미터 > YAML 설정 > 기본값

        Args:
            config_loader: 설정 로더 (YAML 설정용)
            enabled: 활성화 여부
            default_timeout: 기본 타임아웃 (초)
            default_interval: 기본 체크 간격 (초)
            max_history: 최대 히스토리 크기
            enable_system_checks: 시스템 체크 자동 등록 여부
        """
        self._lock = threading.RLock()
        self._config_loader = config_loader

        # YAML 설정 로드
        yaml_config = self._load_yaml_config()

        # 설정 적용 (우선순위: 파라미터 > YAML > 기본값)
        self._enabled = enabled if enabled is not None else yaml_config.get("enabled", True)
        self._default_timeout = (
            default_timeout if default_timeout is not None
            else yaml_config.get("default_timeout", DEFAULT_CHECK_TIMEOUT)
        )
        self._default_interval = (
            default_interval if default_interval is not None
            else yaml_config.get("default_interval", DEFAULT_CHECK_INTERVAL)
        )
        self._max_history = (
            max_history if max_history is not None
            else yaml_config.get("max_history", MAX_HEALTH_HISTORY)
        )

        # 임계치 설정
        thresholds = yaml_config.get("thresholds", {})
        self._cpu_warning = thresholds.get("cpu", {}).get("warning", DEFAULT_CPU_WARNING_THRESHOLD)
        self._cpu_critical = thresholds.get("cpu", {}).get("critical", DEFAULT_CPU_CRITICAL_THRESHOLD)
        self._memory_warning = thresholds.get("memory", {}).get("warning", DEFAULT_MEMORY_WARNING_THRESHOLD)
        self._memory_critical = thresholds.get("memory", {}).get("critical", DEFAULT_MEMORY_CRITICAL_THRESHOLD)
        self._disk_warning = thresholds.get("disk", {}).get("warning", DEFAULT_DISK_WARNING_THRESHOLD)
        self._disk_critical = thresholds.get("disk", {}).get("critical", DEFAULT_DISK_CRITICAL_THRESHOLD)

        # 내부 상태
        self._checks: dict[str, HealthCheckConfig] = {}
        self._dependencies: dict[str, DependencyHealth] = {}
        self._history: deque[SystemHealth] = deque(maxlen=self._max_history)
        self._executor: ThreadPoolExecutor | None = None

        # 시스템 체크 자동 등록
        enable_sys = (
            enable_system_checks if enable_system_checks is not None
            else yaml_config.get("system_checks", {}).get("enabled", True)
        )
        if enable_sys:
            self._register_system_checks(yaml_config.get("system_checks", {}))

        logger.info(
            f"HealthChecker 초기화 완료: enabled={self._enabled}, "
            f"timeout={self._default_timeout}s, interval={self._default_interval}s"
        )

    def __repr__(self) -> str:
        """문자열 표현."""
        return (
            f"HealthChecker(enabled={self._enabled}, "
            f"checks={len(self._checks)}, "
            f"timeout={self._default_timeout}s)"
        )

    def _load_yaml_config(self) -> dict[str, Any]:
        """YAML 설정 로드."""
        if not self._config_loader:
            return {}

        try:
            config = self._config_loader.get("health_check", {})
            if isinstance(config, dict):
                return config
            return {}
        except Exception as e:
            logger.warning(f"health_check 설정 로드 실패: {e}")
            return {}

    def _register_system_checks(self, system_config: dict[str, Any]) -> None:
        """시스템 리소스 + Desktop 하드웨어 체크 등록."""
        if system_config.get("cpu", True):
            self.register_check(
                name="cpu",
                check_func=lambda: check_cpu_health(self._cpu_warning, self._cpu_critical),
                dependency_type=DependencyType.SYSTEM_RESOURCE,
                timeout=self._default_timeout,
                critical=False,
            )

        if system_config.get("memory", True):
            self.register_check(
                name="memory",
                check_func=lambda: check_memory_health(self._memory_warning, self._memory_critical),
                dependency_type=DependencyType.SYSTEM_RESOURCE,
                timeout=self._default_timeout,
                critical=False,
            )

        if system_config.get("disk", True):
            disk_path = system_config.get("disk_path", DEFAULT_DISK_PATH)
            self.register_check(
                name="disk",
                check_func=lambda: check_disk_health(disk_path, self._disk_warning, self._disk_critical),
                dependency_type=DependencyType.SYSTEM_RESOURCE,
                timeout=self._default_timeout,
                critical=False,
            )

        # Desktop 특화: GPU 헬스 체크
        if system_config.get("gpu", TORCH_AVAILABLE):
            self.register_check(
                name="gpu",
                check_func=lambda: check_gpu_health(),
                dependency_type=DependencyType.GPU,
                timeout=self._default_timeout,
                critical=True,  # GPU는 Desktop 필수 리소스
            )

        # Desktop 특화: 카메라 헬스 체크
        if system_config.get("camera", False):
            camera_indices = system_config.get("camera_indices", [0])
            self.register_check(
                name="camera",
                check_func=lambda: check_camera_health(camera_indices),
                dependency_type=DependencyType.CAMERA,
                timeout=self._default_timeout * 2,  # 카메라 오픈은 느릴 수 있음
                critical=False,
            )

    @property
    def enabled(self) -> bool:
        """활성화 여부."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """활성화 상태 설정."""
        self._enabled = value

    @property
    def check_count(self) -> int:
        """등록된 체크 수."""
        with self._lock:
            return len(self._checks)

    def register_check(
        self,
        name: str,
        check_func: HealthCheckFunc | AsyncHealthCheckFunc,
        dependency_type: DependencyType,
        *,
        timeout: float | None = None,
        interval: float | None = None,
        critical: bool = False,
        enabled: bool = True,
        tags: set[str] | None = None,
    ) -> None:
        """
        헬스 체크 등록.

        Args:
            name: 체크 이름 (고유)
            check_func: 체크 함수 (HealthCheckResult 반환)
            dependency_type: 의존성 타입
            timeout: 타임아웃 (초)
            interval: 체크 간격 (초)
            critical: 필수 의존성 여부
            enabled: 활성화 여부
            tags: 태그 셋
        """
        with self._lock:
            # 비동기 함수 여부 판단
            is_async = asyncio.iscoroutinefunction(check_func)

            config = HealthCheckConfig(
                name=name,
                dependency_type=dependency_type,
                check_func=check_func,
                timeout=timeout or self._default_timeout,
                interval=interval or self._default_interval,
                critical=critical,
                enabled=enabled,
                tags=tags or set(),
                is_async=is_async,
            )

            self._checks[name] = config

            # 의존성 상태 초기화
            if name not in self._dependencies:
                self._dependencies[name] = DependencyHealth(
                    name=name,
                    dependency_type=dependency_type,
                )

            logger.debug(f"헬스 체크 등록: {name} (type={dependency_type.value}, critical={critical})")

    def unregister_check(self, name: str) -> bool:
        """
        헬스 체크 등록 해제.

        Args:
            name: 체크 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                logger.debug(f"헬스 체크 해제: {name}")
                return True
            return False

    def get_check(self, name: str) -> HealthCheckConfig | None:
        """
        등록된 체크 조회.

        Args:
            name: 체크 이름

        Returns:
            HealthCheckConfig 또는 None
        """
        with self._lock:
            return self._checks.get(name)

    def list_checks(self) -> list[str]:
        """등록된 모든 체크 이름 목록."""
        with self._lock:
            return list(self._checks.keys())

    def check(self, name: str) -> HealthCheckResult:
        """
        단일 헬스 체크 실행.

        Args:
            name: 체크 이름

        Returns:
            HealthCheckResult

        Raises:
            KeyError: 등록되지 않은 체크
        """
        with self._lock:
            config = self._checks.get(name)
            if not config:
                raise KeyError(f"등록되지 않은 헬스 체크: {name}")

        if not config.enabled:
            return HealthCheckResult.unknown(
                name=name,
                dependency_type=config.dependency_type,
                message="Check is disabled",
            )

        return self._execute_check(config)

    def _execute_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """체크 실행 (타임아웃 적용)."""
        try:
            if config.is_async:
                # 비동기 함수 실행
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            config.check_func(),
                            timeout=config.timeout,
                        )
                    )
                finally:
                    loop.close()
            else:
                # 동기 함수 실행 (ThreadPoolExecutor로 타임아웃 적용)
                executor = self._get_executor()
                future = executor.submit(config.check_func)
                result = future.result(timeout=config.timeout)

            # 결과 타입 검증
            if not isinstance(result, HealthCheckResult):
                result = HealthCheckResult.unknown(
                    name=config.name,
                    dependency_type=config.dependency_type,
                    message="Invalid check result type",
                    error=f"Expected HealthCheckResult, got {type(result).__name__}",
                )

        except (asyncio.TimeoutError, FuturesTimeoutError):
            result = HealthCheckResult.unknown(
                name=config.name,
                dependency_type=config.dependency_type,
                message=f"Check timed out after {config.timeout}s",
                error="Timeout",
            )
        except Exception as e:
            result = HealthCheckResult.unknown(
                name=config.name,
                dependency_type=config.dependency_type,
                message="Check failed with exception",
                error=str(e),
            )

        # 의존성 상태 업데이트
        with self._lock:
            if config.name in self._dependencies:
                self._dependencies[config.name].update(result)

        return result

    def _get_executor(self) -> ThreadPoolExecutor:
        """스레드풀 Executor 가져오기 (지연 초기화)."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=HEALTH_CHECK_THREAD_POOL_SIZE,
                thread_name_prefix="health_check_",
            )
        return self._executor

    def check_all(
        self,
        *,
        tags: set[str] | None = None,
        parallel: bool = True,
    ) -> SystemHealth:
        """
        모든 헬스 체크 실행.

        Args:
            tags: 필터링할 태그 (None이면 모든 체크)
            parallel: 병렬 실행 여부

        Returns:
            SystemHealth (전체 시스템 상태)
        """
        if not self._enabled:
            return SystemHealth(
                overall_status=HealthStatus.UNKNOWN,
                metadata={"reason": "HealthChecker is disabled"},
            )

        start_time = time.perf_counter()

        with self._lock:
            # 활성화된 체크 필터링
            checks_to_run = [
                config for config in self._checks.values()
                if config.enabled and (tags is None or config.tags & tags)
            ]

        if not checks_to_run:
            return SystemHealth(
                overall_status=HealthStatus.UNKNOWN,
                metadata={"reason": "No checks registered or enabled"},
            )

        # 체크 실행
        results: list[HealthCheckResult] = []

        if parallel and len(checks_to_run) > 1:
            # 병렬 실행
            executor = self._get_executor()
            futures = {
                executor.submit(self._execute_check, config): config
                for config in checks_to_run
            }

            for future in futures:
                try:
                    result = future.result(timeout=self._default_timeout * 2)
                    results.append(result)
                except Exception as e:
                    config = futures[future]
                    results.append(HealthCheckResult.unknown(
                        name=config.name,
                        dependency_type=config.dependency_type,
                        message="Parallel execution failed",
                        error=str(e),
                    ))
        else:
            # 순차 실행
            for config in checks_to_run:
                results.append(self._execute_check(config))

        # 결과 집계
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        overall_status = aggregate_health_status(results)

        # 상태 카운트
        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        unknown_count = sum(1 for r in results if r.status == HealthStatus.UNKNOWN)

        system_health = SystemHealth(
            overall_status=overall_status,
            total_checks=len(results),
            healthy_checks=healthy_count,
            degraded_checks=degraded_count,
            unhealthy_checks=unhealthy_count,
            unknown_checks=unknown_count,
            results=results,
            check_duration_ms=elapsed_ms,
        )

        # 히스토리 저장
        with self._lock:
            self._history.append(system_health)

        return system_health

    def get_dependency_status(self, name: str) -> DependencyHealth | None:
        """
        의존성 상태 조회.

        Args:
            name: 의존성 이름

        Returns:
            DependencyHealth 또는 None
        """
        with self._lock:
            return self._dependencies.get(name)

    def get_all_dependencies(self) -> dict[str, DependencyHealth]:
        """모든 의존성 상태 조회."""
        with self._lock:
            return dict(self._dependencies)

    def get_history(
        self,
        limit: int = 100,
    ) -> list[SystemHealth]:
        """
        헬스 체크 히스토리 조회.

        Args:
            limit: 최대 조회 개수

        Returns:
            SystemHealth 목록 (최신순)
        """
        with self._lock:
            history_list = list(self._history)
            return list(reversed(history_list))[:limit]

    def get_current_status(self) -> HealthStatus:
        """현재 전체 시스템 상태."""
        with self._lock:
            if self._history:
                return self._history[-1].overall_status
            return HealthStatus.UNKNOWN

    def is_healthy(self) -> bool:
        """시스템이 정상인지 확인."""
        return self.get_current_status() == HealthStatus.HEALTHY

    def is_operational(self) -> bool:
        """시스템이 운영 가능한지 확인 (HEALTHY 또는 DEGRADED)."""
        status = self.get_current_status()
        return status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()
            for dep in self._dependencies.values():
                dep.consecutive_failures = 0
                dep.total_checks = 0
                dep.successful_checks = 0
                dep.average_response_time_ms = 0.0
                dep.last_check = None
                dep.last_healthy_time = None
                dep.current_status = HealthStatus.UNKNOWN

        logger.info("HealthChecker 상태 초기화")

    def shutdown(self) -> None:
        """리소스 정리."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

        logger.info("HealthChecker 종료")

    def __enter__(self) -> HealthChecker:
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료."""
        self.shutdown()

    def get_status_summary(self) -> dict[str, Any]:
        """
        상태 요약 조회 (API 응답용).

        Returns:
            상태 요약 딕셔너리
        """
        with self._lock:
            last_health = self._history[-1] if self._history else None

            return {
                "status": self.get_current_status().value,
                "is_operational": self.is_operational(),
                "check_count": len(self._checks),
                "enabled": self._enabled,
                "last_check": last_health.to_dict() if last_health else None,
                "dependencies": {
                    name: dep.to_dict()
                    for name, dep in self._dependencies.items()
                },
            }


# ============================================================
# 전역 인스턴스 및 헬퍼 함수
# ============================================================
_global_health_checker: HealthChecker | None = None
_global_lock = threading.Lock()


def _get_health_checker() -> HealthChecker:
    """전역 HealthChecker 인스턴스 반환 (지연 초기화)."""
    global _global_health_checker

    if _global_health_checker is None:
        with _global_lock:
            if _global_health_checker is None:
                _global_health_checker = HealthChecker()

    return _global_health_checker


def _reset_health_checker() -> None:
    """전역 HealthChecker 초기화 (테스트용)."""
    global _global_health_checker

    with _global_lock:
        if _global_health_checker is not None:
            _global_health_checker.shutdown()
            _global_health_checker = None


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "HealthStatus",
    "DependencyType",
    # 상수
    "DEFAULT_CHECK_TIMEOUT",
    "MAX_HEALTH_HISTORY",
    "DEFAULT_CHECK_INTERVAL",
    "DEFAULT_CPU_WARNING_THRESHOLD",
    "DEFAULT_CPU_CRITICAL_THRESHOLD",
    "DEFAULT_MEMORY_WARNING_THRESHOLD",
    "DEFAULT_MEMORY_CRITICAL_THRESHOLD",
    "DEFAULT_DISK_WARNING_THRESHOLD",
    "DEFAULT_DISK_CRITICAL_THRESHOLD",
    "DEFAULT_GPU_TEMP_WARNING",
    "DEFAULT_GPU_TEMP_CRITICAL",
    "DEFAULT_GPU_MEMORY_WARNING",
    "DEFAULT_GPU_MEMORY_CRITICAL",
    "DEFAULT_DISK_PATH",
    # 데이터 클래스
    "HealthCheckResult",
    "DependencyHealth",
    "SystemHealth",
    "HealthCheckConfig",
    # 메인 클래스
    "HealthChecker",
    # 함수
    "create_health_check",
    "aggregate_health_status",
    # 빌트인 체크 함수
    "check_cpu_health",
    "check_memory_health",
    "check_disk_health",
    "check_tcp_port",
    # Desktop 특화 빌트인 체크
    "check_gpu_health",
    "check_camera_health",
    # 유틸리티 (테스트용)
    "_get_health_checker",
    "_reset_health_checker",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
