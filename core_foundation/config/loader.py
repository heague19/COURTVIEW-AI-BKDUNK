# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: loader.py
설명: YAML/JSON 설정 파일 로드, 환경변수 오버라이드, 설정 병합

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - YAML/JSON 설정 파일 자동 감지 및 로드
    - 환경변수 오버라이드 지원 (COURTVIEW_ 접두사)
    - 다중 설정 파일 병합 (딥 머지)
    - 프로파일 기반 설정 (development, production, testing)
    - 싱글톤 패턴으로 전역 접근
    - 설정 값 캐싱 및 타입 변환
    - 중첩 키 접근 지원 (dot notation)

사용 예시:
    # 기본 사용
    config = ConfigLoader.get_instance()
    config.load("config/app.yaml")
    db_host = config.get("database.host", "localhost")

    # 헬퍼 함수 사용
    config_data = load_config("config/app.yaml")
    port = get_config_value("server.port", 8000)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import json
import logging
import os
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Iterator,
    Type,
    TypeVar,
)

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
import yaml

# =============================================================================
# 프로젝트 모듈 (shared)
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.validation_exceptions import (
    ConfigurationException,
    ConfigurationNotFoundException,
    ConfigurationParseException,
)

# =============================================================================
# 로거 설정
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 타입 변수
# =============================================================================
T = TypeVar("T")

# =============================================================================
# 상수 정의
# =============================================================================
# 환경변수 접두사
ENV_PREFIX: str = "COURTVIEW_"

# 기본 설정 검색 경로
DEFAULT_CONFIG_PATHS: list[str] = [
    "configs",
    "config",
    "settings",
    ".",
]

# 지원하는 설정 파일 확장자
YAML_EXTENSIONS: tuple = (".yaml", ".yml")
JSON_EXTENSIONS: tuple = (".json",)

# 프로파일 환경변수
PROFILE_ENV_VAR: str = "COURTVIEW_PROFILE"

# 기본 프로파일
DEFAULT_PROFILE: str = "development"


# =============================================================================
# Enum 정의
# =============================================================================
class ConfigFormat(Enum):
    """
    설정 파일 포맷.

    설정 파일의 형식을 지정합니다.
    AUTO는 파일 확장자에 따라 자동 감지합니다.
    """

    YAML = auto()  # YAML 형식 (.yaml, .yml)
    JSON = auto()  # JSON 형식 (.json)
    AUTO = auto()  # 자동 감지


class ConfigSource(Enum):
    """
    설정 소스.

    설정 값이 어디서 로드되었는지 나타냅니다.
    우선순위: ENV > FILE > DEFAULT
    """

    FILE = auto()     # 설정 파일에서 로드
    ENV = auto()      # 환경변수에서 로드
    DEFAULT = auto()  # 기본값 사용


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass
class ConfigEntry:
    """
    개별 설정 항목.

    단일 설정 값과 메타정보를 담습니다.

    Attributes:
        key: 설정 키 (dot notation 지원, 예: "database.host")
        value: 설정 값
        source: 설정 소스 (FILE, ENV, DEFAULT)
        original_value: 원본 값 (타입 변환 전)
        loaded_at: 로드 시각
        file_path: 로드된 파일 경로 (FILE 소스인 경우)
    """

    key: str
    value: Any
    source: ConfigSource
    original_value: Any = None
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    file_path: str | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        if self.original_value is None:
            self.original_value = self.value


