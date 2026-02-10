# exceptions/validation.py 설계 문서

**파일 경로**: `D:\COURTVIEW_DESK\core_foundation\exceptions\validation.py`
**모듈**: Layer 0 - core_foundation
**목적**: 설정 및 데이터 검증 관련 예외 클래스
**버전**: 1.0.0

---

## 1. 개요 (Overview)

### 1.1 설계 목적
- **설정 검증**: YAML/ENV 설정 파일 로딩 및 검증 관련 예외
- **데이터 검증**: 입력 데이터, API 요청, 파라미터 검증 관련 예외
- **CourtViewError 파생**: 기본 예외 클래스 기능 상속
- **컨텍스트 확장**: 파일명, 필드명, 타입 정보 등 추가

### 1.2 Desktop vs App Server 차이점

| 기능 | App Server | Desktop |
|------|-----------|---------|
| Pydantic 연동 | ✅ ValidationError 변환 | ✅ 동일 |
| 설정 소스 | Consul, ENV, YAML | ENV, YAML만 |
| 검증 범위 | API 요청 + 설정 | 설정 + 로컬 데이터 |
| 에러 세분화 | 10+ 예외 클래스 | 2개 예외 클래스 |

### 1.3 주요 예외 클래스

```python
ConfigError          # CV101~CV103 (설정 파일 관련)
DataValidationError  # CV301~CV303 (데이터 검증 관련)
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
- `pydantic`: 여기서는 직접 의존 X (config/validator.py에서 사용)
- `yaml`, `json`: 파싱은 loader.py에서 수행
- `pathlib`: 경로는 컨텍스트로 전달받음

---

## 3. 클래스 설계 (Class Design)

### 3.1 ConfigError (설정 파일 예외)

```python
class ConfigError(CourtViewError):
    """
    설정 파일 관련 예외

    사용 사례:
    - YAML 파일 없음 (CV101)
    - YAML 파싱 실패 (CV102)
    - 필수 설정값 누락 (CV103)
    - 설정값 타입 불일치 (CV103)

    Attributes:
        ERROR_CODE (str): "CV101" (기본)
        config_file (str): 설정 파일 경로 (context에 저장)
    """

    ERROR_CODE = "CV101"

    def __init__(
        self,
        message: str,
        *,
        config_file: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
```

#### 3.1.1 초기화 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|---------|------|------|------|------|
| `message` | str | ✅ | 에러 메시지 | "YAML 파일을 찾을 수 없습니다" |
| `config_file` | str | ❌ | 설정 파일 경로 | "configs/gpu.yaml" |
| `error_code` | str | ❌ | 에러 코드 오버라이드 | "CV102" |
| `**kwargs` | Any | ❌ | CourtViewError 추가 인자 | context, original_error |

#### 3.1.2 에러 코드 범위

| 코드 | 의미 | 사용 상황 |
|------|------|----------|
| **CV101** | 설정 파일 없음 | FileNotFoundError, 파일 경로 오류 |
| **CV102** | 설정 파일 파싱 실패 | YAMLError, JSON 파싱 에러 |
| **CV103** | 설정값 검증 실패 | 필수 키 누락, 타입 불일치 |

### 3.2 DataValidationError (데이터 검증 예외)

```python
class DataValidationError(CourtViewError):
    """
    데이터 검증 예외

    사용 사례:
    - 입력 데이터 형식 오류 (CV301)
    - 데이터 범위 초과 (CV302)
    - 필수 필드 누락 (CV303)
    - 타입 불일치 (CV301)

    Attributes:
        ERROR_CODE (str): "CV301" (기본)
        field_name (str): 필드 이름 (context에 저장)
        expected_type (str): 기대하는 타입 (context에 저장)
        actual_value (Any): 실제 값 (context에 저장, 100자 제한)
    """

    ERROR_CODE = "CV301"

    def __init__(
        self,
        message: str,
        *,
        field_name: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
```

#### 3.2.1 초기화 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|---------|------|------|------|------|
| `message` | str | ✅ | 에러 메시지 | "GPU ID는 정수여야 합니다" |
| `field_name` | str | ❌ | 필드 이름 | "gpu_id" |
| `expected_type` | str | ❌ | 기대하는 타입 | "int" |
| `actual_value` | Any | ❌ | 실제 값 (100자 제한) | "invalid" |
| `error_code` | str | ❌ | 에러 코드 오버라이드 | "CV302" |
| `**kwargs` | Any | ❌ | CourtViewError 추가 인자 | context, original_error |

#### 3.2.2 에러 코드 범위

| 코드 | 의미 | 사용 상황 |
|------|------|----------|
| **CV301** | 입력 데이터 검증 실패 | 타입 불일치, 형식 오류 |
| **CV302** | 데이터 형식 오류 | 날짜 형식, 이메일 형식 등 |
| **CV303** | 데이터 범위 초과 | 최소/최대값 초과, 길이 제한 |

---

## 4. 주요 기능 (Key Features)

### 4.1 컨텍스트 자동 추가

#### ConfigError
```python
# config_file을 context에 자동 추가
error = ConfigError(
    "YAML 파일을 찾을 수 없습니다",
    config_file="gpu.yaml"
)

# context: {"config_file": "gpu.yaml"}
```

#### DataValidationError
```python
# field_name, expected_type, actual_value를 context에 자동 추가
error = DataValidationError(
    "타입 불일치",
    field_name="gpu_id",
    expected_type="int",
    actual_value="invalid"
)

# context: {
#     "field_name": "gpu_id",
#     "expected_type": "int",
#     "actual_value": "invalid"
# }
```

### 4.2 실제 값 크기 제한

```python
def __init__(self, message: str, *, actual_value: Optional[Any] = None, **kwargs):
    context = kwargs.get("context", {})

    if actual_value is not None:
        # 100자로 제한 (메모리 최적화)
        context["actual_value"] = str(actual_value)[:100]
```

### 4.3 에러 코드 오버라이드

```python
# 클래스 기본 에러 코드 사용
error1 = ConfigError("파일 없음")  # CV101

# 명시적 에러 코드 오버라이드
error2 = ConfigError("파싱 실패", error_code="CV102")  # CV102
```

---

## 5. 메모리 최적화 (Memory Optimization)

### 5.1 메모리 목표
- **예외 인스턴스당**: <1.5KB (base 1KB + 추가 필드 0.5KB)
- **actual_value 제한**: 100 characters
- **컨텍스트 크기**: <512 bytes (base 클래스 제한 활용)

### 5.2 최적화 기법

#### 5.2.1 actual_value 크기 제한
```python
# 100자 초과 시 잘라내기
if actual_value is not None:
    context["actual_value"] = str(actual_value)[:100]
```

#### 5.2.2 불필요한 필드 제외
```python
# config_file이 None이면 context에 추가하지 않음
if config_file:
    context["config_file"] = config_file
```

---

## 6. 사용 예제 (Usage Examples)

### 6.1 ConfigError 사용 예제

```python
from core_foundation.exceptions.validation import ConfigError

# 예제 1: 파일 없음 (CV101)
try:
    open("configs/missing.yaml")
except FileNotFoundError as e:
    raise ConfigError(
        "설정 파일을 찾을 수 없습니다",
        config_file="configs/missing.yaml",
        original_error=e
    )

# 예제 2: 파싱 실패 (CV102)
try:
    yaml.safe_load(bad_yaml_content)
except yaml.YAMLError as e:
    raise ConfigError(
        "YAML 파싱 실패",
        config_file="gpu.yaml",
        error_code="CV102",
        context={"line": 15, "column": 3},
        original_error=e
    )

# 예제 3: 필수 키 누락 (CV103)
config = yaml.safe_load(file)
if "gpu_memory_fraction" not in config:
    raise ConfigError(
        "필수 설정값이 누락되었습니다",
        config_file="gpu.yaml",
        error_code="CV103",
        context={"missing_key": "gpu_memory_fraction"}
    )
```

### 6.2 DataValidationError 사용 예제

```python
from core_foundation.exceptions.validation import DataValidationError

# 예제 1: 타입 불일치 (CV301)
def validate_gpu_id(gpu_id: Any) -> int:
    if not isinstance(gpu_id, int):
        raise DataValidationError(
            "GPU ID는 정수여야 합니다",
            field_name="gpu_id",
            expected_type="int",
            actual_value=gpu_id
        )
    return gpu_id

# 예제 2: 범위 초과 (CV303)
def validate_fps(fps: int) -> int:
    if fps < 1 or fps > 240:
        raise DataValidationError(
            "FPS는 1~240 범위여야 합니다",
            field_name="fps",
            expected_type="int (1~240)",
            actual_value=fps,
            error_code="CV303"
        )
    return fps

# 예제 3: 필수 필드 누락 (CV301)
def validate_config(data: Dict[str, Any]) -> None:
    required_fields = ["gpu_id", "batch_size", "model_path"]
    for field in required_fields:
        if field not in data:
            raise DataValidationError(
                f"필수 필드가 누락되었습니다: {field}",
                field_name=field,
                expected_type="required",
                context={"available_fields": list(data.keys())}
            )
```

### 6.3 loader.py에서 사용 예제

```python
from core_foundation.exceptions.validation import ConfigError

class ConfigLoader:
    def load_yaml(self, file_name: str) -> Dict[str, Any]:
        try:
            file_path = self._validate_path(file_name)

            if not file_path.exists():
                raise ConfigError(
                    f"설정 파일을 찾을 수 없습니다: {file_name}",
                    config_file=file_name,
                    error_code="CV101"
                )

            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            return config

        except yaml.YAMLError as e:
            raise ConfigError(
                f"YAML 파싱 실패: {file_name}",
                config_file=file_name,
                error_code="CV102",
                original_error=e
            )
```

---

## 7. 테스트 전략 (Testing Strategy)

### 7.1 단위 테스트 항목

```python
# tests/core_foundation/exceptions/unit/test_validation.py

class TestConfigError:
    # 기본 기능
    def test_basic_creation()
    def test_with_config_file()
    def test_with_error_code_override()
    def test_with_original_error()

    # 컨텍스트
    def test_context_includes_config_file()
    def test_context_merge_with_additional()

    # 에러 코드
    def test_default_error_code_cv101()
    def test_error_code_cv102()
    def test_error_code_cv103()

    # 사용자 메시지
    def test_user_message()

class TestDataValidationError:
    # 기본 기능
    def test_basic_creation()
    def test_with_field_info()
    def test_with_type_info()
    def test_with_actual_value()

    # 컨텍스트
    def test_context_includes_field_info()
    def test_actual_value_truncation()  # 100자 제한

    # 에러 코드
    def test_default_error_code_cv301()
    def test_error_code_cv302()
    def test_error_code_cv303()

    # Edge Cases
    def test_long_actual_value()  # >100 chars
    def test_none_field_name()
    def test_none_actual_value()
```

### 7.2 성능 테스트 항목

```python
# tests/core_foundation/exceptions/performance/test_validation_perf.py

def test_config_error_creation_time()      # <0.1ms
def test_data_validation_error_creation()  # <0.1ms
def test_memory_usage()                    # <1.5KB per instance
def test_actual_value_truncation_perf()    # <0.01ms
```

---

## 8. 에러 메시지 가이드 (Error Message Guidelines)

### 8.1 ConfigError 메시지 템플릿

```python
# CV101: 파일 없음
"설정 파일을 찾을 수 없습니다: {file_name}"
"'{file_name}' 파일이 존재하지 않습니다"

# CV102: 파싱 실패
"YAML 파싱 실패: {file_name} (라인 {line})"
"설정 파일 형식이 올바르지 않습니다: {file_name}"

# CV103: 검증 실패
"필수 설정값이 누락되었습니다: {key_name}"
"설정값 타입 불일치: {key_name} (기대: {expected}, 실제: {actual})"
```

### 8.2 DataValidationError 메시지 템플릿

```python
# CV301: 입력 데이터 검증 실패
"{field_name}은(는) {expected_type} 타입이어야 합니다"
"필수 필드가 누락되었습니다: {field_name}"

# CV302: 데이터 형식 오류
"날짜 형식이 올바르지 않습니다: {field_name}"
"이메일 형식이 올바르지 않습니다: {field_name}"

# CV303: 데이터 범위 초과
"{field_name}은(는) {min}~{max} 범위여야 합니다 (실제: {actual})"
"문자열 길이가 제한을 초과했습니다: {field_name} (최대: {max})"
```

---

## 9. 파일 구조 (File Structure)

```
core_foundation/exceptions/
├── __init__.py
├── base.py ✅
├── validation.py (이 문서)
└── hardware.py (다음)
```

---

## 10. 구현 체크리스트 (Implementation Checklist)

- [ ] ConfigError 클래스 구현
  - [ ] `__init__` 메서드 (config_file 파라미터)
  - [ ] 컨텍스트 자동 추가
  - [ ] 에러 코드 CV101~CV103
  - [ ] 독스트링 작성

- [ ] DataValidationError 클래스 구현
  - [ ] `__init__` 메서드 (field_name, expected_type, actual_value)
  - [ ] 컨텍스트 자동 추가
  - [ ] actual_value 크기 제한 (100자)
  - [ ] 에러 코드 CV301~CV303
  - [ ] 독스트링 작성

- [ ] 타입 힌팅 완성
- [ ] 단위 테스트 작성 (20+ tests)
- [ ] 성능 테스트 작성 (4 tests)
- [ ] 메모리 프로파일링 (<1.5KB 검증)

---

## 11. 참고 자료 (References)

### 11.1 관련 문서
- [BASE_DESIGN.md](./BASE_DESIGN.md) - CourtViewError 기본 클래스
- [LOADER_DESIGN.md](../config/LOADER_DESIGN.md) - ConfigLoader에서 ConfigError 사용

### 11.2 에러 코드 범위
```
CV101~CV103: ConfigError (설정 파일)
CV301~CV303: DataValidationError (데이터 검증)
```

---

**작성일**: 2026-02-10
**작성자**: Claude (AI Assistant)
**버전**: 1.0.0
