# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/gpu
파일: tensorrt_pool.py
설명: 다중 TensorRT 엔진 풀 관리자
      - 4종 모델 (YOLOv8-Det/YOLOv8-Pose/ViTPose-B/ReID) 수명주기
      - 모델별 CUDA Stream 바인딩 (DET+POSE+REID→STAGE1, ViTPose→STAGE2)
      - VRAM 할당을 GPUManager에 위임
      - 엔진 상태 5단계 (UNLOADED→LOADING→READY→WARMING→ERROR)
      - 추론 카운터 추적

      계층 분리:
        tensorrt_engine.py (pose_estimation/backends) = 단일 TRT 엔진 빌드/추론 (Low-level)
        tensorrt_pool.py (이 파일) = 다중 TRT 엔진 수명주기 관리 (High-level)
        tensorrt_pool이 tensorrt_engine의 public API를 호출. 역방향 없음.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: GPUConfig
    - engine/gpu/gpu_manager.py: GPUManager (VRAM 위임)
    - engine/gpu/cuda_stream_manager.py: StreamID (스트림 바인딩)
    - pose_estimation/backends/tensorrt_engine.py: TensorRTEngine, TensorRTConfig (조건부)

소비자:
    - engine/pipeline/frame_pipeline.py: 모델 핸들 조회 + 추론
    - engine/orchestrator/game_orchestrator.py: 모델 로드/언로드
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import GPUConfig, PipelineConfig, TRTPrecision
from engine.gpu.cuda_stream_manager import StreamID
from engine.gpu.gpu_manager import GPUManager

# TensorRT 엔진 조건부 임포트 (미설치 환경 대비)
try:
    from pose_estimation.backends.tensorrt_engine import (
        TensorRTConfig,
        TensorRTEngine,
    )
    _TRT_ENGINE_AVAILABLE = True
except ImportError:
    _TRT_ENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# 모델 식별자
# =============================================================================
@unique
class ModelID(str, Enum):
    """
    TRT 모델 식별자 (4종).

    Attributes:
        YOLOV8_DET: YOLOv8 객체 감지 (공/선수/코트/골대)
        YOLOV8_POSE: YOLOv8-Pose 17키포인트
        VITPOSE_B: ViTPose-B 133키포인트 (Stage2 정밀)
    """

    YOLOV8_DET = "yolov8_det"
    YOLOV8_POSE = "yolov8_pose"
    VITPOSE_B = "vitpose_b"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 모델→스트림 바인딩
# =============================================================================
_MODEL_STREAM_BINDING: Final[dict[ModelID, StreamID]] = {
    ModelID.YOLOV8_DET: StreamID.STAGE1,
    ModelID.YOLOV8_POSE: StreamID.STAGE1,
    ModelID.VITPOSE_B: StreamID.STAGE2,
}

# =============================================================================
# 모델별 VRAM 추정치 (MB)
# =============================================================================
_MODEL_VRAM_ESTIMATE_MB: Final[dict[ModelID, float]] = {
    ModelID.YOLOV8_DET: 400.0,
    ModelID.YOLOV8_POSE: 800.0,
    ModelID.VITPOSE_B: 600.0,
}

# 모델별 입력 텐서 형상 (ONNX build_or_load 용)
_MODEL_INPUT_SHAPES: Final[dict[ModelID, dict[str, tuple[int, ...]]]] = {
    ModelID.YOLOV8_DET: {"images": (1, 3, 640, 640)},
    ModelID.YOLOV8_POSE: {"images": (1, 3, 640, 640)},
    ModelID.VITPOSE_B: {"input": (1, 3, 256, 192)},
}


# =============================================================================
# 엔진 상태
# =============================================================================
@unique
class EngineStatus(str, Enum):
    """
    TRT 엔진 상태 (5단계).

    Attributes:
        UNLOADED: 미로드
        LOADING: 로딩 중
        READY: 사용 가능
        WARMING: 워밍업 중
        ERROR: 오류
    """

    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    WARMING = "warming"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 엔진 엔트리
