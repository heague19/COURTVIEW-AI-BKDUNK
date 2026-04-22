# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/exceptions
파일: infrastructure_exceptions.py
설명: 인프라스트럭처 관련 예외 클래스 정의
      - 데이터베이스, 캐시, 큐, 스토리지, 스트림, 외부 서비스
      - 비디오 처리, 카메라, 캘리브레이션, 좌표변환, 설정
      - 61개 예외 클래스 (Retryable 17개, NonRetryable 10개, Critical 1개, 기반 33개)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-18
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import re
from typing import Any

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    CriticalException,
    NonRetryableException,
    RetryableException,
)


# =============================================================================
# 인프라 기본 예외
# =============================================================================
class InfrastructureException(CourtViewException):
    """
    인프라스트럭처 관련 기본 예외.

    데이터베이스, 캐시, 큐, 스토리지 등 인프라 관련 예외의 기반 클래스입니다.
    """

    def __init__(
        self,
        message: str = "인프라스트럭처 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.INFRASTRUCTURE_ERROR,
        **kwargs: Any,
    ) -> None:
        """
        인프라 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)


class TimeoutException(RetryableException):
    """
    타임아웃 예외.

    작업이 설정된 시간 내에 완료되지 않은 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "작업 시간이 초과되었습니다",
        timeout_seconds: float | None = None,
        operation: str | None = None,
        retry_after: float = 1.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        타임아웃 예외 초기화.

        Args:
            message: 오류 메시지
            timeout_seconds: 타임아웃 설정값 (초)
            operation: 수행 중인 작업
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds
        if operation:
            self.details["operation"] = operation


class CircuitBreakerOpenException(NonRetryableException):
    """
    서킷 브레이커 OPEN 상태 예외.

    서킷 브레이커가 열린 상태에서 요청 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "서킷 브레이커가 열린 상태입니다",
        circuit_name: str | None = None,
        reset_timeout_seconds: float | None = None,
        failure_count: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        서킷 브레이커 예외 초기화.

        Args:
            message: 오류 메시지
            circuit_name: 서킷 브레이커 이름
            reset_timeout_seconds: 리셋 타임아웃 (초)
            failure_count: 실패 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            **kwargs,
        )

        if circuit_name:
            self.details["circuit_name"] = circuit_name
        if reset_timeout_seconds:
            self.details["reset_timeout_seconds"] = reset_timeout_seconds
        if failure_count:
            self.details["failure_count"] = failure_count


# =============================================================================
# 데이터베이스 예외
# =============================================================================
class DatabaseException(CourtViewException):
    """
    데이터베이스 관련 기본 예외.

    모든 데이터베이스 예외의 기반 클래스로 사용됩니다.
    """

    def __init__(
        self,
        message: str = "데이터베이스 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
        operation: str | None = None,
        table: str | None = None,
        query: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        데이터베이스 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            operation: 수행 중인 작업 (SELECT, INSERT, UPDATE, DELETE 등)
            table: 대상 테이블명
            query: 실행한 쿼리 (민감 정보 제외)
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)
        self.operation = operation
        self.table = table
        self.query = self._sanitize_query(query) if query else None

        if operation:
            self.details["operation"] = operation
        if table:
            self.details["table"] = table
        if self.query:
            self.details["query_preview"] = self.query[:100] + "..." if len(self.query) > 100 else self.query

    def _sanitize_query(self, query: str) -> str:
        """
        쿼리에서 민감 정보 제거.

        Args:
            query: 원본 쿼리

        Returns:
            정제된 쿼리
        """
        # 비밀번호, 토큰 등 민감 정보 마스킹
        patterns = [
            (r"password\s*=\s*'[^']*'", "password='***'"),
            (r"token\s*=\s*'[^']*'", "token='***'"),
            (r"secret\s*=\s*'[^']*'", "secret='***'"),
            (r"api_key\s*=\s*'[^']*'", "api_key='***'"),
        ]

        sanitized = query
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized


class DatabaseConnectionException(RetryableException):
    """
    데이터베이스 연결 실패 예외.

    네트워크 문제, 서버 과부하 등의 이유로 재시도가 가능합니다.
    """

    def __init__(
        self,
        message: str = "데이터베이스 연결에 실패했습니다",
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        retry_after: float = 1.0,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        데이터베이스 연결 예외 초기화.

        Args:
            message: 오류 메시지
            host: 데이터베이스 호스트
            port: 데이터베이스 포트
            database: 데이터베이스명
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_CONNECTION_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port
        if database:
            self.details["database"] = database


class DatabaseTimeoutException(RetryableException):
    """
    데이터베이스 쿼리 타임아웃 예외.

    쿼리 실행 시간이 설정된 시간을 초과한 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "데이터베이스 쿼리 타임아웃",
        timeout_seconds: float | None = None,
        query: str | None = None,
        retry_after: float = 2.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        데이터베이스 타임아웃 예외 초기화.

        Args:
            message: 오류 메시지
            timeout_seconds: 타임아웃 설정값 (초)
            query: 실행한 쿼리
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_TIMEOUT,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds
        if query:
            # 쿼리 미리보기만 포함 (전체 쿼리는 보안상 제외)
            self.details["query_preview"] = query[:50] + "..." if len(query) > 50 else query


class DatabaseIntegrityException(NonRetryableException):
    """
    데이터베이스 무결성 위반 예외.

    유니크 제약, 외래키 제약 등의 무결성 규칙 위반 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "데이터베이스 무결성 제약 조건 위반",
        constraint_name: str | None = None,
        constraint_type: str | None = None,
        table: str | None = None,
        column: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        데이터베이스 무결성 예외 초기화.

        Args:
            message: 오류 메시지
            constraint_name: 제약 조건명
            constraint_type: 제약 조건 타입 (UNIQUE, FOREIGN_KEY, CHECK 등)
            table: 대상 테이블명
            column: 대상 컬럼명
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_INTEGRITY_ERROR,
            **kwargs,
        )

        if constraint_name:
            self.details["constraint_name"] = constraint_name
        if constraint_type:
            self.details["constraint_type"] = constraint_type
        if table:
            self.details["table"] = table
        if column:
            self.details["column"] = column


class TransactionException(NonRetryableException):
    """
    데이터베이스 트랜잭션 오류 예외.

    트랜잭션 충돌, 데드락 등의 상황에서 발생합니다.
    """

    def __init__(
        self,
        message: str = "데이터베이스 트랜잭션 오류",
        transaction_id: str | None = None,
        isolation_level: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        트랜잭션 예외 초기화.

        Args:
            message: 오류 메시지
            transaction_id: 트랜잭션 ID
            isolation_level: 격리 수준
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_TRANSACTION_FAILED,
            **kwargs,
        )

        if transaction_id:
            self.details["transaction_id"] = transaction_id
        if isolation_level:
            self.details["isolation_level"] = isolation_level


class RecordNotFoundException(NonRetryableException):
    """
    데이터베이스 레코드 미발견 예외.

    요청한 레코드가 존재하지 않는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "요청한 레코드를 찾을 수 없습니다",
        table: str | None = None,
        record_id: str | int | None = None,
        search_criteria: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        레코드 미발견 예외 초기화.

        Args:
            message: 오류 메시지
            table: 대상 테이블명
            record_id: 검색한 레코드 ID
            search_criteria: 검색 조건
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_RECORD_NOT_FOUND,
            **kwargs,
        )

        if table:
            self.details["table"] = table
        if record_id:
            self.details["record_id"] = str(record_id)
        if search_criteria:
            # 민감 정보 필터링
            safe_criteria = {
                k: v for k, v in search_criteria.items()
                if k.lower() not in ("password", "token", "secret", "key")
            }
            self.details["search_criteria"] = safe_criteria


