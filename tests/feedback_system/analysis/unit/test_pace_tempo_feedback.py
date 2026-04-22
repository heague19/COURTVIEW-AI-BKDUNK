# -*- coding: utf-8 -*-
"""
feedback_system/analysis/pace_tempo_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.tactical_dto import TransitionData

from feedback_system.analysis.pace_tempo_feedback import (
    PaceTempoFeedbackConfig,
    PaceTempoFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> PaceTempoFeedbackGenerator:
    return PaceTempoFeedbackGenerator()


@pytest.fixture
def fast_transition() -> TransitionData:
    """빠른 전환 공격 팀 데이터."""
    return TransitionData(
        transition_ppp=1.18,
        halfcourt_ppp=0.98,
        transition_frequency=0.22,
        first_wave_success_rate=0.68,
        second_wave_success_rate=0.48,
        defensive_recovery_rate=0.72,
    )


@pytest.fixture
def slow_transition() -> TransitionData:
    """느린 하프코트 팀 데이터."""
    return TransitionData(
        transition_ppp=0.80,
        halfcourt_ppp=1.08,
        transition_frequency=0.07,
        first_wave_success_rate=0.45,
        second_wave_success_rate=0.30,
        defensive_recovery_rate=0.90,
    )


@pytest.fixture
def elite_transition() -> TransitionData:
    """엘리트 전환 공격 팀 데이터."""
    return TransitionData(
        transition_ppp=1.30,
        halfcourt_ppp=1.18,
        transition_frequency=0.25,
        first_wave_success_rate=0.80,
        second_wave_success_rate=0.55,
        defensive_recovery_rate=0.92,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestPaceTempoFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = PaceTempoFeedbackConfig()
        assert cfg.transition_ppp_threshold == 1.10
        assert cfg.recovery_rate_good == 0.75
        assert cfg.max_items == 20

    def test_custom(self) -> None:
        cfg = PaceTempoFeedbackConfig(transition_ppp_threshold=1.05)
        assert cfg.transition_ppp_threshold == 1.05


class TestPaceTempoFeedbackGenerator:
    def test_name(self, gen: PaceTempoFeedbackGenerator) -> None:
        assert gen.name == "PaceTempoFeedbackGenerator"

    def test_generate_returns_15_plus(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        items = gen.generate(fast_transition)
        assert len(items) >= 15
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_generate_slow_team(
        self,
        gen: PaceTempoFeedbackGenerator,
        slow_transition: TransitionData,
    ) -> None:
        items = gen.generate(slow_transition)
        assert len(items) >= 15

    def test_generate_elite_team(
        self,
        gen: PaceTempoFeedbackGenerator,
        elite_transition: TransitionData,
    ) -> None:
        items = gen.generate(elite_transition)
        assert len(items) >= 15

    def test_transition_vs_halfcourt(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """전환 vs 하프코트 PPP 비교 항목 2개."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "전환 공격 PPP" in titles
        assert "하프코트 PPP 및 전환 대비 효율" in titles

    def test_pace_items(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """경기 페이스 관련 항목."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "경기 페이스 분류" in titles
        assert "페이스-효율 상관 분석" in titles

    def test_fast_break_wave_items(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """속공 파도 항목 3개."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "1차 속공 파도 성공률" in titles
        assert "2차 속공 파도 성공률" in titles
        assert "속공 파도 성공률 격차" in titles

    def test_defensive_recovery_items(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """수비 복귀 항목 3개."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "수비 복귀율" in titles
        assert "속공 허용 위험 지수" in titles
        assert "페이스-수비 균형 평가" in titles

    def test_new_analysis_items(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """신규 분석 항목 4개."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "속공 마무리 효율" in titles
        assert "전환 공격 의존도 분석" in titles
        assert "공수 전환 스피드 종합" in titles
        assert "전략적 템포 권고" in titles

    def test_overall_rating(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        """종합 평점 항목."""
        items = gen.generate(fast_transition)
        titles = [i.title for i in items]
        assert "전환·페이스 종합 평점" in titles

    def test_strategic_recommendation_push_tempo(
        self,
        gen: PaceTempoFeedbackGenerator,
        elite_transition: TransitionData,
    ) -> None:
        """엘리트 팀은 push_tempo 전략."""
        items = gen.generate(elite_transition)
        strat = [i for i in items if i.title == "전략적 템포 권고"]
        assert len(strat) == 1
        assert "PUSH_TEMPO" in strat[0].description

    def test_strategic_recommendation_slow_down(
        self,
        gen: PaceTempoFeedbackGenerator,
        slow_transition: TransitionData,
    ) -> None:
        """느린 팀은 slow_down 전략."""
        items = gen.generate(slow_transition)
        strat = [i for i in items if i.title == "전략적 템포 권고"]
        assert len(strat) == 1
        assert "SLOW_DOWN" in strat[0].description

    def test_total_generated(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        gen.generate(fast_transition)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: PaceTempoFeedbackGenerator,
        fast_transition: TransitionData,
    ) -> None:
        gen.generate(fast_transition)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: PaceTempoFeedbackGenerator) -> None:
        assert "PaceTempoFeedbackGenerator" in repr(gen)
