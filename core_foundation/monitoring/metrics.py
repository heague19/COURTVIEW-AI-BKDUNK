# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: metrics.py
설명: Prometheus 스타일 메트릭 수집 (Counter, Gauge, Histogram, Summary) - Desktop Edition

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - Counter: 단조 증가 카운터 (요청 수, 에러 수 등)
    - Gauge: 현재 값 (메모리 사용량, 활성 연결 수 등)
    - Histogram: 분포 측정 (응답 시간, 처리량 등)
    - Summary: 분위수 기반 요약 (지연 시간 백분위)
    - 레이블 기반 메트릭 다차원 분류
    - Prometheus / JSON 형식 내보내기 지원
    - 스레드 안전 설계
    - DI 컨테이너 등록 대상

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 메모리 효율: 오래된 데이터 자동 정리
    - 확장성: 커스텀 메트릭 타입 지원
    - Prometheus 호환: OpenMetrics 형식

Desktop 특화 메트릭:
    - GPU 온도/VRAM/활용률 게이지
    - 카메라별 FPS 및 활성 카메라 수 게이지
    - 시스템 리소스 (CPU/RAM/디스크) 게이지
    - 모델 추론 시간 히스토그램
    - 프레임 처리 시간 히스토그램

농구 분석 특화 메트릭:
    - FPS 히스토그램 버킷 (15-120 FPS 범위)
    - 정확도 히스토그램 버킷 (0-100% 범위)
    - 분석 시간 측정 데코레이터

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    metrics = MetricsCollector(config_loader)

    # 카운터 증가
    metrics.counter("requests_total", labels={"endpoint": "/analyze"}).inc()

    # 게이지 설정
    metrics.gauge("active_sessions").set(42)

    # 히스토그램 관측
    metrics.histogram("response_time_seconds").observe(0.125)

    # GPU 메트릭 조회
    metrics.gauge("gpu_temperature_celsius").set(72.5)
    metrics.gauge("gpu_memory_used_bytes").set(4 * 1024**3)

    # 데코레이터 사용
    @measure_latency("analysis_duration_seconds")
    def analyze_motion(video):
        ...
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import logging
import threading
import time
import math
import bisect
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Generator,
    TypeVar,
)

# ============================================================
# core_foundation 내부 임포트 (shared/utils 불필요 - datetime/time 직접 사용)
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 타입 변수
# ============================================================
F = TypeVar("F", bound=Callable[..., Any])

# ============================================================
# 상수 정의 (Prometheus 호환)
# ============================================================
# 메트릭 이름 접두사 (기본값, YAML에서 오버라이드 가능)
METRIC_PREFIX: str = "courtview"

# 기본 히스토그램 버킷 (응답 시간용, 초 단위)
DEFAULT_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.075,
    0.1, 0.25, 0.5, 0.75,
    1.0, 2.5, 5.0, 7.5, 10.0,
    float("inf"),
)

# FPS 히스토그램 버킷 (농구 분석 특화)
FPS_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    10.0, 15.0, 20.0, 24.0, 25.0, 30.0,
    45.0, 50.0, 60.0, 90.0, 120.0,
    float("inf"),
)

# 정확도 히스토그램 버킷 (0-100%)
ACCURACY_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.5, 0.6, 0.7, 0.75, 0.8,
    0.85, 0.9, 0.92, 0.95, 0.98, 1.0,
)

# 모델 추론 시간 히스토그램 버킷 (Desktop 특화, 초 단위)
MODEL_INFERENCE_BUCKETS: tuple[float, ...] = (
    0.001, 0.002, 0.005, 0.008, 0.01,
    0.015, 0.02, 0.03, 0.05, 0.1,
    float("inf"),
)

# 프레임 처리 시간 히스토그램 버킷 (Desktop 특화, 초 단위)
FRAME_PROCESSING_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.016, 0.02, 0.033,
    0.05, 0.066, 0.1, 0.2, 0.5,
    float("inf"),
)

# GPU 온도 히스토그램 버킷 (섭씨)
GPU_TEMPERATURE_BUCKETS: tuple[float, ...] = (
    40.0, 50.0, 60.0, 65.0, 70.0,
    75.0, 80.0, 85.0, 90.0, 95.0,
    float("inf"),
)

# 기본 분위수 (Summary용)
DEFAULT_QUANTILES: tuple[float, ...] = (0.5, 0.9, 0.95, 0.99)

# 메트릭 최대 개수 (기본값, YAML에서 오버라이드 가능)
MAX_METRICS: int = 10000

# Summary 윈도우 크기 (초, 기본값)
SUMMARY_WINDOW_SECONDS: float = 600.0  # 10분

# Summary 윈도우 내 최대 관측 수 (기본값)
SUMMARY_MAX_OBSERVATIONS: int = 10000

# YAML 설정 키
CONFIG_KEY_METRICS: str = "metrics"
CONFIG_KEY_ENABLED: str = "enabled"
CONFIG_KEY_PREFIX: str = "prefix"
CONFIG_KEY_MAX_METRICS: str = "max_metrics"
CONFIG_KEY_SUMMARY_WINDOW: str = "summary_window_seconds"
CONFIG_KEY_SUMMARY_MAX_OBS: str = "summary_max_observations"


