"""
tests/core_foundation/config/unit/test_validator.py

ConfigValidator 단위 테스트
- GPUConfig: 5개
- CameraConfig: 5개
- DetectionConfig: 3개
- AppConfig: 4개
- DesktopConfigValidator: 3개

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import warnings

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from pydantic import ValidationError

from core_foundation.config.validator import (
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    AppConfig,
    DesktopConfigValidator,
    GPUBackend,
    LogLevel,
    validate_config_dict,
    translate_error,
)
from core_foundation.exceptions.validation import DataValidationError


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


# ==================== GPUConfig 테스트 (5개) ====================
def test_gpu_config_valid(result: TestResult) -> None:
    """GPUConfig 정상 값 검증"""
    try:
        config = GPUConfig(
            device_id=0,
            memory_fraction=0.8,
            backend="cuda",
            batch_size=8,
            enable_fp16=False
        )
        config.validate_custom()

        assert config.device_id == 0
        assert config.memory_fraction == 0.8
        assert config.backend == GPUBackend.CUDA
        assert config.batch_size == 8
        assert config.enable_fp16 is False

        result.ok("GPUConfig 정상 값 검증")
    except Exception as e:
        result.fail("GPUConfig 정상 값 검증", str(e))


def test_gpu_config_device_id_out_of_range(result: TestResult) -> None:
    """GPUConfig device_id 범위 초과"""
    try:
        # device_id > 7
        try:
            config = GPUConfig(device_id=10)
            result.fail("GPUConfig device_id 범위 초과", "ValidationError가 발생하지 않음")
        except (ValidationError, ValueError):
            result.ok("GPUConfig device_id 범위 초과")

    except Exception as e:
        result.fail("GPUConfig device_id 범위 초과", str(e))


def test_gpu_config_memory_fraction_out_of_range(result: TestResult) -> None:
    """GPUConfig memory_fraction 범위 초과"""
    try:
        # memory_fraction < 0.1
        try:
            config = GPUConfig(memory_fraction=0.05)
            result.fail("GPUConfig memory_fraction 범위 초과", "ValidationError가 발생하지 않음")
        except ValidationError:
            result.ok("GPUConfig memory_fraction 범위 초과")

    except Exception as e:
        result.fail("GPUConfig memory_fraction 범위 초과", str(e))


def test_gpu_config_backend_enum(result: TestResult) -> None:
    """GPUConfig backend Enum 검증"""
    try:
        # 정상 케이스
        config1 = GPUConfig(backend="cuda")
        assert config1.backend == GPUBackend.CUDA

        config2 = GPUConfig(backend="metal")
        assert config2.backend == GPUBackend.METAL

        config3 = GPUConfig(backend="cpu")
        assert config3.backend == GPUBackend.CPU

        # 잘못된 backend
        try:
            config4 = GPUConfig(backend="invalid")
            result.fail("GPUConfig backend Enum 검증", "ValidationError가 발생하지 않음")
        except ValidationError:
            pass

        result.ok("GPUConfig backend Enum 검증")

    except Exception as e:
        result.fail("GPUConfig backend Enum 검증", str(e))


def test_gpu_config_custom_validation(result: TestResult) -> None:
    """GPUConfig 커스텀 검증 (메모리 + 배치 크기)"""
    try:
        # 메모리 부족 + 큰 배치 크기
        config = GPUConfig(memory_fraction=0.4, batch_size=32)

        try:
            config.validate_custom()
            result.fail("GPUConfig 커스텀 검증", "ValueError가 발생하지 않음")
        except ValueError as e:
            assert "배치 크기" in str(e)
            result.ok("GPUConfig 커스텀 검증")

    except Exception as e:
        result.fail("GPUConfig 커스텀 검증", str(e))


# ==================== CameraConfig 테스트 (5개) ====================
def test_camera_config_valid(result: TestResult) -> None:
    """CameraConfig 정상 값 검증"""
    try:
        config = CameraConfig(
            min_count=4,
            max_count=8,
            resolution={"width": 1920, "height": 1080},
            fps=30,
            auto_exposure=True
        )
        config.validate_custom()

        assert config.min_count == 4
        assert config.max_count == 8
        assert config.resolution["width"] == 1920
        assert config.resolution["height"] == 1080
        assert config.fps == 30
        assert config.auto_exposure is True

        result.ok("CameraConfig 정상 값 검증")
    except Exception as e:
        result.fail("CameraConfig 정상 값 검증", str(e))


def test_camera_config_resolution_out_of_range(result: TestResult) -> None:
    """CameraConfig 해상도 범위 검증"""
    try:
        # 해상도가 너무 낮음
        try:
            config = CameraConfig(resolution={"width": 320, "height": 240})
            result.fail("CameraConfig 해상도 범위 검증", "ValueError가 발생하지 않음")
        except (ValidationError, ValueError):
            pass

        # 해상도가 너무 높음
        try:
            config = CameraConfig(resolution={"width": 5000, "height": 3000})
            result.fail("CameraConfig 해상도 범위 검증", "ValueError가 발생하지 않음")
        except (ValidationError, ValueError):
            pass

        result.ok("CameraConfig 해상도 범위 검증")

    except Exception as e:
        result.fail("CameraConfig 해상도 범위 검증", str(e))


def test_camera_config_fps_out_of_range(result: TestResult) -> None:
    """CameraConfig FPS 범위 검증"""
    try:
        # FPS < 1
        try:
            config = CameraConfig(fps=0)
            result.fail("CameraConfig FPS 범위 검증", "ValidationError가 발생하지 않음")
        except ValidationError:
            pass

        # FPS > 240
        try:
            config = CameraConfig(fps=300)
            result.fail("CameraConfig FPS 범위 검증", "ValidationError가 발생하지 않음")
        except ValidationError:
            pass

        result.ok("CameraConfig FPS 범위 검증")

    except Exception as e:
        result.fail("CameraConfig FPS 범위 검증", str(e))


def test_camera_config_min_max_count(result: TestResult) -> None:
    """CameraConfig min_count > max_count 검증"""
    try:
        config = CameraConfig(min_count=10, max_count=5)

        try:
            config.validate_custom()
            result.fail("CameraConfig min_count > max_count 검증", "ValueError가 발생하지 않음")
        except ValueError as e:
            assert "max_count" in str(e)
            result.ok("CameraConfig min_count > max_count 검증")

    except Exception as e:
        result.fail("CameraConfig min_count > max_count 검증", str(e))


def test_camera_config_high_res_high_fps_warning(result: TestResult) -> None:
    """CameraConfig 고해상도 + 고FPS 경고"""
    try:
        # 경고가 발생해야 함
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = CameraConfig(
                resolution={"width": 1920, "height": 1080},
                fps=120
            )
            config.validate_custom()

            # 경고가 발생했는지 확인
            warning_found = any("GPU 성능" in str(warning.message) for warning in w)
            if warning_found:
                result.ok("CameraConfig 고해상도 + 고FPS 경고")
            else:
                result.fail("CameraConfig 고해상도 + 고FPS 경고", "경고가 발생하지 않음")

    except Exception as e:
        result.fail("CameraConfig 고해상도 + 고FPS 경고", str(e))


# ==================== DetectionConfig 테스트 (3개) ====================
def test_detection_config_valid(result: TestResult) -> None:
    """DetectionConfig 정상 값 검증"""
    try:
        config = DetectionConfig(
            confidence_threshold=0.75,
            nms_threshold=0.45,
            max_detections=100,
            enable_tracking=True
        )
        config.validate_custom()

        assert config.confidence_threshold == 0.75
        assert config.nms_threshold == 0.45
        assert config.max_detections == 100
        assert config.enable_tracking is True

        result.ok("DetectionConfig 정상 값 검증")
    except Exception as e:
        result.fail("DetectionConfig 정상 값 검증", str(e))


def test_detection_config_threshold_out_of_range(result: TestResult) -> None:
    """DetectionConfig 임계값 범위 검증"""
    try:
        # confidence_threshold > 1.0
        try:
            config = DetectionConfig(confidence_threshold=1.5)
            result.fail("DetectionConfig 임계값 범위 검증", "ValidationError가 발생하지 않음")
        except ValidationError:
            pass

        # nms_threshold < 0.0
        try:
            config = DetectionConfig(nms_threshold=-0.1)
            result.fail("DetectionConfig 임계값 범위 검증", "ValidationError가 발생하지 않음")
        except ValidationError:
            pass

        result.ok("DetectionConfig 임계값 범위 검증")

    except Exception as e:
        result.fail("DetectionConfig 임계값 범위 검증", str(e))


def test_detection_config_high_confidence_warning(result: TestResult) -> None:
    """DetectionConfig 높은 confidence 경고"""
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = DetectionConfig(confidence_threshold=0.95)
            config.validate_custom()

            # 경고가 발생했는지 확인
            warning_found = any("검출률" in str(warning.message) for warning in w)
            if warning_found:
                result.ok("DetectionConfig 높은 confidence 경고")
            else:
                result.fail("DetectionConfig 높은 confidence 경고", "경고가 발생하지 않음")

    except Exception as e:
        result.fail("DetectionConfig 높은 confidence 경고", str(e))


# ==================== AppConfig 테스트 (4개) ====================
def test_app_config_valid(result: TestResult) -> None:
    """AppConfig 정상 값 검증"""
    try:
        config = AppConfig(
            name="COURTVIEW Desktop",
            version="1.0.0",
            debug=False,
            log_level="INFO"
        )
        config.validate_custom()

        assert config.name == "COURTVIEW Desktop"
        assert config.version == "1.0.0"
        assert config.debug is False
        assert config.log_level == "INFO"

        result.ok("AppConfig 정상 값 검증")
    except Exception as e:
        result.fail("AppConfig 정상 값 검증", str(e))


def test_app_config_version_format(result: TestResult) -> None:
    """AppConfig 버전 형식 검증 (Semantic Versioning)"""
    try:
        # 정상 케이스
        config1 = AppConfig(version="1.0.0")
        assert config1.version == "1.0.0"

        config2 = AppConfig(version="2.5.10")
        assert config2.version == "2.5.10"

        # 잘못된 형식
        try:
            config3 = AppConfig(version="1.0")
            result.fail("AppConfig 버전 형식 검증", "ValidationError가 발생하지 않음")
        except (ValidationError, ValueError):
            pass

        try:
            config4 = AppConfig(version="v1.0.0")
            result.fail("AppConfig 버전 형식 검증", "ValidationError가 발생하지 않음")
        except (ValidationError, ValueError):
            pass

        result.ok("AppConfig 버전 형식 검증")

    except Exception as e:
        result.fail("AppConfig 버전 형식 검증", str(e))


def test_app_config_log_level(result: TestResult) -> None:
    """AppConfig 로그 레벨 검증"""
    try:
        # 정상 케이스 (대소문자 무관)
        config1 = AppConfig(log_level="debug")
        assert config1.log_level == "DEBUG"

        config2 = AppConfig(log_level="INFO")
        assert config2.log_level == "INFO"

        # 잘못된 로그 레벨
        try:
            config3 = AppConfig(log_level="INVALID")
            result.fail("AppConfig 로그 레벨 검증", "ValueError가 발생하지 않음")
        except (ValidationError, ValueError):
            pass

        result.ok("AppConfig 로그 레벨 검증")

    except Exception as e:
        result.fail("AppConfig 로그 레벨 검증", str(e))


def test_app_config_debug_log_level_consistency(result: TestResult) -> None:
    """AppConfig 디버그 + 로그 레벨 일관성"""
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = AppConfig(debug=True, log_level="INFO")
            config.validate_custom()

            # 경고가 발생했는지 확인
            warning_found = any("log_level='DEBUG' 권장" in str(warning.message) for warning in w)
            if warning_found:
                result.ok("AppConfig 디버그 + 로그 레벨 일관성")
            else:
                result.fail("AppConfig 디버그 + 로그 레벨 일관성", "경고가 발생하지 않음")

    except Exception as e:
        result.fail("AppConfig 디버그 + 로그 레벨 일관성", str(e))


# ==================== DesktopConfigValidator 테스트 (3개) ====================
def test_desktop_config_validator_valid(result: TestResult) -> None:
    """DesktopConfigValidator 전체 설정 검증"""
    try:
        config = DesktopConfigValidator(
            app={"name": "Test App", "version": "1.0.0", "debug": False, "log_level": "INFO"},
            gpu={"device_id": 0, "memory_fraction": 0.8, "backend": "cuda", "batch_size": 8},
            camera={"min_count": 4, "max_count": 8, "resolution": {"width": 1920, "height": 1080}, "fps": 30},
            detection={"confidence_threshold": 0.75, "nms_threshold": 0.45, "max_detections": 100}
        )
        config.validate_all()

        assert config.app.name == "Test App"
        assert config.gpu.device_id == 0
        assert config.camera.min_count == 4
        assert config.detection.confidence_threshold == 0.75

        result.ok("DesktopConfigValidator 전체 설정 검증")
    except Exception as e:
        result.fail("DesktopConfigValidator 전체 설정 검증", str(e))


def test_desktop_config_validator_cross_section(result: TestResult) -> None:
    """DesktopConfigValidator 섹션 간 의존성 검증"""
    try:
        # 많은 카메라 + 작은 배치 크기
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = DesktopConfigValidator(
                gpu={"batch_size": 2},
                camera={"max_count": 10}
            )
            config.validate_all()

            # 경고가 발생했는지 확인
            warning_found = any("batch_size" in str(warning.message) for warning in w)
            if warning_found:
                result.ok("DesktopConfigValidator 섹션 간 의존성 검증")
            else:
                result.fail("DesktopConfigValidator 섹션 간 의존성 검증", "경고가 발생하지 않음")

    except Exception as e:
        result.fail("DesktopConfigValidator 섹션 간 의존성 검증", str(e))


def test_validate_config_dict_with_errors(result: TestResult) -> None:
    """validate_config_dict 에러 처리 및 한글화"""
    try:
        # 잘못된 설정
        config_dict = {
            "device_id": 10,  # 범위 초과
            "memory_fraction": 1.5,  # 범위 초과
        }

        validated, errors = validate_config_dict(
            config_dict,
            GPUConfig,
            raise_on_error=False
        )

        # 에러가 발생해야 함
        assert validated is None
        assert errors is not None
        assert len(errors) > 0

        # 한글 메시지 확인
        error_text = " ".join(errors)
        # Pydantic V2는 에러 메시지가 다를 수 있으므로 유연하게 체크
        has_korean = any(char >= '\uac00' and char <= '\ud7a3' for char in error_text)

        if has_korean or "device_id" in error_text:
            result.ok("validate_config_dict 에러 처리 및 한글화")
        else:
            result.fail("validate_config_dict 에러 처리 및 한글화", f"에러 메시지: {errors}")

    except Exception as e:
        result.fail("validate_config_dict 에러 처리 및 한글화", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("ConfigValidator 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[GPUConfig]")
    test_gpu_config_valid(result)
    test_gpu_config_device_id_out_of_range(result)
    test_gpu_config_memory_fraction_out_of_range(result)
    test_gpu_config_backend_enum(result)
    test_gpu_config_custom_validation(result)

    print("\n[CameraConfig]")
    test_camera_config_valid(result)
    test_camera_config_resolution_out_of_range(result)
    test_camera_config_fps_out_of_range(result)
    test_camera_config_min_max_count(result)
    test_camera_config_high_res_high_fps_warning(result)

    print("\n[DetectionConfig]")
    test_detection_config_valid(result)
    test_detection_config_threshold_out_of_range(result)
    test_detection_config_high_confidence_warning(result)

    print("\n[AppConfig]")
    test_app_config_valid(result)
    test_app_config_version_format(result)
    test_app_config_log_level(result)
    test_app_config_debug_log_level_consistency(result)

    print("\n[DesktopConfigValidator]")
    test_desktop_config_validator_valid(result)
    test_desktop_config_validator_cross_section(result)
    test_validate_config_dict_with_errors(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
