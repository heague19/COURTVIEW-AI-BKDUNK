# -*- coding: utf-8 -*-
"""BasicStatsCalculator 단위 테스트 — 15 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.statistics.basic_stats import (
    BasicStatsCalculator,
    BasicStatsConfig,
)
from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent


# =============================================================================
# 헬퍼
# =============================================================================
def _make_event(
    event_type: GameEventType,
    player_id: int = 7,
    team_id: str = "home",
    points: int = 0,
    confidence: float = 0.85,
    description: str | None = None,
    **kwargs,
) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        primary_player_id=player_id,
        team_id=team_id,
        frame_number=100,
        timestamp=3.33,
        points=points,
        confidence=confidence,
        description=description,
        **kwargs,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestBasicStatsCalculator:
    """BasicStatsCalculator 단위 테스트."""

    def test_init_default(self):
        calc = BasicStatsCalculator()
        assert calc.name == "BasicStatsCalculator"
        assert calc.total_events_processed == 0
        assert calc.player_count == 0

    def test_shot_made_two_pointer(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.SHOT_MADE, points=2))
        ps = calc.get_player_stats(7)
        assert ps is not None
        assert ps.points == 2
        assert ps.field_goals_made == 1
        assert ps.field_goals_attempted == 1

    def test_shot_made_three_pointer(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.SHOT_MADE, points=3))
        ps = calc.get_player_stats(7)
        assert ps is not None
        assert ps.points == 3
        assert ps.three_pointers_made == 1
        assert ps.three_pointers_attempted == 1

    def test_shot_missed(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.SHOT_MISSED))
        ps = calc.get_player_stats(7)
        assert ps is not None
        assert ps.field_goals_attempted == 1
        assert ps.field_goals_made == 0
        assert ps.points == 0

    def test_free_throw_made(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.FREE_THROW_MADE))
        ps = calc.get_player_stats(7)
        assert ps is not None
        assert ps.free_throws_made == 1
        assert ps.free_throws_attempted == 1
        assert ps.points == 1

    def test_free_throw_missed(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.FREE_THROW_MISSED))
        ps = calc.get_player_stats(7)
        assert ps.free_throws_attempted == 1
        assert ps.free_throws_made == 0

    def test_assist(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.ASSIST))
        ps = calc.get_player_stats(7)
        assert ps.assists == 1

    def test_rebounds(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.OFFENSIVE_REBOUND))
        calc.process_event(_make_event(GameEventType.DEFENSIVE_REBOUND))
        ps = calc.get_player_stats(7)
        assert ps.offensive_rebounds == 1
        assert ps.defensive_rebounds == 1
        assert ps.total_rebounds == 2

    def test_steal_and_block(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.STEAL))
        calc.process_event(_make_event(GameEventType.BLOCK))
        ps = calc.get_player_stats(7)
        assert ps.steals == 1
        assert ps.blocks == 1

    def test_turnover(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.TURNOVER))
        ps = calc.get_player_stats(7)
        assert ps.turnovers == 1

    def test_foul(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.PERSONAL_FOUL))
        ps = calc.get_player_stats(7)
        assert ps.personal_fouls == 1

    def test_reject_low_confidence(self):
        calc = BasicStatsCalculator()
        result = calc.process_event(_make_event(
            GameEventType.SHOT_MADE, points=2, confidence=0.30,
        ))
        assert result is False
        assert calc.total_events_processed == 0

    def test_team_totals(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.SHOT_MADE, player_id=7, points=2))
        calc.process_event(_make_event(GameEventType.SHOT_MADE, player_id=11, points=3))
        totals = calc.get_team_totals("home")
        assert totals["points"] == 5
        assert totals["field_goals_made"] == 2

    def test_plus_minus(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.ASSIST))
        calc.update_plus_minus(7, 5)
        ps = calc.get_player_stats(7)
        assert ps.plus_minus == 5

    def test_reset(self):
        calc = BasicStatsCalculator()
        calc.process_event(_make_event(GameEventType.SHOT_MADE, points=2))
        calc.reset()
        assert calc.total_events_processed == 0
        assert calc.player_count == 0
        assert calc.get_player_stats(7) is None
