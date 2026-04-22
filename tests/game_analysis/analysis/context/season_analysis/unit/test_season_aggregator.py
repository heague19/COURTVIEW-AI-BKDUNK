# -*- coding: utf-8 -*-
"""SeasonAggregator 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.season_analysis.season_aggregator import (
    SeasonAggregator, SeasonAggregatorConfig,
)


class TestSeasonInit:
    def test_default(self) -> None:
        a = SeasonAggregator()
        assert a.name == "SeasonAggregator"
        assert a.total_games == 0


class TestRecordGame:
    def test_single(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=20, rebounds=10, assists=5, fga=15, fgm=8)
        assert a.total_games == 1

    def test_memory_guard(self) -> None:
        cfg = SeasonAggregatorConfig(max_games=2)
        a = SeasonAggregator(config=cfg)
        a.record_game("G001", 1, points=10)
        a.record_game("G002", 1, points=20)
        a.record_game("G003", 1, points=30)  # 한도 초과
        assert a.get_game_count(1) == 2


class TestSeasonTotals:
    def test_totals(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=20, rebounds=10, fga=15, fgm=8, tpa=5, tpm=3)
        a.record_game("G002", 1, points=25, rebounds=8, fga=18, fgm=10, tpa=6, tpm=2)
        totals = a.get_season_totals(1)
        assert totals["games"] == 2
        assert totals["points"] == 45
        assert totals["rebounds"] == 18
        assert totals["fga"] == 33
        assert totals["tpm"] == 5

    def test_empty(self) -> None:
        a = SeasonAggregator()
        totals = a.get_season_totals(99)
        assert totals["games"] == 0
        assert totals["points"] == 0


class TestSeasonAverages:
    def test_averages(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=20, rebounds=10, fga=20, fgm=10, minutes=30.0)
        a.record_game("G002", 1, points=30, rebounds=6, fga=20, fgm=8, minutes=34.0)
        avg = a.get_season_averages(1)
        assert avg["ppg"] == pytest.approx(25.0)
        assert avg["rpg"] == pytest.approx(8.0)
        assert avg["fg_pct"] == pytest.approx(45.0)  # 18/40
        assert avg["mpg"] == pytest.approx(32.0)

    def test_empty(self) -> None:
        a = SeasonAggregator()
        avg = a.get_season_averages(99)
        assert avg["ppg"] == 0.0

    def test_zero_fga(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=0, fga=0, fgm=0)
        avg = a.get_season_averages(1)
        assert avg["fg_pct"] == 0.0


class TestHasEnoughGames:
    def test_enough(self) -> None:
        cfg = SeasonAggregatorConfig(min_games=2)
        a = SeasonAggregator(config=cfg)
        a.record_game("G001", 1, points=10)
        assert not a.has_enough_games(1)
        a.record_game("G002", 1, points=20)
        assert a.has_enough_games(1)


class TestResetRepr:
    def test_reset(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=10)
        a.reset()
        assert a.total_games == 0

    def test_repr(self) -> None:
        a = SeasonAggregator()
        assert "SeasonAggregator" in repr(a)

    def test_stats(self) -> None:
        a = SeasonAggregator()
        a.record_game("G001", 1, points=10)
        a.record_game("G001", 2, points=15)
        stats = a.get_stats()
        assert stats["entities_tracked"] == 2
        assert stats["total_games"] == 2
