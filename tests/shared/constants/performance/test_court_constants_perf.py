# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_court_constants_perf.py

농구 코트 규격 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근
- Enum 프로퍼티 (is_paint, point_value 등)
- frozenset 멤버십 조회
- i18n 다국어 조회
- CourtStandard 규격 속성 접근
- 21개 구역 전체 순회
- 메모리 사용량
- 복합 시나리오 (구역 판별 + 점수 + i18n)
- 대량 처리

Author: COURTVIEW AI Team
Version: 1.2.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

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
    mod_name = "shared.constants.court_constants"
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
def test_final_access(r: PerfResult) -> None:
    print("\n[2] Final 상수 접근")
    from shared.constants.court_constants import (
        COURT_LENGTH_M, COURT_WIDTH_M, THREE_POINT_LINE_DISTANCE_M,
        HOOP_HEIGHT_M, KEY_WIDTH_M,
    )
    elapsed = measure(lambda: (COURT_LENGTH_M, COURT_WIDTH_M,
                               THREE_POINT_LINE_DISTANCE_M, HOOP_HEIGHT_M, KEY_WIDTH_M))
    _check(r, "Final 상수 5개", elapsed, 1.0)


# ==================== 3. Enum 프로퍼티 ====================
def test_enum_property(r: PerfResult) -> None:
    print("\n[3] Enum 프로퍼티")
    from shared.constants.court_constants import CourtZone
    elapsed_paint = measure(lambda: CourtZone.PAINT_CENTER.is_paint)
    _check(r, "CourtZone.is_paint", elapsed_paint, 5.0)

    elapsed_pv = measure(lambda: CourtZone.THREE_TOP_CENTER.point_value)
    _check(r, "CourtZone.point_value", elapsed_pv, 5.0)


# ==================== 4. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    print("\n[4] frozenset 멤버십")
    from shared.constants.court_constants import CourtZone
    elapsed_mid = measure(lambda: CourtZone.MID_LEFT_ELBOW.is_midrange)
    _check(r, "is_midrange (frozenset)", elapsed_mid, 1.0)

    elapsed_three = measure(lambda: CourtZone.THREE_RIGHT_CORNER.is_three_point)
    _check(r, "is_three_point (frozenset)", elapsed_three, 1.0)


# ==================== 5. i18n 조회 ====================
def test_i18n_lookup(r: PerfResult) -> None:
    print("\n[5] i18n 조회")
    from shared.constants.court_constants import CourtZone, CourtStandard
    from shared.constants.localization import SupportedLanguage

    elapsed_ko = measure(lambda: CourtZone.PAINT_CENTER.get_name(SupportedLanguage.KO))
    _check(r, "CourtZone.get_name(KO)", elapsed_ko, 10.0)

    elapsed_en = measure(lambda: CourtZone.THREE_TOP_CENTER.get_name(SupportedLanguage.EN))
    _check(r, "CourtZone.get_name(EN)", elapsed_en, 10.0)

    elapsed_std = measure(lambda: CourtStandard.NBA.get_name(SupportedLanguage.JA))
    _check(r, "CourtStandard.get_name(JA)", elapsed_std, 10.0)


# ==================== 6. CourtStandard 속성 ====================
def test_standard_properties(r: PerfResult) -> None:
    print("\n[6] CourtStandard 속성")
    from shared.constants.court_constants import CourtStandard
    elapsed = measure(lambda: (
        CourtStandard.NBA.court_length,
        CourtStandard.NBA.court_width,
        CourtStandard.NBA.three_point_distance,
        CourtStandard.NBA.three_point_corner_distance,
    ))
    _check(r, "NBA 4속성 접근", elapsed, 5.0)


# ==================== 7. Enum 순회 (21개 구역) ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[7] Enum 순회")
    from shared.constants.court_constants import CourtZone, CourtStandard
    elapsed = measure(lambda: (list(CourtZone), list(CourtStandard)))
    _check(r, "CourtZone(21)+CourtStandard(7) 순회", elapsed, 15.0)


# ==================== 8. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[8] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.court_constants"
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
        _check(r, "메모리 사용량", peak_kb, 512.0)
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 512.0)


# ==================== 9. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[9] 복합 시나리오")
    from shared.constants.court_constants import CourtZone, CourtStandard
    from shared.constants.localization import SupportedLanguage

    def scenario():
        zone = CourtZone.THREE_LEFT_CORNER
        is_3pt = zone.is_three_point
        pts = zone.point_value
        name_ko = zone.get_name(SupportedLanguage.KO)
        name_en = zone.get_name(SupportedLanguage.EN)
        std = CourtStandard.FIBA
        length = std.court_length
        three_d = std.three_point_distance
        return is_3pt, pts, name_ko, name_en, length, three_d

    elapsed = measure(scenario)
    _check(r, "구역 판별+점수+i18n+규격", elapsed, 100.0)


# ==================== 10. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[10] 대량 처리")
    from shared.constants.court_constants import CourtZone
    zones = list(CourtZone)
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(10000):
        for z in zones:
            _ = z.point_value
            _ = z.is_paint
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"10K×21 점수+분류: {elapsed_ms:.1f}ms")
    _check(r, "대량 구역 판별", elapsed_ms * 1000, 200_000)


def main():
    r = PerfResult()
    test_module_import(r)        # 1
    test_final_access(r)         # 1
    test_enum_property(r)        # 2
    test_frozenset_membership(r) # 2
    test_i18n_lookup(r)          # 3
    test_standard_properties(r)  # 1
    test_enum_iteration(r)       # 1
    test_memory_usage(r)         # 1
    test_composite_scenario(r)   # 1
    test_bulk_operations(r)      # 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
