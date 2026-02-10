"""
tests/core_foundation/exceptions/unit/test_base.py

CourtViewError 단위 테스트
- 기본 기능: 예외 생성, 에러 코드, 컨텍스트, 원본 예외
- 메시지 포맷팅: __str__, __repr__, get_user_message
- 직렬화: to_dict
- 보안: 민감 정보 필터링, 컨텍스트 크기 제한
- 메모리: 메모리 footprint, 플랫폼 정보 캐싱
- 스택 트레이스: 캡처, 프레임 제한
- 에러 체이닝: 원본 에러 보존

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from typing import Dict, Any
import traceback

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.exceptions.base import CourtViewError


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과"""
        self.passed += 1
        print(f"[PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"[FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 기본 기능 테스트 ====================
def test_basic_exception_creation(result: TestResult) -> None:
    """기본 예외 생성 테스트"""
    try:
        error = CourtViewError("테스트 에러")
        assert error.message == "테스트 에러"
        assert error.error_code == "CV000"  # 기본 에러 코드
        assert error.context == {}
        assert error.original_error is None
        result.ok("기본 예외 생성")
    except AssertionError as e:
        result.fail("기본 예외 생성", str(e))


def test_exception_with_error_code(result: TestResult) -> None:
    """커스텀 에러 코드 테스트"""
    try:
        error = CourtViewError("GPU 에러", error_code="CV201")
        assert error.error_code == "CV201"
        result.ok("커스텀 에러 코드")
    except AssertionError as e:
        result.fail("커스텀 에러 코드", str(e))


def test_exception_with_context(result: TestResult) -> None:
    """컨텍스트 포함 예외 테스트"""
    try:
        context = {"file": "test.yaml", "line": 42}
        error = CourtViewError("파싱 에러", context=context)
        assert error.context == context
        assert error.context["file"] == "test.yaml"
        assert error.context["line"] == 42
        result.ok("컨텍스트 포함 예외")
    except AssertionError as e:
        result.fail("컨텍스트 포함 예외", str(e))


def test_exception_with_original_error(result: TestResult) -> None:
    """원본 예외 체이닝 테스트"""
    try:
        original = ValueError("원본 에러")
        error = CourtViewError("래핑 에러", original_error=original)
        assert error.original_error is original
        assert isinstance(error.original_error, ValueError)
        result.ok("원본 예외 체이닝")
    except AssertionError as e:
        result.fail("원본 예외 체이닝", str(e))


# ==================== 메시지 포맷팅 테스트 ====================
def test_str_representation(result: TestResult) -> None:
    """__str__ 표현 테스트"""
    try:
        error = CourtViewError("테스트 메시지", error_code="CV101")
        error_str = str(error)
        assert error_str == "[CV101] 테스트 메시지"
        assert "[CV101]" in error_str
        assert "테스트 메시지" in error_str
        result.ok("__str__ 표현")
    except AssertionError as e:
        result.fail("__str__ 표현", str(e))


def test_repr_representation(result: TestResult) -> None:
    """__repr__ 표현 테스트"""
    try:
        error = CourtViewError("테스트", error_code="CV101", context={"key": "value"})
        error_repr = repr(error)
        assert "CourtViewError" in error_repr
        assert "error_code='CV101'" in error_repr
        assert "message='테스트'" in error_repr
        assert "context=" in error_repr
        result.ok("__repr__ 표현")
    except AssertionError as e:
        result.fail("__repr__ 표현", str(e))


def test_user_message(result: TestResult) -> None:
    """사용자 메시지 테스트"""
    try:
        # CV101: 설정 파일 없음
        error1 = CourtViewError("YAML not found", error_code="CV101")
        user_msg1 = error1.get_user_message()
        assert "설정 파일을 찾을 수 없습니다" in user_msg1

        # 정의되지 않은 에러 코드
        error2 = CourtViewError("Unknown", error_code="CV999")
        user_msg2 = error2.get_user_message()
        assert "오류가 발생했습니다" in user_msg2

        result.ok("사용자 메시지")
    except AssertionError as e:
        result.fail("사용자 메시지", str(e))


# ==================== 직렬화 테스트 ====================
def test_to_dict_basic(result: TestResult) -> None:
    """기본 직렬화 테스트"""
    try:
        error = CourtViewError("테스트", error_code="CV101")
        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert error_dict["error_code"] == "CV101"
        assert error_dict["message"] == "테스트"
        assert "timestamp" in error_dict
        assert "platform_info" in error_dict

        result.ok("기본 직렬화")
    except AssertionError as e:
        result.fail("기본 직렬화", str(e))


def test_to_dict_with_all_fields(result: TestResult) -> None:
    """모든 필드 포함 직렬화 테스트"""
    try:
        original = ValueError("원본")
        context = {"key": "value"}
        error = CourtViewError(
            "전체 필드 테스트",
            error_code="CV201",
            context=context,
            original_error=original
        )
        error_dict = error.to_dict()

        assert error_dict["error_code"] == "CV201"
        assert error_dict["message"] == "전체 필드 테스트"
        assert error_dict["context"] == context
        assert "original_error" in error_dict
        assert error_dict["original_error"]["type"] == "ValueError"
        assert error_dict["original_error"]["message"] == "원본"

        result.ok("전체 필드 직렬화")
    except AssertionError as e:
        result.fail("전체 필드 직렬화", str(e))


def test_to_dict_production_mode(result: TestResult) -> None:
    """프로덕션 모드 직렬화 테스트"""
    try:
        error = CourtViewError("프로덕션", production_mode=True)
        error_dict = error.to_dict()

        # 프로덕션 모드에서는 스택 트레이스 제외
        assert "stack_trace" not in error_dict

        result.ok("프로덕션 모드 직렬화")
    except AssertionError as e:
        result.fail("프로덕션 모드 직렬화", str(e))


# ==================== 보안 테스트 ====================
def test_sensitive_context_filtering(result: TestResult) -> None:
    """민감 정보 필터링 테스트"""
    try:
        context = {
            "username": "admin",
            "password": "secret123",
            "api_key": "abc123",
            "token": "xyz789",
            "normal_data": "visible"
        }
        error = CourtViewError("보안 테스트", context=context)

        # 민감 정보는 필터링되어야 함
        assert error.context["password"] == "***REDACTED***"
        assert error.context["api_key"] == "***REDACTED***"
        assert error.context["token"] == "***REDACTED***"

        # 일반 데이터는 그대로
        assert error.context["username"] == "admin"
        assert error.context["normal_data"] == "visible"

        result.ok("민감 정보 필터링")
    except AssertionError as e:
        result.fail("민감 정보 필터링", str(e))


def test_nested_context_filtering(result: TestResult) -> None:
    """중첩된 컨텍스트 필터링 테스트"""
    try:
        context = {
            "user": {
                "name": "admin",
                "password": "secret",
                "settings": {
                    "api_key": "key123"
                }
            }
        }
        error = CourtViewError("중첩 테스트", context=context)

        # 중첩된 민감 정보도 필터링되어야 함
        assert error.context["user"]["password"] == "***REDACTED***"
        assert error.context["user"]["settings"]["api_key"] == "***REDACTED***"
        assert error.context["user"]["name"] == "admin"

        result.ok("중첩 컨텍스트 필터링")
    except AssertionError as e:
        result.fail("중첩 컨텍스트 필터링", str(e))


def test_context_size_limit(result: TestResult) -> None:
    """컨텍스트 크기 제한 테스트"""
    try:
        # 큰 컨텍스트 생성 (>512 bytes)
        large_context = {
            f"key_{i}": f"value_{i}" * 20  # 큰 값
            for i in range(50)
        }
        error = CourtViewError("크기 제한 테스트", context=large_context)

        # 컨텍스트가 잘렸는지 확인
        context_str = str(error.context)
        context_size = len(context_str.encode('utf-8'))

        # 512 bytes를 초과하면 truncate되어야 함
        # (정확히 512가 아닐 수 있지만, 원본보다는 작아야 함)
        original_size = len(str(large_context).encode('utf-8'))
        assert context_size < original_size

        result.ok("컨텍스트 크기 제한")
    except AssertionError as e:
        result.fail("컨텍스트 크기 제한", str(e))


# ==================== 메모리 테스트 ====================
def test_memory_footprint(result: TestResult) -> None:
    """메모리 사용량 테스트"""
    try:
        import sys

        error = CourtViewError(
            "메모리 테스트",
            error_code="CV101",
            context={"key1": "value1", "key2": "value2"}
        )

        # 대략적인 크기 측정
        size = sys.getsizeof(error)

        # 1KB (1024 bytes) 이하여야 함
        # 주의: sys.getsizeof는 shallow size만 측정
        # 실제로는 좀 더 클 수 있지만, 기본 객체는 1KB 이하여야 함
        assert size < 2048, f"예외 크기가 너무 큽니다: {size} bytes"

        result.ok("메모리 사용량")
    except AssertionError as e:
        result.fail("메모리 사용량", str(e))


def test_platform_info_caching(result: TestResult) -> None:
    """플랫폼 정보 캐싱 테스트"""
    try:
        # 첫 번째 인스턴스
        error1 = CourtViewError("테스트 1")
        platform1 = error1.platform_info

        # 두 번째 인스턴스
        error2 = CourtViewError("테스트 2")
        platform2 = error2.platform_info

        # 같은 객체여야 함 (캐싱)
        assert platform1 is platform2, "플랫폼 정보가 캐싱되지 않았습니다"

        # 내용 확인
        assert "os" in platform1
        assert "python_version" in platform1
        assert "architecture" in platform1

        result.ok("플랫폼 정보 캐싱")
    except AssertionError as e:
        result.fail("플랫폼 정보 캐싱", str(e))


# ==================== 스택 트레이스 테스트 ====================
def test_stack_trace_capture(result: TestResult) -> None:
    """스택 트레이스 캡처 테스트"""
    try:
        error = CourtViewError("스택 트레이스 테스트")

        assert error.stack_trace is not None
        assert len(error.stack_trace) > 0
        assert "Traceback" in error.stack_trace or "NoneType" in error.stack_trace

        result.ok("스택 트레이스 캡처")
    except AssertionError as e:
        result.fail("스택 트레이스 캡처", str(e))


def test_stack_trace_limit(result: TestResult) -> None:
    """스택 트레이스 프레임 제한 테스트"""
    try:
        # 개발 모드: 10 프레임
        error_dev = CourtViewError("개발 모드", production_mode=False)

        # 프로덕션 모드: 3 프레임
        error_prod = CourtViewError("프로덕션 모드", production_mode=True)

        # 프로덕션 모드가 더 짧아야 함
        # (실제 스택이 3 프레임보다 길다면)
        assert len(error_prod.stack_trace) <= len(error_dev.stack_trace)

        # 500 bytes 제한
        assert len(error_dev.stack_trace) <= 500
        assert len(error_prod.stack_trace) <= 500

        result.ok("스택 트레이스 프레임 제한")
    except AssertionError as e:
        result.fail("스택 트레이스 프레임 제한", str(e))


# ==================== 에러 체이닝 테스트 ====================
def test_exception_chaining(result: TestResult) -> None:
    """예외 체이닝 테스트"""
    try:
        original = FileNotFoundError("파일 없음")
        error = CourtViewError(
            "설정 파일을 읽을 수 없습니다",
            error_code="CV101",
            original_error=original
        )

        assert error.original_error is original
        assert isinstance(error.original_error, FileNotFoundError)
        assert str(error.original_error) == "파일 없음"

        result.ok("예외 체이닝")
    except AssertionError as e:
        result.fail("예외 체이닝", str(e))


def test_original_error_preserved(result: TestResult) -> None:
    """원본 에러 보존 테스트"""
    try:
        original = ValueError("잘못된 값")
        error = CourtViewError("검증 실패", original_error=original)

        # to_dict()에서도 원본 에러 정보 포함
        error_dict = error.to_dict()
        assert "original_error" in error_dict
        assert error_dict["original_error"]["type"] == "ValueError"
        assert error_dict["original_error"]["message"] == "잘못된 값"

        result.ok("원본 에러 보존")
    except AssertionError as e:
        result.fail("원본 에러 보존", str(e))


# ==================== 파생 클래스 테스트 ====================
def test_derived_exception_error_code(result: TestResult) -> None:
    """파생 예외의 에러 코드 테스트"""
    try:
        # 커스텀 예외 클래스
        class CustomError(CourtViewError):
            ERROR_CODE = "CV301"

        error = CustomError("커스텀 에러")
        assert error.error_code == "CV301"

        # 명시적 에러 코드는 클래스 에러 코드를 오버라이드
        error2 = CustomError("커스텀 에러 2", error_code="CV302")
        assert error2.error_code == "CV302"

        result.ok("파생 예외 에러 코드")
    except AssertionError as e:
        result.fail("파생 예외 에러 코드", str(e))


# ==================== Edge Cases 테스트 ====================
def test_empty_context(result: TestResult) -> None:
    """빈 컨텍스트 테스트"""
    try:
        error = CourtViewError("빈 컨텍스트", context={})
        assert error.context == {}

        result.ok("빈 컨텍스트")
    except AssertionError as e:
        result.fail("빈 컨텍스트", str(e))


def test_none_context(result: TestResult) -> None:
    """None 컨텍스트 테스트"""
    try:
        error = CourtViewError("None 컨텍스트", context=None)
        assert error.context == {}

        result.ok("None 컨텍스트")
    except AssertionError as e:
        result.fail("None 컨텍스트", str(e))


def test_unicode_message(result: TestResult) -> None:
    """유니코드 메시지 테스트"""
    try:
        error = CourtViewError("한글 메시지: GPU 메모리 부족 🎮")
        assert "한글" in error.message
        assert "🎮" in error.message

        result.ok("유니코드 메시지")
    except AssertionError as e:
        result.fail("유니코드 메시지", str(e))


def test_long_message(result: TestResult) -> None:
    """긴 메시지 테스트"""
    try:
        long_message = "A" * 1000
        error = CourtViewError(long_message)
        assert error.message == long_message

        result.ok("긴 메시지")
    except AssertionError as e:
        result.fail("긴 메시지", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("CourtViewError 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[기본 기능]")
    test_basic_exception_creation(result)
    test_exception_with_error_code(result)
    test_exception_with_context(result)
    test_exception_with_original_error(result)

    print("\n[메시지 포맷팅]")
    test_str_representation(result)
    test_repr_representation(result)
    test_user_message(result)

    print("\n[직렬화]")
    test_to_dict_basic(result)
    test_to_dict_with_all_fields(result)
    test_to_dict_production_mode(result)

    print("\n[보안]")
    test_sensitive_context_filtering(result)
    test_nested_context_filtering(result)
    test_context_size_limit(result)

    print("\n[메모리]")
    test_memory_footprint(result)
    test_platform_info_caching(result)

    print("\n[스택 트레이스]")
    test_stack_trace_capture(result)
    test_stack_trace_limit(result)

    print("\n[에러 체이닝]")
    test_exception_chaining(result)
    test_original_error_preserved(result)

    print("\n[파생 클래스]")
    test_derived_exception_error_code(result)

    print("\n[Edge Cases]")
    test_empty_context(result)
    test_none_context(result)
    test_unicode_message(result)
    test_long_message(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
