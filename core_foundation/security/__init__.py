# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: __init__.py
설명: 보안 모듈 초기화 - 시크릿 관리, 감사 로깅

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

모듈 구성:
    - secret_manager: 시크릿 관리 (AWS Secrets Manager, 환경변수, Vault)
    - audit_logger: 감사 로그 기록 (보안 이벤트, 접근 기록, 무결성 보장)
"""

__version__: str = "1.0.0"

# ============================================================
# secret_manager 임포트
# ============================================================
from core_foundation.security.secret_manager import (
    # Enum
    SecretProvider,
    SecretStatus,
    CacheStatus,
    # 예외
    SecretException,
    SecretNotFoundException,
    SecretAccessDeniedException,
    SecretValidationException,
    SecretProviderException,
    # 데이터 클래스
    SecretInfo,
    SecretVersion,
    SecretValidationRule,
    RotationSchedule,
    # 메인 클래스
    SecretManager,
    # 제공자 클래스
    BaseSecretProvider,
    AWSSecretsProvider,
    VaultProvider,
    EnvProvider,
    FileProvider,
    EncryptedFileProvider,
    # 엔터프라이즈 기능 클래스
    SecretEncryption,
    SecretRotator,
    VaultTokenManager,
    # 함수
    get_secret,
    get_secret_manager,
    set_secret_manager,
)

# ============================================================
# audit_logger 임포트
# ============================================================
from core_foundation.security.audit_logger import (
    # Enum
    AuditEventType,
    AuditSeverity,
    # 데이터 클래스
    AuditEvent,
    AuditLogEntry,
    # 저장소 클래스
    BaseAuditStorage,
    FileAuditStorage,
    MemoryAuditStorage,
    CloudWatchAuditStorage,
    ElasticsearchAuditStorage,
    # 알림 핸들러 클래스
    BaseAlertHandler,
    LogAlertHandler,
    SlackAlertHandler,
    EmailAlertHandler,
    WebhookAlertHandler,
    # 추적기 클래스
    LoginFailureTracker,
    # 메인 클래스
    AuditLogger,
    # 함수
    get_audit_logger,
    set_audit_logger,
    log_audit_event,
    # 상수
    EVENT_DEFAULT_SEVERITY,
)

# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # secret_manager - Enum
    "SecretProvider",
    "SecretStatus",
    "CacheStatus",
    # secret_manager - 예외
    "SecretException",
    "SecretNotFoundException",
    "SecretAccessDeniedException",
    "SecretValidationException",
    "SecretProviderException",
    # secret_manager - 데이터 클래스
    "SecretInfo",
    "SecretVersion",
    "SecretValidationRule",
    "RotationSchedule",
    # secret_manager - 메인 클래스
    "SecretManager",
    # secret_manager - 제공자 클래스
    "BaseSecretProvider",
    "AWSSecretsProvider",
    "VaultProvider",
    "EnvProvider",
    "FileProvider",
    "EncryptedFileProvider",
    # secret_manager - 엔터프라이즈 기능 클래스
    "SecretEncryption",
    "SecretRotator",
    "VaultTokenManager",
    # secret_manager - 함수
    "get_secret",
    "get_secret_manager",
    "set_secret_manager",
    # audit_logger - Enum
    "AuditEventType",
    "AuditSeverity",
    # audit_logger - 데이터 클래스
    "AuditEvent",
    "AuditLogEntry",
    # audit_logger - 저장소 클래스
    "BaseAuditStorage",
    "FileAuditStorage",
    "MemoryAuditStorage",
    "CloudWatchAuditStorage",
    "ElasticsearchAuditStorage",
    # audit_logger - 알림 핸들러 클래스
    "BaseAlertHandler",
    "LogAlertHandler",
    "SlackAlertHandler",
    "EmailAlertHandler",
    "WebhookAlertHandler",
    # audit_logger - 추적기 클래스
    "LoginFailureTracker",
    # audit_logger - 메인 클래스
    "AuditLogger",
    # audit_logger - 함수
    "get_audit_logger",
    "set_audit_logger",
    "log_audit_event",
    # audit_logger - 상수
    "EVENT_DEFAULT_SEVERITY",
]
