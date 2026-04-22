# -*- coding: utf-8 -*-
"""PossessionTracker 단위 테스트 — 15 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.possession_tracker import (
    PossessionTracker,
    PossessionTrackerConfig,
    PossessionFrameInput,
    PossessionState,
    PossessionPhase,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> PossessionFrameInput:
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        ball_holder_tracking_id=7,
        ball_holder_team_id="team_a",
        ball_is_live=True,
        ball_is_controlled=True,
        confidence=0.85,
        quarter=1,
        game_clock="10:00",
    )
    defaults.update(overrides)
    return PossessionFrameInput(**defaults)


def _establish_possession(det: PossessionTracker, team: str, start_frame: int = 0) -> None:
    """helper: 점유 확정을 위해 min_frames 이상 프레임 주입."""
    cfg = det._config
    for i in range(cfg.ball_control_min_frames + 1):
        det.process_frame(_make_input(
            frame_index=start_frame + i,
            timestamp_sec=float(start_frame + i) / cfg.fps,
            ball_holder_team_id=team,
            ball_holder_tracking_id=7,
        ))


# =============================================================================
# 테스트
# =============================================================================
class TestPossessionTracker:
    """PossessionTracker 단위 테스트."""

    def test_init_default(self):
        det = PossessionTracker()
        assert det.name == "PossessionTracker"
        assert det.current_team_id == ""
        assert det.possession_state == PossessionState.UNKNOWN

    def test_establish_first_possession(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        assert det.current_team_id == "team_a"

    def test_possession_transition(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a", start_frame=0)
        _establish_possession(det, "team_b", start_frame=100)
        assert det.current_team_id == "team_b"

    def test_transition_event_generated(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a", start_frame=0)
        events_before = len(det.get_event_history())
        _establish_possession(det, "team_b", start_frame=100)
        events_after = len(det.get_event_history())
        assert events_after > events_before

    def test_holder_update_same_team(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200,
            timestamp_sec=6.67,
            ball_holder_team_id="team_a",
            ball_holder_tracking_id=11,
        ))
        assert det.current_holder_id == 11

    def test_dead_ball_state(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            is_dead_ball=True,
        ))
        assert det.possession_state == PossessionState.DEAD_BALL

    def test_loose_ball_state(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            ball_is_controlled=False,
            ball_holder_team_id="",
        ))
        assert det.possession_state == PossessionState.LOOSE_BALL

    def test_shot_ends_possession(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            ball_holder_team_id="team_a",
            shot_attempted=True,
        ))
        assert det.total_possessions >= 1

    def test_turnover_ends_possession(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            ball_holder_team_id="team_a",
            turnover_occurred=True,
        ))
        assert det.total_possessions >= 1

    def test_possession_phase_fast_break(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a", start_frame=0)
        # 종료: 3초 후 슛
        det.process_frame(_make_input(
            frame_index=90, timestamp_sec=3.0,
            ball_holder_team_id="team_a",
            shot_attempted=True,
        ))
        history = det.get_possession_history()
        assert len(history) >= 1
        assert history[-1].phase == PossessionPhase.FAST_BREAK

    def test_possession_stats(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a", start_frame=0)
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            ball_holder_team_id="team_a",
            shot_attempted=True,
        ))
        stats = det.get_possession_stats()
        assert stats["total_possessions"] >= 1

    def test_reset(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.reset()
        assert det.current_team_id == ""
        assert det.total_possessions == 0

    def test_from_yaml(self):
        cfg = {
            "possession_detection": {
                "transition": {"ball_control_min_frames": 3},
                "timing": {"fast_break_max_sec": 5.0},
            },
            "common": {"default_fps": 60},
        }
        det = PossessionTracker.from_yaml(cfg)
        assert det._config.ball_control_min_frames == 3
        assert det._config.fps == 60.0

    def test_history_trim(self):
        det = PossessionTracker()
        for i in range(600):
            _establish_possession(det, f"team_{i % 2}", start_frame=i * 100)
        assert len(det._event_history) <= 500

    def test_offensive_rebound_keeps_possession(self):
        det = PossessionTracker()
        _establish_possession(det, "team_a")
        det.process_frame(_make_input(
            frame_index=200, timestamp_sec=6.67,
            ball_holder_team_id="team_a",
            shot_attempted=True,
            offensive_rebound=True,
        ))
        assert det.current_team_id == "team_a"
