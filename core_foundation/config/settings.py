# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: core_foundation/config
파일: settings.py
설명: 전역 설정 관리 (Singleton) - 타입 안전한 설정 접근 레이어

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - ConfigLoader(YAML 로드) + SchemaValidator(검증)를 결합한 상위 레이어
    - Singleton 패턴으로 애플리케이션 전역에서 동일한 설정 접근
    - Pydantic 모델 기반 타입 안전한 프로퍼티 접근
    - Desktop 전용 편의 메서드 (GPU, 카메라, 스토리지 상태 확인)
    - 프로파일 기반 설정 자동 로드 (development, production, testing)
    - 설정 변경 시 자동 갱신 (HotReloadManager 연동)
    - 설정 스냅샷 및 비교 기능

사용 예시:
    # 초기화 (앱 시작 시 1회)
    settings = Settings.initialize("config/app.yaml")

    # 전역 접근 (어디서든)
    settings = Settings.get_instance()
    gpu = settings.gpu
    print(f"GPU: {gpu.cuda_device}, 메모리: {gpu.memory_fraction * 100}%")

    # 편의 메서드
    if settings.is_gpu_available:
        print(f"TensorRT: {settings.gpu.tensorrt_enabled}")

    # dot notation 접근
    fps = settings.get("analysis.target_fps", 30)
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import logging
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Callable,
    Type,
    TypeVar,
)

# =============================================================================
# 프로젝트 모듈 (core_foundation)
# =============================================================================
from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    LocalDatabaseConfig,
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    SchemaValidator,
    ValidationResult,
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
# Enum 정의
# =============================================================================
class SettingsState(Enum):
    """
    설정 상태.

    Settings 인스턴스의 현재 상태를 나타냅니다.
    """

    UNINITIALIZED = auto()  # 초기화 전
    LOADING = auto()        # 로딩 중
    READY = auto()          # 사용 가능
    ERROR = auto()          # 오류 상태
    RELOADING = auto()      # 리로딩 중


class Environment(Enum):
    """
    실행 환경.

    Desktop 앱의 실행 환경을 나타냅니다.
    """

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass
class SettingsMetadata:
    """
    설정 메타데이터.

    설정 로드/갱신 이력을 추적합니다.

    Attributes:
        config_path: 로드된 설정 파일 경로
        loaded_at: 최초 로드 시각
        last_reloaded_at: 마지막 갱신 시각
        reload_count: 갱신 횟수
        environment: 실행 환경
        validation_passed: 검증 통과 여부
        config_version: 설정 버전
    """

    config_path: str | None = None
    loaded_at: datetime | None = None
    last_reloaded_at: datetime | None = None
    reload_count: int = 0
    environment: str = "production"
    validation_passed: bool = False
    config_version: str = "1.0.0"

    def mark_loaded(self, config_path: str, environment: str) -> None:
        """로드 완료 표시."""
        now = datetime.now(timezone.utc)
        self.config_path = config_path
        self.loaded_at = now
        self.last_reloaded_at = now
        self.environment = environment
        self.validation_passed = True

    def mark_reloaded(self) -> None:
        """갱신 완료 표시."""
        self.last_reloaded_at = datetime.now(timezone.utc)
        self.reload_count += 1

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "config_path": self.config_path,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "last_reloaded_at": (
                self.last_reloaded_at.isoformat() if self.last_reloaded_at else None
            ),
            "reload_count": self.reload_count,
            "environment": self.environment,
            "validation_passed": self.validation_passed,
            "config_version": self.config_version,
        }


