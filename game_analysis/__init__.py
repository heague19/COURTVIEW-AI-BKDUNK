# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis
설명: Layer 5 — 경기 분석 모듈 루트 패키지
      5개 Phase 그룹, 27개 하위 모듈.

      game_state/          Phase 1 — 경기 상태 (3모듈)
        game_management      1A: 기록원 대체
        event_detection      1B: 16종 이벤트 감지
        live_workspace       1C: 실시간 이벤트 검증/보정

      stats/               Phase 2 — 통계·예측 (2모듈)
        statistics           기본/고급 통계
        predictive_models    예측 모델 (WP/EPV/xFG%/라인업)

      analysis/            Phase 3 — 분석 (12모듈)
        team/                팀 전술 공수
          tactical_analysis    공격 전술
          defensive_analysis   수비 분석
          transition_analysis  전환 공수
          play_type_analysis   플레이 유형별
        player/              선수·라인업
          individual_analysis  개인 심층
          lineup_analysis      라인업 분석
          rotation_analysis    로테이션
        context/             상황·흐름
          spatial_analysis     공간/위치
          game_flow            경기 흐름
          situation_splits     상황별 효율
          special_situation    특수 상황
          season_analysis      시즌 분석

      output/              Phase 4 — 출력·코칭 (9모듈)
        shot_location        슛 위치 분석
        highlight            하이라이트 감지/클립
        game_record          기록지/PBP/리포트
        video_editing        비디오 편집/내보내기
        film_session         필름 세션/개인 리뷰
        coaching_intelligence 실시간 코칭
        pre_game             경기 전 준비
        scouting             상대팀 스카우팅
        matchup_analysis     매치업 분석

      data_extraction/     Phase 5 — 데이터셋 추출 (7파일)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# Phase 1A: game_state/game_management — 경기 상태 관리 (6파일)
# =============================================================================
from game_analysis.game_state.game_management import (
    ClockManager,
    ClockManagerConfig,
    FoulManager,
    FoulManagerConfig,
    TimeoutManager,
    TimeoutManagerConfig,
    SubstitutionManager,
    SubstitutionManagerConfig,
    RecordCorrector,
    RecordCorrectorConfig,
    OfficialFormatExporter,
    OfficialFormatExporterConfig,
)

# =============================================================================
# Phase 1B: game_state/event_detection — 16종 이벤트 감지 (16파일)
# =============================================================================
from game_analysis.game_state.event_detection import (
    ShotEventDetector,
    ShotEventDetectorConfig,
    FreeThrowDetector,
    FreeThrowDetectorConfig,
    ScoreDetector,
    ScoreDetectorConfig,
    ReboundDetector,
    ReboundDetectorConfig,
    AssistDetector,
    AssistDetectorConfig,
    BlockDetector,
    BlockDetectorConfig,
    StealDetector,
    StealDetectorConfig,
    TurnoverDetector,
    TurnoverDetectorConfig,
    FoulDetector,
    FoulDetectorConfig,
    PossessionTracker,
    PossessionTrackerConfig,
    DeadBallDetector,
    DeadBallDetectorConfig,
    ScreenDetector,
    ScreenDetectorConfig,
    FastBreakDetector,
    FastBreakDetectorConfig,
    DriveDetector,
    DriveDetectorConfig,
    BoxOutDetector,
    BoxOutDetectorConfig,
    JumpBallDetector,
    JumpBallDetectorConfig,
)

# =============================================================================
# Phase 1C: game_state/live_workspace — 실시간 이벤트 검증/보정 (3파일)
# =============================================================================
from game_analysis.game_state.live_workspace import (
    LiveEventValidator,
    LiveEventValidatorConfig,
    ValidationResult,
    ValidationStatus,
    RejectionReason,
    GameContext,
    ManualEventTagger,
    ManualEventTaggerConfig,
    EventTag,
    TagResult,
    TagCategory,
    OverrideField,
    OverrideRecord,
    CorrectionSync,
    CorrectionSyncConfig,
    CorrectionRecord,
    CorrectionType,
    RecalcTrigger,
    RecalcScope,
    TriggerStatus,
)

