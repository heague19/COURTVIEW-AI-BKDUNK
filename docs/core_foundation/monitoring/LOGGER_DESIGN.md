# Logger 설계 문서

**모듈**: `core_foundation/monitoring/logger.py`
**목적**: 엔터프라이즈급 구조화된 로깅 시스템
**버전**: 1.0.0
**작성일**: 2026-02-10

## 1. 개요

### 1.1 목적
COURTVIEW Desktop의 모든 컴포넌트에서 사용하는 중앙화된 로깅 시스템을 제공합니다.

### 1.2 핵심 기능
- **구조화된 로깅**: JSON 포맷으로 로그 저장 (분석 용이)
- **계층적 로거**: 모듈별 독립적인 로거 생성
- **성능 최적화**: 비동기 로깅, 버퍼링, 회전
- **민감 정보 필터링**: 자동 마스킹 (비밀번호, API 키)
- **예외 통합**: CourtViewError 자동 컨텍스트 추출
- **다중 출력**: 콘솔, 파일, 회전 로그, 원격 전송

### 1.3 설계 원칙
1. **Zero Configuration**: 기본 설정으로 즉시 사용 가능
2. **Type Safety**: 완전한 타입 힌팅
3. **Performance**: 로깅이 메인 로직을 블로킹하지 않음
4. **Production Ready**: 대용량 로그 처리 가능

## 2. 아키텍처

### 2.1 계층 구조
```
CourtViewLogger (Root)
├── core_foundation.*
│   ├── config.*
│   ├── exceptions.*
│   └── monitoring.*
├── motion_analysis.*
│   ├── shooting.*
│   ├── dribbling.*
│   └── passing.*
└── game_analysis.*
```

### 2.2 컴포넌트 구성
```
┌─────────────────────────────────────────────┐
│           CourtViewLogger                   │
│  (Singleton, Thread-Safe)                   │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┼─────────────┬──────────────┐
    │             │             │              │
┌───▼────┐  ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
│Console │  │  File   │  │  Rotating │  │ Remote  │
│Handler │  │ Handler │  │  Handler  │  │ Handler │
└────────┘  └─────────┘  └───────────┘  └─────────┘
    │             │             │              │
┌───▼─────────────▼─────────────▼──────────────▼───┐
│              Filter Chain                         │
│  - Sensitive Data Filter                          │
│  - Level Filter                                   │
│  - Rate Limiter                                   │
└───────────────────┬───────────────────────────────┘
                    │
        ┌───────────▼───────────┐
        │   Formatter           │
        │  - JSON Format        │
        │  - Colored Console    │
        └───────────────────────┘
```

## 3. 로그 레벨

### 3.1 표준 레벨
```python
class LogLevel(Enum):
    DEBUG = 10      # 디버깅 정보
    INFO = 20       # 일반 정보
    WARNING = 30    # 경고 (처리 가능한 문제)
    ERROR = 40      # 에러 (기능 저하)
    CRITICAL = 50   # 치명적 (시스템 중단)
```

### 3.2 레벨별 사용 지침
| 레벨 | 사용 시점 | 예시 |
|------|----------|------|
| DEBUG | 개발 중 디버깅 | "Frame 1234 processed in 0.023s" |
| INFO | 정상 작동 이벤트 | "Settings loaded successfully" |
| WARNING | 잠재적 문제 | "GPU memory usage at 85%" |
| ERROR | 복구 가능한 에러 | "Frame skip detected" |
| CRITICAL | 시스템 중단 에러 | "GPU initialization failed" |

## 4. 로그 포맷

### 4.1 JSON 포맷 (파일)
```json
{
  "timestamp": "2026-02-10T14:30:00.123456+09:00",
  "level": "ERROR",
  "logger": "motion_analysis.shooting.detector",
  "message": "Frame processing failed",
  "context": {
    "frame_id": 1234,
    "fps": 30,
    "device_id": 0
  },
  "exception": {
    "type": "GPUError",
    "message": "GPU memory insufficient",
    "code": "CV201",
    "traceback": "..."
  },
  "performance": {
    "processing_time_ms": 45.2,
    "memory_mb": 1024
  },
  "system": {
    "hostname": "courtview-001",
    "pid": 12345,
    "thread": "MainThread"
  }
}
```

### 4.2 콘솔 포맷 (개발)
```
2026-02-10 14:30:00 [ERROR] motion_analysis.shooting.detector - Frame processing failed
  └─ frame_id=1234, fps=30, device_id=0
  └─ GPUError [CV201]: GPU memory insufficient
```

### 4.3 콘솔 색상
- DEBUG: 회색
- INFO: 녹색
- WARNING: 노란색
- ERROR: 빨간색
- CRITICAL: 밝은 빨간색 + 굵게

## 5. 핸들러

