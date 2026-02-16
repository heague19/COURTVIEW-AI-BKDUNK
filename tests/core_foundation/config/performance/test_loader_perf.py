# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/performance
파일: test_loader_perf.py
설명: ConfigLoader 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - YAML 파일 로드 시간
    - JSON 파일 로드 시간
    - get() 값 조회 시간 (캐시 히트)
    - dot notation 깊은 중첩 조회 시간
    - 타입 변환 조회 시간
    - 딥 머지 성능
    - set/get 처리량 (ops/sec)
    - 프로파일 기반 로드 시간
    - 메모리 사용량
    - 환경변수 오버라이드 적용 시간
"""

import gc
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.loader import (
    ConfigFormat,
    ConfigSource,
    ConfigEntry,
    ConfigMetadata,
    ConfigLoader,
)

# 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def record(
        self,
        test_name: str,
        actual: float,
        target: float,
        unit: str,
        higher_is_better: bool = False,
    ) -> None:
        """테스트 결과 기록."""
        if higher_is_better:
            passed = actual >= target
        else:
            passed = actual <= target

        if passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"

        self.results.append({
            "name": test_name,
            "actual": actual,
            "target": target,
            "unit": unit,
            "status": status,
            "higher_is_better": higher_is_better,
        })

        direction = ">=" if higher_is_better else "<="
        print(f"  [{status}] {test_name}: {actual:.4f} {unit} (목표: {direction} {target} {unit})")

    def summary(self) -> None:
        """결과 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")

        if self.failed > 0:
            print(f"\n목표 미달 항목:")
            for r in self.results:
                if r["status"] == "FAIL":
                    direction = ">=" if r["higher_is_better"] else "<="
                    print(f"  - {r['name']}: {r['actual']:.4f} {r['unit']} "
                          f"(목표: {direction} {r['target']} {r['unit']})")
        print(f"{'='*60}")


# =============================================================================
# 성능 측정 유틸리티
# =============================================================================
def measure_time_ms(func, iterations: int = 1000) -> float:
    """함수 실행 평균 시간 측정 (밀리초)."""
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    gc.enable()
    return (elapsed / iterations) * 1000


def measure_throughput(func, duration_sec: float = 1.0) -> float:
    """초당 처리량 측정 (ops/sec)."""
    gc.disable()
    count = 0
    start = time.perf_counter()
    while time.perf_counter() - start < duration_sec:
        func()
        count += 1
    elapsed = time.perf_counter() - start
    gc.enable()
    return count / elapsed


def measure_memory_kb(func) -> float:
    """함수 실행 전후 메모리 차이 측정 (KB)."""
    import tracemalloc
    tracemalloc.start()
    func()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024


def reset_loader() -> ConfigLoader:
    """테스트 전 ConfigLoader 리셋."""
    ConfigLoader.reset_instance()
    return ConfigLoader.get_instance()


# =============================================================================
# [1] 파일 로드 성능 테스트
# =============================================================================
def test_yaml_load_time(result: PerformanceTestResult) -> None:
    """YAML 파일 로드 시간."""
    def load_yaml():
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

    avg_ms = measure_time_ms(load_yaml, iterations=100)
    result.record("YAML 파일 로드", avg_ms, 10.0, "ms")


def test_json_load_time(result: PerformanceTestResult) -> None:
    """JSON 파일 로드 시간."""
    def load_json():
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.json")

    avg_ms = measure_time_ms(load_json, iterations=100)
    result.record("JSON 파일 로드", avg_ms, 10.0, "ms")


def test_profile_load_time(result: PerformanceTestResult) -> None:
    """프로파일 기반 로드 시간 (3파일 병합)."""
    def load_profile():
        loader = reset_loader()
        loader.load_with_profile(
            base_name="test_base",
            config_dir=str(FIXTURES_DIR),
        )

    avg_ms = measure_time_ms(load_profile, iterations=50)
    result.record("프로파일 기반 로드 (3파일)", avg_ms, 30.0, "ms")


def test_multiple_load_time(result: PerformanceTestResult) -> None:
    """다중 파일 로드 시간 (2파일 병합)."""
    def load_multiple():
        loader = reset_loader()
        loader.load_multiple(
            [
                FIXTURES_DIR / "test_base.yaml",
                FIXTURES_DIR / "test_override.yaml",
            ],
            required=True,
        )

    avg_ms = measure_time_ms(load_multiple, iterations=50)
    result.record("다중 파일 로드 (2파일)", avg_ms, 20.0, "ms")


