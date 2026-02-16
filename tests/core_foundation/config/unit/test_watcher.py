# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/unit
파일: test_watcher.py
설명: HotReloadManager 및 관련 컴포넌트 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] 상수 값 검증
    - [2] ChangeType Enum
    - [3] ReloadStatus Enum
    - [4] WatcherState Enum
    - [5] LogLevel Enum
    - [6] HotReloadConfig 데이터 클래스
    - [7] ConfigChangeEvent 데이터 클래스
    - [8] WatchedFile 데이터 클래스
    - [9] ReloadStatistics 데이터 클래스
    - [10] ConfigFileEventHandler 필터링
    - [11] HotReloadManager 초기화 및 프로퍼티
    - [12] HotReloadManager 감시 관리
    - [13] HotReloadManager 콜백 관리
    - [14] HotReloadManager 내부 유틸리티
    - [15] 헬퍼 함수
    - [16] 엣지 케이스 및 모듈 Export
"""

import os
import sys
import time
import types
import tempfile
import threading
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# =============================================================================
# utils.time_utils 모킹 (아직 미구현 모듈)
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

from core_foundation.config.watcher import (
    # 상수
    DEFAULT_DEBOUNCE_TIME,
    MAX_DEBOUNCE_TIME,
    DEFAULT_POLL_INTERVAL,
    SUPPORTED_EXTENSIONS,
    CALLBACK_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_IGNORE_PATTERNS,
    # Enum
    ChangeType,
    ReloadStatus,
    WatcherState,
    LogLevel,
    # 데이터 클래스
    HotReloadConfig,
    ConfigChangeEvent,
    WatchedFile,
    ReloadStatistics,
    # 타입 별칭
    ConfigChangeCallback,
    # 메인 클래스
    ConfigFileEventHandler,
    HotReloadManager,
    # 함수
    create_hot_reload_manager,
    watch_config,
)
from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import SchemaValidator
from shared.constants.status_codes import ServiceStatus

# 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼: ConfigLoader 싱글톤 리셋 및 생성
# =============================================================================
def create_loader() -> ConfigLoader:
    """테스트용 ConfigLoader 인스턴스 생성."""
    ConfigLoader.reset_instance()
    loader = ConfigLoader.get_instance()
    return loader


def create_manager(
    loader: ConfigLoader = None,
    validator: SchemaValidator = None,
    debounce_time: float = 0.5,
) -> HotReloadManager:
    """테스트용 HotReloadManager 생성."""
    if loader is None:
        loader = create_loader()
    return HotReloadManager(
        config_loader=loader,
        schema_validator=validator,
        debounce_time=debounce_time,
        validate_on_reload=False,
        auto_apply=True,
    )


# =============================================================================
# [1] 상수 값 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 검증."""
    print("\n[1] 상수 값 검증")

    # 1-1. DEFAULT_DEBOUNCE_TIME
    try:
        assert DEFAULT_DEBOUNCE_TIME == 0.5
        assert isinstance(DEFAULT_DEBOUNCE_TIME, float)
        result.ok("DEFAULT_DEBOUNCE_TIME = 0.5")
    except Exception as e:
        result.fail("DEFAULT_DEBOUNCE_TIME", str(e))

    # 1-2. MAX_DEBOUNCE_TIME
    try:
        assert MAX_DEBOUNCE_TIME == 5.0
        result.ok("MAX_DEBOUNCE_TIME = 5.0")
    except Exception as e:
        result.fail("MAX_DEBOUNCE_TIME", str(e))

    # 1-3. DEFAULT_POLL_INTERVAL
    try:
        assert DEFAULT_POLL_INTERVAL == 1.0
        result.ok("DEFAULT_POLL_INTERVAL = 1.0")
    except Exception as e:
        result.fail("DEFAULT_POLL_INTERVAL", str(e))

    # 1-4. SUPPORTED_EXTENSIONS
    try:
        assert SUPPORTED_EXTENSIONS == (".yaml", ".yml", ".json")
        assert isinstance(SUPPORTED_EXTENSIONS, tuple)
        result.ok("SUPPORTED_EXTENSIONS = (.yaml, .yml, .json)")
    except Exception as e:
        result.fail("SUPPORTED_EXTENSIONS", str(e))

    # 1-5. CALLBACK_TIMEOUT
    try:
        assert CALLBACK_TIMEOUT == 30.0
        result.ok("CALLBACK_TIMEOUT = 30.0")
    except Exception as e:
        result.fail("CALLBACK_TIMEOUT", str(e))

    # 1-6. DEFAULT_MAX_RETRIES
    try:
        assert DEFAULT_MAX_RETRIES == 3
        result.ok("DEFAULT_MAX_RETRIES = 3")
    except Exception as e:
        result.fail("DEFAULT_MAX_RETRIES", str(e))

    # 1-7. DEFAULT_RETRY_INTERVAL
    try:
        assert DEFAULT_RETRY_INTERVAL == 5.0
        result.ok("DEFAULT_RETRY_INTERVAL = 5.0")
    except Exception as e:
        result.fail("DEFAULT_RETRY_INTERVAL", str(e))

    # 1-8. DEFAULT_IGNORE_PATTERNS
    try:
        assert DEFAULT_IGNORE_PATTERNS == ("*.tmp", "*.bak", ".*", "__pycache__")
        assert isinstance(DEFAULT_IGNORE_PATTERNS, tuple)
        result.ok("DEFAULT_IGNORE_PATTERNS (4개 패턴)")
    except Exception as e:
        result.fail("DEFAULT_IGNORE_PATTERNS", str(e))


# =============================================================================
# [2] ChangeType Enum
# =============================================================================
def test_change_type_enum(result: TestResult) -> None:
    """ChangeType Enum 테스트."""
    print("\n[2] ChangeType Enum 테스트")

    # 2-1. 멤버 존재
    try:
        members = {"CREATED", "MODIFIED", "DELETED", "MOVED"}
        actual = {m.name for m in ChangeType}
        assert actual == members, f"{actual} != {members}"
        result.ok("멤버 4개 (CREATED, MODIFIED, DELETED, MOVED)")
    except Exception as e:
        result.fail("멤버 확인", str(e))

    # 2-2. auto() 값 확인
    try:
        assert ChangeType.CREATED.value == 1
        assert ChangeType.MODIFIED.value == 2
        assert ChangeType.DELETED.value == 3
        assert ChangeType.MOVED.value == 4
        result.ok("auto() 값 (1, 2, 3, 4)")
    except Exception as e:
        result.fail("auto() 값", str(e))


