"""
tests/core_foundation/config/performance/test_validator_perf.py

ConfigValidator 성능 테스트
- 검증 시간: <5ms (평균 설정)
- 메모리 사용량: <100KB
- 처리량: >1,000 validations/sec
- 대량 검증: 100개 <500ms
- 에러 생성 시간: <1ms

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

from core_foundation.config.validator import (
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    AppConfig,
    DesktopConfigValidator,
    validate_config_dict,
)


# ==================== 성능 측정 유틸리티 ====================
def measure_time_ms(func, iterations: int = 100) -> float:
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
            if isinstance(value, (str, int, float, bool)):
                size += sys.getsizeof(value)
            elif isinstance(value, dict):
                size += sys.getsizeof(value)
                for k, v in value.items():
                    size += sys.getsizeof(k) + sys.getsizeof(v)

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


# ==================== 검증 시간 테스트 ====================
def test_gpu_config_validation_time(result: PerformanceTestResult) -> None:
    """GPUConfig 검증 시간 (목표: <5ms)"""
    test_name = "GPUConfig 검증 시간"

    def validate():
        config = GPUConfig(
            device_id=0,
            memory_fraction=0.8,
            backend="cuda",
            batch_size=8
        )
        config.validate_custom()

    avg_time = measure_time_ms(validate, iterations=1000)
    target = 5.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_camera_config_validation_time(result: PerformanceTestResult) -> None:
    """CameraConfig 검증 시간 (목표: <5ms)"""
    test_name = "CameraConfig 검증 시간"

    def validate():
        config = CameraConfig(
            min_count=4,
            max_count=8,
            resolution={"width": 1920, "height": 1080},
            fps=30
        )
        config.validate_custom()

    avg_time = measure_time_ms(validate, iterations=1000)
    target = 5.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_desktop_config_validator_time(result: PerformanceTestResult) -> None:
    """DesktopConfigValidator 검증 시간 (목표: <5ms)"""
    test_name = "DesktopConfigValidator 검증 시간"

    def validate():
        config = DesktopConfigValidator(
            app={"name": "Test", "version": "1.0.0"},
            gpu={"device_id": 0, "memory_fraction": 0.8},
            camera={"min_count": 4, "max_count": 8},
            detection={"confidence_threshold": 0.75}
        )
        config.validate_all()

    avg_time = measure_time_ms(validate, iterations=1000)
    target = 5.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메모리 사용량 테스트 ====================
def test_gpu_config_memory_usage(result: PerformanceTestResult) -> None:
    """GPUConfig 메모리 사용량 (목표: <100KB)"""
    test_name = "GPUConfig 메모리 사용량"

    config = GPUConfig(
        device_id=0,
        memory_fraction=0.8,
        backend="cuda",
        batch_size=8
    )

    memory_kb = measure_memory_kb(config)
    target = 100.0  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


def test_desktop_config_validator_memory(result: PerformanceTestResult) -> None:
    """DesktopConfigValidator 메모리 사용량 (목표: <100KB)"""
    test_name = "DesktopConfigValidator 메모리 사용량"

    config = DesktopConfigValidator(
        app={"name": "Test", "version": "1.0.0"},
        gpu={"device_id": 0, "memory_fraction": 0.8},
        camera={"min_count": 4, "max_count": 8},
        detection={"confidence_threshold": 0.75}
    )

    memory_kb = measure_memory_kb(config)
    target = 100.0  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== 처리량 테스트 ====================
def test_validation_throughput(result: PerformanceTestResult) -> None:
    """검증 처리량 (목표: >1,000 validations/sec)"""
    test_name = "검증 처리량"

    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        config = GPUConfig(
            device_id=0,
            memory_fraction=0.8,
            backend="cuda",
            batch_size=8
        )
        config.validate_custom()
    end = time.perf_counter()

    total_time = end - start
    throughput = iterations / total_time  # validations/sec
    target = 1000.0  # validations/sec
    passed = throughput > target

    print(f"{'[PASS]' if passed else '[FAIL]'} {test_name}: {throughput:.0f} validations/sec (목표: >{target:.0f} validations/sec)")

    result.passed += 1 if passed else 0
    result.failed += 0 if passed else 1


# ==================== 대량 검증 테스트 ====================
def test_bulk_validation(result: PerformanceTestResult) -> None:
    """대량 검증 (100개 설정, 목표: <500ms)"""
    test_name = "대량 검증 (100개)"

    configs = [
        {
            "device_id": i % 8,
            "memory_fraction": 0.5 + (i % 5) * 0.1,
            "backend": ["cuda", "metal", "cpu"][i % 3],
            "batch_size": 2 ** (i % 6 + 1)  # 2, 4, 8, 16, 32, 64
        }
        for i in range(100)
    ]

    start = time.perf_counter()
    for config_dict in configs:
        config, errors = validate_config_dict(config_dict, GPUConfig, raise_on_error=False)
    end = time.perf_counter()

    total_time = (end - start) * 1000  # ms
    target = 500.0  # ms
    passed = total_time < target

    result.record(test_name, total_time, target, "ms", passed)


# ==================== 에러 생성 시간 테스트 ====================
def test_error_generation_time(result: PerformanceTestResult) -> None:
    """에러 생성 시간 (목표: <1ms)"""
    test_name = "에러 생성 시간"

    def generate_error():
        config_dict = {"device_id": 100}  # 범위 초과
        validated, errors = validate_config_dict(
            config_dict,
            GPUConfig,
            raise_on_error=False
        )

    avg_time = measure_time_ms(generate_error, iterations=1000)
    target = 1.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("ConfigValidator 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[검증 시간]")
    test_gpu_config_validation_time(result)
    test_camera_config_validation_time(result)
    test_desktop_config_validator_time(result)

    print("\n[메모리 사용량]")
    test_gpu_config_memory_usage(result)
    test_desktop_config_validator_memory(result)

    print("\n[처리량 및 대량 검증]")
    test_validation_throughput(result)
    test_bulk_validation(result)

    print("\n[에러 생성]")
    test_error_generation_time(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