# ============================================================
# Enum 정의
# ============================================================
class MetricType(Enum):
    """
    메트릭 타입.

    Prometheus 호환 메트릭 타입을 정의합니다.

    Attributes:
        COUNTER: 단조 증가 카운터
        GAUGE: 현재 값 (증가/감소 가능)
        HISTOGRAM: 버킷 기반 분포
        SUMMARY: 분위수 기반 요약
    """

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricUnit(Enum):
    """
    메트릭 단위.

    메트릭 값의 단위를 정의합니다.

    Attributes:
        SECONDS: 시간 (초)
        MILLISECONDS: 시간 (밀리초)
        BYTES: 데이터 크기
        COUNT: 개수
        PERCENT: 백분율 (0-1)
        FPS: 초당 프레임
        RATIO: 비율 (0-1)
    """

    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    BYTES = "bytes"
    COUNT = "count"
    PERCENT = "percent"
    FPS = "fps"
    RATIO = "ratio"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(frozen=True)
class MetricLabels:
    """
    메트릭 레이블.

    메트릭을 다차원으로 분류하는 레이블 집합입니다.
    불변(frozen)으로 해시 가능합니다.

    Attributes:
        labels: 레이블 키-값 쌍
    """

    labels: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, labels: dict[str, str] | None = None) -> "MetricLabels":
        """
        딕셔너리에서 MetricLabels 생성.

        Args:
            labels: 레이블 딕셔너리

        Returns:
            MetricLabels 인스턴스
        """
        if not labels:
            return cls()

        # 정렬된 튜플로 변환 (일관된 해시)
        sorted_labels = tuple(sorted(labels.items()))
        return cls(labels=sorted_labels)

    def to_dict(self) -> dict[str, str]:
        """딕셔너리로 변환."""
        return dict(self.labels)

    def to_prometheus_string(self) -> str:
        """
        Prometheus 형식 문자열로 변환.

        Returns:
            '{label1="value1",label2="value2"}' 형식
        """
        if not self.labels:
            return ""

        parts = [f'{k}="{v}"' for k, v in self.labels]
        return "{" + ",".join(parts) + "}"

    def __hash__(self) -> int:
        """해시 값."""
        return hash(self.labels)


@dataclass
class MetricValue:
    """
    메트릭 값.

    단일 메트릭 측정값을 나타냅니다.

    Attributes:
        value: 메트릭 값
        timestamp: 측정 시각
        labels: 메트릭 레이블
    """

    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: MetricLabels = field(default_factory=MetricLabels)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels.to_dict(),
        }


@dataclass
class MetricSnapshot:
    """
    메트릭 스냅샷.

    특정 시점의 메트릭 전체 상태입니다.

    Attributes:
        name: 메트릭 이름
        type: 메트릭 타입
        help: 메트릭 설명
        unit: 메트릭 단위
        values: 레이블별 값 목록
        timestamp: 스냅샷 시각
    """

    name: str
    type: MetricType
    help: str = ""
    unit: MetricUnit | None = None
    values: list[MetricValue] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "name": self.name,
            "type": self.type.value,
            "help": self.help,
            "unit": self.unit.value if self.unit else None,
            "values": [v.to_dict() for v in self.values],
            "timestamp": self.timestamp.isoformat(),
        }

    def to_prometheus(self) -> str:
        """
        Prometheus 형식으로 변환.

        Returns:
            Prometheus exposition format 문자열
        """
        lines = []

        # HELP 라인
        if self.help:
            lines.append(f"# HELP {self.name} {self.help}")

        # TYPE 라인
        lines.append(f"# TYPE {self.name} {self.type.value}")

        # 값 라인들
        for mv in self.values:
            label_str = mv.labels.to_prometheus_string()
            lines.append(f"{self.name}{label_str} {mv.value}")

        return "\n".join(lines)


# ============================================================
# 메트릭 기본 클래스
# ============================================================
class BaseMetric:
    """
    메트릭 기본 클래스.

    모든 메트릭 타입의 공통 기능을 제공합니다.

    Attributes:
        name: 메트릭 이름
        help: 메트릭 설명
        unit: 메트릭 단위
        metric_type: 메트릭 타입
    """

    def __init__(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
        metric_type: MetricType = MetricType.GAUGE,
    ) -> None:
        """
        메트릭 초기화.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위
            metric_type: 메트릭 타입
        """
        self.name = name
        self.help = help
        self.unit = unit
        self.metric_type = metric_type
        self._lock = threading.RLock()
        self._created_at = datetime.now(timezone.utc)

    def _validate_labels(self, labels: dict[str, str] | None) -> MetricLabels:
        """레이블 검증 및 변환."""
        if labels is None:
            return MetricLabels()

        # 레이블 키/값 검증
        for key, value in labels.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"레이블 키와 값은 문자열이어야 합니다: {key}={value}")
            if not key:
                raise ValueError("레이블 키는 비어있을 수 없습니다")

        return MetricLabels.from_dict(labels)

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷 반환."""
        raise NotImplementedError("하위 클래스에서 구현")


# ============================================================
# Counter 메트릭
# ============================================================
class Counter(BaseMetric):
    """
    카운터 메트릭.

    단조 증가하는 값을 추적합니다.
    재시작 시 0으로 리셋됩니다.

    사용 예:
        - 요청 총 수
        - 에러 발생 횟수
        - 처리된 바이트 수

    Example:
        >>> counter = Counter("requests_total", help="Total requests")
        >>> counter.inc()
        >>> counter.inc(5)
        >>> counter.labels({"method": "GET"}).inc()
    """

    def __init__(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
    ) -> None:
        """카운터 초기화."""
        super().__init__(name, help, unit, MetricType.COUNTER)
        self._values: dict[MetricLabels, float] = defaultdict(float)

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        카운터 증가.

        Args:
            value: 증가량 (양수만 허용)
            labels: 메트릭 레이블

        Raises:
            ValueError: 음수 값인 경우
        """
        if value < 0:
            raise ValueError("카운터는 음수로 증가할 수 없습니다")

        metric_labels = self._validate_labels(labels)

        with self._lock:
            self._values[metric_labels] += value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """
        현재 값 조회.

        Args:
            labels: 메트릭 레이블

        Returns:
            현재 카운터 값
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._values.get(metric_labels, 0.0)

    def labels(self, labels: dict[str, str]) -> "CounterChild":
        """
        레이블이 지정된 카운터 자식 반환.

        Args:
            labels: 메트릭 레이블

        Returns:
            CounterChild 인스턴스
        """
        return CounterChild(self, labels)

    def reset(self) -> None:
        """카운터 리셋 (테스트용)."""
        with self._lock:
            self._values.clear()

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷."""
        with self._lock:
            values = [
                MetricValue(value=v, labels=l)
                for l, v in self._values.items()
            ]

            return MetricSnapshot(
                name=self.name,
                type=self.metric_type,
                help=self.help,
                unit=self.unit,
                values=values,
            )


