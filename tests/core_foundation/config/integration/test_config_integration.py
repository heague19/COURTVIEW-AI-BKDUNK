"""
tests/core_foundation/config/integration/test_config_integration.py

Config 모듈 통합 테스트
- Loader + Validator + Settings 전체 플로우
- 환경별 설정 로드 및 병합
- 환경 변수 오버라이드
- 에러 처리 및 복구
- 멀티스레드 안전성

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import threading
import os

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    DesktopConfigValidator,
    validate_config_dict,
    validate_config_file,
    GPUConfig,
)
from core_foundation.config.settings import DesktopSettings
from core_foundation.exceptions.validation import ConfigError, DataValidationError


# 테스트 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


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


# ==================== 통합 테스트 (5개) ====================
def test_full_pipeline_dev(result: TestResult) -> None:
    """전체 파이프라인: dev 환경"""
    try:
        # Step 1: Loader로 YAML 로드
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        base_config = loader.load_yaml("base.yaml")
        env_config = loader.load_yaml("env_dev.yaml")

        # Step 2: 병합
        merged = loader.merge_configs(base_config, env_config)

        # Step 3: Validator로 검증
        validated = DesktopConfigValidator(**merged)
        validated.validate_all()

        # Step 4: Settings로 전역 설정
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="dev",
            reload=True
        )

        # Step 5: 검증
        assert settings.environment == "dev"
        assert settings.app.debug is True
        assert settings.app.log_level == "DEBUG"
        assert settings.gpu.batch_size == 4
        assert settings.camera.min_count == 1

        result.ok("전체 파이프라인: dev 환경")
    except Exception as e:
        result.fail("전체 파이프라인: dev 환경", str(e))


def test_full_pipeline_prod(result: TestResult) -> None:
    """전체 파이프라인: prod 환경"""
    try:
        # Step 1: Loader로 YAML 로드
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        base_config = loader.load_yaml("base.yaml")
        env_config = loader.load_yaml("env_prod.yaml")

        # Step 2: 병합
        merged = loader.merge_configs(base_config, env_config)

        # Step 3: Validator로 검증
        validated = DesktopConfigValidator(**merged)
        validated.validate_all()

        # Step 4: Settings로 전역 설정
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="prod",
            reload=True
        )

        # Step 5: 검증
        assert settings.environment == "prod"
        assert settings.app.debug is False
        assert settings.app.log_level == "WARNING"
        assert settings.gpu.memory_fraction == 0.9
        assert settings.gpu.batch_size == 16

        result.ok("전체 파이프라인: prod 환경")
    except Exception as e:
        result.fail("전체 파이프라인: prod 환경", str(e))


def test_config_merge_priority(result: TestResult) -> None:
    """설정 병합 우선순위 검증"""
    try:
        # Loader로 설정 병합
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        base_config = loader.load_yaml("base.yaml")
        dev_config = loader.load_yaml("env_dev.yaml")
        prod_config = loader.load_yaml("env_prod.yaml")

        # dev 병합 (base < dev)
        dev_merged = loader.merge_configs(base_config, dev_config)
        assert dev_merged["gpu"]["batch_size"] == 4  # dev 값
        assert dev_merged["app"]["debug"] is True  # dev 값
        assert dev_merged["gpu"]["memory_fraction"] == 0.8  # base 값 (dev에 없음)

        # prod 병합 (base < prod)
        prod_merged = loader.merge_configs(base_config, prod_config)
        assert prod_merged["gpu"]["batch_size"] == 16  # prod 값
        assert prod_merged["app"]["debug"] is False  # prod 값
        assert prod_merged["camera"]["min_count"] == 4  # base 값 (prod에 없음)

        result.ok("설정 병합 우선순위 검증")
    except Exception as e:
        result.fail("설정 병합 우선순위 검증", str(e))


def test_error_handling_invalid_yaml(result: TestResult) -> None:
    """에러 처리: 잘못된 YAML"""
    try:
        # 잘못된 YAML 파일 생성
        invalid_yaml = FIXTURES_DIR / "invalid.yaml"
        with open(invalid_yaml, "w") as f:
            f.write("invalid: yaml: content: [unclosed")

        # Loader로 로드 시도
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        try:
            loader.load_yaml("invalid.yaml")
            result.fail("에러 처리: 잘못된 YAML", "ConfigError가 발생하지 않음")
        except ConfigError as e:
            assert "CV102" in str(e) or "parsing" in str(e).lower()
            result.ok("에러 처리: 잘못된 YAML")

        # 파일 삭제
        invalid_yaml.unlink()

    except Exception as e:
        result.fail("에러 처리: 잘못된 YAML", str(e))


def test_error_handling_invalid_config(result: TestResult) -> None:
    """에러 처리: 잘못된 설정값"""
    try:
        # 잘못된 설정 딕셔너리
        invalid_config = {
            "app": {"name": "Test", "version": "1.0.0"},
            "gpu": {"device_id": 999},  # 범위 초과 (0-7)
            "camera": {"min_count": 4, "max_count": 8},
            "detection": {"confidence_threshold": 0.75}
        }

        # Validator로 검증 시도
        try:
            validated = DesktopConfigValidator(**invalid_config)
            validated.validate_all()
            result.fail("에러 처리: 잘못된 설정값", "검증 에러가 발생하지 않음")
        except Exception as e:
            # Pydantic ValidationError 또는 DataValidationError
            assert "device_id" in str(e) or "999" in str(e) or "범위" in str(e)
            result.ok("에러 처리: 잘못된 설정값")

    except Exception as e:
        result.fail("에러 처리: 잘못된 설정값", str(e))


def test_multithreaded_settings_access(result: TestResult) -> None:
    """멀티스레드 설정 접근"""
    try:
        # Settings 인스턴스 생성
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        results = []
        errors = []

        def access_settings():
            try:
                # 100번 접근
                for _ in range(100):
                    device_id = settings.gpu.device_id
                    app_name = settings.app.name
                    min_count = settings.camera.min_count

                    # 값 검증
                    assert isinstance(device_id, int)
                    assert isinstance(app_name, str)
                    assert isinstance(min_count, int)

                results.append(True)
            except Exception as e:
                errors.append(str(e))
                results.append(False)

        # 10개 스레드 동시 접근
        threads = [threading.Thread(target=access_settings) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # 모든 스레드 성공 확인
        assert all(results), f"일부 스레드 실패: {errors}"

        result.ok("멀티스레드 설정 접근")
    except Exception as e:
        result.fail("멀티스레드 설정 접근", str(e))


def test_config_reload_consistency(result: TestResult) -> None:
    """설정 리로드 일관성"""
    try:
        # Settings 인스턴스 생성 (test 환경)
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 초기 값 확인
        initial_batch_size = settings.gpu.batch_size
        assert initial_batch_size == 2  # test 환경

        # 환경 변경 후 리로드
        settings._environment = "dev"
        settings.reload()

        # dev 환경 값 확인
        assert settings.environment == "dev"
        assert settings.gpu.batch_size == 4  # dev 환경

        # 다시 test로 리로드
        settings._environment = "test"
        settings.reload()

        # test 환경 값 복원 확인
        assert settings.environment == "test"
        assert settings.gpu.batch_size == 2

        result.ok("설정 리로드 일관성")
    except Exception as e:
        result.fail("설정 리로드 일관성", str(e))


def test_validate_config_file_utility(result: TestResult) -> None:
    """validate_config_file 유틸리티"""
    try:
        # Loader를 명시적으로 전달 (절대 경로 허용)
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        validated = validate_config_file(
            "base.yaml",  # 상대 경로 사용
            DesktopConfigValidator,
            loader=loader
        )

        # 검증 성공 확인
        assert validated is not None
        assert validated.gpu.device_id == 0
        assert validated.gpu.memory_fraction == 0.8
        assert validated.app.name == "COURTVIEW Desktop"
        assert validated.camera.min_count == 4

        result.ok("validate_config_file 유틸리티")
    except Exception as e:
        result.fail("validate_config_file 유틸리티", str(e))


def test_settings_immutability(result: TestResult) -> None:
    """Settings 불변성 보장"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 직접 변경 시도 (실패해야 함)
        try:
            settings.new_field = "test"
            result.fail("Settings 불변성 보장", "AttributeError가 발생하지 않음")
        except AttributeError as e:
            assert "동결" in str(e)
            result.ok("Settings 불변성 보장")

    except Exception as e:
        result.fail("Settings 불변성 보장", str(e))


