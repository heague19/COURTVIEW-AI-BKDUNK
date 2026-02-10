# settings.py 설계 문서

**파일 경로**: `core_foundation/config/settings.py`
**작성일**: 2025-01-XX
**버전**: v1.0.0
**담당**: COURTVIEW Team

---

## 1. 개요

### 1.1 목적
전역 설정 객체(Singleton)를 제공하여 앱 전체에서 단일하고 일관된 설정 접근을 보장합니다.
Loader + Validator를 통합하여 YAML → 검증 → 타입 안전 객체 변환 전체 플로우를 자동화합니다.

### 1.2 핵심 기능
- ✅ **싱글톤 패턴**: 앱 전체에서 단일 설정 인스턴스
- ✅ **환경별 설정**: dev/prod/test 자동 로드
- ✅ **Loader + Validator 통합**: YAML → 검증 → 객체
- ✅ **타입 안전**: Pydantic 기반 타입 힌팅
- ✅ **설정 리로드**: 런타임에 설정 재로드 가능
- ✅ **불변성 보장**: 설정 변경 추적 및 제어

### 1.3 설계 원칙
1. **싱글톤**: 전역 단일 인스턴스 (Thread-Safe)
2. **지연 초기화**: 첫 접근 시 로드 (Lazy Loading)
3. **환경 기반**: ENV 환경 변수로 dev/prod 구분
4. **타입 안전**: IDE 자동완성 + 타입 체크
5. **최소 의존성**: Loader, Validator만 사용

---

## 2. 싱글톤 패턴 구현

### 2.1 구현 방법

```python
from typing import Optional

class DesktopSettings:
    """
    싱글톤 패턴으로 구현된 전역 설정 객체

    특징:
    - Thread-Safe (threading.Lock 사용)
    - Lazy Loading (첫 접근 시 초기화)
    - 불변성 보장 (_frozen 플래그)
    """

    _instance: Optional['DesktopSettings'] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """
        싱글톤 인스턴스 생성 (Thread-Safe)

        Returns:
            DesktopSettings: 싱글톤 인스턴스
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, reload: bool = False):
        """
        초기화 (한 번만 실행)

        Args:
            reload: 강제 재로드 (기본: False)
        """
        if self._initialized and not reload:
            return  # 이미 초기화됨

        with self._lock:
            if not self._initialized or reload:
                self._load_settings()
                self._initialized = True
```

### 2.2 Thread-Safety

- **Lock 사용**: `threading.Lock()`으로 동시 접근 제어
- **Double-Checked Locking**: 성능 최적화
- **원자적 초기화**: 한 번만 초기화 보장

---

## 3. DesktopSettings 클래스 설계

### 3.1 클래스 구조

```python
from pathlib import Path
from typing import Optional, Dict, Any
import os

from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    DesktopConfigValidator,
)


class DesktopSettings:
    """
    COURTVIEW Desktop 전역 설정

    싱글톤 패턴으로 구현되어 앱 전체에서 단일 인스턴스만 존재합니다.
    환경별 설정 자동 로드 (dev/prod/test)

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
    """

    _instance: Optional['DesktopSettings'] = None
    _lock = threading.Lock()
    _initialized = False

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        env_file: Optional[Path] = None,
        environment: Optional[str] = None,
        reload: bool = False
    ):
        """
        초기화

        Args:
            config_dir: 설정 디렉토리 (기본: ./configs)
            env_file: 환경 변수 파일 (기본: .env)
            environment: 환경 (dev/prod/test, 기본: ENV 환경 변수)
            reload: 강제 재로드 (기본: False)
        """
        if self._initialized and not reload:
            return

        with self._lock:
            if not self._initialized or reload:
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
        """
        # Step 1: Base 설정 로드
        base_config = self._loader.load_yaml("base.yaml")

        # Step 2: 환경별 설정 로드
        env_config_file = f"env_{self._environment}.yaml"
        env_config = {}
        try:
            env_config = self._loader.load_yaml(env_config_file)
        except Exception:
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

    def get_dict(self) -> Dict[str, Any]:
        """
        설정을 딕셔너리로 반환

        Returns:
            Dict[str, Any]: 전체 설정 딕셔너리

        Examples:
            >>> config_dict = settings.get_dict()
            >>> print(config_dict["gpu"]["device_id"])
            0
        """
        return {
            "app": self.app.model_dump(),
            "gpu": self.gpu.model_dump(),
            "camera": self.camera.model_dump(),
            "detection": self.detection.model_dump(),
            "environment": self.environment,
        }

    def __setattr__(self, name: str, value: Any) -> None:
        """
        속성 설정 제어 (불변성 보장)

        _frozen=True이면 설정 변경 불가

        Raises:
            AttributeError: 설정 동결 후 변경 시도
        """
        if hasattr(self, '_frozen') and self._frozen:
            if name not in ('_frozen', '_initialized'):
                raise AttributeError(
                    f"설정이 동결되어 있습니다. "
                    f"설정을 변경하려면 reload()를 사용하세요."
                )
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"DesktopSettings(environment={self.environment}, "
            f"app={self.app.name}, "
            f"gpu_id={self.gpu.device_id})"
        )


# ==================== 전역 싱글톤 인스턴스 ====================
settings: DesktopSettings = DesktopSettings()
```

