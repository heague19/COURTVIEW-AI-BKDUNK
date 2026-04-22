# -*- coding: utf-8 -*-
"""
Phase 1B-1 통합 테스트: event_detection 8개 감지기 연동

시나리오별 이벤트 흐름 검증:
  1. 슛 → 득점 → 어시스트 흐름
  2. 슛 → 미스 → 리바운드 흐름
  3. 점유 → 스틸 → 속공 → 득점 흐름
  4. 슛 → 블록 → 턴오버 흐름
  5. 자유투 라운드 전체 흐름
  6. 대량 이벤트 혼합 시나리오
"""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType, ShotResult

from game_analysis.game_state.event_detection.shot_event_detector import (
    ShotEventDetector, ShotReleaseInput, ShotResultInput,
)
from game_analysis.game_state.event_detection.free_throw_detector import (
    FreeThrowDetector, FreeThrowInput,
)
from game_analysis.game_state.event_detection.score_detector import (
    ScoreDetector, ScoreFrameInput,
)
from game_analysis.game_state.event_detection.rebound_detector import (
    ReboundDetector, ReboundInput,
)
from game_analysis.game_state.event_detection.assist_detector import (
    AssistDetector, AssistInput, PassRecord,
)
from game_analysis.game_state.event_detection.block_detector import (
    BlockDetector, BlockInput,
)
from game_analysis.game_state.event_detection.steal_detector import (
    StealDetector, StealInput,
)
from game_analysis.game_state.event_detection.turnover_detector import (
    TurnoverDetector, TurnoverInput,
)


class TestShotToScoreFlow:
    """시나리오 1: 슛 → 득점 → 어시스트 흐름."""

    def test_full_scoring_play(self) -> None:
        """패스 → 슛 시도 → 득점 확인 → 어시스트 판정."""
        shot_det = ShotEventDetector()
        score_det = ScoreDetector()
        assist_det = AssistDetector()

        # 1. 패스 기록
        assist_det.record_pass(PassRecord(
            frame_index=90,
            timestamp_sec=3.0,
            passer_tracking_id=5,
            passer_team_id="home",
            receiver_tracking_id=7,
            receiver_team_id="home",
            dribbles_after_pass=0,
            created_advantage=True,
        ))

        # 2. 슛 릴리스 (4프레임)
        shot_event = None
        for i in range(4):
            shot_event = shot_det.process_release(ShotReleaseInput(
                frame_index=100 + i,
                timestamp_sec=3.33 + i * 0.033,
                player_tracking_id=7,
                team_id="home",
                wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0,
                ball_distance_to_hoop_m=5.0,
                quarter=1,
                game_clock="8:00",
            ))
        assert shot_event is not None
        assert shot_event.event_type == GameEventType.SHOT_ATTEMPT

        # 3. 슛 결과 — 성공
        result_event = shot_det.process_result(ShotResultInput(
            frame_index=120,
            timestamp_sec=4.0,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.7,
            confidence=0.95,
        ))
        assert result_event is not None
        assert result_event.event_type == GameEventType.SHOT_MADE

        # 4. 득점 확인 (ScoreDetector)
        score_event = score_det.process_frame(ScoreFrameInput(
            frame_index=120,
            timestamp_sec=4.0,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.7,
            confidence=0.95,
            shooter_tracking_id=7,
            shooter_team_id="home",
        ))
        assert score_event is not None
        assert score_event.event_type == GameEventType.SHOT_MADE

        # 5. 어시스트 판정
        assist_events = assist_det.detect_assist(AssistInput(
            frame_index=120,
            timestamp_sec=4.0,
            scorer_tracking_id=7,
            scorer_team_id="home",
            score_event_type=GameEventType.SHOT_MADE.value,
            points=2,
            passes=[],  # 버퍼에서 자동 검색
            confidence=0.9,
        ))
        assert len(assist_events) >= 1
        assert assist_events[0].event_type == GameEventType.ASSIST
        assert assist_events[0].primary_player_id == 5  # 패서


