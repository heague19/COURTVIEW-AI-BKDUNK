# -*- coding: utf-8 -*-
"""PossessionStatsCalculator 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.possession_stats import (
    PossessionStatsCalculator,
    PossessionStatsConfig,
    PossessionResult,
    PPPGrade,
    PossessionTiming,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_possession(
    team_id: str = "home",
    quarter: int = 1,
    points: int = 2,
    duration_sec: float = 12.0,
    end_reason: str = "shot",
    is_fast_break: bool = False,
) -> PossessionResult:
    return PossessionResult(
        team_id=team_id,
        quarter=quarter,
        points_scored=points,
        duration_sec=duration_sec,
        end_reason=end_reason,
        is_fast_break=is_fast_break,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPossessionStatsCalculator:
    """PossessionStatsCalculator 단위 테스트."""

    def test_init_default(self):
        calc = PossessionStatsCalculator()
        assert calc.name == "PossessionStatsCalculator"
        assert calc.total_possessions == 0

    def test_single_possession_ppp(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(points=2))
        assert calc.get_team_ppp("home") == 2.0

    def test_multiple_possessions_ppp(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(points=3))
        calc.process_possession(_make_possession(points=0))
        calc.process_possession(_make_possession(points=2))
        # PPP = 5/3 ≈ 1.667
        ppp = calc.get_team_ppp("home")
        assert abs(ppp - 1.667) < 0.01

    def test_ppp_grade_elite(self):
        calc = PossessionStatsCalculator()
        assert calc.get_ppp_grade(1.25) == PPPGrade.ELITE

    def test_ppp_grade_good(self):
        calc = PossessionStatsCalculator()
        assert calc.get_ppp_grade(1.15) == PPPGrade.GOOD

    def test_ppp_grade_average(self):
        calc = PossessionStatsCalculator()
        assert calc.get_ppp_grade(1.05) == PPPGrade.AVERAGE

    def test_ppp_grade_poor(self):
        calc = PossessionStatsCalculator()
        assert calc.get_ppp_grade(0.95) == PPPGrade.POOR

    def test_ppp_grade_very_poor(self):
        calc = PossessionStatsCalculator()
        assert calc.get_ppp_grade(0.80) == PPPGrade.VERY_POOR

    def test_fast_break_timing(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(
            points=2, duration_sec=5.0, is_fast_break=True,
        ))
        summary = calc.get_team_possession_summary("home")
        assert summary["timing"]["fast_break"]["possessions"] == 1

    def test_early_mid_late_clock(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(duration_sec=5.0, points=2))   # early
        calc.process_possession(_make_possession(duration_sec=12.0, points=3))  # mid
        calc.process_possession(_make_possession(duration_sec=20.0, points=0))  # late
        summary = calc.get_team_possession_summary("home")
        assert summary["timing"]["early_clock"]["possessions"] == 1
        assert summary["timing"]["mid_clock"]["possessions"] == 1
        assert summary["timing"]["late_clock"]["possessions"] == 1

    def test_turnover_rate(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(points=2, end_reason="shot"))
        calc.process_possession(_make_possession(points=0, end_reason="turnover"))
        summary = calc.get_team_possession_summary("home")
        assert summary["turnover_rate"] == 50.0

    def test_quarter_ppp(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(quarter=1, points=3))
        calc.process_possession(_make_possession(quarter=2, points=0))
        summary = calc.get_team_possession_summary("home")
        assert summary["quarter_ppp"][0] == 3.0
        assert summary["quarter_ppp"][1] == 0.0

    def test_statistical_significance(self):
        calc = PossessionStatsCalculator()
        # 25 미만 → 유의하지 않음
        for _ in range(20):
            calc.process_possession(_make_possession(points=1))
        assert not calc.is_statistically_significant("home")
        for _ in range(10):
            calc.process_possession(_make_possession(points=1))
        assert calc.is_statistically_significant("home")

    def test_reset(self):
        calc = PossessionStatsCalculator()
        calc.process_possession(_make_possession(points=2))
        calc.reset()
        assert calc.total_possessions == 0
        assert calc.get_team_ppp("home") == 0.0
