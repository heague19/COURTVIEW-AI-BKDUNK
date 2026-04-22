# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: analysis_exceptions.py
설명: 분석 관련 예외 클래스 정의
      - 비디오 처리, 감지, 포즈 추정, 동작 분석 등
      - 39개 예외 클래스 (Retryable 4개, NonRetryable 26개, 기반 9개)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
from typing import Any

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
)


__all__ = [
    # 분석 기본 예외
    "AnalysisException",
    # 비디오 예외
    "VideoException",
    "VideoFormatException",
    "VideoSizeException",
    "VideoDurationException",
    "VideoDownloadException",
    "VideoCorruptedException",
    "FrameExtractionException",
    # 감지 예외
    "DetectionException",
    "PersonNotDetectedException",
    "BallNotDetectedException",
    "CourtNotDetectedException",
    "HoopNotDetectedException",
    "MultiplePersonsDetectedException",
    "LowConfidenceDetectionException",
    # 포즈 추정 예외
    "PoseEstimationException",
    "InsufficientKeypointsException",
    "OcclusionDetectedException",
    # 동작 분석 예외
    "MotionAnalysisException",
    "ShootingNotDetectedException",
    "DribblingNotDetectedException",
    "InsufficientDataException",
    # 생체역학 예외
    "BiomechanicsException",
    "JointAngleCalculationException",
    "ForceCalculationException",
    # 경기 분석 예외
    "GameAnalysisException",
    "TeamDetectionException",
    "ScoreDetectionException",
    "PlayDetectionException",
    # 심판 분석 예외
    "RefereeException",
    "ViolationDetectionException",
    "FoulDetectionException",
    # 피드백 생성 예외
    "FeedbackGenerationException",
    "TemplateNotFoundException",
    "RecommendationException",
    # 모델 예외
    "ModelException",
    "ModelLoadException",
    "ModelInferenceException",
    "ModelNotFoundException",
]


# =============================================================================
# 분석 기본 예외
# =============================================================================

class AnalysisException(CourtViewException):
    """
    분석 관련 기본 예외.

    모든 분석 관련 예외의 기반 클래스입니다.
    """

    def __init__(
        self,
        message: str = "분석 중 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.ANALYSIS_ERROR,
        analysis_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        분석 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            analysis_type: 분석 타입 (training, game, referee 등)
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)
        if analysis_type:
            self.details["analysis_type"] = analysis_type


# =============================================================================
# 비디오 처리 예외
# =============================================================================

class VideoException(CourtViewException):
    """비디오 처리 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.VIDEO_ERROR,
        message: str | None = None,
        video_id: str | None = None,
        video_path: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            video_id: 비디오 식별자
            video_path: 비디오 파일 경로 또는 URL
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if video_id:
            combined_details["video_id"] = video_id
        if video_path:
            combined_details["video_path"] = video_path

        super().__init__(error_code, message, combined_details, cause=cause)
        self.video_id = video_id
        self.video_path = video_path


class VideoFormatException(NonRetryableException):
    """지원하지 않는 비디오 형식 예외."""

    def __init__(
        self,
        format_received: str,
        supported_formats: list[str] | None = None,
        video_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 형식 예외 초기화.

        Args:
            format_received: 수신된 형식
            supported_formats: 지원하는 형식 목록
            video_path: 비디오 경로
            cause: 원인 예외
        """
        supported = supported_formats or ["mp4", "avi", "mov", "mkv"]
        message = f"지원하지 않는 비디오 형식입니다: {format_received}. 지원 형식: {', '.join(supported)}"

        super().__init__(
            ErrorCode.VIDEO_FORMAT_UNSUPPORTED,
            message,
            details={
                "format_received": format_received,
                "supported_formats": supported,
                "video_path": video_path,
            },
            cause=cause,
        )


