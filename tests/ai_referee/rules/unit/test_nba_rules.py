# -*- coding: utf-8 -*-
"""nba_rules.py 단위 테스트 — 25 tests."""
from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.nba_rules import (
    ClearPathFoulRules,
    CoachChallengeRules,
    FlagrantFoulRules,
    NBARules,
    NBATimeoutRules,
    ReplayCenterRules,
    TransitionTakeFoulRules,
)


# =============================================================================
# FlagrantFoulRules
# =============================================================================
class TestFlagrantFoulRules:
    def test_default(self):
        f = FlagrantFoulRules()
        assert f.flagrant_1_free_throws == 2
        assert f.flagrant_2_ejection is True

    def test_get_free_throws(self):
        f = FlagrantFoulRules()
        assert f.get_free_throws(is_flagrant_2=False) == 2
        assert f.get_free_throws(is_flagrant_2=True) == 2

    def test_is_ejection(self):
        f = FlagrantFoulRules()
        assert f.is_ejection(is_flagrant_2=False) is False
        assert f.is_ejection(is_flagrant_2=True) is True

    def test_points_ejection(self):
        f = FlagrantFoulRules()
        assert f.should_eject_on_flagrant_points(1) is False
        assert f.should_eject_on_flagrant_points(2) is True

    def test_from_yaml(self):
        cfg = {
            "flagrant_1": {"free_throws": 2, "ejection": False},
            "flagrant_2": {"free_throws": 2, "ejection": True},
        }
        f = FlagrantFoulRules.from_yaml(cfg)
        assert f.flagrant_1_ejection is False
        assert f.flagrant_2_ejection is True


# =============================================================================
# CoachChallengeRules
# =============================================================================
class TestCoachChallengeRules:
    def test_default(self):
        c = CoachChallengeRules()
        assert c.enabled is True
        assert c.challenges_per_game == 1

    def test_can_challenge(self):
        c = CoachChallengeRules()
        assert c.can_challenge(1, "personal_foul") is True
        assert c.can_challenge(0, "personal_foul") is False
        assert c.can_challenge(1, "shot_clock") is False

    def test_from_yaml(self):
        cfg = {
            "enabled": True,
            "challenges_per_game": 2,
            "reviewable_plays": ["personal_foul"],
        }
        c = CoachChallengeRules.from_yaml(cfg)
        assert c.challenges_per_game == 2


# =============================================================================
# ClearPathFoulRules
# =============================================================================
class TestClearPathFoulRules:
    def test_default(self):
        c = ClearPathFoulRules()
        assert c.enabled is True
        assert c.free_throws == 2
        assert c.possession_retained is True


# =============================================================================
# TransitionTakeFoulRules
# =============================================================================
class TestTransitionTakeFoulRules:
    def test_default(self):
        t = TransitionTakeFoulRules()
        assert t.enabled is True
        assert t.free_throw_awarded == 1
        assert t.possession_retained is True


# =============================================================================
# ReplayCenterRules
# =============================================================================
class TestReplayCenterRules:
    def test_default(self):
        r = ReplayCenterRules()
        assert r.enabled is True
        assert len(r.automatic_triggers) > 0

    def test_is_automatic_review(self):
        r = ReplayCenterRules()
        assert r.is_automatic_review("last_2_minutes_4q") is True
        assert r.is_automatic_review("random_play") is False


# =============================================================================
# NBATimeoutRules
# =============================================================================
class TestNBATimeoutRules:
    def test_default(self):
        t = NBATimeoutRules()
        assert t.total_per_game == 7
        assert t.duration_sec == 75
        assert t.mandatory_tv_timeouts is True
        assert t.advance_ball_timeout is True

    def test_from_yaml(self):
        cfg = {
            "total_per_game": 7,
            "duration_sec": 75,
            "overtime_additional": 2,
            "mandatory_tv_timeouts": True,
            "advance_ball_timeout": True,
        }
        t = NBATimeoutRules.from_yaml(cfg)
        assert t.overtime_additional == 2


# =============================================================================
# NBARules — 통합
# =============================================================================
class TestNBARules:
    def test_default_init(self):
        rules = NBARules()
        assert rules.rule_set == RuleSet.NBA
        assert rules.game_time.quarter_duration_sec == 720
        assert rules.fouls.max_personal_fouls == 6

    def test_three_point_distance(self):
        rules = NBARules()
        assert rules.court.three_point_distance_m == 7.24
        assert rules.court.three_point_corner_m == 6.71

    def test_defensive_three_seconds(self):
        rules = NBARules()
        assert rules.has_defensive_three_seconds() is True

    def test_no_alternating_possession(self):
        rules = NBARules()
        assert rules.has_alternating_possession() is False

    def test_coach_challenge(self):
        rules = NBARules()
        assert rules.has_coach_challenge() is True
        assert rules.can_coach_challenge(1, "personal_foul") is True
        assert rules.can_coach_challenge(0, "personal_foul") is False

    def test_flagrant_ejection(self):
        rules = NBARules()
        assert rules.should_eject_on_flagrant(is_flagrant_2=True, total_flagrant_points=0) is True
        assert rules.should_eject_on_flagrant(is_flagrant_2=False, total_flagrant_points=1) is False
        assert rules.should_eject_on_flagrant(is_flagrant_2=False, total_flagrant_points=2) is True

    def test_flagrant_ft(self):
        rules = NBARules()
        assert rules.get_flagrant_free_throws(is_flagrant_2=False) == 2
        assert rules.get_flagrant_free_throws(is_flagrant_2=True) == 2

    def test_clear_path(self):
        rules = NBARules()
        assert rules.is_clear_path_applicable() is True
        ft, poss = rules.get_clear_path_penalty()
        assert ft == 2
        assert poss is True

    def test_transition_take_foul(self):
        rules = NBARules()
        assert rules.is_transition_take_foul_applicable() is True
        ft, poss = rules.get_transition_take_foul_penalty()
        assert ft == 1
        assert poss is True

    def test_replay_center(self):
        rules = NBARules()
        assert rules.is_automatic_replay_situation("overtime") is True

    def test_advance_ball_timeout(self):
        rules = NBARules()
        assert rules.has_advance_ball_timeout() is True

    def test_tv_timeouts(self):
        rules = NBARules()
        assert rules.has_mandatory_tv_timeouts() is True

    def test_defensive_three_sec_penalty(self):
        rules = NBARules()
        ft, poss = rules.get_defensive_three_second_penalty()
        assert ft == 1
        assert poss is True

    def test_timeouts_remaining(self):
        rules = NBARules()
        assert rules.get_timeouts_remaining(0, 1) == 7
        assert rules.get_timeouts_remaining(7, 4, is_overtime=True) == 2

    def test_eject_personal_6(self):
        rules = NBARules()
        assert rules.should_eject_on_personal(5) is False
        assert rules.should_eject_on_personal(6) is True

    def test_zero_step_enabled(self):
        rules = NBARules()
        assert rules.traveling.zero_step_enabled is True

    def test_get_stats(self):
        stats = NBARules().get_stats()
        assert stats["rule_set"] == "nba"
        assert stats["flagrant_enabled"] is True
        assert stats["coach_challenge"] is True

    def test_repr(self):
        r = repr(NBARules())
        assert "nba" in r
        assert "720" in r
