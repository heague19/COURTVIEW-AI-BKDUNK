# -*- coding: utf-8 -*-
"""feedback_system/analysis/play_by_play_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.play_by_play_feedback import (
    PlayByPlayFeedbackConfig,
    PlayByPlayFeedbackGenerator,
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
        free_throws_made=3,
        free_throws_attempted=4,
        free_throw_percentage=75.0,
        offensive_rebounds=1,
        defensive_rebounds=3,
        total_rebounds=4,
        assists=3,
        turnovers=2,
        steals=1,
        blocks=0,
        personal_fouls=2,
        plus_minus=5,
        **kw,
    )


@pytest.fixture
def gen() -> PlayByPlayFeedbackGenerator:
    return PlayByPlayFeedbackGenerator()


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=95,
        quarter_scores=[30, 18, 25, 22],  # 1쿼터 폭발, 2쿼터 침체
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
            _make_player(1, 28, fgm=10, fga=18),
            _make_player(2, 20, fgm=8, fga=15),
            _make_player(3, 15, fgm=5, fga=12),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=90,
        quarter_scores=[20, 28, 22, 20],  # 2쿼터 반격
        field_goals_made=33,
        field_goals_attempted=76,
        field_goal_percentage=43.4,
        three_pointers_made=9,
        three_pointers_attempted=26,
        three_point_percentage=34.6,
        free_throws_made=15,
        free_throws_attempted=20,
        free_throw_percentage=75.0,
        offensive_rebounds=8,
        defensive_rebounds=22,
        total_rebounds=30,
        assists=18,
        turnovers=14,
        steals=5,
        blocks=3,
        personal_fouls=19,
        points_in_paint=30,
        second_chance_points=10,
        fast_break_points=10,
        bench_points=22,
        player_stats=[
            _make_player(10, 22, fgm=8, fga=17),
            _make_player(11, 18, fgm=7, fga=15),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=95,
        away_score=90,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=10,
        ties=5,
        largest_lead_home=14,
        largest_lead_away=6,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPlayByPlayFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = PlayByPlayFeedbackConfig()
        assert cfg.scoring_run_threshold >= 6
        assert cfg.consecutive_to_warning >= 2

    def test_custom(self) -> None:
        cfg = PlayByPlayFeedbackConfig(scoring_run_threshold=10)
        assert cfg.scoring_run_threshold == 10


class TestPlayByPlayFeedbackGenerator:
    def test_name(self, gen: PlayByPlayFeedbackGenerator) -> None:
        assert gen.name == "PlayByPlayFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 5
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_possession_analysis(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("포제션" in t for t in titles)

    def test_lead_change_analysis(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("리드" in t for t in titles)

    def test_scoring_route_analysis(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("득점" in t for t in titles)

    def test_total_generated(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: PlayByPlayFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: PlayByPlayFeedbackGenerator) -> None:
        assert "PlayByPlayFeedbackGenerator" in repr(gen)
