# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: possession_record_extractor.py
설명: 점유 단위 레코드 추출기
      - 한 점유 시퀀스에 대한 전술/수비/결과 라벨을 PossessionRecord로 추출
      - COURTVIEW 자체 모델 학습용 데이터셋 생산

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    PossessionRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 10000


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class PossessionRecordExtractorConfig:
    """점유 레코드 추출기 설정."""

    max_extractions: int = _MAX_EXTRACTIONS
    max_records_per_extraction: int = _MAX_RECORDS_PER_EXTRACTION


# =============================================================================
# 내부 데이터
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    game_id: str
    records: list[PossessionRecord]


# =============================================================================
# 추출기
# =============================================================================

class PossessionRecordExtractor:
    """
    점유 단위 레코드 추출기.

    점유별 전술/수비 라벨, 결과, 플레이 유형을 수집.
    COURTVIEW 자체 모델 학습용 데이터셋 생산.
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: PossessionRecordExtractorConfig | None = None) -> None:
        self._config = config or PossessionRecordExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "PossessionRecordExtractor"

    @property
    def total_extractions(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def total_records(self) -> int:
        with self._lock:
            return self._total_records

    def __repr__(self) -> str:
        return (
            f"PossessionRecordExtractor("
            f"extractions={self.total_extractions}, "
            f"records={self.total_records})"
        )

    # -- 세션 관리 --

    def create_extraction(self, game_id: str) -> UUID | None:
        """추출 세션 생성."""
        with self._lock:
            if len(self._sessions) >= self._config.max_extractions:
                logger.warning(
                    "추출 세션 한도 도달: %d", self._config.max_extractions,
                )
                return None
            eid = uuid4()
            self._sessions[eid] = _ExtractionSession(
                extraction_id=eid,
                game_id=game_id,
                records=[],
            )
            return eid

    def add_record(
        self,
        extraction_id: UUID,
        team_id: str,
        start_frame: int,
        end_frame: int,
        tactical_label: str = "",
        defensive_label: str = "",
        result_label: str = "",
        points_scored: int = 0,
        play_type: str = "",
    ) -> bool:
        """점유 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False
            # 프레임 범위 검증
            frame_count = max(0, end_frame - start_frame)
            # 득점 클램핑 (0~4)
            pts = max(0, min(4, points_scored))
            record = PossessionRecord(
                team_id=team_id,
                start_frame=start_frame,
                end_frame=end_frame,
                frame_count=frame_count,
                tactical_label=tactical_label,
                defensive_label=defensive_label,
                result_label=result_label,
                points_scored=pts,
                play_type=play_type,
            )
            session.records.append(record)
            self._total_records += 1
            return True

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.POSSESSION_RECORD,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="점유 단위 레코드 추출 — COURTVIEW 자체 모델 학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[PossessionRecord]:
        """레코드 목록 반환."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return list(session.records)

    # -- 조회 --

    def get_extraction_summary(self, extraction_id: UUID) -> dict[str, object] | None:
        """추출 세션 요약."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            tactical_dist: dict[str, int] = {}
            result_dist: dict[str, int] = {}
            total_pts = 0
            for r in session.records:
                if r.tactical_label:
                    tactical_dist[r.tactical_label] = tactical_dist.get(r.tactical_label, 0) + 1
                if r.result_label:
                    result_dist[r.result_label] = result_dist.get(r.result_label, 0) + 1
                total_pts += r.points_scored
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "tactical_distribution": tactical_dist,
                "result_distribution": result_dist,
                "total_points": total_pts,
            }

    # -- 삭제 / 유틸리티 --

    def delete_extraction(self, extraction_id: UUID) -> bool:
        """추출 세션 삭제."""
        with self._lock:
            session = self._sessions.pop(extraction_id, None)
            if session is None:
                return False
            self._total_records -= len(session.records)
            return True

    def get_stats(self) -> dict[str, object]:
        """전체 통계."""
        with self._lock:
            return {
                "total_extractions": len(self._sessions),
                "total_records": self._total_records,
            }

    def reset(self) -> None:
        """전체 초기화."""
        with self._lock:
            self._sessions.clear()
            self._total_records = 0


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "PossessionRecordExtractor",
    "PossessionRecordExtractorConfig",
]

__version__ = "1.0.0"
