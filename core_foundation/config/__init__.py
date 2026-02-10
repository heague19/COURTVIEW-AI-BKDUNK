"""
config - 설정 관리 모듈

YAML/ENV 파일 로더, Pydantic 기반 검증, 전역 설정 객체(Singleton)
"""

from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    # Enum
    GPUBackend,
    LogLevel,
    # 검증 클래스
    ConfigValidator,
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    AppConfig,
    DesktopConfigValidator,
    # 유틸리티
    validate_config_dict,
    validate_config_file,
)
from core_foundation.config.settings import DesktopSettings, settings

__all__ = [
    # Loader
    "ConfigLoader",
    # Enum
    "GPUBackend",
    "LogLevel",
    # 검증 클래스
    "ConfigValidator",
    "GPUConfig",
    "CameraConfig",
    "DetectionConfig",
    "AppConfig",
    "DesktopConfigValidator",
    # 유틸리티
    "validate_config_dict",
    "validate_config_file",
    # Settings
    "DesktopSettings",
    "settings",
]
