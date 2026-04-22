# -*- coding: utf-8 -*-
"""TimeoutEffectivenessAnalyzer 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.game_flow.timeout_effectiveness import (
    TimeoutEffectivenessAnalyzer, TimeoutEffectivenessConfig,
)
from shared.dto.tactical_dto import TimeoutEffectiveness

class TestTimeoutInit:
    def test_default(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        assert a.name == "TimeoutEffectivenessAnalyzer"
        assert a.total_timeouts == 0

class TestRecordTimeout:
    def test_record(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        rec = a.record_timeout(
            team_id=1, game_time_sec=300.0,
            pre_points_for=2, pre_points_against=8,
            post_points_for=10, post_points_against=4,
        )
        assert rec.team_id == 1
        assert a.total_timeouts == 1

    def test_memory_guard(self) -> None:
        cfg = TimeoutEffectivenessConfig(max_records=3)
        a = TimeoutEffectivenessAnalyzer(config=cfg)
        for i in range(5):
            a.record_timeout(team_id=1, game_time_sec=float(i * 100))
        assert a.total_timeouts == 3

class TestGetEffectiveness:
    def test_positive_change(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        a.record_timeout(
            team_id=1, game_time_sec=300.0,
            pre_points_for=2, pre_points_against=8,
            post_points_for=10, post_points_against=4,
        )
        eff = a.get_timeout_effectiveness(1)
        assert isinstance(eff, TimeoutEffectiveness)
        assert eff.pre_timeout_trend == "negative"
        assert eff.post_timeout_trend == "positive"
        assert eff.scoring_change > 0

    def test_empty(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        eff = a.get_timeout_effectiveness(99)
        assert eff.scoring_change == 0.0

class TestEffectiveRate:
    def test_rate(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        # 효과적 타임아웃 (후 > 전)
        a.record_timeout(team_id=1, game_time_sec=100.0,
                         pre_points_for=2, pre_points_against=6,
                         post_points_for=8, post_points_against=3)
        # 비효과적 타임아웃
        a.record_timeout(team_id=1, game_time_sec=200.0,
                         pre_points_for=5, pre_points_against=3,
                         post_points_for=2, post_points_against=6)
        rate = a.get_effective_rate(1)
        assert rate == pytest.approx(50.0)

    def test_empty_rate(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        assert a.get_effective_rate(99) == 0.0

class TestResetRepr:
    def test_reset(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        a.record_timeout(team_id=1, game_time_sec=100.0)
        a.reset()
        assert a.total_timeouts == 0

    def test_repr(self) -> None:
        a = TimeoutEffectivenessAnalyzer()
        assert "TimeoutEffectivenessAnalyzer" in repr(a)
