# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: hard_negative_extractor.py
설명: 하드 네거티브 샘플 추출기
      - 공이 아닌 물체가 공으로 오감지된 경우 (거짓 양성)
      - 패턴 검증에서 탈락한 감지를 하드 네거티브로 수집
      - 공 감지 모델 재학습 시 거짓 양성 억제에 활용
      - YOLO 학습 시 background 클래스 샘플로 사용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 검출 파라미터
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/geometry_dto.py: BoundingBox

하드 네거티브 수집 기준:
    1. YOLO 모델이 공으로 감지했으나 (confidence > threshold)
    2. 패턴 검증에서 탈락한 경우:
       - 원형도 미달 (HSV 마스크 후 circularity < 0.7)
       - 색상 미달 (주황/갈색 마스크 비율 < 0.3)
       - 크기 비정상 (너무 크거나 작음)
    3. 또는 직전 프레임에서 추적되지 않은 감지 (이동 불연속)
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
from enum import Enum, unique
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
    BALL_DETECTION_INPUT_SIZE,
    BALL_DETECTION_MIN_CONFIDENCE,
)
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

# 크롭 출력 크기
_CROP_SIZE: Final[int] = BALL_DETECTION_INPUT_SIZE

# JPEG 인코딩 품질
_JPEG_QUALITY: Final[int] = 90

# 하드 네거티브 최대 수집 비율 (양성 대비)
_MAX_NEGATIVE_RATIO: Final[float] = 3.0

# 버퍼 자동 flush 임계값
_BUFFER_FLUSH_COUNT: Final[int] = 50
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 최대 버퍼 크기 (메모리 보호)
_MAX_BUFFER_SIZE: Final[int] = 300

# pHash 유사도 임계값 (중복 방지)
_PHASH_THRESHOLD: Final[int] = 6

# pHash 크기
_PHASH_SIZE: Final[int] = 8

