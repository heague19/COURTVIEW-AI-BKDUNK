# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/backends
파일: tensorrt_engine.py
설명: TensorRT 엔진 빌더/캐싱/추론 유틸리티 — 공용 GPU 가속 인프라

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-17
버전: 1.0.0

v1.0.0:
    - ONNX → TensorRT 엔진 변환 (FP16/FP32)
    - GPU 아키텍처별 엔진 직렬화 캐싱
    - 동적 배치 지원 (min/opt/max)
    - CUDA 스트림 기반 비동기 추론
    - 스레드 안전 추론 (threading.Lock)
    - 스트리밍 SHA256 해시 기반 캐시 키

용도:
    ViTPoseBackend와 YOLOv8PoseBackend이 공유하는 TensorRT 가속 유틸리티.
    PoseBackend 서브클래스가 아닌 독립 헬퍼 모듈입니다.

    configs/pose/model.yaml의 optimization.tensorrt 섹션에서 설정을 로드합니다.
    enabled: true일 때만 활성화되며, 비활성화 시 백엔드는 기존 ONNX/PyTorch 경로를 사용합니다.

설정 구조 (configs/pose/model.yaml):
    pose.model.optimization.tensorrt:
        enabled: false
        fp16: true
        workspace_mb: 1024
        cache_path: "pose_estimation/weights/tensorrt_cache"
        batch:
            min: 1
            optimal: 1
            max: 8
        build:
            timeout_seconds: 600
            strict_type_constraints: false
        inference:
            warmup_iterations: 3

v1.0 제한사항:
    - INT8 미지원 (캘리브레이션 데이터셋 필요 → v2.0)
    - DLA 미지원 (Jetson 모바일 GPU → 향후 확장)
    - 멀티 GPU 미지원 (단일 GPU 가정)
