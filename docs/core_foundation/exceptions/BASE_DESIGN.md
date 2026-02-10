# exceptions/base.py 설계 문서

**파일 경로**: `D:\COURTVIEW_DESK\core_foundation\exceptions\base.py`
**모듈**: Layer 0 - core_foundation
**목적**: COURTVIEW Desktop 전용 예외 계층 루트 클래스
**버전**: 1.0.0

---

## 1. 개요 (Overview)

### 1.1 설계 목적
- **계층적 예외 구조**: 모든 COURTVIEW 예외의 공통 부모 클래스
- **컨텍스트 보존**: 에러 발생 시점의 상태 정보 저장
- **에러 코드 시스템**: 구조화된 에러 코드로 디버깅 지원
- **Desktop 최적화**: 메모리 효율성 및 로컬 실행 최적화
- **프로덕션 안정성**: 상세한 에러 정보 + 사용자 친화적 메시지

### 1.2 Desktop vs App Server 차이점

| 기능 | App Server | Desktop |
|------|-----------|---------|
| 에러 추적 | Sentry 연동 | 로컬 로그 파일만 |
| 재시도 메커니즘 | resilience layer | 직접 구현 (필요시) |
| 알림 | Slack/Email | 로컬 알림만 |
| 컨텍스트 크기 | 무제한 | <1KB per exception |
| 에러 코드 | 6자리 (CV-L0-001) | 5자리 (CV001) |

### 1.3 주요 설계 원칙
1. **단순성**: 외부 의존성 없음 (Python 표준 라이브러리만)
2. **메모리 효율**: 컨텍스트 정보 최소화 (<1KB)
3. **타입 안전성**: Full type hints (Python 3.8+)
4. **확장성**: 계층 구조로 특수 예외 파생 가능
5. **디버깅 친화적**: 에러 코드 + 컨텍스트 + 스택 트레이스

---

## 2. 임포트 정의 (Import Definitions)

### 2.1 Direct Imports (외부 의존성 없음)
```python
from typing import Dict, Any, Optional
from datetime import datetime
import traceback
import sys
```

**사용 모듈**:
- `typing`: 타입 힌팅 (Dict, Any, Optional)
- `datetime`: 에러 발생 타임스탬프
- `traceback`: 스택 트레이스 캡처
- `sys`: Python 버전 정보, 플랫폼 정보

### 2.2 의존성 없음 (Desktop 최적화)
❌ 사용하지 않는 것들:
- `sentry_sdk`: App Server 전용 (에러 추적 서비스)
- `loguru`: monitoring/logger.py에서 사용 (여기서는 직접 의존 X)
- `pydantic`: 검증은 validation.py에서 처리
- `requests`, `redis`, `celery`: App Server 전용

---

## 3. 클래스 설계 (Class Design)

### 3.1 CourtViewError (기본 예외 클래스)

```python
class CourtViewError(Exception):
    """
    COURTVIEW Desktop 전용 기본 예외 클래스

    모든 COURTVIEW 예외의 루트 클래스
    - 에러 코드 시스템
    - 컨텍스트 정보 저장
    - 타임스탬프 기록
    - 스택 트레이스 캡처
    """

    # 클래스 변수
    ERROR_CODE: str = "CV000"  # 기본 에러 코드 (파생 클래스에서 재정의)

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """
        Args:
            message: 사용자 친화적 에러 메시지
            error_code: 5자리 에러 코드 (CV001~CV999)
            context: 에러 발생 시점의 상태 정보 (<1KB)
            original_error: 원본 예외 (체이닝용)
        """
```

### 3.2 주요 속성 (Attributes)

| 속성 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `message` | str | 사용자 친화적 메시지 | "YAML 파일을 찾을 수 없습니다" |
| `error_code` | str | 5자리 에러 코드 | "CV101" |
| `context` | Dict | 에러 컨텍스트 (<1KB) | `{"file": "gpu.yaml", "layer": "L0"}` |
| `original_error` | Exception | 원본 예외 | `FileNotFoundError(...)` |
| `timestamp` | datetime | 에러 발생 시각 | `2025-01-15 14:23:45` |
| `stack_trace` | str | 스택 트레이스 | `Traceback (most recent call last)...` |
| `platform_info` | Dict | 실행 환경 정보 | `{"os": "Windows", "python": "3.8.10"}` |

