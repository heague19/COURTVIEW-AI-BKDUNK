# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/backends
파일: __init__.py
설명: 포즈 추정 백엔드 통합 export

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-17
버전: 1.0.0

백엔드 모듈 구조:
    - base_backend.py: 추상 기반 클래스 및 공통 열거형
    - vitpose_backend.py: ViTPose WholeBody 백엔드 (133kp, ONNX/PyTorch)
    - yolov8_backend.py: YOLOv8-Pose 백엔드 (다중 인물, GPU)
    - tensorrt_engine.py: TensorRT 엔진 빌더/캐싱 유틸리티 (ONNX→TRT, FP16)

v1.0.0:
    - ViTPose WholeBody 133kp + YOLOv8-Pose 백엔드 통합 export
    - TensorRT 가속 유틸리티 포함
    - 팩토리 함수 (create_backend) 제공

사용 예시:
    >>> from pose_estimation.backends import (
    ...     PoseBackend,
    ...     PoseModelType,
    ...     ViTPoseBackend,
    ...     YOLOv8PoseBackend,
    ...     create_backend,
    ... )
    >>>
    >>> config = {"variant": "vitpose-b-wholebody", "weights_path": "model.onnx"}
    >>> if VITPOSE_AVAILABLE:
    ...     backend = ViTPoseBackend(config)
    ... else:
    ...     backend = create_backend(PoseModelType.YOLOV8_POSE)
"""
from __future__ import annotations


# ============================================================
# 기반 클래스 및 공통 정의
# ============================================================
from pose_estimation.backends.base_backend import (
    # 열거형
    PoseModelType,
    BackendState,

    # 데이터 클래스
    InferenceResult,

    # 추상 기반 클래스
    PoseBackend,

    # 모델 특성 기본값 (yaml 폴백용)
    _DEFAULT_MODEL_CHARACTERISTICS,
)

# shared 모듈에서 직접 임포트 (base_backend에서 re-export 하지 않음)
from shared.interfaces.detector_interface import BoundingBox

# ============================================================
# 백엔드 구현체
# ============================================================
from pose_estimation.backends.vitpose_backend import (
    ViTPoseBackend,
    VITPOSE_AVAILABLE,
)

# YOLOv8 백엔드 (ultralytics → torch 의존성 - 조건부 import)
try:
    from pose_estimation.backends.yolov8_backend import (
        YOLOv8PoseBackend,
        YOLO_AVAILABLE,
    )
except (ImportError, OSError):
    YOLOv8PoseBackend = None  # type: ignore[assignment,misc]
    YOLO_AVAILABLE = False

# TensorRT 유틸리티 (가용성 플래그만 모듈 레벨 import)
try:
    from pose_estimation.backends.tensorrt_engine import TENSORRT_AVAILABLE
except (ImportError, OSError):
    TENSORRT_AVAILABLE = False


# ============================================================
# 편의 함수
# ============================================================
def get_available_backends() -> dict[str, bool]:
    """
    사용 가능한 백엔드 목록 반환.

    Returns:
        백엔드별 가용성 딕셔너리

    Example:
        >>> get_available_backends()
        {'vitpose': True, 'yolov8': True}
    """
    return {
        "vitpose": VITPOSE_AVAILABLE,
        "yolov8": YOLO_AVAILABLE,
        "tensorrt": TENSORRT_AVAILABLE,
    }


def create_backend(
    model_type: PoseModelType,
    config: dict[str, object] | None = None,
    weights_path: str | None = None,
) -> PoseBackend:
    """
    백엔드 팩토리 함수.

    Args:
        model_type: 백엔드 유형 (PoseModelType.VITPOSE, YOLOV8_POSE)
        config: 포즈 모델 설정 딕셔너리 (해당 백엔드 섹션)
               None이면 각 백엔드의 기본값 사용
        weights_path: 모델 가중치 경로 (선택적)

    Returns:
        생성된 백엔드 인스턴스

    Raises:
        ValueError: 지원하지 않는 모델 유형
        ImportError: 필요한 라이브러리 미설치

    Example:
        >>> backend = create_backend(
        ...     PoseModelType.VITPOSE,
        ...     {"variant": "vitpose-b-wholebody"},
        ... )
    """
    if model_type == PoseModelType.VITPOSE:
        if not VITPOSE_AVAILABLE:
            raise ImportError(
                "ONNX Runtime 또는 PyTorch가 설치되지 않았습니다. "
                "pip install onnxruntime-gpu 또는 pip install torch"
            )
        return ViTPoseBackend(config, weights_path)

    elif model_type == PoseModelType.YOLOV8_POSE:
        if not YOLO_AVAILABLE:
            raise ImportError(
                "Ultralytics가 설치되지 않았습니다. pip install ultralytics"
            )
        return YOLOv8PoseBackend(config, weights_path)

    else:
        raise ValueError(f"지원하지 않는 모델 유형: {model_type}")


# 확장 메타데이터 (변경 가능한 설명 정보)
_EXTENDED_METADATA: dict[str, dict[str, object]] = {
    PoseModelType.VITPOSE: {
        "name": "ViTPose WholeBody",
        "multi_person": False,
        "expected_fps_cpu": 10,
        "expected_fps_gpu": 30,
        "accuracy_level": "highest",
        "memory_usage": "medium",
        "best_for": ["정밀 모션 분석", "손가락 릴리즈", "WholeBody 133kp"],
    },
    PoseModelType.YOLOV8_POSE: {
        "name": "YOLOv8-Pose",
        "multi_person": True,
        "expected_fps_cpu": 15,
        "expected_fps_gpu": 60,
        "accuracy_level": "high",
        "memory_usage": "medium",
        "best_for": ["경기 분석", "다중 선수", "빠른 동작"],
    },
    PoseModelType.HYBRID: {
        "name": "Hybrid (Adaptive)",
        "multi_person": True,
        "expected_fps_cpu": 20,
        "expected_fps_gpu": 45,
        "accuracy_level": "high",
        "memory_usage": "medium",
        "best_for": ["적응형 분석", "동작 속도 기반 자동 선택"],
    },
}


def get_model_characteristics(model_type: PoseModelType) -> dict[str, object]:
    """
    모델 특성 정보 반환.

    _DEFAULT_MODEL_CHARACTERISTICS 기본값에 _EXTENDED_METADATA를 병합합니다.

    Args:
        model_type: 모델 유형

    Returns:
        모델 특성 딕셔너리
    """
    base_chars = _DEFAULT_MODEL_CHARACTERISTICS.get(model_type.value, {}).copy()
    extended = _EXTENDED_METADATA.get(model_type, {})
    base_chars.update(extended)
    return base_chars


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # 열거형
    "PoseModelType",
    "BackendState",

    # 데이터 클래스
    "InferenceResult",
    "BoundingBox",

    # 추상 기반 클래스
    "PoseBackend",

    # 백엔드 구현체
    "ViTPoseBackend",
    "YOLOv8PoseBackend",

    # 가용성 플래그
    "VITPOSE_AVAILABLE",
    "YOLO_AVAILABLE",
    "TENSORRT_AVAILABLE",

    # 편의 함수
    "get_available_backends",
    "create_backend",
    "get_model_characteristics",

    # 모델 특성 기본값 (yaml 폴백용)
    "_DEFAULT_MODEL_CHARACTERISTICS",
]

__version__ = "1.0.0"
