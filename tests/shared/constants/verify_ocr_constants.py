# -*- coding: utf-8 -*-
"""ocr_constants.py v1.1.0 검증 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name} - {msg}")
        failed += 1


print("=" * 70)
print("ocr_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.ocr_constants import (
        OCRModel, TextDetectionModel, OCRStatus,
        MIN_OCR_CONFIDENCE, JERSEY_NUMBER_MIN, JERSEY_NUMBER_MAX,
        OCR_FRAME_INTERVAL,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        OCRModel, TextDetectionModel, OCRStatus,
        MIN_OCR_CONFIDENCE, JERSEY_NUMBER_MIN, JERSEY_NUMBER_MAX,
        OCR_FRAME_INTERVAL,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: OCRModel 6 멤버
check(
    "T-03: OCRModel 6 멤버",
    len(OCRModel) == 6,
    f"실제: {len(OCRModel)}",
)

# T-04: TextDetectionModel 5 멤버
check(
    "T-04: TextDetectionModel 5 멤버",
    len(TextDetectionModel) == 5,
    f"실제: {len(TextDetectionModel)}",
)

# T-05: OCRStatus 7 멤버
check(
    "T-05: OCRStatus 7 멤버",
    len(OCRStatus) == 7,
    f"실제: {len(OCRStatus)}",
)

# T-06: OCRModel.input_size 모든 멤버
ok = all(
    isinstance(m.input_size, tuple) and len(m.input_size) == 2
    for m in OCRModel
)
check("T-06: OCRModel.input_size", ok)

# T-07: OCRModel.supports_batch
check(
    "T-07: OCRModel.supports_batch",
    OCRModel.CRNN.supports_batch is True
    and OCRModel.TROCR.supports_batch is True
    and OCRModel.TESSERACT.supports_batch is False
    and OCRModel.CUSTOM_JERSEY.supports_batch is False,
)

# T-08: OCRModel.is_transformer_based
check(
    "T-08: OCRModel.is_transformer_based",
    OCRModel.TROCR.is_transformer_based is True
    and OCRModel.CRNN.is_transformer_based is False,
)

# T-09: OCRModel.to_korean
check(
    "T-09: OCRModel.to_korean",
    OCRModel.CUSTOM_JERSEY.to_korean() == "커스텀 등번호 모델"
    and all(isinstance(m.to_korean(), str) and len(m.to_korean()) > 0 for m in OCRModel),
)

# T-10: TextDetectionModel.supports_rotated
check(
    "T-10: TextDetectionModel.supports_rotated",
    TextDetectionModel.EAST.supports_rotated is True
    and TextDetectionModel.CRAFT.supports_rotated is True
    and TextDetectionModel.DBNET.supports_rotated is True
    and TextDetectionModel.CTPN.supports_rotated is False
    and TextDetectionModel.PSENET.supports_rotated is False,
)

# T-11: TextDetectionModel.output_type
check(
    "T-11: TextDetectionModel.output_type",
    TextDetectionModel.CTPN.output_type == "bbox"
    and TextDetectionModel.EAST.output_type == "polygon"
    and all(isinstance(m.output_type, str) for m in TextDetectionModel),
)

# T-12: TextDetectionModel.to_korean
check(
    "T-12: TextDetectionModel.to_korean",
    TextDetectionModel.DBNET.to_korean() == "DBNet"
    and all(isinstance(m.to_korean(), str) and len(m.to_korean()) > 0 for m in TextDetectionModel),
)

# T-13: OCRStatus.is_successful
check(
    "T-13: OCRStatus.is_successful",
    OCRStatus.RECOGNIZED.is_successful is True
    and all(s.is_successful is False for s in OCRStatus if s != OCRStatus.RECOGNIZED),
)

# T-14: OCRStatus.needs_retry
check(
    "T-14: OCRStatus.needs_retry",
    OCRStatus.LOW_CONFIDENCE.needs_retry is True
    and OCRStatus.TIMEOUT.needs_retry is True
    and OCRStatus.RECOGNIZED.needs_retry is False
    and OCRStatus.INVALID.needs_retry is False,
)

# T-15: OCRStatus.is_terminal
check(
    "T-15: OCRStatus.is_terminal",
    OCRStatus.RECOGNIZED.is_terminal is True
    and OCRStatus.NOT_DETECTED.is_terminal is True
    and OCRStatus.INVALID.is_terminal is True
    and OCRStatus.PROCESSING.is_terminal is False
    and OCRStatus.TIMEOUT.is_terminal is False,
)

# T-16: OCRStatus.to_korean
check(
    "T-16: OCRStatus.to_korean",
    OCRStatus.RECOGNIZED.to_korean() == "인식됨"
    and OCRStatus.TIMEOUT.to_korean() == "시간 초과"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in OCRStatus),
)

# T-17: GRAYSCALE_WEIGHTS 합 = 1.0
from shared.constants.ocr_constants import GRAYSCALE_WEIGHTS
gs = sum(GRAYSCALE_WEIGHTS)
check("T-17: GRAYSCALE_WEIGHTS 합 = 1.0", abs(gs - 1.0) < 1e-9, f"합: {gs}")

# T-18: SIMILAR_CHAR_MAPPING 존재 및 타입
from shared.constants.ocr_constants import SIMILAR_CHAR_MAPPING
check(
    "T-18: SIMILAR_CHAR_MAPPING",
    isinstance(SIMILAR_CHAR_MAPPING, dict)
    and len(SIMILAR_CHAR_MAPPING) == 12
    and SIMILAR_CHAR_MAPPING["O"] == "0"
    and SIMILAR_CHAR_MAPPING["I"] == "1",
)

# T-19: 등번호 범위 검증
check(
    "T-19: 등번호 범위",
    JERSEY_NUMBER_MIN == 0
    and JERSEY_NUMBER_MAX == 99,
)

# T-20: CRNN/TrOCR 입력 크기 참조 일관성
from shared.constants.ocr_constants import CRNN_INPUT_SIZE, TROCR_INPUT_SIZE
check(
    "T-20: 모델 입력 크기 참조 일관성",
    OCRModel.CRNN.input_size == CRNN_INPUT_SIZE
    and OCRModel.TROCR.input_size == TROCR_INPUT_SIZE,
)

# T-21: __all__ 개수 및 존재 확인
import shared.constants.ocr_constants as oc
all_list = oc.__all__
all_exist = all(hasattr(oc, name) for name in all_list)
check(
    f"T-21: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-22: .update() 패턴 부재
import inspect
source = inspect.getsource(oc)
check(
    "T-22: .update() 및 빈 선언 패턴 없음",
    ".update(" not in source
    and "= {}" not in source
    and "= frozenset()" not in source,
)

# T-23: frozenset 캐시 타입 검증
from shared.constants.ocr_constants import (
    _OCR_MODEL_SUPPORTS_BATCH,
    _TEXT_DETECTION_SUPPORTS_ROTATED,
    _OCR_STATUS_NEEDS_RETRY,
    _OCR_STATUS_IS_TERMINAL,
)
check(
    "T-23: 4개 frozenset 캐시 타입",
    isinstance(_OCR_MODEL_SUPPORTS_BATCH, frozenset)
    and isinstance(_TEXT_DETECTION_SUPPORTS_ROTATED, frozenset)
    and isinstance(_OCR_STATUS_NEEDS_RETRY, frozenset)
    and isinstance(_OCR_STATUS_IS_TERMINAL, frozenset),
)

# T-24: dict 캐시 완전성
from shared.constants.ocr_constants import (
    _OCR_MODEL_INPUT_SIZE_MAP,
    _OCR_MODEL_KOREAN_MAP,
    _TEXT_DETECTION_OUTPUT_MAP,
    _TEXT_DETECTION_KOREAN_MAP,
    _OCR_STATUS_KOREAN_MAP,
)
check(
    "T-24: 5개 dict 캐시 완전성",
    len(_OCR_MODEL_INPUT_SIZE_MAP) == len(OCRModel)
    and len(_OCR_MODEL_KOREAN_MAP) == len(OCRModel)
    and len(_TEXT_DETECTION_OUTPUT_MAP) == len(TextDetectionModel)
    and len(_TEXT_DETECTION_KOREAN_MAP) == len(TextDetectionModel)
    and len(_OCR_STATUS_KOREAN_MAP) == len(OCRStatus),
)

# T-25: 버전 검증
check("T-25: 버전 1.1.0", oc.__version__ == "1.1.0", f"실제: {oc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
