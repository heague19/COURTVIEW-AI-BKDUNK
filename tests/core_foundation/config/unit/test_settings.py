# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/unit
파일: test_settings.py
설명: Settings 전역 설정 관리 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] SettingsState Enum
    - [2] Environment Enum
    - [3] SettingsMetadata 데이터 클래스
    - [4] Settings 싱글톤 패턴
    - [5] Settings.initialize() 및 _load_config
    - [6] 설정 접근 프로퍼티 (config, gpu, camera 등)
    - [7] 상태 프로퍼티 (state, is_ready, environment 등)
    - [8] Desktop 전용 편의 프로퍼티
    - [9] 범용 접근 메서드 (get, get_typed, has, to_dict)
    - [10] 변경 리스너 (on_change, off_change)
    - [11] 스냅샷/비교 (snapshot, diff, _find_diff)
    - [12] reload 메서드
    - [13] get_status / __repr__
    - [14] 헬퍼 함수 (get_settings, initialize_settings)
    - [15] 엣지 케이스 및 모듈 Export
"""

import os
import sys
import time
import types
import threading
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈 — watcher 임포트 시 필요)
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

# utils 패키지도 등록
if "utils" not in sys.modules:
    _mock_utils = types.ModuleType("utils")
    sys.modules["utils"] = _mock_utils
sys.modules["utils.time_utils"] = _mock_time_utils

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.settings import (
    SettingsState,
    Environment,
    SettingsMetadata,
    Settings,
    get_settings,
    initialize_settings,
)
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    LocalDatabaseConfig,
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
)
from core_foundation.config.loader import ConfigLoader

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
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼: 각 테스트 전 싱글톤 리셋
# =============================================================================
def reset_settings() -> None:
    """Settings 및 ConfigLoader 싱글톤 리셋."""
    Settings.reset_instance()


# =============================================================================
# [1] SettingsState Enum 테스트
# =============================================================================
def test_settings_state_enum(result: TestResult) -> None:
    """SettingsState Enum 멤버 테스트."""
    print("\n[1] SettingsState Enum 테스트")

    try:
        # 1-1: 멤버 존재 확인
        expected_members = ["UNINITIALIZED", "LOADING", "READY", "ERROR", "RELOADING"]
        for member in expected_members:
            assert hasattr(SettingsState, member), f"{member} 멤버 누락"
        result.ok("1-1: 모든 멤버 존재")
    except Exception as e:
        result.fail("1-1: 모든 멤버 존재", str(e))

    try:
        # 1-2: 멤버 수
        members = list(SettingsState)
        assert len(members) == 5, f"멤버 수: {len(members)} != 5"
        result.ok("1-2: 멤버 수 5개")
    except Exception as e:
        result.fail("1-2: 멤버 수 5개", str(e))

    try:
        # 1-3: auto() 값 사용 (정수 값)
        for member in SettingsState:
            assert isinstance(member.value, int), f"{member.name} 값이 int가 아님"
        result.ok("1-3: auto() 정수 값 확인")
    except Exception as e:
        result.fail("1-3: auto() 정수 값 확인", str(e))

    try:
        # 1-4: 이름으로 접근
        assert SettingsState["READY"] == SettingsState.READY
        assert SettingsState["ERROR"] == SettingsState.ERROR
        result.ok("1-4: 이름 기반 접근")
    except Exception as e:
        result.fail("1-4: 이름 기반 접근", str(e))

    try:
        # 1-5: name 속성
        assert SettingsState.UNINITIALIZED.name == "UNINITIALIZED"
        assert SettingsState.LOADING.name == "LOADING"
        assert SettingsState.READY.name == "READY"
        assert SettingsState.ERROR.name == "ERROR"
        assert SettingsState.RELOADING.name == "RELOADING"
        result.ok("1-5: name 속성")
    except Exception as e:
        result.fail("1-5: name 속성", str(e))


# =============================================================================
# [2] Environment Enum 테스트
# =============================================================================
def test_environment_enum(result: TestResult) -> None:
    """Environment Enum 멤버 테스트."""
    print("\n[2] Environment Enum 테스트")

    try:
        # 2-1: 멤버 존재 확인
        expected = {"DEVELOPMENT": "development", "PRODUCTION": "production", "TESTING": "testing"}
        for name, value in expected.items():
            assert hasattr(Environment, name), f"{name} 멤버 누락"
            assert Environment[name].value == value, f"{name} 값 불일치"
        result.ok("2-1: 모든 멤버 존재 및 값 확인")
    except Exception as e:
        result.fail("2-1: 모든 멤버 존재 및 값 확인", str(e))

    try:
        # 2-2: 멤버 수
        members = list(Environment)
        assert len(members) == 3, f"멤버 수: {len(members)} != 3"
        result.ok("2-2: 멤버 수 3개")
    except Exception as e:
        result.fail("2-2: 멤버 수 3개", str(e))

    try:
        # 2-3: 문자열 값으로 접근
        assert Environment("development") == Environment.DEVELOPMENT
        assert Environment("production") == Environment.PRODUCTION
        assert Environment("testing") == Environment.TESTING
        result.ok("2-3: 문자열 값 기반 접근")
    except Exception as e:
        result.fail("2-3: 문자열 값 기반 접근", str(e))

    try:
        # 2-4: 잘못된 값 접근 시 ValueError
        raised = False
        try:
            Environment("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("2-4: 잘못된 값 ValueError")
    except Exception as e:
        result.fail("2-4: 잘못된 값 ValueError", str(e))


# =============================================================================
# [3] SettingsMetadata 데이터 클래스 테스트
# =============================================================================
def test_settings_metadata(result: TestResult) -> None:
    """SettingsMetadata 데이터 클래스 테스트."""
    print("\n[3] SettingsMetadata 데이터 클래스 테스트")

    try:
        # 3-1: 기본값 생성
        meta = SettingsMetadata()
        assert meta.config_path is None, "config_path 기본값 오류"
        assert meta.loaded_at is None, "loaded_at 기본값 오류"
        assert meta.last_reloaded_at is None, "last_reloaded_at 기본값 오류"
        assert meta.reload_count == 0, "reload_count 기본값 오류"
        assert meta.environment == "production", "environment 기본값 오류"
        assert meta.validation_passed is False, "validation_passed 기본값 오류"
        assert meta.config_version == "1.0.0", "config_version 기본값 오류"
        result.ok("3-1: 기본값 생성")
    except Exception as e:
        result.fail("3-1: 기본값 생성", str(e))

    try:
        # 3-2: mark_loaded
        meta = SettingsMetadata()
        before = datetime.now(timezone.utc)
        meta.mark_loaded("config/app.yaml", "development")
        after = datetime.now(timezone.utc)

        assert meta.config_path == "config/app.yaml"
        assert meta.environment == "development"
        assert meta.validation_passed is True
        assert before <= meta.loaded_at <= after
        assert before <= meta.last_reloaded_at <= after
        # loaded_at과 last_reloaded_at은 동일해야 함 (최초 로드)
        assert meta.loaded_at == meta.last_reloaded_at
        result.ok("3-2: mark_loaded")
    except Exception as e:
        result.fail("3-2: mark_loaded", str(e))

    try:
        # 3-3: mark_reloaded
        meta = SettingsMetadata()
        meta.mark_loaded("config/app.yaml", "production")
        initial_time = meta.last_reloaded_at
        initial_count = meta.reload_count

        time.sleep(0.01)  # 시간 차이 보장
        meta.mark_reloaded()

        assert meta.reload_count == initial_count + 1
        assert meta.last_reloaded_at > initial_time
        # loaded_at은 변경되지 않아야 함
        assert meta.loaded_at == initial_time
        result.ok("3-3: mark_reloaded")
    except Exception as e:
        result.fail("3-3: mark_reloaded", str(e))

    try:
        # 3-4: mark_reloaded 연속 호출
        meta = SettingsMetadata()
        meta.mark_loaded("test.yaml", "testing")
        for i in range(5):
            meta.mark_reloaded()
        assert meta.reload_count == 5
        result.ok("3-4: mark_reloaded 연속 호출 (5회)")
    except Exception as e:
        result.fail("3-4: mark_reloaded 연속 호출 (5회)", str(e))

    try:
        # 3-5: to_dict
        meta = SettingsMetadata()
        d = meta.to_dict()
        expected_keys = {
            "config_path", "loaded_at", "last_reloaded_at",
            "reload_count", "environment", "validation_passed", "config_version",
        }
        assert set(d.keys()) == expected_keys, f"키 불일치: {set(d.keys())}"
        assert d["config_path"] is None
        assert d["loaded_at"] is None
        assert d["last_reloaded_at"] is None
        assert d["reload_count"] == 0
        result.ok("3-5: to_dict (미로드 상태)")
    except Exception as e:
        result.fail("3-5: to_dict (미로드 상태)", str(e))

    try:
        # 3-6: to_dict (로드 후)
        meta = SettingsMetadata()
        meta.mark_loaded("config/app.yaml", "development")
        d = meta.to_dict()
        assert d["config_path"] == "config/app.yaml"
        assert d["loaded_at"] is not None
        assert d["environment"] == "development"
        assert d["validation_passed"] is True
        # ISO 형식 문자열 확인
        assert isinstance(d["loaded_at"], str)
        assert "T" in d["loaded_at"]  # ISO 포맷
        result.ok("3-6: to_dict (로드 후, ISO 시각)")
    except Exception as e:
        result.fail("3-6: to_dict (로드 후, ISO 시각)", str(e))

    try:
        # 3-7: 커스텀 값 생성
        meta = SettingsMetadata(
            config_path="/custom/path.yaml",
            reload_count=10,
            environment="testing",
            validation_passed=True,
            config_version="2.0.0",
        )
        assert meta.config_path == "/custom/path.yaml"
        assert meta.reload_count == 10
        assert meta.environment == "testing"
        assert meta.config_version == "2.0.0"
        result.ok("3-7: 커스텀 값 생성")
    except Exception as e:
        result.fail("3-7: 커스텀 값 생성", str(e))


# =============================================================================
# [4] Settings 싱글톤 패턴 테스트
# =============================================================================
def test_settings_singleton(result: TestResult) -> None:
    """Settings 싱글톤 패턴 테스트."""
    print("\n[4] Settings 싱글톤 패턴 테스트")

    try:
        # 4-1: 동일 인스턴스 반환
        reset_settings()
        s1 = Settings()
        s2 = Settings()
        assert s1 is s2, "싱글톤 인스턴스 불일치"
        result.ok("4-1: 동일 인스턴스 반환")
    except Exception as e:
        result.fail("4-1: 동일 인스턴스 반환", str(e))

    try:
        # 4-2: get_instance()도 동일 인스턴스
        reset_settings()
        s1 = Settings()
        s2 = Settings.get_instance()
        assert s1 is s2, "get_instance() 인스턴스 불일치"
        result.ok("4-2: get_instance() 동일 인스턴스")
    except Exception as e:
        result.fail("4-2: get_instance() 동일 인스턴스", str(e))

    try:
        # 4-3: reset_instance() 후 새 인스턴스
        reset_settings()
        s1 = Settings()
        id1 = id(s1)
        Settings.reset_instance()
        s2 = Settings()
        id2 = id(s2)
        assert id1 != id2, "리셋 후에도 같은 인스턴스"
        result.ok("4-3: reset_instance() 후 새 인스턴스")
    except Exception as e:
        result.fail("4-3: reset_instance() 후 새 인스턴스", str(e))

    try:
        # 4-4: 초기 상태 = UNINITIALIZED
        reset_settings()
        s = Settings()
        assert s.state == SettingsState.UNINITIALIZED, f"초기 상태: {s.state}"
        result.ok("4-4: 초기 상태 UNINITIALIZED")
    except Exception as e:
        result.fail("4-4: 초기 상태 UNINITIALIZED", str(e))

    try:
        # 4-5: 초기화 전 config는 기본 AppConfig
        reset_settings()
        s = Settings()
        cfg = s.config
        assert isinstance(cfg, AppConfig), "config가 AppConfig이 아님"
        result.ok("4-5: 초기화 전 config 기본 AppConfig")
    except Exception as e:
        result.fail("4-5: 초기화 전 config 기본 AppConfig", str(e))

    try:
        # 4-6: _initialized 플래그
        reset_settings()
        s = Settings()
        assert s._initialized is True, "_initialized가 True가 아님"
        result.ok("4-6: _initialized 플래그 True")
    except Exception as e:
        result.fail("4-6: _initialized 플래그 True", str(e))

    try:
        # 4-7: 멀티 스레드 싱글톤 안전성
        reset_settings()
        instances = []
        barrier = threading.Barrier(10)

        def create_instance():
            barrier.wait()
            instances.append(Settings())

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 모든 인스턴스가 동일해야 함
        assert len(instances) == 10
        for inst in instances:
            assert inst is instances[0], "스레드 간 인스턴스 불일치"
        result.ok("4-7: 멀티 스레드 싱글톤 안전성 (10 스레드)")
    except Exception as e:
        result.fail("4-7: 멀티 스레드 싱글톤 안전성 (10 스레드)", str(e))

    try:
        # 4-8: reset_instance()는 내부 상태도 초기화
        reset_settings()
        s = Settings()
        # 임의로 상태 변경
        s._state = SettingsState.READY
        s._raw_config = {"test": True}
        Settings.reset_instance()
        # 새 인스턴스는 깨끗해야 함
        s2 = Settings()
        assert s2.state == SettingsState.UNINITIALIZED
        assert s2._raw_config == {}
        result.ok("4-8: reset_instance() 내부 상태 초기화")
    except Exception as e:
        result.fail("4-8: reset_instance() 내부 상태 초기화", str(e))


# =============================================================================
# [5] Settings.initialize() 및 _load_config 테스트
# =============================================================================
def test_settings_initialize(result: TestResult) -> None:
    """Settings.initialize() 및 _load_config 테스트."""
    print("\n[5] Settings.initialize() 및 _load_config 테스트")

    try:
        # 5-1: fixture 파일로 초기화
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        assert s.state == SettingsState.READY, f"상태: {s.state}"
        assert s.is_ready is True
        result.ok("5-1: fixture 파일로 초기화 → READY")
    except Exception as e:
        result.fail("5-1: fixture 파일로 초기화 → READY", str(e))

    try:
        # 5-2: 초기화 후 메타데이터 확인
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        meta = s.metadata
        assert meta.config_path == str(fixture_path)
        assert meta.loaded_at is not None
        assert meta.validation_passed is True
        result.ok("5-2: 초기화 후 메타데이터 확인")
    except Exception as e:
        result.fail("5-2: 초기화 후 메타데이터 확인", str(e))

    try:
        # 5-3: validate=False로 초기화
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path), validate=False)
        assert s.state == SettingsState.READY
        assert isinstance(s.config, AppConfig)
        result.ok("5-3: validate=False 초기화")
    except Exception as e:
        result.fail("5-3: validate=False 초기화", str(e))

    try:
        # 5-4: 존재하지 않는 파일 → 기본값 사용, READY
        reset_settings()
        s = Settings.initialize(config_path="nonexistent/config.yaml")
        assert s.state == SettingsState.READY
        assert isinstance(s.config, AppConfig)
        # 기본값이 사용되므로 environment는 "production"
        assert s.config.environment == "production"
        result.ok("5-4: 존재하지 않는 파일 → 기본값 READY")
    except Exception as e:
        result.fail("5-4: 존재하지 않는 파일 → 기본값 READY", str(e))

    try:
        # 5-5: config_dir 명시
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(
            config_path=str(fixture_path),
            config_dir=str(FIXTURES_DIR),
        )
        assert s.state == SettingsState.READY
        result.ok("5-5: config_dir 명시 초기화")
    except Exception as e:
        result.fail("5-5: config_dir 명시 초기화", str(e))

    try:
        # 5-6: Path 객체로 초기화
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=fixture_path)
        assert s.state == SettingsState.READY
        result.ok("5-6: Path 객체로 초기화")
    except Exception as e:
        result.fail("5-6: Path 객체로 초기화", str(e))

    try:
        # 5-7: initialize()도 싱글톤 반환
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s1 = Settings.initialize(config_path=str(fixture_path))
        s2 = Settings.get_instance()
        assert s1 is s2
        result.ok("5-7: initialize()도 싱글톤 반환")
    except Exception as e:
        result.fail("5-7: initialize()도 싱글톤 반환", str(e))

    try:
        # 5-8: 프로파일 기반 로드 (test_base + test_base.development)
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        os.environ["COURTVIEW_PROFILE"] = "development"
        try:
            s = Settings.initialize(config_path=str(fixture_path))
            # development 프로파일의 environment 확인
            assert s.state == SettingsState.READY
        finally:
            os.environ.pop("COURTVIEW_PROFILE", None)
        result.ok("5-8: 프로파일 기반 로드")
    except Exception as e:
        result.fail("5-8: 프로파일 기반 로드", str(e))


# =============================================================================
# [6] 설정 접근 프로퍼티 테스트
# =============================================================================
def test_config_properties(result: TestResult) -> None:
    """설정 접근 프로퍼티 테스트."""
    print("\n[6] 설정 접근 프로퍼티 테스트")

    reset_settings()
    fixture_path = FIXTURES_DIR / "test_base.yaml"
    s = Settings.initialize(config_path=str(fixture_path))

    try:
        # 6-1: config 프로퍼티
        cfg = s.config
        assert isinstance(cfg, AppConfig), f"config 타입: {type(cfg)}"
        result.ok("6-1: config → AppConfig")
    except Exception as e:
        result.fail("6-1: config → AppConfig", str(e))

    try:
        # 6-2: gpu 프로퍼티
        gpu = s.gpu
        assert isinstance(gpu, GPUConfig), f"gpu 타입: {type(gpu)}"
        result.ok("6-2: gpu → GPUConfig")
    except Exception as e:
        result.fail("6-2: gpu → GPUConfig", str(e))

    try:
        # 6-3: camera 프로퍼티
        camera = s.camera
        assert isinstance(camera, CameraConfig), f"camera 타입: {type(camera)}"
        result.ok("6-3: camera → CameraConfig")
    except Exception as e:
        result.fail("6-3: camera → CameraConfig", str(e))

    try:
        # 6-4: storage 프로퍼티
        storage = s.storage
        assert isinstance(storage, LocalStorageConfig), f"storage 타입: {type(storage)}"
        result.ok("6-4: storage → LocalStorageConfig")
    except Exception as e:
        result.fail("6-4: storage → LocalStorageConfig", str(e))

    try:
        # 6-5: database 프로퍼티
        db = s.database
        assert isinstance(db, LocalDatabaseConfig), f"database 타입: {type(db)}"
        result.ok("6-5: database → LocalDatabaseConfig")
    except Exception as e:
        result.fail("6-5: database → LocalDatabaseConfig", str(e))

    try:
        # 6-6: model 프로퍼티
        model = s.model
        assert isinstance(model, ModelConfig), f"model 타입: {type(model)}"
        result.ok("6-6: model → ModelConfig")
    except Exception as e:
        result.fail("6-6: model → ModelConfig", str(e))

    try:
        # 6-7: analysis 프로퍼티
        analysis = s.analysis
        assert isinstance(analysis, AnalysisConfig), f"analysis 타입: {type(analysis)}"
        result.ok("6-7: analysis → AnalysisConfig")
    except Exception as e:
        result.fail("6-7: analysis → AnalysisConfig", str(e))

    try:
        # 6-8: logging_config 프로퍼티 (logging과 이름 충돌 방지)
        logging_cfg = s.logging_config
        assert isinstance(logging_cfg, LoggingConfig), f"logging_config 타입: {type(logging_cfg)}"
        result.ok("6-8: logging_config → LoggingConfig")
    except Exception as e:
        result.fail("6-8: logging_config → LoggingConfig", str(e))

    try:
        # 6-9: fixture 값 반영 확인 (gpu.cuda_device)
        # test_base.yaml에서 gpu.device_id=0 → cuda_device="cuda:0"
        assert s.gpu.cuda_device == "cuda:0", f"cuda_device: {s.gpu.cuda_device}"
        result.ok("6-9: fixture gpu.cuda_device='cuda:0' 반영")
    except Exception as e:
        result.fail("6-9: fixture gpu.cuda_device='cuda:0' 반영", str(e))

    try:
        # 6-10: fixture 값 반영 확인 (camera.count)
        # test_base.yaml에서 camera.count=4
        assert s.camera.count == 4, f"camera.count: {s.camera.count}"
        result.ok("6-10: fixture camera.count=4 반영")
    except Exception as e:
        result.fail("6-10: fixture camera.count=4 반영", str(e))

    try:
        # 6-11: fixture 값 반영 확인 (analysis.target_fps)
        assert s.analysis.target_fps == 30, f"target_fps: {s.analysis.target_fps}"
        result.ok("6-11: fixture analysis.target_fps=30 반영")
    except Exception as e:
        result.fail("6-11: fixture analysis.target_fps=30 반영", str(e))


# =============================================================================
# [7] 상태 프로퍼티 테스트
# =============================================================================
def test_state_properties(result: TestResult) -> None:
    """상태 프로퍼티 테스트."""
    print("\n[7] 상태 프로퍼티 테스트")

    try:
        # 7-1: 초기화 전 is_ready = False
        reset_settings()
        s = Settings()
        assert s.is_ready is False, "초기화 전 is_ready가 True"
        result.ok("7-1: 초기화 전 is_ready=False")
    except Exception as e:
        result.fail("7-1: 초기화 전 is_ready=False", str(e))

    try:
        # 7-2: 초기화 후 is_ready = True
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        assert s.is_ready is True
        result.ok("7-2: 초기화 후 is_ready=True")
    except Exception as e:
        result.fail("7-2: 초기화 후 is_ready=True", str(e))

    try:
        # 7-3: environment 프로퍼티 (기본 AppConfig → production)
        # test_base.yaml은 model_type:"yolov8"이 검증 실패하므로
        # 기본 AppConfig(environment="production")가 사용됨
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        env = s.environment
        assert isinstance(env, Environment), f"environment 타입: {type(env)}"
        assert env == Environment.PRODUCTION, f"environment: {env}"
        result.ok("7-3: environment = PRODUCTION (검증 실패 → 기본값)")
    except Exception as e:
        result.fail("7-3: environment = PRODUCTION (검증 실패 → 기본값)", str(e))

    try:
        # 7-4: is_production (기본 AppConfig)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        assert s.is_production is True
        assert s.is_development is False
        assert s.is_testing is False
        result.ok("7-4: is_production=True, 나머지 False")
    except Exception as e:
        result.fail("7-4: is_production=True, 나머지 False", str(e))

    try:
        # 7-5: 기본 AppConfig (production 환경)
        reset_settings()
        s = Settings.initialize(config_path="nonexistent.yaml")
        assert s.is_production is True
        assert s.is_development is False
        result.ok("7-5: 기본값 환경 = PRODUCTION")
    except Exception as e:
        result.fail("7-5: 기본값 환경 = PRODUCTION", str(e))

    try:
        # 7-6: state 프로퍼티 접근
        reset_settings()
        s = Settings()
        state = s.state
        assert isinstance(state, SettingsState), f"state 타입: {type(state)}"
        result.ok("7-6: state 타입 SettingsState")
    except Exception as e:
        result.fail("7-6: state 타입 SettingsState", str(e))

    try:
        # 7-7: metadata 프로퍼티
        reset_settings()
        s = Settings()
        meta = s.metadata
        assert isinstance(meta, SettingsMetadata), f"metadata 타입: {type(meta)}"
        result.ok("7-7: metadata 타입 SettingsMetadata")
    except Exception as e:
        result.fail("7-7: metadata 타입 SettingsMetadata", str(e))

    try:
        # 7-8: 잘못된 environment 문자열 → PRODUCTION 폴백
        # AppConfig Pydantic 검증을 우회하여 잘못된 환경값 주입
        reset_settings()
        s = Settings()
        cfg = AppConfig.model_construct(
            app_name="COURTVIEW Desktop",
            version="1.0.0",
            environment="unknown_env",
            gpu=GPUConfig(),
            camera=CameraConfig(),
            storage=LocalStorageConfig(),
            database=LocalDatabaseConfig(),
            model=ModelConfig(),
            analysis=AnalysisConfig(),
            logging=LoggingConfig(),
        )
        s._config = cfg
        env = s.environment
        assert env == Environment.PRODUCTION, f"폴백 환경: {env}"
        result.ok("7-8: 잘못된 environment → PRODUCTION 폴백")
    except Exception as e:
        result.fail("7-8: 잘못된 environment → PRODUCTION 폴백", str(e))


# =============================================================================
# [8] Desktop 전용 편의 프로퍼티 테스트
# =============================================================================
def test_desktop_convenience_properties(result: TestResult) -> None:
    """Desktop 전용 편의 프로퍼티 테스트."""
    print("\n[8] Desktop 전용 편의 프로퍼티 테스트")

    reset_settings()
    s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

    try:
        # 8-1: is_gpu_available (model.device != "cpu")
        # test_base.yaml: model.device = "cuda:0" → True
        assert s.is_gpu_available is True, f"is_gpu_available: {s.is_gpu_available}"
        result.ok("8-1: is_gpu_available=True (device='cuda:0')")
    except Exception as e:
        result.fail("8-1: is_gpu_available=True (device='cuda:0')", str(e))

    try:
        # 8-2: is_gpu_available (CPU 폴백)
        reset_settings()
        s = Settings()
        cfg = AppConfig(model=ModelConfig(device="cpu"))
        s._config = cfg
        assert s.is_gpu_available is False, "CPU 설정인데 gpu_available=True"
        result.ok("8-2: is_gpu_available=False (device='cpu')")
    except Exception as e:
        result.fail("8-2: is_gpu_available=False (device='cpu')", str(e))

    try:
        # 8-3: is_tensorrt_enabled
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        # test_base.yaml: gpu.tensorrt_enabled=true, model.device="cuda:0"
        assert s.is_tensorrt_enabled is True
        result.ok("8-3: is_tensorrt_enabled=True")
    except Exception as e:
        result.fail("8-3: is_tensorrt_enabled=True", str(e))

    try:
        # 8-4: is_tensorrt_enabled (GPU 없을 때)
        reset_settings()
        s = Settings()
        cfg = AppConfig(
            gpu=GPUConfig(tensorrt_enabled=True),
            model=ModelConfig(device="cpu"),
        )
        s._config = cfg
        # TensorRT 활성화되어 있지만 GPU 없으면 False
        assert s.is_tensorrt_enabled is False
        result.ok("8-4: is_tensorrt_enabled=False (device='cpu')")
    except Exception as e:
        result.fail("8-4: is_tensorrt_enabled=False (device='cpu')", str(e))

    try:
        # 8-5: is_multi_camera (camera.count > 1)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        # test_base.yaml: camera.count=4
        assert s.is_multi_camera is True
        result.ok("8-5: is_multi_camera=True (count=4)")
    except Exception as e:
        result.fail("8-5: is_multi_camera=True (count=4)", str(e))

    try:
        # 8-6: is_multi_camera (카메라 1대)
        reset_settings()
        s = Settings()
        cfg = AppConfig(camera=CameraConfig(count=1))
        s._config = cfg
        assert s.is_multi_camera is False
        result.ok("8-6: is_multi_camera=False (count=1)")
    except Exception as e:
        result.fail("8-6: is_multi_camera=False (count=1)", str(e))

    try:
        # 8-7: cuda_device 바로가기
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        assert s.cuda_device == s.gpu.cuda_device
        result.ok("8-7: cuda_device == gpu.cuda_device")
    except Exception as e:
        result.fail("8-7: cuda_device == gpu.cuda_device", str(e))

    try:
        # 8-8: target_fps 바로가기
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        assert s.target_fps == s.analysis.target_fps
        assert s.target_fps == 30
        result.ok("8-8: target_fps == analysis.target_fps")
    except Exception as e:
        result.fail("8-8: target_fps == analysis.target_fps", str(e))

    try:
        # 8-9: camera_count 바로가기
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        assert s.camera_count == s.camera.count
        assert s.camera_count == 4
        result.ok("8-9: camera_count == camera.count")
    except Exception as e:
        result.fail("8-9: camera_count == camera.count", str(e))


# =============================================================================
# [9] 범용 접근 메서드 테스트
# =============================================================================
def test_generic_access_methods(result: TestResult) -> None:
    """범용 접근 메서드 (get, get_typed, has, to_dict) 테스트."""
    print("\n[9] 범용 접근 메서드 테스트")

    reset_settings()
    s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))

    try:
        # 9-1: get (존재하는 키)
        val = s.get("gpu.cuda_device")
        assert val == "cuda:0", f"get gpu.cuda_device: {val}"
        result.ok("9-1: get('gpu.cuda_device') = 'cuda:0'")
    except Exception as e:
        result.fail("9-1: get('gpu.cuda_device') = 'cuda:0'", str(e))

    try:
        # 9-2: get (존재하지 않는 키 → default)
        val = s.get("nonexistent.key", "fallback")
        assert val == "fallback", f"get nonexistent: {val}"
        result.ok("9-2: get 존재하지 않는 키 → default")
    except Exception as e:
        result.fail("9-2: get 존재하지 않는 키 → default", str(e))

    try:
        # 9-3: get 기본 default=None
        val = s.get("nonexistent")
        assert val is None
        result.ok("9-3: get 기본 default=None")
    except Exception as e:
        result.fail("9-3: get 기본 default=None", str(e))

    try:
        # 9-4: get_typed (타입 변환)
        val = s.get_typed("camera.count", default=1, value_type=int)
        assert isinstance(val, int), f"타입: {type(val)}"
        result.ok("9-4: get_typed 정수 반환")
    except Exception as e:
        result.fail("9-4: get_typed 정수 반환", str(e))

    try:
        # 9-5: has (존재하는 키)
        assert s.has("gpu") is True
        assert s.has("camera") is True
        result.ok("9-5: has 존재하는 키 True")
    except Exception as e:
        result.fail("9-5: has 존재하는 키 True", str(e))

    try:
        # 9-6: has (존재하지 않는 키)
        assert s.has("nonexistent_section") is False
        result.ok("9-6: has 존재하지 않는 키 False")
    except Exception as e:
        result.fail("9-6: has 존재하지 않는 키 False", str(e))

    try:
        # 9-7: to_dict
        d = s.to_dict()
        assert isinstance(d, dict), f"to_dict 타입: {type(d)}"
        # AppConfig.model_dump() 결과이므로 gpu, camera 등 존재
        assert "gpu" in d
        assert "camera" in d
        assert "model" in d
        assert "analysis" in d
        assert "storage" in d
        assert "database" in d
        assert "logging" in d
        result.ok("9-7: to_dict 딕셔너리 구조")
    except Exception as e:
        result.fail("9-7: to_dict 딕셔너리 구조", str(e))

    try:
        # 9-8: to_dict 값 일관성
        d = s.to_dict()
        assert d["gpu"]["device_id"] == 0
        assert d["camera"]["count"] == 4
        assert d["analysis"]["target_fps"] == 30
        result.ok("9-8: to_dict 값 일관성")
    except Exception as e:
        result.fail("9-8: to_dict 값 일관성", str(e))


# =============================================================================
# [10] 변경 리스너 테스트
# =============================================================================
def test_change_listeners(result: TestResult) -> None:
    """변경 리스너 (on_change, off_change) 테스트."""
    print("\n[10] 변경 리스너 테스트")

    try:
        # 10-1: on_change 등록
        reset_settings()
        s = Settings()
        calls = []

        def listener(old, new):
            calls.append((old, new))

        s.on_change(listener)
        assert len(s._change_listeners) == 1
        result.ok("10-1: on_change 등록")
    except Exception as e:
        result.fail("10-1: on_change 등록", str(e))

    try:
        # 10-2: off_change 해제
        reset_settings()
        s = Settings()
        calls = []

        def listener(old, new):
            calls.append((old, new))

        s.on_change(listener)
        assert len(s._change_listeners) == 1
        s.off_change(listener)
        assert len(s._change_listeners) == 0
        result.ok("10-2: off_change 해제")
    except Exception as e:
        result.fail("10-2: off_change 해제", str(e))

    try:
        # 10-3: 중복 등록 방지
        reset_settings()
        s = Settings()

        def listener(old, new):
            pass

        s.on_change(listener)
        s.on_change(listener)
        assert len(s._change_listeners) == 1, "중복 등록됨"
        result.ok("10-3: 중복 등록 방지")
    except Exception as e:
        result.fail("10-3: 중복 등록 방지", str(e))

    try:
        # 10-4: 등록하지 않은 리스너 해제 시 안전
        reset_settings()
        s = Settings()

        def listener(old, new):
            pass

        # 등록하지 않은 리스너 해제 → 에러 없이 무시
        s.off_change(listener)
        assert len(s._change_listeners) == 0
        result.ok("10-4: 미등록 리스너 해제 안전")
    except Exception as e:
        result.fail("10-4: 미등록 리스너 해제 안전", str(e))

    try:
        # 10-5: _notify_change_listeners 호출
        reset_settings()
        s = Settings()
        calls = []

        def listener(old, new):
            calls.append(("called", old, new))

        s.on_change(listener)
        old_cfg = AppConfig()
        new_cfg = AppConfig(environment="testing")
        s._notify_change_listeners(old_cfg, new_cfg)
        assert len(calls) == 1
        assert calls[0][0] == "called"
        assert calls[0][1] is old_cfg
        assert calls[0][2] is new_cfg
        result.ok("10-5: _notify_change_listeners 콜백 호출")
    except Exception as e:
        result.fail("10-5: _notify_change_listeners 콜백 호출", str(e))

    try:
        # 10-6: 리스너 예외 시 다른 리스너에 영향 없음
        reset_settings()
        s = Settings()
        calls = []

        def bad_listener(old, new):
            raise ValueError("의도적 오류")

        def good_listener(old, new):
            calls.append("good")

        s.on_change(bad_listener)
        s.on_change(good_listener)

        old_cfg = AppConfig()
        new_cfg = AppConfig()
        s._notify_change_listeners(old_cfg, new_cfg)

        # bad_listener가 예외를 던져도 good_listener는 호출됨
        assert len(calls) == 1
        assert calls[0] == "good"
        result.ok("10-6: 리스너 예외 격리")
    except Exception as e:
        result.fail("10-6: 리스너 예외 격리", str(e))

    try:
        # 10-7: 다중 리스너 호출 순서
        reset_settings()
        s = Settings()
        order = []

        def listener_a(old, new):
            order.append("A")

        def listener_b(old, new):
            order.append("B")

        def listener_c(old, new):
            order.append("C")

        s.on_change(listener_a)
        s.on_change(listener_b)
        s.on_change(listener_c)

        s._notify_change_listeners(AppConfig(), AppConfig())
        assert order == ["A", "B", "C"], f"순서: {order}"
        result.ok("10-7: 다중 리스너 등록 순서 호출")
    except Exception as e:
        result.fail("10-7: 다중 리스너 등록 순서 호출", str(e))


# =============================================================================
# [11] 스냅샷/비교 테스트
# =============================================================================
def test_snapshot_and_diff(result: TestResult) -> None:
    """스냅샷/비교 (snapshot, diff, _find_diff) 테스트."""
    print("\n[11] 스냅샷/비교 테스트")

    try:
        # 11-1: snapshot 반환 타입
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        snap = s.snapshot()
        assert isinstance(snap, dict), f"snapshot 타입: {type(snap)}"
        result.ok("11-1: snapshot → dict")
    except Exception as e:
        result.fail("11-1: snapshot → dict", str(e))

    try:
        # 11-2: snapshot은 딥 카피 (원본 변경 영향 없음)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        snap = s.snapshot()
        original_fps = snap["analysis"]["target_fps"]
        snap["analysis"]["target_fps"] = 999
        # 원본은 변경되지 않아야 함
        assert s.analysis.target_fps == original_fps
        result.ok("11-2: snapshot 딥 카피 독립성")
    except Exception as e:
        result.fail("11-2: snapshot 딥 카피 독립성", str(e))

    try:
        # 11-3: diff (동일한 설정)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        snap = s.snapshot()
        diff = s.diff(snap)
        assert diff == {}, f"동일 설정인데 diff 발생: {diff}"
        result.ok("11-3: diff (동일 설정) → 빈 딕셔너리")
    except Exception as e:
        result.fail("11-3: diff (동일 설정) → 빈 딕셔너리", str(e))

    try:
        # 11-4: diff (값 변경됨)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        modified = s.snapshot()
        modified["analysis"]["target_fps"] = 60
        diff = s.diff(modified)
        assert "analysis.target_fps" in diff, f"diff에 target_fps 없음: {diff}"
        assert diff["analysis.target_fps"]["old"] == 30
        assert diff["analysis.target_fps"]["new"] == 60
        result.ok("11-4: diff (값 변경 감지)")
    except Exception as e:
        result.fail("11-4: diff (값 변경 감지)", str(e))

    try:
        # 11-5: diff (새 키 추가)
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        modified = s.snapshot()
        modified["new_section"] = {"key": "value"}
        diff = s.diff(modified)
        assert "new_section" in diff, f"diff에 new_section 없음: {diff}"
        result.ok("11-5: diff (새 키 추가 감지)")
    except Exception as e:
        result.fail("11-5: diff (새 키 추가 감지)", str(e))

    try:
        # 11-6: _find_diff 재귀 중첩 딕셔너리
        reset_settings()
        s = Settings()
        dict_a = {"a": {"b": {"c": 1}}, "x": 10}
        dict_b = {"a": {"b": {"c": 2}}, "x": 10}
        diff = s._find_diff(dict_a, dict_b)
        assert "a.b.c" in diff
        assert diff["a.b.c"]["old"] == 1
        assert diff["a.b.c"]["new"] == 2
        assert "x" not in diff  # 동일한 값은 포함 안 됨
        result.ok("11-6: _find_diff 재귀 중첩 처리")
    except Exception as e:
        result.fail("11-6: _find_diff 재귀 중첩 처리", str(e))

    try:
        # 11-7: _find_diff 빈 딕셔너리
        reset_settings()
        s = Settings()
        diff = s._find_diff({}, {})
        assert diff == {}
        result.ok("11-7: _find_diff 빈 딕셔너리 → 빈 결과")
    except Exception as e:
        result.fail("11-7: _find_diff 빈 딕셔너리 → 빈 결과", str(e))

    try:
        # 11-8: _find_diff 한쪽에만 키 존재
        reset_settings()
        s = Settings()
        dict_a = {"a": 1, "b": 2}
        dict_b = {"a": 1, "c": 3}
        diff = s._find_diff(dict_a, dict_b)
        # b는 dict_b에 없음 → {"old": 2, "new": None}
        assert "b" in diff
        assert diff["b"]["old"] == 2
        assert diff["b"]["new"] is None
        # c는 dict_a에 없음 → {"old": None, "new": 3}
        assert "c" in diff
        assert diff["c"]["old"] is None
        assert diff["c"]["new"] == 3
        result.ok("11-8: _find_diff 한쪽만 키 존재")
    except Exception as e:
        result.fail("11-8: _find_diff 한쪽만 키 존재", str(e))


# =============================================================================
# [12] reload 메서드 테스트
# =============================================================================
def test_reload(result: TestResult) -> None:
    """reload 메서드 테스트."""
    print("\n[12] reload 메서드 테스트")

    try:
        # 12-1: reload 성공 (동일 fixture 재로드)
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        success = s.reload()
        assert success is True, "reload 실패"
        assert s.state == SettingsState.READY
        result.ok("12-1: reload 성공")
    except Exception as e:
        result.fail("12-1: reload 성공", str(e))

    try:
        # 12-2: reload 후 metadata 갱신
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        initial_reload_count = s.metadata.reload_count
        s.reload()
        assert s.metadata.reload_count == initial_reload_count + 1
        result.ok("12-2: reload 후 reload_count 증가")
    except Exception as e:
        result.fail("12-2: reload 후 reload_count 증가", str(e))

    try:
        # 12-3: reload 경로 미설정 시 False
        reset_settings()
        s = Settings()
        # metadata에 config_path가 None인 상태
        success = s.reload()
        assert success is False, "경로 없는데 reload 성공"
        result.ok("12-3: reload 경로 없음 → False")
    except Exception as e:
        result.fail("12-3: reload 경로 없음 → False", str(e))

    try:
        # 12-4: reload에 다른 경로 지정
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        # 같은 파일을 다른 경로로 reload
        success = s.reload(config_path=str(fixture_path))
        assert success is True
        result.ok("12-4: reload 다른 경로 지정")
    except Exception as e:
        result.fail("12-4: reload 다른 경로 지정", str(e))

    try:
        # 12-5: reload 시 change listener 호출
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        calls = []

        def listener(old, new):
            calls.append((old, new))

        s.on_change(listener)
        s.reload()
        # reload 성공 시 리스너 호출됨
        assert len(calls) == 1, f"리스너 호출 횟수: {len(calls)}"
        result.ok("12-5: reload 시 change listener 호출")
    except Exception as e:
        result.fail("12-5: reload 시 change listener 호출", str(e))

    try:
        # 12-6: reload 실패 시 이전 설정 복원
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        original_config = deepcopy(s.config)

        # 존재하지 않는 잘못된 파일로 reload 시도
        # ConfigLoader가 예외를 던지면 이전 설정 복원됨
        # 존재하지 않는 파일은 _load_config에서 기본값 사용하므로
        # 직접 _load_config를 모킹하여 실패 유도
        with patch.object(s, "_load_config", side_effect=Exception("테스트 실패")):
            success = s.reload(config_path="bad/path.yaml")
        assert success is False
        assert s.state == SettingsState.READY, f"복원 후 상태: {s.state}"
        result.ok("12-6: reload 실패 시 이전 설정 복원 + READY")
    except Exception as e:
        result.fail("12-6: reload 실패 시 이전 설정 복원 + READY", str(e))

    try:
        # 12-7: reload 연속 호출
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = Settings.initialize(config_path=str(fixture_path))
        for i in range(3):
            success = s.reload()
            assert success is True, f"{i+1}번째 reload 실패"
        assert s.metadata.reload_count == 3
        result.ok("12-7: reload 연속 3회 호출")
    except Exception as e:
        result.fail("12-7: reload 연속 3회 호출", str(e))


# =============================================================================
# [13] get_status / __repr__ 테스트
# =============================================================================
def test_get_status_and_repr(result: TestResult) -> None:
    """get_status / __repr__ 테스트."""
    print("\n[13] get_status / __repr__ 테스트")

    try:
        # 13-1: get_status 반환 타입
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        status = s.get_status()
        assert isinstance(status, dict), f"status 타입: {type(status)}"
        result.ok("13-1: get_status → dict")
    except Exception as e:
        result.fail("13-1: get_status → dict", str(e))

    try:
        # 13-2: get_status 키 확인
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        status = s.get_status()
        expected_keys = {
            "state", "is_ready", "environment", "is_gpu_available",
            "is_tensorrt_enabled", "is_multi_camera", "gpu_device",
            "camera_count", "target_fps", "model_type", "model_precision",
            "db_path", "storage_cache_dir", "listeners_count", "metadata",
        }
        assert set(status.keys()) == expected_keys, f"키: {set(status.keys())}"
        result.ok("13-2: get_status 필수 키 15개")
    except Exception as e:
        result.fail("13-2: get_status 필수 키 15개", str(e))

    try:
        # 13-3: get_status 값 정합성
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        status = s.get_status()
        assert status["state"] == "READY"
        assert status["is_ready"] is True
        assert status["is_gpu_available"] is True
        assert status["camera_count"] == 4
        assert status["target_fps"] == 30
        assert status["listeners_count"] == 0
        result.ok("13-3: get_status 값 정합성")
    except Exception as e:
        result.fail("13-3: get_status 값 정합성", str(e))

    try:
        # 13-4: get_status metadata 포함
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        status = s.get_status()
        assert isinstance(status["metadata"], dict)
        assert "config_path" in status["metadata"]
        assert "loaded_at" in status["metadata"]
        result.ok("13-4: get_status metadata 딕셔너리 포함")
    except Exception as e:
        result.fail("13-4: get_status metadata 딕셔너리 포함", str(e))

    try:
        # 13-5: __repr__ 문자열 포맷
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        r = repr(s)
        assert isinstance(r, str)
        assert "Settings(" in r
        assert "state=" in r
        assert "env=" in r
        assert "gpu=" in r
        assert "cameras=" in r
        result.ok("13-5: __repr__ 포맷 확인")
    except Exception as e:
        result.fail("13-5: __repr__ 포맷 확인", str(e))

    try:
        # 13-6: __repr__ 초기화 전
        reset_settings()
        s = Settings()
        r = repr(s)
        assert "UNINITIALIZED" in r, f"repr: {r}"
        result.ok("13-6: __repr__ 초기화 전 UNINITIALIZED 포함")
    except Exception as e:
        result.fail("13-6: __repr__ 초기화 전 UNINITIALIZED 포함", str(e))

    try:
        # 13-7: get_status listeners_count 반영
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        s.on_change(lambda o, n: None)
        s.on_change(lambda o, n: None)
        status = s.get_status()
        assert status["listeners_count"] == 2
        result.ok("13-7: listeners_count 반영")
    except Exception as e:
        result.fail("13-7: listeners_count 반영", str(e))


# =============================================================================
# [14] 헬퍼 함수 테스트
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 (get_settings, initialize_settings) 테스트."""
    print("\n[14] 헬퍼 함수 테스트")

    try:
        # 14-1: get_settings → Settings.get_instance()
        reset_settings()
        s1 = Settings()
        s2 = get_settings()
        assert s1 is s2, "get_settings() 인스턴스 불일치"
        result.ok("14-1: get_settings() == Settings.get_instance()")
    except Exception as e:
        result.fail("14-1: get_settings() == Settings.get_instance()", str(e))

    try:
        # 14-2: initialize_settings
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = initialize_settings(config_path=str(fixture_path))
        assert s.is_ready is True
        assert isinstance(s, Settings)
        result.ok("14-2: initialize_settings → READY")
    except Exception as e:
        result.fail("14-2: initialize_settings → READY", str(e))

    try:
        # 14-3: initialize_settings validate=False
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s = initialize_settings(config_path=str(fixture_path), validate=False)
        assert s.is_ready is True
        result.ok("14-3: initialize_settings validate=False")
    except Exception as e:
        result.fail("14-3: initialize_settings validate=False", str(e))

    try:
        # 14-4: get_settings 후 initialize_settings → 동일 싱글톤
        reset_settings()
        fixture_path = FIXTURES_DIR / "test_base.yaml"
        s1 = initialize_settings(config_path=str(fixture_path))
        s2 = get_settings()
        assert s1 is s2
        result.ok("14-4: initialize → get_settings 싱글톤 일관성")
    except Exception as e:
        result.fail("14-4: initialize → get_settings 싱글톤 일관성", str(e))

    try:
        # 14-5: initialize_settings 기본 경로
        reset_settings()
        s = initialize_settings()
        # 기본 경로 "config/app.yaml"은 존재하지 않으므로 기본값 사용
        assert isinstance(s, Settings)
        assert s.state == SettingsState.READY
        result.ok("14-5: initialize_settings 기본 경로")
    except Exception as e:
        result.fail("14-5: initialize_settings 기본 경로", str(e))


