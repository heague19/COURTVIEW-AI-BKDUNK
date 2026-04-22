# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/court_detection/data_extraction
파일: arena_profile_extractor.py
설명: 경기장 프로필 데이터 추출기
      - 경기장 환경 특성 수집 (조명/바닥색/라인색/카메라각)
      - 호모그래피 품질 추적 (캘리브레이션 신뢰도)
      - 코트 규격 자동 판별 이력 저장
      - 경기장별 최적 파라미터 프로파일 생성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
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

_MAX_PROFILE_HISTORY: Final[int] = 100
_BRIGHTNESS_SAMPLE_INTERVAL: Final[int] = 30  # 프레임 간격
_METADATA_FILENAME: Final[str] = "arena_profile.json"


# =============================================================================
# 경기장 프로필 데이터
# =============================================================================

@dataclass(slots=True)
class _ArenaSnapshot:
    """경기장 환경 스냅샷 (내부용)."""

    frame_index: int
    timestamp: float
    mean_brightness: float  # 평균 밝기 (0~255)
    brightness_std: float  # 밝기 표준편차
    floor_hsv_mean: tuple[float, float, float]  # 코트 바닥 평균 HSV
    line_contrast: float  # 라인-바닥 명암비
    homography_quality: float  # 호모그래피 품질 (0~1)
    detected_standard: str  # 감지된 규격 ("fiba", "nba" 등)
    num_keypoints: int  # 감지된 키포인트 수
    court_type: str  # "full" 또는 "half"


# =============================================================================
# 경기장 프로필 추출기
# =============================================================================

