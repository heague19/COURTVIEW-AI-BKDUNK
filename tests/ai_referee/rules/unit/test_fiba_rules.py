# -*- coding: utf-8 -*-
"""fiba_rules.py 단위 테스트 — 20 tests."""
from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.fiba_rules import (
    CourtDimensions,
    FIBARules,
    FoulRules,
    GameTimeRules,
    LeagueSpecificRules,
    ThreeSecondRules,
    TimeoutRules,
    TravelingRules,
)


# =============================================================================
# YAML stub
# =============================================================================
_FIBA_YAML = {
    "game_time": {
        "quarter_duration_sec": 600,
        "shot_clock_sec": 24,
        "backcourt_sec": 8,
        "free_throw_sec": 5,
    },
    "court": {
        "three_point_distance_m": 6.75,
        "restricted_area_arc_m": 1.25,
    },
    "fouls": {
        "max_personal_fouls": 5,
        "team_foul_bonus_threshold": 4,
        "technical_foul_ejection": 2,
        "unsportsmanlike_foul_ejection": 2,
        "free_throws": {
            "bonus_free_throws": 2,
            "shooting_foul_2pt": 2,
            "shooting_foul_3pt": 3,
        },
    },
    "timeouts": {
        "total_per_game": 5,
        "first_half_max": 2,
        "second_half_max": 3,
        "overtime_additional": 1,
        "duration_sec": 60,
    },
    "three_second_rule": {
        "offensive_three_sec": True,
        "defensive_three_sec": False,
    },
    "traveling": {
        "gather_step": {
            "enabled": True,
            "max_steps_after_gather": 2,
            "zero_step_enabled": False,
        },
        "pivot_foot": {
            "lift_threshold_m": 0.05,
        },
    },
    "fiba_specific": {
        "alternating_possession": {"enabled": True},
        "coach_challenge": False,
    },
}


# =============================================================================
# GameTimeRules
# =============================================================================
class TestGameTimeRules:
    def test_default(self):
        r = GameTimeRules()
        assert r.quarter_duration_sec == 600
        assert r.shot_clock_sec == 24
        assert r.backcourt_sec == 8

    def test_from_yaml(self):
        r = GameTimeRules.from_yaml(_FIBA_YAML["game_time"])
        assert r.quarter_duration_sec == 600
        assert r.free_throw_sec == 5


# =============================================================================
# CourtDimensions
# =============================================================================
class TestCourtDimensions:
    def test_default(self):
        c = CourtDimensions()
        assert c.three_point_distance_m == 6.75
        assert c.restricted_area_arc_m == 1.25

    def test_from_yaml(self):
        c = CourtDimensions.from_yaml(_FIBA_YAML["court"])
        assert c.three_point_distance_m == 6.75


# =============================================================================
# FoulRules
# =============================================================================
class TestFoulRules:
    def test_default(self):
        f = FoulRules()
        assert f.max_personal_fouls == 5
        assert f.team_foul_bonus_threshold == 4

    def test_shooting_foul_ft(self):
        f = FoulRules()
        assert f.get_shooting_foul_ft(is_three_point=False) == 2
        assert f.get_shooting_foul_ft(is_three_point=True) == 3

    def test_from_yaml(self):
        f = FoulRules.from_yaml(_FIBA_YAML["fouls"])
        assert f.max_personal_fouls == 5
        assert f.shooting_foul_3pt == 3


# =============================================================================
# TimeoutRules
# =============================================================================
class TestTimeoutRules:
    def test_default(self):
        t = TimeoutRules()
        assert t.total_per_game == 5
        assert t.duration_sec == 60

    def test_from_yaml(self):
        t = TimeoutRules.from_yaml(_FIBA_YAML["timeouts"])
        assert t.overtime_additional == 1


# =============================================================================
# ThreeSecondRules
# =============================================================================
class TestThreeSecondRules:
    def test_fiba_no_defensive(self):
        r = ThreeSecondRules()
        assert r.offensive_three_sec is True
        assert r.defensive_three_sec is False


# =============================================================================
# TravelingRules
# =============================================================================
class TestTravelingRules:
    def test_fiba_no_zero_step(self):
        r = TravelingRules()
        assert r.zero_step_enabled is False
        assert r.gather_step_enabled is True

    def test_from_yaml(self):
        r = TravelingRules.from_yaml(_FIBA_YAML["traveling"])
        assert r.zero_step_enabled is False


# =============================================================================
# FIBARules — 통합
# =============================================================================
class TestFIBARules:
    def test_default_init(self):
        rules = FIBARules()
        assert rules.rule_set == RuleSet.FIBA
        assert rules.game_time.quarter_duration_sec == 600
        assert rules.fouls.max_personal_fouls == 5

    def test_from_yaml(self):
        rules = FIBARules.from_yaml(_FIBA_YAML)
        assert rules.rule_set == RuleSet.FIBA
        assert rules.game_time.shot_clock_sec == 24

    def test_bonus_situation(self):
        rules = FIBARules()
        assert rules.is_bonus_situation(3) is False
        assert rules.is_bonus_situation(4) is True
        assert rules.is_bonus_situation(5) is True

    def test_eject_personal(self):
        rules = FIBARules()
        assert rules.should_eject_on_personal(4) is False
        assert rules.should_eject_on_personal(5) is True

    def test_eject_technical(self):
        rules = FIBARules()
        assert rules.should_eject_on_technical(1) is False
        assert rules.should_eject_on_technical(2) is True

    def test_eject_unsportsmanlike(self):
        rules = FIBARules()
        assert rules.should_eject_on_unsportsmanlike(1) is False
        assert rules.should_eject_on_unsportsmanlike(2) is True

    def test_shooting_foul_ft(self):
        rules = FIBARules()
        assert rules.get_free_throws_for_shooting_foul(False, False) == 2
        assert rules.get_free_throws_for_shooting_foul(True, False) == 3
        assert rules.get_free_throws_for_shooting_foul(False, True) == 1
        assert rules.get_free_throws_for_shooting_foul(True, True) == 1

    def test_timeouts_remaining(self):
        rules = FIBARules()
        assert rules.get_timeouts_remaining(0, 1) == 5
        assert rules.get_timeouts_remaining(3, 2) == 2
        assert rules.get_timeouts_remaining(5, 4, is_overtime=True) == 1

    def test_no_defensive_three_sec(self):
        rules = FIBARules()
        assert rules.has_defensive_three_seconds() is False

    def test_no_coach_challenge(self):
        rules = FIBARules()
        assert rules.has_coach_challenge() is False

    def test_alternating_possession(self):
        rules = FIBARules()
        assert rules.has_alternating_possession() is True

    def test_get_stats(self):
        rules = FIBARules()
        stats = rules.get_stats()
        assert stats["rule_set"] == "fiba"
        assert stats["quarter_duration_sec"] == 600
        assert stats["defensive_three_sec"] is False

    def test_repr(self):
        rules = FIBARules()
        r = repr(rules)
        assert "fiba" in r
        assert "600" in r