class VideoSizeException(NonRetryableException):
    """비디오 크기 초과 예외."""

    def __init__(
        self,
        size_bytes: int,
        max_size_bytes: int,
        video_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 크기 예외 초기화.

        Args:
            size_bytes: 실제 크기 (바이트)
            max_size_bytes: 최대 허용 크기 (바이트)
            video_path: 비디오 경로
            cause: 원인 예외
        """
        size_mb = size_bytes / (1024 * 1024)
        max_size_mb = max_size_bytes / (1024 * 1024)
        message = f"비디오 파일이 너무 큽니다: {size_mb:.1f}MB (최대: {max_size_mb:.1f}MB)"

        super().__init__(
            ErrorCode.VIDEO_TOO_LARGE,
            message,
            details={
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "max_size_bytes": max_size_bytes,
                "max_size_mb": round(max_size_mb, 2),
                "video_path": video_path,
            },
            cause=cause,
        )


class VideoDurationException(NonRetryableException):
    """비디오 길이 초과 예외."""

    def __init__(
        self,
        duration_seconds: float,
        max_duration_seconds: float,
        video_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 길이 예외 초기화.

        Args:
            duration_seconds: 실제 길이 (초)
            max_duration_seconds: 최대 허용 길이 (초)
            video_path: 비디오 경로
            cause: 원인 예외
        """
        message = f"비디오 길이가 너무 깁니다: {duration_seconds:.1f}초 (최대: {max_duration_seconds:.1f}초)"

        super().__init__(
            ErrorCode.VIDEO_TOO_LONG,
            message,
            details={
                "duration_seconds": duration_seconds,
                "max_duration_seconds": max_duration_seconds,
                "video_path": video_path,
            },
            cause=cause,
        )


class VideoDownloadException(RetryableException):
    """비디오 다운로드 실패 예외."""

    def __init__(
        self,
        video_url: str,
        status_code: int | None = None,
        cause: Exception | None = None,
        retry_after: float = 5.0,
    ) -> None:
        """
        비디오 다운로드 예외 초기화.

        Args:
            video_url: 다운로드 URL
            status_code: HTTP 상태 코드
            cause: 원인 예외
            retry_after: 재시도 대기 시간
        """
        message = f"비디오 다운로드에 실패했습니다: {video_url}"

        super().__init__(
            ErrorCode.VIDEO_DOWNLOAD_FAILED,
            message,
            details={
                "video_url": video_url,
                "status_code": status_code,
            },
            cause=cause,
            retry_after=retry_after,
        )


class VideoCorruptedException(NonRetryableException):
    """손상된 비디오 예외."""

    def __init__(
        self,
        video_path: str | None = None,
        corruption_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        손상된 비디오 예외 초기화.

        Args:
            video_path: 비디오 경로
            corruption_type: 손상 유형 (header, frames, codec 등)
            cause: 원인 예외
        """
        message = "비디오 파일이 손상되었거나 읽을 수 없습니다"

        super().__init__(
            ErrorCode.VIDEO_CORRUPTED,
            message,
            details={
                "video_path": video_path,
                "corruption_type": corruption_type,
            },
            cause=cause,
        )


class FrameExtractionException(RetryableException):
    """프레임 추출 실패 예외."""

    def __init__(
        self,
        frame_number: int | None = None,
        total_frames: int | None = None,
        video_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        프레임 추출 예외 초기화.

        Args:
            frame_number: 실패한 프레임 번호
            total_frames: 전체 프레임 수
            video_path: 비디오 경로
            cause: 원인 예외
        """
        if frame_number is not None:
            message = f"프레임 {frame_number} 추출에 실패했습니다"
        else:
            message = "프레임 추출에 실패했습니다"

        super().__init__(
            ErrorCode.FRAME_EXTRACTION_FAILED,
            message,
            details={
                "frame_number": frame_number,
                "total_frames": total_frames,
                "video_path": video_path,
            },
            cause=cause,
        )


# =============================================================================
# 감지 예외
# =============================================================================

class DetectionException(CourtViewException):
    """감지 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.DETECTION_ERROR,
        message: str | None = None,
        frame_number: int | None = None,
        detection_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        감지 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            frame_number: 문제 발생 프레임 번호
            detection_type: 감지 유형 (person, ball, court, hoop)
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if frame_number is not None:
            combined_details["frame_number"] = frame_number
        if detection_type:
            combined_details["detection_type"] = detection_type

        super().__init__(error_code, message, combined_details, cause=cause)
        self.frame_number = frame_number
        self.detection_type = detection_type


class PersonNotDetectedException(NonRetryableException):
    """사람 미감지 예외."""

    def __init__(
        self,
        frame_range: tuple[int, int] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        사람 미감지 예외 초기화.

        Args:
            frame_range: 분석한 프레임 범위 (시작, 끝)
            cause: 원인 예외
        """
        message = "영상에서 사람을 감지할 수 없습니다. 사람이 명확하게 보이는 영상을 사용해주세요."

        super().__init__(
            ErrorCode.DETECTION_NO_PERSON,
            message,
            details={"frame_range": frame_range} if frame_range else None,
            cause=cause,
        )


class BallNotDetectedException(NonRetryableException):
    """공 미감지 예외."""

    def __init__(
        self,
        frame_range: tuple[int, int] | None = None,
        frame_index: int | None = None,
        consecutive_misses: int | None = None,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        공 미감지 예외 초기화.

        Args:
            frame_range: 분석한 프레임 범위
            frame_index: 감지 실패한 프레임 인덱스
            consecutive_misses: 연속 미감지 프레임 수
            message: 사용자 정의 오류 메시지
            cause: 원인 예외
        """
        # 사용자 정의 메시지가 없으면 기본 메시지 사용
        if message is None:
            message = "영상에서 농구공을 감지할 수 없습니다. 공이 명확하게 보이는 영상을 사용해주세요."

        # 상세 정보 구성
        details: dict[str, Any] = {}
        if frame_range is not None:
            details["frame_range"] = frame_range
        if frame_index is not None:
            details["frame_index"] = frame_index
        if consecutive_misses is not None:
            details["consecutive_misses"] = consecutive_misses

        super().__init__(
            ErrorCode.DETECTION_NO_BALL,
            message,
            details=details if details else None,
            cause=cause,
        )

        # 인스턴스 속성으로 저장 (추가 접근용)
        self.frame_index = frame_index
        self.consecutive_misses = consecutive_misses


class CourtNotDetectedException(NonRetryableException):
    """코트 미감지 예외."""

    def __init__(
        self,
        frame_range: tuple[int, int] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        코트 미감지 예외 초기화.

        Args:
            frame_range: 분석한 프레임 범위
            cause: 원인 예외
        """
        message = "영상에서 농구 코트를 감지할 수 없습니다. 코트 라인이 보이는 영상을 사용해주세요."

        super().__init__(
            ErrorCode.DETECTION_NO_COURT,
            message,
            details={"frame_range": frame_range} if frame_range else None,
            cause=cause,
        )


class HoopNotDetectedException(NonRetryableException):
    """골대 미감지 예외."""

    def __init__(
        self,
        frame_range: tuple[int, int] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        골대 미감지 예외 초기화.

        Args:
            frame_range: 분석한 프레임 범위
            cause: 원인 예외
        """
        message = "영상에서 골대를 감지할 수 없습니다. 골대가 보이는 영상을 사용해주세요."

        super().__init__(
            ErrorCode.DETECTION_NO_HOOP,
            message,
            details={"frame_range": frame_range} if frame_range else None,
            cause=cause,
        )


class MultiplePersonsDetectedException(NonRetryableException):
    """다수 인물 감지 예외 (1인 분석 시)."""

    def __init__(
        self,
        person_count: int,
        frame_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        다수 인물 감지 예외 초기화.

        Args:
            person_count: 감지된 인원 수
            frame_number: 문제 프레임 번호
            cause: 원인 예외
        """
        message = f"영상에서 {person_count}명이 감지되었습니다. 1인 훈련 분석은 한 명만 촬영된 영상이 필요합니다."

        super().__init__(
            ErrorCode.DETECTION_MULTIPLE_PERSONS,
            message,
            details={
                "person_count": person_count,
                "frame_number": frame_number,
            },
            cause=cause,
        )


class LowConfidenceDetectionException(NonRetryableException):
    """낮은 신뢰도 감지 예외."""

    def __init__(
        self,
        confidence: float,
        min_confidence: float,
        detection_type: str,
        frame_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        낮은 신뢰도 예외 초기화.

        Args:
            confidence: 실제 신뢰도
            min_confidence: 최소 요구 신뢰도
            detection_type: 감지 유형
            frame_number: 프레임 번호
            cause: 원인 예외
        """
        message = f"{detection_type} 감지 신뢰도가 너무 낮습니다: {confidence:.1%} (최소: {min_confidence:.1%})"

        super().__init__(
            ErrorCode.DETECTION_LOW_CONFIDENCE,
            message,
            details={
                "confidence": confidence,
                "min_confidence": min_confidence,
                "detection_type": detection_type,
                "frame_number": frame_number,
            },
            cause=cause,
        )


# =============================================================================
# 포즈 추정 예외
# =============================================================================

class PoseEstimationException(CourtViewException):
    """포즈 추정 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.POSE_ESTIMATION_ERROR,
        message: str | None = None,
        frame_number: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """포즈 추정 예외 초기화."""
        combined_details = details or {}
        if frame_number is not None:
            combined_details["frame_number"] = frame_number

        super().__init__(error_code, message, combined_details, cause=cause)
        self.frame_number = frame_number


class InsufficientKeypointsException(NonRetryableException):
    """키포인트 부족 예외."""

    def __init__(
        self,
        detected_keypoints: int,
        required_keypoints: int,
        missing_keypoints: list[str] | None = None,
        frame_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        키포인트 부족 예외 초기화.

        Args:
            detected_keypoints: 감지된 키포인트 수
            required_keypoints: 필요한 키포인트 수
            missing_keypoints: 누락된 키포인트 이름 목록
            frame_number: 프레임 번호
            cause: 원인 예외
        """
        message = f"포즈 분석에 필요한 키포인트가 부족합니다: {detected_keypoints}/{required_keypoints}"

        super().__init__(
            ErrorCode.POSE_INSUFFICIENT_KEYPOINTS,
            message,
            details={
                "detected_keypoints": detected_keypoints,
                "required_keypoints": required_keypoints,
                "missing_keypoints": missing_keypoints,
                "frame_number": frame_number,
            },
            cause=cause,
        )


class OcclusionDetectedException(NonRetryableException):
    """신체 가림 감지 예외."""

    def __init__(
        self,
        occluded_parts: list[str],
        frame_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        신체 가림 예외 초기화.

        Args:
            occluded_parts: 가려진 신체 부위 목록
            frame_number: 프레임 번호
            cause: 원인 예외
        """
        parts_str = ", ".join(occluded_parts)
        message = f"신체 일부가 가려져 있습니다: {parts_str}. 전신이 보이는 영상을 사용해주세요."

        super().__init__(
            ErrorCode.POSE_OCCLUSION_DETECTED,
            message,
            details={
                "occluded_parts": occluded_parts,
                "frame_number": frame_number,
            },
            cause=cause,
        )


# =============================================================================
# 동작 분석 예외
# =============================================================================

class MotionAnalysisException(CourtViewException):
    """동작 분석 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.MOTION_ANALYSIS_ERROR,
        message: str | None = None,
        motion_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """동작 분석 예외 초기화."""
        combined_details = details or {}
        if motion_type:
            combined_details["motion_type"] = motion_type

        super().__init__(error_code, message, combined_details, cause=cause)
        self.motion_type = motion_type


class ShootingNotDetectedException(NonRetryableException):
    """슈팅 동작 미감지 예외."""

    def __init__(
        self,
        analyzed_frames: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """슈팅 미감지 예외 초기화."""
        message = "영상에서 슈팅 동작을 감지할 수 없습니다. 슈팅 동작이 포함된 영상을 사용해주세요."

        super().__init__(
            ErrorCode.SHOOTING_NOT_DETECTED,
            message,
            details={"analyzed_frames": analyzed_frames} if analyzed_frames else None,
            cause=cause,
        )


class DribblingNotDetectedException(NonRetryableException):
    """드리블 동작 미감지 예외."""

    def __init__(
        self,
        analyzed_frames: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """드리블 미감지 예외 초기화."""
        message = "영상에서 드리블 동작을 감지할 수 없습니다. 드리블 동작이 포함된 영상을 사용해주세요."

        super().__init__(
            ErrorCode.DRIBBLING_NOT_DETECTED,
            message,
            details={"analyzed_frames": analyzed_frames} if analyzed_frames else None,
            cause=cause,
        )


class InsufficientDataException(NonRetryableException):
    """분석 데이터 부족 예외."""

    def __init__(
        self,
        data_type: str,
        received: int,
        required: int,
        cause: Exception | None = None,
    ) -> None:
        """
        데이터 부족 예외 초기화.

        Args:
            data_type: 데이터 유형 (frames, keypoints 등)
            received: 수신된 데이터 양
            required: 필요한 데이터 양
            cause: 원인 예외
        """
        message = f"분석을 위한 {data_type} 데이터가 부족합니다: {received}/{required}"

        super().__init__(
            ErrorCode.MOTION_INSUFFICIENT_DATA,
            message,
            details={
                "data_type": data_type,
                "received": received,
                "required": required,
            },
            cause=cause,
        )


# =============================================================================
# 모델 예외
# =============================================================================

class ModelException(CourtViewException):
    """모델 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.MODEL_ERROR,
        message: str | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """모델 예외 초기화."""
        combined_details = details or {}
        if model_name:
            combined_details["model_name"] = model_name
        if model_version:
            combined_details["model_version"] = model_version

        super().__init__(error_code, message, combined_details, cause=cause)
        self.model_name = model_name
        self.model_version = model_version


class ModelLoadException(RetryableException):
    """모델 로드 실패 예외."""

    def __init__(
        self,
        model_name: str,
        model_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """모델 로드 예외 초기화."""
        message = f"모델 로드에 실패했습니다: {model_name}"

        super().__init__(
            ErrorCode.MODEL_LOAD_FAILED,
            message,
            details={
                "model_name": model_name,
                "model_path": model_path,
            },
            cause=cause,
            retry_after=3.0,
        )


class ModelInferenceException(RetryableException):
    """모델 추론 실패 예외."""

    def __init__(
        self,
        model_name: str,
        input_shape: tuple[int, ...] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """모델 추론 예외 초기화."""
        message = f"모델 추론에 실패했습니다: {model_name}"

        super().__init__(
            ErrorCode.MODEL_INFERENCE_FAILED,
            message,
            details={
                "model_name": model_name,
                "input_shape": input_shape,
            },
            cause=cause,
            retry_after=1.0,
        )


class ModelNotFoundException(NonRetryableException):
    """모델 미발견 예외."""

    def __init__(
        self,
        model_name: str,
        searched_paths: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """모델 미발견 예외 초기화."""
        message = f"모델을 찾을 수 없습니다: {model_name}"

        super().__init__(
            ErrorCode.MODEL_NOT_FOUND,
            message,
            details={
                "model_name": model_name,
                "searched_paths": searched_paths,
            },
            cause=cause,
        )


# =============================================================================
# 생체역학 예외
# =============================================================================

class BiomechanicsException(CourtViewException):
    """생체역학 분석 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.BIOMECHANICS_ERROR,
        message: str | None = None,
        joint_name: str | None = None,
        calculation_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        생체역학 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            joint_name: 관절 이름
            calculation_type: 계산 유형 (angle, velocity, force 등)
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if joint_name:
            combined_details["joint_name"] = joint_name
        if calculation_type:
            combined_details["calculation_type"] = calculation_type

        super().__init__(error_code, message, combined_details, cause=cause)
        self.joint_name = joint_name
        self.calculation_type = calculation_type


class JointAngleCalculationException(NonRetryableException):
    """관절 각도 계산 오류 예외."""

    def __init__(
        self,
        joint_name: str,
        angle_value: float | None = None,
        valid_range: tuple[float, float] | None = None,
        frame_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        관절 각도 계산 예외 초기화.

        Args:
            joint_name: 관절 이름
            angle_value: 계산된 각도 값
            valid_range: 유효 범위 (최소, 최대)
            frame_number: 프레임 번호
            cause: 원인 예외
        """
        message = f"{joint_name} 관절 각도 계산에 오류가 발생했습니다"
        if angle_value is not None and valid_range:
            message += f": {angle_value:.1f}° (유효 범위: {valid_range[0]:.1f}°-{valid_range[1]:.1f}°)"

        super().__init__(
            ErrorCode.BIOMECHANICS_INVALID_ANGLE,
            message,
            details={
                "joint_name": joint_name,
                "angle_value": angle_value,
                "valid_range": valid_range,
                "frame_number": frame_number,
            },
            cause=cause,
        )


class ForceCalculationException(NonRetryableException):
    """힘/속도 계산 오류 예외."""

    def __init__(
        self,
        calculation_type: str,
        body_part: str | None = None,
        calculated_value: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        힘/속도 계산 예외 초기화.

        Args:
            calculation_type: 계산 유형 (velocity, acceleration, force 등)
            body_part: 신체 부위
            calculated_value: 계산된 값
            cause: 원인 예외
        """
        body_part_str = f" ({body_part})" if body_part else ""
        message = f"{calculation_type} 계산에 오류가 발생했습니다{body_part_str}"

        super().__init__(
            ErrorCode.BIOMECHANICS_INVALID_VELOCITY,
            message,
            details={
                "calculation_type": calculation_type,
                "body_part": body_part,
                "calculated_value": calculated_value,
            },
            cause=cause,
        )


# =============================================================================
# 경기 분석 예외
# =============================================================================

class GameAnalysisException(CourtViewException):
    """경기 분석 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.GAME_ANALYSIS_ERROR,
        message: str | None = None,
        game_id: str | None = None,
        quarter: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        경기 분석 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            game_id: 경기 식별자
            quarter: 쿼터 번호
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if game_id:
            combined_details["game_id"] = game_id
        if quarter is not None:
            combined_details["quarter"] = quarter

        super().__init__(error_code, message, combined_details, cause=cause)
        self.game_id = game_id
        self.quarter = quarter


class TeamDetectionException(NonRetryableException):
    """팀 감지 실패 예외."""

    def __init__(
        self,
        expected_teams: int = 2,
        detected_teams: int | None = None,
        frame_range: tuple[int, int] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        팀 감지 예외 초기화.

        Args:
            expected_teams: 예상 팀 수
            detected_teams: 감지된 팀 수
            frame_range: 분석 프레임 범위
            cause: 원인 예외
        """
        if detected_teams is not None:
            message = f"팀 감지에 실패했습니다: {detected_teams}개 팀 감지됨 (예상: {expected_teams}개)"
        else:
            message = "영상에서 팀을 구분할 수 없습니다. 팀 유니폼이 구분되는 영상을 사용해주세요."

        super().__init__(
            ErrorCode.GAME_ANALYSIS_ERROR,
            message,
            details={
                "expected_teams": expected_teams,
                "detected_teams": detected_teams,
                "frame_range": frame_range,
            },
            cause=cause,
        )


class ScoreDetectionException(NonRetryableException):
    """득점 감지 실패 예외."""

    def __init__(
        self,
        frame_number: int | None = None,
        detection_confidence: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        득점 감지 예외 초기화.

        Args:
            frame_number: 문제 프레임 번호
            detection_confidence: 감지 신뢰도
            cause: 원인 예외
        """
        message = "득점 여부를 정확하게 감지할 수 없습니다"

        super().__init__(
            ErrorCode.GAME_ANALYSIS_ERROR,
            message,
            details={
                "frame_number": frame_number,
                "detection_confidence": detection_confidence,
            },
            cause=cause,
        )


class PlayDetectionException(NonRetryableException):
    """플레이 감지 실패 예외."""

    def __init__(
        self,
        play_type: str | None = None,
        frame_range: tuple[int, int] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        플레이 감지 예외 초기화.

        Args:
            play_type: 감지 시도한 플레이 유형
            frame_range: 분석 프레임 범위
            cause: 원인 예외
        """
        if play_type:
            message = f"{play_type} 플레이를 감지할 수 없습니다"
        else:
            message = "경기 플레이를 감지할 수 없습니다"

        super().__init__(
            ErrorCode.GAME_ANALYSIS_ERROR,
            message,
            details={
                "play_type": play_type,
                "frame_range": frame_range,
            },
            cause=cause,
        )


# =============================================================================
# 심판 분석 예외
# =============================================================================

class RefereeException(CourtViewException):
    """AI 심판 분석 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.REFEREE_ERROR,
        message: str | None = None,
        rule_set: str | None = None,
        rule_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        심판 분석 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            rule_set: 규칙 세트 (FIBA, NBA, KBL 등)
            rule_id: 규칙 식별자
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if rule_set:
            combined_details["rule_set"] = rule_set
        if rule_id:
            combined_details["rule_id"] = rule_id

        super().__init__(error_code, message, combined_details, cause=cause)
        self.rule_set = rule_set
        self.rule_id = rule_id


class ViolationDetectionException(NonRetryableException):
    """바이올레이션 감지 실패 예외."""

    def __init__(
        self,
        violation_type: str | None = None,
        frame_number: int | None = None,
        confidence: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        바이올레이션 감지 예외 초기화.

        Args:
            violation_type: 바이올레이션 유형 (traveling, double_dribble 등)
            frame_number: 프레임 번호
            confidence: 감지 신뢰도
            cause: 원인 예외
        """
        if violation_type:
            message = f"{violation_type} 바이올레이션 감지에 실패했습니다"
        else:
            message = "바이올레이션 감지에 실패했습니다"

        super().__init__(
            ErrorCode.REFEREE_ERROR,
            message,
            details={
                "violation_type": violation_type,
                "frame_number": frame_number,
                "confidence": confidence,
            },
            cause=cause,
        )


class FoulDetectionException(NonRetryableException):
    """파울 감지 실패 예외."""

    def __init__(
        self,
        foul_type: str | None = None,
        player_ids: list[str] | None = None,
        frame_number: int | None = None,
        confidence: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        파울 감지 예외 초기화.

        Args:
            foul_type: 파울 유형 (personal, technical 등)
            player_ids: 관련 선수 ID 목록
            frame_number: 프레임 번호
            confidence: 감지 신뢰도
            cause: 원인 예외
        """
        if foul_type:
            message = f"{foul_type} 파울 감지에 실패했습니다"
        else:
            message = "파울 감지에 실패했습니다"

        super().__init__(
            ErrorCode.REFEREE_ERROR,
            message,
            details={
                "foul_type": foul_type,
                "player_ids": player_ids,
                "frame_number": frame_number,
                "confidence": confidence,
            },
            cause=cause,
        )


# =============================================================================
# 피드백 생성 예외
# =============================================================================

class FeedbackGenerationException(CourtViewException):
    """피드백 생성 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.ANALYSIS_ERROR,
        message: str | None = None,
        feedback_type: str | None = None,
        analysis_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        피드백 생성 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            feedback_type: 피드백 유형 (shooting, dribbling, game 등)
            analysis_id: 분석 결과 ID
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if feedback_type:
            combined_details["feedback_type"] = feedback_type
        if analysis_id:
            combined_details["analysis_id"] = analysis_id

        super().__init__(error_code, message, combined_details, cause=cause)
        self.feedback_type = feedback_type
        self.analysis_id = analysis_id


class TemplateNotFoundException(NonRetryableException):
    """피드백 템플릿 미발견 예외."""

    def __init__(
        self,
        template_name: str,
        template_type: str | None = None,
        locale: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        템플릿 미발견 예외 초기화.

        Args:
            template_name: 템플릿 이름
            template_type: 템플릿 유형
            locale: 언어/지역 설정
            cause: 원인 예외
        """
        message = f"피드백 템플릿을 찾을 수 없습니다: {template_name}"

        super().__init__(
            ErrorCode.ANALYSIS_ERROR,
            message,
            details={
                "template_name": template_name,
                "template_type": template_type,
                "locale": locale,
            },
            cause=cause,
        )


class RecommendationException(NonRetryableException):
    """훈련 추천 생성 실패 예외."""

    def __init__(
        self,
        recommendation_type: str,
        analysis_results: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        추천 생성 예외 초기화.

        Args:
            recommendation_type: 추천 유형 (drill, training_plan 등)
            analysis_results: 분석 결과 요약
            cause: 원인 예외
        """
        message = f"{recommendation_type} 추천 생성에 실패했습니다"

        super().__init__(
            ErrorCode.ANALYSIS_ERROR,
            message,
            details={
                "recommendation_type": recommendation_type,
                "has_analysis_results": analysis_results is not None,
            },
            cause=cause,
        )


# =============================================================================
# 모듈 버전 정보
# =============================================================================
__version__ = "1.0.0"
