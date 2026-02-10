# Metrics 설계 문서

## 1. 개요

### 1.1 목적
COURTVIEW 시스템의 성능 메트릭 수집, 집계, 분석 및 내보내기를 담당하는 엔터프라이즈급 메트릭 시스템

### 1.2 핵심 기능
- **실시간 메트릭 수집**: FPS, 레이턴시, 처리량, 리소스 사용량
- **통계 집계**: 평균, 중앙값, 백분위수, 최대/최소값
- **메트릭 타입**: Counter, Gauge, Histogram, Timer
- **자동 리소스 모니터링**: CPU, GPU, 메모리, 디스크
- **데이터 내보내기**: JSON, CSV, Prometheus 포맷
- **경량 설계**: 오버헤드 최소화, 비침투적 측정

### 1.3 성능 목표
| 항목 | 목표 |
|------|------|
| 메트릭 기록 오버헤드 | < 0.01ms |
| 초당 메트릭 수집 | > 100,000 metrics/sec |
| 메모리 사용량 (1000 메트릭) | < 10MB |
| 통계 계산 | < 1ms |
| 데이터 내보내기 | < 100ms (1000 메트릭) |

---

## 2. 아키텍처

### 2.1 계층 구조
```
MetricsRegistry (싱글톤)
    ├─ Counter (카운터)
    ├─ Gauge (게이지)
    ├─ Histogram (히스토그램)
    ├─ Timer (타이머)
    └─ ResourceMonitor (리소스 모니터)
        ├─ CPUMonitor
        ├─ GPUMonitor
        └─ MemoryMonitor
```

### 2.2 데이터 플로우
```
측정 대상
    ↓
Metric 객체 (기록)
    ↓
MetricsRegistry (집계)
    ↓
Aggregator (통계 계산)
    ↓
Exporter (내보내기)
    ↓
JSON/CSV/Prometheus
```

---

## 3. 메트릭 타입

### 3.1 Counter (카운터)
**용도**: 누적 증가만 가능한 단조 증가 메트릭
**예시**: 처리된 프레임 수, 에러 발생 횟수

```python
from core_foundation.monitoring.metrics import Counter

frame_counter = Counter("frames_processed", "Total frames processed")
frame_counter.inc()  # 1 증가
frame_counter.inc(5)  # 5 증가
print(frame_counter.value)  # 6
```

**특징**:
- 항상 증가 (감소 불가)
- 재시작 시 0으로 리셋
- rate() 함수로 초당 증가율 계산 가능

### 3.2 Gauge (게이지)
**용도**: 임의로 증가/감소 가능한 메트릭
**예시**: 현재 CPU 사용률, 큐 크기, 활성 연결 수

```python
from core_foundation.monitoring.metrics import Gauge

cpu_gauge = Gauge("cpu_usage", "Current CPU usage percentage")
cpu_gauge.set(45.2)  # 값 설정
cpu_gauge.inc(5)     # 5 증가 → 50.2
cpu_gauge.dec(10)    # 10 감소 → 40.2
print(cpu_gauge.value)  # 40.2
```

**특징**:
- 증가/감소 자유
- 현재 상태 표현
- 스냅샷 측정에 적합

### 3.3 Histogram (히스토그램)
**용도**: 값의 분포를 추적 (백분위수, 평균, 중앙값)
**예시**: 응답 시간 분포, 프레임 처리 시간 분포

```python
from core_foundation.monitoring.metrics import Histogram

latency_hist = Histogram(
    "request_latency",
    "Request latency in milliseconds",
    buckets=[10, 50, 100, 500, 1000]  # ms 단위 버킷
)

# 값 관찰
latency_hist.observe(23.5)
latency_hist.observe(156.2)
latency_hist.observe(45.8)

# 통계 조회
stats = latency_hist.get_stats()
print(stats.mean)       # 평균
print(stats.median)     # 중앙값 (P50)
print(stats.p95)        # 95 백분위수
print(stats.p99)        # 99 백분위수
```

