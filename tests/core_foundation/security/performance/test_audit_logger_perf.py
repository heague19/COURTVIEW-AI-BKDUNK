# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/security/performance
파일: test_audit_logger_perf.py
설명: 감사 로거 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1] AuditEventType Enum 연산 성능 (3개)
    [2] AuditSeverity Enum 연산 성능 (3개)
    [3] AuditEvent 생성 성능 (3개)
    [4] AuditLogEntry 생성/해시 성능 (4개)
    [5] MemoryAuditStorage 처리량 (4개)
    [6] LoginFailureTracker 성능 (3개)
    [7] AuditLogger 초기화 성능 (2개)
    [8] AuditLogger.log 성능 (3개)
    [9] 직렬화 성능 (to_dict / from_dict) (3개)
    [10] 멀티스레드 동시 접근 (4개)
    [11] 메모리 사용량 (3개)
    [12] 체인 해시 무결성 검증 성능 (3개)
"""

import io
import sys
import time
import threading
import tracemalloc
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.security.audit_logger import (
    # Enum
    AuditEventType,
    AuditSeverity,
    # 상수
    EVENT_DEFAULT_SEVERITY,
    HASH_ALGORITHM,
    INITIAL_CHAIN_HASH,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_FLUSH_INTERVAL,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_LOGIN_FAILURE_THRESHOLD,
    DEFAULT_THRESHOLD_WINDOW_MINUTES,
    # 데이터클래스
    AuditEvent,
    AuditLogEntry,
    # 저장소
    MemoryAuditStorage,
    # 추적기
    LoginFailureTracker,
    # 메인
    AuditLogger,
    # 전역 함수
    get_audit_logger,
    set_audit_logger,
    _audit_logger,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" | {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n성능 메트릭:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼
# =============================================================================
def _make_audit_logger(**kwargs) -> AuditLogger:
    """테스트용 AuditLogger 생성 (파일 저장소 비활성, 샘플링 비활성)."""
    mock_loader = MagicMock()
    config = kwargs.get("config", {})
    # 기본: 파일 저장소 비활성, 메모리 저장소 사용, 샘플링 비활성
    config.setdefault("storage", {"file": {"enabled": False}})
    config.setdefault("sampling_enabled", False)
    mock_loader.get.return_value = config
    return AuditLogger(
        config_loader=mock_loader,
        metrics_collector=kwargs.get("metrics_collector"),
    )


def _make_event(**kwargs) -> AuditEvent:
    """테스트용 AuditEvent 생성."""
    return AuditEvent(
        event_type=kwargs.get("event_type", AuditEventType.LOGIN_SUCCESS),
        actor=kwargs.get("actor", "test_user"),
        action=kwargs.get("action", "login"),
        resource=kwargs.get("resource", "/api/auth"),
        result=kwargs.get("result", "success"),
        severity=kwargs.get("severity", AuditSeverity.INFO),
    )


def _reset_global() -> None:
    """전역 인스턴스 초기화."""
    import core_foundation.security.audit_logger as mod
    with mod._audit_logger_lock:
        mod._audit_logger = None


# =============================================================================
# [1] AuditEventType Enum 연산 성능
# =============================================================================
def test_event_type_perf(result: PerfResult) -> None:
    """AuditEventType Enum 연산 성능."""
    print("\n[1] AuditEventType Enum 연산 성능")

    # 1-1: 멤버 접근
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditEventType.LOGIN_SUCCESS
            _ = AuditEventType.ACCESS_DENIED
            _ = AuditEventType.DATA_READ
            _ = AuditEventType.INTRUSION_DETECTED
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 4) * 1000  # μs
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-1: 멤버 접근 (400K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-1: 멤버 접근", str(e))

    # 1-2: category / action 속성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditEventType.LOGIN_SUCCESS.category
            _ = AuditEventType.LOGIN_SUCCESS.action
            _ = AuditEventType.DATA_READ.category
            _ = AuditEventType.DATA_READ.action
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 4) * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-2: category/action (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-2: category/action", str(e))

    # 1-3: from_string 탐색
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditEventType.from_string("authentication.login_success")
            _ = AuditEventType.from_string("security.intrusion_detected")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-3: from_string (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-3: from_string", str(e))


# =============================================================================
# [2] AuditSeverity Enum 연산 성능
# =============================================================================
def test_severity_perf(result: PerfResult) -> None:
    """AuditSeverity Enum 연산 성능."""
    print("\n[2] AuditSeverity Enum 연산 성능")

    # 2-1: 멤버 접근 + 속성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditSeverity.INFO.value
            _ = AuditSeverity.INFO.retain_days
            _ = AuditSeverity.INFO.name_str
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 3) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-1: 속성 접근 (300K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-1: 속성 접근", str(e))

    # 2-2: 비교 연산자
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditSeverity.CRITICAL > AuditSeverity.INFO
            _ = AuditSeverity.DEBUG < AuditSeverity.WARNING
            _ = AuditSeverity.ERROR >= AuditSeverity.ERROR
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 3) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-2: 비교 연산자 (300K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-2: 비교 연산자", str(e))

    # 2-3: from_string 탐색
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditSeverity.from_string("info")
            _ = AuditSeverity.from_string("critical")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-3: from_string (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-3: from_string", str(e))


# =============================================================================
# [3] AuditEvent 생성 성능
# =============================================================================
def test_event_creation_perf(result: PerfResult) -> None:
    """AuditEvent 생성 성능."""
    print("\n[3] AuditEvent 생성 성능")

    # 3-1: 기본 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditEvent(
                event_type=AuditEventType.LOGIN_SUCCESS,
                actor="user@test.com",
                action="login",
                resource="/api/auth",
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-1: 기본 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-1: 기본 생성", str(e))

    # 3-2: 전체 필드 생성
    try:
        iterations = 5_000
        now = datetime.now(timezone.utc)
        start = time.perf_counter()
        for i in range(iterations):
            _ = AuditEvent(
                event_type=AuditEventType.DATA_READ,
                actor=f"user_{i % 100}",
                action="read",
                resource=f"/api/data/{i}",
                result="success",
                severity=AuditSeverity.INFO,
                timestamp=now,
                request_id=f"req_{i}",
                session_id=f"sess_{i}",
                ip_address="192.168.1.1",
                user_agent="COURTVIEW/1.0",
                details={"count": i},
                metadata={"env": "test"},
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-2: 전체 필드 생성 (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-2: 전체 필드", str(e))

    # 3-3: to_dict 변환
    try:
        event = _make_event()
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = event.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-3: AuditEvent.to_dict (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-3: to_dict", str(e))


# =============================================================================
# [4] AuditLogEntry 생성/해시 성능
# =============================================================================
def test_entry_perf(result: PerfResult) -> None:
    """AuditLogEntry 생성/해시 성능."""
    print("\n[4] AuditLogEntry 생성/해시 성능")

    # 4-1: AuditLogEntry 생성
    try:
        event = _make_event()
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = AuditLogEntry(
                id=str(uuid.uuid4()),
                event=event,
                sequence_number=i,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-1: AuditLogEntry 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-1: 생성", str(e))

    # 4-2: compute_hash 성능
    try:
        event = _make_event()
        entry = AuditLogEntry(id="test-id", event=event, sequence_number=1)
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = entry.compute_hash(INITIAL_CHAIN_HASH)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-2: compute_hash (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-2: compute_hash", str(e))

    # 4-3: verify_integrity 성능
    try:
        event = _make_event()
        entry = AuditLogEntry(id="test-id", event=event, sequence_number=1)
        entry.entry_hash = entry.compute_hash(INITIAL_CHAIN_HASH)
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = entry.verify_integrity(INITIAL_CHAIN_HASH)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-3: verify_integrity (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-3: verify_integrity", str(e))

    # 4-4: to_dict 변환
    try:
        event = _make_event()
        entry = AuditLogEntry(id="test-id", event=event, sequence_number=1)
        entry.entry_hash = entry.compute_hash(INITIAL_CHAIN_HASH)
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = entry.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-4: AuditLogEntry.to_dict (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-4: to_dict", str(e))


# =============================================================================
# [5] MemoryAuditStorage 처리량
# =============================================================================
def test_memory_storage_perf(result: PerfResult) -> None:
    """MemoryAuditStorage 처리량."""
    print("\n[5] MemoryAuditStorage 처리량")

    storage = MemoryAuditStorage(max_entries=100_000)

    # 5-1: write 성능
    try:
        event = _make_event()
        entries = [
            AuditLogEntry(id=str(uuid.uuid4()), event=event, sequence_number=i)
            for i in range(100)
        ]
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            storage.write(entries[i % 100])
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-1: write (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-1: write", str(e))

    # 5-2: write_batch 성능
    try:
        event = _make_event()
        batch = [
            AuditLogEntry(id=str(uuid.uuid4()), event=event, sequence_number=i)
            for i in range(50)
        ]
        iterations = 500
        start = time.perf_counter()
        for _ in range(iterations):
            storage.write_batch(batch)
        elapsed = (time.perf_counter() - start) * 1000
        total_entries = iterations * 50
        ops_sec = total_entries / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-2: write_batch 50개x500회 (25K)", f"{elapsed:.1f}ms, {ops_sec:.0f} entries/s")
    except Exception as e:
        result.fail("5-2: write_batch", str(e))

    # 5-3: read 성능 (필터 없음)
    try:
        # 저장소에 데이터가 있는 상태에서 조회
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            _ = storage.read(limit=100)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-3: read limit=100 (100회)", f"{elapsed:.1f}ms, {per_op:.1f}ms/op")
    except Exception as e:
        result.fail("5-3: read", str(e))

    # 5-4: read 성능 (이벤트타입 필터)
    try:
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            _ = storage.read(
                event_types=[AuditEventType.LOGIN_SUCCESS],
                limit=50,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-4: read 필터링 (100회)", f"{elapsed:.1f}ms, {per_op:.1f}ms/op")
    except Exception as e:
        result.fail("5-4: read 필터링", str(e))


# =============================================================================
# [6] LoginFailureTracker 성능
# =============================================================================
def test_login_tracker_perf(result: PerfResult) -> None:
    """LoginFailureTracker 성능."""
    print("\n[6] LoginFailureTracker 성능")

    tracker = LoginFailureTracker(threshold=100, window_minutes=15)

    # 6-1: record_failure 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            tracker.record_failure(f"user_{i % 200}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-1: record_failure (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-1: record_failure", str(e))

    # 6-2: get_failure_count 성능
    try:
        iterations = 50_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = tracker.get_failure_count(f"user_{i % 200}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-2: get_failure_count (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-2: get_failure_count", str(e))

    # 6-3: reset 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            tracker.reset(f"user_{i % 200}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("6-3: reset (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("6-3: reset", str(e))


# =============================================================================
# [7] AuditLogger 초기화 성능
# =============================================================================
def test_audit_logger_init_perf(result: PerfResult) -> None:
    """AuditLogger 초기화 성능."""
    print("\n[7] AuditLogger 초기화 성능")

    # 7-1: 기본 설정 초기화 (메모리 저장소)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {
            "storage": {"file": {"enabled": False}},
            "sampling_enabled": False,
        }
        iterations = 100
        loggers = []
        start = time.perf_counter()
        for _ in range(iterations):
            lg = AuditLogger(config_loader=mock_loader)
            loggers.append(lg)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-1: 초기화 (100)", f"{elapsed:.1f}ms, {per_op:.1f}ms/op")
        # 정리
        for lg in loggers:
            lg.close()
    except Exception as e:
        result.fail("7-1: 초기화", str(e))

    # 7-2: get_stats 속성 접근
    try:
        lg = _make_audit_logger()
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = lg.get_stats()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-2: get_stats (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
        lg.close()
    except Exception as e:
        result.fail("7-2: get_stats", str(e))


# =============================================================================
# [8] AuditLogger.log 성능
# =============================================================================
def test_audit_logger_log_perf(result: PerfResult) -> None:
    """AuditLogger.log 성능."""
    print("\n[8] AuditLogger.log 성능")

    lg = _make_audit_logger()

    # 8-1: 기본 로그 기록
    try:
        iterations = 5_000
        start = time.perf_counter()
        for i in range(iterations):
            lg.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                actor=f"user_{i % 100}",
                action="login",
                resource="/api/auth",
            )
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-1: log 기본 (5K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-1: log 기본", str(e))

    # 8-2: 전체 필드 로그 기록
    try:
        iterations = 2_000
        start = time.perf_counter()
        for i in range(iterations):
            lg.log(
                event_type=AuditEventType.DATA_READ,
                actor=f"admin_{i % 50}",
                action="read",
                resource=f"/api/data/{i}",
                result="success",
                severity=AuditSeverity.INFO,
                request_id=f"req-{i}",
                session_id=f"sess-{i}",
                ip_address="10.0.0.1",
                user_agent="Test/1.0",
                details={"record_count": i},
                metadata={"env": "perf"},
            )
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-2: log 전체 필드 (2K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-2: log 전체 필드", str(e))

    # 8-3: immediate=True 기록
    try:
        iterations = 2_000
        start = time.perf_counter()
        for i in range(iterations):
            lg.log(
                event_type=AuditEventType.INTRUSION_DETECTED,
                actor="system",
                action="detect",
                resource="firewall",
                severity=AuditSeverity.CRITICAL,
                immediate=True,
            )
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-3: log immediate (2K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-3: log immediate", str(e))

    lg.close()


# =============================================================================
# [9] 직렬화 성능 (to_dict / from_dict)
# =============================================================================
def test_serialization_perf(result: PerfResult) -> None:
    """직렬화 성능."""
    print("\n[9] 직렬화 성능 (to_dict / from_dict)")

    # 9-1: AuditEvent.from_dict
    try:
        event_dict = {
            "event_type": "authentication.login_success",
            "actor": "user@test.com",
            "action": "login",
            "resource": "/api/auth",
            "result": "success",
            "severity": "info",
        }
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = AuditEvent.from_dict(event_dict)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-1: AuditEvent.from_dict (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("9-1: from_dict", str(e))

    # 9-2: AuditLogEntry.to_dict + from_dict 왕복
    try:
        event = _make_event()
        entry = AuditLogEntry(id="roundtrip-id", event=event, sequence_number=1)
        entry.entry_hash = entry.compute_hash(INITIAL_CHAIN_HASH)
        iterations = 2_000
        start = time.perf_counter()
        for _ in range(iterations):
            d = entry.to_dict()
            _ = AuditLogEntry.from_dict(d)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-2: to_dict+from_dict 왕복 (2K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("9-2: 왕복", str(e))

    # 9-3: EVENT_DEFAULT_SEVERITY 조회
    try:
        categories = list(EVENT_DEFAULT_SEVERITY.keys())
        iterations = 100_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = EVENT_DEFAULT_SEVERITY.get(categories[i % len(categories)])
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-3: EVENT_DEFAULT_SEVERITY 조회 (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("9-3: 심각도 매핑", str(e))


# =============================================================================
# [10] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_perf(result: PerfResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[10] 멀티스레드 동시 접근")

    lg = _make_audit_logger()

    # 10-1: 4스레드 동시 로그 기록
    try:
        ops_per_thread = 2_000
        errors = []

        def log_worker(tid):
            try:
                for i in range(ops_per_thread):
                    lg.log(
                        event_type=AuditEventType.DATA_READ,
                        actor=f"thread_{tid}",
                        action="read",
                        resource=f"/api/data/{i}",
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=log_worker, args=(t,)) for t in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-1: 4스레드 log (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-1: 4스레드 log", str(e))

    # 10-2: 8스레드 혼합 (log + get_stats)
    try:
        ops_per_thread = 1_000
        errors = []

        def mixed_worker(tid):
            try:
                for i in range(ops_per_thread):
                    if i % 5 == 0:
                        _ = lg.get_stats()
                    else:
                        lg.log(
                            event_type=AuditEventType.LOGIN_SUCCESS,
                            actor=f"mixed_{tid}",
                            action="login",
                            resource="/api/auth",
                        )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=mixed_worker, args=(t,)) for t in range(8)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 8
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-2: 8스레드 혼합 (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-2: 8스레드 혼합", str(e))

    # 10-3: MemoryAuditStorage 멀티스레드 write
    try:
        storage = MemoryAuditStorage(max_entries=100_000)
        event = _make_event()
        ops_per_thread = 5_000
        errors = []

        def storage_writer():
            try:
                for i in range(ops_per_thread):
                    entry = AuditLogEntry(
                        id=str(uuid.uuid4()),
                        event=event,
                        sequence_number=i,
                    )
                    storage.write(entry)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=storage_writer) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-3: 4스레드 MemoryStorage write (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-3: Storage write 경합", str(e))

    # 10-4: LoginFailureTracker 멀티스레드
    try:
        tracker = LoginFailureTracker(threshold=1000, window_minutes=15)
        ops_per_thread = 5_000
        errors = []

        def tracker_worker(tid):
            try:
                for i in range(ops_per_thread):
                    tracker.record_failure(f"actor_{tid}_{i % 50}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=tracker_worker, args=(t,)) for t in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-4: 4스레드 LoginTracker (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-4: LoginTracker 경합", str(e))

    lg.close()


# =============================================================================
# [11] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerfResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[11] 메모리 사용량")

    # 11-1: AuditEvent 대량 생성 메모리
    try:
        tracemalloc.start()
        events = []
        for i in range(1_000):
            events.append(AuditEvent(
                event_type=AuditEventType.DATA_READ,
                actor=f"user_{i}",
                action="read",
                resource=f"/api/{i}",
            ))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_event = current / 1_000
        assert current / 1024 < 2048, f"메모리 과다: {current/1024:.1f}KB"
        result.ok("11-1: 1K AuditEvent 메모리", f"총: {current/1024:.1f}KB, 개당: {per_event:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-1: AuditEvent 메모리", str(e))

    # 11-2: AuditLogEntry 대량 생성 메모리
    try:
        tracemalloc.start()
        event = _make_event()
        entries = []
        for i in range(1_000):
            entry = AuditLogEntry(
                id=str(uuid.uuid4()),
                event=event,
                sequence_number=i,
            )
            entry.entry_hash = entry.compute_hash(INITIAL_CHAIN_HASH)
            entries.append(entry)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_entry = current / 1_000
        assert current / 1024 < 4096, f"메모리 과다: {current/1024:.1f}KB"
        result.ok("11-2: 1K AuditLogEntry 메모리", f"총: {current/1024:.1f}KB, 개당: {per_entry:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-2: AuditLogEntry 메모리", str(e))

    # 11-3: MemoryAuditStorage 대량 저장 메모리
    try:
        tracemalloc.start()
        storage = MemoryAuditStorage(max_entries=5_000)
        event = _make_event()
        for i in range(5_000):
            entry = AuditLogEntry(
                id=str(uuid.uuid4()),
                event=event,
                sequence_number=i,
            )
            storage.write(entry)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_entry = current / 5_000
        assert current / 1024 < 8192, f"메모리 과다: {current/1024:.1f}KB"
        result.ok("11-3: 5K MemoryStorage 메모리", f"총: {current/1024:.1f}KB, 개당: {per_entry:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-3: MemoryStorage 메모리", str(e))


# =============================================================================
# [12] 체인 해시 무결성 검증 성능
# =============================================================================
def test_chain_hash_perf(result: PerfResult) -> None:
    """체인 해시 무결성 검증 성능."""
    print("\n[12] 체인 해시 무결성 검증 성능")

    # 12-1: 체인 해시 생성 (연쇄)
    try:
        event = _make_event()
        chain_hash = INITIAL_CHAIN_HASH
        iterations = 1_000
        start = time.perf_counter()
        for i in range(iterations):
            entry = AuditLogEntry(
                id=f"chain-{i}",
                event=event,
                sequence_number=i + 1,
            )
            entry.chain_hash = chain_hash
            entry.entry_hash = entry.compute_hash(chain_hash)
            chain_hash = entry.entry_hash
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-1: 체인 해시 생성 (1K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-1: 체인 해시 생성", str(e))

    # 12-2: 체인 해시 검증 (100개 체인)
    try:
        event = _make_event()
        chain_entries = []
        chain_hash = INITIAL_CHAIN_HASH
        for i in range(100):
            entry = AuditLogEntry(
                id=f"verify-{i}",
                event=event,
                sequence_number=i + 1,
            )
            entry.chain_hash = chain_hash
            entry.entry_hash = entry.compute_hash(chain_hash)
            chain_hash = entry.entry_hash
            chain_entries.append(entry)

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            prev = INITIAL_CHAIN_HASH
            for entry in chain_entries:
                entry.verify_integrity(prev)
                prev = entry.entry_hash
        elapsed = (time.perf_counter() - start) * 1000
        per_verify = elapsed / (iterations * 100) * 1000
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-2: 100개 체인 검증 (100회)", f"{elapsed:.1f}ms, {per_verify:.3f}μs/entry")
    except Exception as e:
        result.fail("12-2: 체인 검증", str(e))

    # 12-3: get_by_category 성능
    try:
        iterations = 5_000
        categories = ["authentication", "authorization", "data_access", "security"]
        start = time.perf_counter()
        for i in range(iterations):
            _ = AuditEventType.get_by_category(categories[i % 4])
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-3: get_by_category (5K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-3: get_by_category", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """성능 테스트 실행."""
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("AuditLogger 성능 테스트")
    print("=" * 60)

    r = PerfResult()

    test_event_type_perf(r)
    test_severity_perf(r)
    test_event_creation_perf(r)
    test_entry_perf(r)
    test_memory_storage_perf(r)
    test_login_tracker_perf(r)
    test_audit_logger_init_perf(r)
    test_audit_logger_log_perf(r)
    test_serialization_perf(r)
    test_multithread_perf(r)
    test_memory_usage(r)
    test_chain_hash_perf(r)

    r.summary()

    _reset_global()


if __name__ == "__main__":
    main()
