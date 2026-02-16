# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_ocr_dto_perf.py

OCR DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도
- 메서드 호출 속도 (add_vote, add_result, resolve, to_jersey_number, as_integer)
- i18n get_name() 속도
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

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
    mod_name = "shared.dto.ocr_dto"
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
def test_ocr_result_creation(r: PerfResult) -> None:
    """OCRResult 생성 속도 (__post_init__ 포함)"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus, OCRBackend

    def create():
        OCRResult(
            text="  23  ",
            confidence=0.92,
            status=OCRStatus.SUCCESS,
            backend=OCRBackend.PADDLEOCR,
            language="ko",
            frame_index=100,
            camera_id="cam_01",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("OCRResult 생성", elapsed, limit)
    else:
        r.fail("OCRResult 생성", elapsed, limit)


def test_jersey_number_creation(r: PerfResult) -> None:
    """JerseyNumber 생성 속도"""
    from shared.dto.ocr_dto import JerseyNumber

    def create():
        JerseyNumber(
            number=23,
            confidence=0.9,
            source="back",
            person_id=5,
            frame_index=100,
            camera_id="cam_01",
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("JerseyNumber 생성", elapsed, limit)
    else:
        r.fail("JerseyNumber 생성", elapsed, limit)


def test_jersey_number_vote_creation(r: PerfResult) -> None:
    """JerseyNumberVote 생성 속도"""
    from shared.dto.ocr_dto import JerseyNumberVote

    def create():
        JerseyNumberVote(number=23)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("JerseyNumberVote 생성", elapsed, limit)
    else:
        r.fail("JerseyNumberVote 생성", elapsed, limit)


def test_multiview_ocr_result_creation(r: PerfResult) -> None:
    """MultiViewOCRResult 생성 속도"""
    from shared.dto.ocr_dto import MultiViewOCRResult

    def create():
        MultiViewOCRResult(person_id=5)

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("MultiViewOCRResult 생성", elapsed, limit)
    else:
        r.fail("MultiViewOCRResult 생성", elapsed, limit)


def test_ocr_analysis_result_creation(r: PerfResult) -> None:
    """OCRAnalysisResult 생성 속도"""
    from shared.dto.ocr_dto import OCRAnalysisResult

    def create():
        OCRAnalysisResult(
            frame_index=500,
            timestamp=16.67,
            camera_id="cam_01",
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("OCRAnalysisResult 생성", elapsed, limit)
    else:
        r.fail("OCRAnalysisResult 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_ocr_result_properties(r: PerfResult) -> None:
    """OCRResult 프로퍼티 접근 속도"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus

    res = OCRResult(text="23", confidence=0.9, status=OCRStatus.SUCCESS)

    def access():
        _ = res.is_valid
        _ = res.is_numeric
        _ = res.is_high_confidence
        _ = res.text_length

    elapsed = measure(access, 100000)
    per_call = elapsed / 4
    limit = 2.0
    if per_call < limit:
        r.ok("OCRResult 프로퍼티", per_call, limit)
    else:
        r.fail("OCRResult 프로퍼티", per_call, limit)


def test_jersey_number_properties(r: PerfResult) -> None:
    """JerseyNumber 프로퍼티 접근 속도"""
    from shared.dto.ocr_dto import JerseyNumber

    jn = JerseyNumber(number=23, confidence=0.9)

    def access():
        _ = jn.is_valid
        _ = jn.is_high_confidence
        _ = jn.is_double_digit
        _ = jn.is_single_digit
        _ = jn.display_number

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("JerseyNumber 프로퍼티", per_call, limit)
    else:
        r.fail("JerseyNumber 프로퍼티", per_call, limit)


def test_analysis_result_properties(r: PerfResult) -> None:
    """OCRAnalysisResult 프로퍼티 접근 속도"""
    from shared.dto.ocr_dto import OCRAnalysisResult, JerseyNumber

    jns = [JerseyNumber(number=i, confidence=0.7 + i * 0.05) for i in range(5)]
    ar = OCRAnalysisResult(jersey_numbers=jns)

    def access():
        _ = ar.num_jersey_numbers
        _ = ar.valid_jersey_numbers
        _ = ar.average_confidence

    elapsed = measure(access, 50000)
    per_call = elapsed / 3
    limit = 5.0
    if per_call < limit:
        r.ok("AnalysisResult 프로퍼티", per_call, limit)
    else:
        r.fail("AnalysisResult 프로퍼티", per_call, limit)


