# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/shot_location/efficiency_by_zone.py
설명: ZoneEfficiencyAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from shared.constants.stats_constants import ShotZone

from game_analysis.output.shot_location.efficiency_by_zone import (
    ZoneEfficiencyAnalyzer,
    ZoneEfficiencyConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> ZoneEfficiencyAnalyzer:
    return ZoneEfficiencyAnalyzer()


@pytest.fixture()
def small_analyzer() -> ZoneEfficiencyAnalyzer:
    return ZoneEfficiencyAnalyzer(ZoneEfficiencyConfig(max_records=5))


# =============================================================================
# 초기화
# =============================================================================

class TestZoneEffInit:
    def test_default_config(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "ZoneEfficiencyAnalyzer"

    def test_custom_config(self) -> None:
        cfg = ZoneEfficiencyConfig(max_records=100, min_attempts_for_ranking=3)
        a = ZoneEfficiencyAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestRecording:
    def test_record_single(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        assert analyzer.total_records == 1

    def test_max_records_limit(self, small_analyzer: ZoneEfficiencyAnalyzer) -> None:
        for _ in range(10):
            small_analyzer.record_shot(1, ShotZone.RESTRICTED_AREA)
        assert small_analyzer.total_records == 5


# =============================================================================
# 존별 FG%
# =============================================================================

class TestZoneFGPct:
    def test_no_data(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert analyzer.get_zone_fg_pct(1, ShotZone.RESTRICTED_AREA) == 0.0

    def test_all_made(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        assert analyzer.get_zone_fg_pct(1, ShotZone.RESTRICTED_AREA) == pytest.approx(100.0)

    def test_partial(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.MID_RANGE_CENTER, made=True, points=2)
        analyzer.record_shot(1, ShotZone.MID_RANGE_CENTER, made=False, points=0)
        assert analyzer.get_zone_fg_pct(1, ShotZone.MID_RANGE_CENTER) == pytest.approx(50.0)


# =============================================================================
# 존별 PPP
# =============================================================================

class TestZonePPP:
    def test_no_data(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert analyzer.get_zone_ppp(1, ShotZone.RESTRICTED_AREA) == 0.0

    def test_ppp_calculation(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=True, points=3)
        analyzer.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=False, points=0)
        # PPP = (3+0)/2 = 1.5
        assert analyzer.get_zone_ppp(1, ShotZone.ABOVE_BREAK_CENTER) == pytest.approx(1.5)


# =============================================================================
# 존별 시도 수
# =============================================================================

class TestZoneAttempts:
    def test_no_data(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert analyzer.get_zone_attempts(1, ShotZone.RESTRICTED_AREA) == 0

    def test_count(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA)
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA)
        analyzer.record_shot(1, ShotZone.MID_RANGE_LEFT)
        assert analyzer.get_zone_attempts(1, ShotZone.RESTRICTED_AREA) == 2
        assert analyzer.get_zone_attempts(1, ShotZone.MID_RANGE_LEFT) == 1


# =============================================================================
# 전체 존 요약
# =============================================================================

class TestAllZonesSummary:
    def test_empty(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        summary = analyzer.get_all_zones_summary(1)
        assert summary == {}

    def test_with_data(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        analyzer.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=False, points=0)
        summary = analyzer.get_all_zones_summary(1)
        assert ShotZone.RESTRICTED_AREA.value in summary
        assert ShotZone.ABOVE_BREAK_CENTER.value in summary
        ra = summary[ShotZone.RESTRICTED_AREA.value]
        assert ra["attempts"] == 1
        assert ra["made"] == 1
        assert ra["fg_pct"] == pytest.approx(100.0)


# =============================================================================
# 대분류 효율
# =============================================================================

class TestCategoryEfficiency:
    def test_empty(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        cats = analyzer.get_category_efficiency(1)
        assert cats["paint"]["attempts"] == 0
        assert cats["midrange"]["attempts"] == 0
        assert cats["three_point"]["attempts"] == 0

    def test_paint_category(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        analyzer.record_shot(1, ShotZone.PAINT_NON_RA, made=True, points=2)
        cats = analyzer.get_category_efficiency(1)
        assert cats["paint"]["attempts"] == 2
        assert cats["paint"]["fg_pct"] == pytest.approx(100.0)

    def test_three_point_category(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.CORNER_THREE_LEFT, made=True, points=3)
        analyzer.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=False, points=0)
        cats = analyzer.get_category_efficiency(1)
        assert cats["three_point"]["attempts"] == 2
        assert cats["three_point"]["fg_pct"] == pytest.approx(50.0)
        assert cats["three_point"]["ppp"] == pytest.approx(1.5)

    def test_midrange_category(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.MID_RANGE_CENTER, made=True, points=2)
        cats = analyzer.get_category_efficiency(1)
        assert cats["midrange"]["attempts"] == 1


# =============================================================================
# 베스트/워스트 존
# =============================================================================

class TestBestWorstZone:
    def test_no_data(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert analyzer.get_best_zone(1) is None
        assert analyzer.get_worst_zone(1) is None

    def test_insufficient_attempts(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        # 기본 min_attempts=5, 3개만 기록
        for _ in range(3):
            analyzer.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        assert analyzer.get_best_zone(1) is None

    def test_best_zone(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        cfg = ZoneEfficiencyConfig(min_attempts_for_ranking=2)
        a = ZoneEfficiencyAnalyzer(cfg)
        # RA: PPP 2.0 (2/2 made)
        a.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        a.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        # 3점: PPP 1.5 (1/2 made)
        a.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=True, points=3)
        a.record_shot(1, ShotZone.ABOVE_BREAK_CENTER, made=False, points=0)
        assert a.get_best_zone(1) == ShotZone.RESTRICTED_AREA.value

    def test_worst_zone(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        cfg = ZoneEfficiencyConfig(min_attempts_for_ranking=2)
        a = ZoneEfficiencyAnalyzer(cfg)
        a.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        a.record_shot(1, ShotZone.RESTRICTED_AREA, made=True, points=2)
        a.record_shot(1, ShotZone.MID_RANGE_CENTER, made=False, points=0)
        a.record_shot(1, ShotZone.MID_RANGE_CENTER, made=False, points=0)
        assert a.get_worst_zone(1) == ShotZone.MID_RANGE_CENTER.value


# =============================================================================
# 유틸리티
# =============================================================================

class TestZoneEffUtility:
    def test_get_stats(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA)
        analyzer.record_shot(2, ShotZone.MID_RANGE_LEFT)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 2
        assert stats["entities_tracked"] == 2

    def test_reset(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        analyzer.record_shot(1, ShotZone.RESTRICTED_AREA)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: ZoneEfficiencyAnalyzer) -> None:
        assert "ZoneEfficiencyAnalyzer" in repr(analyzer)
