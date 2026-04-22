# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: license_validator.py
설명: 하드웨어 ID 기반 라이선스 검증
      - 하드웨어 핑거프린트 생성 (CPU, 디스크, MAC)
      - 라이선스 키 검증 (HMAC-SHA256)
      - 라이선스 만료일 확인
      - 라이선스 상태 관리
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
import hmac
import platform
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Final


# =============================================================================
# 상수 정의
# =============================================================================

# 라이선스 서명 키 길이 (바이트)
MIN_LICENSE_KEY_LENGTH: Final[int] = 16

# 하드웨어 ID 해시 알고리즘
HW_HASH_ALGORITHM: Final[str] = "sha256"

# 라이선스 검증 결과 캐시 유효 시간 (초)
LICENSE_CACHE_TTL_SEC: Final[float] = 3600.0

# 기본 평가판 기간 (일)
DEFAULT_TRIAL_DAYS: Final[int] = 30


# =============================================================================
# 라이선스 상태 Enum
# =============================================================================

@unique
class LicenseStatus(Enum):
    """라이선스 상태.

    Members:
        VALID: 유효
        EXPIRED: 만료
        INVALID: 무효 (서명 불일치)
        TRIAL: 평가판
        NOT_CHECKED: 미검증
    """

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    TRIAL = "trial"
    NOT_CHECKED = "not_checked"

    def to_korean(self) -> str:
        """한글 표현."""
        _MAP: dict[LicenseStatus, str] = {
            LicenseStatus.VALID: "유효",
            LicenseStatus.EXPIRED: "만료",
            LicenseStatus.INVALID: "무효",
            LicenseStatus.TRIAL: "평가판",
            LicenseStatus.NOT_CHECKED: "미검증",
        }
        return _MAP[self]

    @property
    def is_active(self) -> bool:
        """활성 (사용 가능) 여부."""
        return self in _ACTIVE_STATUSES


_ACTIVE_STATUSES: Final[frozenset[LicenseStatus]] = frozenset({
    LicenseStatus.VALID,
    LicenseStatus.TRIAL,
})


# =============================================================================
# 라이선스 정보
# =============================================================================

@dataclass(slots=True)
class LicenseInfo:
    """라이선스 정보.

    Attributes:
        status: 라이선스 상태
        hardware_id: 하드웨어 핑거프린트
        license_key: 라이선스 키 (마스킹)
        expires_at: 만료 시각 (epoch, 0이면 무제한)
        issued_at: 발급 시각 (epoch)
        features: 활성화된 기능 목록
        owner: 소유자
        max_cameras: 최대 카메라 수
    """

    status: LicenseStatus
    hardware_id: str
    license_key: str = ""
    expires_at: float = 0.0
    issued_at: float = 0.0
    features: list[str] | None = None
    owner: str = ""
    max_cameras: int = 1

    @property
    def is_active(self) -> bool:
        """활성 여부."""
        return self.status.is_active

    @property
    def is_expired(self) -> bool:
        """만료 여부."""
        if self.expires_at == 0.0:
            return False
        return time.time() > self.expires_at

    @property
    def days_remaining(self) -> int:
        """남은 일수 (만료 없으면 -1)."""
        if self.expires_at == 0.0:
            return -1
        remaining = self.expires_at - time.time()
        return max(0, int(remaining / 86400))

    def __repr__(self) -> str:
        return (
            f"LicenseInfo(status={self.status.value}, "
            f"owner='{self.owner}', "
            f"days_remaining={self.days_remaining})"
        )


# =============================================================================
# 하드웨어 핑거프린트
# =============================================================================