# =============================================================================
# [2] 값 조회 성능 테스트
# =============================================================================
def test_get_simple_key(result: PerformanceTestResult) -> None:
    """단순 키 조회 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_simple():
        loader.get("environment")

    avg_ms = measure_time_ms(get_simple, iterations=10000)
    result.record("단순 키 조회 (get)", avg_ms, 0.05, "ms")


def test_get_dot_notation(result: PerformanceTestResult) -> None:
    """dot notation 2단계 조회 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_dotted():
        loader.get("gpu.cuda_device")

    avg_ms = measure_time_ms(get_dotted, iterations=10000)
    result.record("dot notation 조회 (2단계)", avg_ms, 0.05, "ms")


def test_get_deep_nesting(result: PerformanceTestResult) -> None:
    """깊은 중첩 조회 시간 (5단계)."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_nested.yaml")

    def get_deep():
        loader.get("level1.level2.level3.level4.level5.deep_value")

    avg_ms = measure_time_ms(get_deep, iterations=10000)
    result.record("깊은 중첩 조회 (5단계)", avg_ms, 0.1, "ms")


def test_get_with_default(result: PerformanceTestResult) -> None:
    """존재하지 않는 키 기본값 반환 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_default():
        loader.get("nonexistent.key", "fallback")

    avg_ms = measure_time_ms(get_default, iterations=10000)
    result.record("기본값 반환 (키 미존재)", avg_ms, 0.05, "ms")


def test_get_with_type_conversion(result: PerformanceTestResult) -> None:
    """타입 변환 포함 조회 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_typed():
        loader.get("server.port", 0, str)

    avg_ms = measure_time_ms(get_typed, iterations=10000)
    result.record("타입 변환 조회 (int→str)", avg_ms, 0.1, "ms")


def test_get_int_time(result: PerformanceTestResult) -> None:
    """get_int 조회 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_int_call():
        loader.get_int("server.port")

    avg_ms = measure_time_ms(get_int_call, iterations=10000)
    result.record("get_int 조회", avg_ms, 0.1, "ms")


def test_get_bool_time(result: PerformanceTestResult) -> None:
    """get_bool 조회 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_bool_call():
        loader.get_bool("app.debug")

    avg_ms = measure_time_ms(get_bool_call, iterations=10000)
    result.record("get_bool 조회", avg_ms, 0.1, "ms")


# =============================================================================
# [3] 값 설정 성능 테스트
# =============================================================================
def test_set_throughput(result: PerformanceTestResult) -> None:
    """set 처리량 (ops/sec)."""
    loader = reset_loader()
    counter = [0]

    def set_value():
        loader.set(f"key.{counter[0]}", counter[0])
        counter[0] += 1

    ops = measure_throughput(set_value, duration_sec=1.0)
    result.record("set 처리량", ops, 50000, "ops/sec", higher_is_better=True)


def test_get_throughput(result: PerformanceTestResult) -> None:
    """get 처리량 (ops/sec)."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def get_value():
        loader.get("gpu.cuda_device")

    ops = measure_throughput(get_value, duration_sec=1.0)
    result.record("get 처리량", ops, 100000, "ops/sec", higher_is_better=True)


# =============================================================================
# [4] 딥 머지 성능 테스트
# =============================================================================
def test_deep_merge_performance(result: PerformanceTestResult) -> None:
    """딥 머지 성능 (연속 로드)."""
    def merge_load():
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        loader.load(FIXTURES_DIR / "test_override.yaml")

    avg_ms = measure_time_ms(merge_load, iterations=50)
    result.record("딥 머지 (2파일 연속 로드)", avg_ms, 20.0, "ms")


# =============================================================================
# [5] 메모리 사용량 테스트
# =============================================================================
def test_memory_single_load(result: PerformanceTestResult) -> None:
    """단일 파일 로드 메모리 사용량."""
    def load_and_hold():
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

    mem_kb = measure_memory_kb(load_and_hold)
    result.record("단일 파일 로드 메모리", mem_kb, 512, "KB")


def test_memory_config_entry(result: PerformanceTestResult) -> None:
    """ConfigEntry 1000개 생성 메모리."""
    def create_entries():
        entries = []
        for i in range(1000):
            entries.append(ConfigEntry(
                key=f"key.{i}",
                value=f"value_{i}",
                source=ConfigSource.FILE,
            ))
        return entries

    mem_kb = measure_memory_kb(create_entries)
    result.record("ConfigEntry 1000개 메모리", mem_kb, 1024, "KB")


def test_memory_bulk_set(result: PerformanceTestResult) -> None:
    """10,000건 set 후 메모리."""
    def bulk_set():
        loader = reset_loader()
        for i in range(10000):
            loader.set(f"bulk.key.{i}", f"value_{i}")

    mem_kb = measure_memory_kb(bulk_set)
    result.record("10,000건 set 메모리", mem_kb, 8192, "KB")