### 5.1 ConsoleHandler
**목적**: 개발 중 실시간 로그 확인

**설정**:
```python
ConsoleHandler(
    level=LogLevel.INFO,
    colored=True,           # 색상 출력
    show_context=True,      # 컨텍스트 표시
    max_width=120           # 최대 너비
)
```

### 5.2 FileHandler
**목적**: 일반 로그 파일 저장

**설정**:
```python
FileHandler(
    filename="logs/courtview.log",
    level=LogLevel.DEBUG,
    format="json",          # json | text
    encoding="utf-8"
)
```

### 5.3 RotatingFileHandler
**목적**: 대용량 로그 관리 (자동 회전 + 압축)

**설정**:
```python
RotatingFileHandler(
    filename="logs/courtview.log",
    max_bytes=100 * 1024 * 1024,  # 100MB
    backup_count=10,               # 10개 백업
    compression="gzip",            # gzip | none
    when="midnight"                # 일별 회전
)
```

**회전 규칙**:
- 크기 기반: 100MB 도달 시 회전
- 시간 기반: 매일 자정 회전
- 압축: 이전 로그 자동 gzip 압축
- 정리: 10개 이상 백업 삭제

### 5.4 RemoteHandler (선택)
**목적**: 원격 로그 서버 전송 (ELK, CloudWatch)

**설정**:
```python
RemoteHandler(
    endpoint="https://logs.courtview.com/api/v1/logs",
    api_key="***",
    batch_size=100,         # 배치 전송
    flush_interval=10       # 10초마다 전송
)
```

## 6. 필터

### 6.1 SensitiveDataFilter
**목적**: 민감 정보 자동 마스킹

**마스킹 대상**:
- 비밀번호: `"password": "***"`
- API 키: `"api_key": "sk-***abc"`
- 토큰: `"token": "eyJ***xyz"`
- 이메일: `"email": "u***@example.com"`
- 신용카드: `"card": "****-****-****-1234"`

**구현**:
```python
class SensitiveDataFilter:
    PATTERNS = {
        "password": re.compile(r'"password"\s*:\s*"[^"]*"'),
        "api_key": re.compile(r'"api_key"\s*:\s*"sk-\w+"'),
        # ...
    }

    def filter(self, record: LogRecord) -> LogRecord:
        # 컨텍스트에서 민감 정보 마스킹
        record.context = self._mask_sensitive(record.context)
        return record
```

### 6.2 LevelFilter
**목적**: 레벨별 필터링

### 6.3 RateLimiter
**목적**: 과도한 로깅 방지

**설정**:
```python
RateLimiter(
    max_logs_per_second=100,
    burst=200
)
```

## 7. 성능 고려사항

### 7.1 비동기 로깅
```python
class AsyncLogger:
    def __init__(self):
        self.queue = Queue(maxsize=10000)
        self.worker = Thread(target=self._worker)
        self.worker.start()

    def log(self, record: LogRecord):
        # 메인 스레드는 큐에만 넣고 즉시 반환
        self.queue.put_nowait(record)

    def _worker(self):
        # 백그라운드 스레드가 실제 쓰기 처리
        while True:
            record = self.queue.get()
            self._write(record)
```

### 7.2 버퍼링
- 콘솔: 버퍼링 없음 (즉시 출력)
- 파일: 8KB 버퍼
- 원격: 배치 전송 (100개 또는 10초)

### 7.3 성능 목표
- 로그 호출 오버헤드: <0.1ms (비동기)
- 메모리 사용량: <50MB (큐 + 버퍼)
- 처리량: >10,000 logs/sec

## 8. 예외 통합

### 8.1 CourtViewError 자동 처리
```python
try:
    # 코드 실행
    pass
except CourtViewError as e:
    logger.error(
        f"Operation failed: {e.message}",
        extra={
            "error_code": e.error_code,
            "context": e.context,
            "original_error": str(e.original_error)
        }
    )
```

### 8.2 자동 컨텍스트 추출
```python
logger.exception(e)  # CourtViewError면 자동으로 컨텍스트 추출
# 결과:
# {
#   "exception": {
#     "type": "GPUError",
#     "code": "CV201",
#     "context": {"gpu_id": 0, "required_mb": 8192}
#   }
# }
```

## 9. 사용 예시

### 9.1 기본 사용
```python
from core_foundation.monitoring.logger import get_logger

logger = get_logger(__name__)

# 간단한 로그
logger.info("Processing started")

# 컨텍스트 포함
logger.info("Frame processed", extra={
    "frame_id": 1234,
    "processing_time_ms": 23.5
})

# 예외 로그
try:
    # ...
except Exception as e:
    logger.exception("Processing failed", exc_info=e)
```

