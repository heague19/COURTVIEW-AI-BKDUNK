# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: jersey_ocr.py
설명: 등번호 OCR 인식기
      - 등번호 ROI 추출 + 전처리 (이진화, 정규화)
      - YOLO 숫자 감지 (COURTVIEW_digit.pt, YOLOv8n, 10-class 0~9)
      - 형태학적 분석 폴백 (모델 미존재 시)
      - 다중 프레임 관측 → 투표 기반 등번호 확정
      - 멀티뷰 투표 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ocr_constants.py: 신뢰도, ROI, 전처리, 후처리 상수
    - shared/constants/player_constants.py: 클래스 ID
    - detection/player_detection/models.py: JerseyOCRConfig, _PlayerCandidate, _JerseyRegion
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import re
import threading
from collections import defaultdict, deque
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
from shared.constants.ocr_constants import (
    ADAPTIVE_BINARIZATION_BLOCK_SIZE,
    ADAPTIVE_BINARIZATION_CONSTANT,
    JERSEY_HISTORY_MAX_FRAMES,
    JERSEY_MAX_DIGITS,
    JERSEY_NUMBER_MAX,
    JERSEY_NUMBER_MIN,
    JERSEY_NUMBER_PATTERN,
    JERSEY_VOTING_WINDOW,
    OCR_INPUT_STANDARD_HEIGHT,
)
from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER
from detection.player_detection.models import (
    JerseyOCRConfig,
    _JerseyRegion,
    _PlayerCandidate,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# 등번호 정규식 컴파일 (모듈 레벨 캐시)
_JERSEY_REGEX: Final[re.Pattern[str]] = re.compile(JERSEY_NUMBER_PATTERN)

# YOLO 모델 자동 감지 glob 패턴 (최신 버전 우선, reverse=True)
# CV-Digit_v1/v2/v3/v4/v4.1 → CV-Digit_v99까지 자동 업그레이드
_DIGIT_MODEL_GLOB: Final[str] = "CV-Digit_v*.cv"
_CLS_MODEL_GLOB: Final[str] = "CV-JerseyCls_v*.cv"

# 학습 디렉토리 폴백 (weights/ 미존재 시)
_DEFAULT_CLS_PT_PATH: Final[str] = "D:/SPOIN/training/runs/jersey_cls_v1/weights/best.pt"

# YOLO 숫자 감지 입력 크기
_DIGIT_IMGSZ: Final[int] = 224
_CLS_IMGSZ: Final[int] = 64

# YOLO 숫자 감지 최소 신뢰도
_DIGIT_MIN_CONFIDENCE: Final[float] = 0.3

# OCR 이력 최대 저장 수 (인물당)
_MAX_HISTORY_PER_PERSON: Final[int] = JERSEY_HISTORY_MAX_FRAMES

# 투표 윈도우
_VOTING_WINDOW: Final[int] = JERSEY_VOTING_WINDOW


# =============================================================================
# 등번호 OCR
# =============================================================================

class JerseyOCR:
    """
    등번호 OCR 인식기.

    COURTVIEW_digit.pt (YOLOv8n, 10-class) 숫자 감지 모델로
    등번호 영역 내 개별 숫자를 감지합니다. 각 숫자 bbox를
    x좌표 순으로 정렬하여 등번호를 조합합니다.
    모델 미존재 시 형태학적 분석으로 폴백합니다.

    파이프라인:
        1. 등번호 ROI 추출 (bbox 내 상대 좌표)
        2. YOLO 숫자 감지 → 개별 숫자 bbox + class(0~9)
        3. x좌표 정렬 → 숫자 조합 (예: [1, 3] → 13)
        4. 유효성 검증 (0~99 범위)
        5. 다중 프레임 관측 → 투표 기반 확정
        6. (멀티뷰) 동일 인물 다중 뷰 투표

    사용 예시::

        >>> config = JerseyOCRConfig()
        >>> ocr = JerseyOCR()
        >>> ocr.initialize(config)
        >>> region = ocr.recognize(candidate, frame)
    """

    def __init__(self) -> None:
        """OCR 인식기 초기화."""
        self._lock = threading.RLock()
        self._config: JerseyOCRConfig | None = None
        self._initialized: bool = False

        # YOLO 숫자 감지 모델 (detect 방식, 폴백)
        self._digit_model: Any = None  # ultralytics.YOLO
        # YOLO classification 모델 (전체 번호 분류, 우선)
        self._cls_model: Any = None  # ultralytics.YOLO (classify)

        # 인물별 등번호 관측 이력 (track_id → deque of (number, confidence))
        self._observation_history: dict[int, deque[tuple[int, float]]] = {}

        # 인물별 확정 등번호 (track_id → number)
        self._confirmed_numbers: dict[int, int] = {}

        # 통계
        self._total_recognized: int = 0
        self._total_confirmed: int = 0

        logger.info("JerseyOCR 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_recognized(self) -> int:
        """누적 인식 수."""
        return self._total_recognized

    @property
    def total_confirmed(self) -> int:
        """누적 확정 수."""
        return self._total_confirmed

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, config: JerseyOCRConfig) -> None:
        """
        OCR 인식기 초기화 및 YOLO 숫자 감지 모델 로드.

        Args:
            config: OCR 설정
        """
        with self._lock:
            if self._initialized:
                logger.warning("이미 초기화된 OCR 인식기를 재초기화합니다")
                self.shutdown()

            self._config = config

            # Classification 모델 로드 (우선)
            self._load_cls_model()

            # CV-Digit 최신 버전 자동 감지 (glob + reverse=True)
            digit_files = sorted(
                Path("weights").glob(_DIGIT_MODEL_GLOB), reverse=True,
            )
            model_path: Path | None = digit_files[0] if digit_files else None
            if model_path is not None:
                logger.info("CV-Digit 최신 버전 감지: %s", model_path.name)

            if model_path is not None and model_path.exists():
                try:
                    from ultralytics import YOLO

                    # .cv 패키지 지원 (TensorRT engine 우선, pt 폴백)
                    if model_path.suffix == ".cv":
                        import zipfile
                        import tempfile
                        with zipfile.ZipFile(model_path, "r") as zf:
                            file_list = zf.namelist()
                            tmp_dir = tempfile.mkdtemp(prefix="cvdigit_")
                            if "inference.engine" in file_list:
                                engine_path = Path(tmp_dir) / "inference.engine"
                                with open(engine_path, "wb") as f:
                                    f.write(zf.read("inference.engine"))
                                self._digit_model = YOLO(str(engine_path), task="detect")
                                logger.info("CV-Digit TensorRT 엔진 로드 (FP16)")
                            else:
                                weights_pt = Path(tmp_dir) / "weights.pt"
                                with open(weights_pt, "wb") as f:
                                    f.write(zf.read("weights.pt"))
                                self._digit_model = YOLO(str(weights_pt))
                                logger.info("CV-Digit PyTorch 로드 (TRT 미포함)")
                    else:
                        self._digit_model = YOLO(str(model_path))

                    logger.info(
                        "YOLO 숫자 감지 모델 로드 완료: %s (%d 클래스)",
                        model_path.name,
                        len(self._digit_model.names),
                    )
                except Exception as exc:
                    logger.warning(
                        "YOLO 숫자 감지 모델 로드 실패 (형태학적 분석 폴백): %s",
                        exc,
                    )
                    self._digit_model = None
            else:
                logger.info(
                    "YOLO 숫자 모델 파일 없음 (%s), 형태학적 분석으로 폴백",
                    model_path,
                )

            self._observation_history.clear()
            self._confirmed_numbers.clear()
            self._total_recognized = 0
            self._total_confirmed = 0
            self._initialized = True
            logger.info("JerseyOCR 초기화 완료: %r", config)

    def _load_cls_model(self) -> None:
        """등번호 classification 모델 로드 (전체 번호 한번에 분류)."""
        from pathlib import Path as _Path

        # CV-JerseyCls 최신 버전 자동 감지 (glob + reverse=True)
        cls_files = sorted(
            _Path("weights").glob(_CLS_MODEL_GLOB), reverse=True,
        )
        cls_path: _Path | None = cls_files[0] if cls_files else None
        pt_path = _Path(_DEFAULT_CLS_PT_PATH)

        try:
            from ultralytics import YOLO

            if cls_path is not None and cls_path.exists():
                import zipfile
                import tempfile
                with zipfile.ZipFile(cls_path, "r") as zf:
                    tmp_dir = tempfile.mkdtemp()
                    weights_pt = _Path(tmp_dir) / "weights.pt"
                    with open(weights_pt, "wb") as f:
                        f.write(zf.read("weights.pt"))
                self._cls_model = YOLO(str(weights_pt))
                weights_pt.unlink(missing_ok=True)
                _Path(tmp_dir).rmdir()
                logger.info(
                    "CV-JerseyCls 최신 버전 로드: %s", cls_path.name,
                )
            elif pt_path.exists():
                self._cls_model = YOLO(str(pt_path))
                logger.info(
                    "Jersey classification 모델 로드 (학습 디렉토리 폴백): %s",
                    pt_path.name,
                )
            else:
                logger.info("Classification 모델 없음, digit detect 폴백")
                self._cls_model = None
        except Exception as exc:
            logger.warning("Classification 모델 로드 실패: %s", exc)
            self._cls_model = None

    def _classify_jersey_number(
        self,
        roi: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        Classification 모델로 등번호 전체 인식.

        player crop의 상체 ROI를 입력하면 0~99 번호를 한번에 분류합니다.

        Args:
            roi: BGR 또는 그레이스케일 이미지

        Returns:
            (등번호 int | None, 신뢰도)
        """
        if self._cls_model is None:
            return None, 0.0

        try:
            if roi.ndim == 2:
                input_img = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
            else:
                input_img = roi

            results = self._cls_model.predict(
                input_img,
                imgsz=_CLS_IMGSZ,
                verbose=False,
            )

            if not results or len(results) == 0:
                return None, 0.0

            result = results[0]
            probs = result.probs

            if probs is None:
                return None, 0.0

            # top1 클래스
            top1_idx = int(probs.top1)
            top1_conf = float(probs.top1conf)

            # 클래스 이름 → 등번호
            class_name = self._cls_model.names.get(top1_idx, "")
            if class_name.isdigit():
                number = int(class_name)
                if 0 <= number <= 99 and top1_conf >= 0.3:
                    return number, top1_conf

            return None, 0.0

        except Exception:
            return None, 0.0

    def shutdown(self) -> None:
        """OCR 인식기 종료 및 리소스 해제."""
        with self._lock:
            self._digit_model = None
            self._observation_history.clear()
            self._confirmed_numbers.clear()
            self._initialized = False
            logger.info(
                "JerseyOCR 종료: 인식=%d, 확정=%d",
                self._total_recognized,
                self._total_confirmed,
            )

    def reset(self) -> None:
        """통계/이력 초기화 (모델 유지)."""
        with self._lock:
            self._observation_history.clear()
            self._confirmed_numbers.clear()
            self._total_recognized = 0
            self._total_confirmed = 0

    # =========================================================================
    # 단일 후보 등번호 인식
    # =========================================================================

    def recognize(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
        track_id: int | None = None,
    ) -> _JerseyRegion:
        """
        단일 후보의 등번호 인식.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            track_id: 추적 ID (이력 관리용, None이면 이력 미저장)

        Returns:
            _JerseyRegion (등번호 인식 결과)
        """
        if not self._initialized or self._config is None:
            return _JerseyRegion()

        with self._lock:
            # 선수 클래스만 인식
            if candidate.class_id != PLAYER_CLASS_ID_PLAYER:
                return _JerseyRegion()

            # 이미 확정된 등번호가 있으면 반환
            if track_id is not None and track_id in self._confirmed_numbers:
                confirmed = self._confirmed_numbers[track_id]
                return _JerseyRegion(
                    number=confirmed,
                    confidence=1.0,
                    source_bbox_x=candidate.bbox_x,
                    source_bbox_y=candidate.bbox_y,
                    source_bbox_w=candidate.bbox_w,
                    source_bbox_h=candidate.bbox_h,
                    camera_id=candidate.camera_id,
                    frame_index=candidate.frame_index,
                )

            config = self._config

            # 등번호 ROI 추출
            roi, roi_bbox = self._extract_jersey_roi(candidate, frame, config)
            if roi is None:
                return _JerseyRegion()

            # 숫자 인식 (원본 BGR ROI 전달 — YOLO는 원본이 최적)
            number, confidence = self._recognize_digits(roi)

            region = _JerseyRegion(
                number=number,
                confidence=confidence,
                text_x=0.0,
                text_y=0.0,
                text_w=float(roi.shape[1]) if roi is not None else 0.0,
                text_h=float(roi.shape[0]) if roi is not None else 0.0,
                source_bbox_x=candidate.bbox_x,
                source_bbox_y=candidate.bbox_y,
                source_bbox_w=candidate.bbox_w,
                source_bbox_h=candidate.bbox_h,
                camera_id=candidate.camera_id,
                frame_index=candidate.frame_index,
            )

            # 유효한 인식 결과 → 이력 저장 + 투표
            if region.is_valid and track_id is not None and number is not None:
                self._total_recognized += 1
                self._update_history(track_id, number, confidence)
                self._try_confirm(track_id, config)

            return region

    def recognize_batch(
        self,
        candidates: list[_PlayerCandidate],
        frame: NDArray[np.uint8],
        track_ids: list[int | None] | None = None,
    ) -> list[_JerseyRegion]:
        """단일 프레임 내 다수 후보 배치 인식 (내부에서 multi-frame API 호출)."""
        return self.recognize_batch_multi_frame(
            [(cand, frame) for cand in candidates],
            track_ids=track_ids,
        )

    def recognize_batch_multi_frame(
        self,
        candidates_with_frames: list[tuple[_PlayerCandidate, NDArray[np.uint8]]],
        track_ids: list[int | None] | None = None,
    ) -> list[_JerseyRegion]:
        """
        여러 프레임의 여러 후보를 **한 번의 YOLO predict**로 인식.

        Args:
            candidates_with_frames: [(후보, BGR 프레임), ...] — 카메라 섞어도 됨
            track_ids: 대응 track_id 목록

        Returns:
            _JerseyRegion 목록 (입력 순서 유지, 실패 시 빈 _JerseyRegion)
        """
        n = len(candidates_with_frames)
        if n == 0 or not self._initialized or self._config is None:
            return [_JerseyRegion() for _ in range(n)]

        if track_ids is None:
            track_ids = [None] * n

        results: list[_JerseyRegion] = [_JerseyRegion() for _ in range(n)]

        with self._lock:
            config = self._config

            # 1. ROI 일괄 추출 + 유효 인덱스 기록
            rois: list[NDArray[np.uint8]] = []
            valid_idx: list[int] = []
            roi_sizes: list[tuple[int, int]] = []
            for i, (cand, frame) in enumerate(candidates_with_frames):
                if cand.class_id != PLAYER_CLASS_ID_PLAYER:
                    continue
                # 확정된 번호는 YOLO 건너뛰고 즉시 반환
                tid = track_ids[i] if i < len(track_ids) else None
                if tid is not None and tid in self._confirmed_numbers:
                    results[i] = _JerseyRegion(
                        number=self._confirmed_numbers[tid], confidence=1.0,
                        source_bbox_x=cand.bbox_x, source_bbox_y=cand.bbox_y,
                        source_bbox_w=cand.bbox_w, source_bbox_h=cand.bbox_h,
                        camera_id=cand.camera_id, frame_index=cand.frame_index,
                    )
                    continue
                roi, _ = self._extract_jersey_roi(cand, frame, config)
                if roi is None:
                    continue
                rois.append(roi)
                valid_idx.append(i)
                roi_sizes.append(roi.shape[:2])

            if not rois:
                return results

            # 2. YOLO 배치 추론 (1회 호출)
            if self._digit_model is None:
                # 폴백 — 형태학적 순차 (배치 이점 없지만 극소 케이스)
                for idx, roi in zip(valid_idx, rois):
                    number, conf = self._morphological_fallback(roi)
                    cand, _ = candidates_with_frames[idx]
                    results[idx] = _JerseyRegion(
                        number=number, confidence=conf,
                        source_bbox_x=cand.bbox_x, source_bbox_y=cand.bbox_y,
                        source_bbox_w=cand.bbox_w, source_bbox_h=cand.bbox_h,
                        camera_id=cand.camera_id, frame_index=cand.frame_index,
                    )
                return results

            try:
                yolo_results = self._digit_model.predict(
                    rois,
                    imgsz=_DIGIT_IMGSZ,
                    conf=_DIGIT_MIN_CONFIDENCE,
                    verbose=False,
                )
            except Exception as _exc:
                logger.debug("Jersey batch predict 실패: %s", _exc)
                yolo_results = []

            # 3. 결과 분배
            for k, idx in enumerate(valid_idx):
                cand, _ = candidates_with_frames[idx]
                tid = track_ids[idx] if idx < len(track_ids) else None
                roi_h, roi_w = roi_sizes[k]

                number: int | None = None
                confidence: float = 0.0

                if k < len(yolo_results):
                    r = yolo_results[k]
                    boxes = getattr(r, "boxes", None)
                    if boxes is not None and len(boxes) > 0:
                        # 일괄 CPU 전송
                        xywh = boxes.xywh.cpu().numpy()
                        cls_arr = boxes.cls.cpu().numpy().astype(int)
                        conf_arr = boxes.conf.cpu().numpy()
                        detections: list[tuple[float, int, float]] = []
                        for j in range(len(boxes)):
                            c = int(cls_arr[j])
                            if 0 <= c <= 9:
                                detections.append((
                                    float(xywh[j][0]), c, float(conf_arr[j]),
                                ))
                        if detections:
                            if len(detections) > JERSEY_MAX_DIGITS:
                                detections.sort(key=lambda d: d[2], reverse=True)
                                detections = detections[:JERSEY_MAX_DIGITS]
                            detections.sort(key=lambda d: d[0])
                            number_str = "".join(str(d[1]) for d in detections)
                            digit_confs = [d[2] for d in detections]
                            number, confidence = self._validate_number(
                                number_str, digit_confs,
                            )

                if number is None:
                    # YOLO 실패 → 폴백
                    number, confidence = self._morphological_fallback(rois[k])

                region = _JerseyRegion(
                    number=number, confidence=confidence,
                    text_x=0.0, text_y=0.0,
                    text_w=float(roi_w), text_h=float(roi_h),
                    source_bbox_x=cand.bbox_x, source_bbox_y=cand.bbox_y,
                    source_bbox_w=cand.bbox_w, source_bbox_h=cand.bbox_h,
                    camera_id=cand.camera_id, frame_index=cand.frame_index,
                )
                results[idx] = region

                # 이력/확정 (기존 로직 유지)
                if region.is_valid and tid is not None and number is not None:
                    self._total_recognized += 1
                    self._update_history(tid, number, confidence)
                    self._try_confirm(tid, config)

        return results

    # =========================================================================
    # 멀티뷰 투표
    # =========================================================================

    def recognize_multi_view(
        self,
        candidate_views: dict[str, tuple[_PlayerCandidate, NDArray[np.uint8]]],
        track_id: int | None = None,
    ) -> _JerseyRegion:
        """
        멀티뷰 투표 기반 등번호 인식.

        동일 인물의 여러 카메라 뷰에서 독립 인식 후 다수결 투표.

        Args:
            candidate_views: 카메라 ID → (후보, BGR 프레임) 매핑
            track_id: 추적 ID

        Returns:
            투표 결과 _JerseyRegion
        """
        if not self._initialized or not candidate_views:
            return _JerseyRegion()

        votes: dict[int, list[float]] = defaultdict(list)
        best_region = _JerseyRegion()

        for cam_id, (candidate, frame) in candidate_views.items():
            region = self.recognize(candidate, frame, track_id)
            if region.is_valid and region.number is not None:
                votes[region.number].append(region.confidence)
                # 가장 높은 신뢰도 영역 보존
                if region.confidence > best_region.confidence:
                    best_region = region

        if not votes:
            return _JerseyRegion()

        # 다수결 투표
        best_number = -1
        best_count = 0
        best_avg_conf = 0.0

        for number, confs in votes.items():
            count = len(confs)
            avg_conf = sum(confs) / count
            if count > best_count or (count == best_count and avg_conf > best_avg_conf):
                best_number = number
                best_count = count
                best_avg_conf = avg_conf

        if best_number < 0:
            return _JerseyRegion()

        return _JerseyRegion(
            number=best_number,
            confidence=best_avg_conf,
            source_bbox_x=best_region.source_bbox_x,
            source_bbox_y=best_region.source_bbox_y,
            source_bbox_w=best_region.source_bbox_w,
            source_bbox_h=best_region.source_bbox_h,
            camera_id=best_region.camera_id,
            frame_index=best_region.frame_index,
        )

    # =========================================================================
    # 확정 등번호 조회
    # =========================================================================

    def get_confirmed_number(self, track_id: int) -> int | None:
        """
        확정된 등번호 조회.

        Args:
            track_id: 추적 ID

        Returns:
            확정 등번호 (미확정이면 None)
        """
        return self._confirmed_numbers.get(track_id)

    def get_all_confirmed(self) -> dict[int, int]:
        """모든 확정 등번호 조회. {track_id: number}"""
        return dict(self._confirmed_numbers)

    # =========================================================================
    # 내부 메서드 — ROI 추출
    # =========================================================================

    def _extract_jersey_roi(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
        config: JerseyOCRConfig,
    ) -> tuple[NDArray[np.uint8] | None, tuple[int, int, int, int]]:
        """
        등번호 ROI 추출.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            config: OCR 설정

        Returns:
            (ROI 이미지, (x1, y1, x2, y2)) — ROI가 유효하지 않으면 (None, (0,0,0,0))
        """
        fh, fw = frame.shape[:2]

        y1 = int(candidate.bbox_y + candidate.bbox_h * config.jersey_roi_top)
        y2 = int(candidate.bbox_y + candidate.bbox_h * config.jersey_roi_bottom)
        x1 = int(candidate.bbox_x + candidate.bbox_w * config.jersey_roi_left)
        x2 = int(candidate.bbox_x + candidate.bbox_w * config.jersey_roi_right)

        # 프레임 경계 클리핑
        x1 = max(0, min(x1, fw - 1))
        x2 = max(x1 + 1, min(x2, fw))
        y1 = max(0, min(y1, fh - 1))
        y2 = max(y1 + 1, min(y2, fh))

        roi_w = x2 - x1
        roi_h = y2 - y1

        # 최소 크기 검증
        if roi_w < 10 or roi_h < 10:
            return None, (0, 0, 0, 0)

        roi = frame[y1:y2, x1:x2]
        return roi, (x1, y1, x2, y2)

    # =========================================================================
    # 내부 메서드 — 전처리
    # =========================================================================

    def _preprocess_roi(
        self,
        roi: NDArray[np.uint8],
    ) -> NDArray[np.uint8] | None:
        """
        등번호 ROI 전처리 (그레이스케일, 이진화, 리사이즈).

        Args:
            roi: BGR ROI 이미지

        Returns:
            전처리된 그레이스케일 이미지 (None이면 유효하지 않음)
        """
        if roi.size == 0:
            return None

        # 그레이스케일 변환
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # CLAHE 대비 향상 (조명 불균일 보정)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # 적응형 이진화 (Otsu보다 텍스트에 강건)
        binary = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            ADAPTIVE_BINARIZATION_BLOCK_SIZE,
            int(ADAPTIVE_BINARIZATION_CONSTANT),
        )

        # 표준 높이로 리사이즈 (종횡비 유지)
        h, w = binary.shape[:2]
        if h < 10:
            return None

        target_h = OCR_INPUT_STANDARD_HEIGHT
        scale = target_h / h
        target_w = max(10, int(w * scale))
        resized = cv2.resize(binary, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        return resized

    # =========================================================================
    # 내부 메서드 — 숫자 인식
    # =========================================================================

    def _recognize_digits(
        self,
        roi_bgr: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        ROI 이미지에서 숫자 인식.

        YOLO 모델에는 원본 BGR 이미지를 전달 (색상/질감 정보 보존).
        형태학적 폴백에만 이진화 전처리를 적용.

        우선순위:
        1. Classification 모델 (전체 번호 한번에, 원본 BGR)
        2. YOLO detect 모델 (개별 숫자 bbox, 원본 BGR)
        3. 형태학적 분석 (이진화 전처리 후 폴백)

        Args:
            roi_bgr: 원본 BGR ROI 이미지

        Returns:
            (등번호 int | None, 신뢰도)
        """
        # 1. Classification 우선 (원본 BGR)
        if self._cls_model is not None:
            number, conf = self._classify_jersey_number(roi_bgr)
            if number is not None:
                return number, conf

        # 2. Digit detect 폴백 (원본 BGR)
        if self._digit_model is not None:
            return self._yolo_digit_inference(roi_bgr)

        # 3. 형태학적 폴백 (이진화 전처리 필요)
        processed = self._preprocess_roi(roi_bgr)
        if processed is None:
            return None, 0.0
        return self._morphological_recognition(processed)

    def _yolo_digit_inference(
        self,
        roi_bgr: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        YOLO 숫자 감지 모델 추론.

        원본 BGR 이미지를 직접 전달하여 색상/질감 정보를 보존합니다.
        개별 숫자를 bbox로 감지하고, x좌표 순 정렬하여 등번호를 조합합니다.
        모델 클래스: 0='0', 1='1', ..., 9='9'

        Args:
            roi_bgr: 원본 BGR ROI 이미지

        Returns:
            (등번호 int | None, 신뢰도)
        """
        if self._digit_model is None:
            return None, 0.0

        try:
            # BGR 3채널 보장 (그레이스케일이 들어올 경우 대비)
            if roi_bgr.ndim == 2:
                input_img = cv2.cvtColor(roi_bgr, cv2.COLOR_GRAY2BGR)
            else:
                input_img = roi_bgr

            # YOLO 추론 (원본 BGR, imgsz=224)
            results = self._digit_model.predict(
                input_img,
                imgsz=_DIGIT_IMGSZ,
                conf=_DIGIT_MIN_CONFIDENCE,
                verbose=False,
            )

            if not results or len(results) == 0:
                return self._morphological_fallback(roi_bgr)

            result = results[0]
            boxes = result.boxes

            if boxes is None or len(boxes) == 0:
                return self._morphological_fallback(roi_bgr)

            # 감지된 숫자 수집: (x_center, digit, confidence)
            detections: list[tuple[float, int, float]] = []

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                x_center = float(boxes.xywh[i][0].item())

                # cls_id = 0~9 → 숫자 값
                if 0 <= cls_id <= 9:
                    detections.append((x_center, cls_id, conf))

            if not detections:
                return self._morphological_fallback(roi_bgr)

            # 최대 자릿수 초과 필터 (높은 신뢰도 순으로 유지)
            if len(detections) > JERSEY_MAX_DIGITS:
                detections.sort(key=lambda d: d[2], reverse=True)
                detections = detections[:JERSEY_MAX_DIGITS]

            # x좌표 순 정렬 (좌→우 읽기)
            detections.sort(key=lambda d: d[0])

            # 숫자 조합
            number_str = "".join(str(d[1]) for d in detections)
            digit_confs = [d[2] for d in detections]

            return self._validate_number(number_str, digit_confs)

        except Exception as exc:
            logger.debug("YOLO 숫자 감지 추론 실패: %s", exc)
            return self._morphological_fallback(roi_bgr)

    def _morphological_fallback(
        self,
        roi_bgr: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        형태학적 분석 폴백 (이진화 전처리 후 실행).

        YOLO 모델이 실패한 경우에만 호출됩니다.

        Args:
            roi_bgr: 원본 BGR ROI 이미지

        Returns:
            (등번호 int | None, 신뢰도)
        """
        processed = self._preprocess_roi(roi_bgr)
        if processed is None:
            return None, 0.0
        return self._morphological_recognition(processed)

    # =========================================================================
    # 내부 메서드 — 형태학적 분석 (CRNN 폴백)
    # =========================================================================

    def _morphological_recognition(
        self,
        processed: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        형태학적 분석 기반 숫자 인식 (CRNN 모델 없을 때 폴백).

        이진화 이미지에서 외부 윤곽선(contour)을 찾고,
        숫자 형태를 분석하여 인식합니다.

        Args:
            processed: 이진화된 그레이스케일 이미지

        Returns:
            (등번호 int | None, 신뢰도)
        """
        # 이진화 반전 (숫자가 흰색이 되도록)
        inverted = cv2.bitwise_not(processed)

        # 외부 윤곽선 검출
        contours, _ = cv2.findContours(
            inverted,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return None, 0.0

        h, w = processed.shape[:2]
        min_contour_h = h * 0.3  # 높이의 30% 이상
        min_contour_w = w * 0.05  # 너비의 5% 이상

        # 유효 윤곽선 필터링 (크기, 종횡비)
        digit_contours: list[tuple[int, int, int, int]] = []

        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if ch < min_contour_h or cw < min_contour_w:
                continue
            # 종횡비: 숫자는 세로로 긴 형태 (h/w >= 1.0)
            if ch > 0 and cw / ch > 2.0:
                continue
            digit_contours.append((cx, cy, cw, ch))

        if not digit_contours or len(digit_contours) > JERSEY_MAX_DIGITS:
            return None, 0.0

        # X 좌표 순서로 정렬 (좌→우 읽기)
        digit_contours.sort(key=lambda d: d[0])

        # 각 숫자 영역에서 특징 기반 분류
        digits: list[int] = []
        confidences: list[float] = []

        for cx, cy, cw, ch in digit_contours:
            digit_roi = inverted[cy:cy + ch, cx:cx + cw]
            digit, conf = self._classify_digit_by_features(digit_roi)
            if digit is not None:
                digits.append(digit)
                confidences.append(conf)

        if not digits:
            return None, 0.0

        # 숫자 조합
        number_str = "".join(str(d) for d in digits)
        result = self._validate_number(number_str, confidences)

        # 형태학적 분석은 신뢰도 감쇄 (CRNN보다 덜 정확)
        if result[0] is not None:
            return result[0], result[1] * 0.7

        return None, 0.0

    def _classify_digit_by_features(
        self,
        digit_roi: NDArray[np.uint8],
    ) -> tuple[int | None, float]:
        """
        단일 숫자 ROI의 기하학적 특징 기반 분류.

        가로/세로 프로파일, 구멍(hole) 수, 종횡비 등의
        구조적 특징으로 0~9를 분류합니다.

        Args:
            digit_roi: 이진화된 단일 숫자 ROI (흰색=숫자)

        Returns:
            (숫자 int | None, 신뢰도)
        """
        if digit_roi.size == 0:
            return None, 0.0

        h, w = digit_roi.shape[:2]
        if h < 5 or w < 3:
            return None, 0.0

        total_pixels = h * w
        white_pixels = int(np.count_nonzero(digit_roi))
        fill_ratio = white_pixels / max(1, total_pixels)

        # 구멍 수 분석 (0, 4, 6, 8, 9에 구멍 존재)
        holes = self._count_holes(digit_roi)

        # 종횡비 (h/w)
        aspect = h / max(1, w)

        # 수평 프로파일 (상/중/하 분할)
        third_h = max(1, h // 3)
        top_density = float(np.count_nonzero(digit_roi[:third_h, :])) / max(1, third_h * w)
        mid_density = float(np.count_nonzero(digit_roi[third_h:2*third_h, :])) / max(1, third_h * w)
        bot_density = float(np.count_nonzero(digit_roi[2*third_h:, :])) / max(1, (h - 2*third_h) * w)

        # 기하학적 규칙 기반 분류
        # 이 방법은 CRNN보다 부정확하지만, 모델 없이도 동작
        confidence = 0.4  # 기본 낮은 신뢰도

        if holes >= 2:
            # 8 (구멍 2개)
            return 8, confidence
        elif holes == 1:
            if bot_density > top_density:
                # 6 (하단에 구멍)
                return 6, confidence
            elif top_density > bot_density:
                # 9 (상단에 구멍)
                return 9, confidence
            elif mid_density < top_density and mid_density < bot_density:
                # 0 (중간이 비어있지 않음 — 전체 구멍)
                return 0, confidence
            else:
                # 4 (상단 열림)
                return 4, confidence
        else:
            # 구멍 없는 숫자: 1, 2, 3, 5, 7
            if fill_ratio < 0.25:
                # 1 (매우 얇음)
                return 1, confidence + 0.1
            elif aspect > 2.5 and fill_ratio < 0.35:
                # 1 (세로로 매우 긴 형태)
                return 1, confidence
            elif mid_density > top_density and mid_density > bot_density:
                # 3 또는 5 (중간에 가로획)
                if top_density > bot_density:
                    return 5, confidence
                else:
                    return 3, confidence
            elif top_density > bot_density:
                # 7 (상단 무거움)
                return 7, confidence
            else:
                # 2 (하단 무거움)
                return 2, confidence

    @staticmethod
    def _count_holes(binary: NDArray[np.uint8]) -> int:
        """
        이진 이미지의 구멍(hole) 수 카운트.

        Args:
            binary: 이진 이미지 (흰색=전경)

        Returns:
            구멍 수
        """
        # 반전 → 외부 윤곽선 = 구멍
        inverted = cv2.bitwise_not(binary)
        contours, hierarchy = cv2.findContours(
            inverted,
            cv2.RETR_CCOMP,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if hierarchy is None or len(hierarchy) == 0:
            return 0

        hole_count = 0
        h_data = hierarchy[0]
        for i in range(len(h_data)):
            # parent가 있으면 내부 윤곽선 = 구멍
            if h_data[i][3] >= 0:
                # 면적 필터 (너무 작은 노이즈 제외)
                area = cv2.contourArea(contours[i])
                if area > binary.shape[0] * binary.shape[1] * 0.02:
                    hole_count += 1

        return hole_count

    # =========================================================================
    # 내부 메서드 — 후처리
    # =========================================================================

    @staticmethod
    def _validate_number(
        text: str,
        char_probs: list[float],
    ) -> tuple[int | None, float]:
        """
        등번호 유효성 검증.

        Args:
            text: 숫자 텍스트
            char_probs: 각 문자 확률

        Returns:
            (등번호 int | None, 평균 신뢰도)
        """
        if not _JERSEY_REGEX.match(text):
            return None, 0.0

        number = int(text)
        if number < JERSEY_NUMBER_MIN or number > JERSEY_NUMBER_MAX:
            return None, 0.0

        avg_conf = sum(char_probs) / max(1, len(char_probs))
        return number, avg_conf

    # =========================================================================
    # 내부 메서드 — 이력 관리 및 투표
    # =========================================================================

    def _update_history(
        self,
        track_id: int,
        number: int,
        confidence: float,
    ) -> None:
        """
        등번호 관측 이력 갱신.

        Args:
            track_id: 추적 ID
            number: 인식된 등번호
            confidence: 인식 신뢰도
        """
        if track_id not in self._observation_history:
            self._observation_history[track_id] = deque(
                maxlen=_MAX_HISTORY_PER_PERSON,
            )
        self._observation_history[track_id].append((number, confidence))

    def _try_confirm(
        self,
        track_id: int,
        config: JerseyOCRConfig,
    ) -> None:
        """
        등번호 확정 시도 (투표 기반).

        최근 관측 윈도우에서 가장 빈번한 등번호가
        일관성 비율을 넘으면 확정합니다.

        Args:
            track_id: 추적 ID
            config: OCR 설정
        """
        if track_id in self._confirmed_numbers:
            return

        history = self._observation_history.get(track_id)
        if history is None:
            return

        # 최근 N개 관측만 사용
        recent = list(history)[-_VOTING_WINDOW:]

        if len(recent) < config.min_observations_for_confirm:
            return

        # 등번호별 빈도 및 가중 신뢰도
        vote_counts: dict[int, int] = defaultdict(int)
        vote_confs: dict[int, float] = defaultdict(float)

        for number, conf in recent:
            vote_counts[number] += 1
            vote_confs[number] += conf

        # 최다 득표 등번호
        best_number = max(vote_counts, key=vote_counts.get)  # type: ignore[arg-type]
        best_count = vote_counts[best_number]

        # 일관성 비율 검증
        consistency = best_count / len(recent)
        if consistency >= config.consistency_ratio:
            self._confirmed_numbers[track_id] = best_number
            self._total_confirmed += 1
            logger.info(
                "등번호 확정: track=%d, #%d (일관성=%.1f%%, 관측=%d)",
                track_id,
                best_number,
                consistency * 100,
                best_count,
            )

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def remove_track(self, track_id: int) -> None:
        """
        추적 종료 시 이력 정리.

        Args:
            track_id: 삭제할 추적 ID
        """
        with self._lock:
            self._observation_history.pop(track_id, None)
            self._confirmed_numbers.pop(track_id, None)

    def __repr__(self) -> str:
        model_str = "YOLO" if self._digit_model is not None else "morphological"
        return (
            f"JerseyOCR({model_str}, "
            f"recognized={self._total_recognized}, "
            f"confirmed={self._total_confirmed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "JerseyOCR",
    "JerseyOCRConfig",
]

__version__: str = "1.0.0"
