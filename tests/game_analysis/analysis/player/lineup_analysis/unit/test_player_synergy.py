# -*- coding: utf-8 -*-
"""PlayerSynergyAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.lineup_analysis.player_synergy import (
    PlayerSynergyAnalyzer, PlayerSynergyConfig,
)

class TestSynergyInit:
    def test_default(self) -> None:
        a = PlayerSynergyAnalyzer()
        assert a.name == "PlayerSynergyAnalyzer"
        assert a.total_pairs == 0

class TestRecordPossession:
    def test_generates_combos(self) -> None:
        a = PlayerSynergyAnalyzer()
        a.record_possession([1, 2, 3, 4, 5], points_scored=2, points_allowed=1)
        # C(5,2)=10 pairs
        assert a.total_pairs == 10
        stats = a.get_stats()
        # C(5,3)=10 triples
        assert stats["total_triples"] == 10

class TestPairNetRating:
    def test_pair(self) -> None:
        a = PlayerSynergyAnalyzer()
        for _ in range(10):
            a.record_possession([1, 2, 3, 4, 5], points_scored=2, points_allowed=1)
        nr = a.get_pair_net_rating(1, 2)
        # per 100 possessions: (20-10)/10*100 = 100.0
        assert nr == pytest.approx(100.0)

    def test_unknown_pair(self) -> None:
        a = PlayerSynergyAnalyzer()
        assert a.get_pair_net_rating(99, 100) == 0.0

    def test_order_independent(self) -> None:
        a = PlayerSynergyAnalyzer()
        a.record_possession([1, 2, 3, 4, 5], points_scored=3, points_allowed=0)
        assert a.get_pair_net_rating(2, 1) == a.get_pair_net_rating(1, 2)

class TestTripleNetRating:
    def test_triple(self) -> None:
        a = PlayerSynergyAnalyzer()
        for _ in range(5):
            a.record_possession([1, 2, 3, 4, 5], points_scored=3, points_allowed=2)
        nr = a.get_triple_net_rating(1, 2, 3)
        # per 100 possessions: (15-10)/5*100 = 100.0
        assert nr == pytest.approx(100.0)

class TestBestPair:
    def test_best_pair(self) -> None:
        cfg = PlayerSynergyConfig(min_possessions=3)
        a = PlayerSynergyAnalyzer(config=cfg)
        # 1,2가 함께할 때 좋은 결과
        for _ in range(5):
            a.record_possession([1, 2, 3, 4, 5], points_scored=3, points_allowed=0)
        best = a.get_best_pair()
        assert best is not None

    def test_no_qualifying(self) -> None:
        cfg = PlayerSynergyConfig(min_possessions=100)
        a = PlayerSynergyAnalyzer(config=cfg)
        a.record_possession([1, 2, 3, 4, 5], points_scored=3, points_allowed=0)
        assert a.get_best_pair() is None

class TestResetRepr:
    def test_reset(self) -> None:
        a = PlayerSynergyAnalyzer()
        a.record_possession([1, 2, 3, 4, 5], points_scored=2)
        a.reset()
        assert a.total_pairs == 0

    def test_repr(self) -> None:
        a = PlayerSynergyAnalyzer()
        assert "PlayerSynergyAnalyzer" in repr(a)