# =============================================================================
# Phase 2: stats/statistics — 기본/고급 통계 (7파일)
# =============================================================================
from game_analysis.stats.statistics import (
    BasicStatsCalculator,
    BasicStatsConfig,
    AdvancedStatsCalculator,
    AdvancedStatsConfig,
    ShotChartCalculator,
    ShotChartConfig,
    PlayerTrackerStatsCalculator,
    PlayerTrackerConfig,
    TeamStatsAggregator,
    TeamStatsConfig,
    PossessionStatsCalculator,
    PossessionStatsConfig,
    FourFactorsCalculator,
    FourFactorsConfig,
)

# =============================================================================
# Phase 2: stats/predictive_models — 예측 모델 (4파일)
# =============================================================================
from game_analysis.stats.predictive_models import (
    WinProbabilityModel,
    WinProbabilityConfig,
    EPVModel,
    EPVConfig,
    ShotQualityModel,
    ShotQualityConfig,
    LineupProjectionModel,
    LineupProjectionConfig,
)

# =============================================================================
# Phase 3: analysis/team/tactical_analysis — 전술 분석 (6파일)
# =============================================================================
from game_analysis.analysis.team.tactical_analysis import (
    ScreenAnalyzer,
    ScreenAnalyzerConfig,
    FastBreakAnalyzer,
    FastBreakAnalyzerConfig,
    SetPlayRecognizer,
    SetPlayRecognizerConfig,
    PassingNetworkAnalyzer,
    PassingNetworkConfig,
    PossessionAnalyzer,
    PossessionAnalyzerConfig,
    TurnoverAnalyzer,
    TurnoverAnalyzerConfig,
)

# =============================================================================
# Phase 3: analysis/team/defensive_analysis — 수비 분석 (5파일)
# =============================================================================
from game_analysis.analysis.team.defensive_analysis import (
    DefenseTypeClassifier,
    DefenseTypeClassifierConfig,
    DefensiveRotationAnalyzer,
    DefensiveRotationConfig,
    BoxOutAnalyzer,
    BoxOutAnalyzerConfig,
    CloseoutAnalyzer,
    CloseoutAnalyzerConfig,
    HelpRecoveryAnalyzer,
    HelpRecoveryConfig,
)

# =============================================================================
# Phase 3: analysis/team/transition_analysis — 전환 공수 (3파일)
# =============================================================================
from game_analysis.analysis.team.transition_analysis import (
    TransitionOffenseAnalyzer,
    TransitionOffenseConfig,
    TransitionDefenseAnalyzer,
    TransitionDefenseConfig,
    TransitionEfficiencyAnalyzer,
    TransitionEfficiencyConfig,
)

# =============================================================================
# Phase 3: analysis/team/play_type_analysis — 플레이 유형별 (6파일)
# =============================================================================
from game_analysis.analysis.team.play_type_analysis import (
    PickAndRollAnalyzer,
    PickAndRollConfig,
    PnRRole,
    PnRDefenseType,
    IsolationAnalyzer,
    IsolationConfig,
    IsoResult,
    PostUpAnalyzer,
    PostUpConfig,
    PostUpMove,
    SpotUpAnalyzer,
    SpotUpConfig,
    SpotUpContest,
    FreeThrowAnalyzer,
    FreeThrowAnalyzerConfig,
    FreeThrowContext,
    PlayTypeEfficiencyAnalyzer,
    PlayTypeEfficiencyConfig,
)

