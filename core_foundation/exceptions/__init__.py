"""
exceptions - 구조화된 예외 계층

COURTVIEW Desktop 전용 예외 클래스 (하드웨어, 검증, 설정 등)
"""

from core_foundation.exceptions.base import CourtViewError
from core_foundation.exceptions.hardware import (
    GPUError,
    CameraError,
    InsufficientMemoryError,
)
from core_foundation.exceptions.validation import (
    ConfigError,
    DataValidationError,
)

__all__ = [
    "CourtViewError",
    "GPUError",
    "CameraError",
    "InsufficientMemoryError",
    "ConfigError",
    "DataValidationError",
]
