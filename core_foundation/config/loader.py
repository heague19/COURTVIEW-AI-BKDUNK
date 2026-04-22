# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: loader.py
설명: YAML/ENV 설정 로더 — 멀티소스 설정 로딩 및 병합 엔진
      - YAML 파일 로딩 (base → environment → local 3단계 병합)
      - 환경 변수 오버라이드 (COURTVIEW_ 접두어)
      - 재귀적 딕셔너리 병합 (deep merge)
      - 스레드 안전 (RLock)
      - 설정 캐싱 및 무효화

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import copy
import os
import platform
import threading
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, ClassVar, Final

# =============================================================================
# 서드파티 (Third-party)
# =============================================================================
import yaml

# =============================================================================
# 프로젝트 내부 (Project Internal) — Layer 0: shared만 참조
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.validation_exceptions import (
    ConfigurationLoadException,
    ConfigurationNotFoundException,
    ConfigurationParseException,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 환경 변수 접두어 — COURTVIEW_DATABASE__HOST → database.host
ENV_PREFIX: Final[str] = "COURTVIEW_"

# 환경 변수 중첩 구분자 — __ (더블 언더스코어) → 딕셔너리 중첩
ENV_SEPARATOR: Final[str] = "__"

# 기본 설정 디렉토리 (프로젝트 루트 기준)
DEFAULT_CONFIG_DIR: Final[str] = "configs"

# YAML 파일 최대 크기 (10MB — DoS 방지)
MAX_YAML_FILE_SIZE_BYTES: Final[int] = 10 * 1024 * 1024

# 병합 깊이 제한 (무한 재귀 방지)
MAX_MERGE_DEPTH: Final[int] = 20

# 지원 YAML 확장자
YAML_EXTENSIONS: Final[tuple[str, ...]] = (".yaml", ".yml")


# =============================================================================
# 환경 열거형
# =============================================================================

@unique
class Environment(Enum):
    """실행 환경 열거형."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    PRODUCTION = "production"

    @property
    def is_development(self) -> bool:
        """개발 환경 여부."""
        return self in _DEVELOPMENT_ENVIRONMENTS

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부."""
        return self is Environment.PRODUCTION

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _ENVIRONMENT_KOREAN_MAP[self]

    @classmethod
    def from_string(cls, value: str) -> Environment:
        """문자열에서 환경 파싱. 대소문자 무시."""
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"알 수 없는 환경: '{value}'. "
            f"허용값: {[m.value for m in cls]}"
        )


# 환경 관련 캐시 (frozenset/dict — 모듈 로드 시 1회 생성)
_DEVELOPMENT_ENVIRONMENTS: Final[frozenset[Environment]] = frozenset({
    Environment.LOCAL,
    Environment.DEVELOPMENT,
})

_ENVIRONMENT_KOREAN_MAP: Final[dict[Environment, str]] = {
    Environment.LOCAL: "로컬",
    Environment.DEVELOPMENT: "개발",
    Environment.PRODUCTION: "프로덕션",
}


# =============================================================================
# OS 플랫폼 열거형
# =============================================================================

