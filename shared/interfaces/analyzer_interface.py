# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/interfaces
파일: analyzer_interface.py
설명: 분석기 추상 인터페이스 정의 - 모든 분석 모듈의 기반 프로토콜
      - AnalyzerState: 분석기 생명주기 상태 (6단계)
      - AnalysisResult[OutputT]: 분석 결과 래퍼 (성공/실패 팩토리)
      - AnalyzerMetrics: 성능 메트릭 (FPS, 신뢰도, 성공률)
      - IAnalyzer[InputT, OutputT, ConfigT]: 기본 분석기 ABC
      - IFrameAnalyzer: 단일 프레임 분석 (L1~L2)
      - ISequenceAnalyzer: 프레임 시퀀스 분석 (L3~L4)
      - IStreamAnalyzer: 실시간 스트림 분석 (L5)
      - IComparisonAnalyzer: 비교 분석 (따라하기 훈련)
      - IAnalyzerFactory: 분석기 팩토리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

사용처:
    - motion_analysis/: ISequenceAnalyzer 상속 (동작 분류 분석기)
    - biomechanics/: IFrameAnalyzer 상속 (생체역학 분석기)
    - game_analysis/: IStreamAnalyzer 상속 (실시간 경기 분석기)
    - pose_estimation/: IFrameAnalyzer 상속 (포즈 추정기)

참조:
    - shared/interfaces/detector_interface.py: 탐지기 인터페이스 (유사 패턴)
    - shared/interfaces/storage_interface.py: 스토리지 인터페이스 (유사 패턴)
