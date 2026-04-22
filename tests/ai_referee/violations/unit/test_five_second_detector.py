# -*- coding: utf-8 -*-
"""FiveSecondDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.five_second_detector import FiveSecondDetector


@pytest.fixture()
def detector() -> FiveSecondDetector:
    return FiveSecondDetector(rule_set=RuleSet.FIBA)


@pytest.fixture()
def nba_detector() -> FiveSecondDetector:
    return FiveSecondDetector(rule_set=RuleSet.NBA)


def _make_throw_in_context(
    *,
    frame: int = 1,
    player_id: int = 10,
    ball_disposed: bool = False,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=False,
        is_dead_ball=True,
        ball_possession_player_id=player_id,
        extra={
            "five_second_scenario": "throw_in",
            "ball_disposed": ball_disposed,
        },
    )


def _make_closely_guarded_context(
    *,
    frame: int = 1,
    player_id: int = 10,
    action: str = "hold",
    defender_pos: tuple[float, float] = (1.5, 2.0),
    possession_team: str = "team_a",
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=True,
        is_dead_ball=False,
        ball_possession_player_id=player_id,
        possession_team_id=possession_team,
        player_positions={
            player_id: (1.0, 2.0),
            20: defender_pos,
        },
        player_actions={player_id: action},
        extra={
            f"player_{player_id}_team_id": possession_team,
            "player_20_team_id": "team_b",
        },
    )


class TestInit:
    def test_rule_id(self, detector: FiveSecondDetector) -> None:
        assert detector.rule_id == "FIBA-17.3"

    def test_call_type(self, detector: FiveSecondDetector) -> None:
        assert detector.call_type == CallType.SHOT_CLOCK_VIOLATION

    def test_violation_type(self, detector: FiveSecondDetector) -> None:
        assert detector.violation_type == ViolationType.FIVE_SECONDS


class TestThrowInFiveSecond:
    def test_throw_in_under_five(self, detector: FiveSecondDetector) -> None:
        """스로인 5초 미만 — 위반 없음."""
        for i in range(100):  # ~3.3초
            ctx = _make_throw_in_context(frame=i)
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_throw_in_five_exceeded(self, detector: FiveSecondDetector) -> None:
        """스로인 5초 초과 — 위반."""
        violation_found = False
        for i in range(160):  # ~5.3초
            ctx = _make_throw_in_context(frame=i)
            result = detector.evaluate(ctx)
            if result.confidence > 0:
                violation_found = True
                break
        assert violation_found

    def test_throw_in_ball_disposed(self, detector: FiveSecondDetector) -> None:
        """공 방출 시 카운트 종료."""
        for i in range(100):
            ctx = _make_throw_in_context(frame=i)
            detector.evaluate(ctx)

        ctx_dispose = _make_throw_in_context(frame=101, ball_disposed=True)
        result = detector.evaluate(ctx_dispose)
        assert result.violated is False


class TestCloselyGuarded:
    def test_closely_guarded_under_five(self, detector: FiveSecondDetector) -> None:
        """밀접 수비 5초 미만 — 위반 없음."""
        for i in range(100):
            ctx = _make_closely_guarded_context(frame=i, defender_pos=(1.5, 2.0))
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_closely_guarded_five_exceeded(self, detector: FiveSecondDetector) -> None:
        """밀접 수비 5초 초과 — 위반."""
        violation_found = False
        for i in range(160):
            ctx = _make_closely_guarded_context(frame=i, defender_pos=(1.5, 2.0))
            result = detector.evaluate(ctx)
            if result.confidence > 0:
                violation_found = True
                break
        assert violation_found

    def test_no_closely_guarded_nba(self, nba_detector: FiveSecondDetector) -> None:
        """NBA는 밀접 수비 5초 없음."""
        for i in range(160):
            ctx = _make_closely_guarded_context(frame=i, defender_pos=(1.5, 2.0))
            result = nba_detector.evaluate(ctx)
        assert result.violated is False

    def test_defender_far_no_count(self, detector: FiveSecondDetector) -> None:
        """수비 거리 멀면 — 카운트 안됨."""
        for i in range(160):
            ctx = _make_closely_guarded_context(
                frame=i, defender_pos=(5.0, 5.0),
            )
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_not_stationary_no_count(self, detector: FiveSecondDetector) -> None:
        """볼 핸들러 이동 중 — 카운트 안됨."""
        for i in range(160):
            ctx = _make_closely_guarded_context(frame=i, action="dribble")
            result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: FiveSecondDetector) -> None:
        for i in range(50):
            ctx = _make_throw_in_context(frame=i)
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_throw_in_context(frame=100)
        result = detector.evaluate(ctx)
        assert result.violated is False
