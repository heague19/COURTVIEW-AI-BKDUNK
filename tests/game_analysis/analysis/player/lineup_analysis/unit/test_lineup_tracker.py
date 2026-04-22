# -*- coding: utf-8 -*-
"""LineupTracker 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.lineup_analysis.lineup_tracker import LineupTracker, LineupTrackerConfig
from shared.dto.tactical_dto import LineupData

class TestLineupTrackerInit:
    def test_default(self) -> None:
        t = LineupTracker()
        assert t.name == "LineupTracker"
        assert t.total_lineups == 0

class TestMakeLineupId:
    def test_sorted(self) -> None:
        assert LineupTracker.make_lineup_id([5, 3, 1, 4, 2]) == "1-2-3-4-5"

class TestSetLineup:
    def test_set_and_count(self) -> None:
        t = LineupTracker()
        lid = t.set_lineup([10, 20, 30, 40, 50])
        assert lid == "10-20-30-40-50"
        assert t.total_lineups == 1

    def test_same_lineup_no_duplicate(self) -> None:
        t = LineupTracker()
        t.set_lineup([1, 2, 3, 4, 5])
        t.set_lineup([5, 4, 3, 2, 1])
        assert t.total_lineups == 1

class TestRecordPossession:
    def test_accumulates(self) -> None:
        t = LineupTracker()
        t.set_lineup([1, 2, 3, 4, 5])
        t.record_possession(minutes_elapsed=0.5, points_scored=2, points_allowed=0)
        t.record_possession(minutes_elapsed=0.5, points_scored=0, points_allowed=3)
        lid = "1-2-3-4-5"
        data = t.get_lineup_data(lid)
        assert data.possessions == 2
        assert data.minutes == pytest.approx(1.0)
        assert data.plus_minus == -1

    def test_no_lineup_set(self) -> None:
        t = LineupTracker()
        t.record_possession(minutes_elapsed=0.5, points_scored=2)
        assert t.total_lineups == 0

class TestGetLineupData:
    def test_empty(self) -> None:
        t = LineupTracker()
        data = t.get_lineup_data("nonexistent")
        assert isinstance(data, LineupData)
        assert data.possessions == 0

    def test_ratings(self) -> None:
        t = LineupTracker()
        t.set_lineup([1, 2, 3, 4, 5])
        for _ in range(10):
            t.record_possession(points_scored=2, points_allowed=1)
        data = t.get_lineup_data("1-2-3-4-5")
        # per 100 possessions: OR=20/10*100=200, DR=10/10*100=100, NR=100
        assert data.offensive_rating == pytest.approx(200.0)
        assert data.defensive_rating == pytest.approx(100.0)
        assert data.net_rating == pytest.approx(100.0)

class TestGetAllLineups:
    def test_sorted_by_minutes(self) -> None:
        t = LineupTracker()
        t.set_lineup([1, 2, 3, 4, 5])
        t.record_possession(minutes_elapsed=10.0)
        t.set_lineup([6, 7, 8, 9, 10])
        t.record_possession(minutes_elapsed=20.0)
        all_lineups = t.get_all_lineups()
        assert len(all_lineups) == 2
        assert all_lineups[0].minutes >= all_lineups[1].minutes

class TestResetRepr:
    def test_reset(self) -> None:
        t = LineupTracker()
        t.set_lineup([1, 2, 3, 4, 5])
        t.reset()
        assert t.total_lineups == 0

    def test_repr(self) -> None:
        t = LineupTracker()
        assert "LineupTracker" in repr(t)
