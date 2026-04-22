# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: possession_pipeline.py
설명: 🟡 POSSESSION 등급 파이프라인 — 점유 종료 시 실행 (<100ms)
      - 전술 분석 6종 (tactical_analysis/)
      - 개인 심층 분석 6종 (individual_analysis/)
      - 하이라이트 감지/점수/클립 3종 (highlight/)
      - 공간 분석 4종 (spatial_analysis/)
      - analysis_worker의 possession 스레드풀에서 비동기 실행

      데이터 흐름:
        점유 종료 트리거 (pending_possession_end)
          → 전술 분석: PnR, 속공, 세트플레이, 패싱네트워크, 점유효율, 턴오버
          → 개인 분석: 드라이브, 오프볼, 클러치, 피로도, 임팩트, 리바운드
          → 하이라이트: 감지 → 흥미도 점수 → 클립 추출
          → 공간 분석: 스페이싱, 히트맵, 존 컨트롤, 페인트 분석
          → PossessionPipelineResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceConfig
    - game_analysis/analysis/team/tactical_analysis/: 6종 전술 분석기
    - game_analysis/analysis/player/individual_analysis/: 6종 개인 분석기
    - game_analysis/output/highlight/: 3종 하이라이트 모듈
    - game_analysis/analysis/context/spatial_analysis/: 4종 공간 분석기

소비자:
    - engine/workers/analysis_worker.py: possession 스레드풀에서 실행
    - engine/orchestrator/cadence_scheduler.py: POSSESSION cadence 콜백
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceConfig

if TYPE_CHECKING:
    # 전술 분석 6종
    from game_analysis.analysis.team.tactical_analysis import (
        FastBreakAnalyzer,
        PassingNetworkAnalyzer,
        PossessionAnalyzer,
        ScreenAnalyzer,
        SetPlayRecognizer,
        TurnoverAnalyzer,
    )
    # 개인 심층 분석 6종
    from game_analysis.analysis.player.individual_analysis import (
        ClutchPerformanceAnalyzer,
        DriveAnalyzer,
        FatigueAnalyzer,
        OffBallMovementAnalyzer,
        PlayerImpactAnalyzer,
        ReboundAnalyzer,
    )
    # 하이라이트 3종
    from game_analysis.output.highlight import (
        ClipExtractor,
        ExcitementScorer,
        HighlightDetector,
    )
    # 공간 분석 4종
    from game_analysis.analysis.context.spatial_analysis import (
        FloorSpacingAnalyzer,
        MovementHeatmapAnalyzer,
        PaintAnalyzer,
        ZoneControlAnalyzer,
    )
    # 수비 분석 5종
    from game_analysis.analysis.team.defensive_analysis import (
        BoxOutAnalyzer,
        CloseoutAnalyzer,
        DefenseTypeClassifier,
        DefensiveRotationAnalyzer,
        HelpRecoveryAnalyzer,
    )
    # 전환 분석 3종
    from game_analysis.analysis.team.transition_analysis import (
        TransitionDefenseAnalyzer,
        TransitionEfficiencyAnalyzer,
        TransitionOffenseAnalyzer,
    )
    # 플레이 유형 분석 6종
    from game_analysis.analysis.team.play_type_analysis import (
        FreeThrowAnalyzer as PlayTypeFTAnalyzer,
        IsolationAnalyzer,
        PickAndRollAnalyzer,
        PlayTypeEfficiencyAnalyzer,
        PostUpAnalyzer,
        SpotUpAnalyzer,
    )
    # 라인업 분석 3종
    from game_analysis.analysis.player.lineup_analysis import (
        LineupEfficiencyAnalyzer,
        LineupTracker,
        PlayerSynergyAnalyzer,
    )
    # 매치업 분석 3종
    from game_analysis.output.matchup_analysis import (
        ContestAnalyzer,
        MatchupEvaluator,
        MatchupTracker,
    )
    # 특수 상황 4종
    from game_analysis.analysis.context.special_situation import (
        ATOPlayAnalyzer,
        FoulGameAnalyzer,
        LastPossessionAnalyzer,
        OOBPlayAnalyzer,
    )

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_RESULT_HISTORY: Final[int] = 200


