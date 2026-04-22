# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/backends
파일: vitpose_backend.py
설명: ViTPose WholeBody 133kp 백엔드 - ONNX Runtime/PyTorch, Top-Down 방식

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-17
버전: 1.0.0

v1.0.0:
    - ViTPose WholeBody 133kp 백엔드 초기 구현
    - ONNX Runtime (GPU/CPU) 우선, PyTorch JIT 폴백
    - Top-Down 파이프라인 (단일 인물 크롭 → 133kp 히트맵 추론)
    - 히트맵 디코딩 (argmax + Taylor expansion 서브픽셀 보정)
    - ImageNet 정규화 전처리

특성:
    - 133개 키포인트 (COCO-WholeBody: Body17+Foot6+Face68+Hand42)
    - ONNX Runtime GPU 가속 (CUDAExecutionProvider)
    - FP16 반정밀도 지원 (GPU 메모리 절약)
    - Top-Down 단일 인물 추론 (precision_pose_runner 연동)
    - 워밍업 추론으로 초기화 지연 제거

적합한 사용 사례:
    - 정밀 모션 분석 (슈팅 폼, 손가락 릴리즈)
    - precision_pose_runner 백엔드 (DI 주입)
    - 훈련 동작 분석 (단일 인물)

설정 구조 (configs/pose/model.yaml):
    pose.model.vitpose:
        variant: "vitpose-b-wholebody"
        weights_path: ""
        input_size:
            height: 256
            width: 192
        inference:
            confidence_threshold: 0.3
            device: "auto"
            half_precision: true
            batch_size: 1
        onnx:
            enable: true
            optimization_level: 3
            num_threads: 4
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
from pathlib import Path
from typing import TYPE_CHECKING
import logging
import time

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
from shared.interfaces.detector_interface import BoundingBox
from shared.constants.pose_constants import NUM_KEYPOINTS_WHOLEBODY

# ============================================================
# 내부 백엔드 모듈
# ============================================================
from pose_estimation.backends.base_backend import (
    PoseBackend,
    PoseModelType,
    BackendState,
)

# ============================================================
# 조건부 Import (ONNX Runtime / PyTorch)
# ============================================================
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ort = None
    ONNX_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    torch = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False

# OpenCV (전처리용, 선택적)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

# ViTPose 사용 가능 여부 (ONNX 또는 PyTorch 중 하나 필요)
VITPOSE_AVAILABLE: bool = ONNX_AVAILABLE or TORCH_AVAILABLE

# ============================================================
# TYPE_CHECKING 가드 (DI 주입 대상)
# ============================================================
if TYPE_CHECKING:
    from infrastructure.cache.model_cache import ModelCache

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수
# ============================================================
# ImageNet 정규화 상수
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# ViTPose 변형별 가중치 파일명 매핑
# vitpose-h는 ONNX external data 형식 (model.onnx + data.bin 분리)
_VARIANT_ONNX_FILE_MAP: dict[str, str] = {
    "vitpose-s-wholebody": "vitpose-s-wholebody.onnx",
    "vitpose-b-wholebody": "vitpose-b-wholebody.onnx",
    "vitpose-l-wholebody": "vitpose-l-wholebody.onnx",
    "vitpose-h-wholebody": "vitpose_h_wholebody_model.onnx",
}

# ONNX external data가 필요한 변형 (data.bin과 함께 로드)
_EXTERNAL_DATA_VARIANTS: dict[str, str] = {
    "vitpose-h-wholebody": "vitpose_h_wholebody_data.bin",
}


