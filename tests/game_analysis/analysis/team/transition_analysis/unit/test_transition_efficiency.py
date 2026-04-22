# -*- coding: utf-8 -*-
"""TransitionEfficiencyAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.transition_analysis.transition_efficiency import (
    TransitionEfficiencyAnalyzer, TransitionEfficiencyConfig,
)
from shared.dto.tactical_dto import TransitionData

class TestEfficiencyInit:
    def test_default(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        assert a.name == "TransitionEfficiencyAnalyzer"
        assert a.total_possessions == 0

class TestRecordPossession:
    def test_accumulates(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, points=2)
        a.record_possession(1, False, points=1)
        assert a.total_possessions == 2

    def test_memory_guard(self) -> None:
        cfg = TransitionEfficiencyConfig(max_records=3)
        a = TransitionEfficiencyAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, True)
        assert a.total_possessions == 3

class TestTransitionPPP:
    def test_ppp(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, points=3)
        a.record_possession(1, True, points=2)
        ppp = a.get_transition_ppp(1)
        assert ppp == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        assert a.get_transition_ppp(99) == 0.0

class TestHalfcourtPPP:
    def test_ppp(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, False, points=1)
        a.record_possession(1, False, points=2)
        ppp = a.get_halfcourt_ppp(1)
        assert ppp == pytest.approx(1.5)

class TestFrequency:
    def test_frequency(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True)
        a.record_possession(1, True)
        a.record_possession(1, False)
        a.record_possession(1, False)
        a.record_possession(1, False)
        freq = a.get_transition_frequency(1)
        assert freq == pytest.approx(40.0)

class TestFGPct:
    def test_transition_fg(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, shot_attempted=True, shot_made=True)
        a.record_possession(1, True, shot_attempted=True, shot_made=False)
        pct = a.get_fg_pct(1, True)
        assert pct == pytest.approx(50.0)

class TestTurnoverRate:
    def test_rate(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, turnover=True)
        a.record_possession(1, True, turnover=False)
        rate = a.get_turnover_rate(1, True)
        assert rate == pytest.approx(50.0)

class TestTransitionData:
    def test_dto(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, points=3)
        a.record_possession(1, False, points=1)
        data = a.get_transition_data(1, first_wave_success_rate=60.0,
                                      defensive_recovery_rate=80.0)
        assert isinstance(data, TransitionData)
        assert data.transition_ppp == pytest.approx(3.0)
        assert data.halfcourt_ppp == pytest.approx(1.0)
        assert data.first_wave_success_rate == pytest.approx(60.0)

class TestCompareEfficiency:
    def test_compare(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True, points=3)
        a.record_possession(1, False, points=1)
        result = a.compare_efficiency(1)
        assert result["ppp_difference"] == pytest.approx(2.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        a.record_possession(1, True)
        a.reset()
        assert a.total_possessions == 0

    def test_repr(self) -> None:
        a = TransitionEfficiencyAnalyzer()
        assert "TransitionEfficiencyAnalyzer" in repr(a)
