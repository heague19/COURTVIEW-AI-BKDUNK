# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection
파일: ball_detector.py
설명: YOLO Primary + 패턴 보조 하이브리드 농구공 감지기
      - COURTVIEW_ball.pt 자체 학습 모델 기반 추론
      - HSV 색상 필터 + 원형도 후처리 검증
      - NMS (Non-Maximum Suppression) 중복 제거
      - 멀티뷰 융합 (infrastructure/multi_camera 삼각측량 위임)
      - TensorRT FP16 가속 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 공 물리 상수, 검출 파라미터
    - shared/dto/ball_dto.py: BallDetection DTO
    - shared/dto/detection_dto.py: DetectedObject, DetectionResult DTO
    - shared/dto/geometry_dto.py: Point2D, Point3D, BoundingBox DTO
    - shared/interfaces/detector_interface.py: IBallDetector 인터페이스
    - infrastructure/multi_camera/coordinate_transformer.py: MultiViewTriangulator
    - configs/detection/ball_detection.yaml: 설정 파라미터
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
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
from shared.constants.ball_constants import (
    BALL_AIR_RESISTANCE_PX,
    BALL_ASPECT_RATIO_MAX,
    BALL_ASPECT_RATIO_MIN,
    BALL_CIRCULARITY_THRESHOLD,
    BALL_COLOR_HSV_LOWER,
    BALL_COLOR_HSV_UPPER,
    BALL_DETECTION_CLASS_ID,
    BALL_DETECTION_COCO_CLASS_ID,
    BALL_DETECTION_HIGH_CONFIDENCE,
    BALL_DETECTION_INPUT_SIZE,
    BALL_DETECTION_IOU_THRESHOLD,
    BALL_DETECTION_MAX_DETECTIONS,
    BALL_DETECTION_MAX_SIZE_RATIO,
    BALL_DETECTION_MIN_CONFIDENCE,
    BALL_DETECTION_MIN_SIZE_RATIO,
    BALL_GRAVITY_PX_PER_SEC2,
    BALL_MAX_SIZE_PIXELS,
    BALL_MIN_SIZE_PIXELS,
    BallSize,
)
from shared.dto.ball_dto import BallDetection
from detection.ball_detection.ball_tracker import BallTracker
from shared.dto.detection_dto import (
    DetectedObject,
    DetectionResult,
    DetectionSource,
    MultiViewDetectionResult,
    ObjectType,
)
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D
from infrastructure.multi_camera.coordinate_transformer import (
    MultiViewTriangulator,
    TriangulatedPoint,
)
from shared.interfaces.detector_interface import (
    BallDetectionResult,
    BallState as InterfaceBallState,
    BoundingBox as InterfaceBBox,
    DetectedObject as InterfaceDetectedObject,
    DetectionResult as InterfaceDetectionResult,
    DetectionState,
    DetectionTarget,
    DetectorMetrics,
    IBallDetector,
)

# =============================================================================
# 모듈 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# YOLO 모델 기본 경로
_DEFAULT_MODEL_PATH: Final[str] = "weights/COURTVIEW_ball.pt"
_DEFAULT_ONNX_PATH: Final[str] = "weights/COURTVIEW_ball.onnx"

# 패턴 보조 검증: 확장 HSV 범위 (갈색 가죽 농구공)
_BROWN_HSV_LOWER: Final[tuple[int, int, int]] = (10, 50, 50)
_BROWN_HSV_UPPER: Final[tuple[int, int, int]] = (30, 200, 200)

# 색상 검증 최소 비율 (bbox 내 농구공 색상 픽셀 비율)
_MIN_COLOR_RATIO: Final[float] = 0.3

# 멀티뷰 삼각측량 최소 뷰 수
_MIN_TRIANGULATION_VIEWS: Final[int] = 2

# 감지 결과 캐시 최대 크기 (프레임 수)
_MAX_CACHE_SIZE: Final[int] = 300


