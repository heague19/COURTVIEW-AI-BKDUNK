# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation
파일: __init__.py
설명: 핵심 기반 서비스 (Layer 0) 루트 패키지.
      5개 서브모듈의 핵심 클래스, Enum, 데이터클래스를 re-export.
      상수 및 콜백 타입은 각 서브모듈에서 직접 임포트.

      서브모듈 구성:
      - config/    : YAML/ENV 설정 로딩, 검증, 전역 설정, 변경 감시
      - monitoring/ : 로깅, 에러 추적, 메트릭, 프로파일링, 헬스 체크
      - registry/  : 서비스/모델/DI/파이프라인/규칙 레지스트리
      - resilience/ : 서킷 브레이커, 재시도 정책
      - security/  : 라이선스 검증, 시크릿 관리, 감사 로깅

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations


# =============================================================================
# config/ — 설정 관리
# =============================================================================
from core_foundation.config import (
    # Enum
    Environment,
    FileChangeType,
    OSPlatform,
    ValidationSeverity,
    # 데이터 클래스
    ConfigLoadResult,
    ConfigSnapshot,
    FileChangeEvent,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    # 핵심 클래스
    AppSettings,
    ConfigLoader,
    ConfigValidator,
    ConfigWatcher,
)

# =============================================================================
# monitoring/ — 모니터링
# =============================================================================
from core_foundation.monitoring import (
    # Enum
    ComponentHealth,
    ErrorSeverity,
    LogLevel,
    MetricType,
    # 데이터 클래스
    ErrorEvent,
    ErrorSummary,
    HealthReport,
    Metric,
    MetricPoint,
    MetricSnapshot,
    ProfileEntry,
    ProfileSummary,
    # 핵심 클래스
    ComponentLogger,
    ErrorTracker,
    HealthChecker,
    LogManager,
    MetricsCollector,
    ProfileTracker,
    Profiler,
    # 유틸리티
    get_logger,
)

# =============================================================================
# registry/ — 레지스트리
# =============================================================================
from core_foundation.registry import (
    # Enum
    ModelBackend,
    ModelStatus,
    Scope,
    ServiceLifecycle,
    StageStatus,
    # 데이터 클래스
    Binding,
    ModelInfo,
    PipelineResult,
    RuleOverride,
    RuleSnapshot,
    ServiceDescriptor,
    StageDefinition,
    StageResult,
    # 핵심 클래스
    DependencyInjector,
    ModelRegistry,
    PipelineCoordinator,
    RuleSetManager,
    ServiceRegistry,
)

# =============================================================================
# resilience/ — 장애 복원력
# =============================================================================
from core_foundation.resilience import (
    # Enum
    BackoffStrategy,
    CallResult,
    CircuitState,
    RetryOutcome,
    # 데이터 클래스
    AttemptRecord,
    BreakerSnapshot,
    RetryResult,
    StateTransition,
    # 핵심 클래스
    BreakerRegistry,
    CircuitBreaker,
    RetryPolicy,
    RetryPolicyRegistry,
)

# =============================================================================
# security/ — 보안
# =============================================================================
from core_foundation.security import (
    # Enum
    AuditCategory,
    AuditSeverity,
    LicenseStatus,
    SecretSource,
    # 데이터 클래스
    AuditEvent,
    LicenseInfo,
    SecretEntry,
    # 핵심 클래스
    AuditLogger,
    LicenseValidator,
    SecretManager,
    # 유틸리티
    compute_event_hash,
    generate_hardware_id,
    generate_license_signature,
    mask_secret,
    verify_license_signature,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # =========================================================================
    # config/ (16개)
    # =========================================================================
    # Enum
    "Environment",
    "OSPlatform",
    "ValidationSeverity",
    "FileChangeType",
    # 데이터 클래스
    "ConfigLoadResult",
    "ValidationIssue",
    "ValidationResult",
    "ValidationRule",
    "ConfigSnapshot",
    "FileChangeEvent",
    # 핵심 클래스
    "ConfigLoader",
    "ConfigValidator",
    "AppSettings",
    "ConfigWatcher",
    # =========================================================================
    # monitoring/ (22개)
    # =========================================================================
    # Enum
    "LogLevel",
    "ErrorSeverity",
    "MetricType",
    "ComponentHealth",
    # 데이터 클래스
    "ErrorEvent",
    "ErrorSummary",
    "MetricPoint",
    "MetricSnapshot",
    "Metric",
    "ProfileEntry",
    "ProfileSummary",
    "HealthReport",
    # 핵심 클래스
    "ComponentLogger",
    "LogManager",
    "ErrorTracker",
    "MetricsCollector",
    "ProfileTracker",
    "Profiler",
    "HealthChecker",
    # 유틸리티
    "get_logger",
    # =========================================================================
    # registry/ (19개)
    # =========================================================================
    # Enum
    "ServiceLifecycle",
    "ModelStatus",
    "ModelBackend",
    "Scope",
    "StageStatus",
    # 데이터 클래스
    "ServiceDescriptor",
    "ModelInfo",
    "Binding",
    "StageResult",
    "StageDefinition",
    "PipelineResult",
    "RuleOverride",
    "RuleSnapshot",
    # 핵심 클래스
    "ServiceRegistry",
    "ModelRegistry",
    "DependencyInjector",
    "PipelineCoordinator",
    "RuleSetManager",
    # =========================================================================
    # resilience/ (14개)
    # =========================================================================
    # Enum
    "CircuitState",
    "CallResult",
    "BackoffStrategy",
    "RetryOutcome",
    # 데이터 클래스
    "StateTransition",
    "BreakerSnapshot",
    "AttemptRecord",
    "RetryResult",
    # 핵심 클래스
    "CircuitBreaker",
    "BreakerRegistry",
    "RetryPolicy",
    "RetryPolicyRegistry",
    # =========================================================================
    # security/ (15개)
    # =========================================================================
    # Enum
    "LicenseStatus",
    "SecretSource",
    "AuditCategory",
    "AuditSeverity",
    # 데이터 클래스
    "LicenseInfo",
    "SecretEntry",
    "AuditEvent",
    # 핵심 클래스
    "LicenseValidator",
    "SecretManager",
    "AuditLogger",
    # 유틸리티
    "generate_hardware_id",
    "generate_license_signature",
    "verify_license_signature",
    "mask_secret",
    "compute_event_hash",
]

__version__ = "1.0.0"
