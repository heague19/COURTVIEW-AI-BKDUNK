# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/performance
파일: test_base_exception_perf.py
설명: base_exception.py 성능 테스트 (생성, 직렬화, 메서드 호출 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
    CriticalException,
)


# =============================================================================
# 성능 테스트 하네스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/반복)."""
    gc.disable()
    try:
        # 워밍업
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        # 측정
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


# =============================================================================
# 1. 생성 성능 테스트
# =============================================================================
def test_creation_perf(r: PerfResult) -> None:
    """예외 인스턴스 생성 성능."""
    # CourtViewException 기본 생성
    elapsed = measure(lambda: CourtViewException(), 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("CourtViewException() 기본 생성", elapsed, limit)
    else:
        r.fail("CourtViewException() 기본 생성", elapsed, limit)

    # CourtViewException 전체 인수 생성
    cause = ValueError("test")
    elapsed = measure(
        lambda: CourtViewException(
            ErrorCode.ANALYSIS_ERROR, "msg",
            details={"k": "v"}, context={"r": "id"}, cause=cause
        ), 50000
    )
    limit = 100.0
    if elapsed < limit:
        r.ok("CourtViewException() 전체 인수", elapsed, limit)
    else:
        r.fail("CourtViewException() 전체 인수", elapsed, limit)

    # RetryableException 생성
    elapsed = measure(
        lambda: RetryableException(
            ErrorCode.SERVICE_UNAVAILABLE, "msg",
            retry_after=5.0, max_retries=5
        ), 50000
    )
    limit = 60.0
    if elapsed < limit:
        r.ok("RetryableException() 생성", elapsed, limit)
    else:
        r.fail("RetryableException() 생성", elapsed, limit)

    # NonRetryableException 생성
    elapsed = measure(
        lambda: NonRetryableException(ErrorCode.VALIDATION_ERROR, "msg"),
        50000
    )
    limit = 50.0
    if elapsed < limit:
        r.ok("NonRetryableException() 생성", elapsed, limit)
    else:
        r.fail("NonRetryableException() 생성", elapsed, limit)

    # CriticalException 생성
    elapsed = measure(
        lambda: CriticalException(
            ErrorCode.INTERNAL_ERROR, "msg",
            alert_required=True, severity=5
        ), 50000
    )
    limit = 60.0
    if elapsed < limit:
        r.ok("CriticalException() 생성", elapsed, limit)
    else:
        r.fail("CriticalException() 생성", elapsed, limit)


# =============================================================================
# 2. 프로퍼티 접근 성능
# =============================================================================
def test_property_access_perf(r: PerfResult) -> None:
    """프로퍼티 접근 성능."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR, "테스트")

    # code 프로퍼티
    elapsed = measure(lambda: e.code, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("code 프로퍼티 접근", elapsed, limit)
    else:
        r.fail("code 프로퍼티 접근", elapsed, limit)

    # http_status 프로퍼티
    elapsed = measure(lambda: e.http_status, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("http_status 프로퍼티 접근", elapsed, limit)
    else:
        r.fail("http_status 프로퍼티 접근", elapsed, limit)

    # error_name 프로퍼티
    elapsed = measure(lambda: e.error_name, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("error_name 프로퍼티 접근", elapsed, limit)
    else:
        r.fail("error_name 프로퍼티 접근", elapsed, limit)


# =============================================================================
# 3. 직렬화 성능
# =============================================================================
def test_serialization_perf(r: PerfResult) -> None:
    """직렬화 메서드 성능."""
    cause = ValueError("원인")
    e = CourtViewException(
        ErrorCode.ANALYSIS_ERROR, "분석 실패",
        details={"video_id": "v001", "frame": 100},
        context={"request_id": "req-001"},
        cause=cause,
    )

    # to_dict() 기본
    elapsed = measure(lambda: e.to_dict(), 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("to_dict() 기본", elapsed, limit)
    else:
        r.fail("to_dict() 기본", elapsed, limit)

    # to_dict(include_traceback=True)
    elapsed = measure(lambda: e.to_dict(include_traceback=True), 50000)
    limit = 35.0
    if elapsed < limit:
        r.ok("to_dict(traceback=True)", elapsed, limit)
    else:
        r.fail("to_dict(traceback=True)", elapsed, limit)

    # to_response_dict()
    elapsed = measure(lambda: e.to_response_dict(), 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("to_response_dict()", elapsed, limit)
    else:
        r.fail("to_response_dict()", elapsed, limit)

    # 최소 정보 to_dict (details/context/cause 없음)
    e_min = CourtViewException()
    elapsed = measure(lambda: e_min.to_dict(), 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("to_dict() 최소 (빈 객체)", elapsed, limit)
    else:
        r.fail("to_dict() 최소 (빈 객체)", elapsed, limit)


# =============================================================================
# 4. 메서드 체이닝 성능
# =============================================================================
def test_chaining_perf(r: PerfResult) -> None:
    """with_context/with_details 체이닝 성능."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR)

    elapsed = measure(lambda: e.with_context(key="value"), 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("with_context() 호출", elapsed, limit)
    else:
        r.fail("with_context() 호출", elapsed, limit)

    elapsed = measure(lambda: e.with_details(key="value"), 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("with_details() 호출", elapsed, limit)
    else:
        r.fail("with_details() 호출", elapsed, limit)

    # 체이닝 연속 3회
    elapsed = measure(
        lambda: (CourtViewException(ErrorCode.ANALYSIS_ERROR)
                 .with_context(a=1)
                 .with_details(b=2)
                 .with_context(c=3)),
        50000
    )
    limit = 70.0
    if elapsed < limit:
        r.ok("3단 체이닝 (생성+3호출)", elapsed, limit)
    else:
        r.fail("3단 체이닝 (생성+3호출)", elapsed, limit)


# =============================================================================
# 5. __str__ / __repr__ 성능
# =============================================================================
def test_str_repr_perf(r: PerfResult) -> None:
    """문자열 변환 성능."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR, "테스트 메시지")

    elapsed = measure(lambda: str(e), 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("__str__() 호출", elapsed, limit)
    else:
        r.fail("__str__() 호출", elapsed, limit)

    elapsed = measure(lambda: repr(e), 100000)
    limit = 15.0
    if elapsed < limit:
        r.ok("__repr__() 호출", elapsed, limit)
    else:
        r.fail("__repr__() 호출", elapsed, limit)


# =============================================================================
# 6. 하위 클래스 to_dict 성능 (추가 필드)
# =============================================================================
def test_subclass_to_dict_perf(r: PerfResult) -> None:
    """하위 클래스 to_dict 성능."""
    re = RetryableException(retry_after=3.0, max_retries=5)
    elapsed = measure(lambda: re.to_dict(), 50000)
    limit = 25.0
    if elapsed < limit:
        r.ok("RetryableException.to_dict()", elapsed, limit)
    else:
        r.fail("RetryableException.to_dict()", elapsed, limit)

    nre = NonRetryableException(ErrorCode.VALIDATION_ERROR, "오류")
    elapsed = measure(lambda: nre.to_dict(), 50000)
    limit = 25.0
    if elapsed < limit:
        r.ok("NonRetryableException.to_dict()", elapsed, limit)
    else:
        r.fail("NonRetryableException.to_dict()", elapsed, limit)

    ce = CriticalException(severity=4, alert_required=True)
    elapsed = measure(lambda: ce.to_dict(), 50000)
    limit = 25.0
    if elapsed < limit:
        r.ok("CriticalException.to_dict()", elapsed, limit)
    else:
        r.fail("CriticalException.to_dict()", elapsed, limit)


# =============================================================================
# 7. raise/catch 성능
# =============================================================================
def test_raise_catch_perf(r: PerfResult) -> None:
    """예외 raise/catch 성능."""
    def raise_and_catch():
        try:
            raise CourtViewException(ErrorCode.ANALYSIS_ERROR, "test")
        except CourtViewException:
            pass

    elapsed = measure(raise_and_catch, 50000)
    limit = 80.0
    if elapsed < limit:
        r.ok("raise + catch CourtViewException", elapsed, limit)
    else:
        r.fail("raise + catch CourtViewException", elapsed, limit)

    def raise_and_catch_critical():
        try:
            raise CriticalException(severity=5)
        except CourtViewException:
            pass

    elapsed = measure(raise_and_catch_critical, 50000)
    limit = 90.0
    if elapsed < limit:
        r.ok("raise + catch CriticalException", elapsed, limit)
    else:
        r.fail("raise + catch CriticalException", elapsed, limit)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  base_exception.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] 생성 성능 ---")
    test_creation_perf(r)

    print("\n--- [2] 프로퍼티 접근 성능 ---")
    test_property_access_perf(r)

    print("\n--- [3] 직렬화 성능 ---")
    test_serialization_perf(r)

    print("\n--- [4] 메서드 체이닝 성능 ---")
    test_chaining_perf(r)

    print("\n--- [5] __str__ / __repr__ 성능 ---")
    test_str_repr_perf(r)

    print("\n--- [6] 하위 클래스 to_dict 성능 ---")
    test_subclass_to_dict_perf(r)

    print("\n--- [7] raise/catch 성능 ---")
    test_raise_catch_perf(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
