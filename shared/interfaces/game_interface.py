# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/interfaces
파일: game_interface.py
설명: 경기 분석 모듈 추상 인터페이스 정의 - 이벤트 감지, 심판 검증, 멀티뷰 융합 프로토콜
      - GameModuleState: 경기 모듈 생명주기 상태 (7단계)
      - GameEventResult[OutputT]: 이벤트 감지 결과 래퍼 (성공/실패 팩토리)
      - ValidationResult: 심판 검증 결과 (확인/기각 팩토리)
      - FusionResult[OutputT]: 멀티뷰 융합 결과 래퍼 (성공/실패 팩토리)
      - GameModuleMetrics: 경기 모듈 성능 메트릭
      - IGameEventDetector[EventT, ConfigT]: 이벤트 감지기 ABC (L5)
      - IRefereeValidator[ConfigT]: 심판 규칙 검증기 ABC (L6)
      - IMultiViewFusion[ConfigT]: 멀티뷰 융합기 ABC (L1.5)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

사용처:
    - game_analysis/event_detection/: IGameEventDetector 상속 (16종 이벤트 감지기)
    - ai_referee/: IRefereeValidator 상속 (규칙 검증, 파울/바이올레이션 판정)
    - multi_view/fusion/: IMultiViewFusion 상속 (객체/포즈/궤적 융합)

참조:
    - shared/interfaces/analyzer_interface.py: 분석기 인터페이스 (유사 패턴)
    - shared/interfaces/detector_interface.py: 탐지기 인터페이스 (유사 패턴)
    - shared/dto/game_dto.py: 경기 이벤트/심판 DTO
    - shared/dto/referee_dto.py: 심판 판정 DTO
    - shared/dto/detection_dto.py: 감지 결과 DTO
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import TYPE_CHECKING, Any, Final, Generic, TypeVar

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
import numpy as np

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage

if TYPE_CHECKING:
    from shared.constants.game_rule_constants import (  # noqa: F401
        FoulType,
        GameEventType,
        ViolationType,
    )
    from shared.constants.referee_rule_constants import RuleSet  # noqa: F401


# =============================================================================
# 타입 변수 정의
# =============================================================================
EventT = TypeVar("EventT")    # 이벤트 타입 (GameEvent, ViolationEvent 등)
OutputT = TypeVar("OutputT")  # 출력 타입
ConfigT = TypeVar("ConfigT")  # 설정 타입


