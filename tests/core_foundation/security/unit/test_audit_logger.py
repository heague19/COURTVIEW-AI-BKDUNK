# -*- coding: utf-8 -*-
"""security/audit_logger.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import threading

import pytest

from core_foundation.security.audit_logger import (
    GENESIS_HASH,
    HASH_ALGORITHM,
    MAX_AUDIT_ENTRIES,
    MAX_CALLBACKS,
    AuditCategory,
    AuditEvent,
    AuditEventCallback,
    AuditLogger,
    AuditSeverity,
    compute_event_hash,
)


@pytest.fixture(autouse=True)
def reset_logger():
    AuditLogger.reset()
    yield
    AuditLogger.reset()


# =============================================================================
# AuditCategory 검증
# =============================================================================

class TestAuditCategory:
    def test_member_count(self):
        assert len(AuditCategory) == 6

    def test_values(self):
        assert AuditCategory.AUTH.value == "auth"
        assert AuditCategory.DATA.value == "data"
        assert AuditCategory.CONFIG.value == "config"
        assert AuditCategory.SYSTEM.value == "system"
        assert AuditCategory.ANALYSIS.value == "analysis"
        assert AuditCategory.SECURITY.value == "security"

    def test_to_korean(self):
        assert AuditCategory.AUTH.to_korean() == "인증/인가"
        assert AuditCategory.ANALYSIS.to_korean() == "분석"
        assert AuditCategory.SECURITY.to_korean() == "보안"


# =============================================================================
# AuditSeverity 검증
# =============================================================================

class TestAuditSeverity:
    def test_member_count(self):
        assert len(AuditSeverity) == 3

    def test_values(self):
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.CRITICAL.value == "critical"

    def test_to_korean(self):
        assert AuditSeverity.INFO.to_korean() == "정보"
        assert AuditSeverity.WARNING.to_korean() == "경고"
        assert AuditSeverity.CRITICAL.to_korean() == "심각"


# =============================================================================
# AuditEvent 검증
# =============================================================================

class TestAuditEvent:
    def test_slots(self):
        assert hasattr(AuditEvent, "__slots__")

    def test_repr(self):
        e = AuditEvent(
            sequence=1,
            timestamp=0.0,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="user",
            action="login",
        )
        text = repr(e)
        assert "#1" in text
        assert "auth" in text
        assert "user" in text


# =============================================================================
# compute_event_hash 검증
# =============================================================================

class TestComputeEventHash:
    def test_deterministic(self):
        e = AuditEvent(
            sequence=1,
            timestamp=1000.0,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="user",
            action="login",
            previous_hash=GENESIS_HASH,
        )
        h1 = compute_event_hash(e)
        h2 = compute_event_hash(e)
        assert h1 == h2

    def test_different_content_different_hash(self):
        e1 = AuditEvent(
            sequence=1,
            timestamp=1000.0,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="user1",
            action="login",
            previous_hash=GENESIS_HASH,
        )
        e2 = AuditEvent(
            sequence=1,
            timestamp=1000.0,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="user2",
            action="login",
            previous_hash=GENESIS_HASH,
        )
        assert compute_event_hash(e1) != compute_event_hash(e2)

    def test_hash_length(self):
        e = AuditEvent(
            sequence=1,
            timestamp=0.0,
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="u",
            action="a",
            previous_hash=GENESIS_HASH,
        )
        assert len(compute_event_hash(e)) == 64  # SHA-256 hex


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        l1 = AuditLogger.get_instance()
        l2 = AuditLogger.get_instance()
        assert l1 is l2

    def test_reset(self):
        l1 = AuditLogger.get_instance()
        AuditLogger.reset()
        l2 = AuditLogger.get_instance()
        assert l1 is not l2


# =============================================================================
# 이벤트 기록
# =============================================================================

class TestLogEvent:
    def test_log_basic(self):
        logger = AuditLogger.get_instance()
        event = logger.log(
            category=AuditCategory.AUTH,
            actor="admin",
            action="login",
        )
        assert event.sequence == 1
        assert event.category == AuditCategory.AUTH
        assert event.actor == "admin"
        assert event.action == "login"
        assert event.severity == AuditSeverity.INFO  # 기본값

    def test_log_with_details(self):
        logger = AuditLogger.get_instance()
        event = logger.log(
            category=AuditCategory.ANALYSIS,
            severity=AuditSeverity.WARNING,
            actor="system",
            action="video_analysis",
            resource="game.mp4",
            details="분석 실패",
            result="failure",
            ip_address="127.0.0.1",
        )
        assert event.resource == "game.mp4"
        assert event.result == "failure"
        assert event.ip_address == "127.0.0.1"

    def test_log_increments_sequence(self):
        logger = AuditLogger.get_instance()
        e1 = logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        e2 = logger.log(category=AuditCategory.AUTH, actor="u", action="b")
        assert e2.sequence == e1.sequence + 1

    def test_log_has_hash(self):
        logger = AuditLogger.get_instance()
        event = logger.log(
            category=AuditCategory.AUTH,
            actor="u",
            action="a",
        )
        assert len(event.event_hash) == 64
        assert event.previous_hash == GENESIS_HASH

    def test_log_chain_hashing(self):
        logger = AuditLogger.get_instance()
        e1 = logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        e2 = logger.log(category=AuditCategory.AUTH, actor="u", action="b")
        assert e2.previous_hash == e1.event_hash


# =============================================================================
# 편의 메서드
# =============================================================================

class TestConvenienceMethods:
    def test_log_auth(self):
        logger = AuditLogger.get_instance()
        event = logger.log_auth("admin", "login", details="테스트")
        assert event.category == AuditCategory.AUTH
        assert event.actor == "admin"

    def test_log_security(self):
        logger = AuditLogger.get_instance()
        event = logger.log_security("system", "intrusion_detected")
        assert event.category == AuditCategory.SECURITY
        assert event.severity == AuditSeverity.WARNING  # 기본값


# =============================================================================
# 체인 검증
# =============================================================================

class TestChainVerification:
    def test_valid_chain(self):
        logger = AuditLogger.get_instance()
        for i in range(5):
            logger.log(category=AuditCategory.AUTH, actor="u", action=f"a{i}")

        valid, broken_at = logger.verify_chain()
        assert valid is True
        assert broken_at == 0

    def test_empty_chain_valid(self):
        logger = AuditLogger.get_instance()
        valid, broken_at = logger.verify_chain()
        assert valid is True
        assert broken_at == 0

    def test_tampered_hash_detected(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        logger.log(category=AuditCategory.AUTH, actor="u", action="b")
        logger.log(category=AuditCategory.AUTH, actor="u", action="c")

        # 두 번째 이벤트의 해시 위변조
        entries = list(logger._entries)
        entries[1].event_hash = "tampered" + "0" * 56

        valid, broken_at = logger.verify_chain()
        assert valid is False
        assert broken_at == 2  # 세 번째에서 이전 해시 불일치

    def test_tampered_content_detected(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")

        # 내용 위변조
        entries = list(logger._entries)
        entries[0].actor = "hacker"

        valid, broken_at = logger.verify_chain()
        assert valid is False
        assert broken_at == 1


# =============================================================================
# 조회
# =============================================================================

class TestQuery:
    def test_get_entries_all(self):
        logger = AuditLogger.get_instance()
        for i in range(5):
            logger.log(category=AuditCategory.AUTH, actor="u", action=f"a{i}")

        entries = logger.get_entries()
        assert len(entries) == 5

    def test_get_entries_by_category(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="login")
        logger.log(category=AuditCategory.DATA, actor="u", action="read")
        logger.log(category=AuditCategory.AUTH, actor="u", action="logout")

        entries = logger.get_entries(category=AuditCategory.AUTH)
        assert len(entries) == 2

    def test_get_entries_by_severity(self):
        logger = AuditLogger.get_instance()
        logger.log(
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="u",
            action="a",
        )
        logger.log(
            category=AuditCategory.AUTH,
            severity=AuditSeverity.CRITICAL,
            actor="u",
            action="b",
        )

        entries = logger.get_entries(severity=AuditSeverity.CRITICAL)
        assert len(entries) == 1

    def test_get_entries_by_actor(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="admin", action="a")
        logger.log(category=AuditCategory.AUTH, actor="user", action="b")

        entries = logger.get_entries(actor="admin")
        assert len(entries) == 1

    def test_get_entries_limit(self):
        logger = AuditLogger.get_instance()
        for i in range(10):
            logger.log(category=AuditCategory.AUTH, actor="u", action=f"a{i}")

        entries = logger.get_entries(limit=3)
        assert len(entries) == 3

    def test_get_last(self):
        logger = AuditLogger.get_instance()
        for i in range(5):
            logger.log(category=AuditCategory.AUTH, actor="u", action=f"a{i}")

        last = logger.get_last(2)
        assert len(last) == 2
        assert last[0].sequence > last[1].sequence  # 최근 순

    def test_get_by_sequence(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="first")
        logger.log(category=AuditCategory.AUTH, actor="u", action="second")

        event = logger.get_by_sequence(1)
        assert event is not None
        assert event.action == "first"

    def test_get_by_sequence_missing(self):
        logger = AuditLogger.get_instance()
        assert logger.get_by_sequence(999) is None


# =============================================================================
# 콜백
# =============================================================================

class TestCallbacks:
    def test_callback_called(self):
        logger = AuditLogger.get_instance()
        events: list[AuditEvent] = []

        logger.add_callback(lambda e: events.append(e))
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")

        assert len(events) == 1
        assert events[0].action == "a"

    def test_callback_exception_isolation(self):
        logger = AuditLogger.get_instance()

        def bad_cb(e: AuditEvent):
            raise RuntimeError("콜백 폭발")

        logger.add_callback(bad_cb)
        event = logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        assert event.sequence == 1

    def test_remove_callback(self):
        logger = AuditLogger.get_instance()

        def cb(e: AuditEvent):
            pass

        logger.add_callback(cb)
        assert logger.remove_callback(cb) is True
        assert logger.remove_callback(cb) is False

    def test_max_callbacks(self):
        logger = AuditLogger.get_instance()
        for _ in range(MAX_CALLBACKS):
            logger.add_callback(lambda e: None)

        assert logger.add_callback(lambda e: None) is False


# =============================================================================
# 관리
# =============================================================================

class TestManagement:
    def test_entry_count(self):
        logger = AuditLogger.get_instance()
        assert logger.entry_count == 0
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        assert logger.entry_count == 1

    def test_last_sequence(self):
        logger = AuditLogger.get_instance()
        assert logger.last_sequence == 0
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        assert logger.last_sequence == 1

    def test_last_hash(self):
        logger = AuditLogger.get_instance()
        assert logger.last_hash == GENESIS_HASH
        event = logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        assert logger.last_hash == event.event_hash

    def test_clear(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        logger.log(category=AuditCategory.AUTH, actor="u", action="b")
        count = logger.clear()
        assert count == 2
        assert logger.entry_count == 0
        assert logger.last_sequence == 0
        assert logger.last_hash == GENESIS_HASH

    def test_category_counts(self):
        logger = AuditLogger.get_instance()
        logger.log(category=AuditCategory.AUTH, actor="u", action="a")
        logger.log(category=AuditCategory.AUTH, actor="u", action="b")
        logger.log(category=AuditCategory.DATA, actor="u", action="c")

        counts = logger.category_counts()
        assert counts[AuditCategory.AUTH] == 2
        assert counts[AuditCategory.DATA] == 1


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_log(self):
        logger = AuditLogger.get_instance()
        errors: list[Exception] = []

        def log_many(prefix: str):
            try:
                for i in range(20):
                    logger.log(
                        category=AuditCategory.AUTH,
                        actor=prefix,
                        action=f"action_{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=log_many, args=(f"t{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert logger.entry_count == 100

        # 체인 무결성 유지
        valid, _ = logger.verify_chain()
        assert valid is True


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        logger = AuditLogger.get_instance()
        text = repr(logger)
        assert "entries=" in text
        assert "last_seq=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_entries(self):
        assert MAX_AUDIT_ENTRIES == 10000

    def test_max_callbacks(self):
        assert MAX_CALLBACKS == 20

    def test_genesis_hash(self):
        assert GENESIS_HASH == "0" * 64

    def test_hash_algorithm(self):
        assert HASH_ALGORITHM == "sha256"


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.security.audit_logger as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.security.audit_logger as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.security.audit_logger as mod
        assert mod.__version__ == "1.0.0"
