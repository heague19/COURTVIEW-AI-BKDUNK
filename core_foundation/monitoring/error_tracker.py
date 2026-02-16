# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: error_tracker.py
설명: 에러 추적, 집계, 통계 분석 - 시스템 에러 모니터링 (Desktop Edition)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 에러 기록 및 추적
    - 에러 집계 및 통계 분석
    - 에러 추세 분석 (시간대별, 카테고리별)
    - 심각도별 에러 분류
    - 에러 중복 감지 (핑거프린트 해시)
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상

Desktop Edition 변경사항:
    - 알림 발송 기능 제거 (Slack, Email, SMS, PagerDuty, Webhook)
    - AlertChannel, AlertConfig, AlertRule 제거
    - Circuit Breaker, ThreadPoolExecutor 제거
    - 에러 추적/집계/통계 핵심 기능만 유지
    - 로컬 로깅 기반 에러 기록 (logger 사용)

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 메모리 효율: 최대 에러 개수 제한 (FIFO)
    - 단일 책임: 에러 추적/집계만 담당

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    error_tracker = ErrorTracker(config_loader)
    error_tracker.track(exception, context={"analysis_id": "abc123"})

    # 헬퍼 함수 사용
    track_error(exception, severity=ErrorSeverity.ERROR)
    summary = get_error_summary(hours=24)
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import logging
import threading
import traceback
import hashlib
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import (
    Any,
)

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode, ErrorCategory
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
    CriticalException,
)

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수 정의
# ============================================================
# 최대 에러 보관 개수 (메모리 효율)
MAX_ERROR_RECORDS: int = 10000

# 최대 에러 해시 보관 개수 (중복 감지용)
MAX_ERROR_HASHES: int = 5000

# 에러 집계 윈도우 크기 (시간 슬롯)
AGGREGATION_WINDOW_SIZE: int = 60  # 분 단위


# ============================================================
# Enum 정의
# ============================================================
class ErrorSeverity(Enum):
    """
    에러 심각도.

    심각도에 따라 처리 우선순위가 결정됩니다.
    숫자가 높을수록 심각합니다.

    Attributes:
        DEBUG: 디버그 레벨 (로깅만)
        INFO: 정보 레벨 (참고용)
        WARNING: 경고 레벨 (주의 필요)
        ERROR: 에러 레벨 (조치 필요)
        CRITICAL: 심각 레벨 (즉시 조치 필요)
    """

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def from_logging_level(cls, level: int) -> "ErrorSeverity":
        """
        logging 레벨을 ErrorSeverity로 변환.

        Args:
            level: logging 레벨 (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50)

        Returns:
            해당하는 ErrorSeverity
        """
        if level <= 10:
            return cls.DEBUG
        elif level <= 20:
            return cls.INFO
        elif level <= 30:
            return cls.WARNING
        elif level <= 40:
            return cls.ERROR
        else:
            return cls.CRITICAL

    @classmethod
    def from_exception(cls, exc: Exception) -> "ErrorSeverity":
        """
        예외 타입에서 심각도 추론.

        Args:
            exc: 예외 객체

        Returns:
            추론된 ErrorSeverity
        """
        if isinstance(exc, CriticalException):
            return cls.CRITICAL
        elif isinstance(exc, NonRetryableException):
            return cls.ERROR
        elif isinstance(exc, RetryableException):
            return cls.WARNING
        elif isinstance(exc, CourtViewException):
            return cls.ERROR
        else:
            return cls.ERROR

    def __lt__(self, other: "ErrorSeverity") -> bool:
        """비교 연산자."""
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: "ErrorSeverity") -> bool:
        """비교 연산자."""
        if not isinstance(other, ErrorSeverity):
            return NotImplemented
        return self.value <= other.value


