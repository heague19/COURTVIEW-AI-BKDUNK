# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: event_pipeline.py
설명: 🟠 EVENT 등급 파이프라인 — 이벤트 트리거 시 실행 (<10ms)
      - 16종 이벤트 감지기 직접 연동 (game_state/event_detection/)
      - 통계 증분 갱신 (game_analysis/stats/statistics/BasicStatsCalculator)
      - AI 심판 규칙 평가 위임 (referee_orchestrator 콜백)
      - cadence_scheduler에서 pending_shooting/foul_contact/violation 시 트리거

      데이터 흐름:
        FramePipelineResult (FRAME 결과)
          → EVENT cadence 감지기 6종 (ShotEvent, Rebound, Foul, Screen, FastBreak, Drive)
          → 역추적 감지기 4종 (Assist, Block, Steal, Turnover)
          → SPECIAL 감지기 3종 (FreeThrow, BoxOut, JumpBall)
          → BasicStatsCalculator.process_event() 증분 갱신
          → EventPipelineResult

      참고: FRAME cadence 감지기 3종 (Score, Possession, DeadBall)은
            frame_pipeline에서 매 프레임 이미 호출됨. 여기서 재호출하지 않음.

      Processing Cadence별 감지기:
        🟠 EVENT (<10ms): ShotEventDetector, ReboundDetector, FoulDetector,
                          ScreenDetector, FastBreakDetector, DriveDetector
        🟠 역추적 (<10ms): AssistDetector, BlockDetector, StealDetector, TurnoverDetector
        🟡 SPECIAL: FreeThrowDetector, BoxOutDetector, JumpBallDetector

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CadenceConfig
    - game_analysis/game_state/event_detection/: 13종 감지기 (FRAME 3종 제외)
    - game_analysis/stats/statistics/basic_stats.py: BasicStatsCalculator
    - shared/dto/game_dto.py: GameEvent

소비자:
    - engine/orchestrator/cadence_scheduler.py: EVENT cadence 콜백
    - engine/pipeline/possession_pipeline.py: 🟡 점유 종료 판단 입력
    - engine/referee/referee_orchestrator.py: AI 심판 평가 위임
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Callable, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceConfig
from shared.dto.game_dto import GameEvent

