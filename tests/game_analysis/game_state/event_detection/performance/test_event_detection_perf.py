# -*- coding: utf-8 -*-
"""
Phase 1B-1 성능 테스트: event_detection 8개 감지기

Cadence 준수 검증:
  🔴 FRAME (<2ms): ScoreDetector.process_frame()
  🟠 EVENT (<10ms): ShotEventDetector, FreeThrowDetector, ReboundDetector
  🟠 역추적 (<10ms): AssistDetector, BlockDetector, StealDetector, TurnoverDetector
"""

from __future__ import annotations

import time
import statistics
import pytest

from shared.constants.game_rule_constants import GameEventType

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


ITERATIONS: int = 500


class TestScoreDetectorPerf:
    """🔴 FRAME cadence — ScoreDetector <2ms."""

    FRAME_BUDGET_SEC: float = 0.002  # 2ms

    def test_process_frame_under_2ms(self) -> None:
        """process_frame() 평균 < 2ms."""
        det = ScoreDetector()
        durations: list[float] = []
        for i in range(ITERATIONS):
            data = ScoreFrameInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                ball_rim_distance_m=5.0,  # 림에서 먼 → 빠른 리턴
                confidence=0.95,
            )
            t0 = time.perf_counter()
            det.process_frame(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.FRAME_BUDGET_SEC, (
            f"ScoreDetector.process_frame() 평균 {avg*1000:.3f}ms > 2ms"
        )

    def test_process_frame_with_score_under_2ms(self) -> None:
        """득점 감지 포함 process_frame() < 2ms."""
        det = ScoreDetector()
        durations: list[float] = []
        for i in range(ITERATIONS):
            # 매 30프레임마다 득점 시나리오
            if i % 30 == 0:
                data = ScoreFrameInput(
                    frame_index=i,
                    timestamp_sec=i / 30.0,
                    ball_rim_distance_m=0.1,
                    ball_through_hoop=True,
                    net_deflection=0.7,
                    confidence=0.95,
                    shooter_tracking_id=7,
                    shooter_team_id="home",
                )
            else:
                data = ScoreFrameInput(
                    frame_index=i,
                    timestamp_sec=i / 30.0,
                    ball_rim_distance_m=5.0,
                )
            t0 = time.perf_counter()
            det.process_frame(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.FRAME_BUDGET_SEC, (
            f"ScoreDetector(with score) 평균 {avg*1000:.3f}ms > 2ms"
        )


class TestShotEventDetectorPerf:
    """🟠 EVENT cadence — ShotEventDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_process_release_under_10ms(self) -> None:
        det = ShotEventDetector()
        durations: list[float] = []
        for i in range(ITERATIONS):
            data = ShotReleaseInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                player_tracking_id=(i % 10) + 1,
                wrist_above_shoulder_m=0.2,
                elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0,
                release_height_ratio=1.0,
                ball_distance_to_hoop_m=5.0,
            )
            t0 = time.perf_counter()
            det.process_release(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC, (
            f"ShotEventDetector.process_release() 평균 {avg*1000:.3f}ms > 10ms"
        )

    def test_process_result_under_10ms(self) -> None:
        det = ShotEventDetector()
        # 펜딩 슛 생성
        for i in range(4):
            det.process_release(ShotReleaseInput(
                frame_index=i, timestamp_sec=i/30.0, player_tracking_id=1,
                wrist_above_shoulder_m=0.2, elbow_extension_deg=150.0,
                arm_angular_velocity_degs=400.0, release_height_ratio=1.0,
                ball_distance_to_hoop_m=5.0,
            ))

        durations: list[float] = []
        for i in range(ITERATIONS):
            data = ShotResultInput(
                frame_index=10 + i,
                timestamp_sec=0.33 + i / 30.0,
                ball_rim_distance_m=5.0,
            )
            t0 = time.perf_counter()
            det.process_result(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestFreeThrowDetectorPerf:
    """🟡 SPECIAL — FreeThrowDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_process_attempt_under_10ms(self) -> None:
        det = FreeThrowDetector()
        det.start_round(23, "home", 2, 0, 0.0)

        durations: list[float] = []
        for i in range(ITERATIONS):
            data = FreeThrowInput(
                frame_index=10 + i,
                timestamp_sec=0.33 + i * 0.033,
                player_tracking_id=23,
                is_at_free_throw_line=True,
                wrist_above_shoulder_m=0.15,
                ball_rim_distance_m=5.0,  # 림에서 먼 → 빠른 리턴
            )
            t0 = time.perf_counter()
            det.process_attempt(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestReboundDetectorPerf:
    """🟠 EVENT — ReboundDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_process_rebound_under_10ms(self) -> None:
        det = ReboundDetector()

        durations: list[float] = []
        for i in range(ITERATIONS):
            # 매 50회 미스 등록
            if i % 50 == 0:
                det.register_miss(i, i / 30.0, "home", 7)

            data = ReboundInput(
                frame_index=i + 1,
                timestamp_sec=(i + 1) / 30.0,
                ball_controlled=True,
                ball_controller_id=5,
                ball_controller_team_id="away",
                time_since_miss_sec=0.5,
                confidence=0.85,
            )
            t0 = time.perf_counter()
            det.process_rebound(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestAssistDetectorPerf:
    """🟠 역추적 — AssistDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_detect_assist_under_10ms(self) -> None:
        det = AssistDetector()
        durations: list[float] = []

        for i in range(ITERATIONS):
            passes = [PassRecord(
                frame_index=i * 10,
                timestamp_sec=i * 0.5,
                passer_tracking_id=(i % 5) + 1,
                passer_team_id="home",
                receiver_tracking_id=7,
                receiver_team_id="home",
                dribbles_after_pass=0,
                created_advantage=True,
            )]
            data = AssistInput(
                frame_index=i * 10 + 20,
                timestamp_sec=i * 0.5 + 1.0,
                scorer_tracking_id=7,
                scorer_team_id="home",
                score_event_type=GameEventType.SHOT_MADE.value,
                points=2,
                passes=passes,
                confidence=0.9,
            )
            t0 = time.perf_counter()
            det.detect_assist(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestBlockDetectorPerf:
    """🟠 역추적 — BlockDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_detect_block_under_10ms(self) -> None:
        det = BlockDetector()
        durations: list[float] = []

        for i in range(ITERATIONS):
            data = BlockInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                blocker_tracking_id=4,
                blocker_team_id="away",
                shooter_tracking_id=7,
                shooter_team_id="home",
                hand_ball_distance_m=0.15,
                ball_trajectory_changed=True,
                during_shot_attempt=True,
                confidence=0.88,
            )
            t0 = time.perf_counter()
            det.detect_block(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestStealDetectorPerf:
    """🟠 역추적 — StealDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_detect_steal_under_10ms(self) -> None:
        det = StealDetector()
        durations: list[float] = []

        for i in range(ITERATIONS):
            data = StealInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                previous_possessor_id=7,
                previous_possessor_team_id="home",
                new_possessor_id=4,
                new_possessor_team_id="away",
                possession_gap_frames=5,
                defensive_action_detected=True,
                distance_to_rim_m=5.0,
                confidence=0.85,
            )
            t0 = time.perf_counter()
            det.detect_steal(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestTurnoverDetectorPerf:
    """🟠 역추적 — TurnoverDetector <10ms."""

    EVENT_BUDGET_SEC: float = 0.010

    def test_detect_turnover_under_10ms(self) -> None:
        det = TurnoverDetector()
        durations: list[float] = []

        for i in range(ITERATIONS):
            data = TurnoverInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                possessor_tracking_id=(i % 10) + 1,
                possessor_team_id="home",
                gaining_team_id="away",
                was_bad_pass=True,
                nearest_defender_distance_m=3.0,
                confidence=0.80,
            )
            t0 = time.perf_counter()
            det.detect_turnover(data)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC


class TestMemoryGuard:
    """대량 이벤트 누적 후 메모리 안정성."""

    def test_shot_detector_large_volume(self) -> None:
        """1000개 슛 시도 후 메모리 안정."""
        det = ShotEventDetector()
        t0 = time.perf_counter()
        for i in range(1000):
            for j in range(4):
                det.process_release(ShotReleaseInput(
                    frame_index=i * 10 + j,
                    timestamp_sec=(i * 10 + j) / 30.0,
                    player_tracking_id=(i % 10) + 1,
                    wrist_above_shoulder_m=0.2,
                    elbow_extension_deg=150.0,
                    arm_angular_velocity_degs=400.0,
                    release_height_ratio=1.0,
                    ball_distance_to_hoop_m=5.0,
                ))
        elapsed = time.perf_counter() - t0
        assert elapsed < 10.0, f"1000개 슛 시도 {elapsed:.2f}s > 10s"
        # 이력 크기 제한 확인
        assert len(det.get_event_history()) <= 500

    def test_turnover_large_volume(self) -> None:
        """2000개 턴오버 후 이력 크기 제한."""
        det = TurnoverDetector()
        for i in range(2000):
            det.detect_turnover(TurnoverInput(
                frame_index=i,
                timestamp_sec=i / 30.0,
                possessor_tracking_id=(i % 10) + 1,
                possessor_team_id="home",
                gaining_team_id="away",
                was_bad_pass=True,
                confidence=0.80,
            ))
        assert len(det.get_event_history()) <= 500
