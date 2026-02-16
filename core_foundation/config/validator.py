# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: core_foundation/config
파일: validator.py
설명: 설정 스키마 검증, Pydantic 기반 유효성 검사

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - Pydantic 기반 설정 스키마 정의
    - Desktop 전용 스키마 (GPU, 카메라, 로컬 스토리지, SQLite)
    - AI 모델 및 분석 파이프라인 설정 검증
    - 타입 강제 변환 및 기본값 적용
    - 커스텀 검증 규칙 지원
    - 상세한 검증 오류 보고

사용 예시:
    # 스키마 모델 직접 사용
    gpu_config = GPUConfig(device_id=0, memory_limit_gb=12.0)

    # 검증기 사용
    validator = SchemaValidator()
    result = validator.validate(config_dict, AppConfig)

    # 헬퍼 함수 사용
    validated = validate_config(config_dict, GPUConfig)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Generic,
    Type,
    TypeVar,
)

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# =============================================================================
# 프로젝트 모듈 (shared)
# =============================================================================
from shared.exceptions.validation_exceptions import SchemaValidationException

# =============================================================================
# 로거 설정
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 타입 변수
# =============================================================================
T = TypeVar("T", bound=BaseModel)
ConfigT = TypeVar("ConfigT", bound="BaseConfigModel")


# =============================================================================
# 검증 상태 Enum
# =============================================================================
class ValidationStatus(Enum):
    """
    검증 상태.

    검증 결과의 상태를 나타냅니다.
    """

    SUCCESS = "success"      # 검증 성공
    FAILED = "failed"        # 검증 실패
    PARTIAL = "partial"      # 부분 성공 (일부 필드 검증 실패)
    SKIPPED = "skipped"      # 검증 건너뜀


# =============================================================================
# 검증 결과 데이터 클래스
# =============================================================================
@dataclass
class ValidationErrorDetail:
    """
    단일 검증 오류.

    Attributes:
        field: 오류가 발생한 필드 경로
        message: 오류 메시지
        error_type: 오류 타입 (Pydantic 오류 타입)
        input_value: 입력된 값
    """

    field: str
    message: str
    error_type: str
    input_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "field": self.field,
            "message": self.message,
            "error_type": self.error_type,
            "input_value": self.input_value,
        }


@dataclass
class ValidationResult(Generic[T]):
    """
    검증 결과.

    Attributes:
        status: 검증 상태
        data: 검증된 데이터 (성공 시)
        errors: 검증 오류 목록
        schema_name: 스키마 이름
        validated_at: 검증 시각
    """

    status: ValidationStatus
    data: T | None = None
    errors: list[ValidationErrorDetail] = field(default_factory=list)
    schema_name: str | None = None
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_valid(self) -> bool:
        """검증 성공 여부."""
        return self.status == ValidationStatus.SUCCESS

    @property
    def error_count(self) -> int:
        """오류 수."""
        return len(self.errors)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "errors": [e.to_dict() for e in self.errors],
            "schema_name": self.schema_name,
            "validated_at": self.validated_at.isoformat(),
        }


# =============================================================================
# 기본 설정 모델
# =============================================================================
class BaseConfigModel(BaseModel):
    """
    설정 모델 기본 클래스.

    모든 설정 스키마의 기반이 되는 클래스입니다.
    """

    model_config = {
        "extra": "ignore",              # 알 수 없는 필드 무시
        "validate_default": True,       # 기본값도 검증
        "str_strip_whitespace": True,   # 문자열 공백 제거
        "frozen": False,                # 변경 가능
    }


