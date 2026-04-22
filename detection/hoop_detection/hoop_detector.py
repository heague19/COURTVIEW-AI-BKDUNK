# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection
파일: hoop_detector.py
설명: YOLO Primary + Hough Circle 보조 하이브리드 골대 감지기
      - COURTVIEW_hoop.pt 자체 학습 모델 기반 추론 (2-class: rim/backboard)
      - Hough Circle Transform 보조 림 원형 검증
      - HSV 색상 필터 (오렌지 림) 후처리 검증
      - 백보드 종횡비 검증
      - 골대 위치 캐싱 (정적 객체 최적화)
      - 멀티뷰 융합 (infrastructure/multi_camera 삼각측량 위임)
      - TensorRT FP16 가속 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0

의존성:
    - shared/constants/hoop_constants.py: 골대 검출 파라미터, 색상 HSV 범위
    - shared/dto/detection_dto.py: DetectedObject, DetectionResult, ObjectType
    - shared/dto/geometry_dto.py: Point2D, BoundingBox DTO
    - shared/interfaces/detector_interface.py: IHoopDetector 인터페이스
    - infrastructure/multi_camera/coordinate_transformer.py: MultiViewTriangulator
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.hoop_constants import (
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_RIM,
    HOOP_DETECTION_CONFIDENCE_THRESHOLD,
    HOOP_DETECTION_FREQUENCY_FRAMES,
    HOOP_DETECTION_INPUT_SIZE,
    HOOP_DETECTION_IOU_THRESHOLD,
    HOOP_DETECTION_MAX_DETECTIONS,
    HOOP_HOUGH_DP,
    HOOP_HOUGH_MAX_RADIUS,
    HOOP_HOUGH_MIN_DIST,
    HOOP_HOUGH_MIN_RADIUS,
    HOOP_HOUGH_PARAM1,
    HOOP_HOUGH_PARAM2,
    HOOP_BACKBOARD_ASPECT_RATIO_MAX,
    HOOP_BACKBOARD_ASPECT_RATIO_MIN,
    HOOP_CACHE_TTL_SEC,
    HOOP_RIM_HSV_LOWER,
    HOOP_RIM_HSV_UPPER,
    HOOP_SCORING_CONFIDENCE_THRESHOLD,
    HOOP_SCORING_MIN_TRAJECTORY_POINTS,
    HOOP_SCORING_PASSING_ZONE_RATIO,
)
from shared.dto.detection_dto import (
    DetectedObject,
    DetectionResult,
    DetectionSource,
    MultiViewDetectionResult,
    ObjectType,
)
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D
from detection.hoop_detection.net_analyzer import NetAnalyzer
from infrastructure.multi_camera.coordinate_transformer import (
    MultiViewTriangulator,
    TriangulatedPoint,
)
from shared.interfaces.detector_interface import (
    BoundingBox as InterfaceBBox,
    DetectedObject as InterfaceDetectedObject,
    DetectionResult as InterfaceDetectionResult,
    DetectionState,
    DetectionTarget,
    DetectorMetrics,
    HoopDetection,
    HoopDetectionResult,
    IHoopDetector,
)

# =============================================================================
# 모듈 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# YOLO 모델 경로 상수
_DEFAULT_MODEL_PATH: Final[str] = "weights/COURTVIEW_hoop.pt"
_DEFAULT_ONNX_PATH: Final[str] = "weights/COURTVIEW_hoop.onnx"

# 멀티뷰 삼각측량 최소 뷰 수
_MIN_TRIANGULATION_VIEWS: Final[int] = 2

# Hough Circle 림 검증 가중치
_HOUGH_WEIGHT: Final[float] = 0.3
_YOLO_WEIGHT: Final[float] = 0.7

# HSV 색상 검증 최소 비율 (bbox 내 오렌지 픽셀 비율)
_MIN_RIM_COLOR_RATIO: Final[float] = 0.15

# 골대 좌/우 판별: 프레임 중앙 기준
_SIDE_THRESHOLD_RATIO: Final[float] = 0.5

# 캐시 최대 크기 (프레임 수)
_MAX_CACHE_SIZE: Final[int] = 300

# 림 중심 추정: bbox 내 상대 위치 (림은 보통 bbox 하단 중앙)
_RIM_CENTER_Y_RATIO: Final[float] = 0.6

# 림 반지름 추정: bbox 너비 대비 비율
_RIM_RADIUS_RATIO: Final[float] = 0.4


# =============================================================================
# 득점 유형 열거형
# =============================================================================

# ScoringType은 shared/constants/hoop_constants.py에서 정의 (순환 참조 방지)
from shared.constants.hoop_constants import ScoringType


