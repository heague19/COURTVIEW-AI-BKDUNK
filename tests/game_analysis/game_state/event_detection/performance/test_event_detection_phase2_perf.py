# -*- coding: utf-8 -*-
"""Phase 1B-2 이벤트 감지기 성능 테스트 — 12 tests.

Cadence 준수 확인:
  FRAME (<2ms): PossessionTracker, DeadBallDetector
  EVENT (<10ms): FoulDetector, ScreenDetector, FastBreakDetector, DriveDetector
  SPECIAL: BoxOutDetector, JumpBallDetector
"""
from __future__ import annotations

import time

import pytest

from game_analysis.game_state.event_detection.foul_detector import FoulDetector, FoulInput
from game_analysis.game_state.event_detection.possession_tracker import PossessionTracker, PossessionFrameInput
from game_analysis.game_state.event_detection.dead_ball_detector import DeadBallDetector, DeadBallFrameInput
from game_analysis.game_state.event_detection.screen_detector import ScreenDetector, ScreenInput
from game_analysis.game_state.event_detection.fast_break_detector import FastBreakDetector, FastBreakInput
from game_analysis.game_state.event_detection.drive_detector import DriveDetector, DriveInput
from game_analysis.game_state.event_detection.box_out_detector import BoxOutDetector, BoxOutInput
from game_analysis.game_state.event_detection.jump_ball_detector import JumpBallDetector, JumpBallInput


_FRAME_BUDGET_MS = 2.0
_EVENT_BUDGET_MS = 10.0
_ITERATIONS = 500


