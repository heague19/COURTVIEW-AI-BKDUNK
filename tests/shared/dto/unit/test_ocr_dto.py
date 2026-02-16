# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_ocr_dto.py

OCR DTO 유닛 테스트
- __all__ export 검증
- __version__ 검증
- OCRBackend Enum: 멤버, 프로퍼티, i18n get_name()
- OCRStatus Enum: 멤버, 프로퍼티, i18n get_name()
- OCRResult: __post_init__ clamp/strip, 프로퍼티, as_integer()
- JerseyNumber: __post_init__ clamp, 프로퍼티, matches()
- JerseyNumberVote: add_vote(), average_confidence
- MultiViewOCRResult: add_result(), resolve(), to_jersey_number(), winning_margin
- OCRAnalysisResult: 프로퍼티, get_jersey_number()

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

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

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def assert_eq(r: TestResult, name: str, actual, expected) -> None:
    if actual == expected:
        r.ok(name)
    else:
        r.fail(name, f"expected={expected!r}, actual={actual!r}")


def assert_true(r: TestResult, name: str, value: bool) -> None:
    if value:
        r.ok(name)
    else:
        r.fail(name, "expected True, got False")


def assert_false(r: TestResult, name: str, value: bool) -> None:
    if not value:
        r.ok(name)
    else:
        r.fail(name, "expected False, got True")


def assert_none(r: TestResult, name: str, value) -> None:
    if value is None:
        r.ok(name)
    else:
        r.fail(name, f"expected None, got {value!r}")


def assert_not_none(r: TestResult, name: str, value) -> None:
    if value is not None:
        r.ok(name)
    else:
        r.fail(name, "expected not None, got None")


def assert_isinstance(r: TestResult, name: str, obj, cls) -> None:
    if isinstance(obj, cls):
        r.ok(name)
    else:
        r.fail(name, f"expected isinstance({cls.__name__}), got {type(obj).__name__}")


