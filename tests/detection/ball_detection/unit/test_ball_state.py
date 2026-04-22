# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/unit
파일: test_ball_state.py
설명: BallStateMachine 단위 테스트
      - 9-상태 FSM 전이 검증
      - 유효/무효 전이 매트릭스 검증
      - 소유권 판정, 비행 상태, 멀티뷰 합의
      - 에지 케이스: None 감지, 미초기화, 아웃오브바운드

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from shared.constants.ball_constants import (
    BALL_STATE_FLIGHT_SPEED_PX,
    BALL_STATE_HELD_SPEED_PX,
    BALL_STATE_MIN_POSSESSION_FRAMES,
    BALL_STATE_POSSESSION_DISTANCE_PX,
    BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX,
    BallState,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import Point2D

from detection.ball_detection.ball_state import (
    BallStateMachine,
    BallStateMachineConfig,
    PlayerPosition,
    _VALID_TRANSITIONS,
)


# =============================================================================
# 초기화 테스트
# =============================================================================

class TestBallStateMachineInit:
    """BallStateMachine 초기화 테스트."""

    def test_기본_생성_시_상태_LOST(self):
        """생성 직후 상태는 LOST."""
        fsm = BallStateMachine()
        assert fsm.current_state == BallState.LOST

    def test_initialize_호출_후_상태_LOST(self, state_machine):
        """initialize 후 상태는 LOST."""
        assert state_machine.current_state == BallState.LOST
        assert state_machine.previous_state == BallState.LOST

    def test_holder_id_초기값_None(self, state_machine):
        """초기 holder_id는 None."""
        assert state_machine.holder_id is None

    def test_frames_in_state_초기값_0(self, state_machine):
        """초기 frames_in_state는 0."""
        assert state_machine.frames_in_state == 0

    def test_미초기화_상태에서_update_호출(self):
        """initialize() 없이 update 호출 시 LOST 반환."""
        fsm = BallStateMachine()
        det = BallDetection(
            position=Point2D(x=100, y=200),
            confidence=0.9,
        )
        result = fsm.update(det)
        assert result == BallState.LOST

    def test_repr_포맷(self, state_machine):
        """__repr__이 올바른 형식."""
        repr_str = repr(state_machine)
        assert "BallStateMachine" in repr_str
        assert "state=" in repr_str


# =============================================================================
# 상태 전이 매트릭스 검증
# =============================================================================

class TestValidTransitions:
    """유효 전이 매트릭스 정합성 검증."""

    def test_모든_상태에_전이_규칙_존재(self):
        """9개 모든 BallState에 대해 전이 규칙이 정의됨."""
        for state in BallState:
            assert state in _VALID_TRANSITIONS, (
                f"{state.value}에 전이 규칙이 없음"
            )

    def test_LOST에서_모든_상태로_전이_가능(self):
        """LOST 상태에서는 모든 상태로 복귀 가능."""
        lost_transitions = _VALID_TRANSITIONS[BallState.LOST]
        # LOST 자기 자신 제외 모든 상태로 전이 가능
        for state in BallState:
            if state == BallState.LOST:
                continue
            assert state in lost_transitions, (
                f"LOST → {state.value} 전이가 정의되어 있어야 함"
            )

    def test_자기_자신으로_전이_불가(self):
        """전이 매트릭스에 자기 자신이 포함되지 않음."""
        for state, targets in _VALID_TRANSITIONS.items():
            assert state not in targets, (
                f"{state.value} → {state.value} 자기 자신 전이 있음"
            )

    def test_HELD에서_SHOOTING_전이_가능(self):
        """HELD → SHOOTING 전이 가능."""
        assert BallState.SHOOTING in _VALID_TRANSITIONS[BallState.HELD]

    def test_SHOOTING에서_REBOUNDING_전이_가능(self):
        """SHOOTING → REBOUNDING 전이 가능."""
        assert BallState.REBOUNDING in _VALID_TRANSITIONS[BallState.SHOOTING]


# =============================================================================
# None 감지 → LOST 전이
# =============================================================================

class TestLostTransition:
    """미감지 시 LOST 전이."""

    def test_None_감지_시_LOST(self, state_machine):
        """detection=None이면 LOST."""
        result = state_machine.update(None)
        assert result == BallState.LOST

    def test_position_None_감지_시_LOST(self, state_machine):
        """position=None인 BallDetection도 LOST."""
        det = BallDetection(confidence=0.9)
        result = state_machine.update(det)
        assert result == BallState.LOST

    def test_연속_None_감지(self, state_machine):
        """연속 None 감지 시 LOST 유지."""
        for _ in range(10):
            result = state_machine.update(None)
        assert result == BallState.LOST
        assert state_machine.frames_in_state == 10


# =============================================================================
# 소유/보유 판정 (HELD)
# =============================================================================

class TestHeldTransition:
    """소유/보유 상태 전이."""

    def test_선수_근접_저속_지속시_HELD(
        self, state_machine, make_ball_detection, make_player_position,
    ):
        """선수 근접 + 저속 → min_possession_frames 이상 지속 시 HELD."""
        player = make_player_position(player_id=5, x=322.0, y=242.0)

        for i in range(BALL_STATE_MIN_POSSESSION_FRAMES + 2):
            det = make_ball_detection(
                x=320.0, y=240.0, frame_index=i,
            )
            result = state_machine.update(det, players=[player])

        assert result == BallState.HELD
        assert state_machine.holder_id == 5

    def test_선수_멀리_있으면_HELD_불가(
        self, state_machine, make_ball_detection, make_player_position,
    ):
        """선수가 멀리 있으면 HELD 전이 안 함."""
        # 선수가 먼 위치
        player = make_player_position(
            player_id=1, x=900.0, y=500.0,
        )

        for i in range(BALL_STATE_MIN_POSSESSION_FRAMES + 5):
            det = make_ball_detection(x=100.0, y=100.0, frame_index=i)
            state_machine.update(det, players=[player])

        assert state_machine.current_state != BallState.HELD


# =============================================================================
# 슈팅 판정
# =============================================================================

class TestShootingTransition:
    """슈팅 상태 전이."""

    def test_고속_상승시_SHOOTING(self, state_machine, make_ball_detection):
        """고속 상승 (vy < 0) → SHOOTING 전이."""
        # 먼저 HELD 상태로 만들기
        state_machine._current_state = BallState.HELD
        state_machine._config = BallStateMachineConfig()

        # 위치를 빠르게 위로 이동 (y 감소 = 상승)
        speed = BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX + 5.0
        for i in range(5):
            det = make_ball_detection(
                x=320.0,
                y=240.0 - speed * i,
                frame_index=i,
            )
            result = state_machine.update(det)

        # 고속 상승이면 SHOOTING이 되어야 함
        assert result in (BallState.SHOOTING, BallState.PASSING)


# =============================================================================
# 아웃오브바운드
# =============================================================================

class TestOutOfBounds:
    """아웃오브바운드 판정."""

    def test_코트_밖_위치_시_OUT_OF_BOUNDS(self, state_machine, make_ball_detection):
        """코트 경계 밖이면 OUT_OF_BOUNDS 전이."""
        # 먼저 DRIBBLING으로 전이 (OUT_OF_BOUNDS 전이가 가능한 상태)
        state_machine._current_state = BallState.DRIBBLING
        state_machine._config = BallStateMachineConfig()

        court_bounds = (100.0, 50.0, 1800.0, 1000.0)
        # 코트 밖 위치
        det = make_ball_detection(x=50.0, y=300.0, frame_index=10)
        result = state_machine.update(det, court_bounds=court_bounds)
        assert result == BallState.OUT_OF_BOUNDS

    def test_코트_안_위치_시_OUT_OF_BOUNDS_아님(self, state_machine, make_ball_detection):
        """코트 경계 안이면 OUT_OF_BOUNDS 아님."""
        state_machine._current_state = BallState.DRIBBLING
        state_machine._config = BallStateMachineConfig()

        court_bounds = (100.0, 50.0, 1800.0, 1000.0)
        det = make_ball_detection(x=500.0, y=300.0, frame_index=10)
        result = state_machine.update(det, court_bounds=court_bounds)
        assert result != BallState.OUT_OF_BOUNDS

    def test_is_out_of_bounds_정적_메서드(self):
        """_is_out_of_bounds 정적 메서드 검증."""
        bounds = (0.0, 0.0, 1920.0, 1080.0)
        # 밖
        assert BallStateMachine._is_out_of_bounds(
            Point2D(x=-10.0, y=100.0), bounds,
        )
        # 안
        assert not BallStateMachine._is_out_of_bounds(
            Point2D(x=960.0, y=540.0), bounds,
        )


# =============================================================================
# 리셋 테스트
# =============================================================================

class TestReset:
    """상태 머신 리셋."""

    def test_reset_후_LOST(self, state_machine, make_ball_detection, make_player_position):
        """reset() 후 모든 내부 상태 초기화."""
        # 먼저 HELD로 전이
        player = make_player_position(player_id=3, x=322.0, y=242.0)
        for i in range(BALL_STATE_MIN_POSSESSION_FRAMES + 2):
            det = make_ball_detection(x=320.0, y=240.0, frame_index=i)
            state_machine.update(det, players=[player])

        # 리셋
        state_machine.reset()

        assert state_machine.current_state == BallState.LOST
        assert state_machine.previous_state == BallState.LOST
        assert state_machine.holder_id is None
        assert state_machine.frames_in_state == 0


# =============================================================================
# 유효하지 않은 전이 무시 검증
# =============================================================================

class TestInvalidTransitionIgnored:
    """유효하지 않은 전이 시 현재 상태 유지."""

    def test_STATIONARY에서_REBOUNDING_직접_전이_불가(self, state_machine):
        """STATIONARY → REBOUNDING은 유효하지 않은 전이."""
        state_machine._current_state = BallState.STATIONARY
        # _transition 직접 호출
        result = state_machine._transition(BallState.REBOUNDING)
        # 유효하지 않은 전이이므로 현재 상태 유지
        assert result == BallState.STATIONARY

    def test_INBOUND에서_SHOOTING_직접_전이_불가(self, state_machine):
        """INBOUND → SHOOTING은 유효하지 않은 전이."""
        state_machine._current_state = BallState.INBOUND
        result = state_machine._transition(BallState.SHOOTING)
        assert result == BallState.INBOUND


# =============================================================================
# 정지 상태 (STATIONARY)
# =============================================================================

class TestStationaryTransition:
    """정지 상태 전이."""

    def test_극저속_시_STATIONARY(self, state_machine, make_ball_detection):
        """속도가 극도로 낮으면 STATIONARY."""
        state_machine._current_state = BallState.LOST
        state_machine._config = BallStateMachineConfig()

        # 같은 위치에서 반복 감지 (속도=0)
        for i in range(10):
            det = make_ball_detection(x=500.0, y=300.0, frame_index=i)
            result = state_machine.update(det)

        assert result == BallState.STATIONARY
