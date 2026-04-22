# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: pose_estimation/backends/vitpose_backend.py
설명: ViTPose WholeBody 133kp 백엔드 단위 테스트

작성자: SPOIN_COURTVIEW
버전: 1.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

from pose_estimation.backends.base_backend import (
    BackendState,
    PoseModelType,
)
from pose_estimation.backends.vitpose_backend import (
    ViTPoseBackend,
    VITPOSE_AVAILABLE,
    ONNX_AVAILABLE,
    TORCH_AVAILABLE,
    CV2_AVAILABLE,
    _IMAGENET_MEAN,
    _IMAGENET_STD,
    _VARIANT_ONNX_FILE_MAP,
    _EXTERNAL_DATA_VARIANTS,
    __version__,
)
from shared.exceptions.analysis_exceptions import (
    ModelLoadException,
    ModelInferenceException,
)
from shared.constants.pose_constants import NUM_KEYPOINTS_WHOLEBODY


# ============================================================
# 테스트 픽스처
# ============================================================
@pytest.fixture
def default_config() -> dict:
    """기본 ViTPose 설정."""
    return {
        "variant": "vitpose-b-wholebody",
        "weights_path": "",
        "input_size": {
            "height": 256,
            "width": 192,
        },
        "inference": {
            "confidence_threshold": 0.3,
            "device": "cpu",
            "half_precision": False,
            "batch_size": 1,
            "warmup_count": 0,
        },
        "onnx": {
            "enable": False,
            "optimization_level": 3,
            "num_threads": 4,
        },
    }


@pytest.fixture
def onnx_config() -> dict:
    """ONNX 활성화 설정."""
    return {
        "variant": "vitpose-b-wholebody",
        "weights_path": "",
        "input_size": {
            "height": 256,
            "width": 192,
        },
        "inference": {
            "confidence_threshold": 0.3,
            "device": "auto",
            "half_precision": True,
            "warmup_count": 0,
        },
        "onnx": {
            "enable": True,
            "optimization_level": 3,
            "num_threads": 4,
        },
    }


@pytest.fixture
def backend(default_config: dict) -> ViTPoseBackend:
    """기본 백엔드 인스턴스 (ONNX 비활성, PyTorch 폴백)."""
    return ViTPoseBackend(config=default_config)


@pytest.fixture
def dummy_frame() -> np.ndarray:
    """더미 BGR 이미지 (64x48x3)."""
    return np.random.randint(0, 255, (64, 48, 3), dtype=np.uint8)


@pytest.fixture
def dummy_heatmaps() -> np.ndarray:
    """더미 히트맵 (1, 133, 64, 48)."""
    hm = np.random.rand(1, 133, 64, 48).astype(np.float32)
    # 각 키포인트에 명확한 피크 설정
    for k in range(133):
        hm[0, k, 32, 24] = 1.0
    return hm


# ============================================================
# 1. TestInit — 초기화 테스트 (9건)
# ============================================================
class TestInit:
    """ViTPoseBackend 초기화 테스트."""

    def test_init_default_state(self, backend: ViTPoseBackend) -> None:
        """초기 상태 UNINITIALIZED."""
        assert backend._state == BackendState.UNINITIALIZED
        assert not backend._is_loaded

    def test_init_model_type(self, backend: ViTPoseBackend) -> None:
        """모델 유형 VITPOSE."""
        assert backend.model_type == PoseModelType.VITPOSE

    def test_init_input_size(self, backend: ViTPoseBackend) -> None:
        """입력 크기 (256, 192)."""
        assert backend.input_size == (256, 192)

    def test_init_confidence_threshold(self, backend: ViTPoseBackend) -> None:
        """신뢰도 임계값 기본값 0.3."""
        assert backend._confidence_threshold == 0.3

    def test_init_variant(self, backend: ViTPoseBackend) -> None:
        """변형 정보 저장."""
        assert backend._variant == "vitpose-b-wholebody"

    def test_init_custom_weights_path(self, default_config: dict) -> None:
        """커스텀 가중치 경로 우선."""
        b = ViTPoseBackend(config=default_config, weights_path="/custom/model.onnx")
        assert b._weights_path == "/custom/model.onnx"

    def test_init_model_cache_injection(self, default_config: dict) -> None:
        """ModelCache DI 주입."""
        mock_cache = MagicMock()
        b = ViTPoseBackend(config=default_config, model_cache=mock_cache)
        assert b._model_cache is mock_cache

    def test_init_no_config(self) -> None:
        """설정 없이 초기화 (기본값 사용)."""
        b = ViTPoseBackend()
        assert b._input_height == 256
        assert b._input_width == 192
        assert b._confidence_threshold == 0.3

    def test_init_variant_weights_mapping(self) -> None:
        """variant → 가중치 파일명 자동 매핑."""
        config = {
            "variant": "vitpose-h-wholebody",
            "onnx": {"enable": False},
            "inference": {"device": "cpu"},
        }
        b = ViTPoseBackend(config=config)
        assert b._variant == "vitpose-h-wholebody"


