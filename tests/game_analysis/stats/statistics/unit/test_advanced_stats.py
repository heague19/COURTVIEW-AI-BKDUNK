# -*- coding: utf-8 -*-
"""AdvancedStatsCalculator 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.advanced_stats import (
    AdvancedStatsCalculator,
    AdvancedStatsConfig,
    AdvancedPlayerStats,
    TeamContext,
)
from shared.dto.game_dto import PlayerStats


# =============================================================================
# 헬퍼
# =============================================================================
def _make_player_stats(**overrides) -> PlayerStats:
    defaults = dict(
        player_tracking_id=7,
        team_id="home",
        points=20,
        field_goals_made=8,
        field_goals_attempted=16,
        three_pointers_made=2,
        three_pointers_attempted=5,
        free_throws_made=2,
        free_throws_attempted=3,
        offensive_rebounds=2,
        defensive_rebounds=5,
        total_rebounds=7,
        assists=5,
        turnovers=2,
        steals=1,
        blocks=1,
        personal_fouls=2,
    )
    defaults.update(overrides)
    return PlayerStats(**defaults)


def _make_team_context(**overrides) -> TeamContext:
    defaults = dict(
        team_id="home",
        total_minutes=240.0,
        field_goals_attempted=80,
        free_throws_attempted=20,
        turnovers=12,
        offensive_rebounds=10,
        total_possessions=95,
        points=100,
        opponent_points=90,
    )
    defaults.update(overrides)
    return TeamContext(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestAdvancedStatsCalculator:
    """AdvancedStatsCalculator 단위 테스트."""

    def test_init_default(self):
        calc = AdvancedStatsCalculator()
        assert calc.name == "AdvancedStatsCalculator"

    def test_ts_pct(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats(points=20, field_goals_attempted=16, free_throws_attempted=3)
        result = calc.calculate(ps, minutes=30.0)
        # TS% = 20 / (2 * (16 + 0.44 * 3)) ≈ 0.580
        assert 0.50 < result.ts_pct < 0.70

    def test_efg_pct(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats(
            field_goals_made=8, three_pointers_made=2, field_goals_attempted=16,
        )
        result = calc.calculate(ps)
        # eFG% = (8 + 0.5 * 2) / 16 = 0.5625
        assert abs(result.efg_pct - 0.5625) < 0.01

    def test_usg_pct_with_team_context(self):
        calc = AdvancedStatsCalculator()
        ctx = _make_team_context()
        calc.set_team_context("home", ctx)
        ps = _make_player_stats()
        result = calc.calculate(ps, minutes=32.0)
        assert result.usg_pct > 0.0

    def test_usg_pct_zero_without_context(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats()
        result = calc.calculate(ps, minutes=32.0)
        assert result.usg_pct == 0.0

    def test_game_score(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats()
        result = calc.calculate(ps)
        # GmSc = 20 + 0.4*8 - 0.7*16 - 0.4*(3-2) + 0.7*2 + 0.3*5 + 1 + 0.7*5 + 0.7*1 - 0.4*2 - 2
        assert result.game_score != 0.0

    def test_per_with_team_context(self):
        calc = AdvancedStatsCalculator()
        ctx = _make_team_context()
        calc.set_team_context("home", ctx)
        ps = _make_player_stats()
        result = calc.calculate(ps, minutes=32.0)
        assert result.per != 0.0

    def test_ortg_drtg(self):
        calc = AdvancedStatsCalculator()
        home_ctx = _make_team_context(team_id="home", points=100, total_possessions=95)
        away_ctx = _make_team_context(team_id="away", points=90, total_possessions=95)
        calc.set_team_context("home", home_ctx)
        calc.set_team_context("away", away_ctx)
        ps = _make_player_stats()
        result = calc.calculate(ps, minutes=32.0, opponent_team_id="away")
        # ORtg ≈ 100/95 * 100 ≈ 105.3
        assert result.offensive_rating > 100.0
        assert result.defensive_rating > 0.0
        assert result.net_rating > 0.0

    def test_per_36_normalization(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats(points=20, total_rebounds=7, assists=5)
        result = calc.calculate(ps, minutes=32.0)
        # per-36 points = 20 * 36/32 = 22.5
        assert result.points_per_36 == 22.5
        assert result.rebounds_per_36 > 0
        assert result.assists_per_36 > 0

    def test_ast_to_ratio(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats(assists=5, turnovers=2)
        result = calc.calculate(ps)
        assert result.ast_to_ratio == 2.50

    def test_ast_to_ratio_zero_turnovers(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats(assists=5, turnovers=0)
        result = calc.calculate(ps)
        assert result.ast_to_ratio == 5.0

    def test_cached_result(self):
        calc = AdvancedStatsCalculator()
        ps = _make_player_stats()
        calc.calculate(ps, minutes=30.0)
        cached = calc.get_cached(7)
        assert cached is not None
        assert cached.player_tracking_id == 7

    def test_calculate_all(self):
        calc = AdvancedStatsCalculator()
        players = [_make_player_stats(player_tracking_id=i) for i in range(5)]
        results = calc.calculate_all(players, {i: 30.0 for i in range(5)})
        assert len(results) == 5

    def test_reset(self):
        calc = AdvancedStatsCalculator()
        ctx = _make_team_context()
        calc.set_team_context("home", ctx)
        calc.calculate(_make_player_stats(), minutes=30.0)
        calc.reset()
        assert calc.get_cached(7) is None
