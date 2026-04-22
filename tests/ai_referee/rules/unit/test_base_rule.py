# -*- coding: utf-8 -*-
"""base_rule.py 단위 테스트 — 25 tests."""
from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import FoulType, ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    BaseRule,
    FoulRule,
    FrameContext,
    PenaltyType,
    RuleCategory,
    RuleParameters,
    RuleResult,
    ViolationRule,
)


# =============================================================================
# Fixture
# =============================================================================
def _ctx(frame_number: int = 100, **kwargs) -> FrameContext:
    """테스트용 FrameContext 생성."""
    defaults = dict(
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        quarter=1,
        game_clock_sec=500.0,
        shot_clock_sec=18.0,
        is_dead_ball=False,
        is_live_ball=True,
    )
    defaults.update(kwargs)
    return FrameContext(**defaults)


class _DummyViolationRule(ViolationRule):
    """테스트용 ViolationRule 구현."""

    def __init__(self, *, always_applies: bool = True, always_violates: bool = False):
        super().__init__(
            rule_id="TEST-V1",
            rule_set=RuleSet.FIBA,
            call_type=CallType.TRAVELING,
            violation_type=ViolationType.TRAVELING,
            rule_reference="Test Rule V1",
            description="테스트 바이올레이션",
        )
        self._always_applies = always_applies
        self._always_violates = always_violates

    def applies_to(self, context: FrameContext) -> bool:
        return self._always_applies and not context.is_dead_ball

    def evaluate(self, context: FrameContext) -> RuleResult:
        if self._always_violates:
            return self._make_violation_result(
                context,
                violated=True,
                confidence=0.92,
                description="트래블링 감지",
                evidence=["피봇풋 들림 감지"],
                offending_player_id=5,
            )
        return self._make_violation_result(
            context, violated=False, confidence=0.10,
        )


class _DummyFoulRule(FoulRule):
    """테스트용 FoulRule 구현."""

    def __init__(self, *, always_violates: bool = False):
        super().__init__(
            rule_id="TEST-F1",
            rule_set=RuleSet.FIBA,
            call_type=CallType.PERSONAL_FOUL,
            foul_type=FoulType.BLOCKING,
            rule_reference="Test Rule F1",
            description="테스트 블로킹 파울",
            default_free_throws=2,
        )
        self._always_violates = always_violates

    def applies_to(self, context: FrameContext) -> bool:
        return context.is_live_ball

    def evaluate(self, context: FrameContext) -> RuleResult:
        if self._always_violates:
            return self._make_foul_result(
                context,
                violated=True,
                confidence=0.88,
                description="블로킹 파울 감지",
                evidence=["접촉 감지", "수비 위치 불법"],
                offending_player_id=3,
                victim_player_id=7,
            )
        return self._make_foul_result(
            context, violated=False, confidence=0.05,
        )


# =============================================================================
# RuleCategory 테스트
# =============================================================================
class TestRuleCategory:
    def test_values(self):
        assert RuleCategory.VIOLATION.value == "violation"
        assert RuleCategory.FOUL.value == "foul"
        assert RuleCategory.TECHNICAL.value == "technical"

    def test_display_name_ko(self):
        assert RuleCategory.VIOLATION.display_name_ko == "바이올레이션"
        assert RuleCategory.FOUL.display_name_ko == "파울"

    def test_stops_play(self):
        for cat in RuleCategory:
            assert cat.stops_play is True


# =============================================================================
# PenaltyType 테스트
# =============================================================================
class TestPenaltyType:
    def test_values(self):
        assert PenaltyType.TURNOVER.value == "turnover"
        assert PenaltyType.FREE_THROWS.value == "free_throws"
        assert PenaltyType.EJECTION.value == "ejection"
        assert PenaltyType.NONE.value == "none"


# =============================================================================
# FrameContext 테스트
# =============================================================================
class TestFrameContext:
    def test_default(self):
        ctx = FrameContext()
        assert ctx.frame_number == 0
        assert ctx.quarter == 1
        assert ctx.is_live_ball is True
        assert ctx.is_dead_ball is False

    def test_custom(self):
        ctx = _ctx(frame_number=300, quarter=3, is_dead_ball=True)
        assert ctx.frame_number == 300
        assert ctx.quarter == 3
        assert ctx.is_dead_ball is True

    def test_player_positions(self):
        ctx = _ctx(player_positions={1: (5.0, 3.0), 2: (8.0, 6.0)})
        assert len(ctx.player_positions) == 2
        assert ctx.player_positions[1] == (5.0, 3.0)


