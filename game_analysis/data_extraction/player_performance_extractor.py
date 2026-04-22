# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: player_performance_extractor.py
설명: 선수 성능 프로파일 추출기
      - 선수별 상황 효율/경향성/존 효율을 경기 단위로 추출
      - 개인화 분석 모델 학습 시 선수 프로파일 벡터로 활용
      - Phase 3 individual_analysis + statistics 결과 소비

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    PlayerPerformanceRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 500  # 경기당 선수 수 (양 팀 + 교체)

# 선수 최대 출전 시간 (분).
# 정규 40분 + OT 5분 × 6회까지 대응 (NBA 역사상 최장 경기는 1951년 6OT 경기 = 70분).
# 72분으로 상향하여 극단적 멀티 OT 경기에서도 무결성 유지.
_MAX_PLAYER_MINUTES: Final[float] = 72.0


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class PlayerPerformanceExtractorConfig:
    """선수 성능 추출기 설정."""

    max_extractions: int = _MAX_EXTRACTIONS
    max_records_per_extraction: int = _MAX_RECORDS_PER_EXTRACTION
    min_minutes: float = 0.0  # 최소 출전 시간 (이하 필터링)


# =============================================================================
# 내부 데이터
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    game_id: str
    records: list[PlayerPerformanceRecord]


# =============================================================================
# 추출기
# =============================================================================

class PlayerPerformanceExtractor:
    """
    선수 성능 프로파일 추출기.

    선수별 상황 효율, 경향성, 존 효율, 경기 스탯을 수집.
    개인화 분석 모델의 학습 데이터 생산.

    흐름:
        1. create_extraction(game_id) → 세션 생성
        2. add_record(...) → 선수 프로파일 추가
        3. build_result() → ExtractionResult 반환
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: PlayerPerformanceExtractorConfig | None = None) -> None:
        self._config = config or PlayerPerformanceExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "PlayerPerformanceExtractor"

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
            f"PlayerPerformanceExtractor("
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
        tracking_id: int,
        total_minutes: float = 0.0,
        situation_efficiency: dict[str, float] | None = None,
        tendencies: dict[str, float] | None = None,
        zone_efficiency: dict[str, float] | None = None,
        per_game_stats: dict[str, float] | None = None,
    ) -> bool:
        """선수 성능 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False

            # 출전 시간 클램핑 (0 ~ _MAX_PLAYER_MINUTES 분, 6OT 대응)
            total_minutes = max(0.0, min(_MAX_PLAYER_MINUTES, total_minutes))

            # 최소 출전 시간 필터
            if total_minutes < self._config.min_minutes:
                return False

            # 효율/경향 값 클램핑 (0~1 범위)
            safe_sit = {
                k: max(0.0, min(1.0, v))
                for k, v in (situation_efficiency or {}).items()
            }
            safe_tend = {
                k: max(0.0, min(1.0, v))
                for k, v in (tendencies or {}).items()
            }
            safe_zone = {
                k: max(0.0, min(1.0, v))
                for k, v in (zone_efficiency or {}).items()
            }
            safe_stats = dict(per_game_stats) if per_game_stats else {}

            record = PlayerPerformanceRecord(
                tracking_id=tracking_id,
                game_id=session.game_id,
                total_minutes=total_minutes,
                situation_efficiency=safe_sit,
                tendencies=safe_tend,
                zone_efficiency=safe_zone,
                per_game_stats=safe_stats,
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
                dataset_type=DatasetType.PLAYER_PERFORMANCE,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="선수 성능 프로파일 추출 — 개인화 모델 학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[PlayerPerformanceRecord]:
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
            total_minutes_sum = sum(r.total_minutes for r in session.records)
            avg_minutes = (
                total_minutes_sum / len(session.records) if session.records else 0.0
            )
            unique_players = len({r.tracking_id for r in session.records})

            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "unique_players": unique_players,
                "avg_minutes": round(avg_minutes, 1),
                "total_minutes": round(total_minutes_sum, 1),
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
    "PlayerPerformanceExtractor",
    "PlayerPerformanceExtractorConfig",
]

__version__ = "1.0.0"