def generate_hardware_id() -> str:
    """하드웨어 핑거프린트 생성.

    구성 요소:
    - 플랫폼 (OS)
    - 프로세서
    - 머신 타입
    - MAC 주소

    Returns:
        SHA-256 해시 (hex)
    """
    components = [
        platform.system(),
        platform.processor(),
        platform.machine(),
        str(uuid.getnode()),
    ]
    payload = "|".join(components)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_license_signature(
    hardware_id: str,
    secret_key: str,
    *,
    owner: str = "",
    expires_at: float = 0.0,
    features: str = "",
) -> str:
    """라이선스 서명 생성 (HMAC-SHA256).

    Args:
        hardware_id: 하드웨어 ID
        secret_key: 서명 키
        owner: 소유자
        expires_at: 만료 시각
        features: 기능 목록 (쉼표 구분)

    Returns:
        HMAC-SHA256 서명 (hex)
    """
    message = f"{hardware_id}|{owner}|{expires_at}|{features}"
    return hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_license_signature(
    hardware_id: str,
    secret_key: str,
    signature: str,
    *,
    owner: str = "",
    expires_at: float = 0.0,
    features: str = "",
) -> bool:
    """라이선스 서명 검증.

    Args:
        hardware_id: 하드웨어 ID
        secret_key: 서명 키
        signature: 검증할 서명
        owner: 소유자
        expires_at: 만료 시각
        features: 기능 목록

    Returns:
        서명 유효 여부
    """
    expected = generate_license_signature(
        hardware_id,
        secret_key,
        owner=owner,
        expires_at=expires_at,
        features=features,
    )
    return hmac.compare_digest(expected, signature)


# =============================================================================
# 핵심 클래스: LicenseValidator
# =============================================================================

