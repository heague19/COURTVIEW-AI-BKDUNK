# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_ocr_constants_perf.py

OCR 상수 모듈 성능 테스트
- 모듈 임포트 시간
- Final 상수 접근 (58개 public Final, 12개 섹션)
- tuple 상수 접근 (GRAYSCALE_WEIGHTS, WHITE_TEXT_HSV_LOWER, CRNN_INPUT_SIZE)
- OCRModel 속성 (input_size, supports_batch, is_transformer_based, to_korean)
- TextDetectionModel 속성 (supports_rotated, output_type, to_korean)
- OCRStatus 속성 (is_successful, needs_retry, is_terminal, to_korean)
- frozenset 멤버십 (4 frozenset 캐시)
- Enum 순회 (6 / 5 / 7)
- 메모리 사용량
- 복합 시나리오
- 대량 처리

성능 기준:
- 모듈 임포트: < 500ms
- 상수/속성 접근: < 1us
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
    mod_name = "shared.constants.ocr_constants"
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
    from shared.constants.ocr_constants import (
        MIN_OCR_CONFIDENCE,
        HIGH_OCR_CONFIDENCE,
        OCR_FRAME_INTERVAL,
        JERSEY_NUMBER_MAX,
        OCR_BATCH_SIZE,
    )

    elapsed = measure(lambda: MIN_OCR_CONFIDENCE)
    _check(r, "MIN_OCR_CONFIDENCE", elapsed, 1.0)

    elapsed = measure(lambda: HIGH_OCR_CONFIDENCE)
    _check(r, "HIGH_OCR_CONFIDENCE", elapsed, 1.0)

    elapsed = measure(lambda: OCR_FRAME_INTERVAL)
    _check(r, "OCR_FRAME_INTERVAL", elapsed, 1.0)

    elapsed = measure(lambda: JERSEY_NUMBER_MAX)
    _check(r, "JERSEY_NUMBER_MAX", elapsed, 1.0)

    elapsed = measure(lambda: OCR_BATCH_SIZE)
    _check(r, "OCR_BATCH_SIZE", elapsed, 1.0)


# ==================== 3. tuple 상수 접근 ====================
def test_tuple_constant_access(r: PerfResult) -> None:
    print("\n[3] tuple 상수 접근")
    from shared.constants.ocr_constants import (
        GRAYSCALE_WEIGHTS,
        WHITE_TEXT_HSV_LOWER,
        CRNN_INPUT_SIZE,
    )

    elapsed = measure(lambda: GRAYSCALE_WEIGHTS)
    _check(r, "GRAYSCALE_WEIGHTS", elapsed, 1.0)

    elapsed = measure(lambda: WHITE_TEXT_HSV_LOWER)
    _check(r, "WHITE_TEXT_HSV_LOWER", elapsed, 1.0)

    elapsed = measure(lambda: CRNN_INPUT_SIZE)
    _check(r, "CRNN_INPUT_SIZE", elapsed, 1.0)


# ==================== 4. OCRModel 속성 ====================
def test_ocr_model_properties(r: PerfResult) -> None:
    print("\n[4] OCRModel 속성")
    from shared.constants.ocr_constants import OCRModel

    crnn = OCRModel.CRNN
    elapsed = measure(lambda: crnn.input_size)
    _check(r, "input_size (CRNN)", elapsed, 1.0)

    trocr = OCRModel.TROCR
    elapsed = measure(lambda: trocr.supports_batch)
    _check(r, "supports_batch (TROCR)", elapsed, 1.0)

    elapsed = measure(lambda: trocr.is_transformer_based)
    _check(r, "is_transformer_based (TROCR)", elapsed, 1.0)

    easy_ocr = OCRModel.EASY_OCR
    elapsed = measure(lambda: easy_ocr.to_korean())
    _check(r, "to_korean (EASY_OCR)", elapsed, 1.0)