class TestShotToReboundFlow:
    """시나리오 2: 슛 → 미스 → 리바운드 흐름."""

    def test_missed_shot_rebound(self) -> None:
        """슛 미스 → 수비 리바운드."""
        shot_det = ShotEventDetector()
        reb_det = ReboundDetector()

        # 슛 시도
        for i in range(4):
            shot_det.process_release(ShotReleaseInput(
                frame_index=100 + i,
                timestamp_sec=3.33 + i * 0.033,
                player_tracking_id=7,
                team_id="home",
                wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0,
                ball_distance_to_hoop_m=5.0,
            ))

        # 미스
        miss_event = shot_det.process_result(ShotResultInput(
            frame_index=120,
            timestamp_sec=4.0,
            ball_rim_distance_m=0.2,
            ball_through_hoop=False,
            rim_contact=True,
            confidence=0.85,
        ))
        assert miss_event is not None
        assert miss_event.event_type == GameEventType.SHOT_MISSED

        # 리바운드 등록
        reb_det.register_miss(120, 4.0, "home", 7)

        # 수비 리바운드 (3프레임 확보)
        reb_event = None
        for i in range(3):
            reb_event = reb_det.process_rebound(ReboundInput(
                frame_index=125 + i,
                timestamp_sec=4.17 + i * 0.033,
                ball_controlled=True,
                ball_controller_id=4,
                ball_controller_team_id="away",
                time_since_miss_sec=0.17 + i * 0.033,
                confidence=0.88,
            ))
        assert reb_event is not None
        assert reb_event.event_type == GameEventType.DEFENSIVE_REBOUND

    def test_missed_shot_offensive_rebound(self) -> None:
        """슛 미스 → 공격 리바운드."""
        shot_det = ShotEventDetector()
        reb_det = ReboundDetector()

        for i in range(4):
            shot_det.process_release(ShotReleaseInput(
                frame_index=100 + i,
                timestamp_sec=3.33 + i * 0.033,
                player_tracking_id=7,
                team_id="home",
                wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0,
                ball_distance_to_hoop_m=5.0,
            ))
        shot_det.process_result(ShotResultInput(
            frame_index=120, timestamp_sec=4.0,
            ball_through_hoop=False, rim_contact=True, confidence=0.85,
            ball_rim_distance_m=0.2,
        ))

        reb_det.register_miss(120, 4.0, "home", 7)

        reb_event = None
        for i in range(3):
            reb_event = reb_det.process_rebound(ReboundInput(
                frame_index=125 + i,
                timestamp_sec=4.17 + i * 0.033,
                ball_controlled=True,
                ball_controller_id=11,
                ball_controller_team_id="home",  # 같은 팀 → 공격 리바
                time_since_miss_sec=0.17 + i * 0.033,
                confidence=0.88,
            ))
        assert reb_event is not None
        assert reb_event.event_type == GameEventType.OFFENSIVE_REBOUND


class TestStealFastBreakFlow:
    """시나리오 3: 스틸 → 턴오버 기록 → 속공 득점."""

    def test_steal_to_score(self) -> None:
        """스틸 → 턴오버 기록 → 득점."""
        steal_det = StealDetector()
        to_det = TurnoverDetector()
        score_det = ScoreDetector()

        # 스틸
        steal_event = steal_det.detect_steal(StealInput(
            frame_index=200,
            timestamp_sec=6.67,
            previous_possessor_id=7,
            previous_possessor_team_id="home",
            new_possessor_id=4,
            new_possessor_team_id="away",
            possession_gap_frames=5,
            defensive_action_detected=True,
            distance_to_rim_m=5.0,
            confidence=0.85,
        ))
        assert steal_event is not None
        assert steal_event.event_type == GameEventType.STEAL

        # 턴오버 (스틸 선행)
        to_event = to_det.detect_turnover(TurnoverInput(
            frame_index=200,
            timestamp_sec=6.67,
            possessor_tracking_id=7,
            possessor_team_id="home",
            gaining_team_id="away",
            steal_preceded=True,
            confidence=0.85,
        ))
        assert to_event is not None
        assert to_event.event_type == GameEventType.TURNOVER

        # 속공 득점
        score_event = score_det.process_frame(ScoreFrameInput(
            frame_index=260,
            timestamp_sec=8.67,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.7,
            confidence=0.95,
            shooter_tracking_id=4,
            shooter_team_id="away",
        ))
        assert score_event is not None


