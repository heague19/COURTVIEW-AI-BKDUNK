# -*- coding: utf-8 -*-
"""TechnicalViolationDetector 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import FrameContext, PenaltyType
from ai_referee.fouls.technical_violation_detector import (
    TechnicalType,
    TechnicalViolationDetector,
)


@pytest.fixture()
def detector() -> TechnicalViolationDetector:
    return TechnicalViolationDetector(rule_set=RuleSet.FIBA)


@pytest.fixture()
def nba_detector() -> TechnicalViolationDetector:
    return TechnicalViolationDetector(rule_set=RuleSet.NBA)


def _make_context(
    *,
    frame: int = 1,
    positions: dict | None = None,
    keypoints: dict | None = None,
    velocities: dict | None = None,
    tech_events: list | None = None,
    coach_events: list | None = None,
    ball_abuse: dict | None = None,
    is_dead: bool = False,
) -> FrameContext:
    e: dict = {}
    if tech_events is not None:
        e["technical_events"] = tech_events
    if coach_events is not None:
        e["coach_events"] = coach_events
    if ball_abuse is not None:
        e["ball_abuse_event"] = ball_abuse
    return FrameContext(
        frame_number=frame,
        is_live_ball=not is_dead,
        is_dead_ball=is_dead,
        player_positions=positions or {},
        player_keypoints=keypoints or {},
        joint_velocities=velocities or {},
        extra=e,
    )


class TestInit:
    def test_rule_id(self, detector: TechnicalViolationDetector) -> None:
        assert detector.rule_id == "FIBA-36T"

    def test_call_type(self, detector: TechnicalViolationDetector) -> None:
        assert detector.call_type == CallType.TECHNICAL_FOUL

    def test_foul_type(self, detector: TechnicalViolationDetector) -> None:
        assert detector.foul_type == FoulType.TECHNICAL


class TestTechnicalType:
    def test_protest_requires_review(self) -> None:
        assert TechnicalType.PROTEST.requires_human_review is True

    def test_delay_no_review(self) -> None:
        assert TechnicalType.DELAY.requires_human_review is False

    def test_korean_names(self) -> None:
        assert TechnicalType.PROTEST.display_name_ko == "심판 항의"
        assert TechnicalType.DELAY.display_name_ko == "지연 행위"


class TestAppliesTo:
    def test_always_applies(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context()
        assert detector.applies_to(ctx) is True

    def test_dead_ball_applies(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(is_dead=True)
        assert detector.applies_to(ctx) is True


class TestTechnicalEvents:
    def test_no_events_no_foul(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context()
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_illegal_substitution(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            tech_events=[{
                "type": "illegal_substitution",
                "player_id": 10,
                "confidence": 0.85,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence >= 0.85

    def test_court_entry(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            tech_events=[{
                "type": "unauthorized_court_entry",
                "player_id": 30,
                "confidence": 0.85,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence >= 0.85

    def test_delay_first_warning(self, detector: TechnicalViolationDetector) -> None:
        """첫 지연 행위 → 경고만 (파울 아님)."""
        ctx = _make_context(
            tech_events=[{
                "type": "delay_of_game",
                "player_id": 10,
                "confidence": 0.80,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.violated is False

    def test_delay_repeat_technical(self, detector: TechnicalViolationDetector) -> None:
        """반복 지연 행위 → 테크니컬."""
        for i in range(2):
            ctx = _make_context(
                frame=i,
                tech_events=[{
                    "type": "delay_of_game",
                    "player_id": 10,
                    "confidence": 0.80,
                }],
            )
            result = detector.evaluate(ctx)
        assert result.confidence > 0

    def test_ball_abuse(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            ball_abuse={"player_id": 10},
        )
        result = detector.evaluate(ctx)
        assert result.confidence >= 0.80

    def test_coach_box_violation(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            coach_events=[{
                "type": "box_violation",
                "coach_id": 99,
            }],
        )
        result = detector.evaluate(ctx)
        assert result.confidence >= 0.80


class TestEjection:
    def test_two_technicals_ejection(self, detector: TechnicalViolationDetector) -> None:
        """테크니컬 2개 누적 → 퇴장."""
        for i in range(2):
            ctx = _make_context(
                frame=i,
                tech_events=[{
                    "type": "illegal_substitution",
                    "player_id": 10,
                    "confidence": 0.90,
                }],
            )
            result = detector.evaluate(ctx)

        # 2번째 테크니컬에서 퇴장
        assert result.penalty == PenaltyType.EJECTION

    def test_free_throws_awarded(self, detector: TechnicalViolationDetector) -> None:
        """테크니컬 → 1FT."""
        ctx = _make_context(
            tech_events=[{
                "type": "illegal_substitution",
                "player_id": 10,
                "confidence": 0.90,
            }],
        )
        result = detector.evaluate(ctx)
        if result.violated:
            assert result.free_throws_awarded == 1


class TestNBASpecific:
    def test_timeout_excess(self, nba_detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            tech_events=[{
                "type": "timeout_excess",
                "player_id": None,
                "confidence": 0.88,
            }],
        )
        result = nba_detector.evaluate(ctx)
        assert result.confidence >= 0.88

    def test_timeout_excess_fiba_ignored(self, detector: TechnicalViolationDetector) -> None:
        """FIBA에서는 타임아웃 초과 무시."""
        ctx = _make_context(
            tech_events=[{
                "type": "timeout_excess",
                "player_id": None,
                "confidence": 0.88,
            }],
        )
        result = detector.evaluate(ctx)
        # FIBA에서는 해당 없음
        assert result.violated is False


class TestReset:
    def test_reset(self, detector: TechnicalViolationDetector) -> None:
        ctx = _make_context(
            tech_events=[{
                "type": "illegal_substitution",
                "player_id": 10,
                "confidence": 0.90,
            }],
        )
        detector.evaluate(ctx)
        detector.reset()
        ctx2 = _make_context(frame=2)
        result = detector.evaluate(ctx2)
        assert result.violated is False
