# -*- coding: utf-8 -*-
"""HoldingFoulDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.holding_foul_detector import HoldingFoulDetector


@pytest.fixture()
def detector() -> HoldingFoulDetector:
    return HoldingFoulDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    velocities: dict | None = None,
    extra: dict | None = None,
    is_live: bool = True,
) -> FrameContext:
    e = extra or {}
    e.setdefault("player_10_team_id", "team_a")
    e.setdefault("player_20_team_id", "team_b")
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (5.0, 5.0), 20: (5.2, 5.0)},
        player_keypoints=keypoints or {},
        joint_velocities=velocities or {},
        possession_team_id="team_a",
        extra=e,
    )


def _wrap_keypoints() -> dict:
    """수비자 양손이 공격자 몸통을 감싸는 키포인트."""
    return {
        10: {
            "left_shoulder": (5.0, 4.8, 1.5),
            "right_shoulder": (5.0, 5.2, 1.5),
            "left_hip": (5.0, 4.8, 1.0),
            "right_hip": (5.0, 5.2, 1.0),
        },
        20: {
            "left_wrist": (5.0, 4.9, 1.3),   # 공격자 몸통 왼쪽
            "right_wrist": (5.0, 5.1, 1.3),   # 공격자 몸통 오른쪽
        },
    }


class TestInit:
    def test_rule_id(self, detector: HoldingFoulDetector) -> None:
        assert detector.rule_id == "FIBA-33.10"

    def test_call_type(self, detector: HoldingFoulDetector) -> None:
        assert detector.call_type == CallType.PERSONAL_FOUL

    def test_foul_type(self, detector: HoldingFoulDetector) -> None:
        assert detector.foul_type == FoulType.HOLDING


class TestAppliesTo:
    def test_live_ball(self, detector: HoldingFoulDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: HoldingFoulDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestHolding:
    def test_no_wrap_no_foul(self, detector: HoldingFoulDetector) -> None:
        ctx = _make_context()
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_brief_wrap_no_foul(self, detector: HoldingFoulDetector) -> None:
        """2프레임 감싸기 → 파울 아님 (3프레임 필요)."""
        for i in range(2):
            ctx = _make_context(frame=i, keypoints=_wrap_keypoints())
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_persistent_wrap_foul(self, detector: HoldingFoulDetector) -> None:
        """3프레임 이상 감싸기 → 홀딩 파울."""
        violation_found = False
        for i in range(8):
            ctx = _make_context(
                frame=i,
                keypoints=_wrap_keypoints(),
                velocities={10: {"torso": 2.0}},
            )
            result = detector.evaluate(ctx)
            if result.confidence > 0:
                violation_found = True
                break
        assert violation_found

    def test_restraint_boost(self, detector: HoldingFoulDetector) -> None:
        """이동 제한 시 신뢰도 상승."""
        ctx = _make_context(
            frame=0,
            keypoints=_wrap_keypoints(),
            velocities={10: {"torso": 3.0}},
        )
        detector.evaluate(ctx)

        for i in range(1, 6):
            ctx = _make_context(
                frame=i,
                keypoints=_wrap_keypoints(),
                velocities={10: {"torso": max(3.0 - i * 0.8, 0.3)}},
            )
            result = detector.evaluate(ctx)
        assert result.confidence > 0


class TestReset:
    def test_reset(self, detector: HoldingFoulDetector) -> None:
        for i in range(5):
            ctx = _make_context(frame=i, keypoints=_wrap_keypoints())
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_context(frame=10)
        result = detector.evaluate(ctx)
        assert result.violated is False
