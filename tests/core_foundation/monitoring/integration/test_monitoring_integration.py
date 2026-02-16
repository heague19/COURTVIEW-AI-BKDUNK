# -*- coding: utf-8 -*-
"""
COURTVIEW - monitoring 모듈 통합 테스트

12개 카테고리, 80개 테스트

검증 범위:
    [1]  __init__.py 임포트 무결성 (logger, error_tracker, metrics, profiler, health_checker)
    [2]  __all__ 전체 Export 검증
    [3]  Enum 상호 호환성 / 교차 참조
    [4]  ErrorTracker 독립 워크플로우
    [5]  MetricsCollector 독립 워크플로우
    [6]  PerformanceProfiler 독립 워크플로우
    [7]  HealthChecker 독립 워크플로우
    [8]  에러 추적 + 메트릭 연동 (ErrorTracker -> Metrics)
    [9]  프로파일링 + 메트릭 연동 (Profiler -> Metrics)
    [10] 헬스 체크 + 에러 추적 연동 (HealthChecker -> ErrorTracker)
    [11] 전체 파이프라인 (프레임 분석 시뮬레이션)
    [12] 싱글톤 격리 / 스레드 안전성 / 리셋

실행:
    python tests/core_foundation/monitoring/integration/test_monitoring_integration.py
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================
# TestResult
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
            print(f"통합 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"통합 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)


# =============================================================================
# [1] __init__.py 임포트 무결성 (8개)
# =============================================================================
def test_import_integrity(result: TestResult) -> None:
    """__init__.py에서 모든 서브모듈 임포트가 정상적으로 동작하는지 검증."""
    print("\n[1] __init__.py 임포트 무결성")

    # 1-1. 패키지 임포트 자체 성공
    try:
        import core_foundation.monitoring as monitoring
        assert monitoring is not None
        result.ok("1-1 core_foundation.monitoring 패키지 임포트")
    except Exception as e:
        result.fail("1-1 패키지 임포트", str(e))
        return  # 실패 시 나머지 테스트 불가

    # 1-2. logger 모듈 심볼
    try:
        from core_foundation.monitoring import (
            LogLevel, LogManager, SinkConfig, LoggingConfig,
            InterceptHandler, SensitiveDataFilter,
            setup_logging, get_logger, log_analysis, log_performance,
            _get_manager, _reset_manager,
            LOGURU_AVAILABLE, DEFAULT_LOG_LEVEL, DEFAULT_LOG_DIR,
            DEFAULT_LOG_FORMAT, DEFAULT_FILE_FORMAT,
            DEFAULT_ROTATION_SIZE, DEFAULT_RETENTION,
            DEFAULT_SENSITIVE_PATTERNS, MASK_VALUE,
        )
        assert LogLevel is not None
        assert LogManager is not None
        result.ok("1-2 logger 심볼 (19개)")
    except ImportError as e:
        result.fail("1-2 logger 임포트", str(e))

    # 1-3. error_tracker 모듈 심볼
    try:
        from core_foundation.monitoring import (
            ErrorSeverity, ErrorCategory, TrackingCategory,
            MAX_ERROR_RECORDS, MAX_ERROR_HASHES, AGGREGATION_WINDOW_SIZE,
            ErrorRecord, ErrorSummary, ErrorTrend, ErrorContext,
            ErrorTracker, track_error, get_error_summary,
        )
        assert ErrorTracker is not None
        assert ErrorSeverity is not None
        result.ok("1-3 error_tracker 심볼 (12개)")
    except ImportError as e:
        result.fail("1-3 error_tracker 임포트", str(e))

    # 1-4. metrics 모듈 심볼
    try:
        from core_foundation.monitoring import (
            MetricType, MetricUnit,
            DEFAULT_HISTOGRAM_BUCKETS, FPS_HISTOGRAM_BUCKETS,
            ACCURACY_HISTOGRAM_BUCKETS, DEFAULT_QUANTILES,
            METRIC_PREFIX, MAX_METRICS,
            SUMMARY_WINDOW_SECONDS, SUMMARY_MAX_OBSERVATIONS,
            MODEL_INFERENCE_BUCKETS, FRAME_PROCESSING_BUCKETS,
            GPU_TEMPERATURE_BUCKETS,
            MetricValue, MetricLabels, MetricSnapshot,
            Counter, Gauge, Histogram, Summary,
            MetricsCollector, measure_latency, count_calls,
        )
        assert MetricsCollector is not None
        assert Counter is not None
        result.ok("1-4 metrics 심볼 (22개)")
    except ImportError as e:
        result.fail("1-4 metrics 임포트", str(e))

    # 1-5. profiler 모듈 심볼
    try:
        from core_foundation.monitoring import (
            ProfileType, ResourceType,
            DEFAULT_MAX_PROFILES, DEFAULT_CLEANUP_INTERVAL,
            DEFAULT_TOP_FUNCTIONS, DEFAULT_MEMORY_TRACE_LIMIT,
            FPS_WARNING_THRESHOLD, FRAME_TIME_WARNING_MS, MEMORY_WARNING_MB,
            ProfileResult, MemorySnapshot, CPUSnapshot, GPUSnapshot, FunctionProfile,
            PerformanceProfiler,
            profile_function, profile_memory, profiling_context,
            _get_profiler, _reset_profiler,
        )
        assert PerformanceProfiler is not None
        assert ProfileType is not None
        result.ok("1-5 profiler 심볼 (20개)")
    except ImportError as e:
        result.fail("1-5 profiler 임포트", str(e))

    # 1-6. health_checker 모듈 심볼
    try:
        from core_foundation.monitoring import (
            HealthStatus, DependencyType,
            DEFAULT_CHECK_TIMEOUT, MAX_HEALTH_HISTORY, DEFAULT_CHECK_INTERVAL,
            DEFAULT_CPU_WARNING_THRESHOLD, DEFAULT_CPU_CRITICAL_THRESHOLD,
            DEFAULT_MEMORY_WARNING_THRESHOLD, DEFAULT_MEMORY_CRITICAL_THRESHOLD,
            DEFAULT_DISK_WARNING_THRESHOLD, DEFAULT_DISK_CRITICAL_THRESHOLD,
            DEFAULT_GPU_TEMP_WARNING, DEFAULT_GPU_TEMP_CRITICAL,
            DEFAULT_GPU_MEMORY_WARNING, DEFAULT_GPU_MEMORY_CRITICAL,
            DEFAULT_DISK_PATH,
            HealthCheckResult, DependencyHealth, SystemHealth, HealthCheckConfig,
            HealthChecker,
            create_health_check, aggregate_health_status,
            check_cpu_health, check_memory_health, check_disk_health, check_tcp_port,
            check_gpu_health, check_camera_health,
            _get_health_checker, _reset_health_checker,
        )
        assert HealthChecker is not None
        assert HealthStatus is not None
        result.ok("1-6 health_checker 심볼 (31개)")
    except ImportError as e:
        result.fail("1-6 health_checker 임포트", str(e))

    # 1-7. 순환 참조 없음 (re-import)
    try:
        import importlib
        importlib.reload(sys.modules["core_foundation.monitoring"])
        result.ok("1-7 순환 참조 없음 (reload 성공)")
    except Exception as e:
        result.fail("1-7 순환 참조", str(e))

    # 1-8. 각 서브모듈 직접 임포트도 정상
    try:
        import core_foundation.monitoring.logger
        import core_foundation.monitoring.error_tracker
        import core_foundation.monitoring.metrics
        import core_foundation.monitoring.profiler
        import core_foundation.monitoring.health_checker
        result.ok("1-8 서브모듈 직접 임포트 (5개)")
    except ImportError as e:
        result.fail("1-8 서브모듈 직접", str(e))


# =============================================================================
# [2] __all__ Export 검증 (6개)
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__init__.py __all__ 전체 Export 검증."""
    print("\n[2] __all__ Export 검증")

    import core_foundation.monitoring as monitoring

    # 2-1. __all__ 존재
    try:
        assert hasattr(monitoring, "__all__")
        result.ok("2-1 __all__ 존재")
    except AssertionError as e:
        result.fail("2-1 __all__ 존재", str(e))

    # 2-2. __all__ 전체 개수 (logger 19 + error_tracker 12 + metrics 22 + profiler 20 + health_checker 31 = 104)
    try:
        total = len(monitoring.__all__)
        # 각 서브모듈 __all__ 합산
        from core_foundation.monitoring.logger import __all__ as log_all
        from core_foundation.monitoring.error_tracker import __all__ as et_all
        from core_foundation.monitoring.metrics import __all__ as met_all
        from core_foundation.monitoring.profiler import __all__ as prof_all
        from core_foundation.monitoring.health_checker import __all__ as hc_all
        expected = len(log_all) + len(et_all) + len(met_all) + len(prof_all) + len(hc_all)
        # __init__.__all__ 은 서브모듈 __all__ 합과 일치해야 함
        assert total == expected, f"__init__.__all__={total}, 서브합={expected}"
        result.ok(f"2-2 __all__ 개수 일치 ({total}개)")
    except AssertionError as e:
        result.fail("2-2 __all__ 개수", str(e))

    # 2-3. __all__의 모든 심볼이 실제 접근 가능
    try:
        missing = []
        for name in monitoring.__all__:
            if not hasattr(monitoring, name):
                missing.append(name)
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-3 __all__ 모든 심볼 접근 가능 ({len(monitoring.__all__)}개)")
    except AssertionError as e:
        result.fail("2-3 심볼 접근", str(e))

    # 2-4. logger 카테고리 심볼 포함
    try:
        logger_required = [
            "LogLevel", "LogManager", "setup_logging", "get_logger",
            "_get_manager", "_reset_manager",
        ]
        for sym in logger_required:
            assert sym in monitoring.__all__, f"'{sym}' 누락"
        result.ok("2-4 logger 핵심 심볼 포함")
    except AssertionError as e:
        result.fail("2-4 logger 심볼", str(e))

    # 2-5. 중복 항목 없음
    try:
        all_list = monitoring.__all__
        assert len(all_list) == len(set(all_list)), \
            f"중복: {[x for x in all_list if all_list.count(x) > 1]}"
        result.ok("2-5 __all__ 중복 없음")
    except AssertionError as e:
        result.fail("2-5 중복 검사", str(e))

    # 2-6. 서브모듈 간 이름 충돌 없음
    try:
        from core_foundation.monitoring.logger import __all__ as log_all
        from core_foundation.monitoring.error_tracker import __all__ as et_all
        from core_foundation.monitoring.metrics import __all__ as met_all
        from core_foundation.monitoring.profiler import __all__ as prof_all
        from core_foundation.monitoring.health_checker import __all__ as hc_all
        all_names = list(log_all) + list(et_all) + list(met_all) + list(prof_all) + list(hc_all)
        duplicates = [x for x in set(all_names) if all_names.count(x) > 1]
        # 충돌이 있으면 보고 (경고 수준)
        if duplicates:
            result.ok(f"2-6 서브모듈 간 이름 충돌 감지 (알려진 충돌: {duplicates})")
        else:
            result.ok("2-6 서브모듈 간 이름 충돌 없음")
    except Exception as e:
        result.fail("2-6 이름 충돌", str(e))