# ==================== 5. TextDetectionModel 속성 ====================
def test_text_detection_model_properties(r: PerfResult) -> None:
    print("\n[5] TextDetectionModel 속성")
    from shared.constants.ocr_constants import TextDetectionModel

    east = TextDetectionModel.EAST
    elapsed = measure(lambda: east.supports_rotated)
    _check(r, "supports_rotated (EAST)", elapsed, 1.0)

    ctpn = TextDetectionModel.CTPN
    elapsed = measure(lambda: ctpn.output_type)
    _check(r, "output_type (CTPN)", elapsed, 1.0)

    craft = TextDetectionModel.CRAFT
    elapsed = measure(lambda: craft.to_korean())
    _check(r, "to_korean (CRAFT)", elapsed, 1.0)


# ==================== 6. OCRStatus 속성 ====================
def test_ocr_status_properties(r: PerfResult) -> None:
    print("\n[6] OCRStatus 속성")
    from shared.constants.ocr_constants import OCRStatus

    recognized = OCRStatus.RECOGNIZED
    elapsed = measure(lambda: recognized.is_successful)
    _check(r, "is_successful (RECOGNIZED)", elapsed, 1.0)

    low_conf = OCRStatus.LOW_CONFIDENCE
    elapsed = measure(lambda: low_conf.needs_retry)
    _check(r, "needs_retry (LOW_CONFIDENCE)", elapsed, 1.0)

    not_detected = OCRStatus.NOT_DETECTED
    elapsed = measure(lambda: not_detected.is_terminal)
    _check(r, "is_terminal (NOT_DETECTED)", elapsed, 1.0)

    timeout = OCRStatus.TIMEOUT
    elapsed = measure(lambda: timeout.to_korean())
    _check(r, "to_korean (TIMEOUT)", elapsed, 1.0)


# ==================== 7. frozenset 멤버십 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    print("\n[7] frozenset 멤버십")
    from shared.constants.ocr_constants import (
        OCRModel, TextDetectionModel, OCRStatus,
    )

    # _OCR_MODEL_SUPPORTS_BATCH (supports_batch 속성 경유)
    crnn = OCRModel.CRNN
    elapsed = measure(lambda: crnn.supports_batch)
    _check(r, "_OCR_MODEL_SUPPORTS_BATCH 멤버 (CRNN)", elapsed, 1.0)

    tesseract = OCRModel.TESSERACT
    elapsed = measure(lambda: tesseract.supports_batch)
    _check(r, "_OCR_MODEL_SUPPORTS_BATCH 비멤버 (TESSERACT)", elapsed, 1.0)

    # _TEXT_DETECTION_SUPPORTS_ROTATED (supports_rotated 속성 경유)
    east = TextDetectionModel.EAST
    elapsed = measure(lambda: east.supports_rotated)
    _check(r, "_TEXT_DETECTION_SUPPORTS_ROTATED 멤버 (EAST)", elapsed, 1.0)

    ctpn = TextDetectionModel.CTPN
    elapsed = measure(lambda: ctpn.supports_rotated)
    _check(r, "_TEXT_DETECTION_SUPPORTS_ROTATED 비멤버 (CTPN)", elapsed, 1.0)

    # _OCR_STATUS_NEEDS_RETRY (needs_retry 속성 경유)
    timeout = OCRStatus.TIMEOUT
    elapsed = measure(lambda: timeout.needs_retry)
    _check(r, "_OCR_STATUS_NEEDS_RETRY 멤버 (TIMEOUT)", elapsed, 1.0)

    # _OCR_STATUS_IS_TERMINAL (is_terminal 속성 경유)
    invalid = OCRStatus.INVALID
    elapsed = measure(lambda: invalid.is_terminal)
    _check(r, "_OCR_STATUS_IS_TERMINAL 멤버 (INVALID)", elapsed, 1.0)

    processing = OCRStatus.PROCESSING
    elapsed = measure(lambda: processing.is_terminal)
    _check(r, "_OCR_STATUS_IS_TERMINAL 비멤버 (PROCESSING)", elapsed, 1.0)


