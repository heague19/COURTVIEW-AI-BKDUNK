# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: loader.py
설명: YAML/JSON/TOML 설정 파일 로드, 환경변수 오버라이드, 설정 병합

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-06
버전: 1.0.0

주요 기능:
    - YAML/JSON/TOML 설정 파일 자동 감지 및 로드
    - 환경변수 오버라이드 지원 (COURTVIEW_ 접두사)
    - 다중 설정 파일 병합 (딥 머지)
    - 프로파일 기반 설정 (development, production, testing)
    - 싱글톤 패턴으로 전역 접근 (free-threaded Python 대비 팩토리 메서드)
    - 설정 값 캐싱 및 타입 변환
    - 중첩 키 접근 지원 (dot notation)
    - 환경변수 동적 갱신 (Docker/K8s ConfigMap 대응)
    - LRU 캐시 (split key, entries)

사용 예시:
    # 기본 사용
    config = ConfigLoader.get_instance()
    config.load("config/app.yaml")
    redis_host = config.get("redis.host", "localhost")

    # 헬퍼 함수 사용
    config_data = load_config("config/app.yaml")
    port = get_config_value("server.port", 8000)

    # 환경변수 동적 갱신 (Docker ConfigMap 변경 후)
    config.refresh_env()

환경변수 동작:
    환경변수 스냅샷은 인스턴스 생성 시 1회 수집됩니다.
    이후 load() 호출 시 해당 스냅샷 기반으로 오버라이드를 적용합니다.
    Docker/K8s에서 런타임 환경변수가 변경된 경우 refresh_env()를 명시적으로
    호출해야 새 환경변수가 반영됩니다.

환경변수 키 매핑 규칙:
    접두사: "COURTVIEW_" (단일 언더스코어)
    계층 구분: "__" (더블 언더스코어) → "." (dot)
    단어 구분: "_" (단일 언더스코어) → "_" (그대로 유지)

    예: COURTVIEW_S3__BUCKET_NAME  → s3.bucket_name
        COURTVIEW_SERVER__PORT     → server.port
        COURTVIEW_ANALYSIS__MAX_FPS → analysis.max_fps

    주의: 접두사 뒤에 "__"를 사용하면 키 앞에 "_"가 붙습니다.
        COURTVIEW__S3__BUCKET → _s3.bucket (잘못된 사용)
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import json
import logging
import os
import threading
import tomllib
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, TypeVar, overload

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
# Sentinel 타입 정의
# =============================================================================
class _Sentinel:
    """
    키 부재(key missing)를 None과 명확히 구분하기 위한 sentinel 타입.

    - None: YAML null 등 유효한 설정 값
    - _MISSING: 해당 키가 설정에 존재하지 않음

    class 기반 sentinel은 object() 대비 다음 이점을 가집니다:
      - mypy/Pyright의 타입 narrowing 지원 (is _MISSING 체크 시 정확한 분기 추론)
      - repr으로 디버깅 시 명확한 표시
      - isinstance 검사 가능
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<MISSING>"

    def __bool__(self) -> bool:
        return False


_MISSING: _Sentinel = _Sentinel()

# =============================================================================
# 상수 정의
# =============================================================================
# 환경변수 접두사
ENV_PREFIX: str = "COURTVIEW_"

# 지원하는 설정 파일 확장자
YAML_EXTENSIONS: tuple[str, ...] = (".yaml", ".yml")
JSON_EXTENSIONS: tuple[str, ...] = (".json",)
TOML_EXTENSIONS: tuple[str, ...] = (".toml",)

# 프로파일 환경변수
PROFILE_ENV_VAR: str = "COURTVIEW_PROFILE"

# 기본 프로파일
DEFAULT_PROFILE: str = "development"

# 설정 중첩 깊이 제한 (재귀 폭주 방지)
_MAX_NESTING_DEPTH: int = 32

# dot-notation 키 분할 LRU 캐시 최대 크기
_SPLIT_CACHE_MAX_SIZE: int = 4096

# _entries 최대 크기 (장시간 운영 시 무한 성장 방지)
_ENTRIES_MAX_SIZE: int = 16384


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
    TOML = auto()  # TOML 형식 (.toml) — Python 3.11+ tomllib 내장
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
@dataclass(slots=True)
class ConfigEntry:
    """
    개별 설정 항목.

    단일 설정 값과 메타정보를 담습니다.
    slots=True: 인스턴스당 ~40-60% 메모리 절감 (수천 개 생성 시 체감)

    Attributes:
        key: 설정 키 (dot notation 지원, 예: "server.port")
        value: 설정 값
        source: 설정 소스 (FILE, ENV, DEFAULT)
        original_value: 원본 값 (타입 변환 전)
        file_path: 로드된 파일 경로 (FILE 소스인 경우)
    """

    key: str
    value: Any
    source: ConfigSource
    original_value: Any = field(default=_MISSING)
    file_path: str | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리 (sentinel로 None과 미지정을 구분)."""
        if self.original_value is _MISSING:
            self.original_value = self.value


