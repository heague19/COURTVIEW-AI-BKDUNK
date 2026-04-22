# -*- coding: utf-8 -*-
"""EPVModel 단위 테스트 — 14 tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from game_analysis.stats.predictive_models.expected_possession_value import (
    EPVModel,
    EPVConfig,
)


class TestEPVModel:
    """EPVModel 단위 테스트."""

    def test_init_default(self):
        m = EPVModel()
        assert m.name == "EPVModel"
        assert m.current_epv == 0.0

    def test_calculate_shot_only(self):
        """슛 옵션만 있을 때."""
        m = EPVModel()
        result = m.calculate_epv(
            shot_probability=0.50,
            shot_expected_points=2.0,
        )
        # shot_epv = 0.50 * 2.0 * 1.0 = 1.0
        assert result.shot_option_epv == pytest.approx(1.0, abs=0.01)
        assert result.optimal_action == "shoot"

    def test_calculate_three_pointer(self):
        """3점 슛 → 높은 EPV."""
        m = EPVModel()
        result = m.calculate_epv(
            shot_probability=0.36,
            shot_expected_points=3.0,
        )
        # 0.36 * 3.0 = 1.08
        assert result.shot_option_epv == pytest.approx(1.08, abs=0.01)

    def test_drive_option(self):
        m = EPVModel()
        result = m.calculate_epv(
            shot_probability=0.30,
            shot_expected_points=2.0,
            drive_probability=0.60,
            drive_expected_points=2.0,
        )
        # drive_epv = 0.60 * 2.0 * 0.90 = 1.08
        # shot_epv = 0.30 * 2.0 * 1.0 = 0.60
        assert result.drive_option_epv > result.shot_option_epv
        assert result.optimal_action == "drive"

    def test_pass_option_best(self):
        """패스가 최적 옵션일 때."""
        m = EPVModel()
        result = m.calculate_epv(
            shot_probability=0.30,
            shot_expected_points=2.0,
            pass_options=[
                {"target_tracking_id": 7, "probability": 0.55, "expected_points": 3.0},
            ],
        )
        # pass_epv = 0.55 * 3.0 * 0.95 = 1.5675
        assert result.optimal_action == "pass_to_7"
        assert len(result.pass_options) == 1

    def test_early_clock_bonus(self):
        """빠른 공격 (0~8초) → EPV 보너스."""
        m = EPVModel()
        early = m.calculate_epv(
            shot_probability=0.50,
            shot_expected_points=2.0,
            possession_elapsed_sec=3.0,
        )
        late = m.calculate_epv(
            shot_probability=0.50,
            shot_expected_points=2.0,
            possession_elapsed_sec=20.0,
        )
        assert early.current_epv > late.current_epv

    def test_record_possession_outcome(self):
        m = EPVModel()
        pid = uuid4()
        quality = m.record_possession_outcome(
            possession_id=pid,
            actual_points=2.0,
            initial_epv=1.0,
            final_epv=1.2,
            elapsed_sec=12.0,
        )
        # (2.0 - 1.08) / 1.08 ≈ 0.852
        assert quality > 0  # 리그 평균 이상

    def test_record_zero_points(self):
        m = EPVModel()
        quality = m.record_possession_outcome(
            possession_id=uuid4(),
            actual_points=0.0,
            initial_epv=1.0,
            final_epv=0.5,
            elapsed_sec=20.0,
        )
        assert quality < 0  # 리그 평균 이하

    def test_ppp_grade(self):
        m = EPVModel()
        assert m.get_ppp_grade(1.25) == "elite"
        assert m.get_ppp_grade(1.12) == "good"
        assert m.get_ppp_grade(1.05) == "average"
        assert m.get_ppp_grade(0.92) == "poor"
        assert m.get_ppp_grade(0.80) == "very_poor"

    def test_team_epv_average(self):
        m = EPVModel()
        for i in range(5):
            m.record_possession_outcome(
                possession_id=uuid4(),
                actual_points=float(i),
                initial_epv=1.0,
                final_epv=1.0,
                elapsed_sec=10.0,
            )
        avg = m.get_team_epv_average()
        # 평균 = (0+1+2+3+4)/5 = 2.0
        assert avg == pytest.approx(2.0, abs=0.01)

    def test_get_stats(self):
        m = EPVModel()
        m.record_possession_outcome(
            possession_id=uuid4(),
            actual_points=1.5,
            initial_epv=1.0,
            final_epv=1.0,
            elapsed_sec=10.0,
        )
        stats = m.get_stats()
        assert stats["total_possessions"] == 1
        assert "average_epv" in stats
        assert "ppp_grade" in stats

    def test_memory_guard(self):
        m = EPVModel(config=EPVConfig(max_possession_cache=5))
        for i in range(8):
            m.record_possession_outcome(
                possession_id=uuid4(),
                actual_points=1.0,
                initial_epv=1.0,
                final_epv=1.0,
                elapsed_sec=10.0,
            )
        stats = m.get_stats()
        assert stats["history_size"] <= 8

    def test_reset(self):
        m = EPVModel()
        m.record_possession_outcome(
            possession_id=uuid4(),
            actual_points=2.0,
            initial_epv=1.0,
            final_epv=1.0,
            elapsed_sec=10.0,
        )
        m.reset()
        assert m.current_epv == 0.0
        assert m.get_stats()["total_possessions"] == 0
