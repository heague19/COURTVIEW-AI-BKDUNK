# -*- coding: utf-8 -*-
"""RefereeTendencyAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.output.scouting.referee_tendency_analyzer import (
    RefereeTendencyAnalyzer, RefereeTendencyConfig,
)


class TestRefereeInit:
    def test_default(self) -> None:
        a = RefereeTendencyAnalyzer()
        assert a.name == "RefereeTendencyAnalyzer"
        assert a.total_calls == 0


class TestRecordFoulCall:
    def test_single(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", period=1, time_remaining_sec=600, is_home_foul=True)
        assert a.total_calls == 1

    def test_memory_guard(self) -> None:
        cfg = RefereeTendencyConfig(max_records=3)
        a = RefereeTendencyAnalyzer(config=cfg)
        for i in range(5):
            a.record_foul_call(1, "G001", "personal", 1, 600, True)
        assert a.total_calls == 3


class TestFoulsPerGame:
    def test_fpg(self) -> None:
        a = RefereeTendencyAnalyzer()
        # 심판 1, 경기 G001: 3건
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(1, "G001", "shooting", 2, 500, False)
        a.record_foul_call(1, "G001", "offensive", 3, 400, True)
        # 심판 1, 경기 G002: 1건
        a.record_foul_call(1, "G002", "personal", 1, 600, False)
        fpg = a.get_fouls_per_game(1)
        assert fpg == pytest.approx(2.0)  # 4건 / 2경기

    def test_empty(self) -> None:
        a = RefereeTendencyAnalyzer()
        assert a.get_fouls_per_game(99) == 0.0


class TestFoulTypeDistribution:
    def test_dist(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(1, "G001", "personal", 2, 500, False)
        a.record_foul_call(1, "G001", "shooting", 3, 400, True)
        dist = a.get_foul_type_distribution(1)
        assert dist["personal"] == 2
        assert dist["shooting"] == 1


class TestHomeAwayRatio:
    def test_ratio(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)   # 홈
        a.record_foul_call(1, "G001", "personal", 2, 500, True)   # 홈
        a.record_foul_call(1, "G001", "personal", 3, 400, False)  # 어웨이
        ratio = a.get_home_away_ratio(1)
        assert ratio["home_pct"] == pytest.approx(66.667, abs=0.01)
        assert ratio["away_pct"] == pytest.approx(33.333, abs=0.01)

    def test_empty(self) -> None:
        a = RefereeTendencyAnalyzer()
        ratio = a.get_home_away_ratio(99)
        assert ratio["home_pct"] == 0.0
        assert ratio["away_pct"] == 0.0


class TestLateGameTendency:
    def test_tendency(self) -> None:
        a = RefereeTendencyAnalyzer()
        # 전반: Q1, Q2
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(1, "G001", "personal", 2, 500, True)
        # 후반: Q3, Q4
        a.record_foul_call(1, "G001", "personal", 3, 400, False)
        a.record_foul_call(1, "G001", "personal", 4, 300, False)
        a.record_foul_call(1, "G001", "personal", 4, 100, True)
        result = a.get_late_game_tendency(1)
        # 1 경기: 전반 2, 후반 3
        assert result["first_half_avg"] == pytest.approx(2.0)
        assert result["second_half_avg"] == pytest.approx(3.0)

    def test_empty(self) -> None:
        a = RefereeTendencyAnalyzer()
        result = a.get_late_game_tendency(99)
        assert result["first_half_avg"] == 0.0


class TestGamesOfficiated:
    def test_games(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(1, "G001", "personal", 2, 500, True)
        a.record_foul_call(1, "G002", "personal", 1, 600, True)
        assert a.get_games_officiated(1) == 2


class TestTechnicalRate:
    def test_rate(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(1, "G001", "technical", 2, 500, True)
        rate = a.get_technical_rate(1)
        assert rate == pytest.approx(50.0)

    def test_empty(self) -> None:
        a = RefereeTendencyAnalyzer()
        assert a.get_technical_rate(99) == 0.0


class TestResetRepr:
    def test_reset(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.reset()
        assert a.total_calls == 0

    def test_repr(self) -> None:
        a = RefereeTendencyAnalyzer()
        assert "RefereeTendencyAnalyzer" in repr(a)

    def test_stats(self) -> None:
        a = RefereeTendencyAnalyzer()
        a.record_foul_call(1, "G001", "personal", 1, 600, True)
        a.record_foul_call(2, "G002", "personal", 1, 600, True)
        stats = a.get_stats()
        assert stats["total_calls"] == 2
        assert stats["referees_tracked"] == 2
