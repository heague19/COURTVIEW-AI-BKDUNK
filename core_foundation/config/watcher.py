# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: watcher.py
설명: 설정 파일 변경 감지 및 자동 리로드

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 설정 파일 변경 실시간 감지 (watchdog 기반)
    - 변경 감지 시 자동 리로드 및 검증
    - 콜백 기반 변경 알림 시스템
    - 디바운싱으로 중복 이벤트 방지
    - 스레드 안전 구현
    - 다중 파일/디렉토리 감시 지원
    - config.yaml 기반 동적 설정 로드 (하드코딩 제거)
    - 실패 시 재시도 로직
    - ignore_patterns 지원

사용 예시:
    # 기본 사용
    manager = HotReloadManager(config_loader, schema_validator)
    manager.watch("config/app.yaml")
    manager.register_callback(on_config_changed)
    manager.start()

    # 콜백 정의
    def on_config_changed(event: ConfigChangeEvent) -> None:
        print(f"설정 변경됨: {event.file_path}")
        print(f"변경된 키: {event.changed_keys}")
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import fnmatch
import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Callable,
    TypeAlias,
)

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    DirModifiedEvent,
)

# =============================================================================
# 프로젝트 모듈 (shared)
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.constants.status_codes import ServiceStatus
from shared.exceptions.validation_exceptions import ConfigurationException

# =============================================================================
# 프로젝트 모듈 (utils)
# =============================================================================
from utils.time_utils import get_current_timestamp, Timer

# =============================================================================
# 프로젝트 모듈 (core_foundation)
# =============================================================================
from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import SchemaValidator, AppConfig

# =============================================================================
# 로거 설정
# =============================================================================
logger = logging.getLogger(__name__)


# =============================================================================
# 타입 별칭
# =============================================================================
ConfigChangeCallback: TypeAlias = Callable[["ConfigChangeEvent"], None]


# =============================================================================
# 기본 상수 정의 (config.yaml에서 오버라이드 가능)
# =============================================================================
# 기본 디바운스 시간 (초) - config.yaml의 hot_reload.debounce_ms로 오버라이드
DEFAULT_DEBOUNCE_TIME: float = 0.5

# 최대 디바운스 시간 (초)
MAX_DEBOUNCE_TIME: float = 5.0

# 기본 폴링 간격 (초)
DEFAULT_POLL_INTERVAL: float = 1.0

# 지원하는 설정 파일 확장자 - config.yaml의 hot_reload.watch_patterns로 오버라이드
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".yaml", ".yml", ".json")

# 콜백 실행 타임아웃 (초) - config.yaml의 hot_reload.callback_timeout로 오버라이드
CALLBACK_TIMEOUT: float = 30.0

# 기본 최대 재시도 횟수 - config.yaml의 hot_reload.on_failure.max_retries로 오버라이드
DEFAULT_MAX_RETRIES: int = 3

# 기본 재시도 간격 (초) - config.yaml의 hot_reload.on_failure.retry_interval로 오버라이드
DEFAULT_RETRY_INTERVAL: float = 5.0

# 기본 무시 패턴 - config.yaml의 hot_reload.ignore_patterns로 오버라이드
DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = ("*.tmp", "*.bak", ".*", "__pycache__")


# =============================================================================
# Enum 정의
# =============================================================================
class ChangeType(Enum):
    """
    설정 변경 유형.

    파일 시스템에서 감지된 변경의 종류를 나타냅니다.
    """

    CREATED = auto()   # 파일 생성됨
    MODIFIED = auto()  # 파일 수정됨
    DELETED = auto()   # 파일 삭제됨
    MOVED = auto()     # 파일 이동됨


class ReloadStatus(Enum):
    """
    리로드 상태.

    설정 리로드 작업의 결과 상태를 나타냅니다.
    """

    SUCCESS = "success"               # 리로드 성공
    FAILED = "failed"                 # 리로드 실패
    VALIDATION_ERROR = "validation_error"  # 검증 실패
    SKIPPED = "skipped"               # 스킵됨 (동일 내용)
    PENDING = "pending"               # 대기 중
    RETRYING = "retrying"             # 재시도 중


class WatcherState(Enum):
    """
    감시자 상태.

    HotReloadManager의 상태를 나타냅니다.
    """

    STOPPED = auto()    # 정지됨
    STARTING = auto()   # 시작 중
    RUNNING = auto()    # 실행 중
    STOPPING = auto()   # 정지 중
    ERROR = auto()      # 오류 상태


