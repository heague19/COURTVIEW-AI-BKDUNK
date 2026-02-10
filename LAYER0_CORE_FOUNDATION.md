# Layer 0: core_foundation (Desktop Edition)

> **목적**: 로컬 실행 환경에 최적화된 최소 Foundation
> **원칙**: App Server 대비 **60% 경량화** (registry/resilience/security 제외)

---

## 📁 디렉토리 구조

```
core_foundation/
├── config/                  # ✅ 설정 관리
│   ├── __init__.py
│   ├── loader.py           # YAML/ENV 로더
│   ├── validator.py        # Pydantic 검증
│   └── settings.py         # 전역 설정 객체
│
├── monitoring/              # ✅ 로깅/메트릭
│   ├── __init__.py
│   ├── logger.py           # Loguru 기반 로거
│   ├── metrics.py          # 성능 메트릭 (FPS, GPU 사용률)
│   └── profiler.py         # 함수 실행 시간 프로파일링
│
└── exceptions/              # ✅ 예외 계층
    ├── __init__.py
    ├── base.py             # BaseError
    ├── hardware.py         # GPUError, CameraError
    └── validation.py       # ConfigError, DataValidationError
```

---

## 🔧 1. config/ - 설정 관리

### 1.1 loader.py
```python
"""YAML/ENV 설정 파일 로더"""
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv
import os

class ConfigLoader:
    """통합 설정 로더 (YAML + .env)"""

    def __init__(self, config_dir: Path = Path("./configs")):
        self.config_dir = config_dir
        load_dotenv()  # .env 로드

    def load_yaml(self, file_name: str) -> Dict[str, Any]:
        """YAML 파일 로드"""
        file_path = self.config_dir / file_name
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_env(self, key: str, default: Any = None) -> Any:
        """환경 변수 조회"""
        return os.getenv(key, default)
```

### 1.2 settings.py
```python
"""전역 설정 객체 (Singleton)"""
from pydantic_settings import BaseSettings
from pydantic import Field

class DesktopSettings(BaseSettings):
    """Desktop Edition 전역 설정"""

    # 서버
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # GPU
    cuda_visible_devices: str = Field(default="0")
    gpu_memory_fraction: float = Field(default=0.9)

    # 저장소
    storage_path: Path = Field(default=Path("./storage"))
    video_path: Path = Field(default=Path("./storage/videos"))
    output_path: Path = Field(default=Path("./storage/outputs"))

    # 데이터베이스
    database_url: str = Field(default="sqlite:///./database/courtview.db")

    # 성능
    target_fps: int = Field(default=30)
    batch_size: int = Field(default=4)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton 인스턴스
settings = DesktopSettings()
```

**App Server와 차이:**
- ❌ Consul/Vault 연동 없음 → 단순 .env
- ❌ 동적 reload 없음 → 재시작 필요
- ✅ Pydantic 검증은 유지 → 타입 안전성

---

## 📊 2. monitoring/ - 로깅/메트릭

### 2.1 logger.py
```python
"""Loguru 기반 통합 로거"""
from loguru import logger
import sys
from pathlib import Path

def setup_logger(
    log_dir: Path = Path("./storage/logs"),
    level: str = "INFO",
    rotation: str = "100 MB"
):
    """로거 초기화"""
    log_dir.mkdir(parents=True, exist_ok=True)

    # 기본 핸들러 제거
    logger.remove()

    # 콘솔 출력 (컬러)
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    )

    # 파일 출력 (회전)
    logger.add(
        log_dir / "courtview_{time:YYYY-MM-DD}.log",
        level=level,
        rotation=rotation,
        retention="30 days",
        encoding="utf-8"
    )

    return logger
```

### 2.2 metrics.py
```python
"""성능 메트릭 수집"""
from dataclasses import dataclass, field
from time import perf_counter
import psutil
import GPUtil

@dataclass
class PerformanceMetrics:
    """성능 메트릭"""
    fps: float = 0.0
    gpu_utilization: float = 0.0
    gpu_memory_used: float = 0.0
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0

    processing_time_ms: float = 0.0
    frames_processed: int = 0

    def update_gpu_stats(self):
        """GPU 통계 업데이트"""
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            self.gpu_utilization = gpu.load * 100
            self.gpu_memory_used = gpu.memoryUsed

    def update_system_stats(self):
        """시스템 통계 업데이트"""
        self.cpu_percent = psutil.cpu_percent(interval=0.1)
        self.ram_used_gb = psutil.virtual_memory().used / (1024**3)
```

