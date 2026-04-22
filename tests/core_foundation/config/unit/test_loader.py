# -*- coding: utf-8 -*-
"""config/loader.py 단위 테스트."""
from __future__ import annotations

import os
import sys
import textwrap
import threading

sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
from pathlib import Path

from core_foundation.config.loader import (
    ConfigLoader,
    ConfigLoadResult,
    Environment,
    OSPlatform,
    ENV_PREFIX,
    ENV_SEPARATOR,
    MAX_YAML_FILE_SIZE_BYTES,
    MAX_MERGE_DEPTH,
    YAML_EXTENSIONS,
)
from shared.exceptions.validation_exceptions import (
    ConfigurationLoadException,
    ConfigurationNotFoundException,
    ConfigurationParseException,
)


# =============================================================================
# 테스트 Fixture
# =============================================================================

@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """임시 설정 디렉토리 생성."""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "environments").mkdir()
    return config_dir


@pytest.fixture
def base_yaml(tmp_config_dir: Path) -> Path:
    """기본 YAML 설정 파일 생성."""
    yaml_file = tmp_config_dir / "base_config.yaml"
    yaml_file.write_text(textwrap.dedent("""\
        gpu:
          batch_size: 4
          fp16: true
          device: "cuda:0"
        camera:
          count: 4
          fps: 60
          resolution:
            width: 1920
            height: 1080
        system:
          log_level: "INFO"
    """), encoding="utf-8")
    return yaml_file


@pytest.fixture
def env_yaml(tmp_config_dir: Path) -> Path:
    """환경별 오버라이드 YAML 생성."""
    env_file = tmp_config_dir / "environments" / "local.yaml"
    env_file.write_text(textwrap.dedent("""\
        gpu:
          batch_size: 2
        system:
          log_level: "DEBUG"
          debug_mode: true
    """), encoding="utf-8")
    return env_file


@pytest.fixture
def os_yaml(tmp_config_dir: Path) -> Path:
    """OS별 오버라이드 YAML 생성."""
    os_file = tmp_config_dir / "environments" / "windows.yaml"
    os_file.write_text(textwrap.dedent("""\
        system:
          temp_dir: "C:/temp"
    """), encoding="utf-8")
    return os_file


@pytest.fixture
def loader(tmp_config_dir: Path) -> ConfigLoader:
    """ConfigLoader 인스턴스 생성."""
    return ConfigLoader(
        config_dir=tmp_config_dir,
        environment=Environment.LOCAL,
        os_platform=OSPlatform.WINDOWS,
        enable_env_override=False,
    )


# =============================================================================
# Environment Enum 검증
# =============================================================================

class TestEnvironment:
    """Environment Enum 검증."""

    def test_member_count(self):
        assert len(Environment) == 3

    def test_values(self):
        assert Environment.LOCAL.value == "local"
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.PRODUCTION.value == "production"

    def test_is_development(self):
        assert Environment.LOCAL.is_development is True
        assert Environment.DEVELOPMENT.is_development is True
        assert Environment.PRODUCTION.is_development is False

    def test_is_production(self):
        assert Environment.PRODUCTION.is_production is True
        assert Environment.LOCAL.is_production is False

    def test_to_korean(self):
        assert Environment.LOCAL.to_korean() == "로컬"
        assert Environment.DEVELOPMENT.to_korean() == "개발"
        assert Environment.PRODUCTION.to_korean() == "프로덕션"

    def test_from_string(self):
        assert Environment.from_string("local") == Environment.LOCAL
        assert Environment.from_string("LOCAL") == Environment.LOCAL
        assert Environment.from_string("  production  ") == Environment.PRODUCTION

    def test_from_string_invalid(self):
        with pytest.raises(ValueError, match="알 수 없는 환경"):
            Environment.from_string("staging")


# =============================================================================
# OSPlatform Enum 검증
# =============================================================================