def assert_close(r: TestResult, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
    if abs(actual - expected) < tol:
        r.ok(name)
    else:
        r.fail(name, f"expected≈{expected}, actual={actual}")


# ==================== [A] __all__ / __version__ ====================
def test_exports(r: TestResult) -> None:
    """__all__ export 검증"""
    import shared.dto.ocr_dto as mod
    assert_true(r, "__all__ 존재", hasattr(mod, "__all__"))
    assert_eq(r, "__all__ 개수 = 8", len(mod.__all__), 8)

    expected = [
        "SupportedLanguage", "OCRBackend", "OCRStatus",
        "OCRResult", "JerseyNumber", "JerseyNumberVote",
        "MultiViewOCRResult", "OCRAnalysisResult",
    ]
    for name in expected:
        assert_true(r, f"__all__에 {name} 포함", name in mod.__all__)
        assert_true(r, f"{name} 접근 가능", hasattr(mod, name))


def test_version(r: TestResult) -> None:
    """__version__ 검증"""
    import shared.dto.ocr_dto as mod
    assert_true(r, "__version__ 존재", hasattr(mod, "__version__"))
    assert_eq(r, "__version__ = '2.0.0'", mod.__version__, "2.0.0")


# ==================== [B] OCRBackend Enum ====================
def test_ocr_backend_members(r: TestResult) -> None:
    """OCRBackend 멤버 검증"""
    from shared.dto.ocr_dto import OCRBackend

    expected = ["EASYOCR", "PADDLEOCR", "TESSERACT", "TROCR", "CUSTOM"]
    actual = [m.name for m in OCRBackend]
    assert_eq(r, "OCRBackend 멤버 수 = 5", len(actual), 5)
    for name in expected:
        assert_true(r, f"OCRBackend.{name} 존재", name in actual)

    # str Enum 값 확인
    assert_eq(r, "EASYOCR.value", OCRBackend.EASYOCR.value, "easyocr")
    assert_eq(r, "PADDLEOCR.value", OCRBackend.PADDLEOCR.value, "paddleocr")
    assert_eq(r, "TESSERACT.value", OCRBackend.TESSERACT.value, "tesseract")
    assert_eq(r, "TROCR.value", OCRBackend.TROCR.value, "trocr")
    assert_eq(r, "CUSTOM.value", OCRBackend.CUSTOM.value, "custom")


def test_ocr_backend_properties(r: TestResult) -> None:
    """OCRBackend 프로퍼티 검증"""
    from shared.dto.ocr_dto import OCRBackend

    # supports_korean
    assert_true(r, "EASYOCR supports_korean", OCRBackend.EASYOCR.supports_korean)
    assert_true(r, "PADDLEOCR supports_korean", OCRBackend.PADDLEOCR.supports_korean)
    assert_true(r, "TESSERACT supports_korean", OCRBackend.TESSERACT.supports_korean)
    assert_false(r, "TROCR not supports_korean", OCRBackend.TROCR.supports_korean)
    assert_false(r, "CUSTOM not supports_korean", OCRBackend.CUSTOM.supports_korean)

    # is_lightweight
    assert_true(r, "EASYOCR is_lightweight", OCRBackend.EASYOCR.is_lightweight)
    assert_false(r, "PADDLEOCR not lightweight", OCRBackend.PADDLEOCR.is_lightweight)
    assert_false(r, "TROCR not lightweight", OCRBackend.TROCR.is_lightweight)

    # is_transformer_based
    assert_true(r, "TROCR is_transformer_based", OCRBackend.TROCR.is_transformer_based)
    assert_false(r, "EASYOCR not transformer", OCRBackend.EASYOCR.is_transformer_based)
    assert_false(r, "CUSTOM not transformer", OCRBackend.CUSTOM.is_transformer_based)


def test_ocr_backend_i18n(r: TestResult) -> None:
    """OCRBackend i18n get_name() 검증"""
    from shared.dto.ocr_dto import OCRBackend
    from shared.constants.localization import SupportedLanguage

    # 한국어
    assert_eq(r, "EASYOCR KO", OCRBackend.EASYOCR.get_name(SupportedLanguage.KO), "EasyOCR (경량)")
    assert_eq(r, "CUSTOM KO", OCRBackend.CUSTOM.get_name(SupportedLanguage.KO), "커스텀 모델")

    # 영어
    assert_eq(r, "EASYOCR EN", OCRBackend.EASYOCR.get_name(SupportedLanguage.EN), "EasyOCR (Lightweight)")
    assert_eq(r, "TROCR EN", OCRBackend.TROCR.get_name(SupportedLanguage.EN), "TrOCR (Transformer)")

    # 일본어
    assert_eq(r, "PADDLEOCR JA", OCRBackend.PADDLEOCR.get_name(SupportedLanguage.JA), "PaddleOCR（高精度）")

    # 중국어
    assert_eq(r, "TESSERACT ZH", OCRBackend.TESSERACT.get_name(SupportedLanguage.ZH), "Tesseract（通用）")

    # 스페인어
    assert_eq(r, "CUSTOM ES", OCRBackend.CUSTOM.get_name(SupportedLanguage.ES), "Modelo Personalizado")

    # to_korean 하위 호환성
    assert_eq(r, "to_korean = get_name(KO)", OCRBackend.EASYOCR.to_korean, OCRBackend.EASYOCR.get_name(SupportedLanguage.KO))

    # 기본값 한국어
    assert_eq(r, "get_name() 기본값 KO", OCRBackend.EASYOCR.get_name(), OCRBackend.EASYOCR.get_name(SupportedLanguage.KO))


# ==================== [C] OCRStatus Enum ====================
def test_ocr_status_members(r: TestResult) -> None:
    """OCRStatus 멤버 검증"""
    from shared.dto.ocr_dto import OCRStatus

    expected = ["SUCCESS", "PARTIAL", "FAILED", "LOW_CONFIDENCE", "PROCESSING", "SKIPPED"]
    actual = [m.name for m in OCRStatus]
    assert_eq(r, "OCRStatus 멤버 수 = 6", len(actual), 6)
    for name in expected:
        assert_true(r, f"OCRStatus.{name} 존재", name in actual)

    # str Enum 값 확인
    assert_eq(r, "SUCCESS.value", OCRStatus.SUCCESS.value, "success")
    assert_eq(r, "PARTIAL.value", OCRStatus.PARTIAL.value, "partial")
    assert_eq(r, "FAILED.value", OCRStatus.FAILED.value, "failed")
    assert_eq(r, "LOW_CONFIDENCE.value", OCRStatus.LOW_CONFIDENCE.value, "low_confidence")
    assert_eq(r, "PROCESSING.value", OCRStatus.PROCESSING.value, "processing")
    assert_eq(r, "SKIPPED.value", OCRStatus.SKIPPED.value, "skipped")


def test_ocr_status_properties(r: TestResult) -> None:
    """OCRStatus 프로퍼티 검증"""
    from shared.dto.ocr_dto import OCRStatus

    # is_successful
    assert_true(r, "SUCCESS is_successful", OCRStatus.SUCCESS.is_successful)
    assert_true(r, "PARTIAL is_successful", OCRStatus.PARTIAL.is_successful)
    assert_false(r, "FAILED not successful", OCRStatus.FAILED.is_successful)
    assert_false(r, "LOW_CONFIDENCE not successful", OCRStatus.LOW_CONFIDENCE.is_successful)
    assert_false(r, "PROCESSING not successful", OCRStatus.PROCESSING.is_successful)
    assert_false(r, "SKIPPED not successful", OCRStatus.SKIPPED.is_successful)

    # is_usable
    assert_true(r, "SUCCESS is_usable", OCRStatus.SUCCESS.is_usable)
    assert_true(r, "PARTIAL is_usable", OCRStatus.PARTIAL.is_usable)
    assert_true(r, "LOW_CONFIDENCE is_usable", OCRStatus.LOW_CONFIDENCE.is_usable)
    assert_false(r, "FAILED not usable", OCRStatus.FAILED.is_usable)
    assert_false(r, "PROCESSING not usable", OCRStatus.PROCESSING.is_usable)
    assert_false(r, "SKIPPED not usable", OCRStatus.SKIPPED.is_usable)

    # is_final
    assert_true(r, "SUCCESS is_final", OCRStatus.SUCCESS.is_final)
    assert_true(r, "FAILED is_final", OCRStatus.FAILED.is_final)
    assert_true(r, "SKIPPED is_final", OCRStatus.SKIPPED.is_final)
    assert_false(r, "PROCESSING not final", OCRStatus.PROCESSING.is_final)


def test_ocr_status_i18n(r: TestResult) -> None:
    """OCRStatus i18n get_name() 검증"""
    from shared.dto.ocr_dto import OCRStatus
    from shared.constants.localization import SupportedLanguage

    # 한국어
    assert_eq(r, "SUCCESS KO", OCRStatus.SUCCESS.get_name(SupportedLanguage.KO), "성공")
    assert_eq(r, "PARTIAL KO", OCRStatus.PARTIAL.get_name(SupportedLanguage.KO), "부분 성공")
    assert_eq(r, "FAILED KO", OCRStatus.FAILED.get_name(SupportedLanguage.KO), "실패")
    assert_eq(r, "LOW_CONFIDENCE KO", OCRStatus.LOW_CONFIDENCE.get_name(SupportedLanguage.KO), "낮은 신뢰도")
    assert_eq(r, "PROCESSING KO", OCRStatus.PROCESSING.get_name(SupportedLanguage.KO), "처리 중")
    assert_eq(r, "SKIPPED KO", OCRStatus.SKIPPED.get_name(SupportedLanguage.KO), "건너뜀")

    # 영어
    assert_eq(r, "SUCCESS EN", OCRStatus.SUCCESS.get_name(SupportedLanguage.EN), "Success")
    assert_eq(r, "LOW_CONFIDENCE EN", OCRStatus.LOW_CONFIDENCE.get_name(SupportedLanguage.EN), "Low Confidence")

    # 일본어
    assert_eq(r, "FAILED JA", OCRStatus.FAILED.get_name(SupportedLanguage.JA), "失敗")
    assert_eq(r, "PROCESSING JA", OCRStatus.PROCESSING.get_name(SupportedLanguage.JA), "処理中")

    # 중국어
    assert_eq(r, "SUCCESS ZH", OCRStatus.SUCCESS.get_name(SupportedLanguage.ZH), "成功")
    assert_eq(r, "SKIPPED ZH", OCRStatus.SKIPPED.get_name(SupportedLanguage.ZH), "已跳过")

    # 스페인어
    assert_eq(r, "PARTIAL ES", OCRStatus.PARTIAL.get_name(SupportedLanguage.ES), "Éxito Parcial")
    assert_eq(r, "FAILED ES", OCRStatus.FAILED.get_name(SupportedLanguage.ES), "Fallido")

    # to_korean 하위 호환성
    assert_eq(r, "to_korean 일치", OCRStatus.SUCCESS.to_korean, "성공")

    # 기본값 한국어
    assert_eq(r, "get_name() 기본값 KO", OCRStatus.FAILED.get_name(), "실패")


# ==================== [D] OCRResult ====================
def test_ocr_result_defaults(r: TestResult) -> None:
    """OCRResult 기본값 검증"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus, OCRBackend

    res = OCRResult()
    assert_eq(r, "기본 text = ''", res.text, "")
    assert_close(r, "기본 confidence = 0.0", res.confidence, 0.0)
    assert_none(r, "기본 bbox = None", res.bbox)
    assert_eq(r, "기본 status = FAILED", res.status, OCRStatus.FAILED)
    assert_eq(r, "기본 backend = EASYOCR", res.backend, OCRBackend.EASYOCR)
    assert_eq(r, "기본 language = 'en'", res.language, "en")
    assert_eq(r, "기본 frame_index = 0", res.frame_index, 0)
    assert_none(r, "기본 camera_id = None", res.camera_id)
    assert_none(r, "기본 raw_output = None", res.raw_output)


def test_ocr_result_post_init(r: TestResult) -> None:
    """OCRResult __post_init__ 검증 (clamp + strip)"""
    from shared.dto.ocr_dto import OCRResult

    # confidence clamp
    r1 = OCRResult(confidence=1.5)
    assert_close(r, "confidence clamp 상한 1.0", r1.confidence, 1.0)

    r2 = OCRResult(confidence=-0.3)
    assert_close(r, "confidence clamp 하한 0.0", r2.confidence, 0.0)

    r3 = OCRResult(confidence=0.75)
    assert_close(r, "confidence 정상 유지 0.75", r3.confidence, 0.75)

    # text strip
    r4 = OCRResult(text="  23  ")
    assert_eq(r, "text strip '23'", r4.text, "23")

    r5 = OCRResult(text="\n\t  45  \n")
    assert_eq(r, "text strip whitespace", r5.text, "45")


def test_ocr_result_properties(r: TestResult) -> None:
    """OCRResult 프로퍼티 검증"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus

    # is_valid = status.is_usable AND text length > 0
    valid = OCRResult(text="23", status=OCRStatus.SUCCESS, confidence=0.9)
    assert_true(r, "유효한 결과 is_valid", valid.is_valid)

    empty_text = OCRResult(text="", status=OCRStatus.SUCCESS)
    assert_false(r, "빈 텍스트 not valid", empty_text.is_valid)

    failed_status = OCRResult(text="23", status=OCRStatus.FAILED)
    assert_false(r, "실패 상태 not valid", failed_status.is_valid)

    low_conf = OCRResult(text="23", status=OCRStatus.LOW_CONFIDENCE)
    assert_true(r, "LOW_CONFIDENCE는 usable이므로 valid", low_conf.is_valid)

    # is_numeric
    numeric = OCRResult(text="123")
    assert_true(r, "숫자 텍스트 is_numeric", numeric.is_numeric)

    not_numeric = OCRResult(text="12A")
    assert_false(r, "혼합 텍스트 not numeric", not_numeric.is_numeric)

    # is_high_confidence
    high = OCRResult(confidence=0.85)
    assert_true(r, "0.85 is_high_confidence", high.is_high_confidence)

    low = OCRResult(confidence=0.79)
    assert_false(r, "0.79 not high_confidence", low.is_high_confidence)

    exact = OCRResult(confidence=0.80)
    assert_true(r, "0.80 경계값 is_high_confidence", exact.is_high_confidence)

    # text_length
    assert_eq(r, "text_length '23' = 2", OCRResult(text="23").text_length, 2)
    assert_eq(r, "text_length '' = 0", OCRResult(text="").text_length, 0)


def test_ocr_result_as_integer(r: TestResult) -> None:
    """OCRResult as_integer() 검증"""
    from shared.dto.ocr_dto import OCRResult

    r1 = OCRResult(text="42")
    assert_eq(r, "as_integer '42' = 42", r1.as_integer(), 42)

    r2 = OCRResult(text="0")
    assert_eq(r, "as_integer '0' = 0", r2.as_integer(), 0)

    r3 = OCRResult(text="ABC")
    assert_none(r, "as_integer 'ABC' = None", r3.as_integer())

    r4 = OCRResult(text="12.5")
    assert_none(r, "as_integer '12.5' = None", r4.as_integer())

    r5 = OCRResult(text="")
    assert_none(r, "as_integer '' = None", r5.as_integer())


# ==================== [E] JerseyNumber ====================
def test_jersey_number_defaults(r: TestResult) -> None:
    """JerseyNumber 기본값 검증"""
    from shared.dto.ocr_dto import JerseyNumber

    jn = JerseyNumber()
    assert_eq(r, "기본 number = -1", jn.number, -1)
    assert_close(r, "기본 confidence = 0.0", jn.confidence, 0.0)
    assert_eq(r, "기본 source = 'unknown'", jn.source, "unknown")
    assert_none(r, "기본 ocr_result = None", jn.ocr_result)
    assert_none(r, "기본 person_id = None", jn.person_id)
    assert_false(r, "기본 is_confirmed = False", jn.is_confirmed)
    assert_eq(r, "기본 confirmation_count = 0", jn.confirmation_count, 0)


def test_jersey_number_post_init(r: TestResult) -> None:
    """JerseyNumber __post_init__ confidence clamp 검증"""
    from shared.dto.ocr_dto import JerseyNumber

    jn1 = JerseyNumber(confidence=1.5)
    assert_close(r, "confidence clamp 상한 1.0", jn1.confidence, 1.0)

    jn2 = JerseyNumber(confidence=-0.2)
    assert_close(r, "confidence clamp 하한 0.0", jn2.confidence, 0.0)

    jn3 = JerseyNumber(confidence=0.85)
    assert_close(r, "confidence 정상 유지", jn3.confidence, 0.85)


def test_jersey_number_properties(r: TestResult) -> None:
    """JerseyNumber 프로퍼티 검증"""
    from shared.dto.ocr_dto import JerseyNumber

    # is_valid: 0 <= number <= 99
    assert_true(r, "number=0 is_valid", JerseyNumber(number=0).is_valid)
    assert_true(r, "number=23 is_valid", JerseyNumber(number=23).is_valid)
    assert_true(r, "number=99 is_valid", JerseyNumber(number=99).is_valid)
    assert_false(r, "number=-1 not valid", JerseyNumber(number=-1).is_valid)
    assert_false(r, "number=100 not valid", JerseyNumber(number=100).is_valid)

    # is_high_confidence: >= 0.8
    assert_true(r, "0.9 is_high_confidence", JerseyNumber(confidence=0.9).is_high_confidence)
    assert_true(r, "0.8 경계값 high", JerseyNumber(confidence=0.8).is_high_confidence)
    assert_false(r, "0.79 not high", JerseyNumber(confidence=0.79).is_high_confidence)

    # is_double_digit: number >= 10
    assert_true(r, "23 is_double_digit", JerseyNumber(number=23).is_double_digit)
    assert_true(r, "10 경계값 double", JerseyNumber(number=10).is_double_digit)
    assert_false(r, "9 not double_digit", JerseyNumber(number=9).is_double_digit)

    # is_single_digit: 0 <= number <= 9
    assert_true(r, "0 is_single_digit", JerseyNumber(number=0).is_single_digit)
    assert_true(r, "9 is_single_digit", JerseyNumber(number=9).is_single_digit)
    assert_false(r, "10 not single", JerseyNumber(number=10).is_single_digit)
    assert_false(r, "-1 not single", JerseyNumber(number=-1).is_single_digit)

    # display_number
    assert_eq(r, "display 23 = '23'", JerseyNumber(number=23).display_number, "23")
    assert_eq(r, "display 0 = '0'", JerseyNumber(number=0).display_number, "0")
    assert_eq(r, "display -1 = '??'", JerseyNumber(number=-1).display_number, "??")
    assert_eq(r, "display -5 = '??'", JerseyNumber(number=-5).display_number, "??")


def test_jersey_number_matches(r: TestResult) -> None:
    """JerseyNumber matches() 검증"""
    from shared.dto.ocr_dto import JerseyNumber

    jn1 = JerseyNumber(number=23, confidence=0.9)
    jn2 = JerseyNumber(number=23, confidence=0.7)
    jn3 = JerseyNumber(number=45, confidence=0.9)
    jn_invalid = JerseyNumber(number=-1)

    assert_true(r, "같은 번호 matches", jn1.matches(jn2))
    assert_false(r, "다른 번호 not matches", jn1.matches(jn3))
    assert_false(r, "invalid와 matches 실패", jn1.matches(jn_invalid))
    assert_false(r, "invalid끼리 matches 실패", jn_invalid.matches(JerseyNumber(number=-1)))


# ==================== [F] JerseyNumberVote ====================
def test_jersey_number_vote_defaults(r: TestResult) -> None:
    """JerseyNumberVote 기본값 검증"""
    from shared.dto.ocr_dto import JerseyNumberVote

    v = JerseyNumberVote()
    assert_eq(r, "기본 number = -1", v.number, -1)
    assert_eq(r, "기본 votes = 0", v.votes, 0)
    assert_close(r, "기본 total_confidence = 0.0", v.total_confidence, 0.0)
    assert_eq(r, "기본 sources = []", v.sources, [])
    assert_close(r, "빈 average_confidence = 0.0", v.average_confidence, 0.0)


def test_jersey_number_vote_add_vote(r: TestResult) -> None:
    """JerseyNumberVote add_vote() 검증"""
    from shared.dto.ocr_dto import JerseyNumberVote

    v = JerseyNumberVote(number=23)
    v.add_vote("cam_01", 0.9)
    assert_eq(r, "1회 투표 후 votes=1", v.votes, 1)
    assert_close(r, "1회 투표 후 total=0.9", v.total_confidence, 0.9)
    assert_eq(r, "sources 길이=1", len(v.sources), 1)
    assert_eq(r, "sources[0] 내용", v.sources[0], ("cam_01", 0.9))
    assert_close(r, "average=0.9", v.average_confidence, 0.9)

    v.add_vote("cam_02", 0.7)
    assert_eq(r, "2회 투표 후 votes=2", v.votes, 2)
    assert_close(r, "2회 투표 후 total=1.6", v.total_confidence, 1.6)
    assert_close(r, "average=0.8", v.average_confidence, 0.8)

    v.add_vote("cam_03", 0.8)
    assert_eq(r, "3회 투표 후 votes=3", v.votes, 3)
    assert_close(r, "average≈0.8", v.average_confidence, 0.8, tol=0.01)


# ==================== [G] MultiViewOCRResult ====================
def test_multiview_defaults(r: TestResult) -> None:
    """MultiViewOCRResult 기본값 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult

    mv = MultiViewOCRResult()
    assert_eq(r, "기본 person_id = 0", mv.person_id, 0)
    assert_eq(r, "기본 votes 빈 dict", mv.votes, {})
    assert_none(r, "기본 final_number = None", mv.final_number)
    assert_false(r, "기본 has_result = False", mv.has_result)
    assert_eq(r, "기본 num_views = 0", mv.num_views, 0)
    assert_eq(r, "기본 num_candidates = 0", mv.num_candidates, 0)
    assert_false(r, "기본 is_unanimous = False", mv.is_unanimous)


def test_multiview_add_result(r: TestResult) -> None:
    """MultiViewOCRResult add_result() 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=1)

    # 유효한 등번호 추가
    jn1 = JerseyNumber(number=23, confidence=0.9)
    mv.add_result("cam_01", jn1)
    assert_eq(r, "add 후 num_views=1", mv.num_views, 1)
    assert_eq(r, "add 후 num_candidates=1", mv.num_candidates, 1)
    assert_true(r, "23이 votes에 존재", 23 in mv.votes)
    assert_eq(r, "23 투표수=1", mv.votes[23].votes, 1)

    # 같은 번호 다른 카메라
    jn2 = JerseyNumber(number=23, confidence=0.85)
    mv.add_result("cam_02", jn2)
    assert_eq(r, "add2 후 num_views=2", mv.num_views, 2)
    assert_eq(r, "같은 번호 candidates=1", mv.num_candidates, 1)
    assert_eq(r, "23 투표수=2", mv.votes[23].votes, 2)

    # 다른 번호 추가
    jn3 = JerseyNumber(number=45, confidence=0.6)
    mv.add_result("cam_03", jn3)
    assert_eq(r, "add3 후 num_candidates=2", mv.num_candidates, 2)

    # 무효한 등번호는 무시
    jn_invalid = JerseyNumber(number=-1)
    mv.add_result("cam_04", jn_invalid)
    assert_eq(r, "invalid 등번호 무시 views=3", mv.num_views, 3)


