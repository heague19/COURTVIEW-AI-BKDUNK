# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: __init__.py
설명: 예외 모듈 패키지 초기화 - 모든 커스텀 예외 클래스 내보내기

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 기본 예외 클래스
# =============================================================================
from shared.exceptions.base_exception import (
    CourtViewException,
    CriticalException,
    NonRetryableException,
    RetryableException,
)

# =============================================================================
# 분석 관련 예외
# =============================================================================
from shared.exceptions.analysis_exceptions import (
    # 분석 기본 예외
    AnalysisException,
    # 비디오 예외 (7개)
    VideoException,
    VideoFormatException,
    VideoSizeException,
    VideoDurationException,
    VideoDownloadException,
    VideoCorruptedException,
    FrameExtractionException,
    # 감지 예외 (7개)
    DetectionException,
    PersonNotDetectedException,
    BallNotDetectedException,
    CourtNotDetectedException,
    HoopNotDetectedException,
    MultiplePersonsDetectedException,
    LowConfidenceDetectionException,
    # 포즈 추정 예외 (3개)
    PoseEstimationException,
    InsufficientKeypointsException,
    OcclusionDetectedException,
    # 동작 분석 예외 (4개)
    MotionAnalysisException,
    ShootingNotDetectedException,
    DribblingNotDetectedException,
    InsufficientDataException,
    # 생체역학 예외 (3개)
    BiomechanicsException,
    JointAngleCalculationException,
    ForceCalculationException,
    # 경기 분석 예외 (4개)
    GameAnalysisException,
    TeamDetectionException,
    ScoreDetectionException,
    PlayDetectionException,
    # 심판 분석 예외 (3개)
    RefereeException,
    ViolationDetectionException,
    FoulDetectionException,
    # 피드백 생성 예외 (3개)
    FeedbackGenerationException,
    TemplateNotFoundException,
    RecommendationException,
    # 모델 예외 (4개)
    ModelException,
    ModelLoadException,
    ModelInferenceException,
    ModelNotFoundException,
)

# =============================================================================
# 유효성 검사 예외
# =============================================================================
from shared.exceptions.validation_exceptions import (
    # 기본 유효성 검사 예외 (3개)
    ValidationException,
    InvalidRequestException,
    InputValidationException,
    # 필드 유효성 검사 예외 (3개)
    MissingFieldException,
    InvalidFieldTypeException,
    InvalidFieldValueException,
    # 값 범위/길이 예외 (2개)
    ValueOutOfRangeException,
    StringLengthException,
    # 데이터 형식 예외 (3개)
    InvalidEnumValueException,
    InvalidJsonFormatException,
    InvalidDateFormatException,
    # URL/보안 예외 (2개)
    URLValidationException,
    SecurityException,
    # 파일 포맷 예외 (4개)
    FormatDetectionException,
    UnsupportedFormatException,
    FormatValidationException,
    ResolutionException,
    # 설정 예외 (5개)
    ConfigurationException,
    ConfigurationNotFoundException,
    ConfigurationLoadException,
    ConfigurationParseException,
    ConfigurationValidationException,
    # 스키마 유효성 검사 예외 (1개)
    SchemaValidationException,
    # 인증/권한 예외 (2개)
    AuthenticationException,
    AuthorizationException,
    # 속도 제한 예외 (1개)
    RateLimitException,
    # 데이터 품질 예외 (2개)
    DataQualityException,
    LowQualityException,
    # 규칙 세트 예외 (3개) - v3.0.0
    RuleSetNotFoundException,
    RuleSetValidationException,
    RuleSetVersionMismatchException,
)

# =============================================================================
# Desktop 하드웨어 예외 (GPU/멀티카메라 동기화)
# =============================================================================
from shared.exceptions.desktop_exceptions import (
    # GPU/하드웨어 예외 (13개)
    DesktopHardwareException,
    GPUException,
    GPUMemoryException,
    GPUMemoryAllocationException,
    GPUMemoryFragmentationException,
    CUDAException,
    CUDADeviceNotFoundException,
    CUDADriverException,
    GPUTemperatureException,
    GPUPowerException,
    GPUComputeCapabilityException,
    TensorRTException,
    ModelOptimizationException,
    # 멀티카메라 동기화 예외 (9개)
    MultiCameraException,
    CameraSyncException,
    CameraTimestampDriftException,
    CameraFrameDropException,
    CameraSyncLossException,
    CameraBufferOverflowException,
    CameraGenlockException,
    MultiViewCalibrationException,
    CoordinateTransformException,
)

