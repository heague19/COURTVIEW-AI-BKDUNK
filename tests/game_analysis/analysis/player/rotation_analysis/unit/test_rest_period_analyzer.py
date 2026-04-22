# -*- coding: utf-8 -*-
"""RestPeriodAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.rotation_analysis.rest_period_analyzer import (
    RestPeriodAnalyzer, RestPeriodAnalyzerConfig,
)


class TestRestInit:
    def test_default(self) -> None:
        a = RestPeriodAnalyzer()
        assert a.name == "RestPeriodAnalyzer"
        assert a.total_records == 0


class TestRecordRest:
    def test_single(self) -> None:
        a = RestPeriodAnalyzer()
        a.record_rest_period(10, 180.0, post_rest_points=5, post_rest_possessions=3)
        assert a.total_records == 1

    def test_memory_guard(self) -> None:
        cfg = RestPeriodAnalyzerConfig(max_records=2)
        a = RestPeriodAnalyzer(config=cfg)
        for _ in range(5):
            a.record_rest_period(10, 120.0)
        assert a.total_records == 2


class TestAverageRest:
    def test_average(self) -> None:
        a = RestPeriodAnalyzer()
        a.record_rest_period(10, 120.0)
        a.record_rest_period(10, 180.0)
        assert a.get_average_rest(10) == pytest.approx(150.0)

    def test_empty(self) -> None:
        a = RestPeriodAnalyzer()
        assert a.get_average_rest(99) == 0.0


class TestShortRestCount:
    def test_count(self) -> None:
        cfg = RestPeriodAnalyzerConfig(min_rest_threshold_sec=120.0)
        a = RestPeriodAnalyzer(config=cfg)
        a.record_rest_period(10, 60.0)   # 불충분
        a.record_rest_period(10, 90.0)   # 불충분
        a.record_rest_period(10, 180.0)  # 충분
        assert a.get_short_rest_count(10) == 2


class TestPostRestEfficiency:
    def test_sufficient(self) -> None:
        cfg = RestPeriodAnalyzerConfig(min_rest_threshold_sec=120.0)
        a = RestPeriodAnalyzer(config=cfg)
        a.record_rest_period(10, 180.0, post_rest_points=6, post_rest_possessions=4)
        a.record_rest_period(10, 60.0, post_rest_points=1, post_rest_possessions=4)
        # 충분 휴식만: 6/4 = 1.5
        eff = a.get_post_rest_efficiency(10, sufficient_only=True)
        assert eff == pytest.approx(1.5)

    def test_insufficient(self) -> None:
        cfg = RestPeriodAnalyzerConfig(min_rest_threshold_sec=120.0)
        a = RestPeriodAnalyzer(config=cfg)
        a.record_rest_period(10, 60.0, post_rest_points=1, post_rest_possessions=4)
        eff = a.get_post_rest_efficiency(10, sufficient_only=False)
        assert eff == pytest.approx(0.25)

    def test_empty(self) -> None:
        a = RestPeriodAnalyzer()
        assert a.get_post_rest_efficiency(99) == 0.0

    def test_zero_possessions(self) -> None:
        a = RestPeriodAnalyzer()
        a.record_rest_period(10, 180.0, post_rest_points=0, post_rest_possessions=0)
        assert a.get_post_rest_efficiency(10) == 0.0


class TestCompareRestEffect:
    def test_compare(self) -> None:
        cfg = RestPeriodAnalyzerConfig(min_rest_threshold_sec=120.0)
        a = RestPeriodAnalyzer(config=cfg)
        a.record_rest_period(10, 180.0, post_rest_points=6, post_rest_possessions=4)
        a.record_rest_period(10, 60.0, post_rest_points=1, post_rest_possessions=4)
        result = a.compare_rest_effect(10)
        assert result["sufficient_rest_ppp"] > result["insufficient_rest_ppp"]
        assert result["difference"] > 0


class TestResetRepr:
    def test_reset(self) -> None:
        a = RestPeriodAnalyzer()
        a.record_rest_period(10, 120.0)
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = RestPeriodAnalyzer()
        assert "RestPeriodAnalyzer" in repr(a)

    def test_stats(self) -> None:
        a = RestPeriodAnalyzer()
        a.record_rest_period(10, 120.0)
        a.record_rest_period(20, 180.0)
        stats = a.get_stats()
        assert stats["total_records"] == 2
        assert stats["players_tracked"] == 2