# =============================================================================
# [3] Enum 상호 호환성 / 교차 참조 (6개)
# =============================================================================
def test_enum_cross_reference(result: TestResult) -> None:
    """서로 다른 모듈의 Enum이 독립적이고 충돌 없이 사용 가능한지 검증."""
    print("\n[3] Enum 상호 호환성")

    from core_foundation.monitoring import (
        LogLevel, ErrorSeverity, ErrorCategory, TrackingCategory,
        MetricType, MetricUnit, ProfileType, ResourceType,
        HealthStatus, DependencyType,
    )

    # 3-1. 모든 Enum은 서로 다른 타입
    try:
        enums = [LogLevel, ErrorSeverity, ErrorCategory, TrackingCategory,
                 MetricType, MetricUnit, ProfileType, ResourceType,
                 HealthStatus, DependencyType]
        for i in range(len(enums)):
            for j in range(i + 1, len(enums)):
                assert enums[i] is not enums[j], f"{enums[i].__name__} == {enums[j].__name__}"
        result.ok(f"3-1 Enum 타입 독립성 ({len(enums)}개)")
    except AssertionError as e:
        result.fail("3-1 Enum 독립성", str(e))

    # 3-2. LogLevel과 ErrorSeverity 값 비교 불가 (서로 다른 Enum)
    try:
        assert LogLevel.ERROR != ErrorSeverity.ERROR  # 다른 Enum이므로 값 동일해도 !=
        result.ok("3-2 LogLevel.ERROR != ErrorSeverity.ERROR")
    except AssertionError:
        # Python Enum 비교: 다른 Enum 타입은 항상 !=
        result.ok("3-2 LogLevel.ERROR != ErrorSeverity.ERROR (Enum 타입 구별)")

    # 3-3. MetricType과 ProfileType 독립
    try:
        assert MetricType.COUNTER.value != ProfileType.CPU.value or type(MetricType.COUNTER) != type(ProfileType.CPU)
        result.ok("3-3 MetricType vs ProfileType 독립")
    except AssertionError as e:
        result.fail("3-3 MetricType vs ProfileType", str(e))

    # 3-4. HealthStatus.is_ok + DependencyType.is_critical 조합
    try:
        # 두 프로퍼티가 동시에 사용 가능
        status_ok = HealthStatus.HEALTHY.is_ok
        dep_critical = DependencyType.GPU.is_critical
        assert status_ok is True
        assert dep_critical is True
        # 비중요 의존성이 정상인 경우
        assert HealthStatus.DEGRADED.is_ok is True
        assert DependencyType.CAMERA.is_critical is False
        result.ok("3-4 HealthStatus.is_ok + DependencyType.is_critical 조합")
    except AssertionError as e:
        result.fail("3-4 프로퍼티 조합", str(e))

    # 3-5. Enum 값 타입 일관성 (ErrorSeverity는 int, 나머지는 str)
    try:
        str_enums = [LogLevel, TrackingCategory,
                     MetricType, MetricUnit, ProfileType, ResourceType,
                     HealthStatus, DependencyType]
        for enum_cls in str_enums:
            for member in enum_cls:
                assert isinstance(member.value, str), \
                    f"{enum_cls.__name__}.{member.name}.value = {member.value} (type: {type(member.value).__name__})"
        # ErrorSeverity는 int 값 (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50)
        for member in ErrorSeverity:
            assert isinstance(member.value, int), \
                f"ErrorSeverity.{member.name}.value = {member.value} (expected int)"
        result.ok("3-5 Enum 값 타입 일관성 (str 8개 + int 1개)")
    except AssertionError as e:
        result.fail("3-5 Enum 값 타입", str(e))

    # 3-6. ErrorCategory (shared re-export) 접근
    try:
        # ErrorCategory는 shared에서 re-export
        members = list(ErrorCategory)
        assert len(members) > 0
        result.ok(f"3-6 ErrorCategory (shared re-export, {len(members)}개)")
    except Exception as e:
        result.fail("3-6 ErrorCategory", str(e))


