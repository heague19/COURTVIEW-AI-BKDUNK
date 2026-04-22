# -*- coding: utf-8 -*-
"""FloorSpacingAnalyzer 단위 테스트."""

from __future__ import annotations

import math

import pytest

from game_analysis.analysis.context.spatial_analysis.floor_spacing import (
    FloorSpacingAnalyzer,
    FloorSpacingConfig,
)
from shared.dto.tactical_dto import SpacingData


class TestFloorSpacingInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        assert analyzer.name == "FloorSpacingAnalyzer"
        assert analyzer.total_snapshots == 0

    def test_custom_config(self) -> None:
        cfg = FloorSpacingConfig(max_records=50)
        analyzer = FloorSpacingAnalyzer(config=cfg)
        assert analyzer._config.max_records == 50


class TestRecordSpacing:
    """스페이싱 기록 테스트."""

    def test_record_single(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        # 5인 넓게 배치
        positions = [
            (0.0, 0.0), (15.0, 0.0), (0.0, 14.0),
            (15.0, 14.0), (7.5, 7.0),
        ]
        snap = analyzer.record_spacing(
            possession_id=1, team_id=1, positions=positions,
        )
        assert snap.avg_distance_m > 0
        assert snap.court_utilization > 0
        assert analyzer.total_snapshots == 1

    def test_memory_guard(self) -> None:
        cfg = FloorSpacingConfig(max_records=3)
        analyzer = FloorSpacingAnalyzer(config=cfg)
        positions = [(1.0, 1.0), (5.0, 5.0), (10.0, 10.0), (2.0, 8.0), (8.0, 2.0)]
        for i in range(5):
            analyzer.record_spacing(possession_id=i, team_id=1, positions=positions)
        assert analyzer.total_snapshots == 3


class TestAvgPairwiseDistance:
    """평균 쌍거리 계산 테스트."""

    def test_two_points(self) -> None:
        dist = FloorSpacingAnalyzer._calc_avg_pairwise_distance(
            [(0.0, 0.0), (3.0, 4.0)]
        )
        assert dist == pytest.approx(5.0)

    def test_single_point(self) -> None:
        dist = FloorSpacingAnalyzer._calc_avg_pairwise_distance([(1.0, 1.0)])
        assert dist == 0.0

    def test_empty(self) -> None:
        dist = FloorSpacingAnalyzer._calc_avg_pairwise_distance([])
        assert dist == 0.0


class TestCourtUtilization:
    """코트 활용률 테스트."""

    def test_wide_spread(self) -> None:
        # 코트 4모서리 + 중앙 → 높은 활용률
        positions = [
            (0.0, 0.0), (15.0, 0.0), (0.0, 14.0),
            (15.0, 14.0), (7.5, 7.0),
        ]
        util = FloorSpacingAnalyzer._calc_court_utilization(positions)
        assert util > 0.9  # 거의 전체 코트

    def test_clustered(self) -> None:
        # 좁은 영역에 밀집
        positions = [
            (7.0, 7.0), (7.5, 7.0), (7.0, 7.5),
            (7.5, 7.5), (7.25, 7.25),
        ]
        util = FloorSpacingAnalyzer._calc_court_utilization(positions)
        assert util < 0.01

    def test_less_than_3_points(self) -> None:
        util = FloorSpacingAnalyzer._calc_court_utilization([(1.0, 1.0), (2.0, 2.0)])
        assert util == 0.0


class TestTeamSpacingData:
    """팀별 SpacingData DTO 테스트."""

    def test_empty_team(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        data = analyzer.get_team_spacing_data(99)
        assert isinstance(data, SpacingData)
        assert data.avg_player_spacing == 0.0

    def test_average_across_snapshots(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        # 2회 기록
        pos1 = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0), (5.0, 5.0)]
        pos2 = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), (5.0, 5.0)]
        analyzer.record_spacing(possession_id=1, team_id=1, positions=pos1)
        analyzer.record_spacing(possession_id=2, team_id=1, positions=pos2)
        data = analyzer.get_team_spacing_data(1)
        assert data.avg_player_spacing > 0
        assert data.court_utilization_pct > 0


class TestQualityDistribution:
    """스페이싱 등급 분포 테스트."""

    def test_distribution(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        # 넓은 배치 → excellent/good
        wide = [(0.0, 0.0), (15.0, 0.0), (0.0, 14.0), (15.0, 14.0), (7.5, 7.0)]
        analyzer.record_spacing(possession_id=1, team_id=1, positions=wide)
        dist = analyzer.get_quality_distribution(1)
        assert len(dist) > 0


class TestDriveLaneOpenness:
    """드라이브 레인 개방도 테스트."""

    def test_open_lanes(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        # 공격: 중앙, 수비: 코트 양쪽 끝 사이드 (레인 밖)
        offense = [(7.5, 10.0)]
        defense = [(0.5, 5.0), (14.5, 5.0)]
        rim = (7.5, 1.575)
        openness = analyzer.calc_drive_lane_openness(offense, defense, rim)
        assert openness == pytest.approx(100.0)

    def test_blocked_lanes(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        # 공격: 중앙, 수비: 림 방향 경로에 정확히 위치
        offense = [(7.5, 10.0)]
        defense = [(7.5, 5.0)]
        rim = (7.5, 1.575)
        openness = analyzer.calc_drive_lane_openness(offense, defense, rim)
        assert openness == pytest.approx(0.0)

    def test_empty_positions(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        assert analyzer.calc_drive_lane_openness([], [(1.0, 1.0)]) == 0.0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        pos = [(1.0, 1.0), (5.0, 5.0), (10.0, 10.0), (2.0, 8.0), (8.0, 2.0)]
        analyzer.record_spacing(possession_id=1, team_id=1, positions=pos)
        stats = analyzer.get_stats()
        assert stats["total_snapshots"] == 1
        assert stats["teams_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        pos = [(1.0, 1.0), (5.0, 5.0), (10.0, 10.0), (2.0, 8.0), (8.0, 2.0)]
        analyzer.record_spacing(possession_id=1, team_id=1, positions=pos)
        analyzer.reset()
        assert analyzer.total_snapshots == 0

    def test_repr(self) -> None:
        analyzer = FloorSpacingAnalyzer()
        assert "FloorSpacingAnalyzer" in repr(analyzer)
