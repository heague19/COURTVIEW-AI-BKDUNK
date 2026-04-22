# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: __init__.py
설명: 모니터링 서브모듈 패키지 Export
      - logger: 구조화 로깅 엔진
      - error_tracker: 에러 추적/집계 엔진
      - metrics: 시스템 메트릭 수집 엔진
      - profiler: CPU/메모리 프로파일링 엔진
      - health_checker: 시스템 헬스 체크 엔진

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations


# =============================================================================
# logger.py — 구조화 로깅
# =============================================================================
from core_foundation.monitoring.logger import (
    ComponentLogger,
    LogLevel,
    LogManager,
    StructuredFormatter,
    get_logger,
)

# =============================================================================
# error_tracker.py — 에러 추적
# =============================================================================
from core_foundation.monitoring.error_tracker import (
    MAX_CATEGORY_KEYS,
    MAX_ERROR_HISTORY,
    PATTERN_THRESHOLD,
    PATTERN_WINDOW,
    RATE_WINDOW_1HOUR,
    RATE_WINDOW_1MIN,
    ErrorEvent,
    ErrorSeverity,
    ErrorSummary,
    ErrorTracker,
)

# =============================================================================
# metrics.py — 메트릭 수집
# =============================================================================
from core_foundation.monitoring.metrics import (
    DEFAULT_HISTOGRAM_BUCKETS,
    DEFAULT_HISTORY_SIZE,
    MAX_METRIC_COUNT,
    Metric,
    MetricPoint,
    MetricSnapshot,
    MetricType,
    MetricsCollector,
)

# =============================================================================
# profiler.py — 프로파일링
# =============================================================================
from core_foundation.monitoring.profiler import (
    BYTES_TO_MB,
    DEFAULT_PROFILE_HISTORY,
    MAX_PROFILE_COUNT,
    ProfileEntry,
    ProfileSummary,
    ProfileTracker,
    Profiler,
)

# =============================================================================
# health_checker.py — 헬스 체크
# =============================================================================
from core_foundation.monitoring.health_checker import (
    CHECK_TIMEOUT,
    DEFAULT_CHECK_INTERVAL,
    MAX_CHECK_INTERVAL,
    MAX_COMPONENTS,
    MAX_STATUS_HISTORY,
    MIN_CHECK_INTERVAL,
    ComponentHealth,
    HealthCheckFn,
    HealthChecker,
    HealthReport,
    StatusChangeCallback,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- logger ---
    "LogLevel",
    "StructuredFormatter",
    "ComponentLogger",
    "LogManager",
    "get_logger",
    # --- error_tracker ---
    "ErrorSeverity",
    "ErrorEvent",
    "ErrorSummary",
    "ErrorTracker",
    "MAX_ERROR_HISTORY",
    "RATE_WINDOW_1MIN",
    "RATE_WINDOW_1HOUR",
    "PATTERN_THRESHOLD",
    "PATTERN_WINDOW",
    "MAX_CATEGORY_KEYS",
    # --- metrics ---
    "MetricType",
    "MetricPoint",
    "MetricSnapshot",
    "Metric",
    "MetricsCollector",
    "DEFAULT_HISTORY_SIZE",
    "MAX_METRIC_COUNT",
    "DEFAULT_HISTOGRAM_BUCKETS",
    # --- profiler ---
    "ProfileEntry",
    "ProfileSummary",
    "ProfileTracker",
    "Profiler",
    "DEFAULT_PROFILE_HISTORY",
    "MAX_PROFILE_COUNT",
    "BYTES_TO_MB",
    # --- health_checker ---
    "ComponentHealth",
    "HealthReport",
    "HealthCheckFn",
    "StatusChangeCallback",
    "HealthChecker",
    "DEFAULT_CHECK_INTERVAL",
    "MIN_CHECK_INTERVAL",
    "MAX_CHECK_INTERVAL",
    "MAX_COMPONENTS",
    "CHECK_TIMEOUT",
    "MAX_STATUS_HISTORY",
]

__version__ = "1.0.0"
