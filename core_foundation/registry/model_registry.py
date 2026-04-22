# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: model_registry.py
설명: AI 모델 레지스트리
      - 모델 메타데이터 등록/조회
      - 모델 로드/언로드 라이프사이클
      - VRAM 예산 추적 (GPU 메모리 관리)
      - 모델 버전 관리
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 모델 등록 수
MAX_MODELS: Final[int] = 50

# 기본 VRAM 예산 (MB) — 프로덕션 RTX 5060 8GB 기준, 시스템 예약 2GB 제외 (6GB ≈ 6,000 MB)
# SPOIN 2026-04-20 확정: 프로덕션 RTX 5060 8GB / 개발 RTX 5070 Ti.
# 향후 torch.cuda.get_device_properties()로 런타임 자동 감지 검토 (Phase 13 engine).
DEFAULT_VRAM_BUDGET_MB: Final[float] = 6_000.0

# 최소 VRAM 예산 (MB)
MIN_VRAM_BUDGET_MB: Final[float] = 1_000.0


# =============================================================================
# 모델 상태 열거형
# =============================================================================

@unique
class ModelStatus(Enum):
    """모델 라이프사이클 상태.

    Attributes:
        REGISTERED: 등록됨 (메타데이터만)
        LOADING: 로딩 중
        LOADED: 로드 완료 (추론 가능)
        UNLOADING: 언로딩 중
        ERROR: 로드 실패
    """

    REGISTERED = "registered"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    ERROR = "error"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _MODEL_STATUS_KOREAN_MAP[self]


_MODEL_STATUS_KOREAN_MAP: Final[dict[ModelStatus, str]] = {
    ModelStatus.REGISTERED: "등록됨",
    ModelStatus.LOADING: "로딩 중",
    ModelStatus.LOADED: "로드 완료",
    ModelStatus.UNLOADING: "언로딩 중",
    ModelStatus.ERROR: "오류",
}


@unique
class ModelBackend(Enum):
    """모델 추론 백엔드.

    Attributes:
        PYTORCH: PyTorch 네이티브
        ONNX: ONNX Runtime
        TENSORRT: TensorRT (NVIDIA 최적화)
        CUSTOM: 자체 포맷 (.cv)
    """

    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    CUSTOM = "custom"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _MODEL_BACKEND_KOREAN_MAP[self]


_MODEL_BACKEND_KOREAN_MAP: Final[dict[ModelBackend, str]] = {
    ModelBackend.PYTORCH: "PyTorch",
    ModelBackend.ONNX: "ONNX Runtime",
    ModelBackend.TENSORRT: "TensorRT",
    ModelBackend.CUSTOM: "커스텀",
}


# =============================================================================
# 모델 메타데이터
# =============================================================================

@dataclass(slots=True)
class ModelInfo:
    """모델 등록 메타데이터.

    Attributes:
        name: 모델 이름 (고유 식별자)
        version: 모델 버전
        backend: 추론 백엔드
        vram_mb: 예상 VRAM 사용량 (MB)
        path: 모델 파일 경로
        description: 모델 설명
        tags: 분류 태그
        status: 현재 상태
        instance: 로드된 모델 인스턴스
        load_time_sec: 마지막 로드 소요 시간
        error_message: 오류 메시지
    """

    name: str
    version: str
    backend: ModelBackend
    vram_mb: float = 0.0
    path: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: ModelStatus = ModelStatus.REGISTERED
    instance: Any = None
    load_time_sec: float = 0.0
    error_message: str = ""

    @property
    def is_loaded(self) -> bool:
        """로드 완료 여부."""
        return self.status == ModelStatus.LOADED and self.instance is not None

    def __repr__(self) -> str:
        return (
            f"ModelInfo("
            f"'{self.name}' v{self.version}, "
            f"backend={self.backend.value}, "
            f"vram={self.vram_mb:.0f}MB, "
            f"status={self.status.value})"
        )


# =============================================================================
# 타입 정의
# =============================================================================

# 모델 로더: (model_info) -> 모델 인스턴스
ModelLoaderFn = Callable[[ModelInfo], Any]

# 모델 언로더: (model_info, instance) -> None
ModelUnloaderFn = Callable[[ModelInfo, Any], None]


# =============================================================================
# 핵심 클래스: ModelRegistry
# =============================================================================