# =============================================================================
# 인프라 예외
# =============================================================================
from shared.exceptions.infrastructure_exceptions import (
    # 인프라 기본 예외 (3개)
    InfrastructureException,
    TimeoutException,
    CircuitBreakerOpenException,
    # 데이터베이스 예외 (7개)
    DatabaseException,
    DatabaseConnectionException,
    DatabaseTimeoutException,
    DatabaseIntegrityException,
    TransactionException,
    RecordNotFoundException,
    ConnectionPoolException,
    # 캐시 예외 (5개)
    CacheException,
    CacheConnectionException,
    CacheKeyNotFoundException,
    CacheSerializationException,
    RedisException,
    # 메시지 큐/워커 예외 (9개)
    QueueException,
    QueueConnectionException,
    TaskEnqueueException,
    TaskExecutionException,
    TaskTimeoutException,
    EventBusException,
    WorkerException,
    NotificationException,
    AlertDeliveryException,
    AlertConfigurationException,
    CleanupException,
    # 스토리지 예외 (10개)
    StorageException,
    S3Exception,
    S3UploadException,
    S3DownloadException,
    S3ObjectNotFoundException,
    S3PermissionException,
    MetadataExtractionException,
    LocalStorageException,
    DiskSpaceException,
    FilePermissionException,
    # 스트림/연결 예외 (2개)
    StreamException,
    ConnectionException,
    # 외부 서비스 예외 (2개)
    ExternalServiceException,
    WebhookException,
    # 디코딩 예외 (3개)
    DecodingException,
    CodecException,
    CorruptedFileException,
    # 프레임 추출 예외 (2개)
    InfraFrameExtractionException,
    EndOfStreamException,
    # 비디오 정규화 예외 (2개)
    NormalizationException,
    InfraResolutionException,
    # 분류/샘플링 예외 (2개)
    ClassificationException,
    SamplingException,
    # 프레임 정렬/동기화 예외 (3개, v3.0.0)
    AlignmentException,
    FrameDropException,
    SyncException,
    # 카메라/캘리브레이션/설정 예외 (9개, v3.0.0)
    CameraException,
    CameraConnectionException,
    CameraTimeoutException,
    CalibrationException,
    TransformationException,
    CalibrationRequiredException,
    InfraInsufficientDataException,
    InfraConfigurationException,
    InfraValidationException,
)

