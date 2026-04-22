# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/backends
파일: base_backend.py
설명: 포즈 추정 백엔드 추상 기반 클래스 및 공통 열거형/데이터 클래스

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

설계 원칙:
    - 모든 포즈 백엔드(ViTPose WholeBody, YOLOv8-Pose)의 공통 인터페이스 정의
    - configs/pose/model.yaml의 model_characteristics 섹션에서 모델 특성 로드
    - 열거형 속성은 yaml 값 우선, 폴백으로 표준 상수 사용
    - 설정은 dict[str, Any] | None 형태로 주입받음
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, unique
import logging
import threading

# ============================================================
# 서드파티
# ============================================================
import numpy as np

# ============================================================
# shared 임포트
# ============================================================
from shared.interfaces.detector_interface import BoundingBox

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# 모델 특성 캐시 최대 크기
_MAX_MODEL_CHAR_CACHE_SIZE: int = 32


# ============================================================
# 모델 특성 기본값 (yaml 로드 실패 시 폴백)
# configs/pose/model.yaml의 model_characteristics 섹션과 동기화
# COCO/MediaPipe 국제 표준 기반 - 변경 금지
# ============================================================
_DEFAULT_MODEL_CHARACTERISTICS: dict[str, dict[str, object]] = {
    "vitpose": {
        "keypoint_count": 133,  # COCO-WholeBody 표준 (Body17+Foot6+Face68+Hand42)
        "keypoint_format": "wholebody",
        "supports_gpu": True,
        "realtime_capable": True,
    },
    "yolov8-pose": {
        "keypoint_count": 17,  # COCO 표준
        "keypoint_format": "coco",
        "supports_gpu": True,
        "realtime_capable": True,
    },
    "hybrid": {
        "keypoint_count": 17,  # 통합 형식 (COCO 기준)
        "keypoint_format": "unified",
        "supports_gpu": True,
        "realtime_capable": True,
    },
}

# ============================================================
# 상태 전이 맵 — 유효한 전이만 허용
# ============================================================
_VALID_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "uninitialized": frozenset({"loading"}),
    "loading": frozenset({"ready", "error"}),
    "ready": frozenset({"inferring", "unloaded", "loading"}),
    "inferring": frozenset({"ready", "error"}),
    "error": frozenset({"unloaded", "loading"}),
    "unloaded": frozenset({"loading"}),
}


