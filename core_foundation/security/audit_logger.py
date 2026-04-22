# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: audit_logger.py
설명: 감사 로거 (체인 해싱)
      - 감사 이벤트 기록 (누가/무엇을/언제)
      - SHA-256 체인 해싱 (위변조 탐지)
      - 이벤트 카테고리별 분류
      - 이벤트 검색/필터링
      - 체인 무결성 검증
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import hashlib
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 감사 로그 수 (링버퍼)
MAX_AUDIT_ENTRIES: Final[int] = 10000

# 최대 콜백 수
MAX_CALLBACKS: Final[int] = 20

# 체인 시작 해시 (제네시스)
GENESIS_HASH: Final[str] = "0" * 64

# 해시 알고리즘
HASH_ALGORITHM: Final[str] = "sha256"


# =============================================================================
# 감사 카테고리 Enum
# =============================================================================

@unique
class AuditCategory(Enum):
    """감사 이벤트 카테고리.

    Members:
        AUTH: 인증/인가 관련
        DATA: 데이터 접근/변경
        CONFIG: 설정 변경
        SYSTEM: 시스템 이벤트
        ANALYSIS: 분석 작업
        SECURITY: 보안 관련
    """

    AUTH = "auth"
    DATA = "data"
    CONFIG = "config"
    SYSTEM = "system"
    ANALYSIS = "analysis"
    SECURITY = "security"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP: dict[AuditCategory, str] = {
            AuditCategory.AUTH: "인증/인가",
            AuditCategory.DATA: "데이터",
            AuditCategory.CONFIG: "설정",
            AuditCategory.SYSTEM: "시스템",
            AuditCategory.ANALYSIS: "분석",
            AuditCategory.SECURITY: "보안",
        }
        return _MAP[self]


# =============================================================================
# 감사 심각도 Enum
# =============================================================================