class ViTPoseBackend(PoseBackend):
    """
    ViTPose WholeBody 133kp 백엔드.

    Top-Down 방식: 단일 인물 크롭 이미지 → 133kp 히트맵 추론 → 좌표 디코딩.
    precision_pose_runner에서 DI 주입되어 사용됩니다.

    추론 엔진 우선순위:
        1. ONNX Runtime (GPU/CPU) — 가장 빠름, 프로덕션 권장
        2. PyTorch JIT (GPU/CPU) — ONNX 미사용 시 폴백

    히트맵 디코딩:
        - argmax로 히트맵 피크 위치 검출
        - Taylor expansion 서브픽셀 보정 (±0.25 정밀도)
        - 히트맵 좌표 → 원본 이미지 좌표 스케일링

    Example:
        >>> config = {"variant": "vitpose-b-wholebody", "weights_path": "model.onnx"}
        >>> backend = ViTPoseBackend(config)
        >>> backend.load_model()
        >>> keypoints = backend.infer(cropped_person)
        >>> # keypoints: [np.ndarray(133, 3)]  — (x, y, confidence)
        >>> backend.unload_model()
    """

    def __init__(
        self,
        config: dict[str, object] | None = None,
        weights_path: str | None = None,
        model_cache: ModelCache | None = None,
    ) -> None:
        """
        ViTPose 백엔드 초기화.

        Args:
            config: ViTPose 설정 딕셔너리 (configs/pose/model.yaml의 vitpose 섹션)
                   None이면 기본값 사용
            weights_path: 모델 가중치 경로 (ONNX 또는 PyTorch JIT)
                         None이면 config의 weights_path 또는 variant 사용
            model_cache: GPU VRAM 모델 캐시 (DI 주입, 선택적)
                        제공 시 모델 로드/언로드를 ModelCache에 위임하여
                        다중 백엔드 간 GPU 메모리를 공유 관리합니다.
        """
        super().__init__(config, weights_path)
        self._model_cache = model_cache

        # 추론 세션/모델
        self._onnx_session: object | None = None
        self._torch_model: object | None = None
        self._trt_engine: object | None = None  # TensorRTEngine (조건부)
        self._use_onnx: bool = self._should_use_onnx()
        self._use_tensorrt: bool = False

        # 디바이스 설정
        self._device: str = self._determine_device()

        # 입력 크기 (height, width) — Top-Down 크롭 크기
        self._input_height: int = self._get_config_value("input_size.height", 256)
        self._input_width: int = self._get_config_value("input_size.width", 192)

        # 신뢰도 임계값
        self._confidence_threshold: float = self._get_config_value(
            "inference.confidence_threshold", 0.3
        )

        # FP16 설정
        self._half_precision: bool = self._get_config_value(
            "inference.half_precision", True
        )

        # 변형 정보 저장 (외부 데이터 판별용)
        self._variant: str = self._get_config_value(
            "variant", "vitpose-b-wholebody"
        )

        # 가중치 경로 결정 (우선순위: 인자 > config.weights_path > variant 기반)
        if self._weights_path is None:
            config_weights = self._get_config_value("weights_path", "")
            if config_weights:
                self._weights_path = config_weights
            else:
                if self._use_onnx and self._variant in _VARIANT_ONNX_FILE_MAP:
                    self._weights_path = _VARIANT_ONNX_FILE_MAP[self._variant]
                else:
                    ext = ".onnx" if self._use_onnx else ".pt"
                    self._weights_path = f"{self._variant}{ext}"

    # --------------------------------------------------------
    # 속성
    # --------------------------------------------------------
    @property
    def model_type(self) -> PoseModelType:
        """백엔드 모델 유형."""
        return PoseModelType.VITPOSE

    @property
    def input_size(self) -> tuple[int, int]:
        """입력 크기 (height, width)."""
        return (self._input_height, self._input_width)

    @property
    def use_onnx(self) -> bool:
        """ONNX Runtime 사용 여부."""
        return self._use_onnx

    @property
    def device(self) -> str:
        """추론 디바이스."""
        return self._device

    # --------------------------------------------------------
    # 추상 메서드 구현: load_model
    # --------------------------------------------------------
    def load_model(self) -> None:
        """
        ViTPose 모델 로드.

        ONNX Runtime 또는 PyTorch JIT 모델을 로드합니다.
        GPU 사용 가능 시 CUDAExecutionProvider를 우선 사용합니다.

        Raises:
            ModelLoadException: 모델 로드 실패 시
        """
        if self._is_loaded:
            logger.debug("ViTPose 모델이 이미 로드되어 있습니다")
            return

        self._transition_state(BackendState.LOADING)
        t0 = time.perf_counter()

        try:
            weights_path = self._resolve_weights_path()

            if self._use_onnx:
                self._load_onnx_model(weights_path)
            else:
                self._load_torch_model(weights_path)

            # TensorRT 가속 시도 (ONNX 우선 → TRT 변환)
            self._try_tensorrt_acceleration(weights_path)

            self._is_loaded = True
            self._transition_state(BackendState.READY)

            engine_name = "tensorrt" if self._use_tensorrt else (
                "onnx" if self._use_onnx else "pytorch"
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            logger.info(
                "ViTPose 모델 로드 완료 (%.1fms, engine=%s, device=%s)",
                elapsed,
                engine_name,
                self._device,
            )

            # 워밍업 추론 (초기화 지연 제거, TRT는 자체 워밍업)
            if not self._use_tensorrt:
                self._warmup()

        except Exception as e:
            self._transition_state(BackendState.ERROR)
            raise ModelLoadException(
                f"ViTPose 모델 로드 실패: {e}"
            ) from e

    # --------------------------------------------------------
    # 추상 메서드 구현: unload_model
    # --------------------------------------------------------
    def unload_model(self) -> None:
        """
        ViTPose 모델 언로드.

        메모리에서 모델을 해제하고 GPU 메모리를 정리합니다.
        """
        # TensorRT 엔진 해제
        if self._trt_engine is not None:
            self._trt_engine.release()
            self._trt_engine = None
            self._use_tensorrt = False

        if self._onnx_session is not None:
            self._onnx_session = None

        if self._torch_model is not None:
            self._torch_model = None

            # PyTorch GPU 메모리 해제
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()

        self._model = None
        self._is_loaded = False
        self._state = BackendState.UNLOADED
        self.reset_metrics()
        self._model_char_cache.clear()

        logger.info("ViTPose 모델 언로드 완료")

    # --------------------------------------------------------
    # 추상 메서드 구현: infer
    # --------------------------------------------------------
    def infer(
        self,
        frame: np.ndarray,
        person_boxes: list[BoundingBox] | None = None,
    ) -> list[np.ndarray]:
        """
        ViTPose 133kp 추론.

        Top-Down 방식: 입력 프레임(단일 인물 크롭)에서 133개 키포인트를 추출합니다.
        precision_pose_runner가 ROI 크롭을 전달하므로, person_boxes는 사용하지 않습니다.

        Args:
            frame: BGR 이미지 (H, W, 3) — 단일 인물 크롭
            person_boxes: 사전 탐지된 인물 영역 (Top-Down에서는 미사용)

        Returns:
            list[np.ndarray]: [(133, 3)] — (x, y, confidence) 원본 좌표계

        Raises:
            ModelInferenceException: 추론 실패 시
        """
        if not self._is_loaded:
            raise ModelInferenceException("ViTPose 모델이 로드되지 않았습니다")

        self._transition_state(BackendState.INFERRING)
        t0 = time.perf_counter()

        try:
            orig_h, orig_w = frame.shape[:2]

            # 전처리: BGR → RGB → Resize → Normalize → NCHW
            input_tensor = self._preprocess(frame)

            # 추론 실행
            heatmaps = self._run_inference(input_tensor)

            # 히트맵 디코딩: (1, 133, hm_h, hm_w) → (133, 3)
            keypoints = self._decode_heatmaps(heatmaps, orig_h, orig_w)

            # 메트릭 업데이트
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._update_inference_metrics(elapsed_ms)
            self._transition_state(BackendState.READY)

            return [keypoints]  # 단일 인물 (Top-Down)

        except ModelInferenceException:
            self._transition_state(BackendState.READY)
            raise
        except Exception as e:
            self._transition_state(BackendState.READY)
            raise ModelInferenceException(
                f"ViTPose 추론 실패: {e}"
            ) from e

    # --------------------------------------------------------
    # 추상 메서드 구현: get_keypoint_format
    # --------------------------------------------------------
    def get_keypoint_format(self) -> str:
        """
        키포인트 형식 반환.

        Returns:
            str: "wholebody" (COCO-WholeBody 133kp)
        """
        return "wholebody"

    # --------------------------------------------------------
    # 내부 메서드: 모델 로드
    # --------------------------------------------------------
    def _load_onnx_model(self, weights_path: str) -> None:
        """
        ONNX Runtime InferenceSession 생성.

        vitpose-h 등 ONNX external data 형식의 모델은
        data.bin 파일이 같은 디렉토리에 있어야 합니다.
        """
        providers = self._get_onnx_providers()
        sess_options = self._get_onnx_session_options()

        # ONNX external data 변형: data.bin이 같은 디렉토리에 있는지 검증
        if self._variant in _EXTERNAL_DATA_VARIANTS:
            data_filename = _EXTERNAL_DATA_VARIANTS[self._variant]
            weights_dir = Path(weights_path).parent
            data_path = weights_dir / data_filename
            if not data_path.exists():
                raise ModelLoadException(
                    f"ViTPose-H 외부 데이터 파일 누락: {data_path} "
                    f"(모델 파일과 같은 디렉토리에 {data_filename} 필요)"
                )
            logger.info(
                "ONNX external data 감지: %s (%s)",
                data_filename,
                f"{data_path.stat().st_size / (1024**3):.1f}GB",
            )

        self._onnx_session = ort.InferenceSession(
            weights_path,
            sess_options=sess_options,
            providers=providers,
        )

        # 실제 사용된 프로바이더 로깅
        active_providers = self._onnx_session.get_providers()
        logger.info("ONNX 프로바이더: %s", active_providers)

    def _load_torch_model(self, weights_path: str) -> None:
        """PyTorch JIT 모델 로드."""
        map_location = self._device if self._device != "auto" else "cpu"
        self._torch_model = torch.jit.load(
            weights_path, map_location=map_location
        )
        self._torch_model.eval()

        # GPU로 이동
        if self._device.startswith("cuda") and torch.cuda.is_available():
            self._torch_model = self._torch_model.to(self._device)

        # FP16 변환 (GPU에서만)
        if self._half_precision and self._device.startswith("cuda"):
            self._torch_model = self._torch_model.half()

    # --------------------------------------------------------
    # 내부 메서드: 전처리
    # --------------------------------------------------------
    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        BGR 크롭 이미지 → 모델 입력 텐서.

        파이프라인:
            1. BGR → RGB
            2. 리사이즈 (bilinear, input_size)
            3. [0,255] → [0,1] → ImageNet 정규화
            4. HWC → CHW → NCHW (batch=1)

        Args:
            frame: BGR 이미지 (H, W, 3)

        Returns:
            np.ndarray: (1, 3, input_h, input_w) float32
        """
        h, w = self._input_height, self._input_width

        # 1. BGR → RGB
        rgb = frame[:, :, ::-1].copy()

        # 2. 리사이즈
        if CV2_AVAILABLE:
            resized = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            resized = self._numpy_resize(rgb, w, h)

        # 3. [0,255] → [0,1] → ImageNet 정규화
        normalized = (resized.astype(np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD

        # 4. HWC → CHW → NCHW
        tensor = normalized.transpose(2, 0, 1)[np.newaxis, ...]

        return tensor.astype(np.float32)

    @staticmethod
    def _numpy_resize(image: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """
        NumPy 기반 bilinear 리사이즈 (cv2 미설치 폴백).

        Args:
            image: 소스 이미지 (H, W, C)
            target_w: 목표 너비
            target_h: 목표 높이

        Returns:
            리사이즈된 이미지
        """
        src_h, src_w = image.shape[:2]

        # 그리드 좌표 생성
        y_coords = np.linspace(0, src_h - 1, target_h)
        x_coords = np.linspace(0, src_w - 1, target_w)

        y_grid, x_grid = np.meshgrid(y_coords, x_coords, indexing="ij")

        # 정수 인덱스 + 소수 보간 가중치
        y0 = np.floor(y_grid).astype(np.int32)
        x0 = np.floor(x_grid).astype(np.int32)
        y1 = np.minimum(y0 + 1, src_h - 1)
        x1 = np.minimum(x0 + 1, src_w - 1)

        fy = (y_grid - y0).astype(np.float32)
        fx = (x_grid - x0).astype(np.float32)

        # Bilinear 보간
        result = (
            image[y0, x0] * ((1 - fy) * (1 - fx))[..., np.newaxis]
            + image[y0, x1] * ((1 - fy) * fx)[..., np.newaxis]
            + image[y1, x0] * (fy * (1 - fx))[..., np.newaxis]
            + image[y1, x1] * (fy * fx)[..., np.newaxis]
        )

        return result.astype(np.uint8)

    # --------------------------------------------------------
    # 내부 메서드: 추론 실행
    # --------------------------------------------------------
    def _run_inference(self, input_tensor: np.ndarray) -> np.ndarray:
        """
        추론 실행 (TensorRT > ONNX > PyTorch 우선순위).

        Args:
            input_tensor: (1, 3, H, W) float32

        Returns:
            히트맵 np.ndarray (1, 133, hm_h, hm_w)
        """
        # TensorRT 우선 (활성화 시)
        if self._use_tensorrt and self._trt_engine is not None:
            return self._trt_engine.run_single(input_tensor)
        elif self._use_onnx and self._onnx_session is not None:
            input_name = self._onnx_session.get_inputs()[0].name
            outputs = self._onnx_session.run(None, {input_name: input_tensor})
            return outputs[0]
        elif self._torch_model is not None:
            with torch.no_grad():
                tensor = torch.from_numpy(input_tensor).to(self._device)
                if self._half_precision and self._device.startswith("cuda"):
                    tensor = tensor.half()
                heatmaps = self._torch_model(tensor)
                return heatmaps.float().cpu().numpy()
        else:
            raise ModelInferenceException(
                "추론 엔진이 초기화되지 않았습니다 (TRT/ONNX/PyTorch 모두 없음)"
            )

    # --------------------------------------------------------
    # 내부 메서드: 히트맵 디코딩
    # --------------------------------------------------------
    def _decode_heatmaps(
        self,
        heatmaps: np.ndarray,
        orig_h: int,
        orig_w: int,
    ) -> np.ndarray:
        """
        히트맵 → 키포인트 좌표 디코딩.

        방법:
            1. argmax로 히트맵 피크 위치 검출
            2. Taylor expansion 서브픽셀 보정 (±0.25 정밀도)
            3. 히트맵 좌표 → 원본 이미지 좌표 스케일링

        Args:
            heatmaps: (1, N, hm_h, hm_w) 또는 (N, hm_h, hm_w)
            orig_h: 원본 이미지 높이
            orig_w: 원본 이미지 너비

        Returns:
            np.ndarray: (num_kps, 3) — (x, y, confidence)
        """
        # 배치 차원 제거
        if heatmaps.ndim == 4:
            heatmaps = heatmaps[0]  # (N, hm_h, hm_w)

        num_kps, hm_h, hm_w = heatmaps.shape

        # 출력 키포인트 개수 = NUM_KEYPOINTS_WHOLEBODY (133)
        output_count = min(num_kps, NUM_KEYPOINTS_WHOLEBODY)
        keypoints = np.zeros((NUM_KEYPOINTS_WHOLEBODY, 3), dtype=np.float32)

        # 스케일링 팩터
        scale_x = orig_w / hm_w
        scale_y = orig_h / hm_h

        for k in range(output_count):
            hm = heatmaps[k]

            # 피크 찾기 (argmax)
            flat_idx = int(np.argmax(hm))
            py, px = divmod(flat_idx, hm_w)
            confidence = float(hm[py, px])

            # 서브픽셀 보정 (Taylor expansion)
            # 피크가 경계가 아닌 경우에만 적용
            sub_px = float(px)
            sub_py = float(py)

            if 0 < px < hm_w - 1 and 0 < py < hm_h - 1:
                dx = 0.5 * (float(hm[py, px + 1]) - float(hm[py, px - 1]))
                dy = 0.5 * (float(hm[py + 1, px]) - float(hm[py - 1, px]))
                sub_px += np.sign(dx) * 0.25
                sub_py += np.sign(dy) * 0.25

            # 히트맵 좌표 → 원본 좌표
            keypoints[k, 0] = sub_px * scale_x
            keypoints[k, 1] = sub_py * scale_y
            keypoints[k, 2] = confidence

        return keypoints

    # --------------------------------------------------------
    # 내부 메서드: 디바이스/설정
    # --------------------------------------------------------
    def _determine_device(self) -> str:
        """
        추론 디바이스 결정.

        우선순위: config.inference.device → auto 감지 (CUDA > CPU)

        Returns:
            디바이스 문자열 ("cuda", "cuda:0", "cpu")
        """
        config_device = self._get_config_value("inference.device", "auto")

        if config_device != "auto":
            return config_device

        # ONNX 모드: ONNX Runtime이 프로바이더로 디바이스 관리
        if self._use_onnx:
            return "auto"

        # PyTorch 모드: CUDA 사용 가능 여부 확인
        if TORCH_AVAILABLE and torch.cuda.is_available():
            return "cuda"

        return "cpu"

    def _should_use_onnx(self) -> bool:
        """ONNX Runtime 사용 여부 결정."""
        onnx_enabled = self._get_config_value("onnx.enable", True)
        return ONNX_AVAILABLE and onnx_enabled

    def _get_onnx_providers(self) -> list[str]:
        """
        ONNX Runtime Execution Provider 목록 반환.

        GPU 가용성에 따라 CUDAExecutionProvider를 우선 사용합니다.

        Returns:
            프로바이더 문자열 리스트
        """
        providers = []

        # CUDA 프로바이더 확인
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")

        # CPU 폴백
        providers.append("CPUExecutionProvider")

        return providers

    def _get_onnx_session_options(self) -> object:
        """
        ONNX Runtime SessionOptions 생성.

        Returns:
            ort.SessionOptions
        """
        options = ort.SessionOptions()

        # 최적화 레벨 (0~3)
        opt_level = self._get_config_value("onnx.optimization_level", 3)
        opt_map = {
            0: ort.GraphOptimizationLevel.ORT_DISABLE_ALL,
            1: ort.GraphOptimizationLevel.ORT_ENABLE_BASIC,
            2: ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED,
            3: ort.GraphOptimizationLevel.ORT_ENABLE_ALL,
        }
        options.graph_optimization_level = opt_map.get(
            opt_level, ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        # 스레드 수
        num_threads = self._get_config_value("onnx.num_threads", 4)
        options.intra_op_num_threads = num_threads

        return options

    def _resolve_weights_path(self) -> str:
        """
        가중치 파일 경로 확인.

        절대 경로 또는 프로젝트 루트 기준 상대 경로를 확인합니다.

        Returns:
            확인된 가중치 파일 경로

        Raises:
            ModelLoadException: 가중치 파일 없음
        """
        if self._weights_path is None:
            raise ModelLoadException("가중치 경로가 지정되지 않았습니다")

        path = Path(self._weights_path)

        # 절대 경로 확인
        if path.is_absolute() and path.exists():
            return str(path)

        # 프로젝트 루트 기준 상대 경로
        project_root = Path(__file__).resolve().parents[2]
        candidates = [
            project_root / self._weights_path,
            project_root / "pose_estimation" / "weights" / path.name,
            project_root / "weights" / path.name,
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        # 가중치 파일 없음 — 경고 후 경로 반환 (런타임에서 다운로드 가능)
        logger.warning(
            "ViTPose 가중치 파일을 찾을 수 없습니다: %s "
            "(모델 로드 시 예외가 발생할 수 있습니다)",
            self._weights_path,
        )
        return self._weights_path

    def _warmup(self) -> None:
        """
        워밍업 추론.

        더미 입력으로 첫 추론을 실행하여 초기화 지연을 제거합니다.
        GPU JIT 컴파일, 메모리 할당 등이 워밍업에서 완료됩니다.
        """
        warmup_count = self._get_config_value("inference.warmup_count", 1)

        try:
            dummy_frame = np.zeros(
                (self._input_height, self._input_width, 3),
                dtype=np.uint8,
            )
            for _ in range(warmup_count):
                _ = self.infer(dummy_frame)

            # 워밍업 메트릭 리셋 (실제 추론 메트릭에 포함시키지 않음)
            self.reset_metrics()
            logger.debug("ViTPose 워밍업 완료 (%d회)", warmup_count)

        except Exception as e:
            # 워밍업 실패는 치명적이지 않음
            logger.warning("ViTPose 워밍업 실패 (무시): %s", e)
            self.reset_metrics()

    # --------------------------------------------------------
    # TensorRT 가속
    # --------------------------------------------------------
    def _try_tensorrt_acceleration(self, weights_path: str) -> None:
        """
        TensorRT 가속 시도.

        ONNX 모델을 TensorRT 엔진으로 변환하여 추론 속도를 향상시킵니다.
        ONNX 모드에서만 작동하며, 실패 시 기존 ONNX/PyTorch 경로로 폴백합니다.

        Args:
            weights_path: ONNX 모델 가중치 파일 경로
        """
        # ONNX 모드가 아니면 TRT 불가 (PyTorch → ONNX → TRT 변환 경로 없음)
        if not self._use_onnx or self._onnx_session is None:
            return

        # TensorRT 가용성 확인 (조건부 임포트)
        try:
            from pose_estimation.backends.tensorrt_engine import (
                TENSORRT_AVAILABLE as _trt_available,
                create_tensorrt_engine,
            )
        except ImportError:
            return

        if not _trt_available:
            return

        # optimization.tensorrt 설정 로드
        trt_yaml_config = self._load_tensorrt_config()
        if trt_yaml_config is None:
            return

        # 팩토리를 통한 엔진 생성 (enabled=false이면 None 반환)
        trt_engine = create_tensorrt_engine(trt_yaml_config)
        if trt_engine is None:
            return

        # 입력 형상 정의 (ViTPose Top-Down: 단일 인물 크롭)
        # ONNX 모델의 입력 텐서 이름은 "input_0" (ONNX export 기본 명명)
        input_shapes = {
            "input_0": (1, 3, self._input_height, self._input_width),
        }

        try:
            engine_path = trt_engine.build_or_load(
                onnx_path=weights_path,
                input_shapes=input_shapes,
            )

            self._trt_engine = trt_engine
            self._use_tensorrt = True

            logger.info(
                "ViTPose TensorRT 가속 활성화 (engine=%s)",
                Path(engine_path).name,
            )

        except Exception as e:
            # TRT 실패 시 기존 ONNX 경로 유지 (치명적이지 않음)
            logger.warning(
                "TensorRT 가속 실패, ONNX Runtime 폴백 사용: %s", e
            )
            self._use_tensorrt = False
            self._trt_engine = None
            if trt_engine is not None:
                try:
                    trt_engine.release()
                except Exception:
                    pass
            # CUDA 상태 복구 (TRT 실패로 인한 GPU 오염 방지)
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    logger.info("TRT 실패 후 CUDA 상태 복구 완료")
            except Exception:
                pass

    def _load_tensorrt_config(self) -> dict[str, object] | None:
        """
        optimization.tensorrt 설정 로드.

        DI 주입된 config 딕셔너리에서 optimization.tensorrt 섹션을 가져옵니다.
        설정이 없으면 None을 반환합니다.

        Returns:
            tensorrt 설정 딕셔너리 또는 None
        """
        opt_config = self._get_config_value("optimization")
        if isinstance(opt_config, dict):
            trt_config = opt_config.get("tensorrt")
            if isinstance(trt_config, dict):
                return trt_config
        return None

    # --------------------------------------------------------
    # 확장 메서드
    # --------------------------------------------------------
    def get_metrics(self) -> dict[str, object]:
        """
        성능 메트릭 반환 (ViTPose 확장).

        Returns:
            메트릭 딕셔너리 (기본 + ViTPose 전용 + TensorRT)
        """
        metrics = super().get_metrics()

        # 추론 엔진 이름
        if self._use_tensorrt:
            engine_name = "tensorrt"
        elif self._use_onnx:
            engine_name = "onnx"
        else:
            engine_name = "pytorch"

        metrics.update({
            "engine": engine_name,
            "device": self._device,
            "input_size": f"{self._input_height}x{self._input_width}",
            "half_precision": self._half_precision,
            "keypoint_count": NUM_KEYPOINTS_WHOLEBODY,
            "keypoint_format": "wholebody",
        })

        # 평균 FPS 계산 (스레드 안전)
        with self._lock:
            if self._inference_count > 0 and self._total_inference_time_ms > 0:
                avg_ms = self._total_inference_time_ms / self._inference_count
                metrics["average_fps"] = 1000.0 / avg_ms if avg_ms > 0 else 0.0

        # TensorRT 메트릭 추가
        if self._use_tensorrt and self._trt_engine is not None:
            trt_metrics = self._trt_engine.metrics
            metrics["tensorrt"] = {
                "total_inferences": trt_metrics.total_inferences,
                "total_inference_time_ms": trt_metrics.total_inference_time_ms,
                "min_inference_time_ms": trt_metrics.min_inference_time_ms,
                "max_inference_time_ms": trt_metrics.max_inference_time_ms,
                "engine_build_time_ms": trt_metrics.engine_build_time_ms,
                "engine_load_time_ms": trt_metrics.engine_load_time_ms,
            }

        return metrics

    def __repr__(self) -> str:
        """문자열 표현."""
        if self._use_tensorrt:
            engine_name = "tensorrt"
        elif self._use_onnx:
            engine_name = "onnx"
        else:
            engine_name = "pytorch"

        return (
            f"ViTPoseBackend("
            f"engine={engine_name}, "
            f"device={self._device}, "
            f"input={self._input_height}x{self._input_width}, "
            f"loaded={self._is_loaded}, "
            f"state={self._state.value}, "
            f"inferences={self._inference_count})"
        )


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    "ViTPoseBackend",
    "VITPOSE_AVAILABLE",
    "ONNX_AVAILABLE",
    "TORCH_AVAILABLE",
    "CV2_AVAILABLE",
]

__version__ = "1.0.0"