def test_multiview_resolve(r: TestResult) -> None:
    """MultiViewOCRResult resolve() 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=1)
    mv.add_result("cam_01", JerseyNumber(number=23, confidence=0.9))
    mv.add_result("cam_02", JerseyNumber(number=23, confidence=0.85))
    mv.add_result("cam_03", JerseyNumber(number=45, confidence=0.6))

    mv.resolve()
    assert_eq(r, "resolve 후 final_number=23", mv.final_number, 23)
    assert_true(r, "resolve 후 has_result", mv.has_result)
    assert_close(r, "final_confidence≈0.875", mv.final_confidence, 0.875)
    assert_false(r, "not unanimous (2 candidates)", mv.is_unanimous)


def test_multiview_resolve_unanimous(r: TestResult) -> None:
    """MultiViewOCRResult resolve() 만장일치 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=2)
    mv.add_result("cam_01", JerseyNumber(number=7, confidence=0.95))
    mv.add_result("cam_02", JerseyNumber(number=7, confidence=0.90))
    mv.add_result("cam_03", JerseyNumber(number=7, confidence=0.88))

    mv.resolve()
    assert_eq(r, "만장일치 final=7", mv.final_number, 7)
    assert_true(r, "만장일치 is_unanimous", mv.is_unanimous)


