# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/unit
파일: test_infrastructure_exceptions.py
설명: infrastructure_exceptions.py 단위 테스트 (58개 클래스, 61 팩토리 메서드, 6 보안 기능)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    CriticalException,
    NonRetryableException,
    RetryableException,
)
from shared.exceptions.infrastructure_exceptions import (
    # 인프라 기본
    InfrastructureException,
    TimeoutException,
    CircuitBreakerOpenException,
    # 데이터베이스
    DatabaseException,
    DatabaseConnectionException,
    DatabaseTimeoutException,
    DatabaseIntegrityException,
    TransactionException,
    RecordNotFoundException,
    ConnectionPoolException,
    # 캐시
    CacheException,
    CacheConnectionException,
    CacheKeyNotFoundException,
    CacheSerializationException,
    RedisException,
    # 메시지 큐
    QueueException,
    QueueConnectionException,
    TaskEnqueueException,
    TaskExecutionException,
    TaskTimeoutException,
    EventBusException,
    # 알림
    AlertDeliveryException,
    AlertConfigurationException,
    # 워커
    WorkerException,
    NotificationException,
    CleanupException,
    # 스토리지
    StorageException,
    S3Exception,
    S3UploadException,
    S3DownloadException,
    S3ObjectNotFoundException,
    S3PermissionException,
    MetadataExtractionException,
    LocalStorageException,
    DiskSpaceException,
    FilePermissionException,
    # 스트림
    StreamException,
    ConnectionException,
    # 외부 서비스
    ExternalServiceException,
    WebhookException,
    # 디코딩
    DecodingException,
    CodecException,
    CorruptedFileException,
    # 프레임 추출
    FrameExtractionException,
    EndOfStreamException,
    # 정규화
    NormalizationException,
    ResolutionException,
    # 분류
    ClassificationException,
    # 샘플링
    SamplingException,
    # 카메라
    CameraException,
    CameraConnectionException,
    CameraTimeoutException,
    # 캘리브레이션
    CalibrationException,
    InsufficientDataException,
    # 좌표 변환
    TransformationException,
    CalibrationRequiredException,
    # 설정
    ConfigurationException,
    ValidationException,
)
import shared.exceptions.infrastructure_exceptions as mod


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  단위 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def check(r: TestResult, name: str, condition: bool, reason: str = "") -> None:
    """조건 검사 헬퍼."""
    if condition:
        r.ok(name)
    else:
        r.fail(name, reason or "조건 불일치")


# =============================================================================
# [1] 인프라 기본 예외
# =============================================================================
def test_infrastructure_exception(r: TestResult) -> None:
    """InfrastructureException 기본 테스트."""
    e = InfrastructureException()
    check(r, "InfrastructureException 기본 생성", isinstance(e, CourtViewException))
    check(r, "InfrastructureException 기본 메시지", "인프라스트럭처" in str(e))
    check(r, "InfrastructureException ErrorCode",
          e.code == ErrorCode.INFRASTRUCTURE_ERROR.code)

    # 커스텀 메시지
    e2 = InfrastructureException(message="커스텀 인프라 오류")
    check(r, "InfrastructureException 커스텀 메시지", "커스텀 인프라 오류" in str(e2))


def test_timeout_exception(r: TestResult) -> None:
    """TimeoutException 테스트."""
    e = TimeoutException()
    check(r, "TimeoutException 기본 생성", isinstance(e, RetryableException))
    check(r, "TimeoutException ErrorCode", e.code == ErrorCode.TIMEOUT_ERROR.code)

    # 매개변수 포함
    e2 = TimeoutException(
        timeout_seconds=30.0,
        operation="video_analysis",
    )
    check(r, "TimeoutException timeout_seconds", e2.details.get("timeout_seconds") == 30.0)
    check(r, "TimeoutException operation", e2.details.get("operation") == "video_analysis")


def test_circuit_breaker_exception(r: TestResult) -> None:
    """CircuitBreakerOpenException 테스트."""
    e = CircuitBreakerOpenException()
    check(r, "CircuitBreakerOpenException 기본 생성", isinstance(e, NonRetryableException))
    check(r, "CircuitBreakerOpenException ErrorCode",
          e.code == ErrorCode.CIRCUIT_BREAKER_OPEN.code)

    # 매개변수 포함
    e2 = CircuitBreakerOpenException(
        circuit_name="db_circuit",
        reset_timeout_seconds=60.0,
        failure_count=10,
    )
    check(r, "CircuitBreaker circuit_name", e2.details.get("circuit_name") == "db_circuit")
    check(r, "CircuitBreaker reset_timeout", e2.details.get("reset_timeout_seconds") == 60.0)
    check(r, "CircuitBreaker failure_count", e2.details.get("failure_count") == 10)


# =============================================================================
# [2] 데이터베이스 예외
# =============================================================================
def test_database_exception(r: TestResult) -> None:
    """DatabaseException 테스트."""
    e = DatabaseException()
    check(r, "DatabaseException 기본 생성", isinstance(e, CourtViewException))
    check(r, "DatabaseException ErrorCode", e.code == ErrorCode.DATABASE_ERROR.code)

    # 매개변수 포함 + 쿼리 산출
    e2 = DatabaseException(
        operation="SELECT",
        table="users",
        query="SELECT * FROM users WHERE id = 1",
    )
    check(r, "DatabaseException operation", e2.operation == "SELECT")
    check(r, "DatabaseException table", e2.table == "users")
    check(r, "DatabaseException query 산출", e2.query is not None)
    check(r, "DatabaseException details.operation", e2.details.get("operation") == "SELECT")
    check(r, "DatabaseException details.table", e2.details.get("table") == "users")
    check(r, "DatabaseException details.query_preview 존재",
          "query_preview" in e2.details)


def test_database_exception_sanitize(r: TestResult) -> None:
    """DatabaseException._sanitize_query 보안 기능 테스트."""
    e = DatabaseException(
        query="SELECT * FROM users WHERE password='secret123' AND token='abc'",
    )
    check(r, "DB 쿼리 password 마스킹", "secret123" not in (e.query or ""))
    check(r, "DB 쿼리 password=*** 포함", "password='***'" in (e.query or ""))
    check(r, "DB 쿼리 token 마스킹", "'abc'" not in (e.query or ""))
    check(r, "DB 쿼리 token=*** 포함", "token='***'" in (e.query or ""))

    # 민감 정보 없는 쿼리
    e2 = DatabaseException(query="SELECT id FROM users")
    check(r, "DB 비민감 쿼리 유지", e2.query == "SELECT id FROM users")

    # 긴 쿼리 미리보기 자르기
    long_query = "SELECT " + "a, " * 100 + "b FROM table1"
    e3 = DatabaseException(query=long_query)
    preview = e3.details.get("query_preview", "")
    check(r, "DB 긴 쿼리 미리보기 자르기", len(preview) <= 103 and preview.endswith("..."))


def test_database_connection_exception(r: TestResult) -> None:
    """DatabaseConnectionException 테스트."""
    e = DatabaseConnectionException(host="db.local", port=5432, database="courtview")
    check(r, "DatabaseConnectionException Retryable", isinstance(e, RetryableException))
    check(r, "DatabaseConnectionException ErrorCode",
          e.code == ErrorCode.DATABASE_CONNECTION_FAILED.code)
    check(r, "DatabaseConnectionException host", e.details.get("host") == "db.local")
    check(r, "DatabaseConnectionException port", e.details.get("port") == 5432)
    check(r, "DatabaseConnectionException database", e.details.get("database") == "courtview")


def test_database_timeout_exception(r: TestResult) -> None:
    """DatabaseTimeoutException 테스트."""
    e = DatabaseTimeoutException(timeout_seconds=30.0, query="SELECT * FROM big_table")
    check(r, "DatabaseTimeoutException Retryable", isinstance(e, RetryableException))
    check(r, "DatabaseTimeoutException ErrorCode",
          e.code == ErrorCode.DATABASE_TIMEOUT.code)
    check(r, "DatabaseTimeoutException timeout_seconds", e.details.get("timeout_seconds") == 30.0)
    check(r, "DatabaseTimeoutException query_preview 존재", "query_preview" in e.details)

    # 긴 쿼리 미리보기 자르기
    long_q = "SELECT " + "a, " * 50 + "b FROM t"
    e2 = DatabaseTimeoutException(query=long_q)
    preview = e2.details.get("query_preview", "")
    check(r, "DBTimeout 긴 쿼리 자르기", len(preview) <= 53 and preview.endswith("..."))