# =============================================================================
# [3] ReloadStatus Enum
# =============================================================================
def test_reload_status_enum(result: TestResult) -> None:
    """ReloadStatus Enum 테스트."""
    print("\n[3] ReloadStatus Enum 테스트")

    # 3-1. 멤버 존재
    try:
        expected = {"SUCCESS", "FAILED", "VALIDATION_ERROR", "SKIPPED", "PENDING", "RETRYING"}
        actual = {m.name for m in ReloadStatus}
        assert actual == expected
        result.ok("멤버 6개 확인")
    except Exception as e:
        result.fail("멤버 확인", str(e))

    # 3-2. 값 확인
    try:
        assert ReloadStatus.SUCCESS.value == "success"
        assert ReloadStatus.FAILED.value == "failed"
        assert ReloadStatus.VALIDATION_ERROR.value == "validation_error"
        assert ReloadStatus.SKIPPED.value == "skipped"
        assert ReloadStatus.PENDING.value == "pending"
        assert ReloadStatus.RETRYING.value == "retrying"
        result.ok("값 확인 (6개)")
    except Exception as e:
        result.fail("값 확인", str(e))


# =============================================================================
# [4] WatcherState Enum
# =============================================================================
def test_watcher_state_enum(result: TestResult) -> None:
    """WatcherState Enum 테스트."""
    print("\n[4] WatcherState Enum 테스트")

    # 4-1. 멤버 존재
    try:
        expected = {"STOPPED", "STARTING", "RUNNING", "STOPPING", "ERROR"}
        actual = {m.name for m in WatcherState}
        assert actual == expected
        result.ok("멤버 5개 확인")
    except Exception as e:
        result.fail("멤버 확인", str(e))


# =============================================================================
# [5] LogLevel Enum
# =============================================================================
def test_log_level_enum(result: TestResult) -> None:
    """LogLevel Enum 테스트."""
    print("\n[5] LogLevel Enum 테스트")

    try:
        expected = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        actual = {m.name for m in LogLevel}
        assert actual == expected
        # 값도 동일 (이름=값)
        for member in LogLevel:
            assert member.name == member.value
        result.ok("멤버 5개 + 이름=값 확인")
    except Exception as e:
        result.fail("LogLevel", str(e))