# ============================================================
# 2. TestProperties — 속성 테스트 (4건)
# ============================================================
class TestProperties:
    """ViTPoseBackend 속성 테스트."""

    def test_model_type_property(self, backend: ViTPoseBackend) -> None:
        """model_type 반환값."""
        assert backend.model_type == PoseModelType.VITPOSE

    def test_input_size_property(self, backend: ViTPoseBackend) -> None:
        """input_size 반환 타입 tuple."""
        result = backend.input_size
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_use_onnx_property(self, backend: ViTPoseBackend) -> None:
        """use_onnx 불리언 반환."""
        assert isinstance(backend.use_onnx, bool)

    def test_device_property(self, backend: ViTPoseBackend) -> None:
        """device 문자열 반환."""
        assert isinstance(backend.device, str)


# ============================================================
# 3. TestLoadModel — 모델 로드 테스트 (5건)
# ============================================================
class TestLoadModel:
    """ViTPoseBackend 모델 로드 테스트."""

    @patch("pose_estimation.backends.vitpose_backend.torch")
    def test_load_pytorch_model(
        self, mock_torch: MagicMock, default_config: dict, tmp_path
    ) -> None:
        """PyTorch JIT 모델 로드 성공."""
        # 가중치 파일 생성
        weights_file = tmp_path / "vitpose-b-wholebody.pt"
        weights_file.write_bytes(b"fake_model")

        default_config["weights_path"] = str(weights_file)
        default_config["inference"]["warmup_count"] = 0

        mock_model = MagicMock()
        mock_torch.jit.load.return_value = mock_model
        mock_torch.cuda.is_available.return_value = False

        b = ViTPoseBackend(config=default_config)
        b.load_model()

        assert b._is_loaded
        assert b._state == BackendState.READY
        mock_torch.jit.load.assert_called_once()

    def test_load_already_loaded(self, backend: ViTPoseBackend) -> None:
        """이미 로드된 모델 재로드 방지."""
        backend._is_loaded = True
        backend.load_model()  # 아무 작업 없어야 함
        assert backend._is_loaded

    def test_load_missing_weights(self, default_config: dict) -> None:
        """가중치 누락 시 예외."""
        default_config["weights_path"] = "/nonexistent/model.pt"
        b = ViTPoseBackend(config=default_config)
        # PyTorch/ONNX 모두 없으면 로드 실패
        with pytest.raises(ModelLoadException):
            b.load_model()

    def test_load_state_transition_loading(self, default_config: dict) -> None:
        """로드 시작 시 LOADING 상태 전환."""
        default_config["weights_path"] = "/fake/model.pt"
        b = ViTPoseBackend(config=default_config)

        # 로드 실패해도 상태 전환 확인 (ERROR로 전환)
        with pytest.raises(ModelLoadException):
            b.load_model()
        assert b._state == BackendState.ERROR

    @patch("pose_estimation.backends.vitpose_backend.ort")
    def test_load_onnx_model(
        self, mock_ort: MagicMock, onnx_config: dict, tmp_path
    ) -> None:
        """ONNX Runtime 모델 로드 성공."""
        weights_file = tmp_path / "vitpose-b-wholebody.onnx"
        weights_file.write_bytes(b"fake_onnx")

        onnx_config["weights_path"] = str(weights_file)

        mock_session = MagicMock()
        mock_session.get_providers.return_value = ["CPUExecutionProvider"]
        mock_ort.InferenceSession.return_value = mock_session
        mock_ort.SessionOptions.return_value = MagicMock()
        mock_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99
        mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

        # ONNX 활성 상태로 패치
        with patch.object(
            ViTPoseBackend, "_should_use_onnx", return_value=True
        ):
            b = ViTPoseBackend(config=onnx_config)
            b._use_onnx = True
            b.load_model()

        assert b._is_loaded
        assert b._state == BackendState.READY


