# -*- coding: utf-8 -*-
"""WinProbabilityModel 단위 테스트 — 16 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.predictive_models.win_probability import (
    WinProbabilityModel,
    WinProbabilityConfig,
)


class TestWinProbabilityModel:
    """WinProbabilityModel 단위 테스트."""

    def test_init_default(self):
        m = WinProbabilityModel()
        assert m.name == "WinProbabilityModel"
        assert m.current_wp == 50.0

    def test_even_score_near_50(self):
        """동점 → WP ≈ 50% (홈코트 이점 약간)."""
        m = WinProbabilityModel()
        wp = m.update_score(50, 50, quarter=2, game_clock_sec=300.0)
        assert 48.0 <= wp.home_wp <= 58.0

    def test_home_lead_increases_wp(self):
        """홈팀 리드 → WP > 50%."""
        m = WinProbabilityModel()
        wp = m.update_score(60, 50, quarter=3, game_clock_sec=300.0)
        assert wp.home_wp > 55.0

    def test_away_lead_decreases_wp(self):
        """원정팀 리드 → WP < 50%."""
        m = WinProbabilityModel()
        wp = m.update_score(40, 55, quarter=3, game_clock_sec=300.0)
        assert wp.home_wp < 45.0

    def test_large_lead_high_wp(self):
        """대량 리드 → WP 높음."""
        m = WinProbabilityModel()
        wp = m.update_score(80, 50, quarter=4, game_clock_sec=60.0)
        assert wp.home_wp > 90.0

    def test_time_sensitivity(self):
        """잔여시간 적을수록 점수차 영향 커짐."""
        m = WinProbabilityModel()
        wp_early = m.update_score(55, 50, quarter=1, game_clock_sec=500.0)
        wp_late = m.update_score(55, 50, quarter=4, game_clock_sec=30.0)
        # 같은 5점차, 4쿼터 30초 남은 게 WP 더 높음
        assert wp_late.home_wp > wp_early.home_wp

    def test_wpa_calculation(self):
        """WPA = 현재 WP - 이전 WP."""
        m = WinProbabilityModel()
        m.update_score(50, 50, quarter=3, game_clock_sec=300.0)
        wp2 = m.update_score(53, 50, quarter=3, game_clock_sec=280.0)
        assert wp2.last_play_wpa > 0  # 홈 3점 득점 → WPA 양수

    def test_wp_curve_accumulation(self):
        """WP 곡선 포인트 누적."""
        m = WinProbabilityModel()
        for i in range(5):
            m.update_score(50 + i, 50, quarter=2, game_clock_sec=500.0 - i * 30)
        wp = m.get_wp_snapshot()
        assert len(wp.wp_curve) == 5

    def test_clutch_time_detection(self):
        """클러치 = 4Q + 5분 이내 + 5점차 이내."""
        m = WinProbabilityModel()
        m.update_score(70, 68, quarter=4, game_clock_sec=120.0)
        assert m.is_clutch_time() is True

    def test_not_clutch_early_quarter(self):
        """1쿼터는 클러치 아님."""
        m = WinProbabilityModel()
        m.update_score(20, 18, quarter=1, game_clock_sec=60.0)
        assert m.is_clutch_time() is False

    def test_garbage_time_detection(self):
        """가비지 = 25점차 이상 + 5분 이상 남음."""
        m = WinProbabilityModel()
        m.update_score(80, 50, quarter=3, game_clock_sec=500.0)
        assert m.is_garbage_time() is True

    def test_possession_update(self):
        """점유권 변경으로 WP 미세 변동."""
        m = WinProbabilityModel()
        wp1 = m.update_score(
            60, 58, quarter=4, game_clock_sec=120.0,
            home_has_possession=True,
        )
        wp2 = m.update_possession(
            home_has_possession=False,
            quarter=4,
            game_clock_sec=115.0,
        )
        # 점유권 잃으면 WP 미세 하락
        assert wp2.home_wp <= wp1.home_wp

    def test_leverage_index(self):
        """접전 종반 → 높은 레버리지."""
        m = WinProbabilityModel()
        wp = m.update_score(70, 69, quarter=4, game_clock_sec=30.0)
        assert wp.leverage_index > 0.5

    def test_get_stats(self):
        m = WinProbabilityModel()
        m.update_score(50, 48, quarter=2, game_clock_sec=300.0)
        stats = m.get_stats()
        assert "current_wp" in stats
        assert stats["home_score"] == 50
        assert stats["away_score"] == 48

    def test_reset(self):
        m = WinProbabilityModel()
        m.update_score(60, 55, quarter=3, game_clock_sec=200.0)
        m.reset()
        assert m.current_wp == 50.0
        stats = m.get_stats()
        assert stats["curve_points"] == 0

    def test_game_clock_format(self):
        """게임 클락 MM:SS 포맷."""
        m = WinProbabilityModel()
        wp = m.update_score(50, 50, quarter=1, game_clock_sec=125.0)
        assert wp.game_clock == "02:05"