def test_database_integrity_exception(r: TestResult) -> None:
    """DatabaseIntegrityException 테스트."""
    e = DatabaseIntegrityException(
        constraint_name="uq_email",
        constraint_type="UNIQUE",
        table="users",
        column="email",
    )
    check(r, "DatabaseIntegrityException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "DatabaseIntegrityException ErrorCode",
          e.code == ErrorCode.DATABASE_INTEGRITY_ERROR.code)
    check(r, "DBIntegrity constraint_name", e.details.get("constraint_name") == "uq_email")
    check(r, "DBIntegrity constraint_type", e.details.get("constraint_type") == "UNIQUE")
    check(r, "DBIntegrity table", e.details.get("table") == "users")
    check(r, "DBIntegrity column", e.details.get("column") == "email")


def test_transaction_exception(r: TestResult) -> None:
    """TransactionException 테스트."""
    e = TransactionException(transaction_id="tx-001", isolation_level="SERIALIZABLE")
    check(r, "TransactionException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "TransactionException ErrorCode",
          e.code == ErrorCode.DATABASE_TRANSACTION_FAILED.code)
    check(r, "TransactionException transaction_id", e.details.get("transaction_id") == "tx-001")
    check(r, "TransactionException isolation_level",
          e.details.get("isolation_level") == "SERIALIZABLE")