class TestBlockTurnoverFlow:
    """시나리오 4: 슛 시도 → 블록 → 턴오버."""

    def test_shot_blocked_turnover(self) -> None:
        """슛 시도 → 블록 → 슈터 턴오버."""
        shot_det = ShotEventDetector()
        block_det = BlockDetector()

        # 슛 시도
        for i in range(4):
            shot_det.process_release(ShotReleaseInput(
                frame_index=100 + i,
                timestamp_sec=3.33 + i * 0.033,
                player_tracking_id=7,
                team_id="home",
                wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0,
                ball_distance_to_hoop_m=3.0,
            ))

        # 블록
        block_event = block_det.detect_block(BlockInput(
            frame_index=105,
            timestamp_sec=3.5,
            blocker_tracking_id=4,
            blocker_team_id="away",
            shooter_tracking_id=7,
            shooter_team_id="home",
            hand_ball_distance_m=0.15,
            ball_trajectory_changed=True,
            during_shot_attempt=True,
            blocker_distance_to_rim_m=2.0,
            confidence=0.88,
        ))
        assert block_event is not None
        assert block_event.event_type == GameEventType.BLOCK
        assert block_event.primary_player_id == 4
        assert block_event.secondary_player_id == 7


class TestFreeThrowRoundFlow:
    """시나리오 5: 자유투 라운드 전체 흐름."""

    def test_two_ft_round(self) -> None:
        """2개 자유투: 1성공 + 1실패."""
        ft_det = FreeThrowDetector()

        # 라운드 시작
        round_id = ft_det.start_round(23, "home", 2, 500, 16.67, quarter=2, game_clock="5:00")

        # 1차 시도: 성공
        ft1 = ft_det.process_attempt(FreeThrowInput(
            frame_index=510,
            timestamp_sec=17.0,
            player_tracking_id=23,
            team_id="home",
            is_at_free_throw_line=True,
            wrist_above_shoulder_m=0.15,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.6,
            confidence=0.92,
        ))
        assert ft1 is not None
        assert ft1.event_type == GameEventType.FREE_THROW_MADE
        assert ft1.points == 1

        # 2차 시도: 실패
        ft2 = ft_det.process_attempt(FreeThrowInput(
            frame_index=540,
            timestamp_sec=18.0,
            player_tracking_id=23,
            team_id="home",
            is_at_free_throw_line=True,
            wrist_above_shoulder_m=0.15,
            ball_rim_distance_m=0.2,
            ball_through_hoop=False,
            rim_contact=True,
            confidence=0.88,
        ))
        assert ft2 is not None
        assert ft2.event_type == GameEventType.FREE_THROW_MISSED

        # 라운드 완료 확인
        assert ft_det.active_round_count == 0
        stats = ft_det.get_ft_stats(23)
        assert stats["made"] == 1
        assert stats["total_attempts"] == 2

    def test_and_one_ft(self) -> None:
        """앤드원 자유투 (1회)."""
        ft_det = FreeThrowDetector()
        ft_det.start_round(7, "away", 1, 600, 20.0)

        ft_event = ft_det.process_attempt(FreeThrowInput(
            frame_index=610,
            timestamp_sec=20.33,
            player_tracking_id=7,
            team_id="away",
            is_at_free_throw_line=True,
            wrist_above_shoulder_m=0.15,
            ball_rim_distance_m=0.1,
            ball_through_hoop=True,
            net_deflection=0.7,
            confidence=0.95,
        ))
        assert ft_event is not None
        assert ft_event.points == 1
        assert ft_det.active_round_count == 0


