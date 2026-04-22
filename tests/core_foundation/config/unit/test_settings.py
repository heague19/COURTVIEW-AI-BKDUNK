# -*- coding: utf-8 -*-
"""config/settings.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import copy
import threading
import time

import pytest
from typing import Any
from unittest.mock import MagicMock, patch

from core_foundation.config.settings import (
    AppSettings,
    ConfigSnapshot,
    DEFAULT_CONFIG_FILE,
    MAX_SNAPSHOT_COUNT,
    _DEFAULT_CONFIG,
)
from core_foundation.config.loader import (
    ConfigLoader,
    ConfigLoadResult,
    Environment,
    OSPlatform,
)
from core_foundation.config.validator import (
    ConfigValidator,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)


# =============================================================================
# 테스트 설정
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """모든 테스트 전후로 Singleton 초기화."""
    AppSettings.reset()
    yield
    AppSettings.reset()


def _make_mock_loader(data: dict[str, Any] | None = None) -> ConfigLoader:
    """ConfigLoadResult를 반환하는 mock 로더 생성."""
    mock_loader = MagicMock(spec=ConfigLoader)
    mock_loader.environment = Environment.LOCAL
    mock_loader.os_platform = OSPlatform.WINDOWS
    mock_loader.cache_size = 0

    config_data = data or {
        "gpu": {"batch_size": 8, "fp16": True, "device": "cuda:0"},
        "camera": {"count": 4, "fps": 60},
        "system": {"log_level": "DEBUG"},
    }

    mock_loader.load.return_value = ConfigLoadResult(
        data=config_data,
        loaded_files=["test_config.yaml"],
        environment=Environment.LOCAL,
        os_platform=OSPlatform.WINDOWS,
        env_overrides=[],
    )
    mock_loader.invalidate_cache.return_value = 0
    return mock_loader


# =============================================================================
# ConfigSnapshot 검증
# =============================================================================

class TestConfigSnapshot:
    """ConfigSnapshot 데이터클래스 검증."""

    def test_slots(self):
        assert hasattr(ConfigSnapshot, "__slots__")

    def test_creation(self):
        snap = ConfigSnapshot(
            data={"gpu": {"batch_size": 4}},
            timestamp=time.monotonic(),
            load_result=None,
            validation_result=None,
        )
        assert snap.data["gpu"]["batch_size"] == 4
        assert snap.load_result is None

    def test_repr(self):
        snap = ConfigSnapshot(
            data={"a": 1},
            timestamp=0.0,
            load_result=None,
            validation_result=None,
        )
        assert "N/A" in repr(snap)
        assert "keys=1" in repr(snap)


# =============================================================================
# Singleton 패턴 검증
# =============================================================================

class TestSingleton:
    """Singleton 패턴 검증."""

    def test_initialize_returns_instance(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        assert isinstance(settings, AppSettings)

    def test_initialize_twice_returns_same(self):
        loader = _make_mock_loader()
        s1 = AppSettings.initialize(loader=loader)
        s2 = AppSettings.initialize(loader=loader)
        assert s1 is s2

    def test_get_instance_auto_creates(self):
        """get_instance는 미초기화 시 자동 생성 (기본값 사용)."""
        settings = AppSettings.get_instance()
        assert settings.is_loaded

    def test_reset_clears_instance(self):
        loader = _make_mock_loader()
        s1 = AppSettings.initialize(loader=loader)
        AppSettings.reset()
        s2 = AppSettings.initialize(loader=loader)
        assert s1 is not s2

    def test_force_reinitialize(self):
        loader1 = _make_mock_loader({"mode": "v1"})
        loader2 = _make_mock_loader({"mode": "v2"})
        s1 = AppSettings.initialize(loader=loader1)
        s2 = AppSettings.initialize(loader=loader2, force=True)
        assert s1 is not s2
        assert s2.get("mode") == "v2"


# =============================================================================
# 설정 접근 API 검증
# =============================================================================

class TestSettingsAccess:
    """설정 접근 API 검증."""

    def _create_settings(self, data: dict[str, Any] | None = None) -> AppSettings:
        loader = _make_mock_loader(data)
        return AppSettings.initialize(loader=loader)

    def test_get_simple(self):
        settings = self._create_settings()
        assert settings.get("gpu.batch_size") == 8

    def test_get_nested(self):
        settings = self._create_settings()
        assert settings.get("gpu.fp16") is True

    def test_get_missing_returns_default(self):
        settings = self._create_settings()
        assert settings.get("nonexistent.key", 42) == 42

    def test_get_missing_returns_none(self):
        settings = self._create_settings()
        assert settings.get("nonexistent") is None

    def test_get_returns_defensive_copy(self):
        settings = self._create_settings()
        gpu1 = settings.get("gpu")
        gpu2 = settings.get("gpu")
        assert gpu1 is not gpu2
        assert gpu1 == gpu2

    def test_get_section(self):
        settings = self._create_settings()
        gpu = settings.get_section("gpu")
        assert isinstance(gpu, dict)
        assert gpu["batch_size"] == 8

    def test_get_section_missing(self):
        settings = self._create_settings()
        empty = settings.get_section("nonexistent")
        assert empty == {}

    def test_get_section_defensive_copy(self):
        settings = self._create_settings()
        gpu1 = settings.get_section("gpu")
        gpu2 = settings.get_section("gpu")
        assert gpu1 is not gpu2

    def test_get_all(self):
        settings = self._create_settings()
        all_data = settings.get_all()
        assert isinstance(all_data, dict)
        assert "gpu" in all_data

    def test_get_all_defensive_copy(self):
        settings = self._create_settings()
        d1 = settings.get_all()
        d2 = settings.get_all()
        assert d1 is not d2

    def test_has_existing(self):
        settings = self._create_settings()
        assert settings.has("gpu.batch_size") is True

    def test_has_missing(self):
        settings = self._create_settings()
        assert settings.has("nonexistent.key") is False


# =============================================================================
# 기본값 병합 검증
# =============================================================================

class TestDefaultMerge:
    """기본값 병합 검증."""

    def test_defaults_fill_missing(self):
        """로드된 설정에 없는 키는 기본값으로 채워진다."""
        loader = _make_mock_loader({"gpu": {"batch_size": 16}})
        settings = AppSettings.initialize(loader=loader, use_defaults=True)

        # 로드된 값 우선
        assert settings.get("gpu.batch_size") == 16
        # 기본값으로 채워짐
        assert settings.get("gpu.fp16") is True
        assert settings.get("camera.fps") == 30

    def test_loaded_overrides_defaults(self):
        """로드된 설정이 기본값을 덮어쓴다."""
        loader = _make_mock_loader({"camera": {"fps": 120}})
        settings = AppSettings.initialize(loader=loader)
        assert settings.get("camera.fps") == 120

    def test_no_defaults_mode(self):
        """use_defaults=False면 기본값 병합 안 함."""
        data = {"custom": {"key": "value"}}
        loader = _make_mock_loader(data)
        settings = AppSettings.initialize(loader=loader, use_defaults=False)
        assert settings.get("gpu.batch_size") is None
        assert settings.get("custom.key") == "value"


# =============================================================================
# 파일 미발견 시 기본값 폴백 검증
# =============================================================================

class TestFileNotFound:
    """설정 파일 미발견 시 동작 검증."""

    def test_defaults_on_file_not_found(self):
        """파일 없으면 기본값 사용."""
        from shared.exceptions.validation_exceptions import (
            ConfigurationNotFoundException,
        )
        mock_loader = MagicMock(spec=ConfigLoader)
        mock_loader.environment = Environment.LOCAL
        mock_loader.os_platform = OSPlatform.WINDOWS
        mock_loader.load.side_effect = ConfigurationNotFoundException(
            config_file="missing.yaml",
            searched_paths=["configs/"],
        )

        settings = AppSettings.initialize(loader=mock_loader, use_defaults=True)
        assert settings.is_loaded
        assert settings.get("gpu.batch_size") == 4  # 기본값

    def test_raise_on_file_not_found_no_defaults(self):
        """use_defaults=False면 파일 없을 때 예외 발생."""
        from shared.exceptions.validation_exceptions import (
            ConfigurationNotFoundException,
        )
        mock_loader = MagicMock(spec=ConfigLoader)
        mock_loader.environment = Environment.LOCAL
        mock_loader.os_platform = OSPlatform.WINDOWS
        mock_loader.load.side_effect = ConfigurationNotFoundException(
            config_file="missing.yaml",
            searched_paths=["configs/"],
        )

        with pytest.raises(ConfigurationNotFoundException):
            AppSettings.initialize(loader=mock_loader, use_defaults=False)


# =============================================================================
# 프로퍼티 검증
# =============================================================================

class TestProperties:
    """프로퍼티 접근 검증."""

    def test_is_loaded(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        assert settings.is_loaded is True

    def test_environment(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        assert settings.environment == Environment.LOCAL

    def test_os_platform(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        assert settings.os_platform == OSPlatform.WINDOWS

    def test_config_file(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(
            loader=loader,
            config_file="custom/path.yaml",
        )
        assert settings.config_file == "custom/path.yaml"

    def test_load_timestamp(self):
        before = time.monotonic()
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        after = time.monotonic()
        assert before <= settings.load_timestamp <= after


# =============================================================================
# 리로드 검증
# =============================================================================

class TestReload:
    """설정 리로드 검증."""

    def test_reload_updates_data(self):
        loader = _make_mock_loader({"gpu": {"batch_size": 4}})
        settings = AppSettings.initialize(loader=loader)
        assert settings.get("gpu.batch_size") == 4

        # 리로드 시 새 데이터 반환
        loader.load.return_value = ConfigLoadResult(
            data={"gpu": {"batch_size": 32}},
            loaded_files=["test_config.yaml"],
            environment=Environment.LOCAL,
            os_platform=OSPlatform.WINDOWS,
            env_overrides=[],
        )
        settings.reload()
        assert settings.get("gpu.batch_size") == 32

    def test_reload_invalidates_cache(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        settings.reload()
        loader.invalidate_cache.assert_called()

    def test_reload_saves_snapshot(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        assert settings.snapshot_count == 0
        settings.reload()
        assert settings.snapshot_count == 1


# =============================================================================
# 스냅샷 검증
# =============================================================================

class TestSnapshot:
    """스냅샷 기능 검증."""

    def test_take_snapshot(self):
        loader = _make_mock_loader({"a": 1})
        settings = AppSettings.initialize(loader=loader)
        snap = settings.take_snapshot()
        assert isinstance(snap, ConfigSnapshot)
        assert "a" in snap.data

    def test_snapshot_max_limit(self):
        """스냅샷 최대 보관 수 초과 시 오래된 것부터 제거."""
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)

        for _ in range(MAX_SNAPSHOT_COUNT + 5):
            settings.reload()

        assert settings.snapshot_count <= MAX_SNAPSHOT_COUNT

    def test_snapshots_list(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        settings.reload()
        settings.reload()
        snaps = settings.snapshots
        assert len(snaps) == 2
        assert isinstance(snaps[0], ConfigSnapshot)


# =============================================================================
# 검증 통합 검증
# =============================================================================

class TestValidation:
    """검증기 통합 검증."""

    def test_validate(self):
        loader = _make_mock_loader()
        validator = ConfigValidator()
        validator.add_rule(ValidationRule(key="gpu.batch_size", expected_type=int))

        settings = AppSettings.initialize(loader=loader, validator=validator)
        result = settings.validate()
        assert result.is_valid

    def test_validate_fail(self):
        loader = _make_mock_loader()
        validator = ConfigValidator()
        validator.add_rule(ValidationRule(key="gpu.batch_size", expected_type=str))

        settings = AppSettings.initialize(loader=loader, validator=validator)
        result = settings.validate()
        assert not result.is_valid

    def test_add_validation_rule(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        settings.add_validation_rule(
            ValidationRule(key="missing_key", required=True),
        )
        result = settings.validate()
        assert not result.is_valid

    def test_add_validation_rules_batch(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        settings.add_validation_rules([
            ValidationRule(key="gpu.batch_size", expected_type=int),
            ValidationRule(key="camera.fps", expected_type=int),
        ])
        result = settings.validate()
        assert result.is_valid

    def test_auto_validate_on_load(self):
        """검증 규칙이 있으면 로드 시 자동 검증."""
        loader = _make_mock_loader()
        validator = ConfigValidator()
        validator.add_rule(
            ValidationRule(key="gpu.batch_size", expected_type=int),
        )
        settings = AppSettings.initialize(loader=loader, validator=validator)
        assert settings.validation_result is not None
        assert settings.validation_result.is_valid


# =============================================================================
# 스레드 안전 검증
# =============================================================================

class TestThreadSafety:
    """스레드 안전 검증."""

    def test_concurrent_get(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)

        results: list[Any] = []
        errors: list[Exception] = []

        def read_setting():
            try:
                val = settings.get("gpu.batch_size")
                results.append(val)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=read_setting) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert all(v == 8 for v in results)

    def test_concurrent_singleton_access(self):
        """여러 스레드에서 동시에 get_instance 호출."""
        instances: list[AppSettings] = []
        errors: list[Exception] = []

        def get():
            try:
                inst = AppSettings.get_instance()
                instances.append(inst)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=get) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        # 모두 같은 인스턴스
        assert all(inst is instances[0] for inst in instances)


# =============================================================================
# repr 검증
# =============================================================================

class TestRepr:
    """__repr__ 검증."""

    def test_repr_loaded(self):
        loader = _make_mock_loader()
        settings = AppSettings.initialize(loader=loader)
        r = repr(settings)
        assert "loaded=True" in r
        assert "env=local" in r


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    """__all__ 및 __version__ 검증."""

    def test_all_exists(self):
        import core_foundation.config.settings as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.config.settings as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not in module"

    def test_version(self):
        import core_foundation.config.settings as mod
        assert mod.__version__ == "1.0.0"
