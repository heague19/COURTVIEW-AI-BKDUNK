# -*- coding: utf-8 -*-
"""DecisionEngine 단위 테스트."""

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
from ai_referee.decisions.decision_engine import (
    DecisionEngine,
    FinalDecision,
)


@pytest.fixture()
def engine() -> DecisionEngine:
    return DecisionEngine(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.85,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    offender_id: int | None = 20,
    frame_number: int = 100,
    rule_id: str = "FIBA-33",
    evidence: list[str] | None = None,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id=rule_id,
        category=RuleCategory.FOUL,
        penalty=penalty,
        offending_player_id=offender_id,
        frame_number=frame_number,
        start_frame=frame_number,
        end_frame=frame_number,
        evidence=evidence or ["접촉 감지"],
        free_throws_awarded=2,
    )


def _make_context(frame: int = 100) -> FrameContext:
    return FrameContext(frame_number=frame)


class TestInit:
    def test_rule_set(self, engine: DecisionEngine) -> None:
        assert engine.rule_set == RuleSet.FIBA

    def test_sub_components(self, engine: DecisionEngine) -> None:
        assert engine.confidence_scorer is not None
        assert engine.multi_angle_validator is not None
        assert engine.consistency_tracker is not None
        assert engine.replay_manager is not None


class TestProcessResults:
    def test_no_violations_empty(self, engine: DecisionEngine) -> None:
        """위반 없으면 빈 결과."""
        results = [_make_result(violated=False)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert len(decisions) == 0

    def test_single_violation(self, engine: DecisionEngine) -> None:
        """단일 위반 → 단일 판정."""
        results = [_make_result(confidence=0.85)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert len(decisions) == 1
        assert isinstance(decisions[0], FinalDecision)
        assert decisions[0].result is not None

    def test_multiple_violations(self, engine: DecisionEngine) -> None:
        """복수 위반 → 복수 판정 (심각도 순)."""
        results = [
            _make_result(
                confidence=0.80,
                penalty=PenaltyType.FREE_THROWS,
                offender_id=20,
                frame_number=100,
            ),
            _make_result(
                confidence=0.90,
                penalty=PenaltyType.EJECTION,
                offender_id=30,
                frame_number=200,
            ),
        ]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert len(decisions) == 2
        # 퇴장이 먼저
        assert decisions[0].result.penalty == PenaltyType.EJECTION

    def test_deduplication(self, engine: DecisionEngine) -> None:
        """동일 선수 + 유사 프레임 → 중복 제거."""
        results = [
            _make_result(
                confidence=0.80,
                penalty=PenaltyType.FREE_THROWS,
                offender_id=20,
                frame_number=100,
                rule_id="FIBA-33",
            ),
            _make_result(
                confidence=0.90,
                penalty=PenaltyType.EJECTION,
                offender_id=20,
                frame_number=102,  # 같은 5프레임 윈도우
                rule_id="FIBA-36",
            ),
        ]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        # 중복 제거 후 1건 (높은 심각도)
        assert len(decisions) == 1
        assert decisions[0].result.penalty == PenaltyType.EJECTION


class TestCalibration:
    def test_confidence_calibrated(self, engine: DecisionEngine) -> None:
        """신뢰도 보정 적용."""
        results = [_make_result(confidence=0.85)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert decisions[0].calibration is not None
        assert decisions[0].final_confidence > 0

    def test_confidence_level_assigned(self, engine: DecisionEngine) -> None:
        """신뢰도 등급 할당."""
        results = [_make_result(confidence=0.90)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert decisions[0].confidence_level in (
            DecisionConfidence.HIGH,
            DecisionConfidence.AUTO_CONFIRM,
            DecisionConfidence.MODERATE,
        )


class TestExplanation:
    def test_explanation_generated(self, engine: DecisionEngine) -> None:
        """설명 생성."""
        results = [_make_result(confidence=0.85)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert decisions[0].explanation is not None
        assert decisions[0].explanation.full_text != ""


class TestReplay:
    def test_close_call_replay(self, engine: DecisionEngine) -> None:
        """경계 신뢰도 → 리플레이."""
        results = [_make_result(confidence=0.60)]
        ctx = _make_context()
        decisions = engine.process_results(results, ctx)
        assert decisions[0].should_replay is True


class TestStats:
    def test_stats(self, engine: DecisionEngine) -> None:
        results = [_make_result()]
        ctx = _make_context()
        engine.process_results(results, ctx)
        stats = engine.get_stats()
        assert stats["total_decisions"] == 1


class TestReset:
    def test_reset(self, engine: DecisionEngine) -> None:
        results = [_make_result()]
        ctx = _make_context()
        engine.process_results(results, ctx)
        engine.reset()
        stats = engine.get_stats()
        assert stats["total_decisions"] == 0