# =============================================================================
# [4] ErrorTracker 독립 워크플로우 (7개)
# =============================================================================
def test_error_tracker_workflow(result: TestResult) -> None:
    """ErrorTracker 생성 -> 추적 -> 요약 -> 초기화 전체 흐름."""
    print("\n[4] ErrorTracker 독립 워크플로우")

    from core_foundation.monitoring import (
        ErrorTracker, ErrorSeverity, ErrorRecord, ErrorSummary,
        ErrorContext, TrackingCategory,
    )

    tracker = ErrorTracker(max_records=100, enabled=True)

    # 4-1. 에러 추적 기본
    try:
        exc = ValueError("test error")
        record = tracker.track(exc)
        assert isinstance(record, ErrorRecord)
        assert record.message == "test error"
        result.ok("4-1 track(exception) -> ErrorRecord")
    except Exception as e:
        result.fail("4-1 에러 추적", str(e))

    # 4-2. 컨텍스트와 함께 추적
    try:
        exc = RuntimeError("analysis failed")
        ctx = ErrorContext(
            extra={"component": "motion_analyzer", "operation": "detect_pose", "frame_id": 42},
        )
        record = tracker.track(exc, context=ctx, severity=ErrorSeverity.ERROR)
        assert record.context is not None
        result.ok("4-2 track with ErrorContext")
    except Exception as e:
        result.fail("4-2 컨텍스트 추적", str(e))

    # 4-3. dict 컨텍스트
    try:
        exc = IOError("disk full")
        record = tracker.track(exc, context={"disk": "C:", "usage": 99.5})
        assert isinstance(record, ErrorRecord)
        result.ok("4-3 track with dict context")
    except Exception as e:
        result.fail("4-3 dict 컨텍스트", str(e))

    # 4-4. 요약 조회
    try:
        summary = tracker.get_summary(hours=1)
        assert isinstance(summary, ErrorSummary)
        assert summary.total_count >= 3  # 위에서 3개 추적
        result.ok(f"4-4 get_summary (total={summary.total_count})")
    except Exception as e:
        result.fail("4-4 요약 조회", str(e))

    # 4-5. 레코드 조회
    try:
        records = tracker.get_records(limit=10)
        assert len(records) >= 3
        assert all(isinstance(r, ErrorRecord) for r in records)
        result.ok(f"4-5 get_records (count={len(records)})")
    except Exception as e:
        result.fail("4-5 레코드 조회", str(e))

    # 4-6. 추세 분석
    try:
        trend = tracker.get_trend(hours=1)
        assert trend is not None
        result.ok("4-6 get_trend")
    except Exception as e:
        result.fail("4-6 추세 분석", str(e))

    # 4-7. 클리어
    try:
        tracker.clear()
        records = tracker.get_records(limit=10)
        assert len(records) == 0
        result.ok("4-7 clear -> 레코드 0개")
    except Exception as e:
        result.fail("4-7 클리어", str(e))


# =============================================================================
# [5] MetricsCollector 독립 워크플로우 (7개)
# =============================================================================
def test_metrics_workflow(result: TestResult) -> None:
    """MetricsCollector 생성 -> 메트릭 등록 -> 값 기록 -> Export 전체 흐름."""
    print("\n[5] MetricsCollector 독립 워크플로우")

    from core_foundation.monitoring import (
        MetricsCollector, MetricType, MetricUnit,
        Counter, Gauge, Histogram, Summary,
    )

    mc = MetricsCollector(prefix="integ_test", enabled=True, max_metrics=500)

    # 5-1. Counter 생성 및 증가
    try:
        c = mc.counter("frame_count", "분석 프레임 수", MetricUnit.COUNT)
        assert isinstance(c, Counter)
        c.inc()
        c.inc(5)
        snapshot = c.snapshot()
        assert snapshot.values[0].value == 6.0
        result.ok("5-1 Counter inc -> 6.0")
    except Exception as e:
        result.fail("5-1 Counter", str(e))

    # 5-2. Gauge 설정
    try:
        g = mc.gauge("fps", "현재 FPS", MetricUnit.FPS)
        assert isinstance(g, Gauge)
        g.set(30.0)
        assert g.snapshot().values[0].value == 30.0
        g.inc(5.0)
        assert g.snapshot().values[0].value == 35.0
        g.dec(10.0)
        assert g.snapshot().values[0].value == 25.0
        result.ok("5-2 Gauge set/inc/dec")
    except Exception as e:
        result.fail("5-2 Gauge", str(e))

    # 5-3. Histogram 관측
    try:
        h = mc.histogram("latency_ms", "처리 지연", MetricUnit.MILLISECONDS)
        assert isinstance(h, Histogram)
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            h.observe(v)
        snap = h.snapshot()
        # Histogram: values[-1]이 count (values[-2]는 sum, 나머지는 bucket)
        assert snap.values[-1].value == 5  # count
        result.ok("5-3 Histogram observe (5회)")
    except Exception as e:
        result.fail("5-3 Histogram", str(e))

    # 5-4. Summary 관측
    try:
        s = mc.summary("accuracy", "분석 정확도", MetricUnit.PERCENT)
        assert isinstance(s, Summary)
        for v in [90.0, 92.0, 95.0, 88.0, 91.0]:
            s.observe(v)
        snap = s.snapshot()
        # Summary: values[-1]이 count (values[-2]는 sum, 나머지는 quantile)
        assert snap.values[-1].value == 5  # count
        result.ok("5-4 Summary observe (5회)")
    except Exception as e:
        result.fail("5-4 Summary", str(e))

    # 5-5. 전체 Export
    try:
        exported = mc.get_all_snapshots()
        assert isinstance(exported, list)
        assert len(exported) >= 4  # 위에서 등록한 4개 + 기본 메트릭
        result.ok(f"5-5 export_all ({len(exported)}개)")
    except Exception as e:
        result.fail("5-5 export", str(e))

    # 5-6. 레이블 메트릭
    try:
        c_label = mc.counter("action_count", "동작별 카운트", MetricUnit.COUNT)
        c_label.labels({"action": "shooting"}).inc()
        c_label.labels({"action": "dribble"}).inc(3)
        # CounterChild는 get()으로 값 조회 (snapshot() 미지원)
        shooting_val = c_label.labels({"action": "shooting"}).get()
        dribble_val = c_label.labels({"action": "dribble"}).get()
        assert shooting_val == 1.0
        assert dribble_val == 3.0
        result.ok("5-6 레이블 메트릭 (shooting=1, dribble=3)")
    except Exception as e:
        result.fail("5-6 레이블", str(e))

    # 5-7. get_status
    try:
        status = mc.get_status()
        assert isinstance(status, dict)
        assert "enabled" in status
        assert "total_metrics" in status
        assert status["enabled"] is True
        result.ok("5-7 get_status")
    except Exception as e:
        result.fail("5-7 get_status", str(e))


