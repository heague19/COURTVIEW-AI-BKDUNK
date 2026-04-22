# -*- coding: utf-8 -*-
"""TransitionDefenseAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.transition_analysis.transition_defense import (
    TransitionDefenseAnalyzer, TransitionDefenseConfig,
)

class TestTransitionDefenseInit:
    def test_default(self) -> None:
        a = TransitionDefenseAnalyzer()
        assert a.name == "TransitionDefenseAnalyzer"
        assert a.total_recoveries == 0

class TestRecordRecovery:
    def test_recovered(self) -> None:
        a = TransitionDefenseAnalyzer()
        # 목표 4.0초 내 복귀
        ok = a.record_recovery(team_id=1, recovery_time_sec=3.5,
                                points_allowed=0)
        assert ok is True
        assert a.total_recoveries == 1

    def test_late_recovery(self) -> None:
        a = TransitionDefenseAnalyzer()
        ok = a.record_recovery(team_id=1, recovery_time_sec=5.0,
                                points_allowed=2)
        assert ok is False

    def test_memory_guard(self) -> None:
        cfg = TransitionDefenseConfig(max_records=3)
        a = TransitionDefenseAnalyzer(config=cfg)
        for _ in range(5):
            a.record_recovery(1, 3.0)
        assert a.total_recoveries == 3

class TestRecoveryRate:
    def test_rate(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0)   # recovered
        a.record_recovery(1, 3.5)   # recovered
        a.record_recovery(1, 5.0)   # late
        a.record_recovery(1, 6.0)   # late
        rate = a.get_recovery_rate(1)
        assert rate == pytest.approx(50.0)

    def test_empty(self) -> None:
        a = TransitionDefenseAnalyzer()
        assert a.get_recovery_rate(99) == 0.0

class TestAvgRecoveryTime:
    def test_avg(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0)
        a.record_recovery(1, 5.0)
        avg = a.get_avg_recovery_time(1)
        assert avg == pytest.approx(4.0)

class TestPointsAllowed:
    def test_ppp(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0, points_allowed=0)
        a.record_recovery(1, 5.0, points_allowed=2)
        ppp = a.get_points_allowed_on_transition(1)
        assert ppp == pytest.approx(1.0)

class TestOpponentFGPct:
    def test_fg(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0, shot_allowed=True, shot_made_by_opponent=True)
        a.record_recovery(1, 5.0, shot_allowed=True, shot_made_by_opponent=False)
        pct = a.get_opponent_fg_pct_on_transition(1)
        assert pct == pytest.approx(50.0)

    def test_no_shots(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0)
        assert a.get_opponent_fg_pct_on_transition(1) == 0.0

class TestLateRecoveryPenalty:
    def test_penalty(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0, points_allowed=0)
        a.record_recovery(1, 3.5, points_allowed=0)
        a.record_recovery(1, 5.0, points_allowed=3)
        a.record_recovery(1, 6.0, points_allowed=2)
        result = a.get_late_recovery_penalty(1)
        assert result["recovered_ppp"] == pytest.approx(0.0)
        assert result["late_ppp"] == pytest.approx(2.5)
        assert result["penalty"] == pytest.approx(2.5)

class TestResetRepr:
    def test_reset(self) -> None:
        a = TransitionDefenseAnalyzer()
        a.record_recovery(1, 3.0)
        a.reset()
        assert a.total_recoveries == 0

    def test_repr(self) -> None:
        a = TransitionDefenseAnalyzer()
        assert "TransitionDefenseAnalyzer" in repr(a)