# =============================================================================
# Settings 클래스
# =============================================================================
class Settings:
    """
    전역 설정 관리자 (Singleton).

    ConfigLoader(YAML 로드)와 SchemaValidator(Pydantic 검증)를 결합하여
    애플리케이션 전역에서 타입 안전하게 설정에 접근할 수 있게 합니다.

    구조:
        loader.py  →  YAML/JSON → Dict (범용 로더)
        validator.py → Dict → AppConfig (Pydantic 검증)
        settings.py → AppConfig → 전역 접근 (Singleton 래퍼)  ← 현재 파일

    주요 기능:
        - Singleton 패턴으로 전역 접근
        - Pydantic AppConfig 기반 타입 안전한 프로퍼티
        - Desktop 전용 편의 메서드 (GPU/카메라/스토리지 확인)
        - 프로파일 기반 설정 자동 로드
        - 설정 변경 시 자동 갱신 콜백
        - 스레드 안전

    Example:
        >>> # 앱 시작 시 1회 초기화
        >>> settings = Settings.initialize("config/app.yaml")
        >>>
        >>> # 이후 어디서든 접근
        >>> settings = Settings.get_instance()
        >>> print(settings.gpu.cuda_device)         # "cuda:0"
        >>> print(settings.camera.count)             # 4
        >>> print(settings.analysis.target_fps)      # 30
        >>> print(settings.is_gpu_available)          # True
    """

    # 싱글톤 인스턴스
    _instance: "Settings" | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "Settings":
        """싱글톤 인스턴스 생성."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """초기화."""
        if getattr(self, "_initialized", False):
            return

        # 상태
        self._state: SettingsState = SettingsState.UNINITIALIZED
        self._state_lock = threading.RLock()

        # 설정 데이터
        self._config: AppConfig | None = None
        self._raw_config: dict[str, Any] = {}
        self._config_lock = threading.RLock()

        # 컴포넌트
        self._loader: ConfigLoader = ConfigLoader.get_instance()
        self._validator: SchemaValidator = SchemaValidator()

        # 메타데이터
        self._metadata: SettingsMetadata = SettingsMetadata()

        # 변경 리스너
        self._change_listeners: list[Callable[[AppConfig, AppConfig], None]] = []
        self._listeners_lock = threading.Lock()

        # 설정 스냅샷 (이전 설정 보관)
        self._previous_config: AppConfig | None = None

        # 초기화 완료
        self._initialized = True

        logger.debug("Settings 인스턴스 생성됨 (미로드 상태)")

    # --------------------------------------------------------
    # 클래스 메서드 (초기화/접근)
    # --------------------------------------------------------
    @classmethod
    def get_instance(cls) -> "Settings":
        """
        싱글톤 인스턴스 반환.

        Returns:
            Settings 인스턴스

        Note:
            initialize()를 먼저 호출해야 설정이 로드됩니다.
            초기화 전에도 인스턴스는 반환되지만, config 접근 시
            기본값(AppConfig 기본 생성자)이 사용됩니다.
        """
        return cls()

    @classmethod
    def initialize(
        cls,
        config_path: str | Path = "config/app.yaml",
        config_dir: str | Path | None = None,
        validate: bool = True,
    ) -> "Settings":
        """
        설정 초기화 (앱 시작 시 1회 호출).

        프로파일 기반 로딩:
        1. config/app.yaml (기본 설정)
        2. config/app.{profile}.yaml (프로파일 설정)
        3. config/app.local.yaml (로컬 오버라이드, 선택적)

        Args:
            config_path: 기본 설정 파일 경로
            config_dir: 설정 디렉토리 (None이면 config_path의 부모)
            validate: Pydantic 스키마 검증 수행 여부

        Returns:
            초기화된 Settings 인스턴스

        Raises:
            ConfigurationException: 설정 로드 또는 검증 실패 시
        """
        instance = cls()
        instance._load_config(config_path, config_dir, validate)
        return instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        싱글톤 인스턴스 초기화 (테스트용).

        주의: 프로덕션 환경에서는 사용하지 마세요.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._state = SettingsState.UNINITIALIZED
                cls._instance._config = None
                cls._instance._raw_config = {}
                cls._instance._previous_config = None
                cls._instance._metadata = SettingsMetadata()
            cls._instance = None

        # ConfigLoader도 리셋
        ConfigLoader.reset_instance()

    # --------------------------------------------------------
    # 설정 로드 메서드
    # --------------------------------------------------------
    def _load_config(
        self,
        config_path: str | Path,
        config_dir: str | Path | None,
        validate: bool,
    ) -> None:
        """설정 로드 내부 메서드."""
        with self._state_lock:
            self._state = SettingsState.LOADING

        try:
            path = Path(config_path)

            # 설정 디렉토리 결정
            if config_dir:
                base_dir = Path(config_dir)
            else:
                base_dir = path.parent

            # 설정 파일이 존재하면 프로파일 기반 로드
            if path.exists():
                base_name = path.stem  # "app" from "app.yaml"
                self._loader.load_with_profile(
                    base_name=base_name,
                    config_dir=str(base_dir),
                )
            else:
                # 설정 파일 없으면 기본값 사용
                logger.warning(f"설정 파일 없음, 기본값 사용: {config_path}")

            # 로드된 딕셔너리 가져오기
            self._raw_config = self._loader.to_dict()

            # Pydantic 검증 및 AppConfig 생성
            if validate and self._raw_config:
                validation_result = self._validator.validate(
                    self._raw_config, AppConfig
                )

                if validation_result.is_valid:
                    self._config = validation_result.data
                else:
                    # 검증 실패 시 경고 후 기본값 사용
                    error_msgs = [e.message for e in validation_result.errors[:5]]
                    logger.warning(
                        f"설정 검증 실패, 기본값 사용: {'; '.join(error_msgs)}"
                    )
                    self._config = AppConfig()
            else:
                # 검증 건너뛰기 또는 빈 설정 → 기본값
                if self._raw_config:
                    try:
                        self._config = AppConfig.model_validate(self._raw_config)
                    except Exception as e:
                        logger.warning(
                            f"설정 검증 실패 (model_validate), 기본값 사용: {e}"
                        )
                        self._config = AppConfig()
                else:
                    self._config = AppConfig()

            # 메타데이터 업데이트
            self._metadata.mark_loaded(
                config_path=str(config_path),
                environment=self._config.environment,
            )

            with self._state_lock:
                self._state = SettingsState.READY

            logger.info(
                f"설정 로드 완료: {config_path} "
                f"(환경: {self._config.environment}, "
                f"GPU: {self._config.gpu.cuda_device}, "
                f"카메라: {self._config.camera.count}대)"
            )

        except Exception as e:
            with self._state_lock:
                self._state = SettingsState.ERROR

            # 오류 시에도 기본값으로 동작 가능하도록
            if self._config is None:
                self._config = AppConfig()

            logger.error(f"설정 로드 실패: {e}")
            raise

    def reload(self, config_path: str | Path | None = None) -> bool:
        """
        설정 재로드.

        Args:
            config_path: 재로드할 설정 파일 (None이면 원래 경로 사용)

        Returns:
            재로드 성공 여부
        """
        path = config_path or self._metadata.config_path
        if not path:
            logger.warning("재로드할 설정 경로가 없습니다")
            return False

        with self._state_lock:
            self._state = SettingsState.RELOADING

        try:
            # 이전 설정 보관
            self._previous_config = deepcopy(self._config)

            # 재로드
            self._load_config(Path(path), config_dir=None, validate=True)
            self._metadata.mark_reloaded()

            # 변경 리스너 호출
            if self._previous_config and self._config:
                self._notify_change_listeners(self._previous_config, self._config)

            logger.info(f"설정 재로드 완료: {path}")
            return True

        except Exception as e:
            # 실패 시 이전 설정 복원
            if self._previous_config:
                self._config = self._previous_config
                logger.warning(f"설정 재로드 실패, 이전 설정 복원: {e}")

            with self._state_lock:
                self._state = SettingsState.READY

            return False

    # --------------------------------------------------------
    # 설정 접근 프로퍼티 (타입 안전)
    # --------------------------------------------------------
    @property
    def config(self) -> AppConfig:
        """전체 AppConfig 반환."""
        with self._config_lock:
            if self._config is None:
                self._config = AppConfig()
            return self._config

    @property
    def gpu(self) -> GPUConfig:
        """GPU 설정."""
        return self.config.gpu

    @property
    def camera(self) -> CameraConfig:
        """카메라 설정."""
        return self.config.camera

    @property
    def storage(self) -> LocalStorageConfig:
        """로컬 스토리지 설정."""
        return self.config.storage

    @property
    def database(self) -> LocalDatabaseConfig:
        """로컬 데이터베이스 설정."""
        return self.config.database

    @property
    def model(self) -> ModelConfig:
        """AI 모델 설정."""
        return self.config.model

    @property
    def analysis(self) -> AnalysisConfig:
        """분석 파이프라인 설정."""
        return self.config.analysis

    @property
    def logging_config(self) -> LoggingConfig:
        """로깅 설정 (logging과 이름 충돌 방지)."""
        return self.config.logging

    # --------------------------------------------------------
    # 상태 프로퍼티
    # --------------------------------------------------------
    @property
    def state(self) -> SettingsState:
        """현재 상태."""
        with self._state_lock:
            return self._state

    @property
    def is_ready(self) -> bool:
        """설정 사용 가능 여부."""
        return self.state == SettingsState.READY

    @property
    def environment(self) -> Environment:
        """실행 환경."""
        env_str = self.config.environment
        try:
            return Environment(env_str)
        except ValueError:
            return Environment.PRODUCTION

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """개발 환경 여부."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """테스트 환경 여부."""
        return self.environment == Environment.TESTING

    @property
    def metadata(self) -> SettingsMetadata:
        """메타데이터."""
        return self._metadata

    # --------------------------------------------------------
    # Desktop 전용 편의 프로퍼티
    # --------------------------------------------------------
    @property
    def is_gpu_available(self) -> bool:
        """
        GPU 사용 가능 여부.

        CUDA 디바이스가 설정되어 있고 CPU 폴백이 아닌 경우 True.
        실제 하드웨어 확인은 하지 않음 (설정 기준).
        """
        return self.model.device != "cpu"

    @property
    def is_tensorrt_enabled(self) -> bool:
        """TensorRT 활성화 여부."""
        return self.gpu.tensorrt_enabled and self.is_gpu_available

    @property
    def is_multi_camera(self) -> bool:
        """멀티 카메라 모드 여부."""
        return self.camera.count > 1

    @property
    def cuda_device(self) -> str:
        """CUDA 디바이스 문자열 (gpu.cuda_device 바로가기)."""
        return self.gpu.cuda_device

    @property
    def target_fps(self) -> int:
        """분석 대상 FPS (analysis.target_fps 바로가기)."""
        return self.analysis.target_fps

    @property
    def camera_count(self) -> int:
        """카메라 수 (camera.count 바로가기)."""
        return self.camera.count

    # --------------------------------------------------------
    # 범용 접근 메서드
    # --------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """
        dot notation으로 설정 접근.

        ConfigLoader의 원시 값에 접근합니다.
        타입 안전한 접근이 필요하면 프로퍼티를 사용하세요.

        Args:
            key: 설정 키 (예: "gpu.device_id", "analysis.target_fps")
            default: 기본값

        Returns:
            설정 값 또는 기본값

        Example:
            >>> settings.get("gpu.precision", "fp16")
            "fp16"
        """
        return self._loader.get(key, default)

    def get_typed(self, key: str, default: T = None, value_type: Type[T] = None) -> T:
        """
        타입 변환 포함 설정 접근.

        Args:
            key: 설정 키
            default: 기본값
            value_type: 반환 타입

        Returns:
            타입 변환된 설정 값
        """
        return self._loader.get(key, default, value_type)

    def has(self, key: str) -> bool:
        """설정 키 존재 여부."""
        return self._loader.has(key)

    def to_dict(self) -> dict[str, Any]:
        """전체 설정을 딕셔너리로 반환."""
        return self.config.model_dump()

    # --------------------------------------------------------
    # 변경 리스너
    # --------------------------------------------------------
    def on_change(
        self, listener: Callable[[AppConfig, AppConfig], None]
    ) -> None:
        """
        설정 변경 리스너 등록.

        재로드 시 이전/새 설정을 전달받습니다.

        Args:
            listener: 콜백 함수 (old_config, new_config)

        Example:
            >>> def on_settings_change(old, new):
            ...     if old.gpu.precision != new.gpu.precision:
            ...         print("GPU 정밀도 변경됨")
            >>> settings.on_change(on_settings_change)
        """
        with self._listeners_lock:
            if listener not in self._change_listeners:
                self._change_listeners.append(listener)

    def off_change(
        self, listener: Callable[[AppConfig, AppConfig], None]
    ) -> None:
        """설정 변경 리스너 해제."""
        with self._listeners_lock:
            if listener in self._change_listeners:
                self._change_listeners.remove(listener)

    def _notify_change_listeners(
        self, old_config: AppConfig, new_config: AppConfig
    ) -> None:
        """변경 리스너 호출."""
        with self._listeners_lock:
            listeners = self._change_listeners.copy()

        for listener in listeners:
            try:
                listener(old_config, new_config)
            except Exception as e:
                listener_name = getattr(listener, "__name__", repr(listener))
                logger.error(f"설정 변경 리스너 오류: {listener_name}, {e}")

    # --------------------------------------------------------
    # 스냅샷/비교
    # --------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """
        현재 설정 스냅샷 반환.

        Returns:
            현재 설정의 딥 카피 딕셔너리
        """
        return deepcopy(self.to_dict())

    def diff(self, other: dict[str, Any]) -> dict[str, Any]:
        """
        현재 설정과 다른 딕셔너리의 차이점 반환.

        Args:
            other: 비교 대상 딕셔너리

        Returns:
            변경된 항목 {key: {"old": 값, "new": 값}}
        """
        current = self.to_dict()
        return self._find_diff(current, other)

    def _find_diff(
        self,
        dict_a: dict[str, Any],
        dict_b: dict[str, Any],
        prefix: str = "",
    ) -> dict[str, Any]:
        """재귀적 차이점 탐색."""
        diff = {}
        all_keys = set(dict_a.keys()) | set(dict_b.keys())

        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            val_a = dict_a.get(key)
            val_b = dict_b.get(key)

            if val_a != val_b:
                if isinstance(val_a, dict) and isinstance(val_b, dict):
                    nested = self._find_diff(val_a, val_b, full_key)
                    diff.update(nested)
                else:
                    diff[full_key] = {"old": val_a, "new": val_b}

        return diff

    # --------------------------------------------------------
    # 상태 정보
    # --------------------------------------------------------
    def get_status(self) -> dict[str, Any]:
        """
        현재 상태 정보 반환.

        Returns:
            상태 정보 딕셔너리
        """
        return {
            "state": self.state.name,
            "is_ready": self.is_ready,
            "environment": self.config.environment,
            "is_gpu_available": self.is_gpu_available,
            "is_tensorrt_enabled": self.is_tensorrt_enabled,
            "is_multi_camera": self.is_multi_camera,
            "gpu_device": self.cuda_device,
            "camera_count": self.camera_count,
            "target_fps": self.target_fps,
            "model_type": self.model.model_type,
            "model_precision": self.model.precision,
            "db_path": self.database.db_path,
            "storage_cache_dir": self.storage.cache_dir,
            "listeners_count": len(self._change_listeners),
            "metadata": self._metadata.to_dict(),
        }

    def __repr__(self) -> str:
        """문자열 표현."""
        return (
            f"Settings(state={self.state.name}, "
            f"env={self.config.environment}, "
            f"gpu={self.cuda_device}, "
            f"cameras={self.camera_count})"
        )


# =============================================================================
# 헬퍼 함수
# =============================================================================
def get_settings() -> Settings:
    """
    전역 Settings 인스턴스 반환 (바로가기).

    Returns:
        Settings 인스턴스

    Example:
        >>> from core_foundation.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.gpu.cuda_device)
    """
    return Settings.get_instance()


def initialize_settings(
    config_path: str | Path = "config/app.yaml",
    validate: bool = True,
) -> Settings:
    """
    설정 초기화 헬퍼 함수.

    Args:
        config_path: 설정 파일 경로
        validate: 스키마 검증 수행 여부

    Returns:
        초기화된 Settings 인스턴스

    Example:
        >>> settings = initialize_settings("config/app.yaml")
        >>> print(settings.is_ready)
        True
    """
    return Settings.initialize(config_path=config_path, validate=validate)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "SettingsState",
    "Environment",
    # 데이터 클래스
    "SettingsMetadata",
    # 메인 클래스
    "Settings",
    # 함수
    "get_settings",
    "initialize_settings",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
