# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline/fusion
파일: detection_fusion.py
설명: 멀티카메라 감지 융합 오케스트레이터
      - CV-BBox 통합 모델 1회 추론 → ball/player/hoop/backboard 동시 감지
      - 결과를 클래스별로 분배하여 각 감지기의 후처리(트래킹/검증) 수행
      - 코트 감지는 고정 카메라 캘리브레이션 (1회 설정)으로 대체
      - GPU 추론 1회로 기존 3회 대비 3배 속도 향상

      데이터 흐름:
        8cam 프레임 (dict[camera_id, NDArray])
          → CV-BBox 통합 추론 1회 (ball=0, player=1, hoop=2, backboard=3)
          → 클래스별 분배 → ball_detector / player_detector / hoop_detector 후처리
          → 코트 좌표 변환: 저장된 호모그래피 매트릭스 사용 (GPU 불필요)
          → SceneDetection (3종 감지 + 캘리브레이션 통합)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - detection/ball_detection/ball_detector.py: BallDetector.detect_multi_view()
    - detection/player_detection/player_detector.py: PlayerDetector.detect_multi_view()
    - detection/hoop_detection/hoop_detector.py: HoopDetector.detect_multi_view()
    - 코트: 수동 캘리브레이션 호모그래피 (set_calibrations → pixel_to_court)
    - shared/dto/detection_dto.py: MultiViewDetectionResult, DetectedObject
    - shared/dto/scene_dto.py: SceneDetection

소비자:
    - engine/pipeline/frame_pipeline.py: 🔴 FRAME 파이프라인 Stage1
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트 (TYPE_CHECKING: 순환참조 방지)
# =============================================================================
if TYPE_CHECKING:
    from detection.ball_detection.ball_detector import BallDetector
    from detection.hoop_detection.hoop_detector import HoopDetector
    from detection.player_detection.player_detector import PlayerDetector

from shared.dto.detection_dto import (
    DetectedObject,
    DetectionSource,
    MultiViewDetectionResult,
    ObjectType,
)
from shared.dto.geometry_dto import BoundingBox, Point2D


# =============================================================================
# 상수
# =============================================================================
_MAX_FUSION_HISTORY: Final[int] = 200

# CV-BBox 통합 모델 클래스 매핑
_CVBBOX_CLS_BALL: Final[int] = 0
_CVBBOX_CLS_PLAYER: Final[int] = 1
_CVBBOX_CLS_HOOP: Final[int] = 2
_CVBBOX_CLS_BACKBOARD: Final[int] = 3

# CV-BBox 기본 경로
_DEFAULT_CVBBOX_PATH: Final[str] = "weights/CV-BBox_v7.engine"


# =============================================================================
# 융합 결과
# =============================================================================
@dataclass(slots=True)
class SceneFusionResult:
    """
    4종 감지기 융합 결과.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        ball_result: 공 감지 멀티뷰 결과 (None = 미실행)
        player_result: 선수 감지 멀티뷰 결과
        court_result: 코트 감지 멀티뷰 결과
        hoop_result: 골대 감지 멀티뷰 결과
        total_fused_objects: 총 융합 객체 수
        processing_time_ms: 총 처리 시간 (ms)
        detector_times_ms: 감지기별 처리 시간
    """

    frame_index: int = 0
    timestamp: float = 0.0
    ball_result: MultiViewDetectionResult | None = None
    player_result: MultiViewDetectionResult | None = None
    court_result: MultiViewDetectionResult | None = None
    hoop_result: MultiViewDetectionResult | None = None
    total_fused_objects: int = 0
    processing_time_ms: float = 0.0
    detector_times_ms: dict[str, float] = field(default_factory=dict)


