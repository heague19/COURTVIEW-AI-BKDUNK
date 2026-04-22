# -*- coding: utf-8 -*-
"""ScreenAnalyzer 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.screen_analyzer import (
    ScreenAnalyzer,
    ScreenAnalyzerConfig,
    PnREventInput,
    PnRCoverageType,
    PnRActionType,
)


# =============================================================================
# 헬퍼
# =============================================================================
def _make_pnr(
    team_id: str = "home",
    action: PnRActionType = PnRActionType.ROLL,
    coverage: PnRCoverageType = PnRCoverageType.DROP,
    points: int = 2,
    shot: bool = True,
    made: bool = True,
    confidence: float = 0.85,
) -> PnREventInput:
    return PnREventInput(
        team_id=team_id,
        action_type=action,
        defense_coverage=coverage,
        points_scored=points,
        resulted_in_shot=shot,
        shot_made=made,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestScreenAnalyzer:
    """ScreenAnalyzer 단위 테스트."""

    def test_init_default(self):
        sa = ScreenAnalyzer()
        assert sa.name == "ScreenAnalyzer"

    def test_process_roll_event(self):
        sa = ScreenAnalyzer()
        ok = sa.process_pnr_event(_make_pnr(action=PnRActionType.ROLL, points=2))
        assert ok is True
        result = sa.get_team_pnr_analysis("home")
        assert result.total_pnr == 1
        assert result.pnr_ppp == 2.0

    def test_process_pop_event(self):
        sa = ScreenAnalyzer()
        sa.process_pnr_event(_make_pnr(action=PnRActionType.POP, points=3))
        result = sa.get_team_pnr_analysis("home")
        assert result.pop_efficiency == 1.0

    def test_roller_efficiency(self):
        sa = ScreenAnalyzer()
        # 2 슛 중 1 성공
        sa.process_pnr_event(_make_pnr(action=PnRActionType.ROLL, points=2, made=True))
        sa.process_pnr_event(_make_pnr(action=PnRActionType.ROLL, points=0, made=False))
        result = sa.get_team_pnr_analysis("home")
        assert result.roller_efficiency == 0.5

    def test_defense_distribution(self):
        sa = ScreenAnalyzer()
        sa.process_pnr_event(_make_pnr(coverage=PnRCoverageType.DROP))
        sa.process_pnr_event(_make_pnr(coverage=PnRCoverageType.DROP))
        sa.process_pnr_event(_make_pnr(coverage=PnRCoverageType.SWITCH))
        dist = sa.get_defense_distribution("home")
        assert dist["drop"] > 60.0
        assert dist["switch"] > 30.0

    def test_most_effective_action(self):
        sa = ScreenAnalyzer()
        # 롤: 3회 6점, 팝: 3회 9점
        for _ in range(3):
            sa.process_pnr_event(_make_pnr(action=PnRActionType.ROLL, points=2))
        for _ in range(3):
            sa.process_pnr_event(_make_pnr(action=PnRActionType.POP, points=3))
        result = sa.get_team_pnr_analysis("home")
        assert result.most_effective_action == "pop"

    def test_validate_screen_valid(self):
        sa = ScreenAnalyzer()
        assert sa.validate_screen(distance_m=0.4, angle_deg=90.0, hold_sec=0.5) is True

    def test_validate_screen_too_far(self):
        sa = ScreenAnalyzer()
        assert sa.validate_screen(distance_m=1.0, angle_deg=90.0, hold_sec=0.5) is False

    def test_validate_screen_bad_angle(self):
        sa = ScreenAnalyzer()
        assert sa.validate_screen(distance_m=0.3, angle_deg=30.0, hold_sec=0.5) is False

    def test_classify_action_roll(self):
        sa = ScreenAnalyzer()
        assert sa.classify_action(roll_speed_ms=3.0, pop_distance_m=2.0) == PnRActionType.ROLL

    def test_classify_action_pop(self):
        sa = ScreenAnalyzer()
        assert sa.classify_action(roll_speed_ms=1.0, pop_distance_m=7.0) == PnRActionType.POP

    def test_reject_low_confidence(self):
        sa = ScreenAnalyzer()
        ok = sa.process_pnr_event(_make_pnr(confidence=0.1))
        assert ok is False

    def test_reset(self):
        sa = ScreenAnalyzer()
        sa.process_pnr_event(_make_pnr())
        sa.reset()
        result = sa.get_team_pnr_analysis("home")
        assert result.total_pnr == 0
        assert len(sa.get_event_history()) == 0
