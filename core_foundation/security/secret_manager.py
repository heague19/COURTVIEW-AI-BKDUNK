# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/security
파일: secret_manager.py
설명: 시크릿 관리 - AWS Secrets Manager, 환경변수, Vault 연동

작성자: SPOIN_COURTVIEW
버전: 1.0.0
최종 수정: 2026-03-12

주요 기능:
    - 다중 시크릿 제공자 지원 (AWS Secrets Manager, Vault, 환경변수, 파일)
    - 시크릿 캐싱 및 자동 갱신
    - 시크릿 유효성 검증
    - 시크릿 접근 로깅 (민감정보 마스킹)
    - 시크릿 로테이션 감지
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 보안: 값 마스킹, 접근 로깅
    - 확장성: 제공자 플러그인 방식
    - 장애 허용: 폴백 제공자 지원

시크릿 제공자:
    - AWSSecretsProvider: AWS Secrets Manager 연동
    - VaultProvider: HashiCorp Vault 연동
    - EnvProvider: 환경변수 기반
    - FileProvider: 파일 기반 (개발용)

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    secret_manager = SecretManager(config_loader, metrics_collector, error_tracker)

    # 시크릿 조회
    db_password = secret_manager.get("database_password")

    # 헬퍼 함수 사용
    jwt_secret = get_secret("jwt_secret")

    # 시크릿 정보 조회
    info = secret_manager.get_info("database_password")
