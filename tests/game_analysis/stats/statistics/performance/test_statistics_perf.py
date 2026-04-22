# -*- coding: utf-8 -*-
"""Statistics 모듈 성능 테스트 — 10 tests.

Cadence 준수 확인:
  EVENT (<10ms): BasicStats, ShotChart, TeamStats, PossessionStats
  LAZY (<10ms): AdvancedStats, FourFactors
  FRAME (<2ms): PlayerTrackerStats
"""
from __future__ import annotations

import time

import pytest

from game_analysis.stats.statistics.basic_stats import BasicStatsCalculator
from game_analysis.stats.statistics.advanced_stats import (
    AdvancedStatsCalculator, TeamContext,
)
from game_analysis.stats.statistics.shot_chart import ShotChartCalculator
from game_analysis.stats.statistics.player_tracker_stats import (
    PlayerTrackerStatsCalculator, PlayerPositionInput,
)
from game_analysis.stats.statistics.team_stats_aggregator import TeamStatsAggregator
from game_analysis.stats.statistics.possession_stats import (
    PossessionStatsCalculator, PossessionResult,
)
from game_analysis.stats.statistics.four_factors import (
    FourFactorsCalculator, FourFactorsInput,
)
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent, PlayerStats

_EVENT_BUDGET_MS = 10.0
_FRAME_BUDGET_MS = 2.0
_ITERATIONS = 500


def _make_event(et: GameEventType, pid: int = 7, pts: int = 0) -> GameEvent:
    return GameEvent(
        event_type=et, primary_player_id=pid, team_id="home",
        frame_number=100, timestamp=3.33, points=pts, confidence=0.85,
    )


class TestStatisticsPerformance:
    """Statistics 모듈 성능 테스트."""

    def test_basic_stats_event_cadence(self):
        calc = BasicStatsCalculator()
        event = _make_event(GameEventType.SHOT_MADE, pts=2)
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            calc.process_event(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"BasicStats avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_shot_chart_event_cadence(self):
        calc = ShotChartCalculator()
        t0 = time.perf_counter()
        for i in range(_ITERATIONS):
            calc.process_shot(7, "home", 0.1 * (i % 10), 0.1, 5.0, i % 2 == 0, 2)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"ShotChart avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_team_stats_event_cadence(self):
        agg = TeamStatsAggregator()
        event = _make_event(GameEventType.SHOT_MADE, pts=2)
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            agg.process_event(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"TeamStats avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_possession_stats_event_cadence(self):
        calc = PossessionStatsCalculator()
        poss = PossessionResult(
            team_id="home", quarter=1, points_scored=2,
            duration_sec=12.0, end_reason="shot",
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            calc.process_possession(poss)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"PossessionStats avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_player_tracker_frame_cadence(self):
        calc = PlayerTrackerStatsCalculator()
        inp = PlayerPositionInput(
            player_tracking_id=7, team_id="home",
            court_x_m=5.0, court_y_m=3.0, speed_ms=4.0,
        )
        t0 = time.perf_counter()
        for i in range(_ITERATIONS):
            inp.frame_index = i
            inp.court_x_m = 5.0 + i * 0.01
            calc.process_position(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _FRAME_BUDGET_MS, f"PlayerTracker avg={avg_ms:.3f}ms > {_FRAME_BUDGET_MS}ms"

    def test_advanced_stats_calculation_cadence(self):
        calc = AdvancedStatsCalculator()
        ctx = TeamContext(
            team_id="home", total_minutes=240.0,
            field_goals_attempted=80, free_throws_attempted=20,
            turnovers=12, total_possessions=95, points=100,
        )
        calc.set_team_context("home", ctx)
        ps = PlayerStats(
            player_tracking_id=7, team_id="home",
            points=20, field_goals_made=8, field_goals_attempted=16,
            three_pointers_made=2, three_pointers_attempted=5,
            free_throws_made=2, free_throws_attempted=3,
            offensive_rebounds=2, defensive_rebounds=5, total_rebounds=7,
            assists=5, turnovers=2, steals=1, blocks=1, personal_fouls=2,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            calc.calculate(ps, minutes=32.0)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"AdvancedStats avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_four_factors_calculation_cadence(self):
        calc = FourFactorsCalculator()
        inp = FourFactorsInput(
            team_id="home", field_goals_made=35,
            field_goals_attempted=80, three_pointers_made=10,
            turnovers=12, offensive_rebounds=10,
            opponent_defensive_rebounds=30, free_throws_attempted=20,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            calc.calculate(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"FourFactors avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    # === 메모리 가드 ===

    def test_basic_stats_memory_guard(self):
        calc = BasicStatsCalculator()
        for i in range(600):
            calc.process_event(_make_event(GameEventType.SHOT_MADE, pts=2))
        assert len(calc.get_event_history()) <= 500

    def test_shot_chart_memory_guard(self):
        calc = ShotChartCalculator()
        for i in range(2200):
            calc.process_shot(7, "home", 0.0, 0.0, 1.0, True, 2)
        assert len(calc.get_event_history()) <= 2000

    def test_possession_stats_memory_guard(self):
        calc = PossessionStatsCalculator()
        for i in range(600):
            calc.process_possession(PossessionResult(
                team_id="home", quarter=1, points_scored=1,
                duration_sec=10.0, end_reason="shot",
            ))
        assert len(calc.get_event_history()) <= 500
