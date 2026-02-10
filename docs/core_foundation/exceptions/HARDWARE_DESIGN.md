# exceptions/hardware.py 설계 문서

**파일 경로**: `D:\COURTVIEW_DESK\core_foundation\exceptions\hardware.py`
**모듈**: Layer 0 - core_foundation
**목적**: 하드웨어 리소스 관련 예외 클래스
**버전**: 1.0.0

---

## 1. 개요 (Overview)

### 1.1 설계 목적
- **GPU 에러**: CUDA/Metal GPU 초기화, 메모리 부족, 드라이버 문제
- **카메라 에러**: 멀티뷰 카메라 연결, 초기화, 프레임 캡처 실패
- **메모리 에러**: 시스템/GPU 메모리 부족
- **CourtViewError 파생**: 기본 예외 클래스 기능 상속
- **하드웨어 정보 포함**: GPU ID, 메모리 사용량, 카메라 ID 등

### 1.2 Desktop vs App Server 차이점

| 기능 | App Server | Desktop |
|------|-----------|---------|
| GPU 관리 | 분산 GPU, 멀티 노드 | 단일 GPU (CUDA/Metal) |
| 카메라 | 네트워크 카메라 | USB/로컬 카메라 (4~8대) |
| 메모리 관리 | Redis, Memcached | 시스템 메모리만 |
| 에러 복구 | Circuit Breaker, Retry | 즉시 에러 표시 |

### 1.3 주요 예외 클래스

```python
GPUError                  # CV201 (GPU 관련)
CameraError               # CV202 (카메라 관련)
InsufficientMemoryError   # CV901 (메모리 부족)
```

---

## 2. 임포트 정의 (Import Definitions)

### 2.1 Direct Imports
```python
from typing import Optional, Dict, Any
from core_foundation.exceptions.base import CourtViewError
```

**사용 모듈**:
- `typing`: 타입 힌팅 (Optional, Dict, Any)
- `core_foundation.exceptions.base`: CourtViewError 기본 클래스

### 2.2 의존성 없음
❌ 사용하지 않는 것들:
- `torch`, `tensorflow`: GPU 관리는 shared/utils/gpu_manager.py에서 수행
- `cv2`, `pyrealsense2`: 카메라 관리는 detection/camera/에서 수행
- `psutil`: 메모리 측정은 호출자가 수행

---

## 3. 클래스 설계 (Class Design)

### 3.1 GPUError (GPU 예외)

```python
class GPUError(CourtViewError):
    """
    GPU 관련 예외

    사용 사례:
    - GPU 초기화 실패
    - CUDA/Metal 에러
    - GPU 메모리 부족
    - GPU 드라이버 문제
    - 모델 로드 실패 (GPU 메모리)

    Error Code: CV201

    Attributes:
        gpu_id (int): GPU 장치 ID (context에 저장)
        required_memory_mb (int): 필요한 메모리 (MB, context에 저장)
        available_memory_mb (int): 사용 가능한 메모리 (MB, context에 저장)
    """

    ERROR_CODE = "CV201"

    def __init__(
        self,
        message: str,
        *,
        gpu_id: Optional[int] = None,
        required_memory_mb: Optional[int] = None,
        available_memory_mb: Optional[int] = None,
        **kwargs
    ) -> None:
```

#### 3.1.1 초기화 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|---------|------|------|------|------|
| `message` | str | ✅ | 에러 메시지 | "GPU 초기화 실패" |
| `gpu_id` | int | ❌ | GPU 장치 ID | 0 |
| `required_memory_mb` | int | ❌ | 필요한 메모리 (MB) | 8000 |
| `available_memory_mb` | int | ❌ | 사용 가능한 메모리 (MB) | 4000 |
| `**kwargs` | Any | ❌ | CourtViewError 추가 인자 | context, original_error |

#### 3.1.2 사용 시나리오

| 시나리오 | gpu_id | required_mb | available_mb | 설명 |
|---------|--------|-------------|--------------|------|
| **GPU 없음** | None | None | None | GPU가 감지되지 않음 |
| **초기화 실패** | 0 | None | None | CUDA/Metal 초기화 실패 |
| **메모리 부족** | 0 | 8000 | 4000 | 모델 로드 시 메모리 부족 |
| **드라이버 에러** | 0 | None | None | GPU 드라이버 버전 불일치 |

### 3.2 CameraError (카메라 예외)

