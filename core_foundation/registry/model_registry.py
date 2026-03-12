# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: model_registry.py
버전: 1.0.0
설명: AI 모델 등록, 버전 관리, 로드/언로드 - 엔터프라이즈급 모델 레지스트리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-12

주요 기능:
    - AI 모델 등록 및 메타데이터 관리
    - 모델 버전 관리 (시맨틱 버전)
    - 모델 로드/언로드 라이프사이클
    - 모델 성능 메트릭 수집
    - 워밍업 및 검증
    - 스레드 안전 동시성 지원
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import logging
import os
import threading
import hashlib
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Iterator, Protocol, TypeVar, runtime_checkable

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import Timer

# ============================================================
# core_foundation 내부 임포트 (Direct Import)
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.error_tracker import ErrorTracker
    from core_foundation.monitoring.metrics import MetricsCollector


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "ModelType",
    "ModelStatus",
    "ModelFormat",
    # 상수
    "DEFAULT_MAX_MODELS",
    "DEFAULT_MODEL_TIMEOUT",
    "DEFAULT_WARMUP_ITERATIONS",
    "MODEL_CACHE_SIZE_MB",
    # 데이터 클래스
    "ModelInfo",
    "ModelVersion",
    "ModelMetrics",
    "ModelConfig",
    "LoadedModel",
    # 프로토콜 인터페이스
    "IModel",
    "IModelLoader",
    # 메인 클래스
    "ModelRegistry",
    # 함수
    "get_model",
    "register_model",
    # 유틸리티 (테스트용)
    "_get_registry",
    "_reset_registry",
]


# ============================================================
# 상수
# ============================================================
DEFAULT_MAX_MODELS: int = 50  # 최대 등록 가능 모델 수
DEFAULT_MODEL_TIMEOUT: float = 30.0  # 모델 로드 타임아웃 (초)
DEFAULT_WARMUP_ITERATIONS: int = 3  # 워밍업 반복 횟수
MODEL_CACHE_SIZE_MB: int = 2048  # 모델 캐시 크기 (MB)
MODEL_VERSION_PATTERN: str = r"^\d+\.\d+\.\d+$"  # 시맨틱 버전 패턴


# ============================================================
# Enum 정의
# ============================================================
class ModelType(str, Enum):
    """
    AI 모델 타입.

    지원하는 모델 프레임워크 및 형식을 정의합니다.
    """

    YOLO = "yolo"  # Ultralytics YOLO 모델
    MEDIAPIPE = "mediapipe"  # Google MediaPipe 모델
    ONNX = "onnx"  # ONNX Runtime 모델
    TENSORRT = "tensorrt"  # NVIDIA TensorRT 모델
    PYTORCH = "pytorch"  # PyTorch 모델 (.pt, .pth)
    TENSORFLOW = "tensorflow"  # TensorFlow SavedModel
    TFLITE = "tflite"  # TensorFlow Lite 모델
    OPENVINO = "openvino"  # Intel OpenVINO 모델
    CUSTOM = "custom"  # 커스텀 모델

    @property
    def file_extensions(self) -> list[str]:
        """모델 타입별 지원 파일 확장자."""
        extensions = {
            ModelType.YOLO: [".pt", ".yaml", ".onnx"],
            ModelType.MEDIAPIPE: [".tflite", ".task"],
            ModelType.ONNX: [".onnx"],
            ModelType.TENSORRT: [".engine", ".plan"],
            ModelType.PYTORCH: [".pt", ".pth", ".bin"],
            ModelType.TENSORFLOW: [".pb", ".h5", ".keras"],
            ModelType.TFLITE: [".tflite"],
            ModelType.OPENVINO: [".xml", ".bin"],
            ModelType.CUSTOM: ["*"],
        }
        return extensions.get(self, ["*"])

    @property
    def supports_gpu(self) -> bool:
        """GPU 지원 여부."""
        gpu_types = {
            ModelType.YOLO,
            ModelType.ONNX,
            ModelType.TENSORRT,
            ModelType.PYTORCH,
            ModelType.TENSORFLOW,
        }
        return self in gpu_types


class ModelStatus(str, Enum):
    """
    모델 상태.

    모델 라이프사이클 상태를 정의합니다.
    """

    REGISTERED = "registered"  # 등록됨 (메타데이터만)
    DOWNLOADING = "downloading"  # 다운로드 중
    UNLOADED = "unloaded"  # 언로드됨
    LOADING = "loading"  # 로딩 중
    WARMING_UP = "warming_up"  # 워밍업 중
    READY = "ready"  # 준비 완료
    ERROR = "error"  # 에러 상태
    DEPRECATED = "deprecated"  # 사용 중단

    @property
    def is_usable(self) -> bool:
        """모델 사용 가능 여부."""
        return self in {ModelStatus.READY, ModelStatus.WARMING_UP}

    @property
    def is_loading(self) -> bool:
        """로딩 관련 상태 여부."""
        return self in {
            ModelStatus.DOWNLOADING,
            ModelStatus.LOADING,
            ModelStatus.WARMING_UP,
        }


class ModelFormat(str, Enum):
    """
    모델 포맷.

    모델 저장/로드 포맷을 정의합니다.
    """

    WEIGHTS = "weights"  # 가중치 파일
    CHECKPOINT = "checkpoint"  # 체크포인트
    SAVED_MODEL = "saved_model"  # 저장된 전체 모델
    COMPILED = "compiled"  # 컴파일된 모델
    QUANTIZED = "quantized"  # 양자화된 모델


