# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: pipeline_coordinator.py
설명: 파이프라인 실행 조율, 단계 관리 - 엔터프라이즈급 분석 파이프라인 시스템

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 분석 파이프라인 실행 조율
    - 스테이지 기반 단계 관리
    - 비동기 파이프라인 실행
    - 병렬 스테이지 실행 지원
    - 진행 상태 추적 및 콜백
    - 체크포인팅 및 복구
    - 에러 처리 및 복구
    - 파이프라인 메트릭 수집
"""

# ============================================================
# 표준 라이브러리
# ============================================================
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    TypeVar,
)

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode
from shared.constants.status_codes import AnalysisPhase
from shared.exceptions.analysis_exceptions import AnalysisException

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import get_current_timestamp

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.error_tracker import ErrorTracker
    from core_foundation.monitoring.metrics import MetricsCollector


# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# Export 정의
# ============================================================
__all__ = [
    # Enum (4개)
    "PipelineType",              # Enum: 14개 파이프라인 유형 (TRAINING_*, GAME_*, REFEREE_*, REPORT_*)
    "StageType",                 # Enum: 25개 스테이지 유형 (농구 분석 특화)
    "StageStatus",               # Enum: 7개 스테이지 상태 (is_terminal, is_success 프로퍼티)
    "PipelineStatus",            # Enum: 7개 파이프라인 상태 (is_terminal, is_success 프로퍼티)

    # 예외 클래스 (4개)
    "PipelineException",         # Exception: 파이프라인 예외 기본 클래스 (AnalysisException 상속)
    "StageExecutionError",       # Exception: 스테이지 실행 에러 (스테이지명, 원인 포함)
    "PipelineTimeoutError",      # Exception: 파이프라인 타임아웃 에러
    "PipelineConfigError",       # Exception: 파이프라인 설정 에러

    # 상수 (5개, YAML로 오버라이드 가능)
    "DEFAULT_STAGE_TIMEOUT",     # float: 스테이지 타임아웃 (기본 60.0초)
    "DEFAULT_PIPELINE_TIMEOUT",  # float: 파이프라인 타임아웃 (기본 600.0초)
    "DEFAULT_MAX_RETRIES",       # int: 최대 재시도 횟수 (기본 3)
    "DEFAULT_RETRY_DELAY",       # float: 재시도 지연 (기본 1.0초)
    "MAX_CONCURRENT_PIPELINES",  # int: 최대 동시 파이프라인 (기본 4)

    # 타입 별칭 (4개)
    "StageHandler",              # Callable[..., Coroutine[Any, Any, Any]]: 스테이지 핸들러
    "ProgressCallback",          # Callable[[PipelineProgress], None]: 진행 콜백
    "ErrorCallback",             # Callable[[Exception, StageResult], None]: 에러 콜백
    "CheckpointCallback",        # Callable[[str, int, dict[str, Any]], None]: 체크포인트 콜백

    # 데이터 클래스 (6개)
    "StageConfig",               # dataclass: 스테이지 설정 (타입, 핸들러, 타임아웃, 재시도, 의존성)
    "StageResult",               # dataclass: 스테이지 결과 (상태, 데이터, 에러, 소요시간, 재시도 횟수)
    "PipelineConfig",            # dataclass: 파이프라인 설정 (타입, 스테이지, 타임아웃, 체크포인트)
    "PipelineProgress",          # dataclass: 진행 상태 (현재/전체 스테이지, 퍼센트, 예상 시간)
    "CheckpointData",            # dataclass: 체크포인트 데이터 (파이프라인 ID, 스테이지 인덱스, 상태)
    "PipelineContext",           # dataclass: 파이프라인 컨텍스트 (공유 데이터, 메타데이터, 설정)

    # 메인 클래스 (4개)
    "CheckpointManager",         # class: 체크포인트 관리자 (저장/복원, 자동 정리, 파일 기반)
    "PipelineCoordinator",       # class: 파이프라인 코디네이터 (비동기 실행, 병렬 스테이지, DI 대상)
    "PipelineBuilder",           # class: 파이프라인 빌더 (플루언트 API, 체이닝 설정)
    "PipelineTemplates",         # class: 파이프라인 템플릿 (5개 사전 정의 파이프라인)

    # 전역 함수 (3개)
    "get_coordinator",           # Callable: 전역 코디네이터 조회 (싱글톤)
    "create_pipeline",           # Callable: 파이프라인 생성 헬퍼
    "_reset_coordinator",        # Callable: 전역 인스턴스 리셋 (테스트용)
]


# ============================================================
# 타입 변수
# ============================================================
T = TypeVar("T")
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")
StageInputT = TypeVar("StageInputT")
StageOutputT = TypeVar("StageOutputT")

# 스테이지 핸들러 타입
StageHandler = Callable[..., Coroutine[Any, Any, Any]]
ProgressCallback = Callable[["PipelineProgress"], None]
ErrorCallback = Callable[[Exception, "StageResult"], None]
CheckpointCallback = Callable[[str, int, dict[str, Any]], None]


# ============================================================
# 설정 로더 (YAML 기반)
# ============================================================
class _PipelineConfigProvider:
    """
    파이프라인 설정 제공자.

    registry.yaml에서 설정을 로드하여 제공합니다.
    하드코딩된 상수 대신 YAML 설정을 사용합니다.
    """

    _instance: "_PipelineConfigProvider | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """초기화."""
        self._config_loader = ConfigLoader.get_instance()
        self._pipeline_config: dict[str, Any] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> "_PipelineConfigProvider":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 초기화 (테스트용)."""
        with cls._lock:
            cls._instance = None

    def _load_config(self) -> None:
        """YAML 설정 로드."""
        try:
            # configs/core_foundation/registry.yaml에서 pipeline 섹션 로드
            registry_config = self._config_loader.get(
                "core_foundation.registry",
                default={}
            )
            self._pipeline_config = registry_config.get("pipeline", {})
            logger.debug("파이프라인 설정 로드 완료")
        except Exception as e:
            logger.warning(f"파이프라인 설정 로드 실패, 기본값 사용: {e}")
            self._pipeline_config = {}

    def reload(self) -> None:
        """설정 리로드."""
        self._load_config()

    @property
    def stage_default_timeout(self) -> int:
        """스테이지 기본 타임아웃 (초)."""
        stages_config = self._pipeline_config.get("stages", {})
        return stages_config.get("default_timeout", 60)

    @property
    def pipeline_default_timeout(self) -> int:
        """파이프라인 기본 타임아웃 (초)."""
        # 스테이지 타임아웃 * 30 (경기 분석 등 긴 파이프라인 고려)
        return self.stage_default_timeout * 30

    @property
    def max_retries(self) -> int:
        """최대 재시도 횟수."""
        retry_config = self._pipeline_config.get("stages", {}).get("retry", {})
        return retry_config.get("max_attempts", 3)

    @property
    def retry_enabled(self) -> bool:
        """재시도 활성화 여부."""
        retry_config = self._pipeline_config.get("stages", {}).get("retry", {})
        return retry_config.get("enabled", True)

    @property
    def backoff_multiplier(self) -> float:
        """재시도 백오프 배수."""
        retry_config = self._pipeline_config.get("stages", {}).get("retry", {})
        return retry_config.get("backoff_multiplier", 2.0)

    @property
    def parallelism_enabled(self) -> bool:
        """병렬 처리 활성화 여부."""
        parallel_config = self._pipeline_config.get("parallelism", {})
        return parallel_config.get("enabled", True)

    @property
    def max_parallel_stages(self) -> int:
        """최대 병렬 스테이지 수."""
        parallel_config = self._pipeline_config.get("parallelism", {})
        return parallel_config.get("max_parallel", 4)

    @property
    def worker_pool_size(self) -> int:
        """워커 풀 크기."""
        parallel_config = self._pipeline_config.get("parallelism", {})
        return parallel_config.get("worker_pool_size", 8)

    @property
    def checkpointing_enabled(self) -> bool:
        """체크포인팅 활성화 여부."""
        checkpoint_config = self._pipeline_config.get("checkpointing", {})
        return checkpoint_config.get("enabled", True)

    @property
    def checkpoint_storage_path(self) -> str:
        """체크포인트 저장 경로."""
        checkpoint_config = self._pipeline_config.get("checkpointing", {})
        return checkpoint_config.get("storage_path", "checkpoints")

    @property
    def checkpoint_interval(self) -> int:
        """체크포인트 저장 간격 (스테이지 수)."""
        checkpoint_config = self._pipeline_config.get("checkpointing", {})
        return checkpoint_config.get("interval", 2)

    @property
    def recovery_enabled(self) -> bool:
        """복구 활성화 여부."""
        checkpoint_config = self._pipeline_config.get("checkpointing", {})
        return checkpoint_config.get("recovery", True)

    @property
    def progress_update_interval_ms(self) -> int:
        """진행 상태 업데이트 간격 (밀리초)."""
        progress_config = self._pipeline_config.get("progress", {})
        return progress_config.get("update_interval_ms", 100)

    @property
    def metrics_enabled(self) -> bool:
        """메트릭 활성화 여부."""
        metrics_config = self._pipeline_config.get("metrics", {})
        return metrics_config.get("enabled", True)

    @property
    def abort_on_error(self) -> bool:
        """에러 발생 시 파이프라인 중단 여부."""
        error_config = self._pipeline_config.get("stages", {}).get("on_error", {})
        return error_config.get("abort_pipeline", False)

    @property
    def skip_on_error(self) -> bool:
        """에러 발생 시 다음 스테이지로 스킵 여부."""
        error_config = self._pipeline_config.get("stages", {}).get("on_error", {})
        return error_config.get("skip_to_next", True)

    def get_config(self) -> dict[str, Any]:
        """전체 설정 반환."""
        return self._pipeline_config.copy()