class TrackingCategory(Enum):
    """
    에러 추적용 세분화 카테고리.

    에러를 기능/도메인별로 세분화하여 분류합니다.
    shared.constants.error_codes.ErrorCategory보다 더 상세한 분류를 제공합니다.

    참고: shared.constants.error_codes.ErrorCategory는 고수준 분류용
          TrackingCategory는 에러 추적 시 세분화된 분류용

    Attributes:
        GENERAL: 일반 에러
        AUTHENTICATION: 인증 관련
        VALIDATION: 입력 검증
        BUSINESS: 비즈니스 로직
        INFRASTRUCTURE: 인프라 (DB, 캐시, 스토리지)
        EXTERNAL: 외부 서비스
        ANALYSIS: 분석 엔진
        DETECTION: 감지 (사람, 공, 코트)
        POSE: 포즈 추정
        BIOMECHANICS: 생체역학
        MOTION: 동작 분석
        GAME: 경기 분석
        REFEREE: AI 심판
        MODEL: AI 모델
        CONFIGURATION: 설정
        SYSTEM: 시스템
    """

    GENERAL = "general"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    EXTERNAL = "external"
    ANALYSIS = "analysis"
    DETECTION = "detection"
    POSE = "pose"
    BIOMECHANICS = "biomechanics"
    MOTION = "motion"
    GAME = "game"
    REFEREE = "referee"
    MODEL = "model"
    CONFIGURATION = "configuration"
    SYSTEM = "system"

    @classmethod
    def from_error_code(cls, error_code: ErrorCode) -> "TrackingCategory":
        """
        에러 코드에서 카테고리 추론.

        Args:
            error_code: 에러 코드

        Returns:
            추론된 TrackingCategory
        """
        code = error_code.code

        # 1xxx: 일반 에러
        if 1000 <= code < 2000:
            return cls.GENERAL

        # 2xxx: 인증/권한 에러
        if 2000 <= code < 3000:
            return cls.AUTHENTICATION

        # 3xxx: 입력 검증 에러
        if 3000 <= code < 4000:
            return cls.VALIDATION

        # 4xxx: 비즈니스 로직 에러
        if 4000 <= code < 5000:
            return cls.BUSINESS

        # 5xxx: 인프라 에러
        if 5000 <= code < 6000:
            return cls.INFRASTRUCTURE

        # 6xxx: 외부 서비스 에러
        if 6000 <= code < 7000:
            return cls.EXTERNAL

        # 7xxx: 분석 엔진 에러
        if 7000 <= code < 7200:
            return cls.ANALYSIS
        if 7200 <= code < 7300:
            return cls.DETECTION
        if 7300 <= code < 7400:
            return cls.POSE
        if 7400 <= code < 7500:
            return cls.BIOMECHANICS
        if 7500 <= code < 7600:
            return cls.MOTION
        if 7600 <= code < 7700:
            return cls.GAME
        if 7700 <= code < 8000:
            return cls.MODEL

        # 8xxx: AI 심판 에러
        if 8000 <= code < 9000:
            return cls.REFEREE

        # 9xxx: 시스템 에러
        if 9000 <= code < 9100:
            return cls.CONFIGURATION
        if code >= 9000:
            return cls.SYSTEM

        return cls.GENERAL


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class ErrorContext:
    """
    에러 발생 컨텍스트.

    에러가 발생한 환경과 관련 정보를 담습니다.

    Attributes:
        request_id: 요청 ID
        user_id: 사용자 ID
        session_id: 세션 ID
        analysis_id: 분석 ID
        video_id: 비디오 ID
        endpoint: API 엔드포인트
        method: HTTP 메서드
        ip_address: 클라이언트 IP
        user_agent: User-Agent
        extra: 추가 컨텍스트 정보
    """

    request_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    analysis_id: str | None = None
    video_id: str | None = None
    endpoint: str | None = None
    method: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        result = {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "video_id": self.video_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

        # None 값 제거
        result = {k: v for k, v in result.items() if v is not None}

        # extra 병합
        if self.extra:
            result["extra"] = self.extra

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorContext:
        """딕셔너리에서 생성."""
        extra = data.pop("extra", {})
        known_keys = {
            "request_id", "user_id", "session_id", "analysis_id",
            "video_id", "endpoint", "method", "ip_address", "user_agent"
        }

        # 알려진 키 분리
        known = {k: v for k, v in data.items() if k in known_keys}
        unknown = {k: v for k, v in data.items() if k not in known_keys}

        # extra에 unknown 병합
        extra.update(unknown)

        return cls(**known, extra=extra)


@dataclass
class ErrorRecord:
    """
    에러 기록.

    단일 에러 발생에 대한 상세 정보를 담습니다.

    Attributes:
        id: 에러 레코드 고유 ID
        error_hash: 에러 핑거프린트 (중복 감지용)
        exception_type: 예외 클래스명
        error_code: 에러 코드 (ErrorCode enum)
        error_name: 에러 코드명
        message: 에러 메시지
        severity: 심각도
        category: 에러 카테고리
        traceback: 스택 트레이스
        context: 에러 발생 컨텍스트
        occurred_at: 발생 시각
        is_retryable: 재시도 가능 여부
        is_critical: 심각 에러 여부
        tags: 태그 목록
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    error_hash: str = ""
    exception_type: str = ""
    error_code: ErrorCode | None = None
    error_name: str = ""
    message: str = ""
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: TrackingCategory = TrackingCategory.GENERAL
    traceback: str = ""
    context: ErrorContext = field(default_factory=ErrorContext)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_retryable: bool = False
    is_critical: bool = False
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 에러 해시 생성
        if not self.error_hash:
            self.error_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """에러 핑거프린트 해시 생성."""
        # 동일 에러 식별을 위한 정규화된 문자열
        fingerprint_parts = [
            self.exception_type,
            self.error_name,
            self.message[:100] if self.message else "",  # 메시지 앞 100자
            # 스택 트레이스에서 파일명과 라인번호만 추출
            self._normalize_traceback(),
        ]
        fingerprint = "|".join(fingerprint_parts)

        return hashlib.md5(fingerprint.encode()).hexdigest()[:16]

    def _normalize_traceback(self) -> str:
        """스택 트레이스 정규화 (변수값 제외)."""
        if not self.traceback:
            return ""

        # 파일명과 라인번호만 추출
        lines = []
        for line in self.traceback.split("\n"):
            if 'File "' in line:
                # File "path/to/file.py", line 42 형식
                lines.append(line.strip())

        return "|".join(lines[:5])  # 상위 5개만

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "id": self.id,
            "error_hash": self.error_hash,
            "exception_type": self.exception_type,
            "error_code": self.error_code.code if self.error_code else None,
            "error_name": self.error_name,
            "message": self.message,
            "severity": self.severity.name,
            "category": self.category.value,
            "traceback": self.traceback,
            "context": self.context.to_dict() if self.context else {},
            "occurred_at": self.occurred_at.isoformat(),
            "is_retryable": self.is_retryable,
            "is_critical": self.is_critical,
            "tags": self.tags,
        }

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        context: ErrorContext | dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
        tags: list[str] | None = None,
    ) -> ErrorRecord:
        """
        예외 객체에서 ErrorRecord 생성.

        Args:
            exc: 예외 객체
            context: 에러 컨텍스트
            severity: 심각도 (None이면 자동 추론)
            tags: 태그 목록

        Returns:
            ErrorRecord 인스턴스
        """
        # 컨텍스트 처리
        if context is None:
            error_context = ErrorContext()
        elif isinstance(context, dict):
            error_context = ErrorContext.from_dict(context)
        else:
            error_context = context

        # CourtViewException 처리
        if isinstance(exc, CourtViewException):
            error_code = exc.error_code
            error_name = exc.error_name
            message = exc.message

            # 컨텍스트 병합
            if exc.context:
                error_context.extra.update(exc.context)
            if exc.details:
                error_context.extra["details"] = exc.details
        else:
            error_code = ErrorCode.UNKNOWN_ERROR
            error_name = type(exc).__name__
            message = str(exc)

        # 심각도 결정
        if severity is None:
            severity = ErrorSeverity.from_exception(exc)

        # 카테고리 결정
        category = TrackingCategory.from_error_code(error_code)

        # 스택 트레이스
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        # 특수 플래그
        is_retryable = isinstance(exc, RetryableException)
        is_critical = isinstance(exc, CriticalException)

        return cls(
            exception_type=type(exc).__name__,
            error_code=error_code,
            error_name=error_name,
            message=message,
            severity=severity,
            category=category,
            traceback=tb,
            context=error_context,
            is_retryable=is_retryable,
            is_critical=is_critical,
            tags=tags or [],
        )


@dataclass
class ErrorSummary:
    """
    에러 요약.

    기간 내 에러 통계를 집계한 결과입니다.

    Attributes:
        period_start: 집계 시작 시각
        period_end: 집계 종료 시각
        total_count: 전체 에러 수
        unique_count: 고유 에러 수 (해시 기준)
        by_severity: 심각도별 카운트
        by_category: 카테고리별 카운트
        by_error_code: 에러 코드별 카운트
        top_errors: 가장 많이 발생한 에러 (해시, 카운트)
        error_rate: 에러 발생률 (분당)
    """

    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_count: int = 0
    unique_count: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_error_code: dict[str, int] = field(default_factory=dict)
    top_errors: list[tuple[str, int, str]] = field(default_factory=list)  # (hash, count, message)
    error_rate: float = 0.0  # 분당 에러 수

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_count": self.total_count,
            "unique_count": self.unique_count,
            "by_severity": self.by_severity,
            "by_category": self.by_category,
            "by_error_code": self.by_error_code,
            "top_errors": [
                {"hash": h, "count": c, "message": m}
                for h, c, m in self.top_errors
            ],
            "error_rate": round(self.error_rate, 2),
        }


@dataclass
class ErrorTrend:
    """
    에러 추세.

    시간대별 에러 발생 추세를 나타냅니다.

    Attributes:
        time_slots: 시간 슬롯 목록 (ISO 형식)
        counts: 각 슬롯별 에러 수
        slot_duration_minutes: 슬롯 간격 (분)
        trend_direction: 추세 방향 ("increasing", "decreasing", "stable")
        change_percentage: 이전 대비 변화율 (%)
    """

    time_slots: list[str] = field(default_factory=list)
    counts: list[int] = field(default_factory=list)
    slot_duration_minutes: int = 5
    trend_direction: str = "stable"
    change_percentage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "time_slots": self.time_slots,
            "counts": self.counts,
            "slot_duration_minutes": self.slot_duration_minutes,
            "trend_direction": self.trend_direction,
            "change_percentage": round(self.change_percentage, 2),
        }

    @classmethod
    def calculate_trend(
        cls,
        records: list[ErrorRecord],
        slot_minutes: int = 5,
        window_hours: int = 1,
    ) -> ErrorTrend:
        """
        에러 기록에서 추세 계산.

        Args:
            records: 에러 기록 목록
            slot_minutes: 슬롯 간격 (분)
            window_hours: 분석 윈도우 (시간)

        Returns:
            ErrorTrend 인스턴스
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)

        # 슬롯 생성
        slot_count = (window_hours * 60) // slot_minutes
        slots: list[datetime] = []
        counts: list[int] = []

        for i in range(slot_count):
            slot_start = window_start + timedelta(minutes=i * slot_minutes)
            slot_end = slot_start + timedelta(minutes=slot_minutes)
            slots.append(slot_start)

            # 해당 슬롯의 에러 수 카운트
            count = sum(
                1 for r in records
                if slot_start <= r.occurred_at < slot_end
            )
            counts.append(count)

        # 추세 계산
        total_errors = sum(counts)

        # 에러가 없거나 슬롯이 부족하면 안정 상태
        if len(counts) < 2 or total_errors == 0:
            trend_direction = "stable"
            change_percentage = 0.0
        else:
            # 전반부 vs 후반부 비교
            mid = len(counts) // 2
            first_half = sum(counts[:mid])
            second_half = sum(counts[mid:])

            # 전반부가 0이면 후반부에만 에러가 있는 것 (증가 추세)
            if first_half == 0:
                if second_half > 0:
                    trend_direction = "increasing"
                    change_percentage = 100.0
                else:
                    trend_direction = "stable"
                    change_percentage = 0.0
            else:
                change_percentage = ((second_half - first_half) / first_half) * 100

                if change_percentage > 10:
                    trend_direction = "increasing"
                elif change_percentage < -10:
                    trend_direction = "decreasing"
                else:
                    trend_direction = "stable"

        return cls(
            time_slots=[s.isoformat() for s in slots],
            counts=counts,
            slot_duration_minutes=slot_minutes,
            trend_direction=trend_direction,
            change_percentage=change_percentage,
        )


