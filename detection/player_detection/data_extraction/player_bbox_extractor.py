# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection/data_extraction
파일: player_bbox_extractor.py
설명: 선수 바운딩박스 크롭 추출기
      - 감지된 선수 bbox를 640×640 크롭으로 수집
      - YOLO format 라벨 생성 (class_id cx cy w h)
      - 품질 필터 (신뢰도/크기/종횡비/선명도)
      - 버퍼 축적 → 자동 flush → finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/player_constants.py: 클래스 ID
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - detection/player_detection/models.py: _PlayerCandidate
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
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from detection.player_detection.models import _PlayerCandidate

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

_CROP_SIZE: Final[int] = 640
_MIN_CONFIDENCE: Final[float] = 0.7
_MIN_BBOX_AREA: Final[int] = 2000  # 최소 bbox 면적 (px²)
_MAX_BUFFER_SIZE: Final[int] = 100
_FLUSH_INTERVAL_SEC: Final[float] = 300.0
_JPEG_QUALITY: Final[int] = 95
_SHARPNESS_THRESHOLD: Final[float] = 50.0


# =============================================================================
# 선수 bbox 추출기
# =============================================================================

class PlayerBboxExtractor:
    """
    선수 바운딩박스 크롭 추출기.

    감지된 선수의 bbox를 크롭하여 YOLO 재학습용 데이터로 수집합니다.
    """

    def __init__(self, output_dir: str = "data/extraction/player_bbox") -> None:
        self._lock = threading.RLock()
        self._output_dir = Path(output_dir)
        self._initialized: bool = False
        self._enabled: bool = False

        # 버퍼
        self._buffer: list[tuple[NDArray[np.uint8], str]] = []  # (jpeg, label)
        self._last_flush_time: float = 0.0
        self._total_extracted: int = 0
        self._total_flushed: int = 0
        self._flush_count: int = 0

        logger.info("PlayerBboxExtractor 인스턴스 생성")

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
            logger.info("PlayerBboxExtractor 초기화 완료: %s", self._output_dir)

    def extract(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> bool:
        """
        선수 bbox 크롭 추출.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            추출 성공 여부
        """
        if not self._enabled:
            return False

        with self._lock:
            # 품질 필터
            if candidate.combined_score < _MIN_CONFIDENCE:
                return False
            if candidate.area < _MIN_BBOX_AREA:
                return False

            # 선명도 검사
            fh, fw = frame.shape[:2]
            x1 = max(0, int(candidate.bbox_x))
            y1 = max(0, int(candidate.bbox_y))
            x2 = min(fw, int(candidate.bbox_x + candidate.bbox_w))
            y2 = min(fh, int(candidate.bbox_y + candidate.bbox_h))

            if x2 - x1 < 20 or y2 - y1 < 40:
                return False

            roi = frame[y1:y2, x1:x2]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if sharpness < _SHARPNESS_THRESHOLD:
                return False

            # 크롭 리사이즈
            crop = cv2.resize(roi, (_CROP_SIZE, _CROP_SIZE), interpolation=cv2.INTER_LINEAR)

            # JPEG 인코딩
            success, encoded = cv2.imencode(
                ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
            )
            if not success:
                return False

            # YOLO 라벨 (class_id cx cy w h — 정규화)
            cx_norm = (candidate.center_x - x1) / max(1, x2 - x1)
            cy_norm = (candidate.center_y - y1) / max(1, y2 - y1)
            w_norm = candidate.bbox_w / max(1, x2 - x1)
            h_norm = candidate.bbox_h / max(1, y2 - y1)
            label = f"{candidate.class_id} {cx_norm:.6f} {cy_norm:.6f} {w_norm:.6f} {h_norm:.6f}"

            self._buffer.append((encoded.tobytes(), label))
            self._total_extracted += 1

            # 자동 flush
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
            fname = f"player_{ts}_{self._flush_count:04d}_{i:04d}"
            img_path = self._output_dir / "images" / f"{fname}.jpg"
            lbl_path = self._output_dir / "labels" / f"{fname}.txt"

            img_path.write_bytes(jpeg_bytes)
            lbl_path.write_text(label, encoding="utf-8")

        self._total_flushed += len(self._buffer)
        self._flush_count += 1
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

    def finalize(self) -> ExtractionResult | None:
        """
        추출 종료 및 결과 반환.

        Returns:
            ExtractionResult (데이터 없으면 None)
        """
        try:
            with self._lock:
                self._flush()

                if self._total_flushed == 0:
                    return None

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.PLAYER_BBOX,
                    total_records=self._total_flushed,
                    split=DatasetSplit.TRAIN,
                )

                result = ExtractionResult(
                    metadata=metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._output_dir),
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "PlayerBboxExtractor 종료: %d개 샘플 추출",
                    self._total_flushed,
                )
                return result
        finally:
            self._enabled = False

    def __repr__(self) -> str:
        return (
            f"PlayerBboxExtractor(extracted={self._total_extracted}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = ["PlayerBboxExtractor"]

__version__: str = "1.0.0"