# =============================================================================
# 로컬 데이터베이스 설정 스키마 (SQLite)
# =============================================================================
class LocalDatabaseConfig(BaseConfigModel):
    """
    로컬 데이터베이스 설정 스키마.

    Desktop 환경에서 SQLite 데이터베이스 설정을 정의합니다.
    WAL 모드 + NORMAL 동기화로 최적 성능을 제공합니다.

    Attributes:
        db_path: 데이터베이스 파일 경로
        journal_mode: SQLite 저널 모드 (WAL 권장: 동시 읽기/쓰기)
        cache_size: 캐시 크기 (음수=KB 단위, -64000=64MB)
        busy_timeout: 잠금 대기 시간 (ms)
        foreign_keys: 외래 키 제약 활성화
        synchronous: 동기화 모드 (NORMAL: 성능/안정성 균형)
        temp_store: 임시 저장소 (MEMORY: 성능 향상)
        mmap_size: 메모리 매핑 크기 (바이트, 0=비활성)
        max_page_count: 최대 페이지 수 (0=무제한)
        auto_vacuum: 자동 VACUUM 모드 (INCREMENTAL: 점진적 정리)
    """

    db_path: str = Field(
        default="data/courtview.db",
        min_length=1,
        description="데이터베이스 파일 경로",
    )
    journal_mode: str = Field(
        default="WAL",
        description="SQLite 저널 모드",
    )
    cache_size: int = Field(
        default=-64000,
        description="캐시 크기 (음수=KB 단위, -64000=64MB)",
    )
    busy_timeout: int = Field(
        default=5000,
        ge=100,
        le=60000,
        description="잠금 대기 시간 (ms)",
    )
    foreign_keys: bool = Field(
        default=True,
        description="외래 키 제약 활성화",
    )
    synchronous: str = Field(
        default="NORMAL",
        description="동기화 모드",
    )
    temp_store: str = Field(
        default="MEMORY",
        description="임시 저장소",
    )
    mmap_size: int = Field(
        default=268435456,
        ge=0,
        description="메모리 매핑 크기 (바이트, 기본 256MB)",
    )
    max_page_count: int = Field(
        default=0,
        ge=0,
        description="최대 페이지 수 (0=무제한)",
    )
    auto_vacuum: str = Field(
        default="INCREMENTAL",
        description="자동 VACUUM 모드",
    )

    @field_validator("journal_mode")
    @classmethod
    def validate_journal_mode(cls, v: str) -> str:
        """저널 모드 검증."""
        valid_modes = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
        v_upper = v.upper()
        if v_upper not in valid_modes:
            raise ValueError(f"유효하지 않은 저널 모드: {v}. 허용: {valid_modes}")
        return v_upper

    @field_validator("synchronous")
    @classmethod
    def validate_synchronous(cls, v: str) -> str:
        """동기화 모드 검증."""
        valid_modes = {"OFF", "NORMAL", "FULL", "EXTRA"}
        v_upper = v.upper()
        if v_upper not in valid_modes:
            raise ValueError(f"유효하지 않은 동기화 모드: {v}. 허용: {valid_modes}")
        return v_upper

    @field_validator("auto_vacuum")
    @classmethod
    def validate_auto_vacuum(cls, v: str) -> str:
        """자동 VACUUM 모드 검증."""
        valid_modes = {"NONE", "FULL", "INCREMENTAL"}
        v_upper = v.upper()
        if v_upper not in valid_modes:
            raise ValueError(f"유효하지 않은 VACUUM 모드: {v}. 허용: {valid_modes}")
        return v_upper

    @property
    def connection_string(self) -> str:
        """SQLAlchemy 연결 문자열 생성."""
        return f"sqlite:///{self.db_path}"

    @property
    def pragma_settings(self) -> dict[str, Any]:
        """SQLite PRAGMA 설정 딕셔너리 반환."""
        return {
            "journal_mode": self.journal_mode,
            "cache_size": self.cache_size,
            "busy_timeout": self.busy_timeout,
            "foreign_keys": int(self.foreign_keys),
            "synchronous": self.synchronous,
            "temp_store": self.temp_store,
            "mmap_size": self.mmap_size,
            "auto_vacuum": self.auto_vacuum,
        }