### 3.3 주요 메서드 (Methods)

#### 3.3.1 Public Methods (4개)

```python
def __str__(self) -> str:
    """
    에러 메시지 포맷팅

    Returns:
        "[CV101] YAML 파일을 찾을 수 없습니다"
    """

def __repr__(self) -> str:
    """
    개발자용 상세 정보

    Returns:
        "CourtViewError(error_code='CV101', message='...', context={...})"
    """

def to_dict(self) -> Dict[str, Any]:
    """
    딕셔너리로 직렬화 (로깅, API 응답용)

    Returns:
        {
            "error_code": "CV101",
            "message": "...",
            "context": {...},
            "timestamp": "2025-01-15T14:23:45",
            "stack_trace": "...",
            "platform_info": {...}
        }
    """

def get_user_message(self) -> str:
    """
    사용자에게 표시할 간단한 메시지 (기술 정보 제외)

    Returns:
        "파일을 찾을 수 없습니다. 설정을 확인해주세요."
    """
```

#### 3.3.2 Private Methods (2개)

```python
def _capture_stack_trace(self) -> str:
    """
    현재 스택 트레이스 캡처

    Returns:
        "Traceback (most recent call last):\n  File ..."
    """

def _get_platform_info(self) -> Dict[str, str]:
    """
    실행 환경 정보 수집

    Returns:
        {
            "os": "Windows",
            "python_version": "3.8.10",
            "architecture": "64bit"
        }
    """
```

---

## 4. 에러 코드 시스템 (Error Code System)

### 4.1 에러 코드 구조
```
CV[Category][Number]
└─ CV: COURTVIEW 접두사
   └─ Category: 에러 범주 (0~9)
      └─ Number: 순차 번호 (00~99)
```

### 4.2 에러 코드 범위

| 범위 | 카테고리 | 담당 모듈 | 예시 |
|------|---------|----------|------|
| CV000 | 기본 에러 | base.py | CV000 (Generic Error) |
| CV1XX | 설정 에러 | validation.py | CV101 (Config Not Found) |
| CV2XX | 하드웨어 에러 | hardware.py | CV201 (GPU Error) |
| CV3XX | 데이터 검증 에러 | validation.py | CV301 (Invalid Input) |
| CV4XX | 파일 시스템 에러 | base.py | CV401 (File Access Denied) |
| CV5XX | 네트워크 에러 | (Desktop 미사용) | - |
| CV6XX | 데이터베이스 에러 | (Desktop 미사용) | - |
| CV7XX | 모델 추론 에러 | (Layer 3+) | CV701 (Model Load Failed) |
| CV8XX | 파이프라인 에러 | (Layer 6+) | CV801 (Pipeline Failed) |
| CV9XX | 시스템 에러 | base.py | CV901 (Out of Memory) |

### 4.3 에러 코드 예시

```python
# core_foundation/exceptions/base.py
class CourtViewError(Exception):
    ERROR_CODE = "CV000"  # 기본 에러

# core_foundation/exceptions/validation.py
class ConfigError(CourtViewError):
    ERROR_CODE = "CV101"  # 설정 파일 에러

class DataValidationError(CourtViewError):
    ERROR_CODE = "CV301"  # 데이터 검증 에러

# core_foundation/exceptions/hardware.py
class GPUError(CourtViewError):
    ERROR_CODE = "CV201"  # GPU 에러

class InsufficientMemoryError(CourtViewError):
    ERROR_CODE = "CV901"  # 메모리 부족
```

---

## 5. 메모리 최적화 (Memory Optimization)

### 5.1 메모리 목표
- **예외 인스턴스당**: <1KB
- **컨텍스트 정보**: <512 bytes
- **스택 트레이스**: <500 bytes (최대 10 프레임)

### 5.2 최적화 기법