# pHash 집합 최대 크기 (메모리 보호)
_MAX_PHASH_SET_SIZE: Final[int] = 3000


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class HardNegativeExtractorConfig:
    """
    하드 네거티브 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        min_yolo_confidence: YOLO 최소 감지 신뢰도 (이 이상인데 거짓 양성)
        max_negative_ratio: 양성 대비 최대 수집 비율
        crop_size: 크롭 이미지 크기
        jpeg_quality: JPEG 인코딩 품질
        phash_threshold: pHash 중복 판정 임계값
        buffer_flush_count: 버퍼 flush 샘플 수
        buffer_flush_interval_sec: 버퍼 flush 간격 (초)
        max_buffer_size: 최대 버퍼 크기
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/ball_hard_negative"
    min_yolo_confidence: float = BALL_DETECTION_MIN_CONFIDENCE
    max_negative_ratio: float = _MAX_NEGATIVE_RATIO
    crop_size: int = _CROP_SIZE
    jpeg_quality: int = _JPEG_QUALITY
    phash_threshold: int = _PHASH_THRESHOLD
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/ball_hard_negative"
    enabled: bool = True


# =============================================================================
# 거부 사유 열거
# =============================================================================

@unique
class RejectReason(str, Enum):
    """하드 네거티브 거부 사유."""

    CIRCULARITY = "circularity"       # 원형도 미달
    COLOR = "color"                   # 색상 미달
    SIZE = "size"                     # 크기 비정상
    TRACKING = "tracking"             # 추적 불연속
    ASPECT_RATIO = "aspect_ratio"     # 종횡비 비정상

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _HardNegativeSample:
    """버퍼에 저장되는 하드 네거티브 샘플."""

    sample_id: str
    image_data: bytes
    yolo_confidence: float
    reject_reason: str
    reject_detail: str
    frame_index: int
    camera_id: str
    bbox_normalized: tuple[float, float, float, float]  # cx, cy, w, h
    phash: int


# =============================================================================
# 하드 네거티브 추출기
# =============================================================================

class HardNegativeExtractor:
    """
    하드 네거티브 샘플 추출기.

    YOLO 모델이 공으로 감지했으나 후처리 검증에서 탈락한 샘플을 수집합니다.
    이 데이터는 모델 재학습 시 거짓 양성(False Positive) 억제에 사용됩니다.

    수집 대상:
        - 원형도 미달: YOLO 감지 → HSV 마스크 → 원형도 < 0.7
        - 색상 미달: YOLO 감지 → 주황/갈색 비율 < 0.3
        - 크기 비정상: YOLO 감지 → bbox가 너무 크거나 작음
        - 추적 불연속: YOLO 감지 → 이전 프레임과 위치 불일치

    사용 예시::

        >>> config = HardNegativeExtractorConfig()
        >>> extractor = HardNegativeExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> # 패턴 검증 탈락 시
        >>> extractor.process(
        ...     frame=frame,
        ...     bbox=bbox,
        ...     yolo_confidence=0.72,
        ...     reject_reason=RejectReason.CIRCULARITY,
        ...     reject_detail="circularity=0.45",
        ...     frame_index=42,
        ... )
        >>> result = extractor.finalize()
    """

    def __init__(self, config: HardNegativeExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None
        self._images_dir: Path | None = None

        # 버퍼
        self._buffer: list[_HardNegativeSample] = []
        self._phash_set: dict[int, None] = {}  # 삽입 순서 보존 dict
        self._last_flush_time: float = 0.0

        # 양성 카운터 (비율 제한용, 외부에서 갱신)
        self._positive_count: int = 0

        # 통계
        self._total_processed: int = 0
        self._total_accepted: int = 0
        self._total_flushed: int = 0
        self._reason_counts: dict[str, int] = {r.value: 0 for r in RejectReason}

        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, session_id: str, game_id: str) -> None:
        """추출 세션 초기화."""
        with self._lock:
            if not self._config.enabled:
                return

            self._session_id = session_id
            self._game_id = game_id

            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._session_dir = (
                Path(self._config.output_dir) / date_str / session_id
            )
            self._images_dir = self._session_dir / "images"
            self._images_dir.mkdir(parents=True, exist_ok=True)

            self._buffer.clear()
            self._phash_set.clear()
            self._last_flush_time = time.monotonic()
            self._positive_count = 0
            self._total_processed = 0
            self._total_accepted = 0
            self._total_flushed = 0
            self._reason_counts = {r.value: 0 for r in RejectReason}

            self._initialized = True
            logger.info(
                "HardNegativeExtractor 초기화: session=%s", session_id,
            )

    def update_positive_count(self, count: int) -> None:
        """
        양성 샘플 수 갱신 (비율 제한용).

        BallBboxExtractor의 total_accepted와 동기화.

        Args:
            count: 현재 양성 샘플 수
        """
        with self._lock:
            self._positive_count = max(0, count)

    def process(
        self,
        frame: NDArray[np.uint8],
        bbox: BoundingBox,
        yolo_confidence: float,
        reject_reason: str,
        reject_detail: str,
        frame_index: int,
        camera_id: str = "cam_0",
    ) -> bool:
        """
        하드 네거티브 샘플 처리.

        Args:
            frame: 원본 프레임 (BGR, HWC)
            bbox: YOLO가 감지한 바운딩박스
            yolo_confidence: YOLO 감지 신뢰도
            reject_reason: 거부 사유 (RejectReason 상수)
            reject_detail: 거부 상세 정보
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID

        Returns:
            수집 여부
        """
        if not self._initialized or not self._config.enabled:
            return False

        with self._lock:
            self._total_processed += 1

            # YOLO 신뢰도 검증 (너무 낮은 감지는 의미 없음)
            if yolo_confidence < self._config.min_yolo_confidence:
                return False

            # 양성 대비 비율 제한
            max_negatives = int(
                max(self._positive_count, 1) * self._config.max_negative_ratio
            )
            if self._total_accepted >= max_negatives:
                return False

            # 버퍼 크기 제한
            if len(self._buffer) >= self._config.max_buffer_size:
                return False

            # 크롭 추출
            crop = self._extract_crop(frame, bbox)
            if crop is None:
                return False

            # pHash 중복 검사
            phash_val = self._compute_phash(crop)
            if self._is_duplicate(phash_val):
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

            # 정규화 좌표
            h_frame, w_frame = frame.shape[:2]
            cx_norm = (bbox.x + bbox.width / 2) / w_frame
            cy_norm = (bbox.y + bbox.height / 2) / h_frame
            w_norm = bbox.width / w_frame
            h_norm = bbox.height / h_frame

            sample_id = (
                f"hn_{frame_index:08d}_{camera_id}_"
                f"{reject_reason}_{int(yolo_confidence * 1000):04d}"
            )

            sample = _HardNegativeSample(
                sample_id=sample_id,
                image_data=bytes(encoded),
                yolo_confidence=yolo_confidence,
                reject_reason=reject_reason,
                reject_detail=reject_detail,
                frame_index=frame_index,
                camera_id=camera_id,
                bbox_normalized=(cx_norm, cy_norm, w_norm, h_norm),
                phash=phash_val,
            )

            self._buffer.append(sample)
            self._phash_set[phash_val] = None

            # pHash 집합 크기 제한 (삽입 순서 보존, 가장 오래된 것부터 제거)
            if len(self._phash_set) > _MAX_PHASH_SET_SIZE:
                excess = len(self._phash_set) - _MAX_PHASH_SET_SIZE // 2
                keys = list(self._phash_set.keys())[:excess]
                for k in keys:
                    del self._phash_set[k]

            self._total_accepted += 1

            reason_key = reject_reason.value if hasattr(reject_reason, "value") else reject_reason
            if reason_key in self._reason_counts:
                self._reason_counts[reason_key] += 1

            # 자동 flush
            self._check_auto_flush()
            return True

    def finalize(self) -> ExtractionResult | None:
        """추출 세션 종료 및 결과 반환."""
        if not self._initialized or not self._config.enabled:
            return None

        with self._lock:
            try:
                start_time = time.monotonic()

                self._flush_buffer()
                self._write_metadata()

                total_size = self._compute_directory_size()
                processing_time_ms = (time.monotonic() - start_time) * 1000.0

                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                s3_key = (
                    f"{self._config.s3_prefix}/{date_str}/{self._session_id}"
                )

                ds_metadata = DatasetMetadata(
                    dataset_type=DatasetType.BALL_HARD_NEGATIVE,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id],
                    description=(
                        f"하드 네거티브 샘플 "
                        f"(session={self._session_id}, "
                        f"accepted={self._total_flushed})"
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
                    "HardNegativeExtractor 종료: "
                    "처리=%d, 수집=%d, 사유=%s",
                    self._total_processed,
                    self._total_flushed,
                    self._reason_counts,
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
        """바운딩박스 중심 정사각형 크롭 추출."""
        h_frame, w_frame = frame.shape[:2]

        side = int(max(bbox.width, bbox.height) * 2.0)
        if side < 16:
            return None

        cx = int(bbox.x + bbox.width / 2)
        cy = int(bbox.y + bbox.height / 2)

        x1 = cx - side // 2
        y1 = cy - side // 2
        x2 = x1 + side
        y2 = y1 + side

        src_x1 = max(0, x1)
        src_y1 = max(0, y1)
        src_x2 = min(w_frame, x2)
        src_y2 = min(h_frame, y2)

        if src_x2 <= src_x1 or src_y2 <= src_y1:
            return None

        crop = np.zeros((side, side, 3), dtype=np.uint8)
        dst_x1 = src_x1 - x1
        dst_y1 = src_y1 - y1
        dst_x2 = dst_x1 + (src_x2 - src_x1)
        dst_y2 = dst_y1 + (src_y2 - src_y1)
        crop[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]

        return crop

    @staticmethod
    def _compute_phash(crop: NDArray[np.uint8]) -> int:
        """지각 해시 (pHash) 계산 — utils.image_utils 위임."""
        from utils.image_utils import compute_phash
        return compute_phash(crop, hash_size=_PHASH_SIZE)

    def _is_duplicate(self, phash_val: int) -> bool:
        """pHash 기반 중복 검사."""
        for existing in self._phash_set:
            xor = phash_val ^ existing
            if bin(xor).count("1") < self._config.phash_threshold:
                return True
        return False

    # =========================================================================
    # 버퍼 관리
    # =========================================================================

    def _check_auto_flush(self) -> None:
        """버퍼 자동 flush 조건 확인."""
        now = time.monotonic()
        elapsed = now - self._last_flush_time

        if (
            len(self._buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼를 디스크에 기록."""
        if not self._buffer or self._images_dir is None:
            return

        # 이미지 저장
        for sample in self._buffer:
            try:
                img_path = self._images_dir / f"{sample.sample_id}.jpg"
                img_path.write_bytes(sample.image_data)
            except OSError as exc:
                logger.error(
                    "HardNegativeExtractor 이미지 저장 실패 (sample=%s): %s",
                    sample.sample_id, exc,
                )

        # 메타데이터 JSONL
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        jsonl_path = (
            self._session_dir / f"hard_negatives_{timestamp}.jsonl"
            if self._session_dir else None
        )

        if jsonl_path is not None:
            try:
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for sample in self._buffer:
                        record = {
                            "sample_id": sample.sample_id,
                            "yolo_confidence": sample.yolo_confidence,
                            "reject_reason": sample.reject_reason,
                            "reject_detail": sample.reject_detail,
                            "frame_index": sample.frame_index,
                            "camera_id": sample.camera_id,
                            "bbox_normalized": list(sample.bbox_normalized),
                        }
                        f.write(
                            json.dumps(record, ensure_ascii=False) + "\n",
                        )
            except OSError as exc:
                logger.error(
                    "HardNegativeExtractor JSONL 저장 실패: %s", exc,
                )

        flushed = len(self._buffer)
        self._total_flushed += flushed
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

        logger.debug(
            "HardNegativeExtractor flush: %d 샘플 저장 (누적: %d)",
            flushed, self._total_flushed,
        )

    def _write_metadata(self) -> None:
        """세션 메타데이터 기록."""
        if self._session_dir is None:
            return

        metadata = {
            "session_id": self._session_id,
            "game_id": self._game_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "HardNegativeExtractor",
            "version": __version__,
            "config": {
                "min_yolo_confidence": self._config.min_yolo_confidence,
                "max_negative_ratio": self._config.max_negative_ratio,
                "phash_threshold": self._config.phash_threshold,
            },
            "statistics": {
                "total_processed": self._total_processed,
                "total_accepted": self._total_accepted,
                "total_flushed": self._total_flushed,
                "positive_count": self._positive_count,
                "negative_ratio": (
                    self._total_flushed / max(self._positive_count, 1)
                ),
                "reason_counts": dict(self._reason_counts),
            },
        }

        path = self._session_dir / "metadata.json"
        try:
            path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("HardNegativeExtractor 메타데이터 저장 실패: %s", exc)

    def _compute_directory_size(self) -> int:
        """세션 디렉토리 전체 크기."""
        if self._session_dir is None or not self._session_dir.exists():
            return 0
        total = 0
        for fp in self._session_dir.rglob("*"):
            if fp.is_file():
                total += fp.stat().st_size
        return total

    # =========================================================================
    # 상태 조회
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def total_processed(self) -> int:
        return self._total_processed

    @property
    def total_accepted(self) -> int:
        return self._total_accepted

    @property
    def total_flushed(self) -> int:
        return self._total_flushed

    @property
    def reason_counts(self) -> dict[str, int]:
        return dict(self._reason_counts)

    def __repr__(self) -> str:
        return (
            f"HardNegativeExtractor("
            f"session={self._session_id!r}, "
            f"accepted={self._total_accepted}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "HardNegativeExtractor",
    "HardNegativeExtractorConfig",
    "RejectReason",
]

__version__ = "1.0.0"
