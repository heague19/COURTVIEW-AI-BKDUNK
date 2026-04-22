# -*- coding: utf-8 -*-
"""GoaltendingDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.violations.goaltending_detector import GoaltendingDetector


@pytest.fixture()
def fiba_detector() -> GoaltendingDetector:
    return GoaltendingDetector(rule_set=RuleSet.FIBA)


@pytest.fixture()
def nba_detector() -> GoaltendingDetector:
    return GoaltendingDetector(rule_set=RuleSet.NBA)


def _make_context(
    *,
    frame: int = 1,
    ball_pos: tuple[float, float, float] = (5.0, 5.0, 3.5),
    defender_id: int = 20,
    defender_hand: tuple[float, float, float] = (10.0, 10.0, 2.0),  # 기본은 멀리
    shooter_id: int = 10,
    shot_in_progress: bool = False,
    hoop_x: float = 5.0,
    hoop_y: float = 5.0,
    hoop_z: float = 3.05,
    is_live: bool = True,
) -> FrameContext:
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        ball_position=ball_pos,
        player_keypoints={
            defender_id: {
                "left_wrist": defender_hand,
                "right_wrist": (defender_hand[0] + 0.1, defender_hand[1], defender_hand[2]),
            },
        },
        extra={
            "shot_in_progress": shot_in_progress,
            "shooter_id": shooter_id,
            "hoop_x": hoop_x,
            "hoop_y": hoop_y,
            "hoop_z": hoop_z,
            "cylinder_radius_m": 0.225,
        },
    )


class TestInit:
    def test_fiba_rule_id(self, fiba_detector: GoaltendingDetector) -> None:
        assert detector_rule_id(fiba_detector) == "FIBA-31"

    def test_nba_rule_id(self, nba_detector: GoaltendingDetector) -> None:
        assert detector_rule_id(nba_detector) == "NBA-31"

    def test_violation_type(self, fiba_detector: GoaltendingDetector) -> None:
        assert fiba_detector.violation_type == ViolationType.GOALTENDING


def detector_rule_id(d: GoaltendingDetector) -> str:
    return d.rule_id


class TestAppliesTo:
    def test_live_ball(self, fiba_detector: GoaltendingDetector) -> None:
        ctx = _make_context()
        assert fiba_detector.applies_to(ctx) is True

    def test_dead_ball(self, fiba_detector: GoaltendingDetector) -> None:
        ctx = _make_context(is_live=False)
        assert fiba_detector.applies_to(ctx) is False


class TestGoaltending:
    def test_no_shot_in_progress(self, fiba_detector: GoaltendingDetector) -> None:
        """슛 미진행 — 골텐딩 불가."""
        ctx = _make_context(shot_in_progress=False)
        result = fiba_detector.evaluate(ctx)
        assert result.violated is False

    def test_descending_ball_touch(self, fiba_detector: GoaltendingDetector) -> None:
        """하강 중 공 터치 — 골텐딩."""
        # 슛 시작 (상승)
        ctx1 = _make_context(
            frame=1, shot_in_progress=True,
            ball_pos=(5.0, 5.0, 2.5),
        )
        fiba_detector.evaluate(ctx1)

        # 상승
        ctx2 = _make_context(
            frame=2, ball_pos=(5.0, 5.0, 3.2),
        )
        fiba_detector.evaluate(ctx2)

        # 최고점 (림 위)
        ctx3 = _make_context(
            frame=3, ball_pos=(5.0, 5.0, 3.5),
        )
        fiba_detector.evaluate(ctx3)

        # 하강 + 수비자 터치
        ctx4 = _make_context(
            frame=4,
            ball_pos=(5.0, 5.0, 3.2),
            defender_hand=(5.0, 5.0, 3.2),  # 공 위치에 손
        )
        result = fiba_detector.evaluate(ctx4)
        assert result.confidence > 0

    def test_ascending_ball_touch_no_goaltending(self, fiba_detector: GoaltendingDetector) -> None:
        """상승 중 공 터치 — 골텐딩 아님 (블록)."""
        ctx1 = _make_context(
            frame=1, shot_in_progress=True,
            ball_pos=(5.0, 5.0, 2.0),
        )
        fiba_detector.evaluate(ctx1)

        # 상승 중 터치
        ctx2 = _make_context(
            frame=2,
            ball_pos=(5.0, 5.0, 2.5),
            defender_hand=(5.0, 5.0, 2.5),
        )
        result = fiba_detector.evaluate(ctx2)
        # 아직 상승 중이므로 골텐딩 아님
        assert result.violated is False


class TestBasketInterference:
    def test_ball_in_cylinder_touch(self, fiba_detector: GoaltendingDetector) -> None:
        """실린더 내 공 터치 — 바스켓 인터피어런스."""
        ctx1 = _make_context(
            frame=1, shot_in_progress=True,
            ball_pos=(5.0, 5.0, 2.5),
        )
        fiba_detector.evaluate(ctx1)

        ctx2 = _make_context(
            frame=2, ball_pos=(5.0, 5.0, 3.2),
        )
        fiba_detector.evaluate(ctx2)

        # 실린더 내 (림 위치 근접 + 높이 림 ±0.3)
        ctx3 = _make_context(
            frame=3,
            ball_pos=(5.05, 5.05, 3.05),  # 림 거의 정확 위치
            defender_hand=(5.05, 5.05, 3.05),
        )
        result = fiba_detector.evaluate(ctx3)
        assert result.confidence > 0


class TestFIBAvsNBA:
    def test_fiba_rim_touch_blocks(self, fiba_detector: GoaltendingDetector) -> None:
        """FIBA: 림 접촉 후 터치 불가."""
        assert fiba_detector._rim_touch_allowed is False

    def test_nba_rim_touch_allowed(self, nba_detector: GoaltendingDetector) -> None:
        """NBA: 림 접촉 후 터치 가능."""
        assert nba_detector._rim_touch_allowed is True


class TestNoBall:
    def test_no_ball(self, fiba_detector: GoaltendingDetector) -> None:
        ctx = FrameContext(
            frame_number=1,
            is_live_ball=True,
            is_dead_ball=False,
            ball_position=None,
        )
        result = fiba_detector.evaluate(ctx)
        assert result.violated is False


class TestReset:
    def test_reset(self, fiba_detector: GoaltendingDetector) -> None:
        ctx = _make_context(shot_in_progress=True, ball_pos=(5.0, 5.0, 3.0))
        fiba_detector.evaluate(ctx)
        fiba_detector.reset()
        ctx2 = _make_context(frame=2, ball_pos=(5.0, 5.0, 3.0))
        result = fiba_detector.evaluate(ctx2)
        assert result.violated is False
