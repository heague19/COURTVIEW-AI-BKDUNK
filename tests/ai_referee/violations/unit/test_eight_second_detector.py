# -*- coding: utf-8 -*-
"""EightSecondDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.eight_second_detector import EightSecondDetector


@pytest.fixture()
def detector() -> EightSecondDetector:
    return EightSecondDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    ball_x: float = 3.0,
    half_x: float = 14.0,
    possession_team: str = "team_a",
    player_id: int = 10,
    attack_dir: str = "right",
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        possession_team_id=possession_team,
        ball_possession_player_id=player_id,
        ball_position=(ball_x, 5.0, 1.0),
        half_court_x=half_x,
        extra={"attack_direction": attack_dir},
    )


class TestInit:
    def test_rule_id(self, detector: EightSecondDetector) -> None:
        assert detector.rule_id == "FIBA-28"

    def test_call_type(self, detector: EightSecondDetector) -> None:
        assert detector.call_type == CallType.SHOT_CLOCK_VIOLATION

    def test_violation_type(self, detector: EightSecondDetector) -> None:
        assert detector.violation_type == ViolationType.EIGHT_SECONDS


class TestAppliesTo:
    def test_live_ball_with_possession(self, detector: EightSecondDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: EightSecondDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestEightSecondClock:
    def test_backcourt_under_eight(self, detector: EightSecondDetector) -> None:
        """백코트 8초 미만 — 위반 없음."""
        for i in range(200):  # ~6.67초
            ctx = _make_context(frame=i, ball_x=3.0)
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_backcourt_eight_exceeded(self, detector: EightSecondDetector) -> None:
        """백코트 8초 초과 — 위반."""
        violation_found = False
        for i in range(250):  # ~8.33초
            ctx = _make_context(frame=i, ball_x=3.0)
            result = detector.evaluate(ctx)
            if result.confidence > 0:
                violation_found = True
                break
        assert violation_found

    def test_crossing_halfcourt_resets(self, detector: EightSecondDetector) -> None:
        """하프코트 통과 시 카운트 종료."""
        for i in range(100):
            ctx = _make_context(frame=i, ball_x=3.0)
            detector.evaluate(ctx)

        # 프론트코트 도달
        ctx_front = _make_context(frame=101, ball_x=15.0)
        result = detector.evaluate(ctx_front)
        assert result.violated is False

    def test_possession_change_resets(self, detector: EightSecondDetector) -> None:
        """점유 변경 시 상태 리셋."""
        for i in range(100):
            ctx = _make_context(frame=i, ball_x=3.0, possession_team="team_a")
            detector.evaluate(ctx)

        ctx_change = _make_context(frame=101, ball_x=3.0, possession_team="team_b")
        result = detector.evaluate(ctx_change)
        assert result.violated is False


class TestNoBallPosition:
    def test_no_ball(self, detector: EightSecondDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            possession_team_id="team_a",
            ball_position=None,
            half_court_x=14.0,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: EightSecondDetector) -> None:
        for i in range(100):
            ctx = _make_context(frame=i)
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_context(frame=200)
        result = detector.evaluate(ctx)
        assert result.violated is False
