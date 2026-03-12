# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: audit_logger.py
설명: 감사 로그 기록 - 보안 이벤트, 접근 기록, 변조 방지

작성자: SPOIN_COURTVIEW
버전: 1.0.0
최종 수정: 2026-03-12

주요 기능:
    - 감사 이벤트 기록 (인증, 권한, 데이터 접근, 설정 변경, 시스템, 보안)
    - 다중 저장소 지원 (파일, 데이터베이스, SIEM)
    - 체인 해시 기반 무결성 보장
    - 실시간 알림 (보안 위협 감지)
    - 이벤트 필터링 및 샘플링
    - 로그 로테이션 및 압축
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 무결성: SHA-256 체인 해시
    - 확장성: 저장소 플러그인 방식
    - 성능: 비동기 배치 처리 지원

감사 이벤트 타입:
    - authentication: 인증 관련 (로그인, 로그아웃, 토큰)
    - authorization: 권한 관련 (접근 허용/거부)
    - data_access: 데이터 접근 (CRUD)
    - configuration: 설정 변경
    - system: 시스템 이벤트
    - security: 보안 이벤트 (침입 감지, 의심 활동)

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    audit_logger = AuditLogger(config_loader, metrics_collector)

    # 감사 이벤트 기록
    audit_logger.log(
        event_type=AuditEventType.LOGIN_SUCCESS,
        actor="user@example.com",
        action="login",
        resource="/api/auth/login",
        result="success"
    )

    # 헬퍼 함수 사용
    log_audit_event(
        event_type=AuditEventType.DATA_READ,
        actor="admin",
        action="read",
        resource="user_profiles"
    )
"""

from __future__ import annotations

__version__: str = "1.0.0"

# ============================================================
# 표준 라이브러리
# ============================================================
import json
import logging
import os
import gzip
import hashlib
import threading
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, unique
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ============================================================
# shared 임포트
# ============================================================
# (미사용 임포트 제거됨 - v2.6.0)
# ErrorCode: 도메인 예외 미정의로 미사용
# EventCategory, EventType: AuditEventType 자체 정의 사용
# get_current_timestamp, get_iso_timestamp: datetime 직접 사용

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.metrics import MetricsCollector

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수 정의
# ============================================================
# 기본 로그 디렉토리
DEFAULT_LOG_DIR: str = "logs/audit"

# 기본 최대 파일 수
DEFAULT_MAX_FILES: int = 90

# 기본 버퍼 크기
DEFAULT_BUFFER_SIZE: int = 100

# 기본 플러시 간격 (초)
DEFAULT_FLUSH_INTERVAL: float = 10.0

# 기본 샘플링 비율
DEFAULT_SAMPLE_RATE: float = 0.1

# 해시 알고리즘
HASH_ALGORITHM: str = "sha256"

# 초기 체인 해시 값
INITIAL_CHAIN_HASH: str = "COURTVIEW_AUDIT_CHAIN_GENESIS"

# 로그인 실패 임계값
DEFAULT_LOGIN_FAILURE_THRESHOLD: int = 5

# 임계값 윈도우 (분)
DEFAULT_THRESHOLD_WINDOW_MINUTES: int = 15


# ============================================================
# 감사 이벤트 타입 Enum
# ============================================================
@unique
class AuditEventType(Enum):
    """
    감사 이벤트 타입 열거형.

    보안 및 감사 관련 모든 이벤트 유형을 정의합니다.
    YAML 설정의 event_types와 동기화됩니다.
    """

    # ==================== 인증 이벤트 ====================
    LOGIN_SUCCESS = "authentication.login_success"
    LOGIN_FAILURE = "authentication.login_failure"
    LOGOUT = "authentication.logout"
    TOKEN_REFRESH = "authentication.token_refresh"
    PASSWORD_CHANGE = "authentication.password_change"
    MFA_SUCCESS = "authentication.mfa_success"
    MFA_FAILURE = "authentication.mfa_failure"
    SESSION_EXPIRED = "authentication.session_expired"

    # ==================== 권한 이벤트 ====================
    ACCESS_GRANTED = "authorization.access_granted"
    ACCESS_DENIED = "authorization.access_denied"
    PERMISSION_CHANGE = "authorization.permission_change"
    ROLE_CHANGE = "authorization.role_change"
    PRIVILEGE_ESCALATION = "authorization.privilege_escalation"

    # ==================== 데이터 접근 이벤트 ====================
    DATA_READ = "data_access.data_read"
    DATA_CREATE = "data_access.data_create"
    DATA_UPDATE = "data_access.data_update"
    DATA_DELETE = "data_access.data_delete"
    DATA_EXPORT = "data_access.data_export"
    DATA_IMPORT = "data_access.data_import"
    BULK_OPERATION = "data_access.bulk_operation"

    # ==================== 설정 변경 이벤트 ====================
    CONFIG_CHANGE = "configuration.config_change"
    SECRET_ACCESS = "configuration.secret_access"
    SECRET_ROTATION = "configuration.secret_rotation"
    API_KEY_CREATED = "configuration.api_key_created"
    API_KEY_REVOKED = "configuration.api_key_revoked"

    # ==================== 시스템 이벤트 ====================
    SERVICE_START = "system.service_start"
    SERVICE_STOP = "system.service_stop"
    HEALTH_CHECK = "system.health_check"
    ERROR_OCCURRED = "system.error_occurred"
    MAINTENANCE_MODE = "system.maintenance_mode"
    BACKUP_STARTED = "system.backup_started"
    BACKUP_COMPLETED = "system.backup_completed"

    # ==================== 보안 이벤트 ====================
    INTRUSION_DETECTED = "security.intrusion_detected"
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    INVALID_TOKEN = "security.invalid_token"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    BRUTE_FORCE_DETECTED = "security.brute_force_detected"
    IP_BLOCKED = "security.ip_blocked"
    ANOMALY_DETECTED = "security.anomaly_detected"

    @property
    def category(self) -> str:
        """이벤트 카테고리 반환."""
        return self.value.split(".")[0]

    @property
    def action(self) -> str:
        """이벤트 액션 반환."""
        return self.value.split(".", 1)[1] if "." in self.value else self.value

    @classmethod
    def from_string(cls, value: str) -> AuditEventType | None:
        """문자열에서 이벤트 타입 생성."""
        for event_type in cls:
            if event_type.value == value:
                return event_type
        return None

    @classmethod
    def get_by_category(cls, category: str) -> list[AuditEventType]:
        """카테고리별 이벤트 타입 목록 반환."""
        return [et for et in cls if et.category == category]


# ============================================================
# 감사 심각도 Enum
# ============================================================
@unique
class AuditSeverity(Enum):
    """
    감사 심각도 열거형.

    감사 이벤트의 심각도를 나타냅니다.
    각 심각도는 고유한 숫자 값과 보관 기간을 가집니다.
    """

    DEBUG = (10, 7, "debug")        # 디버그: 7일 보관
    INFO = (20, 30, "info")         # 정보: 30일 보관
    WARNING = (30, 90, "warning")   # 경고: 90일 보관
    ERROR = (40, 180, "error")      # 에러: 180일 보관
    CRITICAL = (50, 365, "critical")  # 치명적: 365일 보관

    def __init__(self, value: int, retain_days: int, name_str: str) -> None:
        self._value_ = value
        self._retain_days = retain_days
        self._name_str = name_str

    @property
    def retain_days(self) -> int:
        """보관 기간(일) 반환."""
        return self._retain_days

    @property
    def name_str(self) -> str:
        """심각도 이름 문자열 반환."""
        return self._name_str

    def __ge__(self, other: "AuditSeverity") -> bool:
        return self.value >= other.value

    def __gt__(self, other: "AuditSeverity") -> bool:
        return self.value > other.value

    def __le__(self, other: "AuditSeverity") -> bool:
        return self.value <= other.value

    def __lt__(self, other: "AuditSeverity") -> bool:
        return self.value < other.value

    @classmethod
    def from_string(cls, value: str) -> AuditSeverity | None:
        """문자열에서 심각도 생성."""
        value_lower = value.lower()
        for severity in cls:
            if severity.name_str == value_lower or severity.name.lower() == value_lower:
                return severity
        return None


# ============================================================
# 이벤트 타입별 기본 심각도 매핑
# ============================================================
EVENT_DEFAULT_SEVERITY: dict[str, AuditSeverity] = {
    "authentication": AuditSeverity.INFO,
    "authorization": AuditSeverity.WARNING,
    "data_access": AuditSeverity.INFO,
    "configuration": AuditSeverity.WARNING,
    "system": AuditSeverity.INFO,
    "security": AuditSeverity.CRITICAL,
}


# ============================================================
# 감사 이벤트 데이터클래스
# ============================================================
@dataclass(slots=True)
class AuditEvent:
    """
    감사 이벤트 데이터 클래스.

    감사 이벤트의 핵심 정보를 담습니다.

    Attributes:
        event_type: 이벤트 타입
        actor: 행위자 (사용자 ID, 서비스명 등)
        action: 수행한 동작
        resource: 대상 리소스
        result: 결과 (success, failure, error 등)
        severity: 심각도
        timestamp: 발생 시간
        request_id: 요청 ID
        session_id: 세션 ID
        ip_address: IP 주소
        user_agent: 사용자 에이전트
        details: 상세 정보
        metadata: 메타데이터
    """

    event_type: AuditEventType
    actor: str
    action: str
    resource: str
    result: str = "success"
    severity: AuditSeverity | None = None
    timestamp: datetime | None = None
    request_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 타임스탬프 설정
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

        # 심각도 설정
        if self.severity is None:
            category = self.event_type.category
            self.severity = EVENT_DEFAULT_SEVERITY.get(category, AuditSeverity.INFO)

        # 보안 이벤트 심각도 상향
        if self.event_type.category == "security":
            if self.severity < AuditSeverity.WARNING:
                self.severity = AuditSeverity.WARNING

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "event_type": self.event_type.value,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "severity": self.severity.name_str if self.severity else "info",
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        """딕셔너리에서 생성."""
        event_type = AuditEventType.from_string(data.get("event_type", ""))
        if event_type is None:
            raise ValueError(f"알 수 없는 이벤트 타입: {data.get('event_type')}")

        severity = AuditSeverity.from_string(data.get("severity", "info"))

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            event_type=event_type,
            actor=data.get("actor", "unknown"),
            action=data.get("action", ""),
            resource=data.get("resource", ""),
            result=data.get("result", "success"),
            severity=severity,
            timestamp=timestamp,
            request_id=data.get("request_id"),
            session_id=data.get("session_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            details=data.get("details", {}),
            metadata=data.get("metadata", {}),
        )


# ============================================================
# 감사 로그 항목 데이터클래스
# ============================================================
@dataclass(slots=True)
class AuditLogEntry:
    """
    감사 로그 항목 데이터 클래스.

    저장소에 기록되는 감사 로그의 완전한 형태입니다.
    무결성 해시와 체인 해시를 포함합니다.

    Attributes:
        id: 고유 ID
        event: 감사 이벤트
        entry_hash: 항목 해시 (무결성)
        chain_hash: 체인 해시 (이전 로그 연결)
        created_at: 생성 시간
        sequence_number: 시퀀스 번호
    """

    id: str
    event: AuditEvent
    entry_hash: str = ""
    chain_hash: str = ""
    created_at: datetime | None = None
    sequence_number: int = 0

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if not self.id:
            self.id = str(uuid.uuid4())

        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    def compute_hash(self, previous_hash: str = "") -> str:
        """
        항목 해시 계산.

        Args:
            previous_hash: 이전 로그의 해시 (체인 해시용)

        Returns:
            계산된 해시 값
        """
        # 해시 대상 데이터 구성
        hash_data = {
            "id": self.id,
            "event": self.event.to_dict(),
            "sequence_number": self.sequence_number,
            "previous_hash": previous_hash,
        }

        # JSON 직렬화 (정렬된 키)
        data_str = json.dumps(hash_data, sort_keys=True, default=str)

        # SHA-256 해시 계산
        hash_obj = hashlib.sha256(data_str.encode("utf-8"))
        return hash_obj.hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "id": self.id,
            "event": self.event.to_dict(),
            "entry_hash": self.entry_hash,
            "chain_hash": self.chain_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
        """딕셔너리에서 생성."""
        event = AuditEvent.from_dict(data.get("event", {}))

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return cls(
            id=data.get("id", ""),
            event=event,
            entry_hash=data.get("entry_hash", ""),
            chain_hash=data.get("chain_hash", ""),
            created_at=created_at,
            sequence_number=data.get("sequence_number", 0),
        )

    def verify_integrity(self, previous_hash: str = "") -> bool:
        """
        무결성 검증.

        Args:
            previous_hash: 이전 로그의 해시

        Returns:
            무결성 검증 성공 여부
        """
        expected_hash = self.compute_hash(previous_hash)
        return self.entry_hash == expected_hash


# ============================================================
# 저장소 추상 기본 클래스
# ============================================================
class BaseAuditStorage(ABC):
    """
    감사 로그 저장소 추상 기본 클래스.

    모든 저장소 구현체가 상속해야 하는 기본 클래스입니다.
    """

    @abstractmethod
    def write(self, entry: AuditLogEntry) -> bool:
        """
        로그 항목 기록.

        Args:
            entry: 감사 로그 항목

        Returns:
            기록 성공 여부
        """
        pass

    @abstractmethod
    def write_batch(self, entries: list[AuditLogEntry]) -> int:
        """
        로그 항목 배치 기록.

        Args:
            entries: 감사 로그 항목 목록

        Returns:
            성공적으로 기록된 항목 수
        """
        pass

    @abstractmethod
    def read(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """
        로그 항목 조회.

        Args:
            start_time: 시작 시간
            end_time: 종료 시간
            event_types: 이벤트 타입 필터
            min_severity: 최소 심각도
            actor: 행위자 필터
            limit: 최대 항목 수
            offset: 오프셋

        Returns:
            감사 로그 항목 목록
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """저장소 종료."""
        pass