**특징**:
- 백분위수 계산 (P50, P95, P99)
- 평균, 표준편차, 최소/최대값
- 버킷 기반 히스토그램 (메모리 효율적)

### 3.4 Timer (타이머)
**용도**: 코드 실행 시간 측정 (컨텍스트 매니저)
**예시**: 함수 실행 시간, API 응답 시간

```python
from core_foundation.monitoring.metrics import Timer

pose_timer = Timer("pose_estimation_time", "Pose estimation duration")

# 컨텍스트 매니저 사용
with pose_timer:
    # 포즈 추정 코드
    result = model.predict(frame)

# 데코레이터 사용
@pose_timer.time()
def process_frame(frame):
    return model.predict(frame)

# 통계 조회
stats = pose_timer.get_stats()
print(f"평균: {stats.mean:.2f}ms")
print(f"P95: {stats.p95:.2f}ms")
```

**특징**:
- 자동 시간 측정 (컨텍스트 매니저)
- 데코레이터 지원
- 내부적으로 Histogram 사용

---

## 4. 리소스 모니터링

### 4.1 CPUMonitor
```python
from core_foundation.monitoring.metrics import CPUMonitor

cpu_monitor = CPUMonitor()

# 현재 CPU 사용률
usage = cpu_monitor.get_usage()
print(f"CPU: {usage.percent}%")
print(f"코어당: {usage.per_core}")  # [12.3, 45.6, 23.1, ...]

# 부하 평균 (1분, 5분, 15분)
load = cpu_monitor.get_load_average()
print(f"Load: {load.one_min}, {load.five_min}, {load.fifteen_min}")
```

**측정 항목**:
- 전체 CPU 사용률 (%)
- 코어별 사용률 (%)
- 부하 평균 (1분, 5분, 15분)
- 프로세스별 CPU 시간

### 4.2 GPUMonitor
```python
from core_foundation.monitoring.metrics import GPUMonitor

gpu_monitor = GPUMonitor()

# GPU 정보
info = gpu_monitor.get_info()
print(f"GPU: {info.name}")
print(f"드라이버: {info.driver_version}")
print(f"CUDA: {info.cuda_version}")

# 리소스 사용량
usage = gpu_monitor.get_usage()
print(f"GPU 사용률: {usage.utilization}%")
print(f"메모리: {usage.memory_used}/{usage.memory_total} MB")
print(f"온도: {usage.temperature}°C")
print(f"전력: {usage.power_usage}/{usage.power_limit} W")
```

**측정 항목**:
- GPU 사용률 (%)
- 메모리 사용량 (MB)
- 온도 (°C)
- 전력 소비 (W)
- CUDA/CUDNN 버전

### 4.3 MemoryMonitor
```python
from core_foundation.monitoring.metrics import MemoryMonitor

mem_monitor = MemoryMonitor()

# 시스템 메모리
sys_mem = mem_monitor.get_system_memory()
print(f"메모리: {sys_mem.used}/{sys_mem.total} MB ({sys_mem.percent}%)")
print(f"스왑: {sys_mem.swap_used}/{sys_mem.swap_total} MB")

# 프로세스 메모리
proc_mem = mem_monitor.get_process_memory()
print(f"RSS: {proc_mem.rss} MB")  # Resident Set Size
print(f"VMS: {proc_mem.vms} MB")  # Virtual Memory Size
```

**측정 항목**:
- 시스템 메모리 사용량 (total, used, free, percent)
- 스왑 메모리 사용량
- 프로세스 메모리 (RSS, VMS)
- 메모리 누수 감지 (증가 추세)

---

## 5. MetricsRegistry (레지스트리)

### 5.1 싱글톤 패턴
```python
from core_foundation.monitoring.metrics import get_metrics_registry

# 싱글톤 인스턴스
registry = get_metrics_registry()

# 메트릭 등록
counter = registry.counter("frames_total", "Total frames processed")
gauge = registry.gauge("queue_size", "Current queue size")
histogram = registry.histogram("latency_ms", "Latency in milliseconds")
timer = registry.timer("process_time", "Processing time")

# 메트릭 조회
all_metrics = registry.get_all_metrics()
counter_value = registry.get_metric("frames_total").value
```

