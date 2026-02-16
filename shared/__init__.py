# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared
파일: __init__.py
설명: Shared 모듈 패키지 초기화 - 프로젝트 전역 공유 자원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

Shared 모듈 구성:
    - constants: 에러 코드, 상태 코드, 이벤트 타입 상수
    - exceptions: 커스텀 예외 클래스 계층
    - dto: Data Transfer Objects 
    - interfaces: 추상 인터페이스 프로토콜
    - protocols: typing.Protocol 기반 인터페이스
"""

# =============================================================================
# 상수 (Constants)
# =============================================================================
from shared.constants import (
    # 에러 코드
    ErrorCode,
    GENERAL_ERRORS,
    AUTH_ERRORS,
    VALIDATION_ERRORS,
    INFRASTRUCTURE_ERRORS,
    ANALYSIS_ERRORS,
    REFEREE_ERRORS,
    CONFIGURATION_ERRORS,
    # 상태 코드
    TaskStatus,
    AnalysisType,
    AnalysisPhase,
    ServiceStatus,
    QueuePriority,
    Environment,
    VALID_TASK_TRANSITIONS,
    is_valid_transition,
    # 이벤트 타입
    EventCategory,
    EventType,
    WEBHOOK_EVENTS,
    REALTIME_EVENTS,
    AUDIT_EVENTS,
    METRIC_EVENTS,
    EVENT_PRIORITY,
    get_event_priority,
)

# =============================================================================
# 예외 (Exceptions)
# =============================================================================
from shared.exceptions import (
    # 기본 예외
    CourtViewException,
    RetryableException,
    NonRetryableException,
    CriticalException,
    # 비디오 예외
    VideoException,
    VideoFormatException,
    VideoDownloadException,
    FrameExtractionException,
    # 감지 예외
    DetectionException,
    PersonNotDetectedException,
    BallNotDetectedException,
    # 포즈 추정 예외
    PoseEstimationException,
    InsufficientKeypointsException,
    OcclusionDetectedException,
    # 동작 분석 예외
    MotionAnalysisException,
    ShootingNotDetectedException,
    DribblingNotDetectedException,
    # 모델 예외
    ModelException,
    ModelLoadException,
    ModelInferenceException,
    # 검증 예외
    ValidationException,
    InvalidRequestException,
    MissingFieldException,
    ConfigurationException,
    SchemaValidationException,
    # 인프라 예외
    DatabaseException,
    DatabaseConnectionException,
    DatabaseTimeoutException,
    DatabaseIntegrityException,
    CacheException,
    CacheConnectionException,
    CacheSerializationException,
    QueueException,
    QueueConnectionException,
    StorageException,
    S3Exception,
    S3UploadException,
    S3DownloadException,
)

# =============================================================================
# DTO (Data Transfer Objects)
# =============================================================================
from shared.dto import (
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
    ViolationCounts,
    FoulCounts,
    RefereeAnalysisResult,
    # Backend 동기화
    SyncEventType,
    BackendSyncPayload,
    # 피드백
    FeedbackCategory,
    FeedbackPriority,
    FeedbackType,
    BodyPart,
    MotionPhase,
    FeedbackItem,
    MotionScore,
    MotionComparison,
    FeedbackSummary,
    TrainingRecommendation,
    TrainingPlan,
    ProgressMetric,
    ProgressReport,
    # 경기 분석
    ShotType,
    ShotResult,
    CourtZone,
    PlayType,
    HighlightType,
    ViolationType,
    FoulType,
    PlayerInfo,
    TeamInfo,
    ShotAttempt,
    ShotChart,
    GameEvent,
    HighlightClip,
    HighlightReel,
    PlayerStats,
    TeamStats,
    GameStats,
    ViolationDetection,
    FoulDetection,
    RefereeReport,
)

# DTO의 EventType을 GameEventType으로 별도 임포트 (상수의 EventType과 구분)
from shared.dto.game_dto import EventType as GameEventType

# =============================================================================
# 인터페이스 (Interfaces)
# =============================================================================
from shared.interfaces import (
    # 분석기 인터페이스
    AnalyzerState,
    AnalysisResult,
    AnalyzerMetrics,
    IAnalyzer,
    IFrameAnalyzer,
    ISequenceAnalyzer,
    IStreamAnalyzer,
    IComparisonAnalyzer,
    ComparisonInput,
    IAnalyzerFactory,
    # 탐지기 인터페이스
    DetectionTarget,
    DetectionState,
    BoundingBox,
    DetectedObject,
    DetectionResult,
    DetectorMetrics,
    IDetector,
    BallState,
    BallDetectionResult,
    IBallDetector,
    CourtKeypoints,
    CourtDetectionResult,
    ICourtDetector,
    PlayerDetection,
    PlayerDetectionResult,
    IPlayerDetector,
    HoopDetection,
    HoopDetectionResult,
    IHoopDetector,
    IDetectorFactory,
    ICompositeDetector,
    # 스토리지 인터페이스
    StorageType,
    StorageState,
    ContentType,
    SortOrder,
    FileMetadata,
    UploadResult,
    DownloadResult,
    StorageMetrics,
    RepositoryMetrics,
    IStorage,
    IVideoStorage,
    CacheEntry,
    ICache,
    AnalysisResultEntry,
    IAnalysisResultStorage,
    IStorageFactory,
    # 리포지토리 인터페이스
    SortCriteria,
    PaginationParams,
    PaginatedResult,
    FilterCriteria,
    QueryOptions,
    IRepository,
    IUserRepository,
    IVideoRepository,
    IAnalysisRepository,
)

# 스토리지 인터페이스의 VideoMetadata를 별도 이름으로 임포트 (DTO와 구분)
from shared.interfaces.storage_interface import VideoMetadata as StorageVideoMetadata

# =============================================================================
# 프로토콜 (Protocols) - v2.0.0 신규
# =============================================================================
from shared.protocols import (
    # 스토리지 프로토콜
    StorageProtocol,
    AsyncStorageProtocol,
    # 카메라 프로토콜
    CameraProtocol,
    MultiCameraProtocol,
)

# =============================================================================
# v2.0.0 DTO - 기하학 기본형
# =============================================================================
from shared.dto import (
    # 2D 기본형
    Point2D,
    Line2D,
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
# v2.0.0 DTO - 추적 데이터
# =============================================================================
from shared.dto import (
    TrackState,
    TrackSource,
    TrackedObjectType,
    TrackHistory,
    KalmanState,
    Track,
    TrackAssociation,
    TrackingResult,
    MultiViewTrackingResult,
)

__all__ = [
    # =========================================================================
    # 상수
    # =========================================================================
    "ErrorCode",
    "GENERAL_ERRORS",
    "AUTH_ERRORS",
    "VALIDATION_ERRORS",
    "INFRASTRUCTURE_ERRORS",
    "ANALYSIS_ERRORS",
    "REFEREE_ERRORS",
    "CONFIGURATION_ERRORS",
    "TaskStatus",
    "AnalysisType",
    "AnalysisPhase",
    "ServiceStatus",
    "QueuePriority",
    "Environment",
    "VALID_TASK_TRANSITIONS",
    "is_valid_transition",
    "EventCategory",
    "EventType",
    "WEBHOOK_EVENTS",
    "REALTIME_EVENTS",
    "AUDIT_EVENTS",
    "METRIC_EVENTS",
    "EVENT_PRIORITY",
    "get_event_priority",
    # =========================================================================
    # 예외
    # =========================================================================
    # 기본
    "CourtViewException",
    "RetryableException",
    "NonRetryableException",
    "CriticalException",
    # 비디오
    "VideoException",
    "VideoFormatException",
    "VideoDownloadException",
    "FrameExtractionException",
    # 감지
    "DetectionException",
    "PersonNotDetectedException",
    "BallNotDetectedException",
    # 포즈 추정
    "PoseEstimationException",
    "InsufficientKeypointsException",
    "OcclusionDetectedException",
    # 동작 분석
    "MotionAnalysisException",
    "ShootingNotDetectedException",
    "DribblingNotDetectedException",
    # 모델
    "ModelException",
    "ModelLoadException",
    "ModelInferenceException",
    # 검증
    "ValidationException",
    "InvalidRequestException",
    "MissingFieldException",
    "ConfigurationException",
    "SchemaValidationException",
    # 인프라
    "DatabaseException",
    "DatabaseConnectionException",
    "DatabaseTimeoutException",
    "DatabaseIntegrityException",
    "CacheException",
    "CacheConnectionException",
    "CacheSerializationException",
    "QueueException",
    "QueueConnectionException",
    "StorageException",
    "S3Exception",
    "S3UploadException",
    "S3DownloadException",
    # =========================================================================
    # DTO — 파이프라인 입출력
    # =========================================================================
    # 비디오 입력
    "VideoSource",
    "VideoMetadata",
    # 파이프라인 옵션
    "PipelineOptions",
    # 파이프라인 요청
    "BasePipelineRequest",
    "GameAnalysisRequest",
    "RefereeAnalysisRequest",
    "PipelineRequest",
    # 파이프라인 진행 상태
    "PipelineProgress",
    # 파이프라인 결과
    "PipelineResultBase",
    "GameAnalysisResult",
    "ViolationCounts",
    "FoulCounts",
    "RefereeAnalysisResult",
    # Backend 동기화
    "SyncEventType",
    "BackendSyncPayload",
    # 피드백
    "FeedbackCategory",
    "FeedbackPriority",
    "FeedbackType",
    "BodyPart",
    "MotionPhase",
    "FeedbackItem",
    "MotionScore",
    "MotionComparison",
    "FeedbackSummary",
    "TrainingRecommendation",
    "TrainingPlan",
    "ProgressMetric",
    "ProgressReport",
    # 경기 분석
    "ShotType",
    "ShotResult",
    "CourtZone",
    "PlayType",
    "GameEventType",
    "HighlightType",
    "ViolationType",
    "FoulType",
    "PlayerInfo",
    "TeamInfo",
    "ShotAttempt",
    "ShotChart",
    "GameEvent",
    "HighlightClip",
    "HighlightReel",
    "PlayerStats",
    "TeamStats",
    "GameStats",
    "ViolationDetection",
    "FoulDetection",
    "RefereeReport",
    # =========================================================================
    # 인터페이스
    # =========================================================================
    # 분석기
    "AnalyzerState",
    "AnalysisResult",
    "AnalyzerMetrics",
    "IAnalyzer",
    "IFrameAnalyzer",
    "ISequenceAnalyzer",
    "IStreamAnalyzer",
    "IComparisonAnalyzer",
    "ComparisonInput",
    "IAnalyzerFactory",
    # 탐지기
    "DetectionTarget",
    "DetectionState",
    "BoundingBox",
    "DetectedObject",
    "DetectionResult",
    "DetectorMetrics",
    "IDetector",
    "BallState",
    "BallDetectionResult",
    "IBallDetector",
    "CourtKeypoints",
    "CourtDetectionResult",
    "ICourtDetector",
    "PlayerDetection",
    "PlayerDetectionResult",
    "IPlayerDetector",
    "HoopDetection",
    "HoopDetectionResult",
    "IHoopDetector",
    "IDetectorFactory",
    "ICompositeDetector",
    # 스토리지
    "StorageType",
    "StorageState",
    "ContentType",
    "SortOrder",
    "FileMetadata",
    "StorageVideoMetadata",
    "UploadResult",
    "DownloadResult",
    "StorageMetrics",
    "RepositoryMetrics",
    "IStorage",
    "IVideoStorage",
    "CacheEntry",
    "ICache",
    "AnalysisResultEntry",
    "IAnalysisResultStorage",
    "IStorageFactory",
    # 리포지토리
    "SortCriteria",
    "PaginationParams",
    "PaginatedResult",
    "FilterCriteria",
    "QueryOptions",
    "IRepository",
    "IUserRepository",
    "IVideoRepository",
    "IAnalysisRepository",
    # =========================================================================
    # 프로토콜 (v2.0.0)
    # =========================================================================
    "StorageProtocol",
    "AsyncStorageProtocol",
    "CameraProtocol",
    "MultiCameraProtocol",
    # =========================================================================
    # v2.0.0 DTO - 기하학 기본형
    # =========================================================================
    "Point2D",
    "Line2D",
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
    # v2.0.0 DTO - 추적 데이터
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
]

__version__ = "2.0.0"
__author__ = "COURTVIEW AI Team"
