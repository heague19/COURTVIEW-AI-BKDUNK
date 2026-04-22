# -*- coding: utf-8 -*-
"""feedback_system/analysis/position_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.position_feedback import (
    PositionFeedbackConfig,
    PositionFeedbackGenerator,
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
        offensive_rebounds=kw.pop("orb", 1),
        defensive_rebounds=kw.pop("drb", 3),
        total_rebounds=kw.pop("reb", 4),
        assists=kw.pop("ast", 3),
        turnovers=kw.pop("tov", 2),
        steals=kw.pop("stl", 1),
        blocks=kw.pop("blk", 0),
        personal_fouls=2,
        plus_minus=5,
        **kw,
    )


@pytest.fixture
def gen() -> PositionFeedbackGenerator:
    return PositionFeedbackGenerator()


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=92,
        quarter_scores=[24, 22, 24, 22],
        field_goals_made=34,
        field_goals_attempted=72,
        field_goal_percentage=47.2,
        three_pointers_made=10,
        three_pointers_attempted=26,
        three_point_percentage=38.5,
        free_throws_made=14,
        free_throws_attempted=18,
        free_throw_percentage=77.8,
        offensive_rebounds=8,
        defensive_rebounds=24,
        total_rebounds=32,
        assists=22,
        turnovers=11,
        steals=7,
        blocks=4,
        personal_fouls=16,
        points_in_paint=34,
        second_chance_points=10,
        fast_break_points=12,
        bench_points=24,
        player_stats=[
            # 가드형 (어시스트 높음, 리바운드 낮음)
            _make_player(1, 22, ast=8, tpm=4, tpa=9, reb=3, drb=2, orb=1, stl=2),
            # 가드형
            _make_player(2, 18, ast=5, tpm=3, tpa=7, reb=2, drb=2, orb=0, stl=2),
            # 포워드형
            _make_player(3, 16, ast=3, reb=7, drb=5, orb=2, blk=1),
            # 센터형 (리바운드 높음, 어시스트 낮음)
            _make_player(4, 14, ast=1, reb=12, drb=8, orb=4, blk=3, tpm=0, tpa=1),
            # 벤치
            _make_player(5, 8, ast=2, reb=4, stl=1),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=86,
        quarter_scores=[20, 22, 22, 22],
        field_goals_made=32,
        field_goals_attempted=74,
        field_goal_percentage=43.2,
        three_pointers_made=8,
        three_pointers_attempted=24,
        three_point_percentage=33.3,
        free_throws_made=14,
        free_throws_attempted=20,
        free_throw_percentage=70.0,
        offensive_rebounds=7,
        defensive_rebounds=22,
        total_rebounds=29,
        assists=18,
        turnovers=13,
        steals=5,
        blocks=3,
        personal_fouls=18,
        points_in_paint=30,
        second_chance_points=8,
        fast_break_points=8,
        bench_points=20,
        player_stats=[
            _make_player(10, 22, ast=6, reb=4),
            _make_player(11, 16, ast=2, reb=8, blk=2),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=92,
        away_score=86,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=7,
        ties=3,
        largest_lead_home=10,
        largest_lead_away=4,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPositionFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = PositionFeedbackConfig()
        assert hasattr(cfg, "guard_ast_threshold")

    def test_custom(self) -> None:
        cfg = PositionFeedbackConfig(guard_ast_threshold=6.0)
        assert cfg.guard_ast_threshold == 6.0


class TestPositionFeedbackGenerator:
    def test_name(self, gen: PositionFeedbackGenerator) -> None:
        assert gen.name == "PositionFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: PositionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 10
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_position_evaluation(
        self,
        gen: PositionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        # 가드/포워드/센터 중 하나는 언급
        assert any(
            "가드" in t or "포워드" in t or "센터" in t or "포지션" in t
            for t in titles
        )

    def test_team_position_balance(
        self,
        gen: PositionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("균형" in t or "밸런스" in t or "팀" in t for t in titles)

    def test_total_generated(
        self,
        gen: PositionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: PositionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: PositionFeedbackGenerator) -> None:
        assert "PositionFeedbackGenerator" in repr(gen)