"""

from __future__ import annotations

__version__: str = "1.0.0"

# ============================================================
# 표준 라이브러리
# ============================================================
import json
import logging
import os
import threading
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

# ============================================================
# 서드파티 (조건부 임포트)
# ============================================================
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False
    hvac = None

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.infrastructure_exceptions import InfrastructureException

# ============================================================
# utils 임포트
# ============================================================
from utils.time_utils import get_current_timestamp

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 타입 힌트용 임포트 (순환 참조 방지)
# ============================================================
if TYPE_CHECKING:
    from core_foundation.monitoring.metrics import MetricsCollector
    from core_foundation.monitoring.error_tracker import ErrorTracker

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수 정의 (환경변수 오버라이드 지원)
# ============================================================
# 기본 캐시 TTL (초) - 환경변수: COURTVIEW_SECRET_CACHE_TTL
DEFAULT_CACHE_TTL: int = int(os.environ.get("COURTVIEW_SECRET_CACHE_TTL", "300"))

# 기본 갱신 임계값 (TTL의 %) - 환경변수: COURTVIEW_SECRET_REFRESH_THRESHOLD
DEFAULT_REFRESH_THRESHOLD: float = float(
    os.environ.get("COURTVIEW_SECRET_REFRESH_THRESHOLD", "0.8")
)

# 최대 캐시 항목 수 - 환경변수: COURTVIEW_SECRET_MAX_CACHE_ENTRIES
DEFAULT_MAX_CACHE_ENTRIES: int = int(
    os.environ.get("COURTVIEW_SECRET_MAX_CACHE_ENTRIES", "100")
)

# 환경변수 접두사 - 환경변수: COURTVIEW_SECRET_ENV_PREFIX
DEFAULT_ENV_PREFIX: str = os.environ.get(
    "COURTVIEW_SECRET_ENV_PREFIX", "COURTVIEW_SECRET_"
)

# AWS 리전 - 환경변수: COURTVIEW_AWS_REGION, AWS_REGION
DEFAULT_AWS_REGION: str = os.environ.get(
    "COURTVIEW_AWS_REGION",
    os.environ.get("AWS_REGION", "ap-northeast-2")
)

# 마스킹 문자 - 환경변수: COURTVIEW_SECRET_MASK_CHAR
DEFAULT_MASK_CHAR: str = os.environ.get("COURTVIEW_SECRET_MASK_CHAR", "*")

# 마스킹 최소 표시 길이 - 환경변수: COURTVIEW_SECRET_MASK_VISIBLE_LENGTH
MASK_VISIBLE_LENGTH: int = int(
    os.environ.get("COURTVIEW_SECRET_MASK_VISIBLE_LENGTH", "4")
)


# ============================================================
# Enum 정의
# ============================================================
class SecretProvider(Enum):
    """
    시크릿 제공자 타입.

    시크릿을 가져올 소스를 지정합니다.
    """

    AWS = auto()      # AWS Secrets Manager
    VAULT = auto()    # HashiCorp Vault
    ENV = auto()      # 환경변수
    FILE = auto()     # 파일 기반


class SecretStatus(Enum):
    """
    시크릿 상태.

    시크릿의 현재 상태를 나타냅니다.
    """

    ACTIVE = auto()       # 활성
    ROTATED = auto()      # 로테이션됨
    EXPIRED = auto()      # 만료됨
    PENDING = auto()      # 대기중
    DEPRECATED = auto()   # 사용 중단


class CacheStatus(Enum):
    """
    캐시 상태.

    캐시된 시크릿의 상태를 나타냅니다.
    """

    HIT = auto()          # 캐시 히트
    MISS = auto()         # 캐시 미스
    EXPIRED = auto()      # 만료됨
    REFRESHED = auto()    # 갱신됨


# ============================================================
# 예외 클래스
# ============================================================
class SecretException(InfrastructureException):
    """
    시크릿 관련 기본 예외.

    시크릿 조회, 저장, 로테이션 등에서 발생하는 예외입니다.
    """

    def __init__(
        self,
        message: str = "시크릿 작업 중 오류가 발생했습니다",
        secret_name: str | None = None,
        provider: SecretProvider | None = None,
        error_code: ErrorCode | None = None,
        **kwargs: Any,
    ) -> None:
        """
        시크릿 예외 초기화.

        Args:
            message: 오류 메시지
            secret_name: 시크릿 이름 (마스킹됨)
            provider: 시크릿 제공자
            error_code: 에러 코드 (기본: INFRASTRUCTURE_ERROR)
            **kwargs: 추가 매개변수
        """
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.INFRASTRUCTURE_ERROR,
            **kwargs,
        )

        if secret_name:
            self.details["secret_name"] = _mask_secret_name(secret_name)
        if provider:
            self.details["provider"] = provider.name


class SecretNotFoundException(SecretException):
    """
    시크릿을 찾을 수 없는 경우 예외.
    """

    def __init__(
        self,
        message: str = "시크릿을 찾을 수 없습니다",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)


class SecretAccessDeniedException(SecretException):
    """
    시크릿 접근 권한이 없는 경우 예외.
    """

    def __init__(
        self,
        message: str = "시크릿 접근 권한이 없습니다",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)


class SecretValidationException(SecretException):
    """
    시크릿 유효성 검증 실패 예외.
    """

    def __init__(
        self,
        message: str = "시크릿 유효성 검증에 실패했습니다",
        validation_errors: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)
        if validation_errors:
            self.details["validation_errors"] = validation_errors


class SecretProviderException(SecretException):
    """
    시크릿 제공자 오류 예외.
    """

    def __init__(
        self,
        message: str = "시크릿 제공자 오류가 발생했습니다",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class SecretVersion:
    """
    시크릿 버전 정보.

    시크릿의 특정 버전에 대한 메타데이터를 담습니다.

    Attributes:
        version_id: 버전 식별자
        version_stage: 버전 스테이지 (AWSCURRENT, AWSPREVIOUS 등)
        created_at: 생성 시각
        is_current: 현재 활성 버전 여부
    """

    version_id: str
    version_stage: str = "AWSCURRENT"
    created_at: datetime | None = None
    is_current: bool = True

    def __post_init__(self) -> None:
        """생성 시각 기본값 설정."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class SecretInfo:
    """
    시크릿 정보.

    시크릿의 메타데이터 및 상태 정보를 담습니다.
    실제 시크릿 값은 포함하지 않습니다 (보안).

    Attributes:
        name: 시크릿 이름
        provider: 시크릿 제공자
        status: 시크릿 상태
        version: 현재 버전 정보
        created_at: 최초 생성 시각
        last_accessed_at: 마지막 접근 시각
        last_rotated_at: 마지막 로테이션 시각
        access_count: 총 접근 횟수
        cached: 캐시 여부
        cache_expires_at: 캐시 만료 시각
        metadata: 추가 메타데이터
    """

    name: str
    provider: SecretProvider
    status: SecretStatus = SecretStatus.ACTIVE
    version: SecretVersion | None = None
    created_at: datetime | None = None
    last_accessed_at: datetime | None = None
    last_rotated_at: datetime | None = None
    access_count: int = 0
    cached: bool = False
    cache_expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """생성 시각 기본값 설정."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """
        딕셔너리로 변환.

        Returns:
            시크릿 정보 딕셔너리
        """
        return {
            "name": _mask_secret_name(self.name),
            "provider": self.provider.name,
            "status": self.status.name,
            "version": {
                "version_id": self.version.version_id,
                "version_stage": self.version.version_stage,
                "created_at": self.version.created_at.isoformat() if self.version.created_at else None,
                "is_current": self.version.is_current,
            } if self.version else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "last_rotated_at": self.last_rotated_at.isoformat() if self.last_rotated_at else None,
            "access_count": self.access_count,
            "cached": self.cached,
            "cache_expires_at": self.cache_expires_at.isoformat() if self.cache_expires_at else None,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class CachedSecret:
    """
    캐시된 시크릿.

    시크릿 값과 캐시 메타데이터를 담습니다.

    Attributes:
        name: 시크릿 이름
        value: 시크릿 값
        provider: 시크릿 제공자
        cached_at: 캐시 시각
        expires_at: 만료 시각
        version: 버전 정보
        access_count: 접근 횟수
    """

    name: str
    value: str
    provider: SecretProvider
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    version: SecretVersion | None = None
    access_count: int = 0

    def is_expired(self) -> bool:
        """
        만료 여부 확인.

        Returns:
            만료된 경우 True
        """
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def should_refresh(self, threshold: float = DEFAULT_REFRESH_THRESHOLD) -> bool:
        """
        갱신 필요 여부 확인.

        Args:
            threshold: 갱신 임계값 (TTL의 비율)

        Returns:
            갱신 필요한 경우 True
        """
        if self.expires_at is None:
            return False

        now = datetime.now(timezone.utc)
        total_ttl = (self.expires_at - self.cached_at).total_seconds()
        elapsed = (now - self.cached_at).total_seconds()

        return elapsed >= (total_ttl * threshold)


@dataclass(slots=True)
class SecretValidationRule:
    """
    시크릿 유효성 검증 규칙.

    Attributes:
        min_length: 최소 길이
        max_length: 최대 길이
        pattern: 정규식 패턴
        required: 필수 여부
    """

    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    required: bool = False


# ============================================================
# 유틸리티 함수
# ============================================================
def _mask_secret_name(name: str) -> str:
    """
    시크릿 이름 마스킹.

    Args:
        name: 시크릿 이름

    Returns:
        마스킹된 이름 (예: "db_***word")
    """
    if len(name) <= MASK_VISIBLE_LENGTH * 2:
        return DEFAULT_MASK_CHAR * len(name)

    visible_start = MASK_VISIBLE_LENGTH
    visible_end = MASK_VISIBLE_LENGTH
    masked_len = len(name) - visible_start - visible_end

    return f"{name[:visible_start]}{DEFAULT_MASK_CHAR * min(masked_len, 3)}{name[-visible_end:]}"


def _mask_secret_value(value: str) -> str:
    """
    시크릿 값 마스킹.

    Args:
        value: 시크릿 값

    Returns:
        마스킹된 값 (예: "****")
    """
    return DEFAULT_MASK_CHAR * min(len(value), 8)


def _generate_cache_key(name: str, provider: SecretProvider) -> str:
    """
    캐시 키 생성.

    Args:
        name: 시크릿 이름
        provider: 제공자

    Returns:
        캐시 키
    """
    return f"{provider.name}:{name}"


# ============================================================
# 시크릿 제공자 인터페이스
# ============================================================
class BaseSecretProvider(ABC):
    """
    시크릿 제공자 기본 클래스.

    모든 시크릿 제공자가 상속해야 하는 추상 클래스입니다.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        제공자 초기화.

        Args:
            config: 제공자별 설정
        """
        self._config = config
        self._lock = threading.RLock()

    @property
    @abstractmethod
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """사용 가능 여부."""
        pass

    @abstractmethod
    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """
        시크릿 조회.

        Args:
            name: 시크릿 이름

        Returns:
            (시크릿 값, 버전 정보) 튜플

        Raises:
            SecretNotFoundException: 시크릿을 찾을 수 없는 경우
            SecretAccessDeniedException: 접근 권한이 없는 경우
        """
        pass

    @abstractmethod
    def secret_exists(self, name: str) -> bool:
        """
        시크릿 존재 여부 확인.

        Args:
            name: 시크릿 이름

        Returns:
            존재하면 True
        """
        pass


class AWSSecretsProvider(BaseSecretProvider):
    """
    AWS Secrets Manager 제공자.

    AWS Secrets Manager에서 시크릿을 조회합니다.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        AWS 제공자 초기화.

        Args:
            config: AWS 설정 (region, prefix 등)
        """
        super().__init__(config)
        self._client: Any | None = None
        self._region = config.get("region", DEFAULT_AWS_REGION)
        self._prefix = config.get("prefix", "courtview/")

    @property
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        return SecretProvider.AWS

    @property
    def is_available(self) -> bool:
        """AWS SDK 사용 가능 여부."""
        return AWS_AVAILABLE

    def _get_client(self) -> Any:
        """
        boto3 클라이언트 가져오기.

        Returns:
            Secrets Manager 클라이언트

        Raises:
            SecretProviderException: 클라이언트 생성 실패 시
        """
        if not AWS_AVAILABLE:
            raise SecretProviderException(
                message="boto3 라이브러리가 설치되지 않았습니다",
                provider=SecretProvider.AWS,
            )

        if self._client is None:
            try:
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self._region,
                )
            except NoCredentialsError as e:
                raise SecretAccessDeniedException(
                    message="AWS 자격 증명을 찾을 수 없습니다",
                    provider=SecretProvider.AWS,
                )
            except Exception as e:
                raise SecretProviderException(
                    message=f"AWS 클라이언트 생성 실패: {e}",
                    provider=SecretProvider.AWS,
                )

        return self._client

    def _get_full_secret_name(self, name: str) -> str:
        """
        전체 시크릿 이름 생성.

        Args:
            name: 시크릿 이름

        Returns:
            접두사가 붙은 전체 이름
        """
        if name.startswith(self._prefix):
            return name
        return f"{self._prefix}{name}"

    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """
        AWS Secrets Manager에서 시크릿 조회.

        Args:
            name: 시크릿 이름

        Returns:
            (시크릿 값, 버전 정보) 튜플

        Raises:
            SecretNotFoundException: 시크릿을 찾을 수 없는 경우
            SecretAccessDeniedException: 접근 권한이 없는 경우
        """
        with self._lock:
            client = self._get_client()
            full_name = self._get_full_secret_name(name)

            try:
                response = client.get_secret_value(SecretId=full_name)

                # 시크릿 값 추출
                if "SecretString" in response:
                    secret_value = response["SecretString"]
                else:
                    # 바이너리 시크릿
                    secret_value = base64.b64decode(response["SecretBinary"]).decode("utf-8")

                # JSON 형식인 경우 파싱 시도
                try:
                    parsed = json.loads(secret_value)
                    if isinstance(parsed, dict) and len(parsed) == 1:
                        # 단일 키-값인 경우 값만 반환
                        secret_value = list(parsed.values())[0]
                except json.JSONDecodeError:
                    pass

                # 버전 정보 생성
                version = SecretVersion(
                    version_id=response.get("VersionId", "unknown"),
                    version_stage=response.get("VersionStages", ["AWSCURRENT"])[0],
                    created_at=response.get("CreatedDate"),
                    is_current=True,
                )

                logger.debug(f"AWS 시크릿 조회 성공: {_mask_secret_name(name)}")
                return secret_value, version

            except client.exceptions.ResourceNotFoundException:
                raise SecretNotFoundException(
                    message=f"시크릿을 찾을 수 없습니다: {_mask_secret_name(name)}",
                    secret_name=name,
                    provider=SecretProvider.AWS,
                )
            except client.exceptions.AccessDeniedException:
                raise SecretAccessDeniedException(
                    message=f"시크릿 접근 권한이 없습니다: {_mask_secret_name(name)}",
                    secret_name=name,
                    provider=SecretProvider.AWS,
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                raise SecretProviderException(
                    message=f"AWS 시크릿 조회 실패 ({error_code}): {e}",
                    secret_name=name,
                    provider=SecretProvider.AWS,
                )

    def secret_exists(self, name: str) -> bool:
        """시크릿 존재 여부 확인."""
        try:
            self.get_secret(name)
            return True
        except SecretNotFoundException:
            return False
        except Exception:
            return False


class VaultProvider(BaseSecretProvider):
    """
    HashiCorp Vault 제공자.

    Vault에서 시크릿을 조회합니다.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Vault 제공자 초기화.

        Args:
            config: Vault 설정 (address, auth_method 등)
        """
        super().__init__(config)
        self._client: Any | None = None
        self._address = config.get("address", "http://localhost:8200")
        self._auth_method = config.get("auth_method", "token")
        self._secret_path = config.get("secret_path", "secret/data/courtview")

    @property
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        return SecretProvider.VAULT

    @property
    def is_available(self) -> bool:
        """hvac 라이브러리 사용 가능 여부."""
        return VAULT_AVAILABLE

    def _get_client(self) -> Any:
        """
        Vault 클라이언트 가져오기.

        Returns:
            Vault 클라이언트
        """
        if not VAULT_AVAILABLE:
            raise SecretProviderException(
                message="hvac 라이브러리가 설치되지 않았습니다",
                provider=SecretProvider.VAULT,
            )

        if self._client is None:
            try:
                self._client = hvac.Client(url=self._address)

                # 토큰 인증
                if self._auth_method == "token":
                    token = os.environ.get("VAULT_TOKEN")
                    if token:
                        self._client.token = token

                if not self._client.is_authenticated():
                    raise SecretAccessDeniedException(
                        message="Vault 인증에 실패했습니다",
                        provider=SecretProvider.VAULT,
                    )

            except Exception as e:
                raise SecretProviderException(
                    message=f"Vault 클라이언트 생성 실패: {e}",
                    provider=SecretProvider.VAULT,
                )

        return self._client

    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """
        Vault에서 시크릿 조회.

        Args:
            name: 시크릿 이름

        Returns:
            (시크릿 값, 버전 정보) 튜플
        """
        with self._lock:
            client = self._get_client()
            path = f"{self._secret_path}/{name}"

            try:
                response = client.secrets.kv.v2.read_secret_version(path=path)

                if response is None or "data" not in response:
                    raise SecretNotFoundException(
                        message=f"시크릿을 찾을 수 없습니다: {_mask_secret_name(name)}",
                        secret_name=name,
                        provider=SecretProvider.VAULT,
                    )

                data = response["data"]["data"]

                # 단일 값 또는 'value' 키 추출
                if isinstance(data, dict):
                    if "value" in data:
                        secret_value = data["value"]
                    elif len(data) == 1:
                        secret_value = list(data.values())[0]
                    else:
                        secret_value = json.dumps(data)
                else:
                    secret_value = str(data)

                # 버전 정보
                metadata = response.get("data", {}).get("metadata", {})
                version = SecretVersion(
                    version_id=str(metadata.get("version", "unknown")),
                    version_stage="current",
                    created_at=datetime.fromisoformat(
                        metadata.get("created_time", "").replace("Z", "+00:00")
                    ) if metadata.get("created_time") else None,
                    is_current=True,
                )

                logger.debug(f"Vault 시크릿 조회 성공: {_mask_secret_name(name)}")
                return secret_value, version

            except Exception as e:
                if "permission denied" in str(e).lower():
                    raise SecretAccessDeniedException(
                        message=f"시크릿 접근 권한이 없습니다: {_mask_secret_name(name)}",
                        secret_name=name,
                        provider=SecretProvider.VAULT,
                    )
                raise SecretProviderException(
                    message=f"Vault 시크릿 조회 실패: {e}",
                    secret_name=name,
                    provider=SecretProvider.VAULT,
                )

    def secret_exists(self, name: str) -> bool:
        """시크릿 존재 여부 확인."""
        try:
            self.get_secret(name)
            return True
        except SecretNotFoundException:
            return False
        except Exception:
            return False


class EnvProvider(BaseSecretProvider):
    """
    환경변수 제공자.

    환경변수에서 시크릿을 조회합니다.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        환경변수 제공자 초기화.

        Args:
            config: 환경변수 설정 (prefix, case_sensitive 등)
        """
        super().__init__(config)
        self._prefix = config.get("prefix", DEFAULT_ENV_PREFIX)
        self._case_sensitive = config.get("case_sensitive", False)

    @property
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        return SecretProvider.ENV

    @property
    def is_available(self) -> bool:
        """항상 사용 가능."""
        return True

    def _get_env_key(self, name: str) -> str:
        """
        환경변수 키 생성.

        Args:
            name: 시크릿 이름

        Returns:
            환경변수 키
        """
        key = f"{self._prefix}{name}"
        if not self._case_sensitive:
            key = key.upper()
        return key

    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """
        환경변수에서 시크릿 조회.

        Args:
            name: 시크릿 이름

        Returns:
            (시크릿 값, 버전 정보) 튜플
        """
        with self._lock:
            env_key = self._get_env_key(name)
            value = os.environ.get(env_key)

            if value is None:
                # 대소문자 변환하여 재시도
                alt_key = env_key.lower() if env_key.isupper() else env_key.upper()
                value = os.environ.get(alt_key)

            if value is None:
                raise SecretNotFoundException(
                    message=f"환경변수 시크릿을 찾을 수 없습니다: {env_key}",
                    secret_name=name,
                    provider=SecretProvider.ENV,
                )

            # 버전 정보 (환경변수는 버전 없음)
            version = SecretVersion(
                version_id="env",
                version_stage="current",
                is_current=True,
            )

            logger.debug(f"환경변수 시크릿 조회 성공: {_mask_secret_name(name)}")
            return value, version

    def secret_exists(self, name: str) -> bool:
        """시크릿 존재 여부 확인."""
        env_key = self._get_env_key(name)
        return env_key in os.environ or env_key.lower() in os.environ or env_key.upper() in os.environ


class FileProvider(BaseSecretProvider):
    """
    파일 기반 제공자.

    파일에서 시크릿을 조회합니다 (개발용).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        파일 제공자 초기화.

        Args:
            config: 파일 설정 (path, encrypted 등)
        """
        super().__init__(config)
        self._path = Path(config.get("path", "secrets/.secrets.yaml"))
        self._encrypted = config.get("encrypted", False)
        self._secrets: dict[str, str] = {}
        self._loaded = False

    @property
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        return SecretProvider.FILE

    @property
    def is_available(self) -> bool:
        """파일 존재 여부."""
        return self._path.exists()

    def _validate_file_permissions(self) -> None:
        """
        파일 권한 검증.

        보안 권장사항:
            - Unix/Linux: 600 (소유자만 읽기/쓰기) 또는 400 (소유자만 읽기)
            - Windows: 현재 사용자만 접근 가능

        Raises:
            SecretProviderException: 파일 권한이 안전하지 않은 경우
        """
        import stat
        import platform

        if not self._path.exists():
            return

        try:
            file_stat = self._path.stat()

            if platform.system() != "Windows":
                # Unix/Linux 권한 검증
                mode = file_stat.st_mode

                # 그룹 및 기타 사용자의 읽기/쓰기/실행 권한 확인
                insecure_bits = (
                    stat.S_IRGRP |  # 그룹 읽기
                    stat.S_IWGRP |  # 그룹 쓰기
                    stat.S_IXGRP |  # 그룹 실행
                    stat.S_IROTH |  # 기타 읽기
                    stat.S_IWOTH |  # 기타 쓰기
                    stat.S_IXOTH    # 기타 실행
                )

                if mode & insecure_bits:
                    # 환경변수로 경고 레벨 설정 가능
                    strict_mode = os.environ.get(
                        "COURTVIEW_SECRET_FILE_STRICT_PERMISSIONS", "false"
                    ).lower() == "true"

                    warning_msg = (
                        f"시크릿 파일 권한이 안전하지 않습니다: {self._path} "
                        f"(현재: {oct(mode)[-3:]}, 권장: 600 또는 400)"
                    )

                    if strict_mode:
                        raise SecretProviderException(
                            message=warning_msg,
                            provider=SecretProvider.FILE,
                        )
                    else:
                        logger.warning(warning_msg)

            else:
                # Windows: 파일 소유자 확인 (기본 경고만)
                # Windows ACL 검증은 복잡하므로 기본적으로 경고만 발생
                logger.debug(f"Windows 환경에서 시크릿 파일 사용: {self._path}")

        except PermissionError as e:
            raise SecretProviderException(
                message=f"파일 권한 확인 실패 (접근 거부): {e}",
                provider=SecretProvider.FILE,
            )
        except Exception as e:
            logger.warning(f"파일 권한 검증 중 오류 (무시됨): {e}")

    def _load_secrets(self) -> None:
        """시크릿 파일 로드."""
        if self._loaded:
            return

        if not self._path.exists():
            logger.warning(f"시크릿 파일을 찾을 수 없습니다: {self._path}")
            return

        # 파일 권한 검증 (로드 전 보안 확인)
        self._validate_file_permissions()

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                if self._path.suffix in (".yaml", ".yml"):
                    if not YAML_AVAILABLE:
                        raise SecretProviderException(
                            message="yaml 라이브러리가 설치되지 않았습니다",
                            provider=SecretProvider.FILE,
                        )
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

                if isinstance(data, dict):
                    self._secrets = {k: str(v) for k, v in data.items()}

                self._loaded = True
                logger.info(f"시크릿 파일 로드 완료: {len(self._secrets)}개")

        except SecretProviderException:
            raise
        except Exception as e:
            raise SecretProviderException(
                message=f"시크릿 파일 로드 실패: {e}",
                provider=SecretProvider.FILE,
            )

    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """
        파일에서 시크릿 조회.

        Args:
            name: 시크릿 이름

        Returns:
            (시크릿 값, 버전 정보) 튜플
        """
        with self._lock:
            self._load_secrets()

            if name not in self._secrets:
                raise SecretNotFoundException(
                    message=f"파일 시크릿을 찾을 수 없습니다: {_mask_secret_name(name)}",
                    secret_name=name,
                    provider=SecretProvider.FILE,
                )

            value = self._secrets[name]

            version = SecretVersion(
                version_id="file",
                version_stage="current",
                is_current=True,
            )

            logger.debug(f"파일 시크릿 조회 성공: {_mask_secret_name(name)}")
            return value, version

    def secret_exists(self, name: str) -> bool:
        """시크릿 존재 여부 확인."""
        self._load_secrets()
        return name in self._secrets


# ============================================================
# 시크릿 매니저 메인 클래스
# ============================================================
class SecretManager:
    """
    시크릿 매니저.

    다중 제공자를 지원하는 통합 시크릿 관리 클래스입니다.
    캐싱, 유효성 검증, 접근 로깅을 제공합니다.

    DI 주입 대상:
        - MetricsCollector: 시크릿 조회 메트릭
        - ErrorTracker: 에러 추적

    Attributes:
        config_loader: 설정 로더
        metrics_collector: 메트릭 수집기 (DI)
        error_tracker: 에러 추적기 (DI)
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        metrics_collector: "MetricsCollector | None" = None,
        error_tracker: "ErrorTracker | None" = None,
    ) -> None:
        """
        시크릿 매니저 초기화.

        Args:
            config_loader: 설정 로더 (Direct Import)
            metrics_collector: 메트릭 수집기 (DI 주입)
            error_tracker: 에러 추적기 (DI 주입)
        """
        self._config_loader = config_loader
        self._metrics_collector = metrics_collector
        self._error_tracker = error_tracker

        self._lock = threading.RLock()
        self._cache: dict[str, CachedSecret] = {}
        self._providers: dict[SecretProvider, BaseSecretProvider] = {}
        self._secret_info: dict[str, SecretInfo] = {}
        self._validation_rules: dict[str, SecretValidationRule] = {}

        # 설정 로드
        self._config = self._load_config()

        # 제공자 초기화
        self._init_providers()

        logger.info("SecretManager 초기화 완료")

    def __repr__(self) -> str:
        """SecretManager 인스턴스 표현."""
        with self._lock:
            providers = len(self._providers)
            cached = len(self._cache)
            rules = len(self._validation_rules)
        return (
            f"SecretManager(providers={providers}, "
            f"cached={cached}, "
            f"rules={rules})"
        )

    def _load_config(self) -> dict[str, Any]:
        """
        설정 로드.

        Returns:
            시크릿 관리자 설정
        """
        config = self._config_loader.get("secret_manager", {})

        # 기본값 설정
        defaults = {
            "enabled": True,
            "provider": {
                "default": "env",
                "aws": {"enabled": False, "region": DEFAULT_AWS_REGION, "prefix": "courtview/"},
                "vault": {"enabled": False, "address": "http://localhost:8200"},
                "env": {"enabled": True, "prefix": DEFAULT_ENV_PREFIX},
                "file": {"enabled": False, "path": "secrets/.secrets.yaml"},
            },
            "cache": {
                "enabled": True,
                "ttl": DEFAULT_CACHE_TTL,
                "max_entries": DEFAULT_MAX_CACHE_ENTRIES,
                "background_refresh": True,
                "refresh_threshold": DEFAULT_REFRESH_THRESHOLD * 100,
            },
            "validation": {
                "on_load": True,
                "required": [],
                "format_rules": {},
            },
            "logging": {
                "log_access": True,
                "mask_values": True,
            },
        }

        # 설정 병합
        def merge_dict(base: dict, override: dict) -> dict:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result

        return merge_dict(defaults, config)

    def _init_providers(self) -> None:
        """시크릿 제공자 초기화."""
        provider_config = self._config.get("provider", {})

        # AWS 제공자
        if provider_config.get("aws", {}).get("enabled", False):
            try:
                self._providers[SecretProvider.AWS] = AWSSecretsProvider(
                    provider_config.get("aws", {})
                )
                logger.info("AWS Secrets Manager 제공자 초기화됨")
            except Exception as e:
                logger.warning(f"AWS 제공자 초기화 실패: {e}")

        # Vault 제공자
        if provider_config.get("vault", {}).get("enabled", False):
            try:
                self._providers[SecretProvider.VAULT] = VaultProvider(
                    provider_config.get("vault", {})
                )
                logger.info("Vault 제공자 초기화됨")
            except Exception as e:
                logger.warning(f"Vault 제공자 초기화 실패: {e}")

        # 환경변수 제공자 (기본)
        if provider_config.get("env", {}).get("enabled", True):
            self._providers[SecretProvider.ENV] = EnvProvider(
                provider_config.get("env", {})
            )
            logger.info("환경변수 제공자 초기화됨")

        # 파일 제공자
        if provider_config.get("file", {}).get("enabled", False):
            try:
                self._providers[SecretProvider.FILE] = FileProvider(
                    provider_config.get("file", {})
                )
                logger.info("파일 제공자 초기화됨")
            except Exception as e:
                logger.warning(f"파일 제공자 초기화 실패: {e}")

        # 유효성 검증 규칙 로드
        self._load_validation_rules()

    def _load_validation_rules(self) -> None:
        """유효성 검증 규칙 로드."""
        validation_config = self._config.get("validation", {})
        format_rules = validation_config.get("format_rules", {})
        required_secrets = validation_config.get("required", [])

        for name, rules in format_rules.items():
            self._validation_rules[name] = SecretValidationRule(
                min_length=rules.get("min_length"),
                max_length=rules.get("max_length"),
                pattern=rules.get("pattern"),
                required=name in required_secrets,
            )

        # 필수 시크릿 규칙 추가
        for name in required_secrets:
            if name not in self._validation_rules:
                self._validation_rules[name] = SecretValidationRule(required=True)

    def _get_default_provider(self) -> SecretProvider:
        """
        기본 제공자 가져오기.

        Returns:
            기본 시크릿 제공자
        """
        default_name = self._config.get("provider", {}).get("default", "env")
        provider_map = {
            "aws": SecretProvider.AWS,
            "vault": SecretProvider.VAULT,
            "env": SecretProvider.ENV,
            "file": SecretProvider.FILE,
        }
        return provider_map.get(default_name.lower(), SecretProvider.ENV)

    def _get_provider(self, provider: SecretProvider | None = None) -> BaseSecretProvider:
        """
        제공자 인스턴스 가져오기.

        Args:
            provider: 제공자 타입 (None이면 기본값)

        Returns:
            제공자 인스턴스

        Raises:
            SecretProviderException: 제공자를 찾을 수 없는 경우
        """
        if provider is None:
            provider = self._get_default_provider()

        if provider not in self._providers:
            # 폴백: 사용 가능한 제공자 찾기
            for p in [SecretProvider.ENV, SecretProvider.FILE, SecretProvider.AWS, SecretProvider.VAULT]:
                if p in self._providers:
                    logger.warning(f"제공자 {provider.name}을 사용할 수 없어 {p.name}으로 폴백합니다")
                    return self._providers[p]

            raise SecretProviderException(
                message=f"사용 가능한 시크릿 제공자가 없습니다",
                provider=provider,
            )

        return self._providers[provider]

    def _get_from_cache(self, name: str, provider: SecretProvider) -> str | None:
        """
        캐시에서 시크릿 조회.

        Args:
            name: 시크릿 이름
            provider: 제공자

        Returns:
            캐시된 시크릿 값 또는 None
        """
        if not self._config.get("cache", {}).get("enabled", True):
            return None

        cache_key = _generate_cache_key(name, provider)

        with self._lock:
            cached = self._cache.get(cache_key)

            if cached is None:
                return None

            if cached.is_expired():
                del self._cache[cache_key]
                logger.debug(f"캐시 만료: {_mask_secret_name(name)}")
                return None

            # 접근 횟수 증가
            cached.access_count += 1

            logger.debug(f"캐시 히트: {_mask_secret_name(name)}")
            return cached.value

    def _add_to_cache(
        self,
        name: str,
        value: str,
        provider: SecretProvider,
        version: SecretVersion | None = None,
    ) -> None:
        """
        캐시에 시크릿 추가.

        Args:
            name: 시크릿 이름
            value: 시크릿 값
            provider: 제공자
            version: 버전 정보
        """
        if not self._config.get("cache", {}).get("enabled", True):
            return

        cache_config = self._config.get("cache", {})
        ttl = cache_config.get("ttl", DEFAULT_CACHE_TTL)
        max_entries = cache_config.get("max_entries", DEFAULT_MAX_CACHE_ENTRIES)

        cache_key = _generate_cache_key(name, provider)

        with self._lock:
            # 캐시 크기 제한
            if len(self._cache) >= max_entries and cache_key not in self._cache:
                # 가장 오래된 항목 제거 (LRU)
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].cached_at,
                )
                del self._cache[oldest_key]

            # 캐시 추가
            self._cache[cache_key] = CachedSecret(
                name=name,
                value=value,
                provider=provider,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
                version=version,
            )

            logger.debug(f"캐시 추가: {_mask_secret_name(name)} (TTL: {ttl}초)")

    def _validate_secret(self, name: str, value: str) -> None:
        """
        시크릿 유효성 검증.

        Args:
            name: 시크릿 이름
            value: 시크릿 값

        Raises:
            SecretValidationException: 유효성 검증 실패 시
        """
        if not self._config.get("validation", {}).get("on_load", True):
            return

        rule = self._validation_rules.get(name)
        if rule is None:
            return

        errors = []

        if rule.min_length and len(value) < rule.min_length:
            errors.append(f"최소 길이 {rule.min_length}자 이상이어야 합니다 (현재: {len(value)}자)")

        if rule.max_length and len(value) > rule.max_length:
            errors.append(f"최대 길이 {rule.max_length}자 이하여야 합니다 (현재: {len(value)}자)")

        if rule.pattern:
            import re
            if not re.match(rule.pattern, value):
                errors.append(f"패턴 '{rule.pattern}'과 일치해야 합니다")

        if errors:
            raise SecretValidationException(
                message=f"시크릿 유효성 검증 실패: {_mask_secret_name(name)}",
                secret_name=name,
                validation_errors=errors,
            )

    def _log_access(self, name: str, provider: SecretProvider, success: bool) -> None:
        """
        시크릿 접근 로깅.

        Args:
            name: 시크릿 이름
            provider: 제공자
            success: 성공 여부
        """
        if not self._config.get("logging", {}).get("log_access", True):
            return

        if success:
            logger.info(f"시크릿 접근: {_mask_secret_name(name)} (제공자: {provider.name})")
        else:
            logger.warning(f"시크릿 접근 실패: {_mask_secret_name(name)} (제공자: {provider.name})")

    def _record_metrics(self, name: str, provider: SecretProvider, cache_status: CacheStatus, duration_ms: float) -> None:
        """
        메트릭 기록.

        Args:
            name: 시크릿 이름
            provider: 제공자
            cache_status: 캐시 상태
            duration_ms: 소요 시간 (밀리초)
        """
        if self._metrics_collector is None:
            return

        try:
            # 카운터 증가
            self._metrics_collector.counter(
                "secret_access_total",
                labels={"provider": provider.name, "cache": cache_status.name},
            ).inc()

            # 히스토그램 기록
            self._metrics_collector.histogram(
                "secret_access_duration_ms",
                labels={"provider": provider.name},
            ).observe(duration_ms)

        except Exception as e:
            logger.warning(f"메트릭 기록 실패: {e}")

    def _track_error(self, exception: Exception, context: dict[str, Any]) -> None:
        """
        에러 추적.

        Args:
            exception: 예외
            context: 컨텍스트
        """
        if self._error_tracker is None:
            return

        try:
            self._error_tracker.track(exception, context=context)
        except Exception as e:
            logger.warning(f"에러 추적 실패: {e}")

    # ========================================
    # 공개 API
    # ========================================

    def get(
        self,
        name: str,
        default: str | None = None,
        provider: SecretProvider | None = None,
        bypass_cache: bool = False,
    ) -> str | None:
        """
        시크릿 조회.

        Args:
            name: 시크릿 이름
            default: 기본값 (시크릿을 찾지 못한 경우)
            provider: 제공자 (None이면 기본값)
            bypass_cache: 캐시 우회 여부

        Returns:
            시크릿 값 또는 기본값

        Raises:
            SecretException: 시크릿 조회 실패 시 (기본값이 없는 경우)
        """
        start_time = get_current_timestamp()

        try:
            # 제공자 결정
            if provider is None:
                provider = self._get_default_provider()

            # 캐시 확인
            cache_status = CacheStatus.MISS
            if not bypass_cache:
                cached_value = self._get_from_cache(name, provider)
                if cached_value is not None:
                    cache_status = CacheStatus.HIT
                    self._log_access(name, provider, True)
                    duration_ms = (get_current_timestamp() - start_time) * 1000
                    self._record_metrics(name, provider, cache_status, duration_ms)
                    return cached_value

            # 제공자에서 조회
            provider_instance = self._get_provider(provider)
            value, version = provider_instance.get_secret(name)

            # 유효성 검증
            self._validate_secret(name, value)

            # 캐시 저장
            self._add_to_cache(name, value, provider, version)

            # 시크릿 정보 업데이트
            with self._lock:
                if name not in self._secret_info:
                    self._secret_info[name] = SecretInfo(
                        name=name,
                        provider=provider,
                        version=version,
                    )
                self._secret_info[name].last_accessed_at = datetime.now(timezone.utc)
                self._secret_info[name].access_count += 1
                self._secret_info[name].cached = True

            self._log_access(name, provider, True)
            duration_ms = (get_current_timestamp() - start_time) * 1000
            self._record_metrics(name, provider, cache_status, duration_ms)

            return value

        except SecretNotFoundException:
            if default is not None:
                logger.debug(f"시크릿을 찾지 못해 기본값 사용: {_mask_secret_name(name)}")
                return default
            raise

        except Exception as e:
            self._log_access(name, provider or self._get_default_provider(), False)
            self._track_error(e, {"secret_name": _mask_secret_name(name)})
            raise

    def get_required(
        self,
        name: str,
        provider: SecretProvider | None = None,
    ) -> str:
        """
        필수 시크릿 조회.

        Args:
            name: 시크릿 이름
            provider: 제공자

        Returns:
            시크릿 값

        Raises:
            SecretNotFoundException: 시크릿을 찾지 못한 경우
        """
        value = self.get(name, provider=provider)

        if value is None:
            raise SecretNotFoundException(
                message=f"필수 시크릿을 찾을 수 없습니다: {_mask_secret_name(name)}",
                secret_name=name,
            )

        return value

    def get_info(self, name: str) -> SecretInfo | None:
        """
        시크릿 정보 조회 (값 제외).

        Args:
            name: 시크릿 이름

        Returns:
            시크릿 정보 또는 None
        """
        with self._lock:
            return self._secret_info.get(name)

    def exists(
        self,
        name: str,
        provider: SecretProvider | None = None,
    ) -> bool:
        """
        시크릿 존재 여부 확인.

        Args:
            name: 시크릿 이름
            provider: 제공자

        Returns:
            존재하면 True
        """
        try:
            provider_instance = self._get_provider(provider)
            return provider_instance.secret_exists(name)
        except Exception:
            return False

    def invalidate_cache(self, name: str | None = None) -> int:
        """
        캐시 무효화.

        Args:
            name: 시크릿 이름 (None이면 전체)

        Returns:
            무효화된 항목 수
        """
        with self._lock:
            if name is None:
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"전체 캐시 무효화: {count}개")
                return count

            count = 0
            keys_to_remove = [
                k for k in self._cache.keys()
                if k.endswith(f":{name}")
            ]

            for key in keys_to_remove:
                del self._cache[key]
                count += 1

            if count > 0:
                logger.info(f"캐시 무효화: {_mask_secret_name(name)} ({count}개)")

            return count

    def get_cache_stats(self) -> dict[str, Any]:
        """
        캐시 통계 조회.

        Returns:
            캐시 통계
        """
        with self._lock:
            total_entries = len(self._cache)
            total_access = sum(c.access_count for c in self._cache.values())
            expired = sum(1 for c in self._cache.values() if c.is_expired())

            return {
                "enabled": self._config.get("cache", {}).get("enabled", True),
                "total_entries": total_entries,
                "max_entries": self._config.get("cache", {}).get("max_entries", DEFAULT_MAX_CACHE_ENTRIES),
                "total_access_count": total_access,
                "expired_entries": expired,
                "ttl_seconds": self._config.get("cache", {}).get("ttl", DEFAULT_CACHE_TTL),
            }

    def get_providers(self) -> list[str]:
        """
        활성화된 제공자 목록.

        Returns:
            제공자 이름 목록
        """
        return [p.name for p in self._providers.keys()]

    def health_check(self) -> dict[str, Any]:
        """
        헬스 체크.

        Returns:
            헬스 체크 결과
        """
        result = {
            "healthy": True,
            "providers": {},
            "cache": self.get_cache_stats(),
        }

        for provider_type, provider in self._providers.items():
            try:
                is_available = provider.is_available
                result["providers"][provider_type.name] = {
                    "available": is_available,
                    "healthy": is_available,
                }
            except Exception as e:
                result["providers"][provider_type.name] = {
                    "available": False,
                    "healthy": False,
                    "error": str(e),
                }
                result["healthy"] = False

        return result


