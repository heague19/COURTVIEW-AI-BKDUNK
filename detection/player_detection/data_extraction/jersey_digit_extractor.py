# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection/data_extraction
파일: jersey_digit_extractor.py
설명: 등번호 숫자 크롭 추출기
      - 등번호 영역 ROI 크롭 수집
      - 숫자 라벨(0~99) 생성
      - 신뢰도/크기 품질 필터
      - 버퍼 → flush → finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ocr_constants.py: ROI 비율
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - detection/player_detection/models.py: _PlayerCandidate, _JerseyRegion
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
import time
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
from shared.constants.ocr_constants import (
    HIGH_OCR_CONFIDENCE,
    JERSEY_ROI_BOTTOM_OFFSET,
    JERSEY_ROI_LEFT_OFFSET,
    JERSEY_ROI_RIGHT_OFFSET,
    JERSEY_ROI_TOP_OFFSET,
)
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from detection.player_detection.models import (
    _JerseyRegion,
    _PlayerCandidate,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

_CROP_H: Final[int] = 64
_CROP_W: Final[int] = 128
_MIN_CONFIDENCE: Final[float] = HIGH_OCR_CONFIDENCE
_MAX_BUFFER_SIZE: Final[int] = 100
_FLUSH_INTERVAL_SEC: Final[float] = 300.0
_JPEG_QUALITY: Final[int] = 95


# =============================================================================
# 등번호 숫자 추출기
# =============================================================================

class JerseyDigitExtractor:
    """등번호 숫자 크롭 추출기 (OCR 모델 재학습용)."""

    def __init__(self, output_dir: str = "data/extraction/jersey_digit") -> None:
        self._lock = threading.RLock()
        self._output_dir = Path(output_dir)
        self._initialized: bool = False
        self._enabled: bool = False

        self._buffer: list[tuple[NDArray[np.uint8], str]] = []
        self._last_flush_time: float = 0.0
        self._total_extracted: int = 0
        self._total_flushed: int = 0
        self._flush_count: int = 0

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def total_extracted(self) -> int:
        return self._total_extracted

    def initialize(self) -> None:
        """추출기 초기화."""
        with self._lock:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            (self._output_dir / "images").mkdir(exist_ok=True)
            (self._output_dir / "labels").mkdir(exist_ok=True)
            self._buffer.clear()
            self._last_flush_time = time.monotonic()
            self._total_extracted = 0
            self._total_flushed = 0
            self._flush_count = 0
            self._initialized = True
            self._enabled = True

    def extract(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
        jersey_region: _JerseyRegion,
    ) -> bool:
        """
        등번호 크롭 추출.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            jersey_region: 등번호 인식 결과

        Returns:
            추출 성공 여부
        """
        if not self._enabled:
            return False

        with self._lock:
            if not jersey_region.is_valid or jersey_region.number is None:
                return False
            if jersey_region.confidence < _MIN_CONFIDENCE:
                return False

            fh, fw = frame.shape[:2]

            # 등번호 ROI 추출
            y1 = int(candidate.bbox_y + candidate.bbox_h * JERSEY_ROI_TOP_OFFSET)
            y2 = int(candidate.bbox_y + candidate.bbox_h * JERSEY_ROI_BOTTOM_OFFSET)
            x1 = int(candidate.bbox_x + candidate.bbox_w * JERSEY_ROI_LEFT_OFFSET)
            x2 = int(candidate.bbox_x + candidate.bbox_w * JERSEY_ROI_RIGHT_OFFSET)

            x1 = max(0, min(x1, fw - 1))
            x2 = max(x1 + 1, min(x2, fw))
            y1 = max(0, min(y1, fh - 1))
            y2 = max(y1 + 1, min(y2, fh))

            roi = frame[y1:y2, x1:x2]
            if roi.shape[0] < 10 or roi.shape[1] < 10:
                return False

            # 리사이즈
            crop = cv2.resize(roi, (_CROP_W, _CROP_H), interpolation=cv2.INTER_LINEAR)

            # JPEG 인코딩
            success, encoded = cv2.imencode(
                ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
            )
            if not success:
                return False

            label = str(jersey_region.number)
            self._buffer.append((encoded.tobytes(), label))
            self._total_extracted += 1

            if (
                len(self._buffer) >= _MAX_BUFFER_SIZE
                or time.monotonic() - self._last_flush_time > _FLUSH_INTERVAL_SEC
            ):
                self._flush()

            return True

    def _flush(self) -> None:
        """버퍼를 디스크에 기록."""
        if not self._buffer:
            return

        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

        for i, (jpeg_bytes, label) in enumerate(self._buffer):
            fname = f"jersey_{ts}_{self._flush_count:04d}_{i:04d}"
            img_path = self._output_dir / "images" / f"{fname}.jpg"
            lbl_path = self._output_dir / "labels" / f"{fname}.txt"

            img_path.write_bytes(jpeg_bytes)
            lbl_path.write_text(label, encoding="utf-8")

        self._total_flushed += len(self._buffer)
        self._flush_count += 1
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

    def finalize(self) -> ExtractionResult | None:
        """추출 종료 및 결과 반환."""
        try:
            with self._lock:
                self._flush()

                if self._total_flushed == 0:
                    return None

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.JERSEY_DIGIT,
                    total_records=self._total_flushed,
                    split=DatasetSplit.TRAIN,
                )

                return ExtractionResult(
                    metadata=metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._output_dir),
                    upload_status=UploadStatus.PENDING,
                )
        finally:
            self._enabled = False

    def __repr__(self) -> str:
        return (
            f"JerseyDigitExtractor(extracted={self._total_extracted}, "
            f"flushed={self._total_flushed})"
        )


__all__: list[str] = ["JerseyDigitExtractor"]

__version__: str = "1.0.0"