### 9.2 구조화된 로깅
```python
logger.info(
    "Model inference completed",
    extra={
        "model_name": "yolov8",
        "input_shape": (640, 640),
        "detections": 5,
        "confidence_avg": 0.87,
        "inference_time_ms": 15.2
    }
)
```

### 9.3 성능 측정
```python
with logger.timed("frame_processing"):
    process_frame()

# 로그 출력:
# INFO - Frame processing completed in 23.45ms
```

### 9.4 계층적 로거
```python
# 모듈별 로거
shooting_logger = get_logger("motion_analysis.shooting")
dribbling_logger = get_logger("motion_analysis.dribbling")

# 각각 독립적인 설정 가능
shooting_logger.setLevel(LogLevel.DEBUG)
dribbling_logger.setLevel(LogLevel.INFO)
```

## 10. 설정

### 10.1 YAML 설정
```yaml
logging:
  version: 1

  # 전역 레벨
  level: INFO

  # 핸들러
  handlers:
    console:
      type: console
      level: INFO
      colored: true

    file:
      type: rotating_file
      filename: logs/courtview.log
      max_bytes: 104857600  # 100MB
      backup_count: 10
      compression: gzip

  # 모듈별 레벨
  loggers:
    motion_analysis.shooting:
      level: DEBUG
    motion_analysis.dribbling:
      level: INFO
```

### 10.2 프로그램 설정
```python
from core_foundation.monitoring.logger import configure_logging

configure_logging(
    level=LogLevel.INFO,
    handlers=[
        ConsoleHandler(colored=True),
        RotatingFileHandler(
            filename="logs/courtview.log",
            max_bytes=100 * 1024 * 1024,
            backup_count=10
        )
    ],
    format="json",
    async_mode=True
)
```

## 11. 클래스 설계

### 11.1 주요 클래스
```python
class CourtViewLogger:
    """중앙 로거 (Singleton)"""
    def __init__(self, name: str):
        self.name = name
        self.handlers: List[Handler] = []
        self.filters: List[Filter] = []
        self.level = LogLevel.INFO

    def debug(self, message: str, **kwargs): ...
    def info(self, message: str, **kwargs): ...
    def warning(self, message: str, **kwargs): ...
    def error(self, message: str, **kwargs): ...
    def critical(self, message: str, **kwargs): ...
    def exception(self, message: str, exc_info: Exception): ...

class LogRecord:
    """로그 레코드"""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    context: Dict[str, Any]
    exception: Optional[ExceptionInfo]
    performance: Optional[PerformanceInfo]

class Handler(ABC):
    """핸들러 기본 클래스"""
    @abstractmethod
    def emit(self, record: LogRecord): ...

class Filter(ABC):
    """필터 기본 클래스"""
    @abstractmethod
    def filter(self, record: LogRecord) -> bool: ...

class Formatter(ABC):
    """포맷터 기본 클래스"""
    @abstractmethod
    def format(self, record: LogRecord) -> str: ...
```

## 12. 테스트 요구사항

### 12.1 단위 테스트
- 로거 생성 및 계층 구조
- 레벨 필터링
- 핸들러 동작
- 필터 체인
- 포맷터 출력
- 예외 처리

### 12.2 성능 테스트
- 로그 처리 속도: >10,000 logs/sec
- 메모리 사용량: <50MB
- 비동기 오버헤드: <0.1ms

### 12.3 통합 테스트
- 다중 핸들러 동시 사용
- 회전 및 압축
- 예외 통합
- 민감 정보 필터링

## 13. 참고 사항

### 13.1 Python 표준 logging 통합
- 기존 코드와 호환성 유지
- `logging.Logger` 래퍼로 구현
- 기존 핸들러/필터 재사용 가능

### 13.2 제약사항
- 로그 파일은 UTF-8 인코딩 고정
- JSON 로그는 최대 64KB/레코드
- 비동기 큐 최대 10,000개

### 13.3 향후 확장
- 분산 추적 (OpenTelemetry)
- 메트릭 수집 (Prometheus)
- 알림 통합 (Slack, Email)
- 대시보드 (Grafana)

## 14. 의존성

```python
# 필수
- Python 3.11+
- typing
- json
- threading
- queue

# 선택
- colorama (콘솔 색상)
- orjson (고성능 JSON)
- python-json-logger (구조화된 로깅)
```

## 15. 우선순위

### Phase 1 (필수)
- [x] 설계 문서
- [ ] 기본 로거 구현
- [ ] 콘솔 핸들러
- [ ] 파일 핸들러
- [ ] JSON 포맷터

### Phase 2 (권장)
- [ ] 회전 핸들러
- [ ] 민감 정보 필터
- [ ] 비동기 로깅
- [ ] 성능 최적화

### Phase 3 (확장)
- [ ] 원격 핸들러
- [ ] 분산 추적
- [ ] 메트릭 수집
