"""
tests/core_foundation/exceptions/unit/test_validation.py

ConfigError, DataValidationError 단위 테스트
- ConfigError: 설정 파일 관련 예외 (CV101~CV103)
- DataValidationError: 데이터 검증 예외 (CV301~CV303)

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.exceptions.validation import ConfigError, DataValidationError


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


# ==================== ConfigError 테스트 ====================
def test_config_error_basic_creation(result: TestResult) -> None:
    """ConfigError 기본 생성 테스트"""
    try:
        error = ConfigError("설정 파일 에러")
        assert error.message == "설정 파일 에러"
        assert error.error_code == "CV101"
        result.ok("ConfigError 기본 생성")
    except AssertionError as e:
        result.fail("ConfigError 기본 생성", str(e))


def test_config_error_with_config_file(result: TestResult) -> None:
    """ConfigError config_file 파라미터 테스트"""
    try:
        error = ConfigError(
            "파일을 찾을 수 없습니다",
            config_file="configs/gpu.yaml"
        )
        assert error.context["config_file"] == "configs/gpu.yaml"
        result.ok("ConfigError config_file 파라미터")
    except AssertionError as e:
        result.fail("ConfigError config_file 파라미터", str(e))


def test_config_error_code_override(result: TestResult) -> None:
    """ConfigError 에러 코드 오버라이드 테스트"""
    try:
        # CV101 (기본)
        error1 = ConfigError("파일 없음")
        assert error1.error_code == "CV101"

        # CV102 (파싱 실패)
        error2 = ConfigError("파싱 실패", error_code="CV102")
        assert error2.error_code == "CV102"

        # CV103 (검증 실패)
        error3 = ConfigError("검증 실패", error_code="CV103")
        assert error3.error_code == "CV103"

        result.ok("ConfigError 에러 코드 오버라이드")
    except AssertionError as e:
        result.fail("ConfigError 에러 코드 오버라이드", str(e))


def test_config_error_with_original_error(result: TestResult) -> None:
    """ConfigError 원본 예외 체이닝 테스트"""
    try:
        original = FileNotFoundError("파일 없음")
        error = ConfigError(
            "설정 파일 로드 실패",
            config_file="test.yaml",
            original_error=original
        )
        assert error.original_error is original
        result.ok("ConfigError 원본 예외 체이닝")
    except AssertionError as e:
        result.fail("ConfigError 원본 예외 체이닝", str(e))


def test_config_error_context_merge(result: TestResult) -> None:
    """ConfigError 컨텍스트 병합 테스트"""
    try:
        error = ConfigError(
            "YAML 파싱 실패",
            config_file="gpu.yaml",
            context={"line": 15, "column": 3}
        )
        assert error.context["config_file"] == "gpu.yaml"
        assert error.context["line"] == 15
        assert error.context["column"] == 3
        result.ok("ConfigError 컨텍스트 병합")
    except AssertionError as e:
        result.fail("ConfigError 컨텍스트 병합", str(e))


def test_config_error_user_message(result: TestResult) -> None:
    """ConfigError 사용자 메시지 테스트"""
    try:
        error = ConfigError("YAML 파일 없음", error_code="CV101")
        user_msg = error.get_user_message()
        assert "설정 파일을 찾을 수 없습니다" in user_msg
        result.ok("ConfigError 사용자 메시지")
    except AssertionError as e:
        result.fail("ConfigError 사용자 메시지", str(e))


# ==================== DataValidationError 테스트 ====================
def test_data_validation_error_basic_creation(result: TestResult) -> None:
    """DataValidationError 기본 생성 테스트"""
    try:
        error = DataValidationError("데이터 검증 실패")
        assert error.message == "데이터 검증 실패"
        assert error.error_code == "CV301"
        result.ok("DataValidationError 기본 생성")
    except AssertionError as e:
        result.fail("DataValidationError 기본 생성", str(e))


def test_data_validation_error_with_field_info(result: TestResult) -> None:
    """DataValidationError field_name 파라미터 테스트"""
    try:
        error = DataValidationError(
            "타입 불일치",
            field_name="gpu_id",
            expected_type="int",
            actual_value="invalid"
        )
        assert error.context["field_name"] == "gpu_id"
        assert error.context["expected_type"] == "int"
        assert error.context["actual_value"] == "invalid"
        result.ok("DataValidationError field_name 파라미터")
    except AssertionError as e:
        result.fail("DataValidationError field_name 파라미터", str(e))


def test_data_validation_error_code_override(result: TestResult) -> None:
    """DataValidationError 에러 코드 오버라이드 테스트"""
    try:
        # CV301 (기본)
        error1 = DataValidationError("검증 실패")
        assert error1.error_code == "CV301"

        # CV302 (형식 오류)
        error2 = DataValidationError("형식 오류", error_code="CV302")
        assert error2.error_code == "CV302"

        # CV303 (범위 초과)
        error3 = DataValidationError("범위 초과", error_code="CV303")
        assert error3.error_code == "CV303"

        result.ok("DataValidationError 에러 코드 오버라이드")
    except AssertionError as e:
        result.fail("DataValidationError 에러 코드 오버라이드", str(e))


def test_data_validation_error_actual_value_truncation(result: TestResult) -> None:
    """DataValidationError actual_value 크기 제한 테스트"""
    try:
        # 100자 초과 값
        long_value = "A" * 150
        error = DataValidationError(
            "값이 너무 깁니다",
            field_name="data",
            actual_value=long_value
        )
        # 100자로 제한되어야 함 (+ "..." 추가)
        assert len(error.context["actual_value"]) == 103  # 100 + "..."
        assert error.context["actual_value"].endswith("...")
        result.ok("DataValidationError actual_value 크기 제한")
    except AssertionError as e:
        result.fail("DataValidationError actual_value 크기 제한", str(e))


def test_data_validation_error_with_none_values(result: TestResult) -> None:
    """DataValidationError None 값 처리 테스트"""
    try:
        error = DataValidationError(
            "필드 누락",
            field_name=None,
            expected_type=None,
            actual_value=None
        )
        # None 값은 컨텍스트에 추가되지 않아야 함
        assert "field_name" not in error.context
        assert "expected_type" not in error.context
        assert "actual_value" not in error.context
        result.ok("DataValidationError None 값 처리")
    except AssertionError as e:
        result.fail("DataValidationError None 값 처리", str(e))


def test_data_validation_error_with_numeric_value(result: TestResult) -> None:
    """DataValidationError 숫자 값 처리 테스트"""
    try:
        error = DataValidationError(
            "범위 초과",
            field_name="fps",
            expected_type="int (1~240)",
            actual_value=500
        )
        assert error.context["actual_value"] == "500"
        result.ok("DataValidationError 숫자 값 처리")
    except AssertionError as e:
        result.fail("DataValidationError 숫자 값 처리", str(e))


def test_data_validation_error_context_merge(result: TestResult) -> None:
    """DataValidationError 컨텍스트 병합 테스트"""
    try:
        error = DataValidationError(
            "검증 실패",
            field_name="test_field",
            context={"custom_key": "custom_value"}
        )
        assert error.context["field_name"] == "test_field"
        assert error.context["custom_key"] == "custom_value"
        result.ok("DataValidationError 컨텍스트 병합")
    except AssertionError as e:
        result.fail("DataValidationError 컨텍스트 병합", str(e))


# ==================== 통합 테스트 ====================
def test_inheritance_from_courtview_error(result: TestResult) -> None:
    """CourtViewError 상속 테스트"""
    try:
        from core_foundation.exceptions.base import CourtViewError

        config_error = ConfigError("테스트")
        data_error = DataValidationError("테스트")

        assert isinstance(config_error, CourtViewError)
        assert isinstance(data_error, CourtViewError)

        result.ok("CourtViewError 상속")
    except AssertionError as e:
        result.fail("CourtViewError 상속", str(e))


def test_to_dict_serialization(result: TestResult) -> None:
    """to_dict() 직렬화 테스트"""
    try:
        error = ConfigError(
            "설정 에러",
            config_file="test.yaml"
        )
        error_dict = error.to_dict()

        assert error_dict["error_code"] == "CV101"
        assert error_dict["message"] == "설정 에러"
        assert error_dict["context"]["config_file"] == "test.yaml"

        result.ok("to_dict() 직렬화")
    except AssertionError as e:
        result.fail("to_dict() 직렬화", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("ConfigError, DataValidationError 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[ConfigError]")
    test_config_error_basic_creation(result)
    test_config_error_with_config_file(result)
    test_config_error_code_override(result)
    test_config_error_with_original_error(result)
    test_config_error_context_merge(result)
    test_config_error_user_message(result)

    print("\n[DataValidationError]")
    test_data_validation_error_basic_creation(result)
    test_data_validation_error_with_field_info(result)
    test_data_validation_error_code_override(result)
    test_data_validation_error_actual_value_truncation(result)
    test_data_validation_error_with_none_values(result)
    test_data_validation_error_with_numeric_value(result)
    test_data_validation_error_context_merge(result)

    print("\n[통합 테스트]")
    test_inheritance_from_courtview_error(result)
    test_to_dict_serialization(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
