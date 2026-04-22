# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: pose_estimation/backends/yolov8_backend.py
설명: YOLOv8-Pose 백엔드 단위 테스트

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
from pose_estimation.backends.yolov8_backend import (
    YOLOv8PoseBackend,
    YOLO_AVAILABLE,
    __version__,
)
from shared.exceptions.analysis_exceptions import (
    ModelLoadException,
    ModelInferenceException,
)


# ============================================================
# 테스트 픽스처
# ============================================================
@pytest.fixture
def default_config() -> dict:
    """기본 설정."""
    return {
        "variant": "yolov8m-pose",
        "weights_path": "",
        "inference": {
            "confidence_threshold": 0.5,
            "iou_threshold": 0.5,
            "max_detections": 10,
            "device": "cpu",
            "half_precision": False,
        },
    }


@pytest.fixture
def backend(default_config: dict) -> YOLOv8PoseBackend:
    """기본 백엔드 인스턴스."""
    return YOLOv8PoseBackend(config=default_config)


@pytest.fixture
def mock_yolo_result() -> MagicMock:
    """YOLO 추론 결과 모의 객체."""
    result = MagicMock()

    # 키포인트 모의
    kpts = np.random.rand(2, 17, 3).astype(np.float32)
    kpts[:, :, 2] = np.clip(kpts[:, :, 2], 0.3, 1.0)  # 신뢰도
    result.keypoints = MagicMock()
    result.keypoints.data = kpts

    # 바운딩 박스 모의
    boxes = np.array([[10, 20, 110, 220], [30, 40, 130, 240]], dtype=np.float32)
    confs = np.array([0.9, 0.8], dtype=np.float32)
    result.boxes = MagicMock()
    result.boxes.xyxy = boxes
    result.boxes.conf = confs

    return result


