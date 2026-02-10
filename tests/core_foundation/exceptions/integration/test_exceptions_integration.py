"""
tests/core_foundation/exceptions/integration/test_exceptions_integration.py

Exceptions 모듈 통합 테스트
- 예외 상속 관계 및 체인
- 다중 모듈 간 예외 전파
- 에러 코드 범위 충돌 검증
- 컨텍스트 정보 전파
- 예외 직렬화 및 로깅
- 실제 사용 시나리오 검증

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import json

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.exceptions.base import CourtViewError
from core_foundation.exceptions.validation import ConfigError, DataValidationError
from core_foundation.exceptions.hardware import (
    GPUError,
    CameraError,
    InsufficientMemoryError,
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


# ==================== 예외 상속 관계 테스트 ====================
def test_exception_inheritance(result: TestResult) -> None:
    """예외 상속 관계 검증"""
    try:
        # 모든 예외가 CourtViewError를 상속
        assert issubclass(ConfigError, CourtViewError)
        assert issubclass(DataValidationError, CourtViewError)
        assert issubclass(GPUError, CourtViewError)
        assert issubclass(CameraError, CourtViewError)
        assert issubclass(InsufficientMemoryError, CourtViewError)

        # 모든 예외가 Exception을 상속
        assert issubclass(CourtViewError, Exception)

        result.ok("예외 상속 관계 검증")
    except Exception as e:
        result.fail("예외 상속 관계 검증", str(e))


def test_exception_chain(result: TestResult) -> None:
    """예외 체인 (original_error) 검증"""
    try:
        # 원본 예외 생성
        original = ValueError("원본 에러")

        # CourtViewError로 래핑
        wrapped = ConfigError(
            "설정 파일 로드 실패",
            config_file="test.yaml",
            original_error=original
        )

        # 체인 검증
        assert wrapped.original_error is original
        assert "원본 에러" in str(wrapped.original_error)
        assert wrapped.context["config_file"] == "test.yaml"

        # 다시 래핑
        double_wrapped = DataValidationError(
            "검증 실패",
            field_name="device_id",
            original_error=wrapped
        )

        # 체인 검증
        assert double_wrapped.original_error is wrapped
        assert wrapped.original_error is original

        result.ok("예외 체인 검증")
    except Exception as e:
        result.fail("예외 체인 검증", str(e))


# ==================== 에러 코드 범위 검증 ====================
def test_error_code_ranges(result: TestResult) -> None:
    """에러 코드 범위 충돌 검증"""
    try:
        # 각 모듈별 에러 코드 범위
        config_err = ConfigError("test")
        data_err = DataValidationError("test")
        gpu_err = GPUError("test")
        camera_err = CameraError("test")
        mem_err = InsufficientMemoryError("test")

        # 에러 코드 범위 검증
        assert config_err.error_code == "CV101"  # 설정: CV1xx
        assert data_err.error_code == "CV301"  # 데이터: CV3xx
        assert gpu_err.error_code == "CV201"  # GPU: CV201
        assert camera_err.error_code == "CV202"  # Camera: CV202
        assert mem_err.error_code == "CV901"  # 메모리: CV9xx

        # 모든 에러 코드가 5자리
        assert len(config_err.error_code) == 5
        assert len(data_err.error_code) == 5
        assert len(gpu_err.error_code) == 5
        assert len(camera_err.error_code) == 5
        assert len(mem_err.error_code) == 5

        # 에러 코드 중복 없음
        codes = [
            config_err.error_code,
            data_err.error_code,
            gpu_err.error_code,
            camera_err.error_code,
            mem_err.error_code
        ]
        assert len(codes) == len(set(codes))

        result.ok("에러 코드 범위 충돌 검증")
    except Exception as e:
        result.fail("에러 코드 범위 충돌 검증", str(e))


# ==================== 컨텍스트 정보 전파 ====================
def test_context_propagation(result: TestResult) -> None:
    """컨텍스트 정보 전파 검증"""
    try:
        # 복잡한 컨텍스트 생성
        gpu_error = GPUError(
            "GPU 메모리 부족",
            gpu_id=0,
            required_memory_mb=8192,
            available_memory_mb=4096
        )

        # 컨텍스트 검증
        assert gpu_error.context["gpu_id"] == 0
        assert gpu_error.context["required_memory_mb"] == 8192
        assert gpu_error.context["available_memory_mb"] == 4096

        # 컨텍스트를 포함한 래핑
        wrapped = DataValidationError(
            "검증 실패: GPU 메모리 부족",
            field_name="gpu_config",
            original_error=gpu_error
        )

        # 원본 에러의 컨텍스트 접근 가능
        assert wrapped.original_error.context["gpu_id"] == 0
        assert wrapped.context["field_name"] == "gpu_config"

        result.ok("컨텍스트 정보 전파 검증")
    except Exception as e:
        result.fail("컨텍스트 정보 전파 검증", str(e))


# ==================== 예외 직렬화 ====================
def test_exception_serialization(result: TestResult) -> None:
    """예외 직렬화 검증"""
    try:
        # 예외 생성
        error = ConfigError(
            "설정 파일 없음",
            config_file="configs/gpu.yaml",
            error_code="CV101"
        )

        # 딕셔너리로 변환
        error_dict = error.to_dict()

        # 구조 검증
        assert "message" in error_dict
        assert "error_code" in error_dict
        assert "context" in error_dict
        assert "timestamp" in error_dict

        # 값 검증
        assert error_dict["message"] == "설정 파일 없음"
        assert error_dict["error_code"] == "CV101"
        assert error_dict["context"]["config_file"] == "configs/gpu.yaml"

        # JSON 직렬화 가능
        json_str = json.dumps(error_dict)
        assert len(json_str) > 0

        # 역직렬화
        deserialized = json.loads(json_str)
        assert deserialized["message"] == "설정 파일 없음"

        result.ok("예외 직렬화 검증")
    except Exception as e:
        result.fail("예외 직렬화 검증", str(e))


# ==================== 실제 시나리오 테스트 ====================
def test_config_loading_scenario(result: TestResult) -> None:
    """실제 시나리오: 설정 로드 실패"""
    try:
        def load_config(file_path: str):
            """설정 파일 로드 시뮬레이션"""
            # 파일 없음
            if not Path(file_path).exists():
                raise ConfigError(
                    f"설정 파일을 찾을 수 없습니다: {file_path}",
                    config_file=file_path,
                    error_code="CV101"
                )

            # 검증 실패
            raise DataValidationError(
                "GPU ID 범위 초과",
                field_name="gpu.device_id",
                expected_type="int (0-7)",
                actual_value=999,
                error_code="CV303"
            )

        # 시나리오 실행
        try:
            load_config("non_existent.yaml")
        except ConfigError as e:
            assert e.error_code == "CV101"
            assert "non_existent.yaml" in str(e)
            assert e.context["config_file"] == "non_existent.yaml"

        result.ok("실제 시나리오: 설정 로드 실패")
    except Exception as e:
        result.fail("실제 시나리오: 설정 로드 실패", str(e))


def test_gpu_initialization_scenario(result: TestResult) -> None:
    """실제 시나리오: GPU 초기화 실패"""
    try:
        def initialize_gpu(device_id: int, required_mb: int):
            """GPU 초기화 시뮬레이션"""
            # GPU 메모리 부족
            raise GPUError(
                f"GPU {device_id} 메모리 부족",
                gpu_id=device_id,
                required_memory_mb=required_mb,
                available_memory_mb=4096
            )

        # 시나리오 실행
        try:
            initialize_gpu(0, 8192)
        except GPUError as e:
            assert e.error_code == "CV201"
            assert e.context["gpu_id"] == 0
            assert e.context["required_memory_mb"] == 8192
            assert e.context["available_memory_mb"] == 4096

        result.ok("실제 시나리오: GPU 초기화 실패")
    except Exception as e:
        result.fail("실제 시나리오: GPU 초기화 실패", str(e))


def test_camera_initialization_scenario(result: TestResult) -> None:
    """실제 시나리오: 카메라 초기화 실패"""
    try:
        def initialize_camera(camera_id: int, camera_name: str):
            """카메라 초기화 시뮬레이션"""
            # 카메라 연결 실패
            raise CameraError(
                f"카메라 {camera_id} 연결 실패",
                camera_id=camera_id,
                camera_name=camera_name
            )

        # 시나리오 실행
        try:
            initialize_camera(0, "USB Camera 0")
        except CameraError as e:
            assert e.error_code == "CV202"
            assert e.context["camera_id"] == 0
            assert e.context["camera_name"] == "USB Camera 0"

        result.ok("실제 시나리오: 카메라 초기화 실패")
    except Exception as e:
        result.fail("실제 시나리오: 카메라 초기화 실패", str(e))


def test_memory_allocation_scenario(result: TestResult) -> None:
    """실제 시나리오: 메모리 할당 실패"""
    try:
        def allocate_memory(size_mb: int, memory_type: str):
            """메모리 할당 시뮬레이션"""
            # 메모리 부족
            raise InsufficientMemoryError(
                f"{memory_type} 메모리 부족",
                required_mb=size_mb,
                available_mb=4096,
                memory_type=memory_type
            )

        # 시나리오 1: 시스템 메모리
        try:
            allocate_memory(16384, "system")
        except InsufficientMemoryError as e:
            assert e.error_code == "CV901"
            assert e.context["required_mb"] == 16384
            assert e.context["available_mb"] == 4096
            assert e.context["memory_type"] == "system"

        # 시나리오 2: GPU 메모리
        try:
            allocate_memory(8192, "gpu")
        except InsufficientMemoryError as e:
            assert e.error_code == "CV901"
            assert e.context["memory_type"] == "gpu"

        result.ok("실제 시나리오: 메모리 할당 실패")
    except Exception as e:
        result.fail("실제 시나리오: 메모리 할당 실패", str(e))


# ==================== 예외 캐치 및 복구 ====================
def test_exception_catch_hierarchy(result: TestResult) -> None:
    """예외 캐치 계층 구조"""
    try:
        # 특정 예외 캐치
        try:
            raise GPUError("GPU 에러", gpu_id=0)
        except GPUError as e:
            assert e.error_code == "CV201"

        # 일반 CourtViewError로 캐치
        try:
            raise DataValidationError("검증 실패", field_name="test")
        except CourtViewError as e:
            assert isinstance(e, DataValidationError)
            assert e.error_code.startswith("CV")

        # 모든 예외 캐치
        try:
            raise ConfigError("설정 오류", config_file="test.yaml")
        except Exception as e:
            assert isinstance(e, CourtViewError)
            assert hasattr(e, "error_code")

        result.ok("예외 캐치 계층 구조")
    except Exception as e:
        result.fail("예외 캐치 계층 구조", str(e))


def test_multi_module_error_propagation(result: TestResult) -> None:
    """다중 모듈 간 예외 전파"""
    try:
        # 3단계 예외 체인
        original = ValueError("잘못된 값")

        hardware_error = GPUError(
            "GPU 초기화 실패",
            gpu_id=0,
            original_error=original
        )

        config_error = ConfigError(
            "GPU 설정 로드 실패",
            config_file="gpu.yaml",
            original_error=hardware_error
        )

        # 체인 검증
        assert config_error.original_error is hardware_error
        assert hardware_error.original_error is original

        # 컨텍스트 접근
        assert config_error.context["config_file"] == "gpu.yaml"
        assert config_error.original_error.context["gpu_id"] == 0

        # 에러 코드 전파
        assert config_error.error_code == "CV101"
        assert hardware_error.error_code == "CV201"

        result.ok("다중 모듈 간 예외 전파")
    except Exception as e:
        result.fail("다중 모듈 간 예외 전파", str(e))


def test_hardware_error_combination(result: TestResult) -> None:
    """하드웨어 에러 조합 시나리오"""
    try:
        # GPU + 메모리 에러
        gpu_error = GPUError(
            "GPU 메모리 부족",
            gpu_id=0,
            required_memory_mb=8192,
            available_memory_mb=4096
        )

        mem_error = InsufficientMemoryError(
            "시스템 메모리 부족",
            required_mb=16384,
            available_mb=8192,
            memory_type="system",
            original_error=gpu_error
        )

        # 체인 검증
        assert mem_error.original_error is gpu_error
        assert mem_error.error_code == "CV901"
        assert gpu_error.error_code == "CV201"

        # 컨텍스트 검증
        assert mem_error.context["memory_type"] == "system"
        assert mem_error.original_error.context["gpu_id"] == 0

        result.ok("하드웨어 에러 조합 시나리오")
    except Exception as e:
        result.fail("하드웨어 에러 조합 시나리오", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 통합 테스트 실행"""
    print("="*60)
    print("Exceptions 모듈 통합 테스트")
    print("="*60)

    result = TestResult()

    print("\n[예외 구조]")
    test_exception_inheritance(result)
    test_exception_chain(result)
    test_error_code_ranges(result)

    print("\n[컨텍스트 및 직렬화]")
    test_context_propagation(result)
    test_exception_serialization(result)

    print("\n[실제 시나리오]")
    test_config_loading_scenario(result)
    test_gpu_initialization_scenario(result)
    test_camera_initialization_scenario(result)
    test_memory_allocation_scenario(result)

    print("\n[예외 처리 패턴]")
    test_exception_catch_hierarchy(result)
    test_multi_module_error_propagation(result)
    test_hardware_error_combination(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