# ============================================================
# 설정 접근 함수 (YAML 설정 기반)
# ============================================================
def _get_config_provider() -> _PipelineConfigProvider:
    """설정 제공자 인스턴스 반환."""
    return _PipelineConfigProvider.get_instance()


# YAML 설정에서 로드하는 동적 상수 (하드코딩 제거)
def _get_default_stage_timeout() -> int:
    """스테이지 기본 타임아웃 (YAML 설정)."""
    return _get_config_provider().stage_default_timeout


def _get_default_pipeline_timeout() -> int:
    """파이프라인 기본 타임아웃 (YAML 설정)."""
    return _get_config_provider().pipeline_default_timeout


def _get_default_max_retries() -> int:
    """기본 재시도 횟수 (YAML 설정)."""
    return _get_config_provider().max_retries


def _get_default_retry_delay() -> float:
    """기본 재시도 대기 시간 (YAML 설정)."""
    return 1.0  # 기본값, 백오프 배수와 함께 사용


def _get_max_concurrent_pipelines() -> int:
    """최대 동시 파이프라인 수 (YAML 설정)."""
    return _get_config_provider().worker_pool_size


# 호환성을 위한 상수 (YAML에서 동적 로드)
DEFAULT_STAGE_TIMEOUT: int = 60  # 초기값, 런타임에 YAML에서 재로드
DEFAULT_PIPELINE_TIMEOUT: int = 1800  # 초기값, 런타임에 YAML에서 재로드
DEFAULT_MAX_RETRIES: int = 3  # 초기값, 런타임에 YAML에서 재로드
DEFAULT_RETRY_DELAY: float = 1.0  # 초기값, 런타임에 YAML에서 재로드
MAX_CONCURRENT_PIPELINES: int = 10  # 초기값, 런타임에 YAML에서 재로드


# ============================================================
# Enum 정의
# ============================================================
class PipelineType(str, Enum):
    """
    파이프라인 타입.

    분석 파이프라인의 유형을 정의합니다.
    """

    # 훈련 분석 파이프라인
    TRAINING = "training"  # 훈련 동작 분석
    TRAINING_SHOOTING = "training_shooting"  # 슈팅 훈련 분석
    TRAINING_DRIBBLING = "training_dribbling"  # 드리블 훈련 분석
    TRAINING_COMPARISON = "training_comparison"  # 정답 영상 비교

    # 경기 분석 파이프라인
    GAME = "game"  # 경기 분석
    GAME_FULL = "game_full"  # 전체 경기 분석
    GAME_HIGHLIGHTS = "game_highlights"  # 하이라이트 추출
    GAME_STATISTICS = "game_statistics"  # 통계 분석

    # AI 심판 파이프라인
    REFEREE = "referee"  # AI 심판
    REFEREE_FULL = "referee_full"  # 전체 심판 분석
    REFEREE_VIOLATION = "referee_violation"  # 바이올레이션 감지
    REFEREE_FOUL = "referee_foul"  # 파울 감지

    # 레포트 파이프라인
    REPORT = "report"  # 레포트 생성
    REPORT_WEEKLY = "report_weekly"  # 주간 레포트

    @property
    def category(self) -> str:
        """파이프라인 카테고리."""
        if self.value.startswith("training"):
            return "training"
        elif self.value.startswith("game"):
            return "game"
        elif self.value.startswith("referee"):
            return "referee"
        elif self.value.startswith("report"):
            return "report"
        return "unknown"


class StageType(str, Enum):
    """
    스테이지 타입.

    파이프라인 내 각 단계의 유형을 정의합니다.
    """

    # 전처리 스테이지
    INITIALIZATION = "initialization"  # 초기화
    VIDEO_DOWNLOAD = "video_download"  # 영상 다운로드
    VIDEO_PREPROCESSING = "video_preprocessing"  # 영상 전처리
    FRAME_EXTRACTION = "frame_extraction"  # 프레임 추출

    # 감지 스테이지
    DETECTION = "detection"  # 객체 감지 (공, 사람, 코트)
    PERSON_DETECTION = "person_detection"  # 사람 감지
    BALL_DETECTION = "ball_detection"  # 공 감지
    COURT_DETECTION = "court_detection"  # 코트 감지
    HOOP_DETECTION = "hoop_detection"  # 골대 감지

    # 포즈 추정 스테이지
    POSE_ESTIMATION = "pose_estimation"  # 포즈 추정
    POSE_TRACKING = "pose_tracking"  # 포즈 추적
    POSE_FILTERING = "pose_filtering"  # 포즈 필터링

    # 분석 스테이지
    MOTION_ANALYSIS = "motion_analysis"  # 동작 분석
    BIOMECHANICS_ANALYSIS = "biomechanics_analysis"  # 생체역학 분석
    SHOOTING_ANALYSIS = "shooting_analysis"  # 슈팅 분석
    DRIBBLING_ANALYSIS = "dribbling_analysis"  # 드리블 분석
    GAME_ANALYSIS = "game_analysis"  # 경기 분석
    REFEREE_ANALYSIS = "referee_analysis"  # 심판 분석

    # 피드백 스테이지
    FEEDBACK_GENERATION = "feedback_generation"  # 피드백 생성
    COMPARISON_ANALYSIS = "comparison_analysis"  # 비교 분석
    STATISTICS_CALCULATION = "statistics_calculation"  # 통계 계산

    # 후처리 스테이지
    POSTPROCESSING = "postprocessing"  # 후처리
    RESULT_AGGREGATION = "result_aggregation"  # 결과 집계
    RESULT_UPLOAD = "result_upload"  # 결과 업로드
    CLEANUP = "cleanup"  # 정리

    @property
    def phase(self) -> AnalysisPhase:
        """대응하는 분석 단계."""
        mapping = {
            StageType.INITIALIZATION: AnalysisPhase.INITIALIZED,
            StageType.VIDEO_DOWNLOAD: AnalysisPhase.DOWNLOADING,
            StageType.VIDEO_PREPROCESSING: AnalysisPhase.PREPROCESSING,
            StageType.FRAME_EXTRACTION: AnalysisPhase.PREPROCESSING,
            StageType.DETECTION: AnalysisPhase.DETECTING,
            StageType.PERSON_DETECTION: AnalysisPhase.DETECTING,
            StageType.BALL_DETECTION: AnalysisPhase.DETECTING,
            StageType.COURT_DETECTION: AnalysisPhase.DETECTING,
            StageType.HOOP_DETECTION: AnalysisPhase.DETECTING,
            StageType.POSE_ESTIMATION: AnalysisPhase.POSE_ESTIMATING,
            StageType.POSE_TRACKING: AnalysisPhase.POSE_ESTIMATING,
            StageType.POSE_FILTERING: AnalysisPhase.POSE_ESTIMATING,
            StageType.MOTION_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.BIOMECHANICS_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.SHOOTING_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.DRIBBLING_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.GAME_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.REFEREE_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.FEEDBACK_GENERATION: AnalysisPhase.GENERATING_FEEDBACK,
            StageType.COMPARISON_ANALYSIS: AnalysisPhase.ANALYZING,
            StageType.STATISTICS_CALCULATION: AnalysisPhase.ANALYZING,
            StageType.POSTPROCESSING: AnalysisPhase.POSTPROCESSING,
            StageType.RESULT_AGGREGATION: AnalysisPhase.POSTPROCESSING,
            StageType.RESULT_UPLOAD: AnalysisPhase.UPLOADING,
            StageType.CLEANUP: AnalysisPhase.FINALIZING,
        }
        return mapping.get(self, AnalysisPhase.INITIALIZED)