class ConnectionPoolException(RetryableException):
    """
    커넥션 풀 예외.

    데이터베이스 또는 캐시 커넥션 풀에서 발생하는 오류에 사용됩니다.
    풀 고갈, 커넥션 획득 타임아웃 등의 상황을 처리합니다.
    """

    def __init__(
        self,
        message: str = "커넥션 풀 오류가 발생했습니다",
        pool_name: str | None = None,
        pool_size: int | None = None,
        active_connections: int | None = None,
        waiting_requests: int | None = None,
        retry_after: float = 1.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        커넥션 풀 예외 초기화.

        Args:
            message: 오류 메시지
            pool_name: 커넥션 풀 이름
            pool_size: 풀 크기
            active_connections: 활성 커넥션 수
            waiting_requests: 대기 중인 요청 수
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_CONNECTION_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if pool_name:
            self.details["pool_name"] = pool_name
        if pool_size is not None:
            self.details["pool_size"] = pool_size
        if active_connections is not None:
            self.details["active_connections"] = active_connections
        if waiting_requests is not None:
            self.details["waiting_requests"] = waiting_requests

    @classmethod
    def pool_exhausted(
        cls,
        pool_name: str,
        pool_size: int,
        active_connections: int,
    ) -> "ConnectionPoolException":
        """
        풀 고갈 예외 생성.

        Args:
            pool_name: 커넥션 풀 이름
            pool_size: 풀 크기
            active_connections: 활성 커넥션 수

        Returns:
            ConnectionPoolException 인스턴스
        """
        return cls(
            message=f"커넥션 풀이 고갈되었습니다: {pool_name} ({active_connections}/{pool_size})",
            pool_name=pool_name,
            pool_size=pool_size,
            active_connections=active_connections,
            retry_after=2.0,
        )

    @classmethod
    def acquisition_timeout(
        cls,
        pool_name: str,
        timeout_seconds: float,
    ) -> "ConnectionPoolException":
        """
        커넥션 획득 타임아웃 예외 생성.

        Args:
            pool_name: 커넥션 풀 이름
            timeout_seconds: 타임아웃 시간

        Returns:
            ConnectionPoolException 인스턴스
        """
        return cls(
            message=f"커넥션 획득 시간 초과: {pool_name} ({timeout_seconds}초)",
            pool_name=pool_name,
        )


# =============================================================================
# 캐시 예외
# =============================================================================
class CacheException(CourtViewException):
    """
    캐시 관련 기본 예외.

    Redis, Memcached 등의 캐시 시스템 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "캐시 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.CACHE_ERROR,
        cache_key: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        캐시 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            cache_key: 캐시 키
            operation: 수행 중인 작업 (GET, SET, DELETE 등)
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if cache_key:
            # 캐시 키에서 민감 정보 마스킹
            self.details["cache_key"] = self._mask_sensitive_key(cache_key)
        if operation:
            self.details["operation"] = operation

    def _mask_sensitive_key(self, key: str) -> str:
        """
        캐시 키의 민감 정보 마스킹.

        Args:
            key: 원본 캐시 키

        Returns:
            마스킹된 캐시 키
        """
        sensitive_patterns = ["token:", "session:", "auth:", "secret:"]

        for pattern in sensitive_patterns:
            if pattern in key.lower():
                # 패턴 이후 부분 마스킹
                idx = key.lower().find(pattern)
                prefix = key[:idx + len(pattern)]
                return prefix + "***"

        return key


class CacheConnectionException(RetryableException):
    """
    캐시 연결 실패 예외.

    Redis 등의 캐시 서버에 연결할 수 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "캐시 서버 연결에 실패했습니다",
        host: str | None = None,
        port: int | None = None,
        retry_after: float = 0.5,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        캐시 연결 예외 초기화.

        Args:
            message: 오류 메시지
            host: 캐시 서버 호스트
            port: 캐시 서버 포트
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_CONNECTION_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port


class CacheKeyNotFoundException(NonRetryableException):
    """
    캐시 키 미발견 예외.

    요청한 캐시 키가 존재하지 않는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "캐시 키를 찾을 수 없습니다",
        cache_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        캐시 키 미발견 예외 초기화.

        Args:
            message: 오류 메시지
            cache_key: 찾으려던 캐시 키
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_KEY_NOT_FOUND,
            **kwargs,
        )

        if cache_key:
            self.details["cache_key"] = cache_key


class CacheSerializationException(NonRetryableException):
    """
    캐시 직렬화/역직렬화 오류 예외.

    데이터를 캐시에 저장하거나 읽을 때 변환 오류가 발생한 경우입니다.
    """

    def __init__(
        self,
        message: str = "캐시 데이터 직렬화/역직렬화 오류",
        operation: str | None = None,
        data_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        캐시 직렬화 예외 초기화.

        Args:
            message: 오류 메시지
            operation: 수행 중인 작업 (serialize, deserialize)
            data_type: 데이터 타입
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_SERIALIZATION_ERROR,
            **kwargs,
        )

        if operation:
            self.details["operation"] = operation
        if data_type:
            self.details["data_type"] = data_type


class RedisException(CacheException):
    """
    Redis 관련 예외.

    Redis 캐시 서버에서 발생하는 특정 오류에 사용됩니다.
    클러스터 모드, 레플리케이션, Lua 스크립트 오류 등을 포함합니다.
    """

    def __init__(
        self,
        message: str = "Redis 오류가 발생했습니다",
        redis_command: str | None = None,
        cluster_node: str | None = None,
        error_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Redis 예외 초기화.

        Args:
            message: 오류 메시지
            redis_command: 실행한 Redis 명령어
            cluster_node: 클러스터 노드 정보
            error_type: Redis 오류 타입 (MOVED, ASK, CLUSTERDOWN 등)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            **kwargs,
        )

        self.details["cache_type"] = "redis"

        if redis_command:
            self.details["redis_command"] = redis_command
        if cluster_node:
            self.details["cluster_node"] = cluster_node
        if error_type:
            self.details["error_type"] = error_type


# =============================================================================
# 메시지 큐 예외
# =============================================================================
class QueueException(CourtViewException):
    """
    메시지 큐 관련 기본 예외.

    Celery, RabbitMQ 등의 메시지 큐 시스템 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "메시지 큐 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.QUEUE_ERROR,
        queue_name: str | None = None,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        메시지 큐 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            queue_name: 큐 이름
            task_id: 태스크 ID
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if queue_name:
            self.details["queue_name"] = queue_name
        if task_id:
            self.details["task_id"] = task_id


class QueueConnectionException(RetryableException):
    """
    메시지 큐 연결 실패 예외.

    브로커에 연결할 수 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "메시지 큐 연결에 실패했습니다",
        broker_url: str | None = None,
        retry_after: float = 1.0,
        max_retries: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        메시지 큐 연결 예외 초기화.

        Args:
            message: 오류 메시지
            broker_url: 브로커 URL (민감 정보 제외)
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.QUEUE_CONNECTION_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if broker_url:
            # URL에서 비밀번호 제거
            import re
            safe_url = re.sub(r"://[^:]+:[^@]+@", "://***:***@", broker_url)
            self.details["broker_url"] = safe_url


class TaskEnqueueException(RetryableException):
    """
    태스크 큐 등록 실패 예외.

    분석 태스크를 큐에 등록할 수 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "태스크를 큐에 등록할 수 없습니다",
        task_name: str | None = None,
        queue_name: str | None = None,
        retry_after: float = 0.5,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        태스크 등록 예외 초기화.

        Args:
            message: 오류 메시지
            task_name: 태스크명
            queue_name: 대상 큐
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.QUEUE_PUBLISH_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if task_name:
            self.details["task_name"] = task_name
        if queue_name:
            self.details["queue_name"] = queue_name


class TaskExecutionException(CourtViewException):
    """
    태스크 실행 중 오류 예외.

    백그라운드 태스크 실행 중 오류가 발생한 경우입니다.
    """

    def __init__(
        self,
        message: str = "태스크 실행 중 오류가 발생했습니다",
        task_id: str | None = None,
        task_name: str | None = None,
        worker_id: str | None = None,
        execution_time: float | None = None,
        **kwargs: Any,
    ) -> None:
        """
        태스크 실행 예외 초기화.

        Args:
            message: 오류 메시지
            task_id: 태스크 ID
            task_name: 태스크명
            worker_id: 워커 ID
            execution_time: 실행 시간 (초)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.QUEUE_CONSUME_FAILED,
            **kwargs,
        )

        if task_id:
            self.details["task_id"] = task_id
        if task_name:
            self.details["task_name"] = task_name
        if worker_id:
            self.details["worker_id"] = worker_id
        if execution_time:
            self.details["execution_time"] = execution_time


class TaskTimeoutException(RetryableException):
    """
    태스크 실행 타임아웃 예외.

    태스크가 설정된 시간 내에 완료되지 않은 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "태스크 실행 시간이 초과되었습니다",
        task_id: str | None = None,
        timeout_seconds: float | None = None,
        retry_after: float = 5.0,
        max_retries: int = 2,
        **kwargs: Any,
    ) -> None:
        """
        태스크 타임아웃 예외 초기화.

        Args:
            message: 오류 메시지
            task_id: 태스크 ID
            timeout_seconds: 타임아웃 설정값 (초)
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.QUEUE_TIMEOUT,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if task_id:
            self.details["task_id"] = task_id
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class WorkerException(CourtViewException):
    """
    워커 관련 기본 예외.

    백그라운드 워커 작업 처리 과정에서 발생하는 오류에 사용됩니다.
    """

    def __init__(
        self,
        message: str = "워커 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.QUEUE_ERROR,
        worker_id: str | None = None,
        worker_type: str | None = None,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        워커 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            worker_id: 워커 ID
            worker_type: 워커 타입
            task_id: 태스크 ID
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if worker_id:
            self.details["worker_id"] = worker_id
        if worker_type:
            self.details["worker_type"] = worker_type
        if task_id:
            self.details["task_id"] = task_id


class NotificationException(CourtViewException):
    """
    알림 관련 예외.

    푸시 알림, 이메일, Slack 등의 알림 발송 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "알림 발송에 실패했습니다",
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        notification_type: str | None = None,
        recipient: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        알림 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            notification_type: 알림 유형 (push, email, slack, webhook)
            recipient: 수신자
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if notification_type:
            self.details["notification_type"] = notification_type
        if recipient:
            self.details["recipient"] = recipient