# =============================================================================
# GPU 설정 스키마
# =============================================================================
class GPUConfig(BaseConfigModel):
    """
    GPU 설정 스키마.

    Desktop 환경에서 CUDA/TensorRT GPU 설정을 정의합니다.
    RTX 4080/4090 기준 최적 기본값을 제공합니다.

    Attributes:
        device_id: CUDA 디바이스 ID (0=기본 GPU)
        memory_limit_gb: GPU 메모리 제한 (GB, 0=무제한)
        memory_fraction: GPU 메모리 사용 비율 (0.0-1.0)
        tensorrt_enabled: TensorRT 최적화 활성화
        tensorrt_cache_dir: TensorRT 엔진 캐시 디렉토리
        tensorrt_workspace_gb: TensorRT 워크스페이스 크기 (GB)
        precision: 기본 추론 정밀도 (fp16 권장: 성능/정확도 균형)
        allow_growth: 동적 메모리 할당 (True 권장)
        benchmark_mode: cuDNN 벤치마크 모드 (입력 크기 고정 시 성능 향상)
        deterministic: 결정론적 연산 (재현성, 성능 약간 저하)
        fallback_to_cpu: GPU 사용 불가 시 CPU 폴백
    """

    device_id: int = Field(
        default=0,
        ge=0,
        le=7,
        description="CUDA 디바이스 ID",
    )
    memory_limit_gb: float = Field(
        default=0.0,
        ge=0.0,
        le=48.0,
        description="GPU 메모리 제한 (GB, 0=무제한)",
    )
    memory_fraction: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="GPU 메모리 사용 비율",
    )
    tensorrt_enabled: bool = Field(
        default=True,
        description="TensorRT 최적화 활성화",
    )
    tensorrt_cache_dir: str = Field(
        default="cache/tensorrt",
        description="TensorRT 엔진 캐시 디렉토리",
    )
    tensorrt_workspace_gb: float = Field(
        default=4.0,
        ge=0.5,
        le=16.0,
        description="TensorRT 워크스페이스 크기 (GB)",
    )
    precision: str = Field(
        default="fp16",
        description="기본 추론 정밀도",
    )
    allow_growth: bool = Field(
        default=True,
        description="동적 메모리 할당",
    )
    benchmark_mode: bool = Field(
        default=True,
        description="cuDNN 벤치마크 모드",
    )
    deterministic: bool = Field(
        default=False,
        description="결정론적 연산 (재현성)",
    )
    fallback_to_cpu: bool = Field(
        default=True,
        description="GPU 사용 불가 시 CPU 폴백",
    )

    @field_validator("precision")
    @classmethod
    def validate_precision(cls, v: str) -> str:
        """추론 정밀도 검증."""
        valid_precisions = {"fp32", "fp16", "int8", "bf16"}
        if v.lower() not in valid_precisions:
            raise ValueError(f"유효하지 않은 정밀도: {v}. 허용: {valid_precisions}")
        return v.lower()

    @property
    def cuda_device(self) -> str:
        """CUDA 디바이스 문자열 반환."""
        return f"cuda:{self.device_id}"