# =============================================================================
# [6] HotReloadConfig 데이터 클래스
# =============================================================================
def test_hot_reload_config(result: TestResult) -> None:
    """HotReloadConfig 데이터 클래스 테스트."""
    print("\n[6] HotReloadConfig 테스트")

    # 6-1. 기본값 확인
    try:
        config = HotReloadConfig()
        assert config.enabled is True
        assert config.watch_directories == ["configs"]
        assert config.watch_patterns == ["*.yaml", "*.yml", "*.json"]
        assert config.ignore_patterns == ["*.tmp", "*.bak", ".*", "__pycache__"]
        assert config.debounce_ms == 500
        assert config.callback_timeout == 30.0
        assert config.keep_previous_on_failure is True
        assert config.max_retries == 3
        assert config.retry_interval == 5.0
        assert config.log_success is True
        assert config.log_failure is True
        assert config.log_level == "INFO"
        result.ok("기본값 12개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 6-2. debounce_seconds 프로퍼티
    try:
        config = HotReloadConfig(debounce_ms=500)
        assert config.debounce_seconds == 0.5
        config = HotReloadConfig(debounce_ms=1000)
        assert config.debounce_seconds == 1.0
        config = HotReloadConfig(debounce_ms=250)
        assert config.debounce_seconds == 0.25
        result.ok("debounce_seconds 프로퍼티 (ms→초 변환)")
    except Exception as e:
        result.fail("debounce_seconds", str(e))

    # 6-3. supported_extensions 프로퍼티
    try:
        config = HotReloadConfig(watch_patterns=["*.yaml", "*.json"])
        exts = config.supported_extensions
        assert ".yaml" in exts
        assert ".json" in exts
        assert len(exts) == 2
        result.ok("supported_extensions 프로퍼티")
    except Exception as e:
        result.fail("supported_extensions", str(e))

    # 6-4. supported_extensions 빈 패턴 → 기본값 폴백
    try:
        config = HotReloadConfig(watch_patterns=["config_*"])
        exts = config.supported_extensions
        assert exts == SUPPORTED_EXTENSIONS
        result.ok("supported_extensions 빈 패턴 → 기본값 폴백")
    except Exception as e:
        result.fail("supported_extensions 폴백", str(e))

    # 6-5. from_dict() 기본 딕셔너리
    try:
        data = {
            "enabled": False,
            "debounce_ms": 1000,
            "callback_timeout": 60.0,
            "watch_patterns": ["*.toml"],
            "ignore_patterns": ["*.log"],
            "on_failure": {
                "keep_previous": False,
                "max_retries": 5,
                "retry_interval": 10.0,
            },
            "notifications": {
                "log_success": False,
                "log_failure": True,
                "log_level": "DEBUG",
            },
        }
        config = HotReloadConfig.from_dict(data)
        assert config.enabled is False
        assert config.debounce_ms == 1000
        assert config.callback_timeout == 60.0
        assert config.watch_patterns == ["*.toml"]
        assert config.ignore_patterns == ["*.log"]
        assert config.keep_previous_on_failure is False
        assert config.max_retries == 5
        assert config.retry_interval == 10.0
        assert config.log_success is False
        assert config.log_level == "DEBUG"
        result.ok("from_dict() 전체 필드 매핑")
    except Exception as e:
        result.fail("from_dict()", str(e))

    # 6-6. from_dict() 빈 딕셔너리 → 기본값
    try:
        config = HotReloadConfig.from_dict({})
        assert config.enabled is True
        assert config.debounce_ms == 500
        assert config.max_retries == 3
        result.ok("from_dict({}) 빈 딕셔너리 → 기본값")
    except Exception as e:
        result.fail("from_dict({})", str(e))

    # 6-7. to_dict()
    try:
        config = HotReloadConfig()
        d = config.to_dict()
        assert d["enabled"] is True
        assert d["debounce_ms"] == 500
        assert d["on_failure"]["keep_previous"] is True
        assert d["on_failure"]["max_retries"] == 3
        assert d["on_failure"]["retry_interval"] == 5.0
        assert d["notifications"]["log_success"] is True
        assert d["notifications"]["log_level"] == "INFO"
        result.ok("to_dict() 구조 검증")
    except Exception as e:
        result.fail("to_dict()", str(e))

    # 6-8. from_dict() → to_dict() 왕복
    try:
        original = {
            "enabled": True,
            "debounce_ms": 750,
            "watch_directories": ["configs", "settings"],
            "watch_patterns": ["*.yaml"],
            "ignore_patterns": ["*.bak"],
            "callback_timeout": 15.0,
            "on_failure": {
                "keep_previous": True,
                "max_retries": 2,
                "retry_interval": 3.0,
            },
            "notifications": {
                "log_success": True,
                "log_failure": False,
                "log_level": "WARNING",
            },
        }
        config = HotReloadConfig.from_dict(original)
        restored = config.to_dict()
        assert restored["enabled"] == original["enabled"]
        assert restored["debounce_ms"] == original["debounce_ms"]
        assert restored["on_failure"]["max_retries"] == original["on_failure"]["max_retries"]
        result.ok("from_dict() → to_dict() 왕복 일관성")
    except Exception as e:
        result.fail("왕복 일관성", str(e))


# =============================================================================
# [7] ConfigChangeEvent 데이터 클래스
# =============================================================================
def test_config_change_event(result: TestResult) -> None:
    """ConfigChangeEvent 데이터 클래스 테스트."""
    print("\n[7] ConfigChangeEvent 테스트")

    # 7-1. 기본 생성
    try:
        event = ConfigChangeEvent(
            file_path="config/app.yaml",
            change_type=ChangeType.MODIFIED,
        )
        assert event.file_path == "config/app.yaml"
        assert event.change_type == ChangeType.MODIFIED
        assert isinstance(event.timestamp, datetime)
        assert event.old_config is None
        assert event.new_config is None
        assert event.changed_keys == []
        assert event.reload_status == ReloadStatus.PENDING
        assert event.error_message is None
        assert event.reload_duration_ms == 0.0
        assert event.retry_count == 0
        result.ok("기본 생성 (10개 필드 기본값)")
    except Exception as e:
        result.fail("기본 생성", str(e))

    # 7-2. is_success 프로퍼티
    try:
        event = ConfigChangeEvent(
            file_path="test.yaml",
            change_type=ChangeType.MODIFIED,
            reload_status=ReloadStatus.SUCCESS,
        )
        assert event.is_success is True

        event = ConfigChangeEvent(
            file_path="test.yaml",
            change_type=ChangeType.MODIFIED,
            reload_status=ReloadStatus.FAILED,
        )
        assert event.is_success is False
        result.ok("is_success 프로퍼티")
    except Exception as e:
        result.fail("is_success", str(e))

    # 7-3. has_changes 프로퍼티
    try:
        event = ConfigChangeEvent(
            file_path="test.yaml",
            change_type=ChangeType.MODIFIED,
            changed_keys=["gpu.precision", "camera.fps"],
        )
        assert event.has_changes is True

        event = ConfigChangeEvent(
            file_path="test.yaml",
            change_type=ChangeType.MODIFIED,
            changed_keys=[],
        )
        assert event.has_changes is False
        result.ok("has_changes 프로퍼티")
    except Exception as e:
        result.fail("has_changes", str(e))

    # 7-4. __post_init__ Path → str 변환
    try:
        p = Path("config/app.yaml")
        event = ConfigChangeEvent(
            file_path=p,
            change_type=ChangeType.CREATED,
        )
        assert isinstance(event.file_path, str)
        # Path → str 변환 확인 (OS별 구분자 차이 허용)
        assert event.file_path == str(p)
        result.ok("__post_init__ Path → str 변환")
    except Exception as e:
        result.fail("__post_init__", str(e))

    # 7-5. to_dict()
    try:
        event = ConfigChangeEvent(
            file_path="config/test.yaml",
            change_type=ChangeType.DELETED,
            changed_keys=["key1", "key2"],
            reload_status=ReloadStatus.SUCCESS,
            reload_duration_ms=15.5,
            retry_count=1,
        )
        d = event.to_dict()
        assert d["file_path"] == "config/test.yaml"
        assert d["change_type"] == "DELETED"  # Enum.name
        assert d["reload_status"] == "success"  # Enum.value
        assert d["changed_keys"] == ["key1", "key2"]
        assert d["reload_duration_ms"] == 15.5
        assert d["retry_count"] == 1
        assert d["has_changes"] is True
        assert "timestamp" in d
        result.ok("to_dict() 구조 검증")
    except Exception as e:
        result.fail("to_dict()", str(e))


# =============================================================================
# [8] WatchedFile 데이터 클래스
# =============================================================================
def test_watched_file(result: TestResult) -> None:
    """WatchedFile 데이터 클래스 테스트."""
    print("\n[8] WatchedFile 테스트")

    # 8-1. 기본 생성
    try:
        wf = WatchedFile(path=Path("test.yaml"))
        assert wf.path == Path("test.yaml")
        assert wf.last_hash == ""
        assert wf.last_modified is None
        assert wf.last_reload is None
        assert wf.reload_count == 0
        assert wf.error_count == 0
        assert wf.consecutive_errors == 0
        assert wf.is_valid is True
        result.ok("기본 생성 (8개 필드)")
    except Exception as e:
        result.fail("기본 생성", str(e))

    # 8-2. update_hash() - 실제 파일
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value1\n")
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)
        changed = wf.update_hash()
        assert changed is True  # 첫 번째: "" → 해시값
        assert wf.last_hash != ""
        assert wf.last_modified is not None

        first_hash = wf.last_hash

        # 같은 내용 → 변경 없음
        changed = wf.update_hash()
        assert changed is False
        assert wf.last_hash == first_hash

        # 내용 변경 → 변경 감지
        temp_path.write_text("key: value2\n")
        changed = wf.update_hash()
        assert changed is True
        assert wf.last_hash != first_hash

        os.unlink(temp_path)
        result.ok("update_hash() 변경 감지 (동일/변경)")
    except Exception as e:
        result.fail("update_hash()", str(e))

    # 8-3. update_hash() - 존재하지 않는 파일
    try:
        wf = WatchedFile(path=Path("nonexistent_file.yaml"))
        changed = wf.update_hash()
        assert changed is False
        result.ok("update_hash() 존재하지 않는 파일 → False")
    except Exception as e:
        result.fail("update_hash() nonexistent", str(e))

    # 8-4. _calculate_hash() - 실제 해시 확인
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("hash_test: 123\n")
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)
        calculated = wf._calculate_hash()
        expected = hashlib.md5(temp_path.read_bytes()).hexdigest()
        assert calculated == expected

        os.unlink(temp_path)
        result.ok("_calculate_hash() MD5 일치")
    except Exception as e:
        result.fail("_calculate_hash()", str(e))

    # 8-5. mark_reloaded() 성공
    try:
        wf = WatchedFile(path=Path("test.yaml"))
        wf.mark_reloaded(success=True)
        assert wf.reload_count == 1
        assert wf.error_count == 0
        assert wf.consecutive_errors == 0
        assert wf.last_reload is not None

        wf.mark_reloaded(success=True)
        assert wf.reload_count == 2
        result.ok("mark_reloaded(success=True) 카운터 증가")
    except Exception as e:
        result.fail("mark_reloaded(True)", str(e))

    # 8-6. mark_reloaded() 실패
    try:
        wf = WatchedFile(path=Path("test.yaml"))
        wf.mark_reloaded(success=False)
        assert wf.reload_count == 1
        assert wf.error_count == 1
        assert wf.consecutive_errors == 1

        wf.mark_reloaded(success=False)
        assert wf.consecutive_errors == 2

        # 성공 시 consecutive_errors 리셋
        wf.mark_reloaded(success=True)
        assert wf.consecutive_errors == 0
        assert wf.error_count == 2  # 총 에러는 유지
        result.ok("mark_reloaded(False) → consecutive_errors 누적, 성공 시 리셋")
    except Exception as e:
        result.fail("mark_reloaded(False)", str(e))


