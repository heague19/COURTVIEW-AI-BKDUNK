# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: decision_record_extractor.py
설명: 전체 판정 기록 추출기
      - 모든 FinalDecision + FrameContext를 DecisionRecord로 수집
      - 콜(violated=True)은 전수 수집
      - 노콜은 샘플링 비율에 따라 수집 (클래스 불균형 방지)
      - 리플레이 결과, 일관성 점수, 편향 경고 포함

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: decision_record 섹션
    - ai_referee/decisions/decision_engine.py: FinalDecision
    - ai_referee/decisions/confidence_scorer.py: CalibrationResult
    - ai_referee/rules/base_rule.py: RuleResult, FrameContext
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    DecisionRecord,
    ExtractionResult,
)

from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.rules.base_rule import FrameContext

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수 (YAML 미로딩 시 폴백)
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_NO_CALL_SAMPLING_RATIO: Final[float] = 0.33
_DEFAULT_MIN_CONFIDENCE_NO_CALL: Final[float] = 0.30


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DecisionRecordExtractorConfig:
    """판정 기록 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    no_call_sampling_ratio: float = _DEFAULT_NO_CALL_SAMPLING_RATIO
    min_confidence_for_no_call: float = _DEFAULT_MIN_CONFIDENCE_NO_CALL


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    game_id: str
    records: list[DecisionRecord]
    call_count: int
    no_call_count: int


# =============================================================================
# 추출기
# =============================================================================
class DecisionRecordExtractor:
    """
    전체 판정 기록 추출기.

    FinalDecision 파이프라인의 출력을 DecisionRecord로 변환하여 수집.
    콜은 전수, 노콜은 샘플링 비율에 따라 수집하여 클래스 불균형을 방지.

    사용 예시::

        >>> extractor = DecisionRecordExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.add_decision(eid, final_decision, context)
        True
        >>> result = extractor.build_result(eid)
        >>> result.record_count
        42
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: DecisionRecordExtractorConfig | None = None,
    ) -> None:
        self._config = config or DecisionRecordExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "DecisionRecordExtractor"

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
            f"DecisionRecordExtractor("
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
                call_count=0,
                no_call_count=0,
            )
            return eid

    def add_decision(
        self,
        extraction_id: UUID,
        decision: FinalDecision,
        context: FrameContext,
    ) -> bool:
        """
        판정을 레코드로 변환하여 추가.

        Args:
            extraction_id: 추출 세션 ID
            decision: 최종 판정 (DecisionEngine 출력)
            context: 판정 시점의 프레임 컨텍스트

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

            # 노콜 샘플링 판정
            if not result.violated:
                if result.confidence < self._config.min_confidence_for_no_call:
                    return False
                # 샘플링: 콜 대비 비율 확인
                max_no_call = max(
                    1, int(session.call_count * self._config.no_call_sampling_ratio),
                )
                if session.no_call_count >= max_no_call:
                    # 확률적 샘플링으로 전환
                    if random.random() > self._config.no_call_sampling_ratio:
                        return False

            # DecisionRecord 생성
            calibration = decision.calibration
            consistency = decision.consistency

            record = DecisionRecord(
                frame_index=result.frame_number,
                quarter=context.quarter,
                game_clock_sec=context.game_clock_sec,
                call_type=result.call_type.value if result.call_type else "",
                rule_category=result.category.value if result.category else "",
                penalty_type=result.penalty.value if result.penalty else "",
                confidence_raw=result.confidence,
                confidence_calibrated=(
                    calibration.calibrated_confidence if calibration else result.confidence
                ),
                confidence_level=(
                    calibration.confidence_level.value
                    if calibration and calibration.confidence_level
                    else ""
                ),
                violated=result.violated,
                offending_player_id=result.offending_player_id,
                victim_player_id=result.victim_player_id,
                evidence=list(result.evidence),
                rule_reference=result.rule_reference,
                player_positions=dict(context.player_positions),
                ball_position=context.ball_position,
                was_replayed=decision.should_replay,
                replay_outcome="",  # 리플레이 결과는 후속 업데이트
                consistency_score=(
                    consistency.consistency_score if consistency else 0.0
                ),
                bias_warnings=(
                    list(consistency.bias_warnings) if consistency else []
                ),
            )

            session.records.append(record)
            self._total_records += 1

            if result.violated:
                session.call_count += 1
            else:
                session.no_call_count += 1

            return True

    def update_replay_outcome(
        self,
        extraction_id: UUID,
        frame_index: int,
        outcome: str,
    ) -> bool:
        """
        리플레이 결과를 기존 레코드에 반영.

        Args:
            extraction_id: 추출 세션 ID
            frame_index: 대상 프레임
            outcome: 결과 (CONFIRMED / OVERTURNED)

        Returns:
            업데이트 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            for record in reversed(session.records):
                if record.frame_index == frame_index and record.was_replayed:
                    record.replay_outcome = outcome
                    return True
            return False

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.REFEREE_DECISION,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="AI 심판 판정 기록 — 자가학습용 전체 판정 데이터셋",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[DecisionRecord]:
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
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "call_count": session.call_count,
                "no_call_count": session.no_call_count,
                "call_ratio": (
                    session.call_count / len(session.records)
                    if session.records else 0.0
                ),
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
    "DecisionRecordExtractor",
    "DecisionRecordExtractorConfig",
]

__version__ = "1.0.0"
