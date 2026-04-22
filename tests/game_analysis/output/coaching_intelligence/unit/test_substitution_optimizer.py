# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/coaching_intelligence/substitution_optimizer.py
설명: SubstitutionOptimizer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.output.coaching_intelligence.substitution_optimizer import (
    SubstitutionOptimizer,
    SubstitutionOptimizerConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def optimizer() -> SubstitutionOptimizer:
    return SubstitutionOptimizer()


@pytest.fixture()
def small_optimizer() -> SubstitutionOptimizer:
    return SubstitutionOptimizer(SubstitutionOptimizerConfig(max_records=3))


# =============================================================================
# 초기화
# =============================================================================

class TestSubOptInit:
    def test_default_config(self, optimizer: SubstitutionOptimizer) -> None:
        assert optimizer.total_events == 0
        assert optimizer.name == "SubstitutionOptimizer"


# =============================================================================
# 선수 등록
# =============================================================================

class TestPlayerRegistration:
    def test_register(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        assert optimizer.get_player_minutes(10) == 0.0

    def test_register_duplicate(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10)
        optimizer.register_player(10)  # 중복 무시
        stats = optimizer.get_stats()
        assert stats["registered_players"] == 1


# =============================================================================
# 출전 시간 갱신
# =============================================================================

class TestPlayingTime:
    def test_update(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer.update_playing_time(10, 15.0)
        assert optimizer.get_player_minutes(10) == 15.0

    def test_update_unregistered(self, optimizer: SubstitutionOptimizer) -> None:
        # 미등록 선수는 무시
        optimizer.update_playing_time(99, 10.0)
        assert optimizer.get_player_minutes(99) == 0.0


# =============================================================================
# 교체 기록
# =============================================================================

class TestSubstitutionRecording:
    def test_record_sub(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer.register_player(20)
        optimizer.record_substitution(
            player_in=20, player_out=10,
            game_clock_sec=300.0, period=2,
        )
        assert optimizer.total_events == 1

    def test_max_limit(self, small_optimizer: SubstitutionOptimizer) -> None:
        small_optimizer.register_player(10, on_court=True)
        small_optimizer.register_player(20)
        for i in range(10):
            small_optimizer.record_substitution(
                player_in=20 if i % 2 == 0 else 10,
                player_out=10 if i % 2 == 0 else 20,
                game_clock_sec=float(600 - i * 30),
                period=1,
            )
        assert small_optimizer.total_events == 3

    def test_player_status_update(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer.register_player(20, on_court=False)
        optimizer.record_substitution(
            player_in=20, player_out=10,
            game_clock_sec=300.0, period=2,
        )
        stats = optimizer.get_stats()
        assert stats["on_court"] == 1  # 20 on, 10 off


# =============================================================================
# 피로도 알림
# =============================================================================

class TestFatigueAlerts:
    def test_no_alerts(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        alerts = optimizer.get_fatigue_alerts()
        assert len(alerts) == 0

    def test_consecutive_minutes_alert(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        # 연속 9분 → 임계 8분 초과
        optimizer._players[10].current_stint_min = 9.0
        alerts = optimizer.get_fatigue_alerts()
        assert len(alerts) == 1
        assert alerts[0]["reason"] == "consecutive_minutes"

    def test_total_minutes_alert(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer._players[10].total_minutes = 39.0
        alerts = optimizer.get_fatigue_alerts()
        assert len(alerts) == 1
        assert alerts[0]["reason"] == "total_minutes_exceeded"

    def test_bench_player_no_alert(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=False)
        optimizer._players[10].current_stint_min = 20.0
        alerts = optimizer.get_fatigue_alerts()
        assert len(alerts) == 0


# =============================================================================
# 활용도 낮은 선수
# =============================================================================

class TestUnderutilized:
    def test_no_underutilized(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer._players[10].total_minutes = 25.0
        under = optimizer.get_underutilized_players()
        assert len(under) == 0

    def test_underutilized(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(20, on_court=False)
        optimizer._players[20].total_minutes = 5.0
        under = optimizer.get_underutilized_players()
        assert len(under) == 1
        assert under[0]["player_id"] == 20


# =============================================================================
# 쿼터별 교체
# =============================================================================

class TestSubByPeriod:
    def test_period_distribution(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        optimizer.register_player(20)
        optimizer.record_substitution(20, 10, 600.0, 1)
        optimizer.record_substitution(10, 20, 500.0, 1)
        optimizer.record_substitution(20, 10, 300.0, 2)
        dist = optimizer.get_substitution_by_period()
        assert dist[1] == 2
        assert dist[2] == 1


# =============================================================================
# 유틸리티
# =============================================================================

class TestSubOptUtility:
    def test_get_stats(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10, on_court=True)
        stats = optimizer.get_stats()
        assert stats["registered_players"] == 1
        assert stats["on_court"] == 1

    def test_reset(self, optimizer: SubstitutionOptimizer) -> None:
        optimizer.register_player(10)
        optimizer.reset()
        stats = optimizer.get_stats()
        assert stats["registered_players"] == 0

    def test_repr(self, optimizer: SubstitutionOptimizer) -> None:
        assert "SubstitutionOptimizer" in repr(optimizer)
