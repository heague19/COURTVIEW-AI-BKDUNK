# -*- coding: utf-8 -*-
"""Phase 1B-2 이벤트 감지기 통합 테스트 — 8 tests.

Phase 1B 후반 8개 감지기 간 시나리오 통합 검증.
"""
from __future__ import annotations

import pytest

from game_analysis.game_state.event_detection.foul_detector import FoulDetector, FoulInput
from game_analysis.game_state.event_detection.possession_tracker import (
    PossessionTracker, PossessionFrameInput, PossessionState,
)
from game_analysis.game_state.event_detection.dead_ball_detector import (
    DeadBallDetector, DeadBallFrameInput,
)
from game_analysis.game_state.event_detection.screen_detector import ScreenDetector, ScreenInput
from game_analysis.game_state.event_detection.fast_break_detector import (
    FastBreakDetector, FastBreakInput,
)
from game_analysis.game_state.event_detection.drive_detector import DriveDetector, DriveInput
from game_analysis.game_state.event_detection.box_out_detector import BoxOutDetector, BoxOutInput
from game_analysis.game_state.event_detection.jump_ball_detector import (
    JumpBallDetector, JumpBallInput,
)


class TestPhase1B2Integration:
    """Phase 1B-2 통합 테스트."""

    def test_scenario_foul_triggers_dead_ball(self):
        """시나리오: 파울 → 데드볼."""
        foul_det = FoulDetector()
        dead_det = DeadBallDetector()

        # 파울 감지
        foul_event = foul_det.detect_foul(FoulInput(
            frame_index=100, timestamp_sec=3.33,
            fouling_player_id=5, fouling_team_id="team_a",
            fouled_player_id=10, fouled_team_id="team_b",
            body_overlap_ratio=0.5, contact_duration_frames=3,
            confidence=0.80,
        ))
        assert foul_event is not None

        # 데드볼 전환
        for i in range(10):
            dead_det.process_frame(DeadBallFrameInput(
                frame_index=100 + i, timestamp_sec=3.33 + i / 30.0,
                foul_detected=True, game_clock_running=False,
                confidence=0.85,
            ))
        assert dead_det.is_dead_ball

    def test_scenario_possession_transition_to_fast_break(self):
        """시나리오: 점유 전환 → 속공."""
        poss_det = PossessionTracker()
        fb_det = FastBreakDetector()

        # A팀 점유 확립
        for i in range(6):
            poss_det.process_frame(PossessionFrameInput(
                frame_index=i, timestamp_sec=i / 30.0,
                ball_holder_tracking_id=7, ball_holder_team_id="team_a",
                ball_is_controlled=True, confidence=0.85,
            ))

        # B팀으로 전환 (스틸)
        for i in range(6):
            poss_det.process_frame(PossessionFrameInput(
                frame_index=50 + i, timestamp_sec=(50 + i) / 30.0,
                ball_holder_tracking_id=11, ball_holder_team_id="team_b",
                ball_is_controlled=True, confidence=0.85,
            ))
        assert poss_det.current_team_id == "team_b"

        # 속공 등록 → 실행
        fb_det.register_transition(FastBreakInput(
            frame_index=56, timestamp_sec=56 / 30.0,
            attacking_team_id="team_b", confidence=0.80,
        ))
        event = fb_det.process_event(FastBreakInput(
            frame_index=100, timestamp_sec=100 / 30.0,
            attacking_team_id="team_b",
            ball_speed_ms=4.5,
            attackers_ahead_of_ball=2, defenders_in_frontcourt=1,
            ball_handler_direction_to_rim=True,
            shot_attempted=True, shot_made=True,
            confidence=0.80,
        ))
        assert event is not None
        assert "속공" in event.description

    def test_scenario_screen_to_drive(self):
        """시나리오: 스크린 → 드라이브."""
        screen_det = ScreenDetector()
        drive_det = DriveDetector()

        # 스크린 설정
        screen_event = screen_det.detect_screen(ScreenInput(
            frame_index=100, timestamp_sec=3.33,
            screener_tracking_id=4, screener_team_id="team_a",
            cutter_tracking_id=7, cutter_has_ball=True,
            screener_speed_ms=0.2,
            screener_defender_distance_m=0.4, screener_angle_deg=90.0,
            hold_duration_sec=0.8, confidence=0.80,
        ))
        assert screen_event is not None

        # 핸들러 드라이브 시작
        drive_det.process_event(DriveInput(
            frame_index=110, timestamp_sec=3.67,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=3.5, direction_to_rim_deg=10.0,
            confidence=0.80,
        ))
        assert drive_det.is_drive_active

        # 드라이브 완료 (킥아웃)
        drive_event = drive_det.process_event(DriveInput(
            frame_index=140, timestamp_sec=4.67,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=2.5,
            drive_distance_m=2.5,
            pass_made=True,
            confidence=0.80,
        ))
        assert drive_event is not None
        assert "kickout" in drive_event.description

    def test_scenario_jump_ball_starts_possession(self):
        """시나리오: 점프볼 → 점유 시작."""
        jb_det = JumpBallDetector()
        poss_det = PossessionTracker()

        # 점프볼
        jb_event = jb_det.detect_jump_ball(JumpBallInput(
            frame_index=0, timestamp_sec=0.0,
            jumper_a_tracking_id=5, jumper_a_team_id="team_home",
            jumper_b_tracking_id=10, jumper_b_team_id="team_away",
            jumper_distance_to_center_m=1.0,
            two_players_facing=True, referee_toss_detected=True,
            ball_upward_velocity_ms=5.0,
            ball_tipped_to_team_id="team_home",
            is_tip_off=True, confidence=0.85,
        ))
        assert jb_event is not None

        # 홈팀 점유 시작
        for i in range(6):
            poss_det.process_frame(PossessionFrameInput(
                frame_index=10 + i, timestamp_sec=(10 + i) / 30.0,
                ball_holder_tracking_id=5, ball_holder_team_id="team_home",
                ball_is_controlled=True, confidence=0.85,
            ))
        assert poss_det.current_team_id == "team_home"

    def test_scenario_shot_miss_box_out(self):
        """시나리오: 슛 미스 → 박스아웃."""
        box_det = BoxOutDetector()

        # 박스아웃 (슛 후 0.3초)
        event = box_det.detect_box_out(BoxOutInput(
            frame_index=110, timestamp_sec=3.67,
            boxer_tracking_id=5, boxer_team_id="team_a",
            target_tracking_id=10, target_team_id="team_b",
            boxer_target_distance_m=1.0,
            body_contact_detected=True, boxer_facing_basket=True,
            time_after_shot_sec=0.3,
            rebound_secured_by_boxer_team=True,
            confidence=0.75,
        ))
        assert event is not None
        assert "secured_rebound" in event.description

    def test_scenario_dead_ball_to_live(self):
        """시나리오: 데드볼 → 라이브볼 전환."""
        dead_det = DeadBallDetector()

        # 데드볼 진입
        for i in range(10):
            dead_det.process_frame(DeadBallFrameInput(
                frame_index=i, timestamp_sec=i / 30.0,
                game_clock_running=False, confidence=0.85,
            ))
        assert dead_det.is_dead_ball

        # 라이브볼 전환
        for i in range(15):
            dead_det.process_frame(DeadBallFrameInput(
                frame_index=100 + i, timestamp_sec=(100 + i) / 30.0,
                game_clock_running=True, ball_is_live=True,
                ball_in_play=True, confidence=0.85,
            ))
        assert not dead_det.is_dead_ball

    def test_scenario_all_detectors_reset(self):
        """시나리오: 전체 감지기 리셋 (경기 시작 준비)."""
        detectors = [
            FoulDetector(),
            PossessionTracker(),
            DeadBallDetector(),
            ScreenDetector(),
            FastBreakDetector(),
            DriveDetector(),
            BoxOutDetector(),
            JumpBallDetector(),
        ]
        for det in detectors:
            det.reset()
            history = det.get_event_history()
            assert len(history) == 0

    def test_scenario_drive_to_foul(self):
        """시나리오: 드라이브 → 파울 → 데드볼."""
        drive_det = DriveDetector()
        foul_det = FoulDetector()

        # 드라이브 시작
        drive_det.process_event(DriveInput(
            frame_index=100, timestamp_sec=3.33,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=3.0, direction_to_rim_deg=10.0,
            confidence=0.80,
        ))
        assert drive_det.is_drive_active

        # 드라이브 중 파울 유도
        drive_event = drive_det.process_event(DriveInput(
            frame_index=120, timestamp_sec=4.0,
            handler_tracking_id=7, handler_team_id="team_a",
            handler_speed_ms=2.5,
            drive_distance_m=2.0,
            foul_drawn=True,
            confidence=0.80,
        ))
        assert drive_event is not None
        assert "foul_drawn" in drive_event.description

        # 파울 기록
        foul_event = foul_det.detect_foul(FoulInput(
            frame_index=120, timestamp_sec=4.0,
            fouling_player_id=11, fouling_team_id="team_b",
            fouled_player_id=7, fouled_team_id="team_a",
            body_overlap_ratio=0.4, contact_duration_frames=3,
            during_shot_attempt=True, confidence=0.80,
        ))
        assert foul_event is not None