# ============================================================
# 4. TestUnloadModel — 모델 언로드 테스트 (3건)
# ============================================================
class TestUnloadModel:
    """ViTPoseBackend 모델 언로드 테스트."""

    def test_unload_basic(self, backend: ViTPoseBackend) -> None:
        """기본 언로드."""
        backend._is_loaded = True
        backend._state = BackendState.READY
        backend._onnx_session = MagicMock()
        backend.unload_model()

        assert not backend._is_loaded
        assert backend._state == BackendState.UNLOADED
        assert backend._onnx_session is None

    def test_unload_with_tensorrt(self, backend: ViTPoseBackend) -> None:
        """TensorRT 엔진 포함 언로드."""
        backend._is_loaded = True
        backend._state = BackendState.READY
        mock_trt = MagicMock()
        backend._trt_engine = mock_trt
        backend._use_tensorrt = True

        backend.unload_model()

        mock_trt.release.assert_called_once()
        assert backend._trt_engine is None
        assert not backend._use_tensorrt

    def test_unload_resets_metrics(self, backend: ViTPoseBackend) -> None:
        """언로드 시 메트릭 초기화."""
        backend._is_loaded = True
        backend._state = BackendState.READY
        backend._inference_count = 100
        backend._total_inference_time_ms = 5000.0

        backend.unload_model()

        assert backend._inference_count == 0
        assert backend._total_inference_time_ms == 0.0


# ============================================================
# 5. TestInfer — 추론 테스트 (5건)
# ============================================================
class TestInfer:
    """ViTPoseBackend 추론 테스트."""

    def test_infer_not_loaded(
        self, backend: ViTPoseBackend, dummy_frame: np.ndarray
    ) -> None:
        """미로드 상태 추론 시 예외."""
        with pytest.raises(ModelInferenceException):
            backend.infer(dummy_frame)

    def test_infer_success(
        self, backend: ViTPoseBackend, dummy_frame: np.ndarray,
        dummy_heatmaps: np.ndarray,
    ) -> None:
        """정상 추론 성공."""
        backend._is_loaded = True
        backend._state = BackendState.READY

        with patch.object(backend, "_preprocess") as mock_pre, \
             patch.object(backend, "_run_inference") as mock_run:
            mock_pre.return_value = np.zeros((1, 3, 256, 192), dtype=np.float32)
            mock_run.return_value = dummy_heatmaps

            results = backend.infer(dummy_frame)

        assert len(results) == 1
        assert results[0].shape == (NUM_KEYPOINTS_WHOLEBODY, 3)
        assert backend._state == BackendState.READY

    def test_infer_state_ready_after_success(
        self, backend: ViTPoseBackend, dummy_frame: np.ndarray,
        dummy_heatmaps: np.ndarray,
    ) -> None:
        """추론 후 READY 상태 복귀."""
        backend._is_loaded = True
        backend._state = BackendState.READY

        with patch.object(backend, "_preprocess") as mock_pre, \
             patch.object(backend, "_run_inference") as mock_run:
            mock_pre.return_value = np.zeros((1, 3, 256, 192), dtype=np.float32)
            mock_run.return_value = dummy_heatmaps

            backend.infer(dummy_frame)

        assert backend._state == BackendState.READY

    def test_infer_state_ready_after_exception(
        self, backend: ViTPoseBackend, dummy_frame: np.ndarray,
    ) -> None:
        """추론 예외 시에도 READY 복귀."""
        backend._is_loaded = True
        backend._state = BackendState.READY

        with patch.object(backend, "_preprocess", side_effect=ValueError("test")):
            with pytest.raises(ModelInferenceException):
                backend.infer(dummy_frame)

        assert backend._state == BackendState.READY

    def test_infer_metrics_update(
        self, backend: ViTPoseBackend, dummy_frame: np.ndarray,
        dummy_heatmaps: np.ndarray,
    ) -> None:
        """추론 후 메트릭 업데이트."""
        backend._is_loaded = True
        backend._state = BackendState.READY

        with patch.object(backend, "_preprocess") as mock_pre, \
             patch.object(backend, "_run_inference") as mock_run:
            mock_pre.return_value = np.zeros((1, 3, 256, 192), dtype=np.float32)
            mock_run.return_value = dummy_heatmaps

            backend.infer(dummy_frame)

        assert backend._inference_count == 1
        assert backend._total_inference_time_ms > 0


