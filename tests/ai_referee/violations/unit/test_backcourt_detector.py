# -*- coding: utf-8 -*-
"""BackcourtDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.backcourt_detector import BackcourtDetector


@pytest.fixture()
def detector() -> BackcourtDetector:
    return BackcourtDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    ball_x: float = 15.0,
    half_x: float = 14.0,
    possession_team: str = "team_a",
    player_id: int = 10,
    attack_dir: str = "right",
    is_live: bool = True,
    is_tip_off: bool = False,
    last_touch_team: str | None = None,
) -> FrameContext:
    extra: dict = {"attack_direction": attack_dir}
    if is_tip_off:
        extra["is_tip_off"] = True
    if last_touch_team:
        extra["last_touch_team_id"] = last_touch_team
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        possession_team_id=possession_team,
        ball_possession_player_id=player_id,
        ball_position=(ball_x, 5.0, 1.0),
        half_court_x=half_x,
        extra=extra,
    )


class TestInit:
    def test_rule_id(self, detector: BackcourtDetector) -> None:
        assert detector.rule_id == "FIBA-30"

    def test_call_type(self, detector: BackcourtDetector) -> None:
        assert detector.call_type == CallType.BACKCOURT_VIOLATION

    def test_violation_type(self, detector: BackcourtDetector) -> None:
        assert detector.violation_type == ViolationType.BACKCOURT


class TestAppliesTo:
    def test_live_ball(self, detector: BackcourtDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: BackcourtDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestBackcourtViolation:
    def test_frontcourt_to_backcourt(self, detector: BackcourtDetector) -> None:
        """프론트코트 → 백코트 — 위반."""
        # 프론트코트에서 시작
        ctx1 = _make_context(frame=1, ball_x=20.0)
        detector.evaluate(ctx1)

        # 백코트로 이동
        ctx2 = _make_context(frame=2, ball_x=5.0)
        result = detector.evaluate(ctx2)
        assert result.confidence > 0

    def test_stay_in_frontcourt(self, detector: BackcourtDetector) -> None:
        """프론트코트 유지 — 위반 없음."""
        ctx1 = _make_context(frame=1, ball_x=20.0)
        detector.evaluate(ctx1)

        ctx2 = _make_context(frame=2, ball_x=18.0)
        result = detector.evaluate(ctx2)
        assert result.violated is False

    def test_backcourt_stay(self, detector: BackcourtDetector) -> None:
        """백코트에서 계속 — 위반 없음 (아직 프론트코트 미진입)."""
        ctx1 = _make_context(frame=1, ball_x=5.0)
        detector.evaluate(ctx1)

        ctx2 = _make_context(frame=2, ball_x=3.0)
        result = detector.evaluate(ctx2)
        assert result.violated is False


class TestExceptions:
    def test_tip_off_exception(self, detector: BackcourtDetector) -> None:
        """점프볼 예외."""
        ctx = _make_context(frame=1, ball_x=15.0, is_tip_off=True)
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_defense_deflection(self, detector: BackcourtDetector) -> None:
        """수비팀에 의한 백코트 이동 — 위반 아님."""
        ctx1 = _make_context(frame=1, ball_x=20.0)
        detector.evaluate(ctx1)

        ctx2 = _make_context(
            frame=2, ball_x=5.0,
            last_touch_team="team_b",  # 수비팀 터치
            possession_team="team_a",
        )
        result = detector.evaluate(ctx2)
        assert result.violated is False

    def test_possession_change_resets(self, detector: BackcourtDetector) -> None:
        """점유 변경 시 상태 리셋."""
        ctx1 = _make_context(frame=1, ball_x=20.0, possession_team="team_a")
        detector.evaluate(ctx1)

        ctx2 = _make_context(frame=2, ball_x=5.0, possession_team="team_b")
        result = detector.evaluate(ctx2)
        assert result.violated is False


class TestNoBall:
    def test_no_ball_position(self, detector: BackcourtDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            possession_team_id="team_a",
            ball_position=None,
            half_court_x=14.0,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: BackcourtDetector) -> None:
        ctx = _make_context(frame=1, ball_x=20.0)
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2, ball_x=5.0)
        result = detector.evaluate(ctx2)
        assert result.violated is False  # 리셋 후 새 상태
