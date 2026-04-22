# -*- coding: utf-8 -*-
"""WeaknessFinder 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.scouting.weakness_finder import (
    WeaknessFinder,
    WeaknessFinderConfig,
    ZoneDefenseInput,
    TransitionDefenseInput,
    ReboundInput,
    MatchupDefenseInput,
    ThreePointDefenseInput,
)


class TestWeaknessFinder:
    """WeaknessFinder 단위 테스트."""

    def test_init_default(self):
        wf = WeaknessFinder()
        assert wf.name == "WeaknessFinder"

    def test_find_empty(self):
        wf = WeaknessFinder()
        wf.set_team_id("T001")
        report = wf.find_weaknesses()
        assert report.team_id == "T001"
        assert len(report.defensive_gaps) == 0

    def test_zone_gap_detected(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            zone_gap_fg_pct_threshold=0.50, zone_min_attempts=3,
        ))
        wf.set_team_id("T001")
        # paint_center: 8/10 = 80% → 수비 갭
        wf.add_zone_defense(ZoneDefenseInput(
            zone="paint_center", fg_attempts_allowed=10, fg_made_allowed=8,
        ))
        report = wf.find_weaknesses()
        assert len(report.defensive_gaps) == 1
        assert report.defensive_gaps[0].zone == "paint_center"

    def test_zone_gap_below_threshold(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            zone_gap_fg_pct_threshold=0.50, zone_min_attempts=3,
        ))
        wf.set_team_id("T001")
        # 4/10 = 40% → 갭 아님
        wf.add_zone_defense(ZoneDefenseInput(
            zone="paint_center", fg_attempts_allowed=10, fg_made_allowed=4,
        ))
        report = wf.find_weaknesses()
        assert len(report.defensive_gaps) == 0

    def test_transition_weakness_high(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            transition_weakness_ppp_threshold=1.15,
        ))
        wf.set_team_id("T001")
        # 30 points / 20 possessions = 1.50 PPP → 취약
        wf.add_transition_defense(TransitionDefenseInput(
            transition_possessions=20, transition_points_allowed=30,
        ))
        report = wf.find_weaknesses()
        assert report.transition_weakness_score > 0.0

    def test_transition_weakness_low(self):
        wf = WeaknessFinder()
        wf.set_team_id("T001")
        # 15 / 20 = 0.75 PPP → 양호
        wf.add_transition_defense(TransitionDefenseInput(
            transition_possessions=20, transition_points_allowed=15,
        ))
        report = wf.find_weaknesses()
        assert report.transition_weakness_score == 0.0

    def test_rebound_weakness_offensive(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            oreb_rate_weakness=0.25, dreb_rate_weakness=0.70,
        ))
        wf.set_team_id("T001")
        # oreb 30/100 = 30% 허용 → 공격 리바운드 취약
        # dreb 72/100 = 72% 확보 → 수비 리바운드 양호
        wf.add_rebound_data(ReboundInput(
            offensive_rebounds=30, defensive_rebounds=72,
            total_rebound_chances=100,
        ))
        report = wf.find_weaknesses()
        assert report.rebounding_weakness == "offensive"

    def test_rebound_weakness_both(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            oreb_rate_weakness=0.25, dreb_rate_weakness=0.70,
        ))
        wf.set_team_id("T001")
        wf.add_rebound_data(ReboundInput(
            offensive_rebounds=30, defensive_rebounds=60,
            total_rebound_chances=100,
        ))
        report = wf.find_weaknesses()
        assert report.rebounding_weakness == "both"

    def test_matchup_exploit_detected(self):
        wf = WeaknessFinder(config=WeaknessFinderConfig(
            matchup_fg_pct_weakness=0.50, matchup_min_possessions=3,
        ))
        wf.set_team_id("T001")
        wf.add_matchup_defense(MatchupDefenseInput(
            player_tracking_id=5, weakness_type="post_defense",
            possessions=10, fg_attempts=8, fg_made=6,  # 75%
        ))
        report = wf.find_weaknesses()
        assert len(report.matchup_exploits) == 1
        assert report.matchup_exploits[0].player_tracking_id == 5

    def test_three_pt_defense_bad(self):
        wf = WeaknessFinder()
        wf.set_team_id("T001")
        # 40/100 = 40% → 나쁜 3점 수비
        wf.add_three_pt_defense(ThreePointDefenseInput(
            three_pt_attempts_allowed=100, three_pt_made_allowed=40,
        ))
        report = wf.find_weaknesses()
        assert report.three_point_defense_rating == 0.0  # 최악

    def test_three_pt_defense_good(self):
        wf = WeaknessFinder()
        wf.set_team_id("T001")
        # 28/100 = 28% → 좋은 3점 수비
        wf.add_three_pt_defense(ThreePointDefenseInput(
            three_pt_attempts_allowed=100, three_pt_made_allowed=28,
        ))
        report = wf.find_weaknesses()
        assert report.three_point_defense_rating > 80.0

    def test_reset(self):
        wf = WeaknessFinder()
        wf.set_team_id("T001")
        wf.add_zone_defense(ZoneDefenseInput(zone="paint_center"))
        wf.reset()
        report = wf.find_weaknesses()
        assert report.team_id == ""
        assert len(wf.get_event_history()) == 0
