# -*- coding: utf-8 -*-
"""LineupEfficiencyAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.lineup_analysis.lineup_efficiency import (
    LineupEfficiencyAnalyzer, LineupEfficiencyConfig,
)

class TestEfficiencyInit:
    def test_default(self) -> None:
        a = LineupEfficiencyAnalyzer()
        assert a.name == "LineupEfficiencyAnalyzer"
        assert a.total_lineups == 0

class TestRecordPossession:
    def test_accumulates(self) -> None:
        a = LineupEfficiencyAnalyzer()
        a.record_possession("A", points_scored=3, points_allowed=2)
        a.record_possession("A", points_scored=2, points_allowed=0)
        assert a.total_lineups == 1

class TestNetRating:
    def test_positive(self) -> None:
        a = LineupEfficiencyAnalyzer()
        for _ in range(10):
            a.record_possession("A", points_scored=2, points_allowed=1)
        # per 100 possessions: (20-10)/10*100 = 100.0
        assert a.get_net_rating("A") == pytest.approx(100.0)

    def test_unknown(self) -> None:
        a = LineupEfficiencyAnalyzer()
        assert a.get_net_rating("X") == 0.0

class TestPlusMinus:
    def test_plus_minus(self) -> None:
        a = LineupEfficiencyAnalyzer()
        a.record_possession("A", points_scored=10, points_allowed=7)
        assert a.get_plus_minus("A") == 3

class TestBestWorst:
    def test_best_worst(self) -> None:
        cfg = LineupEfficiencyConfig(min_possessions=5)
        a = LineupEfficiencyAnalyzer(config=cfg)
        for _ in range(10):
            a.record_possession("GOOD", points_scored=3, points_allowed=1)
            a.record_possession("BAD", points_scored=1, points_allowed=3)
        assert a.get_best_lineup() == "GOOD"
        assert a.get_worst_lineup() == "BAD"

    def test_below_min(self) -> None:
        cfg = LineupEfficiencyConfig(min_possessions=100)
        a = LineupEfficiencyAnalyzer(config=cfg)
        a.record_possession("A", points_scored=10, points_allowed=0)
        assert a.get_best_lineup() == ""

class TestCompare:
    def test_compare(self) -> None:
        a = LineupEfficiencyAnalyzer()
        for _ in range(10):
            a.record_possession("A", points_scored=2, points_allowed=1)
            a.record_possession("B", points_scored=1, points_allowed=2)
        result = a.compare_lineups("A", "B")
        # A: (20-10)/10*100=100, B: (10-20)/10*100=-100, diff=200
        assert result["difference"] == pytest.approx(200.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = LineupEfficiencyAnalyzer()
        a.record_possession("A", points_scored=2)
        a.reset()
        assert a.total_lineups == 0

    def test_repr(self) -> None:
        a = LineupEfficiencyAnalyzer()
        assert "LineupEfficiencyAnalyzer" in repr(a)
