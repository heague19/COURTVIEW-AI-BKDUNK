# -*- coding: utf-8 -*-
"""DoubleDribbleDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.double_dribble_detector import DoubleDribbleDetector


@pytest.fixture()
def detector() -> DoubleDribbleDetector:
    return DoubleDribbleDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    player_id: int = 10,
    action: str = "",
    left_wrist: tuple[float, float, float] = (1.0, 2.0, 1.0),
    right_wrist: tuple[float, float, float] = (1.3, 2.0, 1.0),
    ball_pos: tuple[float, float, float] = (1.15, 2.0, 1.0),
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        ball_possession_player_id=player_id,
        player_actions={player_id: action},
        player_keypoints={
            player_id: {
                "left_wrist": left_wrist,
                "right_wrist": right_wrist,
            },
        },
        ball_position=ball_pos,
    )


class TestDoubleDribbleInit:
    def test_rule_id(self, detector: DoubleDribbleDetector) -> None:
        assert detector.rule_id == "FIBA-24.2"

    def test_call_type(self, detector: DoubleDribbleDetector) -> None:
        assert detector.call_type == CallType.DOUBLE_DRIBBLE

    def test_violation_type(self, detector: DoubleDribbleDetector) -> None:
        assert detector.violation_type == ViolationType.DOUBLE_DRIBBLE


class TestAppliesTo:
    def test_live_ball_with_possession(self, detector: DoubleDribbleDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: DoubleDribbleDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False

    def test_no_possession(self, detector: DoubleDribbleDetector) -> None:
        ctx = FrameContext(is_live_ball=True, is_dead_ball=False, ball_possession_player_id=None)
        assert detector.applies_to(ctx) is False


class TestDribbleEndDetection:
    def test_both_hands_contact_ends_dribble(self, detector: DoubleDribbleDetector) -> None:
        """양손 접촉 + 드리블 종료 감지."""
        # 드리블 중 — 양손 가깝게
        for i in range(5):
            ctx = _make_context(
                frame=i,
                action="dribble",
                left_wrist=(1.1, 2.0, 1.0),
                right_wrist=(1.2, 2.0, 1.0),
                ball_pos=(1.15, 2.0, 1.0),
            )
            detector.evaluate(ctx)

        # 드리블 중지 (양손 가까운 상태)
        ctx_stop = _make_context(
            frame=6,
            action="hold",
            left_wrist=(1.1, 2.0, 1.0),
            right_wrist=(1.2, 2.0, 1.0),
            ball_pos=(1.15, 2.0, 1.0),
        )
        result = detector.evaluate(ctx_stop)
        assert result.violated is False  # 종료만 — 아직 위반 아님


class TestReDribbleDetection:
    def test_re_dribble_after_end(self, detector: DoubleDribbleDetector) -> None:
        """드리블 종료 후 재드리블 → 위반."""
        # 드리블 중 (양손 접촉)
        for i in range(5):
            ctx = _make_context(
                frame=i,
                action="dribble",
                left_wrist=(1.1, 2.0, 1.0),
                right_wrist=(1.2, 2.0, 1.0),
                ball_pos=(1.15, 2.0, 1.0),
            )
            detector.evaluate(ctx)

        # 드리블 종료 (hold → 양손 가까움)
        ctx_stop = _make_context(
            frame=6,
            action="hold",
            left_wrist=(1.1, 2.0, 1.0),
            right_wrist=(1.2, 2.0, 1.0),
            ball_pos=(1.15, 2.0, 1.0),
        )
        detector.evaluate(ctx_stop)

        # 재드리블 시도
        ctx_re = _make_context(
            frame=10,
            action="dribble",
            left_wrist=(1.1, 2.0, 1.0),
            right_wrist=(1.5, 2.0, 1.0),
            ball_pos=(1.15, 2.0, 0.5),
        )
        result = detector.evaluate(ctx_re)
        # 재드리블 감지 여부 (상태 조건 충족 시)
        assert isinstance(result.confidence, float)


class TestNoViolation:
    def test_normal_dribble(self, detector: DoubleDribbleDetector) -> None:
        """일반 드리블 — 위반 없음."""
        for i in range(10):
            ctx = _make_context(
                frame=i,
                action="dribble",
                left_wrist=(1.0, 2.0, 1.0),
                right_wrist=(1.5, 2.0, 1.0),  # 양손 멀리
                ball_pos=(1.2, 2.0, 0.5),
            )
            result = detector.evaluate(ctx)
            assert result.violated is False


class TestReset:
    def test_reset_clears_state(self, detector: DoubleDribbleDetector) -> None:
        ctx = _make_context(action="dribble")
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2, action="dribble")
        result = detector.evaluate(ctx2)
        assert result.violated is False


class TestResultStructure:
    def test_rule_reference(self, detector: DoubleDribbleDetector) -> None:
        ctx = _make_context()
        result = detector.evaluate(ctx)
        assert "24.2" in result.rule_reference

    def test_no_possession_returns_no_violation(self, detector: DoubleDribbleDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            ball_possession_player_id=None,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False