# =============================================================================
# RuleResult 테스트
# =============================================================================
class TestRuleResult:
    def test_default(self):
        r = RuleResult()
        assert r.violated is False
        assert r.confidence == 0.0
        assert r.is_violation is False
        assert r.is_foul is False

    def test_violation_result(self):
        r = RuleResult(
            violated=True,
            confidence=0.90,
            category=RuleCategory.VIOLATION,
        )
        assert r.is_violation is True
        assert r.is_foul is False

    def test_foul_result(self):
        r = RuleResult(
            violated=True,
            confidence=0.85,
            category=RuleCategory.FOUL,
        )
        assert r.is_foul is True

    def test_frame_range(self):
        r = RuleResult(start_frame=100, end_frame=150)
        assert r.frame_range == (100, 150)


# =============================================================================
# RuleParameters 테스트
# =============================================================================
class TestRuleParameters:
    def test_get_nested_key(self):
        p = RuleParameters(
            parameters={"a": {"b": {"c": 42}}},
        )
        assert p.get("a.b.c") == 42
        assert p.get("a.b.d", "default") == "default"

    def test_get_float(self):
        p = RuleParameters(parameters={"threshold": 0.75})
        assert p.get_float("threshold") == 0.75
        assert p.get_float("missing", 0.5) == 0.5

    def test_get_int(self):
        p = RuleParameters(parameters={"max_steps": 3})
        assert p.get_int("max_steps") == 3

    def test_get_bool(self):
        p = RuleParameters(parameters={"enabled": True})
        assert p.get_bool("enabled") is True
        assert p.get_bool("missing", False) is False


# =============================================================================
# ViolationRule 테스트
# =============================================================================
class TestViolationRule:
    def test_check_no_violation(self):
        rule = _DummyViolationRule(always_violates=False)
        result = rule.check(_ctx())
        assert result.violated is False
        assert result.call_type == CallType.NO_CALL

    def test_check_violation(self):
        rule = _DummyViolationRule(always_violates=True)
        result = rule.check(_ctx())
        assert result.violated is True
        assert result.confidence == 0.92
        assert result.penalty == PenaltyType.TURNOVER
        assert result.possession_change is True
        assert result.offending_player_id == 5
        assert result.violation_type == ViolationType.TRAVELING

    def test_dead_ball_skip(self):
        rule = _DummyViolationRule(always_violates=True)
        result = rule.check(_ctx(is_dead_ball=True))
        assert result.violated is False
        assert "적용 불가" in result.description

    def test_disabled_skip(self):
        rule = _DummyViolationRule(always_violates=True)
        rule.enabled = False
        result = rule.check(_ctx())
        assert result.violated is False
        assert "비활성화" in result.description

    def test_stats(self):
        rule = _DummyViolationRule(always_violates=True)
        rule.check(_ctx(frame_number=1))
        rule.check(_ctx(frame_number=2))
        stats = rule.get_stats()
        assert stats["eval_count"] == 2
        assert stats["violation_count"] == 2
        assert stats["violation_rate"] == 1.0

    def test_reset(self):
        rule = _DummyViolationRule(always_violates=True)
        rule.check(_ctx())
        rule.reset()
        stats = rule.get_stats()
        assert stats["eval_count"] == 0


# =============================================================================
# FoulRule 테스트
# =============================================================================
class TestFoulRule:
    def test_check_no_foul(self):
        rule = _DummyFoulRule(always_violates=False)
        result = rule.check(_ctx())
        assert result.violated is False

    def test_check_foul(self):
        rule = _DummyFoulRule(always_violates=True)
        result = rule.check(_ctx())
        assert result.violated is True
        assert result.confidence == 0.88
        assert result.foul_type == FoulType.BLOCKING
        assert result.penalty == PenaltyType.FREE_THROWS
        assert result.free_throws_awarded == 2
        assert result.offending_player_id == 3
        assert result.victim_player_id == 7
        assert len(result.evidence) == 2

    def test_repr(self):
        rule = _DummyFoulRule()
        r = repr(rule)
        assert "TEST-F1" in r
        assert "foul" in r
