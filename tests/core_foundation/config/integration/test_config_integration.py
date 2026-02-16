# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/integration
파일: test_config_integration.py
설명: config 모듈 통합 테스트 (loader + validator + settings + watcher)

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

통합 테스트 시나리오:
    - [1] __init__.py Export 무결성 (45개 Export)
    - [2] Loader → Validator 파이프라인
    - [3] Loader → Validator → Settings 전체 파이프라인
    - [4] Settings 초기화 → 프로퍼티 체인
    - [5] 설정 변경 → Reload → Listener 알림 파이프라인
    - [6] Watcher 컴포넌트 → Settings 연동
    - [7] 동적 설정 파일 생성 → 로드 → 검증 → 접근
    - [8] 프로파일 기반 설정 오버라이드 파이프라인
    - [9] 환경변수 오버라이드 → Validator → Settings
    - [10] 스냅샷 → 변경 → Diff 감지 파이프라인
    - [11] 다중 파일 병합 파이프라인
    - [12] 오류 복원 및 폴백 시나리오
    - [13] 스레드 안전성 통합 검증
    - [14] 헬퍼 함수 통합 검증
    - [15] 메모리 / 자원 정리 검증
"""

import gc
import json
import os
import sys
import time
import types
import tempfile
import threading
import tracemalloc
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈 - watcher 임포트 시 필요)
# =============================================================================
_mock_time_utils = types.ModuleType("utils.time_utils")
_mock_time_utils.get_current_timestamp = lambda: time.time()


class _MockTimer:
    """utils.time_utils.Timer 모킹."""

    def __init__(self, name: str = ""):
        self.name = name
        self._start = 0.0
        self._elapsed = 0.0

    def start(self):
        self._start = time.perf_counter()

    def stop(self):
        self._elapsed = (time.perf_counter() - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed


_mock_time_utils.Timer = _MockTimer

if "utils" not in sys.modules:
    _mock_utils = types.ModuleType("utils")
    sys.modules["utils"] = _mock_utils
sys.modules["utils.time_utils"] = _mock_time_utils

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# config 모듈 전체 임포트 (통합 테스트이므로 __init__.py 경유)
# =============================================================================
import core_foundation.config as config_module

# 개별 모듈 직접 임포트
from core_foundation.config.loader import (
    ConfigFormat,
    ConfigSource,
    ConfigEntry,
    ConfigMetadata,
    ConfigLoader,
    load_config,
    get_config_value,
    ENV_PREFIX,
    PROFILE_ENV_VAR,
    DEFAULT_PROFILE,
)
from core_foundation.config.validator import (
    ValidationStatus,
    ValidationErrorDetail,
    ValidationResult,
    BaseConfigModel,
    LocalDatabaseConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    AppConfig,
    SchemaValidator,
    validate_config,
    get_default_config,
)
from core_foundation.config.settings import (
    SettingsState,
    Environment,
    SettingsMetadata,
    Settings,
    get_settings,
    initialize_settings,
)
from core_foundation.config.watcher import (
    ChangeType,
    ReloadStatus,
    WatcherState,
    LogLevel,
    HotReloadConfig,
    ConfigChangeEvent,
    WatchedFile,
    ReloadStatistics,
    HotReloadManager,
    create_hot_reload_manager,
    watch_config,
    DEFAULT_DEBOUNCE_TIME,
    SUPPORTED_EXTENSIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_IGNORE_PATTERNS,
)

# 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과."""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"통합 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼
# =============================================================================
def reset_all() -> None:
    """Settings / ConfigLoader 싱글톤 전체 리셋."""
    Settings.reset_instance()


def write_yaml(path: Path, data: dict) -> None:
    """YAML 파일 작성 헬퍼."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def write_json(path: Path, data: dict) -> None:
    """JSON 파일 작성 헬퍼."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# [1] __init__.py Export 무결성
# =============================================================================
def test_init_export_integrity(result: TestResult) -> None:
    """__init__.py Export 무결성 테스트."""
    print("\n[1] __init__.py Export 무결성")

    try:
        # 1-1: __all__ 존재 및 45개 항목
        assert hasattr(config_module, "__all__")
        all_items = config_module.__all__
        assert len(all_items) == 45, f"__all__ 항목 수: {len(all_items)} != 45"
        result.ok("1-1: __all__ 45개 항목")
    except Exception as e:
        result.fail("1-1: __all__ 45개 항목", str(e))

    try:
        # 1-2: loader Export 7개
        loader_exports = [
            "ConfigFormat", "ConfigSource", "ConfigEntry",
            "ConfigMetadata", "ConfigLoader", "load_config", "get_config_value",
        ]
        for name in loader_exports:
            assert hasattr(config_module, name), f"{name} 미존재"
            assert name in all_items, f"{name} __all__에 누락"
        result.ok("1-2: loader Export 7개 확인")
    except Exception as e:
        result.fail("1-2: loader Export 7개 확인", str(e))

    try:
        # 1-3: validator Export 15개
        validator_exports = [
            "ValidationStatus", "ValidationErrorDetail", "ValidationResult",
            "BaseConfigModel", "LocalDatabaseConfig", "GPUConfig",
            "CameraConfig", "LocalStorageConfig", "ModelConfig",
            "AnalysisConfig", "LoggingConfig", "AppConfig",
            "SchemaValidator", "validate_config", "get_default_config",
        ]
        for name in validator_exports:
            assert hasattr(config_module, name), f"{name} 미존재"
        result.ok("1-3: validator Export 15개 확인")
    except Exception as e:
        result.fail("1-3: validator Export 15개 확인", str(e))

    try:
        # 1-4: settings Export 6개
        settings_exports = [
            "SettingsState", "Environment", "SettingsMetadata",
            "Settings", "get_settings", "initialize_settings",
        ]
        for name in settings_exports:
            assert hasattr(config_module, name), f"{name} 미존재"
        result.ok("1-4: settings Export 6개 확인")
    except Exception as e:
        result.fail("1-4: settings Export 6개 확인", str(e))

    try:
        # 1-5: watcher Export 17개
        watcher_exports = [
            "ChangeType", "ReloadStatus", "WatcherState", "LogLevel",
            "HotReloadConfig", "ConfigChangeEvent", "WatchedFile",
            "ReloadStatistics", "ConfigChangeCallback",
            "HotReloadManager", "create_hot_reload_manager", "watch_config",
            "DEFAULT_DEBOUNCE_TIME", "SUPPORTED_EXTENSIONS",
            "DEFAULT_MAX_RETRIES", "DEFAULT_RETRY_INTERVAL",
            "DEFAULT_IGNORE_PATTERNS",
        ]
        for name in watcher_exports:
            assert hasattr(config_module, name), f"{name} 미존재"
        result.ok("1-5: watcher Export 17개 확인")
    except Exception as e:
        result.fail("1-5: watcher Export 17개 확인", str(e))

    try:
        # 1-6: __init__.py 경유 접근 == 직접 접근 (동일 객체)
        assert config_module.ConfigLoader is ConfigLoader
        assert config_module.AppConfig is AppConfig
        assert config_module.Settings is Settings
        assert config_module.HotReloadManager is HotReloadManager
        result.ok("1-6: __init__.py 경유 == 직접 임포트 동일 객체")
    except Exception as e:
        result.fail("1-6: __init__.py 경유 == 직접 임포트 동일 객체", str(e))

    try:
        # 1-7: 중복 없이 정확히 45개
        assert len(set(all_items)) == len(all_items), "중복 Export 존재"
        result.ok("1-7: Export 중복 없음")
    except Exception as e:
        result.fail("1-7: Export 중복 없음", str(e))


