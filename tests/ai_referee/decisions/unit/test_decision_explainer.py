# -*- coding: utf-8 -*-
"""DecisionExplainer 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import (
    PenaltyType,
    RuleCategory,
    RuleResult,
)
from ai_referee.decisions.decision_explainer import (
    DecisionExplanation,
    DecisionExplainer,
)


@pytest.fixture()
def explainer() -> DecisionExplainer:
    return DecisionExplainer(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.85,
    description: str = "블로킹 파울",
    rule_reference: str = "FIBA Rule 33.7B",
    evidence: list[str] | None = None,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    free_throws: int = 2,
    offender_id: int | None = 20,
    victim_id: int | None = 10,
    category: RuleCategory = RuleCategory.FOUL,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33.7B",
        category=category,
        description=description,
        rule_reference=rule_reference,
        evidence=evidence or ["수비자 이동 중 접촉", "하체 접촉"],
        penalty=penalty,
        free_throws_awarded=free_throws,
        offending_player_id=offender_id,
        victim_player_id=victim_id,
    )


class TestInit:
    def test_rule_set(self, explainer: DecisionExplainer) -> None:
        assert explainer.rule_set == RuleSet.FIBA


class TestExplain:
    def test_basic_explanation(self, explainer: DecisionExplainer) -> None:
        result = _make_result()
        exp = explainer.explain(result)
        assert isinstance(exp, DecisionExplanation)
        assert exp.title == "블로킹 파울"

    def test_category_korean(self, explainer: DecisionExplainer) -> None:
        result = _make_result()
        exp = explainer.explain(result)
        assert exp.category_ko == "파울"

    def test_violation_category(self, explainer: DecisionExplainer) -> None:
        result = _make_result(category=RuleCategory.VIOLATION)
        exp = explainer.explain(result)
        assert exp.category_ko == "바이올레이션"

    def test_evidence_summary(self, explainer: DecisionExplainer) -> None:
        result = _make_result(evidence=["증거A", "증거B"])
        exp = explainer.explain(result)
        assert "증거A" in exp.evidence_summary
        assert "증거B" in exp.evidence_summary

    def test_penalty_korean(self, explainer: DecisionExplainer) -> None:
        result = _make_result(free_throws=2)
        exp = explainer.explain(result)
        assert "자유투 2구" in exp.penalty_ko

    def test_ejection_penalty(self, explainer: DecisionExplainer) -> None:
        result = _make_result(
            penalty=PenaltyType.EJECTION, free_throws=0,
        )
        exp = explainer.explain(result)
        assert "퇴장" in exp.penalty_ko

    def test_confidence_percent(self, explainer: DecisionExplainer) -> None:
        result = _make_result(confidence=0.87)
        exp = explainer.explain(result)
        assert exp.confidence_pct == "87%"

    def test_offender_description(self, explainer: DecisionExplainer) -> None:
        result = _make_result(offender_id=20)
        exp = explainer.explain(result)
        assert "#20" in exp.offender_desc

    def test_full_text_contains_all(self, explainer: DecisionExplainer) -> None:
        result = _make_result()
        exp = explainer.explain(result)
        assert "[파울]" in exp.full_text
        assert "FIBA Rule 33.7B" in exp.full_text
        assert "근거:" in exp.full_text
        assert "페널티:" in exp.full_text
        assert "신뢰도:" in exp.full_text

    def test_low_confidence_requires_review(self, explainer: DecisionExplainer) -> None:
        result = _make_result(confidence=0.55)
        exp = explainer.explain(result)
        assert exp.requires_review is True
        assert "사람 확인 필요" in exp.full_text


class TestReset:
    def test_reset(self, explainer: DecisionExplainer) -> None:
        explainer.explain(_make_result())
        explainer.reset()
