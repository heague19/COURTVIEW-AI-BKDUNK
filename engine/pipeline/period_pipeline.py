# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: period_pipeline.py
설명: 🟢 PERIOD 등급 파이프라인 — 쿼터 종료 시 실행 (<1s)
      - 경기 흐름 4종 (game_flow/): 모멘텀, 템포, 타임아웃, 리드
      - 로테이션 4종 (rotation_analysis/): 교체패턴, 스태거, 벤치, 휴식
      - 쿼터 요약 (quarter_summary)
      - 시즌 분석 3종 (season_analysis/): 시즌집계, 추세, 벤치마크
      - analysis_worker의 period 스레드풀에서 비동기 실행

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceConfig
    - game_analysis/analysis/context/game_flow/: 4종 흐름 분석기
    - game_analysis/analysis/player/rotation_analysis/: 4종 로테이션 분석기
    - game_analysis/output/game_record/quarter_summary.py: QuarterSummaryGenerator
    - game_analysis/analysis/context/season_analysis/: 3종 시즌 분석기

소비자:
    - engine/workers/analysis_worker.py: period 스레드풀에서 실행
    - engine/orchestrator/cadence_scheduler.py: PERIOD cadence 콜백
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

from engine.config import CadenceConfig

if TYPE_CHECKING:
    # 경기 흐름 4종
    from game_analysis.analysis.context.game_flow import (
        LeadManagementAnalyzer,
        MomentumTracker,
        TempoAnalyzer,
        TimeoutEffectivenessAnalyzer,
    )
    # 로테이션 4종
    from game_analysis.analysis.player.rotation_analysis import (
        BenchUnitAnalyzer,
        RestPeriodAnalyzer,
        RotationTracker,
        StaggerAnalyzer,
    )
    # 쿼터 요약
    from game_analysis.output.game_record.quarter_summary import (
        QuarterSummaryGenerator,
    )
    # 시즌 분석 3종
    from game_analysis.analysis.context.season_analysis import (
        BenchmarkComparator,
        SeasonAggregator,
        TrendTracker,
    )
    # 상황별 스플릿 4종
    from game_analysis.analysis.context.situation_splits import (
        GameContextAnalyzer,
        PeriodSplitsAnalyzer,
        ScoreMarginSplitsAnalyzer,
        ShotClockSplitsAnalyzer,
    )

_logger = logging.getLogger(__name__)
_MAX_RESULT_HISTORY: Final[int] = 50


@dataclass(slots=True)
class PeriodAnalyzerSet:
    """🟢 PERIOD 파이프라인 분석기 DI 컨테이너."""

    # 경기 흐름 4종
    momentum: MomentumTracker | None = None
    tempo: TempoAnalyzer | None = None
    timeout_effectiveness: TimeoutEffectivenessAnalyzer | None = None
    lead_management: LeadManagementAnalyzer | None = None

    # 로테이션 4종
    rotation_tracker: RotationTracker | None = None
    stagger: StaggerAnalyzer | None = None
    bench_unit: BenchUnitAnalyzer | None = None
    rest_period: RestPeriodAnalyzer | None = None

    # 쿼터 요약
    quarter_summary: QuarterSummaryGenerator | None = None

    # 시즌 분석 3종
    season_aggregator: SeasonAggregator | None = None
    trend_tracker: TrendTracker | None = None
    benchmark: BenchmarkComparator | None = None

    # 상황별 스플릿 4종
    period_splits: PeriodSplitsAnalyzer | None = None
    score_margin_splits: ScoreMarginSplitsAnalyzer | None = None
    shot_clock_splits: ShotClockSplitsAnalyzer | None = None
    game_context_analyzer: GameContextAnalyzer | None = None


@dataclass(slots=True)
class PeriodPipelineResult:
    """🟢 PERIOD 파이프라인 결과."""

    quarter: int = 0
    flow_results: list[Any] = field(default_factory=list)
    rotation_results: list[Any] = field(default_factory=list)
    summary_result: Any = None
    season_results: list[Any] = field(default_factory=list)
    processing_time_ms: float = 0.0


