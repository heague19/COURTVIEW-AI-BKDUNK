# -*- coding: utf-8 -*-
"""CorrectionPairExtractor 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_decision_constants import DecisionConfidence
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.data_extraction.correction_pair_extractor import (
    CorrectionPairExtractor,
    CorrectionPairExtractorConfig,
    CorrectionSource,
    ErrorCategory,
)


# === 헬퍼 ===

def _make_decision(
    *,
    violated: bool = True,
    confidence: float = 0.85,
    call_type: CallType = CallType.PERSONAL_FOUL,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    offender_id: int = 20,
    frame_number: int = 100,
) -> FinalDecision:
    result = RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33",
        category=RuleCategory.FOUL,
        call_type=call_type,
        penalty=penalty,
        offending_player_id=offender_id,
        frame_number=frame_number,
        evidence=["접촉 감지", "수비 이동"],
    )
    return FinalDecision(
        result=result,
        final_confidence=confidence,
        confidence_level=DecisionConfidence.HIGH,
        frame_number=frame_number,
    )


@pytest.fixture()
def extractor() -> CorrectionPairExtractor:
    return CorrectionPairExtractor()


# === 테스트 ===

class TestInit:
    def test_default(self, extractor: CorrectionPairExtractor) -> None:
        assert extractor.name == "CorrectionPairExtractor"
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = CorrectionPairExtractorConfig(confirmation_timeout_sec=60.0)
        ext = CorrectionPairExtractor(config=cfg)
        assert ext._config.confirmation_timeout_sec == 60.0


class TestRegisterDecision:
    def test_register(self, extractor: CorrectionPairExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        assert extractor.register_decision(eid, decision, quarter=2, game_clock_sec=300.0)
        assert extractor.get_pending_count(eid) == 1

    def test_register_no_call_rejected(self, extractor: CorrectionPairExtractor) -> None:
        """노콜 판정은 등록 거부."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(violated=False)
        assert not extractor.register_decision(eid, decision)


class TestRecordCorrection:
    def test_false_positive(self, extractor: CorrectionPairExtractor) -> None:
        """콜 → 노콜 = FALSE_POSITIVE."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        extractor.register_decision(eid, decision, quarter=3, game_clock_sec=120.0)
        assert extractor.record_correction(
            eid,
            decision.decision_id,
            corrected_call="no_call",
            source=CorrectionSource.REPLAY_OVERTURN,
        )
        records = extractor.get_records(eid)
        assert len(records) == 1
        assert records[0].error_category == ErrorCategory.FALSE_POSITIVE.value
        assert records[0].correction_source == "replay_overturn"

    def test_wrong_type(self, extractor: CorrectionPairExtractor) -> None:
        """콜 유형 오류 = WRONG_TYPE."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(call_type=CallType.PERSONAL_FOUL)
        extractor.register_decision(eid, decision)
        assert extractor.record_correction(
            eid,
            decision.decision_id,
            corrected_call="offensive_foul",
            source=CorrectionSource.COACH_CHALLENGE,
        )
        records = extractor.get_records(eid)
        assert records[0].error_category == ErrorCategory.WRONG_TYPE.value

    def test_wrong_player(self, extractor: CorrectionPairExtractor) -> None:
        """선수 식별 오류 = WRONG_PLAYER."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(offender_id=20)
        extractor.register_decision(eid, decision)
        assert extractor.record_correction(
            eid,
            decision.decision_id,
            corrected_call="personal_foul",
            source=CorrectionSource.MANUAL_REVIEW,
            corrected_player_id=30,
        )
        records = extractor.get_records(eid)
        assert records[0].error_category == ErrorCategory.WRONG_PLAYER.value

    def test_explicit_error_category(self, extractor: CorrectionPairExtractor) -> None:
        """명시적 오류 분류 지정."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        extractor.register_decision(eid, decision)
        assert extractor.record_correction(
            eid,
            decision.decision_id,
            corrected_call="no_call",
            source=CorrectionSource.REPLAY_OVERTURN,
            error_category=ErrorCategory.FALSE_NEGATIVE,
        )
        records = extractor.get_records(eid)
        assert records[0].error_category == ErrorCategory.FALSE_NEGATIVE.value

    def test_unregistered_decision_rejected(self, extractor: CorrectionPairExtractor) -> None:
        from uuid import uuid4
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        assert not extractor.record_correction(
            eid, uuid4(), "no_call", CorrectionSource.MANUAL_REVIEW,
        )

    def test_severity_delta(self, extractor: CorrectionPairExtractor) -> None:
        """심각도 차이 계산."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(penalty=PenaltyType.FREE_THROWS)  # severity=4
        extractor.register_decision(eid, decision)
        extractor.record_correction(
            eid, decision.decision_id,
            corrected_call="no_call",  # severity=0
            source=CorrectionSource.REPLAY_OVERTURN,
        )
        records = extractor.get_records(eid)
        assert records[0].severity_delta == 4.0


class TestFlushConfirmed:
    def test_flush_expired(self) -> None:
        ext = CorrectionPairExtractor(
            config=CorrectionPairExtractorConfig(confirmation_timeout_sec=0.0),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        ext.register_decision(eid, decision)
        flushed = ext.flush_confirmed(eid)
        assert flushed == 1
        assert ext.get_pending_count(eid) == 0


class TestBuildResult:
    def test_build_result(self, extractor: CorrectionPairExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        extractor.register_decision(eid, decision)
        extractor.record_correction(
            eid, decision.decision_id,
            corrected_call="no_call",
            source=CorrectionSource.REPLAY_OVERTURN,
        )
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1


class TestUtility:
    def test_reset(self, extractor: CorrectionPairExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.reset()
        assert extractor.total_extractions == 0

    def test_get_stats(self, extractor: CorrectionPairExtractor) -> None:
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 0
        assert stats["total_records"] == 0

    def test_repr(self, extractor: CorrectionPairExtractor) -> None:
        assert "CorrectionPairExtractor" in repr(extractor)
