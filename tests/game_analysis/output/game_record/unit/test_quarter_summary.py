# -*- coding: utf-8 -*-
"""QuarterSummaryGenerator 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.game_record.quarter_summary import (
    QuarterSummaryGenerator,
    QuarterSummaryConfig,
    QuarterStatInput,
    QuarterResult,
    HalfComparison,
    QuarterTrend,
)


def _qstat(**kwargs) -> QuarterStatInput:
    defaults = dict(
        team_id="home", quarter=1, points=25,
        field_goals_made=10, field_goals_attempted=20,
        three_pointers_made=3, three_pointers_attempted=8,
        free_throws_made=2, free_throws_attempted=3,
        rebounds=12, assists=6, turnovers=3,
        steals=2, blocks=1, fouls=4,
        player_points={7: 10, 11: 8, 23: 7},
        largest_run=8, confidence=0.85,
    )
    defaults.update(kwargs)
    return QuarterStatInput(**defaults)


class TestQuarterSummaryGenerator:
    """QuarterSummaryGenerator 단위 테스트."""

    def test_init_default(self):
        qsg = QuarterSummaryGenerator()
        assert qsg.name == "QuarterSummaryGenerator"

    def test_submit_and_get_quarter(self):
        qsg = QuarterSummaryGenerator()
        qsg.submit_quarter_stats(_qstat(quarter=1, points=25))
        result = qsg.get_quarter_summary("home", 1)
        assert result is not None
        assert result.points == 25
        assert result.quarter == 1

    def test_shooting_percentages(self):
        qsg = QuarterSummaryGenerator()
        qsg.submit_quarter_stats(_qstat(
            field_goals_made=8, field_goals_attempted=16,
            three_pointers_made=3, three_pointers_attempted=6,
        ))
        result = qsg.get_quarter_summary("home", 1)
        assert result.fg_percentage == 50.0
        assert result.three_pt_percentage == 50.0

    def test_top_scorer(self):
        qsg = QuarterSummaryGenerator()
        qsg.submit_quarter_stats(_qstat(player_points={7: 12, 11: 8}))
        result = qsg.get_quarter_summary("home", 1)
        assert result.top_scorer_id == 7
        assert result.top_scorer_points == 12

    def test_all_quarter_summaries(self):
        qsg = QuarterSummaryGenerator()
        for q in [1, 2, 3, 4]:
            qsg.submit_quarter_stats(_qstat(quarter=q, points=20 + q))
        results = qsg.get_all_quarter_summaries("home")
        assert len(results) == 4
        assert results[0].quarter == 1
        assert results[3].quarter == 4

    def test_half_comparison_improved(self):
        qsg = QuarterSummaryGenerator()
        # 전반: 1Q=15, 2Q=18 → 33
        qsg.submit_quarter_stats(_qstat(quarter=1, points=15,
                                         field_goals_made=5, field_goals_attempted=15))
        qsg.submit_quarter_stats(_qstat(quarter=2, points=18,
                                         field_goals_made=6, field_goals_attempted=15))
        # 후반: 3Q=25, 4Q=28 → 53
        qsg.submit_quarter_stats(_qstat(quarter=3, points=25,
                                         field_goals_made=10, field_goals_attempted=15))
        qsg.submit_quarter_stats(_qstat(quarter=4, points=28,
                                         field_goals_made=11, field_goals_attempted=15))
        hc = qsg.get_half_comparison("home")
        assert hc.first_half_points == 33
        assert hc.second_half_points == 53
        assert hc.points_trend == "improved"

    def test_half_comparison_declined(self):
        qsg = QuarterSummaryGenerator()
        qsg.submit_quarter_stats(_qstat(quarter=1, points=30,
                                         field_goals_made=12, field_goals_attempted=20))
        qsg.submit_quarter_stats(_qstat(quarter=2, points=28,
                                         field_goals_made=10, field_goals_attempted=20))
        qsg.submit_quarter_stats(_qstat(quarter=3, points=15,
                                         field_goals_made=5, field_goals_attempted=20))
        qsg.submit_quarter_stats(_qstat(quarter=4, points=12,
                                         field_goals_made=4, field_goals_attempted=20))
        hc = qsg.get_half_comparison("home")
        assert hc.points_trend == "declined"

    def test_quarter_trend_improving(self):
        qsg = QuarterSummaryGenerator()
        for q, pts in [(1, 15), (2, 18), (3, 22), (4, 28)]:
            qsg.submit_quarter_stats(_qstat(quarter=q, points=pts))
        trend = qsg.get_quarter_trend("home")
        assert trend.points_trend == "improving"
        assert trend.best_quarter == 4
        assert trend.worst_quarter == 1

    def test_quarter_trend_declining(self):
        qsg = QuarterSummaryGenerator()
        for q, pts in [(1, 30), (2, 25), (3, 20), (4, 15)]:
            qsg.submit_quarter_stats(_qstat(quarter=q, points=pts))
        trend = qsg.get_quarter_trend("home")
        assert trend.points_trend == "declining"

    def test_quarter_trend_stable(self):
        qsg = QuarterSummaryGenerator()
        for q, pts in [(1, 20), (2, 21), (3, 20), (4, 21)]:
            qsg.submit_quarter_stats(_qstat(quarter=q, points=pts))
        trend = qsg.get_quarter_trend("home")
        assert trend.points_trend == "stable"

    def test_low_confidence_rejected(self):
        qsg = QuarterSummaryGenerator()
        result = qsg.submit_quarter_stats(_qstat(confidence=0.1))
        assert result is False

    def test_reset(self):
        qsg = QuarterSummaryGenerator()
        qsg.submit_quarter_stats(_qstat())
        qsg.reset()
        assert qsg.get_quarter_summary("home", 1) is None
        assert len(qsg.get_event_history()) == 0
