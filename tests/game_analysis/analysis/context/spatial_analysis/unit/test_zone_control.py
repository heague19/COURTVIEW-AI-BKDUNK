# -*- coding: utf-8 -*-
"""ZoneControlAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.spatial_analysis.zone_control import (
    ZoneControlAnalyzer,
    ZoneControlConfig,
)


class TestZoneControlInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = ZoneControlAnalyzer()
        assert analyzer.name == "ZoneControlAnalyzer"
        assert analyzer.total_events == 0

    def test_custom_config(self) -> None:
        cfg = ZoneControlConfig(max_records=100)
        analyzer = ZoneControlAnalyzer(config=cfg)
        assert analyzer._config.max_records == 100


class TestRecordEvent:
    """이벤트 기록 테스트."""

    def test_shot_made(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        assert analyzer.total_events == 1

    def test_shot_missed(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="mid_range", event_type="shot_missed")
        assert analyzer.total_events == 1

    def test_memory_guard(self) -> None:
        cfg = ZoneControlConfig(max_records=5)
        analyzer = ZoneControlAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_event(team_id=1, zone="paint", event_type="possession")
        assert analyzer.total_events == 5


class TestZoneFgPct:
    """존별 FG% 테스트."""

    def test_fg_pct(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_missed")
        fg = analyzer.get_zone_fg_pct(1, "paint")
        assert fg == pytest.approx(200.0 / 3.0)

    def test_fg_pct_no_attempts(self) -> None:
        analyzer = ZoneControlAnalyzer()
        assert analyzer.get_zone_fg_pct(1, "paint") == 0.0


class TestZonePPP:
    """존별 PPP 테스트."""

    def test_ppp(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="three_point", event_type="possession")
        analyzer.record_event(team_id=1, zone="three_point", event_type="possession")
        analyzer.record_event(team_id=1, zone="three_point", event_type="shot_made", points=3)
        ppp = analyzer.get_zone_ppp(1, "three_point")
        # 3 points / 2 possessions = 1.5
        assert ppp == pytest.approx(1.5)

    def test_ppp_no_possessions(self) -> None:
        analyzer = ZoneControlAnalyzer()
        assert analyzer.get_zone_ppp(1, "paint") == 0.0


class TestZoneSummary:
    """존 종합 요약 테스트."""

    def test_summary_all_zones(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        analyzer.record_event(team_id=1, zone="mid_range", event_type="shot_missed")
        analyzer.record_event(team_id=1, zone="three_point", event_type="shot_made", points=3)
        summary = analyzer.get_zone_summary(1)
        assert "paint" in summary
        assert "mid_range" in summary
        assert "three_point" in summary
        assert summary["paint"]["made"] == 1.0
        assert summary["mid_range"]["attempts"] == 1.0
        assert summary["three_point"]["fg_pct"] == pytest.approx(100.0)

    def test_empty_team_summary(self) -> None:
        analyzer = ZoneControlAnalyzer()
        summary = analyzer.get_zone_summary(99)
        assert all(v["fg_pct"] == 0.0 for v in summary.values())


class TestControlRatio:
    """존 지배력 비율 테스트."""

    def test_equal_control(self) -> None:
        analyzer = ZoneControlAnalyzer()
        for _ in range(5):
            analyzer.record_event(team_id=1, zone="paint", event_type="possession")
            analyzer.record_event(team_id=2, zone="paint", event_type="possession")
        ratio = analyzer.get_control_ratio(1, 2, "paint")
        assert ratio == pytest.approx(50.0)

    def test_dominant_control(self) -> None:
        analyzer = ZoneControlAnalyzer()
        for _ in range(8):
            analyzer.record_event(team_id=1, zone="paint", event_type="possession")
        for _ in range(2):
            analyzer.record_event(team_id=2, zone="paint", event_type="possession")
        ratio = analyzer.get_control_ratio(1, 2, "paint")
        assert ratio == pytest.approx(80.0)

    def test_no_data(self) -> None:
        analyzer = ZoneControlAnalyzer()
        assert analyzer.get_control_ratio(1, 2, "paint") == 0.0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        stats = analyzer.get_stats()
        assert stats["total_events"] == 1

    def test_reset(self) -> None:
        analyzer = ZoneControlAnalyzer()
        analyzer.record_event(team_id=1, zone="paint", event_type="shot_made", points=2)
        analyzer.reset()
        assert analyzer.total_events == 0

    def test_repr(self) -> None:
        analyzer = ZoneControlAnalyzer()
        assert "ZoneControlAnalyzer" in repr(analyzer)