class StageStatus(str, Enum):
    """
    스테이지 상태.

    개별 스테이지의 실행 상태를 정의합니다.
    """

    PENDING = "pending"  # 대기 중
    RUNNING = "running"  # 실행 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패
    SKIPPED = "skipped"  # 건너뜀
    CANCELLED = "cancelled"  # 취소됨
    RETRYING = "retrying"  # 재시도 중

    @property
    def is_terminal(self) -> bool:
        """종료 상태인지 확인."""
        return self in {
            StageStatus.COMPLETED,
            StageStatus.FAILED,
            StageStatus.SKIPPED,
            StageStatus.CANCELLED,
        }

    @property
    def is_success(self) -> bool:
        """성공 상태인지 확인."""
        return self in {StageStatus.COMPLETED, StageStatus.SKIPPED}


class PipelineStatus(str, Enum):
    """
    파이프라인 상태.

    전체 파이프라인의 실행 상태를 정의합니다.
    """

    CREATED = "created"  # 생성됨
    INITIALIZING = "initializing"  # 초기화 중
    RUNNING = "running"  # 실행 중
    PAUSED = "paused"  # 일시 정지
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패
    CANCELLED = "cancelled"  # 취소됨

    @property
    def is_terminal(self) -> bool:
        """종료 상태인지 확인."""
        return self in {
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.CANCELLED,
        }

    @property
    def is_success(self) -> bool:
        """성공 상태인지 확인."""
        return self == PipelineStatus.COMPLETED


# ============================================================
# 예외 클래스
# ============================================================
class PipelineException(AnalysisException):
    """파이프라인 관련 예외 기본 클래스."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.PIPELINE_ERROR,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, error_code=error_code, **kwargs)
        self.pipeline_id = pipeline_id


class StageExecutionError(PipelineException):
    """스테이지 실행 실패 시 발생."""

    def __init__(
        self,
        stage_type: StageType,
        reason: str,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"스테이지 실행 실패 ({stage_type.value}): {reason}",
            error_code=ErrorCode.STAGE_EXECUTION_FAILED,
            pipeline_id=pipeline_id,
            **kwargs,
        )
        self.stage_type = stage_type
        self.reason = reason


class PipelineTimeoutError(PipelineException):
    """파이프라인 타임아웃 시 발생."""

    def __init__(
        self,
        timeout_seconds: float,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"파이프라인 타임아웃: {timeout_seconds}초 초과",
            error_code=ErrorCode.TIMEOUT_ERROR,
            pipeline_id=pipeline_id,
            **kwargs,
        )
        self.timeout_seconds = timeout_seconds


class PipelineConfigError(PipelineException):
    """파이프라인 설정 오류 시 발생."""

    def __init__(
        self,
        message: str,
        pipeline_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"파이프라인 설정 오류: {message}",
            error_code=ErrorCode.PIPELINE_CONFIG_NOT_FOUND,
            pipeline_id=pipeline_id,
            **kwargs,
        )


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class StageConfig:
    """
    스테이지 설정.

    개별 스테이지의 실행 설정을 정의합니다.
    """

    stage_type: StageType
    handler: StageHandler | None = None
    timeout_seconds: float = DEFAULT_STAGE_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    skip_on_failure: bool = False
    dependencies: list[StageType] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stage_name(self) -> str:
        """스테이지 이름."""
        return self.stage_type.value

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "stage_type": self.stage_type.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "skip_on_failure": self.skip_on_failure,
            "dependencies": [d.value for d in self.dependencies],
            "metadata": self.metadata,
        }


@dataclass
class StageResult:
    """
    스테이지 결과.

    개별 스테이지의 실행 결과를 저장합니다.
    """

    stage_type: StageType
    status: StageStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    output: Any = None
    error: Exception | None = None
    error_message: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if self.completed_at and self.duration_seconds == 0.0:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()

    @property
    def is_success(self) -> bool:
        """성공 여부."""
        return self.status.is_success

    @property
    def is_failed(self) -> bool:
        """실패 여부."""
        return self.status == StageStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "stage_type": self.stage_type.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class PipelineConfig:
    """
    파이프라인 설정.

    전체 파이프라인의 실행 설정을 정의합니다.
    """

    pipeline_type: PipelineType
    stages: list[StageConfig] = field(default_factory=list)
    timeout_seconds: float = DEFAULT_PIPELINE_TIMEOUT
    fail_fast: bool = True  # 첫 실패 시 즉시 중단
    parallel_stages: bool = False  # 병렬 스테이지 실행 허용
    max_parallel: int = 4  # 최대 병렬 스테이지 수
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 검증."""
        if not self.stages:
            logger.warning(f"파이프라인 {self.pipeline_type.value}에 스테이지가 없습니다")

    @property
    def stage_count(self) -> int:
        """스테이지 수."""
        return len(self.stages)

    def get_stage(self, stage_type: StageType) -> StageConfig | None:
        """스테이지 설정 조회."""
        for stage in self.stages:
            if stage.stage_type == stage_type:
                return stage
        return None

    def add_stage(self, stage: StageConfig) -> None:
        """스테이지 추가."""
        self.stages.append(stage)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "pipeline_type": self.pipeline_type.value,
            "stages": [s.to_dict() for s in self.stages],
            "timeout_seconds": self.timeout_seconds,
            "fail_fast": self.fail_fast,
            "parallel_stages": self.parallel_stages,
            "max_parallel": self.max_parallel,
            "metadata": self.metadata,
        }