class AlertDeliveryException(RetryableException):
    """
    알림 발송 실패 예외.

    Slack, Email, PagerDuty, Webhook 등의 알림 채널로 메시지 발송이 실패했을 때 발생합니다.
    네트워크 오류, 서비스 장애 등 일시적 문제로 인한 실패 시 재시도가 가능합니다.
    """

    def __init__(
        self,
        message: str = "알림 발송에 실패했습니다",
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        channel: str | None = None,
        alert_id: str | None = None,
        recipient: str | None = None,
        http_status: int | None = None,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        """
        알림 발송 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            channel: 알림 채널 (slack, email, pagerduty, webhook)
            alert_id: 알림 고유 ID
            recipient: 수신자 정보
            http_status: HTTP 응답 상태 코드 (웹훅의 경우)
            retry_after: 재시도 대기 시간 (초)
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if channel:
            self.details["channel"] = channel
        if alert_id:
            self.details["alert_id"] = alert_id
        if recipient:
            self.details["recipient"] = recipient
        if http_status is not None:
            self.details["http_status"] = http_status
        if retry_after is not None:
            self.details["retry_after"] = retry_after


class AlertConfigurationException(NonRetryableException):
    """
    알림 설정 오류 예외.

    알림 채널 설정이 잘못되었거나 필수 인증 정보가 누락된 경우 발생합니다.
    설정 오류이므로 재시도해도 해결되지 않으며, 설정 수정이 필요합니다.
    """

    def __init__(
        self,
        message: str = "알림 설정이 올바르지 않습니다",
        error_code: ErrorCode = ErrorCode.CONFIGURATION_INVALID,
        channel: str | None = None,
        config_key: str | None = None,
        expected_type: str | None = None,
        actual_value: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """
        알림 설정 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            channel: 알림 채널 (slack, email, pagerduty, webhook)
            config_key: 잘못된 설정 키
            expected_type: 기대하는 타입/형식
            actual_value: 실제 입력된 값
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if channel:
            self.details["channel"] = channel
        if config_key:
            self.details["config_key"] = config_key
        if expected_type:
            self.details["expected_type"] = expected_type
        if actual_value is not None:
            self.details["actual_value"] = str(actual_value)


class CleanupException(CourtViewException):
    """
    정리 작업 관련 예외.

    임시 파일 삭제, 만료 데이터 정리 등의 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "정리 작업에 실패했습니다",
        error_code: ErrorCode = ErrorCode.STORAGE_ERROR,
        cleanup_type: str | None = None,
        target_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        정리 작업 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            cleanup_type: 정리 유형 (temp_files, expired_data, s3, cache)
            target_path: 대상 경로
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if cleanup_type:
            self.details["cleanup_type"] = cleanup_type
        if target_path:
            self.details["target_path"] = target_path


class EventBusException(CourtViewException):
    """
    이벤트 버스 관련 예외.

    이벤트 발행, 구독, 처리 과정에서 발생하는 오류에 사용됩니다.
    """

    def __init__(
        self,
        message: str = "이벤트 버스 오류가 발생했습니다",
        event_type: str | None = None,
        event_id: str | None = None,
        handler_name: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        이벤트 버스 예외 초기화.

        Args:
            message: 오류 메시지
            event_type: 이벤트 타입
            event_id: 이벤트 ID
            handler_name: 핸들러 이름
            operation: 수행 중인 작업 (publish, subscribe, handle)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.QUEUE_ERROR,
            **kwargs,
        )

        if event_type:
            self.details["event_type"] = event_type
        if event_id:
            self.details["event_id"] = event_id
        if handler_name:
            self.details["handler_name"] = handler_name
        if operation:
            self.details["operation"] = operation

    @classmethod
    def publish_failed(
        cls,
        event_type: str,
        event_id: str | None = None,
        cause: Exception | None = None,
    ) -> "EventBusException":
        """
        이벤트 발행 실패 예외 생성.

        Args:
            event_type: 이벤트 타입
            event_id: 이벤트 ID
            cause: 원인 예외

        Returns:
            EventBusException 인스턴스
        """
        return cls(
            message=f"이벤트 발행에 실패했습니다: {event_type}",
            event_type=event_type,
            event_id=event_id,
            operation="publish",
            cause=cause,
        )

    @classmethod
    def handler_failed(
        cls,
        event_type: str,
        handler_name: str,
        cause: Exception | None = None,
    ) -> "EventBusException":
        """
        이벤트 핸들러 실패 예외 생성.

        Args:
            event_type: 이벤트 타입
            handler_name: 핸들러 이름
            cause: 원인 예외

        Returns:
            EventBusException 인스턴스
        """
        return cls(
            message=f"이벤트 핸들러 실행 실패: {handler_name}",
            event_type=event_type,
            handler_name=handler_name,
            operation="handle",
            cause=cause,
        )


# =============================================================================
# 스토리지 예외 (S3, 로컬 파일 시스템)
# =============================================================================
class StorageException(CourtViewException):
    """
    스토리지 관련 기본 예외.

    S3, 로컬 파일 시스템 등의 저장소 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "스토리지 오류가 발생했습니다",
        error_code: ErrorCode = ErrorCode.STORAGE_ERROR,
        storage_type: str | None = None,
        file_path: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        스토리지 예외 초기화.

        Args:
            message: 오류 메시지
            error_code: 오류 코드
            storage_type: 스토리지 타입 (s3, local, etc.)
            file_path: 파일 경로
            operation: 수행 중인 작업 (read, write, delete, etc.)
            **kwargs: 추가 매개변수
        """
        super().__init__(message=message, error_code=error_code, **kwargs)

        if storage_type:
            self.details["storage_type"] = storage_type
        if file_path:
            self.details["file_path"] = file_path
        if operation:
            self.details["operation"] = operation


class S3Exception(StorageException):
    """
    AWS S3 관련 예외.

    S3 버킷 접근, 파일 업로드/다운로드 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "S3 스토리지 오류가 발생했습니다",
        bucket: str | None = None,
        key: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        S3 예외 초기화.

        Args:
            message: 오류 메시지
            bucket: S3 버킷명
            key: S3 객체 키
            operation: 수행 중인 작업
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_ERROR,
            storage_type="s3",
            operation=operation,
            **kwargs,
        )

        if bucket:
            self.details["bucket"] = bucket
        if key:
            self.details["key"] = key


class S3UploadException(RetryableException):
    """
    S3 업로드 실패 예외.

    파일을 S3에 업로드할 수 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "S3 파일 업로드에 실패했습니다",
        bucket: str | None = None,
        key: str | None = None,
        file_size: int | None = None,
        retry_after: float = 2.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        S3 업로드 예외 초기화.

        Args:
            message: 오류 메시지
            bucket: S3 버킷명
            key: S3 객체 키
            file_size: 파일 크기 (bytes)
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_UPLOAD_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        self.details["storage_type"] = "s3"
        self.details["operation"] = "upload"

        if bucket:
            self.details["bucket"] = bucket
        if key:
            self.details["key"] = key
        if file_size:
            self.details["file_size_bytes"] = file_size
            self.details["file_size_mb"] = round(file_size / (1024 * 1024), 2)


class S3DownloadException(RetryableException):
    """
    S3 다운로드 실패 예외.

    S3에서 파일을 다운로드할 수 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "S3 파일 다운로드에 실패했습니다",
        bucket: str | None = None,
        key: str | None = None,
        retry_after: float = 2.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        S3 다운로드 예외 초기화.

        Args:
            message: 오류 메시지
            bucket: S3 버킷명
            key: S3 객체 키
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_DOWNLOAD_FAILED,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        self.details["storage_type"] = "s3"
        self.details["operation"] = "download"

        if bucket:
            self.details["bucket"] = bucket
        if key:
            self.details["key"] = key


class S3ObjectNotFoundException(NonRetryableException):
    """
    S3 객체 미발견 예외.

    요청한 S3 객체가 존재하지 않는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "S3 객체를 찾을 수 없습니다",
        bucket: str | None = None,
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        S3 객체 미발견 예외 초기화.

        Args:
            message: 오류 메시지
            bucket: S3 버킷명
            key: S3 객체 키
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_FILE_NOT_FOUND,
            **kwargs,
        )

        self.details["storage_type"] = "s3"

        if bucket:
            self.details["bucket"] = bucket
        if key:
            self.details["key"] = key


class S3PermissionException(NonRetryableException):
    """
    S3 권한 오류 예외.

    S3 버킷이나 객체에 대한 권한이 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "S3 접근 권한이 없습니다",
        bucket: str | None = None,
        key: str | None = None,
        required_permission: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        S3 권한 예외 초기화.

        Args:
            message: 오류 메시지
            bucket: S3 버킷명
            key: S3 객체 키
            required_permission: 필요한 권한 (s3:GetObject, s3:PutObject 등)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.PERMISSION_DENIED,
            **kwargs,
        )

        self.details["storage_type"] = "s3"

        if bucket:
            self.details["bucket"] = bucket
        if key:
            self.details["key"] = key
        if required_permission:
            self.details["required_permission"] = required_permission


class MetadataExtractionException(StorageException):
    """
    메타데이터 추출 관련 예외.

    비디오/이미지/오디오 메타데이터 추출 실패 시 발생합니다.
    FFprobe, OpenCV 등 외부 도구 오류를 포함합니다.
    """

    def __init__(
        self,
        message: str = "메타데이터 추출에 실패했습니다",
        file_path: str | None = None,
        media_type: str | None = None,
        extraction_method: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        메타데이터 추출 예외 초기화.

        Args:
            message: 오류 메시지
            file_path: 파일 경로
            media_type: 미디어 타입 (video, image, audio)
            extraction_method: 추출 방법 (ffprobe, opencv, pillow)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_ERROR,
            storage_type="metadata",
            file_path=file_path,
            operation="extract_metadata",
            **kwargs,
        )

        if media_type:
            self.details["media_type"] = media_type
        if extraction_method:
            self.details["extraction_method"] = extraction_method

    @classmethod
    def ffprobe_failed(
        cls,
        file_path: str,
        error_output: str | None = None,
    ) -> "MetadataExtractionException":
        """
        FFprobe 실행 실패 예외 생성.

        Args:
            file_path: 파일 경로
            error_output: FFprobe 에러 출력

        Returns:
            MetadataExtractionException 인스턴스
        """
        instance = cls(
            message=f"FFprobe 메타데이터 추출 실패: {file_path}",
            file_path=file_path,
            extraction_method="ffprobe",
        )
        if error_output:
            instance.details["ffprobe_error"] = error_output[:500]
        return instance

    @classmethod
    def opencv_failed(
        cls,
        file_path: str,
        reason: str | None = None,
    ) -> "MetadataExtractionException":
        """
        OpenCV 메타데이터 추출 실패 예외 생성.

        Args:
            file_path: 파일 경로
            reason: 실패 사유

        Returns:
            MetadataExtractionException 인스턴스
        """
        instance = cls(
            message=f"OpenCV 메타데이터 추출 실패: {file_path}",
            file_path=file_path,
            extraction_method="opencv",
        )
        if reason:
            instance.details["reason"] = reason
        return instance

    @classmethod
    def unsupported_format(
        cls,
        file_path: str,
        detected_format: str | None = None,
    ) -> "MetadataExtractionException":
        """
        지원하지 않는 포맷 예외 생성.

        Args:
            file_path: 파일 경로
            detected_format: 감지된 포맷

        Returns:
            MetadataExtractionException 인스턴스
        """
        instance = cls(
            message=f"지원하지 않는 미디어 포맷: {file_path}",
            file_path=file_path,
        )
        if detected_format:
            instance.details["detected_format"] = detected_format
        return instance