# =============================================================================
# 분석기 셋 (DI 컨테이너)
# =============================================================================
@dataclass(slots=True)
class PossessionAnalyzerSet:
    """
    🟡 POSSESSION 파이프라인 분석기 DI 컨테이너.

    None인 분석기는 건너뜁니다 (점진적 연동).
    """

    # 전술 6종
    screen_analyzer: ScreenAnalyzer | None = None
    fast_break_analyzer: FastBreakAnalyzer | None = None
    set_play_recognizer: SetPlayRecognizer | None = None
    passing_network: PassingNetworkAnalyzer | None = None
    possession_analyzer: PossessionAnalyzer | None = None
    turnover_analyzer: TurnoverAnalyzer | None = None

    # 개인 6종
    drive_analyzer: DriveAnalyzer | None = None
    off_ball: OffBallMovementAnalyzer | None = None
    clutch: ClutchPerformanceAnalyzer | None = None
    fatigue: FatigueAnalyzer | None = None
    player_impact: PlayerImpactAnalyzer | None = None
    rebound_analyzer: ReboundAnalyzer | None = None

    # 하이라이트 3종
    highlight_detector: HighlightDetector | None = None
    excitement_scorer: ExcitementScorer | None = None
    clip_extractor: ClipExtractor | None = None

    # 공간 4종
    floor_spacing: FloorSpacingAnalyzer | None = None
    movement_heatmap: MovementHeatmapAnalyzer | None = None
    zone_control: ZoneControlAnalyzer | None = None
    paint_analyzer: PaintAnalyzer | None = None

    # 수비 분석 5종
    defense_type: DefenseTypeClassifier | None = None
    defensive_rotation: DefensiveRotationAnalyzer | None = None
    box_out_analyzer: BoxOutAnalyzer | None = None
    closeout: CloseoutAnalyzer | None = None
    help_recovery: HelpRecoveryAnalyzer | None = None

    # 전환 분석 3종
    transition_offense: TransitionOffenseAnalyzer | None = None
    transition_defense: TransitionDefenseAnalyzer | None = None
    transition_efficiency: TransitionEfficiencyAnalyzer | None = None

    # 플레이 유형 6종
    pick_and_roll: PickAndRollAnalyzer | None = None
    isolation: IsolationAnalyzer | None = None
    post_up: PostUpAnalyzer | None = None
    spot_up: SpotUpAnalyzer | None = None
    play_type_ft: PlayTypeFTAnalyzer | None = None
    play_type_efficiency: PlayTypeEfficiencyAnalyzer | None = None

    # 라인업 3종
    lineup_tracker: LineupTracker | None = None
    lineup_efficiency: LineupEfficiencyAnalyzer | None = None
    player_synergy: PlayerSynergyAnalyzer | None = None

    # 매치업 3종
    matchup_tracker: MatchupTracker | None = None
    contest_analyzer: ContestAnalyzer | None = None
    matchup_evaluator: MatchupEvaluator | None = None

    # 특수 상황 4종
    ato_play: ATOPlayAnalyzer | None = None
    oob_play: OOBPlayAnalyzer | None = None
    foul_game: FoulGameAnalyzer | None = None
    last_possession: LastPossessionAnalyzer | None = None


# =============================================================================
# 파이프라인 결과
# =============================================================================
@dataclass(slots=True)
class PossessionPipelineResult:
    """
    🟡 POSSESSION 파이프라인 결과.

    Attributes:
        possession_id: 점유 ID
        tactical_results: 전술 분석 결과 목록
        individual_results: 개인 분석 결과 목록
        highlight_results: 하이라이트 결과 목록
        spatial_results: 공간 분석 결과 목록
        processing_time_ms: 처리 시간 (ms)
    """

    possession_id: int = 0
    tactical_results: list[Any] = field(default_factory=list)
    individual_results: list[Any] = field(default_factory=list)
    highlight_results: list[Any] = field(default_factory=list)
    spatial_results: list[Any] = field(default_factory=list)
    processing_time_ms: float = 0.0


