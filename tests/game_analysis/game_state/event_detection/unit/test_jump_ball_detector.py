# -*- coding: utf-8 -*-
"""JumpBallDetector 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.jump_ball_detector import (
    JumpBallDetector,
    JumpBallDetectorConfig,
    JumpBallInput,
    JumpBallType,
    JumpBallWinner,
)
from shared.constants.game_rule_constants import GameEventType


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> JumpBallInput:
    defaults = dict(
        frame_index=0,
        timestamp_sec=0.0,
        jumper_a_tracking_id=5,
        jumper_a_team_id="team_home",
        jumper_b_tracking_id=10,
        jumper_b_team_id="team_away",
        jumper_distance_to_center_m=1.0,
        two_players_facing=True,
        referee_toss_detected=True,
        ball_upward_velocity_ms=5.0,
        ball_tipped_to_team_id="team_home",
        is_tip_off=True,
        confidence=0.85,
        quarter=1,
        game_clock="12:00",
    )
    defaults.update(overrides)
    return JumpBallInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestJumpBallDetector:
    """JumpBallDetector 단위 테스트."""

    def test_init_default(self):
        det = JumpBallDetector()
        assert det.name == "JumpBallDetector"
        assert det.total_jump_balls == 0

    def test_detect_tip_off(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input())
        assert event is not None
        assert event.event_type == GameEventType.JUMP_BALL
        assert "tip_off" in event.description

    def test_detect_held_ball(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(is_tip_off=False))
        assert event is not None
        assert "held_ball" in event.description

    def test_detect_overtime_start(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(is_overtime=True))
        assert event is not None
        assert "overtime_start" in event.description

    def test_winner_home(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(
            ball_tipped_to_team_id="team_home",
        ))
        assert event is not None
        assert "home" in event.description

    def test_winner_away(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(
            ball_tipped_to_team_id="team_away",
        ))
        assert event is not None
        assert "away" in event.description

    def test_winner_unknown(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(
            ball_tipped_to_team_id="",
        ))
        assert event is not None
        assert "unknown" in event.description

    def test_reject_far_from_center(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(
            jumper_distance_to_center_m=5.0,
        ))
        assert event is None

    def test_reject_no_facing(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(two_players_facing=False))
        assert event is None

    def test_reject_no_toss(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(referee_toss_detected=False))
        assert event is None

    def test_reject_low_ball_velocity(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(ball_upward_velocity_ms=1.0))
        assert event is None

    def test_reject_low_confidence(self):
        det = JumpBallDetector()
        event = det.detect_jump_ball(_make_input(confidence=0.50))
        assert event is None

    def test_reset(self):
        det = JumpBallDetector()
        det.detect_jump_ball(_make_input())
        det.reset()
        assert det.total_jump_balls == 0
