# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: secret_manager.py
설명: 시크릿 관리자
      - 환경변수 기반 시크릿 로드
      - 파일 기반 시크릿 로드 (.env, JSON)
      - 인메모리 시크릿 저장소 (런타임 등록)
      - 시크릿 마스킹 (로그 보호)
      - 시크릿 만료 관리
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import json
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Any, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 시크릿 수
MAX_SECRETS: Final[int] = 200

# 마스킹 문자
MASK_CHAR: Final[str] = "*"

# 마스킹 시 노출할 접두사/접미사 길이
MASK_VISIBLE_CHARS: Final[int] = 3

# 기본 만료 시간 없음 (0 = 무제한)
NO_EXPIRY: Final[float] = 0.0


# =============================================================================
# 시크릿 소스 Enum
# =============================================================================

@unique
class SecretSource(Enum):
    """시크릿 소스.

    Members:
        ENV: 환경변수
        FILE: 파일 (.env, JSON)
        RUNTIME: 런타임 등록
    """

    ENV = "env"
    FILE = "file"
    RUNTIME = "runtime"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP: dict[SecretSource, str] = {
            SecretSource.ENV: "환경변수",
            SecretSource.FILE: "파일",
            SecretSource.RUNTIME: "런타임",
        }
        return _MAP[self]


# =============================================================================
# 시크릿 항목
# =============================================================================

@dataclass(slots=True)
class SecretEntry:
    """시크릿 항목.

    Attributes:
        key: 시크릿 키
        value: 시크릿 값
        source: 시크릿 소스
        description: 설명
        created_at: 생성 시각 (monotonic)
        expires_at: 만료 시각 (monotonic, 0이면 무제한)
    """

    key: str
    value: str
    source: SecretSource
    description: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        """만료 여부."""
        if self.expires_at == NO_EXPIRY:
            return False
        return time.monotonic() > self.expires_at

    @property
    def masked_value(self) -> str:
        """마스킹된 값."""
        return mask_secret(self.value)

    def __repr__(self) -> str:
        return (
            f"SecretEntry('{self.key}', "
            f"source={self.source.value}, "
            f"masked={self.masked_value})"
        )


# =============================================================================
# 유틸리티 함수
# =============================================================================

def mask_secret(value: str) -> str:
    """시크릿 값 마스킹.

    짧은 값(6자 이하)은 전부 마스킹.
    긴 값은 앞뒤 MASK_VISIBLE_CHARS만 노출.

    Args:
        value: 원본 값

    Returns:
        마스킹된 문자열
    """
    if len(value) <= MASK_VISIBLE_CHARS * 2:
        return MASK_CHAR * len(value)

    prefix = value[:MASK_VISIBLE_CHARS]
    suffix = value[-MASK_VISIBLE_CHARS:]
    masked_len = len(value) - MASK_VISIBLE_CHARS * 2
    return f"{prefix}{MASK_CHAR * masked_len}{suffix}"


# =============================================================================
# 핵심 클래스: SecretManager
# =============================================================================

