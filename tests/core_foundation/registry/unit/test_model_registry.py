# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/unit
파일: test_model_registry.py
설명: ModelRegistry 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    - [1] Enum 테스트 (ModelType, ModelStatus, ModelFormat)
    - [2] 상수 테스트
    - [3] ModelVersion 데이터클래스 테스트
    - [4] ModelInfo / ModelConfig / ModelMetrics 데이터클래스 테스트
    - [5] LoadedModel 테스트
    - [6] ModelRegistry 메인 기능 테스트
    - [7] 스레드 안전성 테스트
    - [8] 메모리 누수 테스트
"""

import gc
import sys
import time
import types
import threading
from datetime import datetime, timezone
from pathlib import Path

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈)
# =============================================================================
_mock_time_utils = types.ModuleType("utils.time_utils")
_mock_time_utils.get_current_timestamp = lambda: time.time()


class _MockTimer:
    """utils.time_utils.Timer 모킹 (컨텍스트 매니저 지원)."""

    def __init__(self, name: str = ""):
        self.name = name
        self._start = 0.0
        self._elapsed = 0.0

    def start(self):
        self._start = time.perf_counter()

    def stop(self):
        self._elapsed = (time.perf_counter() - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


_mock_time_utils.Timer = _MockTimer

# utils 패키지도 등록
if "utils" not in sys.modules:
    _mock_utils = types.ModuleType("utils")
    sys.modules["utils"] = _mock_utils
sys.modules["utils.time_utils"] = _mock_time_utils

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
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과"""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# Mock 클래스
# =============================================================================
class MockModel:
    """IModel 프로토콜을 따르는 모킹 모델."""

    def __init__(self, name: str = "mock_model", version: str = "1.0.0"):
        self._name = name
        self._version = version
        self._loaded = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def warmup(self) -> None:
        pass

    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, data):
        return {"result": data}

    def get_info(self):
        return {"name": self._name, "version": self._version}


class MockLoader:
    """IModelLoader 프로토콜을 따르는 모킹 로더."""

    def __init__(self):
        self.load_count = 0
        self.unload_count = 0
        self.warmup_count = 0

    def load(self, model_info):
        self.load_count += 1
        model = MockModel(name=model_info.name, version=str(model_info.version))
        model.load()
        return model

    def unload(self, model):
        self.unload_count += 1
        if hasattr(model, "unload"):
            model.unload()

    def warmup(self, model, iterations):
        self.warmup_count += 1
        for _ in range(iterations):
            pass


class FailingLoader:
    """로드 시 항상 실패하는 모킹 로더."""

    def load(self, model_info):
        raise RuntimeError("의도적 로드 실패")

    def unload(self, model):
        pass

    def warmup(self, model, iterations):
        pass


# =============================================================================
# 헬퍼 함수
# =============================================================================
def _create_registry(**kwargs) -> ModelRegistry:
    """테스트용 레지스트리 생성 헬퍼."""
    return ModelRegistry(**kwargs)


def _register_test_model(
    registry: ModelRegistry,
    name: str = "test-model",
    model_type: ModelType = ModelType.YOLO,
    version: str = "1.0.0",
    **kwargs,
) -> ModelInfo:
    """테스트 모델 등록 헬퍼."""
    return registry.register(
        name=name,
        model_type=model_type,
        version=version,
        **kwargs,
    )


# =============================================================================
# [1] Enum 테스트
# =============================================================================
def test_enum_model_type(result: TestResult) -> None:
    """ModelType, ModelStatus, ModelFormat Enum 테스트."""
    print("\n[1] Enum 테스트")
    _reset_registry()

    # 1-1. ModelType 멤버 존재 확인
    try:
        expected_members = [
            "YOLO", "MEDIAPIPE", "ONNX", "TENSORRT",
            "PYTORCH", "TENSORFLOW", "TFLITE", "OPENVINO", "CUSTOM",
        ]
        for member_name in expected_members:
            assert hasattr(ModelType, member_name), f"ModelType.{member_name} 없음"
        result.ok("ModelType 모든 멤버 존재 확인")
    except Exception as e:
        result.fail("ModelType 모든 멤버 존재 확인", str(e))

    # 1-2. ModelType 값 확인 (문자열 Enum)
    try:
        assert ModelType.YOLO.value == "yolo", f"YOLO 값 불일치: {ModelType.YOLO.value}"
        assert ModelType.MEDIAPIPE.value == "mediapipe"
        assert ModelType.ONNX.value == "onnx"
        assert ModelType.TENSORRT.value == "tensorrt"
        assert ModelType.PYTORCH.value == "pytorch"
        assert ModelType.TENSORFLOW.value == "tensorflow"
        assert ModelType.TFLITE.value == "tflite"
        assert ModelType.OPENVINO.value == "openvino"
        assert ModelType.CUSTOM.value == "custom"
        result.ok("ModelType 값 정확성 확인")
    except Exception as e:
        result.fail("ModelType 값 정확성 확인", str(e))

    # 1-3. ModelType.file_extensions 프로퍼티
    try:
        yolo_ext = ModelType.YOLO.file_extensions
        assert isinstance(yolo_ext, list), "file_extensions는 리스트여야 함"
        assert ".pt" in yolo_ext, "YOLO 확장자에 .pt 포함"
        assert ".onnx" in yolo_ext, "YOLO 확장자에 .onnx 포함"
        onnx_ext = ModelType.ONNX.file_extensions
        assert ".onnx" in onnx_ext, "ONNX 확장자에 .onnx 포함"
        trt_ext = ModelType.TENSORRT.file_extensions
        assert ".engine" in trt_ext, "TENSORRT 확장자에 .engine 포함"
        custom_ext = ModelType.CUSTOM.file_extensions
        assert "*" in custom_ext, "CUSTOM 확장자에 * 포함"
        result.ok("ModelType.file_extensions 프로퍼티")
    except Exception as e:
        result.fail("ModelType.file_extensions 프로퍼티", str(e))

    # 1-4. ModelType.supports_gpu 프로퍼티
    try:
        assert ModelType.YOLO.supports_gpu is True, "YOLO GPU 지원"
        assert ModelType.ONNX.supports_gpu is True, "ONNX GPU 지원"
        assert ModelType.TENSORRT.supports_gpu is True, "TENSORRT GPU 지원"
        assert ModelType.PYTORCH.supports_gpu is True, "PYTORCH GPU 지원"
        assert ModelType.TENSORFLOW.supports_gpu is True, "TENSORFLOW GPU 지원"
        assert ModelType.MEDIAPIPE.supports_gpu is False, "MEDIAPIPE GPU 미지원"
        assert ModelType.TFLITE.supports_gpu is False, "TFLITE GPU 미지원"
        assert ModelType.OPENVINO.supports_gpu is False, "OPENVINO GPU 미지원"
        assert ModelType.CUSTOM.supports_gpu is False, "CUSTOM GPU 미지원"
        result.ok("ModelType.supports_gpu 프로퍼티")
    except Exception as e:
        result.fail("ModelType.supports_gpu 프로퍼티", str(e))

    # 1-5. ModelStatus 멤버 존재 확인
    try:
        expected_statuses = [
            "REGISTERED", "DOWNLOADING", "UNLOADED", "LOADING",
            "WARMING_UP", "READY", "ERROR", "DEPRECATED",
        ]
        for status_name in expected_statuses:
            assert hasattr(ModelStatus, status_name), f"ModelStatus.{status_name} 없음"
        result.ok("ModelStatus 모든 멤버 존재 확인")
    except Exception as e:
        result.fail("ModelStatus 모든 멤버 존재 확인", str(e))

    # 1-6. ModelStatus.is_usable 프로퍼티
    try:
        assert ModelStatus.READY.is_usable is True, "READY 사용 가능"
        assert ModelStatus.WARMING_UP.is_usable is True, "WARMING_UP 사용 가능"
        assert ModelStatus.REGISTERED.is_usable is False, "REGISTERED 사용 불가"
        assert ModelStatus.LOADING.is_usable is False, "LOADING 사용 불가"
        assert ModelStatus.ERROR.is_usable is False, "ERROR 사용 불가"
        assert ModelStatus.UNLOADED.is_usable is False, "UNLOADED 사용 불가"
        assert ModelStatus.DEPRECATED.is_usable is False, "DEPRECATED 사용 불가"
        result.ok("ModelStatus.is_usable 프로퍼티")
    except Exception as e:
        result.fail("ModelStatus.is_usable 프로퍼티", str(e))

    # 1-7. ModelStatus.is_loading 프로퍼티
    try:
        assert ModelStatus.DOWNLOADING.is_loading is True
        assert ModelStatus.LOADING.is_loading is True
        assert ModelStatus.WARMING_UP.is_loading is True
        assert ModelStatus.READY.is_loading is False
        assert ModelStatus.REGISTERED.is_loading is False
        assert ModelStatus.ERROR.is_loading is False
        result.ok("ModelStatus.is_loading 프로퍼티")
    except Exception as e:
        result.fail("ModelStatus.is_loading 프로퍼티", str(e))

    # 1-8. ModelFormat 멤버 및 값 확인
    try:
        assert ModelFormat.WEIGHTS.value == "weights"
        assert ModelFormat.CHECKPOINT.value == "checkpoint"
        assert ModelFormat.SAVED_MODEL.value == "saved_model"
        assert ModelFormat.COMPILED.value == "compiled"
        assert ModelFormat.QUANTIZED.value == "quantized"
        result.ok("ModelFormat 멤버 및 값 확인")
    except Exception as e:
        result.fail("ModelFormat 멤버 및 값 확인", str(e))

    # 1-9. Enum 값 유일성 확인
    try:
        type_values = [m.value for m in ModelType]
        assert len(type_values) == len(set(type_values)), "ModelType 중복 값 존재"
        status_values = [m.value for m in ModelStatus]
        assert len(status_values) == len(set(status_values)), "ModelStatus 중복 값 존재"
        format_values = [m.value for m in ModelFormat]
        assert len(format_values) == len(set(format_values)), "ModelFormat 중복 값 존재"
        result.ok("Enum 값 유일성 확인")
    except Exception as e:
        result.fail("Enum 값 유일성 확인", str(e))

    # 1-10. 문자열 기반 Enum 접근
    try:
        assert ModelType("yolo") == ModelType.YOLO, "문자열 'yolo' → ModelType.YOLO"
        assert ModelType("onnx") == ModelType.ONNX, "문자열 'onnx' → ModelType.ONNX"
        assert ModelStatus("ready") == ModelStatus.READY, "문자열 'ready' → ModelStatus.READY"
        assert ModelFormat("weights") == ModelFormat.WEIGHTS
        # 모든 Enum이 str Enum인지 확인
        assert isinstance(ModelType.YOLO, str), "ModelType은 str Enum"
        assert isinstance(ModelStatus.READY, str), "ModelStatus는 str Enum"
        assert isinstance(ModelFormat.WEIGHTS, str), "ModelFormat은 str Enum"
        result.ok("문자열 기반 Enum 접근 및 str Enum 확인")
    except Exception as e:
        result.fail("문자열 기반 Enum 접근 및 str Enum 확인", str(e))


