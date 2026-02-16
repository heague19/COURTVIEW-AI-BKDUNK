# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_matching_constants_perf.py

객체 매칭 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 (52개 public Final, 3 tuple 포함)
- MatchingStrategy 속성 (is_optimal, supports_partial_matching, default_threshold, to_korean)
- MatchingStatus 속성 (is_successful, needs_resolution, can_retry, to_korean)
- MatchingTargetType 속성 (matching_weights, appearance_threshold, to_korean)
- frozenset 멤버십 (4 frozenset)
- Enum 순회 (7 / 7 / 6)
- 메모리 사용량
- 복합 시나리오
- 대량 처리

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1us
- 튜플 상수 접근: < 1us
- frozenset 멤버십: < 1us
- Enum 순회: < 5us
- 복합 시나리오: < 50us
- 대량 처리: < 500ms
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
    """함수의 평균 실행 시간 (us)."""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000  # us
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
    mod_name = "shared.constants.matching_constants"
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
    from shared.constants.matching_constants import (
        APPEARANCE_WEIGHT,
        DEFAULT_EPIPOLAR_THRESHOLD,
        HUNGARIAN_MAX_COST,
        MIN_MATCH_CONFIDENCE,
        COST_NORMALIZATION_EPS,
    )

    elapsed = measure(lambda: APPEARANCE_WEIGHT)
    _check(r, "APPEARANCE_WEIGHT", elapsed, 1.0)

    elapsed = measure(lambda: DEFAULT_EPIPOLAR_THRESHOLD)
    _check(r, "DEFAULT_EPIPOLAR_THRESHOLD", elapsed, 1.0)

    elapsed = measure(lambda: HUNGARIAN_MAX_COST)
    _check(r, "HUNGARIAN_MAX_COST", elapsed, 1.0)

    elapsed = measure(lambda: MIN_MATCH_CONFIDENCE)
    _check(r, "MIN_MATCH_CONFIDENCE", elapsed, 1.0)

    elapsed = measure(lambda: COST_NORMALIZATION_EPS)
    _check(r, "COST_NORMALIZATION_EPS", elapsed, 1.0)


# ==================== 3. 튜플 상수 접근 ====================
def test_tuple_constant_access(r: PerfResult) -> None:
    print("\n[3] 튜플 상수 접근")
    from shared.constants.matching_constants import (
        PLAYER_MATCHING_WEIGHTS,
        BALL_MATCHING_WEIGHTS,
    )

    elapsed = measure(lambda: PLAYER_MATCHING_WEIGHTS)
    _check(r, "PLAYER_MATCHING_WEIGHTS", elapsed, 1.0)

    elapsed = measure(lambda: BALL_MATCHING_WEIGHTS)
    _check(r, "BALL_MATCHING_WEIGHTS", elapsed, 1.0)


# ==================== 4. MatchingStrategy 속성 ====================
def test_matching_strategy_properties(r: PerfResult) -> None:
    print("\n[4] MatchingStrategy 속성")
    from shared.constants.matching_constants import MatchingStrategy

    hungarian = MatchingStrategy.HUNGARIAN
    elapsed = measure(lambda: hungarian.is_optimal)
    _check(r, "is_optimal (HUNGARIAN)", elapsed, 1.0)

    greedy = MatchingStrategy.GREEDY
    elapsed = measure(lambda: greedy.supports_partial_matching)
    _check(r, "supports_partial_matching (GREEDY)", elapsed, 1.0)

    fusion = MatchingStrategy.FUSION
    elapsed = measure(lambda: fusion.default_threshold)
    _check(r, "default_threshold (FUSION)", elapsed, 1.0)

    auction = MatchingStrategy.AUCTION
    elapsed = measure(lambda: auction.to_korean())
    _check(r, "to_korean (AUCTION)", elapsed, 1.0)


# ==================== 5. MatchingStatus 속성 ====================
def test_matching_status_properties(r: PerfResult) -> None:
    print("\n[5] MatchingStatus 속성")
    from shared.constants.matching_constants import MatchingStatus

    matched = MatchingStatus.MATCHED
    elapsed = measure(lambda: matched.is_successful)
    _check(r, "is_successful (MATCHED)", elapsed, 1.0)

    ambiguous = MatchingStatus.AMBIGUOUS
    elapsed = measure(lambda: ambiguous.needs_resolution)
    _check(r, "needs_resolution (AMBIGUOUS)", elapsed, 1.0)

    below = MatchingStatus.BELOW_THRESHOLD
    elapsed = measure(lambda: below.can_retry)
    _check(r, "can_retry (BELOW_THRESHOLD)", elapsed, 1.0)

    conflicted = MatchingStatus.CONFLICTED
    elapsed = measure(lambda: conflicted.to_korean())
    _check(r, "to_korean (CONFLICTED)", elapsed, 1.0)