@dataclass
class ConfigMetadata:
    """
    설정 메타데이터.

    설정 전체에 대한 메타정보를 담습니다.

    Attributes:
        version: 설정 버전
        profile: 활성 프로파일 (development, production, testing)
        loaded_files: 로드된 설정 파일 목록
        loaded_at: 최초 로드 시각
        last_updated_at: 마지막 업데이트 시각
        env_overrides: 환경변수로 오버라이드된 키 목록
        total_entries: 총 설정 항목 수
    """

    version: str = "1.0.0"
    profile: str = DEFAULT_PROFILE
    loaded_files: list[str] = field(default_factory=list)
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    env_overrides: list[str] = field(default_factory=list)
    total_entries: int = 0

    def add_loaded_file(self, file_path: str) -> None:
        """로드된 파일 추가."""
        if file_path not in self.loaded_files:
            self.loaded_files.append(file_path)
            self.last_updated_at = datetime.now(timezone.utc)

    def add_env_override(self, key: str) -> None:
        """환경변수 오버라이드 키 추가."""
        if key not in self.env_overrides:
            self.env_overrides.append(key)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "version": self.version,
            "profile": self.profile,
            "loaded_files": self.loaded_files,
            "loaded_at": self.loaded_at.isoformat(),
            "last_updated_at": self.last_updated_at.isoformat(),
            "env_overrides": self.env_overrides,
            "total_entries": self.total_entries,
        }


