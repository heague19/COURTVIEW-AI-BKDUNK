# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/shot_location/shot_heatmap.py
설명: ShotHeatmapAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.output.shot_location.shot_heatmap import (
    ShotHeatmapAnalyzer,
    ShotHeatmapConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> ShotHeatmapAnalyzer:
    return ShotHeatmapAnalyzer()


@pytest.fixture()
def small_analyzer() -> ShotHeatmapAnalyzer:
    return ShotHeatmapAnalyzer(ShotHeatmapConfig(max_records=5))


@pytest.fixture()
def small_grid() -> ShotHeatmapAnalyzer:
    """작은 그리드 (테스트 편의)."""
    return ShotHeatmapAnalyzer(ShotHeatmapConfig(
        grid_rows=4, grid_cols=4, min_attempts=1,
    ))


# =============================================================================
# 초기화
# =============================================================================

class TestHeatmapInit:
    def test_default_config(self, analyzer: ShotHeatmapAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "ShotHeatmapAnalyzer"

    def test_custom_config(self) -> None:
        cfg = ShotHeatmapConfig(grid_rows=10, grid_cols=10)
        a = ShotHeatmapAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestHeatmapRecording:
    def test_record_single(self, analyzer: ShotHeatmapAnalyzer) -> None:
        analyzer.record_shot(1, 0.0, 5.0, made=True)
        assert analyzer.total_records == 1

    def test_max_records_limit(self, small_analyzer: ShotHeatmapAnalyzer) -> None:
        for _ in range(10):
            small_analyzer.record_shot(1, 0.0, 5.0)
        assert small_analyzer.total_records == 5


# =============================================================================
# 밀도 그리드
# =============================================================================

class TestDensityGrid:
    def test_empty_grid(self, small_grid: ShotHeatmapAnalyzer) -> None:
        grid = small_grid.get_density_grid(1)
        assert len(grid) == 4
        assert len(grid[0]) == 4
        assert all(cell == 0 for row in grid for cell in row)

    def test_shot_increments_cell(self, small_grid: ShotHeatmapAnalyzer) -> None:
        # 코트 중앙 (x=0, y=7) → 그리드 중간
        small_grid.record_shot(1, 0.0, 7.0)
        grid = small_grid.get_density_grid(1)
        total = sum(cell for row in grid for cell in row)
        assert total == 1

    def test_multiple_shots_same_cell(self, small_grid: ShotHeatmapAnalyzer) -> None:
        small_grid.record_shot(1, 0.0, 7.0)
        small_grid.record_shot(1, 0.0, 7.0)
        grid = small_grid.get_density_grid(1)
        max_val = max(cell for row in grid for cell in row)
        assert max_val == 2

    def test_team_isolation(self, small_grid: ShotHeatmapAnalyzer) -> None:
        small_grid.record_shot(1, 0.0, 5.0)
        small_grid.record_shot(2, 0.0, 5.0)
        grid1 = small_grid.get_density_grid(1)
        grid2 = small_grid.get_density_grid(2)
        total1 = sum(cell for row in grid1 for cell in row)
        total2 = sum(cell for row in grid2 for cell in row)
        assert total1 == 1
        assert total2 == 1


# =============================================================================
# FG% 그리드
# =============================================================================

class TestFGPctGrid:
    def test_empty_grid_all_negative(self, small_grid: ShotHeatmapAnalyzer) -> None:
        grid = small_grid.get_fg_pct_grid(1)
        assert all(cell == -1.0 for row in grid for cell in row)

    def test_fg_pct_calculation(self, small_grid: ShotHeatmapAnalyzer) -> None:
        # 같은 위치에 2개 (1 made, 1 miss)
        small_grid.record_shot(1, 0.0, 7.0, made=True)
        small_grid.record_shot(1, 0.0, 7.0, made=False)
        grid = small_grid.get_fg_pct_grid(1)
        # 최소 1개의 셀이 50%
        pcts = [cell for row in grid for cell in row if cell >= 0]
        assert len(pcts) >= 1
        assert pcts[0] == pytest.approx(50.0)

    def test_min_attempts_filter(self, analyzer: ShotHeatmapAnalyzer) -> None:
        # 기본 min_attempts=3, 1개만 기록하면 -1.0
        analyzer.record_shot(1, 0.0, 7.0, made=True)
        grid = analyzer.get_fg_pct_grid(1)
        pcts = [cell for row in grid for cell in row if cell >= 0]
        assert len(pcts) == 0  # 3개 미만이므로 유효 없음


# =============================================================================
# 핫존/콜드존
# =============================================================================

class TestHotColdZones:
    def test_no_data(self, small_grid: ShotHeatmapAnalyzer) -> None:
        result = small_grid.get_hot_cold_zones(1)
        assert result["hot"] == []
        assert result["cold"] == []

    def test_hot_zone(self, small_grid: ShotHeatmapAnalyzer) -> None:
        # 100% FG = 핫존
        small_grid.record_shot(1, 0.0, 7.0, made=True)
        result = small_grid.get_hot_cold_zones(1)
        assert len(result["hot"]) >= 1

    def test_cold_zone(self, small_grid: ShotHeatmapAnalyzer) -> None:
        # 0% FG = 콜드존
        small_grid.record_shot(1, 0.0, 7.0, made=False)
        result = small_grid.get_hot_cold_zones(1)
        assert len(result["cold"]) >= 1


# =============================================================================
# 슛 빈도
# =============================================================================

class TestShotFrequency:
    def test_no_data(self, analyzer: ShotHeatmapAnalyzer) -> None:
        assert analyzer.get_shot_frequency(1) == 0

    def test_with_data(self, analyzer: ShotHeatmapAnalyzer) -> None:
        analyzer.record_shot(1, 0.0, 5.0)
        analyzer.record_shot(1, 1.0, 5.0)
        assert analyzer.get_shot_frequency(1) == 2


# =============================================================================
# 유틸리티
# =============================================================================

class TestHeatmapUtility:
    def test_get_stats(self, analyzer: ShotHeatmapAnalyzer) -> None:
        analyzer.record_shot(1, 0.0, 5.0)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 1
        assert "grid_size" in stats

    def test_reset(self, analyzer: ShotHeatmapAnalyzer) -> None:
        analyzer.record_shot(1, 0.0, 5.0)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: ShotHeatmapAnalyzer) -> None:
        assert "ShotHeatmapAnalyzer" in repr(analyzer)