# ============================================================
# 열거형 정의
# ============================================================
@unique
class PoseModelType(str, Enum):
    """
    포즈 추정 모델 유형.

    각 모델의 특성:
        - VITPOSE: WholeBody 133kp, ONNX Runtime/PyTorch, Top-Down 방식
        - YOLOV8_POSE: 다중 인물, GPU 가속, 17개 키포인트 (COCO)
        - HYBRID: 적응형 하이브리드 (동작 속도 기반 자동 선택)

    Note:
        모델 특성은 configs/pose/model.yaml의 model_characteristics에서
        로드됩니다. 열거형 속성은 폴백용 기본값입니다.
    """
    VITPOSE = "vitpose"
    YOLOV8_POSE = "yolov8-pose"
    HYBRID = "hybrid"

    @property
    def keypoint_count(self) -> int:
        """
        해당 모델의 키포인트 개수.

        Note:
            이 값은 폴백용 기본값입니다.
            실제 사용 시 yaml에서 로드된 값을 사용하세요.
        """
        chars = _DEFAULT_MODEL_CHARACTERISTICS.get(self.value, {})
        count = chars.get("keypoint_count", 17)
        return int(count) if isinstance(count, (int, float)) else 17

    @property
    def keypoint_format(self) -> str:
        """해당 모델의 키포인트 형식."""
        chars = _DEFAULT_MODEL_CHARACTERISTICS.get(self.value, {})
        fmt = chars.get("keypoint_format", "coco")
        return str(fmt) if fmt is not None else "coco"

    @property
    def supports_gpu(self) -> bool:
        """GPU 지원 여부."""
        chars = _DEFAULT_MODEL_CHARACTERISTICS.get(self.value, {})
        val = chars.get("supports_gpu", False)
        return bool(val)

    @property
    def is_realtime_capable(self) -> bool:
        """실시간 처리 가능 여부."""
        chars = _DEFAULT_MODEL_CHARACTERISTICS.get(self.value, {})
        val = chars.get("realtime_capable", True)
        return bool(val)

    @classmethod
    def get_all_types(cls) -> list[PoseModelType]:
        """모든 모델 유형 반환."""
        return list(cls)

    @classmethod
    def from_string(cls, value: str) -> PoseModelType:
        """
        문자열에서 모델 유형 생성.

        Args:
            value: 모델 유형 문자열

        Returns:
            PoseModelType 인스턴스

        Raises:
            ValueError: 유효하지 않은 모델 유형
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_types = [t.value for t in cls]
            raise ValueError(
                f"유효하지 않은 모델 유형: {value}. "
                f"가능한 값: {valid_types}"
            )


@unique
class BackendState(str, Enum):
    """
    백엔드 상태.

    상태 전이:
        UNINITIALIZED → LOADING → READY ↔ INFERRING
                                    ↓
                                  ERROR
                                    ↓
                                UNLOADED
    """
    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    INFERRING = "inferring"
    ERROR = "error"
    UNLOADED = "unloaded"

    @property
    def is_operational(self) -> bool:
        """운영 가능한 상태인지 여부."""
        return self in (BackendState.READY, BackendState.INFERRING)

    @property
    def can_infer(self) -> bool:
        """추론 가능한 상태인지 여부."""
        return self == BackendState.READY

    def can_transition_to(self, target: BackendState) -> bool:
        """해당 상태로 전이 가능한지 여부."""
        valid_targets = _VALID_STATE_TRANSITIONS.get(self.value, frozenset())
        return target.value in valid_targets


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class InferenceResult:
    """
    백엔드 추론 결과.

    모든 백엔드에서 동일한 형식으로 결과를 반환합니다.

    Attributes:
        keypoints: 각 인물의 키포인트 배열 리스트 [(N, 3)]
        keypoint_format: 키포인트 형식 ("coco", "wholebody", "unified")
        processing_time_ms: 추론 소요 시간 (밀리초)
        model_type: 사용된 모델 유형
        bounding_boxes: 인물 바운딩 박스 (선택적)
        metadata: 추가 메타데이터
    """
    keypoints: list[np.ndarray]
    keypoint_format: str
    processing_time_ms: float = 0.0
    model_type: PoseModelType = PoseModelType.YOLOV8_POSE

    # 추가 메타데이터
    bounding_boxes: list[BoundingBox] | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def person_count(self) -> int:
        """감지된 인원 수."""
        return len(self.keypoints)

    @property
    def is_empty(self) -> bool:
        """결과가 비어있는지 여부."""
        return len(self.keypoints) == 0

    @property
    def average_confidence(self) -> float:
        """평균 키포인트 신뢰도."""
        if self.is_empty:
            return 0.0

        total_conf = 0.0
        total_count = 0

        for kpts in self.keypoints:
            if kpts.shape[1] >= 3:
                confidences = kpts[:, 2]
                total_conf += float(np.sum(confidences))
                total_count += len(confidences)

        return total_conf / total_count if total_count > 0 else 0.0


# ============================================================
# 추상 기반 클래스
# ============================================================
class PoseBackend(ABC):
    """
    포즈 추정 백엔드 추상 기반 클래스.

    모든 포즈 추정 백엔드(ViTPose WholeBody, YOLOv8-Pose)가
    구현해야 하는 공통 인터페이스를 정의합니다.

    구현 요구사항:
        - model_type: 백엔드 모델 유형 (추상 속성)
        - load_model(): 모델 로드 및 초기화
        - unload_model(): 모델 언로드 및 리소스 해제
        - infer(): 프레임에서 키포인트 추출
        - get_keypoint_format(): 키포인트 형식 반환

    설정 로드:
        configs/pose/model.yaml에서 설정을 로드하고
        dict[str, Any] 형태로 전달받습니다.

    Example:
        >>> pose_config = {"model_path": "weights/vitpose.onnx"}
        >>> backend = ViTPoseBackend(config=pose_config)
        >>> backend.load_model()
        >>> result = backend.infer(frame)
    """

    def __init__(
        self,
        config: dict[str, object] | None = None,
        weights_path: str | None = None,
    ) -> None:
        """
        백엔드 초기화.

        Args:
            config: 포즈 모델 설정 (dict[str, Any])
                   None이면 기본값 사용
            weights_path: 모델 가중치 경로 (선택적)
                         커스텀 가중치가 지정되면 설정보다 우선
        """
        self._config: dict[str, object] = config if config is not None else {}
        self._weights_path: str | None = weights_path
        self._is_loaded: bool = False
        self._state: BackendState = BackendState.UNINITIALIZED
        self._model: object = None

        # 스레드 안전 락
        self._lock: threading.RLock = threading.RLock()

        # 성능 메트릭
        self._inference_count: int = 0
        self._total_inference_time_ms: float = 0.0
        self._min_inference_time_ms: float = float('inf')
        self._max_inference_time_ms: float = 0.0

        # 모델 특성 캐시 (get_model_characteristic 조회 최적화)
        self._model_char_cache: dict[tuple[str, int | None], object] = {}

    # --------------------------------------------------------
    # 상태 전이 (스레드 안전)
    # --------------------------------------------------------
    def _transition_state(self, target: BackendState) -> None:
        """
        상태 전이 (유효성 검증 + 스레드 안전).

        Args:
            target: 전이 대상 상태

        Raises:
            RuntimeError: 유효하지 않은 상태 전이
        """
        with self._lock:
            if not self._state.can_transition_to(target):
                raise RuntimeError(
                    f"유효하지 않은 상태 전이: {self._state.value} → {target.value}. "
                    f"허용: {_VALID_STATE_TRANSITIONS.get(self._state.value, set())}"
                )
            self._state = target

    # --------------------------------------------------------
    # 설정 접근 헬퍼
    # --------------------------------------------------------
    def _get_config_value(self, key: str, default: object = None) -> object:
        """
        설정 값 조회.

        중첩 키를 지원합니다 (예: "inference.confidence_threshold").

        Args:
            key: 설정 키 (dot notation 지원)
            default: 기본값

        Returns:
            설정 값 또는 기본값
        """
        if not self._config:
            return default

        # dot notation 지원
        keys = key.split(".")
        value: object = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    # --------------------------------------------------------
    # 추상 속성
    # --------------------------------------------------------
    @property
    @abstractmethod
    def model_type(self) -> PoseModelType:
        """백엔드의 모델 유형."""
        pass

    # --------------------------------------------------------
    # 구현된 속성
    # --------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        """모델 로드 여부."""
        return self._is_loaded

    @property
    def state(self) -> BackendState:
        """현재 백엔드 상태."""
        return self._state

    @property
    def config(self) -> dict[str, object]:
        """현재 설정 (방어적 복사본)."""
        return dict(self._config)

    @property
    def weights_path(self) -> str | None:
        """현재 가중치 경로."""
        return self._weights_path

    @property
    def average_inference_time_ms(self) -> float:
        """평균 추론 시간 (밀리초)."""
        with self._lock:
            if self._inference_count == 0:
                return 0.0
            return self._total_inference_time_ms / self._inference_count

    @property
    def inference_count(self) -> int:
        """총 추론 횟수."""
        return self._inference_count

    # --------------------------------------------------------
    # 추상 메서드
    # --------------------------------------------------------
    @abstractmethod
    def load_model(self) -> None:
        """
        모델 로드.

        모델 가중치를 메모리에 로드하고 추론 준비를 완료합니다.
        커스텀 가중치 경로가 지정된 경우 우선 사용합니다.

        Raises:
            ModelLoadException: 모델 로드 실패 시
        """
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """
        모델 언로드.

        메모리에서 모델을 해제하고 리소스를 정리합니다.
        GPU 메모리도 해제합니다.
        """
        pass

    @abstractmethod
    def infer(
        self,
        frame: np.ndarray,
        person_boxes: list[BoundingBox] | None = None,
    ) -> list[np.ndarray]:
        """
        포즈 추론.

        Args:
            frame: BGR 이미지 (H, W, 3)
            person_boxes: 사전 탐지된 인물 영역 (선택적)

        Returns:
            list[np.ndarray]: 각 인물의 키포인트 배열 리스트
                             각 배열은 (N, 3) 형태 - (x, y, confidence)

        Raises:
            ModelInferenceException: 추론 실패 시
        """
        pass

    @abstractmethod
    def get_keypoint_format(self) -> str:
        """
        키포인트 형식 반환.

        Returns:
            str: "coco", "wholebody", "unified" 중 하나
        """
        pass

    # --------------------------------------------------------
    # 공통 유틸리티 메서드
    # --------------------------------------------------------
    def _update_inference_metrics(self, elapsed_ms: float) -> None:
        """
        추론 메트릭 업데이트 (스레드 안전).

        Args:
            elapsed_ms: 추론 소요 시간 (밀리초)
        """
        with self._lock:
            self._inference_count += 1
            self._total_inference_time_ms += elapsed_ms
            self._min_inference_time_ms = min(self._min_inference_time_ms, elapsed_ms)
            self._max_inference_time_ms = max(self._max_inference_time_ms, elapsed_ms)

    def reset_metrics(self) -> None:
        """메트릭 초기화 (스레드 안전)."""
        with self._lock:
            self._inference_count = 0
            self._total_inference_time_ms = 0.0
            self._min_inference_time_ms = float('inf')
            self._max_inference_time_ms = 0.0

    def get_metrics(self) -> dict[str, object]:
        """
        성능 메트릭 반환.

        Returns:
            메트릭 딕셔너리
        """
        with self._lock:
            return {
                "model_type": self.model_type.value,
                "is_loaded": self._is_loaded,
                "state": self._state.value,
                "inference_count": self._inference_count,
                "total_inference_time_ms": self._total_inference_time_ms,
                "average_inference_time_ms": (
                    self._total_inference_time_ms / self._inference_count
                    if self._inference_count > 0 else 0.0
                ),
                "min_inference_time_ms": (
                    self._min_inference_time_ms
                    if self._min_inference_time_ms != float('inf')
                    else 0.0
                ),
                "max_inference_time_ms": self._max_inference_time_ms,
            }

    def get_model_characteristic(self, key: str, default: object = None) -> object:
        """
        모델 특성 조회 (캐싱 적용, 크기 제한).

        config의 model_characteristics 또는 _DEFAULT_MODEL_CHARACTERISTICS에서
        해당 모델의 특성을 조회합니다. 동일 키 재조회 시 캐시된 값을 반환합니다.

        Args:
            key: 특성 키 (예: "keypoint_count", "supports_gpu")
            default: 기본값 (둘 다 없을 경우)

        Returns:
            특성 값
        """
        # 캐시 키 생성 (default 포함하여 구분)
        cache_key = (key, id(default) if default is not None else None)

        # 캐시 히트 확인
        if cache_key in self._model_char_cache:
            return self._model_char_cache[cache_key]

        # config에서 model_characteristics 조회
        model_chars = self._config.get('model_characteristics', {})

        result = default  # 기본값으로 초기화

        if isinstance(model_chars, dict) and model_chars:
            model_key = self.model_type.value.replace("-", "_")
            char_dict = model_chars.get(model_key, {})
            if isinstance(char_dict, dict) and key in char_dict:
                result = char_dict[key]
                self._cache_characteristic(cache_key, result)
                return result

        # 폴백: 기본 특성 딕셔너리
        fallback_chars = _DEFAULT_MODEL_CHARACTERISTICS.get(
            self.model_type.value, {}
        )
        result = fallback_chars.get(key, default)

        # 결과 캐시에 저장
        self._cache_characteristic(cache_key, result)
        return result

    def _cache_characteristic(
        self,
        cache_key: tuple[str, int | None],
        value: object,
    ) -> None:
        """캐시에 저장 (크기 제한 적용)."""
        if len(self._model_char_cache) >= _MAX_MODEL_CHAR_CACHE_SIZE:
            self._model_char_cache.clear()
        self._model_char_cache[cache_key] = value

    def validate_state(self, required_state: BackendState) -> bool:
        """
        상태 검증.

        Args:
            required_state: 필요한 상태

        Returns:
            상태 일치 여부
        """
        return self._state == required_state

    def __repr__(self) -> str:
        """문자열 표현."""
        return (
            f"{self.__class__.__name__}("
            f"model_type={self.model_type.value}, "
            f"is_loaded={self._is_loaded}, "
            f"state={self._state.value}, "
            f"inference_count={self._inference_count})"
        )

    def __enter__(self) -> PoseBackend:
        """컨텍스트 매니저 진입."""
        if not self._is_loaded:
            self.load_model()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """컨텍스트 매니저 종료 (예외 안전)."""
        try:
            self.unload_model()
        except Exception:
            logger.exception("모델 언로드 중 예외 발생")


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # 열거형
    "PoseModelType",
    "BackendState",

    # 데이터 클래스
    "InferenceResult",

    # 추상 클래스
    "PoseBackend",

    # 상수 (폴백용)
    "_DEFAULT_MODEL_CHARACTERISTICS",
]

__version__ = "1.0.0"
