# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: substitution_manager.py

Cadence: EVENT (<10ms)
목표: substitute() 1회 평균 <10ms, 출전시간 조회 <5ms
"""

from __future__ import annotations

import time
import statistics
import pytest

from game_analysis.game_state.game_management.substitution_manager import (
    SubstitutionManager,
    SubstitutionManagerConfig,
)


class TestSubstitutionManagerPerf:
    """substitution_manager 이벤트 처리 성능 검증."""

    EVENT_BUDGET_SEC: float = 0.010
    ITERATIONS: int = 200

    def _setup(self) -> SubstitutionManager:
        sm = SubstitutionManager()
        sm.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        sm.set_starting_lineup(
            "away", [11, 12, 13, 14, 15],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        return sm

    def test_substitute_under_10ms(self) -> None:
        """substitute() 평균 < 10ms."""
        durations: list[float] = []
        bench_home = list(range(6, 16))  # 벤치 10명
        for i in range(self.ITERATIONS):
            sm = self._setup()
            p_out = (i % 5) + 1
            p_in = bench_home[i % len(bench_home)]
            t0 = time.perf_counter()
            sm.substitute(
                "home", player_in=p_in, player_out=p_out,
                frame=100 + i, timestamp=120.0 + i,
                game_clock="08:00", quarter=1,
            )
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC, (
            f"substitute() 평균 {avg*1000:.3f}ms > 10ms"
        )

    def test_playing_time_query_under_5ms(self) -> None:
        """get_total_playing_time() < 5ms (교체 50회 후)."""
        sm = self._setup()
        # 50회 교체 시뮬레이션
        on_court = [1, 2, 3, 4, 5]
        bench = list(range(6, 16))
        for i in range(50):
            p_out = on_court[i % 5]
            p_in = bench[i % len(bench)]
            sm.substitute(
                "home", player_in=p_in, player_out=p_out,
                frame=100 * (i + 1), timestamp=60.0 * (i + 1),
                game_clock=f"{9 - (i % 10)}:00", quarter=((i // 10) % 4) + 1,
            )
            on_court[i % 5] = p_in

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            sm.get_total_playing_time(1)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_total_playing_time() 평균 {avg*1000:.3f}ms > 5ms"

    def test_get_stints_under_5ms(self) -> None:
        """get_stints() 조회 < 5ms."""
        sm = self._setup()
        # 교체 왕복
        for i in range(10):
            sm.substitute(
                "home", player_in=6, player_out=5,
                frame=100 * (2 * i + 1), timestamp=60.0 * (2 * i + 1),
                game_clock="08:00", quarter=1,
            )
            sm.substitute(
                "home", player_in=5, player_out=6,
                frame=100 * (2 * i + 2), timestamp=60.0 * (2 * i + 2),
                game_clock="06:00", quarter=1,
            )

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            sm.get_stints(5)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_stints() 평균 {avg*1000:.3f}ms > 5ms"

    def test_substitution_history_under_5ms(self) -> None:
        """get_substitution_history() < 5ms (100건 후)."""
        sm = self._setup()
        on_court = [1, 2, 3, 4, 5]
        bench = list(range(6, 16))
        for i in range(100):
            p_out = on_court[i % 5]
            p_in = bench[i % len(bench)]
            sm.substitute(
                "home", player_in=p_in, player_out=p_out,
                frame=100 * (i + 1), timestamp=60.0 * (i + 1),
                game_clock=f"{9 - (i % 10)}:00", quarter=((i // 25) % 4) + 1,
            )
            on_court[i % 5] = p_in

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            sm.get_substitution_history()
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_substitution_history() 평균 {avg*1000:.3f}ms > 5ms"