# =============================================================================
# [9] ReloadStatistics 데이터 클래스
# =============================================================================
def test_reload_statistics(result: TestResult) -> None:
    """ReloadStatistics 데이터 클래스 테스트."""
    print("\n[9] ReloadStatistics 테스트")

    # 9-1. 기본값
    try:
        stats = ReloadStatistics()
        assert stats.total_reloads == 0
        assert stats.successful_reloads == 0
        assert stats.failed_reloads == 0
        assert stats.validation_errors == 0
        assert stats.skipped_reloads == 0
        assert stats.retry_attempts == 0
        assert stats.total_reload_time_ms == 0.0
        assert stats.last_reload_time is None
        result.ok("기본값 8개 필드")
    except Exception as e:
        result.fail("기본값", str(e))

    # 9-2. average_reload_time_ms - 초기값
    try:
        stats = ReloadStatistics()
        assert stats.average_reload_time_ms == 0.0  # 0/0 방지
        result.ok("average_reload_time_ms 초기값 = 0.0")
    except Exception as e:
        result.fail("average_reload_time_ms 초기", str(e))

    # 9-3. success_rate - 초기값
    try:
        stats = ReloadStatistics()
        assert stats.success_rate == 1.0  # 0/0 = 1.0
        result.ok("success_rate 초기값 = 1.0")
    except Exception as e:
        result.fail("success_rate 초기", str(e))

    # 9-4. record_reload(SUCCESS)
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.SUCCESS, 10.5)
        assert stats.total_reloads == 1
        assert stats.successful_reloads == 1
        assert stats.total_reload_time_ms == 10.5
        assert stats.average_reload_time_ms == 10.5
        assert stats.last_reload_time is not None
        result.ok("record_reload(SUCCESS, 10.5)")
    except Exception as e:
        result.fail("record_reload(SUCCESS)", str(e))

    # 9-5. record_reload(FAILED)
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.FAILED, 5.0)
        assert stats.total_reloads == 1
        assert stats.failed_reloads == 1
        assert stats.successful_reloads == 0
        result.ok("record_reload(FAILED)")
    except Exception as e:
        result.fail("record_reload(FAILED)", str(e))

    # 9-6. record_reload(VALIDATION_ERROR)
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.VALIDATION_ERROR, 3.0)
        assert stats.validation_errors == 1
        result.ok("record_reload(VALIDATION_ERROR)")
    except Exception as e:
        result.fail("record_reload(VALIDATION_ERROR)", str(e))

    # 9-7. record_reload(SKIPPED)
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.SKIPPED, 0.0)
        assert stats.skipped_reloads == 1
        result.ok("record_reload(SKIPPED)")
    except Exception as e:
        result.fail("record_reload(SKIPPED)", str(e))

    # 9-8. record_reload(RETRYING)
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.RETRYING, 0.0)
        assert stats.retry_attempts == 1
        result.ok("record_reload(RETRYING)")
    except Exception as e:
        result.fail("record_reload(RETRYING)", str(e))

    # 9-9. 복합 시나리오 - success_rate 계산
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.SUCCESS, 10.0)
        stats.record_reload(ReloadStatus.SUCCESS, 20.0)
        stats.record_reload(ReloadStatus.FAILED, 5.0)
        stats.record_reload(ReloadStatus.VALIDATION_ERROR, 3.0)
        assert stats.total_reloads == 4
        assert stats.successful_reloads == 2
        assert stats.success_rate == 0.5  # 2/4
        assert stats.average_reload_time_ms == 15.0  # (10+20)/2
        result.ok("복합 시나리오: success_rate=0.5, avg=15.0ms")
    except Exception as e:
        result.fail("복합 시나리오", str(e))

    # 9-10. to_dict()
    try:
        stats = ReloadStatistics()
        stats.record_reload(ReloadStatus.SUCCESS, 10.0)
        d = stats.to_dict()
        assert d["total_reloads"] == 1
        assert d["successful_reloads"] == 1
        assert d["success_rate"] == 1.0
        assert d["average_reload_time_ms"] == 10.0
        assert d["last_reload_time"] is not None
        assert "failed_reloads" in d
        assert "validation_errors" in d
        assert "skipped_reloads" in d
        assert "retry_attempts" in d
        result.ok("to_dict() 구조 검증 (9개 키)")
    except Exception as e:
        result.fail("to_dict()", str(e))


