# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/performance
파일: test_logger_perf.py
설명: LogManager(Loguru 기반) 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [1] LogLevel Enum 연산 성능 (4개)
    [2] SensitiveDataFilter 마스킹 성능 (5개)
    [3] LoggingConfig / SinkConfig 생성 성능 (4개)
    [4] LogManager 초기화 성능 (4개)
    [5] get_logger 처리량 (4개)
    [6] set_level 처리량 (3개)
    [7] get_status 처리량 (3개)
    [8] 멀티스레드 동시 접근 (4개)
    [9] 메모리 사용량 (4개)
"""

import logging
import os
import sys
import tempfile
import threading
import time
import tracemalloc
from copy import deepcopy
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.logger import (
    # 상수
    LOGURU_AVAILABLE,
    DEFAULT_SENSITIVE_PATTERNS,
    MASK_VALUE,
    # Enum
    LogLevel,
    # 데이터 클래스
    SinkConfig,
    LoggingConfig,
    # 필터
    SensitiveDataFilter,
    _analysis_filter,
    _performance_filter,
    _error_filter,
    # 메인 클래스
    LogManager,
    # 헬퍼
    setup_logging,
    get_logger,
    log_analysis,
    log_performance,
    _get_manager,
    _reset_manager,
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
# 헬퍼: LogManager 리셋
# =============================================================================
def reset_logging():
    """LogManager 싱글톤 리셋 및 logging 핸들러 정리."""
    from core_foundation.monitoring.logger import InterceptHandler
    _reset_manager()
    root = logging.root
    root.handlers = [h for h in root.handlers if not isinstance(h, InterceptHandler)]
    if not root.handlers:
        root.setLevel(logging.WARNING)


# =============================================================================
# [1] LogLevel Enum 연산 성능
# =============================================================================
def test_log_level_performance(result: PerformanceTestResult) -> None:
    """LogLevel Enum 연산 성능."""
    print("\n[1] LogLevel Enum 연산 성능")

    # 1-1. from_string 처리량
    try:
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE", "SUCCESS"]
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for lv in levels:
                LogLevel.from_string(lv)
        elapsed = time.perf_counter() - start
        ops = (iterations * len(levels)) / elapsed
        per_call = (elapsed / (iterations * len(levels))) * 1_000_000  # us
        result.ok(
            "1-1: from_string 처리량",
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("1-1: from_string", str(e))

    # 1-2. to_stdlib_level 처리량
    try:
        all_levels = list(LogLevel)
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for lv in all_levels:
                lv.to_stdlib_level()
        elapsed = time.perf_counter() - start
        ops = (iterations * len(all_levels)) / elapsed
        per_call = (elapsed / (iterations * len(all_levels))) * 1_000_000
        result.ok(
            "1-2: to_stdlib_level 처리량",
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("1-2: to_stdlib_level", str(e))

    # 1-3. from_string 잘못된 값 (폴백)
    try:
        bad_values = ["unknown", "", "VERBOSE", "NONE", "ALL"]
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for bv in bad_values:
                LogLevel.from_string(bv)
        elapsed = time.perf_counter() - start
        ops = (iterations * len(bad_values)) / elapsed
        result.ok(
            "1-3: from_string 폴백 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("1-3: from_string 폴백", str(e))

    # 1-4. Enum 비교 성능
    try:
        a = LogLevel.DEBUG
        b = LogLevel.INFO
        iterations = 500_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = a == b
            _ = a == LogLevel.DEBUG
            _ = b != LogLevel.ERROR
        elapsed = time.perf_counter() - start
        ops = (iterations * 3) / elapsed
        result.ok(
            "1-4: Enum 비교 성능",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("1-4: Enum 비교", str(e))


# =============================================================================
# [2] SensitiveDataFilter 마스킹 성능
# =============================================================================
def test_sensitive_filter_performance(result: PerformanceTestResult) -> None:
    """SensitiveDataFilter 마스킹 성능."""
    print("\n[2] SensitiveDataFilter 마스킹 성능")

    # 2-1. mask_string (key=value)
    try:
        f = SensitiveDataFilter()
        text = "login: password=secret123 token=abc456 api_key=xyz789"
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            f.mask_string(text)
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "2-1: mask_string 처리량 (3 패턴)",
            f"{ops:,.0f} ops/sec, {per_call_us:.1f}us/call",
        )
    except Exception as e:
        result.fail("2-1: mask_string", str(e))

    # 2-2. mask_string 민감 정보 없는 텍스트
    try:
        f = SensitiveDataFilter()
        text = "normal log message: user logged in at 2024-01-01 12:00:00"
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            f.mask_string(text)
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        result.ok(
            "2-2: mask_string (패턴 없음) 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("2-2: mask_string 패턴 없음", str(e))

    # 2-3. __call__ 필터 레코드 처리
    try:
        f = SensitiveDataFilter()
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            record = {"message": "password=test123 secret=abc"}
            f(record)
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        result.ok(
            "2-3: __call__ 필터 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("2-3: __call__", str(e))

    # 2-4. SensitiveDataFilter 생성 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            SensitiveDataFilter()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "2-4: SensitiveDataFilter 생성 성능",
            f"{ops:,.0f} ops/sec, {per_call_us:.1f}us/call",
        )
    except Exception as e:
        result.fail("2-4: 생성", str(e))

    # 2-5. _analysis_filter / _performance_filter / _error_filter
    try:
        analysis_rec = {"extra": {"log_type": "analysis"}}
        perf_rec = {"extra": {"log_type": "performance"}}

        class _Lvl:
            def __init__(self, no):
                self.no = no

        error_rec = {"level": _Lvl(40)}
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _analysis_filter(analysis_rec)
            _performance_filter(perf_rec)
            _error_filter(error_rec)
        elapsed = time.perf_counter() - start
        ops = (iterations * 3) / elapsed
        result.ok(
            "2-5: 필터 함수 3종 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("2-5: 필터 함수", str(e))


# =============================================================================
# [3] LoggingConfig / SinkConfig 생성 성능
# =============================================================================
def test_config_creation_performance(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능."""
    print("\n[3] LoggingConfig / SinkConfig 생성 성능")

    # 3-1. LoggingConfig 기본 생성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            LoggingConfig()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "3-1: LoggingConfig() 생성",
            f"{ops:,.0f} ops/sec, {per_call_us:.1f}us/call",
        )
    except Exception as e:
        result.fail("3-1: LoggingConfig 생성", str(e))

    # 3-2. SinkConfig 기본 생성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            SinkConfig()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "3-2: SinkConfig() 생성",
            f"{ops:,.0f} ops/sec, {per_call_us:.1f}us/call",
        )
    except Exception as e:
        result.fail("3-2: SinkConfig 생성", str(e))

    # 3-3. LoggingConfig 커스텀 필드 생성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            LoggingConfig(
                level="DEBUG",
                log_dir="/tmp/test",
                console_enabled=False,
                json_format=True,
                module_levels={"a": "DEBUG", "b": "WARNING"},
            )
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        result.ok(
            "3-3: LoggingConfig 커스텀 생성",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("3-3: LoggingConfig 커스텀", str(e))

    # 3-4. SinkConfig with filter_func
    try:
        def dummy_filter(record):
            return True

        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            SinkConfig(
                name="perf_test",
                path="/tmp/test.log",
                level="ERROR",
                filter_func=dummy_filter,
            )
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        result.ok(
            "3-4: SinkConfig 커스텀 생성",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("3-4: SinkConfig 커스텀", str(e))


# =============================================================================
# [4] LogManager 초기화 성능
# =============================================================================
def test_log_manager_init_performance(result: PerformanceTestResult) -> None:
    """LogManager 초기화 성능."""
    print("\n[4] LogManager 초기화 성능")

    # 4-1. LogManager() 객체 생성 (setup 미호출)
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            LogManager()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "4-1: LogManager() 생성 (setup 미호출)",
            f"{ops:,.0f} ops/sec, {per_call_us:.1f}us/call",
        )
    except Exception as e:
        result.fail("4-1: LogManager 생성", str(e))

    # 4-2. LogManager.setup() (최소 구성)
    try:
        times = []
        for _ in range(20):
            reset_logging()
            with tempfile.TemporaryDirectory() as tmpdir:
                cfg = LoggingConfig(
                    log_dir=tmpdir,
                    console_enabled=False,
                    file_enabled=False,
                    error_file_enabled=False,
                    analysis_file_enabled=False,
                    performance_file_enabled=False,
                    intercept_stdlib=False,
                    sensitive_masking=False,
                )
                m = LogManager(config=cfg)
                start = time.perf_counter()
                m.setup()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                m.shutdown()
        avg = sum(times) / len(times)
        result.ok(
            "4-2: setup() 최소 구성 (20회 평균)",
            f"{avg:.2f}ms/call",
        )
    except Exception as e:
        result.fail("4-2: setup 최소", str(e))

    # 4-3. LogManager.setup() (전체 구성)
    try:
        times = []
        for _ in range(10):
            reset_logging()
            with tempfile.TemporaryDirectory() as tmpdir:
                cfg = LoggingConfig(log_dir=tmpdir)
                m = LogManager(config=cfg)
                start = time.perf_counter()
                m.setup()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                m.shutdown()
        avg = sum(times) / len(times)
        result.ok(
            "4-3: setup() 전체 구성 (10회 평균)",
            f"{avg:.2f}ms/call",
        )
    except Exception as e:
        result.fail("4-3: setup 전체", str(e))

    # 4-4. LogManager.shutdown() 성능
    try:
        times = []
        for _ in range(20):
            reset_logging()
            with tempfile.TemporaryDirectory() as tmpdir:
                cfg = LoggingConfig(
                    log_dir=tmpdir,
                    console_enabled=False,
                    file_enabled=False,
                    error_file_enabled=False,
                    analysis_file_enabled=False,
                    performance_file_enabled=False,
                )
                m = LogManager(config=cfg)
                m.setup()
                start = time.perf_counter()
                m.shutdown()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
        avg = sum(times) / len(times)
        result.ok(
            "4-4: shutdown() (20회 평균)",
            f"{avg:.2f}ms/call",
        )
    except Exception as e:
        result.fail("4-4: shutdown", str(e))


# =============================================================================
# [5] get_logger 처리량
# =============================================================================
def test_get_logger_performance(result: PerformanceTestResult) -> None:
    """get_logger 처리량 테스트."""
    print("\n[5] get_logger 처리량")

    # 5-1. LogManager.get_logger() (이름 없음)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            iterations = 100_000
            start = time.perf_counter()
            for _ in range(iterations):
                m.get_logger()
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            per_call_us = (elapsed / iterations) * 1_000_000
            m.shutdown()
        result.ok(
            "5-1: get_logger() 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("5-1: get_logger()", str(e))

    # 5-2. LogManager.get_logger(name) (이름 바인딩)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            iterations = 100_000
            start = time.perf_counter()
            for _ in range(iterations):
                m.get_logger("motion_analysis.shooting")
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            per_call_us = (elapsed / iterations) * 1_000_000
            m.shutdown()
        result.ok(
            "5-2: get_logger(name) 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("5-2: get_logger(name)", str(e))

    # 5-3. 헬퍼 get_logger 처리량
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)

            iterations = 50_000
            start = time.perf_counter()
            for _ in range(iterations):
                get_logger("test_module")
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            _reset_manager()
        result.ok(
            "5-3: 헬퍼 get_logger() 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("5-3: 헬퍼 get_logger", str(e))

    # 5-4. 다양한 이름으로 get_logger
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            names = [f"module_{i}" for i in range(100)]
            iterations = 10_000
            start = time.perf_counter()
            for _ in range(iterations):
                for name in names:
                    m.get_logger(name)
            elapsed = time.perf_counter() - start
            ops = (iterations * len(names)) / elapsed
            m.shutdown()
        result.ok(
            "5-4: get_logger 100개 이름 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("5-4: 100개 이름", str(e))


# =============================================================================
# [6] set_level 처리량
# =============================================================================
def test_set_level_performance(result: PerformanceTestResult) -> None:
    """set_level 처리량 테스트."""
    print("\n[6] set_level 처리량")

    # 6-1. set_level 전체 레벨 변경
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            iterations = 50_000
            start = time.perf_counter()
            for i in range(iterations):
                m.set_level(levels[i % len(levels)])
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            per_call_us = (elapsed / iterations) * 1_000_000
            m.shutdown()
        result.ok(
            "6-1: set_level 전체 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("6-1: set_level 전체", str(e))

    # 6-2. set_level 모듈별
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            modules = [f"module_{i}" for i in range(10)]
            levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            iterations = 20_000
            start = time.perf_counter()
            for i in range(iterations):
                m.set_level(levels[i % len(levels)], module=modules[i % len(modules)])
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            m.shutdown()
        result.ok(
            "6-2: set_level 모듈별 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("6-2: set_level 모듈별", str(e))

    # 6-3. set_level + get_status 연쇄
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            iterations = 20_000
            start = time.perf_counter()
            for i in range(iterations):
                m.set_level("DEBUG" if i % 2 == 0 else "ERROR")
                m.get_status()
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            m.shutdown()
        result.ok(
            "6-3: set_level+get_status 연쇄 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("6-3: 연쇄", str(e))


# =============================================================================
# [7] get_status 처리량
# =============================================================================
def test_get_status_performance(result: PerformanceTestResult) -> None:
    """get_status 처리량 테스트."""
    print("\n[7] get_status 처리량")

    # 7-1. 기본 get_status
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            iterations = 100_000
            start = time.perf_counter()
            for _ in range(iterations):
                m.get_status()
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            per_call_us = (elapsed / iterations) * 1_000_000
            m.shutdown()
        result.ok(
            "7-1: get_status() 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("7-1: get_status", str(e))

    # 7-2. get_status 전체 싱크 구성
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()

            iterations = 50_000
            start = time.perf_counter()
            for _ in range(iterations):
                m.get_status()
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            m.shutdown()
        result.ok(
            "7-2: get_status 전체 구성 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("7-2: get_status 전체", str(e))

    # 7-3. get_status 미초기화
    try:
        reset_logging()
        m = LogManager()
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            m.get_status()
        elapsed = time.perf_counter() - start
        ops = iterations / elapsed
        result.ok(
            "7-3: get_status 미초기화 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("7-3: get_status 미초기화", str(e))


# =============================================================================
# [8] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_performance(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[8] 멀티스레드 동시 접근")

    # 8-1. _get_manager 동시 접근
    try:
        reset_logging()
        num_threads = 4
        iterations_per_thread = 50_000
        barrier = threading.Barrier(num_threads)
        results_list = []

        def worker():
            barrier.wait()
            start = time.perf_counter()
            for _ in range(iterations_per_thread):
                _get_manager()
            elapsed = time.perf_counter() - start
            results_list.append(elapsed)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        total_ops = num_threads * iterations_per_thread
        max_elapsed = max(results_list)
        ops = total_ops / max_elapsed
        result.ok(
            "8-1: _get_manager 4스레드 동시 접근",
            f"{ops:,.0f} ops/sec (total {total_ops:,} ops)",
        )
    except Exception as e:
        result.fail("8-1: _get_manager 멀티스레드", str(e))

    # 8-2. get_logger 동시 접근
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            num_threads = 4
            iterations_per_thread = 20_000
            barrier = threading.Barrier(num_threads)
            results_list = []

            def worker(tid):
                barrier.wait()
                start = time.perf_counter()
                for i in range(iterations_per_thread):
                    m.get_logger(f"thread_{tid}_module_{i % 10}")
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            total_ops = num_threads * iterations_per_thread
            max_elapsed = max(results_list)
            ops = total_ops / max_elapsed
            m.shutdown()
        result.ok(
            "8-2: get_logger 4스레드 동시 접근",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("8-2: get_logger 멀티스레드", str(e))

    # 8-3. set_level 동시 접근
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            num_threads = 4
            iterations_per_thread = 10_000
            barrier = threading.Barrier(num_threads)
            results_list = []
            levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

            def worker(tid):
                barrier.wait()
                start = time.perf_counter()
                for i in range(iterations_per_thread):
                    m.set_level(levels[i % len(levels)], module=f"thread_{tid}")
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            total_ops = num_threads * iterations_per_thread
            max_elapsed = max(results_list)
            ops = total_ops / max_elapsed
            m.shutdown()
        result.ok(
            "8-3: set_level 4스레드 동시 접근",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("8-3: set_level 멀티스레드", str(e))

    # 8-4. get_status 동시 접근
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()

            num_threads = 4
            iterations_per_thread = 20_000
            barrier = threading.Barrier(num_threads)
            results_list = []

            def worker():
                barrier.wait()
                start = time.perf_counter()
                for _ in range(iterations_per_thread):
                    m.get_status()
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)

            threads = [threading.Thread(target=worker) for _ in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            total_ops = num_threads * iterations_per_thread
            max_elapsed = max(results_list)
            ops = total_ops / max_elapsed
            m.shutdown()
        result.ok(
            "8-4: get_status 4스레드 동시 접근",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("8-4: get_status 멀티스레드", str(e))


# =============================================================================
# [9] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[9] 메모리 사용량")

    # 9-1. LogManager 인스턴스 메모리
    try:
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        m = LogManager()
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        result.ok(
            "9-1: LogManager 인스턴스 메모리",
            f"{total / 1024:.1f}KB",
        )
    except Exception as e:
        result.fail("9-1: 인스턴스 메모리", str(e))

    # 9-2. LoggingConfig 인스턴스 메모리
    try:
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        configs = [LoggingConfig() for _ in range(100)]
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        per_config = total / 100
        result.ok(
            "9-2: LoggingConfig 100개 메모리",
            f"총 {total / 1024:.1f}KB, 개당 {per_config:.0f}B",
        )
    except Exception as e:
        result.fail("9-2: LoggingConfig 메모리", str(e))

    # 9-3. SensitiveDataFilter 메모리
    try:
        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()
        filters = [SensitiveDataFilter() for _ in range(100)]
        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap2.compare_to(snap1, "lineno")
        total = sum(s.size_diff for s in diff if s.size_diff > 0)
        per_filter = total / 100
        result.ok(
            "9-3: SensitiveDataFilter 100개 메모리",
            f"총 {total / 1024:.1f}KB, 개당 {per_filter:.0f}B",
        )
    except Exception as e:
        result.fail("9-3: SensitiveDataFilter 메모리", str(e))

    # 9-4. LogManager setup 메모리 증가
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)

            tracemalloc.start()
            snap1 = tracemalloc.take_snapshot()
            m.setup()
            snap2 = tracemalloc.take_snapshot()
            tracemalloc.stop()

            diff = snap2.compare_to(snap1, "lineno")
            total = sum(s.size_diff for s in diff if s.size_diff > 0)
            m.shutdown()
        result.ok(
            "9-4: LogManager setup 메모리 증가 (최소 구성)",
            f"{total / 1024:.1f}KB",
        )
    except Exception as e:
        result.fail("9-4: setup 메모리", str(e))


# =============================================================================
# 메인
# =============================================================================
def main() -> bool:
    """성능 테스트 메인 실행."""
    result = PerformanceTestResult()

    print("=" * 60)
    print("COURTVIEW - logger.py 성능 테스트")
    print("=" * 60)

    test_log_level_performance(result)
    test_sensitive_filter_performance(result)
    test_config_creation_performance(result)
    test_log_manager_init_performance(result)
    test_get_logger_performance(result)
    test_set_level_performance(result)
    test_get_status_performance(result)
    test_multithread_performance(result)
    test_memory_usage(result)

    # 최종 정리
    reset_logging()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
