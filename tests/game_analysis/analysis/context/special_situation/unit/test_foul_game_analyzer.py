# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/special_situation/foul_game_analyzer.py
설명: FoulGameAnalyzer 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.analysis.context.special_situation.foul_game_analyzer import (
    FoulGameAnalyzer,
    FoulGameAnalyzerConfig,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def analyzer() -> FoulGameAnalyzer:
    return FoulGameAnalyzer()


@pytest.fixture()
def small_analyzer() -> FoulGameAnalyzer:
    return FoulGameAnalyzer(FoulGameAnalyzerConfig(max_records=5))


# =============================================================================
# 초기화
# =============================================================================

class TestFoulGameInit:
    def test_default_config(self, analyzer: FoulGameAnalyzer) -> None:
        assert analyzer.total_records == 0
        assert analyzer.name == "FoulGameAnalyzer"

    def test_custom_config(self) -> None:
        cfg = FoulGameAnalyzerConfig(
            max_records=100, foul_game_margin=8, foul_game_time_sec=90,
        )
        a = FoulGameAnalyzer(cfg)
        assert a.total_records == 0


# =============================================================================
# 기록
# =============================================================================

class TestFoulGameRecording:
    def test_record_single(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            team_id=1,
            score_margin=-4,
            time_remaining_sec=60,
            period=4,
            is_fouling_team=True,
            points_scored=3,
            free_throws_given=2,
            free_throws_made_by_opponent=1,
        )
        assert analyzer.total_records == 1

    def test_max_records_limit(self, small_analyzer: FoulGameAnalyzer) -> None:
        for _ in range(10):
            small_analyzer.record_foul_game_possession(
                team_id=1, score_margin=-3, time_remaining_sec=60, period=4,
            )
        assert small_analyzer.total_records == 5


# =============================================================================
# 파울 게임 상황 판별
# =============================================================================

class TestIsFoulGameSituation:
    def test_typical_foul_game(self, analyzer: FoulGameAnalyzer) -> None:
        # 4쿼터, 5점차, 90초 남음
        assert analyzer.is_foul_game_situation(5, 90, 4) is True

    def test_too_early(self, analyzer: FoulGameAnalyzer) -> None:
        # 3쿼터는 파울 게임 아님
        assert analyzer.is_foul_game_situation(3, 60, 3) is False

    def test_too_large_margin(self, analyzer: FoulGameAnalyzer) -> None:
        # 10점차는 파울 게임 아님 (기본 임계 6)
        assert analyzer.is_foul_game_situation(10, 60, 4) is False

    def test_too_much_time(self, analyzer: FoulGameAnalyzer) -> None:
        # 5분 남음은 파울 게임 아님 (기본 임계 120초)
        assert analyzer.is_foul_game_situation(3, 300, 4) is False

    def test_exact_boundary(self, analyzer: FoulGameAnalyzer) -> None:
        # 경계값: 6점차, 120초, 4쿼터
        assert analyzer.is_foul_game_situation(6, 120, 4) is True

    def test_overtime(self, analyzer: FoulGameAnalyzer) -> None:
        # 연장전 (5쿼터)
        assert analyzer.is_foul_game_situation(3, 60, 5) is True

    def test_negative_margin(self, analyzer: FoulGameAnalyzer) -> None:
        # 음수 점수차 (abs 적용됨)
        assert analyzer.is_foul_game_situation(-5, 60, 4) is True

    def test_custom_config_margin(self) -> None:
        cfg = FoulGameAnalyzerConfig(foul_game_margin=10, foul_game_time_sec=180)
        a = FoulGameAnalyzer(cfg)
        assert a.is_foul_game_situation(8, 150, 4) is True


# =============================================================================
# 순득점
# =============================================================================

class TestFoulGameNetPoints:
    def test_net_points_no_data(self, analyzer: FoulGameAnalyzer) -> None:
        assert analyzer.get_foul_game_net_points(1) == 0

    def test_net_points_positive(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4, points_scored=3, points_allowed=2,
        )
        assert analyzer.get_foul_game_net_points(1) == 1

    def test_net_points_negative(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4, points_scored=0, points_allowed=2,
        )
        assert analyzer.get_foul_game_net_points(1) == -2

    def test_net_points_cumulative(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4, points_scored=3, points_allowed=2,
        )
        analyzer.record_foul_game_possession(
            1, -3, 45, 4, points_scored=0, points_allowed=2,
        )
        # (3-2) + (0-2) = 1 + (-2) = -1
        assert analyzer.get_foul_game_net_points(1) == -1

    def test_net_points_team_isolation(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4, points_scored=3, points_allowed=0,
        )
        analyzer.record_foul_game_possession(
            2, 4, 60, 4, points_scored=0, points_allowed=3,
        )
        assert analyzer.get_foul_game_net_points(1) == 3
        assert analyzer.get_foul_game_net_points(2) == -3


# =============================================================================
# 상대 자유투 성공률
# =============================================================================

class TestOpponentFTPct:
    def test_no_data(self, analyzer: FoulGameAnalyzer) -> None:
        assert analyzer.get_opponent_ft_pct_in_foul_game(1) == 0.0

    def test_no_free_throws(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4, is_fouling_team=True,
        )
        assert analyzer.get_opponent_ft_pct_in_foul_game(1) == 0.0

    def test_all_made(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            free_throws_given=2,
            free_throws_made_by_opponent=2,
        )
        assert analyzer.get_opponent_ft_pct_in_foul_game(1) == pytest.approx(100.0)

    def test_partial_made(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            free_throws_given=4,
            free_throws_made_by_opponent=3,
        )
        assert analyzer.get_opponent_ft_pct_in_foul_game(1) == pytest.approx(75.0)

    def test_only_fouling_team_counted(self, analyzer: FoulGameAnalyzer) -> None:
        # is_fouling_team=False인 기록은 집계 안 됨
        analyzer.record_foul_game_possession(
            1, 4, 60, 4,
            is_fouling_team=False,
            free_throws_given=2,
            free_throws_made_by_opponent=2,
        )
        assert analyzer.get_opponent_ft_pct_in_foul_game(1) == 0.0


# =============================================================================
# 파울 게임 성공률
# =============================================================================

class TestFoulGameSuccessRate:
    def test_no_data(self, analyzer: FoulGameAnalyzer) -> None:
        assert analyzer.get_foul_game_success_rate(1) == 0.0

    def test_all_narrowed(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            points_scored=3,
            points_allowed=2,
        )
        assert analyzer.get_foul_game_success_rate(1) == pytest.approx(100.0)

    def test_none_narrowed(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            points_scored=0,
            points_allowed=2,
        )
        assert analyzer.get_foul_game_success_rate(1) == pytest.approx(0.0)

    def test_mixed(self, analyzer: FoulGameAnalyzer) -> None:
        # 2건 중 1건 점수차 줄임
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            points_scored=3, points_allowed=2,
        )
        analyzer.record_foul_game_possession(
            1, -3, 45, 4,
            is_fouling_team=True,
            points_scored=0, points_allowed=2,
        )
        assert analyzer.get_foul_game_success_rate(1) == pytest.approx(50.0)