class ArenaProfileExtractor:
    """
    경기장 프로필 데이터 추출기.

    경기 중 경기장 환경 특성을 주기적으로 수집하여
    코트 감지 파라미터 최적화에 활용합니다.

    수집 항목:
        - 조명 조건 (밝기 평균/표준편차)
        - 코트 바닥 색상 (HSV 평균)
        - 라인-바닥 명암비
        - 호모그래피 캘리브레이션 품질
        - 코트 규격 판별 이력
        - 코트 유형 (full/half)

    사용 예시::

        >>> extractor = ArenaProfileExtractor()
        >>> extractor.initialize(output_dir=Path("data/arena"), enabled=True)
        >>> extractor.process_frame(frame, frame_index=0, homography_quality=0.9)
        >>> result = extractor.finalize()
    """

    def __init__(self) -> None:
        """추출기 초기화."""
        self._lock = threading.RLock()
        self._enabled = False
        self._output_dir: Path | None = None
        self._snapshots: deque[_ArenaSnapshot] = deque(
            maxlen=_MAX_PROFILE_HISTORY,
        )
        self._total_processed: int = 0
        self._last_sample_frame: int = -_BRIGHTNESS_SAMPLE_INTERVAL
        logger.info("ArenaProfileExtractor 인스턴스 생성")

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

            if enabled:
                output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(
                "ArenaProfileExtractor 초기화: enabled=%s, dir=%s",
                enabled, output_dir,
            )

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        homography_quality: float = 0.0,
        detected_standard: str = "fiba",
        num_keypoints: int = 0,
        court_type: str = "unknown",
    ) -> bool:
        """
        프레임에서 경기장 환경 데이터 추출.

        샘플링 간격에 따라 주기적으로 수집합니다.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            homography_quality: 호모그래피 품질 (0~1)
            detected_standard: 감지된 규격
            num_keypoints: 감지된 키포인트 수
            court_type: 코트 유형

        Returns:
            수집 여부
        """
        if not self._enabled:
            return False

        # 샘플링 간격 확인
        if (frame_index - self._last_sample_frame) < _BRIGHTNESS_SAMPLE_INTERVAL:
            return False

        self._last_sample_frame = frame_index

        # 밝기 분석
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        brightness_std = float(np.std(gray))

        # 코트 바닥 색상 분석 (중앙 ROI)
        h, w = frame.shape[:2]
        roi_y1 = h // 4
        roi_y2 = 3 * h // 4
        roi_x1 = w // 4
        roi_x2 = 3 * w // 4
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        floor_hsv_mean = (
            float(np.mean(hsv_roi[:, :, 0])),
            float(np.mean(hsv_roi[:, :, 1])),
            float(np.mean(hsv_roi[:, :, 2])),
        )

        # 라인-바닥 명암비 (에지 강도 기반)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = float(np.count_nonzero(edges)) / (h * w)
        line_contrast = min(1.0, edge_ratio * 20.0)  # 정규화

        snapshot = _ArenaSnapshot(
            frame_index=frame_index,
            timestamp=time.time(),
            mean_brightness=mean_brightness,
            brightness_std=brightness_std,
            floor_hsv_mean=floor_hsv_mean,
            line_contrast=line_contrast,
            homography_quality=homography_quality,
            detected_standard=detected_standard,
            num_keypoints=num_keypoints,
            court_type=court_type,
        )

        with self._lock:
            self._snapshots.append(snapshot)
            self._total_processed += 1

        return True

    def finalize(self) -> ExtractionResult:
        """
        추출 완료 및 결과 반환.

        경기장 프로필을 JSON으로 저장합니다.

        Returns:
            ExtractionResult
        """
        with self._lock:
            try:
                total_count = self._total_processed

                if self._output_dir is not None and self._snapshots:
                    self._save_profile()

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.ARENA_PROFILE,
                    total_records=total_count,
                    split=DatasetSplit.TRAIN,
                    description=f"경기장 프로필 스냅샷 {total_count}건",
                )

                result = ExtractionResult(
                    record_count=total_count,
                    metadata=metadata,
                    file_path=str(self._output_dir) if self._output_dir else "",
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "ArenaProfileExtractor 완료: 스냅샷=%d",
                    total_count,
                )

                return result
            finally:
                self._enabled = False

    def get_average_brightness(self) -> float:
        """평균 밝기 반환."""
        with self._lock:
            if not self._snapshots:
                return 0.0
            return float(np.mean([s.mean_brightness for s in self._snapshots]))

    def get_average_homography_quality(self) -> float:
        """평균 호모그래피 품질 반환."""
        with self._lock:
            if not self._snapshots:
                return 0.0
            return float(np.mean([s.homography_quality for s in self._snapshots]))

    def get_dominant_standard(self) -> str:
        """가장 빈번하게 감지된 코트 규격 반환."""
        with self._lock:
            if not self._snapshots:
                return "fiba"
            standards = [s.detected_standard for s in self._snapshots]
            # 최빈값
            counter = Counter(standards)
            return counter.most_common(1)[0][0]

    def reset(self) -> None:
        """추출기 상태 초기화."""
        with self._lock:
            self._snapshots.clear()
            self._total_processed = 0
            self._last_sample_frame = -_BRIGHTNESS_SAMPLE_INTERVAL

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _save_profile(self) -> None:
        """프로필을 JSON으로 저장."""
        if self._output_dir is None:
            return

        snapshots_list = self._snapshots
        profile: dict[str, Any] = {
            "total_snapshots": len(snapshots_list),
            "average_brightness": self.get_average_brightness(),
            "average_homography_quality": self.get_average_homography_quality(),
            "dominant_standard": self.get_dominant_standard(),
            "snapshots": [
                {
                    "frame_index": s.frame_index,
                    "mean_brightness": round(s.mean_brightness, 2),
                    "brightness_std": round(s.brightness_std, 2),
                    "floor_hsv_mean": [round(v, 2) for v in s.floor_hsv_mean],
                    "line_contrast": round(s.line_contrast, 4),
                    "homography_quality": round(s.homography_quality, 4),
                    "detected_standard": s.detected_standard,
                    "num_keypoints": s.num_keypoints,
                    "court_type": s.court_type,
                }
                for s in list(snapshots_list)[-20:]  # 최근 20개만 저장
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        profile_path = self._output_dir / _METADATA_FILENAME
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def __repr__(self) -> str:
        return (
            f"ArenaProfileExtractor(enabled={self._enabled}, "
            f"snapshots={len(self._snapshots)})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "ArenaProfileExtractor",
]

__version__: str = "1.0.0"
