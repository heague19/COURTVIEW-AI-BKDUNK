# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/performance
파일: test_infrastructure_exceptions_perf.py
설명: infrastructure_exceptions.py 성능 테스트
      (58개 클래스 생성/직렬화/팩토리/보안 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
from shared.exceptions.infrastructure_exceptions import (
    InfrastructureException, TimeoutException, CircuitBreakerOpenException,
    DatabaseException, DatabaseConnectionException, DatabaseTimeoutException,
    DatabaseIntegrityException, TransactionException, RecordNotFoundException,
    ConnectionPoolException,
    CacheException, CacheConnectionException, CacheKeyNotFoundException,
    CacheSerializationException, RedisException,
    QueueException, QueueConnectionException, TaskEnqueueException,
    TaskExecutionException, TaskTimeoutException, EventBusException,
    AlertDeliveryException, AlertConfigurationException,
    WorkerException, NotificationException, CleanupException,
    StorageException, S3Exception, S3UploadException, S3DownloadException,
    S3ObjectNotFoundException, S3PermissionException,
    MetadataExtractionException, LocalStorageException,
    DiskSpaceException, FilePermissionException,
    StreamException, ConnectionException,
    ExternalServiceException, WebhookException,
    DecodingException, CodecException, CorruptedFileException,
    FrameExtractionException, EndOfStreamException,
    NormalizationException, ResolutionException,
    ClassificationException, SamplingException,
    CameraException, CameraConnectionException, CameraTimeoutException,
    CalibrationException, InsufficientDataException,
    TransformationException, CalibrationRequiredException,
    ConfigurationException, ValidationException,
)


# =============================================================================
# 성능 테스트 하네스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/반복)."""
    gc.disable()
    try:
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


def bench(r: PerfResult, name: str, func, limit_us: float, iters: int = 20000) -> None:
    """벤치마크 헬퍼."""
    elapsed = measure(func, iters)
    if elapsed < limit_us:
        r.ok(name, elapsed, limit_us)
    else:
        r.fail(name, elapsed, limit_us)


# =============================================================================
# [1] 인프라 기본 예외 생성 성능
# =============================================================================
def test_infra_base_creation(r: PerfResult) -> None:
    """인프라 기본 예외 생성."""
    limit = 60.0

    bench(r, "InfrastructureException()", lambda: InfrastructureException(), limit)
    bench(r, "TimeoutException()", lambda: TimeoutException(), limit)
    bench(r, "CircuitBreakerOpenException()", lambda: CircuitBreakerOpenException(), limit)


# =============================================================================
# [2] 데이터베이스 예외 생성 성능
# =============================================================================
def test_database_creation(r: PerfResult) -> None:
    """데이터베이스 예외 생성."""
    limit = 70.0

    bench(r, "DatabaseException()", lambda: DatabaseException(), limit)
    bench(r, "DatabaseConnectionException(host,port)",
          lambda: DatabaseConnectionException(host="db.local", port=5432), limit)
    bench(r, "DatabaseTimeoutException(timeout)",
          lambda: DatabaseTimeoutException(timeout_seconds=30.0), limit)
    bench(r, "DatabaseIntegrityException(constraint)",
          lambda: DatabaseIntegrityException(constraint_name="uq"), limit)
    bench(r, "TransactionException()",
          lambda: TransactionException(transaction_id="tx-1"), limit)
    bench(r, "RecordNotFoundException(search_criteria)",
          lambda: RecordNotFoundException(
              table="users", search_criteria={"email": "a@b.com"}
          ), 100.0)
    bench(r, "ConnectionPoolException(pool)",
          lambda: ConnectionPoolException(pool_name="db"), limit)


# =============================================================================
# [3] 캐시 예외 생성 성능
# =============================================================================
def test_cache_creation(r: PerfResult) -> None:
    """캐시 예외 생성."""
    limit = 70.0

    bench(r, "CacheException(key,op)",
          lambda: CacheException(cache_key="user:123", operation="GET"), limit)
    bench(r, "CacheConnectionException(host,port)",
          lambda: CacheConnectionException(host="redis", port=6379), limit)
    bench(r, "CacheKeyNotFoundException(key)",
          lambda: CacheKeyNotFoundException(cache_key="k"), limit)
    bench(r, "CacheSerializationException()",
          lambda: CacheSerializationException(), limit)
    bench(r, "RedisException(cmd,node)",
          lambda: RedisException(redis_command="SET", cluster_node="n1"), limit)


# =============================================================================
# [4] 큐/워커/알림 예외 생성 성능
# =============================================================================
def test_queue_worker_creation(r: PerfResult) -> None:
    """큐/워커/알림 예외 생성."""
    limit = 70.0

    bench(r, "QueueException()", lambda: QueueException(), limit)
    bench(r, "QueueConnectionException(broker)",
          lambda: QueueConnectionException(broker_url="amqp://u:p@host"), 120.0)
    bench(r, "TaskEnqueueException()", lambda: TaskEnqueueException(), limit)
    bench(r, "TaskExecutionException()", lambda: TaskExecutionException(), limit)
    bench(r, "TaskTimeoutException()", lambda: TaskTimeoutException(), limit)
    bench(r, "WorkerException()", lambda: WorkerException(), limit)
    bench(r, "NotificationException()", lambda: NotificationException(), limit)
    bench(r, "AlertDeliveryException()",
          lambda: AlertDeliveryException(channel="slack"), limit)
    bench(r, "AlertConfigurationException()",
          lambda: AlertConfigurationException(channel="email"), limit)
    bench(r, "CleanupException()", lambda: CleanupException(), limit)
    bench(r, "EventBusException()", lambda: EventBusException(), limit)


# =============================================================================
# [5] 스토리지 예외 생성 성능
# =============================================================================
def test_storage_creation(r: PerfResult) -> None:
    """스토리지 예외 생성."""
    limit = 70.0

    bench(r, "StorageException()", lambda: StorageException(), limit)
    bench(r, "S3Exception(bucket,key)",
          lambda: S3Exception(bucket="b", key="k"), limit)
    bench(r, "S3UploadException(bucket,key,size)",
          lambda: S3UploadException(bucket="b", key="k", file_size=1048576), limit)
    bench(r, "S3DownloadException()", lambda: S3DownloadException(), limit)
    bench(r, "S3ObjectNotFoundException()", lambda: S3ObjectNotFoundException(), limit)
    bench(r, "S3PermissionException()", lambda: S3PermissionException(), limit)
    bench(r, "MetadataExtractionException()",
          lambda: MetadataExtractionException(file_path="/v.mp4"), limit)
    bench(r, "LocalStorageException()", lambda: LocalStorageException(), limit)
    bench(r, "DiskSpaceException(bytes)",
          lambda: DiskSpaceException(required_bytes=1024, available_bytes=100), limit)
    bench(r, "FilePermissionException()", lambda: FilePermissionException(), limit)


# =============================================================================
# [6] 스트림/연결/외부 예외 생성 성능
# =============================================================================
def test_stream_connection_creation(r: PerfResult) -> None:
    """스트림/연결/외부 예외 생성."""
    limit = 100.0  # URL 파싱 포함

    bench(r, "StreamException(url,type)",
          lambda: StreamException(stream_url="rtsp://cam/s", stream_type="RTSP"), limit)
    bench(r, "ConnectionException(host,port)",
          lambda: ConnectionException(host="api.local", port=8080), 70.0)
    bench(r, "ExternalServiceException(svc)",
          lambda: ExternalServiceException(service_name="backend"), 70.0)
    bench(r, "WebhookException(url)",
          lambda: WebhookException(webhook_url="https://hook.com/x?t=1"), 70.0)


# =============================================================================
# [7] 비디오 처리 예외 생성 성능
# =============================================================================
def test_video_processing_creation(r: PerfResult) -> None:
    """비디오 처리 예외 생성."""
    limit = 70.0

    bench(r, "DecodingException(path,frame,codec)",
          lambda: DecodingException(video_path="/v.mp4", frame_number=1, codec="h264"), limit)
    bench(r, "CodecException(name,required)",
          lambda: CodecException(codec_name="hevc", required_codec="h264"), limit)
    bench(r, "CorruptedFileException(path,type)",
          lambda: CorruptedFileException(file_path="/v.mp4", corruption_type="header"), limit)
    bench(r, "FrameExtractionException(path,idx)",
          lambda: FrameExtractionException(video_path="/v.mp4", frame_index=100), limit)
    bench(r, "EndOfStreamException(path,last,total)",
          lambda: EndOfStreamException(video_path="/v.mp4", last_frame_index=999, total_frames=1000), limit)
    bench(r, "NormalizationException(path,res)",
          lambda: NormalizationException(video_path="/v.mp4", source_resolution=(3840, 2160)), limit)
    bench(r, "ResolutionException(w,h)",
          lambda: ResolutionException(width=640, height=480), limit)
    bench(r, "ClassificationException(path,type)",
          lambda: ClassificationException(video_path="/v.mp4", video_type="GAME"), limit)
    bench(r, "SamplingException(path,strategy)",
          lambda: SamplingException(video_path="/v.mp4", sampling_strategy="adaptive"), limit)


# =============================================================================
# [8] 카메라/캘리브레이션/변환/설정 예외 생성 성능
# =============================================================================
def test_camera_config_creation(r: PerfResult) -> None:
    """카메라/캘리브레이션/변환/설정 예외 생성."""
    limit = 70.0

    bench(r, "CameraException(id)", lambda: CameraException(camera_id="cam-01"), limit)
    bench(r, "CameraConnectionException(id,uri)",
          lambda: CameraConnectionException(camera_id="cam-01", device_uri="/dev/v0"), limit)
    bench(r, "CameraTimeoutException(id,sec)",
          lambda: CameraTimeoutException(camera_id="cam-01", timeout_seconds=5.0), limit)
    bench(r, "CalibrationException(id,err)",
          lambda: CalibrationException(camera_id="cam-01", reprojection_error=2.5), limit)
    bench(r, "InsufficientDataException(req,avail)",
          lambda: InsufficientDataException(required=20, available=5), limit)
    bench(r, "TransformationException(src,tgt)",
          lambda: TransformationException(source_system="pixel", target_system="world"), limit)
    bench(r, "CalibrationRequiredException(id)",
          lambda: CalibrationRequiredException(camera_id="cam-01"), limit)
    bench(r, "ConfigurationException(path)",
          lambda: ConfigurationException(config_path="/etc/cfg.yaml"), limit)
    bench(r, "ValidationException(field,val)",
          lambda: ValidationException(field="res", value="bad"), limit)


# =============================================================================
# [9] 팩토리 메서드 성능
# =============================================================================
def test_factory_methods(r: PerfResult) -> None:
    """주요 팩토리 메서드 성능."""
    limit = 100.0

    # ConnectionPool
    bench(r, "ConnectionPool.pool_exhausted()",
          lambda: ConnectionPoolException.pool_exhausted("pool", 10, 10), limit)
    bench(r, "ConnectionPool.acquisition_timeout()",
          lambda: ConnectionPoolException.acquisition_timeout("pool", 5.0), limit)

    # EventBus
    bench(r, "EventBus.publish_failed()",
          lambda: EventBusException.publish_failed("ev.type"), limit)
    bench(r, "EventBus.handler_failed()",
          lambda: EventBusException.handler_failed("ev.type", "handler"), limit)

    # Metadata
    bench(r, "Metadata.ffprobe_failed()",
          lambda: MetadataExtractionException.ffprobe_failed("/v.mp4"), limit)

    # Stream (9개)
    bench(r, "Stream.connection_failed()",
          lambda: StreamException.connection_failed("rtsp://cam/s"), 120.0)
    bench(r, "Stream.disconnected()",
          lambda: StreamException.disconnected("rtsp://cam/s"), 120.0)
    bench(r, "Stream.timeout()",
          lambda: StreamException.timeout("rtsp://cam/s", 30.0), 120.0)
    bench(r, "Stream.buffer_overflow()",
          lambda: StreamException.buffer_overflow("rtsp://cam/s", 1024, 512), 120.0)

    # Connection
    bench(r, "Connection.connection_refused()",
          lambda: ConnectionException.connection_refused("host"), limit)
    bench(r, "Connection.connection_timeout()",
          lambda: ConnectionException.connection_timeout("host", 10.0), limit)

    # Decoding
    bench(r, "Decoding.init_failed()",
          lambda: DecodingException.init_failed("/v.mp4", "err"), limit)
    bench(r, "Codec.not_found()",
          lambda: CodecException.not_found("av1"), limit)
    bench(r, "Corrupted.header_corrupted()",
          lambda: CorruptedFileException.header_corrupted("/v.mp4"), limit)

    # FrameExtraction
    bench(r, "Frame.extraction_failed()",
          lambda: FrameExtractionException.extraction_failed("/v.mp4", 100, "err"), limit)

    # EndOfStream
    bench(r, "EOS.video_end()",
          lambda: EndOfStreamException.video_end("/v.mp4", 999, 1000), limit)

    # Normalization
    bench(r, "Norm.resolution_failed()",
          lambda: NormalizationException.resolution_failed(
              "/v.mp4", (3840, 2160), (1920, 1080), "err"), limit)

    # Resolution
    bench(r, "Resolution.below_minimum()",
          lambda: ResolutionException.below_minimum(320, 240, 720, 480), limit)

    # Classification
    bench(r, "Classification.low_confidence()",
          lambda: ClassificationException.low_confidence("/v.mp4", "GAME", 0.3, 0.8), limit)

    # Sampling
    bench(r, "Sampling.insufficient_frames()",
          lambda: SamplingException.insufficient_frames("/v.mp4", 5, 30), limit)


# =============================================================================
# [10] 보안 기능 성능
# =============================================================================
def test_security_features(r: PerfResult) -> None:
    """보안 기능 성능."""
    limit = 120.0

    # DB 쿼리 산출
    bench(r, "DB 쿼리 산출 (password+token)",
          lambda: DatabaseException(
              query="SELECT * FROM t WHERE password='s' AND token='t'"
          ), limit)

    # 캐시 키 마스킹
    bench(r, "캐시 민감키 마스킹 (token:)",
          lambda: CacheException(cache_key="token:abc123"), 80.0)

    # RecordNotFound 민감키 필터링
    bench(r, "RecordNotFound 민감키 필터링",
          lambda: RecordNotFoundException(
              search_criteria={"email": "a", "password": "s", "token": "t"}
          ), limit)

    # StreamURL 산출
    bench(r, "StreamURL 인증정보 제거",
          lambda: StreamException(stream_url="rtsp://u:p@host/s"), 150.0)

    # QueueConnection URL 마스킹
    bench(r, "QueueConn URL 마스킹",
          lambda: QueueConnectionException(broker_url="amqp://u:p@host"), 150.0)

    # Webhook URL 쿼리 제거
    bench(r, "Webhook URL 쿼리 제거",
          lambda: WebhookException(webhook_url="https://hook.com/x?t=1"), 80.0)


# =============================================================================
# [11] 직렬화 성능
# =============================================================================
def test_serialization(r: PerfResult) -> None:
    """to_dict / to_response_dict 성능."""
    limit = 80.0

    e_retry = TimeoutException(timeout_seconds=30.0)
    e_nonretry = CircuitBreakerOpenException(circuit_name="db")
    e_critical = DiskSpaceException(required_bytes=1024)
    e_infra = DecodingException(video_path="/v.mp4")

    bench(r, "Retryable.to_dict()", lambda: e_retry.to_dict(), limit)
    bench(r, "Retryable.to_response_dict()", lambda: e_retry.to_response_dict(), limit)
    bench(r, "NonRetryable.to_dict()", lambda: e_nonretry.to_dict(), limit)
    bench(r, "Critical.to_dict()", lambda: e_critical.to_dict(), limit)
    bench(r, "InfraException.to_dict()", lambda: e_infra.to_dict(), limit)


# =============================================================================
# [12] 대량 생성 성능 (58개 클래스)
# =============================================================================
def test_bulk_creation(r: PerfResult) -> None:
    """58개 클래스 대량 생성."""
    all_classes = [
        InfrastructureException, TimeoutException, CircuitBreakerOpenException,
        DatabaseException, DatabaseConnectionException, DatabaseTimeoutException,
        DatabaseIntegrityException, TransactionException, RecordNotFoundException,
        ConnectionPoolException,
        CacheException, CacheConnectionException, CacheKeyNotFoundException,
        CacheSerializationException, RedisException,
        QueueException, QueueConnectionException, TaskEnqueueException,
        TaskExecutionException, TaskTimeoutException, EventBusException,
        AlertDeliveryException, AlertConfigurationException,
        WorkerException, NotificationException, CleanupException,
        StorageException, S3Exception, S3UploadException, S3DownloadException,
        S3ObjectNotFoundException, S3PermissionException,
        MetadataExtractionException, LocalStorageException,
        DiskSpaceException, FilePermissionException,
        StreamException, ConnectionException,
        ExternalServiceException, WebhookException,
        DecodingException, CodecException, CorruptedFileException,
        FrameExtractionException, EndOfStreamException,
        NormalizationException, ResolutionException,
        ClassificationException, SamplingException,
        CameraException, CameraConnectionException, CameraTimeoutException,
        CalibrationException, InsufficientDataException,
        TransformationException, CalibrationRequiredException,
        ConfigurationException, ValidationException,
    ]

    def create_all():
        for cls in all_classes:
            cls()

    elapsed = measure(create_all, 5000)
    limit = 4000.0  # 58개 클래스 총합 (70us * 58 ≈ 4000us)
    if elapsed < limit:
        r.ok(f"58개 클래스 일괄 생성", elapsed, limit)
    else:
        r.fail(f"58개 클래스 일괄 생성", elapsed, limit)


# =============================================================================
# [13] raise/catch 성능
# =============================================================================
def test_raise_catch(r: PerfResult) -> None:
    """raise/catch 성능."""
    limit = 80.0

    def raise_catch_timeout():
        try:
            raise TimeoutException()
        except Exception:
            pass

    def raise_catch_circuit():
        try:
            raise CircuitBreakerOpenException()
        except Exception:
            pass

    def raise_catch_disk():
        try:
            raise DiskSpaceException()
        except Exception:
            pass

    bench(r, "raise/catch TimeoutException", raise_catch_timeout, limit)
    bench(r, "raise/catch CircuitBreakerOpen", raise_catch_circuit, limit)
    bench(r, "raise/catch DiskSpaceException", raise_catch_disk, limit)


# =============================================================================
# [14] __str__ 성능
# =============================================================================
def test_str_repr(r: PerfResult) -> None:
    """__str__ 성능."""
    limit = 20.0

    e1 = TimeoutException(timeout_seconds=30.0)
    e2 = DatabaseException(operation="SELECT", table="users", query="SELECT 1")
    e3 = DiskSpaceException(required_bytes=1024)

    bench(r, "TimeoutException.__str__()", lambda: str(e1), limit)
    bench(r, "DatabaseException.__str__()", lambda: str(e2), limit)
    bench(r, "DiskSpaceException.__str__()", lambda: str(e3), limit)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    r = PerfResult()

    print("\n[1] 인프라 기본 예외 생성")
    test_infra_base_creation(r)

    print("\n[2] 데이터베이스 예외 생성")
    test_database_creation(r)

    print("\n[3] 캐시 예외 생성")
    test_cache_creation(r)

    print("\n[4] 큐/워커/알림 예외 생성")
    test_queue_worker_creation(r)

    print("\n[5] 스토리지 예외 생성")
    test_storage_creation(r)

    print("\n[6] 스트림/연결/외부 예외 생성")
    test_stream_connection_creation(r)

    print("\n[7] 비디오 처리 예외 생성")
    test_video_processing_creation(r)

    print("\n[8] 카메라/캘리브레이션/변환/설정 예외 생성")
    test_camera_config_creation(r)

    print("\n[9] 팩토리 메서드")
    test_factory_methods(r)

    print("\n[10] 보안 기능")
    test_security_features(r)

    print("\n[11] 직렬화")
    test_serialization(r)

    print("\n[12] 대량 생성 (58개 클래스)")
    test_bulk_creation(r)

    print("\n[13] raise/catch")
    test_raise_catch(r)

    print("\n[14] __str__")
    test_str_repr(r)

    r.summary()

    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
