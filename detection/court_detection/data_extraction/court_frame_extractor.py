# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/court_detection/data_extraction
파일: court_frame_extractor.py
설명: 코트 프레임 데이터 추출기 (호모그래피 대체 자체 학습 모델용)
      - 프레임에서 독립적으로 Hough 라인 추출 → 학습 데이터 수집
      - CourtDetector 의존성 제거 (삭제됨)
      - 라인 키포인트 + 전체 프레임 + 라벨 생성
      - 품질 필터 (라인 수/직선도/해상도/중복)
      - 버퍼 축적 → 자동 flush → ExtractionResult

      목적:
        현재 캘리브레이션은 UI 수동 클릭 → cv2.findHomography 방식.
        이 추출기로 수집한 프레임+라인 데이터로 자체 학습 모델을 만들면
        호모그래피 없이 pixel → court 직접 변환 가능 (GPU 연산 절약).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-29
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata

데이터 흐름:
    프레임 (BGR)
        ↓
    CLAHE 전처리 → Canny 에지 → HoughLinesP
        ↓
    품질 필터 (라인 수 ≥ 4, 해상도, pHash 중복)
        ↓
    전체 프레임 JPEG + 라인 좌표 JSON 생성
        ↓
    버퍼 축적 → 자동 flush (50개 또는 300초)
        ↓
    finalize() → ExtractionResult (PENDING → 학습 파이프라인)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np

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

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_BUFFER_FLUSH_COUNT: Final[int] = 50
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0
_MAX_BUFFER_SIZE: Final[int] = 300
_JPEG_QUALITY: Final[int] = 95
_PHASH_SIMILARITY_THRESHOLD: Final[int] = 10
_MAX_PHASH_SET_SIZE: Final[int] = 3000

# Hough 라인 파라미터
_CANNY_LOW: Final[int] = 50
_CANNY_HIGH: Final[int] = 150
_HOUGH_RHO: Final[float] = 1.0
_HOUGH_THETA: Final[float] = np.pi / 180.0
_HOUGH_THRESHOLD: Final[int] = 80
_HOUGH_MIN_LINE_LENGTH: Final[float] = 80.0
_HOUGH_MAX_LINE_GAP: Final[float] = 15.0
_MIN_LINES_REQUIRED: Final[int] = 4  # 최소 4개 라인 감지 시 수집

_METADATA_FILENAME: Final[str] = "metadata.json"


# =============================================================================
# 프레임 데이터 샘플
# =============================================================================

@dataclass(slots=True)
class _FrameSample:
    """프레임 데이터 샘플 (내부용)."""

    image_data: bytes             # JPEG 인코딩된 전체 프레임
    lines_json: str               # 라인 좌표 JSON
    line_count: int               # 감지된 라인 수
    source_frame_index: int       # 소스 프레임 인덱스
    phash: str                    # 이미지 해시 (중복 방지)
    timestamp: float              # 추출 시각


# =============================================================================
# 코트 프레임 추출기
# =============================================================================

