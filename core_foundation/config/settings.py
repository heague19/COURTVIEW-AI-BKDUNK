# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: settings.py
설명: 전역 설정 Singleton — 중앙 설정 관리 엔진
      - ConfigLoader + ConfigValidator 통합
      - 스레드 안전 Singleton (Double-Checked Locking)
      - 점 구분자 키 접근 (dotted key)
      - 섹션 기반 접근 (GPU, 카메라, 시스템 등)
      - 설정 리로드 및 스냅샷

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import copy
import threading
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final

# =============================================================================
# 프로젝트 내부 (Project Internal) — 동일 패키지 내 참조
# =============================================================================
from core_foundation.config.loader import (
    ConfigLoader,
    ConfigLoadResult,
    Environment,
    OSPlatform,
)
from core_foundation.config.validator import (
    ConfigValidator,
    ValidationResult,
    ValidationRule,
)

# =============================================================================
# 프로젝트 내부 (Project Internal) — Layer 0: shared만 참조
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.validation_exceptions import (
    ConfigurationLoadException,
    ConfigurationNotFoundException,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 설정 파일 경로 (configs/ 기준 상대 경로)
#
# .. note::
#     SPOIN 2026-04-20 확정: ``configs/core_foundation/*.yaml``은 의도적으로 삭제됨
#     (커밋 9ada53e 이후). core_foundation 프레임워크는 자체 설정 파일을 요구하지 않고
#     코드 내부 ``_DEFAULT_CONFIG`` + 상위 Application 설정 주입 방식으로 동작.
#
#     이 상수는 **하위 호환성 및 수동 커스터마이징용**으로 보존됨. 해당 경로에 파일이 없어도
#     ``ConfigLoader._try_load_yaml_file()``이 ``None``을 반환하므로 ``AppSettings``는
#     ``use_defaults=True`` 폴백으로 정상 동작함 (로그 경고 없음).
DEFAULT_CONFIG_FILE: Final[str] = "core_foundation/config.yaml"

# 설정 스냅샷 최대 보관 수 (메모리 성장 방지)
MAX_SNAPSHOT_COUNT: Final[int] = 10

# 설정 기본값 — 설정 파일 없이도 최소 동작 보장
_DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "gpu": {
        "batch_size": 4,
        "fp16": True,
        "device": "cuda:0",
        "vram_limit_mb": 8192,
    },
    "camera": {
        "count": 1,
        "fps": 30,
        "resolution_width": 1920,
        "resolution_height": 1080,
        "sync_tolerance_ms": 1.0,
    },
    "system": {
        "log_level": "INFO",
        "max_workers": 4,
    },
    "analysis": {
        "target_accuracy": 0.92,
        "confidence_threshold": 0.5,
    },
}


# =============================================================================
# 설정 스냅샷 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ConfigSnapshot:
    """설정 상태 스냅샷.

    리로드 전후 비교, 변경 추적에 사용.

    Attributes:
        data: 스냅샷 시점의 전체 설정 (방어적 복사본)
        timestamp: 스냅샷 생성 시각 (monotonic)
        load_result: 로드 결과 메타데이터
        validation_result: 검증 결과
    """

    data: dict[str, Any]
    timestamp: float
    load_result: ConfigLoadResult | None
    validation_result: ValidationResult | None

    def __repr__(self) -> str:
        valid_str = "N/A"
        if self.validation_result is not None:
            valid_str = str(self.validation_result.is_valid)
        return (
            f"ConfigSnapshot("
            f"keys={len(self.data)}, "
            f"valid={valid_str})"
        )


# =============================================================================
# 핵심 클래스: AppSettings (Singleton)
# =============================================================================

