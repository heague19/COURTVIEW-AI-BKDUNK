# -*- coding: utf-8 -*-
"""feedback_system/analysis/free_throw_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.free_throw_feedback import (
    FreeThrowFeedbackConfig,
    FreeThrowFeedbackGenerator,
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
        three_pointers_made=kw.pop("tpm", 1),
        three_pointers_attempted=kw.pop("tpa", 3),
        three_point_percentage=33.3,
        free_throws_made=kw.pop("ftm", 5),
        free_throws_attempted=kw.pop("fta", 6),
        free_throw_percentage=kw.pop("ft_pct", 83.3),
        offensive_rebounds=1,
        defensive_rebounds=3,
        total_rebounds=4,
        assists=3,
        turnovers=2,
        steals=1,
        blocks=0,
        personal_fouls=kw.pop("pf", 2),
        plus_minus=5,
        **kw,
    )


@pytest.fixture
def gen() -> FreeThrowFeedbackGenerator:
    return FreeThrowFeedbackGenerator()


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=90,
        quarter_scores=[22, 25, 20, 23],
        field_goals_made=32,
        field_goals_attempted=72,
        field_goal_percentage=44.4,
        three_pointers_made=8,
        three_pointers_attempted=22,
        three_point_percentage=36.4,
        free_throws_made=18,
        free_throws_attempted=24,
        free_throw_percentage=75.0,
        offensive_rebounds=8,
        defensive_rebounds=22,
        total_rebounds=30,
        assists=20,
        turnovers=12,
        steals=6,
        blocks=3,
        personal_fouls=16,
        points_in_paint=34,
        second_chance_points=10,
        fast_break_points=12,
        bench_points=22,
        player_stats=[
            _make_player(1, 22, ftm=8, fta=9, ft_pct=88.9),
            _make_player(2, 18, ftm=4, fta=5, ft_pct=80.0),
            _make_player(3, 14, ftm=2, fta=6, ft_pct=33.3),
            _make_player(4, 12, ftm=3, fta=3, ft_pct=100.0),
            _make_player(5, 10, ftm=1, fta=1, ft_pct=100.0),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=85,
        quarter_scores=[20, 22, 21, 22],
        field_goals_made=30,
        field_goals_attempted=74,
        field_goal_percentage=40.5,
        three_pointers_made=7,
        three_pointers_attempted=24,
        three_point_percentage=29.2,
        free_throws_made=18,
        free_throws_attempted=26,
        free_throw_percentage=69.2,
        offensive_rebounds=7,
        defensive_rebounds=20,
        total_rebounds=27,
        assists=16,
        turnovers=14,
        steals=5,
        blocks=2,
        personal_fouls=22,
        points_in_paint=30,
        second_chance_points=8,
        fast_break_points=8,
        bench_points=18,
        player_stats=[
            _make_player(10, 20, ftm=6, fta=10, ft_pct=60.0),
            _make_player(11, 16, ftm=5, fta=7, ft_pct=71.4),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=90,
        away_score=85,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=6,
        ties=3,
        largest_lead_home=10,
        largest_lead_away=4,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestFreeThrowFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = FreeThrowFeedbackConfig()
        assert cfg.ft_pct_elite >= 80.0
        assert cfg.ft_pct_good >= 70.0
        assert cfg.ft_pct_poor <= 60.0

    def test_custom(self) -> None:
        cfg = FreeThrowFeedbackConfig(ft_pct_elite=85.0)
        assert cfg.ft_pct_elite == 85.0


class TestFreeThrowFeedbackGenerator:
    def test_name(self, gen: FreeThrowFeedbackGenerator) -> None:
        assert gen.name == "FreeThrowFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 10
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_team_ft_feedback(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("자유투" in t for t in titles)

    def test_player_ft_feedback(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        # 자유투 성공률 낮은 선수 피드백
        assert any("자유투" in t and ("선수" in t or "P" in t) for t in titles)

    def test_ft_poor_player_feedback(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        """자유투 부진 선수 피드백 생성 확인."""
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("부진" in t or "개선" in t for t in titles)

    def test_total_generated(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: FreeThrowFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: FreeThrowFeedbackGenerator) -> None:
        assert "FreeThrowFeedbackGenerator" in repr(gen)