### 5.2 메트릭 그룹화
```python
# 라벨 기반 그룹화
registry.counter(
    "requests_total",
    "Total HTTP requests",
    labels={"method": "POST", "endpoint": "/api/analyze"}
)

# 메트릭 필터링
http_metrics = registry.get_metrics(prefix="http_")
error_metrics = registry.get_metrics(labels={"status": "error"})
```

---

## 6. 통계 집계

### 6.1 Statistics 클래스
```python
@dataclass
class Statistics:
    """통계 정보"""
    count: int              # 샘플 수
    sum: float              # 합계
    mean: float             # 평균
    median: float           # 중앙값 (P50)
    std: float              # 표준편차
    min: float              # 최소값
    max: float              # 최대값
    p50: float              # 50 백분위수
    p90: float              # 90 백분위수
    p95: float              # 95 백분위수
    p99: float              # 99 백분위수
```

### 6.2 롤링 윈도우
```python
from core_foundation.monitoring.metrics import RollingWindow

# 최근 1000개 샘플만 유지
window = RollingWindow(max_size=1000)

for value in values:
    window.add(value)

stats = window.get_stats()
print(f"평균: {stats.mean:.2f}")
print(f"P95: {stats.p95:.2f}")
```

**특징**:
- 고정 크기 윈도우 (메모리 제한)
- 효율적인 백분위수 계산
- 자동 오래된 데이터 제거

### 6.3 시간 기반 윈도우
```python
from core_foundation.monitoring.metrics import TimeWindow

# 최근 60초 데이터만 유지
window = TimeWindow(duration_seconds=60)

window.add(value, timestamp=time.time())

stats = window.get_stats()
rate = window.get_rate()  # 초당 평균
```

---

## 7. 데이터 내보내기

### 7.1 JSON 포맷
```python
from core_foundation.monitoring.metrics import JSONExporter

exporter = JSONExporter()
data = exporter.export(registry)

# 출력 예시
{
    "timestamp": "2026-02-10T12:34:56.789Z",
    "metrics": {
        "frames_total": {
            "type": "counter",
            "value": 12345,
            "description": "Total frames processed"
        },
        "cpu_usage": {
            "type": "gauge",
            "value": 45.2,
            "description": "Current CPU usage percentage"
        },
        "latency_ms": {
            "type": "histogram",
            "count": 1000,
            "sum": 45231.5,
            "mean": 45.23,
            "p95": 123.4,
            "p99": 234.5,
            "buckets": {
                "10": 123,
                "50": 456,
                "100": 789,
                "500": 950,
                "1000": 1000
            }
        }
    }
}
```

### 7.2 CSV 포맷
```python
from core_foundation.monitoring.metrics import CSVExporter

exporter = CSVExporter()
exporter.export_to_file(registry, "metrics.csv")

# CSV 출력 예시
timestamp,metric_name,metric_type,value,count,mean,p95,p99
2026-02-10T12:34:56.789Z,frames_total,counter,12345,,,
2026-02-10T12:34:56.789Z,cpu_usage,gauge,45.2,,,
2026-02-10T12:34:56.789Z,latency_ms,histogram,45231.5,1000,45.23,123.4,234.5
```

### 7.3 Prometheus 포맷
```python
from core_foundation.monitoring.metrics import PrometheusExporter

exporter = PrometheusExporter()
text = exporter.export(registry)

# Prometheus 출력 예시
# HELP frames_total Total frames processed
# TYPE frames_total counter
frames_total 12345

# HELP cpu_usage Current CPU usage percentage
# TYPE cpu_usage gauge
cpu_usage 45.2

# HELP latency_ms Latency in milliseconds
# TYPE latency_ms histogram
latency_ms_bucket{le="10"} 123
latency_ms_bucket{le="50"} 456
latency_ms_bucket{le="100"} 789
latency_ms_bucket{le="500"} 950
latency_ms_bucket{le="1000"} 1000
latency_ms_bucket{le="+Inf"} 1000
latency_ms_sum 45231.5
latency_ms_count 1000
```

