# -*- coding: utf-8 -*-
"""DefensiveRotationAnalyzer 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.analysis.team.defensive_analysis.defensive_rotation import (
    DefensiveRotationAnalyzer,
    DefensiveRotationConfig,
)


class TestDefensiveRotationAnalyzer:
    """DefensiveRotationAnalyzer 단위 테스트."""

    def test_init_default(self):
        a = DefensiveRotationAnalyzer()
        assert a.name == "DefensiveRotationAnalyzer"
        assert a.total_rotations == 0
        assert a.rotation_success_rate == 0.0

    def test_record_successful_rotation(self):
        """빠른 로테이션 + 빈 공간 메움 → 성공."""
        a = DefensiveRotationAnalyzer()
        event = a.record_rotation(
            possession_id=1,
            defender_chain=[3, 5],
            step_times_sec=[0.8, 1.0],
            gap_distance_after=2.0,
            trigger="help",
        )
        assert event.success is True
        assert a.total_rotations == 1
        assert a.rotation_success_rate == 100.0

    def test_record_failed_rotation_slow(self):
        """느린 로테이션 → 실패."""
        a = DefensiveRotationAnalyzer()
        event = a.record_rotation(
            possession_id=1,
            defender_chain=[3, 5, 7],
            step_times_sec=[2.0, 3.0, 2.5],  # 총 7.5초
            gap_distance_after=2.0,
        )
        # 3명 체인 × 1.5초 = 4.5초 목표, 7.5초 → 실패
        assert event.success is False

    def test_record_failed_rotation_gap(self):
        """빈 공간 너무 큼 → 실패."""
        a = DefensiveRotationAnalyzer()
        event = a.record_rotation(
            possession_id=1,
            defender_chain=[3, 5],
            step_times_sec=[0.5, 0.8],
            gap_distance_after=6.0,  # > breakdown_distance 5.0
        )
        assert event.success is False

    def test_record_breakdown(self):
        a = DefensiveRotationAnalyzer()
        event = a.record_breakdown(
            possession_id=1,
            open_attacker_id=10,
            nearest_defender_distance=6.5,
            cause="missed_rotation",
        )
        assert event.cause == "missed_rotation"
        stats = a.get_stats()
        assert stats["total_breakdowns"] == 1

    def test_rotation_quality_score(self):
        """성공 로테이션 → 높은 품질 점수."""
        a = DefensiveRotationAnalyzer()
        for i in range(5):
            a.record_rotation(
                possession_id=i,
                defender_chain=[3, 5],
                step_times_sec=[0.7, 0.8],
                gap_distance_after=1.5,
            )
        quality = a.get_rotation_quality()
        assert quality > 50.0  # 전부 성공 → 높은 점수

    def test_rotation_quality_with_breakdowns(self):
        """브레이크다운 다수 → 품질 점수 하락."""
        a = DefensiveRotationAnalyzer()
        a.record_rotation(
            possession_id=1,
            defender_chain=[3, 5],
            step_times_sec=[0.7, 0.8],
            gap_distance_after=1.5,
        )
        for i in range(10):
            a.record_breakdown(
                possession_id=i + 10,
                open_attacker_id=10,
                nearest_defender_distance=6.0,
            )
        quality = a.get_rotation_quality()
        quality_no_bd = DefensiveRotationAnalyzer()
        quality_no_bd.record_rotation(1, [3, 5], [0.7, 0.8], 1.5)
        # 브레이크다운 10건 추가 → 품질 하락
        assert quality < quality_no_bd.get_rotation_quality()

    def test_average_rotation_time(self):
        a = DefensiveRotationAnalyzer()
        a.record_rotation(
            possession_id=1,
            defender_chain=[3, 5],
            step_times_sec=[1.0, 1.0],
            gap_distance_after=1.5,
        )
        a.record_rotation(
            possession_id=2,
            defender_chain=[3, 5],
            step_times_sec=[0.5, 0.5],
            gap_distance_after=1.5,
        )
        avg = a.get_average_rotation_time()
        assert avg == pytest.approx(1.5, abs=0.01)  # (2.0 + 1.0) / 2

    def test_success_rate(self):
        a = DefensiveRotationAnalyzer()
        # 2 성공, 1 실패
        a.record_rotation(1, [3, 5], [0.7, 0.8], 1.5)
        a.record_rotation(2, [3, 5], [0.7, 0.8], 1.5)
        a.record_rotation(3, [3, 5, 7], [3.0, 3.0, 3.0], 6.0)
        assert a.rotation_success_rate == pytest.approx(66.67, abs=0.5)

    def test_chain_length_limit(self):
        """체인 길이 max_chain_length로 제한."""
        a = DefensiveRotationAnalyzer(
            config=DefensiveRotationConfig(max_chain_length=2)
        )
        event = a.record_rotation(
            possession_id=1,
            defender_chain=[1, 2, 3, 4, 5],
            step_times_sec=[0.5, 0.5, 0.5, 0.5, 0.5],
            gap_distance_after=1.5,
        )
        assert len(event.defender_chain) == 2
        assert len(event.step_times_sec) == 2

    def test_get_stats(self):
        a = DefensiveRotationAnalyzer()
        a.record_rotation(1, [3, 5], [0.8, 1.0], 2.0)
        stats = a.get_stats()
        assert stats["total_rotations"] == 1
        assert "rotation_quality" in stats
        assert "average_rotation_time_sec" in stats

    def test_memory_guard(self):
        a = DefensiveRotationAnalyzer(
            config=DefensiveRotationConfig(max_records=3)
        )
        for i in range(5):
            a.record_rotation(i, [3, 5], [0.8, 1.0], 2.0)
        assert a.total_rotations == 5
        stats = a.get_stats()
        assert stats["records_cached"] <= 5

    def test_reset(self):
        a = DefensiveRotationAnalyzer()
        a.record_rotation(1, [3, 5], [0.8, 1.0], 2.0)
        a.record_breakdown(2, 10, 6.0)
        a.reset()
        assert a.total_rotations == 0
        assert a.rotation_success_rate == 0.0
        assert a.get_stats()["total_breakdowns"] == 0

    def test_repr(self):
        a = DefensiveRotationAnalyzer()
        assert "DefensiveRotationAnalyzer" in repr(a)