def test_multiview_resolve_min_votes(r: TestResult) -> None:
    """MultiViewOCRResult resolve() min_votes 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=3)
    mv.add_result("cam_01", JerseyNumber(number=10, confidence=0.7))

    # min_votes=2인데 1개만 있으면 결정 안됨
    mv.resolve(min_votes=2)
    assert_none(r, "min_votes=2 미달 시 None", mv.final_number)

    # min_votes=1이면 결정됨
    mv.resolve(min_votes=1)
    assert_eq(r, "min_votes=1 충족 시 10", mv.final_number, 10)


def test_multiview_resolve_empty(r: TestResult) -> None:
    """MultiViewOCRResult resolve() 빈 투표 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult

    mv = MultiViewOCRResult()
    mv.resolve()
    assert_none(r, "빈 투표 resolve 후 None", mv.final_number)
    assert_false(r, "빈 투표 has_result=False", mv.has_result)


def test_multiview_to_jersey_number(r: TestResult) -> None:
    """MultiViewOCRResult to_jersey_number() 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    # resolve 안 한 경우
    mv = MultiViewOCRResult(person_id=5)
    assert_none(r, "resolve 전 to_jersey_number=None", mv.to_jersey_number())

    # resolve 후
    mv.add_result("cam_01", JerseyNumber(number=33, confidence=0.9))
    mv.add_result("cam_02", JerseyNumber(number=33, confidence=0.85))
    mv.resolve()

    jn = mv.to_jersey_number()
    assert_not_none(r, "resolve 후 to_jersey_number != None", jn)
    assert_eq(r, "변환 number=33", jn.number, 33)
    assert_eq(r, "변환 source='multiview'", jn.source, "multiview")
    assert_eq(r, "변환 person_id=5", jn.person_id, 5)
    assert_eq(r, "변환 confirmation_count=2", jn.confirmation_count, 2)


def test_multiview_winning_margin(r: TestResult) -> None:
    """MultiViewOCRResult winning_margin 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=1)
    mv.add_result("cam_01", JerseyNumber(number=23, confidence=0.9))
    mv.add_result("cam_02", JerseyNumber(number=23, confidence=0.85))
    mv.add_result("cam_03", JerseyNumber(number=45, confidence=0.6))
    mv.resolve()

    # 23이 2표, 45가 1표 → margin=1
    assert_eq(r, "winning_margin=1", mv.winning_margin, 1)