# =============================================================================
# POSSESSION 파이프라인
# =============================================================================
class PossessionPipeline:
    """
    🟡 POSSESSION 등급 파이프라인.

    점유 종료 시 전술/개인/하이라이트/공간 분석을 수행합니다.
    analysis_worker의 possession 스레드풀에서 비동기 실행됩니다.
    """

    __slots__ = (
        "_analyzers",
        "_cadence_config",
        "_history",
        "_total_runs",
        "_lock",
        "_clip_observer",
    )

    def __init__(
        self,
        analyzers: PossessionAnalyzerSet | None = None,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._analyzers = analyzers or PossessionAnalyzerSet()
        self._cadence_config = cadence_config or CadenceConfig()
        self._history: list[PossessionPipelineResult] = []
        self._total_runs: int = 0
        self._lock: RLock = RLock()
        # ClipExtractor 가 ExtractedClip 을 산출하면 호출되는 옵저버.
        # 시그니처: callback(extracted_clip) — 예외 시 로그만, 파이프라인 중단 없음.
        self._clip_observer = None  # type: ignore[assignment]

    def set_clip_observer(self, callback) -> None:
        """ClipExtractor 결과 옵저버 등록 (옵션).

        Args:
            callback: Callable[[ExtractedClip], None] — 스레드에서 실행됨.
                      빠르게 반환할 것 (무거운 작업은 내부에서 스레드로 offload).
        """
        self._clip_observer = callback

    def process(
        self,
        possession_id: int = 0,
        possession_data: Any = None,
    ) -> PossessionPipelineResult:
        """
        점유 종료 시 분석 실행.

        Args:
            possession_id: 점유 ID
            possession_data: 점유 데이터 (이벤트/프레임 정보)

        Returns:
            PossessionPipelineResult
        """
        t0 = time.perf_counter()
        a = self._analyzers

        tactical: list[Any] = []
        individual: list[Any] = []
        highlights: list[Any] = []
        spatial: list[Any] = []

        # 1. 전술 분석 6종
        for name, analyzer in [
            ("screen", a.screen_analyzer),
            ("fast_break", a.fast_break_analyzer),
            ("set_play", a.set_play_recognizer),
            ("passing", a.passing_network),
            ("possession", a.possession_analyzer),
            ("turnover", a.turnover_analyzer),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                tactical.append(result)
                except Exception:
                    _logger.exception("전술 분석 오류: %s", name)

        # 2. 개인 심층 분석 6종
        for name, analyzer in [
            ("drive", a.drive_analyzer),
            ("off_ball", a.off_ball),
            ("clutch", a.clutch),
            ("fatigue", a.fatigue),
            ("impact", a.player_impact),
            ("rebound", a.rebound_analyzer),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                individual.append(result)
                except Exception:
                    _logger.exception("개인 분석 오류: %s", name)

        # 3. 하이라이트 3종
        for name, analyzer in [
            ("highlight", a.highlight_detector),
            ("excitement", a.excitement_scorer),
            ("clip", a.clip_extractor),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "process", getattr(analyzer, "score", None))
                        # ClipExtractor 는 extract_clip 을 메서드로 갖는다.
                        if name == "clip" and method is None:
                            method = getattr(analyzer, "extract_clip", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                highlights.append(result)
                                # ClipExtractor 결과는 옵저버에게 알림 (파일 추출 등 후처리용)
                                if name == "clip" and self._clip_observer is not None:
                                    try:
                                        self._clip_observer(result)
                                    except Exception:
                                        _logger.exception("clip observer 오류 (무시)")
                except Exception:
                    _logger.exception("하이라이트 오류: %s", name)

        # 4. 공간 분석 4종
        for name, analyzer in [
            ("spacing", a.floor_spacing),
            ("heatmap", a.movement_heatmap),
            ("zone", a.zone_control),
            ("paint", a.paint_analyzer),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                spatial.append(result)
                except Exception:
                    _logger.exception("공간 분석 오류: %s", name)

        # 5. 수비 분석 5종
        for name, analyzer in [
            ("defense_type", a.defense_type),
            ("defensive_rotation", a.defensive_rotation),
            ("box_out", a.box_out_analyzer),
            ("closeout", a.closeout),
            ("help_recovery", a.help_recovery),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                tactical.append(result)
                except Exception:
                    _logger.exception("수비 분석 오류: %s", name)

        # 6. 전환 분석 3종
        for name, analyzer in [
            ("transition_offense", a.transition_offense),
            ("transition_defense", a.transition_defense),
            ("transition_efficiency", a.transition_efficiency),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                tactical.append(result)
                except Exception:
                    _logger.exception("전환 분석 오류: %s", name)

        # 7. 플레이 유형 분석 6종
        for name, analyzer in [
            ("pick_and_roll", a.pick_and_roll),
            ("isolation", a.isolation),
            ("post_up", a.post_up),
            ("spot_up", a.spot_up),
            ("play_type_ft", a.play_type_ft),
            ("play_type_efficiency", a.play_type_efficiency),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                tactical.append(result)
                except Exception:
                    _logger.exception("플레이 유형 오류: %s", name)

        # 8. 라인업 + 매치업 6종
        for name, analyzer in [
            ("lineup_tracker", a.lineup_tracker),
            ("lineup_efficiency", a.lineup_efficiency),
            ("player_synergy", a.player_synergy),
            ("matchup_tracker", a.matchup_tracker),
            ("contest", a.contest_analyzer),
            ("matchup_evaluator", a.matchup_evaluator),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", getattr(analyzer, "process", None))
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                individual.append(result)
                except Exception:
                    _logger.exception("라인업/매치업 오류: %s", name)

        # 9. 특수 상황 4종
        for name, analyzer in [
            ("ato_play", a.ato_play),
            ("oob_play", a.oob_play),
            ("foul_game", a.foul_game),
            ("last_possession", a.last_possession),
        ]:
            if analyzer is not None and possession_data is not None:
                try:
                    input_data = getattr(possession_data, f"{name}_input", None)
                    if input_data is not None:
                        method = getattr(analyzer, "analyze", None)
                        if method is not None:
                            result = method(input_data)
                            if result is not None:
                                tactical.append(result)
                except Exception:
                    _logger.exception("특수 상황 오류: %s", name)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = PossessionPipelineResult(
            possession_id=possession_id,
            tactical_results=tactical,
            individual_results=individual,
            highlight_results=highlights,
            spatial_results=spatial,
            processing_time_ms=elapsed_ms,
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
        """연결된 분석기 수."""
        a = self._analyzers
        return sum(1 for x in (
            # 전술 6
            a.screen_analyzer, a.fast_break_analyzer, a.set_play_recognizer,
            a.passing_network, a.possession_analyzer, a.turnover_analyzer,
            # 개인 6
            a.drive_analyzer, a.off_ball, a.clutch, a.fatigue,
            a.player_impact, a.rebound_analyzer,
            # 하이라이트 3
            a.highlight_detector, a.excitement_scorer, a.clip_extractor,
            # 공간 4
            a.floor_spacing, a.movement_heatmap, a.zone_control, a.paint_analyzer,
            # 수비 5
            a.defense_type, a.defensive_rotation, a.box_out_analyzer,
            a.closeout, a.help_recovery,
            # 전환 3
            a.transition_offense, a.transition_defense, a.transition_efficiency,
            # 플레이 유형 6
            a.pick_and_roll, a.isolation, a.post_up,
            a.spot_up, a.play_type_ft, a.play_type_efficiency,
            # 라인업 3
            a.lineup_tracker, a.lineup_efficiency, a.player_synergy,
            # 매치업 3
            a.matchup_tracker, a.contest_analyzer, a.matchup_evaluator,
            # 특수 상황 4
            a.ato_play, a.oob_play, a.foul_game, a.last_possession,
        ) if x is not None)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._total_runs = 0

    def __repr__(self) -> str:
        return f"PossessionPipeline(runs={self._total_runs}, analyzers={self.analyzer_count}/43)"


__all__ = [
    "PossessionAnalyzerSet",
    "PossessionPipelineResult",
    "PossessionPipeline",
]

__version__ = "1.0.0"
