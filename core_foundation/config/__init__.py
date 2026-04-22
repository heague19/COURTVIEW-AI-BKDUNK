# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: __init__.py
설명: 설정 관리 서브모듈 — YAML 로딩, 검증, 전역 설정, 변경 감시
      - loader: YAML/ENV 3단계 병합 로더
      - validator: 타입/범위/커스텀 검증 엔진
      - settings: 전역 설정 Singleton
      - watcher: 파일 변경 폴링 감시

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 서브모듈 Export
# =============================================================================

# --- loader ---
from core_foundation.config.loader import (
    ConfigLoadResult,
    ConfigLoader,
    Environment,
    OSPlatform,
    DEFAULT_CONFIG_DIR,
    ENV_PREFIX,
    ENV_SEPARATOR,
    MAX_MERGE_DEPTH,
    MAX_YAML_FILE_SIZE_BYTES,
    YAML_EXTENSIONS,
)

# --- validator ---
from core_foundation.config.validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
    MAX_CUSTOM_RULES,
)

# --- settings ---
from core_foundation.config.settings import (
    AppSettings,
    ConfigSnapshot,
    DEFAULT_CONFIG_FILE,
    MAX_SNAPSHOT_COUNT,
)

# --- watcher ---
from core_foundation.config.watcher import (
    ChangeCallback,
    ConfigWatcher,
    FileChangeEvent,
    FileChangeType,
    DEFAULT_POLL_INTERVAL,
    MAX_CALLBACKS,
    MAX_CHANGE_HISTORY,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # === loader ===
    "ConfigLoadResult",
    "ConfigLoader",
    "Environment",
    "OSPlatform",
    "DEFAULT_CONFIG_DIR",
    "ENV_PREFIX",
    "ENV_SEPARATOR",
    "MAX_MERGE_DEPTH",
    "MAX_YAML_FILE_SIZE_BYTES",
    "YAML_EXTENSIONS",
    # === validator ===
    "ConfigValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationRule",
    "ValidationSeverity",
    "MAX_CUSTOM_RULES",
    # === settings ===
    "AppSettings",
    "ConfigSnapshot",
    "DEFAULT_CONFIG_FILE",
    "MAX_SNAPSHOT_COUNT",
    # === watcher ===
    "ChangeCallback",
    "ConfigWatcher",
    "FileChangeEvent",
    "FileChangeType",
    "DEFAULT_POLL_INTERVAL",
    "MAX_CALLBACKS",
    "MAX_CHANGE_HISTORY",
    "MAX_POLL_INTERVAL",
    "MIN_POLL_INTERVAL",
]

__version__ = "1.0.0"
