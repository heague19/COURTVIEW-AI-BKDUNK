"""
tests/core_foundation/config/unit/test_settings.py

DesktopSettings 단위 테스트
- 싱글톤 (3개): 인스턴스 생성, Thread-Safe, 한 번만 초기화
- 환경별 설정 (3개): dev/prod/test 로드, 환경 변수 오버라이드
- 설정 접근 (2개): 타입 안전 접근, 딕셔너리 변환
- 리로드 (2개): 설정 리로드, 불변성 보장

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import threading
import time

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.settings import DesktopSettings


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


# ==================== 싱글톤 테스트 (3개) ====================
def test_singleton_instance(result: TestResult) -> None:
    """싱글톤 인스턴스 생성"""
    try:
        # 첫 번째 인스턴스
        settings1 = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 두 번째 인스턴스 (같은 인스턴스여야 함)
        settings2 = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test"
        )

        # 같은 인스턴스인지 확인
        assert settings1 is settings2
        assert id(settings1) == id(settings2)

        result.ok("싱글톤 인스턴스 생성")
    except Exception as e:
        result.fail("싱글톤 인스턴스 생성", str(e))


def test_singleton_thread_safe(result: TestResult) -> None:
    """싱글톤 Thread-Safe 동시 접근"""
    try:
        instances = []

        def create_instance():
            instance = DesktopSettings(
                config_dir=FIXTURES_DIR,
                environment="test"
            )
            instances.append(instance)

        # 10개 스레드 동시 생성
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # 모든 인스턴스가 같아야 함
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance

        result.ok("싱글톤 Thread-Safe 동시 접근")
    except Exception as e:
        result.fail("싱글톤 Thread-Safe 동시 접근", str(e))


def test_singleton_initialized_once(result: TestResult) -> None:
    """싱글톤 한 번만 초기화"""
    try:
        # 첫 번째 초기화
        settings1 = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )
        first_app_name = settings1.app.name

        # 두 번째 호출 (재초기화 안됨)
        settings2 = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="dev"  # 환경 변경해도 무시됨
        )

        # 환경이 변경되지 않아야 함 (이미 초기화됨)
        assert settings2.environment == "test"
        assert settings2.app.name == first_app_name

        result.ok("싱글톤 한 번만 초기화")
    except Exception as e:
        result.fail("싱글톤 한 번만 초기화", str(e))


# ==================== 환경별 설정 테스트 (3개) ====================
def test_environment_dev(result: TestResult) -> None:
    """dev 환경 로드"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="dev",
            reload=True
        )

        # dev 환경 설정 확인
        assert settings.environment == "dev"
        assert settings.app.debug is True
        assert settings.app.log_level == "DEBUG"
        assert settings.gpu.batch_size == 4  # dev는 작은 배치
        assert settings.camera.min_count == 1  # dev는 카메라 1대

        result.ok("dev 환경 로드")
    except Exception as e:
        result.fail("dev 환경 로드", str(e))


def test_environment_prod(result: TestResult) -> None:
    """prod 환경 로드"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="prod",
            reload=True
        )

        # prod 환경 설정 확인
        assert settings.environment == "prod"
        assert settings.app.debug is False
        assert settings.app.log_level == "WARNING"
        assert settings.gpu.memory_fraction == 0.9  # prod는 메모리 최대
        assert settings.gpu.batch_size == 16  # prod는 큰 배치

        result.ok("prod 환경 로드")
    except Exception as e:
        result.fail("prod 환경 로드", str(e))


def test_environment_test(result: TestResult) -> None:
    """test 환경 로드"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # test 환경 설정 확인
        assert settings.environment == "test"
        assert settings.app.debug is True
        assert settings.gpu.batch_size == 2  # test는 최소 배치
        assert settings.camera.min_count == 1
        assert settings.camera.max_count == 2

        result.ok("test 환경 로드")
    except Exception as e:
        result.fail("test 환경 로드", str(e))


# ==================== 설정 접근 테스트 (2개) ====================
def test_type_safe_access(result: TestResult) -> None:
    """타입 안전 속성 접근"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 타입 안전 접근
        assert isinstance(settings.gpu.device_id, int)
        assert isinstance(settings.app.name, str)
        assert isinstance(settings.app.debug, bool)
        assert isinstance(settings.camera.min_count, int)
        assert isinstance(settings.detection.confidence_threshold, float)

        # 값 확인
        assert settings.gpu.device_id == 0
        assert settings.app.name == "COURTVIEW Desktop"
        assert settings.camera.min_count >= 1

        result.ok("타입 안전 속성 접근")
    except Exception as e:
        result.fail("타입 안전 속성 접근", str(e))


def test_get_dict(result: TestResult) -> None:
    """딕셔너리 변환"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 딕셔너리로 변환
        config_dict = settings.get_dict()

        # 구조 확인
        assert "app" in config_dict
        assert "gpu" in config_dict
        assert "camera" in config_dict
        assert "detection" in config_dict
        assert "environment" in config_dict

        # 값 확인
        assert config_dict["app"]["name"] == "COURTVIEW Desktop"
        assert config_dict["gpu"]["device_id"] == 0
        assert config_dict["environment"] == "test"

        result.ok("딕셔너리 변환")
    except Exception as e:
        result.fail("딕셔너리 변환", str(e))


# ==================== 리로드 테스트 (2개) ====================
def test_reload(result: TestResult) -> None:
    """설정 리로드"""
    try:
        # 첫 번째 환경 (test)
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )
        assert settings.environment == "test"
        assert settings.gpu.batch_size == 2

        # 환경 변경 후 리로드 (dev)
        # 주의: 환경 변경은 __init__이 아닌 reload() 전에 _environment 직접 설정
        settings._environment = "dev"
        settings.reload()

        # dev 환경으로 변경되었는지 확인
        assert settings.environment == "dev"
        assert settings.gpu.batch_size == 4

        result.ok("설정 리로드")
    except Exception as e:
        result.fail("설정 리로드", str(e))


def test_immutability(result: TestResult) -> None:
    """불변성 보장 (freeze)"""
    try:
        settings = DesktopSettings(
            config_dir=FIXTURES_DIR,
            environment="test",
            reload=True
        )

        # 설정 변경 시도 (실패해야 함)
        try:
            settings.custom_field = "test"  # 새로운 필드 추가 시도
            result.fail("불변성 보장", "AttributeError가 발생하지 않음")
        except AttributeError as e:
            assert "동결" in str(e)
            result.ok("불변성 보장")

    except Exception as e:
        result.fail("불변성 보장", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("DesktopSettings 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[싱글톤]")
    test_singleton_instance(result)
    test_singleton_thread_safe(result)
    test_singleton_initialized_once(result)

    print("\n[환경별 설정]")
    test_environment_dev(result)
    test_environment_prod(result)
    test_environment_test(result)

    print("\n[설정 접근]")
    test_type_safe_access(result)
    test_get_dict(result)

    print("\n[리로드]")
    test_reload(result)
    test_immutability(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
