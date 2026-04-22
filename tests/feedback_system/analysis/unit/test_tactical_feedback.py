# -*- coding: utf-8 -*-
"""
feedback_system/analysis/tactical_feedback.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.dto.tactical_dto import (
    FastBreakAnalysis,
    PickAndRollAnalysis,
    PlayTypeData,
    SetPlayAnalysis,
    PassingNetworkData,
    TacticalAnalysisResult,
    TransitionData,
)
from shared.constants.game_rule_constants import PlayType

from feedback_system.analysis.tactical_feedback import (
    TacticalFeedbackConfig,
    TacticalFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> TacticalFeedbackGenerator:
    return TacticalFeedbackGenerator()


@pytest.fixture
def full_result() -> TacticalAnalysisResult:
    """모든 전술 데이터가 채워진 결과."""
    return TacticalAnalysisResult(
        game_id="test-game-001",
        pick_and_roll=PickAndRollAnalysis(
            total_pnr=25,
            pnr_ppp=1.15,
            ballhandler_efficiency=1.10,
            roller_efficiency=1.20,
            pop_efficiency=0.95,
        ),
        fast_break=FastBreakAnalysis(
            total_fast_breaks=12,
            fast_break_ppp=1.25,
            average_transition_time_seconds=3.2,
        ),
        set_plays=SetPlayAnalysis(
            total_set_plays=18,
            set_play_ppp=1.05,
            top_plays=["Horns", "Floppy", "Motion"],
        ),
        passing_network=PassingNetworkData(
            ball_movement_rating=78.0,
            average_passes_per_possession=3.5,
        ),
        play_types=[
            PlayTypeData(play_type=PlayType.ISOLATION, frequency=15, ppp=0.85, fg_pct=38.0),
            PlayTypeData(play_type=PlayType.PICK_AND_ROLL, frequency=25, ppp=1.15, fg_pct=52.0),
        ],
        transitions=TransitionData(
            transition_ppp=1.18,
            halfcourt_ppp=0.95,
        ),
    )


@pytest.fixture
def empty_result() -> TacticalAnalysisResult:
    """빈 전술 결과."""
    return TacticalAnalysisResult(game_id="test-empty")


# =============================================================================
# 테스트
# =============================================================================
class TestTacticalFeedbackGenerator:

    def test_name(self, gen: TacticalFeedbackGenerator) -> None:
        assert gen.name == "TacticalFeedbackGenerator"

    def test_empty_result_no_items(
        self, gen: TacticalFeedbackGenerator, empty_result: TacticalAnalysisResult,
    ) -> None:
        items = gen.generate(empty_result)
        assert isinstance(items, list)
        assert len(items) == 0

    def test_full_result_generates_items(
        self, gen: TacticalFeedbackGenerator, full_result: TacticalAnalysisResult,
    ) -> None:
        items = gen.generate(full_result)
        assert len(items) >= 5  # PnR + 속공 + 세트 + 볼무브 + 전환 + 플레이유형
        titles = [i.title for i in items]
        assert "픽앤롤 효율" in titles
        assert "속공 효율" in titles
        assert "볼 무브먼트" in titles
        assert "전환 공격 효율" in titles

    def test_pick_and_roll_positive(
        self, full_result: TacticalAnalysisResult,
    ) -> None:
        gen = TacticalFeedbackGenerator(TacticalFeedbackConfig(pnr_ppp_good=1.0))
        items = gen.generate(full_result)
        pnr_item = next(i for i in items if i.title == "픽앤롤 효율")
        assert pnr_item.feedback_type == FeedbackType.POSITIVE

    def test_pick_and_roll_correction(
        self, full_result: TacticalAnalysisResult,
    ) -> None:
        gen = TacticalFeedbackGenerator(TacticalFeedbackConfig(pnr_ppp_good=1.5))
        items = gen.generate(full_result)
        pnr_item = next(i for i in items if i.title == "픽앤롤 효율")
        assert pnr_item.feedback_type == FeedbackType.CORRECTION

    def test_play_type_items(
        self, gen: TacticalFeedbackGenerator, full_result: TacticalAnalysisResult,
    ) -> None:
        items = gen.generate(full_result)
        iso_items = [i for i in items if "isolation" in i.title.lower()]
        assert len(iso_items) == 1

    def test_total_generated_increments(
        self, gen: TacticalFeedbackGenerator, full_result: TacticalAnalysisResult,
    ) -> None:
        assert gen.total_generated == 0
        gen.generate(full_result)
        assert gen.total_generated == 1
        gen.generate(full_result)
        assert gen.total_generated == 2

    def test_reset(
        self, gen: TacticalFeedbackGenerator, full_result: TacticalAnalysisResult,
    ) -> None:
        gen.generate(full_result)
        gen.reset()
        assert gen.total_generated == 0

    def test_all_items_are_feedback_items(
        self, gen: TacticalFeedbackGenerator, full_result: TacticalAnalysisResult,
    ) -> None:
        items = gen.generate(full_result)
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_repr(self, gen: TacticalFeedbackGenerator) -> None:
        assert "TacticalFeedbackGenerator" in repr(gen)
