# -*- coding: utf-8 -*-
"""engine/pipeline (possession/period/postgame) + workers/ 단위 테스트."""

from __future__ import annotations

import time

import pytest

from engine.pipeline.possession_pipeline import (
    PossessionAnalyzerSet,
    PossessionPipeline,
    PossessionPipelineResult,
)
from engine.pipeline.period_pipeline import (
    PeriodAnalyzerSet,
    PeriodPipeline,
    PeriodPipelineResult,
)
from engine.pipeline.postgame_pipeline import (
    PostgameModuleSet,
    PostgamePipeline,
    PostgamePipelineResult,
)
from engine.workers.analysis_worker import AnalysisWorker, WorkerStats
from engine.workers.export_worker import ExportWorker, ExportStats
from engine.config import CadenceConfig, IOConfig


# =============================================================================
# PossessionPipeline 테스트
# =============================================================================
class TestPossessionPipeline:

    def test_empty_run(self) -> None:
        pp = PossessionPipeline()
        r = pp.process(possession_id=1)
        assert r.possession_id == 1
        assert r.processing_time_ms >= 0
        assert len(r.tactical_results) == 0

    def test_analyzer_count_zero(self) -> None:
        pp = PossessionPipeline()
        assert pp.analyzer_count == 0

    def test_total_runs(self) -> None:
        pp = PossessionPipeline()
        pp.process(1)
        pp.process(2)
        assert pp.total_runs == 2

    def test_reset(self) -> None:
        pp = PossessionPipeline()
        pp.process(1)
        pp.reset()
        assert pp.total_runs == 0

    def test_repr(self) -> None:
        pp = PossessionPipeline()
        assert "PossessionPipeline" in repr(pp)
        assert "0/43" in repr(pp)

    def test_slots(self) -> None:
        ds = PossessionAnalyzerSet()
        assert not hasattr(ds, "__dict__")

    def test_result_slots(self) -> None:
        r = PossessionPipelineResult()
        assert not hasattr(r, "__dict__")


# =============================================================================
# PeriodPipeline 테스트
# =============================================================================
class TestPeriodPipeline:

    def test_empty_run(self) -> None:
        pp = PeriodPipeline()
        r = pp.process(quarter=3)
        assert r.quarter == 3
        assert r.processing_time_ms >= 0

    def test_analyzer_count_zero(self) -> None:
        pp = PeriodPipeline()
        assert pp.analyzer_count == 0

    def test_total_runs(self) -> None:
        pp = PeriodPipeline()
        pp.process(1)
        pp.process(2)
        assert pp.total_runs == 2

    def test_reset(self) -> None:
        pp = PeriodPipeline()
        pp.process(1)
        pp.reset()
        assert pp.total_runs == 0

    def test_repr(self) -> None:
        pp = PeriodPipeline()
        assert "0/16" in repr(pp)

    def test_slots(self) -> None:
        ds = PeriodAnalyzerSet()
        assert not hasattr(ds, "__dict__")


# =============================================================================
# PostgamePipeline 테스트
# =============================================================================
class TestPostgamePipeline:

    def test_empty_run(self) -> None:
        pp = PostgamePipeline()
        r = pp.process()
        assert r.report_generated is False
        assert r.datasets_extracted == 0

    def test_module_count_zero(self) -> None:
        pp = PostgamePipeline()
        assert pp.module_count == 0

    def test_total_runs(self) -> None:
        pp = PostgamePipeline()
        pp.process()
        assert pp.total_runs == 1

    def test_repr(self) -> None:
        pp = PostgamePipeline()
        assert "0/35" in repr(pp)

    def test_slots(self) -> None:
        ms = PostgameModuleSet()
        assert not hasattr(ms, "__dict__")


# =============================================================================
# AnalysisWorker 테스트
# =============================================================================
class TestAnalysisWorker:

    def test_initial_state(self) -> None:
        aw = AnalysisWorker()
        assert aw.is_initialized is False

    def test_initialize_shutdown(self) -> None:
        aw = AnalysisWorker()
        aw.initialize()
        assert aw.is_initialized is True
        aw.shutdown()
        assert aw.is_initialized is False

    def test_submit_without_init(self) -> None:
        aw = AnalysisWorker()
        assert aw.submit_possession(1) is None

    def test_submit_without_pipeline(self) -> None:
        aw = AnalysisWorker()
        aw.initialize()
        assert aw.submit_possession(1) is None
        aw.shutdown()

    def test_submit_with_pipeline(self) -> None:
        pp = PossessionPipeline()
        aw = AnalysisWorker(possession_pipeline=pp)
        aw.initialize()
        future = aw.submit_possession(1)
        assert future is not None
        result = future.result(timeout=5.0)
        assert result is not None
        assert aw.stats.possession_completed == 1
        aw.shutdown()

    def test_period_submit(self) -> None:
        pp = PeriodPipeline()
        aw = AnalysisWorker(period_pipeline=pp)
        aw.initialize()
        future = aw.submit_period(quarter=2)
        assert future is not None
        result = future.result(timeout=5.0)
        assert result is not None
        assert aw.stats.period_completed == 1
        aw.shutdown()

    def test_stats_defensive_copy(self) -> None:
        aw = AnalysisWorker()
        s1 = aw.stats
        s2 = aw.stats
        assert s1 is not s2

    def test_repr(self) -> None:
        aw = AnalysisWorker()
        assert "AnalysisWorker" in repr(aw)

    def test_worker_stats_slots(self) -> None:
        ws = WorkerStats()
        assert not hasattr(ws, "__dict__")


# =============================================================================
# ExportWorker 테스트
# =============================================================================
class TestExportWorker:

    def test_initial_state(self) -> None:
        ew = ExportWorker()
        assert ew.is_initialized is False

    def test_submit_without_init(self) -> None:
        ew = ExportWorker()
        assert ew.submit() is None

    def test_submit_with_pipeline(self) -> None:
        pp = PostgamePipeline()
        ew = ExportWorker(pipeline=pp)
        ew.initialize()
        future = ew.submit()
        assert future is not None
        result = future.result(timeout=5.0)
        assert result is not None
        assert ew.stats.completed == 1
        ew.shutdown()

    def test_repr(self) -> None:
        ew = ExportWorker()
        assert "ExportWorker" in repr(ew)


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:

    def test_possession_all(self) -> None:
        import engine.pipeline.possession_pipeline as m
        assert len(m.__all__) == 3
        assert m.__version__ == "1.0.0"

    def test_period_all(self) -> None:
        import engine.pipeline.period_pipeline as m
        assert len(m.__all__) == 3
        assert m.__version__ == "1.0.0"

    def test_postgame_all(self) -> None:
        import engine.pipeline.postgame_pipeline as m
        assert len(m.__all__) == 3
        assert m.__version__ == "1.0.0"

    def test_analysis_worker_all(self) -> None:
        import engine.workers.analysis_worker as m
        assert len(m.__all__) == 2
        assert m.__version__ == "1.0.0"

    def test_export_worker_all(self) -> None:
        import engine.workers.export_worker as m
        assert len(m.__all__) == 2
        assert m.__version__ == "1.0.0"

