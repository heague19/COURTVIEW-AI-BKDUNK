# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: foul_manager.py

Cadence: EVENT (<10ms)
목표: record_foul() 1회 평균 <10ms, 대량 파울 누적 안정성
"""

from __future__ import annotations

import time
import statistics
import pytest

from shared.constants.referee_rule_constants import RuleSet
from game_analysis.game_state.game_management.foul_manager import (
    FoulManager,
    FoulManagerConfig,
)


class TestFoulManagerPerf:
    """foul_manager 이벤트 처리 성능 검증."""

    EVENT_BUDGET_SEC: float = 0.010  # 10ms
    ITERATIONS: int = 500

    def test_record_foul_under_10ms(self) -> None:
        """record_foul() 평균 < 10ms."""
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA))
        durations: list[float] = []
        for i in range(self.ITERATIONS):
            pid = (i % 10) + 1
            t0 = time.perf_counter()
            fm.record_foul(
                team_id="home",
                player_tracking_id=pid,
                quarter=((i // 50) % 4) + 1,
                game_clock=f"{9 - (i % 10)}:00",
            )
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC, (
            f"record_foul() 평균 {avg*1000:.3f}ms > 10ms"
        )

    def test_get_foul_state_under_5ms(self) -> None:
        """get_foul_state() 조회 < 5ms."""
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.NBA))
        # 사전 데이터 축적
        for i in range(100):
            fm.record_foul(
                team_id="home",
                player_tracking_id=(i % 5) + 1,
                quarter=((i // 25) % 4) + 1,
                game_clock=f"{9 - (i % 10)}:00",
            )

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            fm.get_foul_state(team_id="home", quarter=2)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_foul_state() 평균 {avg*1000:.3f}ms > 5ms"

    def test_bonus_check_under_1ms(self) -> None:
        """get_bonus_status() < 1ms."""
        fm = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA))
        for i in range(20):
            fm.record_foul(
                team_id="home",
                player_tracking_id=(i % 5) + 1,
                quarter=1,
                game_clock=f"{9 - i}:00",
            )

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            fm.get_bonus_status("home", quarter=1)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.001, f"get_bonus_status() 평균 {avg*1000:.3f}ms > 1ms"

    def test_memory_guard_large_volume(self) -> None:
        """대량 파울(2000건) 기록 후 메모리 안정성."""
        fm = FoulManager()
        t0 = time.perf_counter()
        for i in range(2000):
            fm.record_foul(
                team_id="home" if i % 2 == 0 else "away",
                player_tracking_id=(i % 20) + 1,
                quarter=((i // 500) % 4) + 1,
                game_clock=f"{9 - (i % 10)}:00",
            )
        elapsed = time.perf_counter() - t0
        # 2000건 총 소요 < 5초
        assert elapsed < 5.0, f"2000건 파울 기록 {elapsed:.3f}s > 5.0s"