# =============================================================================
# Phase 3: analysis/player/individual_analysis — 개인 심층 (6파일)
# =============================================================================
from game_analysis.analysis.player.individual_analysis import (
    DriveAnalyzer,
    DriveAnalyzerConfig,
    OffBallMovementAnalyzer,
    OffBallMovementConfig,
    ClutchPerformanceAnalyzer,
    ClutchPerformanceConfig,
    FatigueAnalyzer,
    FatigueAnalyzerConfig,
    PlayerImpactAnalyzer,
    PlayerImpactConfig,
    ReboundAnalyzer,
    ReboundAnalysisConfig,
)

# =============================================================================
# Phase 3: analysis/player/lineup_analysis — 라인업 분석 (3파일)
# =============================================================================
from game_analysis.analysis.player.lineup_analysis import (
    LineupTracker,
    LineupTrackerConfig,
    LineupEfficiencyAnalyzer,
    LineupEfficiencyConfig,
    PlayerSynergyAnalyzer,
    PlayerSynergyConfig,
)

# =============================================================================
# Phase 3: analysis/player/rotation_analysis — 로테이션 분석 (4파일)
# =============================================================================
from game_analysis.analysis.player.rotation_analysis import (
    RotationTracker,
    RotationTrackerConfig,
    StaggerAnalyzer,
    StaggerAnalyzerConfig,
    BenchUnitAnalyzer,
    BenchUnitAnalyzerConfig,
    UnitType,
    RestPeriodAnalyzer,
    RestPeriodAnalyzerConfig,
)

# =============================================================================
# Phase 3: analysis/context/spatial_analysis — 공간/위치 분석 (4파일)
# =============================================================================
from game_analysis.analysis.context.spatial_analysis import (
    FloorSpacingAnalyzer,
    FloorSpacingConfig,
    MovementHeatmapAnalyzer,
    MovementHeatmapConfig,
    ZoneControlAnalyzer,
    ZoneControlConfig,
    PaintAnalyzer,
    PaintAnalysisConfig,
)

# =============================================================================
# Phase 3: analysis/context/game_flow — 경기 흐름 분석 (4파일)
# =============================================================================
from game_analysis.analysis.context.game_flow import (
    MomentumTracker,
    MomentumTrackerConfig,
    TempoAnalyzer,
    TempoAnalyzerConfig,
    TimeoutEffectivenessAnalyzer,
    TimeoutEffectivenessConfig,
    LeadManagementAnalyzer,
    LeadManagementConfig,
)

# =============================================================================
# Phase 3: analysis/context/situation_splits — 상황별 효율 분석 (4파일)
# =============================================================================
from game_analysis.analysis.context.situation_splits import (
    PeriodSplitsAnalyzer,
    PeriodSplitsConfig,
    ScoreMarginSplitsAnalyzer,
    ScoreMarginSplitsConfig,
    MarginBucket,
    ShotClockSplitsAnalyzer,
    ShotClockSplitsConfig,
    ShotClockSegment,
    GameContextAnalyzer,
    GameContextConfig,
)

# =============================================================================
# Phase 3: analysis/context/special_situation — 특수 상황 분석 (4파일)
# =============================================================================
from game_analysis.analysis.context.special_situation import (
    ATOPlayAnalyzer,
    ATOPlayAnalyzerConfig,
    OOBPlayAnalyzer,
    OOBPlayAnalyzerConfig,
    OOBType,
    FoulGameAnalyzer,
    FoulGameAnalyzerConfig,
    LastPossessionAnalyzer,
    LastPossessionConfig,
    LastPossessionType,
)

# =============================================================================
# Phase 3: analysis/context/season_analysis — 시즌 분석 (3파일)
# =============================================================================
from game_analysis.analysis.context.season_analysis import (
    SeasonAggregator,
    SeasonAggregatorConfig,
    TrendTracker,
    TrendTrackerConfig,
    TrendDirection,
    BenchmarkComparator,
    BenchmarkComparatorConfig,
)

# =============================================================================
# Phase 4: output/shot_location — 슛 위치 분석 (3파일)
# =============================================================================
from game_analysis.output.shot_location import (
    ShotZoneMapper,
    ShotZoneMapperConfig,
    LeagueStandard,
    ShotHeatmapAnalyzer,
    ShotHeatmapConfig,
    ZoneEfficiencyAnalyzer,
    ZoneEfficiencyConfig,
)

