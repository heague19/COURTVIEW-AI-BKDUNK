# -*- coding: utf-8 -*-
"""ContestAnalyzer 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.matchup_analysis.contest_analyzer import (
    ContestAnalyzer,
    ContestAnalyzerConfig,
    ContestEventInput,
)


def _evt(**kwargs) -> ContestEventInput:
    defaults = dict(
        defender_tracking_id=1, shooter_tracking_id=10,
        contest_distance_m=0.5, shot_made=False, shot_points=2,
    )
    defaults.update(kwargs)
    return ContestEventInput(**defaults)


class TestContestAnalyzer:
    """ContestAnalyzer 단위 테스트."""

    def test_init_default(self):
        ca = ContestAnalyzer()
        assert ca.name == "ContestAnalyzer"

    def test_record_single(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(min_contests_for_report=1))
        ca.record_contest(_evt(contest_distance_m=0.5, shot_made=False))
        result = ca.get_defender_result(1)
        assert result is not None
        assert result.tight_contests == 1

    def test_tight_contest_classification(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(
            tight_distance_m=0.9, min_contests_for_report=1,
        ))
        ca.record_contest(_evt(contest_distance_m=0.5))
        ca.record_contest(_evt(contest_distance_m=0.8))
        result = ca.get_defender_result(1)
        assert result.tight_contests == 2

    def test_moderate_contest_classification(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(
            tight_distance_m=0.9, moderate_distance_m=1.8,
            min_contests_for_report=1,
        ))
        ca.record_contest(_evt(contest_distance_m=1.2))
        ca.record_contest(_evt(contest_distance_m=1.5))
        result = ca.get_defender_result(1)
        assert result.moderate_contests == 2

    def test_open_shot_classification(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(
            moderate_distance_m=1.8, min_contests_for_report=1,
        ))
        ca.record_contest(_evt(contest_distance_m=2.5))
        result = ca.get_defender_result(1)
        assert result.open_allowed == 1

    def test_fg_pct_by_distance(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(
            tight_distance_m=0.9, moderate_distance_m=1.8,
            min_contests_for_report=1,
        ))
        # tight: 1/3 = 33%
        ca.record_contest(_evt(contest_distance_m=0.5, shot_made=True))
        ca.record_contest(_evt(contest_distance_m=0.5, shot_made=False))
        ca.record_contest(_evt(contest_distance_m=0.5, shot_made=False))
        # open: 2/2 = 100%
        ca.record_contest(_evt(contest_distance_m=2.0, shot_made=True))
        ca.record_contest(_evt(contest_distance_m=2.0, shot_made=True))
        result = ca.get_defender_result(1)
        assert result.fg_pct_when_tight == pytest.approx(0.333, abs=0.001)
        assert result.fg_pct_when_open == 1.0

    def test_contest_grade_high(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(min_contests_for_report=1))
        # 모두 밀착 + 모두 실패 → 높은 등급
        for _ in range(10):
            ca.record_contest(_evt(contest_distance_m=0.5, shot_made=False))
        result = ca.get_defender_result(1)
        assert result.contest_grade > 70.0

    def test_contest_grade_low(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(min_contests_for_report=1))
        # 모두 오픈 + 모두 성공 → 낮은 등급
        for _ in range(10):
            ca.record_contest(_evt(contest_distance_m=3.0, shot_made=True))
        result = ca.get_defender_result(1)
        assert result.contest_grade < 30.0

    def test_multiple_defenders(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(min_contests_for_report=1))
        ca.record_contest(_evt(defender_tracking_id=1))
        ca.record_contest(_evt(defender_tracking_id=2))
        ca.record_contest(_evt(defender_tracking_id=3))
        results = ca.get_all_defender_results()
        assert len(results) == 3

    def test_summary(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(
            tight_distance_m=0.9, moderate_distance_m=1.8,
        ))
        # 3 tight + 2 open = 5 total
        for _ in range(3):
            ca.record_contest(_evt(contest_distance_m=0.5, shot_made=False))
        for _ in range(2):
            ca.record_contest(_evt(contest_distance_m=2.5, shot_made=True))
        summary = ca.get_summary()
        assert summary.total_shots_faced == 5
        assert summary.contested_rate == 0.6  # 3/5
        assert summary.opponent_fg_pct_open == 1.0

    def test_min_contests_filter(self):
        ca = ContestAnalyzer(config=ContestAnalyzerConfig(min_contests_for_report=5))
        ca.record_contest(_evt())
        ca.record_contest(_evt())
        result = ca.get_defender_result(1)
        assert result is None

    def test_reset(self):
        ca = ContestAnalyzer()
        ca.record_contest(_evt())
        ca.record_contest(_evt())
        ca.reset()
        assert len(ca.get_all_defender_results()) == 0
        assert ca.get_summary().total_shots_faced == 0
