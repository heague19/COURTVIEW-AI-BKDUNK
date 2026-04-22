# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: event_correction_extractor.py
설명: 이벤트 보정 데이터 추출기
      - live_workspace에서 인간이 보정한 이벤트와 AI 원본 예측을 쌍으로 추출
      - 이벤트 감지 모델 재학습 시 ground truth 라벨로 활용
      - (AI예측, 인간보정) 쌍 → self_learning 파이프라인 소비

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
    EventCorrectionRecord,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 10000  # 경기당 보정 이벤트 최대 수


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class EventCorrectionExtractorConfig:
    """이벤트 보정 추출기 설정."""

    max_extractions: int = _MAX_EXTRACTIONS
    max_records_per_extraction: int = _MAX_RECORDS_PER_EXTRACTION
    min_ai_confidence: float = 0.0  # 최소 AI 신뢰도 (이하 필터링)


# =============================================================================
# 내부 데이터
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    game_id: str
    records: list[EventCorrectionRecord]


# =============================================================================
# 추출기
# =============================================================================

_VALID_CORRECTION_SOURCES: frozenset[str] = frozenset({
    "live_validator", "manual_tagger",
})


class EventCorrectionExtractor:
    """
    이벤트 보정 데이터 추출기.

    live_workspace(Phase 1C)에서 발생한 AI 예측 vs 인간 보정 쌍을 수집.
    이벤트 감지 모델의 지도 학습 데이터로 활용.

    흐름:
        1. create_extraction(game_id) → 세션 생성
        2. add_record(...) → AI 예측 + 인간 보정 쌍 추가
        3. build_result() → ExtractionResult 반환
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: EventCorrectionExtractorConfig | None = None) -> None:
        self._config = config or EventCorrectionExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "EventCorrectionExtractor"

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
            f"EventCorrectionExtractor("
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
        original_event_type: str,
        corrected_event_type: str,
        ai_confidence: float = 0.0,
        correction_source: str = "live_validator",
        player_tracking_ids: list[int] | None = None,
        game_context: str = "",
    ) -> bool:
        """이벤트 보정 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False

            # 신뢰도 클램핑
            ai_confidence = max(0.0, min(1.0, ai_confidence))

            # 최소 신뢰도 필터
            if ai_confidence < self._config.min_ai_confidence:
                return False

            # 보정 출처 검증 — 미지원 값은 호출자 버그일 수 있으므로 거부
            if correction_source not in _VALID_CORRECTION_SOURCES:
                logger.warning(
                    "미지원 correction_source: %s, 허용: %s",
                    correction_source, _VALID_CORRECTION_SOURCES,
                )
                return False

            record = EventCorrectionRecord(
                frame_index=max(0, frame_index),
                original_event_type=original_event_type,
                corrected_event_type=corrected_event_type,
                ai_confidence=ai_confidence,
                correction_source=correction_source,
                player_tracking_ids=list(player_tracking_ids) if player_tracking_ids else [],
                game_context=game_context,
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
                dataset_type=DatasetType.EVENT_CORRECTION,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="이벤트 보정 쌍 추출 — 이벤트 감지 모델 재학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[EventCorrectionRecord]:
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
            # 보정 유형별 분포
            correction_types: dict[str, int] = {}
            source_distribution: dict[str, int] = {}
            match_count = 0
            for r in session.records:
                key = f"{r.original_event_type}->{r.corrected_event_type}"
                correction_types[key] = correction_types.get(key, 0) + 1
                source_distribution[r.correction_source] = (
                    source_distribution.get(r.correction_source, 0) + 1
                )
                if r.original_event_type == r.corrected_event_type:
                    match_count += 1

            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "correction_types": dict(correction_types),
                "source_distribution": dict(source_distribution),
                "ai_accuracy": match_count / len(session.records) if session.records else 0.0,
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
    "EventCorrectionExtractor",
    "EventCorrectionExtractorConfig",
]

__version__ = "1.0.0"
