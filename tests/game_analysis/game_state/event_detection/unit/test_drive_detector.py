# -*- coding: utf-8 -*-
"""DriveDetector 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.drive_detector import (
    DriveDetector,
    DriveDetectorConfig,
    DriveInput,
    DriveDirection,
    DriveResult,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_start_input(**overrides) -> DriveInput:
    """드라이브 시작 조건 충족 입력."""
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        handler_tracking_id=7,
        handler_team_id="team_a",
        handler_court_x=0.5,
        handler_court_y=0.3,
        handler_speed_ms=3.0,
        direction_to_rim_deg=10.0,
        distance_to_rim_m=5.0,
        confidence=0.80,
        quarter=1,
        game_clock="08:00",
    )
    defaults.update(overrides)
    return DriveInput(**defaults)


def _make_progress_input(**overrides) -> DriveInput:
    """드라이브 진행/종료 입력."""
    defaults = dict(
        frame_index=130,
        timestamp_sec=4.33,
        handler_tracking_id=7,
        handler_team_id="team_a",
        handler_court_x=0.3,
        handler_court_y=0.5,
        handler_speed_ms=2.5,
        direction_to_rim_deg=5.0,
        distance_to_rim_m=2.0,
        drive_distance_m=2.0,
        drive_duration_sec=1.0,
        lateral_displacement_m=0.2,
        confidence=0.80,
        quarter=1,
        game_clock="07:59",
    )
    defaults.update(overrides)
    return DriveInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestDriveDetector:
    """DriveDetector 단위 테스트."""

    def test_init_default(self):
        det = DriveDetector()
        assert det.name == "DriveDetector"
        assert det.total_drives_detected == 0
        assert not det.is_drive_active

    def test_drive_start_registered(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        assert det.is_drive_active

    def test_drive_score(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "score" in event.description

    def test_drive_missed(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(
            shot_attempted=True, shot_made=False,
        ))
        assert event is not None
        assert "missed" in event.description

    def test_drive_kickout(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(pass_made=True))
        assert event is not None
        assert "kickout" in event.description

    def test_drive_foul_drawn(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(foul_drawn=True))
        assert event is not None
        assert "foul_drawn" in event.description

    def test_drive_blocked(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(
            shot_attempted=True, blocked=True,
        ))
        assert event is not None
        assert "blocked" in event.description

    def test_drive_turnover(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(turnover=True))
        assert event is not None
        assert "turnover" in event.description

    def test_no_drive_slow_speed(self):
        det = DriveDetector()
        event = det.process_event(_make_start_input(handler_speed_ms=1.0))
        assert event is None
        assert not det.is_drive_active

    def test_no_drive_bad_angle(self):
        det = DriveDetector()
        event = det.process_event(_make_start_input(direction_to_rim_deg=60.0))
        assert event is None

    def test_direction_left(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(
            lateral_displacement_m=-1.0,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "left" in event.description

    def test_direction_right(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(
            lateral_displacement_m=1.0,
            shot_attempted=True, shot_made=True,
        ))
        assert event is not None
        assert "right" in event.description

    def test_pull_back_on_stop(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        event = det.process_event(_make_progress_input(handler_speed_ms=0.5))
        assert event is not None
        assert "pull_back" in event.description

    def test_reset(self):
        det = DriveDetector()
        det.process_event(_make_start_input())
        det.reset()
        assert not det.is_drive_active
        assert det.total_drives_detected == 0
