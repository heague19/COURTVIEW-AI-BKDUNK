# -*- coding: utf-8 -*-
"""ShotClockSplitsAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.situation_splits.shot_clock_splits import (
    ShotClockSplitsAnalyzer, ShotClockSplitsConfig, ShotClockSegment,
)

class TestShotClockInit:
    def test_default(self) -> None:
        a = ShotClockSplitsAnalyzer()
        assert a.name == "ShotClockSplitsAnalyzer"
        assert a.total_records == 0

class TestRecordPossession:
    def test_early(self) -> None:
        a = ShotClockSplitsAnalyzer()
        seg = a.record_possession(1, 20.0, points=3)
        assert seg == ShotClockSegment.EARLY

    def test_mid(self) -> None:
        a = ShotClockSplitsAnalyzer()
        seg = a.record_possession(1, 12.0)
        assert seg == ShotClockSegment.MID

    def test_late(self) -> None:
        a = ShotClockSplitsAnalyzer()
        seg = a.record_possession(1, 3.0)
        assert seg == ShotClockSegment.LATE

    def test_memory_guard(self) -> None:
        cfg = ShotClockSplitsConfig(max_records=3)
        a = ShotClockSplitsAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, 10.0)
        assert a.total_records == 3

class TestSegmentSplit:
    def test_split(self) -> None:
        a = ShotClockSplitsAnalyzer()
        a.record_possession(1, 20.0, points=3, shot_attempted=True, shot_made=True)
        a.record_possession(1, 19.0, points=0, shot_attempted=True, shot_made=False)
        data = a.get_segment_split(1, ShotClockSegment.EARLY)
        assert data.split_name == "early_clock"
        assert data.fg_pct == pytest.approx(50.0)

class TestSegmentPPP:
    def test_ppp(self) -> None:
        a = ShotClockSplitsAnalyzer()
        a.record_possession(1, 20.0, points=3)
        a.record_possession(1, 19.0, points=2)
        ppp = a.get_segment_ppp(1, ShotClockSegment.EARLY)
        assert ppp == pytest.approx(2.5)

    def test_empty(self) -> None:
        a = ShotClockSplitsAnalyzer()
        assert a.get_segment_ppp(1, ShotClockSegment.LATE) == 0.0

class TestDistribution:
    def test_dist(self) -> None:
        a = ShotClockSplitsAnalyzer()
        a.record_possession(1, 20.0)  # early
        a.record_possession(1, 10.0)  # mid
        a.record_possession(1, 3.0)   # late
        a.record_possession(1, 5.0)   # late
        dist = a.get_segment_distribution(1)
        assert dist["early_clock"] == 1
        assert dist["mid_clock"] == 1
        assert dist["late_clock"] == 2

class TestCompareSegments:
    def test_compare(self) -> None:
        a = ShotClockSplitsAnalyzer()
        a.record_possession(1, 20.0, points=3)
        a.record_possession(1, 10.0, points=1)
        a.record_possession(1, 3.0, points=0)
        result = a.compare_segments(1)
        assert result["early_clock"] > result["late_clock"]

class TestResetRepr:
    def test_reset(self) -> None:
        a = ShotClockSplitsAnalyzer()
        a.record_possession(1, 10.0)
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = ShotClockSplitsAnalyzer()
        assert "ShotClockSplitsAnalyzer" in repr(a)
