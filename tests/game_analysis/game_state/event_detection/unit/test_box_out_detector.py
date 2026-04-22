# -*- coding: utf-8 -*-
"""BoxOutDetector 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.box_out_detector import (
    BoxOutDetector,
    BoxOutDetectorConfig,
    BoxOutInput,
    BoxOutType,
    BoxOutResult,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> BoxOutInput:
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        boxer_tracking_id=5,
        boxer_team_id="team_a",
        boxer_court_x=0.3,
        boxer_court_y=0.5,
        target_tracking_id=10,
        target_team_id="team_b",
        boxer_target_distance_m=1.0,
        body_contact_detected=True,
        boxer_facing_basket=True,
        time_after_shot_sec=0.3,
        confidence=0.75,
        quarter=1,
        game_clock="08:00",
    )
    defaults.update(overrides)
    return BoxOutInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestBoxOutDetector:
    """BoxOutDetector 단위 테스트."""

    def test_init_default(self):
        det = BoxOutDetector()
        assert det.name == "BoxOutDetector"
        assert det.total_box_outs_detected == 0

    def test_detect_valid_box_out(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input())
        assert event is not None

    def test_front_pivot_type(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(
            boxer_facing_basket=True, body_contact_detected=True,
        ))
        assert event is not None
        assert "front_pivot" in event.description

    def test_reverse_pivot_type(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(
            boxer_facing_basket=False, body_contact_detected=True,
        ))
        assert event is not None
        assert "reverse_pivot" in event.description

    def test_result_secured_rebound(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(
            rebound_secured_by_boxer_team=True,
        ))
        assert event is not None
        assert "secured_rebound" in event.description

    def test_result_opponent_scored(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(opponent_putback=True))
        assert event is not None
        assert "opponent_scored" in event.description

    def test_reject_far_distance(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(boxer_target_distance_m=3.0))
        assert event is None

    def test_reject_no_contact_no_facing(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(
            body_contact_detected=False, boxer_facing_basket=False,
        ))
        assert event is None

    def test_reject_same_team(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(
            boxer_team_id="team_a", target_team_id="team_a",
        ))
        assert event is None

    def test_reject_low_confidence(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(confidence=0.40))
        assert event is None

    def test_reject_too_late(self):
        det = BoxOutDetector()
        event = det.detect_box_out(_make_input(time_after_shot_sec=6.0))
        assert event is None

    def test_stats(self):
        det = BoxOutDetector()
        det.detect_box_out(_make_input())
        det.detect_box_out(_make_input(boxer_facing_basket=False))
        stats = det.get_box_out_stats()
        assert stats["total"] == 2

    def test_reset(self):
        det = BoxOutDetector()
        det.detect_box_out(_make_input())
        det.reset()
        assert det.total_box_outs_detected == 0