@unique
class AuditSeverity(Enum):
    """감사 이벤트 심각도.

    Members:
        INFO: 정보
        WARNING: 경고
        CRITICAL: 심각
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP: dict[AuditSeverity, str] = {
            AuditSeverity.INFO: "정보",
            AuditSeverity.WARNING: "경고",
            AuditSeverity.CRITICAL: "심각",
        }
        return _MAP[self]


# =============================================================================
# 감사 이벤트
# =============================================================================

@dataclass(slots=True)
class AuditEvent:
    """감사 이벤트.

    Attributes:
        sequence: 순서 번호
        timestamp: 이벤트 시각 (epoch, time.time())
        category: 카테고리
        severity: 심각도
        actor: 수행자 (사용자/시스템)
        action: 수행 행위
        resource: 대상 리소스
        details: 상세 내용
        result: 결과 (성공/실패)
        ip_address: IP 주소 (선택)
        previous_hash: 이전 이벤트 해시
        event_hash: 이 이벤트의 해시
    """

    sequence: int
    timestamp: float
    category: AuditCategory
    severity: AuditSeverity
    actor: str
    action: str
    resource: str = ""
    details: str = ""
    result: str = "success"
    ip_address: str = ""
    previous_hash: str = ""
    event_hash: str = ""

    def __repr__(self) -> str:
        return (
            f"AuditEvent(#{self.sequence}, "
            f"{self.category.value}/{self.severity.value}, "
            f"actor='{self.actor}', "
            f"action='{self.action}')"
        )


# =============================================================================
# 타입 정의
# =============================================================================

# 감사 이벤트 콜백: (event) -> None
AuditEventCallback = Callable[[AuditEvent], None]


# =============================================================================
# 해시 유틸리티
# =============================================================================

def compute_event_hash(event: AuditEvent) -> str:
    """이벤트 해시 계산 (SHA-256).

    해시 대상: sequence + timestamp + category + severity + actor
    + action + resource + details + result + previous_hash

    Args:
        event: 감사 이벤트

    Returns:
        SHA-256 해시 (hex)
    """
    payload = (
        f"{event.sequence}|"
        f"{event.timestamp}|"
        f"{event.category.value}|"
        f"{event.severity.value}|"
        f"{event.actor}|"
        f"{event.action}|"
        f"{event.resource}|"
        f"{event.details}|"
        f"{event.result}|"
        f"{event.previous_hash}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# =============================================================================
# 핵심 클래스: AuditLogger
# =============================================================================

class AuditLogger:
    """감사 로거.

    감사 이벤트를 체인 해싱으로 기록하고, 무결성을 검증한다.
    각 이벤트는 이전 이벤트의 해시를 포함하여 위변조 시 탐지된다.

    사용 예시::

        logger = AuditLogger.get_instance()

        # 이벤트 기록
        logger.log(
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor="user@example.com",
            action="login",
            details="로그인 성공",
        )

        # 분석 작업 기록
        logger.log(
            category=AuditCategory.ANALYSIS,
            severity=AuditSeverity.INFO,
            actor="system",
            action="video_analysis",
            resource="game_20260320.mp4",
            details="경기 분석 시작",
        )

        # 체인 무결성 검증
        is_valid, broken_at = logger.verify_chain()

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: AuditLogger | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._entries: deque[AuditEvent] = deque(maxlen=MAX_AUDIT_ENTRIES)
        self._sequence = 0
        self._last_hash = GENESIS_HASH
        self._callbacks: list[AuditEventCallback] = []
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> AuditLogger:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 이벤트 기록
    # =========================================================================

    def log(
        self,
        *,
        category: AuditCategory,
        severity: AuditSeverity = AuditSeverity.INFO,
        actor: str,
        action: str,
        resource: str = "",
        details: str = "",
        result: str = "success",
        ip_address: str = "",
    ) -> AuditEvent:
        """감사 이벤트 기록.

        Args:
            category: 카테고리
            severity: 심각도
            actor: 수행자
            action: 수행 행위
            resource: 대상 리소스
            details: 상세 내용
            result: 결과
            ip_address: IP 주소

        Returns:
            기록된 AuditEvent
        """
        with self._lock:
            self._sequence += 1

            event = AuditEvent(
                sequence=self._sequence,
                timestamp=time.time(),
                category=category,
                severity=severity,
                actor=actor,
                action=action,
                resource=resource,
                details=details,
                result=result,
                ip_address=ip_address,
                previous_hash=self._last_hash,
            )

            # 해시 계산 및 설정
            event.event_hash = compute_event_hash(event)
            self._last_hash = event.event_hash

            self._entries.append(event)
            callbacks = list(self._callbacks)

        # 콜백 실행 (lock 밖, 예외 격리)
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                pass

        return event

    # =========================================================================
    # 편의 메서드
    # =========================================================================

    def log_auth(
        self,
        actor: str,
        action: str,
        *,
        severity: AuditSeverity = AuditSeverity.INFO,
        details: str = "",
        result: str = "success",
    ) -> AuditEvent:
        """인증/인가 이벤트 기록."""
        return self.log(
            category=AuditCategory.AUTH,
            severity=severity,
            actor=actor,
            action=action,
            details=details,
            result=result,
        )

    def log_security(
        self,
        actor: str,
        action: str,
        *,
        severity: AuditSeverity = AuditSeverity.WARNING,
        details: str = "",
        result: str = "",
    ) -> AuditEvent:
        """보안 이벤트 기록."""
        return self.log(
            category=AuditCategory.SECURITY,
            severity=severity,
            actor=actor,
            action=action,
            details=details,
            result=result,
        )

    # =========================================================================
    # 체인 검증
    # =========================================================================

    def verify_chain(self) -> tuple[bool, int]:
        """체인 무결성 검증.

        각 이벤트의 해시를 재계산하여 위변조 여부를 확인한다.

        Returns:
            (무결성 여부, 위변조 발견 시퀀스 번호 / 0이면 정상)
        """
        with self._lock:
            entries = list(self._entries)

        expected_prev = GENESIS_HASH
        for event in entries:
            # 이전 해시 검증
            if event.previous_hash != expected_prev:
                return False, event.sequence

            # 현재 해시 재계산
            computed = compute_event_hash(event)
            if computed != event.event_hash:
                return False, event.sequence

            expected_prev = event.event_hash

        return True, 0

    # =========================================================================
    # 조회
    # =========================================================================

    def get_entries(
        self,
        *,
        category: AuditCategory | None = None,
        severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """감사 이벤트 조회 (필터링).

        Args:
            category: 카테고리 필터
            severity: 심각도 필터
            actor: 수행자 필터
            limit: 최대 반환 수

        Returns:
            필터링된 이벤트 리스트 (최근 순)
        """
        with self._lock:
            entries = list(self._entries)

        # 필터링
        if category is not None:
            entries = [e for e in entries if e.category == category]
        if severity is not None:
            entries = [e for e in entries if e.severity == severity]
        if actor is not None:
            entries = [e for e in entries if e.actor == actor]

        # 최근 순, limit 적용
        return list(reversed(entries[-limit:]))

    def get_last(self, count: int = 10) -> list[AuditEvent]:
        """최근 이벤트 조회.

        Args:
            count: 조회 수

        Returns:
            최근 이벤트 리스트
        """
        with self._lock:
            entries = list(self._entries)
        return list(reversed(entries[-count:]))

    def get_by_sequence(self, sequence: int) -> AuditEvent | None:
        """시퀀스 번호로 이벤트 조회.

        Args:
            sequence: 시퀀스 번호

        Returns:
            AuditEvent 또는 None
        """
        with self._lock:
            for entry in self._entries:
                if entry.sequence == sequence:
                    return entry
            return None

    # =========================================================================
    # 콜백
    # =========================================================================

    def add_callback(self, callback: AuditEventCallback) -> bool:
        """이벤트 콜백 등록.

        Args:
            callback: (AuditEvent) -> None

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if len(self._callbacks) >= MAX_CALLBACKS:
                return False
            self._callbacks.append(callback)
            return True

    def remove_callback(self, callback: AuditEventCallback) -> bool:
        """이벤트 콜백 해제.

        Returns:
            해제 성공 여부
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def entry_count(self) -> int:
        """현재 기록된 이벤트 수."""
        with self._lock:
            return len(self._entries)

    @property
    def last_sequence(self) -> int:
        """마지막 시퀀스 번호."""
        with self._lock:
            return self._sequence

    @property
    def last_hash(self) -> str:
        """마지막 이벤트 해시."""
        with self._lock:
            return self._last_hash

    def clear(self) -> int:
        """전체 이벤트 삭제.

        Returns:
            삭제된 수
        """
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._sequence = 0
            self._last_hash = GENESIS_HASH
            return count

    def category_counts(self) -> dict[AuditCategory, int]:
        """카테고리별 이벤트 수.

        Returns:
            카테고리 → 이벤트 수
        """
        with self._lock:
            counts: dict[AuditCategory, int] = {}
            for entry in self._entries:
                counts[entry.category] = counts.get(entry.category, 0) + 1
            return counts

    def __repr__(self) -> str:
        return (
            f"AuditLogger(entries={self.entry_count}, "
            f"last_seq={self.last_sequence})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "AuditCategory",
    "AuditSeverity",
    # 데이터 클래스
    "AuditEvent",
    # 타입
    "AuditEventCallback",
    # 유틸리티
    "compute_event_hash",
    # 핵심 클래스
    "AuditLogger",
    # 상수
    "MAX_AUDIT_ENTRIES",
    "MAX_CALLBACKS",
    "GENESIS_HASH",
    "HASH_ALGORITHM",
]

__version__ = "1.0.0"
