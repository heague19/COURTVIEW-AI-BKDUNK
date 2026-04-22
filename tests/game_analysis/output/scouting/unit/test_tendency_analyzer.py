# -*- coding: utf-8 -*-
"""TendencyAnalyzer 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.scouting.tendency_analyzer import (
    TendencyAnalyzer,
    TendencyAnalyzerConfig,
    ShotRecordInput,
    PossessionRecordInput,
)
from shared.constants.game_rule_constants import CourtZone


def _shot(**kwargs) -> ShotRecordInput:
    defaults = dict(
        zone=CourtZone.PAINT_CENTER.value, made=True,
        points=2, court_side="center",
    )
    defaults.update(kwargs)
    return ShotRecordInput(**defaults)


def _poss(**kwargs) -> PossessionRecordInput:
    defaults = dict(
        play_type="pick_and_roll", is_transition=False,
        points_scored=2, court_side="right",
    )
    defaults.update(kwargs)
    return PossessionRecordInput(**defaults)


class TestTendencyAnalyzer:
    """TendencyAnalyzer 단위 테스트."""

    def test_init_default(self):
        ta = TendencyAnalyzer()
        assert ta.name == "TendencyAnalyzer"

    def test_analyze_empty(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        report = ta.analyze()
        assert report.team_id == "T001"
        assert report.three_point_rate == 0.0

    def test_shot_zone_preferences(self):
        ta = TendencyAnalyzer(config=TendencyAnalyzerConfig(min_shots_for_zone=2))
        ta.set_team_id("T001")
        # 10 shots total: 5 paint, 3 three, 2 mid
        for _ in range(5):
            ta.add_shot(_shot(zone=CourtZone.PAINT_CENTER.value))
        for _ in range(3):
            ta.add_shot(_shot(zone=CourtZone.THREE_LEFT_WING.value))
        for _ in range(2):
            ta.add_shot(_shot(zone=CourtZone.MID_LEFT_ELBOW.value))
        report = ta.analyze()
        assert CourtZone.PAINT_CENTER.value in report.shot_zone_preferences
        assert report.shot_zone_preferences[CourtZone.PAINT_CENTER.value] == 50.0

    def test_play_type_preferences(self):
        ta = TendencyAnalyzer(config=TendencyAnalyzerConfig(
            min_possessions_for_play_type=2
        ))
        ta.set_team_id("T001")
        for _ in range(6):
            ta.add_possession(_poss(play_type="pick_and_roll"))
        for _ in range(4):
            ta.add_possession(_poss(play_type="isolation"))
        report = ta.analyze()
        assert "pick_and_roll" in report.play_type_preferences
        assert report.play_type_preferences["pick_and_roll"] == 60.0

    def test_transition_tendency(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        for _ in range(3):
            ta.add_possession(_poss(is_transition=True))
        for _ in range(7):
            ta.add_possession(_poss(is_transition=False))
        report = ta.analyze()
        assert report.transition_tendency == 30.0

    def test_three_point_rate(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        for _ in range(4):
            ta.add_shot(_shot(zone=CourtZone.THREE_LEFT_CORNER.value))
        for _ in range(6):
            ta.add_shot(_shot(zone=CourtZone.PAINT_CENTER.value))
        report = ta.analyze()
        assert report.three_point_rate == 0.4

    def test_paint_attack_rate(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        for _ in range(3):
            ta.add_shot(_shot(zone=CourtZone.PAINT_LEFT.value))
        for _ in range(7):
            ta.add_shot(_shot(zone=CourtZone.THREE_CENTER.value))
        report = ta.analyze()
        assert report.paint_attack_rate == 0.3

    def test_direction_preference(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        for _ in range(6):
            ta.add_possession(_poss(court_side="right"))
        for _ in range(4):
            ta.add_possession(_poss(court_side="left"))
        report = ta.analyze()
        assert report.right_side_preference == 0.6
        assert report.left_side_preference == 0.4

    def test_min_shots_filter(self):
        ta = TendencyAnalyzer(config=TendencyAnalyzerConfig(min_shots_for_zone=5))
        ta.set_team_id("T001")
        # 3 shots only — below threshold
        for _ in range(3):
            ta.add_shot(_shot(zone=CourtZone.PAINT_CENTER.value))
        report = ta.analyze()
        assert CourtZone.PAINT_CENTER.value not in report.shot_zone_preferences

    def test_event_history(self):
        ta = TendencyAnalyzer()
        ta.add_shot(_shot())
        ta.add_shot(_shot())
        assert len(ta.get_event_history()) == 2

    def test_deep_three_counts_as_three(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        for _ in range(5):
            ta.add_shot(_shot(zone=CourtZone.DEEP_THREE_CENTER.value))
        for _ in range(5):
            ta.add_shot(_shot(zone=CourtZone.PAINT_CENTER.value))
        report = ta.analyze()
        assert report.three_point_rate == 0.5

    def test_reset(self):
        ta = TendencyAnalyzer()
        ta.set_team_id("T001")
        ta.add_shot(_shot())
        ta.add_possession(_poss())
        ta.reset()
        report = ta.analyze()
        assert report.team_id == ""
        assert len(ta.get_event_history()) == 0
