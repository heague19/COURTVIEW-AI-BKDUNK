# -*- coding: utf-8 -*-
"""DecisionRecordExtractor 단위 테스트."""

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
from ai_referee.decisions.confidence_scorer import CalibrationResult
from ai_referee.decisions.consistency_tracker import ConsistencyReport
from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.data_extraction.decision_record_extractor import (
    DecisionRecordExtractor,
    DecisionRecordExtractorConfig,
)


# === 헬퍼 ===

def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.85,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    offender_id: int = 20,
    frame_number: int = 100,
    evidence: list[str] | None = None,
    call_type: CallType = CallType.PERSONAL_FOUL,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33",
        category=RuleCategory.FOUL,
        call_type=call_type,
        penalty=penalty,
        offending_player_id=offender_id,
        frame_number=frame_number,
        evidence=evidence or ["접촉 감지"],
    )


def _make_decision(
    *,
    violated: bool = True,
    confidence: float = 0.85,
    should_replay: bool = False,
    calibration: CalibrationResult | None = None,
    consistency: ConsistencyReport | None = None,
) -> FinalDecision:
    result = _make_result(violated=violated, confidence=confidence)
    return FinalDecision(
        result=result,
        calibration=calibration,
        consistency=consistency,
        final_confidence=confidence,
        confidence_level=DecisionConfidence.HIGH,
        should_replay=should_replay,
        frame_number=result.frame_number,
    )


def _make_context(frame: int = 100) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        quarter=2,
        game_clock_sec=300.0,
        player_positions={1: (5.0, 3.0), 2: (6.0, 4.0)},
        ball_position=(5.5, 3.5, 1.0),
    )


@pytest.fixture()
def extractor() -> DecisionRecordExtractor:
    return DecisionRecordExtractor()


# === 테스트 ===

class TestInit:
    def test_default_config(self, extractor: DecisionRecordExtractor) -> None:
        assert extractor.name == "DecisionRecordExtractor"
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = DecisionRecordExtractorConfig(max_extractions=10)
        ext = DecisionRecordExtractor(config=cfg)
        assert ext._config.max_extractions == 10


class TestSession:
    def test_create_extraction(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        assert extractor.total_extractions == 1

    def test_max_extractions(self) -> None:
        ext = DecisionRecordExtractor(
            config=DecisionRecordExtractorConfig(max_extractions=1),
        )
        eid1 = ext.create_extraction("g1")
        eid2 = ext.create_extraction("g2")
        assert eid1 is not None
        assert eid2 is None

    def test_delete_extraction(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        assert extractor.delete_extraction(eid)
        assert extractor.total_extractions == 0


class TestAddDecision:
    def test_add_call(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(violated=True)
        ctx = _make_context()
        assert extractor.add_decision(eid, decision, ctx)
        assert extractor.total_records == 1

    def test_add_no_call_sampling(self) -> None:
        """노콜은 샘플링 비율에 따라 제한."""
        ext = DecisionRecordExtractor(
            config=DecisionRecordExtractorConfig(
                no_call_sampling_ratio=0.0,
                min_confidence_for_no_call=0.30,
            ),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        # 노콜은 ratio=0.0이면 전부 거부
        decision = _make_decision(violated=False, confidence=0.50)
        ctx = _make_context()
        # 첫 노콜은 max(1, 0*0.0)=1이므로 통과할 수 있으나 random 의존
        # ratio=0.0이면 확률적으로도 거부
        # 여러 번 시도해서 거부 비율 확인
        added = sum(
            1 for _ in range(20)
            if ext.add_decision(eid, decision, ctx)
        )
        # ratio=0.0이면 확률적 샘플링도 0이므로 대부분 거부
        assert added <= 5  # 최대 일부만 통과 (초기 max_no_call=1 때문)

    def test_add_with_calibration(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        cal = CalibrationResult(
            original_confidence=0.80,
            calibrated_confidence=0.88,
            confidence_level=DecisionConfidence.HIGH,
            requires_human_review=False,
        )
        decision = _make_decision(calibration=cal)
        ctx = _make_context()
        assert extractor.add_decision(eid, decision, ctx)
        records = extractor.get_records(eid)
        assert len(records) == 1
        assert records[0].confidence_calibrated == 0.88

    def test_no_result_returns_false(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = FinalDecision(result=None)
        ctx = _make_context()
        assert not extractor.add_decision(eid, decision, ctx)


class TestReplayOutcome:
    def test_update_replay_outcome(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(should_replay=True)
        ctx = _make_context(frame=100)
        extractor.add_decision(eid, decision, ctx)
        assert extractor.update_replay_outcome(eid, 100, "OVERTURNED")
        records = extractor.get_records(eid)
        assert records[0].replay_outcome == "OVERTURNED"

    def test_update_nonexistent_frame(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        assert not extractor.update_replay_outcome(eid, 999, "CONFIRMED")


class TestBuildResult:
    def test_build_result(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        ctx = _make_context()
        extractor.add_decision(eid, decision, ctx)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1
        assert result.game_id == "game_001"

    def test_get_extraction_summary(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.add_decision(eid, _make_decision(violated=True), _make_context())
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["call_count"] == 1


class TestReset:
    def test_reset(self, extractor: DecisionRecordExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.add_decision(eid, _make_decision(), _make_context())
        extractor.reset()
        assert extractor.total_extractions == 0
        assert extractor.total_records == 0

    def test_repr(self, extractor: DecisionRecordExtractor) -> None:
        assert "DecisionRecordExtractor" in repr(extractor)
