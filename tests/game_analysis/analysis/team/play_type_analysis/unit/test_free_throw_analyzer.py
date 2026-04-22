# -*- coding: utf-8 -*-
"""FreeThrowAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.team.play_type_analysis.free_throw_analyzer import (
    FreeThrowAnalyzer, FreeThrowAnalyzerConfig, FreeThrowContext,
)

class TestFTInit:
    def test_default(self) -> None:
        a = FreeThrowAnalyzer()
        assert a.name == "FreeThrowAnalyzer"
        assert a.total_attempts == 0

class TestRecordFT:
    def test_record(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True, FreeThrowContext.NORMAL,
                             attempt_number=1, total_attempts=2)
        assert a.total_attempts == 1

    def test_memory_guard(self) -> None:
        cfg = FreeThrowAnalyzerConfig(max_records=3)
        a = FreeThrowAnalyzer(config=cfg)
        for _ in range(5):
            a.record_free_throw(1, 10, True)
        assert a.total_attempts == 3

class TestPlayerFTPct:
    def test_pct(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True)
        a.record_free_throw(1, 10, True)
        a.record_free_throw(1, 10, False)
        pct = a.get_player_ft_pct(10)
        assert pct == pytest.approx(66.666, abs=0.01)

    def test_empty(self) -> None:
        a = FreeThrowAnalyzer()
        assert a.get_player_ft_pct(99) == 0.0

class TestContextFTPct:
    def test_clutch(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True, FreeThrowContext.CLUTCH)
        a.record_free_throw(1, 10, False, FreeThrowContext.CLUTCH)
        a.record_free_throw(1, 10, True, FreeThrowContext.NORMAL)
        pct = a.get_player_context_ft_pct(10, FreeThrowContext.CLUTCH)
        assert pct == pytest.approx(50.0)

    def test_no_context(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True, FreeThrowContext.NORMAL)
        assert a.get_player_context_ft_pct(10, FreeThrowContext.CLUTCH) == 0.0

class TestRoutineTime:
    def test_avg(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True, routine_time_sec=3.0)
        a.record_free_throw(1, 10, True, routine_time_sec=5.0)
        avg = a.get_player_avg_routine_time(10)
        assert avg == pytest.approx(4.0)

    def test_zero_time(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True, routine_time_sec=0.0)
        assert a.get_player_avg_routine_time(10) == 0.0

class TestFirstVsLast:
    def test_comparison(self) -> None:
        a = FreeThrowAnalyzer()
        # 세트 1: 1/2 성공 → 첫번째=성공, 두번째=실패
        a.record_free_throw(1, 10, True, attempt_number=1, total_attempts=2)
        a.record_free_throw(1, 10, False, attempt_number=2, total_attempts=2)
        # 세트 2: 둘 다 성공
        a.record_free_throw(1, 10, True, attempt_number=1, total_attempts=2)
        a.record_free_throw(1, 10, True, attempt_number=2, total_attempts=2)
        result = a.get_player_first_vs_last(10)
        # 첫번째: 2/2=100%, 마지막(두번째): 1/2=50%
        assert result["first_ft_pct"] == pytest.approx(100.0)
        assert result["last_ft_pct"] == pytest.approx(50.0)

class TestTeamFT:
    def test_team_pct(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True)
        a.record_free_throw(1, 20, False)
        assert a.get_team_ft_pct(1) == pytest.approx(50.0)

    def test_team_attempts(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True)
        a.record_free_throw(1, 20, True)
        a.record_free_throw(2, 30, True)
        assert a.get_team_ft_attempts(1) == 2

class TestResetRepr:
    def test_reset(self) -> None:
        a = FreeThrowAnalyzer()
        a.record_free_throw(1, 10, True)
        a.reset()
        assert a.total_attempts == 0

    def test_repr(self) -> None:
        a = FreeThrowAnalyzer()
        assert "FreeThrowAnalyzer" in repr(a)
