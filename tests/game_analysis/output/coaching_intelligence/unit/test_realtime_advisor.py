# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: game_analysis/coaching_intelligence/realtime_advisor.py
설명: RealtimeAdvisor 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import pytest

from game_analysis.output.coaching_intelligence.realtime_advisor import (
    RealtimeAdvisor,
    RealtimeAdvisorConfig,
    RecommendationType,
    Urgency,
)


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture()
def advisor() -> RealtimeAdvisor:
    return RealtimeAdvisor()


@pytest.fixture()
def small_advisor() -> RealtimeAdvisor:
    return RealtimeAdvisor(RealtimeAdvisorConfig(
        max_recommendations=5, cooldown_sec=30.0,
    ))


# =============================================================================
# Enum
# =============================================================================

class TestEnums:
    def test_recommendation_types(self) -> None:
        assert len(RecommendationType) == 7
        assert RecommendationType.CALL_TIMEOUT.value == "call_timeout"

    def test_urgency(self) -> None:
        assert len(Urgency) == 4
        assert Urgency.CRITICAL.value == "critical"


# =============================================================================
# 초기화
# =============================================================================

class TestAdvisorInit:
    def test_default_config(self, advisor: RealtimeAdvisor) -> None:
        assert advisor.total_recommendations == 0
        assert advisor.name == "RealtimeAdvisor"


# =============================================================================
# 추천 생성
# =============================================================================

class TestGenerateRecommendation:
    def test_generate_single(self, advisor: RealtimeAdvisor) -> None:
        result = advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH,
            "타임아웃 추천",
            game_clock_sec=120.0,
            period=4,
            score_margin=-3,
        )
        assert result is True
        assert advisor.total_recommendations == 1

    def test_cooldown_blocks_duplicate(self, small_advisor: RealtimeAdvisor) -> None:
        # 첫 추천: 120초
        small_advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH,
            "타임아웃 1",
            game_clock_sec=120.0,
            period=4,
            score_margin=-3,
        )
        # 같은 유형, 10초 후 (110초): 쿨다운 내
        result = small_advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH,
            "타임아웃 2",
            game_clock_sec=110.0,
            period=4,
            score_margin=-3,
        )
        assert result is False
        assert small_advisor.total_recommendations == 1

    def test_different_type_not_blocked(self, small_advisor: RealtimeAdvisor) -> None:
        small_advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=-3,
        )
        result = small_advisor.generate_recommendation(
            RecommendationType.SUBSTITUTION,
            Urgency.MEDIUM, "교체",
            game_clock_sec=115.0, period=4, score_margin=-3,
        )
        assert result is True
        assert small_advisor.total_recommendations == 2

    def test_max_limit(self, small_advisor: RealtimeAdvisor) -> None:
        for i in range(10):
            small_advisor.generate_recommendation(
                RecommendationType(list(RecommendationType)[i % len(RecommendationType)].value),
                Urgency.LOW, f"추천 {i}",
                game_clock_sec=float(600 - i * 100),
                period=4, score_margin=0,
            )
        assert small_advisor.total_recommendations == 5


# =============================================================================
# 조회
# =============================================================================

class TestAdvisorQueries:
    def test_recent_recommendations(self, advisor: RealtimeAdvisor) -> None:
        advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=-3,
        )
        recent = advisor.get_recent_recommendations(5)
        assert len(recent) == 1
        assert recent[0]["type"] == "call_timeout"
        assert recent[0]["urgency"] == "high"

    def test_recommendations_by_type(self, advisor: RealtimeAdvisor) -> None:
        advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=0,
        )
        assert advisor.get_recommendations_by_type(RecommendationType.CALL_TIMEOUT) == 1
        assert advisor.get_recommendations_by_type(RecommendationType.SUBSTITUTION) == 0

    def test_clutch_recommendations(self, advisor: RealtimeAdvisor) -> None:
        # 클러치: 4쿼터, 3점차, 120초
        advisor.generate_recommendation(
            RecommendationType.FOUL_STRATEGY,
            Urgency.CRITICAL, "파울 전략",
            game_clock_sec=120.0, period=4, score_margin=3,
        )
        # 비클러치: 1쿼터
        advisor.generate_recommendation(
            RecommendationType.SUBSTITUTION,
            Urgency.LOW, "교체",
            game_clock_sec=500.0, period=1, score_margin=20,
        )
        clutch = advisor.get_clutch_recommendations()
        assert len(clutch) == 1
        assert clutch[0]["type"] == "foul_strategy"

    def test_type_distribution(self, advisor: RealtimeAdvisor) -> None:
        advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=0,
        )
        dist = advisor.get_type_distribution()
        assert dist["call_timeout"] == 1


# =============================================================================
# 유틸리티
# =============================================================================

class TestAdvisorUtility:
    def test_get_stats(self, advisor: RealtimeAdvisor) -> None:
        advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=3,
        )
        stats = advisor.get_stats()
        assert stats["total_recommendations"] == 1

    def test_reset(self, advisor: RealtimeAdvisor) -> None:
        advisor.generate_recommendation(
            RecommendationType.CALL_TIMEOUT,
            Urgency.HIGH, "타임아웃",
            game_clock_sec=120.0, period=4, score_margin=0,
        )
        advisor.reset()
        assert advisor.total_recommendations == 0

    def test_repr(self, advisor: RealtimeAdvisor) -> None:
        assert "RealtimeAdvisor" in repr(advisor)
