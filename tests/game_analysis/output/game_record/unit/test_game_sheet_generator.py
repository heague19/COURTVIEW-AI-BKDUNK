# -*- coding: utf-8 -*-
"""GameSheetGenerator 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.game_record.game_sheet_generator import (
    GameSheetGenerator,
    GameSheetConfig,
    PlayerStatInput,
    PlayerBoxScore,
    TeamBoxScore,
    GameSheet,
)


def _stat(**kwargs) -> PlayerStatInput:
    defaults = dict(
        player_id=7, team_id="home", jersey_number=7,
        points=20, field_goals_made=7, field_goals_attempted=14,
        three_pointers_made=2, three_pointers_attempted=5,
        free_throws_made=4, free_throws_attempted=5,
        offensive_rebounds=2, defensive_rebounds=4,
        assists=5, steals=2, blocks=1, turnovers=3,
        personal_fouls=2, minutes_played=30.0, plus_minus=8,
        is_starter=True,
    )
    defaults.update(kwargs)
    return PlayerStatInput(**defaults)


class TestGameSheetGenerator:
    """GameSheetGenerator 단위 테스트."""

    def test_init_default(self):
        gs = GameSheetGenerator()
        assert gs.name == "GameSheetGenerator"

    def test_update_and_get_player(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=7, team_id="home"))
        box = gs.get_player_box_score("home", 7)
        assert box is not None
        assert box.points == 20
        assert box.total_rebounds == 6  # 2+4

    def test_shooting_percentages(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(
            field_goals_made=5, field_goals_attempted=10,
            three_pointers_made=2, three_pointers_attempted=4,
            free_throws_made=3, free_throws_attempted=4,
        ))
        box = gs.get_player_box_score("home", 7)
        assert box.fg_percentage == 50.0
        assert box.three_pt_percentage == 50.0
        assert box.ft_percentage == 75.0

    def test_efg_percentage(self):
        gs = GameSheetGenerator()
        # eFG% = (FGM + 0.5*3PM) / FGA * 100 = (5 + 0.5*2) / 10 * 100 = 60.0
        gs.update_player_stats(_stat(
            field_goals_made=5, field_goals_attempted=10,
            three_pointers_made=2,
        ))
        box = gs.get_player_box_score("home", 7)
        assert box.efg_percentage == 60.0

    def test_ts_percentage(self):
        gs = GameSheetGenerator()
        # TS% = PTS / (2 * (FGA + 0.44 * FTA)) * 100
        gs.update_player_stats(_stat(
            points=20, field_goals_attempted=14, free_throws_attempted=5,
        ))
        box = gs.get_player_box_score("home", 7)
        assert box.ts_percentage > 0.0

    def test_game_score(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat())
        box = gs.get_player_box_score("home", 7)
        assert box.game_score > 0.0

    def test_double_double(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(
            points=15, offensive_rebounds=5, defensive_rebounds=7,  # 12 REB
        ))
        box = gs.get_player_box_score("home", 7)
        assert box.is_double_double is True
        assert box.is_triple_double is False

    def test_triple_double(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(
            points=15, offensive_rebounds=5, defensive_rebounds=7,
            assists=11,
        ))
        box = gs.get_player_box_score("home", 7)
        assert box.is_triple_double is True

    def test_generate_game_sheet(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=7, team_id="home"))
        gs.update_player_stats(_stat(player_id=11, team_id="away", points=15))
        gs.set_quarter_scores("home", [25, 20, 22, 18])
        gs.set_game_flow(lead_changes=5, ties=3)
        sheet = gs.generate()
        assert sheet.home_team.total_points == 20
        assert sheet.away_team.total_points == 15
        assert sheet.lead_changes == 5
        assert sheet.home_team.quarter_scores == [25, 20, 22, 18]

    def test_team_aggregation(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=7, team_id="home", assists=5, steals=2))
        gs.update_player_stats(_stat(player_id=11, team_id="home", assists=3, steals=1))
        sheet = gs.generate()
        assert sheet.home_team.total_assists == 8
        assert sheet.home_team.total_steals == 3

    def test_special_points(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=7, team_id="home"))
        gs.set_special_points("home", paint=20, fast_break=10, second_chance=6, bench=12)
        sheet = gs.generate()
        assert sheet.home_team.points_in_paint == 20
        assert sheet.home_team.fast_break_points == 10

    def test_team_leaders(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=7, team_id="home", points=25))
        gs.update_player_stats(_stat(player_id=11, team_id="home", points=15))
        gs.update_player_stats(_stat(player_id=23, team_id="home", points=20))
        leaders = gs.get_team_leaders("home", "points", n=2)
        assert len(leaders) == 2
        assert leaders[0].points == 25

    def test_starter_bench_ordering(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat(player_id=1, team_id="home", jersey_number=23, is_starter=False))
        gs.update_player_stats(_stat(player_id=2, team_id="home", jersey_number=7, is_starter=True))
        gs.update_player_stats(_stat(player_id=3, team_id="home", jersey_number=11, is_starter=True))
        sheet = gs.generate()
        players = sheet.home_team.players
        # 스타터 먼저 (7, 11), 벤치 (23)
        assert players[0].jersey_number == 7
        assert players[1].jersey_number == 11
        assert players[2].jersey_number == 23

    def test_reset(self):
        gs = GameSheetGenerator()
        gs.update_player_stats(_stat())
        gs.reset()
        assert gs.get_player_box_score("home", 7) is None
        assert len(gs.get_event_history()) == 0
