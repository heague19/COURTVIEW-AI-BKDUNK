# -*- coding: utf-8 -*-
"""Phase 1B-1 단위 테스트: shot_event_detector.py"""

from __future__ import annotations

import pytest
from uuid import UUID

from shared.constants.game_rule_constants import GameEventType, ShotType, ShotResult
from game_analysis.game_state.event_detection.shot_event_detector import (
    ShotEventDetector,
    ShotEventDetectorConfig,
    ShotReleaseInput,
    ShotResultInput,
)


class TestShotEventDetectorConfig:
    """ShotEventDetectorConfig 테스트."""

    def test_default_values(self) -> None:
        cfg = ShotEventDetectorConfig()
        assert cfg.wrist_above_shoulder_min_m == 0.1
        assert cfg.elbow_extension_min_deg == 120.0
        assert cfg.arm_velocity_min_degs == 300.0
        assert cfg.min_shooting_motion_frames == 4
        assert cfg.ball_rim_proximity_m == 0.3
        assert cfg.three_point_distance_fiba_m == 6.75
        assert cfg.fps == 30.0

    def test_from_yaml(self) -> None:
        yaml_cfg = {
            "shot_detection": {
                "release_detection": {
                    "wrist_above_shoulder_min_m": 0.15,
                    "min_shooting_motion_frames": 5,
                },
                "result_detection": {"ball_rim_proximity_m": 0.25},
                "type_classification": {"layup_max_distance_m": 2.5},
                "multi_view": {"min_cameras_for_confirmation": 3},
            },
            "common": {"default_fps": 60},
        }
        cfg = ShotEventDetectorConfig.from_yaml(yaml_cfg)
        assert cfg.wrist_above_shoulder_min_m == 0.15
        assert cfg.min_shooting_motion_frames == 5
        assert cfg.ball_rim_proximity_m == 0.25
        assert cfg.layup_max_distance_m == 2.5
        assert cfg.min_cameras_for_confirmation == 3
        assert cfg.fps == 60.0


