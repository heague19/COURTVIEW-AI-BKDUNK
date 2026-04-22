# -*- coding: utf-8 -*-
"""DeadBallDetector 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.dead_ball_detector import (
    DeadBallDetector,
    DeadBallDetectorConfig,
    DeadBallFrameInput,
    DeadBallReason,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> DeadBallFrameInput:
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        game_clock_running=True,
        ball_is_live=True,
        ball_in_play=True,
        confidence=0.85,
        quarter=1,
        game_clock="10:00",
    )
    defaults.update(overrides)
    return DeadBallFrameInput(**defaults)


def _trigger_dead_ball(det: DeadBallDetector, reason_kwargs: dict, start_frame: int = 0) -> None:
    """min_dead_ball_frames 이상 데드볼 조건 프레임 주입."""
    cfg = det._config
    for i in range(cfg.min_dead_ball_frames + 1):
        det.process_frame(_make_input(
            frame_index=start_frame + i,
            timestamp_sec=float(start_frame + i) / cfg.fps,
            **reason_kwargs,
        ))


def _trigger_live(det: DeadBallDetector, start_frame: int = 200) -> None:
    """max_dead_ball_gap_frames 이상 라이브 조건 프레임 주입."""
    cfg = det._config
    for i in range(cfg.max_dead_ball_gap_frames + 1):
        det.process_frame(_make_input(
            frame_index=start_frame + i,
            timestamp_sec=float(start_frame + i) / cfg.fps,
        ))


# =============================================================================
# 테스트
# =============================================================================
class TestDeadBallDetector:
    """DeadBallDetector 단위 테스트."""

    def test_init_default(self):
        det = DeadBallDetector()
        assert det.name == "DeadBallDetector"
        assert not det.is_dead_ball

    def test_detect_clock_stopped(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"game_clock_running": False})
        assert det.is_dead_ball

    def test_detect_foul(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"foul_detected": True})
        assert det.is_dead_ball
        assert det.dead_ball_reason == DeadBallReason.FOUL

    def test_detect_out_of_bounds(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"out_of_bounds_detected": True})
        assert det.is_dead_ball
        assert det.dead_ball_reason == DeadBallReason.OUT_OF_BOUNDS

    def test_detect_made_basket(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"made_basket_detected": True})
        assert det.is_dead_ball

    def test_detect_violation(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"violation_detected": True})
        assert det.is_dead_ball
        assert det.dead_ball_reason == DeadBallReason.VIOLATION

    def test_detect_referee_holds_ball(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"ball_held_by_referee": True})
        assert det.is_dead_ball

    def test_no_dead_ball_normal_play(self):
        det = DeadBallDetector()
        for i in range(20):
            det.process_frame(_make_input(
                frame_index=i, timestamp_sec=i / 30.0,
                avg_player_speed_ms=2.0,
            ))
        assert not det.is_dead_ball

    def test_transition_live_after_dead(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"foul_detected": True}, start_frame=0)
        assert det.is_dead_ball
        _trigger_live(det, start_frame=100)
        assert not det.is_dead_ball

    def test_event_generated_on_transition(self):
        det = DeadBallDetector()
        events = []
        for i in range(10):
            ev = det.process_frame(_make_input(
                frame_index=i, timestamp_sec=i / 30.0,
                foul_detected=True,
            ))
            if ev:
                events.append(ev)
        assert len(events) >= 1

    def test_dead_ball_stats(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"foul_detected": True})
        stats = det.get_dead_ball_stats()
        assert stats["total_dead_balls"] >= 1
        assert stats["is_currently_dead"]

    def test_reset(self):
        det = DeadBallDetector()
        _trigger_dead_ball(det, {"foul_detected": True})
        det.reset()
        assert not det.is_dead_ball
        assert det.total_dead_balls == 0

    def test_from_yaml(self):
        cfg = {"common": {"default_fps": 60}, "timeout_detection": {"trigger": {}}}
        det = DeadBallDetector.from_yaml(cfg)
        assert det._config.fps == 60.0

    def test_history_trim(self):
        det = DeadBallDetector()
        for i in range(600):
            _trigger_dead_ball(det, {"foul_detected": True}, start_frame=i * 100)
            _trigger_live(det, start_frame=i * 100 + 50)
        assert len(det._event_history) <= 500
