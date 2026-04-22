# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: calibration_data_extractor.py
설명: 신뢰도 보정 데이터 추출기
      - (예측 신뢰도, 실제 정확 여부) 쌍 수집
      - 0.05 구간 빈(bin) 분류
      - Platt scaling / isotonic regression 보정 곡선 학습용
      - 빈당 30+ 샘플 시 캘리브레이션 유효

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: calibration 섹션
    - ai_referee/decisions/confidence_scorer.py: CalibrationResult
    - ai_referee/decisions/decision_engine.py: FinalDecision
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    CalibrationRecord,
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
)

from ai_referee.decisions.decision_engine import FinalDecision

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_BIN_WIDTH: Final[float] = 0.05
_DEFAULT_MIN_SAMPLES_PER_BIN: Final[int] = 30

# 클러치 기준: 4쿼터 잔여 2분 이내 + 5점차 이내
_CLUTCH_QUARTER: Final[int] = 4
_CLUTCH_CLOCK_SEC: Final[float] = 120.0


# =============================================================================
# 열거형
# =============================================================================
@unique
class ActualOutcome(str, Enum):
    """실제 결과."""
    CONFIRMED = "confirmed"
    OVERTURNED = "overturned"
    UNVERIFIED = "unverified"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class CalibrationDataExtractorConfig:
    """캘리브레이션 데이터 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    bin_width: float = _DEFAULT_BIN_WIDTH
    min_samples_per_bin: int = _DEFAULT_MIN_SAMPLES_PER_BIN


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""
    extraction_id: UUID
    game_id: str
    records: list[CalibrationRecord]
    bin_counts: dict[float, int]  # bin_center → count


# =============================================================================
# 추출기
# =============================================================================
class CalibrationDataExtractor:
    """
    신뢰도 보정 데이터 추출기.

    모든 확정 판정의 (예측 신뢰도, 실제 정확 여부) 쌍을 수집.
    0.05 구간 빈에 분류하여 캘리브레이션 곡선 학습에 사용.

    사용 예시::

        >>> extractor = CalibrationDataExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.add_outcome(eid, decision, ActualOutcome.CONFIRMED, quarter=2, clock=300.0)
        True
        >>> extractor.get_calibration_summary(eid)
        {'0.85': {'count': 12, 'confirmed_ratio': 0.92}, ...}
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: CalibrationDataExtractorConfig | None = None,
    ) -> None:
        self._config = config or CalibrationDataExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "CalibrationDataExtractor"

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
            f"CalibrationDataExtractor("
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
                bin_counts={},
            )
            return eid

    def add_outcome(
        self,
        extraction_id: UUID,
        decision: FinalDecision,
        outcome: ActualOutcome,
        quarter: int = 1,
        game_clock_sec: float = 0.0,
    ) -> bool:
        """
        확정 결과를 캘리브레이션 레코드로 추가.

        Args:
            extraction_id: 추출 세션 ID
            decision: 최종 판정
            outcome: 실제 결과 (CONFIRMED / OVERTURNED / UNVERIFIED)
            quarter: 쿼터
            game_clock_sec: 잔여 시간

        Returns:
            추가 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                return False

            result = decision.result
            if result is None:
                return False

            conf = decision.final_confidence
            # 빈 계산
            bin_center = self._to_bin(conf)

            # 보정 요소
            calibration_factors: dict[str, float] = {}
            if decision.calibration is not None:
                cal = decision.calibration
                calibration_factors = {
                    "original": cal.original_confidence,
                    "calibrated": cal.calibrated_confidence,
                }

            # 클러치 여부
            is_clutch = (
                quarter >= _CLUTCH_QUARTER
                and game_clock_sec <= _CLUTCH_CLOCK_SEC
            )

            record = CalibrationRecord(
                predicted_confidence=conf,
                confidence_level=(
                    decision.confidence_level.value
                    if decision.confidence_level else ""
                ),
                confidence_bin=bin_center,
                actual_outcome=outcome.value,
                call_type=(
                    result.call_type.value if result.call_type else ""
                ),
                rule_category=(
                    result.category.value if result.category else ""
                ),
                calibration_factors=calibration_factors,
                quarter=quarter,
                game_clock_sec=game_clock_sec,
                is_clutch=is_clutch,
            )

            session.records.append(record)
            session.bin_counts[bin_center] = session.bin_counts.get(bin_center, 0) + 1
            self._total_records += 1
            return True

    def _to_bin(self, confidence: float) -> float:
        """신뢰도를 빈 중앙값으로 변환."""
        width = self._config.bin_width
        # floor 방식: 0.87 → bin_width=0.05 → floor(0.87/0.05)*0.05 = 0.85 → center = 0.875
        bin_lower = math.floor(confidence / width) * width
        center = round(bin_lower + width / 2, 4)
        return min(center, 1.0)

    # -- 조회 --

    def get_calibration_summary(
        self, extraction_id: UUID,
    ) -> dict[str, dict[str, object]] | None:
        """
        빈별 캘리브레이션 요약.

        Returns:
            {"0.875": {"count": 30, "confirmed_ratio": 0.87, "is_valid": True}, ...}
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None

            # 빈별 분류
            bins: dict[float, list[CalibrationRecord]] = {}
            for record in session.records:
                key = record.confidence_bin
                if key not in bins:
                    bins[key] = []
                bins[key].append(record)

            summary: dict[str, dict[str, object]] = {}
            for bin_center, records in sorted(bins.items()):
                confirmed = sum(
                    1 for r in records
                    if r.actual_outcome == ActualOutcome.CONFIRMED.value
                )
                total = len(records)
                ratio = confirmed / total if total > 0 else 0.0
                summary[str(bin_center)] = {
                    "count": total,
                    "confirmed_ratio": round(ratio, 4),
                    "is_valid": total >= self._config.min_samples_per_bin,
                }

            return summary

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.REFEREE_CALIBRATION,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="신뢰도 보정 데이터 — Platt/Isotonic 캘리브레이션 곡선용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[CalibrationRecord]:
        """레코드 목록 반환."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return list(session.records)

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
    "CalibrationDataExtractor",
    "CalibrationDataExtractorConfig",
    "ActualOutcome",
]

__version__ = "1.0.0"
