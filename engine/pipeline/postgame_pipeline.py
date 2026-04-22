# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: postgame_pipeline.py
설명: 🔵 POST-GAME 등급 파이프라인 — 경기 종료 후 실행 (무제한)
      - 경기 리포트 빌더 (game_record/game_report_builder)
      - 피드백 리포트 생성 (feedback_system/report/)
      - 자가학습용 데이터 추출 7종 (game_analysis/data_extraction/)
      - AI 심판 학습 데이터 추출 6종 (ai_referee/data_extraction/)
      - export_worker에서 비동기 실행

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceConfig
    - game_analysis/output/game_record/: GameReportBuilder
    - feedback_system/report/: GameReportGenerator, CoachReportGenerator
    - game_analysis/data_extraction/: 7종 추출기
    - ai_referee/data_extraction/: 6종 추출기

소비자:
    - engine/workers/export_worker.py: 비동기 실행
    - engine/orchestrator/cadence_scheduler.py: POSTGAME cadence 콜백
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

from engine.config import CadenceConfig

if TYPE_CHECKING:
    # 경기 리포트
    from game_analysis.output.game_record.game_report_builder import (
        GameReportBuilder,
    )
    # 피드백 리포트
    from feedback_system.report import (
        CoachReportGenerator,
        GameReportGenerator,
    )
    # game_analysis 데이터 추출 7종
    from game_analysis.data_extraction import (
        EventCorrectionExtractor,
        FrameRecordExtractor,
        GameRecordExtractor,
        PlayerPerformanceExtractor,
        PossessionRecordExtractor,
        PredictionOutcomeExtractor,
        TacticalSequenceExtractor,
    )
    # ai_referee 데이터 추출 6종
    from ai_referee.data_extraction import (
        CalibrationDataExtractor,
        CorrectionPairExtractor,
        DecisionRecordExtractor,
        EdgeCaseExtractor,
        FoulContactExtractor,
        ViolationSequenceExtractor,
    )
    # 비디오 편집 4종
    from game_analysis.output.video_editing import (
        AnnotationOverlayManager,
        ClipManager,
        ExportManager,
        MultiAngleSyncManager,
    )
    # 필름 세션 3종
    from game_analysis.output.film_session import (
        FilmSessionBuilder,
        PlayerClipPackageBuilder,
        TeachingPointGenerator,
    )
    # 경기 전 준비 5종
    from game_analysis.output.pre_game import (
        DefensiveAssignmentPlanner,
        GamePlanExecutionTracker,
        GamePlanGenerator,
        OffensivePrioritySetter,
        PreGameBriefingBuilder,
    )
    # 스카우팅 7종
    from game_analysis.output.scouting import (
        HeadToHeadAnalyzer,
        OpponentProfiler,
        PlayPatternMatcher,
        RefereeTendencyAnalyzer,
        ScoutingReportBuilder,
        TendencyAnalyzer,
        WeaknessFinder,
    )

_logger = logging.getLogger(__name__)
_MAX_RESULT_HISTORY: Final[int] = 20


@dataclass(slots=True)
class PostgameModuleSet:
    """🔵 POST-GAME 파이프라인 모듈 DI 컨테이너."""

    # 리포트
    game_report_builder: GameReportBuilder | None = None
    game_report_generator: GameReportGenerator | None = None
    coach_report_generator: CoachReportGenerator | None = None

    # game_analysis 데이터 추출 7종
    frame_extractor: FrameRecordExtractor | None = None
    possession_extractor: PossessionRecordExtractor | None = None
    game_extractor: GameRecordExtractor | None = None
    correction_extractor: EventCorrectionExtractor | None = None
    tactical_extractor: TacticalSequenceExtractor | None = None
    performance_extractor: PlayerPerformanceExtractor | None = None
    prediction_extractor: PredictionOutcomeExtractor | None = None

    # ai_referee 데이터 추출 6종
    decision_record_extractor: DecisionRecordExtractor | None = None
    correction_pair_extractor: CorrectionPairExtractor | None = None
    edge_case_extractor: EdgeCaseExtractor | None = None
    calibration_extractor: CalibrationDataExtractor | None = None
    foul_contact_extractor: FoulContactExtractor | None = None
    violation_sequence_extractor: ViolationSequenceExtractor | None = None

    # 비디오 편집 4종
    clip_manager: ClipManager | None = None
    annotation_overlay: AnnotationOverlayManager | None = None
    multi_angle_sync: MultiAngleSyncManager | None = None
    export_manager: ExportManager | None = None

    # 필름 세션 3종
    film_session_builder: FilmSessionBuilder | None = None
    player_clip_package: PlayerClipPackageBuilder | None = None
    teaching_point_gen: TeachingPointGenerator | None = None

    # 경기 전 준비 5종
    game_plan_gen: GamePlanGenerator | None = None
    game_plan_tracker: GamePlanExecutionTracker | None = None
    defensive_planner: DefensiveAssignmentPlanner | None = None
    offensive_priority: OffensivePrioritySetter | None = None
    pre_game_briefing: PreGameBriefingBuilder | None = None

    # 스카우팅 7종
    opponent_profiler: OpponentProfiler | None = None
    tendency_analyzer: TendencyAnalyzer | None = None
    weakness_finder: WeaknessFinder | None = None
    head_to_head: HeadToHeadAnalyzer | None = None
    scouting_report: ScoutingReportBuilder | None = None
    play_pattern_matcher: PlayPatternMatcher | None = None
    referee_tendency: RefereeTendencyAnalyzer | None = None


