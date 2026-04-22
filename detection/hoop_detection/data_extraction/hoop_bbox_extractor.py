# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection/data_extraction
파일: hoop_bbox_extractor.py
설명: 골대 바운딩박스 크롭 추출기
      - 감지된 림/백보드 바운딩박스를 640×640 크롭으로 수집
      - YOLO format 라벨 생성 (class_id cx cy w h)
      - 4중 품질 필터 (신뢰도/종횡비/크기/pHash 중복)
      - 버퍼 축적 → 자동 flush (100개 또는 300초)
      - finalize() → ExtractionResult (PENDING → S3 업로드 대기)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0

의존성:
    - shared/constants/hoop_constants.py: 검출 파라미터
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/geometry_dto.py: BoundingBox
    - shared/interfaces/detector_interface.py: HoopDetection

데이터 흐름:
    HoopDetector.detect_hoops() → HoopDetection
        ↓
    4중 필터 (신뢰도≥0.7, 종횡비, 크기, pHash 중복)
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
from dataclasses import asdict, dataclass
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
from shared.constants.hoop_constants import (
    HOOP_BACKBOARD_ASPECT_RATIO_MAX,
    HOOP_BACKBOARD_ASPECT_RATIO_MIN,
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_RIM,
    HOOP_DETECTION_CONFIDENCE_THRESHOLD,
    HOOP_DETECTION_INPUT_SIZE,
)
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from shared.dto.geometry_dto import BoundingBox
from shared.interfaces.detector_interface import HoopDetection

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

# 버퍼 자동 flush 임계값
_BUFFER_FLUSH_COUNT: Final[int] = 100
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 크롭 출력 크기
_CROP_SIZE: Final[int] = HOOP_DETECTION_INPUT_SIZE

# JPEG 인코딩 품질
_JPEG_QUALITY: Final[int] = 95

# pHash 유사도 임계값
_PHASH_SIMILARITY_THRESHOLD: Final[int] = 8
_PHASH_SIZE: Final[int] = 8

# 메모리 보호
_MAX_BUFFER_SIZE: Final[int] = 500
_MAX_PHASH_SET_SIZE: Final[int] = 5000

# 최소/최대 bbox 크기 (프레임 대비)
_MIN_BBOX_SIZE_PX: Final[int] = 20
_MAX_BBOX_SIZE_PX: Final[int] = 500