# ============================================================
# 6. TestPreprocess — 전처리 테스트 (3건)
# ============================================================
class TestPreprocess:
    """전처리 파이프라인 테스트."""

    def test_preprocess_output_shape(self, backend: ViTPoseBackend) -> None:
        """전처리 출력 형상 (1, 3, H, W)."""
        frame = np.random.randint(0, 255, (64, 48, 3), dtype=np.uint8)
        result = backend._preprocess(frame)
        assert result.shape == (1, 3, 256, 192)
        assert result.dtype == np.float32

    def test_preprocess_normalization_range(
        self, backend: ViTPoseBackend
    ) -> None:
        """정규화 후 값 범위 확인."""
        frame = np.ones((64, 48, 3), dtype=np.uint8) * 127
        result = backend._preprocess(frame)
        # ImageNet 정규화 후 범위: 약 -2.5 ~ 2.5
        assert result.min() >= -3.0
        assert result.max() <= 3.0

    def test_numpy_resize_fallback(self) -> None:
        """NumPy 기반 리사이즈 폴백 동작."""
        image = np.random.randint(0, 255, (100, 80, 3), dtype=np.uint8)
        result = ViTPoseBackend._numpy_resize(image, 48, 64)
        assert result.shape == (64, 48, 3)
        assert result.dtype == np.uint8


# ============================================================
# 7. TestDecodeHeatmaps — 히트맵 디코딩 테스트 (4건)
# ============================================================
class TestDecodeHeatmaps:
    """히트맵 디코딩 테스트."""

    def test_decode_output_shape(self, backend: ViTPoseBackend) -> None:
        """디코딩 출력 (133, 3)."""
        heatmaps = np.random.rand(1, 133, 64, 48).astype(np.float32)
        result = backend._decode_heatmaps(heatmaps, 480, 640)
        assert result.shape == (NUM_KEYPOINTS_WHOLEBODY, 3)

    def test_decode_peak_detection(self, backend: ViTPoseBackend) -> None:
        """피크 위치 정확도."""
        heatmaps = np.zeros((133, 64, 48), dtype=np.float32)
        # 첫 번째 키포인트에 명확한 피크
        heatmaps[0, 30, 20] = 1.0
        result = backend._decode_heatmaps(heatmaps, 480, 640)

        # 피크 위치 (서브픽셀 보정 포함)가 스케일링됨
        assert result[0, 2] == 1.0  # confidence

    def test_decode_subpixel_correction(
        self, backend: ViTPoseBackend
    ) -> None:
        """Taylor expansion 서브픽셀 보정."""
        heatmaps = np.zeros((133, 64, 48), dtype=np.float32)
        # 비대칭 피크 (오른쪽이 더 높음)
        heatmaps[0, 30, 20] = 1.0
        heatmaps[0, 30, 21] = 0.8
        heatmaps[0, 30, 19] = 0.2

        result = backend._decode_heatmaps(heatmaps, 480, 640)

        # dx > 0 → sub_px += 0.25 → (20.25 * scale_x)
        scale_x = 640.0 / 48
        expected_x = 20.25 * scale_x
        assert abs(result[0, 0] - expected_x) < 0.01

    def test_decode_4d_input(self, backend: ViTPoseBackend) -> None:
        """4D 입력 (배치 차원 포함) 처리."""
        heatmaps = np.random.rand(1, 133, 64, 48).astype(np.float32)
        result = backend._decode_heatmaps(heatmaps, 480, 640)
        assert result.shape == (NUM_KEYPOINTS_WHOLEBODY, 3)