---

## 4. 환경별 설정 로드

### 4.1 환경 구분

| 환경 | ENV 값 | 설정 파일 | 용도 |
|------|--------|----------|------|
| 개발 | dev | env_dev.yaml | 로컬 개발 |
| 프로덕션 | prod | env_prod.yaml | 운영 서버 |
| 테스트 | test | env_test.yaml | 단위/통합 테스트 |

### 4.2 환경 결정 우선순위

1. **명시적 인자**: `DesktopSettings(environment="prod")`
2. **ENV 환경 변수**: `export ENV=prod`
3. **기본값**: `dev` (개발 환경)

### 4.3 설정 병합 우선순위

```
ENV 변수 (.env) > 환경별 설정 (env_dev.yaml) > 기본 설정 (base.yaml)
```

---

## 5. 사용 예시

### 5.1 기본 사용

```python
from core_foundation.config.settings import settings

# 설정 접근 (타입 안전)
print(f"GPU ID: {settings.gpu.device_id}")
print(f"앱 이름: {settings.app.name}")
print(f"카메라 대수: {settings.camera.min_count}")

# IDE 자동완성 지원
batch_size = settings.gpu.batch_size  # IDE가 타입 추론
```

### 5.2 환경별 설정

```python
import os

# 환경 설정 (앱 시작 시)
os.environ["ENV"] = "prod"

from core_foundation.config.settings import settings

print(f"환경: {settings.environment}")  # "prod"
print(f"디버그 모드: {settings.app.debug}")  # False (prod는 debug=False)
```

### 5.3 설정 리로드

```python
from core_foundation.config.settings import settings

# 설정 파일 수정 후 재로드
settings.reload()

print(f"변경된 배치 크기: {settings.gpu.batch_size}")
```

### 5.4 설정 딕셔너리 변환

```python
from core_foundation.config.settings import settings

# 딕셔너리로 변환 (로깅, 디버깅 등)
config_dict = settings.get_dict()
print(config_dict)
```

### 5.5 커스텀 환경 (테스트)

```python
from pathlib import Path
from core_foundation.config.settings import DesktopSettings

# 테스트용 별도 설정
test_settings = DesktopSettings(
    config_dir=Path("./tests/fixtures"),
    environment="test",
    reload=True
)

assert test_settings.gpu.device_id == 0
```

---

## 6. Loader + Validator 통합

### 6.1 통합 플로우

```
┌─────────────────────────────────────────────────────────────┐
│                    DesktopSettings                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. ConfigLoader                                            │
│     ├─ base.yaml 로드                                       │
│     ├─ env_dev.yaml 로드                                    │
│     └─ .env 환경 변수 로드                                  │
│                                                             │
│  2. 병합 (merge_configs)                                     │
│     └─ base + env + ENV                                      │
│                                                             │
│  3. DesktopConfigValidator                                   │
│     ├─ AppConfig 검증                                        │
│     ├─ GPUConfig 검증                                        │
│     ├─ CameraConfig 검증                                     │
│     ├─ DetectionConfig 검증                                  │
│     └─ 섹션 간 의존성 검증                                  │
│                                                             │
│  4. 타입 안전 객체 생성                                     │
│     └─ settings.gpu.device_id (int 타입 보장)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 에러 처리

```python
from core_foundation.exceptions.validation import ConfigError, DataValidationError

try:
    from core_foundation.config.settings import settings
    print(f"GPU ID: {settings.gpu.device_id}")
except ConfigError as e:
    print(f"설정 파일 에러: {e.message}")
    # CV101: 파일 없음
    # CV102: 파싱 실패
except DataValidationError as e:
    print(f"검증 실패: {e.message}")
    # CV301: 타입 불일치
    # CV303: 범위 초과
```

---

## 7. 성능 목표

| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| 초기화 시간 | <50ms | 첫 settings 접근 (YAML 로드 + 검증) |
| 속성 접근 | <0.001ms | settings.gpu.device_id |
| 메모리 사용량 | <500KB | settings 인스턴스 1개 |
| 리로드 시간 | <50ms | settings.reload() |

---

## 8. 설정 파일 구조

### 8.1 base.yaml (기본 설정)

```yaml
# configs/base.yaml
app:
  name: "COURTVIEW Desktop"
  version: "1.0.0"
  debug: false
  log_level: "INFO"

