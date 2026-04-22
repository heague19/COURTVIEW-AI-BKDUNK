# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: edge_case_extractor.py
설명: 저신뢰도 경계 케이스 추출기
      - 신뢰도 0.40~0.85 구간 판정 캡처
      - 멀티앵글 동의율 <0.75 판정 캡처
      - 일관성 점수 <0.70 판정 캡처
      - 라벨링 우선순위 산정 (3요소 가중)
      - 능동 학습(Active Learning) 우선 라벨링 대상 선별

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: edge_case 섹션
    - ai_referee/decisions/decision_engine.py: FinalDecision
    - ai_referee/rules/base_rule.py: RuleResult, FrameContext, PenaltyType
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    EdgeCaseRecord,
    ExtractionResult,
)

from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.rules.base_rule import FrameContext, PenaltyType

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_MAX_CONFIDENCE: Final[float] = 0.85
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.40
_DEFAULT_MAX_AGREEMENT: Final[float] = 0.75
_DEFAULT_MAX_CONSISTENCY: Final[float] = 0.70

# 페널티 심각도 맵 (우선순위 계산용)
_PENALTY_SEVERITY: Final[dict[str, float]] = {
    PenaltyType.EJECTION.value: 1.0,
    PenaltyType.FREE_THROWS_AND_POSSESSION.value: 0.85,
    PenaltyType.FREE_THROWS.value: 0.70,
    PenaltyType.TECHNICAL_FREE_THROW.value: 0.55,
    PenaltyType.TURNOVER.value: 0.40,
    PenaltyType.JUMP_BALL.value: 0.20,
    PenaltyType.NONE.value: 0.10,
}