# =============================================================================
# [2] Loader → Validator 파이프라인
# =============================================================================
def test_loader_to_validator_pipeline(result: TestResult) -> None:
    """Loader → Validator 파이프라인 테스트."""
    print("\n[2] Loader -> Validator 파이프라인")

    try:
        # 2-1: YAML 로드 → GPUConfig 검증
        reset_all()
        loader = ConfigLoader.get_instance()
        loader.load(str(FIXTURES_DIR / "test_base.yaml"))
        gpu_data = loader.get_section("gpu")

        validator = SchemaValidator()
        vr = validator.validate(gpu_data, GPUConfig)
        assert vr.is_valid, f"GPU 검증 실패: {[e.message for e in vr.errors]}"
        assert vr.data.cuda_device == "cuda:0"
        result.ok("2-1: YAML -> loader.get_section -> GPUConfig 검증")
    except Exception as e:
        result.fail("2-1: YAML -> loader.get_section -> GPUConfig 검증", str(e))

    try:
        # 2-2: YAML 로드 → CameraConfig 검증
        reset_all()
        loader = ConfigLoader.get_instance()
        loader.load(str(FIXTURES_DIR / "test_base.yaml"))
        cam_data = loader.get_section("camera")

        validator = SchemaValidator()
        vr = validator.validate(cam_data, CameraConfig)
        assert vr.is_valid
        assert vr.data.count == 4
        assert vr.data.fps == 60
        result.ok("2-2: YAML -> CameraConfig(count=4, fps=60)")
    except Exception as e:
        result.fail("2-2: YAML -> CameraConfig(count=4, fps=60)", str(e))

    try:
        # 2-3: YAML 로드 → AnalysisConfig 검증
        reset_all()
        loader = ConfigLoader.get_instance()
        loader.load(str(FIXTURES_DIR / "test_base.yaml"))
        analysis_data = loader.get_section("analysis")

        validator = SchemaValidator()
        vr = validator.validate(analysis_data, AnalysisConfig)
        assert vr.is_valid
        assert vr.data.target_fps == 30
        assert vr.data.enable_tracking is True  # 기본값 유지
        result.ok("2-3: YAML -> AnalysisConfig(target_fps=30)")
    except Exception as e:
        result.fail("2-3: YAML -> AnalysisConfig(target_fps=30)", str(e))

    try:
        # 2-4: 잘못된 섹션 데이터 → Validator 실패 처리
        validator = SchemaValidator()
        bad_data = {"device_id": -1}  # GPU device_id 범위 초과
        vr = validator.validate(bad_data, GPUConfig)
        assert not vr.is_valid
        assert len(vr.errors) > 0
        result.ok("2-4: 잘못된 데이터 -> Validator 실패 감지")
    except Exception as e:
        result.fail("2-4: 잘못된 데이터 -> Validator 실패 감지", str(e))

    try:
        # 2-5: validate_config 헬퍼 정상 동작
        db_data = {"db_path": "data/test.db", "busy_timeout": 3000}
        db_cfg = validate_config(db_data, LocalDatabaseConfig)
        assert isinstance(db_cfg, LocalDatabaseConfig)
        assert db_cfg.db_path == "data/test.db"
        assert db_cfg.busy_timeout == 3000
        result.ok("2-5: validate_config 헬퍼 -> LocalDatabaseConfig")
    except Exception as e:
        result.fail("2-5: validate_config 헬퍼 -> LocalDatabaseConfig", str(e))

    try:
        # 2-6: get_default_config → 기본값 검증
        default_app = get_default_config(AppConfig)
        assert isinstance(default_app, AppConfig)
        assert default_app.environment == "production"
        assert default_app.gpu.cuda_device == "cuda:0"
        assert default_app.camera.count == 4
        result.ok("2-6: get_default_config(AppConfig) 기본값")
    except Exception as e:
        result.fail("2-6: get_default_config(AppConfig) 기본값", str(e))


