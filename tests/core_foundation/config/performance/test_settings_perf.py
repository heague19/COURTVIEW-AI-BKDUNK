"""
tests/core_foundation/config/performance/test_settings_perf.py

DesktopSettings 성능 테스트
- 초기화 시간: <50ms (Loader + Validator + Settings)
- 설정 접근 시간: <0.001ms (속성 접근)
- 리로드 시간: <50ms (재초기화)
- 메모리 사용량: <100KB (싱글톤 인스턴스)
- 멀티스레드 동시 접근: <100ms (10 스레드)

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import time
import statistics
import threading

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.settings import DesktopSettings


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
            if isinstance(value, (str, int, float, bool)):
                size += sys.getsizeof(value)
            elif isinstance(value, dict):
                size += sys.getsizeof(value)
                for k, v in value.items():
                    size += sys.getsizeof(k) + sys.getsizeof(v)
            elif hasattr(value, '__dict__'):
                # Pydantic 모델
                size += sys.getsizeof(value.__dict__)

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


# ==================== 초기화 성능 테스트 ====================
def test_initialization_time(result: PerformanceTestResult) -> None:
    """초기화 시간 (목표: <50ms)"""
    test_name = "초기화 시간"

    def initialize():
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

    avg_time = measure_time_ms(initialize, iterations=50)
    target = 50.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 설정 접근 성능 테스트 ====================
def test_property_access_time(result: PerformanceTestResult) -> None:
    """설정 접근 시간 (목표: <0.001ms)"""
    test_name = "설정 접근 시간"

    # 싱글톤 인스턴스 준비
    settings = DesktopSettings(
        config_dir=FIXTURES_DIR,
        environment="test",
        reload=True
    )

    def access_properties():
        _ = settings.gpu.device_id
        _ = settings.app.name
        _ = settings.camera.min_count
        _ = settings.detection.confidence_threshold

    avg_time = measure_time_ms(access_properties, iterations=10000)
    target = 0.001  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 리로드 성능 테스트 ====================
def test_reload_time(result: PerformanceTestResult) -> None:
    """리로드 시간 (목표: <50ms)"""
    test_name = "리로드 시간"

    # 싱글톤 인스턴스 준비
    settings = DesktopSettings(
        config_dir=FIXTURES_DIR,
        environment="test",
        reload=True
    )

    def reload_settings():
        settings.reload()

    avg_time = measure_time_ms(reload_settings, iterations=50)
    target = 50.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메모리 사용량 테스트 ====================
def test_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 (목표: <100KB)"""
    test_name = "메모리 사용량"

    # 싱글톤 인스턴스 생성
    settings = DesktopSettings(
        config_dir=FIXTURES_DIR,
        environment="test",
        reload=True
    )

    memory_kb = measure_memory_kb(settings)
    target = 100.0  # KB
    passed = memory_kb < target

    result.record(test_name, memory_kb, target, "KB", passed)


# ==================== 멀티스레드 동시 접근 성능 ====================
def test_multithreaded_access_time(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 (목표: <100ms for 10 threads)"""
    test_name = "멀티스레드 동시 접근 (10 스레드)"

    # 싱글톤 인스턴스 준비
    settings = DesktopSettings(
        config_dir=FIXTURES_DIR,
        environment="test",
        reload=True
    )

    def access_settings():
        for _ in range(100):
            _ = settings.gpu.device_id
            _ = settings.app.name
            _ = settings.camera.min_count

    # 10개 스레드 동시 접근
    start = time.perf_counter()
    threads = [threading.Thread(target=access_settings) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    end = time.perf_counter()

    total_time = (end - start) * 1000  # ms
    target = 100.0  # ms
    passed = total_time < target

    result.record(test_name, total_time, target, "ms", passed)


# ==================== 딕셔너리 변환 성능 테스트 ====================
def test_dict_conversion_time(result: PerformanceTestResult) -> None:
    """딕셔너리 변환 시간 (목표: <1ms)"""
    test_name = "딕셔너리 변환 시간"

    # 싱글톤 인스턴스 준비
    settings = DesktopSettings(
        config_dir=FIXTURES_DIR,
        environment="test",
        reload=True
    )

    def convert_to_dict():
        _ = settings.get_dict()

    avg_time = measure_time_ms(convert_to_dict, iterations=1000)
    target = 1.0  # ms
    passed = avg_time < target

    result.record(test_name, avg_time, target, "ms", passed)


# ==================== 메인 실행 ====================
def main():
    """모든 성능 테스트 실행"""
    print("="*70)
    print("DesktopSettings 성능 테스트")
    print("="*70)

    result = PerformanceTestResult()

    print("\n[초기화 및 리로드]")
    test_initialization_time(result)
    test_reload_time(result)

    print("\n[설정 접근]")
    test_property_access_time(result)
    test_dict_conversion_time(result)

    print("\n[메모리 및 동시성]")
    test_memory_usage(result)
    test_multithreaded_access_time(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