# =============================================================================
# 카메라 설정 스키마
# =============================================================================
class CameraConfig(BaseConfigModel):
    """
    카메라 설정 스키마.

    Desktop 멀티 카메라 시스템 설정을 정의합니다.
    Genlock 하드웨어 동기화로 ±1ms 정밀도를 지원합니다.

    Attributes:
        count: 카메라 수 (1-8)
        resolution_width: 해상도 너비
        resolution_height: 해상도 높이
        fps: 프레임 레이트
        sync_mode: 동기화 모드 (genlock: ±1ms, software: ±16ms, none)
        buffer_size: 프레임 버퍼 크기 (프레임 수)
        auto_exposure: 자동 노출 활성화
        codec: 비디오 코덱
        pixel_format: 픽셀 포맷 (bgr24: OpenCV 기본)
        calibration_dir: 카메라 캘리브레이션 파일 디렉토리
    """

    count: int = Field(
        default=4,
        ge=1,
        le=8,
        description="카메라 수",
    )
    resolution_width: int = Field(
        default=1920,
        ge=640,
        le=7680,
        description="해상도 너비",
    )
    resolution_height: int = Field(
        default=1080,
        ge=480,
        le=4320,
        description="해상도 높이",
    )
    fps: int = Field(
        default=30,
        ge=15,
        le=120,
        description="프레임 레이트",
    )
    sync_mode: str = Field(
        default="genlock",
        description="동기화 모드",
    )
    buffer_size: int = Field(
        default=30,
        ge=5,
        le=300,
        description="프레임 버퍼 크기 (프레임 수)",
    )
    auto_exposure: bool = Field(
        default=True,
        description="자동 노출 활성화",
    )
    codec: str = Field(
        default="h264",
        description="비디오 코덱",
    )
    pixel_format: str = Field(
        default="bgr24",
        description="픽셀 포맷",
    )
    calibration_dir: str = Field(
        default="data/calibration",
        description="카메라 캘리브레이션 파일 디렉토리",
    )

    @field_validator("sync_mode")
    @classmethod
    def validate_sync_mode(cls, v: str) -> str:
        """동기화 모드 검증."""
        valid_modes = {"genlock", "software", "none"}
        v_lower = v.lower()
        if v_lower not in valid_modes:
            raise ValueError(f"유효하지 않은 동기화 모드: {v}. 허용: {valid_modes}")
        return v_lower

    @field_validator("codec")
    @classmethod
    def validate_codec(cls, v: str) -> str:
        """비디오 코덱 검증."""
        valid_codecs = {"h264", "h265", "hevc", "mjpeg", "raw"}
        v_lower = v.lower()
        if v_lower not in valid_codecs:
            raise ValueError(f"유효하지 않은 코덱: {v}. 허용: {valid_codecs}")
        return v_lower

    @field_validator("pixel_format")
    @classmethod
    def validate_pixel_format(cls, v: str) -> str:
        """픽셀 포맷 검증."""
        valid_formats = {"bgr24", "rgb24", "yuv420p", "nv12", "gray"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"유효하지 않은 픽셀 포맷: {v}. 허용: {valid_formats}")
        return v_lower

    @property
    def resolution(self) -> tuple:
        """해상도 튜플 반환 (width, height)."""
        return (self.resolution_width, self.resolution_height)

    @property
    def total_pixels_per_second(self) -> int:
        """초당 총 픽셀 수 (카메라 전체 합계)."""
        return self.resolution_width * self.resolution_height * self.fps * self.count


# =============================================================================
# AI 모델 설정 스키마
# =============================================================================
class ModelConfig(BaseConfigModel):
    """
    AI 모델 설정 스키마.

    AI 모델 로딩 및 추론 설정을 정의합니다.

    Attributes:
        model_path: 모델 파일 경로
        model_type: 모델 타입 (yolo, mediapipe, onnx, tensorrt)
        device: 실행 디바이스 (cpu, cuda, cuda:0 등)
        precision: 추론 정밀도 (fp32, fp16, int8)
        batch_size: 배치 크기
        confidence_threshold: 신뢰도 임계값 (0.0-1.0)
        nms_threshold: NMS 임계값 (0.0-1.0)
        max_detections: 최대 감지 수
        warmup_iterations: 워밍업 반복 횟수
        cache_enabled: 모델 캐시 활성화
    """

    model_path: str = Field(
        default="models",
        min_length=1,
        description="모델 파일 경로",
    )
    model_type: str = Field(
        default="yolo",
        description="모델 타입",
    )
    device: str = Field(
        default="cuda",
        description="실행 디바이스",
    )
    precision: str = Field(
        default="fp16",
        description="추론 정밀도",
    )
    batch_size: int = Field(
        default=1,
        ge=1,
        le=64,
        description="배치 크기",
    )
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="신뢰도 임계값",
    )
    nms_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="NMS 임계값",
    )
    max_detections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="최대 감지 수",
    )
    warmup_iterations: int = Field(
        default=3,
        ge=0,
        le=100,
        description="워밍업 반복 횟수",
    )
    cache_enabled: bool = Field(
        default=True,
        description="모델 캐시 활성화",
    )

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        """모델 타입 검증."""
        valid_types = {"yolo", "mediapipe", "onnx", "tensorrt", "pytorch", "tflite"}
        if v.lower() not in valid_types:
            raise ValueError(f"유효하지 않은 모델 타입: {v}. 허용: {valid_types}")
        return v.lower()

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """디바이스 검증."""
        valid_patterns = [
            r"^cpu$",
            r"^cuda$",
            r"^cuda:\d+$",
            r"^mps$",
        ]
        if not any(re.match(pattern, v) for pattern in valid_patterns):
            raise ValueError(
                f"유효하지 않은 디바이스: {v}. "
                "cpu, cuda, cuda:0, mps 형식을 사용하세요."
            )
        return v

    @field_validator("precision")
    @classmethod
    def validate_precision(cls, v: str) -> str:
        """정밀도 검증."""
        valid_precisions = {"fp32", "fp16", "int8", "bf16"}
        if v.lower() not in valid_precisions:
            raise ValueError(f"유효하지 않은 정밀도: {v}. 허용: {valid_precisions}")
        return v.lower()


