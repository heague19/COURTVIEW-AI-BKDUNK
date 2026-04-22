# -*- coding: utf-8 -*-
"""BenchmarkComparator 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.season_analysis.benchmark_comparator import (
    BenchmarkComparator, BenchmarkComparatorConfig,
)
from shared.constants.stats_constants import PerformanceRating


class TestBenchmarkInit:
    def test_default(self) -> None:
        c = BenchmarkComparator()
        assert c.name == "BenchmarkComparator"
        assert c.total_benchmarks == 0


class TestRegisterBenchmark:
    def test_register(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", league_mean=15.0, league_std=5.0)
        assert c.total_benchmarks == 1

    def test_overwrite(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        c.register_benchmark("ppg", 20.0, 6.0)  # 덮어쓰기
        assert c.total_benchmarks == 1

    def test_memory_guard(self) -> None:
        cfg = BenchmarkComparatorConfig(max_benchmarks=2)
        c = BenchmarkComparator(config=cfg)
        c.register_benchmark("ppg", 15.0, 5.0)
        c.register_benchmark("rpg", 8.0, 3.0)
        c.register_benchmark("apg", 5.0, 2.0)  # 한도 초과
        assert c.total_benchmarks == 2


class TestPercentile:
    def test_above_mean(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        pct = c.get_percentile("ppg", 25.0)  # +2σ
        assert pct > 90.0

    def test_below_mean(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        pct = c.get_percentile("ppg", 5.0)  # -2σ
        assert pct < 10.0

    def test_at_mean(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        pct = c.get_percentile("ppg", 15.0)
        assert pct == pytest.approx(50.0, abs=1.0)

    def test_lower_is_better(self) -> None:
        """TO는 낮을수록 좋음 → 낮은 값이 높은 백분위."""
        c = BenchmarkComparator()
        c.register_benchmark("topg", 3.0, 1.0, higher_is_better=False)
        pct_low = c.get_percentile("topg", 1.0)   # 평균보다 2σ 낮음 = 좋음
        pct_high = c.get_percentile("topg", 5.0)   # 평균보다 2σ 높음 = 나쁨
        assert pct_low > pct_high

    def test_no_benchmark(self) -> None:
        c = BenchmarkComparator()
        assert c.get_percentile("unknown", 10.0) == 50.0


class TestRating:
    def test_elite(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        rating = c.get_rating("ppg", 30.0)  # +3σ
        assert rating == PerformanceRating.ELITE

    def test_poor(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        rating = c.get_rating("ppg", 2.0)  # -2.6σ
        assert rating == PerformanceRating.POOR


class TestCompareToLeague:
    def test_compare(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        result = c.compare_to_league("ppg", 20.0)
        assert result["value"] == 20.0
        assert result["league_mean"] == 15.0
        assert result["difference"] == pytest.approx(5.0)
        assert result["percentile"] > 50.0

    def test_no_benchmark(self) -> None:
        c = BenchmarkComparator()
        result = c.compare_to_league("unknown", 10.0)
        assert result["percentile"] == 50.0


class TestCompareMultiple:
    def test_multiple(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        c.register_benchmark("rpg", 8.0, 3.0)
        results = c.compare_multiple({"ppg": 25.0, "rpg": 5.0})
        assert results["ppg"]["percentile"] > 80.0
        assert results["rpg"]["percentile"] < 30.0


class TestResetRepr:
    def test_reset(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        c.reset()
        assert c.total_benchmarks == 0

    def test_repr(self) -> None:
        c = BenchmarkComparator()
        assert "BenchmarkComparator" in repr(c)

    def test_stats(self) -> None:
        c = BenchmarkComparator()
        c.register_benchmark("ppg", 15.0, 5.0)
        stats = c.get_stats()
        assert stats["total_benchmarks"] == 1
        assert "ppg" in stats["stat_keys"]
