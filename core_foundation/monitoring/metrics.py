"""
core_foundation/monitoring/metrics.py

엔터프라이즈급 메트릭 시스템
- 4가지 메트릭 타입: Counter, Gauge, Histogram, Timer
- 리소스 모니터링: CPU, GPU, Memory
- 통계 집계: 평균, 백분위수, 롤링 윈도우
- 데이터 내보내기: JSON, CSV, Prometheus

Author: COURTVIEW Team
Version: 1.0.0
"""

import time
import threading
import statistics
import json
import csv
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum, auto
from collections import deque
from datetime import datetime
from pathlib import Path
from functools import wraps

# 리소스 모니터링 (선택적)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False

from core_foundation.monitoring.logger import get_logger

logger = get_logger(__name__)


# ==================== Enums ====================
class MetricType(Enum):
    """메트릭 타입"""
    COUNTER = auto()      # 누적 증가
    GAUGE = auto()        # 증가/감소 자유
    HISTOGRAM = auto()    # 값의 분포
    TIMER = auto()        # 시간 측정


# ==================== 데이터 클래스 ====================
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


@dataclass
class CPUUsage:
    """CPU 사용량"""
    percent: float                  # 전체 CPU 사용률 (%)
    per_core: List[float]          # 코어별 사용률 (%)
    load_average_1m: float         # 1분 부하 평균
    load_average_5m: float         # 5분 부하 평균
    load_average_15m: float        # 15분 부하 평균


@dataclass
class GPUUsage:
    """GPU 사용량"""
    id: int                        # GPU ID
    name: str                      # GPU 이름
    utilization: float             # GPU 사용률 (%)
    memory_used: float             # 메모리 사용량 (MB)
    memory_total: float            # 메모리 총량 (MB)
    memory_percent: float          # 메모리 사용률 (%)
    temperature: float             # 온도 (°C)
    power_usage: Optional[float]   # 전력 소비 (W)
    power_limit: Optional[float]   # 전력 제한 (W)


@dataclass
class MemoryUsage:
    """메모리 사용량"""
    total: float           # 총 메모리 (MB)
    used: float            # 사용 중 메모리 (MB)
    free: float            # 여유 메모리 (MB)
    percent: float         # 사용률 (%)
    swap_total: float      # 스왑 총량 (MB)
    swap_used: float       # 스왑 사용량 (MB)
    swap_percent: float    # 스왑 사용률 (%)


@dataclass
class ProcessMemory:
    """프로세스 메모리"""
    rss: float      # Resident Set Size (MB)
    vms: float      # Virtual Memory Size (MB)
    percent: float  # 시스템 대비 사용률 (%)


# ==================== 메트릭 베이스 클래스 ====================
class Metric:
    """메트릭 베이스 클래스"""

    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        """
        Args:
            name: 메트릭 이름
            description: 메트릭 설명
            labels: 라벨 (키-값 쌍)
        """
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.created_at = time.time()
        self._lock = threading.Lock()

    def get_label_string(self) -> str:
        """라벨 문자열 생성"""
        if not self.labels:
            return ""
        items = [f'{k}="{v}"' for k, v in sorted(self.labels.items())]
        return "{" + ",".join(items) + "}"


# ==================== Counter ====================
class Counter(Metric):
    """누적 증가만 가능한 카운터"""

    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, labels)
        self._value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        """
        카운터 증가

        Args:
            amount: 증가량 (>= 0)

        Raises:
            ValueError: amount < 0
        """
        if amount < 0:
            raise ValueError(f"Counter increment must be non-negative, got {amount}")

        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        """현재 값 조회"""
        with self._lock:
            return self._value

    def reset(self) -> None:
        """카운터 리셋 (테스트용)"""
        with self._lock:
            self._value = 0.0


# ==================== Gauge ====================
class Gauge(Metric):
    """증가/감소 자유로운 게이지"""

    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, labels)
        self._value = 0.0

    def set(self, value: float) -> None:
        """값 설정"""
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        """값 증가"""
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        """값 감소"""
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        """현재 값 조회"""
        with self._lock:
            return self._value


