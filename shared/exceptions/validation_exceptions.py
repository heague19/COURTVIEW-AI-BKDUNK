# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: validation_exceptions.py
설명: 검증 관련 예외 클래스 정의 - 입력 검증, 설정 검증, 스키마 검증 등
      - ValidationException: 검증 기본 예외 (민감 필드 마스킹)
      - URLValidationException: URL 검증 (SSRF 방지)
      - SecurityException: 보안 예외 (SSRF, DNS 리바인딩 감지)
      - FormatValidationException: 포맷 검증 (코덱, FPS, 비트레이트)
      - ResolutionException: 해상도 검증
      - ConfigurationException: 설정 예외
      - AuthenticationException/AuthorizationException: 인증/권한
      - RateLimitException: 속도 제한 (Retryable)
      - DataQualityException: 데이터 품질 검사
      - RuleSetException: 규칙 세트 검증 (v3.0.0)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-04
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
from typing import Any

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import NonRetryableException, RetryableException


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 기본 유효성 검사 예외
    "ValidationException",
    "InvalidRequestException",
    "InputValidationException",
    # 필드 유효성 검사 예외
    "MissingFieldException",
    "InvalidFieldTypeException",
    "InvalidFieldValueException",
    # 값 범위/길이 예외
    "ValueOutOfRangeException",
    "StringLengthException",
    # 데이터 형식 예외
    "InvalidEnumValueException",
    "InvalidJsonFormatException",
    "InvalidDateFormatException",
    # URL 유효성 검사 예외
    "URLValidationException",
    # 보안 예외
    "SecurityException",
    # 파일 포맷 예외
    "FormatDetectionException",
    "UnsupportedFormatException",
    "FormatValidationException",
    "ResolutionException",
    # 설정 예외
    "ConfigurationException",
    "ConfigurationNotFoundException",
    "ConfigurationLoadException",
    "ConfigurationParseException",
    "ConfigurationValidationException",
    # 스키마 유효성 검사 예외
    "SchemaValidationException",
    # 인증/권한 예외
    "AuthenticationException",
    "AuthorizationException",
    # 속도 제한 예외
    "RateLimitException",
    # 데이터 품질 예외
    "DataQualityException",
    "LowQualityException",
    # 규칙 세트 예외 (v3.0.0)
    "RuleSetNotFoundException",
    "RuleSetValidationException",
    "RuleSetVersionMismatchException",
]


class ValidationException(NonRetryableException):
    """
    검증 관련 기본 예외.

    모든 입력 검증 실패에 대한 기반 클래스입니다.
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        message: str | None = None,
        field_name: str | None = None,
        field_value: Any | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        검증 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            field_name: 문제가 된 필드명
            field_value: 문제가 된 필드 값
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if field_name:
            combined_details["field_name"] = field_name
        if field_value is not None:
            # 민감한 값은 마스킹
            if any(keyword in str(field_name).lower() for keyword in ["password", "secret", "key", "token"]):
                combined_details["field_value"] = "***MASKED***"
            else:
                combined_details["field_value"] = field_value

        super().__init__(error_code, message, combined_details, cause=cause)
        self.field_name = field_name
        self.field_value = field_value


class InvalidRequestException(ValidationException):
    """잘못된 요청 예외."""

    def __init__(
        self,
        message: str = "잘못된 요청입니다",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """잘못된 요청 예외 초기화."""
        super().__init__(
            ErrorCode.INVALID_REQUEST,
            message,
            details=details,
            cause=cause,
        )


class MissingFieldException(ValidationException):
    """필수 필드 누락 예외."""

    def __init__(
        self,
        field_name: str,
        parent_field: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        필수 필드 누락 예외 초기화.

        Args:
            field_name: 누락된 필드명
            parent_field: 부모 필드명 (중첩 구조인 경우)
            cause: 원인 예외
        """
        full_field = f"{parent_field}.{field_name}" if parent_field else field_name
        message = f"필수 필드가 누락되었습니다: {full_field}"

        super().__init__(
            ErrorCode.MISSING_REQUIRED_FIELD,
            message,
            field_name=full_field,
            details={"parent_field": parent_field} if parent_field else None,
            cause=cause,
        )