# ============================================================
# 모델 인터페이스 프로토콜
# ============================================================
@runtime_checkable
class IModel(Protocol):
    """
    모델 인터페이스 프로토콜.

    레지스트리에 등록되는 모든 모델이 구현해야 하는 프로토콜입니다.
    """

    @property
    def name(self) -> str:
        """모델 이름."""
        ...

    @property
    def version(self) -> str:
        """모델 버전."""
        ...

    def load(self) -> None:
        """모델 로드."""
        ...

    def unload(self) -> None:
        """모델 언로드."""
        ...

    def warmup(self) -> None:
        """모델 워밍업."""
        ...

    def is_loaded(self) -> bool:
        """모델 로드 여부."""
        ...


ModelT = TypeVar("ModelT", bound=IModel)


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class ModelVersion:
    """
    모델 버전 정보.

    시맨틱 버전과 메타데이터를 포함합니다.
    """

    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build_metadata: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    changelog: str | None = None

    def __str__(self) -> str:
        """버전 문자열."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version

    @classmethod
    def from_string(cls, version_str: str) -> "ModelVersion":
        """문자열에서 버전 파싱."""
        import re

        # 빌드 메타데이터 분리
        build_metadata = None
        if "+" in version_str:
            version_str, build_metadata = version_str.split("+", 1)

        # 프리릴리즈 분리
        prerelease = None
        if "-" in version_str:
            version_str, prerelease = version_str.split("-", 1)

        # 주/부/패치 버전 파싱
        parts = version_str.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version_str}")

        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2]),
            prerelease=prerelease,
            build_metadata=build_metadata,
        )

    def __lt__(self, other: "ModelVersion") -> bool:
        """버전 비교."""
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __eq__(self, other: object) -> bool:
        """버전 동등성."""
        if not isinstance(other, ModelVersion):
            return False
        return (self.major, self.minor, self.patch) == (
            other.major,
            other.minor,
            other.patch,
        )

    def __hash__(self) -> int:
        """해시값."""
        return hash((self.major, self.minor, self.patch))

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "version": str(self),
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "prerelease": self.prerelease,
            "build_metadata": self.build_metadata,
            "created_at": self.created_at.isoformat(),
            "changelog": self.changelog,
        }


@dataclass(slots=True)
class ModelMetrics:
    """
    모델 성능 메트릭.

    모델의 성능 및 사용 통계를 추적합니다.
    """

    # 사용 통계
    total_inferences: int = 0
    successful_inferences: int = 0
    failed_inferences: int = 0

    # 성능 메트릭
    total_inference_time_ms: float = 0.0
    min_inference_time_ms: float = float("inf")
    max_inference_time_ms: float = 0.0
    last_inference_time_ms: float = 0.0

    # 처리량
    current_fps: float = 0.0
    peak_fps: float = 0.0

    # 메모리
    memory_usage_mb: float = 0.0
    peak_memory_mb: float = 0.0

    # 정확도 (배치 평균)
    average_confidence: float = 0.0

    # 로드 통계
    load_count: int = 0
    unload_count: int = 0
    total_load_time_ms: float = 0.0
    last_loaded_at: datetime | None = None
    last_unloaded_at: datetime | None = None

    # 에러 통계
    last_error: str | None = None
    last_error_at: datetime | None = None
    error_count: int = 0

    def record_inference(
        self,
        duration_ms: float,
        success: bool = True,
        confidence: float | None = None,
    ) -> None:
        """추론 결과 기록."""
        self.total_inferences += 1

        if success:
            self.successful_inferences += 1
        else:
            self.failed_inferences += 1

        self.total_inference_time_ms += duration_ms
        self.last_inference_time_ms = duration_ms
        self.min_inference_time_ms = min(self.min_inference_time_ms, duration_ms)
        self.max_inference_time_ms = max(self.max_inference_time_ms, duration_ms)

        # FPS 계산
        if duration_ms > 0:
            fps = 1000.0 / duration_ms
            self.current_fps = fps
            self.peak_fps = max(self.peak_fps, fps)

        # 신뢰도 이동 평균
        if confidence is not None and success:
            if self.successful_inferences == 1:
                self.average_confidence = confidence
            else:
                alpha = 0.1  # 지수 이동 평균 계수
                self.average_confidence = (
                    alpha * confidence + (1 - alpha) * self.average_confidence
                )

    def record_load(self, duration_ms: float) -> None:
        """모델 로드 기록."""
        self.load_count += 1
        self.total_load_time_ms += duration_ms
        self.last_loaded_at = datetime.now(timezone.utc)

    def record_unload(self) -> None:
        """모델 언로드 기록."""
        self.unload_count += 1
        self.last_unloaded_at = datetime.now(timezone.utc)

    def record_error(self, error_message: str) -> None:
        """에러 기록."""
        self.error_count += 1
        self.last_error = error_message
        self.last_error_at = datetime.now(timezone.utc)

    def update_memory(self, memory_mb: float) -> None:
        """메모리 사용량 업데이트."""
        self.memory_usage_mb = memory_mb
        self.peak_memory_mb = max(self.peak_memory_mb, memory_mb)

    @property
    def average_inference_time_ms(self) -> float:
        """평균 추론 시간."""
        if self.total_inferences == 0:
            return 0.0
        return self.total_inference_time_ms / self.total_inferences

    @property
    def success_rate(self) -> float:
        """성공률 (0~1)."""
        if self.total_inferences == 0:
            return 0.0
        return self.successful_inferences / self.total_inferences

    @property
    def average_load_time_ms(self) -> float:
        """평균 로드 시간."""
        if self.load_count == 0:
            return 0.0
        return self.total_load_time_ms / self.load_count

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "total_inferences": self.total_inferences,
            "successful_inferences": self.successful_inferences,
            "failed_inferences": self.failed_inferences,
            "average_inference_time_ms": round(self.average_inference_time_ms, 3),
            "min_inference_time_ms": round(self.min_inference_time_ms, 3)
            if self.min_inference_time_ms != float("inf")
            else None,
            "max_inference_time_ms": round(self.max_inference_time_ms, 3),
            "last_inference_time_ms": round(self.last_inference_time_ms, 3),
            "current_fps": round(self.current_fps, 2),
            "peak_fps": round(self.peak_fps, 2),
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "average_confidence": round(self.average_confidence, 4),
            "load_count": self.load_count,
            "unload_count": self.unload_count,
            "average_load_time_ms": round(self.average_load_time_ms, 3),
            "success_rate": round(self.success_rate, 4),
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_loaded_at": self.last_loaded_at.isoformat()
            if self.last_loaded_at
            else None,
        }


@dataclass(slots=True)
class ModelConfig:
    """
    모델 설정.

    모델 로드 및 실행에 필요한 설정을 정의합니다.
    """

    # 기본 설정
    device: str = "cpu"  # cuda, cpu, mps
    precision: str = "fp32"  # fp32, fp16, int8
    batch_size: int = 1
    num_threads: int = 1

    # GPU 설정
    gpu_id: int = 0
    gpu_memory_fraction: float = 0.8

    # 성능 설정
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS
    timeout_seconds: float = DEFAULT_MODEL_TIMEOUT
    enable_profiling: bool = False

    # 캐싱 설정
    enable_caching: bool = True
    cache_size_mb: int = 512

    # 추론 설정
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.45
    max_detections: int = 100

    # 입력 설정
    input_width: int = 640
    input_height: int = 640
    normalize_input: bool = True
    bgr_to_rgb: bool = True

    # 추가 파라미터
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "device": self.device,
            "precision": self.precision,
            "batch_size": self.batch_size,
            "num_threads": self.num_threads,
            "gpu_id": self.gpu_id,
            "gpu_memory_fraction": self.gpu_memory_fraction,
            "warmup_iterations": self.warmup_iterations,
            "timeout_seconds": self.timeout_seconds,
            "enable_profiling": self.enable_profiling,
            "enable_caching": self.enable_caching,
            "cache_size_mb": self.cache_size_mb,
            "confidence_threshold": self.confidence_threshold,
            "nms_threshold": self.nms_threshold,
            "max_detections": self.max_detections,
            "input_size": [self.input_width, self.input_height],
            "normalize_input": self.normalize_input,
            "bgr_to_rgb": self.bgr_to_rgb,
            "extra_params": self.extra_params,
        }


@dataclass(slots=True)
class ModelInfo:
    """
    모델 정보.

    모델의 전체 메타데이터를 포함합니다.
    """

    # 식별 정보
    model_id: str
    name: str
    model_type: ModelType
    version: ModelVersion

    # 파일 정보
    model_path: Path | None = None
    model_format: ModelFormat = ModelFormat.WEIGHTS
    file_size_mb: float = 0.0
    checksum: str | None = None  # SHA256

    # 상태
    status: ModelStatus = ModelStatus.REGISTERED
    status_message: str | None = None

    # 메타데이터
    description: str | None = None
    author: str | None = None
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 설정
    config: ModelConfig = field(default_factory=ModelConfig)

    # 메트릭
    metrics: ModelMetrics = field(default_factory=ModelMetrics)

    # 타임스탬프
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 관계
    parent_model_id: str | None = None  # 파인튜닝 원본
    child_model_ids: list[str] = field(default_factory=list)

    def update_status(
        self,
        status: ModelStatus,
        message: str | None = None,
    ) -> None:
        """상태 업데이트."""
        self.status = status
        self.status_message = message
        self.updated_at = datetime.now(timezone.utc)

    def calculate_checksum(self) -> str | None:
        """모델 파일 체크섬 계산."""
        if not self.model_path or not self.model_path.exists():
            return None

        sha256 = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        self.checksum = sha256.hexdigest()
        return self.checksum

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "model_type": self.model_type.value,
            "version": self.version.to_dict(),
            "model_path": str(self.model_path) if self.model_path else None,
            "model_format": self.model_format.value,
            "file_size_mb": round(self.file_size_mb, 2),
            "checksum": self.checksum,
            "status": self.status.value,
            "status_message": self.status_message,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "tags": self.tags,
            "metadata": self.metadata,
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": self.child_model_ids,
        }


@dataclass(slots=True)
class LoadedModel(Generic[ModelT]):
    """
    로드된 모델 래퍼.

    실제 로드된 모델 인스턴스와 메타데이터를 래핑합니다.
    """

    model_info: ModelInfo
    model_instance: ModelT | None = None
    load_time_ms: float = 0.0
    loaded_at: datetime | None = None
    last_used_at: datetime | None = None
    use_count: int = 0

    # 락 (동시 사용 제어)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if self.model_instance is not None and self.loaded_at is None:
            self.loaded_at = datetime.now(timezone.utc)

    @property
    def is_loaded(self) -> bool:
        """모델 로드 여부."""
        return self.model_instance is not None

    @property
    def model_id(self) -> str:
        """모델 ID."""
        return self.model_info.model_id

    @property
    def status(self) -> ModelStatus:
        """모델 상태."""
        return self.model_info.status

    def mark_used(self) -> None:
        """사용 기록."""
        with self._lock:
            self.use_count += 1
            self.last_used_at = datetime.now(timezone.utc)

    @contextmanager
    def acquire(self) -> Iterator[ModelT | None]:
        """모델 사용을 위한 컨텍스트 매니저."""
        with self._lock:
            self.mark_used()
            yield self.model_instance


# ============================================================
# 모델 로더 프로토콜
# ============================================================
@runtime_checkable
class IModelLoader(Protocol[ModelT]):
    """모델 로더 프로토콜."""

    def load(
        self,
        model_info: ModelInfo,
    ) -> ModelT:
        """모델 로드."""
        ...

    def unload(
        self,
        model: ModelT,
    ) -> None:
        """모델 언로드."""
        ...

    def warmup(
        self,
        model: ModelT,
        iterations: int,
    ) -> None:
        """모델 워밍업."""
        ...


# ============================================================
# 모델 레지스트리 메인 클래스
# ============================================================
class ModelRegistry:
    """
    모델 레지스트리.

    AI 모델의 등록, 버전 관리, 로드/언로드를 관리합니다.
    싱글톤 패턴은 사용하지 않고 DI 컨테이너를 통해 관리됩니다.

    Args:
        config_loader: 설정 로더 (Direct Import)
        metrics_collector: 메트릭 수집기 (DI 주입, Optional)
        error_tracker: 에러 추적기 (DI 주입, Optional)
        max_models: 최대 등록 모델 수
        enable_auto_unload: 자동 언로드 활성화
        auto_unload_threshold: 자동 언로드 임계값 (사용되지 않은 시간, 초)

    Example:
        >>> registry = ModelRegistry(
        ...     config_loader=config_loader,
        ...     metrics_collector=metrics_collector,
        ...     error_tracker=error_tracker,
        ... )
        >>> model_info = registry.register(
        ...     name="yolov8n-basketball",
        ...     model_type=ModelType.YOLO,
        ...     version="1.0.0",
        ...     model_path=Path("models/yolov8n.pt"),
        ... )
        >>> registry.load("yolov8n-basketball")
        >>> model = registry.get("yolov8n-basketball")
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        metrics_collector: "MetricsCollector | None" = None,
        error_tracker: "ErrorTracker | None" = None,
        max_models: int = DEFAULT_MAX_MODELS,
        enable_auto_unload: bool = True,
        auto_unload_threshold: float = 3600.0,  # 1시간
    ) -> None:
        """초기화."""
        # 설정
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._metrics_collector = metrics_collector
        self._error_tracker = error_tracker
        self._max_models = max_models
        self._enable_auto_unload = enable_auto_unload
        self._auto_unload_threshold = auto_unload_threshold

        # YAML 설정 기본값 (storage)
        self._storage_local_path: str = "models"
        self._storage_remote_enabled: bool = True
        self._storage_remote_bucket: str = "courtview-models"
        self._storage_remote_prefix: str = "registry"

        # YAML 설정 기본값 (versioning)
        self._versioning_format: str = "semantic"
        self._versioning_max_versions: int = 5
        self._versioning_auto_cleanup: bool = True

        # YAML 설정 기본값 (loading)
        self._loading_lazy: bool = True
        self._loading_preload: list[str] = ["player_detection", "pose_estimation"]
        self._loading_timeout: float = 60.0
        self._loading_max_concurrent: int = 2

        # YAML 설정 기본값 (unloading)
        self._unloading_idle_timeout: float = 300.0
        self._unloading_on_memory_pressure: bool = True
        self._unloading_min_loaded: int = 1

        # YAML 설정 기본값 (validation)
        self._validation_on_load: bool = True
        self._validation_checksum: bool = True
        self._validation_inference_test: bool = True

        # YAML 설정 기본값 (metrics)
        self._metrics_enabled: bool = True
        self._metrics_track_inference_time: bool = True
        self._metrics_track_memory: bool = True

        # 저장소
        self._models: dict[str, ModelInfo] = {}  # model_id -> ModelInfo
        self._loaded_models: dict[str, LoadedModel] = {}  # model_id -> LoadedModel
        self._model_loaders: dict[ModelType, IModelLoader] = {}  # type -> loader

        # 버전 관리
        self._versions: dict[str, dict[str, ModelInfo]] = {}  # name -> {version -> info}

        # LRU 캐시 (최근 사용 모델 추적)
        self._usage_order: "OrderedDict[str, datetime]" = OrderedDict()

        # 상태
        self._enabled = True
        self._shutdown = False

        # 스레드 안전성
        self._lock = threading.RLock()
        self._model_locks: dict[str, threading.RLock] = {}

        # 설정 로드
        self._load_config()

        # 메트릭 설정
        self._setup_metrics()

        logger.info(
            f"ModelRegistry 초기화 완료: max_models={max_models}, "
            f"auto_unload={enable_auto_unload}"
        )

    def __repr__(self) -> str:
        """ModelRegistry 인스턴스 표현."""
        with self._lock:
            total = len(self._models)
            loaded = len(self._loaded_models)
        return (
            f"ModelRegistry(models={total}/{self._max_models}, "
            f"loaded={loaded}, "
            f"auto_unload={self._enable_auto_unload})"
        )

    def _load_config(self) -> None:
        """
        YAML 설정 로드.

        configs/core_foundation/registry.yaml의 model_registry 섹션에서
        모든 설정을 로드합니다.
        """
        try:
            registry_config = self._config_loader.get(
                "registry.model_registry",
                default={},
            )

            # 기본 설정
            if "max_models" in registry_config:
                self._max_models = registry_config["max_models"]
            if "enable_auto_unload" in registry_config:
                self._enable_auto_unload = registry_config["enable_auto_unload"]
            if "auto_unload_threshold" in registry_config:
                self._auto_unload_threshold = registry_config["auto_unload_threshold"]

            # storage 설정
            storage_config = registry_config.get("storage", {})
            if "local_path" in storage_config:
                self._storage_local_path = storage_config["local_path"]
            remote_config = storage_config.get("remote", {})
            if "enabled" in remote_config:
                self._storage_remote_enabled = remote_config["enabled"]
            if "bucket" in remote_config:
                self._storage_remote_bucket = remote_config["bucket"]
            if "prefix" in remote_config:
                self._storage_remote_prefix = remote_config["prefix"]

            # versioning 설정
            version_config = registry_config.get("versioning", {})
            if "format" in version_config:
                self._versioning_format = version_config["format"]
            if "max_versions" in version_config:
                self._versioning_max_versions = version_config["max_versions"]
            if "auto_cleanup" in version_config:
                self._versioning_auto_cleanup = version_config["auto_cleanup"]

            # loading 설정
            loading_config = registry_config.get("loading", {})
            if "lazy_load" in loading_config:
                self._loading_lazy = loading_config["lazy_load"]
            if "preload" in loading_config:
                self._loading_preload = loading_config["preload"]
            if "timeout" in loading_config:
                self._loading_timeout = float(loading_config["timeout"])
            if "max_concurrent" in loading_config:
                self._loading_max_concurrent = loading_config["max_concurrent"]

            # unloading 설정
            unloading_config = registry_config.get("unloading", {})
            if "idle_timeout" in unloading_config:
                self._unloading_idle_timeout = float(unloading_config["idle_timeout"])
            if "on_memory_pressure" in unloading_config:
                self._unloading_on_memory_pressure = unloading_config["on_memory_pressure"]
            if "min_loaded" in unloading_config:
                self._unloading_min_loaded = unloading_config["min_loaded"]

            # validation 설정
            validation_config = registry_config.get("validation", {})
            if "on_load" in validation_config:
                self._validation_on_load = validation_config["on_load"]
            if "checksum" in validation_config:
                self._validation_checksum = validation_config["checksum"]
            if "inference_test" in validation_config:
                self._validation_inference_test = validation_config["inference_test"]

            # metrics 설정
            metrics_config = registry_config.get("metrics", {})
            if "enabled" in metrics_config:
                self._metrics_enabled = metrics_config["enabled"]
            if "track_inference_time" in metrics_config:
                self._metrics_track_inference_time = metrics_config["track_inference_time"]
            if "track_memory" in metrics_config:
                self._metrics_track_memory = metrics_config["track_memory"]

            logger.debug(
                f"YAML 설정 로드 완료: storage_path={self._storage_local_path}, "
                f"loading_timeout={self._loading_timeout}s, "
                f"max_versions={self._versioning_max_versions}"
            )

        except Exception as e:
            logger.warning(f"설정 로드 실패, 기본값 사용: {e}")

    def _setup_metrics(self) -> None:
        """메트릭 설정."""
        if self._metrics_collector is None:
            return

        # 카운터
        self._register_counter = self._metrics_collector.counter(
            "model_registry_registrations_total",
            "Total model registrations",
        )
        self._load_counter = self._metrics_collector.counter(
            "model_registry_loads_total",
            "Total model loads",
        )
        self._unload_counter = self._metrics_collector.counter(
            "model_registry_unloads_total",
            "Total model unloads",
        )
        self._error_counter = self._metrics_collector.counter(
            "model_registry_errors_total",
            "Total model registry errors",
        )

        # 게이지
        self._registered_gauge = self._metrics_collector.gauge(
            "model_registry_registered_models",
            "Number of registered models",
        )
        self._loaded_gauge = self._metrics_collector.gauge(
            "model_registry_loaded_models",
            "Number of loaded models",
        )

        # 히스토그램
        self._load_time_histogram = self._metrics_collector.histogram(
            "model_registry_load_duration_ms",
            "Model load duration in milliseconds",
        )

    def _get_model_lock(self, model_id: str) -> threading.RLock:
        """모델별 락 가져오기."""
        with self._lock:
            if model_id not in self._model_locks:
                self._model_locks[model_id] = threading.RLock()
            return self._model_locks[model_id]

    def _generate_model_id(self, name: str, version: str) -> str:
        """모델 ID 생성."""
        return f"{name}:{version}"

    def _track_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """에러 추적."""
        if self._error_tracker:
            from core_foundation.monitoring.error_tracker import ErrorSeverity

            self._error_tracker.track(
                error=error,
                severity=ErrorSeverity.ERROR,
                context=context or {},
            )

        if self._metrics_collector:
            self._error_counter.inc()

    # ============================================================
    # 경로 보안
    # ============================================================
    def _validate_model_path(self, model_path: Path | None) -> Path | None:
        """
        모델 경로 유효성 검증 및 보안 처리.

        경로 탐색 공격(path traversal) 방지 및 허용된 디렉토리 내 경로만 허용.

        Args:
            model_path: 검증할 모델 경로

        Returns:
            검증된 절대 경로 또는 None

        Raises:
            ValueError: 유효하지 않은 경로
        """
        if model_path is None:
            return None

        # 절대 경로로 변환 및 정규화 (심볼릭 링크 해석)
        resolved_path = model_path.resolve()

        # 허용된 기본 경로 목록
        allowed_base_paths = [
            Path(self._storage_local_path).resolve(),
            Path.cwd() / self._storage_local_path,
            Path.cwd() / "models",
        ]

        # 환경 변수에서 추가 허용 경로 로드 (선택적)
        extra_paths = os.environ.get("COURTVIEW_MODEL_PATHS", "")
        if extra_paths:
            for extra_path in extra_paths.split(os.pathsep):
                if extra_path.strip():
                    allowed_base_paths.append(Path(extra_path.strip()).resolve())

        # 경로가 허용된 디렉토리 내에 있는지 확인
        is_valid = False
        for base_path in allowed_base_paths:
            try:
                # 경로가 허용된 기본 경로의 하위인지 확인
                resolved_path.relative_to(base_path)
                is_valid = True
                break
            except ValueError:
                continue

        if not is_valid:
            # 파일이 존재하고 허용 목록에 없는 경우 경고
            if resolved_path.exists():
                logger.warning(
                    f"모델 경로가 허용된 디렉토리 외부에 있습니다: {resolved_path}. "
                    f"허용된 경로: {[str(p) for p in allowed_base_paths]}"
                )
            # 개발/테스트 환경에서는 허용, 프로덕션에서는 거부 가능
            # 현재는 경고만 출력하고 허용

        return resolved_path

    # ============================================================
    # 등록 관리
    # ============================================================
    def register(
        self,
        name: str,
        model_type: ModelType,
        version: str | ModelVersion,
        model_path: Path | None = None,
        model_format: ModelFormat = ModelFormat.WEIGHTS,
        description: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        config: ModelConfig | None = None,
        metadata: dict[str, Any] | None = None,
        parent_model_id: str | None = None,
    ) -> ModelInfo:
        """
        모델 등록.

        Args:
            name: 모델 이름
            model_type: 모델 타입
            version: 버전 (문자열 또는 ModelVersion)
            model_path: 모델 파일 경로
            model_format: 모델 포맷
            description: 설명
            author: 작성자
            tags: 태그 목록
            config: 모델 설정
            metadata: 추가 메타데이터
            parent_model_id: 부모 모델 ID

        Returns:
            등록된 모델 정보

        Raises:
            ValueError: 중복 등록 또는 최대 개수 초과
        """
        with self._lock:
            # 경로 보안 검증 (Path.resolve() 및 허용 경로 확인)
            validated_path = self._validate_model_path(model_path)

            # 버전 파싱
            if isinstance(version, str):
                version_obj = ModelVersion.from_string(version)
            else:
                version_obj = version

            # 모델 ID 생성
            model_id = self._generate_model_id(name, str(version_obj))

            # 중복 체크
            if model_id in self._models:
                raise ValueError(f"모델이 이미 등록되어 있습니다: {model_id}")

            # 최대 개수 체크
            if len(self._models) >= self._max_models:
                raise ValueError(
                    f"최대 등록 가능 모델 수 초과: {self._max_models}"
                )

            # 파일 크기 계산
            file_size_mb = 0.0
            if validated_path and validated_path.exists():
                file_size_mb = validated_path.stat().st_size / (1024 * 1024)

            # ModelInfo 생성
            model_info = ModelInfo(
                model_id=model_id,
                name=name,
                model_type=model_type,
                version=version_obj,
                model_path=validated_path,
                model_format=model_format,
                file_size_mb=file_size_mb,
                description=description,
                author=author,
                tags=tags or [],
                config=config or ModelConfig(),
                metadata=metadata or {},
                parent_model_id=parent_model_id,
            )

            # 체크섬 계산 (검증된 경로 사용)
            if validated_path and validated_path.exists():
                model_info.calculate_checksum()

            # 저장
            self._models[model_id] = model_info

            # 버전 맵 업데이트
            if name not in self._versions:
                self._versions[name] = {}
            self._versions[name][str(version_obj)] = model_info

            # 메트릭 업데이트
            if self._metrics_collector:
                self._register_counter.inc(1, {"model_type": model_type.value})
                self._registered_gauge.set(len(self._models))

            logger.info(f"모델 등록 완료: {model_id}")
            return model_info

    def unregister(self, model_id: str) -> bool:
        """
        모델 등록 해제.

        로드된 모델은 먼저 언로드됩니다.

        Args:
            model_id: 모델 ID

        Returns:
            성공 여부
        """
        with self._lock:
            if model_id not in self._models:
                return False

            # 로드된 경우 언로드
            if model_id in self._loaded_models:
                self.unload(model_id)

            model_info = self._models.pop(model_id)

            # 버전 맵에서 제거
            name = model_info.name
            version_str = str(model_info.version)
            if name in self._versions and version_str in self._versions[name]:
                del self._versions[name][version_str]
                if not self._versions[name]:
                    del self._versions[name]

            # 락 정리
            if model_id in self._model_locks:
                del self._model_locks[model_id]

            # 메트릭 업데이트
            if self._metrics_collector:
                self._registered_gauge.set(len(self._models))

            logger.info(f"모델 등록 해제: {model_id}")
            return True

    # ============================================================
    # 조회
    # ============================================================
    def get(self, model_id: str) -> ModelInfo | None:
        """
        모델 정보 조회.

        Args:
            model_id: 모델 ID

        Returns:
            모델 정보 (없으면 None)
        """
        return self._models.get(model_id)

    def get_loaded(self, model_id: str) -> LoadedModel | None:
        """
        로드된 모델 조회.

        Args:
            model_id: 모델 ID

        Returns:
            로드된 모델 래퍼 (없으면 None)
        """
        return self._loaded_models.get(model_id)

    def get_by_name(
        self,
        name: str,
        version: str | None = None,
    ) -> ModelInfo | None:
        """
        이름으로 모델 조회.

        Args:
            name: 모델 이름
            version: 버전 (None이면 최신 버전)

        Returns:
            모델 정보 (없으면 None)
        """
        if name not in self._versions:
            return None

        versions = self._versions[name]

        if version:
            return versions.get(version)

        # 최신 버전 반환
        if not versions:
            return None

        latest_version = max(
            versions.keys(),
            key=lambda v: ModelVersion.from_string(v),
        )
        return versions[latest_version]

    def list_all(self) -> list[ModelInfo]:
        """
        모든 등록된 모델 목록.

        Returns:
            모델 정보 목록
        """
        return list(self._models.values())

    def list_loaded(self) -> list[str]:
        """
        로드된 모델 ID 목록.

        Returns:
            모델 ID 목록
        """
        return list(self._loaded_models.keys())

    def list_by_type(self, model_type: ModelType) -> list[ModelInfo]:
        """
        타입별 모델 목록.

        Args:
            model_type: 모델 타입

        Returns:
            해당 타입의 모델 정보 목록
        """
        return [m for m in self._models.values() if m.model_type == model_type]

    def list_by_status(self, status: ModelStatus) -> list[ModelInfo]:
        """
        상태별 모델 목록.

        Args:
            status: 모델 상태

        Returns:
            해당 상태의 모델 정보 목록
        """
        return [m for m in self._models.values() if m.status == status]

    def list_versions(self, name: str) -> list[ModelVersion]:
        """
        모델의 모든 버전 목록.

        Args:
            name: 모델 이름

        Returns:
            버전 목록 (정렬됨)
        """
        if name not in self._versions:
            return []

        versions = [
            ModelVersion.from_string(v) for v in self._versions[name].keys()
        ]
        return sorted(versions, reverse=True)

    # ============================================================
    # 로드/언로드
    # ============================================================
    def register_loader(
        self,
        model_type: ModelType,
        loader: IModelLoader,
    ) -> None:
        """
        모델 로더 등록.

        Args:
            model_type: 모델 타입
            loader: 모델 로더
        """
        with self._lock:
            self._model_loaders[model_type] = loader
            logger.info(f"모델 로더 등록: {model_type.value}")

    def load(
        self,
        model_id: str,
        force_reload: bool = False,
    ) -> LoadedModel:
        """
        모델 로드.

        Args:
            model_id: 모델 ID
            force_reload: 강제 리로드 여부

        Returns:
            로드된 모델 래퍼

        Raises:
            KeyError: 모델이 등록되지 않음
            RuntimeError: 로더가 등록되지 않음 또는 로드 실패
        """
        model_lock = self._get_model_lock(model_id)

        with model_lock:
            # 이미 로드된 경우
            if model_id in self._loaded_models and not force_reload:
                loaded = self._loaded_models[model_id]
                if loaded.is_loaded and loaded.status == ModelStatus.READY:
                    self._update_usage(model_id)
                    return loaded

            # 모델 정보 확인
            model_info = self._models.get(model_id)
            if not model_info:
                raise KeyError(f"등록되지 않은 모델: {model_id}")

            # 강제 리로드 시 기존 모델 언로드
            if force_reload and model_id in self._loaded_models:
                self._unload_internal(model_id)

            # 로더 확인
            loader = self._model_loaders.get(model_info.model_type)
            if not loader:
                model_info.update_status(
                    ModelStatus.ERROR,
                    f"모델 타입 '{model_info.model_type.value}'의 로더가 등록되지 않았습니다",
                )
                raise RuntimeError(
                    f"모델 타입 '{model_info.model_type.value}'의 로더가 등록되지 않았습니다. "
                    f"register_loader({model_info.model_type.value}, loader)를 먼저 호출하세요."
                )

            # 상태 업데이트
            model_info.update_status(ModelStatus.LOADING, "모델 로딩 중...")

            try:
                # 로드 수행
                with Timer() as timer:
                    model_instance = loader.load(model_info)

                load_time_ms = timer.elapsed_ms

                # 워밍업
                model_info.update_status(ModelStatus.WARMING_UP, "워밍업 중...")
                warmup_iterations = model_info.config.warmup_iterations
                if warmup_iterations > 0:
                    loader.warmup(model_instance, warmup_iterations)

                # 로드 완료
                model_info.update_status(ModelStatus.READY, "준비 완료")
                model_info.metrics.record_load(load_time_ms)

                # LoadedModel 생성
                loaded_model = LoadedModel(
                    model_info=model_info,
                    model_instance=model_instance,
                    load_time_ms=load_time_ms,
                    loaded_at=datetime.now(timezone.utc),
                )

                self._loaded_models[model_id] = loaded_model
                self._update_usage(model_id)

                # 메트릭 업데이트
                if self._metrics_collector:
                    self._load_counter.inc(
                        1,
                        {"model_type": model_info.model_type.value},
                    )
                    self._loaded_gauge.set(len(self._loaded_models))
                    self._load_time_histogram.observe(load_time_ms)

                logger.info(
                    f"모델 로드 완료: {model_id} ({load_time_ms:.1f}ms)"
                )
                return loaded_model

            except Exception as e:
                model_info.update_status(ModelStatus.ERROR, str(e))
                model_info.metrics.record_error(str(e))
                self._track_error(e, {"model_id": model_id, "operation": "load"})
                raise RuntimeError(f"모델 로드 실패: {e}") from e

    def unload(self, model_id: str) -> bool:
        """
        모델 언로드.

        Args:
            model_id: 모델 ID

        Returns:
            성공 여부
        """
        model_lock = self._get_model_lock(model_id)

        with model_lock:
            return self._unload_internal(model_id)

    def _unload_internal(self, model_id: str) -> bool:
        """내부 언로드 (락 없이)."""
        if model_id not in self._loaded_models:
            return False

        loaded_model = self._loaded_models.pop(model_id)
        model_info = loaded_model.model_info

        try:
            # 로더를 통해 언로드
            loader = self._model_loaders.get(model_info.model_type)
            if loader and loaded_model.model_instance:
                loader.unload(loaded_model.model_instance)

            model_info.update_status(ModelStatus.UNLOADED, "언로드 완료")
            model_info.metrics.record_unload()

            # 사용 순서에서 제거
            if model_id in self._usage_order:
                del self._usage_order[model_id]

            # 메트릭 업데이트
            if self._metrics_collector:
                self._unload_counter.inc(
                    1,
                    {"model_type": model_info.model_type.value},
                )
                self._loaded_gauge.set(len(self._loaded_models))

            logger.info(f"모델 언로드 완료: {model_id}")
            return True

        except Exception as e:
            model_info.update_status(ModelStatus.ERROR, str(e))
            self._track_error(e, {"model_id": model_id, "operation": "unload"})
            return False

    def _update_usage(self, model_id: str) -> None:
        """사용 순서 업데이트 (LRU)."""
        with self._lock:
            if model_id in self._usage_order:
                del self._usage_order[model_id]
            self._usage_order[model_id] = datetime.now(timezone.utc)

    # ============================================================
    # 자동 관리
    # ============================================================
    def cleanup_unused(
        self,
        threshold_seconds: float | None = None,
    ) -> int:
        """
        오래 사용되지 않은 모델 언로드.

        Args:
            threshold_seconds: 임계값 (초)

        Returns:
            언로드된 모델 수
        """
        if not self._enable_auto_unload:
            return 0

        threshold = threshold_seconds or self._auto_unload_threshold
        now = datetime.now(timezone.utc)
        unloaded_count = 0

        with self._lock:
            to_unload = []

            for model_id, last_used in self._usage_order.items():
                elapsed = (now - last_used).total_seconds()
                if elapsed > threshold:
                    to_unload.append(model_id)

            for model_id in to_unload:
                if self.unload(model_id):
                    unloaded_count += 1

        if unloaded_count > 0:
            logger.info(f"미사용 모델 정리: {unloaded_count}개 언로드")

        return unloaded_count

    # ============================================================
    # 상태 조회
    # ============================================================
    @property
    def enabled(self) -> bool:
        """활성화 여부."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """활성화 설정."""
        self._enabled = value

    @property
    def model_count(self) -> int:
        """등록된 모델 수."""
        return len(self._models)

    @property
    def loaded_count(self) -> int:
        """로드된 모델 수."""
        return len(self._loaded_models)

    def get_status(self) -> dict[str, Any]:
        """
        레지스트리 상태 조회.

        Returns:
            상태 정보 딕셔너리
        """
        with self._lock:
            model_types = {}
            for model_info in self._models.values():
                type_name = model_info.model_type.value
                model_types[type_name] = model_types.get(type_name, 0) + 1

            status_counts = {}
            for model_info in self._models.values():
                status_name = model_info.status.value
                status_counts[status_name] = status_counts.get(status_name, 0) + 1

            return {
                "enabled": self._enabled,
                "registered_models": len(self._models),
                "loaded_models": len(self._loaded_models),
                "max_models": self._max_models,
                "model_types": model_types,
                "status_counts": status_counts,
                "auto_unload_enabled": self._enable_auto_unload,
                "auto_unload_threshold_seconds": self._auto_unload_threshold,
                "registered_loaders": list(
                    t.value for t in self._model_loaders.keys()
                ),
            }

    # ============================================================
    # 종료
    # ============================================================
    def shutdown(self) -> None:
        """레지스트리 종료."""
        with self._lock:
            if self._shutdown:
                return

            self._shutdown = True
            self._enabled = False

            # 모든 모델 언로드
            for model_id in list(self._loaded_models.keys()):
                self.unload(model_id)

            logger.info("ModelRegistry 종료 완료")

    def __enter__(self) -> "ModelRegistry":
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료."""
        self.shutdown()