gpu:
  device_id: 0
  memory_fraction: 0.8
  backend: "cuda"
  batch_size: 8
  enable_fp16: false

camera:
  min_count: 4
  max_count: 8
  resolution:
    width: 1920
    height: 1080
  fps: 30
  auto_exposure: true

detection:
  confidence_threshold: 0.75
  nms_threshold: 0.45
  max_detections: 100
  enable_tracking: true
```

### 8.2 env_dev.yaml (개발 환경)

```yaml
# configs/env_dev.yaml
app:
  debug: true
  log_level: "DEBUG"

gpu:
  batch_size: 4  # 개발 시 작은 배치

camera:
  min_count: 1  # 개발 시 카메라 1대만
```

### 8.3 env_prod.yaml (프로덕션 환경)

```yaml
# configs/env_prod.yaml
app:
  debug: false
  log_level: "WARNING"

gpu:
  memory_fraction: 0.9  # 프로덕션은 메모리 최대 활용
  batch_size: 16

camera:
  min_count: 4
  max_count: 8
```

### 8.4 .env (환경 변수)

```bash
# .env
ENV=dev

# GPU 오버라이드
GPU_DEVICE_ID=1
GPU_MEMORY_FRACTION=0.7

# 로깅
LOG_LEVEL=DEBUG
```

---

## 9. 테스트 계획

### 9.1 단위 테스트 (10개)

**싱글톤 (3개)**
- ✅ 싱글톤 인스턴스 생성
- ✅ Thread-Safe 동시 접근
- ✅ 한 번만 초기화

**환경별 설정 (3개)**
- ✅ dev 환경 로드
- ✅ prod 환경 로드
- ✅ 환경 변수 오버라이드

**설정 접근 (2개)**
- ✅ 타입 안전 속성 접근
- ✅ 딕셔너리 변환

**리로드 (2개)**
- ✅ 설정 리로드
- ✅ 불변성 보장 (freeze)

### 9.2 통합 테스트 (5개)

- ✅ Loader + Validator 통합
- ✅ YAML → 검증 → 객체 전체 플로우
- ✅ 환경별 설정 병합 우선순위
- ✅ 에러 처리 (파일 없음, 검증 실패)
- ✅ 멀티 스레드 동시 접근

### 9.3 성능 테스트 (3개)

- ✅ 초기화 시간: <50ms
- ✅ 속성 접근 시간: <0.001ms
- ✅ 리로드 시간: <50ms

---

## 10. 구현 체크리스트

- [ ] DesktopSettings 클래스 구현
- [ ] 싱글톤 패턴 (Thread-Safe)
- [ ] _load_settings() 메서드 (Loader + Validator 통합)
- [ ] reload() 메서드
- [ ] get_dict() 메서드
- [ ] __setattr__() 오버라이드 (불변성)
- [ ] 전역 settings 인스턴스
- [ ] 환경별 설정 로드 (dev/prod/test)
- [ ] 단위 테스트 10개 작성 + 실행
- [ ] 통합 테스트 5개 작성 + 실행
- [ ] 성능 테스트 3개 작성 + 실행
- [ ] __init__.py export 업데이트

---

## 11. 의존성

### 11.1 내부 의존성

```python
from core_foundation.config.loader import ConfigLoader
from core_foundation.config.validator import (
    AppConfig,
    GPUConfig,
    CameraConfig,
    DetectionConfig,
    DesktopConfigValidator,
)
from core_foundation.exceptions.validation import ConfigError, DataValidationError
```

### 11.2 표준 라이브러리

```python
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any
```

---

## 12. 보안 고려사항

### 12.1 민감 정보 보호

```python
def get_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
    """
    설정을 딕셔너리로 반환

    Args:
        include_sensitive: 민감 정보 포함 여부 (기본: False)

    Returns:
        Dict[str, Any]: 설정 딕셔너리 (민감 정보 마스킹)
    """
    config_dict = {
        "app": self.app.model_dump(),
        "gpu": self.gpu.model_dump(),
        "camera": self.camera.model_dump(),
        "detection": self.detection.model_dump(),
    }

    if not include_sensitive:
        # 민감 정보 마스킹 (API 키, 비밀번호 등)
        # 현재는 없지만, 향후 추가 시 마스킹 처리
        pass

    return config_dict
```

### 12.2 불변성 보장

- `_frozen` 플래그로 초기화 후 설정 변경 금지
- `reload()` 메서드로만 변경 가능
- 의도하지 않은 설정 변경 방지

---

## 13. 참고 자료

- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Singleton Pattern**: https://refactoring.guru/design-patterns/singleton/python/example
- **Thread-Safe Singleton**: https://en.wikipedia.org/wiki/Double-checked_locking

---

**작성 완료**: 2025-01-XX
**검토자**: COURTVIEW Team
**승인 상태**: ⏸️ 대기 중
