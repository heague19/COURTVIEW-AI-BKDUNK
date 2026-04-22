# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: __init__.py
설명: 상수 모듈 패키지 초기화
      - 에러 코드, 상태 코드, 이벤트 타입
      - 카메라, 코트, 비디오, 융합 상수
      - 추적, 오클루전, Re-ID, 포즈 상수
      - 매칭, 기하학, OCR, 공 물리 상수
      - 경기 규칙, 심판 시스템 상수
      - Gender/AgeGroup/SkillLevel 통합
      - 생체역학, 통계, 전술, 경기관리, 심판판정, 피드백 상수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0
"""

from __future__ import annotations


# =============================================================================
# 다국어 지원
# =============================================================================
from shared.constants.localization import SupportedLanguage

# =============================================================================
# 에러 코드
# =============================================================================
from shared.constants.error_codes import (
    ErrorCategory,
    ErrorCode,
    GENERAL_ERRORS,
    AUTH_ERRORS,
    VALIDATION_ERRORS,
    BUSINESS_ERRORS,
    INFRASTRUCTURE_ERRORS,
    EXTERNAL_ERRORS,
    ANALYSIS_ERRORS,
    REFEREE_ERRORS,
    CONFIGURATION_ERRORS,
    SYSTEM_ERRORS,
)

# =============================================================================
# 상태 코드
# =============================================================================
from shared.constants.status_codes import (
    TaskStatus,
    TaskType,
    AnalysisType,
    AnalysisPhase,
    ServiceStatus,
    QueuePriority,
    Environment,
    QualityLevel,
    LearningStatus,
    VALID_TASK_TRANSITIONS,
)

# =============================================================================
# 이벤트 타입
# =============================================================================
from shared.constants.event_types import (
    EventCategory,
    EventType,
    WEBHOOK_EVENTS,
    REALTIME_EVENTS,
    AUDIT_EVENTS,
    METRIC_EVENTS,
    EVENT_PRIORITY,
)

# =============================================================================
# 카메라 상수
# =============================================================================
from shared.constants.camera_constants import (
    # 열거형
    CameraType,
    CameraState,
    CameraQualityPreset,
    # 주요 상수
    DEFAULT_RESOLUTION,
    DEFAULT_FRAME_RATE,
    MIN_FRAME_RATE,
    MAX_FRAME_RATE,
    SUPPORTED_RESOLUTIONS,
)

# =============================================================================
# 코트 상수
# =============================================================================
from shared.constants.court_constants import (
    # 열거형
    CourtStandard,
    CourtZone,
    # 코트 규격 (FIBA 기준)
    COURT_LENGTH_M,
    COURT_WIDTH_M,
    THREE_POINT_LINE_DISTANCE_M,
    FREE_THROW_LINE_DISTANCE_M,
    # NBA 코트 규격
    THREE_POINT_LINE_NBA_DISTANCE_M,
)

# =============================================================================
# 비디오 상수
# =============================================================================
from shared.constants.video_constants import (
    # 열거형
    VideoFormat,
    VideoCodec,
    AudioCodec,
    ColorSpace,
    # 주요 상수
    DEFAULT_FPS,
    MAX_SYNC_DRIFT_MS,
    FRAME_BUFFER_SIZE,
)

# =============================================================================
# 융합 상수
# =============================================================================
from shared.constants.fusion_constants import (
    # 열거형
    FusionStrategy,
    FusionQuality,
    # 주요 상수
    MIN_VIEWS_FOR_TRIANGULATION,
    FUSION_CONFIDENCE_THRESHOLD,
    TRIANGULATION_MAX_DEPTH_M,
)

# =============================================================================
# 추적 상수
# =============================================================================
from shared.constants.tracking_constants import (
    # 열거형
    TrackState,
    TrackingAlgorithm,
    TrackingTarget,
    # 주요 상수
    IOU_THRESHOLD,
    MAX_TRACK_AGE,
    MIN_TRACK_HITS,
)

# =============================================================================
# 오클루전 상수
# =============================================================================
from shared.constants.occlusion_constants import (
    # 열거형
    OcclusionType,
    OcclusionSeverity,
    ResolutionStrategy,
    # 주요 상수 (occlusion_constants.py 실제 정의명 사용)
    OVERLAP_THRESHOLD,
    MIN_VISIBLE_KEYPOINTS_RATIO,
    MAX_OCCLUSION_DURATION_FRAMES,
)

# =============================================================================
# Re-ID 상수
# =============================================================================
from shared.constants.reid_constants import (
    # 열거형
    ReIDModel,
    MatchStatus,
    # 주요 상수
    FEATURE_DIM,
    SIMILARITY_THRESHOLD,
    GALLERY_MAX_SIZE,
    EMA_MOMENTUM,
)

# =============================================================================
# 포즈 상수
# =============================================================================
from shared.constants.pose_constants import (
    # 열거형
    SkeletonType,
    JointType,
    PoseQuality,
    # 주요 상수
    NUM_KEYPOINTS_MEDIAPIPE,
    NUM_KEYPOINTS_COCO,
    JOINT_CONFIDENCE_THRESHOLD,
    SKELETON_COMPLETENESS_THRESHOLD,
)

# =============================================================================
# 매칭 상수
# =============================================================================
from shared.constants.matching_constants import (
    # 열거형
    MatchingStrategy,
    MatchingStatus,
    MatchingTargetType,
    # 주요 상수 (정의서 필수)
    APPEARANCE_WEIGHT,
    GEOMETRY_WEIGHT,
    POSITION_WEIGHT,
    DEFAULT_EPIPOLAR_THRESHOLD,
    DEFAULT_APPEARANCE_THRESHOLD,
)

# =============================================================================
# 기하학 상수
# =============================================================================
from shared.constants.geometry_constants import (
    # 열거형
    GeometryMethod,
    CoordinateSystem,
    DistortionModel,
    # 주요 상수 (정의서 필수)
    RANSAC_THRESHOLD,
    MIN_POINTS_FOR_FUNDAMENTAL,
    EPIPOLE_INFINITY_THRESHOLD,
)

# =============================================================================
# OCR 상수
# =============================================================================
from shared.constants.ocr_constants import (
    # 열거형
    OCRModel,
    TextDetectionModel,
    OCRStatus,
    # 주요 상수 (정의서 필수)
    MIN_OCR_CONFIDENCE,
    JERSEY_NUMBER_MIN,
    JERSEY_NUMBER_MAX,
    OCR_FRAME_INTERVAL,
)

# =============================================================================
# 공 물리 상수
# =============================================================================
from shared.constants.ball_constants import (
    # 열거형
    BallSize,
    BallState,
    ShotType,
    # 주요 상수 (정의서 필수)
    BASKETBALL_DIAMETER_M,
    BASKETBALL_MASS_KG,
    GRAVITY_ACCELERATION,
    AIR_RESISTANCE_COEFFICIENT,
)

# =============================================================================
# 골대/네트 검출 상수
# =============================================================================
from shared.constants.hoop_constants import (
    # 검출 기본 파라미터
    HOOP_DETECTION_CONFIDENCE_THRESHOLD,
    HOOP_CLASS_ID_RIM,
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_NET,
    # 득점 판정
    HOOP_SCORING_CONFIDENCE_THRESHOLD,
    HOOP_SCORING_MIN_TRAJECTORY_POINTS,
)

# =============================================================================
# 선수 검출/팀 분류 상수
# =============================================================================
from shared.constants.player_constants import (
    # 사용자 속성 열거형 (canonical source)
    Gender,
    AgeGroup,
    SkillLevel,
    # YOLO 감지 클래스 ID
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_STAFF,
    PLAYER_CLASS_ID_UNKNOWN,
    PLAYER_CLASS_NAMES,
    # 팀 분류 밝기 임계값
    TEAM_VALUE_DARK_THRESHOLD,
    TEAM_VALUE_LIGHT_THRESHOLD,
)

# =============================================================================
# 경기 규칙 상수
# =============================================================================
from shared.constants.game_rule_constants import (
    # 열거형 (충돌 제외: ShotType → ball_constants, CourtZone → court_constants)
    ShotResult,
    PlayType,
    GameEventType,
    HighlightType,
    ViolationType,
    FoulType,
    # 경기 규칙 상수
    PLAYERS_ON_COURT,
    GAME_PERIODS,
    SHOT_CLOCK_SEC,
    SHOT_CLOCK_RESET_SEC,
    OVERTIME_DURATION_SEC,
    MAX_PERSONAL_FOULS_FIBA,
    MAX_PERSONAL_FOULS_NBA,
    TEAM_FOUL_BONUS_FIBA,
    TEAM_FOUL_BONUS_NBA,
    TECHNICAL_FOUL_EJECTION,
)

# =============================================================================
# 심판 시스템 상수
# =============================================================================
from shared.constants.referee_rule_constants import (
    # 열거형
    RuleSet,
    CallType,
    SignalType,
    ReviewTrigger,
    ReviewOutcome,
    RefereeRole,
    # 심판 시스템 상수
    MIN_DECISION_CONFIDENCE,
    AUTO_CONFIRM_CONFIDENCE,
    REVIEW_TIME_LIMIT_SEC,
    MAX_COACH_CHALLENGES_PER_GAME,
    REFEREE_COUNT_STANDARD,
    CONSISTENCY_WINDOW_FRAMES,
)

# =============================================================================
# 생체역학 상수
# =============================================================================
from shared.constants.biomechanics_constants import (
    # 열거형
    BodySegment,
    MotionPhase,
    MovementIntensity,
    StanceType,
    # 인체측정 모델 (주요)
    SEGMENT_MASS_RATIO_MALE,
    SEGMENT_MASS_RATIO_FEMALE,
    SEGMENT_LENGTH_RATIO,
    # 관절 ROM
    JOINT_ROM_NORMAL,
    # 슈팅 최적 각도
    SHOOTING_OPTIMAL_ANGLES,
    # 속도 임계치
    VELOCITY_THRESHOLDS_ADULT_MALE,
    AGE_VELOCITY_FACTOR,
)

# =============================================================================
# 통계 상수
# =============================================================================
from shared.constants.stats_constants import (
    # 열거형
    StatCategory,
    PerformanceRating,
    ShotZone,
    # 고급 스탯 계수
    FREE_THROW_TRIP_FACTOR,
    THREE_POINT_EFG_BONUS,
    PER_LEAGUE_AVERAGE,
    # Four Factors
    FOUR_FACTORS_EFG_WEIGHT,
    FOUR_FACTORS_TOV_WEIGHT,
    FOUR_FACTORS_OREB_WEIGHT,
    FOUR_FACTORS_FT_RATE_WEIGHT,
)

# =============================================================================
# 전술 상수
# =============================================================================
from shared.constants.tactical_constants import (
    # 열거형
    SetPlayType,
    TransitionPhase,
    SpacingQuality,
    TurnoverCategory,
    # 주요 파라미터
    SPACING_OPTIMAL_DISTANCE_M,
    SCORING_RUN_MIN_POINTS,
    MOMENTUM_SHIFT_THRESHOLD,
)

# =============================================================================
# 경기 관리 상수
# =============================================================================
from shared.constants.game_management_constants import (
    # 열거형
    GameState,
    BonusStatus,
    TimeoutType,
    RecordFormat,
    # 상태 전이
    VALID_GAME_STATE_TRANSITIONS,
    # 주요 파라미터
    QUARTER_DURATION_SEC,
    TIMEOUTS_PER_TEAM,
    SHOT_CLOCK_FULL_SEC,
)

# =============================================================================
# 심판 판정 상수
# =============================================================================
from shared.constants.referee_decision_constants import (
    # 열거형
    DecisionConfidence,
    FoulGrade,
    ContactArea,
    # 신뢰도 임계치
    DECISION_AUTO_CONFIRM_THRESHOLD,
    DECISION_HIGH_CONFIDENCE_THRESHOLD,
    # 바이올레이션 임계치 (주요)
    TRAVELING_PIVOT_DISPLACEMENT_M,
    THREE_SECOND_OFFENSE_THRESHOLD_SEC,
    # 파울 임계치 (주요)
    FLAGRANT_1_SEVERITY_SCORE,
    FLAGRANT_2_SEVERITY_SCORE,
)

# =============================================================================
# 피드백 상수
# =============================================================================
from shared.constants.feedback_constants import (
    # 열거형
    FeedbackSeverity,
    FeedbackCategory,
    ReportType,
    ReportOutputFormat,
    # 주요 파라미터
    FEEDBACK_MIN_DETAIL_POINTS,
    FEEDBACK_CATEGORY_PRIORITY,
    SINGLE_GAME_REPORT_SECTIONS,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # =========================================================================
    # 다국어 지원
    # =========================================================================
    "SupportedLanguage",

    # =========================================================================
    # 에러 코드
    # =========================================================================
    "ErrorCategory",
    "ErrorCode",
    "GENERAL_ERRORS",
    "AUTH_ERRORS",
    "VALIDATION_ERRORS",
    "BUSINESS_ERRORS",
    "INFRASTRUCTURE_ERRORS",
    "EXTERNAL_ERRORS",
    "ANALYSIS_ERRORS",
    "REFEREE_ERRORS",
    "CONFIGURATION_ERRORS",
    "SYSTEM_ERRORS",

    # =========================================================================
    # 상태 코드
    # =========================================================================
    "TaskStatus",
    "TaskType",
    "AnalysisType",
    "AnalysisPhase",
    "ServiceStatus",
    "QueuePriority",
    "Environment",
    "QualityLevel",
    "LearningStatus",
    "VALID_TASK_TRANSITIONS",

    # =========================================================================
    # 이벤트 타입
    # =========================================================================
    "EventCategory",
    "EventType",
    "WEBHOOK_EVENTS",
    "REALTIME_EVENTS",
    "AUDIT_EVENTS",
    "METRIC_EVENTS",
    "EVENT_PRIORITY",

    # =========================================================================
    # 카메라 상수
    # =========================================================================
    "CameraType",
    "CameraState",
    "CameraQualityPreset",
    "DEFAULT_RESOLUTION",
    "DEFAULT_FRAME_RATE",
    "MIN_FRAME_RATE",
    "MAX_FRAME_RATE",
    "SUPPORTED_RESOLUTIONS",

    # =========================================================================
    # 코트 상수
    # =========================================================================
    "CourtStandard",
    "CourtZone",
    "COURT_LENGTH_M",
    "COURT_WIDTH_M",
    "THREE_POINT_LINE_DISTANCE_M",
    "FREE_THROW_LINE_DISTANCE_M",
    "THREE_POINT_LINE_NBA_DISTANCE_M",

    # =========================================================================
    # 비디오 상수
    # =========================================================================
    "VideoFormat",
    "VideoCodec",
    "AudioCodec",
    "ColorSpace",
    "DEFAULT_FPS",
    "MAX_SYNC_DRIFT_MS",
    "FRAME_BUFFER_SIZE",

    # =========================================================================
    # 융합 상수
    # =========================================================================
    "FusionStrategy",
    "FusionQuality",
    "MIN_VIEWS_FOR_TRIANGULATION",
    "FUSION_CONFIDENCE_THRESHOLD",
    "TRIANGULATION_MAX_DEPTH_M",

    # =========================================================================
    # 추적 상수
    # =========================================================================
    "TrackState",
    "TrackingAlgorithm",
    "TrackingTarget",
    "IOU_THRESHOLD",
    "MAX_TRACK_AGE",
    "MIN_TRACK_HITS",

    # =========================================================================
    # 오클루전 상수
    # =========================================================================
    "OcclusionType",
    "OcclusionSeverity",
    "ResolutionStrategy",
    "OVERLAP_THRESHOLD",
    "MIN_VISIBLE_KEYPOINTS_RATIO",
    "MAX_OCCLUSION_DURATION_FRAMES",

    # =========================================================================
    # Re-ID 상수
    # =========================================================================
    "ReIDModel",
    "MatchStatus",
    "FEATURE_DIM",
    "SIMILARITY_THRESHOLD",
    "GALLERY_MAX_SIZE",
    "EMA_MOMENTUM",

    # =========================================================================
    # 포즈 상수
    # =========================================================================
    "SkeletonType",
    "JointType",
    "PoseQuality",
    "NUM_KEYPOINTS_MEDIAPIPE",
    "NUM_KEYPOINTS_COCO",
    "JOINT_CONFIDENCE_THRESHOLD",
    "SKELETON_COMPLETENESS_THRESHOLD",

    # =========================================================================
    # 매칭 상수
    # =========================================================================
    "MatchingStrategy",
    "MatchingStatus",
    "MatchingTargetType",
    "APPEARANCE_WEIGHT",
    "GEOMETRY_WEIGHT",
    "POSITION_WEIGHT",
    "DEFAULT_EPIPOLAR_THRESHOLD",
    "DEFAULT_APPEARANCE_THRESHOLD",

    # =========================================================================
    # 기하학 상수
    # =========================================================================
    "GeometryMethod",
    "CoordinateSystem",
    "DistortionModel",
    "RANSAC_THRESHOLD",
    "MIN_POINTS_FOR_FUNDAMENTAL",
    "EPIPOLE_INFINITY_THRESHOLD",

    # =========================================================================
    # OCR 상수
    # =========================================================================
    "OCRModel",
    "TextDetectionModel",
    "OCRStatus",
    "MIN_OCR_CONFIDENCE",
    "JERSEY_NUMBER_MIN",
    "JERSEY_NUMBER_MAX",
    "OCR_FRAME_INTERVAL",

    # =========================================================================
    # 공 물리 상수
    # =========================================================================
    "BallSize",
    "BallState",
    "ShotType",
    "BASKETBALL_DIAMETER_M",
    "BASKETBALL_MASS_KG",
    "GRAVITY_ACCELERATION",
    "AIR_RESISTANCE_COEFFICIENT",

    # =========================================================================
    # 골대/네트 검출 상수
    # =========================================================================
    "HOOP_DETECTION_CONFIDENCE_THRESHOLD",
    "HOOP_CLASS_ID_RIM",
    "HOOP_CLASS_ID_BACKBOARD",
    "HOOP_CLASS_ID_NET",
    "HOOP_SCORING_CONFIDENCE_THRESHOLD",
    "HOOP_SCORING_MIN_TRAJECTORY_POINTS",

    # =========================================================================
    # 선수 관련 상수 (v3.0.0 → v3.1.0: Gender/AgeGroup/SkillLevel 통합)
    # =========================================================================
    # 사용자 속성 열거형 (canonical source)
    "Gender",
    "AgeGroup",
    "SkillLevel",
    # YOLO 감지 클래스 ID
    "PLAYER_CLASS_ID_PLAYER",
    "PLAYER_CLASS_ID_REFEREE",
    "PLAYER_CLASS_ID_COACH",
    "PLAYER_CLASS_ID_STAFF",
    "PLAYER_CLASS_ID_UNKNOWN",
    "PLAYER_CLASS_NAMES",
    "TEAM_VALUE_DARK_THRESHOLD",
    "TEAM_VALUE_LIGHT_THRESHOLD",

    # =========================================================================
    # 경기 규칙 상수
    # =========================================================================
    "ShotResult",
    "PlayType",
    "GameEventType",
    "HighlightType",
    "ViolationType",
    "FoulType",
    "PLAYERS_ON_COURT",
    "GAME_PERIODS",
    "SHOT_CLOCK_SEC",
    "SHOT_CLOCK_RESET_SEC",
    "OVERTIME_DURATION_SEC",
    "MAX_PERSONAL_FOULS_FIBA",
    "MAX_PERSONAL_FOULS_NBA",
    "TEAM_FOUL_BONUS_FIBA",
    "TEAM_FOUL_BONUS_NBA",
    "TECHNICAL_FOUL_EJECTION",

    # =========================================================================
    # 심판 시스템 상수
    # =========================================================================
    "RuleSet",
    "CallType",
    "SignalType",
    "ReviewTrigger",
    "ReviewOutcome",
    "RefereeRole",
    "MIN_DECISION_CONFIDENCE",
    "AUTO_CONFIRM_CONFIDENCE",
    "REVIEW_TIME_LIMIT_SEC",
    "MAX_COACH_CHALLENGES_PER_GAME",
    "REFEREE_COUNT_STANDARD",
    "CONSISTENCY_WINDOW_FRAMES",

    # =========================================================================
    # 생체역학 상수
    # =========================================================================
    "BodySegment",
    "MotionPhase",
    "MovementIntensity",
    "StanceType",
    "SEGMENT_MASS_RATIO_MALE",
    "SEGMENT_MASS_RATIO_FEMALE",
    "SEGMENT_LENGTH_RATIO",
    "JOINT_ROM_NORMAL",
    "SHOOTING_OPTIMAL_ANGLES",
    "VELOCITY_THRESHOLDS_ADULT_MALE",
    "AGE_VELOCITY_FACTOR",

    # =========================================================================
    # 통계 상수
    # =========================================================================
    "StatCategory",
    "PerformanceRating",
    "ShotZone",
    "FREE_THROW_TRIP_FACTOR",
    "THREE_POINT_EFG_BONUS",
    "PER_LEAGUE_AVERAGE",
    "FOUR_FACTORS_EFG_WEIGHT",
    "FOUR_FACTORS_TOV_WEIGHT",
    "FOUR_FACTORS_OREB_WEIGHT",
    "FOUR_FACTORS_FT_RATE_WEIGHT",

    # =========================================================================
    # 전술 상수
    # =========================================================================
    "SetPlayType",
    "TransitionPhase",
    "SpacingQuality",
    "TurnoverCategory",
    "SPACING_OPTIMAL_DISTANCE_M",
    "SCORING_RUN_MIN_POINTS",
    "MOMENTUM_SHIFT_THRESHOLD",

    # =========================================================================
    # 경기 관리 상수
    # =========================================================================
    "GameState",
    "BonusStatus",
    "TimeoutType",
    "RecordFormat",
    "VALID_GAME_STATE_TRANSITIONS",
    "QUARTER_DURATION_SEC",
    "TIMEOUTS_PER_TEAM",
    "SHOT_CLOCK_FULL_SEC",

    # =========================================================================
    # 심판 판정 상수
    # =========================================================================
    "DecisionConfidence",
    "FoulGrade",
    "ContactArea",
    "DECISION_AUTO_CONFIRM_THRESHOLD",
    "DECISION_HIGH_CONFIDENCE_THRESHOLD",
    "TRAVELING_PIVOT_DISPLACEMENT_M",
    "THREE_SECOND_OFFENSE_THRESHOLD_SEC",
    "FLAGRANT_1_SEVERITY_SCORE",
    "FLAGRANT_2_SEVERITY_SCORE",

    # =========================================================================
    # 피드백 상수
    # =========================================================================
    "FeedbackSeverity",
    "FeedbackCategory",
    "ReportType",
    "ReportOutputFormat",
    "FEEDBACK_MIN_DETAIL_POINTS",
    "FEEDBACK_CATEGORY_PRIORITY",
    "SINGLE_GAME_REPORT_SECTIONS",
]

# 모듈 버전 정보
__version__ = "1.0.0"
