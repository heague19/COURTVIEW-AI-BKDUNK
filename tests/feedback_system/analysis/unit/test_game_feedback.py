# -*- coding: utf-8 -*-
"""
feedback_system/analysis/game_feedback.py 단위 테스트.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.game_feedback import (
    GameFeedbackConfig,
    GameFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
def _make_player(tid: int, pts: int, **kw) -> PlayerStats:
    fgm = kw.pop("fgm", pts // 3)
    fga = kw.pop("fga", fgm + 5)
    return PlayerStats(
        player_tracking_id=tid,
        points=pts,
        field_goals_made=fgm,
        field_goals_attempted=fga,
        field_goal_percentage=round(fgm / fga * 100, 1) if fga else 0.0,
        three_pointers_made=kw.pop("tpm", 2),
        three_pointers_attempted=kw.pop("tpa", 5),
        three_point_percentage=40.0,
        free_throws_made=kw.pop("ftm", 3),
        free_throws_attempted=kw.pop("fta", 4),
        free_throw_percentage=75.0,
        offensive_rebounds=kw.pop("orb", 1),
        defensive_rebounds=kw.pop("drb", 3),
        total_rebounds=kw.pop("reb", 4),
        assists=kw.pop("ast", 3),
        turnovers=kw.pop("tov", 2),
        steals=kw.pop("stl", 1),
        blocks=kw.pop("blk", 0),
        personal_fouls=kw.pop("pf", 2),
        plus_minus=kw.pop("pm", 5),
        **kw,
    )


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=95,
        quarter_scores=[22, 28, 20, 25],
        field_goals_made=35,
        field_goals_attempted=75,
        field_goal_percentage=46.7,
        three_pointers_made=10,
        three_pointers_attempted=28,
        three_point_percentage=35.7,
        free_throws_made=15,
        free_throws_attempted=20,
        free_throw_percentage=75.0,
        offensive_rebounds=10,
        defensive_rebounds=25,
        total_rebounds=35,
        assists=22,
        turnovers=12,
        steals=7,
        blocks=4,
        personal_fouls=18,
        points_in_paint=36,
        second_chance_points=12,
        fast_break_points=14,
        bench_points=28,
        player_stats=[
            _make_player(1, 25, fgm=9, fga=18, ast=7, reb=8),
            _make_player(2, 18, fgm=7, fga=14, ast=3),
            _make_player(3, 15, fgm=5, fga=12, tpm=3, tpa=7),
            _make_player(4, 12, fgm=4, fga=10, reb=9, drb=7),
            _make_player(5, 10, fgm=3, fga=8, stl=3, blk=2),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=88,
        quarter_scores=[20, 24, 22, 22],
        field_goals_made=32,
        field_goals_attempted=78,
        field_goal_percentage=41.0,
        three_pointers_made=8,
        three_pointers_attempted=25,
        three_point_percentage=32.0,
        free_throws_made=16,
        free_throws_attempted=22,
        free_throw_percentage=72.7,
        offensive_rebounds=8,
        defensive_rebounds=22,
        total_rebounds=30,
        assists=18,
        turnovers=15,
        steals=5,
        blocks=3,
        personal_fouls=20,
        points_in_paint=30,
        second_chance_points=8,
        fast_break_points=8,
        bench_points=20,
        player_stats=[
            _make_player(10, 22, fgm=8, fga=17),
            _make_player(11, 16, fgm=6, fga=15),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=95,
        away_score=88,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=8,
        ties=4,
        largest_lead_home=12,
        largest_lead_away=5,
    )


@pytest.fixture
def gen() -> GameFeedbackGenerator:
    return GameFeedbackGenerator()


# =============================================================================
# 테스트
# =============================================================================
class TestGameFeedbackGenerator:

    def test_name(self, gen: GameFeedbackGenerator) -> None:
        assert gen.name == "GameFeedbackGenerator"

    def test_generates_minimum_items(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 15

    def test_all_items_are_feedback_items(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert all(isinstance(i, FeedbackItem) for i in items)

    def test_game_result_win(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        """홈팀 승리 → POSITIVE."""
        items = gen.generate(game_stats, target_team_id="HOME")
        result = [i for i in items if i.title == "경기 결과"]
        assert len(result) == 1
        assert result[0].feedback_type == FeedbackType.POSITIVE

    def test_game_result_loss(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        """원정팀(패배) → CORRECTION."""
        items = gen.generate(game_stats, target_team_id="AWAY")
        result = [i for i in items if i.title == "경기 결과"]
        assert len(result) == 1
        assert result[0].feedback_type == FeedbackType.CORRECTION

    def test_shooting_feedback_exists(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = {i.title for i in items}
        assert "야투 성공률" in titles

    def test_four_factors_present(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = {i.title for i in items}
        assert "유효 야투율 (eFG%)" in titles
        assert "턴오버 비율" in titles

    def test_key_players_present(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        key_player_items = [i for i in items if "핵심 선수" in i.title]
        assert len(key_player_items) >= 2

    def test_rebound_feedback(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("리바운드" in i.title for i in items)

    def test_bench_contribution(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("벤치" in i.title for i in items)

    def test_second_chance(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("세컨드" in i.title for i in items)

    def test_quarter_momentum(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("쿼터" in i.title for i in items)

    def test_defensive_efficiency(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("수비" in i.title for i in items)

    def test_assist_distribution(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert any("어시스트 비율" in i.title for i in items)

    def test_no_target_returns_empty(self, gen: GameFeedbackGenerator) -> None:
        game = GameStats(task_id=uuid4())
        items = gen.generate(game)
        assert len(items) == 0

    def test_total_generated(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        assert gen.total_generated == 1
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self, gen: GameFeedbackGenerator, game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: GameFeedbackGenerator) -> None:
        assert "GameFeedbackGenerator" in repr(gen)