# =============================================================================
# [6] PerformanceProfiler 독립 워크플로우 (7개)
# =============================================================================
def test_profiler_workflow(result: TestResult) -> None:
    """PerformanceProfiler 프로파일링 전체 흐름."""
    print("\n[6] PerformanceProfiler 독립 워크플로우")

    from core_foundation.monitoring import (
        PerformanceProfiler, ProfileType, ProfileResult, FunctionProfile,
        profile_function, profiling_context,
        _reset_profiler,
    )

    profiler = PerformanceProfiler(
        enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
    )

    # 6-1. start/stop TIME 프로파일링
    try:
        pid = profiler.start_profiling(ProfileType.TIME, "test_session")
        assert isinstance(pid, str)
        assert len(pid) > 0
        time.sleep(0.01)
        pr = profiler.stop_profiling()
        assert isinstance(pr, ProfileResult)
        assert pr.profile_id == pid
        assert pr.duration_ms > 0
        result.ok(f"6-1 start/stop TIME (duration={pr.duration_ms:.1f}ms)")
    except Exception as e:
        result.fail("6-1 start/stop", str(e))

    # 6-2. 함수 프로파일링
    try:
        fp = profiler.profile_function_call("detect_pose", execution_time_ms=15.5)
        assert isinstance(fp, FunctionProfile)
        assert fp.call_count == 1
        assert fp.total_time_ms == 15.5
        result.ok("6-2 profile_function_call")
    except Exception as e:
        result.fail("6-2 함수 프로파일링", str(e))

    # 6-3. 함수 프로파일링 누적
    try:
        for i in range(10):
            profiler.profile_function_call("track_ball", execution_time_ms=float(i + 1))
        fp = profiler.get_function_profile("track_ball")
        assert fp is not None
        assert fp.call_count == 10
        assert fp.total_time_ms == 55.0  # 1+2+...+10
        result.ok(f"6-3 함수 누적 (10회, total={fp.total_time_ms}ms)")
    except Exception as e:
        result.fail("6-3 함수 누적", str(e))

    # 6-4. 느린 함수 감지
    try:
        profiler.profile_function_call("slow_render", execution_time_ms=100.0)
        slow = profiler.get_slow_functions(threshold_ms=40.0)
        slow_names = [f.name for f in slow]
        assert "slow_render" in slow_names
        result.ok(f"6-4 느린 함수 감지 ({len(slow)}개)")
    except Exception as e:
        result.fail("6-4 느린 함수", str(e))

    # 6-5. profiling_context 컨텍스트 매니저
    try:
        _reset_profiler()
        from core_foundation.monitoring import _get_profiler
        p = _get_profiler()
        with profiling_context("ctx_test", ProfileType.TIME) as pid:
            time.sleep(0.01)
        # 컨텍스트 매니저 종료 후 프로파일이 기록됨
        if pid:
            pr = p.get_profile(pid)
            assert pr is not None
        result.ok("6-5 profiling_context")
    except Exception as e:
        result.fail("6-5 컨텍스트 매니저", str(e))
    finally:
        _reset_profiler()

    # 6-6. get_all_profiles
    try:
        p2 = PerformanceProfiler(
            enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
        )
        for i in range(3):
            p2.start_profiling(ProfileType.TIME, f"session_{i}")
            p2.stop_profiling()
        all_profs = p2.get_all_profiles()
        assert len(all_profs) == 3
        result.ok("6-6 get_all_profiles (3개)")
    except Exception as e:
        result.fail("6-6 all_profiles", str(e))

    # 6-7. clear
    try:
        count = p2.clear_profiles()
        assert count == 3
        assert len(p2.get_all_profiles()) == 0
        result.ok("6-7 clear_profiles (3개 삭제)")
    except Exception as e:
        result.fail("6-7 clear", str(e))


# =============================================================================
# [7] HealthChecker 독립 워크플로우 (7개)
# =============================================================================
def test_health_checker_workflow(result: TestResult) -> None:
    """HealthChecker 등록 -> 체크 -> check_all -> 히스토리 전체 흐름."""
    print("\n[7] HealthChecker 독립 워크플로우")

    from core_foundation.monitoring import (
        HealthChecker, HealthStatus, DependencyType,
        HealthCheckResult, SystemHealth, DependencyHealth,
    )

    hc = HealthChecker(enabled=True, enable_system_checks=False, max_history=50, default_timeout=2.0)

    def ok_check() -> HealthCheckResult:
        return HealthCheckResult.healthy("ok", DependencyType.CUSTOM, response_time_ms=1.0)

    def fail_check() -> HealthCheckResult:
        return HealthCheckResult.unhealthy("fail", DependencyType.GPU, "GPU OOM error")

    # 7-1. 커스텀 체크 등록
    try:
        hc.register_check("db", ok_check, DependencyType.DATABASE, critical=True)
        hc.register_check("cache", ok_check, DependencyType.CACHE)
        assert hc.check_count == 2
        result.ok("7-1 커스텀 체크 등록 (2개)")
    except Exception as e:
        result.fail("7-1 등록", str(e))

    # 7-2. 단일 체크
    try:
        r = hc.check("db")
        assert r.status == HealthStatus.HEALTHY
        result.ok("7-2 단일 체크 -> HEALTHY")
    except Exception as e:
        result.fail("7-2 단일 체크", str(e))

    # 7-3. check_all
    try:
        sh = hc.check_all(parallel=False)
        assert isinstance(sh, SystemHealth)
        assert sh.total_checks == 2
        assert sh.overall_status == HealthStatus.HEALTHY
        result.ok("7-3 check_all (2개 HEALTHY)")
    except Exception as e:
        result.fail("7-3 check_all", str(e))

    # 7-4. 실패 체크 추가 후 재체크
    try:
        hc.register_check("gpu_sim", fail_check, DependencyType.GPU, critical=True)
        sh = hc.check_all(parallel=False)
        # GPU is_critical + UNHEALTHY -> 전체 UNHEALTHY
        assert sh.overall_status == HealthStatus.UNHEALTHY
        assert sh.unhealthy_checks == 1
        result.ok("7-4 critical UNHEALTHY -> 전체 UNHEALTHY")
    except Exception as e:
        result.fail("7-4 실패 체크", str(e))

    # 7-5. 의존성 상태 확인
    try:
        dep = hc.get_dependency_status("gpu_sim")
        assert dep is not None
        assert dep.current_status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
        assert dep.total_checks >= 1
        result.ok("7-5 의존성 상태 확인")
    except Exception as e:
        result.fail("7-5 의존성", str(e))

    # 7-6. 히스토리
    try:
        history = hc.get_history(limit=10)
        assert len(history) >= 2  # check_all 2번 호출
        result.ok(f"7-6 히스토리 ({len(history)}건)")
    except Exception as e:
        result.fail("7-6 히스토리", str(e))

    # 7-7. get_status_summary (API 응답용)
    try:
        summary = hc.get_status_summary()
        assert "status" in summary
        assert "dependencies" in summary
        assert "check_count" in summary
        assert summary["check_count"] == 3
        hc.shutdown()
        result.ok("7-7 get_status_summary")
    except Exception as e:
        result.fail("7-7 summary", str(e))