# ==================== Histogram ====================
class Histogram(Metric):
    """값의 분포를 추적하는 히스토그램"""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        max_samples: int = 10000,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            name: 메트릭 이름
            description: 메트릭 설명
            buckets: 버킷 경계값 리스트
            max_samples: 최대 샘플 수 (메모리 제한)
            labels: 라벨
        """
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.max_samples = max_samples

        # 데이터 저장
        self._samples: deque = deque(maxlen=max_samples)
        self._sum = 0.0
        self._count = 0

        # 버킷 카운트
        self._bucket_counts = {b: 0 for b in self.buckets}
        self._bucket_counts[float('inf')] = 0

    def observe(self, value: float) -> None:
        """
        값 관찰

        Args:
            value: 관찰값
        """
        with self._lock:
            self._samples.append(value)
            self._sum += value
            self._count += 1

            # 버킷 업데이트
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1
            self._bucket_counts[float('inf')] += 1

    def get_stats(self) -> Optional[Statistics]:
        """
        통계 계산

        Returns:
            Statistics 객체 또는 None (샘플 없음)
        """
        with self._lock:
            if not self._samples:
                return None

            samples = list(self._samples)

        # 통계 계산
        count = len(samples)
        sum_val = sum(samples)
        mean_val = sum_val / count
        min_val = min(samples)
        max_val = max(samples)

        # 표준편차
        std_val = statistics.stdev(samples) if count > 1 else 0.0

        # 백분위수
        sorted_samples = sorted(samples)
        p50 = self._percentile(sorted_samples, 50)
        p90 = self._percentile(sorted_samples, 90)
        p95 = self._percentile(sorted_samples, 95)
        p99 = self._percentile(sorted_samples, 99)

        return Statistics(
            count=count,
            sum=sum_val,
            mean=mean_val,
            median=p50,
            std=std_val,
            min=min_val,
            max=max_val,
            p50=p50,
            p90=p90,
            p95=p95,
            p99=p99
        )

    def get_bucket_counts(self) -> Dict[float, int]:
        """버킷 카운트 조회"""
        with self._lock:
            return self._bucket_counts.copy()

    @staticmethod
    def _percentile(sorted_data: List[float], percentile: float) -> float:
        """백분위수 계산 (선형 보간)"""
        if not sorted_data:
            return 0.0

        if percentile <= 0:
            return sorted_data[0]
        if percentile >= 100:
            return sorted_data[-1]

        index = (len(sorted_data) - 1) * percentile / 100.0
        lower = int(index)
        upper = lower + 1

        if upper >= len(sorted_data):
            return sorted_data[lower]

        fraction = index - lower
        return sorted_data[lower] + (sorted_data[upper] - sorted_data[lower]) * fraction


# ==================== Timer ====================
class Timer(Metric):
    """시간 측정 타이머 (컨텍스트 매니저, 데코레이터)"""

    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        super().__init__(name, description, labels)
        # 내부적으로 Histogram 사용 (단위: 밀리초)
        self._histogram = Histogram(
            name=name,
            description=description,
            buckets=[0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000],  # ms
            labels=labels
        )
        self._start_time: Optional[float] = None

    def __enter__(self) -> "Timer":
        """컨텍스트 매니저 진입"""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """컨텍스트 매니저 종료"""
        if self._start_time is not None:
            elapsed = (time.perf_counter() - self._start_time) * 1000  # ms
            self._histogram.observe(elapsed)
            self._start_time = None

    def time(self) -> Callable:
        """
        데코레이터

        Usage:
            @timer.time()
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    def observe(self, value: float) -> None:
        """수동으로 시간 기록 (ms)"""
        self._histogram.observe(value)

    def get_stats(self) -> Optional[Statistics]:
        """통계 조회"""
        return self._histogram.get_stats()


# ==================== 롤링 윈도우 ====================
class RollingWindow:
    """고정 크기 롤링 윈도우"""

    def __init__(self, max_size: int = 1000):
        """
        Args:
            max_size: 최대 샘플 수
        """
        self.max_size = max_size
        self._samples: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, value: float) -> None:
        """값 추가"""
        with self._lock:
            self._samples.append(value)

    def get_stats(self) -> Optional[Statistics]:
        """통계 계산"""
        with self._lock:
            if not self._samples:
                return None
            samples = list(self._samples)

        count = len(samples)
        sum_val = sum(samples)
        mean_val = sum_val / count
        min_val = min(samples)
        max_val = max(samples)
        std_val = statistics.stdev(samples) if count > 1 else 0.0

        sorted_samples = sorted(samples)
        p50 = Histogram._percentile(sorted_samples, 50)
        p90 = Histogram._percentile(sorted_samples, 90)
        p95 = Histogram._percentile(sorted_samples, 95)
        p99 = Histogram._percentile(sorted_samples, 99)

        return Statistics(
            count=count,
            sum=sum_val,
            mean=mean_val,
            median=p50,
            std=std_val,
            min=min_val,
            max=max_val,
            p50=p50,
            p90=p90,
            p95=p95,
            p99=p99
        )

    def clear(self) -> None:
        """샘플 초기화"""
        with self._lock:
            self._samples.clear()


