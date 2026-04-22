# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/court_detection/data_extraction
파일: zone_extractor.py
설명: 구역 히트맵/분포 데이터 추출기
      - 선수/공 위치를 구역별로 축적
      - 21구역 히트맵 및 점유 빈도 생성
      - 슛 로케이션 분석용 데이터 수집
      - finalize() → 구역 통계 ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/court_constants.py: CourtZone
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.court_constants import (
    COURT_LENGTH_M,
    COURT_WIDTH_M,
    CourtZone,
)
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

_MAX_POSITION_BUFFER: Final[int] = 10000
_HEATMAP_RESOLUTION: Final[int] = 100  # 히트맵 해상도 (100x100 셀)
_METADATA_FILENAME: Final[str] = "zone_stats.json"


# =============================================================================
# 구역 추출기
# =============================================================================

class ZoneExtractor:
    """
    구역 히트맵/분포 데이터 추출기.

    선수 및 공의 코트 좌표를 구역별로 축적하여
    21구역 히트맵, 점유 빈도, 슛 로케이션 데이터를 생성합니다.

    사용 예시::

        >>> extractor = ZoneExtractor()
        >>> extractor.initialize(output_dir=Path("data/zones"), enabled=True)
        >>> extractor.record_position(court_xy=(5.0, 7.5), zone=CourtZone.PAINT_CENTER)
        >>> result = extractor.finalize()
    """

    def __init__(self) -> None:
        """추출기 초기화."""
        self._lock = threading.RLock()
        self._enabled = False
        self._output_dir: Path | None = None
        # 구역별 위치 카운트 (str 키 = zone.value)
        self._zone_counts: dict[str, int] = {z.value: 0 for z in CourtZone}
        # 히트맵 (2D 밀도)
        self._heatmap: NDArray[np.float64] | None = None
        # 전체 기록 수
        self._total_records: int = 0
        logger.info("ZoneExtractor 인스턴스 생성")

    def initialize(
        self,
        output_dir: Path,
        enabled: bool = True,
        court_length: float = COURT_LENGTH_M,
        court_width: float = COURT_WIDTH_M,
    ) -> None:
        """
        추출기 초기화.

        Args:
            output_dir: 출력 디렉토리
            enabled: 활성화 여부
            court_length: 코트 길이 (미터)
            court_width: 코트 너비 (미터)
        """
        with self._lock:
            self._enabled = enabled
            self._output_dir = output_dir
            self._heatmap = np.zeros(
                (_HEATMAP_RESOLUTION, _HEATMAP_RESOLUTION),
                dtype=np.float64,
            )
            self._court_length = court_length
            self._court_width = court_width

            if enabled:
                output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(
                "ZoneExtractor 초기화: enabled=%s, dir=%s",
                enabled, output_dir,
            )

    def record_position(
        self,
        court_xy: tuple[float, float],
        zone: CourtZone | None = None,
        entity_type: str = "player",
    ) -> None:
        """
        코트 좌표를 기록.

        Args:
            court_xy: 코트 좌표 (x, y) - 미터
            zone: 구역 (None이면 히트맵만 기록)
            entity_type: 엔티티 타입 ("player", "ball")
        """
        if not self._enabled:
            return

        with self._lock:
            # 히트맵 갱신
            if self._heatmap is not None:
                x, y = court_xy
                # 코트 좌표 → 히트맵 인덱스
                col = int(
                    np.clip(
                        x / self._court_length * _HEATMAP_RESOLUTION,
                        0, _HEATMAP_RESOLUTION - 1,
                    ),
                )
                row = int(
                    np.clip(
                        y / self._court_width * _HEATMAP_RESOLUTION,
                        0, _HEATMAP_RESOLUTION - 1,
                    ),
                )
                self._heatmap[row, col] += 1.0

            # 구역 카운트 갱신
            if zone is not None:
                zone_key = zone.value if hasattr(zone, "value") else str(zone)
                if zone_key in self._zone_counts:
                    self._zone_counts[zone_key] += 1

            self._total_records += 1

    def record_batch(
        self,
        positions: list[tuple[tuple[float, float], CourtZone | None]],
    ) -> None:
        """
        복수 좌표를 일괄 기록.

        Args:
            positions: [(코트좌표, 구역 또는 None), ...] 목록
        """
        for court_xy, zone in positions:
            self.record_position(court_xy, zone)

    def finalize(self) -> ExtractionResult:
        """
        추출 완료 및 결과 반환.

        히트맵과 구역 통계를 저장합니다.

        Returns:
            ExtractionResult
        """
        with self._lock:
            try:
                total_count = self._total_records

                # 통계 저장
                if self._output_dir is not None and total_count > 0:
                    self._save_stats()

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.COURT_ZONE,
                    total_records=total_count,
                    split=DatasetSplit.TRAIN,
                    description=f"구역 히트맵 데이터 {total_count}건",
                )

                result = ExtractionResult(
                    record_count=total_count,
                    metadata=metadata,
                    file_path=str(self._output_dir) if self._output_dir else "",
                    upload_status=UploadStatus.PENDING,
                )

                logger.info("ZoneExtractor 완료: 기록=%d", total_count)

                return result
            finally:
                self._enabled = False

    def get_zone_distribution(self) -> dict[str, float]:
        """
        구역별 점유 비율 반환.

        Returns:
            {zone_value: ratio} 딕셔너리
        """
        with self._lock:
            if self._total_records == 0:
                return {z.value: 0.0 for z in CourtZone}

            return {
                zone_val: count / self._total_records
                for zone_val, count in self._zone_counts.items()
            }

    def get_heatmap(self) -> NDArray[np.float64] | None:
        """히트맵 배열 반환 (방어적 복사)."""
        if self._heatmap is not None:
            return self._heatmap.copy()
        return None

    def reset(self) -> None:
        """추출기 상태 초기화."""
        with self._lock:
            self._zone_counts = {z.value: 0 for z in CourtZone}
            if self._heatmap is not None:
                self._heatmap[:] = 0.0
            self._total_records = 0

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _save_stats(self) -> None:
        """통계를 JSON으로 저장."""
        if self._output_dir is None:
            return

        stats = {
            "total_records": self._total_records,
            "zone_counts": self._zone_counts,
            "zone_distribution": self.get_zone_distribution(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        stats_path = self._output_dir / _METADATA_FILENAME
        stats_path.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 히트맵 저장 (numpy)
        if self._heatmap is not None:
            heatmap_path = self._output_dir / "heatmap.npy"
            np.save(str(heatmap_path), self._heatmap)

    def __repr__(self) -> str:
        return (
            f"ZoneExtractor(enabled={self._enabled}, "
            f"records={self._total_records})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "ZoneExtractor",
]

__version__: str = "1.0.0"
