# -*- coding: utf-8 -*-
"""PreGameBriefingBuilder 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.scouting_dto import (
    DefensiveAssignment,
    GamePlan,
    HeadToHeadRecord,
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
)
from game_analysis.output.pre_game.pre_game_briefing_builder import (
    PreGameBriefingBuilder,
    PreGameBriefingBuilderConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def builder() -> PreGameBriefingBuilder:
    return PreGameBriefingBuilder()


@pytest.fixture
def small_builder() -> PreGameBriefingBuilder:
    return PreGameBriefingBuilder(
        PreGameBriefingBuilderConfig(max_briefings=2, max_key_matchups=2),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, builder: PreGameBriefingBuilder) -> None:
        assert builder.total_briefings == 0

    def test_name(self, builder: PreGameBriefingBuilder) -> None:
        assert builder.name == "PreGameBriefingBuilder"

    def test_repr(self, builder: PreGameBriefingBuilder) -> None:
        assert "PreGameBriefingBuilder" in repr(builder)


# =============================================================================
# 브리핑 생성
# =============================================================================

class TestCreateBriefing:
    def test_create(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert bid is not None
        assert builder.total_briefings == 1

    def test_create_max(self, small_builder: PreGameBriefingBuilder) -> None:
        small_builder.create_briefing()
        small_builder.create_briefing()
        assert small_builder.create_briefing() is None


# =============================================================================
# 구성 요소 설정
# =============================================================================

class TestComponents:
    def test_set_opponent_profile(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        prof = OpponentProfile(team_id="T001", team_name="Eagles")
        assert builder.set_opponent_profile(bid, prof)
        b = builder.get_briefing(bid)
        assert b.opponent_profile.team_name == "Eagles"

    def test_set_tendency_report(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_tendency_report(bid, TendencyReport())
        summary = builder.get_briefing_summary(bid)
        assert summary["has_tendency_report"] is True

    def test_set_weakness_report(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_weakness_report(bid, WeaknessReport())
        summary = builder.get_briefing_summary(bid)
        assert summary["has_weakness_report"] is True

    def test_set_head_to_head(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_head_to_head(bid, HeadToHeadRecord())
        summary = builder.get_briefing_summary(bid)
        assert summary["has_head_to_head"] is True

    def test_set_game_plan(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_game_plan(bid, GamePlan())
        summary = builder.get_briefing_summary(bid)
        assert summary["has_game_plan"] is True

    def test_set_defensive_assignment(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_defensive_assignment(bid, DefensiveAssignment())
        summary = builder.get_briefing_summary(bid)
        assert summary["has_defensive_assignment"] is True

    def test_set_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert not builder.set_opponent_profile(uuid4(), OpponentProfile())
        assert not builder.set_tendency_report(uuid4(), TendencyReport())
        assert not builder.set_weakness_report(uuid4(), WeaknessReport())
        assert not builder.set_head_to_head(uuid4(), HeadToHeadRecord())
        assert not builder.set_game_plan(uuid4(), GamePlan())
        assert not builder.set_defensive_assignment(uuid4(), DefensiveAssignment())


# =============================================================================
# 핵심 매치업
# =============================================================================

class TestKeyMatchup:
    def test_add(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.add_key_matchup(bid, "Guard A", "Guard X", 0.3)
        summary = builder.get_briefing_summary(bid)
        assert summary["key_matchups"] == 1

    def test_add_max(self, small_builder: PreGameBriefingBuilder) -> None:
        bid = small_builder.create_briefing()
        small_builder.add_key_matchup(bid, "A", "X")
        small_builder.add_key_matchup(bid, "B", "Y")
        assert not small_builder.add_key_matchup(bid, "C", "Z")

    def test_add_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert not builder.add_key_matchup(uuid4(), "A", "X")

    def test_advantage_clamped(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        builder.add_key_matchup(bid, "A", "X", 2.0)
        builder.add_key_matchup(bid, "B", "Y", -2.0)
        b = builder.get_briefing(bid)
        assert b.key_matchups[0].advantage_score == 1.0
        assert b.key_matchups[1].advantage_score == -1.0


# =============================================================================
# 요약
# =============================================================================

class TestSummary:
    def test_set_executive_summary(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.set_executive_summary(bid, "이글스 약점: 전환 수비 느림")
        b = builder.get_briefing(bid)
        assert "이글스" in b.executive_summary

    def test_set_summary_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert not builder.set_executive_summary(uuid4(), "x")


# =============================================================================
# 완성도
# =============================================================================

class TestCompleteness:
    def test_empty_completeness(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.get_completeness(bid) == 0.0

    def test_partial_completeness(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        builder.set_opponent_profile(bid, OpponentProfile())
        builder.set_game_plan(bid, GamePlan())
        builder.set_executive_summary(bid, "요약")
        # 3/7 = ~42.86%
        c = builder.get_completeness(bid)
        assert 42.0 < c < 43.0

    def test_full_completeness(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        builder.set_opponent_profile(bid, OpponentProfile())
        builder.set_tendency_report(bid, TendencyReport())
        builder.set_weakness_report(bid, WeaknessReport())
        builder.set_head_to_head(bid, HeadToHeadRecord())
        builder.set_game_plan(bid, GamePlan())
        builder.set_defensive_assignment(bid, DefensiveAssignment())
        builder.set_executive_summary(bid, "완전한 브리핑")
        assert abs(builder.get_completeness(bid) - 100.0) < 1e-6

    def test_completeness_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert builder.get_completeness(uuid4()) == 0.0


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_briefing_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert builder.get_briefing(uuid4()) is None

    def test_get_summary_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert builder.get_briefing_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, builder: PreGameBriefingBuilder) -> None:
        bid = builder.create_briefing()
        assert builder.delete_briefing(bid)
        assert builder.total_briefings == 0

    def test_delete_nonexistent(self, builder: PreGameBriefingBuilder) -> None:
        assert not builder.delete_briefing(uuid4())

    def test_get_stats(self, builder: PreGameBriefingBuilder) -> None:
        builder.create_briefing()
        stats = builder.get_stats()
        assert stats["total_briefings"] == 1

    def test_reset(self, builder: PreGameBriefingBuilder) -> None:
        builder.create_briefing()
        builder.reset()
        assert builder.total_briefings == 0
