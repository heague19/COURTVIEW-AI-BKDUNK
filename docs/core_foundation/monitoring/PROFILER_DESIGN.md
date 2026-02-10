# Profiler 설계 문서

## 1. 개요

### 1.1 목적
COURTVIEW 시스템의 성능 분석 및 최적화를 위한 엔터프라이즈급 프로파일링 도구

### 1.2 핵심 기능
- **함수 프로파일링**: 실행 시간, 호출 횟수, 평균/최대/최소 시간
- **메모리 프로파일링**: 메모리 사용량 추적, 메모리 누수 탐지
- **호출 스택 추적**: 함수 호출 계층 구조, 콜 그래프
- **핫스팟 탐지**: 성능 병목 지점 자동 식별
- **상세 보고서**: JSON, HTML, 텍스트 포맷
- **조건부 프로파일링**: 환경별 활성화/비활성화
- **최소 오버헤드**: 프로덕션 환경에서도 사용 가능

### 1.3 성능 목표
| 항목 | 목표 |
|------|------|
| 프로파일링 오버헤드 | < 5% (비활성화 시 < 0.1%) |
| 함수 호출 추적 | < 0.01ms/call |
| 메모리 측정 | < 0.1ms/measurement |
| 보고서 생성 | < 1초 (1000개 함수) |
| 메모리 사용량 | < 50MB (1000개 함수 추적) |

---

## 2. 아키텍처

### 2.1 계층 구조
```
ProfilerManager (싱글톤)
    ├─ TimeProfiler (시간 프로파일링)
    │   ├─ FunctionProfile (함수별 통계)
    │   └─ CallStack (호출 스택)
    ├─ MemoryProfiler (메모리 프로파일링)
    │   └─ MemorySnapshot (메모리 스냅샷)
    └─ Reporter (보고서 생성)
        ├─ TextReporter
        ├─ JSONReporter
        └─ HTMLReporter
```

### 2.2 데이터 플로우
```
@profile 데코레이터
    ↓
함수 실행 전: start_profiling()
    ↓
함수 실행 (실제 작업)
    ↓
함수 실행 후: end_profiling()
    ↓
ProfilerManager에 기록
    ↓
분석 및 집계
    ↓
Reporter로 보고서 생성
```

---

## 3. 프로파일링 타입

### 3.1 TimeProfiler (시간 프로파일링)
**용도**: 함수 실행 시간 측정 및 성능 병목 탐지

```python
from core_foundation.monitoring.profiler import TimeProfiler

profiler = TimeProfiler()

@profiler.profile()
def process_frame(frame):
    # 처리 로직
    return result

# 통계 조회
stats = profiler.get_stats()
for func_name, stat in stats.items():
    print(f"{func_name}: {stat.total_time:.2f}ms, {stat.call_count} calls")
```

**측정 항목**:
- 호출 횟수 (call_count)
- 총 실행 시간 (total_time)
- 평균 실행 시간 (avg_time)
- 최소 실행 시간 (min_time)
- 최대 실행 시간 (max_time)
- 표준편차 (std_time)

### 3.2 MemoryProfiler (메모리 프로파일링)
**용도**: 메모리 사용량 추적 및 메모리 누수 탐지

```python
from core_foundation.monitoring.profiler import MemoryProfiler

profiler = MemoryProfiler()

@profiler.profile()
def load_model():
    model = LargeModel()
    return model

# 메모리 스냅샷
snapshot = profiler.get_snapshot()
print(f"Peak memory: {snapshot.peak_memory_mb:.2f} MB")
print(f"Current memory: {snapshot.current_memory_mb:.2f} MB")

# 메모리 누수 탐지
leaks = profiler.detect_leaks()
for leak in leaks:
    print(f"Leak: {leak.function_name}, {leak.memory_increase_mb:.2f} MB")
```

**측정 항목**:
- 함수 실행 전 메모리 (memory_before)
- 함수 실행 후 메모리 (memory_after)
- 메모리 증가량 (memory_delta)
- 피크 메모리 (peak_memory)
- 메모리 누수 여부 (is_leak)

### 3.3 CallStackProfiler (호출 스택 추적)
**용도**: 함수 호출 계층 구조 및 콜 그래프 생성

