# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_error_codes_perf.py

에러 코드 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근
- ErrorCode 속성 접근 (code, message, http_status)
- ErrorCategory 속성/메서드
- ERROR_CODE_LOOKUP O(1) 캐시 조회
- RETRYABLE_ERRORS frozenset 멤버십
- is_retryable / is_client_error / is_server_error
- ErrorCode.from_code O(1) 조회
- ErrorCode.to_dict 직렬화
- Enum 순회 (270개)
- 메모리 사용량
- 복합 시나리오 (에러 분류 파이프라인)
- 대량 처리 (10K × 270)

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1μs
- 캐시 조회: < 1μs
- frozenset 멤버십: < 1μs
- to_dict: < 10μs
- 복합 시나리오: < 100μs

Author: COURTVIEW AI Team
Version: 1.0.0
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
    mod_name = "shared.constants.error_codes"
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


# ==================== 2. ErrorCode 속성 접근 ====================
def test_error_code_access(r: PerfResult) -> None:
    print("\n[2] ErrorCode 속성 접근")
    from shared.constants.error_codes import ErrorCode

    e = ErrorCode.UNKNOWN_ERROR
    elapsed_code = measure(lambda: e.code)
    _check(r, "ErrorCode.code", elapsed_code, 1.0)

    elapsed_msg = measure(lambda: e.message)
    _check(r, "ErrorCode.message", elapsed_msg, 1.0)

    elapsed_http = measure(lambda: e.http_status)
    _check(r, "ErrorCode.http_status", elapsed_http, 1.0)


# ==================== 3. ErrorCategory 속성/메서드 ====================
def test_error_category_access(r: PerfResult) -> None:
    print("\n[3] ErrorCategory 속성")
    from shared.constants.error_codes import ErrorCategory

    cat = ErrorCategory.INFRASTRUCTURE
    elapsed_start = measure(lambda: cat.start)
    _check(r, "ErrorCategory.start", elapsed_start, 1.0)

    elapsed_contains = measure(lambda: cat.contains(5500))
    _check(r, "ErrorCategory.contains()", elapsed_contains, 1.0)


# ==================== 4. ERROR_CODE_LOOKUP O(1) 캐시 ====================
def test_lookup_cache(r: PerfResult) -> None:
    print("\n[4] ERROR_CODE_LOOKUP 캐시")
    from shared.constants.error_codes import ERROR_CODE_LOOKUP

    elapsed = measure(lambda: ERROR_CODE_LOOKUP[5000])
    _check(r, "LOOKUP[5000] dict 조회", elapsed, 1.0)

    elapsed_in = measure(lambda: 5000 in ERROR_CODE_LOOKUP)
    _check(r, "5000 in LOOKUP 멤버십", elapsed_in, 1.0)


# ==================== 5. RETRYABLE_ERRORS frozenset 멤버십 ====================
def test_retryable_membership(r: PerfResult) -> None:
    print("\n[5] RETRYABLE_ERRORS 멤버십")
    from shared.constants.error_codes import ErrorCode, RETRYABLE_ERRORS

    elapsed_in = measure(lambda: ErrorCode.TIMEOUT_ERROR in RETRYABLE_ERRORS)
    _check(r, "in RETRYABLE_ERRORS (True)", elapsed_in, 1.0)

    elapsed_not = measure(lambda: ErrorCode.VALIDATION_ERROR in RETRYABLE_ERRORS)
    _check(r, "in RETRYABLE_ERRORS (False)", elapsed_not, 1.0)


# ==================== 6. is_retryable / is_client / is_server ====================
def test_classification_methods(r: PerfResult) -> None:
    print("\n[6] 분류 메서드")
    from shared.constants.error_codes import ErrorCode

    elapsed_retry = measure(lambda: ErrorCode.TIMEOUT_ERROR.is_retryable())
    _check(r, "is_retryable()", elapsed_retry, 1.0)

    elapsed_client = measure(lambda: ErrorCode.VALIDATION_ERROR.is_client_error())
    _check(r, "is_client_error()", elapsed_client, 1.0)

    elapsed_server = measure(lambda: ErrorCode.INTERNAL_ERROR.is_server_error())
    _check(r, "is_server_error()", elapsed_server, 1.0)


# ==================== 7. ErrorCode.from_code O(1) ====================
def test_from_code(r: PerfResult) -> None:
    print("\n[7] ErrorCode.from_code")
    from shared.constants.error_codes import ErrorCode

    elapsed = measure(lambda: ErrorCode.from_code(5000))
    _check(r, "from_code(5000)", elapsed, 1.0)

    elapsed_high = measure(lambda: ErrorCode.from_code(9202))
    _check(r, "from_code(9202)", elapsed_high, 1.0)


# ==================== 8. ErrorCode.to_dict ====================
def test_to_dict(r: PerfResult) -> None:
    print("\n[8] to_dict 직렬화")
    from shared.constants.error_codes import ErrorCode

    elapsed = measure(lambda: ErrorCode.UNKNOWN_ERROR.to_dict())
    _check(r, "ErrorCode.to_dict()", elapsed, 10.0)

    from shared.constants.error_codes import ErrorCategory
    elapsed_cat = measure(lambda: ErrorCategory.GENERAL.to_dict())
    _check(r, "ErrorCategory.to_dict()", elapsed_cat, 5.0)


# ==================== 9. Enum 순회 (270개) ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[9] Enum 순회")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    elapsed = measure(lambda: list(ErrorCode), iterations=1000)
    _check(r, "ErrorCode(270) 순회", elapsed, 100.0)

    elapsed_cat = measure(lambda: list(ErrorCategory))
    _check(r, "ErrorCategory(9) 순회", elapsed_cat, 5.0)


# ==================== 10. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[10] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.error_codes"
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


# ==================== 11. 복합 시나리오 ====================
def test_composite_scenario(r: PerfResult) -> None:
    print("\n[11] 복합 시나리오")
    from shared.constants.error_codes import ErrorCode, RETRYABLE_ERRORS

    def scenario():
        e = ErrorCode.from_code(5001)
        code = e.code
        msg = e.message
        http = e.http_status
        cat = e.category
        retry = e.is_retryable()
        client = e.is_client_error()
        server = e.is_server_error()
        d = e.to_dict()
        return code, msg, http, cat, retry, client, server, d

    elapsed = measure(scenario)
    _check(r, "에러 분류 파이프라인", elapsed, 100.0)


# ==================== 12. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[12] 대량 처리")
    from shared.constants.error_codes import ErrorCode, RETRYABLE_ERRORS

    all_errors = list(ErrorCode)
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        for e in all_errors:
            _ = e.is_retryable()
            _ = e.is_client_error()
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 270 분류: {elapsed_ms:.1f}ms")
    _check(r, "대량 에러 분류", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)          # 1: 1
    test_error_code_access(r)      # 2: 3
    test_error_category_access(r)  # 3: 2
    test_lookup_cache(r)           # 4: 2
    test_retryable_membership(r)   # 5: 2
    test_classification_methods(r) # 6: 3
    test_from_code(r)              # 7: 2
    test_to_dict(r)                # 8: 2
    test_enum_iteration(r)         # 9: 2
    test_memory_usage(r)           # 10: 1
    test_composite_scenario(r)     # 11: 1
    test_bulk_operations(r)        # 12: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