#### 5.2.1 컨텍스트 크기 제한
```python
def __init__(self, message: str, *, context: Optional[Dict[str, Any]] = None, ...):
    # 컨텍스트 크기 검증 (<512 bytes)
    if context:
        context_size = len(str(context).encode('utf-8'))
        if context_size > 512:
            # 큰 값은 요약으로 대체
            self.context = self._truncate_context(context)
        else:
            self.context = context
```

#### 5.2.2 스택 트레이스 제한
```python
def _capture_stack_trace(self) -> str:
    # 최대 10 프레임만 캡처
    tb = traceback.format_exc(limit=10)

    # 500 bytes 초과 시 잘라내기
    if len(tb) > 500:
        tb = tb[:497] + "..."

    return tb
```

#### 5.2.3 플랫폼 정보 캐싱
```python
# 클래스 변수로 캐싱 (모든 인스턴스 공유)
_PLATFORM_INFO_CACHE: Optional[Dict[str, str]] = None

def _get_platform_info(self) -> Dict[str, str]:
    if CourtViewError._PLATFORM_INFO_CACHE is None:
        CourtViewError._PLATFORM_INFO_CACHE = {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "architecture": platform.machine()
        }
    return CourtViewError._PLATFORM_INFO_CACHE
```

### 5.3 메모리 프로파일링 결과 (목표)

| 컴포넌트 | 크기 | 비율 |
|---------|------|------|
| message (str) | ~100 bytes | 10% |
| error_code (str) | ~10 bytes | 1% |
| context (Dict) | ~400 bytes | 40% |
| stack_trace (str) | ~400 bytes | 40% |
| timestamp (datetime) | ~48 bytes | 5% |
| platform_info (Dict, cached) | ~40 bytes | 4% |
| **총합** | **~1KB** | **100%** |

---

## 6. 보안성 (Security)

### 6.1 보안 위협 분석

| 위협 | 설명 | 대응 방법 |
|------|------|----------|
| 민감 정보 노출 | 에러 메시지에 비밀번호, API 키 포함 가능 | context에서 필터링 |
| 스택 트레이스 공격 | 내부 구조 노출 | 프로덕션에서 간소화 |
| 에러 기반 정보 수집 | 에러 메시지로 시스템 구조 파악 | 사용자 메시지 단순화 |
| 메모리 덤프 | 예외 객체에 민감 정보 저장 | 컨텍스트 크기 제한 |

### 6.2 보안 기능 구현

#### 6.2.1 민감 정보 필터링
```python
# 필터링할 키 목록
SENSITIVE_KEYS = {
    "password", "passwd", "pwd",
    "api_key", "apikey", "secret",
    "token", "access_token", "refresh_token",
    "credential", "auth", "authorization"
}

def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """컨텍스트에서 민감 정보 제거"""
    sanitized = {}
    for key, value in context.items():
        if key.lower() in self.SENSITIVE_KEYS:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = self._sanitize_context(value)
        else:
            sanitized[key] = value
    return sanitized
```

#### 6.2.2 사용자 메시지 vs 개발자 메시지 분리
```python
def get_user_message(self) -> str:
    """사용자에게 표시할 간단한 메시지 (기술 정보 제외)"""
    user_friendly_messages = {
        "CV101": "설정 파일을 찾을 수 없습니다.",
        "CV201": "GPU를 사용할 수 없습니다. CPU 모드로 전환합니다.",
        "CV301": "입력 데이터가 올바르지 않습니다.",
        "CV901": "메모리가 부족합니다. 일부 기능을 종료해주세요.",
    }
    return user_friendly_messages.get(self.error_code, "오류가 발생했습니다.")

def __str__(self) -> str:
    """개발자용 상세 메시지"""
    return f"[{self.error_code}] {self.message}"
```

#### 6.2.3 프로덕션 모드 스택 트레이스 단순화
```python
def _capture_stack_trace(self, production_mode: bool = False) -> str:
    if production_mode:
        # 프로덕션: 최상위 3 프레임만
        return traceback.format_exc(limit=3)
    else:
        # 개발: 전체 10 프레임
        return traceback.format_exc(limit=10)
```

