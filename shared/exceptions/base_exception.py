# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: base_exception.py
설명: 기본 예외 클래스 정의 - 모든 커스텀 예외의 기반 클래스
      - CourtViewException: 기본 예외 (에러 코드, 컨텍스트, 체이닝 지원)
      - RetryableException: 재시도 가능 예외 (retry_after, max_retries)
      - NonRetryableException: 재시도 불가 예외
      - CriticalException: 심각한 시스템 예외 (alert_required, severity)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-04
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import traceback
from typing import Any
from datetime import datetime, timezone

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.error_codes import (
    CRITICAL_SEVERITY_DEFAULT,
    CRITICAL_SEVERITY_MAX,
    CRITICAL_SEVERITY_MIN,
    ErrorCode,
)


__all__ = [
    "CourtViewException",
    "RetryableException",
    "NonRetryableException",
    "CriticalException",
]


class CourtViewException(Exception):
    """
    COURTVIEW 기본 예외 클래스.

    모든 커스텀 예외의 기반이 되는 클래스입니다.
    에러 코드, 상세 정보, 컨텍스트를 포함하여 구조화된 에러 정보를 제공합니다.

    Attributes:
        error_code: ErrorCode enum 값
        message: 에러 메시지 (한글)
        details: 추가 상세 정보 딕셔너리
        context: 에러 발생 컨텍스트 정보
        cause: 원인이 된 예외 (chained exception)
        timestamp: 에러 발생 시간 (UTC)

    Example:
        >>> try:
        ...     raise CourtViewException(
        ...         ErrorCode.ANALYSIS_ERROR,
        ...         "분석 중 오류가 발생했습니다",
        ...         details={"video_id": "abc123"}
        ...     )
        ... except CourtViewException as e:
        ...     print(e.to_dict())
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        예외 초기화.

        Args:
            error_code: 에러 코드 (ErrorCode enum)
            message: 에러 메시지 (None이면 error_code의 기본 메시지 사용)
            details: 추가 상세 정보
            context: 에러 발생 컨텍스트 (요청 ID, 사용자 ID 등)
            cause: 원인이 된 예외
        """
        self.error_code = error_code
        self.message = message or error_code.message
        self.details = details or {}
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc)

        # 스택 트레이스 저장
        self._traceback: str | None = None
        if cause:
            self._traceback = "".join(traceback.format_exception(
                type(cause), cause, cause.__traceback__
            ))

        # 부모 클래스 초기화
        super().__init__(self.message)

        # Chained exception 설정
        if cause:
            self.__cause__ = cause

    @property
    def code(self) -> int:
        """에러 코드 번호 반환."""
        return self.error_code.code

    @property
    def http_status(self) -> int:
        """HTTP 상태 코드 반환."""
        return self.error_code.http_status

    @property
    def error_name(self) -> str:
        """에러 코드 이름 반환."""
        return self.error_code.name

    def to_dict(self, include_traceback: bool = False) -> dict[str, Any]:
        """
        예외 정보를 딕셔너리로 변환.

        Args:
            include_traceback: 스택 트레이스 포함 여부

        Returns:
            예외 정보 딕셔너리
        """
        result: dict[str, Any] = {
            "error": {
                "code": self.code,
                "name": self.error_name,
                "message": self.message,
                "http_status": self.http_status,
            },
            "timestamp": self.timestamp.isoformat(),
        }

        if self.details:
            result["details"] = self.details

        if self.context:
            result["context"] = self.context

        if include_traceback and self._traceback:
            result["traceback"] = self._traceback

        if self.cause:
            result["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }

        return result

    def to_response_dict(self) -> dict[str, Any]:
        """
        API 응답용 딕셔너리로 변환.

        트레이스백 등 민감한 정보를 제외합니다.

        Returns:
            API 응답용 딕셔너리
        """
        return {
            "success": False,
            "error": {
                "code": self.code,
                "name": self.error_name,
                "message": self.message,
            },
            "details": self.details if self.details else None,
        }

    def with_context(self, **kwargs: Any) -> "CourtViewException":
        """
        컨텍스트 정보 추가.

        Args:
            **kwargs: 추가할 컨텍스트 키-값 쌍

        Returns:
            self (메서드 체이닝용)
        """
        self.context.update(kwargs)
        return self

    def with_details(self, **kwargs: Any) -> "CourtViewException":
        """
        상세 정보 추가.

        Args:
            **kwargs: 추가할 상세 정보 키-값 쌍

        Returns:
            self (메서드 체이닝용)
        """
        self.details.update(kwargs)
        return self

    def __str__(self) -> str:
        """문자열 표현."""
        return f"[{self.code}] {self.error_name}: {self.message}"

    def __repr__(self) -> str:
        """객체 표현."""
        return (
            f"{self.__class__.__name__}("
            f"error_code={self.error_code!r}, "
            f"message={self.message!r}, "
            f"details={self.details!r})"
        )


class RetryableException(CourtViewException):
    """
    재시도 가능한 예외.

    일시적인 오류로 재시도하면 성공할 수 있는 경우에 사용합니다.

    Attributes:
        retry_after: 재시도까지 대기 시간 (초)
        max_retries: 최대 재시도 횟수
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retry_after: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        """
        재시도 가능 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            details: 상세 정보
            context: 컨텍스트
            cause: 원인 예외
            retry_after: 재시도까지 대기 시간 (초)
            max_retries: 최대 재시도 횟수
        """
        super().__init__(error_code, message, details, context, cause)
        self.retry_after = retry_after
        self.max_retries = max_retries

    def to_dict(self, include_traceback: bool = False) -> dict[str, Any]:
        """딕셔너리로 변환."""
        result = super().to_dict(include_traceback)
        result["retry"] = {
            "retry_after": self.retry_after,
            "max_retries": self.max_retries,
        }
        return result


class NonRetryableException(CourtViewException):
    """
    재시도 불가능한 예외.

    재시도해도 동일한 결과가 나오는 영구적인 오류에 사용합니다.
    입력 오류, 권한 오류 등이 해당됩니다.
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """재시도 불가 예외 초기화."""
        super().__init__(error_code, message, details, context, cause)

    def to_dict(self, include_traceback: bool = False) -> dict[str, Any]:
        """딕셔너리로 변환."""
        result = super().to_dict(include_traceback)
        result["retryable"] = False
        return result


class CriticalException(CourtViewException):
    """
    심각한 시스템 예외.

    시스템 운영에 심각한 영향을 미치는 오류에 사용합니다.
    알림 발송 등 즉각적인 대응이 필요합니다.

    Attributes:
        alert_required: 알림 발송 필요 여부
        severity: 심각도 레벨 (1-5, 5가 가장 심각)
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
        alert_required: bool = True,
        severity: int = CRITICAL_SEVERITY_DEFAULT,
    ) -> None:
        """
        심각한 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            details: 상세 정보
            context: 컨텍스트
            cause: 원인 예외
            alert_required: 알림 발송 필요 여부
            severity: 심각도 (CRITICAL_SEVERITY_MIN ~ CRITICAL_SEVERITY_MAX)
        """
        super().__init__(error_code, message, details, context, cause)
        self.alert_required = alert_required
        self.severity = min(
            max(severity, CRITICAL_SEVERITY_MIN), CRITICAL_SEVERITY_MAX
        )  # 허용 범위로 클램핑

    def to_dict(self, include_traceback: bool = False) -> dict[str, Any]:
        """딕셔너리로 변환."""
        result = super().to_dict(include_traceback)
        result["critical"] = {
            "alert_required": self.alert_required,
            "severity": self.severity,
        }
        return result


# =============================================================================
# 모듈 버전 정보
# =============================================================================
__version__ = "1.0.0"
