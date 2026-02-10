"""
tests/core_foundation/config/unit/test_loader.py

ConfigLoader 단위 테스트
- YAML 파일 로딩 및 캐싱
- 설정 병합 (우선순위: ENV > env_config > base_config)
- 중첩 키 접근 (점 표기법)
- 경로 검증 및 보안
- 에러 처리

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
import os
from pathlib import Path
import tempfile

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.loader import ConfigLoader
from core_foundation.exceptions.validation import ConfigError


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


# 테스트 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ==================== 기본 기능 테스트 ====================
def test_loader_initialization(result: TestResult) -> None:
    """ConfigLoader 초기화 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        assert loader.config_dir == FIXTURES_DIR
        result.ok("ConfigLoader 초기화")
    except AssertionError as e:
        result.fail("ConfigLoader 초기화", str(e))


def test_load_yaml_basic(result: TestResult) -> None:
    """기본 YAML 로딩 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        config = loader.load_yaml("test_base.yaml")

        assert config["app"]["name"] == "COURTVIEW Desktop"
        assert config["app"]["version"] == "1.0.0"
        assert config["gpu"]["enabled"] is True
        assert config["gpu"]["device_id"] == 0

        result.ok("기본 YAML 로딩")
    except AssertionError as e:
        result.fail("기본 YAML 로딩", str(e))


def test_load_yaml_caching(result: TestResult) -> None:
    """YAML 캐싱 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        # 첫 번째 로딩
        config1 = loader.load_yaml("test_base.yaml")

        # 두 번째 로딩 (캐시에서)
        config2 = loader.load_yaml("test_base.yaml")

        # 내용이 같아야 함 (loader.py가 shallow copy 사용)
        assert config1 == config2
        assert config1["app"]["name"] == config2["app"]["name"]

        result.ok("YAML 캐싱")
    except AssertionError as e:
        result.fail("YAML 캐싱", str(e))


def test_load_yaml_file_not_found(result: TestResult) -> None:
    """파일 없음 에러 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        error_raised = False
        try:
            loader.load_yaml("missing_file.yaml")
        except ConfigError as e:
            error_raised = True
            assert e.error_code == "CV101", f"Expected CV101, got {e.error_code}"
            assert "missing_file.yaml" in e.message, "missing_file.yaml not in message"

        if not error_raised:
            result.fail("파일 없음 에러", "ConfigError가 발생하지 않음")
        else:
            result.ok("파일 없음 에러")

    except Exception as e:
        result.fail("파일 없음 에러", f"{type(e).__name__}: {str(e)}")


def test_load_yaml_parsing_error(result: TestResult) -> None:
    """YAML 파싱 에러 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        try:
            loader.load_yaml("test_invalid.yaml")
            # 예외가 발생해야 함
            result.fail("YAML 파싱 에러", "ConfigError가 발생하지 않음")
        except ConfigError as e:
            assert e.error_code == "CV102"
            result.ok("YAML 파싱 에러")

    except Exception as e:
        result.fail("YAML 파싱 에러", str(e))


# ==================== 설정 병합 테스트 ====================
def test_merge_configs_basic(result: TestResult) -> None:
    """기본 설정 병합 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        base = loader.load_yaml("test_base.yaml")
        env_config = loader.load_yaml("test_env_dev.yaml")

        merged = loader.merge_configs(base, env_config, {})

        # env_config 값이 우선
        assert merged["app"]["debug"] is True  # env_dev에서 True
        assert merged["gpu"]["memory_fraction"] == 0.7  # env_dev에서 0.7

        # base 값 유지
        assert merged["app"]["name"] == "COURTVIEW Desktop"
        assert merged["camera"]["min_count"] == 4

        result.ok("기본 설정 병합")
    except AssertionError as e:
        result.fail("기본 설정 병합", str(e))


def test_merge_configs_priority(result: TestResult) -> None:
    """설정 병합 우선순위 테스트 (ENV > env_config > base)"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        base = {"app": {"debug": False, "name": "Base"}}
        env_config = {"app": {"debug": True}}
        env_override = {"app": {"name": "Override"}}

        merged = loader.merge_configs(base, env_config, env_override)

        # ENV > env_config > base 우선순위
        assert merged["app"]["name"] == "Override"  # ENV 우선
        assert merged["app"]["debug"] is True  # env_config 우선

        result.ok("설정 병합 우선순위")
    except AssertionError as e:
        result.fail("설정 병합 우선순위", str(e))