---

## 7. 성능 목표 (Performance Targets)

### 7.1 성능 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 예외 생성 시간 | <0.1ms | `timeit` |
| 메모리 사용량 | <1KB per instance | `sys.getsizeof()` |
| 직렬화 시간 | <0.05ms | `to_dict()` 호출 시간 |
| 스택 트레이스 캡처 | <0.03ms | `traceback.format_exc()` |

### 7.2 벤치마크 목표

```python
# 10,000개 예외 생성 성능
target_metrics = {
    "creation_time": "<1 second",      # 평균 0.1ms per exception
    "total_memory": "<10MB",           # 평균 1KB per exception
    "serialization_time": "<0.5 sec",  # 평균 0.05ms per to_dict()
}
```

### 7.3 최적화 체크리스트
- [x] 플랫폼 정보 캐싱 (클래스 변수)
- [x] 컨텍스트 크기 제한 (<512 bytes)
- [x] 스택 트레이스 프레임 제한 (10 frames)
- [x] 민감 정보 필터링 (lazy evaluation)
- [x] `__slots__` 사용 고려 (메모리 절약)

---

## 8. 사용 예제 (Usage Examples)

### 8.1 기본 사용법

```python
from core_foundation.exceptions import CourtViewError

# 기본 예외 발생
raise CourtViewError("파일을 찾을 수 없습니다")

# 에러 코드 + 컨텍스트 포함
raise CourtViewError(
    "GPU 메모리가 부족합니다",
    error_code="CV201",
    context={"required_mb": 8000, "available_mb": 4000}
)

# 원본 예외 체이닝
try:
    open("missing.yaml")
except FileNotFoundError as e:
    raise CourtViewError(
        "설정 파일을 읽을 수 없습니다",
        error_code="CV101",
        context={"file": "missing.yaml"},
        original_error=e
    ) from e
```

### 8.2 커스텀 예외 파생

```python
# validation.py
class ConfigError(CourtViewError):
    """설정 파일 관련 예외"""
    ERROR_CODE = "CV101"

    def __init__(self, message: str, *, config_file: str, **kwargs):
        super().__init__(
            message,
            error_code=self.ERROR_CODE,
            context={"config_file": config_file, **kwargs.get("context", {})},
            **kwargs
        )

# 사용
raise ConfigError(
    "YAML 파싱 실패",
    config_file="gpu.yaml",
    context={"line": 15, "column": 3}
)
```

### 8.3 에러 핸들링 + 로깅

```python
from core_foundation.exceptions import CourtViewError
from core_foundation.monitoring import setup_logger

logger = setup_logger(__name__)

try:
    # 위험한 작업
    risky_operation()
except CourtViewError as e:
    # 로깅
    logger.error(f"에러 발생: {e}")
    logger.debug(f"컨텍스트: {e.context}")
    logger.debug(f"스택 트레이스:\n{e.stack_trace}")

    # 사용자 메시지 표시
    print(f"오류: {e.get_user_message()}")

    # API 응답 (직렬화)
    return {"error": e.to_dict()}, 500
```

### 8.4 파생 예외 계층 구조

```python
# base.py
class CourtViewError(Exception):
    ERROR_CODE = "CV000"

# validation.py
class ConfigError(CourtViewError):
    ERROR_CODE = "CV101"

class DataValidationError(CourtViewError):
    ERROR_CODE = "CV301"

# hardware.py
class GPUError(CourtViewError):
    ERROR_CODE = "CV201"

class CameraError(CourtViewError):
    ERROR_CODE = "CV202"

class InsufficientMemoryError(CourtViewError):
    ERROR_CODE = "CV901"

# 사용: 특정 예외만 캐치
try:
    load_model_to_gpu()
except GPUError as e:
    logger.warning(f"GPU 사용 불가: {e}, CPU로 폴백")
    load_model_to_cpu()
except InsufficientMemoryError as e:
    logger.error(f"메모리 부족: {e}")
    raise  # 재발생
except CourtViewError as e:
    logger.error(f"알 수 없는 COURTVIEW 에러: {e}")
    raise
```

