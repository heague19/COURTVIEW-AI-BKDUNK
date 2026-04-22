# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/backends
파일: yolov8_backend.py
설명: YOLOv8-Pose 백엔드 - 균형 잡힌 성능, GPU 가속

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

특성:
    - 균형 잡힌 정확도/속도 (30-60 FPS on GPU)
    - GPU 가속 지원 (CUDA)
    - 17개 키포인트 (COCO 형식)
    - 다중 인물 동시 추론

적합한 사용 사례:
    - 경기 분석 (다중 선수)
    - 중간 속도 동작
    - GPU 환경
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
from pathlib import Path
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

# ============================================================
# 내부 백엔드 모듈
# ============================================================
from pose_estimation.backends.base_backend import (
    PoseBackend,
    PoseModelType,
    BackendState,
)

# ============================================================
# 조건부 Import (Ultralytics YOLO)
# ============================================================
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except (ImportError, OSError):
    YOLO_AVAILABLE = False
    YOLO = None

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


class YOLOv8PoseBackend(PoseBackend):
    """
    YOLO Pose 백엔드 (YOLO11 기반, YOLOv8 호환).

    Ultralytics YOLO11-Pose (또는 YOLOv8-Pose 하위호환) 를 사용한 포즈 추정 백엔드입니다.
    GPU 가속을 통해 빠른 다중 인물 추론이 가능합니다.

    클래스명은 레거시 호환을 위해 YOLOv8PoseBackend 를 유지하지만 YOLO11 도 동일한
    인터페이스로 지원합니다. variant 에 'yolo11l-pose' 등을 지정하면 YOLO11 로 동작.

    설정 구조 (configs/pose/model.yaml):
        pose.model.yolov8_pose:
            variant: "yolo11l-pose"        # 모델 변형 (기본: YOLO11 l)
            weights_path: ""               # 커스텀 가중치 경로
            input_size:
                width: 640
                height: 640
            inference:
                confidence_threshold: 0.5
                iou_threshold: 0.5
                max_detections: 10
                device: "auto"
                half_precision: true
                batch_size: 4

    장점:
        - GPU 가속 (CUDA, TensorRT)
        - 다중 인물 동시 추론
        - 실시간 처리 가능
        - 높은 안정성

    단점:
        - 키포인트 17개 (WholeBody 133개보다 적음)
        - GPU 필요 (최적 성능)
        - 모델 파일 필요

    모델 변형 (YOLO11 권장):
        - yolo11n-pose:  가장 빠름, 정확도 낮음
        - yolo11s-pose:  빠름, 균형
        - yolo11m-pose:  중간
        - yolo11l-pose:  정확 (기본 권장)
        - yolo11x-pose:  가장 정확, 느림
        (YOLOv8 계열도 동일 인터페이스로 지원: yolov8m-pose 등)

    Example:
        >>> config = {"variant": "yolo11l-pose", "inference": {"device": "auto"}}
        >>> backend = YOLOv8PoseBackend(config, "yolov8m-pose.pt")
        >>> backend.load_model()
        >>> keypoints = backend.infer(frame)
        >>> backend.unload_model()
    """

    def __init__(
        self,
        config: dict[str, object] | None = None,
        weights_path: str | None = None,
    ) -> None:
        """
        YOLOv8-Pose 백엔드 초기화.

        Args:
            config: YOLOv8-Pose 설정 딕셔너리 (configs/pose/model.yaml의 yolov8_pose 섹션)
                   None이면 기본값 사용
            weights_path: 모델 가중치 경로 (예: "yolov8m-pose.pt")
                         None이면 config의 weights_path 또는 variant 사용
        """
        super().__init__(config, weights_path)

        # YOLOv8 전용 설정
        self._yolo_model: object = None
        self._use_tensorrt: bool = False
        self._trt_engine_path: str | None = None

        # 디바이스 설정
        self._device: str = self._determine_device()

        # 추론 설정 캐싱 (핫패스 최적화 — infer() 매 호출 시 dict 탐색 방지)
        self._conf_threshold: float = float(
            self._get_config_value("inference.confidence_threshold", 0.5) or 0.5
        )
        self._iou_threshold: float = float(
            self._get_config_value("inference.iou_threshold", 0.5) or 0.5
        )
        self._max_detections: int = int(
            self._get_config_value("inference.max_detections", 10) or 10
        )
        self._use_half: bool = bool(
            self._get_config_value("inference.half_precision", True)
        ) and "cuda" in self._device

        # 가중치 경로 결정 (우선순위: 인자 > config.weights_path > config.variant > 기본값)
        if self._weights_path is None:
            config_weights = self._get_config_value("weights_path", "")
            if config_weights:
                self._weights_path = str(config_weights)
            else:
                variant = str(self._get_config_value("variant", "yolo11l-pose") or "yolo11l-pose")
                self._weights_path = f"{variant}.pt"

    # --------------------------------------------------------
    # 속성
    # --------------------------------------------------------
    @property
    def model_type(self) -> PoseModelType:
        """백엔드 모델 유형."""
        return PoseModelType.YOLOV8_POSE

    @property
    def device(self) -> str:
        """현재 디바이스."""
        return self._device

    # --------------------------------------------------------
    # 내부 유틸리티
    # --------------------------------------------------------
    def _determine_device(self) -> str:
        """
        사용 가능한 최적 디바이스 결정.

        configs/pose/model.yaml 기준:
            yolov8_pose.inference.device: "auto"  # auto, cpu, cuda, cuda:0, mps

        Returns:
            str: "cuda", "cuda:0", "mps", or "cpu"
        """
        config_device = self._get_config_value("inference.device", "auto")

        if config_device != "auto":
            return str(config_device)

        # 자동 감지
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda:0"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "cpu"

    # --------------------------------------------------------
    # 추상 메서드 구현
    # --------------------------------------------------------
    def load_model(self) -> None:
        """
        YOLOv8-Pose 모델 로드.

        Raises:
            ModelLoadException: 모델 로드 실패 시
        """
        if self._is_loaded:
            logger.debug("YOLOv8-Pose 백엔드가 이미 로드됨, 건너뜀")
            return

        if not YOLO_AVAILABLE:
            raise ModelLoadException(
                model_name="YOLOv8-Pose",
                model_path=self._weights_path,
                cause=ImportError("Ultralytics가 설치되지 않았습니다. pip install ultralytics"),
            )

        self._transition_state(BackendState.LOADING)
        logger.info(
            "YOLOv8-Pose 로드 시작 - weights=%s, device=%s",
            self._weights_path,
            self._device,
        )

        try:
            # TensorRT 엔진이 있으면 우선 사용 (.pt → .engine)
            import os
            engine_path = os.path.splitext(self._weights_path)[0] + '.engine'
            # weights/ 접두사도 확인
            if not os.path.isfile(engine_path):
                engine_path = 'weights/' + os.path.splitext(os.path.basename(self._weights_path))[0] + '.engine'
            if os.path.isfile(engine_path):
                logger.info("YOLOv8-Pose TRT 엔진 발견: %s", engine_path)
                self._yolo_model = YOLO(engine_path, task='pose')
                self._use_tensorrt = True
            else:
                # PyTorch 모델 로드 + TRT 가속 시도
                self._yolo_model = YOLO(self._weights_path)
                self._yolo_model.to(self._device)
                self._try_tensorrt_acceleration()

            # 워밍업 (첫 추론 지연 방지)
            if not self._use_tensorrt:
                self._warmup()

            self._is_loaded = True
            self._transition_state(BackendState.READY)

            engine_tag = "tensorrt" if self._use_tensorrt else "pytorch"
            logger.info(
                "YOLOv8-Pose 로드 완료 - engine=%s, device=%s",
                engine_tag,
                self._device,
            )

        except FileNotFoundError as e:
            self._transition_state(BackendState.ERROR)
            logger.error("YOLOv8-Pose 모델 파일 없음: %s", self._weights_path)
            raise ModelLoadException(
                model_name="YOLOv8-Pose",
                model_path=self._weights_path,
                cause=e,
            )

        except Exception as e:
            self._transition_state(BackendState.ERROR)
            logger.error("YOLOv8-Pose 로드 실패: %s", str(e), exc_info=True)
            raise ModelLoadException(
                model_name="YOLOv8-Pose",
                model_path=self._weights_path,
                cause=e,
            )

    def _warmup(self) -> None:
        """모델 워밍업 (첫 추론 지연 방지)."""
        if self._yolo_model is None:
            return

        try:
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            self._yolo_model.predict(
                dummy_frame,
                verbose=False,
                conf=self._conf_threshold,
            )
            logger.debug("YOLOv8-Pose 워밍업 완료")
        except Exception as e:
            logger.warning("YOLOv8-Pose 워밍업 실패 (무시): %s", str(e))

    def unload_model(self) -> None:
        """YOLOv8-Pose 모델 언로드."""
        if not self._is_loaded:
            return

        logger.debug("YOLOv8-Pose 언로드 시작")

        try:
            if self._yolo_model is not None:
                # GPU 메모리 해제
                if "cuda" in self._device:
                    try:
                        import torch
                        del self._yolo_model
                        torch.cuda.empty_cache()
                    except ImportError:
                        del self._yolo_model
                else:
                    del self._yolo_model

                self._yolo_model = None

            # TRT 상태 초기화
            self._use_tensorrt = False
            self._trt_engine_path = None

            self._is_loaded = False
            self._state = BackendState.UNLOADED
            logger.info("YOLOv8-Pose 언로드 완료")

        except Exception as e:
            logger.warning("YOLOv8-Pose 언로드 중 오류: %s", str(e))
            self._yolo_model = None
            self._is_loaded = False
            self._state = BackendState.UNLOADED
            self._use_tensorrt = False
            self._trt_engine_path = None

    def infer(
        self,
        frame: np.ndarray,
        person_boxes: list[BoundingBox] | None = None,
    ) -> list[np.ndarray]:
        """
        YOLOv8-Pose 추론.

        Args:
            frame: BGR 이미지 (H, W, 3)
            person_boxes: 선택적 인물 영역 (미사용, YOLO 자체 감지)

        Returns:
            list[np.ndarray]: 각 인물의 키포인트 배열 리스트
                             각 배열은 (17, 3) 형태 - (x, y, confidence)

        Raises:
            ModelInferenceException: 추론 실패 시
        """
        if not self._is_loaded:
            raise ModelInferenceException(
                model_name="YOLOv8-Pose",
                cause=RuntimeError("모델이 로드되지 않았습니다"),
            )

        self._transition_state(BackendState.INFERRING)
        start_time = time.perf_counter()

        try:
            # person_boxes가 있으면 bbox crop 개별 추론 (Detection 연동)
            if person_boxes:
                all_kps = self._infer_with_boxes(frame, person_boxes)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self._update_inference_metrics(elapsed_ms)
                self._transition_state(BackendState.READY)
                return all_kps

            # 기본: YOLO 자체 감지 + 포즈 추론
            results = self._yolo_model.predict(
                frame,
                verbose=False,
                conf=self._conf_threshold,
                iou=self._iou_threshold,
                max_det=self._max_detections,
                half=self._use_half,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._update_inference_metrics(elapsed_ms)
            self._transition_state(BackendState.READY)

            if not results or len(results) == 0:
                return []

            return self._extract_keypoints(results[0])

        except Exception as e:
            self._transition_state(BackendState.ERROR)
            logger.error("YOLOv8-Pose 추론 실패: %s", str(e), exc_info=True)
            raise ModelInferenceException(
                model_name="YOLOv8-Pose",
                input_shape=frame.shape if frame is not None else None,
                cause=e,
            )

    def _infer_with_boxes(
        self,
        frame: np.ndarray,
        person_boxes: list[BoundingBox],
    ) -> list[np.ndarray]:
        """
        Detection bbox 기반 crop → 개별 포즈 추론 → 원본 좌표 역변환.

        CV-BBox에서 감지한 선수 bbox를 받아 각 bbox를 crop하여
        포즈 추론 후 bbox 중심에 가장 가까운 사람의 포즈를 선택합니다.
        """
        h, w = frame.shape[:2]
        all_keypoints: list[np.ndarray] = []
        pad = 10  # bbox 패딩 최소화 (겹침 방지)

        for box in person_boxes:
            # bbox 중심 (원본 좌표)
            box_cx = box.x + box.width / 2.0
            box_cy = box.y + box.height / 2.0

            # bbox → crop 영역
            x1 = max(0, int(box.x) - pad)
            y1 = max(0, int(box.y) - pad)
            x2 = min(w, int(box.x + box.width) + pad)
            y2 = min(h, int(box.y + box.height) + pad)

            if x2 - x1 < 30 or y2 - y1 < 50:
                continue

            crop = frame[y1:y2, x1:x2]

            try:
                results = self._yolo_model.predict(
                    crop,
                    verbose=False,
                    conf=self._conf_threshold,
                    iou=self._iou_threshold,
                    max_det=5,  # 여러 명 감지 후 가장 가까운 선택
                    half=self._use_half,
                )

                if not results or len(results) == 0:
                    continue

                kps = self._extract_keypoints(results[0])
                if not kps:
                    continue

                # 여러 명 감지된 경우 → bbox 중심에 가장 가까운 사람 선택
                best_kp = None
                best_dist = float("inf")
                for kp_candidate in kps:
                    # 엉덩이 중점을 기준으로 거리 계산 (crop 좌표 → 원본 좌표)
                    hip_x = (kp_candidate[11][0] + kp_candidate[12][0]) / 2.0 + x1
                    hip_y = (kp_candidate[11][1] + kp_candidate[12][1]) / 2.0 + y1
                    dist = (hip_x - box_cx) ** 2 + (hip_y - box_cy) ** 2
                    if dist < best_dist:
                        best_dist = dist
                        best_kp = kp_candidate

                if best_kp is not None:
                    kp = best_kp.copy()
                    kp[:, 0] += x1
                    kp[:, 1] += y1
                    all_keypoints.append(kp)

            except Exception:
                continue

        return all_keypoints

    def get_keypoint_format(self) -> str:
        """키포인트 형식 반환."""
        return "coco"

    # --------------------------------------------------------
    # TensorRT 가속
    # --------------------------------------------------------
    def _try_tensorrt_acceleration(self) -> None:
        """
        Ultralytics 네이티브 TensorRT 가속 시도.

        Ultralytics의 .export(format="engine")을 사용하여 .pt → .engine 변환 후
        TRT 엔진으로 YOLO 모델을 재로드합니다.

        CUDA 디바이스에서만 작동하며, 실패 시 기존 PyTorch 경로로 폴백합니다.
        """
        # CUDA 환경에서만 TRT 사용 가능
        if "cuda" not in self._device:
            return

        # TRT 설정 확인 (config dict에서 직접 조회)
        trt_config = self._load_tensorrt_config()
        if trt_config is None:
            return

        enabled = trt_config.get("enabled", False)
        if not enabled:
            return

        # Ultralytics YOLO 모델이 로드된 상태인지 확인
        if self._yolo_model is None:
            return

        fp16 = bool(trt_config.get("fp16", True))
        workspace_mb = int(trt_config.get("workspace_mb", 1024))
        batch_config = trt_config.get("batch", {})
        max_batch = int(batch_config.get("max", 8)) if isinstance(batch_config, dict) else 8

        try:
            t0 = time.perf_counter()

            # Ultralytics 네이티브 TRT 엔진 export
            # .engine 파일이 이미 존재하면 Ultralytics가 자동으로 캐시 사용
            engine_path = self._yolo_model.export(
                format="engine",
                half=fp16,
                workspace=workspace_mb / 1024.0,  # Ultralytics는 GB 단위
                batch=max_batch,
                verbose=False,
            )

            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # TRT 엔진으로 YOLO 모델 재로드
            self._yolo_model = YOLO(engine_path)
            self._use_tensorrt = True
            self._trt_engine_path = str(engine_path)

            logger.info(
                "YOLOv8-Pose TensorRT 가속 활성화 (%.1fms, engine=%s, fp16=%s)",
                elapsed_ms,
                Path(str(engine_path)).name,
                fp16,
            )

        except Exception as e:
            # TRT 실패 시 기존 PyTorch 경로 유지
            logger.warning(
                "YOLOv8 TensorRT export 실패, PyTorch 폴백 사용: %s", e
            )
            # 원본 모델 복원 (export 실패 시 원본이 손상되지 않았는지 확인)
            if self._yolo_model is None:
                self._yolo_model = YOLO(self._weights_path)
                self._yolo_model.to(self._device)

    def _load_tensorrt_config(self) -> dict[str, object] | None:
        """
        optimization.tensorrt 설정 로드 (config dict 기반).

        config dict의 optimization.tensorrt 섹션에서 TRT 설정을 조회합니다.
        core_foundation 의존 없이 self._config에서 직접 읽습니다.

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
        성능 메트릭 반환 (YOLOv8 확장).

        Returns:
            메트릭 딕셔너리 (기본 + YOLOv8 전용 + TensorRT)
        """
        metrics = super().get_metrics()

        engine_name = "tensorrt" if self._use_tensorrt else "pytorch"
        metrics.update({
            "engine": engine_name,
            "device": self._device,
            "keypoint_count": 17,
            "keypoint_format": "coco",
        })

        # 평균 FPS 계산
        with self._lock:
            if self._inference_count > 0 and self._total_inference_time_ms > 0:
                avg_ms = self._total_inference_time_ms / self._inference_count
                metrics["average_fps"] = 1000.0 / avg_ms if avg_ms > 0 else 0.0

        # TRT 엔진 정보
        if self._use_tensorrt and self._trt_engine_path:
            metrics["tensorrt_engine_path"] = self._trt_engine_path

        return metrics

    # --------------------------------------------------------
    # 내부 헬퍼 메서드
    # --------------------------------------------------------
    def _extract_keypoints(self, result: object) -> list[np.ndarray]:
        """
        YOLO 결과에서 키포인트 배열 추출.

        Args:
            result: YOLO 추론 결과

        Returns:
            list[np.ndarray]: 인물별 키포인트 리스트
        """
        keypoints_list: list[np.ndarray] = []

        # 키포인트가 없는 경우
        if not hasattr(result, "keypoints") or result.keypoints is None:
            return keypoints_list

        # 원본 데이터 추출
        kpts_data = result.keypoints.data  # (N, 17, 3) - x, y, conf

        if kpts_data is None or len(kpts_data) == 0:
            return keypoints_list

        # Tensor → NumPy 변환
        if hasattr(kpts_data, 'cpu'):
            kpts_data = kpts_data.cpu().numpy()

        # 각 인물의 키포인트 추출
        for person_kpts in kpts_data:
            if person_kpts.shape[0] != 17:
                continue

            # float32로 변환
            keypoints_list.append(person_kpts.astype(np.float32))

        return keypoints_list

    def get_bounding_boxes(self, result: object) -> list[BoundingBox]:
        """
        YOLO 결과에서 바운딩 박스 추출.

        Args:
            result: YOLO 추론 결과

        Returns:
            list[BoundingBox]: 인물별 바운딩 박스 리스트
        """
        boxes_list: list[BoundingBox] = []

        if not hasattr(result, "boxes") or result.boxes is None:
            return boxes_list

        # 원본 데이터 추출
        boxes_data = result.boxes.xyxy  # (N, 4) - x1, y1, x2, y2
        confs_data = result.boxes.conf  # (N,)

        if hasattr(boxes_data, 'cpu'):
            boxes_data = boxes_data.cpu().numpy()
            confs_data = confs_data.cpu().numpy()

        for i, box in enumerate(boxes_data):
            x1, y1, x2, y2 = box
            conf = float(confs_data[i]) if i < len(confs_data) else 0.0

            boxes_list.append(BoundingBox(
                x=float(x1),
                y=float(y1),
                width=float(x2 - x1),
                height=float(y2 - y1),
                confidence=conf,
            ))

        return boxes_list


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    "YOLOv8PoseBackend",
    "YOLO_AVAILABLE",
]

__version__ = "1.0.0"
