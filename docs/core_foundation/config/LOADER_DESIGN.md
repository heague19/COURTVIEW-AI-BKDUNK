# ConfigLoader 설계 문서

> **파일**: `core_foundation/config/loader.py`
> **버전**: 1.0.0
> **작성일**: 2026-02-10
> **목적**: YAML/ENV 설정 파일 로딩 및 검증 (Desktop 로컬 최적화)

---

## 📋 목차

1. [개요](#1-개요)
2. [임포트 정의](#2-임포트-정의)
3. [클래스 설계](#3-클래스-설계)
4. [주요 기능](#4-주요-기능)
5. [메모리 최적화](#5-메모리-최적화)
6. [안정성](#6-안정성)
7. [보안성](#7-보안성)
8. [성능 목표](#8-성능-목표)
9. [테스트 전략](#9-테스트-전략)
10. [사용 예시](#10-사용-예시)

---

## 1. 개요

### 1.1 목적

**ConfigLoader**는 Desktop Edition의 설정 관리 핵심 컴포넌트로, 다음을 담당:

1. **YAML 설정 파일** 로딩 (`configs/**/*.yaml`)
2. **환경 변수** 로딩 및 오버라이드 (`.env`)
3. **설정 병합** (기본값 + 환경별 + 환경변수)
4. **캐싱** (중복 로딩 방지)
5. **파일 감시** (개발 모드에서 변경 감지)

### 1.2 App Server와의 차이

| 항목 | App Server | Desktop |
|------|-----------|---------|
| **설정 소스** | Consul, Vault, YAML, ENV | YAML, ENV만 |
| **동적 reload** | watchdog 기반 무중단 갱신 | 재시작 필요 (개발 모드만 감시) |
| **분산 설정** | 여러 서버 간 동기화 | 로컬 파일만 |
| **복잡도** | ~500줄 | ~200줄 (60% 감소) |

---

## 2. 임포트 정의

### 2.1 표준 라이브러리 (Direct Import)

```python
from pathlib import Path
from typing import Any, Dict, Optional, Union
import os
```

**이유**: 표준 라이브러리는 상태 없고 교체 불가능 → Direct Import

### 2.2 외부 라이브러리 (Direct Import)

```python
import yaml  # PyYAML
from dotenv import load_dotenv
```

**이유**:
- `yaml`: 순수 함수형 라이브러리 (파싱만)
- `dotenv`: 환경 변수 로딩만

### 2.3 내부 모듈 (Direct Import)

```python
from core_foundation.exceptions.base import CourtViewError
from core_foundation.exceptions.validation import ConfigError
```

**이유**:
- `exceptions`: 같은 core_foundation 레이어, 상태 없음
- 순환 참조 없음 (exceptions는 다른 모듈에 의존 안함)

### 2.4 임포트 금지 항목

```python
# ❌ 금지: 상위 레이어 임포트
from shared.constants import ...  # shared는 core_foundation 위
from configs.base import ...      # configs는 Layer 0.5

# ❌ 금지: 동적 import (보안 위험)
importlib.import_module(user_input)

# ❌ 금지: 외부 설정 서비스
import consul  # App Server 전용
import hvac   # Vault (App Server 전용)
```

---

## 3. 클래스 설계

### 3.1 클래스 구조

```python
class ConfigLoader:
    """
    YAML/ENV 설정 로더 (Desktop 로컬 최적화)

    특징:
    - 캐싱: 동일 파일 중복 로딩 방지
    - 병합: 기본값 + 환경별 + 환경변수 오버라이드
    - 검증: YAML 파싱 에러, 필수 키 누락 감지
    - 보안: 경로 이스케이프 방지, 안전한 YAML 로딩

    메모리 사용량: <1MB (캐시 포함)
    """

    def __init__(
        self,
        config_dir: Path = Path("./configs"),
        env_file: Path = Path(".env"),
        cache_enabled: bool = True,
        validate: bool = True
    ):
        """
        초기화

        Args:
            config_dir: YAML 설정 파일 디렉토리 (기본: ./configs)
            env_file: 환경 변수 파일 (기본: .env)
            cache_enabled: 캐싱 활성화 (기본: True)
            validate: 파일 존재 및 포맷 검증 (기본: True)
        """
        ...
```

### 3.2 속성 (Attributes)

```python
# 공개 속성 (Public)
config_dir: Path          # YAML 디렉토리
env_file: Path            # .env 파일 경로
cache_enabled: bool       # 캐싱 활성화 여부

# 비공개 속성 (Private)
_cache: Dict[str, Dict[str, Any]]  # 파일별 캐시
_env_vars: Dict[str, str]          # 환경 변수 저장소
_loaded: bool                      # .env 로딩 완료 플래그
```

### 3.3 메서드 (Methods)

| 메서드 | 가시성 | 목적 | 성능 |
|--------|--------|------|------|
| `__init__()` | Public | 초기화 | O(1) |
| `load_yaml()` | Public | YAML 파일 로드 | O(n) - 파일 크기 |
| `load_env()` | Public | .env 로드 | O(n) - 줄 수 |
| `get()` | Public | 설정 값 조회 (경로 지원) | O(d) - 깊이 |
| `merge_configs()` | Public | 설정 병합 | O(n) - 키 개수 |
| `_parse_yaml()` | Private | YAML 파싱 (안전) | O(n) |
| `_validate_path()` | Private | 경로 검증 (보안) | O(1) |
| `_get_nested()` | Private | 중첩 키 조회 | O(d) |

---

## 4. 주요 기능

### 4.1 YAML 로딩 (캐싱 포함)

```python
def load_yaml(self, file_name: str) -> Dict[str, Any]:
    """
    YAML 파일 로드 (캐싱 지원)

    Args:
        file_name: YAML 파일명 (예: "detection/ball.yaml")

    Returns:
        Dict[str, Any]: 파싱된 설정 딕셔너리

    Raises:
        ConfigError: 파일 없음, 파싱 실패

    성능:
    - 캐시 히트: O(1) - dict 조회만
    - 캐시 미스: O(n) - 파일 읽기 + 파싱

    메모리:
    - 캐시당 ~10KB (평균 YAML 크기)
    - 최대 50개 파일 캐시 → ~500KB
    """
    # Step 1: 캐시 확인
    if self.cache_enabled and file_name in self._cache:
        return self._cache[file_name].copy()  # 복사본 반환 (원본 보호)

    # Step 2: 경로 검증 (보안)
    file_path = self._validate_path(file_name)

    # Step 3: 파일 존재 확인
    if not file_path.exists():
        raise ConfigError(f"Config file not found: {file_path}")

    # Step 4: YAML 파싱 (안전 모드)
    try:
        config = self._parse_yaml(file_path)
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parsing error in {file_name}: {e}")

    # Step 5: 캐시 저장
    if self.cache_enabled:
        self._cache[file_name] = config

    return config.copy()
```

### 4.2 환경 변수 로딩

```python
def load_env(self, override: bool = True) -> Dict[str, str]:
    """
    .env 파일 로드 및 환경 변수 설정

    Args:
        override: 기존 환경 변수 덮어쓰기 (기본: True)

    Returns:
        Dict[str, str]: 로드된 환경 변수

    동작:
    1. .env 파일 파싱
    2. os.environ에 설정 (override=True)
    3. 내부 저장소에도 저장 (조회용)

    보안:
    - .env 파일 권한 확인 (644 이상은 경고)
    - 민감 변수 로깅 금지
    """
    if self._loaded and not override:
        return self._env_vars.copy()

    # .env 로드
    if self.env_file.exists():
        load_dotenv(self.env_file, override=override)

    # 환경 변수 저장 (조회용)
    self._env_vars = dict(os.environ)
    self._loaded = True

    return self._env_vars.copy()
```

### 4.3 설정 병합 (우선순위)

```python
def merge_configs(
    self,
    base_config: Dict[str, Any],
    env_config: Optional[Dict[str, Any]] = None,
    env_override: bool = True
) -> Dict[str, Any]:
    """
    설정 병합 (우선순위: ENV > env_config > base_config)

    Args:
        base_config: 기본 설정 (낮은 우선순위)
        env_config: 환경별 설정 (중간 우선순위)
        env_override: 환경 변수로 오버라이드 (높은 우선순위)

    Returns:
        Dict[str, Any]: 병합된 설정

    예시:
        base = {"port": 8000, "debug": false}
        env = {"debug": true}
        ENV = {"PORT": "9000"}

        결과 = {"port": 9000, "debug": true}
              (ENV > env > base)

    병합 규칙:
    - 중첩 dict: 재귀적 병합
    - list: 덮어쓰기 (병합 안함)
    - scalar: 덮어쓰기
    """
    result = base_config.copy()

    # Step 1: env_config 병합
    if env_config:
        result = self._deep_merge(result, env_config)

    # Step 2: 환경 변수 오버라이드
    if env_override:
        result = self._apply_env_override(result)

    return result
```

### 4.4 중첩 키 조회 (점 표기법)

```python
def get(
    self,
    key_path: str,
    config: Optional[Dict[str, Any]] = None,
    default: Any = None
) -> Any:
    """
    점 표기법으로 중첩 설정 조회

    Args:
        key_path: "detection.ball.confidence_threshold"
        config: 설정 딕셔너리 (None이면 전체 설정)
        default: 기본값 (키 없을 때)

    Returns:
        Any: 설정 값 또는 기본값

    예시:
        config = {
            "detection": {
                "ball": {
                    "confidence_threshold": 0.75
                }
            }
        }

        get("detection.ball.confidence_threshold")  # → 0.75
        get("detection.ball.min_size", default=10)  # → 10
    """
    if config is None:
        config = self.load_yaml("base/app.yaml")

    return self._get_nested(config, key_path.split('.'), default)
```

---

## 5. 메모리 최적화

### 5.1 캐싱 전략

```python
# 설정: 최대 50개 파일 캐싱 (LRU 없음 - Desktop은 파일 수 적음)
MAX_CACHE_SIZE = 50  # 약 500KB (파일당 10KB)

# 캐시 클리어 (필요시)
def clear_cache(self, pattern: Optional[str] = None):
    """
    캐시 클리어

    Args:
        pattern: 파일명 패턴 (예: "detection/*") - None이면 전체

    메모리 해제: O(n)
    """
    if pattern is None:
        self._cache.clear()
    else:
        keys_to_delete = [k for k in self._cache.keys() if fnmatch(k, pattern)]
        for k in keys_to_delete:
            del self._cache[k]
```

### 5.2 얕은 복사 vs 깊은 복사

```python
# ❌ 비효율: 깊은 복사 (재귀적, 느림)
return copy.deepcopy(config)  # 중첩 dict까지 모두 복사

# ✅ 효율적: 얕은 복사 (1-level만)
return config.copy()  # top-level만 복사, 중첩 dict는 참조

# 사용자가 중첩 dict 수정 시 원본 영향 → 문제 없음
# 이유: ConfigLoader는 읽기 전용 (설정 파일은 수정 안함)
```

### 5.3 환경 변수 저장소

```python
# ❌ 비효율: 모든 환경 변수 저장
self._env_vars = dict(os.environ)  # 수백 개 변수 (시스템 포함)

# ✅ 효율적: COURTVIEW 관련만 필터링
self._env_vars = {
    k: v for k, v in os.environ.items()
    if k.startswith(('COURTVIEW_', 'SERVER_', 'GPU_', 'CUDA_'))
}
```

---

## 6. 안정성

### 6.1 에러 처리 (Fail-Fast)

```python
# 파일 없음 → 즉시 예외 (복구 불가)
if not file_path.exists():
    raise ConfigError(f"Config file not found: {file_path}")

# YAML 파싱 실패 → 즉시 예외 (복구 불가)
try:
    config = yaml.safe_load(file)
except yaml.YAMLError as e:
    raise ConfigError(f"Invalid YAML syntax: {e}")

# 환경 변수 누락 → 기본값 또는 예외 (설정에 따라)
def require_env(self, key: str) -> str:
    """필수 환경 변수 (없으면 예외)"""
    value = os.getenv(key)
    if value is None:
        raise ConfigError(f"Required environment variable missing: {key}")
    return value
```

### 6.2 검증 (Validation)

```python
# YAML 스키마 검증 (선택적)
def validate_schema(self, config: Dict, schema: Dict) -> bool:
    """
    설정 스키마 검증 (간단한 타입 체크)

    예시:
        schema = {
            "port": int,
            "debug": bool,
            "gpu_memory_fraction": float
        }
    """
    for key, expected_type in schema.items():
        if key not in config:
            raise ConfigError(f"Missing required key: {key}")

        if not isinstance(config[key], expected_type):
            raise ConfigError(
                f"Invalid type for {key}: "
                f"expected {expected_type.__name__}, "
                f"got {type(config[key]).__name__}"
            )

    return True
```

### 6.3 기본값 처리

```python
# 환경 변수 기본값
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PORT = int(os.getenv("SERVER_PORT", "8000"))
GPU_FRACTION = float(os.getenv("GPU_MEMORY_FRACTION", "0.9"))

# YAML 기본값 (파일 없을 때)
DEFAULT_CONFIG = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "gpu": {"memory_fraction": 0.9, "device": "0"}
}
```

---

## 7. 보안성

### 7.1 경로 이스케이프 방지 (Path Traversal)

```python
def _validate_path(self, file_name: str) -> Path:
    """
    경로 검증 (보안)

    방어:
    - 상위 디렉토리 이동 방지 (../)
    - 절대 경로 금지
    - configs/ 디렉토리 외부 접근 금지
    """
    # 상대 경로만 허용
    if file_name.startswith('/') or file_name.startswith('\\'):
        raise ConfigError(f"Absolute path not allowed: {file_name}")

    # .. 금지
    if '..' in file_name:
        raise ConfigError(f"Path traversal not allowed: {file_name}")

    # 정규화된 경로 확인
    file_path = (self.config_dir / file_name).resolve()
    config_dir_resolved = self.config_dir.resolve()

    if not str(file_path).startswith(str(config_dir_resolved)):
        raise ConfigError(f"Access outside config directory: {file_name}")

    return file_path
```

### 7.2 안전한 YAML 로딩

```python
def _parse_yaml(self, file_path: Path) -> Dict[str, Any]:
    """
    안전한 YAML 파싱

    사용: yaml.safe_load (unsafe 금지)
    이유: 임의 Python 객체 실행 방지
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        # ✅ 안전: safe_load (기본 타입만)
        return yaml.safe_load(f) or {}

    # ❌ 금지: yaml.load (임의 코드 실행 가능)
    # return yaml.load(f, Loader=yaml.Loader)  # 위험!
```

### 7.3 민감 정보 로깅 금지

```python
# 로깅 시 민감 키 마스킹
SENSITIVE_KEYS = {'password', 'api_key', 'secret', 'token'}

def _safe_log(self, config: Dict[str, Any]) -> Dict[str, Any]:
    """민감 정보 마스킹"""
    return {
        k: '***' if any(s in k.lower() for s in SENSITIVE_KEYS) else v
        for k, v in config.items()
    }

# 사용
logger.info(f"Loaded config: {self._safe_log(config)}")
```

---

## 8. 성능 목표

| 메트릭 | 목표 | 실제 (예상) |
|--------|------|-------------|
| **YAML 로드** | < 10ms | ~5ms (캐시 미스) |
| **캐시 조회** | < 0.1ms | ~0.05ms |
| **환경 변수 로드** | < 5ms | ~2ms |
| **설정 병합** | < 1ms | ~0.5ms |
| **메모리 사용** | < 1MB | ~500KB (50개 파일) |
| **캐시 히트율** | > 95% | ~98% (개발 중) |

---

## 9. 테스트 전략

### 9.1 단위 테스트 (Unit Tests)

```python
# tests/core_foundation/config/test_loader.py

def test_load_yaml_basic():
    """기본 YAML 로딩 테스트"""
    loader = ConfigLoader()
    config = loader.load_yaml("base/app.yaml")

    assert isinstance(config, dict)
    assert "server" in config

def test_load_yaml_caching():
    """캐싱 동작 테스트"""
    loader = ConfigLoader(cache_enabled=True)

    # 첫 로드
    config1 = loader.load_yaml("base/app.yaml")

    # 두 번째 로드 (캐시)
    config2 = loader.load_yaml("base/app.yaml")

    assert config1 == config2
    assert len(loader._cache) == 1

def test_path_traversal_prevention():
    """경로 이스케이프 방지 테스트"""
    loader = ConfigLoader()

    # ../../../etc/passwd 같은 시도
    with pytest.raises(ConfigError):
        loader.load_yaml("../../../etc/passwd")

def test_merge_configs_priority():
    """설정 병합 우선순위 테스트"""
    base = {"port": 8000, "debug": False}
    env = {"debug": True}

    os.environ["PORT"] = "9000"

    result = loader.merge_configs(base, env, env_override=True)

    assert result["port"] == 9000  # ENV 우선
    assert result["debug"] is True  # env 우선

def test_get_nested_key():
    """중첩 키 조회 테스트"""
    config = {
        "detection": {
            "ball": {
                "confidence": 0.75
            }
        }
    }

    loader = ConfigLoader()
    value = loader.get("detection.ball.confidence", config=config)

    assert value == 0.75
```

### 9.2 성능 테스트 (Performance Tests)

```python
def test_load_performance():
    """로딩 성능 테스트 (< 10ms)"""
    import time

    loader = ConfigLoader()

    start = time.perf_counter()
    loader.load_yaml("base/app.yaml")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.01  # 10ms

def test_cache_performance():
    """캐시 성능 테스트 (< 0.1ms)"""
    loader = ConfigLoader(cache_enabled=True)
    loader.load_yaml("base/app.yaml")  # 캐시에 저장

    start = time.perf_counter()
    loader.load_yaml("base/app.yaml")  # 캐시 조회
    elapsed = time.perf_counter() - start

    assert elapsed < 0.0001  # 0.1ms
```

---

## 10. 사용 예시

### 10.1 기본 사용

```python
from core_foundation.config.loader import ConfigLoader

# 초기화
loader = ConfigLoader(
    config_dir=Path("./configs"),
    env_file=Path(".env"),
    cache_enabled=True
)

# .env 로드
loader.load_env()

# YAML 로드
ball_config = loader.load_yaml("detection/ball.yaml")
print(ball_config["confidence_threshold"])  # 0.75

# 중첩 키 조회
confidence = loader.get("detection.ball.confidence_threshold")
```

### 10.2 설정 병합

```python
# 기본 설정
base = loader.load_yaml("base/app.yaml")

# 환경별 설정 (개발/프로덕션)
env = loader.load_yaml(f"environments/{ENV}.yaml")

# 병합 (ENV > env > base)
config = loader.merge_configs(base, env, env_override=True)
```

### 10.3 에러 처리

```python
try:
    config = loader.load_yaml("missing_file.yaml")
except ConfigError as e:
    logger.error(f"Config loading failed: {e}")
    # 기본값 사용
    config = DEFAULT_CONFIG
```

---

## 11. 다음 단계

1. ✅ **loader.py 설계 완료**
2. ⬜ `validator.py` 설계 (Pydantic 검증)
3. ⬜ `settings.py` 설계 (Singleton 전역 설정)
4. ⬜ 구현 및 테스트
5. ⬜ 문서화 (API 문서, 예제)

---

**버전**: 1.0.0
**작성자**: COURTVIEW Development Team
**검토 필요**: settings.py와의 연동, Pydantic 검증 연계