def test_multiview_winning_margin_single(r: TestResult) -> None:
    """MultiViewOCRResult winning_margin 단일 후보 검증"""
    from shared.dto.ocr_dto import MultiViewOCRResult, JerseyNumber

    mv = MultiViewOCRResult(person_id=2)
    mv.add_result("cam_01", JerseyNumber(number=7, confidence=0.9))
    mv.add_result("cam_02", JerseyNumber(number=7, confidence=0.85))
    mv.resolve()

    # 7이 2표, 후보 1개 → margin = votes
    assert_eq(r, "단일 후보 winning_margin=2", mv.winning_margin, 2)


# ==================== [H] OCRAnalysisResult ====================
def test_analysis_result_defaults(r: TestResult) -> None:
    """OCRAnalysisResult 기본값 검증"""
    from shared.dto.ocr_dto import OCRAnalysisResult

    ar = OCRAnalysisResult()
    assert_eq(r, "기본 frame_index=0", ar.frame_index, 0)
    assert_close(r, "기본 timestamp=0.0", ar.timestamp, 0.0)
    assert_eq(r, "기본 ocr_results=[]", ar.ocr_results, [])
    assert_eq(r, "기본 jersey_numbers=[]", ar.jersey_numbers, [])
    assert_eq(r, "기본 num_detections=0", ar.num_detections, 0)
    assert_eq(r, "기본 num_jersey_numbers=0", ar.num_jersey_numbers, 0)
    assert_close(r, "기본 average_confidence=0.0", ar.average_confidence, 0.0)