# 13종 이벤트 감지기 (TYPE_CHECKING: 순환참조 방지, 런타임은 DI 주입)
if TYPE_CHECKING:
    # EVENT cadence 6종
    from game_analysis.game_state.event_detection.shot_event_detector import (
        ShotEventDetector,
    )
    from game_analysis.game_state.event_detection.rebound_detector import (
        ReboundDetector,
    )
    from game_analysis.game_state.event_detection.foul_detector import (
        FoulDetector,
    )
    from game_analysis.game_state.event_detection.screen_detector import (
        ScreenDetector,
    )
    from game_analysis.game_state.event_detection.fast_break_detector import (
        FastBreakDetector,
    )
    from game_analysis.game_state.event_detection.drive_detector import (
        DriveDetector,
    )

    # 역추적 4종
    from game_analysis.game_state.event_detection.assist_detector import (
        AssistDetector,
    )
    from game_analysis.game_state.event_detection.block_detector import (
        BlockDetector,
    )
    from game_analysis.game_state.event_detection.steal_detector import (
        StealDetector,
    )
    from game_analysis.game_state.event_detection.turnover_detector import (
        TurnoverDetector,
    )

    # SPECIAL 3종
    from game_analysis.game_state.event_detection.free_throw_detector import (
        FreeThrowDetector,
    )
    from game_analysis.game_state.event_detection.box_out_detector import (
        BoxOutDetector,
    )
    from game_analysis.game_state.event_detection.jump_ball_detector import (
        JumpBallDetector,
    )

    # 통계 증분 7종
    from game_analysis.stats.statistics.basic_stats import BasicStatsCalculator
    from game_analysis.stats.statistics.advanced_stats import AdvancedStatsCalculator
    from game_analysis.stats.statistics.shot_chart import ShotChartCalculator
    from game_analysis.stats.statistics.player_tracker_stats import PlayerTrackerStatsCalculator
    from game_analysis.stats.statistics.team_stats_aggregator import TeamStatsAggregator
    from game_analysis.stats.statistics.possession_stats import PossessionStatsCalculator
    from game_analysis.stats.statistics.four_factors import FourFactorsCalculator

    # 예측 모델 4종
    from game_analysis.stats.predictive_models import (
        WinProbabilityModel,
        EPVModel,
        ShotQualityModel,
        LineupProjectionModel,
    )

    # 코칭 인텔리전스 3종
    from game_analysis.output.coaching_intelligence import (
        RealtimeAdvisor,
        SubstitutionOptimizer,
        EndgameStrategist,
    )

    # 슛 위치 3종
    from game_analysis.output.shot_location.shot_zone_mapper import ShotZoneMapper
    from game_analysis.output.shot_location.shot_heatmap import ShotHeatmapCalculator
    from game_analysis.output.shot_location.efficiency_by_zone import EfficiencyByZoneCalculator

    # 경기 기록 증분 3종
    from game_analysis.output.game_record.game_sheet_generator import GameSheetGenerator
    from game_analysis.output.game_record.play_by_play import PlayByPlayTracker
    from game_analysis.output.game_record.quarter_summary import QuarterSummaryGenerator

    # 실시간 검증/보정 3종
    from game_analysis.game_state.live_workspace import (
        LiveEventValidator,
        ManualEventTagger,
        CorrectionSync,
    )

    # motion_analysis (Stage2 트리거 시)
    from motion_analysis import ActionClassifier

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_EVENT_HISTORY: Final[int] = 500

# 심판 트리거 이벤트 유형 (파울/바이올레이션)
_REFEREE_TRIGGER_TYPES: Final[frozenset[str]] = frozenset({
    "personal_foul", "shooting_foul", "offensive_foul",
    "technical_foul", "flagrant_foul",
    "traveling", "double_dribble", "carrying",
    "three_second", "five_second", "eight_second",
    "shot_clock", "backcourt", "goaltending",
})


# =============================================================================
# 13종 감지기 셋 (DI 컨테이너)
# =============================================================================
@dataclass(slots=True)
class EventDetectorSet:
    """
    13종 이벤트 감지기 + 통계 DI 컨테이너.

    game_orchestrator에서 초기화 후 EventPipeline에 주입합니다.
    None인 감지기는 건너뜁니다 (점진적 연동 지원).

    FRAME cadence 3종 (score/possession/dead_ball)은
    frame_pipeline에서 이미 호출되므로 여기에 포함하지 않습니다.
    """

    # EVENT cadence 6종
    shot_event: ShotEventDetector | None = None
    rebound: ReboundDetector | None = None
    foul: FoulDetector | None = None
    screen: ScreenDetector | None = None
    fast_break: FastBreakDetector | None = None
    drive: DriveDetector | None = None

    # 역추적 4종
    assist: AssistDetector | None = None
    block: BlockDetector | None = None
    steal: StealDetector | None = None
    turnover: TurnoverDetector | None = None

    # SPECIAL 3종
    free_throw: FreeThrowDetector | None = None
    box_out: BoxOutDetector | None = None
    jump_ball: JumpBallDetector | None = None

    # 통계 증분 (기본)
    basic_stats: BasicStatsCalculator | None = None


