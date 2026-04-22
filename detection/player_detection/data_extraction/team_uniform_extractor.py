# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection/data_extraction
파일: team_uniform_extractor.py
설명: 유니폼 크롭 추출기
      - 가슴 영역 ROI 크롭 수집
      - 팀 라벨(team_a/team_b) 생성
      - 색상 품질 필터 (유효 픽셀, 피부색 비율)
      - 버퍼 → flush → finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/player_constants.py: ROI 비율, 피부색 범위
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/player_dto.py: Team
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
from shared.constants.player_constants import (
    CHEST_CROP_X_END,
    CHEST_CROP_X_START,
    CHEST_CROP_Y_END,
    CHEST_CROP_Y_START,
    PLAYER_CLASS_ID_PLAYER,
)
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from shared.dto.player_dto import Team
from detection.player_detection.models import _PlayerCandidate

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

_CROP_SIZE: Final[int] = 128
_MIN_ROI_PIXELS: Final[int] = 200
_MAX_SKIN_RATIO: Final[float] = 0.5
_MAX_BUFFER_SIZE: Final[int] = 100
_FLUSH_INTERVAL_SEC: Final[float] = 300.0
_JPEG_QUALITY: Final[int] = 95


# =============================================================================
# 유니폼 크롭 추출기
# =============================================================================

class TeamUniformExtractor:
    """유니폼 가슴 영역 크롭 추출기 (팀 분류기 재학습용)."""

    def __init__(self, output_dir: str = "data/extraction/team_uniform") -> None:
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
        team: Team,
    ) -> bool:
        """
        유니폼 크롭 추출.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            team: 팀 분류 결과

        Returns:
            추출 성공 여부
        """
        if not self._enabled:
            return False

        with self._lock:
            # 선수만 추출
            if candidate.class_id != PLAYER_CLASS_ID_PLAYER:
                return False
            if not team.is_known:
                return False

            fh, fw = frame.shape[:2]

            # 가슴 ROI 추출
            y1 = int(candidate.bbox_y + candidate.bbox_h * CHEST_CROP_Y_START)
            y2 = int(candidate.bbox_y + candidate.bbox_h * CHEST_CROP_Y_END)
            x1 = int(candidate.bbox_x + candidate.bbox_w * CHEST_CROP_X_START)
            x2 = int(candidate.bbox_x + candidate.bbox_w * CHEST_CROP_X_END)

            x1 = max(0, min(x1, fw - 1))
            x2 = max(x1 + 1, min(x2, fw))
            y1 = max(0, min(y1, fh - 1))
            y2 = max(y1 + 1, min(y2, fh))

            roi = frame[y1:y2, x1:x2]
            if roi.shape[0] * roi.shape[1] < _MIN_ROI_PIXELS:
                return False

            # 피부색 비율 필터 (팔/얼굴 노이즈 제거)
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            skin_mask = cv2.inRange(
                hsv_roi,
                np.array([0, 30, 60], dtype=np.uint8),
                np.array([25, 170, 230], dtype=np.uint8),
            )
            skin_ratio = float(np.count_nonzero(skin_mask)) / max(
                roi.shape[0] * roi.shape[1], 1,
            )
            if skin_ratio > _MAX_SKIN_RATIO:
                return False

            # 리사이즈
            crop = cv2.resize(roi, (_CROP_SIZE, _CROP_SIZE), interpolation=cv2.INTER_LINEAR)

            # JPEG 인코딩
            success, encoded = cv2.imencode(
                ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
            )
            if not success:
                return False

            label = team.value
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
            fname = f"uniform_{ts}_{self._flush_count:04d}_{i:04d}"
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
                    dataset_type=DatasetType.TEAM_UNIFORM,
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
            f"TeamUniformExtractor(extracted={self._total_extracted}, "
            f"flushed={self._total_flushed})"
        )


__all__: list[str] = ["TeamUniformExtractor"]

__version__: str = "1.0.0"
