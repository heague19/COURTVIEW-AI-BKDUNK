# -*- coding: utf-8 -*-
"""feedback_system/analysis/rotation_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.tactical_dto import (
    IndividualAnalysis,
    LineupData,
)

from feedback_system.analysis.rotation_feedback import (
    RotationFeedbackConfig,
    RotationFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> RotationFeedbackGenerator:
    return RotationFeedbackGenerator()


@pytest.fixture
def lineups() -> list[LineupData]:
    return [
        LineupData(
            lineup_id="L1",
            player_tracking_ids=[1, 2, 3, 4, 5],
            minutes=18.5,
            net_rating=8.2,
            offensive_rating=112.5,
            defensive_rating=104.3,
        ),
        LineupData(
            lineup_id="L2",
            player_tracking_ids=[1, 2, 6, 7, 8],
            minutes=12.0,
            net_rating=-3.5,
            offensive_rating=98.0,
            defensive_rating=101.5,
        ),
        LineupData(
            lineup_id="L3",
            player_tracking_ids=[6, 7, 8, 9, 10],
            minutes=8.0,
            net_rating=1.2,
            offensive_rating=105.0,
            defensive_rating=103.8,
        ),
    ]


@pytest.fixture
def individual_analyses() -> list[IndividualAnalysis]:
    return [
        IndividualAnalysis(
            player_tracking_id=1,
            on_court_net_rating=7.5,
            off_court_net_rating=0.0,
        ),
        IndividualAnalysis(
            player_tracking_id=6,
            on_court_net_rating=-1.2,
            off_court_net_rating=0.0,
        ),
    ]


# =============================================================================
# 테스트
# =============================================================================
class TestRotationFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = RotationFeedbackConfig()
        assert cfg.overplay_minutes_threshold == 36.0
        assert cfg.fatigue_warning_threshold == 0.15

    def test_custom(self) -> None:
        cfg = RotationFeedbackConfig(overplay_minutes_threshold=34.0)
        assert cfg.overplay_minutes_threshold == 34.0


class TestRotationFeedbackGenerator:
    def test_name(self, gen: RotationFeedbackGenerator) -> None:
        assert gen.name == "RotationFeedbackGenerator"

    def test_generate_with_lineups_only(
        self,
        gen: RotationFeedbackGenerator,
        lineups: list[LineupData],
    ) -> None:
        items = gen.generate(lineups)
        assert len(items) > 0
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_generate_with_individual(
        self,
        gen: RotationFeedbackGenerator,
        lineups: list[LineupData],
        individual_analyses: list[IndividualAnalysis],
    ) -> None:
        items = gen.generate(lineups, individual_analyses=individual_analyses)
        assert len(items) > 0

    def test_empty_lineups(self, gen: RotationFeedbackGenerator) -> None:
        items = gen.generate([])
        assert isinstance(items, list)

    def test_total_generated(
        self,
        gen: RotationFeedbackGenerator,
        lineups: list[LineupData],
    ) -> None:
        gen.generate(lineups)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: RotationFeedbackGenerator,
        lineups: list[LineupData],
    ) -> None:
        gen.generate(lineups)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: RotationFeedbackGenerator) -> None:
        assert "RotationFeedbackGenerator" in repr(gen)