# =============================================================================
# [6] 환경변수 오버라이드 성능 테스트
# =============================================================================
def test_env_override_performance(result: PerformanceTestResult) -> None:
    """환경변수 오버라이드 적용 시간."""
    # 환경변수 10개 설정
    env_keys = []
    for i in range(10):
        key = f"COURTVIEW_PERF_KEY{i}"
        os.environ[key] = str(i * 100)
        env_keys.append(key)

    try:
        def load_with_env():
            loader = reset_loader()
            loader.load(FIXTURES_DIR / "test_base.yaml")

        avg_ms = measure_time_ms(load_with_env, iterations=50)
        result.record("환경변수 10개 오버라이드 포함 로드", avg_ms, 15.0, "ms")
    finally:
        for key in env_keys:
            os.environ.pop(key, None)


# =============================================================================
# [7] has/keys/to_dict 성능 테스트
# =============================================================================
def test_has_throughput(result: PerformanceTestResult) -> None:
    """has 처리량."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def check_has():
        loader.has("gpu.cuda_device")

    ops = measure_throughput(check_has, duration_sec=1.0)
    result.record("has 처리량", ops, 100000, "ops/sec", higher_is_better=True)


def test_to_dict_time(result: PerformanceTestResult) -> None:
    """to_dict 딥카피 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def to_dict_call():
        loader.to_dict()

    avg_ms = measure_time_ms(to_dict_call, iterations=1000)
    result.record("to_dict (딥카피)", avg_ms, 0.5, "ms")


def test_keys_time(result: PerformanceTestResult) -> None:
    """keys 목록 반환 시간."""
    loader = reset_loader()
    loader.load(FIXTURES_DIR / "test_base.yaml")

    def keys_call():
        loader.keys()

    avg_ms = measure_time_ms(keys_call, iterations=10000)
    result.record("keys 목록 반환", avg_ms, 0.05, "ms")


# =============================================================================
# [8] 대규모 설정 성능 테스트
# =============================================================================
def test_bulk_get_performance(result: PerformanceTestResult) -> None:
    """10,000건 연속 get 총 시간."""
    loader = reset_loader()
    # 설정 데이터 대량 주입
    for i in range(1000):
        loader.set(f"section.{i // 100}.key{i}", i)

    gc.disable()
    start = time.perf_counter()
    for i in range(10000):
        loader.get(f"section.{(i % 1000) // 100}.key{i % 1000}")
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    result.record("10,000건 연속 get 총 시간", elapsed_ms, 100, "ms")


def test_bulk_set_performance(result: PerformanceTestResult) -> None:
    """10,000건 연속 set 총 시간."""
    loader = reset_loader()

    gc.disable()
    start = time.perf_counter()
    for i in range(10000):
        loader.set(f"bulk.key.{i}", i)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    result.record("10,000건 연속 set 총 시간", elapsed_ms, 500, "ms")


# =============================================================================
# [9] 싱글톤 성능 테스트
# =============================================================================
def test_singleton_access_time(result: PerformanceTestResult) -> None:
    """싱글톤 인스턴스 접근 시간."""
    reset_loader()

    def access_singleton():
        ConfigLoader.get_instance()

    avg_ms = measure_time_ms(access_singleton, iterations=100000)
    result.record("싱글톤 접근 시간", avg_ms, 0.01, "ms")


# =============================================================================
# 메인 실행
# =============================================================================
def main():
    """모든 ConfigLoader 성능 테스트 실행."""
    print("=" * 60)
    print("ConfigLoader 성능 테스트")
    print(f"픽스처 경로: {FIXTURES_DIR}")
    print("=" * 60)

    result = PerformanceTestResult()

    print("\n[1] 파일 로드 성능")
    test_yaml_load_time(result)
    test_json_load_time(result)
    test_profile_load_time(result)
    test_multiple_load_time(result)

    print("\n[2] 값 조회 성능")
    test_get_simple_key(result)
    test_get_dot_notation(result)
    test_get_deep_nesting(result)
    test_get_with_default(result)
    test_get_with_type_conversion(result)
    test_get_int_time(result)
    test_get_bool_time(result)

    print("\n[3] 값 설정 성능")
    test_set_throughput(result)
    test_get_throughput(result)

    print("\n[4] 딥 머지 성능")
    test_deep_merge_performance(result)

    print("\n[5] 메모리 사용량")
    test_memory_single_load(result)
    test_memory_config_entry(result)
    test_memory_bulk_set(result)

    print("\n[6] 환경변수 오버라이드 성능")
    test_env_override_performance(result)

    print("\n[7] 유틸리티 성능")
    test_has_throughput(result)
    test_to_dict_time(result)
    test_keys_time(result)

    print("\n[8] 대규모 설정 성능")
    test_bulk_get_performance(result)
    test_bulk_set_performance(result)

    print("\n[9] 싱글톤 성능")
    test_singleton_access_time(result)

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