@dataclass
class PipelineProgress:
    """
    파이프라인 진행 상태.

    파이프라인의 현재 진행 상황을 추적합니다.
    """

    pipeline_id: str
    pipeline_type: PipelineType
    status: PipelineStatus
    current_stage: StageType | None = None
    current_phase: AnalysisPhase = AnalysisPhase.INITIALIZED
    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0
    skipped_stages: int = 0
    progress_percent: float = 0.0
    started_at: datetime | None = None
    estimated_completion: datetime | None = None
    elapsed_seconds: float = 0.0
    stage_results: list[StageResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """진행률 계산."""
        self._update_progress()

    def _update_progress(self) -> None:
        """진행률 업데이트."""
        if self.total_stages > 0:
            self.progress_percent = (
                (self.completed_stages + self.skipped_stages) / self.total_stages
            ) * 100.0

    def update_stage_completed(self, stage_result: StageResult) -> None:
        """스테이지 완료 업데이트."""
        self.stage_results.append(stage_result)
        # SKIPPED는 별도 카운트 (is_success에 포함되므로 먼저 체크)
        if stage_result.status == StageStatus.SKIPPED:
            self.skipped_stages += 1
        elif stage_result.status == StageStatus.COMPLETED:
            self.completed_stages += 1
        else:
            self.failed_stages += 1
        self._update_progress()

    def set_current_stage(self, stage_type: StageType) -> None:
        """현재 스테이지 설정."""
        self.current_stage = stage_type
        self.current_phase = stage_type.phase

    @property
    def is_completed(self) -> bool:
        """완료 여부."""
        return self.status.is_terminal

    @property
    def is_success(self) -> bool:
        """성공 여부."""
        return self.status.is_success

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_type": self.pipeline_type.value,
            "status": self.status.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "current_phase": self.current_phase.value,
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "skipped_stages": self.skipped_stages,
            "progress_percent": round(self.progress_percent, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stage_results": [r.to_dict() for r in self.stage_results],
        }


@dataclass
class CheckpointData:
    """
    체크포인트 데이터.

    파이프라인 실행 상태를 저장하여 복구에 사용합니다.
    """

    pipeline_id: str
    pipeline_type: PipelineType
    completed_stages: list[StageType]
    current_stage_index: int
    stage_outputs: dict[str, Any]  # StageType.value -> output (직렬화용)
    metadata: dict[str, Any]
    created_at: datetime
    checksum: str = ""

    def __post_init__(self) -> None:
        """체크섬 생성."""
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """체크섬 계산."""
        data_str = f"{self.pipeline_id}:{self.current_stage_index}:{len(self.completed_stages)}"
        return hashlib.md5(data_str.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_type": self.pipeline_type.value,
            "completed_stages": [s.value for s in self.completed_stages],
            "current_stage_index": self.current_stage_index,
            "stage_outputs": self.stage_outputs,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointData":
        """딕셔너리에서 생성."""
        return cls(
            pipeline_id=data["pipeline_id"],
            pipeline_type=PipelineType(data["pipeline_type"]),
            completed_stages=[StageType(s) for s in data["completed_stages"]],
            current_stage_index=data["current_stage_index"],
            stage_outputs=data["stage_outputs"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            checksum=data.get("checksum", ""),
        )


@dataclass
class PipelineContext:
    """
    파이프라인 컨텍스트.

    파이프라인 실행 중 공유되는 컨텍스트 데이터입니다.
    """

    pipeline_id: str
    pipeline_type: PipelineType
    input_data: Any = None
    stage_outputs: dict[StageType, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    cancellation_token: asyncio.Event | None = None
    # 체크포인트 관련
    checkpoint_enabled: bool = True
    last_checkpoint_index: int = -1
    recovered_from_checkpoint: bool = False

    def get_stage_output(self, stage_type: StageType) -> Any | None:
        """이전 스테이지 출력 조회."""
        return self.stage_outputs.get(stage_type)

    def set_stage_output(self, stage_type: StageType, output: Any) -> None:
        """스테이지 출력 저장."""
        self.stage_outputs[stage_type] = output

    @property
    def is_cancelled(self) -> bool:
        """취소 여부."""
        return self.cancellation_token is not None and self.cancellation_token.is_set()

    def create_checkpoint(self, current_index: int) -> CheckpointData:
        """현재 상태에서 체크포인트 생성."""
        completed = list(self.stage_outputs.keys())
        # 직렬화 가능한 출력만 저장 (복잡한 객체는 제외)
        serializable_outputs: dict[str, Any] = {}
        for stage_type, output in self.stage_outputs.items():
            try:
                # 직렬화 가능 여부 확인 (default=str 제거하여 정확한 검사)
                json.dumps(output)
                serializable_outputs[stage_type.value] = output
            except (TypeError, ValueError):
                # 직렬화 불가능한 경우 타입 정보만 저장
                serializable_outputs[stage_type.value] = {
                    "_type": type(output).__name__,
                    "_serializable": False,
                }

        return CheckpointData(
            pipeline_id=self.pipeline_id,
            pipeline_type=self.pipeline_type,
            completed_stages=completed,
            current_stage_index=current_index,
            stage_outputs=serializable_outputs,
            metadata=self.metadata.copy(),
            created_at=datetime.now(timezone.utc),
        )

    def restore_from_checkpoint(self, checkpoint: CheckpointData) -> None:
        """체크포인트에서 상태 복원."""
        self.recovered_from_checkpoint = True
        self.last_checkpoint_index = checkpoint.current_stage_index
        self.metadata.update(checkpoint.metadata)
        # 직렬화 가능했던 출력만 복원
        for stage_value, output in checkpoint.stage_outputs.items():
            if isinstance(output, dict) and output.get("_serializable") is False:
                continue
            try:
                stage_type = StageType(stage_value)
                self.stage_outputs[stage_type] = output
            except ValueError:
                pass


# ============================================================
# 체크포인트 관리자
# ============================================================
class CheckpointManager:
    """
    체크포인트 관리자.

    파이프라인 체크포인트 저장 및 복구를 관리합니다.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """
        초기화.

        Args:
            storage_path: 체크포인트 저장 경로
        """
        config = _get_config_provider()
        self._storage_path = Path(storage_path or config.checkpoint_storage_path)
        self._enabled = config.checkpointing_enabled
        self._interval = config.checkpoint_interval
        self._lock = threading.Lock()

        # 저장 디렉토리 생성
        if self._enabled:
            self._storage_path.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        """체크포인팅 활성화 여부."""
        return self._enabled

    @property
    def interval(self) -> int:
        """체크포인트 저장 간격."""
        return self._interval

    def should_checkpoint(self, stage_index: int, last_checkpoint: int) -> bool:
        """체크포인트 저장 여부 판단."""
        if not self._enabled:
            return False
        return (stage_index - last_checkpoint) >= self._interval

    def save(self, checkpoint: CheckpointData) -> bool:
        """
        체크포인트 저장.

        Args:
            checkpoint: 체크포인트 데이터

        Returns:
            저장 성공 여부
        """
        if not self._enabled:
            return False

        try:
            filepath = self._storage_path / f"{checkpoint.pipeline_id}.json"
            with self._lock:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"체크포인트 저장: {checkpoint.pipeline_id}")
            return True
        except Exception as e:
            logger.warning(f"체크포인트 저장 실패: {e}")
            return False

    def load(self, pipeline_id: str) -> CheckpointData | None:
        """
        체크포인트 로드.

        Args:
            pipeline_id: 파이프라인 ID

        Returns:
            체크포인트 데이터 또는 None
        """
        if not self._enabled:
            return None

        try:
            filepath = self._storage_path / f"{pipeline_id}.json"
            if not filepath.exists():
                return None

            with self._lock:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

            checkpoint = CheckpointData.from_dict(data)
            # 체크섬 검증
            expected_checksum = checkpoint._compute_checksum()
            if checkpoint.checksum != expected_checksum:
                logger.warning(f"체크포인트 체크섬 불일치: {pipeline_id}")
                return None

            logger.debug(f"체크포인트 로드: {pipeline_id}")
            return checkpoint
        except Exception as e:
            logger.warning(f"체크포인트 로드 실패: {e}")
            return None

    def delete(self, pipeline_id: str) -> bool:
        """
        체크포인트 삭제.

        Args:
            pipeline_id: 파이프라인 ID

        Returns:
            삭제 성공 여부
        """
        try:
            filepath = self._storage_path / f"{pipeline_id}.json"
            if filepath.exists():
                with self._lock:
                    os.remove(filepath)
                logger.debug(f"체크포인트 삭제: {pipeline_id}")
            return True
        except Exception as e:
            logger.warning(f"체크포인트 삭제 실패: {e}")
            return False

    def list_checkpoints(self) -> list[str]:
        """저장된 체크포인트 목록."""
        if not self._storage_path.exists():
            return []
        return [f.stem for f in self._storage_path.glob("*.json")]

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """
        오래된 체크포인트 정리.

        Args:
            max_age_hours: 최대 보관 시간

        Returns:
            삭제된 체크포인트 수
        """
        deleted = 0
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)

        for filepath in self._storage_path.glob("*.json"):
            try:
                if filepath.stat().st_mtime < cutoff:
                    os.remove(filepath)
                    deleted += 1
            except Exception:
                pass

        return deleted


# ============================================================
# 파이프라인 코디네이터
# ============================================================
class PipelineCoordinator:
    """
    파이프라인 코디네이터.

    분석 파이프라인의 실행을 조율하고 관리합니다.
    YAML 설정 기반으로 동작하며, 병렬 스테이지 실행과 체크포인팅을 지원합니다.

    Example:
        >>> coordinator = PipelineCoordinator(config_loader)
        >>> config = PipelineConfig(
        ...     pipeline_type=PipelineType.TRAINING_SHOOTING,
        ...     stages=[
        ...         StageConfig(StageType.INITIALIZATION),
        ...         StageConfig(StageType.VIDEO_DOWNLOAD),
        ...         StageConfig(StageType.DETECTION),
        ...         StageConfig(StageType.POSE_ESTIMATION),
        ...         StageConfig(StageType.SHOOTING_ANALYSIS),
        ...         StageConfig(StageType.FEEDBACK_GENERATION),
        ...     ]
        ... )
        >>> result = await coordinator.execute(config, input_data)
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        metrics_collector: "MetricsCollector | None" = None,  # DI 주입
        error_tracker: "ErrorTracker | None" = None,  # DI 주입
        checkpoint_manager: CheckpointManager | None = None,  # DI 주입
    ) -> None:
        """
        초기화.

        Args:
            config_loader: 설정 로더
            metrics_collector: 메트릭 수집기 (DI 주입)
            error_tracker: 에러 추적기 (DI 주입)
            checkpoint_manager: 체크포인트 관리자 (DI 주입)
        """
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._config_provider = _get_config_provider()
        self._metrics_collector = metrics_collector
        self._error_tracker = error_tracker
        self._checkpoint_manager = checkpoint_manager or CheckpointManager()

        # 실행 상태
        self._active_pipelines: dict[str, PipelineProgress] = {}
        self._pipeline_contexts: dict[str, PipelineContext] = {}
        self._stage_handlers: dict[StageType, StageHandler] = {}
        self._default_handlers: dict[StageType, StageHandler] = {}

        # 동시성 제어 (YAML 설정에서 로드)
        self._lock = threading.RLock()
        max_concurrent = self._config_provider.worker_pool_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._parallel_semaphore = asyncio.Semaphore(
            self._config_provider.max_parallel_stages
        )

        # 콜백
        self._progress_callbacks: list[ProgressCallback] = []
        self._error_callbacks: list[ErrorCallback] = []
        self._checkpoint_callbacks: list[CheckpointCallback] = []

        # 초기화
        self._setup_default_handlers()

        logger.info(
            f"PipelineCoordinator 초기화 완료 "
            f"(max_concurrent={max_concurrent}, "
            f"parallelism={self._config_provider.parallelism_enabled}, "
            f"checkpointing={self._config_provider.checkpointing_enabled})"
        )

    def _setup_default_handlers(self) -> None:
        """기본 핸들러 설정."""
        # 기본 핸들러는 빈 구현 (실제 구현은 각 분석 모듈에서 등록)
        pass

    def reload_config(self) -> None:
        """설정 리로드."""
        self._config_provider.reload()
        logger.info("파이프라인 설정 리로드 완료")

    # ============================================================
    # 핸들러 등록
    # ============================================================
    def register_handler(
        self,
        stage_type: StageType,
        handler: StageHandler,
    ) -> None:
        """
        스테이지 핸들러 등록.

        Args:
            stage_type: 스테이지 타입
            handler: 핸들러 함수 (async)
        """
        with self._lock:
            self._stage_handlers[stage_type] = handler
            logger.debug(f"스테이지 핸들러 등록: {stage_type.value}")

    def unregister_handler(self, stage_type: StageType) -> None:
        """
        스테이지 핸들러 등록 해제.

        Args:
            stage_type: 스테이지 타입
        """
        with self._lock:
            if stage_type in self._stage_handlers:
                del self._stage_handlers[stage_type]
                logger.debug(f"스테이지 핸들러 해제: {stage_type.value}")

    def get_handler(self, stage_type: StageType) -> StageHandler | None:
        """
        스테이지 핸들러 조회.

        Args:
            stage_type: 스테이지 타입

        Returns:
            핸들러 함수 또는 None
        """
        return self._stage_handlers.get(
            stage_type,
            self._default_handlers.get(stage_type),
        )

    # ============================================================
    # 콜백 등록
    # ============================================================
    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """진행 상태 콜백 추가."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: ProgressCallback) -> None:
        """진행 상태 콜백 제거."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def add_error_callback(self, callback: ErrorCallback) -> None:
        """에러 콜백 추가."""
        self._error_callbacks.append(callback)

    def remove_error_callback(self, callback: ErrorCallback) -> None:
        """에러 콜백 제거."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    def _notify_progress(self, progress: PipelineProgress) -> None:
        """진행 상태 알림."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"진행 콜백 오류: {e}")

    def _notify_error(self, error: Exception, stage_result: StageResult) -> None:
        """에러 알림."""
        for callback in self._error_callbacks:
            try:
                callback(error, stage_result)
            except Exception as e:
                logger.warning(f"에러 콜백 오류: {e}")

    # ============================================================
    # 체크포인트 콜백
    # ============================================================
    def add_checkpoint_callback(self, callback: CheckpointCallback) -> None:
        """체크포인트 콜백 추가."""
        self._checkpoint_callbacks.append(callback)

    def remove_checkpoint_callback(self, callback: CheckpointCallback) -> None:
        """체크포인트 콜백 제거."""
        if callback in self._checkpoint_callbacks:
            self._checkpoint_callbacks.remove(callback)

    def _notify_checkpoint(
        self,
        pipeline_id: str,
        stage_index: int,
        checkpoint_data: dict[str, Any],
    ) -> None:
        """체크포인트 알림."""
        for callback in self._checkpoint_callbacks:
            try:
                callback(pipeline_id, stage_index, checkpoint_data)
            except Exception as e:
                logger.warning(f"체크포인트 콜백 오류: {e}")

    # ============================================================
    # 파이프라인 실행
    # ============================================================
    async def execute(
        self,
        config: PipelineConfig,
        input_data: Any = None,
        pipeline_id: str | None = None,
        resume_from_checkpoint: bool = False,
    ) -> PipelineProgress:
        """
        파이프라인 실행.

        Args:
            config: 파이프라인 설정
            input_data: 입력 데이터
            pipeline_id: 파이프라인 ID (선택)
            resume_from_checkpoint: 체크포인트에서 재개 여부

        Returns:
            파이프라인 진행 결과

        Raises:
            PipelineException: 파이프라인 실행 실패 시
        """
        async with self._semaphore:
            # 파이프라인 ID 생성
            if pipeline_id is None:
                pipeline_id = str(uuid.uuid4())

            # 체크포인트 복구 시도
            start_index = 0
            checkpoint: CheckpointData | None = None
            if resume_from_checkpoint and self._checkpoint_manager.enabled:
                checkpoint = self._checkpoint_manager.load(pipeline_id)
                if checkpoint:
                    start_index = checkpoint.current_stage_index
                    logger.info(
                        f"체크포인트에서 복구: {pipeline_id}, "
                        f"스테이지 {start_index}부터 재개"
                    )

            # 진행 상태 초기화
            progress = PipelineProgress(
                pipeline_id=pipeline_id,
                pipeline_type=config.pipeline_type,
                status=PipelineStatus.INITIALIZING,
                total_stages=config.stage_count,
                started_at=datetime.now(timezone.utc),
            )

            # 컨텍스트 생성
            context = PipelineContext(
                pipeline_id=pipeline_id,
                pipeline_type=config.pipeline_type,
                input_data=input_data,
                cancellation_token=asyncio.Event(),
                checkpoint_enabled=self._checkpoint_manager.enabled,
            )

            # 체크포인트에서 복원
            if checkpoint:
                context.restore_from_checkpoint(checkpoint)
                progress.completed_stages = len(checkpoint.completed_stages)

            # 활성 파이프라인 등록
            with self._lock:
                self._active_pipelines[pipeline_id] = progress
                self._pipeline_contexts[pipeline_id] = context

            try:
                # 메트릭 기록
                if self._metrics_collector and self._config_provider.metrics_enabled:
                    try:
                        self._metrics_collector.increment(
                            "pipeline.started",
                            tags={
                                "type": config.pipeline_type.value,
                                "resumed": str(checkpoint is not None).lower(),
                            },
                        )
                    except Exception:
                        pass

                # 파이프라인 실행
                progress.status = PipelineStatus.RUNNING
                self._notify_progress(progress)

                # YAML 설정에서 타임아웃 로드
                timeout = config.timeout_seconds
                if timeout == DEFAULT_PIPELINE_TIMEOUT:
                    timeout = self._config_provider.pipeline_default_timeout

                # 타임아웃 적용 실행
                try:
                    await asyncio.wait_for(
                        self._execute_stages(
                            config, context, progress, start_index
                        ),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    # 타임아웃 시 체크포인트 저장
                    if self._checkpoint_manager.enabled:
                        cp = context.create_checkpoint(progress.completed_stages)
                        self._checkpoint_manager.save(cp)
                    raise PipelineTimeoutError(
                        timeout,
                        pipeline_id=pipeline_id,
                    )

                # 완료 상태 설정
                if progress.failed_stages > 0 and config.fail_fast:
                    progress.status = PipelineStatus.FAILED
                else:
                    progress.status = PipelineStatus.COMPLETED
                    # 성공 시 체크포인트 삭제
                    if self._checkpoint_manager.enabled:
                        self._checkpoint_manager.delete(pipeline_id)

            except PipelineException:
                progress.status = PipelineStatus.FAILED
                # 실패 시 체크포인트 저장
                if self._checkpoint_manager.enabled:
                    cp = context.create_checkpoint(progress.completed_stages)
                    self._checkpoint_manager.save(cp)
                raise

            except Exception as e:
                progress.status = PipelineStatus.FAILED
                logger.exception(f"파이프라인 실행 오류: {e}")
                # 실패 시 체크포인트 저장
                if self._checkpoint_manager.enabled:
                    cp = context.create_checkpoint(progress.completed_stages)
                    self._checkpoint_manager.save(cp)
                raise PipelineException(
                    f"파이프라인 실행 실패: {e}",
                    pipeline_id=pipeline_id,
                )

            finally:
                # 경과 시간 계산
                if progress.started_at:
                    elapsed = datetime.now(timezone.utc) - progress.started_at
                    progress.elapsed_seconds = elapsed.total_seconds()

                # 활성 파이프라인 제거
                with self._lock:
                    if pipeline_id in self._active_pipelines:
                        del self._active_pipelines[pipeline_id]
                    if pipeline_id in self._pipeline_contexts:
                        del self._pipeline_contexts[pipeline_id]

                # 메트릭 기록
                if self._metrics_collector and self._config_provider.metrics_enabled:
                    try:
                        self._metrics_collector.increment(
                            "pipeline.completed",
                            tags={
                                "type": config.pipeline_type.value,
                                "status": progress.status.value,
                            },
                        )
                        self._metrics_collector.histogram(
                            "pipeline.duration_seconds",
                            progress.elapsed_seconds,
                            tags={"type": config.pipeline_type.value},
                        )
                    except Exception:
                        pass

                # 최종 알림
                self._notify_progress(progress)

            return progress

    async def _execute_stages(
        self,
        config: PipelineConfig,
        context: PipelineContext,
        progress: PipelineProgress,
        start_index: int = 0,
    ) -> None:
        """
        스테이지들 실행.

        Args:
            config: 파이프라인 설정
            context: 파이프라인 컨텍스트
            progress: 진행 상태
            start_index: 시작 스테이지 인덱스 (체크포인트 복구용)
        """
        stages = config.stages[start_index:]

        # 병렬 실행이 활성화된 경우
        if config.parallel_stages and self._config_provider.parallelism_enabled:
            await self._execute_stages_parallel(
                config, context, progress, stages, start_index
            )
        else:
            await self._execute_stages_sequential(
                config, context, progress, stages, start_index
            )

    async def _execute_stages_sequential(
        self,
        config: PipelineConfig,
        context: PipelineContext,
        progress: PipelineProgress,
        stages: list[StageConfig],
        start_index: int = 0,
    ) -> None:
        """
        스테이지 순차 실행.

        Args:
            config: 파이프라인 설정
            context: 파이프라인 컨텍스트
            progress: 진행 상태
            stages: 실행할 스테이지 목록
            start_index: 전체 파이프라인에서의 시작 인덱스
        """
        for i, stage_config in enumerate(stages):
            current_index = start_index + i

            # 취소 확인
            if context.is_cancelled:
                progress.status = PipelineStatus.CANCELLED
                break

            # 실패 시 중단 확인 (YAML 설정 반영)
            if self._config_provider.abort_on_error and progress.failed_stages > 0:
                break
            if config.fail_fast and progress.failed_stages > 0:
                break

            # 스테이지 실행
            progress.set_current_stage(stage_config.stage_type)
            self._notify_progress(progress)

            result = await self._execute_stage(stage_config, context)
            progress.update_stage_completed(result)

            # 에러 알림
            if result.is_failed:
                if result.error:
                    self._notify_error(result.error, result)

            # 체크포인트 저장
            if self._checkpoint_manager.should_checkpoint(
                current_index, context.last_checkpoint_index
            ):
                checkpoint = context.create_checkpoint(current_index)
                if self._checkpoint_manager.save(checkpoint):
                    context.last_checkpoint_index = current_index
                    self._notify_checkpoint(
                        context.pipeline_id,
                        current_index,
                        checkpoint.to_dict(),
                    )

    async def _execute_stages_parallel(
        self,
        config: PipelineConfig,
        context: PipelineContext,
        progress: PipelineProgress,
        stages: list[StageConfig],
        start_index: int = 0,
    ) -> None:
        """
        스테이지 병렬 실행.

        의존성이 없는 스테이지들을 병렬로 실행합니다.
        의존성이 있는 스테이지는 의존 스테이지 완료 후 실행됩니다.

        Args:
            config: 파이프라인 설정
            context: 파이프라인 컨텍스트
            progress: 진행 상태
            stages: 실행할 스테이지 목록
            start_index: 전체 파이프라인에서의 시작 인덱스
        """
        max_parallel = min(config.max_parallel, self._config_provider.max_parallel_stages)

        # 스테이지를 의존성 그룹으로 분류
        groups = self._group_stages_by_dependencies(stages)

        current_index = start_index
        for group in groups:
            # 취소 확인
            if context.is_cancelled:
                progress.status = PipelineStatus.CANCELLED
                break

            # 실패 시 중단 확인
            if self._config_provider.abort_on_error and progress.failed_stages > 0:
                break
            if config.fail_fast and progress.failed_stages > 0:
                break

            # 그룹 내 스테이지들을 병렬 실행
            if len(group) == 1:
                # 단일 스테이지는 순차 실행
                stage_config = group[0]
                progress.set_current_stage(stage_config.stage_type)
                self._notify_progress(progress)

                result = await self._execute_stage(stage_config, context)
                progress.update_stage_completed(result)

                if result.is_failed and result.error:
                    self._notify_error(result.error, result)
            else:
                # 여러 스테이지 병렬 실행
                results = await self._execute_parallel_batch(
                    group, context, max_parallel
                )

                for result in results:
                    progress.update_stage_completed(result)
                    if result.is_failed and result.error:
                        self._notify_error(result.error, result)

            # 체크포인트 저장
            current_index += len(group)
            if self._checkpoint_manager.should_checkpoint(
                current_index, context.last_checkpoint_index
            ):
                checkpoint = context.create_checkpoint(current_index)
                if self._checkpoint_manager.save(checkpoint):
                    context.last_checkpoint_index = current_index
                    self._notify_checkpoint(
                        context.pipeline_id,
                        current_index,
                        checkpoint.to_dict(),
                    )

    def _group_stages_by_dependencies(
        self,
        stages: list[StageConfig],
    ) -> list[list[StageConfig]]:
        """
        스테이지를 의존성 기반으로 그룹화.

        동일 그룹 내 스테이지들은 병렬 실행 가능합니다.

        Args:
            stages: 스테이지 목록

        Returns:
            그룹화된 스테이지 목록
        """
        groups: list[list[StageConfig]] = []
        completed_types: set[StageType] = set()
        remaining = list(stages)

        while remaining:
            # 의존성이 충족된 스테이지 찾기
            ready = []
            not_ready = []

            for stage in remaining:
                deps_met = all(
                    dep in completed_types for dep in stage.dependencies
                )
                if deps_met or not stage.dependencies:
                    ready.append(stage)
                else:
                    not_ready.append(stage)

            if not ready:
                # 모든 스테이지가 의존성 미충족 (순환 의존성 또는 누락)
                # 나머지를 순차 실행으로 처리
                for stage in not_ready:
                    groups.append([stage])
                break

            groups.append(ready)
            for stage in ready:
                completed_types.add(stage.stage_type)
            remaining = not_ready

        return groups

    async def _execute_parallel_batch(
        self,
        stages: list[StageConfig],
        context: PipelineContext,
        max_parallel: int,
    ) -> list[StageResult]:
        """
        스테이지 배치 병렬 실행.

        Args:
            stages: 병렬 실행할 스테이지 목록
            context: 파이프라인 컨텍스트
            max_parallel: 최대 병렬 수

        Returns:
            스테이지 결과 목록
        """
        semaphore = asyncio.Semaphore(max_parallel)

        async def run_with_semaphore(stage: StageConfig) -> StageResult:
            async with semaphore:
                return await self._execute_stage(stage, context)

        tasks = [run_with_semaphore(stage) for stage in stages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외를 StageResult로 변환
        processed_results: list[StageResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                stage = stages[i]
                processed_results.append(
                    StageResult(
                        stage_type=stage.stage_type,
                        status=StageStatus.FAILED,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        error=result,
                        error_message=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_stage(
        self,
        stage_config: StageConfig,
        context: PipelineContext,
    ) -> StageResult:
        """
        단일 스테이지 실행.

        YAML 설정 기반 타임아웃, 재시도, 지수 백오프를 적용합니다.

        Args:
            stage_config: 스테이지 설정
            context: 파이프라인 컨텍스트

        Returns:
            스테이지 결과
        """
        stage_type = stage_config.stage_type
        started_at = datetime.now(timezone.utc)

        # 핸들러 확인
        handler = stage_config.handler or self.get_handler(stage_type)
        if handler is None:
            # 핸들러 없으면 건너뜀
            logger.warning(f"스테이지 핸들러 없음, 건너뜀: {stage_type.value}")
            return StageResult(
                stage_type=stage_type,
                status=StageStatus.SKIPPED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        # YAML 설정 적용
        timeout = stage_config.timeout_seconds
        if timeout == DEFAULT_STAGE_TIMEOUT:
            timeout = self._config_provider.stage_default_timeout

        max_retries = stage_config.max_retries
        if max_retries == DEFAULT_MAX_RETRIES:
            max_retries = self._config_provider.max_retries

        retry_enabled = self._config_provider.retry_enabled
        backoff_multiplier = self._config_provider.backoff_multiplier
        base_delay = stage_config.retry_delay

        # 재시도 비활성화 시 1회만 실행
        if not retry_enabled:
            max_retries = 0

        # 재시도 로직
        last_error: Exception | None = None
        retry_count = 0

        for attempt in range(max_retries + 1):
            try:
                # 타임아웃 적용 실행
                output = await asyncio.wait_for(
                    handler(context),
                    timeout=timeout,
                )

                # 성공
                completed_at = datetime.now(timezone.utc)
                context.set_stage_output(stage_type, output)

                # 메트릭 기록
                if self._metrics_collector and self._config_provider.metrics_enabled:
                    try:
                        duration = (completed_at - started_at).total_seconds()
                        self._metrics_collector.histogram(
                            "stage.duration_seconds",
                            duration,
                            tags={
                                "stage": stage_type.value,
                                "status": "success",
                            },
                        )
                    except Exception:
                        pass

                return StageResult(
                    stage_type=stage_type,
                    status=StageStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=completed_at,
                    output=output,
                    retry_count=retry_count,
                )

            except asyncio.TimeoutError as e:
                last_error = e
                retry_count = attempt
                logger.warning(
                    f"스테이지 타임아웃 ({stage_type.value}): "
                    f"시도 {attempt + 1}/{max_retries + 1}, "
                    f"타임아웃={timeout}초"
                )

            except asyncio.CancelledError:
                # 취소됨
                return StageResult(
                    stage_type=stage_type,
                    status=StageStatus.CANCELLED,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

            except Exception as e:
                last_error = e
                retry_count = attempt
                logger.warning(
                    f"스테이지 실행 오류 ({stage_type.value}): {e}, "
                    f"시도 {attempt + 1}/{max_retries + 1}"
                )

                # 에러 추적
                if self._error_tracker:
                    try:
                        self._error_tracker.track(
                            e,
                            context={
                                "stage": stage_type.value,
                                "attempt": attempt + 1,
                                "pipeline_id": context.pipeline_id,
                            },
                        )
                    except Exception:
                        pass

            # 지수 백오프 재시도 대기
            if attempt < max_retries:
                delay = base_delay * (backoff_multiplier ** attempt)
                logger.debug(
                    f"스테이지 재시도 대기: {delay:.2f}초 "
                    f"(시도 {attempt + 1} -> {attempt + 2})"
                )
                await asyncio.sleep(delay)

        # 모든 재시도 실패
        completed_at = datetime.now(timezone.utc)

        # 메트릭 기록
        if self._metrics_collector and self._config_provider.metrics_enabled:
            try:
                duration = (completed_at - started_at).total_seconds()
                self._metrics_collector.histogram(
                    "stage.duration_seconds",
                    duration,
                    tags={
                        "stage": stage_type.value,
                        "status": "failed",
                    },
                )
                self._metrics_collector.increment(
                    "stage.retries_exhausted",
                    tags={"stage": stage_type.value},
                )
            except Exception:
                pass

        # YAML skip_on_error 설정 또는 stage_config 설정 확인
        should_skip = stage_config.skip_on_failure or self._config_provider.skip_on_error

        if should_skip:
            return StageResult(
                stage_type=stage_type,
                status=StageStatus.SKIPPED,
                started_at=started_at,
                completed_at=completed_at,
                error=last_error,
                error_message=str(last_error) if last_error else None,
                retry_count=retry_count,
            )

        return StageResult(
            stage_type=stage_type,
            status=StageStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            error=last_error,
            error_message=str(last_error) if last_error else None,
            retry_count=retry_count,
        )

    # ============================================================
    # 파이프라인 제어
    # ============================================================
    def cancel(self, pipeline_id: str) -> bool:
        """
        파이프라인 취소.

        cancellation_token을 set하여 실행 중인 스테이지 루프가
        context.is_cancelled를 통해 취소를 감지할 수 있도록 합니다.

        Args:
            pipeline_id: 파이프라인 ID

        Returns:
            취소 성공 여부
        """
        with self._lock:
            progress = self._active_pipelines.get(pipeline_id)
            if progress is None:
                return False

            progress.status = PipelineStatus.CANCELLED

            # cancellation_token set → 실행 중 스테이지가 취소 감지
            context = self._pipeline_contexts.get(pipeline_id)
            if context and context.cancellation_token is not None:
                context.cancellation_token.set()

            return True

    def get_progress(self, pipeline_id: str) -> PipelineProgress | None:
        """
        파이프라인 진행 상태 조회.

        Args:
            pipeline_id: 파이프라인 ID

        Returns:
            진행 상태 또는 None
        """
        with self._lock:
            return self._active_pipelines.get(pipeline_id)

    def get_active_pipelines(self) -> list[PipelineProgress]:
        """
        활성 파이프라인 목록 조회.

        Returns:
            활성 파이프라인 진행 상태 목록
        """
        with self._lock:
            return list(self._active_pipelines.values())

    # ============================================================
    # 상태 조회
    # ============================================================
    @property
    def active_count(self) -> int:
        """활성 파이프라인 수."""
        with self._lock:
            return len(self._active_pipelines)

    @property
    def registered_handlers(self) -> list[StageType]:
        """등록된 핸들러 스테이지 목록."""
        with self._lock:
            return list(self._stage_handlers.keys())

    def get_status(self) -> dict[str, Any]:
        """
        코디네이터 상태 조회.

        Returns:
            상태 정보 딕셔너리
        """
        with self._lock:
            return {
                "active_pipelines": len(self._active_pipelines),
                "registered_handlers": len(self._stage_handlers),
                "handler_types": [t.value for t in self._stage_handlers.keys()],
                # YAML 설정에서 로드된 값 사용
                "config": {
                    "max_concurrent": self._config_provider.worker_pool_size,
                    "parallelism_enabled": self._config_provider.parallelism_enabled,
                    "max_parallel_stages": self._config_provider.max_parallel_stages,
                    "checkpointing_enabled": self._config_provider.checkpointing_enabled,
                    "stage_default_timeout": self._config_provider.stage_default_timeout,
                    "max_retries": self._config_provider.max_retries,
                    "backoff_multiplier": self._config_provider.backoff_multiplier,
                },
                "checkpoints": {
                    "enabled": self._checkpoint_manager.enabled,
                    "saved_count": len(self._checkpoint_manager.list_checkpoints()),
                },
                "pipelines": [
                    {
                        "id": p.pipeline_id,
                        "type": p.pipeline_type.value,
                        "status": p.status.value,
                        "progress": round(p.progress_percent, 2),
                    }
                    for p in self._active_pipelines.values()
                ],
            }

    def get_checkpoint_manager(self) -> CheckpointManager:
        """체크포인트 관리자 반환."""
        return self._checkpoint_manager

    # ============================================================
    # 종료
    # ============================================================
    async def shutdown(self, save_checkpoints: bool = True) -> None:
        """
        코디네이터 종료.

        Args:
            save_checkpoints: 활성 파이프라인의 체크포인트 저장 여부
        """
        logger.info("PipelineCoordinator 종료 시작")

        # 활성 파이프라인 체크포인트 저장 및 취소
        with self._lock:
            for pipeline_id in list(self._active_pipelines.keys()):
                if save_checkpoints and self._checkpoint_manager.enabled:
                    context = self._pipeline_contexts.get(pipeline_id)
                    progress = self._active_pipelines.get(pipeline_id)
                    if context and progress:
                        checkpoint = context.create_checkpoint(
                            progress.completed_stages
                        )
                        self._checkpoint_manager.save(checkpoint)
                        logger.debug(
                            f"종료 전 체크포인트 저장: {pipeline_id}"
                        )

                self.cancel(pipeline_id)

        # 오래된 체크포인트 정리
        if self._checkpoint_manager.enabled:
            deleted = self._checkpoint_manager.cleanup_old(max_age_hours=24)
            if deleted > 0:
                logger.info(f"오래된 체크포인트 {deleted}개 정리")

        logger.info("PipelineCoordinator 종료 완료")


# ============================================================
# 파이프라인 빌더
# ============================================================
class PipelineBuilder:
    """
    파이프라인 빌더.

    파이프라인 설정을 구성하는 빌더 패턴 구현.

    Example:
        >>> config = (
        ...     PipelineBuilder(PipelineType.TRAINING_SHOOTING)
        ...     .add_stage(StageType.INITIALIZATION)
        ...     .add_stage(StageType.VIDEO_DOWNLOAD)
        ...     .add_stage(StageType.DETECTION)
        ...     .add_stage(StageType.POSE_ESTIMATION, timeout=120)
        ...     .add_stage(StageType.SHOOTING_ANALYSIS)
        ...     .add_stage(StageType.FEEDBACK_GENERATION)
        ...     .with_timeout(1200)
        ...     .build()
        ... )
    """

    def __init__(self, pipeline_type: PipelineType) -> None:
        """초기화."""
        self._pipeline_type = pipeline_type
        self._stages: list[StageConfig] = []
        self._timeout = DEFAULT_PIPELINE_TIMEOUT
        self._fail_fast = True
        self._parallel_stages = False
        self._max_parallel = 4
        self._metadata: dict[str, Any] = {}

    def add_stage(
        self,
        stage_type: StageType,
        handler: StageHandler | None = None,
        timeout: float = DEFAULT_STAGE_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        skip_on_failure: bool = False,
        dependencies: list[StageType] | None = None,
    ) -> "PipelineBuilder":
        """
        스테이지 추가.

        Args:
            stage_type: 스테이지 타입
            handler: 핸들러 함수
            timeout: 타임아웃 (초)
            max_retries: 최대 재시도
            retry_delay: 재시도 대기
            skip_on_failure: 실패 시 건너뛰기
            dependencies: 의존 스테이지

        Returns:
            빌더 (체이닝용)
        """
        stage = StageConfig(
            stage_type=stage_type,
            handler=handler,
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            skip_on_failure=skip_on_failure,
            dependencies=dependencies or [],
        )
        self._stages.append(stage)
        return self

    def with_timeout(self, timeout_seconds: float) -> "PipelineBuilder":
        """파이프라인 타임아웃 설정."""
        self._timeout = timeout_seconds
        return self

    def with_fail_fast(self, fail_fast: bool) -> "PipelineBuilder":
        """fail_fast 설정."""
        self._fail_fast = fail_fast
        return self

    def with_parallel(
        self,
        parallel: bool = True,
        max_parallel: int = 4,
    ) -> "PipelineBuilder":
        """병렬 실행 설정."""
        self._parallel_stages = parallel
        self._max_parallel = max_parallel
        return self

    def with_metadata(self, key: str, value: Any) -> "PipelineBuilder":
        """메타데이터 추가."""
        self._metadata[key] = value
        return self

    def build(self) -> PipelineConfig:
        """
        파이프라인 설정 빌드.

        Returns:
            구성된 PipelineConfig
        """
        return PipelineConfig(
            pipeline_type=self._pipeline_type,
            stages=self._stages,
            timeout_seconds=self._timeout,
            fail_fast=self._fail_fast,
            parallel_stages=self._parallel_stages,
            max_parallel=self._max_parallel,
            metadata=self._metadata,
        )


# ============================================================
# 사전 정의 파이프라인 템플릿
# ============================================================
class PipelineTemplates:
    """
    사전 정의 파이프라인 템플릿.

    일반적인 분석 시나리오를 위한 파이프라인 템플릿을 제공합니다.
    """

    @staticmethod
    def training_shooting() -> PipelineConfig:
        """슈팅 훈련 분석 파이프라인."""
        return (
            PipelineBuilder(PipelineType.TRAINING_SHOOTING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.VIDEO_PREPROCESSING)
            .add_stage(StageType.FRAME_EXTRACTION)
            .add_stage(StageType.PERSON_DETECTION)
            .add_stage(StageType.BALL_DETECTION)
            .add_stage(StageType.HOOP_DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.POSE_TRACKING)
            .add_stage(StageType.BIOMECHANICS_ANALYSIS)
            .add_stage(StageType.SHOOTING_ANALYSIS)
            .add_stage(StageType.FEEDBACK_GENERATION)
            .add_stage(StageType.POSTPROCESSING)
            .add_stage(StageType.RESULT_UPLOAD)
            .add_stage(StageType.CLEANUP, skip_on_failure=True)
            .with_timeout(1800)
            .build()
        )

    @staticmethod
    def training_dribbling() -> PipelineConfig:
        """드리블 훈련 분석 파이프라인."""
        return (
            PipelineBuilder(PipelineType.TRAINING_DRIBBLING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.VIDEO_PREPROCESSING)
            .add_stage(StageType.FRAME_EXTRACTION)
            .add_stage(StageType.PERSON_DETECTION)
            .add_stage(StageType.BALL_DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.POSE_TRACKING)
            .add_stage(StageType.BIOMECHANICS_ANALYSIS)
            .add_stage(StageType.DRIBBLING_ANALYSIS)
            .add_stage(StageType.FEEDBACK_GENERATION)
            .add_stage(StageType.POSTPROCESSING)
            .add_stage(StageType.RESULT_UPLOAD)
            .add_stage(StageType.CLEANUP, skip_on_failure=True)
            .with_timeout(1800)
            .build()
        )

    @staticmethod
    def training_comparison() -> PipelineConfig:
        """정답 영상 비교 분석 파이프라인."""
        return (
            PipelineBuilder(PipelineType.TRAINING_COMPARISON)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.VIDEO_PREPROCESSING)
            .add_stage(StageType.FRAME_EXTRACTION)
            .add_stage(StageType.PERSON_DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.POSE_TRACKING)
            .add_stage(StageType.MOTION_ANALYSIS)
            .add_stage(StageType.COMPARISON_ANALYSIS)
            .add_stage(StageType.FEEDBACK_GENERATION)
            .add_stage(StageType.POSTPROCESSING)
            .add_stage(StageType.RESULT_UPLOAD)
            .add_stage(StageType.CLEANUP, skip_on_failure=True)
            .with_timeout(2400)
            .build()
        )

    @staticmethod
    def game_full() -> PipelineConfig:
        """전체 경기 분석 파이프라인."""
        return (
            PipelineBuilder(PipelineType.GAME_FULL)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.VIDEO_PREPROCESSING)
            .add_stage(StageType.FRAME_EXTRACTION)
            .add_stage(StageType.PERSON_DETECTION)
            .add_stage(StageType.BALL_DETECTION)
            .add_stage(StageType.COURT_DETECTION)
            .add_stage(StageType.HOOP_DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.POSE_TRACKING)
            .add_stage(StageType.GAME_ANALYSIS)
            .add_stage(StageType.STATISTICS_CALCULATION)
            .add_stage(StageType.RESULT_AGGREGATION)
            .add_stage(StageType.RESULT_UPLOAD)
            .add_stage(StageType.CLEANUP, skip_on_failure=True)
            .with_timeout(3600)
            .build()
        )

    @staticmethod
    def referee_full() -> PipelineConfig:
        """전체 심판 분석 파이프라인."""
        return (
            PipelineBuilder(PipelineType.REFEREE_FULL)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.VIDEO_PREPROCESSING)
            .add_stage(StageType.FRAME_EXTRACTION)
            .add_stage(StageType.PERSON_DETECTION)
            .add_stage(StageType.BALL_DETECTION)
            .add_stage(StageType.COURT_DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.POSE_TRACKING)
            .add_stage(StageType.REFEREE_ANALYSIS)
            .add_stage(StageType.RESULT_AGGREGATION)
            .add_stage(StageType.RESULT_UPLOAD)
            .add_stage(StageType.CLEANUP, skip_on_failure=True)
            .with_timeout(3600)
            .build()
        )


# ============================================================
# 전역 인스턴스 관리
# ============================================================
_global_coordinator: PipelineCoordinator | None = None
_coordinator_lock = threading.Lock()


def get_coordinator() -> PipelineCoordinator:
    """
    전역 코디네이터 가져오기.

    Returns:
        전역 PipelineCoordinator 인스턴스
    """
    global _global_coordinator
    with _coordinator_lock:
        if _global_coordinator is None:
            _global_coordinator = PipelineCoordinator()
        return _global_coordinator


def create_pipeline(
    pipeline_type: PipelineType,
    stages: list[StageConfig] | None = None,
    timeout_seconds: float = DEFAULT_PIPELINE_TIMEOUT,
    **kwargs: Any,
) -> PipelineConfig:
    """
    파이프라인 설정 생성 헬퍼.

    Args:
        pipeline_type: 파이프라인 타입
        stages: 스테이지 목록 (없으면 템플릿 사용)
        timeout_seconds: 타임아웃 (초)
        **kwargs: 추가 설정

    Returns:
        파이프라인 설정
    """
    if stages:
        return PipelineConfig(
            pipeline_type=pipeline_type,
            stages=stages,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    # 템플릿 사용
    template_map = {
        PipelineType.TRAINING_SHOOTING: PipelineTemplates.training_shooting,
        PipelineType.TRAINING_DRIBBLING: PipelineTemplates.training_dribbling,
        PipelineType.TRAINING_COMPARISON: PipelineTemplates.training_comparison,
        PipelineType.GAME_FULL: PipelineTemplates.game_full,
        PipelineType.REFEREE_FULL: PipelineTemplates.referee_full,
    }

    template_func = template_map.get(pipeline_type)
    if template_func:
        config = template_func()
        config.timeout_seconds = timeout_seconds
        return config

    # 기본 빈 파이프라인
    return PipelineConfig(
        pipeline_type=pipeline_type,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )


def _reset_coordinator() -> None:
    """전역 코디네이터 초기화 (테스트용)."""
    global _global_coordinator
    with _coordinator_lock:
        if _global_coordinator is not None:
            # 비동기 종료 시도
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_global_coordinator.shutdown(save_checkpoints=False))
                else:
                    loop.run_until_complete(_global_coordinator.shutdown(save_checkpoints=False))
            except Exception:
                pass
            _global_coordinator = None
    # 설정 제공자도 초기화
    _PipelineConfigProvider.reset_instance()


# 모듈 버전 정보
__version__: str = "1.0.0"