# ============================================================
# 파일 저장소 구현
# ============================================================
class FileAuditStorage(BaseAuditStorage):
    """
    파일 기반 감사 로그 저장소.

    JSON 형식으로 로그를 파일에 기록합니다.
    일별 로테이션과 압축을 지원합니다.
    """

    def __init__(
        self,
        log_dir: str = DEFAULT_LOG_DIR,
        max_files: int = DEFAULT_MAX_FILES,
        compress: bool = True,
    ) -> None:
        """
        파일 저장소 초기화.

        Args:
            log_dir: 로그 디렉토리 경로
            max_files: 최대 파일 수
            compress: 압축 활성화 여부
        """
        self._log_dir = Path(log_dir)
        self._max_files = max_files
        self._compress = compress
        self._lock = threading.RLock()
        self._current_file: Path | None = None
        self._current_date: str | None = None
        self._file_handle: Any | None = None

        # 디렉토리 생성
        self._log_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"파일 감사 저장소 초기화: {self._log_dir}")

    def _get_log_file_path(self, date_str: str | None = None) -> Path:
        """로그 파일 경로 생성."""
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._log_dir / f"audit_{date_str}.json"

    def _ensure_file_open(self) -> None:
        """현재 날짜의 파일이 열려있는지 확인."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self._current_date != current_date:
            # 기존 파일 닫기
            self._close_current_file()

            # 새 파일 열기
            self._current_date = current_date
            self._current_file = self._get_log_file_path(current_date)
            self._file_handle = open(self._current_file, "a", encoding="utf-8")

            # 이전 파일 정리
            self._cleanup_old_files()

    def _close_current_file(self) -> None:
        """현재 파일 닫기."""
        if self._file_handle is not None:
            try:
                self._file_handle.close()
            except Exception:
                pass
            finally:
                self._file_handle = None

        # 이전 날짜 파일 압축
        if self._compress and self._current_file and self._current_file.exists():
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_file = self._get_log_file_path(yesterday)
            if yesterday_file.exists() and not Path(f"{yesterday_file}.gz").exists():
                self._compress_file(yesterday_file)

    def _compress_file(self, file_path: Path) -> None:
        """파일 압축."""
        try:
            gz_path = Path(f"{file_path}.gz")
            with open(file_path, "rb") as f_in:
                with gzip.open(gz_path, "wb") as f_out:
                    f_out.writelines(f_in)
            file_path.unlink()
            logger.debug(f"감사 로그 파일 압축 완료: {gz_path}")
        except Exception as e:
            logger.warning(f"감사 로그 파일 압축 실패: {e}")

    def _cleanup_old_files(self) -> None:
        """오래된 파일 정리."""
        try:
            # 모든 로그 파일 목록
            log_files = sorted(
                self._log_dir.glob("audit_*.json*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # 초과 파일 삭제
            for old_file in log_files[self._max_files:]:
                old_file.unlink()
                logger.debug(f"오래된 감사 로그 파일 삭제: {old_file}")
        except Exception as e:
            logger.warning(f"감사 로그 파일 정리 실패: {e}")

    def write(self, entry: AuditLogEntry) -> bool:
        """로그 항목 기록."""
        with self._lock:
            try:
                self._ensure_file_open()

                if self._file_handle is None:
                    return False

                # JSON 라인 형식으로 기록
                json_str = json.dumps(entry.to_dict(), ensure_ascii=False, default=str)
                self._file_handle.write(json_str + "\n")
                self._file_handle.flush()

                return True

            except Exception as e:
                logger.error(f"감사 로그 기록 실패: {e}")
                return False

    def write_batch(self, entries: list[AuditLogEntry]) -> int:
        """로그 항목 배치 기록."""
        with self._lock:
            success_count = 0

            try:
                self._ensure_file_open()

                if self._file_handle is None:
                    return 0

                for entry in entries:
                    try:
                        json_str = json.dumps(entry.to_dict(), ensure_ascii=False, default=str)
                        self._file_handle.write(json_str + "\n")
                        success_count += 1
                    except Exception as e:
                        logger.warning(f"감사 로그 항목 기록 실패: {e}")

                self._file_handle.flush()

            except Exception as e:
                logger.error(f"감사 로그 배치 기록 실패: {e}")

            return success_count

    def read(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """로그 항목 조회."""
        results: list[AuditLogEntry] = []

        with self._lock:
            try:
                # 날짜 범위 계산
                if start_time is None:
                    start_time = datetime.now(timezone.utc) - timedelta(days=7)
                if end_time is None:
                    end_time = datetime.now(timezone.utc)

                # 대상 파일 목록
                current = start_time
                file_paths: list[Path] = []

                while current <= end_time:
                    date_str = current.strftime("%Y-%m-%d")
                    json_path = self._get_log_file_path(date_str)
                    gz_path = Path(f"{json_path}.gz")

                    if json_path.exists():
                        file_paths.append(json_path)
                    elif gz_path.exists():
                        file_paths.append(gz_path)

                    current += timedelta(days=1)

                # 파일 읽기
                skip_count = 0

                for file_path in file_paths:
                    if len(results) >= limit:
                        break

                    try:
                        if file_path.suffix == ".gz":
                            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                                lines = f.readlines()
                        else:
                            with open(file_path, "r", encoding="utf-8") as f:
                                lines = f.readlines()

                        for line in lines:
                            if len(results) >= limit:
                                break

                            try:
                                data = json.loads(line.strip())
                                entry = AuditLogEntry.from_dict(data)

                                # 필터 적용
                                if not self._matches_filters(
                                    entry, start_time, end_time,
                                    event_types, min_severity, actor
                                ):
                                    continue

                                # 오프셋 처리
                                if skip_count < offset:
                                    skip_count += 1
                                    continue

                                results.append(entry)

                            except (json.JSONDecodeError, ValueError):
                                continue

                    except Exception as e:
                        logger.warning(f"감사 로그 파일 읽기 실패 ({file_path}): {e}")

            except Exception as e:
                logger.error(f"감사 로그 조회 실패: {e}")

        return results

    def _matches_filters(
        self,
        entry: AuditLogEntry,
        start_time: datetime | None,
        end_time: datetime | None,
        event_types: list[AuditEventType] | None,
        min_severity: AuditSeverity | None,
        actor: str | None,
    ) -> bool:
        """필터 조건 확인."""
        event = entry.event

        # 시간 필터
        if event.timestamp:
            if start_time and event.timestamp < start_time:
                return False
            if end_time and event.timestamp > end_time:
                return False

        # 이벤트 타입 필터
        if event_types and event.event_type not in event_types:
            return False

        # 심각도 필터
        if min_severity and event.severity and event.severity < min_severity:
            return False

        # 행위자 필터
        if actor and event.actor != actor:
            return False

        return True

    def close(self) -> None:
        """저장소 종료."""
        with self._lock:
            self._close_current_file()
            logger.info("파일 감사 저장소 종료")


# ============================================================
# 메모리 저장소 구현 (테스트/개발용)
# ============================================================
class MemoryAuditStorage(BaseAuditStorage):
    """
    메모리 기반 감사 로그 저장소.

    테스트 및 개발 환경에서 사용합니다.
    """

    def __init__(self, max_entries: int = 10000) -> None:
        """
        메모리 저장소 초기화.

        Args:
            max_entries: 최대 항목 수
        """
        self._max_entries = max_entries
        self._entries: deque[AuditLogEntry] = deque(maxlen=max_entries)
        self._lock = threading.RLock()

    def write(self, entry: AuditLogEntry) -> bool:
        """로그 항목 기록."""
        with self._lock:
            self._entries.append(entry)
            return True

    def write_batch(self, entries: list[AuditLogEntry]) -> int:
        """로그 항목 배치 기록."""
        with self._lock:
            for entry in entries:
                self._entries.append(entry)
            return len(entries)

    def read(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """로그 항목 조회."""
        with self._lock:
            results: list[AuditLogEntry] = []
            skip_count = 0

            for entry in self._entries:
                if len(results) >= limit:
                    break

                event = entry.event

                # 필터 적용
                if start_time and event.timestamp and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp and event.timestamp > end_time:
                    continue
                if event_types and event.event_type not in event_types:
                    continue
                if min_severity and event.severity and event.severity < min_severity:
                    continue
                if actor and event.actor != actor:
                    continue

                # 오프셋 처리
                if skip_count < offset:
                    skip_count += 1
                    continue

                results.append(entry)

            return results

    def clear(self) -> None:
        """모든 항목 삭제."""
        with self._lock:
            self._entries.clear()

    def get_all(self) -> list[AuditLogEntry]:
        """모든 항목 조회."""
        with self._lock:
            return list(self._entries)

    def close(self) -> None:
        """저장소 종료."""
        pass


# ============================================================
# 알림 핸들러 추상 기본 클래스
# ============================================================
class BaseAlertHandler(ABC):
    """
    알림 핸들러 추상 기본 클래스.

    보안 위협 감지 시 알림을 전송하는 핸들러입니다.
    """

    @abstractmethod
    def send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> bool:
        """
        알림 전송.

        Args:
            event: 감사 이벤트
            alert_type: 알림 유형
            message: 알림 메시지

        Returns:
            전송 성공 여부
        """
        pass


# ============================================================
# SIEM 저장소: AWS CloudWatch Logs
# ============================================================
class CloudWatchAuditStorage(BaseAuditStorage):
    """
    AWS CloudWatch Logs 기반 감사 로그 저장소.

    CloudWatch Logs에 감사 로그를 전송합니다.
    실시간 모니터링, 알람, Insights 쿼리를 지원합니다.
    """

    def __init__(
        self,
        log_group_name: str = "/courtview/audit",
        log_stream_prefix: str = "audit-",
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        retention_days: int = 90,
    ) -> None:
        """
        CloudWatch 저장소 초기화.

        Args:
            log_group_name: CloudWatch 로그 그룹 이름
            log_stream_prefix: 로그 스트림 접두사
            region_name: AWS 리전
            aws_access_key_id: AWS 액세스 키 ID
            aws_secret_access_key: AWS 시크릿 키
            batch_size: 배치 크기
            flush_interval: 플러시 간격(초)
            retention_days: 로그 보관 기간(일)
        """
        self._log_group_name = log_group_name
        self._log_stream_prefix = log_stream_prefix
        self._region_name = region_name or os.environ.get("AWS_REGION", "ap-northeast-2")
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._retention_days = retention_days
        self._lock = threading.RLock()

        # AWS 클라이언트 지연 초기화
        self._client: Any | None = None
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key

        # 현재 로그 스트림
        self._current_stream: str | None = None
        self._current_date: str | None = None
        self._sequence_token: str | None = None

        # 배치 버퍼
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = datetime.now(timezone.utc)

        # 백그라운드 플러시 스레드
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

        logger.info(f"CloudWatch 감사 저장소 초기화: {self._log_group_name}")

    def _get_client(self) -> Any:
        """boto3 CloudWatch Logs 클라이언트 획득."""
        if self._client is None:
            try:
                import boto3

                client_kwargs: dict[str, Any] = {
                    "service_name": "logs",
                    "region_name": self._region_name,
                }

                if self._aws_access_key_id and self._aws_secret_access_key:
                    client_kwargs["aws_access_key_id"] = self._aws_access_key_id
                    client_kwargs["aws_secret_access_key"] = self._aws_secret_access_key

                self._client = boto3.client(**client_kwargs)

                # 로그 그룹 생성 (없으면)
                self._ensure_log_group()

            except ImportError:
                raise ImportError(
                    "boto3 패키지가 필요합니다. 설치하세요: pip install boto3"
                )

        return self._client

    def _ensure_log_group(self) -> None:
        """로그 그룹 존재 확인 및 생성."""
        try:
            self._client.describe_log_groups(
                logGroupNamePrefix=self._log_group_name,
                limit=1,
            )
        except Exception:
            try:
                self._client.create_log_group(
                    logGroupName=self._log_group_name,
                )

                # 보관 정책 설정
                self._client.put_retention_policy(
                    logGroupName=self._log_group_name,
                    retentionInDays=self._retention_days,
                )

                logger.info(f"CloudWatch 로그 그룹 생성: {self._log_group_name}")
            except Exception as e:
                logger.warning(f"로그 그룹 생성 실패 (이미 존재할 수 있음): {e}")

    def _ensure_log_stream(self) -> str:
        """현재 날짜의 로그 스트림 확보."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self._current_date != current_date or self._current_stream is None:
            self._current_date = current_date
            self._current_stream = f"{self._log_stream_prefix}{current_date}"
            self._sequence_token = None

            try:
                client = self._get_client()
                client.create_log_stream(
                    logGroupName=self._log_group_name,
                    logStreamName=self._current_stream,
                )
                logger.debug(f"CloudWatch 로그 스트림 생성: {self._current_stream}")
            except Exception as e:
                # ResourceAlreadyExistsException은 무시
                if "ResourceAlreadyExistsException" not in str(type(e).__name__):
                    logger.warning(f"로그 스트림 생성 실패: {e}")

        return self._current_stream

    def _start_flush_thread(self) -> None:
        """플러시 스레드 시작."""
        if self._flush_thread is None or not self._flush_thread.is_alive():
            self._stop_event.clear()
            self._flush_thread = threading.Thread(
                target=self._flush_loop,
                name="CloudWatchFlushThread",
                daemon=True,
            )
            self._flush_thread.start()

    def _flush_loop(self) -> None:
        """백그라운드 플러시 루프."""
        while not self._stop_event.wait(self._flush_interval):
            self._flush_buffer()

    def _flush_buffer(self) -> bool:
        """버퍼 플러시."""
        with self._lock:
            if not self._buffer:
                return True

            events_to_send = self._buffer[:]
            self._buffer.clear()

        try:
            client = self._get_client()
            stream_name = self._ensure_log_stream()

            # 이벤트를 CloudWatch 형식으로 변환
            log_events = []
            for event_data in events_to_send:
                log_events.append({
                    "timestamp": int(
                        datetime.fromisoformat(
                            event_data.get("created_at", datetime.now(timezone.utc).isoformat())
                            .replace("Z", "+00:00")
                        ).timestamp() * 1000
                    ),
                    "message": json.dumps(event_data, ensure_ascii=False, default=str),
                })

            # 타임스탬프 순 정렬 (CloudWatch 요구사항)
            log_events.sort(key=lambda e: e["timestamp"])

            # PutLogEvents 호출
            put_kwargs: dict[str, Any] = {
                "logGroupName": self._log_group_name,
                "logStreamName": stream_name,
                "logEvents": log_events,
            }

            if self._sequence_token:
                put_kwargs["sequenceToken"] = self._sequence_token

            response = client.put_log_events(**put_kwargs)
            self._sequence_token = response.get("nextSequenceToken")

            self._last_flush = datetime.now(timezone.utc)
            return True

        except Exception as e:
            logger.error(f"CloudWatch 로그 전송 실패: {e}")
            # 실패한 이벤트 재큐
            with self._lock:
                self._buffer = events_to_send + self._buffer
            return False

    def write(self, entry: AuditLogEntry) -> bool:
        """로그 항목 기록."""
        self._start_flush_thread()

        with self._lock:
            self._buffer.append(entry.to_dict())

            # 배치 크기 도달 시 즉시 플러시
            if len(self._buffer) >= self._batch_size:
                # 락 해제 후 플러시
                pass

        if len(self._buffer) >= self._batch_size:
            return self._flush_buffer()

        return True

    def write_batch(self, entries: list[AuditLogEntry]) -> int:
        """로그 항목 배치 기록."""
        self._start_flush_thread()

        with self._lock:
            for entry in entries:
                self._buffer.append(entry.to_dict())

        # 즉시 플러시
        if self._flush_buffer():
            return len(entries)
        return 0

    def read(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """로그 항목 조회 (CloudWatch Insights 사용)."""
        try:
            client = self._get_client()

            # 시간 범위 설정
            if start_time is None:
                start_time = datetime.now(timezone.utc) - timedelta(days=7)
            if end_time is None:
                end_time = datetime.now(timezone.utc)

            # CloudWatch Insights 쿼리 구성
            query_parts = ["fields @timestamp, @message"]

            filters = []
            if event_types:
                event_values = [f"'{et.value}'" for et in event_types]
                filters.append(f"event.event_type in [{', '.join(event_values)}]")
            if min_severity:
                filters.append(f"event.severity >= '{min_severity.name_str}'")
            if actor:
                filters.append(f"event.actor = '{actor}'")

            if filters:
                query_parts.append(f"| filter {' and '.join(filters)}")

            query_parts.append(f"| sort @timestamp desc")
            query_parts.append(f"| limit {limit + offset}")

            query = " ".join(query_parts)

            # 쿼리 시작
            start_query_response = client.start_query(
                logGroupName=self._log_group_name,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query,
            )

            query_id = start_query_response["queryId"]

            # 쿼리 완료 대기
            response = None
            for _ in range(30):  # 최대 30초 대기
                response = client.get_query_results(queryId=query_id)
                if response["status"] == "Complete":
                    break
                elif response["status"] in ("Failed", "Cancelled"):
                    logger.error(f"CloudWatch 쿼리 실패: {response['status']}")
                    return []
                import time
                time.sleep(1)

            if response is None or response["status"] != "Complete":
                logger.warning("CloudWatch 쿼리 타임아웃")
                return []

            # 결과 파싱
            results: list[AuditLogEntry] = []
            skip_count = 0

            for result in response.get("results", []):
                if len(results) >= limit:
                    break

                # @message 필드 찾기
                message = None
                for field in result:
                    if field["field"] == "@message":
                        message = field["value"]
                        break

                if message:
                    try:
                        data = json.loads(message)
                        entry = AuditLogEntry.from_dict(data)

                        # 오프셋 처리
                        if skip_count < offset:
                            skip_count += 1
                            continue

                        results.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue

            return results

        except Exception as e:
            logger.error(f"CloudWatch 로그 조회 실패: {e}")
            return []

    def close(self) -> None:
        """저장소 종료."""
        self._stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

        # 남은 버퍼 플러시
        self._flush_buffer()

        logger.info("CloudWatch 감사 저장소 종료")


# ============================================================
# SIEM 저장소: Elasticsearch (ELK Stack)
# ============================================================
class ElasticsearchAuditStorage(BaseAuditStorage):
    """
    Elasticsearch 기반 감사 로그 저장소.

    ELK(Elasticsearch-Logstash-Kibana) 스택과 통합됩니다.
    강력한 검색, 분석, 시각화 기능을 제공합니다.
    """

    def __init__(
        self,
        hosts: list[str] | None = None,
        index_prefix: str = "courtview-audit",
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        use_ssl: bool = True,
        verify_certs: bool = True,
        ca_certs: str | None = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        index_rotation: str = "daily",  # daily, weekly, monthly
        shards: int = 1,
        replicas: int = 1,
    ) -> None:
        """
        Elasticsearch 저장소 초기화.

        Args:
            hosts: Elasticsearch 호스트 목록
            index_prefix: 인덱스 접두사
            username: 사용자명
            password: 비밀번호
            api_key: API 키
            use_ssl: SSL 사용 여부
            verify_certs: 인증서 검증 여부
            ca_certs: CA 인증서 경로
            batch_size: 배치 크기
            flush_interval: 플러시 간격(초)
            index_rotation: 인덱스 로테이션 주기
            shards: 샤드 수
            replicas: 레플리카 수
        """
        self._hosts = hosts or [os.environ.get("ELASTICSEARCH_HOST", "http://localhost:9200")]
        self._index_prefix = index_prefix
        self._username = username or os.environ.get("ELASTICSEARCH_USERNAME")
        self._password = password or os.environ.get("ELASTICSEARCH_PASSWORD")
        self._api_key = api_key or os.environ.get("ELASTICSEARCH_API_KEY")
        self._use_ssl = use_ssl
        self._verify_certs = verify_certs
        self._ca_certs = ca_certs
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._index_rotation = index_rotation
        self._shards = shards
        self._replicas = replicas
        self._lock = threading.RLock()

        # 클라이언트 지연 초기화
        self._client: Any | None = None

        # 배치 버퍼
        self._buffer: list[dict[str, Any]] = []

        # 플러시 스레드
        self._stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

        # 인덱스 템플릿 설정 여부
        self._template_created = False

        logger.info(f"Elasticsearch 감사 저장소 초기화: {self._hosts}")

    def _get_client(self) -> Any:
        """Elasticsearch 클라이언트 획득."""
        if self._client is None:
            try:
                from elasticsearch import Elasticsearch

                client_kwargs: dict[str, Any] = {
                    "hosts": self._hosts,
                    "verify_certs": self._verify_certs,
                }

                if self._username and self._password:
                    client_kwargs["basic_auth"] = (self._username, self._password)
                elif self._api_key:
                    client_kwargs["api_key"] = self._api_key

                if self._ca_certs:
                    client_kwargs["ca_certs"] = self._ca_certs

                self._client = Elasticsearch(**client_kwargs)

                # 인덱스 템플릿 생성
                self._ensure_index_template()

            except ImportError:
                raise ImportError(
                    "elasticsearch 패키지가 필요합니다. 설치하세요: pip install elasticsearch"
                )

        return self._client

    def _get_index_name(self) -> str:
        """현재 인덱스 이름 생성."""
        now = datetime.now(timezone.utc)

        if self._index_rotation == "daily":
            suffix = now.strftime("%Y.%m.%d")
        elif self._index_rotation == "weekly":
            suffix = now.strftime("%Y.%W")
        elif self._index_rotation == "monthly":
            suffix = now.strftime("%Y.%m")
        else:
            suffix = now.strftime("%Y.%m.%d")

        return f"{self._index_prefix}-{suffix}"

    def _ensure_index_template(self) -> None:
        """인덱스 템플릿 생성."""
        if self._template_created:
            return

        try:
            template = {
                "index_patterns": [f"{self._index_prefix}-*"],
                "template": {
                    "settings": {
                        "number_of_shards": self._shards,
                        "number_of_replicas": self._replicas,
                        "index.lifecycle.name": "audit-policy",
                        "index.lifecycle.rollover_alias": self._index_prefix,
                    },
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "event": {
                                "properties": {
                                    "event_type": {"type": "keyword"},
                                    "actor": {"type": "keyword"},
                                    "action": {"type": "keyword"},
                                    "resource": {"type": "keyword"},
                                    "result": {"type": "keyword"},
                                    "severity": {"type": "keyword"},
                                    "timestamp": {"type": "date"},
                                    "request_id": {"type": "keyword"},
                                    "session_id": {"type": "keyword"},
                                    "ip_address": {"type": "ip"},
                                    "user_agent": {"type": "text"},
                                    "details": {"type": "object", "dynamic": True},
                                    "metadata": {"type": "object", "dynamic": True},
                                }
                            },
                            "entry_hash": {"type": "keyword"},
                            "chain_hash": {"type": "keyword"},
                            "created_at": {"type": "date"},
                            "sequence_number": {"type": "long"},
                        }
                    },
                },
            }

            self._client.indices.put_index_template(
                name=f"{self._index_prefix}-template",
                body=template,
            )

            self._template_created = True
            logger.info(f"Elasticsearch 인덱스 템플릿 생성: {self._index_prefix}-template")

        except Exception as e:
            logger.warning(f"인덱스 템플릿 생성 실패: {e}")

    def _start_flush_thread(self) -> None:
        """플러시 스레드 시작."""
        if self._flush_thread is None or not self._flush_thread.is_alive():
            self._stop_event.clear()
            self._flush_thread = threading.Thread(
                target=self._flush_loop,
                name="ElasticsearchFlushThread",
                daemon=True,
            )
            self._flush_thread.start()

    def _flush_loop(self) -> None:
        """백그라운드 플러시 루프."""
        while not self._stop_event.wait(self._flush_interval):
            self._flush_buffer()

    def _flush_buffer(self) -> bool:
        """버퍼 플러시."""
        with self._lock:
            if not self._buffer:
                return True

            docs_to_send = self._buffer[:]
            self._buffer.clear()

        try:
            from elasticsearch.helpers import bulk

            client = self._get_client()
            index_name = self._get_index_name()

            # Bulk 인덱싱용 액션 생성
            actions = []
            for doc in docs_to_send:
                actions.append({
                    "_index": index_name,
                    "_id": doc.get("id"),
                    "_source": doc,
                })

            # Bulk 인덱싱
            success, failed = bulk(
                client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
            )

            if failed:
                logger.warning(f"Elasticsearch 일부 문서 인덱싱 실패: {len(failed)}개")

            return True

        except Exception as e:
            logger.error(f"Elasticsearch 인덱싱 실패: {e}")
            # 실패한 문서 재큐
            with self._lock:
                self._buffer = docs_to_send + self._buffer
            return False

    def write(self, entry: AuditLogEntry) -> bool:
        """로그 항목 기록."""
        self._start_flush_thread()

        with self._lock:
            self._buffer.append(entry.to_dict())

            if len(self._buffer) >= self._batch_size:
                pass

        if len(self._buffer) >= self._batch_size:
            return self._flush_buffer()

        return True

    def write_batch(self, entries: list[AuditLogEntry]) -> int:
        """로그 항목 배치 기록."""
        self._start_flush_thread()

        with self._lock:
            for entry in entries:
                self._buffer.append(entry.to_dict())

        if self._flush_buffer():
            return len(entries)
        return 0

    def read(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """로그 항목 조회."""
        try:
            client = self._get_client()

            # 시간 범위 설정
            if start_time is None:
                start_time = datetime.now(timezone.utc) - timedelta(days=7)
            if end_time is None:
                end_time = datetime.now(timezone.utc)

            # Elasticsearch 쿼리 구성
            must_clauses = [
                {
                    "range": {
                        "event.timestamp": {
                            "gte": start_time.isoformat(),
                            "lte": end_time.isoformat(),
                        }
                    }
                }
            ]

            if event_types:
                must_clauses.append({
                    "terms": {
                        "event.event_type": [et.value for et in event_types]
                    }
                })

            if min_severity:
                severity_order = ["debug", "info", "warning", "error", "critical"]
                min_index = severity_order.index(min_severity.name_str)
                allowed_severities = severity_order[min_index:]
                must_clauses.append({
                    "terms": {
                        "event.severity": allowed_severities
                    }
                })

            if actor:
                must_clauses.append({
                    "term": {
                        "event.actor": actor
                    }
                })

            query = {
                "bool": {
                    "must": must_clauses
                }
            }

            # 검색 실행
            response = client.search(
                index=f"{self._index_prefix}-*",
                body={
                    "query": query,
                    "sort": [{"event.timestamp": "desc"}],
                    "from": offset,
                    "size": limit,
                },
            )

            # 결과 파싱
            results: list[AuditLogEntry] = []

            for hit in response.get("hits", {}).get("hits", []):
                try:
                    source = hit["_source"]
                    entry = AuditLogEntry.from_dict(source)
                    results.append(entry)
                except (KeyError, ValueError) as e:
                    logger.warning(f"로그 항목 파싱 실패: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Elasticsearch 조회 실패: {e}")
            return []

    def close(self) -> None:
        """저장소 종료."""
        self._stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

        # 남은 버퍼 플러시
        self._flush_buffer()

        # 클라이언트 종료
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

        logger.info("Elasticsearch 감사 저장소 종료")


# ============================================================
# 로그 알림 핸들러 구현
# ============================================================
class LogAlertHandler(BaseAlertHandler):
    """
    로그 기반 알림 핸들러.

    알림을 로그로 기록합니다.
    """

    def __init__(self, log_level: int = logging.WARNING) -> None:
        """
        로그 알림 핸들러 초기화.

        Args:
            log_level: 로그 레벨
        """
        self._log_level = log_level

    def send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> bool:
        """알림 전송."""
        logger.log(
            self._log_level,
            f"[보안 알림] {alert_type}: {message} - "
            f"이벤트={event.event_type.value}, 행위자={event.actor}, "
            f"리소스={event.resource}"
        )
        return True


# ============================================================
# Slack 알림 핸들러
# ============================================================
class SlackAlertHandler(BaseAlertHandler):
    """
    Slack 기반 알림 핸들러.

    Webhook URL을 통해 Slack 채널에 보안 알림을 전송합니다.
    심각도에 따른 색상 구분과 멘션 기능을 지원합니다.
    """

    # 심각도별 색상
    SEVERITY_COLORS: dict[str, str] = {
        "debug": "#808080",      # 회색
        "info": "#36a64f",       # 녹색
        "warning": "#ffa500",    # 주황색
        "error": "#ff0000",      # 빨간색
        "critical": "#8b0000",   # 진한 빨간색
    }

    def __init__(
        self,
        webhook_url: str | None = None,
        channel: str | None = None,
        username: str = "COURTVIEW Security",
        icon_emoji: str = ":shield:",
        mention_users: list[str] | None = None,
        mention_on_severity: list[str] | None = None,
        rate_limit: int = 10,  # 분당 최대 알림 수
        timeout: float = 10.0,
    ) -> None:
        """
        Slack 알림 핸들러 초기화.

        Args:
            webhook_url: Slack Webhook URL
            channel: 채널 이름 (webhook에 설정된 채널 대신 사용)
            username: 봇 사용자명
            icon_emoji: 봇 아이콘 이모지
            mention_users: 멘션할 사용자 ID 목록
            mention_on_severity: 멘션을 활성화할 심각도 목록
            rate_limit: 분당 최대 알림 수
            timeout: 요청 타임아웃(초)
        """
        self._webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self._channel = channel
        self._username = username
        self._icon_emoji = icon_emoji
        self._mention_users = mention_users or []
        self._mention_on_severity = set(mention_on_severity or ["critical", "error"])
        self._rate_limit = rate_limit
        self._timeout = timeout
        self._lock = threading.RLock()

        # 레이트 리밋 추적
        self._recent_alerts: deque[datetime] = deque()
        self._rate_window = timedelta(minutes=1)

        if not self._webhook_url:
            logger.warning("Slack Webhook URL이 설정되지 않았습니다")

    def _check_rate_limit(self) -> bool:
        """레이트 리밋 확인."""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - self._rate_window

            # 윈도우 외 알림 제거
            while self._recent_alerts and self._recent_alerts[0] < cutoff:
                self._recent_alerts.popleft()

            # 리밋 확인
            if len(self._recent_alerts) >= self._rate_limit:
                return False

            self._recent_alerts.append(now)
            return True

    def _build_message(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> dict[str, Any]:
        """Slack 메시지 구성."""
        severity_str = event.severity.name_str if event.severity else "info"
        color = self.SEVERITY_COLORS.get(severity_str, "#808080")

        # 멘션 구성
        mention_text = ""
        if severity_str in self._mention_on_severity and self._mention_users:
            mentions = " ".join([f"<@{uid}>" for uid in self._mention_users])
            mention_text = f"{mentions} "

        # 필드 구성
        fields = [
            {
                "title": "이벤트 타입",
                "value": event.event_type.value,
                "short": True,
            },
            {
                "title": "행위자",
                "value": event.actor,
                "short": True,
            },
            {
                "title": "리소스",
                "value": event.resource,
                "short": True,
            },
            {
                "title": "결과",
                "value": event.result,
                "short": True,
            },
            {
                "title": "심각도",
                "value": severity_str.upper(),
                "short": True,
            },
        ]

        if event.ip_address:
            fields.append({
                "title": "IP 주소",
                "value": event.ip_address,
                "short": True,
            })

        if event.request_id:
            fields.append({
                "title": "요청 ID",
                "value": event.request_id,
                "short": True,
            })

        # 메시지 구성
        payload: dict[str, Any] = {
            "username": self._username,
            "icon_emoji": self._icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": f":warning: {alert_type}",
                    "text": f"{mention_text}{message}",
                    "fields": fields,
                    "footer": "COURTVIEW Security",
                    "ts": int(event.timestamp.timestamp()) if event.timestamp else None,
                }
            ],
        }

        if self._channel:
            payload["channel"] = self._channel

        return payload

    def send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> bool:
        """알림 전송."""
        if not self._webhook_url:
            logger.warning("Slack Webhook URL이 설정되지 않음")
            return False

        if not self._check_rate_limit():
            logger.warning("Slack 알림 레이트 리밋 초과")
            return False

        try:
            import urllib.request
            import urllib.error

            payload = self._build_message(event, alert_type, message)
            data = json.dumps(payload).encode("utf-8")

            request = urllib.request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                if response.status == 200:
                    logger.debug(f"Slack 알림 전송 성공: {alert_type}")
                    return True
                else:
                    logger.warning(f"Slack 알림 전송 실패: HTTP {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Slack 알림 전송 오류: {e}")
            return False