# =============================================================================
@dataclass(slots=True)
class EngineEntry:
    """
    단일 TRT 엔진 관리 엔트리.

    Attributes:
        model_id: 모델 식별자
        status: 현재 상태
        stream_id: 바인딩된 CUDA 스트림
        vram_mb: 할당된 VRAM (MB)
        engine_handle: TRT 엔진 핸들 (None=미로드)
        inference_count: 누적 추론 횟수
        loaded_at: 로드 시각 (monotonic)
        last_inference_at: 마지막 추론 시각
    """

    model_id: ModelID
    status: EngineStatus = EngineStatus.UNLOADED
    stream_id: StreamID = StreamID.STAGE1
    vram_mb: float = 0.0
    engine_handle: Any = None
    inference_count: int = 0
    loaded_at: float = 0.0
    last_inference_at: float = 0.0


# =============================================================================
# TensorRT 풀 관리자
# =============================================================================
class TensorRTPool:
    """
    다중 TensorRT 엔진 풀 관리자.

    4종 모델의 수명주기(로드/언로드/워밍업)를 관리하며,
    VRAM 할당은 GPUManager에 위임합니다.

    Attributes:
        _config: GPU 설정
        _gpu_manager: GPU 관리자 (VRAM 위임)
        _entries: ModelID → EngineEntry 매핑
        _lock: 스레드 안전 잠금
        _initialized: 초기화 완료 여부
        _next_inference_id: 추론 ID 카운터
    """

    __slots__ = (
        "_config",
        "_pipeline_config",
        "_gpu_manager",
        "_entries",
        "_model_onnx_paths",
        "_lock",
        "_initialized",
        "_next_inference_id",
    )

    def __init__(
        self,
        config: GPUConfig | None = None,
        pipeline_config: PipelineConfig | None = None,
        gpu_manager: GPUManager | None = None,
    ) -> None:
        self._config: GPUConfig = config or GPUConfig()
        self._pipeline_config: PipelineConfig = pipeline_config or PipelineConfig()
        self._gpu_manager: GPUManager | None = gpu_manager
        self._entries: dict[ModelID, EngineEntry] = {}
        self._model_onnx_paths: dict[ModelID, str] = {}
        self._lock: RLock = RLock()
        self._initialized: bool = False
        self._next_inference_id: int = 0

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================
    def initialize(self) -> None:
        """4종 ModelID별 EngineEntry 생성 + 스트림 바인딩 + ONNX 경로 매핑."""
        with self._lock:
            if self._initialized:
                return

            # ONNX 모델 경로 매핑 (PipelineConfig → ModelID)
            self._model_onnx_paths = {
                ModelID.YOLOV8_DET: self._pipeline_config.model_yolov8_det,
                ModelID.YOLOV8_POSE: self._pipeline_config.model_yolov8_pose,
                ModelID.VITPOSE_B: self._pipeline_config.model_vitpose,
            }

            for mid in ModelID:
                self._entries[mid] = EngineEntry(
                    model_id=mid,
                    stream_id=_MODEL_STREAM_BINDING[mid],
                    vram_mb=_MODEL_VRAM_ESTIMATE_MB[mid],
                )
            self._initialized = True
            logger.info(
                "TRT 풀 초기화: %d 모델, tensorrt_engine=%s",
                len(self._entries),
                "사용 가능" if _TRT_ENGINE_AVAILABLE else "시뮬레이션",
            )

    def shutdown(self) -> None:
        """전체 모델 언로드 + 종료."""
        with self._lock:
            for mid in list(self._entries.keys()):
                self._unload_entry(mid)
            self._entries.clear()
            self._initialized = False
            logger.info("TRT 풀 종료")

    # =========================================================================
    # 모델 로드 / 언로드
    # =========================================================================
    def load_model(self, model_id: ModelID) -> bool:
        """
        모델 로드 (GPUManager VRAM 할당 위임).

        Args:
            model_id: 로드할 모델

        Returns:
            로드 성공 여부
        """
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None:
                return False

            if entry.status == EngineStatus.READY:
                return True  # 이미 로드됨

            entry.status = EngineStatus.LOADING
            vram_needed = _MODEL_VRAM_ESTIMATE_MB[model_id]

            # GPUManager VRAM 할당
            if self._gpu_manager is not None:
                if not self._gpu_manager.allocate(model_id.value, vram_needed):
                    entry.status = EngineStatus.ERROR
                    logger.error("VRAM 할당 실패: %s", model_id.value)
                    return False

            # TRT 엔진 빌드/로드 (pose_estimation/backends/tensorrt_engine.py 위임)
            model_path = self._model_onnx_paths.get(model_id, "")
            import os

            if model_path and model_path.endswith(".engine"):
                # 이미 빌드된 TRT 엔진 파일 → ONNX 변환 불필요
                # 실제 추론은 각 백엔드(YOLOv8PoseBackend 등)에서 직접 로드
                entry.engine_handle = f"prebuilt_{model_id.value}"
                logger.info(
                    "사전 빌드 TRT 엔진 감지 (풀 빌드 생략): %s → %s",
                    model_id.value, model_path,
                )
            elif model_path and not model_path.endswith(".onnx"):
                # 2026-05-13: .pt / .pth / 기타 네이티브 형식 — TRT 빌드 불가.
                #   백엔드 (YOLOv8PoseBackend 등) 가 PyTorch 로 직접 로드.
                #   기존 흐름: TRT 빌드 시도 → ONNX 파싱 실패 → 시뮬레이션 폴백
                #   (매번 2~3초 낭비 + 에러 로그). 미리 차단해 깔끔히 native 분기.
                entry.engine_handle = f"native_{model_id.value}"
                logger.info(
                    "native 모델 감지 (TRT 빌드 생략, 백엔드가 직접 로드): %s → %s",
                    model_id.value, model_path,
                )
            elif _TRT_ENGINE_AVAILABLE and model_path and os.path.isfile(model_path):
                try:
                    trt_config = TensorRTConfig(
                        enabled=True,
                        fp16=(self._config.trt_precision in (
                            TRTPrecision.FP16, TRTPrecision.INT8,
                        )),
                    )
                    engine = TensorRTEngine(trt_config)
                    engine.build_or_load(
                        onnx_path=model_path,
                        input_shapes=_MODEL_INPUT_SHAPES.get(model_id, {}),
                    )
                    entry.engine_handle = engine
                except Exception as exc:
                    # TRT 빌드 실패 시 시뮬레이션 폴백
                    logger.warning(
                        "TRT 엔진 빌드 실패 → 시뮬레이션 폴백: %s — %s",
                        model_id.value, exc,
                    )
                    entry.engine_handle = f"sim_handle_{model_id.value}"
            else:
                # TRT 미설치 시 시뮬레이션 핸들
                entry.engine_handle = f"sim_handle_{model_id.value}"

            entry.status = EngineStatus.READY
            entry.loaded_at = time.monotonic()
            entry.vram_mb = vram_needed

            logger.info(
                "모델 로드: %s (%.0fMB, stream=%s)",
                model_id.value, vram_needed, entry.stream_id.value,
            )
            return True

    def unload_model(self, model_id: ModelID) -> float:
        """
        모델 언로드.

        Args:
            model_id: 언로드할 모델

        Returns:
            해제된 VRAM (MB)
        """
        with self._lock:
            return self._unload_entry(model_id)

    def _unload_entry(self, model_id: ModelID) -> float:
        """내부 언로드 (lock 보유 상태)."""
        entry = self._entries.get(model_id)
        if entry is None or entry.status == EngineStatus.UNLOADED:
            return 0.0

        freed = entry.vram_mb

        # TRT 엔진 해제
        if _TRT_ENGINE_AVAILABLE and hasattr(entry.engine_handle, "release"):
            try:
                entry.engine_handle.release()
            except Exception:
                logger.exception("TRT 엔진 해제 오류: %s", model_id.value)

        # GPUManager VRAM 해제
        if self._gpu_manager is not None:
            self._gpu_manager.deallocate(model_id.value)

        entry.engine_handle = None
        entry.status = EngineStatus.UNLOADED
        entry.vram_mb = 0.0

        logger.info("모델 언로드: %s (%.0fMB)", model_id.value, freed)
        return freed

    # =========================================================================
    # 일괄 로드 / 워밍업
    # =========================================================================
    def load_all(self) -> int:
        """
        전체 모델 일괄 로드.

        Returns:
            성공적으로 로드된 모델 수
        """
        loaded = 0
        for mid in ModelID:
            if self.load_model(mid):
                loaded += 1
        return loaded

    def warmup_model(self, model_id: ModelID) -> bool:
        """
        모델 워밍업 (첫 추론 지연 제거).

        Args:
            model_id: 워밍업할 모델

        Returns:
            워밍업 성공 여부
        """
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None or entry.status != EngineStatus.READY:
                return False

            entry.status = EngineStatus.WARMING

            # 실제 TRT 엔진 워밍업 (더미 추론으로 첫 지연 제거)
            if _TRT_ENGINE_AVAILABLE and hasattr(entry.engine_handle, "run_single"):
                try:
                    import numpy as np
                    shapes = _MODEL_INPUT_SHAPES.get(model_id, {})
                    for _name, shape in shapes.items():
                        dummy = np.zeros(shape, dtype=np.float32)
                        entry.engine_handle.run_single(dummy)
                        break  # 첫 입력만 워밍업
                except Exception as exc:
                    logger.warning("워밍업 추론 실패 (무시): %s — %s", model_id.value, exc)

            entry.status = EngineStatus.READY
            logger.info("모델 워밍업: %s", model_id.value)
            return True

    def warmup_all(self) -> int:
        """전체 모델 워밍업. 성공 수 반환."""
        count = 0
        for mid in ModelID:
            if self.warmup_model(mid):
                count += 1
        return count

    # =========================================================================
    # 조회
    # =========================================================================
    def get_engine_handle(self, model_id: ModelID) -> Any:
        """READY 상태 모델의 엔진 핸들 반환 (미로드 시 None)."""
        entry = self._entries.get(model_id)
        if entry is None or entry.status != EngineStatus.READY:
            return None
        return entry.engine_handle

    def get_stream_id(self, model_id: ModelID) -> StreamID | None:
        """모델에 바인딩된 StreamID 반환."""
        return _MODEL_STREAM_BINDING.get(model_id)

    def get_status(self, model_id: ModelID) -> EngineStatus:
        """모델 상태 조회."""
        entry = self._entries.get(model_id)
        if entry is None:
            return EngineStatus.UNLOADED
        return entry.status

    def is_model_ready(self, model_id: ModelID) -> bool:
        """모델 사용 가능 여부."""
        return self.get_status(model_id) == EngineStatus.READY

    def all_ready(self) -> bool:
        """전체 모델 READY 여부."""
        return all(
            self.is_model_ready(mid) for mid in ModelID
        )

    # =========================================================================
    # 추론 카운터
    # =========================================================================
    def record_inference(self, model_id: ModelID) -> None:
        """추론 카운터 증가."""
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is not None:
                entry.inference_count += 1
                entry.last_inference_at = time.monotonic()

    def get_inference_count(self, model_id: ModelID) -> int:
        """모델별 누적 추론 횟수."""
        entry = self._entries.get(model_id)
        return entry.inference_count if entry else 0

    def __repr__(self) -> str:
        statuses = {
            mid.value: self.get_status(mid).value
            for mid in ModelID
        }
        return f"TensorRTPool(models={statuses})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "ModelID",
    "EngineStatus",
    "EngineEntry",
    "TensorRTPool",
]

__version__ = "1.0.0"