# =============================================================================
# 설정 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class BallDetectorConfig:
    """
    공 감지기 설정.

    YOLO Primary + 패턴 보조 하이브리드 감지기 파라미터.

    Attributes:
        model_path: YOLO 모델 파일 경로 (.pt)
        onnx_path: ONNX 모델 경로 (TensorRT 변환용)
        input_size: 모델 입력 해상도 (정사각형)
        confidence_threshold: 최소 감지 신뢰도
        high_confidence_threshold: 높은 신뢰도 임계값 (패턴 검증 생략)
        nms_iou_threshold: NMS IoU 임계값
        max_detections: 프레임당 최대 감지 수
        device: 추론 장치 ("cuda", "cpu")
        half_precision: FP16 사용 여부
        enable_color_validation: 패턴 보조 색상 검증 활성화
        enable_shape_validation: 패턴 보조 형태 검증 활성화
        enable_multi_view: 멀티뷰 융합 활성화
        min_triangulation_views: 삼각측량 최소 뷰 수
        ball_size: 농구공 크기 규격
    """

    model_path: str = _DEFAULT_MODEL_PATH
    onnx_path: str = _DEFAULT_ONNX_PATH
    input_size: int = BALL_DETECTION_INPUT_SIZE
    confidence_threshold: float = BALL_DETECTION_MIN_CONFIDENCE
    high_confidence_threshold: float = BALL_DETECTION_HIGH_CONFIDENCE
    nms_iou_threshold: float = BALL_DETECTION_IOU_THRESHOLD
    max_detections: int = BALL_DETECTION_MAX_DETECTIONS
    device: str = "cuda"
    half_precision: bool = True
    enable_color_validation: bool = True
    enable_shape_validation: bool = True
    enable_multi_view: bool = False
    min_triangulation_views: int = _MIN_TRIANGULATION_VIEWS
    ball_size: BallSize = BallSize.SIZE_7

    def __repr__(self) -> str:
        return (
            f"BallDetectorConfig(model={self.model_path}, "
            f"input={self.input_size}, conf={self.confidence_threshold}, "
            f"device={self.device}, fp16={self.half_precision})"
        )


# =============================================================================
# 후보 데이터 클래스 (내부용)
# =============================================================================

@dataclass(slots=True)
class _BallCandidate:
    """
    공 후보 (내부용).

    YOLO 감지 결과 + 패턴 검증 점수를 결합한 내부 구조체.
    """

    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    yolo_confidence: float
    class_id: int = BALL_DETECTION_CLASS_ID
    color_score: float = 0.0
    shape_score: float = 0.0
    combined_score: float = 0.0
    camera_id: str | None = None

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
    def radius_pixels(self) -> float:
        """추정 반지름 (픽셀)."""
        return (self.bbox_w + self.bbox_h) / 4.0

    def __repr__(self) -> str:
        return (
            f"_BallCandidate(center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"yolo={self.yolo_confidence:.3f}, combined={self.combined_score:.3f})"
        )


# =============================================================================
# 공 감지기 (YOLO Primary + 패턴 보조)
# =============================================================================