class InvalidFieldTypeException(ValidationException):
    """필드 타입 불일치 예외."""

    def __init__(
        self,
        field_name: str,
        expected_type: str | type,
        received_type: str | type,
        received_value: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        필드 타입 불일치 예외 초기화.

        Args:
            field_name: 필드명
            expected_type: 기대하는 타입
            received_type: 실제 수신된 타입
            received_value: 수신된 값
            cause: 원인 예외
        """
        expected_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
        received_name = received_type.__name__ if isinstance(received_type, type) else str(received_type)

        message = f"필드 타입이 올바르지 않습니다: {field_name} (기대: {expected_name}, 수신: {received_name})"

        super().__init__(
            ErrorCode.INVALID_FIELD_TYPE,
            message,
            field_name=field_name,
            field_value=received_value,
            details={
                "expected_type": expected_name,
                "received_type": received_name,
            },
            cause=cause,
        )


class InvalidFieldValueException(ValidationException):
    """필드 값 유효하지 않음 예외."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        reason: str,
        allowed_values: list[Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        필드 값 예외 초기화.

        Args:
            field_name: 필드명
            value: 수신된 값
            reason: 유효하지 않은 이유
            allowed_values: 허용되는 값 목록 (있는 경우)
            cause: 원인 예외
        """
        message = f"필드 값이 유효하지 않습니다: {field_name}. {reason}"

        details: dict[str, Any] = {"reason": reason}
        if allowed_values:
            details["allowed_values"] = allowed_values

        super().__init__(
            ErrorCode.INVALID_FIELD_VALUE,
            message,
            field_name=field_name,
            field_value=value,
            details=details,
            cause=cause,
        )


class ValueOutOfRangeException(ValidationException):
    """값 범위 초과 예외."""

    def __init__(
        self,
        field_name: str,
        value: int | float,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        값 범위 초과 예외 초기화.

        Args:
            field_name: 필드명
            value: 수신된 값
            min_value: 최소값
            max_value: 최대값
            cause: 원인 예외
        """
        if min_value is not None and max_value is not None:
            message = f"{field_name} 값이 허용 범위({min_value}~{max_value})를 벗어났습니다: {value}"
        elif min_value is not None:
            message = f"{field_name} 값이 최소값({min_value})보다 작습니다: {value}"
        elif max_value is not None:
            message = f"{field_name} 값이 최대값({max_value})보다 큽니다: {value}"
        else:
            message = f"{field_name} 값이 허용 범위를 벗어났습니다: {value}"

        super().__init__(
            ErrorCode.VALUE_OUT_OF_RANGE,
            message,
            field_name=field_name,
            field_value=value,
            details={
                "min_value": min_value,
                "max_value": max_value,
            },
            cause=cause,
        )


class StringLengthException(ValidationException):
    """문자열 길이 예외."""

    def __init__(
        self,
        field_name: str,
        actual_length: int,
        min_length: int | None = None,
        max_length: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        문자열 길이 예외 초기화.

        Args:
            field_name: 필드명
            actual_length: 실제 길이
            min_length: 최소 길이
            max_length: 최대 길이
            cause: 원인 예외
        """
        if min_length is not None and actual_length < min_length:
            message = f"{field_name} 길이가 너무 짧습니다: {actual_length}자 (최소: {min_length}자)"
            error_code = ErrorCode.STRING_TOO_SHORT
        elif max_length is not None and actual_length > max_length:
            message = f"{field_name} 길이가 너무 깁니다: {actual_length}자 (최대: {max_length}자)"
            error_code = ErrorCode.STRING_TOO_LONG
        else:
            message = f"{field_name} 길이가 유효하지 않습니다: {actual_length}자"
            error_code = ErrorCode.VALIDATION_ERROR

        super().__init__(
            error_code,
            message,
            field_name=field_name,
            details={
                "actual_length": actual_length,
                "min_length": min_length,
                "max_length": max_length,
            },
            cause=cause,
        )


class InvalidEnumValueException(ValidationException):
    """유효하지 않은 열거형 값 예외."""

    def __init__(
        self,
        field_name: str,
        value: str,
        allowed_values: list[str],
        cause: Exception | None = None,
    ) -> None:
        """
        열거형 값 예외 초기화.

        Args:
            field_name: 필드명
            value: 수신된 값
            allowed_values: 허용되는 값 목록
            cause: 원인 예외
        """
        allowed_str = ", ".join(allowed_values[:10])  # 처음 10개만 표시
        if len(allowed_values) > 10:
            allowed_str += f" 외 {len(allowed_values) - 10}개"

        message = f"유효하지 않은 {field_name} 값입니다: {value}. 허용 값: {allowed_str}"

        super().__init__(
            ErrorCode.INVALID_ENUM_VALUE,
            message,
            field_name=field_name,
            field_value=value,
            details={"allowed_values": allowed_values},
            cause=cause,
        )


class InvalidJsonFormatException(ValidationException):
    """JSON 형식 오류 예외."""

    def __init__(
        self,
        message: str = "JSON 형식이 올바르지 않습니다",
        line: int | None = None,
        column: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        JSON 형식 예외 초기화.

        Args:
            message: 에러 메시지
            line: 오류 발생 라인
            column: 오류 발생 컬럼
            cause: 원인 예외
        """
        details: dict[str, Any] = {}
        if line is not None:
            details["line"] = line
        if column is not None:
            details["column"] = column

        super().__init__(
            ErrorCode.INVALID_JSON_FORMAT,
            message,
            details=details if details else None,
            cause=cause,
        )


class InvalidDateFormatException(ValidationException):
    """날짜 형식 오류 예외."""

    def __init__(
        self,
        field_name: str,
        value: str,
        expected_format: str = "YYYY-MM-DD",
        cause: Exception | None = None,
    ) -> None:
        """
        날짜 형식 예외 초기화.

        Args:
            field_name: 필드명
            value: 수신된 값
            expected_format: 기대하는 형식
            cause: 원인 예외
        """
        message = f"날짜 형식이 올바르지 않습니다: {field_name}. 기대 형식: {expected_format}"

        super().__init__(
            ErrorCode.INVALID_DATE_FORMAT,
            message,
            field_name=field_name,
            field_value=value,
            details={"expected_format": expected_format},
            cause=cause,
        )


# =============================================================================
# URL 검증 예외
# =============================================================================

class URLValidationException(ValidationException):
    """
    URL 검증 예외.

    URL 형식, 스킴, 호스트 등의 검증 실패 시 발생하는 예외입니다.
    SSRF 방지 및 보안 검사에서도 활용됩니다.

    Attributes:
        url: 검증에 실패한 URL
        scheme: URL 스킴
        host: URL 호스트
        reason: 검증 실패 사유
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.URL_VALIDATION_ERROR,
        message: str | None = None,
        url: str | None = None,
        scheme: str | None = None,
        host: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        URL 검증 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            url: 검증 실패 URL (민감 정보 제외)
            scheme: URL 스킴
            host: URL 호스트
            reason: 검증 실패 사유
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if url:
            # URL에서 민감한 정보 (쿼리 파라미터, 인증 정보) 제거
            combined_details["url"] = self._sanitize_url(url)
        if scheme:
            combined_details["scheme"] = scheme
        if host:
            combined_details["host"] = host
        if reason:
            combined_details["reason"] = reason

        super().__init__(
            error_code,
            message,
            details=combined_details,
            cause=cause,
        )
        self.url = url
        self.scheme = scheme
        self.host = host
        self.reason = reason

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """URL에서 민감한 정보 제거."""
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(url)
            # 사용자 정보 및 쿼리 파라미터 제거
            sanitized = urlunparse((
                parsed.scheme,
                parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc,
                parsed.path,
                "",  # params
                "",  # query (제거)
                "",  # fragment (제거)
            ))
            return sanitized
        except Exception:
            return "<invalid-url>"

    @classmethod
    def invalid_format(
        cls,
        url: str,
        reason: str | None = None,
    ) -> "URLValidationException":
        """
        유효하지 않은 URL 형식 예외 생성.

        Args:
            url: 문제가 된 URL
            reason: 추가 사유

        Returns:
            URLValidationException 인스턴스
        """
        msg = "유효하지 않은 URL 형식입니다"
        if reason:
            msg += f": {reason}"

        return cls(
            ErrorCode.URL_INVALID_FORMAT,
            msg,
            url=url,
            reason=reason or "invalid_format",
        )

    @classmethod
    def invalid_scheme(
        cls,
        url: str,
        scheme: str,
        allowed_schemes: list[str] | None = None,
    ) -> "URLValidationException":
        """
        허용되지 않은 스킴 예외 생성.

        Args:
            url: 문제가 된 URL
            scheme: 사용된 스킴
            allowed_schemes: 허용된 스킴 목록

        Returns:
            URLValidationException 인스턴스
        """
        msg = f"허용되지 않은 URL 스킴입니다: {scheme}"
        if allowed_schemes:
            msg += f" (허용: {', '.join(allowed_schemes)})"

        details: dict[str, Any] = {}
        if allowed_schemes:
            details["allowed_schemes"] = allowed_schemes

        return cls(
            ErrorCode.URL_INVALID_SCHEME,
            msg,
            url=url,
            scheme=scheme,
            reason="invalid_scheme",
            details=details,
        )

    @classmethod
    def blocked_host(
        cls,
        url: str,
        host: str,
        reason: str | None = None,
    ) -> "URLValidationException":
        """
        차단된 호스트 예외 생성.

        Args:
            url: 문제가 된 URL
            host: 차단된 호스트
            reason: 차단 사유

        Returns:
            URLValidationException 인스턴스
        """
        msg = f"차단된 호스트입니다: {host}"
        if reason:
            msg += f" ({reason})"

        return cls(
            ErrorCode.URL_BLOCKED_HOST,
            msg,
            url=url,
            host=host,
            reason=reason or "blocked_host",
        )

    @classmethod
    def private_ip(
        cls,
        url: str,
        ip_address: str,
    ) -> "URLValidationException":
        """
        내부 IP 주소 접근 예외 생성.

        Args:
            url: 문제가 된 URL
            ip_address: 감지된 내부 IP

        Returns:
            URLValidationException 인스턴스
        """
        return cls(
            ErrorCode.URL_PRIVATE_IP,
            f"내부 IP 주소에 대한 접근이 차단되었습니다: {ip_address}",
            url=url,
            host=ip_address,
            reason="private_ip",
        )

    @classmethod
    def too_long(
        cls,
        url: str,
        length: int,
        max_length: int,
    ) -> "URLValidationException":
        """
        URL 길이 초과 예외 생성.

        Args:
            url: 문제가 된 URL
            length: 실제 길이
            max_length: 최대 허용 길이

        Returns:
            URLValidationException 인스턴스
        """
        return cls(
            ErrorCode.URL_TOO_LONG,
            f"URL 길이가 너무 깁니다: {length}자 (최대: {max_length}자)",
            url=url,
            reason="too_long",
            details={
                "length": length,
                "max_length": max_length,
            },
        )


class SecurityException(NonRetryableException):
    """
    보안 관련 예외.

    SSRF, DNS 리바인딩 등의 보안 위협이 감지되었을 때 발생하는 예외입니다.

    Attributes:
        threat_type: 위협 유형 (ssrf, dns_rebinding 등)
        source: 위협 소스 (URL, IP 등)
        target: 공격 대상
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.SECURITY_ERROR,
        message: str | None = None,
        threat_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        보안 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            threat_type: 위협 유형
            source: 위협 소스
            target: 공격 대상
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if threat_type:
            combined_details["threat_type"] = threat_type
        if source:
            combined_details["source"] = source
        if target:
            combined_details["target"] = target

        super().__init__(
            error_code,
            message,
            combined_details,
            cause=cause,
        )
        self.threat_type = threat_type
        self.source = source
        self.target = target

    @classmethod
    def ssrf_detected(
        cls,
        url: str,
        target_ip: str | None = None,
        reason: str | None = None,
    ) -> "SecurityException":
        """
        SSRF 공격 감지 예외 생성.

        Args:
            url: 공격에 사용된 URL
            target_ip: 대상 IP 주소
            reason: 감지 사유

        Returns:
            SecurityException 인스턴스
        """
        msg = "SSRF 공격이 감지되었습니다"
        if reason:
            msg += f": {reason}"

        details: dict[str, Any] = {"url": url}
        if target_ip:
            details["target_ip"] = target_ip

        return cls(
            ErrorCode.SSRF_DETECTED,
            msg,
            threat_type="ssrf",
            source=url,
            target=target_ip,
            details=details,
        )

    @classmethod
    def dns_rebinding_detected(
        cls,
        hostname: str,
        resolved_ips: list[str] | None = None,
    ) -> "SecurityException":
        """
        DNS 리바인딩 공격 감지 예외 생성.

        Args:
            hostname: 호스트명
            resolved_ips: 해석된 IP 목록

        Returns:
            SecurityException 인스턴스
        """
        msg = f"DNS 리바인딩 공격이 감지되었습니다: {hostname}"

        details: dict[str, Any] = {"hostname": hostname}
        if resolved_ips:
            details["resolved_ips"] = resolved_ips

        return cls(
            ErrorCode.DNS_REBINDING_DETECTED,
            msg,
            threat_type="dns_rebinding",
            source=hostname,
            details=details,
        )


# =============================================================================
# 파일 포맷 예외
# =============================================================================

class FormatDetectionException(ValidationException):
    """
    파일 포맷 감지 예외.

    파일의 포맷을 감지하는 과정에서 발생하는 예외입니다.
    매직 바이트 읽기 실패, 파일 손상 등에 사용됩니다.

    Attributes:
        file_path: 감지 실패한 파일 경로
        detected_format: 감지된 포맷 (있는 경우)
        expected_format: 예상된 포맷 (있는 경우)
        reason: 실패 사유
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.FORMAT_DETECTION_ERROR,
        message: str | None = None,
        file_path: str | None = None,
        detected_format: str | None = None,
        expected_format: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        파일 포맷 감지 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            file_path: 파일 경로
            detected_format: 감지된 포맷
            expected_format: 예상된 포맷
            reason: 실패 사유
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if file_path:
            combined_details["file_path"] = file_path
        if detected_format:
            combined_details["detected_format"] = detected_format
        if expected_format:
            combined_details["expected_format"] = expected_format
        if reason:
            combined_details["reason"] = reason

        super().__init__(
            error_code,
            message,
            details=combined_details,
            cause=cause,
        )
        self.file_path = file_path
        self.detected_format = detected_format
        self.expected_format = expected_format
        self.reason = reason

    @classmethod
    def read_failed(
        cls,
        file_path: str,
        reason: str | None = None,
    ) -> "FormatDetectionException":
        """
        파일 읽기 실패 예외 생성.

        Args:
            file_path: 파일 경로
            reason: 실패 사유

        Returns:
            FormatDetectionException 인스턴스
        """
        msg = f"파일 읽기에 실패했습니다: {file_path}"
        if reason:
            msg += f" ({reason})"

        return cls(
            ErrorCode.FORMAT_DETECTION_ERROR,
            msg,
            file_path=file_path,
            reason=reason or "read_failed",
        )

    @classmethod
    def invalid_magic_bytes(
        cls,
        file_path: str,
        magic_bytes: bytes | None = None,
    ) -> "FormatDetectionException":
        """
        유효하지 않은 매직 바이트 예외 생성.

        Args:
            file_path: 파일 경로
            magic_bytes: 읽은 매직 바이트

        Returns:
            FormatDetectionException 인스턴스
        """
        details: dict[str, Any] = {}
        if magic_bytes:
            details["magic_bytes_hex"] = magic_bytes[:16].hex()

        return cls(
            ErrorCode.INVALID_MAGIC_BYTES,
            f"유효하지 않은 파일 시그니처입니다: {file_path}",
            file_path=file_path,
            reason="invalid_magic_bytes",
            details=details,
        )

    @classmethod
    def corrupted_file(
        cls,
        file_path: str,
        reason: str | None = None,
    ) -> "FormatDetectionException":
        """
        손상된 파일 예외 생성.

        Args:
            file_path: 파일 경로
            reason: 손상 사유

        Returns:
            FormatDetectionException 인스턴스
        """
        msg = f"파일이 손상되었습니다: {file_path}"
        if reason:
            msg += f" ({reason})"

        return cls(
            ErrorCode.CORRUPTED_FILE,
            msg,
            file_path=file_path,
            reason=reason or "corrupted",
        )

    @classmethod
    def format_mismatch(
        cls,
        file_path: str,
        detected_format: str,
        expected_format: str,
    ) -> "FormatDetectionException":
        """
        포맷 불일치 예외 생성.

        Args:
            file_path: 파일 경로
            detected_format: 실제 감지된 포맷
            expected_format: 확장자 기반 예상 포맷

        Returns:
            FormatDetectionException 인스턴스
        """
        return cls(
            ErrorCode.FORMAT_MISMATCH,
            f"파일 포맷 불일치: {file_path} (감지: {detected_format}, 예상: {expected_format})",
            file_path=file_path,
            detected_format=detected_format,
            expected_format=expected_format,
            reason="format_mismatch",
        )


class UnsupportedFormatException(ValidationException):
    """
    지원하지 않는 파일 포맷 예외.

    분석에 지원되지 않는 파일 포맷을 처리할 때 발생하는 예외입니다.

    Attributes:
        file_path: 파일 경로
        detected_format: 감지된 포맷
        supported_formats: 지원되는 포맷 목록
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.UNSUPPORTED_FORMAT,
        message: str | None = None,
        file_path: str | None = None,
        detected_format: str | None = None,
        supported_formats: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        지원하지 않는 포맷 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            file_path: 파일 경로
            detected_format: 감지된 포맷
            supported_formats: 지원되는 포맷 목록
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if file_path:
            combined_details["file_path"] = file_path
        if detected_format:
            combined_details["detected_format"] = detected_format
        if supported_formats:
            combined_details["supported_formats"] = supported_formats

        super().__init__(
            error_code,
            message,
            details=combined_details,
            cause=cause,
        )
        self.file_path = file_path
        self.detected_format = detected_format
        self.supported_formats = supported_formats or []

    @classmethod
    def video_format(
        cls,
        file_path: str,
        detected_format: str,
        supported_formats: list[str] | None = None,
    ) -> "UnsupportedFormatException":
        """
        지원하지 않는 비디오 포맷 예외 생성.

        Args:
            file_path: 파일 경로
            detected_format: 감지된 포맷
            supported_formats: 지원되는 포맷 목록

        Returns:
            UnsupportedFormatException 인스턴스
        """
        if supported_formats is None:
            supported_formats = ["MP4", "MOV", "AVI", "MKV", "WEBM"]

        supported_str = ", ".join(supported_formats[:5])
        if len(supported_formats) > 5:
            supported_str += f" 외 {len(supported_formats) - 5}개"

        return cls(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"지원하지 않는 비디오 포맷입니다: {detected_format} (지원: {supported_str})",
            file_path=file_path,
            detected_format=detected_format,
            supported_formats=supported_formats,
        )

    @classmethod
    def image_format(
        cls,
        file_path: str,
        detected_format: str,
        supported_formats: list[str] | None = None,
    ) -> "UnsupportedFormatException":
        """
        지원하지 않는 이미지 포맷 예외 생성.

        Args:
            file_path: 파일 경로
            detected_format: 감지된 포맷
            supported_formats: 지원되는 포맷 목록

        Returns:
            UnsupportedFormatException 인스턴스
        """
        if supported_formats is None:
            supported_formats = ["JPEG", "PNG", "BMP", "WEBP", "GIF"]

        supported_str = ", ".join(supported_formats[:5])

        return cls(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"지원하지 않는 이미지 포맷입니다: {detected_format} (지원: {supported_str})",
            file_path=file_path,
            detected_format=detected_format,
            supported_formats=supported_formats,
        )

    @classmethod
    def audio_format(
        cls,
        file_path: str,
        detected_format: str,
        supported_formats: list[str] | None = None,
    ) -> "UnsupportedFormatException":
        """
        지원하지 않는 오디오 포맷 예외 생성.

        Args:
            file_path: 파일 경로
            detected_format: 감지된 포맷
            supported_formats: 지원되는 포맷 목록

        Returns:
            UnsupportedFormatException 인스턴스
        """
        if supported_formats is None:
            supported_formats = ["MP3", "WAV", "AAC", "FLAC", "OGG"]

        supported_str = ", ".join(supported_formats[:5])

        return cls(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"지원하지 않는 오디오 포맷입니다: {detected_format} (지원: {supported_str})",
            file_path=file_path,
            detected_format=detected_format,
            supported_formats=supported_formats,
        )


class FormatValidationException(ValidationException):
    """
    포맷 검증 예외.

    비디오/이미지 포맷의 코덱, 해상도, FPS 등의 검증 실패 시 발생하는 예외입니다.

    Attributes:
        file_path: 검증 실패한 파일 경로
        format_type: 포맷 타입 (video, image, audio)
        validation_type: 검증 타입 (codec, resolution, fps, duration 등)
        actual_value: 실제 값
        expected_value: 기대 값
        reason: 검증 실패 사유
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.FORMAT_VALIDATION_ERROR,
        message: str | None = None,
        file_path: str | None = None,
        format_type: str | None = None,
        validation_type: str | None = None,
        actual_value: Any | None = None,
        expected_value: Any | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        포맷 검증 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            file_path: 파일 경로
            format_type: 포맷 타입
            validation_type: 검증 타입
            actual_value: 실제 값
            expected_value: 기대 값
            reason: 검증 실패 사유
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if file_path:
            combined_details["file_path"] = file_path
        if format_type:
            combined_details["format_type"] = format_type
        if validation_type:
            combined_details["validation_type"] = validation_type
        if actual_value is not None:
            combined_details["actual_value"] = actual_value
        if expected_value is not None:
            combined_details["expected_value"] = expected_value
        if reason:
            combined_details["reason"] = reason

        super().__init__(
            error_code,
            message,
            details=combined_details,
            cause=cause,
        )
        self.file_path = file_path
        self.format_type = format_type
        self.validation_type = validation_type
        self.actual_value = actual_value
        self.expected_value = expected_value
        self.reason = reason

    @classmethod
    def codec_not_supported(
        cls,
        file_path: str,
        codec: str,
        supported_codecs: list[str] | None = None,
    ) -> "FormatValidationException":
        """지원하지 않는 코덱 예외 생성."""
        msg = f"지원하지 않는 코덱입니다: {codec}"
        if supported_codecs:
            msg += f" (지원: {', '.join(supported_codecs[:5])})"

        details: dict[str, Any] = {"codec": codec}
        if supported_codecs:
            details["supported_codecs"] = supported_codecs

        return cls(
            ErrorCode.CODEC_NOT_SUPPORTED,
            msg,
            file_path=file_path,
            format_type="video",
            validation_type="codec",
            actual_value=codec,
            expected_value=supported_codecs,
            reason="codec_not_supported",
            details=details,
        )

    @classmethod
    def format_not_allowed(
        cls,
        file_path: str,
        detected_format: str,
        allowed_formats: list[str] | None = None,
    ) -> "FormatValidationException":
        """허용되지 않은 포맷 예외 생성."""
        msg = f"허용되지 않은 포맷입니다: {detected_format}"
        if allowed_formats:
            msg += f" (허용: {', '.join(allowed_formats[:5])})"

        details: dict[str, Any] = {"detected_format": detected_format}
        if allowed_formats:
            details["allowed_formats"] = allowed_formats

        return cls(
            ErrorCode.FORMAT_NOT_ALLOWED,
            msg,
            file_path=file_path,
            validation_type="format",
            actual_value=detected_format,
            expected_value=allowed_formats,
            reason="format_not_allowed",
            details=details,
        )

    @classmethod
    def bitrate_out_of_range(
        cls,
        file_path: str,
        bitrate: int,
        min_bitrate: int | None = None,
        max_bitrate: int | None = None,
    ) -> "FormatValidationException":
        """비트레이트 범위 초과 예외 생성."""
        bitrate_kbps = bitrate // 1000
        msg = f"비트레이트가 허용 범위를 벗어났습니다: {bitrate_kbps} kbps"

        range_info = []
        if min_bitrate:
            range_info.append(f"최소: {min_bitrate // 1000} kbps")
        if max_bitrate:
            range_info.append(f"최대: {max_bitrate // 1000} kbps")
        if range_info:
            msg += f" ({', '.join(range_info)})"

        return cls(
            ErrorCode.BITRATE_OUT_OF_RANGE,
            msg,
            file_path=file_path,
            format_type="video",
            validation_type="bitrate",
            actual_value=bitrate,
            expected_value={"min": min_bitrate, "max": max_bitrate},
            reason="bitrate_out_of_range",
            details={
                "bitrate": bitrate,
                "bitrate_kbps": bitrate_kbps,
                "min_bitrate": min_bitrate,
                "max_bitrate": max_bitrate,
            },
        )

    @classmethod
    def fps_too_low(
        cls,
        file_path: str,
        fps: float,
        min_fps: float,
    ) -> "FormatValidationException":
        """FPS 너무 낮음 예외 생성."""
        return cls(
            ErrorCode.FPS_TOO_LOW,
            f"FPS가 너무 낮습니다: {fps:.2f} (최소: {min_fps:.2f})",
            file_path=file_path,
            format_type="video",
            validation_type="fps",
            actual_value=fps,
            expected_value={"min": min_fps},
            reason="fps_too_low",
        )

    @classmethod
    def fps_too_high(
        cls,
        file_path: str,
        fps: float,
        max_fps: float,
    ) -> "FormatValidationException":
        """FPS 너무 높음 예외 생성."""
        return cls(
            ErrorCode.FPS_TOO_HIGH,
            f"FPS가 너무 높습니다: {fps:.2f} (최대: {max_fps:.2f})",
            file_path=file_path,
            format_type="video",
            validation_type="fps",
            actual_value=fps,
            expected_value={"max": max_fps},
            reason="fps_too_high",
        )

    @classmethod
    def duration_too_short(
        cls,
        file_path: str,
        duration: float,
        min_duration: float,
    ) -> "FormatValidationException":
        """영상 길이 너무 짧음 예외 생성."""
        return cls(
            ErrorCode.DURATION_TOO_SHORT,
            f"영상 길이가 너무 짧습니다: {duration:.2f}초 (최소: {min_duration:.2f}초)",
            file_path=file_path,
            format_type="video",
            validation_type="duration",
            actual_value=duration,
            expected_value={"min": min_duration},
            reason="duration_too_short",
        )

    @classmethod
    def duration_too_long(
        cls,
        file_path: str,
        duration: float,
        max_duration: float,
    ) -> "FormatValidationException":
        """영상 길이 너무 긺 예외 생성."""
        return cls(
            ErrorCode.DURATION_TOO_LONG,
            f"영상 길이가 너무 깁니다: {duration:.2f}초 (최대: {max_duration:.2f}초)",
            file_path=file_path,
            format_type="video",
            validation_type="duration",
            actual_value=duration,
            expected_value={"max": max_duration},
            reason="duration_too_long",
        )


class ResolutionException(ValidationException):
    """
    해상도 검증 예외.

    비디오/이미지의 해상도가 요구사항을 충족하지 못할 때 발생하는 예외입니다.

    Attributes:
        file_path: 검증 실패한 파일 경로
        width: 실제 너비
        height: 실제 높이
        min_width: 최소 요구 너비
        min_height: 최소 요구 높이
        max_width: 최대 허용 너비
        max_height: 최대 허용 높이
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.RESOLUTION_ERROR,
        message: str | None = None,
        file_path: str | None = None,
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """해상도 검증 예외 초기화."""
        combined_details = details or {}

        if file_path:
            combined_details["file_path"] = file_path
        if width is not None:
            combined_details["width"] = width
        if height is not None:
            combined_details["height"] = height
        if min_width is not None:
            combined_details["min_width"] = min_width
        if min_height is not None:
            combined_details["min_height"] = min_height
        if max_width is not None:
            combined_details["max_width"] = max_width
        if max_height is not None:
            combined_details["max_height"] = max_height

        if width and height:
            combined_details["resolution"] = f"{width}x{height}"

        super().__init__(
            error_code,
            message,
            details=combined_details,
            cause=cause,
        )
        self.file_path = file_path
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self.max_width = max_width
        self.max_height = max_height

    @classmethod
    def too_low(
        cls,
        file_path: str,
        width: int,
        height: int,
        min_width: int,
        min_height: int,
    ) -> "ResolutionException":
        """해상도 너무 낮음 예외 생성."""
        return cls(
            ErrorCode.RESOLUTION_TOO_LOW,
            f"해상도가 너무 낮습니다: {width}x{height} (최소: {min_width}x{min_height})",
            file_path=file_path,
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
        )

    @classmethod
    def too_high(
        cls,
        file_path: str,
        width: int,
        height: int,
        max_width: int,
        max_height: int,
    ) -> "ResolutionException":
        """해상도 너무 높음 예외 생성."""
        return cls(
            ErrorCode.RESOLUTION_TOO_HIGH,
            f"해상도가 너무 높습니다: {width}x{height} (최대: {max_width}x{max_height})",
            file_path=file_path,
            width=width,
            height=height,
            max_width=max_width,
            max_height=max_height,
        )

    @classmethod
    def not_supported(
        cls,
        file_path: str,
        width: int,
        height: int,
        supported_resolutions: list[str] | None = None,
    ) -> "ResolutionException":
        """지원하지 않는 해상도 예외 생성."""
        msg = f"지원하지 않는 해상도입니다: {width}x{height}"
        if supported_resolutions:
            msg += f" (지원: {', '.join(supported_resolutions[:3])})"

        details: dict[str, Any] = {}
        if supported_resolutions:
            details["supported_resolutions"] = supported_resolutions

        return cls(
            ErrorCode.RESOLUTION_NOT_SUPPORTED,
            msg,
            file_path=file_path,
            width=width,
            height=height,
            details=details,
        )

    @classmethod
    def aspect_ratio_not_supported(
        cls,
        file_path: str,
        width: int,
        height: int,
        supported_ratios: list[str] | None = None,
    ) -> "ResolutionException":
        """지원하지 않는 화면 비율 예외 생성."""
        from math import gcd

        g = gcd(width, height) if height > 0 else 1
        aspect = f"{width // g}:{height // g}" if g > 0 else "N/A"

        msg = f"지원하지 않는 화면 비율입니다: {aspect} ({width}x{height})"
        if supported_ratios:
            msg += f" (지원: {', '.join(supported_ratios[:3])})"

        details: dict[str, Any] = {"aspect_ratio": aspect}
        if supported_ratios:
            details["supported_ratios"] = supported_ratios

        return cls(
            ErrorCode.ASPECT_RATIO_NOT_SUPPORTED,
            msg,
            file_path=file_path,
            width=width,
            height=height,
            details=details,
        )


# =============================================================================
# 설정 검증 예외
# =============================================================================

class ConfigurationException(ValidationException):
    """설정 관련 기본 예외."""

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.CONFIGURATION_ERROR,
        message: str | None = None,
        config_key: str | None = None,
        config_file: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 예외 초기화.

        Args:
            error_code: 에러 코드
            message: 에러 메시지
            config_key: 문제가 된 설정 키
            config_file: 설정 파일 경로
            details: 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if config_key:
            combined_details["config_key"] = config_key
        if config_file:
            combined_details["config_file"] = config_file

        super().__init__(
            error_code,
            message,
            field_name=config_key,
            details=combined_details,
            cause=cause,
        )
        self.config_key = config_key
        self.config_file = config_file


class ConfigurationNotFoundException(ConfigurationException):
    """설정 파일 미발견 예외."""

    def __init__(
        self,
        config_file: str,
        searched_paths: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 파일 미발견 예외 초기화.

        Args:
            config_file: 설정 파일명
            searched_paths: 검색한 경로 목록
            cause: 원인 예외
        """
        message = f"설정 파일을 찾을 수 없습니다: {config_file}"

        super().__init__(
            ErrorCode.CONFIGURATION_NOT_FOUND,
            message,
            config_file=config_file,
            details={"searched_paths": searched_paths} if searched_paths else None,
            cause=cause,
        )


class ConfigurationLoadException(ConfigurationException):
    """설정 로드 실패 예외."""

    def __init__(
        self,
        config_file: str,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 로드 예외 초기화.

        Args:
            config_file: 설정 파일명
            reason: 실패 이유
            cause: 원인 예외
        """
        message = f"설정 파일 로드에 실패했습니다: {config_file}"
        if reason:
            message += f". 이유: {reason}"

        super().__init__(
            ErrorCode.CONFIGURATION_LOAD_FAILED,
            message,
            config_file=config_file,
            details={"reason": reason} if reason else None,
            cause=cause,
        )


class ConfigurationParseException(ConfigurationException):
    """설정 파일 파싱 실패 예외."""

    def __init__(
        self,
        config_file: str,
        reason: str | None = None,
        line_number: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 파싱 예외 초기화.

        Args:
            config_file: 설정 파일명
            reason: 파싱 실패 이유
            line_number: 오류 발생 라인 번호
            cause: 원인 예외
        """
        message = f"설정 파일 파싱에 실패했습니다: {config_file}"
        if reason:
            message += f". 이유: {reason}"
        if line_number:
            message += f" (라인 {line_number})"

        super().__init__(
            ErrorCode.CONFIGURATION_LOAD_FAILED,
            message,
            config_file=config_file,
            details={
                "reason": reason,
                "line_number": line_number,
            },
            cause=cause,
        )


class ConfigurationValidationException(ConfigurationException):
    """설정 값 유효성 검증 실패 예외."""

    def __init__(
        self,
        config_key: str,
        config_value: Any,
        reason: str,
        config_file: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 검증 예외 초기화.

        Args:
            config_key: 설정 키
            config_value: 설정 값
            reason: 유효하지 않은 이유
            config_file: 설정 파일명
            cause: 원인 예외
        """
        message = f"설정 값이 유효하지 않습니다: {config_key}. {reason}"

        super().__init__(
            ErrorCode.CONFIGURATION_INVALID,
            message,
            config_key=config_key,
            config_file=config_file,
            details={
                "config_value": config_value,
                "reason": reason,
            },
            cause=cause,
        )


# =============================================================================
# 스키마 검증 예외
# =============================================================================

class SchemaValidationException(ValidationException):
    """스키마 검증 실패 예외."""

    def __init__(
        self,
        errors: list[dict[str, Any]],
        schema_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        스키마 검증 예외 초기화.

        Args:
            errors: 검증 오류 목록 (Pydantic ValidationError에서 추출)
            schema_name: 스키마/모델 이름
            cause: 원인 예외
        """
        error_count = len(errors)
        message = f"스키마 검증에 실패했습니다: {error_count}개의 오류"

        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            message,
            details={
                "schema_name": schema_name,
                "error_count": error_count,
                "errors": errors[:10],  # 처음 10개만 포함
            },
            cause=cause,
        )
        self.errors = errors
        self.schema_name = schema_name

    @classmethod
    def from_pydantic_errors(
        cls,
        errors: list[dict[str, Any]],
        schema_name: str | None = None,
    ) -> "SchemaValidationException":
        """
        Pydantic 오류에서 생성.

        Args:
            errors: Pydantic ValidationError.errors() 결과
            schema_name: 스키마 이름

        Returns:
            SchemaValidationException 인스턴스
        """
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "type": error.get("type"),
                "message": error.get("msg"),
            })
        return cls(formatted_errors, schema_name)


# =============================================================================
# 입력 유효성 검사 예외
# =============================================================================

class InputValidationException(ValidationException):
    """
    입력 데이터 유효성 검사 예외.

    사용자 입력 데이터의 유효성 검사 실패 시 발생하는 예외입니다.
    여러 필드에 대한 검증 오류를 한번에 처리할 수 있습니다.

    Attributes:
        field_errors: 필드별 오류 목록
        input_source: 입력 소스 (form, query, body, header 등)
    """

    def __init__(
        self,
        message: str = "입력 데이터 검증에 실패했습니다",
        field_errors: dict[str, list[str]] | None = None,
        input_source: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        입력 유효성 검사 예외 초기화.

        Args:
            message: 에러 메시지
            field_errors: 필드별 오류 메시지 목록 {field_name: [error1, error2, ...]}
            input_source: 입력 소스 (form, query, body, header, path 등)
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if field_errors:
            combined_details["field_errors"] = field_errors
            combined_details["error_count"] = sum(len(errors) for errors in field_errors.values())

        if input_source:
            combined_details["input_source"] = input_source

        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            message,
            details=combined_details,
            cause=cause,
        )
        self.field_errors = field_errors or {}
        self.input_source = input_source

    def add_field_error(self, field_name: str, error_message: str) -> "InputValidationException":
        """
        필드 오류 추가.

        Args:
            field_name: 필드명
            error_message: 오류 메시지

        Returns:
            self (메서드 체이닝용)
        """
        if field_name not in self.field_errors:
            self.field_errors[field_name] = []
        self.field_errors[field_name].append(error_message)

        # details 업데이트
        self.details["field_errors"] = self.field_errors
        self.details["error_count"] = sum(len(errors) for errors in self.field_errors.values())

        return self

    def has_errors(self) -> bool:
        """오류가 있는지 확인."""
        return len(self.field_errors) > 0


# =============================================================================
# 인증/권한 예외
# =============================================================================

class AuthenticationException(NonRetryableException):
    """
    인증 예외.

    사용자 인증 실패 시 발생하는 예외입니다.
    로그인 실패, 토큰 만료, 잘못된 자격 증명 등에 사용됩니다.

    Attributes:
        auth_method: 인증 방식 (token, api_key, basic, oauth 등)
        reason: 인증 실패 사유
    """

    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_FAILED,
        message: str | None = None,
        auth_method: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        인증 예외 초기화.

        Args:
            error_code: 에러 코드 (AUTHENTICATION_REQUIRED, AUTHENTICATION_FAILED 등)
            message: 에러 메시지
            auth_method: 인증 방식
            reason: 인증 실패 사유
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if auth_method:
            combined_details["auth_method"] = auth_method
        if reason:
            combined_details["reason"] = reason

        super().__init__(
            error_code,
            message,
            combined_details,
            cause=cause,
        )
        self.auth_method = auth_method
        self.reason = reason

    @classmethod
    def token_expired(
        cls,
        token_type: str = "access_token",
        expired_at: str | None = None,
    ) -> "AuthenticationException":
        """
        토큰 만료 예외 생성.

        Args:
            token_type: 토큰 타입 (access_token, refresh_token 등)
            expired_at: 만료 시간 (ISO 형식)

        Returns:
            AuthenticationException 인스턴스
        """
        details: dict[str, Any] = {"token_type": token_type}
        if expired_at:
            details["expired_at"] = expired_at

        return cls(
            ErrorCode.TOKEN_EXPIRED,
            f"{token_type} 토큰이 만료되었습니다",
            auth_method="token",
            reason="token_expired",
            details=details,
        )

    @classmethod
    def invalid_credentials(cls) -> "AuthenticationException":
        """잘못된 자격 증명 예외 생성."""
        return cls(
            ErrorCode.AUTHENTICATION_FAILED,
            "아이디 또는 비밀번호가 올바르지 않습니다",
            reason="invalid_credentials",
        )

    @classmethod
    def api_key_invalid(cls, key_prefix: str | None = None) -> "AuthenticationException":
        """
        잘못된 API 키 예외 생성.

        Args:
            key_prefix: API 키 접두사 (마스킹용)

        Returns:
            AuthenticationException 인스턴스
        """
        details: dict[str, Any] = {}
        if key_prefix:
            details["key_prefix"] = key_prefix[:8] + "..."  # 보안을 위해 일부만 표시

        return cls(
            ErrorCode.API_KEY_INVALID,
            "유효하지 않은 API 키입니다",
            auth_method="api_key",
            reason="invalid_api_key",
            details=details,
        )


class AuthorizationException(NonRetryableException):
    """
    권한 예외.

    사용자가 리소스에 대한 접근 권한이 없을 때 발생하는 예외입니다.

    Attributes:
        resource: 접근하려는 리소스
        action: 수행하려는 동작
        required_permissions: 필요한 권한 목록
    """

    def __init__(
        self,
        message: str = "권한이 없습니다",
        resource: str | None = None,
        action: str | None = None,
        required_permissions: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        권한 예외 초기화.

        Args:
            message: 에러 메시지
            resource: 접근하려는 리소스 (예: "user:123", "analysis:abc")
            action: 수행하려는 동작 (예: "read", "write", "delete")
            required_permissions: 필요한 권한 목록
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if resource:
            combined_details["resource"] = resource
        if action:
            combined_details["action"] = action
        if required_permissions:
            combined_details["required_permissions"] = required_permissions

        super().__init__(
            ErrorCode.PERMISSION_DENIED,
            message,
            combined_details,
            cause=cause,
        )
        self.resource = resource
        self.action = action
        self.required_permissions = required_permissions or []

    @classmethod
    def resource_access_denied(
        cls,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> "AuthorizationException":
        """
        리소스 접근 거부 예외 생성.

        Args:
            resource_type: 리소스 타입 (user, analysis, video 등)
            resource_id: 리소스 ID
            action: 수행하려는 동작

        Returns:
            AuthorizationException 인스턴스
        """
        return cls(
            f"{resource_type} '{resource_id}'에 대한 {action} 권한이 없습니다",
            resource=f"{resource_type}:{resource_id}",
            action=action,
        )


# =============================================================================
# 속도 제한 예외
# =============================================================================

class RateLimitException(RetryableException):
    """
    속도 제한 예외.

    API 요청 속도 제한 초과 시 발생하는 예외입니다.
    RetryableException을 상속하여 재시도 정보를 포함합니다.

    Attributes:
        limit: 제한 값
        window_seconds: 제한 시간 창 (초)
        current_count: 현재 요청 수
        reset_at: 제한 초기화 시간
    """

    def __init__(
        self,
        message: str = "요청 한도를 초과했습니다",
        limit: int | None = None,
        window_seconds: int | None = None,
        current_count: int | None = None,
        reset_at: str | None = None,
        retry_after: float = 60.0,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        속도 제한 예외 초기화.

        Args:
            message: 에러 메시지
            limit: 제한 값 (예: 분당 100회)
            window_seconds: 제한 시간 창 (초)
            current_count: 현재 요청 수
            reset_at: 제한 초기화 시간 (ISO 형식)
            retry_after: 재시도까지 대기 시간 (초)
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if limit is not None:
            combined_details["limit"] = limit
        if window_seconds is not None:
            combined_details["window_seconds"] = window_seconds
        if current_count is not None:
            combined_details["current_count"] = current_count
        if reset_at:
            combined_details["reset_at"] = reset_at

        super().__init__(
            ErrorCode.RATE_LIMIT_EXCEEDED,
            message,
            combined_details,
            cause=cause,
            retry_after=retry_after,
            max_retries=1,  # 속도 제한은 일반적으로 1회 재시도 권장
        )
        self.limit = limit
        self.window_seconds = window_seconds
        self.current_count = current_count
        self.reset_at = reset_at

    def to_response_headers(self) -> dict[str, str]:
        """
        HTTP 응답 헤더용 딕셔너리 반환.

        Returns:
            Rate Limit 관련 HTTP 헤더
        """
        headers: dict[str, str] = {
            "Retry-After": str(int(self.retry_after)),
        }

        if self.limit is not None:
            headers["X-RateLimit-Limit"] = str(self.limit)
        if self.current_count is not None:
            headers["X-RateLimit-Remaining"] = str(max(0, self.limit - self.current_count) if self.limit else 0)
        if self.reset_at:
            headers["X-RateLimit-Reset"] = self.reset_at

        return headers


# =============================================================================
# 데이터 품질 예외
# =============================================================================


class DataQualityException(ValidationException):
    """데이터 품질 검사 실패 예외."""

    def __init__(
        self,
        message: str = "데이터 품질 검사에 실패했습니다",
        quality_level: str | None = None,
        overall_score: float | None = None,
        dimension_scores: dict[str, float] | None = None,
        failed_dimensions: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        데이터 품질 예외 초기화.

        Args:
            message: 에러 메시지
            quality_level: 품질 레벨 (excellent, good, acceptable, poor, unacceptable)
            overall_score: 종합 점수 (0-100)
            dimension_scores: 차원별 점수 딕셔너리
            failed_dimensions: 실패한 품질 차원 목록
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if quality_level is not None:
            combined_details["quality_level"] = quality_level
        if overall_score is not None:
            combined_details["overall_score"] = overall_score
        if dimension_scores:
            combined_details["dimension_scores"] = dimension_scores
        if failed_dimensions:
            combined_details["failed_dimensions"] = failed_dimensions

        super().__init__(
            ErrorCode.DATA_QUALITY_ERROR,
            message,
            combined_details,
            cause=cause,
        )
        self.quality_level = quality_level
        self.overall_score = overall_score
        self.dimension_scores = dimension_scores or {}
        self.failed_dimensions = failed_dimensions or []

    @classmethod
    def brightness_error(
        cls,
        brightness_value: float,
        min_threshold: float,
        max_threshold: float,
        cause: Exception | None = None,
    ) -> "DataQualityException":
        """밝기 품질 에러 팩토리 메서드."""
        if brightness_value < min_threshold:
            message = f"영상 밝기가 너무 낮습니다: {brightness_value:.1f} (최소: {min_threshold:.1f})"
        else:
            message = f"영상 밝기가 너무 높습니다: {brightness_value:.1f} (최대: {max_threshold:.1f})"

        return cls(
            message=message,
            failed_dimensions=["brightness"],
            dimension_scores={"brightness": brightness_value},
            cause=cause,
        )

    @classmethod
    def contrast_error(
        cls,
        contrast_value: float,
        min_threshold: float,
        cause: Exception | None = None,
    ) -> "DataQualityException":
        """대비 품질 에러 팩토리 메서드."""
        return cls(
            message=f"영상 대비가 너무 낮습니다: {contrast_value:.1f} (최소: {min_threshold:.1f})",
            failed_dimensions=["contrast"],
            dimension_scores={"contrast": contrast_value},
            cause=cause,
        )

    @classmethod
    def noise_error(
        cls,
        noise_level: float,
        max_threshold: float,
        cause: Exception | None = None,
    ) -> "DataQualityException":
        """노이즈 품질 에러 팩토리 메서드."""
        return cls(
            message=f"영상 노이즈가 너무 높습니다: {noise_level:.1f} (최대: {max_threshold:.1f})",
            failed_dimensions=["noise"],
            dimension_scores={"noise": noise_level},
            cause=cause,
        )

    @classmethod
    def blur_error(
        cls,
        blur_level: float,
        max_threshold: float,
        cause: Exception | None = None,
    ) -> "DataQualityException":
        """블러 품질 에러 팩토리 메서드."""
        return cls(
            message=f"영상이 너무 흐릿합니다: 선명도 {blur_level:.1f} (최소: {max_threshold:.1f})",
            failed_dimensions=["blur"],
            dimension_scores={"blur": blur_level},
            cause=cause,
        )


class LowQualityException(DataQualityException):
    """최소 품질 기준 미달 예외."""

    def __init__(
        self,
        message: str = "데이터 품질이 최소 기준에 미달합니다",
        overall_score: float | None = None,
        minimum_score: float = 60.0,
        quality_level: str | None = None,
        dimension_scores: dict[str, float] | None = None,
        failed_dimensions: list[str] | None = None,
        recommendations: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        최소 품질 미달 예외 초기화.

        Args:
            message: 에러 메시지
            overall_score: 종합 점수
            minimum_score: 최소 요구 점수
            quality_level: 품질 레벨
            dimension_scores: 차원별 점수
            failed_dimensions: 실패한 차원 목록
            recommendations: 품질 개선 권장사항
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        combined_details["minimum_score"] = minimum_score

        if recommendations:
            combined_details["recommendations"] = recommendations

        super().__init__(
            message=message,
            quality_level=quality_level,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            failed_dimensions=failed_dimensions,
            details=combined_details,
            cause=cause,
        )
        self.minimum_score = minimum_score
        self.recommendations = recommendations or []

    @classmethod
    def from_quality_result(
        cls,
        overall_score: float,
        minimum_score: float,
        dimension_scores: dict[str, float],
        failed_dimensions: list[str],
        quality_level: str,
    ) -> "LowQualityException":
        """품질 검사 결과로부터 예외 생성 팩토리 메서드."""
        recommendations = []

        for dim in failed_dimensions:
            if dim == "brightness":
                recommendations.append("조명 환경을 개선하세요")
            elif dim == "contrast":
                recommendations.append("더 선명한 배경에서 촬영하세요")
            elif dim == "noise":
                recommendations.append("더 밝은 환경에서 촬영하세요")
            elif dim == "blur":
                recommendations.append("카메라를 고정하고 촬영하세요")
            elif dim == "resolution":
                recommendations.append("더 높은 해상도로 촬영하세요")
            elif dim == "fps":
                recommendations.append("더 높은 프레임레이트로 촬영하세요")

        return cls(
            message=f"데이터 품질({overall_score:.1f}점)이 최소 기준({minimum_score:.1f}점)에 미달합니다",
            overall_score=overall_score,
            minimum_score=minimum_score,
            quality_level=quality_level,
            dimension_scores=dimension_scores,
            failed_dimensions=failed_dimensions,
            recommendations=recommendations,
        )


# =============================================================================
# 규칙 세트 예외 (v3.0.0 - rule_set_manager.py 지원)
# =============================================================================


class RuleSetNotFoundException(ValidationException):
    """
    규칙 세트 미발견 예외.

    요청한 리그의 규칙 세트를 찾을 수 없을 때 발생하는 예외입니다.

    Attributes:
        league: 요청한 리그 (FIBA, NBA, KBL 등)
        version: 요청한 버전 (있는 경우)
        searched_paths: 검색한 경로 목록
    """

    def __init__(
        self,
        league: str,
        version: str | None = None,
        searched_paths: list[str] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        규칙 세트 미발견 예외 초기화.

        Args:
            league: 요청한 리그
            version: 요청한 버전
            searched_paths: 검색한 경로 목록
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        combined_details["league"] = league

        if version:
            combined_details["version"] = version
            message = f"규칙 세트를 찾을 수 없습니다: {league} (버전: {version})"
        else:
            message = f"규칙 세트를 찾을 수 없습니다: {league}"

        if searched_paths:
            combined_details["searched_paths"] = searched_paths

        super().__init__(
            ErrorCode.RULE_SET_NOT_FOUND,
            message,
            field_name="league",
            field_value=league,
            details=combined_details,
            cause=cause,
        )
        self.league = league
        self.version = version
        self.searched_paths = searched_paths or []

    @classmethod
    def for_league(
        cls,
        league: str,
        available_leagues: list[str] | None = None,
    ) -> "RuleSetNotFoundException":
        """
        리그별 미발견 예외 생성.

        Args:
            league: 요청한 리그
            available_leagues: 사용 가능한 리그 목록

        Returns:
            RuleSetNotFoundException 인스턴스
        """
        details: dict[str, Any] = {}
        if available_leagues:
            details["available_leagues"] = available_leagues

        return cls(
            league=league,
            details=details,
        )


class RuleSetValidationException(ValidationException):
    """
    규칙 세트 검증 예외.

    규칙 세트의 구조, 스키마, 데이터가 유효하지 않을 때 발생하는 예외입니다.

    Attributes:
        league: 검증 실패한 리그
        validation_errors: 검증 오류 목록
        rule_id: 문제가 된 규칙 ID (있는 경우)
    """

    def __init__(
        self,
        league: str,
        validation_errors: list[dict[str, Any]] | None = None,
        rule_id: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        규칙 세트 검증 예외 초기화.

        Args:
            league: 검증 실패한 리그
            validation_errors: 검증 오류 목록
            rule_id: 문제가 된 규칙 ID
            reason: 검증 실패 사유
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        combined_details["league"] = league

        if validation_errors:
            combined_details["validation_errors"] = validation_errors[:10]  # 최대 10개
            combined_details["error_count"] = len(validation_errors)

        if rule_id:
            combined_details["rule_id"] = rule_id
            message = f"규칙 세트 검증 실패: {league}, 규칙 ID: {rule_id}"
        else:
            message = f"규칙 세트 검증 실패: {league}"

        if reason:
            message += f" - {reason}"
            combined_details["reason"] = reason

        super().__init__(
            ErrorCode.RULE_SET_VALIDATION_ERROR,
            message,
            field_name="rule_set",
            field_value=league,
            details=combined_details,
            cause=cause,
        )
        self.league = league
        self.validation_errors = validation_errors or []
        self.rule_id = rule_id
        self.reason = reason

    @classmethod
    def schema_error(
        cls,
        league: str,
        schema_errors: list[dict[str, Any]],
    ) -> "RuleSetValidationException":
        """
        스키마 검증 오류 예외 생성.

        Args:
            league: 리그
            schema_errors: 스키마 검증 오류 목록

        Returns:
            RuleSetValidationException 인스턴스
        """
        return cls(
            league=league,
            validation_errors=schema_errors,
            reason="스키마 검증 실패",
        )

    @classmethod
    def invalid_rule(
        cls,
        league: str,
        rule_id: str,
        reason: str,
    ) -> "RuleSetValidationException":
        """
        개별 규칙 검증 오류 예외 생성.

        Args:
            league: 리그
            rule_id: 문제가 된 규칙 ID
            reason: 검증 실패 사유

        Returns:
            RuleSetValidationException 인스턴스
        """
        return cls(
            league=league,
            rule_id=rule_id,
            reason=reason,
        )

    @classmethod
    def missing_required_field(
        cls,
        league: str,
        field_name: str,
        rule_id: str | None = None,
    ) -> "RuleSetValidationException":
        """
        필수 필드 누락 예외 생성.

        Args:
            league: 리그
            field_name: 누락된 필드명
            rule_id: 규칙 ID (있는 경우)

        Returns:
            RuleSetValidationException 인스턴스
        """
        return cls(
            league=league,
            rule_id=rule_id,
            reason=f"필수 필드 누락: {field_name}",
            details={"missing_field": field_name},
        )


class RuleSetVersionMismatchException(ValidationException):
    """
    규칙 세트 버전 불일치 예외.

    요청한 규칙 세트 버전과 실제 버전이 일치하지 않을 때 발생하는 예외입니다.

    Attributes:
        league: 리그
        expected_version: 기대 버전
        actual_version: 실제 버전
    """

    def __init__(
        self,
        league: str,
        expected_version: str,
        actual_version: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        규칙 세트 버전 불일치 예외 초기화.

        Args:
            league: 리그
            expected_version: 기대 버전
            actual_version: 실제 버전
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        combined_details["league"] = league
        combined_details["expected_version"] = expected_version
        combined_details["actual_version"] = actual_version

        message = (
            f"규칙 세트 버전 불일치: {league} "
            f"(기대: {expected_version}, 실제: {actual_version})"
        )

        super().__init__(
            ErrorCode.RULE_SET_VERSION_MISMATCH,
            message,
            field_name="version",
            field_value=actual_version,
            details=combined_details,
            cause=cause,
        )
        self.league = league
        self.expected_version = expected_version
        self.actual_version = actual_version

    @classmethod
    def incompatible(
        cls,
        league: str,
        expected_version: str,
        actual_version: str,
        reason: str | None = None,
    ) -> "RuleSetVersionMismatchException":
        """
        호환되지 않는 버전 예외 생성.

        Args:
            league: 리그
            expected_version: 기대 버전
            actual_version: 실제 버전
            reason: 추가 사유

        Returns:
            RuleSetVersionMismatchException 인스턴스
        """
        details: dict[str, Any] = {}
        if reason:
            details["reason"] = reason

        return cls(
            league=league,
            expected_version=expected_version,
            actual_version=actual_version,
            details=details,
        )

    def is_upgrade_available(self) -> bool:
        """
        업그레이드 가능 여부 확인.

        실제 버전이 기대 버전보다 높으면 업그레이드 가능으로 판단합니다.

        Returns:
            업그레이드 가능 여부
        """
        try:
            # 간단한 시맨틱 버전 비교 (v1.0.0 형식)
            expected_parts = self.expected_version.lstrip("v").split(".")
            actual_parts = self.actual_version.lstrip("v").split(".")

            for exp, act in zip(expected_parts, actual_parts):
                if int(act) > int(exp):
                    return True
                elif int(act) < int(exp):
                    return False
            return False
        except (ValueError, IndexError):
            return False


# =============================================================================
# 모듈 버전 정보
# =============================================================================
__version__ = "1.0.0"
