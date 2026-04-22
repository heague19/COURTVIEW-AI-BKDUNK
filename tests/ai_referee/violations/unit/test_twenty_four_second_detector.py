# -*- coding: utf-8 -*-
"""TwentyFourSecondDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.twenty_four_second_detector import TwentyFourSecondDetector


@pytest.fixture()
def detector() -> TwentyFourSecondDetector:
    return TwentyFourSecondDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    shot_clock: float = 24.0,
    possession_team: str = "team_a",
    player_id: int = 10,
    event: str = "",
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        possession_team_id=possession_team,
        ball_possession_player_id=player_id,
        shot_clock_sec=shot_clock,
        extra={"shot_clock_event": event} if event else {},
    )


class TestInit:
    def test_rule_id(self, detector: TwentyFourSecondDetector) -> None:
        assert detector.rule_id == "FIBA-29"

    def test_call_type(self, detector: TwentyFourSecondDetector) -> None:
        assert detector.call_type == CallType.SHOT_CLOCK_VIOLATION

    def test_violation_type(self, detector: TwentyFourSecondDetector) -> None:
        assert detector.violation_type == ViolationType.SHOT_CLOCK


class TestAppliesTo:
    def test_live_ball(self, detector: TwentyFourSecondDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: TwentyFourSecondDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestShotClock:
    def test_clock_running_no_violation(self, detector: TwentyFourSecondDetector) -> None:
        """슛클락 진행 중 — 위반 없음."""
        ctx = _make_context(shot_clock=10.0)
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_clock_expired(self, detector: TwentyFourSecondDetector) -> None:
        """슛클락 만료 — 위반."""
        # 먼저 점유 시작 (상태 생성)
        ctx1 = _make_context(frame=1, shot_clock=1.0)
        detector.evaluate(ctx1)

        # 슛클락 만료 — remaining = 0 → <= 0 체크
        ctx2 = _make_context(frame=2, shot_clock=0.0)
        result = detector.evaluate(ctx2)
        assert result.confidence > 0

    def test_offensive_rebound_resets_14(self, detector: TwentyFourSecondDetector) -> None:
        """공격 리바운드 — 14초 리셋."""
        ctx1 = _make_context(shot_clock=3.0)
        detector.evaluate(ctx1)

        ctx_oreb = _make_context(frame=2, shot_clock=3.0, event="offensive_rebound")
        result = detector.evaluate(ctx_oreb)
        assert result.violated is False

    def test_foul_resets_14_or_remaining(self, detector: TwentyFourSecondDetector) -> None:
        """파울 — 14초 또는 남은 시간 중 큰 값."""
        ctx1 = _make_context(shot_clock=18.0)
        detector.evaluate(ctx1)

        ctx_foul = _make_context(frame=2, shot_clock=18.0, event="foul")
        result = detector.evaluate(ctx_foul)
        assert result.violated is False

    def test_possession_change_resets(self, detector: TwentyFourSecondDetector) -> None:
        """점유 변경 — 24초 풀 리셋."""
        ctx1 = _make_context(shot_clock=5.0, possession_team="team_a")
        detector.evaluate(ctx1)

        ctx_change = _make_context(
            frame=2, shot_clock=24.0, possession_team="team_b",
        )
        result = detector.evaluate(ctx_change)
        assert result.violated is False


class TestRimHit:
    def test_rim_hit_and_shot_resets(self, detector: TwentyFourSecondDetector) -> None:
        """림에 맞은 슛 → 클락 리셋."""
        ctx1 = _make_context(shot_clock=2.0)
        detector.evaluate(ctx1)

        ctx_rim = _make_context(frame=2, shot_clock=2.0, event="rim_hit")
        detector.evaluate(ctx_rim)

        ctx_shot = _make_context(frame=3, shot_clock=2.0, event="shot_attempt")
        result = detector.evaluate(ctx_shot)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: TwentyFourSecondDetector) -> None:
        ctx = _make_context(shot_clock=0.0)
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2, shot_clock=24.0)
        result = detector.evaluate(ctx2)
        assert result.violated is False