_METADATA_FILENAME: Final[str] = "metadata.json"


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class HoopBboxExtractorConfig:
    """
    골대 바운딩박스 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        min_confidence: 최소 감지 신뢰도
        crop_size: 크롭 이미지 크기
        jpeg_quality: JPEG 인코딩 품질
        phash_threshold: pHash 중복 판정 임계값
        buffer_flush_count: 버퍼 flush 샘플 수
        buffer_flush_interval_sec: 버퍼 flush 간격 (초)
        max_buffer_size: 최대 버퍼 크기 (메모리 보호)
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/hoop"
    min_confidence: float = HOOP_DETECTION_CONFIDENCE_THRESHOLD
    crop_size: int = _CROP_SIZE
    jpeg_quality: int = _JPEG_QUALITY
    phash_threshold: int = _PHASH_SIMILARITY_THRESHOLD
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/hoop"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _HoopBboxSample:
    """버퍼에 저장되는 단일 샘플."""

    sample_id: str
    image_data: bytes
    label_text: str
    confidence: float
    class_id: int
    frame_index: int
    camera_id: str
    phash: int


# =============================================================================
# 골대 바운딩박스 추출기
# =============================================================================

class HoopBboxExtractor:
    """
    골대 바운딩박스 크롭 추출기.

    HoopDetector의 감지 결과에서 고품질 림/백보드 바운딩박스를
    수집하여 YOLO 재학습용 데이터셋을 생성합니다.

    4중 품질 필터:
        1. 신뢰도 필터: confidence ≥ threshold
        2. 종횡비 필터: 백보드 종횡비 범위 내
        3. 크기 필터: bbox 크기 범위 내
        4. pHash 중복 필터: 해밍 거리 ≥ threshold

    사용 예시::

        >>> config = HoopBboxExtractorConfig(output_dir="data/hoop")
        >>> extractor = HoopBboxExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> extractor.process(frame, hoop, frame_index=42, camera_id="cam_0")
        >>> result = extractor.finalize()
    """

    def __init__(self, config: HoopBboxExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None
        self._images_dir: Path | None = None
        self._labels_dir: Path | None = None

        # 버퍼
        self._buffer: list[_HoopBboxSample] = []
        # 삽입 순서 보존 dict (오래된 것부터 제거 가능)
        self._phash_set: dict[int, None] = {}
        self._last_flush_time: float = 0.0

        # 통계
        self._total_processed: int = 0
        self._total_accepted: int = 0
        self._total_flushed: int = 0
        self._filter_stats: dict[str, int] = {
            "confidence_reject": 0,
            "aspect_reject": 0,
            "size_reject": 0,
            "phash_reject": 0,
        }

        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_processed(self) -> int:
        """총 처리 수."""
        return self._total_processed

    @property
    def total_accepted(self) -> int:
        """총 수집 수."""
        return self._total_accepted

    def initialize(self, session_id: str, game_id: str) -> None:
        """
        추출 세션 초기화.

        Args:
            session_id: 세션 식별자
            game_id: 경기 식별자
        """
        with self._lock:
            if not self._config.enabled:
                logger.info("HoopBboxExtractor 비활성화 상태")
                return

            self._session_id = session_id
            self._game_id = game_id

            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._session_dir = (
                Path(self._config.output_dir) / date_str / session_id
            )
            self._images_dir = self._session_dir / "images"
            self._labels_dir = self._session_dir / "labels"
            self._images_dir.mkdir(parents=True, exist_ok=True)
            self._labels_dir.mkdir(parents=True, exist_ok=True)

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
                "HoopBboxExtractor 초기화: session=%s, dir=%s",
                session_id, self._session_dir,
            )

    def process(
        self,
        frame: NDArray[np.uint8],
        hoop: HoopDetection,
        confidence: float,
        class_id: int,
        frame_index: int,
        camera_id: str = "cam_0",
    ) -> bool:
        """
        단일 감지 결과 처리.

        Args:
            frame: 원본 프레임 (BGR, HWC)
            hoop: 골대 감지 결과
            confidence: 감지 신뢰도
            class_id: 클래스 ID (0=rim, 1=backboard)
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID

        Returns:
            수집 여부
        """
        if not self._initialized or not self._config.enabled:
            return False

        with self._lock:
            self._total_processed += 1

            bb = hoop.bounding_box

            # 1. 신뢰도 필터
            if confidence < self._config.min_confidence:
                self._filter_stats["confidence_reject"] += 1
                return False

            # 2. 종횡비 필터 (백보드만)
            if class_id == HOOP_CLASS_ID_BACKBOARD:
                ar = bb.width / max(bb.height, 1)
                if not (HOOP_BACKBOARD_ASPECT_RATIO_MIN <= ar <= HOOP_BACKBOARD_ASPECT_RATIO_MAX):
                    self._filter_stats["aspect_reject"] += 1
                    return False

            # 3. 크기 필터
            size = max(bb.width, bb.height)
            if size < _MIN_BBOX_SIZE_PX or size > _MAX_BBOX_SIZE_PX:
                self._filter_stats["size_reject"] += 1
                return False

            # 4. 크롭 추출
            h_frame, w_frame = frame.shape[:2]
            x1 = max(0, int(bb.x))
            y1 = max(0, int(bb.y))
            x2 = min(w_frame, int(bb.x + bb.width))
            y2 = min(h_frame, int(bb.y + bb.height))

            if x2 - x1 < 5 or y2 - y1 < 5:
                self._filter_stats["size_reject"] += 1
                return False

            crop = frame[y1:y2, x1:x2]

            # 5. pHash 중복 검사
            phash = self._compute_phash(crop)
            if self._is_duplicate(phash):
                self._filter_stats["phash_reject"] += 1
                return False

            # 6. 크롭 리사이즈 + JPEG 인코딩
            resized = cv2.resize(
                crop,
                (self._config.crop_size, self._config.crop_size),
                interpolation=cv2.INTER_AREA,
            )
            success, encoded = cv2.imencode(
                ".jpg", resized,
                [cv2.IMWRITE_JPEG_QUALITY, self._config.jpeg_quality],
            )
            if not success:
                return False

            # 7. YOLO 라벨 생성 (정규화 좌표)
            cx = (x1 + x2) / 2.0 / w_frame
            cy = (y1 + y2) / 2.0 / h_frame
            bw = (x2 - x1) / w_frame
            bh = (y2 - y1) / h_frame
            label = f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"

            # 8. 버퍼 추가
            sample_id = f"hoop_{frame_index:08d}_{camera_id}_{class_id}"
            sample = _HoopBboxSample(
                sample_id=sample_id,
                image_data=encoded.tobytes(),
                label_text=label,
                confidence=confidence,
                class_id=class_id,
                frame_index=frame_index,
                camera_id=camera_id,
                phash=phash,
            )
            self._buffer.append(sample)
            self._phash_set[phash] = None
            self._total_accepted += 1

            # 메모리 보호 (삽입 순서 보존 dict → 가장 오래된 것부터 제거)
            if len(self._phash_set) > _MAX_PHASH_SET_SIZE:
                excess = len(self._phash_set) - _MAX_PHASH_SET_SIZE // 2
                keys = list(self._phash_set.keys())[:excess]
                for k in keys:
                    del self._phash_set[k]

            # 자동 flush 조건 확인
            self._check_auto_flush()

            return True

    def finalize(self) -> ExtractionResult | None:
        """
        추출 세션 종료 및 결과 반환.

        Returns:
            ExtractionResult 또는 None
        """
        if not self._initialized:
            return None

        with self._lock:
            try:
                # 잔여 버퍼 flush
                self._flush_buffer()

                # 메타데이터 저장
                metadata = DatasetMetadata(
                    dataset_type=DatasetType.HOOP_BBOX,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id] if self._game_id else [],
                    description=(
                        f"COURTVIEW_hoop bbox 추출 | "
                        f"session={self._session_id} | "
                        f"classes=rim,backboard | "
                        f"processed={self._total_processed} | "
                        f"accepted={self._total_accepted}"
                    ),
                )

                if self._session_dir is not None:
                    meta_path = self._session_dir / _METADATA_FILENAME
                    meta_dict = asdict(metadata)
                    # datetime/UUID → 문자열 변환
                    meta_dict["dataset_id"] = str(meta_dict["dataset_id"])
                    meta_dict["created_at"] = meta_dict["created_at"].isoformat()
                    meta_path.write_text(
                        json.dumps(meta_dict, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                result = ExtractionResult(
                    game_id=self._game_id or "",
                    metadata=metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._session_dir) if self._session_dir else "",
                    upload_status=UploadStatus.PENDING,
                    s3_key=(
                        f"{self._config.s3_prefix}/"
                        f"{self._session_id}/"
                    ),
                )

                logger.info(
                    "HoopBboxExtractor 종료: 처리=%d, 수집=%d, flush=%d",
                    self._total_processed, self._total_accepted, self._total_flushed,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    @staticmethod
    def _compute_phash(image: NDArray[np.uint8]) -> int:
        """지각 해시 (pHash) 계산 — utils.image_utils 위임."""
        from utils.image_utils import compute_phash
        return compute_phash(image, hash_size=_PHASH_SIZE)

    def _is_duplicate(self, phash: int) -> bool:
        """
        pHash 기반 중복 검사.

        Args:
            phash: 해시값

        Returns:
            중복 여부
        """
        threshold = self._config.phash_threshold
        for existing in self._phash_set:
            hamming = bin(phash ^ existing).count("1")
            if hamming < threshold:
                return True
        return False

    def _check_auto_flush(self) -> None:
        """버퍼 자동 flush 조건 확인."""
        elapsed = time.monotonic() - self._last_flush_time
        if (
            len(self._buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼 내 샘플을 디스크에 기록."""
        if not self._buffer or self._images_dir is None:
            return

        for sample in self._buffer:
            img_path = self._images_dir / f"{sample.sample_id}.jpg"
            lbl_path = self._labels_dir / f"{sample.sample_id}.txt"

            img_path.write_bytes(sample.image_data)
            lbl_path.write_text(sample.label_text, encoding="utf-8")

        self._total_flushed += len(self._buffer)
        logger.debug(
            "HoopBboxExtractor flush: %d 샘플 기록", len(self._buffer),
        )
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"HoopBboxExtractor(processed={self._total_processed}, "
            f"accepted={self._total_accepted}, flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "HoopBboxExtractor",
    "HoopBboxExtractorConfig",
]

__version__: str = "1.0.0"
