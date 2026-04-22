# -*- coding: utf-8 -*-
"""TurnoverAnalyzer 단위 테스트 — 13 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.tactical_analysis.turnover_analyzer import (
    TurnoverAnalyzer,
    TurnoverAnalyzerConfig,
    TurnoverEventInput,
    TurnoverCause,
)
from shared.constants.tactical_constants import TurnoverCategory


# =============================================================================
# 헬퍼
# =============================================================================
def _make_tov(
    team_id: str = "home",
    player_id: int = 7,
    category: TurnoverCategory = TurnoverCategory.UNFORCED_LIVE,
    cause: TurnoverCause = TurnoverCause.BAD_PASS,
    pot: int = 0,
    fast_break: bool = False,
    quarter: int = 1,
    confidence: float = 0.85,
) -> TurnoverEventInput:
    return TurnoverEventInput(
        team_id=team_id,
        player_id=player_id,
        category=category,
        cause=cause,
        points_off_turnover=pot,
        resulted_in_fast_break=fast_break,
        quarter=quarter,
        confidence=confidence,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestTurnoverAnalyzer:
    """TurnoverAnalyzer 단위 테스트."""

    def test_init_default(self):
        ta = TurnoverAnalyzer()
        assert ta.name == "TurnoverAnalyzer"

    def test_single_turnover(self):
        ta = TurnoverAnalyzer()
        ok = ta.process_turnover(_make_tov())
        assert ok is True
        summary = ta.get_team_summary("home")
        assert summary["total_turnovers"] == 1

    def test_four_categories(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(category=TurnoverCategory.FORCED_LIVE))
        ta.process_turnover(_make_tov(category=TurnoverCategory.FORCED_DEAD))
        ta.process_turnover(_make_tov(category=TurnoverCategory.UNFORCED_LIVE))
        ta.process_turnover(_make_tov(category=TurnoverCategory.UNFORCED_DEAD))
        summary = ta.get_team_summary("home")
        assert summary["forced"] == 2
        assert summary["unforced"] == 2
        assert summary["live_ball"] == 2

    def test_forced_percentage(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(category=TurnoverCategory.FORCED_LIVE))
        ta.process_turnover(_make_tov(category=TurnoverCategory.UNFORCED_LIVE))
        summary = ta.get_team_summary("home")
        assert summary["forced_pct"] == 50.0

    def test_points_off_turnovers(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(pot=2))
        ta.process_turnover(_make_tov(pot=3))
        summary = ta.get_team_summary("home")
        assert summary["points_off_turnovers"] == 5

    def test_fast_break_after(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(fast_break=True))
        ta.process_turnover(_make_tov(fast_break=False))
        summary = ta.get_team_summary("home")
        assert summary["fast_break_after"] == 1
        assert summary["fast_break_after_pct"] == 50.0

    def test_cause_distribution(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(cause=TurnoverCause.BAD_PASS))
        ta.process_turnover(_make_tov(cause=TurnoverCause.BAD_PASS))
        ta.process_turnover(_make_tov(cause=TurnoverCause.TRAVEL))
        summary = ta.get_team_summary("home")
        causes = summary["cause_distribution"]
        assert causes[0]["cause"] == "bad_pass"
        assert causes[0]["count"] == 2

    def test_quarter_counts(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(quarter=1))
        ta.process_turnover(_make_tov(quarter=1))
        ta.process_turnover(_make_tov(quarter=3))
        summary = ta.get_team_summary("home")
        assert summary["quarter_counts"][1] == 2
        assert summary["quarter_counts"][3] == 1

    def test_player_turnovers(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov(player_id=7, category=TurnoverCategory.FORCED_LIVE))
        ta.process_turnover(_make_tov(player_id=7, category=TurnoverCategory.UNFORCED_LIVE))
        player = ta.get_player_turnovers("home", 7)
        assert player["total"] == 2
        assert player["forced"] == 1
        assert player["unforced"] == 1

    def test_worst_turnover_players(self):
        ta = TurnoverAnalyzer()
        for _ in range(5):
            ta.process_turnover(_make_tov(player_id=7))
        for _ in range(3):
            ta.process_turnover(_make_tov(player_id=11))
        worst = ta.get_worst_turnover_players("home", n=2)
        assert len(worst) == 2
        assert worst[0]["player_id"] == 7
        assert worst[0]["turnovers"] == 5

    def test_reject_low_confidence(self):
        ta = TurnoverAnalyzer()
        ok = ta.process_turnover(_make_tov(confidence=0.1))
        assert ok is False

    def test_empty_team(self):
        ta = TurnoverAnalyzer()
        summary = ta.get_team_summary("away")
        assert summary == {}

    def test_reset(self):
        ta = TurnoverAnalyzer()
        ta.process_turnover(_make_tov())
        ta.reset()
        summary = ta.get_team_summary("home")
        assert summary == {}
        assert len(ta.get_event_history()) == 0
