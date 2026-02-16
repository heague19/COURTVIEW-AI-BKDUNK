# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_tactical_constants_perf.py

전술 상수 모듈(tactical_constants.py v1.0.0) 성능 테스트

테스트 범위:
    [A] 모듈 임포트 시간 (< 500ms)
    [B] SetPlayType Enum 멤버 접근 (100K < 500ms)
    [C] TransitionPhase Enum 멤버 접근 (100K < 500ms)
    [D] SpacingQuality Enum 멤버 접근 (100K < 500ms)
    [E] TurnoverCategory Enum 멤버 접근 (100K < 500ms)
    [F] Enum i18n get_name() (10K < 200ms)
    [G] SetPlayType property 접근 (100K < 500ms)
    [H] TurnoverCategory property 접근 (100K < 500ms)
    [I] classify_spacing_quality (50K < 300ms)
    [J] classify_transition_phase (50K < 300ms)
    [K] is_scoring_run (50K < 300ms)
    [L] 상수 조회 (100K < 500ms)
    [M] 메모리 사용량 (< 1MB)

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
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.passed += 1
        ratio = elapsed_ms / limit_ms * 100
        print(f"  [PASS] {name}: {elapsed_ms:.4f}ms ({ratio:.1f}% of {limit_ms:.0f}ms)")

    def fail(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_ms:.4f}ms > {limit_ms:.0f}ms")
        print(f"  [FAIL] {name}: {elapsed_ms:.4f}ms (limit: {limit_ms:.0f}ms)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def check(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        if elapsed_ms <= limit_ms:
            self.ok(name, elapsed_ms, limit_ms)
        else:
            self.fail(name, elapsed_ms, limit_ms)

    def check_memory(self, name: str, size_kb: float, limit_kb: float) -> None:
        if size_kb <= limit_kb:
            self.passed += 1
            ratio = size_kb / limit_kb * 100
            print(f"  [PASS] {name}: {size_kb:.2f}KB ({ratio:.1f}% of {limit_kb:.0f}KB)")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {size_kb:.2f}KB > {limit_kb:.0f}KB")
            print(f"  [FAIL] {name}: {size_kb:.2f}KB (limit: {limit_kb:.0f}KB)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n목표 미달 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] 모듈 임포트 시간
# =============================================================================
def test_a_import_time(r: PerfResult) -> None:
    import importlib

    mod_name = "shared.constants.tactical_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter()
    importlib.import_module(mod_name)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.info(f"임포트 시간: {elapsed_ms:.2f}ms")
    r.check("모듈 임포트 (cold)", elapsed_ms, 500.0)


# =============================================================================
# [B] SetPlayType Enum 멤버 접근
# =============================================================================
def test_b_set_play_type_access(r: PerfResult) -> None:
    from shared.constants.tactical_constants import SetPlayType

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SetPlayType.HORN
        _ = SetPlayType.FLEX
        _ = SetPlayType.MOTION
        _ = SetPlayType.PICK_AND_ROLL
        _ = SetPlayType.PICK_AND_POP
        _ = SetPlayType.ISOLATION
        _ = SetPlayType.POST_UP
        _ = SetPlayType.DRIBBLE_HAND_OFF
        _ = SetPlayType.STAGGER_SCREEN
        _ = SetPlayType.SPAIN_PNR
        _ = SetPlayType.ATO_SET
        _ = SetPlayType.FLOPPY
        _ = SetPlayType.PRINCETON
        _ = SetPlayType.TRIANGLE
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SetPlayType 멤버 접근 (100K x 14종)", elapsed, 500.0)


# =============================================================================
# [C] TransitionPhase Enum 멤버 접근
# =============================================================================
def test_c_transition_phase_access(r: PerfResult) -> None:
    from shared.constants.tactical_constants import TransitionPhase

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TransitionPhase.PRIMARY_BREAK
        _ = TransitionPhase.SECONDARY_BREAK
        _ = TransitionPhase.EARLY_OFFENSE
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TransitionPhase 멤버 접근 (100K x 3종)", elapsed, 500.0)


# =============================================================================
# [D] SpacingQuality Enum 멤버 접근
# =============================================================================
def test_d_spacing_quality_access(r: PerfResult) -> None:
    from shared.constants.tactical_constants import SpacingQuality

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SpacingQuality.EXCELLENT
        _ = SpacingQuality.GOOD
        _ = SpacingQuality.AVERAGE
        _ = SpacingQuality.POOR
        _ = SpacingQuality.COLLAPSED
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SpacingQuality 멤버 접근 (100K x 5종)", elapsed, 500.0)


# =============================================================================
# [E] TurnoverCategory Enum 멤버 접근
# =============================================================================
def test_e_turnover_category_access(r: PerfResult) -> None:
    from shared.constants.tactical_constants import TurnoverCategory

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TurnoverCategory.FORCED_LIVE
        _ = TurnoverCategory.FORCED_DEAD
        _ = TurnoverCategory.UNFORCED_LIVE
        _ = TurnoverCategory.UNFORCED_DEAD
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TurnoverCategory 멤버 접근 (100K x 4종)", elapsed, 500.0)


# =============================================================================
# [F] Enum i18n get_name()
# =============================================================================
def test_f_enum_i18n(r: PerfResult) -> None:
    from shared.constants.tactical_constants import (
        SetPlayType, TransitionPhase, SpacingQuality, TurnoverCategory,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    # SetPlayType i18n
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for play in SetPlayType:
            _ = play.get_name(SupportedLanguage.KO)
            _ = play.get_name(SupportedLanguage.EN)
    elapsed_play = (time.perf_counter() - start) * 1000
    gc.enable()
    r.check("SetPlayType.get_name() (10K x 14종 x 2언어)", elapsed_play, 200.0)

    # TransitionPhase i18n
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for phase in TransitionPhase:
            _ = phase.get_name(SupportedLanguage.KO)
            _ = phase.get_name(SupportedLanguage.EN)
    elapsed_phase = (time.perf_counter() - start) * 1000
    gc.enable()
    r.check("TransitionPhase.get_name() (10K x 3종 x 2언어)", elapsed_phase, 200.0)

    # SpacingQuality i18n
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for sq in SpacingQuality:
            _ = sq.get_name(SupportedLanguage.KO)
            _ = sq.get_name(SupportedLanguage.EN)
    elapsed_sq = (time.perf_counter() - start) * 1000
    gc.enable()
    r.check("SpacingQuality.get_name() (10K x 5종 x 2언어)", elapsed_sq, 200.0)

    # TurnoverCategory i18n
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for tc in TurnoverCategory:
            _ = tc.get_name(SupportedLanguage.KO)
            _ = tc.get_name(SupportedLanguage.EN)
    elapsed_tc = (time.perf_counter() - start) * 1000
    gc.enable()
    r.check("TurnoverCategory.get_name() (10K x 4종 x 2언어)", elapsed_tc, 200.0)


# =============================================================================
# [G] SetPlayType property 접근
# =============================================================================
def test_g_set_play_properties(r: PerfResult) -> None:
    from shared.constants.tactical_constants import SetPlayType

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SetPlayType.PICK_AND_ROLL.involves_screen
        _ = SetPlayType.ISOLATION.involves_screen
        _ = SetPlayType.ISOLATION.is_one_on_one
        _ = SetPlayType.HORN.is_one_on_one
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SetPlayType property 접근 (100K x 4종)", elapsed, 500.0)


# =============================================================================
# [H] TurnoverCategory property 접근
# =============================================================================
def test_h_turnover_properties(r: PerfResult) -> None:
    from shared.constants.tactical_constants import TurnoverCategory

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TurnoverCategory.FORCED_LIVE.is_forced
        _ = TurnoverCategory.FORCED_LIVE.is_live_ball
        _ = TurnoverCategory.UNFORCED_DEAD.is_forced
        _ = TurnoverCategory.UNFORCED_DEAD.is_live_ball
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TurnoverCategory property 접근 (100K x 4종)", elapsed, 500.0)


# =============================================================================
# [I] classify_spacing_quality
# =============================================================================
def test_i_classify_spacing(r: PerfResult) -> None:
    from shared.constants.tactical_constants import classify_spacing_quality

    iterations = 50_000
    distances = [2.0, 2.5, 3.0, 3.5, 4.5, 5.0]

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for d in distances:
            _ = classify_spacing_quality(d)
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_spacing_quality (50K x 6값)", elapsed, 300.0)


# =============================================================================
# [J] classify_transition_phase
# =============================================================================
def test_j_classify_transition(r: PerfResult) -> None:
    from shared.constants.tactical_constants import classify_transition_phase

    iterations = 50_000
    times = [2.0, 5.0, 6.0, 8.0, 10.0, 15.0]

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for t in times:
            _ = classify_transition_phase(t)
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("classify_transition_phase (50K x 6값)", elapsed, 300.0)


# =============================================================================
# [K] is_scoring_run
# =============================================================================
def test_k_is_scoring_run(r: PerfResult) -> None:
    from shared.constants.tactical_constants import is_scoring_run

    iterations = 50_000
    cases = [(6, 3), (8, 5), (4, 2), (10, 4), (0, 0), (6, 2)]

    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for pts, scoreless in cases:
            _ = is_scoring_run(pts, scoreless)
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_scoring_run (50K x 6케이스)", elapsed, 300.0)


# =============================================================================
# [L] 상수 조회
# =============================================================================
def test_l_constant_lookup(r: PerfResult) -> None:
    from shared.constants.tactical_constants import (
        SPACING_OPTIMAL_DISTANCE_M,
        SCORING_RUN_MIN_POINTS,
        MOMENTUM_SHIFT_THRESHOLD,
        PRIMARY_BREAK_MAX_SEC,
        SCREEN_CONTACT_DISTANCE_M,
        MATCHUP_ASSIGNMENT_DISTANCE_M,
    )

    iterations = 100_000
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SPACING_OPTIMAL_DISTANCE_M
        _ = SCORING_RUN_MIN_POINTS
        _ = MOMENTUM_SHIFT_THRESHOLD
        _ = PRIMARY_BREAK_MAX_SEC
        _ = SCREEN_CONTACT_DISTANCE_M
        _ = MATCHUP_ASSIGNMENT_DISTANCE_M
    elapsed = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("상수 조회 (100K x 6종)", elapsed, 500.0)


# =============================================================================
# [M] 메모리 사용량
# =============================================================================
def test_m_memory_footprint(r: PerfResult) -> None:
    import importlib
    import tracemalloc

    mod_name = "shared.constants.tactical_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    tracemalloc.start()
    importlib.import_module(mod_name)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_kb = peak / 1024
    print(f"\n  tracemalloc 모듈 메모리:")
    print(f"    현재: {current / 1024:.2f}KB")
    print(f"    피크: {peak_kb:.2f}KB")

    r.check_memory("tracemalloc 피크 메모리", peak_kb, 1024.0)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> int:
    r = PerfResult()

    print("\n" + "=" * 60)
    print("tactical_constants.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_import_time(r)

    print("\n--- [B] SetPlayType 멤버 접근 ---")
    test_b_set_play_type_access(r)

    print("\n--- [C] TransitionPhase 멤버 접근 ---")
    test_c_transition_phase_access(r)

    print("\n--- [D] SpacingQuality 멤버 접근 ---")
    test_d_spacing_quality_access(r)

    print("\n--- [E] TurnoverCategory 멤버 접근 ---")
    test_e_turnover_category_access(r)

    print("\n--- [F] Enum i18n get_name() ---")
    test_f_enum_i18n(r)

    print("\n--- [G] SetPlayType property 접근 ---")
    test_g_set_play_properties(r)

    print("\n--- [H] TurnoverCategory property 접근 ---")
    test_h_turnover_properties(r)

    print("\n--- [I] classify_spacing_quality ---")
    test_i_classify_spacing(r)

    print("\n--- [J] classify_transition_phase ---")
    test_j_classify_transition(r)

    print("\n--- [K] is_scoring_run ---")
    test_k_is_scoring_run(r)

    print("\n--- [L] 상수 조회 ---")
    test_l_constant_lookup(r)

    print("\n--- [M] 메모리 사용량 ---")
    test_m_memory_footprint(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
