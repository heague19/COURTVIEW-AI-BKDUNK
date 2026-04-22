# -*- coding: utf-8 -*-
"""feedback_system/analysis/scouting_feedback.py 단위 테스트."""

from __future__ import annotations

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.scouting_dto import (
    DefensiveGap,
    KeyPlayerInfo,
    MatchupExploit,
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
)

from feedback_system.analysis.scouting_feedback import (
    ScoutingFeedbackConfig,
    ScoutingFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def gen() -> ScoutingFeedbackGenerator:
    return ScoutingFeedbackGenerator()


@pytest.fixture
def team() -> TeamStats:
    return TeamStats(
        final_score=95, is_home=True,
        field_goals_attempted=82, free_throws_attempted=22, turnovers=14,
        three_point_percentage=38.0, three_pointers_attempted=28, three_pointers_made=10,
        offensive_rebounds=11, fast_break_points=16,
    )


@pytest.fixture
def game_stats(team: TeamStats) -> GameStats:
    return GameStats(
        task_id="00000000-0000-0000-0000-000000000001",
        home_score=95, away_score=88,
        home_team_stats=team,
    )


@pytest.fixture
def opponent() -> OpponentProfile:
    return OpponentProfile(
        team_name="Eagles", games_analyzed=5,
        offensive_rating=108.0, defensive_rating=105.0, pace=72.0,
        primary_offense="motion", primary_defense="man_to_man",
        key_players=[
            KeyPlayerInfo(tracking_id=23, name="Player X", role="SG", ppg=22.5, usage_pct=0.30),
        ],
        strengths=["3점 슈팅", "전환 공격"],
        weaknesses=["리바운드", "페인트 수비"],
    )


@pytest.fixture
def tendency() -> TendencyReport:
    return TendencyReport(
        transition_tendency=22.0,
        three_point_rate=0.40,
        paint_attack_rate=0.35,
        right_side_preference=0.62,
        left_side_preference=0.38,
    )


@pytest.fixture
def weakness() -> WeaknessReport:
    return WeaknessReport(
        defensive_gaps=[
            DefensiveGap(zone="paint", gap_severity=0.75, exploitable_play="pick_and_roll"),
        ],
        transition_weakness_score=65.0,
        rebounding_weakness="defensive",
        matchup_exploits=[
            MatchupExploit(player_tracking_id=5, weakness_type="post_defense", severity=0.8),
        ],
        three_point_defense_rating=40.0,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestScoutingFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = ScoutingFeedbackConfig()
        assert cfg.transition_exploit_threshold == 14.0

    def test_custom(self) -> None:
        cfg = ScoutingFeedbackConfig(transition_exploit_threshold=12.0)
        assert cfg.transition_exploit_threshold == 12.0


class TestScoutingFeedbackGenerator:
    def test_name(self, gen: ScoutingFeedbackGenerator) -> None:
        assert gen.name == "ScoutingFeedbackGenerator"

    def test_full_scouting_15_items(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport,
        weakness: WeaknessReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency, weakness)
        assert len(items) >= 15
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_without_tendency(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        weakness: WeaknessReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency=None, weakness=weakness)
        assert len(items) >= 15

    def test_without_weakness(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency, weakness=None)
        assert len(items) >= 15

    def test_profile_titles(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport,
        weakness: WeaknessReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency, weakness)
        titles = [i.title for i in items]
        assert "상대 공격력 억제 평가" in titles
        assert "상대 수비 돌파 평가" in titles
        assert "페이스 지배력 평가" in titles

    def test_weakness_exploit_titles(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport,
        weakness: WeaknessReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency, weakness)
        titles = [i.title for i in items]
        assert "전환 약점 공략" in titles
        assert "리바운드 약점 공략" in titles
        assert "매치업 약점 공략" in titles

    def test_scouting_grade(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
        tendency: TendencyReport,
        weakness: WeaknessReport,
    ) -> None:
        items = gen.generate(game_stats, opponent, tendency, weakness)
        grade_item = [i for i in items if i.title == "스카우팅 실행도 등급"]
        assert len(grade_item) == 1
        assert grade_item[0].current_value is not None

    def test_no_home_team(
        self,
        gen: ScoutingFeedbackGenerator,
        opponent: OpponentProfile,
    ) -> None:
        gs = GameStats(task_id="00000000-0000-0000-0000-000000000001")
        items = gen.generate(gs, opponent)
        assert items == []

    def test_total_generated(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
    ) -> None:
        gen.generate(game_stats, opponent)
        assert gen.total_generated == 1

    def test_reset(
        self,
        gen: ScoutingFeedbackGenerator,
        game_stats: GameStats,
        opponent: OpponentProfile,
    ) -> None:
        gen.generate(game_stats, opponent)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: ScoutingFeedbackGenerator) -> None:
        assert "ScoutingFeedbackGenerator" in repr(gen)
