# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/unit
파일: test_base_exception.py
설명: base_exception.py 단위 테스트 (4개 클래스, 전체 메서드 검증)

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
from datetime import datetime, timezone

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
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str) -> None:
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        detail = f" - {msg}" if msg else ""
        print(f"  [FAIL] {name}{detail}")

    def check(self, name: str, condition: bool, msg: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 1. CourtViewException 테스트
# =============================================================================
def test_courtview_exception_defaults(t: TestResult) -> None:
    """기본값 초기화 테스트."""
    e = CourtViewException()

    t.check("기본 error_code = UNKNOWN_ERROR",
            e.error_code == ErrorCode.UNKNOWN_ERROR)
    t.check("기본 message = UNKNOWN_ERROR.message",
            e.message == ErrorCode.UNKNOWN_ERROR.message)
    t.check("기본 details = 빈 dict",
            e.details == {})
    t.check("기본 context = 빈 dict",
            e.context == {})
    t.check("기본 cause = None",
            e.cause is None)
    t.check("timestamp 존재",
            isinstance(e.timestamp, datetime))
    t.check("timestamp UTC timezone",
            e.timestamp.tzinfo == timezone.utc)
    t.check("_traceback = None (cause 없을 때)",
            e._traceback is None)


def test_courtview_exception_custom(t: TestResult) -> None:
    """커스텀 값으로 초기화 테스트."""
    cause = ValueError("원인 예외")
    e = CourtViewException(
        error_code=ErrorCode.ANALYSIS_ERROR,
        message="분석 실패",
        details={"video_id": "v001"},
        context={"request_id": "req-123"},
        cause=cause,
    )

    t.check("error_code = ANALYSIS_ERROR",
            e.error_code == ErrorCode.ANALYSIS_ERROR)
    t.check("message = '분석 실패'",
            e.message == "분석 실패")
    t.check("details에 video_id 포함",
            e.details.get("video_id") == "v001")
    t.check("context에 request_id 포함",
            e.context.get("request_id") == "req-123")
    t.check("cause = ValueError",
            e.cause is cause)
    t.check("__cause__ 체이닝 설정",
            e.__cause__ is cause)
    t.check("_traceback 문자열 존재",
            isinstance(e._traceback, str) and len(e._traceback) > 0)


def test_courtview_exception_properties(t: TestResult) -> None:
    """속성 프로퍼티 테스트."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR)

    t.check("code 프로퍼티 = ErrorCode.code",
            e.code == ErrorCode.ANALYSIS_ERROR.code)
    t.check("http_status 프로퍼티 = ErrorCode.http_status",
            e.http_status == ErrorCode.ANALYSIS_ERROR.http_status)
    t.check("error_name 프로퍼티 = ErrorCode.name",
            e.error_name == ErrorCode.ANALYSIS_ERROR.name)


def test_courtview_exception_to_dict(t: TestResult) -> None:
    """to_dict() 메서드 테스트."""
    cause = RuntimeError("런타임 에러")
    e = CourtViewException(
        ErrorCode.VIDEO_ERROR,
        "비디오 오류",
        details={"path": "/tmp/test.mp4"},
        context={"user_id": "u001"},
        cause=cause,
    )
    d = e.to_dict()

    t.check("to_dict에 error 키 존재",
            "error" in d)
    t.check("error.code 일치",
            d["error"]["code"] == ErrorCode.VIDEO_ERROR.code)
    t.check("error.name 일치",
            d["error"]["name"] == "VIDEO_ERROR")
    t.check("error.message 일치",
            d["error"]["message"] == "비디오 오류")
    t.check("error.http_status 일치",
            d["error"]["http_status"] == ErrorCode.VIDEO_ERROR.http_status)
    t.check("timestamp ISO 형식",
            "timestamp" in d and isinstance(d["timestamp"], str))
    t.check("details 포함",
            d.get("details", {}).get("path") == "/tmp/test.mp4")
    t.check("context 포함",
            d.get("context", {}).get("user_id") == "u001")
    t.check("cause 포함",
            d.get("cause", {}).get("type") == "RuntimeError")

    # traceback 미포함 (기본)
    t.check("traceback 미포함 (기본)",
            "traceback" not in d)

    # traceback 포함 옵션
    d_trace = e.to_dict(include_traceback=True)
    t.check("traceback 포함 (옵션=True)",
            "traceback" in d_trace and isinstance(d_trace["traceback"], str))


def test_courtview_exception_to_dict_minimal(t: TestResult) -> None:
    """최소 정보 to_dict 테스트 (details/context/cause 없을 때)."""
    e = CourtViewException()
    d = e.to_dict()

    t.check("details 미포함 (빈 dict)",
            "details" not in d)
    t.check("context 미포함 (빈 dict)",
            "context" not in d)
    t.check("cause 미포함 (None)",
            "cause" not in d)
    t.check("traceback 미포함",
            "traceback" not in d)


def test_courtview_exception_to_response_dict(t: TestResult) -> None:
    """to_response_dict() 메서드 테스트."""
    e = CourtViewException(
        ErrorCode.ANALYSIS_ERROR,
        "분석 실패",
        details={"info": "값"},
    )
    rd = e.to_response_dict()

    t.check("success = False",
            rd["success"] is False)
    t.check("error.code 포함",
            rd["error"]["code"] == ErrorCode.ANALYSIS_ERROR.code)
    t.check("error.name 포함",
            rd["error"]["name"] == "ANALYSIS_ERROR")
    t.check("error.message 포함",
            rd["error"]["message"] == "분석 실패")
    t.check("details 포함",
            rd["details"] is not None and rd["details"]["info"] == "값")
    t.check("traceback 미포함 (API 응답)",
            "traceback" not in rd)

    # details 없을 때
    e2 = CourtViewException()
    rd2 = e2.to_response_dict()
    t.check("details = None (빈 dict일 때)",
            rd2["details"] is None)


def test_courtview_exception_with_context(t: TestResult) -> None:
    """with_context() 메서드 체이닝 테스트."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR)
    result = e.with_context(request_id="req-001", session_id="sess-001")

    t.check("with_context 반환값 = self",
            result is e)
    t.check("context에 request_id 추가됨",
            e.context["request_id"] == "req-001")
    t.check("context에 session_id 추가됨",
            e.context["session_id"] == "sess-001")

    # 추가 호출로 병합
    e.with_context(user_id="u001")
    t.check("추가 with_context 병합",
            len(e.context) == 3 and e.context["user_id"] == "u001")


def test_courtview_exception_with_details(t: TestResult) -> None:
    """with_details() 메서드 체이닝 테스트."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR)
    result = e.with_details(video_id="v001", frame=100)

    t.check("with_details 반환값 = self",
            result is e)
    t.check("details에 video_id 추가됨",
            e.details["video_id"] == "v001")
    t.check("details에 frame 추가됨",
            e.details["frame"] == 100)


def test_courtview_exception_str_repr(t: TestResult) -> None:
    """__str__ / __repr__ 테스트."""
    e = CourtViewException(ErrorCode.ANALYSIS_ERROR, "테스트 메시지")

    s = str(e)
    t.check("__str__ 포맷: [code] name: message",
            f"[{ErrorCode.ANALYSIS_ERROR.code}]" in s and "ANALYSIS_ERROR" in s
            and "테스트 메시지" in s)

    r = repr(e)
    t.check("__repr__에 클래스명 포함",
            "CourtViewException(" in r)
    t.check("__repr__에 error_code 포함",
            "error_code=" in r)
    t.check("__repr__에 message 포함",
            "테스트 메시지" in r)


def test_courtview_exception_inheritance(t: TestResult) -> None:
    """상속 관계 테스트."""
    e = CourtViewException()
    t.check("Exception 상속",
            isinstance(e, Exception))
    t.check("BaseException 상속",
            isinstance(e, BaseException))


def test_courtview_exception_raise_catch(t: TestResult) -> None:
    """raise/catch 동작 테스트."""
    try:
        raise CourtViewException(ErrorCode.ANALYSIS_ERROR, "테스트")
    except CourtViewException as e:
        t.check("CourtViewException으로 catch 가능",
                e.error_code == ErrorCode.ANALYSIS_ERROR)
    except Exception:
        t.fail("CourtViewException으로 catch 실패")

    try:
        raise CourtViewException(ErrorCode.ANALYSIS_ERROR, "테스트")
    except Exception as e:
        t.check("Exception으로도 catch 가능",
                isinstance(e, CourtViewException))


def test_courtview_exception_chaining(t: TestResult) -> None:
    """예외 체이닝 테스트."""
    original = ValueError("원본 에러")
    try:
        try:
            raise original
        except ValueError as ve:
            raise CourtViewException(
                ErrorCode.ANALYSIS_ERROR, "래핑 에러", cause=ve
            ) from ve
    except CourtViewException as e:
        t.check("체이닝 cause 설정",
                e.__cause__ is original)
        t.check("cause 속성 = 원본",
                e.cause is original)


# =============================================================================
# 2. RetryableException 테스트
# =============================================================================
def test_retryable_defaults(t: TestResult) -> None:
    """RetryableException 기본값 테스트."""
    e = RetryableException()

    t.check("기본 error_code = SERVICE_UNAVAILABLE",
            e.error_code == ErrorCode.SERVICE_UNAVAILABLE)
    t.check("기본 retry_after = 1.0",
            e.retry_after == 1.0)
    t.check("기본 max_retries = 3",
            e.max_retries == 3)


def test_retryable_custom(t: TestResult) -> None:
    """RetryableException 커스텀 값 테스트."""
    e = RetryableException(
        error_code=ErrorCode.VIDEO_DOWNLOAD_FAILED,
        message="다운로드 실패",
        retry_after=5.0,
        max_retries=5,
    )

    t.check("error_code = VIDEO_DOWNLOAD_FAILED",
            e.error_code == ErrorCode.VIDEO_DOWNLOAD_FAILED)
    t.check("message = '다운로드 실패'",
            e.message == "다운로드 실패")
    t.check("retry_after = 5.0",
            e.retry_after == 5.0)
    t.check("max_retries = 5",
            e.max_retries == 5)


def test_retryable_to_dict(t: TestResult) -> None:
    """RetryableException to_dict 테스트."""
    e = RetryableException(retry_after=2.5, max_retries=10)
    d = e.to_dict()

    t.check("retry 키 존재",
            "retry" in d)
    t.check("retry.retry_after = 2.5",
            d["retry"]["retry_after"] == 2.5)
    t.check("retry.max_retries = 10",
            d["retry"]["max_retries"] == 10)
    t.check("error 키도 존재 (부모 호출)",
            "error" in d)


def test_retryable_inheritance(t: TestResult) -> None:
    """RetryableException 상속 관계 테스트."""
    e = RetryableException()
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))
    t.check("Exception 상속",
            isinstance(e, Exception))

    # with_context, with_details 사용 가능
    result = e.with_context(req="test")
    t.check("with_context 사용 가능",
            e.context["req"] == "test" and result is e)


# =============================================================================
# 3. NonRetryableException 테스트
# =============================================================================
def test_non_retryable_defaults(t: TestResult) -> None:
    """NonRetryableException 기본값 테스트."""
    e = NonRetryableException()

    t.check("기본 error_code = VALIDATION_ERROR",
            e.error_code == ErrorCode.VALIDATION_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))


def test_non_retryable_to_dict(t: TestResult) -> None:
    """NonRetryableException to_dict 테스트."""
    e = NonRetryableException(
        ErrorCode.VIDEO_FORMAT_UNSUPPORTED,
        "형식 오류",
    )
    d = e.to_dict()

    t.check("retryable 키 존재",
            "retryable" in d)
    t.check("retryable = False",
            d["retryable"] is False)
    t.check("error 키 존재",
            "error" in d)
    t.check("error.name = VIDEO_FORMAT_UNSUPPORTED",
            d["error"]["name"] == "VIDEO_FORMAT_UNSUPPORTED")


def test_non_retryable_custom(t: TestResult) -> None:
    """NonRetryableException 커스텀 값 테스트."""
    cause = TypeError("타입 오류")
    e = NonRetryableException(
        ErrorCode.DETECTION_NO_PERSON,
        "사람 미감지",
        details={"frame": 42},
        context={"video_id": "v01"},
        cause=cause,
    )

    t.check("error_code 설정",
            e.error_code == ErrorCode.DETECTION_NO_PERSON)
    t.check("message 설정",
            e.message == "사람 미감지")
    t.check("details 설정",
            e.details["frame"] == 42)
    t.check("context 설정",
            e.context["video_id"] == "v01")
    t.check("cause 설정",
            e.cause is cause)


# =============================================================================
# 4. CriticalException 테스트
# =============================================================================
def test_critical_defaults(t: TestResult) -> None:
    """CriticalException 기본값 테스트."""
    e = CriticalException()

    t.check("기본 error_code = INTERNAL_ERROR",
            e.error_code == ErrorCode.INTERNAL_ERROR)
    t.check("기본 alert_required = True",
            e.alert_required is True)
    t.check("기본 severity = 5",
            e.severity == 5)


def test_critical_custom(t: TestResult) -> None:
    """CriticalException 커스텀 값 테스트."""
    e = CriticalException(
        ErrorCode.INTERNAL_ERROR,
        "시스템 장애",
        alert_required=False,
        severity=3,
    )

    t.check("alert_required = False",
            e.alert_required is False)
    t.check("severity = 3",
            e.severity == 3)


def test_critical_severity_clamping(t: TestResult) -> None:
    """CriticalException severity 범위 제한 테스트."""
    e_low = CriticalException(severity=0)
    t.check("severity < 1 → 1로 클램핑",
            e_low.severity == 1)

    e_neg = CriticalException(severity=-10)
    t.check("severity = -10 → 1로 클램핑",
            e_neg.severity == 1)

    e_high = CriticalException(severity=100)
    t.check("severity > 5 → 5로 클램핑",
            e_high.severity == 5)

    e_exact_1 = CriticalException(severity=1)
    t.check("severity = 1 → 1 유지",
            e_exact_1.severity == 1)

    e_exact_5 = CriticalException(severity=5)
    t.check("severity = 5 → 5 유지",
            e_exact_5.severity == 5)

    e_mid = CriticalException(severity=3)
    t.check("severity = 3 → 3 유지",
            e_mid.severity == 3)


def test_critical_to_dict(t: TestResult) -> None:
    """CriticalException to_dict 테스트."""
    e = CriticalException(
        ErrorCode.INTERNAL_ERROR,
        "장애",
        alert_required=True,
        severity=4,
    )
    d = e.to_dict()

    t.check("critical 키 존재",
            "critical" in d)
    t.check("critical.alert_required = True",
            d["critical"]["alert_required"] is True)
    t.check("critical.severity = 4",
            d["critical"]["severity"] == 4)
    t.check("error 키 존재",
            "error" in d)


def test_critical_inheritance(t: TestResult) -> None:
    """CriticalException 상속 관계 테스트."""
    e = CriticalException()
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))
    t.check("Exception 상속",
            isinstance(e, Exception))


# =============================================================================
# 5. 교차 검증: __all__ export / 모듈 메타데이터
# =============================================================================
def test_module_metadata(t: TestResult) -> None:
    """모듈 메타데이터 검증."""
    import shared.exceptions.base_exception as mod

    t.check("__version__ = '1.0.0'",
            mod.__version__ == "1.0.0")
    t.check("__all__ 길이 = 4",
            len(mod.__all__) == 4)

    expected = {"CourtViewException", "RetryableException",
                "NonRetryableException", "CriticalException"}
    t.check("__all__ 내용 일치",
            set(mod.__all__) == expected)


def test_all_exports_importable(t: TestResult) -> None:
    """__all__ 모든 항목 import 가능 검증."""
    import shared.exceptions.base_exception as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        t.check(f"export '{name}' 존재",
                obj is not None)
        t.check(f"export '{name}' 은 클래스",
                isinstance(obj, type))


# =============================================================================
# 6. 엣지 케이스
# =============================================================================
def test_edge_cases(t: TestResult) -> None:
    """엣지 케이스 테스트."""
    # 빈 문자열 message → 빈 문자열 유지 (falsy이므로 error_code.message 사용)
    e1 = CourtViewException(ErrorCode.ANALYSIS_ERROR, message="")
    t.check("빈 message → error_code.message 사용",
            e1.message == ErrorCode.ANALYSIS_ERROR.message)

    # None message → error_code.message 사용
    e2 = CourtViewException(ErrorCode.ANALYSIS_ERROR, message=None)
    t.check("None message → error_code.message 사용",
            e2.message == ErrorCode.ANALYSIS_ERROR.message)

    # 여러 번 with_context/with_details 체이닝
    e3 = (CourtViewException(ErrorCode.ANALYSIS_ERROR)
          .with_context(a=1)
          .with_details(b=2)
          .with_context(c=3)
          .with_details(d=4))
    t.check("다중 체이닝 context",
            e3.context == {"a": 1, "c": 3})
    t.check("다중 체이닝 details",
            e3.details == {"b": 2, "d": 4})

    # cause에 __traceback__ 없는 예외
    bare_cause = ValueError("bare")
    e4 = CourtViewException(ErrorCode.ANALYSIS_ERROR, cause=bare_cause)
    t.check("__traceback__ 없는 cause 처리",
            e4.cause is bare_cause)

    # to_dict include_traceback=True 이지만 _traceback이 None
    e5 = CourtViewException(ErrorCode.ANALYSIS_ERROR)
    d5 = e5.to_dict(include_traceback=True)
    t.check("_traceback None이면 traceback 키 미포함",
            "traceback" not in d5)


# =============================================================================
# 메인
# =============================================================================
def main() -> None:
    t = TestResult()
    print("\n" + "=" * 60)
    print("  base_exception.py v1.0.0 단위 테스트")
    print("=" * 60)

    # 1. CourtViewException
    t.set_section("[1] CourtViewException - 기본값 초기화")
    test_courtview_exception_defaults(t)

    t.set_section("[2] CourtViewException - 커스텀 초기화")
    test_courtview_exception_custom(t)

    t.set_section("[3] CourtViewException - 프로퍼티")
    test_courtview_exception_properties(t)

    t.set_section("[4] CourtViewException - to_dict()")
    test_courtview_exception_to_dict(t)

    t.set_section("[5] CourtViewException - to_dict() 최소")
    test_courtview_exception_to_dict_minimal(t)

    t.set_section("[6] CourtViewException - to_response_dict()")
    test_courtview_exception_to_response_dict(t)

    t.set_section("[7] CourtViewException - with_context()")
    test_courtview_exception_with_context(t)

    t.set_section("[8] CourtViewException - with_details()")
    test_courtview_exception_with_details(t)

    t.set_section("[9] CourtViewException - __str__ / __repr__")
    test_courtview_exception_str_repr(t)

    t.set_section("[10] CourtViewException - 상속 관계")
    test_courtview_exception_inheritance(t)

    t.set_section("[11] CourtViewException - raise/catch")
    test_courtview_exception_raise_catch(t)

    t.set_section("[12] CourtViewException - 예외 체이닝")
    test_courtview_exception_chaining(t)

    # 2. RetryableException
    t.set_section("[13] RetryableException - 기본값")
    test_retryable_defaults(t)

    t.set_section("[14] RetryableException - 커스텀")
    test_retryable_custom(t)

    t.set_section("[15] RetryableException - to_dict()")
    test_retryable_to_dict(t)

    t.set_section("[16] RetryableException - 상속")
    test_retryable_inheritance(t)

    # 3. NonRetryableException
    t.set_section("[17] NonRetryableException - 기본값")
    test_non_retryable_defaults(t)

    t.set_section("[18] NonRetryableException - to_dict()")
    test_non_retryable_to_dict(t)

    t.set_section("[19] NonRetryableException - 커스텀")
    test_non_retryable_custom(t)

    # 4. CriticalException
    t.set_section("[20] CriticalException - 기본값")
    test_critical_defaults(t)

    t.set_section("[21] CriticalException - 커스텀")
    test_critical_custom(t)

    t.set_section("[22] CriticalException - severity 클램핑")
    test_critical_severity_clamping(t)

    t.set_section("[23] CriticalException - to_dict()")
    test_critical_to_dict(t)

    t.set_section("[24] CriticalException - 상속")
    test_critical_inheritance(t)

    # 5. 모듈 메타데이터
    t.set_section("[25] 모듈 메타데이터 검증")
    test_module_metadata(t)

    t.set_section("[26] __all__ export import 검증")
    test_all_exports_importable(t)

    # 6. 엣지 케이스
    t.set_section("[27] 엣지 케이스")
    test_edge_cases(t)

    sys.exit(0 if t.summary() else 1)


if __name__ == "__main__":
    main()
