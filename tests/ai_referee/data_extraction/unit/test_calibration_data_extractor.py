# -*- coding: utf-8 -*-
"""CalibrationDataExtractor 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_decision_constants import DecisionConfidence
from shared.constants.referee_rule_constants import CallType

from ai_referee.rules.base_rule import (
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.decisions.confidence_scorer import CalibrationResult
from ai_referee.decisions.decision_engine import FinalDecision
from ai_referee.data_extraction.calibration_data_extractor import (
    ActualOutcome,
    CalibrationDataExtractor,
    CalibrationDataExtractorConfig,
)


# === 헬퍼 ===

def _make_decision(
    *,
    confidence: float = 0.85,
    calibration: CalibrationResult | None = None,
) -> FinalDecision:
    result = RuleResult(
        violated=True,
        confidence=confidence,
        rule_id="FIBA-33",
        category=RuleCategory.FOUL,
        call_type=CallType.PERSONAL_FOUL,
        penalty=PenaltyType.FREE_THROWS,
        offending_player_id=20,
        frame_number=100,
    )
    return FinalDecision(
        result=result,
        calibration=calibration,
        final_confidence=confidence,
        confidence_level=DecisionConfidence.HIGH,
        frame_number=100,
    )


@pytest.fixture()
def extractor() -> CalibrationDataExtractor:
    return CalibrationDataExtractor()


# === 테스트 ===

class TestInit:
    def test_default(self, extractor: CalibrationDataExtractor) -> None:
        assert extractor.name == "CalibrationDataExtractor"
        assert extractor.total_records == 0

    def test_custom_config(self) -> None:
        cfg = CalibrationDataExtractorConfig(bin_width=0.10)
        ext = CalibrationDataExtractor(config=cfg)
        assert ext._config.bin_width == 0.10


class TestAddOutcome:
    def test_confirmed(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.87)
        assert extractor.add_outcome(
            eid, decision, ActualOutcome.CONFIRMED, quarter=2, game_clock_sec=300.0,
        )
        records = extractor.get_records(eid)
        assert len(records) == 1
        assert records[0].actual_outcome == "confirmed"
        assert records[0].predicted_confidence == 0.87

    def test_overturned(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.60)
        assert extractor.add_outcome(eid, decision, ActualOutcome.OVERTURNED)
        records = extractor.get_records(eid)
        assert records[0].actual_outcome == "overturned"

    def test_clutch_detection(self, extractor: CalibrationDataExtractor) -> None:
        """4쿼터 잔여 2분 이내 → is_clutch=True."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        extractor.add_outcome(
            eid, decision, ActualOutcome.CONFIRMED,
            quarter=4, game_clock_sec=90.0,
        )
        records = extractor.get_records(eid)
        assert records[0].is_clutch is True

    def test_non_clutch(self, extractor: CalibrationDataExtractor) -> None:
        """2쿼터 → is_clutch=False."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision()
        extractor.add_outcome(
            eid, decision, ActualOutcome.CONFIRMED,
            quarter=2, game_clock_sec=300.0,
        )
        records = extractor.get_records(eid)
        assert records[0].is_clutch is False

    def test_with_calibration_factors(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        cal = CalibrationResult(
            original_confidence=0.80,
            calibrated_confidence=0.88,
            confidence_level=DecisionConfidence.HIGH,
            requires_human_review=False,
        )
        decision = _make_decision(calibration=cal)
        extractor.add_outcome(eid, decision, ActualOutcome.CONFIRMED)
        records = extractor.get_records(eid)
        assert "original" in records[0].calibration_factors
        assert records[0].calibration_factors["calibrated"] == 0.88


class TestBinning:
    def test_bin_center(self, extractor: CalibrationDataExtractor) -> None:
        """0.87 → bin_width=0.05 → bin_center=0.875."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.87)
        extractor.add_outcome(eid, decision, ActualOutcome.CONFIRMED)
        records = extractor.get_records(eid)
        assert records[0].confidence_bin == 0.875

    def test_bin_edge(self, extractor: CalibrationDataExtractor) -> None:
        """0.85 → bin_center=0.875."""
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        decision = _make_decision(confidence=0.85)
        extractor.add_outcome(eid, decision, ActualOutcome.CONFIRMED)
        records = extractor.get_records(eid)
        assert records[0].confidence_bin == 0.875


class TestCalibrationSummary:
    def test_summary(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        # 같은 빈에 2개: 1 confirmed, 1 overturned
        d1 = _make_decision(confidence=0.86)
        d2 = _make_decision(confidence=0.87)
        extractor.add_outcome(eid, d1, ActualOutcome.CONFIRMED)
        extractor.add_outcome(eid, d2, ActualOutcome.OVERTURNED)
        summary = extractor.get_calibration_summary(eid)
        assert summary is not None
        bin_key = "0.875"
        assert bin_key in summary
        assert summary[bin_key]["count"] == 2
        assert summary[bin_key]["confirmed_ratio"] == 0.5

    def test_validity_check(self) -> None:
        """30개 미만이면 is_valid=False."""
        ext = CalibrationDataExtractor(
            config=CalibrationDataExtractorConfig(min_samples_per_bin=30),
        )
        eid = ext.create_extraction("game_001")
        assert eid is not None
        ext.add_outcome(eid, _make_decision(confidence=0.86), ActualOutcome.CONFIRMED)
        summary = ext.get_calibration_summary(eid)
        assert summary is not None
        bin_key = "0.875"
        assert summary[bin_key]["is_valid"] is False


class TestBuildResult:
    def test_build_result(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.add_outcome(eid, _make_decision(), ActualOutcome.CONFIRMED)
        result = extractor.build_result(eid)
        assert result is not None
        assert result.record_count == 1


class TestUtility:
    def test_reset(self, extractor: CalibrationDataExtractor) -> None:
        eid = extractor.create_extraction("game_001")
        assert eid is not None
        extractor.add_outcome(eid, _make_decision(), ActualOutcome.CONFIRMED)
        extractor.reset()
        assert extractor.total_records == 0

    def test_repr(self, extractor: CalibrationDataExtractor) -> None:
        assert "CalibrationDataExtractor" in repr(extractor)
