# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/performance
파일: test_model_registry_perf.py
설명: ModelRegistry 모델 레지스트리 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [P1] Enum 연산 성능 (3개) - ModelType/ModelStatus/ModelFormat
    [P2] ModelVersion 생성/비교 성능 (3개)
    [P3] 데이터 클래스 생성 성능 (3개)
    [P4] ModelRegistry 등록/조회 성능 (4개)
    [P5] ModelRegistry 대량 등록 성능 (3개)
    [P6] 싱글톤/헬퍼 함수 성능 (3개)
    [P7] 멀티스레드 동시 접근 (3개)
    [P8] 메모리 사용량 (3개)

    총 25개 테스트
"""

import gc
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.registry.model_registry import (
    # Enum
    ModelType,
    ModelStatus,
    ModelFormat,
    # 상수
    DEFAULT_MAX_MODELS,
    DEFAULT_MODEL_TIMEOUT,
    DEFAULT_WARMUP_ITERATIONS,
    MODEL_CACHE_SIZE_MB,
    # 데이터 클래스
    ModelInfo,
    ModelVersion,
    ModelMetrics,
    ModelConfig,
    LoadedModel,
    # 프로토콜 인터페이스
    IModel,
    IModelLoader,
    # 메인 클래스
    ModelRegistry,
    # 함수
    get_model,
    register_model,
    # 유틸리티 (테스트용)
    _get_registry,
    _reset_registry,
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
    """초당 연산 수 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