# =============================================================================
# Phase 4: output/coaching_intelligence — 코칭 인텔리전스 (3파일)
# =============================================================================
from game_analysis.output.coaching_intelligence import (
    RealtimeAdvisor,
    RealtimeAdvisorConfig,
    RecommendationType,
    Urgency,
    SubstitutionOptimizer,
    SubstitutionOptimizerConfig,
    EndgameStrategist,
    EndgameStrategistConfig,
    EndgameAction,
    GameSituation,
)

# =============================================================================
# Phase 4: output/video_editing — 비디오 편집 (4파일)
# =============================================================================
from game_analysis.output.video_editing import (
    ClipManager,
    ClipManagerConfig,
    AnnotationOverlayManager,
    AnnotationOverlayConfig,
    MultiAngleSyncManager,
    MultiAngleSyncConfig,
    SyncLayout,
    ExportManager,
    ExportManagerConfig,
    ExportStatus,
)

# =============================================================================
# Phase 4: output/film_session — 필름 세션 (3파일)
# =============================================================================
from game_analysis.output.film_session import (
    FilmSessionBuilder,
    FilmSessionBuilderConfig,
    PlayerClipPackageManager,
    PlayerClipPackageConfig,
    ClipCategory,
    TeachingPointGenerator,
    TeachingPointGeneratorConfig,
)

# =============================================================================
# Phase 4: output/pre_game — 경기 전 분석 (5파일)
# =============================================================================
from game_analysis.output.pre_game import (
    GamePlanGenerator,
    GamePlanGeneratorConfig,
    GamePlanExecutionTracker,
    GamePlanExecutionTrackerConfig,
    DefensiveAssignmentPlanner,
    DefensiveAssignmentPlannerConfig,
    OffensivePrioritySetter,
    OffensivePrioritySetterConfig,
    PreGameBriefingBuilder,
    PreGameBriefingBuilderConfig,
)

# =============================================================================
# Phase 4: output/highlight — 하이라이트 (3파일)
# =============================================================================
from game_analysis.output.highlight import (
    HighlightDetector,
    HighlightDetectorConfig,
    ExcitementScorer,
    ExcitementScorerConfig,
    ClipExtractor,
    ClipExtractorConfig,
)

# =============================================================================
# Phase 4: output/game_record — 기록지/PBP/리포트 (4파일)
# =============================================================================
from game_analysis.output.game_record import (
    GameSheetGenerator,
    GameSheetConfig,
    PlayByPlayRecorder,
    PlayByPlayConfig,
    QuarterSummaryGenerator,
    QuarterSummaryConfig,
    GameReportBuilder,
    GameReportConfig,
)

# =============================================================================
# Phase 4: output/scouting — 스카우팅 (7파일)
# =============================================================================
from game_analysis.output.scouting import (
    OpponentProfiler,
    OpponentProfilerConfig,
    TendencyAnalyzer,
    TendencyAnalyzerConfig,
    WeaknessFinder,
    WeaknessFinderConfig,
    HeadToHeadAnalyzer,
    HeadToHeadConfig,
    ScoutingReportBuilder,
    ScoutingReportConfig,
    PlayPatternMatcher,
    PlayPatternMatcherConfig,
    RefereeTendencyAnalyzer,
    RefereeTendencyConfig,
)

# =============================================================================
# Phase 4: output/matchup_analysis — 매치업 분석 (3파일)
# =============================================================================
from game_analysis.output.matchup_analysis import (
    MatchupTracker,
    MatchupTrackerConfig,
    ContestAnalyzer,
    ContestAnalyzerConfig,
    MatchupEvaluator,
    MatchupEvaluatorConfig,
)