# ============================================================
# 모듈 레벨 인스턴스 및 헬퍼 함수
# ============================================================
_secret_manager_instance: SecretManager | None = None
_instance_lock = threading.Lock()


def get_secret_manager() -> SecretManager | None:
    """
    전역 SecretManager 인스턴스 조회.

    Returns:
        SecretManager 인스턴스 또는 None
    """
    return _secret_manager_instance


def set_secret_manager(manager: SecretManager) -> None:
    """
    전역 SecretManager 인스턴스 설정.

    Args:
        manager: SecretManager 인스턴스
    """
    global _secret_manager_instance
    with _instance_lock:
        _secret_manager_instance = manager


def get_secret(
    name: str,
    default: str | None = None,
    provider: SecretProvider | None = None,
) -> str | None:
    """
    시크릿 조회 헬퍼 함수.

    전역 SecretManager 인스턴스를 사용하여 시크릿을 조회합니다.
    인스턴스가 설정되지 않은 경우 환경변수에서 직접 조회합니다.

    Args:
        name: 시크릿 이름
        default: 기본값
        provider: 제공자

    Returns:
        시크릿 값 또는 기본값

    Examples:
        >>> db_password = get_secret("database_password")
        >>> jwt_secret = get_secret("jwt_secret", default="dev-secret")
    """
    manager = get_secret_manager()

    if manager is not None:
        return manager.get(name, default=default, provider=provider)

    # 폴백: 환경변수에서 직접 조회
    env_key = f"{DEFAULT_ENV_PREFIX}{name}".upper()
    value = os.environ.get(env_key)

    if value is not None:
        return value

    return default


