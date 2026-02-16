# -*- coding: utf-8 -*-
"""
tests/verify_error_codes.py

에러 코드 상수 모듈 검증 테스트
- typing 현대화 검증
- ErrorCategory 범위/속성 검증
- ErrorCode 코드 유일성 검증
- 코드-카테고리 범위 일치 검증
- HTTP 상태 코드 적절성 검증
- RETRYABLE_ERRORS 논리 검증
- 카테고리 그룹 완전성 검증
- ERROR_CODE_LOOKUP 캐시 검증
- __all__ export 검증
- __init__.py re-export 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
        print(f"검증 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== A. typing 현대화 검증 ====================
def test_typing_modernization(r: TestResult) -> None:
    print("\n[A] typing 현대화 검증")
    src = Path(_PROJECT_ROOT / "shared" / "constants" / "error_codes.py").read_text(encoding="utf-8")
    code_lines = [line.split("#")[0] for line in src.split("\n")]
    code_only = "\n".join(code_lines)

    r.check("typing import = Final만", "from typing import Final" in src)
    r.check("Dict[ 잔존 없음", "Dict[" not in code_only)
    r.check("FrozenSet[ 잔존 없음", "FrozenSet[" not in code_only)
    r.check("Tuple[ 잔존 없음", "Tuple[" not in code_only)
    r.check("List[ 잔존 없음", "List[" not in code_only)
    r.check("dict[ 사용 확인", "dict[" in code_only)
    r.check("frozenset[ 사용 확인", "frozenset[" in code_only)
    r.check("tuple[ 사용 확인", "tuple[" in code_only)


# ==================== B. ErrorCategory 검증 ====================
def test_error_category(r: TestResult) -> None:
    print("\n[B] ErrorCategory 검증")
    from shared.constants.error_codes import ErrorCategory

    expected = {
        "GENERAL": (1000, 1999, "일반 에러"),
        "AUTHENTICATION": (2000, 2999, "인증/권한 에러"),
        "VALIDATION": (3000, 3999, "입력 검증 에러"),
        "BUSINESS": (4000, 4999, "비즈니스 로직 에러"),
        "INFRASTRUCTURE": (5000, 5999, "인프라 에러"),
        "EXTERNAL": (6000, 6999, "외부 서비스 에러"),
        "ANALYSIS": (7000, 7999, "분석 엔진 에러"),
        "REFEREE": (8000, 8999, "AI 심판 에러"),
        "SYSTEM": (9000, 9999, "시스템 에러"),
    }
    r.check("카테고리 9개", len(ErrorCategory) == 9)

    for name, (start, end, desc) in expected.items():
        cat = ErrorCategory[name]
        r.check(f"{name} 시작={start}", cat.start == start)
        r.check(f"{name} 종료={end}", cat.end == end)
        r.check(f"{name} 설명", cat.description == desc)

    # 범위 겹침 없음 검증
    cats = list(ErrorCategory)
    for i in range(len(cats)):
        for j in range(i + 1, len(cats)):
            overlap = not (cats[i].end < cats[j].start or cats[j].end < cats[i].start)
            r.check(f"{cats[i].name}↔{cats[j].name} 범위 미겹침", not overlap)

    # contains 메서드 검증
    r.check("GENERAL.contains(1000)", ErrorCategory.GENERAL.contains(1000))
    r.check("GENERAL.contains(1999)", ErrorCategory.GENERAL.contains(1999))
    r.check("not GENERAL.contains(2000)", not ErrorCategory.GENERAL.contains(2000))

    # from_code 검증
    r.check("from_code(1000)=GENERAL", ErrorCategory.from_code(1000) == ErrorCategory.GENERAL)
    r.check("from_code(5500)=INFRASTRUCTURE", ErrorCategory.from_code(5500) == ErrorCategory.INFRASTRUCTURE)
    r.check("from_code(9200)=SYSTEM", ErrorCategory.from_code(9200) == ErrorCategory.SYSTEM)

    # from_code 잘못된 코드
    try:
        ErrorCategory.from_code(99999)
        r.fail("from_code(99999) ValueError", "예외 미발생")
    except ValueError:
        r.ok("from_code(99999) ValueError")

    # to_dict 검증
    d = ErrorCategory.GENERAL.to_dict()
    r.check("to_dict keys", set(d.keys()) == {"category", "start", "end", "description"})


# ==================== C. ErrorCode 코드 유일성 ====================
def test_code_uniqueness(r: TestResult) -> None:
    print("\n[C] ErrorCode 코드 유일성")
    from shared.constants.error_codes import ErrorCode

    codes = [e.code for e in ErrorCode]
    r.check(f"전체 {len(codes)}개 코드 유일성", len(codes) == len(set(codes)))

    # 이름 유일성 (@unique 보장이지만 확인)
    names = [e.name for e in ErrorCode]
    r.check(f"전체 {len(names)}개 이름 유일성", len(names) == len(set(names)))


# ==================== D. 코드-카테고리 범위 일치 ====================
def test_code_category_range(r: TestResult) -> None:
    print("\n[D] 코드-카테고리 범위 일치")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    category_counts = {cat: 0 for cat in ErrorCategory}
    mismatched = []

    for error in ErrorCode:
        code = error.code
        # 코드가 정확히 하나의 카테고리에 속하는지
        matching = [cat for cat in ErrorCategory if cat.contains(code)]
        if len(matching) != 1:
            mismatched.append(f"{error.name}({code}): {len(matching)}개 카테고리")
        else:
            category_counts[matching[0]] += 1

    r.check("모든 코드가 정확히 1개 카테고리", len(mismatched) == 0,
            f"불일치: {mismatched[:5]}")

    # 카테고리별 멤버 수 검증
    expected_counts = {
        "GENERAL": 6, "AUTHENTICATION": 7, "VALIDATION": 55,
        "BUSINESS": 6, "INFRASTRUCTURE": 109, "EXTERNAL": 4,
        "ANALYSIS": 64, "REFEREE": 10, "SYSTEM": 9,
    }
    for cat in ErrorCategory:
        expected = expected_counts[cat.name]
        actual = category_counts[cat]
        r.check(f"{cat.name}: {expected}개", actual == expected,
                f"예상 {expected}, 실제 {actual}")


# ==================== E. HTTP 상태 코드 적절성 ====================
def test_http_status_codes(r: TestResult) -> None:
    print("\n[E] HTTP 상태 코드 적절성")
    from shared.constants.error_codes import ErrorCode

    valid_statuses = {200, 400, 401, 403, 404, 405, 409, 412, 413, 429,
                      499, 500, 501, 502, 503, 504, 507}

    invalid = []
    for error in ErrorCode:
        if error.http_status not in valid_statuses:
            invalid.append(f"{error.name}: {error.http_status}")

    r.check("모든 HTTP 상태 유효", len(invalid) == 0,
            f"잘못된 상태: {invalid[:5]}")

    # 특정 매핑 검증
    spot_checks = {
        "UNKNOWN_ERROR": 500,
        "NOT_IMPLEMENTED": 501,
        "SERVICE_UNAVAILABLE": 503,
        "TIMEOUT_ERROR": 504,
        "RATE_LIMIT_EXCEEDED": 429,
        "AUTHENTICATION_REQUIRED": 401,
        "PERMISSION_DENIED": 403,
        "VALIDATION_ERROR": 400,
        "RESOURCE_NOT_FOUND": 404,
        "RESOURCE_ALREADY_EXISTS": 409,
        "OPERATION_NOT_ALLOWED": 405,
        "PRECONDITION_FAILED": 412,
        "VIDEO_TOO_LARGE": 413,
        "STORAGE_QUOTA_EXCEEDED": 507,
        "EXTERNAL_SERVICE_ERROR": 502,
        "ANALYSIS_CANCELLED": 499,
        "DECODING_EOF": 200,
        "END_OF_STREAM": 200,
    }
    for name, expected_status in spot_checks.items():
        error = ErrorCode[name]
        r.check(f"{name} → {expected_status}", error.http_status == expected_status)


# ==================== F. RETRYABLE_ERRORS 검증 ====================
def test_retryable_errors(r: TestResult) -> None:
    print("\n[F] RETRYABLE_ERRORS 검증")
    from shared.constants.error_codes import ErrorCode, RETRYABLE_ERRORS

    r.check("RETRYABLE_ERRORS는 frozenset", isinstance(RETRYABLE_ERRORS, frozenset))
    r.check("18개 재시도 가능 에러", len(RETRYABLE_ERRORS) == 18)

    # 모든 멤버가 ErrorCode인지
    r.check("모든 멤버가 ErrorCode", all(isinstance(e, ErrorCode) for e in RETRYABLE_ERRORS))

    # 예상 멤버 검증
    expected_retryable = {
        "TIMEOUT_ERROR", "SERVICE_UNAVAILABLE",
        "DATABASE_TIMEOUT", "DATABASE_CONNECTION_FAILED",
        "CACHE_CONNECTION_FAILED",
        "QUEUE_CONNECTION_FAILED", "QUEUE_TIMEOUT",
        "STORAGE_CONNECTION_FAILED",
        "STREAM_CONNECTION_FAILED", "STREAM_DISCONNECTED", "STREAM_TIMEOUT",
        "CONNECTION_ERROR", "CAMERA_DISCONNECTED", "CAMERA_TIMEOUT",
        "EXTERNAL_SERVICE_TIMEOUT", "EXTERNAL_SERVICE_UNAVAILABLE",
        "CIRCUIT_BREAKER_OPEN",
        "ANALYSIS_TIMEOUT",
    }
    actual_names = {e.name for e in RETRYABLE_ERRORS}
    r.check("재시도 에러 목록 일치", actual_names == expected_retryable,
            f"차이: {actual_names.symmetric_difference(expected_retryable)}")

    # is_retryable 메서드 검증
    r.check("TIMEOUT_ERROR.is_retryable()", ErrorCode.TIMEOUT_ERROR.is_retryable())
    r.check("not UNKNOWN_ERROR.is_retryable()", not ErrorCode.UNKNOWN_ERROR.is_retryable())
    r.check("CIRCUIT_BREAKER_OPEN.is_retryable()", ErrorCode.CIRCUIT_BREAKER_OPEN.is_retryable())
    r.check("not VALIDATION_ERROR.is_retryable()", not ErrorCode.VALIDATION_ERROR.is_retryable())


# ==================== G. ERROR_CODE_LOOKUP 캐시 검증 ====================
def test_error_code_lookup(r: TestResult) -> None:
    print("\n[G] ERROR_CODE_LOOKUP 캐시 검증")
    from shared.constants.error_codes import ErrorCode, ERROR_CODE_LOOKUP

    r.check("ERROR_CODE_LOOKUP는 dict", isinstance(ERROR_CODE_LOOKUP, dict))
    r.check(f"캐시 크기 = {len(list(ErrorCode))}",
            len(ERROR_CODE_LOOKUP) == len(list(ErrorCode)))

    # 모든 ErrorCode가 캐시에 존재
    missing = [e.name for e in ErrorCode if e.code not in ERROR_CODE_LOOKUP]
    r.check("모든 코드 캐시 존재", len(missing) == 0, f"누락: {missing[:5]}")

    # 캐시 값이 원본과 동일
    mismatch = [e.name for e in ErrorCode if ERROR_CODE_LOOKUP[e.code] is not e]
    r.check("캐시 값 = 원본 동일", len(mismatch) == 0)

    # from_code 메서드 검증
    r.check("from_code(1000)=UNKNOWN_ERROR",
            ErrorCode.from_code(1000) == ErrorCode.UNKNOWN_ERROR)
    r.check("from_code(5001)=DATABASE_CONNECTION_FAILED",
            ErrorCode.from_code(5001) == ErrorCode.DATABASE_CONNECTION_FAILED)
    r.check("from_code(8000)=REFEREE_ERROR",
            ErrorCode.from_code(8000) == ErrorCode.REFEREE_ERROR)

    # from_code 잘못된 코드
    try:
        ErrorCode.from_code(99999)
        r.fail("from_code(99999) ValueError", "예외 미발생")
    except ValueError:
        r.ok("from_code(99999) ValueError")


# ==================== H. 카테고리 그룹 완전성 검증 ====================
def test_category_groups(r: TestResult) -> None:
    print("\n[H] 카테고리 그룹 완전성")
    from shared.constants.error_codes import (
        ErrorCode, ErrorCategory,
        GENERAL_ERRORS, AUTH_ERRORS, VALIDATION_ERRORS,
        BUSINESS_ERRORS, INFRASTRUCTURE_ERRORS, EXTERNAL_ERRORS,
        ANALYSIS_ERRORS, REFEREE_ERRORS, SYSTEM_ERRORS,
        CONFIGURATION_ERRORS,
    )

    groups = {
        "GENERAL_ERRORS": (GENERAL_ERRORS, ErrorCategory.GENERAL),
        "AUTH_ERRORS": (AUTH_ERRORS, ErrorCategory.AUTHENTICATION),
        "VALIDATION_ERRORS": (VALIDATION_ERRORS, ErrorCategory.VALIDATION),
        "BUSINESS_ERRORS": (BUSINESS_ERRORS, ErrorCategory.BUSINESS),
        "INFRASTRUCTURE_ERRORS": (INFRASTRUCTURE_ERRORS, ErrorCategory.INFRASTRUCTURE),
        "EXTERNAL_ERRORS": (EXTERNAL_ERRORS, ErrorCategory.EXTERNAL),
        "ANALYSIS_ERRORS": (ANALYSIS_ERRORS, ErrorCategory.ANALYSIS),
        "REFEREE_ERRORS": (REFEREE_ERRORS, ErrorCategory.REFEREE),
        "SYSTEM_ERRORS": (SYSTEM_ERRORS, ErrorCategory.SYSTEM),
    }

    for group_name, (group, category) in groups.items():
        # 그룹이 tuple인지
        r.check(f"{group_name}는 tuple", isinstance(group, tuple))

        # 모든 멤버가 올바른 카테고리에 속하는지
        wrong_cat = [e.name for e in group if not category.contains(e.code)]
        r.check(f"{group_name} 카테고리 일치", len(wrong_cat) == 0,
                f"잘못된: {wrong_cat[:3]}")

        # 해당 카테고리의 모든 ErrorCode가 그룹에 포함되는지
        category_errors = {e for e in ErrorCode if category.contains(e.code)}
        group_set = set(group)
        missing = category_errors - group_set
        r.check(f"{group_name} 완전성 ({len(group)}개)",
                len(missing) == 0, f"누락: {[e.name for e in missing][:3]}")

    # CONFIGURATION_ERRORS는 SYSTEM_ERRORS 부분집합
    r.check("CONFIGURATION_ERRORS ⊂ SYSTEM_ERRORS",
            set(CONFIGURATION_ERRORS).issubset(set(SYSTEM_ERRORS)))
    r.check("CONFIGURATION_ERRORS = 4개", len(CONFIGURATION_ERRORS) == 4)


# ==================== I. ErrorCode 속성/메서드 검증 ====================
def test_error_code_properties(r: TestResult) -> None:
    print("\n[I] ErrorCode 속성/메서드 검증")
    from shared.constants.error_codes import ErrorCode, ErrorCategory

    # code, message, http_status 속성
    e = ErrorCode.UNKNOWN_ERROR
    r.check("code 속성", e.code == 1000)
    r.check("message 속성", e.message == "알 수 없는 오류가 발생했습니다")
    r.check("http_status 속성", e.http_status == 500)

    # category 속성
    r.check("UNKNOWN_ERROR.category=GENERAL", e.category == ErrorCategory.GENERAL)
    r.check("AUTHENTICATION_REQUIRED.category=AUTHENTICATION",
            ErrorCode.AUTHENTICATION_REQUIRED.category == ErrorCategory.AUTHENTICATION)
    r.check("REFEREE_ERROR.category=REFEREE",
            ErrorCode.REFEREE_ERROR.category == ErrorCategory.REFEREE)

    # is_client_error / is_server_error
    r.check("VALIDATION_ERROR.is_client_error()", ErrorCode.VALIDATION_ERROR.is_client_error())
    r.check("not VALIDATION_ERROR.is_server_error()", not ErrorCode.VALIDATION_ERROR.is_server_error())
    r.check("INTERNAL_ERROR.is_server_error()", ErrorCode.INTERNAL_ERROR.is_server_error())
    r.check("not INTERNAL_ERROR.is_client_error()", not ErrorCode.INTERNAL_ERROR.is_client_error())

    # DECODING_EOF(200) - 클라이언트/서버 에러 아님
    r.check("DECODING_EOF: not client", not ErrorCode.DECODING_EOF.is_client_error())
    r.check("DECODING_EOF: not server", not ErrorCode.DECODING_EOF.is_server_error())

    # to_dict
    d = e.to_dict()
    r.check("to_dict keys", set(d.keys()) == {"error_code", "code", "message", "http_status", "category"})
    r.check("to_dict code", d["code"] == 1000)
    r.check("to_dict category", d["category"] == "GENERAL")

    # get_by_category
    general_codes = ErrorCode.get_by_category(ErrorCategory.GENERAL)
    r.check("get_by_category(GENERAL) tuple", isinstance(general_codes, tuple))
    r.check("get_by_category(GENERAL) 6개", len(general_codes) == 6)

    # __str__ / __repr__
    r.check("__str__ 형식", "[1000]" in str(e))
    r.check("__repr__ 형식", "ErrorCode.UNKNOWN_ERROR" in repr(e))


# ==================== J. 주요 에러 코드 값 검증 ====================
def test_specific_error_codes(r: TestResult) -> None:
    print("\n[J] 주요 에러 코드 값 검증")
    from shared.constants.error_codes import ErrorCode

    # 1xxx
    r.check("UNKNOWN_ERROR=1000", ErrorCode.UNKNOWN_ERROR.code == 1000)
    r.check("RATE_LIMIT_EXCEEDED=1005", ErrorCode.RATE_LIMIT_EXCEEDED.code == 1005)

    # 2xxx
    r.check("AUTHENTICATION_REQUIRED=2000", ErrorCode.AUTHENTICATION_REQUIRED.code == 2000)
    r.check("API_KEY_EXPIRED=2006", ErrorCode.API_KEY_EXPIRED.code == 2006)

    # 3xxx 경계
    r.check("VALIDATION_ERROR=3000", ErrorCode.VALIDATION_ERROR.code == 3000)
    r.check("QUALITY_CHECK_FAILED=3082", ErrorCode.QUALITY_CHECK_FAILED.code == 3082)

    # 4xxx
    r.check("RESOURCE_NOT_FOUND=4000", ErrorCode.RESOURCE_NOT_FOUND.code == 4000)
    r.check("QUOTA_EXCEEDED=4005", ErrorCode.QUOTA_EXCEEDED.code == 4005)

    # 5xxx 경계
    r.check("DATABASE_ERROR=5000", ErrorCode.DATABASE_ERROR.code == 5000)
    r.check("CAMERA_SESSION_ERROR=5911", ErrorCode.CAMERA_SESSION_ERROR.code == 5911)

    # 6xxx
    r.check("EXTERNAL_SERVICE_ERROR=6000", ErrorCode.EXTERNAL_SERVICE_ERROR.code == 6000)
    r.check("WEBHOOK_DELIVERY_FAILED=6003", ErrorCode.WEBHOOK_DELIVERY_FAILED.code == 6003)

    # 7xxx
    r.check("ANALYSIS_ERROR=7000", ErrorCode.ANALYSIS_ERROR.code == 7000)
    r.check("EXPLANATION_ERROR=7824", ErrorCode.EXPLANATION_ERROR.code == 7824)

    # 8xxx
    r.check("REFEREE_ERROR=8000", ErrorCode.REFEREE_ERROR.code == 8000)
    r.check("RULE_SET_SCHEMA_ERROR=8009", ErrorCode.RULE_SET_SCHEMA_ERROR.code == 8009)

    # 9xxx
    r.check("CONFIGURATION_ERROR=9000", ErrorCode.CONFIGURATION_ERROR.code == 9000)
    r.check("MISSING_DEPENDENCY=9202", ErrorCode.MISSING_DEPENDENCY.code == 9202)


# ==================== K. __all__ export 검증 ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[K] __all__ export 검증")
    from shared.constants import error_codes

    expected_all = {
        "ErrorCategory", "ErrorCode",
        "ERROR_CODE_LOOKUP", "RETRYABLE_ERRORS",
        "GENERAL_ERRORS", "AUTH_ERRORS", "VALIDATION_ERRORS",
        "BUSINESS_ERRORS", "INFRASTRUCTURE_ERRORS", "EXTERNAL_ERRORS",
        "ANALYSIS_ERRORS", "REFEREE_ERRORS", "CONFIGURATION_ERRORS",
        "SYSTEM_ERRORS",
    }
    actual_all = set(error_codes.__all__)
    r.check(f"__all__ 14개 항목", len(actual_all) == 14,
            f"실제: {len(actual_all)}")
    r.check("__all__ 목록 일치", actual_all == expected_all,
            f"차이: {actual_all.symmetric_difference(expected_all)}")

    # SupportedLanguage 미포함
    r.check("SupportedLanguage not in __all__", "SupportedLanguage" not in actual_all)

    # 모든 export가 실제 존재
    for name in expected_all:
        r.check(f"export '{name}' 존재", hasattr(error_codes, name))


# ==================== L. __init__.py re-export 검증 ====================
def test_init_reexport(r: TestResult) -> None:
    print("\n[L] __init__.py re-export 검증")
    import shared.constants as pkg

    # __init__.py에서 re-export하는 항목
    init_expected = [
        "ErrorCategory", "ErrorCode",
        "GENERAL_ERRORS", "AUTH_ERRORS", "VALIDATION_ERRORS",
        "BUSINESS_ERRORS", "INFRASTRUCTURE_ERRORS", "EXTERNAL_ERRORS",
        "ANALYSIS_ERRORS", "REFEREE_ERRORS", "CONFIGURATION_ERRORS",
        "SYSTEM_ERRORS",
    ]
    for name in init_expected:
        r.check(f"__init__.py re-export '{name}'", hasattr(pkg, name))


# ==================== M. 에러 메시지 검증 ====================
def test_error_messages(r: TestResult) -> None:
    print("\n[M] 에러 메시지 검증")
    from shared.constants.error_codes import ErrorCode

    # 모든 에러 메시지가 비어있지 않은 문자열인지
    empty_msgs = [e.name for e in ErrorCode if not e.message or not isinstance(e.message, str)]
    r.check("모든 메시지 비어있지 않음", len(empty_msgs) == 0,
            f"빈 메시지: {empty_msgs[:5]}")

    # 모든 메시지가 한글 포함
    no_korean = []
    for e in ErrorCode:
        has_korean = any('\uac00' <= c <= '\ud7a3' for c in e.message)
        if not has_korean:
            no_korean.append(e.name)
    r.check("모든 메시지 한글 포함", len(no_korean) == 0,
            f"한글 없음: {no_korean[:5]}")


# ==================== N. HTTP 상태별 분류 검증 ====================
def test_http_classification(r: TestResult) -> None:
    print("\n[N] HTTP 상태별 분류 일관성")
    from shared.constants.error_codes import ErrorCode

    # 4xx = client error, 5xx = server error
    client_wrong = []
    server_wrong = []
    for e in ErrorCode:
        if 400 <= e.http_status < 500:
            if not e.is_client_error():
                client_wrong.append(e.name)
            if e.is_server_error():
                server_wrong.append(e.name)
        elif 500 <= e.http_status < 600:
            if not e.is_server_error():
                server_wrong.append(e.name)
            if e.is_client_error():
                client_wrong.append(e.name)

    r.check("4xx → is_client_error() 일관성", len(client_wrong) == 0,
            f"불일치: {client_wrong[:5]}")
    r.check("5xx → is_server_error() 일관성", len(server_wrong) == 0,
            f"불일치: {server_wrong[:5]}")

    # 200 코드는 둘 다 아님
    ok_codes = [e for e in ErrorCode if e.http_status == 200]
    for e in ok_codes:
        r.check(f"{e.name}(200): not client/server",
                not e.is_client_error() and not e.is_server_error())


def main():
    r = TestResult()
    test_typing_modernization(r)   # A: 8
    test_error_category(r)         # B: ~40
    test_code_uniqueness(r)        # C: 2
    test_code_category_range(r)    # D: 10
    test_http_status_codes(r)      # E: 19
    test_retryable_errors(r)       # F: 7
    test_error_code_lookup(r)      # G: 8
    test_category_groups(r)        # H: ~30
    test_error_code_properties(r)  # I: ~18
    test_specific_error_codes(r)   # J: 18
    test_all_exports(r)            # K: 17
    test_init_reexport(r)          # L: 12
    test_error_messages(r)         # M: 2
    test_http_classification(r)    # N: 4
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
