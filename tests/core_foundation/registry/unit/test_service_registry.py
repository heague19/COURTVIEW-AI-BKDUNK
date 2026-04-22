# -*- coding: utf-8 -*-
"""registry/service_registry.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from core_foundation.registry.service_registry import (
    MAX_DEPENDENCY_DEPTH,
    MAX_SERVICES,
    MAX_TAGS_PER_SERVICE,
    ServiceDescriptor,
    ServiceLifecycle,
    ServiceRegistry,
)


@pytest.fixture(autouse=True)
def reset_registry():
    ServiceRegistry.reset()
    yield
    ServiceRegistry.reset()


# =============================================================================
# ServiceLifecycle 검증
# =============================================================================

class TestServiceLifecycle:
    def test_member_count(self):
        assert len(ServiceLifecycle) == 3

    def test_values(self):
        assert ServiceLifecycle.SINGLETON.value == "singleton"
        assert ServiceLifecycle.TRANSIENT.value == "transient"
        assert ServiceLifecycle.INSTANCE.value == "instance"

    def test_to_korean(self):
        assert ServiceLifecycle.SINGLETON.to_korean() == "싱글턴"
        assert ServiceLifecycle.TRANSIENT.to_korean() == "일회성"
        assert ServiceLifecycle.INSTANCE.to_korean() == "인스턴스"


# =============================================================================
# ServiceDescriptor 검증
# =============================================================================

class TestServiceDescriptor:
    def test_slots(self):
        assert hasattr(ServiceDescriptor, "__slots__")

    def test_creation(self):
        d = ServiceDescriptor(
            name="test",
            lifecycle=ServiceLifecycle.SINGLETON,
        )
        assert d.name == "test"
        assert d.lifecycle == ServiceLifecycle.SINGLETON
        assert d.is_resolved is False

    def test_is_resolved(self):
        d = ServiceDescriptor(
            name="test",
            lifecycle=ServiceLifecycle.INSTANCE,
            instance=object(),
        )
        assert d.is_resolved is True

    def test_repr(self):
        d = ServiceDescriptor(
            name="my_service",
            lifecycle=ServiceLifecycle.TRANSIENT,
        )
        text = repr(d)
        assert "my_service" in text
        assert "transient" in text
        assert "resolved=False" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        r1 = ServiceRegistry.get_instance()
        r2 = ServiceRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = ServiceRegistry.get_instance()
        ServiceRegistry.reset()
        r2 = ServiceRegistry.get_instance()
        assert r1 is not r2


# =============================================================================
# 인스턴스 등록
# =============================================================================

class TestRegisterInstance:
    def test_register_and_resolve(self):
        reg = ServiceRegistry.get_instance()
        obj = {"key": "value"}
        assert reg.register_instance("config", obj) is True
        assert reg.resolve("config") is obj

    def test_register_with_tags(self):
        reg = ServiceRegistry.get_instance()
        obj = object()
        reg.register_instance("svc", obj, tags=["core", "infra"])
        desc = reg.get_descriptor("svc")
        assert desc is not None
        assert "core" in desc.tags
        assert "infra" in desc.tags

    def test_register_with_description(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("svc", object(), description="테스트 서비스")
        desc = reg.get_descriptor("svc")
        assert desc is not None
        assert desc.description == "테스트 서비스"


# =============================================================================
# Singleton 팩토리 등록
# =============================================================================

class TestRegisterSingleton:
    def test_lazy_creation(self):
        reg = ServiceRegistry.get_instance()
        call_count = [0]

        def create_service():
            call_count[0] += 1
            return {"created": True}

        reg.register_singleton("lazy", create_service)

        # 등록 시점에서는 생성 안 됨
        assert call_count[0] == 0

        # 첫 resolve에서 생성
        result = reg.resolve("lazy")
        assert call_count[0] == 1
        assert result["created"] is True

        # 두 번째 resolve에서 캐시 반환
        result2 = reg.resolve("lazy")
        assert call_count[0] == 1
        assert result2 is result

    def test_factory_with_dependencies(self):
        reg = ServiceRegistry.get_instance()

        reg.register_instance("db", {"type": "sqlite"})

        def create_repo(db: dict) -> dict:
            return {"repo": True, "db": db}

        reg.register_singleton(
            "repo", create_repo, dependencies=["db"],
        )

        repo = reg.resolve("repo")
        assert repo["repo"] is True
        assert repo["db"]["type"] == "sqlite"


# =============================================================================
# Transient 등록
# =============================================================================

class TestRegisterTransient:
    def test_new_instance_each_time(self):
        reg = ServiceRegistry.get_instance()

        def create_worker():
            return {"id": id(object())}

        reg.register_transient("worker", create_worker)

        w1 = reg.resolve("worker")
        w2 = reg.resolve("worker")
        assert w1 is not w2

    def test_transient_with_dependencies(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("config", {"debug": True})

        def create_handler(config: dict) -> dict:
            return {"handler": True, "config": config}

        reg.register_transient(
            "handler", create_handler, dependencies=["config"],
        )

        h = reg.resolve("handler")
        assert h["handler"] is True
        assert h["config"]["debug"] is True


# =============================================================================
# 등록 해제
# =============================================================================

class TestUnregister:
    def test_unregister(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("tmp", object())
        assert reg.unregister("tmp") is True
        assert reg.has("tmp") is False

    def test_unregister_nonexistent(self):
        reg = ServiceRegistry.get_instance()
        assert reg.unregister("missing") is False


# =============================================================================
# 조회
# =============================================================================

class TestResolve:
    def test_resolve_missing_raises(self):
        reg = ServiceRegistry.get_instance()
        with pytest.raises(KeyError, match="미등록 서비스"):
            reg.resolve("nonexistent")

    def test_resolve_optional_missing(self):
        reg = ServiceRegistry.get_instance()
        assert reg.resolve_optional("missing") is None

    def test_resolve_optional_exists(self):
        reg = ServiceRegistry.get_instance()
        obj = {"value": 42}
        reg.register_instance("svc", obj)
        assert reg.resolve_optional("svc") is obj

    def test_resolve_optional_factory_failure(self):
        reg = ServiceRegistry.get_instance()

        def broken_factory():
            raise RuntimeError("실패")

        reg.register_singleton("broken", broken_factory)
        assert reg.resolve_optional("broken") is None

    def test_has(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("exists", object())
        assert reg.has("exists") is True
        assert reg.has("missing") is False

    def test_get_descriptor_defensive_copy(self):
        """get_descriptor 반환값 수정이 원본에 영향 안 줌."""
        reg = ServiceRegistry.get_instance()
        reg.register_instance("svc", object(), tags=["a", "b"])

        desc = reg.get_descriptor("svc")
        assert desc is not None
        desc.tags.append("c")

        # 원본 변경 없음
        desc2 = reg.get_descriptor("svc")
        assert desc2 is not None
        assert "c" not in desc2.tags

    def test_get_descriptor_missing(self):
        reg = ServiceRegistry.get_instance()
        assert reg.get_descriptor("missing") is None


# =============================================================================
# 태그 조회
# =============================================================================

class TestResolveByTag:
    def test_resolve_by_tag(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("det1", {"type": "ball"}, tags=["detector"])
        reg.register_instance("det2", {"type": "player"}, tags=["detector"])
        reg.register_instance("other", {"type": "config"}, tags=["config"])

        detectors = reg.resolve_by_tag("detector")
        assert len(detectors) == 2

    def test_resolve_by_tag_empty(self):
        reg = ServiceRegistry.get_instance()
        assert reg.resolve_by_tag("nonexistent") == []

    def test_tags_truncated(self):
        """태그 수가 MAX_TAGS_PER_SERVICE 초과 시 절삭."""
        reg = ServiceRegistry.get_instance()
        tags = [f"tag_{i}" for i in range(MAX_TAGS_PER_SERVICE + 5)]
        reg.register_instance("svc", object(), tags=tags)

        desc = reg.get_descriptor("svc")
        assert desc is not None
        assert len(desc.tags) == MAX_TAGS_PER_SERVICE


# =============================================================================
# 의존성 검증
# =============================================================================

class TestDependencyValidation:
    def test_no_errors(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("a", object())
        reg.register_singleton("b", lambda a: a, dependencies=["a"])

        errors = reg.validate_dependencies()
        assert len(errors) == 0

    def test_missing_dependency(self):
        reg = ServiceRegistry.get_instance()
        reg.register_singleton(
            "svc", lambda: None, dependencies=["missing"],
        )

        errors = reg.validate_dependencies()
        assert len(errors) >= 1
        assert any("미등록 의존성" in e for e in errors)

    def test_circular_dependency(self):
        reg = ServiceRegistry.get_instance()
        reg.register_singleton("a", lambda b: b, dependencies=["b"])
        reg.register_singleton("b", lambda a: a, dependencies=["a"])

        errors = reg.validate_dependencies()
        assert any("순환 의존" in e for e in errors)

    def test_circular_resolve_raises(self):
        reg = ServiceRegistry.get_instance()
        reg.register_singleton("a", lambda b: b, dependencies=["b"])
        reg.register_singleton("b", lambda a: a, dependencies=["a"])

        with pytest.raises(RuntimeError, match="순환 의존"):
            reg.resolve("a")

    def test_deep_dependency_chain(self):
        """정상 깊이의 의존성 체인은 정상 동작."""
        reg = ServiceRegistry.get_instance()

        # 5단계 체인: svc_0 → svc_1 → svc_2 → svc_3 → svc_4
        reg.register_instance("svc_0", {"level": 0})
        for i in range(1, 5):
            dep = f"svc_{i - 1}"

            def factory(level=i, **kwargs):
                return {"level": level, **kwargs}

            reg.register_singleton(
                f"svc_{i}", factory, dependencies=[dep],
            )

        result = reg.resolve("svc_4")
        assert result["level"] == 4

    def test_missing_dependency_resolve_raises(self):
        reg = ServiceRegistry.get_instance()
        reg.register_singleton(
            "svc", lambda missing: missing, dependencies=["missing"],
        )

        with pytest.raises(KeyError, match="미등록 의존성"):
            reg.resolve("svc")


# =============================================================================
# 등록 덮어쓰기 및 한도
# =============================================================================

class TestRegistrationLimits:
    def test_overwrite(self):
        """동일 이름 재등록 시 덮어쓰기."""
        reg = ServiceRegistry.get_instance()
        reg.register_instance("svc", {"v": 1})
        reg.register_instance("svc", {"v": 2})

        result = reg.resolve("svc")
        assert result["v"] == 2
        assert reg.service_count == 1

    def test_max_services_limit(self):
        reg = ServiceRegistry.get_instance()

        for i in range(MAX_SERVICES):
            reg.register_instance(f"svc_{i}", i)

        # 한도 초과
        assert reg.register_instance("overflow", -1) is False
        assert reg.service_count == MAX_SERVICES

    def test_factory_failure_raises(self):
        reg = ServiceRegistry.get_instance()

        def bad_factory():
            raise ValueError("초기화 실패")

        reg.register_singleton("bad", bad_factory)

        with pytest.raises(RuntimeError, match="서비스 생성 실패"):
            reg.resolve("bad")


# =============================================================================
# 관리
# =============================================================================

class TestManagement:
    def test_service_count(self):
        reg = ServiceRegistry.get_instance()
        assert reg.service_count == 0

        reg.register_instance("a", 1)
        reg.register_instance("b", 2)
        assert reg.service_count == 2

    def test_service_names(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("alpha", 1)
        reg.register_instance("beta", 2)
        names = reg.service_names
        assert "alpha" in names
        assert "beta" in names

    def test_clear(self):
        reg = ServiceRegistry.get_instance()
        reg.register_instance("a", 1)
        reg.register_instance("b", 2)
        assert reg.clear() == 2
        assert reg.service_count == 0

    def test_repr(self):
        reg = ServiceRegistry.get_instance()
        assert "services=" in repr(reg)


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_register_and_resolve(self):
        reg = ServiceRegistry.get_instance()
        errors: list[Exception] = []

        def register_services(prefix: str):
            try:
                for i in range(20):
                    name = f"{prefix}_{i}"
                    reg.register_instance(name, {"id": name})
            except Exception as e:
                errors.append(e)

        def resolve_services(prefix: str):
            try:
                for i in range(20):
                    name = f"{prefix}_{i}"
                    reg.resolve_optional(name)
            except Exception as e:
                errors.append(e)

        threads = []
        for t in range(5):
            threads.append(
                threading.Thread(target=register_services, args=(f"t{t}",))
            )
            threads.append(
                threading.Thread(target=resolve_services, args=(f"t{t}",))
            )

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_services(self):
        assert MAX_SERVICES == 200

    def test_max_dependency_depth(self):
        assert MAX_DEPENDENCY_DEPTH == 20

    def test_max_tags(self):
        assert MAX_TAGS_PER_SERVICE == 10


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.registry.service_registry as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.registry.service_registry as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.registry.service_registry as mod
        assert mod.__version__ == "1.0.0"