class PeriodPipeline:
    """🟢 PERIOD 등급 파이프라인."""

    __slots__ = ("_analyzers", "_cadence_config", "_history", "_total_runs", "_lock")

    def __init__(
        self,
        analyzers: PeriodAnalyzerSet | None = None,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._analyzers = analyzers or PeriodAnalyzerSet()
        self._cadence_config = cadence_config or CadenceConfig()
        self._history: list[PeriodPipelineResult] = []
        self._total_runs: int = 0
        self._lock: RLock = RLock()

    def process(self, quarter: int = 0, period_data: Any = None) -> PeriodPipelineResult:
        """쿼터 종료 시 분석 실행."""
        t0 = time.perf_counter()
        a = self._analyzers
        flow: list[Any] = []
        rotation: list[Any] = []
        summary: Any = None
        season: list[Any] = []

        # 1. 경기 흐름 4종
        for name, analyzer in [
            ("momentum", a.momentum), ("tempo", a.tempo),
            ("timeout", a.timeout_effectiveness), ("lead", a.lead_management),
        ]:
            if analyzer is not None and period_data is not None:
                try:
                    inp = getattr(period_data, f"{name}_input", None)
                    if inp is not None:
                        m = getattr(analyzer, "analyze", getattr(analyzer, "get_summary", None))
                        if m is not None:
                            r = m(inp)
                            if r is not None:
                                flow.append(r)
                except Exception:
                    _logger.exception("흐름 분석 오류: %s", name)

        # 2. 로테이션 4종
        for name, analyzer in [
            ("rotation", a.rotation_tracker), ("stagger", a.stagger),
            ("bench", a.bench_unit), ("rest", a.rest_period),
        ]:
            if analyzer is not None and period_data is not None:
                try:
                    inp = getattr(period_data, f"{name}_input", None)
                    if inp is not None:
                        m = getattr(analyzer, "analyze", None)
                        if m is not None:
                            r = m(inp)
                            if r is not None:
                                rotation.append(r)
                except Exception:
                    _logger.exception("로테이션 오류: %s", name)

        # 3. 쿼터 요약
        if a.quarter_summary is not None and period_data is not None:
            try:
                inp = getattr(period_data, "quarter_input", None)
                if inp is not None:
                    m = getattr(a.quarter_summary, "generate", None)
                    if m is not None:
                        summary = m(inp)
            except Exception:
                _logger.exception("쿼터 요약 오류")

        # 4. 시즌 분석 3종
        for name, analyzer in [
            ("season", a.season_aggregator), ("trend", a.trend_tracker),
            ("benchmark", a.benchmark),
        ]:
            if analyzer is not None and period_data is not None:
                try:
                    inp = getattr(period_data, f"{name}_input", None)
                    if inp is not None:
                        m = getattr(analyzer, "analyze", getattr(analyzer, "update", None))
                        if m is not None:
                            r = m(inp)
                            if r is not None:
                                season.append(r)
                except Exception:
                    _logger.exception("시즌 분석 오류: %s", name)

        # 5. 상황별 스플릿 4종
        for name, analyzer in [
            ("period_splits", a.period_splits),
            ("score_margin", a.score_margin_splits),
            ("shot_clock", a.shot_clock_splits),
            ("game_context", a.game_context_analyzer),
        ]:
            if analyzer is not None and period_data is not None:
                try:
                    inp = getattr(period_data, f"{name}_input", None)
                    if inp is not None:
                        m = getattr(analyzer, "analyze", None)
                        if m is not None:
                            r = m(inp)
                            if r is not None:
                                flow.append(r)
                except Exception:
                    _logger.exception("상황 스플릿 오류: %s", name)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        result = PeriodPipelineResult(
            quarter=quarter, flow_results=flow, rotation_results=rotation,
            summary_result=summary, season_results=season, processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_runs += 1
            self._history.append(result)
            if len(self._history) > _MAX_RESULT_HISTORY:
                self._history = self._history[-_MAX_RESULT_HISTORY:]

        return result

    @property
    def total_runs(self) -> int:
        return self._total_runs

    @property
    def analyzer_count(self) -> int:
        a = self._analyzers
        return sum(1 for x in (
            a.momentum, a.tempo, a.timeout_effectiveness, a.lead_management,
            a.rotation_tracker, a.stagger, a.bench_unit, a.rest_period,
            a.quarter_summary, a.season_aggregator, a.trend_tracker, a.benchmark,
            a.period_splits, a.score_margin_splits, a.shot_clock_splits, a.game_context_analyzer,
        ) if x is not None)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._total_runs = 0

    def __repr__(self) -> str:
        return f"PeriodPipeline(runs={self._total_runs}, analyzers={self.analyzer_count}/16)"


__all__ = ["PeriodAnalyzerSet", "PeriodPipelineResult", "PeriodPipeline"]
__version__ = "1.0.0"
