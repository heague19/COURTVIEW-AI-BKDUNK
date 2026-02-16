# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/unit
파일: test_validation_exceptions.py
설명: validation_exceptions.py 단위 테스트 (31개 클래스, 22+ 팩토리 메서드)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import sys
import io

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
)
from shared.exceptions.validation_exceptions import (
    # 기본 유효성 검사
    ValidationException,
    InvalidRequestException,
    InputValidationException,
    # 필드 유효성 검사
    MissingFieldException,
    InvalidFieldTypeException,
    InvalidFieldValueException,
    # 값 범위/길이
    ValueOutOfRangeException,
    StringLengthException,
    # 데이터 형식
    InvalidEnumValueException,
    InvalidJsonFormatException,
    InvalidDateFormatException,
    # URL 검증
    URLValidationException,
    # 보안
    SecurityException,
    # 파일 포맷
    FormatDetectionException,
    UnsupportedFormatException,
    FormatValidationException,
    ResolutionException,
    # 설정
    ConfigurationException,
    ConfigurationNotFoundException,
    ConfigurationLoadException,
    ConfigurationParseException,
    ConfigurationValidationException,
    # 스키마
    SchemaValidationException,
    # 인증/권한
    AuthenticationException,
    AuthorizationException,
    # 속도 제한
    RateLimitException,
    # 데이터 품질
    DataQualityException,
    LowQualityException,
    # 규칙 세트
    RuleSetNotFoundException,
    RuleSetValidationException,
    RuleSetVersionMismatchException,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  단위 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def check(r: TestResult, name: str, condition: bool, reason: str = "") -> None:
    """조건 검사 헬퍼."""
    if condition:
        r.ok(name)
    else:
        r.fail(name, reason or "조건 불일치")


# =============================================================================
# [1] 기본 유효성 검사 예외
# =============================================================================
def test_validation_exception(r: TestResult) -> None:
    """ValidationException 기본 테스트."""
    # 기본 생성
    e = ValidationException()
    check(r, "ValidationException() 기본 생성", isinstance(e, NonRetryableException))
    check(r, "ValidationException 기본 ErrorCode", e.code == ErrorCode.VALIDATION_ERROR.code)
    check(r, "ValidationException field_name None", e.field_name is None)
    check(r, "ValidationException field_value None", e.field_value is None)

    # 필드명/값 포함 생성
    e2 = ValidationException(
        field_name="email",
        field_value="bad@",
    )
    check(r, "ValidationException field_name 설정", e2.field_name == "email")
    check(r, "ValidationException field_value 설정", e2.field_value == "bad@")
    d = e2.to_dict()
    check(r, "ValidationException details에 field_name 포함",
          d.get("details", {}).get("field_name") == "email")
    check(r, "ValidationException details에 field_value 포함",
          d.get("details", {}).get("field_value") == "bad@")

    # 민감 필드 마스킹 - password
    e3 = ValidationException(field_name="password", field_value="secret123")
    d3 = e3.to_dict()
    check(r, "민감필드 마스킹 (password)",
          d3.get("details", {}).get("field_value") == "***MASKED***")
    check(r, "민감필드 원본 보존", e3.field_value == "secret123")

    # 민감 필드 마스킹 - api_key
    e4 = ValidationException(field_name="api_key", field_value="sk-12345")
    d4 = e4.to_dict()
    check(r, "민감필드 마스킹 (api_key)",
          d4.get("details", {}).get("field_value") == "***MASKED***")

    # 민감 필드 마스킹 - secret_token
    e5 = ValidationException(field_name="secret_token", field_value="tok-abc")
    d5 = e5.to_dict()
    check(r, "민감필드 마스킹 (secret_token)",
          d5.get("details", {}).get("field_value") == "***MASKED***")

    # 비민감 필드는 마스킹 안됨
    e6 = ValidationException(field_name="username", field_value="john")
    d6 = e6.to_dict()
    check(r, "비민감필드 마스킹 없음",
          d6.get("details", {}).get("field_value") == "john")

    # cause 전달
    cause = ValueError("원인")
    e7 = ValidationException(cause=cause)
    check(r, "ValidationException cause 전달", e7.__cause__ is cause)


def test_invalid_request_exception(r: TestResult) -> None:
    """InvalidRequestException 테스트."""
    e = InvalidRequestException()
    check(r, "InvalidRequestException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidRequestException ErrorCode", e.code == ErrorCode.INVALID_REQUEST.code)
    check(r, "InvalidRequestException 기본 메시지", "잘못된 요청" in str(e))

    e2 = InvalidRequestException("커스텀 메시지", details={"key": "val"})
    check(r, "InvalidRequestException 커스텀 메시지", "커스텀 메시지" in str(e2))
    d = e2.to_dict()
    check(r, "InvalidRequestException details 전달",
          d.get("details", {}).get("key") == "val")


def test_input_validation_exception(r: TestResult) -> None:
    """InputValidationException 테스트."""
    # 기본 생성
    e = InputValidationException()
    check(r, "InputValidationException 기본 생성", isinstance(e, ValidationException))
    check(r, "InputValidationException 기본 메시지", "입력 데이터 검증" in str(e))
    check(r, "InputValidationException field_errors 빈 딕셔너리", e.field_errors == {})
    check(r, "InputValidationException has_errors() False", e.has_errors() is False)

    # field_errors 포함 생성
    errors = {"name": ["필수 입력"], "email": ["형식 오류", "도메인 미지원"]}
    e2 = InputValidationException(field_errors=errors, input_source="body")
    check(r, "InputValidationException field_errors 설정", e2.field_errors == errors)
    check(r, "InputValidationException input_source 설정", e2.input_source == "body")
    check(r, "InputValidationException has_errors() True", e2.has_errors() is True)
    d = e2.to_dict()
    check(r, "InputValidationException error_count 3",
          d.get("details", {}).get("error_count") == 3)

    # add_field_error 체이닝
    e3 = InputValidationException()
    result = e3.add_field_error("age", "숫자여야 합니다")
    check(r, "add_field_error 반환값 self", result is e3)
    check(r, "add_field_error 필드 추가", "age" in e3.field_errors)
    check(r, "add_field_error has_errors() True", e3.has_errors() is True)

    # 연속 체이닝
    e3.add_field_error("age", "양수여야 합니다").add_field_error("name", "필수")
    check(r, "add_field_error 연속 체이닝 age 2개", len(e3.field_errors["age"]) == 2)
    check(r, "add_field_error 연속 체이닝 name 1개", len(e3.field_errors["name"]) == 1)
    check(r, "add_field_error details 동기화",
          e3.details.get("error_count") == 3)


# =============================================================================
# [2] 필드 유효성 검사 예외
# =============================================================================
def test_missing_field_exception(r: TestResult) -> None:
    """MissingFieldException 테스트."""
    e = MissingFieldException("name")
    check(r, "MissingFieldException 기본 생성", isinstance(e, ValidationException))
    check(r, "MissingFieldException ErrorCode",
          e.code == ErrorCode.MISSING_REQUIRED_FIELD.code)
    check(r, "MissingFieldException field_name", e.field_name == "name")
    check(r, "MissingFieldException 메시지에 필드명", "name" in str(e))

    # parent_field 포함
    e2 = MissingFieldException("city", parent_field="address")
    check(r, "MissingFieldException parent_field 결합",
          e2.field_name == "address.city")
    check(r, "MissingFieldException 메시지에 full_field", "address.city" in str(e2))
    d = e2.to_dict()
    check(r, "MissingFieldException details에 parent_field",
          d.get("details", {}).get("parent_field") == "address")


def test_invalid_field_type_exception(r: TestResult) -> None:
    """InvalidFieldTypeException 테스트."""
    # type 객체 전달
    e = InvalidFieldTypeException("age", int, str, "hello")
    check(r, "InvalidFieldTypeException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidFieldTypeException ErrorCode",
          e.code == ErrorCode.INVALID_FIELD_TYPE.code)
    check(r, "InvalidFieldTypeException 메시지에 타입명", "int" in str(e) and "str" in str(e))
    d = e.to_dict()
    check(r, "InvalidFieldTypeException expected_type",
          d.get("details", {}).get("expected_type") == "int")
    check(r, "InvalidFieldTypeException received_type",
          d.get("details", {}).get("received_type") == "str")

    # 문자열 타입 전달
    e2 = InvalidFieldTypeException("score", "float", "string")
    check(r, "InvalidFieldTypeException 문자열 타입", "float" in str(e2) and "string" in str(e2))


def test_invalid_field_value_exception(r: TestResult) -> None:
    """InvalidFieldValueException 테스트."""
    e = InvalidFieldValueException("status", "unknown", "허용되지 않는 상태")
    check(r, "InvalidFieldValueException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidFieldValueException ErrorCode",
          e.code == ErrorCode.INVALID_FIELD_VALUE.code)
    check(r, "InvalidFieldValueException 메시지", "status" in str(e))
    check(r, "InvalidFieldValueException field_value", e.field_value == "unknown")

    # allowed_values 포함
    e2 = InvalidFieldValueException(
        "status", "unknown", "무효",
        allowed_values=["active", "inactive", "pending"],
    )
    d = e2.to_dict()
    check(r, "InvalidFieldValueException allowed_values",
          d.get("details", {}).get("allowed_values") == ["active", "inactive", "pending"])


# =============================================================================
# [3] 값 범위/길이 예외
# =============================================================================
def test_value_out_of_range_exception(r: TestResult) -> None:
    """ValueOutOfRangeException 테스트."""
    # min + max
    e = ValueOutOfRangeException("fps", 200.0, min_value=15.0, max_value=120.0)
    check(r, "ValueOutOfRangeException min+max 생성", isinstance(e, ValidationException))
    check(r, "ValueOutOfRangeException ErrorCode",
          e.code == ErrorCode.VALUE_OUT_OF_RANGE.code)
    check(r, "ValueOutOfRangeException 범위 메시지", "15.0~120.0" in str(e))
    d = e.to_dict()
    check(r, "ValueOutOfRangeException details min_value",
          d.get("details", {}).get("min_value") == 15.0)
    check(r, "ValueOutOfRangeException details max_value",
          d.get("details", {}).get("max_value") == 120.0)

    # min only
    e2 = ValueOutOfRangeException("score", -5, min_value=0)
    check(r, "ValueOutOfRangeException min only 메시지", "최소값" in str(e2))

    # max only
    e3 = ValueOutOfRangeException("size", 1000, max_value=500)
    check(r, "ValueOutOfRangeException max only 메시지", "최대값" in str(e3))

    # both None
    e4 = ValueOutOfRangeException("value", 999)
    check(r, "ValueOutOfRangeException no bounds 메시지", "허용 범위" in str(e4))


def test_string_length_exception(r: TestResult) -> None:
    """StringLengthException 테스트."""
    # 너무 짧음
    e = StringLengthException("name", 2, min_length=3)
    check(r, "StringLengthException 너무 짧음", isinstance(e, ValidationException))
    check(r, "StringLengthException SHORT ErrorCode",
          e.code == ErrorCode.STRING_TOO_SHORT.code)
    check(r, "StringLengthException 짧음 메시지", "짧습니다" in str(e))

    # 너무 긺
    e2 = StringLengthException("bio", 1000, max_length=500)
    check(r, "StringLengthException LONG ErrorCode",
          e2.code == ErrorCode.STRING_TOO_LONG.code)
    check(r, "StringLengthException 긺 메시지", "깁니다" in str(e2))

    # 기본 (neither short nor long trigger)
    e3 = StringLengthException("field", 50)
    check(r, "StringLengthException 기본 VALIDATION_ERROR",
          e3.code == ErrorCode.VALIDATION_ERROR.code)

    # details 검증
    d = e.to_dict()
    check(r, "StringLengthException details actual_length",
          d.get("details", {}).get("actual_length") == 2)
    check(r, "StringLengthException details min_length",
          d.get("details", {}).get("min_length") == 3)


# =============================================================================
# [4] 데이터 형식 예외
# =============================================================================
def test_invalid_enum_value_exception(r: TestResult) -> None:
    """InvalidEnumValueException 테스트."""
    allowed = ["active", "inactive", "pending"]
    e = InvalidEnumValueException("status", "unknown", allowed)
    check(r, "InvalidEnumValueException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidEnumValueException ErrorCode",
          e.code == ErrorCode.INVALID_ENUM_VALUE.code)
    check(r, "InvalidEnumValueException 메시지에 값", "unknown" in str(e))
    check(r, "InvalidEnumValueException 메시지에 허용값", "active" in str(e))

    # 10개 초과 시 표시 제한
    many = [f"val_{i}" for i in range(15)]
    e2 = InvalidEnumValueException("type", "bad", many)
    check(r, "InvalidEnumValueException 10개 제한 표시", "외 5개" in str(e2))

    # 정확히 10개
    ten = [f"val_{i}" for i in range(10)]
    e3 = InvalidEnumValueException("type", "bad", ten)
    check(r, "InvalidEnumValueException 10개 정확 표시", "외" not in str(e3))


def test_invalid_json_format_exception(r: TestResult) -> None:
    """InvalidJsonFormatException 테스트."""
    e = InvalidJsonFormatException()
    check(r, "InvalidJsonFormatException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidJsonFormatException ErrorCode",
          e.code == ErrorCode.INVALID_JSON_FORMAT.code)
    check(r, "InvalidJsonFormatException 기본 메시지", "JSON" in str(e))

    # line/column 포함
    e2 = InvalidJsonFormatException("파싱 실패", line=10, column=5)
    d = e2.to_dict()
    check(r, "InvalidJsonFormatException line 정보",
          d.get("details", {}).get("line") == 10)
    check(r, "InvalidJsonFormatException column 정보",
          d.get("details", {}).get("column") == 5)

    # line만
    e3 = InvalidJsonFormatException(line=3)
    d3 = e3.to_dict()
    check(r, "InvalidJsonFormatException line만", d3.get("details", {}).get("line") == 3)
    check(r, "InvalidJsonFormatException column 없음",
          "column" not in d3.get("details", {}))


def test_invalid_date_format_exception(r: TestResult) -> None:
    """InvalidDateFormatException 테스트."""
    e = InvalidDateFormatException("birth_date", "2024-13-45")
    check(r, "InvalidDateFormatException 기본 생성", isinstance(e, ValidationException))
    check(r, "InvalidDateFormatException ErrorCode",
          e.code == ErrorCode.INVALID_DATE_FORMAT.code)
    check(r, "InvalidDateFormatException 기본 형식 YYYY-MM-DD",
          "YYYY-MM-DD" in str(e))
    check(r, "InvalidDateFormatException field_value", e.field_value == "2024-13-45")

    # 커스텀 형식
    e2 = InvalidDateFormatException("timestamp", "abc", expected_format="ISO8601")
    check(r, "InvalidDateFormatException 커스텀 형식", "ISO8601" in str(e2))
    d = e2.to_dict()
    check(r, "InvalidDateFormatException details expected_format",
          d.get("details", {}).get("expected_format") == "ISO8601")


# =============================================================================
# [5] URL 검증 예외
# =============================================================================
def test_url_validation_exception(r: TestResult) -> None:
    """URLValidationException 기본 + 팩토리 메서드 테스트."""
    # 기본 생성
    e = URLValidationException()
    check(r, "URLValidationException 기본 생성", isinstance(e, ValidationException))
    check(r, "URLValidationException ErrorCode",
          e.code == ErrorCode.URL_VALIDATION_ERROR.code)

    # URL 속성
    e2 = URLValidationException(
        url="https://user:pass@example.com/path?key=val",
        scheme="https",
        host="example.com",
        reason="test",
    )
    check(r, "URLValidationException url 속성", e2.url is not None)
    check(r, "URLValidationException scheme 속성", e2.scheme == "https")
    check(r, "URLValidationException host 속성", e2.host == "example.com")
    check(r, "URLValidationException reason 속성", e2.reason == "test")

    # _sanitize_url 테스트 - 쿼리 파라미터 제거
    sanitized = URLValidationException._sanitize_url("https://example.com/path?key=secret")
    check(r, "_sanitize_url 쿼리 제거", "key=secret" not in sanitized)
    check(r, "_sanitize_url 경로 유지", "/path" in sanitized)

    # _sanitize_url - 인증 정보 제거
    sanitized2 = URLValidationException._sanitize_url("https://user:pass@example.com/path")
    check(r, "_sanitize_url 인증정보 제거", "user:pass" not in sanitized2)
    check(r, "_sanitize_url 호스트 유지", "example.com" in sanitized2)

    # _sanitize_url - 잘못된 URL
    sanitized3 = URLValidationException._sanitize_url("not a url <<<>>>")
    check(r, "_sanitize_url 잘못된 URL 처리", isinstance(sanitized3, str))

    # details에 sanitized URL
    d = e2.to_dict()
    details_url = d.get("details", {}).get("url", "")
    check(r, "URLValidationException details URL sanitized",
          "user:pass" not in details_url)

    # --- 팩토리 메서드 ---

    # invalid_format
    f1 = URLValidationException.invalid_format("http://bad url", "공백 포함")
    check(r, "invalid_format ErrorCode", f1.code == ErrorCode.URL_INVALID_FORMAT.code)
    check(r, "invalid_format 메시지", "유효하지 않은 URL" in str(f1))
    check(r, "invalid_format reason", f1.reason == "공백 포함")

    # invalid_format reason 없음
    f1b = URLValidationException.invalid_format("http://bad")
    check(r, "invalid_format reason 기본값", f1b.reason == "invalid_format")

    # invalid_scheme
    f2 = URLValidationException.invalid_scheme("ftp://evil.com", "ftp", ["http", "https"])
    check(r, "invalid_scheme ErrorCode", f2.code == ErrorCode.URL_INVALID_SCHEME.code)
    check(r, "invalid_scheme 메시지에 스킴", "ftp" in str(f2))
    check(r, "invalid_scheme 허용 스킴", "http" in str(f2))
    check(r, "invalid_scheme scheme 속성", f2.scheme == "ftp")

    # blocked_host
    f3 = URLValidationException.blocked_host("http://evil.com", "evil.com", "블랙리스트")
    check(r, "blocked_host ErrorCode", f3.code == ErrorCode.URL_BLOCKED_HOST.code)
    check(r, "blocked_host host 속성", f3.host == "evil.com")
    check(r, "blocked_host reason", f3.reason == "블랙리스트")

    # blocked_host reason 없음
    f3b = URLValidationException.blocked_host("http://x.com", "x.com")
    check(r, "blocked_host reason 기본값", f3b.reason == "blocked_host")

    # private_ip
    f4 = URLValidationException.private_ip("http://192.168.1.1/admin", "192.168.1.1")
    check(r, "private_ip ErrorCode", f4.code == ErrorCode.URL_PRIVATE_IP.code)
    check(r, "private_ip host=ip", f4.host == "192.168.1.1")
    check(r, "private_ip 메시지에 IP", "192.168.1.1" in str(f4))

    # too_long
    f5 = URLValidationException.too_long("http://x.com/" + "a" * 5000, 5015, 2048)
    check(r, "too_long ErrorCode", f5.code == ErrorCode.URL_TOO_LONG.code)
    check(r, "too_long 메시지에 길이", "5015" in str(f5))
    d5 = f5.to_dict()
    check(r, "too_long details length",
          d5.get("details", {}).get("length") == 5015)
    check(r, "too_long details max_length",
          d5.get("details", {}).get("max_length") == 2048)


# =============================================================================
# [6] 보안 예외
# =============================================================================
def test_security_exception(r: TestResult) -> None:
    """SecurityException 기본 + 팩토리 메서드 테스트."""
    # 기본 생성 - NonRetryableException 직접 상속 (ValidationException 아님)
    e = SecurityException()
    check(r, "SecurityException 기본 생성", isinstance(e, NonRetryableException))
    check(r, "SecurityException NOT ValidationException",
          not isinstance(e, ValidationException))
    check(r, "SecurityException ErrorCode", e.code == ErrorCode.SECURITY_ERROR.code)
    check(r, "SecurityException 속성 기본 None",
          e.threat_type is None and e.source is None and e.target is None)

    # 전체 인수
    e2 = SecurityException(
        threat_type="ssrf",
        source="http://evil.com",
        target="192.168.1.1",
    )
    check(r, "SecurityException 속성 설정", e2.threat_type == "ssrf")
    d = e2.to_dict()
    check(r, "SecurityException details threat_type",
          d.get("details", {}).get("threat_type") == "ssrf")

    # ssrf_detected 팩토리
    f1 = SecurityException.ssrf_detected(
        "http://evil.com/internal",
        target_ip="10.0.0.1",
        reason="내부망 접근",
    )
    check(r, "ssrf_detected ErrorCode", f1.code == ErrorCode.SSRF_DETECTED.code)
    check(r, "ssrf_detected threat_type", f1.threat_type == "ssrf")
    check(r, "ssrf_detected source", f1.source == "http://evil.com/internal")
    check(r, "ssrf_detected target", f1.target == "10.0.0.1")
    check(r, "ssrf_detected 메시지", "SSRF" in str(f1))

    # dns_rebinding_detected 팩토리
    f2 = SecurityException.dns_rebinding_detected(
        "evil.example.com",
        resolved_ips=["1.2.3.4", "10.0.0.1"],
    )
    check(r, "dns_rebinding ErrorCode", f2.code == ErrorCode.DNS_REBINDING_DETECTED.code)
    check(r, "dns_rebinding threat_type", f2.threat_type == "dns_rebinding")
    check(r, "dns_rebinding source", f2.source == "evil.example.com")
    d2 = f2.to_dict()
    check(r, "dns_rebinding resolved_ips",
          d2.get("details", {}).get("resolved_ips") == ["1.2.3.4", "10.0.0.1"])


# =============================================================================
# [7] 파일 포맷 감지 예외
# =============================================================================
def test_format_detection_exception(r: TestResult) -> None:
    """FormatDetectionException 기본 + 팩토리 메서드 테스트."""
    # 기본 생성
    e = FormatDetectionException()
    check(r, "FormatDetectionException 기본 생성", isinstance(e, ValidationException))
    check(r, "FormatDetectionException ErrorCode",
          e.code == ErrorCode.FORMAT_DETECTION_ERROR.code)

    # 전체 인수
    e2 = FormatDetectionException(
        file_path="/tmp/video.mp4",
        detected_format="avi",
        expected_format="mp4",
        reason="mismatch",
    )
    check(r, "FormatDetectionException 속성 file_path", e2.file_path == "/tmp/video.mp4")
    check(r, "FormatDetectionException 속성 detected_format", e2.detected_format == "avi")
    check(r, "FormatDetectionException 속성 expected_format", e2.expected_format == "mp4")
    check(r, "FormatDetectionException 속성 reason", e2.reason == "mismatch")

    # read_failed 팩토리
    f1 = FormatDetectionException.read_failed("/tmp/bad.mp4", "권한 부족")
    check(r, "read_failed ErrorCode", f1.code == ErrorCode.FORMAT_DETECTION_ERROR.code)
    check(r, "read_failed 메시지", "읽기" in str(f1))
    check(r, "read_failed reason", f1.reason == "권한 부족")

    # read_failed reason 없음
    f1b = FormatDetectionException.read_failed("/tmp/x.mp4")
    check(r, "read_failed reason 기본값", f1b.reason == "read_failed")

    # invalid_magic_bytes 팩토리
    f2 = FormatDetectionException.invalid_magic_bytes("/tmp/fake.mp4", b"\x00\x01\x02\x03")
    check(r, "invalid_magic_bytes ErrorCode", f2.code == ErrorCode.INVALID_MAGIC_BYTES.code)
    check(r, "invalid_magic_bytes 메시지", "시그니처" in str(f2))
    d2 = f2.to_dict()
    check(r, "invalid_magic_bytes hex 포함",
          "magic_bytes_hex" in d2.get("details", {}))

    # invalid_magic_bytes bytes 없음
    f2b = FormatDetectionException.invalid_magic_bytes("/tmp/x.mp4")
    check(r, "invalid_magic_bytes bytes 없음 OK", f2b.reason == "invalid_magic_bytes")

    # corrupted_file 팩토리
    f3 = FormatDetectionException.corrupted_file("/tmp/broken.mp4", "헤더 손상")
    check(r, "corrupted_file ErrorCode", f3.code == ErrorCode.CORRUPTED_FILE.code)
    check(r, "corrupted_file 메시지", "손상" in str(f3))
    check(r, "corrupted_file reason", f3.reason == "헤더 손상")

    # corrupted_file reason 없음
    f3b = FormatDetectionException.corrupted_file("/tmp/x.mp4")
    check(r, "corrupted_file reason 기본값", f3b.reason == "corrupted")

    # format_mismatch 팩토리
    f4 = FormatDetectionException.format_mismatch("/tmp/video.mp4", "avi", "mp4")
    check(r, "format_mismatch ErrorCode", f4.code == ErrorCode.FORMAT_MISMATCH.code)
    check(r, "format_mismatch detected_format", f4.detected_format == "avi")
    check(r, "format_mismatch expected_format", f4.expected_format == "mp4")
    check(r, "format_mismatch 메시지", "불일치" in str(f4))


# =============================================================================
# [8] 지원하지 않는 포맷 예외
# =============================================================================
def test_unsupported_format_exception(r: TestResult) -> None:
    """UnsupportedFormatException 기본 + 팩토리 메서드 테스트."""
    # 기본 생성
    e = UnsupportedFormatException()
    check(r, "UnsupportedFormatException 기본 생성", isinstance(e, ValidationException))
    check(r, "UnsupportedFormatException ErrorCode",
          e.code == ErrorCode.UNSUPPORTED_FORMAT.code)

    # video_format 팩토리
    f1 = UnsupportedFormatException.video_format("/tmp/video.wmv", "WMV")
    check(r, "video_format 기본 지원 포맷",
          f1.supported_formats == ["MP4", "MOV", "AVI", "MKV", "WEBM"])
    check(r, "video_format 메시지에 포맷", "WMV" in str(f1))
    check(r, "video_format detected_format", f1.detected_format == "WMV")

    # video_format 커스텀 지원 포맷
    f1b = UnsupportedFormatException.video_format("/tmp/x.flv", "FLV", ["MP4", "MOV"])
    check(r, "video_format 커스텀 지원 포맷", f1b.supported_formats == ["MP4", "MOV"])

    # image_format 팩토리
    f2 = UnsupportedFormatException.image_format("/tmp/img.tiff", "TIFF")
    check(r, "image_format 기본 지원 포맷",
          f2.supported_formats == ["JPEG", "PNG", "BMP", "WEBP", "GIF"])
    check(r, "image_format 메시지", "이미지" in str(f2))

    # audio_format 팩토리
    f3 = UnsupportedFormatException.audio_format("/tmp/audio.wma", "WMA")
    check(r, "audio_format 기본 지원 포맷",
          f3.supported_formats == ["MP3", "WAV", "AAC", "FLAC", "OGG"])
    check(r, "audio_format 메시지", "오디오" in str(f3))

    # 6개 초과 지원 포맷 표시 제한
    many = [f"FMT{i}" for i in range(8)]
    f4 = UnsupportedFormatException.video_format("/tmp/x.xyz", "XYZ", many)
    check(r, "video_format 6개 초과 표시 제한", "외 3개" in str(f4))


# =============================================================================
# [9] 포맷 검증 예외
# =============================================================================
def test_format_validation_exception(r: TestResult) -> None:
    """FormatValidationException 기본 + 팩토리 메서드 (7개) 테스트."""
    # 기본 생성
    e = FormatValidationException()
    check(r, "FormatValidationException 기본 생성", isinstance(e, ValidationException))
    check(r, "FormatValidationException ErrorCode",
          e.code == ErrorCode.FORMAT_VALIDATION_ERROR.code)

    # 전체 인수
    e2 = FormatValidationException(
        file_path="/tmp/v.mp4",
        format_type="video",
        validation_type="codec",
        actual_value="h265",
        expected_value="h264",
        reason="unsupported",
    )
    check(r, "FormatValidationException 속성 설정",
          e2.file_path == "/tmp/v.mp4" and e2.format_type == "video")

    # codec_not_supported
    f1 = FormatValidationException.codec_not_supported(
        "/tmp/v.mp4", "vp9", ["h264", "h265"],
    )
    check(r, "codec_not_supported ErrorCode", f1.code == ErrorCode.CODEC_NOT_SUPPORTED.code)
    check(r, "codec_not_supported 메시지", "vp9" in str(f1))
    check(r, "codec_not_supported validation_type", f1.validation_type == "codec")

    # format_not_allowed
    f2 = FormatValidationException.format_not_allowed(
        "/tmp/v.flv", "FLV", ["MP4", "MOV"],
    )
    check(r, "format_not_allowed ErrorCode", f2.code == ErrorCode.FORMAT_NOT_ALLOWED.code)
    check(r, "format_not_allowed 메시지", "FLV" in str(f2))

    # bitrate_out_of_range
    f3 = FormatValidationException.bitrate_out_of_range(
        "/tmp/v.mp4", 50_000_000, min_bitrate=1_000_000, max_bitrate=20_000_000,
    )
    check(r, "bitrate_out_of_range ErrorCode",
          f3.code == ErrorCode.BITRATE_OUT_OF_RANGE.code)
    check(r, "bitrate_out_of_range 메시지 kbps", "50000 kbps" in str(f3))
    d3 = f3.to_dict()
    check(r, "bitrate_out_of_range details bitrate",
          d3.get("details", {}).get("bitrate") == 50_000_000)

    # fps_too_low
    f4 = FormatValidationException.fps_too_low("/tmp/v.mp4", 10.0, 24.0)
    check(r, "fps_too_low ErrorCode", f4.code == ErrorCode.FPS_TOO_LOW.code)
    check(r, "fps_too_low 메시지", "10.00" in str(f4))
    check(r, "fps_too_low validation_type", f4.validation_type == "fps")

    # fps_too_high
    f5 = FormatValidationException.fps_too_high("/tmp/v.mp4", 240.0, 120.0)
    check(r, "fps_too_high ErrorCode", f5.code == ErrorCode.FPS_TOO_HIGH.code)
    check(r, "fps_too_high 메시지", "240.00" in str(f5))

    # duration_too_short
    f6 = FormatValidationException.duration_too_short("/tmp/v.mp4", 0.5, 3.0)
    check(r, "duration_too_short ErrorCode", f6.code == ErrorCode.DURATION_TOO_SHORT.code)
    check(r, "duration_too_short 메시지", "0.50" in str(f6))
    check(r, "duration_too_short validation_type", f6.validation_type == "duration")

    # duration_too_long
    f7 = FormatValidationException.duration_too_long("/tmp/v.mp4", 7200.0, 3600.0)
    check(r, "duration_too_long ErrorCode", f7.code == ErrorCode.DURATION_TOO_LONG.code)
    check(r, "duration_too_long 메시지", "7200.00" in str(f7))


# =============================================================================
# [10] 해상도 예외
# =============================================================================
def test_resolution_exception(r: TestResult) -> None:
    """ResolutionException 기본 + 팩토리 메서드 (4개) 테스트."""
    # 기본 생성
    e = ResolutionException()
    check(r, "ResolutionException 기본 생성", isinstance(e, ValidationException))
    check(r, "ResolutionException ErrorCode",
          e.code == ErrorCode.RESOLUTION_ERROR.code)

    # 전체 인수
    e2 = ResolutionException(
        file_path="/tmp/v.mp4",
        width=320, height=240,
        min_width=640, min_height=480,
    )
    d = e2.to_dict()
    check(r, "ResolutionException resolution 필드",
          d.get("details", {}).get("resolution") == "320x240")

    # too_low 팩토리
    f1 = ResolutionException.too_low("/tmp/v.mp4", 320, 240, 640, 480)
    check(r, "too_low ErrorCode", f1.code == ErrorCode.RESOLUTION_TOO_LOW.code)
    check(r, "too_low 메시지", "320x240" in str(f1) and "640x480" in str(f1))
    check(r, "too_low 속성", f1.width == 320 and f1.height == 240)

    # too_high 팩토리
    f2 = ResolutionException.too_high("/tmp/v.mp4", 7680, 4320, 3840, 2160)
    check(r, "too_high ErrorCode", f2.code == ErrorCode.RESOLUTION_TOO_HIGH.code)
    check(r, "too_high 메시지", "7680x4320" in str(f2))

    # not_supported 팩토리
    f3 = ResolutionException.not_supported(
        "/tmp/v.mp4", 800, 600, ["1280x720", "1920x1080"],
    )
    check(r, "not_supported ErrorCode", f3.code == ErrorCode.RESOLUTION_NOT_SUPPORTED.code)
    check(r, "not_supported 지원 목록", "1280x720" in str(f3))

    # not_supported 지원 목록 없음
    f3b = ResolutionException.not_supported("/tmp/v.mp4", 800, 600)
    check(r, "not_supported 지원 목록 없음", "지원하지 않는 해상도" in str(f3b))

    # aspect_ratio_not_supported 팩토리
    f4 = ResolutionException.aspect_ratio_not_supported(
        "/tmp/v.mp4", 1920, 1080, ["16:9", "4:3"],
    )
    check(r, "aspect_ratio ErrorCode",
          f4.code == ErrorCode.ASPECT_RATIO_NOT_SUPPORTED.code)
    check(r, "aspect_ratio 메시지에 비율", "16:9" in str(f4))
    d4 = f4.to_dict()
    check(r, "aspect_ratio details에 비율",
          d4.get("details", {}).get("aspect_ratio") == "16:9")

    # aspect_ratio gcd 계산 검증 (4:3)
    f5 = ResolutionException.aspect_ratio_not_supported("/tmp/v.mp4", 800, 600)
    d5 = f5.to_dict()
    check(r, "aspect_ratio gcd 4:3", d5.get("details", {}).get("aspect_ratio") == "4:3")


# =============================================================================
# [11] 설정 예외
# =============================================================================
def test_configuration_exception(r: TestResult) -> None:
    """ConfigurationException 기본 테스트."""
    e = ConfigurationException()
    check(r, "ConfigurationException 기본 생성", isinstance(e, ValidationException))
    check(r, "ConfigurationException ErrorCode",
          e.code == ErrorCode.CONFIGURATION_ERROR.code)

    e2 = ConfigurationException(config_key="db.host", config_file="config.yaml")
    check(r, "ConfigurationException config_key", e2.config_key == "db.host")
    check(r, "ConfigurationException config_file", e2.config_file == "config.yaml")
    check(r, "ConfigurationException field_name=config_key", e2.field_name == "db.host")


def test_configuration_not_found_exception(r: TestResult) -> None:
    """ConfigurationNotFoundException 테스트."""
    e = ConfigurationNotFoundException("config.yaml")
    check(r, "ConfigNotFound 기본 생성", isinstance(e, ConfigurationException))
    check(r, "ConfigNotFound ErrorCode",
          e.code == ErrorCode.CONFIGURATION_NOT_FOUND.code)
    check(r, "ConfigNotFound 메시지", "찾을 수 없습니다" in str(e))

    # searched_paths 포함
    e2 = ConfigurationNotFoundException(
        "app.yaml",
        searched_paths=["/etc/app/", "/home/user/.config/"],
    )
    d = e2.to_dict()
    check(r, "ConfigNotFound searched_paths",
          d.get("details", {}).get("searched_paths") is not None)


def test_configuration_load_exception(r: TestResult) -> None:
    """ConfigurationLoadException 테스트."""
    e = ConfigurationLoadException("config.yaml")
    check(r, "ConfigLoad 기본 생성", isinstance(e, ConfigurationException))
    check(r, "ConfigLoad ErrorCode",
          e.code == ErrorCode.CONFIGURATION_LOAD_FAILED.code)
    check(r, "ConfigLoad 메시지", "로드" in str(e))

    e2 = ConfigurationLoadException("config.yaml", reason="파일 손상")
    check(r, "ConfigLoad reason 포함 메시지", "파일 손상" in str(e2))


def test_configuration_parse_exception(r: TestResult) -> None:
    """ConfigurationParseException 테스트."""
    e = ConfigurationParseException("config.yaml")
    check(r, "ConfigParse 기본 생성", isinstance(e, ConfigurationException))
    check(r, "ConfigParse 메시지", "파싱" in str(e))

    e2 = ConfigurationParseException("config.yaml", reason="잘못된 YAML", line_number=42)
    check(r, "ConfigParse reason 메시지", "잘못된 YAML" in str(e2))
    check(r, "ConfigParse line_number 메시지", "라인 42" in str(e2))
    d = e2.to_dict()
    check(r, "ConfigParse details line_number",
          d.get("details", {}).get("line_number") == 42)


def test_configuration_validation_exception(r: TestResult) -> None:
    """ConfigurationValidationException 테스트."""
    e = ConfigurationValidationException("db.port", "abc", "숫자여야 합니다")
    check(r, "ConfigValidation 기본 생성", isinstance(e, ConfigurationException))
    check(r, "ConfigValidation ErrorCode",
          e.code == ErrorCode.CONFIGURATION_INVALID.code)
    check(r, "ConfigValidation 메시지", "db.port" in str(e))
    check(r, "ConfigValidation config_key", e.config_key == "db.port")
    d = e.to_dict()
    check(r, "ConfigValidation details config_value",
          d.get("details", {}).get("config_value") == "abc")
    check(r, "ConfigValidation details reason",
          d.get("details", {}).get("reason") == "숫자여야 합니다")


# =============================================================================
# [12] 스키마 검증 예외
# =============================================================================
def test_schema_validation_exception(r: TestResult) -> None:
    """SchemaValidationException 기본 + from_pydantic_errors 테스트."""
    errors = [
        {"field": "name", "type": "missing", "message": "필수"},
        {"field": "age", "type": "type_error", "message": "정수여야 함"},
    ]
    e = SchemaValidationException(errors, schema_name="UserModel")
    check(r, "SchemaValidation 기본 생성", isinstance(e, ValidationException))
    check(r, "SchemaValidation 에러 수 2", len(e.errors) == 2)
    check(r, "SchemaValidation schema_name", e.schema_name == "UserModel")
    check(r, "SchemaValidation 메시지에 수", "2개" in str(e))
    d = e.to_dict()
    check(r, "SchemaValidation details error_count",
          d.get("details", {}).get("error_count") == 2)

    # 10개 초과 시 자르기
    many_errors = [{"field": f"f{i}", "type": "err"} for i in range(15)]
    e2 = SchemaValidationException(many_errors)
    d2 = e2.to_dict()
    check(r, "SchemaValidation 10개 제한",
          len(d2.get("details", {}).get("errors", [])) == 10)
    check(r, "SchemaValidation 전체 에러 보존", len(e2.errors) == 15)

    # from_pydantic_errors 팩토리
    pydantic_errors = [
        {"loc": ("name",), "type": "missing", "msg": "필수 필드입니다"},
        {"loc": ("address", "city"), "type": "string_type", "msg": "문자열이어야 합니다"},
    ]
    f1 = SchemaValidationException.from_pydantic_errors(pydantic_errors, "AddressModel")
    check(r, "from_pydantic_errors schema_name", f1.schema_name == "AddressModel")
    check(r, "from_pydantic_errors 에러 수", len(f1.errors) == 2)
    check(r, "from_pydantic_errors 필드 경로 결합",
          f1.errors[1].get("field") == "address.city")
    check(r, "from_pydantic_errors type 유지",
          f1.errors[0].get("type") == "missing")
    check(r, "from_pydantic_errors message 유지",
          f1.errors[0].get("message") == "필수 필드입니다")


# =============================================================================
# [13] 인증/권한 예외
# =============================================================================
def test_authentication_exception(r: TestResult) -> None:
    """AuthenticationException 기본 + 팩토리 메서드 (3개) 테스트."""
    # 기본 생성 - NonRetryableException 직접 상속
    e = AuthenticationException()
    check(r, "AuthenticationException 기본 생성", isinstance(e, NonRetryableException))
    check(r, "AuthenticationException ErrorCode",
          e.code == ErrorCode.AUTHENTICATION_FAILED.code)
    check(r, "AuthenticationException 속성 None",
          e.auth_method is None and e.reason is None)

    # 전체 인수
    e2 = AuthenticationException(
        auth_method="oauth",
        reason="token_revoked",
    )
    check(r, "AuthenticationException 속성 설정", e2.auth_method == "oauth")

    # token_expired 팩토리
    f1 = AuthenticationException.token_expired("access_token", "2026-02-16T12:00:00Z")
    check(r, "token_expired ErrorCode", f1.code == ErrorCode.TOKEN_EXPIRED.code)
    check(r, "token_expired auth_method", f1.auth_method == "token")
    check(r, "token_expired reason", f1.reason == "token_expired")
    check(r, "token_expired 메시지", "만료" in str(f1))
    d1 = f1.to_dict()
    check(r, "token_expired details expired_at",
          d1.get("details", {}).get("expired_at") == "2026-02-16T12:00:00Z")

    # token_expired 기본값
    f1b = AuthenticationException.token_expired()
    check(r, "token_expired 기본 token_type", "access_token" in str(f1b))

    # invalid_credentials 팩토리
    f2 = AuthenticationException.invalid_credentials()
    check(r, "invalid_credentials ErrorCode",
          f2.code == ErrorCode.AUTHENTICATION_FAILED.code)
    check(r, "invalid_credentials 메시지", "아이디" in str(f2) or "비밀번호" in str(f2))
    check(r, "invalid_credentials reason", f2.reason == "invalid_credentials")

    # api_key_invalid 팩토리
    f3 = AuthenticationException.api_key_invalid("sk-1234567890abcdef")
    check(r, "api_key_invalid ErrorCode", f3.code == ErrorCode.API_KEY_INVALID.code)
    check(r, "api_key_invalid auth_method", f3.auth_method == "api_key")
    d3 = f3.to_dict()
    key_prefix = d3.get("details", {}).get("key_prefix", "")
    check(r, "api_key_invalid 키 마스킹 (8자+...)", key_prefix.endswith("..."))
    check(r, "api_key_invalid 키 접두사 길이", len(key_prefix) == 11)  # 8 + "..."

    # api_key_invalid prefix 없음
    f3b = AuthenticationException.api_key_invalid()
    check(r, "api_key_invalid prefix 없음", f3b.auth_method == "api_key")


def test_authorization_exception(r: TestResult) -> None:
    """AuthorizationException 기본 + 팩토리 메서드 테스트."""
    # 기본 생성
    e = AuthorizationException()
    check(r, "AuthorizationException 기본 생성", isinstance(e, NonRetryableException))
    check(r, "AuthorizationException ErrorCode",
          e.code == ErrorCode.PERMISSION_DENIED.code)
    check(r, "AuthorizationException 기본 메시지", "권한" in str(e))

    # 전체 인수
    e2 = AuthorizationException(
        resource="user:123",
        action="delete",
        required_permissions=["admin", "user_manager"],
    )
    check(r, "AuthorizationException resource", e2.resource == "user:123")
    check(r, "AuthorizationException action", e2.action == "delete")
    check(r, "AuthorizationException required_permissions",
          e2.required_permissions == ["admin", "user_manager"])

    # resource_access_denied 팩토리
    f1 = AuthorizationException.resource_access_denied("analysis", "abc-123", "read")
    check(r, "resource_access_denied 메시지", "analysis" in str(f1) and "abc-123" in str(f1))
    check(r, "resource_access_denied resource", f1.resource == "analysis:abc-123")
    check(r, "resource_access_denied action", f1.action == "read")


# =============================================================================
# [14] 속도 제한 예외
# =============================================================================
def test_rate_limit_exception(r: TestResult) -> None:
    """RateLimitException 기본 + to_response_headers 테스트."""
    # 기본 생성 - RetryableException 상속!
    e = RateLimitException()
    check(r, "RateLimitException 기본 생성", isinstance(e, RetryableException))
    check(r, "RateLimitException NOT NonRetryableException",
          not isinstance(e, NonRetryableException))
    check(r, "RateLimitException ErrorCode",
          e.code == ErrorCode.RATE_LIMIT_EXCEEDED.code)
    check(r, "RateLimitException max_retries=1", e.max_retries == 1)
    check(r, "RateLimitException retry_after=60", e.retry_after == 60.0)

    # 전체 인수
    e2 = RateLimitException(
        limit=100,
        window_seconds=60,
        current_count=105,
        reset_at="2026-02-16T12:01:00Z",
        retry_after=30.0,
    )
    check(r, "RateLimitException limit", e2.limit == 100)
    check(r, "RateLimitException window_seconds", e2.window_seconds == 60)
    check(r, "RateLimitException current_count", e2.current_count == 105)
    check(r, "RateLimitException reset_at", e2.reset_at == "2026-02-16T12:01:00Z")

    # to_response_headers
    headers = e2.to_response_headers()
    check(r, "to_response_headers Retry-After", headers.get("Retry-After") == "30")
    check(r, "to_response_headers X-RateLimit-Limit",
          headers.get("X-RateLimit-Limit") == "100")
    check(r, "to_response_headers X-RateLimit-Remaining",
          headers.get("X-RateLimit-Remaining") == "0")  # max(0, 100-105) = 0
    check(r, "to_response_headers X-RateLimit-Reset",
          headers.get("X-RateLimit-Reset") == "2026-02-16T12:01:00Z")

    # to_response_headers - remaining > 0
    e3 = RateLimitException(limit=100, current_count=80)
    h3 = e3.to_response_headers()
    check(r, "to_response_headers remaining 20",
          h3.get("X-RateLimit-Remaining") == "20")

    # to_response_headers - 최소 필드만
    e4 = RateLimitException()
    h4 = e4.to_response_headers()
    check(r, "to_response_headers 최소 Retry-After만",
          "Retry-After" in h4)
    check(r, "to_response_headers limit 없으면 X-RateLimit-Limit 없음",
          "X-RateLimit-Limit" not in h4)

    # to_dict에 retry 필드 (retry: {retry_after, max_retries})
    d = e2.to_dict()
    retry = d.get("retry", {})
    check(r, "RateLimitException to_dict retry.retry_after",
          retry.get("retry_after") == 30.0)
    check(r, "RateLimitException to_dict retry.max_retries",
          retry.get("max_retries") == 1)


# =============================================================================
# [15] 데이터 품질 예외
# =============================================================================
def test_data_quality_exception(r: TestResult) -> None:
    """DataQualityException 기본 + 팩토리 메서드 (4개) 테스트."""
    # 기본 생성
    e = DataQualityException()
    check(r, "DataQualityException 기본 생성", isinstance(e, ValidationException))
    check(r, "DataQualityException ErrorCode",
          e.code == ErrorCode.DATA_QUALITY_ERROR.code)
    check(r, "DataQualityException 기본 속성",
          e.quality_level is None and e.overall_score is None)

    # 전체 인수
    e2 = DataQualityException(
        quality_level="poor",
        overall_score=35.0,
        dimension_scores={"brightness": 20.0, "contrast": 50.0},
        failed_dimensions=["brightness"],
    )
    check(r, "DataQualityException quality_level", e2.quality_level == "poor")
    check(r, "DataQualityException overall_score", e2.overall_score == 35.0)
    check(r, "DataQualityException dimension_scores", e2.dimension_scores == {"brightness": 20.0, "contrast": 50.0})
    check(r, "DataQualityException failed_dimensions", e2.failed_dimensions == ["brightness"])

    # brightness_error 팩토리 - 너무 낮음
    f1 = DataQualityException.brightness_error(10.0, 30.0, 200.0)
    check(r, "brightness_error 낮음 메시지", "낮습니다" in str(f1))
    check(r, "brightness_error failed_dimensions", f1.failed_dimensions == ["brightness"])
    check(r, "brightness_error dimension_scores",
          f1.dimension_scores.get("brightness") == 10.0)

    # brightness_error - 너무 높음
    f1b = DataQualityException.brightness_error(250.0, 30.0, 200.0)
    check(r, "brightness_error 높음 메시지", "높습니다" in str(f1b))

    # contrast_error 팩토리
    f2 = DataQualityException.contrast_error(15.0, 30.0)
    check(r, "contrast_error 메시지", "대비" in str(f2))
    check(r, "contrast_error failed_dimensions", f2.failed_dimensions == ["contrast"])

    # noise_error 팩토리
    f3 = DataQualityException.noise_error(80.0, 50.0)
    check(r, "noise_error 메시지", "노이즈" in str(f3))
    check(r, "noise_error failed_dimensions", f3.failed_dimensions == ["noise"])

    # blur_error 팩토리
    f4 = DataQualityException.blur_error(10.0, 30.0)
    check(r, "blur_error 메시지", "흐릿" in str(f4))
    check(r, "blur_error failed_dimensions", f4.failed_dimensions == ["blur"])


def test_low_quality_exception(r: TestResult) -> None:
    """LowQualityException 기본 + from_quality_result 테스트."""
    # 기본 생성
    e = LowQualityException()
    check(r, "LowQualityException 기본 생성", isinstance(e, DataQualityException))
    check(r, "LowQualityException minimum_score 기본값", e.minimum_score == 60.0)
    check(r, "LowQualityException recommendations 빈 목록", e.recommendations == [])

    # 전체 인수
    e2 = LowQualityException(
        overall_score=40.0,
        minimum_score=70.0,
        quality_level="poor",
        dimension_scores={"brightness": 30.0},
        failed_dimensions=["brightness"],
        recommendations=["조명 개선"],
    )
    check(r, "LowQualityException overall_score", e2.overall_score == 40.0)
    check(r, "LowQualityException minimum_score", e2.minimum_score == 70.0)
    check(r, "LowQualityException recommendations", e2.recommendations == ["조명 개선"])
    check(r, "LowQualityException details minimum_score",
          e2.minimum_score == 70.0)

    # from_quality_result 팩토리
    f1 = LowQualityException.from_quality_result(
        overall_score=45.0,
        minimum_score=60.0,
        dimension_scores={"brightness": 20.0, "blur": 15.0, "noise": 80.0},
        failed_dimensions=["brightness", "blur", "noise"],
        quality_level="unacceptable",
    )
    check(r, "from_quality_result overall_score", f1.overall_score == 45.0)
    check(r, "from_quality_result minimum_score", f1.minimum_score == 60.0)
    check(r, "from_quality_result quality_level", f1.quality_level == "unacceptable")
    check(r, "from_quality_result recommendations 자동 생성",
          len(f1.recommendations) == 3)
    check(r, "from_quality_result brightness 권장", "조명" in f1.recommendations[0])
    check(r, "from_quality_result blur 권장", "고정" in f1.recommendations[1])
    check(r, "from_quality_result noise 권장", "밝은" in f1.recommendations[2])
    check(r, "from_quality_result 메시지에 점수", "45.0" in str(f1) and "60.0" in str(f1))

    # from_quality_result - resolution + fps 권장
    f2 = LowQualityException.from_quality_result(
        overall_score=50.0,
        minimum_score=60.0,
        dimension_scores={"resolution": 40.0, "fps": 30.0},
        failed_dimensions=["resolution", "fps"],
        quality_level="poor",
    )
    check(r, "from_quality_result resolution 권장", "해상도" in f2.recommendations[0])
    check(r, "from_quality_result fps 권장", "프레임레이트" in f2.recommendations[1])

    # from_quality_result - contrast 권장
    f3 = LowQualityException.from_quality_result(
        overall_score=55.0,
        minimum_score=60.0,
        dimension_scores={"contrast": 25.0},
        failed_dimensions=["contrast"],
        quality_level="poor",
    )
    check(r, "from_quality_result contrast 권장", "선명한" in f3.recommendations[0])


# =============================================================================
# [16] 규칙 세트 예외
# =============================================================================
def test_rule_set_not_found_exception(r: TestResult) -> None:
    """RuleSetNotFoundException 기본 + for_league 테스트."""
    e = RuleSetNotFoundException("NBA")
    check(r, "RuleSetNotFound 기본 생성", isinstance(e, ValidationException))
    check(r, "RuleSetNotFound ErrorCode",
          e.code == ErrorCode.RULE_SET_NOT_FOUND.code)
    check(r, "RuleSetNotFound league", e.league == "NBA")
    check(r, "RuleSetNotFound 메시지", "NBA" in str(e))
    check(r, "RuleSetNotFound field_name=league", e.field_name == "league")
    check(r, "RuleSetNotFound field_value=NBA", e.field_value == "NBA")

    # 버전 포함
    e2 = RuleSetNotFoundException("FIBA", version="v3.0.0")
    check(r, "RuleSetNotFound version 메시지", "v3.0.0" in str(e2))
    check(r, "RuleSetNotFound version 속성", e2.version == "v3.0.0")

    # searched_paths 포함
    e3 = RuleSetNotFoundException("KBL", searched_paths=["/rules/kbl/"])
    check(r, "RuleSetNotFound searched_paths", e3.searched_paths == ["/rules/kbl/"])

    # for_league 팩토리
    f1 = RuleSetNotFoundException.for_league(
        "WNBA", available_leagues=["NBA", "FIBA", "KBL"],
    )
    check(r, "for_league league", f1.league == "WNBA")
    d = f1.to_dict()
    check(r, "for_league available_leagues",
          d.get("details", {}).get("available_leagues") == ["NBA", "FIBA", "KBL"])


def test_rule_set_validation_exception(r: TestResult) -> None:
    """RuleSetValidationException 기본 + 팩토리 메서드 (3개) 테스트."""
    e = RuleSetValidationException("NBA")
    check(r, "RuleSetValidation 기본 생성", isinstance(e, ValidationException))
    check(r, "RuleSetValidation ErrorCode",
          e.code == ErrorCode.RULE_SET_VALIDATION_ERROR.code)
    check(r, "RuleSetValidation league", e.league == "NBA")

    # validation_errors 포함
    errors = [{"field": "shot_clock", "error": "누락"}]
    e2 = RuleSetValidationException("FIBA", validation_errors=errors, rule_id="R001")
    check(r, "RuleSetValidation rule_id 메시지", "R001" in str(e2))
    check(r, "RuleSetValidation validation_errors", len(e2.validation_errors) == 1)

    # reason 포함
    e3 = RuleSetValidationException("KBL", reason="스키마 불일치")
    check(r, "RuleSetValidation reason 메시지", "스키마 불일치" in str(e3))

    # 10개 초과 에러 자르기
    many_errors = [{"field": f"f{i}"} for i in range(15)]
    e4 = RuleSetValidationException("NBA", validation_errors=many_errors)
    d4 = e4.to_dict()
    check(r, "RuleSetValidation 10개 제한",
          len(d4.get("details", {}).get("validation_errors", [])) == 10)
    check(r, "RuleSetValidation error_count",
          d4.get("details", {}).get("error_count") == 15)

    # schema_error 팩토리
    f1 = RuleSetValidationException.schema_error(
        "NBA", [{"path": "/shot_clock", "error": "type mismatch"}],
    )
    check(r, "schema_error league", f1.league == "NBA")
    check(r, "schema_error reason", f1.reason == "스키마 검증 실패")

    # invalid_rule 팩토리
    f2 = RuleSetValidationException.invalid_rule("FIBA", "R042", "시간 값 음수")
    check(r, "invalid_rule rule_id", f2.rule_id == "R042")
    check(r, "invalid_rule reason", f2.reason == "시간 값 음수")

    # missing_required_field 팩토리
    f3 = RuleSetValidationException.missing_required_field("KBL", "shot_clock_duration", "R001")
    check(r, "missing_required_field rule_id", f3.rule_id == "R001")
    check(r, "missing_required_field reason", "shot_clock_duration" in f3.reason)
    d3 = f3.to_dict()
    check(r, "missing_required_field missing_field",
          d3.get("details", {}).get("missing_field") == "shot_clock_duration")


def test_rule_set_version_mismatch_exception(r: TestResult) -> None:
    """RuleSetVersionMismatchException 기본 + incompatible + is_upgrade_available 테스트."""
    e = RuleSetVersionMismatchException("NBA", "v2.0.0", "v1.5.0")
    check(r, "VersionMismatch 기본 생성", isinstance(e, ValidationException))
    check(r, "VersionMismatch ErrorCode",
          e.code == ErrorCode.RULE_SET_VERSION_MISMATCH.code)
    check(r, "VersionMismatch league", e.league == "NBA")
    check(r, "VersionMismatch expected_version", e.expected_version == "v2.0.0")
    check(r, "VersionMismatch actual_version", e.actual_version == "v1.5.0")
    check(r, "VersionMismatch 메시지", "v2.0.0" in str(e) and "v1.5.0" in str(e))

    # is_upgrade_available - actual > expected → True
    e2 = RuleSetVersionMismatchException("NBA", "v1.0.0", "v2.0.0")
    check(r, "is_upgrade_available True (2.0 > 1.0)", e2.is_upgrade_available() is True)

    # is_upgrade_available - actual < expected → False
    check(r, "is_upgrade_available False (1.5 < 2.0)", e.is_upgrade_available() is False)

    # is_upgrade_available - equal → False
    e3 = RuleSetVersionMismatchException("NBA", "v1.0.0", "v1.0.0")
    check(r, "is_upgrade_available False (같음)", e3.is_upgrade_available() is False)

    # is_upgrade_available - 잘못된 버전 → False
    e4 = RuleSetVersionMismatchException("NBA", "abc", "def")
    check(r, "is_upgrade_available False (잘못된 버전)", e4.is_upgrade_available() is False)

    # is_upgrade_available - minor 비교
    e5 = RuleSetVersionMismatchException("NBA", "v1.0.0", "v1.1.0")
    check(r, "is_upgrade_available True (minor 비교)", e5.is_upgrade_available() is True)

    # is_upgrade_available - patch 비교
    e6 = RuleSetVersionMismatchException("NBA", "v1.0.1", "v1.0.2")
    check(r, "is_upgrade_available True (patch 비교)", e6.is_upgrade_available() is True)

    # is_upgrade_available - v 접두사 없이
    e7 = RuleSetVersionMismatchException("NBA", "1.0.0", "2.0.0")
    check(r, "is_upgrade_available v 접두사 없이", e7.is_upgrade_available() is True)

    # incompatible 팩토리
    f1 = RuleSetVersionMismatchException.incompatible(
        "FIBA", "v3.0.0", "v2.0.0", "메이저 버전 불일치",
    )
    check(r, "incompatible league", f1.league == "FIBA")
    check(r, "incompatible expected", f1.expected_version == "v3.0.0")
    check(r, "incompatible actual", f1.actual_version == "v2.0.0")
    d = f1.to_dict()
    check(r, "incompatible reason", d.get("details", {}).get("reason") == "메이저 버전 불일치")


# =============================================================================
# [17] 상속 계층 검증
# =============================================================================
def test_inheritance_hierarchy(r: TestResult) -> None:
    """31개 클래스의 상속 계층 검증."""
    # ValidationException → NonRetryableException
    check(r, "ValidationException → NonRetryableException",
          issubclass(ValidationException, NonRetryableException))
    check(r, "ValidationException → CourtViewException",
          issubclass(ValidationException, CourtViewException))

    # ValidationException 하위 (28개 from ValidationException)
    val_subclasses = [
        InvalidRequestException, InputValidationException,
        MissingFieldException, InvalidFieldTypeException, InvalidFieldValueException,
        ValueOutOfRangeException, StringLengthException,
        InvalidEnumValueException, InvalidJsonFormatException, InvalidDateFormatException,
        URLValidationException,
        FormatDetectionException, UnsupportedFormatException, FormatValidationException,
        ResolutionException,
        ConfigurationException,
        SchemaValidationException,
        DataQualityException,
        RuleSetNotFoundException, RuleSetValidationException, RuleSetVersionMismatchException,
    ]
    for cls in val_subclasses:
        check(r, f"{cls.__name__} → ValidationException",
              issubclass(cls, ValidationException))

    # ConfigurationException 하위
    config_subclasses = [
        ConfigurationNotFoundException, ConfigurationLoadException,
        ConfigurationParseException, ConfigurationValidationException,
    ]
    for cls in config_subclasses:
        check(r, f"{cls.__name__} → ConfigurationException",
              issubclass(cls, ConfigurationException))

    # LowQualityException → DataQualityException
    check(r, "LowQualityException → DataQualityException",
          issubclass(LowQualityException, DataQualityException))

    # NonRetryableException 직접 상속 (ValidationException 아님)
    direct_non_retryable = [SecurityException, AuthenticationException, AuthorizationException]
    for cls in direct_non_retryable:
        check(r, f"{cls.__name__} → NonRetryableException (직접)",
              issubclass(cls, NonRetryableException))

    # SecurityException은 ValidationException이 아님
    check(r, "SecurityException NOT → ValidationException",
          not issubclass(SecurityException, ValidationException))
    check(r, "AuthenticationException NOT → ValidationException",
          not issubclass(AuthenticationException, ValidationException))
    check(r, "AuthorizationException NOT → ValidationException",
          not issubclass(AuthorizationException, ValidationException))

    # RateLimitException → RetryableException
    check(r, "RateLimitException → RetryableException",
          issubclass(RateLimitException, RetryableException))
    check(r, "RateLimitException NOT → NonRetryableException",
          not issubclass(RateLimitException, NonRetryableException))


# =============================================================================
# [18] 직렬화 검증
# =============================================================================
def test_serialization(r: TestResult) -> None:
    """직렬화 메서드 (to_dict, to_response_dict) 검증."""
    # ValidationException to_dict 기본 구조: {error:{code,name,message,http_status}, timestamp, details, retryable}
    e = ValidationException(
        field_name="email",
        field_value="bad@",
        details={"custom": "data"},
    )
    d = e.to_dict()
    check(r, "to_dict error 필드 존재", "error" in d)
    check(r, "to_dict error.code 존재", "code" in d.get("error", {}))
    check(r, "to_dict details 필드 존재", "details" in d)
    check(r, "to_dict details custom 유지", d["details"].get("custom") == "data")
    check(r, "to_dict details field_name 유지", d["details"].get("field_name") == "email")

    # to_response_dict: {success, error:{code,name,message}, details}
    rd = e.to_response_dict()
    check(r, "to_response_dict success False", rd.get("success") is False)
    check(r, "to_response_dict error 존재", "error" in rd)

    # RateLimitException to_dict에 retry 필드 (retry: {retry_after, max_retries})
    rl = RateLimitException(retry_after=30.0)
    rld = rl.to_dict()
    retry = rld.get("retry", {})
    check(r, "RateLimitException to_dict retry.retry_after", retry.get("retry_after") == 30.0)
    check(r, "RateLimitException to_dict retry.max_retries", retry.get("max_retries") == 1)

    # SecurityException to_dict
    se = SecurityException.ssrf_detected("http://evil.com", "10.0.0.1")
    sd = se.to_dict()
    check(r, "SecurityException to_dict threat_type",
          sd.get("details", {}).get("threat_type") == "ssrf")

    # LowQualityException to_dict - details 구조 확인
    ce = LowQualityException.from_quality_result(
        45.0, 60.0, {"brightness": 20.0}, ["brightness"], "poor",
    )
    cd = ce.to_dict()
    check(r, "LowQualityException to_dict details 존재", "details" in cd)
    # 속성으로 직접 검증
    check(r, "LowQualityException 속성 recommendations",
          len(ce.recommendations) > 0)
    check(r, "LowQualityException 속성 minimum_score",
          ce.minimum_score == 60.0)


# =============================================================================
# [19] raise/catch 검증
# =============================================================================
def test_raise_catch(r: TestResult) -> None:
    """raise/catch 동작 검증."""
    # ValidationException으로 catch
    try:
        raise MissingFieldException("name")
    except ValidationException as ex:
        check(r, "MissingFieldException caught by ValidationException", True)
        check(r, "catch 후 field_name 접근", ex.field_name == "name")

    # NonRetryableException으로 catch
    try:
        raise SecurityException.ssrf_detected("http://evil.com")
    except NonRetryableException as ex:
        check(r, "SecurityException caught by NonRetryableException", True)

    # RetryableException으로 catch
    try:
        raise RateLimitException(limit=100, current_count=110)
    except RetryableException as ex:
        check(r, "RateLimitException caught by RetryableException", True)
        check(r, "catch 후 limit 접근", ex.limit == 100)

    # CourtViewException으로 전부 catch
    try:
        raise AuthorizationException.resource_access_denied("video", "v001", "delete")
    except CourtViewException as ex:
        check(r, "AuthorizationException caught by CourtViewException", True)

    # ConfigurationException 계층 catch
    try:
        raise ConfigurationNotFoundException("app.yaml")
    except ConfigurationException as ex:
        check(r, "ConfigNotFound caught by ConfigurationException", True)

    # DataQualityException 계층 catch
    try:
        raise LowQualityException.from_quality_result(
            40.0, 60.0, {"blur": 10.0}, ["blur"], "poor"
        )
    except DataQualityException as ex:
        check(r, "LowQuality caught by DataQualityException", True)
        check(r, "catch 후 recommendations 접근", len(ex.recommendations) > 0)


# =============================================================================
# [20] __all__ export 검증
# =============================================================================
def test_all_exports(r: TestResult) -> None:
    """__all__ 31개 export 검증."""
    from shared.exceptions import validation_exceptions

    all_exports = validation_exceptions.__all__
    check(r, "__all__ 31개 export", len(all_exports) == 31)

    expected = [
        "ValidationException", "InvalidRequestException", "InputValidationException",
        "MissingFieldException", "InvalidFieldTypeException", "InvalidFieldValueException",
        "ValueOutOfRangeException", "StringLengthException",
        "InvalidEnumValueException", "InvalidJsonFormatException", "InvalidDateFormatException",
        "URLValidationException", "SecurityException",
        "FormatDetectionException", "UnsupportedFormatException", "FormatValidationException",
        "ResolutionException",
        "ConfigurationException", "ConfigurationNotFoundException",
        "ConfigurationLoadException", "ConfigurationParseException",
        "ConfigurationValidationException",
        "SchemaValidationException",
        "AuthenticationException", "AuthorizationException",
        "RateLimitException",
        "DataQualityException", "LowQualityException",
        "RuleSetNotFoundException", "RuleSetValidationException",
        "RuleSetVersionMismatchException",
    ]
    for name in expected:
        check(r, f"__all__에 {name} 포함", name in all_exports)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = TestResult()
    print("\n" + "=" * 60)
    print("  validation_exceptions.py v1.0.0 단위 테스트")
    print("=" * 60)

    print("\n--- [1] 기본 유효성 검사 ---")
    test_validation_exception(r)
    test_invalid_request_exception(r)
    test_input_validation_exception(r)

    print("\n--- [2] 필드 유효성 검사 ---")
    test_missing_field_exception(r)
    test_invalid_field_type_exception(r)
    test_invalid_field_value_exception(r)

    print("\n--- [3] 값 범위/길이 ---")
    test_value_out_of_range_exception(r)
    test_string_length_exception(r)

    print("\n--- [4] 데이터 형식 ---")
    test_invalid_enum_value_exception(r)
    test_invalid_json_format_exception(r)
    test_invalid_date_format_exception(r)

    print("\n--- [5] URL 검증 ---")
    test_url_validation_exception(r)

    print("\n--- [6] 보안 ---")
    test_security_exception(r)

    print("\n--- [7] 파일 포맷 감지 ---")
    test_format_detection_exception(r)

    print("\n--- [8] 지원하지 않는 포맷 ---")
    test_unsupported_format_exception(r)

    print("\n--- [9] 포맷 검증 ---")
    test_format_validation_exception(r)

    print("\n--- [10] 해상도 ---")
    test_resolution_exception(r)

    print("\n--- [11] 설정 ---")
    test_configuration_exception(r)
    test_configuration_not_found_exception(r)
    test_configuration_load_exception(r)
    test_configuration_parse_exception(r)
    test_configuration_validation_exception(r)

    print("\n--- [12] 스키마 ---")
    test_schema_validation_exception(r)

    print("\n--- [13] 인증/권한 ---")
    test_authentication_exception(r)
    test_authorization_exception(r)

    print("\n--- [14] 속도 제한 ---")
    test_rate_limit_exception(r)

    print("\n--- [15] 데이터 품질 ---")
    test_data_quality_exception(r)
    test_low_quality_exception(r)

    print("\n--- [16] 규칙 세트 ---")
    test_rule_set_not_found_exception(r)
    test_rule_set_validation_exception(r)
    test_rule_set_version_mismatch_exception(r)

    print("\n--- [17] 상속 계층 ---")
    test_inheritance_hierarchy(r)

    print("\n--- [18] 직렬화 ---")
    test_serialization(r)

    print("\n--- [19] raise/catch ---")
    test_raise_catch(r)

    print("\n--- [20] __all__ export ---")
    test_all_exports(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
