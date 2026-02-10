"""
core_foundation/config/settings.py - 전역 설정 객체 (Singleton)

COURTVIEW Desktop 전역 설정 관리
- Singleton 패턴 (Thread-Safe)
- 환경별 설정 로드 (dev/prod/test)
- Loader + Validator 통합
- 타입 안전한 설정 접근
- 설정 리로드 기능

Author: COURTVIEW Team
Version: 1.0.0
"""

import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import ValidationError

from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    DesktopConfigValidator,
)
from core_foundation.exceptions.validation import ConfigError, DataValidationError


class DesktopSettings:
    """
    COURTVIEW Desktop 전역 설정 (Singleton)

    싱글톤 패턴으로 구현되어 앱 전체에서 단일 인스턴스만 존재합니다.
    환경별 설정 자동 로드 (dev/prod/test)

    Features:
    - Thread-Safe: 멀티스레드 환경에서 안전
    - Lazy Loading: 첫 접근 시 초기화
    - 환경 기반: ENV 환경 변수로 dev/prod 구분
    - 타입 안전: Pydantic 기반 타입 힌팅
    - 불변성: 초기화 후 설정 변경 금지 (reload()만 가능)

    Attributes:
        app: 앱 전역 설정 (AppConfig)
        gpu: GPU 설정 (GPUConfig)
        camera: 카메라 설정 (CameraConfig)
        detection: 검출 설정 (DetectionConfig)
        environment: 현재 환경 (dev/prod/test)

    Examples:
        >>> from core_foundation.config.settings import settings
        >>> print(settings.gpu.device_id)
        0
        >>> print(settings.app.name)
        "COURTVIEW Desktop"
        >>> settings.reload()  # 설정 재로드
    """

    _instance: Optional['DesktopSettings'] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """
        싱글톤 인스턴스 생성 (Thread-Safe)

        Double-checked locking 패턴 사용

        Returns:
            DesktopSettings: 싱글톤 인스턴스
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        env_file: Optional[Path] = None,
        environment: Optional[str] = None,
        reload: bool = False
    ):
        """
        초기화 (한 번만 실행)

        Args:
            config_dir: 설정 디렉토리 (기본: ./configs)
            env_file: 환경 변수 파일 (기본: .env)
            environment: 환경 (dev/prod/test, 기본: ENV 환경 변수)
            reload: 강제 재로드 (기본: False)

        Examples:
            >>> # 기본 초기화 (싱글톤)
            >>> settings = DesktopSettings()
            >>>
            >>> # 커스텀 설정 (테스트용)
            >>> test_settings = DesktopSettings(
            ...     config_dir=Path("./tests/fixtures"),
            ...     environment="test",
            ...     reload=True
            ... )
        """
        if self._initialized and not reload:
            return  # 이미 초기화됨

        with self._lock:
            if not self._initialized or reload:
                # 설정 디렉토리 및 파일
                self._config_dir = config_dir or Path("./configs")
                self._env_file = env_file or Path(".env")
                self._environment = environment or os.getenv("ENV", "dev")
                self._frozen = False

                # Loader 초기화
                self._loader = ConfigLoader(
                    config_dir=self._config_dir,
                    env_file=self._env_file
                )

                # 설정 로드
                self._load_settings()
                self._initialized = True

    def _load_settings(self) -> None:
        """
        설정 파일 로드 및 검증

        플로우:
        1. base 설정 로드 (configs/base.yaml)
        2. 환경별 설정 로드 (configs/env_{environment}.yaml)
        3. 환경 변수 오버라이드 (.env)
        4. 병합 (base + env + ENV)
        5. 검증 (Pydantic Validator)
        6. 타입 안전 객체 생성

        Raises:
            ConfigError: 설정 파일 로드 실패
            DataValidationError: 검증 실패
        """
        # Step 1: Base 설정 로드
        try:
            base_config = self._loader.load_yaml("base.yaml")
        except ConfigError as e:
            # base.yaml이 없으면 기본값 사용
            base_config = {}

        # Step 2: 환경별 설정 로드
        env_config_file = f"env_{self._environment}.yaml"
        env_config = {}
        try:
            env_config = self._loader.load_yaml(env_config_file)
        except ConfigError:
            # 환경별 설정 파일 없으면 무시 (선택적)
            pass

        # Step 3: 병합 (base + env + ENV 변수)
        merged_config = self._loader.merge_configs(
            base_config,
            env_config,
            env_override=True  # .env 파일 자동 로드
        )

        # Step 4: 검증 및 타입 안전 객체 생성
        validated = DesktopConfigValidator(**merged_config)
        validated.validate_all()

        # Step 5: 속성 설정
        self.app = validated.app
        self.gpu = validated.gpu
        self.camera = validated.camera
        self.detection = validated.detection
        self.environment = self._environment

        # 설정 동결 (불변성 보장)
        self._frozen = True

    def reload(self) -> None:
        """
        설정 재로드

        런타임에 설정 파일이 변경되었을 때 재로드합니다.
        주의: 스레드 안전하지만, 재로드 중 다른 스레드의 설정 접근은 블로킹됩니다.

        Examples:
            >>> settings.reload()
            >>> print(settings.gpu.batch_size)  # 변경된 값
        """
        with self._lock:
            self._frozen = False
            self._load_settings()

    def get_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        설정을 딕셔너리로 반환

        Args:
            include_sensitive: 민감 정보 포함 여부 (기본: False)
                               현재는 민감 정보 없음 (향후 API 키 등 추가 시 사용)

        Returns:
            Dict[str, Any]: 전체 설정 딕셔너리

        Examples:
            >>> config_dict = settings.get_dict()
            >>> print(config_dict["gpu"]["device_id"])
            0
            >>> print(config_dict["app"]["name"])
            "COURTVIEW Desktop"
        """
        config_dict = {
            "app": self.app.model_dump(),
            "gpu": self.gpu.model_dump(),
            "camera": self.camera.model_dump(),
            "detection": self.detection.model_dump(),
            "environment": self.environment,
        }

        if not include_sensitive:
            # 민감 정보 마스킹 (현재는 없지만, 향후 추가 시 사용)
            # 예: API 키, 비밀번호 등
            pass

        return config_dict

    def __setattr__(self, name: str, value: Any) -> None:
        """
        속성 설정 제어 (불변성 보장)

        _frozen=True이면 설정 변경 불가 (reload()만 가능)

        Args:
            name: 속성 이름
            value: 속성 값

        Raises:
            AttributeError: 설정 동결 후 변경 시도

        Examples:
            >>> settings.gpu.device_id = 999  # ❌ AttributeError
            >>> settings.reload()             # ✅ 리로드로만 변경 가능
        """
        # 내부 속성 및 초기화 중에는 변경 허용
        if name.startswith('_') or name in ('app', 'gpu', 'camera', 'detection', 'environment'):
            super().__setattr__(name, value)
            return

        # 설정 동결 후 변경 시도
        if hasattr(self, '_frozen') and self._frozen:
            raise AttributeError(
                f"설정이 동결되어 있습니다. "
                f"설정을 변경하려면 reload()를 사용하세요."
            )

        super().__setattr__(name, value)

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"DesktopSettings("
            f"environment={self.environment}, "
            f"app={self.app.name}, "
            f"gpu_id={self.gpu.device_id}, "
            f"cameras={self.camera.min_count}~{self.camera.max_count})"
        )


# ==================== 전역 싱글톤 인스턴스 ====================
"""
전역 설정 인스턴스

앱 전체에서 이 인스턴스를 import하여 사용합니다.
싱글톤 패턴으로 단일 인스턴스만 존재합니다.

Examples:
    >>> from core_foundation.config.settings import settings
    >>>
    >>> # 설정 접근
    >>> print(settings.gpu.device_id)
    >>> print(settings.app.name)
    >>>
    >>> # 설정 리로드
    >>> settings.reload()
    >>>
    >>> # 딕셔너리 변환
    >>> config_dict = settings.get_dict()
"""

# 전역 settings 인스턴스 (Lazy Loading)
# 설정 파일이 없으면 None (테스트 시 명시적 초기화 필요)
settings: Optional[DesktopSettings] = None

try:
    # 설정 파일이 있으면 자동 초기화
    settings = DesktopSettings()
except (ConfigError, DataValidationError, ValidationError):
    # 설정 파일이 없거나 검증 실패 시 None (수동 초기화 필요)
    settings = None


# ==================== __all__ Export ====================
__all__ = [
    "DesktopSettings",
    "settings",
]