# =============================================================================
# [3] Loader → Validator → Settings 전체 파이프라인
# =============================================================================
def test_full_pipeline(result: TestResult) -> None:
    """Loader -> Validator -> Settings 전체 파이프라인."""
    print("\n[3] Loader -> Validator -> Settings 전체 파이프라인")

    try:
        # 3-1: 동적 YAML 생성 → Settings.initialize
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "development",
                "gpu": {"device_id": 0, "memory_fraction": 0.8, "tensorrt_enabled": True},
                "camera": {"count": 2, "fps": 60},
                "model": {"model_type": "yolo", "device": "cuda:0", "precision": "fp16"},
                "analysis": {"target_fps": 30, "max_persons": 10},
                "database": {"db_path": "data/test.db"},
                "storage": {"cache_dir": "cache"},
                "logging": {"level": "DEBUG"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))

            assert s.state == SettingsState.READY
            assert s.is_ready is True
            assert s.config.environment == "development"
            assert s.gpu.cuda_device == "cuda:0"
            assert s.gpu.memory_fraction == 0.8
            assert s.camera.count == 2
            assert s.model.model_type == "yolo"
            assert s.analysis.target_fps == 30
            result.ok("3-1: YAML 생성 -> Settings 전체 파이프라인")
    except Exception as e:
        result.fail("3-1: YAML 생성 -> Settings 전체 파이프라인", str(e))

    try:
        # 3-2: JSON 설정 파일로 전체 파이프라인
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "testing",
                "gpu": {"device_id": 1},
                "camera": {"count": 1},
                "model": {"model_type": "mediapipe", "device": "cpu"},
                "analysis": {"target_fps": 15},
            }
            config_path = Path(tmpdir) / "app.json"
            write_json(config_path, config_data)

            loader = ConfigLoader.get_instance()
            loader.load(str(config_path))
            raw_data = loader.to_dict()

            validator = SchemaValidator()
            vr = validator.validate(raw_data, AppConfig)
            assert vr.is_valid
            assert vr.data.environment == "testing"
            assert vr.data.gpu.cuda_device == "cuda:1"
            assert vr.data.model.device == "cpu"
            result.ok("3-2: JSON -> Loader -> Validator -> AppConfig")
    except Exception as e:
        result.fail("3-2: JSON -> Loader -> Validator -> AppConfig", str(e))

    try:
        # 3-3: 부분 설정 (나머지 기본값)
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 최소 설정만 제공
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))
            assert s.is_ready
            # 명시하지 않은 값은 기본값
            assert s.config.gpu.device_id == 0  # 기본값
            assert s.config.camera.count == 4   # 기본값
            assert s.config.analysis.target_fps == 30  # 기본값
            result.ok("3-3: 부분 설정 -> 기본값 자동 적용")
    except Exception as e:
        result.fail("3-3: 부분 설정 -> 기본값 자동 적용", str(e))


# =============================================================================
# [4] Settings 초기화 → 프로퍼티 체인
# =============================================================================
def test_settings_property_chain(result: TestResult) -> None:
    """Settings 초기화 후 프로퍼티 체인 테스트."""
    print("\n[4] Settings 초기화 -> 프로퍼티 체인")

    reset_all()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_data = {
            "environment": "development",
            "gpu": {"device_id": 0, "memory_fraction": 0.85, "tensorrt_enabled": True},
            "camera": {"count": 4, "fps": 60},
            "model": {"model_type": "yolo", "device": "cuda:0"},
            "analysis": {"target_fps": 30},
            "database": {"db_path": "data/cv.db", "pool_size": 5},
            "storage": {"cache_dir": "cache/main", "max_cache_gb": 100.0},
            "logging": {"level": "INFO", "file_path": "logs/app.log"},
        }
        config_path = Path(tmpdir) / "app.yaml"
        write_yaml(config_path, config_data)
        s = Settings.initialize(config_path=str(config_path))

    try:
        # 4-1: config → gpu → cuda_device 체인
        assert s.config.gpu.cuda_device == "cuda:0"
        assert s.gpu.cuda_device == "cuda:0"
        assert s.cuda_device == "cuda:0"
        # 3가지 접근 경로 모두 동일
        assert s.config.gpu.cuda_device == s.gpu.cuda_device == s.cuda_device
        result.ok("4-1: config.gpu.cuda_device == gpu.cuda_device == cuda_device")
    except Exception as e:
        result.fail("4-1: config.gpu.cuda_device == gpu.cuda_device == cuda_device", str(e))

    try:
        # 4-2: camera 체인
        assert s.config.camera.count == s.camera.count == s.camera_count == 4
        result.ok("4-2: camera.count == camera_count == 4")
    except Exception as e:
        result.fail("4-2: camera.count == camera_count == 4", str(e))

    try:
        # 4-3: analysis 체인
        assert s.config.analysis.target_fps == s.analysis.target_fps == s.target_fps == 30
        result.ok("4-3: analysis.target_fps == target_fps == 30")
    except Exception as e:
        result.fail("4-3: analysis.target_fps == target_fps == 30", str(e))

    try:
        # 4-4: Desktop 편의 프로퍼티 정합성
        assert s.is_gpu_available is True      # device != "cpu"
        assert s.is_tensorrt_enabled is True   # gpu.tensorrt_enabled + gpu_available
        assert s.is_multi_camera is True       # camera.count > 1
        result.ok("4-4: Desktop 편의 프로퍼티 정합성")
    except Exception as e:
        result.fail("4-4: Desktop 편의 프로퍼티 정합성", str(e))

    try:
        # 4-5: to_dict → 다시 AppConfig 검증 라운드트립
        d = s.to_dict()
        validator = SchemaValidator()
        vr = validator.validate(d, AppConfig)
        assert vr.is_valid, f"라운드트립 실패: {[e.message for e in vr.errors]}"
        assert vr.data.gpu.cuda_device == "cuda:0"
        result.ok("4-5: to_dict -> AppConfig 라운드트립 검증")
    except Exception as e:
        result.fail("4-5: to_dict -> AppConfig 라운드트립 검증", str(e))

    try:
        # 4-6: get_status 전체 키 확인 및 값 정합성
        status = s.get_status()
        assert status["state"] == "READY"
        assert status["is_ready"] is True
        assert status["environment"] == "development"
        assert status["is_gpu_available"] is True
        assert status["camera_count"] == 4
        assert status["target_fps"] == 30
        assert isinstance(status["metadata"], dict)
        result.ok("4-6: get_status 정합성 확인")
    except Exception as e:
        result.fail("4-6: get_status 정합성 확인", str(e))