class AppSettings:
    """전역 설정 Singleton.

    애플리케이션 전체에서 하나의 인스턴스만 존재하는 중앙 설정 관리자.
    ConfigLoader로 YAML을 로드하고, ConfigValidator로 검증한 뒤,
    병합된 설정에 대한 읽기 전용 접근을 제공한다.

    스레드 안전:
        - Singleton 생성: Double-Checked Locking (RLock)
        - 설정 접근/리로드: 인스턴스 레벨 RLock
        - 모든 반환값은 방어적 복사

    사용 예시::

        # 초기화 (앱 시작 시 1회)
        settings = AppSettings.initialize(config_file="core_foundation/config.yaml")

        # 이후 어디서든 접근
        settings = AppSettings.get_instance()
        batch_size = settings.get("gpu.batch_size", 4)

        # 섹션 접근
        gpu_config = settings.get_section("gpu")
        # → {"batch_size": 4, "fp16": True, "device": "cuda:0", ...}

        # 리로드
        settings.reload()
    """

    # Singleton 관련
    _instance: ClassVar[AppSettings | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(
        self,
        *,
        config_file: str = DEFAULT_CONFIG_FILE,
        loader: ConfigLoader | None = None,
        validator: ConfigValidator | None = None,
        use_defaults: bool = True,
    ) -> None:
        """AppSettings 초기화.

        직접 호출보다는 initialize() 클래스메서드 사용 권장.

        Args:
            config_file: 메인 설정 파일 경로 (config_dir 기준)
            loader: 외부 ConfigLoader 주입. None이면 기본 생성.
            validator: 외부 ConfigValidator 주입. None이면 기본 생성.
            use_defaults: 기본값 병합 여부 (설정 파일 누락 시 폴백)
        """
        self._lock = threading.RLock()
        self._config_file = config_file
        self._use_defaults = use_defaults

        # 외부 주입 또는 기본 생성
        self._loader = loader or ConfigLoader()
        self._validator = validator or ConfigValidator()

        # 설정 상태
        self._data: dict[str, Any] = {}
        self._load_result: ConfigLoadResult | None = None
        self._validation_result: ValidationResult | None = None
        self._loaded: bool = False
        self._load_timestamp: float = 0.0

        # 스냅샷 이력
        self._snapshots: list[ConfigSnapshot] = []

        # 초기 로드
        self._initial_load()

    # =========================================================================
    # Singleton 관리
    # =========================================================================

    @classmethod
    def initialize(
        cls,
        *,
        config_file: str = DEFAULT_CONFIG_FILE,
        loader: ConfigLoader | None = None,
        validator: ConfigValidator | None = None,
        use_defaults: bool = True,
        force: bool = False,
    ) -> AppSettings:
        """Singleton 초기화.

        앱 시작 시 1회 호출. 이미 초기화된 경우 기존 인스턴스 반환.
        force=True면 기존 인스턴스를 파괴하고 재생성.

        Args:
            config_file: 메인 설정 파일 경로
            loader: 외부 ConfigLoader 주입
            validator: 외부 ConfigValidator 주입
            use_defaults: 기본값 병합 여부
            force: 강제 재초기화 여부

        Returns:
            AppSettings 인스턴스
        """
        # Double-Checked Locking
        if cls._instance is not None and not force:
            return cls._instance

        with cls._class_lock:
            if cls._instance is not None and not force:
                return cls._instance

            cls._instance = cls(
                config_file=config_file,
                loader=loader,
                validator=validator,
                use_defaults=use_defaults,
            )
            return cls._instance

    @classmethod
    def get_instance(cls) -> AppSettings:
        """Singleton 인스턴스 획득.

        initialize()가 먼저 호출되어야 한다.
        미초기화 시 기본값으로 자동 초기화.

        Returns:
            AppSettings 인스턴스
        """
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    # 기본 설정으로 자동 초기화
                    cls._instance = cls(use_defaults=True)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 인스턴스 해제.

        테스트 또는 앱 종료 시 사용.
        """
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 설정 접근 API
    # =========================================================================

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """점 구분자 키로 설정 값 접근.

        Args:
            dotted_key: 점 구분 키 (예: "gpu.batch_size")
            default: 키가 없을 때 반환할 기본값

        Returns:
            설정 값 (방어적 복사) 또는 기본값
        """
        with self._lock:
            value = self._get_nested(self._data, dotted_key)
            if value is _MISSING:
                return default
            # dict/list는 방어적 복사
            if isinstance(value, (dict, list)):
                return copy.deepcopy(value)
            return value

    def get_section(self, section: str) -> dict[str, Any]:
        """최상위 섹션 전체 조회.

        Args:
            section: 섹션 키 (예: "gpu", "camera", "system")

        Returns:
            섹션 딕셔너리 (방어적 복사). 없으면 빈 딕셔너리.
        """
        with self._lock:
            value = self._data.get(section, {})
            if isinstance(value, dict):
                return copy.deepcopy(value)
            return {}

    def get_all(self) -> dict[str, Any]:
        """전체 설정 조회.

        Returns:
            전체 설정 딕셔너리 (방어적 복사)
        """
        with self._lock:
            return copy.deepcopy(self._data)

    def has(self, dotted_key: str) -> bool:
        """설정 키 존재 여부 확인.

        Args:
            dotted_key: 점 구분 키

        Returns:
            키 존재 여부
        """
        with self._lock:
            return self._get_nested(self._data, dotted_key) is not _MISSING

    @property
    def is_loaded(self) -> bool:
        """설정 로드 완료 여부."""
        return self._loaded

    @property
    def environment(self) -> Environment:
        """현재 실행 환경."""
        return self._loader.environment

    @property
    def os_platform(self) -> OSPlatform:
        """현재 OS 플랫폼."""
        return self._loader.os_platform

    @property
    def load_timestamp(self) -> float:
        """마지막 로드 시각 (monotonic clock)."""
        return self._load_timestamp

    @property
    def config_file(self) -> str:
        """메인 설정 파일 경로."""
        return self._config_file

    @property
    def validation_result(self) -> ValidationResult | None:
        """마지막 검증 결과."""
        with self._lock:
            return self._validation_result

    # =========================================================================
    # 리로드 및 스냅샷
    # =========================================================================

    def reload(self) -> ConfigLoadResult:
        """설정 리로드.

        캐시를 무효화하고 설정 파일을 다시 로드한다.
        리로드 전 현재 상태를 스냅샷으로 저장한다.

        Returns:
            ConfigLoadResult: 리로드 결과

        Raises:
            ConfigurationLoadException: 로드 실패 시
        """
        with self._lock:
            # 리로드 전 스냅샷 저장
            self._save_snapshot()

            # 캐시 무효화
            self._loader.invalidate_cache()

            # 재로드
            return self._load_config()

    def take_snapshot(self) -> ConfigSnapshot:
        """현재 설정 상태 스냅샷 생성.

        Returns:
            ConfigSnapshot: 현재 상태 스냅샷
        """
        with self._lock:
            snapshot = ConfigSnapshot(
                data=copy.deepcopy(self._data),
                timestamp=time.monotonic(),
                load_result=self._load_result,
                validation_result=self._validation_result,
            )
            return snapshot

    @property
    def snapshot_count(self) -> int:
        """보관 중인 스냅샷 수."""
        with self._lock:
            return len(self._snapshots)

    @property
    def snapshots(self) -> list[ConfigSnapshot]:
        """스냅샷 이력 (방어적 복사)."""
        with self._lock:
            return list(self._snapshots)

    # =========================================================================
    # 검증
    # =========================================================================

    def validate(self) -> ValidationResult:
        """현재 설정을 검증기로 검증.

        Returns:
            ValidationResult: 검증 결과
        """
        with self._lock:
            result = self._validator.validate(self._data)
            self._validation_result = result
            return result

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """검증 규칙 추가.

        Args:
            rule: 추가할 검증 규칙
        """
        self._validator.add_rule(rule)

    def add_validation_rules(self, rules: list[ValidationRule]) -> None:
        """검증 규칙 일괄 추가.

        Args:
            rules: 추가할 규칙 목록
        """
        self._validator.add_rules(rules)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _initial_load(self) -> None:
        """초기 설정 로드. 파일 미발견 시 기본값 사용."""
        try:
            self._load_config()
        except (ConfigurationNotFoundException, ConfigurationLoadException):
            # 설정 파일 없음 → 기본값 사용
            if self._use_defaults:
                self._data = copy.deepcopy(_DEFAULT_CONFIG)
                self._loaded = True
                self._load_timestamp = time.monotonic()
            else:
                raise

    def _load_config(self) -> ConfigLoadResult:
        """설정 로드 실행.

        Returns:
            ConfigLoadResult: 로드 결과
        """
        load_result = self._loader.load(self._config_file)

        # 기본값 병합 (base에 기본값, 그 위에 로드된 설정 오버라이드)
        if self._use_defaults:
            merged = self._deep_merge_defaults(
                copy.deepcopy(_DEFAULT_CONFIG),
                load_result.data,
            )
        else:
            merged = load_result.data

        self._data = merged
        self._load_result = load_result
        self._loaded = True
        self._load_timestamp = time.monotonic()

        # 검증 규칙이 등록되어 있으면 자동 검증
        if self._validator.rule_count > 0:
            self._validation_result = self._validator.validate(self._data)

        return load_result

    def _save_snapshot(self) -> None:
        """현재 상태를 스냅샷 이력에 저장."""
        snapshot = ConfigSnapshot(
            data=copy.deepcopy(self._data),
            timestamp=time.monotonic(),
            load_result=self._load_result,
            validation_result=self._validation_result,
        )
        self._snapshots.append(snapshot)

        # 최대 수 초과 시 오래된 것부터 제거
        while len(self._snapshots) > MAX_SNAPSHOT_COUNT:
            self._snapshots.pop(0)

    @staticmethod
    def _deep_merge_defaults(
        defaults: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """기본값 위에 로드된 설정 병합.

        기본값에 있지만 로드된 설정에 없는 키는 보존.
        로드된 설정의 값이 기본값을 덮어쓴다.

        Args:
            defaults: 기본값 딕셔너리
            override: 로드된 설정 딕셔너리

        Returns:
            병합된 딕셔너리
        """
        result = copy.deepcopy(defaults)

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = AppSettings._deep_merge_defaults(
                    result[key], value,
                )
            else:
                result[key] = copy.deepcopy(value)

        return result

    @staticmethod
    def _get_nested(data: dict[str, Any], dotted_key: str) -> Any:
        """점 구분자 키로 중첩 값 접근.

        Args:
            data: 대상 딕셔너리
            dotted_key: 점 구분 키

        Returns:
            값 또는 _MISSING (키 없음)
        """
        keys = dotted_key.split(".")
        current: Any = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return _MISSING
        return current

    def __repr__(self) -> str:
        valid_str = "N/A"
        if self._validation_result is not None:
            valid_str = str(self._validation_result.is_valid)
        return (
            f"AppSettings("
            f"loaded={self._loaded}, "
            f"env={self._loader.environment.value}, "
            f"keys={len(self._data)}, "
            f"valid={valid_str})"
        )


# =============================================================================
# 내부 센티넬
# =============================================================================

class _MissingSentinel:
    """딕셔너리에 키가 없음을 나타내는 센티넬."""

    _instance: ClassVar[_MissingSentinel | None] = None

    def __new__(cls) -> _MissingSentinel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<MISSING>"

    def __bool__(self) -> bool:
        return False


_MISSING = _MissingSentinel()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 상수
    "DEFAULT_CONFIG_FILE",
    "MAX_SNAPSHOT_COUNT",
    # 데이터 클래스
    "ConfigSnapshot",
    # 핵심 클래스
    "AppSettings",
]

__version__ = "1.0.0"
