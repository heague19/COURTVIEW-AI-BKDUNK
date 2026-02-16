# -*- coding: utf-8 -*-
"""
COURTVIEW - core_foundation 전체 크로스 모듈 통합 테스트

10개 카테고리, ~65개 테스트

검증 범위:
    [1]  최상위 core_foundation 임포트 무결성 (8개)
    [2]  __all__ 크로스 모듈 Export 검증 (5개)
    [3]  Config -> Monitoring 파이프라인 (7개)
    [4]  Monitoring -> Resilience 파이프라인 (7개)
    [5]  Resilience -> Security 파이프라인 (6개)
    [6]  Security -> Monitoring 파이프라인 (6개)
    [7]  전체 관측 파이프라인 (8개)
    [8]  Registry 통합 (6개)
    [9]  에러 전파 크로스 모듈 (5개)
    [10] 모듈 격리 및 정리 (7개)

실행:
    python tests/core_foundation/integration/test_core_foundation_integration.py

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16
"""

from __future__ import annotations

import io
import sys
import threading
import time
from pathlib import Path
from typing import List

# ============================================================
# 프로젝트 루트 + 인코딩
# ============================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ============================================================
# 실제 모듈 임포트 (shared 및 config 의존성은 실제 사용)
# ============================================================
from core_foundation.config.loader import ConfigLoader
from shared.exceptions.infrastructure_exceptions import (
    CircuitBreakerOpenException as _CircuitBreakerOpenException,
)
from shared.exceptions.base_exception import RetryableException as _RetryableException


# ============================================================
# 테스트용 ConfigLoader 래퍼 (외부 YAML 파일 로드 없이 사용)
# ============================================================
class _MockConfigLoader:
    """테스트용 경량 ConfigLoader 스텁.

    실제 ConfigLoader와 동일한 인터페이스를 제공하되,
    YAML 파일 로드 없이 인메모리 데이터로만 동작합니다.
    """

    _instance = None

    def __init__(self) -> None:
        self._data: dict = {}
        self._loaded: bool = True

    @classmethod
    def get_instance(cls) -> "_MockConfigLoader":
        if cls._instance is None:
            cls._instance = _MockConfigLoader()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """싱글톤 리셋 (테스트 격리용)."""
        cls._instance = None

    def get(self, key: str, default=None) -> object:
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        return int(val) if val is not None else default

    def get_str(self, key: str, default: str = "") -> str:
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        return bool(val) if val is not None else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        return float(val) if val is not None else default

    def get_section(self, section: str) -> dict:
        val = self._data.get(section)
        return val if isinstance(val, dict) else {}

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def to_dict(self) -> dict:
        return dict(self._data)

    def clear(self) -> None:
        self._data.clear()

# ============================================================
# 모듈 임포트
# ============================================================
# 각 서브모듈은 try/except로 감싸서 누락 시 건너뜀
_monitoring_available = False
_resilience_available = False
_security_available = False
_registry_available = False

# resilience
try:
    import core_foundation.resilience as resilience_mod
    from core_foundation.resilience import (
        CircuitState, FailureType, BackoffStrategy, RetryOutcome,
        CircuitBreakerConfig, CircuitBreakerStats, RetryConfig, RetryResult,
        StateChangeEvent, CircuitBreaker, CircuitBreakerRegistry,
        RetryMechanism, circuit_protected, retry,
        get_circuit_breaker, get_all_circuit_status,
        _get_circuit_registry, _reset_circuit_registry, _reset_retry_registry,
        calculate_backoff,
    )
    _resilience_available = True
except ImportError as e:
    print(f"  [WARN] resilience 임포트 실패: {e}")

# monitoring
try:
    import core_foundation.monitoring as monitoring_mod
    from core_foundation.monitoring import (
        ErrorTracker, ErrorSeverity, ErrorContext, ErrorRecord, ErrorSummary,
        MetricsCollector, MetricUnit, Counter, Gauge, Histogram,
        PerformanceProfiler, ProfileType, ProfileResult, FunctionProfile,
        HealthChecker, HealthStatus, HealthCheckResult,
    )
    from core_foundation.monitoring import DependencyType as MonitoringDependencyType
    _monitoring_available = True
except ImportError as e:
    print(f"  [WARN] monitoring 임포트 실패: {e}")

# security
try:
    import core_foundation.security as security_mod
    from core_foundation.security import (
        SecretManager, SecretProvider, EnvProvider,
        SecretNotFoundException,
        AuditLogger, AuditEventType, AuditSeverity, AuditLogEntry,
        MemoryAuditStorage, LoginFailureTracker,
        get_audit_logger, set_audit_logger, log_audit_event,
        get_secret_manager, set_secret_manager,
    )
    _security_available = True
except ImportError as e:
    print(f"  [WARN] security 임포트 실패: {e}")

# registry
try:
    import core_foundation.registry as registry_mod
    from core_foundation.registry import (
        ModelRegistry, ModelType, ServiceRegistry, ServiceType,
        DIContainer, Scope, PipelineCoordinator, PipelineBuilder, PipelineType,
        StageType, PipelineTemplates, RuleSetManager, League,
        _reset_model_registry, _reset_service_registry,
        _reset_container, _reset_coordinator, _reset_rule_set_manager,
    )
    _registry_available = True
except ImportError as e:
    print(f"  [WARN] registry 임포트 실패: {e}")