class SecretManager:
    """시크릿 관리자.

    환경변수, 파일, 런타임 등록을 통해 시크릿을 관리한다.
    시크릿 값은 마스킹되어 로그에 노출되지 않도록 보호한다.

    사용 예시::

        manager = SecretManager.get_instance()

        # 환경변수에서 로드
        manager.load_from_env("API_KEY")
        manager.load_from_env("DB_PASSWORD", key_alias="db_pass")

        # 런타임 등록
        manager.set("jwt_secret", "my-secret-value", description="JWT 서명 키")

        # 조회
        api_key = manager.get("API_KEY")

        # .env 파일에서 일괄 로드
        manager.load_from_dotenv(Path(".env"))

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: SecretManager | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._secrets: dict[str, SecretEntry] = {}
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> SecretManager:
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
    # 시크릿 등록
    # =========================================================================

    def set(
        self,
        key: str,
        value: str,
        *,
        source: SecretSource = SecretSource.RUNTIME,
        description: str = "",
        ttl_sec: float = NO_EXPIRY,
    ) -> bool:
        """시크릿 등록 또는 갱신.

        Args:
            key: 시크릿 키
            value: 시크릿 값
            source: 시크릿 소스
            description: 설명
            ttl_sec: 만료까지 남은 시간 (초, 0이면 무제한)

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if key not in self._secrets and len(self._secrets) >= MAX_SECRETS:
                return False

            now = time.monotonic()
            expires_at = now + ttl_sec if ttl_sec > 0 else NO_EXPIRY

            self._secrets[key] = SecretEntry(
                key=key,
                value=value,
                source=source,
                description=description,
                created_at=now,
                expires_at=expires_at,
            )
            return True

    # =========================================================================
    # 환경변수 로드
    # =========================================================================

    def load_from_env(
        self,
        env_var: str,
        *,
        key_alias: str | None = None,
        required: bool = False,
        description: str = "",
    ) -> bool:
        """환경변수에서 시크릿 로드.

        Args:
            env_var: 환경변수 이름
            key_alias: 저장할 키 (None이면 env_var 사용)
            required: 필수 여부 (True이면 없을 때 KeyError)
            description: 설명

        Returns:
            로드 성공 여부

        Raises:
            KeyError: required=True인데 환경변수 없을 때
        """
        value = os.environ.get(env_var)
        if value is None:
            if required:
                raise KeyError(f"필수 환경변수 미설정: '{env_var}'")
            return False

        store_key = key_alias or env_var
        return self.set(
            store_key,
            value,
            source=SecretSource.ENV,
            description=description or f"환경변수 {env_var}",
        )

    # =========================================================================
    # 파일 로드
    # =========================================================================

    def load_from_dotenv(self, path: Path) -> int:
        """dotenv 파일에서 시크릿 로드.

        형식: KEY=VALUE (# 주석, 빈 줄 무시)

        Args:
            path: .env 파일 경로

        Returns:
            로드된 시크릿 수

        Raises:
            FileNotFoundError: 파일 없을 때
        """
        if not path.exists():
            raise FileNotFoundError(f"dotenv 파일 없음: {path}")

        count = 0
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # 따옴표 제거
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            if key and self.set(
                key,
                value,
                source=SecretSource.FILE,
                description=f"dotenv: {path.name}",
            ):
                count += 1

        return count

    def load_from_json(self, path: Path) -> int:
        """JSON 파일에서 시크릿 로드.

        형식: {"key": "value", ...} (최상위 딕셔너리)

        Args:
            path: JSON 파일 경로

        Returns:
            로드된 시크릿 수

        Raises:
            FileNotFoundError: 파일 없을 때
            ValueError: JSON 파싱 실패
        """
        if not path.exists():
            raise FileNotFoundError(f"JSON 파일 없음: {path}")

        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 실패: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("JSON 최상위는 딕셔너리여야 합니다")

        count = 0
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                if self.set(
                    key,
                    value,
                    source=SecretSource.FILE,
                    description=f"json: {path.name}",
                ):
                    count += 1

        return count

    # =========================================================================
    # 시크릿 조회
    # =========================================================================

    def get(self, key: str) -> str:
        """시크릿 값 조회.

        Args:
            key: 시크릿 키

        Returns:
            시크릿 값

        Raises:
            KeyError: 미등록 또는 만료된 시크릿
        """
        with self._lock:
            entry = self._secrets.get(key)
            if entry is None:
                raise KeyError(f"미등록 시크릿: '{key}'")

            if entry.is_expired:
                del self._secrets[key]
                raise KeyError(f"만료된 시크릿: '{key}'")

            return entry.value

    def get_optional(self, key: str, default: str = "") -> str:
        """시크릿 값 조회 (없으면 기본값).

        Args:
            key: 시크릿 키
            default: 기본 반환값

        Returns:
            시크릿 값 또는 기본값
        """
        try:
            return self.get(key)
        except KeyError:
            return default

    def get_entry(self, key: str) -> SecretEntry | None:
        """시크릿 항목 조회 (방어적 복사).

        Args:
            key: 시크릿 키

        Returns:
            SecretEntry 또는 None
        """
        with self._lock:
            entry = self._secrets.get(key)
            if entry is None:
                return None

            if entry.is_expired:
                del self._secrets[key]
                return None

            return SecretEntry(
                key=entry.key,
                value=entry.value,
                source=entry.source,
                description=entry.description,
                created_at=entry.created_at,
                expires_at=entry.expires_at,
            )

    def has(self, key: str) -> bool:
        """시크릿 존재 여부 (만료 검사 포함)."""
        with self._lock:
            entry = self._secrets.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._secrets[key]
                return False
            return True

    def get_masked(self, key: str) -> str:
        """마스킹된 시크릿 값.

        Args:
            key: 시크릿 키

        Returns:
            마스킹된 값

        Raises:
            KeyError: 미등록 시크릿
        """
        value = self.get(key)
        return mask_secret(value)

    # =========================================================================
    # 시크릿 제거
    # =========================================================================

    def remove(self, key: str) -> bool:
        """시크릿 제거.

        Args:
            key: 시크릿 키

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if key in self._secrets:
                del self._secrets[key]
                return True
            return False

    def clear(self) -> int:
        """전체 시크릿 제거.

        Returns:
            제거된 수
        """
        with self._lock:
            count = len(self._secrets)
            self._secrets.clear()
            return count

    def cleanup_expired(self) -> int:
        """만료된 시크릿 정리.

        Returns:
            정리된 수
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._secrets.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._secrets[key]
            return len(expired_keys)

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def secret_count(self) -> int:
        """등록된 시크릿 수 (만료 포함)."""
        with self._lock:
            return len(self._secrets)

    @property
    def secret_keys(self) -> list[str]:
        """등록된 시크릿 키 목록."""
        with self._lock:
            return list(self._secrets.keys())

    def all_masked(self) -> dict[str, str]:
        """전체 시크릿 마스킹 조회.

        Returns:
            키 → 마스킹된 값
        """
        with self._lock:
            return {
                key: entry.masked_value
                for key, entry in self._secrets.items()
                if not entry.is_expired
            }

    def __repr__(self) -> str:
        return f"SecretManager(secrets={self.secret_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "SecretSource",
    # 데이터 클래스
    "SecretEntry",
    # 유틸리티
    "mask_secret",
    # 핵심 클래스
    "SecretManager",
    # 상수
    "MAX_SECRETS",
    "MASK_CHAR",
    "MASK_VISIBLE_CHARS",
    "NO_EXPIRY",
]

__version__ = "1.0.0"
