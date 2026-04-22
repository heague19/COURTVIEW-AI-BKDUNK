# -*- coding: utf-8 -*-
"""kbl_rules.py 단위 테스트 — 16 tests."""
from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.kbl_rules import (
    ForeignPlayerRules,
    KBLRules,
    KBLSubstitutionRules,
    KBLTimeoutRules,
    KBLVideoReviewRules,
)


# =============================================================================
# KBLVideoReviewRules
# =============================================================================
class TestKBLVideoReviewRules:
    def test_default(self):
        v = KBLVideoReviewRules()
        assert v.enabled is True
        assert "out_of_bounds" in v.situations

    def test_is_reviewable(self):
        v = KBLVideoReviewRules()
        assert v.is_reviewable("goaltending") is True
        assert v.is_reviewable("random_call") is False

    def test_no_coach_challenge(self):
        v = KBLVideoReviewRules()
        assert v.coach_challenge is False


# =============================================================================
# ForeignPlayerRules
# =============================================================================
class TestForeignPlayerRules:
    def test_default(self):
        f = ForeignPlayerRules()
        assert f.max_on_court == 2
        assert f.total_roster == 2

    def test_lineup_valid(self):
        f = ForeignPlayerRules()
        assert f.is_lineup_valid(2) is True
        assert f.is_lineup_valid(3) is False

    def test_from_yaml(self):
        f = ForeignPlayerRules.from_yaml({"max_on_court": 3, "total_roster": 3})
        assert f.max_on_court == 3


# =============================================================================
# KBLSubstitutionRules
# =============================================================================
class TestKBLSubstitutionRules:
    def test_default(self):
        s = KBLSubstitutionRules()
        assert s.dead_ball_only is True
        assert s.free_substitution is False


# =============================================================================
# KBLTimeoutRules
# =============================================================================
class TestKBLTimeoutRules:
    def test_default(self):
        t = KBLTimeoutRules()
        assert t.total_per_game == 5
        assert t.duration_sec == 60
        assert t.tv_timeout is True


# =============================================================================
# KBLRules — 통합
# =============================================================================
class TestKBLRules:
    def test_default_init(self):
        rules = KBLRules()
        assert rules.rule_set == RuleSet.KBL
        assert rules.game_time.quarter_duration_sec == 600
        assert rules.fouls.max_personal_fouls == 5

    def test_fiba_compatible(self):
        """KBL은 FIBA 규정 준용."""
        rules = KBLRules()
        assert rules.has_defensive_three_seconds() is False
        assert rules.has_alternating_possession() is True
        assert rules.has_coach_challenge() is False

    def test_video_reviewable(self):
        rules = KBLRules()
        assert rules.is_video_reviewable("out_of_bounds") is True
        assert rules.is_video_reviewable("clear_path") is False

    def test_lineup_valid(self):
        rules = KBLRules()
        assert rules.is_lineup_valid(2) is True
        assert rules.is_lineup_valid(3) is False

    def test_can_substitute(self):
        rules = KBLRules()
        assert rules.can_substitute(is_dead_ball=True) is True
        assert rules.can_substitute(is_dead_ball=False) is False

    def test_tv_timeout(self):
        rules = KBLRules()
        assert rules.has_tv_timeout() is True

    def test_get_stats(self):
        stats = KBLRules().get_stats()
        assert stats["rule_set"] == "kbl"
        assert stats["foreign_player_max"] == 2

    def test_repr(self):
        r = repr(KBLRules())
        assert "kbl" in r
        assert "foreign_max=2" in r
