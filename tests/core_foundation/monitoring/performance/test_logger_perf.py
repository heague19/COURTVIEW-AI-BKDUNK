"""
tests/core_foundation/monitoring/performance/test_logger_perf.py

Logger 성능 테스트
- 로그 처리 속도: >10,000 logs/sec
- 메모리 사용량: <50MB
- 호출 오버헤드: <0.1ms
- 파일 쓰기 성능: >5,000 logs/sec
- 필터 처리: <0.01ms
- 포맷터 성능: <0.01ms

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import statistics
import tempfile

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.logger import (
    LogLevel,
    CourtViewLogger,
    ConsoleHandler,
    FileHandler,
    JSONFormatter,
    ConsoleFormatter,
    SensitiveDataFilter,
    get_logger,
)


# ==================== 성능 측정 유틸리티 ====================
def measure_time_ms(func, iterations: int = 1000) -> float:
    """
    함수 실행 시간 측정 (밀리초)

    Args:
        func: 측정할 함수
        iterations: 반복 횟수

    Returns:
        평균 실행 시간 (ms)
    """
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # ms로 변환

    return statistics.mean(times)


def measure_throughput(func, duration_sec: float = 1.0) -> float:
    """
    처리량 측정 (ops/sec)

    Args:
        func: 측정할 함수
        duration_sec: 측정 시간

    Returns:
        초당 처리량
    """
    count = 0
    start = time.perf_counter()
    end_time = start + duration_sec

    while time.perf_counter() < end_time:
        func()
        count += 1

    elapsed = time.perf_counter() - start
    return count / elapsed


def measure_memory_mb(obj) -> float:
    """
    객체 메모리 사용량 측정 (MB)

    Args:
        obj: 측정할 객체

    Returns:
        메모리 사용량 (MB)
    """
    import sys

    # 기본 객체 크기
    size = sys.getsizeof(obj)

    # __dict__ 크기 (있다면)
    if hasattr(obj, '__dict__'):
        size += sys.getsizeof(obj.__dict__)
        for key, value in obj.__dict__.items():
            size += sys.getsizeof(key)
            if isinstance(value, (str, int, float, bool)):
                size += sys.getsizeof(value)
            elif isinstance(value, (list, dict)):
                size += sys.getsizeof(value)

    return size / (1024 * 1024)  # MB로 변환


# ==================== 성능 테스트 결과 ====================
class PerformanceTestResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def record(self, test_name: str, actual: float, target: float, unit: str, passed: bool) -> None:
        """테스트 결과 기록"""
        self.results.append({
            "test": test_name,
            "actual": actual,
            "target": target,
            "unit": unit,
            "passed": passed
        })

        if passed:
            self.passed += 1
            status = "[PASS]"
        else:
            self.failed += 1
            status = "[FAIL]"

        print(f"{status} {test_name}: {actual:.4f}{unit} (목표: {'>' if 'throughput' in test_name.lower() or '/sec' in unit else '<'}{target}{unit})")

    def summary(self) -> None:
        """성능 테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")

        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for result in self.results:
                if not result["passed"]:
                    comp = ">" if "throughput" in result["test"].lower() else "<"
                    print(f"  - {result['test']}: {result['actual']:.4f}{result['unit']} (목표: {comp}{result['target']}{result['unit']})")

        print(f"{'='*70}")


