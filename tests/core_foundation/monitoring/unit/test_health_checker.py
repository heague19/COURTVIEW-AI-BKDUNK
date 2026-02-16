# -*- coding: utf-8 -*-
"""
COURTVIEW - health_checker.py 단위 테스트

18개 카테고리, 114개 테스트

실행:
    python tests/core_foundation/monitoring/unit/test_health_checker.py
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================
# TestResult 클래스 (pytest 미사용)
# ============================================================
class TestResult:
    """테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str = "") -> None:
        self.failed += 1
        self.failures.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> None:
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)


# ============================================================
# 임포트
# ============================================================
from core_foundation.monitoring.health_checker import (
    # Enum
    HealthStatus,
    DependencyType,
    # 상수
    DEFAULT_CHECK_TIMEOUT,
    MAX_HEALTH_HISTORY,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_CPU_WARNING_THRESHOLD,
    DEFAULT_CPU_CRITICAL_THRESHOLD,
    DEFAULT_MEMORY_WARNING_THRESHOLD,
    DEFAULT_MEMORY_CRITICAL_THRESHOLD,
    DEFAULT_DISK_WARNING_THRESHOLD,
    DEFAULT_DISK_CRITICAL_THRESHOLD,
    DEFAULT_GPU_TEMP_WARNING,
    DEFAULT_GPU_TEMP_CRITICAL,
    DEFAULT_GPU_MEMORY_WARNING,
    DEFAULT_GPU_MEMORY_CRITICAL,
    DEFAULT_DISK_PATH,
    HEALTH_CHECK_THREAD_POOL_SIZE,
    CONSECUTIVE_FAILURE_THRESHOLD,
    PSUTIL_AVAILABLE,
    TORCH_AVAILABLE,
    CV2_AVAILABLE,
    # 데이터 클래스
    HealthCheckResult,
    DependencyHealth,
    SystemHealth,
    HealthCheckConfig,
    # 메인 클래스
    HealthChecker,
    # 함수
    create_health_check,
    aggregate_health_status,
    # 빌트인 체크
    check_cpu_health,
    check_memory_health,
    check_disk_health,
    check_tcp_port,
    check_gpu_health,
    check_camera_health,
    # 싱글톤
    _get_health_checker,
    _reset_health_checker,
)


# ============================================================
# 헬퍼
# ============================================================
def _make_checker(**kwargs) -> HealthChecker:
    """테스트용 HealthChecker 팩토리 (시스템 체크 비활성)."""
    defaults = dict(
        enabled=True,
        enable_system_checks=False,
        max_history=100,
        default_timeout=2.0,
    )
    defaults.update(kwargs)
    return HealthChecker(**defaults)


def _healthy_check_func() -> HealthCheckResult:
    """항상 HEALTHY 반환하는 체크 함수."""
    return HealthCheckResult.healthy(
        name="test_ok",
        dependency_type=DependencyType.CUSTOM,
        message="OK",
        response_time_ms=1.0,
    )


def _unhealthy_check_func() -> HealthCheckResult:
    """항상 UNHEALTHY 반환하는 체크 함수."""
    return HealthCheckResult.unhealthy(
        name="test_fail",
        dependency_type=DependencyType.CUSTOM,
        message="Failed",
        error="test error",
        response_time_ms=5.0,
    )


def _slow_check_func() -> HealthCheckResult:
    """3초 지연 체크 함수 (타임아웃 테스트용)."""
    time.sleep(3.0)
    return HealthCheckResult.healthy(
        name="slow",
        dependency_type=DependencyType.CUSTOM,
    )


def _reset_singleton() -> None:
    """싱글톤 안전 초기화."""
    try:
        _reset_health_checker()
    except Exception:
        pass