def test_analysis_result_properties(r: TestResult) -> None:
    """OCRAnalysisResult 프로퍼티 검증"""
    from shared.dto.ocr_dto import OCRAnalysisResult, OCRResult, JerseyNumber, OCRStatus

    ocr1 = OCRResult(text="23", status=OCRStatus.SUCCESS, confidence=0.9)
    ocr2 = OCRResult(text="45", status=OCRStatus.PARTIAL, confidence=0.7)
    jn1 = JerseyNumber(number=23, confidence=0.9, person_id=1)
    jn2 = JerseyNumber(number=45, confidence=0.7, person_id=2)
    jn3 = JerseyNumber(number=-1, confidence=0.3, person_id=3)  # invalid

    ar = OCRAnalysisResult(
        frame_index=100,
        timestamp=3.33,
        ocr_results=[ocr1, ocr2],
        jersey_numbers=[jn1, jn2, jn3],
        processing_time_ms=5.2,
        camera_id="cam_01",
    )

    assert_eq(r, "num_detections=2", ar.num_detections, 2)
    assert_eq(r, "num_jersey_numbers=3", ar.num_jersey_numbers, 3)

    # valid_jersey_numbers: number 0-99만
    valid = ar.valid_jersey_numbers
    assert_eq(r, "valid_jersey_numbers 개수=2", len(valid), 2)
    assert_eq(r, "valid[0].number=23", valid[0].number, 23)
    assert_eq(r, "valid[1].number=45", valid[1].number, 45)

    # average_confidence: (0.9 + 0.7 + 0.3) / 3
    assert_close(r, "average_confidence≈0.633", ar.average_confidence, 0.6333, tol=0.01)


