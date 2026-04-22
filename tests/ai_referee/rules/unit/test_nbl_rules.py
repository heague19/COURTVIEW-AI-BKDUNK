# -*- coding: utf-8 -*-
"""nbl_rules.py 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.nbl_rules import (
    ImportPlayerRules,
    NBLOvertimeRules,
    NBLRules,
    NBLVideoReviewRules,
)


# =============================================================================
# NBLVideoReviewRules
# =============================================================================
class TestNBLVideoReviewRules:
    def test_default(self):
        v = NBLVideoReviewRules()
        assert v.enabled is True
        assert "out_of_bounds_last_2_min" in v.situations

    def test_is_reviewable(self):
        v = NBLVideoReviewRules()
        assert v.is_reviewable("goaltending") is True
        assert v.is_reviewable("out_of_bounds_last_2_min") is True
        assert v.is_reviewable("coach_challenge") is False


# =============================================================================
# ImportPlayerRules
# =============================================================================
class TestImportPlayerRules:
    def test_default(self):
        p = ImportPlayerRules()
        assert p.max_on_court == 3
        assert p.total_roster == 3

    def test_lineup_valid(self):
        p = ImportPlayerRules()
        assert p.is_lineup_valid(3) is True
        assert p.is_lineup_valid(4) is False


# =============================================================================
# NBLOvertimeRules
# =============================================================================
class TestNBLOvertimeRules:
    def test_default(self):
        o = NBLOvertimeRules()
        assert o.max_overtime_periods == 3
        assert o.regular_season_only is True

    def test_can_play_overtime_regular(self):
        o = NBLOvertimeRules()
        assert o.can_play_overtime(0, is_playoff=False) is True
        assert o.can_play_overtime(2, is_playoff=False) is True
        assert o.can_play_overtime(3, is_playoff=False) is False

    def test_can_play_overtime_playoff(self):
        o = NBLOvertimeRules()
        assert o.can_play_overtime(5, is_playoff=True) is True
        assert o.can_play_overtime(10, is_playoff=True) is True


# =============================================================================
# NBLRules — 통합
# =============================================================================
class TestNBLRules:
    def test_default_init(self):
        rules = NBLRules()
        assert rules.rule_set == RuleSet.NBL
        assert rules.game_time.quarter_duration_sec == 600
        assert rules.fouls.max_personal_fouls == 5

    def test_fiba_compatible(self):
        """NBL은 FIBA 규정 준용."""
        rules = NBLRules()
        assert rules.has_defensive_three_seconds() is False
        assert rules.has_alternating_possession() is True
        assert rules.has_coach_challenge() is False

    def test_video_reviewable(self):
        rules = NBLRules()
        assert rules.is_video_reviewable("out_of_bounds_last_2_min") is True
        assert rules.is_video_reviewable("random_call") is False

    def test_lineup_valid(self):
        rules = NBLRules()
        assert rules.is_lineup_valid(3) is True
        assert rules.is_lineup_valid(4) is False

    def test_can_play_overtime(self):
        rules = NBLRules()
        assert rules.can_play_overtime(2) is True
        assert rules.can_play_overtime(3) is False
        assert rules.can_play_overtime(5, is_playoff=True) is True

    def test_get_stats(self):
        stats = NBLRules().get_stats()
        assert stats["rule_set"] == "nbl"
        assert stats["import_player_max"] == 3
        assert stats["max_overtime"] == 3

    def test_repr(self):
        r = repr(NBLRules())
        assert "nbl" in r
        assert "import_max=3" in r
