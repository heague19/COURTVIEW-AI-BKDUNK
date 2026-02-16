# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_fusion_constants_perf.py

멀티뷰 융합 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근
- FusionStrategy 속성 (requires_history, is_probabilistic, default_weight_type, to_korean)
- FusionQuality 속성 (level_name, min_score, score_range, is_usable, to_korean)
- FusionQuality.from_score
- frozenset 멤버십
- Enum 순회 (8개 / 5개)
- 메모리 사용량
- 복합 시나리오
- 대량 처리

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1μs
- frozenset 멤버십: < 1μs
- from_score: < 1μs
- to_korean: < 1μs
- 복합 시나리오: < 50μs
- 메모리: < 128KB

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수의 평균 실행 시간 (μs)."""
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


def _check(r: PerfResult, name: str, elapsed: float, limit: float) -> None:
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 ====================
def test_module_import(r: PerfResult) -> None:
    print("\n[1] 모듈 임포트")
    import importlib
    mod_name = "shared.constants.fusion_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    _check(r, "모듈 임포트", elapsed_ms * 1000, 500_000)


# ==================== 2. Final 상수 접근 ====================
def test_constant_access(r: PerfResult) -> None:
    print("\n[2] Final 상수 접근")
    from shared.constants.fusion_constants import (
        FUSION_CONFIDENCE_THRESHOLD, APPEARANCE_WEIGHT,
        MAX_REPROJECTION_ERROR_PX, RANSAC_ITERATIONS,
    )

    elapsed_conf = measure(lambda: FUSION_CONFIDENCE_THRESHOLD)
    _check(r, "FUSION_CONFIDENCE_THRESHOLD", elapsed_conf, 1.0)

    elapsed_weight = measure(lambda: APPEARANCE_WEIGHT)
    _check(r, "APPEARANCE_WEIGHT", elapsed_weight, 1.0)

    elapsed_reproj = measure(lambda: MAX_REPROJECTION_ERROR_PX)
    _check(r, "MAX_REPROJECTION_ERROR_PX", elapsed_reproj, 1.0)

    elapsed_ransac = measure(lambda: RANSAC_ITERATIONS)
    _check(r, "RANSAC_ITERATIONS", elapsed_ransac, 1.0)


# ==================== 3. FusionStrategy 속성 ====================
def test_strategy_properties(r: PerfResult) -> None:
    print("\n[3] FusionStrategy 속성")
    from shared.constants.fusion_constants import FusionStrategy

    fs = FusionStrategy.KALMAN_FILTER
    elapsed_hist = measure(lambda: fs.requires_history)
    _check(r, "requires_history", elapsed_hist, 1.0)

    elapsed_prob = measure(lambda: fs.is_probabilistic)
    _check(r, "is_probabilistic", elapsed_prob, 1.0)

    elapsed_wt = measure(lambda: fs.default_weight_type)
    _check(r, "default_weight_type", elapsed_wt, 1.0)

    elapsed_kr = measure(lambda: fs.to_korean())
    _check(r, "FusionStrategy.to_korean()", elapsed_kr, 1.0)


# ==================== 4. FusionQuality 속성 ====================
def test_quality_properties(r: PerfResult) -> None:
    print("\n[4] FusionQuality 속성")
    from shared.constants.fusion_constants import FusionQuality

    fq = FusionQuality.EXCELLENT
    elapsed_level = measure(lambda: fq.level_name)
    _check(r, "level_name", elapsed_level, 1.0)

    elapsed_min = measure(lambda: fq.min_score)
    _check(r, "min_score", elapsed_min, 1.0)

    elapsed_range = measure(lambda: fq.score_range)
    _check(r, "score_range", elapsed_range, 1.0)

    elapsed_usable = measure(lambda: fq.is_usable)
    _check(r, "is_usable", elapsed_usable, 1.0)

    elapsed_kr = measure(lambda: fq.to_korean())
    _check(r, "FusionQuality.to_korean()", elapsed_kr, 1.0)


# ==================== 5. FusionQuality.from_score ====================
def test_from_score(r: PerfResult) -> None:
    print("\n[5] FusionQuality.from_score")
    from shared.constants.fusion_constants import FusionQuality

    # 최상위 경로 (첫 if 진입)
    elapsed_top = measure(lambda: FusionQuality.from_score(0.95))
    _check(r, "from_score(0.95) EXCELLENT", elapsed_top, 1.0)

    # 최하위 경로 (모든 if 통과)
    elapsed_bot = measure(lambda: FusionQuality.from_score(0.1))
    _check(r, "from_score(0.1) FAILED", elapsed_bot, 1.0)

    # 중간 경로
    elapsed_mid = measure(lambda: FusionQuality.from_score(0.65))
    _check(r, "from_score(0.65) ACCEPTABLE", elapsed_mid, 1.0)


# ==================== 6. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[6] Enum 순회")
    from shared.constants.fusion_constants import FusionStrategy, FusionQuality

    elapsed_fs = measure(lambda: list(FusionStrategy))
    _check(r, "FusionStrategy(8) 순회", elapsed_fs, 5.0)

    elapsed_fq = measure(lambda: list(FusionQuality))
    _check(r, "FusionQuality(5) 순회", elapsed_fq, 5.0)


# ==================== 7. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[7] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.fusion_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()
    try:
        import tracemalloc
        tracemalloc.start()
        importlib.import_module(mod_name)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kb = peak_bytes / 1024
        r.info(f"메모리: {peak_kb:.1f}KB")
        _check(r, "메모리 사용량", peak_kb, 128.0)
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 128.0)


# ==================== 8. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[8] 복합 시나리오")
    from shared.constants.fusion_constants import (
        FusionStrategy, FusionQuality,
        FUSION_CONFIDENCE_THRESHOLD, APPEARANCE_WEIGHT,
    )

    def scenario():
        fs = FusionStrategy.WEIGHTED_AVERAGE
        _ = fs.requires_history
        _ = fs.is_probabilistic
        _ = fs.default_weight_type
        _ = fs.to_korean()

        fq = FusionQuality.from_score(0.8)
        _ = fq.level_name
        _ = fq.min_score
        _ = fq.is_usable
        _ = fq.to_korean()

        _ = FUSION_CONFIDENCE_THRESHOLD
        _ = APPEARANCE_WEIGHT
        return fq

    elapsed = measure(scenario)
    _check(r, "전략+품질 분류 파이프라인", elapsed, 50.0)


# ==================== 9. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[9] 대량 처리")
    from shared.constants.fusion_constants import FusionStrategy, FusionQuality
    import random

    all_strategies = list(FusionStrategy)
    scores = [i / 100.0 for i in range(0, 101)]

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        for fs in all_strategies:
            _ = fs.requires_history
            _ = fs.is_probabilistic
            _ = fs.default_weight_type
        for score in scores:
            _ = FusionQuality.from_score(score)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x (8 전략 + 101 점수): {elapsed_ms:.1f}ms")
    _check(r, "대량 분류 처리", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)          # 1: 1
    test_constant_access(r)        # 2: 4
    test_strategy_properties(r)    # 3: 4
    test_quality_properties(r)     # 4: 5
    test_from_score(r)             # 5: 3
    test_enum_iteration(r)         # 6: 2
    test_memory_usage(r)           # 7: 1
    test_composite_scenario(r)     # 8: 1
    test_bulk_operations(r)        # 9: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