class TestShotEventDetector:
    """ShotEventDetector 핵심 기능 테스트."""

    def _make_release_input(self, **kwargs) -> ShotReleaseInput:
        defaults = dict(
            frame_index=100,
            timestamp_sec=3.33,
            player_tracking_id=7,
            team_id="home",
            wrist_above_shoulder_m=0.2,
            elbow_extension_deg=150.0,
            arm_angular_velocity_degs=400.0,
            release_height_ratio=1.0,
            ball_distance_to_hoop_m=5.0,
            player_court_x=0.3,
            player_court_y=0.5,
            quarter=1,
            game_clock="8:00",
        )
        defaults.update(kwargs)
        return ShotReleaseInput(**defaults)

    def test_init_default(self) -> None:
        det = ShotEventDetector()
        assert det.name == "ShotEventDetector"
        assert det.version == "1.0.0"
        assert det.pending_shot_count == 0
        assert det.total_shots_detected == 0

    def test_release_detection_single_frame_no_event(self) -> None:
        """단일 프레임은 슛 확정 불가 (최소 4프레임)."""
        det = ShotEventDetector()
        event = det.process_release(self._make_release_input())
        assert event is None

    def test_release_detection_min_frames(self) -> None:
        """최소 프레임 수 충족 시 SHOT_ATTEMPT 이벤트 생성."""
        det = ShotEventDetector()
        event = None
        for i in range(4):
            event = det.process_release(self._make_release_input(frame_index=100 + i))
        assert event is not None
        assert event.event_type == GameEventType.SHOT_ATTEMPT
        assert event.primary_player_id == 7
        assert event.team_id == "home"
        assert det.pending_shot_count == 1

    def test_release_below_threshold_resets_buffer(self) -> None:
        """기준 미달 프레임이 오면 버퍼 리셋."""
        det = ShotEventDetector()
        det.process_release(self._make_release_input(frame_index=100))
        det.process_release(self._make_release_input(frame_index=101))
        # 기준 미달 → 리셋
        det.process_release(self._make_release_input(frame_index=102, wrist_above_shoulder_m=0.01))
        # 다시 3프레임 → 아직 부족
        for i in range(3):
            event = det.process_release(self._make_release_input(frame_index=103 + i))
        assert event is None  # 4프레임 충족 안됨

    def test_result_made_shot(self) -> None:
        """슛 성공 판정."""
        det = ShotEventDetector()
        # 릴리스
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))

        # 결과: 성공
        result_event = det.process_result(ShotResultInput(
            frame_index=120,
            timestamp_sec=4.0,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.7,
            confidence=0.95,
        ))
        assert result_event is not None
        assert result_event.event_type == GameEventType.SHOT_MADE
        assert result_event.points == 2
        assert det.pending_shot_count == 0

    def test_result_missed_shot(self) -> None:
        """슛 미스 판정."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))

        result_event = det.process_result(ShotResultInput(
            frame_index=120,
            timestamp_sec=4.0,
            ball_rim_distance_m=0.2,
            ball_through_hoop=False,
            rim_contact=True,
            confidence=0.85,
        ))
        assert result_event is not None
        assert result_event.event_type == GameEventType.SHOT_MISSED
        assert result_event.points == 0

    def test_result_timeout_auto_miss(self) -> None:
        """타임아웃 시 자동 미스 처리."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))

        # 45프레임 초과 → 타임아웃
        result = det.process_result(ShotResultInput(
            frame_index=200,
            timestamp_sec=6.67,
            ball_rim_distance_m=0.1,
        ))
        assert result is not None
        assert result.event_type == GameEventType.SHOT_MISSED

    def test_three_pointer_classification(self) -> None:
        """3점슛 유형 분류."""
        det = ShotEventDetector()
        event = None
        for i in range(4):
            event = det.process_release(self._make_release_input(
                frame_index=100 + i,
                ball_distance_to_hoop_m=7.5,
            ))
        assert event is not None
        assert "슛 시도" in event.description

    def test_layup_classification(self) -> None:
        """레이업 유형 분류."""
        det = ShotEventDetector()
        event = None
        for i in range(4):
            event = det.process_release(self._make_release_input(
                frame_index=100 + i,
                ball_distance_to_hoop_m=1.5,
            ))
        assert event is not None
        assert "layup" in event.description.lower() or "슛 시도" in event.description

    def test_expire_pending_shots(self) -> None:
        """만료된 펜딩 슛 정리."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))
        assert det.pending_shot_count == 1

        expired = det.expire_pending_shots(current_frame=200)
        assert len(expired) == 1
        assert expired[0].event_type == GameEventType.SHOT_MISSED
        assert det.pending_shot_count == 0

    def test_event_history(self) -> None:
        """이벤트 이력 조회."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))
        history = det.get_event_history()
        assert len(history) == 1
        assert history[0].event_type == GameEventType.SHOT_ATTEMPT

    def test_reset(self) -> None:
        """리셋 후 상태 초기화."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))
        det.reset()
        assert det.pending_shot_count == 0
        assert det.total_shots_detected == 0
        assert len(det.get_event_history()) == 0

    def test_from_yaml_factory(self) -> None:
        """from_yaml 팩토리."""
        det = ShotEventDetector.from_yaml({"shot_detection": {}, "common": {}})
        assert det.name == "ShotEventDetector"

    def test_multiple_players(self) -> None:
        """다수 선수 동시 슈팅 모션."""
        det = ShotEventDetector()
        # 선수 7: 3프레임
        for i in range(3):
            det.process_release(self._make_release_input(frame_index=100+i, player_tracking_id=7))
        # 선수 11: 4프레임 → 확정
        for i in range(4):
            event = det.process_release(self._make_release_input(frame_index=100+i, player_tracking_id=11))
        assert event is not None
        assert event.primary_player_id == 11
        # 선수 7: 1프레임 더 → 아직 4프레임 → 확정
        event7 = det.process_release(self._make_release_input(frame_index=103, player_tracking_id=7))
        assert event7 is not None
        assert event7.primary_player_id == 7

    def test_get_shot_attempts_dto(self) -> None:
        """ShotAttempt DTO 이력."""
        det = ShotEventDetector()
        for i in range(4):
            det.process_release(self._make_release_input(frame_index=100 + i))
        det.process_result(ShotResultInput(
            frame_index=120, timestamp_sec=4.0,
            ball_rim_distance_m=0.1, ball_through_hoop=True,
            net_deflection=0.7, confidence=0.95,
        ))
        attempts = det.get_shot_attempts()
        assert len(attempts) == 1
        assert attempts[0].result == ShotResult.MADE
        assert attempts[0].points == 2
