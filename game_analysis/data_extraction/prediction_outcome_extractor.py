# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: prediction_outcome_extractor.py
설명: 예측 결과 추출기
      - 예측 모델(WP/EPV/xFG%)의 예측값과 실제 결과를 쌍으로 추출
      - 예측 모델 캘리브레이션 및 재학습에 활용
      - Phase 2 predictive_models 출력 소비

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
    PredictionOutcomeRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 50000  # 예측 이벤트 수 (매 점유/슛마다)

_VALID_PREDICTION_TYPES: frozenset[str] = frozenset({
    "WP", "EPV", "xFG",
})


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class PredictionOutcomeExtractorConfig:
    """예측 결과 추출기 설정."""

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
    records: list[PredictionOutcomeRecord]


# =============================================================================
# 추출기
# =============================================================================

class PredictionOutcomeExtractor:
    """
    예측 결과 추출기.

    예측 모델의 예측값(WP/EPV/xFG%)과 실제 결과를 쌍으로 수집.
    예측 모델 캘리브레이션 학습 데이터 생산.

    흐름:
        1. create_extraction(game_id) → 세션 생성
        2. add_record(...) → 예측 vs 결과 쌍 추가
        3. build_result() → ExtractionResult 반환
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: PredictionOutcomeExtractorConfig | None = None) -> None:
        self._config = config or PredictionOutcomeExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "PredictionOutcomeExtractor"

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
            f"PredictionOutcomeExtractor("
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
        prediction_type: str,
        predicted_value: float,
        actual_outcome: float,
        game_state_features: dict[str, float] | None = None,
        frame_index: int = 0,
        possession_index: int = 0,
    ) -> bool:
        """예측 결과 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False

            # 예측 유형 검증
            if prediction_type not in _VALID_PREDICTION_TYPES:
                logger.warning(
                    "미지원 예측 유형: %s, 허용: %s",
                    prediction_type, _VALID_PREDICTION_TYPES,
                )
                return False

            # 값 클램핑 (WP: 0~1, EPV: 0~4, xFG: 0~1)
            predicted_value = max(0.0, predicted_value)
            actual_outcome = max(0.0, actual_outcome)
            if prediction_type in ("WP", "xFG"):
                predicted_value = min(1.0, predicted_value)
                actual_outcome = min(1.0, actual_outcome)
            elif prediction_type == "EPV":
                predicted_value = min(4.0, predicted_value)
                actual_outcome = min(4.0, actual_outcome)

            record = PredictionOutcomeRecord(
                prediction_type=prediction_type,
                predicted_value=predicted_value,
                actual_outcome=actual_outcome,
                game_state_features=dict(game_state_features) if game_state_features else {},
                frame_index=max(0, frame_index),
                possession_index=max(0, possession_index),
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
                dataset_type=DatasetType.PREDICTION_OUTCOME,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="예측 결과 쌍 추출 — 예측 모델 캘리브레이션용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[PredictionOutcomeRecord]:
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
            type_dist: dict[str, int] = {}
            error_sum: dict[str, float] = {}
            for r in session.records:
                type_dist[r.prediction_type] = (
                    type_dist.get(r.prediction_type, 0) + 1
                )
                error = abs(r.predicted_value - r.actual_outcome)
                error_sum[r.prediction_type] = (
                    error_sum.get(r.prediction_type, 0.0) + error
                )

            # 유형별 MAE
            mae_by_type: dict[str, float] = {}
            for pt, count in type_dist.items():
                mae_by_type[pt] = round(error_sum[pt] / count, 4) if count else 0.0

            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "type_distribution": dict(type_dist),
                "mae_by_type": mae_by_type,
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
    "PredictionOutcomeExtractor",
    "PredictionOutcomeExtractorConfig",
]

__version__ = "1.0.0"
