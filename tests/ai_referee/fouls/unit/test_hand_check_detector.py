# -*- coding: utf-8 -*-
"""HandCheckDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.hand_check_detector import HandCheckDetector


@pytest.fixture()
def detector() -> HandCheckDetector:
    return HandCheckDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    velocities: dict | None = None,
    ball_holder: int = 10,
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
        ball_possession_player_id=ball_holder,
        possession_team_id="team_a",
        extra=e,
    )


def _hand_on_body_keypoints() -> dict:
    """수비자 손이 공격자 몸통에 있는 키포인트."""
    return {
        10: {
            "left_shoulder": (5.0, 5.0, 1.5),
            "right_shoulder": (5.0, 5.4, 1.5),
            "left_hip": (5.0, 5.0, 1.0),
            "right_hip": (5.0, 5.4, 1.0),
        },
        20: {
            "left_wrist": (5.0, 5.1, 1.3),  # 공격자 몸통 근처
            "right_wrist": (5.3, 5.2, 1.3),
            "left_elbow": (5.1, 5.1, 1.4),
            "right_elbow": (5.3, 5.2, 1.4),
        },
    }


class TestInit:
    def test_rule_id(self, detector: HandCheckDetector) -> None:
        assert detector.rule_id == "FIBA-33.9"

    def test_call_type(self, detector: HandCheckDetector) -> None:
        assert detector.call_type == CallType.PERSONAL_FOUL

    def test_foul_type(self, detector: HandCheckDetector) -> None:
        assert detector.foul_type == FoulType.PERSONAL


class TestAppliesTo:
    def test_live_ball_with_holder(self, detector: HandCheckDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_no_ball_holder(self, detector: HandCheckDetector) -> None:
        ctx = _make_context(ball_holder=None)
        assert detector.applies_to(ctx) is False


class TestHandCheck:
    def test_no_keypoints_no_foul(self, detector: HandCheckDetector) -> None:
        ctx = _make_context()
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_brief_contact_no_foul(self, detector: HandCheckDetector) -> None:
        """3프레임 미만 접촉 → 파울 아님."""
        for i in range(3):
            ctx = _make_context(
                frame=i, keypoints=_hand_on_body_keypoints(),
            )
            detector.evaluate(ctx)
        result = detector.evaluate(
            _make_context(frame=3, keypoints=_hand_on_body_keypoints()),
        )
        assert result.violated is False

    def test_persistent_hand_on(self, detector: HandCheckDetector) -> None:
        """5프레임 이상 손 대기 → 파울."""
        violation_found = False
        for i in range(10):
            ctx = _make_context(
                frame=i,
                keypoints=_hand_on_body_keypoints(),
                velocities={10: {"torso": 2.0}},
            )
            result = detector.evaluate(ctx)
            if result.confidence > 0:
                violation_found = True
                break
        assert violation_found

    def test_speed_reduction_boost(self, detector: HandCheckDetector) -> None:
        """속도 감소 시 신뢰도 상승."""
        # 초기 속도 높게
        ctx = _make_context(
            frame=0,
            keypoints=_hand_on_body_keypoints(),
            velocities={10: {"torso": 3.0}},
        )
        detector.evaluate(ctx)

        # 지속 + 속도 감소
        for i in range(1, 8):
            ctx = _make_context(
                frame=i,
                keypoints=_hand_on_body_keypoints(),
                velocities={10: {"torso": max(3.0 - i * 0.5, 0.5)}},
            )
            result = detector.evaluate(ctx)

        # 마지막 결과에서 신뢰도 확인
        assert result.confidence > 0


class TestReset:
    def test_reset(self, detector: HandCheckDetector) -> None:
        for i in range(5):
            ctx = _make_context(
                frame=i, keypoints=_hand_on_body_keypoints(),
            )
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_context(frame=10)
        result = detector.evaluate(ctx)
        assert result.violated is False
