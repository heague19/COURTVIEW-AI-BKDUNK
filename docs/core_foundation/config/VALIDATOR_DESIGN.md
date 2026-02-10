# validator.py 설계 문서

**파일 경로**: `core_foundation/config/validator.py`
**작성일**: 2025-01-XX
**버전**: v1.0.0
**담당**: COURTVIEW Team

---

## 1. 개요

### 1.1 목적
Pydantic 기반 설정값 검증 시스템으로, YAML/ENV에서 로드된 설정의 타입, 범위, 형식을 검증하여 런타임 에러를 사전에 방지합니다.

### 1.2 핵심 기능
- ✅ **타입 검증**: int, float, str, bool, Enum, List, Dict
- ✅ **범위 검증**: min/max, 정규표현식, 선택지(choices)
- ✅ **필수 필드**: required vs optional
- ✅ **커스텀 검증**: 복잡한 비즈니스 로직 (GPU 메모리 체크, 카메라 대수 등)
- ✅ **자동 타입 변환**: "123" → 123, "true" → True
- ✅ **에러 메시지 한글화**: 사용자 친화적 에러 메시지

### 1.3 설계 원칙
1. **Pydantic V2 사용**: 성능 최적화 (Rust 기반)
2. **단계적 검증**: 타입 → 범위 → 커스텀 순서
3. **명확한 에러**: 어떤 필드가 왜 실패했는지 명시
4. **성능 우선**: 검증 시간 <5ms (평균 설정 파일)

---

## 2. 주요 클래스 설계

### 2.1 ConfigValidator (추상 기본 클래스)

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

class ConfigValidator(BaseModel, ABC):
    """
    설정 검증 기본 클래스

    모든 설정 검증 클래스는 이 클래스를 상속합니다.
    Pydantic BaseModel의 자동 검증 + 커스텀 검증 메서드 제공
    """

    model_config = ConfigDict(
        strict=False,           # 자동 타입 변환 허용 ("123" → 123)
        validate_assignment=True,  # 할당 시에도 검증
        extra='forbid',         # 정의되지 않은 필드 금지
        frozen=False            # 수정 가능 (설정 동적 변경)
    )

    @abstractmethod
    def validate_custom(self) -> None:
        """
        커스텀 검증 로직 (서브클래스에서 구현)

        예시:
        - GPU 메모리와 배치 크기 간 일관성 검증
        - 카메라 해상도와 FPS 조합 가능 여부
        - 멀티 필드 의존성 검증
        """
        pass
```

### 2.2 GPUConfig (GPU 설정 검증)

```python
from enum import Enum

class GPUBackend(str, Enum):
    """GPU 백엔드 타입"""
    CUDA = "cuda"
    METAL = "metal"
    CPU = "cpu"

class GPUConfig(ConfigValidator):
    """
    GPU 설정 검증

    검증 항목:
    - device_id: 0~7 범위 (일반적인 GPU 개수)
    - memory_fraction: 0.1~1.0 (10%~100%)
    - backend: cuda/metal/cpu
    - batch_size: 1~128
    """

    # 필수 필드
    device_id: int = Field(
        default=0,
        ge=0,                   # >=0
        le=7,                   # <=7
        description="GPU 장치 ID (0~7)"
    )

    memory_fraction: float = Field(
        default=0.8,
        ge=0.1,                 # >=0.1 (최소 10%)
        le=1.0,                 # <=1.0 (최대 100%)
        description="GPU 메모리 사용 비율 (0.1~1.0)"
    )

    backend: GPUBackend = Field(
        default=GPUBackend.CUDA,
        description="GPU 백엔드 (cuda/metal/cpu)"
    )

    # 선택 필드
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
        """
        GPU ID 검증 (실제 GPU 존재 여부는 런타임에 체크)
        """
        if v < 0 or v > 7:
            raise ValueError(f"GPU device_id는 0~7 범위여야 합니다 (입력값: {v})")
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """
        배치 크기 검증 (2의 거듭제곱 권장)
        """
        if v > 0 and (v & (v - 1)) != 0:
            # 경고만 (에러는 아님)
            import warnings
            warnings.warn(
                f"batch_size={v}는 2의 거듭제곱이 아닙니다. "
                f"성능 최적화를 위해 2/4/8/16/32/64 권장"
            )
        return v

    def validate_custom(self) -> None:
        """
        GPU 메모리와 배치 크기 간 일관성 검증
        """
        # 예상 메모리 사용량 (간단한 추정)
        estimated_memory_gb = self.batch_size * 0.5  # 배치당 ~500MB

        if self.memory_fraction < 0.5 and self.batch_size > 16:
            raise ValueError(
                f"GPU 메모리 비율({self.memory_fraction})이 낮으면 "
                f"배치 크기({self.batch_size})를 줄여야 합니다"
            )