class BallDetector(IBallDetector[BallDetectorConfig]):
    """
    YOLO Primary + 패턴 보조 농구공 감지기.

    COURTVIEW_ball.pt 자체 학습 YOLO 모델을 Primary로 사용하고,
    HSV 색상 필터링 + 원형도 검증을 보조 후처리로 적용합니다.
    멀티뷰 융합(cross-view 매칭 + 삼각측량)을 모듈 내 통합 지원합니다.

    파이프라인:
        1. YOLO 추론 → 공 후보 추출 (Primary)
        2. NMS 중복 제거
        3. 크기/종횡비 필터링
        4. HSV 색상 검증 (보조)
        5. 원형도/형태 검증 (보조)
        6. 최종 점수 산출 + 최선 후보 선택
        7. (멀티뷰) cross-view 매칭 + 삼각측량 → 3D 위치

    사용 예시::

        >>> config = BallDetectorConfig(model_path="weights/COURTVIEW_ball.pt")
        >>> detector = BallDetector()
        >>> detector.initialize(config)
        >>> result = detector.detect(frame, frame_index=0)
        >>> if result.success:
        ...     for obj in result.objects:
        ...         print(obj.bounding_box.center)
    """

    def __init__(self) -> None:
        """공 감지기 초기화."""
        self._lock = threading.RLock()
        self._config: BallDetectorConfig | None = None
        self._model: Any = None  # ultralytics.YOLO 인스턴스
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()
        self._detection_cache: deque[BallDetectionResult] = deque(
            maxlen=_MAX_CACHE_SIZE,
        )
        # 런타임 장치/정밀도 (initialize에서 CUDA 가용성 기반으로 결정)
        self._effective_device: str = "cpu"
        self._effective_half: bool = False
        # 멀티뷰 삼각측량기 (infrastructure에서 주입)
        self._triangulator: MultiViewTriangulator | None = None
        # 서브모듈: 공 추적기
        self._ball_tracker: BallTracker = BallTracker()
        logger.info("BallDetector 인스턴스 생성")

    # =========================================================================
    # IDetector 추상 속성 구현
    # =========================================================================

    @property
    def name(self) -> str:
        """탐지기 이름."""
        return "BallDetector"

    @property
    def version(self) -> str:
        """탐지기 버전."""
        return __version__

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        """지원하는 탐지 대상."""
        return [DetectionTarget.BALL]

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
        self, config: BallDetectorConfig, unified_mode: bool = False,
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
                logger.info("BallDetector unified_mode 보호 — 재초기화 무시")
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
                    "BallDetector 초기화 완료 (통합 모드 — 후처리 전용)",
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
                    "BallDetector 초기화 완료: model=%s, device=%s, fp16=%s",
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
        단일 프레임에서 농구공 감지.

        YOLO Primary → NMS → 크기/종횡비 필터 → HSV 색상 검증
        → 형태 검증 → 최종 점수 산출 → 결과 반환.

        Args:
            frame: BGR 이미지 (H, W, 3)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            targets: 탐지할 대상 (None이면 BALL)

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
                # 1단계: YOLO 추론
                candidates = self._yolo_inference(frame)

                # 2단계: 크기/종횡비 필터링
                candidates = self._filter_by_size(
                    candidates, frame.shape[1], frame.shape[0],
                )

                # 3단계: 패턴 보조 검증 (색상 + 형태)
                candidates = self._pattern_validation(frame, candidates)

                # 4단계: 최종 점수 산출 + 정렬
                candidates = self._compute_combined_scores(candidates)

                # 5단계: 상위 N개 선택
                candidates = candidates[: self._config.max_detections]

                # 결과 변환
                processing_time_ms = (
                    time.perf_counter() - start_time
                ) * 1000.0
                detected_objects = self._candidates_to_objects(candidates)

                result = InterfaceDetectionResult.success_result(
                    objects=detected_objects,
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    processing_time_ms=processing_time_ms,
                    metadata={
                        "num_yolo_raw": len(candidates),
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
                logger.error("공 감지 중 오류: %s", exc, exc_info=True)
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
        CV-BBox 통합 추론 결과에서 공 감지 후처리.

        외부에서 이미 추론된 DetectedObject 리스트를 받아
        크기 필터링 + 패턴 검증 + 점수 산출을 수행합니다.
        YOLO 추론을 건너뛰고 후처리만 실행합니다.

        Args:
            detections: DetectedObject 리스트 (ball 클래스만)
            frames: {camera_id: frame} 딕셔너리
            frame_index: 프레임 인덱스

        Returns:
            MultiViewDetectionResult
        """
        # DetectedObject → _BallCandidate 변환
        # 입력 형식 두 가지 모두 지원: DTO(det.bbox.x) 및 평면 속성(det.bbox_x)
        candidates_by_cam: dict[str, list[_BallCandidate]] = {}

        for det in detections:
            cam_id = getattr(det, "camera_id", "cam_0")
            # DetectedObject DTO 우선
            bbox = getattr(det, "bbox", None)
            if bbox is not None and hasattr(bbox, "x"):
                bx, by = bbox.x, bbox.y
                bw, bh = bbox.width, bbox.height
            else:
                bx = getattr(det, "bbox_x", 0.0)
                by = getattr(det, "bbox_y", 0.0)
                bw = getattr(det, "bbox_w", 0.0)
                bh = getattr(det, "bbox_h", 0.0)

            candidate = _BallCandidate(
                bbox_x=bx, bbox_y=by, bbox_w=bw, bbox_h=bh,
                yolo_confidence=det.confidence,
                class_id=getattr(det, "class_id", 0),
                camera_id=cam_id,
            )
            candidates_by_cam.setdefault(cam_id, []).append(candidate)

        # 카메라별 후처리 (크기 필터 + 패턴 검증 + 점수)
        all_objects: list[DetectedObject] = []

        for cam_id, candidates in candidates_by_cam.items():
            frame = frames.get(cam_id)
            if frame is None:
                continue

            if self._config is not None:
                candidates = self._filter_by_size(
                    candidates, frame.shape[1], frame.shape[0],
                )
                candidates = self._pattern_validation(frame, candidates)
                candidates = self._compute_combined_scores(candidates)
                candidates = candidates[: self._config.max_detections]

            all_objects.extend(self._candidates_to_objects(candidates))

        return MultiViewDetectionResult(
            fused_objects=all_objects,
            frame_index=frame_index,
        )

    def reset(self) -> None:
        """감지기 상태 초기화."""
        with self._lock:
            self._detection_cache.clear()
            self._metrics = DetectorMetrics()
            if self._model is not None:
                self._state = DetectionState.READY
            logger.info("BallDetector 상태 초기화 완료")

    def shutdown(self) -> None:
        """감지기 종료 및 리소스 해제."""
        with self._lock:
            self._detection_cache.clear()
            self._model = None
            self._state = DetectionState.SHUTDOWN
            self._triangulator = None
            logger.info("BallDetector 종료 완료")

    # =========================================================================
    # IBallDetector 추상 메서드 구현
    # =========================================================================

    def detect_ball(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> BallDetectionResult:
        """
        공 전용 감지 (IBallDetector 인터페이스).

        detect()를 호출하고 BallDetectionResult로 래핑합니다.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            BallDetectionResult: 공 전용 감지 결과
        """
        base_result = self.detect(frame, frame_index, timestamp_ms)

        ball_state: InterfaceBallState | None = None
        predicted_position: tuple[float, float] | None = None

        if base_result.success and base_result.objects:
            best = base_result.objects[0]
            center = best.bounding_box.center
            ball_state = InterfaceBallState(
                position=center,
                radius=min(
                    best.bounding_box.width,
                    best.bounding_box.height,
                ) / 2.0,
                is_visible=True,
            )

            # 캐시에서 이전 결과로 속도 추정
            if self._detection_cache:
                prev = self._detection_cache[-1]
                if prev.ball_state is not None:
                    dt = (timestamp_ms - prev.timestamp_ms) / 1000.0
                    if dt > 0:
                        vx = (center[0] - prev.ball_state.position[0]) / dt
                        vy = (center[1] - prev.ball_state.position[1]) / dt
                        ball_state.velocity = (vx, vy)
                        # 단순 선형 예측 (1프레임 앞)
                        predicted_position = (
                            center[0] + vx * dt,
                            center[1] + vy * dt,
                        )

        ball_result = BallDetectionResult(
            success=base_result.success,
            objects=base_result.objects,
            frame_index=base_result.frame_index,
            timestamp_ms=base_result.timestamp_ms,
            processing_time_ms=base_result.processing_time_ms,
            error_message=base_result.error_message,
            metadata=base_result.metadata,
            ball_state=ball_state,
            predicted_position=predicted_position,
            prediction_confidence=(
                0.7 if (ball_state is not None and ball_state.velocity is not None) else 0.0
            ),
        )

        # 캐시 저장
        self._detection_cache.append(ball_result)

        return ball_result

    def predict_trajectory(
        self,
        current_state: InterfaceBallState,
        time_ahead_ms: float,
    ) -> list[tuple[float, float]]:
        """
        물리 기반 공 궤적 예측.

        등가속도 운동 + 중력 효과로 미래 위치를 예측합니다.

        Args:
            current_state: 현재 공 상태
            time_ahead_ms: 예측할 미래 시간 (밀리초)

        Returns:
            예측 궤적 점 목록 [(x, y), ...]
        """
        if current_state.velocity is None:
            return [current_state.position]

        trajectory: list[tuple[float, float]] = []
        x, y = current_state.position
        vx, vy = current_state.velocity

        # 픽셀 공간 중력 효과 (아래 방향 양수)
        gravity_px = BALL_GRAVITY_PX_PER_SEC2
        air_resistance = BALL_AIR_RESISTANCE_PX

        dt = 1.0 / 30.0  # 30fps 기준 시간 간격
        steps = int(time_ahead_ms / (dt * 1000.0))
        steps = min(steps, 90)  # 최대 3초 (90프레임)

        for _ in range(steps):
            x += vx * dt
            y += vy * dt
            vy += gravity_px * dt  # 중력 가속
            vx *= air_resistance  # 공기 저항 감속
            vy *= air_resistance
            trajectory.append((x, y))

        return trajectory

    def is_ball_in_hoop_region(
        self,
        ball_state: InterfaceBallState,
        hoop_region: InterfaceBBox,
    ) -> bool:
        """
        공이 골대 영역에 있는지 확인.

        Args:
            ball_state: 공 상태
            hoop_region: 골대 바운딩 박스

        Returns:
            골대 영역 내 여부
        """
        bx, by = ball_state.position
        return hoop_region.contains_point(bx, by)

    # =========================================================================
    # 멀티뷰 융합
    # =========================================================================

    def set_triangulator(
        self,
        triangulator: MultiViewTriangulator,
    ) -> None:
        """
        멀티뷰 삼각측량기 주입 (infrastructure 연결).

        CameraManager.calibrate_all() 완료 후 생성된
        MultiViewTriangulator를 주입합니다.

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
        멀티뷰 공 감지 + 융합.

        각 카메라 프레임에서 독립 감지 → cross-view 매칭 →
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
        view_candidates: dict[str, list[_BallCandidate]] = {}

        for camera_id, frame in frames.items():
            interface_result = self.detect(
                frame, frame_index, timestamp_ms,
            )

            # InterfaceDetectionResult → shared DTO DetectionResult 변환
            dto_objects: list[DetectedObject] = []
            candidates: list[_BallCandidate] = []

            if interface_result.success:
                for obj in interface_result.objects:
                    bb = obj.bounding_box
                    dto_obj = DetectedObject(
                        object_type=ObjectType.BALL,
                        bbox=BoundingBox(
                            x1=bb.x,
                            y1=bb.y,
                            x2=bb.x_max,
                            y2=bb.y_max,
                        ),
                        confidence=obj.confidence,
                        source=DetectionSource.BALL_DETECTOR,
                        position=Point2D(x=bb.x_center, y=bb.y_center),
                    )
                    dto_objects.append(dto_obj)

                    candidates.append(_BallCandidate(
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
                source=DetectionSource.BALL_DETECTOR,
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

        # 3단계: 공 추적기 갱신 (시간적 안정성 확보)
        if self._ball_tracker is not None and fused_objects:
            ball_dtos: list[BallDetection] = []
            for obj in fused_objects:
                if obj.position is not None:
                    ball_dtos.append(BallDetection(
                        position=obj.position,
                        confidence=obj.confidence,
                        bbox=obj.bbox,
                        frame_index=frame_index,
                    ))
            if ball_dtos:
                try:
                    self._ball_tracker.update(
                        ball_dtos, frame_index, timestamp_ms,
                    )
                except Exception:
                    logger.debug("BallTracker 갱신 오류")

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

    def detect_to_dto(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        camera_id: str | None = None,
    ) -> BallDetection | None:
        """
        감지 결과를 shared DTO BallDetection으로 반환.

        상위 모듈(ball_tracker, ball_state)이 DTO 기반으로 동작하므로,
        인터페이스 결과를 DTO로 변환하는 편의 메서드.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)
            camera_id: 카메라 ID

        Returns:
            BallDetection DTO 또는 None (미감지 시)
        """
        ball_result = self.detect_ball(frame, frame_index, timestamp_ms)

        if not ball_result.success or not ball_result.objects:
            return None

        best = ball_result.objects[0]
        bb = best.bounding_box

        return BallDetection(
            position=Point2D(x=bb.x_center, y=bb.y_center),
            confidence=best.confidence,
            bbox=BoundingBox(
                x1=bb.x,
                y1=bb.y,
                x2=bb.x_max,
                y2=bb.y_max,
            ),
            radius_pixels=min(bb.width, bb.height) / 2.0,
            frame_index=frame_index,
            camera_id=camera_id,
        )

    # =========================================================================
    # 내부 메서드: YOLO 추론
    # =========================================================================

    def _yolo_inference(
        self,
        frame: np.ndarray,
    ) -> list[_BallCandidate]:
        """
        YOLO 모델 추론으로 공 후보 추출.

        Args:
            frame: BGR 이미지

        Returns:
            공 후보 목록
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
            classes=[BALL_DETECTION_CLASS_ID, BALL_DETECTION_COCO_CLASS_ID],
        )

        candidates: list[_BallCandidate] = []

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

            # 유효성 기본 검사 (음수 크기 방지)
            if w <= 0 or h <= 0:
                continue

            candidates.append(_BallCandidate(
                bbox_x=float(x1),
                bbox_y=float(y1),
                bbox_w=float(w),
                bbox_h=float(h),
                yolo_confidence=conf,
                class_id=cls_id,
            ))

        return candidates

    # =========================================================================
    # 내부 메서드: 크기/종횡비 필터링
    # =========================================================================

    def _filter_by_size(
        self,
        candidates: list[_BallCandidate],
        frame_width: int,
        frame_height: int,
    ) -> list[_BallCandidate]:
        """
        크기 및 종횡비 기반 필터링.

        프레임 대비 최소/최대 크기 비율과 종횡비로 필터링합니다.

        Args:
            candidates: 후보 목록
            frame_width: 프레임 너비
            frame_height: 프레임 높이

        Returns:
            필터링된 후보 목록
        """
        if not candidates:
            return candidates

        frame_diag = np.sqrt(frame_width ** 2 + frame_height ** 2)
        min_size = frame_diag * BALL_DETECTION_MIN_SIZE_RATIO
        max_size = frame_diag * BALL_DETECTION_MAX_SIZE_RATIO

        filtered: list[_BallCandidate] = []

        for c in candidates:
            # 절대 픽셀 크기 검사
            size = max(c.bbox_w, c.bbox_h)
            if size < BALL_MIN_SIZE_PIXELS or size > BALL_MAX_SIZE_PIXELS:
                continue

            # 프레임 대비 비율 검사
            if size < min_size or size > max_size:
                continue

            # 종횡비 검사
            ar = c.aspect_ratio
            if ar < BALL_ASPECT_RATIO_MIN or ar > BALL_ASPECT_RATIO_MAX:
                continue

            filtered.append(c)

        return filtered

    # =========================================================================
    # 내부 메서드: 패턴 보조 검증
    # =========================================================================

    def _pattern_validation(
        self,
        frame: np.ndarray,
        candidates: list[_BallCandidate],
    ) -> list[_BallCandidate]:
        """
        패턴 기반 보조 검증 (HSV 색상 + 형태).

        YOLO 고신뢰도(≥0.8) 후보는 검증을 생략하고 만점 부여합니다.

        Args:
            frame: BGR 이미지
            candidates: 후보 목록

        Returns:
            검증 점수가 반영된 후보 목록
        """
        if not candidates:
            return candidates

        config = self._config
        h, w = frame.shape[:2]

        # HSV 변환 (전체 프레임 1회)
        hsv_frame: NDArray[np.uint8] | None = None
        if config.enable_color_validation:
            hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for c in candidates:
            # 고신뢰도는 검증 생략
            if c.yolo_confidence >= config.high_confidence_threshold:
                c.color_score = 1.0
                c.shape_score = 1.0
                continue

            # ROI 추출 (bbox + 여백)
            margin = 2
            x1 = max(0, int(c.bbox_x) - margin)
            y1 = max(0, int(c.bbox_y) - margin)
            x2 = min(w, int(c.bbox_x + c.bbox_w) + margin)
            y2 = min(h, int(c.bbox_y + c.bbox_h) + margin)

            if x2 - x1 < 3 or y2 - y1 < 3:
                c.color_score = 0.0
                c.shape_score = 0.0
                continue

            # 색상 검증
            if config.enable_color_validation and hsv_frame is not None:
                c.color_score = self._validate_color(hsv_frame[y1:y2, x1:x2])

            # 형태 검증
            if config.enable_shape_validation:
                gray_roi = cv2.cvtColor(
                    frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY,
                )
                c.shape_score = self._validate_shape(gray_roi)

        return candidates

    def _validate_color(
        self,
        hsv_roi: NDArray[np.uint8],
    ) -> float:
        """
        HSV 색상 검증.

        주황색 + 갈색 마스크 비율로 농구공 여부를 점수화합니다.

        Args:
            hsv_roi: HSV 색상 공간 ROI

        Returns:
            색상 점수 (0.0 ~ 1.0)
        """
        # 주황색 마스크
        orange_mask = cv2.inRange(
            hsv_roi,
            np.array(BALL_COLOR_HSV_LOWER, dtype=np.uint8),
            np.array(BALL_COLOR_HSV_UPPER, dtype=np.uint8),
        )

        # 갈색 마스크 (가죽 농구공)
        brown_mask = cv2.inRange(
            hsv_roi,
            np.array(_BROWN_HSV_LOWER, dtype=np.uint8),
            np.array(_BROWN_HSV_UPPER, dtype=np.uint8),
        )

        # 합산 마스크
        combined_mask = cv2.bitwise_or(orange_mask, brown_mask)
        total_pixels = hsv_roi.shape[0] * hsv_roi.shape[1]

        if total_pixels == 0:
            return 0.0

        color_ratio = float(np.count_nonzero(combined_mask)) / total_pixels

        # 비율 → 점수 매핑 (0.3 이상이면 1.0, 아래면 비례)
        if color_ratio >= _MIN_COLOR_RATIO:
            return 1.0
        return color_ratio / _MIN_COLOR_RATIO

    def _validate_shape(
        self,
        gray_roi: NDArray[np.uint8],
    ) -> float:
        """
        원형도 검증.

        컨투어 분석으로 농구공의 원형 정도를 점수화합니다.

        Args:
            gray_roi: 그레이스케일 ROI

        Returns:
            형태 점수 (0.0 ~ 1.0)
        """
        # 가우시안 블러 + 이진화
        blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
        _, thresh = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return 0.5  # 컨투어 없으면 중립 점수

        # 가장 큰 컨투어 선택
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        perimeter = cv2.arcLength(largest, True)

        if perimeter == 0:
            return 0.5

        # 원형도: 4π × area / perimeter²  (완전한 원 = 1.0)
        circularity = (4.0 * np.pi * area) / (perimeter ** 2)

        if circularity >= BALL_CIRCULARITY_THRESHOLD:
            return 1.0
        return circularity / BALL_CIRCULARITY_THRESHOLD

    # =========================================================================
    # 내부 메서드: 최종 점수 산출
    # =========================================================================

    def _compute_combined_scores(
        self,
        candidates: list[_BallCandidate],
    ) -> list[_BallCandidate]:
        """
        최종 결합 점수 산출 + 정렬.

        가중합: YOLO 70% + 색상 15% + 형태 15%.

        Args:
            candidates: 후보 목록

        Returns:
            점수순 정렬된 후보 목록
        """
        for c in candidates:
            c.combined_score = (
                c.yolo_confidence * 0.70
                + c.color_score * 0.15
                + c.shape_score * 0.15
            )

        # 결합 점수 내림차순 정렬
        candidates.sort(key=lambda c: c.combined_score, reverse=True)
        return candidates

    # =========================================================================
    # 내부 메서드: 후보 → 인터페이스 객체 변환
    # =========================================================================

    def _candidates_to_objects(
        self,
        candidates: list[_BallCandidate],
    ) -> list[InterfaceDetectedObject]:
        """
        후보를 인터페이스 DetectedObject로 변환.

        Args:
            candidates: 후보 목록

        Returns:
            InterfaceDetectedObject 목록
        """
        objects: list[InterfaceDetectedObject] = []

        for idx, c in enumerate(candidates):
            bbox = InterfaceBBox(
                x=c.bbox_x,
                y=c.bbox_y,
                width=c.bbox_w,
                height=c.bbox_h,
                confidence=c.combined_score,
            )

            obj = InterfaceDetectedObject(
                target_type=DetectionTarget.BALL,
                bounding_box=bbox,
                object_id=idx,
                class_name="basketball",
                attributes={
                    "yolo_confidence": c.yolo_confidence,
                    "color_score": c.color_score,
                    "shape_score": c.shape_score,
                    "class_id": c.class_id,
                },
            )
            objects.append(obj)

        return objects

    # =========================================================================
    # 내부 메서드: 멀티뷰 융합
    # =========================================================================

    def _fuse_multi_view(
        self,
        view_candidates: dict[str, list[_BallCandidate]],
        frames: dict[str, np.ndarray],
    ) -> list[DetectedObject]:
        """
        멀티뷰 cross-view 매칭 + 삼각측량.

        각 뷰의 최선 후보를 추출하고, infrastructure의
        MultiViewTriangulator에 위임하여 3D 위치를 복원합니다.

        Args:
            view_candidates: {카메라ID: 후보 목록}
            frames: {카메라ID: BGR 프레임}

        Returns:
            융합된 DetectedObject 목록 (3D 위치 포함)
        """
        fused: list[DetectedObject] = []

        # 각 뷰에서 최선 후보 추출
        best_per_view: dict[str, _BallCandidate] = {}
        for camera_id, candidates in view_candidates.items():
            if candidates:
                best_per_view[camera_id] = candidates[0]

        # 최소 뷰 수 미달 시 2D 결과만 반환
        min_views = (
            self._config.min_triangulation_views
            if self._config is not None
            else _MIN_TRIANGULATION_VIEWS
        )
        if len(best_per_view) < min_views:
            for camera_id, c in best_per_view.items():
                fused.append(DetectedObject(
                    object_type=ObjectType.BALL,
                    confidence=c.combined_score,
                    source=DetectionSource.BALL_DETECTOR,
                    position=Point2D(x=c.center_x, y=c.center_y),
                ))
            return fused

        # 삼각측량기 미주입 시 2D 결과만
        if self._triangulator is None:
            logger.warning("MultiViewTriangulator 미주입: 2D 결과만 반환")
            best_cam = max(
                best_per_view.keys(),
                key=lambda k: best_per_view[k].combined_score,
            )
            c = best_per_view[best_cam]
            fused.append(DetectedObject(
                object_type=ObjectType.BALL,
                confidence=c.combined_score,
                source=DetectionSource.BALL_DETECTOR,
                position=Point2D(x=c.center_x, y=c.center_y),
            ))
            return fused

        # infrastructure 삼각측량기에 관측 전달
        observations: dict[str, NDArray[np.float64]] = {}
        confidences: list[float] = []
        for cam_id, c in best_per_view.items():
            observations[cam_id] = np.array(
                [c.center_x, c.center_y], dtype=np.float64,
            )
            confidences.append(c.combined_score)

        result: TriangulatedPoint = self._triangulator.triangulate(observations)

        if result.is_valid:
            camera_ids = list(best_per_view.keys())
            avg_confidence = float(np.mean(confidences))
            fused.append(DetectedObject(
                object_type=ObjectType.BALL,
                confidence=avg_confidence,
                source=DetectionSource.FUSED,
                position=Point2D(
                    x=best_per_view[camera_ids[0]].center_x,
                    y=best_per_view[camera_ids[0]].center_y,
                ),
                position_3d=Point3D(
                    x=result.x,
                    y=result.y,
                    z=result.z,
                ),
                attributes={
                    "num_views": result.num_views,
                    "source_cameras": list(observations.keys()),
                    "fusion_method": "infrastructure_dlt",
                    "reprojection_error": result.reprojection_error,
                },
            ))
        else:
            # 삼각측량 실패 시 최고 신뢰도 2D 결과
            best_cam = max(
                best_per_view.keys(),
                key=lambda k: best_per_view[k].combined_score,
            )
            c = best_per_view[best_cam]
            fused.append(DetectedObject(
                object_type=ObjectType.BALL,
                confidence=c.combined_score,
                source=DetectionSource.BALL_DETECTOR,
                position=Point2D(x=c.center_x, y=c.center_y),
            ))

        return fused


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 설정
    "BallDetectorConfig",

    # 감지기
    "BallDetector",
]

# 모듈 버전 정보
__version__ = "1.0.0"
