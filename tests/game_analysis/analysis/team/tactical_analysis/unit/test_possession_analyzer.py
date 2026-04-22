# -*- coding: utf-8 -*-
"""PossessionAnalyzer 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.possession_analyzer import (
    PossessionAnalyzer,
    PossessionAnalyzerConfig,
    PossessionInput,
    PossessionType,
    PossessionOutcome,
    ClockSegment,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_poss(
    team_id: str = "home",
    poss_type: PossessionType = PossessionType.HALFCOURT_SET,
    outcome: PossessionOutcome = PossessionOutcome.SCORE,
    duration_sec: float = 12.0,
    shot_clock_sec: float = 10.0,
    points: int = 2,
    passes: int = 4,
    quarter: int = 1,
    confidence: float = 0.85,
) -> PossessionInput:
    return PossessionInput(
        team_id=team_id,
        possession_type=poss_type,
        outcome=outcome,
        duration_sec=duration_sec,
        shot_clock_at_shot_sec=shot_clock_sec,
        points_scored=points,
        passes=passes,
        quarter=quarter,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPossessionAnalyzer:
    """PossessionAnalyzer 단위 테스트."""

    def test_init_default(self):
        pa = PossessionAnalyzer()
        assert pa.name == "PossessionAnalyzer"

    def test_single_possession(self):
        pa = PossessionAnalyzer()
        ok = pa.process_possession(_make_poss(points=2))
        assert ok is True
        summary = pa.get_team_summary("home")
        assert summary["total_possessions"] == 1
        assert summary["ppp"] == 2.0

    def test_multiple_possessions_ppp(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss(points=3))
        pa.process_possession(_make_poss(points=0, outcome=PossessionOutcome.TURNOVER))
        pa.process_possession(_make_poss(points=2))
        summary = pa.get_team_summary("home")
        # PPP = 5/3 ≈ 1.667
        assert abs(summary["ppp"] - 1.667) < 0.01

    def test_type_ppp(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss(poss_type=PossessionType.TRANSITION, points=3))
        pa.process_possession(_make_poss(poss_type=PossessionType.HALFCOURT_SET, points=1))
        summary = pa.get_team_summary("home")
        assert summary["type_ppp"]["transition"] == 3.0
        assert summary["type_ppp"]["halfcourt_set"] == 1.0

    def test_clock_segment_early(self):
        pa = PossessionAnalyzer()
        assert pa.classify_clock_segment(16.0) == ClockSegment.EARLY

    def test_clock_segment_mid(self):
        pa = PossessionAnalyzer()
        assert pa.classify_clock_segment(10.0) == ClockSegment.MID

    def test_clock_segment_late(self):
        pa = PossessionAnalyzer()
        assert pa.classify_clock_segment(5.0) == ClockSegment.LATE

    def test_clock_segment_ppp(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss(shot_clock_sec=16.0, points=3))  # early
        pa.process_possession(_make_poss(shot_clock_sec=5.0, points=0, outcome=PossessionOutcome.MISSED_SHOT))   # late
        summary = pa.get_team_summary("home")
        assert summary["clock_segment_ppp"]["early"] == 3.0
        assert summary["clock_segment_ppp"]["late"] == 0.0

    def test_turnover_rate(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss(outcome=PossessionOutcome.SCORE))
        pa.process_possession(_make_poss(outcome=PossessionOutcome.TURNOVER, points=0))
        summary = pa.get_team_summary("home")
        assert summary["turnover_rate"] == 50.0

    def test_tempo_classification(self):
        pa = PossessionAnalyzer()
        assert pa.classify_tempo(10.0) == "fast"
        assert pa.classify_tempo(15.0) == "moderate"
        assert pa.classify_tempo(20.0) == "slow"

    def test_type_efficiency(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss(poss_type=PossessionType.ATO, points=3))
        eff = pa.get_type_efficiency("home", PossessionType.ATO)
        assert eff == 3.0

    def test_reject_low_confidence(self):
        pa = PossessionAnalyzer()
        ok = pa.process_possession(_make_poss(confidence=0.1))
        assert ok is False

    def test_reset(self):
        pa = PossessionAnalyzer()
        pa.process_possession(_make_poss())
        pa.reset()
        summary = pa.get_team_summary("home")
        assert summary == {}
        assert len(pa.get_event_history()) == 0
