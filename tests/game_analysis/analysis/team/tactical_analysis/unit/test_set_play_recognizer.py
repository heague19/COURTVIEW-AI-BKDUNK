# -*- coding: utf-8 -*-
"""SetPlayRecognizer 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.set_play_recognizer import (
    SetPlayRecognizer,
    SetPlayRecognizerConfig,
    SetPlayEventInput,
)
from shared.constants.tactical_constants import SetPlayType


# =============================================================================
# 헬퍼
# =============================================================================
def _make_sp(
    team_id: str = "home",
    play_type: SetPlayType = SetPlayType.PICK_AND_ROLL,
    points: int = 2,
    shot: bool = True,
    made: bool = True,
    turnover: bool = False,
    confidence: float = 0.80,
) -> SetPlayEventInput:
    return SetPlayEventInput(
        team_id=team_id,
        play_type=play_type,
        points_scored=points,
        resulted_in_shot=shot,
        shot_made=made,
        resulted_in_turnover=turnover,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestSetPlayRecognizer:
    """SetPlayRecognizer 단위 테스트."""

    def test_init_default(self):
        spr = SetPlayRecognizer()
        assert spr.name == "SetPlayRecognizer"

    def test_process_single_play(self):
        spr = SetPlayRecognizer()
        ok = spr.process_set_play(_make_sp(points=2))
        assert ok is True
        result = spr.get_team_analysis("home")
        assert result.total_set_plays == 1
        assert result.set_play_ppp == 2.0

    def test_multiple_play_types(self):
        spr = SetPlayRecognizer()
        spr.process_set_play(_make_sp(play_type=SetPlayType.PICK_AND_ROLL, points=2))
        spr.process_set_play(_make_sp(play_type=SetPlayType.ISOLATION, points=3))
        spr.process_set_play(_make_sp(play_type=SetPlayType.PICK_AND_ROLL, points=0, made=False))
        result = spr.get_team_analysis("home")
        assert result.total_set_plays == 3
        assert len(result.detected_plays) == 2

    def test_top_plays(self):
        spr = SetPlayRecognizer()
        for _ in range(5):
            spr.process_set_play(_make_sp(play_type=SetPlayType.HORN, points=2))
        for _ in range(3):
            spr.process_set_play(_make_sp(play_type=SetPlayType.FLEX, points=2))
        result = spr.get_team_analysis("home")
        assert result.top_plays[0] == "horn"

    def test_play_ppp(self):
        spr = SetPlayRecognizer()
        spr.process_set_play(_make_sp(play_type=SetPlayType.ISOLATION, points=3))
        spr.process_set_play(_make_sp(play_type=SetPlayType.ISOLATION, points=0))
        ppp = spr.get_play_ppp("home", SetPlayType.ISOLATION)
        assert ppp == 1.5

    def test_play_frequency(self):
        spr = SetPlayRecognizer()
        for _ in range(3):
            spr.process_set_play(_make_sp(play_type=SetPlayType.PICK_AND_ROLL))
        spr.process_set_play(_make_sp(play_type=SetPlayType.POST_UP))
        freq = spr.get_play_frequency("home")
        assert freq["pick_and_roll"] == 75.0
        assert freq["post_up"] == 25.0

    def test_success_rate_in_detected_plays(self):
        spr = SetPlayRecognizer()
        spr.process_set_play(_make_sp(play_type=SetPlayType.MOTION, made=True, shot=True))
        spr.process_set_play(_make_sp(play_type=SetPlayType.MOTION, made=False, shot=True))
        result = spr.get_team_analysis("home")
        play = result.detected_plays[0]
        assert play.success_rate == 0.5

    def test_turnover_rate(self):
        spr = SetPlayRecognizer()
        spr.process_set_play(_make_sp(play_type=SetPlayType.TRIANGLE, turnover=True, points=0))
        spr.process_set_play(_make_sp(play_type=SetPlayType.TRIANGLE, turnover=False))
        rate = spr.get_play_turnover_rate("home", SetPlayType.TRIANGLE)
        assert rate == 50.0

    def test_reject_low_confidence(self):
        spr = SetPlayRecognizer()
        ok = spr.process_set_play(_make_sp(confidence=0.3))
        assert ok is False

    def test_empty_team(self):
        spr = SetPlayRecognizer()
        result = spr.get_team_analysis("away")
        assert result.total_set_plays == 0

    def test_unknown_play_ppp(self):
        spr = SetPlayRecognizer()
        ppp = spr.get_play_ppp("home", SetPlayType.SPAIN_PNR)
        assert ppp == 0.0

    def test_reset(self):
        spr = SetPlayRecognizer()
        spr.process_set_play(_make_sp())
        spr.reset()
        result = spr.get_team_analysis("home")
        assert result.total_set_plays == 0
        assert len(spr.get_event_history()) == 0