# =============================================================================
# [2] 상수 테스트
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 유효성 테스트."""
    print("\n[2] 상수 테스트")
    _reset_registry()

    # 2-1. DEFAULT_MAX_MODELS
    try:
        assert isinstance(DEFAULT_MAX_MODELS, int), "DEFAULT_MAX_MODELS는 int"
        assert DEFAULT_MAX_MODELS > 0, f"DEFAULT_MAX_MODELS > 0: {DEFAULT_MAX_MODELS}"
        assert DEFAULT_MAX_MODELS == 50, f"기본값 50: {DEFAULT_MAX_MODELS}"
        result.ok("DEFAULT_MAX_MODELS 유효성")
    except Exception as e:
        result.fail("DEFAULT_MAX_MODELS 유효성", str(e))

    # 2-2. DEFAULT_MODEL_TIMEOUT
    try:
        assert isinstance(DEFAULT_MODEL_TIMEOUT, (int, float)), "DEFAULT_MODEL_TIMEOUT는 숫자"
        assert DEFAULT_MODEL_TIMEOUT > 0, f"DEFAULT_MODEL_TIMEOUT > 0: {DEFAULT_MODEL_TIMEOUT}"
        assert DEFAULT_MODEL_TIMEOUT == 30.0, f"기본값 30.0: {DEFAULT_MODEL_TIMEOUT}"
        result.ok("DEFAULT_MODEL_TIMEOUT 유효성")
    except Exception as e:
        result.fail("DEFAULT_MODEL_TIMEOUT 유효성", str(e))

    # 2-3. DEFAULT_WARMUP_ITERATIONS
    try:
        assert isinstance(DEFAULT_WARMUP_ITERATIONS, int), "DEFAULT_WARMUP_ITERATIONS는 int"
        assert DEFAULT_WARMUP_ITERATIONS >= 0, f">= 0: {DEFAULT_WARMUP_ITERATIONS}"
        assert DEFAULT_WARMUP_ITERATIONS == 3, f"기본값 3: {DEFAULT_WARMUP_ITERATIONS}"
        result.ok("DEFAULT_WARMUP_ITERATIONS 유효성")
    except Exception as e:
        result.fail("DEFAULT_WARMUP_ITERATIONS 유효성", str(e))

    # 2-4. MODEL_CACHE_SIZE_MB
    try:
        assert isinstance(MODEL_CACHE_SIZE_MB, int), "MODEL_CACHE_SIZE_MB는 int"
        assert MODEL_CACHE_SIZE_MB > 0, f"> 0: {MODEL_CACHE_SIZE_MB}"
        assert MODEL_CACHE_SIZE_MB == 2048, f"기본값 2048: {MODEL_CACHE_SIZE_MB}"
        result.ok("MODEL_CACHE_SIZE_MB 유효성")
    except Exception as e:
        result.fail("MODEL_CACHE_SIZE_MB 유효성", str(e))

    # 2-5. 상수 타입 종합 확인
    try:
        assert type(DEFAULT_MAX_MODELS) is int
        assert type(DEFAULT_MODEL_TIMEOUT) is float
        assert type(DEFAULT_WARMUP_ITERATIONS) is int
        assert type(MODEL_CACHE_SIZE_MB) is int
        result.ok("상수 타입 종합 확인")
    except Exception as e:
        result.fail("상수 타입 종합 확인", str(e))


# =============================================================================
# [3] ModelVersion 테스트
# =============================================================================
def test_model_version(result: TestResult) -> None:
    """ModelVersion 데이터클래스 테스트."""
    print("\n[3] ModelVersion 테스트")
    _reset_registry()

    # 3-1. 기본 생성자
    try:
        v = ModelVersion(major=1, minor=2, patch=3)
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None
        assert v.build_metadata is None
        assert v.changelog is None
        assert isinstance(v.created_at, datetime)
        result.ok("ModelVersion 기본 생성자")
    except Exception as e:
        result.fail("ModelVersion 기본 생성자", str(e))

    # 3-2. from_string 파싱 ("1.2.3")
    try:
        v = ModelVersion.from_string("1.2.3")
        assert v.major == 1, f"major: {v.major}"
        assert v.minor == 2, f"minor: {v.minor}"
        assert v.patch == 3, f"patch: {v.patch}"
        result.ok("ModelVersion.from_string 기본 파싱")
    except Exception as e:
        result.fail("ModelVersion.from_string 기본 파싱", str(e))

    # 3-3. from_string 잘못된 포맷 → ValueError
    try:
        raised = False
        try:
            ModelVersion.from_string("1.2")
        except ValueError:
            raised = True
        assert raised, "잘못된 포맷에 ValueError 발생해야 함"

        raised = False
        try:
            ModelVersion.from_string("abc")
        except (ValueError, Exception):
            raised = True
        assert raised, "비숫자 포맷에 에러 발생해야 함"
        result.ok("ModelVersion.from_string 잘못된 포맷 → ValueError")
    except Exception as e:
        result.fail("ModelVersion.from_string 잘못된 포맷 → ValueError", str(e))

    # 3-4. __str__ 출력
    try:
        v = ModelVersion(major=2, minor=0, patch=1)
        assert str(v) == "2.0.1", f"__str__ 불일치: {str(v)}"

        v_pre = ModelVersion(major=1, minor=0, patch=0, prerelease="alpha")
        assert str(v_pre) == "1.0.0-alpha", f"prerelease 포함: {str(v_pre)}"

        v_build = ModelVersion(major=1, minor=0, patch=0, build_metadata="build123")
        assert str(v_build) == "1.0.0+build123", f"build_metadata 포함: {str(v_build)}"

        v_both = ModelVersion(major=1, minor=0, patch=0, prerelease="beta", build_metadata="456")
        assert str(v_both) == "1.0.0-beta+456", f"둘 다 포함: {str(v_both)}"
        result.ok("ModelVersion __str__ 출력")
    except Exception as e:
        result.fail("ModelVersion __str__ 출력", str(e))

    # 3-5. 비교 연산자 (__lt__, __eq__, __gt__)
    try:
        v1 = ModelVersion(1, 0, 0)
        v2 = ModelVersion(2, 0, 0)
        v3 = ModelVersion(1, 1, 0)
        v4 = ModelVersion(1, 0, 1)
        v5 = ModelVersion(1, 0, 0)

        assert v1 < v2, "1.0.0 < 2.0.0"
        assert v1 < v3, "1.0.0 < 1.1.0"
        assert v1 < v4, "1.0.0 < 1.0.1"
        assert v1 == v5, "1.0.0 == 1.0.0"
        assert not (v2 < v1), "2.0.0 < 1.0.0 이 아님"
        assert v2 > v1, "2.0.0 > 1.0.0 (not less and not equal)"
        result.ok("ModelVersion 비교 연산자")
    except Exception as e:
        result.fail("ModelVersion 비교 연산자", str(e))

    # 3-6. 에지 케이스: 0.0.0
    try:
        v_zero = ModelVersion(0, 0, 0)
        assert str(v_zero) == "0.0.0"
        assert v_zero.major == 0
        assert v_zero.minor == 0
        assert v_zero.patch == 0
        result.ok("ModelVersion 에지 케이스: 0.0.0")
    except Exception as e:
        result.fail("ModelVersion 에지 케이스: 0.0.0", str(e))

    # 3-7. 에지 케이스: 큰 버전 999.999.999
    try:
        v_large = ModelVersion(999, 999, 999)
        assert str(v_large) == "999.999.999"
        v_small = ModelVersion(0, 0, 1)
        assert v_small < v_large, "0.0.1 < 999.999.999"
        result.ok("ModelVersion 에지 케이스: 큰 버전 999.999.999")
    except Exception as e:
        result.fail("ModelVersion 에지 케이스: 큰 버전 999.999.999", str(e))

    # 3-8. 프리릴리즈/빌드 메타데이터 from_string 파싱
    try:
        v_pre = ModelVersion.from_string("1.0.0-alpha")
        assert v_pre.major == 1
        assert v_pre.prerelease == "alpha"
        assert v_pre.build_metadata is None

        v_build = ModelVersion.from_string("1.0.0+build.789")
        assert v_build.build_metadata == "build.789"
        assert v_build.prerelease is None

        v_both = ModelVersion.from_string("2.1.0-rc.1+build.123")
        assert v_both.major == 2
        assert v_both.minor == 1
        assert v_both.patch == 0
        assert v_both.prerelease == "rc.1"
        assert v_both.build_metadata == "build.123"
        result.ok("ModelVersion 프리릴리즈/빌드 메타데이터 파싱")
    except Exception as e:
        result.fail("ModelVersion 프리릴리즈/빌드 메타데이터 파싱", str(e))

    # 3-9. 해시 일관성 (같은 값 → 같은 해시)
    try:
        v_a = ModelVersion(1, 2, 3)
        v_b = ModelVersion(1, 2, 3)
        assert hash(v_a) == hash(v_b), "같은 버전은 같은 해시"

        v_c = ModelVersion(1, 2, 4)
        # 다른 버전이 다른 해시를 갖는지 확인 (보장은 아니지만 일반적으로 다름)
        # 핵심은 같은 값이면 같은 해시라는 것
        s = {v_a, v_b}
        assert len(s) == 1, "같은 버전은 set에서 하나"
        s.add(v_c)
        assert len(s) == 2, "다른 버전 추가 시 2개"
        result.ok("ModelVersion 해시 일관성")
    except Exception as e:
        result.fail("ModelVersion 해시 일관성", str(e))

    # 3-10. to_dict 출력
    try:
        v = ModelVersion(major=3, minor=1, patch=4, prerelease="beta", build_metadata="sha.abc")
        d = v.to_dict()
        assert d["major"] == 3
        assert d["minor"] == 1
        assert d["patch"] == 4
        assert d["prerelease"] == "beta"
        assert d["build_metadata"] == "sha.abc"
        assert "version" in d
        assert d["version"] == "3.1.4-beta+sha.abc"
        assert "created_at" in d
        assert "changelog" in d
        result.ok("ModelVersion.to_dict 출력")
    except Exception as e:
        result.fail("ModelVersion.to_dict 출력", str(e))


# =============================================================================
# [4] ModelInfo / ModelConfig / ModelMetrics 데이터클래스 테스트
# =============================================================================
def test_dataclasses(result: TestResult) -> None:
    """ModelInfo, ModelConfig, ModelMetrics 데이터클래스 테스트."""
    print("\n[4] ModelInfo / ModelConfig / ModelMetrics 데이터클래스 테스트")
    _reset_registry()

    # 4-1. ModelConfig 생성 및 기본값
    try:
        config = ModelConfig()
        assert config.device == "cpu"
        assert config.precision == "fp32"
        assert config.batch_size == 1
        assert config.num_threads == 1
        assert config.gpu_id == 0
        assert config.gpu_memory_fraction == 0.8
        assert config.warmup_iterations == DEFAULT_WARMUP_ITERATIONS
        assert config.timeout_seconds == DEFAULT_MODEL_TIMEOUT
        assert config.enable_profiling is False
        assert config.enable_caching is True
        assert config.cache_size_mb == 512
        assert config.confidence_threshold == 0.5
        assert config.nms_threshold == 0.45
        assert config.max_detections == 100
        assert config.input_width == 640
        assert config.input_height == 640
        assert config.normalize_input is True
        assert config.bgr_to_rgb is True
        assert config.extra_params == {}
        result.ok("ModelConfig 생성 및 기본값")
    except Exception as e:
        result.fail("ModelConfig 생성 및 기본값", str(e))

    # 4-2. ModelConfig 커스텀 값
    try:
        config = ModelConfig(
            device="cuda",
            precision="fp16",
            batch_size=4,
            num_threads=8,
            gpu_id=1,
            confidence_threshold=0.7,
            input_width=1280,
            input_height=720,
        )
        assert config.device == "cuda"
        assert config.precision == "fp16"
        assert config.batch_size == 4
        assert config.num_threads == 8
        assert config.gpu_id == 1
        assert config.confidence_threshold == 0.7
        assert config.input_width == 1280
        assert config.input_height == 720
        result.ok("ModelConfig 커스텀 값")
    except Exception as e:
        result.fail("ModelConfig 커스텀 값", str(e))

    # 4-3. ModelConfig.to_dict
    try:
        config = ModelConfig(device="cuda", precision="fp16")
        d = config.to_dict()
        assert d["device"] == "cuda"
        assert d["precision"] == "fp16"
        assert "input_size" in d
        assert d["input_size"] == [640, 640]
        assert "extra_params" in d
        assert isinstance(d, dict)
        result.ok("ModelConfig.to_dict")
    except Exception as e:
        result.fail("ModelConfig.to_dict", str(e))

    # 4-4. ModelMetrics 생성 및 기본값
    try:
        metrics = ModelMetrics()
        assert metrics.total_inferences == 0
        assert metrics.successful_inferences == 0
        assert metrics.failed_inferences == 0
        assert metrics.total_inference_time_ms == 0.0
        assert metrics.min_inference_time_ms == float("inf")
        assert metrics.max_inference_time_ms == 0.0
        assert metrics.current_fps == 0.0
        assert metrics.peak_fps == 0.0
        assert metrics.memory_usage_mb == 0.0
        assert metrics.load_count == 0
        assert metrics.error_count == 0
        result.ok("ModelMetrics 생성 및 기본값")
    except Exception as e:
        result.fail("ModelMetrics 생성 및 기본값", str(e))

    # 4-5. ModelMetrics.record_inference
    try:
        metrics = ModelMetrics()
        metrics.record_inference(duration_ms=10.0, success=True, confidence=0.95)
        assert metrics.total_inferences == 1
        assert metrics.successful_inferences == 1
        assert metrics.failed_inferences == 0
        assert metrics.last_inference_time_ms == 10.0
        assert metrics.min_inference_time_ms == 10.0
        assert metrics.max_inference_time_ms == 10.0
        assert metrics.current_fps > 0
        assert metrics.average_confidence == 0.95

        # 두 번째 추론 기록
        metrics.record_inference(duration_ms=20.0, success=True, confidence=0.85)
        assert metrics.total_inferences == 2
        assert metrics.successful_inferences == 2
        assert metrics.min_inference_time_ms == 10.0
        assert metrics.max_inference_time_ms == 20.0

        # 실패한 추론
        metrics.record_inference(duration_ms=5.0, success=False)
        assert metrics.total_inferences == 3
        assert metrics.failed_inferences == 1
        result.ok("ModelMetrics.record_inference")
    except Exception as e:
        result.fail("ModelMetrics.record_inference", str(e))

    # 4-6. ModelMetrics 계산 프로퍼티
    try:
        metrics = ModelMetrics()
        # 빈 상태
        assert metrics.average_inference_time_ms == 0.0
        assert metrics.success_rate == 0.0
        assert metrics.average_load_time_ms == 0.0

        # 추론 기록 후
        metrics.record_inference(duration_ms=10.0, success=True)
        metrics.record_inference(duration_ms=20.0, success=True)
        assert metrics.average_inference_time_ms == 15.0, \
            f"평균: {metrics.average_inference_time_ms}"
        assert metrics.success_rate == 1.0

        metrics.record_inference(duration_ms=5.0, success=False)
        expected_rate = 2 / 3
        assert abs(metrics.success_rate - expected_rate) < 0.001, \
            f"성공률: {metrics.success_rate}"
        result.ok("ModelMetrics 계산 프로퍼티")
    except Exception as e:
        result.fail("ModelMetrics 계산 프로퍼티", str(e))

    # 4-7. ModelMetrics.record_load / record_unload
    try:
        metrics = ModelMetrics()
        metrics.record_load(duration_ms=500.0)
        assert metrics.load_count == 1
        assert metrics.total_load_time_ms == 500.0
        assert metrics.last_loaded_at is not None

        metrics.record_unload()
        assert metrics.unload_count == 1
        assert metrics.last_unloaded_at is not None

        assert metrics.average_load_time_ms == 500.0
        result.ok("ModelMetrics.record_load / record_unload")
    except Exception as e:
        result.fail("ModelMetrics.record_load / record_unload", str(e))

    # 4-8. ModelMetrics.record_error
    try:
        metrics = ModelMetrics()
        metrics.record_error("테스트 에러")
        assert metrics.error_count == 1
        assert metrics.last_error == "테스트 에러"
        assert metrics.last_error_at is not None

        metrics.record_error("두 번째 에러")
        assert metrics.error_count == 2
        assert metrics.last_error == "두 번째 에러"
        result.ok("ModelMetrics.record_error")
    except Exception as e:
        result.fail("ModelMetrics.record_error", str(e))

    # 4-9. ModelMetrics.update_memory
    try:
        metrics = ModelMetrics()
        metrics.update_memory(100.0)
        assert metrics.memory_usage_mb == 100.0
        assert metrics.peak_memory_mb == 100.0

        metrics.update_memory(200.0)
        assert metrics.memory_usage_mb == 200.0
        assert metrics.peak_memory_mb == 200.0

        metrics.update_memory(150.0)
        assert metrics.memory_usage_mb == 150.0
        assert metrics.peak_memory_mb == 200.0  # 피크는 유지
        result.ok("ModelMetrics.update_memory")
    except Exception as e:
        result.fail("ModelMetrics.update_memory", str(e))

    # 4-10. ModelMetrics.to_dict
    try:
        metrics = ModelMetrics()
        metrics.record_inference(10.0, success=True)
        metrics.record_load(200.0)
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "total_inferences" in d
        assert "average_inference_time_ms" in d
        assert "success_rate" in d
        assert "load_count" in d
        assert d["total_inferences"] == 1
        assert d["load_count"] == 1
        result.ok("ModelMetrics.to_dict")
    except Exception as e:
        result.fail("ModelMetrics.to_dict", str(e))

    # 4-11. ModelInfo 생성
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="test:1.0.0",
            name="test",
            model_type=ModelType.YOLO,
            version=version,
        )
        assert info.model_id == "test:1.0.0"
        assert info.name == "test"
        assert info.model_type == ModelType.YOLO
        assert info.version == version
        assert info.status == ModelStatus.REGISTERED
        assert info.model_format == ModelFormat.WEIGHTS
        assert info.model_path is None
        assert info.tags == []
        assert info.metadata == {}
        assert isinstance(info.config, ModelConfig)
        assert isinstance(info.metrics, ModelMetrics)
        assert isinstance(info.registered_at, datetime)
        assert isinstance(info.updated_at, datetime)
        result.ok("ModelInfo 생성")
    except Exception as e:
        result.fail("ModelInfo 생성", str(e))

    # 4-12. ModelInfo.update_status
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="test:1.0.0",
            name="test",
            model_type=ModelType.YOLO,
            version=version,
        )
        before_update = info.updated_at
        time.sleep(0.01)  # 시간 차이 보장
        info.update_status(ModelStatus.LOADING, "로딩 중...")
        assert info.status == ModelStatus.LOADING
        assert info.status_message == "로딩 중..."
        assert info.updated_at >= before_update
        result.ok("ModelInfo.update_status")
    except Exception as e:
        result.fail("ModelInfo.update_status", str(e))

    # 4-13. ModelInfo.to_dict
    try:
        version = ModelVersion(2, 1, 0)
        info = ModelInfo(
            model_id="yolo-v8:2.1.0",
            name="yolo-v8",
            model_type=ModelType.YOLO,
            version=version,
            description="YOLOv8 모델",
            author="COURTVIEW",
            tags=["detection", "basketball"],
        )
        d = info.to_dict()
        assert isinstance(d, dict)
        assert d["model_id"] == "yolo-v8:2.1.0"
        assert d["name"] == "yolo-v8"
        assert d["model_type"] == "yolo"
        assert d["status"] == "registered"
        assert d["description"] == "YOLOv8 모델"
        assert d["author"] == "COURTVIEW"
        assert d["tags"] == ["detection", "basketball"]
        assert isinstance(d["version"], dict)
        assert isinstance(d["config"], dict)
        assert isinstance(d["metrics"], dict)
        result.ok("ModelInfo.to_dict")
    except Exception as e:
        result.fail("ModelInfo.to_dict", str(e))

    # 4-14. ModelInfo 필드 타입 검증
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="check:1.0.0",
            name="check",
            model_type=ModelType.PYTORCH,
            version=version,
        )
        assert isinstance(info.model_id, str)
        assert isinstance(info.name, str)
        assert isinstance(info.model_type, ModelType)
        assert isinstance(info.version, ModelVersion)
        assert isinstance(info.status, ModelStatus)
        assert isinstance(info.model_format, ModelFormat)
        assert isinstance(info.file_size_mb, float)
        assert isinstance(info.tags, list)
        assert isinstance(info.metadata, dict)
        assert isinstance(info.child_model_ids, list)
        result.ok("ModelInfo 필드 타입 검증")
    except Exception as e:
        result.fail("ModelInfo 필드 타입 검증", str(e))


# =============================================================================
# [5] LoadedModel 테스트
# =============================================================================
def test_loaded_model(result: TestResult) -> None:
    """LoadedModel 데이터클래스 테스트."""
    print("\n[5] LoadedModel 테스트")
    _reset_registry()

    # 5-1. LoadedModel 기본 생성 (model_instance 없이)
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="lm-test:1.0.0",
            name="lm-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        loaded = LoadedModel(model_info=info)
        assert loaded.model_info == info
        assert loaded.model_instance is None
        assert loaded.is_loaded is False
        assert loaded.use_count == 0
        assert loaded.model_id == "lm-test:1.0.0"
        result.ok("LoadedModel 기본 생성 (모델 없이)")
    except Exception as e:
        result.fail("LoadedModel 기본 생성 (모델 없이)", str(e))

    # 5-2. LoadedModel 생성 (model_instance 있음)
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="lm-test2:1.0.0",
            name="lm-test2",
            model_type=ModelType.YOLO,
            version=version,
        )
        mock = MockModel("test", "1.0.0")
        loaded = LoadedModel(model_info=info, model_instance=mock)
        assert loaded.is_loaded is True
        assert loaded.model_instance is mock
        assert loaded.loaded_at is not None  # __post_init__에서 설정됨
        result.ok("LoadedModel 생성 (model_instance 있음)")
    except Exception as e:
        result.fail("LoadedModel 생성 (model_instance 있음)", str(e))

    # 5-3. LoadedModel.is_loaded 프로퍼티
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="prop-test:1.0.0",
            name="prop-test",
            model_type=ModelType.ONNX,
            version=version,
        )
        # model_instance 없음 → is_loaded False
        loaded_empty = LoadedModel(model_info=info)
        assert loaded_empty.is_loaded is False

        # model_instance 있음 → is_loaded True
        loaded_full = LoadedModel(model_info=info, model_instance=MockModel())
        assert loaded_full.is_loaded is True
        result.ok("LoadedModel.is_loaded 프로퍼티")
    except Exception as e:
        result.fail("LoadedModel.is_loaded 프로퍼티", str(e))

    # 5-4. LoadedModel.mark_used 및 use_count 추적
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="use-test:1.0.0",
            name="use-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        loaded = LoadedModel(model_info=info, model_instance=MockModel())
        assert loaded.use_count == 0
        assert loaded.last_used_at is None

        loaded.mark_used()
        assert loaded.use_count == 1
        assert loaded.last_used_at is not None

        first_used = loaded.last_used_at
        time.sleep(0.01)
        loaded.mark_used()
        assert loaded.use_count == 2
        assert loaded.last_used_at >= first_used
        result.ok("LoadedModel.mark_used 및 use_count 추적")
    except Exception as e:
        result.fail("LoadedModel.mark_used 및 use_count 추적", str(e))

    # 5-5. LoadedModel.acquire 컨텍스트 매니저
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="ctx-test:1.0.0",
            name="ctx-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        mock_instance = MockModel()
        loaded = LoadedModel(model_info=info, model_instance=mock_instance)
        assert loaded.use_count == 0

        with loaded.acquire() as model:
            assert model is mock_instance
            assert loaded.use_count == 1

        # 컨텍스트 매니저 종료 후에도 use_count 유지
        assert loaded.use_count == 1
        result.ok("LoadedModel.acquire 컨텍스트 매니저")
    except Exception as e:
        result.fail("LoadedModel.acquire 컨텍스트 매니저", str(e))

    # 5-6. LoadedModel.status 프로퍼티
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="status-test:1.0.0",
            name="status-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        loaded = LoadedModel(model_info=info)
        assert loaded.status == ModelStatus.REGISTERED

        info.update_status(ModelStatus.READY)
        assert loaded.status == ModelStatus.READY
        result.ok("LoadedModel.status 프로퍼티")
    except Exception as e:
        result.fail("LoadedModel.status 프로퍼티", str(e))

    # 5-7. LoadedModel.model_id 프로퍼티
    try:
        version = ModelVersion(2, 0, 0)
        info = ModelInfo(
            model_id="id-test:2.0.0",
            name="id-test",
            model_type=ModelType.PYTORCH,
            version=version,
        )
        loaded = LoadedModel(model_info=info)
        assert loaded.model_id == "id-test:2.0.0"
        result.ok("LoadedModel.model_id 프로퍼티")
    except Exception as e:
        result.fail("LoadedModel.model_id 프로퍼티", str(e))

    # 5-8. LoadedModel 동시 acquire (스레드 안전성)
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="thread-test:1.0.0",
            name="thread-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        mock_instance = MockModel()
        loaded = LoadedModel(model_info=info, model_instance=mock_instance)
        errors = []

        def acquire_model():
            try:
                with loaded.acquire() as model:
                    assert model is mock_instance
                    time.sleep(0.005)
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=acquire_model) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        assert loaded.use_count == 4, f"use_count: {loaded.use_count}"
        result.ok("LoadedModel 동시 acquire (스레드 안전성)")
    except Exception as e:
        result.fail("LoadedModel 동시 acquire (스레드 안전성)", str(e))


# =============================================================================
# [6] ModelRegistry 메인 테스트
# =============================================================================
def test_model_registry(result: TestResult) -> None:
    """ModelRegistry 메인 기능 테스트."""
    print("\n[6] ModelRegistry 메인 테스트")
    _reset_registry()

    # 6-1. 싱글톤 패턴 (_get_registry)
    try:
        _reset_registry()
        r1 = _get_registry()
        r2 = _get_registry()
        assert r1 is r2, "_get_registry 동일 인스턴스 반환"
        _reset_registry()
        result.ok("싱글톤 패턴 (_get_registry)")
    except Exception as e:
        result.fail("싱글톤 패턴 (_get_registry)", str(e))

    # 6-2. _reset_registry
    try:
        _reset_registry()
        r1 = _get_registry()
        _reset_registry()
        r2 = _get_registry()
        assert r1 is not r2, "_reset_registry 후 새 인스턴스"
        _reset_registry()
        result.ok("_reset_registry 동작")
    except Exception as e:
        result.fail("_reset_registry 동작", str(e))

    # 6-3. register 기본
    try:
        registry = _create_registry()
        info = registry.register(
            name="yolo-basketball",
            model_type=ModelType.YOLO,
            version="1.0.0",
            description="농구 탐지 모델",
        )
        assert isinstance(info, ModelInfo)
        assert info.name == "yolo-basketball"
        assert info.model_type == ModelType.YOLO
        assert info.status == ModelStatus.REGISTERED
        assert info.model_id == "yolo-basketball:1.0.0"
        assert info.description == "농구 탐지 모델"
        assert registry.model_count == 1
        result.ok("register 기본")
    except Exception as e:
        result.fail("register 기본", str(e))

    # 6-4. register 중복 → ValueError
    try:
        registry = _create_registry()
        registry.register(name="dup-model", model_type=ModelType.YOLO, version="1.0.0")
        raised = False
        try:
            registry.register(name="dup-model", model_type=ModelType.YOLO, version="1.0.0")
        except ValueError:
            raised = True
        assert raised, "중복 등록 시 ValueError 발생해야 함"
        result.ok("register 중복 → ValueError")
    except Exception as e:
        result.fail("register 중복 → ValueError", str(e))

    # 6-5. register 최대 개수 초과 → ValueError
    try:
        registry = _create_registry(max_models=2)
        registry.register(name="m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="m2", model_type=ModelType.ONNX, version="1.0.0")
        raised = False
        try:
            registry.register(name="m3", model_type=ModelType.PYTORCH, version="1.0.0")
        except ValueError as ve:
            raised = True
            assert "초과" in str(ve), f"에러 메시지에 '초과' 포함: {ve}"
        assert raised, "최대 개수 초과 시 ValueError 발생해야 함"
        result.ok("register 최대 개수 초과 → ValueError")
    except Exception as e:
        result.fail("register 최대 개수 초과 → ValueError", str(e))

    # 6-6. get (model_id 로 조회)
    try:
        registry = _create_registry()
        registered = registry.register(
            name="get-test",
            model_type=ModelType.ONNX,
            version="2.0.0",
        )
        found = registry.get("get-test:2.0.0")
        assert found is not None
        assert found.model_id == "get-test:2.0.0"
        assert found is registered

        # 존재하지 않는 모델
        not_found = registry.get("nonexistent:1.0.0")
        assert not_found is None
        result.ok("get (model_id 조회)")
    except Exception as e:
        result.fail("get (model_id 조회)", str(e))

    # 6-7. get_by_name
    try:
        registry = _create_registry()
        registry.register(name="named-model", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="named-model", model_type=ModelType.YOLO, version="2.0.0")

        # 이름만으로 조회 → 최신 버전
        found = registry.get_by_name("named-model")
        assert found is not None
        assert str(found.version) == "2.0.0"

        # 특정 버전 조회
        found_v1 = registry.get_by_name("named-model", version="1.0.0")
        assert found_v1 is not None
        assert str(found_v1.version) == "1.0.0"

        # 존재하지 않는 이름
        not_found = registry.get_by_name("no-such-model")
        assert not_found is None
        result.ok("get_by_name")
    except Exception as e:
        result.fail("get_by_name", str(e))

    # 6-8. list_all
    try:
        registry = _create_registry()
        registry.register(name="list-m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="list-m2", model_type=ModelType.ONNX, version="1.0.0")
        registry.register(name="list-m3", model_type=ModelType.PYTORCH, version="1.0.0")
        all_models = registry.list_all()
        assert len(all_models) == 3
        names = [m.name for m in all_models]
        assert "list-m1" in names
        assert "list-m2" in names
        assert "list-m3" in names
        result.ok("list_all")
    except Exception as e:
        result.fail("list_all", str(e))

    # 6-9. list_by_type
    try:
        registry = _create_registry()
        registry.register(name="type-yolo1", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="type-yolo2", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="type-onnx1", model_type=ModelType.ONNX, version="1.0.0")
        yolo_models = registry.list_by_type(ModelType.YOLO)
        assert len(yolo_models) == 2
        onnx_models = registry.list_by_type(ModelType.ONNX)
        assert len(onnx_models) == 1
        empty = registry.list_by_type(ModelType.PYTORCH)
        assert len(empty) == 0
        result.ok("list_by_type")
    except Exception as e:
        result.fail("list_by_type", str(e))

    # 6-10. list_by_status
    try:
        registry = _create_registry()
        info1 = registry.register(name="status-m1", model_type=ModelType.YOLO, version="1.0.0")
        info2 = registry.register(name="status-m2", model_type=ModelType.ONNX, version="1.0.0")
        info2.update_status(ModelStatus.READY)

        registered = registry.list_by_status(ModelStatus.REGISTERED)
        assert len(registered) == 1
        ready = registry.list_by_status(ModelStatus.READY)
        assert len(ready) == 1
        result.ok("list_by_status")
    except Exception as e:
        result.fail("list_by_status", str(e))

    # 6-11. list_versions
    try:
        registry = _create_registry()
        registry.register(name="ver-model", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="ver-model", model_type=ModelType.YOLO, version="2.0.0")
        registry.register(name="ver-model", model_type=ModelType.YOLO, version="1.5.0")

        versions = registry.list_versions("ver-model")
        assert len(versions) == 3
        # 정렬 확인 (역순: 최신→오래된)
        assert versions[0] == ModelVersion(2, 0, 0)
        assert versions[1] == ModelVersion(1, 5, 0)
        assert versions[2] == ModelVersion(1, 0, 0)

        # 존재하지 않는 모델
        empty_versions = registry.list_versions("nonexistent")
        assert len(empty_versions) == 0
        result.ok("list_versions")
    except Exception as e:
        result.fail("list_versions", str(e))

    # 6-12. unregister
    try:
        registry = _create_registry()
        registry.register(name="unreg-model", model_type=ModelType.YOLO, version="1.0.0")
        assert registry.model_count == 1

        success = registry.unregister("unreg-model:1.0.0")
        assert success is True
        assert registry.model_count == 0
        assert registry.get("unreg-model:1.0.0") is None

        # 존재하지 않는 모델 해제
        fail_result = registry.unregister("nonexistent:1.0.0")
        assert fail_result is False
        result.ok("unregister")
    except Exception as e:
        result.fail("unregister", str(e))

    # 6-13. register_loader
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        # 내부 확인: _model_loaders에 등록되었는지
        assert ModelType.YOLO in registry._model_loaders
        assert registry._model_loaders[ModelType.YOLO] is loader
        result.ok("register_loader")
    except Exception as e:
        result.fail("register_loader", str(e))

    # 6-14. load_model (로더 등록 후)
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="load-test", model_type=ModelType.YOLO, version="1.0.0")

        loaded = registry.load("load-test:1.0.0")
        assert isinstance(loaded, LoadedModel)
        assert loaded.is_loaded is True
        assert loaded.model_info.status == ModelStatus.READY
        assert loader.load_count == 1
        assert loader.warmup_count == 1  # 기본 warmup_iterations > 0
        assert registry.loaded_count == 1
        result.ok("load_model (로더 등록 후)")
    except Exception as e:
        result.fail("load_model (로더 등록 후)", str(e))

    # 6-15. load_model 로더 미등록 → RuntimeError
    try:
        registry = _create_registry()
        registry.register(name="no-loader", model_type=ModelType.PYTORCH, version="1.0.0")

        raised = False
        try:
            registry.load("no-loader:1.0.0")
        except RuntimeError as re:
            raised = True
            assert "로더" in str(re), f"에러 메시지에 '로더' 포함: {re}"
        assert raised, "로더 미등록 시 RuntimeError 발생해야 함"
        result.ok("load_model 로더 미등록 → RuntimeError")
    except Exception as e:
        result.fail("load_model 로더 미등록 → RuntimeError", str(e))

    # 6-16. load_model 미등록 모델 → KeyError
    try:
        registry = _create_registry()
        raised = False
        try:
            registry.load("nonexistent:1.0.0")
        except KeyError:
            raised = True
        assert raised, "미등록 모델 로드 시 KeyError 발생해야 함"
        result.ok("load_model 미등록 모델 → KeyError")
    except Exception as e:
        result.fail("load_model 미등록 모델 → KeyError", str(e))

    # 6-17. unload
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="unload-test", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("unload-test:1.0.0")
        assert registry.loaded_count == 1

        success = registry.unload("unload-test:1.0.0")
        assert success is True
        assert registry.loaded_count == 0
        assert loader.unload_count == 1

        model_info = registry.get("unload-test:1.0.0")
        assert model_info.status == ModelStatus.UNLOADED
        result.ok("unload")
    except Exception as e:
        result.fail("unload", str(e))

    # 6-18. get_loaded
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="get-loaded-test", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("get-loaded-test:1.0.0")

        loaded = registry.get_loaded("get-loaded-test:1.0.0")
        assert loaded is not None
        assert loaded.is_loaded is True
        assert loaded.model_id == "get-loaded-test:1.0.0"

        # 로드되지 않은 모델
        not_loaded = registry.get_loaded("nonexistent:1.0.0")
        assert not_loaded is None
        result.ok("get_loaded")
    except Exception as e:
        result.fail("get_loaded", str(e))

    # 6-19. list_loaded
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="ll-m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="ll-m2", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("ll-m1:1.0.0")
        registry.load("ll-m2:1.0.0")

        loaded_list = registry.list_loaded()
        assert len(loaded_list) == 2
        assert "ll-m1:1.0.0" in loaded_list
        assert "ll-m2:1.0.0" in loaded_list
        result.ok("list_loaded")
    except Exception as e:
        result.fail("list_loaded", str(e))

    # 6-20. get_status
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="st-m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("st-m1:1.0.0")

        status = registry.get_status()
        assert isinstance(status, dict)
        assert status["registered_models"] == 1
        assert status["loaded_models"] == 1
        assert status["enabled"] is True
        assert "model_types" in status
        assert "yolo" in status["model_types"]
        assert "registered_loaders" in status
        result.ok("get_status")
    except Exception as e:
        result.fail("get_status", str(e))

    # 6-21. shutdown
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="sd-m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.register(name="sd-m2", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("sd-m1:1.0.0")
        registry.load("sd-m2:1.0.0")
        assert registry.loaded_count == 2

        registry.shutdown()
        assert registry.loaded_count == 0
        assert registry.enabled is False
        result.ok("shutdown")
    except Exception as e:
        result.fail("shutdown", str(e))

    # 6-22. 컨텍스트 매니저
    try:
        with _create_registry() as registry:
            loader = MockLoader()
            registry.register_loader(ModelType.ONNX, loader)
            registry.register(name="ctx-m1", model_type=ModelType.ONNX, version="1.0.0")
            registry.load("ctx-m1:1.0.0")
            assert registry.loaded_count == 1
        # __exit__ 후 shutdown 호출
        assert registry.loaded_count == 0
        assert registry.enabled is False
        result.ok("컨텍스트 매니저")
    except Exception as e:
        result.fail("컨텍스트 매니저", str(e))

    # 6-23. model_count / loaded_count 프로퍼티
    try:
        registry = _create_registry()
        assert registry.model_count == 0
        assert registry.loaded_count == 0

        registry.register(name="count-m1", model_type=ModelType.YOLO, version="1.0.0")
        assert registry.model_count == 1
        assert registry.loaded_count == 0

        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.load("count-m1:1.0.0")
        assert registry.loaded_count == 1
        result.ok("model_count / loaded_count 프로퍼티")
    except Exception as e:
        result.fail("model_count / loaded_count 프로퍼티", str(e))

    # 6-24. enabled 프로퍼티 설정
    try:
        registry = _create_registry()
        assert registry.enabled is True
        registry.enabled = False
        assert registry.enabled is False
        registry.enabled = True
        assert registry.enabled is True
        result.ok("enabled 프로퍼티 설정")
    except Exception as e:
        result.fail("enabled 프로퍼티 설정", str(e))

    # 6-25. force_reload 옵션
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="reload-test", model_type=ModelType.YOLO, version="1.0.0")

        # 첫 로드
        loaded1 = registry.load("reload-test:1.0.0")
        assert loader.load_count == 1

        # 동일 모델 다시 로드 (캐시됨)
        loaded2 = registry.load("reload-test:1.0.0")
        assert loader.load_count == 1  # 추가 로드 없음
        assert loaded2 is loaded1

        # 강제 리로드
        loaded3 = registry.load("reload-test:1.0.0", force_reload=True)
        assert loader.load_count == 2  # 다시 로드됨
        assert loaded3 is not loaded1
        result.ok("force_reload 옵션")
    except Exception as e:
        result.fail("force_reload 옵션", str(e))

    # 6-26. register 버전 문자열 자동 파싱
    try:
        registry = _create_registry()
        info = registry.register(
            name="str-ver",
            model_type=ModelType.YOLO,
            version="3.2.1",
        )
        assert info.version.major == 3
        assert info.version.minor == 2
        assert info.version.patch == 1
        assert info.model_id == "str-ver:3.2.1"
        result.ok("register 버전 문자열 자동 파싱")
    except Exception as e:
        result.fail("register 버전 문자열 자동 파싱", str(e))

    # 6-27. register ModelVersion 객체 직접 전달
    try:
        registry = _create_registry()
        ver = ModelVersion(4, 0, 0)
        info = registry.register(
            name="obj-ver",
            model_type=ModelType.YOLO,
            version=ver,
        )
        assert info.version == ver
        assert info.model_id == "obj-ver:4.0.0"
        result.ok("register ModelVersion 객체 직접 전달")
    except Exception as e:
        result.fail("register ModelVersion 객체 직접 전달", str(e))

    # 6-28. 헬퍼 함수 register_model / get_model
    try:
        _reset_registry()
        info = register_model(
            name="helper-model",
            model_type=ModelType.YOLO,
            version="1.0.0",
            description="헬퍼 함수 테스트",
        )
        assert isinstance(info, ModelInfo)
        assert info.name == "helper-model"

        found = get_model("helper-model:1.0.0")
        assert found is not None
        assert found.name == "helper-model"

        not_found = get_model("no-such:0.0.0")
        assert not_found is None
        _reset_registry()
        result.ok("헬퍼 함수 register_model / get_model")
    except Exception as e:
        result.fail("헬퍼 함수 register_model / get_model", str(e))

    # 6-29. unregister 로드된 모델 자동 언로드
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="auto-unload", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("auto-unload:1.0.0")
        assert registry.loaded_count == 1

        success = registry.unregister("auto-unload:1.0.0")
        assert success is True
        assert registry.loaded_count == 0
        assert registry.model_count == 0
        result.ok("unregister 로드된 모델 자동 언로드")
    except Exception as e:
        result.fail("unregister 로드된 모델 자동 언로드", str(e))

    # 6-30. 로드 실패 시 에러 상태 업데이트
    try:
        registry = _create_registry()
        failing = FailingLoader()
        registry.register_loader(ModelType.PYTORCH, failing)
        registry.register(name="fail-load", model_type=ModelType.PYTORCH, version="1.0.0")

        raised = False
        try:
            registry.load("fail-load:1.0.0")
        except RuntimeError:
            raised = True
        assert raised, "로드 실패 시 RuntimeError 발생"

        info = registry.get("fail-load:1.0.0")
        assert info.status == ModelStatus.ERROR
        assert info.metrics.error_count >= 1
        result.ok("로드 실패 시 에러 상태 업데이트")
    except Exception as e:
        result.fail("로드 실패 시 에러 상태 업데이트", str(e))

    # 6-31. cleanup_unused
    try:
        registry = _create_registry(enable_auto_unload=True, auto_unload_threshold=0.01)
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="cleanup-m1", model_type=ModelType.YOLO, version="1.0.0")
        registry.load("cleanup-m1:1.0.0")
        assert registry.loaded_count == 1

        time.sleep(0.05)  # 임계값 초과 대기
        unloaded_count = registry.cleanup_unused(threshold_seconds=0.01)
        assert unloaded_count == 1
        assert registry.loaded_count == 0
        result.ok("cleanup_unused")
    except Exception as e:
        result.fail("cleanup_unused", str(e))

    # 6-32. register 추가 메타데이터 (tags, author, metadata, parent_model_id)
    try:
        registry = _create_registry()
        info = registry.register(
            name="meta-model",
            model_type=ModelType.YOLO,
            version="1.0.0",
            description="메타데이터 테스트",
            author="COURTVIEW",
            tags=["basketball", "detection"],
            metadata={"accuracy": 0.95},
            parent_model_id="base-model:1.0.0",
        )
        assert info.author == "COURTVIEW"
        assert info.tags == ["basketball", "detection"]
        assert info.metadata == {"accuracy": 0.95}
        assert info.parent_model_id == "base-model:1.0.0"
        result.ok("register 추가 메타데이터")
    except Exception as e:
        result.fail("register 추가 메타데이터", str(e))

    # 6-33. register 커스텀 ModelConfig 전달
    try:
        registry = _create_registry()
        custom_config = ModelConfig(
            device="cuda",
            precision="fp16",
            batch_size=8,
            confidence_threshold=0.7,
        )
        info = registry.register(
            name="config-model",
            model_type=ModelType.YOLO,
            version="1.0.0",
            config=custom_config,
        )
        assert info.config.device == "cuda"
        assert info.config.precision == "fp16"
        assert info.config.batch_size == 8
        assert info.config.confidence_threshold == 0.7
        result.ok("register 커스텀 ModelConfig 전달")
    except Exception as e:
        result.fail("register 커스텀 ModelConfig 전달", str(e))

    # 6-34. register 다양한 ModelFormat
    try:
        registry = _create_registry()
        for fmt in ModelFormat:
            info = registry.register(
                name=f"fmt-{fmt.value}",
                model_type=ModelType.YOLO,
                version="1.0.0",
                model_format=fmt,
            )
            assert info.model_format == fmt
        result.ok("register 다양한 ModelFormat")
    except Exception as e:
        result.fail("register 다양한 ModelFormat", str(e))

    # 6-35. 이미 로드된 모델 다시 load → 캐시 반환
    try:
        registry = _create_registry()
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)
        registry.register(name="cache-test", model_type=ModelType.YOLO, version="1.0.0")

        loaded1 = registry.load("cache-test:1.0.0")
        loaded2 = registry.load("cache-test:1.0.0")
        assert loaded1 is loaded2, "이미 로드된 모델 → 동일 객체 반환"
        assert loader.load_count == 1, "로더는 한 번만 호출"
        result.ok("이미 로드된 모델 → 캐시 반환")
    except Exception as e:
        result.fail("이미 로드된 모델 → 캐시 반환", str(e))


# =============================================================================
# [7] 스레드 안전성 테스트
# =============================================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 테스트."""
    print("\n[7] 스레드 안전성 테스트")
    _reset_registry()

    # 7-1. 4개 스레드 동시 register
    try:
        registry = _create_registry(max_models=50)
        errors = []
        barrier = threading.Barrier(4)

        def register_model_thread(thread_id):
            try:
                barrier.wait(timeout=5.0)
                for i in range(5):
                    registry.register(
                        name=f"thread-{thread_id}-model-{i}",
                        model_type=ModelType.YOLO,
                        version="1.0.0",
                    )
            except Exception as ex:
                errors.append(f"Thread-{thread_id}: {ex}")

        threads = [
            threading.Thread(target=register_model_thread, args=(tid,))
            for tid in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        assert registry.model_count == 20, f"모델 수: {registry.model_count}"
        result.ok("4개 스레드 동시 register")
    except Exception as e:
        result.fail("4개 스레드 동시 register", str(e))

    # 7-2. 4개 스레드 동시 get
    try:
        registry = _create_registry()
        for i in range(10):
            registry.register(
                name=f"get-thread-model-{i}",
                model_type=ModelType.YOLO,
                version="1.0.0",
            )
        errors = []
        barrier = threading.Barrier(4)

        def get_model_thread(thread_id):
            try:
                barrier.wait(timeout=5.0)
                for i in range(10):
                    model_id = f"get-thread-model-{i}:1.0.0"
                    found = registry.get(model_id)
                    if found is None:
                        errors.append(f"Thread-{thread_id}: {model_id} not found")
            except Exception as ex:
                errors.append(f"Thread-{thread_id}: {ex}")

        threads = [
            threading.Thread(target=get_model_thread, args=(tid,))
            for tid in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        result.ok("4개 스레드 동시 get")
    except Exception as e:
        result.fail("4개 스레드 동시 get", str(e))

    # 7-3. Register + Unregister 경쟁 조건
    try:
        registry = _create_registry(max_models=50)
        errors = []
        barrier = threading.Barrier(4)

        def register_unregister_thread(thread_id):
            try:
                barrier.wait(timeout=5.0)
                for i in range(10):
                    name = f"race-{thread_id}-{i}"
                    try:
                        registry.register(
                            name=name,
                            model_type=ModelType.YOLO,
                            version="1.0.0",
                        )
                    except ValueError:
                        pass  # 중복 등록은 무시
                    try:
                        registry.unregister(f"{name}:1.0.0")
                    except Exception:
                        pass  # 이미 해제된 경우 무시
            except Exception as ex:
                errors.append(f"Thread-{thread_id}: {ex}")

        threads = [
            threading.Thread(target=register_unregister_thread, args=(tid,))
            for tid in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        result.ok("Register + Unregister 경쟁 조건")
    except Exception as e:
        result.fail("Register + Unregister 경쟁 조건", str(e))

    # 7-4. 동시 register 후 이름 중복 없음 확인
    try:
        registry = _create_registry(max_models=50)
        errors = []
        barrier = threading.Barrier(4)

        def unique_register_thread(thread_id):
            try:
                barrier.wait(timeout=5.0)
                for i in range(5):
                    name = f"unique-{thread_id}-{i}"
                    registry.register(
                        name=name,
                        model_type=ModelType.YOLO,
                        version="1.0.0",
                    )
            except Exception as ex:
                errors.append(f"Thread-{thread_id}: {ex}")

        threads = [
            threading.Thread(target=unique_register_thread, args=(tid,))
            for tid in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"에러: {errors}"
        all_models = registry.list_all()
        model_ids = [m.model_id for m in all_models]
        assert len(model_ids) == len(set(model_ids)), "중복 ID 없음"
        result.ok("동시 register 후 이름 중복 없음 확인")
    except Exception as e:
        result.fail("동시 register 후 이름 중복 없음 확인", str(e))

    # 7-5. 동시 load/unload
    try:
        registry = _create_registry(max_models=50)
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)

        for i in range(4):
            registry.register(
                name=f"lu-model-{i}",
                model_type=ModelType.YOLO,
                version="1.0.0",
            )

        errors = []
        barrier = threading.Barrier(4)

        def load_unload_thread(thread_id):
            try:
                barrier.wait(timeout=5.0)
                model_id = f"lu-model-{thread_id}:1.0.0"
                registry.load(model_id)
                time.sleep(0.01)
                registry.unload(model_id)
            except Exception as ex:
                errors.append(f"Thread-{thread_id}: {ex}")

        threads = [
            threading.Thread(target=load_unload_thread, args=(tid,))
            for tid in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(errors) == 0, f"에러 발생: {errors}"
        assert registry.loaded_count == 0, "모든 모델 언로드됨"
        result.ok("동시 load/unload (0 에러)")
    except Exception as e:
        result.fail("동시 load/unload (0 에러)", str(e))


# =============================================================================
# [8] 메모리 누수 테스트
# =============================================================================
def test_memory_leak(result: TestResult) -> None:
    """메모리 누수 테스트."""
    print("\n[8] 메모리 누수 테스트")
    _reset_registry()

    # 8-1. 1000회 register/unregister 사이클
    try:
        registry = _create_registry(max_models=50)
        for cycle in range(1000):
            name = f"leak-test-{cycle % 50}"
            model_id = f"{name}:1.0.0"
            try:
                registry.register(
                    name=name,
                    model_type=ModelType.YOLO,
                    version="1.0.0",
                )
            except ValueError:
                pass  # 이미 등록된 경우

            registry.unregister(model_id)

        assert registry.model_count == 0, f"사이클 후 남은 모델: {registry.model_count}"
        # 내부 버전 맵도 정리되었는지 확인
        assert len(registry._versions) == 0, f"버전 맵 크기: {len(registry._versions)}"
        result.ok("1000회 register/unregister 사이클")
    except Exception as e:
        result.fail("1000회 register/unregister 사이클", str(e))

    # 8-2. LoadedModel 컨텍스트 매니저 정리
    try:
        version = ModelVersion(1, 0, 0)
        for i in range(100):
            info = ModelInfo(
                model_id=f"cm-leak-{i}:1.0.0",
                name=f"cm-leak-{i}",
                model_type=ModelType.YOLO,
                version=version,
            )
            mock = MockModel()
            loaded = LoadedModel(model_info=info, model_instance=mock)
            with loaded.acquire() as model:
                assert model is not None

        # GC 실행하여 정리
        gc.collect()
        # 메모리 누수 없음을 확인 (명시적 에러 없이 완료)
        result.ok("LoadedModel 컨텍스트 매니저 정리 (100회)")
    except Exception as e:
        result.fail("LoadedModel 컨텍스트 매니저 정리 (100회)", str(e))

    # 8-3. load/unload 사이클 후 캐시 정리
    try:
        registry = _create_registry(max_models=50)
        loader = MockLoader()
        registry.register_loader(ModelType.YOLO, loader)

        for i in range(50):
            name = f"cache-leak-{i}"
            registry.register(name=name, model_type=ModelType.YOLO, version="1.0.0")
            registry.load(f"{name}:1.0.0")

        assert registry.loaded_count == 50

        for i in range(50):
            registry.unload(f"cache-leak-{i}:1.0.0")

        assert registry.loaded_count == 0

        # _loaded_models 딕셔너리가 비어있는지 확인
        assert len(registry._loaded_models) == 0, \
            f"_loaded_models 크기: {len(registry._loaded_models)}"
        result.ok("load/unload 사이클 후 캐시 정리")
    except Exception as e:
        result.fail("load/unload 사이클 후 캐시 정리", str(e))


# =============================================================================
# [9] 프로토콜 인터페이스 테스트
# =============================================================================
def test_protocols(result: TestResult) -> None:
    """IModel / IModelLoader 프로토콜 테스트."""
    print("\n[9] 프로토콜 인터페이스 테스트")
    _reset_registry()

    # 9-1. IModel 프로토콜 runtime_checkable
    try:
        mock = MockModel()
        assert isinstance(mock, IModel), "MockModel은 IModel 프로토콜 구현"
        result.ok("IModel 프로토콜 runtime_checkable")
    except Exception as e:
        result.fail("IModel 프로토콜 runtime_checkable", str(e))

    # 9-2. IModel 프로퍼티 접근
    try:
        mock = MockModel(name="proto-test", version="2.0.0")
        assert mock.name == "proto-test"
        assert mock.version == "2.0.0"
        result.ok("IModel 프로퍼티 접근")
    except Exception as e:
        result.fail("IModel 프로퍼티 접근", str(e))

    # 9-3. IModel 메서드 호출
    try:
        mock = MockModel()
        assert mock.is_loaded() is False
        mock.load()
        assert mock.is_loaded() is True
        mock.unload()
        assert mock.is_loaded() is False
        result.ok("IModel 메서드 호출")
    except Exception as e:
        result.fail("IModel 메서드 호출", str(e))

    # 9-4. IModelLoader 프로토콜 runtime_checkable
    try:
        loader = MockLoader()
        assert isinstance(loader, IModelLoader), "MockLoader는 IModelLoader 프로토콜 구현"
        result.ok("IModelLoader 프로토콜 runtime_checkable")
    except Exception as e:
        result.fail("IModelLoader 프로토콜 runtime_checkable", str(e))

    # 9-5. IModelLoader 전체 워크플로우
    try:
        loader = MockLoader()
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="wf-test:1.0.0",
            name="wf-test",
            model_type=ModelType.YOLO,
            version=version,
        )

        model = loader.load(info)
        assert model is not None
        assert loader.load_count == 1

        loader.warmup(model, 3)
        assert loader.warmup_count == 1

        loader.unload(model)
        assert loader.unload_count == 1
        result.ok("IModelLoader 전체 워크플로우")
    except Exception as e:
        result.fail("IModelLoader 전체 워크플로우", str(e))


# =============================================================================
# [10] 엣지 케이스 및 추가 테스트
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 및 추가 테스트."""
    print("\n[10] 엣지 케이스 및 추가 테스트")
    _reset_registry()

    # 10-1. 빈 레지스트리 상태 조회
    try:
        registry = _create_registry()
        status = registry.get_status()
        assert status["registered_models"] == 0
        assert status["loaded_models"] == 0
        assert status["model_types"] == {}
        assert status["status_counts"] == {}
        result.ok("빈 레지스트리 상태 조회")
    except Exception as e:
        result.fail("빈 레지스트리 상태 조회", str(e))

    # 10-2. unload 미로드 모델 → False
    try:
        registry = _create_registry()
        success = registry.unload("nonexistent:1.0.0")
        assert success is False
        result.ok("unload 미로드 모델 → False")
    except Exception as e:
        result.fail("unload 미로드 모델 → False", str(e))

    # 10-3. 동일 이름 다른 버전 등록
    try:
        registry = _create_registry()
        v1 = registry.register(name="multi-ver", model_type=ModelType.YOLO, version="1.0.0")
        v2 = registry.register(name="multi-ver", model_type=ModelType.YOLO, version="2.0.0")
        v3 = registry.register(name="multi-ver", model_type=ModelType.YOLO, version="3.0.0")

        assert registry.model_count == 3
        assert v1.model_id != v2.model_id
        assert v2.model_id != v3.model_id

        versions = registry.list_versions("multi-ver")
        assert len(versions) == 3
        result.ok("동일 이름 다른 버전 등록")
    except Exception as e:
        result.fail("동일 이름 다른 버전 등록", str(e))

    # 10-4. shutdown 이중 호출
    try:
        registry = _create_registry()
        registry.shutdown()
        # 두 번째 호출이 에러 없이 처리되어야 함
        registry.shutdown()
        assert registry.enabled is False
        result.ok("shutdown 이중 호출")
    except Exception as e:
        result.fail("shutdown 이중 호출", str(e))

    # 10-5. cleanup_unused auto_unload 비활성화
    try:
        registry = _create_registry(enable_auto_unload=False)
        count = registry.cleanup_unused()
        assert count == 0, "auto_unload 비활성화 시 0 반환"
        result.ok("cleanup_unused auto_unload 비활성화")
    except Exception as e:
        result.fail("cleanup_unused auto_unload 비활성화", str(e))

    # 10-6. _generate_model_id 형식 확인
    try:
        registry = _create_registry()
        model_id = registry._generate_model_id("test-model", "1.0.0")
        assert model_id == "test-model:1.0.0", f"ID 형식: {model_id}"
        result.ok("_generate_model_id 형식 확인")
    except Exception as e:
        result.fail("_generate_model_id 형식 확인", str(e))

    # 10-7. ModelVersion 정렬 (sorted 사용)
    try:
        versions = [
            ModelVersion(3, 0, 0),
            ModelVersion(1, 0, 0),
            ModelVersion(2, 0, 0),
            ModelVersion(1, 5, 0),
            ModelVersion(1, 0, 1),
        ]
        sorted_versions = sorted(versions)
        assert sorted_versions[0] == ModelVersion(1, 0, 0)
        assert sorted_versions[1] == ModelVersion(1, 0, 1)
        assert sorted_versions[2] == ModelVersion(1, 5, 0)
        assert sorted_versions[3] == ModelVersion(2, 0, 0)
        assert sorted_versions[4] == ModelVersion(3, 0, 0)
        result.ok("ModelVersion 정렬")
    except Exception as e:
        result.fail("ModelVersion 정렬", str(e))

    # 10-8. ModelType 반복(iteration) 일관성
    try:
        members_first = list(ModelType)
        members_second = list(ModelType)
        assert members_first == members_second, "반복 순서 일관성"
        assert len(members_first) == 9, f"ModelType 멤버 수: {len(members_first)}"
        result.ok("ModelType 반복 일관성")
    except Exception as e:
        result.fail("ModelType 반복 일관성", str(e))

    # 10-9. ModelInfo.calculate_checksum (경로 없음)
    try:
        version = ModelVersion(1, 0, 0)
        info = ModelInfo(
            model_id="cs-test:1.0.0",
            name="cs-test",
            model_type=ModelType.YOLO,
            version=version,
        )
        # model_path가 None인 경우
        checksum = info.calculate_checksum()
        assert checksum is None, "model_path None → checksum None"
        result.ok("ModelInfo.calculate_checksum (경로 없음)")
    except Exception as e:
        result.fail("ModelInfo.calculate_checksum (경로 없음)", str(e))

    # 10-10. ModelMetrics to_dict min_inference_time 기본값 (inf → None)
    try:
        metrics = ModelMetrics()
        d = metrics.to_dict()
        assert d["min_inference_time_ms"] is None, "inf → None 변환"
        result.ok("ModelMetrics to_dict inf → None 변환")
    except Exception as e:
        result.fail("ModelMetrics to_dict inf → None 변환", str(e))

    # 10-11. register_model 전역 헬퍼 + _reset_registry 완전 초기화
    try:
        _reset_registry()
        register_model("global-test", ModelType.YOLO, "1.0.0")
        found = get_model("global-test:1.0.0")
        assert found is not None

        _reset_registry()
        found_after = get_model("global-test:1.0.0")
        assert found_after is None, "_reset_registry 후 조회 시 None"
        _reset_registry()
        result.ok("_reset_registry 완전 초기화 확인")
    except Exception as e:
        result.fail("_reset_registry 완전 초기화 확인", str(e))

    # 10-12. ModelVersion __eq__ 비 ModelVersion 객체 비교
    try:
        v = ModelVersion(1, 0, 0)
        assert (v == "1.0.0") is False, "문자열과 비교 시 False"
        assert (v == 1) is False, "정수와 비교 시 False"
        assert (v == None) is False, "None과 비교 시 False"
        result.ok("ModelVersion __eq__ 비 ModelVersion 비교")
    except Exception as e:
        result.fail("ModelVersion __eq__ 비 ModelVersion 비교", str(e))

    # 10-13. ModelConfig extra_params
    try:
        config = ModelConfig(extra_params={"custom_key": "custom_value", "threshold": 0.8})
        assert config.extra_params["custom_key"] == "custom_value"
        assert config.extra_params["threshold"] == 0.8
        d = config.to_dict()
        assert d["extra_params"]["custom_key"] == "custom_value"
        result.ok("ModelConfig extra_params")
    except Exception as e:
        result.fail("ModelConfig extra_params", str(e))

    # 10-14. ModelInfo 전체 필드 to_dict 검증
    try:
        version = ModelVersion(1, 0, 0)
        config = ModelConfig(device="cuda")
        info = ModelInfo(
            model_id="full:1.0.0",
            name="full",
            model_type=ModelType.YOLO,
            version=version,
            model_format=ModelFormat.COMPILED,
            description="전체 테스트",
            author="테스트",
            license="MIT",
            tags=["a", "b"],
            config=config,
            parent_model_id="parent:1.0.0",
        )
        d = info.to_dict()
        # 필수 키 확인
        required_keys = [
            "model_id", "name", "model_type", "version", "model_path",
            "model_format", "file_size_mb", "checksum", "status",
            "status_message", "description", "author", "license", "tags",
            "metadata", "config", "metrics", "registered_at", "updated_at",
            "parent_model_id", "child_model_ids",
        ]
        for key in required_keys:
            assert key in d, f"to_dict에 '{key}' 키 누락"
        assert d["model_format"] == "compiled"
        assert d["license"] == "MIT"
        result.ok("ModelInfo 전체 필드 to_dict 검증")
    except Exception as e:
        result.fail("ModelInfo 전체 필드 to_dict 검증", str(e))


# =============================================================================
# [11] __all__ Export 검증 테스트
# =============================================================================
def test_exports(result: TestResult) -> None:
    """모듈 Export (__all__) 검증 테스트."""
    print("\n[11] __all__ Export 검증 테스트")
    _reset_registry()

    # 11-1. __all__에 정의된 모든 심볼 임포트 가능
    try:
        import core_foundation.registry.model_registry as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"__all__에 정의된 '{name}' 속성 없음"
        result.ok("__all__ 심볼 존재 확인")
    except Exception as e:
        result.fail("__all__ 심볼 존재 확인", str(e))

    # 11-2. __all__ 목록 포함 확인
    try:
        import core_foundation.registry.model_registry as mod
        expected = [
            "ModelType", "ModelStatus", "ModelFormat",
            "DEFAULT_MAX_MODELS", "DEFAULT_MODEL_TIMEOUT",
            "DEFAULT_WARMUP_ITERATIONS", "MODEL_CACHE_SIZE_MB",
            "ModelInfo", "ModelVersion", "ModelMetrics",
            "ModelConfig", "LoadedModel",
            "IModel", "IModelLoader",
            "ModelRegistry",
            "get_model", "register_model",
            "_get_registry", "_reset_registry",
        ]
        for name in expected:
            assert name in mod.__all__, f"'{name}'이 __all__에 없음"
        result.ok("__all__ 필수 항목 포함 확인")
    except Exception as e:
        result.fail("__all__ 필수 항목 포함 확인", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main():
    result = TestResult()

    test_enum_model_type(result)          # [1] Enum 테스트 (10개)
    test_constants(result)                 # [2] 상수 테스트 (5개)
    test_model_version(result)             # [3] ModelVersion 테스트 (10개)
    test_dataclasses(result)               # [4] 데이터클래스 테스트 (14개)
    test_loaded_model(result)              # [5] LoadedModel 테스트 (8개)
    test_model_registry(result)            # [6] ModelRegistry 메인 (35개)
    test_thread_safety(result)             # [7] 스레드 안전성 (5개)
    test_memory_leak(result)               # [8] 메모리 누수 (3개)
    test_protocols(result)                 # [9] 프로토콜 (5개)
    test_edge_cases(result)                # [10] 엣지 케이스 (14개)
    test_exports(result)                   # [11] Export 검증 (2개)

    result.summary()
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
