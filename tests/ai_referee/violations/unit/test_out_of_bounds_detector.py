# -*- coding: utf-8 -*-
"""OutOfBoundsDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.out_of_bounds_detector import OutOfBoundsDetector


@pytest.fixture()
def detector() -> OutOfBoundsDetector:
    return OutOfBoundsDetector(rule_set=RuleSet.FIBA)


_COURT = {"x_min": 0.0, "x_max": 28.0, "y_min": 0.0, "y_max": 15.0}


def _make_context(
    *,
    frame: int = 1,
    ball_x: float = 14.0,
    ball_y: float = 7.5,
    player_id: int = 10,
    player_pos: tuple[float, float] = (14.0, 7.5),
    is_live: bool = True,
    last_touch_id: int | None = None,
    camera_votes: list[bool] | None = None,
) -> FrameContext:
    extra: dict = {}
    if last_touch_id is not None:
        extra["last_touch_player_id"] = last_touch_id
    if camera_votes is not None:
        extra["oob_camera_votes"] = camera_votes

    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        ball_possession_player_id=player_id,
        ball_position=(ball_x, ball_y, 1.0),
        player_positions={player_id: player_pos},
        court_boundaries=_COURT,
        extra=extra,
    )


class TestInit:
    def test_rule_id(self, detector: OutOfBoundsDetector) -> None:
        assert detector.rule_id == "FIBA-23"

    def test_call_type(self, detector: OutOfBoundsDetector) -> None:
        assert detector.call_type == CallType.OUT_OF_BOUNDS

    def test_violation_type(self, detector: OutOfBoundsDetector) -> None:
        assert detector.violation_type == ViolationType.OUT_OF_BOUNDS


class TestAppliesTo:
    def test_live_ball(self, detector: OutOfBoundsDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: OutOfBoundsDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestBallOutOfBounds:
    def test_ball_on_line_x_min(self, detector: OutOfBoundsDetector) -> None:
        """공이 x_min 라인 위 — 아웃."""
        ctx = _make_context(ball_x=0.01)
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_ball_on_line_x_max(self, detector: OutOfBoundsDetector) -> None:
        """공이 x_max 라인 위 — 아웃."""
        ctx = _make_context(ball_x=27.99)
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_ball_on_line_y_min(self, detector: OutOfBoundsDetector) -> None:
        """공이 y_min 라인 위 — 아웃."""
        ctx = _make_context(ball_y=0.01)
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_ball_inside_court(self, detector: OutOfBoundsDetector) -> None:
        """공이 코트 내부 — 아웃 아님."""
        ctx = _make_context(ball_x=14.0, ball_y=7.5)
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestPlayerOnLine:
    def test_player_on_line_with_ball(self, detector: OutOfBoundsDetector) -> None:
        """선수가 라인 밟으면서 공 소유 — 아웃."""
        ctx = _make_context(
            player_pos=(0.01, 7.5),
            ball_x=14.0,
            ball_y=7.5,
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0


class TestLastTouch:
    def test_last_touch_boosts_confidence(self, detector: OutOfBoundsDetector) -> None:
        """마지막 터치 확인 시 신뢰도 부스트."""
        ctx = _make_context(ball_x=0.01, last_touch_id=10)
        result = detector.evaluate(ctx)
        assert result.confidence > 0.82  # 기본 + last_touch 부스트


class TestMultiView:
    def test_camera_agreement_boost(self, detector: OutOfBoundsDetector) -> None:
        """멀티뷰 합의 시 신뢰도 부스트."""
        ctx = _make_context(
            ball_x=0.01,
            camera_votes=[True, True, True],  # 3대 모두 아웃 판정
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0.82


class TestNoBall:
    def test_no_ball_position(self, detector: OutOfBoundsDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            ball_position=None,
            court_boundaries=_COURT,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_no_court_boundaries(self, detector: OutOfBoundsDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            ball_position=(14.0, 7.5, 1.0),
            court_boundaries={},
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: OutOfBoundsDetector) -> None:
        ctx = _make_context(ball_x=0.01)
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2, ball_x=14.0)
        result = detector.evaluate(ctx2)
        assert result.violated is False
