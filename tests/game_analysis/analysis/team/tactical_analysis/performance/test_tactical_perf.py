# -*- coding: utf-8 -*-
"""tactical_analysis 성능 테스트 — 9 tests.

Cadence 준수 확인:
  POSSESSION (<100ms): 전 분석기
  메모리 가드: 이벤트 히스토리 500건 제한
"""
from __future__ import annotations

import time

import pytest

from game_analysis.analysis.team.tactical_analysis.screen_analyzer import (
    ScreenAnalyzer, PnREventInput, PnRCoverageType, PnRActionType,
)
from game_analysis.analysis.team.tactical_analysis.fast_break_analyzer import (
    FastBreakAnalyzer, FastBreakEventInput, FastBreakOutcome,
)
from game_analysis.analysis.team.tactical_analysis.set_play_recognizer import (
    SetPlayRecognizer, SetPlayEventInput,
)
from game_analysis.analysis.team.tactical_analysis.passing_network import (
    PassingNetworkAnalyzer, PassEventInput,
)
from game_analysis.analysis.team.tactical_analysis.possession_analyzer import (
    PossessionAnalyzer, PossessionInput, PossessionType, PossessionOutcome,
)
from game_analysis.analysis.team.tactical_analysis.turnover_analyzer import (
    TurnoverAnalyzer, TurnoverEventInput, TurnoverCause,
)
from shared.constants.tactical_constants import SetPlayType, TurnoverCategory, TransitionPhase

_POSSESSION_BUDGET_MS = 100.0
_ITERATIONS = 500


class TestTacticalPerformance:
    """tactical_analysis 성능 테스트."""

    def test_screen_analyzer_cadence(self):
        sa = ScreenAnalyzer()
        event = PnREventInput(
            team_id="home", action_type=PnRActionType.ROLL,
            defense_coverage=PnRCoverageType.DROP, points_scored=2,
            resulted_in_shot=True, shot_made=True, confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            sa.process_pnr_event(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS, f"ScreenAnalyzer avg={avg_ms:.3f}ms > {_POSSESSION_BUDGET_MS}ms"

    def test_fast_break_analyzer_cadence(self):
        fb = FastBreakAnalyzer()
        event = FastBreakEventInput(
            team_id="home", attackers=3, defenders=2,
            transition_time_sec=4.0, phase=TransitionPhase.PRIMARY_BREAK,
            outcome=FastBreakOutcome.SCORE, points_scored=2, confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            fb.process_fast_break(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS

    def test_set_play_recognizer_cadence(self):
        spr = SetPlayRecognizer()
        event = SetPlayEventInput(
            team_id="home", play_type=SetPlayType.PICK_AND_ROLL,
            points_scored=2, resulted_in_shot=True, shot_made=True, confidence=0.80,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            spr.process_set_play(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS

    def test_passing_network_cadence(self):
        pn = PassingNetworkAnalyzer()
        event = PassEventInput(
            team_id="home", passer_id=7, receiver_id=11,
            resulted_in_assist=False, possession_id="p1", confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            pn.process_pass(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS

    def test_possession_analyzer_cadence(self):
        pa = PossessionAnalyzer()
        event = PossessionInput(
            team_id="home", possession_type=PossessionType.HALFCOURT_SET,
            outcome=PossessionOutcome.SCORE, duration_sec=14.0,
            shot_clock_at_shot_sec=10.0, points_scored=2, passes=4, confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            pa.process_possession(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS

    def test_turnover_analyzer_cadence(self):
        ta = TurnoverAnalyzer()
        event = TurnoverEventInput(
            team_id="home", player_id=7,
            category=TurnoverCategory.UNFORCED_LIVE,
            cause=TurnoverCause.BAD_PASS, confidence=0.85,
        )
        t0 = time.perf_counter()
        for _ in range(_ITERATIONS):
            ta.process_turnover(event)
        avg_ms = (time.perf_counter() - t0) / _ITERATIONS * 1000.0
        assert avg_ms < _POSSESSION_BUDGET_MS

    # === 메모리 가드 ===

    def test_screen_analyzer_memory_guard(self):
        sa = ScreenAnalyzer()
        for _ in range(600):
            sa.process_pnr_event(PnREventInput(
                team_id="home", points_scored=2, confidence=0.85,
            ))
        assert len(sa.get_event_history()) <= 500

    def test_passing_network_memory_guard(self):
        pn = PassingNetworkAnalyzer()
        for _ in range(600):
            pn.process_pass(PassEventInput(
                team_id="home", passer_id=7, receiver_id=11,
                possession_id="p1", confidence=0.85,
            ))
        assert len(pn.get_event_history()) <= 500

    def test_turnover_analyzer_memory_guard(self):
        ta = TurnoverAnalyzer()
        for _ in range(600):
            ta.process_turnover(TurnoverEventInput(
                team_id="home", player_id=7, confidence=0.85,
            ))
        assert len(ta.get_event_history()) <= 500