# =============================================================================
# [1] 상수 검증 (8개)
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 검증."""
    print("\n[1] 상수 검증")

    # 1-1. DEFAULT_CHECK_TIMEOUT / MAX_HEALTH_HISTORY / DEFAULT_CHECK_INTERVAL
    try:
        assert DEFAULT_CHECK_TIMEOUT == 5.0
        assert MAX_HEALTH_HISTORY == 1000
        assert DEFAULT_CHECK_INTERVAL == 30.0
        result.ok("1-1 기본 상수 (3개)")
    except AssertionError as e:
        result.fail("1-1 기본 상수", str(e))

    # 1-2. CPU/Memory/Disk 임계치 (6개)
    try:
        assert DEFAULT_CPU_WARNING_THRESHOLD == 80.0
        assert DEFAULT_CPU_CRITICAL_THRESHOLD == 95.0
        assert DEFAULT_MEMORY_WARNING_THRESHOLD == 80.0
        assert DEFAULT_MEMORY_CRITICAL_THRESHOLD == 95.0
        assert DEFAULT_DISK_WARNING_THRESHOLD == 80.0
        assert DEFAULT_DISK_CRITICAL_THRESHOLD == 95.0
        result.ok("1-2 리소스 임계치 (6개)")
    except AssertionError as e:
        result.fail("1-2 리소스 임계치", str(e))

    # 1-3. GPU 임계치 (4개)
    try:
        assert DEFAULT_GPU_TEMP_WARNING == 80.0
        assert DEFAULT_GPU_TEMP_CRITICAL == 90.0
        assert DEFAULT_GPU_MEMORY_WARNING == 85.0
        assert DEFAULT_GPU_MEMORY_CRITICAL == 95.0
        result.ok("1-3 GPU 임계치 (4개)")
    except AssertionError as e:
        result.fail("1-3 GPU 임계치", str(e))

    # 1-4. DEFAULT_DISK_PATH (OS별)
    try:
        import platform
        if platform.system() == "Windows":
            assert DEFAULT_DISK_PATH == "C:\\"
        else:
            assert DEFAULT_DISK_PATH == "/"
        result.ok("1-4 DEFAULT_DISK_PATH (OS별)")
    except AssertionError as e:
        result.fail("1-4 DISK_PATH", str(e))

    # 1-5. HEALTH_CHECK_THREAD_POOL_SIZE / CONSECUTIVE_FAILURE_THRESHOLD
    try:
        assert HEALTH_CHECK_THREAD_POOL_SIZE == 8
        assert CONSECUTIVE_FAILURE_THRESHOLD == 3
        result.ok("1-5 스레드풀/연속실패 상수")
    except AssertionError as e:
        result.fail("1-5 기타 상수", str(e))

    # 1-6. 모든 임계치 타입 float
    try:
        thresholds = [
            DEFAULT_CPU_WARNING_THRESHOLD, DEFAULT_CPU_CRITICAL_THRESHOLD,
            DEFAULT_MEMORY_WARNING_THRESHOLD, DEFAULT_MEMORY_CRITICAL_THRESHOLD,
            DEFAULT_DISK_WARNING_THRESHOLD, DEFAULT_DISK_CRITICAL_THRESHOLD,
            DEFAULT_GPU_TEMP_WARNING, DEFAULT_GPU_TEMP_CRITICAL,
            DEFAULT_GPU_MEMORY_WARNING, DEFAULT_GPU_MEMORY_CRITICAL,
        ]
        assert all(isinstance(t, float) for t in thresholds)
        result.ok("1-6 임계치 타입 모두 float (10개)")
    except AssertionError as e:
        result.fail("1-6 타입 검증", str(e))

    # 1-7. PSUTIL_AVAILABLE / TORCH_AVAILABLE / CV2_AVAILABLE 불리언
    try:
        assert isinstance(PSUTIL_AVAILABLE, bool)
        assert isinstance(TORCH_AVAILABLE, bool)
        assert isinstance(CV2_AVAILABLE, bool)
        result.ok("1-7 선택적 의존성 불리언")
    except AssertionError as e:
        result.fail("1-7 의존성 불리언", str(e))

    # 1-8. warning < critical 관계
    try:
        assert DEFAULT_CPU_WARNING_THRESHOLD < DEFAULT_CPU_CRITICAL_THRESHOLD
        assert DEFAULT_MEMORY_WARNING_THRESHOLD < DEFAULT_MEMORY_CRITICAL_THRESHOLD
        assert DEFAULT_DISK_WARNING_THRESHOLD < DEFAULT_DISK_CRITICAL_THRESHOLD
        assert DEFAULT_GPU_TEMP_WARNING < DEFAULT_GPU_TEMP_CRITICAL
        assert DEFAULT_GPU_MEMORY_WARNING < DEFAULT_GPU_MEMORY_CRITICAL
        result.ok("1-8 warning < critical 관계 검증")
    except AssertionError as e:
        result.fail("1-8 임계치 순서", str(e))


# =============================================================================
# [2] HealthStatus Enum (6개)
# =============================================================================
def test_health_status(result: TestResult) -> None:
    """HealthStatus Enum 검증."""
    print("\n[2] HealthStatus Enum")

    # 2-1. 멤버 4개
    try:
        members = list(HealthStatus)
        assert len(members) == 4, f"실제: {len(members)}"
        result.ok("2-1 HealthStatus 멤버 4개")
    except AssertionError as e:
        result.fail("2-1 멤버 수", str(e))

    # 2-2. 값 검증
    try:
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
        result.ok("2-2 HealthStatus 값 (4개)")
    except AssertionError as e:
        result.fail("2-2 값 검증", str(e))

    # 2-3. is_ok 프로퍼티
    try:
        assert HealthStatus.HEALTHY.is_ok is True
        assert HealthStatus.DEGRADED.is_ok is True
        assert HealthStatus.UNHEALTHY.is_ok is False
        assert HealthStatus.UNKNOWN.is_ok is False
        result.ok("2-3 is_ok 프로퍼티")
    except AssertionError as e:
        result.fail("2-3 is_ok", str(e))

    # 2-4. 문자열 변환
    try:
        assert HealthStatus("healthy") == HealthStatus.HEALTHY
        assert HealthStatus("unknown") == HealthStatus.UNKNOWN
        result.ok("2-4 문자열 변환")
    except (AssertionError, ValueError) as e:
        result.fail("2-4 문자열 변환", str(e))

    # 2-5. __lt__ 심각도 순서 (HEALTHY < DEGRADED < UNKNOWN < UNHEALTHY)
    try:
        assert HealthStatus.HEALTHY < HealthStatus.DEGRADED
        assert HealthStatus.DEGRADED < HealthStatus.UNKNOWN
        assert HealthStatus.UNKNOWN < HealthStatus.UNHEALTHY
        assert not (HealthStatus.UNHEALTHY < HealthStatus.HEALTHY)
        result.ok("2-5 __lt__ 심각도 순서")
    except AssertionError as e:
        result.fail("2-5 __lt__", str(e))

    # 2-6. 잘못된 값 -> ValueError
    try:
        raised = False
        try:
            HealthStatus("invalid")
        except ValueError:
            raised = True
        assert raised
        result.ok("2-6 잘못된 값 -> ValueError")
    except AssertionError as e:
        result.fail("2-6 ValueError", str(e))


# =============================================================================
# [3] DependencyType Enum (6개)
# =============================================================================
def test_dependency_type(result: TestResult) -> None:
    """DependencyType Enum 검증."""
    print("\n[3] DependencyType Enum")

    # 3-1. 멤버 9개
    try:
        members = list(DependencyType)
        assert len(members) == 9, f"실제: {len(members)}"
        result.ok("3-1 DependencyType 멤버 9개")
    except AssertionError as e:
        result.fail("3-1 멤버 수", str(e))

    # 3-2. 값 검증
    try:
        expected = {
            "DATABASE": "database", "CACHE": "cache", "STORAGE": "storage",
            "GPU": "gpu", "CAMERA": "camera", "SYSTEM_RESOURCE": "system_resource",
            "MODEL": "model", "EXTERNAL_API": "external_api", "CUSTOM": "custom",
        }
        for name, value in expected.items():
            assert DependencyType[name].value == value
        result.ok("3-2 DependencyType 값 (9개)")
    except AssertionError as e:
        result.fail("3-2 값 검증", str(e))

    # 3-3. is_critical (DATABASE, GPU, MODEL -> True)
    try:
        assert DependencyType.DATABASE.is_critical is True
        assert DependencyType.GPU.is_critical is True
        assert DependencyType.MODEL.is_critical is True
        result.ok("3-3 is_critical True (3개)")
    except AssertionError as e:
        result.fail("3-3 is_critical True", str(e))

    # 3-4. is_critical (나머지 -> False)
    try:
        non_critical = [
            DependencyType.CACHE, DependencyType.STORAGE,
            DependencyType.CAMERA, DependencyType.SYSTEM_RESOURCE,
            DependencyType.EXTERNAL_API, DependencyType.CUSTOM,
        ]
        for dt in non_critical:
            assert dt.is_critical is False, f"{dt.name}.is_critical != False"
        result.ok("3-4 is_critical False (6개)")
    except AssertionError as e:
        result.fail("3-4 is_critical False", str(e))

    # 3-5. 문자열 변환
    try:
        assert DependencyType("database") == DependencyType.DATABASE
        assert DependencyType("gpu") == DependencyType.GPU
        result.ok("3-5 문자열 변환")
    except (AssertionError, ValueError) as e:
        result.fail("3-5 문자열 변환", str(e))

    # 3-6. 잘못된 값 -> ValueError
    try:
        raised = False
        try:
            DependencyType("invalid")
        except ValueError:
            raised = True
        assert raised
        result.ok("3-6 잘못된 값 -> ValueError")
    except AssertionError as e:
        result.fail("3-6 ValueError", str(e))


# =============================================================================
# [4] HealthCheckResult 데이터 클래스 (8개)
# =============================================================================
def test_health_check_result(result: TestResult) -> None:
    """HealthCheckResult 데이터 클래스 검증."""
    print("\n[4] HealthCheckResult 데이터 클래스")

    # 4-1. 기본 생성 (필수 + 기본값)
    try:
        hcr = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            dependency_type=DependencyType.CUSTOM,
        )
        assert hcr.name == "test"
        assert hcr.status == HealthStatus.HEALTHY
        assert hcr.message == ""
        assert hcr.response_time_ms == 0.0
        assert isinstance(hcr.timestamp, datetime)
        assert hcr.metadata == {}
        assert hcr.error is None
        result.ok("4-1 기본 생성 (기본값 검증)")
    except AssertionError as e:
        result.fail("4-1 기본 생성", str(e))

    # 4-2. to_dict 구조
    try:
        hcr = HealthCheckResult(
            name="test",
            status=HealthStatus.DEGRADED,
            dependency_type=DependencyType.GPU,
            message="high temp",
            response_time_ms=12.345,
            error="warn",
        )
        d = hcr.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "degraded"
        assert d["dependency_type"] == "gpu"
        assert d["message"] == "high temp"
        assert d["response_time_ms"] == 12.35  # round(2)
        assert "timestamp" in d
        assert d["error"] == "warn"
        result.ok("4-2 to_dict 구조/반올림")
    except AssertionError as e:
        result.fail("4-2 to_dict", str(e))

    # 4-3. healthy() 클래스메소드
    try:
        hcr = HealthCheckResult.healthy(
            name="cpu",
            dependency_type=DependencyType.SYSTEM_RESOURCE,
            message="CPU OK",
            response_time_ms=2.5,
            metadata={"percent": 30.0},
        )
        assert hcr.status == HealthStatus.HEALTHY
        assert hcr.name == "cpu"
        assert hcr.metadata["percent"] == 30.0
        assert hcr.error is None
        result.ok("4-3 healthy() 클래스메소드")
    except AssertionError as e:
        result.fail("4-3 healthy()", str(e))

    # 4-4. degraded() 클래스메소드
    try:
        hcr = HealthCheckResult.degraded(
            name="mem",
            dependency_type=DependencyType.SYSTEM_RESOURCE,
            message="Memory high",
        )
        assert hcr.status == HealthStatus.DEGRADED
        assert hcr.error is None
        result.ok("4-4 degraded() 클래스메소드")
    except AssertionError as e:
        result.fail("4-4 degraded()", str(e))

    # 4-5. unhealthy() 클래스메소드
    try:
        hcr = HealthCheckResult.unhealthy(
            name="gpu",
            dependency_type=DependencyType.GPU,
            message="GPU OOM",
            error="CUDA out of memory",
            response_time_ms=50.0,
        )
        assert hcr.status == HealthStatus.UNHEALTHY
        assert hcr.error == "CUDA out of memory"
        result.ok("4-5 unhealthy() 클래스메소드")
    except AssertionError as e:
        result.fail("4-5 unhealthy()", str(e))

    # 4-6. unknown() 클래스메소드
    try:
        hcr = HealthCheckResult.unknown(
            name="cam",
            dependency_type=DependencyType.CAMERA,
        )
        assert hcr.status == HealthStatus.UNKNOWN
        assert "timed out" in hcr.message.lower() or "failed" in hcr.message.lower()
        result.ok("4-6 unknown() 클래스메소드")
    except AssertionError as e:
        result.fail("4-6 unknown()", str(e))

    # 4-7. metadata None -> 빈 딕셔너리
    try:
        hcr = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            metadata=None,
        )
        assert hcr.metadata == {}
        result.ok("4-7 metadata None -> {}")
    except AssertionError as e:
        result.fail("4-7 metadata None", str(e))

    # 4-8. 필드 수 8개
    try:
        field_names = [f.name for f in fields(HealthCheckResult)]
        assert len(field_names) == 8, f"실제: {len(field_names)}"
        result.ok("4-8 HealthCheckResult 필드 8개")
    except AssertionError as e:
        result.fail("4-8 필드 수", str(e))


# =============================================================================
# [5] DependencyHealth 데이터 클래스 (8개)
# =============================================================================
def test_dependency_health(result: TestResult) -> None:
    """DependencyHealth 데이터 클래스 검증."""
    print("\n[5] DependencyHealth 데이터 클래스")

    # 5-1. 기본 생성
    try:
        dh = DependencyHealth(name="gpu", dependency_type=DependencyType.GPU)
        assert dh.current_status == HealthStatus.UNKNOWN
        assert dh.consecutive_failures == 0
        assert dh.total_checks == 0
        assert dh.successful_checks == 0
        assert dh.average_response_time_ms == 0.0
        assert dh.last_healthy_time is None
        assert dh.last_check is None
        result.ok("5-1 기본 생성 (기본값)")
    except AssertionError as e:
        result.fail("5-1 기본 생성", str(e))

    # 5-2. update HEALTHY -> 상태 변경
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        healthy_result = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            response_time_ms=10.0,
        )
        dh.update(healthy_result)
        assert dh.current_status == HealthStatus.HEALTHY
        assert dh.consecutive_failures == 0
        assert dh.total_checks == 1
        assert dh.successful_checks == 1
        assert dh.last_healthy_time is not None
        result.ok("5-2 update HEALTHY")
    except AssertionError as e:
        result.fail("5-2 update HEALTHY", str(e))

    # 5-3. update UNHEALTHY 연속 -> consecutive_failures 증가
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        unhealthy_result = HealthCheckResult.unhealthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            message="fail",
        )
        dh.update(unhealthy_result)
        assert dh.consecutive_failures == 1
        assert dh.current_status == HealthStatus.DEGRADED  # 1 < CONSECUTIVE_FAILURE_THRESHOLD
        dh.update(unhealthy_result)
        assert dh.consecutive_failures == 2
        assert dh.current_status == HealthStatus.DEGRADED
        result.ok("5-3 update UNHEALTHY 연속 (1~2회)")
    except AssertionError as e:
        result.fail("5-3 UNHEALTHY 연속", str(e))

    # 5-4. 연속 실패 >= CONSECUTIVE_FAILURE_THRESHOLD -> UNHEALTHY
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        unhealthy_result = HealthCheckResult.unhealthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            message="fail",
        )
        for _ in range(CONSECUTIVE_FAILURE_THRESHOLD):
            dh.update(unhealthy_result)
        assert dh.consecutive_failures == CONSECUTIVE_FAILURE_THRESHOLD
        assert dh.current_status == HealthStatus.UNHEALTHY
        result.ok(f"5-4 연속 {CONSECUTIVE_FAILURE_THRESHOLD}회 실패 -> UNHEALTHY")
    except AssertionError as e:
        result.fail("5-4 연속 실패 임계", str(e))

    # 5-5. HEALTHY 후 consecutive_failures 초기화
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        unhealthy_result = HealthCheckResult.unhealthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            message="fail",
        )
        dh.update(unhealthy_result)
        dh.update(unhealthy_result)
        assert dh.consecutive_failures == 2
        healthy_result = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            response_time_ms=5.0,
        )
        dh.update(healthy_result)
        assert dh.consecutive_failures == 0
        assert dh.current_status == HealthStatus.HEALTHY
        result.ok("5-5 HEALTHY 후 연속실패 초기화")
    except AssertionError as e:
        result.fail("5-5 초기화", str(e))

    # 5-6. uptime_percentage
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        assert dh.uptime_percentage == 0.0  # 0 checks
        healthy_result = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            response_time_ms=1.0,
        )
        unhealthy_result = HealthCheckResult.unhealthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            message="fail",
        )
        dh.update(healthy_result)
        dh.update(healthy_result)
        dh.update(unhealthy_result)
        # 2 success / 3 total = 66.67%
        assert abs(dh.uptime_percentage - 66.67) < 1.0
        result.ok("5-6 uptime_percentage 계산")
    except AssertionError as e:
        result.fail("5-6 uptime_percentage", str(e))

    # 5-7. to_dict 구조
    try:
        dh = DependencyHealth(name="gpu", dependency_type=DependencyType.GPU)
        d = dh.to_dict()
        assert d["name"] == "gpu"
        assert d["dependency_type"] == "gpu"
        assert d["current_status"] == "unknown"
        assert "uptime_percentage" in d
        assert "average_response_time_ms" in d
        assert d["last_check"] is None
        assert d["last_healthy_time"] is None
        result.ok("5-7 to_dict 구조")
    except AssertionError as e:
        result.fail("5-7 to_dict", str(e))

    # 5-8. average_response_time_ms EMA (지수 이동 평균)
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        # 첫 번째: avg = 10.0
        r1 = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            response_time_ms=10.0,
        )
        dh.update(r1)
        assert dh.average_response_time_ms == 10.0
        # 두 번째: avg = 0.2 * 50.0 + 0.8 * 10.0 = 10 + 8 = 18.0
        r2 = HealthCheckResult.healthy(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            response_time_ms=50.0,
        )
        dh.update(r2)
        expected = 0.2 * 50.0 + 0.8 * 10.0
        assert abs(dh.average_response_time_ms - expected) < 0.01, \
            f"실제: {dh.average_response_time_ms}, 기대: {expected}"
        result.ok("5-8 EMA 평균 응답시간")
    except AssertionError as e:
        result.fail("5-8 EMA", str(e))


# =============================================================================
# [6] SystemHealth 데이터 클래스 (6개)
# =============================================================================
def test_system_health(result: TestResult) -> None:
    """SystemHealth 데이터 클래스 검증."""
    print("\n[6] SystemHealth 데이터 클래스")

    # 6-1. 기본 생성
    try:
        sh = SystemHealth(overall_status=HealthStatus.HEALTHY)
        assert sh.overall_status == HealthStatus.HEALTHY
        assert sh.total_checks == 0
        assert sh.healthy_checks == 0
        assert sh.results == []
        assert sh.check_duration_ms == 0.0
        assert isinstance(sh.timestamp, datetime)
        result.ok("6-1 기본 생성")
    except AssertionError as e:
        result.fail("6-1 기본 생성", str(e))

    # 6-2. to_dict 구조 (summary 중첩)
    try:
        sh = SystemHealth(
            overall_status=HealthStatus.DEGRADED,
            total_checks=3,
            healthy_checks=2,
            degraded_checks=1,
            check_duration_ms=123.456,
        )
        d = sh.to_dict()
        assert d["overall_status"] == "degraded"
        assert "summary" in d
        assert d["summary"]["total_checks"] == 3
        assert d["summary"]["healthy"] == 2
        assert d["summary"]["degraded"] == 1
        assert d["check_duration_ms"] == 123.46  # round(2)
        assert "results" in d
        result.ok("6-2 to_dict 구조 (summary 중첩)")
    except AssertionError as e:
        result.fail("6-2 to_dict", str(e))

    # 6-3. is_healthy 프로퍼티
    try:
        sh_ok = SystemHealth(overall_status=HealthStatus.HEALTHY)
        sh_bad = SystemHealth(overall_status=HealthStatus.UNHEALTHY)
        assert sh_ok.is_healthy is True
        assert sh_bad.is_healthy is False
        result.ok("6-3 is_healthy 프로퍼티")
    except AssertionError as e:
        result.fail("6-3 is_healthy", str(e))

    # 6-4. is_operational (HEALTHY/DEGRADED -> True)
    try:
        assert SystemHealth(overall_status=HealthStatus.HEALTHY).is_operational is True
        assert SystemHealth(overall_status=HealthStatus.DEGRADED).is_operational is True
        assert SystemHealth(overall_status=HealthStatus.UNHEALTHY).is_operational is False
        assert SystemHealth(overall_status=HealthStatus.UNKNOWN).is_operational is False
        result.ok("6-4 is_operational 프로퍼티")
    except AssertionError as e:
        result.fail("6-4 is_operational", str(e))

    # 6-5. results 리스트에 HealthCheckResult 포함
    try:
        r1 = HealthCheckResult.healthy("a", DependencyType.CUSTOM)
        r2 = HealthCheckResult.unhealthy("b", DependencyType.GPU, "fail")
        sh = SystemHealth(
            overall_status=HealthStatus.DEGRADED,
            results=[r1, r2],
            total_checks=2,
        )
        d = sh.to_dict()
        assert len(d["results"]) == 2
        assert d["results"][0]["status"] == "healthy"
        assert d["results"][1]["status"] == "unhealthy"
        result.ok("6-5 results to_dict 직렬화")
    except AssertionError as e:
        result.fail("6-5 results", str(e))

    # 6-6. 필드 수 10개
    try:
        field_names = [f.name for f in fields(SystemHealth)]
        assert len(field_names) == 10, f"실제: {len(field_names)}"
        result.ok("6-6 SystemHealth 필드 10개")
    except AssertionError as e:
        result.fail("6-6 필드 수", str(e))


# =============================================================================
# [7] HealthCheckConfig 데이터 클래스 (5개)
# =============================================================================
def test_health_check_config(result: TestResult) -> None:
    """HealthCheckConfig 데이터 클래스 검증."""
    print("\n[7] HealthCheckConfig 데이터 클래스")

    # 7-1. 기본 생성
    try:
        cfg = HealthCheckConfig(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            check_func=_healthy_check_func,
        )
        assert cfg.name == "test"
        assert cfg.dependency_type == DependencyType.CUSTOM
        assert cfg.timeout == DEFAULT_CHECK_TIMEOUT
        assert cfg.interval == DEFAULT_CHECK_INTERVAL
        assert cfg.critical is False
        assert cfg.enabled is True
        assert cfg.tags == set()
        assert cfg.is_async is False
        result.ok("7-1 기본 생성 (기본값)")
    except AssertionError as e:
        result.fail("7-1 기본 생성", str(e))

    # 7-2. 커스텀 값 설정
    try:
        cfg = HealthCheckConfig(
            name="gpu",
            dependency_type=DependencyType.GPU,
            check_func=_healthy_check_func,
            timeout=10.0,
            interval=60.0,
            critical=True,
            enabled=False,
            tags={"hardware", "gpu"},
        )
        assert cfg.timeout == 10.0
        assert cfg.interval == 60.0
        assert cfg.critical is True
        assert cfg.enabled is False
        assert "gpu" in cfg.tags
        result.ok("7-2 커스텀 값 설정")
    except AssertionError as e:
        result.fail("7-2 커스텀 값", str(e))

    # 7-3. is_async 감지 (비동기 함수)
    try:
        async def async_check() -> HealthCheckResult:
            return HealthCheckResult.healthy("async_test", DependencyType.CUSTOM)

        cfg = HealthCheckConfig(
            name="async",
            dependency_type=DependencyType.CUSTOM,
            check_func=async_check,
            is_async=True,
        )
        assert cfg.is_async is True
        result.ok("7-3 is_async=True (비동기)")
    except AssertionError as e:
        result.fail("7-3 is_async", str(e))

    # 7-4. check_func 호출 가능
    try:
        cfg = HealthCheckConfig(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            check_func=_healthy_check_func,
        )
        r = cfg.check_func()
        assert isinstance(r, HealthCheckResult)
        assert r.status == HealthStatus.HEALTHY
        result.ok("7-4 check_func 호출 가능")
    except AssertionError as e:
        result.fail("7-4 check_func", str(e))

    # 7-5. 필드 수 9개
    try:
        field_names = [f.name for f in fields(HealthCheckConfig)]
        assert len(field_names) == 9, f"실제: {len(field_names)}"
        result.ok("7-5 HealthCheckConfig 필드 9개")
    except AssertionError as e:
        result.fail("7-5 필드 수", str(e))


# =============================================================================
# [8] aggregate_health_status 함수 (7개)
# =============================================================================
def test_aggregate_health_status(result: TestResult) -> None:
    """aggregate_health_status 함수 검증."""
    print("\n[8] aggregate_health_status 함수")

    # 8-1. 빈 리스트 -> UNKNOWN
    try:
        assert aggregate_health_status([]) == HealthStatus.UNKNOWN
        result.ok("8-1 빈 리스트 -> UNKNOWN")
    except AssertionError as e:
        result.fail("8-1 빈 리스트", str(e))

    # 8-2. 모두 HEALTHY -> HEALTHY
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.healthy("b", DependencyType.SYSTEM_RESOURCE),
        ]
        assert aggregate_health_status(results) == HealthStatus.HEALTHY
        result.ok("8-2 모두 HEALTHY -> HEALTHY")
    except AssertionError as e:
        result.fail("8-2 모두 HEALTHY", str(e))

    # 8-3. 하나 DEGRADED -> DEGRADED
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.degraded("b", DependencyType.SYSTEM_RESOURCE, "high"),
        ]
        assert aggregate_health_status(results) == HealthStatus.DEGRADED
        result.ok("8-3 하나 DEGRADED -> DEGRADED")
    except AssertionError as e:
        result.fail("8-3 DEGRADED", str(e))

    # 8-4. 중요 의존성 UNHEALTHY -> UNHEALTHY
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.unhealthy("gpu", DependencyType.GPU, "OOM"),
        ]
        assert aggregate_health_status(results) == HealthStatus.UNHEALTHY
        result.ok("8-4 중요 의존성 UNHEALTHY -> UNHEALTHY")
    except AssertionError as e:
        result.fail("8-4 critical UNHEALTHY", str(e))

    # 8-5. 비중요 의존성 UNHEALTHY -> DEGRADED
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.unhealthy("cam", DependencyType.CAMERA, "disconnected"),
        ]
        assert aggregate_health_status(results) == HealthStatus.DEGRADED
        result.ok("8-5 비중요 UNHEALTHY -> DEGRADED")
    except AssertionError as e:
        result.fail("8-5 non-critical UNHEALTHY", str(e))

    # 8-6. UNKNOWN만 -> DEGRADED
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.unknown("b", DependencyType.EXTERNAL_API),
        ]
        assert aggregate_health_status(results) == HealthStatus.DEGRADED
        result.ok("8-6 UNKNOWN -> DEGRADED")
    except AssertionError as e:
        result.fail("8-6 UNKNOWN", str(e))

    # 8-7. 복합 (critical UNHEALTHY 우선)
    try:
        results = [
            HealthCheckResult.healthy("a", DependencyType.CUSTOM),
            HealthCheckResult.degraded("b", DependencyType.SYSTEM_RESOURCE, "high"),
            HealthCheckResult.unhealthy("db", DependencyType.DATABASE, "conn fail"),
        ]
        # DATABASE is_critical -> UNHEALTHY
        assert aggregate_health_status(results) == HealthStatus.UNHEALTHY
        result.ok("8-7 복합 (critical 우선)")
    except AssertionError as e:
        result.fail("8-7 복합", str(e))


# =============================================================================
# [9] create_health_check 함수 (5개)
# =============================================================================
def test_create_health_check(result: TestResult) -> None:
    """create_health_check 헬퍼 검증."""
    print("\n[9] create_health_check 함수")

    # 9-1. 성공 -> HEALTHY
    try:
        check_fn = create_health_check(
            name="sqlite",
            dependency_type=DependencyType.DATABASE,
            check_func=lambda: True,
        )
        r = check_fn()
        assert isinstance(r, HealthCheckResult)
        assert r.status == HealthStatus.HEALTHY
        assert r.name == "sqlite"
        result.ok("9-1 성공 -> HEALTHY")
    except AssertionError as e:
        result.fail("9-1 성공", str(e))

    # 9-2. 실패 -> UNHEALTHY
    try:
        check_fn = create_health_check(
            name="sqlite",
            dependency_type=DependencyType.DATABASE,
            check_func=lambda: False,
            failure_message="DB down",
        )
        r = check_fn()
        assert r.status == HealthStatus.UNHEALTHY
        assert r.message == "DB down"
        result.ok("9-2 실패 -> UNHEALTHY")
    except AssertionError as e:
        result.fail("9-2 실패", str(e))

    # 9-3. 예외 -> UNHEALTHY with error
    try:
        def raise_err():
            raise ConnectionError("timeout")

        check_fn = create_health_check(
            name="db",
            dependency_type=DependencyType.DATABASE,
            check_func=raise_err,
        )
        r = check_fn()
        assert r.status == HealthStatus.UNHEALTHY
        assert r.error is not None
        assert "timeout" in r.error
        result.ok("9-3 예외 -> UNHEALTHY with error")
    except AssertionError as e:
        result.fail("9-3 예외", str(e))

    # 9-4. response_time_ms 측정
    try:
        def slow_check():
            time.sleep(0.05)
            return True

        check_fn = create_health_check(
            name="slow",
            dependency_type=DependencyType.CUSTOM,
            check_func=slow_check,
        )
        r = check_fn()
        assert r.response_time_ms >= 40.0, f"응답시간: {r.response_time_ms}ms"
        result.ok("9-4 response_time_ms 측정")
    except AssertionError as e:
        result.fail("9-4 응답시간", str(e))

    # 9-5. 커스텀 메시지
    try:
        check_fn = create_health_check(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            check_func=lambda: True,
            success_message="All good",
            failure_message="Bad",
        )
        r = check_fn()
        assert r.message == "All good"
        result.ok("9-5 커스텀 성공 메시지")
    except AssertionError as e:
        result.fail("9-5 커스텀 메시지", str(e))


# =============================================================================
# [10] 빌트인 체크 함수 (6개)
# =============================================================================
def test_builtin_checks(result: TestResult) -> None:
    """빌트인 헬스 체크 함수 검증."""
    print("\n[10] 빌트인 체크 함수")

    # 10-1. check_cpu_health -> HealthCheckResult
    try:
        r = check_cpu_health()
        assert isinstance(r, HealthCheckResult)
        assert r.name == "cpu"
        assert r.dependency_type == DependencyType.SYSTEM_RESOURCE
        if PSUTIL_AVAILABLE:
            assert r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
            assert r.response_time_ms > 0
        else:
            assert r.status == HealthStatus.UNKNOWN
        result.ok("10-1 check_cpu_health")
    except AssertionError as e:
        result.fail("10-1 cpu_health", str(e))

    # 10-2. check_memory_health -> HealthCheckResult
    try:
        r = check_memory_health()
        assert isinstance(r, HealthCheckResult)
        assert r.name == "memory"
        if PSUTIL_AVAILABLE:
            assert r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
            assert "memory_percent" in r.metadata
        else:
            assert r.status == HealthStatus.UNKNOWN
        result.ok("10-2 check_memory_health")
    except AssertionError as e:
        result.fail("10-2 memory_health", str(e))

    # 10-3. check_disk_health -> HealthCheckResult
    try:
        r = check_disk_health()
        assert isinstance(r, HealthCheckResult)
        assert r.name == "disk"
        if PSUTIL_AVAILABLE:
            assert r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
        else:
            assert r.status == HealthStatus.UNKNOWN
        result.ok("10-3 check_disk_health")
    except AssertionError as e:
        result.fail("10-3 disk_health", str(e))

    # 10-4. check_tcp_port 연결 실패 -> UNHEALTHY
    try:
        # 닫혀 있는 포트에 연결 시도
        r = check_tcp_port(
            host="127.0.0.1",
            port=59999,  # 사용 안 하는 포트
            name="test_port",
            dependency_type=DependencyType.EXTERNAL_API,
            timeout=1.0,
        )
        assert isinstance(r, HealthCheckResult)
        assert r.status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN)
        result.ok("10-4 check_tcp_port (닫힌 포트)")
    except AssertionError as e:
        result.fail("10-4 tcp_port", str(e))

    # 10-5. check_gpu_health (CUDA 없으면 UNHEALTHY)
    try:
        r = check_gpu_health()
        assert isinstance(r, HealthCheckResult)
        if not TORCH_AVAILABLE:
            assert r.status == HealthStatus.UNHEALTHY
            assert "CUDA" in r.message
        else:
            assert r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
        result.ok("10-5 check_gpu_health")
    except AssertionError as e:
        result.fail("10-5 gpu_health", str(e))

    # 10-6. check_camera_health (cv2 없으면 UNKNOWN)
    try:
        r = check_camera_health()
        assert isinstance(r, HealthCheckResult)
        if not CV2_AVAILABLE:
            assert r.status == HealthStatus.UNKNOWN
        # cv2 있어도 카메라 없으면 UNHEALTHY 가능
        result.ok("10-6 check_camera_health")
    except AssertionError as e:
        result.fail("10-6 camera_health", str(e))


# =============================================================================
# [11] HealthChecker 초기화 (7개)
# =============================================================================
def test_health_checker_init(result: TestResult) -> None:
    """HealthChecker 초기화 검증."""
    print("\n[11] HealthChecker 초기화")

    # 11-1. 기본 초기화 (시스템 체크 비활성)
    try:
        hc = _make_checker()
        assert hc.enabled is True
        assert hc.check_count == 0  # 시스템 체크 비활성
        result.ok("11-1 기본 초기화")
    except Exception as e:
        result.fail("11-1 기본 초기화", str(e))

    # 11-2. 파라미터 오버라이드
    try:
        hc = _make_checker(
            enabled=False,
            default_timeout=10.0,
            default_interval=60.0,
        )
        assert hc.enabled is False
        assert hc._default_timeout == 10.0
        assert hc._default_interval == 60.0
        result.ok("11-2 파라미터 오버라이드")
    except Exception as e:
        result.fail("11-2 오버라이드", str(e))

    # 11-3. enabled 프로퍼티 getter/setter
    try:
        hc = _make_checker()
        assert hc.enabled is True
        hc.enabled = False
        assert hc.enabled is False
        hc.enabled = True
        assert hc.enabled is True
        result.ok("11-3 enabled getter/setter")
    except Exception as e:
        result.fail("11-3 enabled", str(e))

    # 11-4. check_count 초기
    try:
        hc = _make_checker()
        assert hc.check_count == 0
        hc.register_check(
            name="test",
            check_func=_healthy_check_func,
            dependency_type=DependencyType.CUSTOM,
        )
        assert hc.check_count == 1
        result.ok("11-4 check_count")
    except Exception as e:
        result.fail("11-4 check_count", str(e))

    # 11-5. enable_system_checks=True -> cpu/memory/disk 자동 등록
    try:
        hc = HealthChecker(enable_system_checks=True, default_timeout=2.0)
        checks = hc.list_checks()
        # cpu, memory, disk는 기본 등록 (psutil 있으면)
        if PSUTIL_AVAILABLE:
            assert "cpu" in checks
            assert "memory" in checks
            assert "disk" in checks
        hc.shutdown()
        result.ok("11-5 시스템 체크 자동 등록")
    except Exception as e:
        result.fail("11-5 시스템 체크", str(e))

    # 11-6. enable_system_checks=False -> 자동 등록 없음
    try:
        hc = _make_checker(enable_system_checks=False)
        assert hc.check_count == 0
        result.ok("11-6 시스템 체크 비활성")
    except Exception as e:
        result.fail("11-6 시스템 체크 비활성", str(e))

    # 11-7. max_history 적용
    try:
        hc = _make_checker(max_history=5)
        assert hc._max_history == 5
        result.ok("11-7 max_history 적용")
    except Exception as e:
        result.fail("11-7 max_history", str(e))


# =============================================================================
# [12] HealthChecker register/unregister (7개)
# =============================================================================
def test_register_unregister(result: TestResult) -> None:
    """HealthChecker register/unregister 검증."""
    print("\n[12] HealthChecker register/unregister")

    # 12-1. register_check 기본
    try:
        hc = _make_checker()
        hc.register_check(
            name="custom_db",
            check_func=_healthy_check_func,
            dependency_type=DependencyType.DATABASE,
            critical=True,
        )
        assert hc.check_count == 1
        result.ok("12-1 register_check 기본")
    except Exception as e:
        result.fail("12-1 register", str(e))

    # 12-2. register_check -> DependencyHealth 생성
    try:
        hc = _make_checker()
        hc.register_check(
            name="gpu_check",
            check_func=_healthy_check_func,
            dependency_type=DependencyType.GPU,
        )
        dep = hc.get_dependency_status("gpu_check")
        assert dep is not None
        assert dep.name == "gpu_check"
        assert dep.dependency_type == DependencyType.GPU
        assert dep.current_status == HealthStatus.UNKNOWN
        result.ok("12-2 DependencyHealth 자동 생성")
    except Exception as e:
        result.fail("12-2 DependencyHealth", str(e))

    # 12-3. list_checks
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.register_check("b", _healthy_check_func, DependencyType.CACHE)
        checks = hc.list_checks()
        assert "a" in checks
        assert "b" in checks
        assert len(checks) == 2
        result.ok("12-3 list_checks (2개)")
    except Exception as e:
        result.fail("12-3 list_checks", str(e))

    # 12-4. get_check 존재
    try:
        hc = _make_checker()
        hc.register_check("gpu", _healthy_check_func, DependencyType.GPU, critical=True)
        cfg = hc.get_check("gpu")
        assert cfg is not None
        assert cfg.name == "gpu"
        assert cfg.critical is True
        result.ok("12-4 get_check 존재")
    except Exception as e:
        result.fail("12-4 get_check", str(e))

    # 12-5. get_check 미존재 -> None
    try:
        hc = _make_checker()
        cfg = hc.get_check("nonexistent")
        assert cfg is None
        result.ok("12-5 get_check 미존재 -> None")
    except Exception as e:
        result.fail("12-5 get_check None", str(e))

    # 12-6. unregister_check -> True
    try:
        hc = _make_checker()
        hc.register_check("test", _healthy_check_func, DependencyType.CUSTOM)
        assert hc.check_count == 1
        removed = hc.unregister_check("test")
        assert removed is True
        assert hc.check_count == 0
        result.ok("12-6 unregister_check -> True")
    except Exception as e:
        result.fail("12-6 unregister", str(e))

    # 12-7. unregister_check 미존재 -> False
    try:
        hc = _make_checker()
        removed = hc.unregister_check("nonexistent")
        assert removed is False
        result.ok("12-7 unregister 미존재 -> False")
    except Exception as e:
        result.fail("12-7 unregister False", str(e))


# =============================================================================
# [13] HealthChecker check 단일 실행 (6개)
# =============================================================================
def test_check_single(result: TestResult) -> None:
    """HealthChecker check() 단일 실행 검증."""
    print("\n[13] HealthChecker check 단일 실행")

    # 13-1. check (HEALTHY 반환)
    try:
        hc = _make_checker()
        hc.register_check("ok", _healthy_check_func, DependencyType.CUSTOM)
        r = hc.check("ok")
        assert isinstance(r, HealthCheckResult)
        assert r.status == HealthStatus.HEALTHY
        result.ok("13-1 check -> HEALTHY")
    except Exception as e:
        result.fail("13-1 check HEALTHY", str(e))

    # 13-2. check (UNHEALTHY 반환)
    try:
        hc = _make_checker()
        hc.register_check("fail", _unhealthy_check_func, DependencyType.CUSTOM)
        r = hc.check("fail")
        assert r.status == HealthStatus.UNHEALTHY
        result.ok("13-2 check -> UNHEALTHY")
    except Exception as e:
        result.fail("13-2 check UNHEALTHY", str(e))

    # 13-3. check 미등록 -> KeyError
    try:
        hc = _make_checker()
        raised = False
        try:
            hc.check("nonexistent")
        except KeyError:
            raised = True
        assert raised
        result.ok("13-3 check 미등록 -> KeyError")
    except AssertionError as e:
        result.fail("13-3 KeyError", str(e))

    # 13-4. check disabled 체크 -> UNKNOWN
    try:
        hc = _make_checker()
        hc.register_check("dis", _healthy_check_func, DependencyType.CUSTOM, enabled=False)
        r = hc.check("dis")
        assert r.status == HealthStatus.UNKNOWN
        assert "disabled" in r.message.lower()
        result.ok("13-4 disabled 체크 -> UNKNOWN")
    except Exception as e:
        result.fail("13-4 disabled", str(e))

    # 13-5. check 타임아웃 -> UNKNOWN
    try:
        hc = _make_checker(default_timeout=0.5)
        hc.register_check("slow", _slow_check_func, DependencyType.CUSTOM, timeout=0.5)
        r = hc.check("slow")
        assert r.status == HealthStatus.UNKNOWN
        assert "timeout" in r.message.lower() or "timed out" in r.message.lower()
        hc.shutdown()
        result.ok("13-5 타임아웃 -> UNKNOWN")
    except Exception as e:
        result.fail("13-5 타임아웃", str(e))

    # 13-6. check -> DependencyHealth 업데이트
    try:
        hc = _make_checker()
        hc.register_check("dep", _healthy_check_func, DependencyType.CUSTOM)
        hc.check("dep")
        dep = hc.get_dependency_status("dep")
        assert dep is not None
        assert dep.total_checks == 1
        assert dep.current_status == HealthStatus.HEALTHY
        result.ok("13-6 DependencyHealth 업데이트")
    except Exception as e:
        result.fail("13-6 dep 업데이트", str(e))


# =============================================================================
# [14] HealthChecker check_all (8개)
# =============================================================================
def test_check_all(result: TestResult) -> None:
    """HealthChecker check_all() 검증."""
    print("\n[14] HealthChecker check_all")

    # 14-1. check_all 복수 체크 (순차)
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.register_check("b", _healthy_check_func, DependencyType.CACHE)
        sh = hc.check_all(parallel=False)
        assert isinstance(sh, SystemHealth)
        assert sh.overall_status == HealthStatus.HEALTHY
        assert sh.total_checks == 2
        assert sh.healthy_checks == 2
        result.ok("14-1 check_all 순차 (2개 HEALTHY)")
    except Exception as e:
        result.fail("14-1 check_all 순차", str(e))

    # 14-2. check_all disabled -> UNKNOWN
    try:
        hc = _make_checker(enabled=False)
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        sh = hc.check_all()
        assert sh.overall_status == HealthStatus.UNKNOWN
        assert "disabled" in str(sh.metadata).lower()
        result.ok("14-2 check_all disabled -> UNKNOWN")
    except Exception as e:
        result.fail("14-2 disabled", str(e))

    # 14-3. check_all parallel=True
    try:
        hc = _make_checker()
        for i in range(3):
            hc.register_check(f"p{i}", _healthy_check_func, DependencyType.CUSTOM)
        sh = hc.check_all(parallel=True)
        assert sh.total_checks == 3
        assert sh.healthy_checks == 3
        hc.shutdown()
        result.ok("14-3 check_all parallel=True (3개)")
    except Exception as e:
        result.fail("14-3 parallel", str(e))

    # 14-4. check_all 혼합 결과 (HEALTHY + UNHEALTHY)
    try:
        hc = _make_checker()
        hc.register_check("ok", _healthy_check_func, DependencyType.CUSTOM)
        hc.register_check("fail", _unhealthy_check_func, DependencyType.CUSTOM)
        sh = hc.check_all(parallel=False)
        # UNHEALTHY + non-critical -> DEGRADED
        assert sh.overall_status == HealthStatus.DEGRADED
        assert sh.healthy_checks == 1
        assert sh.unhealthy_checks == 1
        result.ok("14-4 혼합 (HEALTHY + UNHEALTHY)")
    except Exception as e:
        result.fail("14-4 혼합", str(e))

    # 14-5. check_all tags 필터링
    try:
        hc = _make_checker()
        hc.register_check("tagged", _healthy_check_func, DependencyType.CUSTOM, tags={"hw"})
        hc.register_check("untagged", _healthy_check_func, DependencyType.CACHE)
        sh = hc.check_all(tags={"hw"}, parallel=False)
        assert sh.total_checks == 1
        result.ok("14-5 tags 필터링 (1/2)")
    except Exception as e:
        result.fail("14-5 tags", str(e))

    # 14-6. check_all -> 히스토리 저장
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.check_all(parallel=False)
        hc.check_all(parallel=False)
        history = hc.get_history()
        assert len(history) == 2
        result.ok("14-6 히스토리 저장 (2회)")
    except Exception as e:
        result.fail("14-6 히스토리", str(e))

    # 14-7. 상태 카운트 정확성
    try:
        hc = _make_checker()
        hc.register_check("ok1", _healthy_check_func, DependencyType.CUSTOM)
        hc.register_check("ok2", _healthy_check_func, DependencyType.CACHE)
        hc.register_check("bad", _unhealthy_check_func, DependencyType.STORAGE)
        sh = hc.check_all(parallel=False)
        assert sh.total_checks == 3
        assert sh.healthy_checks == 2
        assert sh.unhealthy_checks == 1
        assert sh.degraded_checks == 0
        assert sh.unknown_checks == 0
        result.ok("14-7 상태 카운트 정확성")
    except Exception as e:
        result.fail("14-7 카운트", str(e))

    # 14-8. 체크 없음 -> UNKNOWN
    try:
        hc = _make_checker()
        sh = hc.check_all(parallel=False)
        assert sh.overall_status == HealthStatus.UNKNOWN
        result.ok("14-8 체크 없음 -> UNKNOWN")
    except Exception as e:
        result.fail("14-8 체크 없음", str(e))


# =============================================================================
# [15] HealthChecker 유틸리티 메서드 (8개)
# =============================================================================
def test_utility_methods(result: TestResult) -> None:
    """HealthChecker 유틸리티 메서드 검증."""
    print("\n[15] HealthChecker 유틸리티 메서드")

    # 15-1. get_dependency_status
    try:
        hc = _make_checker()
        hc.register_check("gpu", _healthy_check_func, DependencyType.GPU)
        dep = hc.get_dependency_status("gpu")
        assert dep is not None
        assert isinstance(dep, DependencyHealth)
        result.ok("15-1 get_dependency_status")
    except Exception as e:
        result.fail("15-1 get_dep", str(e))

    # 15-2. get_dependency_status 미존재 -> None
    try:
        hc = _make_checker()
        dep = hc.get_dependency_status("nonexistent")
        assert dep is None
        result.ok("15-2 get_dependency_status None")
    except Exception as e:
        result.fail("15-2 dep None", str(e))

    # 15-3. get_all_dependencies
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.register_check("b", _healthy_check_func, DependencyType.GPU)
        deps = hc.get_all_dependencies()
        assert len(deps) == 2
        assert "a" in deps
        assert "b" in deps
        result.ok("15-3 get_all_dependencies (2개)")
    except Exception as e:
        result.fail("15-3 all_deps", str(e))

    # 15-4. get_history (최신순)
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        for _ in range(3):
            hc.check_all(parallel=False)
        history = hc.get_history(limit=2)
        assert len(history) == 2
        # 최신순: [0]이 가장 최근
        assert history[0].timestamp >= history[1].timestamp
        result.ok("15-4 get_history (최신순 limit=2)")
    except Exception as e:
        result.fail("15-4 history", str(e))

    # 15-5. get_current_status (히스토리 없음 -> UNKNOWN)
    try:
        hc = _make_checker()
        assert hc.get_current_status() == HealthStatus.UNKNOWN
        result.ok("15-5 get_current_status (히스토리 없음)")
    except Exception as e:
        result.fail("15-5 current_status", str(e))

    # 15-6. is_healthy / is_operational
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.check_all(parallel=False)
        assert hc.is_healthy() is True
        assert hc.is_operational() is True
        result.ok("15-6 is_healthy/is_operational")
    except Exception as e:
        result.fail("15-6 is_healthy/op", str(e))

    # 15-7. reset 상태 초기화
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.check_all(parallel=False)
        assert len(hc.get_history()) > 0
        hc.reset()
        assert len(hc.get_history()) == 0
        dep = hc.get_dependency_status("a")
        assert dep.total_checks == 0
        assert dep.current_status == HealthStatus.UNKNOWN
        result.ok("15-7 reset 상태 초기화")
    except Exception as e:
        result.fail("15-7 reset", str(e))

    # 15-8. get_status_summary 구조
    try:
        hc = _make_checker()
        hc.register_check("test", _healthy_check_func, DependencyType.CUSTOM)
        hc.check_all(parallel=False)
        summary = hc.get_status_summary()
        assert "status" in summary
        assert "is_operational" in summary
        assert "check_count" in summary
        assert "enabled" in summary
        assert "last_check" in summary
        assert "dependencies" in summary
        assert summary["check_count"] == 1
        assert summary["is_operational"] is True
        result.ok("15-8 get_status_summary 구조")
    except Exception as e:
        result.fail("15-8 summary", str(e))


# =============================================================================
# [16] HealthChecker 컨텍스트 매니저 / shutdown (4개)
# =============================================================================
def test_context_manager(result: TestResult) -> None:
    """HealthChecker 컨텍스트 매니저/shutdown 검증."""
    print("\n[16] 컨텍스트 매니저 / shutdown")

    # 16-1. __enter__ -> self
    try:
        hc = _make_checker()
        with hc as ctx:
            assert ctx is hc
        result.ok("16-1 __enter__ -> self")
    except Exception as e:
        result.fail("16-1 __enter__", str(e))

    # 16-2. __exit__ -> shutdown 호출 (executor None)
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        with hc:
            hc.check("a")  # executor 생성됨
            assert hc._executor is not None
        # __exit__ 후 executor 정리
        assert hc._executor is None
        result.ok("16-2 __exit__ -> shutdown (executor 정리)")
    except Exception as e:
        result.fail("16-2 __exit__", str(e))

    # 16-3. shutdown 중복 호출 안전
    try:
        hc = _make_checker()
        hc.shutdown()
        hc.shutdown()  # 두 번째 호출도 안전
        result.ok("16-3 shutdown 중복 호출 안전")
    except Exception as e:
        result.fail("16-3 shutdown 중복", str(e))

    # 16-4. shutdown 후 executor None
    try:
        hc = _make_checker()
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        hc.check("a")
        hc.shutdown()
        assert hc._executor is None
        result.ok("16-4 shutdown 후 executor None")
    except Exception as e:
        result.fail("16-4 executor None", str(e))


# =============================================================================
# [17] 싱글톤 (4개)
# =============================================================================
def test_singleton(result: TestResult) -> None:
    """싱글톤 검증."""
    print("\n[17] 싱글톤")

    # 17-1. _get_health_checker -> HealthChecker
    try:
        _reset_singleton()
        hc = _get_health_checker()
        assert isinstance(hc, HealthChecker)
        result.ok("17-1 _get_health_checker -> HealthChecker")
    except Exception as e:
        result.fail("17-1 _get_health_checker", str(e))
    finally:
        _reset_singleton()

    # 17-2. 동일 인스턴스 반환
    try:
        _reset_singleton()
        hc1 = _get_health_checker()
        hc2 = _get_health_checker()
        assert hc1 is hc2
        result.ok("17-2 동일 인스턴스 반환")
    except Exception as e:
        result.fail("17-2 동일 인스턴스", str(e))
    finally:
        _reset_singleton()

    # 17-3. reset 후 새 인스턴스
    try:
        _reset_singleton()
        hc1 = _get_health_checker()
        _reset_singleton()
        hc2 = _get_health_checker()
        assert hc1 is not hc2
        result.ok("17-3 reset 후 새 인스턴스")
    except Exception as e:
        result.fail("17-3 reset", str(e))
    finally:
        _reset_singleton()

    # 17-4. 멀티스레드 싱글톤
    try:
        _reset_singleton()
        instances = []
        errors = []

        def get_instance():
            try:
                inst = _get_health_checker()
                instances.append(id(inst))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors}"
        assert len(set(instances)) == 1, f"서로 다른 인스턴스: {len(set(instances))}개"
        result.ok("17-4 멀티스레드 싱글톤 (10스레드)")
    except AssertionError as e:
        result.fail("17-4 멀티스레드 싱글톤", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [18] 엣지 케이스 / __all__ (5개)
# =============================================================================
def test_edge_cases_and_all(result: TestResult) -> None:
    """엣지 케이스 및 __all__ 검증."""
    print("\n[18] 엣지 케이스 / __all__")

    # 18-1. __all__ == 31개
    try:
        from core_foundation.monitoring.health_checker import __all__ as hc_all
        assert len(hc_all) == 31, f"실제: {len(hc_all)}"
        result.ok("18-1 __all__ == 31개")
    except AssertionError as e:
        result.fail("18-1 __all__ 개수", str(e))

    # 18-2. __all__ 필수 항목 포함
    try:
        from core_foundation.monitoring.health_checker import __all__ as hc_all
        required = [
            "HealthStatus", "DependencyType",
            "HealthCheckResult", "DependencyHealth", "SystemHealth", "HealthCheckConfig",
            "HealthChecker",
            "create_health_check", "aggregate_health_status",
            "check_cpu_health", "check_memory_health", "check_disk_health",
            "check_tcp_port", "check_gpu_health", "check_camera_health",
            "_get_health_checker", "_reset_health_checker",
        ]
        for item in required:
            assert item in hc_all, f"__all__에 '{item}' 누락"
        result.ok("18-2 __all__ 필수 항목 포함")
    except AssertionError as e:
        result.fail("18-2 __all__ 필수", str(e))

    # 18-3. HealthStatus __lt__ with non-HealthStatus -> NotImplemented
    try:
        hs = HealthStatus.HEALTHY
        # 비교 시 NotImplemented 반환 (TypeError 가능)
        res = hs.__lt__("not_enum")
        assert res is NotImplemented
        result.ok("18-3 __lt__ non-HealthStatus -> NotImplemented")
    except Exception as e:
        result.fail("18-3 __lt__ non-enum", str(e))

    # 18-4. max_history deque 한계 (FIFO 삭제)
    try:
        hc = _make_checker(max_history=3)
        hc.register_check("a", _healthy_check_func, DependencyType.CUSTOM)
        for _ in range(5):
            hc.check_all(parallel=False)
        history = hc.get_history()
        assert len(history) <= 3, f"히스토리: {len(history)}"
        result.ok("18-4 max_history=3 FIFO 제한")
    except Exception as e:
        result.fail("18-4 max_history", str(e))

    # 18-5. DependencyHealth update DEGRADED -> successful_checks 증가
    try:
        dh = DependencyHealth(name="test", dependency_type=DependencyType.CUSTOM)
        degraded_result = HealthCheckResult.degraded(
            name="test",
            dependency_type=DependencyType.CUSTOM,
            message="warning",
            response_time_ms=5.0,
        )
        dh.update(degraded_result)
        assert dh.current_status == HealthStatus.DEGRADED
        assert dh.successful_checks == 1  # DEGRADED도 성공으로 카운트
        assert dh.consecutive_failures == 0
        result.ok("18-5 DEGRADED -> successful_checks 증가")
    except AssertionError as e:
        result.fail("18-5 DEGRADED 성공", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - health_checker.py 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # [1] 상수
    test_constants(result)
    # [2] HealthStatus Enum
    test_health_status(result)
    # [3] DependencyType Enum
    test_dependency_type(result)
    # [4] HealthCheckResult
    test_health_check_result(result)
    # [5] DependencyHealth
    test_dependency_health(result)
    # [6] SystemHealth
    test_system_health(result)
    # [7] HealthCheckConfig
    test_health_check_config(result)
    # [8] aggregate_health_status
    test_aggregate_health_status(result)
    # [9] create_health_check
    test_create_health_check(result)
    # [10] 빌트인 체크 함수
    test_builtin_checks(result)
    # [11] HealthChecker 초기화
    test_health_checker_init(result)
    # [12] register/unregister
    test_register_unregister(result)
    # [13] check 단일
    test_check_single(result)
    # [14] check_all
    test_check_all(result)
    # [15] 유틸리티 메서드
    test_utility_methods(result)
    # [16] 컨텍스트 매니저
    test_context_manager(result)
    # [17] 싱글톤
    test_singleton(result)
    # [18] 엣지 케이스 / __all__
    test_edge_cases_and_all(result)

    result.summary()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
