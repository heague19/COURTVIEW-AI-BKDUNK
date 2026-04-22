# -*- coding: utf-8 -*-
"""FourFactorsCalculator 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.four_factors import (
    FourFactorsCalculator,
    FourFactorsConfig,
    FourFactorsInput,
    FourFactorsResult,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(
    team_id: str = "home",
    fgm: int = 35,
    fga: int = 80,
    three_pm: int = 10,
    tov: int = 12,
    oreb: int = 10,
    opp_dreb: int = 30,
    fta: int = 20,
) -> FourFactorsInput:
    return FourFactorsInput(
        team_id=team_id,
        field_goals_made=fgm,
        field_goals_attempted=fga,
        three_pointers_made=three_pm,
        turnovers=tov,
        offensive_rebounds=oreb,
        opponent_defensive_rebounds=opp_dreb,
        free_throws_attempted=fta,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestFourFactorsCalculator:
    """FourFactorsCalculator 단위 테스트."""

    def test_init_default(self):
        calc = FourFactorsCalculator()
        assert calc.name == "FourFactorsCalculator"

    def test_efg_pct(self):
        calc = FourFactorsCalculator()
        # eFG% = (35 + 0.5*10) / 80 = 40/80 = 0.5
        result = calc.calculate(_make_input(fgm=35, fga=80, three_pm=10))
        assert abs(result.efg_pct - 0.5) < 0.001

    def test_tov_pct(self):
        calc = FourFactorsCalculator()
        # TOV% = 12 / (80 + 0.44*20 + 12) = 12 / 100.8 ≈ 0.119
        result = calc.calculate(_make_input(tov=12, fga=80, fta=20))
        assert 0.10 < result.tov_pct < 0.15

    def test_oreb_pct(self):
        calc = FourFactorsCalculator()
        # OREB% = 10 / (10 + 30) = 0.25
        result = calc.calculate(_make_input(oreb=10, opp_dreb=30))
        assert abs(result.oreb_pct - 0.25) < 0.001

    def test_ft_rate(self):
        calc = FourFactorsCalculator()
        # FT Rate = 20 / 80 = 0.25
        result = calc.calculate(_make_input(fta=20, fga=80))
        assert abs(result.ft_rate - 0.25) < 0.001

    def test_composite_score(self):
        calc = FourFactorsCalculator()
        result = calc.calculate(_make_input())
        # composite = 0.40*eFG + 0.25*(1-TOV%) + 0.20*OREB% + 0.15*min(FTrate,1)
        assert result.composite_score > 0.0

    def test_zero_fga(self):
        calc = FourFactorsCalculator()
        result = calc.calculate(_make_input(fgm=0, fga=0, three_pm=0, fta=0))
        assert result.efg_pct == 0.0
        assert result.ft_rate == 0.0

    def test_compare_two_teams(self):
        calc = FourFactorsCalculator()
        home = _make_input(team_id="home", fgm=40, fga=80, three_pm=12, tov=10)
        away = _make_input(team_id="away", fgm=30, fga=80, three_pm=8, tov=15)
        ra, rb = calc.compare(home, away)
        # 홈팀이 eFG% 유리
        assert ra.efg_advantage > 0.0
        # 홈팀이 TOV% 유리 (상대가 턴오버 더 많으므로)
        assert ra.tov_advantage > 0.0
        assert ra.total_advantage > 0.0
        # 반대 팀은 불리
        assert rb.total_advantage < 0.0

    def test_advantages_symmetry(self):
        calc = FourFactorsCalculator()
        home = _make_input(team_id="home")
        away = _make_input(team_id="away")
        ra, rb = calc.compare(home, away)
        # 동일 입력 → 어드밴티지 0
        assert abs(ra.efg_advantage) < 0.001
        assert abs(ra.total_advantage) < 0.001

    def test_dominant_factor(self):
        calc = FourFactorsCalculator()
        home = _make_input(team_id="home", fgm=40, fga=80, three_pm=15)
        away = _make_input(team_id="away", fgm=30, fga=80, three_pm=5)
        ra, rb = calc.compare(home, away)
        # eFG 차이가 가장 클 것
        factor = calc.get_dominant_factor(ra)
        assert factor == "efg"

    def test_to_dict(self):
        calc = FourFactorsCalculator()
        result = calc.calculate(_make_input())
        d = result.to_dict()
        assert "efg_pct" in d
        assert "tov_pct" in d
        assert "composite_score" in d
        assert "advantages" in d

    def test_cached_result(self):
        calc = FourFactorsCalculator()
        calc.calculate(_make_input(team_id="home"))
        cached = calc.get_cached("home")
        assert cached is not None
        assert cached.team_id == "home"

    def test_reset(self):
        calc = FourFactorsCalculator()
        calc.calculate(_make_input())
        calc.reset()
        assert calc.get_cached("home") is None
