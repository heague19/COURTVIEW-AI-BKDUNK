# -*- coding: utf-8 -*-
"""
tests/shared/constants/test_error_codes.py

에러 코드 상수 모듈 유닛 테스트
- ErrorCategory: 생성, 속성, contains, from_code, to_dict, __str__, __repr__
- ErrorCode: 생성, 속성, category, to_dict, from_code, get_by_category
- ErrorCode: is_retryable, is_client_error, is_server_error, __str__, __repr__
- ERROR_CODE_LOOKUP: O(1) 캐시 조회
- RETRYABLE_ERRORS: frozenset 멤버십
- 카테고리 그룹: 타입, 완전성, 범위 일치
- 에지 케이스: 경계값, 잘못된 코드

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. ErrorCategory 기본 ====================
def test_error_category_basics(r: TestResult) -> None:
    print("\n[1] ErrorCategory 기본")
    from shared.constants.error_codes import ErrorCategory

    r.check("Enum 크기 = 9", len(ErrorCategory) == 9)
    r.check("GENERAL 존재", hasattr(ErrorCategory, "GENERAL"))
    r.check("SYSTEM 존재", hasattr(ErrorCategory, "SYSTEM"))

    cat = ErrorCategory.GENERAL
    r.check("start 속성", cat.start == 1000)
    r.check("end 속성", cat.end == 1999)
    r.check("description 속성", cat.description == "일반 에러")


# ==================== 2. ErrorCategory.contains ====================
def test_error_category_contains(r: TestResult) -> None:
    print("\n[2] ErrorCategory.contains")
    from shared.constants.error_codes import ErrorCategory

    # 경계값 테스트
    r.check("contains(1000)=True", ErrorCategory.GENERAL.contains(1000))
    r.check("contains(1999)=True", ErrorCategory.GENERAL.contains(1999))
    r.check("contains(999)=False", not ErrorCategory.GENERAL.contains(999))
    r.check("contains(2000)=False", not ErrorCategory.GENERAL.contains(2000))
    r.check("contains(1500)=True", ErrorCategory.GENERAL.contains(1500))

    # 다른 카테고리
    r.check("INFRASTRUCTURE.contains(5500)", ErrorCategory.INFRASTRUCTURE.contains(5500))
    r.check("REFEREE.contains(8005)", ErrorCategory.REFEREE.contains(8005))


# ==================== 3. ErrorCategory.from_code ====================
def test_error_category_from_code(r: TestResult) -> None:
    print("\n[3] ErrorCategory.from_code")
    from shared.constants.error_codes import ErrorCategory

    r.check("from_code(1000)=GENERAL", ErrorCategory.from_code(1000) == ErrorCategory.GENERAL)
    r.check("from_code(2500)=AUTH", ErrorCategory.from_code(2500) == ErrorCategory.AUTHENTICATION)
    r.check("from_code(3000)=VALIDATION", ErrorCategory.from_code(3000) == ErrorCategory.VALIDATION)
    r.check("from_code(4999)=BUSINESS", ErrorCategory.from_code(4999) == ErrorCategory.BUSINESS)
    r.check("from_code(5000)=INFRA", ErrorCategory.from_code(5000) == ErrorCategory.INFRASTRUCTURE)
    r.check("from_code(6500)=EXTERNAL", ErrorCategory.from_code(6500) == ErrorCategory.EXTERNAL)
    r.check("from_code(7777)=ANALYSIS", ErrorCategory.from_code(7777) == ErrorCategory.ANALYSIS)
    r.check("from_code(8000)=REFEREE", ErrorCategory.from_code(8000) == ErrorCategory.REFEREE)
    r.check("from_code(9999)=SYSTEM", ErrorCategory.from_code(9999) == ErrorCategory.SYSTEM)

    # 잘못된 코드
    try:
        ErrorCategory.from_code(0)
        r.fail("from_code(0) ValueError")
    except ValueError:
        r.ok("from_code(0) ValueError")

    try:
        ErrorCategory.from_code(10000)
        r.fail("from_code(10000) ValueError")
    except ValueError:
        r.ok("from_code(10000) ValueError")


# ==================== 4. ErrorCategory.to_dict / __str__ / __repr__ ====================
def test_error_category_serialization(r: TestResult) -> None:
    print("\n[4] ErrorCategory 직렬화")
    from shared.constants.error_codes import ErrorCategory

    d = ErrorCategory.ANALYSIS.to_dict()
    r.check("to_dict.category", d["category"] == "ANALYSIS")
    r.check("to_dict.start", d["start"] == 7000)
    r.check("to_dict.end", d["end"] == 7999)
    r.check("to_dict.description", d["description"] == "분석 엔진 에러")

    s = str(ErrorCategory.ANALYSIS)
    r.check("__str__ 포함 ANALYSIS", "ANALYSIS" in s)
    r.check("__str__ 포함 7000", "7000" in s)

    rp = repr(ErrorCategory.ANALYSIS)
    r.check("__repr__ 포함 ErrorCategory", "ErrorCategory" in rp)


# ==================== 5. ErrorCode 기본 속성 ====================
def test_error_code_basics(r: TestResult) -> None:
    print("\n[5] ErrorCode 기본 속성")
    from shared.constants.error_codes import ErrorCode

    r.check("전체 270개", len(list(ErrorCode)) == 270)

    e = ErrorCode.UNKNOWN_ERROR
    r.check("code=1000", e.code == 1000)
    r.check("message 문자열", isinstance(e.message, str) and len(e.message) > 0)
    r.check("http_status=500", e.http_status == 500)


# ==================== 6. ErrorCode.category 속성 ====================
def test_error_code_category(r: TestResult) -> None:
    print("\n[6] ErrorCode.category")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    tests = [
        ("UNKNOWN_ERROR", ErrorCategory.GENERAL),
        ("AUTHENTICATION_REQUIRED", ErrorCategory.AUTHENTICATION),
        ("VALIDATION_ERROR", ErrorCategory.VALIDATION),
        ("RESOURCE_NOT_FOUND", ErrorCategory.BUSINESS),
        ("DATABASE_ERROR", ErrorCategory.INFRASTRUCTURE),
        ("EXTERNAL_SERVICE_ERROR", ErrorCategory.EXTERNAL),
        ("ANALYSIS_ERROR", ErrorCategory.ANALYSIS),
        ("REFEREE_ERROR", ErrorCategory.REFEREE),
        ("CONFIGURATION_ERROR", ErrorCategory.SYSTEM),
    ]
    for name, expected_cat in tests:
        error = ErrorCode[name]
        r.check(f"{name}.category={expected_cat.name}", error.category == expected_cat)


# ==================== 7. ErrorCode.to_dict ====================
def test_error_code_to_dict(r: TestResult) -> None:
    print("\n[7] ErrorCode.to_dict")
    from shared.constants.error_codes import ErrorCode

    d = ErrorCode.PERMISSION_DENIED.to_dict()
    r.check("error_code key", d["error_code"] == "PERMISSION_DENIED")
    r.check("code key", d["code"] == 2004)
    r.check("message key", "권한" in d["message"])
    r.check("http_status key", d["http_status"] == 403)
    r.check("category key", d["category"] == "AUTHENTICATION")


# ==================== 8. ErrorCode.from_code (O(1)) ====================
def test_error_code_from_code(r: TestResult) -> None:
    print("\n[8] ErrorCode.from_code")
    from shared.constants.error_codes import ErrorCode

    # 정상 조회
    r.check("from_code(1000)", ErrorCode.from_code(1000) == ErrorCode.UNKNOWN_ERROR)
    r.check("from_code(3021)", ErrorCode.from_code(3021) == ErrorCode.SSRF_DETECTED)
    r.check("from_code(5401)", ErrorCode.from_code(5401) == ErrorCode.CIRCUIT_BREAKER_OPEN)
    r.check("from_code(7510)", ErrorCode.from_code(7510) == ErrorCode.SHOOTING_NOT_DETECTED)
    r.check("from_code(9202)", ErrorCode.from_code(9202) == ErrorCode.MISSING_DEPENDENCY)

    # 잘못된 코드
    try:
        ErrorCode.from_code(9999)
        r.fail("from_code(9999) ValueError")
    except ValueError:
        r.ok("from_code(9999) ValueError")

    try:
        ErrorCode.from_code(-1)
        r.fail("from_code(-1) ValueError")
    except ValueError:
        r.ok("from_code(-1) ValueError")


# ==================== 9. ErrorCode.get_by_category ====================
def test_get_by_category(r: TestResult) -> None:
    print("\n[9] ErrorCode.get_by_category")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    general = ErrorCode.get_by_category(ErrorCategory.GENERAL)
    r.check("GENERAL tuple", isinstance(general, tuple))
    r.check("GENERAL 6개", len(general) == 6)
    r.check("GENERAL 모두 1xxx", all(1000 <= e.code <= 1999 for e in general))

    referee = ErrorCode.get_by_category(ErrorCategory.REFEREE)
    r.check("REFEREE 10개", len(referee) == 10)
    r.check("REFEREE 모두 8xxx", all(8000 <= e.code <= 8999 for e in referee))


# ==================== 10. is_retryable ====================
def test_is_retryable(r: TestResult) -> None:
    print("\n[10] is_retryable")
    from shared.constants.error_codes import ErrorCode

    # 재시도 가능
    retryable = [
        "TIMEOUT_ERROR", "SERVICE_UNAVAILABLE", "DATABASE_TIMEOUT",
        "DATABASE_CONNECTION_FAILED", "CACHE_CONNECTION_FAILED",
        "STREAM_CONNECTION_FAILED", "CIRCUIT_BREAKER_OPEN",
        "ANALYSIS_TIMEOUT",
    ]
    for name in retryable:
        r.check(f"{name}.is_retryable()=True", ErrorCode[name].is_retryable())

    # 재시도 불가
    non_retryable = [
        "UNKNOWN_ERROR", "VALIDATION_ERROR", "PERMISSION_DENIED",
        "RESOURCE_NOT_FOUND", "INTERNAL_ERROR",
    ]
    for name in non_retryable:
        r.check(f"{name}.is_retryable()=False", not ErrorCode[name].is_retryable())


# ==================== 11. is_client_error / is_server_error ====================
def test_http_classification(r: TestResult) -> None:
    print("\n[11] HTTP 분류")
    from shared.constants.error_codes import ErrorCode

    # 클라이언트 에러 (4xx)
    client_errors = [
        "VALIDATION_ERROR", "AUTHENTICATION_REQUIRED", "PERMISSION_DENIED",
        "RESOURCE_NOT_FOUND", "VIDEO_TOO_LARGE", "RATE_LIMIT_EXCEEDED",
    ]
    for name in client_errors:
        e = ErrorCode[name]
        r.check(f"{name} is_client_error", e.is_client_error())
        r.check(f"{name} not is_server_error", not e.is_server_error())

    # 서버 에러 (5xx)
    server_errors = [
        "UNKNOWN_ERROR", "INTERNAL_ERROR", "DATABASE_ERROR",
        "ANALYSIS_ERROR", "MODEL_LOAD_FAILED",
    ]
    for name in server_errors:
        e = ErrorCode[name]
        r.check(f"{name} is_server_error", e.is_server_error())
        r.check(f"{name} not is_client_error", not e.is_client_error())

    # 200 코드 - 둘 다 아님
    r.check("DECODING_EOF neither", not ErrorCode.DECODING_EOF.is_client_error()
            and not ErrorCode.DECODING_EOF.is_server_error())


# ==================== 12. ErrorCode __str__ / __repr__ ====================
def test_error_code_string(r: TestResult) -> None:
    print("\n[12] ErrorCode 문자열 표현")
    from shared.constants.error_codes import ErrorCode

    e = ErrorCode.DATABASE_ERROR
    s = str(e)
    r.check("__str__ 코드 포함", "[5000]" in s)
    r.check("__str__ 메시지 포함", "데이터베이스" in s)

    rp = repr(e)
    r.check("__repr__ 이름 포함", "ErrorCode.DATABASE_ERROR" in rp)
    r.check("__repr__ 코드 포함", "code=5000" in rp)


# ==================== 13. ERROR_CODE_LOOKUP 캐시 ====================
def test_error_code_lookup(r: TestResult) -> None:
    print("\n[13] ERROR_CODE_LOOKUP 캐시")
    from shared.constants.error_codes import ErrorCode, ERROR_CODE_LOOKUP

    r.check("dict 타입", isinstance(ERROR_CODE_LOOKUP, dict))
    r.check("270개 엔트리", len(ERROR_CODE_LOOKUP) == 270)

    # O(1) 조회 = from_code와 동일
    r.check("LOOKUP[1000] = UNKNOWN_ERROR", ERROR_CODE_LOOKUP[1000] is ErrorCode.UNKNOWN_ERROR)
    r.check("LOOKUP[8000] = REFEREE_ERROR", ERROR_CODE_LOOKUP[8000] is ErrorCode.REFEREE_ERROR)

    # 없는 키
    r.check("999 not in LOOKUP", 999 not in ERROR_CODE_LOOKUP)


# ==================== 14. RETRYABLE_ERRORS ====================
def test_retryable_errors_set(r: TestResult) -> None:
    print("\n[14] RETRYABLE_ERRORS")
    from shared.constants.error_codes import ErrorCode, RETRYABLE_ERRORS

    r.check("frozenset 타입", isinstance(RETRYABLE_ERRORS, frozenset))
    r.check("18개", len(RETRYABLE_ERRORS) == 18)
    r.check("TIMEOUT_ERROR in", ErrorCode.TIMEOUT_ERROR in RETRYABLE_ERRORS)
    r.check("VALIDATION_ERROR not in", ErrorCode.VALIDATION_ERROR not in RETRYABLE_ERRORS)

    # 모든 멤버의 HTTP 상태가 5xx 또는 타임아웃/서비스불가
    for e in RETRYABLE_ERRORS:
        valid_status = e.http_status in {429, 500, 503, 504}
        r.check(f"{e.name} HTTP={e.http_status} 재시도 가능", valid_status)


# ==================== 15. 카테고리 그룹 타입/완전성 ====================
def test_category_group_integrity(r: TestResult) -> None:
    print("\n[15] 카테고리 그룹 완전성")
    from shared.constants.error_codes import (
        ErrorCode, ErrorCategory,
        GENERAL_ERRORS, AUTH_ERRORS, VALIDATION_ERRORS,
        BUSINESS_ERRORS, INFRASTRUCTURE_ERRORS, EXTERNAL_ERRORS,
        ANALYSIS_ERRORS, REFEREE_ERRORS, SYSTEM_ERRORS,
    )

    groups = {
        "GENERAL": (GENERAL_ERRORS, ErrorCategory.GENERAL, 6),
        "AUTH": (AUTH_ERRORS, ErrorCategory.AUTHENTICATION, 7),
        "VALIDATION": (VALIDATION_ERRORS, ErrorCategory.VALIDATION, 55),
        "BUSINESS": (BUSINESS_ERRORS, ErrorCategory.BUSINESS, 6),
        "INFRASTRUCTURE": (INFRASTRUCTURE_ERRORS, ErrorCategory.INFRASTRUCTURE, 109),
        "EXTERNAL": (EXTERNAL_ERRORS, ErrorCategory.EXTERNAL, 4),
        "ANALYSIS": (ANALYSIS_ERRORS, ErrorCategory.ANALYSIS, 64),
        "REFEREE": (REFEREE_ERRORS, ErrorCategory.REFEREE, 10),
        "SYSTEM": (SYSTEM_ERRORS, ErrorCategory.SYSTEM, 9),
    }

    for name, (group, cat, expected_count) in groups.items():
        r.check(f"{name}_ERRORS 크기={expected_count}", len(group) == expected_count,
                f"실제: {len(group)}")
        # 그룹 내 모든 코드가 올바른 카테고리
        wrong = [e.name for e in group if not cat.contains(e.code)]
        r.check(f"{name}_ERRORS 카테고리 범위 일치", len(wrong) == 0)


# ==================== 16. CONFIGURATION_ERRORS 부분집합 ====================
def test_configuration_errors_subset(r: TestResult) -> None:
    print("\n[16] CONFIGURATION_ERRORS")
    from shared.constants.error_codes import CONFIGURATION_ERRORS, SYSTEM_ERRORS, ErrorCode

    r.check("4개", len(CONFIGURATION_ERRORS) == 4)
    r.check("SYSTEM_ERRORS 부분집합", set(CONFIGURATION_ERRORS).issubset(set(SYSTEM_ERRORS)))
    r.check("9000 포함", ErrorCode.CONFIGURATION_ERROR in CONFIGURATION_ERRORS)
    r.check("9003 포함", ErrorCode.CONFIGURATION_LOAD_FAILED in CONFIGURATION_ERRORS)


# ==================== 17. 에러 메시지 품질 ====================
def test_error_message_quality(r: TestResult) -> None:
    print("\n[17] 에러 메시지 품질")
    from shared.constants.error_codes import ErrorCode

    # 모든 메시지가 비어있지 않고 한글 포함
    empty = [e.name for e in ErrorCode if not e.message]
    r.check("빈 메시지 없음", len(empty) == 0)

    # 메시지 길이 적정 (최소 5자)
    short = [e.name for e in ErrorCode if len(e.message) < 5]
    r.check("너무 짧은 메시지 없음", len(short) == 0, f"짧은: {short[:3]}")

    # 특정 메시지 내용 검증
    r.check("SSRF_DETECTED 메시지", "SSRF" in ErrorCode.SSRF_DETECTED.message)
    r.check("DNS_REBINDING 메시지", "DNS" in ErrorCode.DNS_REBINDING_DETECTED.message)
    r.check("SHOOTING_NOT_DETECTED 메시지", "슈팅" in ErrorCode.SHOOTING_NOT_DETECTED.message)


# ==================== 18. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[18] 에지 케이스")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    # 같은 에러 비교
    r.check("동일 에러 비교", ErrorCode.UNKNOWN_ERROR == ErrorCode.UNKNOWN_ERROR)
    r.check("다른 에러 비교", ErrorCode.UNKNOWN_ERROR != ErrorCode.INTERNAL_ERROR)

    # identity 보장
    r.check("identity 보장", ErrorCode.UNKNOWN_ERROR is ErrorCode.UNKNOWN_ERROR)

    # 해시 가능 (dict 키, set 멤버)
    d = {ErrorCode.UNKNOWN_ERROR: "test"}
    r.check("dict 키 사용 가능", d[ErrorCode.UNKNOWN_ERROR] == "test")

    s = {ErrorCode.UNKNOWN_ERROR, ErrorCode.INTERNAL_ERROR}
    r.check("set 멤버 사용 가능", len(s) == 2)

    # ErrorCategory도 해시 가능
    cat_set = set(ErrorCategory)
    r.check("ErrorCategory set 가능", len(cat_set) == 9)


def main():
    r = TestResult()
    test_error_category_basics(r)       # 1: 5
    test_error_category_contains(r)     # 2: 7
    test_error_category_from_code(r)    # 3: 11
    test_error_category_serialization(r)  # 4: 7
    test_error_code_basics(r)           # 5: 3
    test_error_code_category(r)         # 6: 9
    test_error_code_to_dict(r)          # 7: 5
    test_error_code_from_code(r)        # 8: 7
    test_get_by_category(r)             # 9: 4
    test_is_retryable(r)               # 10: 13
    test_http_classification(r)         # 11: 13
    test_error_code_string(r)           # 12: 4
    test_error_code_lookup(r)           # 13: 5
    test_retryable_errors_set(r)        # 14: 22
    test_category_group_integrity(r)    # 15: 18
    test_configuration_errors_subset(r) # 16: 4
    test_error_message_quality(r)       # 17: 5
    test_edge_cases(r)                  # 18: 6
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
