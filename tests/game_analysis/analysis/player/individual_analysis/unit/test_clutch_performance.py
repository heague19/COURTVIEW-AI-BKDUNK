# -*- coding: utf-8 -*-
"""ClutchPerformanceAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.clutch_performance import (
    ClutchPerformanceAnalyzer,
    ClutchPerformanceConfig,
)
from shared.dto.tactical_dto import ClutchStats


class TestClutchInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        assert analyzer.name == "ClutchPerformanceAnalyzer"
        assert analyzer.total_clutch_events == 0

    def test_custom_config(self) -> None:
        cfg = ClutchPerformanceConfig(max_records=50)
        analyzer = ClutchPerformanceAnalyzer(config=cfg)
        assert analyzer._config.max_records == 50


class TestIsClutch:
    """클러치 판별 테스트."""

    def test_clutch_4q_close_game(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        # 4Q, 3분 남음, 4점차 → 클러치
        assert analyzer.is_clutch(quarter=4, time_remaining_sec=180.0, score_margin=4)

    def test_not_clutch_1q(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        # 1Q → 클러치 아님
        assert not analyzer.is_clutch(quarter=1, time_remaining_sec=180.0, score_margin=3)

    def test_not_clutch_blowout(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        # 4Q 3분 남았지만 20점차 → 클러치 아님
        assert not analyzer.is_clutch(quarter=4, time_remaining_sec=180.0, score_margin=20)

    def test_clutch_overtime(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        # OT(5Q), 2분 남음, 2점차 → 클러치
        assert analyzer.is_clutch(quarter=5, time_remaining_sec=120.0, score_margin=2)


class TestRecordEvent:
    """이벤트 기록 테스트."""

    def test_record_fg_made(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        ev = analyzer.record_event(
            player_id=10, event_type="fg_made", points=2, plus_minus=2,
        )
        assert ev.event_type == "fg_made"
        assert analyzer.total_clutch_events == 1

    def test_memory_guard(self) -> None:
        cfg = ClutchPerformanceConfig(max_records=5)
        analyzer = ClutchPerformanceAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_event(player_id=1, event_type="fg_made", points=2)
        assert analyzer.total_clutch_events == 5


class TestPlayerClutchStats:
    """ClutchStats DTO 산출 테스트."""

    def test_empty_player(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        stats = analyzer.get_player_clutch_stats(99)
        assert isinstance(stats, ClutchStats)

    def test_fg_pct(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        analyzer.record_event(player_id=10, event_type="fg_made", points=2)
        analyzer.record_event(player_id=10, event_type="fg_made", points=3)
        analyzer.record_event(player_id=10, event_type="fg_missed")
        stats = analyzer.get_player_clutch_stats(10)
        # fg_pct = 2/3 * 100
        assert stats.fg_pct == pytest.approx(200.0 / 3.0)
        assert stats.points == 5

    def test_ft_pct(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        analyzer.record_event(player_id=10, event_type="ft_made", points=1)
        analyzer.record_event(player_id=10, event_type="ft_missed")
        stats = analyzer.get_player_clutch_stats(10)
        assert stats.ft_pct == pytest.approx(50.0)

    def test_turnover_and_plus_minus(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        analyzer.record_event(player_id=10, event_type="turnover", plus_minus=-2)
        analyzer.record_event(player_id=10, event_type="fg_made", points=2, plus_minus=2)
        stats = analyzer.get_player_clutch_stats(10)
        assert stats.turnovers == 1
        assert stats.plus_minus == 0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        analyzer.record_event(player_id=10, event_type="fg_made")
        stats = analyzer.get_stats()
        assert stats["total_clutch_events"] == 1

    def test_reset(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        analyzer.record_event(player_id=10, event_type="fg_made")
        analyzer.reset()
        assert analyzer.total_clutch_events == 0

    def test_repr(self) -> None:
        analyzer = ClutchPerformanceAnalyzer()
        assert "ClutchPerformanceAnalyzer" in repr(analyzer)