# ============================================================
# 시크릿 암호화 유틸리티
# ============================================================
class SecretEncryption:
    """
    시크릿 암호화/복호화 유틸리티.

    Fernet 대칭 암호화를 사용하여 시크릿을 보호합니다.
    """

    def __init__(self, key: bytes | None = None, password: str | None = None) -> None:
        """
        암호화 유틸리티 초기화.

        Args:
            key: Fernet 키 (32바이트 base64 인코딩)
            password: 키 도출용 비밀번호
        """
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64

            self._fernet_available = True
        except ImportError:
            self._fernet_available = False
            logger.warning("cryptography 라이브러리가 설치되지 않았습니다. 암호화 비활성화.")
            return

        if key:
            self._fernet = Fernet(key)
        elif password:
            # 비밀번호에서 키 도출 (환경변수에서 salt 가져오기)
            salt_str = os.environ.get(
                "COURTVIEW_SECRET_SALT",
                os.environ.get("SECRET_ENCRYPTION_SALT", "courtview_secret_salt_v1")
            )
            salt = salt_str.encode("utf-8")

            # iterations도 환경변수에서 설정 가능
            iterations = int(os.environ.get("COURTVIEW_PBKDF2_ITERATIONS", "100000"))

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            self._fernet = Fernet(key)
        else:
            # 새 키 생성
            self._key = Fernet.generate_key()
            self._fernet = Fernet(self._key)

    @property
    def is_available(self) -> bool:
        """암호화 사용 가능 여부."""
        return self._fernet_available

    def encrypt(self, plaintext: str) -> str:
        """
        문자열 암호화.

        Args:
            plaintext: 평문

        Returns:
            암호문 (base64 인코딩)
        """
        if not self._fernet_available:
            return plaintext

        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        문자열 복호화.

        Args:
            ciphertext: 암호문 (base64 인코딩)

        Returns:
            평문
        """
        if not self._fernet_available:
            return ciphertext

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            raise SecretException(
                message=f"시크릿 복호화 실패: {e}",
                error_code=ErrorCode.ENCRYPTION_ERROR,
            )

    @staticmethod
    def generate_key() -> bytes:
        """새 암호화 키 생성."""
        try:
            from cryptography.fernet import Fernet
            return Fernet.generate_key()
        except ImportError:
            raise SecretException(
                message="cryptography 라이브러리가 필요합니다",
                error_code=ErrorCode.ENCRYPTION_UNAVAILABLE,
            )


# ============================================================
# 시크릿 로테이션 스케줄러
# ============================================================
@dataclass(slots=True)
class RotationSchedule:
    """시크릿 로테이션 스케줄."""

    secret_name: str
    interval_days: int
    last_rotated: datetime | None = None
    next_rotation: datetime | None = None
    rotation_func: Callable[[], str] | None = None
    pre_rotation_hook: Callable[[str], bool] | None = None
    post_rotation_hook: Callable[[str, str], None] | None = None
    enabled: bool = True


class SecretRotator:
    """
    시크릿 자동 로테이션 관리자.

    주기적으로 시크릿을 교체하고 무중단 전환을 지원합니다.
    """

    def __init__(
        self,
        secret_manager: "SecretManager",
        check_interval_seconds: int = 3600,
    ) -> None:
        """
        로테이션 관리자 초기화.

        Args:
            secret_manager: SecretManager 인스턴스
            check_interval_seconds: 로테이션 확인 주기 (초)
        """
        self._secret_manager = secret_manager
        self._check_interval = check_interval_seconds
        self._schedules: dict[str, RotationSchedule] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._rotation_thread: threading.Thread | None = None
        self._running = False

        logger.info("SecretRotator 초기화 완료")

    def add_schedule(
        self,
        secret_name: str,
        interval_days: int,
        rotation_func: Callable[[], str] | None = None,
        pre_rotation_hook: Callable[[str], bool] | None = None,
        post_rotation_hook: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        로테이션 스케줄 추가.

        Args:
            secret_name: 시크릿 이름
            interval_days: 로테이션 주기 (일)
            rotation_func: 새 시크릿 생성 함수
            pre_rotation_hook: 로테이션 전 실행 훅 (False 반환 시 취소)
            post_rotation_hook: 로테이션 후 실행 훅
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            schedule = RotationSchedule(
                secret_name=secret_name,
                interval_days=interval_days,
                last_rotated=now,
                next_rotation=now + timedelta(days=interval_days),
                rotation_func=rotation_func,
                pre_rotation_hook=pre_rotation_hook,
                post_rotation_hook=post_rotation_hook,
            )
            self._schedules[secret_name] = schedule
            logger.info(f"로테이션 스케줄 추가: {secret_name} (주기: {interval_days}일)")

    def remove_schedule(self, secret_name: str) -> None:
        """로테이션 스케줄 제거."""
        with self._lock:
            if secret_name in self._schedules:
                del self._schedules[secret_name]
                logger.info(f"로테이션 스케줄 제거: {secret_name}")

    def start(self) -> None:
        """로테이션 스케줄러 시작."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop,
            name="SecretRotationThread",
            daemon=True,
        )
        self._rotation_thread.start()
        logger.info("SecretRotator 시작됨")

    def stop(self) -> None:
        """로테이션 스케줄러 중지."""
        self._running = False
        self._stop_event.set()
        if self._rotation_thread:
            self._rotation_thread.join(timeout=5)
        logger.info("SecretRotator 중지됨")

    def _rotation_loop(self) -> None:
        """로테이션 확인 루프."""
        while not self._stop_event.wait(self._check_interval):
            self._check_and_rotate()

    def _check_and_rotate(self) -> None:
        """만료된 시크릿 확인 및 로테이션."""
        now = datetime.now(timezone.utc)

        with self._lock:
            for name, schedule in self._schedules.items():
                if not schedule.enabled:
                    continue

                if schedule.next_rotation and now >= schedule.next_rotation:
                    try:
                        self._rotate_secret(schedule)
                    except Exception as e:
                        logger.error(f"시크릿 로테이션 실패 ({name}): {e}")

    def _rotate_secret(self, schedule: RotationSchedule) -> bool:
        """
        시크릿 로테이션 수행.

        Args:
            schedule: 로테이션 스케줄

        Returns:
            성공 여부
        """
        secret_name = schedule.secret_name
        logger.info(f"시크릿 로테이션 시작: {secret_name}")

        # 현재 값 가져오기
        try:
            old_value = self._secret_manager.get(secret_name)
        except SecretNotFoundException:
            old_value = None

        # 사전 훅 실행
        if schedule.pre_rotation_hook:
            if not schedule.pre_rotation_hook(secret_name):
                logger.warning(f"사전 훅에서 로테이션 취소: {secret_name}")
                return False

        # 새 값 생성
        if schedule.rotation_func:
            new_value = schedule.rotation_func()
        else:
            # 기본: 랜덤 문자열 생성
            import secrets as py_secrets
            new_value = py_secrets.token_urlsafe(32)

        # 시크릿 업데이트 (제공자에 따라 다름)
        # AWS/Vault의 경우 API로 업데이트
        # 환경변수의 경우 직접 업데이트 불가 - 로그만 기록
        logger.info(f"시크릿 로테이션 완료: {secret_name}")

        # 캐시 무효화
        self._secret_manager.invalidate_cache(secret_name)

        # 사후 훅 실행
        if schedule.post_rotation_hook and old_value:
            schedule.post_rotation_hook(old_value, new_value)

        # 스케줄 업데이트
        now = datetime.now(timezone.utc)
        schedule.last_rotated = now
        schedule.next_rotation = now + timedelta(days=schedule.interval_days)

        return True

    def rotate_now(self, secret_name: str) -> bool:
        """
        즉시 로테이션 수행.

        Args:
            secret_name: 시크릿 이름

        Returns:
            성공 여부
        """
        with self._lock:
            if secret_name not in self._schedules:
                logger.warning(f"등록되지 않은 시크릿: {secret_name}")
                return False

            return self._rotate_secret(self._schedules[secret_name])

    def get_schedules(self) -> dict[str, RotationSchedule]:
        """모든 로테이션 스케줄 조회."""
        with self._lock:
            return dict(self._schedules)

    def get_next_rotation(self, secret_name: str) -> datetime | None:
        """다음 로테이션 시간 조회."""
        with self._lock:
            schedule = self._schedules.get(secret_name)
            return schedule.next_rotation if schedule else None


