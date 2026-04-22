# -*- coding: utf-8 -*-
"""BlockingFoulDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.blocking_foul_detector import BlockingFoulDetector


@pytest.fixture()
def detector() -> BlockingFoulDetector:
    return BlockingFoulDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    ball_holder: int = 10,
    contact_events: list | None = None,
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
        extra=e,
    )


class TestInit:
    def test_rule_id(self, detector: BlockingFoulDetector) -> None:
        assert detector.rule_id == "FIBA-33.7B"

    def test_call_type(self, detector: BlockingFoulDetector) -> None:
        assert detector.call_type == CallType.PERSONAL_FOUL

    def test_foul_type(self, detector: BlockingFoulDetector) -> None:
        assert detector.foul_type == FoulType.BLOCKING


class TestAppliesTo:
    def test_live_ball(self, detector: BlockingFoulDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: BlockingFoulDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestBlocking:
    def test_no_contact_no_foul(self, detector: BlockingFoulDetector) -> None:
        """접촉 이벤트 없으면 파울 없음."""
        ctx = _make_context(contact_events=[])
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_moving_defender_foul(self, detector: BlockingFoulDetector) -> None:
        """이동 중 수비자 + 접촉 → 블로킹 후보."""
        # 수비자 이동 시뮬레이션 (매 프레임 위치 변경)
        for i in range(5):
            ctx = _make_context(
                frame=i,
                positions={10: (5.0, 5.0), 20: (5.0 + i * 0.1, 5.0)},
                contact_events=[],
            )
            detector.evaluate(ctx)

        # 접촉 발생
        ctx = _make_context(
            frame=6,
            positions={10: (5.0, 5.0), 20: (5.5, 5.0)},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["hip", "thigh"],
                "impact_accel": 12.0,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_stationary_defender_no_blocking(self, detector: BlockingFoulDetector) -> None:
        """정지 수비자(LGP) → 블로킹 아님."""
        for i in range(10):
            ctx = _make_context(
                frame=i,
                positions={10: (5.0, 5.0), 20: (5.2, 5.0)},
                contact_events=[],
            )
            detector.evaluate(ctx)

        ctx = _make_context(
            frame=11,
            positions={10: (5.0, 5.0), 20: (5.2, 5.0)},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "contact_bodies": ["chest"],
                "impact_accel": 10.0,
            }],
        )
        result = detector.evaluate(ctx)
        # LGP 확보 → 블로킹 아님
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: BlockingFoulDetector) -> None:
        ctx = _make_context()
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2)
        result = detector.evaluate(ctx2)
        assert result.violated is False
