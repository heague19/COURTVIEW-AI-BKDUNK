# -*- coding: utf-8 -*-
"""ContactDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.contact_detector import ContactDetector


@pytest.fixture()
def detector() -> ContactDetector:
    return ContactDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    velocities: dict | None = None,
    accelerations: dict | None = None,
    ball_holder: int | None = 10,
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (1.0, 2.0), 20: (1.2, 2.1)},
        player_keypoints=keypoints or {},
        joint_velocities=velocities or {},
        joint_accelerations=accelerations or {},
        ball_possession_player_id=ball_holder,
        possession_team_id="team_a",
    )


class TestInit:
    def test_rule_id(self, detector: ContactDetector) -> None:
        assert detector.rule_id == "FIBA-33"

    def test_call_type(self, detector: ContactDetector) -> None:
        assert detector.call_type == CallType.PERSONAL_FOUL

    def test_foul_type(self, detector: ContactDetector) -> None:
        assert detector.foul_type == FoulType.PERSONAL


class TestAppliesTo:
    def test_live_ball_two_players(self, detector: ContactDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: ContactDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False

    def test_single_player(self, detector: ContactDetector) -> None:
        ctx = _make_context(positions={10: (1.0, 2.0)})
        assert detector.applies_to(ctx) is False


class TestContact:
    def test_no_contact_far_apart(self, detector: ContactDetector) -> None:
        """2m 이상 떨어져 있으면 접촉 없음."""
        ctx = _make_context(positions={10: (0.0, 0.0), 20: (5.0, 5.0)})
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_close_with_impact(self, detector: ContactDetector) -> None:
        """근접 + 가속도 충격 → 접촉 감지."""
        ctx = _make_context(
            positions={10: (1.0, 2.0), 20: (1.1, 2.0)},
            accelerations={10: {"torso": 20.0}, 20: {"torso": 18.0}},
            velocities={10: {"torso": 2.0}, 20: {"torso": 1.8}},
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_close_with_keypoints(self, detector: ContactDetector) -> None:
        """키포인트 접촉 + 충격 → 접촉 감지."""
        ctx = _make_context(
            positions={10: (1.0, 2.0), 20: (1.15, 2.0)},
            keypoints={
                10: {"left_shoulder": (1.0, 2.0, 1.5)},
                20: {"right_wrist": (1.05, 2.0, 1.5)},
            },
            accelerations={10: {"torso": 16.0}, 20: {"torso": 15.0}},
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_detect_contacts_api(self, detector: ContactDetector) -> None:
        """detect_contacts API 테스트."""
        ctx = _make_context(
            positions={10: (1.0, 2.0), 20: (1.1, 2.0)},
            accelerations={10: {"torso": 20.0}, 20: {"torso": 18.0}},
            velocities={10: {"torso": 2.0}, 20: {"torso": 1.8}},
        )
        contacts = detector.detect_contacts(ctx)
        assert isinstance(contacts, list)


class TestReset:
    def test_reset(self, detector: ContactDetector) -> None:
        ctx = _make_context(
            positions={10: (1.0, 2.0), 20: (1.1, 2.0)},
            accelerations={10: {"torso": 20.0}, 20: {"torso": 18.0}},
            velocities={10: {"torso": 2.0}, 20: {"torso": 1.8}},
        )
        detector.evaluate(ctx)
        detector.reset()
        assert detector.last_contacts == []