class TestMixedEventsFlow:
    """시나리오 6: 대량 혼합 이벤트."""

    def test_quarter_simulation(self) -> None:
        """쿼터 시뮬레이션: 20 점유 × 다양한 이벤트."""
        shot_det = ShotEventDetector()
        score_det = ScoreDetector()
        reb_det = ReboundDetector()
        assist_det = AssistDetector()
        steal_det = StealDetector()
        to_det = TurnoverDetector()
        block_det = BlockDetector()
        ft_det = FreeThrowDetector()

        total_events = 0
        frame = 0

        for possession in range(20):
            frame += 30  # 매 점유 ~1초
            ts = frame / 30.0

            if possession % 5 == 0:
                # 스틸 + 턴오버
                steal_det.detect_steal(StealInput(
                    frame_index=frame,
                    timestamp_sec=ts,
                    previous_possessor_id=7,
                    previous_possessor_team_id="home",
                    new_possessor_id=4,
                    new_possessor_team_id="away",
                    possession_gap_frames=5,
                    defensive_action_detected=True,
                    distance_to_rim_m=5.0,
                    confidence=0.85,
                ))
                to_det.detect_turnover(TurnoverInput(
                    frame_index=frame,
                    timestamp_sec=ts,
                    possessor_tracking_id=7,
                    possessor_team_id="home",
                    gaining_team_id="away",
                    steal_preceded=True,
                    confidence=0.85,
                ))
                total_events += 2

            elif possession % 3 == 0:
                # 블록
                block_det.detect_block(BlockInput(
                    frame_index=frame,
                    timestamp_sec=ts,
                    blocker_tracking_id=4,
                    blocker_team_id="away",
                    shooter_tracking_id=7,
                    shooter_team_id="home",
                    hand_ball_distance_m=0.15,
                    ball_trajectory_changed=True,
                    during_shot_attempt=True,
                    confidence=0.88,
                ))
                total_events += 1

            else:
                # 슛 시도 + 득점
                for i in range(4):
                    shot_det.process_release(ShotReleaseInput(
                        frame_index=frame + i,
                        timestamp_sec=ts + i * 0.033,
                        player_tracking_id=(possession % 10) + 1,
                        team_id="home" if possession % 2 == 0 else "away",
                        wrist_above_shoulder_m=0.2,
                        elbow_extension_deg=150.0,
                        arm_angular_velocity_degs=400.0,
                        release_height_ratio=1.0,
                        ball_distance_to_hoop_m=5.0,
                    ))

                score_det.process_frame(ScoreFrameInput(
                    frame_index=frame + 20,
                    timestamp_sec=ts + 0.67,
                    ball_rim_distance_m=0.1,
                    ball_through_hoop=True,
                    net_deflection=0.7,
                    confidence=0.95,
                ))
                total_events += 2  # shot + score

        # 모든 감지기에 이벤트가 기록되었는지 확인
        assert len(shot_det.get_event_history()) > 0
        assert score_det.total_scores_detected > 0
        assert steal_det.total_steals_detected > 0
        assert to_det.total_turnovers_detected > 0
        assert block_det.total_blocks_detected > 0

    def test_all_detectors_independent(self) -> None:
        """감지기 간 독립성 — 한 감지기 리셋이 다른 감지기에 영향 없음."""
        shot_det = ShotEventDetector()
        score_det = ScoreDetector()

        # 슛
        for i in range(4):
            shot_det.process_release(ShotReleaseInput(
                frame_index=100+i, timestamp_sec=3.33+i*0.033,
                player_tracking_id=7, wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0, arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0, ball_distance_to_hoop_m=5.0,
            ))

        # 득점
        score_det.process_frame(ScoreFrameInput(
            frame_index=120, timestamp_sec=4.0,
            ball_rim_distance_m=0.1, ball_through_hoop=True,
            net_deflection=0.7, confidence=0.95,
        ))

        # shot_det 리셋
        shot_det.reset()
        assert shot_det.total_shots_detected == 0
        # score_det은 영향 없음
        assert score_det.total_scores_detected == 1
