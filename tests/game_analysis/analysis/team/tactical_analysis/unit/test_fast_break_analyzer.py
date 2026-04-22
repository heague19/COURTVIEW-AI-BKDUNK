# -*- coding: utf-8 -*-
"""FastBreakAnalyzer 단위 테스트 — 12 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.fast_break_analyzer import (
    FastBreakAnalyzer,
    FastBreakAnalyzerConfig,
    FastBreakEventInput,
    FastBreakOutcome,
)
from shared.constants.tactical_constants import TransitionPhase


# =============================================================================
# 헬퍼
# =============================================================================
def _make_fb(
    team_id: str = "home",
    attackers: int = 3,
    defenders: int = 2,
    time_sec: float = 4.0,
    phase: TransitionPhase = TransitionPhase.PRIMARY_BREAK,
    outcome: FastBreakOutcome = FastBreakOutcome.SCORE,
    points: int = 2,
    confidence: float = 0.85,
) -> FastBreakEventInput:
    return FastBreakEventInput(
        team_id=team_id,
        attackers=attackers,
        defenders=defenders,
        transition_time_sec=time_sec,
        phase=phase,
        outcome=outcome,
        points_scored=points,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestFastBreakAnalyzer:
    """FastBreakAnalyzer 단위 테스트."""

    def test_init_default(self):
        fb = FastBreakAnalyzer()
        assert fb.name == "FastBreakAnalyzer"

    def test_process_single_fast_break(self):
        fb = FastBreakAnalyzer()
        ok = fb.process_fast_break(_make_fb(points=2))
        assert ok is True
        result = fb.get_team_analysis("home")
        assert result.total_fast_breaks == 1
        assert result.fast_break_ppp == 2.0

    def test_multiple_fast_breaks_ppp(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb(points=2))
        fb.process_fast_break(_make_fb(points=3))
        fb.process_fast_break(_make_fb(points=0, outcome=FastBreakOutcome.MISSED))
        result = fb.get_team_analysis("home")
        # PPP = 5/3 ≈ 1.667
        assert abs(result.fast_break_ppp - 1.667) < 0.01

    def test_advantage_counts(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb(attackers=2, defenders=1))
        fb.process_fast_break(_make_fb(attackers=3, defenders=2))
        fb.process_fast_break(_make_fb(attackers=2, defenders=1))
        result = fb.get_team_analysis("home")
        assert result.numerical_advantage_counts["2v1"] == 2
        assert result.numerical_advantage_counts["3v2"] == 1

    def test_success_rate(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb(attackers=2, defenders=1, points=2))
        fb.process_fast_break(_make_fb(attackers=2, defenders=1, points=0))
        result = fb.get_team_analysis("home")
        assert result.success_rate_by_advantage["2v1"] == 0.5

    def test_avg_transition_time(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb(time_sec=3.0))
        fb.process_fast_break(_make_fb(time_sec=5.0))
        result = fb.get_team_analysis("home")
        assert result.average_transition_time_seconds == 4.0

    def test_classify_phase_primary(self):
        fb = FastBreakAnalyzer()
        assert fb.classify_phase(3.0) == TransitionPhase.PRIMARY_BREAK

    def test_classify_phase_secondary(self):
        fb = FastBreakAnalyzer()
        assert fb.classify_phase(6.0) == TransitionPhase.SECONDARY_BREAK

    def test_classify_phase_early_offense(self):
        fb = FastBreakAnalyzer()
        assert fb.classify_phase(10.0) == TransitionPhase.EARLY_OFFENSE

    def test_is_fast_break_opportunity(self):
        fb = FastBreakAnalyzer()
        assert fb.is_fast_break_opportunity(3, 2, 4.0) is True
        assert fb.is_fast_break_opportunity(2, 2, 4.0) is False
        assert fb.is_fast_break_opportunity(3, 2, 2.0) is False

    def test_outcome_distribution(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb(outcome=FastBreakOutcome.SCORE))
        fb.process_fast_break(_make_fb(outcome=FastBreakOutcome.TURNOVER, points=0))
        dist = fb.get_outcome_distribution("home")
        assert dist["score"] == 50.0
        assert dist["turnover"] == 50.0

    def test_reset(self):
        fb = FastBreakAnalyzer()
        fb.process_fast_break(_make_fb())
        fb.reset()
        result = fb.get_team_analysis("home")
        assert result.total_fast_breaks == 0
        assert len(fb.get_event_history()) == 0