@unique
class OSPlatform(Enum):
    """운영 체제 플랫폼 열거형."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _OS_PLATFORM_KOREAN_MAP[self]

    @classmethod
    def detect(cls) -> OSPlatform:
        """현재 OS 플랫폼 자동 감지."""
        system = platform.system().lower()
        if system == "windows":
            return cls.WINDOWS
        elif system == "darwin":
            return cls.MACOS
        elif system == "linux":
            return cls.LINUX
        # 미지원 OS는 Linux 폴백 (POSIX 호환 가정)
        return cls.LINUX


_OS_PLATFORM_KOREAN_MAP: Final[dict[OSPlatform, str]] = {
    OSPlatform.WINDOWS: "윈도우",
    OSPlatform.MACOS: "맥OS",
    OSPlatform.LINUX: "리눅스",
}


# =============================================================================
# 설정 로드 결과 DTO
# =============================================================================

@dataclass(slots=True)
class ConfigLoadResult:
    """설정 로드 결과.

    Attributes:
        data: 병합된 설정 딕셔너리 (방어적 복사본)
        loaded_files: 로드된 YAML 파일 경로 목록 (로드 순서)
        environment: 감지된 실행 환경
        os_platform: 감지된 OS 플랫폼
        env_overrides: 환경 변수에서 오버라이드된 키 목록
    """

    data: dict[str, Any]
    loaded_files: list[str]
    environment: Environment
    os_platform: OSPlatform
    env_overrides: list[str]

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """점 구분자 키로 중첩 값 접근.

        Args:
            dotted_key: 점 구분 키 (예: "gpu.batch_size")
            default: 기본값

        Returns:
            설정 값 또는 기본값
        """
        keys = dotted_key.split(".")
        current: Any = self.data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def __repr__(self) -> str:
        return (
            f"ConfigLoadResult("
            f"files={len(self.loaded_files)}, "
            f"env={self.environment.value}, "
            f"os={self.os_platform.value}, "
            f"overrides={len(self.env_overrides)})"
        )


# =============================================================================
# 핵심 클래스: ConfigLoader
# =============================================================================

class ConfigLoader:
    """YAML/ENV 설정 로더.

    3단계 병합 전략:
        1. base 설정 (base_config.yaml 등)
        2. environment 설정 (local.yaml / windows.yaml 등)
        3. 환경 변수 오버라이드 (COURTVIEW_ 접두어)

    병합 우선순위: 환경 변수 > environment YAML > base YAML

    스레드 안전:
        내부 RLock으로 동시 로드/캐시 접근 보호.
        같은 설정 파일 중복 로드 시 캐시 반환.

    사용 예시::

        loader = ConfigLoader(config_dir="configs")
        result = loader.load("base/base_config.yaml")
        batch_size = result.get("gpu.batch_size", 4)

        # 하위 디렉토리 로딩
        detection = loader.load("detection/ball/ball_detection.yaml")

        # 환경 변수 오버라이드
        # COURTVIEW_GPU__BATCH_SIZE=8 → {"gpu": {"batch_size": "8"}}
    """

    # 클래스 레벨 상수
    _ENV_PREFIX: ClassVar[str] = ENV_PREFIX
    _ENV_SEPARATOR: ClassVar[str] = ENV_SEPARATOR

    def __init__(
        self,
        config_dir: str | Path | None = None,
        environment: Environment | None = None,
        os_platform: OSPlatform | None = None,
        *,
        enable_env_override: bool = True,
        enable_cache: bool = True,
    ) -> None:
        """
        ConfigLoader 초기화.

        Args:
            config_dir: 설정 파일 루트 디렉토리. None이면 프로젝트 루트/configs.
            environment: 실행 환경. None이면 COURTVIEW_ENV 환경 변수 또는 local.
            os_platform: OS 플랫폼. None이면 자동 감지.
            enable_env_override: 환경 변수 오버라이드 활성화 여부.
            enable_cache: 파일 캐싱 활성화 여부.
        """
        self._lock = threading.RLock()

        # 설정 디렉토리 해석
        if config_dir is not None:
            self._config_dir = Path(config_dir).resolve()
        else:
            # 프로젝트 루트 = core_foundation 상위 2단계
            project_root = Path(__file__).resolve().parent.parent.parent
            self._config_dir = project_root / DEFAULT_CONFIG_DIR

        # 환경 감지
        self._environment = environment or self._detect_environment()
        self._os_platform = os_platform or OSPlatform.detect()

        # 옵션
        self._enable_env_override = enable_env_override
        self._enable_cache = enable_cache

        # 캐시: 파일 경로 → 파싱된 딕셔너리
        self._file_cache: dict[str, dict[str, Any]] = {}

        # 로드 결과 캐시: 설정 키 → ConfigLoadResult
        self._result_cache: dict[str, ConfigLoadResult] = {}

    # =========================================================================
    # 공개 API
    # =========================================================================

    def load(
        self,
        config_path: str,
        *,
        merge_environment: bool = True,
        merge_os: bool = True,
    ) -> ConfigLoadResult:
        """설정 파일 로드 및 병합.

        3단계 병합:
            1. config_path에 지정된 base 파일
            2. environments/{environment}.yaml (merge_environment=True 시)
            3. environments/{os_platform}.yaml (merge_os=True 시)
            4. 환경 변수 오버라이드

        Args:
            config_path: 설정 파일 상대 경로 (config_dir 기준)
            merge_environment: 환경별 오버라이드 병합 여부
            merge_os: OS별 오버라이드 병합 여부

        Returns:
            ConfigLoadResult: 병합된 설정 결과

        Raises:
            ConfigurationNotFoundException: 설정 파일 미발견
            ConfigurationLoadException: 파일 읽기 실패
            ConfigurationParseException: YAML 파싱 실패
        """
        cache_key = f"{config_path}|env={merge_environment}|os={merge_os}"

        with self._lock:
            # 캐시 확인
            if self._enable_cache and cache_key in self._result_cache:
                cached = self._result_cache[cache_key]
                # 방어적 복사 반환
                return ConfigLoadResult(
                    data=copy.deepcopy(cached.data),
                    loaded_files=list(cached.loaded_files),
                    environment=cached.environment,
                    os_platform=cached.os_platform,
                    env_overrides=list(cached.env_overrides),
                )

            # 1단계: base 설정 로드
            merged: dict[str, Any] = {}
            loaded_files: list[str] = []

            base_data = self._load_yaml_file(config_path)
            merged = self._deep_merge(merged, base_data)
            loaded_files.append(config_path)

            # 2단계: 환경별 오버라이드
            if merge_environment:
                env_file = f"environments/{self._environment.value}.yaml"
                env_data = self._try_load_yaml_file(env_file)
                if env_data is not None:
                    merged = self._deep_merge(merged, env_data)
                    loaded_files.append(env_file)

            # 3단계: OS별 오버라이드
            if merge_os:
                os_file = f"environments/{self._os_platform.value}.yaml"
                os_data = self._try_load_yaml_file(os_file)
                if os_data is not None:
                    merged = self._deep_merge(merged, os_data)
                    loaded_files.append(os_file)

            # 4단계: 환경 변수 오버라이드
            env_overrides: list[str] = []
            if self._enable_env_override:
                merged, env_overrides = self._apply_env_overrides(merged)

            result = ConfigLoadResult(
                data=merged,
                loaded_files=loaded_files,
                environment=self._environment,
                os_platform=self._os_platform,
                env_overrides=env_overrides,
            )

            # 캐시 저장
            if self._enable_cache:
                self._result_cache[cache_key] = ConfigLoadResult(
                    data=copy.deepcopy(merged),
                    loaded_files=list(loaded_files),
                    environment=self._environment,
                    os_platform=self._os_platform,
                    env_overrides=list(env_overrides),
                )

            return result

    def load_raw(self, config_path: str) -> dict[str, Any]:
        """단일 YAML 파일 로드 (병합 없음).

        Args:
            config_path: 설정 파일 상대 경로

        Returns:
            파싱된 딕셔너리 (방어적 복사본)

        Raises:
            ConfigurationNotFoundException: 파일 미발견
            ConfigurationLoadException: 읽기 실패
            ConfigurationParseException: 파싱 실패
        """
        with self._lock:
            data = self._load_yaml_file(config_path)
            return copy.deepcopy(data)

    def invalidate_cache(self, config_path: str | None = None) -> int:
        """캐시 무효화.

        Args:
            config_path: 특정 파일만 무효화. None이면 전체 무효화.

        Returns:
            무효화된 캐시 항목 수
        """
        with self._lock:
            if config_path is None:
                count = len(self._file_cache) + len(self._result_cache)
                self._file_cache.clear()
                self._result_cache.clear()
                return count

            # 특정 파일 관련 캐시 무효화
            count = 0
            resolved = str(self._resolve_path(config_path))
            if resolved in self._file_cache:
                del self._file_cache[resolved]
                count += 1

            # 해당 파일을 포함하는 결과 캐시도 무효화
            keys_to_remove = [
                k for k, v in self._result_cache.items()
                if config_path in v.loaded_files
            ]
            for key in keys_to_remove:
                del self._result_cache[key]
                count += 1

            return count

    @property
    def config_dir(self) -> Path:
        """설정 디렉토리 경로."""
        return self._config_dir

    @property
    def environment(self) -> Environment:
        """현재 실행 환경."""
        return self._environment

    @property
    def os_platform(self) -> OSPlatform:
        """현재 OS 플랫폼."""
        return self._os_platform

    @property
    def cache_size(self) -> int:
        """현재 캐시 항목 수."""
        with self._lock:
            return len(self._file_cache) + len(self._result_cache)

    def __repr__(self) -> str:
        return (
            f"ConfigLoader("
            f"dir='{self._config_dir}', "
            f"env={self._environment.value}, "
            f"os={self._os_platform.value}, "
            f"cache={self.cache_size})"
        )

    # =========================================================================
    # 내부 메서드 — YAML 로딩
    # =========================================================================

    def _resolve_path(self, config_path: str) -> Path:
        """상대 경로를 절대 경로로 해석.

        Args:
            config_path: config_dir 기준 상대 경로

        Returns:
            절대 경로
        """
        resolved = (self._config_dir / config_path).resolve()

        # 확장자 없으면 .yaml 추가
        if resolved.suffix not in YAML_EXTENSIONS:
            for ext in YAML_EXTENSIONS:
                candidate = resolved.with_suffix(ext)
                if candidate.is_file():
                    return candidate
            # 후보 없으면 .yaml 기본값
            resolved = resolved.with_suffix(".yaml")

        return resolved

    def _load_yaml_file(self, config_path: str) -> dict[str, Any]:
        """YAML 파일 로드 (캐시 적용).

        Args:
            config_path: 상대 경로

        Returns:
            파싱된 딕셔너리

        Raises:
            ConfigurationNotFoundException: 파일 미발견
            ConfigurationLoadException: 읽기 실패
            ConfigurationParseException: 파싱 실패
        """
        resolved = self._resolve_path(config_path)
        cache_key = str(resolved)

        # 파일 캐시 확인
        if self._enable_cache and cache_key in self._file_cache:
            return self._file_cache[cache_key]

        # 파일 존재 확인
        if not resolved.is_file():
            raise ConfigurationNotFoundException(
                config_file=config_path,
                searched_paths=[str(self._config_dir)],
            )

        # 파일 크기 확인 (DoS 방지)
        file_size = resolved.stat().st_size
        if file_size > MAX_YAML_FILE_SIZE_BYTES:
            raise ConfigurationLoadException(
                config_file=config_path,
                reason=(
                    f"파일 크기 초과: {file_size:,} bytes "
                    f"(최대: {MAX_YAML_FILE_SIZE_BYTES:,} bytes)"
                ),
            )

        # 파일 읽기
        try:
            raw_content = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationLoadException(
                config_file=config_path,
                reason=f"파일 읽기 실패: {exc}",
                cause=exc,
            ) from exc

        # YAML 파싱
        try:
            # yaml.safe_load: 임의 Python 객체 실행 방지 (보안)
            parsed = yaml.safe_load(raw_content)
        except yaml.YAMLError as exc:
            line_number = None
            if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
                line_number = exc.problem_mark.line + 1
            raise ConfigurationParseException(
                config_file=config_path,
                reason=str(exc),
                line_number=line_number,
                cause=exc,
            ) from exc

        # 빈 파일 → 빈 딕셔너리
        if parsed is None:
            parsed = {}

        # 최상위가 딕셔너리가 아니면 에러
        if not isinstance(parsed, dict):
            raise ConfigurationParseException(
                config_file=config_path,
                reason=f"최상위 구조가 dict가 아닙니다: {type(parsed).__name__}",
            )

        # 캐시 저장
        if self._enable_cache:
            self._file_cache[cache_key] = parsed

        return parsed

    def _try_load_yaml_file(self, config_path: str) -> dict[str, Any] | None:
        """YAML 파일 선택적 로드 (파일 없으면 None 반환).

        환경/OS 오버라이드 파일은 존재하지 않을 수 있으므로
        FileNotFound는 무시하고 None을 반환한다.

        Args:
            config_path: 상대 경로

        Returns:
            파싱된 딕셔너리 또는 None
        """
        try:
            return self._load_yaml_file(config_path)
        except ConfigurationNotFoundException:
            return None

    # =========================================================================
    # 내부 메서드 — 딕셔너리 병합
    # =========================================================================

    @staticmethod
    def _deep_merge(
        base: dict[str, Any],
        override: dict[str, Any],
        _depth: int = 0,
    ) -> dict[str, Any]:
        """재귀적 딕셔너리 병합 (deep merge).

        override의 값이 base의 동일 키를 덮어쓴다.
        양쪽 모두 dict인 경우에만 재귀적으로 병합한다.

        Args:
            base: 기본 딕셔너리
            override: 오버라이드 딕셔너리
            _depth: 현재 재귀 깊이 (내부용)

        Returns:
            병합된 딕셔너리 (base의 복사본 기반)
        """
        if _depth > MAX_MERGE_DEPTH:
            # 무한 재귀 방지 — 깊이 초과 시 override로 대체
            return copy.deepcopy(override)

        result = copy.deepcopy(base)

        for key, override_value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(override_value, dict)
            ):
                # 양쪽 모두 dict → 재귀 병합
                result[key] = ConfigLoader._deep_merge(
                    result[key], override_value, _depth + 1,
                )
            else:
                # 그 외 → 오버라이드 값으로 대체
                result[key] = copy.deepcopy(override_value)

        return result

    # =========================================================================
    # 내부 메서드 — 환경 변수 오버라이드
    # =========================================================================

    def _apply_env_overrides(
        self,
        config: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """환경 변수 오버라이드 적용.

        COURTVIEW_ 접두어를 가진 환경 변수를 탐색하여
        설정 딕셔너리에 오버라이드한다.

        변환 규칙:
            COURTVIEW_GPU__BATCH_SIZE=8
            → config["gpu"]["batch_size"] = "8"

        Args:
            config: 기존 설정 딕셔너리

        Returns:
            (오버라이드된 설정, 오버라이드된 키 목록)
        """
        result = copy.deepcopy(config)
        overridden_keys: list[str] = []

        prefix = self._ENV_PREFIX
        separator = self._ENV_SEPARATOR

        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue

            # 접두어 제거 후 키 파싱
            # COURTVIEW_GPU__BATCH_SIZE → GPU__BATCH_SIZE → ["gpu", "batch_size"]
            stripped = env_key[len(prefix):]
            parts = [p.lower() for p in stripped.split(separator) if p]

            if not parts:
                continue

            # 딕셔너리에 값 설정
            current = result
            for i, part in enumerate(parts[:-1]):
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            final_key = parts[-1]
            current[final_key] = self._coerce_env_value(env_value)
            overridden_keys.append(".".join(parts))

        return result, overridden_keys

    @staticmethod
    def _coerce_env_value(value: str) -> Any:
        """환경 변수 문자열을 Python 타입으로 변환.

        변환 규칙 (순서대로 시도):
            "true"/"false" → bool
            정수 형태 → int
            실수 형태 → float
            "none"/"null" → None
            그 외 → str

        Args:
            value: 환경 변수 값 (문자열)

        Returns:
            변환된 Python 값
        """
        lower = value.strip().lower()

        # bool
        if lower == "true":
            return True
        if lower == "false":
            return False

        # None
        if lower in ("none", "null", ""):
            return None

        # int
        try:
            return int(value)
        except ValueError:
            pass

        # float
        try:
            return float(value)
        except ValueError:
            pass

        # str
        return value

    # =========================================================================
    # 내부 메서드 — 환경 감지
    # =========================================================================

    @staticmethod
    def _detect_environment() -> Environment:
        """실행 환경 자동 감지.

        감지 순서:
            1. COURTVIEW_ENV 환경 변수
            2. 기본값: local

        Returns:
            감지된 Environment
        """
        env_str = os.environ.get("COURTVIEW_ENV", "").strip()
        if env_str:
            try:
                return Environment.from_string(env_str)
            except ValueError:
                # 잘못된 환경 변수 → local 폴백
                pass
        return Environment.LOCAL


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "Environment",
    "OSPlatform",
    # 상수
    "ENV_PREFIX",
    "ENV_SEPARATOR",
    "DEFAULT_CONFIG_DIR",
    "MAX_YAML_FILE_SIZE_BYTES",
    "MAX_MERGE_DEPTH",
    "YAML_EXTENSIONS",
    # 데이터 클래스
    "ConfigLoadResult",
    # 핵심 클래스
    "ConfigLoader",
]

__version__ = "1.0.0"
