# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_ocr_constants.py

OCR (광학 문자 인식) 상수 모듈 단위 테스트
- 58개 Final 상수 정확값/타입/논리적 순서 관계 검증
- 3개 Enum 전체 멤버 이름/값, 모든 속성, to_korean 검증
- SIMILAR_CHAR_MAPPING 12개 항목 전체 검증
- GRAYSCALE_WEIGHTS ITU-R BT.601 합 = 1.0 검증
- JERSEY_NUMBER_PATTERN regex 매칭 테스트
- CRNN_INPUT_SIZE / TROCR_INPUT_SIZE 와 OCRModel.input_size 참조 일관성
- __all__ 61개 완전성 + __version__
- 에지 케이스: identity, hashable, set, iteration order,
  frozenset/dict 캐시 완전성, tuple 불변성, CTPN만 bbox,
  status flags 상호배타성

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import io
import re
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 보장
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import ocr_constants
from shared.constants.ocr_constants import (
    # OCR 신뢰도 (4개)
    MIN_OCR_CONFIDENCE,
    HIGH_OCR_CONFIDENCE,
    CONFIRMED_OCR_CONFIDENCE,
    LOW_OCR_CONFIDENCE,
    # 등번호 범위 (5개)
    JERSEY_NUMBER_MIN,
    JERSEY_NUMBER_MAX,
    FIBA_JERSEY_NUMBERS,
    NBA_JERSEY_NUMBERS,
    KBL_JERSEY_NUMBERS,
    # OCR 처리 간격 (5개)
    OCR_FRAME_INTERVAL,
    OCR_MIN_FRAME_INTERVAL,
    OCR_MAX_FRAME_INTERVAL,
    MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION,
    OCR_CONFIRMATION_CONSISTENCY_RATIO,
    # 텍스트 검출 (7개)
    TEXT_DETECTION_MIN_CONFIDENCE,
    TEXT_AREA_MIN,
    TEXT_AREA_MAX,
    TEXT_HEIGHT_MIN,
    TEXT_WIDTH_MIN,
    TEXT_ASPECT_RATIO_MIN,
    TEXT_ASPECT_RATIO_MAX,
    # 등번호 ROI (5개)
    JERSEY_ROI_TOP_OFFSET,
    JERSEY_ROI_BOTTOM_OFFSET,
    JERSEY_ROI_LEFT_OFFSET,
    JERSEY_ROI_RIGHT_OFFSET,
    JERSEY_ROI_EXPANSION,
    # 이미지 전처리 (7개)
    OCR_INPUT_MIN_HEIGHT,
    OCR_INPUT_MAX_HEIGHT,
    OCR_INPUT_STANDARD_HEIGHT,
    GRAYSCALE_WEIGHTS,
    BINARIZATION_THRESHOLD,
    ADAPTIVE_BINARIZATION_BLOCK_SIZE,
    ADAPTIVE_BINARIZATION_CONSTANT,
    # 등번호 문자 (6개)
    JERSEY_CHARSET,
    JERSEY_MAX_DIGITS,
    JERSEY_MIN_DIGITS,
    JERSEY_FONT_ASPECT_RATIO_MIN,
    JERSEY_FONT_ASPECT_RATIO_MAX,
    JERSEY_CHAR_SPACING_RATIO,
    # 색상 검출 (6개)
    JERSEY_CONTRAST_MIN,
    WHITE_TEXT_HSV_LOWER,
    WHITE_TEXT_HSV_UPPER,
    BLACK_TEXT_HSV_LOWER,
    BLACK_TEXT_HSV_UPPER,
    COLOR_CONTRAST_KERNEL_SIZE,
    # OCR 후처리 (4개)
    JERSEY_NUMBER_PATTERN,
    SIMILAR_CHAR_MAPPING,
    OCR_NMS_IOU_THRESHOLD,
    SAME_NUMBER_MERGE_DISTANCE,
    # 시간적 일관성 (3개)
    JERSEY_HISTORY_MAX_FRAMES,
    JERSEY_CHANGE_THRESHOLD_FRAMES,
    JERSEY_VOTING_WINDOW,
    # 배치 처리 (3개)
    OCR_BATCH_SIZE,
    OCR_MAX_CONCURRENT,
    OCR_TIMEOUT_MS,
    # 모델별 (3개)
    CRNN_INPUT_SIZE,
    CRNN_HIDDEN_SIZE,
    TROCR_INPUT_SIZE,
    # Enum (3개)
    OCRModel,
    TextDetectionModel,
    OCRStatus,
)


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{test_name}: {detail}" if detail else test_name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, test_name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(test_name)
        else:
            self.fail(test_name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ============================================================================
# 1. OCR 신뢰도 상수 (4개) - 정확값, 타입, 순서
# ============================================================================
def test_ocr_confidence_exact_values(r: TestResult) -> None:
    """OCR 신뢰도 4개 상수 정확값 검증"""
    r.check("MIN_OCR_CONFIDENCE == 0.5",
            MIN_OCR_CONFIDENCE == 0.5,
            f"실제: {MIN_OCR_CONFIDENCE}")
    r.check("HIGH_OCR_CONFIDENCE == 0.8",
            HIGH_OCR_CONFIDENCE == 0.8,
            f"실제: {HIGH_OCR_CONFIDENCE}")
    r.check("CONFIRMED_OCR_CONFIDENCE == 0.9",
            CONFIRMED_OCR_CONFIDENCE == 0.9,
            f"실제: {CONFIRMED_OCR_CONFIDENCE}")
    r.check("LOW_OCR_CONFIDENCE == 0.3",
            LOW_OCR_CONFIDENCE == 0.3,
            f"실제: {LOW_OCR_CONFIDENCE}")


def test_ocr_confidence_types(r: TestResult) -> None:
    """OCR 신뢰도 4개 상수 타입 검증 (float)"""
    for name, val in [
        ("MIN_OCR_CONFIDENCE", MIN_OCR_CONFIDENCE),
        ("HIGH_OCR_CONFIDENCE", HIGH_OCR_CONFIDENCE),
        ("CONFIRMED_OCR_CONFIDENCE", CONFIRMED_OCR_CONFIDENCE),
        ("LOW_OCR_CONFIDENCE", LOW_OCR_CONFIDENCE),
    ]:
        r.check(f"{name} 타입=float",
                isinstance(val, float),
                f"실제 타입: {type(val).__name__}")


def test_ocr_confidence_ordering(r: TestResult) -> None:
    """OCR 신뢰도 순서: LOW < MIN < HIGH < CONFIRMED"""
    r.check("LOW < MIN < HIGH < CONFIRMED 순서",
            LOW_OCR_CONFIDENCE < MIN_OCR_CONFIDENCE < HIGH_OCR_CONFIDENCE < CONFIRMED_OCR_CONFIDENCE,
            f"{LOW_OCR_CONFIDENCE} < {MIN_OCR_CONFIDENCE} < {HIGH_OCR_CONFIDENCE} < {CONFIRMED_OCR_CONFIDENCE}")


# ============================================================================
# 2. 등번호 범위 상수 (5개) - 정확값, 타입, tuple 검증
# ============================================================================
def test_jersey_number_range_exact_values(r: TestResult) -> None:
    """등번호 범위 정확값 검증"""
    r.check("JERSEY_NUMBER_MIN == 0",
            JERSEY_NUMBER_MIN == 0,
            f"실제: {JERSEY_NUMBER_MIN}")
    r.check("JERSEY_NUMBER_MAX == 99",
            JERSEY_NUMBER_MAX == 99,
            f"실제: {JERSEY_NUMBER_MAX}")


def test_jersey_number_range_types(r: TestResult) -> None:
    """등번호 범위 타입 검증 (int)"""
    r.check("JERSEY_NUMBER_MIN 타입=int",
            isinstance(JERSEY_NUMBER_MIN, int),
            f"실제: {type(JERSEY_NUMBER_MIN).__name__}")
    r.check("JERSEY_NUMBER_MAX 타입=int",
            isinstance(JERSEY_NUMBER_MAX, int),
            f"실제: {type(JERSEY_NUMBER_MAX).__name__}")


def test_jersey_league_tuples(r: TestResult) -> None:
    """FIBA/NBA/KBL 등번호 tuple 검증 (len=100, tuple(range(0,100)))"""
    expected = tuple(range(0, 100))
    for name, val in [
        ("FIBA_JERSEY_NUMBERS", FIBA_JERSEY_NUMBERS),
        ("NBA_JERSEY_NUMBERS", NBA_JERSEY_NUMBERS),
        ("KBL_JERSEY_NUMBERS", KBL_JERSEY_NUMBERS),
    ]:
        r.check(f"{name} 타입=tuple",
                isinstance(val, tuple),
                f"실제: {type(val).__name__}")
        r.check(f"{name} len=100",
                len(val) == 100,
                f"실제 길이: {len(val)}")
        r.check(f"{name} == tuple(range(0,100))",
                val == expected,
                f"불일치")


# ============================================================================
# 3. OCR 처리 간격 (5개) - 정확값, 타입, 순서
# ============================================================================
def test_ocr_frame_interval_exact_values(r: TestResult) -> None:
    """OCR 처리 간격 5개 상수 정확값 검증"""
    r.check("OCR_FRAME_INTERVAL == 5",
            OCR_FRAME_INTERVAL == 5,
            f"실제: {OCR_FRAME_INTERVAL}")
    r.check("OCR_MIN_FRAME_INTERVAL == 1",
            OCR_MIN_FRAME_INTERVAL == 1,
            f"실제: {OCR_MIN_FRAME_INTERVAL}")
    r.check("OCR_MAX_FRAME_INTERVAL == 30",
            OCR_MAX_FRAME_INTERVAL == 30,
            f"실제: {OCR_MAX_FRAME_INTERVAL}")
    r.check("MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION == 3",
            MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION == 3,
            f"실제: {MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION}")
    r.check("OCR_CONFIRMATION_CONSISTENCY_RATIO == 0.7",
            OCR_CONFIRMATION_CONSISTENCY_RATIO == 0.7,
            f"실제: {OCR_CONFIRMATION_CONSISTENCY_RATIO}")


def test_ocr_frame_interval_types(r: TestResult) -> None:
    """OCR 처리 간격 타입 검증"""
    for name, val, expected_type in [
        ("OCR_FRAME_INTERVAL", OCR_FRAME_INTERVAL, int),
        ("OCR_MIN_FRAME_INTERVAL", OCR_MIN_FRAME_INTERVAL, int),
        ("OCR_MAX_FRAME_INTERVAL", OCR_MAX_FRAME_INTERVAL, int),
        ("MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION", MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION, int),
        ("OCR_CONFIRMATION_CONSISTENCY_RATIO", OCR_CONFIRMATION_CONSISTENCY_RATIO, float),
    ]:
        r.check(f"{name} 타입={expected_type.__name__}",
                isinstance(val, expected_type),
                f"실제: {type(val).__name__}")


def test_ocr_frame_interval_ordering(r: TestResult) -> None:
    """OCR 처리 간격 순서: MIN_FRAME < FRAME < MAX_FRAME"""
    r.check("MIN_FRAME < FRAME < MAX_FRAME 순서",
            OCR_MIN_FRAME_INTERVAL < OCR_FRAME_INTERVAL < OCR_MAX_FRAME_INTERVAL,
            f"{OCR_MIN_FRAME_INTERVAL} < {OCR_FRAME_INTERVAL} < {OCR_MAX_FRAME_INTERVAL}")


# ============================================================================
# 4. 텍스트 검출 파라미터 (7개) - 정확값, 타입, 순서
# ============================================================================
def test_text_detection_exact_values(r: TestResult) -> None:
    """텍스트 검출 7개 상수 정확값 검증"""
    r.check("TEXT_DETECTION_MIN_CONFIDENCE == 0.5",
            TEXT_DETECTION_MIN_CONFIDENCE == 0.5,
            f"실제: {TEXT_DETECTION_MIN_CONFIDENCE}")
    r.check("TEXT_AREA_MIN == 100",
            TEXT_AREA_MIN == 100,
            f"실제: {TEXT_AREA_MIN}")
    r.check("TEXT_AREA_MAX == 50000",
            TEXT_AREA_MAX == 50000,
            f"실제: {TEXT_AREA_MAX}")
    r.check("TEXT_HEIGHT_MIN == 10",
            TEXT_HEIGHT_MIN == 10,
            f"실제: {TEXT_HEIGHT_MIN}")
    r.check("TEXT_WIDTH_MIN == 5",
            TEXT_WIDTH_MIN == 5,
            f"실제: {TEXT_WIDTH_MIN}")
    r.check("TEXT_ASPECT_RATIO_MIN == 0.2",
            TEXT_ASPECT_RATIO_MIN == 0.2,
            f"실제: {TEXT_ASPECT_RATIO_MIN}")
    r.check("TEXT_ASPECT_RATIO_MAX == 5.0",
            TEXT_ASPECT_RATIO_MAX == 5.0,
            f"실제: {TEXT_ASPECT_RATIO_MAX}")


def test_text_detection_types(r: TestResult) -> None:
    """텍스트 검출 타입 검증"""
    r.check("TEXT_DETECTION_MIN_CONFIDENCE 타입=float",
            isinstance(TEXT_DETECTION_MIN_CONFIDENCE, float),
            f"실제: {type(TEXT_DETECTION_MIN_CONFIDENCE).__name__}")
    for name, val in [
        ("TEXT_AREA_MIN", TEXT_AREA_MIN),
        ("TEXT_AREA_MAX", TEXT_AREA_MAX),
        ("TEXT_HEIGHT_MIN", TEXT_HEIGHT_MIN),
        ("TEXT_WIDTH_MIN", TEXT_WIDTH_MIN),
    ]:
        r.check(f"{name} 타입=int",
                isinstance(val, int),
                f"실제: {type(val).__name__}")
    r.check("TEXT_ASPECT_RATIO_MIN 타입=float",
            isinstance(TEXT_ASPECT_RATIO_MIN, float),
            f"실제: {type(TEXT_ASPECT_RATIO_MIN).__name__}")
    r.check("TEXT_ASPECT_RATIO_MAX 타입=float",
            isinstance(TEXT_ASPECT_RATIO_MAX, float),
            f"실제: {type(TEXT_ASPECT_RATIO_MAX).__name__}")


def test_text_detection_ordering(r: TestResult) -> None:
    """텍스트 검출 순서: AREA_MIN < AREA_MAX, ASPECT_MIN < ASPECT_MAX"""
    r.check("AREA_MIN < AREA_MAX",
            TEXT_AREA_MIN < TEXT_AREA_MAX,
            f"{TEXT_AREA_MIN} < {TEXT_AREA_MAX}")
    r.check("ASPECT_RATIO_MIN < ASPECT_RATIO_MAX",
            TEXT_ASPECT_RATIO_MIN < TEXT_ASPECT_RATIO_MAX,
            f"{TEXT_ASPECT_RATIO_MIN} < {TEXT_ASPECT_RATIO_MAX}")


# ============================================================================
# 5. 등번호 ROI (5개) - 정확값, 타입, 순서
# ============================================================================
def test_jersey_roi_exact_values(r: TestResult) -> None:
    """등번호 ROI 5개 상수 정확값 검증"""
    r.check("JERSEY_ROI_TOP_OFFSET == 0.15",
            JERSEY_ROI_TOP_OFFSET == 0.15,
            f"실제: {JERSEY_ROI_TOP_OFFSET}")
    r.check("JERSEY_ROI_BOTTOM_OFFSET == 0.55",
            JERSEY_ROI_BOTTOM_OFFSET == 0.55,
            f"실제: {JERSEY_ROI_BOTTOM_OFFSET}")
    r.check("JERSEY_ROI_LEFT_OFFSET == 0.2",
            JERSEY_ROI_LEFT_OFFSET == 0.2,
            f"실제: {JERSEY_ROI_LEFT_OFFSET}")
    r.check("JERSEY_ROI_RIGHT_OFFSET == 0.8",
            JERSEY_ROI_RIGHT_OFFSET == 0.8,
            f"실제: {JERSEY_ROI_RIGHT_OFFSET}")
    r.check("JERSEY_ROI_EXPANSION == 1.1",
            JERSEY_ROI_EXPANSION == 1.1,
            f"실제: {JERSEY_ROI_EXPANSION}")


def test_jersey_roi_types(r: TestResult) -> None:
    """등번호 ROI 타입 검증 (float)"""
    for name, val in [
        ("JERSEY_ROI_TOP_OFFSET", JERSEY_ROI_TOP_OFFSET),
        ("JERSEY_ROI_BOTTOM_OFFSET", JERSEY_ROI_BOTTOM_OFFSET),
        ("JERSEY_ROI_LEFT_OFFSET", JERSEY_ROI_LEFT_OFFSET),
        ("JERSEY_ROI_RIGHT_OFFSET", JERSEY_ROI_RIGHT_OFFSET),
        ("JERSEY_ROI_EXPANSION", JERSEY_ROI_EXPANSION),
    ]:
        r.check(f"{name} 타입=float",
                isinstance(val, float),
                f"실제: {type(val).__name__}")


def test_jersey_roi_ordering(r: TestResult) -> None:
    """등번호 ROI 순서: TOP < BOTTOM, LEFT < RIGHT"""
    r.check("TOP < BOTTOM",
            JERSEY_ROI_TOP_OFFSET < JERSEY_ROI_BOTTOM_OFFSET,
            f"{JERSEY_ROI_TOP_OFFSET} < {JERSEY_ROI_BOTTOM_OFFSET}")
    r.check("LEFT < RIGHT",
            JERSEY_ROI_LEFT_OFFSET < JERSEY_ROI_RIGHT_OFFSET,
            f"{JERSEY_ROI_LEFT_OFFSET} < {JERSEY_ROI_RIGHT_OFFSET}")


# ============================================================================
# 6. 이미지 전처리 (7개) - 정확값, 타입, 순서, ITU-R BT.601
# ============================================================================
def test_image_preprocessing_exact_values(r: TestResult) -> None:
    """이미지 전처리 7개 상수 정확값 검증"""
    r.check("OCR_INPUT_MIN_HEIGHT == 32",
            OCR_INPUT_MIN_HEIGHT == 32,
            f"실제: {OCR_INPUT_MIN_HEIGHT}")
    r.check("OCR_INPUT_MAX_HEIGHT == 128",
            OCR_INPUT_MAX_HEIGHT == 128,
            f"실제: {OCR_INPUT_MAX_HEIGHT}")
    r.check("OCR_INPUT_STANDARD_HEIGHT == 64",
            OCR_INPUT_STANDARD_HEIGHT == 64,
            f"실제: {OCR_INPUT_STANDARD_HEIGHT}")
    r.check("GRAYSCALE_WEIGHTS == (0.299, 0.587, 0.114)",
            GRAYSCALE_WEIGHTS == (0.299, 0.587, 0.114),
            f"실제: {GRAYSCALE_WEIGHTS}")
    r.check("BINARIZATION_THRESHOLD == 128",
            BINARIZATION_THRESHOLD == 128,
            f"실제: {BINARIZATION_THRESHOLD}")
    r.check("ADAPTIVE_BINARIZATION_BLOCK_SIZE == 11",
            ADAPTIVE_BINARIZATION_BLOCK_SIZE == 11,
            f"실제: {ADAPTIVE_BINARIZATION_BLOCK_SIZE}")
    r.check("ADAPTIVE_BINARIZATION_CONSTANT == 2.0",
            ADAPTIVE_BINARIZATION_CONSTANT == 2.0,
            f"실제: {ADAPTIVE_BINARIZATION_CONSTANT}")


def test_image_preprocessing_types(r: TestResult) -> None:
    """이미지 전처리 타입 검증"""
    for name, val in [
        ("OCR_INPUT_MIN_HEIGHT", OCR_INPUT_MIN_HEIGHT),
        ("OCR_INPUT_MAX_HEIGHT", OCR_INPUT_MAX_HEIGHT),
        ("OCR_INPUT_STANDARD_HEIGHT", OCR_INPUT_STANDARD_HEIGHT),
        ("BINARIZATION_THRESHOLD", BINARIZATION_THRESHOLD),
        ("ADAPTIVE_BINARIZATION_BLOCK_SIZE", ADAPTIVE_BINARIZATION_BLOCK_SIZE),
    ]:
        r.check(f"{name} 타입=int",
                isinstance(val, int),
                f"실제: {type(val).__name__}")

    r.check("GRAYSCALE_WEIGHTS 타입=tuple",
            isinstance(GRAYSCALE_WEIGHTS, tuple),
            f"실제: {type(GRAYSCALE_WEIGHTS).__name__}")
    r.check("GRAYSCALE_WEIGHTS len=3",
            len(GRAYSCALE_WEIGHTS) == 3,
            f"실제 길이: {len(GRAYSCALE_WEIGHTS)}")
    for i, w in enumerate(GRAYSCALE_WEIGHTS):
        r.check(f"GRAYSCALE_WEIGHTS[{i}] 타입=float",
                isinstance(w, float),
                f"실제: {type(w).__name__}")
    r.check("ADAPTIVE_BINARIZATION_CONSTANT 타입=float",
            isinstance(ADAPTIVE_BINARIZATION_CONSTANT, float),
            f"실제: {type(ADAPTIVE_BINARIZATION_CONSTANT).__name__}")


def test_image_preprocessing_ordering(r: TestResult) -> None:
    """이미지 전처리 순서: MIN_HEIGHT < STANDARD < MAX_HEIGHT"""
    r.check("MIN_HEIGHT < STANDARD_HEIGHT < MAX_HEIGHT",
            OCR_INPUT_MIN_HEIGHT < OCR_INPUT_STANDARD_HEIGHT < OCR_INPUT_MAX_HEIGHT,
            f"{OCR_INPUT_MIN_HEIGHT} < {OCR_INPUT_STANDARD_HEIGHT} < {OCR_INPUT_MAX_HEIGHT}")


def test_grayscale_weights_itu_bt601(r: TestResult) -> None:
    """GRAYSCALE_WEIGHTS 합 = 1.0 (ITU-R BT.601 표준)"""
    weight_sum = sum(GRAYSCALE_WEIGHTS)
    r.check("GRAYSCALE_WEIGHTS 합 == 1.0 (ITU-R BT.601)",
            abs(weight_sum - 1.0) < 1e-9,
            f"합계: {weight_sum}")


def test_adaptive_binarization_block_size_odd(r: TestResult) -> None:
    """ADAPTIVE_BINARIZATION_BLOCK_SIZE 홀수 검증"""
    r.check("ADAPTIVE_BINARIZATION_BLOCK_SIZE 홀수",
            ADAPTIVE_BINARIZATION_BLOCK_SIZE % 2 == 1,
            f"실제: {ADAPTIVE_BINARIZATION_BLOCK_SIZE} (짝수)")


# ============================================================================
# 7. 등번호 문자 특성 (6개) - 정확값, 타입, 순서
# ============================================================================
def test_jersey_char_exact_values(r: TestResult) -> None:
    """등번호 문자 6개 상수 정확값 검증"""
    r.check('JERSEY_CHARSET == "0123456789"',
            JERSEY_CHARSET == "0123456789",
            f"실제: {repr(JERSEY_CHARSET)}")
    r.check("JERSEY_CHARSET len=10",
            len(JERSEY_CHARSET) == 10,
            f"실제 길이: {len(JERSEY_CHARSET)}")
    r.check("JERSEY_MAX_DIGITS == 2",
            JERSEY_MAX_DIGITS == 2,
            f"실제: {JERSEY_MAX_DIGITS}")
    r.check("JERSEY_MIN_DIGITS == 1",
            JERSEY_MIN_DIGITS == 1,
            f"실제: {JERSEY_MIN_DIGITS}")
    r.check("JERSEY_FONT_ASPECT_RATIO_MIN == 1.2",
            JERSEY_FONT_ASPECT_RATIO_MIN == 1.2,
            f"실제: {JERSEY_FONT_ASPECT_RATIO_MIN}")
    r.check("JERSEY_FONT_ASPECT_RATIO_MAX == 2.5",
            JERSEY_FONT_ASPECT_RATIO_MAX == 2.5,
            f"실제: {JERSEY_FONT_ASPECT_RATIO_MAX}")
    r.check("JERSEY_CHAR_SPACING_RATIO == 0.1",
            JERSEY_CHAR_SPACING_RATIO == 0.1,
            f"실제: {JERSEY_CHAR_SPACING_RATIO}")


def test_jersey_char_types(r: TestResult) -> None:
    """등번호 문자 타입 검증"""
    r.check("JERSEY_CHARSET 타입=str",
            isinstance(JERSEY_CHARSET, str),
            f"실제: {type(JERSEY_CHARSET).__name__}")
    r.check("JERSEY_MAX_DIGITS 타입=int",
            isinstance(JERSEY_MAX_DIGITS, int),
            f"실제: {type(JERSEY_MAX_DIGITS).__name__}")
    r.check("JERSEY_MIN_DIGITS 타입=int",
            isinstance(JERSEY_MIN_DIGITS, int),
            f"실제: {type(JERSEY_MIN_DIGITS).__name__}")
    r.check("JERSEY_FONT_ASPECT_RATIO_MIN 타입=float",
            isinstance(JERSEY_FONT_ASPECT_RATIO_MIN, float),
            f"실제: {type(JERSEY_FONT_ASPECT_RATIO_MIN).__name__}")
    r.check("JERSEY_FONT_ASPECT_RATIO_MAX 타입=float",
            isinstance(JERSEY_FONT_ASPECT_RATIO_MAX, float),
            f"실제: {type(JERSEY_FONT_ASPECT_RATIO_MAX).__name__}")
    r.check("JERSEY_CHAR_SPACING_RATIO 타입=float",
            isinstance(JERSEY_CHAR_SPACING_RATIO, float),
            f"실제: {type(JERSEY_CHAR_SPACING_RATIO).__name__}")


def test_jersey_char_ordering(r: TestResult) -> None:
    """등번호 문자 순서: MIN_DIGITS < MAX_DIGITS, FONT_AR_MIN < FONT_AR_MAX"""
    r.check("MIN_DIGITS < MAX_DIGITS",
            JERSEY_MIN_DIGITS < JERSEY_MAX_DIGITS,
            f"{JERSEY_MIN_DIGITS} < {JERSEY_MAX_DIGITS}")
    r.check("FONT_ASPECT_RATIO_MIN < FONT_ASPECT_RATIO_MAX",
            JERSEY_FONT_ASPECT_RATIO_MIN < JERSEY_FONT_ASPECT_RATIO_MAX,
            f"{JERSEY_FONT_ASPECT_RATIO_MIN} < {JERSEY_FONT_ASPECT_RATIO_MAX}")


# ============================================================================
# 8. 색상 검출 (6개) - 정확값, 타입, HSV 범위
# ============================================================================
def test_color_detection_exact_values(r: TestResult) -> None:
    """색상 검출 6개 상수 정확값 검증"""
    r.check("JERSEY_CONTRAST_MIN == 0.3",
            JERSEY_CONTRAST_MIN == 0.3,
            f"실제: {JERSEY_CONTRAST_MIN}")
    r.check("WHITE_TEXT_HSV_LOWER == (0, 0, 180)",
            WHITE_TEXT_HSV_LOWER == (0, 0, 180),
            f"실제: {WHITE_TEXT_HSV_LOWER}")
    r.check("WHITE_TEXT_HSV_UPPER == (180, 50, 255)",
            WHITE_TEXT_HSV_UPPER == (180, 50, 255),
            f"실제: {WHITE_TEXT_HSV_UPPER}")
    r.check("BLACK_TEXT_HSV_LOWER == (0, 0, 0)",
            BLACK_TEXT_HSV_LOWER == (0, 0, 0),
            f"실제: {BLACK_TEXT_HSV_LOWER}")
    r.check("BLACK_TEXT_HSV_UPPER == (180, 50, 80)",
            BLACK_TEXT_HSV_UPPER == (180, 50, 80),
            f"실제: {BLACK_TEXT_HSV_UPPER}")
    r.check("COLOR_CONTRAST_KERNEL_SIZE == 5",
            COLOR_CONTRAST_KERNEL_SIZE == 5,
            f"실제: {COLOR_CONTRAST_KERNEL_SIZE}")


def test_color_detection_types(r: TestResult) -> None:
    """색상 검출 타입 검증"""
    r.check("JERSEY_CONTRAST_MIN 타입=float",
            isinstance(JERSEY_CONTRAST_MIN, float),
            f"실제: {type(JERSEY_CONTRAST_MIN).__name__}")
    for name, val in [
        ("WHITE_TEXT_HSV_LOWER", WHITE_TEXT_HSV_LOWER),
        ("WHITE_TEXT_HSV_UPPER", WHITE_TEXT_HSV_UPPER),
        ("BLACK_TEXT_HSV_LOWER", BLACK_TEXT_HSV_LOWER),
        ("BLACK_TEXT_HSV_UPPER", BLACK_TEXT_HSV_UPPER),
    ]:
        r.check(f"{name} 타입=tuple",
                isinstance(val, tuple),
                f"실제: {type(val).__name__}")
        r.check(f"{name} len=3",
                len(val) == 3,
                f"실제 길이: {len(val)}")
        for i, v in enumerate(val):
            r.check(f"{name}[{i}] 타입=int",
                    isinstance(v, int),
                    f"실제: {type(v).__name__}")
    r.check("COLOR_CONTRAST_KERNEL_SIZE 타입=int",
            isinstance(COLOR_CONTRAST_KERNEL_SIZE, int),
            f"실제: {type(COLOR_CONTRAST_KERNEL_SIZE).__name__}")


def test_color_contrast_kernel_size_odd(r: TestResult) -> None:
    """COLOR_CONTRAST_KERNEL_SIZE 홀수 검증"""
    r.check("COLOR_CONTRAST_KERNEL_SIZE 홀수",
            COLOR_CONTRAST_KERNEL_SIZE % 2 == 1,
            f"실제: {COLOR_CONTRAST_KERNEL_SIZE} (짝수)")


# ============================================================================
# 9. OCR 후처리 (4개) - 정확값, 타입, regex, SIMILAR_CHAR_MAPPING 전체
# ============================================================================
def test_ocr_postprocessing_exact_values(r: TestResult) -> None:
    """OCR 후처리 상수 정확값 검증"""
    r.check('JERSEY_NUMBER_PATTERN == r"^[0-9]{1,2}$"',
            JERSEY_NUMBER_PATTERN == r"^[0-9]{1,2}$",
            f"실제: {repr(JERSEY_NUMBER_PATTERN)}")
    r.check("OCR_NMS_IOU_THRESHOLD == 0.5",
            OCR_NMS_IOU_THRESHOLD == 0.5,
            f"실제: {OCR_NMS_IOU_THRESHOLD}")
    r.check("SAME_NUMBER_MERGE_DISTANCE == 20.0",
            SAME_NUMBER_MERGE_DISTANCE == 20.0,
            f"실제: {SAME_NUMBER_MERGE_DISTANCE}")


def test_ocr_postprocessing_types(r: TestResult) -> None:
    """OCR 후처리 타입 검증"""
    r.check("JERSEY_NUMBER_PATTERN 타입=str",
            isinstance(JERSEY_NUMBER_PATTERN, str),
            f"실제: {type(JERSEY_NUMBER_PATTERN).__name__}")
    r.check("SIMILAR_CHAR_MAPPING 타입=dict",
            isinstance(SIMILAR_CHAR_MAPPING, dict),
            f"실제: {type(SIMILAR_CHAR_MAPPING).__name__}")
    r.check("OCR_NMS_IOU_THRESHOLD 타입=float",
            isinstance(OCR_NMS_IOU_THRESHOLD, float),
            f"실제: {type(OCR_NMS_IOU_THRESHOLD).__name__}")
    r.check("SAME_NUMBER_MERGE_DISTANCE 타입=float",
            isinstance(SAME_NUMBER_MERGE_DISTANCE, float),
            f"실제: {type(SAME_NUMBER_MERGE_DISTANCE).__name__}")


def test_jersey_number_pattern_regex(r: TestResult) -> None:
    """JERSEY_NUMBER_PATTERN regex 매칭 테스트"""
    pattern = re.compile(JERSEY_NUMBER_PATTERN)
    # 유효한 매칭: "1", "99"
    r.check('PATTERN match "1" → True',
            pattern.match("1") is not None,
            '"1" 매칭 실패')
    r.check('PATTERN match "99" → True',
            pattern.match("99") is not None,
            '"99" 매칭 실패')
    r.check('PATTERN match "0" → True',
            pattern.match("0") is not None,
            '"0" 매칭 실패')
    r.check('PATTERN match "05" → True',
            pattern.match("05") is not None,
            '"05" 매칭 실패')
    # 무효한 매칭: "100", "abc", "", "-1"
    r.check('PATTERN match "100" → False',
            pattern.match("100") is None,
            '"100" 매칭됨 (오류)')
    r.check('PATTERN match "abc" → False',
            pattern.match("abc") is None,
            '"abc" 매칭됨 (오류)')
    r.check('PATTERN match "" → False',
            pattern.match("") is None,
            '"" 매칭됨 (오류)')
    r.check('PATTERN match "-1" → False',
            pattern.match("-1") is None,
            '"-1" 매칭됨 (오류)')


def test_similar_char_mapping_complete(r: TestResult) -> None:
    """SIMILAR_CHAR_MAPPING 12개 항목 전체 검증"""
    expected = {
        "O": "0", "o": "0",
        "I": "1", "l": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "B": "8",
        "G": "6",
        "g": "9", "q": "9",
    }
    r.check("SIMILAR_CHAR_MAPPING 항목 수 == 12",
            len(SIMILAR_CHAR_MAPPING) == 12,
            f"실제: {len(SIMILAR_CHAR_MAPPING)}")
    r.check("SIMILAR_CHAR_MAPPING == 기대 매핑",
            SIMILAR_CHAR_MAPPING == expected,
            f"차이 키: {set(SIMILAR_CHAR_MAPPING.keys()) ^ set(expected.keys())}")
    # 개별 항목 검증
    for key, val in expected.items():
        r.check(f"SIMILAR_CHAR_MAPPING['{key}'] == '{val}'",
                SIMILAR_CHAR_MAPPING.get(key) == val,
                f"실제: {SIMILAR_CHAR_MAPPING.get(key, 'MISSING')}")


# ============================================================================
# 10. 시간적 일관성 (3개) - 정확값, 타입
# ============================================================================
def test_temporal_consistency_exact_values(r: TestResult) -> None:
    """시간적 일관성 3개 상수 정확값 검증"""
    r.check("JERSEY_HISTORY_MAX_FRAMES == 30",
            JERSEY_HISTORY_MAX_FRAMES == 30,
            f"실제: {JERSEY_HISTORY_MAX_FRAMES}")
    r.check("JERSEY_CHANGE_THRESHOLD_FRAMES == 10",
            JERSEY_CHANGE_THRESHOLD_FRAMES == 10,
            f"실제: {JERSEY_CHANGE_THRESHOLD_FRAMES}")
    r.check("JERSEY_VOTING_WINDOW == 15",
            JERSEY_VOTING_WINDOW == 15,
            f"실제: {JERSEY_VOTING_WINDOW}")


def test_temporal_consistency_types(r: TestResult) -> None:
    """시간적 일관성 타입 검증 (int)"""
    for name, val in [
        ("JERSEY_HISTORY_MAX_FRAMES", JERSEY_HISTORY_MAX_FRAMES),
        ("JERSEY_CHANGE_THRESHOLD_FRAMES", JERSEY_CHANGE_THRESHOLD_FRAMES),
        ("JERSEY_VOTING_WINDOW", JERSEY_VOTING_WINDOW),
    ]:
        r.check(f"{name} 타입=int",
                isinstance(val, int),
                f"실제: {type(val).__name__}")


# ============================================================================
# 11. 배치 처리 (3개) - 정확값, 타입
# ============================================================================
def test_batch_processing_exact_values(r: TestResult) -> None:
    """배치 처리 3개 상수 정확값 검증"""
    r.check("OCR_BATCH_SIZE == 16",
            OCR_BATCH_SIZE == 16,
            f"실제: {OCR_BATCH_SIZE}")
    r.check("OCR_MAX_CONCURRENT == 8",
            OCR_MAX_CONCURRENT == 8,
            f"실제: {OCR_MAX_CONCURRENT}")
    r.check("OCR_TIMEOUT_MS == 500",
            OCR_TIMEOUT_MS == 500,
            f"실제: {OCR_TIMEOUT_MS}")


def test_batch_processing_types(r: TestResult) -> None:
    """배치 처리 타입 검증 (int)"""
    for name, val in [
        ("OCR_BATCH_SIZE", OCR_BATCH_SIZE),
        ("OCR_MAX_CONCURRENT", OCR_MAX_CONCURRENT),
        ("OCR_TIMEOUT_MS", OCR_TIMEOUT_MS),
    ]:
        r.check(f"{name} 타입=int",
                isinstance(val, int),
                f"실제: {type(val).__name__}")


# ============================================================================
# 12. 모델별 파라미터 (3개) - 정확값, 타입
# ============================================================================
def test_model_params_exact_values(r: TestResult) -> None:
    """모델별 3개 상수 정확값 검증"""
    r.check("CRNN_INPUT_SIZE == (32, 100)",
            CRNN_INPUT_SIZE == (32, 100),
            f"실제: {CRNN_INPUT_SIZE}")
    r.check("CRNN_HIDDEN_SIZE == 256",
            CRNN_HIDDEN_SIZE == 256,
            f"실제: {CRNN_HIDDEN_SIZE}")
    r.check("TROCR_INPUT_SIZE == (384, 384)",
            TROCR_INPUT_SIZE == (384, 384),
            f"실제: {TROCR_INPUT_SIZE}")


def test_model_params_types(r: TestResult) -> None:
    """모델별 타입 검증"""
    r.check("CRNN_INPUT_SIZE 타입=tuple",
            isinstance(CRNN_INPUT_SIZE, tuple),
            f"실제: {type(CRNN_INPUT_SIZE).__name__}")
    r.check("CRNN_INPUT_SIZE len=2",
            len(CRNN_INPUT_SIZE) == 2,
            f"실제 길이: {len(CRNN_INPUT_SIZE)}")
    for i, v in enumerate(CRNN_INPUT_SIZE):
        r.check(f"CRNN_INPUT_SIZE[{i}] 타입=int",
                isinstance(v, int),
                f"실제: {type(v).__name__}")
    r.check("CRNN_HIDDEN_SIZE 타입=int",
            isinstance(CRNN_HIDDEN_SIZE, int),
            f"실제: {type(CRNN_HIDDEN_SIZE).__name__}")
    r.check("TROCR_INPUT_SIZE 타입=tuple",
            isinstance(TROCR_INPUT_SIZE, tuple),
            f"실제: {type(TROCR_INPUT_SIZE).__name__}")
    r.check("TROCR_INPUT_SIZE len=2",
            len(TROCR_INPUT_SIZE) == 2,
            f"실제 길이: {len(TROCR_INPUT_SIZE)}")
    for i, v in enumerate(TROCR_INPUT_SIZE):
        r.check(f"TROCR_INPUT_SIZE[{i}] 타입=int",
                isinstance(v, int),
                f"실제: {type(v).__name__}")


# ============================================================================
# 13. OCRModel Enum (6멤버) - 이름/값, 속성, to_korean, input_size 일관성
# ============================================================================
def test_ocrmodel_members(r: TestResult) -> None:
    """OCRModel 6멤버 이름/값 검증"""
    expected = {
        "CRNN": "crnn",
        "TROCR": "trocr",
        "EASY_OCR": "easy_ocr",
        "PADDLE_OCR": "paddle_ocr",
        "TESSERACT": "tesseract",
        "CUSTOM_JERSEY": "custom_jersey",
    }
    members = {m.name: m.value for m in OCRModel}
    r.check("OCRModel 멤버 수 == 6",
            len(members) == 6,
            f"실제: {len(members)}")
    r.check("OCRModel 멤버 이름/값 일치",
            members == expected,
            f"차이: {set(members.keys()) ^ set(expected.keys())}")
    # Enum 기본 검증
    r.check("OCRModel은 Enum 서브클래스",
            issubclass(OCRModel, Enum),
            "")


def test_ocrmodel_input_size(r: TestResult) -> None:
    """OCRModel.input_size 속성 검증 (6멤버 모두)"""
    expected_sizes = {
        OCRModel.CRNN: (32, 100),
        OCRModel.TROCR: (384, 384),
        OCRModel.EASY_OCR: (64, 256),
        OCRModel.PADDLE_OCR: (48, 320),
        OCRModel.TESSERACT: (32, 128),
        OCRModel.CUSTOM_JERSEY: (64, 128),
    }
    for member, expected_size in expected_sizes.items():
        r.check(f"OCRModel.{member.name}.input_size == {expected_size}",
                member.input_size == expected_size,
                f"실제: {member.input_size}")


def test_ocrmodel_input_size_consistency_with_constants(r: TestResult) -> None:
    """OCRModel.CRNN/TROCR input_size와 CRNN_INPUT_SIZE/TROCR_INPUT_SIZE 참조 일관성"""
    r.check("OCRModel.CRNN.input_size is CRNN_INPUT_SIZE",
            OCRModel.CRNN.input_size is CRNN_INPUT_SIZE,
            f"identity 불일치: {OCRModel.CRNN.input_size} vs {CRNN_INPUT_SIZE}")
    r.check("OCRModel.TROCR.input_size is TROCR_INPUT_SIZE",
            OCRModel.TROCR.input_size is TROCR_INPUT_SIZE,
            f"identity 불일치: {OCRModel.TROCR.input_size} vs {TROCR_INPUT_SIZE}")


def test_ocrmodel_supports_batch(r: TestResult) -> None:
    """OCRModel.supports_batch: CRNN/TROCR/EASY_OCR/PADDLE_OCR→True, TESSERACT/CUSTOM_JERSEY→False"""
    batch_true = {OCRModel.CRNN, OCRModel.TROCR, OCRModel.EASY_OCR, OCRModel.PADDLE_OCR}
    batch_false = {OCRModel.TESSERACT, OCRModel.CUSTOM_JERSEY}
    for member in batch_true:
        r.check(f"OCRModel.{member.name}.supports_batch == True",
                member.supports_batch is True,
                f"실제: {member.supports_batch}")
    for member in batch_false:
        r.check(f"OCRModel.{member.name}.supports_batch == False",
                member.supports_batch is False,
                f"실제: {member.supports_batch}")


def test_ocrmodel_is_transformer_based(r: TestResult) -> None:
    """OCRModel.is_transformer_based: TROCR→True, 나머지 False"""
    r.check("OCRModel.TROCR.is_transformer_based == True",
            OCRModel.TROCR.is_transformer_based is True,
            f"실제: {OCRModel.TROCR.is_transformer_based}")
    non_transformer = [m for m in OCRModel if m != OCRModel.TROCR]
    for member in non_transformer:
        r.check(f"OCRModel.{member.name}.is_transformer_based == False",
                member.is_transformer_based is False,
                f"실제: {member.is_transformer_based}")


def test_ocrmodel_to_korean(r: TestResult) -> None:
    """OCRModel.to_korean() 검증"""
    expected_korean = {
        OCRModel.CRNN: "CRNN",
        OCRModel.TROCR: "TrOCR",
        OCRModel.EASY_OCR: "EasyOCR",
        OCRModel.PADDLE_OCR: "PaddleOCR",
        OCRModel.TESSERACT: "Tesseract",
        OCRModel.CUSTOM_JERSEY: "커스텀 등번호 모델",
    }
    for member, expected in expected_korean.items():
        r.check(f'OCRModel.{member.name}.to_korean() == "{expected}"',
                member.to_korean() == expected,
                f"실제: {repr(member.to_korean())}")


# ============================================================================
# 14. TextDetectionModel Enum (5멤버)
# ============================================================================
def test_textdetectionmodel_members(r: TestResult) -> None:
    """TextDetectionModel 5멤버 이름/값 검증"""
    expected = {
        "EAST": "east",
        "CRAFT": "craft",
        "DBNET": "dbnet",
        "PSENET": "psenet",
        "CTPN": "ctpn",
    }
    members = {m.name: m.value for m in TextDetectionModel}
    r.check("TextDetectionModel 멤버 수 == 5",
            len(members) == 5,
            f"실제: {len(members)}")
    r.check("TextDetectionModel 멤버 이름/값 일치",
            members == expected,
            f"차이: {set(members.keys()) ^ set(expected.keys())}")
    r.check("TextDetectionModel은 Enum 서브클래스",
            issubclass(TextDetectionModel, Enum),
            "")


def test_textdetectionmodel_supports_rotated(r: TestResult) -> None:
    """TextDetectionModel.supports_rotated: EAST/CRAFT/DBNET→True, PSENET/CTPN→False"""
    rotated_true = {TextDetectionModel.EAST, TextDetectionModel.CRAFT, TextDetectionModel.DBNET}
    rotated_false = {TextDetectionModel.PSENET, TextDetectionModel.CTPN}
    for member in rotated_true:
        r.check(f"TextDetectionModel.{member.name}.supports_rotated == True",
                member.supports_rotated is True,
                f"실제: {member.supports_rotated}")
    for member in rotated_false:
        r.check(f"TextDetectionModel.{member.name}.supports_rotated == False",
                member.supports_rotated is False,
                f"실제: {member.supports_rotated}")


def test_textdetectionmodel_output_type(r: TestResult) -> None:
    """TextDetectionModel.output_type: EAST/CRAFT/DBNET/PSENET→polygon, CTPN→bbox"""
    polygon_models = [TextDetectionModel.EAST, TextDetectionModel.CRAFT,
                      TextDetectionModel.DBNET, TextDetectionModel.PSENET]
    for member in polygon_models:
        r.check(f'TextDetectionModel.{member.name}.output_type == "polygon"',
                member.output_type == "polygon",
                f"실제: {repr(member.output_type)}")
    r.check('TextDetectionModel.CTPN.output_type == "bbox"',
            TextDetectionModel.CTPN.output_type == "bbox",
            f"실제: {repr(TextDetectionModel.CTPN.output_type)}")


def test_textdetectionmodel_ctpn_only_bbox(r: TestResult) -> None:
    """CTPN만 bbox 출력 (유일성 검증)"""
    bbox_models = [m for m in TextDetectionModel if m.output_type == "bbox"]
    r.check("bbox 출력 모델은 CTPN만 유일",
            len(bbox_models) == 1 and bbox_models[0] == TextDetectionModel.CTPN,
            f"bbox 모델: {[m.name for m in bbox_models]}")


def test_textdetectionmodel_to_korean(r: TestResult) -> None:
    """TextDetectionModel.to_korean() 검증"""
    expected_korean = {
        TextDetectionModel.EAST: "EAST",
        TextDetectionModel.CRAFT: "CRAFT",
        TextDetectionModel.DBNET: "DBNet",
        TextDetectionModel.PSENET: "PSENet",
        TextDetectionModel.CTPN: "CTPN",
    }
    for member, expected in expected_korean.items():
        r.check(f'TextDetectionModel.{member.name}.to_korean() == "{expected}"',
                member.to_korean() == expected,
                f"실제: {repr(member.to_korean())}")


# ============================================================================
# 15. OCRStatus Enum (7멤버)
# ============================================================================
def test_ocrstatus_members(r: TestResult) -> None:
    """OCRStatus 7멤버 이름/값 검증"""
    expected = {
        "RECOGNIZED": "recognized",
        "DETECTED": "detected",
        "NOT_DETECTED": "not_detected",
        "LOW_CONFIDENCE": "low_confidence",
        "INVALID": "invalid",
        "PROCESSING": "processing",
        "TIMEOUT": "timeout",
    }
    members = {m.name: m.value for m in OCRStatus}
    r.check("OCRStatus 멤버 수 == 7",
            len(members) == 7,
            f"실제: {len(members)}")
    r.check("OCRStatus 멤버 이름/값 일치",
            members == expected,
            f"차이: {set(members.keys()) ^ set(expected.keys())}")
    r.check("OCRStatus는 Enum 서브클래스",
            issubclass(OCRStatus, Enum),
            "")


def test_ocrstatus_is_successful(r: TestResult) -> None:
    """OCRStatus.is_successful: RECOGNIZED→True, 나머지 False"""
    r.check("OCRStatus.RECOGNIZED.is_successful == True",
            OCRStatus.RECOGNIZED.is_successful is True,
            f"실제: {OCRStatus.RECOGNIZED.is_successful}")
    non_successful = [m for m in OCRStatus if m != OCRStatus.RECOGNIZED]
    for member in non_successful:
        r.check(f"OCRStatus.{member.name}.is_successful == False",
                member.is_successful is False,
                f"실제: {member.is_successful}")


def test_ocrstatus_needs_retry(r: TestResult) -> None:
    """OCRStatus.needs_retry: LOW_CONFIDENCE/TIMEOUT→True, 나머지 False"""
    retry_true = {OCRStatus.LOW_CONFIDENCE, OCRStatus.TIMEOUT}
    retry_false = set(OCRStatus) - retry_true
    for member in retry_true:
        r.check(f"OCRStatus.{member.name}.needs_retry == True",
                member.needs_retry is True,
                f"실제: {member.needs_retry}")
    for member in retry_false:
        r.check(f"OCRStatus.{member.name}.needs_retry == False",
                member.needs_retry is False,
                f"실제: {member.needs_retry}")


def test_ocrstatus_is_terminal(r: TestResult) -> None:
    """OCRStatus.is_terminal: RECOGNIZED/NOT_DETECTED/INVALID→True, 나머지 False"""
    terminal_true = {OCRStatus.RECOGNIZED, OCRStatus.NOT_DETECTED, OCRStatus.INVALID}
    terminal_false = set(OCRStatus) - terminal_true
    for member in terminal_true:
        r.check(f"OCRStatus.{member.name}.is_terminal == True",
                member.is_terminal is True,
                f"실제: {member.is_terminal}")
    for member in terminal_false:
        r.check(f"OCRStatus.{member.name}.is_terminal == False",
                member.is_terminal is False,
                f"실제: {member.is_terminal}")


def test_ocrstatus_flags_mutual_exclusivity(r: TestResult) -> None:
    """OCRStatus 상태 플래그 상호배타성: is_successful+needs_retry 동시 True 불가"""
    for member in OCRStatus:
        # is_successful과 needs_retry는 동시에 True일 수 없음
        r.check(f"OCRStatus.{member.name} is_successful+needs_retry 상호배타",
                not (member.is_successful and member.needs_retry),
                f"is_successful={member.is_successful}, needs_retry={member.needs_retry}")
    # needs_retry와 is_terminal이 동시에 True인 경우도 검증
    for member in OCRStatus:
        r.check(f"OCRStatus.{member.name} needs_retry+is_terminal 상호배타",
                not (member.needs_retry and member.is_terminal),
                f"needs_retry={member.needs_retry}, is_terminal={member.is_terminal}")


def test_ocrstatus_to_korean(r: TestResult) -> None:
    """OCRStatus.to_korean() 검증"""
    expected_korean = {
        OCRStatus.RECOGNIZED: "인식됨",
        OCRStatus.DETECTED: "검출됨",
        OCRStatus.NOT_DETECTED: "검출 안됨",
        OCRStatus.LOW_CONFIDENCE: "낮은 신뢰도",
        OCRStatus.INVALID: "유효하지 않음",
        OCRStatus.PROCESSING: "처리 중",
        OCRStatus.TIMEOUT: "시간 초과",
    }
    for member, expected in expected_korean.items():
        r.check(f'OCRStatus.{member.name}.to_korean() == "{expected}"',
                member.to_korean() == expected,
                f"실제: {repr(member.to_korean())}")


# ============================================================================
# 16. Private 캐시 완전성 (frozenset 4개, dict 5개)
# ============================================================================
def test_private_cache_frozensets(r: TestResult) -> None:
    """frozenset 캐시 4개 완전성 검증"""
    # _OCR_MODEL_SUPPORTS_BATCH (4개)
    batch_cache = getattr(ocr_constants, "_OCR_MODEL_SUPPORTS_BATCH", None)
    r.check("_OCR_MODEL_SUPPORTS_BATCH 존재",
            batch_cache is not None,
            "존재하지 않음")
    if batch_cache is not None:
        r.check("_OCR_MODEL_SUPPORTS_BATCH 타입=frozenset",
                isinstance(batch_cache, frozenset),
                f"실제: {type(batch_cache).__name__}")
        r.check("_OCR_MODEL_SUPPORTS_BATCH len=4",
                len(batch_cache) == 4,
                f"실제 길이: {len(batch_cache)}")

    # _TEXT_DETECTION_SUPPORTS_ROTATED (3개)
    rotated_cache = getattr(ocr_constants, "_TEXT_DETECTION_SUPPORTS_ROTATED", None)
    r.check("_TEXT_DETECTION_SUPPORTS_ROTATED 존재",
            rotated_cache is not None,
            "존재하지 않음")
    if rotated_cache is not None:
        r.check("_TEXT_DETECTION_SUPPORTS_ROTATED 타입=frozenset",
                isinstance(rotated_cache, frozenset),
                f"실제: {type(rotated_cache).__name__}")
        r.check("_TEXT_DETECTION_SUPPORTS_ROTATED len=3",
                len(rotated_cache) == 3,
                f"실제 길이: {len(rotated_cache)}")

    # _OCR_STATUS_NEEDS_RETRY (2개)
    retry_cache = getattr(ocr_constants, "_OCR_STATUS_NEEDS_RETRY", None)
    r.check("_OCR_STATUS_NEEDS_RETRY 존재",
            retry_cache is not None,
            "존재하지 않음")
    if retry_cache is not None:
        r.check("_OCR_STATUS_NEEDS_RETRY 타입=frozenset",
                isinstance(retry_cache, frozenset),
                f"실제: {type(retry_cache).__name__}")
        r.check("_OCR_STATUS_NEEDS_RETRY len=2",
                len(retry_cache) == 2,
                f"실제 길이: {len(retry_cache)}")

    # _OCR_STATUS_IS_TERMINAL (3개)
    terminal_cache = getattr(ocr_constants, "_OCR_STATUS_IS_TERMINAL", None)
    r.check("_OCR_STATUS_IS_TERMINAL 존재",
            terminal_cache is not None,
            "존재하지 않음")
    if terminal_cache is not None:
        r.check("_OCR_STATUS_IS_TERMINAL 타입=frozenset",
                isinstance(terminal_cache, frozenset),
                f"실제: {type(terminal_cache).__name__}")
        r.check("_OCR_STATUS_IS_TERMINAL len=3",
                len(terminal_cache) == 3,
                f"실제 길이: {len(terminal_cache)}")


def test_private_cache_dicts(r: TestResult) -> None:
    """dict 캐시 5개 완전성 검증"""
    # _OCR_MODEL_INPUT_SIZE_MAP (6개)
    input_map = getattr(ocr_constants, "_OCR_MODEL_INPUT_SIZE_MAP", None)
    r.check("_OCR_MODEL_INPUT_SIZE_MAP 존재",
            input_map is not None,
            "존재하지 않음")
    if input_map is not None:
        r.check("_OCR_MODEL_INPUT_SIZE_MAP 타입=dict",
                isinstance(input_map, dict),
                f"실제: {type(input_map).__name__}")
        r.check("_OCR_MODEL_INPUT_SIZE_MAP len=6",
                len(input_map) == 6,
                f"실제 길이: {len(input_map)}")

    # _OCR_MODEL_KOREAN_MAP (6개)
    korean_map = getattr(ocr_constants, "_OCR_MODEL_KOREAN_MAP", None)
    r.check("_OCR_MODEL_KOREAN_MAP 존재",
            korean_map is not None,
            "존재하지 않음")
    if korean_map is not None:
        r.check("_OCR_MODEL_KOREAN_MAP 타입=dict",
                isinstance(korean_map, dict),
                f"실제: {type(korean_map).__name__}")
        r.check("_OCR_MODEL_KOREAN_MAP len=6",
                len(korean_map) == 6,
                f"실제 길이: {len(korean_map)}")

    # _TEXT_DETECTION_OUTPUT_MAP (5개)
    output_map = getattr(ocr_constants, "_TEXT_DETECTION_OUTPUT_MAP", None)
    r.check("_TEXT_DETECTION_OUTPUT_MAP 존재",
            output_map is not None,
            "존재하지 않음")
    if output_map is not None:
        r.check("_TEXT_DETECTION_OUTPUT_MAP 타입=dict",
                isinstance(output_map, dict),
                f"실제: {type(output_map).__name__}")
        r.check("_TEXT_DETECTION_OUTPUT_MAP len=5",
                len(output_map) == 5,
                f"실제 길이: {len(output_map)}")

    # _TEXT_DETECTION_KOREAN_MAP (5개)
    td_korean_map = getattr(ocr_constants, "_TEXT_DETECTION_KOREAN_MAP", None)
    r.check("_TEXT_DETECTION_KOREAN_MAP 존재",
            td_korean_map is not None,
            "존재하지 않음")
    if td_korean_map is not None:
        r.check("_TEXT_DETECTION_KOREAN_MAP 타입=dict",
                isinstance(td_korean_map, dict),
                f"실제: {type(td_korean_map).__name__}")
        r.check("_TEXT_DETECTION_KOREAN_MAP len=5",
                len(td_korean_map) == 5,
                f"실제 길이: {len(td_korean_map)}")

    # _OCR_STATUS_KOREAN_MAP (7개)
    status_korean_map = getattr(ocr_constants, "_OCR_STATUS_KOREAN_MAP", None)
    r.check("_OCR_STATUS_KOREAN_MAP 존재",
            status_korean_map is not None,
            "존재하지 않음")
    if status_korean_map is not None:
        r.check("_OCR_STATUS_KOREAN_MAP 타입=dict",
                isinstance(status_korean_map, dict),
                f"실제: {type(status_korean_map).__name__}")
        r.check("_OCR_STATUS_KOREAN_MAP len=7",
                len(status_korean_map) == 7,
                f"실제 길이: {len(status_korean_map)}")


# ============================================================================
# 17. __all__ Export 완전성 (61개) + __version__
# ============================================================================
def test_all_exports_count(r: TestResult) -> None:
    """__all__ 61개 완전성 검증"""
    r.check("__all__ 존재",
            hasattr(ocr_constants, "__all__"),
            "__all__ 미존재")
    if hasattr(ocr_constants, "__all__"):
        r.check(f"__all__ len=61",
                len(ocr_constants.__all__) == 61,
                f"실제 길이: {len(ocr_constants.__all__)}")


def test_all_exports_exist_in_module(r: TestResult) -> None:
    """__all__의 모든 이름이 모듈에 실제 존재"""
    if not hasattr(ocr_constants, "__all__"):
        r.fail("__all__ Export 존재 확인", "__all__ 미존재")
        return
    missing = [name for name in ocr_constants.__all__
               if not hasattr(ocr_constants, name)]
    r.check(f"__all__ Export 완전성 ({len(ocr_constants.__all__)}개 모두 존재)",
            len(missing) == 0,
            f"누락: {missing}")


def test_all_exports_expected_names(r: TestResult) -> None:
    """__all__에 58개 상수 + 3개 Enum 이름 포함 확인"""
    expected_constants = [
        # OCR 신뢰도 (4)
        "MIN_OCR_CONFIDENCE", "HIGH_OCR_CONFIDENCE",
        "CONFIRMED_OCR_CONFIDENCE", "LOW_OCR_CONFIDENCE",
        # 등번호 범위 (5)
        "JERSEY_NUMBER_MIN", "JERSEY_NUMBER_MAX",
        "FIBA_JERSEY_NUMBERS", "NBA_JERSEY_NUMBERS", "KBL_JERSEY_NUMBERS",
        # OCR 처리 간격 (5)
        "OCR_FRAME_INTERVAL", "OCR_MIN_FRAME_INTERVAL", "OCR_MAX_FRAME_INTERVAL",
        "MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION", "OCR_CONFIRMATION_CONSISTENCY_RATIO",
        # 텍스트 검출 (7)
        "TEXT_DETECTION_MIN_CONFIDENCE", "TEXT_AREA_MIN", "TEXT_AREA_MAX",
        "TEXT_HEIGHT_MIN", "TEXT_WIDTH_MIN",
        "TEXT_ASPECT_RATIO_MIN", "TEXT_ASPECT_RATIO_MAX",
        # 등번호 ROI (5)
        "JERSEY_ROI_TOP_OFFSET", "JERSEY_ROI_BOTTOM_OFFSET",
        "JERSEY_ROI_LEFT_OFFSET", "JERSEY_ROI_RIGHT_OFFSET", "JERSEY_ROI_EXPANSION",
        # 이미지 전처리 (7)
        "OCR_INPUT_MIN_HEIGHT", "OCR_INPUT_MAX_HEIGHT", "OCR_INPUT_STANDARD_HEIGHT",
        "GRAYSCALE_WEIGHTS", "BINARIZATION_THRESHOLD",
        "ADAPTIVE_BINARIZATION_BLOCK_SIZE", "ADAPTIVE_BINARIZATION_CONSTANT",
        # 등번호 문자 (6)
        "JERSEY_CHARSET", "JERSEY_MAX_DIGITS", "JERSEY_MIN_DIGITS",
        "JERSEY_FONT_ASPECT_RATIO_MIN", "JERSEY_FONT_ASPECT_RATIO_MAX",
        "JERSEY_CHAR_SPACING_RATIO",
        # 색상 검출 (6)
        "JERSEY_CONTRAST_MIN", "WHITE_TEXT_HSV_LOWER", "WHITE_TEXT_HSV_UPPER",
        "BLACK_TEXT_HSV_LOWER", "BLACK_TEXT_HSV_UPPER", "COLOR_CONTRAST_KERNEL_SIZE",
        # OCR 후처리 (4)
        "JERSEY_NUMBER_PATTERN", "SIMILAR_CHAR_MAPPING",
        "OCR_NMS_IOU_THRESHOLD", "SAME_NUMBER_MERGE_DISTANCE",
        # 시간적 일관성 (3)
        "JERSEY_HISTORY_MAX_FRAMES", "JERSEY_CHANGE_THRESHOLD_FRAMES",
        "JERSEY_VOTING_WINDOW",
        # 배치 처리 (3)
        "OCR_BATCH_SIZE", "OCR_MAX_CONCURRENT", "OCR_TIMEOUT_MS",
        # 모델별 (3)
        "CRNN_INPUT_SIZE", "CRNN_HIDDEN_SIZE", "TROCR_INPUT_SIZE",
    ]
    expected_enums = ["OCRModel", "TextDetectionModel", "OCRStatus"]

    if not hasattr(ocr_constants, "__all__"):
        r.fail("__all__ 내용 확인", "__all__ 미존재")
        return

    all_set = set(ocr_constants.__all__)
    missing_constants = [n for n in expected_constants if n not in all_set]
    missing_enums = [n for n in expected_enums if n not in all_set]

    r.check(f"__all__에 58개 상수 포함",
            len(missing_constants) == 0,
            f"누락 상수: {missing_constants}")
    r.check(f"__all__에 3개 Enum 포함",
            len(missing_enums) == 0,
            f"누락 Enum: {missing_enums}")


def test_version(r: TestResult) -> None:
    """__version__ == '1.1.0' 검증"""
    r.check("__version__ 존재",
            hasattr(ocr_constants, "__version__"),
            "__version__ 미존재")
    if hasattr(ocr_constants, "__version__"):
        r.check('__version__ == "1.1.0"',
                ocr_constants.__version__ == "1.1.0",
                f"실제: {repr(ocr_constants.__version__)}")


# ============================================================================
# 18. __init__.py re-export 동기화 검증
# ============================================================================
def test_init_reexports(r: TestResult) -> None:
    """constants/__init__.py에서 ocr_constants 핵심 항목 re-export 확인"""
    from shared import constants as const_pkg

    expected = [
        "OCRModel", "TextDetectionModel", "OCRStatus",
        "MIN_OCR_CONFIDENCE", "JERSEY_NUMBER_MIN",
        "JERSEY_NUMBER_MAX", "OCR_FRAME_INTERVAL",
    ]
    for name in expected:
        r.check(f"__init__.py re-export: {name} 존재",
                hasattr(const_pkg, name),
                f"{name} 미존재")
        if hasattr(const_pkg, name):
            r.check(f"__init__.py re-export: {name} identity 일치",
                    getattr(const_pkg, name) is getattr(ocr_constants, name),
                    f"identity 불일치")


# ============================================================================
# 19. 에지 케이스: identity, hashable, set, iteration, 불변성
# ============================================================================
def test_enum_hashable_and_set(r: TestResult) -> None:
    """Enum 멤버 hashable 및 set 구성 가능 검증"""
    for enum_cls in (OCRModel, TextDetectionModel, OCRStatus):
        try:
            members_set = set(enum_cls)
            r.check(f"{enum_cls.__name__} set 구성 가능",
                    len(members_set) == len(list(enum_cls)),
                    f"set 크기 불일치")
        except TypeError as e:
            r.fail(f"{enum_cls.__name__} set 구성", str(e))


def test_enum_identity(r: TestResult) -> None:
    """Enum 멤버 identity 검증 (같은 이름 → 같은 객체)"""
    r.check("OCRModel.CRNN is OCRModel.CRNN",
            OCRModel.CRNN is OCRModel.CRNN, "")
    r.check("TextDetectionModel.EAST is TextDetectionModel.EAST",
            TextDetectionModel.EAST is TextDetectionModel.EAST, "")
    r.check("OCRStatus.RECOGNIZED is OCRStatus.RECOGNIZED",
            OCRStatus.RECOGNIZED is OCRStatus.RECOGNIZED, "")
    # value로 접근해도 동일 identity
    r.check('OCRModel("crnn") is OCRModel.CRNN',
            OCRModel("crnn") is OCRModel.CRNN, "")
    r.check('TextDetectionModel("east") is TextDetectionModel.EAST',
            TextDetectionModel("east") is TextDetectionModel.EAST, "")
    r.check('OCRStatus("recognized") is OCRStatus.RECOGNIZED',
            OCRStatus("recognized") is OCRStatus.RECOGNIZED, "")


def test_enum_iteration_order(r: TestResult) -> None:
    """Enum iteration 순서 (정의 순서 보존)"""
    ocr_names = [m.name for m in OCRModel]
    r.check("OCRModel iteration 순서",
            ocr_names == ["CRNN", "TROCR", "EASY_OCR", "PADDLE_OCR", "TESSERACT", "CUSTOM_JERSEY"],
            f"실제: {ocr_names}")

    td_names = [m.name for m in TextDetectionModel]
    r.check("TextDetectionModel iteration 순서",
            td_names == ["EAST", "CRAFT", "DBNET", "PSENET", "CTPN"],
            f"실제: {td_names}")

    status_names = [m.name for m in OCRStatus]
    r.check("OCRStatus iteration 순서",
            status_names == ["RECOGNIZED", "DETECTED", "NOT_DETECTED",
                             "LOW_CONFIDENCE", "INVALID", "PROCESSING", "TIMEOUT"],
            f"실제: {status_names}")


def test_tuple_immutability(r: TestResult) -> None:
    """tuple 상수 불변성 검증 (변경 시도 시 TypeError)"""
    immutable_tuples = [
        ("FIBA_JERSEY_NUMBERS", FIBA_JERSEY_NUMBERS),
        ("NBA_JERSEY_NUMBERS", NBA_JERSEY_NUMBERS),
        ("KBL_JERSEY_NUMBERS", KBL_JERSEY_NUMBERS),
        ("GRAYSCALE_WEIGHTS", GRAYSCALE_WEIGHTS),
        ("WHITE_TEXT_HSV_LOWER", WHITE_TEXT_HSV_LOWER),
        ("WHITE_TEXT_HSV_UPPER", WHITE_TEXT_HSV_UPPER),
        ("BLACK_TEXT_HSV_LOWER", BLACK_TEXT_HSV_LOWER),
        ("BLACK_TEXT_HSV_UPPER", BLACK_TEXT_HSV_UPPER),
        ("CRNN_INPUT_SIZE", CRNN_INPUT_SIZE),
        ("TROCR_INPUT_SIZE", TROCR_INPUT_SIZE),
    ]
    for name, val in immutable_tuples:
        try:
            val[0] = 999  # type: ignore
            r.fail(f"{name} tuple 불변성", "변경 가능 (TypeError 미발생)")
        except TypeError:
            r.check(f"{name} tuple 불변성", True, "")


def test_frozenset_immutability(r: TestResult) -> None:
    """frozenset 캐시 불변성 검증 (add 시도 시 AttributeError)"""
    frozenset_attrs = [
        "_OCR_MODEL_SUPPORTS_BATCH",
        "_TEXT_DETECTION_SUPPORTS_ROTATED",
        "_OCR_STATUS_NEEDS_RETRY",
        "_OCR_STATUS_IS_TERMINAL",
    ]
    for attr_name in frozenset_attrs:
        cache = getattr(ocr_constants, attr_name, None)
        if cache is None:
            r.fail(f"{attr_name} frozenset 불변성", "존재하지 않음")
            continue
        try:
            cache.add("test")  # type: ignore
            r.fail(f"{attr_name} frozenset 불변성", "add 가능 (set일 수 있음)")
        except AttributeError:
            r.check(f"{attr_name} frozenset 불변성", True, "")


# ============================================================================
# 실행
# ============================================================================
def main() -> int:
    r = TestResult()
    print("\n" + "=" * 60)
    print("ocr_constants.py 단위 테스트 (v1.1.0)")
    print("=" * 60)

    # 1. OCR 신뢰도
    print("\n--- 1. OCR 신뢰도 상수 (4개) ---")
    test_ocr_confidence_exact_values(r)
    test_ocr_confidence_types(r)
    test_ocr_confidence_ordering(r)

    # 2. 등번호 범위
    print("\n--- 2. 등번호 범위 상수 (5개) ---")
    test_jersey_number_range_exact_values(r)
    test_jersey_number_range_types(r)
    test_jersey_league_tuples(r)

    # 3. OCR 처리 간격
    print("\n--- 3. OCR 처리 간격 상수 (5개) ---")
    test_ocr_frame_interval_exact_values(r)
    test_ocr_frame_interval_types(r)
    test_ocr_frame_interval_ordering(r)

    # 4. 텍스트 검출
    print("\n--- 4. 텍스트 검출 파라미터 (7개) ---")
    test_text_detection_exact_values(r)
    test_text_detection_types(r)
    test_text_detection_ordering(r)

    # 5. 등번호 ROI
    print("\n--- 5. 등번호 ROI (5개) ---")
    test_jersey_roi_exact_values(r)
    test_jersey_roi_types(r)
    test_jersey_roi_ordering(r)

    # 6. 이미지 전처리
    print("\n--- 6. 이미지 전처리 (7개) ---")
    test_image_preprocessing_exact_values(r)
    test_image_preprocessing_types(r)
    test_image_preprocessing_ordering(r)
    test_grayscale_weights_itu_bt601(r)
    test_adaptive_binarization_block_size_odd(r)

    # 7. 등번호 문자
    print("\n--- 7. 등번호 문자 특성 (6개) ---")
    test_jersey_char_exact_values(r)
    test_jersey_char_types(r)
    test_jersey_char_ordering(r)

    # 8. 색상 검출
    print("\n--- 8. 색상 기반 검출 (6개) ---")
    test_color_detection_exact_values(r)
    test_color_detection_types(r)
    test_color_contrast_kernel_size_odd(r)

    # 9. OCR 후처리
    print("\n--- 9. OCR 후처리 (4개) ---")
    test_ocr_postprocessing_exact_values(r)
    test_ocr_postprocessing_types(r)
    test_jersey_number_pattern_regex(r)
    test_similar_char_mapping_complete(r)

    # 10. 시간적 일관성
    print("\n--- 10. 시간적 일관성 (3개) ---")
    test_temporal_consistency_exact_values(r)
    test_temporal_consistency_types(r)

    # 11. 배치 처리
    print("\n--- 11. 배치 처리 (3개) ---")
    test_batch_processing_exact_values(r)
    test_batch_processing_types(r)

    # 12. 모델별 파라미터
    print("\n--- 12. 모델별 파라미터 (3개) ---")
    test_model_params_exact_values(r)
    test_model_params_types(r)

    # 13. OCRModel Enum
    print("\n--- 13. OCRModel Enum (6멤버) ---")
    test_ocrmodel_members(r)
    test_ocrmodel_input_size(r)
    test_ocrmodel_input_size_consistency_with_constants(r)
    test_ocrmodel_supports_batch(r)
    test_ocrmodel_is_transformer_based(r)
    test_ocrmodel_to_korean(r)

    # 14. TextDetectionModel Enum
    print("\n--- 14. TextDetectionModel Enum (5멤버) ---")
    test_textdetectionmodel_members(r)
    test_textdetectionmodel_supports_rotated(r)
    test_textdetectionmodel_output_type(r)
    test_textdetectionmodel_ctpn_only_bbox(r)
    test_textdetectionmodel_to_korean(r)

    # 15. OCRStatus Enum
    print("\n--- 15. OCRStatus Enum (7멤버) ---")
    test_ocrstatus_members(r)
    test_ocrstatus_is_successful(r)
    test_ocrstatus_needs_retry(r)
    test_ocrstatus_is_terminal(r)
    test_ocrstatus_flags_mutual_exclusivity(r)
    test_ocrstatus_to_korean(r)

    # 16. Private 캐시
    print("\n--- 16. Private 캐시 완전성 ---")
    test_private_cache_frozensets(r)
    test_private_cache_dicts(r)

    # 17. __all__ Export + __version__
    print("\n--- 17. __all__ Export + __version__ ---")
    test_all_exports_count(r)
    test_all_exports_exist_in_module(r)
    test_all_exports_expected_names(r)
    test_version(r)

    # 18. __init__.py re-export
    print("\n--- 18. __init__.py re-export ---")
    test_init_reexports(r)

    # 19. 에지 케이스
    print("\n--- 19. 에지 케이스 ---")
    test_enum_hashable_and_set(r)
    test_enum_identity(r)
    test_enum_iteration_order(r)
    test_tuple_immutability(r)
    test_frozenset_immutability(r)

    r.summary()
    return 1 if r.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