# =============================================================================
# 분석 설정 스키마
# =============================================================================
class AnalysisConfig(BaseConfigModel):
    """
    분석 설정 스키마.

    영상 분석 파이프라인 설정을 정의합니다.

    Attributes:
        target_fps: 분석 대상 FPS
        max_video_duration: 최대 영상 길이 (초)
        min_video_duration: 최소 영상 길이 (초)
        max_video_size_mb: 최대 영상 크기 (MB)
        supported_formats: 지원 영상 형식
        keypoint_confidence_threshold: 키포인트 신뢰도 임계값
        motion_smoothing_window: 모션 스무딩 윈도우 크기
        enable_tracking: 트래킹 활성화
        enable_pose_estimation: 포즈 추정 활성화
        enable_ball_detection: 공 감지 활성화
        enable_court_detection: 코트 감지 활성화
        parallel_workers: 병렬 워커 수
    """

    target_fps: int = Field(
        default=30,
        ge=1,
        le=120,
        description="분석 대상 FPS",
    )
    max_video_duration: int = Field(
        default=7200,
        ge=1,
        le=14400,
        description="최대 영상 길이 (초, 기본 2시간)",
    )
    min_video_duration: int = Field(
        default=1,
        ge=1,
        le=60,
        description="최소 영상 길이 (초)",
    )
    max_video_size_mb: int = Field(
        default=4096,
        ge=1,
        le=20480,
        description="최대 영상 크기 (MB, 기본 4GB)",
    )
    supported_formats: list[str] = Field(
        default_factory=lambda: ["mp4", "avi", "mov", "mkv", "webm"],
        description="지원 영상 형식",
    )
    keypoint_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="키포인트 신뢰도 임계값",
    )
    motion_smoothing_window: int = Field(
        default=5,
        ge=1,
        le=30,
        description="모션 스무딩 윈도우 크기",
    )
    enable_tracking: bool = Field(
        default=True,
        description="트래킹 활성화",
    )
    enable_pose_estimation: bool = Field(
        default=True,
        description="포즈 추정 활성화",
    )
    enable_ball_detection: bool = Field(
        default=True,
        description="공 감지 활성화",
    )
    enable_court_detection: bool = Field(
        default=True,
        description="코트 감지 활성화",
    )
    parallel_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="병렬 워커 수",
    )

    @model_validator(mode="after")
    def validate_duration_range(self) -> "AnalysisConfig":
        """영상 길이 범위 검증."""
        if self.min_video_duration > self.max_video_duration:
            raise ValueError(
                f"최소 영상 길이({self.min_video_duration}초)가 "
                f"최대 영상 길이({self.max_video_duration}초)보다 큽니다."
            )
        return self

    @field_validator("supported_formats")
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        """영상 형식 검증."""
        valid_formats = {"mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", "m4v"}
        normalized = []
        for fmt in v:
            fmt_lower = fmt.lower().lstrip(".")
            if fmt_lower not in valid_formats:
                raise ValueError(f"지원하지 않는 영상 형식: {fmt}")
            normalized.append(fmt_lower)
        return normalized