# =============================================================================
# [15] 엣지 케이스 및 모듈 Export 테스트
# =============================================================================
def test_edge_cases_and_exports(result: TestResult) -> None:
    """엣지 케이스 및 모듈 Export 테스트."""
    print("\n[15] 엣지 케이스 및 모듈 Export 테스트")

    try:
        # 15-1: __all__ Export 목록
        import core_foundation.config.settings as settings_module
        expected_all = [
            "SettingsState", "Environment", "SettingsMetadata",
            "Settings", "get_settings", "initialize_settings",
        ]
        assert hasattr(settings_module, "__all__")
        assert set(settings_module.__all__) == set(expected_all), (
            f"__all__ 불일치: {settings_module.__all__}"
        )
        result.ok("15-1: __all__ Export 목록 6개")
    except Exception as e:
        result.fail("15-1: __all__ Export 목록 6개", str(e))

    try:
        # 15-2: __version__
        import core_foundation.config.settings as settings_module
        assert hasattr(settings_module, "__version__")
        assert settings_module.__version__ == "1.0.0"
        result.ok("15-2: __version__ = '1.0.0'")
    except Exception as e:
        result.fail("15-2: __version__ = '1.0.0'", str(e))

    try:
        # 15-3: config 프로퍼티 None 안전성 (_config=None → 기본 AppConfig)
        reset_settings()
        s = Settings()
        s._config = None  # 강제 None
        cfg = s.config
        assert isinstance(cfg, AppConfig), "None 시 기본 AppConfig 미생성"
        result.ok("15-3: config None → 기본 AppConfig 안전 생성")
    except Exception as e:
        result.fail("15-3: config None → 기본 AppConfig 안전 생성", str(e))

    try:
        # 15-4: 스레드 안전한 state 접근
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        states = []
        barrier = threading.Barrier(10)

        def read_state():
            barrier.wait()
            states.append(s.state)

        threads = [threading.Thread(target=read_state) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(states) == 10
        for st in states:
            assert st == SettingsState.READY
        result.ok("15-4: 스레드 안전 state 접근 (10 스레드)")
    except Exception as e:
        result.fail("15-4: 스레드 안전 state 접근 (10 스레드)", str(e))

    try:
        # 15-5: snapshot 연속 호출 독립성
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        snap1 = s.snapshot()
        snap2 = s.snapshot()
        assert snap1 == snap2, "연속 스냅샷 불일치"
        assert snap1 is not snap2, "스냅샷이 동일 객체"
        result.ok("15-5: snapshot 연속 호출 독립성")
    except Exception as e:
        result.fail("15-5: snapshot 연속 호출 독립성", str(e))

    try:
        # 15-6: to_dict는 model_dump 위임
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        d1 = s.to_dict()
        d2 = s.config.model_dump()
        assert d1 == d2
        result.ok("15-6: to_dict == config.model_dump()")
    except Exception as e:
        result.fail("15-6: to_dict == config.model_dump()", str(e))

    try:
        # 15-7: Settings 클래스 _lock 존재
        assert hasattr(Settings, "_lock")
        assert isinstance(Settings._lock, type(threading.Lock()))
        result.ok("15-7: Settings._lock 존재")
    except Exception as e:
        result.fail("15-7: Settings._lock 존재", str(e))

    try:
        # 15-8: 내부 컴포넌트 타입 확인
        reset_settings()
        s = Settings()
        assert hasattr(s, "_loader")
        assert hasattr(s, "_validator")
        assert isinstance(s._loader, ConfigLoader)
        result.ok("15-8: 내부 컴포넌트 타입 확인 (loader, validator)")
    except Exception as e:
        result.fail("15-8: 내부 컴포넌트 타입 확인 (loader, validator)", str(e))

    try:
        # 15-9: diff에 빈 딕셔너리 전달
        reset_settings()
        s = Settings.initialize(config_path=str(FIXTURES_DIR / "test_base.yaml"))
        diff = s.diff({})
        # 모든 키가 diff에 포함되어야 함 (other에 없으므로)
        assert len(diff) > 0, "빈 딕셔너리와의 diff가 비어있음"
        result.ok("15-9: diff 빈 딕셔너리 → 전체 차이")
    except Exception as e:
        result.fail("15-9: diff 빈 딕셔너리 → 전체 차이", str(e))

    try:
        # 15-10: _previous_config 초기값 None
        reset_settings()
        s = Settings()
        assert s._previous_config is None
        result.ok("15-10: _previous_config 초기값 None")
    except Exception as e:
        result.fail("15-10: _previous_config 초기값 None", str(e))

    try:
        # 15-11: Environment Enum은 Enum 상속
        from enum import Enum
        assert issubclass(Environment, Enum)
        assert issubclass(SettingsState, Enum)
        result.ok("15-11: Enum 상속 확인")
    except Exception as e:
        result.fail("15-11: Enum 상속 확인", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """전체 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW Desktop - settings.py 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # [1] SettingsState Enum
    test_settings_state_enum(result)

    # [2] Environment Enum
    test_environment_enum(result)

    # [3] SettingsMetadata 데이터 클래스
    test_settings_metadata(result)

    # [4] Settings 싱글톤 패턴
    test_settings_singleton(result)

    # [5] Settings.initialize() 및 _load_config
    test_settings_initialize(result)

    # [6] 설정 접근 프로퍼티
    test_config_properties(result)

    # [7] 상태 프로퍼티
    test_state_properties(result)

    # [8] Desktop 전용 편의 프로퍼티
    test_desktop_convenience_properties(result)

    # [9] 범용 접근 메서드
    test_generic_access_methods(result)

    # [10] 변경 리스너
    test_change_listeners(result)

    # [11] 스냅샷/비교
    test_snapshot_and_diff(result)

    # [12] reload 메서드
    test_reload(result)

    # [13] get_status / __repr__
    test_get_status_and_repr(result)

    # [14] 헬퍼 함수
    test_helper_functions(result)

    # [15] 엣지 케이스 및 모듈 Export
    test_edge_cases_and_exports(result)

    # 최종 정리
    reset_settings()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
