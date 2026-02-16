# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/performance
파일: test_error_tracker_perf.py
설명: ErrorTracker 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [P1] ErrorSeverity 연산 성능 (3개)
    [P2] TrackingCategory.from_error_code 성능 (2개)
    [P3] ErrorContext 생성/직렬화 성능 (3개)
    [P4] ErrorRecord 생성/해시/직렬화 성능 (4개)
    [P5] ErrorTracker.track 처리량 (3개)
    [P6] ErrorTracker.get_summary / get_trend 성능 (3개)
    [P7] ErrorTracker.get_records / get_count 성능 (3개)
    [P8] 멀티스레드 동시 추적 성능 (3개)
    [P9] 메모리 사용량 (3개)

    총 27개 테스트
"""

import gc
import sys
import threading
import time
from dataclasses import fields
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.error_tracker import (
    MAX_ERROR_RECORDS,
    MAX_ERROR_HASHES,
    AGGREGATION_WINDOW_SIZE,
    ErrorSeverity,
    TrackingCategory,
    ErrorContext,
    ErrorRecord,
    ErrorSummary,
    ErrorTrend,
    ErrorTracker,
    _get_tracker,
    _reset_tracker,
)

from shared.constants.error_codes import ErrorCode, ErrorCategory
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
    CriticalException,
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
    """연산 속도 측정 (ops/sec 반환)."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


