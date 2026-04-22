# -*- coding: utf-8 -*-
"""KickBallDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.kick_ball_detector import KickBallDetector


@pytest.fixture()
def detector() -> KickBallDetector:
    return KickBallDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    player_id: int = 10,
    left_ankle: tuple[float, float, float] = (1.0, 2.0, 0.1),
    right_ankle: tuple[float, float, float] = (1.3, 2.0, 0.1),
    ball_pos: tuple[float, float, float] = (5.0, 5.0, 0.5),
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_keypoints={
            player_id: {
                "left_ankle": left_ankle,
                "right_ankle": right_ankle,
            },
        },
        ball_position=ball_pos,
    )


class TestKickBallInit:
    def test_rule_id(self, detector: KickBallDetector) -> None:
        assert detector.rule_id == "FIBA-24.3"

    def test_call_type(self, detector: KickBallDetector) -> None:
        assert detector.call_type == CallType.OUT_OF_BOUNDS

    def test_violation_type(self, detector: KickBallDetector) -> None:
        assert detector.violation_type == ViolationType.KICKED_BALL


class TestAppliesTo:
    def test_live_ball(self, detector: KickBallDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: KickBallDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestIntentionalKick:
    def test_fast_foot_near_ball(self, detector: KickBallDetector) -> None:
        """빠른 발 + 공 근접 → 의도적 킥."""
        # 프레임 1: 발 위치 기록
        ctx1 = _make_context(
            frame=1,
            left_ankle=(1.0, 2.0, 0.1),
            ball_pos=(1.05, 2.0, 0.1),
        )
        detector.evaluate(ctx1)

        # 프레임 2: 발이 빠르게 이동 + 공 근접
        ctx2 = _make_context(
            frame=2,
            left_ankle=(1.1, 2.0, 0.2),  # 이동
            ball_pos=(1.12, 2.0, 0.15),  # 공 근접
        )
        result = detector.evaluate(ctx2)
        # 속도 계산: sqrt(0.1^2 + 0 + 0.1^2) * 30 ≈ 4.24 m/s > 1.5
        assert result.confidence > 0

    def test_slow_foot_near_ball(self, detector: KickBallDetector) -> None:
        """느린 발 + 공 근접 → 비의도적."""
        ctx1 = _make_context(
            frame=1,
            left_ankle=(1.0, 2.0, 0.1),
            ball_pos=(1.05, 2.0, 0.1),
        )
        detector.evaluate(ctx1)

        ctx2 = _make_context(
            frame=2,
            left_ankle=(1.001, 2.0, 0.1),  # 거의 정지
            ball_pos=(1.005, 2.0, 0.1),
        )
        result = detector.evaluate(ctx2)
        assert result.violated is False

    def test_fast_foot_far_from_ball(self, detector: KickBallDetector) -> None:
        """빠른 발이지만 공과 거리 멀면 — 무시."""
        ctx1 = _make_context(
            frame=1,
            left_ankle=(1.0, 2.0, 0.1),
            ball_pos=(5.0, 5.0, 0.5),
        )
        detector.evaluate(ctx1)

        ctx2 = _make_context(
            frame=2,
            left_ankle=(1.2, 2.0, 0.3),
            ball_pos=(5.0, 5.0, 0.5),
        )
        result = detector.evaluate(ctx2)
        assert result.violated is False


class TestNoBallPosition:
    def test_no_ball_returns_no_violation(self, detector: KickBallDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            ball_position=None,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: KickBallDetector) -> None:
        ctx = _make_context(ball_pos=(1.05, 2.0, 0.1))
        detector.evaluate(ctx)
        detector.reset()
        # 리셋 후 이전 발 위치 없어야 함
        ctx2 = _make_context(frame=2, ball_pos=(1.05, 2.0, 0.1))
        result = detector.evaluate(ctx2)
        assert result.violated is False