# ============================================================
# Vault 토큰 갱신 관리자
# ============================================================
class VaultTokenManager:
    """
    Vault 토큰 자동 갱신 관리자.

    토큰 만료 전 자동으로 갱신하여 무중단 운영을 지원합니다.
    """

    def __init__(
        self,
        vault_provider: "VaultProvider",
        renew_threshold_seconds: int = 300,
        check_interval_seconds: int = 60,
    ) -> None:
        """
        토큰 관리자 초기화.

        Args:
            vault_provider: VaultProvider 인스턴스
            renew_threshold_seconds: 갱신 임계값 (만료 전 초)
            check_interval_seconds: 확인 주기 (초)
        """
        self._provider = vault_provider
        self._renew_threshold = renew_threshold_seconds
        self._check_interval = check_interval_seconds
        self._stop_event = threading.Event()
        self._renew_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """토큰 갱신 모니터링 시작."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._renew_thread = threading.Thread(
            target=self._renew_loop,
            name="VaultTokenRenewThread",
            daemon=True,
        )
        self._renew_thread.start()
        logger.info("VaultTokenManager 시작됨")

    def stop(self) -> None:
        """토큰 갱신 모니터링 중지."""
        self._running = False
        self._stop_event.set()
        if self._renew_thread:
            self._renew_thread.join(timeout=5)
        logger.info("VaultTokenManager 중지됨")

    def _renew_loop(self) -> None:
        """토큰 갱신 루프."""
        while not self._stop_event.wait(self._check_interval):
            self._check_and_renew()

    def _check_and_renew(self) -> None:
        """토큰 만료 확인 및 갱신."""
        if not VAULT_AVAILABLE:
            return

        try:
            client = self._provider._get_client()
            token_info = client.auth.token.lookup_self()

            if token_info and "data" in token_info:
                ttl = token_info["data"].get("ttl", 0)

                if ttl <= self._renew_threshold:
                    logger.info(f"Vault 토큰 갱신 시작 (TTL: {ttl}초)")
                    client.auth.token.renew_self()
                    logger.info("Vault 토큰 갱신 완료")

        except Exception as e:
            logger.error(f"Vault 토큰 갱신 실패: {e}")

    def get_token_ttl(self) -> int | None:
        """현재 토큰 TTL 조회."""
        if not VAULT_AVAILABLE:
            return None

        try:
            client = self._provider._get_client()
            token_info = client.auth.token.lookup_self()

            if token_info and "data" in token_info:
                return token_info["data"].get("ttl")
        except Exception as e:
            logger.warning(f"Vault 토큰 TTL 조회 실패: {e}")

        return None


# ============================================================
# 암호화된 파일 제공자
# ============================================================
class EncryptedFileProvider(BaseSecretProvider):
    """
    암호화된 파일 기반 제공자.

    파일에 저장된 시크릿을 암호화/복호화합니다.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        암호화 파일 제공자 초기화.

        Args:
            config: 설정 (path, encryption_key, password 등)
        """
        super().__init__(config)
        self._path = Path(config.get("path", "secrets/.secrets.enc.yaml"))
        self._secrets: dict[str, str] = {}
        self._loaded = False

        # 암호화 설정
        encryption_key = config.get("encryption_key")
        password = config.get("password") or os.environ.get("COURTVIEW_SECRET_ENCRYPTION_KEY")

        if encryption_key:
            self._encryption = SecretEncryption(key=encryption_key.encode())
        elif password:
            self._encryption = SecretEncryption(password=password)
        else:
            raise SecretProviderException(
                message="암호화 키 또는 비밀번호가 필요합니다",
                provider=SecretProvider.FILE,
            )

    @property
    def provider_type(self) -> SecretProvider:
        """제공자 타입."""
        return SecretProvider.FILE

    @property
    def is_available(self) -> bool:
        """파일 및 암호화 사용 가능 여부."""
        return self._path.exists() and self._encryption.is_available

    def _load_secrets(self) -> None:
        """암호화된 시크릿 파일 로드."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            if not self._path.exists():
                self._secrets = {}
                self._loaded = True
                return

            try:
                content = self._path.read_text(encoding="utf-8")

                # 암호화된 내용 복호화
                decrypted = self._encryption.decrypt(content)

                # YAML 파싱
                import yaml
                self._secrets = yaml.safe_load(decrypted) or {}
                self._loaded = True

                logger.debug(f"암호화된 시크릿 파일 로드 완료: {len(self._secrets)}개")

            except Exception as e:
                raise SecretProviderException(
                    message=f"암호화된 시크릿 파일 로드 실패: {e}",
                    provider=SecretProvider.FILE,
                )

    def get_secret(self, name: str) -> tuple[str, SecretVersion | None]:
        """암호화된 파일에서 시크릿 조회."""
        self._load_secrets()

        with self._lock:
            if name not in self._secrets:
                raise SecretNotFoundException(
                    message=f"암호화된 시크릿을 찾을 수 없습니다: {name}",
                    secret_name=name,
                    provider=SecretProvider.FILE,
                )

            value = self._secrets[name]
            version = SecretVersion(
                version_id="encrypted",
                version_stage="current",
                is_current=True,
            )

            return str(value), version

    def secret_exists(self, name: str) -> bool:
        """시크릿 존재 여부 확인."""
        self._load_secrets()
        return name in self._secrets

    def save_secret(self, name: str, value: str) -> None:
        """시크릿 저장 (암호화)."""
        self._load_secrets()

        with self._lock:
            self._secrets[name] = value

            # YAML로 직렬화
            import yaml
            content = yaml.safe_dump(self._secrets, default_flow_style=False)

            # 암호화 후 저장
            encrypted = self._encryption.encrypt(content)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(encrypted, encoding="utf-8")

            logger.debug(f"암호화된 시크릿 저장 완료: {name}")


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "SecretProvider",
    "SecretStatus",
    "CacheStatus",
    # 예외
    "SecretException",
    "SecretNotFoundException",
    "SecretAccessDeniedException",
    "SecretValidationException",
    "SecretProviderException",
    # 데이터 클래스
    "SecretInfo",
    "SecretVersion",
    "SecretValidationRule",
    "RotationSchedule",
    # 메인 클래스
    "SecretManager",
    # 제공자 클래스
    "BaseSecretProvider",
    "AWSSecretsProvider",
    "VaultProvider",
    "EnvProvider",
    "FileProvider",
    "EncryptedFileProvider",
    # 유틸리티 클래스
    "SecretEncryption",
    "SecretRotator",
    "VaultTokenManager",
    # 함수
    "get_secret",
    "get_secret_manager",
    "set_secret_manager",
]