def test_record_not_found_exception(r: TestResult) -> None:
    """RecordNotFoundException 보안 기능 테스트."""
    e = RecordNotFoundException(
        table="users",
        record_id=42,
        search_criteria={"email": "a@b.com", "password": "secret", "token": "abc"},
    )
    check(r, "RecordNotFoundException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "RecordNotFoundException record_id", e.details.get("record_id") == "42")
    criteria = e.details.get("search_criteria", {})
    check(r, "RecordNotFound 민감키 password 제외", "password" not in criteria)
    check(r, "RecordNotFound 민감키 token 제외", "token" not in criteria)
    check(r, "RecordNotFound 비민감키 email 유지", "email" in criteria)


def test_connection_pool_exception(r: TestResult) -> None:
    """ConnectionPoolException + 팩토리 메서드 테스트."""
    e = ConnectionPoolException(
        pool_name="db_pool", pool_size=10,
        active_connections=10, waiting_requests=5,
    )
    check(r, "ConnectionPoolException Retryable", isinstance(e, RetryableException))
    check(r, "ConnectionPool pool_name", e.details.get("pool_name") == "db_pool")
    check(r, "ConnectionPool pool_size", e.details.get("pool_size") == 10)
    check(r, "ConnectionPool active_connections", e.details.get("active_connections") == 10)
    check(r, "ConnectionPool waiting_requests", e.details.get("waiting_requests") == 5)

    # pool_exhausted 팩토리
    e2 = ConnectionPoolException.pool_exhausted("main_pool", 20, 20)
    check(r, "pool_exhausted 인스턴스 타입", isinstance(e2, ConnectionPoolException))
    check(r, "pool_exhausted 메시지 포함", "고갈" in str(e2))
    check(r, "pool_exhausted pool_name", e2.details.get("pool_name") == "main_pool")

    # acquisition_timeout 팩토리
    e3 = ConnectionPoolException.acquisition_timeout("read_pool", 5.0)
    check(r, "acquisition_timeout 인스턴스 타입", isinstance(e3, ConnectionPoolException))
    check(r, "acquisition_timeout 메시지 포함", "시간 초과" in str(e3))


# =============================================================================
# [3] 캐시 예외
# =============================================================================
def test_cache_exception(r: TestResult) -> None:
    """CacheException + 민감 키 마스킹 테스트."""
    e = CacheException(cache_key="user:123", operation="GET")
    check(r, "CacheException 기본 생성", isinstance(e, CourtViewException))
    check(r, "CacheException cache_key", e.details.get("cache_key") == "user:123")
    check(r, "CacheException operation", e.details.get("operation") == "GET")


def test_cache_key_masking(r: TestResult) -> None:
    """CacheException._mask_sensitive_key 보안 기능."""
    # token: 패턴 마스킹
    e1 = CacheException(cache_key="token:abc123")
    check(r, "CacheKey token: 마스킹", e1.details.get("cache_key") == "token:***")

    # session: 패턴 마스킹
    e2 = CacheException(cache_key="session:xyz789")
    check(r, "CacheKey session: 마스킹", e2.details.get("cache_key") == "session:***")

    # auth: 패턴 마스킹
    e3 = CacheException(cache_key="auth:bearer_token")
    check(r, "CacheKey auth: 마스킹", e3.details.get("cache_key") == "auth:***")

    # secret: 패턴 마스킹
    e4 = CacheException(cache_key="secret:mysecret")
    check(r, "CacheKey secret: 마스킹", e4.details.get("cache_key") == "secret:***")

    # 비민감 키는 그대로
    e5 = CacheException(cache_key="player:stats:42")
    check(r, "CacheKey 비민감 키 유지", e5.details.get("cache_key") == "player:stats:42")


def test_cache_connection_exception(r: TestResult) -> None:
    """CacheConnectionException 테스트."""
    e = CacheConnectionException(host="redis.local", port=6379)
    check(r, "CacheConnectionException Retryable", isinstance(e, RetryableException))
    check(r, "CacheConnectionException ErrorCode",
          e.code == ErrorCode.CACHE_CONNECTION_FAILED.code)
    check(r, "CacheConnectionException host", e.details.get("host") == "redis.local")
    check(r, "CacheConnectionException port", e.details.get("port") == 6379)


def test_cache_key_not_found_exception(r: TestResult) -> None:
    """CacheKeyNotFoundException 테스트."""
    e = CacheKeyNotFoundException(cache_key="missing_key")
    check(r, "CacheKeyNotFoundException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "CacheKeyNotFoundException cache_key", e.details.get("cache_key") == "missing_key")


def test_cache_serialization_exception(r: TestResult) -> None:
    """CacheSerializationException 테스트."""
    e = CacheSerializationException(operation="deserialize", data_type="json")
    check(r, "CacheSerializationException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "CacheSerializationException operation", e.details.get("operation") == "deserialize")
    check(r, "CacheSerializationException data_type", e.details.get("data_type") == "json")


def test_redis_exception(r: TestResult) -> None:
    """RedisException 테스트."""
    e = RedisException(redis_command="SET", cluster_node="node1", error_type="MOVED")
    check(r, "RedisException CacheException 하위", isinstance(e, CacheException))
    check(r, "RedisException cache_type 자동 설정", e.details.get("cache_type") == "redis")
    check(r, "RedisException redis_command", e.details.get("redis_command") == "SET")
    check(r, "RedisException cluster_node", e.details.get("cluster_node") == "node1")
    check(r, "RedisException error_type", e.details.get("error_type") == "MOVED")


# =============================================================================
# [4] 메시지 큐 예외
# =============================================================================
def test_queue_exception(r: TestResult) -> None:
    """QueueException 테스트."""
    e = QueueException(queue_name="analysis_queue", task_id="task-001")
    check(r, "QueueException 기본 생성", isinstance(e, CourtViewException))
    check(r, "QueueException queue_name", e.details.get("queue_name") == "analysis_queue")
    check(r, "QueueException task_id", e.details.get("task_id") == "task-001")


def test_queue_connection_exception(r: TestResult) -> None:
    """QueueConnectionException + URL 마스킹 보안 기능."""
    e = QueueConnectionException(broker_url="amqp://user:password123@rabbit.local:5672/vhost")
    check(r, "QueueConnectionException Retryable", isinstance(e, RetryableException))
    safe_url = e.details.get("broker_url", "")
    check(r, "QueueConn URL 비밀번호 마스킹", "password123" not in safe_url)
    check(r, "QueueConn URL ***:*** 포함", "***:***@" in safe_url)
    check(r, "QueueConn URL 호스트 유지", "rabbit.local" in safe_url)


def test_task_enqueue_exception(r: TestResult) -> None:
    """TaskEnqueueException 테스트."""
    e = TaskEnqueueException(task_name="analyze_video", queue_name="high_priority")
    check(r, "TaskEnqueueException Retryable", isinstance(e, RetryableException))
    check(r, "TaskEnqueueException task_name", e.details.get("task_name") == "analyze_video")
    check(r, "TaskEnqueueException queue_name", e.details.get("queue_name") == "high_priority")


def test_task_execution_exception(r: TestResult) -> None:
    """TaskExecutionException 테스트."""
    e = TaskExecutionException(
        task_id="task-002", task_name="pose_estimation",
        worker_id="worker-1", execution_time=45.5,
    )
    check(r, "TaskExecutionException CourtViewException", isinstance(e, CourtViewException))
    check(r, "TaskExecutionException task_id", e.details.get("task_id") == "task-002")
    check(r, "TaskExecutionException execution_time", e.details.get("execution_time") == 45.5)


def test_task_timeout_exception(r: TestResult) -> None:
    """TaskTimeoutException 테스트."""
    e = TaskTimeoutException(task_id="task-003", timeout_seconds=300.0)
    check(r, "TaskTimeoutException Retryable", isinstance(e, RetryableException))
    check(r, "TaskTimeoutException timeout_seconds", e.details.get("timeout_seconds") == 300.0)


# =============================================================================
# [5] 알림/워커/이벤트버스/정리 예외
# =============================================================================
def test_alert_delivery_exception(r: TestResult) -> None:
    """AlertDeliveryException 테스트."""
    e = AlertDeliveryException(
        channel="slack", alert_id="alert-001",
        recipient="#alerts", http_status=502, retry_after=5.0,
    )
    check(r, "AlertDeliveryException Retryable", isinstance(e, RetryableException))
    check(r, "AlertDeliveryException channel", e.details.get("channel") == "slack")
    check(r, "AlertDeliveryException alert_id", e.details.get("alert_id") == "alert-001")
    check(r, "AlertDeliveryException http_status", e.details.get("http_status") == 502)
    check(r, "AlertDeliveryException retry_after detail", e.details.get("retry_after") == 5.0)


def test_alert_configuration_exception(r: TestResult) -> None:
    """AlertConfigurationException 테스트."""
    e = AlertConfigurationException(
        channel="email", config_key="smtp_host",
        expected_type="str", actual_value=123,
    )
    check(r, "AlertConfigurationException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "AlertConfigurationException channel", e.details.get("channel") == "email")
    check(r, "AlertConfigurationException config_key", e.details.get("config_key") == "smtp_host")
    check(r, "AlertConfigurationException expected_type", e.details.get("expected_type") == "str")
    check(r, "AlertConfigurationException actual_value", e.details.get("actual_value") == "123")


def test_worker_exception(r: TestResult) -> None:
    """WorkerException 테스트."""
    e = WorkerException(worker_id="w-01", worker_type="analysis", task_id="t-01")
    check(r, "WorkerException CourtViewException", isinstance(e, CourtViewException))
    check(r, "WorkerException worker_id", e.details.get("worker_id") == "w-01")
    check(r, "WorkerException worker_type", e.details.get("worker_type") == "analysis")


def test_notification_exception(r: TestResult) -> None:
    """NotificationException 테스트."""
    e = NotificationException(notification_type="push", recipient="user-42")
    check(r, "NotificationException CourtViewException", isinstance(e, CourtViewException))
    check(r, "NotificationException notification_type",
          e.details.get("notification_type") == "push")
    check(r, "NotificationException recipient", e.details.get("recipient") == "user-42")


def test_cleanup_exception(r: TestResult) -> None:
    """CleanupException 테스트."""
    e = CleanupException(cleanup_type="temp_files", target_path="/tmp/analysis")
    check(r, "CleanupException CourtViewException", isinstance(e, CourtViewException))
    check(r, "CleanupException cleanup_type", e.details.get("cleanup_type") == "temp_files")
    check(r, "CleanupException target_path", e.details.get("target_path") == "/tmp/analysis")


def test_event_bus_exception(r: TestResult) -> None:
    """EventBusException + 팩토리 메서드 테스트."""
    e = EventBusException(
        event_type="analysis.complete", event_id="ev-001",
        handler_name="notify_handler", operation="publish",
    )
    check(r, "EventBusException CourtViewException", isinstance(e, CourtViewException))
    check(r, "EventBusException event_type",
          e.details.get("event_type") == "analysis.complete")
    check(r, "EventBusException handler_name",
          e.details.get("handler_name") == "notify_handler")

    # publish_failed 팩토리
    e2 = EventBusException.publish_failed("game.started", event_id="ev-002")
    check(r, "publish_failed 인스턴스 타입", isinstance(e2, EventBusException))
    check(r, "publish_failed 메시지", "발행" in str(e2))
    check(r, "publish_failed operation", e2.details.get("operation") == "publish")

    # handler_failed 팩토리
    e3 = EventBusException.handler_failed("game.started", "score_handler")
    check(r, "handler_failed 인스턴스 타입", isinstance(e3, EventBusException))
    check(r, "handler_failed 메시지", "핸들러" in str(e3))
    check(r, "handler_failed operation", e3.details.get("operation") == "handle")


# =============================================================================
# [6] 스토리지 예외
# =============================================================================
def test_storage_exception(r: TestResult) -> None:
    """StorageException 테스트."""
    e = StorageException(storage_type="s3", file_path="/data/video.mp4", operation="read")
    check(r, "StorageException CourtViewException", isinstance(e, CourtViewException))
    check(r, "StorageException storage_type", e.details.get("storage_type") == "s3")
    check(r, "StorageException file_path", e.details.get("file_path") == "/data/video.mp4")
    check(r, "StorageException operation", e.details.get("operation") == "read")


def test_s3_exception(r: TestResult) -> None:
    """S3Exception 테스트."""
    e = S3Exception(bucket="courtview-bucket", key="videos/game1.mp4", operation="get")
    check(r, "S3Exception StorageException 하위", isinstance(e, StorageException))
    check(r, "S3Exception storage_type 자동", e.details.get("storage_type") == "s3")
    check(r, "S3Exception bucket", e.details.get("bucket") == "courtview-bucket")
    check(r, "S3Exception key", e.details.get("key") == "videos/game1.mp4")


def test_s3_upload_exception(r: TestResult) -> None:
    """S3UploadException 테스트."""
    e = S3UploadException(bucket="bucket", key="video.mp4", file_size=104857600)
    check(r, "S3UploadException Retryable", isinstance(e, RetryableException))
    check(r, "S3UploadException storage_type", e.details.get("storage_type") == "s3")
    check(r, "S3UploadException operation", e.details.get("operation") == "upload")
    check(r, "S3UploadException file_size_bytes", e.details.get("file_size_bytes") == 104857600)
    check(r, "S3UploadException file_size_mb", e.details.get("file_size_mb") == 100.0)


def test_s3_download_exception(r: TestResult) -> None:
    """S3DownloadException 테스트."""
    e = S3DownloadException(bucket="bucket", key="video.mp4")
    check(r, "S3DownloadException Retryable", isinstance(e, RetryableException))
    check(r, "S3DownloadException storage_type", e.details.get("storage_type") == "s3")
    check(r, "S3DownloadException operation", e.details.get("operation") == "download")


def test_s3_object_not_found(r: TestResult) -> None:
    """S3ObjectNotFoundException 테스트."""
    e = S3ObjectNotFoundException(bucket="bucket", key="missing.mp4")
    check(r, "S3ObjectNotFoundException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "S3ObjectNotFoundException storage_type", e.details.get("storage_type") == "s3")
    check(r, "S3ObjectNotFoundException key", e.details.get("key") == "missing.mp4")


def test_s3_permission_exception(r: TestResult) -> None:
    """S3PermissionException 테스트."""
    e = S3PermissionException(
        bucket="bucket", key="secret.mp4", required_permission="s3:GetObject",
    )
    check(r, "S3PermissionException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "S3PermissionException required_permission",
          e.details.get("required_permission") == "s3:GetObject")


def test_metadata_extraction_exception(r: TestResult) -> None:
    """MetadataExtractionException + 팩토리 메서드 테스트."""
    e = MetadataExtractionException(
        file_path="/data/video.mp4", media_type="video", extraction_method="ffprobe",
    )
    check(r, "MetadataExtractionException StorageException 하위",
          isinstance(e, StorageException))
    check(r, "MetadataExtractionException media_type", e.details.get("media_type") == "video")
    check(r, "MetadataExtractionException extraction_method",
          e.details.get("extraction_method") == "ffprobe")

    # ffprobe_failed 팩토리
    e2 = MetadataExtractionException.ffprobe_failed("/data/v.mp4", "codec not found")
    check(r, "ffprobe_failed 인스턴스 타입", isinstance(e2, MetadataExtractionException))
    check(r, "ffprobe_failed ffprobe_error", e2.details.get("ffprobe_error") == "codec not found")

    # opencv_failed 팩토리
    e3 = MetadataExtractionException.opencv_failed("/data/v.mp4", "cannot open")
    check(r, "opencv_failed 인스턴스 타입", isinstance(e3, MetadataExtractionException))
    check(r, "opencv_failed reason", e3.details.get("reason") == "cannot open")

    # unsupported_format 팩토리
    e4 = MetadataExtractionException.unsupported_format("/data/v.webm", "webm")
    check(r, "unsupported_format 인스턴스 타입", isinstance(e4, MetadataExtractionException))
    check(r, "unsupported_format detected_format", e4.details.get("detected_format") == "webm")


def test_local_storage_exception(r: TestResult) -> None:
    """LocalStorageException 테스트."""
    e = LocalStorageException(file_path="/tmp/data.bin", operation="write")
    check(r, "LocalStorageException StorageException 하위", isinstance(e, StorageException))
    check(r, "LocalStorageException storage_type", e.details.get("storage_type") == "local")


def test_disk_space_exception(r: TestResult) -> None:
    """DiskSpaceException (CriticalException) 테스트."""
    e = DiskSpaceException(
        required_bytes=1073741824,
        available_bytes=536870912,
        mount_point="/data",
    )
    check(r, "DiskSpaceException CriticalException", isinstance(e, CriticalException))
    check(r, "DiskSpaceException alert_required", e.alert_required is True)
    check(r, "DiskSpaceException severity", e.severity == 5)
    check(r, "DiskSpaceException required_mb", e.details.get("required_mb") == 1024.0)
    check(r, "DiskSpaceException available_mb", e.details.get("available_mb") == 512.0)
    check(r, "DiskSpaceException mount_point", e.details.get("mount_point") == "/data")


def test_file_permission_exception(r: TestResult) -> None:
    """FilePermissionException 테스트."""
    e = FilePermissionException(file_path="/etc/config", required_permission="write")
    check(r, "FilePermissionException NonRetryable", isinstance(e, NonRetryableException))
    check(r, "FilePermissionException storage_type", e.details.get("storage_type") == "local")
    check(r, "FilePermissionException file_path", e.details.get("file_path") == "/etc/config")
    check(r, "FilePermissionException required_permission",
          e.details.get("required_permission") == "write")


# =============================================================================
# [7] 스트림 예외
# =============================================================================
def test_stream_exception(r: TestResult) -> None:
    """StreamException 기본 + URL 산출 테스트."""
    e = StreamException(stream_url="rtsp://camera1.local/stream", stream_type="RTSP")
    check(r, "StreamException Retryable", isinstance(e, RetryableException))
    check(r, "StreamException stream_type", e.details.get("stream_type") == "RTSP")
    check(r, "StreamException URL 존재", "stream_url" in e.details)


def test_stream_url_sanitization(r: TestResult) -> None:
    """StreamException._sanitize_stream_url 보안 기능."""
    # 인증 정보 제거
    e = StreamException(stream_url="rtsp://admin:password@192.168.1.1:554/live")
    sanitized = e.details.get("stream_url", "")
    check(r, "StreamURL 인증정보 제거 (password)", "password" not in sanitized)
    check(r, "StreamURL 인증정보 제거 (admin)", "admin" not in sanitized)
    check(r, "StreamURL 호스트 유지", "192.168.1.1" in sanitized)

    # 쿼리 파라미터 제거
    e2 = StreamException(stream_url="https://stream.example.com/live?token=abc123")
    sanitized2 = e2.details.get("stream_url", "")
    check(r, "StreamURL 쿼리 파라미터 제거", "token" not in sanitized2)

    # 잘못된 URL
    sanitized3 = StreamException._sanitize_stream_url("not_a_url")
    check(r, "StreamURL 잘못된 URL 처리", isinstance(sanitized3, str))


def test_stream_factory_methods(r: TestResult) -> None:
    """StreamException 9개 팩토리 메서드 테스트."""
    url = "rtsp://cam.local/stream"

    # connection_failed
    e1 = StreamException.connection_failed(url, "RTSP", "timeout")
    check(r, "stream.connection_failed 타입", isinstance(e1, StreamException))
    check(r, "stream.connection_failed 메시지", "연결" in str(e1))

    # disconnected
    e2 = StreamException.disconnected(url, "RTSP", duration_seconds=120.5)
    check(r, "stream.disconnected 타입", isinstance(e2, StreamException))
    check(r, "stream.disconnected duration",
          e2.details.get("duration_seconds") == 120.5)

    # timeout
    e3 = StreamException.timeout(url, 30.0, "connect")
    check(r, "stream.timeout 타입", isinstance(e3, StreamException))
    check(r, "stream.timeout timeout_seconds", e3.details.get("timeout_seconds") == 30.0)

    # invalid_source
    e4 = StreamException.invalid_source(url, "protocol not supported")
    check(r, "stream.invalid_source 타입", isinstance(e4, StreamException))
    check(r, "stream.invalid_source 메시지", "유효하지 않은" in str(e4))

    # unsupported_type
    e5 = StreamException.unsupported_type("SRT", ["RTSP", "HLS", "RTMP"])
    check(r, "stream.unsupported_type 타입", isinstance(e5, StreamException))
    check(r, "stream.unsupported_type supported_types",
          e5.details.get("supported_types") == ["RTSP", "HLS", "RTMP"])

    # buffer_overflow
    e6 = StreamException.buffer_overflow(url, 1024, 512)
    check(r, "stream.buffer_overflow 타입", isinstance(e6, StreamException))
    check(r, "stream.buffer_overflow buffer_size", e6.details.get("buffer_size") == 1024)
    check(r, "stream.buffer_overflow max_buffer_size",
          e6.details.get("max_buffer_size") == 512)

    # decode_error
    e7 = StreamException.decode_error(url, "h264", "corrupted NAL unit")
    check(r, "stream.decode_error 타입", isinstance(e7, StreamException))
    check(r, "stream.decode_error codec", e7.details.get("codec") == "h264")

    # frame_error
    e8 = StreamException.frame_error(url, frame_number=100, reason="damaged")
    check(r, "stream.frame_error 타입", isinstance(e8, StreamException))
    check(r, "stream.frame_error frame_number", e8.details.get("frame_number") == 100)

    # authentication_failed
    e9 = StreamException.authentication_failed(url, "invalid credentials")
    check(r, "stream.authentication_failed 타입", isinstance(e9, StreamException))
    check(r, "stream.authentication_failed 메시지", "인증" in str(e9))


# =============================================================================
# [8] 연결 예외
# =============================================================================
def test_connection_exception(r: TestResult) -> None:
    """ConnectionException + 팩토리 메서드 테스트."""
    e = ConnectionException(host="api.server.com", port=8080, protocol="HTTP")
    check(r, "ConnectionException Retryable", isinstance(e, RetryableException))
    check(r, "ConnectionException host", e.details.get("host") == "api.server.com")
    check(r, "ConnectionException port", e.details.get("port") == 8080)
    check(r, "ConnectionException protocol", e.details.get("protocol") == "HTTP")

    # connection_refused 팩토리
    e2 = ConnectionException.connection_refused("db.local", 5432)
    check(r, "connection_refused 타입", isinstance(e2, ConnectionException))
    check(r, "connection_refused 메시지", "거부" in str(e2))

    # connection_timeout 팩토리
    e3 = ConnectionException.connection_timeout("api.local", 10.0, 443)
    check(r, "connection_timeout 타입", isinstance(e3, ConnectionException))
    check(r, "connection_timeout timeout_seconds", e3.details.get("timeout_seconds") == 10.0)

    # host_unreachable 팩토리
    e4 = ConnectionException.host_unreachable("10.0.0.1", "network unreachable")
    check(r, "host_unreachable 타입", isinstance(e4, ConnectionException))
    check(r, "host_unreachable 메시지", "도달" in str(e4))


# =============================================================================
# [9] 외부 서비스 예외
# =============================================================================
def test_external_service_exception(r: TestResult) -> None:
    """ExternalServiceException 테스트."""
    e = ExternalServiceException(
        service_name="courtview_backend", endpoint="/api/v1/results",
        status_code=503,
    )
    check(r, "ExternalServiceException Retryable", isinstance(e, RetryableException))
    check(r, "ExternalServiceException service_name",
          e.details.get("service_name") == "courtview_backend")
    check(r, "ExternalServiceException endpoint",
          e.details.get("endpoint") == "/api/v1/results")
    check(r, "ExternalServiceException status_code", e.details.get("status_code") == 503)


def test_webhook_exception(r: TestResult) -> None:
    """WebhookException + URL 쿼리 파라미터 제거 보안 기능."""
    e = WebhookException(
        webhook_url="https://hooks.slack.com/services/T/B/xxx?token=secret",
        event_type="analysis.complete",
        status_code=500,
    )
    check(r, "WebhookException Retryable", isinstance(e, RetryableException))
    webhook_url = e.details.get("webhook_url", "")
    check(r, "WebhookException URL 쿼리 제거", "token=secret" not in webhook_url)
    check(r, "WebhookException URL 기본부분 유지",
          "hooks.slack.com" in webhook_url)
    check(r, "WebhookException event_type",
          e.details.get("event_type") == "analysis.complete")
    check(r, "WebhookException status_code", e.details.get("status_code") == 500)


# =============================================================================
# [10] 디코딩 예외
# =============================================================================
def test_decoding_exception(r: TestResult) -> None:
    """DecodingException + 팩토리 메서드 테스트."""
    e = DecodingException(
        video_path="/data/video.mp4", frame_number=100, codec="h264",
    )
    check(r, "DecodingException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "DecodingException video_path", e.video_path == "/data/video.mp4")
    check(r, "DecodingException frame_number", e.frame_number == 100)
    check(r, "DecodingException codec", e.codec == "h264")

    # init_failed 팩토리
    e2 = DecodingException.init_failed("/data/v.mp4", "no decoder available")
    check(r, "decoding.init_failed 타입", isinstance(e2, DecodingException))
    check(r, "decoding.init_failed 메시지", "초기화" in str(e2))

    # frame_failed 팩토리
    e3 = DecodingException.frame_failed("/data/v.mp4", 50, "corrupted")
    check(r, "decoding.frame_failed 타입", isinstance(e3, DecodingException))

    # seek_failed 팩토리
    e4 = DecodingException.seek_failed("/data/v.mp4", 1000)
    check(r, "decoding.seek_failed 타입", isinstance(e4, DecodingException))


def test_codec_exception(r: TestResult) -> None:
    """CodecException + 팩토리 메서드 테스트."""
    e = CodecException(
        codec_name="hevc", required_codec="h264", video_path="/data/v.mp4",
    )
    check(r, "CodecException DecodingException 하위", isinstance(e, DecodingException))
    check(r, "CodecException codec_name", e.codec_name == "hevc")
    check(r, "CodecException required_codec", e.required_codec == "h264")

    # not_found 팩토리
    e2 = CodecException.not_found("av1", "/data/v.mp4")
    check(r, "codec.not_found 타입", isinstance(e2, CodecException))

    # not_supported 팩토리
    e3 = CodecException.not_supported("vp9", "/data/v.mp4")
    check(r, "codec.not_supported 타입", isinstance(e3, CodecException))

    # init_failed 팩토리
    e4 = CodecException.init_failed("h264", "missing library")
    check(r, "codec.init_failed 타입", isinstance(e4, CodecException))


def test_corrupted_file_exception(r: TestResult) -> None:
    """CorruptedFileException + 팩토리 메서드 테스트."""
    e = CorruptedFileException(
        file_path="/data/corrupt.mp4",
        corruption_type="header",
        affected_range=(0, 1024),
    )
    check(r, "CorruptedFileException DecodingException 하위",
          isinstance(e, DecodingException))
    check(r, "CorruptedFileException file_path", e.file_path == "/data/corrupt.mp4")
    check(r, "CorruptedFileException corruption_type", e.corruption_type == "header")
    check(r, "CorruptedFileException affected_range", e.affected_range == (0, 1024))

    # header_corrupted 팩토리
    e2 = CorruptedFileException.header_corrupted("/data/v.mp4")
    check(r, "corrupted.header_corrupted 타입", isinstance(e2, CorruptedFileException))

    # frame_corrupted 팩토리
    e3 = CorruptedFileException.frame_corrupted("/data/v.mp4", 50)
    check(r, "corrupted.frame_corrupted 타입", isinstance(e3, CorruptedFileException))

    # incomplete_file 팩토리
    e4 = CorruptedFileException.incomplete_file("/data/v.mp4", 1000, 500)
    check(r, "corrupted.incomplete_file 타입", isinstance(e4, CorruptedFileException))


# =============================================================================
# [11] 프레임 추출 + 스트림 종료 예외
# =============================================================================
def test_frame_extraction_exception(r: TestResult) -> None:
    """FrameExtractionException + 팩토리 메서드 테스트."""
    e = FrameExtractionException(
        video_path="/data/v.mp4", frame_index=200, extraction_method="opencv",
    )
    check(r, "FrameExtractionException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "FrameExtractionException video_path", e.video_path == "/data/v.mp4")
    check(r, "FrameExtractionException frame_index", e.frame_index == 200)

    # init_failed 팩토리
    e2 = FrameExtractionException.init_failed("/data/v.mp4", "opencv not installed")
    check(r, "frame.init_failed 타입", isinstance(e2, FrameExtractionException))

    # extraction_failed 팩토리
    e3 = FrameExtractionException.extraction_failed("/data/v.mp4", 100, "decode error")
    check(r, "frame.extraction_failed 타입", isinstance(e3, FrameExtractionException))

    # timeout 팩토리
    e4 = FrameExtractionException.timeout("/data/v.mp4", 5.0)
    check(r, "frame.timeout 타입", isinstance(e4, FrameExtractionException))

    # invalid_range 팩토리
    e5 = FrameExtractionException.invalid_range("/data/v.mp4", -1, 1000, 500)
    check(r, "frame.invalid_range 타입", isinstance(e5, FrameExtractionException))

    # keyframe_detection_failed 팩토리
    e6 = FrameExtractionException.keyframe_detection_failed("/data/v.mp4", "no keyframes")
    check(r, "frame.keyframe_detection_failed 타입", isinstance(e6, FrameExtractionException))

    # buffer_overflow 팩토리
    e7 = FrameExtractionException.buffer_overflow("/data/v.mp4", 1024, 512)
    check(r, "frame.buffer_overflow 타입", isinstance(e7, FrameExtractionException))


def test_end_of_stream_exception(r: TestResult) -> None:
    """EndOfStreamException + 팩토리 메서드 테스트."""
    e = EndOfStreamException(
        video_path="/data/v.mp4", last_frame_index=999, total_frames=1000,
    )
    check(r, "EndOfStreamException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "EndOfStreamException video_path", e.video_path == "/data/v.mp4")
    check(r, "EndOfStreamException last_frame_index", e.last_frame_index == 999)

    # video_end 팩토리
    e2 = EndOfStreamException.video_end("/data/v.mp4", 999, 1000)
    check(r, "eos.video_end 타입", isinstance(e2, EndOfStreamException))

    # stream_closed 팩토리
    e3 = EndOfStreamException.stream_closed("rtsp://cam/stream")
    check(r, "eos.stream_closed 타입", isinstance(e3, EndOfStreamException))


# =============================================================================
# [12] 정규화/해상도 예외
# =============================================================================
def test_normalization_exception(r: TestResult) -> None:
    """NormalizationException + 팩토리 메서드 테스트."""
    e = NormalizationException(
        video_path="/data/v.mp4",
        source_resolution=(3840, 2160),
        target_resolution=(1920, 1080),
        normalization_type="resolution",
    )
    check(r, "NormalizationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "NormalizationException video_path", e.video_path == "/data/v.mp4")
    check(r, "NormalizationException source_resolution", e.source_resolution == (3840, 2160))

    # init_failed 팩토리
    e2 = NormalizationException.init_failed("/data/v.mp4", "missing ffmpeg")
    check(r, "norm.init_failed 타입", isinstance(e2, NormalizationException))

    # resolution_failed 팩토리
    e3 = NormalizationException.resolution_failed(
        "/data/v.mp4", (3840, 2160), (1920, 1080), "interpolation error",
    )
    check(r, "norm.resolution_failed 타입", isinstance(e3, NormalizationException))

    # fps_failed 팩토리
    e4 = NormalizationException.fps_failed("/data/v.mp4", 120.0, 30.0, "unsupported")
    check(r, "norm.fps_failed 타입", isinstance(e4, NormalizationException))

    # format_failed 팩토리
    e5 = NormalizationException.format_failed("/data/v.mp4", "avi", "mp4", "codec mismatch")
    check(r, "norm.format_failed 타입", isinstance(e5, NormalizationException))

    # color_space_failed 팩토리
    e6 = NormalizationException.color_space_failed("/data/v.mp4", "YUV420", "RGB", "unsupported")
    check(r, "norm.color_space_failed 타입", isinstance(e6, NormalizationException))

    # aspect_ratio_failed 팩토리
    e7 = NormalizationException.aspect_ratio_failed("/data/v.mp4", 1.33, 1.78, "distortion")
    check(r, "norm.aspect_ratio_failed 타입", isinstance(e7, NormalizationException))


def test_resolution_exception(r: TestResult) -> None:
    """ResolutionException + 팩토리 메서드 테스트."""
    e = ResolutionException(
        width=640, height=480,
        min_resolution=(720, 480),
        max_resolution=(3840, 2160),
    )
    check(r, "ResolutionException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "ResolutionException width", e.width == 640)
    check(r, "ResolutionException height", e.height == 480)

    # invalid_resolution 팩토리
    e2 = ResolutionException.invalid_resolution(0, 0, "zero dimensions")
    check(r, "resolution.invalid_resolution 타입", isinstance(e2, ResolutionException))

    # unsupported_resolution 팩토리
    e3 = ResolutionException.unsupported_resolution(7680, 4320, [(1920, 1080), (3840, 2160)])
    check(r, "resolution.unsupported_resolution 타입", isinstance(e3, ResolutionException))

    # below_minimum 팩토리
    e4 = ResolutionException.below_minimum(320, 240, 720, 480)
    check(r, "resolution.below_minimum 타입", isinstance(e4, ResolutionException))

    # above_maximum 팩토리
    e5 = ResolutionException.above_maximum(7680, 4320, 3840, 2160)
    check(r, "resolution.above_maximum 타입", isinstance(e5, ResolutionException))

    # interpolation_failed 팩토리
    e6 = ResolutionException.interpolation_failed((1920, 1080), (3840, 2160), "LANCZOS")
    check(r, "resolution.interpolation_failed 타입", isinstance(e6, ResolutionException))


# =============================================================================
# [13] 분류/샘플링 예외
# =============================================================================
def test_classification_exception(r: TestResult) -> None:
    """ClassificationException + 팩토리 메서드 테스트."""
    e = ClassificationException(
        video_path="/data/v.mp4", video_type="GAME",
        confidence=0.4, threshold=0.8,
    )
    check(r, "ClassificationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "ClassificationException video_path", e.video_path == "/data/v.mp4")
    check(r, "ClassificationException video_type", e.video_type == "GAME")
    check(r, "ClassificationException confidence", e.confidence == 0.4)
    check(r, "ClassificationException threshold", e.threshold == 0.8)

    # init_failed 팩토리
    e2 = ClassificationException.init_failed("model not loaded")
    check(r, "class.init_failed 타입", isinstance(e2, ClassificationException))

    # low_confidence 팩토리
    e3 = ClassificationException.low_confidence("/data/v.mp4", "GAME", 0.3, 0.8)
    check(r, "class.low_confidence 타입", isinstance(e3, ClassificationException))
    check(r, "class.low_confidence 메시지", "미달" in str(e3))

    # ambiguous_result 팩토리
    e4 = ClassificationException.ambiguous_result(
        "/data/v.mp4", {"GAME": 0.45, "TRAINING": 0.42},
    )
    check(r, "class.ambiguous_result 타입", isinstance(e4, ClassificationException))
    check(r, "class.ambiguous_result candidates",
          e4.details.get("candidates") == {"GAME": 0.45, "TRAINING": 0.42})

    # feature_extraction_failed 팩토리
    e5 = ClassificationException.feature_extraction_failed("/data/v.mp4", "empty frames")
    check(r, "class.feature_extraction_failed 타입", isinstance(e5, ClassificationException))

    # unsupported_format 팩토리
    e6 = ClassificationException.unsupported_format("/data/v.gif", "gif")
    check(r, "class.unsupported_format 타입", isinstance(e6, ClassificationException))

    # training_type_detection_failed 팩토리
    e7 = ClassificationException.training_type_detection_failed("/data/v.mp4", "no markers")
    check(r, "class.training_type_detection_failed 타입", isinstance(e7, ClassificationException))
    check(r, "class.training_type video_type", e7.video_type == "TRAINING")

    # game_type_detection_failed 팩토리
    e8 = ClassificationException.game_type_detection_failed("/data/v.mp4", "no court")
    check(r, "class.game_type_detection_failed 타입", isinstance(e8, ClassificationException))
    check(r, "class.game_type video_type", e8.video_type == "GAME")


def test_sampling_exception(r: TestResult) -> None:
    """SamplingException + 팩토리 메서드 테스트."""
    e = SamplingException(
        video_path="/data/v.mp4", sampling_strategy="adaptive",
        frame_index=50, sampling_rate=0.5,
    )
    check(r, "SamplingException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "SamplingException video_path", e.video_path == "/data/v.mp4")
    check(r, "SamplingException sampling_strategy", e.sampling_strategy == "adaptive")
    check(r, "SamplingException frame_index", e.frame_index == 50)
    check(r, "SamplingException sampling_rate", e.sampling_rate == 0.5)

    # init_failed 팩토리
    e2 = SamplingException.init_failed("config missing")
    check(r, "sampling.init_failed 타입", isinstance(e2, SamplingException))

    # invalid_config 팩토리
    e3 = SamplingException.invalid_config("fps", -1, "must be positive")
    check(r, "sampling.invalid_config 타입", isinstance(e3, SamplingException))
    check(r, "sampling.invalid_config config_name",
          e3.details.get("config_name") == "fps")

    # motion_analysis_failed 팩토리
    e4 = SamplingException.motion_analysis_failed("/data/v.mp4", 100, "no features")
    check(r, "sampling.motion_analysis_failed 타입", isinstance(e4, SamplingException))

    # optical_flow_failed 팩토리
    e5 = SamplingException.optical_flow_failed("/data/v.mp4", 50)
    check(r, "sampling.optical_flow_failed 타입", isinstance(e5, SamplingException))

    # invalid_sampling_rate 팩토리
    e6 = SamplingException.invalid_sampling_rate(0.01, 0.1, 1.0)
    check(r, "sampling.invalid_sampling_rate 타입", isinstance(e6, SamplingException))
    check(r, "sampling.invalid_sampling_rate min_rate", e6.details.get("min_rate") == 0.1)

    # insufficient_frames 팩토리
    e7 = SamplingException.insufficient_frames("/data/v.mp4", 5, 30)
    check(r, "sampling.insufficient_frames 타입", isinstance(e7, SamplingException))
    check(r, "sampling.insufficient_frames available",
          e7.details.get("available_frames") == 5)

    # timeout 팩토리
    e8 = SamplingException.timeout("/data/v.mp4", 65.0, 60.0)
    check(r, "sampling.timeout 타입", isinstance(e8, SamplingException))
    check(r, "sampling.timeout elapsed",
          e8.details.get("elapsed_seconds") == 65.0)


# =============================================================================
# [14] 카메라 예외
# =============================================================================
def test_camera_exception(r: TestResult) -> None:
    """CameraException 테스트."""
    e = CameraException(camera_id="cam-01")
    check(r, "CameraException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "CameraException camera_id", e.camera_id == "cam-01")
    check(r, "CameraException details.camera_id", e.details.get("camera_id") == "cam-01")


def test_camera_connection_exception(r: TestResult) -> None:
    """CameraConnectionException 테스트."""
    e = CameraConnectionException(camera_id="cam-02", device_uri="/dev/video0")
    check(r, "CameraConnectionException Retryable", isinstance(e, RetryableException))
    check(r, "CameraConnectionException camera_id", e.camera_id == "cam-02")
    check(r, "CameraConnectionException device_uri", e.device_uri == "/dev/video0")


def test_camera_timeout_exception(r: TestResult) -> None:
    """CameraTimeoutException 테스트."""
    e = CameraTimeoutException(camera_id="cam-03", timeout_seconds=5.0)
    check(r, "CameraTimeoutException Retryable", isinstance(e, RetryableException))
    check(r, "CameraTimeoutException camera_id", e.camera_id == "cam-03")
    check(r, "CameraTimeoutException timeout_seconds", e.timeout_seconds == 5.0)


# =============================================================================
# [15] 캘리브레이션 예외
# =============================================================================
def test_calibration_exception(r: TestResult) -> None:
    """CalibrationException 테스트."""
    e = CalibrationException(camera_id="cam-01", reprojection_error=2.5)
    check(r, "CalibrationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "CalibrationException camera_id", e.camera_id == "cam-01")
    check(r, "CalibrationException reprojection_error", e.reprojection_error == 2.5)
    check(r, "CalibrationException details.reprojection_error",
          e.details.get("reprojection_error") == 2.5)


def test_insufficient_data_exception(r: TestResult) -> None:
    """InsufficientDataException 테스트."""
    e = InsufficientDataException(required=20, available=5)
    check(r, "InsufficientDataException CalibrationException 하위",
          isinstance(e, CalibrationException))
    check(r, "InsufficientDataException required", e.required == 20)
    check(r, "InsufficientDataException available", e.available == 5)
    check(r, "InsufficientDataException details.required", e.details.get("required") == 20)
    check(r, "InsufficientDataException details.available", e.details.get("available") == 5)


# =============================================================================
# [16] 좌표 변환 예외
# =============================================================================
def test_transformation_exception(r: TestResult) -> None:
    """TransformationException 테스트."""
    e = TransformationException(source_system="pixel", target_system="world")
    check(r, "TransformationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "TransformationException source_system", e.source_system == "pixel")
    check(r, "TransformationException target_system", e.target_system == "world")


def test_calibration_required_exception(r: TestResult) -> None:
    """CalibrationRequiredException 테스트."""
    e = CalibrationRequiredException(camera_id="cam-01")
    check(r, "CalibrationRequiredException TransformationException 하위",
          isinstance(e, TransformationException))
    check(r, "CalibrationRequiredException camera_id", e.camera_id == "cam-01")


# =============================================================================
# [17] 설정 예외
# =============================================================================
def test_configuration_exception(r: TestResult) -> None:
    """ConfigurationException 테스트."""
    e = ConfigurationException(config_path="/etc/courtview/config.yaml")
    check(r, "ConfigurationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "ConfigurationException config_path", e.config_path == "/etc/courtview/config.yaml")
    check(r, "ConfigurationException details.config_path",
          e.details.get("config_path") == "/etc/courtview/config.yaml")


def test_infra_validation_exception(r: TestResult) -> None:
    """ValidationException (infrastructure) 테스트."""
    e = ValidationException(field="resolution", value="invalid")
    check(r, "Infra ValidationException InfrastructureException 하위",
          isinstance(e, InfrastructureException))
    check(r, "Infra ValidationException field", e.field == "resolution")
    check(r, "Infra ValidationException value", e.value == "invalid")
    check(r, "Infra ValidationException details.field",
          e.details.get("field") == "resolution")
    check(r, "Infra ValidationException details.value",
          e.details.get("value") == "invalid")


# =============================================================================
# [18] 상속 계층 구조 검증
# =============================================================================
def test_inheritance_hierarchy(r: TestResult) -> None:
    """58개 클래스 상속 계층 구조 검증."""
    # Retryable 계열 (17개)
    retryable_classes = [
        TimeoutException, DatabaseConnectionException, DatabaseTimeoutException,
        ConnectionPoolException, CacheConnectionException, QueueConnectionException,
        TaskEnqueueException, TaskTimeoutException, AlertDeliveryException,
        S3UploadException, S3DownloadException, StreamException,
        ConnectionException, ExternalServiceException, WebhookException,
        CameraConnectionException, CameraTimeoutException,
    ]
    for cls in retryable_classes:
        check(r, f"{cls.__name__} → RetryableException",
              issubclass(cls, RetryableException))

    # NonRetryable 계열 (10개)
    nonretryable_classes = [
        CircuitBreakerOpenException, DatabaseIntegrityException, TransactionException,
        RecordNotFoundException, CacheKeyNotFoundException, CacheSerializationException,
        AlertConfigurationException, S3ObjectNotFoundException, S3PermissionException,
        FilePermissionException,
    ]
    for cls in nonretryable_classes:
        check(r, f"{cls.__name__} → NonRetryableException",
              issubclass(cls, NonRetryableException))

    # Critical 계열 (1개)
    check(r, "DiskSpaceException → CriticalException",
          issubclass(DiskSpaceException, CriticalException))

    # InfrastructureException 하위 (12개)
    infra_classes = [
        DecodingException, FrameExtractionException, EndOfStreamException,
        NormalizationException, ResolutionException, ClassificationException,
        SamplingException, CameraException, CalibrationException,
        TransformationException, ConfigurationException, ValidationException,
    ]
    for cls in infra_classes:
        check(r, f"{cls.__name__} → InfrastructureException",
              issubclass(cls, InfrastructureException))

    # 특수 상속
    check(r, "CodecException → DecodingException",
          issubclass(CodecException, DecodingException))
    check(r, "CorruptedFileException → DecodingException",
          issubclass(CorruptedFileException, DecodingException))
    check(r, "RedisException → CacheException",
          issubclass(RedisException, CacheException))
    check(r, "S3Exception → StorageException",
          issubclass(S3Exception, StorageException))
    check(r, "MetadataExtractionException → StorageException",
          issubclass(MetadataExtractionException, StorageException))
    check(r, "LocalStorageException → StorageException",
          issubclass(LocalStorageException, StorageException))
    check(r, "InsufficientDataException → CalibrationException",
          issubclass(InsufficientDataException, CalibrationException))
    check(r, "CalibrationRequiredException → TransformationException",
          issubclass(CalibrationRequiredException, TransformationException))


# =============================================================================
# [19] 직렬화 (to_dict, to_response_dict) 테스트
# =============================================================================
def test_serialization(r: TestResult) -> None:
    """to_dict / to_response_dict 직렬화 테스트."""
    # Retryable 예외 직렬화
    e1 = TimeoutException(timeout_seconds=30.0, operation="analyze")
    d1 = e1.to_dict()
    check(r, "to_dict error 키 존재", "error" in d1)
    check(r, "to_dict error.code 존재", "code" in d1.get("error", {}))
    check(r, "to_dict error.name 존재", "name" in d1.get("error", {}))
    check(r, "to_dict error.message 존재", "message" in d1.get("error", {}))
    check(r, "to_dict timestamp 존재", "timestamp" in d1)
    check(r, "to_dict retry 키 존재 (Retryable)", "retry" in d1)

    rd1 = e1.to_response_dict()
    check(r, "to_response_dict success False", rd1.get("success") is False)
    check(r, "to_response_dict error 키 존재", "error" in rd1)

    # NonRetryable 예외 직렬화
    e2 = CircuitBreakerOpenException(circuit_name="db")
    d2 = e2.to_dict()
    check(r, "NonRetryable to_dict retryable False", d2.get("retryable") is False)

    # Critical 예외 직렬화
    e3 = DiskSpaceException(required_bytes=1024, available_bytes=100)
    d3 = e3.to_dict()
    check(r, "Critical to_dict critical 키 존재", "critical" in d3)
    check(r, "Critical to_dict details.storage_type",
          d3.get("details", {}).get("storage_type") == "local")

    # InfrastructureException 직렬화
    e4 = DecodingException(video_path="/v.mp4", codec="h264")
    d4 = e4.to_dict()
    check(r, "InfraException to_dict details.video_path",
          d4.get("details", {}).get("video_path") == "/v.mp4")


# =============================================================================
# [20] raise/catch 검증
# =============================================================================
def test_raise_catch(r: TestResult) -> None:
    """예외 raise/catch 검증."""
    # Retryable catch 체인
    try:
        raise TimeoutException(timeout_seconds=10.0)
    except RetryableException as e:
        check(r, "TimeoutException RetryableException catch", True)
    except Exception:
        check(r, "TimeoutException RetryableException catch", False, "잘못된 catch")

    # NonRetryable catch 체인
    try:
        raise CircuitBreakerOpenException()
    except NonRetryableException as e:
        check(r, "CircuitBreakerOpen NonRetryableException catch", True)
    except Exception:
        check(r, "CircuitBreakerOpen NonRetryableException catch", False, "잘못된 catch")

    # Critical catch 체인
    try:
        raise DiskSpaceException()
    except CriticalException as e:
        check(r, "DiskSpace CriticalException catch", True)
    except Exception:
        check(r, "DiskSpace CriticalException catch", False, "잘못된 catch")

    # InfrastructureException catch
    try:
        raise DecodingException()
    except InfrastructureException as e:
        check(r, "DecodingException InfrastructureException catch", True)
    except Exception:
        check(r, "DecodingException InfrastructureException catch", False, "잘못된 catch")

    # CourtViewException 최상위 catch
    try:
        raise S3UploadException()
    except CourtViewException as e:
        check(r, "S3UploadException CourtViewException catch", True)
    except Exception:
        check(r, "S3UploadException CourtViewException catch", False, "잘못된 catch")

    # cause 체인
    original = ValueError("원본 오류")
    try:
        raise DatabaseException(cause=original)
    except CourtViewException as e:
        check(r, "cause 체인 전달", e.__cause__ is original)


# =============================================================================
# [21] __all__ 검증
# =============================================================================
def test_all_exports(r: TestResult) -> None:
    """__all__ 완전성 검증."""
    import inspect

    all_list = mod.__all__
    check(r, "__all__ 개수 58", len(all_list) == 58)

    # __all__ 내 모든 이름이 실제 클래스인지 확인
    for name in all_list:
        obj = getattr(mod, name, None)
        check(r, f"__all__ '{name}' 존재", obj is not None)
        if obj is not None:
            check(r, f"__all__ '{name}' Exception 하위",
                  inspect.isclass(obj) and issubclass(obj, Exception))

    # 실제 정의된 클래스가 __all__에 포함되는지 (base_exception에서 import된 것 제외)
    defined_classes = [
        name for name, obj in inspect.getmembers(mod)
        if inspect.isclass(obj) and issubclass(obj, Exception)
        and obj.__module__ == mod.__name__
    ]
    for name in defined_classes:
        check(r, f"정의 클래스 '{name}' __all__에 포함", name in all_list)


# =============================================================================
# [22] 버전 검증
# =============================================================================
def test_version(r: TestResult) -> None:
    """모듈 버전 검증."""
    check(r, "모듈 버전 존재", hasattr(mod, "__version__"))
    check(r, "모듈 버전 형식", mod.__version__ == "1.0.0")


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    r = TestResult()

    print("\n[1] 인프라 기본 예외")
    test_infrastructure_exception(r)
    test_timeout_exception(r)
    test_circuit_breaker_exception(r)

    print("\n[2] 데이터베이스 예외")
    test_database_exception(r)
    test_database_exception_sanitize(r)
    test_database_connection_exception(r)
    test_database_timeout_exception(r)
    test_database_integrity_exception(r)
    test_transaction_exception(r)
    test_record_not_found_exception(r)
    test_connection_pool_exception(r)

    print("\n[3] 캐시 예외")
    test_cache_exception(r)
    test_cache_key_masking(r)
    test_cache_connection_exception(r)
    test_cache_key_not_found_exception(r)
    test_cache_serialization_exception(r)
    test_redis_exception(r)

    print("\n[4] 메시지 큐 예외")
    test_queue_exception(r)
    test_queue_connection_exception(r)
    test_task_enqueue_exception(r)
    test_task_execution_exception(r)
    test_task_timeout_exception(r)

    print("\n[5] 알림/워커/이벤트버스/정리 예외")
    test_alert_delivery_exception(r)
    test_alert_configuration_exception(r)
    test_worker_exception(r)
    test_notification_exception(r)
    test_cleanup_exception(r)
    test_event_bus_exception(r)

    print("\n[6] 스토리지 예외")
    test_storage_exception(r)
    test_s3_exception(r)
    test_s3_upload_exception(r)
    test_s3_download_exception(r)
    test_s3_object_not_found(r)
    test_s3_permission_exception(r)
    test_metadata_extraction_exception(r)
    test_local_storage_exception(r)
    test_disk_space_exception(r)
    test_file_permission_exception(r)

    print("\n[7] 스트림 예외")
    test_stream_exception(r)
    test_stream_url_sanitization(r)
    test_stream_factory_methods(r)

    print("\n[8] 연결 예외")
    test_connection_exception(r)

    print("\n[9] 외부 서비스 예외")
    test_external_service_exception(r)
    test_webhook_exception(r)

    print("\n[10] 디코딩 예외")
    test_decoding_exception(r)
    test_codec_exception(r)
    test_corrupted_file_exception(r)

    print("\n[11] 프레임 추출/스트림 종료 예외")
    test_frame_extraction_exception(r)
    test_end_of_stream_exception(r)

    print("\n[12] 정규화/해상도 예외")
    test_normalization_exception(r)
    test_resolution_exception(r)

    print("\n[13] 분류/샘플링 예외")
    test_classification_exception(r)
    test_sampling_exception(r)

    print("\n[14] 카메라 예외")
    test_camera_exception(r)
    test_camera_connection_exception(r)
    test_camera_timeout_exception(r)

    print("\n[15] 캘리브레이션 예외")
    test_calibration_exception(r)
    test_insufficient_data_exception(r)

    print("\n[16] 좌표 변환 예외")
    test_transformation_exception(r)
    test_calibration_required_exception(r)

    print("\n[17] 설정 예외")
    test_configuration_exception(r)
    test_infra_validation_exception(r)

    print("\n[18] 상속 계층 구조 검증")
    test_inheritance_hierarchy(r)

    print("\n[19] 직렬화 검증")
    test_serialization(r)

    print("\n[20] raise/catch 검증")
    test_raise_catch(r)

    print("\n[21] __all__ 검증")
    test_all_exports(r)

    print("\n[22] 버전 검증")
    test_version(r)

    r.summary()

    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