# =============================================================================
# 로컬 스토리지 설정 스키마
# =============================================================================
class LocalStorageConfig(BaseConfigModel):
    """
    로컬 스토리지 설정 스키마.

    Desktop 환경에서 로컬 파일 스토리지 설정을 정의합니다.

    Attributes:
        data_dir: 데이터 루트 디렉토리
        video_dir: 영상 저장 디렉토리
        cache_dir: 캐시 디렉토리
        export_dir: 분석 결과 내보내기 디렉토리
        temp_dir: 임시 파일 디렉토리
        max_cache_gb: 최대 캐시 크기 (GB)
        max_storage_gb: 최대 스토리지 크기 (GB, 0=무제한)
        auto_cleanup: 자동 정리 활성화
        cleanup_threshold_percent: 정리 시작 임계값 (%)
        video_output_format: 영상 출력 포맷
    """

    data_dir: str = Field(
        default="data",
        min_length=1,
        description="데이터 루트 디렉토리",
    )
    video_dir: str = Field(
        default="data/videos",
        min_length=1,
        description="영상 저장 디렉토리",
    )
    cache_dir: str = Field(
        default="cache",
        min_length=1,
        description="캐시 디렉토리",
    )
    export_dir: str = Field(
        default="exports",
        min_length=1,
        description="분석 결과 내보내기 디렉토리",
    )
    temp_dir: str = Field(
        default="temp",
        min_length=1,
        description="임시 파일 디렉토리",
    )
    max_cache_gb: float = Field(
        default=50.0,
        ge=1.0,
        le=1000.0,
        description="최대 캐시 크기 (GB)",
    )
    max_storage_gb: float = Field(
        default=0.0,
        ge=0.0,
        description="최대 스토리지 크기 (GB, 0=무제한)",
    )
    auto_cleanup: bool = Field(
        default=True,
        description="자동 정리 활성화",
    )
    cleanup_threshold_percent: float = Field(
        default=90.0,
        ge=50.0,
        le=99.0,
        description="정리 시작 임계값 (%)",
    )
    video_output_format: str = Field(
        default="mp4",
        description="영상 출력 포맷",
    )

    @field_validator("video_output_format")
    @classmethod
    def validate_video_format(cls, v: str) -> str:
        """영상 출력 포맷 검증."""
        valid_formats = {"mp4", "avi", "mov", "mkv"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"유효하지 않은 영상 포맷: {v}. 허용: {valid_formats}")
        return v_lower


