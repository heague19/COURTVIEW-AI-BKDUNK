# -*- coding: utf-8 -*-
"""GamePlanExecutionTracker 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from game_analysis.output.pre_game.game_plan_execution_tracker import (
    GamePlanExecutionTracker,
    GamePlanExecutionTrackerConfig,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tracker() -> GamePlanExecutionTracker:
    return GamePlanExecutionTracker()


@pytest.fixture
def small_tracker() -> GamePlanExecutionTracker:
    return GamePlanExecutionTracker(
        GamePlanExecutionTrackerConfig(max_results=2, max_strategies_per_result=3),
    )


# =============================================================================
# 초기화
# =============================================================================

class TestInit:
    def test_default_init(self, tracker: GamePlanExecutionTracker) -> None:
        assert tracker.total_results == 0

    def test_name(self, tracker: GamePlanExecutionTracker) -> None:
        assert tracker.name == "GamePlanExecutionTracker"

    def test_repr(self, tracker: GamePlanExecutionTracker) -> None:
        assert "GamePlanExecutionTracker" in repr(tracker)


# =============================================================================
# 추적 생성
# =============================================================================

class TestCreateTracking:
    def test_create_returns_uuid(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        assert rid is not None
        assert tracker.total_results == 1

    def test_create_with_plan_id(self, tracker: GamePlanExecutionTracker) -> None:
        pid = uuid4()
        rid = tracker.create_tracking(plan_id=pid)
        assert rid == pid

    def test_create_max(self, small_tracker: GamePlanExecutionTracker) -> None:
        small_tracker.create_tracking()
        small_tracker.create_tracking()
        assert small_tracker.create_tracking() is None


# =============================================================================
# 전략 실행 기록
# =============================================================================

class TestRecordExecution:
    def test_record(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        ok = tracker.record_strategy_execution(rid, "high_pnr", True, 0.35, 1.12)
        assert ok
        res = tracker.get_result(rid)
        assert len(res.strategy_execution) == 1
        assert res.strategy_execution[0].executed is True
        assert res.strategy_execution[0].frequency == 0.35

    def test_record_max(self, small_tracker: GamePlanExecutionTracker) -> None:
        rid = small_tracker.create_tracking()
        for i in range(3):
            small_tracker.record_strategy_execution(rid, f"s{i}", True)
        assert not small_tracker.record_strategy_execution(rid, "s3", True)

    def test_record_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert not tracker.record_strategy_execution(uuid4(), "x", True)

    def test_frequency_clamped(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_strategy_execution(rid, "s1", True, frequency=1.5)
        tracker.record_strategy_execution(rid, "s2", True, frequency=-0.5)
        res = tracker.get_result(rid)
        assert res.strategy_execution[0].frequency == 1.0
        assert res.strategy_execution[1].frequency == 0.0


# =============================================================================
# 이탈 기록
# =============================================================================

class TestDeviation:
    def test_record_deviation(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        ok = tracker.record_deviation(rid, "zone_defense", "abandoned", 0.6)
        assert ok
        res = tracker.get_result(rid)
        assert len(res.deviations) == 1
        assert res.deviations[0].deviation_type == "abandoned"

    def test_impact_clamped(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_deviation(rid, "s1", "x", impact=2.0)
        res = tracker.get_result(rid)
        assert res.deviations[0].impact == 1.0

    def test_deviation_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert not tracker.record_deviation(uuid4(), "x", "y")


# =============================================================================
# 쿼터별 순수율
# =============================================================================

class TestQuarterAdherence:
    def test_add_quarter(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        assert tracker.add_quarter_adherence(rid, 75.0)
        assert tracker.add_quarter_adherence(rid, 80.0)
        res = tracker.get_result(rid)
        assert len(res.quarter_trends) == 2

    def test_adherence_clamped(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.add_quarter_adherence(rid, 120.0)
        res = tracker.get_result(rid)
        assert res.quarter_trends[0] == 100.0

    def test_quarter_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert not tracker.add_quarter_adherence(uuid4(), 50.0)


# =============================================================================
# 순수율 계산
# =============================================================================

class TestOverallAdherence:
    def test_calculate(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_strategy_execution(rid, "s1", True)
        tracker.record_strategy_execution(rid, "s2", False)
        tracker.record_strategy_execution(rid, "s3", True)
        tracker.record_strategy_execution(rid, "s4", True)
        rate = tracker.calculate_overall_adherence(rid)
        assert abs(rate - 75.0) < 1e-6

    def test_calculate_empty(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        assert tracker.calculate_overall_adherence(rid) == 0.0

    def test_calculate_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert tracker.calculate_overall_adherence(uuid4()) == 0.0

    def test_calculate_all_executed(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_strategy_execution(rid, "s1", True)
        tracker.record_strategy_execution(rid, "s2", True)
        assert abs(tracker.calculate_overall_adherence(rid) - 100.0) < 1e-6


# =============================================================================
# PPP 비교
# =============================================================================

class TestPPP:
    def test_set_ppp(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        assert tracker.set_plan_vs_actual_ppp(rid, "iso", 0.88)
        res = tracker.get_result(rid)
        assert res.plan_vs_actual_ppp["iso"] == 0.88

    def test_set_ppp_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert not tracker.set_plan_vs_actual_ppp(uuid4(), "x", 1.0)


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_result_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert tracker.get_result(uuid4()) is None

    def test_get_result_summary(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_strategy_execution(rid, "s1", True)
        tracker.record_deviation(rid, "s2", "abandoned")
        tracker.add_quarter_adherence(rid, 80.0)
        summary = tracker.get_result_summary(rid)
        assert summary["total_strategies"] == 1
        assert summary["executed_strategies"] == 1
        assert summary["deviations"] == 1
        assert summary["quarters_tracked"] == 1

    def test_summary_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert tracker.get_result_summary(uuid4()) is None


# =============================================================================
# 삭제 / 유틸리티
# =============================================================================

class TestDeleteAndUtility:
    def test_delete(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        assert tracker.delete_result(rid)
        assert tracker.total_results == 0

    def test_delete_nonexistent(self, tracker: GamePlanExecutionTracker) -> None:
        assert not tracker.delete_result(uuid4())

    def test_get_stats(self, tracker: GamePlanExecutionTracker) -> None:
        rid = tracker.create_tracking()
        tracker.record_strategy_execution(rid, "s1", True)
        stats = tracker.get_stats()
        assert stats["total_results"] == 1
        assert stats["total_strategies_tracked"] == 1

    def test_reset(self, tracker: GamePlanExecutionTracker) -> None:
        tracker.create_tracking()
        tracker.reset()
        assert tracker.total_results == 0