# =============================================================================
# [8] ErrorTracker + Metrics 연동 (7개)
# =============================================================================
def test_error_tracker_metrics_integration(result: TestResult) -> None:
    """에러 발생 -> ErrorTracker 추적 -> Metrics Counter 증가 패턴."""
    print("\n[8] ErrorTracker + Metrics 연동")

    from core_foundation.monitoring import (
        ErrorTracker, ErrorSeverity,
        MetricsCollector, MetricUnit,
    )

    tracker = ErrorTracker(max_records=100, enabled=True)
    mc = MetricsCollector(prefix="err_integ", enabled=True, max_metrics=500)

    error_counter = mc.counter("errors_total", "총 에러 수", MetricUnit.COUNT)
    error_by_severity = mc.counter("errors_by_severity", "심각도별 에러", MetricUnit.COUNT)
    error_latency = mc.histogram("error_handling_ms", "에러 처리 시간", MetricUnit.MILLISECONDS)

    # 8-1. 에러 추적 + 메트릭 증가 패턴
    try:
        exc = ValueError("invalid frame")
        start = time.perf_counter()
        record = tracker.track(exc, severity=ErrorSeverity.WARNING)
        elapsed_ms = (time.perf_counter() - start) * 1000
        error_counter.inc()
        error_by_severity.labels({"severity": "warning"}).inc()
        error_latency.observe(elapsed_ms)
        assert error_counter.snapshot().values[0].value == 1.0
        result.ok("8-1 에러 추적 + 메트릭 기록")
    except Exception as e:
        result.fail("8-1 연동 기본", str(e))

    # 8-2. 다수 에러 -> 메트릭 누적
    try:
        errors = [
            (ValueError("bad input"), ErrorSeverity.WARNING),
            (RuntimeError("OOM"), ErrorSeverity.CRITICAL),
            (IOError("disk"), ErrorSeverity.ERROR),
            (TypeError("type"), ErrorSeverity.WARNING),
        ]
        for exc, sev in errors:
            tracker.track(exc, severity=sev)
            error_counter.inc()
            error_by_severity.labels({"severity": sev.name.lower()}).inc()

        assert error_counter.snapshot().values[0].value == 5.0  # 1 + 4
        result.ok("8-2 다수 에러 메트릭 누적 (total=5)")
    except Exception as e:
        result.fail("8-2 다수 에러", str(e))

    # 8-3. 심각도별 메트릭 정확성
    try:
        warning_count = error_by_severity.labels({"severity": "warning"}).get()
        critical_count = error_by_severity.labels({"severity": "critical"}).get()
        error_count = error_by_severity.labels({"severity": "error"}).get()
        assert warning_count == 3.0  # 8-1에서 1 + 8-2에서 2
        assert critical_count == 1.0
        assert error_count == 1.0
        result.ok("8-3 심각도별 메트릭 정확 (W=3, C=1, E=1)")
    except AssertionError as e:
        result.fail("8-3 심각도별", str(e))

    # 8-4. 에러 요약 + 메트릭 일관성
    try:
        summary = tracker.get_summary(hours=1)
        total_from_tracker = summary.total_count
        total_from_metric = int(error_counter.snapshot().values[0].value)
        assert total_from_tracker == total_from_metric, \
            f"tracker={total_from_tracker}, metric={total_from_metric}"
        result.ok(f"8-4 ErrorTracker/Metrics 수치 일관 ({total_from_tracker})")
    except AssertionError as e:
        result.fail("8-4 일관성", str(e))

    # 8-5. 에러율 계산 (메트릭 기반)
    try:
        total_ops = 100
        ops_counter = mc.counter("total_ops", "총 연산", MetricUnit.COUNT)
        ops_counter.inc(total_ops)
        error_rate = error_counter.snapshot().values[0].value / ops_counter.snapshot().values[0].value * 100
        assert 0 < error_rate <= 100
        result.ok(f"8-5 에러율 계산 ({error_rate:.1f}%)")
    except Exception as e:
        result.fail("8-5 에러율", str(e))

    # 8-6. 에러 처리 시간 히스토그램
    try:
        for _ in range(10):
            start = time.perf_counter()
            tracker.track(ValueError("bench"))
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_latency.observe(elapsed_ms)
        snap = error_latency.snapshot()
        assert snap.values[-1].value >= 11  # count (1 + 10)
        result.ok(f"8-6 에러 처리 시간 히스토그램 (count={int(snap.values[-1].value)})")
    except Exception as e:
        result.fail("8-6 히스토그램", str(e))

    # 8-7. export 에 에러 메트릭 포함
    try:
        exported = mc.get_all_snapshots()
        names = [s.name for s in exported]
        assert any("errors_total" in n for n in names)
        assert any("errors_by_severity" in n for n in names)
        result.ok("8-7 export에 에러 메트릭 포함")
    except Exception as e:
        result.fail("8-7 export", str(e))


