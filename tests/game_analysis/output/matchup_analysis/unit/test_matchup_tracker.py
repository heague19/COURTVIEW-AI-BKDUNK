# -*- coding: utf-8 -*-
"""MatchupTracker 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.matchup_analysis.matchup_tracker import (
    MatchupTracker,
    MatchupTrackerConfig,
    MatchupEventInput,
)


def _evt(**kwargs) -> MatchupEventInput:
    defaults = dict(
        defender_tracking_id=1, offensive_tracking_id=10,
        points_allowed=2, fg_attempted=True, fg_made=True,
        was_contested=True, avg_distance_m=1.2,
    )
    defaults.update(kwargs)
    return MatchupEventInput(**defaults)


class TestMatchupTracker:
    """MatchupTracker 단위 테스트."""

    def test_init_default(self):
        mt = MatchupTracker()
        assert mt.name == "MatchupTracker"

    def test_record_single(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt())
        result = mt.get_matchup(1, 10)
        assert result is not None
        assert result.possessions == 1
        assert result.fg_pct == 1.0

    def test_accumulate_matchup(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(fg_made=True, points_allowed=2))
        mt.record_matchup(_evt(fg_made=False, points_allowed=0))
        mt.record_matchup(_evt(fg_made=True, points_allowed=3))
        result = mt.get_matchup(1, 10)
        assert result is not None
        assert result.possessions == 3
        assert result.fg_made == 2
        assert result.fg_attempts == 3
        assert result.points_allowed == 5

    def test_fg_pct_calculation(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(fg_made=True))
        mt.record_matchup(_evt(fg_made=False))
        mt.record_matchup(_evt(fg_made=True))
        mt.record_matchup(_evt(fg_made=False))
        result = mt.get_matchup(1, 10)
        assert result.fg_pct == 0.5

    def test_contest_rate(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(was_contested=True))
        mt.record_matchup(_evt(was_contested=False))
        mt.record_matchup(_evt(was_contested=True))
        result = mt.get_matchup(1, 10)
        assert result.contest_rate == pytest.approx(0.667, abs=0.001)

    def test_defender_matchups(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(defender_tracking_id=1, offensive_tracking_id=10))
        mt.record_matchup(_evt(defender_tracking_id=1, offensive_tracking_id=20))
        mt.record_matchup(_evt(defender_tracking_id=2, offensive_tracking_id=10))
        results = mt.get_defender_matchups(1)
        assert len(results) == 2

    def test_offensive_matchups(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(defender_tracking_id=1, offensive_tracking_id=10))
        mt.record_matchup(_evt(defender_tracking_id=2, offensive_tracking_id=10))
        mt.record_matchup(_evt(defender_tracking_id=3, offensive_tracking_id=20))
        results = mt.get_offensive_matchups(10)
        assert len(results) == 2

    def test_min_possessions_filter(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=5))
        for _ in range(3):
            mt.record_matchup(_evt())
        results = mt.get_all_matchups()
        assert len(results) == 0  # 3 < 5 최소 점유

    def test_all_matchups(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(defender_tracking_id=1, offensive_tracking_id=10))
        mt.record_matchup(_evt(defender_tracking_id=2, offensive_tracking_id=20))
        results = mt.get_all_matchups()
        assert len(results) == 2

    def test_nonexistent_matchup(self):
        mt = MatchupTracker()
        result = mt.get_matchup(99, 99)
        assert result is None

    def test_no_fg_attempt(self):
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=1))
        mt.record_matchup(_evt(fg_attempted=False, fg_made=False, points_allowed=0))
        result = mt.get_matchup(1, 10)
        assert result.fg_attempts == 0
        assert result.fg_pct == 0.0

    def test_reset(self):
        mt = MatchupTracker()
        mt.record_matchup(_evt())
        mt.record_matchup(_evt())
        mt.reset()
        assert len(mt.get_all_matchups()) == 0
        assert len(mt.get_event_history()) == 0
