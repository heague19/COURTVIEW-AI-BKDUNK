# -*- coding: utf-8 -*-
"""registry/pipeline_coordinator.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading
from typing import Any

import pytest

from core_foundation.registry.pipeline_coordinator import (
    MAX_PIPELINES,
    MAX_STAGES_PER_PIPELINE,
    PipelineCoordinator,
    PipelineResult,
    StageDefinition,
    StageResult,
    StageStatus,
)


@pytest.fixture(autouse=True)
def reset_coordinator():
    PipelineCoordinator.reset()
    yield
    PipelineCoordinator.reset()


# =============================================================================
# StageStatus 검증
# =============================================================================

class TestStageStatus:
    def test_member_count(self):
        assert len(StageStatus) == 5

    def test_values(self):
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"

    def test_to_korean(self):
        assert StageStatus.PENDING.to_korean() == "대기"
        assert StageStatus.RUNNING.to_korean() == "실행 중"
        assert StageStatus.COMPLETED.to_korean() == "완료"

    def test_is_terminal(self):
        assert StageStatus.COMPLETED.is_terminal is True
        assert StageStatus.FAILED.is_terminal is True
        assert StageStatus.SKIPPED.is_terminal is True
        assert StageStatus.PENDING.is_terminal is False
        assert StageStatus.RUNNING.is_terminal is False


# =============================================================================
# StageResult 검증
# =============================================================================

class TestStageResult:
    def test_slots(self):
        assert hasattr(StageResult, "__slots__")

    def test_creation(self):
        r = StageResult("detect", StageStatus.COMPLETED, duration_sec=0.5)
        assert r.stage_name == "detect"
        assert r.duration_sec == pytest.approx(0.5)

    def test_repr(self):
        r = StageResult("detect", StageStatus.COMPLETED, duration_sec=1.234)
        assert "detect" in repr(r)
        assert "completed" in repr(r)


# =============================================================================
# StageDefinition 검증
# =============================================================================

class TestStageDefinition:
    def test_slots(self):
        assert hasattr(StageDefinition, "__slots__")

    def test_repr(self):
        s = StageDefinition("track", lambda ctx: None, dependencies=["detect"])
        assert "track" in repr(s)
        assert "detect" in repr(s)[repr(s).index("deps="):]


# =============================================================================
# PipelineResult 검증
# =============================================================================

class TestPipelineResult:
    def test_slots(self):
        assert hasattr(PipelineResult, "__slots__")

    def test_completed_count(self):
        stages = {
            "a": StageResult("a", StageStatus.COMPLETED),
            "b": StageResult("b", StageStatus.FAILED),
            "c": StageResult("c", StageStatus.COMPLETED),
        }
        result = PipelineResult("test", False, stages, 1.0)
        assert result.completed_count == 2

    def test_failed_stages(self):
        stages = {
            "a": StageResult("a", StageStatus.COMPLETED),
            "b": StageResult("b", StageStatus.FAILED),
        }
        result = PipelineResult("test", False, stages, 1.0)
        assert result.failed_stages == ["b"]

    def test_repr(self):
        result = PipelineResult("game", True, {}, 0.5)
        assert "game" in repr(result)
        assert "success=True" in repr(result)


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        c1 = PipelineCoordinator.get_instance()
        c2 = PipelineCoordinator.get_instance()
        assert c1 is c2

    def test_reset(self):
        c1 = PipelineCoordinator.get_instance()
        PipelineCoordinator.reset()
        c2 = PipelineCoordinator.get_instance()
        assert c1 is not c2


# =============================================================================
# 파이프라인 관리
# =============================================================================

class TestPipelineManagement:
    def test_create_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        assert coord.create_pipeline("game") is True
        assert coord.pipeline_count == 1

    def test_create_duplicate(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")
        assert coord.create_pipeline("game") is False

    def test_create_max_limit(self):
        coord = PipelineCoordinator.get_instance()
        for i in range(MAX_PIPELINES):
            coord.create_pipeline(f"pipe_{i}")
        assert coord.create_pipeline("overflow") is False

    def test_remove_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("tmp")
        assert coord.remove_pipeline("tmp") is True
        assert coord.pipeline_count == 0

    def test_remove_nonexistent(self):
        coord = PipelineCoordinator.get_instance()
        assert coord.remove_pipeline("missing") is False

    def test_has_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")
        assert coord.has_pipeline("game") is True
        assert coord.has_pipeline("missing") is False

    def test_pipeline_names(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("a")
        coord.create_pipeline("b")
        names = coord.pipeline_names
        assert "a" in names and "b" in names

    def test_clear(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("a")
        coord.create_pipeline("b")
        assert coord.clear() == 2
        assert coord.pipeline_count == 0


# =============================================================================
# 단계 관리
# =============================================================================

class TestStageManagement:
    def test_add_stage(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")

        stage = StageDefinition("detect", lambda ctx: None)
        assert coord.add_stage("game", stage) is True
        assert coord.stage_count("game") == 1

    def test_add_stage_missing_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        stage = StageDefinition("detect", lambda ctx: None)

        with pytest.raises(KeyError, match="미등록 파이프라인"):
            coord.add_stage("missing", stage)

    def test_add_duplicate_stage(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")

        coord.add_stage("game", StageDefinition("detect", lambda ctx: None))
        result = coord.add_stage("game", StageDefinition("detect", lambda ctx: None))
        assert result is False

    def test_add_stage_max_limit(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")

        for i in range(MAX_STAGES_PER_PIPELINE):
            coord.add_stage("game", StageDefinition(f"s{i}", lambda ctx: None))

        result = coord.add_stage(
            "game", StageDefinition("overflow", lambda ctx: None),
        )
        assert result is False

    def test_get_stages(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("game")
        coord.add_stage("game", StageDefinition("a", lambda ctx: None))
        coord.add_stage("game", StageDefinition("b", lambda ctx: None))

        stages = coord.get_stages("game")
        assert len(stages) == 2

    def test_get_stages_missing(self):
        coord = PipelineCoordinator.get_instance()
        with pytest.raises(KeyError):
            coord.get_stages("missing")

    def test_stage_count_missing(self):
        coord = PipelineCoordinator.get_instance()
        assert coord.stage_count("missing") == 0


# =============================================================================
# 파이프라인 실행
# =============================================================================

class TestExecution:
    def test_simple_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("simple")
        coord.add_stage("simple", StageDefinition(
            "step1", lambda ctx: {"result": 42},
        ))

        result = coord.execute("simple")
        assert result.success is True
        assert result.completed_count == 1
        assert result.stages["step1"].status == StageStatus.COMPLETED
        assert result.stages["step1"].output["result"] == 42

    def test_multi_stage_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("multi")

        coord.add_stage("multi", StageDefinition(
            "detect", lambda ctx: {"objects": 5},
        ))
        coord.add_stage("multi", StageDefinition(
            "track", lambda ctx: {"tracked": ctx["detect"]["objects"]},
            dependencies=["detect"],
        ))

        result = coord.execute("multi")
        assert result.success is True
        assert result.completed_count == 2
        assert result.stages["track"].output["tracked"] == 5

    def test_stage_failure_stops_dependents(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("fail")

        def failing(ctx: dict[str, Any]) -> Any:
            raise RuntimeError("실패")

        coord.add_stage("fail", StageDefinition("bad", failing))
        coord.add_stage("fail", StageDefinition(
            "after", lambda ctx: None, dependencies=["bad"],
        ))

        result = coord.execute("fail")
        assert result.success is False
        assert result.stages["bad"].status == StageStatus.FAILED
        assert result.stages["after"].status == StageStatus.FAILED
        assert "선행 단계 실패" in result.stages["after"].error_message

    def test_optional_stage_failure(self):
        """선택 단계 실패 시 건너뜀, 파이프라인은 계속."""
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("opt")

        def failing(ctx: dict[str, Any]) -> Any:
            raise RuntimeError("선택 실패")

        coord.add_stage("opt", StageDefinition(
            "optional_step", failing, optional=True,
        ))
        coord.add_stage("opt", StageDefinition(
            "normal_step", lambda ctx: {"done": True},
        ))

        result = coord.execute("opt")
        assert result.success is True
        assert result.stages["optional_step"].status == StageStatus.SKIPPED

    def test_with_initial_context(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("ctx")

        coord.add_stage("ctx", StageDefinition(
            "use_ctx", lambda ctx: ctx.get("input_data"),
        ))

        result = coord.execute("ctx", context={"input_data": "hello"})
        assert result.success is True
        assert result.stages["use_ctx"].output == "hello"

    def test_execute_missing_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        with pytest.raises(KeyError, match="미등록 파이프라인"):
            coord.execute("missing")

    def test_execute_empty_pipeline(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("empty")

        result = coord.execute("empty")
        assert result.success is True
        assert len(result.stages) == 0

    def test_execution_duration(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("timed")
        coord.add_stage("timed", StageDefinition(
            "step", lambda ctx: None,
        ))

        result = coord.execute("timed")
        assert result.total_duration_sec >= 0
        assert result.stages["step"].duration_sec >= 0


# =============================================================================
# 순환 의존
# =============================================================================

class TestCyclicDependency:
    def test_circular_raises(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("cycle")

        coord.add_stage("cycle", StageDefinition(
            "a", lambda ctx: None, dependencies=["b"],
        ))
        coord.add_stage("cycle", StageDefinition(
            "b", lambda ctx: None, dependencies=["a"],
        ))

        with pytest.raises(RuntimeError, match="순환 의존"):
            coord.execute("cycle")

    def test_missing_dependency_raises(self):
        coord = PipelineCoordinator.get_instance()
        coord.create_pipeline("broken")

        coord.add_stage("broken", StageDefinition(
            "stage", lambda ctx: None, dependencies=["nonexistent"],
        ))

        with pytest.raises(RuntimeError, match="미등록 의존 단계"):
            coord.execute("broken")


# =============================================================================
# 콜백
# =============================================================================

class TestCallbacks:
    def test_callback_called(self):
        coord = PipelineCoordinator.get_instance()
        events: list[tuple[str, StageStatus]] = []

        def on_event(stage: str, status: StageStatus):
            events.append((stage, status))

        coord.add_callback(on_event)
        coord.create_pipeline("cb")
        coord.add_stage("cb", StageDefinition("step", lambda ctx: None))

        coord.execute("cb")

        # RUNNING + COMPLETED
        assert len(events) == 2
        assert events[0] == ("step", StageStatus.RUNNING)
        assert events[1] == ("step", StageStatus.COMPLETED)

    def test_callback_exception_isolation(self):
        coord = PipelineCoordinator.get_instance()

        def bad_callback(stage: str, status: StageStatus):
            raise RuntimeError("콜백 폭발")

        coord.add_callback(bad_callback)
        coord.create_pipeline("safe")
        coord.add_stage("safe", StageDefinition("step", lambda ctx: None))

        # 콜백 예외가 실행에 영향 없음
        result = coord.execute("safe")
        assert result.success is True

    def test_remove_callback(self):
        coord = PipelineCoordinator.get_instance()

        def cb(stage: str, status: StageStatus):
            pass

        coord.add_callback(cb)
        assert coord.remove_callback(cb) is True
        assert coord.remove_callback(cb) is False


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_create_and_execute(self):
        coord = PipelineCoordinator.get_instance()
        errors: list[Exception] = []

        def create_and_execute(idx: int):
            try:
                name = f"pipe_{idx}"
                coord.create_pipeline(name)
                coord.add_stage(name, StageDefinition(
                    "step", lambda ctx: None,
                ))
                coord.execute(name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_and_execute, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        coord = PipelineCoordinator.get_instance()
        assert "pipelines=" in repr(coord)


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_pipelines(self):
        assert MAX_PIPELINES == 30

    def test_max_stages(self):
        assert MAX_STAGES_PER_PIPELINE == 50


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.registry.pipeline_coordinator as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.registry.pipeline_coordinator as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.registry.pipeline_coordinator as mod
        assert mod.__version__ == "1.0.0"