# =============================================================================
# 통계 + 예측 + 기록 셋 (EVENT Cadence 증분)
# =============================================================================
@dataclass(slots=True)
class EventStatsSet:
    """
    통계/예측/기록 DI 컨테이너.

    EVENT Cadence에서 이벤트 발생 시 증분 갱신.
    """

    # statistics 나머지 6종 (BasicStats는 EventDetectorSet에)
    advanced_stats: AdvancedStatsCalculator | None = None
    shot_chart: ShotChartCalculator | None = None
    player_tracker: PlayerTrackerStatsCalculator | None = None
    team_stats: TeamStatsAggregator | None = None
    possession_stats: PossessionStatsCalculator | None = None
    four_factors: FourFactorsCalculator | None = None

    # predictive_models 4종
    win_probability: WinProbabilityModel | None = None
    epv: EPVModel | None = None
    shot_quality: ShotQualityModel | None = None
    lineup_projection: LineupProjectionModel | None = None

    # game_record 증분 3종
    game_sheet: GameSheetGenerator | None = None
    play_by_play: PlayByPlayTracker | None = None
    quarter_summary: QuarterSummaryGenerator | None = None

    # shot_location 증분 3종
    shot_zone_mapper: ShotZoneMapper | None = None
    shot_heatmap: ShotHeatmapCalculator | None = None
    efficiency_by_zone: EfficiencyByZoneCalculator | None = None


# =============================================================================
# 실시간 코칭 + 검증 셋
# =============================================================================
@dataclass(slots=True)
class EventRealtimeSet:
    """
    실시간 코칭/검증 DI 컨테이너.

    EVENT Cadence에서 이벤트 트리거 시 실행.
    """

    # coaching_intelligence 3종
    realtime_advisor: RealtimeAdvisor | None = None
    substitution_optimizer: SubstitutionOptimizer | None = None
    endgame_strategist: EndgameStrategist | None = None

    # live_workspace 3종
    live_validator: LiveEventValidator | None = None
    manual_tagger: ManualEventTagger | None = None
    correction_sync: CorrectionSync | None = None

    # motion_analysis (Stage2 트리거)
    action_classifier: ActionClassifier | None = None


# =============================================================================
# 이벤트 레코드
# =============================================================================
@dataclass(slots=True)
class DetectedEvent:
    """
    감지된 경기 이벤트.

    Attributes:
        event_type: 이벤트 유형 (예: "shot_made", "personal_foul")
        frame_index: 감지 프레임
        confidence: 감지 신뢰도 (0~1)
        player_id: 관련 선수 ID
        team_id: 관련 팀 ID
        source_detector: 감지기 이름
        details: 추가 상세 정보
    """

    event_type: str = ""
    frame_index: int = 0
    confidence: float = 0.0
    player_id: str = ""
    team_id: str = ""
    source_detector: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 파이프라인 결과
# =============================================================================
@dataclass(slots=True)
class EventPipelineResult:
    """
    🟠 EVENT 파이프라인 결과.

    Attributes:
        frame_index: 프레임 인덱스
        detected_events: 감지된 이벤트 목록
        num_events: 감지된 이벤트 수
        stats_updated: 통계 증분 갱신 건수
        referee_triggered: AI 심판 평가 트리거 여부
        processing_time_ms: 처리 시간 (ms)
    """

    frame_index: int = 0
    detected_events: list[DetectedEvent] = field(default_factory=list)
    num_events: int = 0
    stats_updated: int = 0
    referee_triggered: bool = False
    processing_time_ms: float = 0.0


# =============================================================================
# AI 심판 위임 콜백 타입
# =============================================================================
RefereeCallback = Callable[[int, list[DetectedEvent]], list[DetectedEvent]]


