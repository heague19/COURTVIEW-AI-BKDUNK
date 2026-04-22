# -*- coding: utf-8 -*-
"""IllegalScreenDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.illegal_screen_detector import IllegalScreenDetector


@pytest.fixture()
def detector() -> IllegalScreenDetector:
    return IllegalScreenDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    ball_holder: int = 10,
    contact_events: list | None = None,
    extra: dict | None = None,
    is_live: bool = True,
) -> FrameContext:
    e = extra or {}
    e.setdefault("player_10_team_id", "team_a")
    e.setdefault("player_11_team_id", "team_a")
    e.setdefault("player_20_team_id", "team_b")
    if contact_events is not None:
        e["contact_events"] = contact_events
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        player_positions=positions or {10: (5.0, 5.0), 11: (5.3, 5.0), 20: (5.4, 5.0)},
        player_keypoints=keypoints or {},
        ball_possession_player_id=ball_holder,
        possession_team_id="team_a",
        extra=e,
    )


class TestInit:
    def test_rule_id(self, detector: IllegalScreenDetector) -> None:
        assert detector.rule_id == "FIBA-33.7S"

    def test_call_type(self, detector: IllegalScreenDetector) -> None:
        assert detector.call_type == CallType.OFFENSIVE_FOUL

    def test_foul_type(self, detector: IllegalScreenDetector) -> None:
        assert detector.foul_type == FoulType.ILLEGAL_SCREEN


class TestAppliesTo:
    def test_live_ball(self, detector: IllegalScreenDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball(self, detector: IllegalScreenDetector) -> None:
        ctx = _make_context(is_live=False)
        assert detector.applies_to(ctx) is False


class TestIllegalScreen:
    def test_no_screen_no_foul(self, detector: IllegalScreenDetector) -> None:
        """스크린 근처가 아니면 파울 없음."""
        ctx = _make_context(
            positions={10: (5.0, 5.0), 11: (8.0, 8.0), 20: (3.0, 3.0)},
        )
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_moving_screen(self, detector: IllegalScreenDetector) -> None:
        """스크린 설정 중 이동 → 무빙 스크린."""
        for i in range(5):
            ctx = _make_context(
                frame=i,
                positions={
                    10: (5.0, 5.0),
                    11: (5.3 + i * 0.05, 5.0),  # 스크리너 이동
                    20: (5.4, 5.0),
                },
                contact_events=[],
            )
            detector.evaluate(ctx)

        # 접촉 발생
        ctx = _make_context(
            frame=6,
            positions={10: (5.0, 5.0), 11: (5.55, 5.0), 20: (5.5, 5.0)},
            contact_events=[{
                "offender_id": 11,
                "victim_id": 20,
                "contact_bodies": ["shoulder"],
                "impact_accel": 10.0,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_stationary_screen_legal(self, detector: IllegalScreenDetector) -> None:
        """정지 스크린 → 합법 (파울 아님)."""
        for i in range(5):
            ctx = _make_context(
                frame=i,
                positions={10: (5.0, 5.0), 11: (5.3, 5.0), 20: (5.5, 5.0)},
                contact_events=[],
            )
            detector.evaluate(ctx)
        result = detector.evaluate(
            _make_context(frame=6, contact_events=[]),
        )
        # 이동 없으면 낮은 신뢰도
        assert result.violated is False

    def test_possession_change(self, detector: IllegalScreenDetector) -> None:
        """불법 스크린 → 공격 파울 → 점유 전환."""
        # 위반 발생 시 possession_change 확인
        result = detector.evaluate(_make_context())
        if result.violated:
            assert result.possession_change is True


class TestReset:
    def test_reset(self, detector: IllegalScreenDetector) -> None:
        ctx = _make_context()
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2)
        result = detector.evaluate(ctx2)
        assert result.violated is False
