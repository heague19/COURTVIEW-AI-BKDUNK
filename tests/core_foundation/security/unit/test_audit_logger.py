# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/security/unit
파일: test_audit_logger.py
설명: 감사 로거 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1]  모듈 상수 검증 (6개)
    [2]  AuditEventType Enum (8개)
    [3]  AuditSeverity Enum (8개)
    [4]  EVENT_DEFAULT_SEVERITY 매핑 (4개)
    [5]  AuditEvent 데이터 클래스 (8개)
    [6]  AuditLogEntry 데이터 클래스 (8개)
    [7]  MemoryAuditStorage (8개)
    [8]  BaseAuditStorage / BaseAlertHandler (4개)
    [9]  LogAlertHandler (4개)
    [10] SlackAlertHandler (5개)
    [11] EmailAlertHandler (4개)
    [12] WebhookAlertHandler (4개)
    [13] LoginFailureTracker (6개)
    [14] AuditLogger 초기화 (6개)
    [15] AuditLogger.log (10개)
    [16] AuditLogger 관리 API (8개)
    [17] 모듈 레벨 함수 (get/set/log_audit_event) (6개)
    [18] __all__ 내보내기 검증 (4개)
    [19] 엣지 케이스 (6개)
"""

import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import fields
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# UTF-8 출력 강제
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core_foundation.security.audit_logger import (
    # 상수
    DEFAULT_LOG_DIR,
    DEFAULT_MAX_FILES,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_FLUSH_INTERVAL,
    DEFAULT_SAMPLE_RATE,
    HASH_ALGORITHM,
    INITIAL_CHAIN_HASH,
    DEFAULT_LOGIN_FAILURE_THRESHOLD,
    DEFAULT_THRESHOLD_WINDOW_MINUTES,
    # Enum
    AuditEventType,
    AuditSeverity,
    # 데이터 클래스
    AuditEvent,
    AuditLogEntry,
    # 저장소
    BaseAuditStorage,
    FileAuditStorage,
    MemoryAuditStorage,
    # 알림 핸들러
    BaseAlertHandler,
    LogAlertHandler,
    SlackAlertHandler,
    EmailAlertHandler,
    WebhookAlertHandler,
    # 추적기
    LoginFailureTracker,
    # 메인 클래스
    AuditLogger,
    # 함수
    get_audit_logger,
    set_audit_logger,
    log_audit_event,
    # 상수 매핑
    EVENT_DEFAULT_SEVERITY,
)


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼
# =============================================================================
def _make_audit_logger(**overrides) -> AuditLogger:
    """테스트용 AuditLogger 생성."""
    mock_loader = MagicMock()
    # 기본: 파일 저장소 비활성, 메모리 저장소 사용
    config = overrides.get("config", {
        "storage": {"file": {"enabled": False}},
        "sampling_enabled": False,  # 테스트 시 샘플링 비활성
    })
    mock_loader.get.return_value = config
    logger = AuditLogger(
        config_loader=mock_loader,
        metrics_collector=overrides.get("metrics_collector"),
    )
    return logger


def _make_event(**kwargs) -> AuditEvent:
    """테스트용 AuditEvent 생성."""
    defaults = {
        "event_type": AuditEventType.LOGIN_SUCCESS,
        "actor": "test_user",
        "action": "login",
        "resource": "/api/auth",
    }
    defaults.update(kwargs)
    return AuditEvent(**defaults)


def _reset_global():
    """전역 인스턴스 리셋."""
    import core_foundation.security.audit_logger as mod
    with mod._audit_logger_lock:
        mod._audit_logger = None


# =============================================================================
# [1] 모듈 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """모듈 상수 검증."""
    print("\n[1] 모듈 상수 검증")

    # 1-1
    try:
        assert isinstance(DEFAULT_LOG_DIR, str) and len(DEFAULT_LOG_DIR) > 0
        result.ok("1-1: DEFAULT_LOG_DIR 문자열")
    except Exception as e:
        result.fail("1-1: DEFAULT_LOG_DIR", str(e))

    # 1-2
    try:
        assert isinstance(DEFAULT_MAX_FILES, int) and DEFAULT_MAX_FILES > 0
        result.ok("1-2: DEFAULT_MAX_FILES 양의 정수")
    except Exception as e:
        result.fail("1-2: DEFAULT_MAX_FILES", str(e))

    # 1-3
    try:
        assert isinstance(DEFAULT_BUFFER_SIZE, int) and DEFAULT_BUFFER_SIZE > 0
        result.ok("1-3: DEFAULT_BUFFER_SIZE 양의 정수")
    except Exception as e:
        result.fail("1-3: DEFAULT_BUFFER_SIZE", str(e))

    # 1-4
    try:
        assert isinstance(DEFAULT_FLUSH_INTERVAL, float) and DEFAULT_FLUSH_INTERVAL > 0
        result.ok("1-4: DEFAULT_FLUSH_INTERVAL 양의 실수")
    except Exception as e:
        result.fail("1-4: DEFAULT_FLUSH_INTERVAL", str(e))

    # 1-5
    try:
        assert HASH_ALGORITHM == "sha256"
        result.ok("1-5: HASH_ALGORITHM = sha256")
    except Exception as e:
        result.fail("1-5: HASH_ALGORITHM", str(e))

    # 1-6
    try:
        assert isinstance(INITIAL_CHAIN_HASH, str) and len(INITIAL_CHAIN_HASH) > 0
        assert isinstance(DEFAULT_LOGIN_FAILURE_THRESHOLD, int)
        assert isinstance(DEFAULT_THRESHOLD_WINDOW_MINUTES, int)
        result.ok("1-6: 체인 해시 / 로그인 실패 상수")
    except Exception as e:
        result.fail("1-6: 추가 상수", str(e))


# =============================================================================
# [2] AuditEventType Enum
# =============================================================================
def test_audit_event_type(result: TestResult) -> None:
    """AuditEventType Enum 검증."""
    print("\n[2] AuditEventType Enum")

    # 2-1: 멤버 수
    try:
        members = list(AuditEventType)
        assert len(members) >= 38, f"멤버 수: {len(members)}"
        result.ok(f"2-1: AuditEventType 멤버 {len(members)}개")
    except Exception as e:
        result.fail("2-1: 멤버 수", str(e))

    # 2-2: 인증 이벤트 존재
    try:
        auth_events = AuditEventType.get_by_category("authentication")
        assert len(auth_events) >= 8
        assert AuditEventType.LOGIN_SUCCESS in auth_events
        assert AuditEventType.LOGIN_FAILURE in auth_events
        result.ok("2-2: 인증 이벤트 8개+")
    except Exception as e:
        result.fail("2-2: 인증 이벤트", str(e))

    # 2-3: 보안 이벤트 존재
    try:
        sec_events = AuditEventType.get_by_category("security")
        assert len(sec_events) >= 6
        assert AuditEventType.INTRUSION_DETECTED in sec_events
        result.ok("2-3: 보안 이벤트 6개+")
    except Exception as e:
        result.fail("2-3: 보안 이벤트", str(e))

    # 2-4: category 프로퍼티
    try:
        assert AuditEventType.LOGIN_SUCCESS.category == "authentication"
        assert AuditEventType.DATA_READ.category == "data_access"
        assert AuditEventType.INTRUSION_DETECTED.category == "security"
        result.ok("2-4: category 프로퍼티")
    except Exception as e:
        result.fail("2-4: category", str(e))

    # 2-5: action 프로퍼티
    try:
        assert AuditEventType.LOGIN_SUCCESS.action == "login_success"
        assert AuditEventType.DATA_READ.action == "data_read"
        result.ok("2-5: action 프로퍼티")
    except Exception as e:
        result.fail("2-5: action", str(e))

    # 2-6: from_string
    try:
        et = AuditEventType.from_string("authentication.login_success")
        assert et == AuditEventType.LOGIN_SUCCESS
        none_result = AuditEventType.from_string("nonexistent.event")
        assert none_result is None
        result.ok("2-6: from_string 동작")
    except Exception as e:
        result.fail("2-6: from_string", str(e))

    # 2-7: value 형식 (category.action)
    try:
        for et in AuditEventType:
            assert "." in et.value, f"{et.name} 값에 . 없음: {et.value}"
        result.ok("2-7: 모든 value에 '.' 포함")
    except Exception as e:
        result.fail("2-7: value 형식", str(e))

    # 2-8: get_by_category 빈 결과
    try:
        empty = AuditEventType.get_by_category("nonexistent_category")
        assert empty == []
        result.ok("2-8: get_by_category 빈 결과")
    except Exception as e:
        result.fail("2-8: 빈 결과", str(e))


# =============================================================================
# [3] AuditSeverity Enum
# =============================================================================
def test_audit_severity(result: TestResult) -> None:
    """AuditSeverity Enum 검증."""
    print("\n[3] AuditSeverity Enum")

    # 3-1: 멤버 수
    try:
        members = list(AuditSeverity)
        assert len(members) == 5
        result.ok("3-1: AuditSeverity 멤버 5개")
    except Exception as e:
        result.fail("3-1: 멤버 수", str(e))

    # 3-2: 순서 (비교 연산자)
    try:
        assert AuditSeverity.DEBUG < AuditSeverity.INFO
        assert AuditSeverity.INFO < AuditSeverity.WARNING
        assert AuditSeverity.WARNING < AuditSeverity.ERROR
        assert AuditSeverity.ERROR < AuditSeverity.CRITICAL
        result.ok("3-2: 순서 정상")
    except Exception as e:
        result.fail("3-2: 순서", str(e))

    # 3-3: retain_days 프로퍼티
    try:
        assert AuditSeverity.DEBUG.retain_days == 7
        assert AuditSeverity.INFO.retain_days == 30
        assert AuditSeverity.WARNING.retain_days == 90
        assert AuditSeverity.ERROR.retain_days == 180
        assert AuditSeverity.CRITICAL.retain_days == 365
        result.ok("3-3: retain_days 프로퍼티")
    except Exception as e:
        result.fail("3-3: retain_days", str(e))

    # 3-4: name_str 프로퍼티
    try:
        assert AuditSeverity.DEBUG.name_str == "debug"
        assert AuditSeverity.CRITICAL.name_str == "critical"
        result.ok("3-4: name_str 프로퍼티")
    except Exception as e:
        result.fail("3-4: name_str", str(e))

    # 3-5: from_string
    try:
        s = AuditSeverity.from_string("warning")
        assert s == AuditSeverity.WARNING
        s2 = AuditSeverity.from_string("CRITICAL")
        assert s2 == AuditSeverity.CRITICAL
        result.ok("3-5: from_string 대소문자 무관")
    except Exception as e:
        result.fail("3-5: from_string", str(e))

    # 3-6: from_string None
    try:
        s = AuditSeverity.from_string("nonexistent")
        assert s is None
        result.ok("3-6: from_string 미존재 → None")
    except Exception as e:
        result.fail("3-6: from_string None", str(e))

    # 3-7: ge/le 비교
    try:
        assert AuditSeverity.CRITICAL >= AuditSeverity.CRITICAL
        assert AuditSeverity.WARNING <= AuditSeverity.ERROR
        assert AuditSeverity.INFO >= AuditSeverity.DEBUG
        result.ok("3-7: ge/le 비교 연산자")
    except Exception as e:
        result.fail("3-7: ge/le", str(e))

    # 3-8: value (숫자값)
    try:
        assert AuditSeverity.DEBUG.value == 10
        assert AuditSeverity.INFO.value == 20
        assert AuditSeverity.WARNING.value == 30
        assert AuditSeverity.ERROR.value == 40
        assert AuditSeverity.CRITICAL.value == 50
        result.ok("3-8: 숫자 값 (10~50)")
    except Exception as e:
        result.fail("3-8: 숫자 값", str(e))


# =============================================================================
# [4] EVENT_DEFAULT_SEVERITY 매핑
# =============================================================================
def test_default_severity(result: TestResult) -> None:
    """EVENT_DEFAULT_SEVERITY 매핑 검증."""
    print("\n[4] EVENT_DEFAULT_SEVERITY 매핑")

    # 4-1
    try:
        assert isinstance(EVENT_DEFAULT_SEVERITY, dict)
        assert len(EVENT_DEFAULT_SEVERITY) >= 6
        result.ok("4-1: 매핑 dict 6개+")
    except Exception as e:
        result.fail("4-1: 매핑 구조", str(e))

    # 4-2
    try:
        assert EVENT_DEFAULT_SEVERITY["authentication"] == AuditSeverity.INFO
        assert EVENT_DEFAULT_SEVERITY["security"] == AuditSeverity.CRITICAL
        result.ok("4-2: authentication=INFO, security=CRITICAL")
    except Exception as e:
        result.fail("4-2: 매핑 값", str(e))

    # 4-3
    try:
        assert EVENT_DEFAULT_SEVERITY["authorization"] == AuditSeverity.WARNING
        assert EVENT_DEFAULT_SEVERITY["configuration"] == AuditSeverity.WARNING
        result.ok("4-3: authorization/configuration=WARNING")
    except Exception as e:
        result.fail("4-3: 매핑 값2", str(e))

    # 4-4
    try:
        for key, val in EVENT_DEFAULT_SEVERITY.items():
            assert isinstance(val, AuditSeverity), f"{key}: {type(val)}"
        result.ok("4-4: 모든 값 AuditSeverity 타입")
    except Exception as e:
        result.fail("4-4: 타입", str(e))


# =============================================================================
# [5] AuditEvent 데이터 클래스
# =============================================================================
def test_audit_event(result: TestResult) -> None:
    """AuditEvent 데이터 클래스 검증."""
    print("\n[5] AuditEvent 데이터 클래스")

    # 5-1: 기본 생성
    try:
        evt = _make_event()
        assert evt.event_type == AuditEventType.LOGIN_SUCCESS
        assert evt.actor == "test_user"
        assert evt.result == "success"
        result.ok("5-1: 기본 생성")
    except Exception as e:
        result.fail("5-1: 기본 생성", str(e))

    # 5-2: timestamp 자동 설정
    try:
        evt = _make_event()
        assert isinstance(evt.timestamp, datetime)
        result.ok("5-2: timestamp 자동 설정")
    except Exception as e:
        result.fail("5-2: timestamp", str(e))

    # 5-3: severity 자동 설정 (카테고리 기반)
    try:
        evt = _make_event(event_type=AuditEventType.INTRUSION_DETECTED)
        # security 카테고리 → CRITICAL → 최소 WARNING 보장
        assert evt.severity >= AuditSeverity.WARNING
        result.ok("5-3: severity 자동 설정 (security → WARNING+)")
    except Exception as e:
        result.fail("5-3: severity 자동", str(e))

    # 5-4: to_dict
    try:
        evt = _make_event(ip_address="192.168.1.1")
        d = evt.to_dict()
        assert isinstance(d, dict)
        assert d["event_type"] == "authentication.login_success"
        assert d["ip_address"] == "192.168.1.1"
        assert "severity" in d
        result.ok("5-4: to_dict 변환")
    except Exception as e:
        result.fail("5-4: to_dict", str(e))

    # 5-5: from_dict
    try:
        evt = _make_event()
        d = evt.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.event_type == AuditEventType.LOGIN_SUCCESS
        assert restored.actor == "test_user"
        result.ok("5-5: from_dict 복원")
    except Exception as e:
        result.fail("5-5: from_dict", str(e))

    # 5-6: from_dict 잘못된 이벤트 타입 → ValueError
    try:
        raised = False
        try:
            AuditEvent.from_dict({"event_type": "invalid.type", "actor": "x"})
        except ValueError:
            raised = True
        assert raised
        result.ok("5-6: from_dict 잘못된 타입 → ValueError")
    except Exception as e:
        result.fail("5-6: from_dict ValueError", str(e))

    # 5-7: details/metadata 기본 빈 dict
    try:
        evt = _make_event()
        assert evt.details == {}
        assert evt.metadata == {}
        result.ok("5-7: details/metadata 기본 빈 dict")
    except Exception as e:
        result.fail("5-7: details/metadata", str(e))

    # 5-8: 보안 이벤트 심각도 강제 상향
    try:
        evt = _make_event(
            event_type=AuditEventType.IP_BLOCKED,
            severity=AuditSeverity.INFO,
        )
        # 보안 이벤트는 최소 WARNING
        assert evt.severity >= AuditSeverity.WARNING
        result.ok("5-8: 보안 이벤트 심각도 강제 상향")
    except Exception as e:
        result.fail("5-8: 심각도 상향", str(e))


# =============================================================================
# [6] AuditLogEntry 데이터 클래스
# =============================================================================
def test_audit_log_entry(result: TestResult) -> None:
    """AuditLogEntry 데이터 클래스 검증."""
    print("\n[6] AuditLogEntry 데이터 클래스")

    # 6-1: 기본 생성
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="test-id-1", event=evt)
        assert entry.id == "test-id-1"
        assert entry.event is evt
        assert entry.sequence_number == 0
        result.ok("6-1: 기본 생성")
    except Exception as e:
        result.fail("6-1: 기본 생성", str(e))

    # 6-2: id 자동 생성 (빈 문자열)
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="", event=evt)
        assert len(entry.id) > 0
        # UUID 형식
        uuid.UUID(entry.id)
        result.ok("6-2: id 자동 생성 (UUID)")
    except Exception as e:
        result.fail("6-2: id 자동 생성", str(e))

    # 6-3: created_at 자동 설정
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="e3", event=evt)
        assert isinstance(entry.created_at, datetime)
        result.ok("6-3: created_at 자동 설정")
    except Exception as e:
        result.fail("6-3: created_at", str(e))

    # 6-4: compute_hash
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="hash-test", event=evt, sequence_number=1)
        h = entry.compute_hash(previous_hash="prev_hash")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex = 64 chars
        result.ok("6-4: compute_hash SHA-256")
    except Exception as e:
        result.fail("6-4: compute_hash", str(e))

    # 6-5: verify_integrity
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="integrity-test", event=evt, sequence_number=1)
        entry.entry_hash = entry.compute_hash("genesis")
        assert entry.verify_integrity("genesis") is True
        assert entry.verify_integrity("wrong_hash") is False
        result.ok("6-5: verify_integrity")
    except Exception as e:
        result.fail("6-5: verify_integrity", str(e))

    # 6-6: to_dict
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="dict-test", event=evt, sequence_number=5)
        d = entry.to_dict()
        assert d["id"] == "dict-test"
        assert d["sequence_number"] == 5
        assert "event" in d
        assert "entry_hash" in d
        result.ok("6-6: to_dict")
    except Exception as e:
        result.fail("6-6: to_dict", str(e))

    # 6-7: from_dict
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="from-dict-test", event=evt, sequence_number=3)
        d = entry.to_dict()
        restored = AuditLogEntry.from_dict(d)
        assert restored.id == "from-dict-test"
        assert restored.sequence_number == 3
        result.ok("6-7: from_dict 복원")
    except Exception as e:
        result.fail("6-7: from_dict", str(e))

    # 6-8: 해시 결정적 (동일 입력 → 동일 출력)
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="det-test", event=evt, sequence_number=1)
        h1 = entry.compute_hash("prev")
        h2 = entry.compute_hash("prev")
        assert h1 == h2
        result.ok("6-8: 해시 결정적")
    except Exception as e:
        result.fail("6-8: 해시 결정적", str(e))


# =============================================================================
# [7] MemoryAuditStorage
# =============================================================================
def test_memory_storage(result: TestResult) -> None:
    """MemoryAuditStorage 검증."""
    print("\n[7] MemoryAuditStorage")

    # 7-1: 초기화
    try:
        storage = MemoryAuditStorage(max_entries=100)
        assert storage is not None
        result.ok("7-1: 초기화 성공")
    except Exception as e:
        result.fail("7-1: 초기화", str(e))

    # 7-2: write
    try:
        storage = MemoryAuditStorage()
        evt = _make_event()
        entry = AuditLogEntry(id="w1", event=evt)
        ok = storage.write(entry)
        assert ok is True
        result.ok("7-2: write 성공")
    except Exception as e:
        result.fail("7-2: write", str(e))

    # 7-3: write_batch
    try:
        storage = MemoryAuditStorage()
        entries = [
            AuditLogEntry(id=f"b{i}", event=_make_event())
            for i in range(5)
        ]
        count = storage.write_batch(entries)
        assert count == 5
        result.ok("7-3: write_batch 5개")
    except Exception as e:
        result.fail("7-3: write_batch", str(e))

    # 7-4: read (전체)
    try:
        storage = MemoryAuditStorage()
        for i in range(3):
            storage.write(AuditLogEntry(id=f"r{i}", event=_make_event()))
        entries = storage.read()
        assert len(entries) == 3
        result.ok("7-4: read 3개")
    except Exception as e:
        result.fail("7-4: read", str(e))

    # 7-5: read 필터 — event_types
    try:
        storage = MemoryAuditStorage()
        storage.write(AuditLogEntry(
            id="f1", event=_make_event(event_type=AuditEventType.LOGIN_SUCCESS)
        ))
        storage.write(AuditLogEntry(
            id="f2", event=_make_event(event_type=AuditEventType.DATA_READ)
        ))
        results = storage.read(event_types=[AuditEventType.LOGIN_SUCCESS])
        assert len(results) == 1
        assert results[0].id == "f1"
        result.ok("7-5: read 이벤트 타입 필터")
    except Exception as e:
        result.fail("7-5: 이벤트 타입 필터", str(e))

    # 7-6: read 필터 — actor
    try:
        storage = MemoryAuditStorage()
        storage.write(AuditLogEntry(id="a1", event=_make_event(actor="alice")))
        storage.write(AuditLogEntry(id="a2", event=_make_event(actor="bob")))
        results = storage.read(actor="alice")
        assert len(results) == 1
        result.ok("7-6: read actor 필터")
    except Exception as e:
        result.fail("7-6: actor 필터", str(e))

    # 7-7: clear / get_all
    try:
        storage = MemoryAuditStorage()
        storage.write(AuditLogEntry(id="c1", event=_make_event()))
        assert len(storage.get_all()) == 1
        storage.clear()
        assert len(storage.get_all()) == 0
        result.ok("7-7: clear / get_all")
    except Exception as e:
        result.fail("7-7: clear/get_all", str(e))

    # 7-8: max_entries 제한
    try:
        storage = MemoryAuditStorage(max_entries=3)
        for i in range(5):
            storage.write(AuditLogEntry(id=f"m{i}", event=_make_event()))
        assert len(storage.get_all()) == 3
        result.ok("7-8: max_entries 제한")
    except Exception as e:
        result.fail("7-8: max_entries", str(e))


# =============================================================================
# [8] BaseAuditStorage / BaseAlertHandler
# =============================================================================
def test_base_classes(result: TestResult) -> None:
    """기본 추상 클래스 검증."""
    print("\n[8] BaseAuditStorage / BaseAlertHandler")

    # 8-1: BaseAuditStorage 추상 클래스
    try:
        from abc import ABC
        assert issubclass(BaseAuditStorage, ABC)
        result.ok("8-1: BaseAuditStorage는 ABC")
    except Exception as e:
        result.fail("8-1: ABC", str(e))

    # 8-2: BaseAuditStorage 직접 인스턴스화 불가
    try:
        raised = False
        try:
            _ = BaseAuditStorage()
        except TypeError:
            raised = True
        assert raised
        result.ok("8-2: BaseAuditStorage 인스턴스화 불가")
    except Exception as e:
        result.fail("8-2: 인스턴스화", str(e))

    # 8-3: BaseAlertHandler 추상 클래스
    try:
        assert issubclass(BaseAlertHandler, ABC)
        result.ok("8-3: BaseAlertHandler는 ABC")
    except Exception as e:
        result.fail("8-3: ABC", str(e))

    # 8-4: BaseAlertHandler 직접 인스턴스화 불가
    try:
        raised = False
        try:
            _ = BaseAlertHandler()
        except TypeError:
            raised = True
        assert raised
        result.ok("8-4: BaseAlertHandler 인스턴스화 불가")
    except Exception as e:
        result.fail("8-4: 인스턴스화", str(e))


# =============================================================================
# [9] LogAlertHandler
# =============================================================================
def test_log_alert_handler(result: TestResult) -> None:
    """LogAlertHandler 검증."""
    print("\n[9] LogAlertHandler")

    # 9-1: 초기화
    try:
        handler = LogAlertHandler()
        assert handler is not None
        result.ok("9-1: LogAlertHandler 초기화")
    except Exception as e:
        result.fail("9-1: 초기화", str(e))

    # 9-2: issubclass
    try:
        assert issubclass(LogAlertHandler, BaseAlertHandler)
        result.ok("9-2: BaseAlertHandler 상속")
    except Exception as e:
        result.fail("9-2: 상속", str(e))

    # 9-3: send_alert 반환값
    try:
        handler = LogAlertHandler()
        evt = _make_event()
        ok = handler.send_alert(evt, "test_alert", "테스트 알림")
        assert ok is True
        result.ok("9-3: send_alert → True")
    except Exception as e:
        result.fail("9-3: send_alert", str(e))

    # 9-4: 커스텀 log_level
    try:
        import logging
        handler = LogAlertHandler(log_level=logging.ERROR)
        assert handler._log_level == logging.ERROR
        result.ok("9-4: 커스텀 log_level")
    except Exception as e:
        result.fail("9-4: log_level", str(e))


# =============================================================================
# [10] SlackAlertHandler
# =============================================================================
def test_slack_handler(result: TestResult) -> None:
    """SlackAlertHandler 검증."""
    print("\n[10] SlackAlertHandler")

    # 10-1: 초기화 (webhook_url=None → 경고)
    try:
        handler = SlackAlertHandler(webhook_url=None)
        assert handler._webhook_url is None or handler._webhook_url == os.environ.get("SLACK_WEBHOOK_URL")
        result.ok("10-1: 초기화 (webhook_url=None)")
    except Exception as e:
        result.fail("10-1: 초기화", str(e))

    # 10-2: send_alert without URL → False
    try:
        # webhook 환경변수 없도록 보장
        orig = os.environ.pop("SLACK_WEBHOOK_URL", None)
        try:
            handler = SlackAlertHandler(webhook_url=None)
            evt = _make_event()
            ok = handler.send_alert(evt, "test", "msg")
            assert ok is False
            result.ok("10-2: send_alert URL 없음 → False")
        finally:
            if orig:
                os.environ["SLACK_WEBHOOK_URL"] = orig
    except Exception as e:
        result.fail("10-2: send_alert", str(e))

    # 10-3: rate_limit 동작
    try:
        handler = SlackAlertHandler(webhook_url="http://fake", rate_limit=2)
        # 첫 2번은 통과
        assert handler._check_rate_limit() is True
        assert handler._check_rate_limit() is True
        # 3번째 초과
        assert handler._check_rate_limit() is False
        result.ok("10-3: rate_limit 동작")
    except Exception as e:
        result.fail("10-3: rate_limit", str(e))

    # 10-4: _build_message 구조
    try:
        handler = SlackAlertHandler(webhook_url="http://fake")
        evt = _make_event(severity=AuditSeverity.CRITICAL)
        msg = handler._build_message(evt, "침입 감지", "위협 발견")
        assert "attachments" in msg
        assert len(msg["attachments"]) >= 1
        assert "fields" in msg["attachments"][0]
        result.ok("10-4: _build_message 구조")
    except Exception as e:
        result.fail("10-4: _build_message", str(e))

    # 10-5: SEVERITY_COLORS 존재
    try:
        colors = SlackAlertHandler.SEVERITY_COLORS
        assert "critical" in colors
        assert "info" in colors
        assert all(c.startswith("#") for c in colors.values())
        result.ok("10-5: SEVERITY_COLORS 색상 코드")
    except Exception as e:
        result.fail("10-5: SEVERITY_COLORS", str(e))


# =============================================================================
# [11] EmailAlertHandler
# =============================================================================
def test_email_handler(result: TestResult) -> None:
    """EmailAlertHandler 검증."""
    print("\n[11] EmailAlertHandler")

    # 11-1: 초기화
    try:
        handler = EmailAlertHandler(to_emails=["admin@test.com"])
        assert handler._to_emails == ["admin@test.com"]
        result.ok("11-1: EmailAlertHandler 초기화")
    except Exception as e:
        result.fail("11-1: 초기화", str(e))

    # 11-2: send_alert 수신자 없음 → False
    try:
        handler = EmailAlertHandler(to_emails=[])
        evt = _make_event()
        ok = handler.send_alert(evt, "test", "msg")
        assert ok is False
        result.ok("11-2: 수신자 없음 → False")
    except Exception as e:
        result.fail("11-2: 수신자 없음", str(e))

    # 11-3: rate_limit 설정
    try:
        handler = EmailAlertHandler(rate_limit=3)
        assert handler._rate_limit == 3
        result.ok("11-3: rate_limit 설정")
    except Exception as e:
        result.fail("11-3: rate_limit", str(e))

    # 11-4: _build_html_content 구조
    try:
        handler = EmailAlertHandler()
        evt = _make_event()
        html = handler._build_html_content(evt, "경고", "보안 위협")
        assert "<html>" in html
        assert "보안 위협" in html
        result.ok("11-4: HTML 본문 생성")
    except Exception as e:
        result.fail("11-4: HTML 본문", str(e))


# =============================================================================
# [12] WebhookAlertHandler
# =============================================================================
def test_webhook_handler(result: TestResult) -> None:
    """WebhookAlertHandler 검증."""
    print("\n[12] WebhookAlertHandler")

    # 12-1: 초기화
    try:
        handler = WebhookAlertHandler(webhook_url="http://example.com/hook")
        assert handler._webhook_url == "http://example.com/hook"
        result.ok("12-1: WebhookAlertHandler 초기화")
    except Exception as e:
        result.fail("12-1: 초기화", str(e))

    # 12-2: send_alert URL 없음 → False
    try:
        orig = os.environ.pop("ALERT_WEBHOOK_URL", None)
        try:
            handler = WebhookAlertHandler(webhook_url=None)
            evt = _make_event()
            ok = handler.send_alert(evt, "test", "msg")
            assert ok is False
            result.ok("12-2: URL 없음 → False")
        finally:
            if orig:
                os.environ["ALERT_WEBHOOK_URL"] = orig
    except Exception as e:
        result.fail("12-2: URL 없음", str(e))

    # 12-3: _build_payload 구조
    try:
        handler = WebhookAlertHandler(webhook_url="http://fake")
        evt = _make_event()
        payload = handler._build_payload(evt, "침입 감지", "위협 발견")
        assert "alert_type" in payload
        assert "event" in payload
        assert payload["source"] == "courtview-security"
        result.ok("12-3: _build_payload 구조")
    except Exception as e:
        result.fail("12-3: _build_payload", str(e))

    # 12-4: _build_headers 인증 헤더
    try:
        handler = WebhookAlertHandler(
            webhook_url="http://fake",
            auth_type="bearer",
            auth_token="my_token",
        )
        headers = handler._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my_token"
        result.ok("12-4: _build_headers bearer 인증")
    except Exception as e:
        result.fail("12-4: _build_headers", str(e))


# =============================================================================
# [13] LoginFailureTracker
# =============================================================================
def test_login_failure_tracker(result: TestResult) -> None:
    """LoginFailureTracker 검증."""
    print("\n[13] LoginFailureTracker")

    # 13-1: 초기화
    try:
        tracker = LoginFailureTracker(threshold=3, window_minutes=5)
        assert tracker._threshold == 3
        result.ok("13-1: LoginFailureTracker 초기화")
    except Exception as e:
        result.fail("13-1: 초기화", str(e))

    # 13-2: record_failure 임계값 미만 → False
    try:
        tracker = LoginFailureTracker(threshold=3)
        assert tracker.record_failure("user1") is False
        assert tracker.record_failure("user1") is False
        result.ok("13-2: 임계값 미만 → False")
    except Exception as e:
        result.fail("13-2: 임계값 미만", str(e))

    # 13-3: record_failure 임계값 도달 → True
    try:
        tracker = LoginFailureTracker(threshold=3)
        tracker.record_failure("user2")
        tracker.record_failure("user2")
        reached = tracker.record_failure("user2")
        assert reached is True
        result.ok("13-3: 임계값 도달 → True")
    except Exception as e:
        result.fail("13-3: 임계값 도달", str(e))

    # 13-4: get_failure_count
    try:
        tracker = LoginFailureTracker(threshold=5)
        tracker.record_failure("user3")
        tracker.record_failure("user3")
        assert tracker.get_failure_count("user3") == 2
        assert tracker.get_failure_count("unknown") == 0
        result.ok("13-4: get_failure_count")
    except Exception as e:
        result.fail("13-4: get_failure_count", str(e))

    # 13-5: reset
    try:
        tracker = LoginFailureTracker(threshold=5)
        tracker.record_failure("user4")
        tracker.record_failure("user4")
        tracker.reset("user4")
        assert tracker.get_failure_count("user4") == 0
        result.ok("13-5: reset")
    except Exception as e:
        result.fail("13-5: reset", str(e))

    # 13-6: 사용자별 독립 추적
    try:
        tracker = LoginFailureTracker(threshold=3)
        tracker.record_failure("alice")
        tracker.record_failure("alice")
        tracker.record_failure("bob")
        assert tracker.get_failure_count("alice") == 2
        assert tracker.get_failure_count("bob") == 1
        result.ok("13-6: 사용자별 독립 추적")
    except Exception as e:
        result.fail("13-6: 독립 추적", str(e))


# =============================================================================
# [14] AuditLogger 초기화
# =============================================================================
def test_audit_logger_init(result: TestResult) -> None:
    """AuditLogger 초기화 검증."""
    print("\n[14] AuditLogger 초기화")

    # 14-1: 기본 초기화
    try:
        al = _make_audit_logger()
        assert al is not None
        result.ok("14-1: 기본 초기화 성공")
    except Exception as e:
        result.fail("14-1: 기본 초기화", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 14-2: 저장소 존재
    try:
        al = _make_audit_logger()
        assert len(al._storages) >= 1
        result.ok("14-2: 저장소 1개+")
    except Exception as e:
        result.fail("14-2: 저장소", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 14-3: 알림 핸들러 존재
    try:
        al = _make_audit_logger()
        assert len(al._alert_handlers) >= 1
        result.ok("14-3: 알림 핸들러 1개+")
    except Exception as e:
        result.fail("14-3: 알림 핸들러", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 14-4: 체인 해시 초기 상태
    try:
        al = _make_audit_logger()
        assert al._last_chain_hash == INITIAL_CHAIN_HASH
        assert al._sequence_number == 0
        result.ok("14-4: 체인 해시 초기 상태")
    except Exception as e:
        result.fail("14-4: 체인 해시", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 14-5: _login_tracker 존재
    try:
        al = _make_audit_logger()
        assert isinstance(al._login_tracker, LoginFailureTracker)
        result.ok("14-5: LoginFailureTracker 존재")
    except Exception as e:
        result.fail("14-5: _login_tracker", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 14-6: get_stats
    try:
        al = _make_audit_logger()
        stats = al.get_stats()
        assert isinstance(stats, dict)
        assert "sequence_number" in stats
        assert "integrity_enabled" in stats
        assert "alerting_enabled" in stats
        result.ok("14-6: get_stats 구조")
    except Exception as e:
        result.fail("14-6: get_stats", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass


# =============================================================================
# [15] AuditLogger.log
# =============================================================================
def test_audit_logger_log(result: TestResult) -> None:
    """AuditLogger.log 검증."""
    print("\n[15] AuditLogger.log")

    # 15-1: 기본 로그 기록
    try:
        al = _make_audit_logger()
        entry_id = al.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            actor="user1",
            action="login",
            resource="/auth",
        )
        assert entry_id is not None
        assert isinstance(entry_id, str)
        result.ok("15-1: 기본 로그 기록")
    except Exception as e:
        result.fail("15-1: 기본 로그", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-2: sequence_number 증가
    try:
        al = _make_audit_logger()
        al.log(AuditEventType.LOGIN_SUCCESS, "u", "login", "/auth")
        al.log(AuditEventType.LOGOUT, "u", "logout", "/auth")
        assert al._sequence_number == 2
        result.ok("15-2: sequence_number 증가")
    except Exception as e:
        result.fail("15-2: sequence_number", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-3: immediate=True 즉시 기록
    try:
        al = _make_audit_logger()
        # 메모리 저장소 추가
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al.log(
            AuditEventType.INTRUSION_DETECTED,
            "attacker",
            "intrusion",
            "/admin",
            immediate=True,
        )
        # 즉시 기록되므로 저장소에 있어야 함
        entries = mem_storage.get_all()
        assert len(entries) >= 1
        result.ok("15-3: immediate=True 즉시 기록")
    except Exception as e:
        result.fail("15-3: immediate", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-4: CRITICAL 심각도 자동 즉시 기록
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al.log(
            AuditEventType.BRUTE_FORCE_DETECTED,
            "attacker",
            "brute_force",
            "/login",
            severity=AuditSeverity.CRITICAL,
        )
        entries = mem_storage.get_all()
        assert len(entries) >= 1
        result.ok("15-4: CRITICAL → 즉시 기록")
    except Exception as e:
        result.fail("15-4: CRITICAL 즉시", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-5: log_event (AuditEvent 객체)
    try:
        al = _make_audit_logger()
        evt = _make_event()
        entry_id = al.log_event(evt)
        assert entry_id is not None
        result.ok("15-5: log_event 동작")
    except Exception as e:
        result.fail("15-5: log_event", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-6: 로그인 실패 추적
    try:
        al = _make_audit_logger()
        for _ in range(DEFAULT_LOGIN_FAILURE_THRESHOLD):
            al.log(
                AuditEventType.LOGIN_FAILURE,
                "attacker",
                "login_failure",
                "/auth",
            )
        # 임계값 초과 후 알림 전송됨 (오류 없이 완료)
        result.ok("15-6: 로그인 실패 추적 동작")
    except Exception as e:
        result.fail("15-6: 로그인 실패 추적", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-7: 로그인 성공 시 실패 카운터 리셋
    try:
        al = _make_audit_logger()
        al.log(AuditEventType.LOGIN_FAILURE, "user", "fail", "/auth")
        al.log(AuditEventType.LOGIN_SUCCESS, "user", "login", "/auth")
        count = al._login_tracker.get_failure_count("user")
        assert count == 0
        result.ok("15-7: 로그인 성공 → 실패 리셋")
    except Exception as e:
        result.fail("15-7: 실패 리셋", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-8: details/metadata 전달
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al.log(
            AuditEventType.DATA_READ,
            "admin",
            "read",
            "user_profiles",
            details={"count": 100},
            metadata={"version": "1.0"},
            immediate=True,
        )
        entries = mem_storage.get_all()
        assert len(entries) >= 1
        assert entries[0].event.details.get("count") == 100
        result.ok("15-8: details/metadata 전달")
    except Exception as e:
        result.fail("15-8: details/metadata", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-9: 무결성 해시 체인
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        # 무결성 활성화
        al._integrity_enabled = True
        al._chain_hash_enabled = True

        al.log(AuditEventType.LOGIN_SUCCESS, "u1", "login", "/auth", immediate=True)
        al.log(AuditEventType.LOGOUT, "u1", "logout", "/auth", immediate=True)

        entries = mem_storage.get_all()
        assert len(entries) >= 2
        # 첫 항목의 entry_hash 존재
        assert len(entries[0].entry_hash) == 64
        # 두 번째 항목의 chain_hash = 첫 항목의 entry_hash
        assert entries[1].chain_hash == entries[0].entry_hash
        result.ok("15-9: 무결성 해시 체인")
    except Exception as e:
        result.fail("15-9: 해시 체인", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 15-10: verify_integrity
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al._integrity_enabled = True
        al._chain_hash_enabled = True

        for i in range(3):
            al.log(
                AuditEventType.DATA_READ,
                f"user{i}",
                "read",
                "/data",
                immediate=True,
            )

        entries = mem_storage.get_all()
        is_valid, errors = al.verify_integrity(entries=entries)
        assert is_valid is True, f"무결성 검증 실패: {errors}"
        assert len(errors) == 0
        result.ok("15-10: verify_integrity 통과")
    except Exception as e:
        result.fail("15-10: verify_integrity", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass


# =============================================================================
# [16] AuditLogger 관리 API
# =============================================================================
def test_audit_logger_api(result: TestResult) -> None:
    """AuditLogger 관리 API 검증."""
    print("\n[16] AuditLogger 관리 API")

    # 16-1: add_storage
    try:
        al = _make_audit_logger()
        initial_count = len(al._storages)
        mem = MemoryAuditStorage()
        al.add_storage(mem)
        assert len(al._storages) == initial_count + 1
        result.ok("16-1: add_storage")
    except Exception as e:
        result.fail("16-1: add_storage", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-2: add_alert_handler
    try:
        al = _make_audit_logger()
        initial_count = len(al._alert_handlers)
        handler = LogAlertHandler()
        al.add_alert_handler(handler)
        assert len(al._alert_handlers) == initial_count + 1
        result.ok("16-2: add_alert_handler")
    except Exception as e:
        result.fail("16-2: add_alert_handler", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-3: flush
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]

        # 버퍼에 넣기 (immediate=False, severity < CRITICAL)
        al.log(
            AuditEventType.DATA_READ,
            "user",
            "read",
            "/data",
            severity=AuditSeverity.INFO,
        )
        # flush 전 버퍼에 있을 수 있음
        al.flush()
        # flush 후 저장소에 기록됨
        time.sleep(0.1)  # 약간의 대기
        result.ok("16-3: flush 호출 성공")
    except Exception as e:
        result.fail("16-3: flush", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-4: query
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al.log(AuditEventType.LOGIN_SUCCESS, "u1", "login", "/auth", immediate=True)
        al.log(AuditEventType.DATA_READ, "u2", "read", "/data", immediate=True)
        results = al.query(limit=100)
        assert len(results) >= 2
        result.ok("16-4: query 동작")
    except Exception as e:
        result.fail("16-4: query", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-5: query 필터
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al.log(AuditEventType.LOGIN_SUCCESS, "u1", "login", "/auth", immediate=True)
        al.log(AuditEventType.DATA_READ, "u2", "read", "/data", immediate=True)
        results = al.query(event_types=[AuditEventType.LOGIN_SUCCESS])
        assert len(results) == 1
        result.ok("16-5: query 이벤트 필터")
    except Exception as e:
        result.fail("16-5: query 필터", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-6: get_stats 변화
    try:
        al = _make_audit_logger()
        stats_before = al.get_stats()
        al.log(AuditEventType.LOGIN_SUCCESS, "u1", "login", "/auth")
        stats_after = al.get_stats()
        assert stats_after["sequence_number"] == stats_before["sequence_number"] + 1
        result.ok("16-6: get_stats sequence_number 변화")
    except Exception as e:
        result.fail("16-6: get_stats 변화", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 16-7: close 정상 종료
    try:
        al = _make_audit_logger()
        al.log(AuditEventType.LOGIN_SUCCESS, "u1", "login", "/auth")
        al.close()
        # close 후에도 에러 없어야 함
        result.ok("16-7: close 정상 종료")
    except Exception as e:
        result.fail("16-7: close", str(e))

    # 16-8: close 후 상태
    try:
        al = _make_audit_logger()
        al.close()
        # _stop_flush가 set되어 있어야 함
        assert al._stop_flush.is_set()
        result.ok("16-8: close 후 _stop_flush set")
    except Exception as e:
        result.fail("16-8: close 후 상태", str(e))


# =============================================================================
# [17] 모듈 레벨 함수
# =============================================================================
def test_module_functions(result: TestResult) -> None:
    """모듈 레벨 함수 검증."""
    print("\n[17] 모듈 레벨 함수")

    # 17-1: get_audit_logger 초기 None
    try:
        _reset_global()
        assert get_audit_logger() is None
        result.ok("17-1: get_audit_logger 초기 None")
    except Exception as e:
        result.fail("17-1: 초기 None", str(e))

    # 17-2: set_audit_logger / get_audit_logger
    try:
        _reset_global()
        al = _make_audit_logger()
        set_audit_logger(al)
        assert get_audit_logger() is al
        result.ok("17-2: set/get_audit_logger")
    except Exception as e:
        result.fail("17-2: set/get", str(e))
    finally:
        _reset_global()
        try:
            al.close()
        except Exception:
            pass

    # 17-3: log_audit_event 로거 없을 때 → None
    try:
        _reset_global()
        ret = log_audit_event(
            AuditEventType.LOGIN_SUCCESS,
            "user",
            "login",
            "/auth",
        )
        assert ret is None
        result.ok("17-3: log_audit_event 로거 없음 → None")
    except Exception as e:
        result.fail("17-3: 로거 없음", str(e))

    # 17-4: log_audit_event 로거 있을 때
    try:
        _reset_global()
        al = _make_audit_logger()
        set_audit_logger(al)
        ret = log_audit_event(
            AuditEventType.DATA_CREATE,
            "admin",
            "create",
            "/users",
        )
        assert ret is not None
        assert isinstance(ret, str)
        result.ok("17-4: log_audit_event 로거 있음 → entry_id")
    except Exception as e:
        result.fail("17-4: 로거 있음", str(e))
    finally:
        _reset_global()
        try:
            al.close()
        except Exception:
            pass

    # 17-5: log_audit_event 추가 파라미터
    try:
        _reset_global()
        al = _make_audit_logger()
        set_audit_logger(al)
        ret = log_audit_event(
            AuditEventType.SECRET_ACCESS,
            "service",
            "access",
            "db_password",
            severity=AuditSeverity.WARNING,
            ip_address="10.0.0.1",
            details={"reason": "refresh"},
        )
        assert ret is not None
        result.ok("17-5: log_audit_event 추가 파라미터")
    except Exception as e:
        result.fail("17-5: 추가 파라미터", str(e))
    finally:
        _reset_global()
        try:
            al.close()
        except Exception:
            pass

    # 17-6: log_audit_event immediate=True
    try:
        _reset_global()
        al = _make_audit_logger()
        set_audit_logger(al)
        ret = log_audit_event(
            AuditEventType.INTRUSION_DETECTED,
            "attacker",
            "intrusion",
            "/admin",
            immediate=True,
        )
        assert ret is not None
        result.ok("17-6: log_audit_event immediate=True")
    except Exception as e:
        result.fail("17-6: immediate", str(e))
    finally:
        _reset_global()
        try:
            al.close()
        except Exception:
            pass


# =============================================================================
# [18] __all__ 내보내기 검증
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__all__ 내보내기 검증."""
    print("\n[18] __all__ 내보내기 검증")

    import core_foundation.security.audit_logger as mod
    import core_foundation.security as pkg

    # 18-1: audit_logger.__all__ 존재
    try:
        assert hasattr(mod, "__all__")
        assert isinstance(mod.__all__, list)
        assert len(mod.__all__) >= 20
        result.ok(f"18-1: audit_logger.__all__ = {len(mod.__all__)}개")
    except Exception as e:
        result.fail("18-1: __all__ 존재", str(e))

    # 18-2: __all__ 항목 실제 존재
    try:
        missing = [name for name in mod.__all__ if not hasattr(mod, name)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok("18-2: __all__ 모든 항목 실제 존재")
    except Exception as e:
        result.fail("18-2: 항목 존재", str(e))

    # 18-3: __init__.py에서 접근 가능
    try:
        assert hasattr(pkg, "AuditEventType")
        assert hasattr(pkg, "AuditLogger")
        assert hasattr(pkg, "log_audit_event")
        assert hasattr(pkg, "EVENT_DEFAULT_SEVERITY")
        result.ok("18-3: __init__.py 주요 항목 접근 가능")
    except Exception as e:
        result.fail("18-3: 항목 접근", str(e))

    # 18-4: __init__.py __all__ 전체 45개
    try:
        assert len(pkg.__all__) == 45, f"pkg.__all__ = {len(pkg.__all__)}"
        result.ok("18-4: __init__.py __all__ = 45개")
    except Exception as e:
        result.fail("18-4: 55개", str(e))


# =============================================================================
# [19] 엣지 케이스
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 검증."""
    print("\n[19] 엣지 케이스")

    # 19-1: 멀티스레드 로깅
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        errors = []

        def worker(thread_id):
            try:
                for i in range(20):
                    al.log(
                        AuditEventType.DATA_READ,
                        f"user_{thread_id}",
                        "read",
                        f"/data/{i}",
                        immediate=True,
                    )
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"오류: {errors[:3]}"
        # 4 threads × 20 logs = 80
        assert len(mem_storage.get_all()) == 80
        result.ok("19-1: 멀티스레드 로깅 80건")
    except Exception as e:
        result.fail("19-1: 멀티스레드", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 19-2: AuditEvent to_dict → from_dict 왕복
    try:
        original = AuditEvent(
            event_type=AuditEventType.DATA_UPDATE,
            actor="admin",
            action="update",
            resource="/users/123",
            result="success",
            severity=AuditSeverity.WARNING,
            ip_address="10.0.0.1",
            request_id="req-123",
            session_id="sess-456",
            details={"field": "email"},
            metadata={"version": "2.0"},
        )
        d = original.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.actor == original.actor
        assert restored.ip_address == original.ip_address
        assert restored.details == original.details
        result.ok("19-2: AuditEvent 왕복 변환")
    except Exception as e:
        result.fail("19-2: 왕복 변환", str(e))

    # 19-3: AuditLogEntry 왕복 변환
    try:
        evt = _make_event()
        entry = AuditLogEntry(id="roundtrip", event=evt, sequence_number=42)
        entry.entry_hash = entry.compute_hash("prev")
        d = entry.to_dict()
        restored = AuditLogEntry.from_dict(d)
        assert restored.id == "roundtrip"
        assert restored.sequence_number == 42
        result.ok("19-3: AuditLogEntry 왕복 변환")
    except Exception as e:
        result.fail("19-3: Entry 왕복", str(e))

    # 19-4: MemoryAuditStorage read limit/offset
    try:
        storage = MemoryAuditStorage()
        for i in range(10):
            storage.write(AuditLogEntry(id=f"lo{i}", event=_make_event()))
        results = storage.read(limit=3, offset=2)
        assert len(results) == 3
        result.ok("19-4: read limit=3, offset=2")
    except Exception as e:
        result.fail("19-4: limit/offset", str(e))

    # 19-5: 해시 변조 감지
    try:
        al = _make_audit_logger()
        mem_storage = MemoryAuditStorage()
        al._storages = [mem_storage]
        al._integrity_enabled = True
        al._chain_hash_enabled = True

        al.log(AuditEventType.DATA_READ, "u1", "read", "/data", immediate=True)
        al.log(AuditEventType.DATA_READ, "u2", "read", "/data", immediate=True)

        entries = mem_storage.get_all()
        # 첫 항목 해시 변조
        entries[0].entry_hash = "tampered_hash_value"
        is_valid, errors = al.verify_integrity(entries=entries)
        assert is_valid is False
        assert len(errors) >= 1
        result.ok("19-5: 해시 변조 감지")
    except Exception as e:
        result.fail("19-5: 변조 감지", str(e))
    finally:
        try:
            al.close()
        except Exception:
            pass

    # 19-6: CloudWatchAuditStorage / ElasticsearchAuditStorage 클래스 존재
    try:
        from core_foundation.security.audit_logger import (
            CloudWatchAuditStorage,
            ElasticsearchAuditStorage,
        )
        assert issubclass(CloudWatchAuditStorage, BaseAuditStorage)
        assert issubclass(ElasticsearchAuditStorage, BaseAuditStorage)
        result.ok("19-6: CloudWatch/ES 저장소 클래스 존재")
    except Exception as e:
        result.fail("19-6: SIEM 클래스", str(e))


# =============================================================================
# main
# =============================================================================
def main() -> None:
    """테스트 실행."""
    result = TestResult()

    test_constants(result)
    test_audit_event_type(result)
    test_audit_severity(result)
    test_default_severity(result)
    test_audit_event(result)
    test_audit_log_entry(result)
    test_memory_storage(result)
    test_base_classes(result)
    test_log_alert_handler(result)
    test_slack_handler(result)
    test_email_handler(result)
    test_webhook_handler(result)
    test_login_failure_tracker(result)
    test_audit_logger_init(result)
    test_audit_logger_log(result)
    test_audit_logger_api(result)
    test_module_functions(result)
    test_all_exports(result)
    test_edge_cases(result)

    result.summary()

    _reset_global()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