```python
from core_foundation.monitoring.profiler import CallStackProfiler

profiler = CallStackProfiler()

@profiler.profile()
def process_video(video_path):
    frames = extract_frames(video_path)  # 추적됨
    results = analyze_frames(frames)     # 추적됨
    return results

# 호출 그래프
call_graph = profiler.get_call_graph()
print(call_graph.to_text())

# 플레임 그래프 데이터
flame_graph = profiler.get_flame_graph()
```

**측정 항목**:
- 호출자 (caller)
- 피호출자 (callee)
- 호출 깊이 (depth)
- 누적 시간 (cumulative_time)
- 자체 시간 (self_time)

---

## 4. 프로파일러 클래스

### 4.1 FunctionProfile (함수별 통계)
```python
@dataclass
class FunctionProfile:
    """함수 프로파일 통계"""
    function_name: str          # 함수 이름
    module_name: str            # 모듈 이름
    call_count: int             # 호출 횟수
    total_time: float           # 총 실행 시간 (ms)
    avg_time: float             # 평균 실행 시간 (ms)
    min_time: float             # 최소 실행 시간 (ms)
    max_time: float             # 최대 실행 시간 (ms)
    std_time: float             # 표준편차 (ms)

    # 메모리
    total_memory: float         # 총 메모리 사용량 (MB)
    avg_memory: float           # 평균 메모리 (MB)
    peak_memory: float          # 피크 메모리 (MB)

    # 호출 스택
    callers: List[str]          # 호출자 목록
    callees: List[str]          # 피호출자 목록

    # 기타
    first_call_time: float      # 첫 호출 시각
    last_call_time: float       # 마지막 호출 시각
```

### 4.2 TimeProfiler
```python
class TimeProfiler:
    """시간 프로파일러"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._profiles: Dict[str, FunctionProfile] = {}
        self._lock = threading.Lock()

    def profile(self, name: Optional[str] = None):
        """
        프로파일링 데코레이터

        Args:
            name: 프로파일 이름 (None이면 함수명 사용)

        Usage:
            @profiler.profile()
            def my_function():
                pass
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                profile_name = name or f"{func.__module__}.{func.__name__}"

                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = (time.perf_counter() - start_time) * 1000  # ms
                    self._record(profile_name, elapsed)

            return wrapper
        return decorator

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        if self.enabled:
            self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self.enabled and hasattr(self, '_start_time'):
            elapsed = (time.perf_counter() - self._start_time) * 1000
            self._record("__context__", elapsed)

    def get_stats(self) -> Dict[str, FunctionProfile]:
        """전체 통계 조회"""
        with self._lock:
            return self._profiles.copy()

    def get_hotspots(self, top_n: int = 10) -> List[FunctionProfile]:
        """
        핫스팟 탐지 (가장 느린 함수)

        Args:
            top_n: 반환할 함수 수

        Returns:
            총 실행 시간 기준 상위 N개 함수
        """
        profiles = list(self._profiles.values())
        profiles.sort(key=lambda p: p.total_time, reverse=True)
        return profiles[:top_n]

    def reset(self):
        """통계 초기화"""
        with self._lock:
            self._profiles.clear()
```

### 4.3 MemoryProfiler
```python
class MemoryProfiler:
    """메모리 프로파일러"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._snapshots: List[MemorySnapshot] = []
        self._lock = threading.Lock()

    def profile(self, name: Optional[str] = None):
        """메모리 프로파일링 데코레이터"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                profile_name = name or f"{func.__module__}.{func.__name__}"

                # 실행 전 메모리
                memory_before = self._get_memory()

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    # 실행 후 메모리
                    memory_after = self._get_memory()
                    delta = memory_after - memory_before

                    self._record_snapshot(
                        profile_name,
                        memory_before,
                        memory_after,
                        delta
                    )

            return wrapper
        return decorator

    def _get_memory(self) -> float:
        """현재 프로세스 메모리 사용량 (MB)"""
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        return 0.0

    def detect_leaks(self, threshold_mb: float = 10.0) -> List[MemoryLeak]:
        """
        메모리 누수 탐지

        Args:
            threshold_mb: 누수 판정 임계값 (MB)

        Returns:
            메모리 누수 목록
        """
        leaks = []

        for snapshot in self._snapshots:
            if snapshot.memory_delta > threshold_mb:
                leaks.append(MemoryLeak(
                    function_name=snapshot.function_name,
                    memory_increase_mb=snapshot.memory_delta,
                    timestamp=snapshot.timestamp
                ))

        return leaks
```

