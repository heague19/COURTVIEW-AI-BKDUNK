# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: frame_record_extractor.py
설명: 프레임 단위 레코드 추출기
      - 프레임별 10인 위치 + 키포인트 + 공 위치 + 이벤트/동작 라벨을 FrameRecord로 추출
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
    ActionRecord,
    DatasetMetadata,
    DatasetType,
    EventRecord,
    ExtractionResult,
    FrameRecord,
    KeypointRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 100000  # 프레임 수 많음 (30fps × 2h = ~216,000)


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class FrameRecordExtractorConfig:
    """프레임 레코드 추출기 설정."""

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
    records: list[FrameRecord]


# =============================================================================
# 추출기
# =============================================================================

class FrameRecordExtractor:
    """
    프레임 단위 레코드 추출기.

    프레임별 전체 장면 정보 (선수 위치, 키포인트, 공, 이벤트, 동작)를 수집.
    COURTVIEW 자체 모델 학습용 데이터셋 생산.
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: FrameRecordExtractorConfig | None = None) -> None:
        self._config = config or FrameRecordExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "FrameRecordExtractor"

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
            f"FrameRecordExtractor("
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
        frame_index: int,
        camera_id: str = "",
        player_positions: list[tuple[int, float, float]] | None = None,
        keypoints: list[KeypointRecord] | None = None,
        ball_position: tuple[float, float] | None = None,
        actions: list[ActionRecord] | None = None,
        events: list[EventRecord] | None = None,
    ) -> bool:
        """프레임 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False
            record = FrameRecord(
                frame_index=frame_index,
                camera_id=camera_id,
                player_positions=list(player_positions) if player_positions else [],
                keypoints=list(keypoints) if keypoints else [],
                ball_position=ball_position,
                actions=list(actions) if actions else [],
                events=list(events) if events else [],
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
                dataset_type=DatasetType.FRAME_RECORD,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="프레임 단위 레코드 추출 — COURTVIEW 자체 모델 학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[FrameRecord]:
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
            total_actions = sum(len(r.actions) for r in session.records)
            total_events = sum(len(r.events) for r in session.records)
            frames_with_ball = sum(
                1 for r in session.records if r.ball_position is not None
            )
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "total_actions": total_actions,
                "total_events": total_events,
                "frames_with_ball": frames_with_ball,
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
    "FrameRecordExtractor",
    "FrameRecordExtractorConfig",
]

__version__ = "1.0.0"