"""

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Generic, TypeVar
from uuid import UUID

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
import numpy as np

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 타입 변수 정의
# =============================================================================
InputT = TypeVar("InputT")  # 입력 타입
OutputT = TypeVar("OutputT")  # 출력 타입
ConfigT = TypeVar("ConfigT")  # 설정 타입


# =============================================================================
# 분석 상태 열거형
# =============================================================================
@unique
class AnalyzerState(str, Enum):
    """
    분석기 상태 열거형.

    분석기의 생명주기 상태를 나타냅니다.
    """

    UNINITIALIZED = "uninitialized"  # 초기화 전
    READY = "ready"  # 준비 완료
    PROCESSING = "processing"  # 처리 중
    PAUSED = "paused"  # 일시 정지
    ERROR = "error"  # 오류 상태
    SHUTDOWN = "shutdown"  # 종료됨

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 상태명
        """
        return _ANALYZER_STATE_NAME_MAP[self].get(
            lang, _ANALYZER_STATE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 상태명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (처리 가능한 상태)."""
        return self in (AnalyzerState.READY, AnalyzerState.PROCESSING, AnalyzerState.PAUSED)

    @property
    def is_error(self) -> bool:
        """오류 상태 여부."""
        return self == AnalyzerState.ERROR

    @property
    def is_terminated(self) -> bool:
        """종료 상태 여부."""
        return self in (AnalyzerState.SHUTDOWN, AnalyzerState.ERROR)


# -- AnalyzerState 다국어 이름 캐시 (모듈 레벨, 1회 생성) --

_ANALYZER_STATE_NAME_MAP: dict[AnalyzerState, dict[SupportedLanguage, str]] = {
    AnalyzerState.UNINITIALIZED: {
        SupportedLanguage.KO: "초기화 전",
        SupportedLanguage.EN: "Uninitialized",
        SupportedLanguage.JA: "未初期化",
        SupportedLanguage.ZH: "未初始化",
        SupportedLanguage.ES: "Sin inicializar",
    },
    AnalyzerState.READY: {
        SupportedLanguage.KO: "준비 완료",
        SupportedLanguage.EN: "Ready",
        SupportedLanguage.JA: "準備完了",
        SupportedLanguage.ZH: "就绪",
        SupportedLanguage.ES: "Listo",
    },
    AnalyzerState.PROCESSING: {
        SupportedLanguage.KO: "처리 중",
        SupportedLanguage.EN: "Processing",
        SupportedLanguage.JA: "処理中",
        SupportedLanguage.ZH: "处理中",
        SupportedLanguage.ES: "Procesando",
    },
    AnalyzerState.PAUSED: {
        SupportedLanguage.KO: "일시 정지",
        SupportedLanguage.EN: "Paused",
        SupportedLanguage.JA: "一時停止",
        SupportedLanguage.ZH: "已暂停",
        SupportedLanguage.ES: "En pausa",
    },
    AnalyzerState.ERROR: {
        SupportedLanguage.KO: "오류",
        SupportedLanguage.EN: "Error",
        SupportedLanguage.JA: "エラー",
        SupportedLanguage.ZH: "错误",
        SupportedLanguage.ES: "Error",
    },
    AnalyzerState.SHUTDOWN: {
        SupportedLanguage.KO: "종료됨",
        SupportedLanguage.EN: "Shutdown",
        SupportedLanguage.JA: "シャットダウン",
        SupportedLanguage.ZH: "已关闭",
        SupportedLanguage.ES: "Apagado",
    },
}


# =============================================================================
# 분석 결과 기본 구조
# =============================================================================
@dataclass
class AnalysisResult(Generic[OutputT]):
    """
    분석 결과 래퍼.

    모든 분석기의 출력을 감싸는 공통 구조입니다.
    """

    success: bool
    result_id: UUID | None = None  # 결과 고유 식별자
    data: OutputT | None = None
    error_message: str | None = None
    error_code: str | None = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    frame_index: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: OutputT,
        confidence: float = 1.0,
        processing_time_ms: float = 0.0,
        frame_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AnalysisResult[OutputT]":
        """성공 결과 생성."""
        return cls(
            success=True,
            data=data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            frame_index=frame_index,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AnalysisResult[OutputT]":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            error_code=error_code,
            metadata=metadata or {},
        )


# =============================================================================
# 분석기 메트릭
# =============================================================================
@dataclass
class AnalyzerMetrics:
    """
    분석기 성능 메트릭.

    분석기의 성능 및 상태를 추적합니다.
    """

    total_processed: int = 0
    successful_count: int = 0
    failed_count: int = 0
    total_processing_time_ms: float = 0.0
    average_processing_time_ms: float = 0.0
    average_confidence: float = 0.0
    peak_memory_mb: float = 0.0
    current_fps: float = 0.0
    last_error: str | None = None
    last_error_time: datetime | None = None

    def update(self, result: AnalysisResult[Any], processing_time_ms: float) -> None:
        """메트릭 업데이트."""
        self.total_processed += 1
        self.total_processing_time_ms += processing_time_ms

        if result.success:
            self.successful_count += 1
            # 이동 평균으로 신뢰도 계산
            self.average_confidence = (
                (self.average_confidence * (self.successful_count - 1) + result.confidence)
                / self.successful_count
            )
        else:
            self.failed_count += 1
            self.last_error = result.error_message
            self.last_error_time = datetime.now(timezone.utc)

        # 평균 처리 시간 계산
        self.average_processing_time_ms = (
            self.total_processing_time_ms / self.total_processed
        )

        # FPS 계산 (평균 처리 시간 기반)
        if self.average_processing_time_ms > 0:
            self.current_fps = 1000.0 / self.average_processing_time_ms

    @property
    def success_rate(self) -> float:
        """성공률 계산."""
        if self.total_processed == 0:
            return 0.0
        return self.successful_count / self.total_processed


# =============================================================================
# 기본 분석기 인터페이스
# =============================================================================
class IAnalyzer(ABC, Generic[InputT, OutputT, ConfigT]):
    """
    분석기 기본 인터페이스.

    모든 분석 모듈이 구현해야 하는 추상 인터페이스입니다.

    Type Parameters:
        InputT: 입력 데이터 타입 (예: np.ndarray, List[np.ndarray])
        OutputT: 출력 데이터 타입 (예: ShootingAnalysisResult)
        ConfigT: 설정 타입 (예: ShootingAnalyzerConfig)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """분석기 이름."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """분석기 버전."""
        pass

    @property
    @abstractmethod
    def state(self) -> AnalyzerState:
        """현재 상태."""
        pass

    @property
    @abstractmethod
    def metrics(self) -> AnalyzerMetrics:
        """성능 메트릭."""
        pass

    @abstractmethod
    def initialize(self, config: ConfigT) -> None:
        """
        분석기 초기화.

        Args:
            config: 분석기 설정

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        pass

    @abstractmethod
    def analyze(self, input_data: InputT) -> AnalysisResult[OutputT]:
        """
        분석 수행.

        Args:
            input_data: 분석할 입력 데이터

        Returns:
            분석 결과

        Raises:
            AnalysisException: 분석 중 오류 발생
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """분석기 상태 초기화."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """분석기 종료 및 리소스 해제."""
        pass

    def validate_input(self, input_data: InputT) -> bool:
        """
        입력 데이터 유효성 검사.

        기본 구현은 None 체크만 수행합니다.
        하위 클래스에서 오버라이드하여 상세 검증을 구현하세요.

        Args:
            input_data: 검증할 입력 데이터

        Returns:
            유효 여부
        """
        return input_data is not None


# =============================================================================
# 프레임 기반 분석기 인터페이스
# =============================================================================
class IFrameAnalyzer(IAnalyzer[np.ndarray, OutputT, ConfigT], Generic[OutputT, ConfigT]):
    """
    프레임 기반 분석기 인터페이스.

    단일 프레임(이미지)을 분석하는 분석기의 인터페이스입니다.
    """

    @abstractmethod
    def analyze_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_ms: float,
    ) -> AnalysisResult[OutputT]:
        """
        단일 프레임 분석.

        Args:
            frame: BGR 이미지 (H, W, 3)
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            분석 결과
        """
        pass

    def analyze(self, input_data: np.ndarray) -> AnalysisResult[OutputT]:
        """기본 analyze는 frame_index=0으로 호출."""
        return self.analyze_frame(input_data, frame_index=0, timestamp_ms=0.0)

    def validate_input(self, input_data: np.ndarray) -> bool:
        """프레임 유효성 검사."""
        if input_data is None:
            return False
        if not isinstance(input_data, np.ndarray):
            return False
        if input_data.ndim != 3 or input_data.shape[2] != 3:
            return False
        return True


# =============================================================================
# 시퀀스 기반 분석기 인터페이스
# =============================================================================
class ISequenceAnalyzer(IAnalyzer[list[np.ndarray], OutputT, ConfigT], Generic[OutputT, ConfigT]):
    """
    시퀀스 기반 분석기 인터페이스.

    연속된 프레임 시퀀스를 분석하는 분석기의 인터페이스입니다.
    동작 분석, 모션 패턴 분석 등에 사용됩니다.
    """

    @property
    @abstractmethod
    def min_sequence_length(self) -> int:
        """최소 시퀀스 길이."""
        pass

    @property
    @abstractmethod
    def max_sequence_length(self) -> int:
        """최대 시퀀스 길이."""
        pass

    @abstractmethod
    def analyze_sequence(
        self,
        frames: list[np.ndarray],
        start_frame_index: int,
        fps: float,
    ) -> AnalysisResult[OutputT]:
        """
        프레임 시퀀스 분석.

        Args:
            frames: 프레임 시퀀스 (각 프레임은 BGR 이미지)
            start_frame_index: 시작 프레임 인덱스
            fps: 프레임 레이트

        Returns:
            분석 결과
        """
        pass

    def analyze(self, input_data: list[np.ndarray]) -> AnalysisResult[OutputT]:
        """기본 analyze는 start_frame_index=0, fps=30으로 호출."""
        return self.analyze_sequence(input_data, start_frame_index=0, fps=30.0)

    def validate_input(self, input_data: list[np.ndarray]) -> bool:
        """시퀀스 유효성 검사."""
        if input_data is None or len(input_data) == 0:
            return False
        if len(input_data) < self.min_sequence_length:
            return False
        if len(input_data) > self.max_sequence_length:
            return False
        # 모든 프레임 검사
        for frame in input_data:
            if not isinstance(frame, np.ndarray):
                return False
            if frame.ndim != 3 or frame.shape[2] != 3:
                return False
        return True


# =============================================================================
# 스트리밍 분석기 인터페이스
# =============================================================================
class IStreamAnalyzer(IAnalyzer[np.ndarray, OutputT, ConfigT], Generic[OutputT, ConfigT]):
    """
    스트리밍 분석기 인터페이스.

    실시간 스트림을 처리하는 분석기의 인터페이스입니다.
    내부적으로 프레임 버퍼를 유지하며 상태를 추적합니다.
    """

    @property
    @abstractmethod
    def buffer_size(self) -> int:
        """내부 버퍼 크기."""
        pass

    @property
    @abstractmethod
    def is_streaming(self) -> bool:
        """스트리밍 활성화 여부."""
        pass

    @abstractmethod
    def start_stream(self) -> None:
        """스트리밍 시작."""
        pass

    @abstractmethod
    def stop_stream(self) -> None:
        """스트리밍 중지."""
        pass

    @abstractmethod
    def push_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_ms: float,
    ) -> AnalysisResult[OutputT] | None:
        """
        프레임 추가 및 분석.

        버퍼가 충분히 채워지면 분석 결과를 반환합니다.

        Args:
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프

        Returns:
            분석 결과 (버퍼가 부족하면 None)
        """
        pass

    @abstractmethod
    def flush(self) -> list[AnalysisResult[OutputT]]:
        """
        버퍼에 남은 프레임 처리.

        스트림 종료 시 호출하여 남은 데이터를 처리합니다.

        Returns:
            분석 결과 목록
        """
        pass


# =============================================================================
# 비교 분석기 인터페이스
# =============================================================================
@dataclass
class ComparisonInput(Generic[InputT]):
    """비교 분석 입력."""

    reference: InputT  # 기준(정답) 데이터
    target: InputT  # 비교 대상 데이터
    reference_metadata: dict[str, Any] = field(default_factory=dict)
    target_metadata: dict[str, Any] = field(default_factory=dict)


class IComparisonAnalyzer(
    IAnalyzer[ComparisonInput[InputT], OutputT, ConfigT],
    Generic[InputT, OutputT, ConfigT],
):
    """
    비교 분석기 인터페이스.

    기준 데이터와 대상 데이터를 비교하는 분석기의 인터페이스입니다.
    따라하기 훈련, 정답 비교 분석 등에 사용됩니다.
    """

    @abstractmethod
    def compare(
        self,
        reference: InputT,
        target: InputT,
    ) -> AnalysisResult[OutputT]:
        """
        기준 데이터와 대상 데이터 비교.

        Args:
            reference: 기준(정답) 데이터
            target: 비교할 대상 데이터

        Returns:
            비교 분석 결과
        """
        pass

    @abstractmethod
    def calculate_similarity(
        self,
        reference: InputT,
        target: InputT,
    ) -> float:
        """
        유사도 계산.

        Args:
            reference: 기준 데이터
            target: 비교 대상 데이터

        Returns:
            유사도 (0.0 ~ 1.0)
        """
        pass

    def analyze(self, input_data: ComparisonInput[InputT]) -> AnalysisResult[OutputT]:
        """ComparisonInput을 받아 compare 호출."""
        return self.compare(input_data.reference, input_data.target)


# =============================================================================
# 분석기 팩토리 인터페이스
# =============================================================================
class IAnalyzerFactory(ABC, Generic[ConfigT]):
    """
    분석기 팩토리 인터페이스.

    분석기 인스턴스를 생성하는 팩토리의 인터페이스입니다.
    """

    @abstractmethod
    def create(self, config: ConfigT) -> IAnalyzer[Any, Any, ConfigT]:
        """
        분석기 인스턴스 생성.

        Args:
            config: 분석기 설정

        Returns:
            생성된 분석기 인스턴스
        """
        pass

    @abstractmethod
    def get_supported_types(self) -> list[str]:
        """
        지원하는 분석기 타입 목록.

        Returns:
            분석기 타입 이름 목록
        """
        pass


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
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
]

__version__ = "1.0.0"
