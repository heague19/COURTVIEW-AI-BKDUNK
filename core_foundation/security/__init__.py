# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
설명: 보안 서브모듈 (라이선스 검증, 시크릿 관리, 감사 로깅)
      - license_validator: 하드웨어 ID 기반 라이선스 검증 (HMAC-SHA256)
      - secret_manager: 환경변수/파일/런타임 시크릿 관리
      - audit_logger: 감사 이벤트 기록 (SHA-256 체인 해싱)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# license_validator
# =============================================================================
from core_foundation.security.license_validator import (
    DEFAULT_TRIAL_DAYS,
    HW_HASH_ALGORITHM,
    LICENSE_CACHE_TTL_SEC,
    MIN_LICENSE_KEY_LENGTH,
    LicenseInfo,
    LicenseStatus,
    LicenseValidator,
    generate_hardware_id,
    generate_license_signature,
    verify_license_signature,
)

# =============================================================================
# secret_manager
# =============================================================================
from core_foundation.security.secret_manager import (
    MASK_CHAR,
    MASK_VISIBLE_CHARS,
    MAX_SECRETS,
    NO_EXPIRY,
    SecretEntry,
    SecretManager,
    SecretSource,
    mask_secret,
)

# =============================================================================
# audit_logger
# =============================================================================
from core_foundation.security.audit_logger import (
    GENESIS_HASH,
    HASH_ALGORITHM,
    MAX_AUDIT_ENTRIES,
    MAX_CALLBACKS,
    AuditCategory,
    AuditEvent,
    AuditEventCallback,
    AuditLogger,
    AuditSeverity,
    compute_event_hash,
)

# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- license_validator ---
    # Enum
    "LicenseStatus",
    # 데이터 클래스
    "LicenseInfo",
    # 유틸리티
    "generate_hardware_id",
    "generate_license_signature",
    "verify_license_signature",
    # 핵심 클래스
    "LicenseValidator",
    # 상수
    "MIN_LICENSE_KEY_LENGTH",
    "HW_HASH_ALGORITHM",
    "LICENSE_CACHE_TTL_SEC",
    "DEFAULT_TRIAL_DAYS",
    # --- secret_manager ---
    # Enum
    "SecretSource",
    # 데이터 클래스
    "SecretEntry",
    # 유틸리티
    "mask_secret",
    # 핵심 클래스
    "SecretManager",
    # 상수
    "MAX_SECRETS",
    "MASK_CHAR",
    "MASK_VISIBLE_CHARS",
    "NO_EXPIRY",
    # --- audit_logger ---
    # Enum
    "AuditCategory",
    "AuditSeverity",
    # 데이터 클래스
    "AuditEvent",
    # 타입
    "AuditEventCallback",
    # 유틸리티
    "compute_event_hash",
    # 핵심 클래스
    "AuditLogger",
    # 상수
    "MAX_AUDIT_ENTRIES",
    "MAX_CALLBACKS",
    "GENESIS_HASH",
    "HASH_ALGORITHM",
]

__version__ = "1.0.0"