# =============================================================================
# [10] ConfigFileEventHandler 필터링
# =============================================================================
def test_event_handler_filtering(result: TestResult) -> None:
    """ConfigFileEventHandler 필터링 로직 테스트."""
    print("\n[10] ConfigFileEventHandler 필터링")

    manager = create_manager()

    handler = ConfigFileEventHandler(
        manager=manager,
        watched_files=set(),
        supported_extensions=(".yaml", ".yml", ".json"),
        ignore_patterns=["*.tmp", "*.bak", ".*", "__pycache__"],
    )

    # 10-1. _should_ignore - 무시 패턴 매칭
    try:
        assert handler._should_ignore("config.tmp") is True
        assert handler._should_ignore("backup.bak") is True
        assert handler._should_ignore(".gitignore") is True
        assert handler._should_ignore(".env") is True
        result.ok("_should_ignore - 무시 패턴 (tmp, bak, .*)")
    except Exception as e:
        result.fail("_should_ignore 무시 패턴", str(e))

    # 10-2. _should_ignore - __pycache__ 경로
    try:
        assert handler._should_ignore("project/__pycache__/module.pyc") is True
        result.ok("_should_ignore - __pycache__ 경로")
    except Exception as e:
        result.fail("__pycache__", str(e))

    # 10-3. _should_ignore - 정상 파일
    try:
        assert handler._should_ignore("config.yaml") is False
        assert handler._should_ignore("settings.json") is False
        assert handler._should_ignore("app.yml") is False
        result.ok("_should_ignore - 정상 파일 → False")
    except Exception as e:
        result.fail("_should_ignore 정상", str(e))

    # 10-4. _should_process - 확장자 필터
    try:
        # 감시 대상이 없으므로 지원 확장자라도 False (감시 대상 불일치)
        assert handler._should_process("config.txt") is False
        assert handler._should_process("config.py") is False
        result.ok("_should_process - 비지원 확장자 → False")
    except Exception as e:
        result.fail("_should_process 확장자", str(e))

    # 10-5. _should_process - 무시 패턴 우선
    try:
        assert handler._should_process("config.tmp") is False
        assert handler._should_process(".hidden.yaml") is False
        result.ok("_should_process - 무시 패턴 우선")
    except Exception as e:
        result.fail("_should_process 무시 우선", str(e))


# =============================================================================
# [11] HotReloadManager 초기화 및 프로퍼티
# =============================================================================
def test_manager_init_and_properties(result: TestResult) -> None:
    """HotReloadManager 초기화 및 프로퍼티 테스트."""
    print("\n[11] HotReloadManager 초기화 및 프로퍼티")

    # 11-1. 기본 초기화
    try:
        manager = create_manager(debounce_time=0.5)
        assert manager.state == WatcherState.STOPPED
        assert manager.is_running is False
        assert manager.debounce_time == 0.5
        assert isinstance(manager.statistics, ReloadStatistics)
        assert manager.watched_files == []
        result.ok("기본 초기화 (STOPPED, is_running=False)")
    except Exception as e:
        result.fail("기본 초기화", str(e))

    # 11-2. debounce_time 세터 (최소 0.1)
    try:
        manager = create_manager()
        manager.debounce_time = 0.05  # 최소 미만
        assert manager.debounce_time == 0.1  # 최소값으로 클램프
        result.ok("debounce_time 세터 → 최소 0.1 클램프")
    except Exception as e:
        result.fail("debounce_time 최소", str(e))

    # 11-3. debounce_time 세터 (최대 MAX_DEBOUNCE_TIME)
    try:
        manager = create_manager()
        manager.debounce_time = 100.0  # 최대 초과
        assert manager.debounce_time == MAX_DEBOUNCE_TIME
        result.ok(f"debounce_time 세터 → 최대 {MAX_DEBOUNCE_TIME} 클램프")
    except Exception as e:
        result.fail("debounce_time 최대", str(e))

    # 11-4. service_status (STOPPED)
    try:
        manager = create_manager()
        assert manager.service_status == ServiceStatus.STOPPED
        result.ok("service_status = STOPPED")
    except Exception as e:
        result.fail("service_status", str(e))

    # 11-5. hot_reload_config 프로퍼티
    try:
        manager = create_manager()
        config = manager.hot_reload_config
        assert isinstance(config, HotReloadConfig)
        result.ok("hot_reload_config 프로퍼티")
    except Exception as e:
        result.fail("hot_reload_config", str(e))

    # 11-6. ignore_patterns 프로퍼티
    try:
        manager = create_manager()
        patterns = manager.ignore_patterns
        assert isinstance(patterns, list)
        assert len(patterns) >= 1
        result.ok("ignore_patterns 프로퍼티")
    except Exception as e:
        result.fail("ignore_patterns", str(e))

    # 11-7. supported_extensions 프로퍼티
    try:
        manager = create_manager()
        exts = manager.supported_extensions
        assert isinstance(exts, tuple)
        result.ok("supported_extensions 프로퍼티")
    except Exception as e:
        result.fail("supported_extensions", str(e))

    # 11-8. 커스텀 debounce_time 초기화
    try:
        manager = create_manager(debounce_time=2.0)
        assert manager.debounce_time == 2.0
        result.ok("커스텀 debounce_time=2.0 초기화")
    except Exception as e:
        result.fail("커스텀 debounce_time", str(e))

    # 11-9. validate_on_reload=False 옵션
    try:
        manager = create_manager()
        assert manager._validate_on_reload is False  # create_manager에서 False
        result.ok("validate_on_reload=False 설정")
    except Exception as e:
        result.fail("validate_on_reload", str(e))


