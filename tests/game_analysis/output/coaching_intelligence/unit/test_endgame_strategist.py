# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/coaching_intelligence/endgame_strategist.py
설명: EndgameStrategist 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.output.coaching_intelligence.endgame_strategist import (
    EndgameAction,
    EndgameStrategist,
    EndgameStrategistConfig,
    GameSituation,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def strategist() -> EndgameStrategist:
    return EndgameStrategist()


@pytest.fixture()
def small_strategist() -> EndgameStrategist:
    return EndgameStrategist(EndgameStrategistConfig(max_strategies=5))


# =============================================================================
# Enum
# =============================================================================

class TestEnums:
    def test_endgame_action(self) -> None:
        assert len(EndgameAction) == 6
        assert EndgameAction.INTENTIONAL_FOUL.value == "intentional_foul"
        assert EndgameAction.TWO_FOR_ONE.value == "two_for_one"

    def test_game_situation(self) -> None:
        assert len(GameSituation) == 3
        assert GameSituation.LEADING.value == "leading"


# =============================================================================
# 초기화
# =============================================================================

class TestStrategistInit:
    def test_default(self, strategist: EndgameStrategist) -> None:
        assert strategist.total_strategies == 0
        assert strategist.name == "EndgameStrategist"


# =============================================================================
# 상황 분류
# =============================================================================

class TestClassifySituation:
    def test_leading(self) -> None:
        assert EndgameStrategist.classify_situation(5) == GameSituation.LEADING

    def test_trailing(self) -> None:
        assert EndgameStrategist.classify_situation(-5) == GameSituation.TRAILING

    def test_tied(self) -> None:
        assert EndgameStrategist.classify_situation(0) == GameSituation.TIED


# =============================================================================
# 전략 추천
# =============================================================================

class TestRecommendStrategy:
    def test_no_recommendation_before_4q(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=-3, time_remaining_sec=60, period=3,
        )
        assert recs == []

    def test_foul_strategy_trailing(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=-4, time_remaining_sec=90, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.INTENTIONAL_FOUL.value in actions

    def test_no_foul_strategy_leading(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=4, time_remaining_sec=90, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.INTENTIONAL_FOUL.value not in actions

    def test_timeout_on_scoring_run(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=-5, time_remaining_sec=180, period=4,
            timeouts_remaining=2, opponent_scoring_run=10,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.CALL_TIMEOUT.value in actions

    def test_last_possession_trailing(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=-2, time_remaining_sec=20, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.RUN_PLAY.value in actions

    def test_last_possession_leading(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=3, time_remaining_sec=15, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.HOLD_BALL.value in actions

    def test_two_for_one(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=0, time_remaining_sec=38, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.TWO_FOR_ONE.value in actions

    def test_press_defense(self, strategist: EndgameStrategist) -> None:
        recs = strategist.recommend_strategy(
            score_margin=-8, time_remaining_sec=150, period=4,
        )
        actions = [r["action"] for r in recs]
        assert EndgameAction.PRESS_DEFENSE.value in actions

    def test_max_3_recommendations(self, strategist: EndgameStrategist) -> None:
        # 여러 조건 동시 충족 → 최대 3개
        recs = strategist.recommend_strategy(
            score_margin=-5, time_remaining_sec=40, period=4,
            timeouts_remaining=2, opponent_scoring_run=10,
        )
        assert len(recs) <= 3

    def test_strategies_recorded(self, strategist: EndgameStrategist) -> None:
        strategist.recommend_strategy(
            score_margin=-4, time_remaining_sec=90, period=4,
        )
        assert strategist.total_strategies > 0


# =============================================================================
# 파울 전략 판별
# =============================================================================

class TestShouldFoul:
    def test_should_foul(self, strategist: EndgameStrategist) -> None:
        assert strategist.should_foul(-4, 90, 4) is True

    def test_should_not_foul_leading(self, strategist: EndgameStrategist) -> None:
        assert strategist.should_foul(4, 90, 4) is False

    def test_should_not_foul_large_margin(self, strategist: EndgameStrategist) -> None:
        assert strategist.should_foul(-10, 90, 4) is False

    def test_should_not_foul_early(self, strategist: EndgameStrategist) -> None:
        assert strategist.should_foul(-4, 90, 3) is False

    def test_should_not_foul_too_much_time(self, strategist: EndgameStrategist) -> None:
        assert strategist.should_foul(-4, 300, 4) is False


# =============================================================================
# 전략 분포
# =============================================================================

class TestStrategyDistribution:
    def test_empty(self, strategist: EndgameStrategist) -> None:
        assert strategist.get_strategy_distribution() == {}

    def test_with_data(self, strategist: EndgameStrategist) -> None:
        strategist.recommend_strategy(
            score_margin=-4, time_remaining_sec=90, period=4,
        )
        dist = strategist.get_strategy_distribution()
        assert len(dist) > 0


# =============================================================================
# 유틸리티
# =============================================================================

class TestStrategistUtility:
    def test_get_stats(self, strategist: EndgameStrategist) -> None:
        stats = strategist.get_stats()
        assert stats["total_strategies"] == 0

    def test_reset(self, strategist: EndgameStrategist) -> None:
        strategist.recommend_strategy(
            score_margin=-4, time_remaining_sec=90, period=4,
        )
        strategist.reset()
        assert strategist.total_strategies == 0

    def test_repr(self, strategist: EndgameStrategist) -> None:
        assert "EndgameStrategist" in repr(strategist)