class LogLevel(Enum):
    """로그 레벨."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass
class HotReloadConfig:
    """
    핫 리로드 설정.

    config.yaml의 hot_reload 섹션에서 로드됩니다.

    Attributes:
        enabled: 핫 리로드 활성화 여부
        watch_directories: 감시 대상 디렉토리 목록
        watch_patterns: 감시 대상 파일 패턴 목록
        ignore_patterns: 무시할 파일 패턴 목록
        debounce_ms: 디바운스 시간 (밀리초)
        callback_timeout: 콜백 실행 타임아웃 (초)
        keep_previous_on_failure: 실패 시 이전 설정 유지 여부
        max_retries: 최대 재시도 횟수
        retry_interval: 재시도 간격 (초)
        log_success: 성공 시 로그 출력 여부
        log_failure: 실패 시 로그 출력 여부
        log_level: 로그 레벨
    """

    enabled: bool = True
    watch_directories: list[str] = field(default_factory=lambda: ["configs"])
    watch_patterns: list[str] = field(default_factory=lambda: ["*.yaml", "*.yml", "*.json"])
    ignore_patterns: list[str] = field(default_factory=lambda: ["*.tmp", "*.bak", ".*", "__pycache__"])
    debounce_ms: int = 500
    callback_timeout: float = 30.0
    keep_previous_on_failure: bool = True
    max_retries: int = 3
    retry_interval: float = 5.0
    log_success: bool = True
    log_failure: bool = True
    log_level: str = "INFO"

    @property
    def debounce_seconds(self) -> float:
        """디바운스 시간 (초)."""
        return self.debounce_ms / 1000.0

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """지원하는 확장자 튜플로 변환."""
        extensions = []
        for pattern in self.watch_patterns:
            if pattern.startswith("*."):
                ext = pattern[1:]  # *.yaml -> .yaml
                extensions.append(ext)
        return tuple(extensions) if extensions else SUPPORTED_EXTENSIONS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HotReloadConfig":
        """딕셔너리에서 생성."""
        on_failure = data.get("on_failure", {})
        notifications = data.get("notifications", {})

        return cls(
            enabled=data.get("enabled", True),
            watch_directories=data.get("watch_directories", ["configs"]),
            watch_patterns=data.get("watch_patterns", ["*.yaml", "*.yml", "*.json"]),
            ignore_patterns=data.get("ignore_patterns", ["*.tmp", "*.bak", ".*", "__pycache__"]),
            debounce_ms=data.get("debounce_ms", 500),
            callback_timeout=data.get("callback_timeout", 30.0),
            keep_previous_on_failure=on_failure.get("keep_previous", True),
            max_retries=on_failure.get("max_retries", 3),
            retry_interval=on_failure.get("retry_interval", 5.0),
            log_success=notifications.get("log_success", True),
            log_failure=notifications.get("log_failure", True),
            log_level=notifications.get("log_level", "INFO"),
        )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "enabled": self.enabled,
            "watch_directories": self.watch_directories,
            "watch_patterns": self.watch_patterns,
            "ignore_patterns": self.ignore_patterns,
            "debounce_ms": self.debounce_ms,
            "callback_timeout": self.callback_timeout,
            "on_failure": {
                "keep_previous": self.keep_previous_on_failure,
                "max_retries": self.max_retries,
                "retry_interval": self.retry_interval,
            },
            "notifications": {
                "log_success": self.log_success,
                "log_failure": self.log_failure,
                "log_level": self.log_level,
            },
        }


@dataclass
class ConfigChangeEvent:
    """
    설정 변경 이벤트.

    파일 변경이 감지되었을 때 생성되는 이벤트입니다.

    Attributes:
        file_path: 변경된 파일 경로
        change_type: 변경 유형
        timestamp: 변경 감지 시각
        old_config: 이전 설정 (수정/삭제 시)
        new_config: 새 설정 (생성/수정 시)
        changed_keys: 변경된 설정 키 목록
        reload_status: 리로드 결과 상태
        error_message: 오류 메시지 (실패 시)
        reload_duration_ms: 리로드 소요 시간 (밀리초)
        retry_count: 재시도 횟수
    """

    file_path: str
    change_type: ChangeType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    old_config: dict[str, Any] | None = None
    new_config: dict[str, Any] | None = None
    changed_keys: list[str] = field(default_factory=list)
    reload_status: ReloadStatus = ReloadStatus.PENDING
    error_message: str | None = None
    reload_duration_ms: float = 0.0
    retry_count: int = 0

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if isinstance(self.file_path, Path):
            self.file_path = str(self.file_path)

    @property
    def is_success(self) -> bool:
        """리로드 성공 여부."""
        return self.reload_status == ReloadStatus.SUCCESS

    @property
    def has_changes(self) -> bool:
        """실제 설정 변경이 있었는지 여부."""
        return len(self.changed_keys) > 0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "file_path": self.file_path,
            "change_type": self.change_type.name,
            "timestamp": self.timestamp.isoformat(),
            "changed_keys": self.changed_keys,
            "reload_status": self.reload_status.value,
            "error_message": self.error_message,
            "reload_duration_ms": self.reload_duration_ms,
            "retry_count": self.retry_count,
            "has_changes": self.has_changes,
        }


@dataclass
class WatchedFile:
    """
    감시 중인 파일 정보.

    Attributes:
        path: 파일 경로
        last_hash: 마지막 파일 해시
        last_modified: 마지막 수정 시각
        last_reload: 마지막 리로드 시각
        reload_count: 리로드 횟수
        error_count: 오류 발생 횟수
        consecutive_errors: 연속 오류 횟수
        is_valid: 유효 여부
    """

    path: Path
    last_hash: str = ""
    last_modified: datetime | None = None
    last_reload: datetime | None = None
    reload_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    is_valid: bool = True

    def update_hash(self) -> bool:
        """
        파일 해시 업데이트.

        Returns:
            해시가 변경되었으면 True
        """
        if not self.path.exists():
            return False

        new_hash = self._calculate_hash()
        changed = new_hash != self.last_hash
        self.last_hash = new_hash
        self.last_modified = datetime.now(timezone.utc)
        return changed

    def _calculate_hash(self) -> str:
        """파일 내용 해시 계산."""
        try:
            content = self.path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

    def mark_reloaded(self, success: bool) -> None:
        """리로드 완료 표시."""
        self.last_reload = datetime.now(timezone.utc)
        self.reload_count += 1
        if success:
            self.consecutive_errors = 0
        else:
            self.error_count += 1
            self.consecutive_errors += 1


@dataclass
class ReloadStatistics:
    """
    리로드 통계.

    Attributes:
        total_reloads: 총 리로드 횟수
        successful_reloads: 성공한 리로드 횟수
        failed_reloads: 실패한 리로드 횟수
        validation_errors: 검증 실패 횟수
        skipped_reloads: 스킵된 리로드 횟수
        retry_attempts: 재시도 횟수
        total_reload_time_ms: 총 리로드 시간 (밀리초)
        last_reload_time: 마지막 리로드 시각
        average_reload_time_ms: 평균 리로드 시간 (밀리초)
    """

    total_reloads: int = 0
    successful_reloads: int = 0
    failed_reloads: int = 0
    validation_errors: int = 0
    skipped_reloads: int = 0
    retry_attempts: int = 0
    total_reload_time_ms: float = 0.0
    last_reload_time: datetime | None = None

    @property
    def average_reload_time_ms(self) -> float:
        """평균 리로드 시간."""
        if self.successful_reloads == 0:
            return 0.0
        return self.total_reload_time_ms / self.successful_reloads

    @property
    def success_rate(self) -> float:
        """성공률 (0.0 ~ 1.0)."""
        if self.total_reloads == 0:
            return 1.0
        return self.successful_reloads / self.total_reloads

    def record_reload(self, status: ReloadStatus, duration_ms: float) -> None:
        """리로드 기록."""
        self.total_reloads += 1
        self.last_reload_time = datetime.now(timezone.utc)

        if status == ReloadStatus.SUCCESS:
            self.successful_reloads += 1
            self.total_reload_time_ms += duration_ms
        elif status == ReloadStatus.FAILED:
            self.failed_reloads += 1
        elif status == ReloadStatus.VALIDATION_ERROR:
            self.validation_errors += 1
        elif status == ReloadStatus.SKIPPED:
            self.skipped_reloads += 1
        elif status == ReloadStatus.RETRYING:
            self.retry_attempts += 1

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "total_reloads": self.total_reloads,
            "successful_reloads": self.successful_reloads,
            "failed_reloads": self.failed_reloads,
            "validation_errors": self.validation_errors,
            "skipped_reloads": self.skipped_reloads,
            "retry_attempts": self.retry_attempts,
            "success_rate": self.success_rate,
            "average_reload_time_ms": self.average_reload_time_ms,
            "last_reload_time": (
                self.last_reload_time.isoformat() if self.last_reload_time else None
            ),
        }


# =============================================================================
# 파일 시스템 이벤트 핸들러
# =============================================================================
class ConfigFileEventHandler(FileSystemEventHandler):
    """
    설정 파일 이벤트 핸들러.

    watchdog 이벤트를 처리하고 HotReloadManager에 전달합니다.
    ignore_patterns를 지원하여 불필요한 파일 변경을 무시합니다.
    """

    def __init__(
        self,
        manager: "HotReloadManager",
        watched_files: set[str],
        supported_extensions: tuple[str, ...],
        ignore_patterns: list[str],
    ) -> None:
        """
        초기화.

        Args:
            manager: HotReloadManager 인스턴스
            watched_files: 감시 대상 파일 경로 집합
            supported_extensions: 지원하는 파일 확장자
            ignore_patterns: 무시할 파일 패턴 목록
        """
        super().__init__()
        self._manager = manager
        self._watched_files = watched_files
        self._supported_extensions = supported_extensions
        self._ignore_patterns = ignore_patterns
        self._pending_events: dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_ignore(self, file_path: str) -> bool:
        """
        파일이 무시 대상인지 확인.

        Args:
            file_path: 파일 경로

        Returns:
            무시해야 하면 True
        """
        file_name = Path(file_path).name

        for pattern in self._ignore_patterns:
            # 정확한 매칭
            if fnmatch.fnmatch(file_name, pattern):
                return True

            # 숨김 파일 패턴 (.*) 처리
            if pattern == ".*" and file_name.startswith("."):
                return True

            # __pycache__ 등 디렉토리 패턴
            if pattern in file_path:
                return True

        return False

    def _should_process(self, file_path: str) -> bool:
        """파일 처리 대상 여부 확인."""
        # 무시 패턴 확인
        if self._should_ignore(file_path):
            return False

        path = Path(file_path)

        # 확장자 확인
        if path.suffix.lower() not in self._supported_extensions:
            return False

        # 감시 대상 확인
        abs_path = str(path.resolve())
        for watched in self._watched_files:
            watched_path = Path(watched).resolve()
            if abs_path == str(watched_path):
                return True
            # 디렉토리 감시인 경우
            if watched_path.is_dir() and abs_path.startswith(str(watched_path)):
                return True

        return False

    def _debounce(self, file_path: str) -> bool:
        """
        디바운싱 처리.

        짧은 시간 내 중복 이벤트를 필터링합니다.

        Args:
            file_path: 파일 경로

        Returns:
            이벤트 처리해야 하면 True
        """
        current_time = get_current_timestamp()
        debounce_time = self._manager.debounce_time

        with self._lock:
            last_event_time = self._pending_events.get(file_path, 0)

            if current_time - last_event_time < debounce_time:
                return False

            self._pending_events[file_path] = current_time
            return True

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent) -> None:
        """파일 수정 이벤트 처리."""
        if event.is_directory:
            return

        file_path = event.src_path
        if not self._should_process(file_path):
            return

        if self._debounce(file_path):
            logger.debug(f"설정 파일 수정 감지: {file_path}")
            self._manager._queue_reload(file_path, ChangeType.MODIFIED)

    def on_created(self, event: FileCreatedEvent) -> None:
        """파일 생성 이벤트 처리."""
        if event.is_directory:
            return

        file_path = event.src_path
        if not self._should_process(file_path):
            return

        if self._debounce(file_path):
            logger.debug(f"설정 파일 생성 감지: {file_path}")
            self._manager._queue_reload(file_path, ChangeType.CREATED)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """파일 삭제 이벤트 처리."""
        if event.is_directory:
            return

        file_path = event.src_path
        if not self._should_process(file_path):
            return

        logger.warning(f"설정 파일 삭제됨: {file_path}")
        self._manager._handle_deleted(file_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """파일 이동 이벤트 처리."""
        if event.is_directory:
            return

        # 원본 파일 삭제 처리
        if self._should_process(event.src_path):
            logger.debug(f"설정 파일 이동됨 (원본): {event.src_path}")
            self._manager._handle_deleted(event.src_path)

        # 대상 파일 생성 처리
        if self._should_process(event.dest_path):
            if self._debounce(event.dest_path):
                logger.debug(f"설정 파일 이동됨 (대상): {event.dest_path}")
                self._manager._queue_reload(event.dest_path, ChangeType.MOVED)


# =============================================================================
# HotReloadManager 클래스
# =============================================================================
class HotReloadManager:
    """
    설정 핫 리로드 매니저.

    설정 파일 변경을 감지하고 자동으로 리로드합니다.
    DI 패턴을 사용하여 ConfigLoader와 SchemaValidator를 주입받습니다.
    config.yaml의 hot_reload 섹션에서 설정을 동적으로 로드합니다.

    주요 기능:
        - 파일 변경 실시간 감시 (watchdog)
        - 변경 감지 시 자동 리로드
        - 스키마 검증 후 적용
        - 콜백 기반 변경 알림
        - 디바운싱으로 중복 방지
        - 스레드 안전 구현
        - ignore_patterns 지원
        - 실패 시 재시도 로직
        - config.yaml 기반 동적 설정

    Example:
        >>> loader = ConfigLoader.get_instance()
        >>> validator = SchemaValidator()
        >>> manager = HotReloadManager(loader, validator)
        >>> manager.watch("config/app.yaml")
        >>> manager.register_callback(lambda e: print(f"Changed: {e.file_path}"))
        >>> manager.start()
        >>> # ... 애플리케이션 실행 ...
        >>> manager.stop()
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        schema_validator: SchemaValidator | None = None,
        debounce_time: float | None = None,
        validate_on_reload: bool = True,
        auto_apply: bool = True,
    ) -> None:
        """
        초기화.

        Args:
            config_loader: 설정 로더 인스턴스 (DI 주입)
            schema_validator: 스키마 검증기 인스턴스 (DI 주입, 선택적)
            debounce_time: 디바운스 시간 (초, None이면 config.yaml에서 로드)
            validate_on_reload: 리로드 시 스키마 검증 여부
            auto_apply: 검증 성공 시 자동 적용 여부
        """
        # DI 주입 의존성
        self._config_loader = config_loader
        self._schema_validator = schema_validator

        # config.yaml에서 hot_reload 설정 로드
        self._hot_reload_config = self._load_hot_reload_config()

        # 디바운스 시간 설정 (파라미터 > config.yaml > 기본값)
        if debounce_time is not None:
            self._debounce_time = min(max(debounce_time, 0.1), MAX_DEBOUNCE_TIME)
        else:
            self._debounce_time = min(
                max(self._hot_reload_config.debounce_seconds, 0.1),
                MAX_DEBOUNCE_TIME
            )

        # 설정
        self._validate_on_reload = validate_on_reload
        self._auto_apply = auto_apply

        # 상태
        self._state: WatcherState = WatcherState.STOPPED
        self._state_lock = threading.RLock()

        # watchdog 옵저버 (Observer 타입, watchdog 라이브러리)
        self._observer: Any | None = None

        # 감시 대상 파일/디렉토리
        self._watched_paths: set[str] = set()
        self._watched_files: dict[str, WatchedFile] = {}
        self._paths_lock = threading.Lock()

        # 콜백 관리
        self._callbacks: list[ConfigChangeCallback] = []
        self._callbacks_lock = threading.Lock()

        # 리로드 큐 (디바운싱 후 처리)
        self._reload_queue: dict[str, ChangeType] = {}
        self._queue_lock = threading.Lock()

        # 리로드 처리 스레드
        self._reload_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # 통계
        self._statistics = ReloadStatistics()

        # 마지막 설정 스냅샷 (변경 감지용)
        self._config_snapshot: dict[str, Any] = {}

        # 로그 레벨 설정
        self._configure_logging()

        self._log_info(
            f"HotReloadManager 초기화 완료 "
            f"(debounce={self._debounce_time}s, "
            f"validate={self._validate_on_reload}, "
            f"auto_apply={self._auto_apply}, "
            f"max_retries={self._hot_reload_config.max_retries})"
        )

    def _load_hot_reload_config(self) -> HotReloadConfig:
        """
        config.yaml에서 hot_reload 설정 로드.

        Returns:
            HotReloadConfig 인스턴스
        """
        try:
            hot_reload_data = self._config_loader.get("hot_reload", {})
            if hot_reload_data:
                config = HotReloadConfig.from_dict(hot_reload_data)
                logger.debug(f"hot_reload 설정 로드됨: {config.to_dict()}")
                return config
        except Exception as e:
            logger.warning(f"hot_reload 설정 로드 실패, 기본값 사용: {e}")

        return HotReloadConfig()

    def _configure_logging(self) -> None:
        """로그 레벨 설정."""
        log_level_str = self._hot_reload_config.log_level.upper()
        try:
            log_level = getattr(logging, log_level_str, logging.INFO)
            # 모듈 로거 레벨은 변경하지 않고, 설정만 저장
            self._log_level = log_level
        except Exception:
            self._log_level = logging.INFO

    def _log_info(self, message: str) -> None:
        """조건부 INFO 로깅."""
        if self._hot_reload_config.log_success:
            logger.info(message)

    def _log_error(self, message: str) -> None:
        """조건부 ERROR 로깅."""
        if self._hot_reload_config.log_failure:
            logger.error(message)

    def _log_warning(self, message: str) -> None:
        """조건부 WARNING 로깅."""
        if self._hot_reload_config.log_failure:
            logger.warning(message)

    # --------------------------------------------------------
    # 프로퍼티
    # --------------------------------------------------------
    @property
    def state(self) -> WatcherState:
        """현재 상태."""
        with self._state_lock:
            return self._state

    @property
    def is_running(self) -> bool:
        """실행 중 여부."""
        return self.state == WatcherState.RUNNING

    @property
    def debounce_time(self) -> float:
        """디바운스 시간 (초)."""
        return self._debounce_time

    @debounce_time.setter
    def debounce_time(self, value: float) -> None:
        """디바운스 시간 설정."""
        self._debounce_time = min(max(value, 0.1), MAX_DEBOUNCE_TIME)

    @property
    def statistics(self) -> ReloadStatistics:
        """리로드 통계."""
        return self._statistics

    @property
    def watched_files(self) -> list[str]:
        """감시 중인 파일 목록."""
        with self._paths_lock:
            return list(self._watched_paths)

    @property
    def service_status(self) -> ServiceStatus:
        """서비스 상태 반환."""
        state = self.state
        if state == WatcherState.RUNNING:
            return ServiceStatus.HEALTHY
        elif state == WatcherState.ERROR:
            return ServiceStatus.UNHEALTHY
        elif state in (WatcherState.STARTING, WatcherState.STOPPING):
            return ServiceStatus.DEGRADED
        return ServiceStatus.STOPPED

    @property
    def hot_reload_config(self) -> HotReloadConfig:
        """핫 리로드 설정."""
        return self._hot_reload_config

    @property
    def ignore_patterns(self) -> list[str]:
        """무시 패턴 목록."""
        return self._hot_reload_config.ignore_patterns

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """지원하는 파일 확장자."""
        return self._hot_reload_config.supported_extensions

    # --------------------------------------------------------
    # 감시 관리 메서드
    # --------------------------------------------------------
    def watch(
        self,
        path: str | Path,
        recursive: bool = False,
    ) -> None:
        """
        파일 또는 디렉토리 감시 등록.

        Args:
            path: 감시할 파일 또는 디렉토리 경로
            recursive: 디렉토리인 경우 재귀 감시 여부

        Raises:
            ConfigurationException: 경로가 유효하지 않은 경우
        """
        path_obj = Path(path).resolve()

        if not path_obj.exists():
            logger.warning(f"감시 대상 경로가 존재하지 않음: {path}")
            # 향후 생성될 수 있으므로 등록은 진행

        with self._paths_lock:
            path_str = str(path_obj)

            if path_str in self._watched_paths:
                logger.debug(f"이미 감시 중인 경로: {path}")
                return

            self._watched_paths.add(path_str)

            # 파일인 경우 WatchedFile 생성
            if path_obj.is_file():
                self._watched_files[path_str] = WatchedFile(
                    path=path_obj,
                    last_hash=self._calculate_file_hash(path_obj),
                )

            self._log_info(f"감시 등록: {path} (recursive={recursive})")

        # 실행 중이면 옵저버에 추가
        if self.is_running and self._observer:
            self._add_to_observer(path_str, recursive)

    def unwatch(self, path: str | Path) -> None:
        """
        감시 해제.

        Args:
            path: 감시 해제할 경로
        """
        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        with self._paths_lock:
            if path_str in self._watched_paths:
                self._watched_paths.discard(path_str)
                self._watched_files.pop(path_str, None)
                self._log_info(f"감시 해제: {path}")

    def watch_multiple(
        self,
        paths: list[str | Path],
        recursive: bool = False,
    ) -> None:
        """
        여러 경로 감시 등록.

        Args:
            paths: 감시할 경로 목록
            recursive: 재귀 감시 여부
        """
        for path in paths:
            self.watch(path, recursive)

    def watch_from_config(self) -> None:
        """config.yaml의 watch_directories 설정에서 감시 경로 등록."""
        for directory in self._hot_reload_config.watch_directories:
            path = Path(directory)
            if path.exists():
                self.watch(path, recursive=True)
            else:
                logger.warning(f"config.yaml에 지정된 감시 디렉토리 없음: {directory}")

    # --------------------------------------------------------
    # 콜백 관리 메서드
    # --------------------------------------------------------
    def register_callback(self, callback: ConfigChangeCallback) -> None:
        """
        변경 콜백 등록.

        Args:
            callback: 변경 시 호출될 콜백 함수
        """
        with self._callbacks_lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
                callback_name = getattr(callback, "__name__", repr(callback))
                logger.debug(f"콜백 등록됨: {callback_name}")

    def unregister_callback(self, callback: ConfigChangeCallback) -> None:
        """
        콜백 등록 해제.

        Args:
            callback: 해제할 콜백 함수
        """
        with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
                callback_name = getattr(callback, "__name__", repr(callback))
                logger.debug(f"콜백 해제됨: {callback_name}")

    def clear_callbacks(self) -> None:
        """모든 콜백 제거."""
        with self._callbacks_lock:
            self._callbacks.clear()
            logger.debug("모든 콜백 제거됨")

    # --------------------------------------------------------
    # 시작/중지 메서드
    # --------------------------------------------------------
    def start(self) -> None:
        """
        감시 시작.

        Raises:
            ConfigurationException: 이미 실행 중이거나 시작 실패 시
        """
        # enabled 확인
        if not self._hot_reload_config.enabled:
            logger.warning("핫 리로드가 config.yaml에서 비활성화되어 있습니다")
            return

        with self._state_lock:
            if self._state == WatcherState.RUNNING:
                logger.warning("HotReloadManager가 이미 실행 중입니다")
                return

            if self._state == WatcherState.STARTING:
                logger.warning("HotReloadManager가 시작 중입니다")
                return

            self._state = WatcherState.STARTING

        try:
            # 현재 설정 스냅샷 저장
            self._config_snapshot = self._config_loader.to_dict()

            # watchdog 옵저버 생성
            self._observer = Observer()

            # 감시 대상 등록
            with self._paths_lock:
                for path_str in self._watched_paths:
                    self._add_to_observer(path_str, recursive=False)

            # 옵저버 시작
            self._observer.start()

            # 리로드 처리 스레드 시작
            self._stop_event.clear()
            self._reload_thread = threading.Thread(
                target=self._reload_worker,
                name="HotReloadWorker",
                daemon=True,
            )
            self._reload_thread.start()

            with self._state_lock:
                self._state = WatcherState.RUNNING

            self._log_info("HotReloadManager 시작됨")

        except Exception as e:
            with self._state_lock:
                self._state = WatcherState.ERROR

            self._log_error(f"HotReloadManager 시작 실패: {e}")
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_LOAD_FAILED,
                message=f"핫 리로드 매니저 시작 실패: {e}",
                cause=e,
            )

    def stop(self, timeout: float = 5.0) -> None:
        """
        감시 중지.

        Args:
            timeout: 종료 대기 시간 (초)
        """
        with self._state_lock:
            if self._state == WatcherState.STOPPED:
                return

            if self._state == WatcherState.STOPPING:
                return

            self._state = WatcherState.STOPPING

        # 리로드 스레드 중지
        self._stop_event.set()

        if self._reload_thread and self._reload_thread.is_alive():
            self._reload_thread.join(timeout=timeout)

        # 옵저버 중지
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=timeout)
            self._observer = None

        with self._state_lock:
            self._state = WatcherState.STOPPED

        self._log_info("HotReloadManager 중지됨")

    def restart(self) -> None:
        """감시 재시작."""
        self.stop()
        self.start()

    # --------------------------------------------------------
    # 수동 리로드 메서드
    # --------------------------------------------------------
    def reload(self, file_path: str | Path | None = None) -> ConfigChangeEvent:
        """
        수동 리로드 실행.

        Args:
            file_path: 리로드할 파일 (None이면 모든 파일)

        Returns:
            리로드 결과 이벤트
        """
        if file_path:
            path_str = str(Path(file_path).resolve())
            return self._perform_reload_with_retry(path_str, ChangeType.MODIFIED)

        # 모든 감시 파일 리로드
        events = []
        with self._paths_lock:
            for path_str, watched_file in self._watched_files.items():
                if watched_file.path.is_file():
                    event = self._perform_reload_with_retry(path_str, ChangeType.MODIFIED)
                    events.append(event)

        # 마지막 이벤트 반환 (또는 빈 이벤트)
        if events:
            return events[-1]

        return ConfigChangeEvent(
            file_path="",
            change_type=ChangeType.MODIFIED,
            reload_status=ReloadStatus.SKIPPED,
        )

    def reload_all(self) -> list[ConfigChangeEvent]:
        """
        모든 감시 파일 리로드.

        Returns:
            리로드 결과 이벤트 목록
        """
        events = []
        with self._paths_lock:
            for path_str, watched_file in self._watched_files.items():
                if watched_file.path.is_file() and watched_file.path.exists():
                    event = self._perform_reload_with_retry(path_str, ChangeType.MODIFIED)
                    events.append(event)

        return events

    def reload_config(self) -> None:
        """hot_reload 설정 자체를 다시 로드."""
        self._hot_reload_config = self._load_hot_reload_config()
        self._configure_logging()
        logger.debug("hot_reload 설정이 다시 로드됨")

    # --------------------------------------------------------
    # 내부 메서드
    # --------------------------------------------------------
    def _add_to_observer(self, path_str: str, recursive: bool) -> None:
        """옵저버에 감시 경로 추가."""
        if not self._observer:
            return

        path_obj = Path(path_str)

        # 이벤트 핸들러 생성 (ignore_patterns 전달)
        handler = ConfigFileEventHandler(
            manager=self,
            watched_files=self._watched_paths,
            supported_extensions=self._hot_reload_config.supported_extensions,
            ignore_patterns=self._hot_reload_config.ignore_patterns,
        )

        # 감시 대상 디렉토리 결정
        if path_obj.is_file():
            watch_path = str(path_obj.parent)
        else:
            watch_path = str(path_obj)

        try:
            self._observer.schedule(
                handler,
                watch_path,
                recursive=recursive,
            )
            logger.debug(f"옵저버에 경로 추가: {watch_path}")
        except Exception as e:
            self._log_error(f"옵저버 경로 추가 실패: {watch_path}, 오류: {e}")

    def _queue_reload(self, file_path: str, change_type: ChangeType) -> None:
        """리로드 큐에 추가."""
        with self._queue_lock:
            self._reload_queue[file_path] = change_type

    def _handle_deleted(self, file_path: str) -> None:
        """파일 삭제 처리."""
        event = ConfigChangeEvent(
            file_path=file_path,
            change_type=ChangeType.DELETED,
            reload_status=ReloadStatus.SKIPPED,
        )

        # 콜백 호출
        self._notify_callbacks(event)

    def _reload_worker(self) -> None:
        """리로드 처리 워커 스레드."""
        poll_interval = self._hot_reload_config.retry_interval or DEFAULT_POLL_INTERVAL

        while not self._stop_event.is_set():
            try:
                # 큐에서 리로드 대상 가져오기
                pending_reloads: dict[str, ChangeType] = {}

                with self._queue_lock:
                    if self._reload_queue:
                        pending_reloads = self._reload_queue.copy()
                        self._reload_queue.clear()

                # 리로드 실행
                for file_path, change_type in pending_reloads.items():
                    if self._stop_event.is_set():
                        break
                    self._perform_reload_with_retry(file_path, change_type)

            except Exception as e:
                self._log_error(f"리로드 워커 오류: {e}")

            # 다음 폴링까지 대기 (config.yaml의 retry_interval 반영)
            self._stop_event.wait(timeout=poll_interval)

    def _perform_reload_with_retry(
        self,
        file_path: str,
        change_type: ChangeType,
    ) -> ConfigChangeEvent:
        """
        재시도 로직이 포함된 리로드 수행.

        Args:
            file_path: 파일 경로
            change_type: 변경 유형

        Returns:
            리로드 결과 이벤트
        """
        max_retries = self._hot_reload_config.max_retries
        retry_interval = self._hot_reload_config.retry_interval
        retry_count = 0

        while retry_count <= max_retries:
            event = self._perform_reload(file_path, change_type, retry_count)

            # 성공 또는 스킵이면 즉시 반환
            if event.reload_status in (ReloadStatus.SUCCESS, ReloadStatus.SKIPPED):
                return event

            # 검증 오류는 재시도하지 않음
            if event.reload_status == ReloadStatus.VALIDATION_ERROR:
                return event

            # 실패한 경우 재시도
            retry_count += 1
            if retry_count <= max_retries:
                self._log_warning(
                    f"리로드 실패, 재시도 중 ({retry_count}/{max_retries}): {file_path}"
                )
                self._statistics.record_reload(ReloadStatus.RETRYING, 0)
                time.sleep(retry_interval)
            else:
                self._log_error(f"리로드 최대 재시도 횟수 초과: {file_path}")

        return event

    def _perform_reload(
        self,
        file_path: str,
        change_type: ChangeType,
        retry_count: int = 0,
    ) -> ConfigChangeEvent:
        """
        실제 리로드 수행.

        Args:
            file_path: 파일 경로
            change_type: 변경 유형
            retry_count: 현재 재시도 횟수

        Returns:
            리로드 결과 이벤트
        """
        timer = Timer(f"reload:{file_path}")
        timer.start()

        event = ConfigChangeEvent(
            file_path=file_path,
            change_type=change_type,
            retry_count=retry_count,
        )

        watched_file = self._watched_files.get(file_path)

        try:
            path_obj = Path(file_path)

            # 파일 존재 확인
            if not path_obj.exists():
                event.reload_status = ReloadStatus.FAILED
                event.error_message = "파일이 존재하지 않습니다"
                return event

            # 해시 기반 변경 감지
            if watched_file:
                if not watched_file.update_hash():
                    # 내용 변경 없음
                    event.reload_status = ReloadStatus.SKIPPED
                    logger.debug(f"파일 내용 변경 없음: {file_path}")
                    return event

            # 이전 설정 저장
            event.old_config = self._config_loader.to_dict()

            # 설정 리로드
            self._config_loader.load(file_path, merge=False, required=True)
            event.new_config = self._config_loader.to_dict()

            # 변경된 키 감지
            event.changed_keys = self._find_changed_keys(
                event.old_config,
                event.new_config,
            )

            # 스키마 검증
            if self._validate_on_reload and self._schema_validator:
                validation_result = self._schema_validator.validate(
                    event.new_config,
                    AppConfig,
                )

                if not validation_result.is_valid:
                    event.reload_status = ReloadStatus.VALIDATION_ERROR
                    event.error_message = "; ".join(
                        e.message for e in validation_result.errors[:5]
                    )

                    # keep_previous_on_failure 설정에 따라 이전 설정 복원
                    if self._hot_reload_config.keep_previous_on_failure and event.old_config:
                        for key, value in self._flatten_dict(event.old_config).items():
                            self._config_loader.set(key, value)

                    self._log_warning(f"설정 검증 실패: {file_path}")
                    self._statistics.record_reload(
                        ReloadStatus.VALIDATION_ERROR,
                        timer.elapsed_ms,
                    )

                    if watched_file:
                        watched_file.mark_reloaded(success=False)

                    return event

            # 성공
            event.reload_status = ReloadStatus.SUCCESS
            self._config_snapshot = event.new_config

            if watched_file:
                watched_file.mark_reloaded(success=True)

            self._log_info(
                f"설정 리로드 성공: {file_path}, "
                f"변경된 키: {len(event.changed_keys)}개"
            )

        except Exception as e:
            event.reload_status = ReloadStatus.FAILED
            event.error_message = str(e)

            self._log_error(f"설정 리로드 실패: {file_path}, 오류: {e}")

            if watched_file:
                watched_file.mark_reloaded(success=False)

        finally:
            timer.stop()
            event.reload_duration_ms = timer.elapsed_ms
            self._statistics.record_reload(event.reload_status, event.reload_duration_ms)

            # 콜백 호출
            self._notify_callbacks(event)

        return event

    def _notify_callbacks(self, event: ConfigChangeEvent) -> None:
        """
        콜백 호출.

        각 콜백을 별도 스레드에서 실행하고 callback_timeout 내에 완료되지 않으면
        타임아웃으로 처리합니다. 느린 콜백이 리로드 워커 스레드를 차단하는 것을 방지합니다.
        """
        with self._callbacks_lock:
            callbacks = self._callbacks.copy()

        callback_timeout = self._hot_reload_config.callback_timeout

        for callback in callbacks:
            callback_name = getattr(callback, "__name__", repr(callback))
            try:
                # 콜백을 별도 스레드에서 실행하여 타임아웃 적용
                callback_thread = threading.Thread(
                    target=callback,
                    args=(event,),
                    name=f"CallbackExecutor-{callback_name}",
                    daemon=True,
                )
                callback_thread.start()
                callback_thread.join(timeout=callback_timeout)

                if callback_thread.is_alive():
                    self._log_warning(
                        f"콜백 실행 타임아웃 ({callback_timeout}s 초과): {callback_name}"
                    )
            except Exception as e:
                self._log_error(f"콜백 실행 오류: {callback_name}, {e}")

    def _find_changed_keys(
        self,
        old_config: dict[str, Any],
        new_config: dict[str, Any],
        prefix: str = "",
    ) -> list[str]:
        """
        변경된 키 찾기.

        Args:
            old_config: 이전 설정
            new_config: 새 설정
            prefix: 키 접두사 (재귀용)

        Returns:
            변경된 키 목록
        """
        changed_keys = []

        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_value = old_config.get(key)
            new_value = new_config.get(key)

            if old_value != new_value:
                if isinstance(old_value, dict) and isinstance(new_value, dict):
                    # 중첩 딕셔너리 재귀 비교
                    changed_keys.extend(
                        self._find_changed_keys(old_value, new_value, full_key)
                    )
                else:
                    changed_keys.append(full_key)

        return changed_keys

    def _flatten_dict(
        self,
        data: dict[str, Any],
        prefix: str = "",
    ) -> dict[str, Any]:
        """딕셔너리 평탄화."""
        result = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value

        return result

    def _calculate_file_hash(self, path: Path) -> str:
        """파일 해시 계산."""
        if not path.exists():
            return ""

        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

    # --------------------------------------------------------
    # 상태 조회 메서드
    # --------------------------------------------------------
    def get_status(self) -> dict[str, Any]:
        """
        현재 상태 정보 반환.

        Returns:
            상태 정보 딕셔너리
        """
        return {
            "state": self.state.name,
            "service_status": self.service_status.value,
            "is_running": self.is_running,
            "watched_files_count": len(self._watched_paths),
            "watched_files": self.watched_files,
            "callbacks_count": len(self._callbacks),
            "debounce_time": self._debounce_time,
            "validate_on_reload": self._validate_on_reload,
            "auto_apply": self._auto_apply,
            "hot_reload_config": self._hot_reload_config.to_dict(),
            "statistics": self._statistics.to_dict(),
        }

    def get_watched_file_info(self, file_path: str) -> dict[str, Any] | None:
        """
        감시 파일 정보 조회.

        Args:
            file_path: 파일 경로

        Returns:
            파일 정보 또는 None
        """
        path_str = str(Path(file_path).resolve())

        with self._paths_lock:
            watched_file = self._watched_files.get(path_str)
            if not watched_file:
                return None

            return {
                "path": str(watched_file.path),
                "last_hash": watched_file.last_hash,
                "last_modified": (
                    watched_file.last_modified.isoformat()
                    if watched_file.last_modified else None
                ),
                "last_reload": (
                    watched_file.last_reload.isoformat()
                    if watched_file.last_reload else None
                ),
                "reload_count": watched_file.reload_count,
                "error_count": watched_file.error_count,
                "consecutive_errors": watched_file.consecutive_errors,
                "is_valid": watched_file.is_valid,
            }

    # --------------------------------------------------------
    # 컨텍스트 매니저
    # --------------------------------------------------------
    def __enter__(self) -> "HotReloadManager":
        """컨텍스트 매니저 진입."""
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        """컨텍스트 매니저 종료."""
        self.stop()