# ==================== 시간 기반 윈도우 ====================
class TimeWindow:
    """시간 기반 윈도우"""

    def __init__(self, duration_seconds: float = 60.0):
        """
        Args:
            duration_seconds: 윈도우 지속 시간 (초)
        """
        self.duration = duration_seconds
        self._samples: deque = deque()  # (timestamp, value)
        self._lock = threading.Lock()

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        """
        값 추가

        Args:
            value: 값
            timestamp: 타임스탬프 (None이면 현재 시각)
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self._samples.append((timestamp, value))
            self._cleanup(timestamp)

    def _cleanup(self, current_time: float) -> None:
        """오래된 샘플 제거"""
        cutoff = current_time - self.duration
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def get_stats(self) -> Optional[Statistics]:
        """통계 계산"""
        with self._lock:
            if not self._samples:
                return None

            # 오래된 데이터 정리
            self._cleanup(time.time())

            if not self._samples:
                return None

            values = [v for _, v in self._samples]

        count = len(values)
        sum_val = sum(values)
        mean_val = sum_val / count
        min_val = min(values)
        max_val = max(values)
        std_val = statistics.stdev(values) if count > 1 else 0.0

        sorted_values = sorted(values)
        p50 = Histogram._percentile(sorted_values, 50)
        p90 = Histogram._percentile(sorted_values, 90)
        p95 = Histogram._percentile(sorted_values, 95)
        p99 = Histogram._percentile(sorted_values, 99)

        return Statistics(
            count=count,
            sum=sum_val,
            mean=mean_val,
            median=p50,
            std=std_val,
            min=min_val,
            max=max_val,
            p50=p50,
            p90=p90,
            p95=p95,
            p99=p99
        )

    def get_rate(self) -> float:
        """초당 평균 값 (샘플 수 / 시간)"""
        with self._lock:
            if len(self._samples) < 2:
                return 0.0

            self._cleanup(time.time())
            if len(self._samples) < 2:
                return 0.0

            duration = self._samples[-1][0] - self._samples[0][0]
            if duration <= 0:
                return 0.0

            return len(self._samples) / duration


# ==================== 리소스 모니터 ====================
class CPUMonitor:
    """CPU 모니터"""

    def get_usage(self) -> Optional[CPUUsage]:
        """CPU 사용량 조회"""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, CPU monitoring disabled")
            return None

        try:
            percent = psutil.cpu_percent(interval=0.1)
            per_core = psutil.cpu_percent(interval=0.1, percpu=True)

            # 부하 평균 (Unix 계열만)
            try:
                load_avg = psutil.getloadavg()
                load_1m, load_5m, load_15m = load_avg
            except (AttributeError, OSError):
                # Windows는 getloadavg() 없음
                load_1m = load_5m = load_15m = 0.0

            return CPUUsage(
                percent=percent,
                per_core=per_core,
                load_average_1m=load_1m,
                load_average_5m=load_5m,
                load_average_15m=load_15m
            )
        except Exception as e:
            logger.error(f"Failed to get CPU usage: {e}")
            return None


class GPUMonitor:
    """GPU 모니터"""

    def get_usage(self, gpu_id: int = 0) -> Optional[GPUUsage]:
        """
        GPU 사용량 조회

        Args:
            gpu_id: GPU ID

        Returns:
            GPUUsage 또는 None (GPU 없음/오류)
        """
        if not GPUTIL_AVAILABLE:
            logger.warning("GPUtil not available, GPU monitoring disabled")
            return None

        try:
            gpus = GPUtil.getGPUs()
            if not gpus or gpu_id >= len(gpus):
                logger.warning(f"GPU {gpu_id} not found")
                return None

            gpu = gpus[gpu_id]

            return GPUUsage(
                id=gpu.id,
                name=gpu.name,
                utilization=gpu.load * 100,  # 0-1 → 0-100%
                memory_used=gpu.memoryUsed,
                memory_total=gpu.memoryTotal,
                memory_percent=(gpu.memoryUsed / gpu.memoryTotal * 100) if gpu.memoryTotal > 0 else 0.0,
                temperature=gpu.temperature,
                power_usage=None,  # GPUtil doesn't provide power info
                power_limit=None
            )
        except Exception as e:
            logger.error(f"Failed to get GPU usage: {e}")
            return None

    def get_all_gpus(self) -> List[GPUUsage]:
        """모든 GPU 사용량 조회"""
        if not GPUTIL_AVAILABLE:
            return []

        try:
            gpus = GPUtil.getGPUs()
            results = []

            for gpu in gpus:
                results.append(GPUUsage(
                    id=gpu.id,
                    name=gpu.name,
                    utilization=gpu.load * 100,
                    memory_used=gpu.memoryUsed,
                    memory_total=gpu.memoryTotal,
                    memory_percent=(gpu.memoryUsed / gpu.memoryTotal * 100) if gpu.memoryTotal > 0 else 0.0,
                    temperature=gpu.temperature,
                    power_usage=None,
                    power_limit=None
                ))

            return results
        except Exception as e:
            logger.error(f"Failed to get GPU list: {e}")
            return []


class MemoryMonitor:
    """메모리 모니터"""

    def get_system_memory(self) -> Optional[MemoryUsage]:
        """시스템 메모리 사용량 조회"""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, memory monitoring disabled")
            return None

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return MemoryUsage(
                total=mem.total / (1024 * 1024),      # Bytes → MB
                used=mem.used / (1024 * 1024),
                free=mem.available / (1024 * 1024),
                percent=mem.percent,
                swap_total=swap.total / (1024 * 1024),
                swap_used=swap.used / (1024 * 1024),
                swap_percent=swap.percent
            )
        except Exception as e:
            logger.error(f"Failed to get system memory: {e}")
            return None

    def get_process_memory(self) -> Optional[ProcessMemory]:
        """프로세스 메모리 사용량 조회"""
        if not PSUTIL_AVAILABLE:
            return None

        try:
            process = psutil.Process()
            mem_info = process.memory_info()

            return ProcessMemory(
                rss=mem_info.rss / (1024 * 1024),  # Bytes → MB
                vms=mem_info.vms / (1024 * 1024),
                percent=process.memory_percent()
            )
        except Exception as e:
            logger.error(f"Failed to get process memory: {e}")
            return None


class ResourceMonitor:
    """통합 리소스 모니터"""

    def __init__(self):
        self.cpu = CPUMonitor()
        self.gpu = GPUMonitor()
        self.memory = MemoryMonitor()

    def get_all(self) -> Dict[str, Any]:
        """모든 리소스 정보 조회"""
        return {
            "cpu": self.cpu.get_usage(),
            "gpu": self.gpu.get_usage(),
            "memory": self.memory.get_system_memory(),
            "process_memory": self.memory.get_process_memory()
        }


# ==================== 메트릭 레지스트리 ====================
class MetricsRegistry:
    """메트릭 레지스트리 (싱글톤)"""

    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()

    def counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """
        Counter 생성 또는 조회

        Args:
            name: 메트릭 이름
            description: 설명
            labels: 라벨

        Returns:
            Counter 인스턴스
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Counter(name, description, labels)
            return self._metrics[key]

    def gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """
        Gauge 생성 또는 조회

        Args:
            name: 메트릭 이름
            description: 설명
            labels: 라벨

        Returns:
            Gauge 인스턴스
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Gauge(name, description, labels)
            return self._metrics[key]

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Histogram:
        """
        Histogram 생성 또는 조회

        Args:
            name: 메트릭 이름
            description: 설명
            buckets: 버킷 경계값
            labels: 라벨

        Returns:
            Histogram 인스턴스
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Histogram(name, description, buckets, labels=labels)
            return self._metrics[key]

    def timer(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None
    ) -> Timer:
        """
        Timer 생성 또는 조회

        Args:
            name: 메트릭 이름
            description: 설명
            labels: 라벨

        Returns:
            Timer 인스턴스
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Timer(name, description, labels)
            return self._metrics[key]

    def get_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[Metric]:
        """메트릭 조회"""
        key = self._make_key(name, labels)
        with self._lock:
            return self._metrics.get(key)

    def get_all_metrics(self) -> Dict[str, Metric]:
        """모든 메트릭 조회"""
        with self._lock:
            return self._metrics.copy()

    def get_metrics(
        self,
        prefix: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, Metric]:
        """
        메트릭 필터링

        Args:
            prefix: 이름 접두사
            labels: 라벨 필터

        Returns:
            필터링된 메트릭 딕셔너리
        """
        with self._lock:
            results = {}

            for key, metric in self._metrics.items():
                # 접두사 필터
                if prefix and not metric.name.startswith(prefix):
                    continue

                # 라벨 필터
                if labels:
                    if not all(metric.labels.get(k) == v for k, v in labels.items()):
                        continue

                results[key] = metric

            return results

    def remove_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        """메트릭 제거"""
        key = self._make_key(name, labels)
        with self._lock:
            self._metrics.pop(key, None)

    def clear(self) -> None:
        """모든 메트릭 제거"""
        with self._lock:
            self._metrics.clear()

    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]]) -> str:
        """메트릭 키 생성 (이름 + 라벨)"""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# ==================== 내보내기 ====================
class Exporter:
    """메트릭 내보내기 기본 클래스"""

    def export(self, registry: MetricsRegistry) -> Any:
        """
        메트릭 내보내기

        Args:
            registry: 메트릭 레지스트리

        Returns:
            내보내기 결과
        """
        raise NotImplementedError


class JSONExporter(Exporter):
    """JSON 포맷 내보내기"""

    def export(self, registry: MetricsRegistry) -> str:
        """
        JSON 형식으로 내보내기

        Args:
            registry: 메트릭 레지스트리

        Returns:
            JSON 문자열
        """
        metrics_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": {}
        }

        for key, metric in registry.get_all_metrics().items():
            metric_data = {
                "type": metric.__class__.__name__.lower(),
                "description": metric.description,
                "labels": metric.labels
            }

            if isinstance(metric, Counter):
                metric_data["value"] = metric.value

            elif isinstance(metric, Gauge):
                metric_data["value"] = metric.value

            elif isinstance(metric, (Histogram, Timer)):
                stats = metric.get_stats()
                if stats:
                    metric_data.update({
                        "count": stats.count,
                        "sum": stats.sum,
                        "mean": stats.mean,
                        "median": stats.median,
                        "std": stats.std,
                        "min": stats.min,
                        "max": stats.max,
                        "p50": stats.p50,
                        "p90": stats.p90,
                        "p95": stats.p95,
                        "p99": stats.p99
                    })

                    # 히스토그램 버킷
                    if isinstance(metric, Histogram):
                        buckets = metric.get_bucket_counts()
                        metric_data["buckets"] = {str(k): v for k, v in buckets.items()}

            metrics_data["metrics"][key] = metric_data

        return json.dumps(metrics_data, indent=2, ensure_ascii=False)

    def export_to_file(self, registry: MetricsRegistry, filepath: str) -> None:
        """파일로 내보내기"""
        data = self.export(registry)
        Path(filepath).write_text(data, encoding="utf-8")


class CSVExporter(Exporter):
    """CSV 포맷 내보내기"""

    def export(self, registry: MetricsRegistry) -> str:
        """
        CSV 형식으로 내보내기

        Args:
            registry: 메트릭 레지스트리

        Returns:
            CSV 문자열
        """
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # 헤더
        writer.writerow([
            "timestamp", "metric_name", "metric_type", "labels",
            "value", "count", "mean", "median", "std", "min", "max",
            "p50", "p90", "p95", "p99"
        ])

        timestamp = datetime.utcnow().isoformat() + "Z"

        for key, metric in registry.get_all_metrics().items():
            label_str = json.dumps(metric.labels) if metric.labels else ""
            row = [timestamp, metric.name, metric.__class__.__name__.lower(), label_str]

            if isinstance(metric, Counter):
                row.extend([metric.value, "", "", "", "", "", "", "", "", "", ""])

            elif isinstance(metric, Gauge):
                row.extend([metric.value, "", "", "", "", "", "", "", "", "", ""])

            elif isinstance(metric, (Histogram, Timer)):
                stats = metric.get_stats()
                if stats:
                    row.extend([
                        stats.sum, stats.count, stats.mean, stats.median, stats.std,
                        stats.min, stats.max, stats.p50, stats.p90, stats.p95, stats.p99
                    ])
                else:
                    row.extend([""] * 11)

            writer.writerow(row)

        return output.getvalue()

    def export_to_file(self, registry: MetricsRegistry, filepath: str) -> None:
        """파일로 내보내기"""
        data = self.export(registry)
        Path(filepath).write_text(data, encoding="utf-8")


class PrometheusExporter(Exporter):
    """Prometheus 포맷 내보내기"""

    def export(self, registry: MetricsRegistry) -> str:
        """
        Prometheus 텍스트 형식으로 내보내기

        Args:
            registry: 메트릭 레지스트리

        Returns:
            Prometheus 포맷 문자열
        """
        lines = []

        for key, metric in registry.get_all_metrics().items():
            # HELP
            if metric.description:
                lines.append(f"# HELP {metric.name} {metric.description}")

            # TYPE
            metric_type = "counter" if isinstance(metric, Counter) else \
                         "gauge" if isinstance(metric, Gauge) else \
                         "histogram"
            lines.append(f"# TYPE {metric.name} {metric_type}")

            label_str = metric.get_label_string()

            if isinstance(metric, Counter):
                lines.append(f"{metric.name}{label_str} {metric.value}")

            elif isinstance(metric, Gauge):
                lines.append(f"{metric.name}{label_str} {metric.value}")

            elif isinstance(metric, (Histogram, Timer)):
                # 히스토그램 버킷
                if isinstance(metric, Histogram):
                    buckets = metric.get_bucket_counts()
                    for bucket, count in sorted(buckets.items()):
                        bucket_label = f'{{le="{bucket}"}}'
                        lines.append(f"{metric.name}_bucket{bucket_label} {count}")

                # 합계 및 카운트
                stats = metric.get_stats()
                if stats:
                    lines.append(f"{metric.name}_sum{label_str} {stats.sum}")
                    lines.append(f"{metric.name}_count{label_str} {stats.count}")

            lines.append("")  # 빈 줄

        return "\n".join(lines)

    def export_to_file(self, registry: MetricsRegistry, filepath: str) -> None:
        """파일로 내보내기"""
        data = self.export(registry)
        Path(filepath).write_text(data, encoding="utf-8")


# ==================== 싱글톤 팩토리 ====================
_registry: Optional[MetricsRegistry] = None
_registry_lock = threading.Lock()


def get_metrics_registry() -> MetricsRegistry:
    """
    메트릭 레지스트리 싱글톤 인스턴스 조회

    Returns:
        MetricsRegistry 인스턴스 (스레드 안전)
    """
    global _registry

    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = MetricsRegistry()

    return _registry


# ==================== 유틸리티 함수 ====================
def measure_time(func: Callable, iterations: int = 1000) -> float:
    """
    함수 실행 시간 측정 (평균, 밀리초)

    Args:
        func: 측정할 함수
        iterations: 반복 횟수

    Returns:
        평균 실행 시간 (ms)
    """
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)

    return statistics.mean(times)


def calculate_rate(count: int, duration_seconds: float) -> float:
    """
    처리율 계산 (초당 처리량)

    Args:
        count: 처리 건수
        duration_seconds: 지속 시간 (초)

    Returns:
        초당 처리량 (ops/sec)
    """
    if duration_seconds <= 0:
        return 0.0
    return count / duration_seconds


def format_bytes(bytes_value: float) -> str:
    """
    바이트를 읽기 쉬운 형식으로 변환

    Args:
        bytes_value: 바이트 값

    Returns:
        포맷된 문자열 (예: "1.23 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


# ==================== 데코레이터 ====================
def timed(metric_name: str, description: str = "") -> Callable:
    """
    함수 실행 시간 측정 데코레이터

    Args:
        metric_name: 메트릭 이름
        description: 설명

    Usage:
        @timed("my_function_time", "My function execution time")
        def my_function():
            pass
    """
    registry = get_metrics_registry()
    timer = registry.timer(metric_name, description)

    def decorator(func: Callable) -> Callable:
        return timer.time()(func)

    return decorator
