# -*- coding: utf-8 -*-
"""DefensiveThreeSecDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.defensive_three_sec_detector import DefensiveThreeSecDetector


@pytest.fixture()
def detector() -> DefensiveThreeSecDetector:
    return DefensiveThreeSecDetector(rule_set=RuleSet.NBA)


@pytest.fixture()
def fiba_detector() -> DefensiveThreeSecDetector:
    return DefensiveThreeSecDetector(rule_set=RuleSet.FIBA)


_PAINT = {"x_min": 4.0, "x_max": 6.0, "y_min": 0.0, "y_max": 3.0}


def _make_context(
    *,
    frame: int = 1,
    defender_id: int = 20,
    defender_pos: tuple[float, float] = (5.0, 1.5),
    offense_positions: dict[int, tuple[float, float]] | None = None,
    possession_team: str = "team_a",
    is_live: bool = True,
) -> FrameContext:
    positions = {defender_id: defender_pos}
    extra: dict = {f"player_{defender_id}_team_id": "team_b"}

    if offense_positions:
        for pid, pos in offense_positions.items():
            positions[pid] = pos
            extra[f"player_{pid}_team_id"] = possession_team

    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        possession_team_id=possession_team,
        player_positions=positions,
        paint_zone_bounds=_PAINT,
        extra=extra,
    )


class TestInit:
    def test_nba_rule_id(self, detector: DefensiveThreeSecDetector) -> None:
        assert "10.XIII" in detector.rule_id

    def test_call_type(self, detector: DefensiveThreeSecDetector) -> None:
        assert detector.call_type == CallType.TECHNICAL_FOUL

    def test_violation_type(self, detector: DefensiveThreeSecDetector) -> None:
        assert detector.violation_type == ViolationType.THREE_SECONDS


class TestAppliesTo:
    def test_nba_applies(self, detector: DefensiveThreeSecDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_fiba_does_not_apply(self, fiba_detector: DefensiveThreeSecDetector) -> None:
        """FIBA에서는 수비 3초 미적용."""
        ctx = _make_context()
        assert fiba_detector.applies_to(ctx) is False

    def test_dead_ball(self, detector: DefensiveThreeSecDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestDefensiveThreeSecond:
    def test_no_violation_guarding(self, detector: DefensiveThreeSecDetector) -> None:
        """수비가 공격 선수 근접 수비 중 — 예외 (위반 아님)."""
        for i in range(100):
            ctx = _make_context(
                frame=i,
                defender_pos=(5.0, 1.5),
                offense_positions={30: (5.5, 1.5)},  # 0.5m 거리
            )
            result = detector.evaluate(ctx)
        assert result.violated is False

    def test_violation_no_matchup(self, detector: DefensiveThreeSecDetector) -> None:
        """수비가 공격 선수 없이 페인트존 체류 — 위반."""
        for i in range(100):  # ~3.33초
            ctx = _make_context(
                frame=i,
                defender_pos=(5.0, 1.5),
                offense_positions={30: (1.0, 1.0)},  # 매우 먼 거리
            )
            result = detector.evaluate(ctx)

        assert result.confidence > 0

    def test_defender_outside_paint(self, detector: DefensiveThreeSecDetector) -> None:
        """수비가 페인트존 밖 — 카운트 안됨."""
        for i in range(100):
            ctx = _make_context(
                frame=i,
                defender_pos=(1.0, 1.0),  # 페인트 밖
            )
            result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: DefensiveThreeSecDetector) -> None:
        for i in range(50):
            ctx = _make_context(frame=i)
            detector.evaluate(ctx)
        detector.reset()
        ctx = _make_context(frame=100)
        result = detector.evaluate(ctx)
        assert result.violated is False