# ============================================================
# Email 알림 핸들러
# ============================================================
class EmailAlertHandler(BaseAlertHandler):
    """
    이메일 기반 알림 핸들러.

    SMTP를 통해 보안 알림 이메일을 전송합니다.
    HTML 형식과 템플릿을 지원합니다.
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        use_tls: bool = True,
        from_email: str | None = None,
        to_emails: list[str] | None = None,
        cc_emails: list[str] | None = None,
        subject_prefix: str = "[COURTVIEW Security]",
        rate_limit: int = 5,  # 분당 최대 이메일 수
        timeout: float = 30.0,
    ) -> None:
        """
        이메일 알림 핸들러 초기화.

        Args:
            smtp_host: SMTP 서버 호스트
            smtp_port: SMTP 서버 포트
            smtp_username: SMTP 인증 사용자명
            smtp_password: SMTP 인증 비밀번호
            use_tls: TLS 사용 여부
            from_email: 발신자 이메일
            to_emails: 수신자 이메일 목록
            cc_emails: 참조 이메일 목록
            subject_prefix: 제목 접두사
            rate_limit: 분당 최대 이메일 수
            timeout: 연결 타임아웃(초)
        """
        self._smtp_host = smtp_host or os.environ.get("SMTP_HOST", "localhost")
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username or os.environ.get("SMTP_USERNAME")
        self._smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD")
        self._use_tls = use_tls
        self._from_email = from_email or os.environ.get("SMTP_FROM", "security@courtview.ai")
        self._to_emails = to_emails or []
        self._cc_emails = cc_emails or []
        self._subject_prefix = subject_prefix
        self._rate_limit = rate_limit
        self._timeout = timeout
        self._lock = threading.RLock()

        # 레이트 리밋 추적
        self._recent_alerts: deque[datetime] = deque()
        self._rate_window = timedelta(minutes=1)

        # 환경 변수에서 수신자 로드
        if not self._to_emails:
            env_to = os.environ.get("ALERT_EMAILS", "")
            if env_to:
                self._to_emails = [e.strip() for e in env_to.split(",") if e.strip()]

    def _check_rate_limit(self) -> bool:
        """레이트 리밋 확인."""
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - self._rate_window

            while self._recent_alerts and self._recent_alerts[0] < cutoff:
                self._recent_alerts.popleft()

            if len(self._recent_alerts) >= self._rate_limit:
                return False

            self._recent_alerts.append(now)
            return True

    def _build_html_content(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> str:
        """HTML 이메일 본문 구성."""
        severity_str = event.severity.name_str if event.severity else "info"

        severity_colors = {
            "debug": "#808080",
            "info": "#28a745",
            "warning": "#ffc107",
            "error": "#dc3545",
            "critical": "#8b0000",
        }
        color = severity_colors.get(severity_str, "#808080")

        timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if event.timestamp else "N/A"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .alert-box {{ border: 2px solid {color}; border-radius: 8px; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 10px; border-radius: 5px 5px 0 0; margin: -20px -20px 20px -20px; }}
                .field {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #555; }}
                .value {{ color: #333; }}
                .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="alert-box">
                <div class="header">
                    <h2 style="margin: 0;">🚨 {alert_type}</h2>
                </div>

                <p style="font-size: 16px;">{message}</p>

                <div class="field">
                    <span class="label">이벤트 타입:</span>
                    <span class="value">{event.event_type.value}</span>
                </div>

                <div class="field">
                    <span class="label">행위자:</span>
                    <span class="value">{event.actor}</span>
                </div>

                <div class="field">
                    <span class="label">리소스:</span>
                    <span class="value">{event.resource}</span>
                </div>

                <div class="field">
                    <span class="label">결과:</span>
                    <span class="value">{event.result}</span>
                </div>

                <div class="field">
                    <span class="label">심각도:</span>
                    <span class="value" style="color: {color}; font-weight: bold;">{severity_str.upper()}</span>
                </div>

                <div class="field">
                    <span class="label">시간:</span>
                    <span class="value">{timestamp_str}</span>
                </div>

                {"<div class='field'><span class='label'>IP 주소:</span><span class='value'>" + event.ip_address + "</span></div>" if event.ip_address else ""}

                {"<div class='field'><span class='label'>요청 ID:</span><span class='value'>" + (event.request_id or "") + "</span></div>" if event.request_id else ""}

                <div class="footer">
                    <p>이 알림은 COURTVIEW Security 시스템에서 자동으로 발송되었습니다.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> bool:
        """알림 전송."""
        if not self._to_emails:
            logger.warning("이메일 수신자가 설정되지 않음")
            return False

        if not self._check_rate_limit():
            logger.warning("이메일 알림 레이트 리밋 초과")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # 이메일 구성
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"{self._subject_prefix} {alert_type}"
            msg["From"] = self._from_email
            msg["To"] = ", ".join(self._to_emails)

            if self._cc_emails:
                msg["Cc"] = ", ".join(self._cc_emails)

            # 텍스트 본문
            text_content = f"""