class TestPhase1B2Performance:
    """Phase 1B-2 성능 테스트."""

    # === FRAME cadence (<2ms) ===

    def test_possession_tracker_frame_cadence(self):
        det = PossessionTracker()
        inp = PossessionFrameInput(
            frame_index=0, timestamp_sec=0.0,
            ball_holder_tracking_id=7, ball_holder_team_id="team_a",
            ball_is_controlled=True, confidence=0.85,
        )
        t0 = time.perf_counter()
        for i in range(_ITERATIONS):
            inp.frame_index = i
            inp.timestamp_sec = i / 30.0
            det.process_frame(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _FRAME_BUDGET_MS, f"PossessionTracker avg={avg_ms:.3f}ms > {_FRAME_BUDGET_MS}ms"

    def test_dead_ball_detector_frame_cadence(self):
        det = DeadBallDetector()
        inp = DeadBallFrameInput(
            frame_index=0, timestamp_sec=0.0,
            game_clock_running=True, ball_is_live=True, confidence=0.85,
        )
        t0 = time.perf_counter()
        for i in range(_ITERATIONS):
            inp.frame_index = i
            inp.timestamp_sec = i / 30.0
            det.process_frame(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _FRAME_BUDGET_MS, f"DeadBallDetector avg={avg_ms:.3f}ms > {_FRAME_BUDGET_MS}ms"

    # === EVENT cadence (<10ms) ===

    def test_foul_detector_event_cadence(self):
        det = FoulDetector()
        inp = FoulInput(
            frame_index=100, timestamp_sec=3.33,
            fouling_player_id=5, fouling_team_id="team_a",
            fouled_player_id=10, fouled_team_id="team_b",
            body_overlap_ratio=0.4, contact_duration_frames=3,
            confidence=0.80,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.detect_foul(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"FoulDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_screen_detector_event_cadence(self):
        det = ScreenDetector()
        inp = ScreenInput(
            frame_index=100, timestamp_sec=3.33,
            screener_tracking_id=4, screener_team_id="team_a",
            screener_speed_ms=0.2,
            screener_defender_distance_m=0.4, screener_angle_deg=90.0,
            hold_duration_sec=0.8, confidence=0.80,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.detect_screen(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"ScreenDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_fast_break_detector_event_cadence(self):
        det = FastBreakDetector()
        reg_inp = FastBreakInput(
            frame_index=100, timestamp_sec=3.33,
            attacking_team_id="team_a", confidence=0.80,
        )
        proc_inp = FastBreakInput(
            frame_index=200, timestamp_sec=6.67,
            attacking_team_id="team_a",
            ball_speed_ms=4.0,
            attackers_ahead_of_ball=2, defenders_in_frontcourt=1,
            ball_handler_direction_to_rim=True,
            shot_attempted=True, shot_made=True,
            confidence=0.80,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.register_transition(reg_inp)
            det.process_event(proc_inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"FastBreakDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_drive_detector_event_cadence(self):
        det = DriveDetector()
        start_inp = DriveInput(
            frame_index=100, timestamp_sec=3.33,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=3.0, direction_to_rim_deg=10.0,
            confidence=0.80,
        )
        end_inp = DriveInput(
            frame_index=130, timestamp_sec=4.33,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=2.5, drive_distance_m=2.0,
            shot_attempted=True, shot_made=True,
            confidence=0.80,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.process_event(start_inp)
            det.process_event(end_inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"DriveDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    # === SPECIAL cadence ===

    def test_box_out_detector_cadence(self):
        det = BoxOutDetector()
        inp = BoxOutInput(
            frame_index=100, timestamp_sec=3.33,
            boxer_tracking_id=5, boxer_team_id="team_a",
            target_tracking_id=10, target_team_id="team_b",
            boxer_target_distance_m=1.0, body_contact_detected=True,
            boxer_facing_basket=True, time_after_shot_sec=0.3,
            confidence=0.75,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.detect_box_out(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"BoxOutDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    def test_jump_ball_detector_cadence(self):
        det = JumpBallDetector()
        inp = JumpBallInput(
            frame_index=0, timestamp_sec=0.0,
            jumper_a_tracking_id=5, jumper_a_team_id="team_home",
            jumper_b_tracking_id=10, jumper_b_team_id="team_away",
            jumper_distance_to_center_m=1.0,
            two_players_facing=True, referee_toss_detected=True,
            ball_upward_velocity_ms=5.0,
            ball_tipped_to_team_id="team_home",
            is_tip_off=True, confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            det.detect_jump_ball(inp)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _EVENT_BUDGET_MS, f"JumpBallDetector avg={avg_ms:.3f}ms > {_EVENT_BUDGET_MS}ms"

    # === 메모리 가드 ===

    def test_possession_tracker_memory_guard(self):
        det = PossessionTracker()
        for i in range(600):
            det.process_frame(PossessionFrameInput(
                frame_index=i, timestamp_sec=i / 30.0,
                ball_holder_tracking_id=i % 10,
                ball_holder_team_id=f"team_{i % 2}",
                ball_is_controlled=True, confidence=0.85,
            ))
        assert len(det._event_history) <= 500

    def test_dead_ball_detector_memory_guard(self):
        det = DeadBallDetector()
        for i in range(600):
            det.process_frame(DeadBallFrameInput(
                frame_index=i, timestamp_sec=i / 30.0,
                foul_detected=(i % 20 == 0),
                game_clock_running=(i % 20 != 0),
                confidence=0.85,
            ))
        assert len(det._event_history) <= 500

    def test_foul_detector_memory_guard(self):
        det = FoulDetector()
        for i in range(600):
            det.detect_foul(FoulInput(
                frame_index=i, timestamp_sec=i / 30.0,
                fouling_player_id=5, fouling_team_id="team_a",
                fouled_player_id=10, fouled_team_id="team_b",
                body_overlap_ratio=0.5, contact_duration_frames=3,
                confidence=0.80,
            ))
        assert len(det._event_history) <= 500

    def test_screen_detector_memory_guard(self):
        det = ScreenDetector()
        for i in range(600):
            det.detect_screen(ScreenInput(
                frame_index=i, timestamp_sec=i / 30.0,
                screener_tracking_id=4, screener_team_id="team_a",
                screener_speed_ms=0.2,
                screener_defender_distance_m=0.4, screener_angle_deg=90.0,
                hold_duration_sec=0.8, confidence=0.80,
            ))
        assert len(det._event_history) <= 500
