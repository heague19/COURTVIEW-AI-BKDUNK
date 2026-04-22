# -*- coding: utf-8 -*-
"""ScreenDetector 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.screen_detector import (
    ScreenDetector,
    ScreenDetectorConfig,
    ScreenInput,
    ScreenType,
    ScreenResult,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> ScreenInput:
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        screener_tracking_id=4,
        screener_team_id="team_a",
        screener_court_x=0.3,
        screener_court_y=0.4,
        screener_speed_ms=0.2,
        cutter_tracking_id=7,
        defender_tracking_id=10,
        screener_defender_distance_m=0.4,
        screener_angle_deg=90.0,
        hold_duration_sec=0.8,
        distance_to_rim_m=5.0,
        confidence=0.80,
        quarter=1,
        game_clock="08:00",
    )
    defaults.update(overrides)
    return ScreenInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestScreenDetector:
    """ScreenDetector 단위 테스트."""

    def test_init_default(self):
        det = ScreenDetector()
        assert det.name == "ScreenDetector"
        assert det.total_screens_detected == 0

    def test_detect_valid_screen(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input())
        assert event is not None

    def test_on_ball_screen(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(cutter_has_ball=True))
        assert event is not None
        assert "on_ball" in event.description

    def test_off_ball_screen_default(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input())
        assert event is not None
        assert "off_ball" in event.description

    def test_reject_far_distance(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(screener_defender_distance_m=2.0))
        assert event is None

    def test_reject_bad_angle(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(screener_angle_deg=20.0))
        assert event is None

    def test_reject_moving_screener(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(screener_speed_ms=1.5))
        assert event is None

    def test_reject_short_hold(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(hold_duration_sec=0.1))
        assert event is None

    def test_reject_long_hold(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(hold_duration_sec=3.0))
        assert event is None

    def test_reject_low_confidence(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(confidence=0.50))
        assert event is None

    def test_screen_result_switched(self):
        det = ScreenDetector()
        event = det.detect_screen(_make_input(defender_switched=True))
        assert event is not None
        assert "switched" in event.description

    def test_screen_stats(self):
        det = ScreenDetector()
        det.detect_screen(_make_input())
        det.detect_screen(_make_input(cutter_has_ball=True))
        stats = det.get_screen_stats()
        assert stats["total"] == 2

    def test_reset(self):
        det = ScreenDetector()
        det.detect_screen(_make_input())
        det.reset()
        assert det.total_screens_detected == 0