class LicenseValidator:
    """라이선스 검증자.

    하드웨어 ID와 라이선스 키를 기반으로 라이선스를 검증한다.

    사용 예시::

        validator = LicenseValidator.get_instance()

        # 라이선스 설정
        validator.set_license(
            license_key="ABCD-EFGH-IJKL-MNOP",
            secret_key="my-secret",
            owner="COURTVIEW",
            expires_at=1735689600.0,  # 2025-01-01
        )

        # 검증
        info = validator.validate()
        if info.is_active:
            print("라이선스 유효")

        # 기능 확인
        if validator.has_feature("ai_referee"):
            enable_ai_referee()

    스레드 안전:
        모든 메서드는 RLock 보호.
    """

    _instance: LicenseValidator | None = None
    _class_lock: threading.RLock = threading.RLock()

    def __init__(self) -> None:
        self._hardware_id = generate_hardware_id()
        self._license_key: str = ""
        self._secret_key: str = ""
        self._owner: str = ""
        self._expires_at: float = 0.0
        self._features: list[str] = []
        self._max_cameras: int = 1
        self._status = LicenseStatus.NOT_CHECKED
        self._last_validation: float = 0.0
        self._lock = threading.RLock()

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> LicenseValidator:
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
    # 속성
    # =========================================================================

    @property
    def hardware_id(self) -> str:
        """하드웨어 핑거프린트."""
        return self._hardware_id

    @property
    def status(self) -> LicenseStatus:
        """현재 라이선스 상태."""
        with self._lock:
            return self._status

    @property
    def is_active(self) -> bool:
        """라이선스 활성 여부."""
        with self._lock:
            return self._status.is_active

    # =========================================================================
    # 라이선스 설정
    # =========================================================================

    def set_license(
        self,
        *,
        license_key: str,
        secret_key: str,
        owner: str = "",
        expires_at: float = 0.0,
        features: list[str] | None = None,
        max_cameras: int = 1,
    ) -> None:
        """라이선스 설정.

        Args:
            license_key: 라이선스 키 (서명)
            secret_key: 비밀 키
            owner: 소유자
            expires_at: 만료 시각 (epoch, 0이면 무제한)
            features: 활성화 기능 목록
            max_cameras: 최대 카메라 수
        """
        with self._lock:
            self._license_key = license_key
            self._secret_key = secret_key
            self._owner = owner
            self._expires_at = expires_at
            self._features = list(features) if features else []
            self._max_cameras = max(1, max_cameras)
            self._status = LicenseStatus.NOT_CHECKED
            self._last_validation = 0.0

    def set_trial(self, *, days: int = DEFAULT_TRIAL_DAYS) -> None:
        """평가판 설정.

        Args:
            days: 평가판 기간 (일)
        """
        with self._lock:
            self._status = LicenseStatus.TRIAL
            self._expires_at = time.time() + (days * 86400)
            self._features = ["basic_analysis"]
            self._max_cameras = 1
            self._owner = "trial"
            self._last_validation = time.monotonic()

    # =========================================================================
    # 검증
    # =========================================================================

    def validate(self) -> LicenseInfo:
        """라이선스 검증.

        Returns:
            LicenseInfo
        """
        with self._lock:
            # 평가판인 경우
            if self._status == LicenseStatus.TRIAL:
                if self._expires_at > 0 and time.time() > self._expires_at:
                    self._status = LicenseStatus.EXPIRED
                return self._build_info()

            # 라이선스 키 없으면 미검증
            if not self._license_key or not self._secret_key:
                self._status = LicenseStatus.NOT_CHECKED
                return self._build_info()

            # 캐시 유효성 확인
            now = time.monotonic()
            if (
                self._status in (LicenseStatus.VALID, LicenseStatus.EXPIRED)
                and now - self._last_validation < LICENSE_CACHE_TTL_SEC
            ):
                return self._build_info()

            # 서명 검증
            features_str = ",".join(sorted(self._features))
            is_valid = verify_license_signature(
                self._hardware_id,
                self._secret_key,
                self._license_key,
                owner=self._owner,
                expires_at=self._expires_at,
                features=features_str,
            )

            if not is_valid:
                self._status = LicenseStatus.INVALID
            elif self._expires_at > 0 and time.time() > self._expires_at:
                self._status = LicenseStatus.EXPIRED
            else:
                self._status = LicenseStatus.VALID

            self._last_validation = now
            return self._build_info()

    # =========================================================================
    # 기능 확인
    # =========================================================================

    def has_feature(self, feature: str) -> bool:
        """기능 활성화 여부.

        Args:
            feature: 기능 이름

        Returns:
            활성화 여부
        """
        with self._lock:
            if not self._status.is_active:
                return False
            return feature in self._features

    def get_features(self) -> list[str]:
        """활성화된 기능 목록 (방어적 복사).

        Returns:
            기능 리스트
        """
        with self._lock:
            return list(self._features)

    @property
    def max_cameras(self) -> int:
        """최대 허용 카메라 수."""
        with self._lock:
            return self._max_cameras

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _build_info(self) -> LicenseInfo:
        """현재 상태로 LicenseInfo 생성."""
        masked_key = ""
        if self._license_key:
            if len(self._license_key) > 8:
                masked_key = self._license_key[:4] + "****" + self._license_key[-4:]
            else:
                masked_key = "****"

        return LicenseInfo(
            status=self._status,
            hardware_id=self._hardware_id,
            license_key=masked_key,
            expires_at=self._expires_at,
            issued_at=0.0,
            features=list(self._features),
            owner=self._owner,
            max_cameras=self._max_cameras,
        )

    def __repr__(self) -> str:
        return (
            f"LicenseValidator("
            f"status={self._status.value}, "
            f"owner='{self._owner}')"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "LicenseStatus",
    # 데이터 클래스
    "LicenseInfo",
    # 유틸리티
    "generate_hardware_id",
    "generate_license_signature",
    "verify_license_signature",
    # 핵심 클래스
    "LicenseValidator",
    # 상수
    "MIN_LICENSE_KEY_LENGTH",
    "HW_HASH_ALGORITHM",
    "LICENSE_CACHE_TTL_SEC",
    "DEFAULT_TRIAL_DAYS",
]

__version__ = "1.0.0"