# =============================================================================
# 헬퍼 함수
# =============================================================================
def create_hot_reload_manager(
    config_loader: ConfigLoader | None = None,
    schema_validator: SchemaValidator | None = None,
    debounce_time: float | None = None,
) -> HotReloadManager:
    """
    HotReloadManager 생성 헬퍼 함수.

    Args:
        config_loader: ConfigLoader 인스턴스 (None이면 싱글톤 사용)
        schema_validator: SchemaValidator 인스턴스
        debounce_time: 디바운스 시간 (초, None이면 config.yaml에서 로드)

    Returns:
        HotReloadManager 인스턴스

    Example:
        >>> manager = create_hot_reload_manager()
        >>> manager.watch("config/app.yaml")
        >>> manager.start()
    """
    loader = config_loader or ConfigLoader.get_instance()
    validator = schema_validator or SchemaValidator()

    return HotReloadManager(
        config_loader=loader,
        schema_validator=validator,
        debounce_time=debounce_time,
    )


def watch_config(
    file_path: str | Path,
    callback: ConfigChangeCallback,
    config_loader: ConfigLoader | None = None,
    start_immediately: bool = True,
) -> HotReloadManager:
    """
    설정 파일 감시 시작 헬퍼 함수.

    Args:
        file_path: 감시할 설정 파일 경로
        callback: 변경 시 호출될 콜백
        config_loader: ConfigLoader 인스턴스
        start_immediately: 즉시 시작 여부

    Returns:
        HotReloadManager 인스턴스

    Example:
        >>> def on_change(event):
        ...     print(f"Config changed: {event.changed_keys}")
        >>> manager = watch_config("config/app.yaml", on_change)
    """
    manager = create_hot_reload_manager(config_loader=config_loader)
    manager.watch(file_path)
    manager.register_callback(callback)

    if start_immediately:
        manager.start()

    return manager


# =============================================================================
# 모듈 내보내기
# =============================================================================
__all__ = [
    # Enum
    "ChangeType",
    "ReloadStatus",
    "WatcherState",
    "LogLevel",
    # 데이터 클래스
    "HotReloadConfig",
    "ConfigChangeEvent",
    "WatchedFile",
    "ReloadStatistics",
    # 타입 별칭
    "ConfigChangeCallback",
    # 메인 클래스
    "HotReloadManager",
    # 함수
    "create_hot_reload_manager",
    "watch_config",
    # 상수 (기본값, config.yaml로 오버라이드 가능)
    "DEFAULT_DEBOUNCE_TIME",
    "SUPPORTED_EXTENSIONS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_INTERVAL",
    "DEFAULT_IGNORE_PATTERNS",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
