"""
tests/core_foundation/exceptions/performance/test_validation_hardware_perf.py

validation.py, hardware.py 성능 테스트
- ConfigError, DataValidationError: <0.1ms 생성
- GPUError, CameraError, InsufficientMemoryError: <0.1ms 생성
- 메모리 사용량: <1.5KB per instance

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import statistics

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.exceptions.validation import ConfigError, DataValidationError
from core_foundation.exceptions.hardware import GPUError, CameraError, InsufficientMemoryError


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


def measure_memory_kb(obj) -> float:
    """
    객체 메모리 사용량 측정 (KB)

    Args:
        obj: 측정할 객체

    Returns:
        메모리 사용량 (KB)
    """
    import sys

    # 기본 객체 크기
    size = sys.getsizeof(obj)

    # __dict__ 크기 (있다면)
    if hasattr(obj, '__dict__'):
        size += sys.getsizeof(obj.__dict__)
        for key, value in obj.__dict__.items():
            size += sys.getsizeof(key)
            size += sys.getsizeof(value)

    return size / 1024  # KB로 변환


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

        print(f"{status} {test_name}: {actual:.4f}{unit} (목표: <{target}{unit})")

    def summary(self) -> None:
        """성능 테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")

        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['actual']:.4f}{result['unit']} (목표: <{result['target']}{result['unit']})")

        print(f"{'='*70}")


# ==================== ConfigError 성능 테스트 ====================
def test_config_error_creation_time(result: PerformanceTestResult) -> None:
    """ConfigError 생성 시간 테스트 (목표: <0.1ms)"""
    test_name = "ConfigError 생성 시간"

    def create_exception():
        ConfigError("설정 에러", config_file="test.yaml")

    avg_time = measure_time_ms(create_exception, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_config_error_memory_usage(result: PerformanceTestResult) -> None:
    """ConfigError 메모리 사용량 테스트 (목표: <1.5KB)"""
    test_name = "ConfigError 메모리 사용량"

    error = ConfigError(
        "설정 에러",
        config_file="configs/gpu.yaml",
        context={"key": "value"}
    )

    memory_kb = measure_memory_kb(error)
    target = 1.5  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== DataValidationError 성능 테스트 ====================
def test_data_validation_error_creation_time(result: PerformanceTestResult) -> None:
    """DataValidationError 생성 시간 테스트 (목표: <0.1ms)"""
    test_name = "DataValidationError 생성 시간"

    def create_exception():
        DataValidationError(
            "검증 실패",
            field_name="test_field",
            expected_type="int",
            actual_value="invalid"
        )

    avg_time = measure_time_ms(create_exception, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_data_validation_error_memory_usage(result: PerformanceTestResult) -> None:
    """DataValidationError 메모리 사용량 테스트 (목표: <1.5KB)"""
    test_name = "DataValidationError 메모리 사용량"

    error = DataValidationError(
        "검증 실패",
        field_name="gpu_id",
        expected_type="int",
        actual_value="invalid_value"
    )

    memory_kb = measure_memory_kb(error)
    target = 1.5  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== GPUError 성능 테스트 ====================
def test_gpu_error_creation_time(result: PerformanceTestResult) -> None:
    """GPUError 생성 시간 테스트 (목표: <0.1ms)"""
    test_name = "GPUError 생성 시간"

    def create_exception():
        GPUError(
            "GPU 메모리 부족",
            gpu_id=0,
            required_memory_mb=8000,
            available_memory_mb=4000
        )

    avg_time = measure_time_ms(create_exception, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_gpu_error_memory_usage(result: PerformanceTestResult) -> None:
    """GPUError 메모리 사용량 테스트 (목표: <1.5KB)"""
    test_name = "GPUError 메모리 사용량"

    error = GPUError(
        "GPU 메모리 부족",
        gpu_id=0,
        required_memory_mb=8000,
        available_memory_mb=4000
    )

    memory_kb = measure_memory_kb(error)
    target = 1.5  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== CameraError 성능 테스트 ====================
def test_camera_error_creation_time(result: PerformanceTestResult) -> None:
    """CameraError 생성 시간 테스트 (목표: <0.1ms)"""
    test_name = "CameraError 생성 시간"

    def create_exception():
        CameraError(
            "카메라 연결 실패",
            camera_id=0,
            camera_name="USB Camera 0"
        )

    avg_time = measure_time_ms(create_exception, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_camera_error_memory_usage(result: PerformanceTestResult) -> None:
    """CameraError 메모리 사용량 테스트 (목표: <1.5KB)"""
    test_name = "CameraError 메모리 사용량"

    error = CameraError(
        "카메라 연결 실패",
        camera_id=0,
        camera_name="USB Camera 0"
    )

    memory_kb = measure_memory_kb(error)
    target = 1.5  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== InsufficientMemoryError 성능 테스트 ====================
def test_memory_error_creation_time(result: PerformanceTestResult) -> None:
    """InsufficientMemoryError 생성 시간 테스트 (목표: <0.1ms)"""
    test_name = "InsufficientMemoryError 생성 시간"

    def create_exception():
        InsufficientMemoryError(
            "메모리 부족",
            required_mb=16000,
            available_mb=8000,
            memory_type="system"
        )

    avg_time = measure_time_ms(create_exception, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_memory_error_memory_usage(result: PerformanceTestResult) -> None:
    """InsufficientMemoryError 메모리 사용량 테스트 (목표: <1.5KB)"""
    test_name = "InsufficientMemoryError 메모리 사용량"

    error = InsufficientMemoryError(
        "메모리 부족",
        required_mb=16000,
        available_mb=8000,
        memory_type="system"
    )

    memory_kb = measure_memory_kb(error)
    target = 1.5  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== 대량 생성 테스트 ====================
def test_bulk_creation_performance(result: PerformanceTestResult) -> None:
    """대량 생성 성능 테스트 (목표: 1,000개 <100ms)"""
    test_name = "대량 생성 (1,000개)"

    start = time.perf_counter()
    for i in range(1000):
        if i % 5 == 0:
            ConfigError(f"에러 {i}", config_file="test.yaml")
        elif i % 5 == 1:
            DataValidationError(f"에러 {i}", field_name="field")
        elif i % 5 == 2:
            GPUError(f"에러 {i}", gpu_id=0)
        elif i % 5 == 3:
            CameraError(f"에러 {i}", camera_id=0)
        else:
            InsufficientMemoryError(f"에러 {i}")
    end = time.perf_counter()

    total_time = (end - start) * 1000  # ms
    target = 100.0  # ms
    passed = total_time < target

    result.record(test_name, total_time, target, "ms", passed)


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("validation.py, hardware.py 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[ConfigError]")
    test_config_error_creation_time(result)
    test_config_error_memory_usage(result)

    print("\n[DataValidationError]")
    test_data_validation_error_creation_time(result)
    test_data_validation_error_memory_usage(result)

    print("\n[GPUError]")
    test_gpu_error_creation_time(result)
    test_gpu_error_memory_usage(result)

    print("\n[CameraError]")
    test_camera_error_creation_time(result)
    test_camera_error_memory_usage(result)

    print("\n[InsufficientMemoryError]")
    test_memory_error_creation_time(result)
    test_memory_error_memory_usage(result)

    print("\n[대량 생성]")
    test_bulk_creation_performance(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
