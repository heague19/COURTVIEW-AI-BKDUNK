# -*- coding: utf-8 -*-
"""FastBreakDetector 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.fast_break_detector import (
    FastBreakDetector,
    FastBreakDetectorConfig,
    FastBreakInput,
    FastBreakType,
    FastBreakResult,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> FastBreakInput:
    defaults = dict(
        frame_index=200,
        timestamp_sec=6.67,
        transition_frame=100,
        transition_timestamp_sec=3.33,
        attacking_team_id="team_a",
        ball_handler_tracking_id=7,
        ball_speed_ms=4.0,
        attackers_ahead_of_ball=2,
        defenders_in_frontcourt=1,
        ball_handler_speed_ms=5.0,
        ball_handler_direction_to_rim=True,
        confidence=0.80,
        quarter=1,
        game_clock="09:00",
    )
    defaults.update(overrides)
    return FastBreakInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestFastBreakDetector:
    """FastBreakDetector 단위 테스트."""

    def test_init_default(self):
        det = FastBreakDetector()
        assert det.name == "FastBreakDetector"
        assert det.total_fast_breaks == 0
        assert not det.is_fast_break_active

    def test_register_transition(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        assert det.is_fast_break_active

    def test_detect_fast_break_scored(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            frame_index=200, timestamp_sec=6.67,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "속공" in event.description

    def test_detect_fast_break_missed(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            shot_attempted=True, shot_made=False,
        ))
        assert event is not None
        assert "missed" in event.description

    def test_detect_fast_break_turnover(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(turnover_occurred=True))
        assert event is not None
        assert "turnover" in event.description

    def test_no_event_without_transition(self):
        det = FastBreakDetector()
        event = det.process_event(_make_input(shot_attempted=True, shot_made=True))
        assert event is None

    def test_no_event_no_advantage(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            attackers_ahead_of_ball=1,
            defenders_in_frontcourt=3,
            ball_speed_ms=1.0,
            ball_handler_direction_to_rim=False,
            shot_attempted=True, shot_made=True,
        ))
        assert event is None

    def test_timeout_secondary_break(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=0, timestamp_sec=0.0))
        event = det.process_event(_make_input(
            frame_index=270, timestamp_sec=9.0,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "secondary" in event.description

    def test_timeout_expired(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=0, timestamp_sec=0.0))
        event = det.process_event(_make_input(
            frame_index=400, timestamp_sec=13.0,
            shot_attempted=True, shot_made=True,
        ))
        assert event is None

    def test_type_2v1(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            attackers_ahead_of_ball=1,
            defenders_in_frontcourt=1,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "2v1" in event.description

    def test_type_3v2(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            attackers_ahead_of_ball=2,
            defenders_in_frontcourt=2,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "3v2" in event.description

    def test_reject_low_confidence(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        event = det.process_event(_make_input(
            confidence=0.30,
            shot_attempted=True, shot_made=True,
        ))
        assert event is None

    def test_reset(self):
        det = FastBreakDetector()
        det.register_transition(_make_input(frame_index=100, timestamp_sec=3.33))
        det.reset()
        assert not det.is_fast_break_active
        assert det.total_fast_breaks == 0

    def test_from_yaml(self):
        cfg = {
            "possession_detection": {"timing": {"fast_break_max_sec": 5.0}},
            "common": {"default_fps": 60},
        }
        det = FastBreakDetector.from_yaml(cfg)
        assert det._config.fast_break_max_sec == 5.0
