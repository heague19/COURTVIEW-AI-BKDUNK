# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: health_checker.py
설명: 시스템 헬스 체크 엔진
      - 컴포넌트별 헬스 체크 등록/실행
      - GPU/카메라/시스템 상태 점검
      - 헬스 리포트 생성
      - 주기적 백그라운드 체크 (daemon)
      - 상태 변경 콜백

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 프로젝트 내부 (Project Internal) — Layer 0: shared만 참조
# =============================================================================
from shared.constants.status_codes import ServiceStatus


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 헬스 체크 간격 (초)
DEFAULT_CHECK_INTERVAL: Final[float] = 30.0

# 최소 체크 간격 (초)
MIN_CHECK_INTERVAL: Final[float] = 5.0

# 최대 체크 간격 (초)
MAX_CHECK_INTERVAL: Final[float] = 300.0

# 최대 컴포넌트 등록 수
MAX_COMPONENTS: Final[int] = 100

# 체크 타임아웃 (초) — 개별 체크 함수 실행 한도
CHECK_TIMEOUT: Final[float] = 10.0

# 상태 이력 최대 수
MAX_STATUS_HISTORY: Final[int] = 50


# =============================================================================
# 헬스 체크 결과 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ComponentHealth:
    """단일 컴포넌트 헬스 결과.

    Attributes:
        component: 컴포넌트 이름
        status: 서비스 상태
        message: 상태 설명 메시지
        details: 추가 상세 정보
        check_duration_sec: 체크 소요 시간 (초)
        timestamp: 체크 시각 (monotonic)
    """

    component: str
    status: ServiceStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    check_duration_sec: float = 0.0
    timestamp: float = 0.0

    def __repr__(self) -> str:
        return (
            f"ComponentHealth("
            f"{self.component}: {self.status.value}, "
            f"'{self.message}')"
        )


@dataclass(slots=True)
class HealthReport:
    """전체 헬스 리포트.

    Attributes:
        overall_status: 전체 상태 (최악의 컴포넌트 기준)
        components: 컴포넌트별 헬스 결과
        timestamp: 리포트 생성 시각
        total_duration_sec: 전체 체크 소요 시간
    """

    overall_status: ServiceStatus
    components: dict[str, ComponentHealth]
    timestamp: float
    total_duration_sec: float

    @property
    def is_healthy(self) -> bool:
        """전체 시스템 정상 여부."""
        return self.overall_status == ServiceStatus.HEALTHY

    @property
    def unhealthy_components(self) -> list[str]:
        """비정상 컴포넌트 목록."""
        return [
            name for name, health in self.components.items()
            if health.status not in _ACCEPTABLE_STATUSES
        ]

    def __repr__(self) -> str:
        return (
            f"HealthReport("
            f"status={self.overall_status.value}, "
            f"components={len(self.components)}, "
            f"healthy={self.is_healthy})"
        )


# 허용 가능 상태 (HEALTHY, DEGRADED)
_ACCEPTABLE_STATUSES: Final[frozenset[ServiceStatus]] = frozenset({
    ServiceStatus.HEALTHY,
    ServiceStatus.DEGRADED,
})


# =============================================================================
# 체크 함수 타입
# =============================================================================

# 헬스 체크 함수: () -> ComponentHealth
HealthCheckFn = Callable[[], ComponentHealth]

# 상태 변경 콜백: (component, old_status, new_status) -> None
StatusChangeCallback = Callable[[str, ServiceStatus, ServiceStatus], None]


# =============================================================================
# 핵심 클래스: HealthChecker
# =============================================================================

