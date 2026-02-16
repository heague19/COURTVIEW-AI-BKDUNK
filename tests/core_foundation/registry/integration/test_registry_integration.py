# -*- coding: utf-8 -*-
"""
COURTVIEW - registry 모듈 통합 테스트

12개 카테고리, ~80개 테스트

검증 범위:
    [1]  __init__.py 임포트 무결성 (model_registry, service_registry, dependency_injector, pipeline_coordinator, rule_set_manager)
    [2]  __all__ 전체 Export 검증
    [3]  Enum 상호 호환성 / 교차 참조
    [4]  ModelRegistry 독립 워크플로우
    [5]  ServiceRegistry 독립 워크플로우
    [6]  DependencyInjector 독립 워크플로우
    [7]  PipelineCoordinator 독립 워크플로우
    [8]  RuleSetManager 독립 워크플로우
    [9]  ModelRegistry + ServiceRegistry 연동
    [10] DI + Registry 연동
    [11] 전체 파이프라인 시뮬레이션
    [12] 싱글톤 격리 / 스레드 안전성

실행:
    python tests/core_foundation/registry/integration/test_registry_integration.py

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12
"""

from __future__ import annotations

import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================
# TestResult
# ============================================================
class TestResult:
    """테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str = "") -> None:
        self.failed += 1
        self.failures.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> None:
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"통합 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"통합 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)


# =============================================================================
# [1] __init__.py 임포트 무결성 (8개)
# =============================================================================
def test_import_integrity(result: TestResult) -> None:
    """__init__.py에서 모든 서브모듈 임포트가 정상적으로 동작하는지 검증."""
    print("\n[1] __init__.py 임포트 무결성")

    # 1-1. 패키지 임포트 자체 성공
    try:
        import core_foundation.registry as registry
        assert registry is not None
        result.ok("1-1 core_foundation.registry 패키지 임포트")
    except Exception as e:
        result.fail("1-1 패키지 임포트", str(e))
        return  # 실패 시 나머지 테스트 불가

    # 1-2. model_registry 심볼 (16개)
    try:
        from core_foundation.registry import (
            ModelType, ModelStatus, ModelFormat,
            DEFAULT_MAX_MODELS, DEFAULT_MODEL_TIMEOUT,
            DEFAULT_WARMUP_ITERATIONS, MODEL_CACHE_SIZE_MB,
            ModelInfo, ModelVersion, ModelMetrics, ModelConfig, LoadedModel,
            IModel, IModelLoader,
            ModelRegistry,
            get_model, register_model,
            _get_model_registry, _reset_model_registry,
        )
        assert ModelType is not None
        assert ModelRegistry is not None
        result.ok("1-2 model_registry 심볼 (20개)")
    except ImportError as e:
        result.fail("1-2 model_registry 임포트", str(e))

    # 1-3. service_registry 심볼 (15개)
    try:
        from core_foundation.registry import (
            ServiceType, ServiceLifecycle, DependencyType,
            DEFAULT_MAX_SERVICES, DEFAULT_SERVICE_TIMEOUT,
            DEFAULT_HEALTH_CHECK_INTERVAL, SERVICE_SHUTDOWN_GRACE_PERIOD,
            ServiceInfo, ServiceDependency, ServiceMetrics,
            ServiceConfig, RegisteredService,
            IService,
            ServiceRegistry,
            get_service, register_service,
            _get_service_registry, _reset_service_registry,
        )
        assert ServiceType is not None
        assert ServiceRegistry is not None
        result.ok("1-3 service_registry 심볼 (19개)")
    except ImportError as e:
        result.fail("1-3 service_registry 임포트", str(e))

    # 1-4. dependency_injector 심볼 (21개)
    try:
        from core_foundation.registry import (
            Scope, LifecycleHook, ResolutionStatus,
            DEFAULT_MAX_RESOLUTION_DEPTH, DEFAULT_SCOPE_NAME,
            DIException, ServiceNotFoundError,
            CircularDependencyError, ResolutionError,
            ServiceDescriptor, DependencyNode, DependencyGraph, ScopeContext,
            DIContainer, ContainerBuilder, ServiceProvider,
            injectable, inject, is_injectable, get_injectable_metadata,
            get_container, configure_container,
            _reset_container,
        )
        assert Scope is not None
        assert DIContainer is not None
        result.ok("1-4 dependency_injector 심볼 (23개)")
    except ImportError as e:
        result.fail("1-4 dependency_injector 임포트", str(e))

    # 1-5. pipeline_coordinator 심볼 (31개)
    try:
        from core_foundation.registry import (
            PipelineType, StageType, StageStatus, PipelineStatus,
            DEFAULT_STAGE_TIMEOUT, DEFAULT_PIPELINE_TIMEOUT,
            DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY, MAX_CONCURRENT_PIPELINES,
            PipelineException, StageExecutionError,
            PipelineTimeoutError, PipelineConfigError,
            StageHandler, ProgressCallback, ErrorCallback, CheckpointCallback,
            StageConfig, StageResult, PipelineConfig,
            PipelineProgress, PipelineContext, CheckpointData,
            PipelineCoordinator, PipelineBuilder, PipelineTemplates,
            CheckpointManager,
            get_coordinator, create_pipeline,
            _reset_coordinator,
        )
        assert PipelineType is not None
        assert PipelineCoordinator is not None
        result.ok("1-5 pipeline_coordinator 심볼 (31개)")
    except ImportError as e:
        result.fail("1-5 pipeline_coordinator 임포트", str(e))

    # 1-6. rule_set_manager 심볼 (32개)
    try:
        from core_foundation.registry import (
            League, RuleCategory, RuleSeverity,
            SUPPORTED_LEAGUES, DEFAULT_RULE_SET_PATH,
            RULE_SET_SCHEMA_VERSION, DEFAULT_CACHE_TTL, MAX_CACHE_SIZE,
            RULE_PRIORITY_WEIGHTS, LEAGUE_HIERARCHY, DEFAULT_FALLBACK_LEAGUE,
            Rule, RuleSet, RuleCondition, Penalty, RuleSetMetadata, LeagueConfig,
            RuleSetLoaderProtocol,
            RuleSetManager,
            load_rule_set, get_rule_by_id, get_rules_by_category,
            merge_rule_sets, validate_rule_set,
            get_fiba_rules, get_nba_rules, get_kbl_rules,
            get_nbl_rules, get_ncaa_rules, get_b_league_rules, get_pba_rules,
            _get_rule_set_manager, _reset_rule_set_manager,
        )
        assert League is not None
        assert RuleSetManager is not None
        result.ok("1-6 rule_set_manager 심볼 (32개)")
    except ImportError as e:
        result.fail("1-6 rule_set_manager 임포트", str(e))

    # 1-7. 총 Export 수 검증 (__all__ 길이)
    try:
        import core_foundation.registry as registry
        total = len(registry.__all__)
        # 기대: 모든 서브모듈 __all__ 합산
        assert total > 100, f"__all__ 개수가 너무 적음: {total}"
        result.ok(f"1-7 __all__ 총 Export 수 ({total}개)")
    except Exception as e:
        result.fail("1-7 __all__ 개수", str(e))

    # 1-8. 중복 Export 없음
    try:
        all_list = registry.__all__
        duplicates = [x for x in all_list if all_list.count(x) > 1]
        assert len(duplicates) == 0, f"중복: {set(duplicates)}"
        result.ok("1-8 __all__ 중복 없음")
    except Exception as e:
        result.fail("1-8 중복 검사", str(e))


# =============================================================================
# [2] __all__ 전체 Export 검증 (5개)
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__init__.py __all__ 전체 Export 검증."""
    print("\n[2] __all__ Export 검증")

    import core_foundation.registry as registry

    # 2-1. model_registry Export 접근 가능
    try:
        model_symbols = [
            "ModelType", "ModelStatus", "ModelFormat",
            "ModelInfo", "ModelVersion", "ModelMetrics", "ModelConfig", "LoadedModel",
            "IModel", "IModelLoader", "ModelRegistry",
            "get_model", "register_model",
            "_get_model_registry", "_reset_model_registry",
        ]
        missing = [s for s in model_symbols if not hasattr(registry, s)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-1 model_registry Export 접근 가능 ({len(model_symbols)}개)")
    except Exception as e:
        result.fail("2-1 model_registry Export", str(e))

    # 2-2. service_registry Export 접근 가능
    try:
        svc_symbols = [
            "ServiceType", "ServiceLifecycle", "DependencyType",
            "ServiceInfo", "ServiceDependency", "ServiceMetrics",
            "ServiceConfig", "RegisteredService",
            "IService", "ServiceRegistry",
            "get_service", "register_service",
            "_get_service_registry", "_reset_service_registry",
        ]
        missing = [s for s in svc_symbols if not hasattr(registry, s)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-2 service_registry Export 접근 가능 ({len(svc_symbols)}개)")
    except Exception as e:
        result.fail("2-2 service_registry Export", str(e))

    # 2-3. dependency_injector Export 접근 가능
    try:
        di_symbols = [
            "Scope", "LifecycleHook", "ResolutionStatus",
            "DIException", "ServiceNotFoundError", "CircularDependencyError", "ResolutionError",
            "ServiceDescriptor", "DependencyNode", "DependencyGraph", "ScopeContext",
            "DIContainer", "ContainerBuilder", "ServiceProvider",
            "injectable", "inject", "is_injectable", "get_injectable_metadata",
            "get_container", "configure_container", "_reset_container",
        ]
        missing = [s for s in di_symbols if not hasattr(registry, s)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-3 dependency_injector Export 접근 가능 ({len(di_symbols)}개)")
    except Exception as e:
        result.fail("2-3 dependency_injector Export", str(e))

    # 2-4. pipeline_coordinator Export 접근 가능
    try:
        pipe_symbols = [
            "PipelineType", "StageType", "StageStatus", "PipelineStatus",
            "PipelineException", "StageExecutionError", "PipelineTimeoutError", "PipelineConfigError",
            "StageConfig", "StageResult", "PipelineConfig", "PipelineProgress",
            "PipelineContext", "CheckpointData",
            "PipelineCoordinator", "PipelineBuilder", "PipelineTemplates", "CheckpointManager",
            "get_coordinator", "create_pipeline", "_reset_coordinator",
        ]
        missing = [s for s in pipe_symbols if not hasattr(registry, s)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-4 pipeline_coordinator Export 접근 가능 ({len(pipe_symbols)}개)")
    except Exception as e:
        result.fail("2-4 pipeline_coordinator Export", str(e))

    # 2-5. rule_set_manager Export 접근 가능
    try:
        rule_symbols = [
            "League", "RuleCategory", "RuleSeverity",
            "SUPPORTED_LEAGUES", "DEFAULT_RULE_SET_PATH", "RULE_SET_SCHEMA_VERSION",
            "DEFAULT_CACHE_TTL", "MAX_CACHE_SIZE", "RULE_PRIORITY_WEIGHTS",
            "LEAGUE_HIERARCHY", "DEFAULT_FALLBACK_LEAGUE",
            "Rule", "RuleSet", "RuleCondition", "Penalty", "RuleSetMetadata", "LeagueConfig",
            "RuleSetLoaderProtocol", "RuleSetManager",
            "load_rule_set", "get_rule_by_id", "get_rules_by_category",
            "merge_rule_sets", "validate_rule_set",
            "get_fiba_rules", "get_nba_rules", "get_kbl_rules",
            "get_nbl_rules", "get_ncaa_rules", "get_b_league_rules", "get_pba_rules",
            "_get_rule_set_manager", "_reset_rule_set_manager",
        ]
        missing = [s for s in rule_symbols if not hasattr(registry, s)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-5 rule_set_manager Export 접근 가능 ({len(rule_symbols)}개)")
    except Exception as e:
        result.fail("2-5 rule_set_manager Export", str(e))


# =============================================================================
# [3] Enum 상호 호환성 (5개)
# =============================================================================
def test_enum_cross_reference(result: TestResult) -> None:
    """서로 다른 모듈의 Enum이 독립적이고 충돌 없이 사용 가능한지 검증."""
    print("\n[3] Enum 상호 호환성")

    from core_foundation.registry import (
        ModelType, ModelStatus, ModelFormat,
        ServiceType, ServiceLifecycle, DependencyType,
        Scope, LifecycleHook, ResolutionStatus,
        PipelineType, StageType, StageStatus, PipelineStatus,
        League, RuleCategory, RuleSeverity,
    )

    # 3-1. ModelType과 ServiceType이 서로 다른 네임스페이스
    try:
        assert ModelType is not ServiceType
        # 같은 값 "custom"이 있어도 서로 다른 Enum 타입
        # 참고: str Enum은 str.__eq__로 값 비교가 되므로 type()으로 구분
        assert type(ModelType.CUSTOM) is not type(ServiceType.CUSTOM)
        assert ModelType.CUSTOM is not ServiceType.CUSTOM
        # Enum 클래스 이름이 다름
        assert type(ModelType.CUSTOM).__name__ == "ModelType"
        assert type(ServiceType.CUSTOM).__name__ == "ServiceType"
        result.ok("3-1 ModelType != ServiceType (독립 네임스페이스)")
    except Exception as e:
        result.fail("3-1 Enum 네임스페이스", str(e))

    # 3-2. PipelineType과 StageType 교차 참조 가능
    try:
        # 파이프라인 타입의 카테고리 참조
        pt = PipelineType.TRAINING_SHOOTING
        assert pt.category == "training"
        # 스테이지 타입의 phase 참조
        st = StageType.SHOOTING_ANALYSIS
        assert st.phase is not None
        # 두 Enum은 독립적이지만 함께 사용 가능
        config_data = {"pipeline": pt.value, "stage": st.value}
        assert "training_shooting" in config_data["pipeline"]
        assert "shooting_analysis" in config_data["stage"]
        result.ok("3-2 PipelineType/StageType 교차 참조 가능")
    except Exception as e:
        result.fail("3-2 PipelineType/StageType", str(e))

    # 3-3. Scope과 ServiceLifecycle 독립성
    try:
        # Scope는 DI 스코프, ServiceLifecycle은 서비스 상태 - 완전 독립
        assert Scope.SINGLETON.value == "singleton"
        assert ServiceLifecycle.REGISTERED.value == "registered"
        assert Scope is not ServiceLifecycle
        # 동시 사용 가능
        scope = Scope.SINGLETON
        lifecycle = ServiceLifecycle.RUNNING
        assert scope.is_cached is True
        assert lifecycle.is_active is True
        result.ok("3-3 Scope/ServiceLifecycle 독립성")
    except Exception as e:
        result.fail("3-3 Scope/ServiceLifecycle", str(e))

    # 3-4. League과 RuleCategory 조합 사용
    try:
        # 리그와 규칙 카테고리 조합으로 필터링 키 생성
        league = League.NBA
        category = RuleCategory.FOUL
        combo_key = f"{league.value}_{category.value}"
        assert combo_key == "nba_foul"
        assert league.display_name is not None
        assert category.display_name is not None
        result.ok("3-4 League/RuleCategory 조합 사용")
    except Exception as e:
        result.fail("3-4 League/RuleCategory", str(e))

    # 3-5. 모든 Enum이 str 또는 정수 기반인지 확인
    try:
        str_enums = [
            ModelType, ModelStatus, ModelFormat,
            ServiceType, ServiceLifecycle, DependencyType,
            Scope, LifecycleHook, ResolutionStatus,
            PipelineType, StageType, StageStatus, PipelineStatus,
            RuleCategory, RuleSeverity,
        ]
        for enum_cls in str_enums:
            for member in enum_cls:
                assert isinstance(member.value, str), \
                    f"{enum_cls.__name__}.{member.name}.value = {member.value} (type: {type(member.value).__name__})"
        # League는 str value 이지만 str(Enum)이 아닌 일반 Enum일 수 있음
        for member in League:
            assert isinstance(member.value, str), \
                f"League.{member.name}.value = {member.value} (expected str)"
        result.ok(f"3-5 모든 Enum 값 타입 일관성 (str 기반 {len(str_enums) + 1}개)")
    except Exception as e:
        result.fail("3-5 Enum 값 타입", str(e))


# =============================================================================
# [4] ModelRegistry 독립 워크플로우 (6개)
# =============================================================================
def test_model_registry_workflow(result: TestResult) -> None:
    """ModelRegistry 등록 -> 조회 -> 목록 전체 흐름."""
    print("\n[4] ModelRegistry 독립 워크플로우")

    from core_foundation.registry import (
        ModelRegistry, ModelType, ModelStatus, ModelFormat,
        ModelVersion, ModelMetrics, ModelConfig, ModelInfo,
        _reset_model_registry,
    )

    _reset_model_registry()
    reg = ModelRegistry(max_models=50)

    # 4-1. 모델 등록 -> 조회 -> 목록
    try:
        info = reg.register(
            name="yolov8n-pose",
            model_type=ModelType.YOLO,
            version="1.0.0",
            description="YOLOv8 포즈 추정 모델",
        )
        assert isinstance(info, ModelInfo)
        assert info.model_id == "yolov8n-pose:1.0.0"
        # 조회
        retrieved = reg.get("yolov8n-pose:1.0.0")
        assert retrieved is not None
        assert retrieved.name == "yolov8n-pose"
        # 목록
        all_models = reg.list_all()
        assert len(all_models) == 1
        result.ok("4-1 모델 등록 -> 조회 -> 목록")
    except Exception as e:
        result.fail("4-1 모델 워크플로우", str(e))

    # 4-2. 버전 관리 (ModelVersion 비교)
    try:
        v1 = ModelVersion(major=1, minor=0, patch=0)
        v2 = ModelVersion(major=1, minor=1, patch=0)
        v3 = ModelVersion.from_string("2.0.0")
        assert v1 < v2
        assert v2 < v3
        assert v1 == ModelVersion(major=1, minor=0, patch=0)
        assert str(v3) == "2.0.0"
        # 프리릴리즈 버전
        v_pre = ModelVersion.from_string("1.0.0-beta")
        assert str(v_pre) == "1.0.0-beta"
        result.ok("4-2 ModelVersion 비교/파싱")
    except Exception as e:
        result.fail("4-2 ModelVersion", str(e))

    # 4-3. 모델 상태 전이 (registered -> loaded 등)
    try:
        info = reg.get("yolov8n-pose:1.0.0")
        assert info.status == ModelStatus.REGISTERED
        # 수동 상태 전이 (로더 없이)
        info.update_status(ModelStatus.LOADING, "로딩 시작")
        assert info.status == ModelStatus.LOADING
        info.update_status(ModelStatus.READY, "준비 완료")
        assert info.status == ModelStatus.READY
        assert info.status.is_usable is True
        result.ok("4-3 모델 상태 전이 (REGISTERED -> LOADING -> READY)")
    except Exception as e:
        result.fail("4-3 상태 전이", str(e))

    # 4-4. ModelMetrics record_inference 누적
    try:
        metrics = ModelMetrics()
        for i in range(10):
            metrics.record_inference(
                duration_ms=float(10 + i),
                success=True,
                confidence=0.9 + (i * 0.005),
            )
        assert metrics.total_inferences == 10
        assert metrics.successful_inferences == 10
        assert metrics.failed_inferences == 0
        assert metrics.average_inference_time_ms > 0
        assert metrics.current_fps > 0
        assert metrics.success_rate == 1.0
        result.ok(f"4-4 ModelMetrics 누적 (inferences={metrics.total_inferences}, avg={metrics.average_inference_time_ms:.1f}ms)")
    except Exception as e:
        result.fail("4-4 ModelMetrics", str(e))

    # 4-5. list_by_type 필터링
    try:
        reg.register(name="mediapipe-pose", model_type=ModelType.MEDIAPIPE, version="1.0.0")
        reg.register(name="onnx-ball", model_type=ModelType.ONNX, version="1.0.0")
        yolo_models = reg.list_by_type(ModelType.YOLO)
        assert len(yolo_models) == 1
        assert yolo_models[0].name == "yolov8n-pose"
        mediapipe_models = reg.list_by_type(ModelType.MEDIAPIPE)
        assert len(mediapipe_models) == 1
        result.ok("4-5 list_by_type 필터링 (YOLO=1, MEDIAPIPE=1)")
    except Exception as e:
        result.fail("4-5 list_by_type", str(e))

    # 4-6. unregister -> get returns None
    try:
        success = reg.unregister("onnx-ball:1.0.0")
        assert success is True
        assert reg.get("onnx-ball:1.0.0") is None
        assert reg.model_count == 2  # yolov8n-pose + mediapipe-pose
        result.ok("4-6 unregister -> get returns None")
    except Exception as e:
        result.fail("4-6 unregister", str(e))

    reg.shutdown()
    _reset_model_registry()


# =============================================================================
# [5] ServiceRegistry 독립 워크플로우 (6개)
# =============================================================================
def test_service_registry_workflow(result: TestResult) -> None:
    """ServiceRegistry 등록 -> 조회 -> 타입별 조회 전체 흐름."""
    print("\n[5] ServiceRegistry 독립 워크플로우")

    from core_foundation.registry import (
        ServiceRegistry, ServiceType, ServiceLifecycle,
        DependencyType as SvcDependencyType,
        ServiceDependency, ServiceMetrics, ServiceConfig, ServiceInfo,
        _reset_service_registry,
    )

    _reset_service_registry()
    reg = ServiceRegistry(max_services=50)

    # 테스트용 간단한 서비스 인스턴스
    class MockService:
        def __init__(self, name: str) -> None:
            self._name = name
        @property
        def service_name(self) -> str:
            return self._name
        @property
        def service_type(self) -> ServiceType:
            return ServiceType.DETECTOR
        def initialize(self) -> None:
            pass
        def start(self) -> None:
            pass
        def stop(self) -> None:
            pass
        def health_check(self) -> bool:
            return True

    # 5-1. 서비스 등록 -> 조회 -> 타입별 조회
    try:
        svc = MockService("ball_detector")
        info = reg.register(
            name="ball_detector",
            service_type=ServiceType.DETECTOR,
            instance=svc,
            description="공 탐지 서비스",
        )
        assert isinstance(info, ServiceInfo)
        service_id = info.service_id
        retrieved = reg.get(service_id)
        assert retrieved is not None
        assert retrieved.name == "ball_detector"
        # 타입별 조회
        detectors = reg.list_by_type(ServiceType.DETECTOR)
        assert len(detectors) == 1
        result.ok("5-1 서비스 등록 -> 조회 -> 타입별 조회")
    except Exception as e:
        result.fail("5-1 서비스 워크플로우", str(e))

    # 5-2. 의존성 추가 -> get_dependencies
    try:
        pose_svc = MockService("pose_estimator")
        pose_info = reg.register(
            name="pose_estimator",
            service_type=ServiceType.POSE_ESTIMATOR,
            instance=pose_svc,
            dependencies=[
                ServiceDependency(
                    service_id=service_id,
                    dependency_type=SvcDependencyType.OPTIONAL,
                    description="공 탐지 의존",
                ),
            ],
        )
        deps = reg.get_dependencies(pose_info.service_id)
        assert len(deps) == 1
        assert deps[0].service_id == service_id
        result.ok("5-2 의존성 추가 -> get_dependencies")
    except Exception as e:
        result.fail("5-2 의존성", str(e))

    # 5-3. 위상 정렬 start_order
    try:
        order = reg.get_start_order()
        assert isinstance(order, list)
        assert len(order) == 2
        # ball_detector가 먼저 시작 (pose_estimator가 의존)
        ball_idx = order.index(service_id)
        pose_idx = order.index(pose_info.service_id)
        assert ball_idx < pose_idx
        result.ok(f"5-3 위상 정렬 start_order ({len(order)}개)")
    except Exception as e:
        result.fail("5-3 위상 정렬", str(e))

    # 5-4. ServiceMetrics 업데이트 (record_request 등)
    try:
        metrics = ServiceMetrics()
        for i in range(5):
            metrics.record_request(duration_ms=float(10 + i), success=True)
        metrics.record_request(duration_ms=50.0, success=False)
        assert metrics.total_requests == 6
        assert metrics.successful_requests == 5
        assert metrics.failed_requests == 1
        assert metrics.success_rate > 0.8
        assert metrics.average_processing_time_ms > 0
        result.ok(f"5-4 ServiceMetrics (requests={metrics.total_requests}, success_rate={metrics.success_rate:.2f})")
    except Exception as e:
        result.fail("5-4 ServiceMetrics", str(e))

    # 5-5. ServiceLifecycle 상태 전이 확인
    try:
        assert ServiceLifecycle.REGISTERED.can_start is True
        assert ServiceLifecycle.REGISTERED.can_stop is False
        assert ServiceLifecycle.RUNNING.is_active is True
        assert ServiceLifecycle.RUNNING.can_stop is True
        assert ServiceLifecycle.STOPPED.can_start is True
        assert ServiceLifecycle.FAILED.can_start is True
        result.ok("5-5 ServiceLifecycle 상태 전이 규칙")
    except Exception as e:
        result.fail("5-5 ServiceLifecycle", str(e))

    # 5-6. unregister -> get returns None
    try:
        success = reg.unregister(service_id)
        assert success is True
        assert reg.get(service_id) is None
        assert reg.service_count == 1  # pose_estimator만 남음
        result.ok("5-6 unregister -> get returns None")
    except Exception as e:
        result.fail("5-6 unregister", str(e))

    reg.shutdown()
    _reset_service_registry()


# =============================================================================
# DI 테스트용 클래스 (모듈 레벨 정의 - from __future__ annotations 호환)
# =============================================================================
class _DIServiceA:
    """DI 테스트용 서비스 A."""
    def __init__(self) -> None:
        self.name = "A"

class _DIServiceB:
    """DI 테스트용 서비스 B (A에 의존)."""
    def __init__(self, a: _DIServiceA) -> None:
        self.a = a
        self.name = "B"

class _DIServiceC:
    """DI 테스트용 서비스 C (B에 의존)."""
    def __init__(self, b: _DIServiceB) -> None:
        self.b = b
        self.name = "C"

class _CyclicX:
    """순환 의존성 테스트용 X (Y에 의존)."""
    def __init__(self, y: "_CyclicY") -> None:
        self.y = y

class _CyclicY:
    """순환 의존성 테스트용 Y (X에 의존)."""
    def __init__(self, x: _CyclicX) -> None:
        self.x = x


# =============================================================================
# [6] DependencyInjector 독립 워크플로우 (8개)
# =============================================================================
def test_dependency_injector_workflow(result: TestResult) -> None:
    """DI 컨테이너 등록 -> 해결 전체 흐름."""
    print("\n[6] DependencyInjector 독립 워크플로우")

    from core_foundation.registry import (
        DIContainer, ContainerBuilder, Scope, ScopeContext,
        ServiceNotFoundError, CircularDependencyError,
        injectable, is_injectable, get_injectable_metadata,
        get_container, configure_container, _reset_container,
    )

    _reset_container()

    # 6-1. ContainerBuilder 싱글톤 등록 + resolve
    try:
        builder = ContainerBuilder()
        builder.register(_DIServiceA, scope=Scope.SINGLETON)
        container = builder.build()
        a1 = container.resolve(_DIServiceA)
        a2 = container.resolve(_DIServiceA)
        assert a1 is a2  # 싱글톤이므로 동일 인스턴스
        assert a1.name == "A"
        result.ok("6-1 ContainerBuilder 싱글톤 등록 + resolve")
    except Exception as e:
        result.fail("6-1 싱글톤", str(e))

    # 6-2. Transient 등록 + 매번 새 인스턴스
    try:
        container2 = DIContainer()
        container2.register(_DIServiceA, scope=Scope.TRANSIENT)
        t1 = container2.resolve(_DIServiceA)
        t2 = container2.resolve(_DIServiceA)
        assert t1 is not t2  # Transient이므로 매번 새 인스턴스
        result.ok("6-2 Transient 등록 -> 매번 새 인스턴스")
    except Exception as e:
        result.fail("6-2 Transient", str(e))

    # 6-3. Factory 등록 + resolve
    try:
        container3 = DIContainer()
        call_count = [0]

        def factory_a() -> _DIServiceA:
            call_count[0] += 1
            return _DIServiceA()

        container3.register_factory(_DIServiceA, factory_a, scope=Scope.SINGLETON)
        resolved = container3.resolve(_DIServiceA)
        assert isinstance(resolved, _DIServiceA)
        assert call_count[0] == 1
        # 두 번째 resolve는 캐시에서 가져옴
        container3.resolve(_DIServiceA)
        assert call_count[0] == 1  # 팩토리 다시 호출 안 됨
        result.ok("6-3 Factory 등록 + resolve (싱글톤 캐시)")
    except Exception as e:
        result.fail("6-3 Factory", str(e))

    # 6-4. 의존성 체인 (C->B->A) 자동 해결
    try:
        container4 = DIContainer()
        container4.register(_DIServiceA, scope=Scope.SINGLETON)
        container4.register(_DIServiceB, scope=Scope.SINGLETON)
        container4.register(_DIServiceC, scope=Scope.SINGLETON)
        c = container4.resolve(_DIServiceC)
        assert isinstance(c, _DIServiceC)
        assert isinstance(c.b, _DIServiceB)
        assert isinstance(c.b.a, _DIServiceA)
        assert c.name == "C"
        assert c.b.name == "B"
        assert c.b.a.name == "A"
        result.ok("6-4 의존성 체인 C->B->A 자동 해결")
    except Exception as e:
        result.fail("6-4 의존성 체인", str(e))

    # 6-5. CircularDependencyError 감지
    try:
        container5 = DIContainer()
        container5.register(_CyclicX, scope=Scope.TRANSIENT)
        container5.register(_CyclicY, scope=Scope.TRANSIENT)
        try:
            container5.resolve(_CyclicX)
            result.fail("6-5 순환 의존성", "CircularDependencyError 미발생")
        except CircularDependencyError:
            result.ok("6-5 CircularDependencyError 감지")
        except Exception as e2:
            # 다른 예외도 순환 감지와 관련될 수 있음
            if "순환" in str(e2) or "circular" in str(e2).lower():
                result.ok("6-5 CircularDependencyError 감지 (대체 예외)")
            else:
                result.fail("6-5 순환 의존성", str(e2))
    except Exception as e:
        result.fail("6-5 순환 의존성", str(e))

    # 6-6. @injectable 데코레이터 + is_injectable
    try:
        @injectable(scope=Scope.SINGLETON, name="test_service", tags=["test"])
        class TestInjectableService:
            pass

        assert is_injectable(TestInjectableService) is True
        metadata = get_injectable_metadata(TestInjectableService)
        assert metadata is not None
        assert metadata["scope"] == Scope.SINGLETON
        assert metadata["name"] == "test_service"
        assert "test" in metadata["tags"]

        # 일반 클래스는 injectable이 아님
        class NormalClass:
            pass

        assert is_injectable(NormalClass) is False
        result.ok("6-6 @injectable 데코레이터 + is_injectable")
    except Exception as e:
        result.fail("6-6 injectable", str(e))

    # 6-7. ScopeContext 생성/해제
    try:
        scope = ScopeContext(name="test_scope")
        scope.set(_DIServiceA, _DIServiceA())
        instance = scope.get(_DIServiceA)
        assert instance is not None
        # 자식 스코프
        child = ScopeContext(name="child_scope", parent=scope)
        scope.children.append(child)
        # 부모에서 가져오기
        parent_instance = child.get(_DIServiceA)
        assert parent_instance is instance  # 부모에서 상속
        # 클리어
        scope.clear()
        assert scope.get(_DIServiceA) is None
        result.ok("6-7 ScopeContext 생성/해제/계층")
    except Exception as e:
        result.fail("6-7 ScopeContext", str(e))

    # 6-8. get_container/configure_container 전역 함수
    try:
        _reset_container()
        c = get_container()
        assert isinstance(c, DIContainer)

        def setup(container: DIContainer) -> None:
            container.register_instance(_DIServiceA, _DIServiceA())

        configured = configure_container(setup)
        assert configured is c  # 같은 전역 컨테이너
        assert c.is_registered(_DIServiceA) is True
        resolved = c.resolve(_DIServiceA)
        assert isinstance(resolved, _DIServiceA)
        result.ok("6-8 get_container/configure_container 전역 함수")
    except Exception as e:
        result.fail("6-8 전역 함수", str(e))

    _reset_container()


# =============================================================================
# [7] PipelineCoordinator 독립 워크플로우 (6개)
# =============================================================================
def test_pipeline_coordinator_workflow(result: TestResult) -> None:
    """PipelineCoordinator 빌더 -> 템플릿 -> 체크포인트 전체 흐름."""
    print("\n[7] PipelineCoordinator 독립 워크플로우")

    from core_foundation.registry import (
        PipelineCoordinator, PipelineBuilder, PipelineTemplates,
        PipelineType, StageType, StageStatus, PipelineStatus,
        StageConfig, StageResult, PipelineConfig, PipelineProgress,
        CheckpointManager, CheckpointData,
        _reset_coordinator,
    )

    _reset_coordinator()

    # 7-1. PipelineBuilder로 PipelineConfig 빌드
    try:
        config = (
            PipelineBuilder(PipelineType.TRAINING_SHOOTING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.DETECTION, timeout=120)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.SHOOTING_ANALYSIS)
            .with_timeout(1800)
            .with_fail_fast(True)
            .build()
        )
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_SHOOTING
        assert config.stage_count == 5
        assert config.timeout_seconds == 1800
        result.ok(f"7-1 PipelineBuilder 빌드 (stages={config.stage_count})")
    except Exception as e:
        result.fail("7-1 PipelineBuilder", str(e))

    # 7-2. PipelineTemplates 5개 템플릿 생성
    try:
        templates = {
            "training_shooting": PipelineTemplates.training_shooting(),
            "training_dribbling": PipelineTemplates.training_dribbling(),
            "training_comparison": PipelineTemplates.training_comparison(),
            "game_full": PipelineTemplates.game_full(),
            "referee_full": PipelineTemplates.referee_full(),
        }
        for name, tmpl in templates.items():
            assert isinstance(tmpl, PipelineConfig), f"{name} PipelineConfig 아님"
            assert tmpl.stage_count > 0, f"{name} 스테이지 없음"
        result.ok(f"7-2 PipelineTemplates 5개 템플릿 생성")
    except Exception as e:
        result.fail("7-2 PipelineTemplates", str(e))

    # 7-3. StageConfig + StageResult 데이터 흐름
    try:
        stage_config = StageConfig(
            stage_type=StageType.DETECTION,
            timeout_seconds=60,
            max_retries=3,
        )
        assert stage_config.stage_name == "detection"
        d = stage_config.to_dict()
        assert d["stage_type"] == "detection"

        stage_result = StageResult(
            stage_type=StageType.DETECTION,
            status=StageStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            output={"detections": 5},
        )
        assert stage_result.is_success is True
        assert stage_result.is_failed is False
        result.ok("7-3 StageConfig + StageResult 데이터 흐름")
    except Exception as e:
        result.fail("7-3 데이터 흐름", str(e))

    # 7-4. CheckpointManager save/restore (tempdir)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            checkpoint = CheckpointData(
                pipeline_id="test-pipeline-001",
                pipeline_type=PipelineType.TRAINING_SHOOTING,
                completed_stages=[StageType.INITIALIZATION, StageType.VIDEO_DOWNLOAD],
                current_stage_index=2,
                stage_outputs={"initialization": "ok", "video_download": "ok"},
                metadata={"user": "test"},
                created_at=datetime.now(timezone.utc),
            )
            saved = cm.save(checkpoint)
            assert saved is True
            # 복원
            loaded = cm.load("test-pipeline-001")
            assert loaded is not None
            assert loaded.pipeline_id == "test-pipeline-001"
            assert loaded.current_stage_index == 2
            assert len(loaded.completed_stages) == 2
            # 삭제
            cm.delete("test-pipeline-001")
            assert cm.load("test-pipeline-001") is None
        result.ok("7-4 CheckpointManager save/load/delete")
    except Exception as e:
        result.fail("7-4 CheckpointManager", str(e))

    # 7-5. PipelineCoordinator handler 등록/조회
    try:
        coordinator = PipelineCoordinator()

        async def mock_handler(context, stage_config):
            return {"result": "ok"}

        coordinator.register_handler(StageType.DETECTION, mock_handler)
        handler = coordinator.get_handler(StageType.DETECTION)
        assert handler is mock_handler
        # 등록 해제
        coordinator.unregister_handler(StageType.DETECTION)
        assert coordinator.get_handler(StageType.DETECTION) is None
        result.ok("7-5 PipelineCoordinator handler 등록/조회/해제")
    except Exception as e:
        result.fail("7-5 handler 등록", str(e))

    # 7-6. PipelineProgress 퍼센트 계산
    try:
        progress = PipelineProgress(
            pipeline_id="test-001",
            pipeline_type=PipelineType.TRAINING_SHOOTING,
            status=PipelineStatus.RUNNING,
            total_stages=5,
            completed_stages=0,
        )
        assert progress.progress_percent == 0.0

        # 스테이지 완료 업데이트
        for i in range(3):
            sr = StageResult(
                stage_type=StageType.INITIALIZATION,
                status=StageStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
            )
            progress.update_stage_completed(sr)

        assert progress.completed_stages == 3
        assert progress.progress_percent == 60.0
        result.ok(f"7-6 PipelineProgress 퍼센트 ({progress.progress_percent}%)")
    except Exception as e:
        result.fail("7-6 PipelineProgress", str(e))

    _reset_coordinator()


# =============================================================================
# [8] RuleSetManager 독립 워크플로우 (6개)
# =============================================================================
def test_rule_set_manager_workflow(result: TestResult) -> None:
    """RuleSetManager 규칙 로드 -> 필터 -> 검증 전체 흐름."""
    print("\n[8] RuleSetManager 독립 워크플로우")

    from core_foundation.registry import (
        RuleSetManager, League, RuleCategory, RuleSeverity,
        Rule, RuleSet, RuleCondition, Penalty,
        load_rule_set, get_rules_by_category, merge_rule_sets, validate_rule_set,
        get_fiba_rules, get_nba_rules, get_kbl_rules,
        get_nbl_rules, get_ncaa_rules, get_b_league_rules, get_pba_rules,
        SUPPORTED_LEAGUES, DEFAULT_FALLBACK_LEAGUE,
        _reset_rule_set_manager,
    )
    from core_foundation.config.loader import ConfigLoader

    _reset_rule_set_manager()

    config_loader = ConfigLoader()
    manager = RuleSetManager(config_loader)

    # 8-1. 7개 리그 규칙 로드
    try:
        leagues_loaded = 0
        for league in League:
            rule_set = manager.get_rule_set(league)
            assert isinstance(rule_set, RuleSet)
            assert rule_set.rule_count > 0
            leagues_loaded += 1
        assert leagues_loaded == 7
        result.ok(f"8-1 7개 리그 규칙 로드 (leagues={leagues_loaded})")
    except Exception as e:
        result.fail("8-1 리그 로드", str(e))

    # 8-2. 카테고리별 규칙 필터링
    try:
        fiba_rules = manager.get_rule_set(League.FIBA)
        violations = fiba_rules.get_rules_by_category(RuleCategory.VIOLATION)
        fouls = fiba_rules.get_rules_by_category(RuleCategory.FOUL)
        timing = fiba_rules.get_rules_by_category(RuleCategory.TIMING)
        assert len(violations) > 0, "바이올레이션 규칙 없음"
        assert len(timing) > 0, "시간 규칙 없음"
        total_filtered = len(violations) + len(fouls) + len(timing)
        result.ok(f"8-2 카테고리 필터 (violation={len(violations)}, foul={len(fouls)}, timing={len(timing)})")
    except Exception as e:
        result.fail("8-2 카테고리 필터", str(e))

    # 8-3. RuleCondition.evaluate 검증
    try:
        # gt 비교
        cond_gt = RuleCondition(condition_type="steps", threshold=3.0, comparison="gt")
        assert cond_gt.evaluate(4.0) is True
        assert cond_gt.evaluate(2.0) is False
        # lt 비교
        cond_lt = RuleCondition(condition_type="time", threshold=24.0, comparison="lt")
        assert cond_lt.evaluate(20.0) is True
        assert cond_lt.evaluate(25.0) is False
        # gte 비교
        cond_gte = RuleCondition(condition_type="count", threshold=5.0, comparison="gte")
        assert cond_gte.evaluate(5.0) is True
        assert cond_gte.evaluate(4.0) is False
        # eq 비교
        cond_eq = RuleCondition(condition_type="exact", threshold=10.0, comparison="eq")
        assert cond_eq.evaluate(10.0) is True
        # threshold None이면 항상 True
        cond_none = RuleCondition(condition_type="any")
        assert cond_none.evaluate(999) is True
        result.ok("8-3 RuleCondition.evaluate 검증 (gt/lt/gte/eq/none)")
    except Exception as e:
        result.fail("8-3 RuleCondition", str(e))

    # 8-4. FIBA 폴백 동작
    try:
        # NBA 규칙 세트는 FIBA를 상속
        nba_rules = manager.get_rule_set(League.NBA, include_inherited=True)
        assert nba_rules.rule_count > 0
        # NBA는 FIBA를 부모로
        assert nba_rules.parent_league == League.FIBA
        # 기본 폴백 리그 확인
        assert DEFAULT_FALLBACK_LEAGUE == "fiba"
        result.ok(f"8-4 FIBA 폴백 동작 (NBA rules={nba_rules.rule_count}, parent=FIBA)")
    except Exception as e:
        result.fail("8-4 FIBA 폴백", str(e))

    # 8-5. merge_rule_sets 합병
    try:
        fiba_set = manager.get_rule_set(League.FIBA)
        nba_set = manager.get_rule_set(League.NBA)
        merged = merge_rule_sets([fiba_set, nba_set], priority_order=[League.NBA, League.FIBA])
        assert isinstance(merged, RuleSet)
        assert merged.rule_count > 0
        result.ok(f"8-5 merge_rule_sets (merged={merged.rule_count})")
    except Exception as e:
        result.fail("8-5 merge", str(e))

    # 8-6. validate_rule_set 검증
    try:
        fiba_set = manager.get_rule_set(League.FIBA)
        is_valid = manager.validate_rule_set(fiba_set)
        assert is_valid is True
        result.ok("8-6 validate_rule_set -> True")
    except Exception as e:
        result.fail("8-6 validate", str(e))

    manager.shutdown()
    _reset_rule_set_manager()


# =============================================================================
# [9] ModelRegistry + ServiceRegistry 연동 (6개)
# =============================================================================
def test_model_service_integration(result: TestResult) -> None:
    """ModelRegistry + ServiceRegistry 연동 테스트."""
    print("\n[9] ModelRegistry + ServiceRegistry 연동")

    from core_foundation.registry import (
        ModelRegistry, ModelType, ModelStatus,
        ServiceRegistry, ServiceType, ServiceLifecycle,
        ServiceDependency, DependencyType as SvcDepType,
        _reset_model_registry, _reset_service_registry,
    )

    _reset_model_registry()
    _reset_service_registry()

    model_reg = ModelRegistry(max_models=50)
    svc_reg = ServiceRegistry(max_services=50)

    # 간단한 서비스 mock
    class MockService:
        def __init__(self, name: str) -> None:
            self._name = name
        @property
        def service_name(self) -> str:
            return self._name
        @property
        def service_type(self) -> ServiceType:
            return ServiceType.DETECTOR
        def initialize(self) -> None:
            pass
        def start(self) -> None:
            pass
        def stop(self) -> None:
            pass
        def health_check(self) -> bool:
            return True

    # 9-1. 모델을 등록하고 서비스로도 등록 (같은 이름)
    try:
        model_info = model_reg.register(
            name="yolov8n-ball",
            model_type=ModelType.YOLO,
            version="1.0.0",
        )
        svc_info = svc_reg.register(
            name="yolov8n-ball",
            service_type=ServiceType.DETECTOR,
            instance=MockService("yolov8n-ball"),
        )
        assert model_info is not None
        assert svc_info is not None
        result.ok("9-1 모델+서비스 같은 이름으로 등록")
    except Exception as e:
        result.fail("9-1 동시 등록", str(e))

    # 9-2. 서비스 의존성에 모델 이름 참조
    try:
        svc_info2 = svc_reg.register(
            name="analysis_service",
            service_type=ServiceType.ANALYZER,
            instance=MockService("analysis_service"),
            dependencies=[
                ServiceDependency(
                    service_id=svc_info.service_id,
                    dependency_type=SvcDepType.OPTIONAL,
                    description="공 탐지기 모델 서비스 의존",
                ),
            ],
        )
        deps = svc_reg.get_dependencies(svc_info2.service_id)
        assert len(deps) == 1
        assert deps[0].service_id == svc_info.service_id
        result.ok("9-2 서비스 의존성에 모델 서비스 참조")
    except Exception as e:
        result.fail("9-2 의존성 참조", str(e))

    # 9-3. 두 레지스트리 동시 목록 조회
    try:
        models = model_reg.list_all()
        services = svc_reg.list_all()
        assert len(models) == 1
        assert len(services) == 2  # detector + analyzer
        result.ok(f"9-3 동시 목록 (models={len(models)}, services={len(services)})")
    except Exception as e:
        result.fail("9-3 동시 조회", str(e))

    # 9-4. 모델 해제 -> 서비스 상태 확인
    try:
        model_reg.unregister("yolov8n-ball:1.0.0")
        assert model_reg.get("yolov8n-ball:1.0.0") is None
        # 서비스는 독립적으로 여전히 존재
        assert svc_reg.get(svc_info.service_id) is not None
        result.ok("9-4 모델 해제 -> 서비스 독립 유지")
    except Exception as e:
        result.fail("9-4 모델 해제", str(e))

    # 9-5. ServiceType.DETECTOR 타입으로 서비스 등록
    try:
        detectors = svc_reg.list_by_type(ServiceType.DETECTOR)
        analyzers = svc_reg.list_by_type(ServiceType.ANALYZER)
        assert len(detectors) == 1
        assert len(analyzers) == 1
        result.ok("9-5 ServiceType별 조회 (DETECTOR=1, ANALYZER=1)")
    except Exception as e:
        result.fail("9-5 ServiceType 조회", str(e))

    # 9-6. 두 레지스트리 모두 리셋 후 독립 확인
    try:
        model_reg.shutdown()
        svc_reg.shutdown()
        _reset_model_registry()
        _reset_service_registry()
        # 새로 생성
        mr2 = ModelRegistry(max_models=10)
        sr2 = ServiceRegistry(max_services=10)
        assert mr2.model_count == 0
        assert sr2.service_count == 0
        mr2.shutdown()
        sr2.shutdown()
        result.ok("9-6 리셋 후 독립 확인 (모두 빈 상태)")
    except Exception as e:
        result.fail("9-6 리셋 독립", str(e))

    _reset_model_registry()
    _reset_service_registry()


# =============================================================================
# [10] DI + Registry 연동 (6개)
# =============================================================================
def test_di_registry_integration(result: TestResult) -> None:
    """DI 컨테이너에 레지스트리 모듈 등록/해결."""
    print("\n[10] DI + Registry 연동")

    from core_foundation.registry import (
        DIContainer, Scope,
        ModelRegistry, ServiceRegistry,
        PipelineCoordinator, RuleSetManager,
        _reset_container, _reset_model_registry, _reset_service_registry,
        _reset_coordinator, _reset_rule_set_manager,
    )
    from core_foundation.config.loader import ConfigLoader

    _reset_container()
    _reset_model_registry()
    _reset_service_registry()
    _reset_coordinator()
    _reset_rule_set_manager()

    # 10-1. DI 컨테이너에 ModelRegistry 등록 -> resolve
    try:
        container = DIContainer()
        mr = ModelRegistry(max_models=20)
        container.register_instance(ModelRegistry, mr)
        resolved = container.resolve(ModelRegistry)
        assert resolved is mr
        result.ok("10-1 DI에 ModelRegistry 등록 -> resolve")
    except Exception as e:
        result.fail("10-1 ModelRegistry DI", str(e))

    # 10-2. DI 컨테이너에 ServiceRegistry 등록 -> resolve
    try:
        sr = ServiceRegistry(max_services=20)
        container.register_instance(ServiceRegistry, sr)
        resolved = container.resolve(ServiceRegistry)
        assert resolved is sr
        result.ok("10-2 DI에 ServiceRegistry 등록 -> resolve")
    except Exception as e:
        result.fail("10-2 ServiceRegistry DI", str(e))

    # 10-3. DI 싱글톤으로 같은 인스턴스 반환 검증
    try:
        r1 = container.resolve(ModelRegistry)
        r2 = container.resolve(ModelRegistry)
        assert r1 is r2
        s1 = container.resolve(ServiceRegistry)
        s2 = container.resolve(ServiceRegistry)
        assert s1 is s2
        result.ok("10-3 DI 싱글톤 동일 인스턴스 검증")
    except Exception as e:
        result.fail("10-3 싱글톤 검증", str(e))

    # 10-4. DI로 PipelineCoordinator 등록 -> resolve
    try:
        pc = PipelineCoordinator()
        container.register_instance(PipelineCoordinator, pc)
        resolved = container.resolve(PipelineCoordinator)
        assert resolved is pc
        result.ok("10-4 DI에 PipelineCoordinator 등록 -> resolve")
    except Exception as e:
        result.fail("10-4 PipelineCoordinator DI", str(e))

    # 10-5. DI로 RuleSetManager 등록 -> resolve
    try:
        config_loader = ConfigLoader()
        rsm = RuleSetManager(config_loader)
        container.register_instance(RuleSetManager, rsm)
        resolved = container.resolve(RuleSetManager)
        assert resolved is rsm
        result.ok("10-5 DI에 RuleSetManager 등록 -> resolve")
    except Exception as e:
        result.fail("10-5 RuleSetManager DI", str(e))

    # 10-6. 전체 5개 모듈 DI 등록 + 해결 통합
    try:
        all_types = [ModelRegistry, ServiceRegistry, PipelineCoordinator, RuleSetManager]
        for svc_type in all_types:
            assert container.is_registered(svc_type) is True
            resolved = container.resolve(svc_type)
            assert resolved is not None
        result.ok(f"10-6 전체 {len(all_types)}개 모듈 DI 등록/해결 통합")
    except Exception as e:
        result.fail("10-6 전체 DI", str(e))

    # 정리
    mr.shutdown()
    sr.shutdown()
    rsm.shutdown()
    container.shutdown()
    _reset_container()
    _reset_model_registry()
    _reset_service_registry()
    _reset_coordinator()
    _reset_rule_set_manager()


# =============================================================================
# [11] 전체 파이프라인 시뮬레이션 (8개)
# =============================================================================
def test_full_pipeline_simulation(result: TestResult) -> None:
    """전체 레지스트리 모듈을 사용한 E2E 시뮬레이션."""
    print("\n[11] 전체 파이프라인 시뮬레이션")

    from core_foundation.registry import (
        ModelRegistry, ModelType, ModelStatus,
        ServiceRegistry, ServiceType, ServiceLifecycle,
        ServiceDependency, DependencyType as SvcDepType,
        DIContainer,
        PipelineBuilder, PipelineType, StageType, PipelineConfig,
        RuleSetManager, League, RuleSet,
        _reset_model_registry, _reset_service_registry,
        _reset_coordinator, _reset_rule_set_manager, _reset_container,
    )
    from core_foundation.config.loader import ConfigLoader

    _reset_model_registry()
    _reset_service_registry()
    _reset_coordinator()
    _reset_rule_set_manager()
    _reset_container()

    model_reg = ModelRegistry(max_models=50)
    svc_reg = ServiceRegistry(max_services=50)
    config_loader = ConfigLoader()
    rule_mgr = RuleSetManager(config_loader)
    container = DIContainer()

    # 서비스 mock 클래스
    class MockService:
        def __init__(self, name: str) -> None:
            self._name = name
        @property
        def service_name(self) -> str:
            return self._name
        @property
        def service_type(self) -> ServiceType:
            return ServiceType.CUSTOM
        def initialize(self) -> None:
            pass
        def start(self) -> None:
            pass
        def stop(self) -> None:
            pass
        def health_check(self) -> bool:
            return True

    # 11-1. 모델 등록 (YOLO pose, ball detector)
    try:
        model_reg.register(name="yolo-pose", model_type=ModelType.YOLO, version="8.0.0",
                           description="YOLOv8 Pose Estimation")
        model_reg.register(name="yolo-ball", model_type=ModelType.YOLO, version="8.0.0",
                           description="YOLOv8 Ball Detection")
        assert model_reg.model_count == 2
        result.ok("11-1 모델 등록 (yolo-pose, yolo-ball)")
    except Exception as e:
        result.fail("11-1 모델 등록", str(e))

    # 11-2. 서비스 등록 (pose_service, detect_service, analysis_service) + 의존성
    try:
        pose_info = svc_reg.register(
            name="pose_service", service_type=ServiceType.POSE_ESTIMATOR,
            instance=MockService("pose_service"),
        )
        detect_info = svc_reg.register(
            name="detect_service", service_type=ServiceType.DETECTOR,
            instance=MockService("detect_service"),
        )
        analysis_info = svc_reg.register(
            name="analysis_service", service_type=ServiceType.ANALYZER,
            instance=MockService("analysis_service"),
            dependencies=[
                ServiceDependency(service_id=pose_info.service_id, dependency_type=SvcDepType.OPTIONAL),
                ServiceDependency(service_id=detect_info.service_id, dependency_type=SvcDepType.OPTIONAL),
            ],
        )
        assert svc_reg.service_count == 3
        result.ok("11-2 서비스 등록 (3개 + 의존성)")
    except Exception as e:
        result.fail("11-2 서비스 등록", str(e))

    # 11-3. DI 컨테이너에 전부 등록
    try:
        container.register_instance(ModelRegistry, model_reg)
        container.register_instance(ServiceRegistry, svc_reg)
        container.register_instance(RuleSetManager, rule_mgr)
        assert container.is_registered(ModelRegistry)
        assert container.is_registered(ServiceRegistry)
        assert container.is_registered(RuleSetManager)
        result.ok("11-3 DI 컨테이너 전부 등록")
    except Exception as e:
        result.fail("11-3 DI 등록", str(e))

    # 11-4. 파이프라인 빌드 (5단계: init -> pose -> detect -> analyze -> output)
    try:
        pipeline_config = (
            PipelineBuilder(PipelineType.TRAINING_SHOOTING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.DETECTION)
            .add_stage(StageType.SHOOTING_ANALYSIS)
            .add_stage(StageType.RESULT_UPLOAD)
            .with_timeout(600)
            .build()
        )
        assert pipeline_config.stage_count == 5
        assert pipeline_config.pipeline_type == PipelineType.TRAINING_SHOOTING
        result.ok(f"11-4 파이프라인 빌드 (stages={pipeline_config.stage_count})")
    except Exception as e:
        result.fail("11-4 파이프라인 빌드", str(e))

    # 11-5. 규칙 세트 로드 (NBA)
    try:
        nba_rules = rule_mgr.get_rule_set(League.NBA)
        assert isinstance(nba_rules, RuleSet)
        assert nba_rules.rule_count > 0
        result.ok(f"11-5 NBA 규칙 로드 (rules={nba_rules.rule_count})")
    except Exception as e:
        result.fail("11-5 NBA 규칙", str(e))

    # 11-6. 전체 상태 확인 (model count, service count, rule count)
    try:
        m_count = model_reg.model_count
        s_count = svc_reg.service_count
        r_count = nba_rules.rule_count
        assert m_count == 2
        assert s_count == 3
        assert r_count > 0
        result.ok(f"11-6 전체 상태 (models={m_count}, services={s_count}, rules={r_count})")
    except Exception as e:
        result.fail("11-6 전체 상태", str(e))

    # 11-7. 모든 모듈 리셋
    try:
        model_reg.shutdown()
        svc_reg.shutdown()
        rule_mgr.shutdown()
        container.shutdown()
        _reset_model_registry()
        _reset_service_registry()
        _reset_coordinator()
        _reset_rule_set_manager()
        _reset_container()
        result.ok("11-7 모든 모듈 리셋")
    except Exception as e:
        result.fail("11-7 리셋", str(e))

    # 11-8. 리셋 후 빈 상태 확인
    try:
        mr_new = ModelRegistry(max_models=10)
        sr_new = ServiceRegistry(max_services=10)
        assert mr_new.model_count == 0
        assert sr_new.service_count == 0
        mr_new.shutdown()
        sr_new.shutdown()
        result.ok("11-8 리셋 후 빈 상태 확인")
    except Exception as e:
        result.fail("11-8 빈 상태", str(e))

    _reset_model_registry()
    _reset_service_registry()
    _reset_coordinator()
    _reset_rule_set_manager()
    _reset_container()


# =============================================================================
# [12] 싱글톤 격리 / 스레드 안전성 (5개)
# =============================================================================
def test_singleton_isolation_and_threads(result: TestResult) -> None:
    """각 모듈 싱글톤의 독립성, 스레드 안전성, 리셋 동작."""
    print("\n[12] 싱글톤 격리 / 스레드 안전성")

    from core_foundation.registry import (
        _get_model_registry, _reset_model_registry,
        _get_service_registry, _reset_service_registry,
        _reset_coordinator,
        _get_rule_set_manager, _reset_rule_set_manager,
        _reset_container,
        ModelRegistry, ServiceRegistry, RuleSetManager,
        ModelType,
    )

    # 전체 리셋
    _reset_model_registry()
    _reset_service_registry()
    _reset_coordinator()
    _reset_rule_set_manager()
    _reset_container()

    # 12-1. 각 모듈 싱글톤 독립성 (하나 리셋해도 다른 것 영향 없음)
    try:
        mr = _get_model_registry()
        sr = _get_service_registry()
        rsm = _get_rule_set_manager()

        # 모델 레지스트리에 데이터 추가
        mr.register(name="test-model", model_type=ModelType.YOLO, version="1.0.0")

        # 모델 레지스트리만 리셋
        _reset_model_registry()

        # 서비스 레지스트리는 영향 없음
        sr_check = _get_service_registry()
        assert sr_check is sr  # 리셋 안 했으므로 동일 인스턴스

        # RuleSetManager도 영향 없음
        rsm_check = _get_rule_set_manager()
        assert rsm_check is rsm

        result.ok("12-1 싱글톤 독립성 (ModelRegistry 리셋 -> ServiceRegistry/RuleSetManager 무영향)")
    except Exception as e:
        result.fail("12-1 독립성", str(e))
    finally:
        _reset_model_registry()
        _reset_service_registry()
        _reset_rule_set_manager()

    # 12-2. 멀티스레드 ModelRegistry 접근
    try:
        _reset_model_registry()
        errors = []
        results_ids = []

        def register_model(idx: int) -> None:
            try:
                mr = _get_model_registry()
                mr.register(
                    name=f"thread-model-{idx}",
                    model_type=ModelType.YOLO,
                    version="1.0.0",
                )
                results_ids.append(idx)
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=register_model, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        mr = _get_model_registry()
        assert mr.model_count == 8
        result.ok(f"12-2 멀티스레드 ModelRegistry (8스레드, models={mr.model_count})")
    except Exception as e:
        result.fail("12-2 멀티스레드 ModelRegistry", str(e))
    finally:
        _reset_model_registry()

    # 12-3. 멀티스레드 ServiceRegistry 접근
    try:
        _reset_service_registry()
        errors = []

        class ThreadMockService:
            def __init__(self, name: str) -> None:
                self._name = name
            @property
            def service_name(self) -> str:
                return self._name
            def initialize(self) -> None:
                pass
            def start(self) -> None:
                pass
            def stop(self) -> None:
                pass
            def health_check(self) -> bool:
                return True

        from core_foundation.registry import ServiceType

        def register_service(idx: int) -> None:
            try:
                sr = _get_service_registry()
                sr.register(
                    name=f"thread-svc-{idx}",
                    service_type=ServiceType.CUSTOM,
                    instance=ThreadMockService(f"thread-svc-{idx}"),
                )
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=register_service, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        sr = _get_service_registry()
        assert sr.service_count == 8
        result.ok(f"12-3 멀티스레드 ServiceRegistry (8스레드, services={sr.service_count})")
    except Exception as e:
        result.fail("12-3 멀티스레드 ServiceRegistry", str(e))
    finally:
        _reset_service_registry()

    # 12-4. 멀티스레드 RuleSetManager 접근
    try:
        _reset_rule_set_manager()
        errors = []
        from core_foundation.registry import League

        def load_rules(idx: int) -> None:
            try:
                rsm = _get_rule_set_manager()
                league = list(League)[idx % len(list(League))]
                rule_set = rsm.get_rule_set(league)
                assert rule_set.rule_count > 0
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=load_rules, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors[:3]}"
        result.ok("12-4 멀티스레드 RuleSetManager (8스레드)")
    except Exception as e:
        result.fail("12-4 멀티스레드 RuleSetManager", str(e))
    finally:
        _reset_rule_set_manager()

    # 12-5. 전체 리셋 순서 안전성
    try:
        # 순방향 리셋
        _get_model_registry()
        _get_service_registry()
        _get_rule_set_manager()

        _reset_model_registry()
        _reset_service_registry()
        _reset_coordinator()
        _reset_rule_set_manager()
        _reset_container()

        # 역순 리셋
        _get_model_registry()
        _get_service_registry()
        _get_rule_set_manager()

        _reset_container()
        _reset_rule_set_manager()
        _reset_coordinator()
        _reset_service_registry()
        _reset_model_registry()

        # 다시 생성 가능
        _get_model_registry()
        _get_service_registry()
        _get_rule_set_manager()

        result.ok("12-5 전체 리셋 순서 안전성 (순방향/역순/재생성)")
    except Exception as e:
        result.fail("12-5 리셋 순서", str(e))
    finally:
        _reset_model_registry()
        _reset_service_registry()
        _reset_coordinator()
        _reset_rule_set_manager()
        _reset_container()


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - registry 모듈 통합 테스트")
    print("=" * 60)

    result = TestResult()

    test_import_integrity(result)                  # [1] 8개
    test_all_exports(result)                       # [2] 5개
    test_enum_cross_reference(result)              # [3] 5개
    test_model_registry_workflow(result)            # [4] 6개
    test_service_registry_workflow(result)          # [5] 6개
    test_dependency_injector_workflow(result)       # [6] 8개
    test_pipeline_coordinator_workflow(result)      # [7] 6개
    test_rule_set_manager_workflow(result)          # [8] 6개
    test_model_service_integration(result)          # [9] 6개
    test_di_registry_integration(result)            # [10] 6개
    test_full_pipeline_simulation(result)           # [11] 8개
    test_singleton_isolation_and_threads(result)    # [12] 5개

    result.summary()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
