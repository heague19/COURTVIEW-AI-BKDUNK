# -*- coding: utf-8 -*-
"""
feedback_system/analysis/referee_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.game_dto import (
    FoulEvent,
    RefereeDecision,
    ViolationEvent,
)
from shared.constants.game_rule_constants import (
    FoulType,
    GameEventType,
    ViolationType,
)

from feedback_system.analysis.referee_feedback import (
    RefereeFeedbackConfig,
    RefereeFeedbackGenerator,
)


@pytest.fixture
def gen() -> RefereeFeedbackGenerator:
    return RefereeFeedbackGenerator()


@pytest.fixture
def decisions() -> list[RefereeDecision]:
    return [
        RefereeDecision(
            decision_id="d1",
            frame_number=100,
            timestamp=4.0,
            decision_type="foul",
            confidence=0.92,
            foul_event=FoulEvent(
                event_id="f1",
                event_type=GameEventType.PERSONAL_FOUL,
                frame_number=100,
                timestamp=4.0,
                foul_type=FoulType.BLOCKING,
                confidence=0.92,
            ),
        ),
        RefereeDecision(
            decision_id="d2",
            frame_number=200,
            timestamp=8.0,
            decision_type="foul",
            confidence=0.88,
            foul_event=FoulEvent(
                event_id="f2",
                event_type=GameEventType.OFFENSIVE_FOUL,
                frame_number=200,
                timestamp=8.0,
                foul_type=FoulType.CHARGE,
                confidence=0.88,
            ),
        ),
        RefereeDecision(
            decision_id="d3",
            frame_number=300,
            timestamp=12.0,
            decision_type="violation",
            confidence=0.50,  # 논쟁적 판정
            violation_event=ViolationEvent(
                event_id="v1",
                event_type=GameEventType.TURNOVER,
                frame_number=300,
                timestamp=12.0,
                violation_type=ViolationType.TRAVELING,
                confidence=0.50,
            ),
        ),
        RefereeDecision(
            decision_id="d4",
            frame_number=400,
            timestamp=16.0,
            decision_type="no_call",
            confidence=0.75,
        ),
    ]


class TestRefereeFeedbackGenerator:

    def test_name(self, gen: RefereeFeedbackGenerator) -> None:
        assert gen.name == "RefereeFeedbackGenerator"

    def test_empty_decisions(self, gen: RefereeFeedbackGenerator) -> None:
        items = gen.generate([])
        assert len(items) == 0

    def test_generates_summary(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions)
        summary = next(i for i in items if "판정 요약" in i.title)
        assert "4건" in summary.description
        assert "파울 2건" in summary.description
        assert "바이올레이션 1건" in summary.description

    def test_foul_distribution(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions)
        foul_items = [i for i in items if "파울 분포" in i.title]
        assert len(foul_items) == 2  # blocking + charging

    def test_violation_distribution(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions)
        viol_items = [i for i in items if "바이올레이션" in i.title]
        assert len(viol_items) == 1

    def test_controversial_detection(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions)
        controversial = [i for i in items if "경계선" in i.title]
        assert len(controversial) == 1
        assert controversial[0].feedback_type == FeedbackType.WARNING

    def test_consistency_score_good(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions, consistency_score=85.0)
        consistency = next(i for i in items if "일관성" in i.title)
        assert consistency.feedback_type == FeedbackType.POSITIVE

    def test_consistency_score_bad(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        items = gen.generate(decisions, consistency_score=60.0)
        consistency = next(i for i in items if "일관성" in i.title)
        assert consistency.feedback_type == FeedbackType.CORRECTION

    def test_total_generated(
        self, gen: RefereeFeedbackGenerator, decisions: list[RefereeDecision],
    ) -> None:
        gen.generate(decisions)
        assert gen.total_generated == 1
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: RefereeFeedbackGenerator) -> None:
        assert "RefereeFeedbackGenerator" in repr(gen)
