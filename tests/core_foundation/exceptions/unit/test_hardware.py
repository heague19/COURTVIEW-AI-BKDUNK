"""
tests/core_foundation/exceptions/unit/test_hardware.py

GPUError, CameraError, InsufficientMemoryError 단위 테스트
- GPUError: GPU 관련 예외 (CV201)
- CameraError: 카메라 관련 예외 (CV202)
- InsufficientMemoryError: 메모리 부족 예외 (CV901)

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.exceptions.hardware import (
    GPUError,
    CameraError,
    InsufficientMemoryError
)


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


# ==================== GPUError 테스트 ====================
def test_gpu_error_basic_creation(result: TestResult) -> None:
    """GPUError 기본 생성 테스트"""
    try:
        error = GPUError("GPU 에러")
        assert error.message == "GPU 에러"
        assert error.error_code == "CV201"
        result.ok("GPUError 기본 생성")
    except AssertionError as e:
        result.fail("GPUError 기본 생성", str(e))


def test_gpu_error_with_gpu_id(result: TestResult) -> None:
    """GPUError gpu_id 파라미터 테스트"""
    try:
        error = GPUError("GPU 0 초기화 실패", gpu_id=0)
        assert error.context["gpu_id"] == 0
        result.ok("GPUError gpu_id 파라미터")
    except AssertionError as e:
        result.fail("GPUError gpu_id 파라미터", str(e))


def test_gpu_error_with_memory_info(result: TestResult) -> None:
    """GPUError 메모리 정보 파라미터 테스트"""
    try:
        error = GPUError(
            "GPU 메모리 부족",
            gpu_id=0,
            required_memory_mb=8000,
            available_memory_mb=4000
        )
        assert error.context["gpu_id"] == 0
        assert error.context["required_memory_mb"] == 8000
        assert error.context["available_memory_mb"] == 4000
        result.ok("GPUError 메모리 정보 파라미터")
    except AssertionError as e:
        result.fail("GPUError 메모리 정보 파라미터", str(e))


def test_gpu_error_excludes_none_values(result: TestResult) -> None:
    """GPUError None 값 제외 테스트"""
    try:
        error = GPUError("GPU 에러", gpu_id=None)
        assert "gpu_id" not in error.context
        result.ok("GPUError None 값 제외")
    except AssertionError as e:
        result.fail("GPUError None 값 제외", str(e))


def test_gpu_error_user_message(result: TestResult) -> None:
    """GPUError 사용자 메시지 테스트"""
    try:
        error = GPUError("CUDA 에러")
        user_msg = error.get_user_message()
        assert "GPU를 사용할 수 없습니다" in user_msg
        result.ok("GPUError 사용자 메시지")
    except AssertionError as e:
        result.fail("GPUError 사용자 메시지", str(e))


# ==================== CameraError 테스트 ====================
def test_camera_error_basic_creation(result: TestResult) -> None:
    """CameraError 기본 생성 테스트"""
    try:
        error = CameraError("카메라 에러")
        assert error.message == "카메라 에러"
        assert error.error_code == "CV202"
        result.ok("CameraError 기본 생성")
    except AssertionError as e:
        result.fail("CameraError 기본 생성", str(e))


def test_camera_error_with_camera_id(result: TestResult) -> None:
    """CameraError camera_id 파라미터 테스트"""
    try:
        error = CameraError("카메라 연결 실패", camera_id=0)
        assert error.context["camera_id"] == 0
        result.ok("CameraError camera_id 파라미터")
    except AssertionError as e:
        result.fail("CameraError camera_id 파라미터", str(e))


def test_camera_error_with_camera_name(result: TestResult) -> None:
    """CameraError camera_name 파라미터 테스트"""
    try:
        error = CameraError(
            "카메라 초기화 실패",
            camera_id=0,
            camera_name="USB Camera 0"
        )
        assert error.context["camera_id"] == 0
        assert error.context["camera_name"] == "USB Camera 0"
        result.ok("CameraError camera_name 파라미터")
    except AssertionError as e:
        result.fail("CameraError camera_name 파라미터", str(e))


def test_camera_error_excludes_none_values(result: TestResult) -> None:
    """CameraError None 값 제외 테스트"""
    try:
        error = CameraError("카메라 에러", camera_id=None, camera_name=None)
        assert "camera_id" not in error.context
        assert "camera_name" not in error.context
        result.ok("CameraError None 값 제외")
    except AssertionError as e:
        result.fail("CameraError None 값 제외", str(e))


def test_camera_error_user_message(result: TestResult) -> None:
    """CameraError 사용자 메시지 테스트"""
    try:
        error = CameraError("카메라 연결 실패")
        user_msg = error.get_user_message()
        assert "카메라를 연결할 수 없습니다" in user_msg
        result.ok("CameraError 사용자 메시지")
    except AssertionError as e:
        result.fail("CameraError 사용자 메시지", str(e))


# ==================== InsufficientMemoryError 테스트 ====================
def test_memory_error_basic_creation(result: TestResult) -> None:
    """InsufficientMemoryError 기본 생성 테스트"""
    try:
        error = InsufficientMemoryError("메모리 부족")
        assert error.message == "메모리 부족"
        assert error.error_code == "CV901"
        result.ok("InsufficientMemoryError 기본 생성")
    except AssertionError as e:
        result.fail("InsufficientMemoryError 기본 생성", str(e))


def test_memory_error_with_memory_info(result: TestResult) -> None:
    """InsufficientMemoryError 메모리 정보 파라미터 테스트"""
    try:
        error = InsufficientMemoryError(
            "시스템 메모리 부족",
            required_mb=16000,
            available_mb=8000
        )
        assert error.context["required_mb"] == 16000
        assert error.context["available_mb"] == 8000
        result.ok("InsufficientMemoryError 메모리 정보 파라미터")
    except AssertionError as e:
        result.fail("InsufficientMemoryError 메모리 정보 파라미터", str(e))


def test_memory_error_memory_type_system(result: TestResult) -> None:
    """InsufficientMemoryError memory_type='system' 테스트"""
    try:
        error = InsufficientMemoryError(
            "시스템 메모리 부족",
            memory_type="system"
        )
        assert error.context["memory_type"] == "system"
        result.ok("InsufficientMemoryError memory_type='system'")
    except AssertionError as e:
        result.fail("InsufficientMemoryError memory_type='system'", str(e))


def test_memory_error_memory_type_gpu(result: TestResult) -> None:
    """InsufficientMemoryError memory_type='gpu' 테스트"""
    try:
        error = InsufficientMemoryError(
            "GPU 메모리 부족",
            memory_type="gpu"
        )
        assert error.context["memory_type"] == "gpu"
        result.ok("InsufficientMemoryError memory_type='gpu'")
    except AssertionError as e:
        result.fail("InsufficientMemoryError memory_type='gpu'", str(e))


def test_memory_error_memory_type_cache(result: TestResult) -> None:
    """InsufficientMemoryError memory_type='cache' 테스트"""
    try:
        error = InsufficientMemoryError(
            "캐시 메모리 부족",
            memory_type="cache"
        )
        assert error.context["memory_type"] == "cache"
        result.ok("InsufficientMemoryError memory_type='cache'")
    except AssertionError as e:
        result.fail("InsufficientMemoryError memory_type='cache'", str(e))


def test_memory_error_default_memory_type(result: TestResult) -> None:
    """InsufficientMemoryError 기본 memory_type 테스트"""
    try:
        error = InsufficientMemoryError("메모리 부족")
        # 기본값은 "system"
        assert error.context["memory_type"] == "system"
        result.ok("InsufficientMemoryError 기본 memory_type")
    except AssertionError as e:
        result.fail("InsufficientMemoryError 기본 memory_type", str(e))


def test_memory_error_user_message(result: TestResult) -> None:
    """InsufficientMemoryError 사용자 메시지 테스트"""
    try:
        error = InsufficientMemoryError("메모리 부족")
        user_msg = error.get_user_message()
        assert "메모리가 부족합니다" in user_msg
        result.ok("InsufficientMemoryError 사용자 메시지")
    except AssertionError as e:
        result.fail("InsufficientMemoryError 사용자 메시지", str(e))


# ==================== 통합 테스트 ====================
def test_inheritance_from_courtview_error(result: TestResult) -> None:
    """CourtViewError 상속 테스트"""
    try:
        from core_foundation.exceptions.base import CourtViewError

        gpu_error = GPUError("테스트")
        camera_error = CameraError("테스트")
        memory_error = InsufficientMemoryError("테스트")

        assert isinstance(gpu_error, CourtViewError)
        assert isinstance(camera_error, CourtViewError)
        assert isinstance(memory_error, CourtViewError)

        result.ok("CourtViewError 상속")
    except AssertionError as e:
        result.fail("CourtViewError 상속", str(e))


def test_to_dict_serialization(result: TestResult) -> None:
    """to_dict() 직렬화 테스트"""
    try:
        error = GPUError(
            "GPU 메모리 부족",
            gpu_id=0,
            required_memory_mb=8000
        )
        error_dict = error.to_dict()

        assert error_dict["error_code"] == "CV201"
        assert error_dict["message"] == "GPU 메모리 부족"
        assert error_dict["context"]["gpu_id"] == 0

        result.ok("to_dict() 직렬화")
    except AssertionError as e:
        result.fail("to_dict() 직렬화", str(e))


def test_context_merge_with_additional_fields(result: TestResult) -> None:
    """컨텍스트 병합 테스트"""
    try:
        error = GPUError(
            "GPU 에러",
            gpu_id=0,
            context={"custom_field": "custom_value"}
        )
        assert error.context["gpu_id"] == 0
        assert error.context["custom_field"] == "custom_value"
        result.ok("컨텍스트 병합")
    except AssertionError as e:
        result.fail("컨텍스트 병합", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("GPUError, CameraError, InsufficientMemoryError 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[GPUError]")
    test_gpu_error_basic_creation(result)
    test_gpu_error_with_gpu_id(result)
    test_gpu_error_with_memory_info(result)
    test_gpu_error_excludes_none_values(result)
    test_gpu_error_user_message(result)

    print("\n[CameraError]")
    test_camera_error_basic_creation(result)
    test_camera_error_with_camera_id(result)
    test_camera_error_with_camera_name(result)
    test_camera_error_excludes_none_values(result)
    test_camera_error_user_message(result)

    print("\n[InsufficientMemoryError]")
    test_memory_error_basic_creation(result)
    test_memory_error_with_memory_info(result)
    test_memory_error_memory_type_system(result)
    test_memory_error_memory_type_gpu(result)
    test_memory_error_memory_type_cache(result)
    test_memory_error_default_memory_type(result)
    test_memory_error_user_message(result)

    print("\n[통합 테스트]")
    test_inheritance_from_courtview_error(result)
    test_to_dict_serialization(result)
    test_context_merge_with_additional_fields(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