# =============================================================================
# ConfigLoader 클래스
# =============================================================================
class ConfigLoader:
    """
    설정 로더.

    YAML/JSON 설정 파일을 로드하고 환경변수 오버라이드를 적용합니다.
    싱글톤 패턴으로 구현되어 전역에서 동일한 인스턴스에 접근합니다.

    주요 기능:
        - YAML/JSON 자동 감지 및 파싱
        - 환경변수 오버라이드 (COURTVIEW_ 접두사)
        - 다중 설정 파일 병합 (딥 머지)
        - 프로파일 기반 설정 로드
        - 중첩 키 접근 (dot notation)
        - 타입 안전 값 조회
        - 스레드 안전

    Example:
        >>> loader = ConfigLoader.get_instance()
        >>> loader.load("config/app.yaml")
        >>> host = loader.get("database.host", "localhost")
        >>> port = loader.get("database.port", 5432, int)
        >>> loader.set("custom.key", "value")
    """

    # 싱글톤 인스턴스
    _instance: "ConfigLoader" | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ConfigLoader":
        """싱글톤 인스턴스 생성."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """초기화."""
        # 중복 초기화 방지
        if getattr(self, "_initialized", False):
            return

        # 설정 데이터 저장소
        self._config: dict[str, Any] = {}

        # 설정 항목 캐시 (키 -> ConfigEntry)
        self._entries: dict[str, ConfigEntry] = {}

        # 메타데이터
        self._metadata: ConfigMetadata = ConfigMetadata()

        # 활성 프로파일
        self._profile: str = os.environ.get(PROFILE_ENV_VAR, DEFAULT_PROFILE)
        self._metadata.profile = self._profile

        # 스레드 락
        self._config_lock: threading.RLock = threading.RLock()

        # 초기화 완료 플래그
        self._initialized: bool = True

        logger.info(f"ConfigLoader 초기화 완료 (프로파일: {self._profile})")

    @classmethod
    def get_instance(cls) -> "ConfigLoader":
        """
        싱글톤 인스턴스 반환.

        Returns:
            ConfigLoader 인스턴스
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """
        싱글톤 인스턴스 초기화 (테스트용).

        주의: 프로덕션 환경에서는 사용하지 마세요.
        """
        with cls._lock:
            cls._instance = None

    # --------------------------------------------------------
    # 파일 로드 메서드
    # --------------------------------------------------------
    def load(
        self,
        file_path: str | Path,
        format: ConfigFormat = ConfigFormat.AUTO,
        merge: bool = True,
        required: bool = True,
    ) -> dict[str, Any]:
        """
        설정 파일 로드.

        Args:
            file_path: 설정 파일 경로
            format: 파일 포맷 (AUTO면 자동 감지)
            merge: True면 기존 설정과 병합, False면 덮어쓰기
            required: True면 파일 없을 시 예외 발생

        Returns:
            로드된 설정 딕셔너리

        Raises:
            ConfigurationNotFoundException: 필수 파일이 없는 경우
            ConfigurationParseException: 파싱 실패한 경우
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        # 파일 존재 확인
        if not path.exists():
            if required:
                searched_paths = [str(path)]
                raise ConfigurationNotFoundException(
                    config_file=str(path),
                    searched_paths=searched_paths,
                )
            logger.warning(f"설정 파일 없음 (선택적): {path}")
            return {}

        # 포맷 결정
        actual_format = self._detect_format(path, format)

        # 파일 로드
        try:
            with open(path, "r", encoding="utf-8") as f:
                if actual_format == ConfigFormat.YAML:
                    data = yaml.safe_load(f) or {}
                else:
                    data = json.load(f)
        except yaml.YAMLError as e:
            raise ConfigurationParseException(
                config_file=str(path),
                reason=f"YAML 파싱 오류: {e}",
                cause=e,
            )
        except json.JSONDecodeError as e:
            raise ConfigurationParseException(
                config_file=str(path),
                reason=f"JSON 파싱 오류: {e}",
                line_number=e.lineno,
                cause=e,
            )
        except Exception as e:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_LOAD_FAILED,
                message=f"설정 파일 로드 실패: {path}",
                config_file=str(path),
                cause=e,
            )

        # 데이터 적용
        with self._config_lock:
            if merge:
                self._config = self._deep_merge(self._config, data)
            else:
                self._config = data

            # 메타데이터 업데이트
            self._metadata.add_loaded_file(str(path))
            self._update_entries(data, str(path))

            # 환경변수 오버라이드 적용
            self._apply_env_overrides()

        logger.info(f"설정 파일 로드 완료: {path} (포맷: {actual_format.name})")
        return deepcopy(data)

    def load_multiple(
        self,
        file_paths: list[str | Path],
        format: ConfigFormat = ConfigFormat.AUTO,
        required: bool = False,
    ) -> dict[str, Any]:
        """
        여러 설정 파일 순차 로드 및 병합.

        나중에 로드된 파일이 이전 파일을 오버라이드합니다.

        Args:
            file_paths: 설정 파일 경로 목록
            format: 파일 포맷
            required: 필수 여부

        Returns:
            병합된 설정 딕셔너리
        """
        for path in file_paths:
            self.load(path, format=format, merge=True, required=required)
        return deepcopy(self._config)

    def load_with_profile(
        self,
        base_name: str,
        config_dir: str | Path = "config",
        format: ConfigFormat = ConfigFormat.AUTO,
    ) -> dict[str, Any]:
        """
        프로파일 기반 설정 로드.

        로드 순서:
        1. base_name.yaml (기본 설정)
        2. base_name.{profile}.yaml (프로파일 설정)
        3. base_name.local.yaml (로컬 설정, 선택적)

        Args:
            base_name: 기본 파일명 (확장자 제외)
            config_dir: 설정 디렉토리
            format: 파일 포맷

        Returns:
            병합된 설정 딕셔너리
        """
        config_path = Path(config_dir)

        # 확장자 결정
        ext = ".yaml" if format in (ConfigFormat.YAML, ConfigFormat.AUTO) else ".json"

        # 로드할 파일 목록
        files_to_load = [
            config_path / f"{base_name}{ext}",                    # 기본 설정
            config_path / f"{base_name}.{self._profile}{ext}",    # 프로파일 설정
            config_path / f"{base_name}.local{ext}",              # 로컬 설정
        ]

        # 첫 번째 파일은 필수
        for i, file_path in enumerate(files_to_load):
            self.load(file_path, format=format, merge=True, required=(i == 0))

        return deepcopy(self._config)

    # --------------------------------------------------------
    # 값 조회 메서드
    # --------------------------------------------------------
    def get(
        self,
        key: str,
        default: T = None,
        value_type: Type[T] | None = None,
    ) -> T:
        """
        설정 값 조회.

        중첩 키는 dot notation으로 접근합니다.

        Args:
            key: 설정 키 (예: "database.host", "server.port")
            default: 기본값
            value_type: 반환 타입 (자동 변환)

        Returns:
            설정 값 또는 기본값

        Example:
            >>> loader.get("database.host", "localhost")
            "localhost"
            >>> loader.get("server.port", 8000, int)
            8000
        """
        with self._config_lock:
            value = self._get_nested(self._config, key)

            if value is None:
                return default

            # 타입 변환
            if value_type is not None:
                try:
                    return self._convert_type(value, value_type)
                except (ValueError, TypeError):
                    logger.warning(f"타입 변환 실패: {key}={value} -> {value_type.__name__}")
                    return default

            return value

    def get_required(
        self,
        key: str,
        value_type: Type[T] | None = None,
    ) -> T:
        """
        필수 설정 값 조회.

        값이 없으면 예외를 발생시킵니다.

        Args:
            key: 설정 키
            value_type: 반환 타입

        Returns:
            설정 값

        Raises:
            ConfigurationException: 키가 없는 경우
        """
        value = self.get(key, value_type=value_type)

        if value is None:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_NOT_FOUND,
                message=f"필수 설정 값이 없습니다: {key}",
                config_key=key,
            )

        return value

    def get_int(self, key: str, default: int = 0) -> int:
        """정수 값 조회."""
        return self.get(key, default, int)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """실수 값 조회."""
        return self.get(key, default, float)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """불리언 값 조회."""
        value = self.get(key)
        if value is None:
            return default
        return self._parse_bool(value)

    def get_str(self, key: str, default: str = "") -> str:
        """문자열 값 조회."""
        return self.get(key, default, str)

    def get_list(self, key: str, default: list | None = None) -> list:
        """리스트 값 조회."""
        value = self.get(key, default)
        if value is None:
            return default or []
        if isinstance(value, list):
            return value
        return [value]

    def get_dict(self, key: str, default: dict | None = None) -> dict:
        """딕셔너리 값 조회."""
        value = self.get(key, default)
        if value is None:
            return default or {}
        if isinstance(value, dict):
            return value
        return default or {}

    def get_section(self, key: str) -> dict[str, Any]:
        """
        설정 섹션 전체 조회.

        Args:
            key: 섹션 키 (예: "database")

        Returns:
            섹션 딕셔너리
        """
        return self.get_dict(key, {})

    # --------------------------------------------------------
    # 값 설정 메서드
    # --------------------------------------------------------
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.DEFAULT) -> None:
        """
        설정 값 저장.

        Args:
            key: 설정 키 (dot notation 지원)
            value: 설정 값
            source: 설정 소스
        """
        with self._config_lock:
            self._set_nested(self._config, key, value)

            # 엔트리 업데이트
            self._entries[key] = ConfigEntry(
                key=key,
                value=value,
                source=source,
            )
            self._metadata.total_entries = len(self._entries)
            self._metadata.last_updated_at = datetime.now(timezone.utc)

    def set_multiple(self, values: dict[str, Any], source: ConfigSource = ConfigSource.DEFAULT) -> None:
        """
        여러 설정 값 저장.

        Args:
            values: 키-값 딕셔너리
            source: 설정 소스
        """
        for key, value in values.items():
            self.set(key, value, source)

    # --------------------------------------------------------
    # 유틸리티 메서드
    # --------------------------------------------------------
    def has(self, key: str) -> bool:
        """키 존재 여부 확인."""
        return self.get(key) is not None

    def keys(self) -> list[str]:
        """모든 설정 키 반환."""
        with self._config_lock:
            return list(self._entries.keys())

    def items(self) -> Iterator[tuple]:
        """모든 설정 항목 반복."""
        with self._config_lock:
            for key, entry in self._entries.items():
                yield key, entry.value

    def to_dict(self) -> dict[str, Any]:
        """전체 설정을 딕셔너리로 반환."""
        with self._config_lock:
            return deepcopy(self._config)

    def get_entry(self, key: str) -> ConfigEntry | None:
        """설정 항목 메타정보 조회."""
        with self._config_lock:
            return self._entries.get(key)

    @property
    def metadata(self) -> ConfigMetadata:
        """메타데이터 반환."""
        return self._metadata

    @property
    def profile(self) -> str:
        """활성 프로파일 반환."""
        return self._profile

    def clear(self) -> None:
        """모든 설정 초기화."""
        with self._config_lock:
            self._config.clear()
            self._entries.clear()
            self._metadata = ConfigMetadata()
            self._metadata.profile = self._profile

    # --------------------------------------------------------
    # 프라이빗 헬퍼 메서드
    # --------------------------------------------------------
    def _detect_format(self, path: Path, format: ConfigFormat) -> ConfigFormat:
        """파일 포맷 감지."""
        if format != ConfigFormat.AUTO:
            return format

        suffix = path.suffix.lower()
        if suffix in YAML_EXTENSIONS:
            return ConfigFormat.YAML
        elif suffix in JSON_EXTENSIONS:
            return ConfigFormat.JSON
        else:
            # 기본값은 YAML
            return ConfigFormat.YAML

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """딕셔너리 딥 머지."""
        result = deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)

        return result

    def _get_nested(self, data: dict, key: str) -> Any:
        """중첩 키로 값 조회."""
        keys = key.split(".")
        current = data

        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
                if current is None:
                    return None
            else:
                return None

        return current

    def _set_nested(self, data: dict, key: str, value: Any) -> None:
        """중첩 키로 값 설정."""
        keys = key.split(".")

        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]

        data[keys[-1]] = value

    def _update_entries(self, data: dict, file_path: str, prefix: str = "") -> None:
        """설정 항목 업데이트."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._update_entries(value, file_path, full_key)
            else:
                self._entries[full_key] = ConfigEntry(
                    key=full_key,
                    value=value,
                    source=ConfigSource.FILE,
                    file_path=file_path,
                )

        self._metadata.total_entries = len(self._entries)

    def _apply_env_overrides(self) -> None:
        """환경변수 오버라이드 적용."""
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(ENV_PREFIX):
                continue

            # COURTVIEW_DATABASE_HOST -> database.host
            config_key = env_key[len(ENV_PREFIX):].lower().replace("_", ".")

            # 타입 추론 및 변환
            converted_value = self._parse_env_value(env_value)

            self._set_nested(self._config, config_key, converted_value)
            self._entries[config_key] = ConfigEntry(
                key=config_key,
                value=converted_value,
                source=ConfigSource.ENV,
                original_value=env_value,
            )
            self._metadata.add_env_override(config_key)

            logger.debug(f"환경변수 오버라이드: {config_key}={converted_value}")

    def _parse_env_value(self, value: str) -> Any:
        """환경변수 값 파싱 및 타입 변환."""
        # 불리언
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False

        # 정수
        try:
            return int(value)
        except ValueError:
            pass

        # 실수
        try:
            return float(value)
        except ValueError:
            pass

        # JSON 배열/객체
        if value.startswith("[") or value.startswith("{"):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # 문자열
        return value

    def _parse_bool(self, value: Any) -> bool:
        """불리언 파싱."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    def _convert_type(self, value: Any, target_type: Type[T]) -> T:
        """타입 변환."""
        if isinstance(value, target_type):
            return value

        if target_type == bool:
            return self._parse_bool(value)

        return target_type(value)


# =============================================================================
# 헬퍼 함수
# =============================================================================
def load_config(
    file_path: str | Path,
    format: ConfigFormat = ConfigFormat.AUTO,
    merge: bool = True,
    required: bool = True,
) -> dict[str, Any]:
    """
    설정 파일 로드 헬퍼 함수.

    Args:
        file_path: 설정 파일 경로
        format: 파일 포맷
        merge: 병합 여부
        required: 필수 여부

    Returns:
        로드된 설정 딕셔너리

    Example:
        >>> config = load_config("config/app.yaml")
        >>> print(config["database"]["host"])
    """
    loader = ConfigLoader.get_instance()
    return loader.load(file_path, format=format, merge=merge, required=required)


def get_config_value(
    key: str,
    default: T = None,
    value_type: Type[T] | None = None,
) -> T:
    """
    설정 값 조회 헬퍼 함수.

    Args:
        key: 설정 키
        default: 기본값
        value_type: 반환 타입

    Returns:
        설정 값 또는 기본값

    Example:
        >>> host = get_config_value("database.host", "localhost")
        >>> port = get_config_value("database.port", 5432, int)
    """
    loader = ConfigLoader.get_instance()
    return loader.get(key, default=default, value_type=value_type)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "ConfigFormat",
    "ConfigSource",
    # 데이터 클래스
    "ConfigEntry",
    "ConfigMetadata",
    # 클래스
    "ConfigLoader",
    # 함수
    "load_config",
    "get_config_value",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