@dataclass(slots=True)
class PostgamePipelineResult:
    """🔵 POST-GAME 파이프라인 결과."""

    report_generated: bool = False
    feedback_generated: bool = False
    datasets_extracted: int = 0
    referee_datasets_extracted: int = 0
    processing_time_ms: float = 0.0
    # 추출된 학습 데이터 (Cloud 전송용)
    extracted_training_data: dict[str, Any] = field(default_factory=dict)


class PostgamePipeline:
    """🔵 POST-GAME 등급 파이프라인."""

    __slots__ = ("_modules", "_cadence_config", "_history", "_total_runs", "_lock")

    def __init__(
        self,
        modules: PostgameModuleSet | None = None,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._modules = modules or PostgameModuleSet()
        self._cadence_config = cadence_config or CadenceConfig()
        self._history: list[PostgamePipelineResult] = []
        self._total_runs: int = 0
        self._lock: RLock = RLock()

    def process(self, game_data: Any = None) -> PostgamePipelineResult:
        """경기 종료 후 전체 분석 실행."""
        t0 = time.perf_counter()
        m = self._modules
        report_ok = False
        feedback_ok = False
        ga_extracted = 0
        ref_extracted = 0

        # 1. 경기 리포트
        if m.game_report_builder is not None and game_data is not None:
            try:
                inp = getattr(game_data, "report_input", None)
                if inp is not None:
                    build = getattr(m.game_report_builder, "build", None)
                    if build is not None:
                        build(inp)
                        report_ok = True
            except Exception:
                _logger.exception("경기 리포트 생성 오류")

        # 2. 피드백 리포트
        for name, gen in [
            ("game_feedback", m.game_report_generator),
            ("coach_feedback", m.coach_report_generator),
        ]:
            if gen is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_input", None)
                    if inp is not None:
                        generate = getattr(gen, "generate", None)
                        if generate is not None:
                            generate(**inp) if isinstance(inp, dict) else generate(inp)
                            feedback_ok = True
                except Exception:
                    _logger.exception("피드백 리포트 오류: %s", name)

        # 3. game_analysis 데이터 추출 7종 (결과 수집)
        training_data: dict[str, Any] = {}
        for name, extractor in [
            ("frame", m.frame_extractor),
            ("possession", m.possession_extractor),
            ("game", m.game_extractor),
            ("correction", m.correction_extractor),
            ("tactical", m.tactical_extractor),
            ("performance", m.performance_extractor),
            ("prediction", m.prediction_extractor),
        ]:
            if extractor is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_extract_input", None)
                    if inp is not None:
                        extract = getattr(extractor, "extract", getattr(extractor, "build", None))
                        if extract is not None:
                            result = extract(inp)
                            if result is not None:
                                training_data[f"ga_{name}"] = result
                            ga_extracted += 1
                except Exception:
                    _logger.exception("GA 데이터 추출 오류: %s", name)

        # 4. ai_referee 데이터 추출 6종 (결과 수집)
        for name, extractor in [
            ("decision", m.decision_record_extractor),
            ("pair", m.correction_pair_extractor),
            ("edge", m.edge_case_extractor),
            ("calibration", m.calibration_extractor),
            ("foul_contact", m.foul_contact_extractor),
            ("violation_seq", m.violation_sequence_extractor),
        ]:
            if extractor is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_extract_input", None)
                    if inp is not None:
                        extract = getattr(extractor, "extract", getattr(extractor, "build", None))
                        if extract is not None:
                            result = extract(inp)
                            if result is not None:
                                training_data[f"ref_{name}"] = result
                            ref_extracted += 1
                except Exception:
                    _logger.exception("Referee 데이터 추출 오류: %s", name)

        # 5. 비디오 편집 4종
        for name, module in [
            ("clip", m.clip_manager),
            ("annotation", m.annotation_overlay),
            ("multi_angle", m.multi_angle_sync),
            ("export", m.export_manager),
        ]:
            if module is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_input", None)
                    if inp is not None:
                        method = getattr(module, "process", getattr(module, "generate", None))
                        if method is not None:
                            method(inp)
                except Exception:
                    _logger.exception("비디오 편집 오류: %s", name)

        # 6. 필름 세션 3종
        for name, module in [
            ("film_session", m.film_session_builder),
            ("player_clip", m.player_clip_package),
            ("teaching_point", m.teaching_point_gen),
        ]:
            if module is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_input", None)
                    if inp is not None:
                        method = getattr(module, "build", getattr(module, "generate", None))
                        if method is not None:
                            method(inp)
                except Exception:
                    _logger.exception("필름 세션 오류: %s", name)

        # 7. 경기 전 준비 5종 (다음 경기용)
        for name, module in [
            ("game_plan", m.game_plan_gen),
            ("game_plan_exec", m.game_plan_tracker),
            ("defensive_assign", m.defensive_planner),
            ("offensive_priority", m.offensive_priority),
            ("pre_game_briefing", m.pre_game_briefing),
        ]:
            if module is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_input", None)
                    if inp is not None:
                        method = getattr(module, "generate", getattr(module, "build", None))
                        if method is not None:
                            method(inp)
                except Exception:
                    _logger.exception("경기 전 준비 오류: %s", name)

        # 8. 스카우팅 7종
        for name, module in [
            ("opponent", m.opponent_profiler),
            ("tendency", m.tendency_analyzer),
            ("weakness", m.weakness_finder),
            ("h2h", m.head_to_head),
            ("scouting_report", m.scouting_report),
            ("play_pattern", m.play_pattern_matcher),
            ("referee_tendency", m.referee_tendency),
        ]:
            if module is not None and game_data is not None:
                try:
                    inp = getattr(game_data, f"{name}_input", None)
                    if inp is not None:
                        method = getattr(module, "analyze", getattr(module, "build", None))
                        if method is not None:
                            method(inp)
                except Exception:
                    _logger.exception("스카우팅 오류: %s", name)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        result = PostgamePipelineResult(
            report_generated=report_ok,
            feedback_generated=feedback_ok,
            datasets_extracted=ga_extracted,
            referee_datasets_extracted=ref_extracted,
            processing_time_ms=elapsed_ms,
            extracted_training_data=training_data,
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
    def module_count(self) -> int:
        m = self._modules
        return sum(1 for x in (
            # 리포트 3
            m.game_report_builder, m.game_report_generator, m.coach_report_generator,
            # GA 추출 7
            m.frame_extractor, m.possession_extractor, m.game_extractor,
            m.correction_extractor, m.tactical_extractor, m.performance_extractor,
            m.prediction_extractor,
            # 심판 추출 6
            m.decision_record_extractor, m.correction_pair_extractor,
            m.edge_case_extractor, m.calibration_extractor,
            m.foul_contact_extractor, m.violation_sequence_extractor,
            # 비디오 편집 4
            m.clip_manager, m.annotation_overlay, m.multi_angle_sync, m.export_manager,
            # 필름 세션 3
            m.film_session_builder, m.player_clip_package, m.teaching_point_gen,
            # 경기 전 5
            m.game_plan_gen, m.game_plan_tracker, m.defensive_planner,
            m.offensive_priority, m.pre_game_briefing,
            # 스카우팅 7
            m.opponent_profiler, m.tendency_analyzer, m.weakness_finder,
            m.head_to_head, m.scouting_report, m.play_pattern_matcher,
            m.referee_tendency,
        ) if x is not None)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._total_runs = 0

    def __repr__(self) -> str:
        return f"PostgamePipeline(runs={self._total_runs}, modules={self.module_count}/35)"


__all__ = ["PostgameModuleSet", "PostgamePipelineResult", "PostgamePipeline"]
__version__ = "1.0.0"
