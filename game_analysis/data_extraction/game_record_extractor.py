# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: game_record_extractor.py
설명: 경기 단위 레코드 추출기
      - 경기 전체의 팀 스타일, 라인업, 모멘텀 커브를 GameDataRecord로 추출
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
    GameDataRecord,
    LineupRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 500
_MAX_LINEUPS_PER_RECORD: int = 100
_MAX_MOMENTUM_POINTS: int = 1000


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class GameRecordExtractorConfig:
    """경기 레코드 추출기 설정."""

    max_extractions: int = _MAX_EXTRACTIONS
    max_records_per_extraction: int = _MAX_RECORDS_PER_EXTRACTION
    max_lineups_per_record: int = _MAX_LINEUPS_PER_RECORD
    max_momentum_points: int = _MAX_MOMENTUM_POINTS


# =============================================================================
# 내부 데이터
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    source_game_id: str
    records: list[GameDataRecord]


# =============================================================================
# 추출기
# =============================================================================

class GameRecordExtractor:
    """
    경기 단위 레코드 추출기.

    경기별 팀 스타일, 라인업 데이터, 모멘텀 커브를 수집.
    COURTVIEW 자체 모델 학습용 데이터셋 생산.
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: GameRecordExtractorConfig | None = None) -> None:
        self._config = config or GameRecordExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "GameRecordExtractor"

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
            f"GameRecordExtractor("
            f"extractions={self.total_extractions}, "
            f"records={self.total_records})"
        )

    # -- 세션 관리 --

    def create_extraction(self, source_game_id: str) -> UUID | None:
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
                source_game_id=source_game_id,
                records=[],
            )
            return eid

    def add_record(
        self,
        extraction_id: UUID,
        game_id: str,
        date: str,
        team_style_metrics: dict[str, float] | None = None,
        lineup_data: list[LineupRecord] | None = None,
        momentum_curve: list[float] | None = None,
        final_score: tuple[int, int] = (0, 0),
        total_possessions: int = 0,
    ) -> bool:
        """경기 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False
            # 라인업 한도 제한
            lineups = list(lineup_data) if lineup_data else []
            if len(lineups) > self._config.max_lineups_per_record:
                lineups = lineups[:self._config.max_lineups_per_record]
            # 모멘텀 커브 한도 제한
            curve = list(momentum_curve) if momentum_curve else []
            if len(curve) > self._config.max_momentum_points:
                curve = curve[:self._config.max_momentum_points]
            # WP 클램핑 (0~1)
            curve = [max(0.0, min(1.0, v)) for v in curve]
            record = GameDataRecord(
                game_id=game_id,
                date=date,
                team_style_metrics=dict(team_style_metrics) if team_style_metrics else {},
                lineup_data=lineups,
                momentum_curve=curve,
                final_score=final_score,
                total_possessions=max(0, total_possessions),
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
                dataset_type=DatasetType.GAME_RECORD,
                total_records=len(session.records),
                source_game_ids=[session.source_game_id],
                description="경기 단위 레코드 추출 — COURTVIEW 자체 모델 학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.source_game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[GameDataRecord]:
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
            total_lineups = sum(len(r.lineup_data) for r in session.records)
            total_possessions = sum(r.total_possessions for r in session.records)
            return {
                "source_game_id": session.source_game_id,
                "total_records": len(session.records),
                "total_lineups": total_lineups,
                "total_possessions": total_possessions,
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
    "GameRecordExtractor",
    "GameRecordExtractorConfig",
]

__version__ = "1.0.0"