# ==================== 로그 처리 속도 테스트 ====================
def test_logging_overhead(result: PerformanceTestResult) -> None:
    """로그 호출 오버헤드 (목표: <0.1ms)"""
    test_name = "로그 호출 오버헤드"

    # 핸들러 없는 로거 (순수 오버헤드)
    logger = CourtViewLogger("test", level=LogLevel.INFO)

    def log_message():
        logger.info("test message", extra={"key": "value"})

    avg_time = measure_time_ms(log_message, iterations=10000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_console_handler_throughput(result: PerformanceTestResult) -> None:
    """콘솔 핸들러 처리량 (목표: >10,000 logs/sec)"""
    test_name = "콘솔 핸들러 처리량"

    # stderr를 null로 리다이렉트
    import os
    devnull = open(os.devnull, 'w')

    handler = ConsoleHandler(level=LogLevel.INFO, stream=devnull)
    logger = CourtViewLogger("test", level=LogLevel.INFO)
    logger.add_handler(handler)

    def log_message():
        logger.info("test message")

    throughput = measure_throughput(log_message, duration_sec=0.5)
    target = 10000.0  # logs/sec
    passed = throughput > target

    devnull.close()

    result.record(test_name, throughput, target, " logs/sec", passed)


def test_file_handler_throughput(result: PerformanceTestResult) -> None:
    """파일 핸들러 처리량 (목표: >5,000 logs/sec)"""
    test_name = "파일 핸들러 처리량"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        temp_file = f.name

    handler = FileHandler(filename=temp_file, level=LogLevel.INFO)
    logger = CourtViewLogger("test", level=LogLevel.INFO)
    logger.add_handler(handler)

    def log_message():
        logger.info("test message", extra={"key": "value"})

    throughput = measure_throughput(log_message, duration_sec=0.5)
    target = 5000.0  # logs/sec
    passed = throughput > target

    handler.close()
    Path(temp_file).unlink()

    result.record(test_name, throughput, target, " logs/sec", passed)


def test_bulk_logging_performance(result: PerformanceTestResult) -> None:
    """대량 로그 처리 (10,000개, 목표: <1초)"""
    test_name = "대량 로그 처리 (10,000개)"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        temp_file = f.name

    handler = FileHandler(filename=temp_file, level=LogLevel.INFO)
    logger = CourtViewLogger("test", level=LogLevel.INFO)
    logger.add_handler(handler)

    start = time.perf_counter()
    for i in range(10000):
        logger.info(f"test message {i}", extra={"index": i})
    elapsed = (time.perf_counter() - start) * 1000  # ms

    target = 1000.0  # ms
    passed = elapsed < target

    handler.close()
    Path(temp_file).unlink()

    result.record(test_name, elapsed, target, "ms", passed)


# ==================== 필터 성능 테스트 ====================
def test_level_filter_performance(result: PerformanceTestResult) -> None:
    """레벨 필터 성능 (목표: <0.001ms)"""
    test_name = "레벨 필터 성능"

    from datetime import datetime
    from core_foundation.monitoring.logger import LevelFilter, LogRecord

    level_filter = LevelFilter(min_level=LogLevel.WARNING)

    record = LogRecord(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        logger_name="test",
        message="test"
    )

    def filter_record():
        level_filter.filter(record)

    avg_time = measure_time_ms(filter_record, iterations=100000)
    target = 0.001  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_sensitive_filter_performance(result: PerformanceTestResult) -> None:
    """민감 정보 필터 성능 (목표: <0.01ms)"""
    test_name = "민감 정보 필터 성능"

    from datetime import datetime
    from core_foundation.monitoring.logger import LogRecord

    sensitive_filter = SensitiveDataFilter()

    record = LogRecord(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        logger_name="test",
        message="test",
        context={
            "username": "test_user",
            "password": "secret123",
            "api_key": "sk-1234567890",
            "email": "user@example.com"
        }
    )

    def filter_record():
        sensitive_filter.filter(record)

    avg_time = measure_time_ms(filter_record, iterations=10000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 포맷터 성능 테스트 ====================
def test_json_formatter_performance(result: PerformanceTestResult) -> None:
    """JSON 포맷터 성능 (목표: <0.01ms)"""
    test_name = "JSON 포맷터 성능"

    from datetime import datetime
    from core_foundation.monitoring.logger import LogRecord

    formatter = JSONFormatter()

    record = LogRecord(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        logger_name="test.module",
        message="test message",
        context={"key": "value", "frame_id": 123}
    )

    def format_record():
        formatter.format(record)

    avg_time = measure_time_ms(format_record, iterations=10000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_console_formatter_performance(result: PerformanceTestResult) -> None:
    """콘솔 포맷터 성능 (목표: <0.01ms)"""
    test_name = "콘솔 포맷터 성능"

    from datetime import datetime
    from core_foundation.monitoring.logger import LogRecord

    formatter = ConsoleFormatter(colored=False)

    record = LogRecord(
        timestamp=datetime.now(),
        level=LogLevel.WARNING,
        logger_name="test.module",
        message="test message",
        context={"key": "value"}
    )

    def format_record():
        formatter.format(record)

    avg_time = measure_time_ms(format_record, iterations=10000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메모리 사용량 테스트 ====================
def test_logger_memory_usage(result: PerformanceTestResult) -> None:
    """로거 메모리 사용량 (목표: <1MB)"""
    test_name = "로거 메모리 사용량"

    logger = CourtViewLogger("test", level=LogLevel.INFO)
    handler = ConsoleHandler()
    logger.add_handler(handler)

    memory_mb = measure_memory_mb(logger)
    target = 1.0  # MB
    passed = memory_mb < target

    result.record(test_name, memory_mb, target, "MB", passed)


def test_handler_memory_usage(result: PerformanceTestResult) -> None:
    """핸들러 메모리 사용량 (목표: <0.5MB)"""
    test_name = "핸들러 메모리 사용량"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        temp_file = f.name

    handler = FileHandler(filename=temp_file, level=LogLevel.INFO)

    memory_mb = measure_memory_mb(handler)
    target = 0.5  # MB
    passed = memory_mb < target

    handler.close()
    Path(temp_file).unlink()

    result.record(test_name, memory_mb, target, "MB", passed)


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("Logger 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[로그 처리 속도]")
    test_logging_overhead(result)
    test_console_handler_throughput(result)
    test_file_handler_throughput(result)
    test_bulk_logging_performance(result)

    print("\n[필터 성능]")
    test_level_filter_performance(result)
    test_sensitive_filter_performance(result)

    print("\n[포맷터 성능]")
    test_json_formatter_performance(result)
    test_console_formatter_performance(result)

    print("\n[메모리 사용량]")
    test_logger_memory_usage(result)
    test_handler_memory_usage(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
