# -*- coding: utf-8 -*-
"""BenchUnitAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.rotation_analysis.bench_unit_analyzer import (
    BenchUnitAnalyzer, BenchUnitAnalyzerConfig, UnitType,
)


class TestBenchInit:
    def test_default(self) -> None:
        a = BenchUnitAnalyzer()
        assert a.name == "BenchUnitAnalyzer"
        assert a.total_records == 0


class TestClassifyUnit:
    def test_starter(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        assert a.classify_unit(1, [10, 11, 12, 13, 14]) == UnitType.STARTER

    def test_bench(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        assert a.classify_unit(1, [20, 21, 22, 23, 24]) == UnitType.BENCH

    def test_mixed(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        assert a.classify_unit(1, [10, 11, 12, 20, 21]) == UnitType.MIXED

    def test_no_starters(self) -> None:
        a = BenchUnitAnalyzer()
        assert a.classify_unit(1, [10, 11]) == UnitType.MIXED


class TestRecordPossession:
    def test_record_returns_type(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        ut = a.record_possession(1, [10, 11, 12, 13, 14], points_scored=2)
        assert ut == UnitType.STARTER
        assert a.total_records == 1

    def test_memory_guard(self) -> None:
        cfg = BenchUnitAnalyzerConfig(max_records=2)
        a = BenchUnitAnalyzer(config=cfg)
        a.register_starters(1, [10])
        a.record_possession(1, [10], points_scored=1)
        a.record_possession(1, [10], points_scored=2)
        a.record_possession(1, [10], points_scored=3)  # 한도 초과
        assert a.total_records == 2


class TestUnitNetRating:
    def test_starter_rating(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=3, points_allowed=1)
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=2, points_allowed=1)
        nr = a.get_unit_net_rating(1, UnitType.STARTER)
        # (5-2)/2*100 = 150.0
        assert nr == pytest.approx(150.0)

    def test_empty(self) -> None:
        a = BenchUnitAnalyzer()
        assert a.get_unit_net_rating(1, UnitType.BENCH) == 0.0


class TestUnitPPP:
    def test_ppp(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=3)
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=0)
        ppp = a.get_unit_ppp(1, UnitType.STARTER)
        assert ppp == pytest.approx(1.5)


class TestCompareUnits:
    def test_compare(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=3, points_allowed=1)
        a.record_possession(1, [20, 21, 22, 23, 24], points_scored=1, points_allowed=2)
        result = a.compare_units(1)
        assert result["starter_net"] > result["bench_net"]
        assert result["drop_off"] > 0


class TestUnitDistribution:
    def test_dist(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [20, 21, 22, 23, 24])
        dist = a.get_unit_distribution(1)
        assert dist["starter"] == 2
        assert dist["bench"] == 1


class TestResetRepr:
    def test_reset(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10])
        a.record_possession(1, [10])
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = BenchUnitAnalyzer()
        assert "BenchUnitAnalyzer" in repr(a)

    def test_stats(self) -> None:
        a = BenchUnitAnalyzer()
        a.register_starters(1, [10])
        stats = a.get_stats()
        assert stats["teams_tracked"] == 1
