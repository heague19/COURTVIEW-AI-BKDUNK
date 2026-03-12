# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: __init__.py
설명: 레지스트리 모듈 초기화 - 모델 등록, 서비스 등록, DI 컨테이너, 파이프라인 조율, 규칙 세트 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

모듈 구성:
    - model_registry: AI 모델 등록, 버전 관리, 로드/언로드
    - service_registry: 서비스 등록, 검색, 라이프사이클 관리
    - dependency_injector: DI 컨테이너, 의존성 주입 관리
    - pipeline_coordinator: 파이프라인 실행 조율, 단계 관리
    - rule_set_manager: 7개 리그 규칙 세트 로딩/캐싱 (v3.0.0)
"""

# ============================================================
# model_registry 임포트
# ============================================================
from core_foundation.registry.model_registry import (
    # Enum
    ModelType,
    ModelStatus,
    ModelFormat,
    # 상수
    DEFAULT_MAX_MODELS,
    DEFAULT_MODEL_TIMEOUT,
    DEFAULT_WARMUP_ITERATIONS,
    MODEL_CACHE_SIZE_MB,
    # 데이터 클래스
    ModelInfo,
    ModelVersion,
    ModelMetrics,
    ModelConfig,
    LoadedModel,
    # 프로토콜 인터페이스
    IModel,
    IModelLoader,
    # 메인 클래스
    ModelRegistry,
    # 함수
    get_model,
    register_model,
    # 유틸리티 (테스트용)
    _get_registry as _get_model_registry,
    _reset_registry as _reset_model_registry,
)

# ============================================================
# service_registry 임포트
# ============================================================
from core_foundation.registry.service_registry import (
    # Enum
    ServiceType,
    ServiceLifecycle,
    DependencyType,
    # 예외 클래스
    ServiceRegistryException,
    ServiceAlreadyExistsError,
    ServiceCapacityExceededError,
    # 상수
    DEFAULT_MAX_SERVICES,
    DEFAULT_SERVICE_TIMEOUT,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    SERVICE_SHUTDOWN_GRACE_PERIOD,
    # 데이터 클래스
    ServiceInfo,
    ServiceDependency,
    ServiceMetrics,
    ServiceConfig,
    RegisteredService,
    # 프로토콜 인터페이스
    IService,
    # 메인 클래스
    ServiceRegistry,
    # 함수
    get_service,
    register_service,
    # 유틸리티 (테스트용)
    _get_registry as _get_service_registry,
    _reset_registry as _reset_service_registry,
)

# ============================================================
# dependency_injector 임포트
# ============================================================
from core_foundation.registry.dependency_injector import (
    # Enum
    Scope,
    LifecycleHook,
    ResolutionStatus,
    # 상수
    DEFAULT_MAX_RESOLUTION_DEPTH,
    DEFAULT_SCOPE_NAME,
    # 예외
    DIException,
    ServiceNotFoundError,
    CircularDependencyError,
    ResolutionError,
    # 데이터 클래스
    ServiceDescriptor,
    DependencyNode,
    DependencyGraph,
    ScopeContext,
    # 메인 클래스
    DIContainer,
    ContainerBuilder,
    ServiceProvider,
    # 데코레이터
    injectable,
    inject,
    is_injectable,
    get_injectable_metadata,
    # 함수
    get_container,
    configure_container,
    # 유틸리티 (테스트용)
    _reset_container,
)

# ============================================================
# pipeline_coordinator 임포트
# ============================================================
from core_foundation.registry.pipeline_coordinator import (
    # Enum
    PipelineType,
    StageType,
    StageStatus,
    PipelineStatus,
    # 상수
    DEFAULT_STAGE_TIMEOUT,
    DEFAULT_PIPELINE_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    MAX_CONCURRENT_PIPELINES,
    # 예외
    PipelineException,
    StageExecutionError,
    PipelineTimeoutError,
    PipelineConfigError,
    # 타입 별칭
    StageHandler,
    ProgressCallback,
    ErrorCallback,
    CheckpointCallback,
    # 데이터 클래스
    StageConfig,
    StageResult,
    PipelineConfig,
    PipelineProgress,
    PipelineContext,
    CheckpointData,
    # 메인 클래스
    PipelineCoordinator,
    PipelineBuilder,
    PipelineTemplates,
    CheckpointManager,
    # 함수
    get_coordinator,
    create_pipeline,
    # 유틸리티 (테스트용)
    _reset_coordinator,
)

# ============================================================
# rule_set_manager 임포트 (v3.0.0)
# ============================================================
from core_foundation.registry.rule_set_manager import (
    # Enum
    League,
    RuleCategory,
    RuleSeverity,
    # 상수
    SUPPORTED_LEAGUES,
    DEFAULT_RULE_SET_PATH,
    RULE_SET_SCHEMA_VERSION,
    DEFAULT_CACHE_TTL,
    MAX_CACHE_SIZE,
    RULE_PRIORITY_WEIGHTS,
    LEAGUE_HIERARCHY,
    DEFAULT_FALLBACK_LEAGUE,
    # 데이터 클래스
    Rule,
    RuleSet,
    RuleCondition,
    Penalty,
    RuleSetMetadata,
    LeagueConfig,
    # Protocol
    RuleSetLoaderProtocol,
    # 메인 클래스
    RuleSetManager,
    # 헬퍼 함수
    load_rule_set,
    get_rule_by_id,
    get_rules_by_category,
    merge_rule_sets,
    validate_rule_set,
    # 리그별 팩토리 함수
    get_fiba_rules,
    get_nba_rules,
    get_kbl_rules,
    get_nbl_rules,
    get_ncaa_rules,
    get_b_league_rules,
    get_pba_rules,
    # 유틸리티 (테스트용)
    _get_manager as _get_rule_set_manager,
    _reset_manager as _reset_rule_set_manager,
)

# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # model_registry - Enum
    "ModelType",
    "ModelStatus",
    "ModelFormat",
    # model_registry - 상수
    "DEFAULT_MAX_MODELS",
    "DEFAULT_MODEL_TIMEOUT",
    "DEFAULT_WARMUP_ITERATIONS",
    "MODEL_CACHE_SIZE_MB",
    # model_registry - 데이터 클래스
    "ModelInfo",
    "ModelVersion",
    "ModelMetrics",
    "ModelConfig",
    "LoadedModel",
    # model_registry - 프로토콜 인터페이스
    "IModel",
    "IModelLoader",
    # model_registry - 메인 클래스
    "ModelRegistry",
    # model_registry - 함수
    "get_model",
    "register_model",
    # model_registry - 유틸리티 (테스트용)
    "_get_model_registry",
    "_reset_model_registry",
    # service_registry - Enum
    "ServiceType",
    "ServiceLifecycle",
    "DependencyType",
    # service_registry - 예외 클래스
    "ServiceRegistryException",
    "ServiceAlreadyExistsError",
    "ServiceCapacityExceededError",
    # service_registry - 상수
    "DEFAULT_MAX_SERVICES",
    "DEFAULT_SERVICE_TIMEOUT",
    "DEFAULT_HEALTH_CHECK_INTERVAL",
    "SERVICE_SHUTDOWN_GRACE_PERIOD",
    # service_registry - 데이터 클래스
    "ServiceInfo",
    "ServiceDependency",
    "ServiceMetrics",
    "ServiceConfig",
    "RegisteredService",
    # service_registry - 프로토콜 인터페이스
    "IService",
    # service_registry - 메인 클래스
    "ServiceRegistry",
    # service_registry - 함수
    "get_service",
    "register_service",
    # service_registry - 유틸리티 (테스트용)
    "_get_service_registry",
    "_reset_service_registry",
    # dependency_injector - Enum
    "Scope",
    "LifecycleHook",
    "ResolutionStatus",
    # dependency_injector - 상수
    "DEFAULT_MAX_RESOLUTION_DEPTH",
    "DEFAULT_SCOPE_NAME",
    # dependency_injector - 예외
    "DIException",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "ResolutionError",
    # dependency_injector - 데이터 클래스
    "ServiceDescriptor",
    "DependencyNode",
    "DependencyGraph",
    "ScopeContext",
    # dependency_injector - 메인 클래스
    "DIContainer",
    "ContainerBuilder",
    "ServiceProvider",
    # dependency_injector - 데코레이터
    "injectable",
    "inject",
    "is_injectable",
    "get_injectable_metadata",
    # dependency_injector - 함수
    "get_container",
    "configure_container",
    # dependency_injector - 유틸리티 (테스트용)
    "_reset_container",
    # pipeline_coordinator - Enum
    "PipelineType",
    "StageType",
    "StageStatus",
    "PipelineStatus",
    # pipeline_coordinator - 상수
    "DEFAULT_STAGE_TIMEOUT",
    "DEFAULT_PIPELINE_TIMEOUT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "MAX_CONCURRENT_PIPELINES",
    # pipeline_coordinator - 예외
    "PipelineException",
    "StageExecutionError",
    "PipelineTimeoutError",
    "PipelineConfigError",
    # pipeline_coordinator - 타입 별칭
    "StageHandler",
    "ProgressCallback",
    "ErrorCallback",
    "CheckpointCallback",
    # pipeline_coordinator - 데이터 클래스
    "StageConfig",
    "StageResult",
    "PipelineConfig",
    "PipelineProgress",
    "PipelineContext",
    "CheckpointData",
    # pipeline_coordinator - 메인 클래스
    "PipelineCoordinator",
    "PipelineBuilder",
    "PipelineTemplates",
    "CheckpointManager",
    # pipeline_coordinator - 함수
    "get_coordinator",
    "create_pipeline",
    # pipeline_coordinator - 유틸리티 (테스트용)
    "_reset_coordinator",
    # rule_set_manager - Enum (v3.0.0)
    "League",
    "RuleCategory",
    "RuleSeverity",
    # rule_set_manager - 상수
    "SUPPORTED_LEAGUES",
    "DEFAULT_RULE_SET_PATH",
    "RULE_SET_SCHEMA_VERSION",
    "DEFAULT_CACHE_TTL",
    "MAX_CACHE_SIZE",
    "RULE_PRIORITY_WEIGHTS",
    "LEAGUE_HIERARCHY",
    "DEFAULT_FALLBACK_LEAGUE",
    # rule_set_manager - 데이터 클래스
    "Rule",
    "RuleSet",
    "RuleCondition",
    "Penalty",
    "RuleSetMetadata",
    "LeagueConfig",
    # rule_set_manager - Protocol
    "RuleSetLoaderProtocol",
    # rule_set_manager - 메인 클래스
    "RuleSetManager",
    # rule_set_manager - 헬퍼 함수
    "load_rule_set",
    "get_rule_by_id",
    "get_rules_by_category",
    "merge_rule_sets",
    "validate_rule_set",
    # rule_set_manager - 리그별 팩토리 함수
    "get_fiba_rules",
    "get_nba_rules",
    "get_kbl_rules",
    "get_nbl_rules",
    "get_ncaa_rules",
    "get_b_league_rules",
    "get_pba_rules",
    # rule_set_manager - 유틸리티 (테스트용)
    "_get_rule_set_manager",
    "_reset_rule_set_manager",
]

__version__: str = "1.0.0"