### 4.4 CallStackProfiler
```python
class CallStackProfiler:
    """호출 스택 프로파일러"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._call_stack: List[CallFrame] = []
        self._call_graph: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def profile(self, name: Optional[str] = None):
        """호출 스택 추적 데코레이터"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                profile_name = name or f"{func.__module__}.{func.__name__}"

                # 현재 스택에 푸시
                frame = CallFrame(
                    function_name=profile_name,
                    depth=len(self._call_stack),
                    start_time=time.perf_counter()
                )

                with self._lock:
                    self._call_stack.append(frame)

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    # 스택에서 팝
                    with self._lock:
                        if self._call_stack:
                            frame = self._call_stack.pop()
                            frame.end_time = time.perf_counter()

                            # 호출 그래프 업데이트
                            if self._call_stack:
                                caller = self._call_stack[-1].function_name
                                if caller not in self._call_graph:
                                    self._call_graph[caller] = []
                                if profile_name not in self._call_graph[caller]:
                                    self._call_graph[caller].append(profile_name)

            return wrapper
        return decorator

    def get_call_graph(self) -> CallGraph:
        """호출 그래프 조회"""
        with self._lock:
            return CallGraph(self._call_graph.copy())

    def get_flame_graph(self) -> FlameGraph:
        """플레임 그래프 데이터 생성"""
        # 플레임 그래프 형식으로 변환
        pass
```

---

## 5. ProfilerManager (통합 관리)

### 5.1 싱글톤 매니저
```python
class ProfilerManager:
    """프로파일러 통합 관리 (싱글톤)"""

    def __init__(self):
        self.time_profiler = TimeProfiler(enabled=False)
        self.memory_profiler = MemoryProfiler(enabled=False)
        self.callstack_profiler = CallStackProfiler(enabled=False)
        self._enabled = False

    def enable(self, time: bool = True, memory: bool = False, callstack: bool = False):
        """
        프로파일링 활성화

        Args:
            time: 시간 프로파일링
            memory: 메모리 프로파일링
            callstack: 호출 스택 추적
        """
        self._enabled = True
        self.time_profiler.enabled = time
        self.memory_profiler.enabled = memory
        self.callstack_profiler.enabled = callstack

    def disable(self):
        """프로파일링 비활성화"""
        self._enabled = False
        self.time_profiler.enabled = False
        self.memory_profiler.enabled = False
        self.callstack_profiler.enabled = False

    def profile(self, name: Optional[str] = None,
                time: bool = True,
                memory: bool = False,
                callstack: bool = False):
        """
        통합 프로파일링 데코레이터

        Args:
            name: 프로파일 이름
            time: 시간 프로파일링
            memory: 메모리 프로파일링
            callstack: 호출 스택 추적

        Usage:
            @profiler.profile(time=True, memory=True)
            def my_function():
                pass
        """
        def decorator(func):
            # 데코레이터 체인
            wrapped = func

            if callstack and self.callstack_profiler.enabled:
                wrapped = self.callstack_profiler.profile(name)(wrapped)

            if memory and self.memory_profiler.enabled:
                wrapped = self.memory_profiler.profile(name)(wrapped)

            if time and self.time_profiler.enabled:
                wrapped = self.time_profiler.profile(name)(wrapped)

            return wrapped

        return decorator

    def get_report(self, format: str = "text") -> str:
        """
        통합 보고서 생성

        Args:
            format: 보고서 형식 ("text", "json", "html")

        Returns:
            보고서 문자열
        """
        if format == "text":
            reporter = TextReporter()
        elif format == "json":
            reporter = JSONReporter()
        elif format == "html":
            reporter = HTMLReporter()
        else:
            raise ValueError(f"Unknown format: {format}")

        return reporter.generate(self)


# 싱글톤 인스턴스
_profiler_manager: Optional[ProfilerManager] = None
_profiler_lock = threading.Lock()


def get_profiler() -> ProfilerManager:
    """프로파일러 매니저 싱글톤 인스턴스"""
    global _profiler_manager

    if _profiler_manager is None:
        with _profiler_lock:
            if _profiler_manager is None:
                _profiler_manager = ProfilerManager()

    return _profiler_manager
```

---

## 6. 보고서 생성