class LocalStorageException(StorageException):
    """
    로컬 파일 시스템 관련 예외.

    로컬 파일 읽기/쓰기 오류 시 발생합니다.
    """

    def __init__(
        self,
        message: str = "로컬 스토리지 오류가 발생했습니다",
        file_path: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        로컬 스토리지 예외 초기화.

        Args:
            message: 오류 메시지
            file_path: 파일 경로
            operation: 수행 중인 작업
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_ERROR,
            storage_type="local",
            file_path=file_path,
            operation=operation,
            **kwargs,
        )


class DiskSpaceException(CriticalException):
    """
    디스크 공간 부족 예외.

    파일 저장을 위한 디스크 공간이 부족한 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "디스크 공간이 부족합니다",
        required_bytes: int | None = None,
        available_bytes: int | None = None,
        mount_point: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        디스크 공간 예외 초기화.

        Args:
            message: 오류 메시지
            required_bytes: 필요한 공간 (bytes)
            available_bytes: 사용 가능 공간 (bytes)
            mount_point: 마운트 포인트
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_QUOTA_EXCEEDED,
            alert_required=True,
            severity=5,
            **kwargs,
        )

        self.details["storage_type"] = "local"

        if required_bytes:
            self.details["required_mb"] = round(required_bytes / (1024 * 1024), 2)
        if available_bytes:
            self.details["available_mb"] = round(available_bytes / (1024 * 1024), 2)
        if mount_point:
            self.details["mount_point"] = mount_point


class FilePermissionException(NonRetryableException):
    """
    파일 권한 오류 예외.

    파일이나 디렉토리에 대한 접근 권한이 없는 경우 발생합니다.
    """

    def __init__(
        self,
        message: str = "파일 접근 권한이 없습니다",
        file_path: str | None = None,
        required_permission: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        파일 권한 예외 초기화.

        Args:
            message: 오류 메시지
            file_path: 파일 경로
            required_permission: 필요한 권한 (read, write, execute)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.STORAGE_PERMISSION_DENIED,
            **kwargs,
        )

        self.details["storage_type"] = "local"

        if file_path:
            self.details["file_path"] = file_path
        if required_permission:
            self.details["required_permission"] = required_permission


# =============================================================================
# 스트림 예외
# =============================================================================
class StreamException(RetryableException):
    """
    스트림 처리 기본 예외.

    RTSP, HLS, RTMP 등 스트림 처리 중 발생하는 예외의 기반 클래스입니다.
    """

    def __init__(
        self,
        message: str = "스트림 처리 중 오류가 발생했습니다",
        stream_url: str | None = None,
        stream_type: str | None = None,
        error_code: ErrorCode = ErrorCode.STREAM_ERROR,
        retry_after: float = 1.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        스트림 예외 초기화.

        Args:
            message: 오류 메시지
            stream_url: 스트림 URL
            stream_type: 스트림 타입 (RTSP, HLS, RTMP 등)
            error_code: 오류 코드
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=error_code,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if stream_url:
            # URL에서 인증 정보 제거 (민감 정보 보호)
            sanitized_url = self._sanitize_stream_url(stream_url)
            self.details["stream_url"] = sanitized_url
        if stream_type:
            self.details["stream_type"] = stream_type

    @staticmethod
    def _sanitize_stream_url(url: str) -> str:
        """스트림 URL에서 민감 정보 제거."""
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(url)
            # 사용자 정보 제거
            if "@" in parsed.netloc:
                host = parsed.netloc.split("@")[-1]
            else:
                host = parsed.netloc

            sanitized = urlunparse((
                parsed.scheme,
                host,
                parsed.path,
                "",  # params
                "",  # query (제거)
                "",  # fragment (제거)
            ))
            return sanitized
        except Exception:
            return "<invalid-stream-url>"

    @classmethod
    def connection_failed(
        cls,
        stream_url: str,
        stream_type: str | None = None,
        reason: str | None = None,
    ) -> "StreamException":
        """
        스트림 연결 실패 예외 생성.

        Args:
            stream_url: 스트림 URL
            stream_type: 스트림 타입
            reason: 실패 사유

        Returns:
            StreamException 인스턴스
        """
        msg = f"스트림 연결에 실패했습니다: {cls._sanitize_stream_url(stream_url)}"
        if reason:
            msg += f" ({reason})"

        return cls(
            message=msg,
            stream_url=stream_url,
            stream_type=stream_type,
            error_code=ErrorCode.STREAM_CONNECTION_FAILED,
        )

    @classmethod
    def disconnected(
        cls,
        stream_url: str,
        stream_type: str | None = None,
        duration_seconds: float | None = None,
    ) -> "StreamException":
        """
        스트림 연결 끊김 예외 생성.

        Args:
            stream_url: 스트림 URL
            stream_type: 스트림 타입
            duration_seconds: 연결 유지 시간 (초)

        Returns:
            StreamException 인스턴스
        """
        exc = cls(
            message="스트림 연결이 끊어졌습니다",
            stream_url=stream_url,
            stream_type=stream_type,
            error_code=ErrorCode.STREAM_DISCONNECTED,
        )

        if duration_seconds is not None:
            exc.details["duration_seconds"] = round(duration_seconds, 2)

        return exc

    @classmethod
    def timeout(
        cls,
        stream_url: str,
        timeout_seconds: float,
        operation: str | None = None,
    ) -> "StreamException":
        """
        스트림 타임아웃 예외 생성.

        Args:
            stream_url: 스트림 URL
            timeout_seconds: 타임아웃 설정 (초)
            operation: 수행 중인 작업

        Returns:
            StreamException 인스턴스
        """
        exc = cls(
            message=f"스트림 응답 시간이 초과되었습니다: {timeout_seconds}초",
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_TIMEOUT,
        )

        exc.details["timeout_seconds"] = timeout_seconds
        if operation:
            exc.details["operation"] = operation

        return exc

    @classmethod
    def invalid_source(
        cls,
        stream_url: str,
        reason: str | None = None,
    ) -> "StreamException":
        """
        유효하지 않은 스트림 소스 예외 생성.

        Args:
            stream_url: 스트림 URL
            reason: 유효하지 않은 이유

        Returns:
            StreamException 인스턴스
        """
        msg = "유효하지 않은 스트림 소스입니다"
        if reason:
            msg += f": {reason}"

        return cls(
            message=msg,
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_INVALID_SOURCE,
        )

    @classmethod
    def unsupported_type(
        cls,
        stream_type: str,
        supported_types: list[str] | None = None,
    ) -> "StreamException":
        """
        지원하지 않는 스트림 타입 예외 생성.

        Args:
            stream_type: 시도된 스트림 타입
            supported_types: 지원되는 타입 목록

        Returns:
            StreamException 인스턴스
        """
        msg = f"지원하지 않는 스트림 타입입니다: {stream_type}"
        if supported_types:
            msg += f" (지원: {', '.join(supported_types)})"

        exc = cls(
            message=msg,
            stream_type=stream_type,
            error_code=ErrorCode.STREAM_UNSUPPORTED_TYPE,
        )

        if supported_types:
            exc.details["supported_types"] = supported_types

        return exc

    @classmethod
    def buffer_overflow(
        cls,
        stream_url: str,
        buffer_size: int,
        max_buffer_size: int,
    ) -> "StreamException":
        """
        스트림 버퍼 오버플로우 예외 생성.

        Args:
            stream_url: 스트림 URL
            buffer_size: 현재 버퍼 크기
            max_buffer_size: 최대 버퍼 크기

        Returns:
            StreamException 인스턴스
        """
        exc = cls(
            message=f"스트림 버퍼가 초과되었습니다: {buffer_size}/{max_buffer_size}",
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_BUFFER_OVERFLOW,
        )

        exc.details["buffer_size"] = buffer_size
        exc.details["max_buffer_size"] = max_buffer_size

        return exc

    @classmethod
    def decode_error(
        cls,
        stream_url: str,
        codec: str | None = None,
        reason: str | None = None,
    ) -> "StreamException":
        """
        스트림 디코딩 오류 예외 생성.

        Args:
            stream_url: 스트림 URL
            codec: 코덱 정보
            reason: 디코딩 실패 사유

        Returns:
            StreamException 인스턴스
        """
        msg = "스트림 디코딩에 실패했습니다"
        if reason:
            msg += f": {reason}"

        exc = cls(
            message=msg,
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_DECODE_ERROR,
        )

        if codec:
            exc.details["codec"] = codec

        return exc

    @classmethod
    def frame_error(
        cls,
        stream_url: str,
        frame_number: int | None = None,
        reason: str | None = None,
    ) -> "StreamException":
        """
        프레임 처리 오류 예외 생성.

        Args:
            stream_url: 스트림 URL
            frame_number: 프레임 번호
            reason: 오류 사유

        Returns:
            StreamException 인스턴스
        """
        msg = "프레임 처리에 실패했습니다"
        if reason:
            msg += f": {reason}"

        exc = cls(
            message=msg,
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_FRAME_ERROR,
        )

        if frame_number is not None:
            exc.details["frame_number"] = frame_number

        return exc

    @classmethod
    def authentication_failed(
        cls,
        stream_url: str,
        reason: str | None = None,
    ) -> "StreamException":
        """
        스트림 인증 실패 예외 생성.

        Args:
            stream_url: 스트림 URL
            reason: 인증 실패 사유

        Returns:
            StreamException 인스턴스
        """
        msg = "스트림 인증에 실패했습니다"
        if reason:
            msg += f": {reason}"

        return cls(
            message=msg,
            stream_url=stream_url,
            error_code=ErrorCode.STREAM_AUTHENTICATION_FAILED,
        )


class ConnectionException(RetryableException):
    """
    연결 오류 예외.

    네트워크 연결 실패, 타임아웃 등 연결 관련 예외입니다.
    """

    def __init__(
        self,
        message: str = "연결에 실패했습니다",
        host: str | None = None,
        port: int | None = None,
        protocol: str | None = None,
        error_code: ErrorCode = ErrorCode.STREAM_CONNECTION_FAILED,
        retry_after: float = 1.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        연결 예외 초기화.

        Args:
            message: 오류 메시지
            host: 대상 호스트
            port: 대상 포트
            protocol: 프로토콜 (TCP, UDP, HTTP 등)
            error_code: 오류 코드
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=error_code,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port
        if protocol:
            self.details["protocol"] = protocol

    @classmethod
    def connection_refused(
        cls,
        host: str,
        port: int | None = None,
    ) -> "ConnectionException":
        """
        연결 거부 예외 생성.

        Args:
            host: 대상 호스트
            port: 대상 포트

        Returns:
            ConnectionException 인스턴스
        """
        msg = f"연결이 거부되었습니다: {host}"
        if port:
            msg += f":{port}"

        return cls(
            message=msg,
            host=host,
            port=port,
        )

    @classmethod
    def connection_timeout(
        cls,
        host: str,
        timeout_seconds: float,
        port: int | None = None,
    ) -> "ConnectionException":
        """
        연결 타임아웃 예외 생성.

        Args:
            host: 대상 호스트
            timeout_seconds: 타임아웃 설정 (초)
            port: 대상 포트

        Returns:
            ConnectionException 인스턴스
        """
        exc = cls(
            message=f"연결 시간이 초과되었습니다: {timeout_seconds}초",
            host=host,
            port=port,
            error_code=ErrorCode.STREAM_TIMEOUT,
        )

        exc.details["timeout_seconds"] = timeout_seconds

        return exc

    @classmethod
    def host_unreachable(
        cls,
        host: str,
        reason: str | None = None,
    ) -> "ConnectionException":
        """
        호스트 도달 불가 예외 생성.

        Args:
            host: 대상 호스트
            reason: 도달 불가 사유

        Returns:
            ConnectionException 인스턴스
        """
        msg = f"호스트에 도달할 수 없습니다: {host}"
        if reason:
            msg += f" ({reason})"

        return cls(
            message=msg,
            host=host,
        )


# =============================================================================
# 외부 서비스 예외
# =============================================================================
class ExternalServiceException(RetryableException):
    """
    외부 서비스 호출 실패 예외.

    앱 백엔드 등 외부 서비스 호출 시 오류가 발생한 경우입니다.
    """

    def __init__(
        self,
        message: str = "외부 서비스 호출에 실패했습니다",
        service_name: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        retry_after: float = 1.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        외부 서비스 예외 초기화.

        Args:
            message: 오류 메시지
            service_name: 서비스명
            endpoint: API 엔드포인트
            status_code: HTTP 상태 코드
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if service_name:
            self.details["service_name"] = service_name
        if endpoint:
            self.details["endpoint"] = endpoint
        if status_code:
            self.details["status_code"] = status_code


class WebhookException(RetryableException):
    """
    웹훅 호출 실패 예외.

    분석 완료 알림 등 웹훅 호출 시 오류가 발생한 경우입니다.
    """

    def __init__(
        self,
        message: str = "웹훅 호출에 실패했습니다",
        webhook_url: str | None = None,
        event_type: str | None = None,
        status_code: int | None = None,
        retry_after: float = 2.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        웹훅 예외 초기화.

        Args:
            message: 오류 메시지
            webhook_url: 웹훅 URL
            event_type: 이벤트 타입
            status_code: HTTP 상태 코드
            retry_after: 재시도 대기 시간 (초)
            max_retries: 최대 재시도 횟수
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            retry_after=retry_after,
            max_retries=max_retries,
            **kwargs,
        )

        if webhook_url:
            # URL에서 쿼리 파라미터 제거 (민감 정보 보호)
            base_url = webhook_url.split("?")[0]
            self.details["webhook_url"] = base_url
        if event_type:
            self.details["event_type"] = event_type
        if status_code:
            self.details["status_code"] = status_code


# =============================================================================
# 디코딩 예외
# =============================================================================


class DecodingException(InfrastructureException):
    """비디오 디코딩 예외."""

    def __init__(
        self,
        message: str = "비디오 디코딩에 실패했습니다",
        video_path: str | None = None,
        frame_number: int | None = None,
        codec: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        디코딩 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            frame_number: 문제 발생 프레임 번호
            codec: 사용 코덱
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if frame_number is not None:
            combined_details["frame_number"] = frame_number
        if codec:
            combined_details["codec"] = codec

        super().__init__(
            message=message,
            error_code=ErrorCode.DECODING_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.frame_number = frame_number
        self.codec = codec

    @classmethod
    def init_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "DecodingException":
        """디코더 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"디코더 초기화에 실패했습니다: {reason}",
            video_path=video_path,
            cause=cause,
        )

    @classmethod
    def frame_failed(
        cls,
        video_path: str,
        frame_number: int,
        reason: str,
        cause: Exception | None = None,
    ) -> "DecodingException":
        """프레임 디코딩 실패 팩토리 메서드."""
        return cls(
            message=f"프레임 {frame_number} 디코딩에 실패했습니다: {reason}",
            video_path=video_path,
            frame_number=frame_number,
            cause=cause,
        )

    @classmethod
    def seek_failed(
        cls,
        video_path: str,
        target_frame: int,
        cause: Exception | None = None,
    ) -> "DecodingException":
        """비디오 탐색 실패 팩토리 메서드."""
        return cls(
            message=f"프레임 {target_frame}으로 탐색에 실패했습니다",
            video_path=video_path,
            frame_number=target_frame,
            cause=cause,
        )


