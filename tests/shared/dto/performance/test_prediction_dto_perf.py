# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_prediction_dto_perf.py

예측 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.prediction_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. dataclass 생성 ====================
def test_win_probability_creation(r: PerfResult) -> None:
    """WinProbability 생성 속도 (__post_init__ 포함)"""
    from shared.dto.prediction_dto import WinProbability

    def create():
        WinProbability(
            home_wp=65.0,
            leverage_index=1.5,
            frame_number=9000,
            game_clock="Q3 05:30",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("WinProbability 생성", elapsed, limit)
    else:
        r.fail("WinProbability 생성", elapsed, limit)


def test_epv_creation(r: PerfResult) -> None:
    """ExpectedPossessionValue 생성 속도"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    pid = uuid4()

    def create():
        ExpectedPossessionValue(
            current_epv=1.15,
            pass_options=[{"epv": 1.2}, {"epv": 0.9}],
            shot_option_epv=0.85,
            drive_option_epv=1.05,
            optimal_action="pass_to_3",
            possession_id=pid,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("EPV 생성", elapsed, limit)
    else:
        r.fail("EPV 생성", elapsed, limit)


def test_shot_quality_creation(r: PerfResult) -> None:
    """ShotQualityPrediction 생성 속도"""
    from shared.dto.prediction_dto import ShotQualityPrediction
    from shared.constants.game_rule_constants import CourtZone

    def create():
        ShotQualityPrediction(
            xfg_pct=45.0,
            shot_location=(12.5, 8.3),
            court_zone=CourtZone.MID_LEFT_WING,
            defender_distance_m=1.8,
            hand_contest=True,
            shot_type="mid_range",
            player_tracking_id=23,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ShotQualityPrediction 생성", elapsed, limit)
    else:
        r.fail("ShotQualityPrediction 생성", elapsed, limit)


def test_lineup_projection_creation(r: PerfResult) -> None:
    """LineupProjection 생성 속도"""
    from shared.dto.prediction_dto import LineupProjection

    def create():
        LineupProjection(
            lineup_players=[1, 3, 5, 7, 11],
            predicted_net_rating=8.5,
            predicted_offensive_rating=112.0,
            predicted_defensive_rating=103.5,
            sample_minutes=48.5,
            matchup_quality=0.7,
            fatigue_adjusted=True,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("LineupProjection 생성", elapsed, limit)
    else:
        r.fail("LineupProjection 생성", elapsed, limit)


def test_prediction_snapshot_creation(r: PerfResult) -> None:
    """PredictionSnapshot 생성 속도 (UUID 포함)"""
    from shared.dto.prediction_dto import PredictionSnapshot

    def create():
        PredictionSnapshot(
            frame_number=9000,
            timestamp=300.0,
            game_clock="Q3 05:00",
            quarter=3,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("PredictionSnapshot 생성", elapsed, limit)
    else:
        r.fail("PredictionSnapshot 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_epv_best_option_property(r: PerfResult) -> None:
    """EPV best_option_epv 프로퍼티 속도"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    epv = ExpectedPossessionValue(
        shot_option_epv=0.85,
        drive_option_epv=1.05,
        pass_options=[{"epv": 1.2}, {"epv": 0.9}, {"epv": 1.1}],
    )

    def access():
        _ = epv.best_option_epv

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("best_option_epv 프로퍼티", elapsed, limit)
    else:
        r.fail("best_option_epv 프로퍼티", elapsed, limit)


# ==================== 4. 대량 처리 ====================
def test_batch_wp_updates(r: PerfResult) -> None:
    """WinProbability 20개 배치 생성"""
    from shared.dto.prediction_dto import WinProbability

    def batch():
        for i in range(20):
            WinProbability(
                home_wp=40.0 + i,
                leverage_index=1.0 + i * 0.1,
                frame_number=i * 100,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("WinProbability×20", elapsed, limit)
    else:
        r.fail("WinProbability×20", elapsed, limit)


def test_full_prediction_snapshot(r: PerfResult) -> None:
    """풀 PredictionSnapshot 스냅샷 생성"""
    from shared.dto.prediction_dto import (
        PredictionSnapshot, WinProbability,
        ExpectedPossessionValue, LineupProjection,
    )

    def create():
        wp = WinProbability(
            home_wp=55.0,
            wp_curve=[(i * 30.0, 50.0 + i * 0.5) for i in range(10)],
            leverage_index=1.5,
        )
        epv = ExpectedPossessionValue(
            current_epv=1.2,
            pass_options=[{"epv": 1.3}, {"epv": 0.8}],
            shot_option_epv=0.9,
            drive_option_epv=1.1,
        )
        lp = LineupProjection(
            lineup_players=[1, 3, 5, 7, 11],
            predicted_net_rating=8.5,
        )
        PredictionSnapshot(
            frame_number=9000,
            timestamp=300.0,
            game_clock="Q3 05:00",
            quarter=3,
            win_probability=wp,
            epv=epv,
            current_lineup_projection=lp,
        )

    elapsed = measure(create, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("풀 PredictionSnapshot", elapsed, limit)
    else:
        r.fail("풀 PredictionSnapshot", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("prediction_dto.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_win_probability_creation(r)
    test_epv_creation(r)
    test_shot_quality_creation(r)
    test_lineup_projection_creation(r)
    test_prediction_snapshot_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_epv_best_option_property(r)

    print("\n--- 대량 처리 ---")
    test_batch_wp_updates(r)
    test_full_prediction_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
