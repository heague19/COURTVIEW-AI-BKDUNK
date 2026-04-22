# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/shot_location/shot_zone_mapper.py
설명: ShotZoneMapper 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from shared.constants.court_constants import BASKET_CENTER_FROM_ENDLINE_M
from shared.constants.stats_constants import ShotZone

from game_analysis.output.shot_location.shot_zone_mapper import (
    LeagueStandard,
    ShotZoneMapper,
    ShotZoneMapperConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def mapper() -> ShotZoneMapper:
    return ShotZoneMapper()


@pytest.fixture()
def small_mapper() -> ShotZoneMapper:
    return ShotZoneMapper(ShotZoneMapperConfig(max_records=5))


# =============================================================================
# 초기화
# =============================================================================

class TestShotZoneMapperInit:
    def test_default_config(self, mapper: ShotZoneMapper) -> None:
        assert mapper.total_records == 0
        assert mapper.name == "ShotZoneMapper"

    def test_custom_config(self) -> None:
        cfg = ShotZoneMapperConfig(max_records=100, league=LeagueStandard.NBA)
        m = ShotZoneMapper(cfg)
        assert m.total_records == 0

    def test_league_standard_enum(self) -> None:
        assert LeagueStandard.FIBA.value == "fiba"
        assert LeagueStandard.NBA.value == "nba"


# =============================================================================
# 존 분류
# =============================================================================

class TestClassifyZone:
    def test_restricted_area(self, mapper: ShotZoneMapper) -> None:
        # 림 바로 아래 (0, basket_y)
        zone = mapper.classify_zone(0.0, BASKET_CENTER_FROM_ENDLINE_M)
        assert zone == ShotZone.RESTRICTED_AREA

    def test_restricted_area_near_rim(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.classify_zone(0.5, BASKET_CENTER_FROM_ENDLINE_M + 0.5)
        assert zone == ShotZone.RESTRICTED_AREA

    def test_paint_non_ra(self, mapper: ShotZoneMapper) -> None:
        # 페인트 안, RA 밖 (y ~3.5m, x ~1.0m)
        zone = mapper.classify_zone(1.0, 3.5)
        assert zone == ShotZone.PAINT_NON_RA

    def test_midrange_center(self, mapper: ShotZoneMapper) -> None:
        # 미드레인지 중앙 (자유투 라인 근처, 3점 라인 안)
        zone = mapper.classify_zone(0.0, 6.5)
        assert zone == ShotZone.MID_RANGE_CENTER

    def test_midrange_left(self, mapper: ShotZoneMapper) -> None:
        # 미드레인지 좌측 (x<0, 3점 안)
        zone = mapper.classify_zone(-4.0, 5.0)
        assert zone == ShotZone.MID_RANGE_LEFT

    def test_midrange_right(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.classify_zone(4.0, 5.0)
        assert zone == ShotZone.MID_RANGE_RIGHT

    def test_corner_three_left(self, mapper: ShotZoneMapper) -> None:
        # 좌측 코너 3점 (x<0, y < basket_y + corner_break, distance >= 6.75)
        zone = mapper.classify_zone(-7.0, 1.5)
        assert zone == ShotZone.CORNER_THREE_LEFT

    def test_corner_three_right(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.classify_zone(7.0, 1.5)
        assert zone == ShotZone.CORNER_THREE_RIGHT

    def test_above_break_center(self, mapper: ShotZoneMapper) -> None:
        # 탑 3점 중앙 (x~0, y 높음, distance >= 6.75)
        zone = mapper.classify_zone(0.0, 9.0)
        assert zone == ShotZone.ABOVE_BREAK_CENTER

    def test_above_break_left(self, mapper: ShotZoneMapper) -> None:
        # 좌측 윙 3점
        zone = mapper.classify_zone(-5.0, 9.0)
        assert zone == ShotZone.ABOVE_BREAK_LEFT

    def test_above_break_right(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.classify_zone(5.0, 9.0)
        assert zone == ShotZone.ABOVE_BREAK_RIGHT

    def test_backcourt(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.classify_zone(0.0, 14.5)
        assert zone == ShotZone.BACKCOURT


# =============================================================================
# 거리/각도
# =============================================================================

class TestDistanceAngle:
    def test_at_rim(self, mapper: ShotZoneMapper) -> None:
        dist, angle = mapper.get_distance_and_angle(0.0, BASKET_CENTER_FROM_ENDLINE_M)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_distance_positive(self, mapper: ShotZoneMapper) -> None:
        dist, angle = mapper.get_distance_and_angle(3.0, 5.0)
        assert dist > 0.0
        assert 0 <= angle <= 90


# =============================================================================
# 기록
# =============================================================================

class TestRecording:
    def test_record_shot(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.record_shot(1, 0.0, BASKET_CENTER_FROM_ENDLINE_M, made=True)
        assert zone == ShotZone.RESTRICTED_AREA
        assert mapper.total_records == 1

    def test_max_records_limit(self, small_mapper: ShotZoneMapper) -> None:
        for _ in range(10):
            small_mapper.record_shot(1, 0.0, 5.0)
        assert small_mapper.total_records == 5

    def test_record_returns_zone(self, mapper: ShotZoneMapper) -> None:
        zone = mapper.record_shot(1, 0.0, 14.5)
        assert zone == ShotZone.BACKCOURT


# =============================================================================
# 조회
# =============================================================================

class TestQueries:
    def test_shots_by_zone(self, mapper: ShotZoneMapper) -> None:
        mapper.record_shot(1, 0.0, BASKET_CENTER_FROM_ENDLINE_M)
        mapper.record_shot(1, 0.0, BASKET_CENTER_FROM_ENDLINE_M)
        mapper.record_shot(1, 0.0, 9.0)  # 3점
        assert mapper.get_shots_by_zone(1, ShotZone.RESTRICTED_AREA) == 2

    def test_zone_distribution(self, mapper: ShotZoneMapper) -> None:
        mapper.record_shot(1, 0.0, BASKET_CENTER_FROM_ENDLINE_M)
        mapper.record_shot(1, 0.0, 9.0)
        dist = mapper.get_zone_distribution(1)
        assert len(dist) == 2
        assert ShotZone.RESTRICTED_AREA.value in dist

    def test_average_distance(self, mapper: ShotZoneMapper) -> None:
        mapper.record_shot(1, 0.0, BASKET_CENTER_FROM_ENDLINE_M)  # dist~0
        mapper.record_shot(1, 0.0, 9.0)  # dist~7.4
        avg = mapper.get_average_distance(1)
        assert avg > 0.0

    def test_average_distance_no_data(self, mapper: ShotZoneMapper) -> None:
        assert mapper.get_average_distance(1) == 0.0


# =============================================================================
# 유틸리티
# =============================================================================

class TestMapperUtility:
    def test_get_stats(self, mapper: ShotZoneMapper) -> None:
        mapper.record_shot(1, 0.0, 5.0)
        stats = mapper.get_stats()
        assert stats["total_records"] == 1
        assert stats["league"] == "fiba"

    def test_reset(self, mapper: ShotZoneMapper) -> None:
        mapper.record_shot(1, 0.0, 5.0)
        mapper.reset()
        assert mapper.total_records == 0

    def test_repr(self, mapper: ShotZoneMapper) -> None:
        assert "ShotZoneMapper" in repr(mapper)