### 6.1 TextReporter (텍스트 보고서)
```
============================================================
Performance Profiling Report
============================================================

[Top 10 Hotspots by Total Time]
  1. motion_analyzer.analyze()           2345.67ms  (150 calls, avg: 15.64ms)
  2. pose_estimator.estimate()           1234.56ms  (300 calls, avg: 4.12ms)
  3. ball_detector.detect()               987.65ms  (300 calls, avg: 3.29ms)
  ...

[Function Details]
  motion_analyzer.analyze()
    Calls: 150
    Total: 2345.67ms
    Avg:   15.64ms (±3.45ms)
    Min:   8.23ms
    Max:   45.67ms
    Memory: +12.34 MB

[Call Graph]
  process_video()
    ├─ extract_frames()
    ├─ analyze_frames()
    │   ├─ pose_estimator.estimate()
    │   └─ ball_detector.detect()
    └─ generate_report()

[Memory Profile]
  Peak Memory: 512.34 MB
  Current Memory: 234.56 MB

  Top Memory Consumers:
    1. model.predict()    +128.45 MB
    2. load_video()        +89.23 MB
    ...

============================================================
```

### 6.2 JSONReporter (JSON 보고서)
```json
{
  "timestamp": "2026-02-10T12:34:56.789Z",
  "profiling_duration": 10.5,
  "time_profile": {
    "motion_analyzer.analyze": {
      "call_count": 150,
      "total_time": 2345.67,
      "avg_time": 15.64,
      "min_time": 8.23,
      "max_time": 45.67,
      "std_time": 3.45
    }
  },
  "memory_profile": {
    "peak_memory_mb": 512.34,
    "current_memory_mb": 234.56,
    "functions": [...]
  },
  "call_graph": {
    "process_video": ["extract_frames", "analyze_frames", "generate_report"],
    "analyze_frames": ["pose_estimator.estimate", "ball_detector.detect"]
  }
}
```

### 6.3 HTMLReporter (HTML 보고서)
- 인터랙티브 차트 (Chart.js)
- 콜 그래프 시각화 (D3.js)
- 플레임 그래프
- 필터링 및 정렬 기능

---

## 7. 실전 사용 패턴

### 7.1 기본 사용
```python
from core_foundation.monitoring.profiler import get_profiler

profiler = get_profiler()
profiler.enable(time=True, memory=False, callstack=False)

@profiler.profile()
def process_frame(frame):
    # 프레임 처리
    return result

# 실행
for frame in video:
    process_frame(frame)

# 보고서
report = profiler.get_report(format="text")
print(report)
```

### 7.2 조건부 프로파일링
```python
import os
from core_foundation.monitoring.profiler import get_profiler

profiler = get_profiler()

# 개발 환경에서만 활성화
if os.getenv("ENVIRONMENT") == "development":
    profiler.enable(time=True, memory=True, callstack=True)

@profiler.profile()
def analyze_motion(poses):
    # 분석 로직
    pass
```

### 7.3 컨텍스트 매니저
```python
from core_foundation.monitoring.profiler import TimeProfiler

profiler = TimeProfiler()

with profiler:
    # 이 블록의 실행 시간 측정
    result = expensive_operation()

stats = profiler.get_stats()
print(f"Execution time: {stats['__context__'].total_time:.2f}ms")
```

### 7.4 핫스팟 탐지
```python
from core_foundation.monitoring.profiler import get_profiler

profiler = get_profiler()
profiler.enable(time=True)

# 분석 실행
process_video(video_path)

# 상위 10개 핫스팟
hotspots = profiler.time_profiler.get_hotspots(top_n=10)
for i, profile in enumerate(hotspots, 1):
    print(f"{i}. {profile.function_name}: {profile.total_time:.2f}ms ({profile.call_count} calls)")
```

### 7.5 메모리 누수 탐지
```python
from core_foundation.monitoring.profiler import get_profiler

profiler = get_profiler()
profiler.enable(memory=True)

@profiler.profile()
def load_and_process():
    data = load_large_data()  # 잠재적 누수
    process_data(data)

# 여러 번 실행
for _ in range(100):
    load_and_process()

# 누수 탐지
leaks = profiler.memory_profiler.detect_leaks(threshold_mb=10.0)
for leak in leaks:
    print(f"Memory leak: {leak.function_name}, +{leak.memory_increase_mb:.2f} MB")
```

---

## 8. 성능 최적화

### 8.1 오버헤드 최소화
```python
# 비활성화 시 거의 제로 오버헤드
profiler = get_profiler()
profiler.disable()  # enabled=False

@profiler.profile()  # 체크만 하고 바로 반환
def my_function():
    pass

# 오버헤드: < 0.0001ms
```

