# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation
파일: __init__.py
설명: 핵심 기반 모듈 초기화 - 설정, 모니터링, 레지스트리, 복원력, 보안

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

이 모듈은 다음 기능을 제공합니다:
    - config: 설정 로딩, 스키마 검증, 핫 리로드
    - monitoring: 에러 추적, 메트릭 수집, 성능 프로파일링, 헬스 체크
    - registry: DI 컨테이너, 모델/서비스 레지스트리, 파이프라인 코디네이터
    - resilience: 서킷 브레이커, 재시도 메커니즘
    - security: 시크릿 관리, 감사 로깅
"""

# =============================================================================
# config 서브모듈 임포트
# =============================================================================
from core_foundation.config import (
    # config_loader - Enum
    ConfigFormat,
    ConfigSource,
    # config_loader - 데이터 클래스
    ConfigEntry,
    ConfigMetadata,
    # config_loader - 클래스
    ConfigLoader,
    # config_loader - 함수
    load_config,
    get_config_value,
    # schema_validator - Enum
    ValidationStatus,
    # schema_validator - 데이터 클래스
    ValidationErrorDetail,
    ValidationResult,
    # schema_validator - 기본 모델
    BaseConfigModel,
    # schema_validator - Desktop 전용 스키마
    LocalDatabaseConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    # schema_validator - 공통 스키마
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    AppConfig,
    # schema_validator - 검증 클래스
    SchemaValidator,
    # schema_validator - 함수
    validate_config,
    get_default_config,
    # settings - Enum
    SettingsState,
    Environment,
    # settings - 데이터 클래스
    SettingsMetadata,
    # settings - 클래스
    Settings,
    # settings - 함수
    get_settings,
    initialize_settings,
    # hot_reload - Enum
    ChangeType,
    ReloadStatus,
    WatcherState,
    LogLevel,
    # hot_reload - 데이터 클래스
    HotReloadConfig,
    ConfigChangeEvent,
    WatchedFile,
    ReloadStatistics,
    # hot_reload - 타입 별칭
    ConfigChangeCallback,
    # hot_reload - 클래스
    HotReloadManager,
    # hot_reload - 함수
    create_hot_reload_manager,
    watch_config,
    # hot_reload - 상수
    DEFAULT_DEBOUNCE_TIME,
    SUPPORTED_EXTENSIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_IGNORE_PATTERNS,
)

# =============================================================================
# monitoring 서브모듈 임포트 (지연 로드 - 서브모듈 업데이트 진행 중)
# =============================================================================
try:
    from core_foundation.monitoring import *  # noqa: F403
except ImportError as _monitoring_err:
    import logging as _logging
    _logging.getLogger(__name__).debug(f"monitoring 서브모듈 임포트 지연: {_monitoring_err}")

# =============================================================================
# registry 서브모듈 임포트 (지연 로드 - 서브모듈 업데이트 진행 중)
# =============================================================================
try:
    from core_foundation.registry import *  # noqa: F403
except ImportError as _registry_err:
    import logging as _logging
    _logging.getLogger(__name__).debug(f"registry 서브모듈 임포트 지연: {_registry_err}")

# =============================================================================
# resilience 서브모듈 임포트 (지연 로드 - 서브모듈 업데이트 진행 중)
# =============================================================================
try:
    from core_foundation.resilience import *  # noqa: F403
except ImportError as _resilience_err:
    import logging as _logging
    _logging.getLogger(__name__).debug(f"resilience 서브모듈 임포트 지연: {_resilience_err}")

# =============================================================================
# security 서브모듈 임포트 (지연 로드 - 서브모듈 업데이트 진행 중)
# =============================================================================
try:
    from core_foundation.security import *  # noqa: F403
except ImportError as _security_err:
    import logging as _logging
    _logging.getLogger(__name__).debug(f"security 서브모듈 임포트 지연: {_security_err}")

__version__ = "1.0.0"
__author__ = "COURTVIEW AI Team"

__all__ = [
    # =========================================================================
    # config 서브모듈
    # =========================================================================
    # config_loader
    "ConfigFormat",
    "ConfigSource",
    "ConfigEntry",
    "ConfigMetadata",
    "ConfigLoader",
    "load_config",
    "get_config_value",
    # schema_validator
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
    # settings
    "SettingsState",
    "Environment",
    "SettingsMetadata",
    "Settings",
    "get_settings",
    "initialize_settings",
    # hot_reload
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
    # =========================================================================
    # monitoring, registry, resilience, security 서브모듈
    # → 각 서브모듈의 __all__에 정의된 항목이 동적으로 추가됨
    # =========================================================================
]