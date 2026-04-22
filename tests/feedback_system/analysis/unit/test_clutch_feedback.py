# -*- coding: utf-8 -*-
"""
feedback_system/analysis/clutch_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem, FeedbackType
from shared.dto.tactical_dto import (
    ClutchStats,
    IndividualAnalysis,
)

from feedback_system.analysis.clutch_feedback import (
    ClutchFeedbackConfig,
    ClutchFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> ClutchFeedbackGenerator:
    return ClutchFeedbackGenerator()


@pytest.fixture
def clutch_stats_good() -> ClutchStats:
    return ClutchStats(
        points=8,
        fg_pct=0.52,
        ft_pct=0.88,
        turnovers=1,
        plus_minus=5,
    )


@pytest.fixture
def clutch_stats_poor() -> ClutchStats:
    return ClutchStats(
        points=2,
        fg_pct=0.22,
        ft_pct=0.50,
        turnovers=4,
        plus_minus=-6,
    )


@pytest.fixture
def analyses(
    clutch_stats_good: ClutchStats,
    clutch_stats_poor: ClutchStats,
) -> list[IndividualAnalysis]:
    return [
        IndividualAnalysis(
            player_tracking_id=1,
            clutch_stats=clutch_stats_good,
            on_court_net_rating=8.0,
            off_court_net_rating=1.8,
        ),
        IndividualAnalysis(
            player_tracking_id=2,
            clutch_stats=clutch_stats_poor,
            on_court_net_rating=-1.0,
            off_court_net_rating=1.5,
        ),
    ]


# =============================================================================
# 테스트
# =============================================================================
class TestClutchFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = ClutchFeedbackConfig()
        assert cfg.clutch_fg_pct_threshold == 0.40
        assert cfg.clutch_fg_pct_elite == 0.50
        assert cfg.clutch_turnover_max == 2

    def test_custom(self) -> None:
        cfg = ClutchFeedbackConfig(clutch_fg_pct_threshold=0.45)
        assert cfg.clutch_fg_pct_threshold == 0.45


class TestClutchFeedbackGenerator:
    def test_name(self, gen: ClutchFeedbackGenerator) -> None:
        assert gen.name == "ClutchFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        items = gen.generate(analyses)
        assert len(items) >= 15
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_no_clutch_data(self, gen: ClutchFeedbackGenerator) -> None:
        """클러치 스탯 없는 선수만 → 데이터 없음 피드백."""
        analyses = [
            IndividualAnalysis(
                player_tracking_id=3,
                clutch_stats=None,
            ),
        ]
        items = gen.generate(analyses)
        assert len(items) >= 1
        assert "데이터 없음" in items[0].title

    def test_empty_list(self, gen: ClutchFeedbackGenerator) -> None:
        items = gen.generate([])
        assert len(items) >= 1

    def test_individual_clutch_items(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        """개인 클러치 피드백 항목 존재."""
        items = gen.generate(analyses)
        titles = [i.title for i in items]
        assert any("클러치 득점" in t for t in titles)
        assert any("클러치 야투율" in t for t in titles)
        assert any("클러치 턴오버" in t for t in titles)
        assert any("클러치 +/-" in t for t in titles)

    def test_team_clutch_items(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        """팀 클러치 종합 피드백 항목 존재."""
        items = gen.generate(analyses)
        titles = [i.title for i in items]
        assert any("팀 클러치 야투율" in t for t in titles)
        assert any("팀 클러치 총득점" in t for t in titles)

    def test_best_clutch_performer(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        items = gen.generate(analyses)
        best = [i for i in items if "최고 클러치" in i.title]
        assert len(best) == 1
        assert best[0].feedback_type == FeedbackType.POSITIVE

    def test_clutch_overall_grade(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        items = gen.generate(analyses)
        assert any("클러치 종합 등급" in i.title for i in items)

    def test_clutch_risk_assessment(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        items = gen.generate(analyses)
        assert any("리스크" in i.title for i in items)

    def test_total_generated(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        gen.generate(analyses)
        gen.generate(analyses)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: ClutchFeedbackGenerator,
        analyses: list[IndividualAnalysis],
    ) -> None:
        gen.generate(analyses)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: ClutchFeedbackGenerator) -> None:
        assert "ClutchFeedbackGenerator" in repr(gen)