---

## 8. 실전 사용 패턴

### 8.1 프레임 처리 메트릭
```python
from core_foundation.monitoring.metrics import get_metrics_registry

registry = get_metrics_registry()

# 메트릭 등록
frames_total = registry.counter("frames_processed_total", "Total frames processed")
frames_error = registry.counter("frames_error_total", "Total frames with errors")
processing_time = registry.timer("frame_processing_time", "Frame processing duration")
fps_gauge = registry.gauge("current_fps", "Current frames per second")

# 사용
def process_frame(frame):
    with processing_time:
        try:
            result = analyze_frame(frame)
            frames_total.inc()
            return result
        except Exception as e:
            frames_error.inc()
            raise

# FPS 계산
import time
last_time = time.time()
frame_count = 0

while True:
    process_frame(frame)
    frame_count += 1

    current_time = time.time()
    if current_time - last_time >= 1.0:
        fps = frame_count / (current_time - last_time)
        fps_gauge.set(fps)
        frame_count = 0
        last_time = current_time
```

### 8.2 리소스 모니터링
```python
from core_foundation.monitoring.metrics import get_metrics_registry, ResourceMonitor

registry = get_metrics_registry()
resource_monitor = ResourceMonitor()

# 주기적 모니터링
import threading

def monitor_resources():
    cpu_gauge = registry.gauge("cpu_usage", "CPU usage percentage")
    gpu_gauge = registry.gauge("gpu_usage", "GPU usage percentage")
    memory_gauge = registry.gauge("memory_usage", "Memory usage MB")

    while True:
        cpu = resource_monitor.get_cpu_usage()
        gpu = resource_monitor.get_gpu_usage()
        memory = resource_monitor.get_memory_usage()

        cpu_gauge.set(cpu.percent)
        gpu_gauge.set(gpu.utilization)
        memory_gauge.set(memory.used)

        time.sleep(1)  # 1초마다

monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
monitor_thread.start()
```

### 8.3 분석 파이프라인 메트릭
```python
from core_foundation.monitoring.metrics import get_metrics_registry

registry = get_metrics_registry()

# 각 단계별 메트릭
pose_timer = registry.timer("pose_estimation_time", "Pose estimation duration")
detection_timer = registry.timer("ball_detection_time", "Ball detection duration")
analysis_timer = registry.timer("motion_analysis_time", "Motion analysis duration")

pipeline_time = registry.timer("pipeline_total_time", "Total pipeline duration")

def analyze_video(video_path):
    with pipeline_time:
        # 1. 포즈 추정
        with pose_timer:
            poses = pose_estimator.estimate(video_path)

        # 2. 공 탐지
        with detection_timer:
            ball_positions = ball_detector.detect(video_path)

        # 3. 모션 분석
        with analysis_timer:
            result = motion_analyzer.analyze(poses, ball_positions)

        return result
```

---

## 9. 성능 최적화

### 9.1 샘플링
```python
# 모든 요청을 기록하지 않고 1/100만 샘플링
import random

def process_request(request):
    if random.random() < 0.01:  # 1% 샘플링
        with request_timer:
            return handle_request(request)
    else:
        return handle_request(request)
```

### 9.2 비동기 기록
```python
from core_foundation.monitoring.metrics import AsyncMetricsWriter

writer = AsyncMetricsWriter()

# 백그라운드 스레드에서 비동기로 기록
writer.write(metric_name, value)

# 종료 시 대기
writer.flush()
writer.close()
```

### 9.3 메모리 제한
```python
# 히스토그램에 최대 샘플 수 제한
histogram = registry.histogram(
    "latency_ms",
    "Latency in milliseconds",
    max_samples=10000  # 최대 10,000개만 유지
)
```