보안 알림: {alert_type}

{message}

이벤트 타입: {event.event_type.value}
행위자: {event.actor}
리소스: {event.resource}
결과: {event.result}
심각도: {event.severity.name_str.upper() if event.severity else 'INFO'}
시간: {event.timestamp.isoformat() if event.timestamp else 'N/A'}
IP 주소: {event.ip_address or 'N/A'}
요청 ID: {event.request_id or 'N/A'}

--
COURTVIEW Security
            """

            # HTML 본문
            html_content = self._build_html_content(event, alert_type, message)

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # SMTP 연결 및 전송
            all_recipients = self._to_emails + self._cc_emails

            if self._use_tls:
                with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=self._timeout) as server:
                    server.starttls()
                    if self._smtp_username and self._smtp_password:
                        server.login(self._smtp_username, self._smtp_password)
                    server.sendmail(self._from_email, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=self._timeout) as server:
                    if self._smtp_username and self._smtp_password:
                        server.login(self._smtp_username, self._smtp_password)
                    server.sendmail(self._from_email, all_recipients, msg.as_string())

            logger.debug(f"이메일 알림 전송 성공: {alert_type}")
            return True

        except Exception as e:
            logger.error(f"이메일 알림 전송 오류: {e}")
            return False


# ============================================================
# Webhook 알림 핸들러
# ============================================================
class WebhookAlertHandler(BaseAlertHandler):
    """
    범용 Webhook 알림 핸들러.

    HTTP POST를 통해 외부 시스템에 보안 알림을 전송합니다.
    커스텀 헤더, 인증, 페이로드 포맷을 지원합니다.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        headers: dict[str, str] | None = None,
        auth_type: str | None = None,  # bearer, basic, api_key
        auth_token: str | None = None,
        api_key_header: str = "X-API-Key",
        payload_format: str = "json",  # json, form
        include_details: bool = True,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        """
        Webhook 알림 핸들러 초기화.

        Args:
            webhook_url: Webhook URL
            headers: 커스텀 헤더
            auth_type: 인증 타입 (bearer, basic, api_key)
            auth_token: 인증 토큰/키
            api_key_header: API 키 헤더 이름
            payload_format: 페이로드 포맷
            include_details: 상세 정보 포함 여부
            retry_count: 재시도 횟수
            retry_delay: 재시도 간격(초)
            timeout: 요청 타임아웃(초)
        """
        self._webhook_url = webhook_url or os.environ.get("ALERT_WEBHOOK_URL")
        self._headers = headers or {}
        self._auth_type = auth_type
        self._auth_token = auth_token or os.environ.get("ALERT_WEBHOOK_TOKEN")
        self._api_key_header = api_key_header
        self._payload_format = payload_format
        self._include_details = include_details
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        self._timeout = timeout

        if not self._webhook_url:
            logger.warning("Webhook URL이 설정되지 않았습니다")

    def _build_headers(self) -> dict[str, str]:
        """요청 헤더 구성."""
        headers = dict(self._headers)

        if self._payload_format == "json":
            headers["Content-Type"] = "application/json"
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        # 인증 헤더
        if self._auth_type and self._auth_token:
            if self._auth_type == "bearer":
                headers["Authorization"] = f"Bearer {self._auth_token}"
            elif self._auth_type == "basic":
                import base64
                encoded = base64.b64encode(self._auth_token.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"
            elif self._auth_type == "api_key":
                headers[self._api_key_header] = self._auth_token

        return headers

    def _build_payload(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> dict[str, Any]:
        """페이로드 구성."""
        payload = {
            "alert_type": alert_type,
            "message": message,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "event": {
                "type": event.event_type.value,
                "actor": event.actor,
                "action": event.action,
                "resource": event.resource,
                "result": event.result,
                "severity": event.severity.name_str if event.severity else "info",
            },
            "source": "courtview-security",
        }

        if self._include_details:
            payload["event"]["ip_address"] = event.ip_address
            payload["event"]["request_id"] = event.request_id
            payload["event"]["session_id"] = event.session_id
            payload["event"]["user_agent"] = event.user_agent
            payload["event"]["details"] = event.details
            payload["event"]["metadata"] = event.metadata

        return payload

    def send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> bool:
        """알림 전송."""
        if not self._webhook_url:
            logger.warning("Webhook URL이 설정되지 않음")
            return False

        import urllib.request
        import urllib.error
        import urllib.parse
        import time

        headers = self._build_headers()
        payload = self._build_payload(event, alert_type, message)

        # 페이로드 인코딩
        if self._payload_format == "json":
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        else:
            data = urllib.parse.urlencode(payload).encode("utf-8")

        # 재시도 로직
        last_error: Exception | None = None

        for attempt in range(self._retry_count):
            try:
                request = urllib.request.Request(
                    self._webhook_url,
                    data=data,
                    headers=headers,
                    method="POST",
                )

                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    if 200 <= response.status < 300:
                        logger.debug(f"Webhook 알림 전송 성공: {alert_type}")
                        return True
                    else:
                        logger.warning(f"Webhook 알림 전송 실패: HTTP {response.status}")
                        last_error = Exception(f"HTTP {response.status}")

            except urllib.error.HTTPError as e:
                last_error = e
                logger.warning(f"Webhook 알림 HTTP 오류 (시도 {attempt + 1}/{self._retry_count}): {e}")
            except urllib.error.URLError as e:
                last_error = e
                logger.warning(f"Webhook 알림 URL 오류 (시도 {attempt + 1}/{self._retry_count}): {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"Webhook 알림 오류 (시도 {attempt + 1}/{self._retry_count}): {e}")

            # 마지막 시도가 아니면 대기
            if attempt < self._retry_count - 1:
                time.sleep(self._retry_delay * (attempt + 1))  # 지수 백오프

        logger.error(f"Webhook 알림 전송 최종 실패: {last_error}")
        return False


# ============================================================
# 로그인 실패 추적기
# ============================================================
class LoginFailureTracker:
    """
    로그인 실패 추적기.

    특정 시간 윈도우 내 로그인 실패 횟수를 추적합니다.
    """

    def __init__(
        self,
        threshold: int = DEFAULT_LOGIN_FAILURE_THRESHOLD,
        window_minutes: int = DEFAULT_THRESHOLD_WINDOW_MINUTES,
    ) -> None:
        """
        로그인 실패 추적기 초기화.

        Args:
            threshold: 알림 임계값
            window_minutes: 추적 윈도우 (분)
        """
        self._threshold = threshold
        self._window = timedelta(minutes=window_minutes)
        self._failures: dict[str, deque[datetime]] = {}
        self._lock = threading.RLock()

    def record_failure(self, actor: str) -> bool:
        """
        로그인 실패 기록.

        Args:
            actor: 행위자

        Returns:
            임계값 초과 여부
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - self._window

            # 행위자별 실패 기록 초기화
            if actor not in self._failures:
                self._failures[actor] = deque()

            # 윈도우 외 기록 제거
            while self._failures[actor] and self._failures[actor][0] < cutoff:
                self._failures[actor].popleft()

            # 새 실패 기록
            self._failures[actor].append(now)

            # 임계값 확인
            return len(self._failures[actor]) >= self._threshold

    def get_failure_count(self, actor: str) -> int:
        """행위자의 현재 실패 횟수 조회."""
        with self._lock:
            if actor not in self._failures:
                return 0

            now = datetime.now(timezone.utc)
            cutoff = now - self._window

            # 윈도우 외 기록 제거
            while self._failures[actor] and self._failures[actor][0] < cutoff:
                self._failures[actor].popleft()

            return len(self._failures[actor])

    def reset(self, actor: str) -> None:
        """행위자의 실패 기록 초기화."""
        with self._lock:
            if actor in self._failures:
                self._failures[actor].clear()


# ============================================================
# 감사 로거 메인 클래스
# ============================================================
class AuditLogger:
    """
    감사 로거 메인 클래스.

    보안 이벤트 및 접근 기록을 기록하고 관리합니다.
    DI 컨테이너에 등록되어 주입됩니다.

    Features:
        - 다중 저장소 지원
        - 체인 해시 기반 무결성 보장
        - 실시간 알림
        - 이벤트 필터링 및 샘플링
        - 비동기 배치 처리
        - 스레드 안전 설계
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        """
        감사 로거 초기화.

        Args:
            config_loader: 설정 로더
            metrics_collector: 메트릭 수집기 (DI 주입)
        """
        self._config_loader = config_loader
        self._metrics_collector = metrics_collector
        self._lock = threading.RLock()

        # 설정 로드
        self._config = self._load_config()

        # 저장소 초기화
        self._storages: list[BaseAuditStorage] = []
        self._init_storages()

        # 알림 핸들러
        self._alert_handlers: list[BaseAlertHandler] = []
        self._init_alert_handlers()

        # 로그인 실패 추적기
        self._login_tracker = LoginFailureTracker(
            threshold=self._config.get("login_failure_threshold", DEFAULT_LOGIN_FAILURE_THRESHOLD),
            window_minutes=self._config.get("threshold_window_minutes", DEFAULT_THRESHOLD_WINDOW_MINUTES),
        )

        # 체인 해시 상태
        self._last_chain_hash = INITIAL_CHAIN_HASH
        self._sequence_number = 0

        # 필터링 설정
        self._exclude_events: set[str] = set(
            self._config.get("exclude_events", ["health_check"])
        )
        self._min_severity = AuditSeverity.from_string(
            self._config.get("min_severity", "info")
        ) or AuditSeverity.INFO

        # 샘플링 설정
        self._sampling_enabled = self._config.get("sampling_enabled", True)
        self._sampling_rate = self._config.get("sampling_rate", DEFAULT_SAMPLE_RATE)
        self._sampling_levels: set[str] = set(
            self._config.get("sampling_levels", ["debug"])
        )

        # 무결성 설정
        self._integrity_enabled = self._config.get("integrity_enabled", True)
        self._chain_hash_enabled = self._config.get("chain_hash_enabled", True)

        # 알림 설정
        self._alerting_enabled = self._config.get("alerting_enabled", True)
        self._immediate_alerts: set[str] = set(
            self._config.get("immediate_alerts", [
                "intrusion_detected",
                "suspicious_activity",
                "login_failure_threshold",
            ])
        )

        # 버퍼 (배치 처리용)
        self._buffer: list[AuditLogEntry] = []
        self._buffer_size = self._config.get("buffer_size", DEFAULT_BUFFER_SIZE)
        self._flush_interval = self._config.get("flush_interval", DEFAULT_FLUSH_INTERVAL)

        # 백그라운드 플러시 스레드
        self._flush_thread: threading.Thread | None = None
        self._stop_flush = threading.Event()
        self._start_flush_thread()

        logger.info("감사 로거 초기화 완료")

    def __repr__(self) -> str:
        """AuditLogger 인스턴스 표현."""
        with self._lock:
            storages = len(self._storages)
            alerts = len(self._alert_handlers)
            seq = self._sequence_number
        return (
            f"AuditLogger(storages={storages}, "
            f"alerts={alerts}, "
            f"sequence={seq})"
        )

    def _load_config(self) -> dict[str, Any]:
        """설정 로드."""
        try:
            config = self._config_loader.get("security.audit_logger", {})
            return config
        except Exception as e:
            logger.warning(f"감사 로거 설정 로드 실패, 기본값 사용: {e}")
            return {}

    def _init_storages(self) -> None:
        """저장소 초기화."""
        storage_config = self._config.get("storage", {})

        # 파일 저장소
        file_config = storage_config.get("file", {})
        if file_config.get("enabled", True):
            log_dir = file_config.get("path", DEFAULT_LOG_DIR)
            max_files = file_config.get("rotation", {}).get("max_files", DEFAULT_MAX_FILES)
            compress = file_config.get("rotation", {}).get("compress", True)

            self._storages.append(FileAuditStorage(
                log_dir=log_dir,
                max_files=max_files,
                compress=compress,
            ))

        # 기본 저장소가 없으면 메모리 저장소 사용
        if not self._storages:
            self._storages.append(MemoryAuditStorage())

    def _init_alert_handlers(self) -> None:
        """알림 핸들러 초기화."""
        # 기본 로그 알림 핸들러
        self._alert_handlers.append(LogAlertHandler(logging.WARNING))

    def _start_flush_thread(self) -> None:
        """플러시 스레드 시작."""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name="AuditFlushThread",
            daemon=True,
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        """플러시 루프."""
        while not self._stop_flush.wait(self._flush_interval):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼 플러시."""
        with self._lock:
            if not self._buffer:
                return

            entries_to_write = self._buffer[:]
            self._buffer.clear()

        # 저장소에 기록
        for storage in self._storages:
            try:
                storage.write_batch(entries_to_write)
            except Exception as e:
                logger.error(f"감사 로그 플러시 실패 ({type(storage).__name__}): {e}")

    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        resource: str,
        result: str = "success",
        severity: AuditSeverity | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        immediate: bool = False,
    ) -> str | None:
        """
        감사 이벤트 기록.

        Args:
            event_type: 이벤트 타입
            actor: 행위자
            action: 동작
            resource: 리소스
            result: 결과
            severity: 심각도
            request_id: 요청 ID
            session_id: 세션 ID
            ip_address: IP 주소
            user_agent: 사용자 에이전트
            details: 상세 정보
            metadata: 메타데이터
            immediate: 즉시 기록 여부

        Returns:
            로그 항목 ID (필터링된 경우 None)
        """
        # 필터링 확인
        if not self._should_log(event_type, severity):
            return None

        # 이벤트 생성
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            severity=severity,
            request_id=request_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            metadata=metadata or {},
        )

        # 로그 항목 생성
        entry = self._create_entry(event)

        # 메트릭 기록
        self._record_metrics(event)

        # 알림 처리
        self._process_alerts(event)

        # 로그인 실패 추적
        if event_type == AuditEventType.LOGIN_FAILURE:
            if self._login_tracker.record_failure(actor):
                self._send_alert(
                    event,
                    "login_failure_threshold",
                    f"로그인 실패 임계값 초과: {actor}",
                )
        elif event_type == AuditEventType.LOGIN_SUCCESS:
            self._login_tracker.reset(actor)

        # 저장
        if immediate or event.severity == AuditSeverity.CRITICAL:
            self._write_immediate(entry)
        else:
            self._add_to_buffer(entry)

        return entry.id

    def _should_log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity | None,
    ) -> bool:
        """로깅 여부 확인."""
        # 제외 이벤트 확인
        if event_type.action in self._exclude_events:
            return False

        # 심각도 확인
        if severity is None:
            severity = EVENT_DEFAULT_SEVERITY.get(
                event_type.category,
                AuditSeverity.INFO,
            )

        if severity < self._min_severity:
            return False

        # 샘플링 확인
        if self._sampling_enabled:
            if severity.name_str in self._sampling_levels:
                import random
                if random.random() > self._sampling_rate:
                    return False

        return True

    def _create_entry(self, event: AuditEvent) -> AuditLogEntry:
        """로그 항목 생성."""
        with self._lock:
            self._sequence_number += 1

            entry = AuditLogEntry(
                id=str(uuid.uuid4()),
                event=event,
                sequence_number=self._sequence_number,
            )

            # 무결성 해시 계산
            if self._integrity_enabled:
                if self._chain_hash_enabled:
                    entry.chain_hash = self._last_chain_hash
                    entry.entry_hash = entry.compute_hash(self._last_chain_hash)
                    self._last_chain_hash = entry.entry_hash
                else:
                    entry.entry_hash = entry.compute_hash("")

            return entry

    def _record_metrics(self, event: AuditEvent) -> None:
        """메트릭 기록."""
        if self._metrics_collector is None:
            return

        try:
            # 이벤트 카운트
            self._metrics_collector.increment(
                "audit_events_total",
                labels={
                    "event_type": event.event_type.value,
                    "severity": event.severity.name_str if event.severity else "info",
                    "result": event.result,
                },
            )
        except Exception as e:
            logger.debug(f"감사 메트릭 기록 실패: {e}")

    def _process_alerts(self, event: AuditEvent) -> None:
        """알림 처리."""
        if not self._alerting_enabled:
            return

        # 즉시 알림 이벤트 확인
        if event.event_type.action in self._immediate_alerts:
            self._send_alert(
                event,
                event.event_type.action,
                f"보안 이벤트 감지: {event.event_type.value}",
            )

    def _send_alert(
        self,
        event: AuditEvent,
        alert_type: str,
        message: str,
    ) -> None:
        """알림 전송."""
        for handler in self._alert_handlers:
            try:
                handler.send_alert(event, alert_type, message)
            except Exception as e:
                logger.error(f"알림 전송 실패 ({type(handler).__name__}): {e}")

    def _write_immediate(self, entry: AuditLogEntry) -> None:
        """즉시 기록."""
        for storage in self._storages:
            try:
                storage.write(entry)
            except Exception as e:
                logger.error(f"감사 로그 즉시 기록 실패 ({type(storage).__name__}): {e}")

    def _add_to_buffer(self, entry: AuditLogEntry) -> None:
        """버퍼에 추가."""
        with self._lock:
            self._buffer.append(entry)

            # 버퍼 크기 초과 시 플러시
            if len(self._buffer) >= self._buffer_size:
                entries_to_write = self._buffer[:]
                self._buffer.clear()

                # 저장소에 기록 (락 해제 후)
                for storage in self._storages:
                    try:
                        storage.write_batch(entries_to_write)
                    except Exception as e:
                        logger.error(f"감사 로그 버퍼 플러시 실패: {e}")

    def log_event(self, event: AuditEvent, immediate: bool = False) -> str | None:
        """
        감사 이벤트 객체 기록.

        Args:
            event: 감사 이벤트
            immediate: 즉시 기록 여부

        Returns:
            로그 항목 ID
        """
        return self.log(
            event_type=event.event_type,
            actor=event.actor,
            action=event.action,
            resource=event.resource,
            result=event.result,
            severity=event.severity,
            request_id=event.request_id,
            session_id=event.session_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            details=event.details,
            metadata=event.metadata,
            immediate=immediate,
        )

    def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        min_severity: AuditSeverity | None = None,
        actor: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """
        감사 로그 조회.

        Args:
            start_time: 시작 시간
            end_time: 종료 시간
            event_types: 이벤트 타입 필터
            min_severity: 최소 심각도
            actor: 행위자 필터
            limit: 최대 항목 수
            offset: 오프셋

        Returns:
            감사 로그 항목 목록
        """
        # 첫 번째 저장소에서 조회
        if not self._storages:
            return []

        return self._storages[0].read(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            min_severity=min_severity,
            actor=actor,
            limit=limit,
            offset=offset,
        )

    def verify_integrity(
        self,
        entries: list[AuditLogEntry] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[bool, list[str]]:
        """
        감사 로그 무결성 검증.

        Args:
            entries: 검증할 로그 항목 (없으면 조회)
            start_time: 시작 시간
            end_time: 종료 시간

        Returns:
            (검증 성공 여부, 오류 메시지 목록)
        """
        if entries is None:
            entries = self.query(
                start_time=start_time,
                end_time=end_time,
                limit=10000,
            )

        if not entries:
            return True, []

        errors: list[str] = []
        previous_hash = INITIAL_CHAIN_HASH

        # 시퀀스 번호로 정렬
        sorted_entries = sorted(entries, key=lambda e: e.sequence_number)

        for entry in sorted_entries:
            if not entry.entry_hash:
                continue

            # 해시 검증
            if not entry.verify_integrity(previous_hash if self._chain_hash_enabled else ""):
                errors.append(
                    f"무결성 검증 실패: ID={entry.id}, 시퀀스={entry.sequence_number}"
                )

            previous_hash = entry.entry_hash

        return len(errors) == 0, errors

    def add_alert_handler(self, handler: BaseAlertHandler) -> None:
        """알림 핸들러 추가."""
        self._alert_handlers.append(handler)

    def add_storage(self, storage: BaseAuditStorage) -> None:
        """저장소 추가."""
        self._storages.append(storage)

    def flush(self) -> None:
        """버퍼 즉시 플러시."""
        self._flush_buffer()

    def close(self) -> None:
        """감사 로거 종료."""
        # 플러시 스레드 중지
        self._stop_flush.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

        # 버퍼 플러시
        self._flush_buffer()

        # 저장소 종료
        for storage in self._storages:
            try:
                storage.close()
            except Exception as e:
                logger.error(f"저장소 종료 실패 ({type(storage).__name__}): {e}")

        logger.info("감사 로거 종료 완료")

    def get_stats(self) -> dict[str, Any]:
        """통계 정보 조회."""
        with self._lock:
            return {
                "sequence_number": self._sequence_number,
                "buffer_size": len(self._buffer),
                "storage_count": len(self._storages),
                "alert_handler_count": len(self._alert_handlers),
                "integrity_enabled": self._integrity_enabled,
                "chain_hash_enabled": self._chain_hash_enabled,
                "alerting_enabled": self._alerting_enabled,
                "sampling_enabled": self._sampling_enabled,
            }


# ============================================================
# 전역 감사 로거 인스턴스 관리
# ============================================================
_audit_logger: AuditLogger | None = None
_audit_logger_lock = threading.RLock()


def get_audit_logger() -> AuditLogger | None:
    """
    전역 감사 로거 인스턴스 조회.

    Returns:
        감사 로거 인스턴스 (없으면 None)
    """
    with _audit_logger_lock:
        return _audit_logger


def set_audit_logger(audit_logger: AuditLogger) -> None:
    """
    전역 감사 로거 인스턴스 설정.

    Args:
        audit_logger: 감사 로거 인스턴스
    """
    global _audit_logger
    with _audit_logger_lock:
        _audit_logger = audit_logger


def log_audit_event(
    event_type: AuditEventType,
    actor: str,
    action: str,
    resource: str,
    result: str = "success",
    severity: AuditSeverity | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    immediate: bool = False,
) -> str | None:
    """
    감사 이벤트 기록 헬퍼 함수.

    전역 감사 로거를 사용하여 이벤트를 기록합니다.

    Args:
        event_type: 이벤트 타입
        actor: 행위자
        action: 동작
        resource: 리소스
        result: 결과
        severity: 심각도
        request_id: 요청 ID
        session_id: 세션 ID
        ip_address: IP 주소
        user_agent: 사용자 에이전트
        details: 상세 정보
        metadata: 메타데이터
        immediate: 즉시 기록 여부

    Returns:
        로그 항목 ID (로거가 없거나 필터링된 경우 None)

    Example:
        >>> log_audit_event(
        ...     event_type=AuditEventType.LOGIN_SUCCESS,
        ...     actor="user@example.com",
        ...     action="login",
        ...     resource="/api/auth/login",
        ... )
    """
    logger_instance = get_audit_logger()
    if logger_instance is None:
        return None

    return logger_instance.log(
        event_type=event_type,
        actor=actor,
        action=action,
        resource=resource,
        result=result,
        severity=severity,
        request_id=request_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        metadata=metadata,
        immediate=immediate,
    )


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "AuditEventType",
    "AuditSeverity",
    # 데이터 클래스
    "AuditEvent",
    "AuditLogEntry",
    # 저장소 클래스
    "BaseAuditStorage",
    "FileAuditStorage",
    "MemoryAuditStorage",
    "CloudWatchAuditStorage",
    "ElasticsearchAuditStorage",
    # 알림 핸들러 클래스
    "BaseAlertHandler",
    "LogAlertHandler",
    "SlackAlertHandler",
    "EmailAlertHandler",
    "WebhookAlertHandler",
    # 추적기 클래스
    "LoginFailureTracker",
    # 메인 클래스
    "AuditLogger",
    # 함수
    "get_audit_logger",
    "set_audit_logger",
    "log_audit_event",
    # 상수
    "EVENT_DEFAULT_SEVERITY",
]