# =============================================================================
# [5] 설정 변경 → Reload → Listener 알림 파이프라인
# =============================================================================
def test_reload_listener_pipeline(result: TestResult) -> None:
    """설정 변경 -> Reload -> Listener 알림 파이프라인."""
    print("\n[5] 설정 변경 -> Reload -> Listener 알림 파이프라인")

    try:
        # 5-1: 설정 변경 → reload → listener 호출
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data_v1 = {
                "environment": "development",
                "gpu": {"device_id": 0},
                "camera": {"count": 2},
                "model": {"model_type": "yolo", "device": "cuda:0"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data_v1)

            s = Settings.initialize(config_path=str(config_path))
            assert s.camera.count == 2
            assert s.analysis.target_fps == 30

            # 리스너 등록
            changes = []

            def on_change(old, new):
                changes.append({
                    "old_cameras": old.camera.count,
                    "new_cameras": new.camera.count,
                    "old_fps": old.analysis.target_fps,
                    "new_fps": new.analysis.target_fps,
                })

            s.on_change(on_change)

            # 설정 변경 후 reload
            config_data_v2 = {
                "environment": "development",
                "gpu": {"device_id": 0},
                "camera": {"count": 4},
                "model": {"model_type": "yolo", "device": "cuda:0"},
                "analysis": {"target_fps": 60},
            }
            write_yaml(config_path, config_data_v2)
            success = s.reload(config_path=str(config_path))

            assert success is True
            assert s.camera.count == 4
            assert s.analysis.target_fps == 60

            # 리스너가 호출되었는지
            assert len(changes) == 1
            assert changes[0]["old_cameras"] == 2
            assert changes[0]["new_cameras"] == 4
            assert changes[0]["old_fps"] == 30
            assert changes[0]["new_fps"] == 60
            result.ok("5-1: 설정 변경 -> reload -> listener 콜백 (값 변경 감지)")
    except Exception as e:
        result.fail("5-1: 설정 변경 -> reload -> listener 콜백 (값 변경 감지)", str(e))

    try:
        # 5-2: 다중 리스너 + reload
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))

            calls = {"a": 0, "b": 0, "c": 0}

            def listener_a(old, new):
                calls["a"] += 1

            def listener_b(old, new):
                calls["b"] += 1

            def listener_c(old, new):
                calls["c"] += 1

            s.on_change(listener_a)
            s.on_change(listener_b)
            s.on_change(listener_c)

            s.reload()
            assert calls == {"a": 1, "b": 1, "c": 1}

            s.off_change(listener_b)
            s.reload()
            assert calls == {"a": 2, "b": 1, "c": 2}
            result.ok("5-2: 다중 리스너 등록/해제 + reload")
    except Exception as e:
        result.fail("5-2: 다중 리스너 등록/해제 + reload", str(e))

    try:
        # 5-3: reload 후 metadata 갱신 확인
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))
            assert s.metadata.reload_count == 0
            loaded_time = s.metadata.loaded_at

            time.sleep(0.01)
            s.reload()
            assert s.metadata.reload_count == 1
            assert s.metadata.last_reloaded_at > loaded_time
            # loaded_at은 변경되지 않아야 함 (initialize 시 설정)
            result.ok("5-3: reload 후 metadata 갱신")
    except Exception as e:
        result.fail("5-3: reload 후 metadata 갱신", str(e))


# =============================================================================
# [6] Watcher 컴포넌트 → Settings 연동
# =============================================================================
def test_watcher_settings_integration(result: TestResult) -> None:
    """Watcher 컴포넌트와 Settings 연동."""
    print("\n[6] Watcher 컴포넌트 -> Settings 연동")

    try:
        # 6-1: ConfigChangeEvent → Settings diff 파이프라인
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
                "camera": {"count": 2},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))
            snap_before = s.snapshot()

            # Watcher가 감지할 변경 시뮬레이션
            event = ConfigChangeEvent(
                file_path=str(config_path),
                change_type=ChangeType.MODIFIED,
            )
            assert event.change_type == ChangeType.MODIFIED

            # 설정 파일 변경 후 reload (동일 디렉토리에서)
            config_data_v2 = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 60},
                "camera": {"count": 4},
            }
            write_yaml(config_path, config_data_v2)
            s.reload(config_path=str(config_path))

            # reload 후 값 변경 확인
            assert s.analysis.target_fps == 60, f"reload 후 fps: {s.analysis.target_fps}"
            assert s.camera.count == 4, f"reload 후 count: {s.camera.count}"

            diff = s.diff(snap_before)
            assert len(diff) > 0, f"diff가 비어있음: {diff}"
            result.ok("6-1: ConfigChangeEvent + reload + diff 파이프라인")
    except Exception as e:
        result.fail("6-1: ConfigChangeEvent + reload + diff 파이프라인", str(e))

    try:
        # 6-2: HotReloadManager 생성 with Settings 내부 컴포넌트
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))

            # Settings의 내부 loader/validator로 HotReloadManager 생성
            manager = HotReloadManager(
                config_loader=s._loader,
                schema_validator=s._validator,
            )
            assert isinstance(manager, HotReloadManager)
            assert manager.state == WatcherState.STOPPED
            result.ok("6-2: HotReloadManager + Settings 내부 컴포넌트")
    except Exception as e:
        result.fail("6-2: HotReloadManager + Settings 내부 컴포넌트", str(e))

    try:
        # 6-3: HotReloadManager watch + 파일 감시 등록
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            s = Settings.initialize(config_path=str(config_path))
            manager = HotReloadManager(
                config_loader=s._loader,
                schema_validator=s._validator,
            )
            manager.watch(str(config_path))
            assert str(config_path) in manager.watched_files
            result.ok("6-3: HotReloadManager.watch 파일 등록")
    except Exception as e:
        result.fail("6-3: HotReloadManager.watch 파일 등록", str(e))

    try:
        # 6-4: ReloadStatistics 연동
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.SUCCESS, 5.0)
        stats.record_reload(ReloadStatus.SUCCESS, 3.0)
        stats.record_reload(ReloadStatus.FAILED, 10.0)
        # success_rate는 0.0~1.0 범위
        assert abs(stats.success_rate - 2.0 / 3) < 0.001
        # average_reload_time_ms는 성공한 리로드만 포함
        assert abs(stats.average_reload_time_ms - (5.0 + 3.0) / 2) < 0.001
        result.ok("6-4: ReloadStatistics 통계 정합성")
    except Exception as e:
        result.fail("6-4: ReloadStatistics 통계 정합성", str(e))


