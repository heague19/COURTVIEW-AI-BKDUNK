# -*- coding: utf-8 -*-
"""FoulSeverityAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.base_rule import FrameContext
from ai_referee.fouls.foul_severity_analyzer import (
    FoulSeverityAnalyzer,
    SeverityGrade,
    SeverityResult,
)


@pytest.fixture()
def analyzer() -> FoulSeverityAnalyzer:
    return FoulSeverityAnalyzer(rule_set=RuleSet.FIBA)


def _make_context(
    *,
    frame: int = 1,
    contact_events: list | None = None,
    player_actions: dict | None = None,
    quarter: int = 1,
    game_clock: float = 600.0,
    is_live: bool = True,
) -> FrameContext:
    e: dict = {}
    if contact_events is not None:
        e["contact_events"] = contact_events
    return FrameContext(
        frame_number=frame,
        is_live_ball=is_live,
        is_dead_ball=not is_live,
        quarter=quarter,
        game_clock_sec=game_clock,
        player_actions=player_actions or {},
        extra=e,
    )


class TestInit:
    def test_rule_id(self, analyzer: FoulSeverityAnalyzer) -> None:
        assert analyzer.rule_id == "FIBA-SEVERITY"


class TestSeverityGrade:
    def test_light(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(
            contact_events=[{"impact_accel": 5.0, "contact_bodies": ["arm"]}],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.grade == SeverityGrade.LIGHT

    def test_moderate(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 12.0, "contact_bodies": ["chest"],
            }],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.grade == SeverityGrade.MODERATE

    def test_hard(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 22.0, "contact_bodies": ["shoulder"],
            }],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.grade == SeverityGrade.HARD

    def test_excessive(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 30.0, "contact_bodies": ["head"],
            }],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.grade == SeverityGrade.EXCESSIVE


class TestFlagrantThreshold:
    def test_high_impact_head_flagrant(self, analyzer: FoulSeverityAnalyzer) -> None:
        """머리 접촉 + 높은 충격 → 플래그런트."""
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 25.0,
                "contact_bodies": ["head"],
                "ball_distance": 2.0,
            }],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.is_flagrant_1 is True

    def test_low_impact_no_flagrant(self, analyzer: FoulSeverityAnalyzer) -> None:
        """낮은 충격 → 플래그런트 아님."""
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 5.0,
                "contact_bodies": ["arm"],
            }],
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.is_flagrant_1 is False

    def test_airborne_vulnerability(self, analyzer: FoulSeverityAnalyzer) -> None:
        """공중 선수 접촉 → 취약성 점수 상승."""
        ctx = _make_context(
            contact_events=[{
                "impact_accel": 18.0,
                "contact_bodies": ["back"],
                "victim_id": 10,
                "ball_distance": 1.5,
            }],
            player_actions={10: "shooting"},
        )
        analyzer.evaluate(ctx)
        sev = analyzer.last_severity
        assert sev is not None
        assert sev.vulnerability_score > 0


class TestNoContact:
    def test_no_events(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(contact_events=[])
        result = analyzer.evaluate(ctx)
        assert result.violated is False
        assert analyzer.last_severity is None


class TestAnalyzeAPI:
    def test_analyze_method(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context()
        event = {"impact_accel": 15.0, "contact_bodies": ["chest"]}
        result = analyzer.analyze(ctx, event)
        assert isinstance(result, SeverityResult)
        assert result.severity_score > 0


class TestReset:
    def test_reset(self, analyzer: FoulSeverityAnalyzer) -> None:
        ctx = _make_context(
            contact_events=[{"impact_accel": 15.0, "contact_bodies": ["arm"]}],
        )
        analyzer.evaluate(ctx)
        analyzer.reset()
        assert analyzer.last_severity is None
