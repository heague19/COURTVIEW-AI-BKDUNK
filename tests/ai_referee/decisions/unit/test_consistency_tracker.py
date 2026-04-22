# -*- coding: utf-8 -*-
"""ConsistencyTracker 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import RuleResult
from ai_referee.decisions.consistency_tracker import (
    ConsistencyReport,
    ConsistencyTracker,
)


@pytest.fixture()
def tracker() -> ConsistencyTracker:
    return ConsistencyTracker(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.80,
    call_type: CallType = CallType.PERSONAL_FOUL,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33",
        call_type=call_type,
    )


class TestInit:
    def test_rule_set(self, tracker: ConsistencyTracker) -> None:
        assert tracker.rule_set == RuleSet.FIBA


class TestRecord:
    def test_record_decision(self, tracker: ConsistencyTracker) -> None:
        result = _make_result()
        tracker.record_decision(result, team_id="team_a")
        counts = tracker.get_team_call_counts()
        assert counts["team_a"]["calls"] == 1

    def test_record_nocall(self, tracker: ConsistencyTracker) -> None:
        result = _make_result(violated=False)
        tracker.record_decision(result, team_id="team_a")
        counts = tracker.get_team_call_counts()
        assert counts["team_a"]["nocalls"] == 1


class TestConsistency:
    def test_consistent_calls(self, tracker: ConsistencyTracker) -> None:
        """일관된 콜 → 일관성 보고."""
        for _ in range(5):
            r = _make_result(violated=True, confidence=0.80)
            tracker.record_decision(r, team_id="team_a")

        r = _make_result(violated=True, confidence=0.80)
        report = tracker.check_consistency(r, team_id="team_a")
        assert isinstance(report, ConsistencyReport)
        assert report.is_consistent is True

    def test_inconsistent_nocall(self, tracker: ConsistencyTracker) -> None:
        """유사 상황 콜 후 노콜 → 비일관."""
        for _ in range(5):
            r = _make_result(violated=True, confidence=0.80)
            tracker.record_decision(r, team_id="team_a")

        no_call = _make_result(violated=False, confidence=0.80)
        report = tracker.check_consistency(no_call, team_id="team_a")
        assert report.consistency_score < 1.0

    def test_no_history_consistent(self, tracker: ConsistencyTracker) -> None:
        """이력 없을 때 일관성 = True."""
        r = _make_result()
        report = tracker.check_consistency(r)
        assert report.is_consistent is True


class TestBias:
    def test_team_bias_detection(self, tracker: ConsistencyTracker) -> None:
        """한쪽 팀 콜 편중 → 편향 경고."""
        # 팀A에 15번 콜, 팀B에 2번 콜
        for _ in range(15):
            tracker.record_decision(
                _make_result(violated=True),
                team_id="team_a",
            )
        for _ in range(2):
            tracker.record_decision(
                _make_result(violated=True),
                team_id="team_b",
            )

        r = _make_result()
        report = tracker.check_consistency(r, team_id="team_a")
        assert len(report.bias_warnings) > 0

    def test_no_bias_balanced(self, tracker: ConsistencyTracker) -> None:
        """균형 잡힌 콜 → 편향 없음."""
        for _ in range(8):
            tracker.record_decision(
                _make_result(violated=True),
                team_id="team_a",
            )
        for _ in range(8):
            tracker.record_decision(
                _make_result(violated=True),
                team_id="team_b",
            )

        r = _make_result()
        report = tracker.check_consistency(r, team_id="team_a")
        assert len(report.bias_warnings) == 0


class TestCallLevel:
    def test_tight_call_level(self, tracker: ConsistencyTracker) -> None:
        """높은 콜 비율 → tight."""
        for _ in range(15):
            tracker.record_decision(
                _make_result(violated=True),
                team_id="team_a",
            )
        assert tracker.get_call_level() == "tight"

    def test_loose_call_level(self, tracker: ConsistencyTracker) -> None:
        """낮은 콜 비율 → loose."""
        for i in range(15):
            tracker.record_decision(
                _make_result(violated=(i < 2)),  # 2/15 = 13%
                team_id="team_a",
            )
        assert tracker.get_call_level() == "loose"

    def test_normal_call_level(self, tracker: ConsistencyTracker) -> None:
        """적절한 콜 비율 → normal."""
        for i in range(15):
            tracker.record_decision(
                _make_result(violated=(i < 6)),  # 6/15 = 40%
                team_id="team_a",
            )
        assert tracker.get_call_level() == "normal"


class TestReset:
    def test_reset(self, tracker: ConsistencyTracker) -> None:
        tracker.record_decision(
            _make_result(), team_id="team_a",
        )
        tracker.reset()
        counts = tracker.get_team_call_counts()
        assert len(counts) == 0
