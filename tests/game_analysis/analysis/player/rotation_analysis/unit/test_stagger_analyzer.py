# -*- coding: utf-8 -*-
"""StaggerAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.player.rotation_analysis.stagger_analyzer import (
    StaggerAnalyzer, StaggerAnalyzerConfig,
)


class TestStaggerInit:
    def test_default(self) -> None:
        a = StaggerAnalyzer()
        assert a.name == "StaggerAnalyzer"
        assert a.total_records == 0


class TestKeyPlayers:
    def test_register(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        # 등록 후 함께 출전 조회 가능
        assert a.get_together_net_rating(1) == 0.0


class TestRecordPossession:
    def test_record(self) -> None:
        a = StaggerAnalyzer()
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=2)
        assert a.total_records == 1

    def test_memory_guard(self) -> None:
        cfg = StaggerAnalyzerConfig(max_records=3)
        a = StaggerAnalyzer(config=cfg)
        for _ in range(5):
            a.record_possession(1, [10, 11], points_scored=1)
        assert a.total_records == 3


class TestTogetherVsStagger:
    def test_together(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        # 함께: 10+11 포함
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=3, points_allowed=1)
        nr = a.get_together_net_rating(1)
        # (3-1)/1*100 = 200.0
        assert nr == pytest.approx(200.0)

    def test_staggered(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        # 스태거: 10만 포함 (11 없음)
        a.record_possession(1, [10, 20, 21, 22, 23], points_scored=1, points_allowed=2)
        nr = a.get_staggered_net_rating(1)
        # (1-2)/1*100 = -100.0
        assert nr == pytest.approx(-100.0)

    def test_empty(self) -> None:
        a = StaggerAnalyzer()
        assert a.get_together_net_rating(1) == 0.0
        assert a.get_staggered_net_rating(1) == 0.0


class TestStaggerRatio:
    def test_ratio(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        # 함께 2건
        a.record_possession(1, [10, 11, 12, 13, 14])
        a.record_possession(1, [10, 11, 20, 21, 22])
        # 스태거 1건 (10만)
        a.record_possession(1, [10, 20, 21, 22, 23])
        # 없음 1건
        a.record_possession(1, [20, 21, 22, 23, 24])
        ratio = a.get_stagger_ratio(1)
        assert ratio["together_pct"] == pytest.approx(50.0)
        assert ratio["staggered_pct"] == pytest.approx(25.0)
        assert ratio["none_pct"] == pytest.approx(25.0)


class TestCompareStagger:
    def test_compare(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        a.record_possession(1, [10, 11, 12, 13, 14], points_scored=3, points_allowed=1)
        a.record_possession(1, [10, 20, 21, 22, 23], points_scored=1, points_allowed=2)
        result = a.compare_stagger(1)
        assert result["together_net"] > result["staggered_net"]
        assert result["difference"] > 0


class TestResetRepr:
    def test_reset(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        a.record_possession(1, [10, 11])
        a.reset()
        assert a.total_records == 0

    def test_repr(self) -> None:
        a = StaggerAnalyzer()
        assert "StaggerAnalyzer" in repr(a)

    def test_stats(self) -> None:
        a = StaggerAnalyzer()
        a.register_key_players(1, [10, 11])
        a.record_possession(1, [10, 11])
        stats = a.get_stats()
        assert stats["total_records"] == 1
        assert stats["teams_tracked"] == 1