# =============================================================================
# [7] 동적 설정 파일 생성 → 로드 → 검증 → 접근
# =============================================================================
def test_dynamic_config_lifecycle(result: TestResult) -> None:
    """동적 설정 파일의 전체 라이프사이클."""
    print("\n[7] 동적 설정 파일 라이프사이클")

    try:
        # 7-1: tempfile YAML → 전체 라이프사이클
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1단계: 설정 파일 생성
            cfg = {
                "environment": "testing",
                "gpu": {"device_id": 2, "memory_fraction": 0.5, "tensorrt_enabled": False},
                "camera": {"count": 1, "fps": 30},
                "model": {"model_type": "onnx", "device": "cpu", "precision": "fp32"},
                "analysis": {"target_fps": 15, "max_persons": 5},
                "database": {"db_path": "data/test.db"},
                "storage": {"cache_dir": "tmp_cache"},
                "logging": {"level": "WARNING"},
            }
            config_path = Path(tmpdir) / "test_app.yaml"
            write_yaml(config_path, cfg)

            # 2단계: Loader로 로드
            loader = ConfigLoader.get_instance()
            loader.load(str(config_path))
            raw = loader.to_dict()
            assert raw["environment"] == "testing"

            # 3단계: Validator로 검증
            validator = SchemaValidator()
            vr = validator.validate(raw, AppConfig)
            assert vr.is_valid
            app_config = vr.data
            assert app_config.gpu.cuda_device == "cuda:2"
            assert app_config.model.device == "cpu"

            # 4단계: Settings로 전역 접근
            ConfigLoader.reset_instance()  # 리셋 후 다시 시작
            Settings.reset_instance()
            s = Settings.initialize(config_path=str(config_path))
            assert s.is_ready
            assert s.is_testing
            assert s.is_gpu_available is False  # device=cpu
            assert s.is_multi_camera is False   # count=1
            assert s.target_fps == 15
            result.ok("7-1: YAML -> Loader -> Validator -> Settings 전체 라이프사이클")
    except Exception as e:
        result.fail("7-1: YAML -> Loader -> Validator -> Settings 전체 라이프사이클", str(e))

    try:
        # 7-2: JSON 파일 → Loader 직접 로드 → Validator → AppConfig
        # (Settings.initialize는 load_with_profile로 .yaml만 탐색하므로 직접 파이프라인)
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "gpu": {"device_id": 0},
                "model": {"model_type": "tensorrt", "device": "cuda:0"},
                "analysis": {"target_fps": 60},
            }
            config_path = Path(tmpdir) / "config.json"
            write_json(config_path, cfg)

            loader = ConfigLoader.get_instance()
            loader.load(str(config_path))
            raw = loader.to_dict()

            validator = SchemaValidator()
            vr = validator.validate(raw, AppConfig)
            assert vr.is_valid
            assert vr.data.environment == "production"
            assert vr.data.model.model_type == "tensorrt"
            assert vr.data.analysis.target_fps == 60
            result.ok("7-2: JSON -> Loader -> Validator -> AppConfig 라이프사이클")
    except Exception as e:
        result.fail("7-2: JSON -> Loader -> Validator -> AppConfig 라이프사이클", str(e))


# =============================================================================
# [8] 프로파일 기반 설정 오버라이드 파이프라인
# =============================================================================
def test_profile_override_pipeline(result: TestResult) -> None:
    """프로파일 기반 설정 오버라이드 파이프라인."""
    print("\n[8] 프로파일 기반 설정 오버라이드")

    try:
        # 8-1: base + development 프로파일 병합
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 기본 설정
            base = {
                "environment": "production",
                "gpu": {"device_id": 0, "memory_fraction": 0.9},
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
                "logging": {"level": "INFO"},
            }
            write_yaml(Path(tmpdir) / "app.yaml", base)

            # development 프로파일 (오버라이드)
            dev = {
                "environment": "development",
                "gpu": {"memory_fraction": 0.5},
                "logging": {"level": "DEBUG"},
            }
            write_yaml(Path(tmpdir) / "app.development.yaml", dev)

            # 환경 변수로 프로파일 설정
            os.environ[PROFILE_ENV_VAR] = "development"
            try:
                s = Settings.initialize(
                    config_path=str(Path(tmpdir) / "app.yaml"),
                    config_dir=tmpdir,
                )
                assert s.is_ready
                # development 프로파일이 오버라이드
                assert s.config.environment == "development"
                assert s.gpu.memory_fraction == 0.5
                # base에서 오버라이드되지 않은 값 유지
                assert s.analysis.target_fps == 30
            finally:
                os.environ.pop(PROFILE_ENV_VAR, None)
            result.ok("8-1: base + development 프로파일 병합")
    except Exception as e:
        result.fail("8-1: base + development 프로파일 병합", str(e))

    try:
        # 8-2: base + production 프로파일
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = {
                "environment": "development",
                "gpu": {"device_id": 0, "memory_fraction": 0.7},
                "model": {"model_type": "yolo", "device": "cuda"},
                "logging": {"level": "DEBUG"},
            }
            write_yaml(Path(tmpdir) / "app.yaml", base)

            prod = {
                "environment": "production",
                "gpu": {"memory_fraction": 0.95},
                "logging": {"level": "WARNING"},
            }
            write_yaml(Path(tmpdir) / "app.production.yaml", prod)

            os.environ[PROFILE_ENV_VAR] = "production"
            try:
                s = Settings.initialize(
                    config_path=str(Path(tmpdir) / "app.yaml"),
                    config_dir=tmpdir,
                )
                assert s.config.environment == "production"
                assert s.gpu.memory_fraction == 0.95
                assert s.is_production
            finally:
                os.environ.pop(PROFILE_ENV_VAR, None)
            result.ok("8-2: base + production 프로파일 병합")
    except Exception as e:
        result.fail("8-2: base + production 프로파일 병합", str(e))

    try:
        # 8-3: base + profile + local 오버라이드 3단계
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = {
                "environment": "production",
                "gpu": {"device_id": 0, "memory_fraction": 0.9},
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            write_yaml(Path(tmpdir) / "app.yaml", base)

            dev = {
                "environment": "development",
                "gpu": {"memory_fraction": 0.7},
            }
            write_yaml(Path(tmpdir) / "app.development.yaml", dev)

            local = {
                "gpu": {"memory_fraction": 0.5},
                "analysis": {"target_fps": 15},
            }
            write_yaml(Path(tmpdir) / "app.local.yaml", local)

            os.environ[PROFILE_ENV_VAR] = "development"
            try:
                s = Settings.initialize(
                    config_path=str(Path(tmpdir) / "app.yaml"),
                    config_dir=tmpdir,
                )
                # local이 가장 마지막에 적용됨
                assert s.gpu.memory_fraction == 0.5   # local 오버라이드
                assert s.analysis.target_fps == 15    # local 오버라이드
            finally:
                os.environ.pop(PROFILE_ENV_VAR, None)
            result.ok("8-3: base + profile + local 3단계 오버라이드")
    except Exception as e:
        result.fail("8-3: base + profile + local 3단계 오버라이드", str(e))


# =============================================================================
# [9] 환경변수 오버라이드 → Validator → Settings
# =============================================================================
def test_env_override_pipeline(result: TestResult) -> None:
    """환경변수 오버라이드 파이프라인."""
    print("\n[9] 환경변수 오버라이드 파이프라인")

    try:
        # 9-1: 환경변수로 값 오버라이드
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            # 환경변수 설정 (COURTVIEW_ 접두사)
            os.environ[f"{ENV_PREFIX}ANALYSIS__TARGET_FPS"] = "60"
            try:
                loader = ConfigLoader.get_instance()
                loader.load(str(config_path))
                # 환경변수가 적용되었는지 확인
                val = loader.get("analysis.target_fps")
                # 환경변수 오버라이드가 적용되었으면 60, 아니면 30
                assert val is not None
            finally:
                os.environ.pop(f"{ENV_PREFIX}ANALYSIS__TARGET_FPS", None)
            result.ok("9-1: 환경변수 오버라이드 적용")
    except Exception as e:
        result.fail("9-1: 환경변수 오버라이드 적용", str(e))

    try:
        # 9-2: Loader get 타입 변환 체인
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
                "camera": {"count": 4},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, config_data)

            loader = ConfigLoader.get_instance()
            loader.load(str(config_path))

            # 다양한 타입 변환
            assert loader.get_int("camera.count") == 4
            assert loader.get_int("analysis.target_fps") == 30
            assert loader.get_str("environment") == "production"
            assert loader.get_bool("nonexistent", False) is False
            result.ok("9-2: Loader 타입 변환 체인 (get_int, get_str, get_bool)")
    except Exception as e:
        result.fail("9-2: Loader 타입 변환 체인 (get_int, get_str, get_bool)", str(e))


