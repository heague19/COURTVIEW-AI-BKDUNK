# -*- coding: utf-8 -*-
"""
feedback_system/analysis/individual_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.game_dto import PlayerStats

from feedback_system.analysis.individual_feedback import (
    IndividualFeedbackConfig,
    IndividualFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> IndividualFeedbackGenerator:
    return IndividualFeedbackGenerator()


@pytest.fixture
def good_player() -> PlayerStats:
    """높은 효율의 선수 (더블더블 달성)."""
    return PlayerStats(
        player_tracking_id=7,
        points=28,
        field_goals_made=10,
        field_goals_attempted=18,
        field_goal_percentage=55.6,
        three_pointers_made=4,
        three_pointers_attempted=8,
        three_point_percentage=50.0,
        free_throws_made=4,
        free_throws_attempted=5,
        free_throw_percentage=80.0,
        offensive_rebounds=3,
        defensive_rebounds=8,
        total_rebounds=11,
        assists=6,
        turnovers=2,
        steals=2,
        blocks=1,
        personal_fouls=2,
        plus_minus=12,
    )


@pytest.fixture
def weak_player() -> PlayerStats:
    """낮은 효율의 선수."""
    return PlayerStats(
        player_tracking_id=15,
        points=4,
        field_goals_made=2,
        field_goals_attempted=10,
        field_goal_percentage=20.0,
        three_pointers_made=0,
        three_pointers_attempted=4,
        three_point_percentage=0.0,
        free_throws_made=0,
        free_throws_attempted=2,
        free_throw_percentage=0.0,
        offensive_rebounds=0,
        defensive_rebounds=1,
        total_rebounds=1,
        assists=1,
        turnovers=4,
        steals=0,
        blocks=0,
        personal_fouls=4,
        plus_minus=-15,
    )


@pytest.fixture
def no_three_player() -> PlayerStats:
    """3점슛 시도 없는 선수."""
    return PlayerStats(
        player_tracking_id=20,
        points=12,
        field_goals_made=6,
        field_goals_attempted=10,
        field_goal_percentage=60.0,
        three_pointers_made=0,
        three_pointers_attempted=0,
        three_point_percentage=0.0,
        free_throws_made=0,
        free_throws_attempted=0,
        free_throw_percentage=0.0,
        offensive_rebounds=2,
        defensive_rebounds=4,
        total_rebounds=6,
        assists=2,
        turnovers=1,
        steals=1,
        blocks=2,
        personal_fouls=2,
        plus_minus=3,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestIndividualFeedbackGenerator:

    def test_name(self, gen: IndividualFeedbackGenerator) -> None:
        assert gen.name == "IndividualFeedbackGenerator"

    def test_generates_minimum_items(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert len(items) >= 15

    def test_all_items_are_feedback_items(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert all(isinstance(i, FeedbackItem) for i in items)

    def test_game_score_positive(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        """높은 게임스코어 → POSITIVE."""
        items = gen.generate(good_player)
        gs_items = [i for i in items if "종합 효율" in i.title]
        assert len(gs_items) == 1
        assert gs_items[0].feedback_type == FeedbackType.POSITIVE

    def test_game_score_correction(
        self, gen: IndividualFeedbackGenerator, weak_player: PlayerStats,
    ) -> None:
        """낮은 게임스코어 → CORRECTION."""
        items = gen.generate(weak_player)
        gs_items = [i for i in items if "종합 효율" in i.title]
        assert len(gs_items) == 1
        assert gs_items[0].feedback_type == FeedbackType.CORRECTION

    def test_ts_pct_feedback(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("트루 슈팅" in i.title for i in items)

    def test_three_pt_feedback(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("3점슛" in i.title for i in items)

    def test_no_three_pt_when_zero_attempts(
        self, gen: IndividualFeedbackGenerator, no_three_player: PlayerStats,
    ) -> None:
        items = gen.generate(no_three_player)
        assert not any("3점슛" in i.title for i in items)

    def test_free_throw_feedback(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("자유투" in i.title for i in items)

    def test_efficiency_index(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("효율성 지수" in i.title for i in items)

    def test_double_double_detection(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        """28점 11리바운드 → 더블더블."""
        items = gen.generate(good_player)
        dd_items = [i for i in items if "더블" in i.title]
        assert len(dd_items) == 1
        assert dd_items[0].feedback_type == FeedbackType.POSITIVE

    def test_scoring_breakdown(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("득점 구성" in i.title for i in items)

    def test_turnover_burden(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("턴오버 부담" in i.title for i in items)

    def test_offensive_rebound(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        items = gen.generate(good_player)
        assert any("공격 리바운드" in i.title for i in items)

    def test_total_generated(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        gen.generate(good_player)
        assert gen.total_generated == 1
        gen.generate(good_player)
        assert gen.total_generated == 2

    def test_reset(
        self, gen: IndividualFeedbackGenerator, good_player: PlayerStats,
    ) -> None:
        gen.generate(good_player)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: IndividualFeedbackGenerator) -> None:
        assert "IndividualFeedbackGenerator" in repr(gen)
