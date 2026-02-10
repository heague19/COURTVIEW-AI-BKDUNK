"""
core_foundation/config/validator.py - Pydantic 기반 설정 검증

COURTVIEW Desktop 설정값 타입/범위/형식 검증
- Pydantic V2 (Rust 기반 성능)
- 자동 타입 변환
- 커스텀 검증 로직
- 한글 에러 메시지

Author: COURTVIEW Team
Version: 1.0.0
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union
import re
import warnings

from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError

from core_foundation.exceptions.validation import DataValidationError, ConfigError


# ==================== 타입 변수 ====================
T = TypeVar('T', bound='ConfigValidator')


# ==================== Enum 정의 ====================
class GPUBackend(str, Enum):
    """GPU 백엔드 타입"""
    CUDA = "cuda"
    METAL = "metal"
    CPU = "cpu"


class LogLevel(str, Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ==================== 추상 기본 클래스 ====================
class ConfigValidator(BaseModel, ABC):
    """
    설정 검증 기본 클래스

    모든 설정 검증 클래스는 이 클래스를 상속합니다.
    Pydantic BaseModel의 자동 검증 + 커스텀 검증 메서드 제공

    Features:
    - 자동 타입 변환 (strict=False)
    - 할당 시 검증 (validate_assignment=True)
    - 정의되지 않은 필드 금지 (extra='forbid')
    - 수정 가능 (frozen=False)

    Examples:
        >>> class MyConfig(ConfigValidator):
        ...     field: int = Field(ge=0, le=100)
        ...     def validate_custom(self):
        ...         if self.field > 50:
        ...             warnings.warn("필드 값이 큽니다")
        >>> config = MyConfig(field=30)
        >>> config.validate_custom()
    """

    model_config = ConfigDict(
        strict=False,               # 자동 타입 변환 허용 ("123" → 123)
        validate_assignment=True,   # 할당 시에도 검증
        extra='forbid',             # 정의되지 않은 필드 금지 (오타 방지)
        frozen=False                # 수정 가능 (설정 동적 변경)
    )

    @abstractmethod
    def validate_custom(self) -> None:
        """
        커스텀 검증 로직 (서브클래스에서 구현)

        Pydantic의 기본 검증 후 실행되는 추가 검증 로직입니다.
        복잡한 비즈니스 규칙이나 멀티 필드 의존성을 검증합니다.

        Raises:
            ValueError: 검증 실패 시

        Examples:
            >>> def validate_custom(self):
            ...     if self.memory_fraction < 0.5 and self.batch_size > 16:
            ...         raise ValueError("메모리가 부족합니다")
        """
        pass


# ==================== GPU 설정 검증 ====================
class GPUConfig(ConfigValidator):
    """
    GPU 설정 검증

    검증 항목:
    - device_id: 0~7 범위 (일반적인 GPU 개수)
    - memory_fraction: 0.1~1.0 (10%~100%)
    - backend: cuda/metal/cpu
    - batch_size: 1~128
    - enable_fp16: FP16 혼합 정밀도 사용 여부

    Examples:
        >>> gpu_config = GPUConfig(
        ...     device_id=0,
        ...     memory_fraction=0.8,
        ...     backend="cuda",
        ...     batch_size=8
        ... )
        >>> gpu_config.validate_custom()
    """

    device_id: int = Field(
        default=0,
        ge=0,
        le=7,
        description="GPU 장치 ID (0~7)"
    )

    memory_fraction: float = Field(
        default=0.8,
        ge=0.1,
        le=1.0,
        description="GPU 메모리 사용 비율 (0.1~1.0)"
    )

    backend: GPUBackend = Field(
        default=GPUBackend.CUDA,
        description="GPU 백엔드 (cuda/metal/cpu)"
    )

    batch_size: int = Field(
        default=8,
        ge=1,
        le=128,
        description="배치 크기 (1~128)"
    )

    enable_fp16: bool = Field(
        default=False,
        description="FP16 혼합 정밀도 사용"
    )

    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v: int) -> int:
        """GPU ID 검증"""
        if v < 0 or v > 7:
            raise ValueError(f"GPU device_id는 0~7 범위여야 합니다 (입력값: {v})")
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """배치 크기 검증 (2의 거듭제곱 권장)"""
        if v > 0 and (v & (v - 1)) != 0:
            warnings.warn(
                f"batch_size={v}는 2의 거듭제곱이 아닙니다. "
                f"성능 최적화를 위해 2/4/8/16/32/64 권장",
                UserWarning
            )
        return v

    def validate_custom(self) -> None:
        """GPU 메모리와 배치 크기 간 일관성 검증"""
        # 메모리가 부족하면 배치 크기 줄여야 함
        if self.memory_fraction < 0.5 and self.batch_size > 16:
            raise ValueError(
                f"GPU 메모리 비율({self.memory_fraction})이 낮으면 "
                f"배치 크기({self.batch_size})를 줄여야 합니다 (권장: ≤16)"
            )


# ==================== 카메라 설정 검증 ====================
class CameraConfig(ConfigValidator):
    """
    카메라 설정 검증

    검증 항목:
    - min_count: 최소 카메라 대수 (4대 이상 권장)
    - max_count: 최대 카메라 대수
    - resolution: 해상도 (width x height)
    - fps: 프레임 레이트 (1~240)
    - auto_exposure: 자동 노출 활성화

    Examples:
        >>> camera_config = CameraConfig(
        ...     min_count=4,
        ...     max_count=8,
        ...     resolution={"width": 1920, "height": 1080},
        ...     fps=30
        ... )
        >>> camera_config.validate_custom()
    """

    min_count: int = Field(
        default=4,
        ge=1,
        le=32,
        description="최소 카메라 대수"
    )

    max_count: int = Field(
        default=8,
        ge=1,
        le=32,
        description="최대 카메라 대수"
    )

    resolution: Dict[str, int] = Field(
        default={"width": 1920, "height": 1080},
        description="카메라 해상도"
    )

    fps: int = Field(
        default=30,
        ge=1,
        le=240,
        description="프레임 레이트 (1~240)"
    )

    auto_exposure: bool = Field(
        default=True,
        description="자동 노출 활성화"
    )

    @field_validator('resolution')
    @classmethod
    def validate_resolution(cls, v: Dict[str, int]) -> Dict[str, int]:
        """해상도 검증 (표준 해상도 권장)"""
        if 'width' not in v or 'height' not in v:
            raise ValueError("resolution에는 width와 height가 필요합니다")

        width, height = v['width'], v['height']

        # 최소 해상도 (640x480)
        if width < 640 or height < 480:
            raise ValueError(
                f"해상도가 너무 낮습니다: {width}x{height} (최소: 640x480)"
            )

        # 최대 해상도 (3840x2160 = 4K)
        if width > 3840 or height > 2160:
            raise ValueError(
                f"해상도가 너무 높습니다: {width}x{height} (최대: 3840x2160)"
            )

        # 표준 해상도 권장
        standard_resolutions = {
            (640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)
        }
        if (width, height) not in standard_resolutions:
            warnings.warn(
                f"비표준 해상도입니다: {width}x{height}. "
                f"표준 해상도 권장: 640x480, 1280x720, 1920x1080, 2560x1440, 3840x2160",
                UserWarning
            )

        return v

    @field_validator('fps')
    @classmethod
    def validate_fps(cls, v: int) -> int:
        """FPS 검증 (표준 프레임 레이트 권장)"""
        standard_fps = {24, 25, 30, 50, 60, 120, 240}
        if v not in standard_fps:
            warnings.warn(
                f"비표준 FPS입니다: {v}. "
                f"표준 FPS 권장: 24, 25, 30, 50, 60, 120, 240",
                UserWarning
            )
        return v

    def validate_custom(self) -> None:
        """카메라 대수 및 해상도/FPS 조합 검증"""
        # min_count <= max_count
        if self.min_count > self.max_count:
            raise ValueError(
                f"min_count({self.min_count})는 "
                f"max_count({self.max_count})보다 작거나 같아야 합니다"
            )

        # 고해상도 + 고FPS 조합 경고
        width = self.resolution['width']
        height = self.resolution['height']
        total_pixels = width * height

        if total_pixels >= 1920 * 1080 and self.fps >= 60:
            warnings.warn(
                f"고해상도({width}x{height}) + 고FPS({self.fps}) 조합은 "
                f"GPU 성능에 부담을 줄 수 있습니다",
                UserWarning
            )


# ==================== 검출 설정 검증 ====================
class DetectionConfig(ConfigValidator):
    """
    객체 검출 설정 검증

    검증 항목:
    - confidence_threshold: 신뢰도 임계값 (0.0~1.0)
    - nms_threshold: NMS 임계값 (0.0~1.0)
    - max_detections: 최대 검출 개수
    - enable_tracking: 객체 추적 활성화

    Examples:
        >>> detection_config = DetectionConfig(
        ...     confidence_threshold=0.75,
        ...     nms_threshold=0.45,
        ...     max_detections=100
        ... )
        >>> detection_config.validate_custom()
    """

    confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="신뢰도 임계값 (0.0~1.0)"
    )

    nms_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="NMS(Non-Maximum Suppression) 임계값 (0.0~1.0)"
    )

    max_detections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="최대 검출 개수 (1~1000)"
    )

    enable_tracking: bool = Field(
        default=True,
        description="객체 추적 활성화"
    )

    def validate_custom(self) -> None:
        """검출 설정 일관성 검증"""
        # confidence_threshold가 너무 높으면 검출 실패 가능
        if self.confidence_threshold > 0.9:
            warnings.warn(
                f"confidence_threshold={self.confidence_threshold}가 너무 높습니다. "
                f"검출률이 낮아질 수 있습니다 (권장: 0.5~0.8)",
                UserWarning
            )


# ==================== 앱 설정 검증 ====================
class AppConfig(ConfigValidator):
    """
    앱 전역 설정 검증

    검증 항목:
    - name: 앱 이름
    - version: 버전 (Semantic Versioning)
    - debug: 디버그 모드
    - log_level: 로그 레벨

    Examples:
        >>> app_config = AppConfig(
        ...     name="COURTVIEW Desktop",
        ...     version="1.0.0",
        ...     debug=False,
        ...     log_level="INFO"
        ... )
        >>> app_config.validate_custom()
    """

    name: str = Field(
        default="COURTVIEW Desktop",
        min_length=1,
        max_length=100,
        description="앱 이름"
    )

    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="버전 (x.y.z)"
    )

    debug: bool = Field(
        default=False,
        description="디버그 모드"
    )

    log_level: str = Field(
        default="INFO",
        description="로그 레벨 (DEBUG/INFO/WARNING/ERROR/CRITICAL)"
    )

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """로그 레벨 검증"""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        v_upper = v.upper()

        if v_upper not in valid_levels:
            raise ValueError(
                f"log_level은 {valid_levels} 중 하나여야 합니다 (입력값: {v})"
            )

        return v_upper

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """버전 형식 검증 (Semantic Versioning)"""
        pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(pattern, v):
            raise ValueError(
                f"version은 'x.y.z' 형식이어야 합니다 (예: 1.0.0) (입력값: {v})"
            )
        return v

    def validate_custom(self) -> None:
        """앱 설정 일관성 검증"""
        # 디버그 모드에서는 로그 레벨 DEBUG 권장
        if self.debug and self.log_level != 'DEBUG':
            warnings.warn(
                f"debug=True일 때는 log_level='DEBUG' 권장 (현재: {self.log_level})",
                UserWarning
            )


# ==================== 전체 설정 검증 클래스 ====================
class DesktopConfigValidator(BaseModel):
    """
    COURTVIEW Desktop 전체 설정 검증

    각 섹션별 설정을 통합하여 검증합니다.
    섹션 간 의존성 검증도 수행합니다.

    Attributes:
        app: 앱 전역 설정
        gpu: GPU 설정
        camera: 카메라 설정
        detection: 객체 검출 설정

    Examples:
        >>> config = DesktopConfigValidator(
        ...     app={"name": "COURTVIEW", "version": "1.0.0"},
        ...     gpu={"device_id": 0, "memory_fraction": 0.8},
        ...     camera={"min_count": 4, "max_count": 8},
        ...     detection={"confidence_threshold": 0.75}
        ... )
        >>> config.validate_all()
    """

    model_config = ConfigDict(
        strict=False,
        validate_assignment=True,
        extra='forbid'
    )

    app: AppConfig = Field(
        default_factory=AppConfig,
        description="앱 전역 설정"
    )

    gpu: GPUConfig = Field(
        default_factory=GPUConfig,
        description="GPU 설정"
    )

    camera: CameraConfig = Field(
        default_factory=CameraConfig,
        description="카메라 설정"
    )

    detection: DetectionConfig = Field(
        default_factory=DetectionConfig,
        description="객체 검출 설정"
    )

    def validate_custom(self) -> None:
        """
        전체 설정 검증 (validate_all 별칭)

        validate_config_dict 유틸리티와의 호환성을 위한 메서드
        """
        self.validate_all()

    def validate_all(self) -> None:
        """
        전체 설정 간 일관성 검증

        각 섹션의 커스텀 검증 + 섹션 간 의존성 검증

        Raises:
            ValueError: 검증 실패 시
        """
        # 각 섹션 커스텀 검증
        self.app.validate_custom()
        self.gpu.validate_custom()
        self.camera.validate_custom()
        self.detection.validate_custom()

        # 섹션 간 의존성 검증
        self._validate_cross_section()

    def _validate_cross_section(self) -> None:
        """
        섹션 간 의존성 검증

        예시:
        - 카메라 대수가 많으면 GPU 배치 크기 조정 필요
        - 고해상도 카메라는 GPU 메모리 많이 필요
        """
        # 카메라 대수와 GPU 배치 크기
        total_cameras = self.camera.max_count
        if total_cameras > 4 and self.gpu.batch_size < 4:
            warnings.warn(
                f"카메라 {total_cameras}대 사용 시 batch_size={self.gpu.batch_size}는 "
                f"너무 작을 수 있습니다 (권장: {total_cameras} 이상)",
                UserWarning
            )

        # 고해상도 + 많은 카메라 = GPU 메모리 부족 가능
        width = self.camera.resolution['width']
        height = self.camera.resolution['height']
        total_pixels = width * height * total_cameras

        # 대략적인 추정: 1920x1080x4대 = ~8M pixels → ~2GB GPU 메모리
        estimated_memory_gb = total_pixels / (1920 * 1080 * 4) * 2

        if estimated_memory_gb > 6 and self.gpu.memory_fraction < 0.8:
            warnings.warn(
                f"고해상도({width}x{height}) x {total_cameras}대 카메라는 "
                f"~{estimated_memory_gb:.1f}GB GPU 메모리 필요. "
                f"memory_fraction={self.gpu.memory_fraction} 증가 권장",
                UserWarning
            )


# ==================== 한글 에러 메시지 ====================
ERROR_MESSAGES_KR = {
    "int_type": "{field}는 정수여야 합니다",
    "float_type": "{field}는 실수여야 합니다",
    "bool_type": "{field}는 불리언(true/false)이어야 합니다",
    "string_type": "{field}는 문자열이어야 합니다",
    "greater_than_equal": "{field}는 {ge} 이상이어야 합니다",
    "less_than_equal": "{field}는 {le} 이하여야 합니다",
    "missing": "{field}는 필수 항목입니다",
    "string_pattern_mismatch": "{field}의 형식이 올바르지 않습니다",
    "string_too_short": "{field}는 최소 {min_length}자 이상이어야 합니다",
    "string_too_long": "{field}는 최대 {max_length}자 이하여야 합니다",
    "extra_forbidden": "정의되지 않은 필드입니다: {field}",
    "enum": "{field}는 {expected} 중 하나여야 합니다",
}


def translate_error(error: dict) -> str:
    """
    Pydantic 에러 → 한글 메시지 변환

    Args:
        error: Pydantic ValidationError의 에러 딕셔너리

    Returns:
        str: 한글 에러 메시지

    Examples:
        >>> error = {
        ...     'type': 'greater_than_equal',
        ...     'loc': ('device_id',),
        ...     'ctx': {'ge': 0}
        ... }
        >>> translate_error(error)
        'device_id는 0 이상이어야 합니다'
    """
    error_type = error['type']
    field = ".".join(str(loc) for loc in error['loc'])

    # 한글 템플릿 조회
    template = ERROR_MESSAGES_KR.get(error_type, error.get('msg', '알 수 없는 오류'))

    # 컨텍스트 정보 추출
    ctx = error.get('ctx', {})

    try:
        return template.format(field=field, **ctx)
    except (KeyError, ValueError):
        # 포맷팅 실패 시 기본 메시지 반환
        return f"{field}: {error.get('msg', '검증 실패')}"


# ==================== 검증 유틸리티 함수 ====================
def validate_config_dict(
    config_dict: Dict[str, Any],
    validator_class: Type[T],
    raise_on_error: bool = True
) -> Tuple[Optional[T], Optional[List[str]]]:
    """
    딕셔너리 → Pydantic 모델 검증

    Args:
        config_dict: 검증할 설정 딕셔너리
        validator_class: 검증 클래스 (GPUConfig, CameraConfig 등)
        raise_on_error: 에러 시 예외 발생 (False면 에러 리스트 반환)

    Returns:
        (검증된 설정 객체, 에러 리스트)

    Raises:
        DataValidationError: 검증 실패 시 (raise_on_error=True)

    Examples:
        >>> config_dict = {"device_id": 0, "memory_fraction": 0.8}
        >>> gpu_config, errors = validate_config_dict(config_dict, GPUConfig)
        >>> if errors:
        ...     print(f"검증 실패: {errors}")
        >>> else:
        ...     print(f"GPU ID: {gpu_config.device_id}")
    """
    try:
        # Pydantic 검증 실행
        validated = validator_class(**config_dict)

        # 커스텀 검증 실행
        validated.validate_custom()

        return validated, None

    except ValidationError as e:
        # Pydantic 검증 에러
        errors = []
        for error in e.errors():
            # 한글 메시지로 변환
            kr_msg = translate_error(error)
            errors.append(kr_msg)

        if raise_on_error:
            raise DataValidationError(
                f"설정 검증 실패: {len(errors)}개 오류",
                context={"errors": errors, "config_dict": str(config_dict)[:100]}
            )

        return None, errors

    except ValueError as e:
        # 커스텀 검증 에러
        errors = [str(e)]

        if raise_on_error:
            raise DataValidationError(
                f"커스텀 검증 실패: {e}",
                context={"errors": errors, "config_dict": str(config_dict)[:100]}
            )

        return None, errors


def validate_config_file(
    file_path: Union[str, Path],
    validator_class: Type[T],
    loader: Optional['ConfigLoader'] = None
) -> T:
    """
    YAML 파일 → 검증된 설정 객체

    Args:
        file_path: YAML 파일 경로
        validator_class: 검증 클래스
        loader: ConfigLoader 인스턴스 (None이면 생성)

    Returns:
        검증된 설정 객체

    Raises:
        ConfigError: 파일 로드 실패
        DataValidationError: 검증 실패

    Examples:
        >>> gpu_config = validate_config_file("configs/gpu.yaml", GPUConfig)
        >>> print(f"GPU ID: {gpu_config.device_id}")
    """
    if loader is None:
        from core_foundation.config.loader import ConfigLoader
        loader = ConfigLoader()

    # YAML 로드
    config_dict = loader.load_yaml(str(file_path))

    # 검증
    validated, errors = validate_config_dict(config_dict, validator_class)

    if errors:
        raise DataValidationError(
            f"설정 파일 검증 실패: {file_path}",
            context={"errors": errors, "file_path": str(file_path)}
        )

    return validated


# ==================== __all__ Export ====================
__all__ = [
    # Enum
    "GPUBackend",
    "LogLevel",
    # 추상 클래스
    "ConfigValidator",
    # 구체적인 검증 클래스
    "GPUConfig",
    "CameraConfig",
    "DetectionConfig",
    "AppConfig",
    # 통합 검증 클래스
    "DesktopConfigValidator",
    # 유틸리티 함수
    "validate_config_dict",
    "validate_config_file",
    "translate_error",
    # 에러 메시지
    "ERROR_MESSAGES_KR",
]