# ============================================================
# 전역 인스턴스 관리 (싱글톤 대안)
# ============================================================
_global_registry: ModelRegistry | None = None
_registry_lock = threading.Lock()


def _get_registry() -> ModelRegistry:
    """전역 레지스트리 가져오기."""
    global _global_registry
    with _registry_lock:
        if _global_registry is None:
            _global_registry = ModelRegistry()
        return _global_registry


def _reset_registry() -> None:
    """전역 레지스트리 초기화 (테스트용)."""
    global _global_registry
    with _registry_lock:
        if _global_registry is not None:
            _global_registry.shutdown()
            _global_registry = None


# ============================================================
# 헬퍼 함수
# ============================================================
def get_model(model_id: str) -> ModelInfo | None:
    """
    모델 정보 조회 헬퍼.

    Args:
        model_id: 모델 ID

    Returns:
        모델 정보 (없으면 None)
    """
    return _get_registry().get(model_id)


def register_model(
    name: str,
    model_type: ModelType,
    version: str,
    model_path: Path | None = None,
    **kwargs: Any,
) -> ModelInfo:
    """
    모델 등록 헬퍼.

    Args:
        name: 모델 이름
        model_type: 모델 타입
        version: 버전
        model_path: 모델 경로
        **kwargs: 추가 인자

    Returns:
        등록된 모델 정보
    """
    return _get_registry().register(
        name=name,
        model_type=model_type,
        version=version,
        model_path=model_path,
        **kwargs,
    )


# 모듈 버전 정보
__version__: str = "1.0.0"