def test_dict_export_consistency(result: TestResult) -> None:
    """딕셔너리 변환 일관성"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 딕셔너리로 변환
        config_dict = settings.get_dict()

        # 구조 검증
        assert "app" in config_dict
        assert "gpu" in config_dict
        assert "camera" in config_dict
        assert "detection" in config_dict
        assert "environment" in config_dict

        # 값 일관성 검증
        assert config_dict["gpu"]["device_id"] == settings.gpu.device_id
        assert config_dict["app"]["name"] == settings.app.name
        assert config_dict["camera"]["min_count"] == settings.camera.min_count
        assert config_dict["environment"] == settings.environment

        result.ok("딕셔너리 변환 일관성")
    except Exception as e:
        result.fail("딕셔너리 변환 일관성", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 통합 테스트 실행"""
    print("="*60)
    print("Config 모듈 통합 테스트")
    print("="*60)

    result = TestResult()

    print("\n[전체 파이프라인]")
    test_full_pipeline_dev(result)
    test_full_pipeline_prod(result)
    test_config_merge_priority(result)

    print("\n[에러 처리]")
    test_error_handling_invalid_yaml(result)
    test_error_handling_invalid_config(result)

    print("\n[멀티스레드 및 리로드]")
    test_multithreaded_settings_access(result)
    test_config_reload_consistency(result)

    print("\n[유틸리티 및 일관성]")
    test_validate_config_file_utility(result)
    test_settings_immutability(result)
    test_dict_export_consistency(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