"""

# ============================================================
# 표준 라이브러리
# ============================================================
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

# ============================================================
# 서드파티
# ============================================================
import numpy as np

# ============================================================
# shared 임포트
# ============================================================
from shared.exceptions.analysis_exceptions import (
    ModelLoadException,
    ModelInferenceException,
)

# ============================================================
# 타입 체킹 전용 Import (Pylance/Pyright 정적 분석용)
# TYPE_CHECKING = True일 때만 평가 → 런타임 비용 없음
# from __future__ import annotations로 어노테이션은 문자열 처리
# ============================================================
if TYPE_CHECKING:
    import tensorrt as trt
    import pycuda.driver as cuda
    import torch

# ============================================================
# 조건부 Import (TensorRT — 선택적, 런타임)
# ============================================================
try:
    import tensorrt as trt  # type: ignore[no-redef]
    TENSORRT_AVAILABLE = True
except ImportError:
    TENSORRT_AVAILABLE = False

# PyTorch CUDA (우선 사용 — pycuda.autoinit과 CUDA 컨텍스트 충돌 방지)
try:
    import torch  # type: ignore[no-redef]
    TORCH_AVAILABLE = bool(torch.cuda.is_available())
except (ImportError, OSError):
    TORCH_AVAILABLE = False

# CUDA 드라이버 (PyTorch CUDA 사용 불가 시에만 pycuda 초기화)
# pycuda.autoinit은 별도 CUDA 컨텍스트를 생성하여 PyTorch YOLO와 충돌하므로
# PyTorch CUDA가 사용 가능하면 pycuda 초기화를 건너뜀
if not TORCH_AVAILABLE:
    try:
        import pycuda.driver as cuda  # type: ignore[no-redef]
        import pycuda.autoinit  # noqa: F401 — CUDA 컨텍스트 자동 초기화
        PYCUDA_AVAILABLE = True
    except ImportError:
        PYCUDA_AVAILABLE = False
else:
    PYCUDA_AVAILABLE = False

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수
# ============================================================
_DEFAULT_WORKSPACE_MB: int = 1024
_DEFAULT_CACHE_PATH: str = "pose_estimation/weights/tensorrt_cache"
_ENGINE_FILE_EXTENSION: str = ".engine"
_MANIFEST_EXTENSION: str = ".manifest.json"
_HASH_CHUNK_SIZE: int = 65536  # 64KB — 스트리밍 해시 청크
_CACHE_KEY_LENGTH: int = 16  # SHA256의 앞 16자

# TensorRT dtype → NumPy dtype 매핑
_TRT_DTYPE_MAP: dict[str, np.dtype] = {}
if TENSORRT_AVAILABLE:
    _TRT_DTYPE_MAP = {
        trt.float32: np.float32,
        trt.float16: np.float16,
        trt.int32: np.int32,
        trt.int8: np.int8,
        trt.bool: np.bool_,
    }


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(frozen=True, slots=True)
class TensorRTConfig:
    """
    TensorRT 엔진 빌드/추론 설정.

    configs/pose/model.yaml의 optimization.tensorrt 섹션에서 로드됩니다.
    frozen=True로 생성 후 불변입니다.
    """
    # 기본 설정
    enabled: bool = False
    fp16: bool = True
    workspace_mb: int = _DEFAULT_WORKSPACE_MB
    cache_path: str = _DEFAULT_CACHE_PATH

    # 동적 배치 설정
    min_batch_size: int = 1
    optimal_batch_size: int = 1
    max_batch_size: int = 8

    # 빌드 설정
    build_timeout_seconds: float = 600.0
    strict_type_constraints: bool = False

    # 추론 설정
    warmup_iterations: int = 3

    @classmethod
    def from_yaml_dict(cls, config: dict[str, object]) -> TensorRTConfig:
        """
        YAML 딕셔너리에서 설정 생성.

        기존 4개 키(enabled/fp16/workspace_mb/cache_path)와
        신규 하위 섹션(batch/build/inference)을 모두 지원합니다.

        Args:
            config: optimization.tensorrt 섹션 딕셔너리

        Returns:
            TensorRTConfig 인스턴스
        """
        if not config:
            return cls()

        batch = config.get("batch", {})
        build = config.get("build", {})
        inference = config.get("inference", {})

        return cls(
            enabled=config.get("enabled", False),
            fp16=config.get("fp16", True),
            workspace_mb=config.get("workspace_mb", _DEFAULT_WORKSPACE_MB),
            cache_path=config.get("cache_path", _DEFAULT_CACHE_PATH),
            min_batch_size=batch.get("min", 1),
            optimal_batch_size=batch.get("optimal", 1),
            max_batch_size=batch.get("max", 8),
            build_timeout_seconds=build.get("timeout_seconds", 600.0),
            strict_type_constraints=build.get("strict_type_constraints", False),
            warmup_iterations=inference.get("warmup_iterations", 3),
        )


@dataclass(slots=True)
class EngineMetadata:
    """
    캐시된 TensorRT 엔진의 메타데이터.

    엔진 파일과 함께 .manifest.json으로 저장됩니다.
    캐시 적중 시 현재 환경과 비교하여 유효성을 검증합니다.
    """
    onnx_hash: str
    gpu_name: str
    gpu_compute_capability: str
    trt_version: str
    cuda_version: str
    precision: str
    workspace_mb: int
    min_batch: int
    optimal_batch: int
    max_batch: int
    input_shapes: dict[str, list[int]]
    build_timestamp: str
    engine_file_size_bytes: int

    def to_dict(self) -> dict[str, object]:
        """딕셔너리로 변환 (JSON 직렬화용)."""
        return {
            "onnx_hash": self.onnx_hash,
            "gpu_name": self.gpu_name,
            "gpu_compute_capability": self.gpu_compute_capability,
            "trt_version": self.trt_version,
            "cuda_version": self.cuda_version,
            "precision": self.precision,
            "workspace_mb": self.workspace_mb,
            "min_batch": self.min_batch,
            "optimal_batch": self.optimal_batch,
            "max_batch": self.max_batch,
            "input_shapes": self.input_shapes,
            "build_timestamp": self.build_timestamp,
            "engine_file_size_bytes": self.engine_file_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> EngineMetadata:
        """딕셔너리에서 복원."""
        return cls(
            onnx_hash=data["onnx_hash"],
            gpu_name=data["gpu_name"],
            gpu_compute_capability=data["gpu_compute_capability"],
            trt_version=data["trt_version"],
            cuda_version=data["cuda_version"],
            precision=data["precision"],
            workspace_mb=data["workspace_mb"],
            min_batch=data["min_batch"],
            optimal_batch=data["optimal_batch"],
            max_batch=data["max_batch"],
            input_shapes=data["input_shapes"],
            build_timestamp=data["build_timestamp"],
            engine_file_size_bytes=data["engine_file_size_bytes"],
        )


@dataclass(slots=True)
class TensorRTMetrics:
    """TensorRT 엔진 성능 메트릭."""
    total_inferences: int = 0
    total_inference_time_ms: float = 0.0
    min_inference_time_ms: float = float("inf")
    max_inference_time_ms: float = 0.0
    engine_build_time_ms: float = 0.0
    engine_load_time_ms: float = 0.0

    def record_inference(self, elapsed_ms: float) -> None:
        """추론 시간 기록."""
        self.total_inferences += 1
        self.total_inference_time_ms += elapsed_ms
        if elapsed_ms < self.min_inference_time_ms:
            self.min_inference_time_ms = elapsed_ms
        if elapsed_ms > self.max_inference_time_ms:
            self.max_inference_time_ms = elapsed_ms

    @property
    def average_inference_time_ms(self) -> float:
        """평균 추론 시간 (ms)."""
        if self.total_inferences == 0:
            return 0.0
        return self.total_inference_time_ms / self.total_inferences

    @property
    def average_fps(self) -> float:
        """평균 FPS."""
        avg_ms = self.average_inference_time_ms
        if avg_ms <= 0.0:
            return 0.0
        return 1000.0 / avg_ms

    def to_dict(self) -> dict[str, object]:
        """딕셔너리로 변환."""
        return {
            "total_inferences": self.total_inferences,
            "total_inference_time_ms": round(self.total_inference_time_ms, 3),
            "average_inference_time_ms": round(self.average_inference_time_ms, 3),
            "min_inference_time_ms": (
                round(self.min_inference_time_ms, 3)
                if self.min_inference_time_ms != float("inf")
                else 0.0
            ),
            "max_inference_time_ms": round(self.max_inference_time_ms, 3),
            "average_fps": round(self.average_fps, 1),
            "engine_build_time_ms": round(self.engine_build_time_ms, 1),
            "engine_load_time_ms": round(self.engine_load_time_ms, 3),
        }


@dataclass(slots=True)
class _BindingInfo:
    """엔진 I/O 바인딩 정보 (내부용)."""
    name: str
    dtype: np.dtype
    shape: tuple[int, ...]
    is_input: bool
    size_bytes: int
    binding_index: int


# ============================================================
# TensorRTEngine 메인 클래스
# ============================================================
class TensorRTEngine:
    """
    TensorRT 엔진 빌더/캐싱/추론 유틸리티.

    ONNX 모델을 TensorRT 엔진으로 변환하고, 직렬화된 엔진 파일을
    캐싱하여 재빌드 비용을 제거합니다.

    GPU 아키텍처(compute capability), TensorRT 버전, ONNX 모델 해시,
    정밀도, 배치 설정을 모두 포함한 캐시 키로 엔진을 관리합니다.

    스레드 안전: TensorRT execution context는 스레드 안전하지 않으므로
    threading.Lock으로 추론 직렬화를 보장합니다.

    Example:
        >>> config = TensorRTConfig(enabled=True, fp16=True)
        >>> engine = TensorRTEngine(config)
        >>> engine.build_or_load(
        ...     onnx_path="weights/vitpose-b-wholebody.onnx",
        ...     input_shapes={"input": (1, 3, 256, 192)},
        ... )
        >>> output = engine.run_single(input_tensor)
        >>> engine.release()
    """

    def __init__(self, config: TensorRTConfig) -> None:
        """
        TensorRT 엔진 초기화.

        Args:
            config: TensorRTConfig 설정 객체

        Raises:
            ModelLoadException: TensorRT 미설치 시
        """
        if not TENSORRT_AVAILABLE:
            raise ModelLoadException(
                "TensorRT가 설치되지 않았습니다. "
                "pip install tensorrt"
            )

        if not PYCUDA_AVAILABLE and not TORCH_AVAILABLE:
            raise ModelLoadException(
                "CUDA 드라이버를 사용할 수 없습니다. "
                "pip install pycuda 또는 pip install torch"
            )

        self._config: TensorRTConfig = config

        # TensorRT 로거 (WARNING 이상만 출력)
        self._trt_logger: trt.Logger = trt.Logger(trt.Logger.WARNING)

        # 엔진 및 런타임
        self._runtime: trt.Runtime | None = None
        self._engine: trt.ICudaEngine | None = None
        self._context: trt.IExecutionContext | None = None

        # CUDA 스트림
        self._stream: object | None = None

        # I/O 바인딩 정보
        self._input_bindings: dict[str, _BindingInfo] = {}
        self._output_bindings: dict[str, _BindingInfo] = {}

        # GPU 메모리 버퍼 (사전 할당)
        self._device_buffers: dict[str, object] = {}
        self._host_buffers: dict[str, np.ndarray] = {}

        # 메타데이터 및 메트릭
        self._metadata: EngineMetadata | None = None
        self._metrics: TensorRTMetrics = TensorRTMetrics()

        # 스레드 안전
        self._inference_lock: threading.Lock = threading.Lock()

        # 상태
        self._is_ready: bool = False
        self._engine_path: str | None = None

    # --------------------------------------------------------
    # 공개 메서드
    # --------------------------------------------------------
    def build_or_load(
        self,
        onnx_path: str,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> str:
        """
        TensorRT 엔진 빌드 또는 캐시 로드.

        1. 캐시 확인: ONNX 해시 + GPU + TRT 버전 + 설정 일치하면 로드
        2. 불일치 시: ONNX → TensorRT 엔진 빌드 + 직렬화 캐싱

        Args:
            onnx_path: ONNX 모델 파일 경로
            input_shapes: 입력 바인딩별 기본 형태
                         예: {"input": (1, 3, 256, 192)}

        Returns:
            엔진 파일 경로

        Raises:
            ModelLoadException: 빌드/로드 실패 시
        """
        # ONNX 파일 검증
        onnx_resolved = self._resolve_onnx_path(onnx_path)
        if not Path(onnx_resolved).exists():
            raise ModelLoadException(
                f"ONNX 파일을 찾을 수 없습니다: {onnx_resolved}"
            )

        # ONNX 해시 계산
        onnx_hash = self._compute_onnx_hash(onnx_resolved)

        # 캐시 키 생성
        cache_key = self._get_cache_key(onnx_hash, input_shapes)

        # 캐시된 엔진 로드 시도
        cached_engine = self._try_load_cached_engine(cache_key, onnx_hash)
        if cached_engine is not None:
            self._engine = cached_engine
            self._setup_inference(self._engine)
            self._engine_path = str(self._get_engine_cache_path(cache_key))
            self._is_ready = True

            logger.info(
                "TensorRT 캐시 로드 완료: %s (%.1fms)",
                cache_key[:8],
                self._metrics.engine_load_time_ms,
            )
            return self._engine_path

        # 캐시 미스 — 새 엔진 빌드
        logger.info(
            "TensorRT 엔진 빌드 시작 (ONNX=%s, FP16=%s, batch=%d/%d/%d)",
            Path(onnx_resolved).name,
            self._config.fp16,
            self._config.min_batch_size,
            self._config.optimal_batch_size,
            self._config.max_batch_size,
        )

        t0 = time.perf_counter()
        engine = self._build_engine(onnx_resolved, input_shapes)
        build_ms = (time.perf_counter() - t0) * 1000.0
        self._metrics.engine_build_time_ms = build_ms

        logger.info("TensorRT 엔진 빌드 완료 (%.1f초)", build_ms / 1000.0)

        # 캐시에 저장
        engine_path = self._save_engine_to_cache(
            engine, cache_key, onnx_hash, onnx_resolved, input_shapes,
        )

        # 추론 환경 준비
        self._engine = engine
        self._setup_inference(engine)
        self._engine_path = engine_path
        self._is_ready = True

        # 워밍업 — 실패 시 엔진 비활성화 (CUDA 오염 방지)
        if not self._warmup(input_shapes):
            logger.warning("TensorRT 워밍업 실패로 엔진 비활성화")
            self._is_ready = False
            raise ModelLoadException(
                "TensorRT 워밍업 추론 실패: 엔진이 현재 환경과 호환되지 않습니다"
            )

        return engine_path

    def run(self, inputs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """
        TensorRT 추론 실행.

        Args:
            inputs: 입력 텐서 딕셔너리
                    예: {"input": np.ndarray(1, 3, 256, 192)}

        Returns:
            출력 텐서 딕셔너리

        Raises:
            ModelInferenceException: 추론 실패 시
        """
        if not self._is_ready:
            raise ModelInferenceException(
                "TensorRT 엔진이 준비되지 않았습니다. "
                "build_or_load()를 먼저 호출하세요."
            )

        t0 = time.perf_counter()

        with self._inference_lock:
            try:
                result = self._execute_inference(inputs)
            except Exception as e:
                raise ModelInferenceException(
                    f"TensorRT 추론 실패: {e}"
                ) from e

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._metrics.record_inference(elapsed_ms)

        return result

    def run_single(self, input_tensor: np.ndarray) -> np.ndarray:
        """
        단일 입력/단일 출력 추론 (편의 메서드).

        첫 번째 입력 바인딩에 텐서를 넣고, 첫 번째 출력을 반환합니다.
        ViTPoseBackend / YOLOv8Backend에서 주로 사용합니다.

        Args:
            input_tensor: (B, C, H, W) float32 텐서

        Returns:
            첫 번째 출력 텐서
        """
        if not self._input_bindings:
            raise ModelInferenceException(
                "입력 바인딩이 없습니다. 엔진이 올바르게 로드되지 않았습니다."
            )

        # 첫 번째 입력 바인딩 이름
        input_name = next(iter(self._input_bindings))
        results = self.run({input_name: input_tensor})

        # 첫 번째 출력 반환
        output_name = next(iter(self._output_bindings))
        return results[output_name]

    def release(self) -> None:
        """
        엔진 및 GPU 리소스 해제.

        GPU 메모리 버퍼, CUDA 스트림, 실행 컨텍스트를 정리합니다.
        """
        self._free_buffers()

        if self._stream is not None:
            if PYCUDA_AVAILABLE:
                self._stream.synchronize()
            self._stream = None

        self._context = None
        self._engine = None
        self._runtime = None

        self._input_bindings.clear()
        self._output_bindings.clear()
        self._is_ready = False

        logger.debug("TensorRT 엔진 리소스 해제 완료")

    # --------------------------------------------------------
    # 속성
    # --------------------------------------------------------
    @property
    def is_ready(self) -> bool:
        """엔진 추론 준비 여부."""
        return self._is_ready

    @property
    def metrics(self) -> TensorRTMetrics:
        """성능 메트릭."""
        return self._metrics

    @property
    def metadata(self) -> EngineMetadata | None:
        """엔진 메타데이터."""
        return self._metadata

    @property
    def engine_path(self) -> str | None:
        """엔진 파일 경로."""
        return self._engine_path

    @property
    def config(self) -> TensorRTConfig:
        """현재 설정."""
        return self._config

    def get_info(self) -> dict[str, object]:
        """엔진 상태 정보 요약."""
        info: dict[str, object] = {
            "is_ready": self._is_ready,
            "engine_path": self._engine_path,
            "config": {
                "fp16": self._config.fp16,
                "workspace_mb": self._config.workspace_mb,
                "batch": f"{self._config.min_batch_size}/"
                         f"{self._config.optimal_batch_size}/"
                         f"{self._config.max_batch_size}",
            },
            "input_bindings": {
                name: list(b.shape)
                for name, b in self._input_bindings.items()
            },
            "output_bindings": {
                name: list(b.shape)
                for name, b in self._output_bindings.items()
            },
            "metrics": self._metrics.to_dict(),
        }
        if self._metadata is not None:
            info["gpu"] = self._metadata.gpu_name
            info["trt_version"] = self._metadata.trt_version
        return info

    # --------------------------------------------------------
    # 내부 메서드: 엔진 빌드
    # --------------------------------------------------------
    def _build_engine(
        self,
        onnx_path: str,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> trt.ICudaEngine:
        """
        ONNX → TensorRT 엔진 빌드.

        Args:
            onnx_path: ONNX 모델 경로
            input_shapes: 입력 형태

        Returns:
            빌드된 TensorRT 엔진

        Raises:
            ModelLoadException: 빌드 실패
        """
        builder = trt.Builder(self._trt_logger)
        # EXPLICIT_BATCH 플래그 (동적 배치 필수)
        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(network_flags)
        parser = trt.OnnxParser(network, self._trt_logger)

        # ONNX 파싱
        with open(onnx_path, "rb") as f:
            onnx_data = f.read()

        if not parser.parse(onnx_data):
            error_msgs = []
            for i in range(parser.num_errors):
                error_msgs.append(str(parser.get_error(i)))
            raise ModelLoadException(
                f"ONNX 파싱 실패: {'; '.join(error_msgs)}"
            )

        # 빌더 설정 구성
        config = self._configure_builder(builder, network, input_shapes)

        # 엔진 빌드
        serialized_engine = builder.build_serialized_network(network, config)
        if serialized_engine is None:
            raise ModelLoadException("TensorRT 엔진 빌드 실패 (serialized_engine=None)")

        # 역직렬화
        runtime = trt.Runtime(self._trt_logger)
        engine = runtime.deserialize_cuda_engine(serialized_engine)
        if engine is None:
            raise ModelLoadException("TensorRT 엔진 역직렬화 실패")

        self._runtime = runtime
        return engine

    def _configure_builder(
        self,
        builder: trt.Builder,
        network: trt.INetworkDefinition,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> trt.IBuilderConfig:
        """
        빌더 설정 구성.

        워크스페이스, FP16 플래그, 동적 배치 프로파일을 설정합니다.

        Args:
            builder: TRT Builder
            network: 네트워크 정의
            input_shapes: 입력 형태

        Returns:
            빌더 설정
        """
        config = builder.create_builder_config()

        # 워크스페이스 크기 (bytes)
        config.set_memory_pool_limit(
            trt.MemoryPoolType.WORKSPACE,
            self._config.workspace_mb * (1 << 20),
        )

        # FP16 정밀도
        if self._config.fp16:
            if builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
                logger.info("TensorRT FP16 활성화")
            else:
                logger.warning(
                    "GPU가 FP16을 지원하지 않습니다. FP32로 빌드합니다."
                )

        # 정밀도 강제 제약 (비활성이면 TRT가 자동으로 최적 정밀도 선택)
        if self._config.strict_type_constraints:
            config.set_flag(trt.BuilderFlag.STRICT_TYPES)

        # 최적화 프로파일 (동적 배치)
        profile = self._create_optimization_profile(
            builder, network, input_shapes,
        )
        config.add_optimization_profile(profile)

        return config

    def _create_optimization_profile(
        self,
        builder: trt.Builder,
        network: trt.INetworkDefinition,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> trt.IOptimizationProfile:
        """
        동적 배치 최적화 프로파일 생성.

        input_shapes의 batch 차원(dim 0)을 min/opt/max로 설정합니다.

        Args:
            builder: TRT Builder
            network: 네트워크 정의
            input_shapes: 입력 형태 (기본 배치 크기)

        Returns:
            최적화 프로파일
        """
        profile = builder.create_optimization_profile()

        for i in range(network.num_inputs):
            input_tensor = network.get_input(i)
            name = input_tensor.name

            # input_shapes에서 기본 형태 가져오기
            if name in input_shapes:
                base_shape = input_shapes[name]
            else:
                # 네트워크에서 추출 (고정 차원 가정)
                base_shape = tuple(input_tensor.shape)

            # 동적 배치 차원 설정 (dim 0 = batch)
            # ONNX 입력이 static(고정 차원)이면 해당 값을 그대로 사용
            is_dynamic = any(d == -1 for d in input_tensor.shape)
            if is_dynamic:
                min_shape = (self._config.min_batch_size,) + base_shape[1:]
                opt_shape = (self._config.optimal_batch_size,) + base_shape[1:]
                max_shape = (self._config.max_batch_size,) + base_shape[1:]
            else:
                # static 입력 — min/opt/max 동일하게 고정
                min_shape = base_shape
                opt_shape = base_shape
                max_shape = base_shape

            profile.set_shape(name, min_shape, opt_shape, max_shape)

            logger.debug(
                "프로파일 설정: %s — min=%s, opt=%s, max=%s",
                name, min_shape, opt_shape, max_shape,
            )

        return profile

    # --------------------------------------------------------
    # 내부 메서드: 캐시 관리
    # --------------------------------------------------------
    def _get_cache_key(
        self,
        onnx_hash: str,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> str:
        """
        엔진 캐시 키 생성.

        Args:
            onnx_hash: ONNX 파일 SHA256 해시
            input_shapes: 입력 형태

        Returns:
            캐시 키 문자열 (SHA256 앞 16자)
        """
        gpu_name, gpu_cc = self._get_gpu_info()
        trt_version = trt.__version__ if TENSORRT_AVAILABLE else "unknown"
        cuda_version = self._get_cuda_version()
        precision = "fp16" if self._config.fp16 else "fp32"

        # 해시 입력 조립
        key_parts = [
            f"onnx:{onnx_hash}",
            f"gpu:{gpu_name}",
            f"cc:{gpu_cc}",
            f"trt:{trt_version}",
            f"cuda:{cuda_version}",
            f"prec:{precision}",
            f"batch:{self._config.min_batch_size}/"
            f"{self._config.optimal_batch_size}/"
            f"{self._config.max_batch_size}",
            f"ws:{self._config.workspace_mb}",
            f"shapes:{json.dumps(input_shapes, sort_keys=True)}",
        ]
        combined = "|".join(key_parts)
        full_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        return full_hash[:_CACHE_KEY_LENGTH]

    def _compute_onnx_hash(self, onnx_path: str) -> str:
        """
        ONNX 파일 SHA256 해시 계산 (스트리밍).

        대용량 파일(ViTPose-H 2.4GB)도 메모리 효율적으로 처리합니다.

        Args:
            onnx_path: ONNX 파일 경로

        Returns:
            SHA256 해시 문자열 (64자)
        """
        sha256 = hashlib.sha256()
        with open(onnx_path, "rb") as f:
            while True:
                chunk = f.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_gpu_info(self) -> tuple[str, str]:
        """
        GPU 정보 조회.

        Returns:
            (gpu_name, compute_capability) 튜플
        """
        if PYCUDA_AVAILABLE:
            try:
                device = cuda.Device(0)
                name = device.name()
                cc = f"{device.compute_capability()[0]}.{device.compute_capability()[1]}"
                return (name, cc)
            except Exception:
                pass

        if TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
                cc_major, cc_minor = torch.cuda.get_device_capability(0)
                return (name, f"{cc_major}.{cc_minor}")
            except Exception:
                pass

        return ("unknown_gpu", "0.0")

    def _get_cuda_version(self) -> str:
        """CUDA 버전 조회."""
        if TORCH_AVAILABLE and hasattr(torch.version, "cuda") and torch.version.cuda:
            return torch.version.cuda

        if PYCUDA_AVAILABLE:
            try:
                version = cuda.get_version()
                return f"{version // 1000}.{(version % 1000) // 10}"
            except Exception:
                pass

        return "unknown"

    def _get_engine_cache_path(self, cache_key: str) -> Path:
        """캐시 키에서 엔진 파일 경로 생성."""
        project_root = Path(__file__).resolve().parents[2]
        cache_dir = project_root / self._config.cache_path
        return cache_dir / f"{cache_key}{_ENGINE_FILE_EXTENSION}"

    def _get_manifest_path(self, cache_key: str) -> Path:
        """캐시 키에서 매니페스트 경로 생성."""
        project_root = Path(__file__).resolve().parents[2]
        cache_dir = project_root / self._config.cache_path
        return cache_dir / f"{cache_key}{_MANIFEST_EXTENSION}"

    def _try_load_cached_engine(
        self,
        cache_key: str,
        onnx_hash: str,
    ) -> trt.ICudaEngine | None:
        """
        캐시된 엔진 로드 시도.

        Args:
            cache_key: 캐시 키
            onnx_hash: ONNX 파일 해시 (검증용)

        Returns:
            로드된 엔진 또는 None (캐시 미스)
        """
        engine_path = self._get_engine_cache_path(cache_key)
        manifest_path = self._get_manifest_path(cache_key)

        # 파일 존재 확인
        if not engine_path.exists() or not manifest_path.exists():
            return None

        # 매니페스트 검증
        try:
            metadata = self._load_manifest(manifest_path)
        except Exception as e:
            logger.warning("매니페스트 로드 실패: %s", e)
            return None

        if metadata is None:
            return None

        # ONNX 해시 일치 확인
        if metadata.onnx_hash != onnx_hash:
            logger.info("ONNX 해시 불일치 — 캐시 무효화")
            return None

        # GPU/TRT 버전 일치 확인
        gpu_name, gpu_cc = self._get_gpu_info()
        trt_version = trt.__version__
        if metadata.gpu_name != gpu_name or metadata.trt_version != trt_version:
            logger.info(
                "환경 불일치 — 캐시 무효화 (GPU=%s→%s, TRT=%s→%s)",
                metadata.gpu_name, gpu_name,
                metadata.trt_version, trt_version,
            )
            return None

        # 엔진 역직렬화
        t0 = time.perf_counter()
        try:
            runtime = trt.Runtime(self._trt_logger)
            with open(engine_path, "rb") as f:
                engine_data = f.read()
            engine = runtime.deserialize_cuda_engine(engine_data)

            if engine is None:
                logger.warning("캐시 엔진 역직렬화 실패")
                return None

            self._runtime = runtime
            self._metadata = metadata
            self._metrics.engine_load_time_ms = (
                (time.perf_counter() - t0) * 1000.0
            )
            return engine

        except Exception as e:
            logger.warning("캐시 엔진 로드 실패: %s", e)
            return None

    def _save_engine_to_cache(
        self,
        engine: trt.ICudaEngine,
        cache_key: str,
        onnx_hash: str,
        onnx_path: str,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> str:
        """
        엔진을 캐시 디렉토리에 직렬화.

        Args:
            engine: 빌드된 엔진
            cache_key: 캐시 키
            onnx_hash: ONNX 해시
            onnx_path: ONNX 경로
            input_shapes: 입력 형태

        Returns:
            엔진 파일 경로
        """
        engine_path = self._get_engine_cache_path(cache_key)
        manifest_path = self._get_manifest_path(cache_key)

        # 캐시 디렉토리 생성
        engine_path.parent.mkdir(parents=True, exist_ok=True)

        # 엔진 직렬화
        serialized = engine.serialize()
        with open(engine_path, "wb") as f:
            f.write(serialized)

        # 메타데이터 저장
        gpu_name, gpu_cc = self._get_gpu_info()
        metadata = EngineMetadata(
            onnx_hash=onnx_hash,
            gpu_name=gpu_name,
            gpu_compute_capability=gpu_cc,
            trt_version=trt.__version__,
            cuda_version=self._get_cuda_version(),
            precision="fp16" if self._config.fp16 else "fp32",
            workspace_mb=self._config.workspace_mb,
            min_batch=self._config.min_batch_size,
            optimal_batch=self._config.optimal_batch_size,
            max_batch=self._config.max_batch_size,
            input_shapes={k: list(v) for k, v in input_shapes.items()},
            build_timestamp=datetime.now(timezone.utc).isoformat(),
            engine_file_size_bytes=engine_path.stat().st_size,
        )

        self._metadata = metadata
        self._save_manifest(manifest_path, metadata)

        logger.info(
            "TensorRT 엔진 캐싱 완료: %s (%.1fMB)",
            engine_path.name,
            metadata.engine_file_size_bytes / (1024 * 1024),
        )

        return str(engine_path)

    def _load_manifest(self, manifest_path: Path) -> EngineMetadata | None:
        """매니페스트 JSON 로드."""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EngineMetadata.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("매니페스트 파싱 실패: %s", e)
            return None

    def _save_manifest(
        self, manifest_path: Path, metadata: EngineMetadata,
    ) -> None:
        """매니페스트 JSON 저장."""
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

    # --------------------------------------------------------
    # 내부 메서드: 추론 준비
    # --------------------------------------------------------
    def _setup_inference(self, engine: trt.ICudaEngine) -> None:
        """
        추론 환경 준비.

        Context, CUDA Stream, I/O 바인딩, 메모리 버퍼를 초기화합니다.

        Args:
            engine: TensorRT 엔진
        """
        # Execution Context 생성
        self._context = engine.create_execution_context()
        if self._context is None:
            raise ModelLoadException("TensorRT Execution Context 생성 실패")

        # CUDA Stream 생성 (PyTorch 우선 — pycuda 컨텍스트 충돌 방지)
        if TORCH_AVAILABLE and torch.cuda.is_available():
            self._stream = torch.cuda.Stream()
        elif PYCUDA_AVAILABLE:
            self._stream = cuda.Stream()

        # 바인딩 파싱
        self._parse_bindings(engine)

        # 메모리 버퍼 할당
        self._allocate_buffers()

    def _parse_bindings(self, engine: trt.ICudaEngine) -> None:
        """
        엔진 I/O 바인딩 파싱.

        TensorRT 10.x API를 사용합니다.

        Args:
            engine: TensorRT 엔진
        """
        self._input_bindings.clear()
        self._output_bindings.clear()

        num_io = engine.num_io_tensors

        for i in range(num_io):
            name = engine.get_tensor_name(i)
            mode = engine.get_tensor_mode(name)
            shape = tuple(engine.get_tensor_shape(name))
            dtype_trt = engine.get_tensor_dtype(name)
            dtype_np = _TRT_DTYPE_MAP.get(dtype_trt, np.float32)
            is_input = (mode == trt.TensorIOMode.INPUT)

            # 동적 차원(-1)을 max_batch로 대체하여 버퍼 크기 계산
            resolved_shape = tuple(
                self._config.max_batch_size if s == -1 else s
                for s in shape
            )
            elem_count = 1
            for s in resolved_shape:
                elem_count *= s
            size_bytes = elem_count * np.dtype(dtype_np).itemsize

            binding = _BindingInfo(
                name=name,
                dtype=dtype_np,
                shape=resolved_shape,
                is_input=is_input,
                size_bytes=size_bytes,
                binding_index=i,
            )

            if is_input:
                self._input_bindings[name] = binding
            else:
                self._output_bindings[name] = binding

            logger.debug(
                "바인딩[%d]: %s (%s) shape=%s dtype=%s %s",
                i, name, "입력" if is_input else "출력",
                resolved_shape, dtype_np, f"{size_bytes / 1024:.1f}KB",
            )

    def _allocate_buffers(self) -> None:
        """
        Host/Device 메모리 버퍼 사전 할당.

        max_batch_size 기준으로 할당하여 동적 배치에서 재할당이 불필요합니다.
        """
        all_bindings = {
            **self._input_bindings,
            **self._output_bindings,
        }

        for name, binding in all_bindings.items():
            # Host 버퍼 (page-locked memory)
            host_buf = np.empty(binding.shape, dtype=binding.dtype)
            self._host_buffers[name] = host_buf

            # Device 버퍼 (PyTorch 우선 — pycuda 컨텍스트 충돌 방지)
            if TORCH_AVAILABLE and torch.cuda.is_available():
                device_buf = torch.empty(
                    binding.shape,
                    dtype=torch.float32 if binding.dtype == np.float32
                    else torch.float16,
                    device="cuda",
                )
                self._device_buffers[name] = device_buf
            elif PYCUDA_AVAILABLE:
                device_buf = cuda.mem_alloc(binding.size_bytes)
                self._device_buffers[name] = device_buf

    def _free_buffers(self) -> None:
        """Host/Device 메모리 버퍼 해제."""
        # pycuda DeviceAllocation은 __del__에서 자동 해제
        self._device_buffers.clear()
        self._host_buffers.clear()

    # --------------------------------------------------------
    # 내부 메서드: 추론 실행
    # --------------------------------------------------------
    def _execute_inference(
        self, inputs: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """
        TensorRT 추론 실행.

        1. 입력 텐서를 Host 버퍼에 복사
        2. Host → Device 전송 (H2D)
        3. TensorRT 추론 실행
        4. Device → Host 전송 (D2H)
        5. Stream 동기화

        Args:
            inputs: 입력 텐서 딕셔너리

        Returns:
            출력 텐서 딕셔너리
        """
        context = self._context

        # PyTorch 우선 사용 (pycuda와 PyTorch CUDA 컨텍스트 충돌 방지)
        # pycuda.autoinit이 별도 CUDA 컨텍스트를 생성하여 PyTorch YOLO와 충돌
        if TORCH_AVAILABLE and torch.cuda.is_available():
            return self._execute_torch(inputs, context)
        elif PYCUDA_AVAILABLE:
            return self._execute_pycuda(inputs, context)
        else:
            raise ModelInferenceException(
                "CUDA 드라이버를 사용할 수 없습니다."
            )

    def _execute_pycuda(
        self,
        inputs: dict[str, np.ndarray],
        context: trt.IExecutionContext,
    ) -> dict[str, np.ndarray]:
        """pycuda 기반 추론 실행."""
        stream = self._stream

        # 입력 처리: Host → Device
        for name, tensor in inputs.items():
            binding = self._input_bindings[name]
            # 배치 크기에 따른 실제 shape 설정
            actual_shape = tensor.shape
            context.set_input_shape(name, actual_shape)

            # 입력 데이터를 연속 메모리로 변환
            host_data = np.ascontiguousarray(tensor.astype(binding.dtype))
            cuda.memcpy_htod_async(
                self._device_buffers[name], host_data, stream,
            )

        # 텐서 주소 설정 (TRT 10.x API)
        for name, dev_buf in self._device_buffers.items():
            context.set_tensor_address(name, int(dev_buf))

        # 추론 실행
        context.execute_async_v3(stream_handle=stream.handle)

        # 출력 처리: Device → Host
        results: dict[str, np.ndarray] = {}
        for name, binding in self._output_bindings.items():
            # 실제 출력 shape 조회
            output_shape = tuple(context.get_tensor_shape(name))
            host_buf = np.empty(output_shape, dtype=binding.dtype)
            cuda.memcpy_dtoh_async(
                host_buf, self._device_buffers[name], stream,
            )
            results[name] = host_buf

        # 동기화
        stream.synchronize()

        return results

    def _execute_torch(
        self,
        inputs: dict[str, np.ndarray],
        context: trt.IExecutionContext,
    ) -> dict[str, np.ndarray]:
        """PyTorch CUDA 기반 추론 실행 (pycuda 미설치 폴백)."""
        # 입력 텐서를 GPU로 전송
        gpu_inputs: dict[str, torch.Tensor] = {}
        for name, tensor in inputs.items():
            binding = self._input_bindings[name]
            actual_shape = tensor.shape
            context.set_input_shape(name, actual_shape)

            torch_dtype = (
                torch.float32 if binding.dtype == np.float32
                else torch.float16
            )
            gpu_tensor = torch.from_numpy(tensor).to(
                dtype=torch_dtype, device="cuda",
            ).contiguous()
            gpu_inputs[name] = gpu_tensor

        # 출력 텐서 할당
        gpu_outputs: dict[str, torch.Tensor] = {}
        for name, binding in self._output_bindings.items():
            output_shape = tuple(context.get_tensor_shape(name))
            # 동적 shape에서 -1 → 입력 배치 크기로 대체
            first_input = next(iter(inputs.values()))
            batch_size = first_input.shape[0]
            resolved = tuple(
                batch_size if s == -1 else s for s in output_shape
            )
            torch_dtype = (
                torch.float32 if binding.dtype == np.float32
                else torch.float16
            )
            gpu_outputs[name] = torch.empty(
                resolved, dtype=torch_dtype, device="cuda",
            )

        # 텐서 주소 설정
        for name, t in gpu_inputs.items():
            context.set_tensor_address(name, t.data_ptr())
        for name, t in gpu_outputs.items():
            context.set_tensor_address(name, t.data_ptr())

        # 추론 실행
        stream = torch.cuda.current_stream()
        context.execute_async_v3(stream_handle=stream.cuda_stream)

        # 동기화
        stream.synchronize()

        # 결과를 NumPy로 변환
        results: dict[str, np.ndarray] = {}
        for name, t in gpu_outputs.items():
            results[name] = t.cpu().numpy()

        return results

    # --------------------------------------------------------
    # 내부 메서드: 유틸리티
    # --------------------------------------------------------
    def _resolve_onnx_path(self, onnx_path: str) -> str:
        """ONNX 파일 경로 확인."""
        path = Path(onnx_path)
        if path.is_absolute() and path.exists():
            return str(path)

        project_root = Path(__file__).resolve().parents[2]
        candidates = [
            project_root / onnx_path,
            project_root / "weights" / path.name,
            project_root / "pose_estimation" / "weights" / path.name,
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return onnx_path

    def _warmup(self, input_shapes: dict[str, tuple[int, ...]]) -> bool:
        """
        워밍업 추론.

        더미 입력으로 반복 추론하여 GPU 초기화 오버헤드를 제거합니다.

        Returns:
            워밍업 성공 여부
        """
        if self._config.warmup_iterations <= 0:
            return True

        try:
            # 더미 입력 생성
            dummy_inputs: dict[str, np.ndarray] = {}
            for name, shape in input_shapes.items():
                binding = self._input_bindings.get(name)
                dtype = binding.dtype if binding else np.float32
                dummy_inputs[name] = np.zeros(shape, dtype=dtype)

            for _ in range(self._config.warmup_iterations):
                self.run(dummy_inputs)

            # 워밍업 메트릭 리셋
            self._metrics = TensorRTMetrics(
                engine_build_time_ms=self._metrics.engine_build_time_ms,
                engine_load_time_ms=self._metrics.engine_load_time_ms,
            )
            logger.debug(
                "TensorRT 워밍업 완료 (%d회)", self._config.warmup_iterations,
            )
            return True
        except Exception as e:
            logger.warning("TensorRT 워밍업 실패: %s", e)
            # CUDA 상태 복구 (후속 GPU 모듈 오염 방지)
            try:
                if TORCH_AVAILABLE and torch.cuda.is_available():
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                elif PYCUDA_AVAILABLE and self._stream is not None:
                    self._stream.synchronize()
            except Exception:
                pass
            return False

    # --------------------------------------------------------
    # 컨텍스트 매니저
    # --------------------------------------------------------
    def __enter__(self) -> TensorRTEngine:
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """컨텍스트 매니저 종료 — 리소스 해제."""
        self.release()

    def __repr__(self) -> str:
        """문자열 표현."""
        return (
            f"TensorRTEngine("
            f"ready={self._is_ready}, "
            f"fp16={self._config.fp16}, "
            f"batch={self._config.min_batch_size}/"
            f"{self._config.optimal_batch_size}/"
            f"{self._config.max_batch_size}, "
            f"inferences={self._metrics.total_inferences})"
        )


# ============================================================
# 팩토리 함수
# ============================================================
def create_tensorrt_engine(
    yaml_config: dict[str, object],
) -> TensorRTEngine | None:
    """
    YAML 설정에서 TensorRTEngine 생성 팩토리.

    TensorRT가 사용 불가능하거나 비활성화되면 None을 반환합니다.

    Args:
        yaml_config: optimization.tensorrt 섹션 딕셔너리

    Returns:
        TensorRTEngine 또는 None

    Example:
        >>> trt_config = config_loader.get_section(
        ...     "pose.model.optimization.tensorrt"
        ... )
        >>> engine = create_tensorrt_engine(trt_config)
        >>> if engine is not None:
        ...     engine.build_or_load(onnx_path, shapes)
    """
    if not TENSORRT_AVAILABLE:
        logger.info(
            "TensorRT를 사용할 수 없습니다 (미설치). "
            "ONNX Runtime/PyTorch 폴백을 사용합니다."
        )
        return None

    trt_config = TensorRTConfig.from_yaml_dict(yaml_config)
    if not trt_config.enabled:
        logger.debug("TensorRT가 비활성화 상태입니다 (enabled=false)")
        return None

    return TensorRTEngine(config=trt_config)


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # 가용성 플래그
    "TENSORRT_AVAILABLE",
    "PYCUDA_AVAILABLE",

    # 설정
    "TensorRTConfig",

    # 메타데이터/메트릭
    "EngineMetadata",
    "TensorRTMetrics",

    # 메인 클래스
    "TensorRTEngine",

    # 팩토리 함수
    "create_tensorrt_engine",
]

__version__ = "1.0.0"
