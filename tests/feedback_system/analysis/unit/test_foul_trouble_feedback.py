# -*- coding: utf-8 -*-
"""feedback_system/analysis/foul_trouble_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.foul_trouble_feedback import (
    FoulTroubleFeedbackConfig,
    FoulTroubleFeedbackGenerator,
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
        three_pointers_attempted=kw.pop("tpa", 4),
        three_point_percentage=25.0,
        free_throws_made=kw.pop("ftm", 3),
        free_throws_attempted=kw.pop("fta", 4),
        free_throw_percentage=75.0,
        offensive_rebounds=1,
        defensive_rebounds=3,
        total_rebounds=4,
        assists=2,
        turnovers=2,
        steals=1,
        blocks=0,
        personal_fouls=kw.pop("pf", 2),
        plus_minus=kw.pop("pm", 3),
        **kw,
    )


@pytest.fixture
def gen() -> FoulTroubleFeedbackGenerator:
    return FoulTroubleFeedbackGenerator()


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=88,
        quarter_scores=[22, 24, 20, 22],
        field_goals_made=33,
        field_goals_attempted=74,
        field_goal_percentage=44.6,
        three_pointers_made=9,
        three_pointers_attempted=26,
        three_point_percentage=34.6,
        free_throws_made=13,
        free_throws_attempted=18,
        free_throw_percentage=72.2,
        offensive_rebounds=7,
        defensive_rebounds=22,
        total_rebounds=29,
        assists=19,
        turnovers=11,
        steals=6,
        blocks=3,
        personal_fouls=22,
        points_in_paint=32,
        second_chance_points=10,
        fast_break_points=10,
        bench_points=20,
        player_stats=[
            # 스타 선수가 파울 4개 (파울 트러블)
            _make_player(1, 25, pf=4, pm=8),
            _make_player(2, 18, pf=3, pm=5),
            _make_player(3, 14, pf=5, pm=-2),  # 파울 아웃 직전
            _make_player(4, 12, pf=1, pm=4),
            _make_player(5, 8, pf=2, pm=1),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=82,
        quarter_scores=[18, 22, 20, 22],
        field_goals_made=30,
        field_goals_attempted=72,
        field_goal_percentage=41.7,
        three_pointers_made=6,
        three_pointers_attempted=22,
        three_point_percentage=27.3,
        free_throws_made=16,
        free_throws_attempted=22,
        free_throw_percentage=72.7,
        offensive_rebounds=6,
        defensive_rebounds=20,
        total_rebounds=26,
        assists=16,
        turnovers=13,
        steals=5,
        blocks=2,
        personal_fouls=18,
        points_in_paint=28,
        second_chance_points=8,
        fast_break_points=6,
        bench_points=16,
        player_stats=[
            _make_player(10, 20, pf=2),
            _make_player(11, 14, pf=3),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=88,
        away_score=82,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=5,
        ties=3,
        largest_lead_home=8,
        largest_lead_away=3,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestFoulTroubleFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = FoulTroubleFeedbackConfig()
        assert cfg.foul_limit == 5
        assert cfg.foul_danger_zone == 4
        assert cfg.foul_trouble_zone == 3
        assert cfg.team_foul_bonus == 5

    def test_custom(self) -> None:
        cfg = FoulTroubleFeedbackConfig(foul_limit=6)
        assert cfg.foul_limit == 6


class TestFoulTroubleFeedbackGenerator:
    def test_name(self, gen: FoulTroubleFeedbackGenerator) -> None:
        assert gen.name == "FoulTroubleFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 10
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_team_foul_feedback(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("팀 파울" in t for t in titles)

    def test_player_foul_feedback(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        """파울 많은 선수에 대한 피드백 생성 확인."""
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        # 파울 4~5개 선수에 대한 피드백
        assert any("파울" in t and ("트러블" in t or "위험" in t or "주의" in t or "누적" in t) for t in titles)

    def test_foul_penalty_impact(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        """파울로 인한 추정 실점 피드백."""
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("실점" in t or "보너스" in t for t in titles)

    def test_star_player_foul_alert(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        """핵심 선수 파울 트러블 경고."""
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("핵심" in t or "파울아웃" in t for t in titles)

    def test_total_generated(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: FoulTroubleFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: FoulTroubleFeedbackGenerator) -> None:
        assert "FoulTroubleFeedbackGenerator" in repr(gen)