__all__ = [
    # ==========================================================================
    # 기본 예외 클래스 (4개)
    # ==========================================================================
    "CourtViewException",
    "RetryableException",
    "NonRetryableException",
    "CriticalException",
    # ==========================================================================
    # 분석 관련 예외 (38개)
    # ==========================================================================
    # 분석 기본 예외 (1개)
    "AnalysisException",
    # 비디오 예외 (7개)
    "VideoException",
    "VideoFormatException",
    "VideoSizeException",
    "VideoDurationException",
    "VideoDownloadException",
    "VideoCorruptedException",
    "FrameExtractionException",
    # 감지 예외 (7개)
    "DetectionException",
    "PersonNotDetectedException",
    "BallNotDetectedException",
    "CourtNotDetectedException",
    "HoopNotDetectedException",
    "MultiplePersonsDetectedException",
    "LowConfidenceDetectionException",
    # 포즈 추정 예외 (3개)
    "PoseEstimationException",
    "InsufficientKeypointsException",
    "OcclusionDetectedException",
    # 동작 분석 예외 (4개)
    "MotionAnalysisException",
    "ShootingNotDetectedException",
    "DribblingNotDetectedException",
    "InsufficientDataException",
    # 생체역학 예외 (3개)
    "BiomechanicsException",
    "JointAngleCalculationException",
    "ForceCalculationException",
    # 경기 분석 예외 (4개)
    "GameAnalysisException",
    "TeamDetectionException",
    "ScoreDetectionException",
    "PlayDetectionException",
    # 심판 분석 예외 (3개)
    "RefereeException",
    "ViolationDetectionException",
    "FoulDetectionException",
    # 피드백 생성 예외 (3개)
    "FeedbackGenerationException",
    "TemplateNotFoundException",
    "RecommendationException",
    # 모델 예외 (4개)
    "ModelException",
    "ModelLoadException",
    "ModelInferenceException",
    "ModelNotFoundException",
    # ==========================================================================
    # 유효성 검사 예외 (31개)
    # ==========================================================================
    # 기본 유효성 검사 예외 (3개)
    "ValidationException",
    "InvalidRequestException",
    "InputValidationException",
    # 필드 유효성 검사 예외 (3개)
    "MissingFieldException",
    "InvalidFieldTypeException",
    "InvalidFieldValueException",
    # 값 범위/길이 예외 (2개)
    "ValueOutOfRangeException",
    "StringLengthException",
    # 데이터 형식 예외 (3개)
    "InvalidEnumValueException",
    "InvalidJsonFormatException",
    "InvalidDateFormatException",
    # URL/보안 예외 (2개)
    "URLValidationException",
    "SecurityException",
    # 파일 포맷 예외 (4개)
    "FormatDetectionException",
    "UnsupportedFormatException",
    "FormatValidationException",
    "ResolutionException",
    # 설정 예외 (5개)
    "ConfigurationException",
    "ConfigurationNotFoundException",
    "ConfigurationLoadException",
    "ConfigurationParseException",
    "ConfigurationValidationException",
    # 스키마 유효성 검사 예외 (1개)
    "SchemaValidationException",
    # 인증/권한 예외 (2개)
    "AuthenticationException",
    "AuthorizationException",
    # 속도 제한 예외 (1개)
    "RateLimitException",
    # 데이터 품질 예외 (2개)
    "DataQualityException",
    "LowQualityException",
    # 규칙 세트 예외 (3개) - v3.0.0
    "RuleSetNotFoundException",
    "RuleSetValidationException",
    "RuleSetVersionMismatchException",
    # ==========================================================================
    # 인프라 예외 (47개)
    # ==========================================================================
    # 인프라 기본 예외 (3개)
    "InfrastructureException",
    "TimeoutException",
    "CircuitBreakerOpenException",
    # 데이터베이스 예외 (7개)
    "DatabaseException",
    "DatabaseConnectionException",
    "DatabaseTimeoutException",
    "DatabaseIntegrityException",
    "TransactionException",
    "RecordNotFoundException",
    "ConnectionPoolException",
    # 캐시 예외 (5개)
    "CacheException",
    "CacheConnectionException",
    "CacheKeyNotFoundException",
    "CacheSerializationException",
    "RedisException",
    # 메시지 큐/워커 예외 (9개)
    "QueueException",
    "QueueConnectionException",
    "TaskEnqueueException",
    "TaskExecutionException",
    "TaskTimeoutException",
    "EventBusException",
    "WorkerException",
    "NotificationException",
    "AlertDeliveryException",
    "AlertConfigurationException",
    "CleanupException",
    # 스토리지 예외 (10개)
    "StorageException",
    "S3Exception",
    "S3UploadException",
    "S3DownloadException",
    "S3ObjectNotFoundException",
    "S3PermissionException",
    "MetadataExtractionException",
    "LocalStorageException",
    "DiskSpaceException",
    "FilePermissionException",
    # 스트림/연결 예외 (2개)
    "StreamException",
    "ConnectionException",
    # 외부 서비스 예외 (2개)
    "ExternalServiceException",
    "WebhookException",
    # 디코딩 예외 (3개)
    "DecodingException",
    "CodecException",
    "CorruptedFileException",
    # 프레임 추출 예외 (2개)
    "InfraFrameExtractionException",
    "EndOfStreamException",
    # 비디오 정규화 예외 (2개)
    "NormalizationException",
    "InfraResolutionException",
    # 분류/샘플링 예외 (2개)
    "ClassificationException",
    "SamplingException",
    # 프레임 정렬/동기화 예외 (3개, v3.0.0)
    "AlignmentException",
    "FrameDropException",
    "SyncException",
    # ==========================================================================
    # Desktop 하드웨어 예외 (22개)
    # ==========================================================================
    # GPU/하드웨어 예외 (13개)
    "DesktopHardwareException",
    "GPUException",
    "GPUMemoryException",
    "GPUMemoryAllocationException",
    "GPUMemoryFragmentationException",
    "CUDAException",
    "CUDADeviceNotFoundException",
    "CUDADriverException",
    "GPUTemperatureException",
    "GPUPowerException",
    "GPUComputeCapabilityException",
    "TensorRTException",
    "ModelOptimizationException",
    # 멀티카메라 동기화 예외 (9개)
    "MultiCameraException",
    "CameraSyncException",
    "CameraTimestampDriftException",
    "CameraFrameDropException",
    "CameraSyncLossException",
    "CameraBufferOverflowException",
    "CameraGenlockException",
    "MultiViewCalibrationException",
    "CoordinateTransformException",
    # ==========================================================================
    # 인프라 카메라/캘리브레이션/설정 예외 (9개, v3.0.0)
    # ==========================================================================
    "CameraException",
    "CameraConnectionException",
    "CameraTimeoutException",
    "CalibrationException",
    "TransformationException",
    "CalibrationRequiredException",
    "InfraInsufficientDataException",
    "InfraConfigurationException",
    "InfraValidationException",
]

__version__ = "1.0.0"
