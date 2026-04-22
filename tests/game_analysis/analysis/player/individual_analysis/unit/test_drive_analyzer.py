# -*- coding: utf-8 -*-
"""DriveAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.drive_analyzer import (
    DriveAnalyzer,
    DriveAnalyzerConfig,
)
from shared.dto.tactical_dto import DriveStats


class TestDriveAnalyzerInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = DriveAnalyzer()
        assert analyzer.name == "DriveAnalyzer"
        assert analyzer.total_drives == 0

    def test_custom_config(self) -> None:
        cfg = DriveAnalyzerConfig(max_records=100)
        analyzer = DriveAnalyzer(config=cfg)
        assert analyzer._config.max_records == 100


class TestRecordDrive:
    """드라이브 기록 테스트."""

    def test_record_single_drive(self) -> None:
        analyzer = DriveAnalyzer()
        rec = analyzer.record_drive(
            possession_id=1, player_id=10, speed_ms=3.5,
            distance_m=5.0, direction="left", outcome="finish_made",
            points_scored=2,
        )
        assert rec.player_id == 10
        assert rec.direction == "left"
        assert analyzer.total_drives == 1

    def test_record_multiple_players(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10, outcome="finish_made")
        analyzer.record_drive(possession_id=2, player_id=20, outcome="kickout")
        assert analyzer.total_drives == 2

    def test_memory_guard_trims(self) -> None:
        cfg = DriveAnalyzerConfig(max_records=5)
        analyzer = DriveAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_drive(possession_id=i, player_id=1)
        assert analyzer.total_drives == 5


class TestPlayerDriveStats:
    """선수별 DriveStats 산출 테스트."""

    def test_empty_player(self) -> None:
        analyzer = DriveAnalyzer()
        stats = analyzer.get_player_drive_stats(player_id=99)
        assert isinstance(stats, DriveStats)
        assert stats.total_drives == 0

    def test_finish_rate(self) -> None:
        analyzer = DriveAnalyzer()
        # 3 finish attempts: 2 made, 1 missed
        analyzer.record_drive(possession_id=1, player_id=10, outcome="finish_made", points_scored=2)
        analyzer.record_drive(possession_id=2, player_id=10, outcome="finish_made", points_scored=2)
        analyzer.record_drive(possession_id=3, player_id=10, outcome="finish_missed")
        stats = analyzer.get_player_drive_stats(10)
        assert stats.total_drives == 3
        # finish_rate = made/finishes = 2/3
        assert abs(stats.finish_rate - 2.0 / 3.0) < 0.01

    def test_kickout_and_foul_rate(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10, outcome="kickout")
        analyzer.record_drive(possession_id=2, player_id=10, outcome="foul_drawn", points_scored=2)
        analyzer.record_drive(possession_id=3, player_id=10, outcome="turnover")
        analyzer.record_drive(possession_id=4, player_id=10, outcome="finish_made", points_scored=2)
        stats = analyzer.get_player_drive_stats(10)
        assert stats.kick_out_rate == pytest.approx(0.25)
        assert stats.foul_drawn_rate == pytest.approx(0.25)
        assert stats.turnover_rate == pytest.approx(0.25)

    def test_pts_per_drive(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10, outcome="finish_made", points_scored=2)
        analyzer.record_drive(possession_id=2, player_id=10, outcome="foul_drawn", points_scored=3)
        analyzer.record_drive(possession_id=3, player_id=10, outcome="turnover", points_scored=0)
        stats = analyzer.get_player_drive_stats(10)
        assert stats.pts_per_drive == pytest.approx(5.0 / 3.0)


class TestDirectionDistribution:
    """방향 분포 테스트."""

    def test_distribution(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10, direction="left")
        analyzer.record_drive(possession_id=2, player_id=10, direction="left")
        analyzer.record_drive(possession_id=3, player_id=10, direction="right")
        dist = analyzer.get_direction_distribution(10)
        assert dist["left"] == 2
        assert dist["right"] == 1

    def test_empty_distribution(self) -> None:
        analyzer = DriveAnalyzer()
        assert analyzer.get_direction_distribution(99) == {}


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10)
        stats = analyzer.get_stats()
        assert stats["total_drives"] == 1
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = DriveAnalyzer()
        analyzer.record_drive(possession_id=1, player_id=10)
        analyzer.reset()
        assert analyzer.total_drives == 0

    def test_repr(self) -> None:
        analyzer = DriveAnalyzer()
        assert "DriveAnalyzer" in repr(analyzer)
