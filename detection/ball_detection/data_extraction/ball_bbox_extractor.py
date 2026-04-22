# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: ball_bbox_extractor.py
설명: 공 바운딩박스 크롭 추출기
      - 감지된 공 바운딩박스를 640×640 크롭으로 수집
      - YOLO format 라벨 생성 (class_id cx cy w h)
      - 6중 품질 필터 (신뢰도/원형도/블러/크기/선명도/중복)
      - 버퍼 축적 → 자동 flush (100개 또는 300초)
      - finalize() → ExtractionResult (PENDING → S3 업로드 대기)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 검출 파라미터
    - shared/dto/ball_dto.py: BallDetection DTO
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/geometry_dto.py: BoundingBox

데이터 흐름:
    BallDetector.detect() → BallDetection
        ↓
    6중 필터 (신뢰도≥0.8, 원형도, 블러, 크기, 선명도, pHash 중복)
        ↓
    bbox 중심 크롭 → 640×640 리사이즈 → JPEG 인코딩
        ↓
    YOLO 라벨 생성 (class_id cx cy w h)
        ↓
    버퍼 축적 → 자동 flush (100개 또는 300초)
        ↓
    finalize() → images/*.jpg + labels/*.txt + metadata.json
        ↓
    ExtractionResult (PENDING → self_learning 파이프라인 → S3 업로드)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.ball_constants import (
    BALL_CIRCULARITY_THRESHOLD,
    BALL_DETECTION_CLASS_ID,
    BALL_DETECTION_HIGH_CONFIDENCE,
    BALL_DETECTION_INPUT_SIZE,
    BALL_DETECTION_MAX_SIZE_RATIO,
    BALL_DETECTION_MIN_SIZE_RATIO,
    BALL_MOTION_BLUR_THRESHOLD,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from shared.dto.geometry_dto import BoundingBox


logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 버퍼 자동 flush 임계값
_BUFFER_FLUSH_COUNT: Final[int] = 100
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 크롭 출력 크기 (YOLO 학습 입력 크기)
_CROP_SIZE: Final[int] = BALL_DETECTION_INPUT_SIZE

# JPEG 인코딩 품질
_JPEG_QUALITY: Final[int] = 95

# pHash 유사도 임계값 (비트 수, 낮을수록 유사)
_PHASH_SIMILARITY_THRESHOLD: Final[int] = 8

# pHash 해시 크기
_PHASH_SIZE: Final[int] = 8

# 선명도 (라플라시안 분산) 최소 임계값
_SHARPNESS_MIN_THRESHOLD: Final[float] = 50.0

# 최대 버퍼 메모리 (샘플 수)
_MAX_BUFFER_SIZE: Final[int] = 500

# pHash 집합 최대 크기 (메모리 보호)
_MAX_PHASH_SET_SIZE: Final[int] = 5000

# 메타데이터 파일명
_METADATA_FILENAME: Final[str] = "metadata.json"


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class BallBboxExtractorConfig:
    """
    공 바운딩박스 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        min_confidence: 최소 감지 신뢰도 (기본: 0.8)
        min_circularity: 최소 원형도 (기본: ball_constants)
        min_sharpness: 최소 선명도 (라플라시안 분산)
        blur_threshold: 블러 판정 임계값
        crop_size: 크롭 이미지 크기
        jpeg_quality: JPEG 인코딩 품질
        phash_threshold: pHash 중복 판정 임계값
        buffer_flush_count: 버퍼 flush 샘플 수
        buffer_flush_interval_sec: 버퍼 flush 간격 (초)
        max_buffer_size: 최대 버퍼 크기 (메모리 보호)
        dataset_split: 데이터셋 분할 (train/val/test)
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/ball"
    min_confidence: float = BALL_DETECTION_HIGH_CONFIDENCE
    min_circularity: float = BALL_CIRCULARITY_THRESHOLD
    min_sharpness: float = _SHARPNESS_MIN_THRESHOLD
    blur_threshold: float = BALL_MOTION_BLUR_THRESHOLD
    crop_size: int = _CROP_SIZE
    jpeg_quality: int = _JPEG_QUALITY
    phash_threshold: int = _PHASH_SIMILARITY_THRESHOLD
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/ball"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _BboxSample:
    """버퍼에 저장되는 단일 샘플."""

    sample_id: str
    image_data: bytes  # JPEG 인코딩된 크롭 이미지
    label_text: str    # YOLO format "class_id cx cy w h"
    confidence: float
    frame_index: int
    camera_id: str
    phash: int         # 지각 해시값 (중복 검사용)


# =============================================================================
# 공 바운딩박스 추출기
# =============================================================================

class BallBboxExtractor:
    """
    공 바운딩박스 크롭 추출기.

    BallDetector의 감지 결과에서 고품질 공 바운딩박스를 수집하여
    YOLO 재학습용 데이터셋을 생성합니다.

    6중 품질 필터:
        1. 신뢰도 필터: confidence ≥ 0.8
        2. 원형도 필터: circularity ≥ 0.7
        3. 블러 필터: 모션 블러 ≤ threshold
        4. 크기 필터: min_size_ratio ≤ bbox ≤ max_size_ratio
        5. 선명도 필터: 라플라시안 분산 ≥ threshold
        6. pHash 중복 필터: 해밍 거리 ≥ threshold

    사용 예시::

        >>> config = BallBboxExtractorConfig(output_dir="data/ball")
        >>> extractor = BallBboxExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> # 감지 루프 내에서
        >>> extractor.process(frame, detection, frame_index=42, camera_id="cam_0")
        >>> # 분석 종료 시
        >>> result = extractor.finalize()
    """

    def __init__(self, config: BallBboxExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None
        self._images_dir: Path | None = None
        self._labels_dir: Path | None = None

        # 버퍼
        self._buffer: list[_BboxSample] = []
        self._phash_set: dict[int, None] = {}  # 중복 검사용 해시 (삽입 순서 보존 dict)
        self._last_flush_time: float = 0.0

        # 통계
        self._total_processed: int = 0
        self._total_accepted: int = 0
        self._total_flushed: int = 0
        self._filter_stats: dict[str, int] = {
            "confidence_reject": 0,
            "circularity_reject": 0,
            "blur_reject": 0,
            "size_reject": 0,
            "sharpness_reject": 0,
            "phash_reject": 0,
        }

        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, session_id: str, game_id: str) -> None:
        """
        추출 세션 초기화.

        Args:
            session_id: 세션 식별자
            game_id: 경기 식별자
        """
        with self._lock:
            if not self._config.enabled:
                logger.info("BallBboxExtractor 비활성화 상태")
                return

            self._session_id = session_id
            self._game_id = game_id

            # 출력 디렉토리 생성
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._session_dir = (
                Path(self._config.output_dir) / date_str / session_id
            )
            self._images_dir = self._session_dir / "images"
            self._labels_dir = self._session_dir / "labels"
            self._images_dir.mkdir(parents=True, exist_ok=True)
            self._labels_dir.mkdir(parents=True, exist_ok=True)

            # 상태 초기화
            self._buffer.clear()
            self._phash_set.clear()
            self._last_flush_time = time.monotonic()
            self._total_processed = 0
            self._total_accepted = 0
            self._total_flushed = 0
            for key in self._filter_stats:
                self._filter_stats[key] = 0

            self._initialized = True
            logger.info(
                "BallBboxExtractor 초기화 완료: session=%s, game=%s, dir=%s",
                session_id, game_id, self._session_dir,
            )

    def process(
        self,
        frame: NDArray[np.uint8],
        detection: BallDetection,
        frame_index: int,
        camera_id: str = "cam_0",
    ) -> bool:
        """
        단일 감지 결과 처리.

        Args:
            frame: 원본 프레임 (BGR, HWC)
            detection: 공 감지 결과
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID

        Returns:
            수집 여부 (True: 버퍼에 추가됨)
        """
        if not self._initialized or not self._config.enabled:
            return False

        with self._lock:
            self._total_processed += 1

            # 1. 신뢰도 필터
            if detection.confidence < self._config.min_confidence:
                self._filter_stats["confidence_reject"] += 1
                return False

            # 2. bbox 유효성
            if detection.bbox is None or detection.position is None:
                return False

            bbox = detection.bbox
            h_frame, w_frame = frame.shape[:2]

            # 3. 크기 필터 (프레임 대비)
            bbox_area_ratio = (bbox.width * bbox.height) / max(
                w_frame * h_frame, 1
            )
            if not (
                BALL_DETECTION_MIN_SIZE_RATIO
                <= bbox_area_ratio
                <= BALL_DETECTION_MAX_SIZE_RATIO
            ):
                self._filter_stats["size_reject"] += 1
                return False

            # 4. 크롭 추출
            crop = self._extract_crop(frame, bbox)
            if crop is None:
                self._filter_stats["size_reject"] += 1
                return False

            # 5. 원형도 필터
            circularity = self._compute_circularity(crop)
            if circularity < self._config.min_circularity:
                self._filter_stats["circularity_reject"] += 1
                return False

            # 6. 블러 필터
            if self._is_blurred(crop):
                self._filter_stats["blur_reject"] += 1
                return False

            # 7. 선명도 필터
            sharpness = self._compute_sharpness(crop)
            if sharpness < self._config.min_sharpness:
                self._filter_stats["sharpness_reject"] += 1
                return False

            # 8. pHash 중복 필터
            phash_val = self._compute_phash(crop)
            if self._is_duplicate(phash_val):
                self._filter_stats["phash_reject"] += 1
                return False

            # 크롭 리사이즈 → JPEG 인코딩
            resized = cv2.resize(
                crop,
                (self._config.crop_size, self._config.crop_size),
                interpolation=cv2.INTER_LINEAR,
            )
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._config.jpeg_quality]
            success, encoded = cv2.imencode(".jpg", resized, encode_params)
            if not success:
                return False

            # YOLO 라벨 생성 (정규화 좌표)
            cx_norm = (bbox.x + bbox.width / 2) / w_frame
            cy_norm = (bbox.y + bbox.height / 2) / h_frame
            w_norm = bbox.width / w_frame
            h_norm = bbox.height / h_frame
            label_text = (
                f"{BALL_DETECTION_CLASS_ID} "
                f"{cx_norm:.6f} {cy_norm:.6f} "
                f"{w_norm:.6f} {h_norm:.6f}"
            )

            # 샘플 ID 생성
            sample_id = (
                f"ball_{frame_index:08d}_{camera_id}_"
                f"{int(detection.confidence * 1000):04d}"
            )

            # 버퍼에 추가
            sample = _BboxSample(
                sample_id=sample_id,
                image_data=bytes(encoded),
                label_text=label_text,
                confidence=detection.confidence,
                frame_index=frame_index,
                camera_id=camera_id,
                phash=phash_val,
            )
            self._buffer.append(sample)
            self._phash_set[phash_val] = None

            # pHash 집합 크기 제한 (메모리 보호, 삽입 순서 보존으로 가장 오래된 것부터 제거)
            if len(self._phash_set) > _MAX_PHASH_SET_SIZE:
                excess = len(self._phash_set) - _MAX_PHASH_SET_SIZE // 2
                keys = list(self._phash_set.keys())[:excess]
                for k in keys:
                    del self._phash_set[k]

            self._total_accepted += 1

            # 자동 flush 확인
            self._check_auto_flush()

            return True

    def finalize(self) -> ExtractionResult | None:
        """
        추출 세션 종료 및 결과 반환.

        남은 버퍼를 flush하고, 메타데이터를 기록하고,
        ExtractionResult를 반환합니다.

        Returns:
            추출 결과 (비활성화 시 None)
        """
        if not self._initialized or not self._config.enabled:
            return None

        with self._lock:
            try:
                start_time = time.monotonic()

                # 남은 버퍼 flush
                self._flush_buffer()

                # 메타데이터 기록
                metadata_path = self._write_metadata()

                # 세션 디렉토리 전체 크기 계산
                total_size = self._compute_directory_size()

                processing_time_ms = (time.monotonic() - start_time) * 1000.0

                # S3 키 생성
                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                s3_key = (
                    f"{self._config.s3_prefix}/{date_str}/"
                    f"{self._session_id}"
                )

                # DatasetMetadata 생성
                ds_metadata = DatasetMetadata(
                    dataset_type=DatasetType.BALL_BBOX,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id],
                    description=(
                        f"공 바운딩박스 크롭 데이터 "
                        f"(session={self._session_id}, "
                        f"accepted={self._total_flushed}/{self._total_processed})"
                    ),
                )

                result = ExtractionResult(
                    game_id=self._game_id,
                    metadata=ds_metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._session_dir) if self._session_dir else "",
                    file_size_bytes=total_size,
                    processing_time_ms=processing_time_ms,
                    s3_bucket=self._config.s3_bucket,
                    s3_key=s3_key,
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "BallBboxExtractor 종료: "
                    "총 처리=%d, 수집=%d, flush=%d, "
                    "필터 통계=%s",
                    self._total_processed,
                    self._total_accepted,
                    self._total_flushed,
                    self._filter_stats,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 크롭 및 필터
    # =========================================================================

    def _extract_crop(
        self,
        frame: NDArray[np.uint8],
        bbox: BoundingBox,
    ) -> NDArray[np.uint8] | None:
        """
        바운딩박스 중심으로 정사각형 크롭 추출.

        bbox를 포함하는 정사각형 영역을 프레임에서 잘라냅니다.
        프레임 경계를 벗어나는 경우 제로 패딩을 적용합니다.

        Args:
            frame: 원본 프레임 (BGR)
            bbox: 공 바운딩박스

        Returns:
            크롭 이미지 또는 None (bbox가 너무 작은 경우)
        """
        h_frame, w_frame = frame.shape[:2]

        # 크롭 크기: bbox의 긴 변의 2배 (여유 포함)
        side = int(max(bbox.width, bbox.height) * 2.0)
        if side < 16:
            return None

        # 중심 좌표
        cx = int(bbox.x + bbox.width / 2)
        cy = int(bbox.y + bbox.height / 2)

        # 크롭 영역 계산
        x1 = cx - side // 2
        y1 = cy - side // 2
        x2 = x1 + side
        y2 = y1 + side

        # 프레임 경계 클리핑
        src_x1 = max(0, x1)
        src_y1 = max(0, y1)
        src_x2 = min(w_frame, x2)
        src_y2 = min(h_frame, y2)

        if src_x2 <= src_x1 or src_y2 <= src_y1:
            return None

        # 크롭 추출 (경계 벗어나면 제로 패딩)
        crop = np.zeros((side, side, 3), dtype=np.uint8)
        dst_x1 = src_x1 - x1
        dst_y1 = src_y1 - y1
        dst_x2 = dst_x1 + (src_x2 - src_x1)
        dst_y2 = dst_y1 + (src_y2 - src_y1)
        crop[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]

        return crop

    def _compute_circularity(self, crop: NDArray[np.uint8]) -> float:
        """
        크롭 이미지의 원형도 계산.

        원형도 = 4πA / P² (1.0이면 완벽한 원)
        HSV 마스크로 공 영역 추출 후 컨투어 기반 원형도 측정.

        Args:
            crop: 크롭 이미지 (BGR)

        Returns:
            원형도 (0.0 ~ 1.0)
        """
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # 주황색 마스크
        mask = cv2.inRange(hsv, (5, 80, 80), (25, 255, 255))
        # 갈색 마스크 병합
        mask_brown = cv2.inRange(hsv, (10, 50, 50), (30, 200, 200))
        mask = cv2.bitwise_or(mask, mask_brown)

        # 노이즈 제거
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            return 0.0

        # 가장 큰 컨투어의 원형도
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        perimeter = cv2.arcLength(largest, closed=True)

        if perimeter < 1e-6:
            return 0.0

        return float(4.0 * np.pi * area / (perimeter * perimeter))

    def _is_blurred(self, crop: NDArray[np.uint8]) -> bool:
        """
        모션 블러 판정.

        라플라시안 분산이 임계값 미만이면 블러로 판정.

        Args:
            crop: 크롭 이미지 (BGR)

        Returns:
            블러 여부
        """
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return laplacian_var < (self._config.blur_threshold * 100.0)

    def _compute_sharpness(self, crop: NDArray[np.uint8]) -> float:
        """
        선명도 계산 (라플라시안 분산).

        Args:
            crop: 크롭 이미지 (BGR)

        Returns:
            선명도 값 (높을수록 선명)
        """
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _compute_phash(crop: NDArray[np.uint8]) -> int:
        """지각 해시 (pHash) 계산 — utils.image_utils 위임."""
        from utils.image_utils import compute_phash
        return compute_phash(crop, hash_size=_PHASH_SIZE)

    def _is_duplicate(self, phash_val: int) -> bool:
        """
        pHash 기반 중복 검사.

        기존 해시와의 해밍 거리가 임계값 미만이면 중복으로 판정.

        Args:
            phash_val: 새 이미지의 pHash 값

        Returns:
            중복 여부
        """
        threshold = self._config.phash_threshold
        for existing_hash in self._phash_set:
            xor = phash_val ^ existing_hash
            hamming = bin(xor).count("1")
            if hamming < threshold:
                return True
        return False

    # =========================================================================
    # 버퍼 관리
    # =========================================================================

    def _check_auto_flush(self) -> None:
        """버퍼 자동 flush 조건 확인."""
        now = time.monotonic()
        elapsed = now - self._last_flush_time

        should_flush = (
            len(self._buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
            or len(self._buffer) >= self._config.max_buffer_size
        )

        if should_flush:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼의 모든 샘플을 디스크에 기록."""
        if not self._buffer or self._images_dir is None or self._labels_dir is None:
            return

        flushed = 0
        for sample in self._buffer:
            try:
                # 이미지 파일 저장
                img_path = self._images_dir / f"{sample.sample_id}.jpg"
                img_path.write_bytes(sample.image_data)

                # 라벨 파일 저장
                label_path = self._labels_dir / f"{sample.sample_id}.txt"
                label_path.write_text(sample.label_text, encoding="utf-8")

                flushed += 1
            except OSError as exc:
                logger.error(
                    "BallBboxExtractor 디스크 저장 실패 (sample=%s): %s",
                    sample.sample_id, exc,
                )

        self._total_flushed += flushed
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

        logger.debug(
            "BallBboxExtractor flush: %d 샘플 디스크 저장 (누적: %d)",
            flushed, self._total_flushed,
        )

    # =========================================================================
    # 메타데이터
    # =========================================================================

    def _write_metadata(self) -> Path | None:
        """세션 메타데이터 JSON 기록."""
        if self._session_dir is None:
            return None

        metadata = {
            "session_id": self._session_id,
            "game_id": self._game_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "BallBboxExtractor",
            "version": __version__,
            "config": {
                "min_confidence": self._config.min_confidence,
                "min_circularity": self._config.min_circularity,
                "min_sharpness": self._config.min_sharpness,
                "blur_threshold": self._config.blur_threshold,
                "crop_size": self._config.crop_size,
                "phash_threshold": self._config.phash_threshold,
                "dataset_split": self._config.dataset_split.value,
            },
            "statistics": {
                "total_processed": self._total_processed,
                "total_accepted": self._total_accepted,
                "total_flushed": self._total_flushed,
                "acceptance_rate": (
                    self._total_accepted / max(self._total_processed, 1)
                ),
                "filter_stats": dict(self._filter_stats),
            },
        }

        metadata_path = self._session_dir / _METADATA_FILENAME
        try:
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("메타데이터 저장 실패: %s", exc)
            return None

        logger.info("메타데이터 기록: %s", metadata_path)
        return metadata_path

    def _compute_directory_size(self) -> int:
        """세션 디렉토리 전체 크기 (바이트)."""
        if self._session_dir is None or not self._session_dir.exists():
            return 0

        total = 0
        for file_path in self._session_dir.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    # =========================================================================
    # 상태 조회
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_processed(self) -> int:
        """총 처리 프레임 수."""
        return self._total_processed

    @property
    def total_accepted(self) -> int:
        """총 수집 샘플 수."""
        return self._total_accepted

    @property
    def total_flushed(self) -> int:
        """디스크에 저장된 총 샘플 수."""
        return self._total_flushed

    @property
    def buffer_size(self) -> int:
        """현재 버퍼 크기."""
        return len(self._buffer)

    @property
    def acceptance_rate(self) -> float:
        """수집 비율 (accepted / processed)."""
        if self._total_processed == 0:
            return 0.0
        return self._total_accepted / self._total_processed

    @property
    def filter_statistics(self) -> dict[str, int]:
        """필터별 거부 통계 (방어적 복사)."""
        return dict(self._filter_stats)

    def __repr__(self) -> str:
        return (
            f"BallBboxExtractor("
            f"session={self._session_id!r}, "
            f"processed={self._total_processed}, "
            f"accepted={self._total_accepted}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "BallBboxExtractor",
    "BallBboxExtractorConfig",
]

__version__ = "1.0.0"