```

### 2.3 CameraConfig (카메라 설정 검증)

```python
class CameraConfig(ConfigValidator):
    """
    카메라 설정 검증

    검증 항목:
    - min_count: 최소 카메라 대수 (4대 이상 권장)
    - max_count: 최대 카메라 대수
    - resolution: 해상도 (width x height)
    - fps: 프레임 레이트 (1~240)
    """

    min_count: int = Field(
        default=4,
        ge=1,                   # 최소 1대
        le=32,                  # 최대 32대
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
        """
        해상도 검증 (표준 해상도 권장)
        """
        if 'width' not in v or 'height' not in v:
            raise ValueError("resolution에는 width와 height가 필요합니다")

        width, height = v['width'], v['height']

        # 최소 해상도 (640x480)
        if width < 640 or height < 480:
            raise ValueError(f"해상도가 너무 낮습니다: {width}x{height} (최소: 640x480)")

        # 최대 해상도 (3840x2160 = 4K)
        if width > 3840 or height > 2160:
            raise ValueError(f"해상도가 너무 높습니다: {width}x{height} (최대: 3840x2160)")

        # 표준 해상도 권장
        standard_resolutions = {
            (640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)
        }
        if (width, height) not in standard_resolutions:
            import warnings
            warnings.warn(
                f"비표준 해상도입니다: {width}x{height}. "
                f"표준 해상도 권장: 640x480, 1280x720, 1920x1080, 2560x1440, 3840x2160"
            )

        return v

    @field_validator('fps')
    @classmethod
    def validate_fps(cls, v: int) -> int:
        """
        FPS 검증 (표준 프레임 레이트 권장)
        """
        standard_fps = {24, 25, 30, 50, 60, 120, 240}
        if v not in standard_fps:
            import warnings
            warnings.warn(
                f"비표준 FPS입니다: {v}. "
                f"표준 FPS 권장: 24, 25, 30, 50, 60, 120, 240"
            )
        return v

    def validate_custom(self) -> None:
        """
        카메라 대수 및 해상도/FPS 조합 검증
        """
        # min_count <= max_count
        if self.min_count > self.max_count:
            raise ValueError(
                f"min_count({self.min_count})는 max_count({self.max_count})보다 작거나 같아야 합니다"
            )

        # 고해상도 + 고FPS 조합 경고
        width = self.resolution['width']
        height = self.resolution['height']
        total_pixels = width * height

        if total_pixels >= 1920 * 1080 and self.fps >= 60:
            import warnings
            warnings.warn(
                f"고해상도({width}x{height}) + 고FPS({self.fps}) 조합은 "
                f"GPU 성능에 부담을 줄 수 있습니다"
            )
```

### 2.4 DetectionConfig (검출 설정 검증)

```python
class DetectionConfig(ConfigValidator):
    """
    객체 검출 설정 검증

    검증 항목:
    - confidence_threshold: 신뢰도 임계값 (0.0~1.0)
    - nms_threshold: NMS 임계값 (0.0~1.0)
    - max_detections: 최대 검출 개수
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
        """
        검출 설정 일관성 검증
        """
        # confidence_threshold가 너무 높으면 검출 실패 가능
        if self.confidence_threshold > 0.9:
            import warnings
            warnings.warn(
                f"confidence_threshold={self.confidence_threshold}가 너무 높습니다. "
                f"검출률이 낮아질 수 있습니다 (권장: 0.5~0.8)"
            )
```

### 2.5 AppConfig (앱 설정 검증)

```python
import re

class AppConfig(ConfigValidator):
    """
    앱 전역 설정 검증

    검증 항목:
    - name: 앱 이름
    - version: 버전 (Semantic Versioning)
    - debug: 디버그 모드
    - log_level: 로그 레벨
    """

    name: str = Field(
        default="COURTVIEW Desktop",
        min_length=1,
        max_length=100,
        description="앱 이름"
    )

    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",  # Semantic Versioning
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
        """
        로그 레벨 검증
        """
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
        """
        버전 형식 검증 (Semantic Versioning)
        """
        pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(pattern, v):
            raise ValueError(
                f"version은 'x.y.z' 형식이어야 합니다 (예: 1.0.0) (입력값: {v})"
            )
        return v

    def validate_custom(self) -> None:
        """
        앱 설정 일관성 검증
        """
        # 디버그 모드에서는 로그 레벨 DEBUG 권장
        if self.debug and self.log_level != 'DEBUG':
            import warnings
            warnings.warn(
                f"debug=True일 때는 log_level='DEBUG' 권장 (현재: {self.log_level})"
            )
```

---

## 3. 전체 설정 검증 클래스

### 3.1 DesktopConfigValidator

```python
class DesktopConfigValidator(BaseModel):
    """
    COURTVIEW Desktop 전체 설정 검증

    각 섹션별 설정을 통합하여 검증합니다.
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

    def validate_all(self) -> None:
        """
        전체 설정 간 일관성 검증

        각 섹션의 커스텀 검증 + 섹션 간 의존성 검증
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
            import warnings
            warnings.warn(
                f"카메라 {total_cameras}대 사용 시 batch_size={self.gpu.batch_size}는 "
                f"너무 작을 수 있습니다 (권장: {total_cameras} 이상)"
            )

        # 고해상도 + 많은 카메라 = GPU 메모리 부족 가능
        width = self.camera.resolution['width']
        height = self.camera.resolution['height']
        total_pixels = width * height * total_cameras

        # 대략적인 추정: 1920x1080x4대 = ~8M pixels → ~2GB GPU 메모리
        estimated_memory_gb = total_pixels / (1920 * 1080 * 4) * 2

        if estimated_memory_gb > 6 and self.gpu.memory_fraction < 0.8:
            import warnings
            warnings.warn(
                f"고해상도({width}x{height}) x {total_cameras}대 카메라는 "
                f"~{estimated_memory_gb:.1f}GB GPU 메모리 필요. "
                f"memory_fraction={self.gpu.memory_fraction} 증가 권장"
            )
```

---

## 4. 검증 유틸리티 함수

### 4.1 validate_config_dict()

```python
from pydantic import ValidationError
from typing import Type, TypeVar

T = TypeVar('T', bound=ConfigValidator)

def validate_config_dict(
    config_dict: Dict[str, Any],
    validator_class: Type[T],
    raise_on_error: bool = True
) -> tuple[Optional[T], Optional[List[str]]]:
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

    예시:
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
            field = ".".join(str(loc) for loc in error['loc'])
            msg = error['msg']
            errors.append(f"{field}: {msg}")

        if raise_on_error:
            from core_foundation.exceptions.validation import DataValidationError
            raise DataValidationError(
                f"설정 검증 실패: {len(errors)}개 오류",
                context={"errors": errors, "config_dict": config_dict}
            )

        return None, errors

    except ValueError as e:
        # 커스텀 검증 에러
        errors = [str(e)]

        if raise_on_error:
            from core_foundation.exceptions.validation import DataValidationError
            raise DataValidationError(
                f"커스텀 검증 실패: {e}",
                context={"errors": errors, "config_dict": config_dict}
            )

        return None, errors
```

### 4.2 validate_config_file()

```python
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

    예시:
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
        from core_foundation.exceptions.validation import DataValidationError
        raise DataValidationError(
            f"설정 파일 검증 실패: {file_path}",
            context={"errors": errors, "file_path": str(file_path)}
        )

    return validated
```

---

## 5. 성능 목표

| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| 검증 시간 | <5ms | 평균 설정 파일 (50개 필드) |
| 메모리 사용량 | <100KB | 검증된 객체 1개 |
| 처리량 | >1,000 validations/sec | 벤치마크 테스트 |
| 에러 메시지 생성 | <1ms | Pydantic 내장 포매터 |

---

## 6. 에러 처리

### 6.1 에러 코드 매핑

| Pydantic Error | 에러 코드 | 설명 |
|----------------|----------|------|
| `type_error.integer` | CV301 | 정수 타입 불일치 |
| `value_error.number.not_ge` | CV303 | 최소값 미달 |
| `value_error.number.not_le` | CV303 | 최대값 초과 |
| `value_error.missing` | CV301 | 필수 필드 누락 |
| `value_error.str.regex` | CV302 | 정규표현식 불일치 |

### 6.2 한글 에러 메시지

```python
ERROR_MESSAGES_KR = {
    "type_error.integer": "{field}는 정수여야 합니다",
    "type_error.float": "{field}는 실수여야 합니다",
    "type_error.bool": "{field}는 불리언(true/false)이어야 합니다",
    "value_error.number.not_ge": "{field}는 {limit_value} 이상이어야 합니다",
    "value_error.number.not_le": "{field}는 {limit_value} 이하여야 합니다",
    "value_error.missing": "{field}는 필수 항목입니다",
    "value_error.str.regex": "{field}의 형식이 올바르지 않습니다",
}

def translate_error(error: dict) -> str:
    """
    Pydantic 에러 → 한글 메시지 변환
    """
    error_type = error['type']
    field = ".".join(str(loc) for loc in error['loc'])

    template = ERROR_MESSAGES_KR.get(error_type, error['msg'])

    return template.format(
        field=field,
        limit_value=error.get('ctx', {}).get('limit_value', ''),
        **error.get('ctx', {})
    )
```

---

## 7. 사용 예시

### 7.1 기본 사용

```python
from core_foundation.config.validator import GPUConfig, validate_config_dict

# 1. 딕셔너리 검증
config_dict = {
    "device_id": 0,
    "memory_fraction": 0.8,
    "backend": "cuda",
    "batch_size": 8
}

gpu_config, errors = validate_config_dict(config_dict, GPUConfig)

if errors:
    print(f"검증 실패: {errors}")
else:
    print(f"GPU ID: {gpu_config.device_id}")
    print(f"메모리 비율: {gpu_config.memory_fraction}")
```

### 7.2 YAML 파일 검증

```python
from core_foundation.config.validator import validate_config_file, GPUConfig

# YAML 파일 → 검증된 객체
gpu_config = validate_config_file("configs/gpu.yaml", GPUConfig)

print(f"GPU Backend: {gpu_config.backend.value}")
```

### 7.3 전체 설정 검증

```python
from core_foundation.config.validator import DesktopConfigValidator
from core_foundation.config.loader import ConfigLoader

# 1. 설정 로드
loader = ConfigLoader()
app_config = loader.load_yaml("configs/app.yaml")
gpu_config = loader.load_yaml("configs/gpu.yaml")
camera_config = loader.load_yaml("configs/camera.yaml")
detection_config = loader.load_yaml("configs/detection.yaml")

# 2. 전체 검증
config_validator = DesktopConfigValidator(
    app=app_config,
    gpu=gpu_config,
    camera=camera_config,
    detection=detection_config
)

# 3. 커스텀 검증 + 섹션 간 의존성 검증
config_validator.validate_all()

print("✅ 모든 설정 검증 완료")
```

---

## 8. 테스트 계획

### 8.1 단위 테스트 (20개)

**GPUConfig (5개)**
- ✅ 정상 값 검증
- ✅ device_id 범위 초과
- ✅ memory_fraction 범위 초과
- ✅ backend Enum 검증
- ✅ 커스텀 검증 (메모리 + 배치 크기)

**CameraConfig (5개)**
- ✅ 정상 값 검증
- ✅ 해상도 범위 검증
- ✅ FPS 범위 검증
- ✅ min_count > max_count 검증
- ✅ 고해상도 + 고FPS 경고

**DetectionConfig (3개)**
- ✅ 신뢰도 임계값 범위
- ✅ NMS 임계값 범위
- ✅ max_detections 범위

**AppConfig (4개)**
- ✅ 버전 형식 검증 (Semantic Versioning)
- ✅ 로그 레벨 검증
- ✅ name 길이 검증
- ✅ 디버그 + 로그 레벨 일관성

**DesktopConfigValidator (3개)**
- ✅ 전체 설정 검증
- ✅ 섹션 간 의존성 검증
- ✅ 에러 메시지 한글화

### 8.2 성능 테스트 (5개)

- ✅ 검증 시간: <5ms (평균 설정)
- ✅ 메모리 사용량: <100KB
- ✅ 처리량: >1,000 validations/sec
- ✅ 대량 검증: 100개 설정 <500ms
- ✅ 에러 생성 시간: <1ms

---

## 9. 구현 체크리스트

- [ ] ConfigValidator 추상 클래스 구현
- [ ] GPUConfig 구현 + field_validator
- [ ] CameraConfig 구현 + 해상도/FPS 검증
- [ ] DetectionConfig 구현
- [ ] AppConfig 구현 + 버전/로그 레벨 검증
- [ ] DesktopConfigValidator 구현 + 섹션 간 검증
- [ ] validate_config_dict() 유틸리티
- [ ] validate_config_file() 유틸리티
- [ ] 한글 에러 메시지 translate_error()
- [ ] 단위 테스트 20개 작성 + 실행
- [ ] 성능 테스트 5개 작성 + 실행
- [ ] __init__.py export 추가

---

## 10. 의존성

### 10.1 필수 패키지

```txt
pydantic>=2.0.0         # V2 필수 (Rust 기반 성능)
pydantic-settings>=2.0.0  # BaseSettings (settings.py용)
```

### 10.2 내부 의존성

```python
from core_foundation.exceptions.validation import DataValidationError, ConfigError
from core_foundation.config.loader import ConfigLoader
```

---

## 11. 참고 자료

- **Pydantic V2 문서**: https://docs.pydantic.dev/latest/
- **Field Validators**: https://docs.pydantic.dev/latest/concepts/validators/
- **ConfigDict**: https://docs.pydantic.dev/latest/api/config/
- **Semantic Versioning**: https://semver.org/

---

**작성 완료**: 2025-01-XX
**검토자**: COURTVIEW Team
**승인 상태**: ⏸️ 대기 중