class ModelRegistry:
    """AI 모델 레지스트리.

    모델 메타데이터를 등록하고, 로드/언로드 라이프사이클을 관리한다.
    VRAM 예산을 추적하여 GPU 메모리 초과를 방지한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        registry = ModelRegistry.get_instance()

        # 모델 등록
        registry.register(
            name="yolo11l-pose",
            version="11.0.0",
            backend=ModelBackend.TENSORRT,
            vram_mb=800.0,
            path="weights/yolo11l-pose.onnx",  # TensorRT engine 런타임 빌드
        )

        # 로더 등록 및 모델 로드
        registry.set_loader(my_loader_fn)
        registry.load("yolo11l-pose")

        # 모델 조회
        info = registry.get("yolo11l-pose")
        model = info.instance
    """

    _instance: ClassVar[ModelRegistry | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._models: dict[str, ModelInfo] = {}
        self._loader: ModelLoaderFn | None = None
        self._unloader: ModelUnloaderFn | None = None
        self._vram_budget_mb = DEFAULT_VRAM_BUDGET_MB

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 모델 등록
    # =========================================================================

    def register(
        self,
        name: str,
        version: str,
        backend: ModelBackend,
        *,
        vram_mb: float = 0.0,
        path: str = "",
        description: str = "",
        tags: list[str] | None = None,
    ) -> bool:
        """모델 메타데이터 등록.

        Args:
            name: 모델 이름
            version: 버전
            backend: 추론 백엔드
            vram_mb: 예상 VRAM (MB)
            path: 모델 파일 경로
            description: 설명
            tags: 분류 태그

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if (
                name not in self._models
                and len(self._models) >= MAX_MODELS
            ):
                return False

            self._models[name] = ModelInfo(
                name=name,
                version=version,
                backend=backend,
                vram_mb=vram_mb,
                path=path,
                description=description,
                tags=list(tags) if tags else [],
                status=ModelStatus.REGISTERED,
            )
            return True

    def unregister(self, name: str) -> bool:
        """모델 등록 해제.

        로드된 모델은 먼저 언로드 후 해제.

        Args:
            name: 모델 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            info = self._models.get(name)
            if info is None:
                return False

            # 로드된 상태면 언로드 시도
            if info.is_loaded:
                self._do_unload(info)

            del self._models[name]
            return True

    # =========================================================================
    # 로더/언로더 설정
    # =========================================================================

    def set_loader(self, loader: ModelLoaderFn) -> None:
        """모델 로더 함수 설정.

        Args:
            loader: (ModelInfo) -> model_instance
        """
        with self._lock:
            self._loader = loader

    def set_unloader(self, unloader: ModelUnloaderFn) -> None:
        """모델 언로더 함수 설정.

        Args:
            unloader: (ModelInfo, instance) -> None
        """
        with self._lock:
            self._unloader = unloader

    # =========================================================================
    # 모델 로드/언로드
    # =========================================================================

    def load(self, name: str) -> bool:
        """모델 로드.

        Args:
            name: 모델 이름

        Returns:
            로드 성공 여부

        Raises:
            KeyError: 미등록 모델
            RuntimeError: 로더 미설정 또는 VRAM 부족
        """
        with self._lock:
            info = self._models.get(name)
            if info is None:
                raise KeyError(f"미등록 모델: '{name}'")

            if info.is_loaded:
                return True  # 이미 로드됨

            if self._loader is None:
                raise RuntimeError("모델 로더 미설정")

            # VRAM 예산 확인
            if info.vram_mb > 0:
                available = self._vram_budget_mb - self.vram_used_mb
                if info.vram_mb > available:
                    raise RuntimeError(
                        f"VRAM 부족: '{name}' 요청 "
                        f"{info.vram_mb:.0f}MB, "
                        f"가용 {available:.0f}MB"
                    )

            info.status = ModelStatus.LOADING
            loader = self._loader

        # Lock 밖에서 로드 (장시간 작업)
        start = time.perf_counter()
        try:
            instance = loader(info)
            elapsed = time.perf_counter() - start

            with self._lock:
                info.instance = instance
                info.status = ModelStatus.LOADED
                info.load_time_sec = elapsed
                info.error_message = ""

            return True

        except Exception as exc:
            elapsed = time.perf_counter() - start

            with self._lock:
                info.status = ModelStatus.ERROR
                info.load_time_sec = elapsed
                info.error_message = f"{type(exc).__name__}: {exc}"

            return False

    def unload(self, name: str) -> bool:
        """모델 언로드.

        Args:
            name: 모델 이름

        Returns:
            언로드 성공 여부
        """
        with self._lock:
            info = self._models.get(name)
            if info is None:
                return False

            if not info.is_loaded:
                return False

            return self._do_unload(info)

    # =========================================================================
    # 조회
    # =========================================================================

    def get(self, name: str) -> ModelInfo | None:
        """모델 정보 조회.

        Args:
            name: 모델 이름

        Returns:
            ModelInfo 또는 None
        """
        with self._lock:
            return self._models.get(name)

    def get_by_tag(self, tag: str) -> list[ModelInfo]:
        """태그로 모델 목록 조회.

        Args:
            tag: 검색 태그

        Returns:
            해당 태그의 모델 정보 목록
        """
        with self._lock:
            return [
                info for info in self._models.values()
                if tag in info.tags
            ]

    def get_loaded(self) -> list[ModelInfo]:
        """로드된 모델 목록.

        Returns:
            로드 완료 상태의 모델 정보 목록
        """
        with self._lock:
            return [
                info for info in self._models.values()
                if info.is_loaded
            ]

    # =========================================================================
    # VRAM 관리
    # =========================================================================

    @property
    def vram_budget_mb(self) -> float:
        """VRAM 예산 (MB)."""
        with self._lock:
            return self._vram_budget_mb

    def set_vram_budget(self, budget_mb: float) -> None:
        """VRAM 예산 설정.

        Args:
            budget_mb: 예산 (MB)
        """
        with self._lock:
            self._vram_budget_mb = max(budget_mb, MIN_VRAM_BUDGET_MB)

    @property
    def vram_used_mb(self) -> float:
        """로드된 모델의 총 VRAM 사용량 (MB)."""
        with self._lock:
            return sum(
                info.vram_mb for info in self._models.values()
                if info.is_loaded
            )

    @property
    def vram_available_mb(self) -> float:
        """사용 가능 VRAM (MB)."""
        with self._lock:
            return self._vram_budget_mb - self.vram_used_mb

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def model_count(self) -> int:
        """등록된 모델 수."""
        with self._lock:
            return len(self._models)

    @property
    def model_names(self) -> list[str]:
        """등록된 모델 이름 목록."""
        with self._lock:
            return list(self._models.keys())

    @property
    def loaded_count(self) -> int:
        """로드된 모델 수."""
        with self._lock:
            return sum(
                1 for info in self._models.values()
                if info.is_loaded
            )

    def clear(self) -> int:
        """전체 모델 제거 (로드된 모델 언로드 포함).

        Returns:
            제거된 모델 수
        """
        with self._lock:
            # 로드된 모델 언로드
            for info in self._models.values():
                if info.is_loaded:
                    self._do_unload(info)

            count = len(self._models)
            self._models.clear()
            return count

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _do_unload(self, info: ModelInfo) -> bool:
        """내부 언로드 처리 (lock 내부에서 호출).

        Args:
            info: 모델 정보

        Returns:
            언로드 성공 여부
        """
        info.status = ModelStatus.UNLOADING

        if self._unloader is not None and info.instance is not None:
            try:
                self._unloader(info, info.instance)
            except Exception:
                pass  # 언로더 예외 격리

        info.instance = None
        info.status = ModelStatus.REGISTERED
        return True

    def __repr__(self) -> str:
        return (
            f"ModelRegistry("
            f"models={self.model_count}, "
            f"loaded={self.loaded_count}, "
            f"vram={self.vram_used_mb:.0f}/{self._vram_budget_mb:.0f}MB)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ModelStatus",
    "ModelBackend",
    # 데이터 클래스
    "ModelInfo",
    # 타입
    "ModelLoaderFn",
    "ModelUnloaderFn",
    # 핵심 클래스
    "ModelRegistry",
    # 상수
    "MAX_MODELS",
    "DEFAULT_VRAM_BUDGET_MB",
    "MIN_VRAM_BUDGET_MB",
]

__version__ = "1.0.0"
