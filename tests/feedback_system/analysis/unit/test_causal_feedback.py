# -*- coding: utf-8 -*-
"""feedback_system/analysis/causal_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import CausalFactor, FeedbackItem
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import (
    DefenseAnalysis,
    FastBreakAnalysis,
    PassingNetworkData,
    PickAndRollAnalysis,
    TacticalAnalysisResult,
    TransitionData,
)

from feedback_system.analysis.causal_feedback import (
    CausalFeedbackConfig,
    CausalFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def poor_team() -> TeamStats:
    return TeamStats(
        field_goal_percentage=38.0, field_goals_attempted=80, field_goals_made=30,
        three_point_percentage=28.0, three_pointers_attempted=30, three_pointers_made=8,
        free_throw_percentage=75.0, free_throws_made=15, free_throws_attempted=20,
        offensive_rebounds=5, defensive_rebounds=22, total_rebounds=27,
        assists=12, turnovers=18, steals=6, blocks=3,
        points_in_paint=26, second_chance_points=6, fast_break_points=8, bench_points=12,
    )


@pytest.fixture
def good_team() -> TeamStats:
    return TeamStats(
        field_goal_percentage=50.0, field_goals_attempted=78, field_goals_made=39,
        three_point_percentage=38.0, three_pointers_attempted=22, three_pointers_made=8,
        free_throw_percentage=82.0, free_throws_made=18, free_throws_attempted=22,
        offensive_rebounds=13, defensive_rebounds=32, total_rebounds=45,
        assists=25, turnovers=10, steals=8, blocks=5,
        points_in_paint=48, second_chance_points=16, fast_break_points=18, bench_points=32,
    )


@pytest.fixture
def poor_tactical() -> TacticalAnalysisResult:
    return TacticalAnalysisResult(
        defense=DefenseAnalysis(
            defensive_rating=112.0, opponent_fg_pct=50.0,
            contested_shot_rate=0.38, help_rotation_quality=35.0,
            closeout_quality=42.0, box_out_rate=40.0,
        ),
        passing_network=PassingNetworkData(
            ball_movement_rating=35.0, average_passes_per_possession=2.1,
        ),
        pick_and_roll=PickAndRollAnalysis(pnr_ppp=0.82),
        fast_break=FastBreakAnalysis(fast_break_ppp=1.20),
        transitions=TransitionData(
            defensive_recovery_rate=0.62, transition_frequency=0.22,
        ),
    )


@pytest.fixture
def gen() -> CausalFeedbackGenerator:
    return CausalFeedbackGenerator()


# =============================================================================
# 테스트
# =============================================================================
class TestCausalFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = CausalFeedbackConfig()
        assert cfg.fg_pct_poor == 40.0
        assert cfg.tov_rate_high == 16.0

    def test_custom(self) -> None:
        cfg = CausalFeedbackConfig(fg_pct_poor=35.0)
        assert cfg.fg_pct_poor == 35.0


class TestCausalFeedbackGenerator:
    def test_name(self, gen: CausalFeedbackGenerator) -> None:
        assert gen.name == "CausalFeedbackGenerator"

    def test_poor_team_generates_16_items(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        items = gen.generate(gs, poor_tactical)
        assert len(items) >= 15
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_good_team_generates_items(
        self,
        gen: CausalFeedbackGenerator,
        good_team: TeamStats,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=good_team,
        )
        tactical = TacticalAnalysisResult(
            defense=DefenseAnalysis(
                defensive_rating=98.0, opponent_fg_pct=41.0,
                contested_shot_rate=0.65, help_rotation_quality=75.0,
                closeout_quality=70.0, box_out_rate=72.0,
            ),
            passing_network=PassingNetworkData(
                ball_movement_rating=78.0, average_passes_per_possession=3.8,
            ),
        )
        items = gen.generate(gs, tactical)
        assert len(items) >= 15

    def test_causal_factors_attached(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        items = gen.generate(gs, poor_tactical)
        items_with_causes = [i for i in items if i.causal_factors]
        assert len(items_with_causes) >= 5
        for item in items_with_causes:
            for cf in item.causal_factors:
                assert isinstance(cf, CausalFactor)
                assert cf.factor
                assert 0.0 <= cf.impact <= 1.0

    def test_no_home_team(self, gen: CausalFeedbackGenerator) -> None:
        gs = GameStats(task_id="00000000-0000-0000-0000-000000000001")
        items = gen.generate(gs, TacticalAnalysisResult())
        assert items == []

    def test_total_generated(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        gen.generate(gs, poor_tactical)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        gen.generate(gs, poor_tactical)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: CausalFeedbackGenerator) -> None:
        assert "CausalFeedbackGenerator" in repr(gen)

    def test_shooting_cause_titles(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        items = gen.generate(gs, poor_tactical)
        titles = [i.title for i in items]
        assert "슈팅 효율 원인 분석" in titles
        assert "3점 슈팅 원인 분석" in titles
        assert "턴오버 원인 분석" in titles

    def test_defensive_titles(
        self,
        gen: CausalFeedbackGenerator,
        poor_team: TeamStats,
        poor_tactical: TacticalAnalysisResult,
    ) -> None:
        gs = GameStats(
            task_id="00000000-0000-0000-0000-000000000001",
            home_team_stats=poor_team,
        )
        items = gen.generate(gs, poor_tactical)
        titles = [i.title for i in items]
        assert "상대 FG% 허용 원인" in titles
        assert "헬프 로테이션 품질 원인" in titles
