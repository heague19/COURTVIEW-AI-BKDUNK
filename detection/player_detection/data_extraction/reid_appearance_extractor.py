# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection/data_extraction
파일: reid_appearance_extractor.py
설명: 외관 크롭 쌍 추출기
      - 동일 인물의 다른 프레임/뷰 크롭 쌍 수집
      - positive pair (같은 인물) 라벨 생성
      - 크기/선명도 품질 필터
      - 버퍼 → flush → finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/reid_constants.py: 입력 크기
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
from collections import defaultdict
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
from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER
from shared.constants.reid_constants import (
    BBOX_EXPANSION_RATIO,
    MIN_BBOX_SIZE,
    REID_INPUT_SIZE,
)
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

_CROP_H: Final[int] = REID_INPUT_SIZE[0]  # 256
_CROP_W: Final[int] = REID_INPUT_SIZE[1]  # 128
_MAX_BUFFER_SIZE: Final[int] = 50  # 쌍 단위
_FLUSH_INTERVAL_SEC: Final[float] = 300.0
_JPEG_QUALITY: Final[int] = 95
_PAIR_INTERVAL_FRAMES: Final[int] = 10  # 쌍 수집 프레임 간격
_MAX_PAIRS_PER_PERSON: Final[int] = 20
_SHARPNESS_THRESHOLD: Final[float] = 40.0


# =============================================================================
# 외관 크롭 쌍 추출기
# =============================================================================

class ReIDAppearanceExtractor:
    """외관 크롭 쌍 추출기 (Re-ID 모델 재학습용)."""

    def __init__(self, output_dir: str = "data/extraction/reid_appearance") -> None:
        self._lock = threading.RLock()
        self._output_dir = Path(output_dir)
        self._initialized: bool = False
        self._enabled: bool = False

        # 인물별 최근 크롭 저장 (쌍 생성용)
        self._person_last_crop: dict[int, tuple[NDArray[np.uint8], int]] = {}

        # 쌍 버퍼: (anchor_jpeg, positive_jpeg, person_id)
        self._pair_buffer: list[tuple[bytes, bytes, int]] = []
        self._person_pair_count: dict[int, int] = defaultdict(int)
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
            (self._output_dir / "anchor").mkdir(exist_ok=True)
            (self._output_dir / "positive").mkdir(exist_ok=True)
            (self._output_dir / "labels").mkdir(exist_ok=True)
            self._person_last_crop.clear()
            self._pair_buffer.clear()
            self._person_pair_count.clear()
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
        person_id: int,
        frame_index: int,
    ) -> bool:
        """
        외관 크롭 추출 + 쌍 생성.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            person_id: 인물 ID (ReID 또는 track)
            frame_index: 프레임 인덱스

        Returns:
            쌍 생성 성공 여부
        """
        if not self._enabled:
            return False

        with self._lock:
            if candidate.class_id != PLAYER_CLASS_ID_PLAYER:
                return False
            if self._person_pair_count[person_id] >= _MAX_PAIRS_PER_PERSON:
                return False

            # bbox 크롭
            crop = self._crop_person(candidate, frame)
            if crop is None:
                return False

            # 선명도 검사
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if sharpness < _SHARPNESS_THRESHOLD:
                return False

            # 리사이즈
            resized = cv2.resize(crop, (_CROP_W, _CROP_H), interpolation=cv2.INTER_LINEAR)

            # 이전 크롭과 쌍 생성
            last = self._person_last_crop.get(person_id)
            if last is not None:
                last_crop, last_frame = last
                if frame_index - last_frame >= _PAIR_INTERVAL_FRAMES:
                    # 쌍 생성
                    success_a, enc_a = cv2.imencode(
                        ".jpg", last_crop, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
                    )
                    success_p, enc_p = cv2.imencode(
                        ".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
                    )

                    if success_a and success_p:
                        self._pair_buffer.append(
                            (enc_a.tobytes(), enc_p.tobytes(), person_id),
                        )
                        self._total_extracted += 1
                        self._person_pair_count[person_id] += 1

                    self._person_last_crop[person_id] = (resized.copy(), frame_index)
            else:
                self._person_last_crop[person_id] = (resized.copy(), frame_index)

            # 자동 flush
            if (
                len(self._pair_buffer) >= _MAX_BUFFER_SIZE
                or time.monotonic() - self._last_flush_time > _FLUSH_INTERVAL_SEC
            ):
                self._flush()

            return self._total_extracted > 0

    @staticmethod
    def _crop_person(
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> NDArray[np.uint8] | None:
        """bbox 크롭 (확장 + 클리핑)."""
        fh, fw = frame.shape[:2]

        cx = candidate.center_x
        cy = candidate.center_y
        half_w = candidate.bbox_w * BBOX_EXPANSION_RATIO / 2.0
        half_h = candidate.bbox_h * BBOX_EXPANSION_RATIO / 2.0

        x1 = max(0, int(cx - half_w))
        y1 = max(0, int(cy - half_h))
        x2 = min(fw, int(cx + half_w))
        y2 = min(fh, int(cy + half_h))

        if x2 - x1 < MIN_BBOX_SIZE[1] or y2 - y1 < MIN_BBOX_SIZE[0]:
            return None

        return frame[y1:y2, x1:x2].copy()

    def _flush(self) -> None:
        """버퍼를 디스크에 기록."""
        if not self._pair_buffer:
            return

        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

        for i, (anchor_bytes, positive_bytes, pid) in enumerate(self._pair_buffer):
            fname = f"reid_{ts}_{self._flush_count:04d}_{i:04d}"
            anchor_path = self._output_dir / "anchor" / f"{fname}.jpg"
            positive_path = self._output_dir / "positive" / f"{fname}.jpg"
            label_path = self._output_dir / "labels" / f"{fname}.txt"

            anchor_path.write_bytes(anchor_bytes)
            positive_path.write_bytes(positive_bytes)
            label_path.write_text(str(pid), encoding="utf-8")

        self._total_flushed += len(self._pair_buffer)
        self._flush_count += 1
        self._pair_buffer.clear()
        self._last_flush_time = time.monotonic()

    def finalize(self) -> ExtractionResult | None:
        """추출 종료 및 결과 반환."""
        try:
            with self._lock:
                self._flush()

                if self._total_flushed == 0:
                    return None

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.REID_APPEARANCE,
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
            self._person_last_crop.clear()
            self._person_pair_count.clear()
            self._enabled = False

    def __repr__(self) -> str:
        return (
            f"ReIDAppearanceExtractor(extracted={self._total_extracted}, "
            f"flushed={self._total_flushed})"
        )


__all__: list[str] = ["ReIDAppearanceExtractor"]

__version__: str = "1.0.0"
