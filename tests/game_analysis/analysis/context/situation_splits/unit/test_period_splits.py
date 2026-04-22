# -*- coding: utf-8 -*-
"""PeriodSplitsAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.situation_splits.period_splits import (
    PeriodSplitsAnalyzer, PeriodSplitsConfig,
)
from shared.dto.tactical_dto import SituationSplitData

class TestPeriodInit:
    def test_default(self) -> None:
        a = PeriodSplitsAnalyzer()
        assert a.name == "PeriodSplitsAnalyzer"
        assert a.total_records == 0

class TestRecordPossession:
    def test_record(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, period=1, points_scored=2, minutes=0.5)
        assert a.total_records == 1

    def test_memory_guard(self) -> None:
        cfg = PeriodSplitsConfig(max_records=3)
        a = PeriodSplitsAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, period=1)
        assert a.total_records == 3

class TestPeriodSplit:
    def test_quarter(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 1, points_scored=2, points_allowed=1,
                             shot_attempted=True, shot_made=True)
        a.record_possession(1, 1, points_scored=0, points_allowed=2,
                             shot_attempted=True, shot_made=False)
        data = a.get_period_split(1, 1)
        assert isinstance(data, SituationSplitData)
        assert data.split_name == "Q1"
        assert data.fg_pct == pytest.approx(50.0)

    def test_empty_period(self) -> None:
        a = PeriodSplitsAnalyzer()
        data = a.get_period_split(1, 3)
        assert data.offensive_rating == 0.0

class TestHalfSplits:
    def test_first_half(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 1, points_scored=3)
        a.record_possession(1, 2, points_scored=2)
        data = a.get_first_half(1)
        assert data.split_name == "first_half"
        # OR = (3+2)/2*100 = 250
        assert data.offensive_rating == pytest.approx(250.0)

    def test_second_half(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 3, points_scored=1)
        a.record_possession(1, 4, points_scored=0)
        data = a.get_second_half(1)
        assert data.split_name == "second_half"
        assert data.offensive_rating == pytest.approx(50.0)

class TestOvertime:
    def test_ot(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 5, points_scored=3)
        a.record_possession(1, 4, points_scored=1)  # Q4, OT 아님
        data = a.get_overtime(1)
        assert data.split_name == "overtime"
        assert data.offensive_rating == pytest.approx(300.0)

class TestCompareHalves:
    def test_compare(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 1, points_scored=1, points_allowed=0)
        a.record_possession(1, 3, points_scored=3, points_allowed=0)
        result = a.compare_halves(1)
        assert result["second_half_net"] > result["first_half_net"]

class TestResetRepr:
    def test_reset(self) -> None:
        a = PeriodSplitsAnalyzer()
        a.record_possession(1, 1)
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = PeriodSplitsAnalyzer()
        assert "PeriodSplitsAnalyzer" in repr(a)
