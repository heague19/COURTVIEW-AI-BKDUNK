# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: free_throw_detector.py"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType, ShotType, ShotResult
from game_analysis.game_state.event_detection.free_throw_detector import (
    FreeThrowDetector,
    FreeThrowDetectorConfig,
    FreeThrowInput,
)


class TestFreeThrowDetectorConfig:
    """FreeThrowDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = FreeThrowDetectorConfig()
        assert cfg.shooter_in_arc is True
        assert cfg.max_motion_before_release_m == 0.3
        assert cfg.max_ft_per_round == 3
        assert cfg.round_timeout_sec == 30.0

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "score_detection": {
                "free_throw": {"max_motion_before_release_m": 0.5},
                "confirmation": {"min_confidence": 0.80},
            },
            "common": {"default_fps": 60},
        }
        cfg = FreeThrowDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.max_motion_before_release_m == 0.5
        assert cfg.made_shot_confidence == 0.80
        assert cfg.fps == 60.0


class TestFreeThrowDetector:
    """FreeThrowDetector 핵심 기능 테스트."""

    def _make_ft_input(self, **kwargs) -> FreeThrowInput:
        defaults = dict(
            frame_index=500,
            timestamp_sec=16.67,
            player_tracking_id=23,
            team_id="home",
            is_at_free_throw_line=True,
            distance_from_ft_line_m=0.1,
            player_movement_m=0.05,
            wrist_above_shoulder_m=0.15,
            elbow_extension_deg=145.0,
            ball_rim_distance_m=0.2,
            ball_through_hoop=True,
            net_deflection=0.6,
            confidence=0.92,
            quarter=2,
            game_clock="5:00",
        )
        defaults.update(kwargs)
        return FreeThrowInput(**defaults)

    def test_init(self) -> None:
        det = FreeThrowDetector()
        assert det.name == "FreeThrowDetector"
        assert det.version == "1.0.0"
        assert det.active_round_count == 0

    def test_start_round(self) -> None:
        """자유투 라운드 시작."""
        det = FreeThrowDetector()
        round_id = det.start_round(
            player_tracking_id=23, team_id="home",
            total_attempts=2, frame_index=500, timestamp_sec=16.67,
        )
        assert det.active_round_count == 1
        status = det.get_round_status(23)
        assert status is not None
        assert status["total_attempts"] == 2
        assert status["completed"] == 0

    def test_ft_made(self) -> None:
        """자유투 성공."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        event = det.process_attempt(self._make_ft_input())
        assert event is not None
        assert event.event_type == GameEventType.FREE_THROW_MADE
        assert event.points == 1

    def test_ft_missed(self) -> None:
        """자유투 실패."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        event = det.process_attempt(self._make_ft_input(
            ball_through_hoop=False, rim_contact=True,
        ))
        assert event is not None
        assert event.event_type == GameEventType.FREE_THROW_MISSED
        assert event.points == 0

    def test_round_completion(self) -> None:
        """라운드 완료 (2/2)."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)

        # 1/2 성공
        det.process_attempt(self._make_ft_input(frame_index=510, timestamp_sec=17.0))
        assert det.active_round_count == 1
        status = det.get_round_status(23)
        assert status["completed"] == 1

        # 2/2 실패
        det.process_attempt(self._make_ft_input(
            frame_index=520, timestamp_sec=17.33,
            ball_through_hoop=False, rim_contact=True,
        ))
        assert det.active_round_count == 0  # 라운드 완료

    def test_three_ft_and_one(self) -> None:
        """앤드원 자유투 (1회)."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 1, 500, 16.67)
        event = det.process_attempt(self._make_ft_input())
        assert event is not None
        assert event.points == 1
        assert det.active_round_count == 0

    def test_no_round_no_event(self) -> None:
        """라운드 없이 시도 → 이벤트 없음."""
        det = FreeThrowDetector()
        event = det.process_attempt(self._make_ft_input())
        assert event is None

    def test_wrong_player_no_event(self) -> None:
        """다른 선수 시도 → 이벤트 없음."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        event = det.process_attempt(self._make_ft_input(player_tracking_id=99))
        assert event is None

    def test_round_timeout(self) -> None:
        """라운드 타임아웃."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        # 30초 초과
        event = det.process_attempt(self._make_ft_input(timestamp_sec=50.0))
        assert event is None
        assert det.active_round_count == 0

    def test_movement_exceeds_limit(self) -> None:
        """이동량 초과 시 이벤트 없음."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        event = det.process_attempt(self._make_ft_input(player_movement_m=0.5))
        assert event is None

    def test_ft_stats(self) -> None:
        """자유투 통계."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        det.process_attempt(self._make_ft_input(frame_index=510, timestamp_sec=17.0))
        det.process_attempt(self._make_ft_input(
            frame_index=520, timestamp_sec=17.33,
            ball_through_hoop=False, rim_contact=True,
        ))
        stats = det.get_ft_stats(player_tracking_id=23)
        assert stats["total_attempts"] == 2
        assert stats["made"] == 1
        assert stats["percentage"] == 50.0

    def test_expire_rounds(self) -> None:
        """타임아웃 라운드 일괄 정리."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 10.0)
        det.start_round(11, "away", 2, 510, 10.5)
        assert det.active_round_count == 2
        det.expire_rounds(current_timestamp_sec=45.0)
        assert det.active_round_count == 0

    def test_reset(self) -> None:
        """리셋 후 상태 초기화."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 500, 16.67)
        det.process_attempt(self._make_ft_input())
        det.reset()
        assert det.active_round_count == 0
        assert det.total_ft_detected == 0

    def test_from_yaml_factory(self) -> None:
        det = FreeThrowDetector.from_yaml({"score_detection": {}, "common": {}})
        assert det.name == "FreeThrowDetector"

    def test_max_attempts_clamped(self) -> None:
        """배정 자유투 수 클램핑 (1~3)."""
        det = FreeThrowDetector()
        det.start_round(23, "home", 5, 500, 16.67)  # 5 → 3
        status = det.get_round_status(23)
        assert status["total_attempts"] == 3
