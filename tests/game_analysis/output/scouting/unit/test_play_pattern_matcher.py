# -*- coding: utf-8 -*-
"""PlayPatternMatcher 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.output.scouting.play_pattern_matcher import (
    PlayPatternMatcher, PlayPatternMatcherConfig,
)
from shared.constants.tactical_constants import SetPlayType


class TestPatternInit:
    def test_default(self) -> None:
        m = PlayPatternMatcher()
        assert m.name == "PlayPatternMatcher"
        assert m.total_observations == 0
        assert m.total_patterns == 0


class TestRecordObservation:
    def test_single(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "screen_left-roll", success=True, points=2)
        assert m.total_observations == 1
        assert m.total_patterns == 1

    def test_same_hash_aggregates(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_left", success=True, points=2)
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_left", success=False, points=0)
        assert m.total_observations == 2
        assert m.total_patterns == 1  # 같은 hash → 1 패턴

    def test_different_hash(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_left")
        m.record_observation(10, SetPlayType.FLOPPY, "floppy_right")
        assert m.total_patterns == 2

    def test_memory_guard_observations(self) -> None:
        cfg = PlayPatternMatcherConfig(max_observations=3)
        m = PlayPatternMatcher(config=cfg)
        for i in range(5):
            m.record_observation(10, SetPlayType.PICK_AND_ROLL, f"hash_{i}")
        assert m.total_observations == 3

    def test_memory_guard_patterns(self) -> None:
        cfg = PlayPatternMatcherConfig(max_patterns=2, max_observations=100)
        m = PlayPatternMatcher(config=cfg)
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "hash_a")
        m.record_observation(10, SetPlayType.FLOPPY, "hash_b")
        m.record_observation(10, SetPlayType.HORN, "hash_c")  # 한도 초과
        assert m.total_patterns == 2


class TestTopPatterns:
    def test_top(self) -> None:
        cfg = PlayPatternMatcherConfig(min_observations=2)
        m = PlayPatternMatcher(config=cfg)
        # 패턴 A: 4회 (기준 충족)
        for _ in range(4):
            m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_left", success=True, points=2)
        # 패턴 B: 3회 (기준 충족)
        for _ in range(3):
            m.record_observation(10, SetPlayType.FLOPPY, "floppy_right", success=False, points=0)
        # 패턴 C: 1회 (기준 미달)
        m.record_observation(10, SetPlayType.HORN, "horn_split")
        top = m.get_top_patterns(10, top_n=5)
        assert len(top) == 2  # C 제외
        assert top[0]["count"] == 4  # A가 1위
        assert top[0]["success_rate"] == pytest.approx(100.0)
        assert top[0]["ppp"] == pytest.approx(2.0)

    def test_empty(self) -> None:
        m = PlayPatternMatcher()
        assert m.get_top_patterns(99) == []


class TestPatternSuccessRate:
    def test_rate(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr", success=True, points=2)
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr", success=False, points=0)
        rate = m.get_pattern_success_rate(10, "pnr")
        assert rate == pytest.approx(50.0)

    def test_no_pattern(self) -> None:
        m = PlayPatternMatcher()
        assert m.get_pattern_success_rate(10, "nonexist") == 0.0


class TestPlayTypeFrequency:
    def test_freq(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_a")
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr_a")
        m.record_observation(10, SetPlayType.FLOPPY, "floppy_b")
        freq = m.get_play_type_frequency(10)
        assert freq["pick_and_roll"] == 2
        assert freq["floppy"] == 1

    def test_empty(self) -> None:
        m = PlayPatternMatcher()
        assert m.get_play_type_frequency(99) == {}


class TestResetRepr:
    def test_reset(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr")
        m.reset()
        assert m.total_observations == 0
        assert m.total_patterns == 0

    def test_repr(self) -> None:
        m = PlayPatternMatcher()
        assert "PlayPatternMatcher" in repr(m)

    def test_stats(self) -> None:
        m = PlayPatternMatcher()
        m.record_observation(10, SetPlayType.PICK_AND_ROLL, "pnr")
        m.record_observation(20, SetPlayType.FLOPPY, "floppy")
        stats = m.get_stats()
        assert stats["total_observations"] == 2
        assert stats["total_patterns"] == 2
        assert set(stats["opponents"]) == {10, 20}
