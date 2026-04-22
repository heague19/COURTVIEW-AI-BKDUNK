# -*- coding: utf-8 -*-
"""ReboundAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.rebound_analysis import (
    ReboundAnalyzer,
    ReboundAnalysisConfig,
)


class TestReboundInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = ReboundAnalyzer()
        assert analyzer.name == "ReboundAnalyzer"
        assert analyzer.total_rebounds == 0

    def test_custom_config(self) -> None:
        cfg = ReboundAnalysisConfig(max_records=100)
        analyzer = ReboundAnalyzer(config=cfg)
        assert analyzer._config.max_records == 100


class TestRecordRebound:
    """리바운드 기록 테스트."""

    def test_record_offensive(self) -> None:
        analyzer = ReboundAnalyzer()
        rec = analyzer.record_rebound(
            player_id=10, rebound_type="offensive",
            position="paint", contest_type="contested",
        )
        assert rec.rebound_type == "offensive"
        assert analyzer.total_rebounds == 1

    def test_record_defensive(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(
            player_id=10, rebound_type="defensive",
            position="perimeter", distance_from_rim_m=5.0,
        )
        assert analyzer.total_rebounds == 1

    def test_memory_guard(self) -> None:
        cfg = ReboundAnalysisConfig(max_records=5)
        analyzer = ReboundAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_rebound(player_id=1, rebound_type="defensive")
        assert analyzer.total_rebounds == 5


class TestPlayerReboundSummary:
    """선수별 리바운드 요약 테스트."""

    def test_empty_player(self) -> None:
        analyzer = ReboundAnalyzer()
        summary = analyzer.get_player_rebound_summary(99)
        assert summary["offensive"] == 0
        assert summary["defensive"] == 0
        assert summary["total"] == 0

    def test_offensive_defensive_count(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="offensive")
        analyzer.record_rebound(player_id=10, rebound_type="offensive")
        analyzer.record_rebound(player_id=10, rebound_type="defensive")
        summary = analyzer.get_player_rebound_summary(10)
        assert summary["offensive"] == 2
        assert summary["defensive"] == 1
        assert summary["total"] == 3

    def test_contested_rate(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="defensive", contest_type="contested")
        analyzer.record_rebound(player_id=10, rebound_type="defensive", contest_type="uncontested")
        analyzer.record_rebound(player_id=10, rebound_type="offensive", contest_type="contested")
        summary = analyzer.get_player_rebound_summary(10)
        # 2/3 * 100 = 66.67%
        assert summary["contested_rate"] == pytest.approx(200.0 / 3.0)

    def test_long_rebounds(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="defensive", distance_from_rim_m=5.0)
        analyzer.record_rebound(player_id=10, rebound_type="defensive", distance_from_rim_m=2.0)
        analyzer.record_rebound(player_id=10, rebound_type="defensive", distance_from_rim_m=6.0)
        summary = analyzer.get_player_rebound_summary(10)
        # 5.0m, 6.0m >= 4.0m(LONG_REBOUND_DISTANCE_M) = 2
        assert summary["long_rebounds"] == 2

    def test_second_chance_points(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="offensive", second_chance_points=2)
        analyzer.record_rebound(player_id=10, rebound_type="offensive", second_chance_points=3)
        summary = analyzer.get_player_rebound_summary(10)
        assert summary["second_chance_points"] == 5


class TestPositionDistribution:
    """위치 분포 테스트."""

    def test_distribution(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="defensive", position="paint")
        analyzer.record_rebound(player_id=10, rebound_type="defensive", position="paint")
        analyzer.record_rebound(player_id=10, rebound_type="defensive", position="mid_range")
        dist = analyzer.get_position_distribution(10)
        assert dist["paint"] == 2
        assert dist["mid_range"] == 1

    def test_empty_distribution(self) -> None:
        analyzer = ReboundAnalyzer()
        assert analyzer.get_position_distribution(99) == {}


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="defensive")
        stats = analyzer.get_stats()
        assert stats["total_rebounds"] == 1
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = ReboundAnalyzer()
        analyzer.record_rebound(player_id=10, rebound_type="defensive")
        analyzer.reset()
        assert analyzer.total_rebounds == 0

    def test_repr(self) -> None:
        analyzer = ReboundAnalyzer()
        assert "ReboundAnalyzer" in repr(analyzer)
