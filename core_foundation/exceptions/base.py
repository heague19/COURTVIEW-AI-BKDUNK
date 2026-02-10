"""
exceptions/base.py - COURTVIEW Desktop 예외 계층 루트 클래스

모든 COURTVIEW 예외의 공통 부모 클래스
- 에러 코드 시스템 (CV000~CV999)
- 컨텍스트 정보 저장 (<1KB)
- 스택 트레이스 캡처 (10 프레임 제한)
- 민감 정보 필터링
- 프로덕션 안정성

Author: COURTVIEW Team
Version: 1.0.0
"""

from typing import Dict, Any, Optional
from datetime import datetime
import traceback
import sys
import platform


class CourtViewError(Exception):
    """
    COURTVIEW Desktop 전용 기본 예외 클래스

    모든 COURTVIEW 예외의 루트 클래스
    - 에러 코드 시스템
    - 컨텍스트 정보 저장
    - 타임스탬프 기록
    - 스택 트레이스 캡처
    - 민감 정보 필터링

    Attributes:
        ERROR_CODE (str): 기본 에러 코드 (파생 클래스에서 재정의)
        message (str): 사용자 친화적 에러 메시지
        error_code (str): 5자리 에러 코드 (CV000~CV999)
        context (Dict): 에러 발생 시점의 상태 정보 (<512 bytes)
        original_error (Exception): 원본 예외 (체이닝용)
        timestamp (datetime): 에러 발생 시각
        stack_trace (str): 스택 트레이스 (최대 10 프레임)
        platform_info (Dict): 실행 환경 정보

    Examples:
        >>> raise CourtViewError("파일을 찾을 수 없습니다")
        >>> raise CourtViewError(
        ...     "GPU 메모리가 부족합니다",
        ...     error_code="CV201",
        ...     context={"required_mb": 8000, "available_mb": 4000}
        ... )
    """

    # 클래스 변수
    ERROR_CODE: str = "CV000"  # 기본 에러 코드 (파생 클래스에서 재정의)

    # 민감 정보 필터링 키 목록
    SENSITIVE_KEYS = {
        "password", "passwd", "pwd",
        "api_key", "apikey", "secret",
        "token", "access_token", "refresh_token",
        "credential", "auth", "authorization",
        "private_key", "secret_key",
    }

    # 플랫폼 정보 캐시 (모든 인스턴스 공유)
    _PLATFORM_INFO_CACHE: Optional[Dict[str, str]] = None

    # 사용자 친화적 메시지 매핑
    USER_FRIENDLY_MESSAGES: Dict[str, str] = {
        "CV000": "오류가 발생했습니다.",
        "CV101": "설정 파일을 찾을 수 없습니다.",
        "CV102": "설정 파일이 올바르지 않습니다.",
        "CV201": "GPU를 사용할 수 없습니다. CPU 모드로 전환합니다.",
        "CV202": "카메라를 연결할 수 없습니다.",
        "CV301": "입력 데이터가 올바르지 않습니다.",
        "CV401": "파일에 접근할 수 없습니다.",
        "CV901": "메모리가 부족합니다. 일부 기능을 종료해주세요.",
    }

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        production_mode: bool = False,
    ) -> None:
        """
        CourtViewError 초기화

        Args:
            message: 사용자 친화적 에러 메시지
            error_code: 5자리 에러 코드 (CV000~CV999), None이면 클래스 변수 사용
            context: 에러 발생 시점의 상태 정보 (<512 bytes)
            original_error: 원본 예외 (체이닝용)
            production_mode: 프로덕션 모드 여부 (스택 트레이스 단순화)
        """
        super().__init__(message)

        self.message: str = message
        self.error_code: str = error_code or self.ERROR_CODE
        self.original_error: Optional[Exception] = original_error
        self.timestamp: datetime = datetime.now()
        self.production_mode: bool = production_mode

        # 컨텍스트 처리 (민감 정보 필터링 + 크기 제한)
        if context:
            sanitized = self._sanitize_context(context)
            self.context = self._truncate_context(sanitized)
        else:
            self.context: Dict[str, Any] = {}

        # 스택 트레이스 캡처
        self.stack_trace: str = self._capture_stack_trace()

        # 플랫폼 정보 (캐싱)
        self.platform_info: Dict[str, str] = self._get_platform_info()

    def __str__(self) -> str:
        """
        에러 메시지 포맷팅 (개발자용)

        Returns:
            "[CV101] YAML 파일을 찾을 수 없습니다"
        """
        return f"[{self.error_code}] {self.message}"

    def __repr__(self) -> str:
        """
        개발자용 상세 정보

        Returns:
            "CourtViewError(error_code='CV101', message='...', context={...})"
        """
        context_repr = f", context={self.context}" if self.context else ""
        return f"{self.__class__.__name__}(error_code='{self.error_code}', message='{self.message}'{context_repr})"

    def to_dict(self) -> Dict[str, Any]:
        """
        딕셔너리로 직렬화 (로깅, API 응답용)

        Returns:
            {
                "error_code": "CV101",
                "message": "...",
                "context": {...},
                "timestamp": "2025-01-15T14:23:45.123456",
                "stack_trace": "...",
                "platform_info": {...},
                "original_error": "..."
            }
        """
        result: Dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "platform_info": self.platform_info,
        }

        # 프로덕션 모드가 아닐 때만 스택 트레이스 포함
        if not self.production_mode:
            result["stack_trace"] = self.stack_trace

        # 원본 예외 정보 포함
        if self.original_error:
            result["original_error"] = {
                "type": type(self.original_error).__name__,
                "message": str(self.original_error),
            }

        return result

    def get_user_message(self) -> str:
        """
        사용자에게 표시할 간단한 메시지 (기술 정보 제외)

        Returns:
            "파일을 찾을 수 없습니다. 설정을 확인해주세요."
        """
        return self.USER_FRIENDLY_MESSAGES.get(
            self.error_code,
            "오류가 발생했습니다. 관리자에게 문의하세요."
        )

    # ==================== Private Methods ====================

    def _capture_stack_trace(self) -> str:
        """
        현재 스택 트레이스 캡처

        프로덕션 모드:
            - 최대 3 프레임
        개발 모드:
            - 최대 10 프레임

        Returns:
            "Traceback (most recent call last):\n  File ..."
        """
        # 프레임 제한
        limit = 3 if self.production_mode else 10

        # 스택 트레이스 캡처
        tb = traceback.format_exc(limit=limit)

        # 크기 제한 (500 bytes)
        if len(tb) > 500:
            tb = tb[:497] + "..."

        return tb

    def _get_platform_info(self) -> Dict[str, str]:
        """
        실행 환경 정보 수집 (캐싱)

        Returns:
            {
                "os": "Windows",
                "python_version": "3.8.10",
                "architecture": "AMD64"
            }
        """
        # 캐시 확인
        if CourtViewError._PLATFORM_INFO_CACHE is not None:
            return CourtViewError._PLATFORM_INFO_CACHE

        # 플랫폼 정보 수집
        info = {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "architecture": platform.machine(),
        }

        # 캐시 저장
        CourtViewError._PLATFORM_INFO_CACHE = info

        return info

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        컨텍스트에서 민감 정보 제거

        Args:
            context: 원본 컨텍스트

        Returns:
            민감 정보가 제거된 컨텍스트
        """
        sanitized: Dict[str, Any] = {}

        for key, value in context.items():
            # 민감한 키 필터링
            if key.lower() in self.SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            # 중첩된 딕셔너리 재귀 처리
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_context(value)
            else:
                sanitized[key] = value

        return sanitized

    def _truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        컨텍스트 크기 제한 (<512 bytes)

        큰 값은 요약으로 대체하여 메모리 사용량 최소화

        Args:
            context: 원본 컨텍스트

        Returns:
            크기 제한된 컨텍스트
        """
        # 컨텍스트 크기 측정
        context_str = str(context)
        context_size = len(context_str.encode('utf-8'))

        # 512 bytes 이하면 그대로 반환
        if context_size <= 512:
            return context

        # 크기 초과 시 값 요약
        truncated: Dict[str, Any] = {}

        for key, value in context.items():
            # 문자열 값 길이 제한 (100 chars)
            if isinstance(value, str) and len(value) > 100:
                truncated[key] = value[:97] + "..."
            # 리스트 요소 개수 제한 (10개)
            elif isinstance(value, list) and len(value) > 10:
                truncated[key] = value[:10] + ["..."]
            # 딕셔너리 키 개수 제한 (10개)
            elif isinstance(value, dict) and len(value) > 10:
                truncated[key] = {
                    k: v for i, (k, v) in enumerate(value.items()) if i < 10
                }
                truncated[key]["..."] = f"({len(value) - 10} more)"
            else:
                truncated[key] = value

        # 재측정 후 여전히 크면 강제 잘라내기
        truncated_size = len(str(truncated).encode('utf-8'))
        if truncated_size > 512:
            # 전체 컨텍스트를 요약으로 대체
            return {
                "_truncated": True,
                "_original_size": context_size,
                "_keys": list(context.keys())[:10],
            }

        return truncated


