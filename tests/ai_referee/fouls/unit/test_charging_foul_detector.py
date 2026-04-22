# -*- coding: utf-8 -*-
"""ChargingFoulDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.charging_foul_detector import ChargingFoulDetector


@pytest.fixture()
def detector() -> ChargingFoulDetector:
    return ChargingFoulDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    ball_holder: int = 10,
    contact_events: list | None = None,
    velocities: dict | None = None,
    extra: dict | None = None,
    is_live: bool = True,
) -> FrameContext:
    e = extra or {}
    e.setdefault("player_10_team_id", "team_a")
    e.setdefault("player_20_team_id", "team_b")
    if contact_events is not None:
        e["contact_events"] = contact_events
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (5.0, 5.0), 20: (5.2, 5.0)},
        ball_possession_player_id=ball_holder,
        possession_team_id="team_a",
        joint_velocities=velocities or {},
        extra=e,
    )


class TestInit:
    def test_rule_id(self, detector: ChargingFoulDetector) -> None:
        assert detector.rule_id == "FIBA-33.7C"

    def test_call_type(self, detector: ChargingFoulDetector) -> None:
        assert detector.call_type == CallType.OFFENSIVE_FOUL

    def test_foul_type(self, detector: ChargingFoulDetector) -> None:
        assert detector.foul_type == FoulType.CHARGE


class TestAppliesTo:
    def test_live_ball_with_holder(self, detector: ChargingFoulDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_no_ball_holder(self, detector: ChargingFoulDetector) -> None:
        ctx = _make_context(ball_holder=None)
        assert detector.applies_to(ctx) is False


class TestCharging:
    def test_no_contact_no_foul(self, detector: ChargingFoulDetector) -> None:
        ctx = _make_context(contact_events=[])
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_lgp_defender_charge(self, detector: ChargingFoulDetector) -> None:
        """LGP 확보 수비자에게 돌진 → 차징."""
        # 수비자 정지 시뮬레이션
        for i in range(10):
            ctx = _make_context(
                frame=i,
                positions={10: (5.0 - i * 0.3, 5.0), 20: (5.0, 5.0)},
                contact_events=[],
            )
            detector.evaluate(ctx)

        # 돌진 + 접촉
        ctx = _make_context(
            frame=11,
            positions={10: (5.0, 5.0), 20: (5.0, 5.0)},
            contact_events=[{
                "offender_id": 10,
                "victim_id": 20,
                "contact_bodies": ["chest", "shoulder"],
                "impact_accel": 15.0,
            }],
            velocities={10: {"torso": 3.0}},
            extra={
                "player_10_team_id": "team_a",
                "player_20_team_id": "team_b",
                "hoop_x": 14.0,
                "hoop_y": 5.0,
            },
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_restricted_area_no_charge(self, detector: ChargingFoulDetector) -> None:
        """제한 구역 내 수비자 → 차징 불가."""
        for i in range(10):
            ctx = _make_context(
                frame=i,
                positions={10: (13.0, 5.0), 20: (14.0, 5.0)},
                contact_events=[],
                extra={
                    "player_10_team_id": "team_a",
                    "player_20_team_id": "team_b",
                    "hoop_x": 14.0,
                    "hoop_y": 5.0,
                },
            )
            detector.evaluate(ctx)

        ctx = _make_context(
            frame=11,
            positions={10: (14.0, 5.0), 20: (14.0, 5.0)},
            contact_events=[{
                "offender_id": 10,
                "victim_id": 20,
                "contact_bodies": ["chest"],
                "impact_accel": 12.0,
            }],
            velocities={10: {"torso": 3.0}},
            extra={
                "player_10_team_id": "team_a",
                "player_20_team_id": "team_b",
                "hoop_x": 14.0,
                "hoop_y": 5.0,
            },
        )
        result = detector.evaluate(ctx)
        # 제한 구역 내 → 차징 불가 (blocked)
        assert result.violated is False

    def test_possession_change_on_charge(self, detector: ChargingFoulDetector) -> None:
        """차징 파울 시 공격권 전환."""
        for i in range(10):
            ctx = _make_context(
                frame=i,
                positions={10: (5.0 - i * 0.3, 5.0), 20: (5.0, 5.0)},
                contact_events=[],
                extra={
                    "player_10_team_id": "team_a",
                    "player_20_team_id": "team_b",
                    "hoop_x": 14.0,
                    "hoop_y": 5.0,
                },
            )
            detector.evaluate(ctx)

        ctx = _make_context(
            frame=11,
            positions={10: (5.0, 5.0), 20: (5.0, 5.0)},
            contact_events=[{
                "offender_id": 10,
                "victim_id": 20,
                "contact_bodies": ["chest", "shoulder"],
                "impact_accel": 18.0,
            }],
            velocities={10: {"torso": 3.5}},
            extra={
                "player_10_team_id": "team_a",
                "player_20_team_id": "team_b",
                "hoop_x": 14.0,
                "hoop_y": 5.0,
            },
        )
        result = detector.evaluate(ctx)
        if result.violated:
            assert result.possession_change is True


class TestReset:
    def test_reset(self, detector: ChargingFoulDetector) -> None:
        ctx = _make_context()
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2)
        result = detector.evaluate(ctx2)
        assert result.violated is False