# =============================================================================
# 설정 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class HoopDetectorConfig:
    """
    골대 감지기 설정.

    YOLO Primary (2-class: rim/backboard) + Hough Circle 보조
    하이브리드 감지기 파라미터.

    Attributes:
        model_path: YOLO 모델 파일 경로 (.pt)
        onnx_path: ONNX 모델 경로 (TensorRT 변환용)
        input_size: 모델 입력 해상도 (정사각형)
        confidence_threshold: 최소 감지 신뢰도
        nms_iou_threshold: NMS IoU 임계값
        max_detections: 프레임당 최대 감지 수
        device: 추론 장치 ("cuda", "cpu")
        half_precision: FP16 사용 여부
        enable_hough_fallback: Hough Circle 보조 활성화
        hough_dp: Hough 역해상도 비율
        hough_min_dist: Hough 원 중심 간 최소 거리 (px)
        hough_param1: Hough Canny 에지 상한값
        hough_param2: Hough 누적기 임계값
        hough_min_radius: Hough 최소 반지름 (px)
        hough_max_radius: Hough 최대 반지름 (px)
        enable_color_validation: HSV 색상 검증 활성화
        backboard_aspect_min: 백보드 종횡비 하한
        backboard_aspect_max: 백보드 종횡비 상한
        detection_frequency: 전체 감지 주기 (프레임)
        cache_ttl_sec: 골대 위치 캐시 TTL (초)
        enable_multi_view: 멀티뷰 융합 활성화
        min_triangulation_views: 삼각측량 최소 뷰 수
    """

    model_path: str = _DEFAULT_MODEL_PATH
    onnx_path: str = _DEFAULT_ONNX_PATH
    input_size: int = HOOP_DETECTION_INPUT_SIZE
    confidence_threshold: float = HOOP_DETECTION_CONFIDENCE_THRESHOLD
    nms_iou_threshold: float = HOOP_DETECTION_IOU_THRESHOLD
    max_detections: int = HOOP_DETECTION_MAX_DETECTIONS
    device: str = "cuda"
    half_precision: bool = True

    # Hough Circle 보조 파라미터
    enable_hough_fallback: bool = True
    hough_dp: float = HOOP_HOUGH_DP
    hough_min_dist: int = HOOP_HOUGH_MIN_DIST
    hough_param1: int = HOOP_HOUGH_PARAM1
    hough_param2: int = HOOP_HOUGH_PARAM2
    hough_min_radius: int = HOOP_HOUGH_MIN_RADIUS
    hough_max_radius: int = HOOP_HOUGH_MAX_RADIUS

    # 패턴 검증 파라미터
    enable_color_validation: bool = True
    backboard_aspect_min: float = HOOP_BACKBOARD_ASPECT_RATIO_MIN
    backboard_aspect_max: float = HOOP_BACKBOARD_ASPECT_RATIO_MAX

    # 성능 파라미터
    detection_frequency: int = HOOP_DETECTION_FREQUENCY_FRAMES
    cache_ttl_sec: int = HOOP_CACHE_TTL_SEC

    # 멀티뷰
    enable_multi_view: bool = False
    min_triangulation_views: int = _MIN_TRIANGULATION_VIEWS

    def __repr__(self) -> str:
        return (
            f"HoopDetectorConfig(model={self.model_path}, "
            f"input={self.input_size}, conf={self.confidence_threshold}, "
            f"device={self.device}, fp16={self.half_precision}, "
            f"hough={self.enable_hough_fallback})"
        )


# =============================================================================
# 내부 데이터 클래스 — 파이프라인 단계 간 전달용
# =============================================================================

@dataclass(slots=True)
class _HoopCandidate:
    """
    골대 후보 (내부용).

    YOLO 감지 결과 + Hough Circle 검증 점수를 결합한 내부 구조체.

    Attributes:
        bbox_x: 바운딩박스 좌상단 X (px)
        bbox_y: 바운딩박스 좌상단 Y (px)
        bbox_w: 바운딩박스 너비 (px)
        bbox_h: 바운딩박스 높이 (px)
        yolo_confidence: YOLO 감지 신뢰도
        class_id: 클래스 ID (0=림, 1=백보드)
        color_score: HSV 색상 검증 점수 (0.0~1.0)
        hough_score: Hough Circle 검증 점수 (0.0~1.0)
        combined_score: 최종 결합 점수
        camera_id: 카메라 식별자 (멀티뷰)
        frame_index: 프레임 인덱스
        side: 골대 방향 ("left" 또는 "right", None이면 미확인)
    """

    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    yolo_confidence: float
    class_id: int = HOOP_CLASS_ID_RIM
    color_score: float = 0.0
    hough_score: float = 0.0
    combined_score: float = 0.0
    camera_id: str | None = None
    frame_index: int = 0
    side: str | None = None

    @property
    def center_x(self) -> float:
        """중심 X 좌표."""
        return self.bbox_x + self.bbox_w / 2.0

    @property
    def center_y(self) -> float:
        """중심 Y 좌표."""
        return self.bbox_y + self.bbox_h / 2.0

    @property
    def aspect_ratio(self) -> float:
        """종횡비 (w/h)."""
        if self.bbox_h <= 0:
            return 0.0
        return self.bbox_w / self.bbox_h

    @property
    def area(self) -> float:
        """면적 (px²)."""
        return max(0.0, self.bbox_w * self.bbox_h)

    @property
    def is_rim(self) -> bool:
        """림 클래스 여부."""
        return self.class_id == HOOP_CLASS_ID_RIM

    @property
    def is_backboard(self) -> bool:
        """백보드 클래스 여부."""
        return self.class_id == HOOP_CLASS_ID_BACKBOARD

    def to_xyxy(self) -> tuple[float, float, float, float]:
        """(x1, y1, x2, y2) 변환."""
        return (
            self.bbox_x,
            self.bbox_y,
            self.bbox_x + self.bbox_w,
            self.bbox_y + self.bbox_h,
        )

    def __repr__(self) -> str:
        cls_name = "rim" if self.is_rim else "backboard"
        return (
            f"_HoopCandidate({cls_name}, "
            f"center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"yolo={self.yolo_confidence:.3f}, "
            f"combined={self.combined_score:.3f})"
        )


# =============================================================================
# 골대 감지기 (YOLO Primary + Hough Circle 보조)
# =============================================================================