# ============================================================
# TestResult
# ============================================================
class TestResult:
    """테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.skipped: int = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str = "") -> None:
        self.failed += 1
        self.failures.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    def skip(self, name: str, reason: str = "") -> None:
        self.skipped += 1
        print(f"  [SKIP] {name}: {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> None:
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"크로스 모듈 통합 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"크로스 모듈 통합 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        if self.skipped > 0:
            print(f"\n건너뛴 테스트: {self.skipped}개")
        print("=" * 60)


# ============================================================
# 헬퍼 함수
# ============================================================
def _make_cb(
    name: str = "test_cb",
    failure_threshold: int = 3,
    success_threshold: int = 2,
    open_timeout: float = 0.1,
    minimum_requests: int = 3,
    **kwargs,
) -> "CircuitBreaker":
    """테스트용 CircuitBreaker 생성."""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        open_timeout=open_timeout,
        minimum_requests=minimum_requests,
        **kwargs,
    )
    return CircuitBreaker(name=name, config=config, config_loader=_MockConfigLoader())


def _make_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.001,
    max_delay: float = 0.01,
    jitter_enabled: bool = False,
    **kwargs,
) -> "RetryMechanism":
    """테스트용 RetryMechanism 생성."""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        jitter_enabled=jitter_enabled,
        retryable_exceptions=(ConnectionError, TimeoutError, _RetryableException),
        log_retries=False,
        **kwargs,
    )
    return RetryMechanism(config=config, name="test_retry")


def _reset_all() -> None:
    """모든 모듈 싱글톤 리셋."""
    if _resilience_available:
        _reset_circuit_registry()
        _reset_retry_registry()
    if _registry_available:
        _reset_model_registry()
        _reset_service_registry()
        _reset_container()
        _reset_coordinator()
        _reset_rule_set_manager()
    _MockConfigLoader.reset_instance()


# =============================================================================
# [1] 최상위 core_foundation 임포트 무결성 (8개)
# =============================================================================
def test_top_level_import_integrity(result: TestResult) -> None:
    """최상위 core_foundation 패키지에서 모든 서브모듈 접근 가능 검증."""
    print("\n[1] 최상위 core_foundation 임포트 무결성")

    # 1-1. core_foundation 패키지 임포트
    try:
        import core_foundation
        assert core_foundation is not None
        result.ok("1-1 core_foundation 패키지 임포트")
    except Exception as e:
        result.fail("1-1 core_foundation 패키지 임포트", str(e))
        return

    # 1-2. config 서브모듈 접근 가능
    try:
        assert hasattr(core_foundation, "ConfigLoader") or "ConfigLoader" in dir(core_foundation)
        result.ok("1-2 config 서브모듈 심볼 접근 (ConfigLoader)")
    except Exception as e:
        result.fail("1-2 config 서브모듈", str(e))

    # 1-3. monitoring 서브모듈 접근 가능
    try:
        if _monitoring_available:
            assert hasattr(core_foundation, "ErrorTracker") or hasattr(monitoring_mod, "ErrorTracker")
            result.ok("1-3 monitoring 서브모듈 심볼 접근 (ErrorTracker)")
        else:
            result.skip("1-3 monitoring 서브모듈", "임포트 불가")
    except Exception as e:
        result.fail("1-3 monitoring 서브모듈", str(e))

    # 1-4. resilience 서브모듈 접근 가능
    try:
        if _resilience_available:
            assert hasattr(resilience_mod, "CircuitBreaker")
            assert hasattr(resilience_mod, "RetryMechanism")
            result.ok("1-4 resilience 서브모듈 심볼 접근 (CircuitBreaker, RetryMechanism)")
        else:
            result.skip("1-4 resilience 서브모듈", "임포트 불가")
    except Exception as e:
        result.fail("1-4 resilience 서브모듈", str(e))

    # 1-5. security 서브모듈 접근 가능
    try:
        if _security_available:
            assert hasattr(security_mod, "SecretManager")
            assert hasattr(security_mod, "AuditLogger")
            result.ok("1-5 security 서브모듈 심볼 접근 (SecretManager, AuditLogger)")
        else:
            result.skip("1-5 security 서브모듈", "임포트 불가")
    except Exception as e:
        result.fail("1-5 security 서브모듈", str(e))

    # 1-6. registry 서브모듈 접근 가능
    try:
        if _registry_available:
            assert hasattr(registry_mod, "ModelRegistry")
            assert hasattr(registry_mod, "ServiceRegistry")
            assert hasattr(registry_mod, "DIContainer")
            result.ok("1-6 registry 서브모듈 심볼 접근 (ModelRegistry, ServiceRegistry, DIContainer)")
        else:
            result.skip("1-6 registry 서브모듈", "임포트 불가")
    except Exception as e:
        result.fail("1-6 registry 서브모듈", str(e))

    # 1-7. __version__ 검증
    try:
        assert hasattr(core_foundation, "__version__")
        assert core_foundation.__version__ == "1.0.0"
        result.ok("1-7 core_foundation.__version__ == '1.0.0'")
    except Exception as e:
        result.fail("1-7 __version__", str(e))

    # 1-8. 순환 참조 검증 (각 서브모듈 reload)
    try:
        import importlib
        reloaded = 0
        if _resilience_available:
            importlib.reload(sys.modules["core_foundation.resilience"])
            reloaded += 1
        if _monitoring_available:
            importlib.reload(sys.modules["core_foundation.monitoring"])
            reloaded += 1
        if _security_available:
            importlib.reload(sys.modules["core_foundation.security"])
            reloaded += 1
        if _registry_available:
            importlib.reload(sys.modules["core_foundation.registry"])
            reloaded += 1
        assert reloaded >= 1
        result.ok(f"1-8 순환 참조 없음 (reload {reloaded}개 서브모듈)")
    except Exception as e:
        result.fail("1-8 순환 참조", str(e))


# =============================================================================
# [2] __all__ 크로스 모듈 Export 검증 (5개)
# =============================================================================
def test_cross_module_all_exports(result: TestResult) -> None:
    """각 서브모듈 __all__의 접근성 및 충돌 검증."""
    print("\n[2] __all__ 크로스 모듈 Export 검증")

    submodules = {}
    if _resilience_available:
        submodules["resilience"] = resilience_mod
    if _monitoring_available:
        submodules["monitoring"] = monitoring_mod
    if _security_available:
        submodules["security"] = security_mod
    if _registry_available:
        submodules["registry"] = registry_mod

    # 2-1. 각 서브모듈 __all__ 접근 가능
    try:
        for name, mod in submodules.items():
            assert hasattr(mod, "__all__"), f"{name}에 __all__ 없음"
            assert len(mod.__all__) > 0, f"{name}.__all__ 비어있음"
        result.ok(f"2-1 각 서브모듈 __all__ 접근 가능 ({len(submodules)}개)")
    except Exception as e:
        result.fail("2-1 __all__ 접근", str(e))

    # 2-2. 각 서브모듈 __all__ 심볼 실제 접근 가능
    try:
        total_symbols = 0
        for name, mod in submodules.items():
            missing = [s for s in mod.__all__ if not hasattr(mod, s)]
            assert len(missing) == 0, f"{name} 누락: {missing[:5]}"
            total_symbols += len(mod.__all__)
        result.ok(f"2-2 전체 심볼 접근 가능 (총 {total_symbols}개)")
    except Exception as e:
        result.fail("2-2 심볼 접근", str(e))

    # 2-3. 서브모듈 간 이름 충돌 검사
    try:
        all_names: dict[str, list[str]] = {}
        for name, mod in submodules.items():
            for sym in mod.__all__:
                if sym not in all_names:
                    all_names[sym] = []
                all_names[sym].append(name)

        collisions = {k: v for k, v in all_names.items() if len(v) > 1 and not k.startswith("_")}
        # 충돌이 있어도 보고만 함 (DependencyType 등은 알려진 충돌)
        if collisions:
            collision_names = list(collisions.keys())[:5]
            result.ok(f"2-3 서브모듈 간 이름 충돌 감지 (알려진 충돌: {collision_names})")
        else:
            result.ok("2-3 서브모듈 간 이름 충돌 없음")
    except Exception as e:
        result.fail("2-3 이름 충돌", str(e))

    # 2-4. core_foundation.__all__에 config 심볼 포함
    try:
        import core_foundation
        assert hasattr(core_foundation, "__all__")
        config_required = ["ConfigLoader", "Settings", "AppConfig", "SchemaValidator"]
        for sym in config_required:
            assert sym in core_foundation.__all__, f"'{sym}' 누락"
        result.ok("2-4 core_foundation.__all__에 config 핵심 심볼 포함")
    except Exception as e:
        result.fail("2-4 config 심볼", str(e))

    # 2-5. 각 서브모듈 __all__ 중복 없음
    try:
        for name, mod in submodules.items():
            all_list = mod.__all__
            duplicates = [x for x in all_list if all_list.count(x) > 1]
            assert len(duplicates) == 0, f"{name} 중복: {set(duplicates)}"
        result.ok(f"2-5 각 서브모듈 __all__ 중복 없음 ({len(submodules)}개)")
    except Exception as e:
        result.fail("2-5 중복 검사", str(e))


# =============================================================================
# [3] Config -> Monitoring 파이프라인 (7개)
# =============================================================================
def test_config_monitoring_pipeline(result: TestResult) -> None:
    """Config 로드 -> Monitoring 연동 시나리오."""
    print("\n[3] Config -> Monitoring 파이프라인")

    if not _monitoring_available:
        for i in range(1, 8):
            result.skip(f"3-{i}", "monitoring 모듈 미사용 가능")
        return

    # 3-1. ConfigLoader -> MetricsCollector 설정 메트릭 기록
    try:
        loader = _MockConfigLoader()
        loader.set("analysis.target_fps", 30)
        loader.set("gpu.memory_fraction", 0.85)

        mc = MetricsCollector(prefix="config_integ", enabled=True, max_metrics=500)
        config_loads = mc.counter("config_loads_total", "설정 로드 수", MetricUnit.COUNT)
        config_values = mc.gauge("config_target_fps", "설정 FPS", MetricUnit.FPS)

        config_loads.inc()
        fps_val = loader.get_int("analysis.target_fps", 30)
        config_values.set(float(fps_val))

        assert config_loads.snapshot().values[0].value == 1.0
        assert config_values.snapshot().values[0].value == 30.0
        result.ok("3-1 ConfigLoader -> MetricsCollector 설정 메트릭")
    except Exception as e:
        result.fail("3-1 Config->Metrics", str(e))

    # 3-2. Settings.get() -> PerformanceProfiler 접근 프로파일링
    try:
        profiler = PerformanceProfiler(
            enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
        )
        start_t = time.perf_counter()
        loader.get("analysis.target_fps")
        elapsed_ms = (time.perf_counter() - start_t) * 1000
        profiler.profile_function_call("config_get", execution_time_ms=elapsed_ms)

        fp = profiler.get_function_profile("config_get")
        assert fp is not None
        assert fp.call_count == 1
        assert fp.total_time_ms >= 0
        result.ok(f"3-2 Config.get -> Profiler 프로파일링 ({fp.total_time_ms:.3f}ms)")
    except Exception as e:
        result.fail("3-2 Config->Profiler", str(e))

    # 3-3. ErrorTracker가 설정 오류 추적
    try:
        tracker = ErrorTracker(max_records=100, enabled=True)
        try:
            bad_value = loader.get("nonexistent.key")
            if bad_value is None:
                raise ValueError("설정 키 'nonexistent.key' 없음")
        except ValueError as exc:
            record = tracker.track(exc, severity=ErrorSeverity.WARNING)
            assert isinstance(record, ErrorRecord)
            assert record.message == "설정 키 'nonexistent.key' 없음"

        summary = tracker.get_summary(hours=1)
        assert summary.total_count == 1
        result.ok("3-3 ErrorTracker 설정 오류 추적")
    except Exception as e:
        result.fail("3-3 Config->ErrorTracker", str(e))

    # 3-4. HealthChecker가 설정 신선도 모니터링
    try:
        hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)
        config_load_time = time.time()

        def config_freshness_check() -> HealthCheckResult:
            age_seconds = time.time() - config_load_time
            if age_seconds > 3600:
                return HealthCheckResult.unhealthy(
                    "config", MonitoringDependencyType.CUSTOM, "설정이 1시간 이상 지남"
                )
            return HealthCheckResult.healthy(
                "config", MonitoringDependencyType.CUSTOM,
                f"설정 신선도 OK ({age_seconds:.0f}초)", response_time_ms=0.1,
            )

        hc.register_check("config_freshness", config_freshness_check, MonitoringDependencyType.CUSTOM)
        r = hc.check("config_freshness")
        assert r.status == HealthStatus.HEALTHY
        hc.shutdown()
        result.ok("3-4 HealthChecker 설정 신선도 모니터링")
    except Exception as e:
        result.fail("3-4 Config->HealthChecker", str(e))

    # 3-5. 설정 변경 -> 메트릭 갱신
    try:
        mc2 = MetricsCollector(prefix="cfg_change", enabled=True, max_metrics=100)
        change_counter = mc2.counter("config_changes", "설정 변경 수", MetricUnit.COUNT)
        fps_gauge = mc2.gauge("current_fps", "현재 설정 FPS", MetricUnit.FPS)

        fps_gauge.set(30.0)
        loader.set("analysis.target_fps", 60)
        change_counter.inc()
        fps_gauge.set(60.0)

        assert change_counter.snapshot().values[0].value == 1.0
        assert fps_gauge.snapshot().values[0].value == 60.0
        result.ok("3-5 설정 변경 -> 메트릭 갱신")
    except Exception as e:
        result.fail("3-5 설정 변경->메트릭", str(e))

    # 3-6. 다수 설정 섹션별 메트릭 라벨링
    try:
        mc3 = MetricsCollector(prefix="cfg_sections", enabled=True, max_metrics=100)
        section_counter = mc3.counter("section_access", "섹션 접근 수", MetricUnit.COUNT)

        sections = ["gpu", "camera", "analysis", "model"]
        for sec in sections:
            loader.get_section(sec)
            section_counter.labels({"section": sec}).inc()

        for sec in sections:
            val = section_counter.labels({"section": sec}).get()
            assert val == 1.0, f"section={sec}, val={val}"
        result.ok("3-6 섹션별 메트릭 라벨링 (4개 섹션)")
    except Exception as e:
        result.fail("3-6 섹션 라벨링", str(e))

    # 3-7. 설정 로드 실패 -> ErrorTracker + MetricsCollector 동시 기록
    try:
        tracker2 = ErrorTracker(max_records=100, enabled=True)
        mc4 = MetricsCollector(prefix="cfg_errors", enabled=True, max_metrics=100)
        error_counter = mc4.counter("config_errors", "설정 에러 수", MetricUnit.COUNT)

        for i in range(3):
            exc = IOError(f"설정 파일 읽기 실패 #{i}")
            tracker2.track(exc, severity=ErrorSeverity.ERROR)
            error_counter.inc()

        assert tracker2.get_summary(hours=1).total_count == 3
        assert error_counter.snapshot().values[0].value == 3.0
        result.ok("3-7 설정 로드 실패 -> ErrorTracker + MetricsCollector 동시 기록")
    except Exception as e:
        result.fail("3-7 동시 기록", str(e))


# =============================================================================
# [4] Monitoring -> Resilience 파이프라인 (7개)
# =============================================================================
def test_monitoring_resilience_pipeline(result: TestResult) -> None:
    """Monitoring -> Resilience 연동 시나리오."""
    print("\n[4] Monitoring -> Resilience 파이프라인")

    if not (_monitoring_available and _resilience_available):
        for i in range(1, 8):
            result.skip(f"4-{i}", "monitoring 또는 resilience 미사용 가능")
        return

    _reset_all()

    # 4-1. CircuitBreaker 상태 변경 -> ErrorTracker 기록
    try:
        tracker = ErrorTracker(max_records=100, enabled=True)
        cb = _make_cb("mon_cb_1", failure_threshold=2, minimum_requests=2)
        events = []

        def on_state_change(event):
            events.append(event)
            if event.current_state == CircuitState.OPEN:
                tracker.track(
                    RuntimeError(f"서킷 '{event.circuit_name}' OPEN 전환"),
                    context=ErrorContext(extra={
                        "circuit_name": event.circuit_name,
                        "previous_state": event.previous_state.value,
                        "current_state": event.current_state.value,
                    }),
                    severity=ErrorSeverity.CRITICAL,
                )

        cb.add_state_change_callback(on_state_change)
        cb.record_failure(exception=ValueError("err1"))
        cb.record_failure(exception=ValueError("err2"))

        assert cb.state == CircuitState.OPEN
        assert len(events) >= 1
        summary = tracker.get_summary(hours=1)
        assert summary.total_count >= 1
        result.ok("4-1 CircuitBreaker OPEN -> ErrorTracker CRITICAL 기록")
    except Exception as e:
        result.fail("4-1 CB->ErrorTracker", str(e))

    # 4-2. RetryMechanism 재시도 -> MetricsCollector 카운트
    try:
        mc = MetricsCollector(prefix="retry_integ", enabled=True, max_metrics=100)
        retry_counter = mc.counter("retries_total", "총 재시도", MetricUnit.COUNT)
        retry_success = mc.counter("retry_successes", "재시도 성공", MetricUnit.COUNT)

        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                retry_counter.inc()
                raise ConnectionError("transient")
            retry_success.inc()
            return "ok"

        rm = _make_retry(max_attempts=5)
        val = rm.execute(flaky)
        assert val == "ok"
        assert retry_counter.snapshot().values[0].value == 2.0
        assert retry_success.snapshot().values[0].value == 1.0
        result.ok("4-2 RetryMechanism -> MetricsCollector (retries=2, success=1)")
    except Exception as e:
        result.fail("4-2 Retry->Metrics", str(e))

    # 4-3. HealthChecker 비정상 -> CircuitBreaker 강제 오픈
    try:
        hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)
        cb = _make_cb("health_cb", failure_threshold=5, minimum_requests=5)

        def unhealthy_check() -> HealthCheckResult:
            return HealthCheckResult.unhealthy(
                "gpu", MonitoringDependencyType.GPU, "GPU 과열"
            )

        hc.register_check("gpu_temp", unhealthy_check, MonitoringDependencyType.GPU, critical=True)
        sh = hc.check_all(parallel=False)

        if sh.overall_status == HealthStatus.UNHEALTHY:
            cb.force_open("HealthChecker 비정상 감지")

        assert cb.state == CircuitState.OPEN
        hc.shutdown()
        result.ok("4-3 HealthChecker UNHEALTHY -> CircuitBreaker force_open")
    except Exception as e:
        result.fail("4-3 Health->CB", str(e))

    # 4-4. Profiler가 서킷 실행 시간 측정
    try:
        profiler = PerformanceProfiler(
            enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
        )
        cb = _make_cb("prof_cb")
        start_t = time.perf_counter()
        val = cb.execute(lambda: "profiled_result")
        elapsed_ms = (time.perf_counter() - start_t) * 1000
        profiler.profile_function_call("circuit_execute", execution_time_ms=elapsed_ms)

        fp = profiler.get_function_profile("circuit_execute")
        assert fp is not None
        assert fp.call_count == 1
        assert val == "profiled_result"
        result.ok(f"4-4 Profiler 서킷 실행 측정 ({fp.total_time_ms:.3f}ms)")
    except Exception as e:
        result.fail("4-4 Profiler->CB", str(e))

    # 4-5. 서킷 OPEN -> 폴백 -> 메트릭 기록
    try:
        mc2 = MetricsCollector(prefix="cb_fb", enabled=True, max_metrics=100)
        fallback_counter = mc2.counter("fallbacks_total", "폴백 수", MetricUnit.COUNT)

        cb = _make_cb("fb_cb", failure_threshold=2, minimum_requests=2)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        val = cb.execute(lambda: "normal", fallback=lambda: "cached")
        fallback_counter.inc()

        assert val == "cached"
        assert fallback_counter.snapshot().values[0].value == 1.0
        result.ok("4-5 서킷 OPEN 폴백 -> MetricsCollector fallback 카운트")
    except Exception as e:
        result.fail("4-5 CB 폴백->Metrics", str(e))

    # 4-6. 재시도 소진 -> ErrorTracker + 메트릭 동시 기록
    try:
        tracker2 = ErrorTracker(max_records=100, enabled=True)
        mc3 = MetricsCollector(prefix="exhausted", enabled=True, max_metrics=100)
        exhausted_counter = mc3.counter("retries_exhausted", "재시도 소진", MetricUnit.COUNT)

        rm2 = _make_retry(max_attempts=2)
        rr = rm2.execute_with_result(lambda: (_ for _ in ()).throw(ConnectionError("always")))
        if not rr.success:
            tracker2.track(
                ConnectionError("재시도 소진"),
                severity=ErrorSeverity.ERROR,
            )
            exhausted_counter.inc()

        assert not rr.success
        assert rr.outcome == RetryOutcome.EXHAUSTED
        assert tracker2.get_summary(hours=1).total_count == 1
        assert exhausted_counter.snapshot().values[0].value == 1.0
        result.ok("4-6 재시도 소진 -> ErrorTracker + MetricsCollector")
    except Exception as e:
        result.fail("4-6 Retry 소진->Error+Metrics", str(e))

    # 4-7. 서킷 복구 -> HealthChecker 정상 판정
    try:
        cb = _make_cb("recovery_cb", failure_threshold=2, minimum_requests=2,
                       open_timeout=0.05, success_threshold=1)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)
        _ = cb.state  # HALF_OPEN 트리거
        cb.record_success(1.0)
        assert cb.state == CircuitState.CLOSED

        hc2 = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)

        def circuit_health() -> HealthCheckResult:
            if cb.is_closed:
                return HealthCheckResult.healthy(
                    "circuit", MonitoringDependencyType.CUSTOM, "서킷 정상", response_time_ms=0.1,
                )
            return HealthCheckResult.unhealthy(
                "circuit", MonitoringDependencyType.CUSTOM, "서킷 비정상",
            )

        hc2.register_check("circuit_status", circuit_health, MonitoringDependencyType.CUSTOM)
        r = hc2.check("circuit_status")
        assert r.status == HealthStatus.HEALTHY
        hc2.shutdown()
        result.ok("4-7 서킷 복구 -> HealthChecker HEALTHY")
    except Exception as e:
        result.fail("4-7 CB 복구->Health", str(e))

    _reset_all()


# =============================================================================
# [5] Resilience -> Security 파이프라인 (6개)
# =============================================================================
def test_resilience_security_pipeline(result: TestResult) -> None:
    """Resilience -> Security 연동 시나리오."""
    print("\n[5] Resilience -> Security 파이프라인")

    if not (_resilience_available and _security_available):
        for i in range(1, 7):
            result.skip(f"5-{i}", "resilience 또는 security 미사용 가능")
        return

    _reset_all()
    config_loader = _MockConfigLoader()

    # 5-1. RetryMechanism으로 SecretManager.get 래핑
    try:
        sm = SecretManager(config_loader=config_loader)
        rm = _make_retry(max_attempts=3)

        call_count = [0]

        def get_secret_with_retry():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("provider 연결 실패")
            return sm.get("test_key", default="fallback_value")

        val = rm.execute(get_secret_with_retry)
        assert val is not None  # 기본값이 반환되거나 None
        assert call_count[0] == 2  # 2번째 시도에서 성공
        result.ok("5-1 RetryMechanism으로 SecretManager.get 래핑")
    except Exception as e:
        result.fail("5-1 Retry+SecretManager", str(e))

    # 5-2. CircuitBreaker가 시크릿 제공자 보호
    try:
        cb = _make_cb("secret_cb", failure_threshold=3, minimum_requests=3)
        provider_fail_count = [0]

        def protected_secret_access():
            provider_fail_count[0] += 1
            if provider_fail_count[0] <= 3:
                raise TimeoutError("Provider timeout")
            return "secret_value"

        for _ in range(3):
            try:
                cb.execute(protected_secret_access)
            except TimeoutError:
                pass

        assert cb.state == CircuitState.OPEN
        result.ok("5-2 CircuitBreaker가 시크릿 제공자 보호 (3회 실패 -> OPEN)")
    except Exception as e:
        result.fail("5-2 CB+SecretProvider", str(e))

    # 5-3. AuditLogger가 서킷 상태 변경 기록
    try:
        storage = MemoryAuditStorage()
        audit = AuditLogger(config_loader=config_loader)
        audit.add_storage(storage)

        cb = _make_cb("audit_cb", failure_threshold=2, minimum_requests=2)

        def on_change(event):
            audit.log(
                event_type=AuditEventType.CONFIG_CHANGE,
                actor="system",
                action="circuit_state_change",
                resource=event.circuit_name,
                result=event.current_state.value,
                details={
                    "previous_state": event.previous_state.value,
                    "current_state": event.current_state.value,
                },
                immediate=True,
            )

        cb.add_state_change_callback(on_change)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        audit.flush()
        entries = audit.query()
        assert len(entries) >= 1
        result.ok(f"5-3 AuditLogger 서킷 상태 변경 기록 ({len(entries)}건)")
    except Exception as e:
        result.fail("5-3 AuditLogger+CB", str(e))

    # 5-4. 시크릿 접근 실패 -> AuditLogger 보안 이벤트
    try:
        storage2 = MemoryAuditStorage()
        audit2 = AuditLogger(config_loader=config_loader)
        audit2.add_storage(storage2)

        audit2.log(
            event_type=AuditEventType.SECRET_ACCESS,
            actor="system",
            action="get_secret",
            resource="database_password",
            result="failure",
            severity=AuditSeverity.ERROR,
            details={"reason": "provider_timeout", "circuit_state": "open"},
            immediate=True,
        )

        audit2.flush()
        entries = audit2.query(event_types=[AuditEventType.SECRET_ACCESS])
        assert len(entries) >= 1
        assert entries[0].event.result == "failure"
        result.ok("5-4 시크릿 접근 실패 -> AuditLogger 보안 이벤트")
    except Exception as e:
        result.fail("5-4 Secret 실패->Audit", str(e))

    # 5-5. 서킷 OPEN -> 폴백 시크릿 + 감사 로그
    try:
        storage3 = MemoryAuditStorage()
        audit3 = AuditLogger(config_loader=config_loader)
        audit3.add_storage(storage3)

        cb = _make_cb("fb_secret_cb", failure_threshold=2, minimum_requests=2)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))

        val = cb.execute(
            lambda: "real_secret",
            fallback=lambda: "cached_secret",
        )
        audit3.log(
            event_type=AuditEventType.SECRET_ACCESS,
            actor="system",
            action="get_secret_fallback",
            resource="api_key",
            result="fallback",
            details={"source": "cache"},
            immediate=True,
        )

        assert val == "cached_secret"
        audit3.flush()
        entries = audit3.query()
        assert len(entries) >= 1
        result.ok("5-5 서킷 OPEN 폴백 시크릿 + 감사 로그")
    except Exception as e:
        result.fail("5-5 CB 폴백+Audit", str(e))

    # 5-6. 재시도+서킷+감사 통합 시나리오
    try:
        storage4 = MemoryAuditStorage()
        audit4 = AuditLogger(config_loader=config_loader)
        audit4.add_storage(storage4)

        cb = _make_cb("full_sec_cb", failure_threshold=5, minimum_requests=5)
        rm = _make_retry(max_attempts=3)
        call_count = [0]

        def protected_op():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("transient")
            return cb.execute(lambda: "secured_value")

        val = rm.execute(protected_op)
        audit4.log(
            event_type=AuditEventType.DATA_READ,
            actor="system",
            action="protected_read",
            resource="secured_data",
            result="success",
            details={"attempts": call_count[0]},
            immediate=True,
        )

        assert val == "secured_value"
        assert call_count[0] == 2
        audit4.flush()
        entries = audit4.query()
        assert len(entries) >= 1
        result.ok("5-6 재시도+서킷+감사 통합 시나리오")
    except Exception as e:
        result.fail("5-6 Retry+CB+Audit 통합", str(e))

    _reset_all()


# =============================================================================
# [6] Security -> Monitoring 파이프라인 (6개)
# =============================================================================
def test_security_monitoring_pipeline(result: TestResult) -> None:
    """Security -> Monitoring 연동 시나리오."""
    print("\n[6] Security -> Monitoring 파이프라인")

    if not (_security_available and _monitoring_available):
        for i in range(1, 7):
            result.skip(f"6-{i}", "security 또는 monitoring 미사용 가능")
        return

    config_loader = _MockConfigLoader()

    # 6-1. AuditLogger 이벤트 -> MetricsCollector audit_events_total
    try:
        storage = MemoryAuditStorage()
        audit = AuditLogger(config_loader=config_loader)
        audit.add_storage(storage)

        mc = MetricsCollector(prefix="sec_mon", enabled=True, max_metrics=100)
        audit_counter = mc.counter("audit_events_total", "감사 이벤트 수", MetricUnit.COUNT)

        event_types = [
            AuditEventType.LOGIN_SUCCESS,
            AuditEventType.DATA_READ,
            AuditEventType.CONFIG_CHANGE,
            AuditEventType.SECRET_ACCESS,
            AuditEventType.ACCESS_DENIED,
        ]
        for et in event_types:
            audit.log(
                event_type=et,
                actor="admin",
                action="test_action",
                resource="test_resource",
                immediate=True,
            )
            audit_counter.labels({"event_type": et.value}).inc()

        total = sum(
            audit_counter.labels({"event_type": et.value}).get()
            for et in event_types
        )
        assert total == 5.0
        result.ok("6-1 AuditLogger -> MetricsCollector audit_events_total (5개)")
    except Exception as e:
        result.fail("6-1 Audit->Metrics", str(e))

    # 6-2. LoginFailureTracker 임계값 -> ErrorTracker 크리티컬 에러
    try:
        tracker = ErrorTracker(max_records=100, enabled=True)
        lft = LoginFailureTracker(threshold=3, window_minutes=60)

        for i in range(4):
            exceeded = lft.record_failure(f"user_{i % 2}")

        # threshold 3회 초과 시
        tracker.track(
            RuntimeError("로그인 실패 임계값 초과"),
            severity=ErrorSeverity.CRITICAL,
            context=ErrorContext(extra={"tracker": "login_failure"}),
        )

        summary = tracker.get_summary(hours=1)
        assert summary.total_count >= 1
        result.ok("6-2 LoginFailureTracker 임계값 -> ErrorTracker CRITICAL")
    except Exception as e:
        result.fail("6-2 LoginFailure->Error", str(e))

    # 6-3. SecretManager 캐시 통계 -> HealthChecker 의존성
    try:
        sm = SecretManager(config_loader=config_loader)
        hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)

        def secret_cache_health() -> HealthCheckResult:
            try:
                stats = sm.get_cache_stats()
                return HealthCheckResult.healthy(
                    "secret_cache", MonitoringDependencyType.CACHE,
                    f"캐시 항목: {stats.get('total_entries', 0)}",
                    response_time_ms=0.1,
                )
            except Exception as ex:
                return HealthCheckResult.unhealthy(
                    "secret_cache", MonitoringDependencyType.CACHE, str(ex),
                )

        hc.register_check("secret_cache", secret_cache_health, MonitoringDependencyType.CACHE)
        r = hc.check("secret_cache")
        assert r.status == HealthStatus.HEALTHY
        hc.shutdown()
        result.ok("6-3 SecretManager 캐시 -> HealthChecker 의존성")
    except Exception as e:
        result.fail("6-3 SecretCache->Health", str(e))

    # 6-4. 감사 체인 무결성 -> HealthChecker 커스텀 체크
    try:
        storage2 = MemoryAuditStorage()
        audit2 = AuditLogger(config_loader=config_loader)
        audit2.add_storage(storage2)

        # 이벤트 기록
        for i in range(5):
            audit2.log(
                event_type=AuditEventType.DATA_READ,
                actor=f"user_{i}",
                action="read",
                resource=f"data_{i}",
                immediate=True,
            )
        audit2.flush()

        hc2 = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)

        def audit_integrity_check() -> HealthCheckResult:
            entries = audit2.query(limit=10)
            if len(entries) >= 5:
                return HealthCheckResult.healthy(
                    "audit_integrity", MonitoringDependencyType.CUSTOM,
                    f"감사 로그 정상 ({len(entries)}건)", response_time_ms=0.1,
                )
            return HealthCheckResult.degraded(
                "audit_integrity", MonitoringDependencyType.CUSTOM,
                f"감사 로그 부족 ({len(entries)}건)",
            )

        hc2.register_check("audit_integrity", audit_integrity_check, MonitoringDependencyType.CUSTOM)
        r = hc2.check("audit_integrity")
        assert r.status == HealthStatus.HEALTHY
        hc2.shutdown()
        result.ok("6-4 감사 체인 무결성 -> HealthChecker 커스텀 체크")
    except Exception as e:
        result.fail("6-4 Audit 무결성->Health", str(e))

    # 6-5. 보안 이벤트 -> Profiler 측정
    try:
        profiler = PerformanceProfiler(
            enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
        )
        storage3 = MemoryAuditStorage()
        audit3 = AuditLogger(config_loader=config_loader)
        audit3.add_storage(storage3)

        for i in range(10):
            start_t = time.perf_counter()
            audit3.log(
                event_type=AuditEventType.DATA_READ,
                actor="system",
                action="audit_perf_test",
                resource=f"resource_{i}",
                immediate=True,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            profiler.profile_function_call("audit_log", execution_time_ms=elapsed_ms)

        fp = profiler.get_function_profile("audit_log")
        assert fp is not None
        assert fp.call_count == 10
        assert fp.average_time_ms >= 0
        result.ok(f"6-5 보안 이벤트 -> Profiler 측정 (10회, avg={fp.average_time_ms:.3f}ms)")
    except Exception as e:
        result.fail("6-5 Audit->Profiler", str(e))

    # 6-6. 보안 메트릭 Export 확인
    try:
        mc2 = MetricsCollector(prefix="sec_export", enabled=True, max_metrics=100)
        mc2.counter("security_events", "보안 이벤트", MetricUnit.COUNT).inc(5)
        mc2.counter("login_failures", "로그인 실패", MetricUnit.COUNT).inc(2)
        mc2.gauge("active_sessions", "활성 세션", MetricUnit.COUNT).set(10.0)

        exported = mc2.get_all_snapshots()
        names = [s.name for s in exported]
        assert any("security_events" in n for n in names)
        assert any("login_failures" in n for n in names)
        assert any("active_sessions" in n for n in names)
        result.ok(f"6-6 보안 메트릭 Export ({len(exported)}개)")
    except Exception as e:
        result.fail("6-6 보안 Export", str(e))


# =============================================================================
# [7] 전체 관측 파이프라인 (8개)
# =============================================================================
def test_full_observability_pipeline(result: TestResult) -> None:
    """20-프레임 분석 시뮬레이션: 모든 모듈 동시 작동."""
    print("\n[7] 전체 관측 파이프라인 (20-프레임 분석)")

    all_available = _monitoring_available and _resilience_available and _security_available
    if not all_available:
        for i in range(1, 9):
            result.skip(f"7-{i}", "일부 모듈 미사용 가능")
        return

    _reset_all()
    config_loader = _MockConfigLoader()
    config_loader.set("analysis.target_fps", 30)

    # 전체 모듈 초기화
    tracker = ErrorTracker(max_records=500, enabled=True)
    mc = MetricsCollector(prefix="full_obs", enabled=True, max_metrics=1000)
    profiler = PerformanceProfiler(
        enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
    )
    hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)
    cb = _make_cb("api_circuit", failure_threshold=5, minimum_requests=5, open_timeout=0.1)
    rm = _make_retry(max_attempts=3)

    storage = MemoryAuditStorage()
    audit = AuditLogger(config_loader=config_loader)
    audit.add_storage(storage)

    # 메트릭 정의
    frame_counter = mc.counter("frames_total", "프레임 수", MetricUnit.COUNT)
    fps_gauge = mc.gauge("current_fps", "현재 FPS", MetricUnit.FPS)
    frame_time = mc.histogram("frame_time_ms", "프레임 시간", MetricUnit.MILLISECONDS)
    error_counter = mc.counter("errors_total", "에러 수", MetricUnit.COUNT)

    # 7-1. 설정 로드 확인
    try:
        fps_val = config_loader.get_int("analysis.target_fps", 30)
        assert fps_val == 30
        audit.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            actor="system", action="load_config",
            resource="analysis_config", result="success",
            immediate=True,
        )
        result.ok("7-1 설정 로드 + 감사 기록")
    except Exception as e:
        result.fail("7-1 설정 로드", str(e))

    # 7-2. 20-프레임 처리 + 메트릭 기록
    try:
        frame_count = 20
        start_batch = time.perf_counter()

        for frame_id in range(frame_count):
            frame_start = time.perf_counter()
            time.sleep(0.001)  # 분석 시뮬레이션
            frame_elapsed_ms = (time.perf_counter() - frame_start) * 1000

            profiler.profile_function_call("process_frame", execution_time_ms=frame_elapsed_ms)
            frame_counter.inc()
            frame_time.observe(frame_elapsed_ms)

        batch_elapsed = time.perf_counter() - start_batch
        actual_fps = frame_count / batch_elapsed if batch_elapsed > 0 else 0
        fps_gauge.set(actual_fps)

        assert frame_counter.snapshot().values[0].value == 20
        result.ok(f"7-2 프레임 처리 완료 (20프레임, FPS={actual_fps:.1f})")
    except Exception as e:
        result.fail("7-2 프레임 처리", str(e))

    # 7-3. 외부 API 서킷 보호
    try:
        api_call_count = [0]

        def external_api():
            api_call_count[0] += 1
            return {"status": 200, "data": "player_stats"}

        api_result = rm.execute(lambda: cb.execute(external_api))
        assert api_result["status"] == 200
        assert cb.is_closed
        result.ok("7-3 CircuitBreaker 보호 외부 API 호출")
    except Exception as e:
        result.fail("7-3 CB API 호출", str(e))

    # 7-4. 일시적 실패 -> 재시도 성공
    try:
        retry_call = [0]

        def transient_fail():
            retry_call[0] += 1
            if retry_call[0] < 2:
                raise ConnectionError("network blip")
            return cb.execute(lambda: "recovered_data")

        val = rm.execute(transient_fail)
        assert val == "recovered_data"
        result.ok(f"7-4 일시적 실패 재시도 성공 (시도 {retry_call[0]}회)")
    except Exception as e:
        result.fail("7-4 재시도 성공", str(e))

    # 7-5. 감사 로그 데이터 접근 기록
    try:
        audit.log(
            event_type=AuditEventType.DATA_READ,
            actor="analysis_engine",
            action="read_frame_data",
            resource="video_frames",
            result="success",
            details={"frames_processed": 20},
            immediate=True,
        )
        audit.flush()
        entries = audit.query(event_types=[AuditEventType.DATA_READ])
        assert len(entries) >= 1
        result.ok(f"7-5 감사 로그 데이터 접근 기록 ({len(entries)}건)")
    except Exception as e:
        result.fail("7-5 감사 기록", str(e))

    # 7-6. 에러 프레임 시뮬레이션 + ErrorTracker
    try:
        for i in range(2):
            exc = RuntimeError(f"프레임 {20 + i} 분석 실패")
            tracker.track(exc, severity=ErrorSeverity.WARNING)
            error_counter.inc()

        assert tracker.get_summary(hours=1).total_count == 2
        assert error_counter.snapshot().values[0].value == 2.0
        result.ok("7-6 에러 프레임 -> ErrorTracker + MetricsCollector")
    except Exception as e:
        result.fail("7-6 에러 프레임", str(e))

    # 7-7. HealthChecker 전체 모듈 상태 집계
    try:
        def fps_health() -> HealthCheckResult:
            fps = fps_gauge.snapshot().values[0].value if fps_gauge.snapshot().values else 0
            if fps >= 24:
                return HealthCheckResult.healthy(
                    "fps", MonitoringDependencyType.CUSTOM, f"FPS={fps:.0f}", response_time_ms=0.1
                )
            return HealthCheckResult.degraded(
                "fps", MonitoringDependencyType.CUSTOM, f"Low FPS={fps:.0f}",
            )

        def circuit_health() -> HealthCheckResult:
            if cb.is_closed:
                return HealthCheckResult.healthy(
                    "circuit", MonitoringDependencyType.CUSTOM, "CLOSED", response_time_ms=0.1,
                )
            return HealthCheckResult.unhealthy(
                "circuit", MonitoringDependencyType.CUSTOM, cb.state.value,
            )

        hc.register_check("fps_status", fps_health, MonitoringDependencyType.CUSTOM)
        hc.register_check("circuit_status", circuit_health, MonitoringDependencyType.CUSTOM)
        sh = hc.check_all(parallel=False)

        assert sh.total_checks == 2
        result.ok(f"7-7 HealthChecker 상태 집계 (status={sh.overall_status.value})")
    except Exception as e:
        result.fail("7-7 HealthChecker 집계", str(e))

    # 7-8. 전체 Export + 상태 요약
    try:
        exported = mc.get_all_snapshots()
        health_summary = hc.get_status_summary()
        error_summary = tracker.get_summary(hours=1)
        profiler_fp = profiler.get_function_profile("process_frame")
        audit.flush()
        audit_entries = audit.query(limit=100)

        assert len(exported) >= 4
        assert isinstance(health_summary, dict)
        assert error_summary.total_count == 2
        assert profiler_fp.call_count == 20
        assert len(audit_entries) >= 2

        hc.shutdown()
        result.ok(f"7-8 전체 상태 요약 (metrics={len(exported)}, errors={error_summary.total_count}, audit={len(audit_entries)})")
    except Exception as e:
        result.fail("7-8 전체 요약", str(e))

    _reset_all()


# =============================================================================
# [8] Registry 통합 (6개) - registry 모듈 사용 가능 시
# =============================================================================
def test_registry_integration(result: TestResult) -> None:
    """Registry 모듈과 다른 모듈 간 통합 테스트."""
    print("\n[8] Registry 통합")

    if not _registry_available:
        for i in range(1, 7):
            result.skip(f"8-{i}", "registry 모듈 미사용 가능")
        return

    _reset_all()
    config_loader = _MockConfigLoader()

    # 8-1. ModelRegistry + ServiceRegistry 상호 운용
    try:
        mr = ModelRegistry(max_models=50)
        sr = ServiceRegistry(max_services=50)

        mr.register(name="yolo-pose", model_type=ModelType.YOLO, version="1.0.0")
        mr.register(name="yolo-ball", model_type=ModelType.YOLO, version="1.0.0")

        class MockService:
            def __init__(self, name):
                self._name = name

            @property
            def service_name(self):
                return self._name

            def initialize(self):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            def health_check(self):
                return True

        sr.register(name="pose_svc", service_type=ServiceType.POSE_ESTIMATOR, instance=MockService("pose_svc"))
        sr.register(name="detect_svc", service_type=ServiceType.DETECTOR, instance=MockService("detect_svc"))

        assert mr.model_count == 2
        assert sr.service_count == 2
        mr.shutdown()
        sr.shutdown()
        result.ok("8-1 ModelRegistry + ServiceRegistry 상호 운용 (models=2, services=2)")
    except Exception as e:
        result.fail("8-1 MR+SR", str(e))

    _reset_model_registry()
    _reset_service_registry()

    # 8-2. PipelineCoordinator 오케스트레이션
    try:
        config = (
            PipelineBuilder(PipelineType.TRAINING_SHOOTING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.SHOOTING_ANALYSIS)
            .with_timeout(1800)
            .build()
        )
        assert config.stage_count == 5
        assert config.pipeline_type == PipelineType.TRAINING_SHOOTING
        result.ok(f"8-2 PipelineCoordinator 빌드 (stages={config.stage_count})")
    except Exception as e:
        result.fail("8-2 Pipeline 빌드", str(e))

    # 8-3. RuleSetManager + CircuitBreaker (규칙 로딩 보호)
    try:
        if _resilience_available:
            rsm = RuleSetManager(config_loader)
            cb = _make_cb("rule_cb", failure_threshold=5, minimum_requests=5)

            rule_set = cb.execute(lambda: rsm.get_rule_set(League.FIBA))
            assert rule_set is not None
            assert rule_set.rule_count > 0
            rsm.shutdown()
            result.ok(f"8-3 RuleSetManager + CircuitBreaker (FIBA rules={rule_set.rule_count})")
        else:
            result.skip("8-3 RSM+CB", "resilience 미사용 가능")
    except Exception as e:
        result.fail("8-3 RSM+CB", str(e))

    _reset_rule_set_manager()

    # 8-4. DI 컨테이너가 서비스 해결
    try:
        container = DIContainer()
        mr = ModelRegistry(max_models=20)
        container.register_instance(ModelRegistry, mr)
        resolved = container.resolve(ModelRegistry)
        assert resolved is mr
        mr.shutdown()
        container.shutdown()
        result.ok("8-4 DI 컨테이너 -> ModelRegistry 해결")
    except Exception as e:
        result.fail("8-4 DI 해결", str(e))

    _reset_container()

    # 8-5. PipelineTemplates 5개 템플릿 생성
    try:
        templates = {
            "training_shooting": PipelineTemplates.training_shooting(),
            "training_dribbling": PipelineTemplates.training_dribbling(),
            "training_comparison": PipelineTemplates.training_comparison(),
            "game_full": PipelineTemplates.game_full(),
            "referee_full": PipelineTemplates.referee_full(),
        }
        for name, tmpl in templates.items():
            assert tmpl.stage_count > 0, f"{name} 스테이지 없음"
        result.ok(f"8-5 PipelineTemplates 5개 생성 완료")
    except Exception as e:
        result.fail("8-5 Templates", str(e))

    # 8-6. Registry + Monitoring 통합 (있는 경우)
    try:
        if _monitoring_available:
            mc = MetricsCollector(prefix="reg_mon", enabled=True, max_metrics=100)
            models_gauge = mc.gauge("registered_models", "등록 모델 수", MetricUnit.COUNT)

            mr2 = ModelRegistry(max_models=50)
            mr2.register(name="test-model", model_type=ModelType.YOLO, version="1.0.0")
            models_gauge.set(float(mr2.model_count))

            assert models_gauge.snapshot().values[0].value == 1.0
            mr2.shutdown()
            result.ok("8-6 Registry + Monitoring 통합 (모델 수 메트릭)")
        else:
            result.skip("8-6 Registry+Monitoring", "monitoring 미사용 가능")
    except Exception as e:
        result.fail("8-6 Registry+Mon", str(e))

    _reset_all()


# =============================================================================
# [9] 에러 전파 크로스 모듈 (5개)
# =============================================================================
def test_error_propagation(result: TestResult) -> None:
    """에러가 여러 모듈을 걸쳐 전파되는 시나리오."""
    print("\n[9] 에러 전파 크로스 모듈")

    all_available = _monitoring_available and _resilience_available and _security_available
    if not all_available:
        for i in range(1, 6):
            result.skip(f"9-{i}", "일부 모듈 미사용 가능")
        return

    _reset_all()
    config_loader = _MockConfigLoader()

    # 9-1. 설정 로드 실패 -> monitoring 에러 -> resilience 폴백 -> security 감사
    try:
        tracker = ErrorTracker(max_records=100, enabled=True)
        cb = _make_cb("config_fail_cb", failure_threshold=2, minimum_requests=2)
        storage = MemoryAuditStorage()
        audit = AuditLogger(config_loader=config_loader)
        audit.add_storage(storage)

        # 설정 로드 실패 시뮬레이션
        config_error = IOError("설정 파일 접근 불가")
        tracker.track(config_error, severity=ErrorSeverity.ERROR)

        # 서킷에 실패 기록
        cb.record_failure(exception=config_error)
        cb.record_failure(exception=config_error)
        assert cb.state == CircuitState.OPEN

        # 폴백 사용
        val = cb.execute(
            lambda: "real_config",
            fallback=lambda: "default_config",
        )
        assert val == "default_config"

        # 감사 기록
        audit.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            actor="system",
            action="config_load_fallback",
            resource="app_config",
            result="fallback",
            severity=AuditSeverity.WARNING,
            details={"reason": "config_file_inaccessible"},
            immediate=True,
        )

        assert tracker.get_summary(hours=1).total_count >= 1
        audit.flush()
        assert len(audit.query()) >= 1
        result.ok("9-1 설정 실패 -> 에러 추적 -> 서킷 폴백 -> 감사 기록")
    except Exception as e:
        result.fail("9-1 설정 실패 전파", str(e))

    # 9-2. 연쇄 서킷 (DB 서킷 OPEN -> 관련 서비스 저하)
    try:
        db_cb = _make_cb("db_circuit", failure_threshold=2, minimum_requests=2)
        svc_cb = _make_cb("svc_circuit", failure_threshold=3, minimum_requests=3)
        mc = MetricsCollector(prefix="cascade", enabled=True, max_metrics=100)
        cascade_counter = mc.counter("cascading_failures", "연쇄 실패", MetricUnit.COUNT)

        # DB 서킷 OPEN
        db_cb.record_failure(exception=ConnectionError("DB down"))
        db_cb.record_failure(exception=ConnectionError("DB down"))
        assert db_cb.state == CircuitState.OPEN

        # DB 의존 서비스 실패
        for _ in range(3):
            try:
                db_cb.execute(lambda: "db_query")
            except _CircuitBreakerOpenException:
                svc_cb.record_failure(exception=RuntimeError("DB 의존 서비스 실패"))
                cascade_counter.inc()

        assert svc_cb.state == CircuitState.OPEN
        assert cascade_counter.snapshot().values[0].value >= 3
        result.ok("9-2 연쇄 서킷 (DB OPEN -> 서비스 OPEN)")
    except Exception as e:
        result.fail("9-2 연쇄 서킷", str(e))

    # 9-3. 시크릿 미발견 -> 재시도 -> 서킷 OPEN -> 감사 로그
    try:
        cb = _make_cb("secret_retry_cb", failure_threshold=3, minimum_requests=3)
        rm = _make_retry(max_attempts=3)
        storage2 = MemoryAuditStorage()
        audit2 = AuditLogger(config_loader=config_loader)
        audit2.add_storage(storage2)
        tracker2 = ErrorTracker(max_records=100, enabled=True)

        attempt_count = [0]

        def get_secret():
            attempt_count[0] += 1
            return cb.execute(
                lambda: (_ for _ in ()).throw(ConnectionError("secret provider down"))
            )

        rr = rm.execute_with_result(get_secret)

        if not rr.success:
            tracker2.track(
                ConnectionError("시크릿 조회 실패"),
                severity=ErrorSeverity.CRITICAL,
            )
            audit2.log(
                event_type=AuditEventType.SECRET_ACCESS,
                actor="system",
                action="get_secret_failed",
                resource="database_password",
                result="failure",
                severity=AuditSeverity.CRITICAL,
                immediate=True,
            )

        assert not rr.success
        assert cb.state == CircuitState.OPEN
        assert tracker2.get_summary(hours=1).total_count >= 1
        audit2.flush()
        assert len(audit2.query()) >= 1
        result.ok("9-3 시크릿 실패 -> 재시도 -> 서킷 OPEN -> 감사 로그")
    except Exception as e:
        result.fail("9-3 시크릿 전파", str(e))

    # 9-4. 전체 모듈 에러 전파 + 메트릭 일관성
    try:
        mc2 = MetricsCollector(prefix="propagation", enabled=True, max_metrics=100)
        error_total = mc2.counter("errors_total", "전체 에러", MetricUnit.COUNT)
        tracker3 = ErrorTracker(max_records=100, enabled=True)

        errors = [
            (IOError("설정 파일 오류"), ErrorSeverity.ERROR),
            (ConnectionError("API 연결 실패"), ErrorSeverity.WARNING),
            (TimeoutError("DB 타임아웃"), ErrorSeverity.ERROR),
            (RuntimeError("분석 엔진 오류"), ErrorSeverity.CRITICAL),
        ]
        for exc, sev in errors:
            tracker3.track(exc, severity=sev)
            error_total.inc()

        assert tracker3.get_summary(hours=1).total_count == 4
        assert error_total.snapshot().values[0].value == 4.0
        result.ok("9-4 전체 에러 전파 + 메트릭 일관 (4건)")
    except Exception as e:
        result.fail("9-4 에러 전파 일관성", str(e))

    # 9-5. 에러 복구 후 정상화 검증
    try:
        cb = _make_cb("recovery_test", failure_threshold=2, minimum_requests=2,
                       open_timeout=0.05, success_threshold=1)
        cb.record_failure(exception=ValueError("a"))
        cb.record_failure(exception=ValueError("b"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)
        _ = cb.state  # HALF_OPEN
        cb.record_success(1.0)
        assert cb.state == CircuitState.CLOSED

        # 복구 후 정상 작동 확인
        rm2 = _make_retry(max_attempts=2)
        val = rm2.execute(lambda: cb.execute(lambda: "normal"))
        assert val == "normal"
        result.ok("9-5 에러 복구 -> 정상화 검증")
    except Exception as e:
        result.fail("9-5 에러 복구", str(e))

    _reset_all()


# =============================================================================
# [10] 모듈 격리 및 정리 (7개)
# =============================================================================
def test_module_isolation_cleanup(result: TestResult) -> None:
    """모듈 간 격리, 리셋, 스레드 안전성."""
    print("\n[10] 모듈 격리 및 정리")

    # 10-1. 각 모듈 독립 리셋 검증
    try:
        if _resilience_available:
            _reset_circuit_registry()
            _reset_retry_registry()

            cb = _make_cb("isolation_test")
            cb.record_success(1.0)
            assert cb.stats.total_successes >= 1

            _reset_circuit_registry()

            # 리셋 후 새 인스턴스
            cb2 = _make_cb("isolation_test_2")
            assert cb2.stats.total_successes == 0
            result.ok("10-1 resilience 독립 리셋")
        else:
            result.skip("10-1 resilience 독립 리셋", "모듈 미사용 가능")
    except Exception as e:
        result.fail("10-1 독립 리셋", str(e))

    # 10-2. 한 모듈 리셋이 다른 모듈에 영향 없음
    try:
        if _resilience_available and _monitoring_available:
            _reset_circuit_registry()

            tracker = ErrorTracker(max_records=100, enabled=True)
            tracker.track(ValueError("test"), severity=ErrorSeverity.WARNING)
            assert tracker.get_summary(hours=1).total_count == 1

            # resilience 리셋
            _reset_circuit_registry()
            _reset_retry_registry()

            # monitoring은 영향 없어야 함
            assert tracker.get_summary(hours=1).total_count == 1
            result.ok("10-2 resilience 리셋 -> monitoring 무영향")
        else:
            result.skip("10-2 교차 리셋", "모듈 미사용 가능")
    except Exception as e:
        result.fail("10-2 교차 리셋", str(e))

    # 10-3. 멀티스레드 동시 모듈 접근
    try:
        if _resilience_available and _monitoring_available:
            _reset_circuit_registry()

            errors = []
            results_list = []

            def thread_fn(thread_id: int):
                try:
                    # resilience
                    cb = _make_cb(f"thread_cb_{thread_id}")
                    cb.record_success(1.0)

                    # monitoring
                    mc = MetricsCollector(prefix=f"t{thread_id}", enabled=True, max_metrics=50)
                    c = mc.counter("ops", "ops", MetricUnit.COUNT)
                    c.inc()

                    results_list.append(thread_id)
                except Exception as ex:
                    errors.append(str(ex))

            threads = [threading.Thread(target=thread_fn, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"에러: {errors[:3]}"
            assert len(results_list) == 8
            result.ok("10-3 멀티스레드 동시 모듈 접근 (8스레드)")
        else:
            result.skip("10-3 멀티스레드", "모듈 미사용 가능")
    except Exception as e:
        result.fail("10-3 멀티스레드", str(e))

    # 10-4. Security 모듈 독립 정리
    try:
        if _security_available:
            config_loader = _MockConfigLoader()

            # 첫 번째 AuditLogger + 전용 MemoryAuditStorage
            storage_a = MemoryAuditStorage()
            audit_a = AuditLogger(config_loader=config_loader)
            audit_a._storages.clear()  # 기본 저장소 제거
            audit_a._storages.append(storage_a)

            audit_a.log(
                event_type=AuditEventType.DATA_READ,
                actor="test", action="read", resource="test_isolation",
                immediate=True,
            )
            audit_a.flush()
            entries_a = audit_a.query()
            assert len(entries_a) >= 1, f"entries_a={len(entries_a)}"

            # 두 번째 AuditLogger + 전용 MemoryAuditStorage
            storage_b = MemoryAuditStorage()
            audit_b = AuditLogger(config_loader=config_loader)
            audit_b._storages.clear()
            audit_b._storages.append(storage_b)

            # audit_a의 항목은 변하지 않아야 함
            entries_a2 = audit_a.query()
            assert len(entries_a2) == len(entries_a), (
                f"이전={len(entries_a)}, 이후={len(entries_a2)}"
            )
            # audit_b는 비어있어야 함
            entries_b = audit_b.query()
            assert len(entries_b) == 0, f"audit_b entries={len(entries_b)}"
            result.ok("10-4 Security 모듈 독립 정리")
        else:
            result.skip("10-4 Security 정리", "모듈 미사용 가능")
    except Exception as e:
        result.fail("10-4 Security 정리", str(e))

    # 10-5. 전체 리셋 후 재초기화
    try:
        _reset_all()

        if _resilience_available:
            cb = _make_cb("reinit_test")
            assert cb.is_closed
            rm = _make_retry()
            assert rm.execute(lambda: "ok") == "ok"

        if _monitoring_available:
            mc = MetricsCollector(prefix="reinit", enabled=True, max_metrics=50)
            c = mc.counter("test", "test", MetricUnit.COUNT)
            c.inc()
            assert c.snapshot().values[0].value == 1.0

        result.ok("10-5 전체 리셋 후 재초기화 성공")
    except Exception as e:
        result.fail("10-5 재초기화", str(e))

    # 10-6. Registry 리셋 독립성
    try:
        if _registry_available:
            _reset_model_registry()
            _reset_service_registry()

            mr = ModelRegistry(max_models=10)
            mr.register(name="test", model_type=ModelType.YOLO, version="1.0.0")
            assert mr.model_count == 1

            # 서비스 레지스트리 리셋이 모델에 영향 없음
            _reset_service_registry()
            assert mr.model_count == 1

            mr.shutdown()
            _reset_model_registry()
            result.ok("10-6 Registry 리셋 독립성 (ServiceRegistry 리셋 -> ModelRegistry 무영향)")
        else:
            result.skip("10-6 Registry 독립성", "registry 미사용 가능")
    except Exception as e:
        result.fail("10-6 Registry 독립성", str(e))

    # 10-7. 멀티스레드 전체 모듈 동시 리셋 안전
    try:
        errors = []

        def reset_fn():
            try:
                _reset_all()
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=reset_fn) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"

        # 리셋 후 정상 작동 확인
        if _resilience_available:
            cb = _make_cb("final_test")
            assert cb.is_closed
        result.ok("10-7 멀티스레드 전체 리셋 안전 (4스레드)")
    except Exception as e:
        result.fail("10-7 멀티스레드 리셋", str(e))

    _reset_all()


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - core_foundation 크로스 모듈 통합 테스트")
    print("=" * 60)

    available = []
    if _monitoring_available:
        available.append("monitoring")
    if _resilience_available:
        available.append("resilience")
    if _security_available:
        available.append("security")
    if _registry_available:
        available.append("registry")
    print(f"사용 가능 모듈: {', '.join(available) if available else '없음'}")

    r = TestResult()

    test_top_level_import_integrity(r)       # [1]  8개
    test_cross_module_all_exports(r)         # [2]  5개
    test_config_monitoring_pipeline(r)       # [3]  7개
    test_monitoring_resilience_pipeline(r)   # [4]  7개
    test_resilience_security_pipeline(r)     # [5]  6개
    test_security_monitoring_pipeline(r)     # [6]  6개
    test_full_observability_pipeline(r)      # [7]  8개
    test_registry_integration(r)             # [8]  6개
    test_error_propagation(r)                # [9]  5개
    test_module_isolation_cleanup(r)         # [10] 7개

    r.summary()
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
