# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: rebound_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType
from game_analysis.game_state.event_detection.rebound_detector import (
    ReboundDetector,
    ReboundDetectorConfig,
    ReboundInput,
    ReboundType,
)


class TestReboundDetectorConfig:
    """ReboundDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = ReboundDetectorConfig()
        assert cfg.max_time_after_miss_sec == 5.0
        assert cfg.ball_control_min_frames == 3
        assert cfg.long_rebound_distance_m == 4.0

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "rebound_detection": {
                "trigger": {"max_time_after_miss_sec": 4.0, "ball_control_min_frames": 5},
                "classification": {"long_rebound_distance_m": 5.0},
                "box_out": {"detection_enabled": False},
            },
            "common": {"default_fps": 60},
        }
        cfg = ReboundDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.max_time_after_miss_sec == 4.0
        assert cfg.ball_control_min_frames == 5
        assert cfg.box_out_detection_enabled is False


class TestReboundDetector:
    """ReboundDetector 핵심 기능 테스트."""

    def _make_input(self, **kwargs) -> ReboundInput:
        defaults = dict(
            frame_index=200,
            timestamp_sec=6.67,
            ball_controlled=True,
            ball_controller_id=5,
            ball_controller_team_id="away",
            time_since_miss_sec=1.5,
            player_distance_to_rim_m=2.0,
            confidence=0.88,
            quarter=2,
            game_clock="4:00",
        )
        defaults.update(kwargs)
        return ReboundInput(**defaults)

    def test_init(self) -> None:
        det = ReboundDetector()
        assert det.name == "ReboundDetector"
        assert det.total_rebounds_detected == 0

    def test_no_miss_no_rebound(self) -> None:
        """미스 등록 없이 → 리바운드 안됨."""
        det = ReboundDetector()
        event = det.process_rebound(self._make_input())
        assert event is None

    def test_defensive_rebound(self) -> None:
        """수비 리바운드."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)  # home 팀 미스

        # away 팀 선수가 확보 (3프레임)
        for i in range(3):
            event = det.process_rebound(self._make_input(
                frame_index=190 + i, timestamp_sec=6.33 + i * 0.033,
                ball_controller_team_id="away",
            ))
        assert event is not None
        assert event.event_type == GameEventType.DEFENSIVE_REBOUND
        assert event.primary_player_id == 5

    def test_offensive_rebound(self) -> None:
        """공격 리바운드."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        for i in range(3):
            event = det.process_rebound(self._make_input(
                frame_index=190 + i, timestamp_sec=6.33 + i * 0.033,
                ball_controller_id=11, ball_controller_team_id="home",
            ))
        assert event is not None
        assert event.event_type == GameEventType.OFFENSIVE_REBOUND

    def test_team_rebound_out_of_bounds(self) -> None:
        """팀 리바운드 (아웃오브바운즈)."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        event = det.process_rebound(self._make_input(
            is_out_of_bounds=True, last_touched_team_id="home",
        ))
        assert event is not None
        assert event.event_type == GameEventType.DEFENSIVE_REBOUND

    def test_timeout_no_rebound(self) -> None:
        """미스 후 5초 초과 → 리바운드 안됨."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        event = det.process_rebound(self._make_input(time_since_miss_sec=6.0))
        assert event is None

    def test_not_enough_control_frames(self) -> None:
        """확보 프레임 부족 → 리바운드 미확정."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        # 2프레임만 → 부족
        for i in range(2):
            event = det.process_rebound(self._make_input(frame_index=190 + i))
        assert event is None

    def test_controller_change_resets_count(self) -> None:
        """다른 선수가 확보 → 카운트 리셋."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        det.process_rebound(self._make_input(frame_index=190, ball_controller_id=5))
        det.process_rebound(self._make_input(frame_index=191, ball_controller_id=5))
        # 다른 선수로 전환 → 리셋
        det.process_rebound(self._make_input(frame_index=192, ball_controller_id=8))
        event = det.process_rebound(self._make_input(frame_index=193, ball_controller_id=8))
        assert event is None  # 8번 선수 2프레임만

    def test_long_rebound(self) -> None:
        """장거리 리바운드 표시."""
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)

        for i in range(3):
            event = det.process_rebound(self._make_input(
                frame_index=190 + i, player_distance_to_rim_m=5.0,
            ))
        assert event is not None
        assert "장거리" in event.description

    def test_rebound_stats(self) -> None:
        """리바운드 통계."""
        det = ReboundDetector()
        # 수비 리바운드
        det.register_miss(180, 6.0, "home", 7)
        for i in range(3):
            det.process_rebound(self._make_input(
                frame_index=190+i, ball_controller_team_id="away",
            ))
        stats = det.get_rebound_stats()
        assert stats["defensive"] == 1
        assert stats["total"] == 1

    def test_reset(self) -> None:
        det = ReboundDetector()
        det.register_miss(180, 6.0, "home", 7)
        det.reset()
        assert det.total_rebounds_detected == 0
        event = det.process_rebound(self._make_input())
        assert event is None  # miss context cleared

    def test_from_yaml_factory(self) -> None:
        det = ReboundDetector.from_yaml({"rebound_detection": {}, "common": {}})
        assert det.name == "ReboundDetector"
