# -*- coding: utf-8 -*-
"""ThreeSecondDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.three_second_detector import ThreeSecondDetector


@pytest.fixture()
def detector() -> ThreeSecondDetector:
    return ThreeSecondDetector(rule_set=RuleSet.FIBA)


_PAINT = {"x_min": 4.0, "x_max": 6.0, "y_min": 0.0, "y_max": 3.0}


def _make_context(
    *,
    frame: int = 1,
    player_id: int = 10,
    pos: tuple[float, float] = (5.0, 1.5),
    action: str = "",
    is_live: bool = True,
    possession_team: str = "team_a",
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        possession_team_id=possession_team,
        player_positions={player_id: pos},
        player_actions={player_id: action} if action else {},
        paint_zone_bounds=_PAINT,
    )


class TestThreeSecondInit:
    def test_rule_id(self, detector: ThreeSecondDetector) -> None:
        assert detector.rule_id == "FIBA-26"

    def test_call_type(self, detector: ThreeSecondDetector) -> None:
        assert detector.call_type == CallType.SHOT_CLOCK_VIOLATION

    def test_violation_type(self, detector: ThreeSecondDetector) -> None:
        assert detector.violation_type == ViolationType.THREE_SECONDS


class TestAppliesTo:
    def test_live_ball_with_possession(self, detector: ThreeSecondDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: ThreeSecondDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False

    def test_no_possession(self, detector: ThreeSecondDetector) -> None:
        ctx = FrameContext(
            is_live_ball=True, is_dead_ball=False, possession_team_id=None,
            paint_zone_bounds=_PAINT,
        )
        assert detector.applies_to(ctx) is False


class TestPaintZoneDetection:
    def test_player_in_paint_accumulates(self, detector: ThreeSecondDetector) -> None:
        """페인트존 내 체류 시간 누적."""
        for i in range(30):  # 30프레임 = 1초
            ctx = _make_context(frame=i, pos=(5.0, 1.5))
            detector.evaluate(ctx)
        # 1초 누적 — 아직 3초 미만
        ctx_check = _make_context(frame=30, pos=(5.0, 1.5))
        result = detector.evaluate(ctx_check)
        assert result.violated is False

    def test_three_seconds_exceeded(self, detector: ThreeSecondDetector) -> None:
        """3초 초과 — 위반."""
        for i in range(100):  # 100프레임 = ~3.33초
            ctx = _make_context(frame=i, pos=(5.0, 1.5))
            result = detector.evaluate(ctx)

        assert result.confidence > 0

    def test_player_outside_paint(self, detector: ThreeSecondDetector) -> None:
        """페인트존 밖 — 카운트 안됨."""
        for i in range(100):
            ctx = _make_context(frame=i, pos=(1.0, 1.0))  # 페인트 밖
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_shot_resets_count(self, detector: ThreeSecondDetector) -> None:
        """슛 시도 시 카운트 리셋."""
        for i in range(80):
            ctx = _make_context(frame=i, pos=(5.0, 1.5))
            detector.evaluate(ctx)

        # 슛 시도
        ctx_shot = _make_context(frame=81, pos=(5.0, 1.5), action="shot_attempt")
        detector.evaluate(ctx_shot)

        # 리셋 후 새 카운트
        ctx_after = _make_context(frame=82, pos=(5.0, 1.5))
        result = detector.evaluate(ctx_after)
        assert result.violated is False


class TestNoPaintZone:
    def test_no_paint_bounds(self, detector: ThreeSecondDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            possession_team_id="team_a",
            player_positions={10: (5.0, 1.5)},
            paint_zone_bounds={},
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: ThreeSecondDetector) -> None:
        for i in range(50):
            ctx = _make_context(frame=i, pos=(5.0, 1.5))
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_context(frame=100, pos=(5.0, 1.5))
        result = detector.evaluate(ctx)
        assert result.violated is False