# =============================================================================
# 경기 모듈 상태 열거형
# =============================================================================
@unique
class GameModuleState(str, Enum):
    """
    경기 모듈 상태 열거형.

    경기 분석 관련 모듈(이벤트 감지기, 심판 검증기, 멀티뷰 융합기)의
    공통 생명주기 상태를 나타냅니다.
    AnalyzerState(6멤버)에 INITIALIZING을 추가한 7멤버 버전입니다.
    """

    UNINITIALIZED = "uninitialized"  # 초기화 전
    INITIALIZING = "initializing"    # 초기화 중 (규칙 DB, 캘리브레이션 로드)
    READY = "ready"                  # 준비 완료
    PROCESSING = "processing"        # 처리 중
    PAUSED = "paused"                # 일시 정지
    ERROR = "error"                  # 오류 상태
    SHUTDOWN = "shutdown"            # 종료됨

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
        return _GAME_MODULE_STATE_NAME_MAP[self].get(
            lang, _GAME_MODULE_STATE_NAME_MAP[self][SupportedLanguage.KO]
        )

    @property
    def to_korean(self) -> str:
        """한글 상태명."""
        return self.get_name(SupportedLanguage.KO)

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (처리 가능한 상태)."""
        return self in _GAME_MODULE_STATE_ACTIVE

    @property
    def is_initializing(self) -> bool:
        """초기화 중 여부."""
        return self == GameModuleState.INITIALIZING

    @property
    def is_error(self) -> bool:
        """오류 상태 여부."""
        return self == GameModuleState.ERROR

    @property
    def is_terminated(self) -> bool:
        """종료 상태 여부."""
        return self in _GAME_MODULE_STATE_TERMINATED

    @property
    def can_process(self) -> bool:
        """처리 요청 수락 가능 여부 (READY 또는 PAUSED)."""
        return self in _GAME_MODULE_STATE_CAN_PROCESS


# -- GameModuleState 다국어 이름 캐시 (모듈 레벨, 1회 생성) --

_GAME_MODULE_STATE_NAME_MAP: Final[dict[GameModuleState, dict[SupportedLanguage, str]]] = {
    GameModuleState.UNINITIALIZED: {
        SupportedLanguage.KO: "초기화 전",
        SupportedLanguage.EN: "Uninitialized",
        SupportedLanguage.JA: "未初期化",
        SupportedLanguage.ZH: "未初始化",
        SupportedLanguage.ES: "Sin inicializar",
    },
    GameModuleState.INITIALIZING: {
        SupportedLanguage.KO: "초기화 중",
        SupportedLanguage.EN: "Initializing",
        SupportedLanguage.JA: "初期化中",
        SupportedLanguage.ZH: "初始化中",
        SupportedLanguage.ES: "Inicializando",
    },
    GameModuleState.READY: {
        SupportedLanguage.KO: "준비 완료",
        SupportedLanguage.EN: "Ready",
        SupportedLanguage.JA: "準備完了",
        SupportedLanguage.ZH: "就绪",
        SupportedLanguage.ES: "Listo",
    },
    GameModuleState.PROCESSING: {
        SupportedLanguage.KO: "처리 중",
        SupportedLanguage.EN: "Processing",
        SupportedLanguage.JA: "処理中",
        SupportedLanguage.ZH: "处理中",
        SupportedLanguage.ES: "Procesando",
    },
    GameModuleState.PAUSED: {
        SupportedLanguage.KO: "일시 정지",
        SupportedLanguage.EN: "Paused",
        SupportedLanguage.JA: "一時停止",
        SupportedLanguage.ZH: "已暂停",
        SupportedLanguage.ES: "En pausa",
    },
    GameModuleState.ERROR: {
        SupportedLanguage.KO: "오류",
        SupportedLanguage.EN: "Error",
        SupportedLanguage.JA: "エラー",
        SupportedLanguage.ZH: "错误",
        SupportedLanguage.ES: "Error",
    },
    GameModuleState.SHUTDOWN: {
        SupportedLanguage.KO: "종료됨",
        SupportedLanguage.EN: "Shutdown",
        SupportedLanguage.JA: "シャットダウン",
        SupportedLanguage.ZH: "已关闭",
        SupportedLanguage.ES: "Apagado",
    },
}

_GAME_MODULE_STATE_ACTIVE: frozenset[GameModuleState] = frozenset({
    GameModuleState.READY, GameModuleState.PROCESSING, GameModuleState.PAUSED,
})

_GAME_MODULE_STATE_TERMINATED: frozenset[GameModuleState] = frozenset({
    GameModuleState.SHUTDOWN, GameModuleState.ERROR,
})

_GAME_MODULE_STATE_CAN_PROCESS: frozenset[GameModuleState] = frozenset({
    GameModuleState.READY, GameModuleState.PAUSED,
})


# =============================================================================
# 이벤트 감지 결과
# =============================================================================
@dataclass(slots=True)
class GameEventResult(Generic[OutputT]):
    """
    이벤트 감지 결과 래퍼.

    IGameEventDetector의 출력을 감싸는 공통 구조입니다.
    """

    success: bool
    data: OutputT | None = None
    error_message: str | None = None
    error_code: str | None = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    frame_index: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events_detected: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: OutputT,
        confidence: float = 1.0,
        processing_time_ms: float = 0.0,
        frame_index: int | None = None,
        events_detected: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "GameEventResult[OutputT]":
        """성공 결과 생성."""
        return cls(
            success=True,
            data=data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            frame_index=frame_index,
            events_detected=events_detected,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "GameEventResult[OutputT]":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            error_code=error_code,
            metadata=metadata or {},
        )


# =============================================================================
# 심판 검증 결과
# =============================================================================
@dataclass(slots=True)
class ValidationResult:
    """
    심판 검증 결과.

    IRefereeValidator의 검증 결과를 감싸는 구조입니다.
    is_valid: 규칙 위반/파울이 실제로 유효한지 여부 (판정 확인/기각).
    """

    is_valid: bool
    confidence: float = 0.0
    rule_reference: str = ""
    explanation: str = ""
    processing_time_ms: float = 0.0
    evidence_quality: float = 0.0
    requires_review: bool = False
    alternative_calls: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def confirmed(
        cls,
        confidence: float,
        rule_reference: str,
        explanation: str,
        processing_time_ms: float = 0.0,
        evidence_quality: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ValidationResult":
        """위반/파울 확인 결과 생성."""
        return cls(
            is_valid=True,
            confidence=confidence,
            rule_reference=rule_reference,
            explanation=explanation,
            processing_time_ms=processing_time_ms,
            evidence_quality=evidence_quality,
            metadata=metadata or {},
        )

    @classmethod
    def rejected(
        cls,
        confidence: float,
        explanation: str,
        processing_time_ms: float = 0.0,
        evidence_quality: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ValidationResult":
        """위반/파울 기각 결과 생성."""
        return cls(
            is_valid=False,
            confidence=confidence,
            explanation=explanation,
            processing_time_ms=processing_time_ms,
            evidence_quality=evidence_quality,
            metadata=metadata or {},
        )


# =============================================================================
# 멀티뷰 융합 결과
# =============================================================================
@dataclass(slots=True)
class FusionResult(Generic[OutputT]):
    """
    멀티뷰 융합 결과 래퍼.

    IMultiViewFusion의 출력을 감싸는 공통 구조입니다.
    """

    success: bool
    data: OutputT | None = None
    error_message: str | None = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    num_views_used: int = 0
    num_views_rejected: int = 0
    fusion_quality: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: OutputT,
        confidence: float = 1.0,
        processing_time_ms: float = 0.0,
        num_views_used: int = 0,
        num_views_rejected: int = 0,
        fusion_quality: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "FusionResult[OutputT]":
        """성공 결과 생성."""
        return cls(
            success=True,
            data=data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            num_views_used=num_views_used,
            num_views_rejected=num_views_rejected,
            fusion_quality=fusion_quality,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> "FusionResult[OutputT]":
        """실패 결과 생성."""
        return cls(
            success=False,
            error_message=error_message,
            metadata=metadata or {},
        )


# =============================================================================
# 경기 모듈 메트릭
# =============================================================================
@dataclass(slots=True)
class GameModuleMetrics:
    """
    경기 모듈 성능 메트릭.

    IGameEventDetector, IRefereeValidator, IMultiViewFusion 공통 메트릭.
    3종 결과 타입에 대한 typed update 메서드를 제공합니다.
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

    def update_from_event_result(
        self, result: GameEventResult[Any], processing_time_ms: float
    ) -> None:
        """이벤트 감지 결과로 메트릭 업데이트."""
        self._update_common(
            result.success, result.confidence, result.error_message, processing_time_ms
        )

    def update_from_validation_result(
        self, result: ValidationResult, processing_time_ms: float
    ) -> None:
        """검증 결과로 메트릭 업데이트 (검증 처리 자체는 항상 성공)."""
        self._update_common(True, result.confidence, None, processing_time_ms)

    def update_from_fusion_result(
        self, result: FusionResult[Any], processing_time_ms: float
    ) -> None:
        """융합 결과로 메트릭 업데이트."""
        self._update_common(
            result.success, result.confidence, result.error_message, processing_time_ms
        )

    def _update_common(
        self,
        success: bool,
        confidence: float,
        error_message: str | None,
        processing_time_ms: float,
    ) -> None:
        """공통 메트릭 업데이트 로직."""
        self.total_processed += 1
        self.total_processing_time_ms += processing_time_ms

        if success:
            self.successful_count += 1
            # 이동 평균으로 신뢰도 계산
            self.average_confidence = (
                (self.average_confidence * (self.successful_count - 1) + confidence)
                / self.successful_count
            )
        else:
            self.failed_count += 1
            self.last_error = error_message
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
# 이벤트 감지기 인터페이스
# =============================================================================
class IGameEventDetector(ABC, Generic[EventT, ConfigT]):
    """
    이벤트 감지기 인터페이스.

    경기 중 발생하는 농구 이벤트(슛, 파울, 바이올레이션, 턴오버 등)를
    비디오 프레임에서 감지하는 모듈의 추상 인터페이스입니다.

    Type Parameters:
        EventT: 감지하는 이벤트 타입 (예: GameEvent, ViolationEvent)
        ConfigT: 감지기 설정 타입

    사용처:
        - game_analysis/event_detection/ (16종 감지기)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """감지기 이름."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """감지기 버전."""
        ...

    @property
    @abstractmethod
    def state(self) -> GameModuleState:
        """현재 상태."""
        ...

    @property
    @abstractmethod
    def metrics(self) -> GameModuleMetrics:
        """성능 메트릭."""
        ...

    @property
    @abstractmethod
    def supported_events(self) -> list[str]:
        """
        감지 가능한 이벤트 유형 목록.

        Returns:
            GameEventType.value 문자열 목록
        """
        ...

    @abstractmethod
    def initialize(self, config: ConfigT) -> None:
        """
        감지기 초기화.

        Args:
            config: 감지기 설정

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        ...

    @abstractmethod
    def detect_events(
        self,
        frame: np.ndarray,
        detections: list[Any],
        tracks: list[Any],
        poses: list[Any],
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> GameEventResult[list[EventT]]:
        """
        프레임에서 이벤트 감지.

        Args:
            frame: BGR 이미지 (H, W, 3)
            detections: 현재 프레임 감지 결과 목록
            tracks: 추적 결과 목록
            poses: 포즈 추정 결과 목록
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            이벤트 감지 결과
        """
        ...

    @abstractmethod
    def get_active_events(self) -> list[EventT]:
        """
        현재 진행 중인 이벤트 목록.

        아직 종료되지 않은 활성 이벤트를 반환합니다.

        Returns:
            활성 이벤트 목록
        """
        ...

    @abstractmethod
    def get_event_history(
        self,
        event_type: str | None = None,
        start_time_ms: float | None = None,
        end_time_ms: float | None = None,
        max_count: int = 100,
    ) -> list[EventT]:
        """
        이벤트 이력 조회.

        Args:
            event_type: 이벤트 유형 필터 (GameEventType.value, None이면 전체)
            start_time_ms: 시작 시간 필터 (밀리초)
            end_time_ms: 종료 시간 필터 (밀리초)
            max_count: 최대 반환 수

        Returns:
            조건에 맞는 이벤트 목록
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """감지기 상태 초기화."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """감지기 종료 및 리소스 해제."""
        ...

    def validate_input(self, frame: np.ndarray) -> bool:
        """
        입력 프레임 유효성 검사.

        기본 구현: None 체크 + ndarray 3차원 + 3채널.
        하위 클래스에서 오버라이드하여 상세 검증을 구현하세요.

        Args:
            frame: 검증할 프레임

        Returns:
            유효 여부
        """
        if frame is None:
            return False
        if not isinstance(frame, np.ndarray):
            return False
        if frame.ndim != 3 or frame.shape[2] != 3:
            return False
        return True


# =============================================================================
# 심판 규칙 검증기 인터페이스
# =============================================================================
class IRefereeValidator(ABC, Generic[ConfigT]):
    """
    심판 규칙 검증기 인터페이스.

    AI 심판 시스템에서 감지된 바이올레이션/파울을 규칙에 따라 검증하는
    모듈의 추상 인터페이스입니다.
    FIBA, NBA, KBL, NBL 등 다양한 규칙 세트를 지원합니다.

    Type Parameters:
        ConfigT: 검증기 설정 타입

    사용처:
        - ai_referee/ (규칙 검증, 파울/바이올레이션 판정)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """검증기 이름."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """검증기 버전."""
        ...

    @property
    @abstractmethod
    def state(self) -> GameModuleState:
        """현재 상태."""
        ...

    @property
    @abstractmethod
    def metrics(self) -> GameModuleMetrics:
        """성능 메트릭."""
        ...

    @property
    @abstractmethod
    def active_rule_set(self) -> str:
        """
        현재 적용 중인 규칙 세트.

        Returns:
            RuleSet.value 문자열 (예: "fiba", "nba", "kbl")
        """
        ...

    @property
    @abstractmethod
    def confidence_threshold(self) -> float:
        """
        판정 신뢰도 임계값.

        이 값 이상의 신뢰도를 가진 판정만 자동 확정됩니다.

        Returns:
            임계값 (0.0~1.0)
        """
        ...

    @property
    @abstractmethod
    def consistency_score(self) -> float:
        """
        판정 일관성 점수.

        최근 판정들의 일관성을 나타냅니다.

        Returns:
            일관성 점수 (0.0~1.0, 높을수록 일관적)
        """
        ...

    @abstractmethod
    def initialize(self, config: ConfigT, rule_set: str = "fiba") -> None:
        """
        검증기 초기화.

        Args:
            config: 검증기 설정
            rule_set: 규칙 세트 (RuleSet.value, 기본값: "fiba")

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        ...

    @abstractmethod
    def validate_violation(
        self,
        violation_data: Any,
        evidence: dict[str, Any],
    ) -> ValidationResult:
        """
        바이올레이션 검증.

        감지된 바이올레이션이 규칙에 부합하는지 검증합니다.

        Args:
            violation_data: 바이올레이션 데이터 (ViolationEvent 등)
            evidence: 증거 데이터 (프레임, 포즈, 궤적 등)

        Returns:
            검증 결과
        """
        ...

    @abstractmethod
    def validate_foul(
        self,
        foul_data: Any,
        evidence: dict[str, Any],
    ) -> ValidationResult:
        """
        파울 검증.

        감지된 파울이 규칙에 부합하는지 검증합니다.

        Args:
            foul_data: 파울 데이터 (FoulEvent 등)
            evidence: 증거 데이터 (프레임, 포즈, 궤적, 접촉 분석 등)

        Returns:
            검증 결과
        """
        ...

    @abstractmethod
    def check_consistency(
        self,
        decision: Any,
        history: list[Any],
    ) -> float:
        """
        판정 일관성 확인.

        현재 판정이 과거 판정 이력과 얼마나 일관적인지 확인합니다.

        Args:
            decision: 현재 판정 (RefereeCall, RefereeDecision 등)
            history: 과거 판정 이력

        Returns:
            일관성 점수 (0.0~1.0, 높을수록 일관적)
        """
        ...

    @abstractmethod
    def get_decision_explanation(
        self,
        decision: Any,
        lang: str = "ko",
    ) -> str:
        """
        판정 설명 생성.

        사람이 읽을 수 있는 판정 설명을 생성합니다.

        Args:
            decision: 판정 데이터
            lang: 출력 언어 코드 (SupportedLanguage.value, 기본값: "ko")

        Returns:
            판정 설명 문자열
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """검증기 상태 초기화."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """검증기 종료 및 리소스 해제."""
        ...


# =============================================================================
# 멀티뷰 융합 인터페이스
# =============================================================================
class IMultiViewFusion(ABC, Generic[ConfigT]):
    """
    멀티뷰 융합 인터페이스.

    다중 카메라 뷰의 감지/포즈/궤적을 3D 공간에서 통합하는
    모듈의 추상 인터페이스입니다.

    Type Parameters:
        ConfigT: 융합기 설정 타입

    사용처:
        - multi_view/fusion/ (ObjectFusion, PoseFusion, BallTrajectoryFusion)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """융합기 이름."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """융합기 버전."""
        ...

    @property
    @abstractmethod
    def state(self) -> GameModuleState:
        """현재 상태."""
        ...

    @property
    @abstractmethod
    def metrics(self) -> GameModuleMetrics:
        """성능 메트릭."""
        ...

    @property
    @abstractmethod
    def num_views(self) -> int:
        """
        구성된 카메라 뷰 수.

        Returns:
            카메라 수
        """
        ...

    @property
    @abstractmethod
    def calibration_quality(self) -> float:
        """
        카메라 캘리브레이션 품질.

        Returns:
            품질 점수 (0.0~1.0)
        """
        ...

    @abstractmethod
    def initialize(
        self, config: ConfigT, calibrations: list[Any] | None = None
    ) -> None:
        """
        융합기 초기화.

        Args:
            config: 융합기 설정
            calibrations: 카메라 캘리브레이션 데이터 목록 (선택적)

        Raises:
            ConfigurationException: 설정이 유효하지 않은 경우
        """
        ...

    @abstractmethod
    def fuse_detections(
        self,
        per_view_detections: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        """
        멀티뷰 객체 감지 융합.

        각 카메라 뷰의 객체 감지 결과를 3D 공간에서 통합합니다.

        Args:
            per_view_detections: 카메라ID -> 감지 결과 목록

        Returns:
            융합된 객체 목록
        """
        ...

    @abstractmethod
    def fuse_poses(
        self,
        per_view_poses: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        """
        멀티뷰 포즈 융합.

        각 카메라 뷰의 2D 스켈레톤을 3D 스켈레톤으로 융합합니다.

        Args:
            per_view_poses: 카메라ID -> 포즈 결과 목록

        Returns:
            융합된 3D 포즈 목록
        """
        ...

    @abstractmethod
    def fuse_trajectories(
        self,
        per_view_trajectories: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        """
        멀티뷰 궤적 융합.

        각 카메라 뷰의 공 궤적을 3D 궤적으로 융합합니다.

        Args:
            per_view_trajectories: 카메라ID -> 궤적 데이터 목록

        Returns:
            융합된 3D 궤적
        """
        ...

    @abstractmethod
    def triangulate_point(
        self,
        per_view_points: dict[str, tuple[float, float]],
    ) -> tuple[float, float, float]:
        """
        3D 삼각측량.

        다중 카메라 뷰의 2D 좌표를 3D 좌표로 삼각측량합니다.

        Args:
            per_view_points: 카메라ID -> (x, y) 2D 좌표

        Returns:
            (x, y, z) 3D 좌표

        Raises:
            ValueError: 뷰가 2개 미만인 경우
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """융합기 상태 초기화."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """융합기 종료 및 리소스 해제."""
        ...


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
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
