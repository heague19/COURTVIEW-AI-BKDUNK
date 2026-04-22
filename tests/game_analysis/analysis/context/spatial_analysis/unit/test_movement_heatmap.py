# -*- coding: utf-8 -*-
"""MovementHeatmapAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.spatial_analysis.movement_heatmap import (
    MovementHeatmapAnalyzer,
    MovementHeatmapConfig,
)


class TestHeatmapInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        assert analyzer.name == "MovementHeatmapAnalyzer"
        assert analyzer.total_records == 0

    def test_custom_config(self) -> None:
        cfg = MovementHeatmapConfig(grid_rows=5, grid_cols=5)
        analyzer = MovementHeatmapAnalyzer(config=cfg)
        assert analyzer._config.grid_rows == 5


class TestRecordPosition:
    """위치 기록 테스트."""

    def test_record_single(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        row, col = analyzer.record_position(player_id=10, team_id=1, x=7.5, y=7.0)
        assert 0 <= row < 10
        assert 0 <= col < 10
        assert analyzer.total_records == 1

    def test_boundary_clamp(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        # 범위 초과
        row, col = analyzer.record_position(player_id=10, team_id=1, x=100.0, y=100.0)
        assert row == 9  # grid_rows - 1
        assert col == 9

    def test_negative_clamp(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        row, col = analyzer.record_position(player_id=10, team_id=1, x=-5.0, y=-5.0)
        assert row == 0
        assert col == 0


class TestPlayerHeatmap:
    """선수별 히트맵 테스트."""

    def test_empty_player(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        grid = analyzer.get_player_heatmap(99)
        assert len(grid) == 10
        assert all(sum(row) == 0 for row in grid)

    def test_accumulates(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        # 같은 위치 3회
        for _ in range(3):
            analyzer.record_position(player_id=10, team_id=1, x=7.5, y=7.0)
        grid = analyzer.get_player_heatmap(10)
        total = sum(sum(row) for row in grid)
        assert total == 3

    def test_defensive_copy(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        analyzer.record_position(player_id=10, team_id=1, x=7.5, y=7.0)
        grid = analyzer.get_player_heatmap(10)
        grid[0][0] = 999
        original = analyzer.get_player_heatmap(10)
        assert original[0][0] != 999


class TestTeamHeatmap:
    """팀별 히트맵 테스트."""

    def test_team_accumulates(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        analyzer.record_position(player_id=10, team_id=1, x=5.0, y=5.0)
        analyzer.record_position(player_id=20, team_id=1, x=5.0, y=5.0)
        grid = analyzer.get_team_heatmap(1)
        total = sum(sum(row) for row in grid)
        assert total == 2


class TestPlayerHotspot:
    """최다 체류 셀 테스트."""

    def test_hotspot(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        # 특정 위치에 집중
        for _ in range(10):
            analyzer.record_position(player_id=10, team_id=1, x=3.0, y=3.0)
        for _ in range(2):
            analyzer.record_position(player_id=10, team_id=1, x=10.0, y=10.0)
        row, col = analyzer.get_player_hotspot(10)
        grid = analyzer.get_player_heatmap(10)
        assert grid[row][col] == 10

    def test_empty_hotspot(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        assert analyzer.get_player_hotspot(99) == (0, 0)


class TestPlayerZonePct:
    """영역별 체류 비율 테스트."""

    def test_zone_pct(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        # 다양한 위치 기록
        for _ in range(10):
            analyzer.record_position(player_id=10, team_id=1, x=7.5, y=12.0)  # 하단 중앙 = paint
        for _ in range(5):
            analyzer.record_position(player_id=10, team_id=1, x=7.5, y=2.0)  # 상단 = three
        pct = analyzer.get_player_zone_pct(10)
        assert pct["paint"] > 0
        assert pct["three"] > 0
        total = pct["paint"] + pct["mid"] + pct["three"]
        assert total == pytest.approx(100.0)

    def test_empty_zone_pct(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        pct = analyzer.get_player_zone_pct(99)
        assert pct["paint"] == 0.0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        analyzer.record_position(player_id=10, team_id=1, x=5.0, y=5.0)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 1
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        analyzer.record_position(player_id=10, team_id=1, x=5.0, y=5.0)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self) -> None:
        analyzer = MovementHeatmapAnalyzer()
        assert "MovementHeatmapAnalyzer" in repr(analyzer)