def test_analysis_result_get_jersey_number(r: TestResult) -> None:
    """OCRAnalysisResult get_jersey_number() 검증"""
    from shared.dto.ocr_dto import OCRAnalysisResult, JerseyNumber

    jn1 = JerseyNumber(number=23, person_id=1)
    jn2 = JerseyNumber(number=45, person_id=2)
    ar = OCRAnalysisResult(jersey_numbers=[jn1, jn2])

    found = ar.get_jersey_number(1)
    assert_not_none(r, "person_id=1 조회 성공", found)
    assert_eq(r, "조회 결과 number=23", found.number, 23)

    found2 = ar.get_jersey_number(2)
    assert_eq(r, "person_id=2 number=45", found2.number, 45)

    not_found = ar.get_jersey_number(999)
    assert_none(r, "존재하지 않는 person_id=None", not_found)


# ==================== [I] SupportedLanguage re-export ====================
def test_supported_language_reexport(r: TestResult) -> None:
    """SupportedLanguage re-export 검증"""
    from shared.dto.ocr_dto import SupportedLanguage
    from shared.constants.localization import SupportedLanguage as Original

    assert_true(r, "SupportedLanguage re-export 동일", SupportedLanguage is Original)
    assert_eq(r, "KO 값", SupportedLanguage.KO.value, "ko")
    assert_eq(r, "EN 값", SupportedLanguage.EN.value, "en")