class TestOSPlatform:
    """OSPlatform Enum 검증."""

    def test_member_count(self):
        assert len(OSPlatform) == 3

    def test_values(self):
        assert OSPlatform.WINDOWS.value == "windows"
        assert OSPlatform.MACOS.value == "macos"
        assert OSPlatform.LINUX.value == "linux"

    def test_to_korean(self):
        assert OSPlatform.WINDOWS.to_korean() == "윈도우"
        assert OSPlatform.MACOS.to_korean() == "맥OS"
        assert OSPlatform.LINUX.to_korean() == "리눅스"

    def test_detect_returns_valid(self):
        """현재 OS에서 유효한 값 반환."""
        detected = OSPlatform.detect()
        assert isinstance(detected, OSPlatform)


# =============================================================================
# ConfigLoadResult 검증
# =============================================================================

class TestConfigLoadResult:
    """ConfigLoadResult 데이터클래스 검증."""

    def test_get_simple_key(self):
        result = ConfigLoadResult(
            data={"gpu": {"batch_size": 4}},
            loaded_files=["test.yaml"],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=[],
        )
        assert result.get("gpu.batch_size") == 4

    def test_get_nested_key(self):
        result = ConfigLoadResult(
            data={"a": {"b": {"c": 42}}},
            loaded_files=[],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=[],
        )
        assert result.get("a.b.c") == 42

    def test_get_missing_key_returns_default(self):
        result = ConfigLoadResult(
            data={"gpu": {}},
            loaded_files=[],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=[],
        )
        assert result.get("gpu.missing", "fallback") == "fallback"

    def test_get_top_level_key(self):
        result = ConfigLoadResult(
            data={"key": "value"},
            loaded_files=[],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=[],
        )
        assert result.get("key") == "value"

    def test_repr(self):
        result = ConfigLoadResult(
            data={},
            loaded_files=["a.yaml", "b.yaml"],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=["gpu.batch_size"],
        )
        r = repr(result)
        assert "files=2" in r
        assert "env=local" in r
        assert "overrides=1" in r

    def test_slots(self):
        """slots=True 확인."""
        assert hasattr(ConfigLoadResult, "__slots__")


# =============================================================================
# ConfigLoader — 기본 로딩
# =============================================================================

class TestConfigLoaderBasic:
    """ConfigLoader 기본 YAML 로딩."""

    def test_load_base_yaml(self, loader: ConfigLoader, base_yaml: Path):
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert result.data["gpu"]["batch_size"] == 4
        assert result.data["camera"]["count"] == 4
        assert result.data["system"]["log_level"] == "INFO"

    def test_load_returns_config_load_result(self, loader: ConfigLoader, base_yaml: Path):
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert isinstance(result, ConfigLoadResult)

    def test_loaded_files_tracked(self, loader: ConfigLoader, base_yaml: Path):
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert "base_config.yaml" in result.loaded_files

    def test_load_raw(self, loader: ConfigLoader, base_yaml: Path):
        data = loader.load_raw("base_config.yaml")
        assert isinstance(data, dict)
        assert data["gpu"]["fp16"] is True

    def test_load_nonexistent_raises(self, loader: ConfigLoader):
        with pytest.raises(ConfigurationNotFoundException):
            loader.load("nonexistent.yaml")

    def test_load_invalid_yaml_raises(self, loader: ConfigLoader, tmp_config_dir: Path):
        bad_file = tmp_config_dir / "bad.yaml"
        bad_file.write_text(":\n  - {\ninvalid", encoding="utf-8")
        with pytest.raises(ConfigurationParseException):
            loader.load("bad.yaml")

    def test_load_non_dict_yaml_raises(self, loader: ConfigLoader, tmp_config_dir: Path):
        list_file = tmp_config_dir / "list.yaml"
        list_file.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigurationParseException, match="dict가 아닙니다"):
            loader.load("list.yaml")

    def test_load_empty_yaml(self, loader: ConfigLoader, tmp_config_dir: Path):
        empty = tmp_config_dir / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        result = loader.load("empty.yaml", merge_environment=False, merge_os=False)
        assert result.data == {}


# =============================================================================
# ConfigLoader — 3단계 병합
# =============================================================================

