# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: steal_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType
from game_analysis.game_state.event_detection.steal_detector import (
    StealDetector,
    StealDetectorConfig,
    StealInput,
    StealType,
)


class TestStealDetectorConfig:
    """StealDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = StealDetectorConfig()
        assert cfg.max_possession_gap_frames == 10
        assert cfg.min_steal_confidence == 0.75

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "steal_detection": {
                "criteria": {"max_possession_gap_frames": 15, "min_steal_confidence": 0.80},
            },
            "common": {"default_fps": 60},
        }
        cfg = StealDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.max_possession_gap_frames == 15
        assert cfg.min_steal_confidence == 0.80


class TestStealDetector:
    """StealDetector 핵심 기능 테스트."""

    def _make_input(self, **kwargs) -> StealInput:
        defaults = dict(
            frame_index=200,
            timestamp_sec=6.67,
            previous_possessor_id=7,
            previous_possessor_team_id="home",
            new_possessor_id=4,
            new_possessor_team_id="away",
            possession_gap_frames=5,
            defensive_action_detected=True,
            steal_court_x=0.3,
            steal_court_y=0.5,
            distance_to_rim_m=5.0,
            confidence=0.85,
            quarter=2,
            game_clock="5:00",
        )
        defaults.update(kwargs)
        return StealInput(**defaults)

    def test_init(self) -> None:
        det = StealDetector()
        assert det.name == "StealDetector"
        assert det.total_steals_detected == 0

    def test_steal_detected(self) -> None:
        """스틸 감지."""
        det = StealDetector()
        event = det.detect_steal(self._make_input())
        assert event is not None
        assert event.event_type == GameEventType.STEAL
        assert event.primary_player_id == 4   # stealer
        assert event.secondary_player_id == 7  # victim

    def test_no_steal_same_team(self) -> None:
        """같은 팀 전환 → 스틸 안됨."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(new_possessor_team_id="home"))
        assert event is None

    def test_no_steal_gap_exceeded(self) -> None:
        """갭 초과 → 스틸 안됨."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(possession_gap_frames=15))
        assert event is None

    def test_no_steal_low_confidence(self) -> None:
        """신뢰도 미달 → 스틸 안됨."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(confidence=0.5))
        assert event is None

    def test_no_steal_no_defensive_action(self) -> None:
        """수비 행위 미감지 → 스틸 안됨."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(
            defensive_action_detected=False,
            hand_in_passing_lane=False,
            active_hands_detected=False,
        ))
        assert event is None

    def test_steal_with_passing_lane(self) -> None:
        """패싱 레인 손 감지로도 스틸 가능."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(
            defensive_action_detected=False,
            hand_in_passing_lane=True,
        ))
        assert event is not None

    def test_on_ball_steal_type(self) -> None:
        """온볼 스틸 유형."""
        det = StealDetector()
        event = det.detect_steal(self._make_input())
        assert event is not None
        assert "on_ball_steal" in event.description

    def test_passing_lane_steal_type(self) -> None:
        """패싱 레인 스틸 유형."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(ball_was_in_air=True))
        assert event is not None
        assert "passing_lane" in event.description

    def test_post_steal_type(self) -> None:
        """포스트 스틸 유형."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(is_in_post=True))
        assert event is not None
        assert "post_steal" in event.description

    def test_event_history(self) -> None:
        det = StealDetector()
        det.detect_steal(self._make_input())
        assert len(det.get_event_history()) == 1

    def test_reset(self) -> None:
        det = StealDetector()
        det.detect_steal(self._make_input())
        det.reset()
        assert det.total_steals_detected == 0

    def test_from_yaml_factory(self) -> None:
        det = StealDetector.from_yaml({"steal_detection": {}, "common": {}})
        assert det.name == "StealDetector"

    def test_no_team_info(self) -> None:
        """팀 정보 없으면 스틸 안됨."""
        det = StealDetector()
        event = det.detect_steal(self._make_input(previous_possessor_team_id=""))
        assert event is None