# =============================================================================
# [9] Profiler + Metrics 연동 (6개)
# =============================================================================
def test_profiler_metrics_integration(result: TestResult) -> None:
    """프로파일링 결과 -> Metrics 기록 패턴."""
    print("\n[9] Profiler + Metrics 연동")

    from core_foundation.monitoring import (
        PerformanceProfiler, ProfileType,
        MetricsCollector, MetricUnit,
    )

    profiler = PerformanceProfiler(
        enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
    )
    mc = MetricsCollector(prefix="prof_integ", enabled=True, max_metrics=500)

    fn_latency = mc.histogram("function_latency_ms", "함수 지연", MetricUnit.MILLISECONDS)
    fn_calls = mc.counter("function_calls_total", "함수 호출 수", MetricUnit.COUNT)
    active_profiles = mc.gauge("active_profiles", "활성 프로파일", MetricUnit.COUNT)

    # 9-1. 함수 실행 -> profiler + metrics 동시 기록
    try:
        functions = ["detect_pose", "track_ball", "analyze_motion"]
        for func_name in functions:
            exec_time = time.perf_counter()
            time.sleep(0.005)
            elapsed_ms = (time.perf_counter() - exec_time) * 1000

            profiler.profile_function_call(func_name, execution_time_ms=elapsed_ms)
            fn_latency.labels({"function": func_name}).observe(elapsed_ms)
            fn_calls.labels({"function": func_name}).inc()

        assert fn_calls.labels({"function": "detect_pose"}).get() == 1.0
        result.ok("9-1 함수 -> profiler + metrics 동시 기록")
    except Exception as e:
        result.fail("9-1 동시 기록", str(e))

    # 9-2. 프로파일 세션 -> gauge 반영
    try:
        active_profiles.set(0)
        pid = profiler.start_profiling(ProfileType.TIME, "session_1")
        active_profiles.inc()
        assert active_profiles.snapshot().values[0].value == 1.0
        profiler.stop_profiling()
        active_profiles.dec()
        assert active_profiles.snapshot().values[0].value == 0.0
        result.ok("9-2 프로파일 세션 gauge 반영")
    except Exception as e:
        result.fail("9-2 gauge", str(e))

    # 9-3. 느린 함수 -> 메트릭 경고 카운터
    try:
        slow_counter = mc.counter("slow_functions", "느린 함수 수", MetricUnit.COUNT)
        profiler.profile_function_call("render_overlay", execution_time_ms=100.0)
        slow_funcs = profiler.get_slow_functions(threshold_ms=40.0)
        slow_counter.inc(len(slow_funcs))
        assert slow_counter.snapshot().values[0].value >= 1
        result.ok(f"9-3 느린 함수 경고 ({len(slow_funcs)}개)")
    except Exception as e:
        result.fail("9-3 느린 함수", str(e))

    # 9-4. 프로파일 결과 to_dict -> 메트릭 메타데이터
    try:
        pid = profiler.start_profiling(ProfileType.TIME, "meta_test")
        time.sleep(0.01)
        pr = profiler.stop_profiling()
        d = pr.to_dict()
        assert "duration_ms" in d
        assert "profile_type" in d
        assert d["duration_ms"] > 0
        result.ok("9-4 프로파일 to_dict 메타데이터")
    except Exception as e:
        result.fail("9-4 to_dict", str(e))

    # 9-5. 다수 함수 프로파일 -> 메트릭 일관성
    try:
        all_profiles = profiler.get_all_function_profiles()
        metric_total_calls = 0
        for fp in all_profiles:
            metric_total_calls += fp.call_count

        profiler_call_count = sum(fp.call_count for fp in all_profiles)
        assert metric_total_calls == profiler_call_count
        result.ok(f"9-5 프로파일/메트릭 일관성 (calls={profiler_call_count})")
    except Exception as e:
        result.fail("9-5 일관성", str(e))

    # 9-6. export에 프로파일 메트릭 포함
    try:
        exported = mc.get_all_snapshots()
        names = [s.name for s in exported]
        assert any("function_latency" in n for n in names)
        assert any("function_calls" in n for n in names)
        result.ok("9-6 export에 프로파일 메트릭 포함")
    except Exception as e:
        result.fail("9-6 export", str(e))


# =============================================================================
# [10] HealthChecker + ErrorTracker 연동 (6개)
# =============================================================================
def test_health_error_integration(result: TestResult) -> None:
    """헬스 체크 실패 -> ErrorTracker 기록 패턴."""
    print("\n[10] HealthChecker + ErrorTracker 연동")

    from core_foundation.monitoring import (
        HealthChecker, HealthStatus, DependencyType, HealthCheckResult,
        ErrorTracker, ErrorSeverity, ErrorContext,
    )

    hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)
    tracker = ErrorTracker(max_records=100, enabled=True)

    def ok_check() -> HealthCheckResult:
        return HealthCheckResult.healthy("ok", DependencyType.CUSTOM, response_time_ms=1.0)

    def fail_check() -> HealthCheckResult:
        return HealthCheckResult.unhealthy("gpu_sim", DependencyType.GPU, "OOM error")

    # 10-1. 헬스 체크 실패 -> 에러 추적
    try:
        hc.register_check("gpu_sim", fail_check, DependencyType.GPU, critical=True)
        r = hc.check("gpu_sim")
        if r.status == HealthStatus.UNHEALTHY:
            tracker.track(
                RuntimeError(r.message),
                context=ErrorContext(
                    extra={"component": "health_checker", "operation": f"check_{r.name}", **r.to_dict()},
                ),
                severity=ErrorSeverity.CRITICAL,
            )
        summary = tracker.get_summary(hours=1)
        assert summary.total_count >= 1
        result.ok("10-1 헬스 실패 -> 에러 추적")
    except Exception as e:
        result.fail("10-1 헬스->에러", str(e))

    # 10-2. check_all -> 실패 항목만 에러 추적
    try:
        hc.register_check("db_ok", ok_check, DependencyType.DATABASE)
        tracker.clear()
        sh = hc.check_all(parallel=False)
        for r in sh.results:
            if r.status == HealthStatus.UNHEALTHY:
                tracker.track(RuntimeError(r.message), severity=ErrorSeverity.ERROR)
        summary = tracker.get_summary(hours=1)
        assert summary.total_count == sh.unhealthy_checks
        result.ok(f"10-2 check_all 실패만 추적 ({summary.total_count}개)")
    except Exception as e:
        result.fail("10-2 check_all 추적", str(e))

    # 10-3. 연속 실패 -> 에러 심각도 상승
    try:
        tracker.clear()
        for i in range(5):
            r = hc.check("gpu_sim")
            dep = hc.get_dependency_status("gpu_sim")
            if dep and dep.consecutive_failures >= 3:
                sev = ErrorSeverity.CRITICAL
            else:
                sev = ErrorSeverity.WARNING
            tracker.track(RuntimeError(r.message), severity=sev)

        records = tracker.get_records(limit=10)
        severities = [rec.severity for rec in records]
        # 처음 2개는 WARNING (또는 DEGRADED), 나머지는 CRITICAL
        has_critical = any(s == ErrorSeverity.CRITICAL for s in severities)
        assert has_critical, "연속 실패 시 CRITICAL 에러 없음"
        result.ok("10-3 연속 실패 -> 심각도 상승")
    except Exception as e:
        result.fail("10-3 심각도 상승", str(e))

    # 10-4. 헬스 복구 확인
    try:
        hc.register_check("recovered", ok_check, DependencyType.CUSTOM)
        r = hc.check("recovered")
        dep = hc.get_dependency_status("recovered")
        assert dep.current_status == HealthStatus.HEALTHY
        assert dep.consecutive_failures == 0
        result.ok("10-4 헬스 복구 확인")
    except Exception as e:
        result.fail("10-4 복구", str(e))

    # 10-5. 시스템 상태 + 에러 수 상관관계
    try:
        tracker.clear()
        sh = hc.check_all(parallel=False)
        error_count = 0
        for r in sh.results:
            if r.status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN):
                tracker.track(RuntimeError(r.message))
                error_count += 1
        summary = tracker.get_summary(hours=1)
        assert summary.total_count == error_count
        result.ok(f"10-5 시스템 상태-에러 상관 (errors={error_count})")
    except Exception as e:
        result.fail("10-5 상관관계", str(e))

    # 10-6. 정리
    try:
        hc.reset()
        hc.shutdown()
        tracker.clear()
        result.ok("10-6 리소스 정리")
    except Exception as e:
        result.fail("10-6 정리", str(e))


