# -*- coding: utf-8 -*-
"""feedback_system/analysis/quarter_momentum_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.tactical_dto import (
    GameFlowData,
    MomentumShift,
    MomentumState,
    ScoringRun,
    TimeoutEffectiveness,
)

from feedback_system.analysis.quarter_momentum_feedback import (
    QuarterMomentumFeedbackConfig,
    QuarterMomentumFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> QuarterMomentumFeedbackGenerator:
    return QuarterMomentumFeedbackGenerator()


@pytest.fixture
def scoring_runs() -> list[ScoringRun]:
    return [
        ScoringRun(team_id="home", points=8, start_time=60.0, end_time=180.0),
        ScoringRun(team_id="away", points=12, start_time=300.0, end_time=480.0),
    ]


@pytest.fixture
def flow(scoring_runs: list[ScoringRun]) -> GameFlowData:
    return GameFlowData(
        scoring_runs=scoring_runs,
        momentum_shifts=[
            MomentumShift(frame=100, from_state="neutral", to_state="slight_home"),
            MomentumShift(frame=500, from_state="slight_home", to_state="slight_away"),
        ],
        current_momentum=MomentumState.NEUTRAL,
        lead_changes=7,
        ties=4,
        largest_lead_home=12,
        largest_lead_away=8,
        timeout_effectiveness=TimeoutEffectiveness(
            pre_timeout_trend="negative",
            post_timeout_trend="positive",
            scoring_change=5.2,
        ),
    )


# =============================================================================
# 테스트
# =============================================================================
class TestQuarterMomentumFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = QuarterMomentumFeedbackConfig()
        assert cfg.min_scoring_run_points == 6
        assert cfg.big_scoring_run_points == 10
        assert cfg.lead_change_stable == 5

    def test_custom(self) -> None:
        cfg = QuarterMomentumFeedbackConfig(min_scoring_run_points=8)
        assert cfg.min_scoring_run_points == 8


class TestQuarterMomentumFeedbackGenerator:
    def test_name(self, gen: QuarterMomentumFeedbackGenerator) -> None:
        assert gen.name == "QuarterMomentumFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: QuarterMomentumFeedbackGenerator,
        flow: GameFlowData,
    ) -> None:
        items = gen.generate(flow)
        assert len(items) > 0
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_total_generated(
        self,
        gen: QuarterMomentumFeedbackGenerator,
        flow: GameFlowData,
    ) -> None:
        assert gen.total_generated == 0
        gen.generate(flow)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: QuarterMomentumFeedbackGenerator,
        flow: GameFlowData,
    ) -> None:
        gen.generate(flow)
        gen.reset()
        assert gen.total_generated == 0

    def test_no_timeout_data(
        self,
        gen: QuarterMomentumFeedbackGenerator,
        scoring_runs: list[ScoringRun],
    ) -> None:
        flow = GameFlowData(
            scoring_runs=scoring_runs,
            momentum_shifts=[],
            current_momentum=MomentumState.STRONG_HOME,
            lead_changes=2,
            ties=1,
            largest_lead_home=20,
            largest_lead_away=3,
            timeout_effectiveness=None,
        )
        items = gen.generate(flow)
        assert isinstance(items, list)

    def test_repr(self, gen: QuarterMomentumFeedbackGenerator) -> None:
        assert "QuarterMomentumFeedbackGenerator" in repr(gen)