class HealthChecker:
    """시스템 헬스 체크 관리자.

    컴포넌트별 헬스 체크 함수를 등록하고,
    수동 또는 주기적으로 실행한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        checker = HealthChecker.get_instance()

        # 컴포넌트 등록
        def check_gpu() -> ComponentHealth:
            return ComponentHealth(
                component="gpu",
                status=ServiceStatus.HEALTHY,
                message="GPU 정상",
                details={"vram_used_mb": 2048},
            )

        checker.register("gpu", check_gpu)

        # 수동 체크
        report = checker.check_all()
        print(f"전체 상태: {report.overall_status}")

        # 주기적 체크 시작
        checker.start(interval=30.0)
    """

    _instance: ClassVar[HealthChecker | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: dict[str, HealthCheckFn] = {}
        self._last_results: dict[str, ComponentHealth] = {}
        self._status_history: dict[str, list[ServiceStatus]] = {}
        self._callbacks: list[StatusChangeCallback] = []

        # 백그라운드 체크
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._check_interval = DEFAULT_CHECK_INTERVAL

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> HealthChecker:
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._class_lock:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    # =========================================================================
    # 컴포넌트 등록
    # =========================================================================

    def register(self, component: str, check_fn: HealthCheckFn) -> bool:
        """헬스 체크 함수 등록.

        Args:
            component: 컴포넌트 이름
            check_fn: 체크 함수

        Returns:
            등록 성공 여부 (한도 초과 시 False)
        """
        with self._lock:
            if (
                component not in self._checks
                and len(self._checks) >= MAX_COMPONENTS
            ):
                return False

            self._checks[component] = check_fn
            return True

    def unregister(self, component: str) -> bool:
        """컴포넌트 등록 해제.

        Args:
            component: 컴포넌트 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if component in self._checks:
                del self._checks[component]
                self._last_results.pop(component, None)
                self._status_history.pop(component, None)
                return True
            return False

    @property
    def component_count(self) -> int:
        """등록된 컴포넌트 수."""
        with self._lock:
            return len(self._checks)

    @property
    def component_names(self) -> list[str]:
        """등록된 컴포넌트 이름 목록."""
        with self._lock:
            return list(self._checks.keys())

    # =========================================================================
    # 콜백 관리
    # =========================================================================

    def add_status_callback(self, callback: StatusChangeCallback) -> None:
        """상태 변경 콜백 등록."""
        with self._lock:
            self._callbacks.append(callback)

    def remove_status_callback(self, callback: StatusChangeCallback) -> bool:
        """상태 변경 콜백 해제."""
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    # =========================================================================
    # 체크 실행
    # =========================================================================

    def check_all(self) -> HealthReport:
        """전체 컴포넌트 헬스 체크 실행.

        Returns:
            HealthReport
        """
        start = time.perf_counter()

        with self._lock:
            checks = dict(self._checks)

        results: dict[str, ComponentHealth] = {}
        for component, check_fn in checks.items():
            result = self._execute_check(component, check_fn)
            results[component] = result

        total_duration = time.perf_counter() - start

        # 전체 상태 = 최악의 컴포넌트 기준
        overall = self._compute_overall_status(results)

        report = HealthReport(
            overall_status=overall,
            components=results,
            timestamp=time.monotonic(),
            total_duration_sec=total_duration,
        )

        return report

    def check_component(self, component: str) -> ComponentHealth | None:
        """특정 컴포넌트 체크.

        Args:
            component: 컴포넌트 이름

        Returns:
            ComponentHealth 또는 None (미등록)
        """
        with self._lock:
            check_fn = self._checks.get(component)

        if check_fn is None:
            return None

        return self._execute_check(component, check_fn)

    def get_last_result(self, component: str) -> ComponentHealth | None:
        """마지막 체크 결과 조회.

        Args:
            component: 컴포넌트 이름

        Returns:
            마지막 ComponentHealth 또는 None
        """
        with self._lock:
            return self._last_results.get(component)

    def get_last_report(self) -> HealthReport | None:
        """마지막 전체 리포트 생성.

        캐시된 마지막 결과로 리포트 구성.

        Returns:
            HealthReport 또는 None (체크 미실행)
        """
        with self._lock:
            if not self._last_results:
                return None

            results = dict(self._last_results)

        overall = self._compute_overall_status(results)
        return HealthReport(
            overall_status=overall,
            components=results,
            timestamp=time.monotonic(),
            total_duration_sec=0.0,
        )

    # =========================================================================
    # 주기적 체크
    # =========================================================================

    def start(self, interval: float = DEFAULT_CHECK_INTERVAL) -> bool:
        """주기적 헬스 체크 시작.

        Args:
            interval: 체크 간격 (초)

        Returns:
            시작 성공 여부
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._check_interval = max(
                MIN_CHECK_INTERVAL,
                min(interval, MAX_CHECK_INTERVAL),
            )
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._check_loop,
                name="HealthChecker-Loop",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """주기적 체크 중지.

        Args:
            timeout: 대기 시간 (초)

        Returns:
            정상 종료 여부
        """
        self._stop_event.set()

        with self._lock:
            thread = self._thread
            self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            return not thread.is_alive()
        return True

    @property
    def is_running(self) -> bool:
        """주기적 체크 실행 중 여부."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _execute_check(
        self,
        component: str,
        check_fn: HealthCheckFn,
    ) -> ComponentHealth:
        """단일 체크 실행 (예외 격리)."""
        start = time.perf_counter()
        try:
            result = check_fn()
            result.check_duration_sec = time.perf_counter() - start
            result.timestamp = time.monotonic()
        except Exception as exc:
            result = ComponentHealth(
                component=component,
                status=ServiceStatus.UNHEALTHY,
                message=f"체크 실패: {type(exc).__name__}: {exc}",
                check_duration_sec=time.perf_counter() - start,
                timestamp=time.monotonic(),
            )

        # 상태 변경 감지 및 콜백
        with self._lock:
            old_result = self._last_results.get(component)
            self._last_results[component] = result

            # 상태 이력 기록
            history = self._status_history.setdefault(component, [])
            history.append(result.status)
            if len(history) > MAX_STATUS_HISTORY:
                history.pop(0)

            if old_result is not None and old_result.status != result.status:
                callbacks = list(self._callbacks)
            else:
                callbacks = []

        # 콜백 실행 (lock 밖에서, 예외 격리)
        old_status = old_result.status if old_result else ServiceStatus.UNKNOWN
        for callback in callbacks:
            try:
                callback(component, old_status, result.status)
            except Exception:
                pass

        return result

    def _check_loop(self) -> None:
        """백그라운드 체크 루프."""
        while not self._stop_event.is_set():
            self.check_all()
            self._stop_event.wait(timeout=self._check_interval)

    @staticmethod
    def _compute_overall_status(
        results: dict[str, ComponentHealth],
    ) -> ServiceStatus:
        """전체 상태 계산 (최악의 컴포넌트 기준).

        우선순위: UNHEALTHY > DEGRADED > HEALTHY
        """
        if not results:
            return ServiceStatus.UNKNOWN

        statuses = {r.status for r in results.values()}

        if ServiceStatus.UNHEALTHY in statuses:
            return ServiceStatus.UNHEALTHY
        if ServiceStatus.DEGRADED in statuses:
            return ServiceStatus.DEGRADED
        if ServiceStatus.HEALTHY in statuses:
            return ServiceStatus.HEALTHY
        return ServiceStatus.UNKNOWN

    def __repr__(self) -> str:
        return (
            f"HealthChecker("
            f"components={self.component_count}, "
            f"running={self.is_running})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터 클래스
    "ComponentHealth",
    "HealthReport",
    # 타입
    "HealthCheckFn",
    "StatusChangeCallback",
    # 핵심 클래스
    "HealthChecker",
    # 상수
    "DEFAULT_CHECK_INTERVAL",
    "MIN_CHECK_INTERVAL",
    "MAX_CHECK_INTERVAL",
    "MAX_COMPONENTS",
    "CHECK_TIMEOUT",
    "MAX_STATUS_HISTORY",
]

__version__ = "1.0.0"
