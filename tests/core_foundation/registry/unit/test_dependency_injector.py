# -*- coding: utf-8 -*-
"""registry/dependency_injector.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from core_foundation.registry.dependency_injector import (
    MAX_BINDINGS,
    MAX_RESOLVE_DEPTH,
    MAX_SCOPES,
    Binding,
    DependencyInjector,
    Scope,
)


@pytest.fixture(autouse=True)
def reset_injector():
    DependencyInjector.reset()
    yield
    DependencyInjector.reset()


# =============================================================================
# Scope 검증
# =============================================================================

class TestScope:
    def test_member_count(self):
        assert len(Scope) == 3

    def test_values(self):
        assert Scope.SINGLETON.value == "singleton"
        assert Scope.TRANSIENT.value == "transient"
        assert Scope.SCOPED.value == "scoped"

    def test_to_korean(self):
        assert Scope.SINGLETON.to_korean() == "싱글턴"
        assert Scope.TRANSIENT.to_korean() == "일회성"
        assert Scope.SCOPED.to_korean() == "스코프"


# =============================================================================
# Binding 검증
# =============================================================================

class TestBinding:
    def test_slots(self):
        assert hasattr(Binding, "__slots__")

    def test_creation(self):
        b = Binding(key="config", scope=Scope.SINGLETON)
        assert b.key == "config"
        assert b.is_resolved is False

    def test_is_resolved(self):
        b = Binding(key="config", scope=Scope.SINGLETON, instance=object())
        assert b.is_resolved is True

    def test_repr(self):
        b = Binding(key="svc", scope=Scope.TRANSIENT)
        text = repr(b)
        assert "svc" in text
        assert "transient" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        d1 = DependencyInjector.get_instance()
        d2 = DependencyInjector.get_instance()
        assert d1 is d2

    def test_reset(self):
        d1 = DependencyInjector.get_instance()
        DependencyInjector.reset()
        d2 = DependencyInjector.get_instance()
        assert d1 is not d2


# =============================================================================
# 인스턴스 바인딩
# =============================================================================

class TestBindInstance:
    def test_bind_and_resolve(self):
        di = DependencyInjector.get_instance()
        obj = {"key": "value"}
        di.bind_instance("config", obj)
        assert di.resolve("config") is obj

    def test_bind_with_description(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("svc", object(), description="테스트")
        binding = di.get_binding("svc")
        assert binding is not None
        assert binding.description == "테스트"


# =============================================================================
# Singleton 바인딩
# =============================================================================

class TestBindSingleton:
    def test_lazy_creation(self):
        di = DependencyInjector.get_instance()
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"created": True}

        di.bind_singleton("lazy", factory)
        assert call_count[0] == 0

        result = di.resolve("lazy")
        assert call_count[0] == 1
        assert result["created"] is True

        # 캐시 반환
        result2 = di.resolve("lazy")
        assert call_count[0] == 1
        assert result2 is result

    def test_with_dependencies(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("db", {"type": "sqlite"})

        def create_repo(db: dict) -> dict:
            return {"repo": True, "db": db}

        di.bind_singleton("repo", create_repo, dependencies=["db"])
        repo = di.resolve("repo")
        assert repo["repo"] is True
        assert repo["db"]["type"] == "sqlite"


# =============================================================================
# Transient 바인딩
# =============================================================================

class TestBindTransient:
    def test_new_instance_each_time(self):
        di = DependencyInjector.get_instance()

        def factory():
            return object()

        di.bind_transient("worker", factory)
        w1 = di.resolve("worker")
        w2 = di.resolve("worker")
        assert w1 is not w2


# =============================================================================
# Scoped 바인딩
# =============================================================================

class TestBindScoped:
    def test_scoped_in_same_scope(self):
        """같은 스코프 내에서는 동일 인스턴스."""
        di = DependencyInjector.get_instance()
        di.bind_scoped("handler", lambda: object())
        di.create_scope("req1")

        h1 = di.resolve_in_scope("req1", "handler")
        h2 = di.resolve_in_scope("req1", "handler")
        assert h1 is h2

    def test_scoped_in_different_scope(self):
        """다른 스코프에서는 별개 인스턴스."""
        di = DependencyInjector.get_instance()
        di.bind_scoped("handler", lambda: object())
        di.create_scope("req1")
        di.create_scope("req2")

        h1 = di.resolve_in_scope("req1", "handler")
        h2 = di.resolve_in_scope("req2", "handler")
        assert h1 is not h2

    def test_singleton_in_scope_is_global(self):
        """스코프 내 Singleton 해석은 글로벌 캐시 사용."""
        di = DependencyInjector.get_instance()
        di.bind_singleton("global_svc", lambda: {"global": True})
        di.create_scope("req1")
        di.create_scope("req2")

        g1 = di.resolve_in_scope("req1", "global_svc")
        g2 = di.resolve_in_scope("req2", "global_svc")
        assert g1 is g2

    def test_resolve_in_missing_scope(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("svc", object())

        with pytest.raises(KeyError, match="미등록 스코프"):
            di.resolve_in_scope("missing", "svc")

    def test_resolve_missing_key_in_scope(self):
        di = DependencyInjector.get_instance()
        di.create_scope("req1")

        with pytest.raises(KeyError, match="미등록 바인딩"):
            di.resolve_in_scope("req1", "missing")


# =============================================================================
# 스코프 관리
# =============================================================================

class TestScopeManagement:
    def test_create_scope(self):
        di = DependencyInjector.get_instance()
        assert di.create_scope("s1") is True
        assert di.scope_count == 1

    def test_create_scope_duplicate(self):
        di = DependencyInjector.get_instance()
        di.create_scope("s1")
        assert di.create_scope("s1") is False

    def test_create_scope_max(self):
        di = DependencyInjector.get_instance()
        for i in range(MAX_SCOPES):
            di.create_scope(f"s{i}")

        assert di.create_scope("overflow") is False

    def test_destroy_scope(self):
        di = DependencyInjector.get_instance()
        di.create_scope("s1")
        assert di.destroy_scope("s1") is True
        assert di.scope_count == 0

    def test_destroy_scope_nonexistent(self):
        di = DependencyInjector.get_instance()
        assert di.destroy_scope("missing") is False

    def test_scope_ids(self):
        di = DependencyInjector.get_instance()
        di.create_scope("a")
        di.create_scope("b")
        ids = di.scope_ids
        assert "a" in ids
        assert "b" in ids


# =============================================================================
# 해제 및 조회
# =============================================================================

class TestUnbindAndQuery:
    def test_unbind(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("tmp", object())
        assert di.unbind("tmp") is True
        assert di.has("tmp") is False

    def test_unbind_nonexistent(self):
        di = DependencyInjector.get_instance()
        assert di.unbind("missing") is False

    def test_has(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("svc", object())
        assert di.has("svc") is True
        assert di.has("missing") is False

    def test_resolve_missing_raises(self):
        di = DependencyInjector.get_instance()
        with pytest.raises(KeyError, match="미등록 바인딩"):
            di.resolve("nonexistent")

    def test_resolve_optional_missing(self):
        di = DependencyInjector.get_instance()
        assert di.resolve_optional("missing") is None

    def test_resolve_optional_factory_failure(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("broken", lambda: (_ for _ in ()).throw(RuntimeError("실패")))
        assert di.resolve_optional("broken") is None

    def test_get_binding_defensive_copy(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("svc", lambda: None, dependencies=["a"])

        binding = di.get_binding("svc")
        assert binding is not None
        binding.dependencies.append("b")

        binding2 = di.get_binding("svc")
        assert binding2 is not None
        assert "b" not in binding2.dependencies

    def test_get_binding_missing(self):
        di = DependencyInjector.get_instance()
        assert di.get_binding("missing") is None


# =============================================================================
# 순환 의존
# =============================================================================

class TestCircularDependency:
    def test_circular_raises(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("a", lambda b: b, dependencies=["b"])
        di.bind_singleton("b", lambda a: a, dependencies=["a"])

        with pytest.raises(RuntimeError, match="순환 의존"):
            di.resolve("a")

    def test_self_dependency_raises(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("self_dep", lambda self_dep: self_dep, dependencies=["self_dep"])

        with pytest.raises(RuntimeError, match="순환 의존"):
            di.resolve("self_dep")

    def test_missing_dependency_raises(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("svc", lambda missing: missing, dependencies=["missing"])

        with pytest.raises(KeyError, match="미등록 바인딩"):
            di.resolve("svc")

    def test_factory_failure_raises(self):
        di = DependencyInjector.get_instance()
        di.bind_singleton("bad", lambda: (_ for _ in ()).throw(ValueError("실패")))

        with pytest.raises(RuntimeError, match="인스턴스 생성 실패"):
            di.resolve("bad")


# =============================================================================
# 등록 한도
# =============================================================================

class TestLimits:
    def test_overwrite(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("svc", {"v": 1})
        di.bind_instance("svc", {"v": 2})
        assert di.resolve("svc")["v"] == 2
        assert di.binding_count == 1

    def test_max_bindings(self):
        di = DependencyInjector.get_instance()
        for i in range(MAX_BINDINGS):
            di.bind_instance(f"b_{i}", i)

        assert di.bind_instance("overflow", -1) is False


# =============================================================================
# 관리
# =============================================================================

class TestManagement:
    def test_binding_count(self):
        di = DependencyInjector.get_instance()
        assert di.binding_count == 0
        di.bind_instance("a", 1)
        assert di.binding_count == 1

    def test_binding_keys(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("x", 1)
        di.bind_instance("y", 2)
        keys = di.binding_keys
        assert "x" in keys and "y" in keys

    def test_clear(self):
        di = DependencyInjector.get_instance()
        di.bind_instance("a", 1)
        di.create_scope("s1")
        count = di.clear()
        assert count == 1
        assert di.binding_count == 0
        assert di.scope_count == 0

    def test_repr(self):
        di = DependencyInjector.get_instance()
        text = repr(di)
        assert "bindings=" in text
        assert "scopes=" in text


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_bind_and_resolve(self):
        di = DependencyInjector.get_instance()
        errors: list[Exception] = []

        def bind_and_resolve(prefix: str):
            try:
                for i in range(20):
                    key = f"{prefix}_{i}"
                    di.bind_instance(key, {"id": key})
                    di.resolve(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=bind_and_resolve, args=(f"t{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_bindings(self):
        assert MAX_BINDINGS == 300

    def test_max_resolve_depth(self):
        assert MAX_RESOLVE_DEPTH == 25

    def test_max_scopes(self):
        assert MAX_SCOPES == 20


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.registry.dependency_injector as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.registry.dependency_injector as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.registry.dependency_injector as mod
        assert mod.__version__ == "1.0.0"