# ==================== 6. MatchingTargetType 속성 ====================
def test_matching_target_type_properties(r: PerfResult) -> None:
    print("\n[6] MatchingTargetType 속성")
    from shared.constants.matching_constants import MatchingTargetType

    player = MatchingTargetType.PLAYER
    elapsed = measure(lambda: player.matching_weights)
    _check(r, "matching_weights (PLAYER)", elapsed, 1.0)

    ball = MatchingTargetType.BALL
    elapsed = measure(lambda: ball.appearance_threshold)
    _check(r, "appearance_threshold (BALL)", elapsed, 1.0)

    referee = MatchingTargetType.REFEREE
    elapsed = measure(lambda: referee.to_korean())
    _check(r, "to_korean (REFEREE)", elapsed, 1.0)


# ==================== 7. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    print("\n[7] frozenset 멤버십")
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus,
    )
    # _MATCHING_STRATEGY_IS_OPTIMAL 멤버십을 is_optimal 속성을 통해 검증
    hungarian = MatchingStrategy.HUNGARIAN
    elapsed = measure(lambda: hungarian.is_optimal)
    _check(r, "_MATCHING_STRATEGY_IS_OPTIMAL 멤버십", elapsed, 1.0)

    # _MATCHING_STATUS_NEEDS_RESOLUTION 멤버십을 needs_resolution 속성을 통해 검증
    ambiguous = MatchingStatus.AMBIGUOUS
    elapsed = measure(lambda: ambiguous.needs_resolution)
    _check(r, "_MATCHING_STATUS_NEEDS_RESOLUTION 멤버십", elapsed, 1.0)


# ==================== 8. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[8] Enum 순회")
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
    )

    elapsed = measure(lambda: list(MatchingStrategy))
    r.info(f"MatchingStrategy 멤버 수: {len(list(MatchingStrategy))}")
    _check(r, "MatchingStrategy(7) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(MatchingStatus))
    r.info(f"MatchingStatus 멤버 수: {len(list(MatchingStatus))}")
    _check(r, "MatchingStatus(7) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(MatchingTargetType))
    r.info(f"MatchingTargetType 멤버 수: {len(list(MatchingTargetType))}")
    _check(r, "MatchingTargetType(6) 순회", elapsed, 5.0)


# ==================== 9. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[9] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.matching_constants"
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


# ==================== 10. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[10] 복합 시나리오")
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
        MIN_MATCH_CONFIDENCE,
    )

    def scenario():
        # MatchingStrategy 속성 접근
        ms = MatchingStrategy.HUNGARIAN
        _ = ms.is_optimal
        _ = ms.supports_partial_matching
        _ = ms.default_threshold
        _ = ms.to_korean()

        # MatchingStatus 속성 접근
        st = MatchingStatus.AMBIGUOUS
        _ = st.is_successful
        _ = st.needs_resolution
        _ = st.can_retry
        _ = st.to_korean()

        # MatchingTargetType 속성 접근
        tt = MatchingTargetType.PLAYER
        _ = tt.matching_weights
        _ = tt.appearance_threshold
        _ = tt.to_korean()

        # 상수 접근 + 가중치 합 검증
        w_sum = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
        _ = abs(w_sum - 1.0) < 1e-9
        _ = MIN_MATCH_CONFIDENCE
        return st

    elapsed = measure(scenario)
    _check(r, "3 Enum 속성 + 상수 + 가중치 합 검증", elapsed, 50.0)


# ==================== 11. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[11] 대량 처리")
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
    )

    all_strategies = list(MatchingStrategy)   # 7
    all_statuses = list(MatchingStatus)       # 7
    all_targets = list(MatchingTargetType)    # 6 -> 총 20 멤버

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        for s in all_strategies:
            _ = s.is_optimal
            _ = s.supports_partial_matching
            _ = s.default_threshold
            _ = s.to_korean()
        for st in all_statuses:
            _ = st.is_successful
            _ = st.needs_resolution
            _ = st.can_retry
            _ = st.to_korean()
        for tt in all_targets:
            _ = tt.matching_weights
            _ = tt.appearance_threshold
            _ = tt.to_korean()
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 20 Enum 멤버 전체 속성: {elapsed_ms:.1f}ms")
    _check(r, "대량 처리 (1K x 20 멤버)", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)                     # 1:  1
    test_constant_access(r)                   # 2:  5
    test_tuple_constant_access(r)             # 3:  2
    test_matching_strategy_properties(r)      # 4:  4
    test_matching_status_properties(r)        # 5:  4
    test_matching_target_type_properties(r)   # 6:  3
    test_frozenset_membership(r)              # 7:  2
    test_enum_iteration(r)                    # 8:  3
    test_memory_usage(r)                      # 9:  1
    test_composite_scenario(r)                # 10: 1
    test_bulk_operations(r)                   # 11: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