### 8.2 샘플링 프로파일링
```python
from core_foundation.monitoring.profiler import SamplingProfiler

# 10% 샘플링 (무작위)
profiler = SamplingProfiler(sample_rate=0.1)

@profiler.profile()
def frequent_function():
    # 10번 호출 중 1번만 프로파일링
    pass
```

### 8.3 선택적 프로파일링
```python
# 특정 함수만 프로파일링
profiler = get_profiler()
profiler.enable(time=True, memory=False)  # 메모리 비활성화

@profiler.profile(time=True, memory=False)
def fast_function():
    pass  # 시간만 측정

@profiler.profile(time=False, memory=True)
def memory_intensive():
    pass  # 메모리만 측정
```

---

## 9. 오류 처리

### 9.1 프로파일링 실패
```python
# 프로파일링 중 예외 발생해도 원본 함수는 정상 실행
@profiler.profile()
def my_function():
    raise ValueError("Error")

try:
    my_function()
except ValueError:
    pass  # 원본 예외는 전파됨

# 프로파일링 실패는 로그만 남김
```

### 9.2 리소스 부족
```python
# 메모리 부족 시 자동으로 오래된 데이터 제거
profiler = TimeProfiler(max_profiles=1000)

# 1000개 초과 시 가장 오래된 것부터 제거
```

---

## 10. 테스트 전략

### 10.1 단위 테스트
- TimeProfiler 동작 검증
- MemoryProfiler 동작 검증
- CallStackProfiler 동작 검증
- 데코레이터 동작
- 컨텍스트 매니저 동작
- 통계 계산 정확성

### 10.2 성능 테스트
| 항목 | 목표 |
|------|------|
| 프로파일링 오버헤드 (활성화) | < 5% |
| 프로파일링 오버헤드 (비활성화) | < 0.1% |
| 함수 호출 추적 | < 0.01ms/call |
| 메모리 측정 | < 0.1ms |
| 보고서 생성 (1000 함수) | < 1초 |
| 메모리 사용량 (1000 함수) | < 50MB |

### 10.3 통합 테스트
- 실제 파이프라인 프로파일링
- 멀티스레드 환경
- 장시간 실행 (메모리 누수 검증)
- 보고서 생성 및 검증

---

## 11. 구현 체크리스트

### 11.1 핵심 클래스
- [ ] `ProfileMode` Enum
- [ ] `FunctionProfile` 데이터클래스
- [ ] `MemorySnapshot` 데이터클래스
- [ ] `CallFrame` 데이터클래스
- [ ] `TimeProfiler` 클래스
- [ ] `MemoryProfiler` 클래스
- [ ] `CallStackProfiler` 클래스
- [ ] `ProfilerManager` 싱글톤
- [ ] `get_profiler()` 팩토리 함수

### 11.2 보고서
- [ ] `Reporter` 기본 클래스
- [ ] `TextReporter` 클래스
- [ ] `JSONReporter` 클래스
- [ ] `HTMLReporter` 클래스

### 11.3 유틸리티
- [ ] `@profile` 데코레이터
- [ ] `SamplingProfiler` 클래스
- [ ] `CallGraph` 클래스
- [ ] `FlameGraph` 클래스
- [ ] 핫스팟 탐지 함수
- [ ] 메모리 누수 탐지 함수

---

## 12. 의존성

### 12.1 외부 라이브러리
```python
# 필수
import time
import threading
from functools import wraps
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict

# 선택 (메모리 프로파일링)
import psutil  # 메모리 측정
```

### 12.2 내부 의존성
```python
from core_foundation.monitoring.logger import get_logger
from core_foundation.monitoring.metrics import Timer, Statistics
```

---

## 13. 예상 파일 구조
```
core_foundation/
└── monitoring/
    ├── __init__.py
    ├── logger.py          ✅ 완료
    ├── metrics.py         ✅ 완료
    └── profiler.py        ← 이번 작업
```

---

## 14. 다음 단계
1. **profiler.py 구현** (약 900-1100줄)
2. **단위 테스트** (test_profiler.py)
3. **성능 테스트** (test_profiler_perf.py)
4. **통합 테스트** (test_profiler_integration.py)
5. **실제 파이프라인 적용**

---

**설계 작성**: 2026-02-10
**버전**: 1.0.0
**작성자**: COURTVIEW Team