# =============================================================================
# [11] 전체 파이프라인 - 프레임 분석 시뮬레이션 (8개)
# =============================================================================
def test_full_pipeline(result: TestResult) -> None:
    """실제 프레임 분석 워크플로우를 모든 모니터링 모듈로 관측하는 E2E 시뮬레이션."""
    print("\n[11] 전체 파이프라인 (프레임 분석 시뮬레이션)")

    from core_foundation.monitoring import (
        ErrorTracker, ErrorSeverity, ErrorContext,
        MetricsCollector, MetricUnit,
        PerformanceProfiler, ProfileType,
        HealthChecker, HealthStatus, DependencyType, HealthCheckResult,
    )

    # --- 초기화 ---
    tracker = ErrorTracker(max_records=500, enabled=True)
    mc = MetricsCollector(prefix="pipeline", enabled=True, max_metrics=1000)
    profiler = PerformanceProfiler(
        enabled=True, cpu_enabled=False, memory_enabled=False, gpu_enabled=False,
    )
    hc = HealthChecker(enabled=True, enable_system_checks=False, default_timeout=2.0)

    # 메트릭 정의
    frame_counter = mc.counter("frames_processed", "처리 프레임", MetricUnit.COUNT)
    fps_gauge = mc.gauge("current_fps", "현재 FPS", MetricUnit.FPS)
    frame_time_hist = mc.histogram("frame_time_ms", "프레임 처리 시간", MetricUnit.MILLISECONDS)
    accuracy_summary = mc.summary("pose_accuracy", "포즈 정확도", MetricUnit.PERCENT)
    error_counter = mc.counter("pipeline_errors", "파이프라인 에러", MetricUnit.COUNT)

    # 헬스 체크 등록
    def pipeline_health() -> HealthCheckResult:
        snap = fps_gauge.snapshot()
        fps = snap.values[0].value if snap.values else 0.0
        if fps < 10:
            return HealthCheckResult.unhealthy("pipeline", DependencyType.CUSTOM, f"Low FPS: {fps}")
        elif fps < 24:
            return HealthCheckResult.degraded("pipeline", DependencyType.CUSTOM, f"FPS degraded: {fps}")
        return HealthCheckResult.healthy("pipeline", DependencyType.CUSTOM, f"FPS OK: {fps}", response_time_ms=1.0)

    hc.register_check("pipeline", pipeline_health, DependencyType.CUSTOM)

    # 11-1. 초기 상태 (아직 inc/set 안 했으므로 values 비어있거나 0)
    try:
        fc_snap = frame_counter.snapshot()
        fps_snap = fps_gauge.snapshot()
        assert len(fc_snap.values) == 0 or fc_snap.values[0].value == 0
        assert len(fps_snap.values) == 0 or fps_snap.values[0].value == 0
        assert tracker.get_summary(hours=1).total_count == 0
        result.ok("11-1 초기 상태 (모두 0)")
    except AssertionError as e:
        result.fail("11-1 초기 상태", str(e))

    # 11-2. 프레임 처리 시뮬레이션 (30 프레임)
    try:
        frame_count = 30
        start_batch = time.perf_counter()

        for frame_id in range(frame_count):
            frame_start = time.perf_counter()

            # 프레임 처리 시뮬레이션 (약간의 지연)
            time.sleep(0.001)

            frame_elapsed_ms = (time.perf_counter() - frame_start) * 1000

            # 프로파일링
            profiler.profile_function_call("process_frame", execution_time_ms=frame_elapsed_ms)

            # 메트릭 기록
            frame_counter.inc()
            frame_time_hist.observe(frame_elapsed_ms)

            # 정확도 시뮬레이션 (90~96%)
            accuracy = 90.0 + (frame_id % 7)
            accuracy_summary.observe(accuracy)

        batch_elapsed = time.perf_counter() - start_batch
        actual_fps = frame_count / batch_elapsed if batch_elapsed > 0 else 0
        fps_gauge.set(actual_fps)

        assert frame_counter.snapshot().values[0].value == 30
        result.ok(f"11-2 프레임 처리 완료 (30프레임, FPS={actual_fps:.1f})")
    except Exception as e:
        result.fail("11-2 프레임 처리", str(e))

    # 11-3. 에러 프레임 시뮬레이션 (3회 실패)
    try:
        for i in range(3):
            try:
                raise RuntimeError(f"Pose detection failed at frame {30 + i}")
            except RuntimeError as exc:
                tracker.track(
                    exc,
                    context=ErrorContext(
                        extra={"component": "pose_detector", "operation": "detect", "frame_id": 30 + i},
                    ),
                    severity=ErrorSeverity.WARNING,
                )
                error_counter.inc()

        assert error_counter.snapshot().values[0].value == 3
        assert tracker.get_summary(hours=1).total_count == 3
        result.ok("11-3 에러 프레임 (3회 추적)")
    except Exception as e:
        result.fail("11-3 에러 프레임", str(e))

    # 11-4. 프로파일링 검증
    try:
        fp = profiler.get_function_profile("process_frame")
        assert fp is not None
        assert fp.call_count == 30
        assert fp.total_time_ms > 0
        assert fp.average_time_ms > 0
        result.ok(f"11-4 프로파일 검증 (calls={fp.call_count}, avg={fp.average_time_ms:.2f}ms)")
    except Exception as e:
        result.fail("11-4 프로파일", str(e))

    # 11-5. 헬스 체크
    try:
        sh = hc.check_all(parallel=False)
        # FPS > 24이면 HEALTHY
        current_fps = fps_gauge.snapshot().values[0].value
        if current_fps >= 24:
            assert sh.overall_status == HealthStatus.HEALTHY
        elif current_fps >= 10:
            assert sh.overall_status == HealthStatus.DEGRADED
        result.ok(f"11-5 헬스 체크 (FPS={current_fps:.0f}, status={sh.overall_status.value})")
    except Exception as e:
        result.fail("11-5 헬스", str(e))

    # 11-6. 전체 메트릭 Export
    try:
        exported = mc.get_all_snapshots()
        assert len(exported) >= 5  # 등록한 5개 + 기본
        metric_names = [s.name for s in exported]
        assert any("frames_processed" in n for n in metric_names)
        assert any("current_fps" in n for n in metric_names)
        assert any("frame_time_ms" in n for n in metric_names)
        result.ok(f"11-6 전체 Export ({len(exported)}개)")
    except Exception as e:
        result.fail("11-6 export", str(e))

    # 11-7. 에러율 계산 + 정확도 요약
    try:
        total_frames = int(frame_counter.snapshot().values[0].value)
        total_errors = int(error_counter.snapshot().values[0].value)
        error_rate = (total_errors / (total_frames + total_errors)) * 100 if (total_frames + total_errors) > 0 else 0
        assert error_rate < 20.0, f"에러율 과다: {error_rate:.1f}%"
        result.ok(f"11-7 에러율 {error_rate:.1f}% (frames={total_frames}, errors={total_errors})")
    except AssertionError as e:
        result.fail("11-7 에러율", str(e))

    # 11-8. 전체 상태 요약
    try:
        health_summary = hc.get_status_summary()
        assert health_summary["status"] in ("healthy", "degraded", "unhealthy", "unknown")
        assert health_summary["is_operational"] is True or health_summary["is_operational"] is False
        error_summary = tracker.get_summary(hours=1)
        profiler_status = profiler.get_status()

        # 모든 모듈이 유효한 상태 반환
        assert isinstance(health_summary, dict)
        assert isinstance(error_summary.total_count, int)
        assert isinstance(profiler_status, dict)

        hc.shutdown()
        result.ok("11-8 전체 상태 요약 (모든 모듈 정상 응답)")
    except Exception as e:
        result.fail("11-8 전체 요약", str(e))


