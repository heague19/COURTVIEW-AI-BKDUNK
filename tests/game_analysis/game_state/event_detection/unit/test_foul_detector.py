# -*- coding: utf-8 -*-
"""FoulDetector 단위 테스트 — 15 tests."""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.foul_detector import (
    FoulDetector,
    FoulDetectorConfig,
    FoulInput,
    ContactType,
)
from shared.constants.game_rule_constants import GameEventType


# =============================================================================
# 헬퍼
# =============================================================================
def _make_input(**overrides) -> FoulInput:
    defaults = dict(
        frame_index=100,
        timestamp_sec=3.33,
        fouling_player_id=5,
        fouling_team_id="team_a",
        fouled_player_id=10,
        fouled_team_id="team_b",
        body_overlap_ratio=0.4,
        velocity_change_ms=0.5,
        acceleration_spike_ms2=5.0,
        contact_duration_frames=3,
        confidence=0.80,
        quarter=1,
        game_clock="08:30",
    )
    defaults.update(overrides)
    return FoulInput(**defaults)


# =============================================================================
# 테스트
# =============================================================================
class TestFoulDetector:
    """FoulDetector 단위 테스트."""

    def test_init_default(self):
        det = FoulDetector()
        assert det.name == "FoulDetector"
        assert det.version == "1.0.0"
        assert det.total_fouls_detected == 0

    def test_detect_body_overlap_foul(self):
        det = FoulDetector()
        inp = _make_input(body_overlap_ratio=0.5)
        event = det.detect_foul(inp)
        assert event is not None
        assert event.event_type == GameEventType.PERSONAL_FOUL

    def test_detect_velocity_change_foul(self):
        det = FoulDetector()
        inp = _make_input(body_overlap_ratio=0.1, velocity_change_ms=2.0)
        event = det.detect_foul(inp)
        assert event is not None

    def test_detect_acceleration_spike_foul(self):
        det = FoulDetector()
        inp = _make_input(body_overlap_ratio=0.1, acceleration_spike_ms2=20.0)
        event = det.detect_foul(inp)
        assert event is not None

    def test_detect_arm_contact_foul(self):
        det = FoulDetector()
        inp = _make_input(body_overlap_ratio=0.1, arm_contact_detected=True)
        event = det.detect_foul(inp)
        assert event is not None

    def test_reject_no_contact(self):
        det = FoulDetector()
        inp = _make_input(body_overlap_ratio=0.1, velocity_change_ms=0.5, acceleration_spike_ms2=5.0)
        event = det.detect_foul(inp)
        assert event is None

    def test_reject_low_confidence(self):
        det = FoulDetector()
        inp = _make_input(confidence=0.50)
        event = det.detect_foul(inp)
        assert event is None

    def test_reject_same_team(self):
        det = FoulDetector()
        inp = _make_input(fouling_team_id="team_a", fouled_team_id="team_a")
        event = det.detect_foul(inp)
        assert event is None

    def test_reject_short_contact(self):
        det = FoulDetector()
        inp = _make_input(contact_duration_frames=1)
        event = det.detect_foul(inp)
        assert event is None

    def test_technical_foul_dead_ball(self):
        det = FoulDetector()
        inp = _make_input(is_dead_ball=True, confidence=0.90)
        event = det.detect_foul(inp)
        assert event is not None
        assert event.event_type == GameEventType.TECHNICAL_FOUL

    def test_offensive_foul_hip_contact(self):
        det = FoulDetector()
        inp = _make_input(hip_contact_detected=True, during_shot_attempt=False)
        event = det.detect_foul(inp)
        assert event is not None
        assert event.event_type == GameEventType.OFFENSIVE_FOUL

    def test_shooting_foul_description(self):
        det = FoulDetector()
        inp = _make_input(during_shot_attempt=True)
        event = det.detect_foul(inp)
        assert event is not None
        assert "슈팅 중" in event.description

    def test_foul_stats(self):
        det = FoulDetector()
        det.detect_foul(_make_input())
        det.detect_foul(_make_input(is_dead_ball=True, confidence=0.90))
        stats = det.get_foul_stats()
        assert stats["total"] == 2
        assert stats["personal"] >= 1

    def test_reset(self):
        det = FoulDetector()
        det.detect_foul(_make_input())
        det.reset()
        assert det.total_fouls_detected == 0

    def test_from_yaml(self):
        cfg = {
            "foul_detection": {
                "contact": {"body_overlap_threshold": 0.25},
                "confidence": {"min_for_call": 0.80},
            },
            "common": {"default_fps": 60},
        }
        det = FoulDetector.from_yaml(cfg)
        assert det._config.body_overlap_threshold == 0.25
        assert det._config.fps == 60.0