# =============================================================================
# [12] HotReloadManager 감시 관리
# =============================================================================
def test_manager_watch(result: TestResult) -> None:
    """HotReloadManager 감시 관리 테스트."""
    print("\n[12] HotReloadManager 감시 관리")

    # 12-1. watch() 파일 등록
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            temp_path = f.name

        manager = create_manager()
        manager.watch(temp_path)
        assert len(manager.watched_files) == 1
        # 절대 경로로 저장됨
        assert str(Path(temp_path).resolve()) in manager.watched_files

        os.unlink(temp_path)
        result.ok("watch() 파일 등록")
    except Exception as e:
        result.fail("watch() 파일", str(e))

    # 12-2. watch() 중복 등록 방지
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            temp_path = f.name

        manager = create_manager()
        manager.watch(temp_path)
        manager.watch(temp_path)  # 중복
        assert len(manager.watched_files) == 1

        os.unlink(temp_path)
        result.ok("watch() 중복 등록 방지")
    except Exception as e:
        result.fail("watch() 중복", str(e))

    # 12-3. unwatch() 감시 해제
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            temp_path = f.name

        manager = create_manager()
        manager.watch(temp_path)
        assert len(manager.watched_files) == 1

        manager.unwatch(temp_path)
        assert len(manager.watched_files) == 0

        os.unlink(temp_path)
        result.ok("unwatch() 감시 해제")
    except Exception as e:
        result.fail("unwatch()", str(e))

    # 12-4. watch_multiple() 여러 파일
    try:
        temp_files = []
        for i in range(3):
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
            f.write(f"key{i}: value{i}\n")
            f.close()
            temp_files.append(f.name)

        manager = create_manager()
        manager.watch_multiple(temp_files)
        assert len(manager.watched_files) == 3

        for f in temp_files:
            os.unlink(f)
        result.ok("watch_multiple() 3개 파일 등록")
    except Exception as e:
        result.fail("watch_multiple()", str(e))

    # 12-5. watch() 존재하지 않는 경로 (경고만, 등록은 진행)
    try:
        manager = create_manager()
        manager.watch("nonexistent/path/config.yaml")
        assert len(manager.watched_files) == 1  # 등록은 됨
        result.ok("watch() 존재하지 않는 경로 → 등록 진행")
    except Exception as e:
        result.fail("watch() 존재하지 않는 경로", str(e))

    # 12-6. get_watched_file_info() - 파일 정보 조회
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("info_test: yes\n")
            temp_path = f.name

        manager = create_manager()
        manager.watch(temp_path)

        info = manager.get_watched_file_info(temp_path)
        assert info is not None
        assert "path" in info
        assert "last_hash" in info
        assert "reload_count" in info
        assert info["is_valid"] is True

        os.unlink(temp_path)
        result.ok("get_watched_file_info() 정보 조회")
    except Exception as e:
        result.fail("get_watched_file_info()", str(e))

    # 12-7. get_watched_file_info() - 미등록 파일
    try:
        manager = create_manager()
        info = manager.get_watched_file_info("unregistered.yaml")
        assert info is None
        result.ok("get_watched_file_info() 미등록 → None")
    except Exception as e:
        result.fail("get_watched_file_info() 미등록", str(e))


# =============================================================================
# [13] HotReloadManager 콜백 관리
# =============================================================================
def test_manager_callbacks(result: TestResult) -> None:
    """HotReloadManager 콜백 관리 테스트."""
    print("\n[13] HotReloadManager 콜백 관리")

    # 13-1. register_callback()
    try:
        manager = create_manager()
        events_received = []

        def on_change(event):
            events_received.append(event)

        manager.register_callback(on_change)
        assert len(manager._callbacks) == 1
        result.ok("register_callback() 등록")
    except Exception as e:
        result.fail("register_callback()", str(e))

    # 13-2. 중복 콜백 등록 방지
    try:
        manager = create_manager()

        def callback_a(event):
            pass

        manager.register_callback(callback_a)
        manager.register_callback(callback_a)  # 중복
        assert len(manager._callbacks) == 1
        result.ok("콜백 중복 등록 방지")
    except Exception as e:
        result.fail("콜백 중복", str(e))

    # 13-3. unregister_callback()
    try:
        manager = create_manager()

        def callback_b(event):
            pass

        manager.register_callback(callback_b)
        assert len(manager._callbacks) == 1
        manager.unregister_callback(callback_b)
        assert len(manager._callbacks) == 0
        result.ok("unregister_callback() 해제")
    except Exception as e:
        result.fail("unregister_callback()", str(e))

    # 13-4. clear_callbacks()
    try:
        manager = create_manager()
        manager.register_callback(lambda e: None)
        manager.register_callback(lambda e: None)
        assert len(manager._callbacks) == 2
        manager.clear_callbacks()
        assert len(manager._callbacks) == 0
        result.ok("clear_callbacks() 전체 제거")
    except Exception as e:
        result.fail("clear_callbacks()", str(e))

    # 13-5. _notify_callbacks 실제 호출
    try:
        manager = create_manager()
        received = []

        def collector(event):
            received.append(event)

        manager.register_callback(collector)
        test_event = ConfigChangeEvent(
            file_path="test.yaml",
            change_type=ChangeType.MODIFIED,
        )
        manager._notify_callbacks(test_event)

        # 콜백이 스레드에서 실행되므로 약간 대기
        time.sleep(0.5)
        assert len(received) == 1
        assert received[0].file_path == "test.yaml"
        result.ok("_notify_callbacks() 실제 호출 확인")
    except Exception as e:
        result.fail("_notify_callbacks()", str(e))

    # 13-6. 다중 콜백 호출
    try:
        manager = create_manager()
        results_a = []
        results_b = []

        manager.register_callback(lambda e: results_a.append(e))
        manager.register_callback(lambda e: results_b.append(e))

        test_event = ConfigChangeEvent(
            file_path="multi.yaml",
            change_type=ChangeType.CREATED,
        )
        manager._notify_callbacks(test_event)
        time.sleep(0.5)

        assert len(results_a) == 1
        assert len(results_b) == 1
        result.ok("다중 콜백 호출 (2개)")
    except Exception as e:
        result.fail("다중 콜백", str(e))

    # 13-7. 콜백 예외 시 다른 콜백에 영향 없음
    try:
        manager = create_manager()
        safe_results = []

        def error_callback(event):
            raise RuntimeError("콜백 오류")

        def safe_callback(event):
            safe_results.append(event)

        manager.register_callback(error_callback)
        manager.register_callback(safe_callback)

        test_event = ConfigChangeEvent(
            file_path="error.yaml",
            change_type=ChangeType.MODIFIED,
        )
        manager._notify_callbacks(test_event)
        time.sleep(0.5)

        assert len(safe_results) == 1
        result.ok("콜백 예외 시 다른 콜백에 영향 없음")
    except Exception as e:
        result.fail("콜백 예외 격리", str(e))