```python
class CameraError(CourtViewError):
    """
    카메라 관련 예외

    사용 사례:
    - 카메라 연결 실패
    - 카메라 초기화 실패
    - 프레임 캡처 실패
    - 카메라 설정 오류 (해상도, FPS)
    - 최소 카메라 대수 미달 (4대 이상 필요)

    Error Code: CV202

    Attributes:
        camera_id (int): 카메라 장치 ID (context에 저장)
        camera_name (str): 카메라 이름 (context에 저장)
    """

    ERROR_CODE = "CV202"

    def __init__(
        self,
        message: str,
        *,
        camera_id: Optional[int] = None,
        camera_name: Optional[str] = None,
        **kwargs
    ) -> None:
```

#### 3.2.1 초기화 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|---------|------|------|------|------|
| `message` | str | ✅ | 에러 메시지 | "카메라 연결 실패" |
| `camera_id` | int | ❌ | 카메라 장치 ID | 0 |
| `camera_name` | str | ❌ | 카메라 이름 | "USB Camera 0" |
| `**kwargs` | Any | ❌ | CourtViewError 추가 인자 | context, original_error |

#### 3.2.2 사용 시나리오

| 시나리오 | camera_id | camera_name | 설명 |
|---------|-----------|-------------|------|
| **연결 실패** | 0 | "USB Camera 0" | 카메라 장치 미감지 |
| **초기화 실패** | 1 | None | 카메라 열기 실패 |
| **프레임 캡처 실패** | 0 | "Camera A" | 프레임 읽기 타임아웃 |
| **최소 대수 미달** | None | None | 4대 미만 감지 |

### 3.3 InsufficientMemoryError (메모리 부족 예외)

```python
class InsufficientMemoryError(CourtViewError):
    """
    메모리 부족 예외

    사용 사례:
    - 시스템 메모리 부족
    - GPU 메모리 부족
    - 캐시 메모리 부족
    - 대용량 영상 로딩 실패

    Error Code: CV901

    Attributes:
        required_mb (int): 필요한 메모리 (MB, context에 저장)
        available_mb (int): 사용 가능한 메모리 (MB, context에 저장)
        memory_type (str): 메모리 타입 ("system", "gpu", "cache")
    """

    ERROR_CODE = "CV901"

    def __init__(
        self,
        message: str,
        *,
        required_mb: Optional[int] = None,
        available_mb: Optional[int] = None,
        memory_type: str = "system",  # "system", "gpu", "cache"
        **kwargs
    ) -> None:
```

#### 3.3.1 초기화 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|---------|------|------|------|------|
| `message` | str | ✅ | 에러 메시지 | "시스템 메모리 부족" |
| `required_mb` | int | ❌ | 필요한 메모리 (MB) | 16000 |
| `available_mb` | int | ❌ | 사용 가능한 메모리 (MB) | 8000 |
| `memory_type` | str | ❌ | 메모리 타입 | "system" |
| `**kwargs` | Any | ❌ | CourtViewError 추가 인자 | context, original_error |

#### 3.3.2 메모리 타입

| 타입 | 설명 | 사용 상황 |
|------|------|----------|
| **"system"** | 시스템 RAM | 대용량 영상 로딩, NumPy 배열 |
| **"gpu"** | GPU VRAM | 모델 추론, 텐서 연산 |
| **"cache"** | 캐시 메모리 | ConfigLoader 캐시, 프레임 버퍼 |

---

## 4. 주요 기능 (Key Features)

### 4.1 컨텍스트 자동 추가

#### GPUError
```python
error = GPUError(
    "GPU 메모리 부족",
    gpu_id=0,
    required_memory_mb=8000,
    available_memory_mb=4000
)

# context: {
#     "gpu_id": 0,
#     "required_memory_mb": 8000,
#     "available_memory_mb": 4000
# }
```

#### CameraError
```python
error = CameraError(
    "카메라 연결 실패",
    camera_id=0,
    camera_name="USB Camera 0"
)

# context: {
#     "camera_id": 0,
#     "camera_name": "USB Camera 0"
# }
```

#### InsufficientMemoryError
```python
error = InsufficientMemoryError(
    "시스템 메모리 부족",
    required_mb=16000,
    available_mb=8000,
    memory_type="system"
)

# context: {
#     "required_mb": 16000,
#     "available_mb": 8000,
#     "memory_type": "system"
# }
```

### 4.2 사용자 메시지 매핑