@dataclass(slots=True)
class ConfigMetadata:
    """
    설정 메타데이터.

    설정 전체에 대한 메타정보를 담습니다.
    slots=True: 메모리 최적화
    내부 dict 필드는 메서드를 통해서만 변경해야 합니다.

    Attributes:
        version: 설정 버전
        profile: 활성 프로파일 (development, production, testing)
        loaded_at: 최초 로드 시각
        last_updated_at: 마지막 업데이트 시각
        total_entries: 총 설정 항목 수
    """

    version: str = "1.0.0"
    profile: str = DEFAULT_PROFILE
    # dict를 순서 보존 set으로 활용 (O(1) 중복 체크)
    _loaded_files: dict[str, None] = field(default_factory=dict)
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # dict를 순서 보존 set으로 활용 (O(1) 중복 체크)
    _env_overrides: dict[str, None] = field(default_factory=dict)
    total_entries: int = 0

    @property
    def loaded_files(self) -> tuple[str, ...]:
        """로드된 파일 목록 반환 (순서 보존, 불변)."""
        return tuple(self._loaded_files.keys())

    @property
    def env_overrides(self) -> tuple[str, ...]:
        """환경변수 오버라이드 키 목록 반환 (불변)."""
        return tuple(self._env_overrides.keys())

    def add_loaded_file(self, file_path: str) -> None:
        """로드된 파일 추가 (O(1) 중복 체크)."""
        if file_path not in self._loaded_files:
            self._loaded_files[file_path] = None
            self.last_updated_at = datetime.now(timezone.utc)

    def add_env_override(self, key: str) -> None:
        """환경변수 오버라이드 키 추가 (O(1) 중복 체크)."""
        self._env_overrides[key] = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "version": self.version,
            "profile": self.profile,
            "loaded_files": list(self._loaded_files.keys()),
            "loaded_at": self.loaded_at.isoformat(),
            "last_updated_at": self.last_updated_at.isoformat(),
            "env_overrides": list(self._env_overrides.keys()),
            "total_entries": self.total_entries,
        }