# =============================================================================
# Phase 5: data_extraction — 데이터셋 추출 (7파일)
# =============================================================================
from game_analysis.data_extraction import (
    FrameRecordExtractor,
    FrameRecordExtractorConfig,
    PossessionRecordExtractor,
    PossessionRecordExtractorConfig,
    GameRecordExtractor,
    GameRecordExtractorConfig,
    EventCorrectionExtractor,
    EventCorrectionExtractorConfig,
    TacticalSequenceExtractor,
    TacticalSequenceExtractorConfig,
    PlayerPerformanceExtractor,
    PlayerPerformanceExtractorConfig,
    PredictionOutcomeExtractor,
    PredictionOutcomeExtractorConfig,
)

# =============================================================================
# Export 정의
# =============================================================================
__all__ = [
    # Phase 1A: game_state/game_management
    "ClockManager", "ClockManagerConfig",
    "FoulManager", "FoulManagerConfig",
    "TimeoutManager", "TimeoutManagerConfig",
    "SubstitutionManager", "SubstitutionManagerConfig",
    "RecordCorrector", "RecordCorrectorConfig",
    "OfficialFormatExporter", "OfficialFormatExporterConfig",
    # Phase 1B: game_state/event_detection (16종)
    "ShotEventDetector", "ShotEventDetectorConfig",
    "FreeThrowDetector", "FreeThrowDetectorConfig",
    "ScoreDetector", "ScoreDetectorConfig",
    "ReboundDetector", "ReboundDetectorConfig",
    "AssistDetector", "AssistDetectorConfig",
    "BlockDetector", "BlockDetectorConfig",
    "StealDetector", "StealDetectorConfig",
    "TurnoverDetector", "TurnoverDetectorConfig",
    "FoulDetector", "FoulDetectorConfig",
    "PossessionTracker", "PossessionTrackerConfig",
    "DeadBallDetector", "DeadBallDetectorConfig",
    "ScreenDetector", "ScreenDetectorConfig",
    "FastBreakDetector", "FastBreakDetectorConfig",
    "DriveDetector", "DriveDetectorConfig",
    "BoxOutDetector", "BoxOutDetectorConfig",
    "JumpBallDetector", "JumpBallDetectorConfig",
    # Phase 1C: game_state/live_workspace
    "LiveEventValidator", "LiveEventValidatorConfig",
    "ValidationResult", "ValidationStatus", "RejectionReason", "GameContext",
    "ManualEventTagger", "ManualEventTaggerConfig",
    "EventTag", "TagResult", "TagCategory", "OverrideField", "OverrideRecord",
    "CorrectionSync", "CorrectionSyncConfig",
    "CorrectionRecord", "CorrectionType",
    "RecalcTrigger", "RecalcScope", "TriggerStatus",
    # Phase 2: stats/statistics
    "BasicStatsCalculator", "BasicStatsConfig",
    "AdvancedStatsCalculator", "AdvancedStatsConfig",
    "ShotChartCalculator", "ShotChartConfig",
    "PlayerTrackerStatsCalculator", "PlayerTrackerConfig",
    "TeamStatsAggregator", "TeamStatsConfig",
    "PossessionStatsCalculator", "PossessionStatsConfig",
    "FourFactorsCalculator", "FourFactorsConfig",
    # Phase 2: stats/predictive_models
    "WinProbabilityModel", "WinProbabilityConfig",
    "EPVModel", "EPVConfig",
    "ShotQualityModel", "ShotQualityConfig",
    "LineupProjectionModel", "LineupProjectionConfig",
    # Phase 3: analysis/team/tactical_analysis
    "ScreenAnalyzer", "ScreenAnalyzerConfig",
    "FastBreakAnalyzer", "FastBreakAnalyzerConfig",
    "SetPlayRecognizer", "SetPlayRecognizerConfig",
    "PassingNetworkAnalyzer", "PassingNetworkConfig",
    "PossessionAnalyzer", "PossessionAnalyzerConfig",
    "TurnoverAnalyzer", "TurnoverAnalyzerConfig",
    # Phase 3: analysis/team/defensive_analysis
    "DefenseTypeClassifier", "DefenseTypeClassifierConfig",
    "DefensiveRotationAnalyzer", "DefensiveRotationConfig",
    "BoxOutAnalyzer", "BoxOutAnalyzerConfig",
    "CloseoutAnalyzer", "CloseoutAnalyzerConfig",
    "HelpRecoveryAnalyzer", "HelpRecoveryConfig",
    # Phase 3: analysis/team/transition_analysis
    "TransitionOffenseAnalyzer", "TransitionOffenseConfig",
    "TransitionDefenseAnalyzer", "TransitionDefenseConfig",
    "TransitionEfficiencyAnalyzer", "TransitionEfficiencyConfig",
    # Phase 3: analysis/team/play_type_analysis
    "PickAndRollAnalyzer", "PickAndRollConfig",
    "PnRRole", "PnRDefenseType",
    "IsolationAnalyzer", "IsolationConfig", "IsoResult",
    "PostUpAnalyzer", "PostUpConfig", "PostUpMove",
    "SpotUpAnalyzer", "SpotUpConfig", "SpotUpContest",
    "FreeThrowAnalyzer", "FreeThrowAnalyzerConfig", "FreeThrowContext",
    "PlayTypeEfficiencyAnalyzer", "PlayTypeEfficiencyConfig",
    # Phase 3: analysis/player/individual_analysis
    "DriveAnalyzer", "DriveAnalyzerConfig",
    "OffBallMovementAnalyzer", "OffBallMovementConfig",
    "ClutchPerformanceAnalyzer", "ClutchPerformanceConfig",
    "FatigueAnalyzer", "FatigueAnalyzerConfig",
    "PlayerImpactAnalyzer", "PlayerImpactConfig",
    "ReboundAnalyzer", "ReboundAnalysisConfig",
    # Phase 3: analysis/player/lineup_analysis
    "LineupTracker", "LineupTrackerConfig",
    "LineupEfficiencyAnalyzer", "LineupEfficiencyConfig",
    "PlayerSynergyAnalyzer", "PlayerSynergyConfig",
    # Phase 3: analysis/player/rotation_analysis
    "RotationTracker", "RotationTrackerConfig",
    "StaggerAnalyzer", "StaggerAnalyzerConfig",
    "BenchUnitAnalyzer", "BenchUnitAnalyzerConfig", "UnitType",
    "RestPeriodAnalyzer", "RestPeriodAnalyzerConfig",
    # Phase 3: analysis/context/spatial_analysis
    "FloorSpacingAnalyzer", "FloorSpacingConfig",
    "MovementHeatmapAnalyzer", "MovementHeatmapConfig",
    "ZoneControlAnalyzer", "ZoneControlConfig",
    "PaintAnalyzer", "PaintAnalysisConfig",
    # Phase 3: analysis/context/game_flow
    "MomentumTracker", "MomentumTrackerConfig",
    "TempoAnalyzer", "TempoAnalyzerConfig",
    "TimeoutEffectivenessAnalyzer", "TimeoutEffectivenessConfig",
    "LeadManagementAnalyzer", "LeadManagementConfig",
    # Phase 3: analysis/context/situation_splits
    "PeriodSplitsAnalyzer", "PeriodSplitsConfig",
    "ScoreMarginSplitsAnalyzer", "ScoreMarginSplitsConfig", "MarginBucket",
    "ShotClockSplitsAnalyzer", "ShotClockSplitsConfig", "ShotClockSegment",
    "GameContextAnalyzer", "GameContextConfig",
    # Phase 3: analysis/context/special_situation
    "ATOPlayAnalyzer", "ATOPlayAnalyzerConfig",
    "OOBPlayAnalyzer", "OOBPlayAnalyzerConfig", "OOBType",
    "FoulGameAnalyzer", "FoulGameAnalyzerConfig",
    "LastPossessionAnalyzer", "LastPossessionConfig", "LastPossessionType",
    # Phase 3: analysis/context/season_analysis
    "SeasonAggregator", "SeasonAggregatorConfig",
    "TrendTracker", "TrendTrackerConfig", "TrendDirection",
    "BenchmarkComparator", "BenchmarkComparatorConfig",
    # Phase 4: output/shot_location
    "ShotZoneMapper", "ShotZoneMapperConfig", "LeagueStandard",
    "ShotHeatmapAnalyzer", "ShotHeatmapConfig",
    "ZoneEfficiencyAnalyzer", "ZoneEfficiencyConfig",
    # Phase 4: output/coaching_intelligence
    "RealtimeAdvisor", "RealtimeAdvisorConfig",
    "RecommendationType", "Urgency",
    "SubstitutionOptimizer", "SubstitutionOptimizerConfig",
    "EndgameStrategist", "EndgameStrategistConfig",
    "EndgameAction", "GameSituation",
    # Phase 4: output/video_editing
    "ClipManager", "ClipManagerConfig",
    "AnnotationOverlayManager", "AnnotationOverlayConfig",
    "MultiAngleSyncManager", "MultiAngleSyncConfig", "SyncLayout",
    "ExportManager", "ExportManagerConfig", "ExportStatus",
    # Phase 4: output/film_session
    "FilmSessionBuilder", "FilmSessionBuilderConfig",
    "PlayerClipPackageManager", "PlayerClipPackageConfig", "ClipCategory",
    "TeachingPointGenerator", "TeachingPointGeneratorConfig",
    # Phase 4: output/pre_game
    "GamePlanGenerator", "GamePlanGeneratorConfig",
    "GamePlanExecutionTracker", "GamePlanExecutionTrackerConfig",
    "DefensiveAssignmentPlanner", "DefensiveAssignmentPlannerConfig",
    "OffensivePrioritySetter", "OffensivePrioritySetterConfig",
    "PreGameBriefingBuilder", "PreGameBriefingBuilderConfig",
    # Phase 4: output/highlight
    "HighlightDetector", "HighlightDetectorConfig",
    "ExcitementScorer", "ExcitementScorerConfig",
    "ClipExtractor", "ClipExtractorConfig",
    # Phase 4: output/game_record
    "GameSheetGenerator", "GameSheetConfig",
    "PlayByPlayRecorder", "PlayByPlayConfig",
    "QuarterSummaryGenerator", "QuarterSummaryConfig",
    "GameReportBuilder", "GameReportConfig",
    # Phase 4: output/scouting
    "OpponentProfiler", "OpponentProfilerConfig",
    "TendencyAnalyzer", "TendencyAnalyzerConfig",
    "WeaknessFinder", "WeaknessFinderConfig",
    "HeadToHeadAnalyzer", "HeadToHeadConfig",
    "ScoutingReportBuilder", "ScoutingReportConfig",
    "PlayPatternMatcher", "PlayPatternMatcherConfig",
    "RefereeTendencyAnalyzer", "RefereeTendencyConfig",
    # Phase 4: output/matchup_analysis
    "MatchupTracker", "MatchupTrackerConfig",
    "ContestAnalyzer", "ContestAnalyzerConfig",
    "MatchupEvaluator", "MatchupEvaluatorConfig",
    # Phase 5: data_extraction
    "FrameRecordExtractor", "FrameRecordExtractorConfig",
    "PossessionRecordExtractor", "PossessionRecordExtractorConfig",
    "GameRecordExtractor", "GameRecordExtractorConfig",
    "EventCorrectionExtractor", "EventCorrectionExtractorConfig",
    "TacticalSequenceExtractor", "TacticalSequenceExtractorConfig",
    "PlayerPerformanceExtractor", "PlayerPerformanceExtractorConfig",
    "PredictionOutcomeExtractor", "PredictionOutcomeExtractorConfig",
]

__version__ = "1.0.0"
