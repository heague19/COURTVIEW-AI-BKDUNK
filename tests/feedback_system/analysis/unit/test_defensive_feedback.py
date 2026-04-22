# -*- coding: utf-8 -*-
"""
feedback_system/analysis/defensive_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackType,
)
from shared.dto.tactical_dto import (
    DefenseAnalysis,
    DefenseScheme,
    MatchupData,
)

from feedback_system.analysis.defensive_feedback import (
    DefensiveFeedbackConfig,
    DefensiveFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> DefensiveFeedbackGenerator:
    return DefensiveFeedbackGenerator()


@pytest.fixture
def good_defense() -> DefenseAnalysis:
    return DefenseAnalysis(
        primary_scheme=DefenseScheme.MAN_TO_MAN,
        defensive_rating=100.5,
        opponent_fg_pct=42.0,
        opponent_3pt_pct=33.0,
        contested_shot_rate=0.72,
        help_rotation_quality=82.0,
        closeout_quality=75.0,
        box_out_rate=0.65,
    )


@pytest.fixture
def bad_defense() -> DefenseAnalysis:
    return DefenseAnalysis(
        primary_scheme=DefenseScheme.ZONE_2_3,
        defensive_rating=115.0,
        opponent_fg_pct=48.0,
        contested_shot_rate=0.40,
        help_rotation_quality=45.0,
        closeout_quality=40.0,
        box_out_rate=0.30,
    )


@pytest.fixture
def matchups() -> list[MatchupData]:
    return [
        MatchupData(
            defender_tracking_id=1,
            offensive_tracking_id=10,
            possessions=20,
            fg_attempts=15,
            fg_made=5,
            fg_pct=33.3,
            contest_rate=0.80,
        ),
        MatchupData(
            defender_tracking_id=2,
            offensive_tracking_id=11,
            possessions=18,
            fg_attempts=12,
            fg_made=7,
            fg_pct=58.3,
            contest_rate=0.50,
        ),
    ]


# =============================================================================
# 테스트
# =============================================================================
class TestDefensiveFeedbackGenerator:

    def test_name(self, gen: DefensiveFeedbackGenerator) -> None:
        assert gen.name == "DefensiveFeedbackGenerator"

    def test_good_defense_positive_items(
        self, gen: DefensiveFeedbackGenerator, good_defense: DefenseAnalysis,
    ) -> None:
        items = gen.generate(good_defense)
        assert len(items) >= 5  # DRtg + 스킴 + 컨테스트 + 헬프 + 클로즈아웃 + 박스아웃
        drtg = next(i for i in items if "DRtg" in i.title)
        assert drtg.feedback_type == FeedbackType.POSITIVE

    def test_bad_defense_correction_items(
        self, gen: DefensiveFeedbackGenerator, bad_defense: DefenseAnalysis,
    ) -> None:
        items = gen.generate(bad_defense)
        drtg = next(i for i in items if "DRtg" in i.title)
        assert drtg.feedback_type == FeedbackType.CORRECTION
        contest = next(i for i in items if "컨테스트" in i.title)
        assert contest.feedback_type == FeedbackType.CORRECTION

    def test_matchup_feedback(
        self,
        gen: DefensiveFeedbackGenerator,
        good_defense: DefenseAnalysis,
        matchups: list[MatchupData],
    ) -> None:
        items = gen.generate(good_defense, matchups=matchups)
        matchup_items = [i for i in items if "매치업" in i.title]
        assert len(matchup_items) >= 2
        # 개별 매치업 아이템 필터 (패턴: "매치업: #X vs #Y")
        individual = [i for i in matchup_items if "매치업:" in i.title]
        assert len(individual) == 2
        # 첫 번째 매치업: FG% 33.3 < 45 → POSITIVE
        assert individual[0].feedback_type == FeedbackType.POSITIVE
        # 두 번째 매치업: FG% 58.3 > 45 → CORRECTION
        assert individual[1].feedback_type == FeedbackType.CORRECTION

    def test_no_matchups(
        self, gen: DefensiveFeedbackGenerator, good_defense: DefenseAnalysis,
    ) -> None:
        items = gen.generate(good_defense, matchups=None)
        matchup_items = [i for i in items if "매치업" in i.title]
        assert len(matchup_items) == 0

    def test_scheme_info_always_present(
        self, gen: DefensiveFeedbackGenerator, good_defense: DefenseAnalysis,
    ) -> None:
        items = gen.generate(good_defense)
        scheme_items = [i for i in items if "스킴" in i.title]
        assert len(scheme_items) == 1

    def test_total_generated_increments(
        self, gen: DefensiveFeedbackGenerator, good_defense: DefenseAnalysis,
    ) -> None:
        gen.generate(good_defense)
        gen.generate(good_defense)
        assert gen.total_generated == 2

    def test_reset(
        self, gen: DefensiveFeedbackGenerator, good_defense: DefenseAnalysis,
    ) -> None:
        gen.generate(good_defense)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: DefensiveFeedbackGenerator) -> None:
        assert "DefensiveFeedbackGenerator" in repr(gen)
