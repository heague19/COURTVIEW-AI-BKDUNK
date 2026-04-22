# -*- coding: utf-8 -*-
"""TrendTracker 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.season_analysis.trend_tracker import (
    TrendTracker, TrendTrackerConfig, TrendDirection,
)


class TestTrendInit:
    def test_default(self) -> None:
        t = TrendTracker()
        assert t.name == "TrendTracker"
        assert t.total_data_points == 0


class TestRecordStat:
    def test_single(self) -> None:
        t = TrendTracker()
        t.record_stat(1, "ppg", 25.0)
        assert t.total_data_points == 1

    def test_memory_guard(self) -> None:
        cfg = TrendTrackerConfig(max_data_points=3)
        t = TrendTracker(config=cfg)
        for i in range(5):
            t.record_stat(1, "ppg", float(i))
        assert t.total_data_points == 3


class TestMovingAverage:
    def test_short_window(self) -> None:
        cfg = TrendTrackerConfig(min_games=2)
        t = TrendTracker(config=cfg)
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            t.record_stat(1, "ppg", v)
        # short window = 3 → avg(30, 40, 50) = 40
        ma = t.get_moving_average(1, "ppg", window=3)
        assert ma == pytest.approx(40.0)

    def test_not_enough_games(self) -> None:
        cfg = TrendTrackerConfig(min_games=5)
        t = TrendTracker(config=cfg)
        t.record_stat(1, "ppg", 10.0)
        t.record_stat(1, "ppg", 20.0)
        assert t.get_moving_average(1, "ppg") == 0.0

    def test_all_windows(self) -> None:
        cfg = TrendTrackerConfig(min_games=1, window_short=2, window_medium=3, window_long=5)
        t = TrendTracker(config=cfg)
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            t.record_stat(1, "ppg", v)
        windows = t.get_all_windows(1, "ppg")
        assert windows["short"] == pytest.approx(45.0)   # avg(40,50)
        assert windows["medium"] == pytest.approx(40.0)  # avg(30,40,50)
        assert windows["long"] == pytest.approx(30.0)    # avg(10..50)


class TestTrendDirection:
    def test_rising(self) -> None:
        cfg = TrendTrackerConfig(min_games=2)
        t = TrendTracker(config=cfg)
        for v in [10.0, 15.0, 20.0, 25.0, 30.0]:
            t.record_stat(1, "ppg", v)
        assert t.get_trend_direction(1, "ppg") == TrendDirection.RISING

    def test_declining(self) -> None:
        cfg = TrendTrackerConfig(min_games=2)
        t = TrendTracker(config=cfg)
        for v in [30.0, 25.0, 20.0, 15.0, 10.0]:
            t.record_stat(1, "ppg", v)
        assert t.get_trend_direction(1, "ppg") == TrendDirection.DECLINING

    def test_stable(self) -> None:
        cfg = TrendTrackerConfig(min_games=2)
        t = TrendTracker(config=cfg)
        for v in [20.0, 20.0, 20.0, 20.0]:
            t.record_stat(1, "ppg", v)
        assert t.get_trend_direction(1, "ppg") == TrendDirection.STABLE

    def test_not_enough_data(self) -> None:
        cfg = TrendTrackerConfig(min_games=10)
        t = TrendTracker(config=cfg)
        t.record_stat(1, "ppg", 10.0)
        assert t.get_trend_direction(1, "ppg") == TrendDirection.STABLE


class TestOutlier:
    def test_outlier(self) -> None:
        cfg = TrendTrackerConfig(min_games=3)
        t = TrendTracker(config=cfg)
        for v in [20.0, 21.0, 19.0, 20.0, 22.0]:
            t.record_stat(1, "ppg", v)
        # mean≈20.4, std≈1.02 → 50은 z≈29 → 이상치
        assert t.is_outlier(1, "ppg", 50.0) is True
        # 21은 z<2 → 정상
        assert t.is_outlier(1, "ppg", 21.0) is False

    def test_not_enough_data(self) -> None:
        cfg = TrendTrackerConfig(min_games=10)
        t = TrendTracker(config=cfg)
        t.record_stat(1, "ppg", 20.0)
        assert t.is_outlier(1, "ppg", 100.0) is False


class TestResetRepr:
    def test_reset(self) -> None:
        t = TrendTracker()
        t.record_stat(1, "ppg", 20.0)
        t.reset()
        assert t.total_data_points == 0

    def test_repr(self) -> None:
        t = TrendTracker()
        assert "TrendTracker" in repr(t)

    def test_stats(self) -> None:
        t = TrendTracker()
        t.record_stat(1, "ppg", 20.0)
        t.record_stat(2, "rpg", 10.0)
        stats = t.get_stats()
        assert stats["entities_tracked"] == 2
        assert stats["total_data_points"] == 2
