# -*- coding: utf-8 -*-
"""PlayByPlayRecorder 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.game_record.play_by_play import (
    PlayByPlayRecorder,
    PlayByPlayConfig,
    PBPEventInput,
    PBPEntry,
    PBPSummary,
)
from shared.constants.game_rule_constants import GameEventType


def _evt(**kwargs) -> PBPEventInput:
    defaults = dict(
        event_type=GameEventType.SHOT_MADE,
        team_id="home", player_id=7, jersey_number=7,
        quarter=1, game_clock="08:30", timestamp_sec=90.0,
        points=2, home_score=10, away_score=8,
        is_home_team=True, confidence=0.85,
    )
    defaults.update(kwargs)
    return PBPEventInput(**defaults)


class TestPlayByPlayRecorder:
    """PlayByPlayRecorder 단위 테스트."""

    def test_init_default(self):
        pbp = PlayByPlayRecorder()
        assert pbp.name == "PlayByPlayRecorder"

    def test_record_basic(self):
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(_evt())
        assert entry.sequence == 1
        assert entry.is_scoring is True
        assert entry.score_margin == 2  # 10-8

    def test_sequence_increment(self):
        pbp = PlayByPlayRecorder()
        e1 = pbp.record_event(_evt())
        e2 = pbp.record_event(_evt(timestamp_sec=100.0))
        assert e1.sequence == 1
        assert e2.sequence == 2

    def test_korean_description(self):
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(_evt(
            event_type=GameEventType.FREE_THROW_MADE,
            jersey_number=23,
        ))
        assert "23" in entry.description_ko
        assert "자유투" in entry.description_ko

    def test_english_description(self):
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(_evt(
            event_type=GameEventType.STEAL,
            jersey_number=7,
        ))
        assert "STL" in entry.description_en

    def test_scoring_flag(self):
        pbp = PlayByPlayRecorder()
        e_fg = pbp.record_event(_evt(event_type=GameEventType.SHOT_MADE))
        e_miss = pbp.record_event(_evt(event_type=GameEventType.SHOT_MISSED))
        assert e_fg.is_scoring is True
        assert e_miss.is_scoring is False

    def test_turnover_flag(self):
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(_evt(event_type=GameEventType.TURNOVER))
        assert entry.is_turnover is True

    def test_foul_flag(self):
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(_evt(event_type=GameEventType.PERSONAL_FOUL))
        assert entry.is_foul is True

    def test_quarter_entries(self):
        pbp = PlayByPlayRecorder()
        pbp.record_event(_evt(quarter=1))
        pbp.record_event(_evt(quarter=2))
        pbp.record_event(_evt(quarter=1))
        q1 = pbp.get_quarter_entries(1)
        assert len(q1) == 2

    def test_team_entries(self):
        pbp = PlayByPlayRecorder()
        pbp.record_event(_evt(team_id="home"))
        pbp.record_event(_evt(team_id="away"))
        home = pbp.get_team_entries("home")
        assert len(home) == 1

    def test_scoring_runs(self):
        pbp = PlayByPlayRecorder()
        # home 연속 8점
        pbp.record_event(_evt(team_id="home", points=2, timestamp_sec=100.0))
        pbp.record_event(_evt(team_id="home", points=3, timestamp_sec=110.0))
        pbp.record_event(_evt(team_id="home", points=3, timestamp_sec=120.0))
        # away 득점으로 런 종료
        pbp.record_event(_evt(team_id="away", points=2, timestamp_sec=130.0))
        runs = pbp.get_scoring_runs(min_run=6)
        assert len(runs) == 1
        assert runs[0]["points"] == 8
        assert runs[0]["team_id"] == "home"

    def test_summary(self):
        pbp = PlayByPlayRecorder()
        pbp.record_event(_evt(event_type=GameEventType.SHOT_MADE, quarter=1))
        pbp.record_event(_evt(event_type=GameEventType.TURNOVER, quarter=1))
        pbp.record_event(_evt(event_type=GameEventType.PERSONAL_FOUL, quarter=2))
        summary = pbp.get_summary()
        assert summary.total_events == 3
        assert summary.scoring_events == 1
        assert summary.turnovers == 1
        assert summary.fouls == 1
        assert summary.events_per_quarter[1] == 2

    def test_reset(self):
        pbp = PlayByPlayRecorder()
        pbp.record_event(_evt())
        pbp.reset()
        assert len(pbp.get_all_entries()) == 0
        assert len(pbp.get_event_history()) == 0
