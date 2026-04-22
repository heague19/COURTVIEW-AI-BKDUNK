# -*- coding: utf-8 -*-
"""TransitionOffenseAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.transition_analysis.transition_offense import (
    TransitionOffenseAnalyzer, TransitionOffenseConfig,
)
from shared.constants.tactical_constants import TransitionPhase

class TestTransitionOffenseInit:
    def test_default(self) -> None:
        a = TransitionOffenseAnalyzer()
        assert a.name == "TransitionOffenseAnalyzer"
        assert a.total_transitions == 0

class TestRecordTransition:
    def test_primary_break(self) -> None:
        a = TransitionOffenseAnalyzer()
        phase = a.record_transition(team_id=1, time_since_possession_sec=3.0,
                                     shot_attempted=True, shot_made=True, points=2)
        assert phase == TransitionPhase.PRIMARY_BREAK
        assert a.total_transitions == 1

    def test_secondary_break(self) -> None:
        a = TransitionOffenseAnalyzer()
        phase = a.record_transition(team_id=1, time_since_possession_sec=6.5)
        assert phase == TransitionPhase.SECONDARY_BREAK

    def test_early_offense(self) -> None:
        a = TransitionOffenseAnalyzer()
        phase = a.record_transition(team_id=1, time_since_possession_sec=10.0)
        assert phase == TransitionPhase.EARLY_OFFENSE

    def test_memory_guard(self) -> None:
        cfg = TransitionOffenseConfig(max_records=3)
        a = TransitionOffenseAnalyzer(config=cfg)
        for i in range(5):
            a.record_transition(team_id=1, time_since_possession_sec=3.0)
        assert a.total_transitions == 3

class TestPhasePPP:
    def test_ppp(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0, points=2)
        a.record_transition(1, 4.0, points=3)
        ppp = a.get_phase_ppp(1, TransitionPhase.PRIMARY_BREAK)
        assert ppp == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = TransitionOffenseAnalyzer()
        assert a.get_phase_ppp(1, TransitionPhase.PRIMARY_BREAK) == 0.0

class TestPhaseFGPct:
    def test_fg_pct(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0, shot_attempted=True, shot_made=True)
        a.record_transition(1, 4.0, shot_attempted=True, shot_made=False)
        pct = a.get_phase_fg_pct(1, TransitionPhase.PRIMARY_BREAK)
        assert pct == pytest.approx(50.0)

class TestPhaseSuccessRate:
    def test_success(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0, points=2)
        a.record_transition(1, 4.0, points=0)
        rate = a.get_phase_success_rate(1, TransitionPhase.PRIMARY_BREAK)
        assert rate == pytest.approx(50.0)

class TestTransitionPPP:
    def test_overall(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0, points=2)
        a.record_transition(1, 7.0, points=3)
        ppp = a.get_transition_ppp(1)
        assert ppp == pytest.approx(2.5)

class TestTransitionFrequency:
    def test_frequency(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0)
        a.record_transition(1, 4.0)
        freq = a.get_transition_frequency(1, total_possessions=10)
        assert freq == pytest.approx(20.0)

    def test_zero_possessions(self) -> None:
        a = TransitionOffenseAnalyzer()
        assert a.get_transition_frequency(1, 0) == 0.0

class TestPhaseBreakdown:
    def test_breakdown(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0)  # primary
        a.record_transition(1, 6.0)  # secondary
        a.record_transition(1, 10.0)  # early
        bd = a.get_phase_breakdown(1)
        assert bd["primary_break"] == 1
        assert bd["secondary_break"] == 1
        assert bd["early_offense"] == 1

class TestResetRepr:
    def test_reset(self) -> None:
        a = TransitionOffenseAnalyzer()
        a.record_transition(1, 3.0)
        a.reset()
        assert a.total_transitions == 0

    def test_repr(self) -> None:
        a = TransitionOffenseAnalyzer()
        assert "TransitionOffenseAnalyzer" in repr(a)