---

## 10. 오류 처리

### 10.1 메트릭 기록 실패
```python
try:
    with timer:
        result = process()
except Exception as e:
    # 메트릭 기록 실패는 무시 (원본 작업 방해 금지)
    logger.debug(f"Failed to record metric: {e}")
    raise  # 원본 예외는 재발생
```

### 10.2 리소스 모니터링 실패
```python
def get_gpu_usage():
    try:
        return gpu_monitor.get_usage()
    except GPUError:
        # GPU 없으면 None 반환
        return None
```

---

## 11. 테스트 전략

### 11.1 단위 테스트
- 각 메트릭 타입 (Counter, Gauge, Histogram, Timer) 동작 검증
- 통계 계산 정확성 (평균, 백분위수)
- 롤링 윈도우 동작
- 내보내기 포맷 검증

### 11.2 성능 테스트
| 항목 | 목표 |
|------|------|
| Counter.inc() | < 0.001ms |
| Gauge.set() | < 0.001ms |
| Histogram.observe() | < 0.01ms |
| Timer 측정 | < 0.01ms 오버헤드 |
| Statistics 계산 | < 1ms (1000 샘플) |
| JSON 내보내기 | < 100ms (1000 메트릭) |
| 메모리 사용량 | < 10MB (1000 메트릭) |

### 11.3 통합 테스트
- 전체 파이프라인 (등록 → 기록 → 집계 → 내보내기)
- 멀티스레드 환경
- 리소스 모니터링 실제 동작
- 대량 메트릭 처리

---

## 12. 구현 체크리스트

### 12.1 핵심 클래스
- [ ] `MetricType` Enum
- [ ] `Counter` 클래스
- [ ] `Gauge` 클래스
- [ ] `Histogram` 클래스
- [ ] `Timer` 클래스 (컨텍스트 매니저)
- [ ] `Statistics` 데이터클래스
- [ ] `MetricsRegistry` 싱글톤
- [ ] `get_metrics_registry()` 팩토리 함수

### 12.2 리소스 모니터
- [ ] `CPUMonitor` 클래스
- [ ] `GPUMonitor` 클래스
- [ ] `MemoryMonitor` 클래스
- [ ] `ResourceMonitor` 통합 클래스

### 12.3 집계 및 분석
- [ ] `RollingWindow` 클래스
- [ ] `TimeWindow` 클래스
- [ ] `Aggregator` 클래스
- [ ] 백분위수 계산 함수

### 12.4 내보내기
- [ ] `Exporter` 기본 클래스
- [ ] `JSONExporter` 클래스
- [ ] `CSVExporter` 클래스
- [ ] `PrometheusExporter` 클래스

### 12.5 유틸리티
- [ ] `@timed` 데코레이터
- [ ] `measure_time()` 함수
- [ ] `calculate_rate()` 함수
- [ ] `format_bytes()` 함수

---

## 13. 의존성

### 13.1 외부 라이브러리
```python
# 필수
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum, auto
from collections import deque
import statistics

# 선택 (리소스 모니터링)
import psutil  # CPU, 메모리
import GPUtil  # GPU (없으면 None 반환)
```

### 13.2 내부 의존성
```python
from core_foundation.monitoring.logger import get_logger
from core_foundation.exceptions.base import CourtViewError
```

---

## 14. 예상 파일 구조
```
core_foundation/
└── monitoring/
    ├── __init__.py
    ├── logger.py          ✅ 완료
    └── metrics.py         ← 이번 작업
```

---

## 15. 다음 단계
1. **metrics.py 구현** (약 800-1000줄)
2. **단위 테스트** (test_metrics.py)
3. **성능 테스트** (test_metrics_perf.py)
4. **통합 테스트** (test_metrics_integration.py)
5. **실제 파이프라인 적용**

---

**설계 작성**: 2026-02-10
**버전**: 1.0.0
**작성자**: COURTVIEW Team