# =============================================================================
# ConfigLoader 클래스
# =============================================================================
class ConfigLoader:
    """
    설정 로더.

    YAML/JSON/TOML 설정 파일을 로드하고 환경변수 오버라이드를 적용합니다.
    싱글톤 패턴으로 구현되어 전역에서 동일한 인스턴스에 접근합니다.

    주요 기능:
        - YAML/JSON/TOML 자동 감지 및 파싱
        - 환경변수 오버라이드 (COURTVIEW_ 접두사)
        - 다중 설정 파일 병합 (딥 머지)
        - 프로파일 기반 설정 로드
        - 중첩 키 접근 (dot notation)
        - 타입 안전 값 조회
        - 스레드 안전 (읽기/쓰기 모두 lock 보호, free-threaded 대비)
        - 환경변수 동적 갱신 (Docker/K8s 대응)

    환경변수 동작:
        환경변수 스냅샷은 인스턴스 생성 시 1회 수집됩니다.
        load() 호출마다 해당 스냅샷 기반으로 오버라이드를 적용합니다.
        런타임 환경변수 변경 시 refresh_env()를 명시적으로 호출하세요.

    환경변수 키 매핑 규칙:
        접두사 "COURTVIEW_" 제거 후 "__" → "." (계층 구분), "_" → "_" (유지)
        예: COURTVIEW_S3__BUCKET_NAME  → s3.bucket_name
            COURTVIEW_SERVER__PORT     → server.port

    Example:
        >>> loader = ConfigLoader.get_instance()
        >>> loader.load("config/app.yaml")
        >>> bucket = loader.get("s3.bucket_name", "courtview-videos")
        >>> port = loader.get("server.port", 8000, int)
        >>> loader.set("analysis.max_fps", 60)
    """

    # 싱글톤 인스턴스 + 초기화 보호 lock
    _instance: ConfigLoader | None = None
    _lock: threading.Lock = threading.Lock()
    # 직접 생성 차단용 내부 토큰 (get_instance()에서만 전달)
    _INTERNAL_TOKEN: object = object()

    # __slots__: 오타 방지 + 의도 명시
    __slots__ = (
        "_config",
        "_entries",
        "_metadata",
        "_profile",
        "_split_cache",
        "_env_snapshot",
        "_config_lock",
        "_initialized",
        "_config_proxy",
    )

    # --------------------------------------------------------
    # 싱글톤: 팩토리 메서드 패턴 (free-threaded Python 3.13+ 대비)
    # __new__ + __init__ DCL 대신, get_instance()에서 lock 내 완전 초기화
    # --------------------------------------------------------
    def __new__(cls, *, _token: object = None) -> ConfigLoader:
        """직접 생성 차단 — get_instance()를 사용하세요."""
        if _token is not cls._INTERNAL_TOKEN:
            raise TypeError(
                "ConfigLoader()를 직접 호출할 수 없습니다. "
                "ConfigLoader.get_instance()를 사용하세요."
            )
        return super().__new__(cls)

    def __init__(self, *, _token: object = None) -> None:
        """내부 초기화 — get_instance()에서 호출."""
        pass

    def _do_init(self) -> None:
        """실제 초기화 로직 (get_instance의 lock 내에서 1회 호출)."""
        # 설정 데이터 저장소
        self._config: dict[str, Any] = {}

        # 읽기 전용 프록시 (to_dict 대신 deepcopy 없이 안전한 읽기 제공)
        self._config_proxy: MappingProxyType[str, Any] = MappingProxyType(self._config)

        # 설정 항목 캐시 (키 -> ConfigEntry)
        self._entries: dict[str, ConfigEntry] = {}

        # 메타데이터
        self._metadata: ConfigMetadata = ConfigMetadata()

        # 활성 프로파일
        self._profile: str = os.environ.get(PROFILE_ENV_VAR, DEFAULT_PROFILE)
        self._metadata.profile = self._profile

        # dot-notation 키 분할 LRU 캐시
        self._split_cache: dict[str, tuple[str, ...]] = {}

        # COURTVIEW_ 접두사 환경변수 수집 (refresh_env()로 명시적 갱신)
        self._env_snapshot: dict[str, str] = self._collect_env_snapshot()

        # 스레드 락 (읽기/쓰기 모두 보호 — GIL-free Python 3.13+ 대비)
        self._config_lock: threading.RLock = threading.RLock()

        # 초기화 완료 플래그
        self._initialized: bool = True

        logger.info("ConfigLoader 초기화 완료", extra={"profile": self._profile})

    @classmethod
    def get_instance(cls) -> ConfigLoader:
        """
        싱글톤 인스턴스 반환.

        free-threaded Python 대비: lock 내에서 생성 + 초기화를 원자적으로 수행.
        __new__ + __init__ DCL 패턴의 경쟁 조건을 완전히 제거합니다.

        Returns:
            ConfigLoader 인스턴스
        """
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                inst = cls.__new__(cls, _token=cls._INTERNAL_TOKEN)
                inst._do_init()
                cls._instance = inst
        return cls._instance

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
        config_format: ConfigFormat = ConfigFormat.AUTO,
        merge: bool = True,
        required: bool = True,
        *,
        _defer_env: bool = False,
    ) -> dict[str, Any]:
        """
        설정 파일 로드.

        환경변수 오버라이드는 인스턴스 생성 시 수집된 스냅샷 기반입니다.
        런타임 환경변수 변경을 반영하려면 refresh_env()를 먼저 호출하세요.

        Args:
            file_path: 설정 파일 경로
            config_format: 파일 포맷 (AUTO면 자동 감지)
            merge: True면 기존 설정과 병합, False면 덮어쓰기
            required: True면 파일 없을 시 예외 발생
            _defer_env: True면 환경변수 오버라이드 지연 (내부 배치 호출용)

        Returns:
            로드 후 전체 설정 딕셔너리 (env override 포함, 방어적 복사)

        Raises:
            ConfigurationNotFoundException: 필수 파일이 없는 경우
            ConfigurationParseException: 파싱 실패한 경우
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        # 파일 존재 확인
        if not path.exists():
            if required:
                raise ConfigurationNotFoundException(
                    config_file=str(path),
                    searched_paths=[str(path)],
                )
            logger.warning("설정 파일 없음 (선택적)", extra={"file_path": str(path)})
            return {}

        # 포맷 결정
        actual_format = self._detect_format(path, config_format)

        # 파일 파싱
        data = self._parse_file(path, actual_format)

        # 데이터 적용
        with self._config_lock:
            if merge:
                self._merge_into(self._config, data)
            else:
                # merge=False: 전체 교체 — _entries도 초기화하여 stale entries 방지
                self._config.clear()
                self._config.update(data)
                self._entries.clear()

            # 메타데이터 업데이트
            self._metadata.add_loaded_file(str(path))
            self._update_entries(data, str(path))

            # 단일 load 호출 시 환경변수 오버라이드 즉시 적용
            # 배치 호출(load_multiple, load_with_profile)에서는 _defer_env=True로 지연
            if not _defer_env:
                self._apply_env_overrides()

            # lock 내에서 스냅샷 생성 → TOCTOU 방지
            # 배치 호출 시 반환값 미사용 → deepcopy 비용 회피
            result = {} if _defer_env else deepcopy(self._config)

        logger.info(
            "설정 파일 로드 완료",
            extra={"file_path": str(path), "format": actual_format.name},
        )
        return result

    def load_multiple(
        self,
        file_paths: list[str | Path],
        config_format: ConfigFormat = ConfigFormat.AUTO,
        required: bool = False,
    ) -> dict[str, Any]:
        """
        여러 설정 파일 순차 로드 및 병합.

        나중에 로드된 파일이 이전 파일을 오버라이드합니다.

        원자성 보장:
            파일 로드 중 예외가 발생하면 로드 시작 전 상태로 완전히 롤백합니다.
            부분 적용 상태(일부 파일만 로드된 불일치 상태)를 방지합니다.

        Args:
            file_paths: 설정 파일 경로 목록
            config_format: 파일 포맷
            required: 필수 여부

        Returns:
            병합된 전체 설정 딕셔너리

        Raises:
            ConfigurationNotFoundException: required=True 파일이 없는 경우 (롤백 후)
            ConfigurationParseException: 파싱 실패한 경우 (롤백 후)
        """
        with self._atomic_config_update():
            for path in file_paths:
                self.load(
                    path,
                    config_format=config_format,
                    merge=True,
                    required=required,
                    _defer_env=True,
                )

            # 모든 파일 로드 완료 후 환경변수 오버라이드 1회 적용
            with self._config_lock:
                self._apply_env_overrides()

        return self.to_dict()

    def load_with_profile(
        self,
        base_name: str,
        config_dir: str | Path = "config",
        config_format: ConfigFormat = ConfigFormat.AUTO,
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
            config_format: 파일 포맷

        Returns:
            병합된 전체 설정 딕셔너리
        """
        config_path = Path(config_dir)

        # 확장자 결정
        match config_format:
            case ConfigFormat.JSON:
                ext = ".json"
            case ConfigFormat.TOML:
                ext = ".toml"
            case _:
                ext = ".yaml"

        # 로드할 파일 목록
        files_to_load = [
            config_path / f"{base_name}{ext}",                    # 기본 설정
            config_path / f"{base_name}.{self._profile}{ext}",    # 프로파일 설정
            config_path / f"{base_name}.local{ext}",              # 로컬 설정
        ]

        with self._atomic_config_update():
            # 첫 번째 파일은 필수
            for i, fp in enumerate(files_to_load):
                self.load(fp, config_format=config_format, merge=True, required=(i == 0), _defer_env=True)

            # 모든 파일 로드 완료 후 환경변수 오버라이드 1회 적용
            with self._config_lock:
                self._apply_env_overrides()

        return self.to_dict()

    # --------------------------------------------------------
    # 값 조회 메서드
    # --------------------------------------------------------
    @overload
    def get(self, key: str) -> Any: ...
    @overload
    def get(self, key: str, default: T) -> T: ...
    @overload
    def get(self, key: str, default: T, value_type: type[T]) -> T: ...

    def get(
        self,
        key: str,
        default: Any = None,
        value_type: type[T] | None = None,
    ) -> Any:
        """
        설정 값 조회.

        중첩 키는 dot notation으로 접근합니다.
        YAML null(None)도 유효한 값으로 반환합니다.

        Args:
            key: 설정 키 (예: "server.host", "analysis.max_fps")
            default: 기본값
            value_type: 반환 타입 (자동 변환)

        Returns:
            설정 값 또는 기본값

        Example:
            >>> loader.get("s3.bucket_name", "courtview-videos")
            "courtview-videos"
            >>> loader.get("server.port", 8000, int)
            8000
        """
        with self._config_lock:
            value = self._get_nested(self._config, key)

        # sentinel: 키 자체가 존재하지 않음 → 기본값 반환
        # None: YAML null 등 유효한 값 → 그대로 반환
        if value is _MISSING:
            return default

        # 타입 변환
        if value_type is not None:
            try:
                return self._convert_type(value, value_type)
            except (ValueError, TypeError):
                logger.warning(
                    "타입 변환 실패",
                    extra={"key": key, "value": value, "target_type": value_type.__name__},
                )
                return default

        return value

    def get_required(
        self,
        key: str,
        value_type: type[T] | None = None,
    ) -> T:
        """
        필수 설정 값 조회.

        값이 없으면 예외를 발생시킵니다.
        YAML의 null(None) 값은 유효한 값으로 간주합니다.

        키 부재와 타입 변환 실패를 명확히 구분합니다:
        - 키 없음 → ConfigurationException (CONFIGURATION_NOT_FOUND)
        - 타입 변환 실패 → ConfigurationException (CONFIGURATION_ERROR, 변환 실패 메시지)

        Args:
            key: 설정 키
            value_type: 반환 타입

        Returns:
            설정 값

        Raises:
            ConfigurationException: 키가 존재하지 않는 경우
            ConfigurationException: 타입 변환에 실패한 경우
        """
        # 1단계: 키 존재 여부만 확인 (타입 변환 없음)
        with self._config_lock:
            raw = self._get_nested(self._config, key)

        if raw is _MISSING:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_NOT_FOUND,
                message=f"필수 설정 값이 없습니다: {key}",
                config_key=key,
            )

        # 2단계: 타입 변환 (키는 존재하므로, 변환 실패를 별도 에러로 분리)
        if value_type is None:
            return raw  # type: ignore[return-value]

        try:
            return self._convert_type(raw, value_type)
        except (ValueError, TypeError) as e:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_ERROR,
                message=(
                    f"필수 설정 값 타입 변환 실패: {key} "
                    f"({type(raw).__name__} → {value_type.__name__})"
                ),
                config_key=key,
            ) from e

    def get_int(self, key: str, default: int = 0) -> int:
        """정수 값 조회."""
        return self.get(key, default, int)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """실수 값 조회."""
        return self.get(key, default, float)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """불리언 값 조회."""
        return self.get(key, default, bool)

    def get_str(self, key: str, default: str = "") -> str:
        """문자열 값 조회."""
        return self.get(key, default, str)

    def get_list(self, key: str, default: list | None = None) -> list:
        """리스트 값 조회 (방어적 복사, YAML null과 키 부재를 sentinel로 구분)."""
        with self._config_lock:
            value = self._get_nested(self._config, key)
        if value is _MISSING:
            return [] if default is None else default
        if isinstance(value, list):
            return list(value)
        if value is None:
            return [] if default is None else default
        return [value]

    def get_dict(self, key: str, default: dict | None = None) -> dict:
        """딕셔너리 값 조회 (방어적 복사, YAML null과 키 부재를 sentinel로 구분)."""
        with self._config_lock:
            value = self._get_nested(self._config, key)
        if value is _MISSING:
            return {} if default is None else default
        if isinstance(value, dict):
            return dict(value)
        return {} if default is None else default

    def get_section(self, key: str) -> dict[str, Any]:
        """
        설정 섹션 전체 조회.

        Args:
            key: 섹션 키 (예: "analysis")

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

            # 엔트리 업데이트 (크기 제한 적용)
            self._put_entry(key, ConfigEntry(
                key=key,
                value=value,
                source=source,
            ))
            self._metadata.total_entries = len(self._entries)
            self._metadata.last_updated_at = datetime.now(timezone.utc)

    def set_multiple(self, values: dict[str, Any], source: ConfigSource = ConfigSource.DEFAULT) -> None:
        """
        여러 설정 값 원자적 저장.

        단일 lock 내에서 모든 키를 일괄 처리하여
        부분 업데이트 상태 노출을 방지합니다.

        Args:
            values: 키-값 딕셔너리
            source: 설정 소스
        """
        now = datetime.now(timezone.utc)
        with self._config_lock:
            for key, value in values.items():
                self._set_nested(self._config, key, value)
                self._put_entry(key, ConfigEntry(
                    key=key,
                    value=value,
                    source=source,
                ))
            self._metadata.total_entries = len(self._entries)
            self._metadata.last_updated_at = now

    # --------------------------------------------------------
    # 유틸리티 메서드
    # --------------------------------------------------------
    def has(self, key: str) -> bool:
        """키 존재 여부 확인 (YAML null도 존재로 판정)."""
        with self._config_lock:
            return self._get_nested(self._config, key) is not _MISSING

    def keys(self) -> list[str]:
        """
        모든 리프(leaf) 설정 키 반환 (dot notation).

        Note:
            섹션(중첩 dict) 키는 포함되지 않습니다. 리프 값 키만 반환합니다.

            예시: {"redis": {"host": "localhost", "port": 6379}}
              → ["redis.host", "redis.port"]  반환
              → "redis" 는 미포함 (섹션 키)

            섹션 키의 존재 여부는 has()로 확인하세요:
              loader.has("redis")        → True  (섹션 키)
              "redis" in loader.keys()   → False (리프 키 목록에 없음)
        """
        with self._config_lock:
            return list(self._entries.keys())

    def items(self) -> Iterator[tuple[str, Any]]:
        """모든 설정 항목 반복."""
        # 스냅샷을 생성하여 반복 중 변경 안전성 확보
        with self._config_lock:
            snapshot = list(self._entries.items())
        for key, entry in snapshot:
            yield key, entry.value

    def to_dict(self) -> dict[str, Any]:
        """전체 설정을 딕셔너리로 반환 (방어적 복사)."""
        with self._config_lock:
            return deepcopy(self._config)

    def as_readonly(self) -> MappingProxyType[str, Any]:
        """
        전체 설정을 읽기 전용 뷰로 반환 (복사 없음, O(1)).

        deepcopy 없이 O(1)로 최상위 키에 대한 읽기 전용 접근을 제공합니다.

        ⚠️ SHALLOW 불변성 경고:
            이 메서드는 최상위 키의 추가/삭제/교체만 차단합니다.
            중첩 dict의 내부 값은 여전히 직접 변경할 수 있습니다:

                proxy = loader.as_readonly()
                proxy["redis"]["host"] = "attacker.host"  # ← 가능! 전역 설정 오염!

            여러 서비스(analysis_service, wearable_service 등)가 동시에 이 뷰를
            공유할 경우, 한 서비스의 실수가 전역 설정을 오염시킬 위험이 있습니다.

        완전한 불변 복사본이 필요하면 to_dict()를 사용하세요 (deepcopy, O(n)).

        Returns:
            MappingProxyType 읽기 전용 뷰 (최상위 키만 보호)
        """
        return self._config_proxy

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

    def __repr__(self) -> str:
        """문자열 표현."""
        return (
            f"ConfigLoader(profile={self._profile!r}, "
            f"entries={len(self._entries)}, "
            f"files={len(self._metadata._loaded_files)})"
        )

    def clear(self) -> None:
        """모든 설정 초기화."""
        with self._config_lock:
            self._config.clear()
            self._entries.clear()
            self._split_cache.clear()
            self._metadata = ConfigMetadata()
            self._metadata.profile = self._profile

    def refresh_env(self) -> int:
        """
        환경변수 스냅샷 갱신 및 오버라이드 재적용.

        Docker/K8s 환경에서 ConfigMap 변경 후 호출하여
        런타임에 환경변수 변경을 반영합니다.

        COURTVIEW_PROFILE 변경도 감지하여 _profile 인스턴스 변수를 동기화합니다.
        이를 통해 loader.profile 프로퍼티와 환경변수가 항상 일치합니다.

        Returns:
            현재 COURTVIEW_ 환경변수 수 (PROFILE_ENV_VAR 제외)
        """
        with self._config_lock:
            new_snapshot = self._collect_env_snapshot()

            # COURTVIEW_PROFILE 변경 감지 → _profile / metadata 동기화
            new_profile = os.environ.get(PROFILE_ENV_VAR, DEFAULT_PROFILE)
            profile_changed = new_profile != self._profile
            if profile_changed:
                old_profile = self._profile
                self._profile = new_profile
                self._metadata.profile = new_profile
                logger.info(
                    "프로파일 변경 감지",
                    extra={"old": old_profile, "new": new_profile},
                )

            if new_snapshot != self._env_snapshot or profile_changed:
                self._env_snapshot = new_snapshot
                self._apply_env_overrides()
                count = len(new_snapshot)
                logger.info("환경변수 스냅샷 갱신 완료", extra={"count": count})
                return count

            return len(self._env_snapshot)

    # --------------------------------------------------------
    # 프라이빗 헬퍼 메서드
    # --------------------------------------------------------
    @contextmanager
    def _atomic_config_update(self):
        """
        원자적 설정 업데이트 컨텍스트 매니저.

        진입 시 현재 설정 상태를 스냅샷하고, 블록 내 예외 발생 시
        스냅샷으로 완전 롤백합니다. 부분 적용 상태를 방지합니다.

        Yields:
            None

        Raises:
            예외 발생 시 롤백 후 원본 예외를 재발생시킵니다.
        """
        with self._config_lock:
            config_snapshot = deepcopy(self._config)
            entries_snapshot = dict(self._entries)
            metadata_files_snapshot = dict(self._metadata._loaded_files)
            metadata_env_snapshot = dict(self._metadata._env_overrides)

        try:
            yield
        except Exception:
            with self._config_lock:
                self._config.clear()
                self._config.update(config_snapshot)
                self._entries.clear()
                self._entries.update(entries_snapshot)
                self._metadata._loaded_files.clear()
                self._metadata._loaded_files.update(metadata_files_snapshot)
                self._metadata._env_overrides.clear()
                self._metadata._env_overrides.update(metadata_env_snapshot)
                self._metadata.total_entries = len(self._entries)
            raise

    @staticmethod
    def _collect_env_snapshot() -> dict[str, str]:
        """
        COURTVIEW_ 접두사 환경변수 수집.

        PROFILE_ENV_VAR(COURTVIEW_PROFILE)는 제외합니다.
        해당 환경변수는 _do_init / refresh_env 에서 _profile 인스턴스 변수로만
        처리됩니다. _apply_env_overrides를 통해 config["profile"]로 이중 삽입되면
        loader.profile 프로퍼티와 get("profile") 반환값이 불일치하는 부작용이
        발생하므로 단일 경로로 관리합니다.
        """
        return {
            k: v for k, v in os.environ.items()
            if k.startswith(ENV_PREFIX) and k != PROFILE_ENV_VAR
        }

    def _split_key(self, key: str) -> tuple[str, ...]:
        """
        dot-notation 키를 분할하여 캐시된 tuple 반환 (LRU 방식).

        동일 키 반복 조회 시 str.split() + list 생성 비용을 제거합니다.
        tuple은 list 대비 ~20% 적은 메모리를 사용합니다.
        접근된 키를 맨 뒤로 이동하여 LRU 퇴거를 구현합니다.

        호출자가 _config_lock 내에서 호출하므로 별도 lock 불필요.
        """
        # pop + re-insert: 캐시 히트 시 맨 뒤로 이동 (LRU)
        parts = self._split_cache.pop(key, None)
        if parts is not None:
            self._split_cache[key] = parts
            return parts

        # 캐시 미스: 새로 생성
        parts = tuple(key.split("."))
        if len(self._split_cache) >= _SPLIT_CACHE_MAX_SIZE:
            # LRU 퇴거: 가장 오래 미사용 항목 제거 (dict insertion order 맨 앞)
            self._split_cache.pop(next(iter(self._split_cache)))
        self._split_cache[key] = parts
        return parts

    def _put_entry(self, key: str, entry: ConfigEntry) -> None:
        """
        _entries에 항목 추가 (크기 제한 적용).

        장시간 운영 + 빈번한 set() 호출 시 무한 성장 방지.
        기존 키 업데이트는 크기 변화 없으므로 퇴거 없이 통과.
        호출자가 _config_lock 내에서 호출.
        """
        if key not in self._entries and len(self._entries) >= _ENTRIES_MAX_SIZE:
            # FIFO 퇴거: 가장 오래된 항목 제거
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]
        self._entries[key] = entry

    @staticmethod
    def _detect_format(path: Path, config_format: ConfigFormat) -> ConfigFormat:
        """파일 포맷 감지."""
        if config_format != ConfigFormat.AUTO:
            return config_format

        suffix = path.suffix.lower()
        if suffix in YAML_EXTENSIONS:
            return ConfigFormat.YAML
        if suffix in JSON_EXTENSIONS:
            return ConfigFormat.JSON
        if suffix in TOML_EXTENSIONS:
            return ConfigFormat.TOML
        # 기본값은 YAML
        return ConfigFormat.YAML

    @staticmethod
    def _parse_file(path: Path, fmt: ConfigFormat) -> dict[str, Any]:
        """
        파일을 파싱하여 딕셔너리로 반환.

        Args:
            path: 파일 경로 (존재 확인 완료)
            fmt: 확정된 포맷 (AUTO 아님)

        Returns:
            파싱된 설정 딕셔너리

        Raises:
            ConfigurationParseException: 파싱 실패
            ConfigurationException: 기타 로드 실패
        """
        try:
            match fmt:
                case ConfigFormat.YAML:
                    with open(path, "r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
                case ConfigFormat.JSON:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                case ConfigFormat.TOML:
                    with open(path, "rb") as fb:
                        return tomllib.load(fb)
                case _:
                    # _detect_format이 항상 YAML/JSON/TOML 중 하나를 반환하므로
                    # 이 분기는 정상 경로에서 도달 불가합니다.
                    # ConfigFormat 열거형이 향후 확장될 경우를 대비한 방어적 폴백으로,
                    # 알 수 없는 포맷은 YAML로 처리하고 경고 로그를 남깁니다.
                    logger.warning(
                        "알 수 없는 설정 포맷, YAML로 폴백",
                        extra={"format": fmt, "file_path": str(path)},
                    )
                    with open(path, "r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
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
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationParseException(
                config_file=str(path),
                reason=f"TOML 파싱 오류: {e}",
                cause=e,
            )
        except Exception as e:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_LOAD_FAILED,
                message=f"설정 파일 로드 실패: {path}",
                config_file=str(path),
                cause=e,
            )

    def _merge_into(self, target: dict, source: dict, *, _depth: int = 0) -> None:
        """source를 target에 in-place 딥 머지 (내부 재귀용). 호출자가 lock 보유."""
        if _depth > _MAX_NESTING_DEPTH:
            raise ConfigurationException(
                error_code=ErrorCode.CONFIGURATION_ERROR,
                message=f"설정 병합 깊이 초과 (최대 {_MAX_NESTING_DEPTH}단계)",
            )
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_into(target[key], value, _depth=_depth + 1)
            else:
                # source는 yaml.safe_load/json.load/tomllib.load 직출력 → 외부 참조 없음, 복사 불필요
                target[key] = value

    def _get_nested(self, data: dict, key: str) -> Any:
        """
        중첩 키로 값 조회.

        키가 존재하지 않으면 _MISSING sentinel을 반환하여
        YAML null(None)과 "키 부재"를 명확히 구분합니다.
        호출자가 _config_lock 보유.
        """
        keys = self._split_key(key)
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return _MISSING

        return current

    def _set_nested(self, data: dict, key: str, value: Any) -> None:
        """중첩 키로 값 설정. 호출자가 _config_lock 보유."""
        keys = self._split_key(key)

        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]

        data[keys[-1]] = value

    def _update_entries(self, data: dict, file_path: str, prefix: str = "", *, _depth: int = 0) -> None:
        """
        설정 항목 업데이트.

        재귀 호출 시 len() 반복 계산을 방지하기 위해
        total_entries는 최상위 호출에서만 1회 갱신합니다.
        호출자가 _config_lock 보유.
        """
        if _depth > _MAX_NESTING_DEPTH:
            logger.warning("설정 항목 업데이트 깊이 초과 (최대 %d단계), 하위 항목 무시", _MAX_NESTING_DEPTH)
            return
        is_root = not prefix
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._update_entries(value, file_path, full_key, _depth=_depth + 1)
            else:
                self._put_entry(full_key, ConfigEntry(
                    key=full_key,
                    value=value,
                    source=ConfigSource.FILE,
                    file_path=file_path,
                ))

        # 최상위 호출에서만 1회 갱신
        if is_root:
            self._metadata.total_entries = len(self._entries)

    def _apply_env_overrides(self) -> None:
        """
        환경변수 오버라이드 적용.

        인스턴스 생성 시 수집된 _env_snapshot 기반으로 적용합니다.
        런타임 환경변수 변경을 반영하려면 refresh_env()를 먼저 호출하세요.
        호출자가 _config_lock 보유.
        """
        for env_key, env_value in self._env_snapshot.items():

            # COURTVIEW_S3__BUCKET_NAME → s3.bucket_name
            # 접두사 "COURTVIEW_" 제거 후 "__" → "." (계층 구분), "_" → "_" (유지)
            config_key = env_key[len(ENV_PREFIX):].lower().replace("__", ".")

            # 타입 추론 및 변환
            converted_value = self._parse_env_value(env_value)

            self._set_nested(self._config, config_key, converted_value)
            self._put_entry(config_key, ConfigEntry(
                key=config_key,
                value=converted_value,
                source=ConfigSource.ENV,
                original_value=env_value,
            ))
            self._metadata.add_env_override(config_key)

            logger.debug(
                "환경변수 오버라이드 적용",
                extra={"config_key": config_key, "value": converted_value},
            )

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """
        환경변수 값 파싱 및 타입 변환.

        변환 순서: bool → null → int → float → JSON → str
        "0"/"1"은 숫자 파서에서 처리하여 bool 오변환 방지.
        """
        low = value.lower()
        match low:
            case "true" | "yes" | "on":
                return True
            case "false" | "no" | "off":
                return False
            case "null" | "none" | "~":
                # YAML null과 일관성 유지
                return None
            case _:
                # 숫자 변환 시도
                for parser in (int, float):
                    try:
                        return parser(value)
                    except ValueError:
                        continue

                # JSON 배열/객체
                if value and value[0] in ("[", "{"):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        pass

                return value

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """불리언 파싱 (match 문 활용)."""
        match value:
            case bool():
                return value
            case str():
                return value.lower() in ("true", "yes", "1", "on")
            case int() | float():
                return bool(value)
            case _:
                return False

    # 안전하게 target_type(value) 호출이 가능한 스칼라 타입만 허용
    _SAFE_CONVERT_TYPES: frozenset[type] = frozenset({int, float, str, bool})

    def _convert_type(self, value: Any, target_type: type[T]) -> T:
        """
        타입 변환.

        스칼라 타입(int, float, str, bool)만 안전 변환합니다.
        컨테이너 타입(list, dict 등)은 isinstance 일치 확인만 허용합니다.

        bool/int 상속 관계 처리:
        - Python에서 bool은 int 서브클래스이므로 isinstance(True, int) == True.
        - isinstance 대신 type() 정확 비교(type(value) is target_type)를 사용하여
          bool → int 투과(True가 int로 통과) 및 int → bool 투과를 차단합니다.
        - bool 변환은 항상 _parse_bool을 통해 명시적으로 처리합니다.

        Examples:
            _convert_type(True, int)  → int(True) → 1       (bool → int 명시 변환)
            _convert_type(1, bool)    → _parse_bool(1) → True
            _convert_type(True, bool) → _parse_bool(True) → True
            _convert_type("8080", int)→ int("8080") → 8080
        """
        # bool 변환: isinstance보다 먼저 처리 (bool은 int 서브클래스이므로 순서가 중요)
        if target_type is bool:
            return self._parse_bool(value)  # type: ignore[return-value]

        # 정확한 타입 일치 확인 (isinstance 미사용 — bool/int 상속 투과 방지)
        # isinstance(True, int) == True 이므로 type() 정확 비교 사용
        if type(value) is target_type:
            return value

        # 컨테이너 타입(list, dict 등)은 target_type(value) 호출 시 의도치 않은 결과 방지
        # 예: list("abc") → ["a", "b", "c"] / dict([(1,2)]) → {1: 2}
        if target_type not in self._SAFE_CONVERT_TYPES:
            raise TypeError(
                f"안전하지 않은 타입 변환: {type(value).__name__} → {target_type.__name__}"
            )

        return target_type(value)


# =============================================================================
# 헬퍼 함수
# =============================================================================
def load_config(
    file_path: str | Path,
    config_format: ConfigFormat = ConfigFormat.AUTO,
    merge: bool = True,
    required: bool = True,
) -> dict[str, Any]:
    """
    설정 파일 로드 헬퍼 함수.

    Args:
        file_path: 설정 파일 경로
        config_format: 파일 포맷
        merge: 병합 여부
        required: 필수 여부

    Returns:
        로드 후 전체 설정 딕셔너리

    Example:
        >>> config = load_config("config/app.yaml")
        >>> print(config["server"]["port"])
    """
    loader = ConfigLoader.get_instance()
    return loader.load(file_path, config_format=config_format, merge=merge, required=required)


def get_config_value(
    key: str,
    default: Any = None,
    value_type: type[T] | None = None,
) -> Any:
    """
    설정 값 조회 헬퍼 함수.

    Args:
        key: 설정 키
        default: 기본값
        value_type: 반환 타입

    Returns:
        설정 값 또는 기본값

    Example:
        >>> bucket = get_config_value("s3.bucket_name", "courtview-videos")
        >>> port = get_config_value("server.port", 8000, int)
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