class CourtFrameExtractor:
    """
    코트 프레임 데이터 추출기 (독립 Hough 라인 기반).

    호모그래피 대체 자체 학습 모델 훈련을 위해
    코트가 포함된 프레임 + 자동 감지된 라인 좌표를 수집합니다.
    CourtDetector 의존성 없이 독립적으로 동작합니다.

    사용 예시::

        >>> extractor = CourtFrameExtractor()
        >>> extractor.initialize(output_dir=Path("data/court_frames"), enabled=True)
        >>> extractor.process_frame(frame, frame_index=0)
        >>> result = extractor.finalize()
    """

    def __init__(self) -> None:
        """추출기 초기화."""
        self._lock = threading.RLock()
        self._enabled = False
        self._output_dir: Path | None = None
        self._buffer: list[_FrameSample] = []
        self._phash_set: set[str] = set()
        self._total_flushed: int = 0
        self._total_rejected: int = 0
        self._last_flush_time: float = 0.0
        self._flush_count: int = 0
        # CLAHE 인스턴스 재사용
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        logger.info("CourtFrameExtractor 인스턴스 생성")

    def initialize(
        self,
        output_dir: Path,
        enabled: bool = True,
    ) -> None:
        """
        추출기 초기화.

        Args:
            output_dir: 출력 디렉토리
            enabled: 활성화 여부
        """
        with self._lock:
            self._enabled = enabled
            self._output_dir = output_dir
            self._last_flush_time = time.monotonic()

            if enabled:
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "images").mkdir(exist_ok=True)
                (output_dir / "labels").mkdir(exist_ok=True)

            logger.info(
                "CourtFrameExtractor 초기화: enabled=%s, dir=%s",
                enabled, output_dir,
            )

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
    ) -> int:
        """
        프레임에서 독립적으로 Hough 라인 추출 + 수집.

        CourtDetector 없이 프레임만으로 동작합니다.
        CLAHE 전처리 → Canny → HoughLinesP → 품질 필터.

        Args:
            frame: BGR 프레임
            frame_index: 프레임 인덱스

        Returns:
            이번 호출에서 수집된 샘플 수 (0 또는 1)
        """
        if not self._enabled:
            return 0

        # 1. CLAHE 전처리 + Canny 에지
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = self._clahe.apply(gray)
        edges = cv2.Canny(enhanced, _CANNY_LOW, _CANNY_HIGH)

        # 2. HoughLinesP 라인 감지
        raw_lines = cv2.HoughLinesP(
            edges,
            rho=_HOUGH_RHO,
            theta=_HOUGH_THETA,
            threshold=_HOUGH_THRESHOLD,
            minLineLength=_HOUGH_MIN_LINE_LENGTH,
            maxLineGap=_HOUGH_MAX_LINE_GAP,
        )

        if raw_lines is None or len(raw_lines) < _MIN_LINES_REQUIRED:
            self._total_rejected += 1
            return 0

        # 3. 라인 좌표 추출
        lines: list[dict[str, float]] = []
        for line in raw_lines:
            x1, y1, x2, y2 = line[0]
            length = float(np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))
            lines.append({
                "x1": float(x1), "y1": float(y1),
                "x2": float(x2), "y2": float(y2),
                "length": length,
            })

        # 4. JPEG 인코딩
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]
        success, encoded = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return 0

        image_data = encoded.tobytes()

        # 5. pHash 중복 체크
        phash = hashlib.md5(image_data[:4096]).hexdigest()
        with self._lock:
            if phash in self._phash_set:
                self._total_rejected += 1
                return 0
            if len(self._phash_set) >= _MAX_PHASH_SET_SIZE:
                self._phash_set.clear()
            self._phash_set.add(phash)

        # 6. 라인 좌표 JSON
        lines_json = json.dumps(lines, ensure_ascii=False)

        # 7. 버퍼에 추가
        sample = _FrameSample(
            image_data=image_data,
            lines_json=lines_json,
            line_count=len(lines),
            source_frame_index=frame_index,
            phash=phash,
            timestamp=time.time(),
        )

        with self._lock:
            if len(self._buffer) < _MAX_BUFFER_SIZE:
                self._buffer.append(sample)

        # 자동 flush 확인
        self._check_auto_flush()

        return 1

    def finalize(self) -> ExtractionResult:
        """
        추출 완료 및 결과 반환.

        Returns:
            ExtractionResult
        """
        with self._lock:
            try:
                if self._buffer:
                    self._flush_buffer()

                total_count = self._total_flushed
                metadata = DatasetMetadata(
                    dataset_type=DatasetType.COURT_LINE,
                    total_records=total_count,
                    split=DatasetSplit.TRAIN,
                    description=f"코트 프레임 + Hough 라인 학습 데이터 {total_count}건",
                )

                result = ExtractionResult(
                    record_count=total_count,
                    metadata=metadata,
                    file_path=str(self._output_dir) if self._output_dir else "",
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "CourtFrameExtractor 완료: 수집=%d, 거부=%d",
                    total_count, self._total_rejected,
                )

                return result
            finally:
                self._enabled = False

    def reset(self) -> None:
        """추출기 상태 초기화."""
        with self._lock:
            self._buffer.clear()
            self._phash_set.clear()
            self._total_flushed = 0
            self._total_rejected = 0
            self._flush_count = 0
            self._last_flush_time = time.monotonic()

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _check_auto_flush(self) -> None:
        """자동 flush 조건 확인."""
        with self._lock:
            elapsed = time.monotonic() - self._last_flush_time
            if (
                len(self._buffer) >= _BUFFER_FLUSH_COUNT
                or elapsed >= _BUFFER_FLUSH_INTERVAL_SEC
            ):
                if self._buffer:
                    self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼를 디스크에 저장."""
        if not self._output_dir or not self._buffer:
            return

        images_dir = self._output_dir / "images"
        labels_dir = self._output_dir / "labels"

        for sample in self._buffer:
            file_id = (
                f"court_frame_{self._flush_count:06d}"
                f"_{sample.source_frame_index:06d}"
            )

            # 전체 프레임 이미지 저장
            img_path = images_dir / f"{file_id}.jpg"
            img_path.write_bytes(sample.image_data)

            # 라인 좌표 JSON 라벨 저장
            lbl_path = labels_dir / f"{file_id}.json"
            lbl_path.write_text(sample.lines_json, encoding="utf-8")

            self._total_flushed += 1

        self._flush_count += 1
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"CourtFrameExtractor(enabled={self._enabled}, "
            f"buffer={len(self._buffer)}, flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "CourtFrameExtractor",
]

__version__: str = "1.0.0"
