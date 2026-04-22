# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: pose_estimation/backends/base_backend.py
설명: 포즈 추정 백엔드 추상 기반 클래스 단위 테스트

작성자: SPOIN_COURTVIEW
버전: 1.0.0
"""

from __future__ import annotations

import threading
from unittest.mock import patch

import numpy as np
import pytest

from pose_estimation.backends.base_backend import (
    BackendState,
    InferenceResult,
    PoseBackend,
    PoseModelType,
    _DEFAULT_MODEL_CHARACTERISTICS,
    _MAX_MODEL_CHAR_CACHE_SIZE,
    _VALID_STATE_TRANSITIONS,
    __version__,
)
from shared.interfaces.detector_interface import BoundingBox


# ============================================================
# 테스트용 구체 구현 (추상 클래스 인스턴스화)
# ============================================================
class _ConcreteBackend(PoseBackend):
    """테스트용 PoseBackend 구체 구현."""

    @property
    def model_type(self) -> PoseModelType:
        return PoseModelType.YOLOV8_POSE

    def load_model(self) -> None:
        self._transition_state(BackendState.LOADING)
        self._model = "mock_model"
        self._is_loaded = True
        self._transition_state(BackendState.READY)

    def unload_model(self) -> None:
        self._model = None
        self._is_loaded = False
        self._state = BackendState.UNLOADED

    def infer(
        self,
        frame: np.ndarray,
        person_boxes: list[BoundingBox] | None = None,
    ) -> list[np.ndarray]:
        self._transition_state(BackendState.INFERRING)
        result = [np.array([[100.0, 200.0, 0.95]] * 17)]
        self._transition_state(BackendState.READY)
        return result

    def get_keypoint_format(self) -> str:
        return "coco"


class _FailingUnloadBackend(_ConcreteBackend):
    """unload_model이 예외를 발생시키는 테스트용 백엔드."""

    def unload_model(self) -> None:
        raise RuntimeError("unload 실패")


# ============================================================
# A. PoseModelType 열거형 테스트
# ============================================================
class TestPoseModelType:
    """PoseModelType 열거형 테스트."""

    def test_enum_values(self) -> None:
        """열거형 값 확인."""
        assert PoseModelType.VITPOSE.value == "vitpose"
        assert PoseModelType.YOLOV8_POSE.value == "yolov8-pose"
        assert PoseModelType.HYBRID.value == "hybrid"

    def test_unique_values(self) -> None:
        """모든 값이 고유한지 확인."""
        values = [m.value for m in PoseModelType]
        assert len(values) == len(set(values))

    def test_keypoint_count_vitpose(self) -> None:
        """ViTPose 키포인트 수 = 133."""
        assert PoseModelType.VITPOSE.keypoint_count == 133

    def test_keypoint_count_yolov8(self) -> None:
        """YOLOv8 키포인트 수 = 17."""
        assert PoseModelType.YOLOV8_POSE.keypoint_count == 17

    def test_keypoint_count_hybrid(self) -> None:
        """Hybrid 키포인트 수 = 17."""
        assert PoseModelType.HYBRID.keypoint_count == 17

    def test_keypoint_format(self) -> None:
        """키포인트 형식 확인."""
        assert PoseModelType.VITPOSE.keypoint_format == "wholebody"
        assert PoseModelType.YOLOV8_POSE.keypoint_format == "coco"
        assert PoseModelType.HYBRID.keypoint_format == "unified"

    def test_supports_gpu(self) -> None:
        """모든 모델 GPU 지원."""
        for model_type in PoseModelType:
            assert model_type.supports_gpu is True

    def test_is_realtime_capable(self) -> None:
        """실시간 처리 가능 여부."""
        for model_type in PoseModelType:
            assert model_type.is_realtime_capable is True

    def test_get_all_types(self) -> None:
        """모든 유형 반환."""
        all_types = PoseModelType.get_all_types()
        assert len(all_types) == 3
        assert PoseModelType.VITPOSE in all_types

    def test_from_string_valid(self) -> None:
        """유효한 문자열 변환."""
        assert PoseModelType.from_string("vitpose") == PoseModelType.VITPOSE
        assert PoseModelType.from_string("VITPOSE") == PoseModelType.VITPOSE
        assert PoseModelType.from_string("yolov8-pose") == PoseModelType.YOLOV8_POSE

    def test_from_string_invalid(self) -> None:
        """유효하지 않은 문자열 → ValueError."""
        with pytest.raises(ValueError, match="유효하지 않은 모델 유형"):
            PoseModelType.from_string("invalid")


# ============================================================
# B. BackendState 열거형 테스트
# ============================================================
class TestBackendState:
    """BackendState 열거형 테스트."""

    def test_enum_values(self) -> None:
        """열거형 값 확인."""
        assert BackendState.UNINITIALIZED.value == "uninitialized"
        assert BackendState.LOADING.value == "loading"
        assert BackendState.READY.value == "ready"
        assert BackendState.INFERRING.value == "inferring"
        assert BackendState.ERROR.value == "error"
        assert BackendState.UNLOADED.value == "unloaded"

    def test_is_operational(self) -> None:
        """운영 가능 상태 확인."""
        assert BackendState.READY.is_operational is True
        assert BackendState.INFERRING.is_operational is True
        assert BackendState.UNINITIALIZED.is_operational is False
        assert BackendState.ERROR.is_operational is False
        assert BackendState.UNLOADED.is_operational is False

    def test_can_infer(self) -> None:
        """추론 가능 상태 확인."""
        assert BackendState.READY.can_infer is True
        assert BackendState.INFERRING.can_infer is False
        assert BackendState.LOADING.can_infer is False

    def test_can_transition_to_valid(self) -> None:
        """유효한 상태 전이."""
        assert BackendState.UNINITIALIZED.can_transition_to(BackendState.LOADING) is True
        assert BackendState.LOADING.can_transition_to(BackendState.READY) is True
        assert BackendState.LOADING.can_transition_to(BackendState.ERROR) is True
        assert BackendState.READY.can_transition_to(BackendState.INFERRING) is True
        assert BackendState.INFERRING.can_transition_to(BackendState.READY) is True
        assert BackendState.INFERRING.can_transition_to(BackendState.ERROR) is True
        assert BackendState.ERROR.can_transition_to(BackendState.UNLOADED) is True

    def test_can_transition_to_invalid(self) -> None:
        """유효하지 않은 상태 전이."""
        assert BackendState.UNINITIALIZED.can_transition_to(BackendState.READY) is False
        assert BackendState.UNINITIALIZED.can_transition_to(BackendState.INFERRING) is False
        assert BackendState.LOADING.can_transition_to(BackendState.INFERRING) is False
        assert BackendState.UNLOADED.can_transition_to(BackendState.READY) is False


# ============================================================
# C. InferenceResult 데이터클래스 테스트
# ============================================================
class TestInferenceResult:
    """InferenceResult 데이터클래스 테스트."""

    def test_basic_creation(self) -> None:
        """기본 생성."""
        kpts = [np.array([[100.0, 200.0, 0.9]] * 17)]
        result = InferenceResult(keypoints=kpts, keypoint_format="coco")
        assert result.person_count == 1
        assert result.keypoint_format == "coco"
        assert result.processing_time_ms == 0.0
        assert result.model_type == PoseModelType.YOLOV8_POSE

    def test_empty_result(self) -> None:
        """빈 결과."""
        result = InferenceResult(keypoints=[], keypoint_format="coco")
        assert result.is_empty is True
        assert result.person_count == 0
        assert result.average_confidence == 0.0

    def test_multiple_persons(self) -> None:
        """다중 인물."""
        kpts = [
            np.array([[10.0, 20.0, 0.8]] * 17),
            np.array([[30.0, 40.0, 0.6]] * 17),
        ]
        result = InferenceResult(keypoints=kpts, keypoint_format="coco")
        assert result.person_count == 2
        assert result.is_empty is False

    def test_average_confidence(self) -> None:
        """평균 신뢰도 계산."""
        kpts = [np.array([[10.0, 20.0, 1.0]] * 17)]
        result = InferenceResult(keypoints=kpts, keypoint_format="coco")
        assert abs(result.average_confidence - 1.0) < 1e-6

    def test_average_confidence_mixed(self) -> None:
        """혼합 신뢰도."""
        kpts = [np.array([[0.0, 0.0, 0.5], [0.0, 0.0, 1.0]])]
        result = InferenceResult(keypoints=kpts, keypoint_format="coco")
        assert abs(result.average_confidence - 0.75) < 1e-6

    def test_slots_applied(self) -> None:
        """__slots__ 적용 확인."""
        kpts = [np.array([[0.0, 0.0, 0.5]])]
        result = InferenceResult(keypoints=kpts, keypoint_format="coco")
        assert hasattr(result, "__slots__")

    def test_metadata_default(self) -> None:
        """metadata 기본값 = 빈 dict."""
        result = InferenceResult(keypoints=[], keypoint_format="coco")
        assert result.metadata == {}

    def test_bounding_boxes_none(self) -> None:
        """bounding_boxes 기본값 = None."""
        result = InferenceResult(keypoints=[], keypoint_format="coco")
        assert result.bounding_boxes is None


# ============================================================
# D. PoseBackend 추상 클래스 테스트
# ============================================================
class TestPoseBackend:
    """PoseBackend 추상 클래스 테스트."""

    def test_initial_state(self) -> None:
        """초기 상태 확인."""
        backend = _ConcreteBackend()
        assert backend.state == BackendState.UNINITIALIZED
        assert backend.is_loaded is False
        assert backend.inference_count == 0
        assert backend.average_inference_time_ms == 0.0

    def test_config_default_empty(self) -> None:
        """config 기본값 = 빈 dict."""
        backend = _ConcreteBackend()
        assert backend.config == {}

    def test_config_injection(self) -> None:
        """config 주입."""
        cfg = {"model_path": "test.onnx", "threshold": 0.5}
        backend = _ConcreteBackend(config=cfg)
        assert backend.config == cfg

    def test_config_defensive_copy(self) -> None:
        """config 프로퍼티는 방어적 복사본 반환."""
        cfg = {"key": "value"}
        backend = _ConcreteBackend(config=cfg)
        returned = backend.config
        returned["injected"] = "malicious"
        # 내부 config는 변조되지 않아야 함
        assert "injected" not in backend.config

    def test_weights_path(self) -> None:
        """가중치 경로."""
        backend = _ConcreteBackend(weights_path="/path/to/weights.pt")
        assert backend.weights_path == "/path/to/weights.pt"

    def test_load_model(self) -> None:
        """모델 로드."""
        backend = _ConcreteBackend()
        backend.load_model()
        assert backend.is_loaded is True
        assert backend.state == BackendState.READY

    def test_unload_model(self) -> None:
        """모델 언로드."""
        backend = _ConcreteBackend()
        backend.load_model()
        backend.unload_model()
        assert backend.is_loaded is False
        assert backend.state == BackendState.UNLOADED

    def test_model_type(self) -> None:
        """모델 유형."""
        backend = _ConcreteBackend()
        assert backend.model_type == PoseModelType.YOLOV8_POSE

    def test_get_keypoint_format(self) -> None:
        """키포인트 형식."""
        backend = _ConcreteBackend()
        assert backend.get_keypoint_format() == "coco"

    def test_repr(self) -> None:
        """문자열 표현."""
        backend = _ConcreteBackend()
        r = repr(backend)
        assert "_ConcreteBackend" in r
        assert "yolov8-pose" in r

    def test_validate_state(self) -> None:
        """상태 검증."""
        backend = _ConcreteBackend()
        assert backend.validate_state(BackendState.UNINITIALIZED) is True
        assert backend.validate_state(BackendState.READY) is False


# ============================================================
# E. 상태 전이 테스트
# ============================================================
class TestStateTransition:
    """상태 전이 테스트."""

    def test_valid_transition(self) -> None:
        """유효한 상태 전이 성공."""
        backend = _ConcreteBackend()
        backend._transition_state(BackendState.LOADING)
        assert backend.state == BackendState.LOADING

    def test_invalid_transition_raises(self) -> None:
        """유효하지 않은 상태 전이 → RuntimeError."""
        backend = _ConcreteBackend()
        with pytest.raises(RuntimeError, match="유효하지 않은 상태 전이"):
            backend._transition_state(BackendState.INFERRING)

    def test_full_lifecycle(self) -> None:
        """전체 생명주기: UNINITIALIZED → LOADING → READY → INFERRING → READY."""
        backend = _ConcreteBackend()
        assert backend.state == BackendState.UNINITIALIZED
        backend.load_model()
        assert backend.state == BackendState.READY

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        backend.infer(frame)
        assert backend.state == BackendState.READY


# ============================================================
# F. 메트릭 테스트
# ============================================================
class TestMetrics:
    """성능 메트릭 테스트."""

    def test_update_inference_metrics(self) -> None:
        """메트릭 업데이트."""
        backend = _ConcreteBackend()
        backend._update_inference_metrics(10.0)
        backend._update_inference_metrics(20.0)
        assert backend.inference_count == 2
        assert backend.average_inference_time_ms == 15.0

    def test_reset_metrics(self) -> None:
        """메트릭 초기화."""
        backend = _ConcreteBackend()
        backend._update_inference_metrics(10.0)
        backend.reset_metrics()
        assert backend.inference_count == 0
        assert backend.average_inference_time_ms == 0.0

    def test_get_metrics(self) -> None:
        """get_metrics 딕셔너리 구조."""
        backend = _ConcreteBackend()
        backend.load_model()
        backend._update_inference_metrics(15.0)
        backend._update_inference_metrics(25.0)

        metrics = backend.get_metrics()
        assert metrics["model_type"] == "yolov8-pose"
        assert metrics["is_loaded"] is True
        assert metrics["state"] == "ready"
        assert metrics["inference_count"] == 2
        assert abs(metrics["average_inference_time_ms"] - 20.0) < 1e-6
        assert abs(metrics["min_inference_time_ms"] - 15.0) < 1e-6
        assert abs(metrics["max_inference_time_ms"] - 25.0) < 1e-6

    def test_metrics_min_default_zero(self) -> None:
        """추론 전 min은 0.0으로 표시."""
        backend = _ConcreteBackend()
        metrics = backend.get_metrics()
        assert metrics["min_inference_time_ms"] == 0.0

    def test_metrics_thread_safety(self) -> None:
        """멀티스레드 메트릭 업데이트 경쟁 조건 없음."""
        backend = _ConcreteBackend()
        n_threads = 10
        n_updates = 100

        def update_metrics() -> None:
            for i in range(n_updates):
                backend._update_inference_metrics(float(i))

        threads = [threading.Thread(target=update_metrics) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert backend.inference_count == n_threads * n_updates


# ============================================================
# G. config 헬퍼 테스트
# ============================================================
class TestConfigHelper:
    """_get_config_value 테스트."""

    def test_simple_key(self) -> None:
        """단순 키 조회."""
        backend = _ConcreteBackend(config={"threshold": 0.5})
        assert backend._get_config_value("threshold") == 0.5

    def test_dot_notation(self) -> None:
        """dot notation 중첩 키 조회."""
        cfg = {"inference": {"confidence_threshold": 0.3}}
        backend = _ConcreteBackend(config=cfg)
        assert backend._get_config_value("inference.confidence_threshold") == 0.3

    def test_missing_key_default(self) -> None:
        """누락된 키 → 기본값 반환."""
        backend = _ConcreteBackend(config={"a": 1})
        assert backend._get_config_value("b", default=42) == 42

    def test_empty_config_default(self) -> None:
        """빈 config → 기본값 반환."""
        backend = _ConcreteBackend()
        assert backend._get_config_value("any_key", default="fallback") == "fallback"


# ============================================================
# H. 모델 특성 캐시 테스트
# ============================================================
class TestModelCharacteristic:
    """get_model_characteristic 테스트."""

    def test_default_characteristic(self) -> None:
        """기본 특성 딕셔너리에서 조회."""
        backend = _ConcreteBackend()
        assert backend.get_model_characteristic("keypoint_count") == 17
        assert backend.get_model_characteristic("supports_gpu") is True

    def test_config_override(self) -> None:
        """config의 model_characteristics가 기본값보다 우선."""
        cfg = {
            "model_characteristics": {
                "yolov8_pose": {"keypoint_count": 25},
            }
        }
        backend = _ConcreteBackend(config=cfg)
        assert backend.get_model_characteristic("keypoint_count") == 25

    def test_cache_hit(self) -> None:
        """캐시 적중 확인."""
        backend = _ConcreteBackend()
        backend.get_model_characteristic("keypoint_count")
        # 두 번째 호출은 캐시에서
        assert backend.get_model_characteristic("keypoint_count") == 17
        assert len(backend._model_char_cache) == 1

    def test_cache_size_limit(self) -> None:
        """캐시 크기 제한 (_MAX_MODEL_CHAR_CACHE_SIZE 초과 시 클리어)."""
        backend = _ConcreteBackend()
        # 캐시를 직접 채움
        for i in range(_MAX_MODEL_CHAR_CACHE_SIZE):
            backend._model_char_cache[(f"key_{i}", None)] = i

        assert len(backend._model_char_cache) == _MAX_MODEL_CHAR_CACHE_SIZE

        # 추가 항목 → 클리어 후 1개만 남음
        backend.get_model_characteristic("new_key", default="val")
        assert len(backend._model_char_cache) == 1

    def test_missing_characteristic_default(self) -> None:
        """존재하지 않는 특성 → 기본값."""
        backend = _ConcreteBackend()
        assert backend.get_model_characteristic("nonexistent", default=-1) == -1


# ============================================================
# I. 컨텍스트 매니저 테스트
# ============================================================
class TestContextManager:
    """컨텍스트 매니저 테스트."""

    def test_enter_loads_model(self) -> None:
        """__enter__ 시 모델 자동 로드."""
        with _ConcreteBackend() as backend:
            assert backend.is_loaded is True
            assert backend.state == BackendState.READY

    def test_exit_unloads_model(self) -> None:
        """__exit__ 시 모델 자동 언로드."""
        backend = _ConcreteBackend()
        with backend:
            pass
        assert backend.is_loaded is False

    def test_exit_exception_safe(self) -> None:
        """__exit__에서 unload 예외 발생 시에도 안전하게 종료."""
        backend = _FailingUnloadBackend()
        # 예외가 전파되지 않아야 함
        with backend:
            assert backend.is_loaded is True
        # unload 실패했으므로 is_loaded는 여전히 True일 수 있음 — 중요한 것은 예외 미전파

    def test_already_loaded_skip(self) -> None:
        """이미 로드된 상태에서 __enter__ 시 중복 로드하지 않음."""
        backend = _ConcreteBackend()
        backend.load_model()
        assert backend.is_loaded is True
        with backend:
            assert backend.is_loaded is True


# ============================================================
# J. 모듈 레벨 상수 테스트
# ============================================================
class TestModuleConstants:
    """모듈 레벨 상수 테스트."""

    def test_version(self) -> None:
        """__version__ 확인."""
        assert __version__ == "1.0.0"

    def test_default_characteristics_keys(self) -> None:
        """기본 특성 딕셔너리 키 확인."""
        assert "vitpose" in _DEFAULT_MODEL_CHARACTERISTICS
        assert "yolov8-pose" in _DEFAULT_MODEL_CHARACTERISTICS
        assert "hybrid" in _DEFAULT_MODEL_CHARACTERISTICS

    def test_valid_state_transitions_complete(self) -> None:
        """모든 BackendState에 대한 전이 맵 존재."""
        for state in BackendState:
            assert state.value in _VALID_STATE_TRANSITIONS

    def test_max_cache_size_positive(self) -> None:
        """캐시 최대 크기가 양수."""
        assert _MAX_MODEL_CHAR_CACHE_SIZE > 0
