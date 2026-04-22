# -*- coding: utf-8 -*-
"""PlayerImpactAnalyzer 단위 테스트."""

from __future__ import annotations

import pytest

from game_analysis.analysis.player.individual_analysis.player_impact import (
    PlayerImpactAnalyzer,
    PlayerImpactConfig,
)


class TestImpactInit:
    """초기화 테스트."""

    def test_default_init(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        assert analyzer.name == "PlayerImpactAnalyzer"
        assert analyzer.players_tracked == 0

    def test_custom_config(self) -> None:
        cfg = PlayerImpactConfig(min_possessions=20)
        analyzer = PlayerImpactAnalyzer(config=cfg)
        assert analyzer._config.min_possessions == 20


class TestRecordPossession:
    """점유 기록 테스트."""

    def test_on_court_accumulation(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        analyzer.record_possession(
            on_court_ids=[1, 2, 3, 4, 5],
            all_team_ids=[1, 2, 3, 4, 5, 6, 7],
            points_scored=2,
            points_allowed=0,
        )
        # players_tracked = len(_on_court) = 5 (6,7은 오프코트만)
        assert analyzer.players_tracked == 5

    def test_multiple_possessions(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        for _ in range(10):
            analyzer.record_possession(
                on_court_ids=[1, 2, 3, 4, 5],
                all_team_ids=[1, 2, 3, 4, 5, 6],
                points_scored=2,
                points_allowed=1,
            )
        # player 1은 10번 온코트
        assert analyzer._on_court[1].possessions == 10
        # player 6은 10번 오프코트
        assert analyzer._off_court[6].possessions == 10


class TestNetRating:
    """넷레이팅 계산 테스트."""

    def test_on_court_net_rating(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        # 10 possessions: 20 scored, 15 allowed → net = (20-15)/10 * 100 = 50.0
        for _ in range(10):
            analyzer.record_possession(
                on_court_ids=[1],
                all_team_ids=[1],
                points_scored=2,
                points_allowed=1 if _ < 5 else 2,
            )
        rating = analyzer.get_on_court_net_rating(1)
        # 20 scored, 15 allowed (5*1 + 5*2 = 15)
        assert rating == pytest.approx((20 - 15) / 10.0 * 100.0)

    def test_off_court_net_rating(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        for _ in range(5):
            analyzer.record_possession(
                on_court_ids=[2],
                all_team_ids=[1, 2],
                points_scored=1,
                points_allowed=3,
            )
        # player 1 오프코트: 5 scored, 15 allowed → -200.0
        rating = analyzer.get_off_court_net_rating(1)
        assert rating == pytest.approx((5 - 15) / 5.0 * 100.0)

    def test_unknown_player_returns_zero(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        assert analyzer.get_on_court_net_rating(99) == 0.0
        assert analyzer.get_off_court_net_rating(99) == 0.0


class TestImpactDifferential:
    """온-오프 차이 테스트."""

    def test_positive_impact(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        # 온코트: 좋은 성적
        for _ in range(10):
            analyzer.record_possession(
                on_court_ids=[1, 2, 3, 4, 5],
                all_team_ids=[1, 2, 3, 4, 5, 6],
                points_scored=3,
                points_allowed=1,
            )
        # 오프코트: 나쁜 성적
        for _ in range(10):
            analyzer.record_possession(
                on_court_ids=[2, 3, 4, 5, 6],
                all_team_ids=[1, 2, 3, 4, 5, 6],
                points_scored=1,
                points_allowed=3,
            )
        diff = analyzer.get_impact_differential(1)
        # on = (30-10)/10*100 = 200, off = (10-30)/10*100 = -200 → diff = 400
        assert diff == pytest.approx(400.0)


class TestGetStatsAndReset:
    """get_stats / reset / repr 테스트."""

    def test_get_stats(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        analyzer.record_possession(
            on_court_ids=[1], all_team_ids=[1], points_scored=2, points_allowed=0,
        )
        stats = analyzer.get_stats()
        assert stats["players_tracked"] == 1

    def test_reset(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        analyzer.record_possession(
            on_court_ids=[1], all_team_ids=[1], points_scored=2, points_allowed=0,
        )
        analyzer.reset()
        assert analyzer.players_tracked == 0

    def test_repr(self) -> None:
        analyzer = PlayerImpactAnalyzer()
        assert "PlayerImpactAnalyzer" in repr(analyzer)