# ==================== 4. 메서드 호출 ====================
def test_as_integer(r: PerfResult) -> None:
    """OCRResult.as_integer() 속도"""
    from shared.dto.ocr_dto import OCRResult

    res = OCRResult(text="42")

    def call():
        res.as_integer()

    elapsed = measure(call, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("as_integer()", elapsed, limit)
    else:
        r.fail("as_integer()", elapsed, limit)


def test_jersey_matches(r: PerfResult) -> None:
    """JerseyNumber.matches() 속도"""
    from shared.dto.ocr_dto import JerseyNumber

    jn1 = JerseyNumber(number=23, confidence=0.9)
    jn2 = JerseyNumber(number=23, confidence=0.7)

    def call():
        jn1.matches(jn2)

    elapsed = measure(call, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("matches()", elapsed, limit)
    else:
        r.fail("matches()", elapsed, limit)


def test_i18n_get_name(r: PerfResult) -> None:
    """OCRBackend/OCRStatus i18n get_name() 속도"""
    from shared.dto.ocr_dto import OCRBackend, OCRStatus
    from shared.constants.localization import SupportedLanguage

    def call():
        OCRBackend.EASYOCR.get_name(SupportedLanguage.KO)
        OCRBackend.PADDLEOCR.get_name(SupportedLanguage.EN)
        OCRStatus.SUCCESS.get_name(SupportedLanguage.KO)
        OCRStatus.FAILED.get_name(SupportedLanguage.EN)

    elapsed = measure(call, 50000)
    per_call = elapsed / 4
    limit = 10.0
    if per_call < limit:
        r.ok("i18n get_name()", per_call, limit)
    else:
        r.fail("i18n get_name()", per_call, limit)


def test_resolve_workflow(r: PerfResult) -> None:
    """MultiViewOCRResult resolve + to_jersey_number 워크플로우 속도"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    def workflow():
        mv = MultiViewOCRResult(person_id=1)
        mv.add_result("cam_01", JerseyNumber(number=23, confidence=0.9))
        mv.add_result("cam_02", JerseyNumber(number=23, confidence=0.85))
        mv.add_result("cam_03", JerseyNumber(number=45, confidence=0.6))
        mv.resolve()
        mv.to_jersey_number()

    elapsed = measure(workflow, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("resolve 워크플로우", elapsed, limit)
    else:
        r.fail("resolve 워크플로우", elapsed, limit)


# ==================== 5. 대량 처리 ====================
def test_batch_ocr_results(r: PerfResult) -> None:
    """OCRResult 20개 배치 생성"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus

    statuses = list(OCRStatus)

    def batch():
        for i in range(20):
            OCRResult(
                text=str(i),
                confidence=0.5 + (i % 5) * 0.1,
                status=statuses[i % len(statuses)],
                frame_index=i * 30,
            )

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("OCRResult×20", elapsed, limit)
    else:
        r.fail("OCRResult×20", elapsed, limit)


def test_full_ocr_analysis_snapshot(r: PerfResult) -> None:
    """풀 OCRAnalysisResult 스냅샷 생성"""
    from shared.dto.ocr_dto import (
        OCRAnalysisResult, OCRResult, JerseyNumber,
        OCRStatus, OCRBackend,
    )

    def create():
        ocr_results = [
            OCRResult(text=str(i), confidence=0.8, status=OCRStatus.SUCCESS, backend=OCRBackend.PADDLEOCR)
            for i in range(5)
        ]
        jersey_numbers = [
            JerseyNumber(number=i * 10 + 3, confidence=0.85, person_id=i)
            for i in range(5)
        ]
        OCRAnalysisResult(
            frame_index=500,
            timestamp=16.67,
            ocr_results=ocr_results,
            jersey_numbers=jersey_numbers,
            processing_time_ms=3.5,
            camera_id="cam_01",
        )

    elapsed = measure(create, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("풀 AnalysisResult 스냅샷", elapsed, limit)
    else:
        r.fail("풀 AnalysisResult 스냅샷", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("ocr_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_ocr_result_creation(r)
    test_jersey_number_creation(r)
    test_jersey_number_vote_creation(r)
    test_multiview_ocr_result_creation(r)
    test_ocr_analysis_result_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_ocr_result_properties(r)
    test_jersey_number_properties(r)
    test_analysis_result_properties(r)

    print("\n--- 메서드 호출 ---")
    test_as_integer(r)
    test_jersey_matches(r)
    test_i18n_get_name(r)
    test_resolve_workflow(r)

    print("\n--- 대량 처리 ---")
    test_batch_ocr_results(r)
    test_full_ocr_analysis_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