class CodecException(DecodingException):
    """코덱 관련 예외."""

    def __init__(
        self,
        message: str = "코덱 오류가 발생했습니다",
        codec_name: str | None = None,
        required_codec: str | None = None,
        video_path: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        코덱 예외 초기화.

        Args:
            message: 에러 메시지
            codec_name: 코덱 이름
            required_codec: 필요한 코덱
            video_path: 비디오 파일 경로
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if codec_name:
            combined_details["codec_name"] = codec_name
        if required_codec:
            combined_details["required_codec"] = required_codec

        super().__init__(
            message=message,
            video_path=video_path,
            codec=codec_name,
            details=combined_details,
            cause=cause,
        )
        self.codec_name = codec_name
        self.required_codec = required_codec

    @classmethod
    def not_found(
        cls,
        codec_name: str,
        video_path: str | None = None,
    ) -> "CodecException":
        """코덱 미발견 팩토리 메서드."""
        return cls(
            message=f"코덱을 찾을 수 없습니다: {codec_name}",
            codec_name=codec_name,
            video_path=video_path,
        )

    @classmethod
    def not_supported(
        cls,
        codec_name: str,
        video_path: str | None = None,
    ) -> "CodecException":
        """코덱 미지원 팩토리 메서드."""
        return cls(
            message=f"지원하지 않는 코덱입니다: {codec_name}",
            codec_name=codec_name,
            video_path=video_path,
        )

    @classmethod
    def init_failed(
        cls,
        codec_name: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "CodecException":
        """코덱 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"코덱 초기화에 실패했습니다 ({codec_name}): {reason}",
            codec_name=codec_name,
            cause=cause,
        )


class CorruptedFileException(DecodingException):
    """손상된 파일 예외."""

    def __init__(
        self,
        message: str = "파일이 손상되었습니다",
        file_path: str | None = None,
        corruption_type: str | None = None,
        affected_range: tuple[int, int] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        손상된 파일 예외 초기화.

        Args:
            message: 에러 메시지
            file_path: 파일 경로
            corruption_type: 손상 유형 (header, frame, audio, metadata)
            affected_range: 영향 받은 범위 (시작, 끝)
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if corruption_type:
            combined_details["corruption_type"] = corruption_type
        if affected_range:
            combined_details["affected_range"] = affected_range

        super().__init__(
            message=message,
            video_path=file_path,
            details=combined_details,
            cause=cause,
        )
        self.file_path = file_path
        self.corruption_type = corruption_type
        self.affected_range = affected_range

    @classmethod
    def header_corrupted(
        cls,
        file_path: str,
        cause: Exception | None = None,
    ) -> "CorruptedFileException":
        """헤더 손상 팩토리 메서드."""
        return cls(
            message=f"파일 헤더가 손상되었습니다: {file_path}",
            file_path=file_path,
            corruption_type="header",
            cause=cause,
        )

    @classmethod
    def frame_corrupted(
        cls,
        file_path: str,
        frame_number: int,
        cause: Exception | None = None,
    ) -> "CorruptedFileException":
        """프레임 손상 팩토리 메서드."""
        return cls(
            message=f"프레임 {frame_number}이 손상되었습니다: {file_path}",
            file_path=file_path,
            corruption_type="frame",
            affected_range=(frame_number, frame_number),
            cause=cause,
        )

    @classmethod
    def incomplete_file(
        cls,
        file_path: str,
        expected_size: int,
        actual_size: int,
        cause: Exception | None = None,
    ) -> "CorruptedFileException":
        """불완전한 파일 팩토리 메서드."""
        return cls(
            message=f"파일이 불완전합니다: {file_path} (예상: {expected_size}, 실제: {actual_size})",
            file_path=file_path,
            corruption_type="incomplete",
            details={
                "expected_size": expected_size,
                "actual_size": actual_size,
            },
            cause=cause,
        )


# =============================================================================
# 프레임 추출 예외
# =============================================================================


class InfraFrameExtractionException(InfrastructureException):
    """프레임 추출 예외."""

    def __init__(
        self,
        message: str = "프레임 추출에 실패했습니다",
        video_path: str | None = None,
        frame_index: int | None = None,
        extraction_method: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        프레임 추출 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            frame_index: 실패한 프레임 인덱스
            extraction_method: 추출 방법 (uniform, keyframe, adaptive 등)
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if frame_index is not None:
            combined_details["frame_index"] = frame_index
        if extraction_method:
            combined_details["extraction_method"] = extraction_method

        super().__init__(
            message=message,
            error_code=ErrorCode.FRAME_EXTRACTION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.frame_index = frame_index
        self.extraction_method = extraction_method

    @classmethod
    def init_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "InfraFrameExtractionException":
        """추출기 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"프레임 추출기 초기화에 실패했습니다: {reason}",
            video_path=video_path,
            cause=cause,
        )

    @classmethod
    def extraction_failed(
        cls,
        video_path: str,
        frame_index: int,
        reason: str,
        cause: Exception | None = None,
    ) -> "InfraFrameExtractionException":
        """프레임 추출 실패 팩토리 메서드."""
        return cls(
            message=f"프레임 {frame_index} 추출에 실패했습니다: {reason}",
            video_path=video_path,
            frame_index=frame_index,
            cause=cause,
        )

    @classmethod
    def timeout(
        cls,
        video_path: str,
        timeout_seconds: float,
        cause: Exception | None = None,
    ) -> "InfraFrameExtractionException":
        """추출 타임아웃 팩토리 메서드."""
        return cls(
            message=f"프레임 추출 시간이 초과되었습니다: {timeout_seconds}초",
            video_path=video_path,
            details={"timeout_seconds": timeout_seconds},
            cause=cause,
        )

    @classmethod
    def invalid_range(
        cls,
        video_path: str,
        start_frame: int,
        end_frame: int,
        total_frames: int,
    ) -> "InfraFrameExtractionException":
        """유효하지 않은 프레임 범위 팩토리 메서드."""
        return cls(
            message=f"유효하지 않은 프레임 범위입니다: {start_frame}-{end_frame} (총 {total_frames})",
            video_path=video_path,
            details={
                "start_frame": start_frame,
                "end_frame": end_frame,
                "total_frames": total_frames,
            },
        )

    @classmethod
    def keyframe_detection_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "InfraFrameExtractionException":
        """키프레임 감지 실패 팩토리 메서드."""
        return cls(
            message=f"키프레임 감지에 실패했습니다: {reason}",
            video_path=video_path,
            extraction_method="keyframe",
            cause=cause,
        )

    @classmethod
    def buffer_overflow(
        cls,
        video_path: str,
        buffer_size: int,
        max_size: int,
    ) -> "InfraFrameExtractionException":
        """버퍼 오버플로우 팩토리 메서드."""
        return cls(
            message=f"프레임 버퍼가 초과되었습니다: {buffer_size}/{max_size}",
            video_path=video_path,
            details={
                "buffer_size": buffer_size,
                "max_size": max_size,
            },
        )


class EndOfStreamException(InfrastructureException):
    """스트림 끝 도달 예외."""

    def __init__(
        self,
        message: str = "스트림 끝에 도달했습니다",
        video_path: str | None = None,
        last_frame_index: int | None = None,
        total_frames: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        스트림 끝 도달 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            last_frame_index: 마지막 프레임 인덱스
            total_frames: 총 프레임 수
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if last_frame_index is not None:
            combined_details["last_frame_index"] = last_frame_index
        if total_frames is not None:
            combined_details["total_frames"] = total_frames

        super().__init__(
            message=message,
            error_code=ErrorCode.END_OF_STREAM,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.last_frame_index = last_frame_index
        self.total_frames = total_frames

    @classmethod
    def video_end(
        cls,
        video_path: str,
        last_frame_index: int,
        total_frames: int,
    ) -> "EndOfStreamException":
        """비디오 끝 도달 팩토리 메서드."""
        return cls(
            message=f"비디오 끝에 도달했습니다 (프레임 {last_frame_index}/{total_frames})",
            video_path=video_path,
            last_frame_index=last_frame_index,
            total_frames=total_frames,
        )

    @classmethod
    def stream_closed(
        cls,
        video_path: str,
        reason: str | None = None,
    ) -> "EndOfStreamException":
        """스트림 닫힘 팩토리 메서드."""
        msg = "스트림이 닫혔습니다"
        if reason:
            msg += f": {reason}"
        return cls(
            message=msg,
            video_path=video_path,
        )


# =============================================================================
# 비디오 정규화 예외
# =============================================================================


class NormalizationException(InfrastructureException):
    """비디오 정규화 예외."""

    def __init__(
        self,
        message: str = "비디오 정규화에 실패했습니다",
        video_path: str | None = None,
        source_resolution: tuple[int, int] | None = None,
        target_resolution: tuple[int, int] | None = None,
        normalization_type: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 정규화 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            source_resolution: 원본 해상도 (width, height)
            target_resolution: 목표 해상도 (width, height)
            normalization_type: 정규화 유형 (resolution, fps, format 등)
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if source_resolution:
            combined_details["source_resolution"] = source_resolution
        if target_resolution:
            combined_details["target_resolution"] = target_resolution
        if normalization_type:
            combined_details["normalization_type"] = normalization_type

        super().__init__(
            message=message,
            error_code=ErrorCode.NORMALIZATION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.source_resolution = source_resolution
        self.target_resolution = target_resolution
        self.normalization_type = normalization_type

    @classmethod
    def init_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """정규화기 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"정규화기 초기화에 실패했습니다: {reason}",
            video_path=video_path,
            cause=cause,
        )

    @classmethod
    def resolution_failed(
        cls,
        video_path: str,
        source_resolution: tuple[int, int],
        target_resolution: tuple[int, int],
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """해상도 변환 실패 팩토리 메서드."""
        return cls(
            message=f"해상도 변환에 실패했습니다: {reason}",
            video_path=video_path,
            source_resolution=source_resolution,
            target_resolution=target_resolution,
            normalization_type="resolution",
            cause=cause,
        )

    @classmethod
    def fps_failed(
        cls,
        video_path: str,
        source_fps: float,
        target_fps: float,
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """FPS 변환 실패 팩토리 메서드."""
        return cls(
            message=f"FPS 변환에 실패했습니다: {reason}",
            video_path=video_path,
            normalization_type="fps",
            details={
                "source_fps": source_fps,
                "target_fps": target_fps,
            },
            cause=cause,
        )

    @classmethod
    def format_failed(
        cls,
        video_path: str,
        source_format: str,
        target_format: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """포맷 변환 실패 팩토리 메서드."""
        return cls(
            message=f"포맷 변환에 실패했습니다: {reason}",
            video_path=video_path,
            normalization_type="format",
            details={
                "source_format": source_format,
                "target_format": target_format,
            },
            cause=cause,
        )

    @classmethod
    def color_space_failed(
        cls,
        video_path: str,
        source_color_space: str,
        target_color_space: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """색공간 변환 실패 팩토리 메서드."""
        return cls(
            message=f"색공간 변환에 실패했습니다: {reason}",
            video_path=video_path,
            normalization_type="color_space",
            details={
                "source_color_space": source_color_space,
                "target_color_space": target_color_space,
            },
            cause=cause,
        )

    @classmethod
    def aspect_ratio_failed(
        cls,
        video_path: str,
        source_ratio: float,
        target_ratio: float,
        reason: str,
        cause: Exception | None = None,
    ) -> "NormalizationException":
        """종횡비 변환 실패 팩토리 메서드."""
        return cls(
            message=f"종횡비 변환에 실패했습니다: {reason}",
            video_path=video_path,
            normalization_type="aspect_ratio",
            details={
                "source_ratio": source_ratio,
                "target_ratio": target_ratio,
            },
            cause=cause,
        )


class InfraResolutionException(InfrastructureException):
    """해상도 관련 예외."""

    def __init__(
        self,
        message: str = "해상도 처리에 실패했습니다",
        width: int | None = None,
        height: int | None = None,
        min_resolution: tuple[int, int] | None = None,
        max_resolution: tuple[int, int] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        해상도 예외 초기화.

        Args:
            message: 에러 메시지
            width: 문제가 된 너비
            height: 문제가 된 높이
            min_resolution: 최소 허용 해상도
            max_resolution: 최대 허용 해상도
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if width is not None:
            combined_details["width"] = width
        if height is not None:
            combined_details["height"] = height
        if min_resolution:
            combined_details["min_resolution"] = min_resolution
        if max_resolution:
            combined_details["max_resolution"] = max_resolution

        super().__init__(
            message=message,
            error_code=ErrorCode.VIDEO_RESOLUTION_CONVERSION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.width = width
        self.height = height
        self.min_resolution = min_resolution
        self.max_resolution = max_resolution

    @classmethod
    def invalid_resolution(
        cls,
        width: int,
        height: int,
        reason: str,
    ) -> "InfraResolutionException":
        """유효하지 않은 해상도 팩토리 메서드."""
        return cls(
            message=f"유효하지 않은 해상도입니다 ({width}x{height}): {reason}",
            width=width,
            height=height,
        )

    @classmethod
    def unsupported_resolution(
        cls,
        width: int,
        height: int,
        supported_resolutions: list,
    ) -> "InfraResolutionException":
        """지원하지 않는 해상도 팩토리 메서드."""
        return cls(
            message=f"지원하지 않는 해상도입니다: {width}x{height}",
            width=width,
            height=height,
            details={"supported_resolutions": supported_resolutions},
        )

    @classmethod
    def below_minimum(
        cls,
        width: int,
        height: int,
        min_width: int,
        min_height: int,
    ) -> "InfraResolutionException":
        """최소 해상도 미달 팩토리 메서드."""
        return cls(
            message=f"해상도가 최소 요구사항 미달입니다: {width}x{height} < {min_width}x{min_height}",
            width=width,
            height=height,
            min_resolution=(min_width, min_height),
        )

    @classmethod
    def above_maximum(
        cls,
        width: int,
        height: int,
        max_width: int,
        max_height: int,
    ) -> "InfraResolutionException":
        """최대 해상도 초과 팩토리 메서드."""
        return cls(
            message=f"해상도가 최대 허용치 초과입니다: {width}x{height} > {max_width}x{max_height}",
            width=width,
            height=height,
            max_resolution=(max_width, max_height),
        )

    @classmethod
    def interpolation_failed(
        cls,
        source_resolution: tuple[int, int],
        target_resolution: tuple[int, int],
        method: str,
        cause: Exception | None = None,
    ) -> "InfraResolutionException":
        """보간 실패 팩토리 메서드."""
        return cls(
            message=f"해상도 보간에 실패했습니다: {source_resolution} -> {target_resolution} ({method})",
            width=target_resolution[0],
            height=target_resolution[1],
            details={
                "source_resolution": source_resolution,
                "interpolation_method": method,
            },
            cause=cause,
        )


class ClassificationException(InfrastructureException):
    """비디오 분류 예외."""

    def __init__(
        self,
        message: str = "비디오 분류에 실패했습니다",
        video_path: str | None = None,
        video_type: str | None = None,
        confidence: float | None = None,
        threshold: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        비디오 분류 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            video_type: 분류된 비디오 타입
            confidence: 분류 신뢰도
            threshold: 분류 임계값
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if video_type:
            combined_details["video_type"] = video_type
        if confidence is not None:
            combined_details["confidence"] = confidence
        if threshold is not None:
            combined_details["threshold"] = threshold

        super().__init__(
            message=message,
            error_code=ErrorCode.CLASSIFICATION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.video_type = video_type
        self.confidence = confidence
        self.threshold = threshold

    @classmethod
    def init_failed(
        cls,
        reason: str,
        cause: Exception | None = None,
    ) -> "ClassificationException":
        """분류기 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"분류기 초기화에 실패했습니다: {reason}",
            cause=cause,
        )

    @classmethod
    def low_confidence(
        cls,
        video_path: str,
        video_type: str,
        confidence: float,
        threshold: float,
    ) -> "ClassificationException":
        """낮은 신뢰도 팩토리 메서드."""
        return cls(
            message=f"분류 신뢰도가 임계값 미달입니다: {confidence:.2%} < {threshold:.2%}",
            video_path=video_path,
            video_type=video_type,
            confidence=confidence,
            threshold=threshold,
        )

    @classmethod
    def ambiguous_result(
        cls,
        video_path: str,
        candidates: dict[str, float],
    ) -> "ClassificationException":
        """모호한 분류 결과 팩토리 메서드."""
        return cls(
            message="분류 결과가 모호합니다: 여러 타입의 신뢰도가 유사합니다",
            video_path=video_path,
            details={"candidates": candidates},
        )

    @classmethod
    def feature_extraction_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "ClassificationException":
        """특성 추출 실패 팩토리 메서드."""
        return cls(
            message=f"분류 특성 추출에 실패했습니다: {reason}",
            video_path=video_path,
            cause=cause,
        )

    @classmethod
    def unsupported_format(
        cls,
        video_path: str,
        format_type: str,
    ) -> "ClassificationException":
        """지원하지 않는 형식 팩토리 메서드."""
        return cls(
            message=f"분류를 지원하지 않는 형식입니다: {format_type}",
            video_path=video_path,
            details={"format": format_type},
        )

    @classmethod
    def training_type_detection_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "ClassificationException":
        """훈련 유형 감지 실패 팩토리 메서드."""
        return cls(
            message=f"훈련 유형 감지에 실패했습니다: {reason}",
            video_path=video_path,
            video_type="TRAINING",
            cause=cause,
        )

    @classmethod
    def game_type_detection_failed(
        cls,
        video_path: str,
        reason: str,
        cause: Exception | None = None,
    ) -> "ClassificationException":
        """경기 유형 감지 실패 팩토리 메서드."""
        return cls(
            message=f"경기 유형 감지에 실패했습니다: {reason}",
            video_path=video_path,
            video_type="GAME",
            cause=cause,
        )


class SamplingException(InfrastructureException):
    """적응형 샘플링 예외."""

    def __init__(
        self,
        message: str = "프레임 샘플링에 실패했습니다",
        video_path: str | None = None,
        sampling_strategy: str | None = None,
        frame_index: int | None = None,
        sampling_rate: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        적응형 샘플링 예외 초기화.

        Args:
            message: 에러 메시지
            video_path: 비디오 파일 경로
            sampling_strategy: 사용된 샘플링 전략
            frame_index: 문제가 발생한 프레임 인덱스
            sampling_rate: 샘플링 레이트
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}

        if video_path:
            combined_details["video_path"] = video_path
        if sampling_strategy:
            combined_details["sampling_strategy"] = sampling_strategy
        if frame_index is not None:
            combined_details["frame_index"] = frame_index
        if sampling_rate is not None:
            combined_details["sampling_rate"] = sampling_rate

        super().__init__(
            message=message,
            error_code=ErrorCode.SAMPLING_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.video_path = video_path
        self.sampling_strategy = sampling_strategy
        self.frame_index = frame_index
        self.sampling_rate = sampling_rate

    @classmethod
    def init_failed(
        cls,
        reason: str,
        cause: Exception | None = None,
    ) -> "SamplingException":
        """샘플러 초기화 실패 팩토리 메서드."""
        return cls(
            message=f"샘플러 초기화에 실패했습니다: {reason}",
            cause=cause,
        )

    @classmethod
    def invalid_config(
        cls,
        config_name: str,
        value: Any,
        reason: str,
    ) -> "SamplingException":
        """잘못된 설정 팩토리 메서드."""
        return cls(
            message=f"샘플링 설정이 유효하지 않습니다: {config_name}={value}, {reason}",
            details={
                "config_name": config_name,
                "config_value": str(value),
            },
        )

    @classmethod
    def motion_analysis_failed(
        cls,
        video_path: str,
        frame_index: int,
        reason: str,
        cause: Exception | None = None,
    ) -> "SamplingException":
        """움직임 분석 실패 팩토리 메서드."""
        return cls(
            message=f"움직임 분석에 실패했습니다: {reason}",
            video_path=video_path,
            frame_index=frame_index,
            cause=cause,
        )

    @classmethod
    def optical_flow_failed(
        cls,
        video_path: str,
        frame_index: int,
        cause: Exception | None = None,
    ) -> "SamplingException":
        """옵티컬 플로우 계산 실패 팩토리 메서드."""
        return cls(
            message=f"옵티컬 플로우 계산에 실패했습니다 (프레임: {frame_index})",
            video_path=video_path,
            frame_index=frame_index,
            cause=cause,
        )

    @classmethod
    def invalid_sampling_rate(
        cls,
        rate: float,
        min_rate: float,
        max_rate: float,
    ) -> "SamplingException":
        """잘못된 샘플링 레이트 팩토리 메서드."""
        return cls(
            message=f"샘플링 레이트가 유효하지 않습니다: {rate} (범위: {min_rate}-{max_rate})",
            sampling_rate=rate,
            details={
                "min_rate": min_rate,
                "max_rate": max_rate,
            },
        )

    @classmethod
    def insufficient_frames(
        cls,
        video_path: str,
        available: int,
        required: int,
    ) -> "SamplingException":
        """프레임 부족 팩토리 메서드."""
        return cls(
            message=f"샘플링할 프레임이 부족합니다: {available}/{required}",
            video_path=video_path,
            details={
                "available_frames": available,
                "required_frames": required,
            },
        )

    @classmethod
    def timeout(
        cls,
        video_path: str,
        elapsed_seconds: float,
        timeout_seconds: float,
    ) -> "SamplingException":
        """샘플링 타임아웃 팩토리 메서드."""
        return cls(
            message=f"샘플링 시간이 초과되었습니다: {elapsed_seconds:.1f}초 > {timeout_seconds}초",
            video_path=video_path,
            details={
                "elapsed_seconds": elapsed_seconds,
                "timeout_seconds": timeout_seconds,
            },
        )


# =============================================================================
# 인프라 예외 모듈 익스포트
# =============================================================================
__all__ = [
    # 인프라 기본 예외
    "InfrastructureException",
    "TimeoutException",
    "CircuitBreakerOpenException",
    # 데이터베이스 예외
    "DatabaseException",
    "DatabaseConnectionException",
    "DatabaseTimeoutException",
    "DatabaseIntegrityException",
    "TransactionException",
    "RecordNotFoundException",
    "ConnectionPoolException",
    # 캐시 예외
    "CacheException",
    "CacheConnectionException",
    "CacheKeyNotFoundException",
    "CacheSerializationException",
    "RedisException",
    # 메시지 큐 예외
    "QueueException",
    "QueueConnectionException",
    "TaskEnqueueException",
    "TaskExecutionException",
    "TaskTimeoutException",
    "EventBusException",
    # 알림 예외
    "AlertDeliveryException",
    "AlertConfigurationException",
    # 워커 예외
    "WorkerException",
    "NotificationException",
    "CleanupException",
    # 스토리지 예외
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
    # 스트림 예외
    "StreamException",
    "ConnectionException",
    # 외부 서비스 예외
    "ExternalServiceException",
    "WebhookException",
    # 디코딩 예외
    "DecodingException",
    "CodecException",
    "CorruptedFileException",
    # 프레임 추출 예외
    "InfraFrameExtractionException",
    "EndOfStreamException",
    # 비디오 정규화 예외
    "NormalizationException",
    "InfraResolutionException",
    # 비디오 분류 예외
    "ClassificationException",
    # 적응형 샘플링 예외
    "SamplingException",
    # 카메라 예외 (v3.0.0 멀티카메라)
    "CameraException",
    "CameraConnectionException",
    "CameraTimeoutException",
    # 캘리브레이션 예외 (v3.0.0 멀티카메라)
    "CalibrationException",
    "InfraInsufficientDataException",
    # 좌표 변환 예외 (v3.0.0 멀티카메라)
    "TransformationException",
    "CalibrationRequiredException",
    # 설정 예외
    "InfraConfigurationException",
    "InfraValidationException",
    # 프레임 정렬 예외 (v3.0.0 전처리)
    "AlignmentException",
    "FrameDropException",
    # 동기화 예외 (v3.0.0 전처리)
    "SyncException",
]


# =============================================================================
# 카메라 예외 (v3.0.0 멀티카메라 지원)
# =============================================================================
class CameraException(InfrastructureException):
    """카메라 기본 예외."""

    def __init__(
        self,
        message: str = "카메라 작업에 실패했습니다",
        camera_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        카메라 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 카메라 ID
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id

        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.camera_id = camera_id


class CameraConnectionException(RetryableException):
    """카메라 연결 예외."""

    def __init__(
        self,
        message: str = "카메라 연결에 실패했습니다",
        camera_id: str | None = None,
        device_uri: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        카메라 연결 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 카메라 ID
            device_uri: 장치 URI
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if device_uri:
            combined_details["device_uri"] = device_uri

        super().__init__(
            message=message,
            error_code=ErrorCode.CONNECTION_ERROR,
            details=combined_details,
            cause=cause,
            retry_after=2.0,
        )
        self.camera_id = camera_id
        self.device_uri = device_uri


class CameraTimeoutException(RetryableException):
    """카메라 타임아웃 예외."""

    def __init__(
        self,
        message: str = "카메라 작업이 타임아웃되었습니다",
        camera_id: str | None = None,
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        카메라 타임아웃 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 카메라 ID
            timeout_seconds: 타임아웃 시간
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if timeout_seconds is not None:
            combined_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            details=combined_details,
            cause=cause,
            retry_after=1.0,
        )
        self.camera_id = camera_id
        self.timeout_seconds = timeout_seconds


# =============================================================================
# 캘리브레이션 예외 (v3.0.0 멀티카메라 지원)
# =============================================================================
class CalibrationException(InfrastructureException):
    """캘리브레이션 예외."""

    def __init__(
        self,
        message: str = "캘리브레이션에 실패했습니다",
        camera_id: str | None = None,
        reprojection_error: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        캘리브레이션 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 카메라 ID
            reprojection_error: 재투영 오차
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if reprojection_error is not None:
            combined_details["reprojection_error"] = reprojection_error

        super().__init__(
            message=message,
            error_code=ErrorCode.CALIBRATION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.camera_id = camera_id
        self.reprojection_error = reprojection_error


class InfraInsufficientDataException(CalibrationException):
    """캘리브레이션 데이터 부족 예외."""

    def __init__(
        self,
        message: str = "캘리브레이션에 필요한 데이터가 부족합니다",
        required: int | None = None,
        available: int | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        데이터 부족 예외 초기화.

        Args:
            message: 에러 메시지
            required: 필요한 데이터 수
            available: 사용 가능한 데이터 수
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if required is not None:
            combined_details["required"] = required
        if available is not None:
            combined_details["available"] = available

        super().__init__(
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.required = required
        self.available = available


# =============================================================================
# 좌표 변환 예외 (v3.0.0 멀티카메라 지원)
# =============================================================================
class TransformationException(InfrastructureException):
    """좌표 변환 예외."""

    def __init__(
        self,
        message: str = "좌표 변환에 실패했습니다",
        source_system: str | None = None,
        target_system: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        좌표 변환 예외 초기화.

        Args:
            message: 에러 메시지
            source_system: 소스 좌표계
            target_system: 대상 좌표계
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if source_system:
            combined_details["source_system"] = source_system
        if target_system:
            combined_details["target_system"] = target_system

        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.source_system = source_system
        self.target_system = target_system


class CalibrationRequiredException(TransformationException):
    """캘리브레이션 필요 예외."""

    def __init__(
        self,
        message: str = "좌표 변환을 위해 캘리브레이션이 필요합니다",
        camera_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        캘리브레이션 필요 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 카메라 ID
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id

        super().__init__(
            message=message,
            details=combined_details,
            cause=cause,
        )
        self.camera_id = camera_id


# =============================================================================
# 설정 예외
# =============================================================================
class InfraConfigurationException(InfrastructureException):
    """설정 예외."""

    def __init__(
        self,
        message: str = "설정 로드에 실패했습니다",
        config_path: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        설정 예외 초기화.

        Args:
            message: 에러 메시지
            config_path: 설정 파일 경로
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if config_path:
            combined_details["config_path"] = config_path

        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.config_path = config_path


class InfraValidationException(InfrastructureException):
    """유효성 검증 예외."""

    def __init__(
        self,
        message: str = "유효성 검증에 실패했습니다",
        field: str | None = None,
        value: Any | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        유효성 검증 예외 초기화.

        Args:
            message: 에러 메시지
            field: 검증 실패 필드
            value: 검증 실패 값
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if field:
            combined_details["field"] = field
        if value is not None:
            combined_details["value"] = str(value)

        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.field = field
        self.value = value


# =============================================================================
# 프레임 정렬 예외 (v3.0.0 전처리)
# =============================================================================
class AlignmentException(InfrastructureException):
    """프레임 정렬 예외."""

    def __init__(
        self,
        message: str = "프레임 정렬에 실패했습니다",
        camera_id: str | None = None,
        timestamp_ms: float | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        프레임 정렬 예외 초기화.

        Args:
            message: 에러 메시지
            camera_id: 관련 카메라 ID
            timestamp_ms: 관련 타임스탬프
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_id:
            combined_details["camera_id"] = camera_id
        if timestamp_ms is not None:
            combined_details["timestamp_ms"] = timestamp_ms

        super().__init__(
            message=message,
            error_code=ErrorCode.MULTI_CAMERA_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.camera_id = camera_id
        self.timestamp_ms = timestamp_ms


class FrameDropException(InfrastructureException):
    """프레임 드롭 예외."""

    def __init__(
        self,
        message: str = "프레임 드롭이 발생했습니다",
        dropped_count: int = 0,
        total_count: int = 0,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        프레임 드롭 예외 초기화.

        Args:
            message: 에러 메시지
            dropped_count: 드롭된 프레임 수
            total_count: 전체 프레임 수
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if dropped_count:
            combined_details["dropped_count"] = dropped_count
        if total_count:
            combined_details["total_count"] = total_count

        super().__init__(
            message=message,
            error_code=ErrorCode.CAMERA_FRAME_DROP,
            details=combined_details,
            cause=cause,
        )
        self.dropped_count = dropped_count
        self.total_count = total_count

    @property
    def drop_rate(self) -> float:
        """드롭률 반환."""
        if self.total_count == 0:
            return 0.0
        return self.dropped_count / self.total_count


# =============================================================================
# 동기화 예외 (v3.0.0 전처리)
# =============================================================================
class SyncException(InfrastructureException):
    """멀티카메라 영상 동기화 예외."""

    def __init__(
        self,
        message: str = "영상 동기화에 실패했습니다",
        camera_ids: list[str] | None = None,
        sync_method: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        동기화 예외 초기화.

        Args:
            message: 에러 메시지
            camera_ids: 관련 카메라 ID 목록
            sync_method: 사용된 동기화 방법
            details: 추가 상세 정보
            cause: 원인 예외
        """
        combined_details = details or {}
        if camera_ids:
            combined_details["camera_ids"] = camera_ids
        if sync_method:
            combined_details["sync_method"] = sync_method

        super().__init__(
            message=message,
            error_code=ErrorCode.CAMERA_SYNC_ERROR,
            details=combined_details,
            cause=cause,
        )
        self.camera_ids = camera_ids or []
        self.sync_method = sync_method


# =============================================================================
# 모듈 버전 정보
# =============================================================================
__version__ = "1.0.0"