# =============================================================================
# 감지 융합 오케스트레이터
# =============================================================================
class DetectionFusion:
    """
    멀티카메라 감지 융합 오케스트레이터.

    4개 감지기의 detect_multi_view()를 순차 호출하고 결과를 통합합니다.
    NMS, 삼각측량 등 융합 로직은 각 감지기 내부에 구현되어 있으므로
    이 클래스는 호출 순서 제어 + 결과 수집 + 프로파일링만 담당합니다.

    Attributes:
        _ball_detector: 공 감지기 (DI 주입)
        _player_detector: 선수 감지기 (DI 주입)
        _hoop_detector: 골대 감지기 (DI 주입)
        _calibrations: 카메라별 호모그래피 (코트 감지 대체)
        _history: 융합 이력
        _total_fusions: 총 융합 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_ball_detector",
        "_player_detector",
        "_hoop_detector",
        "_unified_model",
        "_unified_config",
        "_team_tracker",
        "_team_track_results",
        "_calibrations",
        "_history",
        "_total_fusions",
        "_lock",
    )

    def __init__(self) -> None:
        self._ball_detector: BallDetector | None = None
        self._player_detector: PlayerDetector | None = None
        self._hoop_detector: HoopDetector | None = None
        # CV-BBox 통합 모델 (1회 추론으로 ball/player/hoop/backboard 전부 감지)
        self._unified_model: Any = None
        self._unified_config: dict[str, Any] = {}
        # 팀별 분리 트래커 (크로스팀 스위칭 차단)
        self._team_tracker: Any = None
        self._team_track_results: list = []
        # 카메라별 호모그래피 캘리브레이션 (코트 감지 대체)
        self._calibrations: dict[str, np.ndarray] = {}
        self._history: list[SceneFusionResult] = []
        self._total_fusions: int = 0
        self._lock: RLock = RLock()

    # =========================================================================
    # 감지기 주입 (DI)
    # =========================================================================
    def set_detectors(
        self,
        *,
        ball: BallDetector | None = None,
        player: PlayerDetector | None = None,
        hoop: HoopDetector | None = None,
    ) -> None:
        """
        감지기 인스턴스 주입.

        코트 감지는 캘리브레이션 방식으로 대체되어 감지기 주입 불필요.
        set_calibrations()로 호모그래피를 설정합니다.

        Args:
            ball: 공 감지기
            player: 선수 감지기
            hoop: 골대 감지기
        """
        with self._lock:
            if ball is not None:
                self._ball_detector = ball
            if player is not None:
                self._player_detector = player
            if hoop is not None:
                self._hoop_detector = hoop

        _logger.info(
            "감지기 주입: ball=%s, player=%s, hoop=%s",
            ball is not None, player is not None, hoop is not None,
        )

    def load_unified_model(
        self, cv_path: str = _DEFAULT_CVBBOX_PATH,
    ) -> bool:
        """
        CV-BBox 통합 모델 로드.

        지원 포맷 (우선순위):
          1. .engine — TensorRT 엔진 직접 로드 (최고 속도)
          2. .cv — 패키지에서 추출 (engine > pt 순)
          3. .pt — PyTorch 네이티브 (폴백)

        Args:
            cv_path: 모델 파일 경로 (.engine / .cv / .pt)

        Returns:
            로드 성공 여부
        """
        cv_file = Path(cv_path)
        if not cv_file.exists():
            _logger.warning("CV-BBox 모델 없음: %s", cv_file)
            return False

        try:
            from ultralytics import YOLO

            suffix = cv_file.suffix.lower()
            # .engine/.pt 로드 시에도 config/class_map 기본값 필요
            config: dict = {}
            class_map: dict = {}
            tmp_dir: str | None = None

            # .engine 직접 로드 (TensorRT)
            if suffix == ".engine":
                self._unified_model = YOLO(str(cv_file), task="detect")
                _logger.info("CV-BBox TensorRT 엔진 직접 로드: %s", cv_file.name)

            # .pt 직접 로드 (PyTorch)
            elif suffix == ".pt":
                self._unified_model = YOLO(str(cv_file))
                _logger.info("CV-BBox PyTorch 직접 로드: %s", cv_file.name)

            # .cv 패키지 (기존 방식)
            elif suffix == ".cv":
                import tempfile
                import os
                with zipfile.ZipFile(cv_file, "r") as zf:
                    config = json.loads(zf.read("model_config.json"))
                    class_map = json.loads(zf.read("class_map.json"))
                    file_list = zf.namelist()

                    tmp_dir = tempfile.mkdtemp(prefix="cvbbox_")

                    # 동일 디렉토리의 외부 .engine 우선 (TRT 버전 매칭 보장)
                    external_engine = cv_file.parent / (cv_file.stem.split(".")[0] + ".engine")
                    # 예: CV-BBox_v7.0.0.cv → CV-BBox_v7.engine
                    alt_engine = cv_file.parent / (cv_file.stem.split("_v")[0] + "_v"
                        + cv_file.stem.split("_v")[-1].split(".")[0] + ".engine") \
                        if "_v" in cv_file.stem else external_engine

                    if alt_engine.exists():
                        self._unified_model = YOLO(str(alt_engine), task="detect")
                        _logger.info("CV-BBox 외부 엔진 로드 (.cv 메타, 엔진 %s)", alt_engine.name)
                    elif "inference.engine" in file_list:
                        engine_path = os.path.join(tmp_dir, "inference.engine")
                        with open(engine_path, "wb") as f:
                            f.write(zf.read("inference.engine"))
                        self._unified_model = YOLO(engine_path, task="detect")
                        _logger.info("CV-BBox TensorRT 엔진 로드 (.cv 내부)")
                    else:
                        weights_path = os.path.join(tmp_dir, "weights.pt")
                        with open(weights_path, "wb") as f:
                            f.write(zf.read("weights.pt"))
                        self._unified_model = YOLO(weights_path)
                        _logger.info("CV-BBox PyTorch 로드 (.cv)")
            else:
                _logger.warning("지원하지 않는 모델 포맷: %s", suffix)
                return False

            # 워밍업 추론 (모델 완전 로드 보장)
            import numpy as _np
            _dummy = _np.zeros((640, 640, 3), dtype=_np.uint8)
            self._unified_model.predict(_dummy, imgsz=640, conf=0.9, verbose=False)

            self._unified_config = {
                "imgsz": config.get("input_size", 640),
                "class_map": class_map,
                "num_classes": config.get("num_classes", 4),
                "name": config.get("name", "CV-BBox"),
                "version": config.get("version", "unknown"),
            }

            # 워밍업 후 임시 디렉토리 정리 (.cv 경로에서만 생성됨)
            if tmp_dir is not None:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)

            _logger.info(
                "CV-BBox 통합 모델 로드: %s v%s (%d 클래스, imgsz=%d)",
                self._unified_config["name"],
                self._unified_config["version"],
                self._unified_config["num_classes"],
                self._unified_config["imgsz"],
            )
            return True

        except Exception:
            _logger.exception("CV-BBox 모델 로드 실패: %s", cv_file)
            self._unified_model = None
            return False

    def init_team_tracker(self) -> None:
        """
        팀별 분리 트래커 초기화.

        크로스팀 ID 스위칭 방지를 위해 팀별 독립 트래커를 생성합니다.
        detection_fusion 레벨에서 관리하므로 orchestrator 변경 불필요.
        """
        try:
            from detection.player_detection.team_aware_tracker import TeamAwareTracker
            self._team_tracker = TeamAwareTracker()
            self._team_tracker.initialize()
            _logger.info("TeamAwareTracker 초기화 완료")
        except Exception:
            _logger.exception("TeamAwareTracker 초기화 실패 — 팀 분리 트래킹 비활성화")
            self._team_tracker = None

    def set_calibrations(
        self, calibrations: dict[str, np.ndarray],
    ) -> None:
        """
        카메라별 호모그래피 매트릭스 설정 (코트 감지 대체).

        고정 카메라 수동 캘리브레이션으로 저장된 호모그래피를 로드하여
        매 프레임 pixel → court 좌표 변환에 사용합니다.

        Args:
            calibrations: {camera_id: 3x3 호모그래피 매트릭스}
        """
        with self._lock:
            self._calibrations = calibrations
        _logger.info("캘리브레이션 로드: %d대 카메라", len(calibrations))

    def pixel_to_court(
        self, camera_id: str, pixel_point: tuple[float, float],
    ) -> tuple[float, float] | None:
        """
        픽셀 좌표 → 코트 좌표(미터) 변환.

        Args:
            camera_id: 카메라 ID
            pixel_point: (px_x, px_y) 픽셀 좌표

        Returns:
            (court_x, court_y) 코트 좌표 (미터) 또는 None (캘리브레이션 없음)
        """
        H = self._calibrations.get(camera_id)
        if H is None:
            return None
        pt = np.array([[pixel_point]], dtype=np.float64)
        transformed = cv2.perspectiveTransform(pt, H)
        return float(transformed[0, 0, 0]), float(transformed[0, 0, 1])

    # =========================================================================
    # 융합 실행
    # =========================================================================
    def fuse(
        self,
        frames: dict[str, NDArray[np.uint8]],
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> SceneFusionResult:
        """
        8cam 프레임에 대해 4종 감지기 멀티뷰 융합 실행.

        각 감지기의 detect_multi_view()를 순차 호출합니다.
        감지기가 미주입(None)이면 해당 결과는 None으로 스킵합니다.

        Args:
            frames: {camera_id: frame_array} 딕셔너리
            frame_index: 프레임 인덱스
            timestamp: 프레임 타임스탬프

        Returns:
            SceneFusionResult: 4종 통합 결과
        """
        t0 = time.perf_counter()
        detector_times: dict[str, float] = {}
        total_objects = 0

        if self._unified_model is not None:
            # === CV-BBox 통합 추론 (GPU 1회) ===
            ball_result, player_result, hoop_result = self._run_unified(
                frames, frame_index, timestamp, detector_times,
            )
        else:
            # === 폴백: 개별 감지기 (기존 방식) ===
            ball_result = self._run_detector(
                "ball", self._ball_detector, frames, frame_index, timestamp,
                detector_times,
            )
            player_result = self._run_detector(
                "player", self._player_detector, frames, frame_index, timestamp,
                detector_times,
            )
            hoop_result = self._run_detector(
                "hoop", self._hoop_detector, frames, frame_index, timestamp,
                detector_times,
            )

        # 코트: 캘리브레이션 기반 (GPU 추론 없음)
        court_result = None

        # 총 융합 객체 수
        for r in (ball_result, player_result, court_result, hoop_result):
            if r is not None:
                total_objects += r.num_fused_objects

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = SceneFusionResult(
            frame_index=frame_index,
            timestamp=timestamp,
            ball_result=ball_result,
            player_result=player_result,
            court_result=court_result,
            hoop_result=hoop_result,
            total_fused_objects=total_objects,
            processing_time_ms=elapsed_ms,
            detector_times_ms=detector_times,
        )

        # 이력 기록
        with self._lock:
            self._total_fusions += 1
            self._history.append(result)
            if len(self._history) > _MAX_FUSION_HISTORY:
                self._history = self._history[-_MAX_FUSION_HISTORY:]

        return result

    # =========================================================================
    # 내부: 코트 영역 필터
    # =========================================================================
    def _filter_outside_court(
        self,
        objects: list[DetectedObject],
        court_margin_m: float = 2.0,
    ) -> list[DetectedObject]:
        """
        캘리브레이션 기반 코트 영역 밖 감지 제거.

        player의 발 위치(bbox 하단 중앙)를 코트 좌표로 변환하여
        코트 범위 밖이면 제거합니다 (벤치/관중/스태프 필터링).

        FIBA 코트: 28m × 15m + margin

        Args:
            objects: DetectedObject 리스트
            court_margin_m: 코트 경계 여유 (미터) — 사이드라인 밖 약간 허용

        Returns:
            코트 안 감지만 남긴 리스트
        """
        # FIBA 코트 범위 + 마진
        court_x_min = -court_margin_m
        court_x_max = 28.0 + court_margin_m
        court_y_min = -court_margin_m
        court_y_max = 15.0 + court_margin_m

        filtered: list[DetectedObject] = []

        for obj in objects:
            # 발 위치 = bbox 하단 중앙 (코트 위 실제 접지점)
            foot_x = obj.bbox.x + obj.bbox.width / 2.0
            foot_y = obj.bbox.y + obj.bbox.height  # 하단

            # 카메라 ID 추출 (DetectedObject에 camera_id가 있을 때)
            cam_id = getattr(obj, "camera_id", None)
            if cam_id is None:
                # 카메라 정보 없으면 필터 불가 → 유지
                filtered.append(obj)
                continue

            court_pt = self.pixel_to_court(cam_id, (foot_x, foot_y))
            if court_pt is None:
                # 캘리브레이션 없는 카메라 → 유지
                filtered.append(obj)
                continue

            cx, cy = court_pt
            if court_x_min <= cx <= court_x_max and court_y_min <= cy <= court_y_max:
                filtered.append(obj)
            # else: 코트 밖 → 제거

        removed = len(objects) - len(filtered)
        if removed > 0:
            _logger.debug("코트 밖 감지 제거: %d개", removed)

        return filtered

    # =========================================================================
    # 내부: CV-BBox 통합 추론
    # =========================================================================
    def _run_unified(
        self,
        frames: dict[str, NDArray[np.uint8]],
        frame_index: int,
        timestamp: float,
        times: dict[str, float],
    ) -> tuple[
        MultiViewDetectionResult | None,
        MultiViewDetectionResult | None,
        MultiViewDetectionResult | None,
    ]:
        """
        CV-BBox 통합 모델 1회 추론 → 클래스별 분배.

        ball(0), player(1), hoop(2), backboard(3)을 동시 감지하고
        각 감지기의 후처리 파이프라인에 전달합니다.

        Returns:
            (ball_result, player_result, hoop_result) 튜플
        """
        t0 = time.perf_counter()
        imgsz = self._unified_config.get("imgsz", 640)

        # 8카메라 배치 통합 추론 (동일 모델 → 배치 가능, 순차 대비 5~8x ↑)
        ball_objects: list[DetectedObject] = []
        player_objects: list[DetectedObject] = []
        hoop_objects: list[DetectedObject] = []

        cam_ids = list(frames.keys())
        batch_imgs = [frames[c] for c in cam_ids]
        if not batch_imgs:
            times["unified"] = (time.perf_counter() - t0) * 1000.0
            return None, None, None

        try:
            results = self._unified_model.predict(
                batch_imgs,
                imgsz=imgsz,
                conf=0.3,
                verbose=False,
            )
        except Exception as _exc:
            _logger.exception("CV-BBox 배치 추론 실패: err=%s", _exc)
            results = []

        # 결과 길이 불일치 시 경고 (dynamic 배치 엔진 부분 실패 감지)
        if len(results) < len(cam_ids):
            _logger.warning(
                "CV-BBox 배치 결과 누락: %d/%d 카메라 (누락 카메라: %s)",
                len(results), len(cam_ids), cam_ids[len(results):],
            )

        for cam_id, result in zip(cam_ids, results):
            boxes = getattr(result, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue

            # GPU → CPU 일괄 전송 (per-box cpu() 호출 회피)
            xyxy_arr = boxes.xyxy.cpu().numpy()
            conf_arr = boxes.conf.cpu().numpy()
            cls_arr = boxes.cls.cpu().numpy().astype(int)

            for i in range(len(boxes)):
                x1, y1, x2, y2 = [float(v) for v in xyxy_arr[i]]
                conf = float(conf_arr[i])
                cls_id = int(cls_arr[i])

                obj = DetectedObject(
                    object_type=ObjectType.BALL if cls_id == _CVBBOX_CLS_BALL
                    else ObjectType.PLAYER if cls_id == _CVBBOX_CLS_PLAYER
                    else ObjectType.HOOP,
                    bbox=BoundingBox(
                        x=x1, y=y1,
                        width=x2 - x1, height=y2 - y1,
                    ),
                    confidence=conf,
                    source=DetectionSource.YOLO,
                    position=Point2D(
                        x=(x1 + x2) / 2.0,
                        y=(y1 + y2) / 2.0,
                    ),
                    class_id=cls_id,
                    attributes={"camera_id": cam_id},
                )

                if cls_id == _CVBBOX_CLS_BALL:
                    ball_objects.append(obj)
                elif cls_id == _CVBBOX_CLS_PLAYER:
                    player_objects.append(obj)
                elif cls_id in (_CVBBOX_CLS_HOOP, _CVBBOX_CLS_BACKBOARD):
                    hoop_objects.append(obj)

        # 캘리브레이션 기반 코트 영역 필터 (player만 적용)
        if self._calibrations and player_objects:
            player_objects = self._filter_outside_court(player_objects)

        times["unified"] = (time.perf_counter() - t0) * 1000.0

        # 후처리: 각 감지기에 결과 주입 (없으면 raw 결과 직접 반환)
        def _make_raw(objects: list[DetectedObject]) -> MultiViewDetectionResult:
            """감지기 없을 때 raw DetectedObject → MultiViewDetectionResult 변환."""
            return MultiViewDetectionResult(
                frame_index=frame_index,
                fused_objects=objects,
            )

        t1 = time.perf_counter()
        if ball_objects:
            if self._ball_detector is not None:
                try:
                    ball_result = self._ball_detector.process_detections(
                        ball_objects, frames, frame_index,
                    )
                except Exception:
                    ball_result = _make_raw(ball_objects)
            else:
                ball_result = _make_raw(ball_objects)
        else:
            ball_result = None
        times["ball_post"] = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        if player_objects:
            _logger.info("CV-BBox player: %d명 감지 → process_detections 호출", len(player_objects))
            if self._player_detector is not None:
                try:
                    player_result = self._player_detector.process_detections(
                        player_objects, frames, frame_index,
                    )
                except Exception:
                    _logger.exception("process_detections 실패")
                    player_result = _make_raw(player_objects)
            else:
                player_result = _make_raw(player_objects)
        else:
            player_result = None
        times["player_post"] = (time.perf_counter() - t2) * 1000.0

        # TeamAwareTracker 적용 (팀분류 + role보정 + 팀별 분리 트래킹)
        # 5프레임 간격으로 실행 (GPU ReID 모델 사용하므로)
        _TEAM_TRACK_INTERVAL = 5
        t_team = time.perf_counter()
        if self._team_tracker is not None and player_objects and (frame_index % _TEAM_TRACK_INTERVAL == 0):
            try:
                from detection.player_detection.models import _PlayerCandidate
                from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER

                # DetectedObject → _PlayerCandidate 변환
                candidates = []
                # 대표 프레임 (첫 번째 카메라)
                repr_frame = next(iter(frames.values())) if frames else None

                for obj in player_objects:
                    candidates.append(_PlayerCandidate(
                        bbox_x=obj.bbox.x if hasattr(obj.bbox, 'x') else obj.bbox_x,
                        bbox_y=obj.bbox.y if hasattr(obj.bbox, 'y') else obj.bbox_y,
                        bbox_w=obj.bbox.width if hasattr(obj.bbox, 'width') else obj.bbox_w,
                        bbox_h=obj.bbox.height if hasattr(obj.bbox, 'height') else obj.bbox_h,
                        yolo_confidence=obj.confidence,
                        class_id=PLAYER_CLASS_ID_PLAYER,
                    ))

                self._team_track_results = self._team_tracker.update(
                    candidates, frame_index=frame_index, frame=repr_frame,
                )
            except Exception:
                _logger.exception("TeamAwareTracker 업데이트 실패")
                self._team_track_results = []
        else:
            self._team_track_results = []
        times["team_tracker"] = (time.perf_counter() - t_team) * 1000.0

        t3 = time.perf_counter()
        if hoop_objects:
            if self._hoop_detector is not None:
                try:
                    hoop_result = self._hoop_detector.process_detections(
                        hoop_objects, frames, frame_index,
                    )
                except Exception:
                    hoop_result = _make_raw(hoop_objects)
            else:
                hoop_result = _make_raw(hoop_objects)
        else:
            hoop_result = None
        times["hoop_post"] = (time.perf_counter() - t3) * 1000.0

        return ball_result, player_result, hoop_result

    # =========================================================================
    # 내부: 단일 감지기 실행
    # =========================================================================
    def _run_detector(
        self,
        name: str,
        detector: Any,
        frames: dict[str, NDArray[np.uint8]],
        frame_index: int,
        timestamp: float,
        times: dict[str, float],
    ) -> MultiViewDetectionResult | None:
        """단일 감지기 detect_multi_view() 호출 + 프로파일링."""
        if detector is None:
            return None

        t0 = time.perf_counter()
        try:
            result = detector.detect_multi_view(frames, frame_index=frame_index)
            times[name] = (time.perf_counter() - t0) * 1000.0
            return result
        except Exception:
            times[name] = (time.perf_counter() - t0) * 1000.0
            _logger.exception("%s 감지기 멀티뷰 융합 실패", name)
            return None

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_fusions(self) -> int:
        """총 융합 횟수."""
        return self._total_fusions

    @property
    def avg_processing_time_ms(self) -> float:
        """평균 처리 시간 (ms)."""
        with self._lock:
            if not self._history:
                return 0.0
            return sum(r.processing_time_ms for r in self._history) / len(self._history)

    @property
    def team_track_results(self) -> list:
        """최신 TeamAwareTracker 결과 (TeamTrackResult 리스트)."""
        return self._team_track_results

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()
            self._total_fusions = 0

    def __repr__(self) -> str:
        return (
            f"DetectionFusion(fusions={self._total_fusions}, "
            f"avg_ms={self.avg_processing_time_ms:.1f})"
        )


_logger = logging.getLogger(__name__)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "SceneFusionResult",
    "DetectionFusion",
]

__version__ = "1.0.0"
