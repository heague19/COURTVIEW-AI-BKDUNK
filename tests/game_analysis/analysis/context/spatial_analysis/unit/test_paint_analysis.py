# -*- coding: utf-8 -*-
"""PaintAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.spatial_analysis.paint_analysis import (
    PaintAnalyzer,
    PaintAnalysisConfig,
)


class TestPaintInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = PaintAnalyzer()
        assert analyzer.name == "PaintAnalyzer"
        assert analyzer.total_touches == 0

    def test_custom_config(self) -> None:
        cfg = PaintAnalysisConfig(max_records=100)
        analyzer = PaintAnalyzer(config=cfg)
        assert analyzer._config.max_records == 100


class TestRecordPaintTouch:
    """페인트 터치 기록 테스트."""

    def test_record_drive(self) -> None:
        analyzer = PaintAnalyzer()
        ev = analyzer.record_paint_touch(
            player_id=10, team_id=1,
            entry_type="drive", outcome="shot_made", points=2,
        )
        assert ev.entry_type == "drive"
        assert analyzer.total_touches == 1

    def test_record_multiple(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, entry_type="post_up")
        analyzer.record_paint_touch(player_id=20, team_id=1, entry_type="cut")
        assert analyzer.total_touches == 2

    def test_memory_guard(self) -> None:
        cfg = PaintAnalysisConfig(max_records=5)
        analyzer = PaintAnalyzer(config=cfg)
        for i in range(8):
            analyzer.record_paint_touch(player_id=1, team_id=1)
        assert analyzer.total_touches == 5


class TestPlayerPaintSummary:
    """선수별 페인트 요약 테스트."""

    def test_empty_player(self) -> None:
        analyzer = PaintAnalyzer()
        summary = analyzer.get_player_paint_summary(99)
        assert summary["touches"] == 0
        assert summary["fg_pct"] == 0.0

    def test_fg_pct(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="shot_made", points=2)
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="shot_made", points=2)
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="shot_missed")
        summary = analyzer.get_player_paint_summary(10)
        assert summary["fg_pct"] == pytest.approx(200.0 / 3.0)
        assert summary["touches"] == 3

    def test_ppp(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="shot_made", points=2)
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="no_shot")
        summary = analyzer.get_player_paint_summary(10)
        # 2 points / 2 touches = 1.0
        assert summary["ppp"] == pytest.approx(1.0)

    def test_fouls_and_turnovers(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="foul_drawn")
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="turnover")
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="foul_drawn")
        summary = analyzer.get_player_paint_summary(10)
        assert summary["fouls_drawn"] == 2
        assert summary["turnovers"] == 1


class TestEntryTypeDistribution:
    """진입 경로 분포 테스트."""

    def test_distribution(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, entry_type="drive")
        analyzer.record_paint_touch(player_id=10, team_id=1, entry_type="drive")
        analyzer.record_paint_touch(player_id=10, team_id=1, entry_type="cut")
        analyzer.record_paint_touch(player_id=10, team_id=1, entry_type="post_up")
        dist = analyzer.get_entry_type_distribution(10)
        assert dist["drive"] == 2
        assert dist["cut"] == 1
        assert dist["post_up"] == 1

    def test_empty_distribution(self) -> None:
        analyzer = PaintAnalyzer()
        assert analyzer.get_entry_type_distribution(99) == {}


class TestTeamPaintSummary:
    """팀별 페인트 요약 테스트."""

    def test_team_summary(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1, outcome="shot_made", points=2)
        analyzer.record_paint_touch(player_id=20, team_id=1, outcome="shot_missed")
        analyzer.record_paint_touch(player_id=30, team_id=1, outcome="foul_drawn")
        summary = analyzer.get_team_paint_summary(1)
        assert summary["touches"] == 3
        assert summary["fg_pct"] == pytest.approx(50.0)
        assert summary["points"] == 2
        assert summary["fouls_drawn"] == 1

    def test_empty_team(self) -> None:
        analyzer = PaintAnalyzer()
        summary = analyzer.get_team_paint_summary(99)
        assert summary["touches"] == 0


class TestPaintDominance:
    """페인트 지배력 테스트."""

    def test_equal_dominance(self) -> None:
        analyzer = PaintAnalyzer()
        for _ in range(5):
            analyzer.record_paint_touch(player_id=10, team_id=1)
            analyzer.record_paint_touch(player_id=20, team_id=2)
        dom = analyzer.get_paint_dominance(1, 2)
        assert dom == pytest.approx(50.0)

    def test_dominant(self) -> None:
        analyzer = PaintAnalyzer()
        for _ in range(8):
            analyzer.record_paint_touch(player_id=10, team_id=1)
        for _ in range(2):
            analyzer.record_paint_touch(player_id=20, team_id=2)
        dom = analyzer.get_paint_dominance(1, 2)
        assert dom == pytest.approx(80.0)

    def test_no_data(self) -> None:
        analyzer = PaintAnalyzer()
        assert analyzer.get_paint_dominance(1, 2) == 0.0


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1)
        stats = analyzer.get_stats()
        assert stats["total_touches"] == 1
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = PaintAnalyzer()
        analyzer.record_paint_touch(player_id=10, team_id=1)
        analyzer.reset()
        assert analyzer.total_touches == 0

    def test_repr(self) -> None:
        analyzer = PaintAnalyzer()
        assert "PaintAnalyzer" in repr(analyzer)
