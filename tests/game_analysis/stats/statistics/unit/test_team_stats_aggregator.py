# -*- coding: utf-8 -*-
"""TeamStatsAggregator 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.team_stats_aggregator import (
    TeamStatsAggregator,
    TeamStatsConfig,
)
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent


# =============================================================================
# 헬퍼
# =============================================================================
def _make_event(
    event_type: GameEventType,
    team_id: str = "home",
    player_id: int = 7,
    points: int = 0,
    description: str | None = None,
) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        primary_player_id=player_id,
        team_id=team_id,
        frame_number=100,
        timestamp=3.33,
        points=points,
        confidence=0.85,
        description=description,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestTeamStatsAggregator:
    """TeamStatsAggregator 단위 테스트."""

    def test_init_default(self):
        agg = TeamStatsAggregator()
        assert agg.name == "TeamStatsAggregator"
        assert agg.total_events == 0

    def test_shot_made_points(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.SHOT_MADE, points=2))
        summary = agg.get_team_summary("home")
        assert summary["total_points"] == 2
        assert "1/1" in summary["fg"]

    def test_three_pointer(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.SHOT_MADE, points=3))
        summary = agg.get_team_summary("home")
        assert summary["total_points"] == 3
        assert "1/1" in summary["three"]

    def test_free_throw(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.FREE_THROW_MADE))
        agg.process_event(_make_event(GameEventType.FREE_THROW_MISSED))
        summary = agg.get_team_summary("home")
        assert summary["total_points"] == 1
        assert summary["ft_pct"] == 50.0

    def test_rebounds(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.OFFENSIVE_REBOUND))
        agg.process_event(_make_event(GameEventType.DEFENSIVE_REBOUND))
        summary = agg.get_team_summary("home")
        assert summary["rebounds"] == 2
        assert summary["offensive_rebounds"] == 1

    def test_assists_turnovers(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.ASSIST))
        agg.process_event(_make_event(GameEventType.TURNOVER))
        summary = agg.get_team_summary("home")
        assert summary["assists"] == 1
        assert summary["turnovers"] == 1

    def test_steals_blocks(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.STEAL))
        agg.process_event(_make_event(GameEventType.BLOCK))
        summary = agg.get_team_summary("home")
        assert summary["steals"] == 1
        assert summary["blocks"] == 1

    def test_paint_points(self):
        agg = TeamStatsAggregator()
        agg.process_event(
            _make_event(GameEventType.SHOT_MADE, points=2),
            is_paint=True,
        )
        summary = agg.get_team_summary("home")
        assert summary["points_in_paint"] == 2

    def test_fast_break_points(self):
        agg = TeamStatsAggregator()
        agg.process_event(
            _make_event(GameEventType.SHOT_MADE, points=2),
            is_fast_break=True,
        )
        summary = agg.get_team_summary("home")
        assert summary["fast_break_points"] == 2

    def test_bench_points(self):
        agg = TeamStatsAggregator()
        agg.register_starters("home", {1, 2, 3, 4, 5})
        # 벤치 선수 (7번)
        agg.process_event(_make_event(
            GameEventType.SHOT_MADE, points=2, player_id=7,
        ))
        summary = agg.get_team_summary("home")
        assert summary["bench_points"] == 2

    def test_quarter_scores(self):
        agg = TeamStatsAggregator()
        agg.process_event(
            _make_event(GameEventType.SHOT_MADE, points=2), quarter=1,
        )
        agg.process_event(
            _make_event(GameEventType.SHOT_MADE, points=3), quarter=2,
        )
        summary = agg.get_team_summary("home")
        assert summary["quarter_scores"] == [2, 3, 0, 0]

    def test_score_comparison(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.SHOT_MADE, team_id="home", points=2))
        agg.process_event(_make_event(GameEventType.SHOT_MADE, team_id="away", points=3))
        scores = agg.get_score_comparison()
        assert scores["home"] == 2
        assert scores["away"] == 3

    def test_reset(self):
        agg = TeamStatsAggregator()
        agg.process_event(_make_event(GameEventType.SHOT_MADE, points=2))
        agg.reset()
        assert agg.total_events == 0
        assert agg.get_team_summary("home") == {}
