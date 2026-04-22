# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: correction_pair_extractor.py
설명: AI 판정 vs 인간 교정 쌍 추출기
      - 리플레이 번복(OVERTURNED) 시 자동 트리거
      - 코치 챌린지 성공 시 자동 트리거
      - 외부 수동 검토 결과 수신
      - 오류 분류: FALSE_POSITIVE / FALSE_NEGATIVE / WRONG_TYPE / WRONG_PLAYER
      - 자가학습 시 최고 가치 데이터 (명시적 오류 신호)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: correction_pair 섹션
    - ai_referee/decisions/decision_engine.py: FinalDecision
    - ai_referee/decisions/replay_manager.py: ReplayStatus
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    CorrectionPairRecord,
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
)

from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.rules.base_rule import PenaltyType

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_CONFIRMATION_TIMEOUT: Final[float] = 300.0  # 5분


# =============================================================================
# 열거형
# =============================================================================
@unique
class CorrectionSource(str, Enum):
    """교정 소스."""
    REPLAY_OVERTURN = "replay_overturn"
    COACH_CHALLENGE = "coach_challenge"
    MANUAL_REVIEW = "manual_review"

    def __str__(self) -> str:
        return self.value


@unique
class ErrorCategory(str, Enum):
    """오류 분류."""
    FALSE_POSITIVE = "false_positive"    # 노콜인데 콜
    FALSE_NEGATIVE = "false_negative"    # 콜인데 노콜
    WRONG_TYPE = "wrong_type"            # 콜 유형 오류
    WRONG_PLAYER = "wrong_player"        # 선수 식별 오류

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class CorrectionPairExtractorConfig:
    """교정 쌍 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    confirmation_timeout_sec: float = _DEFAULT_CONFIRMATION_TIMEOUT
    source_weights: dict[str, float] = field(default_factory=lambda: {
        CorrectionSource.REPLAY_OVERTURN.value: 1.0,
        CorrectionSource.COACH_CHALLENGE.value: 0.9,
        CorrectionSource.MANUAL_REVIEW.value: 0.8,
    })


# =============================================================================
# 내부 데이터
# =============================================================================

# 페널티 심각도 맵 (severity_delta 계산용)
_PENALTY_SEVERITY: Final[dict[str, int]] = {
    PenaltyType.EJECTION.value: 6,
    PenaltyType.FREE_THROWS_AND_POSSESSION.value: 5,
    PenaltyType.FREE_THROWS.value: 4,
    PenaltyType.TECHNICAL_FREE_THROW.value: 3,
    PenaltyType.TURNOVER.value: 2,
    PenaltyType.JUMP_BALL.value: 1,
    PenaltyType.NONE.value: 0,
}


@dataclass(slots=True)
class _PendingDecision:
    """교정 대기 중인 판정."""
    decision: FinalDecision
    received_at: float
    quarter: int
    game_clock_sec: float


@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""
    extraction_id: UUID
    game_id: str
    records: list[CorrectionPairRecord]
    pending: dict[UUID, _PendingDecision]  # decision_id → 대기 판정


# =============================================================================
# 추출기
# =============================================================================
class CorrectionPairExtractor:
    """
    AI 판정 vs 인간 교정 쌍 추출기.

    자가학습 시 가장 높은 가치를 지닌 데이터를 수집:
    - 리플레이 번복 / 코치 챌린지 성공 → 명시적 오류 신호
    - 오류 분류를 통해 모델의 약점 패턴을 식별

    사용 예시::

        >>> extractor = CorrectionPairExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.register_decision(eid, final_decision, quarter=2, clock=180.0)
        >>> extractor.record_correction(
        ...     eid, decision.decision_id,
        ...     corrected_call="personal_foul",
        ...     source=CorrectionSource.REPLAY_OVERTURN,
        ... )
        True
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: CorrectionPairExtractorConfig | None = None,
    ) -> None:
        self._config = config or CorrectionPairExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "CorrectionPairExtractor"

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
            f"CorrectionPairExtractor("
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
                pending={},
            )
            return eid

    def register_decision(
        self,
        extraction_id: UUID,
        decision: FinalDecision,
        quarter: int = 1,
        game_clock_sec: float = 0.0,
    ) -> bool:
        """
        판정을 교정 대기 상태로 등록.

        Args:
            extraction_id: 추출 세션 ID
            decision: 최종 판정
            quarter: 쿼터
            game_clock_sec: 잔여 시간

        Returns:
            등록 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if decision.result is None:
                return False
            # violated 판정만 교정 대상
            if not decision.result.violated:
                return False
            session.pending[decision.decision_id] = _PendingDecision(
                decision=decision,
                received_at=time.monotonic(),
                quarter=quarter,
                game_clock_sec=game_clock_sec,
            )
            return True

    def record_correction(
        self,
        extraction_id: UUID,
        decision_id: UUID,
        corrected_call: str,
        source: CorrectionSource,
        error_category: ErrorCategory | None = None,
        corrected_player_id: int | None = None,
    ) -> bool:
        """
        인간 교정을 기록하여 교정 쌍 레코드 생성.

        Args:
            extraction_id: 추출 세션 ID
            decision_id: 원본 판정 ID
            corrected_call: 교정된 콜 타입 (CallType.value 또는 "no_call")
            source: 교정 소스
            error_category: 오류 분류 (None이면 자동 판별)
            corrected_player_id: 교정된 위반 선수 ID (WRONG_PLAYER용)

        Returns:
            기록 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                return False

            pending = session.pending.pop(decision_id, None)
            if pending is None:
                return False

            original = pending.decision
            result = original.result
            if result is None:
                return False

            original_call = result.call_type.value if result.call_type else ""

            # 오류 분류 자동 판별
            if error_category is None:
                error_category = self._classify_error(
                    original_call=original_call,
                    corrected_call=corrected_call,
                    original_player=result.offending_player_id,
                    corrected_player=corrected_player_id,
                )

            # 심각도 차이 계산
            original_severity = _PENALTY_SEVERITY.get(
                result.penalty.value if result.penalty else "", 0,
            )
            # 교정 후 페널티 심각도는 no_call이면 0
            corrected_severity = 0 if corrected_call == "no_call" else original_severity
            severity_delta = abs(original_severity - corrected_severity)

            record = CorrectionPairRecord(
                frame_index=result.frame_number,
                original_call_type=original_call,
                original_confidence=result.confidence,
                original_evidence=list(result.evidence),
                corrected_call_type=corrected_call,
                correction_source=source.value,
                error_category=error_category.value,
                severity_delta=float(severity_delta),
                offending_player_id=result.offending_player_id,
                victim_player_id=result.victim_player_id,
                quarter=pending.quarter,
                game_clock_sec=pending.game_clock_sec,
            )

            session.records.append(record)
            self._total_records += 1
            return True

    def flush_confirmed(self, extraction_id: UUID) -> int:
        """
        타임아웃 초과 대기 판정을 CONFIRMED로 확정.

        Returns:
            확정된 판정 수
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return 0

            now = time.monotonic()
            expired_ids: list[UUID] = []
            for did, pending in session.pending.items():
                elapsed = now - pending.received_at
                if elapsed >= self._config.confirmation_timeout_sec:
                    expired_ids.append(did)

            for did in expired_ids:
                session.pending.pop(did, None)
                # 타임아웃 확정은 레코드를 생성하지 않음 (교정 없음 = 정답)

            return len(expired_ids)

    # -- 내부 --

    @staticmethod
    def _classify_error(
        original_call: str,
        corrected_call: str,
        original_player: int | None,
        corrected_player: int | None,
    ) -> ErrorCategory:
        """오류 분류 자동 판별."""
        # 선수 오류 (교정 선수가 명시되고 원본과 다름)
        if (
            corrected_player is not None
            and original_player is not None
            and corrected_player != original_player
        ):
            return ErrorCategory.WRONG_PLAYER
        # 오탐 (콜 → 노콜)
        if corrected_call == "no_call":
            return ErrorCategory.FALSE_POSITIVE
        # 미탐 (노콜 → 콜) — register_decision이 violated만 받으므로 이 경우는 드묾
        if original_call == "no_call":
            return ErrorCategory.FALSE_NEGATIVE
        # 유형 오류 (콜 타입이 다름)
        if original_call != corrected_call:
            return ErrorCategory.WRONG_TYPE
        # 기본값 (동일 타입이면 선수 오류로 추정)
        return ErrorCategory.WRONG_PLAYER

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.REFEREE_CORRECTION,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="AI 판정 vs 인간 교정 쌍 — 자가학습 최고 가치 데이터",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[CorrectionPairRecord]:
        """레코드 목록 반환."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return list(session.records)

    def get_pending_count(self, extraction_id: UUID) -> int:
        """교정 대기 중인 판정 수."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return 0
            return len(session.pending)

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
            total_pending = sum(
                len(s.pending) for s in self._sessions.values()
            )
            return {
                "total_extractions": len(self._sessions),
                "total_records": self._total_records,
                "total_pending": total_pending,
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
    "CorrectionPairExtractor",
    "CorrectionPairExtractorConfig",
    "CorrectionSource",
    "ErrorCategory",
]

__version__ = "1.0.0"
