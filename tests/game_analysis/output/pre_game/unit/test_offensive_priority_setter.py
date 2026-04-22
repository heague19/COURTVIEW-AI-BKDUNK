# -*- coding: utf-8 -*-
"""OffensivePrioritySetter 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.pre_game.offensive_priority_setter import (
    OffensivePrioritySetter,
    OffensivePrioritySetterConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def setter() -> OffensivePrioritySetter:
    return OffensivePrioritySetter()


@pytest.fixture
def small_setter() -> OffensivePrioritySetter:
    return OffensivePrioritySetter(
        OffensivePrioritySetterConfig(
            max_priority_sets=2, max_player_roles=3, max_exploitation_points=2,
        ),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, setter: OffensivePrioritySetter) -> None:
        assert setter.total_sets == 0

    def test_name(self, setter: OffensivePrioritySetter) -> None:
        assert setter.name == "OffensivePrioritySetter"

    def test_repr(self, setter: OffensivePrioritySetter) -> None:
        assert "OffensivePrioritySetter" in repr(setter)


# =============================================================================
# 세트 생성
# =============================================================================

class TestCreateSet:
    def test_create(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP_001")
        assert sid is not None
        assert setter.total_sets == 1

    def test_create_max(self, small_setter: OffensivePrioritySetter) -> None:
        small_setter.create_priority_set("A")
        small_setter.create_priority_set("B")
        assert small_setter.create_priority_set("C") is None


# =============================================================================
# 선수 역할
# =============================================================================

class TestPlayerRole:
    def test_add_role(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        assert setter.add_player_role(sid, 10, "primary_scorer", 1, "에이스")
        roles = setter.get_player_roles(sid)
        assert len(roles) == 1
        assert roles[0]["role"] == "primary_scorer"
        assert roles[0]["priority"] == 1

    def test_add_role_max(self, small_setter: OffensivePrioritySetter) -> None:
        sid = small_setter.create_priority_set("OPP")
        for i in range(3):
            small_setter.add_player_role(sid, i, "scorer")
        assert not small_setter.add_player_role(sid, 99, "spacer")

    def test_add_role_nonexistent(self, setter: OffensivePrioritySetter) -> None:
        assert not setter.add_player_role(uuid4(), 10, "x")

    def test_priority_clamped(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_player_role(sid, 10, "scorer", priority=0)
        setter.add_player_role(sid, 20, "spacer", priority=10)
        roles = setter.get_player_roles(sid)
        priorities = [r["priority"] for r in roles]
        assert 1 in priorities
        assert 5 in priorities

    def test_sorted_by_priority(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_player_role(sid, 10, "spacer", 4)
        setter.add_player_role(sid, 23, "scorer", 1)
        setter.add_player_role(sid, 5, "facilitator", 2)
        roles = setter.get_player_roles(sid)
        assert roles[0]["priority"] == 1
        assert roles[-1]["priority"] == 4


# =============================================================================
# 플레이 유형 우선순위
# =============================================================================

class TestPlayTypePriority:
    def test_add(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        assert setter.add_play_type_priority(sid, "pnr", 1, 1.15)
        rankings = setter.get_play_type_rankings(sid)
        assert len(rankings) == 1
        assert rankings[0]["play_type"] == "pnr"

    def test_add_nonexistent(self, setter: OffensivePrioritySetter) -> None:
        assert not setter.add_play_type_priority(uuid4(), "x", 1)

    def test_sorted_by_priority(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_play_type_priority(sid, "iso", 3, 0.9)
        setter.add_play_type_priority(sid, "pnr", 1, 1.1)
        setter.add_play_type_priority(sid, "post", 2, 1.0)
        rankings = setter.get_play_type_rankings(sid)
        assert rankings[0]["play_type"] == "pnr"
        assert rankings[-1]["play_type"] == "iso"


# =============================================================================
# 약점 공략
# =============================================================================

class TestExploitation:
    def test_add(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        ok = setter.add_exploitation_point(
            sid, "slow_closeout", 23, "spot_up_three", 1,
        )
        assert ok
        eps = setter.get_exploitation_points(sid)
        assert len(eps) == 1
        assert eps[0]["weakness"] == "slow_closeout"

    def test_add_max(self, small_setter: OffensivePrioritySetter) -> None:
        sid = small_setter.create_priority_set("OPP")
        small_setter.add_exploitation_point(sid, "w1", 1, "s1")
        small_setter.add_exploitation_point(sid, "w2", 2, "s2")
        assert not small_setter.add_exploitation_point(sid, "w3", 3, "s3")

    def test_add_nonexistent(self, setter: OffensivePrioritySetter) -> None:
        assert not setter.add_exploitation_point(uuid4(), "w", 1, "s")

    def test_sorted_by_priority(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_exploitation_point(sid, "w1", 1, "s1", 3)
        setter.add_exploitation_point(sid, "w2", 2, "s2", 1)
        eps = setter.get_exploitation_points(sid)
        assert eps[0]["priority"] == 1


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_summary(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_player_role(sid, 10, "scorer")
        setter.add_play_type_priority(sid, "pnr", 1)
        setter.add_exploitation_point(sid, "w", 1, "s")
        summary = setter.get_set_summary(sid)
        assert summary["player_roles"] == 1
        assert summary["play_type_priorities"] == 1
        assert summary["exploitation_points"] == 1

    def test_summary_nonexistent(self, setter: OffensivePrioritySetter) -> None:
        assert setter.get_set_summary(uuid4()) is None

    def test_roles_empty(self, setter: OffensivePrioritySetter) -> None:
        assert setter.get_player_roles(uuid4()) == []

    def test_rankings_empty(self, setter: OffensivePrioritySetter) -> None:
        assert setter.get_play_type_rankings(uuid4()) == []

    def test_exploitation_empty(self, setter: OffensivePrioritySetter) -> None:
        assert setter.get_exploitation_points(uuid4()) == []


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        assert setter.delete_set(sid)
        assert setter.total_sets == 0

    def test_delete_nonexistent(self, setter: OffensivePrioritySetter) -> None:
        assert not setter.delete_set(uuid4())

    def test_get_stats(self, setter: OffensivePrioritySetter) -> None:
        sid = setter.create_priority_set("OPP")
        setter.add_player_role(sid, 10, "scorer")
        stats = setter.get_stats()
        assert stats["total_sets"] == 1
        assert stats["total_player_roles"] == 1

    def test_reset(self, setter: OffensivePrioritySetter) -> None:
        setter.create_priority_set("OPP")
        setter.reset()
        assert setter.total_sets == 0