```python
# base.py USER_FRIENDLY_MESSAGES 확장
USER_FRIENDLY_MESSAGES = {
    "CV201": "GPU를 사용할 수 없습니다. CPU 모드로 전환합니다.",
    "CV202": "카메라를 연결할 수 없습니다.",
    "CV901": "메모리가 부족합니다. 일부 기능을 종료해주세요.",
}
```

---

## 5. 메모리 최적화 (Memory Optimization)

### 5.1 메모리 목표
- **예외 인스턴스당**: <1.5KB (base 1KB + 추가 필드 0.5KB)
- **컨텍스트 크기**: <512 bytes (base 클래스 제한 활용)

### 5.2 최적화 기법

#### 5.2.1 불필요한 필드 제외
```python
# gpu_id가 None이면 context에 추가하지 않음
if gpu_id is not None:
    context["gpu_id"] = gpu_id
```

#### 5.2.2 정수 타입 사용
```python
# 메모리 크기는 MB 단위 정수로 저장 (float 대신)
required_memory_mb: Optional[int] = None  # MB 단위
```

---

## 6. 사용 예제 (Usage Examples)

### 6.1 GPUError 사용 예제

```python
from core_foundation.exceptions.hardware import GPUError

# 예제 1: GPU 초기화 실패
try:
    import torch
    if not torch.cuda.is_available():
        raise GPUError("CUDA GPU를 사용할 수 없습니다")
except Exception as e:
    # CPU 모드로 폴백
    print(f"GPU 에러: {e.get_user_message()}")

# 예제 2: GPU 메모리 부족
try:
    model = load_model_to_gpu(gpu_id=0)
except RuntimeError as e:
    if "out of memory" in str(e).lower():
        raise GPUError(
            "GPU 메모리가 부족합니다",
            gpu_id=0,
            required_memory_mb=8000,
            available_memory_mb=4000,
            original_error=e
        )

# 예제 3: 특정 GPU 초기화 실패
def initialize_gpu(gpu_id: int):
    try:
        torch.cuda.set_device(gpu_id)
    except RuntimeError as e:
        raise GPUError(
            f"GPU {gpu_id} 초기화 실패",
            gpu_id=gpu_id,
            original_error=e
        )
```

### 6.2 CameraError 사용 예제

```python
from core_foundation.exceptions.hardware import CameraError

# 예제 1: 카메라 연결 실패
import cv2

def connect_camera(camera_id: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        raise CameraError(
            f"카메라 {camera_id} 연결 실패",
            camera_id=camera_id
        )
    return cap

# 예제 2: 최소 카메라 대수 확인
def validate_camera_count(cameras: list):
    if len(cameras) < 4:
        raise CameraError(
            f"최소 4대의 카메라가 필요합니다 (현재: {len(cameras)}대)",
            context={"required": 4, "actual": len(cameras)}
        )

# 예제 3: 프레임 캡처 실패
def capture_frame(cap: cv2.VideoCapture, camera_id: int):
    ret, frame = cap.read()
    if not ret:
        raise CameraError(
            "프레임 캡처 실패",
            camera_id=camera_id,
            camera_name=f"Camera {camera_id}"
        )
    return frame
```

### 6.3 InsufficientMemoryError 사용 예제

```python
from core_foundation.exceptions.hardware import InsufficientMemoryError
import psutil

# 예제 1: 시스템 메모리 체크
def check_system_memory(required_mb: int):
    available_mb = psutil.virtual_memory().available / (1024 ** 2)
    if available_mb < required_mb:
        raise InsufficientMemoryError(
            "시스템 메모리가 부족합니다",
            required_mb=required_mb,
            available_mb=int(available_mb),
            memory_type="system"
        )

# 예제 2: GPU 메모리 체크
def check_gpu_memory(required_mb: int, gpu_id: int = 0):
    import torch
    if torch.cuda.is_available():
        available_mb = torch.cuda.mem_get_info(gpu_id)[0] / (1024 ** 2)
        if available_mb < required_mb:
            raise InsufficientMemoryError(
                "GPU 메모리가 부족합니다",
                required_mb=required_mb,
                available_mb=int(available_mb),
                memory_type="gpu"
            )

# 예제 3: 대용량 파일 로딩
def load_large_video(file_path: str, max_frames: int = 10000):
    # 프레임당 2MB 예상
    required_mb = max_frames * 2
    check_system_memory(required_mb)

    # 영상 로딩...
    pass
```

