# -*- coding: utf-8 -*-
"""feedback_system/analysis/opponent_tendency_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.tactical_dto import (
    DefenseAnalysis,
    DefenseScheme,
    PlayType,
    PlayTypeData,
    SpacingData,
    TacticalAnalysisResult,
    TransitionData,
)

from feedback_system.analysis.opponent_tendency_feedback import (
    OpponentTendencyFeedbackConfig,
    OpponentTendencyFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> OpponentTendencyFeedbackGenerator:
    return OpponentTendencyFeedbackGenerator()


@pytest.fixture
def tactical_result() -> TacticalAnalysisResult:
    return TacticalAnalysisResult(
        defense=DefenseAnalysis(
            primary_scheme=DefenseScheme.MAN_TO_MAN,
            defensive_rating=108.5,
            opponent_fg_pct=48.2,
            contested_shot_rate=0.52,
            steals_per_possession=0.07,
            blocks_per_possession=0.04,
        ),
        spacing=SpacingData(
            avg_player_spacing=14.2,
            court_utilization_pct=65.0,
            drive_lane_openness=55.0,
            paint_touch_frequency=2.8,
            three_point_spacing=12.5,
        ),
        play_types=[
            PlayTypeData(
                play_type=PlayType.PICK_AND_ROLL,
                frequency=35,
                ppp=0.82,
                fg_pct=0.40,
            ),
            PlayTypeData(
                play_type=PlayType.ISOLATION,
                frequency=18,
                ppp=0.78,
                fg_pct=0.38,
            ),
            PlayTypeData(
                play_type=PlayType.SPOT_UP,
                frequency=22,
                ppp=1.18,
                fg_pct=0.42,
            ),
        ],
        transitions=TransitionData(
            transition_ppp=1.15,
            halfcourt_ppp=0.95,
            transition_frequency=0.18,
            first_wave_success_rate=0.62,
            second_wave_success_rate=0.42,
            defensive_recovery_rate=0.68,
        ),
    )


# =============================================================================
# 테스트
# =============================================================================
class TestOpponentTendencyFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = OpponentTendencyFeedbackConfig()
        assert cfg.weakness_threshold_ppp == 0.85
        assert cfg.drtg_weak_threshold == 110.0

    def test_custom(self) -> None:
        cfg = OpponentTendencyFeedbackConfig(drtg_weak_threshold=108.0)
        assert cfg.drtg_weak_threshold == 108.0


class TestOpponentTendencyFeedbackGenerator:
    def test_name(self, gen: OpponentTendencyFeedbackGenerator) -> None:
        assert gen.name == "OpponentTendencyFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: OpponentTendencyFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
    ) -> None:
        items = gen.generate(tactical_result)
        assert len(items) > 0
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_total_generated(
        self,
        gen: OpponentTendencyFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
    ) -> None:
        gen.generate(tactical_result)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: OpponentTendencyFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
    ) -> None:
        gen.generate(tactical_result)
        gen.reset()
        assert gen.total_generated == 0

    def test_minimal_tactical_result(
        self,
        gen: OpponentTendencyFeedbackGenerator,
    ) -> None:
        """최소 데이터 → 기본 피드백 반환."""
        result = TacticalAnalysisResult()
        items = gen.generate(result)
        assert isinstance(items, list)

    def test_repr(self, gen: OpponentTendencyFeedbackGenerator) -> None:
        assert "OpponentTendencyFeedbackGenerator" in repr(gen)
