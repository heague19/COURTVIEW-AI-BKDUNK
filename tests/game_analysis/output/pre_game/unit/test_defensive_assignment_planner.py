# -*- coding: utf-8 -*-
"""DefensiveAssignmentPlanner 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.pre_game.defensive_assignment_planner import (
    DefensiveAssignmentPlanner,
    DefensiveAssignmentPlannerConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def planner() -> DefensiveAssignmentPlanner:
    return DefensiveAssignmentPlanner()


@pytest.fixture
def small_planner() -> DefensiveAssignmentPlanner:
    return DefensiveAssignmentPlanner(
        DefensiveAssignmentPlannerConfig(
            max_assignments=2, max_switch_rules=2, max_double_team_triggers=1,
        ),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, planner: DefensiveAssignmentPlanner) -> None:
        assert planner.total_plans == 0

    def test_name(self, planner: DefensiveAssignmentPlanner) -> None:
        assert planner.name == "DefensiveAssignmentPlanner"

    def test_repr(self, planner: DefensiveAssignmentPlanner) -> None:
        assert "DefensiveAssignmentPlanner" in repr(planner)


# =============================================================================
# 플랜 생성
# =============================================================================

class TestCreatePlan:
    def test_create(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert pid is not None
        assert planner.total_plans == 1

    def test_create_max(self, small_planner: DefensiveAssignmentPlanner) -> None:
        small_planner.create_plan()
        small_planner.create_plan()
        assert small_planner.create_plan() is None


# =============================================================================
# 매치업 배정
# =============================================================================

class TestMatchup:
    def test_assign(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.assign_matchup(pid, 10, 23)
        plan = planner.get_plan(pid)
        assert plan.assignments[10] == 23

    def test_assign_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.assign_matchup(uuid4(), 10, 23)

    def test_assign_override(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        planner.assign_matchup(pid, 10, 23)
        planner.assign_matchup(pid, 10, 30)
        plan = planner.get_plan(pid)
        assert plan.assignments[10] == 30

    def test_backup_assignment(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.set_backup_assignment(pid, 10, 99)
        plan = planner.get_plan(pid)
        assert plan.backup_assignments[10] == 99

    def test_backup_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.set_backup_assignment(uuid4(), 10, 99)

    def test_get_matchup_for_player(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        planner.assign_matchup(pid, 10, 23)
        assert planner.get_matchup_for_player(pid, 10) == 23
        assert planner.get_matchup_for_player(pid, 99) is None


# =============================================================================
# 스위치 규칙
# =============================================================================

class TestSwitchRule:
    def test_add(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.add_switch_rule(pid, "ball_screen", "switch", "guard_on_guard")
        summary = planner.get_plan_summary(pid)
        assert summary["switch_rules"] == 1

    def test_add_max(self, small_planner: DefensiveAssignmentPlanner) -> None:
        pid = small_planner.create_plan()
        small_planner.add_switch_rule(pid, "bs1", "switch")
        small_planner.add_switch_rule(pid, "bs2", "hedge")
        assert not small_planner.add_switch_rule(pid, "bs3", "drop")

    def test_add_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.add_switch_rule(uuid4(), "x", "y")


# =============================================================================
# 더블팀 트리거
# =============================================================================

class TestDoubleTeam:
    def test_add(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.add_double_team_trigger(pid, 23, "post_entry", "weak_side_wing")
        summary = planner.get_plan_summary(pid)
        assert summary["double_team_triggers"] == 1

    def test_add_max(self, small_planner: DefensiveAssignmentPlanner) -> None:
        pid = small_planner.create_plan()
        small_planner.add_double_team_trigger(pid, 23, "post")
        assert not small_planner.add_double_team_trigger(pid, 30, "drive")

    def test_add_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.add_double_team_trigger(uuid4(), 1, "x")


# =============================================================================
# 존 수비
# =============================================================================

class TestZoneResponsibility:
    def test_set_zone(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.set_zone_responsibility(pid, 10, "paint")
        plan = planner.get_plan(pid)
        assert plan.zone_responsibilities[10] == "paint"

    def test_set_zone_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.set_zone_responsibility(uuid4(), 10, "paint")

    def test_zone_summary(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        planner.set_zone_responsibility(pid, 10, "paint")
        planner.set_zone_responsibility(pid, 23, "wing")
        summary = planner.get_plan_summary(pid)
        assert summary["zone_responsibilities"] == 2


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_plan_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert planner.get_plan(uuid4()) is None

    def test_get_summary_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert planner.get_plan_summary(uuid4()) is None

    def test_matchup_nonexistent_plan(self, planner: DefensiveAssignmentPlanner) -> None:
        assert planner.get_matchup_for_player(uuid4(), 10) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        assert planner.delete_plan(pid)
        assert planner.total_plans == 0

    def test_delete_nonexistent(self, planner: DefensiveAssignmentPlanner) -> None:
        assert not planner.delete_plan(uuid4())

    def test_get_stats(self, planner: DefensiveAssignmentPlanner) -> None:
        pid = planner.create_plan()
        planner.assign_matchup(pid, 10, 23)
        planner.assign_matchup(pid, 5, 30)
        stats = planner.get_stats()
        assert stats["total_plans"] == 1
        assert stats["total_matchups"] == 2

    def test_reset(self, planner: DefensiveAssignmentPlanner) -> None:
        planner.create_plan()
        planner.reset()
        assert planner.total_plans == 0