class HoopDetector(IHoopDetector[HoopDetectorConfig]):
    """
    YOLO Primary + Hough Circle 보조 골대 감지기.

    COURTVIEW_hoop.pt 자체 학습 YOLO 모델 (2-class: rim=0, backboard=1)을
    Primary로 사용하고, Hough Circle Transform으로 림 원형 검증을 보조합니다.

    골대는 경기 중 위치가 거의 변하지 않는 정적 객체이므로,
    detection_frequency 간격으로만 전체 감지를 수행하고
    나머지 프레임에서는 캐시된 결과를 반환합니다.

    파이프라인:
        1. YOLO 추론 → 림/백보드 후보 추출 (Primary)
        2. Hough Circle Transform으로 림 원형 검증 (보조)
        3. HSV 색상 검증 (오렌지 림 필터)
        4. 백보드 종횡비 검증
        5. 최종 점수 산출 + 좌/우 골대 매칭
        6. 결과 캐싱 (정적 객체 최적화)
        7. (멀티뷰) cross-view 매칭 + 삼각측량 → 3D 위치

    사용 예시::

        >>> config = HoopDetectorConfig(model_path="weights/COURTVIEW_hoop.pt")
        >>> detector = HoopDetector()
        >>> detector.initialize(config)
        >>> result = detector.detect(frame, frame_index=0)
        >>> if result.success:
        ...     for obj in result.objects:
        ...         print(obj.bounding_box.center)
    """

    def __init__(self) -> None:
        """골대 감지기 초기화."""
        self._lock = threading.RLock()
        self._config: HoopDetectorConfig | None = None
        self._model: Any = None  # ultralytics.YOLO 인스턴스
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()
        self._detection_cache: deque[HoopDetectionResult] = deque(
            maxlen=_MAX_CACHE_SIZE,
        )
        # 런타임 장치/정밀도 (initialize에서 CUDA 가용성 기반으로 결정)
        self._effective_device: str = "cpu"
        self._effective_half: bool = False
        # 멀티뷰 삼각측량기 (infrastructure에서 주입)
        self._triangulator: MultiViewTriangulator | None = None
        # 캐싱: 마지막 전체 감지 프레임 인덱스
        self._last_full_detection_frame: int = -1
        # 캐싱: 마지막 감지 결과 (정적 객체 최적화)
        self._cached_hoops: list[HoopDetection] = []
        self._cached_candidates: list[_HoopCandidate] = []
        # 서브모듈: 네트 모션 분석 (득점 감지)
        self._net_analyzer: NetAnalyzer = NetAnalyzer()
        logger.info("HoopDetector 인스턴스 생성")

    # =========================================================================
    # IDetector 추상 속성 구현
    # =========================================================================

    @property
    def name(self) -> str:
        """탐지기 이름."""
        return "HoopDetector"

    @property
    def version(self) -> str:
        """탐지기 버전."""
        return __version__

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원하는 탐지 대상."""
        return [DetectionTarget.HOOP]

    @property
    def state(self) -> DetectionState:
        """현재 상태."""
        return self._state

    @property
    def metrics(self) -> DetectorMetrics:
        """성능 메트릭."""
        return self._metrics

    # =========================================================================
    # IDetector 추상 메서드 구현
    # =========================================================================

    def initialize(
        self, config: HoopDetectorConfig, unified_mode: bool = False,
    ) -> None:
        """
        감지기 초기화 및 YOLO 모델 로드.

        Args:
            config: 감지기 설정
            unified_mode: True이면 개별 YOLO 모델 로드 생략
                         (CV-BBox 통합 모델이 추론, 후처리만 수행)

        Raises:
            FileNotFoundError: 모델 파일이 존재하지 않는 경우
            RuntimeError: 모델 로드 실패 시
        """
        with self._lock:
            # 이미 unified_mode로 초기화됨 → 외부 재초기화 무시
            if self._state == DetectionState.READY and getattr(self, "_unified_mode", False):
                logger.info("HoopDetector unified_mode 보호 — 재초기화 무시")
                return

            if self._state == DetectionState.READY:
                logger.warning("이미 초기화된 감지기를 재초기화합니다")
                self.shutdown()

            self._config = config
            self._unified_mode = unified_mode

            # 통합 모드: YOLO 모델 로드 생략 (후처리만 사용)
            if unified_mode:
                self._model = None
                self._state = DetectionState.READY
                logger.info(
                    "HoopDetector 초기화 완료 (통합 모드 — 후처리 전용)",
                )
                return

            model_path = Path(config.model_path)

            if not model_path.exists():
                msg = f"YOLO 모델 파일을 찾을 수 없습니다: {model_path}"
                logger.error(msg)
                self._state = DetectionState.ERROR
                raise FileNotFoundError(msg)

            try:
                # ultralytics YOLO 모델 로드
                from ultralytics import YOLO

                self._model = YOLO(str(model_path))

                # GPU 장치 설정 + FP16 워밍업
                device = config.device
                use_half = config.half_precision
                if device == "cuda":
                    import torch
                    if not torch.cuda.is_available():
                        logger.warning("CUDA 사용 불가, CPU로 폴백합니다")
                        device = "cpu"
                        use_half = False
                self._effective_device = device
                self._effective_half = use_half

                # 워밍업 추론 (첫 추론 지연 방지)
                warmup_frame = np.zeros(
                    (config.input_size, config.input_size, 3),
                    dtype=np.uint8,
                )
                self._model.predict(
                    warmup_frame,
                    device=self._effective_device,
                    imgsz=config.input_size,
                    half=self._effective_half,
                    verbose=False,
                )

                self._state = DetectionState.READY
                logger.info(
                    "HoopDetector 초기화 완료: model=%s, device=%s, fp16=%s",
                    model_path.name,
                    self._effective_device,
                    self._effective_half,
                )
            except Exception as exc:
                self._state = DetectionState.ERROR
                self._metrics.last_error = str(exc)
                logger.error("YOLO 모델 로드 실패: %s", exc)
                raise RuntimeError(
                    f"YOLO 모델 로드 실패: {exc}"
                ) from exc

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        targets: list[DetectionTarget] | None = None,
    ) -> InterfaceDetectionResult:
        """
        단일 프레임에서 골대 감지.

        골대는 정적 객체이므로 detection_frequency 간격으로만 전체 감지를
        수행하고, 나머지 프레임에서는 캐시된 결과를 반환합니다.

        Args:
            frame: BGR 이미지 (H, W, 3)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            targets: 탐지할 대상 (None이면 HOOP)

        Returns:
            InterfaceDetectionResult: 탐지 결과
        """
        start_time = time.perf_counter()

        # 상태 검증
        if self._state != DetectionState.READY:
            return InterfaceDetectionResult.failure_result(
                error_message=f"감지기 상태 이상: {self._state.value}",
                frame_index=frame_index,
            )

        # 프레임 유효성 검증
        if not self.validate_frame(frame):
            return InterfaceDetectionResult.failure_result(
                error_message="유효하지 않은 프레임",
                frame_index=frame_index,
            )

        with self._lock:
            self._state = DetectionState.DETECTING

            try:
                # 캐시 히트 확인 (정적 객체 최적화)
                should_detect = self._should_run_full_detection(frame_index)

                if should_detect:
                    # 전체 감지 파이프라인 실행
                    candidates = self._full_detection_pipeline(frame)
                    self._cached_candidates = candidates
                    self._last_full_detection_frame = frame_index

                    # HoopDetection 변환 + 캐시 갱신
                    self._cached_hoops = self._candidates_to_hoops(
                        candidates, frame.shape[1],
                    )
                else:
                    candidates = self._cached_candidates

                # 결과 변환
                processing_time_ms = (
                    time.perf_counter() - start_time
                ) * 1000.0

                detected_objects = self._candidates_to_interface_objects(
                    candidates,
                )

                result = InterfaceDetectionResult.success_result(
                    objects=detected_objects,
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    processing_time_ms=processing_time_ms,
                    metadata={
                        "num_hoops": len(candidates),
                        "cached": not should_detect,
                        "detector": self.name,
                    },
                )

                # 메트릭 업데이트
                self._metrics.update(result)
                self._state = DetectionState.READY

                return result

            except Exception as exc:
                self._state = DetectionState.READY
                self._metrics.last_error = str(exc)
                logger.error("골대 감지 중 오류: %s", exc, exc_info=True)
                return InterfaceDetectionResult.failure_result(
                    error_message=f"감지 오류: {exc}",
                    frame_index=frame_index,
                )

    def process_detections(
        self,
        detections: list,
        frames: dict[str, np.ndarray],
        frame_index: int = 0,
    ) -> MultiViewDetectionResult:
        """
        CV-BBox 통합 추론 결과에서 골대 감지 후처리.

        외부에서 이미 추론된 DetectedObject 리스트를 받아
        Hough Circle 검증 + 점수 산출을 수행합니다.

        Args:
            detections: DetectedObject 리스트 (hoop/backboard 클래스만)
            frames: {camera_id: frame} 딕셔너리
            frame_index: 프레임 인덱스

        Returns:
            MultiViewDetectionResult
        """
        from shared.dto.detection_dto import (
            BoundingBox,
            DetectedObject as DtoDetectedObject,
            ObjectType,
        )

        # DetectedObject → _HoopCandidate 변환
        candidates_by_cam: dict[str, list[_HoopCandidate]] = {}

        for det in detections:
            cam_id = getattr(det, "camera_id", "cam_0")
            # CV-BBox cls: 2=hoop, 3=backboard → HoopDetector cls: 0=rim, 1=backboard
            orig_cls = getattr(det, "class_id", 2)
            hoop_cls = HOOP_CLASS_ID_RIM if orig_cls == 2 else HOOP_CLASS_ID_BACKBOARD

            # DetectedObject DTO 또는 평면 속성 모두 지원
            bbox = getattr(det, "bbox", None)
            if bbox is not None and hasattr(bbox, "x"):
                bx, by = bbox.x, bbox.y
                bw, bh = bbox.width, bbox.height
            else:
                bx = getattr(det, "bbox_x", 0.0)
                by = getattr(det, "bbox_y", 0.0)
                bw = getattr(det, "bbox_w", 0.0)
                bh = getattr(det, "bbox_h", 0.0)

            candidate = _HoopCandidate(
                bbox_x=bx, bbox_y=by, bbox_w=bw, bbox_h=bh,
                yolo_confidence=det.confidence,
                class_id=hoop_cls,
                camera_id=cam_id,
                frame_index=frame_index,
            )
            candidates_by_cam.setdefault(cam_id, []).append(candidate)

        # 카메라별 후처리
        all_objects: list[DtoDetectedObject] = []

        for cam_id, candidates in candidates_by_cam.items():
            frame = frames.get(cam_id)
            if frame is None:
                continue

            # Hough Circle 검증 (림 후보만)
            try:
                candidates = self._hough_circle_validation(frame, candidates)
            except Exception:
                pass

            # 점수 산출
            candidates = self._compute_combined_scores(candidates)

            for c in candidates:
                obj_type = ObjectType.HOOP if c.class_id == HOOP_CLASS_ID_RIM else ObjectType.BACKBOARD
                obj = DtoDetectedObject(
                    object_type=obj_type,
                    bbox=BoundingBox(
                        x=c.bbox_x,
                        y=c.bbox_y,
                        width=c.bbox_w,
                        height=c.bbox_h,
                    ),
                    confidence=c.combined_score if c.combined_score > 0 else c.yolo_confidence,
                    class_id=c.class_id,
                )
                all_objects.append(obj)

        return MultiViewDetectionResult(
            fused_objects=all_objects,
            frame_index=frame_index,
        )

    def reset(self) -> None:
        """감지기 상태 초기화."""
        with self._lock:
            self._detection_cache.clear()
            self._cached_hoops.clear()
            self._cached_candidates.clear()
            self._last_full_detection_frame = -1
            self._metrics = DetectorMetrics()
            if self._model is not None:
                self._state = DetectionState.READY
            logger.info("HoopDetector 상태 초기화 완료")

    def shutdown(self) -> None:
        """감지기 종료 및 리소스 해제."""
        with self._lock:
            self._detection_cache.clear()
            self._cached_hoops.clear()
            self._cached_candidates.clear()
            self._last_full_detection_frame = -1
            self._model = None
            self._state = DetectionState.SHUTDOWN
            self._triangulator = None
            logger.info("HoopDetector 종료 완료")

    # =========================================================================
    # IHoopDetector 추상 메서드 구현
    # =========================================================================

    def detect_hoops(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> HoopDetectionResult:
        """
        골대 전용 감지 (IHoopDetector 인터페이스).

        detect()를 호출하고 HoopDetectionResult로 래핑합니다.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            HoopDetectionResult: 골대 전용 감지 결과
        """
        base_result = self.detect(frame, frame_index, timestamp_ms)

        hoop_result = HoopDetectionResult(
            success=base_result.success,
            objects=base_result.objects,
            frame_index=base_result.frame_index,
            timestamp_ms=base_result.timestamp_ms,
            processing_time_ms=base_result.processing_time_ms,
            error_message=base_result.error_message,
            metadata=base_result.metadata,
            hoops=list(self._cached_hoops),
        )

        # 캐시 저장
        self._detection_cache.append(hoop_result)

        return hoop_result

    def detect_score(
        self,
        ball_trajectory: list[tuple[float, float]],
        hoop: HoopDetection,
    ) -> tuple[bool, float]:
        """
        득점 판정 (궤적 기반).

        공 궤적이 림 통과 영역을 관통하는지 판정합니다.
        넷 움직임 기반 정밀 판정은 NetAnalyzer에서 수행합니다.

        Args:
            ball_trajectory: 공 궤적 (최근 N개 포인트)
            hoop: 골대 정보

        Returns:
            (득점 여부, 판정 신뢰도)
        """
        # 최소 궤적 포인트 검증
        if len(ball_trajectory) < HOOP_SCORING_MIN_TRAJECTORY_POINTS:
            return False, 0.0

        rim_cx, rim_cy = hoop.rim_center
        rim_r = hoop.rim_radius
        passing_zone_r = rim_r * HOOP_SCORING_PASSING_ZONE_RATIO

        # 궤적 포인트 중 림 통과 영역 내 진입 검사
        entered = False
        exited_below = False
        entry_idx = -1

        for i, (px, py) in enumerate(ball_trajectory):
            dist = ((px - rim_cx) ** 2 + (py - rim_cy) ** 2) ** 0.5

            if dist <= passing_zone_r:
                if not entered:
                    entered = True
                    entry_idx = i
            elif entered and py > rim_cy:
                # 림 아래로 빠져나감 → 통과
                exited_below = True
                break

        if not (entered and exited_below):
            return False, 0.0

        # 신뢰도 계산: 통과 깊이 + 궤적 연속성
        # 림 중심과의 최소 거리
        in_zone_points = ball_trajectory[entry_idx:]
        min_dist = min(
            ((px - rim_cx) ** 2 + (py - rim_cy) ** 2) ** 0.5
            for px, py in in_zone_points
        )
        proximity_score = max(0.0, 1.0 - min_dist / passing_zone_r)

        # 연속성 점수 (궤적이 끊기지 않았는지)
        continuity_score = min(
            1.0,
            len(in_zone_points) / HOOP_SCORING_MIN_TRAJECTORY_POINTS,
        )

        confidence = 0.6 * proximity_score + 0.4 * continuity_score

        is_score = confidence >= HOOP_SCORING_CONFIDENCE_THRESHOLD

        return is_score, confidence

    # =========================================================================
    # 멀티뷰 융합
    # =========================================================================

    def set_triangulator(
        self,
        triangulator: MultiViewTriangulator,
    ) -> None:
        """
        멀티뷰 삼각측량기 주입 (infrastructure 연결).

        Args:
            triangulator: infrastructure 삼각측량기
        """
        with self._lock:
            self._triangulator = triangulator
            logger.info(
                "MultiViewTriangulator 주입 완료: cameras=%d",
                triangulator.camera_count,
            )

    def detect_multi_view(
        self,
        frames: dict[str, np.ndarray],
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> MultiViewDetectionResult:
        """
        멀티뷰 골대 감지 + 융합.

        각 카메라에서 독립 감지 → cross-view 매칭 →
        삼각측량으로 3D 위치 복원.

        Args:
            frames: {카메라ID: BGR 프레임} 딕셔너리
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            MultiViewDetectionResult: 멀티뷰 융합 결과
        """
        start_time = time.perf_counter()

        # 1단계: 각 뷰에서 독립 감지
        view_results: dict[str, DetectionResult] = {}
        view_candidates: dict[str, list[_HoopCandidate]] = {}

        for camera_id, frame in frames.items():
            interface_result = self.detect(
                frame, frame_index, timestamp_ms,
            )

            dto_objects: list[DetectedObject] = []
            candidates: list[_HoopCandidate] = []

            if interface_result.success:
                for obj in interface_result.objects:
                    bb = obj.bounding_box
                    obj_type = (
                        ObjectType.HOOP if "rim" in obj.attributes.get("class", "")
                        else ObjectType.BACKBOARD
                    )
                    dto_obj = DetectedObject(
                        object_type=obj_type,
                        bbox=BoundingBox(
                            x1=bb.x,
                            y1=bb.y,
                            x2=bb.x_max,
                            y2=bb.y_max,
                        ),
                        confidence=obj.confidence,
                        source=DetectionSource.YOLO,
                        position=Point2D(x=bb.x_center, y=bb.y_center),
                    )
                    dto_objects.append(dto_obj)

                    candidates.append(_HoopCandidate(
                        bbox_x=bb.x,
                        bbox_y=bb.y,
                        bbox_w=bb.width,
                        bbox_h=bb.height,
                        yolo_confidence=obj.confidence,
                        combined_score=obj.confidence,
                        camera_id=camera_id,
                    ))

            view_results[camera_id] = DetectionResult(
                frame_index=frame_index,
                timestamp=timestamp_ms / 1000.0,
                objects=dto_objects,
                source=DetectionSource.YOLO,
                processing_time_ms=interface_result.processing_time_ms,
                camera_id=camera_id,
                image_size=(
                    (frame.shape[0], frame.shape[1]) if frame is not None
                    else None
                ),
            )
            view_candidates[camera_id] = candidates

        # 2단계: cross-view 매칭 + 삼각측량
        fused_objects = self._fuse_multi_view(
            view_candidates, frames,
        )

        # 3단계: 네트 모션 분석 (득점 감지)
        if self._net_analyzer is not None and self._cached_hoops:
            for cam_id, frame in frames.items():
                for hoop in self._cached_hoops:
                    try:
                        scoring_evt = self._net_analyzer.analyze(
                            frame, hoop, frame_index, cam_id,
                        )
                        if scoring_evt is not None:
                            logger.debug(
                                "네트 모션 감지: cam=%s frame=%d", cam_id, frame_index,
                            )
                    except Exception:
                        pass
                break  # 대표 카메라 1대만 분석 (성능 최적화)

        processing_time_ms = (time.perf_counter() - start_time) * 1000.0

        return MultiViewDetectionResult(
            frame_index=frame_index,
            timestamp=timestamp_ms / 1000.0,
            view_results=view_results,
            fused_objects=fused_objects,
            processing_time_ms=processing_time_ms,
        )

    # =========================================================================
    # 공개 유틸리티 메서드
    # =========================================================================

    def get_cached_hoops(self) -> list[HoopDetection]:
        """
        캐시된 골대 감지 결과 반환.

        골대는 정적 객체이므로, 매 프레임 감지 대신
        캐시된 결과를 활용할 수 있습니다.

        Returns:
            캐시된 HoopDetection 목록
        """
        with self._lock:
            return list(self._cached_hoops)

    def get_rim_positions(self) -> dict[str, tuple[float, float]]:
        """
        캐시된 림 중심 좌표 반환.

        Returns:
            {side: (center_x, center_y)} 딕셔너리
        """
        with self._lock:
            positions: dict[str, tuple[float, float]] = {}
            for hoop in self._cached_hoops:
                if hoop.hoop_side is not None:
                    positions[hoop.hoop_side] = hoop.rim_center
            return positions

    # =========================================================================
    # 내부: 전체 감지 파이프라인
    # =========================================================================

    def _should_run_full_detection(self, frame_index: int) -> bool:
        """
        전체 감지 실행 여부 결정.

        정적 객체 최적화: detection_frequency 간격 또는
        캐시 미스 시에만 전체 감지를 수행합니다.

        Args:
            frame_index: 현재 프레임 인덱스

        Returns:
            전체 감지 실행 여부
        """
        # 첫 감지 또는 캐시 비어있음
        if self._last_full_detection_frame < 0 or not self._cached_candidates:
            return True

        # 주기적 갱신
        elapsed = frame_index - self._last_full_detection_frame
        return elapsed >= self._config.detection_frequency

    def _full_detection_pipeline(
        self,
        frame: np.ndarray,
    ) -> list[_HoopCandidate]:
        """
        전체 감지 파이프라인 실행.

        1. YOLO 추론
        2. Hough Circle 보조 검증 (림)
        3. HSV 색상 검증 (림)
        4. 백보드 종횡비 검증
        5. 최종 점수 산출

        Args:
            frame: BGR 이미지

        Returns:
            최종 후보 목록
        """
        # 1단계: YOLO 추론
        candidates = self._yolo_inference(frame)

        if not candidates:
            return candidates

        # 2단계: Hough Circle 보조 검증 (림만)
        if self._config.enable_hough_fallback:
            candidates = self._hough_circle_validation(frame, candidates)

        # 3단계: HSV 색상 검증 (림만)
        if self._config.enable_color_validation:
            candidates = self._color_validation(frame, candidates)

        # 4단계: 백보드 종횡비 검증
        candidates = self._backboard_aspect_validation(candidates)

        # 5단계: 최종 점수 산출 + 정렬
        candidates = self._compute_combined_scores(candidates)

        # 6단계: 상위 N개 선택
        candidates = candidates[: self._config.max_detections]

        return candidates

    # =========================================================================
    # 내부: YOLO 추론
    # =========================================================================

    def _yolo_inference(
        self,
        frame: np.ndarray,
    ) -> list[_HoopCandidate]:
        """
        YOLO 모델 추론으로 골대 후보 추출.

        2-class 모델: 0=rim, 1=backboard

        Args:
            frame: BGR 이미지

        Returns:
            골대 후보 목록
        """
        config = self._config
        results = self._model.predict(
            frame,
            device=self._effective_device,
            imgsz=config.input_size,
            conf=config.confidence_threshold,
            iou=config.nms_iou_threshold,
            half=self._effective_half,
            verbose=False,
            classes=[HOOP_CLASS_ID_RIM, HOOP_CLASS_ID_BACKBOARD],
        )

        candidates: list[_HoopCandidate] = []

        if not results or len(results) == 0:
            return candidates

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return candidates

        boxes = result.boxes
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i].cpu().numpy())
            cls_id = int(boxes.cls[i].cpu().numpy())

            x1, y1, x2, y2 = xyxy
            w = x2 - x1
            h = y2 - y1

            # 유효성 기본 검사
            if w <= 0 or h <= 0:
                continue

            candidates.append(_HoopCandidate(
                bbox_x=float(x1),
                bbox_y=float(y1),
                bbox_w=float(w),
                bbox_h=float(h),
                yolo_confidence=conf,
                class_id=cls_id,
            ))

        return candidates

    # =========================================================================
    # 내부: Hough Circle 보조 검증
    # =========================================================================

    def _hough_circle_validation(
        self,
        frame: np.ndarray,
        candidates: list[_HoopCandidate],
    ) -> list[_HoopCandidate]:
        """
        Hough Circle Transform으로 림 원형 검증.

        림 후보의 ROI에서 원형 구조를 검출하여 점수를 부여합니다.
        백보드 후보에는 적용하지 않습니다.

        Args:
            frame: BGR 이미지
            candidates: 후보 목록

        Returns:
            Hough 점수가 반영된 후보 목록
        """
        config = self._config
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        for c in candidates:
            # 백보드는 Hough 검증 불필요
            if c.is_backboard:
                c.hough_score = 0.5  # 중립 점수
                continue

            # ROI 추출 (여백 포함)
            margin = int(max(c.bbox_w, c.bbox_h) * 0.2)
            x1 = max(0, int(c.bbox_x) - margin)
            y1 = max(0, int(c.bbox_y) - margin)
            x2 = min(w, int(c.bbox_x + c.bbox_w) + margin)
            y2 = min(h, int(c.bbox_y + c.bbox_h) + margin)

            roi_w = x2 - x1
            roi_h = y2 - y1
            if roi_w < 10 or roi_h < 10:
                c.hough_score = 0.0
                continue

            roi = gray[y1:y2, x1:x2]

            # 가우시안 블러 (노이즈 제거)
            blurred = cv2.GaussianBlur(roi, (9, 9), 2)

            # Hough Circle 검출
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=config.hough_dp,
                minDist=config.hough_min_dist,
                param1=config.hough_param1,
                param2=config.hough_param2,
                minRadius=config.hough_min_radius,
                maxRadius=config.hough_max_radius,
            )

            if circles is None:
                c.hough_score = 0.0
                continue

            # 원이 검출됨 → 림 중심과의 일치도로 점수 산출
            circles = circles[0]  # (N, 3) — [cx, cy, radius]
            bbox_cx = c.bbox_w / 2.0  # ROI 내 상대 중심
            bbox_cy = c.bbox_h / 2.0

            best_score = 0.0
            for cx, cy, radius in circles:
                # ROI 좌표 → bbox 내 상대 좌표
                rel_cx = cx - (int(c.bbox_x) - x1)
                rel_cy = cy - (int(c.bbox_y) - y1)

                # 중심 일치도 (bbox 중심과의 거리)
                dist = ((rel_cx - bbox_cx) ** 2 + (rel_cy - bbox_cy) ** 2) ** 0.5
                max_dist = (c.bbox_w ** 2 + c.bbox_h ** 2) ** 0.5 / 2.0
                center_score = max(0.0, 1.0 - dist / max_dist) if max_dist > 0 else 0.0

                # 반지름 적합도 (bbox 크기와 비교)
                expected_r = min(c.bbox_w, c.bbox_h) / 2.0
                radius_score = 1.0 - min(1.0, abs(radius - expected_r) / max(expected_r, 1.0))

                score = 0.6 * center_score + 0.4 * radius_score
                best_score = max(best_score, score)

            c.hough_score = best_score

        return candidates

    # =========================================================================
    # 내부: HSV 색상 검증
    # =========================================================================

    def _color_validation(
        self,
        frame: np.ndarray,
        candidates: list[_HoopCandidate],
    ) -> list[_HoopCandidate]:
        """
        HSV 색상 검증 (오렌지 림 필터).

        림 후보의 ROI에서 오렌지색 픽셀 비율로 점수를 부여합니다.
        백보드 후보에는 적용하지 않습니다.

        Args:
            frame: BGR 이미지
            candidates: 후보 목록

        Returns:
            색상 점수가 반영된 후보 목록
        """
        if not candidates:
            return candidates

        h, w = frame.shape[:2]
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for c in candidates:
            # 백보드는 색상 검증 불필요
            if c.is_backboard:
                c.color_score = 0.5  # 중립 점수
                continue

            # 고신뢰도는 검증 생략
            if c.yolo_confidence >= 0.85:
                c.color_score = 1.0
                continue

            # ROI 추출
            x1 = max(0, int(c.bbox_x))
            y1 = max(0, int(c.bbox_y))
            x2 = min(w, int(c.bbox_x + c.bbox_w))
            y2 = min(h, int(c.bbox_y + c.bbox_h))

            if x2 - x1 < 3 or y2 - y1 < 3:
                c.color_score = 0.0
                continue

            roi_hsv = hsv_frame[y1:y2, x1:x2]

            # 오렌지 림 마스크
            mask = cv2.inRange(
                roi_hsv,
                np.array(HOOP_RIM_HSV_LOWER, dtype=np.uint8),
                np.array(HOOP_RIM_HSV_UPPER, dtype=np.uint8),
            )

            total_pixels = roi_hsv.shape[0] * roi_hsv.shape[1]
            if total_pixels == 0:
                c.color_score = 0.0
                continue

            color_ratio = float(np.count_nonzero(mask)) / total_pixels

            if color_ratio >= _MIN_RIM_COLOR_RATIO:
                c.color_score = 1.0
            else:
                c.color_score = color_ratio / _MIN_RIM_COLOR_RATIO

        return candidates

    # =========================================================================
    # 내부: 백보드 종횡비 검증
    # =========================================================================

    def _backboard_aspect_validation(
        self,
        candidates: list[_HoopCandidate],
    ) -> list[_HoopCandidate]:
        """
        백보드 종횡비 검증.

        백보드 후보의 종횡비가 기준 범위 내인지 확인합니다.
        범위 밖이면 점수를 낮춥니다.

        Args:
            candidates: 후보 목록

        Returns:
            검증된 후보 목록
        """
        config = self._config

        for c in candidates:
            if not c.is_backboard:
                continue

            ar = c.aspect_ratio

            if config.backboard_aspect_min <= ar <= config.backboard_aspect_max:
                # 종횡비 범위 내 → 보너스 점수
                c.hough_score = 1.0
            else:
                # 범위 밖 → 낮은 점수
                mid = (config.backboard_aspect_min + config.backboard_aspect_max) / 2.0
                half_range = (config.backboard_aspect_max - config.backboard_aspect_min) / 2.0
                if half_range > 0:
                    deviation = abs(ar - mid) / half_range
                    c.hough_score = max(0.0, 1.0 - deviation * 0.5)
                else:
                    c.hough_score = 0.5

        return candidates

    # =========================================================================
    # 내부: 최종 점수 산출
    # =========================================================================

    def _compute_combined_scores(
        self,
        candidates: list[_HoopCandidate],
    ) -> list[_HoopCandidate]:
        """
        YOLO + Hough/종횡비 + 색상 점수 결합.

        림: YOLO(0.7) + Hough(0.15) + 색상(0.15)
        백보드: YOLO(0.7) + 종횡비(0.3)

        Args:
            candidates: 후보 목록

        Returns:
            점수순 정렬된 후보 목록
        """
        for c in candidates:
            if c.is_rim:
                c.combined_score = (
                    _YOLO_WEIGHT * c.yolo_confidence
                    + _HOUGH_WEIGHT * 0.5 * c.hough_score
                    + _HOUGH_WEIGHT * 0.5 * c.color_score
                )
            else:
                # 백보드
                c.combined_score = (
                    _YOLO_WEIGHT * c.yolo_confidence
                    + _HOUGH_WEIGHT * c.hough_score
                )

        # combined_score 내림차순 정렬
        candidates.sort(key=lambda x: x.combined_score, reverse=True)

        return candidates

    # =========================================================================
    # 내부: 결과 변환
    # =========================================================================

    def _candidates_to_interface_objects(
        self,
        candidates: list[_HoopCandidate],
    ) -> list[InterfaceDetectedObject]:
        """
        후보를 인터페이스 DetectedObject 목록으로 변환.

        Args:
            candidates: 후보 목록

        Returns:
            인터페이스 객체 목록
        """
        objects: list[InterfaceDetectedObject] = []

        for c in candidates:
            bbox = InterfaceBBox(
                x=c.bbox_x,
                y=c.bbox_y,
                width=c.bbox_w,
                height=c.bbox_h,
                confidence=c.combined_score,
            )
            obj = InterfaceDetectedObject(
                target_type=DetectionTarget.HOOP,
                bounding_box=bbox,
                class_name="rim" if c.is_rim else "backboard",
                attributes={
                    "class_id": c.class_id,
                    "yolo_conf": c.yolo_confidence,
                    "hough_score": c.hough_score,
                    "color_score": c.color_score,
                    "side": c.side,
                },
            )
            objects.append(obj)

        return objects

    def _candidates_to_hoops(
        self,
        candidates: list[_HoopCandidate],
        frame_width: int,
    ) -> list[HoopDetection]:
        """
        후보를 HoopDetection 목록으로 변환.

        림 후보만 HoopDetection으로 변환하고,
        백보드 후보는 연관된 림의 backboard_box로 할당합니다.

        Args:
            candidates: 후보 목록
            frame_width: 프레임 너비 (좌/우 판별용)

        Returns:
            HoopDetection 목록
        """
        # 림과 백보드 분리
        rims = [c for c in candidates if c.is_rim]
        backboards = [c for c in candidates if c.is_backboard]

        # 좌/우 골대 판별
        for c in rims:
            c.side = (
                "left" if c.center_x < frame_width * _SIDE_THRESHOLD_RATIO
                else "right"
            )
        for c in backboards:
            c.side = (
                "left" if c.center_x < frame_width * _SIDE_THRESHOLD_RATIO
                else "right"
            )

        hoops: list[HoopDetection] = []

        for rim in rims:
            # 림 중심 추정 (bbox 내 상대 위치)
            rim_cx = rim.center_x
            rim_cy = rim.bbox_y + rim.bbox_h * _RIM_CENTER_Y_RATIO
            rim_radius = rim.bbox_w * _RIM_RADIUS_RATIO

            # 매칭 백보드 찾기 (같은 쪽에 있는 것)
            matched_bb: InterfaceBBox | None = None
            for bb in backboards:
                if bb.side == rim.side:
                    matched_bb = InterfaceBBox(
                        x=bb.bbox_x,
                        y=bb.bbox_y,
                        width=bb.bbox_w,
                        height=bb.bbox_h,
                    )
                    break

            hoop = HoopDetection(
                bounding_box=InterfaceBBox(
                    x=rim.bbox_x,
                    y=rim.bbox_y,
                    width=rim.bbox_w,
                    height=rim.bbox_h,
                ),
                rim_center=(rim_cx, rim_cy),
                rim_radius=rim_radius,
                backboard_box=matched_bb,
                net_visible=True,  # 네트 가시성은 NetAnalyzer에서 정밀 판정
                hoop_side=rim.side,
            )
            hoops.append(hoop)

        return hoops

    # =========================================================================
    # 내부: 멀티뷰 융합
    # =========================================================================

    def _fuse_multi_view(
        self,
        view_candidates: dict[str, list[_HoopCandidate]],
        frames: dict[str, np.ndarray],
    ) -> list[DetectedObject]:
        """
        멀티뷰 cross-view 매칭 + 삼각측량.

        골대는 정적 객체이므로, 뷰 간 일치하는 위치를
        삼각측량하여 3D 좌표를 복원합니다.

        Args:
            view_candidates: {카메라ID: 후보 목록}
            frames: {카메라ID: 프레임}

        Returns:
            융합된 DetectedObject 목록 (3D 위치 포함)
        """
        if self._triangulator is None or not self._config.enable_multi_view:
            # 삼각측량기 미주입 → 최고 신뢰도 뷰 결과 반환
            best_camera: str | None = None
            best_confidence = 0.0

            for camera_id, cands in view_candidates.items():
                if cands:
                    max_conf = max(c.combined_score for c in cands)
                    if max_conf > best_confidence:
                        best_confidence = max_conf
                        best_camera = camera_id

            if best_camera is None:
                return []

            return [
                DetectedObject(
                    object_type=(
                        ObjectType.HOOP if c.is_rim
                        else ObjectType.BACKBOARD
                    ),
                    bbox=BoundingBox(
                        x1=c.bbox_x,
                        y1=c.bbox_y,
                        x2=c.bbox_x + c.bbox_w,
                        y2=c.bbox_y + c.bbox_h,
                    ),
                    confidence=c.combined_score,
                    source=DetectionSource.YOLO,
                    position=Point2D(x=c.center_x, y=c.center_y),
                )
                for c in view_candidates[best_camera]
            ]

        # 삼각측량: 각 뷰에서 림 중심점 수집
        rim_points: dict[str, tuple[float, float]] = {}
        for camera_id, cands in view_candidates.items():
            rims = [c for c in cands if c.is_rim]
            if rims:
                best_rim = max(rims, key=lambda x: x.combined_score)
                rim_points[camera_id] = (best_rim.center_x, best_rim.center_y)

        fused_objects: list[DetectedObject] = []

        if len(rim_points) >= self._config.min_triangulation_views:
            try:
                triangulated = self._triangulator.triangulate(rim_points)
                fused_objects.append(DetectedObject(
                    object_type=ObjectType.HOOP,
                    bbox=BoundingBox(x1=0, y1=0, x2=0, y2=0),
                    confidence=triangulated.confidence,
                    source=DetectionSource.YOLO,
                    position_3d=Point3D(
                        x=triangulated.x,
                        y=triangulated.y,
                        z=triangulated.z,
                    ),
                ))
            except Exception as exc:
                logger.warning("골대 삼각측량 실패: %s", exc)

        return fused_objects

    # =========================================================================
    # repr
    # =========================================================================

    def __repr__(self) -> str:
        mode = "YOLO"
        if self._config and self._config.enable_hough_fallback:
            mode += "+Hough"
        return (
            f"HoopDetector(state={self._state.value}, "
            f"mode={mode}, device={self._effective_device}, "
            f"cached_hoops={len(self._cached_hoops)})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "HoopDetector",
    "HoopDetectorConfig",
    "ScoringType",
]

__version__: str = "1.0.0"