def measure_time_ms(func, iterations: int = 100) -> float:
    """평균 실행 시간 측정 (ms 반환)."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000


def get_object_size(obj) -> int:
    """객체 크기 추정 (bytes)."""
    return sys.getsizeof(obj)


def reset_tracker():
    """ErrorTracker 싱글톤 리셋."""
    _reset_tracker()


# =============================================================================
# [P1] ErrorSeverity 연산 성능
# =============================================================================
def test_severity_performance(result: PerformanceTestResult) -> None:
    """ErrorSeverity 연산 성능."""
    print("\n[P1] ErrorSeverity 연산 성능")

    # P1-1. from_logging_level 속도
    try:
        iters = 100000
        ops = measure_ops(lambda: ErrorSeverity.from_logging_level(30), iters)
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-1: from_logging_level", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-1: from_logging_level", str(e))

    # P1-2. from_exception 속도
    try:
        exc = CriticalException(ErrorCode.INTERNAL_ERROR, "test")
        iters = 100000
        ops = measure_ops(lambda: ErrorSeverity.from_exception(exc), iters)
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-2: from_exception", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-2: from_exception", str(e))

    # P1-3. __lt__ / __le__ 비교 속도
    try:
        a = ErrorSeverity.DEBUG
        b = ErrorSeverity.CRITICAL
        iters = 200000
        ops = measure_ops(lambda: a < b, iters)
        assert ops > 500000, f"느림: {ops:.0f} ops/sec"
        result.ok("P1-3: __lt__ 비교", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-3: 비교 연산", str(e))


# =============================================================================
# [P2] TrackingCategory.from_error_code 성능
# =============================================================================
def test_tracking_category_performance(result: PerformanceTestResult) -> None:
    """TrackingCategory.from_error_code 성능."""
    print("\n[P2] TrackingCategory.from_error_code 성능")

    # P2-1. 빈번한 에러 코드 조회 속도
    try:
        codes = [
            ErrorCode.UNKNOWN_ERROR,       # 1xxx
            ErrorCode.VALIDATION_ERROR,    # 3xxx
            ErrorCode.DATABASE_ERROR,      # 5xxx
            ErrorCode.ANALYSIS_ERROR,      # 7xxx
            ErrorCode.REFEREE_ERROR,       # 8xxx
            ErrorCode.CONFIGURATION_ERROR, # 9xxx
        ]
        iters = 50000

        def lookup_all():
            for c in codes:
                TrackingCategory.from_error_code(c)

        ops = measure_ops(lookup_all, iters)
        total_ops = ops * len(codes)
        assert total_ops > 100000, f"느림: {total_ops:.0f} ops/sec"
        result.ok("P2-1: from_error_code (6개 코드)", f"{total_ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-1: from_error_code", str(e))

    # P2-2. 7xxx 세분화 분기 속도
    try:
        codes_7xxx = [
            ErrorCode.ANALYSIS_ERROR,          # 7000 -> ANALYSIS
            ErrorCode.DETECTION_ERROR,         # 7200 -> DETECTION
            ErrorCode.POSE_ESTIMATION_ERROR,   # 7300 -> POSE
            ErrorCode.BIOMECHANICS_ERROR,      # 7400 -> BIOMECHANICS
            ErrorCode.MOTION_ANALYSIS_ERROR,   # 7500 -> MOTION
            ErrorCode.GAME_ANALYSIS_ERROR,     # 7600 -> GAME
            ErrorCode.MODEL_ERROR,             # 7700 -> MODEL
        ]
        iters = 50000

        def lookup_7xxx():
            for c in codes_7xxx:
                TrackingCategory.from_error_code(c)

        ops = measure_ops(lookup_7xxx, iters)
        total_ops = ops * len(codes_7xxx)
        assert total_ops > 100000, f"느림: {total_ops:.0f} ops/sec"
        result.ok("P2-2: from_error_code (7xxx 세분화)", f"{total_ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-2: 7xxx 세분화", str(e))


# =============================================================================
# [P3] ErrorContext 생성/직렬화 성능
# =============================================================================
def test_context_performance(result: PerformanceTestResult) -> None:
    """ErrorContext 생성/직렬화 성능."""
    print("\n[P3] ErrorContext 성능")

    # P3-1. 생성 속도
    try:
        iters = 100000
        ops = measure_ops(
            lambda: ErrorContext(
                request_id="req-001",
                user_id="user-001",
                endpoint="/api/analyze",
                method="POST",
            ),
            iters,
        )
        assert ops > 100000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-1: ErrorContext 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-1: 생성", str(e))

    # P3-2. to_dict 속도
    try:
        ctx = ErrorContext(
            request_id="req-001", user_id="user-001",
            endpoint="/api/analyze", extra={"key": "value"},
        )
        iters = 100000
        ops = measure_ops(lambda: ctx.to_dict(), iters)
        assert ops > 50000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-2: to_dict", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-2: to_dict", str(e))

    # P3-3. from_dict 속도
    try:
        data = {
            "request_id": "req-001",
            "user_id": "user-001",
            "endpoint": "/api/analyze",
            "extra": {"key": "value"},
            "unknown_field": "test",
        }
        iters = 50000
        ops = measure_ops(lambda: ErrorContext.from_dict(dict(data)), iters)
        assert ops > 30000, f"느림: {ops:.0f} ops/sec"
        result.ok("P3-3: from_dict", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-3: from_dict", str(e))


# =============================================================================
# [P4] ErrorRecord 생성/해시/직렬화 성능
# =============================================================================
def test_record_performance(result: PerformanceTestResult) -> None:
    """ErrorRecord 생성/해시/직렬화 성능."""
    print("\n[P4] ErrorRecord 성능")

    # P4-1. 생성 속도 (해시 포함)
    try:
        iters = 50000
        ops = measure_ops(
            lambda: ErrorRecord(
                exception_type="ValueError",
                error_name="VALIDATION_ERROR",
                message="검증 실패",
                severity=ErrorSeverity.ERROR,
                category=TrackingCategory.VALIDATION,
            ),
            iters,
        )
        assert ops > 10000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-1: ErrorRecord 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-1: 생성", str(e))

    # P4-2. _generate_hash 속도
    try:
        record = ErrorRecord(
            exception_type="ValueError",
            message="테스트",
            traceback='  File "test.py", line 10\n    raise ValueError()',
        )
        iters = 100000
        ops = measure_ops(lambda: record._generate_hash(), iters)
        assert ops > 50000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-2: _generate_hash", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-2: _generate_hash", str(e))

    # P4-3. to_dict 속도
    try:
        record = ErrorRecord(
            exception_type="ValueError",
            error_code=ErrorCode.VALIDATION_ERROR,
            error_name="VALIDATION_ERROR",
            message="검증 실패",
            severity=ErrorSeverity.ERROR,
            category=TrackingCategory.VALIDATION,
            context=ErrorContext(request_id="req-001"),
            tags=["test"],
        )
        iters = 50000
        ops = measure_ops(lambda: record.to_dict(), iters)
        assert ops > 20000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-3: to_dict", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-3: to_dict", str(e))

    # P4-4. from_exception 속도
    try:
        exc = CourtViewException(
            ErrorCode.ANALYSIS_ERROR, "분석 오류",
            details={"video_id": "v001"},
        )
        try:
            raise exc
        except CourtViewException:
            pass

        iters = 10000
        ops = measure_ops(
            lambda: ErrorRecord.from_exception(exc, tags=["perf"]),
            iters,
        )
        assert ops > 5000, f"느림: {ops:.0f} ops/sec"
        result.ok("P4-4: from_exception", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P4-4: from_exception", str(e))


# =============================================================================
# [P5] ErrorTracker.track 처리량
# =============================================================================
def test_tracker_track_performance(result: PerformanceTestResult) -> None:
    """ErrorTracker.track 처리량."""
    print("\n[P5] ErrorTracker.track 처리량")
    reset_tracker()

    # P5-1. 단일 스레드 track 처리량
    try:
        tracker = ErrorTracker(max_records=10000)
        records = [
            ErrorRecord(
                exception_type=f"Error{i % 10}",
                message=f"에러 {i}",
                severity=ErrorSeverity.ERROR,
            )
            for i in range(1000)
        ]

        start = time.perf_counter()
        for r in records:
            tracker.track(r)
        elapsed = time.perf_counter() - start

        ops = 1000 / elapsed
        avg_ms = (elapsed / 1000) * 1000
        assert ops > 5000, f"느림: {ops:.0f} ops/sec"
        result.ok("P5-1: track 처리량 (1K)", f"{ops:,.0f} ops/sec, {avg_ms:.3f}ms/op")
    except Exception as e:
        result.fail("P5-1: track 처리량", str(e))

    # P5-2. FIFO 오버플로우 성능 (maxlen 초과)
    try:
        tracker = ErrorTracker(max_records=100)
        records = [
            ErrorRecord(
                exception_type=f"Error{i % 50}",
                message=f"에러 {i}",
            )
            for i in range(500)
        ]

        start = time.perf_counter()
        for r in records:
            tracker.track(r)
        elapsed = time.perf_counter() - start

        ops = 500 / elapsed
        assert len(tracker._records) == 100
        assert ops > 3000, f"느림: {ops:.0f} ops/sec"
        result.ok("P5-2: FIFO 오버플로우 (500->100)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-2: FIFO 오버플로우", str(e))

    # P5-3. disabled 상태 track 속도
    try:
        tracker = ErrorTracker(max_records=10000, enabled=False)
        exc = ValueError("비활성")
        try:
            raise exc
        except ValueError:
            pass

        iters = 10000
        ops = measure_ops(
            lambda: tracker.track(exc),
            iters,
        )
        # disabled 상태에서도 from_exception() 호출 (traceback.format_exception 오버헤드)
        assert ops > 10000, f"느림: {ops:.0f} ops/sec"
        result.ok("P5-3: disabled track", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-3: disabled track", str(e))


# =============================================================================
# [P6] ErrorTracker.get_summary / get_trend 성능
# =============================================================================
def test_tracker_query_performance(result: PerformanceTestResult) -> None:
    """ErrorTracker 조회 성능."""
    print("\n[P6] ErrorTracker.get_summary / get_trend 성능")
    reset_tracker()

    # 데이터 준비 (1000개 에러)
    tracker = ErrorTracker(max_records=5000)
    now = datetime.now(timezone.utc)
    severities = list(ErrorSeverity)
    categories = [
        TrackingCategory.VALIDATION,
        TrackingCategory.GENERAL,
        TrackingCategory.ANALYSIS,
        TrackingCategory.INFRASTRUCTURE,
    ]

    for i in range(1000):
        record = ErrorRecord(
            exception_type=f"Error{i % 20}",
            error_name=f"ERR_{i % 20}",
            message=f"에러 메시지 {i}",
            severity=severities[i % len(severities)],
            category=categories[i % len(categories)],
            occurred_at=now - timedelta(minutes=i % 60),
        )
        tracker.track(record)

    # P6-1. get_summary 속도 (1000개 레코드)
    try:
        iters = 100
        avg_ms = measure_time_ms(lambda: tracker.get_summary(hours=1), iters)
        assert avg_ms < 100, f"느림: {avg_ms:.2f}ms"
        result.ok("P6-1: get_summary (1K 레코드)", f"{avg_ms:.2f}ms/call")
    except Exception as e:
        result.fail("P6-1: get_summary", str(e))

    # P6-2. get_trend 속도 (1000개 레코드)
    try:
        iters = 100
        avg_ms = measure_time_ms(lambda: tracker.get_trend(hours=1, slot_minutes=5), iters)
        assert avg_ms < 200, f"느림: {avg_ms:.2f}ms"
        result.ok("P6-2: get_trend (1K 레코드)", f"{avg_ms:.2f}ms/call")
    except Exception as e:
        result.fail("P6-2: get_trend", str(e))

    # P6-3. get_summary + category 필터 속도
    try:
        iters = 100
        avg_ms = measure_time_ms(
            lambda: tracker.get_summary(hours=1, category=TrackingCategory.VALIDATION),
            iters,
        )
        assert avg_ms < 100, f"느림: {avg_ms:.2f}ms"
        result.ok("P6-3: get_summary + category 필터", f"{avg_ms:.2f}ms/call")
    except Exception as e:
        result.fail("P6-3: get_summary 필터", str(e))


# =============================================================================
# [P7] ErrorTracker.get_records / get_count 성능
# =============================================================================
def test_tracker_records_performance(result: PerformanceTestResult) -> None:
    """ErrorTracker 레코드 조회 성능."""
    print("\n[P7] ErrorTracker.get_records / get_count 성능")
    reset_tracker()

    # 데이터 준비 (1000개)
    tracker = ErrorTracker(max_records=5000)
    now = datetime.now(timezone.utc)
    stored_ids = []
    stored_hashes = []

    for i in range(1000):
        record = ErrorRecord(
            exception_type=f"Error{i % 20}",
            message=f"에러 {i}",
            severity=ErrorSeverity.ERROR if i % 2 == 0 else ErrorSeverity.WARNING,
            category=TrackingCategory.VALIDATION if i < 500 else TrackingCategory.GENERAL,
            occurred_at=now - timedelta(minutes=i % 120),
        )
        tracker.track(record)
        stored_ids.append(record.id)
        stored_hashes.append(record.error_hash)

    # P7-1. get_records 속도 (정렬 + 필터)
    try:
        iters = 100
        avg_ms = measure_time_ms(
            lambda: tracker.get_records(limit=50, severity=ErrorSeverity.ERROR),
            iters,
        )
        assert avg_ms < 50, f"느림: {avg_ms:.2f}ms"
        result.ok("P7-1: get_records (필터+정렬)", f"{avg_ms:.2f}ms/call")
    except Exception as e:
        result.fail("P7-1: get_records", str(e))

    # P7-2. get_record_by_id 속도
    try:
        target_id = stored_ids[500]  # 중간 위치
        iters = 1000
        avg_ms = measure_time_ms(lambda: tracker.get_record_by_id(target_id), iters)
        assert avg_ms < 10, f"느림: {avg_ms:.2f}ms"
        result.ok("P7-2: get_record_by_id", f"{avg_ms:.3f}ms/call")
    except Exception as e:
        result.fail("P7-2: get_record_by_id", str(e))

    # P7-3. get_count 속도
    try:
        iters = 500
        avg_ms = measure_time_ms(
            lambda: tracker.get_count(severity=ErrorSeverity.ERROR),
            iters,
        )
        assert avg_ms < 20, f"느림: {avg_ms:.2f}ms"
        result.ok("P7-3: get_count (severity 필터)", f"{avg_ms:.3f}ms/call")
    except Exception as e:
        result.fail("P7-3: get_count", str(e))


# =============================================================================
# [P8] 멀티스레드 동시 추적 성능
# =============================================================================
def test_multithread_performance(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 추적 성능."""
    print("\n[P8] 멀티스레드 동시 추적 성능")
    reset_tracker()

    # P8-1. 4스레드 동시 track
    try:
        tracker = ErrorTracker(max_records=50000)
        per_thread = 500
        barrier = threading.Barrier(4)
        thread_times = []

        def track_many():
            barrier.wait()
            t_start = time.perf_counter()
            for i in range(per_thread):
                record = ErrorRecord(
                    exception_type=f"ThreadError{i % 10}",
                    message=f"스레드 에러 {i}",
                )
                tracker.track(record)
            t_end = time.perf_counter()
            thread_times.append(t_end - t_start)

        threads = [threading.Thread(target=track_many) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        total_elapsed = time.perf_counter() - start

        total_ops = 4 * per_thread
        ops = total_ops / total_elapsed
        assert len(tracker._records) == total_ops
        assert ops > 2000, f"느림: {ops:.0f} ops/sec"
        result.ok("P8-1: 4스레드 track (2K)", f"{ops:,.0f} ops/sec, {total_elapsed:.2f}s")
    except Exception as e:
        result.fail("P8-1: 4스레드 track", str(e))

    # P8-2. 4스레드 동시 get_summary
    try:
        tracker = ErrorTracker(max_records=5000)
        now = datetime.now(timezone.utc)
        for i in range(500):
            tracker.track(ErrorRecord(
                exception_type=f"Error{i}", message=f"msg {i}",
                occurred_at=now - timedelta(minutes=i % 60),
            ))

        barrier = threading.Barrier(4)
        summaries = []

        def get_summary_thread():
            barrier.wait()
            s = tracker.get_summary(hours=1)
            summaries.append(s.total_count)

        start = time.perf_counter()
        threads = [threading.Thread(target=get_summary_thread) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        elapsed = time.perf_counter() - start

        # 모든 스레드가 동일한 결과
        assert len(set(summaries)) == 1, f"불일치: {summaries}"
        ops = 4 / elapsed
        result.ok("P8-2: 4스레드 get_summary", f"{ops:,.1f} ops/sec, {elapsed:.3f}s")
    except Exception as e:
        result.fail("P8-2: 4스레드 get_summary", str(e))

    # P8-3. 읽기/쓰기 동시 수행
    try:
        tracker = ErrorTracker(max_records=10000)
        now = datetime.now(timezone.utc)
        # 초기 데이터
        for i in range(200):
            tracker.track(ErrorRecord(
                exception_type="InitError", message=f"init {i}",
                occurred_at=now - timedelta(minutes=i % 30),
            ))

        barrier = threading.Barrier(4)
        errors_occurred = []

        def writer():
            barrier.wait()
            for i in range(200):
                tracker.track(ErrorRecord(
                    exception_type=f"WriteError{i}", message=f"write {i}",
                ))

        def reader():
            barrier.wait()
            for _ in range(50):
                tracker.get_summary(hours=1)
                tracker.get_count()

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        # 데이터 무결성 확인
        assert len(tracker._records) == 600  # 200 + 200*2
        result.ok("P8-3: 읽기/쓰기 동시", f"데이터 무결성 확인, {elapsed:.2f}s")
    except Exception as e:
        result.fail("P8-3: 읽기/쓰기 동시", str(e))


# =============================================================================
# [P9] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 측정."""
    print("\n[P9] 메모리 사용량")
    reset_tracker()

    # P9-1. ErrorRecord 인스턴스 크기
    try:
        gc.collect()
        record = ErrorRecord(
            exception_type="ValueError",
            error_code=ErrorCode.VALIDATION_ERROR,
            error_name="VALIDATION_ERROR",
            message="검증 실패 메시지",
            severity=ErrorSeverity.ERROR,
            category=TrackingCategory.VALIDATION,
            context=ErrorContext(request_id="req-001"),
            tags=["test"],
        )
        size = get_object_size(record)
        assert size < 2048, f"너무 큼: {size} bytes"
        result.ok("P9-1: ErrorRecord 크기", f"{size} bytes")
    except Exception as e:
        result.fail("P9-1: ErrorRecord 크기", str(e))

    # P9-2. ErrorTracker 빈 인스턴스 크기
    try:
        gc.collect()
        tracker = ErrorTracker(max_records=10000)
        size = get_object_size(tracker)
        assert size < 1024, f"너무 큼: {size} bytes"
        result.ok("P9-2: ErrorTracker 빈 크기", f"{size} bytes")
    except Exception as e:
        result.fail("P9-2: ErrorTracker 크기", str(e))

    # P9-3. ErrorTracker 1000개 레코드 메모리
    try:
        gc.collect()
        before = sys.getsizeof([])
        tracker = ErrorTracker(max_records=5000)
        for i in range(1000):
            tracker.track(ErrorRecord(
                exception_type=f"Error{i % 10}",
                message=f"에러 {i}",
            ))

        # deque + hashes + counts + messages 전체 추정
        deque_size = sys.getsizeof(tracker._records)
        hashes_size = sys.getsizeof(tracker._error_hashes)
        counts_size = sys.getsizeof(tracker._error_counts)
        msgs_size = sys.getsizeof(tracker._error_messages)
        total = deque_size + hashes_size + counts_size + msgs_size

        # 1000개 레코드에 대해 1MB 미만이어야 함
        assert total < 1_000_000, f"너무 큼: {total} bytes"
        result.ok(
            "P9-3: 1K 레코드 메모리",
            f"deque={deque_size:,}B, hashes={hashes_size:,}B, "
            f"counts={counts_size:,}B, msgs={msgs_size:,}B, "
            f"합계={total:,}B"
        )
    except Exception as e:
        result.fail("P9-3: 1K 레코드 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("ErrorTracker 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    test_severity_performance(result)
    test_tracking_category_performance(result)
    test_context_performance(result)
    test_record_performance(result)
    test_tracker_track_performance(result)
    test_tracker_query_performance(result)
    test_tracker_records_performance(result)
    test_multithread_performance(result)
    test_memory_usage(result)

    result.summary()


if __name__ == "__main__":
    main()
