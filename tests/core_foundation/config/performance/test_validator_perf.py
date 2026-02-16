# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/performance
파일: test_validator_perf.py
설명: SchemaValidator 및 Pydantic 스키마 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] 스키마 모델 생성 성능
    - [2] SchemaValidator.validate() 성능
    - [3] SchemaValidator.validate_or_raise() 성능
    - [4] 대량 검증 처리량 (Throughput)
    - [5] AppConfig 중첩 스키마 성능
    - [6] 실패 검증 성능
    - [7] 메모리 효율성
    - [8] 직렬화/역직렬화 성능
"""

import gc
import sys
import time
import tracemalloc
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.validator import (
    ValidationStatus,
    ValidationErrorDetail,
    ValidationResult,
    BaseConfigModel,
    LocalDatabaseConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    AppConfig,
    SchemaValidator,
    validate_config,
    get_default_config,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        """테스트 통과"""
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" → {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 성능 측정 유틸리티
# =============================================================================
def measure_time(func, iterations: int = 1000) -> float:
    """함수 실행 시간 측정 (초). 워밍업 포함."""
    # 워밍업 (10% 또는 최소 10회)
    warmup = max(10, iterations // 10)
    for _ in range(warmup):
        func()

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    gc.enable()

    return elapsed


def measure_memory(func, iterations: int = 100) -> float:
    """메모리 사용량 측정 (bytes)."""
    gc.collect()
    tracemalloc.start()
    for _ in range(iterations):
        func()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


# =============================================================================
# [1] 스키마 모델 생성 성능
# =============================================================================
def test_model_creation_performance(result: PerformanceTestResult) -> None:
    """스키마 모델 생성 성능."""
    print("\n[1] 스키마 모델 생성 성능")

    iterations = 5000

    # 1-1. GPUConfig 기본 생성
    try:
        elapsed = measure_time(lambda: GPUConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"GPUConfig 생성 {avg_ms:.4f}ms > 5ms"
        result.ok("GPUConfig 기본 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("GPUConfig 기본 생성", str(e))

    # 1-2. CameraConfig 기본 생성
    try:
        elapsed = measure_time(lambda: CameraConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"CameraConfig 생성 {avg_ms:.4f}ms > 5ms"
        result.ok("CameraConfig 기본 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("CameraConfig 기본 생성", str(e))

    # 1-3. ModelConfig 기본 생성
    try:
        elapsed = measure_time(lambda: ModelConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"ModelConfig 생성 {avg_ms:.4f}ms > 5ms"
        result.ok("ModelConfig 기본 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("ModelConfig 기본 생성", str(e))

    # 1-4. LocalDatabaseConfig 기본 생성
    try:
        elapsed = measure_time(lambda: LocalDatabaseConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"LocalDatabaseConfig 생성 {avg_ms:.4f}ms > 5ms"
        result.ok("LocalDatabaseConfig 기본 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("LocalDatabaseConfig 기본 생성", str(e))

    # 1-5. AnalysisConfig 기본 생성
    try:
        elapsed = measure_time(lambda: AnalysisConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"AnalysisConfig 생성 {avg_ms:.4f}ms > 5ms"
        result.ok("AnalysisConfig 기본 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("AnalysisConfig 기본 생성", str(e))

    # 1-6. AppConfig 통합 생성 (7개 서브 설정 포함)
    try:
        elapsed = measure_time(lambda: AppConfig(), iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 20.0, f"AppConfig 생성 {avg_ms:.4f}ms > 20ms"
        result.ok("AppConfig 통합 생성 (7개 서브)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("AppConfig 통합 생성", str(e))

    # 1-7. GPUConfig 커스텀 값 생성
    try:
        data = {"device_id": 2, "precision": "fp32", "memory_fraction": 0.8}

        def create():
            return GPUConfig(**data)

        elapsed = measure_time(create, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("GPUConfig 커스텀 값 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("GPUConfig 커스텀 값 생성", str(e))


# =============================================================================
# [2] SchemaValidator.validate() 성능
# =============================================================================
def test_validate_performance(result: PerformanceTestResult) -> None:
    """SchemaValidator.validate() 성능."""
    print("\n[2] SchemaValidator.validate() 성능")

    sv = SchemaValidator()
    iterations = 3000

    # 2-1. GPUConfig 검증
    try:
        data = {"device_id": 1, "precision": "fp16", "memory_fraction": 0.9}

        def validate_gpu():
            return sv.validate(data, GPUConfig)

        elapsed = measure_time(validate_gpu, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0, f"GPUConfig 검증 {avg_ms:.4f}ms > 5ms"
        result.ok("GPUConfig validate()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("GPUConfig validate()", str(e))

    # 2-2. CameraConfig 검증
    try:
        data = {"count": 4, "fps": 60, "sync_mode": "software", "codec": "h265"}

        def validate_camera():
            return sv.validate(data, CameraConfig)

        elapsed = measure_time(validate_camera, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("CameraConfig validate()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("CameraConfig validate()", str(e))

    # 2-3. AnalysisConfig 검증 (model_validator 포함)
    try:
        data = {
            "target_fps": 60,
            "min_video_duration": 5,
            "max_video_duration": 3600,
            "supported_formats": ["mp4", "avi"],
        }

        def validate_analysis():
            return sv.validate(data, AnalysisConfig)

        elapsed = measure_time(validate_analysis, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("AnalysisConfig validate()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("AnalysisConfig validate()", str(e))

    # 2-4. AppConfig 중첩 검증
    try:
        data = {
            "app_name": "Perf Test",
            "environment": "testing",
            "gpu": {"device_id": 0, "precision": "fp16"},
            "camera": {"count": 2, "fps": 30},
            "model": {"model_type": "yolo", "device": "cuda"},
            "analysis": {"target_fps": 30},
        }

        def validate_app():
            return sv.validate(data, AppConfig)

        elapsed = measure_time(validate_app, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 20.0, f"AppConfig 검증 {avg_ms:.4f}ms > 20ms"
        result.ok("AppConfig validate() (중첩)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("AppConfig validate()", str(e))

    # 2-5. 빈 딕셔너리 검증 (기본값 적용)
    try:
        def validate_empty():
            return sv.validate({}, GPUConfig)

        elapsed = measure_time(validate_empty, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("빈 딕셔너리 validate()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("빈 딕셔너리 validate()", str(e))


# =============================================================================
# [3] SchemaValidator.validate_or_raise() 성능
# =============================================================================
def test_validate_or_raise_performance(result: PerformanceTestResult) -> None:
    """SchemaValidator.validate_or_raise() 성능."""
    print("\n[3] validate_or_raise() 성능")

    sv = SchemaValidator()
    iterations = 3000

    # 3-1. 성공 케이스
    try:
        data = {"device_id": 0, "precision": "fp16"}

        def validate_or_raise():
            return sv.validate_or_raise(data, GPUConfig)

        elapsed = measure_time(validate_or_raise, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("validate_or_raise() 성공", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("validate_or_raise() 성공", str(e))

    # 3-2. validate_config() 헬퍼 성능
    try:
        data = {"count": 4, "fps": 60}

        def call_helper():
            return validate_config(data, CameraConfig)

        elapsed = measure_time(call_helper, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("validate_config() 헬퍼", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("validate_config() 헬퍼", str(e))

    # 3-3. get_default_config() 성능
    try:
        def call_default():
            return get_default_config(GPUConfig)

        elapsed = measure_time(call_default, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("get_default_config(GPUConfig)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("get_default_config()", str(e))


# =============================================================================
# [4] 대량 검증 처리량 (Throughput)
# =============================================================================
def test_throughput(result: PerformanceTestResult) -> None:
    """대량 검증 처리량."""
    print("\n[4] 대량 검증 처리량")

    sv = SchemaValidator()

    # 4-1. GPUConfig 검증 처리량 (10,000건)
    try:
        count = 10000
        data = {"device_id": 1, "precision": "fp16"}

        gc.disable()
        start = time.perf_counter()
        for _ in range(count):
            sv.validate(data, GPUConfig)
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 1000, f"처리량 {ops_per_sec:.0f} ops/sec < 1,000"
        result.ok(
            f"GPUConfig 검증 처리량 ({count:,}건)",
            f"{ops_per_sec:,.0f} ops/sec ({elapsed:.3f}s)",
        )
    except Exception as e:
        result.fail("GPUConfig 검증 처리량", str(e))

    # 4-2. AppConfig 검증 처리량 (5,000건)
    try:
        count = 5000
        data = {
            "gpu": {"device_id": 0},
            "camera": {"count": 2},
            "model": {"model_type": "yolo"},
        }

        gc.disable()
        start = time.perf_counter()
        for _ in range(count):
            sv.validate(data, AppConfig)
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 200, f"처리량 {ops_per_sec:.0f} ops/sec < 200"
        result.ok(
            f"AppConfig 검증 처리량 ({count:,}건)",
            f"{ops_per_sec:,.0f} ops/sec ({elapsed:.3f}s)",
        )
    except Exception as e:
        result.fail("AppConfig 검증 처리량", str(e))

    # 4-3. 모델 생성 처리량 (10,000건)
    try:
        count = 10000

        gc.disable()
        start = time.perf_counter()
        for _ in range(count):
            GPUConfig()
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 1000, f"처리량 {ops_per_sec:.0f} ops/sec < 1,000"
        result.ok(
            f"GPUConfig 생성 처리량 ({count:,}건)",
            f"{ops_per_sec:,.0f} ops/sec ({elapsed:.3f}s)",
        )
    except Exception as e:
        result.fail("GPUConfig 생성 처리량", str(e))

    # 4-4. validate_field 처리량 (10,000건)
    try:
        count = 10000

        gc.disable()
        start = time.perf_counter()
        for _ in range(count):
            sv.validate_field("fp16", GPUConfig, "precision")
        elapsed = time.perf_counter() - start
        gc.enable()

        ops_per_sec = count / elapsed
        assert ops_per_sec > 1000
        result.ok(
            f"validate_field 처리량 ({count:,}건)",
            f"{ops_per_sec:,.0f} ops/sec ({elapsed:.3f}s)",
        )
    except Exception as e:
        result.fail("validate_field 처리량", str(e))


# =============================================================================
# [5] AppConfig 중첩 스키마 성능
# =============================================================================
def test_nested_schema_performance(result: PerformanceTestResult) -> None:
    """AppConfig 중첩 스키마 성능."""
    print("\n[5] 중첩 스키마 성능")

    iterations = 2000

    # 5-1. 전체 필드 지정 AppConfig
    try:
        full_data = {
            "app_name": "COURTVIEW Desktop",
            "version": "2.0.0",
            "environment": "production",
            "gpu": {
                "device_id": 0, "memory_limit_gb": 12.0, "memory_fraction": 0.9,
                "tensorrt_enabled": True, "precision": "fp16",
            },
            "camera": {
                "count": 4, "resolution_width": 1920, "resolution_height": 1080,
                "fps": 30, "sync_mode": "genlock", "codec": "h264",
            },
            "model": {
                "model_path": "models/yolov8", "model_type": "yolo",
                "device": "cuda", "precision": "fp16", "batch_size": 4,
            },
            "analysis": {
                "target_fps": 30, "max_video_duration": 7200,
                "min_video_duration": 1, "parallel_workers": 8,
            },
            "storage": {
                "data_dir": "data", "max_cache_gb": 100.0,
            },
            "database": {
                "db_path": "data/production.db", "journal_mode": "WAL",
            },
            "logging": {
                "level": "WARNING", "output": "file",
            },
        }

        def create_full():
            return AppConfig(**full_data)

        elapsed = measure_time(create_full, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 30.0, f"전체 필드 AppConfig {avg_ms:.4f}ms > 30ms"
        result.ok("전체 필드 AppConfig 생성", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("전체 필드 AppConfig", str(e))

    # 5-2. model_validate 전체 필드
    try:
        sv = SchemaValidator()

        def validate_full():
            return sv.validate(full_data, AppConfig)

        elapsed = measure_time(validate_full, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 30.0
        result.ok("model_validate 전체 필드 AppConfig", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_validate 전체 필드", str(e))

    # 5-3. model_dump 성능
    try:
        config = AppConfig()

        def dump():
            return config.model_dump()

        elapsed = measure_time(dump, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("AppConfig model_dump()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_dump()", str(e))

    # 5-4. get_schema_info 성능
    try:
        sv = SchemaValidator()

        def schema_info():
            return sv.get_schema_info(AppConfig)

        elapsed = measure_time(schema_info, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("get_schema_info(AppConfig)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("get_schema_info()", str(e))


# =============================================================================
# [6] 실패 검증 성능
# =============================================================================
def test_failure_validation_performance(result: PerformanceTestResult) -> None:
    """실패 검증 성능."""
    print("\n[6] 실패 검증 성능")

    sv = SchemaValidator()
    iterations = 3000

    # 6-1. 단일 오류 검증
    try:
        data = {"device_id": 99}  # 범위 초과

        def validate_single_error():
            return sv.validate(data, GPUConfig)

        elapsed = measure_time(validate_single_error, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 10.0
        result.ok("단일 오류 검증", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("단일 오류 검증", str(e))

    # 6-2. 다중 오류 검증
    try:
        data = {
            "device_id": 99,
            "memory_fraction": 5.0,
            "precision": "invalid",
            "tensorrt_workspace_gb": 100.0,
        }

        def validate_multi_error():
            return sv.validate(data, GPUConfig)

        elapsed = measure_time(validate_multi_error, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 10.0
        result.ok("다중 오류 검증 (4개 오류)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("다중 오류 검증", str(e))

    # 6-3. 성공 vs 실패 성능 비교
    try:
        success_data = {"device_id": 0, "precision": "fp16"}
        fail_data = {"device_id": 99, "precision": "invalid"}

        elapsed_success = measure_time(
            lambda: sv.validate(success_data, GPUConfig), iterations
        )
        elapsed_fail = measure_time(
            lambda: sv.validate(fail_data, GPUConfig), iterations
        )

        avg_success = (elapsed_success / iterations) * 1000
        avg_fail = (elapsed_fail / iterations) * 1000
        ratio = avg_fail / avg_success if avg_success > 0 else 0

        result.ok(
            "성공 vs 실패 비교",
            f"성공={avg_success:.4f}ms, 실패={avg_fail:.4f}ms, 비율={ratio:.2f}x",
        )
    except Exception as e:
        result.fail("성공 vs 실패 비교", str(e))


# =============================================================================
# [7] 메모리 효율성
# =============================================================================
def test_memory_efficiency(result: PerformanceTestResult) -> None:
    """메모리 효율성 테스트."""
    print("\n[7] 메모리 효율성")

    # 7-1. GPUConfig 1,000건 생성 메모리
    try:
        count = 1000
        peak = measure_memory(lambda: GPUConfig(), count)
        peak_mb = peak / (1024 * 1024)
        per_instance_kb = (peak / count) / 1024
        assert peak_mb < 50.0, f"메모리 {peak_mb:.2f}MB > 50MB"
        result.ok(
            f"GPUConfig {count}건 메모리",
            f"피크 {peak_mb:.2f}MB, ~{per_instance_kb:.2f}KB/건",
        )
    except Exception as e:
        result.fail("GPUConfig 메모리", str(e))

    # 7-2. AppConfig 500건 생성 메모리
    try:
        count = 500
        peak = measure_memory(lambda: AppConfig(), count)
        peak_mb = peak / (1024 * 1024)
        per_instance_kb = (peak / count) / 1024
        assert peak_mb < 100.0, f"메모리 {peak_mb:.2f}MB > 100MB"
        result.ok(
            f"AppConfig {count}건 메모리",
            f"피크 {peak_mb:.2f}MB, ~{per_instance_kb:.2f}KB/건",
        )
    except Exception as e:
        result.fail("AppConfig 메모리", str(e))

    # 7-3. SchemaValidator 검증 메모리
    try:
        sv = SchemaValidator()
        data = {"device_id": 0, "precision": "fp16"}
        count = 1000
        peak = measure_memory(lambda: sv.validate(data, GPUConfig), count)
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 50.0
        result.ok(
            f"validate() {count}건 메모리",
            f"피크 {peak_mb:.2f}MB",
        )
    except Exception as e:
        result.fail("validate() 메모리", str(e))

    # 7-4. ValidationResult 메모리
    try:
        count = 1000

        def create_result():
            return ValidationResult(
                status=ValidationStatus.SUCCESS,
                data=None,
                schema_name="MemTest",
            )

        peak = measure_memory(create_result, count)
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 20.0
        result.ok(
            f"ValidationResult {count}건 메모리",
            f"피크 {peak_mb:.2f}MB",
        )
    except Exception as e:
        result.fail("ValidationResult 메모리", str(e))


# =============================================================================
# [8] 직렬화/역직렬화 성능
# =============================================================================
def test_serialization_performance(result: PerformanceTestResult) -> None:
    """직렬화/역직렬화 성능."""
    print("\n[8] 직렬화/역직렬화 성능")

    iterations = 3000

    # 8-1. model_dump 성능
    try:
        config = GPUConfig(device_id=2, precision="fp32")

        def dump():
            return config.model_dump()

        elapsed = measure_time(dump, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 2.0
        result.ok("GPUConfig model_dump()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_dump()", str(e))

    # 8-2. model_dump_json 성능
    try:
        config = GPUConfig(device_id=2, precision="fp32")

        def dump_json():
            return config.model_dump_json()

        elapsed = measure_time(dump_json, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 2.0
        result.ok("GPUConfig model_dump_json()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_dump_json()", str(e))

    # 8-3. model_validate (dict → model) 성능
    try:
        data = {"device_id": 2, "precision": "fp32", "memory_fraction": 0.8}

        def validate_dict():
            return GPUConfig.model_validate(data)

        elapsed = measure_time(validate_dict, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("GPUConfig model_validate(dict)", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_validate(dict)", str(e))

    # 8-4. model_validate_json (JSON → model) 성능
    try:
        import json
        json_str = json.dumps({"device_id": 2, "precision": "fp32"})

        def validate_json():
            return GPUConfig.model_validate_json(json_str)

        elapsed = measure_time(validate_json, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("GPUConfig model_validate_json()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("model_validate_json()", str(e))

    # 8-5. AppConfig model_dump 성능
    try:
        config = AppConfig()

        def dump_app():
            return config.model_dump()

        elapsed = measure_time(dump_app, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 5.0
        result.ok("AppConfig model_dump()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("AppConfig model_dump()", str(e))

    # 8-6. ValidationResult.to_dict() 성능
    try:
        errors = [
            ValidationErrorDetail("f1", "msg1", "t1", "v1"),
            ValidationErrorDetail("f2", "msg2", "t2", "v2"),
            ValidationErrorDetail("f3", "msg3", "t3", "v3"),
        ]
        vr = ValidationResult(
            status=ValidationStatus.FAILED,
            errors=errors,
            schema_name="PerfSchema",
        )

        def to_dict():
            return vr.to_dict()

        elapsed = measure_time(to_dict, iterations)
        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0
        result.ok("ValidationResult.to_dict()", f"{avg_ms:.4f}ms/건")
    except Exception as e:
        result.fail("to_dict()", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """메인 실행."""
    print("=" * 60)
    print("COURTVIEW - SchemaValidator 성능 테스트")
    print("대상: core_foundation/config/validator.py")
    print("=" * 60)

    r = PerformanceTestResult()

    # [1] 모델 생성 성능
    test_model_creation_performance(r)

    # [2] validate() 성능
    test_validate_performance(r)

    # [3] validate_or_raise() 성능
    test_validate_or_raise_performance(r)

    # [4] 처리량
    test_throughput(r)

    # [5] 중첩 스키마 성능
    test_nested_schema_performance(r)

    # [6] 실패 검증 성능
    test_failure_validation_performance(r)

    # [7] 메모리 효율성
    test_memory_efficiency(r)

    # [8] 직렬화 성능
    test_serialization_performance(r)

    r.summary()
    return r.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