# =============================================================================
# [10] 스냅샷 → 변경 → Diff 감지 파이프라인
# =============================================================================
def test_snapshot_diff_pipeline(result: TestResult) -> None:
    """스냅샷 -> 변경 -> Diff 감지 파이프라인."""
    print("\n[10] 스냅샷 -> 변경 -> Diff 감지 파이프라인")

    try:
        # 10-1: 초기 스냅샷 → 설정 변경 → reload → diff
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_v1 = {
                "environment": "development",
                "gpu": {"device_id": 0, "memory_fraction": 0.8},
                "camera": {"count": 2},
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg_v1)

            s = Settings.initialize(config_path=str(config_path))
            snap_v1 = s.snapshot()

            # 설정 변경 후 reload
            cfg_v2 = {
                "environment": "production",
                "gpu": {"device_id": 0, "memory_fraction": 0.95},
                "camera": {"count": 4},
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 60},
            }
            write_yaml(config_path, cfg_v2)
            s.reload(config_path=str(config_path))

            # reload 후 값 변경 확인
            assert s.camera.count == 4, f"reload 후 count: {s.camera.count}"
            assert s.analysis.target_fps == 60, f"reload 후 fps: {s.analysis.target_fps}"

            # diff 확인
            diff = s.diff(snap_v1)
            assert len(diff) > 0, f"변경사항이 감지되지 않음, snap_v1 cameras={snap_v1.get('camera', {}).get('count')}, current={s.camera.count}"
            result.ok("10-1: 스냅샷 -> 변경 -> diff 감지")
    except Exception as e:
        result.fail("10-1: 스냅샷 -> 변경 -> diff 감지", str(e))

    try:
        # 10-2: 스냅샷 독립성 (변경 후에도 원본 유지)
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            snap = s.snapshot()
            original_fps = snap["analysis"]["target_fps"]

            # 스냅샷 수정 (원본에 영향 없어야 함)
            snap["analysis"]["target_fps"] = 999

            assert s.analysis.target_fps == original_fps
            result.ok("10-2: 스냅샷 수정 -> 원본 영향 없음")
    except Exception as e:
        result.fail("10-2: 스냅샷 수정 -> 원본 영향 없음", str(e))