# =============================================================================
# EVENT 파이프라인
# =============================================================================
class EventPipeline:
    """
    🟠 EVENT 등급 파이프라인.

    13종 이벤트 감지기를 직접 호출하고, 감지된 이벤트로
    통계를 증분 갱신하며, 파울/바이올레이션 시 AI 심판에 위임합니다.
    """

    __slots__ = (
        "_detectors",
        "_stats_set",
        "_realtime_set",
        "_referee_callback",
        "_cadence_config",
        "_event_history",
        "_total_events",
        "_total_runs",
        "_lock",
    )

    def __init__(
        self,
        detectors: EventDetectorSet | None = None,
        stats_set: EventStatsSet | None = None,
        realtime_set: EventRealtimeSet | None = None,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        self._detectors: EventDetectorSet = detectors or EventDetectorSet()
        self._stats_set: EventStatsSet = stats_set or EventStatsSet()
        self._realtime_set: EventRealtimeSet = realtime_set or EventRealtimeSet()
        self._referee_callback: RefereeCallback | None = None
        self._cadence_config = cadence_config or CadenceConfig()
        self._event_history: list[DetectedEvent] = []
        self._total_events: int = 0
        self._total_runs: int = 0
        self._lock: RLock = RLock()

    def set_referee_callback(self, callback: RefereeCallback) -> None:
        """AI 심판 위임 콜백 설정."""
        self._referee_callback = callback
        _logger.info("AI 심판 콜백 설정 완료")

    # =========================================================================
    # 파이프라인 실행
    # =========================================================================
    def process_events(
        self,
        frame_index: int = 0,
        trigger_keys: frozenset[str] = frozenset(),
        frame_data: Any = None,
    ) -> EventPipelineResult:
        """
        이벤트 파이프라인 실행.

        13종 감지기를 Cadence 순서대로 호출하고,
        감지된 이벤트로 통계를 증분 갱신합니다.

        Args:
            frame_index: 현재 프레임 인덱스
            trigger_keys: 활성화된 트리거 키 집합
            frame_data: 프레임 분석 결과 (각 감지기 Input을 속성으로 보유)

        Returns:
            EventPipelineResult
        """
        t0 = time.perf_counter()
        all_events: list[DetectedEvent] = []
        stats_updated = 0
        referee_triggered = False
        d = self._detectors

        # -----------------------------------------------------------------
        # 1. EVENT cadence 감지기 6종
        # -----------------------------------------------------------------
        if "pending_shooting" in trigger_keys:
            self._try_detect(d.shot_event, "process_release",
                             frame_data, "shot_release_input", "shot_event", all_events)
            self._try_detect(d.shot_event, "process_result",
                             frame_data, "shot_result_input", "shot_event", all_events)
            self._try_detect(d.rebound, "process_rebound",
                             frame_data, "rebound_input", "rebound", all_events)

        if "pending_foul_contact" in trigger_keys:
            self._try_detect(d.foul, "detect_foul",
                             frame_data, "foul_input", "foul", all_events)

        # 스크린/속공/드라이브 — 이벤트 트리거 시 항상
        self._try_detect(d.screen, "detect_screen",
                         frame_data, "screen_input", "screen", all_events)
        self._try_detect(d.fast_break, "process_event",
                         frame_data, "fast_break_input", "fast_break", all_events)
        self._try_detect(d.drive, "process_event",
                         frame_data, "drive_input", "drive", all_events)

        # -----------------------------------------------------------------
        # 2. 역추적 감지기 4종
        # -----------------------------------------------------------------
        self._try_detect_multi(d.assist, "detect_assist",
                               frame_data, "assist_input", "assist", all_events)
        self._try_detect(d.block, "detect_block",
                         frame_data, "block_input", "block", all_events)
        self._try_detect(d.steal, "detect_steal",
                         frame_data, "steal_input", "steal", all_events)
        self._try_detect(d.turnover, "detect_turnover",
                         frame_data, "turnover_input", "turnover", all_events)

        # -----------------------------------------------------------------
        # 3. SPECIAL 감지기 3종
        # -----------------------------------------------------------------
        self._try_detect(d.free_throw, "process_attempt",
                         frame_data, "free_throw_input", "free_throw", all_events)
        self._try_detect(d.box_out, "detect_box_out",
                         frame_data, "box_out_input", "box_out", all_events)
        self._try_detect(d.jump_ball, "detect_jump_ball",
                         frame_data, "jump_ball_input", "jump_ball", all_events)

        # -----------------------------------------------------------------
        # 4. 통계 증분 갱신 (BasicStats + EventStatsSet)
        # -----------------------------------------------------------------
        if d.basic_stats is not None:
            for det_event in all_events:
                game_event = det_event.details.get("game_event")
                if game_event is not None:
                    try:
                        if d.basic_stats.process_event(game_event):
                            stats_updated += 1
                    except Exception:
                        _logger.exception("BasicStatsCalculator 오류")

        # EventStatsSet 증분 갱신 (statistics 6 + predictive 4 + game_record 3 + shot_location 3)
        ss = self._stats_set
        for name, module, method_name in [
            ("advanced_stats", ss.advanced_stats, "process_event"),
            ("shot_chart", ss.shot_chart, "process_event"),
            ("player_tracker", ss.player_tracker, "process_event"),
            ("team_stats", ss.team_stats, "process_event"),
            ("possession_stats", ss.possession_stats, "process_event"),
            ("four_factors", ss.four_factors, "process_event"),
            ("win_probability", ss.win_probability, "update"),
            ("epv", ss.epv, "update"),
            ("shot_quality", ss.shot_quality, "update"),
            ("lineup_projection", ss.lineup_projection, "update"),
            ("game_sheet", ss.game_sheet, "process_event"),
            ("play_by_play", ss.play_by_play, "process_event"),
            ("quarter_summary", ss.quarter_summary, "process_event"),
            ("shot_zone_mapper", ss.shot_zone_mapper, "process_event"),
            ("shot_heatmap", ss.shot_heatmap, "process_event"),
            ("efficiency_by_zone", ss.efficiency_by_zone, "process_event"),
        ]:
            if module is not None:
                for det_event in all_events:
                    game_event = det_event.details.get("game_event")
                    if game_event is not None:
                        try:
                            method = getattr(module, method_name, None)
                            if method is not None:
                                method(game_event)
                                stats_updated += 1
                        except Exception:
                            _logger.exception("%s 증분 오류", name)

        # -----------------------------------------------------------------
        # 4-2. 실시간 코칭 + 검증 (EventRealtimeSet)
        # -----------------------------------------------------------------
        rs = self._realtime_set
        for name, module, method_name in [
            ("realtime_advisor", rs.realtime_advisor, "process"),
            ("substitution_optimizer", rs.substitution_optimizer, "process"),
            ("endgame_strategist", rs.endgame_strategist, "process"),
            ("live_validator", rs.live_validator, "validate"),
            ("correction_sync", rs.correction_sync, "process"),
            ("action_classifier", rs.action_classifier, "classify"),
        ]:
            if module is not None and frame_data is not None:
                try:
                    method = getattr(module, method_name, None)
                    if method is not None:
                        inp = getattr(frame_data, f"{name}_input", None)
                        if inp is not None:
                            # action_classifier.classify(candidates, snapshots) 시그니처 대응
                            if name == "action_classifier":
                                candidates = getattr(inp, "candidates", None) or []
                                snapshots = getattr(inp, "snapshots", None) or []
                                if candidates and snapshots:
                                    method(candidates, snapshots)
                            else:
                                method(inp)
                except Exception:
                    _logger.exception("%s 실시간 오류", name)

        # -----------------------------------------------------------------
        # 5. AI 심판 위임
        # -----------------------------------------------------------------
        if self._referee_callback is not None:
            has_referee_event = any(
                e.event_type in _REFEREE_TRIGGER_TYPES for e in all_events
            )
            has_referee_trigger = (
                "pending_foul_contact" in trigger_keys
                or "pending_violation" in trigger_keys
            )
            if has_referee_event or has_referee_trigger:
                try:
                    referee_events = self._referee_callback(
                        frame_index, all_events,
                    )
                    if referee_events:
                        all_events.extend(referee_events)
                    referee_triggered = True
                except Exception:
                    _logger.exception("AI 심판 콜백 오류")

        # -----------------------------------------------------------------
        # 결과
        # -----------------------------------------------------------------
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = EventPipelineResult(
            frame_index=frame_index,
            detected_events=all_events,
            num_events=len(all_events),
            stats_updated=stats_updated,
            referee_triggered=referee_triggered,
            processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_runs += 1
            self._total_events += len(all_events)
            self._event_history.extend(all_events)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

        return result

    # =========================================================================
    # 감지기 호출 헬퍼
    # =========================================================================
    @staticmethod
    def _try_detect(
        detector: Any,
        method_name: str,
        frame_data: Any,
        input_attr: str,
        source: str,
        out: list[DetectedEvent],
    ) -> None:
        """단일 GameEvent 반환 감지기 호출."""
        if detector is None or frame_data is None:
            return
        input_data = getattr(frame_data, input_attr, None)
        if input_data is None:
            return
        try:
            method = getattr(detector, method_name)
            event = method(input_data)
            if event is not None:
                out.append(EventPipeline._wrap_event(event, source))
        except Exception:
            _logger.exception("%s.%s 오류", source, method_name)

    @staticmethod
    def _try_detect_multi(
        detector: Any,
        method_name: str,
        frame_data: Any,
        input_attr: str,
        source: str,
        out: list[DetectedEvent],
    ) -> None:
        """list[GameEvent] 반환 감지기 호출 (AssistDetector)."""
        if detector is None or frame_data is None:
            return
        input_data = getattr(frame_data, input_attr, None)
        if input_data is None:
            return
        try:
            method = getattr(detector, method_name)
            events = method(input_data)
            if events:
                for event in events:
                    out.append(EventPipeline._wrap_event(event, source))
        except Exception:
            _logger.exception("%s.%s 오류", source, method_name)

    @staticmethod
    def _wrap_event(game_event: GameEvent, source: str) -> DetectedEvent:
        """GameEvent → DetectedEvent 래핑."""
        et = getattr(game_event, "event_type", "")
        return DetectedEvent(
            event_type=et.value if hasattr(et, "value") else str(et),
            frame_index=getattr(game_event, "frame_index", 0),
            confidence=getattr(game_event, "confidence", 0.0),
            player_id=str(getattr(game_event, "primary_player_id", "") or ""),
            team_id=str(getattr(game_event, "team_id", "") or ""),
            source_detector=source,
            details={"game_event": game_event},
        )

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_events(self) -> int:
        """총 감지 이벤트 수."""
        return self._total_events

    @property
    def total_runs(self) -> int:
        """총 실행 횟수."""
        return self._total_runs

    @property
    def detector_count(self) -> int:
        """연결된 감지기 수 (None 아닌 것만)."""
        d = self._detectors
        return sum(1 for attr in (
            d.shot_event, d.rebound, d.foul,
            d.screen, d.fast_break, d.drive,
            d.assist, d.block, d.steal, d.turnover,
            d.free_throw, d.box_out, d.jump_ball,
        ) if attr is not None)

    def get_recent_events(self, count: int = 10) -> list[DetectedEvent]:
        """최근 이벤트 조회 (방어적 복사)."""
        with self._lock:
            return list(self._event_history[-count:])

    def reset(self) -> None:
        """이력 초기화 (감지기 유지)."""
        with self._lock:
            self._event_history.clear()
            self._total_events = 0
            self._total_runs = 0

    def __repr__(self) -> str:
        return (
            f"EventPipeline(runs={self._total_runs}, "
            f"events={self._total_events}, "
            f"detectors={self.detector_count}/13)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "EventDetectorSet",
    "EventStatsSet",
    "EventRealtimeSet",
    "DetectedEvent",
    "EventPipelineResult",
    "RefereeCallback",
    "EventPipeline",
]

__version__ = "1.0.0"