# =============================================================================
# 로깅 설정 스키마
# =============================================================================
class LoggingConfig(BaseConfigModel):
    """
    로깅 설정 스키마.

    Attributes:
        level: 로그 레벨
        format: 로그 포맷
        output: 출력 방식 (console, file, both)
        file_path: 로그 파일 경로
        max_file_size_mb: 최대 로그 파일 크기
        backup_count: 로그 파일 백업 수
        json_format: JSON 포맷 사용
    """

    level: str = Field(
        default="INFO",
        description="로그 레벨",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="로그 포맷",
    )
    output: str = Field(
        default="both",
        description="출력 방식",
    )
    file_path: str | None = Field(
        default="logs/courtview.log",
        description="로그 파일 경로",
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1024,
        description="최대 로그 파일 크기",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        le=100,
        description="로그 파일 백업 수",
    )
    json_format: bool = Field(
        default=False,
        description="JSON 포맷 사용",
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """로그 레벨 검증."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"유효하지 않은 로그 레벨: {v}. 허용: {valid_levels}")
        return v_upper

    @field_validator("output")
    @classmethod
    def validate_output(cls, v: str) -> str:
        """출력 방식 검증."""
        valid_outputs = {"console", "file", "both"}
        v_lower = v.lower()
        if v_lower not in valid_outputs:
            raise ValueError(f"유효하지 않은 출력 방식: {v}. 허용: {valid_outputs}")
        return v_lower


# =============================================================================
# Desktop 전체 앱 설정 스키마
# =============================================================================
class AppConfig(BaseConfigModel):
    """
    Desktop 앱 전체 설정 스키마.

    Desktop 환경의 모든 설정을 통합합니다.

    Attributes:
        app_name: 애플리케이션 이름
        version: 버전
        environment: 실행 환경 (development, production, testing)
        gpu: GPU 설정 (CUDA, TensorRT)
        camera: 카메라 설정 (멀티 카메라, Genlock)
        storage: 로컬 스토리지 설정
        database: 로컬 데이터베이스 설정 (SQLite)
        model: AI 모델 설정
        analysis: 분석 파이프라인 설정
        logging: 로깅 설정
    """

    app_name: str = Field(
        default="COURTVIEW Desktop",
        description="애플리케이션 이름",
    )
    version: str = Field(
        default="1.0.0",
        description="버전",
    )
    environment: str = Field(
        default="production",
        description="실행 환경",
    )

    # Desktop 전용 설정
    gpu: GPUConfig = Field(
        default_factory=GPUConfig,
        description="GPU 설정",
    )
    camera: CameraConfig = Field(
        default_factory=CameraConfig,
        description="카메라 설정",
    )
    storage: LocalStorageConfig = Field(
        default_factory=LocalStorageConfig,
        description="로컬 스토리지 설정",
    )
    database: LocalDatabaseConfig = Field(
        default_factory=LocalDatabaseConfig,
        description="로컬 데이터베이스 설정",
    )

    # 공통 설정
    model: ModelConfig = Field(
        default_factory=ModelConfig,
        description="AI 모델 설정",
    )
    analysis: AnalysisConfig = Field(
        default_factory=AnalysisConfig,
        description="분석 파이프라인 설정",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="로깅 설정",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """실행 환경 검증."""
        valid_envs = {"development", "production", "testing"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"유효하지 않은 실행 환경: {v}. 허용: {valid_envs}")
        return v_lower


# =============================================================================
# SchemaValidator 클래스
# =============================================================================
class SchemaValidator:
    """
    스키마 검증기.

    Pydantic 모델을 사용하여 설정 데이터를 검증합니다.

    주요 기능:
        - 딕셔너리 데이터를 Pydantic 모델로 검증
        - 상세한 검증 오류 보고
        - 타입 강제 변환 지원
        - 기본값 적용

    Example:
        >>> validator = SchemaValidator()
        >>> result = validator.validate({"device_id": 0}, GPUConfig)
        >>> if result.is_valid:
        ...     print(result.data.cuda_device)
    """

    def __init__(
        self,
        strict_mode: bool = False,
        coerce_types: bool = True,
        apply_defaults: bool = True,
    ) -> None:
        """
        초기화.

        Args:
            strict_mode: 엄격 모드 (알 수 없는 필드 거부)
            coerce_types: 타입 강제 변환
            apply_defaults: 기본값 적용
        """
        self._strict_mode = strict_mode
        self._coerce_types = coerce_types
        self._apply_defaults = apply_defaults

        logger.debug(
            f"SchemaValidator 초기화 "
            f"(strict={strict_mode}, coerce={coerce_types}, defaults={apply_defaults})"
        )

    def validate(
        self,
        data: dict[str, Any],
        schema: Type[T],
        partial: bool = False,
    ) -> ValidationResult[T]:
        """
        데이터 검증.

        Args:
            data: 검증할 데이터 딕셔너리
            schema: Pydantic 스키마 클래스
            partial: 부분 검증 (필수 필드 생략 허용)

        Returns:
            검증 결과
        """
        schema_name = schema.__name__

        try:
            # Pydantic 모델로 검증
            validated_data = schema.model_validate(data)

            logger.debug(f"스키마 검증 성공: {schema_name}")
            return ValidationResult(
                status=ValidationStatus.SUCCESS,
                data=validated_data,
                schema_name=schema_name,
            )

        except ValidationError as e:
            # 검증 오류 변환
            errors = self._convert_pydantic_errors(e)

            logger.warning(f"스키마 검증 실패: {schema_name}, 오류 {len(errors)}개")
            return ValidationResult(
                status=ValidationStatus.FAILED,
                errors=errors,
                schema_name=schema_name,
            )

        except Exception as e:
            # 예상치 못한 오류
            logger.error(f"스키마 검증 중 오류 발생: {schema_name}, {e}")
            return ValidationResult(
                status=ValidationStatus.FAILED,
                errors=[
                    ValidationErrorDetail(
                        field="__root__",
                        message=str(e),
                        error_type="unexpected_error",
                    )
                ],
                schema_name=schema_name,
            )

    def validate_or_raise(
        self,
        data: dict[str, Any],
        schema: Type[T],
    ) -> T:
        """
        데이터 검증 (실패 시 예외 발생).

        Args:
            data: 검증할 데이터 딕셔너리
            schema: Pydantic 스키마 클래스

        Returns:
            검증된 Pydantic 모델 인스턴스

        Raises:
            SchemaValidationException: 검증 실패 시
        """
        result = self.validate(data, schema)

        if not result.is_valid:
            error_dicts = [e.to_dict() for e in result.errors]
            raise SchemaValidationException(
                errors=error_dicts,
                schema_name=result.schema_name,
            )

        return result.data

    def validate_field(
        self,
        value: Any,
        schema: Type[T],
        field_name: str,
    ) -> ValidationResult[Any]:
        """
        단일 필드 검증.

        Args:
            value: 검증할 값
            schema: Pydantic 스키마 클래스
            field_name: 필드 이름

        Returns:
            검증 결과
        """
        return self.validate({field_name: value}, schema)

    def get_schema_info(self, schema: Type[T]) -> dict[str, Any]:
        """
        스키마 정보 조회.

        Args:
            schema: Pydantic 스키마 클래스

        Returns:
            스키마 정보 딕셔너리
        """
        return {
            "name": schema.__name__,
            "fields": {
                name: {
                    "type": str(field.annotation),
                    "required": field.is_required(),
                    "default": field.default if field.default is not None else None,
                    "description": field.description,
                }
                for name, field in schema.model_fields.items()
            },
        }

    def _convert_pydantic_errors(
        self,
        error: ValidationError,
    ) -> list[ValidationErrorDetail]:
        """Pydantic 오류를 내부 오류 형식으로 변환."""
        errors = []

        for err in error.errors():
            field_path = ".".join(str(loc) for loc in err.get("loc", []))
            errors.append(
                ValidationErrorDetail(
                    field=field_path,
                    message=err.get("msg", "검증 실패"),
                    error_type=err.get("type", "unknown"),
                    input_value=err.get("input"),
                )
            )

        return errors


# =============================================================================
# 헬퍼 함수
# =============================================================================
def validate_config(
    data: dict[str, Any],
    schema: Type[T],
    strict: bool = False,
) -> T:
    """
    설정 검증 헬퍼 함수.

    Args:
        data: 검증할 설정 딕셔너리
        schema: Pydantic 스키마 클래스
        strict: 엄격 모드

    Returns:
        검증된 Pydantic 모델 인스턴스

    Raises:
        SchemaValidationException: 검증 실패 시

    Example:
        >>> config = validate_config({"device_id": 0}, GPUConfig)
        >>> print(config.cuda_device)
        "cuda:0"
    """
    validator = SchemaValidator(strict_mode=strict)
    return validator.validate_or_raise(data, schema)


def get_default_config(schema: Type[T]) -> T:
    """
    기본 설정 생성 헬퍼 함수.

    Args:
        schema: Pydantic 스키마 클래스

    Returns:
        기본값으로 생성된 Pydantic 모델 인스턴스

    Example:
        >>> config = get_default_config(GPUConfig)
        >>> print(config.cuda_device)
        "cuda:0"
    """
    return schema()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ValidationStatus",
    # 데이터 클래스
    "ValidationErrorDetail",
    "ValidationResult",
    # 기본 모델
    "BaseConfigModel",
    # Desktop 전용 스키마
    "LocalDatabaseConfig",
    "GPUConfig",
    "CameraConfig",
    "LocalStorageConfig",
    # 공통 스키마
    "ModelConfig",
    "AnalysisConfig",
    "LoggingConfig",
    # 통합 설정
    "AppConfig",
    # 검증 클래스
    "SchemaValidator",
    # 함수
    "validate_config",
    "get_default_config",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