class TestConfigLoaderMerge:
    """3단계 병합 검증."""

    def test_environment_override(
        self, loader: ConfigLoader, base_yaml: Path, env_yaml: Path
    ):
        result = loader.load("base_config.yaml", merge_os=False)
        # local.yaml에서 오버라이드
        assert result.data["gpu"]["batch_size"] == 2
        assert result.data["system"]["log_level"] == "DEBUG"
        assert result.data["system"]["debug_mode"] is True
        # base 값 보존
        assert result.data["gpu"]["fp16"] is True
        assert result.data["camera"]["count"] == 4

    def test_os_override(
        self, loader: ConfigLoader, base_yaml: Path, os_yaml: Path
    ):
        result = loader.load("base_config.yaml", merge_environment=False)
        assert result.data["system"]["temp_dir"] == "C:/temp"
        # base 값 보존
        assert result.data["gpu"]["batch_size"] == 4

    def test_full_merge_order(
        self, loader: ConfigLoader, base_yaml: Path, env_yaml: Path, os_yaml: Path
    ):
        """base → env → os 순서로 병합."""
        result = loader.load("base_config.yaml")
        # env 오버라이드
        assert result.data["gpu"]["batch_size"] == 2
        assert result.data["system"]["debug_mode"] is True
        # os 오버라이드
        assert result.data["system"]["temp_dir"] == "C:/temp"
        # 로드된 파일 3개
        assert len(result.loaded_files) == 3

    def test_deep_merge_nested(self, loader: ConfigLoader, base_yaml: Path, env_yaml: Path):
        """중첩 딕셔너리 deep merge — 형제 키 보존."""
        result = loader.load("base_config.yaml", merge_os=False)
        # gpu.batch_size는 오버라이드, gpu.fp16과 gpu.device는 보존
        assert result.data["gpu"]["batch_size"] == 2
        assert result.data["gpu"]["fp16"] is True
        assert result.data["gpu"]["device"] == "cuda:0"


# =============================================================================
# ConfigLoader — 환경 변수 오버라이드
# =============================================================================

class TestConfigLoaderEnvOverride:
    """환경 변수 오버라이드 검증."""

    def test_env_override_simple(self, tmp_config_dir: Path, base_yaml: Path, monkeypatch):
        monkeypatch.setenv("COURTVIEW_GPU__BATCH_SIZE", "16")
        loader = ConfigLoader(
            config_dir=tmp_config_dir,
            environment=Environment.LOCAL,
            enable_env_override=True,
            enable_cache=False,
        )
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert result.data["gpu"]["batch_size"] == 16
        assert "gpu.batch_size" in result.env_overrides

    def test_env_override_bool(self, tmp_config_dir: Path, base_yaml: Path, monkeypatch):
        monkeypatch.setenv("COURTVIEW_GPU__FP16", "false")
        loader = ConfigLoader(
            config_dir=tmp_config_dir,
            environment=Environment.LOCAL,
            enable_env_override=True,
            enable_cache=False,
        )
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert result.data["gpu"]["fp16"] is False

    def test_env_override_creates_new_key(self, tmp_config_dir: Path, base_yaml: Path, monkeypatch):
        monkeypatch.setenv("COURTVIEW_NEW__NESTED__KEY", "hello")
        loader = ConfigLoader(
            config_dir=tmp_config_dir,
            environment=Environment.LOCAL,
            enable_env_override=True,
            enable_cache=False,
        )
        result = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert result.data["new"]["nested"]["key"] == "hello"

    def test_env_coerce_int(self):
        assert ConfigLoader._coerce_env_value("42") == 42

    def test_env_coerce_float(self):
        assert ConfigLoader._coerce_env_value("3.14") == 3.14

    def test_env_coerce_true(self):
        assert ConfigLoader._coerce_env_value("true") is True

    def test_env_coerce_false(self):
        assert ConfigLoader._coerce_env_value("false") is False

    def test_env_coerce_none(self):
        assert ConfigLoader._coerce_env_value("none") is None
        assert ConfigLoader._coerce_env_value("null") is None

    def test_env_coerce_string(self):
        assert ConfigLoader._coerce_env_value("hello") == "hello"


