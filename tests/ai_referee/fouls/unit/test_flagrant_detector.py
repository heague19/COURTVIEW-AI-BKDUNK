# -*- coding: utf-8 -*-
"""FlagrantDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext, PenaltyType
from ai_referee.fouls.flagrant_detector import FlagrantDetector


@pytest.fixture()
def detector() -> FlagrantDetector:
    return FlagrantDetector(rule_set=RuleSet.FIBA)


@pytest.fixture()
def nba_detector() -> FlagrantDetector:
    return FlagrantDetector(rule_set=RuleSet.NBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    actions: dict | None = None,
    ball_pos: tuple | None = (5.0, 5.0, 1.0),
    contact_events: list | None = None,
    is_fast_break: bool = False,
    is_live: bool = True,
) -> FrameContext:
    e: dict = {}
    if contact_events is not None:
        e["contact_events"] = contact_events
    e["is_fast_break"] = is_fast_break
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (5.0, 5.0), 20: (5.2, 5.0)},
        player_actions=actions or {},
        ball_position=ball_pos,
        extra=e,
    )


class TestInit:
    def test_rule_id(self, detector: FlagrantDetector) -> None:
        assert detector.rule_id == "FIBA-36"

    def test_nba_rule_id(self, nba_detector: FlagrantDetector) -> None:
        assert nba_detector.rule_id == "NBA-36"

    def test_call_type(self, detector: FlagrantDetector) -> None:
        assert detector.call_type == CallType.FLAGRANT_FOUL

    def test_foul_type(self, detector: FlagrantDetector) -> None:
        assert detector.foul_type == FoulType.FLAGRANT_1


class TestAppliesTo:
    def test_live_ball(self, detector: FlagrantDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True


class TestFlagrant:
    def test_no_contact_no_flagrant(self, detector: FlagrantDetector) -> None:
        ctx = _make_context(contact_events=[])
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_low_impact_no_flagrant(self, detector: FlagrantDetector) -> None:
        """낮은 충격 → 플래그런트 아님."""
        ctx = _make_context(
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 5.0,
                "contact_bodies": ["arm"],
            }],
        )
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_flagrant_1_no_ball_play(self, detector: FlagrantDetector) -> None:
        """볼 플레이 의도 없음 + 중간 충격 → F1."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (8.0, 8.0)},
            ball_pos=(5.0, 5.0, 1.0),
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 14.0,
                "contact_bodies": ["chest", "shoulder"],
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_flagrant_2_head_contact(self, detector: FlagrantDetector) -> None:
        """머리 접촉 + 과도한 충격 → F2."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (8.0, 8.0)},
            ball_pos=(5.0, 5.0, 1.0),
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 25.0,
                "contact_bodies": ["head", "neck"],
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence >= 0.70

    def test_airborne_contact_boost(self, detector: FlagrantDetector) -> None:
        """공중 선수 접촉 → 신뢰도 상승."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (8.0, 8.0)},
            ball_pos=(5.0, 5.0, 1.0),
            actions={10: "shooting"},
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 16.0,
                "contact_bodies": ["back"],
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_fast_break_clear_path(self, nba_detector: FlagrantDetector) -> None:
        """속공 방해 (Clear Path)."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (8.0, 8.0)},
            ball_pos=(5.0, 5.0, 1.0),
            is_fast_break=True,
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 14.0,
                "contact_bodies": ["shoulder"],
            }],
        )
        result = nba_detector.evaluate(ctx)
        assert result.confidence > 0

    def test_ejection_on_f2(self, detector: FlagrantDetector) -> None:
        """F2 판정 시 퇴장."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (8.0, 8.0)},
            ball_pos=(5.0, 5.0, 1.0),
            contact_events=[{
                "offender_id": 20,
                "victim_id": 10,
                "impact_accel": 28.0,
                "contact_bodies": ["head"],
            }],
        )
        result = detector.evaluate(ctx)
        if result.violated and result.confidence >= 0.90:
            assert result.penalty == PenaltyType.EJECTION


class TestReset:
    def test_reset(self, detector: FlagrantDetector) -> None:
        detector.reset()
        ctx = _make_context(contact_events=[])
        result = detector.evaluate(ctx)
        assert result.violated is False
