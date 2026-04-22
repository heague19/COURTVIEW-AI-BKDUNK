# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: block_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType
from game_analysis.game_state.event_detection.block_detector import (
    BlockDetector,
    BlockDetectorConfig,
    BlockInput,
    BlockType,
)


class TestBlockDetectorConfig:
    """BlockDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = BlockDetectorConfig()
        assert cfg.hand_ball_contact_proximity_m == 0.3
        assert cfg.min_block_confidence == 0.80
        assert cfg.during_shot_attempt is True

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "block_detection": {
                "criteria": {"hand_ball_contact_proximity_m": 0.25, "min_block_confidence": 0.85},
            },
            "common": {"default_fps": 60},
        }
        cfg = BlockDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.hand_ball_contact_proximity_m == 0.25
        assert cfg.min_block_confidence == 0.85


class TestBlockDetector:
    """BlockDetector 핵심 기능 테스트."""

    def _make_input(self, **kwargs) -> BlockInput:
        defaults = dict(
            frame_index=150,
            timestamp_sec=5.0,
            blocker_tracking_id=4,
            blocker_team_id="away",
            shooter_tracking_id=7,
            shooter_team_id="home",
            hand_ball_distance_m=0.15,
            ball_trajectory_changed=True,
            during_shot_attempt=True,
            blocker_distance_to_rim_m=2.0,
            confidence=0.88,
            quarter=1,
            game_clock="7:00",
        )
        defaults.update(kwargs)
        return BlockInput(**defaults)

    def test_init(self) -> None:
        det = BlockDetector()
        assert det.name == "BlockDetector"
        assert det.total_blocks_detected == 0

    def test_block_detected(self) -> None:
        """블록 감지."""
        det = BlockDetector()
        event = det.detect_block(self._make_input())
        assert event is not None
        assert event.event_type == GameEventType.BLOCK
        assert event.primary_player_id == 4   # blocker
        assert event.secondary_player_id == 7  # shooter

    def test_no_block_same_team(self) -> None:
        """같은 팀 → 블록 불가."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_team_id="home"))
        assert event is None

    def test_no_block_too_far(self) -> None:
        """손-공 거리 초과 → 블록 안됨."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(hand_ball_distance_m=0.5))
        assert event is None

    def test_no_block_no_trajectory_change(self) -> None:
        """궤적 변화 없음 → 블록 안됨."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(ball_trajectory_changed=False))
        assert event is None

    def test_no_block_not_during_shot(self) -> None:
        """슛 시도 중이 아님 → 블록 안됨."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(during_shot_attempt=False))
        assert event is None

    def test_no_block_low_confidence(self) -> None:
        """신뢰도 미달 → 블록 안됨."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(confidence=0.5))
        assert event is None

    def test_chase_down_type(self) -> None:
        """체이스다운 블록."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_from_behind=True))
        assert event is not None
        assert "chase_down" in event.description

    def test_weakside_type(self) -> None:
        """약사이드 블록."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_from_weakside=True))
        assert event is not None
        assert "weakside" in event.description

    def test_post_type(self) -> None:
        """포스트 블록 (림 근접)."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_distance_to_rim_m=1.5))
        assert event is not None
        assert "post" in event.description

    def test_perimeter_type(self) -> None:
        """외곽 블록."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_distance_to_rim_m=6.0))
        assert event is not None
        assert "perimeter" in event.description

    def test_event_history(self) -> None:
        det = BlockDetector()
        det.detect_block(self._make_input())
        history = det.get_event_history()
        assert len(history) == 1

    def test_reset(self) -> None:
        det = BlockDetector()
        det.detect_block(self._make_input())
        det.reset()
        assert det.total_blocks_detected == 0

    def test_from_yaml_factory(self) -> None:
        det = BlockDetector.from_yaml({"block_detection": {}, "common": {}})
        assert det.name == "BlockDetector"

    def test_no_blocker_id(self) -> None:
        """블로커 ID 없음 → 블록 안됨."""
        det = BlockDetector()
        event = det.detect_block(self._make_input(blocker_tracking_id=None))
        assert event is None
