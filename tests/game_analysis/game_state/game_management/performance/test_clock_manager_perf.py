# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: clock_manager.py

Cadence: FRAME (<2ms/tick)
목표: tick() 1회 평균 <2ms, 1000회 연속 tick 안정성 확인
"""

from __future__ import annotations

import time
import statistics
import pytest

from shared.constants.game_management_constants import GameState
from game_analysis.game_state.game_management.clock_manager import (
    ClockManager,
    ClockManagerConfig,
)


# =============================================================================
# FRAME Cadence: tick() < 2ms
# =============================================================================

class TestClockManagerPerf:
    """clock_manager tick() 성능 검증."""

    FRAME_BUDGET_SEC: float = 0.002  # 2ms
    WARM_UP: int = 50
    ITERATIONS: int = 1000

    def _make_live_cm(self, fps: float = 30.0) -> ClockManager:
        cm = ClockManager(ClockManagerConfig(fps=fps))
        cm.start_game()
        cm.transition_to(GameState.LIVE)
        cm.set_possession("home")
        return cm

    def test_tick_under_2ms_average(self) -> None:
        """tick() 평균 호출 시간 < 2ms."""
        cm = self._make_live_cm()
        # 워밍업
        for _ in range(self.WARM_UP):
            cm.tick()

        cm2 = self._make_live_cm()
        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            cm2.tick()
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        p99 = sorted(durations)[int(self.ITERATIONS * 0.99)]
        assert avg < self.FRAME_BUDGET_SEC, (
            f"tick() 평균 {avg*1000:.3f}ms > 2ms 예산 초과"
        )
        # P99도 10ms 미만이어야 안정적
        assert p99 < 0.010, f"tick() P99 {p99*1000:.3f}ms > 10ms"

    def test_tick_1000_consecutive_stable(self) -> None:
        """1000회 연속 tick — 전체 소요 < 2초."""
        cm = self._make_live_cm(fps=60.0)
        t0 = time.perf_counter()
        for _ in range(1000):
            cm.tick()
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"1000 tick 소요 {elapsed:.3f}s > 2.0s"

    def test_state_transition_under_1ms(self) -> None:
        """상태 전이 1회 < 1ms."""
        cm = ClockManager()
        cm.start_game()
        durations: list[float] = []
        transitions = [
            GameState.LIVE, GameState.DEAD_BALL, GameState.LIVE,
            GameState.TIMEOUT, GameState.LIVE, GameState.PERIOD_BREAK,
        ]
        for target in transitions:
            t0 = time.perf_counter()
            cm.transition_to(target)
            durations.append(time.perf_counter() - t0)
        avg = statistics.mean(durations)
        assert avg < 0.001, f"상태 전이 평균 {avg*1000:.3f}ms > 1ms"

    def test_get_clock_state_under_1ms(self) -> None:
        """get_clock_state() 스냅샷 < 1ms."""
        cm = self._make_live_cm()
        for _ in range(100):
            cm.tick()

        durations: list[float] = []
        for _ in range(500):
            t0 = time.perf_counter()
            cm.get_clock_state()
            durations.append(time.perf_counter() - t0)
        avg = statistics.mean(durations)
        assert avg < 0.001, f"get_clock_state() 평균 {avg*1000:.3f}ms > 1ms"

    def test_full_quarter_simulation(self) -> None:
        """1쿼터 전체 시뮬레이션 (600초 / fps=30 = 18000 tick)."""
        cm = self._make_live_cm(fps=30.0)
        tick_count = 0
        t0 = time.perf_counter()
        while cm.game_clock_sec > 0 and tick_count < 20000:
            cm.tick()
            tick_count += 1
        elapsed = time.perf_counter() - t0
        avg_per_tick = elapsed / tick_count if tick_count else 0
        assert avg_per_tick < self.FRAME_BUDGET_SEC, (
            f"쿼터 시뮬레이션 평균 {avg_per_tick*1000:.3f}ms/tick > 2ms"
        )
