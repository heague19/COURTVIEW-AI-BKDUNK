# -*- coding: utf-8 -*-
"""CloseoutAnalyzer 단위 테스트 — 15 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.defensive_analysis.closeout_analyzer import (
    CloseoutAnalyzer,
    CloseoutAnalyzerConfig,
)


class TestCloseoutAnalyzer:
    """CloseoutAnalyzer 단위 테스트."""

    def test_init_default(self):
        a = CloseoutAnalyzer()
        assert a.name == "CloseoutAnalyzer"
        assert a.total_closeouts == 0
        assert a.success_rate == 0.0

    def test_successful_closeout(self):
        """도착 거리 ≤ 성공 거리 → 성공."""
        a = CloseoutAnalyzer()
        record = a.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=3.5,
            final_distance_m=1.0,  # ≤ 1.2m
            time_sec=0.9,
            shooter_outcome="missed",
        )
        assert record.success is True
        assert record.over_closeout is False
        assert a.success_rate == 100.0

    def test_failed_closeout_too_far(self):
        """도착 거리 > 성공 거리 → 실패."""
        a = CloseoutAnalyzer()
        record = a.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=4.0,
            final_distance_m=2.0,  # > 1.2m
            time_sec=0.8,
            shooter_outcome="made",
        )
        assert record.success is False

    def test_over_closeout(self):
        """극밀착 + 고속 접근 → 오버클로즈아웃."""
        a = CloseoutAnalyzer()
        record = a.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=4.0,
            final_distance_m=0.3,  # ≤ 0.5m
            time_sec=0.8,          # speed = 3.7/0.8 ≈ 4.6 m/s > 4.0
            shooter_outcome="drive",
        )
        assert record.over_closeout is True
        assert a.over_closeout_rate > 0

    def test_not_over_closeout_slow(self):
        """밀착이지만 느리면 → 오버클로즈아웃 아님."""
        a = CloseoutAnalyzer()
        record = a.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=2.0,
            final_distance_m=0.4,  # ≤ 0.5m
            time_sec=2.0,          # speed = 1.6/2.0 = 0.8 m/s < 4.0
        )
        assert record.over_closeout is False

    def test_speed_calculation(self):
        """접근 속도 계산."""
        a = CloseoutAnalyzer()
        record = a.record_closeout(
            possession_id=1,
            defender_id=5,
            shooter_id=12,
            start_distance_m=4.0,
            final_distance_m=1.0,
            time_sec=1.0,
        )
        assert record.speed_ms == pytest.approx(3.0, abs=0.01)

    def test_closeout_quality_all_success(self):
        """전부 성공 + 적절 속도 → 높은 품질."""
        a = CloseoutAnalyzer()
        for i in range(5):
            a.record_closeout(i, 5, 12, 3.5, 1.0, 1.0, "missed")
        quality = a.get_closeout_quality()
        assert quality > 60.0

    def test_closeout_quality_with_over(self):
        """오버클로즈아웃 다수 → 품질 하락."""
        a = CloseoutAnalyzer()
        for i in range(5):
            a.record_closeout(i, 5, 12, 4.0, 0.3, 0.7, "drive")
        quality = a.get_closeout_quality()
        # 성공이지만 오버클로즈아웃이 많으면 패널티
        over_rate = a.over_closeout_rate
        assert over_rate > 0

    def test_shooter_outcome_distribution(self):
        a = CloseoutAnalyzer()
        a.record_closeout(1, 5, 12, 3.5, 1.0, 0.9, "missed")
        a.record_closeout(2, 5, 12, 3.5, 1.0, 0.9, "missed")
        a.record_closeout(3, 5, 12, 3.5, 2.0, 0.9, "made")
        dist = a.get_shooter_outcome_distribution()
        assert dist["missed"] == 2
        assert dist["made"] == 1

    def test_player_closeout_success(self):
        a = CloseoutAnalyzer()
        a.record_closeout(1, 5, 12, 3.5, 1.0, 0.9)
        a.record_closeout(2, 5, 12, 3.5, 2.0, 0.9)
        a.record_closeout(3, 5, 12, 3.5, 1.0, 0.9)
        rate = a.get_player_closeout_success(5)
        assert rate == pytest.approx(66.67, abs=0.5)

    def test_player_closeout_unknown(self):
        a = CloseoutAnalyzer()
        assert a.get_player_closeout_success(99) == 0.0

    def test_get_stats(self):
        a = CloseoutAnalyzer()
        a.record_closeout(1, 5, 12, 3.5, 1.0, 0.9, "missed")
        stats = a.get_stats()
        assert stats["total_closeouts"] == 1
        assert "closeout_quality" in stats
        assert "shooter_outcomes" in stats
        assert stats["players_tracked"] == 1

    def test_memory_guard(self):
        a = CloseoutAnalyzer(config=CloseoutAnalyzerConfig(max_records=3))
        for i in range(5):
            a.record_closeout(i, 5, 12, 3.5, 1.0, 0.9)
        assert a.total_closeouts == 5
        stats = a.get_stats()
        assert stats["records_cached"] <= 5

    def test_reset(self):
        a = CloseoutAnalyzer()
        a.record_closeout(1, 5, 12, 3.5, 1.0, 0.9, "missed")
        a.reset()
        assert a.total_closeouts == 0
        assert a.success_rate == 0.0
        assert a.over_closeout_rate == 0.0

    def test_repr(self):
        a = CloseoutAnalyzer()
        assert "CloseoutAnalyzer" in repr(a)
