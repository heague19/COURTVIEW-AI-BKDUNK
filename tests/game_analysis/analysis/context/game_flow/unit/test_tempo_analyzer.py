# -*- coding: utf-8 -*-
"""TempoAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.game_flow.tempo_analyzer import TempoAnalyzer, TempoAnalyzerConfig

class TestTempoInit:
    def test_default(self) -> None:
        a = TempoAnalyzer()
        assert a.name == "TempoAnalyzer"
        assert a.total_possessions == 0

class TestRecordPossessionTime:
    def test_record(self) -> None:
        a = TempoAnalyzer()
        a.record_possession_time(team_id=1, duration_sec=14.0)
        assert a.total_possessions == 1

    def test_memory_guard(self) -> None:
        cfg = TempoAnalyzerConfig(max_records=5)
        a = TempoAnalyzer(config=cfg)
        for i in range(8):
            a.record_possession_time(team_id=1, duration_sec=10.0 + i)
        assert a.total_possessions == 5

class TestAvgPossessionTime:
    def test_avg(self) -> None:
        a = TempoAnalyzer()
        a.record_possession_time(1, 10.0)
        a.record_possession_time(1, 20.0)
        assert a.get_avg_possession_time(1) == pytest.approx(15.0)

    def test_empty(self) -> None:
        a = TempoAnalyzer()
        assert a.get_avg_possession_time(99) == 0.0

class TestTempoCategory:
    def test_fast(self) -> None:
        cfg = TempoAnalyzerConfig(fast_threshold_sec=12.0, slow_threshold_sec=18.0)
        a = TempoAnalyzer(config=cfg)
        for _ in range(10):
            a.record_possession_time(1, 10.0)
        assert a.get_tempo_category(1) == "fast"

    def test_slow(self) -> None:
        cfg = TempoAnalyzerConfig(fast_threshold_sec=12.0, slow_threshold_sec=18.0)
        a = TempoAnalyzer(config=cfg)
        for _ in range(10):
            a.record_possession_time(1, 20.0)
        assert a.get_tempo_category(1) == "slow"

    def test_normal(self) -> None:
        a = TempoAnalyzer()
        for _ in range(10):
            a.record_possession_time(1, 15.0)
        assert a.get_tempo_category(1) == "normal"

class TestPace:
    def test_pace(self) -> None:
        a = TempoAnalyzer()
        for _ in range(48):
            a.record_possession_time(1, 14.0)
        pace = a.get_pace(1, game_minutes=24.0)
        # 48 / 24 * 48 = 96
        assert pace == pytest.approx(96.0)

    def test_pace_no_data(self) -> None:
        a = TempoAnalyzer()
        assert a.get_pace(1, game_minutes=10.0) == 0.0

class TestCompareTempo:
    def test_compare(self) -> None:
        a = TempoAnalyzer()
        for _ in range(10):
            a.record_possession_time(1, 10.0)
            a.record_possession_time(2, 20.0)
        result = a.compare_tempo(1, 2)
        assert result["difference_sec"] == pytest.approx(-10.0)

class TestResetRepr:
    def test_reset(self) -> None:
        a = TempoAnalyzer()
        a.record_possession_time(1, 14.0)
        a.reset()
        assert a.total_possessions == 0

    def test_repr(self) -> None:
        a = TempoAnalyzer()
        assert "TempoAnalyzer" in repr(a)
