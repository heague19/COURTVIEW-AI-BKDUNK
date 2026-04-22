# -*- coding: utf-8 -*-
"""OpponentProfiler 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.scouting.opponent_profiler import (
    OpponentProfiler,
    OpponentProfilerConfig,
    GameDataInput,
    PlayerSeasonInput,
)


def _game(**kwargs) -> GameDataInput:
    defaults = dict(
        game_id="G001",
        offensive_rating=115.0, defensive_rating=105.0, pace=78.0,
        primary_offense="pick_and_roll", primary_defense="man_to_man",
        fg_pct=0.48, three_pt_pct=0.38, ft_pct=0.80,
        rebounds=44, assists=26, turnovers=12, steals=8, blocks=5,
    )
    defaults.update(kwargs)
    return GameDataInput(**defaults)


def _player(**kwargs) -> PlayerSeasonInput:
    defaults = dict(
        tracking_id=7, name="Player A", role="PG",
        ppg=18.5, usage_pct=0.28, minutes_per_game=32.0,
    )
    defaults.update(kwargs)
    return PlayerSeasonInput(**defaults)


class TestOpponentProfiler:
    """OpponentProfiler 단위 테스트."""

    def test_init_default(self):
        op = OpponentProfiler()
        assert op.name == "OpponentProfiler"

    def test_build_empty(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        profile = op.build_profile()
        assert profile.team_id == "T001"
        assert profile.games_analyzed == 0

    def test_single_game(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game())
        profile = op.build_profile()
        assert profile.games_analyzed == 1
        assert profile.offensive_rating == 115.0

    def test_multi_game_average(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game(offensive_rating=110.0, defensive_rating=108.0))
        op.add_game(_game(offensive_rating=120.0, defensive_rating=102.0))
        profile = op.build_profile()
        assert profile.offensive_rating == 115.0
        assert profile.defensive_rating == 105.0

    def test_key_players_sorted_by_usage(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game())
        op.set_players([
            _player(tracking_id=1, usage_pct=0.15),
            _player(tracking_id=2, usage_pct=0.30),
            _player(tracking_id=3, usage_pct=0.25),
        ])
        profile = op.build_profile()
        assert len(profile.key_players) == 3
        assert profile.key_players[0].tracking_id == 2  # 최고 사용률

    def test_key_players_max_limit(self):
        op = OpponentProfiler(config=OpponentProfilerConfig(max_key_players=2))
        op.set_team_info("T001", "Eagles")
        op.add_game(_game())
        op.set_players([
            _player(tracking_id=i, usage_pct=0.10 + i * 0.05)
            for i in range(5)
        ])
        profile = op.build_profile()
        assert len(profile.key_players) == 2

    def test_primary_offense_most_frequent(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game(primary_offense="pick_and_roll"))
        op.add_game(_game(primary_offense="pick_and_roll"))
        op.add_game(_game(primary_offense="isolation"))
        profile = op.build_profile()
        assert profile.primary_offense == "pick_and_roll"

    def test_strength_detection_high_offense(self):
        op = OpponentProfiler(config=OpponentProfilerConfig(
            league_avg_offensive_rating=110.0, strength_threshold=3.0,
        ))
        op.set_team_info("T001", "Eagles")
        op.add_game(_game(offensive_rating=115.0))
        profile = op.build_profile()
        assert any("공격 효율" in s for s in profile.strengths)

    def test_weakness_detection_high_turnover(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game(turnovers=18))
        profile = op.build_profile()
        assert any("턴오버" in w for w in profile.weaknesses)

    def test_weakness_detection_low_offense(self):
        op = OpponentProfiler(config=OpponentProfilerConfig(
            league_avg_offensive_rating=110.0, weakness_threshold=3.0,
        ))
        op.set_team_info("T001", "Eagles")
        op.add_game(_game(offensive_rating=105.0))
        profile = op.build_profile()
        assert any("공격 효율" in w for w in profile.weaknesses)

    def test_event_history(self):
        op = OpponentProfiler()
        op.add_game(_game())
        op.add_game(_game(game_id="G002"))
        assert len(op.get_event_history()) == 2

    def test_reset(self):
        op = OpponentProfiler()
        op.set_team_info("T001", "Eagles")
        op.add_game(_game())
        op.set_players([_player()])
        op.reset()
        profile = op.build_profile()
        assert profile.games_analyzed == 0
        assert len(op.get_event_history()) == 0
