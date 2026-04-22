# -*- coding: utf-8 -*-
"""feedback_system/analysis/drill_prescription_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, PlayerStats, TeamStats

from feedback_system.analysis.drill_prescription_feedback import (
    DrillPrescriptionFeedbackConfig,
    DrillPrescriptionFeedbackGenerator,
    DrillSpec,
)


# =============================================================================
# Fixtures
# =============================================================================
def _make_player(tid: int, pts: int, **kw) -> PlayerStats:
    fgm = kw.pop("fgm", pts // 3)
    fga = kw.pop("fga", fgm + 5)
    return PlayerStats(
        player_tracking_id=tid,
        points=pts,
        field_goals_made=fgm,
        field_goals_attempted=fga,
        field_goal_percentage=round(fgm / fga * 100, 1) if fga else 0.0,
        three_pointers_made=kw.pop("tpm", 2),
        three_pointers_attempted=kw.pop("tpa", 5),
        three_point_percentage=40.0,
        free_throws_made=kw.pop("ftm", 3),
        free_throws_attempted=kw.pop("fta", 4),
        free_throw_percentage=75.0,
        offensive_rebounds=1,
        defensive_rebounds=3,
        total_rebounds=4,
        assists=kw.pop("ast", 3),
        turnovers=kw.pop("tov", 2),
        steals=kw.pop("stl", 1),
        blocks=kw.pop("blk", 0),
        personal_fouls=2,
        plus_minus=5,
        **kw,
    )


@pytest.fixture
def gen() -> DrillPrescriptionFeedbackGenerator:
    return DrillPrescriptionFeedbackGenerator()


@pytest.fixture
def home_team() -> TeamStats:
    return TeamStats(
        team_id="HOME",
        team_name="홈팀",
        is_home=True,
        final_score=78,
        quarter_scores=[18, 20, 18, 22],
        field_goals_made=28,
        field_goals_attempted=72,
        field_goal_percentage=38.9,
        three_pointers_made=5,
        three_pointers_attempted=22,
        three_point_percentage=22.7,
        free_throws_made=17,
        free_throws_attempted=24,
        free_throw_percentage=70.8,
        offensive_rebounds=6,
        defensive_rebounds=20,
        total_rebounds=26,
        assists=14,
        turnovers=16,
        steals=4,
        blocks=2,
        personal_fouls=18,
        points_in_paint=28,
        second_chance_points=8,
        fast_break_points=6,
        bench_points=18,
        player_stats=[
            _make_player(1, 20, fgm=7, fga=18, tov=4),  # 낮은 야투율, 높은 턴오버
            _make_player(2, 14, fgm=4, fga=14, tpm=1, tpa=8),  # 3점 낮음
            _make_player(3, 12, fgm=5, fga=10, ast=6, stl=3),
            _make_player(4, 10, fgm=3, fga=10, ftm=2, fta=6),  # 자유투 낮음
            _make_player(5, 8, fgm=2, fga=8, blk=2),
        ],
    )


@pytest.fixture
def away_team() -> TeamStats:
    return TeamStats(
        team_id="AWAY",
        team_name="원정팀",
        is_home=False,
        final_score=92,
        quarter_scores=[24, 22, 24, 22],
        field_goals_made=35,
        field_goals_attempted=70,
        field_goal_percentage=50.0,
        three_pointers_made=10,
        three_pointers_attempted=24,
        three_point_percentage=41.7,
        free_throws_made=12,
        free_throws_attempted=16,
        free_throw_percentage=75.0,
        offensive_rebounds=9,
        defensive_rebounds=24,
        total_rebounds=33,
        assists=22,
        turnovers=10,
        steals=7,
        blocks=4,
        personal_fouls=16,
        points_in_paint=36,
        second_chance_points=12,
        fast_break_points=14,
        bench_points=24,
        player_stats=[
            _make_player(10, 24, fgm=9, fga=16),
            _make_player(11, 18, fgm=7, fga=13),
        ],
    )


@pytest.fixture
def game_stats(home_team: TeamStats, away_team: TeamStats) -> GameStats:
    return GameStats(
        task_id=uuid4(),
        home_score=78,
        away_score=92,
        home_team_stats=home_team,
        away_team_stats=away_team,
        lead_changes=4,
        ties=2,
        largest_lead_home=3,
        largest_lead_away=18,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestDrillSpec:
    def test_frozen(self) -> None:
        spec = DrillSpec(
            name="폼슈팅 50회",
            category="shooting",
            description="페인트 존 근거리 폼슈팅",
            duration_min=15,
            repetitions=50,
            target_weakness="야투율",
            expected_effect="정확도 향상",
            difficulty="beginner",
        )
        assert spec.name == "폼슈팅 50회"
        with pytest.raises(AttributeError):
            spec.name = "변경"  # type: ignore[misc]


class TestDrillPrescriptionFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = DrillPrescriptionFeedbackConfig()
        assert cfg.fg_pct_weak == 40.0
        assert cfg.three_pt_pct_weak == 30.0
        assert cfg.ft_pct_weak == 70.0

    def test_custom(self) -> None:
        cfg = DrillPrescriptionFeedbackConfig(fg_pct_weak=42.0)
        assert cfg.fg_pct_weak == 42.0


class TestDrillPrescriptionFeedbackGenerator:
    def test_name(self, gen: DrillPrescriptionFeedbackGenerator) -> None:
        assert gen.name == "DrillPrescriptionFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        assert len(items) >= 10
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_team_drill_feedback(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("훈련" in t or "드릴" in t for t in titles)

    def test_player_drill_feedback(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        descs = [i.description for i in items]
        # 드릴 처방 관련 설명 포함
        assert any("반복" in d or "훈련" in d or "연습" in d or "드릴" in d for d in descs)

    def test_training_plan_summary(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        items = gen.generate(game_stats)
        titles = [i.title for i in items]
        assert any("훈련" in t or "플랜" in t or "계획" in t or "종합" in t for t in titles)

    def test_total_generated(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.generate(game_stats)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: DrillPrescriptionFeedbackGenerator,
        game_stats: GameStats,
    ) -> None:
        gen.generate(game_stats)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: DrillPrescriptionFeedbackGenerator) -> None:
        assert "DrillPrescriptionFeedbackGenerator" in repr(gen)
