# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: core_foundation/config
파일: __init__.py
설명: 설정 관리 모듈 초기화 - 로딩, 검증, 전역 설정, 파일 감시

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.1.0

이 모듈은 다음 기능을 제공합니다:
    - loader: YAML/JSON 설정 로드, 환경변수 오버라이드, 설정 병합
    - validator: Pydantic 기반 Desktop 전용 스키마 검증
    - settings: 전역 설정 Singleton (타입 안전한 접근 레이어)
    - watcher: 설정 파일 변경 감지 및 자동 리로드
"""

from core_foundation.config.loader import (
    # Enum
    ConfigFormat,
    ConfigSource,
    # 데이터 클래스
    ConfigEntry,
    ConfigMetadata,
    # 클래스
    ConfigLoader,
    # 함수
    load_config,
    get_config_value,
)

from core_foundation.config.validator import (
    # Enum
    ValidationStatus,
    # 데이터 클래스
    ValidationErrorDetail,
    ValidationResult,
    # 기본 모델
    BaseConfigModel,
    # Desktop 전용 스키마
    LocalDatabaseConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    # 공통 스키마
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    # 통합 설정
    AppConfig,
    # 검증 클래스
    SchemaValidator,
    # 함수
    validate_config,
    get_default_config,
)

from core_foundation.config.settings import (
    # Enum
    SettingsState,
    Environment,
    # 데이터 클래스
    SettingsMetadata,
    # 클래스
    Settings,
    # 함수
    get_settings,
    initialize_settings,
)

from core_foundation.config.watcher import (
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
    # 클래스
    HotReloadManager,
    # 함수
    create_hot_reload_manager,
    watch_config,
    # 상수
    DEFAULT_DEBOUNCE_TIME,
    SUPPORTED_EXTENSIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_IGNORE_PATTERNS,
)

__all__ = [
    # ============================================================
    # loader 내보내기
    # ============================================================
    "ConfigFormat",
    "ConfigSource",
    "ConfigEntry",
    "ConfigMetadata",
    "ConfigLoader",
    "load_config",
    "get_config_value",
    # ============================================================
    # validator 내보내기
    # ============================================================
    "ValidationStatus",
    "ValidationErrorDetail",
    "ValidationResult",
    "BaseConfigModel",
    # Desktop 전용 스키마
    "LocalDatabaseConfig",
    "GPUConfig",
    "CameraConfig",
    "LocalStorageConfig",
    # 공통 스키마
    "ModelConfig",
    "AnalysisConfig",
    "LoggingConfig",
    "AppConfig",
    "SchemaValidator",
    "validate_config",
    "get_default_config",
    # ============================================================
    # settings 내보내기
    # ============================================================
    "SettingsState",
    "Environment",
    "SettingsMetadata",
    "Settings",
    "get_settings",
    "initialize_settings",
    # ============================================================
    # watcher 내보내기
    # ============================================================
    "ChangeType",
    "ReloadStatus",
    "WatcherState",
    "LogLevel",
    "HotReloadConfig",
    "ConfigChangeEvent",
    "WatchedFile",
    "ReloadStatistics",
    "ConfigChangeCallback",
    "HotReloadManager",
    "create_hot_reload_manager",
    "watch_config",
    "DEFAULT_DEBOUNCE_TIME",
    "SUPPORTED_EXTENSIONS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_INTERVAL",
    "DEFAULT_IGNORE_PATTERNS",
]

__version__: str = "1.0.0"
