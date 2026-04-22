# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: player_detector.py
설명: YOLO Primary + 패턴 보조 하이브리드 선수 감지기
      - COURTVIEW_player.pt 자체 학습 모델 기반 추론
      - 피부색/체형 비율 후처리 검증 (패턴 보조)
      - NMS (Non-Maximum Suppression) 중복 제거
      - 멀티뷰 융합 (infrastructure/multi_camera 삼각측량 위임)
      - TensorRT FP16 가속 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/player_constants.py: 클래스 ID, 크기 파라미터
    - shared/dto/detection_dto.py: DetectedObject, DetectionResult
    - shared/dto/geometry_dto.py: BoundingBox, Point2D, Point3D
    - shared/dto/player_dto.py: PlayerRole, Team
    - infrastructure/multi_camera/coordinate_transformer.py: MultiViewTriangulator
    - detection/player_detection/models.py: 설정 및 내부 데이터 클래스
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
# 프로젝트 모듈
# =============================================================================
from shared.constants.player_constants import (
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_STAFF,
    PLAYER_CLASS_ID_UNKNOWN,
    PLAYER_CLASS_NAMES,
    PLAYER_MODEL_NUM_CLASSES,
    TEAM_SKIN_HUE_RANGE,
    TEAM_SKIN_SAT_RANGE,
)
from shared.dto.detection_dto import (
    DetectedObject,
    DetectionResult,
    DetectionSource,
    MultiViewDetectionResult,
    ObjectType,
)
from shared.dto.geometry_dto import BoundingBox, Point3D
from infrastructure.multi_camera.coordinate_transformer import (
    MultiViewTriangulator,
    TriangulatedPoint,
)
from detection.player_detection.models import (
    PlayerDetectorConfig,
    _PlayerCandidate,
)
from detection.player_detection.player_tracker import PlayerTracker
from detection.player_detection.team_classifier import TeamClassifier
from detection.player_detection.jersey_ocr import JerseyOCR
from detection.player_detection.player_id_manager import PlayerIDManager

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# 클래스 ID → ObjectType 매핑
_CLASS_TO_OBJECT_TYPE: Final[dict[int, ObjectType]] = {
    PLAYER_CLASS_ID_PLAYER: ObjectType.PLAYER,
    PLAYER_CLASS_ID_REFEREE: ObjectType.REFEREE,
    PLAYER_CLASS_ID_COACH: ObjectType.COACH,
    PLAYER_CLASS_ID_STAFF: ObjectType.PERSON,
    PLAYER_CLASS_ID_UNKNOWN: ObjectType.PERSON,
}

# 피부색 HSV 범위 (패턴 보조 검증)
_SKIN_HUE_LOW: Final[int] = TEAM_SKIN_HUE_RANGE[0]
_SKIN_HUE_HIGH: Final[int] = TEAM_SKIN_HUE_RANGE[1]
_SKIN_SAT_LOW: Final[int] = TEAM_SKIN_SAT_RANGE[0]
_SKIN_SAT_HIGH: Final[int] = TEAM_SKIN_SAT_RANGE[1]

# 피부색 비율 임계값 (bbox 내 피부색 픽셀 최소 비율)
_MIN_SKIN_RATIO: Final[float] = 0.03
_MAX_SKIN_RATIO: Final[float] = 0.40

# 종횡비 기반 사람 형태 검증 범위
_PERSON_ASPECT_MIN: Final[float] = 0.2   # 매우 세로로 긴 형태
_PERSON_ASPECT_MAX: Final[float] = 0.85  # 앉거나 구부린 형태

# 결과 캐시 최대 크기
_MAX_CACHE_SIZE: Final[int] = 300

# 멀티뷰 삼각측량 최소 뷰 수
_MIN_TRIANGULATION_VIEWS: Final[int] = 2


# =============================================================================
# 선수 감지기
# =============================================================================

