# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: timeout_manager.py

Cadence: EVENT (<10ms)
목표: use_timeout() 1회 평균 <10ms
"""

from __future__ import annotations

import time
import statistics
import pytest

from shared.constants.referee_rule_constants import RuleSet
from game_analysis.game_state.game_management.timeout_manager import (
    TimeoutManager,
    TimeoutManagerConfig,
)


class TestTimeoutManagerPerf:
    """timeout_manager 이벤트 처리 성능 검증."""

    EVENT_BUDGET_SEC: float = 0.010
    ITERATIONS: int = 200

    def test_use_timeout_under_10ms(self) -> None:
        """use_timeout() 평균 < 10ms."""
        durations: list[float] = []
        for i in range(self.ITERATIONS):
            # 매번 새 인스턴스 (타임아웃 소진 방지)
            tm = TimeoutManager(
                TimeoutManagerConfig(rule_set=RuleSet.NBA),
                teams=["home"],
            )
            t0 = time.perf_counter()
            tm.use_timeout("home", quarter=1, game_clock=f"{10 - (i % 10)}:00")
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC, (
            f"use_timeout() 평균 {avg*1000:.3f}ms > 10ms"
        )

    def test_get_remaining_under_1ms(self) -> None:
        """get_remaining() < 1ms."""
        tm = TimeoutManager(
            TimeoutManagerConfig(rule_set=RuleSet.FIBA),
            teams=["home", "away"],
        )
        tm.use_timeout("home", quarter=1, game_clock="08:00")

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            tm.get_remaining("home", quarter=1)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.001, f"get_remaining() 평균 {avg*1000:.3f}ms > 1ms"

    def test_get_timeout_state_under_5ms(self) -> None:
        """get_timeout_state() < 5ms."""
        tm = TimeoutManager(
            TimeoutManagerConfig(rule_set=RuleSet.FIBA),
            teams=["home"],
        )
        tm.use_timeout("home", quarter=1, game_clock="08:00")
        tm.use_timeout("home", quarter=2, game_clock="07:00")

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            tm.get_timeout_state("home", quarter=2)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_timeout_state() 평균 {avg*1000:.3f}ms > 5ms"