def measure_time_ms(func, iterations: int = 1000) -> float:
    """평균 실행 시간 (밀리초) 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000


def get_object_size(obj) -> int:
    """객체 대략적 메모리 크기 (바이트) 측정."""
    return sys.getsizeof(obj)


def _make_registry(**kwargs) -> ModelRegistry:
    """테스트용 ModelRegistry 생성 (최소 설정)."""
    defaults = {
        "max_models": 5000,
        "enable_auto_unload": False,
    }
    defaults.update(kwargs)
    return ModelRegistry(**defaults)


def _make_model_info(
    name: str = "test_model",
    idx: int = 0,
    model_type: ModelType = ModelType.YOLO,
) -> ModelInfo:
    """테스트용 ModelInfo 생성 헬퍼."""
    version = ModelVersion(major=1, minor=0, patch=idx)
    return ModelInfo(
        model_id=f"{name}:{version}",
        name=name,
        model_type=model_type,
        version=version,
    )


# =============================================================================
# [P1] Enum 연산 성능 (3개)
# =============================================================================
def test_p1_enum_performance(result: PerformanceTestResult) -> None:
    """Enum 연산 성능 테스트."""
    print("\n[P1] Enum 연산 성능")

    # P1-1. ModelType/ModelStatus/ModelFormat 순회 성능
    try:
        iterations = 100_000

        start = time.perf_counter()
        for _ in range(iterations):
            for _ in ModelType:
                pass
            for _ in ModelStatus:
                pass
            for _ in ModelFormat:
                pass
        elapsed = time.perf_counter() - start

        total_enums = len(ModelType) + len(ModelStatus) + len(ModelFormat)
        total_ops = iterations * total_enums
        ops = total_ops / elapsed
        result.ok("P1-1 Enum 3종 순회 성능", f"{ops:,.0f} ops/sec (총 {total_enums}개 멤버)")
    except Exception as e:
        result.fail("P1-1 Enum 순회", str(e))

    # P1-2. Enum 비교 연산 성능
    try:
        type_yolo = ModelType.YOLO
        type_onnx = ModelType.ONNX
        status_ready = ModelStatus.READY
        status_error = ModelStatus.ERROR
        fmt_weights = ModelFormat.WEIGHTS
        fmt_compiled = ModelFormat.COMPILED

        iterations = 500_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = type_yolo == type_onnx
            _ = type_yolo == ModelType.YOLO
            _ = status_ready != status_error
            _ = status_ready == ModelStatus.READY
            _ = fmt_weights == fmt_compiled
            _ = fmt_weights != ModelFormat.QUANTIZED
        elapsed = time.perf_counter() - start

        ops = (iterations * 6) / elapsed
        result.ok("P1-2 Enum 비교 연산 (6종)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P1-2 Enum 비교", str(e))

    # P1-3. Enum 속성 접근 및 문자열 변환 성능
    try:
        all_types = list(ModelType)
        all_statuses = list(ModelStatus)

        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            for mt in all_types:
                _ = mt.value
                _ = mt.file_extensions
                _ = mt.supports_gpu
            for ms in all_statuses:
                _ = ms.value
                _ = ms.is_usable
                _ = ms.is_loading
        elapsed = time.perf_counter() - start

        total_calls = iterations * (len(all_types) * 3 + len(all_statuses) * 3)
        ops = total_calls / elapsed
        result.ok(
            "P1-3 Enum 속성/문자열 변환",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P1-3 Enum 속성 접근", str(e))


# =============================================================================
# [P2] ModelVersion 생성/비교 성능 (3개)
# =============================================================================
def test_p2_model_version_performance(result: PerformanceTestResult) -> None:
    """ModelVersion 생성 및 비교 성능."""
    print("\n[P2] ModelVersion 생성/비교 성능")

    # P2-1. ModelVersion 직접 생성 처리량
    try:
        ops = measure_ops(
            lambda: ModelVersion(major=1, minor=2, patch=3),
            iterations=100_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000
        result.ok("P2-1 ModelVersion() 생성", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        result.fail("P2-1 ModelVersion 생성", str(e))

    # P2-2. ModelVersion 비교 연산 성능
    try:
        v1 = ModelVersion(major=1, minor=0, patch=0)
        v2 = ModelVersion(major=1, minor=1, patch=0)
        v3 = ModelVersion(major=2, minor=0, patch=0)

        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = v1 < v2
            _ = v2 < v3
            _ = v1 == v1
            _ = v1 != v3
            _ = hash(v1)
            _ = hash(v2)
        elapsed = time.perf_counter() - start

        ops = (iterations * 6) / elapsed
        result.ok("P2-2 ModelVersion 비교/해시 (6종)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-2 ModelVersion 비교", str(e))

    # P2-3. ModelVersion.from_string 파싱 성능
    try:
        version_strings = [
            "1.0.0",
            "2.3.1",
            "0.1.0-alpha",
            "3.0.0-beta+build123",
            "10.20.30",
        ]
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            for vs in version_strings:
                ModelVersion.from_string(vs)
        elapsed = time.perf_counter() - start

        total_parses = iterations * len(version_strings)
        ops = total_parses / elapsed
        per_call_us = (elapsed / total_parses) * 1_000_000
        result.ok(
            "P2-3 from_string 파싱",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-3 from_string 파싱", str(e))


# =============================================================================
# [P3] 데이터 클래스 생성 성능 (3개)
# =============================================================================
def test_p3_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능."""
    print("\n[P3] 데이터 클래스 생성 성능")

    # P3-1. ModelInfo 생성 처리량
    try:
        version = ModelVersion(major=1, minor=0, patch=0)

        ops = measure_ops(
            lambda: ModelInfo(
                model_id="test:1.0.0",
                name="test",
                model_type=ModelType.YOLO,
                version=version,
            ),
            iterations=30_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000
        result.ok("P3-1 ModelInfo() 생성", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        result.fail("P3-1 ModelInfo 생성", str(e))

    # P3-2. ModelMetrics 생성 + record_inference 처리량
    try:
        iterations = 50_000

        start = time.perf_counter()
        for _ in range(iterations):
            mm = ModelMetrics()
            mm.record_inference(16.5, success=True, confidence=0.92)
        elapsed = time.perf_counter() - start

        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok(
            "P3-2 ModelMetrics 생성+record_inference",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-2 ModelMetrics", str(e))

    # P3-3. ModelConfig + LoadedModel 생성 처리량
    try:
        version = ModelVersion(major=1, minor=0, patch=0)
        info = ModelInfo(
            model_id="test:1.0.0",
            name="test",
            model_type=ModelType.YOLO,
            version=version,
        )

        # ModelConfig 생성 측정
        config_ops = measure_ops(
            lambda: ModelConfig(
                device="cuda",
                precision="fp16",
                batch_size=4,
                num_threads=4,
            ),
            iterations=50_000,
        )

        # LoadedModel 생성 측정
        loaded_ops = measure_ops(
            lambda: LoadedModel(model_info=info),
            iterations=30_000,
        )

        result.ok(
            "P3-3 ModelConfig+LoadedModel 생성",
            f"ModelConfig: {config_ops:,.0f} ops/sec, LoadedModel: {loaded_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P3-3 Config+LoadedModel", str(e))


# =============================================================================
# [P4] ModelRegistry 등록/조회 성능 (4개)
# =============================================================================
def test_p4_registry_operations(result: PerformanceTestResult) -> None:
    """ModelRegistry 기본 등록/조회 성능."""
    print("\n[P4] ModelRegistry 등록/조회 성능")

    # P4-1. register 처리량
    try:
        registry = _make_registry(max_models=10000)

        iterations = 1000
        start = time.perf_counter()
        for i in range(iterations):
            registry.register(
                name=f"model_{i}",
                model_type=ModelType.YOLO,
                version="1.0.0",
            )
        elapsed = time.perf_counter() - start

        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        result.ok("P4-1 register 처리량", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        result.fail("P4-1 register", str(e))

    # P4-2. get 조회 처리량
    try:
        registry = _make_registry(max_models=5000)
        # 500개 모델 사전 등록
        model_ids = []
        for i in range(500):
            info = registry.register(
                name=f"get_model_{i}",
                model_type=ModelType.ONNX,
                version="1.0.0",
            )
            model_ids.append(info.model_id)

        # 조회 성능 측정 (존재하는 모델)
        target_id = model_ids[250]
        ops = measure_ops(lambda: registry.get(target_id), iterations=100_000)
        per_call_us = (1.0 / ops) * 1_000_000
        result.ok("P4-2 get 조회 (500개 중)", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        result.fail("P4-2 get 조회", str(e))

    # P4-3. list_all / list_by_type 처리량
    try:
        registry = _make_registry(max_models=2000)
        model_types = [ModelType.YOLO, ModelType.ONNX, ModelType.PYTORCH, ModelType.MEDIAPIPE]
        for i in range(200):
            registry.register(
                name=f"list_model_{i}",
                model_type=model_types[i % len(model_types)],
                version="1.0.0",
            )

        # list_all 측정
        list_all_ops = measure_ops(lambda: registry.list_all(), iterations=10_000)

        # list_by_type 측정
        list_type_ops = measure_ops(
            lambda: registry.list_by_type(ModelType.YOLO),
            iterations=10_000,
        )

        result.ok(
            "P4-3 list_all/list_by_type (200개)",
            f"list_all: {list_all_ops:,.0f} ops/sec, list_by_type: {list_type_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P4-3 list_all/list_by_type", str(e))

    # P4-4. unregister 처리량
    try:
        registry = _make_registry(max_models=5000)
        model_ids = []
        for i in range(500):
            info = registry.register(
                name=f"unreg_model_{i}",
                model_type=ModelType.CUSTOM,
                version="1.0.0",
            )
            model_ids.append(info.model_id)

        start = time.perf_counter()
        for mid in model_ids:
            registry.unregister(mid)
        elapsed = time.perf_counter() - start

        ops = len(model_ids) / elapsed
        per_call_us = (elapsed / len(model_ids)) * 1_000_000
        result.ok("P4-4 unregister 처리량 (500개)", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        result.fail("P4-4 unregister", str(e))


# =============================================================================
# [P5] ModelRegistry 대량 등록 성능 (3개)
# =============================================================================
def test_p5_bulk_registration(result: PerformanceTestResult) -> None:
    """대량 등록 성능 테스트."""
    print("\n[P5] ModelRegistry 대량 등록 성능")

    model_types = list(ModelType)

    # P5-1. 100개 모델 등록 시간
    try:
        registry = _make_registry(max_models=5000)
        count = 100

        start = time.perf_counter()
        for i in range(count):
            registry.register(
                name=f"bulk100_{i}",
                model_type=model_types[i % len(model_types)],
                version="1.0.0",
                description=f"성능 테스트 모델 {i}",
                tags=["perf", "test"],
            )
        elapsed = time.perf_counter() - start

        elapsed_ms = elapsed * 1000
        ops = count / elapsed
        result.ok("P5-1 100개 등록", f"{elapsed_ms:.1f}ms 소요, {ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P5-1 100개 등록", str(e))

    # P5-2. 500개 모델 등록 시간
    try:
        registry = _make_registry(max_models=5000)
        count = 500

        start = time.perf_counter()
        for i in range(count):
            registry.register(
                name=f"bulk500_{i}",
                model_type=model_types[i % len(model_types)],
                version="1.0.0",
                description=f"대량 등록 테스트 {i}",
                tags=["bulk", "perf"],
            )
        elapsed = time.perf_counter() - start

        elapsed_ms = elapsed * 1000
        ops = count / elapsed
        # 500개 등록 후 list_all 속도도 측정
        list_ops = measure_ops(lambda: registry.list_all(), iterations=5_000)
        result.ok(
            "P5-2 500개 등록",
            f"{elapsed_ms:.1f}ms 소요, {ops:,.0f} reg/sec, list_all: {list_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P5-2 500개 등록", str(e))

    # P5-3. 1000개 모델 등록 + get_status 성능
    try:
        registry = _make_registry(max_models=5000)
        count = 1000

        start = time.perf_counter()
        for i in range(count):
            registry.register(
                name=f"bulk1000_{i}",
                model_type=model_types[i % len(model_types)],
                version="1.0.0",
            )
        elapsed = time.perf_counter() - start

        reg_elapsed_ms = elapsed * 1000
        reg_ops = count / elapsed

        # get_status 속도 측정 (1000개 등록 상태)
        status_ops = measure_ops(lambda: registry.get_status(), iterations=5_000)

        result.ok(
            "P5-3 1000개 등록 + get_status",
            f"등록: {reg_elapsed_ms:.1f}ms ({reg_ops:,.0f} reg/sec), "
            f"get_status: {status_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P5-3 1000개 등록", str(e))


# =============================================================================
# [P6] 싱글톤/헬퍼 함수 성능 (3개)
# =============================================================================
def test_p6_singleton_helpers(result: PerformanceTestResult) -> None:
    """싱글톤 및 헬퍼 함수 성능."""
    print("\n[P6] 싱글톤/헬퍼 함수 성능")

    # P6-1. _get_registry 싱글톤 조회 처리량
    try:
        _reset_registry()
        # 첫 호출로 인스턴스 생성
        _ = _get_registry()

        # 이후 반복 조회 성능
        ops = measure_ops(lambda: _get_registry(), iterations=100_000)
        per_call_us = (1.0 / ops) * 1_000_000
        _reset_registry()
        result.ok("P6-1 _get_registry 조회", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        _reset_registry()
        result.fail("P6-1 _get_registry", str(e))

    # P6-2. get_model 헬퍼 처리량
    try:
        _reset_registry()
        registry = _get_registry()
        # 모델 등록
        registry.register(
            name="helper_test",
            model_type=ModelType.YOLO,
            version="1.0.0",
        )

        # 존재하는 모델 조회
        ops_exist = measure_ops(
            lambda: get_model("helper_test:1.0.0"),
            iterations=50_000,
        )
        # 존재하지 않는 모델 조회
        ops_none = measure_ops(
            lambda: get_model("nonexistent:0.0.0"),
            iterations=50_000,
        )

        _reset_registry()
        result.ok(
            "P6-2 get_model 헬퍼",
            f"존재: {ops_exist:,.0f} ops/sec, 미존재: {ops_none:,.0f} ops/sec",
        )
    except Exception as e:
        _reset_registry()
        result.fail("P6-2 get_model", str(e))

    # P6-3. register_model 헬퍼 처리량
    try:
        _reset_registry()

        # 전역 싱글톤 기본 max_models=50이므로 40회 반복
        iterations = 40
        start = time.perf_counter()
        for i in range(iterations):
            register_model(
                name=f"helper_reg_{i}",
                model_type=ModelType.ONNX,
                version="1.0.0",
            )
        elapsed = time.perf_counter() - start

        ops = iterations / elapsed
        per_call_us = (elapsed / iterations) * 1_000_000
        _reset_registry()
        result.ok("P6-3 register_model 헬퍼", f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call")
    except Exception as e:
        _reset_registry()
        result.fail("P6-3 register_model", str(e))


# =============================================================================
# [P7] 멀티스레드 동시 접근 (3개)
# =============================================================================
def test_p7_multithread(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[P7] 멀티스레드 동시 접근")

    # P7-1. 동시 register (4스레드 x 100)
    try:
        registry = _make_registry(max_models=5000)
        errors = []
        n_threads = 4
        n_ops = 100

        def register_worker(tid):
            try:
                for i in range(n_ops):
                    registry.register(
                        name=f"mt_t{tid}_m{i}",
                        model_type=ModelType.YOLO,
                        version="1.0.0",
                    )
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [
            threading.Thread(target=register_worker, args=(tid,))
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러 발생: {errors[:3]}"
        total_registered = registry.model_count
        expected = n_threads * n_ops
        assert total_registered == expected, f"등록 수: {total_registered} != {expected}"

        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok(
            "P7-1 동시 register (4x100)",
            f"{ops:,.0f} ops/sec, 등록 수: {total_registered}, 정확도: 100%",
        )
    except (AssertionError, Exception) as e:
        result.fail("P7-1 동시 register", str(e))

    # P7-2. 동시 get 조회 (4스레드 x 10000)
    try:
        registry = _make_registry(max_models=5000)
        # 사전 등록
        model_ids = []
        for i in range(200):
            info = registry.register(
                name=f"mt_get_{i}",
                model_type=ModelType.PYTORCH,
                version="1.0.0",
            )
            model_ids.append(info.model_id)

        errors = []
        n_threads = 4
        n_ops = 10_000
        results_list = []

        def get_worker(tid):
            try:
                local_start = time.perf_counter()
                for i in range(n_ops):
                    mid = model_ids[i % len(model_ids)]
                    info = registry.get(mid)
                    assert info is not None
                local_elapsed = time.perf_counter() - local_start
                results_list.append(local_elapsed)
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [
            threading.Thread(target=get_worker, args=(tid,))
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러 발생: {errors[:3]}"
        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok("P7-2 동시 get 조회 (4x10000)", f"{ops:,.0f} ops/sec")
    except (AssertionError, Exception) as e:
        result.fail("P7-2 동시 get", str(e))

    # P7-3. 혼합 연산 (register + get + list_all, 4스레드)
    try:
        registry = _make_registry(max_models=5000)
        # 초기 모델 등록
        for i in range(50):
            registry.register(
                name=f"mt_mix_init_{i}",
                model_type=ModelType.ONNX,
                version="1.0.0",
            )

        errors = []
        n_threads = 4
        n_ops = 500

        def mixed_worker(tid):
            try:
                for i in range(n_ops):
                    op = i % 3
                    if op == 0:
                        # 등록
                        registry.register(
                            name=f"mt_mix_t{tid}_m{i}",
                            model_type=ModelType.TFLITE,
                            version="1.0.0",
                        )
                    elif op == 1:
                        # 조회
                        registry.get(f"mt_mix_init_{i % 50}:1.0.0")
                    else:
                        # 목록 조회
                        registry.list_all()
            except Exception as ex:
                errors.append(str(ex))

        start = time.perf_counter()
        threads = [
            threading.Thread(target=mixed_worker, args=(tid,))
            for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        assert len(errors) == 0, f"에러 발생: {errors[:3]}"
        total_ops = n_threads * n_ops
        ops = total_ops / elapsed
        result.ok(
            "P7-3 혼합 연산 (register+get+list, 4x500)",
            f"{ops:,.0f} mixed ops/sec, 최종 등록: {registry.model_count}개",
        )
    except (AssertionError, Exception) as e:
        result.fail("P7-3 혼합 연산", str(e))


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_p8_memory(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. ModelRegistry 단일 인스턴스 메모리
    try:
        gc.collect()
        registry = _make_registry()
        obj_size = get_object_size(registry)

        # ModelInfo 단일 메모리
        version = ModelVersion(major=1, minor=0, patch=0)
        info = ModelInfo(
            model_id="mem_test:1.0.0",
            name="mem_test",
            model_type=ModelType.YOLO,
            version=version,
        )
        info_size = get_object_size(info)

        result.ok(
            "P8-1 단일 인스턴스 메모리",
            f"ModelRegistry: ~{obj_size}B, ModelInfo: ~{info_size}B",
        )
    except Exception as e:
        result.fail("P8-1 인스턴스 메모리", str(e))

    # P8-2. 100개 등록 후 메모리 증가
    try:
        gc.collect()
        registry = _make_registry(max_models=5000)
        base_size = get_object_size(registry)

        model_types = list(ModelType)
        for i in range(100):
            registry.register(
                name=f"mem100_{i}",
                model_type=model_types[i % len(model_types)],
                version="1.0.0",
                description=f"메모리 테스트 모델 {i}",
                tags=["memory", "test"],
            )

        # 등록된 모델 수 확인
        assert registry.model_count == 100

        # 모든 모델의 메모리 샘플링
        models = registry.list_all()
        sample_sizes = [get_object_size(m) for m in models[:10]]
        avg_model_size = sum(sample_sizes) / len(sample_sizes)

        result.ok(
            "P8-2 100개 등록 메모리",
            f"등록 수: {registry.model_count}, 모델 평균: ~{avg_model_size:.0f}B/개, "
            f"Registry 기본: ~{base_size}B",
        )
    except (AssertionError, Exception) as e:
        result.fail("P8-2 100개 등록 메모리", str(e))

    # P8-3. ModelVersion 대량 생성 메모리
    try:
        gc.collect()
        versions = []
        for i in range(1000):
            v = ModelVersion(major=i // 100, minor=(i // 10) % 10, patch=i % 10)
            versions.append(v)

        sample_size = get_object_size(versions[0])
        total_estimated = sample_size * 1000
        # 1000개 ModelVersion < 1MB
        assert total_estimated < 1 * 1024 * 1024, f"{total_estimated / 1024:.1f}KB > 1MB"
        result.ok(
            "P8-3 ModelVersion 1000개 메모리",
            f"개당 ~{sample_size}B, 추정 총 {total_estimated / 1024:.1f}KB",
        )
    except (AssertionError, Exception) as e:
        result.fail("P8-3 ModelVersion 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - model_registry.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [P1] Enum 연산 성능
    test_p1_enum_performance(result)

    # [P2] ModelVersion 생성/비교 성능
    test_p2_model_version_performance(result)

    # [P3] 데이터 클래스 생성 성능
    test_p3_dataclass_creation(result)

    # [P4] ModelRegistry 등록/조회 성능
    test_p4_registry_operations(result)

    # [P5] 대량 등록 성능
    test_p5_bulk_registration(result)

    # [P6] 싱글톤/헬퍼 함수 성능
    test_p6_singleton_helpers(result)

    # [P7] 멀티스레드 동시 접근
    test_p7_multithread(result)

    # [P8] 메모리 사용량
    test_p8_memory(result)

    # 최종 정리
    _reset_registry()

    # 요약 출력
    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
