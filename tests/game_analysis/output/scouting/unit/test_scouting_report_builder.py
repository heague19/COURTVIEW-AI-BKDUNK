# -*- coding: utf-8 -*-
"""ScoutingReportBuilder 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.scouting.scouting_report_builder import (
    ScoutingReportBuilder,
    ScoutingReportConfig,
    ScoutingReport,
)
from shared.dto.scouting_dto import (
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
    HeadToHeadRecord,
    KeyPlayerInfo,
    DefensiveGap,
    RecentGameResult,
)


def _profile(**kwargs) -> OpponentProfile:
    defaults = dict(
        team_id="T001", team_name="Eagles", games_analyzed=10,
        offensive_rating=115.0, defensive_rating=105.0, pace=78.0,
        primary_offense="pick_and_roll", primary_defense="man_to_man",
        key_players=[KeyPlayerInfo(tracking_id=7, name="Star", role="PG", ppg=22.0, usage_pct=0.30)],
        strengths=["높은 공격 효율"], weaknesses=["높은 턴오버"],
    )
    defaults.update(kwargs)
    return OpponentProfile(**defaults)


def _tendency(**kwargs) -> TendencyReport:
    defaults = dict(
        team_id="T001",
        shot_zone_preferences={"paint_center": 30.0, "three_left_wing": 20.0},
        play_type_preferences={"pick_and_roll": 40.0},
        transition_tendency=25.0,
        three_point_rate=0.38,
        paint_attack_rate=0.30,
        right_side_preference=0.55,
        left_side_preference=0.45,
    )
    defaults.update(kwargs)
    return TendencyReport(**defaults)


def _weakness(**kwargs) -> WeaknessReport:
    defaults = dict(
        team_id="T001",
        defensive_gaps=[DefensiveGap(zone="paint_center", gap_severity=0.75, exploitable_play="pick_and_roll")],
        transition_weakness_score=60.0,
        rebounding_weakness="offensive",
        three_point_defense_rating=40.0,
    )
    defaults.update(kwargs)
    return WeaknessReport(**defaults)


def _h2h(**kwargs) -> HeadToHeadRecord:
    defaults = dict(
        opponent_id="T001", total_games=5, wins=3, losses=2,
        avg_point_differential=4.5,
        successful_strategies=["pick_and_roll"],
        failed_strategies=["isolation"],
        recent_results=[RecentGameResult(date="2026-03-10", score="85-78", outcome="win")],
    )
    defaults.update(kwargs)
    return HeadToHeadRecord(**defaults)


class TestScoutingReportBuilder:
    """ScoutingReportBuilder 단위 테스트."""

    def test_init_default(self):
        rb = ScoutingReportBuilder()
        assert rb.name == "ScoutingReportBuilder"

    def test_build_empty(self):
        rb = ScoutingReportBuilder()
        report = rb.build()
        assert report.team_id == ""
        assert report.profile is None

    def test_set_profile(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        report = rb.build()
        assert report.team_id == "T001"
        assert report.team_name == "Eagles"
        assert report.profile is not None

    def test_set_all_components(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_tendency(_tendency())
        rb.set_weakness(_weakness())
        rb.set_head_to_head(_h2h())
        report = rb.build()
        assert report.profile is not None
        assert report.tendency is not None
        assert report.weakness is not None
        assert report.head_to_head is not None

    def test_key_points_ko_generated(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_weakness(_weakness())
        rb.set_head_to_head(_h2h())
        report = rb.build()
        assert len(report.key_points_ko) > 0
        # 강점/수비갭/전적 포인트 포함
        all_text = " ".join(report.key_points_ko)
        assert "강점" in all_text or "공격 효율" in all_text

    def test_key_points_en_generated(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_head_to_head(_h2h())
        report = rb.build()
        assert len(report.key_points_en) > 0

    def test_key_points_max_limit(self):
        rb = ScoutingReportBuilder(config=ScoutingReportConfig(max_key_points=3))
        rb.set_profile(_profile(
            strengths=["a", "b", "c", "d", "e"],
            weaknesses=["x", "y", "z"],
        ))
        rb.set_weakness(_weakness())
        rb.set_head_to_head(_h2h())
        report = rb.build()
        assert len(report.key_points_ko) <= 3

    def test_summary_ko_contains_team_name(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        report = rb.build()
        assert "Eagles" in report.summary_ko

    def test_summary_en_generated(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        report = rb.build()
        assert "Eagles" in report.summary_en
        assert "ORTG" in report.summary_en

    def test_build_json(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_tendency(_tendency())
        rb.set_weakness(_weakness())
        rb.set_head_to_head(_h2h())
        result = rb.build_json()
        assert result["team_id"] == "T001"
        assert "profile" in result
        assert "tendency" in result
        assert "weakness" in result
        assert "head_to_head" in result
        assert "key_points_ko" in result

    def test_event_history(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_tendency(_tendency())
        assert len(rb.get_event_history()) == 2

    def test_reset(self):
        rb = ScoutingReportBuilder()
        rb.set_profile(_profile())
        rb.set_tendency(_tendency())
        rb.set_weakness(_weakness())
        rb.set_head_to_head(_h2h())
        rb.reset()
        report = rb.build()
        assert report.team_id == ""
        assert report.profile is None
        assert len(rb.get_event_history()) == 0
