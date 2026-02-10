"""
tests/core_foundation/config/performance/test_loader_perf.py

ConfigLoader 성능 테스트
- YAML 로드: <10ms (캐시 미스)
- 캐시 조회: <0.1ms (캐시 히트)
- 메모리: <1MB (50개 파일 캐시)
- 병합: <1ms

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

from core_foundation.config.loader import ConfigLoader


# 테스트 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


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


# ==================== YAML 로딩 성능 테스트 ====================
def test_yaml_load_cold_cache(result: PerformanceTestResult) -> None:
    """YAML 로드 시간 테스트 - 캐시 미스 (목표: <10ms)"""
    test_name = "YAML 로드 (캐시 미스)"

    def load_yaml():
        loader = ConfigLoader(config_dir=FIXTURES_DIR, cache_enabled=False)
        loader.load_yaml("test_base.yaml")

    avg_time = measure_time_ms(load_yaml, iterations=100)
    target = 10.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


def test_yaml_load_hot_cache(result: PerformanceTestResult) -> None:
    """YAML 로드 시간 테스트 - 캐시 히트 (목표: <0.1ms)"""
    test_name = "YAML 로드 (캐시 히트)"

    loader = ConfigLoader(config_dir=FIXTURES_DIR, cache_enabled=True)
    loader.load_yaml("test_base.yaml")  # 캐시 워밍

    def load_yaml():
        loader.load_yaml("test_base.yaml")

    avg_time = measure_time_ms(load_yaml, iterations=1000)
    target = 0.1  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 설정 병합 성능 테스트 ====================
def test_merge_configs_performance(result: PerformanceTestResult) -> None:
    """설정 병합 시간 테스트 (목표: <1ms)"""
    test_name = "설정 병합"

    loader = ConfigLoader(config_dir=FIXTURES_DIR)
    base = loader.load_yaml("test_base.yaml")
    env_config = loader.load_yaml("test_env_dev.yaml")
    env_override = {"app": {"name": "Override"}}

    def merge():
        loader.merge_configs(base, env_config, env_override)

    avg_time = measure_time_ms(merge, iterations=1000)
    target = 1.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== get() 메서드 성능 테스트 ====================
def test_get_nested_key_performance(result: PerformanceTestResult) -> None:
    """중첩 키 접근 시간 테스트 (목표: <0.01ms)"""
    test_name = "중첩 키 접근 (점 표기법)"

    loader = ConfigLoader(config_dir=FIXTURES_DIR)
    config = loader.load_yaml("test_base.yaml")

    def get_key():
        loader.get("camera.resolution.width", config)

    avg_time = measure_time_ms(get_key, iterations=10000)
    target = 0.01  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메모리 사용량 테스트 ====================
def test_loader_memory_usage(result: PerformanceTestResult) -> None:
    """ConfigLoader 메모리 사용량 테스트 (목표: <100KB)"""
    test_name = "ConfigLoader 메모리 사용량"

    loader = ConfigLoader(config_dir=FIXTURES_DIR)
    loader.load_yaml("test_base.yaml")

    memory_kb = measure_memory_kb(loader)
    target = 100.0  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


def test_cache_memory_usage(result: PerformanceTestResult) -> None:
    """캐시 메모리 사용량 테스트 - 10개 파일 (목표: <200KB)"""
    test_name = "캐시 메모리 (10개 파일)"

    loader = ConfigLoader(config_dir=FIXTURES_DIR, cache_enabled=True)

    # 10개 파일 로드 (test_base.yaml, test_env_dev.yaml 반복)
    for i in range(5):
        loader.load_yaml("test_base.yaml")
        loader.load_yaml("test_env_dev.yaml")

    memory_kb = measure_memory_kb(loader)
    target = 200.0  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== 대량 로딩 테스트 ====================
def test_bulk_loading_performance(result: PerformanceTestResult) -> None:
    """대량 로딩 성능 테스트 - 100개 파일 (목표: <100ms)"""
    test_name = "대량 로딩 (100개)"

    loader = ConfigLoader(config_dir=FIXTURES_DIR, cache_enabled=True)

    start = time.perf_counter()
    for i in range(100):
        if i % 2 == 0:
            loader.load_yaml("test_base.yaml")
        else:
            loader.load_yaml("test_env_dev.yaml")
    end = time.perf_counter()

    total_time = (end - start) * 1000  # ms
    target = 100.0  # ms
    passed = total_time < target

    result.record(test_name, total_time, target, "ms", passed)


# ==================== 처리량 테스트 ====================
def test_throughput(result: PerformanceTestResult) -> None:
    """처리량 테스트 (목표: >1,000 loads/sec)"""
    test_name = "처리량"

    loader = ConfigLoader(config_dir=FIXTURES_DIR, cache_enabled=True)
    loader.load_yaml("test_base.yaml")  # 캐시 워밍

    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        loader.load_yaml("test_base.yaml")
    end = time.perf_counter()

    total_time = end - start
    throughput = iterations / total_time  # loads/sec
    target = 1000.0  # loads/sec
    passed = throughput > target

    print(f"{'[PASS]' if passed else '[FAIL]'} {test_name}: {throughput:.0f} loads/sec (목표: >{target:.0f} loads/sec)")

    result.passed += 1 if passed else 0
    result.failed += 0 if passed else 1


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("ConfigLoader 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[YAML 로딩]")
    test_yaml_load_cold_cache(result)
    test_yaml_load_hot_cache(result)

    print("\n[설정 병합]")
    test_merge_configs_performance(result)

    print("\n[get() 메서드]")
    test_get_nested_key_performance(result)

    print("\n[메모리]")
    test_loader_memory_usage(result)
    test_cache_memory_usage(result)

    print("\n[대량 처리]")
    test_bulk_loading_performance(result)
    test_throughput(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