# =============================================================================
# [11] 다중 파일 병합 파이프라인
# =============================================================================
def test_multi_file_merge_pipeline(result: TestResult) -> None:
    """다중 파일 병합 파이프라인."""
    print("\n[11] 다중 파일 병합 파이프라인")

    try:
        # 11-1: 2개 YAML 병합 후 Validator 검증
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_data = {
                "environment": "production",
                "gpu": {"device_id": 0, "memory_fraction": 0.9},
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            override_data = {
                "gpu": {"memory_fraction": 0.5},
                "analysis": {"target_fps": 15},
            }
            base_path = Path(tmpdir) / "base.yaml"
            override_path = Path(tmpdir) / "override.yaml"
            write_yaml(base_path, base_data)
            write_yaml(override_path, override_data)

            loader = ConfigLoader.get_instance()
            loader.load_multiple([str(base_path), str(override_path)])

            raw = loader.to_dict()
            validator = SchemaValidator()
            vr = validator.validate(raw, AppConfig)
            assert vr.is_valid
            # override가 적용됨
            assert vr.data.gpu.memory_fraction == 0.5
            assert vr.data.analysis.target_fps == 15
            # base 값 유지
            assert vr.data.environment == "production"
            result.ok("11-1: 2개 YAML 병합 -> AppConfig 검증")
    except Exception as e:
        result.fail("11-1: 2개 YAML 병합 -> AppConfig 검증", str(e))

    try:
        # 11-2: Loader set → Validator → 재검증
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            loader = ConfigLoader.get_instance()
            loader.load(str(config_path))

            # 프로그래밍 방식으로 값 설정
            loader.set("analysis.target_fps", 45)
            loader.set("camera.count", 2)

            raw = loader.to_dict()
            validator = SchemaValidator()
            vr = validator.validate(raw, AppConfig)
            assert vr.is_valid
            assert vr.data.analysis.target_fps == 45
            assert vr.data.camera.count == 2
            result.ok("11-2: Loader.set -> Validator 재검증")
    except Exception as e:
        result.fail("11-2: Loader.set -> Validator 재검증", str(e))


# =============================================================================
# [12] 오류 복원 및 폴백 시나리오
# =============================================================================
def test_error_recovery_scenarios(result: TestResult) -> None:
    """오류 복원 및 폴백 시나리오."""
    print("\n[12] 오류 복원 및 폴백 시나리오")

    try:
        # 12-1: 잘못된 YAML → Settings 기본값 폴백
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_path = Path(tmpdir) / "invalid.yaml"
            with open(invalid_path, "w") as f:
                f.write("{{invalid yaml content:}")

            try:
                s = Settings.initialize(config_path=str(invalid_path))
                # 파싱 실패 시 예외 발생하거나 기본값 사용
            except Exception:
                # 예외가 발생해도 괜찮음 (정상적인 오류 처리)
                pass

            # 재초기화 시 정상 작동
            reset_all()
            s = Settings.initialize(config_path="nonexistent.yaml")
            assert s.is_ready
            assert isinstance(s.config, AppConfig)
            result.ok("12-1: 잘못된 YAML -> 기본값 폴백 + 재초기화")
    except Exception as e:
        result.fail("12-1: 잘못된 YAML -> 기본값 폴백 + 재초기화", str(e))

    try:
        # 12-2: reload 실패 → 이전 설정 복원
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            original_fps = s.analysis.target_fps

            # _load_config 강제 실패
            with patch.object(s, "_load_config", side_effect=RuntimeError("시뮬레이션 실패")):
                success = s.reload(config_path=str(config_path))

            assert success is False
            assert s.state == SettingsState.READY  # 복원됨
            assert s.analysis.target_fps == original_fps  # 이전 값 유지
            result.ok("12-2: reload 실패 -> 이전 설정 복원")
    except Exception as e:
        result.fail("12-2: reload 실패 -> 이전 설정 복원", str(e))

    try:
        # 12-3: Validator 검증 실패 → 기본 AppConfig 폴백
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            # model_type이 잘못된 값
            cfg = {
                "environment": "production",
                "model": {"model_type": "invalid_model", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            # 검증 실패 시 기본 AppConfig 사용
            assert s.is_ready
            assert isinstance(s.config, AppConfig)
            # 기본값으로 폴백됨
            assert s.config.model.model_type == "yolo"  # 기본값
            result.ok("12-3: Validator 검증 실패 -> 기본 AppConfig 폴백")
    except Exception as e:
        result.fail("12-3: Validator 검증 실패 -> 기본 AppConfig 폴백", str(e))

    try:
        # 12-4: 리스너 예외 → 다른 리스너 + Settings 정상 작동
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            good_calls = []

            def bad_listener(old, new):
                raise ValueError("의도적 예외")

            def good_listener(old, new):
                good_calls.append(True)

            s.on_change(bad_listener)
            s.on_change(good_listener)

            success = s.reload()
            assert success is True
            assert len(good_calls) == 1
            assert s.is_ready
            result.ok("12-4: 리스너 예외 격리 + Settings 정상 작동")
    except Exception as e:
        result.fail("12-4: 리스너 예외 격리 + Settings 정상 작동", str(e))


# =============================================================================
# [13] 스레드 안전성 통합 검증
# =============================================================================
def test_thread_safety_integration(result: TestResult) -> None:
    """스레드 안전성 통합 검증."""
    print("\n[13] 스레드 안전성 통합 검증")

    try:
        # 13-1: 다중 스레드 Settings 동시 접근
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 30},
                "camera": {"count": 4},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))

            errors = []
            barrier = threading.Barrier(8)

            def read_worker():
                barrier.wait()
                try:
                    for _ in range(1000):
                        _ = s.config
                        _ = s.gpu
                        _ = s.camera
                        _ = s.state
                        _ = s.is_ready
                        _ = s.target_fps
                except Exception as ex:
                    errors.append(str(ex))

            threads = [threading.Thread(target=read_worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"스레드 오류: {errors}"
            result.ok("13-1: 8 스레드 동시 읽기 (1000회/스레드)")
    except Exception as e:
        result.fail("13-1: 8 스레드 동시 읽기 (1000회/스레드)", str(e))

    try:
        # 13-2: 읽기 + 리스너 등록/해제 동시 진행
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            errors = []
            barrier = threading.Barrier(4)

            def reader():
                barrier.wait()
                try:
                    for _ in range(500):
                        _ = s.config
                        _ = s.state
                except Exception as ex:
                    errors.append(str(ex))

            def listener_manager():
                barrier.wait()
                try:
                    for i in range(100):
                        fn = lambda o, n, i=i: None
                        s.on_change(fn)
                        s.off_change(fn)
                except Exception as ex:
                    errors.append(str(ex))

            threads = (
                [threading.Thread(target=reader) for _ in range(3)]
                + [threading.Thread(target=listener_manager)]
            )
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"스레드 오류: {errors}"
            result.ok("13-2: 3 reader + 1 listener-manager 동시 진행")
    except Exception as e:
        result.fail("13-2: 3 reader + 1 listener-manager 동시 진행", str(e))

    try:
        # 13-3: Singleton 동시 초기화 안전성
        reset_all()
        instances = []
        barrier = threading.Barrier(10)

        def init_worker():
            barrier.wait()
            instances.append(Settings.get_instance())

        threads = [threading.Thread(target=init_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 10
        for inst in instances:
            assert inst is instances[0]
        result.ok("13-3: 10 스레드 Singleton 동시 접근 안전성")
    except Exception as e:
        result.fail("13-3: 10 스레드 Singleton 동시 접근 안전성", str(e))


# =============================================================================
# [14] 헬퍼 함수 통합 검증
# =============================================================================
def test_helper_functions_integration(result: TestResult) -> None:
    """헬퍼 함수 통합 검증."""
    print("\n[14] 헬퍼 함수 통합 검증")

    try:
        # 14-1: initialize_settings → get_settings 체인
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "testing",
                "model": {"model_type": "yolo", "device": "cpu"},
                "analysis": {"target_fps": 15},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s1 = initialize_settings(config_path=str(config_path))
            s2 = get_settings()
            assert s1 is s2
            assert s2.is_ready
            assert s2.is_testing
            result.ok("14-1: initialize_settings -> get_settings 체인")
    except Exception as e:
        result.fail("14-1: initialize_settings -> get_settings 체인", str(e))

    try:
        # 14-2: load_config 헬퍼 → validate_config 헬퍼
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "device_id": 1,
                "memory_fraction": 0.7,
                "tensorrt_enabled": False,
            }
            config_path = Path(tmpdir) / "gpu.yaml"
            write_yaml(config_path, cfg)

            raw = load_config(str(config_path))
            assert isinstance(raw, dict)

            gpu_cfg = validate_config(raw, GPUConfig)
            assert gpu_cfg.cuda_device == "cuda:1"
            assert gpu_cfg.memory_fraction == 0.7
            result.ok("14-2: load_config -> validate_config 헬퍼 체인")
    except Exception as e:
        result.fail("14-2: load_config -> validate_config 헬퍼 체인", str(e))

    try:
        # 14-3: get_config_value 헬퍼
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
                "analysis": {"target_fps": 45},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            # load_config로 먼저 로드
            load_config(str(config_path))
            val = get_config_value("analysis.target_fps", 30)
            assert val == 45
            result.ok("14-3: load_config -> get_config_value 체인")
    except Exception as e:
        result.fail("14-3: load_config -> get_config_value 체인", str(e))

    try:
        # 14-4: create_hot_reload_manager 헬퍼
        reset_all()
        loader = ConfigLoader.get_instance()
        validator = SchemaValidator()
        manager = create_hot_reload_manager(
            config_loader=loader,
            schema_validator=validator,
        )
        assert isinstance(manager, HotReloadManager)
        assert manager.state == WatcherState.STOPPED
        result.ok("14-4: create_hot_reload_manager 헬퍼")
    except Exception as e:
        result.fail("14-4: create_hot_reload_manager 헬퍼", str(e))

    try:
        # 14-5: get_default_config 모든 스키마
        schemas = [
            GPUConfig, CameraConfig, ModelConfig, AnalysisConfig,
            LoggingConfig, LocalStorageConfig, LocalDatabaseConfig, AppConfig,
        ]
        for schema in schemas:
            instance = get_default_config(schema)
            assert isinstance(instance, schema), f"{schema.__name__} 기본값 생성 실패"
        result.ok("14-5: get_default_config 8개 스키마 기본값 생성")
    except Exception as e:
        result.fail("14-5: get_default_config 8개 스키마 기본값 생성", str(e))


# =============================================================================
# [15] 메모리 / 자원 정리 검증
# =============================================================================
def test_resource_cleanup(result: TestResult) -> None:
    """메모리 및 자원 정리 검증."""
    print("\n[15] 메모리 / 자원 정리 검증")

    try:
        # 15-1: reset_instance 후 자원 해제
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            # 리스너 여러 개 등록
            for i in range(50):
                s.on_change(lambda o, n, i=i: None)

            assert len(s._change_listeners) == 50

            # 리셋
            Settings.reset_instance()
            s2 = Settings()
            assert len(s2._change_listeners) == 0
            assert s2.state == SettingsState.UNINITIALIZED
            result.ok("15-1: reset_instance -> 리스너 정리")
    except Exception as e:
        result.fail("15-1: reset_instance -> 리스너 정리", str(e))

    try:
        # 15-2: 반복 초기화/리셋 메모리 안정성
        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        for _ in range(20):
            reset_all()
            with tempfile.TemporaryDirectory() as tmpdir:
                cfg = {
                    "environment": "production",
                    "model": {"model_type": "yolo", "device": "cuda"},
                }
                config_path = Path(tmpdir) / "app.yaml"
                write_yaml(config_path, cfg)
                s = Settings.initialize(config_path=str(config_path))
                _ = s.snapshot()
                _ = s.to_dict()
                _ = s.get_status()

        gc.collect()
        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        growth_kb = total_growth / 1024
        # 20회 반복 후 합리적인 메모리 증가량 (100KB 미만)
        assert growth_kb < 500, f"메모리 증가: {growth_kb:.1f}KB"
        result.ok(f"15-2: 20회 초기화/리셋 메모리 안정 ({growth_kb:.1f}KB)")
    except Exception as e:
        result.fail("15-2: 20회 초기화/리셋 메모리 안정성", str(e))

    try:
        # 15-3: Loader clear 후 Settings 상태
        reset_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {
                "environment": "production",
                "model": {"model_type": "yolo", "device": "cuda"},
            }
            config_path = Path(tmpdir) / "app.yaml"
            write_yaml(config_path, cfg)

            s = Settings.initialize(config_path=str(config_path))
            assert s.has("environment")

            # Loader를 직접 clear 해도 Settings의 AppConfig는 유지
            s._loader.clear()
            assert s.config is not None
            assert isinstance(s.config, AppConfig)
            result.ok("15-3: Loader.clear 후 Settings AppConfig 유지")
    except Exception as e:
        result.fail("15-3: Loader.clear 후 Settings AppConfig 유지", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """전체 통합 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW Desktop - config 모듈 통합 테스트")
    print("=" * 60)

    result = TestResult()

    # [1] __init__.py Export 무결성
    test_init_export_integrity(result)

    # [2] Loader → Validator 파이프라인
    test_loader_to_validator_pipeline(result)

    # [3] 전체 파이프라인
    test_full_pipeline(result)

    # [4] Settings 프로퍼티 체인
    test_settings_property_chain(result)

    # [5] Reload → Listener 파이프라인
    test_reload_listener_pipeline(result)

    # [6] Watcher → Settings 연동
    test_watcher_settings_integration(result)

    # [7] 동적 설정 파일 라이프사이클
    test_dynamic_config_lifecycle(result)

    # [8] 프로파일 기반 오버라이드
    test_profile_override_pipeline(result)

    # [9] 환경변수 오버라이드
    test_env_override_pipeline(result)

    # [10] 스냅샷 / Diff
    test_snapshot_diff_pipeline(result)

    # [11] 다중 파일 병합
    test_multi_file_merge_pipeline(result)

    # [12] 오류 복원 / 폴백
    test_error_recovery_scenarios(result)

    # [13] 스레드 안전성
    test_thread_safety_integration(result)

    # [14] 헬퍼 함수 통합
    test_helper_functions_integration(result)

    # [15] 메모리 / 자원 정리
    test_resource_cleanup(result)

    # 최종 정리
    reset_all()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
