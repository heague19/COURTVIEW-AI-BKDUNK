# -*- coding: utf-8 -*-
"""BoxOutAnalyzer 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.defensive_analysis.box_out_analyzer import (
    BoxOutAnalyzer,
    BoxOutAnalyzerConfig,
)


class TestBoxOutAnalyzer:
    """BoxOutAnalyzer 단위 테스트."""

    def test_init_default(self):
        a = BoxOutAnalyzer()
        assert a.name == "BoxOutAnalyzer"
        assert a.total_attempts == 0
        assert a.effective_rate == 0.0

    def test_record_effective_box_out(self):
        """접촉 유효 + 유지 + 밀어냄 충분 → effective."""
        a = BoxOutAnalyzer()
        record = a.record_box_out(
            possession_id=1,
            defender_id=3,
            attacker_id=8,
            reaction_time_sec=0.4,
            hold_duration_sec=1.2,
            min_contact_distance_m=1.0,  # ≤ 1.5m
            push_distance_m=2.5,        # ≥ 2.0m
            rebound_secured=True,
        )
        assert record.effective is True
        assert a.total_attempts == 1
        assert a.effective_rate == 100.0

    def test_record_ineffective_too_far(self):
        """접촉 거리 너무 멀면 → ineffective."""
        a = BoxOutAnalyzer()
        record = a.record_box_out(
            possession_id=1,
            defender_id=3,
            attacker_id=8,
            reaction_time_sec=0.4,
            hold_duration_sec=1.2,
            min_contact_distance_m=2.5,  # > 1.5m
            push_distance_m=2.5,
            rebound_secured=False,
        )
        assert record.effective is False

    def test_record_ineffective_short_hold(self):
        """유지 시간 부족 → ineffective."""
        a = BoxOutAnalyzer()
        record = a.record_box_out(
            possession_id=1,
            defender_id=3,
            attacker_id=8,
            reaction_time_sec=0.3,
            hold_duration_sec=0.2,  # < 0.5s
            min_contact_distance_m=1.0,
            push_distance_m=2.5,
        )
        assert record.effective is False

    def test_record_ineffective_no_push(self):
        """밀어냄 거리 부족 → ineffective."""
        a = BoxOutAnalyzer()
        record = a.record_box_out(
            possession_id=1,
            defender_id=3,
            attacker_id=8,
            reaction_time_sec=0.4,
            hold_duration_sec=1.0,
            min_contact_distance_m=1.0,
            push_distance_m=1.0,  # < 2.0m
        )
        assert record.effective is False

    def test_box_out_impact(self):
        """박스아웃 有 vs 無 리바운드 확보율 비교."""
        a = BoxOutAnalyzer()
        # 박스아웃 有: 3/4 = 75%
        for i in range(4):
            a.record_box_out(
                possession_id=i,
                defender_id=3,
                attacker_id=8,
                reaction_time_sec=0.4,
                hold_duration_sec=1.0,
                min_contact_distance_m=1.0,
                push_distance_m=2.5,
                rebound_secured=(i < 3),
            )
        # 박스아웃 無: 1/4 = 25%
        for i in range(4):
            a.record_no_box_out(rebound_secured=(i < 1))
        impact = a.get_box_out_impact()
        assert impact["rebound_rate_with_boxout"] == pytest.approx(75.0, abs=0.1)
        assert impact["rebound_rate_without_boxout"] == pytest.approx(25.0, abs=0.1)
        assert impact["impact_pct"] == pytest.approx(50.0, abs=0.1)

    def test_player_box_out_rate(self):
        a = BoxOutAnalyzer()
        # defender_id=3: 2 effective / 3 total = 66.7%
        a.record_box_out(1, 3, 8, 0.4, 1.0, 1.0, 2.5, True)
        a.record_box_out(2, 3, 8, 0.4, 1.0, 1.0, 2.5, True)
        a.record_box_out(3, 3, 8, 0.4, 0.2, 2.0, 1.0, False)  # ineffective
        rate = a.get_player_box_out_rate(3)
        assert rate == pytest.approx(66.67, abs=0.5)

    def test_player_box_out_rate_unknown(self):
        a = BoxOutAnalyzer()
        assert a.get_player_box_out_rate(99) == 0.0

    def test_average_reaction_time(self):
        a = BoxOutAnalyzer()
        a.record_box_out(1, 3, 8, 0.3, 1.0, 1.0, 2.5)
        a.record_box_out(2, 5, 10, 0.5, 1.0, 1.0, 2.5)
        avg = a.get_average_reaction_time()
        assert avg == pytest.approx(0.4, abs=0.01)

    def test_effective_rate_mixed(self):
        a = BoxOutAnalyzer()
        a.record_box_out(1, 3, 8, 0.4, 1.0, 1.0, 2.5)   # effective
        a.record_box_out(2, 3, 8, 0.4, 0.2, 2.5, 1.0)    # ineffective
        assert a.effective_rate == pytest.approx(50.0, abs=0.1)

    def test_get_stats(self):
        a = BoxOutAnalyzer()
        a.record_box_out(1, 3, 8, 0.4, 1.0, 1.0, 2.5, True)
        stats = a.get_stats()
        assert stats["total_attempts"] == 1
        assert stats["total_effective"] == 1
        assert "box_out_impact" in stats
        assert stats["players_tracked"] == 1

    def test_memory_guard(self):
        a = BoxOutAnalyzer(config=BoxOutAnalyzerConfig(max_records=3))
        for i in range(5):
            a.record_box_out(i, 3, 8, 0.4, 1.0, 1.0, 2.5)
        assert a.total_attempts == 5
        stats = a.get_stats()
        assert stats["records_cached"] <= 5

    def test_reset(self):
        a = BoxOutAnalyzer()
        a.record_box_out(1, 3, 8, 0.4, 1.0, 1.0, 2.5, True)
        a.record_no_box_out(True)
        a.reset()
        assert a.total_attempts == 0
        assert a.effective_rate == 0.0
        impact = a.get_box_out_impact()
        assert impact["impact_pct"] == 0.0

    def test_repr(self):
        a = BoxOutAnalyzer()
        assert "BoxOutAnalyzer" in repr(a)
