# -*- coding: utf-8 -*-
"""ConfidenceScorer 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_decision_constants import DecisionConfidence
from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.decisions.confidence_scorer import (
    CalibrationResult,
    ConfidenceScorer,
)


@pytest.fixture()
def scorer() -> ConfidenceScorer:
    return ConfidenceScorer(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    confidence: float = 0.80,
    evidence: list[str] | None = None,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    category: RuleCategory = RuleCategory.FOUL,
) -> RuleResult:
    return RuleResult(
        violated=True,
        confidence=confidence,
        rule_id="FIBA-33",
        category=category,
        penalty=penalty,
        evidence=evidence or [],
    )


def _make_context(
    *,
    quarter: int = 1,
    clock: float = 600.0,
    score_diff: int = 20,
    is_scoring_play: bool = False,
) -> FrameContext:
    e: dict = {"score_diff": score_diff}
    if is_scoring_play:
        e["is_scoring_play"] = True
    return FrameContext(
        frame_number=1,
        quarter=quarter,
        game_clock_sec=clock,
        extra=e,
    )


class TestInit:
    def test_rule_set(self, scorer: ConfidenceScorer) -> None:
        assert scorer.rule_set == RuleSet.FIBA


class TestCalibrate:
    def test_basic_calibration(self, scorer: ConfidenceScorer) -> None:
        result = _make_result(confidence=0.80)
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert isinstance(cal, CalibrationResult)
        assert cal.original_confidence == 0.80

    def test_evidence_boost(self, scorer: ConfidenceScorer) -> None:
        """근거 항목이 많으면 신뢰도 상승."""
        result = _make_result(
            confidence=0.80,
            evidence=["증거1", "증거2", "증거3", "증거4"],
        )
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert cal.calibrated_confidence > cal.original_confidence

    def test_clutch_penalty(self, scorer: ConfidenceScorer) -> None:
        """클러치 상황에서 보수적 감점."""
        result = _make_result(confidence=0.85)
        ctx = _make_context(quarter=4, clock=120.0, score_diff=3)
        cal = scorer.calibrate(result, ctx)
        assert cal.calibrated_confidence < 0.85

    def test_ejection_penalty(self, scorer: ConfidenceScorer) -> None:
        """퇴장 판정 보수적 감점."""
        result = _make_result(
            confidence=0.90, penalty=PenaltyType.EJECTION,
        )
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert cal.calibrated_confidence < 0.90

    def test_high_confidence_level(self, scorer: ConfidenceScorer) -> None:
        """높은 신뢰도 → HIGH 등급."""
        result = _make_result(confidence=0.90)
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert cal.confidence_level in (
            DecisionConfidence.HIGH,
            DecisionConfidence.AUTO_CONFIRM,
        )

    def test_low_confidence_requires_review(self, scorer: ConfidenceScorer) -> None:
        """낮은 신뢰도 → 리뷰 필요."""
        result = _make_result(confidence=0.55)
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert cal.requires_human_review is True

    def test_auto_confirm_no_review(self, scorer: ConfidenceScorer) -> None:
        """자동 확정 → 리뷰 불필요."""
        result = _make_result(
            confidence=0.98,
            evidence=["a", "b", "c"],
            category=RuleCategory.VIOLATION,
        )
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        assert cal.requires_human_review is False

    def test_violation_no_foul_penalty(self, scorer: ConfidenceScorer) -> None:
        """바이올레이션은 파울 감점 없음."""
        result = _make_result(
            confidence=0.85, category=RuleCategory.VIOLATION,
        )
        ctx = _make_context()
        cal = scorer.calibrate(result, ctx)
        # 파울 감점(-0.02)이 없으므로 약간 더 높음
        foul_result = _make_result(
            confidence=0.85, category=RuleCategory.FOUL,
        )
        foul_cal = scorer.calibrate(foul_result, ctx)
        assert cal.calibrated_confidence >= foul_cal.calibrated_confidence


class TestAverage:
    def test_average_confidence(self, scorer: ConfidenceScorer) -> None:
        ctx = _make_context()
        for c in [0.80, 0.90]:
            scorer.calibrate(_make_result(confidence=c), ctx)
        avg = scorer.get_average_confidence()
        assert avg > 0


class TestReset:
    def test_reset(self, scorer: ConfidenceScorer) -> None:
        scorer.calibrate(
            _make_result(confidence=0.80), _make_context(),
        )
        scorer.reset()
        assert scorer.get_average_confidence() == 0.0