# ============================================================
# ErrorTracker 메인 클래스
# ============================================================
class ErrorTracker:
    """
    에러 추적기.

    시스템 전체의 에러를 추적, 집계하는 중앙 컴포넌트입니다.
    DI 컨테이너에 등록되어 주입받아 사용합니다.

    주요 기능:
        - 에러 기록 및 저장 (메모리 기반, 최대 개수 제한)
        - 에러 중복 감지 (해시 기반)
        - 에러 집계 및 통계
        - 시간대별 추세 분석
        - 로컬 로깅 기반 에러 알림
        - 스레드 안전 설계

    Attributes:
        config_loader: 설정 로더 (Direct Import)
        max_records: 최대 에러 보관 개수
        enabled: 활성화 여부

    Example:
        >>> tracker = ErrorTracker(config_loader)
        >>> tracker.track(exception, context={"analysis_id": "123"})
        >>> summary = tracker.get_summary(hours=24)
        >>> trend = tracker.get_trend(hours=1)
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        max_records: int = MAX_ERROR_RECORDS,
        enabled: bool = True,
    ) -> None:
        """
        ErrorTracker 초기화.

        Args:
            config_loader: 설정 로더 (None이면 싱글톤 사용)
            max_records: 최대 에러 보관 개수
            enabled: 활성화 여부
        """
        # 설정 로더
        self._config_loader = config_loader or ConfigLoader.get_instance()

        # 에러 저장소 (deque로 O(1) FIFO 구현)
        self._records: deque[ErrorRecord] = deque(maxlen=max_records)
        self._max_records = max_records

        # 에러 해시 -> 마지막 발생 시각 (중복 감지용)
        self._error_hashes: dict[str, datetime] = {}

        # 에러 해시 -> 발생 카운트 (집계용)
        self._error_counts: dict[str, int] = defaultdict(int)

        # 에러 해시 -> 마지막 메시지 (요약용)
        self._error_messages: dict[str, str] = {}

        # 스레드 락
        self._lock: threading.RLock = threading.RLock()

        # 활성화 여부
        self._enabled: bool = enabled

        logger.info(
            f"ErrorTracker 초기화 완료 "
            f"(max_records={max_records}, enabled={enabled})"
        )

    # --------------------------------------------------------
    # 에러 추적 메서드
    # --------------------------------------------------------
    def track(
        self,
        error: Exception | ErrorRecord,
        context: ErrorContext | dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
        tags: list[str] | None = None,
    ) -> ErrorRecord:
        """
        에러 추적.

        예외 또는 ErrorRecord를 추적하고 저장합니다.

        Args:
            error: 예외 객체 또는 ErrorRecord
            context: 에러 컨텍스트
            severity: 심각도 (None이면 자동 추론)
            tags: 태그 목록

        Returns:
            저장된 ErrorRecord

        Example:
            >>> tracker.track(exception, context={"analysis_id": "123"})
            >>> tracker.track(exception, severity=ErrorSeverity.CRITICAL)
        """
        if not self._enabled:
            # 비활성화 상태에서도 레코드는 생성
            if isinstance(error, ErrorRecord):
                return error
            return ErrorRecord.from_exception(error, context, severity, tags)

        with self._lock:
            # ErrorRecord 생성
            if isinstance(error, ErrorRecord):
                record = error
            else:
                record = ErrorRecord.from_exception(error, context, severity, tags)

            # 저장
            self._store_record(record)

            # 로깅
            self._log_error(record)

            return record

    def track_exception(
        self,
        exc_type: type[Exception],
        exc_value: Exception,
        exc_tb: Any,
        context: dict[str, Any] | None = None,
    ) -> ErrorRecord:
        """
        sys.exc_info() 형식의 예외 추적.

        예외 핸들러에서 사용하기 편리한 인터페이스입니다.

        Args:
            exc_type: 예외 타입
            exc_value: 예외 값
            exc_tb: 트레이스백
            context: 컨텍스트

        Returns:
            ErrorRecord
        """
        return self.track(exc_value, context=context)

    def _store_record(self, record: ErrorRecord) -> None:
        """에러 레코드 저장.

        deque(maxlen=N)을 사용하여 O(1) FIFO 구현.
        maxlen 초과 시 자동으로 왼쪽(가장 오래된) 요소가 제거됩니다.
        """
        # deque가 가득 찼을 때 제거될 레코드의 해시 카운트 정리
        if len(self._records) >= self._max_records:
            old_record = self._records[0]  # 제거될 레코드 (O(1) 접근)
            # 해시 카운트 정리
            if old_record.error_hash in self._error_counts:
                self._error_counts[old_record.error_hash] -= 1
                if self._error_counts[old_record.error_hash] <= 0:
                    del self._error_counts[old_record.error_hash]
                    self._error_hashes.pop(old_record.error_hash, None)
                    self._error_messages.pop(old_record.error_hash, None)

        # 저장 (O(1) - deque의 append는 maxlen 초과 시 자동 FIFO)
        self._records.append(record)

        # 해시 업데이트
        self._error_hashes[record.error_hash] = record.occurred_at
        self._error_counts[record.error_hash] += 1
        self._error_messages[record.error_hash] = record.message[:100]

        # 해시 개수 제한
        if len(self._error_hashes) > MAX_ERROR_HASHES:
            # 가장 오래된 해시들을 일괄 제거 (10% 정리)
            cleanup_count = MAX_ERROR_HASHES // 10
            oldest_hashes = sorted(
                self._error_hashes.keys(),
                key=lambda h: self._error_hashes[h]
            )[:cleanup_count]

            for old_hash in oldest_hashes:
                del self._error_hashes[old_hash]
                self._error_counts.pop(old_hash, None)
                self._error_messages.pop(old_hash, None)

    def _log_error(self, record: ErrorRecord) -> None:
        """에러 로깅."""
        log_message = (
            f"[{record.severity.name}] {record.exception_type}: {record.message}"
        )

        # 컨텍스트 추가
        if record.context.request_id:
            log_message += f" (request_id={record.context.request_id})"

        # 심각도에 따른 로그 레벨
        if record.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif record.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif record.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif record.severity == ErrorSeverity.INFO:
            logger.info(log_message)
        else:
            logger.debug(log_message)

    # --------------------------------------------------------
    # 집계 및 통계 메서드
    # --------------------------------------------------------
    def get_summary(
        self,
        hours: int = 24,
        category: TrackingCategory | None = None,
        min_severity: ErrorSeverity = ErrorSeverity.DEBUG,
    ) -> ErrorSummary:
        """
        에러 요약 조회.

        Args:
            hours: 집계 기간 (시간)
            category: 필터링할 카테고리
            min_severity: 최소 심각도

        Returns:
            ErrorSummary 인스턴스
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=hours)

            # 필터링
            filtered = [
                r for r in self._records
                if r.occurred_at >= period_start
                and r.severity >= min_severity
                and (category is None or r.category == category)
            ]

            # 심각도별 카운트
            by_severity: dict[str, int] = defaultdict(int)
            for r in filtered:
                by_severity[r.severity.name] += 1

            # 카테고리별 카운트
            by_category: dict[str, int] = defaultdict(int)
            for r in filtered:
                by_category[r.category.value] += 1

            # 에러 코드별 카운트
            by_error_code: dict[str, int] = defaultdict(int)
            for r in filtered:
                if r.error_code:
                    by_error_code[r.error_name] += 1

            # 고유 에러 수
            unique_hashes = set(r.error_hash for r in filtered)

            # Top 에러
            hash_counts: dict[str, int] = defaultdict(int)
            hash_messages: dict[str, str] = {}
            for r in filtered:
                hash_counts[r.error_hash] += 1
                hash_messages[r.error_hash] = r.message[:100]

            top_errors = sorted(
                [(h, c, hash_messages[h]) for h, c in hash_counts.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:10]

            # 에러율 (분당)
            duration_minutes = max(hours * 60, 1)
            error_rate = len(filtered) / duration_minutes

            return ErrorSummary(
                period_start=period_start,
                period_end=now,
                total_count=len(filtered),
                unique_count=len(unique_hashes),
                by_severity=dict(by_severity),
                by_category=dict(by_category),
                by_error_code=dict(by_error_code),
                top_errors=top_errors,
                error_rate=error_rate,
            )

    def get_trend(
        self,
        hours: int = 1,
        slot_minutes: int = 5,
        category: TrackingCategory | None = None,
    ) -> ErrorTrend:
        """
        에러 추세 조회.

        Args:
            hours: 분석 기간 (시간)
            slot_minutes: 슬롯 간격 (분)
            category: 필터링할 카테고리

        Returns:
            ErrorTrend 인스턴스
        """
        with self._lock:
            window_start = datetime.now(timezone.utc) - timedelta(hours=hours)

            # 필터링
            filtered = [
                r for r in self._records
                if r.occurred_at >= window_start
                and (category is None or r.category == category)
            ]

            return ErrorTrend.calculate_trend(filtered, slot_minutes, hours)

    def get_records(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: ErrorSeverity | None = None,
        category: TrackingCategory | None = None,
        since: datetime | None = None,
    ) -> list[ErrorRecord]:
        """
        에러 기록 조회.

        Args:
            limit: 최대 개수
            offset: 시작 위치
            severity: 필터링할 심각도
            category: 필터링할 카테고리
            since: 이 시각 이후

        Returns:
            ErrorRecord 목록
        """
        with self._lock:
            # deque를 list로 변환하여 정렬 가능하게 함
            filtered = list(self._records)

            # 필터링
            if severity:
                filtered = [r for r in filtered if r.severity == severity]
            if category:
                filtered = [r for r in filtered if r.category == category]
            if since:
                filtered = [r for r in filtered if r.occurred_at >= since]

            # 최신순 정렬
            filtered.sort(key=lambda r: r.occurred_at, reverse=True)

            # 페이징
            return filtered[offset:offset + limit]

    def get_record_by_id(self, record_id: str) -> ErrorRecord | None:
        """
        ID로 에러 기록 조회.

        Args:
            record_id: 에러 레코드 ID

        Returns:
            ErrorRecord 또는 None
        """
        with self._lock:
            for record in self._records:
                if record.id == record_id:
                    return record
            return None

    def get_records_by_hash(self, error_hash: str) -> list[ErrorRecord]:
        """
        해시로 에러 기록 조회.

        Args:
            error_hash: 에러 해시

        Returns:
            ErrorRecord 목록
        """
        with self._lock:
            return [r for r in self._records if r.error_hash == error_hash]

    # --------------------------------------------------------
    # 유틸리티 메서드
    # --------------------------------------------------------
    def clear(self) -> None:
        """모든 에러 기록 삭제."""
        with self._lock:
            self._records.clear()
            self._error_hashes.clear()
            self._error_counts.clear()
            self._error_messages.clear()
            logger.info("모든 에러 기록 삭제됨")

    def get_count(
        self,
        severity: ErrorSeverity | None = None,
        category: TrackingCategory | None = None,
        since: datetime | None = None,
    ) -> int:
        """
        에러 개수 조회.

        Args:
            severity: 필터링할 심각도
            category: 필터링할 카테고리
            since: 이 시각 이후

        Returns:
            에러 개수
        """
        with self._lock:
            count = 0
            for record in self._records:
                if severity and record.severity != severity:
                    continue
                if category and record.category != category:
                    continue
                if since and record.occurred_at < since:
                    continue
                count += 1
            return count

    def get_status(self) -> dict[str, Any]:
        """
        추적기 상태 조회.

        Returns:
            상태 딕셔너리
        """
        with self._lock:
            return {
                "enabled": self._enabled,
                "total_records": len(self._records),
                "unique_errors": len(self._error_hashes),
                "max_records": self._max_records,
            }

    @property
    def enabled(self) -> bool:
        """활성화 여부."""
        with self._lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """활성화 여부 설정 (스레드 안전)."""
        with self._lock:
            old_value = self._enabled
            self._enabled = value
            if old_value != value:
                logger.info(f"ErrorTracker 활성화 상태 변경: {old_value} -> {value}")


# ============================================================
# 싱글톤 인스턴스 관리
# ============================================================
_tracker_instance: ErrorTracker | None = None
_tracker_lock: threading.Lock = threading.Lock()


def _get_tracker() -> ErrorTracker:
    """전역 ErrorTracker 인스턴스 반환."""
    global _tracker_instance

    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = ErrorTracker()

    return _tracker_instance


def _reset_tracker() -> None:
    """전역 ErrorTracker 인스턴스 리셋 (테스트용)."""
    global _tracker_instance

    with _tracker_lock:
        _tracker_instance = None


# ============================================================
# 헬퍼 함수
# ============================================================
def track_error(
    error: Exception | ErrorRecord,
    context: ErrorContext | dict[str, Any] | None = None,
    severity: ErrorSeverity | None = None,
    tags: list[str] | None = None,
) -> ErrorRecord:
    """
    에러 추적 헬퍼 함수.

    전역 ErrorTracker를 사용하여 에러를 추적합니다.

    Args:
        error: 예외 객체 또는 ErrorRecord
        context: 에러 컨텍스트
        severity: 심각도
        tags: 태그 목록

    Returns:
        저장된 ErrorRecord

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     track_error(e, context={"user_id": "123"})
    """
    tracker = _get_tracker()
    return tracker.track(error, context, severity, tags)


def get_error_summary(
    hours: int = 24,
    category: TrackingCategory | None = None,
    min_severity: ErrorSeverity = ErrorSeverity.DEBUG,
) -> ErrorSummary:
    """
    에러 요약 조회 헬퍼 함수.

    전역 ErrorTracker의 에러 요약을 조회합니다.

    Args:
        hours: 집계 기간 (시간)
        category: 필터링할 카테고리
        min_severity: 최소 심각도

    Returns:
        ErrorSummary 인스턴스

    Example:
        >>> summary = get_error_summary(hours=24)
        >>> print(f"지난 24시간 에러: {summary.total_count}개")
    """
    tracker = _get_tracker()
    return tracker.get_summary(hours, category, min_severity)


# ============================================================
# 모듈 내보내기
# ============================================================
# ErrorCategory는 shared.constants.error_codes에서 re-export (고수준 분류)
# TrackingCategory는 에러 추적용 세분화 카테고리 (16개 상세 분류)
__all__ = [
    # Enum
    "ErrorSeverity",
    "ErrorCategory",       # shared에서 re-export (고수준 분류)
    "TrackingCategory",    # 에러 추적용 세분화 카테고리
    # 상수
    "MAX_ERROR_RECORDS",
    "MAX_ERROR_HASHES",
    "AGGREGATION_WINDOW_SIZE",
    # 데이터 클래스
    "ErrorRecord",
    "ErrorSummary",
    "ErrorTrend",
    "ErrorContext",
    # 메인 클래스
    "ErrorTracker",
    # 함수
    "track_error",
    "get_error_summary",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
