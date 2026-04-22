# -*- coding: utf-8 -*-
"""feedback_system/analysis/game_context_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import (
    GameFlowData,
    MomentumShift,
    MomentumState,
    ScoringRun,
)

from feedback_system.analysis.game_context_feedback import (
    GameContextFeedbackConfig,
    GameContextFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> GameContextFeedbackGenerator:
    return GameContextFeedbackGenerator()


@pytest.fixture
def close_game() -> tuple[GameStats, GameFlowData]:
    team = TeamStats(
        final_score=88, is_home=True,
        quarter_scores=[22, 24, 20, 22],
        field_goals_attempted=80, fast_break_points=10,
    )
    gs = GameStats(
        task_id="00000000-0000-0000-0000-000000000001",
        home_score=88, away_score=90,
        home_team_stats=team,
        lead_changes=12, ties=8,
        largest_lead_home=8, largest_lead_away=6,
    )
    gf = GameFlowData(
        scoring_runs=[
            ScoringRun(team_id="home", points=12, start_time=300, end_time=420),
            ScoringRun(team_id="away", points=10, start_time=600, end_time=780),
            ScoringRun(team_id="home", points=8, start_time=1200, end_time=1350),
        ],
        momentum_shifts=[
            MomentumShift(frame=i * 500, from_state="home", to_state="away")
            for i in range(7)
        ],
        current_momentum=MomentumState.SLIGHT_AWAY,
        lead_changes=12, ties=8,
        largest_lead_home=8, largest_lead_away=6,
    )
    return gs, gf


@pytest.fixture
def blowout_game() -> tuple[GameStats, GameFlowData]:
    team = TeamStats(
        final_score=110, is_home=True,
        quarter_scores=[30, 28, 30, 22],
        field_goals_attempted=85, fast_break_points=20,
    )
    gs = GameStats(
        task_id="00000000-0000-0000-0000-000000000001",
        home_score=110, away_score=82,
        home_team_stats=team,
        lead_changes=1, ties=1,
        largest_lead_home=32, largest_lead_away=2,
    )
    gf = GameFlowData(
        scoring_runs=[
            ScoringRun(team_id="home", points=18, start_time=100, end_time=300),
        ],
        momentum_shifts=[
            MomentumShift(frame=200, from_state="neutral", to_state="strong_home"),
        ],
        current_momentum=MomentumState.STRONG_HOME,
        lead_changes=1, ties=1,
        largest_lead_home=32, largest_lead_away=2,
    )
    return gs, gf


# =============================================================================
# 테스트
# =============================================================================
class TestGameContextFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = GameContextFeedbackConfig()
        assert cfg.garbage_time_lead == 20
        assert cfg.close_game_threshold == 5

    def test_custom(self) -> None:
        cfg = GameContextFeedbackConfig(close_game_threshold=3)
        assert cfg.close_game_threshold == 3


class TestGameContextFeedbackGenerator:
    def test_name(self, gen: GameContextFeedbackGenerator) -> None:
        assert gen.name == "GameContextFeedbackGenerator"

    def test_close_game_generates_16(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        items = gen.generate(gs, gf)
        assert len(items) >= 15
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_blowout_generates_16(
        self,
        gen: GameContextFeedbackGenerator,
        blowout_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = blowout_game
        items = gen.generate(gs, gf)
        assert len(items) >= 15

    def test_game_context_tags_present(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        items = gen.generate(gs, gf)
        items_with_ctx = [i for i in items if i.game_context is not None]
        assert len(items_with_ctx) >= 10

    def test_close_game_detected(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        items = gen.generate(gs, gf)
        result_item = [i for i in items if i.title == "경기 결과 맥락 분석"][0]
        assert result_item.game_context == "close_game"

    def test_blowout_garbage_time(
        self,
        gen: GameContextFeedbackGenerator,
        blowout_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = blowout_game
        items = gen.generate(gs, gf)
        garbage = [i for i in items if i.title == "가비지타임 감지"][0]
        assert garbage.game_context == "garbage_time"

    def test_quarter_trend_items(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        items = gen.generate(gs, gf)
        titles = [i.title for i in items]
        assert "쿼터별 점수 추세" in titles
        assert "최강·최약 쿼터 분석" in titles
        assert "전반/후반 체력 추세" in titles

    def test_momentum_items(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        items = gen.generate(gs, gf)
        titles = [i.title for i in items]
        assert "모멘텀 전환 빈도" in titles
        assert "최종 모멘텀 상태" in titles

    def test_no_home_team(self, gen: GameContextFeedbackGenerator) -> None:
        gs = GameStats(task_id="00000000-0000-0000-0000-000000000001")
        items = gen.generate(gs, GameFlowData())
        assert items == []

    def test_total_generated(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        gen.generate(gs, gf)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: GameContextFeedbackGenerator,
        close_game: tuple[GameStats, GameFlowData],
    ) -> None:
        gs, gf = close_game
        gen.generate(gs, gf)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: GameContextFeedbackGenerator) -> None:
        assert "GameContextFeedbackGenerator" in repr(gen)