# =============================================================================
# 열거형
# =============================================================================
@unique
class UncertaintyReason(str, Enum):
    """불확실성 이유."""
    LOW_EVIDENCE = "low_evidence"
    CONFLICTING_ANGLES = "conflicting_angles"
    LOW_CONSISTENCY = "low_consistency"
    NOVEL_SITUATION = "novel_situation"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class EdgeCaseExtractorConfig:
    """경계 케이스 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    max_confidence: float = _DEFAULT_MAX_CONFIDENCE
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE
    max_multi_angle_agreement: float = _DEFAULT_MAX_AGREEMENT
    max_consistency_score: float = _DEFAULT_MAX_CONSISTENCY
    # 우선순위 가중치
    weight_confidence_inverse: float = 0.40
    weight_agreement_inverse: float = 0.30
    weight_severity: float = 0.30


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""
    extraction_id: UUID
    game_id: str
    records: list[EdgeCaseRecord]


# =============================================================================
# 추출기
# =============================================================================
class EdgeCaseExtractor:
    """
    저신뢰도 경계 케이스 추출기.

    AUTO_CONFIRM 미달 판정을 캡처하여 능동 학습 라벨링 큐를 구성.
    라벨링 우선순위가 높은 케이스부터 전문가 검토 대상으로 선별.

    사용 예시::

        >>> extractor = EdgeCaseExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.evaluate_decision(eid, decision, context)
        True
        >>> records = extractor.get_records(eid)
        >>> records[0].labeling_priority
        0.72
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: EdgeCaseExtractorConfig | None = None,
    ) -> None:
        self._config = config or EdgeCaseExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "EdgeCaseExtractor"

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
            f"EdgeCaseExtractor("
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

    def evaluate_decision(
        self,
        extraction_id: UUID,
        decision: FinalDecision,
        context: FrameContext,
    ) -> bool:
        """
        판정을 평가하여 경계 케이스 여부 판단 + 캡처.

        경계 케이스 기준 (하나 이상 해당):
        - 보정 신뢰도 < max_confidence (0.85)
        - 멀티앵글 동의율 < max_agreement (0.75)
        - 일관성 점수 < max_consistency (0.70)

        Args:
            extraction_id: 추출 세션 ID
            decision: 최종 판정
            context: 프레임 컨텍스트

        Returns:
            캡처 성공 여부 (경계 케이스가 아니면 False)
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
            # 신뢰도 범위 체크
            if conf < self._config.min_confidence or conf > self._config.max_confidence:
                # 범위 밖이면 캡처하지 않음 (너무 낮거나 이미 확정)
                # 단, 다른 기준으로 해당될 수 있음
                pass

            # 멀티앵글 동의율
            agreement = 1.0
            if decision.validation is not None:
                agreement = decision.validation.agreement_ratio

            # 일관성 점수
            consistency = 1.0
            if decision.consistency is not None:
                consistency = decision.consistency.consistency_score

            # 경계 케이스 기준 판별
            is_low_confidence = (
                self._config.min_confidence <= conf <= self._config.max_confidence
            )
            is_low_agreement = agreement < self._config.max_multi_angle_agreement
            is_low_consistency = consistency < self._config.max_consistency_score

            if not (is_low_confidence or is_low_agreement or is_low_consistency):
                return False

            # 불확실성 이유 결정
            uncertainty = self._determine_uncertainty(
                conf, agreement, consistency, result.evidence,
            )

            # 라벨링 우선순위 계산
            severity_score = _PENALTY_SEVERITY.get(
                result.penalty.value if result.penalty else "", 0.10,
            )
            priority = self._calculate_priority(
                conf, agreement, severity_score,
            )

            # 유사 과거 판정 수
            similar_count = 0
            if decision.consistency is not None:
                similar_count = decision.consistency.similar_count

            record = EdgeCaseRecord(
                frame_index=result.frame_number,
                call_type=result.call_type.value if result.call_type else "",
                confidence=conf,
                violated=result.violated,
                evidence=list(result.evidence),
                uncertainty_reason=uncertainty.value,
                multi_angle_agreement=agreement,
                consistency_score=consistency,
                similar_past_count=similar_count,
                labeling_priority=priority,
                player_positions=dict(context.player_positions),
                offending_player_id=result.offending_player_id,
            )

            session.records.append(record)
            self._total_records += 1
            return True

    # -- 내부 --

    @staticmethod
    def _determine_uncertainty(
        confidence: float,
        agreement: float,
        consistency: float,
        evidence: list[str],
    ) -> UncertaintyReason:
        """불확실성 이유 결정 (최저 요소 기준)."""
        # 근거 부족
        if len(evidence) <= 1:
            return UncertaintyReason.LOW_EVIDENCE
        # 앵글 충돌
        if agreement < 0.60:
            return UncertaintyReason.CONFLICTING_ANGLES
        # 일관성 저하
        if consistency < 0.50:
            return UncertaintyReason.LOW_CONSISTENCY
        # 신규 상황 (근거는 있지만 신뢰도 낮음)
        if confidence < 0.60:
            return UncertaintyReason.NOVEL_SITUATION
        # 기본값: 근거 부족
        return UncertaintyReason.LOW_EVIDENCE

    def _calculate_priority(
        self,
        confidence: float,
        agreement: float,
        severity_score: float,
    ) -> float:
        """
        라벨링 우선순위 계산.

        3요소 가중 평균: 신뢰도 역수 × 0.4 + 동의율 역수 × 0.3 + 심각도 × 0.3
        결과: 0.0~1.0 (높을수록 우선)
        """
        # 신뢰도 역수 (0.85 → 0.15, 0.40 → 0.60, 정규화)
        conf_inv = min(1.0, max(0.0, 1.0 - confidence))
        # 동의율 역수
        agree_inv = min(1.0, max(0.0, 1.0 - agreement))

        priority = (
            conf_inv * self._config.weight_confidence_inverse
            + agree_inv * self._config.weight_agreement_inverse
            + severity_score * self._config.weight_severity
        )
        return round(min(1.0, max(0.0, priority)), 4)

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.REFEREE_EDGE_CASE,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="저신뢰도 경계 케이스 — 능동 학습 라벨링 대상",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[EdgeCaseRecord]:
        """레코드 목록 반환 (우선순위 내림차순)."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return sorted(
                session.records,
                key=lambda r: r.labeling_priority,
                reverse=True,
            )

    def get_extraction_summary(self, extraction_id: UUID) -> dict[str, object] | None:
        """추출 세션 요약."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            if not session.records:
                return {
                    "game_id": session.game_id,
                    "total_records": 0,
                    "avg_priority": 0.0,
                    "avg_confidence": 0.0,
                }
            avg_pri = sum(r.labeling_priority for r in session.records) / len(session.records)
            avg_conf = sum(r.confidence for r in session.records) / len(session.records)
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "avg_priority": round(avg_pri, 4),
                "avg_confidence": round(avg_conf, 4),
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
    "EdgeCaseExtractor",
    "EdgeCaseExtractorConfig",
    "UncertaintyReason",
]

__version__ = "1.0.0"