# ==================== 에러 코드 범위 문서화 ====================
"""
에러 코드 범위:

CV000: 기본 에러 (base.py)
CV1XX: 설정 에러 (validation.py)
  - CV101: 설정 파일 없음
  - CV102: 설정 파일 파싱 실패
  - CV103: 설정 값 검증 실패

CV2XX: 하드웨어 에러 (hardware.py)
  - CV201: GPU 에러
  - CV202: 카메라 에러
  - CV203: 하드웨어 초기화 실패

CV3XX: 데이터 검증 에러 (validation.py)
  - CV301: 입력 데이터 검증 실패
  - CV302: 데이터 형식 오류
  - CV303: 데이터 범위 초과

CV4XX: 파일 시스템 에러 (base.py)
  - CV401: 파일 접근 거부
  - CV402: 파일 없음
  - CV403: 디스크 공간 부족

CV5XX: 네트워크 에러 (Desktop 미사용)
CV6XX: 데이터베이스 에러 (Desktop 미사용)

CV7XX: 모델 추론 에러 (Layer 3+)
  - CV701: 모델 로드 실패
  - CV702: 추론 실패
  - CV703: 모델 파일 손상

CV8XX: 파이프라인 에러 (Layer 6+)
  - CV801: 파이프라인 실패
  - CV802: 파이프라인 타임아웃
  - CV803: 파이프라인 단계 실패

CV9XX: 시스템 에러 (base.py)
  - CV901: 메모리 부족
  - CV902: 시스템 리소스 부족
  - CV903: 시스템 호환성 문제
"""
