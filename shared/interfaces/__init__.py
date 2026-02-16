# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/interfaces
파일: __init__.py
설명: 인터페이스 모듈 패키지 초기화 - 모든 추상 인터페이스 내보내기

작성자: COURTVIEW AI Team
최종 수정: 2025-12-24
"""

# =============================================================================
# 분석기 인터페이스
# =============================================================================
from shared.interfaces.analyzer_interface import (
    # 상태
    AnalyzerState,
    # 결과 및 메트릭
    AnalysisResult,
    AnalyzerMetrics,
    # 기본 인터페이스
    IAnalyzer,
    # 특화 인터페이스
    IFrameAnalyzer,
    ISequenceAnalyzer,
    IStreamAnalyzer,
    IComparisonAnalyzer,
    # 비교 입력
    ComparisonInput,
    # 팩토리
    IAnalyzerFactory,
)

# =============================================================================
# 탐지기 인터페이스
# =============================================================================
from shared.interfaces.detector_interface import (
    # 열거형
    DetectionTarget,
    DetectionState,
    PlayerRole,
    ColorFormat,
    # 바운딩 박스
    BoundingBox,
    # 프레임 데이터
    FrameData,
    # 기본 탐지 결과
    DetectedObject,
    DetectionResult,
    # 메트릭
    DetectorMetrics,
    # 기본 인터페이스
    IDetector,
    # 공 탐지
    BallState,
    BallDetectionResult,
    IBallDetector,
    # 코트 탐지
    CourtKeypoints,
    CourtDetectionResult,
    ICourtDetector,
    # 선수 탐지
    PlayerDetection,
    PlayerDetectionResult,
    IPlayerDetector,
    # 포즈 추정
    PoseKeypoint,
    BodySegment,
    KeypointData,
    JointAngle,
    SegmentData,
    PoseEstimation,
    PoseEstimationResult,
    IPoseEstimator,
    # 골대 탐지
    HoopDetection,
    HoopDetectionResult,
    IHoopDetector,
    # 추적 (Tracking)
    TrackingResult,
    TrackState,
    ITracker,
    TrackerMetrics,
    # 팩토리 및 복합
    IDetectorFactory,
    ICompositeDetector,
    # 콜백 프로토콜
    DetectionCallback,
)

# =============================================================================
# 스토리지 인터페이스
# =============================================================================
from shared.interfaces.storage_interface import (
    # 열거형
    StorageType,
    StorageState,
    ContentType,
    SortOrder,
    # 메타데이터
    FileMetadata,
    VideoMetadata,
    # 결과
    UploadResult,
    DownloadResult,
    # 메트릭
    StorageMetrics,
    RepositoryMetrics,
    # 기본 스토리지
    IStorage,
    # 비디오 스토리지
    IVideoStorage,
    # 캐시
    CacheEntry,
    ICache,
    # 분석 결과 스토리지
    AnalysisResultEntry,
    IAnalysisResultStorage,
    # 리포지토리
    SortCriteria,
    PaginationParams,
    PaginatedResult,
    FilterCriteria,
    QueryOptions,
    IRepository,
    IUserRepository,
    IVideoRepository,
    IAnalysisRepository,
    # 팩토리
    IStorageFactory,
)

# =============================================================================
# 경기 분석 인터페이스
# =============================================================================
from shared.interfaces.game_interface import (
    # 상태 열거형
    GameModuleState,
    # 결과 데이터클래스
    GameEventResult,
    ValidationResult,
    FusionResult,
    # 메트릭
    GameModuleMetrics,
    # 인터페이스
    IGameEventDetector,
    IRefereeValidator,
    IMultiViewFusion,
)

__all__ = [
    # =========================================================================
    # 분석기 인터페이스
    # =========================================================================
    # 상태
    "AnalyzerState",
    # 결과 및 메트릭
    "AnalysisResult",
    "AnalyzerMetrics",
    # 기본 인터페이스
    "IAnalyzer",
    # 특화 인터페이스
    "IFrameAnalyzer",
    "ISequenceAnalyzer",
    "IStreamAnalyzer",
    "IComparisonAnalyzer",
    # 비교 입력
    "ComparisonInput",
    # 팩토리
    "IAnalyzerFactory",
    # =========================================================================
    # 탐지기 인터페이스
    # =========================================================================
    # 열거형
    "DetectionTarget",
    "DetectionState",
    "PlayerRole",
    "ColorFormat",
    # 바운딩 박스
    "BoundingBox",
    # 프레임 데이터
    "FrameData",
    # 기본 탐지 결과
    "DetectedObject",
    "DetectionResult",
    # 메트릭
    "DetectorMetrics",
    # 기본 인터페이스
    "IDetector",
    # 공 탐지
    "BallState",
    "BallDetectionResult",
    "IBallDetector",
    # 코트 탐지
    "CourtKeypoints",
    "CourtDetectionResult",
    "ICourtDetector",
    # 선수 탐지
    "PlayerDetection",
    "PlayerDetectionResult",
    "IPlayerDetector",
    # 포즈 추정
    "PoseKeypoint",
    "BodySegment",
    "KeypointData",
    "JointAngle",
    "SegmentData",
    "PoseEstimation",
    "PoseEstimationResult",
    "IPoseEstimator",
    # 골대 탐지
    "HoopDetection",
    "HoopDetectionResult",
    "IHoopDetector",
    # 추적 (Tracking)
    "TrackingResult",
    "TrackState",
    "ITracker",
    "TrackerMetrics",
    # 팩토리 및 복합
    "IDetectorFactory",
    "ICompositeDetector",
    # 콜백 프로토콜
    "DetectionCallback",
    # =========================================================================
    # 스토리지 인터페이스
    # =========================================================================
    # 열거형
    "StorageType",
    "StorageState",
    "ContentType",
    "SortOrder",
    # 메타데이터
    "FileMetadata",
    "VideoMetadata",
    # 결과
    "UploadResult",
    "DownloadResult",
    # 메트릭
    "StorageMetrics",
    "RepositoryMetrics",
    # 기본 스토리지
    "IStorage",
    # 비디오 스토리지
    "IVideoStorage",
    # 캐시
    "CacheEntry",
    "ICache",
    # 분석 결과 스토리지
    "AnalysisResultEntry",
    "IAnalysisResultStorage",
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
    # 팩토리
    "IStorageFactory",
    # =========================================================================
    # 경기 분석 인터페이스
    # =========================================================================
    # 상태 열거형
    "GameModuleState",
    # 결과 데이터클래스
    "GameEventResult",
    "ValidationResult",
    "FusionResult",
    # 메트릭
    "GameModuleMetrics",
    # 인터페이스
    "IGameEventDetector",
    "IRefereeValidator",
    "IMultiViewFusion",
]

__version__ = "1.0.0"