---

## 9. 파일 구조 (File Structure)

```
core_foundation/exceptions/
├── __init__.py              # 예외 클래스 export
├── base.py                  # CourtViewError (이 문서)
├── validation.py            # ConfigError, DataValidationError
└── hardware.py              # GPUError, CameraError, InsufficientMemoryError
```

### __init__.py 예상 내용
```python
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
```

---

## 10. 테스트 전략 (Testing Strategy)

### 10.1 단위 테스트 항목

```python
# tests/core_foundation/exceptions/unit/test_base.py

class TestCourtViewError:
    # 기본 기능
    def test_basic_exception_creation()
    def test_exception_with_error_code()
    def test_exception_with_context()
    def test_exception_with_original_error()

    # 메시지 포맷팅
    def test_str_representation()
    def test_repr_representation()
    def test_user_message()

    # 직렬화
    def test_to_dict()
    def test_to_dict_with_all_fields()

    # 보안
    def test_sensitive_context_filtering()
    def test_context_size_limit()

    # 메모리
    def test_memory_footprint()
    def test_platform_info_caching()

    # 스택 트레이스
    def test_stack_trace_capture()
    def test_stack_trace_limit()

    # 에러 체이닝
    def test_exception_chaining()
    def test_original_error_preserved()
```

### 10.2 성능 테스트 항목

```python
# tests/core_foundation/exceptions/performance/test_base_perf.py

class TestCourtViewErrorPerformance:
    def test_creation_time()          # <0.1ms
    def test_memory_usage()            # <1KB
    def test_serialization_time()      # <0.05ms
    def test_bulk_creation_10k()       # <1 second
    def test_platform_info_cache_hit() # <0.001ms
```

---

## 11. 의존성 그래프 (Dependency Graph)

```
CourtViewError (base.py)
    ↑
    ├── ConfigError (validation.py)
    ├── DataValidationError (validation.py)
    ├── GPUError (hardware.py)
    ├── CameraError (hardware.py)
    └── InsufficientMemoryError (hardware.py)
```

**외부 의존성**: 없음 (Python 표준 라이브러리만)

---

## 12. 구현 체크리스트 (Implementation Checklist)

- [ ] CourtViewError 클래스 구현
- [ ] 에러 코드 시스템 구현
- [ ] 컨텍스트 저장 + 크기 제한
- [ ] 스택 트레이스 캡처 + 프레임 제한
- [ ] 플랫폼 정보 캐싱
- [ ] 민감 정보 필터링
- [ ] `__str__`, `__repr__` 구현
- [ ] `to_dict()` 직렬화 구현
- [ ] `get_user_message()` 구현
- [ ] 타입 힌팅 완성
- [ ] 독스트링 작성
- [ ] 단위 테스트 작성 (20+ tests)
- [ ] 성능 테스트 작성 (5 tests)
- [ ] 메모리 프로파일링 (<1KB 검증)

---

## 13. 참고 자료 (References)

### 13.1 관련 문서
- [ARCHITECTURE_DESKTOP.md](../../../ARCHITECTURE_DESKTOP.md) - Layer 0 구조
- [LAYER0_CORE_FOUNDATION.md](../../../LAYER0_CORE_FOUNDATION.md) - core_foundation 개요
- [LOADER_DESIGN.md](../config/LOADER_DESIGN.md) - ConfigLoader 설계 (참조 패턴)

### 13.2 Python 문서
- [Built-in Exceptions](https://docs.python.org/3/library/exceptions.html)
- [traceback module](https://docs.python.org/3/library/traceback.html)
- [Exception Chaining (PEP 3134)](https://www.python.org/dev/peps/pep-3134/)

### 13.3 모범 사례
- [Google Python Style Guide - Exceptions](https://google.github.io/styleguide/pyguide.html#24-exceptions)
- [PEP 8 - Exception Names](https://www.python.org/dev/peps/pep-0008/#exception-names)

---

**작성일**: 2025-01-15
**작성자**: Claude (AI Assistant)
**버전**: 1.0.0