# =============================================================================
# [14] HotReloadManager 내부 유틸리티
# =============================================================================
def test_manager_internal_utils(result: TestResult) -> None:
    """HotReloadManager 내부 유틸리티 테스트."""
    print("\n[14] HotReloadManager 내부 유틸리티")

    manager = create_manager()

    # 14-1. _find_changed_keys - 변경 없음
    try:
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 2}
        changed = manager._find_changed_keys(old, new)
        assert changed == []
        result.ok("_find_changed_keys() 변경 없음 → []")
    except Exception as e:
        result.fail("_find_changed_keys 변경 없음", str(e))

    # 14-2. _find_changed_keys - 단순 변경
    try:
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 99}
        changed = manager._find_changed_keys(old, new)
        assert changed == ["b"]
        result.ok("_find_changed_keys() 단순 변경 → ['b']")
    except Exception as e:
        result.fail("_find_changed_keys 단순 변경", str(e))

    # 14-3. _find_changed_keys - 키 추가
    try:
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        changed = manager._find_changed_keys(old, new)
        assert "b" in changed
        result.ok("_find_changed_keys() 키 추가 → ['b']")
    except Exception as e:
        result.fail("_find_changed_keys 키 추가", str(e))

    # 14-4. _find_changed_keys - 키 제거
    try:
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        changed = manager._find_changed_keys(old, new)
        assert "b" in changed
        result.ok("_find_changed_keys() 키 제거 → ['b']")
    except Exception as e:
        result.fail("_find_changed_keys 키 제거", str(e))

    # 14-5. _find_changed_keys - 중첩 딕셔너리
    try:
        old = {"gpu": {"precision": "fp16", "device_id": 0}}
        new = {"gpu": {"precision": "fp32", "device_id": 0}}
        changed = manager._find_changed_keys(old, new)
        assert "gpu.precision" in changed
        assert len(changed) == 1
        result.ok("_find_changed_keys() 중첩 → ['gpu.precision']")
    except Exception as e:
        result.fail("_find_changed_keys 중첩", str(e))

    # 14-6. _find_changed_keys - 다중 중첩
    try:
        old = {"a": {"b": {"c": 1, "d": 2}}, "x": 10}
        new = {"a": {"b": {"c": 99, "d": 2}}, "x": 20}
        changed = manager._find_changed_keys(old, new)
        assert "a.b.c" in changed
        assert "x" in changed
        assert len(changed) == 2
        result.ok("_find_changed_keys() 다중 중첩 → ['a.b.c', 'x']")
    except Exception as e:
        result.fail("_find_changed_keys 다중 중첩", str(e))

    # 14-7. _flatten_dict - 단순
    try:
        data = {"a": 1, "b": 2}
        flat = manager._flatten_dict(data)
        assert flat == {"a": 1, "b": 2}
        result.ok("_flatten_dict() 단순 → 그대로")
    except Exception as e:
        result.fail("_flatten_dict 단순", str(e))

    # 14-8. _flatten_dict - 중첩
    try:
        data = {"gpu": {"device_id": 0, "precision": "fp16"}, "version": "1.0"}
        flat = manager._flatten_dict(data)
        assert flat["gpu.device_id"] == 0
        assert flat["gpu.precision"] == "fp16"
        assert flat["version"] == "1.0"
        assert len(flat) == 3
        result.ok("_flatten_dict() 중첩 → 평탄화")
    except Exception as e:
        result.fail("_flatten_dict 중첩", str(e))

    # 14-9. _flatten_dict - 깊은 중첩
    try:
        data = {"a": {"b": {"c": {"d": 42}}}}
        flat = manager._flatten_dict(data)
        assert flat["a.b.c.d"] == 42
        assert len(flat) == 1
        result.ok("_flatten_dict() 깊은 중첩 → 'a.b.c.d'")
    except Exception as e:
        result.fail("_flatten_dict 깊은 중첩", str(e))

    # 14-10. _calculate_file_hash - 실제 파일
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("hash_key: hash_value\n")
            temp_path = Path(f.name)

        hash_val = manager._calculate_file_hash(temp_path)
        expected = hashlib.md5(temp_path.read_bytes()).hexdigest()
        assert hash_val == expected

        os.unlink(temp_path)
        result.ok("_calculate_file_hash() MD5 일치")
    except Exception as e:
        result.fail("_calculate_file_hash()", str(e))

    # 14-11. _calculate_file_hash - 존재하지 않는 파일
    try:
        hash_val = manager._calculate_file_hash(Path("nonexistent.yaml"))
        assert hash_val == ""
        result.ok("_calculate_file_hash() 미존재 → 빈 문자열")
    except Exception as e:
        result.fail("_calculate_file_hash() 미존재", str(e))

    # 14-12. get_status()
    try:
        status = manager.get_status()
        assert status["state"] == "STOPPED"
        assert status["is_running"] is False
        assert "statistics" in status
        assert "hot_reload_config" in status
        assert "watched_files_count" in status
        assert "debounce_time" in status
        result.ok("get_status() 구조 검증")
    except Exception as e:
        result.fail("get_status()", str(e))

    # 14-13. _queue_reload
    try:
        manager._queue_reload("test.yaml", ChangeType.MODIFIED)
        assert "test.yaml" in manager._reload_queue
        assert manager._reload_queue["test.yaml"] == ChangeType.MODIFIED
        # 정리
        manager._reload_queue.clear()
        result.ok("_queue_reload() 큐 추가")
    except Exception as e:
        result.fail("_queue_reload()", str(e))


