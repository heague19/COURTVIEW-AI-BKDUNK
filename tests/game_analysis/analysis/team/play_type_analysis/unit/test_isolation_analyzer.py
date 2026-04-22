# -*- coding: utf-8 -*-
"""IsolationAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.isolation_analyzer import (
    IsolationAnalyzer, IsolationConfig, IsoResult,
)

class TestIsoInit:
    def test_default(self) -> None:
        a = IsolationAnalyzer()
        assert a.name == "IsolationAnalyzer"
        assert a.total_iso == 0

class TestRecordIso:
    def test_record(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(team_id=1, player_id=10, result_type=IsoResult.SHOT,
                      shot_attempted=True, shot_made=True, points=2)
        assert a.total_iso == 1

    def test_memory_guard(self) -> None:
        cfg = IsolationConfig(max_records=3)
        a = IsolationAnalyzer(config=cfg)
        for _ in range(5):
            a.record_iso(1, 10)
        assert a.total_iso == 3

class TestPlayerPPP:
    def test_ppp(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10, points=2)
        a.record_iso(1, 10, points=3)
        assert a.get_player_ppp(10) == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = IsolationAnalyzer()
        assert a.get_player_ppp(99) == 0.0

class TestPlayerFGPct:
    def test_fg(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10, shot_attempted=True, shot_made=True)
        a.record_iso(1, 10, shot_attempted=True, shot_made=False)
        assert a.get_player_fg_pct(10) == pytest.approx(50.0)

    def test_no_attempts(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10)
        assert a.get_player_fg_pct(10) == 0.0

class TestPlayerTurnoverRate:
    def test_to_rate(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10, IsoResult.TURNOVER)
        a.record_iso(1, 10, IsoResult.SHOT)
        rate = a.get_player_turnover_rate(10)
        assert rate == pytest.approx(50.0)

class TestResultBreakdown:
    def test_breakdown(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10, IsoResult.SHOT)
        a.record_iso(1, 10, IsoResult.DRIVE)
        a.record_iso(1, 10, IsoResult.TURNOVER)
        bd = a.get_player_result_breakdown(10)
        assert bd["shot"] == 1
        assert bd["drive"] == 1
        assert bd["turnover"] == 1
        assert bd["pass_out"] == 0

class TestTeamIso:
    def test_team_ppp(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10, points=2)
        a.record_iso(1, 20, points=3)
        assert a.get_team_ppp(1) == pytest.approx(2.5)

    def test_frequency(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10)
        assert a.get_team_frequency(1, 10) == pytest.approx(10.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = IsolationAnalyzer()
        a.record_iso(1, 10)
        a.reset()
        assert a.total_iso == 0

    def test_repr(self) -> None:
        a = IsolationAnalyzer()
        assert "IsolationAnalyzer" in repr(a)
