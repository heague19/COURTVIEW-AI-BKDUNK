# -*- coding: utf-8 -*-
"""HelpRecoveryAnalyzer 단위 테스트 — 15 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.defensive_analysis.help_recovery import (
    HelpRecoveryAnalyzer,
    HelpRecoveryConfig,
)


class TestHelpRecoveryAnalyzer:
    """HelpRecoveryAnalyzer 단위 테스트."""

    def test_init_default(self):
        a = HelpRecoveryAnalyzer()
        assert a.name == "HelpRecoveryAnalyzer"
        assert a.total_helps == 0
        assert a.recovery_rate == 0.0
        assert a.kickout_rate == 0.0

    def test_successful_recovery(self):
        """빠른 리커버리 + 근접 복귀 → 성공."""
        a = HelpRecoveryAnalyzer()
        event = a.record_help(
            possession_id=1,
            helper_id=3,
            target_attacker_id=10,
            original_matchup_id=7,
            trigger_type="drive",
            recovery_time_sec=1.0,   # ≤ 1.5s
            recovery_distance_m=1.5,  # ≤ 2.0m
            outcome="stop",
        )
        assert event.recovered is True
        assert a.recovery_rate == 100.0

    def test_failed_recovery_slow(self):
        """리커버리 시간 초과 → 실패."""
        a = HelpRecoveryAnalyzer()
        event = a.record_help(
            possession_id=1,
            helper_id=3,
            target_attacker_id=10,
            original_matchup_id=7,
            recovery_time_sec=3.0,   # > 1.5s
            recovery_distance_m=1.5,
            outcome="kickout_open",
        )
        assert event.recovered is False

    def test_failed_recovery_far(self):
        """리커버리 거리 초과 → 실패."""
        a = HelpRecoveryAnalyzer()
        event = a.record_help(
            possession_id=1,
            helper_id=3,
            target_attacker_id=10,
            original_matchup_id=7,
            recovery_time_sec=1.0,
            recovery_distance_m=3.5,  # > 2.0m
            outcome="score",
        )
        assert event.recovered is False

    def test_kickout_tracking(self):
        """킥아웃 발생 추적."""
        a = HelpRecoveryAnalyzer()
        a.record_help(
            possession_id=1,
            helper_id=3,
            target_attacker_id=10,
            original_matchup_id=7,
            recovery_time_sec=1.0,
            recovery_distance_m=1.5,
            outcome="kickout_contested",
            kickout_occurred=True,
        )
        assert a.kickout_rate == 100.0

    def test_help_quality_all_success(self):
        """전부 성공 + 빠른 리커버리 + 킥아웃 없음 → 높은 품질."""
        a = HelpRecoveryAnalyzer()
        for i in range(5):
            a.record_help(
                possession_id=i,
                helper_id=3,
                target_attacker_id=10,
                original_matchup_id=7,
                recovery_time_sec=1.0,
                recovery_distance_m=1.5,
                outcome="stop",
            )
        quality = a.get_help_quality()
        assert quality > 70.0

    def test_help_quality_with_kickouts(self):
        """킥아웃 다수 → 품질 하락."""
        a = HelpRecoveryAnalyzer()
        for i in range(5):
            a.record_help(
                possession_id=i,
                helper_id=3,
                target_attacker_id=10,
                original_matchup_id=7,
                recovery_time_sec=2.0,
                recovery_distance_m=3.0,
                outcome="kickout_open",
                kickout_occurred=True,
            )
        quality = a.get_help_quality()
        assert quality < 40.0

    def test_outcome_distribution(self):
        a = HelpRecoveryAnalyzer()
        a.record_help(1, 3, 10, 7, outcome="stop")
        a.record_help(2, 3, 10, 7, outcome="stop")
        a.record_help(3, 3, 10, 7, outcome="score")
        dist = a.get_outcome_distribution()
        assert dist["stop"] == 2
        assert dist["score"] == 1

    def test_trigger_distribution(self):
        a = HelpRecoveryAnalyzer()
        a.record_help(1, 3, 10, 7, trigger_type="drive")
        a.record_help(2, 3, 10, 7, trigger_type="drive")
        a.record_help(3, 3, 10, 7, trigger_type="post_up")
        dist = a.get_trigger_distribution()
        assert dist["drive"] == 2
        assert dist["post_up"] == 1

    def test_player_recovery_rate(self):
        a = HelpRecoveryAnalyzer()
        # helper_id=3: 2 recovered / 3 total
        a.record_help(1, 3, 10, 7, recovery_time_sec=1.0, recovery_distance_m=1.5)
        a.record_help(2, 3, 10, 7, recovery_time_sec=1.0, recovery_distance_m=1.5)
        a.record_help(3, 3, 10, 7, recovery_time_sec=3.0, recovery_distance_m=3.0)
        rate = a.get_player_recovery_rate(3)
        assert rate == pytest.approx(66.67, abs=0.5)

    def test_player_recovery_rate_unknown(self):
        a = HelpRecoveryAnalyzer()
        assert a.get_player_recovery_rate(99) == 0.0

    def test_average_recovery_time(self):
        a = HelpRecoveryAnalyzer()
        a.record_help(1, 3, 10, 7, recovery_time_sec=1.0)
        a.record_help(2, 3, 10, 7, recovery_time_sec=2.0)
        avg = a.get_average_recovery_time()
        assert avg == pytest.approx(1.5, abs=0.01)

    def test_get_stats(self):
        a = HelpRecoveryAnalyzer()
        a.record_help(1, 3, 10, 7, recovery_time_sec=1.0, outcome="stop")
        stats = a.get_stats()
        assert stats["total_helps"] == 1
        assert "help_quality" in stats
        assert "outcome_distribution" in stats
        assert stats["players_tracked"] == 1

    def test_memory_guard(self):
        a = HelpRecoveryAnalyzer(config=HelpRecoveryConfig(max_records=3))
        for i in range(5):
            a.record_help(i, 3, 10, 7)
        assert a.total_helps == 5
        stats = a.get_stats()
        assert stats["records_cached"] <= 5

    def test_reset(self):
        a = HelpRecoveryAnalyzer()
        a.record_help(1, 3, 10, 7, kickout_occurred=True)
        a.reset()
        assert a.total_helps == 0
        assert a.recovery_rate == 0.0
        assert a.kickout_rate == 0.0
