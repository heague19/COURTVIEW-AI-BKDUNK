# -*- coding: utf-8 -*-
"""feedback_system/analysis/strategic_recommendation_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import (
    DefenseAnalysis,
    DefenseScheme,
    PlayType,
    PlayTypeData,
    SpacingData,
    TacticalAnalysisResult,
    TransitionData,
)

from feedback_system.analysis.strategic_recommendation_feedback import (
    StrategicRecommendationFeedbackConfig,
    StrategicRecommendationFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
_TASK_ID = uuid4()


@pytest.fixture
def gen() -> StrategicRecommendationFeedbackGenerator:
    return StrategicRecommendationFeedbackGenerator()


@pytest.fixture
def game_stats() -> GameStats:
    home = TeamStats(
        team_id="home_team",
        is_home=True,
        final_score=106,
        field_goals_made=38,
        field_goals_attempted=82,
        three_pointers_made=12,
        three_pointers_attempted=30,
        free_throws_made=18,
        free_throws_attempted=22,
        offensive_rebounds=10,
        defensive_rebounds=28,
        total_rebounds=38,
        assists=24,
        steals=8,
        blocks=5,
        turnovers=12,
        personal_fouls=18,
    )
    away = TeamStats(
        team_id="away_team",
        is_home=False,
        final_score=95,
        field_goals_made=35,
        field_goals_attempted=85,
        three_pointers_made=10,
        three_pointers_attempted=32,
        free_throws_made=15,
        free_throws_attempted=20,
        offensive_rebounds=8,
        defensive_rebounds=30,
        total_rebounds=38,
        assists=20,
        steals=6,
        blocks=3,
        turnovers=15,
        personal_fouls=20,
    )
    return GameStats(
        task_id=_TASK_ID,
        home_team_stats=home,
        away_team_stats=away,
        home_score=106,
        away_score=95,
    )


@pytest.fixture
def tactical_result() -> TacticalAnalysisResult:
    return TacticalAnalysisResult(
        defense=DefenseAnalysis(
            primary_scheme=DefenseScheme.MAN_TO_MAN,
            defensive_rating=104.3,
            opponent_fg_pct=41.2,
            contested_shot_rate=0.62,
            steals_per_possession=0.08,
            blocks_per_possession=0.05,
        ),
        spacing=SpacingData(
            avg_player_spacing=14.8,
            court_utilization_pct=68.0,
            drive_lane_openness=60.0,
            paint_touch_frequency=2.5,
            three_point_spacing=13.0,
        ),
        play_types=[
            PlayTypeData(
                play_type=PlayType.PICK_AND_ROLL,
                frequency=40,
                ppp=1.05,
                fg_pct=0.46,
            ),
            PlayTypeData(
                play_type=PlayType.TRANSITION,
                frequency=25,
                ppp=1.22,
                fg_pct=0.55,
            ),
        ],
        transitions=TransitionData(
            transition_ppp=1.22,
            halfcourt_ppp=0.98,
            transition_frequency=0.20,
            first_wave_success_rate=0.65,
            second_wave_success_rate=0.45,
            defensive_recovery_rate=0.78,
        ),
    )


# =============================================================================
# 테스트
# =============================================================================
class TestStrategicRecommendationFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = StrategicRecommendationFeedbackConfig()
        assert cfg.efg_good_threshold == 53.0
        assert cfg.tov_good_threshold == 12.0
        assert cfg.three_pt_rate_good == 36.0

    def test_custom(self) -> None:
        cfg = StrategicRecommendationFeedbackConfig(efg_good_threshold=55.0)
        assert cfg.efg_good_threshold == 55.0


class TestStrategicRecommendationFeedbackGenerator:
    def test_name(self, gen: StrategicRecommendationFeedbackGenerator) -> None:
        assert gen.name == "StrategicRecommendationFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: StrategicRecommendationFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(tactical_result, game_stats)
        assert len(items) > 0
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_total_generated(
        self,
        gen: StrategicRecommendationFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
        game_stats: GameStats,
    ) -> None:
        gen.generate(tactical_result, game_stats)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: StrategicRecommendationFeedbackGenerator,
        tactical_result: TacticalAnalysisResult,
        game_stats: GameStats,
    ) -> None:
        gen.generate(tactical_result, game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_minimal_data(
        self,
        gen: StrategicRecommendationFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        """최소 전술 데이터 → 기본 전략 권고."""
        result = TacticalAnalysisResult()
        items = gen.generate(result, game_stats)
        assert isinstance(items, list)

    def test_repr(self, gen: StrategicRecommendationFeedbackGenerator) -> None:
        assert "StrategicRecommendationFeedbackGenerator" in repr(gen)