# ============================================================
# A. 초기화 테스트
# ============================================================
class TestInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        """기본 초기화."""
        backend = YOLOv8PoseBackend()
        assert backend.model_type == PoseModelType.YOLOV8_POSE
        assert backend.state == BackendState.UNINITIALIZED
        assert backend.is_loaded is False

    def test_config_injection(self, default_config: dict) -> None:
        """설정 주입."""
        backend = YOLOv8PoseBackend(config=default_config)
        assert backend._conf_threshold == 0.5
        assert backend._iou_threshold == 0.5
        assert backend._max_detections == 10

    def test_custom_confidence(self) -> None:
        """커스텀 신뢰도 임계값."""
        cfg = {"inference": {"confidence_threshold": 0.3, "device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend._conf_threshold == 0.3

    def test_weights_path_from_arg(self) -> None:
        """인자로 가중치 경로 지정."""
        backend = YOLOv8PoseBackend(weights_path="custom.pt")
        assert backend.weights_path == "custom.pt"

    def test_weights_path_from_config(self) -> None:
        """설정에서 가중치 경로."""
        cfg = {"weights_path": "config_model.pt", "inference": {"device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend.weights_path == "config_model.pt"

    def test_weights_path_from_variant(self) -> None:
        """variant에서 가중치 경로 유도."""
        cfg = {"variant": "yolov8s-pose", "weights_path": "", "inference": {"device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend.weights_path == "yolov8s-pose.pt"

    def test_weights_path_default_variant(self) -> None:
        """기본 variant = yolov8l-pose."""
        cfg = {"inference": {"device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend.weights_path == "yolov8l-pose.pt"

    def test_device_from_config(self) -> None:
        """설정에서 디바이스."""
        cfg = {"inference": {"device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend.device == "cpu"

    def test_half_precision_cpu_disabled(self) -> None:
        """CPU에서 half precision 비활성."""
        cfg = {"inference": {"device": "cpu", "half_precision": True}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend._use_half is False  # CPU에서는 항상 False


# ============================================================
# B. 모델 로드 테스트
# ============================================================
class TestLoadModel:
    """모델 로드 테스트."""

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_load_success(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """로드 성공."""
        mock_model = MagicMock()
        mock_yolo_cls.return_value = mock_model

        backend.load_model()

        assert backend.is_loaded is True
        assert backend.state == BackendState.READY
        mock_yolo_cls.assert_called_once()

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_load_duplicate_skip(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """이중 로드 방지."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()
        backend.load_model()  # 두 번째 호출은 건너뜀
        mock_yolo_cls.assert_called_once()

    @patch("pose_estimation.backends.yolov8_backend.YOLO", side_effect=FileNotFoundError("not found"))
    def test_load_file_not_found(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """파일 없음 → ModelLoadException."""
        with pytest.raises(ModelLoadException):
            backend.load_model()
        assert backend.state == BackendState.ERROR

    @patch("pose_estimation.backends.yolov8_backend.YOLO", side_effect=RuntimeError("load fail"))
    def test_load_general_error(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """일반 오류 → ModelLoadException."""
        with pytest.raises(ModelLoadException):
            backend.load_model()
        assert backend.state == BackendState.ERROR

    def test_load_no_ultralytics(self) -> None:
        """Ultralytics 미설치 시 ModelLoadException."""
        backend = YOLOv8PoseBackend(config={"inference": {"device": "cpu"}})
        with patch("pose_estimation.backends.yolov8_backend.YOLO_AVAILABLE", False):
            with pytest.raises(ModelLoadException):
                backend.load_model()


# ============================================================
# C. 모델 언로드 테스트
# ============================================================
class TestUnloadModel:
    """모델 언로드 테스트."""

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_unload_success(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """언로드 성공."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()
        backend.unload_model()

        assert backend.is_loaded is False
        assert backend.state == BackendState.UNLOADED

    def test_unload_not_loaded(self, backend: YOLOv8PoseBackend) -> None:
        """미로드 상태에서 언로드 → 무시."""
        backend.unload_model()
        assert backend.state == BackendState.UNINITIALIZED

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_unload_resets_tensorrt(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """언로드 시 TRT 상태 초기화."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()
        backend._use_tensorrt = True
        backend._trt_engine_path = "/path/to/engine"

        backend.unload_model()

        assert backend._use_tensorrt is False
        assert backend._trt_engine_path is None


# ============================================================
# D. 추론 테스트
# ============================================================
class TestInfer:
    """추론 테스트."""

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_infer_success(
        self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend, mock_yolo_result: MagicMock
    ) -> None:
        """추론 성공."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_yolo_result]
        mock_yolo_cls.return_value = mock_model

        backend.load_model()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)

        assert len(result) == 2  # 2명
        assert result[0].shape == (17, 3)
        assert backend.state == BackendState.READY
        assert backend.inference_count == 1

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_infer_empty_result(
        self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend
    ) -> None:
        """빈 결과."""
        mock_model = MagicMock()
        mock_model.predict.return_value = []
        mock_yolo_cls.return_value = mock_model

        backend.load_model()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)

        assert result == []

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_infer_no_keypoints(
        self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend
    ) -> None:
        """키포인트 없는 결과."""
        mock_result = MagicMock()
        mock_result.keypoints = None
        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]
        mock_yolo_cls.return_value = mock_model

        backend.load_model()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = backend.infer(frame)

        assert result == []

    def test_infer_not_loaded(self, backend: YOLOv8PoseBackend) -> None:
        """미로드 상태에서 추론 → ModelInferenceException."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with pytest.raises(ModelInferenceException):
            backend.infer(frame)

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_infer_uses_cached_config(
        self, mock_yolo_cls: MagicMock
    ) -> None:
        """추론 시 캐싱된 설정 사용."""
        cfg = {
            "inference": {
                "confidence_threshold": 0.7,
                "iou_threshold": 0.3,
                "max_detections": 5,
                "device": "cpu",
                "half_precision": False,
            }
        }
        backend = YOLOv8PoseBackend(config=cfg)
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.keypoints = None
        mock_model.predict.return_value = [mock_result]
        mock_yolo_cls.return_value = mock_model

        backend.load_model()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        backend.infer(frame)

        mock_model.predict.assert_called_with(
            frame,
            verbose=False,
            conf=0.7,
            iou=0.3,
            max_det=5,
            half=False,
        )

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_infer_error_state(
        self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend
    ) -> None:
        """추론 오류 → ERROR 상태."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("inference error")
        mock_yolo_cls.return_value = mock_model

        backend.load_model()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with pytest.raises(ModelInferenceException):
            backend.infer(frame)
        assert backend.state == BackendState.ERROR


# ============================================================
# E. 바운딩 박스 추출 테스트
# ============================================================
class TestGetBoundingBoxes:
    """바운딩 박스 추출 테스트."""

    def test_extract_boxes(self, backend: YOLOv8PoseBackend, mock_yolo_result: MagicMock) -> None:
        """바운딩 박스 추출."""
        boxes = backend.get_bounding_boxes(mock_yolo_result)
        assert len(boxes) == 2
        assert boxes[0].x == 10.0
        assert boxes[0].y == 20.0
        assert boxes[0].width == 100.0  # 110 - 10
        assert boxes[0].height == 200.0  # 220 - 20
        assert boxes[0].confidence == pytest.approx(0.9)

    def test_extract_boxes_no_boxes(self, backend: YOLOv8PoseBackend) -> None:
        """박스 없는 결과."""
        result = MagicMock()
        result.boxes = None
        boxes = backend.get_bounding_boxes(result)
        assert boxes == []


# ============================================================
# F. 메트릭 테스트
# ============================================================
class TestMetrics:
    """메트릭 테스트."""

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_extended_metrics(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """확장 메트릭."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()

        metrics = backend.get_metrics()
        assert metrics["engine"] == "pytorch"
        assert metrics["device"] == "cpu"
        assert metrics["keypoint_count"] == 17
        assert metrics["keypoint_format"] == "coco"

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_metrics_with_fps(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """FPS 포함 메트릭."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()
        backend._update_inference_metrics(20.0)  # 20ms = 50 FPS

        metrics = backend.get_metrics()
        assert "average_fps" in metrics
        assert metrics["average_fps"] == pytest.approx(50.0)

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_metrics_tensorrt(self, mock_yolo_cls: MagicMock, backend: YOLOv8PoseBackend) -> None:
        """TRT 활성화 시 메트릭."""
        mock_yolo_cls.return_value = MagicMock()
        backend.load_model()
        backend._use_tensorrt = True
        backend._trt_engine_path = "/path/to/engine.trt"

        metrics = backend.get_metrics()
        assert metrics["engine"] == "tensorrt"
        assert metrics["tensorrt_engine_path"] == "/path/to/engine.trt"


# ============================================================
# G. TensorRT 설정 로드 테스트
# ============================================================
class TestTensorRTConfig:
    """TensorRT 설정 로드 테스트."""

    def test_load_trt_config_from_dict(self) -> None:
        """config dict에서 TRT 설정 로드."""
        cfg = {
            "inference": {"device": "cpu"},
            "optimization": {
                "tensorrt": {"enabled": True, "fp16": True, "workspace_mb": 2048}
            },
        }
        backend = YOLOv8PoseBackend(config=cfg)
        trt_config = backend._load_tensorrt_config()

        assert trt_config is not None
        assert trt_config["enabled"] is True
        assert trt_config["fp16"] is True
        assert trt_config["workspace_mb"] == 2048

    def test_load_trt_config_missing(self) -> None:
        """TRT 설정 없는 경우 None."""
        cfg = {"inference": {"device": "cpu"}}
        backend = YOLOv8PoseBackend(config=cfg)
        assert backend._load_tensorrt_config() is None

    def test_try_trt_skip_cpu(self, backend: YOLOv8PoseBackend) -> None:
        """CPU 환경에서 TRT 건너뜀."""
        backend._try_tensorrt_acceleration()
        assert backend._use_tensorrt is False


# ============================================================
# H. 키포인트 형식 테스트
# ============================================================
class TestKeypointFormat:
    """키포인트 형식 테스트."""

    def test_format_coco(self, backend: YOLOv8PoseBackend) -> None:
        """COCO 형식."""
        assert backend.get_keypoint_format() == "coco"


# ============================================================
# I. 컨텍스트 매니저 테스트
# ============================================================
class TestContextManager:
    """컨텍스트 매니저 테스트."""

    @patch("pose_estimation.backends.yolov8_backend.YOLO")
    def test_with_statement(self, mock_yolo_cls: MagicMock, default_config: dict) -> None:
        """with 문 사용."""
        mock_yolo_cls.return_value = MagicMock()

        with YOLOv8PoseBackend(config=default_config) as backend:
            assert backend.is_loaded is True


# ============================================================
# J. 모듈 레벨 테스트
# ============================================================
class TestModuleLevel:
    """모듈 레벨 테스트."""

    def test_version(self) -> None:
        """__version__ 확인."""
        assert __version__ == "1.0.0"

    def test_yolo_available(self) -> None:
        """YOLO_AVAILABLE 불리언."""
        assert isinstance(YOLO_AVAILABLE, bool)

    def test_all_exports(self) -> None:
        """__all__ export 확인."""
        from pose_estimation.backends import yolov8_backend
        assert "YOLOv8PoseBackend" in yolov8_backend.__all__
        assert "YOLO_AVAILABLE" in yolov8_backend.__all__
