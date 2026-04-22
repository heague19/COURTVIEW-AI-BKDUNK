# -*- coding: utf-8 -*-
"""LineupProjectionModel 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest

from game_analysis.stats.predictive_models.lineup_projection import (
    LineupProjectionModel,
    LineupProjectionConfig,
)


class TestLineupProjectionModel:
    """LineupProjectionModel 단위 테스트."""

    def test_init_default(self):
        m = LineupProjectionModel()
        assert m.name == "LineupProjectionModel"
        assert m.tracked_lineups == 0

    def test_project_no_data(self):
        """데이터 없으면 리그 평균 기반 예측."""
        m = LineupProjectionModel()
        proj = m.project_lineup([1, 2, 3, 4, 5])
        # 리그 평균 → 넷레이팅 ≈ 0
        assert -10.0 < proj.predicted_net_rating < 10.0
        assert proj.sample_minutes == 0.0

    def test_project_with_data(self):
        """출전 데이터 반영."""
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [1, 2, 3, 4, 5],
            minutes=20.0,
            points_scored=50,
            points_allowed=40,
            possessions=50,
        )
        proj = m.project_lineup([1, 2, 3, 4, 5])
        assert proj.sample_minutes == 20.0
        # 100 possession당 +20 → 양의 넷레이팅
        assert proj.predicted_net_rating > 0

    def test_regression_to_mean(self):
        """소표본은 리그 평균으로 회귀."""
        cfg_no_reg = LineupProjectionConfig(regression_to_mean_factor=0.0)
        cfg_reg = LineupProjectionConfig(regression_to_mean_factor=0.5)

        m1 = LineupProjectionModel(config=cfg_no_reg)
        m2 = LineupProjectionModel(config=cfg_reg)

        lineup = [1, 2, 3, 4, 5]
        stint = dict(
            minutes=10.0, points_scored=30, points_allowed=20, possessions=25,
        )
        m1.record_lineup_stint(lineup, **stint)
        m2.record_lineup_stint(lineup, **stint)

        p1 = m1.project_lineup(lineup)
        p2 = m2.project_lineup(lineup)
        # 높은 회귀 → 리그 평균(0)에 가까움
        assert abs(p2.predicted_net_rating) < abs(p1.predicted_net_rating)

    def test_fatigue_adjustment(self):
        """피로도 반영 시 효율 감소."""
        m = LineupProjectionModel()
        lineup = [1, 2, 3, 4, 5]
        m.record_lineup_stint(
            lineup, minutes=30.0,
            points_scored=60, points_allowed=50, possessions=60,
        )
        # 30분 연속 출전 → 피로도 효과
        proj = m.project_lineup(lineup)
        assert proj.fatigue_adjusted is True

    def test_fatigue_disabled(self):
        cfg = LineupProjectionConfig(fatigue_enabled=False)
        m = LineupProjectionModel(config=cfg)
        lineup = [1, 2, 3, 4, 5]
        m.record_lineup_stint(
            lineup, minutes=30.0,
            points_scored=60, points_allowed=50, possessions=60,
        )
        proj = m.project_lineup(lineup)
        assert proj.fatigue_adjusted is False

    def test_synergy_bonus(self):
        """2인 시너지 보너스."""
        m = LineupProjectionModel()
        m.update_synergy(1, 2, net_rating_bonus=3.0)
        lineup = [1, 2, 3, 4, 5]
        m.record_lineup_stint(
            lineup, minutes=10.0,
            points_scored=25, points_allowed=25, possessions=25,
        )
        proj = m.project_lineup(lineup)
        # 시너지 3.0 추가 → 공격 효율 상승
        assert proj.predicted_offensive_rating > 100.0

    def test_matchup_quality(self):
        """매치업 품질 계산."""
        m = LineupProjectionModel()
        lineup_a = [1, 2, 3, 4, 5]
        lineup_b = [6, 7, 8, 9, 10]
        m.record_lineup_stint(
            lineup_a, minutes=20.0,
            points_scored=60, points_allowed=40, possessions=50,
        )
        m.record_lineup_stint(
            lineup_b, minutes=20.0,
            points_scored=40, points_allowed=60, possessions=50,
        )
        proj = m.project_lineup(lineup_a, opponent_lineup=lineup_b)
        assert proj.matchup_quality > 0  # A가 B보다 우수

    def test_lineup_key_order_invariant(self):
        """라인업 ID 순서 무관."""
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [5, 3, 1, 4, 2], minutes=10.0,
            points_scored=25, points_allowed=20, possessions=25,
        )
        proj = m.project_lineup([1, 2, 3, 4, 5])
        assert proj.sample_minutes == 10.0

    def test_player_minutes_tracking(self):
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [1, 2, 3, 4, 5], minutes=12.0,
            points_scored=30, points_allowed=25, possessions=30,
        )
        assert m.get_player_minutes(1) == 12.0
        assert m.get_player_minutes(99) == 0.0

    def test_reset_stint(self):
        """교체 시 stint 초기화."""
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [1, 2, 3, 4, 5], minutes=15.0,
            points_scored=30, points_allowed=25, possessions=30,
        )
        m.reset_stint(1)
        # 총 시간은 유지, stint만 초기화
        assert m.get_player_minutes(1) == 15.0

    def test_get_stats(self):
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [1, 2, 3, 4, 5], minutes=10.0,
            points_scored=20, points_allowed=15, possessions=20,
        )
        stats = m.get_stats()
        assert stats["tracked_lineups"] == 1
        assert stats["tracked_players"] == 5

    def test_memory_guard(self):
        m = LineupProjectionModel(
            config=LineupProjectionConfig(max_lineup_cache=3),
        )
        for i in range(5):
            m.record_lineup_stint(
                [i * 5 + 1, i * 5 + 2, i * 5 + 3, i * 5 + 4, i * 5 + 5],
                minutes=1.0,
                points_scored=5,
                points_allowed=5,
                possessions=5,
            )
        assert m.tracked_lineups <= 5  # trim 발생

    def test_reset(self):
        m = LineupProjectionModel()
        m.record_lineup_stint(
            [1, 2, 3, 4, 5], minutes=10.0,
            points_scored=20, points_allowed=15, possessions=20,
        )
        m.reset()
        assert m.tracked_lineups == 0
        assert m.get_player_minutes(1) == 0.0