---

## 7. 테스트 전략 (Testing Strategy)

### 7.1 단위 테스트 항목

```python
# tests/core_foundation/exceptions/unit/test_hardware.py

class TestGPUError:
    # 기본 기능
    def test_basic_creation()
    def test_with_gpu_id()
    def test_with_memory_info()
    def test_with_all_fields()

    # 컨텍스트
    def test_context_includes_gpu_info()
    def test_context_excludes_none_values()

    # 에러 코드
    def test_error_code_cv201()

    # 사용자 메시지
    def test_user_message()

class TestCameraError:
    # 기본 기능
    def test_basic_creation()
    def test_with_camera_id()
    def test_with_camera_name()
    def test_with_both_fields()

    # 컨텍스트
    def test_context_includes_camera_info()

    # 에러 코드
    def test_error_code_cv202()

class TestInsufficientMemoryError:
    # 기본 기능
    def test_basic_creation()
    def test_with_memory_info()
    def test_with_memory_type()

    # 메모리 타입
    def test_memory_type_system()
    def test_memory_type_gpu()
    def test_memory_type_cache()

    # 에러 코드
    def test_error_code_cv901()
```

### 7.2 성능 테스트 항목

```python
# tests/core_foundation/exceptions/performance/test_hardware_perf.py

def test_gpu_error_creation_time()      # <0.1ms
def test_camera_error_creation_time()   # <0.1ms
def test_memory_error_creation_time()   # <0.1ms
def test_memory_usage()                  # <1.5KB per instance
```

---

## 8. 에러 처리 패턴 (Error Handling Patterns)

### 8.1 GPU 폴백 패턴

```python
try:
    device = initialize_gpu(gpu_id=0)
except GPUError as e:
    logger.warning(f"GPU 초기화 실패: {e}, CPU 모드로 전환")
    device = "cpu"
```

### 8.2 카메라 재시도 패턴

```python
max_retries = 3
for attempt in range(max_retries):
    try:
        camera = connect_camera(camera_id)
        break
    except CameraError as e:
        if attempt == max_retries - 1:
            raise
        logger.warning(f"카메라 연결 재시도 {attempt + 1}/{max_retries}")
        time.sleep(1)
```

### 8.3 메모리 해제 패턴

```python
try:
    large_array = load_large_data()
except InsufficientMemoryError as e:
    logger.error(f"메모리 부족: {e}")
    # 캐시 정리
    clear_cache()
    # 재시도
    large_array = load_large_data()
```

---

## 9. 파일 구조 (File Structure)

```
core_foundation/exceptions/
├── __init__.py
├── base.py ✅
├── validation.py (이전)
└── hardware.py (이 문서)
```

---

## 10. 구현 체크리스트 (Implementation Checklist)

- [ ] GPUError 클래스 구현
  - [ ] `__init__` 메서드 (gpu_id, required_memory_mb, available_memory_mb)
  - [ ] 컨텍스트 자동 추가
  - [ ] 에러 코드 CV201
  - [ ] 독스트링 작성

- [ ] CameraError 클래스 구현
  - [ ] `__init__` 메서드 (camera_id, camera_name)
  - [ ] 컨텍스트 자동 추가
  - [ ] 에러 코드 CV202
  - [ ] 독스트링 작성

- [ ] InsufficientMemoryError 클래스 구현
  - [ ] `__init__` 메서드 (required_mb, available_mb, memory_type)
  - [ ] 컨텍스트 자동 추가
  - [ ] 메모리 타입 검증
  - [ ] 에러 코드 CV901
  - [ ] 독스트링 작성

- [ ] 타입 힌팅 완성
- [ ] 단위 테스트 작성 (20+ tests)
- [ ] 성능 테스트 작성 (4 tests)
- [ ] 메모리 프로파일링 (<1.5KB 검증)

---

## 11. 참고 자료 (References)

### 11.1 관련 문서
- [BASE_DESIGN.md](./BASE_DESIGN.md) - CourtViewError 기본 클래스
- [VALIDATION_DESIGN.md](./VALIDATION_DESIGN.md) - ConfigError, DataValidationError

### 11.2 에러 코드 범위
```
CV201: GPUError (GPU 관련)
CV202: CameraError (카메라 관련)
CV901: InsufficientMemoryError (메모리 부족)
```

---

**작성일**: 2026-02-10
**작성자**: Claude (AI Assistant)
**버전**: 1.0.0
