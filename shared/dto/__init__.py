# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: __init__.py
설명: DTO 모듈 패키지 초기화 - 모든 Data Transfer Object 내보내기

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0
"""

# =============================================================================
# 기하학 기본형 DTO
# =============================================================================
from shared.dto.geometry_dto import (
    # 2D 기본형
    Point2D,
    Line2D,
    BoundingBox,
    Polygon2D,
    # 3D 기본형
    Point3D,
    Vector3D,
    Ray3D,
    BoundingBox3D,
    Plane3D,
    # 변환
    Pose2D,
    Pose3D,
    Trajectory3D,
    # 코트 좌표
    CourtCoordinate,
)

# =============================================================================
# 비디오 메타데이터 DTO
# =============================================================================
from shared.dto.video_dto import (
    # 열거형
    VideoFormat,
    VideoType,
    FrameStatus,
    VideoCodec,
    AudioCodec,
    # 데이터 클래스
    VideoResolution,
    VideoFileMetadata,
    FrameData,
    VideoSegment,
    VideoInfo,
)

# =============================================================================
# 카메라 정보 DTO
# =============================================================================
from shared.dto.camera_dto import (
    # 열거형
    CameraType,
    CameraState,
    ExposureMode,
    WhiteBalanceMode,
    FocusMode,
    # 데이터 클래스
    CameraInfo,
    CameraStatus,
    CameraConfig,
    CameraFrame,
    CameraPosition,
    CameraSetup,
    MultiCameraSetup,
)

# =============================================================================
# 캘리브레이션 DTO
# =============================================================================
from shared.dto.calibration_dto import (
    # 열거형
    CalibrationStatus,
    CalibrationMethod,
    # 내부 파라미터
    IntrinsicParams,
    DistortionCoeffs,
    CameraMatrix,
    # 외부 파라미터
    ExtrinsicParams,
    RotationMatrix,
    TranslationVector,
    # 행렬
    HomographyMatrix,
    FundamentalMatrix,
    EssentialMatrix,
    ProjectionMatrix,
    # 결과
    CalibrationResult,
    StereoCalibration,
    MultiCameraCalibration,
)

# =============================================================================
# 추적 데이터 DTO
# =============================================================================
from shared.dto.tracking_dto import (
    # 열거형
    TrackState,
    TrackSource,
    TrackedObjectType,
    # 데이터 클래스
    TrackHistory,
    KalmanState,
    Track,
    TrackAssociation,
    TrackingResult,
    MultiViewTrackingResult,
)

# =============================================================================
# 오클루전 데이터 DTO
# =============================================================================
from shared.dto.occlusion_dto import (
    # 데이터 클래스
    ViewVisibility,
    OccludedObject,
    OcclusionEvent,
    OcclusionResolution,
    OcclusionAnalysisResult,
)

# =============================================================================
# Re-ID 데이터 DTO
# =============================================================================
from shared.dto.reid_dto import (
    # 데이터 클래스
    ReIDFeature,
    GalleryEntry,
    ReIDGallery,
    ReIDMatch,
    ReIDResult,
)

# =============================================================================
# 포즈/스켈레톤 DTO (v2.0.0 신규 - v2.1.0 i18n 업데이트)
# =============================================================================
from shared.dto.pose_dto import (
    # 데이터 클래스
    Keypoint,
    JointAngle,  # get_description(lang) 메서드 추가됨
    Skeleton2D,
    Skeleton3D,
    PoseEstimationResult,
)

# =============================================================================
# 감지 결과 통합 DTO
# =============================================================================
from shared.dto.detection_dto import (
    # 열거형
    ObjectType,
    DetectionSource,
    # 데이터 클래스
    DetectedObject,
    DetectionConfig,
    DetectionResult,
    MultiViewDetectionResult,
)

# =============================================================================
# 공 감지/궤적 DTO
# =============================================================================
from shared.dto.ball_dto import (
    # 열거형
    TrajectoryType,
    BallShotResult,
    # 데이터 클래스
    BallDetection,
    BallTrajectory,
    ShotTrajectory,
    BallAnalysisResult,
)

# =============================================================================
# OCR 결과 DTO (v2.0.0 신규 - i18n 업데이트)
# =============================================================================
from shared.dto.ocr_dto import (
    # 열거형 (DTO 고유)
    OCRBackend,
    OCRStatus,
    # 데이터 클래스
    OCRResult,
    JerseyNumber,
    JerseyNumberVote,
    MultiViewOCRResult,
    OCRAnalysisResult,
)

# =============================================================================
# 3D 씬 데이터 DTO (v2.0.0 신규 - v2.2.0 i18n 업데이트)
# =============================================================================
from shared.dto.scene_dto import (
    # 열거형 (i18n 지원)
    SceneStatus,     # i18n: get_name(lang), to_korean property
    ObjectCategory,  # i18n: get_name(lang), to_korean property
    # 데이터 클래스
    SceneObject,     # __post_init__: confidence 클램핑 [0.0, 1.0]
    CourtModel,      # FIBA 기준 코트 모델 (28m×15m)
    HoopModel,       # FIBA 기준 골대 모델 (3.05m 높이)
    Scene3D,         # __post_init__: confidence 클램핑 [0.0, 1.0]
    SceneSnapshot,
    SceneTimeline,
    SceneMetadata,
)

# =============================================================================
# 선수 정보 DTO
# =============================================================================
from shared.dto.player_dto import (
    # 열거형
    Team,
    PlayerRole,
    PlayerPosition,
    # 데이터 클래스
    PlayerID,
    DetailedPlayerInfo,
    IdentificationSource,
    PlayerIdentification,
    PlayerHistoryEntry,
    ManagedPlayer,
    PlayerManager,
)

# =============================================================================
# 파이프라인 입출력 DTO (v1.0.0 - analysis_dto에서 리팩토링)
# =============================================================================
from shared.dto.pipeline_dto import (
    # 비디오 입력
    VideoSource,
    VideoMetadata,
    # 파이프라인 옵션
    PipelineOptions,
    # 파이프라인 요청
    BasePipelineRequest,
    GameAnalysisRequest,
    RefereeAnalysisRequest,
    PipelineRequest,
    # 파이프라인 진행 상태
    PipelineProgress,
    # 파이프라인 결과
    PipelineResultBase,
    GameAnalysisResult,
    # AI 심판 결과 (중첩 모델 포함)
    ViolationCounts,
    FoulCounts,
    RefereeAnalysisResult,
    # Backend 동기화
    SyncEventType,
    BackendSyncPayload,
)

# =============================================================================
# 피드백 관련 DTO (기존)
# =============================================================================
from shared.dto.feedback_dto import (
    # 열거형
    FeedbackCategory,
    FeedbackPriority,
    FeedbackType,
    BodyPart,
    MotionPhase,
    FeedbackSource,
    # 영상 증거 & 원인 요소
    VideoClipReference,
    CausalFactor,
    # 세부 피드백
    FeedbackItem,
    MotionScore,
    MotionComparison,
    # 피드백 요약
    FeedbackSummary,
    # 훈련 추천
    TrainingRecommendation,
    TrainingPlan,
    # 진행 추적
    ProgressMetric,
    ProgressReport,
    # 학습 시스템용
    UserFeedback,
    FeedbackEffectiveness,
    FeedbackResult,
)

# =============================================================================
# 경기 분석 관련 DTO (기존 - v2.0.0 i18n 업데이트)
# =============================================================================
from shared.dto.game_dto import (
    # 선수/팀 정보
    PlayerInfo,
    TeamInfo,
    # 슛 관련 (시각화 메서드 포함)
    ShotAttempt,
    ZoneStatistics,
    ShotChart,
    # 경기 이벤트
    GameEvent,
    # 하이라이트
    HighlightClip,
    HighlightReel,
    # 경기 통계 (통계 계산 헬퍼 포함)
    PlayerStats,
    TeamStats,
    GameStats,
    # AI 심판 - 이벤트 DTO
    ViolationEvent,
    FoulEvent,
    RefereeDecision,
    ReviewSuggestion,
    # AI 심판 - 감지 결과 DTO
    ViolationDetection,
    FoulDetection,
    GameRefereeReport,
)

# =============================================================================
# AI 심판 시스템 DTO (v2.3.0 신규 - Desktop Edition)
# =============================================================================
from shared.dto.referee_dto import (
    # 판정 시스템
    RefereeCall,
    RefereePosition,
    CallContext,
    # 리뷰 시스템
    ReplayReview,
    ChallengeRequest,
    # 심판 평가
    CallAccuracy,
    ConsistencyMetrics,
    RefereePerformance,
    # 경기 관리
    ClockAdjustment,
    TimeoutManagement,
    SubstitutionRecord,
    GameClockManagement,
    # 로컬 열거형 (DTO 전용)
    AdvantageState,
    UnsportsmanlikeActionType,
    # 어드밴티지/비신사적 행위
    AdvantageDecision,
    UnsportsmanlikeBehavior,
    # 통합 리포트
    RefereeReport,
)

# =============================================================================
# 생체역학 DTO (v4.0.0 신규 - Layer 3)
# =============================================================================
from shared.dto.biomechanics_dto import (
    # 운동학
    JointKinematics,
    BodySegmentData,
    # 동역학
    BalanceMetrics,
    EnergyMetrics,
    ForceEstimate,
    # 패턴 분류
    MotionPatternData,
    # 인체측정
    AnthropometryData,
    # 이벤트 데이터
    LandingImpactData,
    ContactEventData,
    ExplosiveEventData,
    DirectionChangeData,
    # 시퀀스 요약 데이터
    TrajectoryProfileData,
    MomentumProfileData,
    EnergyProfileData,
    BalanceHistoryData,
    # 종합 결과
    BiomechanicalFrame,
    BiomechanicalResult,
)

# =============================================================================
# 동작 분석 DTO (v4.0.0 신규 - Layer 4)
# =============================================================================
from shared.dto.motion_dto import (
    # 열거형
    ActionType,
    ContestLevel,
    DribbleType,
    PassType,
    DefensiveActionType,
    MovementType,
    DeceptionType,
    # 특징 벡터
    MotionFeatureVector,
    # 동작 분류 결과
    ActionClassification,
    # 세부 동작
    ShootingMotion,
    DribblingMotion,
    PassingMotion,
    DefensiveMotion,
    MovementMotion,
    # 플로핑/디셉션 감지
    FloppingDetection,
    # 종합 결과
    MotionDetectionResult,
)

# =============================================================================
# 경기 관리 DTO (v4.0.0 신규 - Layer 5 Phase 1A)
# =============================================================================
from shared.dto.game_management_dto import (
    # 세부 구조체
    TimeoutRecord,
    PlayerBoxStat,
    TeamBoxStat,
    # 열거형
    GameState,
    BonusStatus,
    CorrectionType,
    # 데이터 클래스
    OnCourtLineup,
    SubstitutionEvent,
    FoulState,
    TimeoutState,
    ClockState,
    CorrectionRecord,
    OfficialBoxScore,
    GameManagementSnapshot,
)

# =============================================================================
# 예측 모델 DTO (v4.0.0 신규 - Layer 5 Phase 2)
# =============================================================================
from shared.dto.prediction_dto import (
    WinProbability,
    ExpectedPossessionValue,
    ShotQualityPrediction,
    LineupProjection,
    PredictionSnapshot,
)

# =============================================================================
# 전술/분석 결과 DTO (v4.0.0 신규 - Layer 5 Phase 3)
# =============================================================================
from shared.dto.tactical_dto import (
    # 세부 구조체
    DetectedPlay,
    PassConnection,
    DriveStats,
    OffBallMovement,
    ClutchStats,
    FatigueIndicators,
    ScoringRun,
    MomentumShift,
    TimeoutEffectiveness,
    ReboundPosition,
    # 열거형
    DefenseScheme,
    MomentumState,
    TrendDirection,
    # 분석 결과
    PickAndRollAnalysis,
    FastBreakAnalysis,
    SetPlayAnalysis,
    PassingNetworkData,
    DefenseAnalysis,
    MatchupData,
    IndividualAnalysis,
    SpacingData,
    LineupData,
    GameFlowData,
    TransitionData,
    PlayTypeData,
    SituationSplitData,
    # 리바운드 전술 분석
    ReboundAnalysis,
    TacticalAnalysisResult,
)

# =============================================================================
# 스카우팅/게임플랜 DTO (v4.0.0 신규 - Layer 5 Phase 3+4)
# =============================================================================
from shared.dto.scouting_dto import (
    # 세부 구조체
    KeyPlayerInfo,
    DefensiveGap,
    MatchupExploit,
    RecentGameResult,
    StrategyItem,
    SwitchRule,
    DoubleTeamTrigger,
    KeyMatchup,
    StrategyExecution,
    PlanDeviation,
    # 스카우팅
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
    HeadToHeadRecord,
    # 게임플랜
    GamePlan,
    DefensiveAssignment,
    PreGameBriefing,
    # 전략 실행도
    GamePlanExecutionResult,
)

# =============================================================================
# 미디어/비디오 편집 DTO (v4.0.0 신규 - Layer 5 Phase 4)
# =============================================================================
from shared.dto.media_dto import (
    # 열거형
    ExportFormat,
    AnnotationType,
    # 데이터 클래스
    Annotation,
    VideoClip,
    MultiAngleClip,
    CoachingPoint,
    PlayerClipPackage,
    FilmSessionData,
    ExportConfig,
)

# =============================================================================
# 데이터셋 추출 DTO (v4.0.0 신규 - Layer 5 Phase 5)
# =============================================================================
from shared.dto.dataset_dto import (
    # 세부 구조체
    KeypointRecord,
    ActionRecord,
    EventRecord,
    LineupRecord,
    # 열거형
    DatasetType,
    DatasetSplit,
    UploadStatus,
    # 하위 레이어 재학습용
    ShotTrajectoryRecord,
    PlayerBboxRecord,
    CourtLineRecord,
    FoulSceneRecord,
    # COURTVIEW 자체 모델 학습용
    FrameRecord,
    PossessionRecord,
    GameDataRecord,
    # game_analysis 고유 학습 데이터
    EventCorrectionRecord,
    TacticalSequenceRecord,
    PlayerPerformanceRecord,
    PredictionOutcomeRecord,
    # ai_referee 자가학습용
    DecisionRecord,
    CorrectionPairRecord,
    EdgeCaseRecord,
    CalibrationRecord,
    FoulContactRecord,
    ViolationSequenceRecord,
    # 메타데이터/결과
    DatasetMetadata,
    ExtractionResult,
)

# =============================================================================
# 훈련 관련 DTO - Desktop 제외 (앱 전용)
# =============================================================================
# training_dto.py는 Desktop 버전에서 제외됨 (motion_analysis 레이어 제외)

# =============================================================================
# 사용자 프로필 관련 DTO - Desktop 제외 (앱 전용)
# =============================================================================
# user_dto.py는 Desktop 버전에서 제외됨 (신체 스캔 기능은 앱 전용)
# AgeGroup, Gender, UserProfile은 analysis_dto에서 제공

__all__ = [
    # =========================================================================
    # 기하학 기본형 DTO
    # =========================================================================
    "Point2D",
    "Line2D",
    "BoundingBox",
    "Polygon2D",
    "Point3D",
    "Vector3D",
    "Ray3D",
    "BoundingBox3D",
    "Plane3D",
    "Pose2D",
    "Pose3D",
    "Trajectory3D",
    "CourtCoordinate",
    # =========================================================================
    # 비디오 메타데이터 DTO
    # =========================================================================
    "VideoFormat",
    "VideoType",
    "FrameStatus",
    "VideoCodec",
    "AudioCodec",
    "VideoResolution",
    "VideoFileMetadata",
    "FrameData",
    "VideoSegment",
    "VideoInfo",
    # =========================================================================
    # 카메라 정보 DTO
    # =========================================================================
    "CameraType",
    "CameraState",
    "ExposureMode",
    "WhiteBalanceMode",
    "FocusMode",
    "CameraInfo",
    "CameraStatus",
    "CameraConfig",
    "CameraFrame",
    "CameraPosition",
    "CameraSetup",
    "MultiCameraSetup",
    # =========================================================================
    # 캘리브레이션 DTO
    # =========================================================================
    "CalibrationStatus",
    "CalibrationMethod",
    "IntrinsicParams",
    "DistortionCoeffs",
    "CameraMatrix",
    "ExtrinsicParams",
    "RotationMatrix",
    "TranslationVector",
    "HomographyMatrix",
    "FundamentalMatrix",
    "EssentialMatrix",
    "ProjectionMatrix",
    "CalibrationResult",
    "StereoCalibration",
    "MultiCameraCalibration",
    # =========================================================================
    # 추적 데이터 DTO
    # =========================================================================
    "TrackState",
    "TrackSource",
    "TrackedObjectType",
    "TrackHistory",
    "KalmanState",
    "Track",
    "TrackAssociation",
    "TrackingResult",
    "MultiViewTrackingResult",
    # =========================================================================
    # 오클루전 데이터 DTO
    # =========================================================================
    "ViewVisibility",
    "OccludedObject",
    "OcclusionEvent",
    "OcclusionResolution",
    "OcclusionAnalysisResult",
    # =========================================================================
    # Re-ID 데이터 DTO
    # =========================================================================
    "ReIDFeature",
    "GalleryEntry",
    "ReIDGallery",
    "ReIDMatch",
    "ReIDResult",
    # =========================================================================
    # 포즈/스켈레톤 DTO (v2.0.0 - v2.1.0 i18n 업데이트)
    # =========================================================================
    "Keypoint",
    "JointAngle",     # i18n: get_description(lang)
    "Skeleton2D",
    "Skeleton3D",
    "PoseEstimationResult",
    # =========================================================================
    # 감지 결과 통합 DTO
    # =========================================================================
    "ObjectType",
    "DetectionSource",
    "DetectedObject",
    "DetectionConfig",
    "DetectionResult",
    "MultiViewDetectionResult",
    # =========================================================================
    # 공 감지/궤적 DTO
    # =========================================================================
    "TrajectoryType",
    "BallShotResult",
    "BallDetection",
    "BallTrajectory",
    "ShotTrajectory",
    "BallAnalysisResult",
    # =========================================================================
    # OCR 결과 DTO (v2.0.0 - i18n 업데이트)
    # =========================================================================
    "OCRBackend",
    "OCRStatus",
    "OCRResult",
    "JerseyNumber",
    "JerseyNumberVote",
    "MultiViewOCRResult",
    "OCRAnalysisResult",
    # =========================================================================
    # 3D 씬 데이터 DTO (v2.0.0 - v2.2.0 i18n 업데이트)
    # =========================================================================
    "SceneStatus",
    "ObjectCategory",
    "SceneObject",
    "CourtModel",
    "HoopModel",
    "Scene3D",
    "SceneSnapshot",
    "SceneTimeline",
    "SceneMetadata",
    # =========================================================================
    # 선수 정보 DTO
    # =========================================================================
    "Team",
    "PlayerRole",
    "PlayerPosition",
    "PlayerID",
    "DetailedPlayerInfo",
    "IdentificationSource",
    "PlayerIdentification",
    "PlayerHistoryEntry",
    "ManagedPlayer",
    "PlayerManager",
    # =========================================================================
    # 파이프라인 입출력 DTO
    # =========================================================================
    "VideoSource",
    "VideoMetadata",
    "PipelineOptions",
    "BasePipelineRequest",
    "GameAnalysisRequest",
    "RefereeAnalysisRequest",
    "PipelineRequest",
    "PipelineProgress",
    "PipelineResultBase",
    "GameAnalysisResult",
    "ViolationCounts",
    "FoulCounts",
    "RefereeAnalysisResult",
    "SyncEventType",
    "BackendSyncPayload",
    # =========================================================================
    # 피드백 DTO (기존)
    # =========================================================================
    "FeedbackCategory",
    "FeedbackPriority",
    "FeedbackType",
    "BodyPart",
    "MotionPhase",
    "FeedbackSource",
    "VideoClipReference",
    "CausalFactor",
    "FeedbackItem",
    "MotionScore",
    "MotionComparison",
    "FeedbackSummary",
    "TrainingRecommendation",
    "TrainingPlan",
    "ProgressMetric",
    "ProgressReport",
    "UserFeedback",
    "FeedbackEffectiveness",
    "FeedbackResult",
    # =========================================================================
    # 경기 DTO (기존)
    # =========================================================================
    "PlayerInfo",
    "TeamInfo",
    "ShotAttempt",
    "ZoneStatistics",
    "ShotChart",
    "GameEvent",
    "HighlightClip",
    "HighlightReel",
    "PlayerStats",
    "TeamStats",
    "GameStats",
    "ViolationEvent",
    "FoulEvent",
    "RefereeDecision",
    "ReviewSuggestion",
    "ViolationDetection",
    "FoulDetection",
    "GameRefereeReport",
    # =========================================================================
    # AI 심판 시스템 DTO (v2.3.0 - Desktop Edition)
    # =========================================================================
    "RefereeCall",
    "RefereePosition",
    "CallContext",
    "ReplayReview",
    "ChallengeRequest",
    "CallAccuracy",
    "ConsistencyMetrics",
    "RefereePerformance",
    "ClockAdjustment",
    "TimeoutManagement",
    "SubstitutionRecord",
    "GameClockManagement",
    "AdvantageState",
    "UnsportsmanlikeActionType",
    "AdvantageDecision",
    "UnsportsmanlikeBehavior",
    "RefereeReport",  # referee_dto의 RefereeReport (AI 심판 시스템)
    # =========================================================================
    # 생체역학 DTO (v4.0.0 - Layer 3)
    # =========================================================================
    "JointKinematics",
    "BodySegmentData",
    "BalanceMetrics",
    "EnergyMetrics",
    "ForceEstimate",
    "MotionPatternData",
    "AnthropometryData",
    "LandingImpactData",
    "ContactEventData",
    "ExplosiveEventData",
    "DirectionChangeData",
    "TrajectoryProfileData",
    "MomentumProfileData",
    "EnergyProfileData",
    "BalanceHistoryData",
    "BiomechanicalFrame",
    "BiomechanicalResult",
    # =========================================================================
    # 동작 분석 DTO (v4.0.0 - Layer 4)
    # =========================================================================
    "ActionType",
    "ContestLevel",
    "DribbleType",
    "PassType",
    "DefensiveActionType",
    "MovementType",
    "DeceptionType",
    "MotionFeatureVector",
    "ActionClassification",
    "ShootingMotion",
    "DribblingMotion",
    "PassingMotion",
    "DefensiveMotion",
    "MovementMotion",
    "FloppingDetection",
    "MotionDetectionResult",
    # =========================================================================
    # 경기 관리 DTO (v4.0.0 - Layer 5 Phase 1A)
    # =========================================================================
    # 세부 구조체
    "TimeoutRecord",
    "PlayerBoxStat",
    "TeamBoxStat",
    "GameState",
    "BonusStatus",
    "CorrectionType",
    "OnCourtLineup",
    "SubstitutionEvent",
    "FoulState",
    "TimeoutState",
    "ClockState",
    "CorrectionRecord",
    "OfficialBoxScore",
    "GameManagementSnapshot",
    # =========================================================================
    # 예측 모델 DTO (v4.0.0 - Layer 5 Phase 2)
    # =========================================================================
    "WinProbability",
    "ExpectedPossessionValue",
    "ShotQualityPrediction",
    "LineupProjection",
    "PredictionSnapshot",
    # =========================================================================
    # 전술/분석 결과 DTO (v4.0.0 - Layer 5 Phase 3)
    # =========================================================================
    # 세부 구조체
    "DetectedPlay",
    "PassConnection",
    "DriveStats",
    "OffBallMovement",
    "ClutchStats",
    "FatigueIndicators",
    "ScoringRun",
    "MomentumShift",
    "TimeoutEffectiveness",
    "ReboundPosition",
    "DefenseScheme",
    "MomentumState",
    "TrendDirection",
    "PickAndRollAnalysis",
    "FastBreakAnalysis",
    "SetPlayAnalysis",
    "PassingNetworkData",
    "DefenseAnalysis",
    "MatchupData",
    "IndividualAnalysis",
    "SpacingData",
    "LineupData",
    "GameFlowData",
    "TransitionData",
    "PlayTypeData",
    "SituationSplitData",
    "ReboundAnalysis",
    "TacticalAnalysisResult",
    # =========================================================================
    # 스카우팅/게임플랜 DTO (v4.0.0 - Layer 5 Phase 3+4)
    # =========================================================================
    # 세부 구조체
    "KeyPlayerInfo",
    "DefensiveGap",
    "MatchupExploit",
    "RecentGameResult",
    "StrategyItem",
    "SwitchRule",
    "DoubleTeamTrigger",
    "KeyMatchup",
    "StrategyExecution",
    "PlanDeviation",
    # 스카우팅
    "OpponentProfile",
    "TendencyReport",
    "WeaknessReport",
    "HeadToHeadRecord",
    # 게임플랜
    "GamePlan",
    "DefensiveAssignment",
    "PreGameBriefing",
    # 전략 실행도
    "GamePlanExecutionResult",
    # =========================================================================
    # 미디어/비디오 편집 DTO (v4.0.0 - Layer 5 Phase 4)
    # =========================================================================
    "ExportFormat",
    "AnnotationType",
    "Annotation",
    "VideoClip",
    "MultiAngleClip",
    "CoachingPoint",
    "PlayerClipPackage",
    "FilmSessionData",
    "ExportConfig",
    # =========================================================================
    # 데이터셋 추출 DTO (v4.0.0 - Layer 5 Phase 5)
    # =========================================================================
    # 세부 구조체
    "KeypointRecord",
    "ActionRecord",
    "EventRecord",
    "LineupRecord",
    "DatasetType",
    "DatasetSplit",
    "UploadStatus",
    "ShotTrajectoryRecord",
    "PlayerBboxRecord",
    "CourtLineRecord",
    "FoulSceneRecord",
    "FrameRecord",
    "PossessionRecord",
    "GameDataRecord",
    "EventCorrectionRecord",
    "TacticalSequenceRecord",
    "PlayerPerformanceRecord",
    "PredictionOutcomeRecord",
    "DecisionRecord",
    "CorrectionPairRecord",
    "EdgeCaseRecord",
    "CalibrationRecord",
    "FoulContactRecord",
    "ViolationSequenceRecord",
    "DatasetMetadata",
    "ExtractionResult",
    # =========================================================================
    # 훈련 DTO - Desktop 제외 (앱 전용)
    # =========================================================================
    # "DrillCategory", "DrillDifficulty", "Drill", "DrillRecommendation",
    # "TrainingSession", "WeeklyTrainingPlan" - training_dto.py 제거됨
    # =========================================================================
    # 사용자 프로필 DTO - Desktop 제외 (앱 전용)
    # =========================================================================
    # "DetailedAgeGroup", "DetailedGender", "Handedness", "Position",
    # "BodyMeasurement", "BodyScanData", "DetailedUserProfile" - user_dto.py 제거됨
    # AgeGroup, Gender, UserProfile은 analysis_dto에서 사용
]

__version__ = "1.0.0"