# =============================================================================
# 종합 요약
# =============================================================================

class TestFoulGameSummary:
    def test_summary_empty(self, analyzer: FoulGameAnalyzer) -> None:
        s = analyzer.get_foul_game_summary(1)
        assert s["total_possessions"] == 0
        assert s["net_points"] == 0
        assert s["opponent_ft_pct"] == 0.0
        assert s["success_rate"] == 0.0

    def test_summary_with_data(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(
            1, -4, 60, 4,
            is_fouling_team=True,
            points_scored=3,
            points_allowed=2,
            free_throws_given=2,
            free_throws_made_by_opponent=2,
        )
        s = analyzer.get_foul_game_summary(1)
        assert s["total_possessions"] == 1
        assert s["net_points"] == 1
        assert s["opponent_ft_pct"] == pytest.approx(100.0)
        assert s["success_rate"] == pytest.approx(100.0)


# =============================================================================
# 유틸리티
# =============================================================================

class TestFoulGameUtility:
    def test_get_stats(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(1, -4, 60, 4)
        stats = analyzer.get_stats()
        assert stats["total_records"] == 1

    def test_reset(self, analyzer: FoulGameAnalyzer) -> None:
        analyzer.record_foul_game_possession(1, -4, 60, 4)
        analyzer.reset()
        assert analyzer.total_records == 0

    def test_repr(self, analyzer: FoulGameAnalyzer) -> None:
        assert "FoulGameAnalyzer" in repr(analyzer)
        assert "records=0" in repr(analyzer)