# ============================================================
# 8. TestTensorRTConfig — TensorRT 설정 테스트 (3건)
# ============================================================
class TestTensorRTConfig:
    """TensorRT 설정 로드 테스트."""

    def test_load_tensorrt_config_from_config(self) -> None:
        """DI config에서 TRT 설정 로드."""
        config = {
            "optimization": {
                "tensorrt": {
                    "enabled": True,
                    "fp16": True,
                },
            },
            "onnx": {"enable": False},
            "inference": {"device": "cpu"},
        }
        b = ViTPoseBackend(config=config)
        result = b._load_tensorrt_config()
        assert result is not None
        assert result["enabled"] is True

    def test_load_tensorrt_config_missing(
        self, backend: ViTPoseBackend
    ) -> None:
        """TRT 설정 없으면 None."""
        result = backend._load_tensorrt_config()
        assert result is None

    def test_load_tensorrt_config_no_tensorrt_key(self) -> None:
        """optimization 있지만 tensorrt 없으면 None."""
        config = {
            "optimization": {"some_other": True},
            "onnx": {"enable": False},
            "inference": {"device": "cpu"},
        }
        b = ViTPoseBackend(config=config)
        result = b._load_tensorrt_config()
        assert result is None


# ============================================================
# 9. TestMetrics — 메트릭 테스트 (3건)
# ============================================================
class TestMetrics:
    """ViTPoseBackend 메트릭 테스트."""

    def test_get_metrics_basic(self, backend: ViTPoseBackend) -> None:
        """기본 메트릭 딕셔너리."""
        metrics = backend.get_metrics()
        assert "engine" in metrics
        assert "device" in metrics
        assert "input_size" in metrics
        assert "keypoint_count" in metrics
        assert metrics["keypoint_count"] == NUM_KEYPOINTS_WHOLEBODY

    def test_get_metrics_fps(self, backend: ViTPoseBackend) -> None:
        """FPS 계산 메트릭."""
        backend._inference_count = 10
        backend._total_inference_time_ms = 1000.0
        metrics = backend.get_metrics()
        assert "average_fps" in metrics
        assert abs(metrics["average_fps"] - 10.0) < 0.01

    def test_get_metrics_engine_name(self, backend: ViTPoseBackend) -> None:
        """엔진 이름 반영."""
        # PyTorch 모드 (ONNX 비활성)
        backend._use_onnx = False
        backend._use_tensorrt = False
        metrics = backend.get_metrics()
        assert metrics["engine"] == "pytorch"

        # ONNX 모드
        backend._use_onnx = True
        metrics = backend.get_metrics()
        assert metrics["engine"] == "onnx"

        # TensorRT 모드
        backend._use_tensorrt = True
        metrics = backend.get_metrics()
        assert metrics["engine"] == "tensorrt"


