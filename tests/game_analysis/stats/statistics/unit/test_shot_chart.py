# -*- coding: utf-8 -*-
"""ShotChartCalculator 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.shot_chart import (
    ShotChartCalculator,
    ShotChartConfig,
    ZoneAccumulator,
)
from shared.constants.stats_constants import ShotZone
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent


# =============================================================================
# 테스트
# =============================================================================
class TestShotChartCalculator:
    """ShotChartCalculator 단위 테스트."""

    def test_init_default(self):
        calc = ShotChartCalculator()
        assert calc.name == "ShotChartCalculator"
        assert calc.total_shots == 0

    def test_classify_restricted_area(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.0, 0.0, 1.0)
        assert zone == ShotZone.RESTRICTED_AREA

    def test_classify_paint_non_ra(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.0, 0.0, 3.0)
        assert zone == ShotZone.PAINT_NON_RA

    def test_classify_mid_range_center(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.0, 0.0, 5.0)
        assert zone == ShotZone.MID_RANGE_CENTER

    def test_classify_mid_range_left(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(-0.5, 0.0, 5.0)
        assert zone == ShotZone.MID_RANGE_LEFT

    def test_classify_mid_range_right(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.5, 0.0, 5.0)
        assert zone == ShotZone.MID_RANGE_RIGHT

    def test_classify_corner_three_left(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(-0.5, -0.9, 7.0)
        assert zone == ShotZone.CORNER_THREE_LEFT

    def test_classify_corner_three_right(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.5, 0.9, 7.0)
        assert zone == ShotZone.CORNER_THREE_RIGHT

    def test_classify_above_break_center(self):
        calc = ShotChartCalculator()
        zone = calc.classify_zone(0.0, 0.0, 7.5)
        assert zone == ShotZone.ABOVE_BREAK_CENTER

    def test_process_shot_made(self):
        calc = ShotChartCalculator()
        result = calc.process_shot(
            player_id=7, team_id="home",
            court_x=0.0, court_y=0.0, distance_m=1.0,
            made=True, points=2,
        )
        assert result is True
        assert calc.total_shots == 1
        stats = calc.get_player_zone_stats(7)
        assert len(stats) == 1
        assert stats[0]["made"] == 1

    def test_hot_cold_zones(self):
        calc = ShotChartCalculator()
        # 핫존: 5/5 = 100%
        for _ in range(5):
            calc.process_shot(7, "home", 0.0, 0.0, 1.0, True, 2)
        # 콜드존: 0/5 = 0%
        for _ in range(5):
            calc.process_shot(7, "home", 0.0, 0.0, 5.0, False, 0)

        hot = calc.get_hot_zones(player_id=7)
        cold = calc.get_cold_zones(player_id=7)
        assert ShotZone.RESTRICTED_AREA.value in hot
        assert ShotZone.MID_RANGE_CENTER.value in cold

    def test_player_summary(self):
        calc = ShotChartCalculator()
        calc.process_shot(7, "home", 0.0, 0.0, 1.0, True, 2)
        calc.process_shot(7, "home", 0.0, 0.0, 1.0, False, 0)
        summary = calc.get_player_summary(7)
        assert summary["total_attempts"] == 2
        assert summary["total_made"] == 1
        assert summary["fg_pct"] == 50.0

    def test_reset(self):
        calc = ShotChartCalculator()
        calc.process_shot(7, "home", 0.0, 0.0, 1.0, True, 2)
        calc.reset()
        assert calc.total_shots == 0
        assert calc.get_player_zone_stats(7) == []