# ==================== get() 메서드 테스트 ====================
def test_get_simple_key(result: TestResult) -> None:
    """단순 키 접근 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        config = loader.load_yaml("test_base.yaml")

        # config 파라미터 전달
        value = loader.get("app", config)

        assert value["name"] == "COURTVIEW Desktop"

        result.ok("단순 키 접근")
    except AssertionError as e:
        result.fail("단순 키 접근", str(e))


def test_get_nested_key(result: TestResult) -> None:
    """중첩 키 접근 테스트 (점 표기법)"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        config = loader.load_yaml("test_base.yaml")

        # 점 표기법 (config 파라미터 전달)
        assert loader.get("app.name", config) == "COURTVIEW Desktop"
        assert loader.get("app.version", config) == "1.0.0"
        assert loader.get("gpu.device_id", config) == 0
        assert loader.get("camera.resolution.width", config) == 1920

        result.ok("중첩 키 접근")
    except AssertionError as e:
        result.fail("중첩 키 접근", str(e))


def test_get_with_default(result: TestResult) -> None:
    """기본값 사용 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)
        config = loader.load_yaml("test_base.yaml")

        # 존재하는 키
        assert loader.get("app.name", config, default="default") == "COURTVIEW Desktop"

        # 존재하지 않는 키 -> 기본값 반환
        assert loader.get("missing.key", config, default="default") == "default"

        result.ok("기본값 사용")
    except AssertionError as e:
        result.fail("기본값 사용", str(e))


# ==================== clear_cache() 메서드 테스트 ====================
def test_clear_cache(result: TestResult) -> None:
    """clear_cache() 캐시 무효화 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        # 첫 번째 로딩
        loader.load_yaml("test_base.yaml")
        loader.load_yaml("test_env_dev.yaml")

        # 캐시 클리어
        cleared = loader.clear_cache()

        # 2개 이상 삭제되어야 함
        assert cleared >= 2

        result.ok("clear_cache() 캐시 무효화")
    except AssertionError as e:
        result.fail("clear_cache() 캐시 무효화", str(e))


# ==================== 보안 테스트 ====================
def test_path_validation_path_traversal(result: TestResult) -> None:
    """경로 탐색 공격 방지 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        try:
            # ../ 공격
            loader.load_yaml("../../../etc/passwd")
            result.fail("경로 탐색 공격 방지", "예외가 발생하지 않음")
        except (ConfigError, ValueError):
            result.ok("경로 탐색 공격 방지")

    except Exception as e:
        result.fail("경로 탐색 공격 방지", str(e))


def test_path_validation_absolute_path(result: TestResult) -> None:
    """절대 경로 차단 테스트"""
    try:
        loader = ConfigLoader(config_dir=FIXTURES_DIR)

        try:
            # 절대 경로 차단
            loader.load_yaml("/etc/passwd")
            result.fail("절대 경로 차단", "예외가 발생하지 않음")
        except (ConfigError, ValueError):
            result.ok("절대 경로 차단")

    except Exception as e:
        result.fail("절대 경로 차단", str(e))


# ==================== 환경 변수 테스트 ====================
def test_load_env_from_file(result: TestResult) -> None:
    """환경 변수 파일 로딩 테스트"""
    try:
        # 임시 .env 파일 생성 (COURTVIEW 접두사 사용)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("COURTVIEW_TEST_KEY=test_value\n")
            f.write("SERVER_PORT=8080\n")
            f.write("GPU_DEVICE_ID=0\n")
            env_file = f.name

        try:
            loader = ConfigLoader(config_dir=FIXTURES_DIR, env_file=env_file)
            env_vars = loader.load_env()

            # COURTVIEW 접두사 변수들이 로드되어야 함
            assert "COURTVIEW_TEST_KEY" in env_vars
            assert env_vars["COURTVIEW_TEST_KEY"] == "test_value"
            assert "SERVER_PORT" in env_vars
            assert env_vars["SERVER_PORT"] == "8080"
            assert "GPU_DEVICE_ID" in env_vars
            assert env_vars["GPU_DEVICE_ID"] == "0"

            result.ok("환경 변수 파일 로딩")
        finally:
            os.unlink(env_file)

    except AssertionError as e:
        result.fail("환경 변수 파일 로딩", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 테스트 실행"""
    print("="*60)
    print("ConfigLoader 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[기본 기능]")
    test_loader_initialization(result)
    test_load_yaml_basic(result)
    test_load_yaml_caching(result)
    test_load_yaml_file_not_found(result)
    test_load_yaml_parsing_error(result)

    print("\n[설정 병합]")
    test_merge_configs_basic(result)
    test_merge_configs_priority(result)

    print("\n[get() 메서드]")
    test_get_simple_key(result)
    test_get_nested_key(result)
    test_get_with_default(result)

    print("\n[clear_cache() 메서드]")
    test_clear_cache(result)

    print("\n[보안]")
    test_path_validation_path_traversal(result)
    test_path_validation_absolute_path(result)

    print("\n[환경 변수]")
    test_load_env_from_file(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