# =============================================================================
# ConfigLoader — 캐싱
# =============================================================================

class TestConfigLoaderCache:
    """캐시 동작 검증."""

    def test_cache_hit(self, loader: ConfigLoader, base_yaml: Path):
        r1 = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        r2 = loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert r1.data == r2.data
        # 방어적 복사 — 다른 객체
        assert r1.data is not r2.data

    def test_cache_size(self, loader: ConfigLoader, base_yaml: Path):
        assert loader.cache_size == 0
        loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert loader.cache_size > 0

    def test_invalidate_all(self, loader: ConfigLoader, base_yaml: Path):
        loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        count = loader.invalidate_cache()
        assert count > 0
        assert loader.cache_size == 0

    def test_invalidate_specific(self, loader: ConfigLoader, base_yaml: Path):
        loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        count = loader.invalidate_cache("base_config.yaml")
        assert count > 0

    def test_cache_disabled(self, tmp_config_dir: Path, base_yaml: Path):
        loader = ConfigLoader(
            config_dir=tmp_config_dir,
            environment=Environment.LOCAL,
            enable_cache=False,
            enable_env_override=False,
        )
        loader.load("base_config.yaml", merge_environment=False, merge_os=False)
        assert loader.cache_size == 0


# =============================================================================
# ConfigLoader — 스레드 안전
# =============================================================================

class TestConfigLoaderThreadSafety:
    """스레드 안전성 검증."""

    def test_concurrent_loads(self, loader: ConfigLoader, base_yaml: Path):
        """10개 스레드 동시 로드 — 에러 없음."""
        errors: list[Exception] = []

        def load_config():
            try:
                result = loader.load(
                    "base_config.yaml",
                    merge_environment=False,
                    merge_os=False,
                )
                assert result.data["gpu"]["batch_size"] == 4
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=load_config) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"스레드 에러: {errors}"


# =============================================================================
# ConfigLoader — 속성 검증
# =============================================================================

class TestConfigLoaderProperties:
    """ConfigLoader 속성 검증."""

    def test_config_dir(self, loader: ConfigLoader, tmp_config_dir: Path):
        assert loader.config_dir == tmp_config_dir.resolve()

    def test_environment(self, loader: ConfigLoader):
        assert loader.environment == Environment.LOCAL

    def test_os_platform(self, loader: ConfigLoader):
        assert loader.os_platform == OSPlatform.WINDOWS

    def test_repr(self, loader: ConfigLoader):
        r = repr(loader)
        assert "ConfigLoader" in r
        assert "env=local" in r

    def test_detect_environment_from_env_var(self, monkeypatch):
        monkeypatch.setenv("COURTVIEW_ENV", "production")
        env = ConfigLoader._detect_environment()
        assert env == Environment.PRODUCTION

    def test_detect_environment_default(self, monkeypatch):
        monkeypatch.delenv("COURTVIEW_ENV", raising=False)
        env = ConfigLoader._detect_environment()
        assert env == Environment.LOCAL


# =============================================================================
# 모듈 상수 검증
# =============================================================================

class TestModuleConstants:
    """모듈 레벨 상수 검증."""

    def test_env_prefix(self):
        assert ENV_PREFIX == "COURTVIEW_"

    def test_env_separator(self):
        assert ENV_SEPARATOR == "__"

    def test_max_yaml_size(self):
        assert MAX_YAML_FILE_SIZE_BYTES == 10 * 1024 * 1024

    def test_max_merge_depth(self):
        assert MAX_MERGE_DEPTH == 20

    def test_yaml_extensions(self):
        assert ".yaml" in YAML_EXTENSIONS
        assert ".yml" in YAML_EXTENSIONS


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    """__all__ 및 __version__ 검증."""

    def test_all_exists(self):
        import core_foundation.config.loader as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.config.loader as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not in module"

    def test_version(self):
        import core_foundation.config.loader as mod
        assert mod.__version__ == "1.0.0"
