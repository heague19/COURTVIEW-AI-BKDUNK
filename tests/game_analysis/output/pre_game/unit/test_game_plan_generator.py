# -*- coding: utf-8 -*-
"""GamePlanGenerator 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.pre_game.game_plan_generator import (
    GamePlanGenerator,
    GamePlanGeneratorConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def gen() -> GamePlanGenerator:
    return GamePlanGenerator()


@pytest.fixture
def small_gen() -> GamePlanGenerator:
    return GamePlanGenerator(
        GamePlanGeneratorConfig(max_plans=2, max_strategies_per_category=2),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, gen: GamePlanGenerator) -> None:
        assert gen.total_plans == 0

    def test_name(self, gen: GamePlanGenerator) -> None:
        assert gen.name == "GamePlanGenerator"

    def test_repr(self, gen: GamePlanGenerator) -> None:
        assert "GamePlanGenerator" in repr(gen)


# =============================================================================
# 플랜 생성
# =============================================================================

class TestCreatePlan:
    def test_create_returns_uuid(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP_001", "2026-03-30")
        assert pid is not None
        assert gen.total_plans == 1

    def test_create_max(self, small_gen: GamePlanGenerator) -> None:
        small_gen.create_plan("A", "2026-03-30")
        small_gen.create_plan("B", "2026-03-31")
        assert small_gen.create_plan("C", "2026-04-01") is None

    def test_plan_details(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP_001", "2026-03-30")
        plan = gen.get_plan(pid)
        assert plan.opponent_id == "OPP_001"
        assert plan.game_date == "2026-03-30"


# =============================================================================
# 전략 추가
# =============================================================================

class TestAddStrategy:
    def test_add_offensive(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.add_offensive_strategy(pid, "high_pnr", 1, 1.15)
        summary = gen.get_plan_summary(pid)
        assert summary["offensive_strategies"] == 1

    def test_add_defensive(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.add_defensive_strategy(pid, "drop_coverage", 2)
        summary = gen.get_plan_summary(pid)
        assert summary["defensive_strategies"] == 1

    def test_add_transition(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.add_transition_strategy(pid, "push_pace", 1, 1.2)
        summary = gen.get_plan_summary(pid)
        assert summary["transition_strategies"] == 1

    def test_add_special(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.add_special_situation_strategy(pid, "inbound_play_a", 1)
        summary = gen.get_plan_summary(pid)
        assert summary["special_situations"] == 1

    def test_add_strategy_max(self, small_gen: GamePlanGenerator) -> None:
        pid = small_gen.create_plan("OPP", "2026-03-30")
        small_gen.add_offensive_strategy(pid, "s1", 1)
        small_gen.add_offensive_strategy(pid, "s2", 2)
        assert not small_gen.add_offensive_strategy(pid, "s3", 3)

    def test_add_strategy_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert not gen.add_offensive_strategy(uuid4(), "x", 1)

    def test_strategy_expected_ppp(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        gen.add_offensive_strategy(pid, "iso", 1, 0.95)
        plan = gen.get_plan(pid)
        assert plan.offensive_strategies[0].expected_ppp == 0.95


# =============================================================================
# 슛존 / 플레이 유형
# =============================================================================

class TestShotZoneAndPlayType:
    def test_set_shot_zone_target(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.set_shot_zone_target(pid, "paint", 35.0)
        plan = gen.get_plan(pid)
        assert plan.shot_zone_targets["paint"] == 35.0

    def test_set_shot_zone_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert not gen.set_shot_zone_target(uuid4(), "paint", 30.0)

    def test_add_priority_play_type(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.add_priority_play_type(pid, "pick_and_roll")
        plan = gen.get_plan(pid)
        assert "pick_and_roll" in plan.priority_play_types

    def test_add_duplicate_play_type(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        gen.add_priority_play_type(pid, "iso")
        gen.add_priority_play_type(pid, "iso")
        plan = gen.get_plan(pid)
        assert plan.priority_play_types.count("iso") == 1

    def test_add_play_type_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert not gen.add_priority_play_type(uuid4(), "x")


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_plan_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert gen.get_plan(uuid4()) is None

    def test_get_plan_summary_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert gen.get_plan_summary(uuid4()) is None

    def test_get_plans_for_opponent(self, gen: GamePlanGenerator) -> None:
        gen.create_plan("OPP_A", "2026-03-30")
        gen.create_plan("OPP_A", "2026-03-31")
        gen.create_plan("OPP_B", "2026-04-01")
        assert len(gen.get_plans_for_opponent("OPP_A")) == 2
        assert len(gen.get_plans_for_opponent("OPP_B")) == 1
        assert len(gen.get_plans_for_opponent("OPP_C")) == 0


# =============================================================================
# 삭제
# =============================================================================

class TestDelete:
    def test_delete(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        assert gen.delete_plan(pid)
        assert gen.total_plans == 0

    def test_delete_nonexistent(self, gen: GamePlanGenerator) -> None:
        assert not gen.delete_plan(uuid4())


# =============================================================================
# 유틸리티
# =============================================================================

class TestUtility:
    def test_get_stats(self, gen: GamePlanGenerator) -> None:
        pid = gen.create_plan("OPP", "2026-03-30")
        gen.add_offensive_strategy(pid, "s1", 1)
        gen.add_defensive_strategy(pid, "s2", 2)
        stats = gen.get_stats()
        assert stats["total_plans"] == 1
        assert stats["total_strategies"] == 2

    def test_reset(self, gen: GamePlanGenerator) -> None:
        gen.create_plan("OPP", "2026-03-30")
        gen.reset()
        assert gen.total_plans == 0