# ==================== 8. Enum 순회 ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[8] Enum 순회")
    from shared.constants.ocr_constants import (
        OCRModel, TextDetectionModel, OCRStatus,
    )

    elapsed = measure(lambda: list(OCRModel))
    r.info(f"OCRModel 멤버 수: {len(list(OCRModel))}")
    _check(r, "OCRModel(6) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(TextDetectionModel))
    r.info(f"TextDetectionModel 멤버 수: {len(list(TextDetectionModel))}")
    _check(r, "TextDetectionModel(5) 순회", elapsed, 5.0)

    elapsed = measure(lambda: list(OCRStatus))
    r.info(f"OCRStatus 멤버 수: {len(list(OCRStatus))}")
    _check(r, "OCRStatus(7) 순회", elapsed, 5.0)


# ==================== 9. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[9] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.ocr_constants"
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
    from shared.constants.ocr_constants import (
        OCRModel, TextDetectionModel, OCRStatus,
        MIN_OCR_CONFIDENCE, OCR_FRAME_INTERVAL, OCR_BATCH_SIZE,
        SIMILAR_CHAR_MAPPING,
    )

    def scenario():
        # OCRModel 속성 접근
        crnn = OCRModel.CRNN
        _ = crnn.input_size
        _ = crnn.supports_batch
        _ = crnn.is_transformer_based
        _ = crnn.to_korean()

        # TextDetectionModel 속성 접근
        craft = TextDetectionModel.CRAFT
        _ = craft.supports_rotated
        _ = craft.output_type
        _ = craft.to_korean()

        # OCRStatus 속성 접근
        recognized = OCRStatus.RECOGNIZED
        _ = recognized.is_successful
        _ = recognized.needs_retry
        _ = recognized.is_terminal
        _ = recognized.to_korean()

        # Final 상수 접근
        _ = MIN_OCR_CONFIDENCE
        _ = OCR_FRAME_INTERVAL
        _ = OCR_BATCH_SIZE

        # SIMILAR_CHAR_MAPPING 조회
        _ = SIMILAR_CHAR_MAPPING.get("O", "")
        _ = SIMILAR_CHAR_MAPPING.get("I", "")
        _ = SIMILAR_CHAR_MAPPING.get("Z", "")

        return recognized

    elapsed = measure(scenario)
    _check(r, "3 Enum 속성 + 상수 + SIMILAR_CHAR_MAPPING 조회", elapsed, 50.0)


# ==================== 11. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[11] 대량 처리")
    from shared.constants.ocr_constants import (
        OCRModel, TextDetectionModel, OCRStatus,
    )

    all_ocr_models = list(OCRModel)                  # 6
    all_text_models = list(TextDetectionModel)        # 5
    all_statuses = list(OCRStatus)                    # 7  -> 총 18 멤버

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        # OCRModel: 4속성 x 6멤버
        for model in all_ocr_models:
            _ = model.input_size
            _ = model.supports_batch
            _ = model.is_transformer_based
            _ = model.to_korean()

        # TextDetectionModel: 3속성 x 5멤버
        for model in all_text_models:
            _ = model.supports_rotated
            _ = model.output_type
            _ = model.to_korean()

        # OCRStatus: 4속성 x 7멤버
        for status in all_statuses:
            _ = status.is_successful
            _ = status.needs_retry
            _ = status.is_terminal
            _ = status.to_korean()
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 18 Enum 멤버 전체 속성: {elapsed_ms:.1f}ms")
    _check(r, "대량 처리 (1K x 18 멤버)", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)                         # 1:  1
    test_constant_access(r)                       # 2:  5
    test_tuple_constant_access(r)                 # 3:  3
    test_ocr_model_properties(r)                  # 4:  4
    test_text_detection_model_properties(r)       # 5:  3
    test_ocr_status_properties(r)                 # 6:  4
    test_frozenset_membership(r)                  # 7:  7
    test_enum_iteration(r)                        # 8:  3
    test_memory_usage(r)                          # 9:  1
    test_composite_scenario(r)                    # 10: 1
    test_bulk_operations(r)                       # 11: 1
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
