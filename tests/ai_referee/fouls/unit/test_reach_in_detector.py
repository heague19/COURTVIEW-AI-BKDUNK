# -*- coding: utf-8 -*-
"""ReachInDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.reach_in_detector import ReachInDetector


@pytest.fixture()
def detector() -> ReachInDetector:
    return ReachInDetector(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    ball_pos: tuple | None = (5.0, 5.0, 1.0),
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
        player_positions=positions or {10: (5.0, 5.0), 20: (5.3, 5.0)},
        player_keypoints=keypoints or {},
        ball_position=ball_pos,
        ball_possession_player_id=ball_holder,
        possession_team_id="team_a",
        extra=e,
    )


def _reach_keypoints() -> dict:
    """수비자 손이 실린더 밖으로 뻗어 공격자 팔에 접촉."""
    return {
        10: {
            "left_wrist": (5.0, 4.8, 1.2),
            "right_wrist": (5.0, 5.2, 1.2),
            "left_elbow": (5.0, 4.9, 1.3),
            "right_elbow": (5.0, 5.1, 1.3),
        },
        20: {
            "left_shoulder": (5.3, 4.8, 1.5),
            "right_shoulder": (5.3, 5.2, 1.5),
            "left_wrist": (5.05, 5.0, 1.2),  # 공격자 팔 근처
            "right_wrist": (5.6, 5.0, 1.2),
        },
    }


class TestInit:
    def test_rule_id(self, detector: ReachInDetector) -> None:
        assert detector.rule_id == "FIBA-33.8"

    def test_call_type(self, detector: ReachInDetector) -> None:
        assert detector.call_type == CallType.PERSONAL_FOUL

    def test_foul_type(self, detector: ReachInDetector) -> None:
        assert detector.foul_type == FoulType.PERSONAL


class TestAppliesTo:
    def test_live_ball_with_holder(self, detector: ReachInDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_no_ball_holder(self, detector: ReachInDetector) -> None:
        ctx = _make_context(ball_holder=None)
        assert detector.applies_to(ctx) is False


class TestReachIn:
    def test_no_keypoints_no_foul(self, detector: ReachInDetector) -> None:
        ctx = _make_context()
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_reach_body_contact(self, detector: ReachInDetector) -> None:
        """실린더 밖 뻗기 + 신체 접촉 → 파울."""
        ctx = _make_context(keypoints=_reach_keypoints())
        result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_reach_ball_only_no_foul(self, detector: ReachInDetector) -> None:
        """공만 접촉 → 합법 스틸."""
        kp = {
            10: {
                "left_wrist": (5.0, 5.0, 1.0),
                "right_wrist": (5.0, 5.3, 1.0),
                "left_elbow": (5.0, 4.9, 1.1),
                "right_elbow": (5.0, 5.2, 1.1),
            },
            20: {
                "left_shoulder": (5.3, 4.8, 1.5),
                "right_shoulder": (5.3, 5.2, 1.5),
                "left_wrist": (5.0, 5.0, 1.0),  # 공 위치와 동일
                "right_wrist": (5.6, 5.0, 1.0),
            },
        }
        ctx = _make_context(
            keypoints=kp,
            ball_pos=(5.0, 5.0, 1.0),
        )
        result = detector.evaluate(ctx)
        # 공만 접촉한 경우 낮은 신뢰도
        assert result.confidence < 0.80 or result.violated is False

    def test_far_defender_no_reach(self, detector: ReachInDetector) -> None:
        """수비자 멀리 있으면 리치인 아님."""
        kp = {
            10: {
                "left_wrist": (5.0, 5.0, 1.2),
                "right_wrist": (5.0, 5.3, 1.2),
            },
            20: {
                "left_shoulder": (7.0, 4.8, 1.5),
                "right_shoulder": (7.0, 5.2, 1.5),
                "left_wrist": (6.5, 5.0, 1.2),
                "right_wrist": (7.5, 5.0, 1.2),
            },
        }
        ctx = _make_context(
            positions={10: (5.0, 5.0), 20: (7.0, 5.0)},
            keypoints=kp,
        )
        result = detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: ReachInDetector) -> None:
        ctx = _make_context(keypoints=_reach_keypoints())
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2)
        result = detector.evaluate(ctx2)
        assert result.violated is False