# ==================== [J] dataclass 속성 할당 ====================
def test_ocr_result_with_all_fields(r: TestResult) -> None:
    """OCRResult 모든 필드 설정 검증"""
    from shared.dto.ocr_dto import OCRResult, OCRStatus, OCRBackend
    from shared.dto.geometry_dto import BoundingBox

    res = OCRResult(
        text="23",
        confidence=0.95,
        bbox=BoundingBox(10, 20, 50, 80),
        status=OCRStatus.SUCCESS,
        backend=OCRBackend.PADDLEOCR,
        language="ko",
        frame_index=500,
        camera_id="cam_02",
        processing_time_ms=2.5,
        raw_output={"detail": "test"},
    )

    assert_eq(r, "full text='23'", res.text, "23")
    assert_close(r, "full confidence=0.95", res.confidence, 0.95)
    assert_not_none(r, "full bbox != None", res.bbox)
    assert_eq(r, "full status=SUCCESS", res.status, OCRStatus.SUCCESS)
    assert_eq(r, "full backend=PADDLEOCR", res.backend, OCRBackend.PADDLEOCR)
    assert_eq(r, "full language='ko'", res.language, "ko")
    assert_eq(r, "full frame_index=500", res.frame_index, 500)
    assert_eq(r, "full camera_id='cam_02'", res.camera_id, "cam_02")
    assert_eq(r, "full raw_output", res.raw_output, {"detail": "test"})


def test_jersey_number_with_ocr_result(r: TestResult) -> None:
    """JerseyNumber OCRResult 연관 검증"""
    from shared.dto.ocr_dto import JerseyNumber, OCRResult, OCRStatus
    from shared.dto.geometry_dto import BoundingBox

    ocr = OCRResult(text="23", confidence=0.9, status=OCRStatus.SUCCESS)
    jn = JerseyNumber(
        number=23,
        confidence=0.9,
        source="back",
        ocr_result=ocr,
        person_id=5,
        bbox=BoundingBox(100, 200, 50, 80),
        is_confirmed=True,
        confirmation_count=3,
    )

    assert_eq(r, "jn.number=23", jn.number, 23)
    assert_eq(r, "jn.source='back'", jn.source, "back")
    assert_not_none(r, "jn.ocr_result != None", jn.ocr_result)
    assert_eq(r, "jn.ocr_result.text='23'", jn.ocr_result.text, "23")
    assert_eq(r, "jn.person_id=5", jn.person_id, 5)
    assert_true(r, "jn.is_confirmed", jn.is_confirmed)
    assert_eq(r, "jn.confirmation_count=3", jn.confirmation_count, 3)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("ocr_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- [A] __all__ / __version__ ---")
    test_exports(r)
    test_version(r)

    print("\n--- [B] OCRBackend Enum ---")
    test_ocr_backend_members(r)
    test_ocr_backend_properties(r)
    test_ocr_backend_i18n(r)

    print("\n--- [C] OCRStatus Enum ---")
    test_ocr_status_members(r)
    test_ocr_status_properties(r)
    test_ocr_status_i18n(r)

    print("\n--- [D] OCRResult ---")
    test_ocr_result_defaults(r)
    test_ocr_result_post_init(r)
    test_ocr_result_properties(r)
    test_ocr_result_as_integer(r)

    print("\n--- [E] JerseyNumber ---")
    test_jersey_number_defaults(r)
    test_jersey_number_post_init(r)
    test_jersey_number_properties(r)
    test_jersey_number_matches(r)

    print("\n--- [F] JerseyNumberVote ---")
    test_jersey_number_vote_defaults(r)
    test_jersey_number_vote_add_vote(r)

    print("\n--- [G] MultiViewOCRResult ---")
    test_multiview_defaults(r)
    test_multiview_add_result(r)
    test_multiview_resolve(r)
    test_multiview_resolve_unanimous(r)
    test_multiview_resolve_min_votes(r)
    test_multiview_resolve_empty(r)
    test_multiview_to_jersey_number(r)
    test_multiview_winning_margin(r)
    test_multiview_winning_margin_single(r)

    print("\n--- [H] OCRAnalysisResult ---")
    test_analysis_result_defaults(r)
    test_analysis_result_properties(r)
    test_analysis_result_get_jersey_number(r)

    print("\n--- [I] SupportedLanguage re-export ---")
    test_supported_language_reexport(r)

    print("\n--- [J] 전체 필드 검증 ---")
    test_ocr_result_with_all_fields(r)
    test_jersey_number_with_ocr_result(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