class CounterChild:
    """레이블이 지정된 카운터 자식."""

    def __init__(self, parent: Counter, labels: dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels

    def inc(self, value: float = 1.0) -> None:
        """카운터 증가."""
        self._parent.inc(value, self._labels)

    def get(self) -> float:
        """현재 값 조회."""
        return self._parent.get(self._labels)


# ============================================================
# Gauge 메트릭
# ============================================================
class Gauge(BaseMetric):
    """
    게이지 메트릭.

    현재 값을 추적합니다. 증가/감소 모두 가능합니다.

    사용 예:
        - 현재 메모리 사용량
        - 활성 연결 수
        - 현재 온도
        - 진행률

    Example:
        >>> gauge = Gauge("memory_bytes", help="Memory usage")
        >>> gauge.set(1024000)
        >>> gauge.inc(100)
        >>> gauge.dec(50)
    """

    def __init__(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
    ) -> None:
        """게이지 초기화."""
        super().__init__(name, help, unit, MetricType.GAUGE)
        self._values: dict[MetricLabels, float] = defaultdict(float)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """
        값 설정.

        Args:
            value: 설정할 값
            labels: 메트릭 레이블
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            self._values[metric_labels] = value

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        값 증가.

        Args:
            value: 증가량
            labels: 메트릭 레이블
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            self._values[metric_labels] += value

    def dec(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        값 감소.

        Args:
            value: 감소량
            labels: 메트릭 레이블
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            self._values[metric_labels] -= value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """
        현재 값 조회.

        Args:
            labels: 메트릭 레이블

        Returns:
            현재 게이지 값
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._values.get(metric_labels, 0.0)

    def labels(self, labels: dict[str, str]) -> "GaugeChild":
        """레이블이 지정된 게이지 자식 반환."""
        return GaugeChild(self, labels)

    def set_to_current_time(self, labels: dict[str, str] | None = None) -> None:
        """현재 시간(Unix timestamp)으로 설정."""
        self.set(time.time(), labels)

    @contextmanager
    def track_inprogress(
        self, labels: dict[str, str] | None = None
    ) -> Generator[None, None, None]:
        """
        진행 중인 작업 추적.

        Context manager로 사용하여 진행 중인 작업 수를 추적합니다.

        Example:
            >>> with gauge.track_inprogress():
            ...     process_request()
        """
        self.inc(1.0, labels)
        try:
            yield
        finally:
            self.dec(1.0, labels)

    def reset(self) -> None:
        """게이지 리셋 (테스트용)."""
        with self._lock:
            self._values.clear()

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷."""
        with self._lock:
            values = [
                MetricValue(value=v, labels=l)
                for l, v in self._values.items()
            ]

            return MetricSnapshot(
                name=self.name,
                type=self.metric_type,
                help=self.help,
                unit=self.unit,
                values=values,
            )


class GaugeChild:
    """레이블이 지정된 게이지 자식."""

    def __init__(self, parent: Gauge, labels: dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels

    def set(self, value: float) -> None:
        """값 설정."""
        self._parent.set(value, self._labels)

    def inc(self, value: float = 1.0) -> None:
        """값 증가."""
        self._parent.inc(value, self._labels)

    def dec(self, value: float = 1.0) -> None:
        """값 감소."""
        self._parent.dec(value, self._labels)

    def get(self) -> float:
        """현재 값 조회."""
        return self._parent.get(self._labels)


# ============================================================
# Histogram 메트릭
# ============================================================
class Histogram(BaseMetric):
    """
    히스토그램 메트릭.

    값의 분포를 버킷으로 추적합니다.

    사용 예:
        - 응답 시간 분포
        - 요청 크기 분포
        - FPS 분포

    Example:
        >>> histogram = Histogram("response_seconds", buckets=(0.1, 0.5, 1.0))
        >>> histogram.observe(0.25)
        >>> histogram.observe(0.8)
    """

    def __init__(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
        buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        """
        히스토그램 초기화.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위
            buckets: 버킷 경계값 (오름차순, 마지막은 +Inf)
        """
        super().__init__(name, help, unit, MetricType.HISTOGRAM)

        # 버킷 검증 및 정렬
        self._buckets = self._validate_buckets(buckets)

        # 레이블별 버킷 카운트
        self._bucket_counts: dict[MetricLabels, list[int]] = defaultdict(
            lambda: [0] * len(self._buckets)
        )
        # 레이블별 합계
        self._sums: dict[MetricLabels, float] = defaultdict(float)
        # 레이블별 총 개수
        self._counts: dict[MetricLabels, int] = defaultdict(int)

    def _validate_buckets(self, buckets: tuple[float, ...]) -> tuple[float, ...]:
        """버킷 검증 및 정렬."""
        bucket_list = list(buckets)

        # +Inf 추가 (없는 경우)
        if not bucket_list or bucket_list[-1] != float("inf"):
            bucket_list.append(float("inf"))

        # 정렬
        bucket_list.sort()

        # 중복 제거
        seen = set()
        unique = []
        for b in bucket_list:
            if b not in seen:
                seen.add(b)
                unique.append(b)

        return tuple(unique)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """
        값 관측.

        Args:
            value: 관측 값
            labels: 메트릭 레이블
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            # 합계 및 카운트 업데이트
            self._sums[metric_labels] += value
            self._counts[metric_labels] += 1

            # 버킷 카운트 업데이트 (bisect로 O(log n) 최적화)
            bucket_counts = self._bucket_counts[metric_labels]
            # value가 들어갈 버킷 인덱스 찾기
            bucket_index = bisect.bisect_left(self._buckets, value)
            # 해당 인덱스부터 모든 버킷 증가 (누적 카운트)
            for i in range(bucket_index, len(self._buckets)):
                bucket_counts[i] += 1

    def get_bucket_counts(
        self, labels: dict[str, str] | None = None
    ) -> list[tuple[float, int]]:
        """
        버킷별 카운트 조회.

        Returns:
            [(upper_bound, count), ...] 형식
        """
        metric_labels = self._validate_labels(labels)

        with self._lock:
            counts = self._bucket_counts.get(metric_labels, [0] * len(self._buckets))
            return list(zip(self._buckets, counts))

    def get_sum(self, labels: dict[str, str] | None = None) -> float:
        """합계 조회."""
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._sums.get(metric_labels, 0.0)

    def get_count(self, labels: dict[str, str] | None = None) -> int:
        """총 개수 조회."""
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._counts.get(metric_labels, 0)

    def labels(self, labels: dict[str, str]) -> "HistogramChild":
        """레이블이 지정된 히스토그램 자식 반환."""
        return HistogramChild(self, labels)

    @contextmanager
    def time(
        self, labels: dict[str, str] | None = None
    ) -> Generator[None, None, None]:
        """
        시간 측정 컨텍스트 매니저.

        Example:
            >>> with histogram.time():
            ...     process_request()
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.observe(elapsed, labels)

    def reset(self) -> None:
        """히스토그램 리셋 (테스트용)."""
        with self._lock:
            self._bucket_counts.clear()
            self._sums.clear()
            self._counts.clear()

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷."""
        with self._lock:
            values = []

            for metric_labels in set(
                list(self._bucket_counts.keys())
                + list(self._sums.keys())
                + list(self._counts.keys())
            ):
                label_dict = metric_labels.to_dict()

                # 버킷별 값
                bucket_counts = self._bucket_counts.get(
                    metric_labels, [0] * len(self._buckets)
                )
                for upper_bound, count in zip(self._buckets, bucket_counts):
                    bucket_labels = label_dict.copy()
                    bucket_labels["le"] = (
                        str(upper_bound) if upper_bound != float("inf") else "+Inf"
                    )
                    values.append(
                        MetricValue(
                            value=count,
                            labels=MetricLabels.from_dict(bucket_labels),
                        )
                    )

                # _sum
                sum_labels = label_dict.copy()
                values.append(
                    MetricValue(
                        value=self._sums.get(metric_labels, 0.0),
                        labels=MetricLabels.from_dict(sum_labels),
                    )
                )

                # _count
                values.append(
                    MetricValue(
                        value=self._counts.get(metric_labels, 0),
                        labels=MetricLabels.from_dict(label_dict),
                    )
                )

            return MetricSnapshot(
                name=self.name,
                type=self.metric_type,
                help=self.help,
                unit=self.unit,
                values=values,
            )


class HistogramChild:
    """레이블이 지정된 히스토그램 자식."""

    def __init__(self, parent: Histogram, labels: dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels

    def observe(self, value: float) -> None:
        """값 관측."""
        self._parent.observe(value, self._labels)

    @contextmanager
    def time(self) -> Generator[None, None, None]:
        """시간 측정."""
        with self._parent.time(self._labels):
            yield


# ============================================================
# Summary 메트릭
# ============================================================
class Summary(BaseMetric):
    """
    서머리 메트릭.

    분위수(quantile)를 계산하여 요약합니다.
    슬라이딩 윈도우 기반으로 최근 데이터만 사용합니다.

    사용 예:
        - 응답 시간 백분위 (p50, p90, p99)
        - 처리 시간 분포

    Example:
        >>> summary = Summary("latency_seconds", quantiles=(0.5, 0.9, 0.99))
        >>> summary.observe(0.1)
        >>> summary.observe(0.2)
    """

    def __init__(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
        quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
        max_age_seconds: float = SUMMARY_WINDOW_SECONDS,
        max_observations: int = SUMMARY_MAX_OBSERVATIONS,
    ) -> None:
        """
        서머리 초기화.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위
            quantiles: 계산할 분위수 (0-1)
            max_age_seconds: 관측값 최대 수명 (초)
            max_observations: 최대 관측값 수
        """
        super().__init__(name, help, unit, MetricType.SUMMARY)

        self._quantiles = quantiles
        self._max_age = max_age_seconds
        self._max_observations = max_observations

        # 레이블별 관측값 (timestamp, value)
        self._observations: dict[MetricLabels, list[tuple[float, float]]] = defaultdict(list)
        # 레이블별 합계
        self._sums: dict[MetricLabels, float] = defaultdict(float)
        # 레이블별 총 개수
        self._counts: dict[MetricLabels, int] = defaultdict(int)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """
        값 관측.

        Args:
            value: 관측 값
            labels: 메트릭 레이블
        """
        metric_labels = self._validate_labels(labels)
        now = time.time()

        with self._lock:
            self._sums[metric_labels] += value
            self._counts[metric_labels] += 1

            observations = self._observations[metric_labels]
            observations.append((now, value))

            # 오래된 관측값 정리
            self._cleanup_observations(metric_labels, now)

    def _cleanup_observations(self, labels: MetricLabels, now: float) -> None:
        """오래된 관측값 정리."""
        observations = self._observations[labels]
        cutoff = now - self._max_age

        # 오래된 항목 제거
        while observations and observations[0][0] < cutoff:
            observations.pop(0)

        # 최대 개수 초과 시 오래된 항목 제거
        while len(observations) > self._max_observations:
            observations.pop(0)

    def get_quantile(
        self,
        quantile: float,
        labels: dict[str, str] | None = None,
    ) -> float | None:
        """
        분위수 값 조회.

        Args:
            quantile: 분위수 (0-1)
            labels: 메트릭 레이블

        Returns:
            분위수 값 또는 None
        """
        if not 0 <= quantile <= 1:
            raise ValueError(f"분위수는 0-1 사이여야 합니다: {quantile}")

        metric_labels = self._validate_labels(labels)
        now = time.time()

        with self._lock:
            self._cleanup_observations(metric_labels, now)

            observations = self._observations.get(metric_labels, [])
            if not observations:
                return None

            # 값만 추출하여 정렬
            values = sorted([v for _, v in observations])
            n = len(values)

            # 분위수 인덱스 계산
            index = int(math.ceil(quantile * n)) - 1
            index = max(0, min(index, n - 1))

            return values[index]

    def get_quantiles(
        self, labels: dict[str, str] | None = None
    ) -> dict[float, float | None]:
        """모든 분위수 값 조회."""
        return {q: self.get_quantile(q, labels) for q in self._quantiles}

    def get_sum(self, labels: dict[str, str] | None = None) -> float:
        """합계 조회."""
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._sums.get(metric_labels, 0.0)

    def get_count(self, labels: dict[str, str] | None = None) -> int:
        """총 개수 조회."""
        metric_labels = self._validate_labels(labels)

        with self._lock:
            return self._counts.get(metric_labels, 0)

    def labels(self, labels: dict[str, str]) -> "SummaryChild":
        """레이블이 지정된 서머리 자식 반환."""
        return SummaryChild(self, labels)

    @contextmanager
    def time(
        self, labels: dict[str, str] | None = None
    ) -> Generator[None, None, None]:
        """시간 측정 컨텍스트 매니저."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.observe(elapsed, labels)

    def reset(self) -> None:
        """서머리 리셋 (테스트용)."""
        with self._lock:
            self._observations.clear()
            self._sums.clear()
            self._counts.clear()

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷."""
        now = time.time()

        with self._lock:
            values = []

            for metric_labels in set(
                list(self._observations.keys())
                + list(self._sums.keys())
                + list(self._counts.keys())
            ):
                self._cleanup_observations(metric_labels, now)
                label_dict = metric_labels.to_dict()

                # 분위수별 값
                observations = self._observations.get(metric_labels, [])
                if observations:
                    sorted_values = sorted([v for _, v in observations])
                    n = len(sorted_values)

                    for q in self._quantiles:
                        index = int(math.ceil(q * n)) - 1
                        index = max(0, min(index, n - 1))

                        q_labels = label_dict.copy()
                        q_labels["quantile"] = str(q)
                        values.append(
                            MetricValue(
                                value=sorted_values[index],
                                labels=MetricLabels.from_dict(q_labels),
                            )
                        )

                # _sum
                values.append(
                    MetricValue(
                        value=self._sums.get(metric_labels, 0.0),
                        labels=MetricLabels.from_dict(label_dict),
                    )
                )

                # _count
                values.append(
                    MetricValue(
                        value=self._counts.get(metric_labels, 0),
                        labels=MetricLabels.from_dict(label_dict),
                    )
                )

            return MetricSnapshot(
                name=self.name,
                type=self.metric_type,
                help=self.help,
                unit=self.unit,
                values=values,
            )


class SummaryChild:
    """레이블이 지정된 서머리 자식."""

    def __init__(self, parent: Summary, labels: dict[str, str]) -> None:
        self._parent = parent
        self._labels = labels

    def observe(self, value: float) -> None:
        """값 관측."""
        self._parent.observe(value, self._labels)

    @contextmanager
    def time(self) -> Generator[None, None, None]:
        """시간 측정."""
        with self._parent.time(self._labels):
            yield


# ============================================================
# MetricsCollector 메인 클래스
# ============================================================
class MetricsCollector:
    """
    메트릭 수집기.

    시스템 전체의 메트릭을 중앙에서 관리합니다.
    DI 컨테이너에 등록되어 주입받아 사용합니다.

    주요 기능:
        - 메트릭 등록 및 조회
        - Prometheus 형식 내보내기
        - 스레드 안전 설계
        - 농구 분석 특화 메트릭 사전 정의

    Example:
        >>> collector = MetricsCollector(config_loader)
        >>> collector.counter("requests_total").inc()
        >>> collector.gauge("active_sessions").set(10)
        >>> print(collector.export_prometheus())
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        prefix: str | None = None,
        enabled: bool | None = None,
        max_metrics: int | None = None,
    ) -> None:
        """
        MetricsCollector 초기화.

        Args:
            config_loader: 설정 로더 (None이면 싱글톤 사용)
            prefix: 메트릭 이름 접두사 (None이면 YAML 또는 기본값)
            enabled: 활성화 여부 (None이면 YAML 또는 기본값)
            max_metrics: 최대 메트릭 수 (None이면 YAML 또는 기본값)
        """
        self._config_loader = config_loader or ConfigLoader.get_instance()

        # YAML 설정 로드
        config = self._load_metrics_config()

        # 파라미터 > YAML > 기본값 우선순위
        self._prefix = prefix if prefix is not None else config.get("prefix", METRIC_PREFIX)
        self._enabled = enabled if enabled is not None else config.get("enabled", True)
        self._max_metrics = max_metrics if max_metrics is not None else config.get("max_metrics", MAX_METRICS)
        self._summary_window = config.get("summary_window_seconds", SUMMARY_WINDOW_SECONDS)
        self._summary_max_obs = config.get("summary_max_observations", SUMMARY_MAX_OBSERVATIONS)

        # 메트릭 저장소
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._summaries: dict[str, Summary] = {}

        # 스레드 락
        self._lock = threading.RLock()

        # 생성 시각
        self._created_at = datetime.now(timezone.utc)

        # 농구 분석 특화 메트릭 사전 등록
        self._register_default_metrics()

        logger.info(
            f"MetricsCollector 초기화 완료 "
            f"(prefix={self._prefix}, enabled={self._enabled}, max_metrics={self._max_metrics})"
        )

    def _load_metrics_config(self) -> dict[str, Any]:
        """
        YAML 설정에서 메트릭 설정 로드.

        Returns:
            메트릭 설정 딕셔너리
        """
        try:
            metrics_config = self._config_loader.get(CONFIG_KEY_METRICS, {})
            if not isinstance(metrics_config, dict):
                metrics_config = {}

            return {
                "enabled": metrics_config.get(CONFIG_KEY_ENABLED, True),
                "prefix": metrics_config.get(CONFIG_KEY_PREFIX, METRIC_PREFIX),
                "max_metrics": metrics_config.get(CONFIG_KEY_MAX_METRICS, MAX_METRICS),
                "summary_window_seconds": metrics_config.get(
                    CONFIG_KEY_SUMMARY_WINDOW, SUMMARY_WINDOW_SECONDS
                ),
                "summary_max_observations": metrics_config.get(
                    CONFIG_KEY_SUMMARY_MAX_OBS, SUMMARY_MAX_OBSERVATIONS
                ),
            }
        except Exception as e:
            logger.warning(f"메트릭 설정 로드 실패, 기본값 사용: {e}")
            return {
                "enabled": True,
                "prefix": METRIC_PREFIX,
                "max_metrics": MAX_METRICS,
                "summary_window_seconds": SUMMARY_WINDOW_SECONDS,
                "summary_max_observations": SUMMARY_MAX_OBSERVATIONS,
            }

    def _check_max_metrics(self) -> None:
        """
        메트릭 최대 개수 체크.

        Raises:
            RuntimeError: 최대 개수 초과 시
        """
        total = (
            len(self._counters)
            + len(self._gauges)
            + len(self._histograms)
            + len(self._summaries)
        )
        if total >= self._max_metrics:
            raise RuntimeError(
                f"메트릭 최대 개수 초과: {total} >= {self._max_metrics}. "
                f"max_metrics 설정을 늘리거나 불필요한 메트릭을 제거하세요."
            )

    def _register_default_metrics(self) -> None:
        """농구 분석 + Desktop 하드웨어 기본 메트릭 등록."""
        # ========================================================
        # 농구 분석 공통 메트릭
        # ========================================================
        # 분석 요청 카운터
        self.counter(
            "analysis_requests_total",
            help="Total analysis requests",
            unit=MetricUnit.COUNT,
        )

        # 분석 에러 카운터
        self.counter(
            "analysis_errors_total",
            help="Total analysis errors",
            unit=MetricUnit.COUNT,
        )

        # 활성 분석 게이지
        self.gauge(
            "active_analyses",
            help="Currently active analyses",
            unit=MetricUnit.COUNT,
        )

        # 분석 시간 히스토그램
        self.histogram(
            "analysis_duration_seconds",
            help="Analysis duration in seconds",
            unit=MetricUnit.SECONDS,
        )

        # FPS 히스토그램
        self.histogram(
            "video_fps",
            help="Video frames per second",
            unit=MetricUnit.FPS,
            buckets=FPS_HISTOGRAM_BUCKETS,
        )

        # 정확도 히스토그램
        self.histogram(
            "detection_accuracy",
            help="Detection accuracy ratio",
            unit=MetricUnit.RATIO,
            buckets=ACCURACY_HISTOGRAM_BUCKETS,
        )

        # 처리 시간 서머리
        self.summary(
            "processing_time_seconds",
            help="Processing time in seconds",
            unit=MetricUnit.SECONDS,
        )

        # ========================================================
        # Desktop GPU 메트릭
        # ========================================================
        # GPU 온도 (섭씨)
        self.gauge(
            "gpu_temperature_celsius",
            help="GPU temperature in Celsius",
            unit=MetricUnit.COUNT,  # 커스텀 단위 (섭씨)
        )

        # GPU VRAM 사용량 (바이트)
        self.gauge(
            "gpu_memory_used_bytes",
            help="GPU VRAM currently used",
            unit=MetricUnit.BYTES,
        )

        # GPU VRAM 전체 용량 (바이트)
        self.gauge(
            "gpu_memory_total_bytes",
            help="GPU VRAM total capacity",
            unit=MetricUnit.BYTES,
        )

        # GPU 활용률 (0-1)
        self.gauge(
            "gpu_utilization",
            help="GPU utilization ratio (0-1)",
            unit=MetricUnit.RATIO,
        )

        # TensorRT 최적화 활성 상태 (0=비활성, 1=활성)
        self.gauge(
            "tensorrt_enabled",
            help="TensorRT optimization status (0=off, 1=on)",
            unit=MetricUnit.COUNT,
        )

        # 모델 추론 시간 히스토그램
        self.histogram(
            "model_inference_seconds",
            help="Model inference latency per frame",
            unit=MetricUnit.SECONDS,
            buckets=MODEL_INFERENCE_BUCKETS,
        )

        # GPU 온도 히스토그램 (분포 추적)
        self.histogram(
            "gpu_temperature_distribution",
            help="GPU temperature distribution over time",
            buckets=GPU_TEMPERATURE_BUCKETS,
        )

        # ========================================================
        # Desktop 카메라 메트릭
        # ========================================================
        # 활성 카메라 수
        self.gauge(
            "camera_active_count",
            help="Number of active cameras",
            unit=MetricUnit.COUNT,
        )

        # 카메라 프레임 처리 시간 히스토그램
        self.histogram(
            "frame_processing_seconds",
            help="Per-frame processing latency",
            unit=MetricUnit.SECONDS,
            buckets=FRAME_PROCESSING_BUCKETS,
        )

        # 카메라 프레임 드롭 카운터
        self.counter(
            "camera_frames_dropped_total",
            help="Total dropped camera frames",
            unit=MetricUnit.COUNT,
        )

        # ========================================================
        # Desktop 시스템 리소스 메트릭
        # ========================================================
        # CPU 활용률 (0-1)
        self.gauge(
            "cpu_utilization",
            help="CPU utilization ratio (0-1)",
            unit=MetricUnit.RATIO,
        )

        # 시스템 RAM 사용량 (바이트)
        self.gauge(
            "system_memory_used_bytes",
            help="System RAM currently used",
            unit=MetricUnit.BYTES,
        )

        # 시스템 RAM 전체 용량 (바이트)
        self.gauge(
            "system_memory_total_bytes",
            help="System RAM total capacity",
            unit=MetricUnit.BYTES,
        )

        # 로컬 스토리지 사용량 (바이트)
        self.gauge(
            "disk_usage_bytes",
            help="Local storage used bytes",
            unit=MetricUnit.BYTES,
        )

        # 로컬 스토리지 전체 용량 (바이트)
        self.gauge(
            "disk_total_bytes",
            help="Local storage total capacity",
            unit=MetricUnit.BYTES,
        )

    def _make_name(self, name: str) -> str:
        """접두사가 포함된 전체 메트릭 이름 생성."""
        if name.startswith(self._prefix):
            return name
        return f"{self._prefix}_{name}"

    # --------------------------------------------------------
    # 메트릭 팩토리 메서드
    # --------------------------------------------------------
    def counter(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
    ) -> Counter:
        """
        카운터 메트릭 가져오기 또는 생성.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위

        Returns:
            Counter 인스턴스

        Raises:
            RuntimeError: 최대 메트릭 수 초과 시
        """
        full_name = self._make_name(name)

        with self._lock:
            if full_name not in self._counters:
                self._check_max_metrics()
                self._counters[full_name] = Counter(full_name, help, unit)

            return self._counters[full_name]

    def gauge(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
    ) -> Gauge:
        """
        게이지 메트릭 가져오기 또는 생성.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위

        Returns:
            Gauge 인스턴스

        Raises:
            RuntimeError: 최대 메트릭 수 초과 시
        """
        full_name = self._make_name(name)

        with self._lock:
            if full_name not in self._gauges:
                self._check_max_metrics()
                self._gauges[full_name] = Gauge(full_name, help, unit)

            return self._gauges[full_name]

    def histogram(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
        buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> Histogram:
        """
        히스토그램 메트릭 가져오기 또는 생성.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위
            buckets: 버킷 경계값

        Returns:
            Histogram 인스턴스

        Raises:
            RuntimeError: 최대 메트릭 수 초과 시
        """
        full_name = self._make_name(name)

        with self._lock:
            if full_name not in self._histograms:
                self._check_max_metrics()
                self._histograms[full_name] = Histogram(full_name, help, unit, buckets)

            return self._histograms[full_name]

    def summary(
        self,
        name: str,
        help: str = "",
        unit: MetricUnit | None = None,
        quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
        max_age_seconds: float | None = None,
        max_observations: int | None = None,
    ) -> Summary:
        """
        서머리 메트릭 가져오기 또는 생성.

        Args:
            name: 메트릭 이름
            help: 메트릭 설명
            unit: 메트릭 단위
            quantiles: 분위수 목록
            max_age_seconds: 관측값 최대 수명 (None이면 설정값 사용)
            max_observations: 최대 관측값 수 (None이면 설정값 사용)

        Returns:
            Summary 인스턴스

        Raises:
            RuntimeError: 최대 메트릭 수 초과 시
        """
        full_name = self._make_name(name)

        # YAML 설정 또는 기본값 사용
        age = max_age_seconds if max_age_seconds is not None else self._summary_window
        max_obs = max_observations if max_observations is not None else self._summary_max_obs

        with self._lock:
            if full_name not in self._summaries:
                self._check_max_metrics()
                self._summaries[full_name] = Summary(
                    full_name, help, unit, quantiles, age, max_obs
                )

            return self._summaries[full_name]

    # --------------------------------------------------------
    # 내보내기 메서드
    # --------------------------------------------------------
    def get_all_snapshots(self) -> list[MetricSnapshot]:
        """모든 메트릭의 스냅샷 반환."""
        with self._lock:
            snapshots = []

            for counter in self._counters.values():
                snapshots.append(counter.snapshot())

            for gauge in self._gauges.values():
                snapshots.append(gauge.snapshot())

            for histogram in self._histograms.values():
                snapshots.append(histogram.snapshot())

            for summary in self._summaries.values():
                snapshots.append(summary.snapshot())

            return snapshots

    def export_prometheus(self) -> str:
        """
        Prometheus exposition format으로 내보내기.

        Returns:
            Prometheus 형식 문자열
        """
        if not self._enabled:
            return ""

        snapshots = self.get_all_snapshots()
        lines = []

        for snapshot in snapshots:
            lines.append(snapshot.to_prometheus())

        return "\n\n".join(lines)

    def export_json(self) -> dict[str, Any]:
        """
        JSON 형식으로 내보내기.

        Returns:
            메트릭 딕셔너리
        """
        if not self._enabled:
            return {"metrics": [], "enabled": False}

        snapshots = self.get_all_snapshots()

        return {
            "prefix": self._prefix,
            "enabled": self._enabled,
            "created_at": self._created_at.isoformat(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [s.to_dict() for s in snapshots],
        }

    # --------------------------------------------------------
    # 유틸리티 메서드
    # --------------------------------------------------------
    def get_status(self) -> dict[str, Any]:
        """수집기 상태 조회."""
        with self._lock:
            total = (
                len(self._counters)
                + len(self._gauges)
                + len(self._histograms)
                + len(self._summaries)
            )
            return {
                "enabled": self._enabled,
                "prefix": self._prefix,
                "max_metrics": self._max_metrics,
                "counters_count": len(self._counters),
                "gauges_count": len(self._gauges),
                "histograms_count": len(self._histograms),
                "summaries_count": len(self._summaries),
                "total_metrics": total,
                "metrics_remaining": self._max_metrics - total,
                "summary_window_seconds": self._summary_window,
                "summary_max_observations": self._summary_max_obs,
                "created_at": self._created_at.isoformat(),
            }

    def reset_all(self) -> None:
        """모든 메트릭 리셋 (테스트용)."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for gauge in self._gauges.values():
                gauge.reset()
            for histogram in self._histograms.values():
                histogram.reset()
            for summary in self._summaries.values():
                summary.reset()

        logger.info("모든 메트릭 리셋 완료")

    @property
    def enabled(self) -> bool:
        """활성화 여부."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """활성화 여부 설정."""
        old_value = self._enabled
        self._enabled = value
        if old_value != value:
            logger.info(f"MetricsCollector 활성화 상태 변경: {old_value} -> {value}")


# ============================================================
# 싱글톤 인스턴스 관리
# ============================================================
_collector_instance: MetricsCollector | None = None
_collector_lock: threading.Lock = threading.Lock()


def _get_collector() -> MetricsCollector:
    """전역 MetricsCollector 인스턴스 반환."""
    global _collector_instance

    if _collector_instance is None:
        with _collector_lock:
            if _collector_instance is None:
                _collector_instance = MetricsCollector()

    return _collector_instance


def _reset_collector() -> None:
    """전역 MetricsCollector 인스턴스 리셋 (테스트용)."""
    global _collector_instance

    with _collector_lock:
        _collector_instance = None


# ============================================================
# 데코레이터
# ============================================================
def measure_latency(
    metric_name: str,
    labels: dict[str, str] | None = None,
    use_histogram: bool = True,
) -> Callable[[F], F]:
    """
    함수 실행 시간 측정 데코레이터.

    Args:
        metric_name: 메트릭 이름
        labels: 추가 레이블
        use_histogram: True면 Histogram, False면 Summary 사용

    Returns:
        데코레이터 함수

    Example:
        >>> @measure_latency("analysis_duration_seconds")
        ... def analyze(video):
        ...     ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = _get_collector()

            # 기본 레이블에 함수 이름 추가
            metric_labels = labels.copy() if labels else {}
            metric_labels.setdefault("function", func.__name__)

            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                metric_labels["status"] = "success"
                return result
            except Exception as e:
                metric_labels["status"] = "error"
                metric_labels["error_type"] = type(e).__name__
                raise
            finally:
                elapsed = time.perf_counter() - start

                if use_histogram:
                    collector.histogram(metric_name).observe(elapsed, metric_labels)
                else:
                    collector.summary(metric_name).observe(elapsed, metric_labels)

        return wrapper  # type: ignore

    return decorator


def count_calls(
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> Callable[[F], F]:
    """
    함수 호출 횟수 카운트 데코레이터.

    Args:
        metric_name: 메트릭 이름
        labels: 추가 레이블

    Returns:
        데코레이터 함수

    Example:
        >>> @count_calls("api_calls_total")
        ... def handle_request():
        ...     ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = _get_collector()

            # 기본 레이블에 함수 이름 추가
            metric_labels = labels.copy() if labels else {}
            metric_labels.setdefault("function", func.__name__)

            try:
                result = func(*args, **kwargs)
                metric_labels["status"] = "success"
                return result
            except Exception as e:
                metric_labels["status"] = "error"
                metric_labels["error_type"] = type(e).__name__
                raise
            finally:
                collector.counter(metric_name).inc(1.0, metric_labels)

        return wrapper  # type: ignore

    return decorator


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "MetricType",
    "MetricUnit",
    # 상수
    "DEFAULT_HISTOGRAM_BUCKETS",
    "FPS_HISTOGRAM_BUCKETS",
    "ACCURACY_HISTOGRAM_BUCKETS",
    "MODEL_INFERENCE_BUCKETS",
    "FRAME_PROCESSING_BUCKETS",
    "GPU_TEMPERATURE_BUCKETS",
    "DEFAULT_QUANTILES",
    "METRIC_PREFIX",
    "MAX_METRICS",
    "SUMMARY_WINDOW_SECONDS",
    "SUMMARY_MAX_OBSERVATIONS",
    # 데이터 클래스
    "MetricValue",
    "MetricLabels",
    "MetricSnapshot",
    # 메트릭 클래스
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    # 메인 클래스
    "MetricsCollector",
    # 데코레이터
    "measure_latency",
    "count_calls",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
