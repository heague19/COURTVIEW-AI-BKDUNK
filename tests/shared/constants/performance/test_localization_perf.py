# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_localization_perf.py

다국어 지원(localization) 상수 모듈 성능 테스트
- 모듈 임포트 시간
- native_name 속성 접근
- english_name 속성 접근
- from_code() 조회 (첫 번째, 마지막, 폴백)
- Enum 순회 (5개 멤버)
- 메모리 사용량
- 복합 시나리오 (전체 속성 접근)
- 대량 처리 (10K 반복)

성능 기준:
- 모듈 임포트: < 500ms
- 속성 접근: < 1us
- from_code 첫 번째: < 1us
- from_code 마지막/폴백: < 2us (전체 멤버 순회)
- Enum 순회: < 5us
- 복합 시나리오: < 50us
- 메모리: < 128KB
- 대량 처리: < 500ms

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
    """함수의 평균 실행 시간을 마이크로초(us) 단위로 반환."""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000  # ns -> us
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
    mod_name = "shared.constants.localization"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    _check(r, "모듈 임포트", elapsed_ms * 1000, 500_000)  # < 500ms


# ==================== 2. native_name 속성 접근 ====================
def test_native_name_access(r: PerfResult) -> None:
    print("\n[2] native_name 속성 접근")
    from shared.constants.localization import SupportedLanguage

    elapsed_ko = measure(lambda: SupportedLanguage.KO.native_name)
    _check(r, "KO.native_name", elapsed_ko, 1.0)

    elapsed_en = measure(lambda: SupportedLanguage.EN.native_name)
    _check(r, "EN.native_name", elapsed_en, 1.0)


# ==================== 3. english_name 속성 접근 ====================
def test_english_name_access(r: PerfResult) -> None:
    print("\n[3] english_name 속성 접근")
    from shared.constants.localization import SupportedLanguage

    elapsed_ko = measure(lambda: SupportedLanguage.KO.english_name)
    _check(r, "KO.english_name", elapsed_ko, 1.0)

    elapsed_ja = measure(lambda: SupportedLanguage.JA.english_name)
    _check(r, "JA.english_name", elapsed_ja, 1.0)


# ==================== 4. from_code() 조회 ====================
def test_from_code_lookup(r: PerfResult) -> None:
    print("\n[4] from_code() 조회")
    from shared.constants.localization import SupportedLanguage

    # 첫 번째 매칭 (ko)
    elapsed_first = measure(lambda: SupportedLanguage.from_code("ko"))
    _check(r, "from_code('ko') 첫 번째", elapsed_first, 1.0)

    # 마지막 매칭 (es) - 5개 멤버 전체 순회 후 매칭
    elapsed_last = measure(lambda: SupportedLanguage.from_code("es"))
    _check(r, "from_code('es') 마지막", elapsed_last, 2.0)

    # 폴백 (존재하지 않는 코드 -> KO 반환) - 전체 순회 후 기본값
    elapsed_fallback = measure(lambda: SupportedLanguage.from_code("xx"))
    _check(r, "from_code('xx') 폴백", elapsed_fallback, 2.0)


# ==================== 5. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[5] Enum 순회")
    from shared.constants.localization import SupportedLanguage

    elapsed = measure(lambda: list(SupportedLanguage))
    _check(r, "SupportedLanguage(5) 순회", elapsed, 5.0)


# ==================== 6. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[6] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.localization"
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
        _check(r, "메모리 사용량", peak_kb, 128.0)  # < 128KB
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 128.0)


# ==================== 7. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[7] 복합 시나리오")
    from shared.constants.localization import SupportedLanguage

    # 모든 멤버의 native_name + english_name 접근
    def scenario_all_names():
        for lang in SupportedLanguage:
            _ = lang.native_name
            _ = lang.english_name
    elapsed_names = measure(scenario_all_names)
    _check(r, "전체 멤버 속성 접근 (5개)", elapsed_names, 50.0)

    # 모든 멤버 값으로 from_code 호출
    def scenario_from_code_all():
        for lang in SupportedLanguage:
            _ = SupportedLanguage.from_code(lang.value)
    elapsed_from = measure(scenario_from_code_all)
    _check(r, "전체 멤버 from_code (5개)", elapsed_from, 50.0)


# ==================== 8. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[8] 대량 처리")
    from shared.constants.localization import SupportedLanguage

    all_langs = list(SupportedLanguage)
    all_codes = [lang.value for lang in all_langs]

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(10_000):
        for code in all_codes:
            _ = SupportedLanguage.from_code(code)
        for lang in all_langs:
            _ = lang.native_name
            _ = lang.english_name
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"10K x (from_code 5 + native 5 + english 5): {elapsed_ms:.1f}ms")
    _check(r, "대량 처리", elapsed_ms * 1000, 500_000)  # < 500ms


def main():
    r = PerfResult()
    test_module_import(r)          # 1: 1
    test_native_name_access(r)     # 2: 2
    test_english_name_access(r)    # 3: 2
    test_from_code_lookup(r)       # 4: 3
    test_enum_iteration(r)         # 5: 1
    test_memory_usage(r)           # 6: 1
    test_composite_scenario(r)     # 7: 2
    test_bulk_operations(r)        # 8: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
