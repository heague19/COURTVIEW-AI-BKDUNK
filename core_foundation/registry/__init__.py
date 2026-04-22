# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
설명: 서비스/모델/의존성/파이프라인/규칙 레지스트리 통합 패키지.
     - ServiceRegistry: 서비스 등록/해석
     - ModelRegistry: 모델 등록/로드/VRAM 관리
     - DependencyInjector: DI 컨테이너
     - PipelineCoordinator: 파이프라인 오케스트레이션
     - RuleSetManager: 리그별 규칙 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations


# =============================================================================
# service_registry
# =============================================================================
from core_foundation.registry.service_registry import (
    MAX_DEPENDENCY_DEPTH,
    MAX_SERVICES,
    MAX_TAGS_PER_SERVICE,
    ServiceDescriptor,
    ServiceLifecycle,
    ServiceRegistry,
)

# =============================================================================
# model_registry
# =============================================================================
from core_foundation.registry.model_registry import (
    DEFAULT_VRAM_BUDGET_MB,
    MAX_MODELS,
    MIN_VRAM_BUDGET_MB,
    ModelBackend,
    ModelInfo,
    ModelLoaderFn,
    ModelRegistry,
    ModelStatus,
    ModelUnloaderFn,
)

# =============================================================================
# dependency_injector
# =============================================================================
from core_foundation.registry.dependency_injector import (
    MAX_BINDINGS,
    MAX_RESOLVE_DEPTH,
    MAX_SCOPES,
    Binding,
    DependencyInjector,
    Scope,
)

# =============================================================================
# pipeline_coordinator
# =============================================================================
from core_foundation.registry.pipeline_coordinator import (
    MAX_PIPELINES,
    MAX_STAGES_PER_PIPELINE,
    PipelineCoordinator,
    PipelineResult,
    StageCallback,
    StageDefinition,
    StageResult,
    StageStatus,
)

# =============================================================================
# rule_set_manager
# =============================================================================
from core_foundation.registry.rule_set_manager import (
    DEFAULT_RULE_SET,
    MAX_CALLBACKS,
    MAX_OVERRIDES_PER_RULESET,
    RuleChangeCallback,
    RuleOverride,
    RuleSetManager,
    RuleSnapshot,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # --- service_registry ---
    "ServiceLifecycle",
    "ServiceDescriptor",
    "ServiceRegistry",
    "MAX_SERVICES",
    "MAX_DEPENDENCY_DEPTH",
    "MAX_TAGS_PER_SERVICE",
    # --- model_registry ---
    "ModelStatus",
    "ModelBackend",
    "ModelInfo",
    "ModelLoaderFn",
    "ModelUnloaderFn",
    "ModelRegistry",
    "MAX_MODELS",
    "DEFAULT_VRAM_BUDGET_MB",
    "MIN_VRAM_BUDGET_MB",
    # --- dependency_injector ---
    "Scope",
    "Binding",
    "DependencyInjector",
    "MAX_BINDINGS",
    "MAX_RESOLVE_DEPTH",
    "MAX_SCOPES",
    # --- pipeline_coordinator ---
    "StageStatus",
    "StageResult",
    "StageDefinition",
    "PipelineResult",
    "StageCallback",
    "PipelineCoordinator",
    "MAX_PIPELINES",
    "MAX_STAGES_PER_PIPELINE",
    # --- rule_set_manager ---
    "RuleOverride",
    "RuleSnapshot",
    "RuleChangeCallback",
    "RuleSetManager",
    "MAX_OVERRIDES_PER_RULESET",
    "MAX_CALLBACKS",
    "DEFAULT_RULE_SET",
]

__version__ = "1.0.0"
