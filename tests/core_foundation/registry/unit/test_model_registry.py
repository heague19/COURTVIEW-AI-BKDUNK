# -*- coding: utf-8 -*-
"""registry/model_registry.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from core_foundation.registry.model_registry import (
    DEFAULT_VRAM_BUDGET_MB,
    MAX_MODELS,
    MIN_VRAM_BUDGET_MB,
    ModelBackend,
    ModelInfo,
    ModelRegistry,
    ModelStatus,
)


@pytest.fixture(autouse=True)
def reset_registry():
    ModelRegistry.reset()
    yield
    ModelRegistry.reset()


# =============================================================================
# ModelStatus 검증
# =============================================================================

class TestModelStatus:
    def test_member_count(self):
        assert len(ModelStatus) == 5

    def test_values(self):
        assert ModelStatus.REGISTERED.value == "registered"
        assert ModelStatus.LOADING.value == "loading"
        assert ModelStatus.LOADED.value == "loaded"
        assert ModelStatus.UNLOADING.value == "unloading"
        assert ModelStatus.ERROR.value == "error"

    def test_to_korean(self):
        assert ModelStatus.REGISTERED.to_korean() == "등록됨"
        assert ModelStatus.LOADED.to_korean() == "로드 완료"
        assert ModelStatus.ERROR.to_korean() == "오류"


# =============================================================================
# ModelBackend 검증
# =============================================================================

class TestModelBackend:
    def test_member_count(self):
        assert len(ModelBackend) == 4

    def test_values(self):
        assert ModelBackend.PYTORCH.value == "pytorch"
        assert ModelBackend.ONNX.value == "onnx"
        assert ModelBackend.TENSORRT.value == "tensorrt"
        assert ModelBackend.CUSTOM.value == "custom"

    def test_to_korean(self):
        assert ModelBackend.TENSORRT.to_korean() == "TensorRT"
        assert ModelBackend.CUSTOM.to_korean() == "커스텀"


# =============================================================================
# ModelInfo 검증
# =============================================================================

class TestModelInfo:
    def test_slots(self):
        assert hasattr(ModelInfo, "__slots__")

    def test_creation(self):
        info = ModelInfo(
            name="yolov8x-pose",
            version="8.0.0",
            backend=ModelBackend.TENSORRT,
            vram_mb=800.0,
        )
        assert info.name == "yolov8x-pose"
        assert info.version == "8.0.0"
        assert info.vram_mb == 800.0

    def test_is_loaded_false(self):
        info = ModelInfo(
            name="test", version="1.0", backend=ModelBackend.PYTORCH,
        )
        assert info.is_loaded is False

    def test_is_loaded_true(self):
        info = ModelInfo(
            name="test", version="1.0", backend=ModelBackend.PYTORCH,
            status=ModelStatus.LOADED, instance=object(),
        )
        assert info.is_loaded is True

    def test_repr(self):
        info = ModelInfo(
            name="yolo", version="8.0",
            backend=ModelBackend.TENSORRT, vram_mb=800.0,
        )
        text = repr(info)
        assert "yolo" in text
        assert "v8.0" in text
        assert "tensorrt" in text
        assert "800MB" in text


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        r1 = ModelRegistry.get_instance()
        r2 = ModelRegistry.get_instance()
        assert r1 is r2

    def test_reset(self):
        r1 = ModelRegistry.get_instance()
        ModelRegistry.reset()
        r2 = ModelRegistry.get_instance()
        assert r1 is not r2


# =============================================================================
# 모델 등록
# =============================================================================

class TestRegistration:
    def test_register(self):
        reg = ModelRegistry.get_instance()
        result = reg.register(
            "yolo", "8.0", ModelBackend.TENSORRT, vram_mb=800.0,
        )
        assert result is True
        assert reg.model_count == 1

    def test_register_with_tags(self):
        reg = ModelRegistry.get_instance()
        reg.register(
            "yolo", "8.0", ModelBackend.TENSORRT,
            tags=["detection", "pose"],
        )
        info = reg.get("yolo")
        assert info is not None
        assert "detection" in info.tags

    def test_register_overwrite(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH)
        reg.register("model", "2.0", ModelBackend.ONNX)

        info = reg.get("model")
        assert info is not None
        assert info.version == "2.0"
        assert info.backend == ModelBackend.ONNX
        assert reg.model_count == 1

    def test_register_max_limit(self):
        reg = ModelRegistry.get_instance()
        for i in range(MAX_MODELS):
            reg.register(f"model_{i}", "1.0", ModelBackend.PYTORCH)

        result = reg.register("overflow", "1.0", ModelBackend.PYTORCH)
        assert result is False

    def test_unregister(self):
        reg = ModelRegistry.get_instance()
        reg.register("tmp", "1.0", ModelBackend.PYTORCH)
        assert reg.unregister("tmp") is True
        assert reg.model_count == 0

    def test_unregister_nonexistent(self):
        reg = ModelRegistry.get_instance()
        assert reg.unregister("missing") is False


# =============================================================================
# 모델 로드/언로드
# =============================================================================

class TestLoadUnload:
    def test_load_success(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH, vram_mb=500.0)

        def loader(info: ModelInfo):
            return {"loaded": True, "name": info.name}

        reg.set_loader(loader)

        result = reg.load("model")
        assert result is True

        info = reg.get("model")
        assert info is not None
        assert info.is_loaded is True
        assert info.instance["loaded"] is True
        assert info.load_time_sec > 0

    def test_load_already_loaded(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH)
        reg.set_loader(lambda info: object())

        reg.load("model")
        result = reg.load("model")  # 이미 로드됨
        assert result is True

    def test_load_missing_raises(self):
        reg = ModelRegistry.get_instance()
        reg.set_loader(lambda info: object())

        with pytest.raises(KeyError, match="미등록 모델"):
            reg.load("nonexistent")

    def test_load_no_loader_raises(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH)

        with pytest.raises(RuntimeError, match="로더 미설정"):
            reg.load("model")

    def test_load_vram_exceeded_raises(self):
        reg = ModelRegistry.get_instance()
        reg.set_vram_budget(2000.0)  # 2GB 예산
        reg.set_loader(lambda info: object())

        reg.register("big", "1.0", ModelBackend.TENSORRT, vram_mb=1500.0)
        reg.load("big")

        reg.register("too_big", "1.0", ModelBackend.TENSORRT, vram_mb=1000.0)
        with pytest.raises(RuntimeError, match="VRAM 부족"):
            reg.load("too_big")

    def test_load_failure(self):
        reg = ModelRegistry.get_instance()
        reg.register("bad", "1.0", ModelBackend.PYTORCH)

        def bad_loader(info: ModelInfo):
            raise RuntimeError("로드 실패")

        reg.set_loader(bad_loader)

        result = reg.load("bad")
        assert result is False

        info = reg.get("bad")
        assert info is not None
        assert info.status == ModelStatus.ERROR
        assert "RuntimeError" in info.error_message

    def test_unload(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH, vram_mb=500.0)
        reg.set_loader(lambda info: object())
        reg.load("model")

        unload_called = [False]

        def unloader(info: ModelInfo, instance: object):
            unload_called[0] = True

        reg.set_unloader(unloader)

        result = reg.unload("model")
        assert result is True
        assert unload_called[0] is True

        info = reg.get("model")
        assert info is not None
        assert info.is_loaded is False
        assert info.status == ModelStatus.REGISTERED

    def test_unload_not_loaded(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH)
        assert reg.unload("model") is False

    def test_unload_nonexistent(self):
        reg = ModelRegistry.get_instance()
        assert reg.unload("missing") is False

    def test_unregister_loaded_model(self):
        """로드된 모델 등록 해제 시 자동 언로드."""
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH, vram_mb=500.0)
        reg.set_loader(lambda info: object())
        reg.load("model")

        assert reg.unregister("model") is True
        assert reg.model_count == 0


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get(self):
        reg = ModelRegistry.get_instance()
        reg.register("model", "1.0", ModelBackend.PYTORCH)
        info = reg.get("model")
        assert info is not None
        assert info.name == "model"

    def test_get_missing(self):
        reg = ModelRegistry.get_instance()
        assert reg.get("missing") is None

    def test_get_by_tag(self):
        reg = ModelRegistry.get_instance()
        reg.register("yolo", "8.0", ModelBackend.TENSORRT, tags=["detection"])
        reg.register("vitpose", "1.0", ModelBackend.TENSORRT, tags=["pose"])
        reg.register("cv-ball", "1.0", ModelBackend.CUSTOM, tags=["detection"])

        detectors = reg.get_by_tag("detection")
        assert len(detectors) == 2

    def test_get_loaded(self):
        reg = ModelRegistry.get_instance()
        reg.set_loader(lambda info: object())

        reg.register("a", "1.0", ModelBackend.PYTORCH)
        reg.register("b", "1.0", ModelBackend.PYTORCH)
        reg.load("a")

        loaded = reg.get_loaded()
        assert len(loaded) == 1
        assert loaded[0].name == "a"

    def test_model_names(self):
        reg = ModelRegistry.get_instance()
        reg.register("alpha", "1.0", ModelBackend.PYTORCH)
        reg.register("beta", "1.0", ModelBackend.ONNX)
        names = reg.model_names
        assert "alpha" in names
        assert "beta" in names


# =============================================================================
# VRAM 관리
# =============================================================================

class TestVRAM:
    def test_default_budget(self):
        reg = ModelRegistry.get_instance()
        assert reg.vram_budget_mb == DEFAULT_VRAM_BUDGET_MB

    def test_set_budget(self):
        reg = ModelRegistry.get_instance()
        reg.set_vram_budget(8000.0)
        assert reg.vram_budget_mb == 8000.0

    def test_set_budget_minimum(self):
        reg = ModelRegistry.get_instance()
        reg.set_vram_budget(100.0)  # 최소값 미만
        assert reg.vram_budget_mb == MIN_VRAM_BUDGET_MB

    def test_vram_used(self):
        reg = ModelRegistry.get_instance()
        reg.set_loader(lambda info: object())

        reg.register("a", "1.0", ModelBackend.TENSORRT, vram_mb=800.0)
        reg.register("b", "1.0", ModelBackend.TENSORRT, vram_mb=600.0)

        reg.load("a")
        assert reg.vram_used_mb == pytest.approx(800.0)

        reg.load("b")
        assert reg.vram_used_mb == pytest.approx(1400.0)

    def test_vram_available(self):
        reg = ModelRegistry.get_instance()
        reg.set_vram_budget(2000.0)
        reg.set_loader(lambda info: object())

        reg.register("a", "1.0", ModelBackend.TENSORRT, vram_mb=800.0)
        reg.load("a")

        assert reg.vram_available_mb == pytest.approx(1200.0)

    def test_vram_freed_on_unload(self):
        reg = ModelRegistry.get_instance()
        reg.set_vram_budget(2000.0)
        reg.set_loader(lambda info: object())

        reg.register("model", "1.0", ModelBackend.TENSORRT, vram_mb=800.0)
        reg.load("model")
        assert reg.vram_used_mb == pytest.approx(800.0)

        reg.unload("model")
        assert reg.vram_used_mb == pytest.approx(0.0)


# =============================================================================
# 관리
# =============================================================================

class TestManagement:
    def test_model_count(self):
        reg = ModelRegistry.get_instance()
        assert reg.model_count == 0
        reg.register("a", "1.0", ModelBackend.PYTORCH)
        assert reg.model_count == 1

    def test_loaded_count(self):
        reg = ModelRegistry.get_instance()
        reg.set_loader(lambda info: object())
        reg.register("a", "1.0", ModelBackend.PYTORCH)
        reg.register("b", "1.0", ModelBackend.PYTORCH)
        reg.load("a")

        assert reg.loaded_count == 1

    def test_clear(self):
        reg = ModelRegistry.get_instance()
        reg.set_loader(lambda info: object())
        reg.register("a", "1.0", ModelBackend.PYTORCH)
        reg.register("b", "1.0", ModelBackend.PYTORCH)
        reg.load("a")

        count = reg.clear()
        assert count == 2
        assert reg.model_count == 0

    def test_repr(self):
        reg = ModelRegistry.get_instance()
        text = repr(reg)
        assert "models=" in text
        assert "loaded=" in text
        assert "vram=" in text


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_register(self):
        reg = ModelRegistry.get_instance()
        errors: list[Exception] = []

        def register_models(prefix: str):
            try:
                for i in range(10):
                    reg.register(
                        f"{prefix}_{i}", "1.0", ModelBackend.PYTORCH,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_models, args=(f"t{t}",))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert reg.model_count == 40


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_models(self):
        assert MAX_MODELS == 50

    def test_default_vram(self):
        assert DEFAULT_VRAM_BUDGET_MB == 14_000.0

    def test_min_vram(self):
        assert MIN_VRAM_BUDGET_MB == 1_000.0


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.registry.model_registry as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.registry.model_registry as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.registry.model_registry as mod
        assert mod.__version__ == "1.0.0"