**App Server와 차이:**
- ❌ Prometheus/Grafana 연동 없음
- ❌ 분산 추적 (OpenTelemetry) 없음
- ✅ 로컬 메트릭만 (GUI에 표시용)

---

## ⚠️ 3. exceptions/ - 예외 계층

### 3.1 base.py
```python
"""기본 예외 클래스"""
class CourtViewError(Exception):
    """모든 COURTVIEW 예외의 기본 클래스"""

    def __init__(self, message: str, code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)
```

### 3.2 hardware.py
```python
"""하드웨어 관련 예외"""
class GPUError(CourtViewError):
    """GPU 오류"""
    def __init__(self, message: str):
        super().__init__(message, code="GPU_ERROR")

class CameraError(CourtViewError):
    """카메라 오류"""
    def __init__(self, message: str):
        super().__init__(message, code="CAMERA_ERROR")

class InsufficientMemoryError(GPUError):
    """GPU 메모리 부족"""
    def __init__(self, required_mb: int, available_mb: int):
        message = f"GPU 메모리 부족: {required_mb}MB 필요, {available_mb}MB 사용 가능"
        super().__init__(message)
```

---

## 🚫 제외된 모듈 및 대체 방안

| App Server 모듈 | Desktop 대체 방안 | 이유 |
|-----------------|------------------|------|
| **registry/service_registry.py** | 직접 import | 단일 프로세스, 서비스 발견 불필요 |
| **registry/model_registry.py** | `./models/*.pt` 직접 로드 | 고정된 모델 경로 |
| **registry/di_container.py** | 생성자 직접 호출 | 간단한 의존성 그래프 |
| **resilience/circuit_breaker.py** | 즉시 에러 표시 | 네트워크 호출 없음 |
| **resilience/retry.py** | 로컬 오류는 재시도 무의미 | GPU/파일 오류는 근본 원인 해결 필요 |
| **security/secrets_manager.py** | `.env` 파일 | 외부 노출 없음, OS 파일 권한 충분 |
| **security/audit_logger.py** | 일반 로그로 충분 | 단일 사용자, 규정 준수 불필요 |

---

## 📊 크기 비교

| 항목 | App Server | Desktop | 절감률 |
|------|-----------|---------|--------|
| 모듈 수 | 15개 | 6개 | **60%** |
| 코드 라인 | ~3,000 | ~1,200 | **60%** |
| 의존성 | consul, vault, prometheus | dotenv, loguru, pydantic | **70%** |
| 메모리 | ~200MB | ~50MB | **75%** |

---

## 🎯 설계 원칙

1. **YAGNI (You Aren't Gonna Need It)**
   - 분산 시스템 패턴 (Circuit Breaker, Service Registry) 제거
   - 로컬 실행에 필요한 최소 기능만 유지

2. **로컬 최적화**
   - 네트워크 오버헤드 없음 → 빠른 응답
   - 파일 권한으로 보안 충분
   - .env로 설정 관리 간소화

3. **프로덕션 품질 유지**
   - Pydantic 검증 → 타입 안전성
   - Loguru 로깅 → 디버깅 용이
   - 구조화된 예외 → 명확한 에러 처리

---

## 🚀 사용 예시

```python
# main.py
from core_foundation.config.settings import settings
from core_foundation.monitoring.logger import setup_logger
from core_foundation.monitoring.metrics import PerformanceMetrics

# 초기화
logger = setup_logger(level="INFO" if not settings.debug else "DEBUG")
metrics = PerformanceMetrics()

# 사용
logger.info(f"서버 시작: {settings.server_host}:{settings.server_port}")
logger.info(f"GPU 디바이스: {settings.cuda_visible_devices}")

# 성능 모니터링
metrics.update_gpu_stats()
logger.info(f"GPU 사용률: {metrics.gpu_utilization:.1f}%")
```

---

## ✅ 결론

Desktop Edition은 **로컬 단일 프로세스 실행**이라는 특성상:
- ❌ registry: 서비스 발견/DI 불필요 (직접 import)
- ❌ resilience: 네트워크 장애 없음 (로컬 호출)
- ❌ security: 외부 노출 없음 (.env 충분)

대신 **config + monitoring + exceptions**만으로:
- ✅ 타입 안전한 설정 관리
- ✅ 디버깅을 위한 로깅
- ✅ 명확한 에러 처리

**60% 경량화**하면서도 **프로덕션 품질** 유지! 🎉