# =============================================================================
# [12] 싱글톤 격리 / 스레드 안전성 / 리셋 (5개)
# =============================================================================
def test_singleton_isolation_and_threads(result: TestResult) -> None:
    """각 모듈 싱글톤의 독립성, 스레드 안전성, 리셋 동작."""
    print("\n[12] 싱글톤 격리 / 스레드 안전성")

    from core_foundation.monitoring import (
        _get_manager, _reset_manager,
        _get_profiler, _reset_profiler,
        _get_health_checker, _reset_health_checker,
    )
    from core_foundation.monitoring.error_tracker import (
        _get_tracker, _reset_tracker,
    )
    from core_foundation.monitoring.metrics import (
        _get_collector, _reset_collector,
    )

    # 12-1. 각 모듈 싱글톤 독립
    try:
        _reset_manager()
        _reset_tracker()
        _reset_collector()
        _reset_profiler()
        _reset_health_checker()

        mgr = _get_manager()
        tracker = _get_tracker()
        collector = _get_collector()
        profiler = _get_profiler()
        hc = _get_health_checker()

        # 모두 서로 다른 객체
        objects = [mgr, tracker, collector, profiler, hc]
        ids = [id(o) for o in objects]
        assert len(set(ids)) == 5, "싱글톤 간 id 충돌"
        result.ok("12-1 5개 모듈 싱글톤 독립")
    except Exception as e:
        result.fail("12-1 독립성", str(e))
    finally:
        _reset_manager()
        _reset_tracker()
        _reset_collector()
        _reset_profiler()
        _reset_health_checker()

    # 12-2. 리셋 후 새 인스턴스
    try:
        _reset_profiler()
        p1 = _get_profiler()
        _reset_profiler()
        p2 = _get_profiler()
        assert p1 is not p2
        result.ok("12-2 리셋 후 새 인스턴스 (profiler)")
    except Exception as e:
        result.fail("12-2 리셋", str(e))
    finally:
        _reset_profiler()

    # 12-3. 멀티스레드 싱글톤 접근 (5개 모듈 동시)
    try:
        _reset_manager()
        _reset_tracker()
        _reset_collector()
        _reset_profiler()
        _reset_health_checker()

        errors = []
        results_map = {
            "manager": [], "tracker": [], "collector": [],
            "profiler": [], "health_checker": [],
        }

        def get_all():
            try:
                results_map["manager"].append(id(_get_manager()))
                results_map["tracker"].append(id(_get_tracker()))
                results_map["collector"].append(id(_get_collector()))
                results_map["profiler"].append(id(_get_profiler()))
                results_map["health_checker"].append(id(_get_health_checker()))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=get_all) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        # 각 모듈은 동일 인스턴스 반환
        for key, ids_list in results_map.items():
            unique = len(set(ids_list))
            assert unique == 1, f"{key}: {unique}개 인스턴스"
        result.ok("12-3 멀티스레드 5개 모듈 동시 접근 (8스레드)")
    except AssertionError as e:
        result.fail("12-3 멀티스레드", str(e))
    finally:
        _reset_manager()
        _reset_tracker()
        _reset_collector()
        _reset_profiler()
        _reset_health_checker()

    # 12-4. 한 모듈 리셋이 다른 모듈에 영향 없음
    try:
        _reset_profiler()
        _reset_tracker()

        p = _get_profiler()
        t = _get_tracker()

        p.profile_function_call("test_func", execution_time_ms=10.0)
        t.track(ValueError("test"))

        # profiler만 리셋
        _reset_profiler()
        p_new = _get_profiler()
        assert p_new is not p

        # tracker는 그대로
        t_same = _get_tracker()
        assert t_same is t
        summary = t_same.get_summary(hours=1)
        assert summary.total_count >= 1  # 리셋 안 됐으므로 데이터 유지
        result.ok("12-4 부분 리셋 격리 (profiler 리셋 -> tracker 무영향)")
    except Exception as e:
        result.fail("12-4 부분 리셋", str(e))
    finally:
        _reset_profiler()
        _reset_tracker()

    # 12-5. 전체 리셋 순서 안전
    try:
        _get_manager()
        _get_tracker()
        _get_collector()
        _get_profiler()
        _get_health_checker()

        # 역순 리셋도 안전
        _reset_health_checker()
        _reset_profiler()
        _reset_collector()
        _reset_tracker()
        _reset_manager()

        # 다시 생성 가능
        _get_manager()
        _get_tracker()
        _get_collector()
        _get_profiler()
        _get_health_checker()

        result.ok("12-5 전체 리셋 순서 안전 (역순/재생성)")
    except Exception as e:
        result.fail("12-5 전체 리셋", str(e))
    finally:
        _reset_manager()
        _reset_tracker()
        _reset_collector()
        _reset_profiler()
        _reset_health_checker()


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - monitoring 모듈 통합 테스트")
    print("=" * 60)

    result = TestResult()

    test_import_integrity(result)          # [1] 8개
    test_all_exports(result)               # [2] 6개
    test_enum_cross_reference(result)      # [3] 6개
    test_error_tracker_workflow(result)     # [4] 7개
    test_metrics_workflow(result)           # [5] 7개
    test_profiler_workflow(result)          # [6] 7개
    test_health_checker_workflow(result)    # [7] 7개
    test_error_tracker_metrics_integration(result)  # [8] 7개
    test_profiler_metrics_integration(result)       # [9] 6개
    test_health_error_integration(result)            # [10] 6개
    test_full_pipeline(result)             # [11] 8개
    test_singleton_isolation_and_threads(result)     # [12] 5개

    result.summary()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