class PlayerDetector:
    """
    YOLO Primary + 패턴 보조 선수/심판/코치 감지기.

    COURTVIEW_player.pt 자체 학습 YOLO 모델을 Primary로 사용하고,
    피부색 검증 + 체형 비율 검증을 보조 후처리로 적용합니다.
    멀티뷰 융합(cross-view 매칭 + 삼각측량)을 모듈 내 통합 지원합니다.

    감지 클래스:
        - 0: 선수 (player)
        - 1: 심판 (referee)
        - 2: 코치 (coach)
        - 3: 스태프 (staff)
        - 4: 미식별 (unknown)

    파이프라인:
        1. YOLO 추론 → 사람 후보 추출 (Primary)
        2. NMS 중복 제거
        3. 크기/종횡비 필터링
        4. 피부색 검증 (보조) — 사람인지 오감지 판별
        5. 체형 비율 검증 (보조) — 서있는/움직이는 사람 형태 확인
        6. 최종 점수 산출 + 후보 확정
        7. (멀티뷰) cross-view 매칭 + 삼각측량 → 3D 위치

    사용 예시::

        >>> config = PlayerDetectorConfig(model_path="weights/COURTVIEW_player.pt")
        >>> detector = PlayerDetector()
        >>> detector.initialize(config)
        >>> result = detector.detect(frame, frame_index=0)
    """

    def __init__(self) -> None:
        """감지기 초기화."""
        self._lock = threading.RLock()
        self._config: PlayerDetectorConfig | None = None
        self._model: Any = None  # ultralytics.YOLO 인스턴스
        self._initialized: bool = False
        self._total_detections: int = 0
        self._total_frames: int = 0
        self._detection_cache: deque[DetectionResult] = deque(
            maxlen=_MAX_CACHE_SIZE,
        )
        # 런타임 장치/정밀도 (initialize에서 결정)
        self._effective_device: str = "cpu"
        self._effective_half: bool = False
        # 멀티뷰 삼각측량기 (infrastructure에서 주입)
        self._triangulator: MultiViewTriangulator | None = None
        # 모델 메타데이터 (initialize에서 검증)
        self._model_num_classes: int = 0
        self._model_class_names: dict[int, str] = {}
        # 서브모듈: 추적/분류/식별
        self._player_tracker: PlayerTracker = PlayerTracker()
        self._team_classifier: TeamClassifier = TeamClassifier()
        self._jersey_ocr: JerseyOCR = JerseyOCR()
        # ReID 제거 — digit(등번호) + team(색상)으로 선수 식별 대체
        self._player_id_manager: PlayerIDManager = PlayerIDManager()
        logger.info("PlayerDetector 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_detections(self) -> int:
        """누적 감지 수."""
        return self._total_detections

    @property
    def total_frames(self) -> int:
        """누적 처리 프레임 수."""
        return self._total_frames

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(
        self, config: PlayerDetectorConfig, unified_mode: bool = False,
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
            if self._initialized and getattr(self, "_unified_mode", False):
                logger.info("PlayerDetector unified_mode 보호 — 재초기화 무시")
                return

            if self._initialized:
                logger.warning("이미 초기화된 감지기를 재초기화합니다")
                self.shutdown()

            self._config = config
            self._unified_mode = unified_mode

            # 통합 모드: YOLO 모델 로드 생략 (후처리만 사용)
            if unified_mode:
                self._model = None
                # 서브모듈 초기화 (팀 분류, OCR, 트래킹)
                from detection.player_detection.models import (
                    TeamClassifierConfig,
                    JerseyOCRConfig,
                    PlayerTrackerConfig,
                    PlayerIDManagerConfig,
                )
                self._team_classifier.initialize(TeamClassifierConfig(device="cpu"))
                self._jersey_ocr.initialize(JerseyOCRConfig())
                self._player_tracker.initialize(PlayerTrackerConfig())
                self._player_id_manager.initialize(PlayerIDManagerConfig())
                self._initialized = True
                logger.info(
                    "PlayerDetector 초기화 완료 (통합 모드 — 후처리 전용)",
                )
                return

            model_path = Path(config.model_path)

            if not model_path.exists():
                msg = f"YOLO 모델 파일을 찾을 수 없습니다: {model_path}"
                logger.error(msg)
                raise FileNotFoundError(msg)

            try:
                from ultralytics import YOLO

                self._model = YOLO(str(model_path))

                # 모델 메타데이터 검증
                self._validate_model_metadata(self._model, model_path.name)

                # GPU 장치 설정 + FP16
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

                self._initialized = True
                logger.info(
                    "PlayerDetector 초기화 완료: model=%s, device=%s, fp16=%s",
                    model_path.name,
                    self._effective_device,
                    self._effective_half,
                )
            except Exception as exc:
                logger.error("YOLO 모델 로드 실패: %s", exc)
                raise RuntimeError(
                    f"YOLO 모델 로드 실패: {exc}"
                ) from exc

    def shutdown(self) -> None:
        """감지기 종료 및 리소스 해제."""
        with self._lock:
            self._model = None
            self._initialized = False
            self._detection_cache.clear()
            logger.info(
                "PlayerDetector 종료: 총 프레임=%d, 총 감지=%d",
                self._total_frames,
                self._total_detections,
            )

    def process_detections(
        self,
        detections: list,
        frames: dict[str, np.ndarray],
        frame_index: int = 0,
    ) -> MultiViewDetectionResult:
        """
        CV-BBox 통합 추론 결과에서 선수 감지 후처리.

        외부에서 이미 추론된 DetectedObject 리스트를 받아
        크기 필터링 + 팀 분류 + 등번호 OCR + 트래킹을 수행합니다.

        Args:
            detections: DetectedObject 리스트 (player 클래스만)
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

        # DetectedObject → _PlayerCandidate 변환
        candidates_by_cam: dict[str, list[_PlayerCandidate]] = {}

        for det in detections:
            # camera_id는 _run_unified에서 attributes에 주입함
            cam_id = (
                getattr(det, "camera_id", None)
                or (det.attributes.get("camera_id") if hasattr(det, "attributes") and det.attributes else None)
                or "cam_0"
            )
            # DetectedObject.bbox는 BoundingBox(x, y, width, height) 객체
            bbox = det.bbox
            candidate = _PlayerCandidate(
                bbox_x=bbox.x,
                bbox_y=bbox.y,
                bbox_w=bbox.width,
                bbox_h=bbox.height,
                yolo_confidence=det.confidence,
                # CV-BBox player=1이지만 jersey_ocr는 PLAYER_CLASS_ID_PLAYER=0 체크
                class_id=PLAYER_CLASS_ID_PLAYER,
                camera_id=cam_id,
                frame_index=frame_index,
            )
            candidates_by_cam.setdefault(cam_id, []).append(candidate)

        all_objects: list[DtoDetectedObject] = []

        # 팀 분류: 30프레임 (≈1초) 간격, OCR: 30프레임 간격.
        # team은 교체/TO 전에는 변하지 않으므로 자주 할 필요 없음.
        # 5프레임 간격 쓰면 HSV K-Means가 340ms 스파이크 유발 (측정 완료).
        _CLASSIFY_INTERVAL = 30
        _OCR_INTERVAL = 30
        run_classify = (frame_index % _CLASSIFY_INTERVAL == 0)
        run_ocr = (frame_index % _OCR_INTERVAL == 0)

        # --- Team 분류: 카메라별 (단일 프레임 batch) ---
        team_results_by_cam: dict[str, list[tuple[str, float]]] = {}
        if run_classify and self._team_classifier.is_initialized:
            for cam_id, candidates in candidates_by_cam.items():
                frame = frames.get(cam_id)
                if frame is None:
                    continue
                if not self._team_classifier.is_calibrated:
                    self._team_classifier.calibrate(candidates, frame)
                batch = self._team_classifier.classify_batch(candidates, frame)
                team_results_by_cam[cam_id] = [(t.value, c) for t, c in batch]

        # --- Jersey OCR: 전 카메라 후보를 1회 배치 추론 ---
        # candidates_by_cam[cam_id] = [cand,...] 순서를 유지하며 (cand, frame) 쌍 생성
        jersey_results_by_cam: dict[str, list[tuple[int | None, float]]] = {}
        if run_ocr and self._jersey_ocr.is_initialized:
            all_pairs: list = []
            all_track_ids: list = []
            cam_counts: list[tuple[str, int]] = []  # cam_id → this cam's candidate 수
            # tid 구성: frame_index * 1_000_000 + cam_idx * 100 + i → 카메라 간 충돌 방지
            for cam_idx, (cam_id, candidates) in enumerate(candidates_by_cam.items()):
                frame = frames.get(cam_id)
                if frame is None:
                    cam_counts.append((cam_id, 0))
                    continue
                for i, cand in enumerate(candidates):
                    all_pairs.append((cand, frame))
                    tid = frame_index * 1_000_000 + cam_idx * 100 + i
                    all_track_ids.append(tid)
                cam_counts.append((cam_id, len(candidates)))

            regions = []
            if all_pairs:
                try:
                    regions = self._jersey_ocr.recognize_batch_multi_frame(
                        all_pairs, track_ids=all_track_ids,
                    )
                except Exception as _ocr_err:
                    logger.error("OCR 배치 에러: %s", _ocr_err)
                    regions = [None] * len(all_pairs)

            # 결과 분배 (cam 순서 + 카메라별 후보 순서 유지)
            pos = 0
            for cam_id, count in cam_counts:
                sub: list[tuple[int | None, float]] = []
                for i in range(count):
                    r = regions[pos + i] if pos + i < len(regions) else None
                    if r is not None:
                        sub.append((r.number, r.confidence))
                        # player_id_manager 업데이트
                        try:
                            if (self._player_id_manager.is_initialized
                                and r.number is not None):
                                self._player_id_manager.update_player(
                                    track_id=all_track_ids[pos + i],
                                    jersey_number=r.number,
                                    jersey_conf=r.confidence,
                                    frame_index=frame_index,
                                )
                        except Exception as _pm_err:
                            logger.debug("player_id_manager 업데이트 실패: %s", _pm_err)
                    else:
                        sub.append((None, 0.0))
                jersey_results_by_cam[cam_id] = sub
                pos += count

        # --- DTO 변환 (카메라별 candidates 순서대로) ---
        for cam_id, candidates in candidates_by_cam.items():
            team_results = team_results_by_cam.get(cam_id, [])
            jersey_results = jersey_results_by_cam.get(cam_id, [])
            for idx, cand in enumerate(candidates):
                attributes: dict = {"camera_id": cam_id}
                if idx < len(team_results):
                    team_str, team_conf = team_results[idx]
                    attributes["team"] = team_str
                    attributes["team_confidence"] = team_conf
                if idx < len(jersey_results):
                    jnum, jconf = jersey_results[idx]
                    if jnum is not None:
                        attributes["jersey_number"] = jnum
                        attributes["jersey_conf"] = jconf
                obj = DtoDetectedObject(
                    object_type=ObjectType.PLAYER,
                    bbox=BoundingBox(
                        x=cand.bbox_x,
                        y=cand.bbox_y,
                        width=cand.bbox_w,
                        height=cand.bbox_h,
                    ),
                    confidence=cand.yolo_confidence,
                    class_id=cand.class_id,
                    attributes=attributes,
                )
                all_objects.append(obj)

        return MultiViewDetectionResult(
            fused_objects=all_objects,
            frame_index=frame_index,
        )

    def reset(self) -> None:
        """통계 및 캐시 초기화 (모델 유지)."""
        with self._lock:
            self._total_detections = 0
            self._total_frames = 0
            self._detection_cache.clear()

    # =========================================================================
    # 모델 메타데이터 검증
    # =========================================================================

    def _validate_model_metadata(self, model: Any, model_name: str) -> None:
        """
        COURTVIEW 자체 학습 YOLO 모델의 클래스 수/이름을 검증.

        Args:
            model: ultralytics.YOLO 인스턴스
            model_name: 모델 파일명 (로깅용)
        """
        # model.names: {0: 'player', 1: 'referee', 2: 'coach', 3: 'staff', 4: 'unknown'}
        model_names: dict[int, str] = getattr(model, "names", {})
        num_classes = len(model_names)

        self._model_num_classes = num_classes
        self._model_class_names = dict(model_names)

        # 클래스 수 검증 (COURTVIEW 5-class)
        if num_classes != PLAYER_MODEL_NUM_CLASSES:
            logger.warning(
                "모델 클래스 수 불일치: 기대=%d, 실제=%d (%s)",
                PLAYER_MODEL_NUM_CLASSES,
                num_classes,
                model_name,
            )

        # 클래스 이름 교차 검증
        expected = PLAYER_CLASS_NAMES
        mismatches: list[str] = []
        for cls_id, expected_name in expected.items():
            actual_name = model_names.get(cls_id, "")
            if actual_name.lower() != expected_name.lower():
                mismatches.append(
                    f"class {cls_id}: 기대='{expected_name}', 실제='{actual_name}'"
                )

        if mismatches:
            logger.warning(
                "COURTVIEW 모델 클래스 이름 불일치 %d건: %s",
                len(mismatches),
                "; ".join(mismatches),
            )

        logger.info(
            "COURTVIEW 자체 모델 로드: %s (%d 클래스: %s)",
            model_name,
            num_classes,
            ", ".join(f"{k}={v}" for k, v in model_names.items()),
        )

    @property
    def model_num_classes(self) -> int:
        """로드된 모델의 클래스 수."""
        return self._model_num_classes

    @property
    def model_class_names(self) -> dict[int, str]:
        """로드된 모델의 클래스 이름 매핑."""
        return dict(self._model_class_names)

    # =========================================================================
    # 멀티뷰 삼각측량기 주입
    # =========================================================================

    def set_triangulator(
        self,
        triangulator: MultiViewTriangulator | None,
    ) -> None:
        """
        멀티뷰 삼각측량기 주입.

        Args:
            triangulator: 삼각측량기 (None이면 멀티뷰 비활성화)
        """
        with self._lock:
            self._triangulator = triangulator
            logger.info(
                "PlayerDetector 삼각측량기 %s",
                "주입됨" if triangulator else "제거됨",
            )

    # =========================================================================
    # 단일 프레임 감지
    # =========================================================================

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        camera_id: str = "cam_0",
    ) -> DetectionResult:
        """
        단일 프레임에서 선수/심판/코치 감지.

        Args:
            frame: BGR 입력 이미지
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID

        Returns:
            DetectionResult (감지된 객체 목록)
        """
        if not self._initialized or self._config is None:
            return DetectionResult(
                objects=[],
                frame_index=frame_index,
                source=DetectionSource.YOLO,
            )

        start_time = time.monotonic()

        with self._lock:
            config = self._config

            # 1. YOLO 추론 → 후보 추출
            candidates = self._yolo_inference(frame, camera_id, frame_index)

            # 2. 크기/종횡비 필터링
            h, w = frame.shape[:2]
            candidates = self._filter_by_size(candidates, w, h, config)

            # 3. 패턴 보조 검증 (피부색 + 체형)
            if config.enable_color_validation or config.enable_shape_validation:
                candidates = self._pattern_validation(
                    candidates, frame, config,
                )

            # 4. 최종 점수 산출
            candidates = self._compute_combined_scores(candidates, config)

            # 5. 최대 감지 수 제한
            candidates.sort(key=lambda c: c.combined_score, reverse=True)
            candidates = candidates[:config.max_detections]

            # 6. DetectedObject 변환
            objects = self._candidates_to_objects(candidates)

            self._total_frames += 1
            self._total_detections += len(objects)

            elapsed_ms = (time.monotonic() - start_time) * 1000.0

            result = DetectionResult(
                objects=objects,
                frame_index=frame_index,
                source=DetectionSource.YOLO,
                processing_time_ms=elapsed_ms,
            )

            self._detection_cache.append(result)
            return result

    # =========================================================================
    # 멀티뷰 감지
    # =========================================================================

    def detect_multi_view(
        self,
        frames: dict[str, np.ndarray],
        frame_index: int = 0,
    ) -> MultiViewDetectionResult:
        """
        멀티뷰 선수 감지 + 삼각측량.

        Args:
            frames: 카메라 ID → BGR 이미지 매핑
            frame_index: 프레임 인덱스

        Returns:
            MultiViewDetectionResult
        """
        start_time = time.monotonic()

        # 각 카메라별 독립 감지
        per_view: dict[str, DetectionResult] = {}
        all_candidates: dict[str, list[_PlayerCandidate]] = {}

        for cam_id, frame in frames.items():
            result = self.detect(frame, frame_index, cam_id)
            per_view[cam_id] = result

            # 내부 후보 재구축 (3D 융합용)
            cam_candidates: list[_PlayerCandidate] = []
            for obj in result.objects:
                candidate = _PlayerCandidate(
                    bbox_x=obj.bbox.x,
                    bbox_y=obj.bbox.y,
                    bbox_w=obj.bbox.width,
                    bbox_h=obj.bbox.height,
                    yolo_confidence=obj.confidence,
                    class_id=self._object_type_to_class_id(obj.object_type),
                    combined_score=obj.confidence,
                    camera_id=cam_id,
                    frame_index=frame_index,
                )
                cam_candidates.append(candidate)
            all_candidates[cam_id] = cam_candidates

        # 3D 융합 (삼각측량기 주입 시)
        fused_objects: list[DetectedObject] = []
        if self._triangulator is not None and len(per_view) >= 2:
            fused_objects = self._fuse_multi_view(
                all_candidates, per_view, frame_index,
            )

        # 서브모듈 체인: 추적 → 팀분류 → 등번호 → ReID → 최종 ID
        self._post_process_players(
            fused_objects, all_candidates, frames, frame_index,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000.0

        return MultiViewDetectionResult(
            view_results=per_view,
            fused_objects=fused_objects,
            frame_index=frame_index,
            processing_time_ms=elapsed_ms,
        )

    # =========================================================================
    # 내부 메서드 — YOLO 추론
    # =========================================================================

    def _yolo_inference(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_index: int,
    ) -> list[_PlayerCandidate]:
        """
        YOLO 모델 추론으로 사람 후보 추출.

        Args:
            frame: BGR 이미지
            camera_id: 카메라 ID
            frame_index: 프레임 인덱스

        Returns:
            _PlayerCandidate 목록
        """
        if self._model is None or self._config is None:
            return []

        config = self._config

        results = self._model.predict(
            frame,
            device=self._effective_device,
            imgsz=config.input_size,
            conf=config.confidence_threshold,
            iou=config.nms_iou_threshold,
            half=self._effective_half,
            verbose=False,
            max_det=config.max_detections,
        )

        candidates: list[_PlayerCandidate] = []

        if not results or len(results) == 0:
            return candidates

        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return candidates

        boxes = result.boxes

        for i in range(len(boxes)):
            # YOLO 출력: xyxy 형식
            xyxy = boxes.xyxy[i].cpu().numpy().flatten()
            if len(xyxy) < 4:
                continue

            x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
            conf = float(boxes.conf[i].cpu().numpy())
            cls_id = int(boxes.cls[i].cpu().numpy())

            # 클래스 ID 검증 (COURTVIEW 5-class: 0~4)
            if cls_id not in _CLASS_TO_OBJECT_TYPE:
                continue

            candidate = _PlayerCandidate(
                bbox_x=x1,
                bbox_y=y1,
                bbox_w=x2 - x1,
                bbox_h=y2 - y1,
                yolo_confidence=conf,
                class_id=cls_id,
                camera_id=camera_id,
                frame_index=frame_index,
            )
            candidates.append(candidate)

        return candidates

    # =========================================================================
    # 내부 메서드 — 크기/종횡비 필터링
    # =========================================================================

    def _filter_by_size(
        self,
        candidates: list[_PlayerCandidate],
        frame_w: int,
        frame_h: int,
        config: PlayerDetectorConfig,
    ) -> list[_PlayerCandidate]:
        """
        크기/종횡비 기반 필터링.

        Args:
            candidates: 후보 목록
            frame_w: 프레임 너비
            frame_h: 프레임 높이
            config: 설정

        Returns:
            필터링된 후보 목록
        """
        frame_area = frame_w * frame_h
        if frame_area <= 0:
            return []

        filtered: list[_PlayerCandidate] = []
        min_area = frame_area * config.min_size_ratio
        max_area = frame_area * config.max_size_ratio

        for c in candidates:
            area = c.area
            if area < min_area or area > max_area:
                continue

            ar = c.aspect_ratio
            if ar < config.min_aspect_ratio or ar > config.max_aspect_ratio:
                continue

            filtered.append(c)

        return filtered

    # =========================================================================
    # 내부 메서드 — 패턴 보조 검증
    # =========================================================================

    def _pattern_validation(
        self,
        candidates: list[_PlayerCandidate],
        frame: np.ndarray,
        config: PlayerDetectorConfig,
    ) -> list[_PlayerCandidate]:
        """
        패턴 보조 검증 (피부색 + 체형).

        높은 신뢰도 후보는 검증 생략.

        Args:
            candidates: 후보 목록
            frame: BGR 이미지
            config: 설정

        Returns:
            검증된 후보 목록
        """
        h, w = frame.shape[:2]
        validated: list[_PlayerCandidate] = []

        for c in candidates:
            # 높은 신뢰도 → 검증 생략 (빠른 경로)
            if c.yolo_confidence >= config.high_confidence_threshold:
                c.color_score = 1.0
                c.shape_score = 1.0
                validated.append(c)
                continue

            # 색상 검증 (피부색 존재 여부)
            color_ok = True
            if config.enable_color_validation:
                color_score = self._validate_skin_presence(frame, c, w, h)
                c.color_score = color_score
                color_ok = color_score > 0.0

            # 체형 검증 (종횡비 + 세로 길이)
            shape_ok = True
            if config.enable_shape_validation:
                shape_score = self._validate_body_shape(c, h)
                c.shape_score = shape_score
                shape_ok = shape_score > 0.0

            if color_ok and shape_ok:
                validated.append(c)

        return validated

    def _validate_skin_presence(
        self,
        frame: np.ndarray,
        candidate: _PlayerCandidate,
        frame_w: int,
        frame_h: int,
    ) -> float:
        """
        피부색 존재 여부 검증.

        사람 bbox 상단 20% (머리/목 영역)에서 피부색 픽셀 비율 확인.

        Args:
            frame: BGR 이미지
            candidate: 후보
            frame_w: 프레임 너비
            frame_h: 프레임 높이

        Returns:
            피부색 점수 (0.0~1.0)
        """
        x1 = max(0, int(candidate.bbox_x))
        y1 = max(0, int(candidate.bbox_y))
        x2 = min(frame_w, int(candidate.bbox_x + candidate.bbox_w))
        # 상단 25% (머리/목 영역)
        head_h = max(1, int(candidate.bbox_h * 0.25))
        y2 = min(frame_h, y1 + head_h)

        if x2 - x1 < 5 or y2 - y1 < 5:
            return 0.0

        roi = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 피부색 범위 마스킹
        skin_mask = cv2.inRange(
            hsv,
            np.array([_SKIN_HUE_LOW, _SKIN_SAT_LOW, 60], dtype=np.uint8),
            np.array([_SKIN_HUE_HIGH, _SKIN_SAT_HIGH, 255], dtype=np.uint8),
        )

        total_pixels = roi.shape[0] * roi.shape[1]
        if total_pixels == 0:
            return 0.0

        skin_ratio = float(np.count_nonzero(skin_mask)) / total_pixels

        if skin_ratio < _MIN_SKIN_RATIO:
            return 0.0
        if skin_ratio > _MAX_SKIN_RATIO:
            # 과도한 피부색 → 코트 바닥 오감지 가능
            return 0.3

        # 적정 범위 → 정규화 (0.03~0.40 → 0.0~1.0)
        return min(1.0, (skin_ratio - _MIN_SKIN_RATIO) / (_MAX_SKIN_RATIO - _MIN_SKIN_RATIO))

    def _validate_body_shape(
        self,
        candidate: _PlayerCandidate,
        frame_h: int,
    ) -> float:
        """
        체형 비율 검증.

        농구 선수는 세로로 긴 형태 (aspect_ratio < 1.0).
        최소 높이 제한으로 너무 작은 감지 제거.

        Args:
            candidate: 후보
            frame_h: 프레임 높이

        Returns:
            체형 점수 (0.0~1.0)
        """
        ar = candidate.aspect_ratio

        if ar < _PERSON_ASPECT_MIN or ar > _PERSON_ASPECT_MAX:
            return 0.0

        # 높이 비율 검증 (프레임 높이 대비)
        height_ratio = candidate.bbox_h / max(1, frame_h)

        if height_ratio < 0.05:  # 너무 작은 감지
            return 0.0

        # 이상적 종횡비: 0.35~0.55 (서있는 사람)
        ideal_center = 0.45
        ideal_range = 0.15
        ar_score = max(0.0, 1.0 - abs(ar - ideal_center) / ideal_range)

        # 높이 점수: 클수록 양호 (0.1~0.6 → 0.0~1.0)
        height_score = min(1.0, max(0.0, (height_ratio - 0.05) / 0.5))

        return 0.6 * ar_score + 0.4 * height_score

    # =========================================================================
    # 내부 메서드 — 점수 산출 및 변환
    # =========================================================================

    def _compute_combined_scores(
        self,
        candidates: list[_PlayerCandidate],
        config: PlayerDetectorConfig,
    ) -> list[_PlayerCandidate]:
        """
        최종 복합 점수 산출.

        YOLO 신뢰도 Primary (70%) + 패턴 보조 (30%) 가중 합산.

        Args:
            candidates: 후보 목록
            config: 설정

        Returns:
            점수 산출된 후보 목록
        """
        yolo_weight = 0.7
        pattern_weight = 0.3

        for c in candidates:
            pattern_avg = (c.color_score + c.shape_score) / 2.0
            c.combined_score = (
                yolo_weight * c.yolo_confidence
                + pattern_weight * pattern_avg
            )

        return candidates

    def _candidates_to_objects(
        self,
        candidates: list[_PlayerCandidate],
    ) -> list[DetectedObject]:
        """
        _PlayerCandidate → DetectedObject 변환.

        Args:
            candidates: 후보 목록

        Returns:
            DetectedObject 목록
        """
        objects: list[DetectedObject] = []

        for c in candidates:
            obj_type = _CLASS_TO_OBJECT_TYPE.get(
                c.class_id, ObjectType.PERSON,
            )
            class_name = PLAYER_CLASS_NAMES.get(c.class_id, "unknown")

            bbox = BoundingBox(
                x=c.bbox_x,
                y=c.bbox_y,
                width=c.bbox_w,
                height=c.bbox_h,
            )

            obj = DetectedObject(
                object_type=obj_type,
                bbox=bbox,
                confidence=c.combined_score,
                class_id=c.class_id,
                source=DetectionSource.YOLO,
                attributes={"class_name": class_name},
            )
            objects.append(obj)

        return objects

    # =========================================================================
    # 내부 메서드 — 멀티뷰 융합
    # =========================================================================

    def _fuse_multi_view(
        self,
        all_candidates: dict[str, list[_PlayerCandidate]],
        per_view: dict[str, DetectionResult],
        frame_index: int,
    ) -> list[DetectedObject]:
        """
        멀티뷰 감지 결과 융합.

        각 뷰의 감지 결과를 cross-view 매칭하고,
        삼각측량으로 3D 위치를 추정합니다.

        Args:
            all_candidates: 카메라별 후보 목록
            per_view: 카메라별 감지 결과
            frame_index: 프레임 인덱스

        Returns:
            3D 위치가 포함된 융합 DetectedObject 목록
        """
        if self._triangulator is None:
            return []

        fused: list[DetectedObject] = []
        camera_ids = list(all_candidates.keys())

        if len(camera_ids) < _MIN_TRIANGULATION_VIEWS:
            return fused

        # 기준 뷰: 첫 번째 카메라
        ref_cam = camera_ids[0]
        ref_candidates = all_candidates[ref_cam]

        for ref_c in ref_candidates:
            # 각 뷰에서 가장 유사한 후보 찾기 (IoU 기반)
            observations: dict[str, NDArray[np.float64]] = {
                ref_cam: np.array(
                    [ref_c.center_x, ref_c.center_y],
                    dtype=np.float64,
                ),
            }

            for other_cam in camera_ids[1:]:
                best_match = self._find_best_match(
                    ref_c, all_candidates[other_cam],
                )
                if best_match is not None:
                    observations[other_cam] = np.array(
                        [best_match.center_x, best_match.center_y],
                        dtype=np.float64,
                    )

            # 2뷰 이상이면 삼각측량
            if len(observations) >= _MIN_TRIANGULATION_VIEWS:
                tri_result: TriangulatedPoint = self._triangulator.triangulate(
                    observations,
                )

                if tri_result.is_valid:
                    obj_type = _CLASS_TO_OBJECT_TYPE.get(
                        ref_c.class_id, ObjectType.PERSON,
                    )
                    class_name = PLAYER_CLASS_NAMES.get(
                        ref_c.class_id, "unknown",
                    )

                    bbox = BoundingBox(
                        x=ref_c.bbox_x,
                        y=ref_c.bbox_y,
                        width=ref_c.bbox_w,
                        height=ref_c.bbox_h,
                    )

                    position_3d = Point3D(
                        x=tri_result.x,
                        y=tri_result.y,
                        z=tri_result.z,
                    )

                    obj = DetectedObject(
                        object_type=obj_type,
                        bbox=bbox,
                        confidence=ref_c.combined_score,
                        class_id=ref_c.class_id,
                        source=DetectionSource.FUSED,
                        position_3d=position_3d,
                        attributes={"class_name": class_name},
                    )
                    fused.append(obj)

        return fused

    def _find_best_match(
        self,
        ref: _PlayerCandidate,
        candidates: list[_PlayerCandidate],
    ) -> _PlayerCandidate | None:
        """
        기준 후보와 가장 유사한 후보 찾기.

        크기 유사성 + 같은 클래스 조건으로 cross-view 매칭.

        Args:
            ref: 기준 후보
            candidates: 비교 대상 목록

        Returns:
            최적 매칭 또는 None
        """
        best: _PlayerCandidate | None = None
        best_score = -1.0

        ref_area = ref.area
        if ref_area <= 0:
            return None

        for c in candidates:
            # 같은 클래스만 매칭
            if c.class_id != ref.class_id:
                continue

            # 크기 유사성 (면적 비율)
            c_area = c.area
            if c_area <= 0:
                continue
            area_ratio = min(ref_area, c_area) / max(ref_area, c_area)

            # 신뢰도 가중
            score = 0.6 * area_ratio + 0.4 * c.yolo_confidence

            if score > best_score:
                best_score = score
                best = c

        # 최소 유사성 임계값
        if best_score < 0.3:
            return None

        return best

    # =========================================================================
    # 유틸리티
    # =========================================================================

    @staticmethod
    def _object_type_to_class_id(obj_type: ObjectType) -> int:
        """ObjectType → 클래스 ID 역변환."""
        for cls_id, ot in _CLASS_TO_OBJECT_TYPE.items():
            if ot == obj_type:
                return cls_id
        return PLAYER_CLASS_ID_UNKNOWN

    def get_candidates(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        camera_id: str = "cam_0",
    ) -> list[_PlayerCandidate]:
        """
        내부 후보 목록 반환 (다른 서브모듈용).

        team_classifier, jersey_ocr가 호출하여
        이미 감지된 후보의 bbox 정보를 활용합니다.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID

        Returns:
            _PlayerCandidate 목록
        """
        if not self._initialized or self._config is None:
            return []

        with self._lock:
            config = self._config
            candidates = self._yolo_inference(frame, camera_id, frame_index)

            h, w = frame.shape[:2]
            candidates = self._filter_by_size(candidates, w, h, config)

            if config.enable_color_validation or config.enable_shape_validation:
                candidates = self._pattern_validation(
                    candidates, frame, config,
                )

            candidates = self._compute_combined_scores(candidates, config)
            candidates.sort(key=lambda c: c.combined_score, reverse=True)
            return candidates[:config.max_detections]

    def __repr__(self) -> str:
        return (
            f"PlayerDetector(initialized={self._initialized}, "
            f"classes={self._model_num_classes}, "
            f"frames={self._total_frames}, "
            f"detections={self._total_detections})"
        )


    # =========================================================================
    # 서브모듈 체인: 추적 → 팀분류 → 등번호 → ReID → 최종 ID
    # =========================================================================
    def _post_process_players(
        self,
        fused_objects: list[DetectedObject],
        all_candidates: dict[str, list[_PlayerCandidate]],
        frames: dict[str, np.ndarray],
        frame_index: int,
    ) -> None:
        """감지 후 서브모듈 체인 실행 (추적/분류/식별)."""
        if not fused_objects:
            return

        # 대표 프레임 (첫 번째 카메라)
        first_cam = next(iter(frames), None)
        frame = frames[first_cam] if first_cam else None
        if frame is None:
            return

        # 후보 리스트 통합
        flat_candidates = [
            c for cam_list in all_candidates.values() for c in cam_list
        ]

        # 1. 트래커 갱신
        tracks = []
        try:
            tracks = self._player_tracker.update(
                flat_candidates, frame_index,
            )
        except Exception:
            logger.debug("PlayerTracker 갱신 오류")

        # 2. 각 트랙별 팀/등번호/최종ID
        for track in tracks:
            # _TrackState (detection/player_detection/models.py) 필드 직접 접근
            candidate = _PlayerCandidate(
                bbox_x=track.bbox_x,
                bbox_y=track.bbox_y,
                bbox_w=track.bbox_w,
                bbox_h=track.bbox_h,
                yolo_confidence=track.confidence,
                combined_score=track.confidence,
                class_id=track.class_id,
                camera_id=first_cam or "",
                frame_index=frame_index,
            )

            # 팀 분류
            team = None
            try:
                team, _ = self._team_classifier.classify(candidate, frame)
            except Exception:
                pass

            # 등번호 OCR
            jersey_number = None
            jersey_conf = 0.0
            try:
                jersey_region = self._jersey_ocr.recognize(
                    candidate, frame, track_id=getattr(track, "track_id", None),
                )
                jersey_number = getattr(jersey_region, "number", None)
                jersey_conf = getattr(jersey_region, "confidence", 0.0)
            except Exception:
                pass

            # 최종 ID 융합 (OCR + Tracking)
            try:
                self._player_id_manager.update_player(
                    track_id=getattr(track, "track_id", 0),
                    jersey_number=jersey_number,
                    jersey_conf=jersey_conf,
                    team=team,
                    frame_index=frame_index,
                )
            except Exception:
                pass


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "PlayerDetector",
    "PlayerDetectorConfig",
]

__version__: str = "1.0.0"
