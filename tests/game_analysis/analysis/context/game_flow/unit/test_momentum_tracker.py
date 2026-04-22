# -*- coding: utf-8 -*-
"""MomentumTracker 단위 테스트."""
from __future__ import annotations
import pytest
from game_analysis.analysis.context.game_flow.momentum_tracker import MomentumTracker, MomentumTrackerConfig
from shared.dto.tactical_dto import MomentumState

class TestMomentumInit:
    def test_default(self) -> None:
        t = MomentumTracker()
        assert t.name == "MomentumTracker"
        assert t.current_state == MomentumState.NEUTRAL
        assert t.total_runs == 0

class TestRecordPossession:
    def test_home_scoring(self) -> None:
        t = MomentumTracker()
        # 연속 홈 득점 → 모멘텀 홈으로 이동
        for _ in range(5):
            t.record_possession(home_points=3, away_points=0)
        state = t.current_state
        assert state in (MomentumState.SLIGHT_HOME, MomentumState.STRONG_HOME)

    def test_away_scoring(self) -> None:
        t = MomentumTracker()
        for _ in range(5):
            t.record_possession(home_points=0, away_points=3)
        state = t.current_state
        assert state in (MomentumState.SLIGHT_AWAY, MomentumState.STRONG_AWAY)

    def test_neutral_balanced(self) -> None:
        t = MomentumTracker()
        t.record_possession(home_points=2, away_points=2)
        assert t.current_state == MomentumState.NEUTRAL

class TestScoringRuns:
    def test_home_run_detected(self) -> None:
        t = MomentumTracker()
        # 홈 6점 연속 무응답 + 상대 3회 무득점
        t.record_possession(home_points=3, away_points=0)
        t.record_possession(home_points=0, away_points=0)
        t.record_possession(home_points=3, away_points=0)
        runs = t.get_scoring_runs()
        assert len(runs) >= 1
        assert runs[-1].team_id == "home"

class TestMomentumShifts:
    def test_shift_recorded(self) -> None:
        t = MomentumTracker()
        # 홈 강세 구간
        for _ in range(5):
            t.record_possession(home_points=3, away_points=0)
        # 원정 역전
        for _ in range(10):
            t.record_possession(home_points=0, away_points=3)
        shifts = t.get_momentum_shifts()
        assert len(shifts) >= 1

class TestTimeoutReset:
    def test_timeout_reduces_momentum(self) -> None:
        t = MomentumTracker()
        for _ in range(5):
            t.record_possession(home_points=3, away_points=0)
        stats_before = t.get_stats()
        score_before = stats_before["momentum_score"]
        t.apply_timeout_reset()
        stats_after = t.get_stats()
        assert abs(stats_after["momentum_score"]) < abs(score_before)  # type: ignore[arg-type]

class TestResetRepr:
    def test_reset(self) -> None:
        t = MomentumTracker()
        t.record_possession(home_points=3, away_points=0)
        t.reset()
        assert t.current_state == MomentumState.NEUTRAL
        assert t.total_runs == 0

    def test_repr(self) -> None:
        t = MomentumTracker()
        assert "MomentumTracker" in repr(t)
