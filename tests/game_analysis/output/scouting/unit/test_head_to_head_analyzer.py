# -*- coding: utf-8 -*-
"""HeadToHeadAnalyzer 단위 테스트 — 11 tests."""
from __future__ import annotations

import pytest

from game_analysis.output.scouting.head_to_head_analyzer import (
    HeadToHeadAnalyzer,
    HeadToHeadConfig,
    H2HGameInput,
    H2HStrategyInput,
)


def _game(**kwargs) -> H2HGameInput:
    defaults = dict(date="2026-03-10", our_score=85, opponent_score=78)
    defaults.update(kwargs)
    return H2HGameInput(**defaults)


class TestHeadToHeadAnalyzer:
    """HeadToHeadAnalyzer 단위 테스트."""

    def test_init_default(self):
        h2h = HeadToHeadAnalyzer()
        assert h2h.name == "HeadToHeadAnalyzer"

    def test_analyze_empty(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        record = h2h.analyze()
        assert record.opponent_id == "OPP001"
        assert record.total_games == 0

    def test_single_win(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game(our_score=90, opponent_score=80))
        record = h2h.analyze()
        assert record.wins == 1
        assert record.losses == 0
        assert record.avg_point_differential == 10.0

    def test_win_loss_count(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game(our_score=90, opponent_score=80))
        h2h.add_game(_game(our_score=75, opponent_score=85))
        h2h.add_game(_game(our_score=100, opponent_score=95))
        record = h2h.analyze()
        assert record.total_games == 3
        assert record.wins == 2
        assert record.losses == 1

    def test_avg_point_differential(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game(our_score=90, opponent_score=80))   # +10
        h2h.add_game(_game(our_score=70, opponent_score=80))   # -10
        record = h2h.analyze()
        assert record.avg_point_differential == 0.0

    def test_successful_strategies(self):
        h2h = HeadToHeadAnalyzer(config=HeadToHeadConfig(
            strategy_success_ppp_threshold=1.05,
        ))
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game())
        h2h.add_strategy_result(H2HStrategyInput(strategy="pick_and_roll", ppp=1.20))
        h2h.add_strategy_result(H2HStrategyInput(strategy="pick_and_roll", ppp=1.10))
        record = h2h.analyze()
        assert "pick_and_roll" in record.successful_strategies

    def test_failed_strategies(self):
        h2h = HeadToHeadAnalyzer(config=HeadToHeadConfig(
            strategy_failure_ppp_threshold=0.85,
        ))
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game())
        h2h.add_strategy_result(H2HStrategyInput(strategy="isolation", ppp=0.70))
        h2h.add_strategy_result(H2HStrategyInput(strategy="isolation", ppp=0.80))
        record = h2h.analyze()
        assert "isolation" in record.failed_strategies

    def test_recent_results_order(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game(date="2026-01-10", our_score=80, opponent_score=90))
        h2h.add_game(_game(date="2026-03-15", our_score=95, opponent_score=85))
        h2h.add_game(_game(date="2026-02-20", our_score=88, opponent_score=82))
        record = h2h.analyze()
        assert len(record.recent_results) == 3
        assert record.recent_results[0].date == "2026-03-15"  # 최신순
        assert record.recent_results[0].outcome == "win"

    def test_recent_results_max_limit(self):
        h2h = HeadToHeadAnalyzer(config=HeadToHeadConfig(max_recent_results=2))
        h2h.set_opponent_id("OPP001")
        for i in range(5):
            h2h.add_game(_game(date=f"2026-03-{10+i:02d}"))
        record = h2h.analyze()
        assert len(record.recent_results) == 2

    def test_event_history(self):
        h2h = HeadToHeadAnalyzer()
        h2h.add_game(_game())
        h2h.add_game(_game(date="2026-03-11"))
        assert len(h2h.get_event_history()) == 2

    def test_reset(self):
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(_game())
        h2h.add_strategy_result(H2HStrategyInput(strategy="iso", ppp=1.0))
        h2h.reset()
        record = h2h.analyze()
        assert record.total_games == 0
        assert len(h2h.get_event_history()) == 0