# ============================================================
# 10. TestRepr — 문자열 표현 테스트 (2건)
# ============================================================
class TestRepr:
    """문자열 표현 테스트."""

    def test_repr_basic(self, backend: ViTPoseBackend) -> None:
        """__repr__ 반환값."""
        r = repr(backend)
        assert "ViTPoseBackend" in r
        assert "loaded=False" in r

    def test_repr_engine_name(self, backend: ViTPoseBackend) -> None:
        """엔진 이름 반영."""
        backend._use_onnx = True
        backend._use_tensorrt = False
        r = repr(backend)
        assert "engine=onnx" in r


# ============================================================
# 11. TestGetKeypointFormat — 키포인트 형식 테스트 (1건)
# ============================================================
class TestGetKeypointFormat:
    """키포인트 형식 반환 테스트."""

    def test_wholebody_format(self, backend: ViTPoseBackend) -> None:
        """wholebody 형식 반환."""
        assert backend.get_keypoint_format() == "wholebody"


# ============================================================
# 12. TestModuleLevel — 모듈 레벨 상수 테스트 (4건)
# ============================================================
class TestModuleLevel:
    """모듈 레벨 상수 테스트."""

    def test_version(self) -> None:
        """버전 1.0.0."""
        assert __version__ == "1.0.0"

    def test_vitpose_available_bool(self) -> None:
        """VITPOSE_AVAILABLE 불리언."""
        assert isinstance(VITPOSE_AVAILABLE, bool)

    def test_imagenet_constants(self) -> None:
        """ImageNet 정규화 상수 값."""
        np.testing.assert_allclose(_IMAGENET_MEAN, [0.485, 0.456, 0.406], atol=1e-6)
        np.testing.assert_allclose(_IMAGENET_STD, [0.229, 0.224, 0.225], atol=1e-6)

    def test_variant_map_entries(self) -> None:
        """변형별 파일명 매핑 4종."""
        assert len(_VARIANT_ONNX_FILE_MAP) == 4
        assert "vitpose-b-wholebody" in _VARIANT_ONNX_FILE_MAP
        assert "vitpose-h-wholebody" in _VARIANT_ONNX_FILE_MAP


# ============================================================
# 13. TestContextManager — 컨텍스트 매니저 테스트 (2건)
# ============================================================
class TestContextManager:
    """컨텍스트 매니저 테스트."""

    def test_context_manager_protocol(
        self, backend: ViTPoseBackend
    ) -> None:
        """__enter__/__exit__ 프로토콜."""
        assert hasattr(backend, "__enter__")
        assert hasattr(backend, "__exit__")

    def test_context_manager_exit_unloads(
        self, backend: ViTPoseBackend
    ) -> None:
        """exit 시 언로드 호출."""
        backend._is_loaded = True
        backend._state = BackendState.READY
        backend.__exit__(None, None, None)
        assert not backend._is_loaded


# ============================================================
# 14. TestDeviceDetection — 디바이스 감지 테스트 (3건)
# ============================================================
class TestDeviceDetection:
    """디바이스 감지 테스트."""

    def test_explicit_device(self) -> None:
        """명시적 디바이스 설정."""
        config = {
            "inference": {"device": "cpu"},
            "onnx": {"enable": False},
        }
        b = ViTPoseBackend(config=config)
        assert b.device == "cpu"

    def test_auto_device_onnx_mode(self) -> None:
        """ONNX 모드에서 auto 디바이스."""
        config = {
            "inference": {"device": "auto"},
            "onnx": {"enable": False},
        }
        # ONNX 비활성 + auto → CPU (CUDA 미설치 환경)
        b = ViTPoseBackend(config=config)
        assert b.device in ("auto", "cpu", "cuda")

    def test_should_use_onnx(self) -> None:
        """_should_use_onnx 로직."""
        config = {
            "onnx": {"enable": False},
            "inference": {"device": "cpu"},
        }
        b = ViTPoseBackend(config=config)
        # onnx.enable=False → False (ONNX_AVAILABLE 무관)
        assert not b._use_onnx or not ONNX_AVAILABLE
