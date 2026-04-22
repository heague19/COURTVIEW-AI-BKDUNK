# -*- coding: utf-8 -*-
"""GameReportBuilder 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.game_record.game_report_builder import (
    GameReportBuilder,
    GameReportConfig,
    ReportTeamData,
    ReportPlayerData,
    ReportHighlightRef,
    GameReport,
)


def _home_team(**kwargs) -> ReportTeamData:
    defaults = dict(
        team_id="home", team_name="Home Tigers", final_score=85,
        quarter_scores=[22, 20, 25, 18],
        efg_percentage=52.0, tov_percentage=12.0,
        oreb_percentage=30.0, ft_rate=25.0,
        fg_made=32, fg_attempted=70, three_pt_made=8, three_pt_attempted=22,
        ft_made=13, ft_attempted=17, rebounds=42, assists=20,
        turnovers=12, steals=8, blocks=4,
    )
    defaults.update(kwargs)
    return ReportTeamData(**defaults)


def _away_team(**kwargs) -> ReportTeamData:
    defaults = dict(
        team_id="away", team_name="Away Eagles", final_score=80,
        quarter_scores=[20, 22, 18, 20],
        efg_percentage=48.0, tov_percentage=15.0,
        oreb_percentage=25.0, ft_rate=20.0,
    )
    defaults.update(kwargs)
    return ReportTeamData(**defaults)


def _player(**kwargs) -> ReportPlayerData:
    defaults = dict(
        player_id=7, team_id="home", jersey_number=7,
        is_starter=True, points=20, rebounds=8,
        assists=5, steals=2, blocks=1, turnovers=3,
        minutes_played=32.0, game_score=18.5,
    )
    defaults.update(kwargs)
    return ReportPlayerData(**defaults)


def _hl(**kwargs) -> ReportHighlightRef:
    defaults = dict(
        event_key="dunk", description="슬램덩크",
        timestamp_sec=300.0, quarter=2,
        excitement_score=85.0, player_id=7,
    )
    defaults.update(kwargs)
    return ReportHighlightRef(**defaults)


class TestGameReportBuilder:
    """GameReportBuilder 단위 테스트."""

    def test_init_default(self):
        rb = GameReportBuilder()
        assert rb.name == "GameReportBuilder"

    def test_build_empty(self):
        rb = GameReportBuilder()
        report = rb.build()
        assert report.mvp_player_id == 0

    def test_set_meta(self):
        rb = GameReportBuilder()
        rb.set_meta(game_date="2026-03-24", venue="Seoul Arena", league="KBL")
        report = rb.build()
        assert report.game_date == "2026-03-24"
        assert report.venue == "Seoul Arena"

    def test_team_data(self):
        rb = GameReportBuilder()
        rb.set_team_data(_home_team(), _away_team())
        report = rb.build()
        assert report.home_team.final_score == 85
        assert report.away_team.final_score == 80

    def test_four_factors_comparison(self):
        rb = GameReportBuilder()
        rb.set_team_data(_home_team(efg_percentage=55.0), _away_team(efg_percentage=48.0))
        report = rb.build()
        ff = report.four_factors_comparison
        assert ff["home"]["efg_pct"] == 55.0
        assert ff["away"]["efg_pct"] == 48.0
        assert "weights" in ff

    def test_mvp_selection(self):
        rb = GameReportBuilder()
        rb.set_players(
            home_players=[
                _player(player_id=7, game_score=22.0),
                _player(player_id=11, game_score=15.0),
            ],
            away_players=[
                _player(player_id=23, team_id="away", game_score=18.0),
            ],
        )
        report = rb.build()
        assert report.mvp_player_id == 7
        assert report.mvp_game_score == 22.0

    def test_highlights_sorted(self):
        rb = GameReportBuilder()
        rb.add_highlight(_hl(excitement_score=70.0))
        rb.add_highlight(_hl(excitement_score=95.0))
        rb.add_highlight(_hl(excitement_score=80.0))
        report = rb.build()
        assert len(report.top_highlights) == 3
        assert report.top_highlights[0].excitement_score == 95.0

    def test_highlights_max_limit(self):
        rb = GameReportBuilder(config=GameReportConfig(max_highlights_in_report=2))
        for i in range(5):
            rb.add_highlight(_hl(excitement_score=float(50 + i * 10)))
        report = rb.build()
        assert len(report.top_highlights) == 2

    def test_game_flow(self):
        rb = GameReportBuilder()
        rb.set_game_flow(lead_changes=7, ties=4)
        report = rb.build()
        assert report.lead_changes == 7
        assert report.ties == 4

    def test_pbp_summary(self):
        rb = GameReportBuilder()
        rb.set_pbp_summary(total=120, scoring=45)
        report = rb.build()
        assert report.total_events == 120
        assert report.scoring_events == 45

    def test_build_json(self):
        rb = GameReportBuilder()
        rb.set_meta(game_date="2026-03-24")
        rb.set_team_data(_home_team(final_score=90), _away_team(final_score=85))
        rb.set_game_flow(lead_changes=5, ties=2)
        result = rb.build_json()
        assert result["meta"]["game_date"] == "2026-03-24"
        assert result["score"]["home"] == 90
        assert result["game_flow"]["lead_changes"] == 5

    def test_reset(self):
        rb = GameReportBuilder()
        rb.set_meta(game_date="2026-03-24")
        rb.add_highlight(_hl())
        rb.reset()
        report = rb.build()
        assert report.game_date == ""
        assert len(report.top_highlights) == 0
        assert len(rb.get_event_history()) == 0
