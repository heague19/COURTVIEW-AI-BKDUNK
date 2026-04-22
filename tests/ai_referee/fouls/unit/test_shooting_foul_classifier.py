# -*- coding: utf-8 -*-
"""ShootingFoulClassifier 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.shooting_foul_classifier import (
    ShootingFoulClassifier,
    ShootingFoulType,
)


@pytest.fixture()
def classifier() -> ShootingFoulClassifier:
    return ShootingFoulClassifier(rule_set=RuleSet.FIBA)


@pytest.fixture()
def nba_classifier() -> ShootingFoulClassifier:
    return ShootingFoulClassifier(rule_set=RuleSet.NBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    actions: dict | None = None,
    contact_events: list | None = None,
    shot_result: str = "",
    extra: dict | None = None,
    is_live: bool = True,
) -> FrameContext:
    e = extra or {}
    if contact_events is not None:
        e["contact_events"] = contact_events
    if shot_result:
        e["shot_result"] = shot_result
    e.setdefault("hoop_x", 14.0)
    e.setdefault("hoop_y", 5.0)
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (8.0, 5.0), 20: (8.2, 5.0)},
        player_keypoints=keypoints or {},
        player_actions=actions or {},
        possession_team_id="team_a",
        extra=e,
    )


class TestInit:
    def test_rule_id(self, classifier: ShootingFoulClassifier) -> None:
        assert classifier.rule_id == "FIBA-34.2"

    def test_call_type(self, classifier: ShootingFoulClassifier) -> None:
        assert classifier.call_type == CallType.SHOOTING_FOUL

    def test_foul_type(self, classifier: ShootingFoulClassifier) -> None:
        assert classifier.foul_type == FoulType.SHOOTING


class TestShootingFoulType:
    def test_two_point_ft(self) -> None:
        assert ShootingFoulType.TWO_POINT.free_throws == 2

    def test_three_point_ft(self) -> None:
        assert ShootingFoulType.THREE_POINT.free_throws == 3

    def test_and_one_ft(self) -> None:
        assert ShootingFoulType.AND_ONE.free_throws == 1


class TestClassification:
    def test_no_shooting_no_foul(self, classifier: ShootingFoulClassifier) -> None:
        """슈팅 아닌 상태 → 파울 아님."""
        ctx = _make_context(
            actions={10: "dribble"},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["arm"],
                "impact_accel": 10.0,
            }],
        )
        result = classifier.evaluate(ctx)
        assert result.violated is False

    def test_two_point_shooting_foul(self, classifier: ShootingFoulClassifier) -> None:
        """2점 슈팅 파울."""
        # 슈팅 시작 (3점 라인 안)
        ctx = _make_context(
            frame=1,
            positions={10: (8.0, 5.0), 20: (8.2, 5.0)},
            actions={10: "shooting"},
        )
        classifier.evaluate(ctx)

        # 접촉
        ctx = _make_context(
            frame=2,
            positions={10: (8.0, 5.0), 20: (8.2, 5.0)},
            actions={10: "shooting"},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["arm", "shoulder"],
                "impact_accel": 12.0,
            }],
        )
        result = classifier.evaluate(ctx)
        if result.violated:
            assert result.free_throws_awarded == 2

    def test_three_point_shooting_foul(self, classifier: ShootingFoulClassifier) -> None:
        """3점 슈팅 파울."""
        # 3점 라인 밖에서 슈팅 (FIBA 6.75m)
        ctx = _make_context(
            frame=1,
            positions={10: (3.0, 5.0), 20: (3.2, 5.0)},  # 거리 > 6.75m
            actions={10: "shooting"},
        )
        classifier.evaluate(ctx)

        ctx = _make_context(
            frame=2,
            positions={10: (3.0, 5.0), 20: (3.2, 5.0)},
            actions={10: "shooting"},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["arm"],
                "impact_accel": 10.0,
            }],
        )
        result = classifier.evaluate(ctx)
        if result.violated:
            assert result.free_throws_awarded == 3

    def test_and_one(self, classifier: ShootingFoulClassifier) -> None:
        """앤드원 (슛 성공 + 파울)."""
        ctx = _make_context(
            frame=1,
            actions={10: "shooting"},
        )
        classifier.evaluate(ctx)

        ctx = _make_context(
            frame=2,
            actions={10: "shooting"},
            shot_result="made",
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["arm"],
                "impact_accel": 8.0,
            }],
        )
        result = classifier.evaluate(ctx)
        if result.violated:
            assert result.free_throws_awarded == 1


class TestAppliesTo:
    def test_live_ball(self, classifier: ShootingFoulClassifier) -> None:
        ctx = _make_context()
        assert classifier.applies_to(ctx) is True

    def test_dead_ball(self, classifier: ShootingFoulClassifier) -> None:
        ctx = _make_context(is_live=False)
        assert classifier.applies_to(ctx) is False


class TestReset:
    def test_reset(self, classifier: ShootingFoulClassifier) -> None:
        ctx = _make_context(actions={10: "shooting"})
        classifier.evaluate(ctx)
        classifier.reset()
        ctx2 = _make_context(frame=2)
        result = classifier.evaluate(ctx2)
        assert result.violated is False
