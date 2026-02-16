# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: __init__.py
설명: 모니터링 모듈 초기화 - 로깅, 에러 추적, 메트릭 수집, 성능 프로파일링, 헬스 체크

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

Desktop Edition 모듈 구성:
    - logger: Loguru 기반 중앙 로깅 시스템 (파일 로테이션, 민감정보 마스킹)
    - error_tracker: 에러 추적, 집계, 통계 분석
    - metrics: Prometheus 스타일 메트릭 수집 (GPU, Camera, System)
    - profiler: 성능 프로파일링
    - health_checker: 시스템 헬스 체크 (GPU, 카메라, 디스크)

Desktop Edition 변경사항:
    - alert_service 제거 (서버 전용: Slack, Email, PagerDuty, Webhook)
    - error_tracker에서 알림 관련 코드 제거 (AlertChannel, AlertConfig, AlertRule)
    - logger 신규 추가 (Loguru 기반, stdlib 인터셉트, 분석/성능 전용 싱크)
    - health_checker에 GPU, Camera 헬스 체크 추가
    - metrics에 GPU, Camera, System 메트릭 추가
"""

# ============================================================
# logger 임포트
# ============================================================
from core_foundation.monitoring.logger import (
    # 상수
    LOGURU_AVAILABLE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    DEFAULT_FILE_FORMAT,
    DEFAULT_ROTATION_SIZE,
    DEFAULT_RETENTION,
    DEFAULT_SENSITIVE_PATTERNS,
    MASK_VALUE,
    # Enum
    LogLevel,
    # 데이터 클래스
    SinkConfig,
    LoggingConfig,
    # 핸들러/필터
    InterceptHandler,
    SensitiveDataFilter,
    # 메인 클래스
    LogManager,
    # 헬퍼 함수
    setup_logging,
    get_logger,
    log_analysis,
    log_performance,
    # 유틸리티 (테스트용)
    _get_manager,
    _reset_manager,
)

# ============================================================
# error_tracker 임포트
# ============================================================
from core_foundation.monitoring.error_tracker import (
    # Enum
    ErrorSeverity,
    ErrorCategory,       # shared에서 re-export (고수준 분류)
    TrackingCategory,    # 에러 추적용 세분화 카테고리
    # 상수
    MAX_ERROR_RECORDS,
    MAX_ERROR_HASHES,
    AGGREGATION_WINDOW_SIZE,
    # 데이터 클래스
    ErrorRecord,
    ErrorSummary,
    ErrorTrend,
    ErrorContext,
    # 메인 클래스
    ErrorTracker,
    # 함수
    track_error,
    get_error_summary,
)

# ============================================================
# metrics 임포트
# ============================================================
from core_foundation.monitoring.metrics import (
    # Enum
    MetricType,
    MetricUnit,
    # 상수
    DEFAULT_HISTOGRAM_BUCKETS,
    FPS_HISTOGRAM_BUCKETS,
    ACCURACY_HISTOGRAM_BUCKETS,
    DEFAULT_QUANTILES,
    METRIC_PREFIX,
    MAX_METRICS,
    SUMMARY_WINDOW_SECONDS,
    SUMMARY_MAX_OBSERVATIONS,
    # Desktop 전용 상수
    MODEL_INFERENCE_BUCKETS,
    FRAME_PROCESSING_BUCKETS,
    GPU_TEMPERATURE_BUCKETS,
    # 데이터 클래스
    MetricValue,
    MetricLabels,
    MetricSnapshot,
    # 메트릭 클래스
    Counter,
    Gauge,
    Histogram,
    Summary,
    # 메인 클래스
    MetricsCollector,
    # 데코레이터
    measure_latency,
    count_calls,
)

# ============================================================
# profiler 임포트
# ============================================================
from core_foundation.monitoring.profiler import (
    # Enum
    ProfileType,
    ResourceType,
    # 상수
    DEFAULT_MAX_PROFILES,
    DEFAULT_CLEANUP_INTERVAL,
    DEFAULT_TOP_FUNCTIONS,
    DEFAULT_MEMORY_TRACE_LIMIT,
    FPS_WARNING_THRESHOLD,
    FRAME_TIME_WARNING_MS,
    MEMORY_WARNING_MB,
    # 데이터 클래스
    ProfileResult,
    MemorySnapshot,
    CPUSnapshot,
    GPUSnapshot,
    FunctionProfile,
    # 메인 클래스
    PerformanceProfiler,
    # 데코레이터
    profile_function,
    profile_memory,
    # 컨텍스트 매니저
    profiling_context,
    # 유틸리티 함수 (테스트용)
    _get_profiler,
    _reset_profiler,
)

# ============================================================
# health_checker 임포트
# ============================================================
from core_foundation.monitoring.health_checker import (
    # Enum
    HealthStatus,
    DependencyType,
    # 상수
    DEFAULT_CHECK_TIMEOUT,
    MAX_HEALTH_HISTORY,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_CPU_WARNING_THRESHOLD,
    DEFAULT_CPU_CRITICAL_THRESHOLD,
    DEFAULT_MEMORY_WARNING_THRESHOLD,
    DEFAULT_MEMORY_CRITICAL_THRESHOLD,
    DEFAULT_DISK_WARNING_THRESHOLD,
    DEFAULT_DISK_CRITICAL_THRESHOLD,
    # Desktop 전용 상수
    DEFAULT_GPU_TEMP_WARNING,
    DEFAULT_GPU_TEMP_CRITICAL,
    DEFAULT_GPU_MEMORY_WARNING,
    DEFAULT_GPU_MEMORY_CRITICAL,
    DEFAULT_DISK_PATH,
    # 데이터 클래스
    HealthCheckResult,
    DependencyHealth,
    SystemHealth,
    HealthCheckConfig,
    # 메인 클래스
    HealthChecker,
    # 함수
    create_health_check,
    aggregate_health_status,
    # 빌트인 체크 함수
    check_cpu_health,
    check_memory_health,
    check_disk_health,
    check_tcp_port,
    # Desktop 전용 체크 함수
    check_gpu_health,
    check_camera_health,
    # 유틸리티 (테스트용)
    _get_health_checker,
    _reset_health_checker,
)

# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # === logger ===
    # 상수
    "LOGURU_AVAILABLE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_FILE_FORMAT",
    "DEFAULT_ROTATION_SIZE",
    "DEFAULT_RETENTION",
    "DEFAULT_SENSITIVE_PATTERNS",
    "MASK_VALUE",
    # Enum
    "LogLevel",
    # 데이터 클래스
    "SinkConfig",
    "LoggingConfig",
    # 핸들러/필터
    "InterceptHandler",
    "SensitiveDataFilter",
    # 메인 클래스
    "LogManager",
    # 헬퍼 함수
    "setup_logging",
    "get_logger",
    "log_analysis",
    "log_performance",
    # 유틸리티 (테스트용)
    "_get_manager",
    "_reset_manager",

    # === error_tracker ===
    # Enum
    "ErrorSeverity",
    "ErrorCategory",       # shared에서 re-export (고수준 분류)
    "TrackingCategory",    # 에러 추적용 세분화 카테고리
    # 상수
    "MAX_ERROR_RECORDS",
    "MAX_ERROR_HASHES",
    "AGGREGATION_WINDOW_SIZE",
    # 데이터 클래스
    "ErrorRecord",
    "ErrorSummary",
    "ErrorTrend",
    "ErrorContext",
    # 메인 클래스
    "ErrorTracker",
    # 함수
    "track_error",
    "get_error_summary",

    # === metrics ===
    # Enum
    "MetricType",
    "MetricUnit",
    # 상수
    "DEFAULT_HISTOGRAM_BUCKETS",
    "FPS_HISTOGRAM_BUCKETS",
    "ACCURACY_HISTOGRAM_BUCKETS",
    "DEFAULT_QUANTILES",
    "METRIC_PREFIX",
    "MAX_METRICS",
    "SUMMARY_WINDOW_SECONDS",
    "SUMMARY_MAX_OBSERVATIONS",
    # Desktop 전용 상수
    "MODEL_INFERENCE_BUCKETS",
    "FRAME_PROCESSING_BUCKETS",
    "GPU_TEMPERATURE_BUCKETS",
    # 데이터 클래스
    "MetricValue",
    "MetricLabels",
    "MetricSnapshot",
    # 메트릭 클래스
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    # 메인 클래스
    "MetricsCollector",
    # 데코레이터
    "measure_latency",
    "count_calls",

    # === profiler ===
    # Enum
    "ProfileType",
    "ResourceType",
    # 상수
    "DEFAULT_MAX_PROFILES",
    "DEFAULT_CLEANUP_INTERVAL",
    "DEFAULT_TOP_FUNCTIONS",
    "DEFAULT_MEMORY_TRACE_LIMIT",
    "FPS_WARNING_THRESHOLD",
    "FRAME_TIME_WARNING_MS",
    "MEMORY_WARNING_MB",
    # 데이터 클래스
    "ProfileResult",
    "MemorySnapshot",
    "CPUSnapshot",
    "GPUSnapshot",
    "FunctionProfile",
    # 메인 클래스
    "PerformanceProfiler",
    # 데코레이터
    "profile_function",
    "profile_memory",
    # 컨텍스트 매니저
    "profiling_context",
    # 유틸리티 함수 (테스트용)
    "_get_profiler",
    "_reset_profiler",

    # === health_checker ===
    # Enum
    "HealthStatus",
    "DependencyType",
    # 상수
    "DEFAULT_CHECK_TIMEOUT",
    "MAX_HEALTH_HISTORY",
    "DEFAULT_CHECK_INTERVAL",
    "DEFAULT_CPU_WARNING_THRESHOLD",
    "DEFAULT_CPU_CRITICAL_THRESHOLD",
    "DEFAULT_MEMORY_WARNING_THRESHOLD",
    "DEFAULT_MEMORY_CRITICAL_THRESHOLD",
    "DEFAULT_DISK_WARNING_THRESHOLD",
    "DEFAULT_DISK_CRITICAL_THRESHOLD",
    # Desktop 전용 상수
    "DEFAULT_GPU_TEMP_WARNING",
    "DEFAULT_GPU_TEMP_CRITICAL",
    "DEFAULT_GPU_MEMORY_WARNING",
    "DEFAULT_GPU_MEMORY_CRITICAL",
    "DEFAULT_DISK_PATH",
    # 데이터 클래스
    "HealthCheckResult",
    "DependencyHealth",
    "SystemHealth",
    "HealthCheckConfig",
    # 메인 클래스
    "HealthChecker",
    # 함수
    "create_health_check",
    "aggregate_health_status",
    # 빌트인 체크 함수
    "check_cpu_health",
    "check_memory_health",
    "check_disk_health",
    "check_tcp_port",
    # Desktop 전용 체크 함수
    "check_gpu_health",
    "check_camera_health",
    # 유틸리티 (테스트용)
    "_get_health_checker",
    "_reset_health_checker",
]

__version__: str = "1.0.0"
