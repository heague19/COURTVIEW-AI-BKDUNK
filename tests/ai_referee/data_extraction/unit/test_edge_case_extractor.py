# -*- coding: utf-8 -*-
"""EdgeCaseExtractor 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_decision_constants import DecisionConfidence

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.decisions.confidence_scorer import CalibrationResult
from ai_referee.decisions.consistency_tracker import ConsistencyReport
from ai_referee.decisions.multi_angle_validator import ValidationResult
from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.data_extraction.edge_case_extractor import (
    EdgeCaseExtractor,
    EdgeCaseExtractorConfig,
    UncertaintyReason,
)


# === 헬퍼 ===

def _make_decision(
    *,
    confidence: float = 0.70,
    agreement: float | None = None,
    consistency_score: float | None = None,
    similar_count: int = 0,
    evidence: list[str] | None = None,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
) -> FinalDecision:
    result = RuleResult(
        violated=True,
        confidence=confidence,
        rule_id="FIBA-33",
        category=RuleCategory.FOUL,
        penalty=penalty,
        offending_player_id=20,
        frame_number=100,
        evidence=evidence or ["접촉 감지"],
    )
    validation = None
    if agreement is not None:
        validation = ValidationResult(
            is_valid=agreement >= 0.75,
            agreement_ratio=agreement,
            final_confidence=confidence,
        )
    consistency = None
    if consistency_score is not None:
        consistency = ConsistencyReport(
            is_consistent=consistency_score >= 0.80,
            consistency_score=consistency_score,
            similar_count=similar_count,
        )
    return FinalDecision(
        result=result,
        validation=validation,
        consistency=consistency,
        final_confidence=confidence,
        confidence_level=DecisionConfidence.MODERATE,
        frame_number=100,
    )


def _make_context(frame: int = 100) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        player_positions={1: (5.0, 3.0), 2: (6.0, 4.0)},
    )


@pytest.fixture()
def extractor() -> EdgeCaseExtractor:
    return EdgeCaseExtractor()


# === 테스트 ===

class TestInit:
    def test_default(self, extractor: EdgeCaseExtractor) -> None:
        assert extractor.name == "EdgeCaseExtractor"
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = EdgeCaseExtractorConfig(max_confidence=0.90)
        ext = EdgeCaseExtractor(config=cfg)
        assert ext._config.max_confidence == 0.90


class TestEvaluateDecision:
    def test_low_confidence_captured(self, extractor: EdgeCaseExtractor) -> None:
        """신뢰도 0.70 (< 0.85) → 캡처."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.70)
        assert extractor.evaluate_decision(eid, decision, _make_context())
        assert extractor.total_records == 1

    def test_high_confidence_rejected(self, extractor: EdgeCaseExtractor) -> None:
        """신뢰도 0.95 (> 0.85) → 거부."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.95)
        assert not extractor.evaluate_decision(eid, decision, _make_context())

    def test_too_low_confidence_rejected(self, extractor: EdgeCaseExtractor) -> None:
        """신뢰도 0.30 (< 0.40) → 거부 (기본 설정)."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.30)
        assert not extractor.evaluate_decision(eid, decision, _make_context())

    def test_low_agreement_captured(self, extractor: EdgeCaseExtractor) -> None:
        """동의율 0.50 (< 0.75) → 캡처."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        # 신뢰도는 높지만 동의율이 낮음
        decision = _make_decision(confidence=0.90, agreement=0.50)
        assert extractor.evaluate_decision(eid, decision, _make_context())

    def test_low_consistency_captured(self, extractor: EdgeCaseExtractor) -> None:
        """일관성 0.50 (< 0.70) → 캡처."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.90, consistency_score=0.50)
        assert extractor.evaluate_decision(eid, decision, _make_context())


class TestPriority:
    def test_priority_increases_with_severity(self, extractor: EdgeCaseExtractor) -> None:
        """퇴장 페널티가 턴오버보다 우선순위 높음."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        d_high = _make_decision(confidence=0.70, penalty=PenaltyType.EJECTION)
        d_low = _make_decision(confidence=0.70, penalty=PenaltyType.TURNOVER)
        extractor.evaluate_decision(eid, d_high, _make_context())
        extractor.evaluate_decision(eid, d_low, _make_context())
        records = extractor.get_records(eid)  # 우선순위 내림차순
        assert records[0].labeling_priority >= records[1].labeling_priority

    def test_priority_increases_with_lower_confidence(self, extractor: EdgeCaseExtractor) -> None:
        """낮은 신뢰도가 높은 우선순위."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        d_low = _make_decision(confidence=0.45)
        d_high = _make_decision(confidence=0.80)
        extractor.evaluate_decision(eid, d_low, _make_context())
        extractor.evaluate_decision(eid, d_high, _make_context())
        records = extractor.get_records(eid)
        assert records[0].labeling_priority > records[1].labeling_priority


class TestUncertaintyReason:
    def test_low_evidence(self, extractor: EdgeCaseExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.60, evidence=["단일 근거"])
        extractor.evaluate_decision(eid, decision, _make_context())
        records = extractor.get_records(eid)
        assert records[0].uncertainty_reason == UncertaintyReason.LOW_EVIDENCE.value

    def test_conflicting_angles(self, extractor: EdgeCaseExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(
            confidence=0.70, agreement=0.40,
            evidence=["근거1", "근거2"],
        )
        extractor.evaluate_decision(eid, decision, _make_context())
        records = extractor.get_records(eid)
        assert records[0].uncertainty_reason == UncertaintyReason.CONFLICTING_ANGLES.value


class TestBuildResult:
    def test_build_result(self, extractor: EdgeCaseExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.evaluate_decision(eid, _make_decision(), _make_context())
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1

    def test_summary(self, extractor: EdgeCaseExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.evaluate_decision(eid, _make_decision(confidence=0.60), _make_context())
        summary = extractor.get_extraction_summary(eid)
        assert summary is not None
        assert summary["total_records"] == 1
        assert summary["avg_confidence"] > 0


class TestUtility:
    def test_reset(self, extractor: EdgeCaseExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.evaluate_decision(eid, _make_decision(), _make_context())
        extractor.reset()
        assert extractor.total_records == 0

    def test_repr(self, extractor: EdgeCaseExtractor) -> None:
        assert "EdgeCaseExtractor" in repr(extractor)