# =============================================================================
# [15] 헬퍼 함수
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 테스트."""
    print("\n[15] 헬퍼 함수")

    # 15-1. create_hot_reload_manager() 기본
    try:
        ConfigLoader.reset_instance()
        manager = create_hot_reload_manager()
        assert isinstance(manager, HotReloadManager)
        assert manager.state == WatcherState.STOPPED
        result.ok("create_hot_reload_manager() 기본 생성")
    except Exception as e:
        result.fail("create_hot_reload_manager()", str(e))

    # 15-2. create_hot_reload_manager() 커스텀 인자
    try:
        ConfigLoader.reset_instance()
        loader = ConfigLoader.get_instance()
        validator = SchemaValidator()
        manager = create_hot_reload_manager(
            config_loader=loader,
            schema_validator=validator,
            debounce_time=1.0,
        )
        assert isinstance(manager, HotReloadManager)
        assert manager.debounce_time == 1.0
        result.ok("create_hot_reload_manager() 커스텀 인자")
    except Exception as e:
        result.fail("create_hot_reload_manager() 커스텀", str(e))

    # 15-3. watch_config() start_immediately=False
    try:
        ConfigLoader.reset_instance()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("watch_key: watch_value\n")
            temp_path = f.name

        callback_events = []

        def test_callback(event):
            callback_events.append(event)

        manager = watch_config(
            file_path=temp_path,
            callback=test_callback,
            start_immediately=False,
        )
        assert isinstance(manager, HotReloadManager)
        assert manager.is_running is False  # 시작 안 함
        assert len(manager._callbacks) == 1
        assert len(manager.watched_files) == 1

        os.unlink(temp_path)
        result.ok("watch_config(start_immediately=False)")
    except Exception as e:
        result.fail("watch_config()", str(e))


# =============================================================================
# [16] 엣지 케이스 및 모듈 Export
# =============================================================================
def test_edge_cases_and_exports(result: TestResult) -> None:
    """엣지 케이스 및 모듈 Export 테스트."""
    print("\n[16] 엣지 케이스 및 모듈 Export")

    # 16-1. __all__ Export 확인
    try:
        from core_foundation.config import watcher
        expected = {
            "ChangeType", "ReloadStatus", "WatcherState", "LogLevel",
            "HotReloadConfig", "ConfigChangeEvent", "WatchedFile", "ReloadStatistics",
            "ConfigChangeCallback",
            "HotReloadManager",
            "create_hot_reload_manager", "watch_config",
            "DEFAULT_DEBOUNCE_TIME", "SUPPORTED_EXTENSIONS",
            "DEFAULT_MAX_RETRIES", "DEFAULT_RETRY_INTERVAL", "DEFAULT_IGNORE_PATTERNS",
        }
        actual = set(watcher.__all__)
        assert actual == expected, f"차이: {actual.symmetric_difference(expected)}"
        result.ok(f"__all__ Export 확인 ({len(expected)}개)")
    except Exception as e:
        result.fail("__all__ Export", str(e))

    # 16-2. __version__
    try:
        from core_foundation.config import watcher
        assert watcher.__version__ == "1.0.0"
        result.ok("__version__ = 1.0.0")
    except Exception as e:
        result.fail("__version__", str(e))

    # 16-3. ConfigChangeEvent - timestamp UTC
    try:
        event = ConfigChangeEvent(
            file_path="tz.yaml",
            change_type=ChangeType.MODIFIED,
        )
        assert event.timestamp.tzinfo is not None
        result.ok("ConfigChangeEvent timestamp UTC")
    except Exception as e:
        result.fail("timestamp UTC", str(e))

    # 16-4. HotReloadConfig from_dict - 부분 on_failure
    try:
        data = {"on_failure": {"max_retries": 10}}
        config = HotReloadConfig.from_dict(data)
        assert config.max_retries == 10
        assert config.keep_previous_on_failure is True  # 기본값
        assert config.retry_interval == 5.0  # 기본값
        result.ok("from_dict() 부분 on_failure → 나머지 기본값")
    except Exception as e:
        result.fail("from_dict() 부분 on_failure", str(e))

    # 16-5. HotReloadConfig from_dict - 부분 notifications
    try:
        data = {"notifications": {"log_level": "ERROR"}}
        config = HotReloadConfig.from_dict(data)
        assert config.log_level == "ERROR"
        assert config.log_success is True  # 기본값
        result.ok("from_dict() 부분 notifications → 나머지 기본값")
    except Exception as e:
        result.fail("from_dict() 부분 notifications", str(e))

    # 16-6. ReloadStatistics to_dict - last_reload_time None
    try:
        stats = ReloadStatistics()
        d = stats.to_dict()
        assert d["last_reload_time"] is None
        result.ok("ReloadStatistics to_dict() last_reload_time=None")
    except Exception as e:
        result.fail("to_dict() None", str(e))

    # 16-7. WatchedFile 해시 빈 파일
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            pass  # 빈 파일
            temp_path = Path(f.name)

        wf = WatchedFile(path=temp_path)
        changed = wf.update_hash()
        assert changed is True  # "" → 해시값
        assert wf.last_hash == hashlib.md5(b"").hexdigest()

        os.unlink(temp_path)
        result.ok("WatchedFile 빈 파일 해시")
    except Exception as e:
        result.fail("빈 파일 해시", str(e))

    # 16-8. _find_changed_keys 빈 딕셔너리
    try:
        manager = create_manager()
        changed = manager._find_changed_keys({}, {})
        assert changed == []
        result.ok("_find_changed_keys({}, {}) → []")
    except Exception as e:
        result.fail("_find_changed_keys({})", str(e))

    # 16-9. _find_changed_keys 한쪽만 빈 딕셔너리
    try:
        manager = create_manager()
        changed = manager._find_changed_keys({}, {"a": 1, "b": 2})
        assert "a" in changed
        assert "b" in changed
        assert len(changed) == 2
        result.ok("_find_changed_keys({}, {a,b}) → ['a','b']")
    except Exception as e:
        result.fail("_find_changed_keys 한쪽 빈", str(e))

    # 16-10. _flatten_dict 빈 딕셔너리
    try:
        manager = create_manager()
        flat = manager._flatten_dict({})
        assert flat == {}
        result.ok("_flatten_dict({}) → {}")
    except Exception as e:
        result.fail("_flatten_dict({})", str(e))

    # 16-11. ConfigChangeCallback 타입 별칭
    try:
        # ConfigChangeCallback이 Callable 타입 별칭인지 확인
        assert ConfigChangeCallback is not None
        result.ok("ConfigChangeCallback 타입 별칭 존재")
    except Exception as e:
        result.fail("ConfigChangeCallback", str(e))

    # 16-12. HotReloadManager 스레드 안전 (기본 속성 접근)
    try:
        manager = create_manager()
        errors = []

        def access_properties():
            try:
                for _ in range(100):
                    _ = manager.state
                    _ = manager.is_running
                    _ = manager.debounce_time
                    _ = manager.watched_files
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=access_properties) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"스레드 오류: {errors}"
        result.ok("스레드 안전 프로퍼티 접근 (4 스레드)")
    except Exception as e:
        result.fail("스레드 안전", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """메인 실행."""
    print("=" * 60)
    print("COURTVIEW - HotReloadManager 단위 테스트")
    print("대상: core_foundation/config/watcher.py")
    print("=" * 60)

    r = TestResult()

    test_constants(r)
    test_change_type_enum(r)
    test_reload_status_enum(r)
    test_watcher_state_enum(r)
    test_log_level_enum(r)
    test_hot_reload_config(r)
    test_config_change_event(r)
    test_watched_file(r)
    test_reload_statistics(r)
    test_event_handler_filtering(r)
    test_manager_init_and_properties(r)
    test_manager_watch(r)
    test_manager_callbacks(r)
    test_manager_internal_utils(r)
    test_helper_functions(r)
    test_edge_cases_and_exports(r)

    r.summary()
    return r.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
