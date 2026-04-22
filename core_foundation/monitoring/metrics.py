# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: metrics.py
설명: 시스템 메트릭 수집 엔진
      - 메트릭 타입 (카운터, 게이지, 히스토그램)
      - GPU/카메라/시스템 메트릭 수집
      - 링 버퍼 기반 시계열 이력
      - 메트릭 스냅샷 및 집계
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import collections
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 메트릭 이력 기본 크기 (시계열 데이터 포인트 수)
DEFAULT_HISTORY_SIZE: Final[int] = 300

# 메트릭 등록 최대 수 (메모리 성장 방지)
MAX_METRIC_COUNT: Final[int] = 500

# 히스토그램 기본 버킷 경계
DEFAULT_HISTOGRAM_BUCKETS: Final[tuple[float, ...]] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


# =============================================================================
# 메트릭 타입 열거형
# =============================================================================

@unique
class MetricType(Enum):
    """메트릭 타입."""

    COUNTER = "counter"       # 단조 증가 (처리 건수, 에러 횟수)
    GAUGE = "gauge"           # 현재 값 (온도, 사용률, FPS)
    HISTOGRAM = "histogram"   # 분포 (지연 시간, 프레임 처리 시간)

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _METRIC_TYPE_KOREAN_MAP[self]


_METRIC_TYPE_KOREAN_MAP: Final[dict[MetricType, str]] = {
    MetricType.COUNTER: "카운터",
    MetricType.GAUGE: "게이지",
    MetricType.HISTOGRAM: "히스토그램",
}


# =============================================================================
# 메트릭 데이터 포인트
# =============================================================================

@dataclass(slots=True)
class MetricPoint:
    """단일 메트릭 데이터 포인트.

    Attributes:
        value: 측정값
        timestamp: 기록 시각 (monotonic)
        labels: 추가 라벨 (컴포넌트, 디바이스 등)
    """

    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"MetricPoint(value={self.value:.4f})"


# =============================================================================
# 메트릭 스냅샷
# =============================================================================

@dataclass(slots=True)
class MetricSnapshot:
    """메트릭 집계 스냅샷.

    Attributes:
        name: 메트릭 이름
        metric_type: 메트릭 타입
        current: 현재/최신 값
        count: 데이터 포인트 수
        mean: 평균
        min_value: 최소값
        max_value: 최대값
        p50: 중앙값 (50th percentile)
        p95: 95th percentile
        p99: 99th percentile
    """

    name: str
    metric_type: MetricType
    current: float
    count: int
    mean: float
    min_value: float
    max_value: float
    p50: float
    p95: float
    p99: float

    def __repr__(self) -> str:
        return (
            f"MetricSnapshot("
            f"{self.name}: current={self.current:.2f}, "
            f"mean={self.mean:.2f}, "
            f"count={self.count})"
        )


# =============================================================================
# 개별 메트릭 클래스
# =============================================================================

class Metric:
    """단일 메트릭.

    카운터, 게이지, 히스토그램 모두 지원하는 통합 메트릭.
    내부적으로 링 버퍼(deque)에 시계열 이력을 보관한다.

    Attributes:
        name: 메트릭 이름
        metric_type: 메트릭 타입
        description: 메트릭 설명
    """

    __slots__ = (
        "_name", "_type", "_description", "_history",
        "_current", "_lock",
    )

    def __init__(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        *,
        history_size: int = DEFAULT_HISTORY_SIZE,
    ) -> None:
        """Metric 초기화.

        Args:
            name: 메트릭 이름
            metric_type: 메트릭 타입
            description: 메트릭 설명
            history_size: 이력 보관 크기
        """
        self._name = name
        self._type = metric_type
        self._description = description
        self._history: collections.deque[MetricPoint] = collections.deque(
            maxlen=history_size,
        )
        self._current: float = 0.0
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        """메트릭 이름."""
        return self._name

    @property
    def metric_type(self) -> MetricType:
        """메트릭 타입."""
        return self._type

    @property
    def description(self) -> str:
        """메트릭 설명."""
        return self._description

    @property
    def current(self) -> float:
        """현재 값."""
        with self._lock:
            return self._current

    @property
    def count(self) -> int:
        """데이터 포인트 수."""
        with self._lock:
            return len(self._history)

    # =========================================================================
    # 값 기록
    # =========================================================================

    def increment(self, amount: float = 1.0, **labels: str) -> None:
        """카운터 증가 (COUNTER 전용).

        Args:
            amount: 증가량 (양수만)
            **labels: 추가 라벨
        """
        if amount < 0:
            amount = 0.0  # 카운터는 음수 불가

        with self._lock:
            self._current += amount
            self._history.append(MetricPoint(
                value=self._current,
                timestamp=time.monotonic(),
                labels=labels,
            ))

    def set(self, value: float, **labels: str) -> None:
        """게이지 설정 (GAUGE 전용).

        Args:
            value: 설정할 값
            **labels: 추가 라벨
        """
        with self._lock:
            self._current = value
            self._history.append(MetricPoint(
                value=value,
                timestamp=time.monotonic(),
                labels=labels,
            ))

    def observe(self, value: float, **labels: str) -> None:
        """관측 기록 (HISTOGRAM 전용).

        Args:
            value: 관측값
            **labels: 추가 라벨
        """
        with self._lock:
            self._current = value
            self._history.append(MetricPoint(
                value=value,
                timestamp=time.monotonic(),
                labels=labels,
            ))

    def record(self, value: float, **labels: str) -> None:
        """범용 기록 (타입 무관).

        Args:
            value: 기록할 값
            **labels: 추가 라벨
        """
        if self._type == MetricType.COUNTER:
            self.increment(value, **labels)
        elif self._type == MetricType.GAUGE:
            self.set(value, **labels)
        else:
            self.observe(value, **labels)

    # =========================================================================
    # 집계
    # =========================================================================

    def snapshot(self) -> MetricSnapshot:
        """현재 상태 스냅샷 생성.

        Returns:
            MetricSnapshot
        """
        with self._lock:
            values = [p.value for p in self._history]

            if not values:
                return MetricSnapshot(
                    name=self._name,
                    metric_type=self._type,
                    current=0.0,
                    count=0,
                    mean=0.0,
                    min_value=0.0,
                    max_value=0.0,
                    p50=0.0,
                    p95=0.0,
                    p99=0.0,
                )

            sorted_vals = sorted(values)
            n = len(sorted_vals)

            return MetricSnapshot(
                name=self._name,
                metric_type=self._type,
                current=self._current,
                count=n,
                mean=sum(sorted_vals) / n,
                min_value=sorted_vals[0],
                max_value=sorted_vals[-1],
                p50=self._percentile(sorted_vals, 50),
                p95=self._percentile(sorted_vals, 95),
                p99=self._percentile(sorted_vals, 99),
            )

    def reset(self) -> None:
        """메트릭 초기화."""
        with self._lock:
            self._current = 0.0
            self._history.clear()

    @staticmethod
    def _percentile(sorted_values: list[float], pct: float) -> float:
        """정렬된 리스트에서 백분위 계산.

        선형 보간법 사용.

        Args:
            sorted_values: 정렬된 값 리스트
            pct: 백분위 (0-100)

        Returns:
            백분위 값
        """
        n = len(sorted_values)
        if n == 0:
            return 0.0
        if n == 1:
            return sorted_values[0]

        k = (pct / 100.0) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)

        if f == c:
            return sorted_values[int(k)]

        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def __repr__(self) -> str:
        return (
            f"Metric("
            f"name='{self._name}', "
            f"type={self._type.value}, "
            f"current={self._current:.2f}, "
            f"points={self.count})"
        )


# =============================================================================
# 핵심 클래스: MetricsCollector
# =============================================================================

class MetricsCollector:
    """메트릭 수집 관리자.

    메트릭 등록, 기록, 조회를 중앙 관리한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        collector = MetricsCollector.get_instance()

        # 메트릭 등록
        fps = collector.register("camera.fps", MetricType.GAUGE, "카메라 FPS")
        latency = collector.register("detection.latency", MetricType.HISTOGRAM)

        # 값 기록
        fps.set(60.0)
        latency.observe(0.033)

        # 전체 스냅샷
        snapshots = collector.snapshot_all()
    """

    _instance: ClassVar[MetricsCollector | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        """MetricsCollector 초기화."""
        self._lock = threading.RLock()
        self._metrics: dict[str, Metric] = {}

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> MetricsCollector:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 메트릭 관리
    # =========================================================================

    def register(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        *,
        history_size: int = DEFAULT_HISTORY_SIZE,
    ) -> Metric:
        """메트릭 등록 또는 기존 메트릭 반환.

        Args:
            name: 메트릭 이름
            metric_type: 메트릭 타입
            description: 설명
            history_size: 이력 크기

        Returns:
            Metric 인스턴스

        Raises:
            ValueError: 등록 한도 초과
        """
        with self._lock:
            if name in self._metrics:
                return self._metrics[name]

            if len(self._metrics) >= MAX_METRIC_COUNT:
                raise ValueError(
                    f"메트릭 최대 등록 수 초과: {MAX_METRIC_COUNT}"
                )

            metric = Metric(
                name=name,
                metric_type=metric_type,
                description=description,
                history_size=history_size,
            )
            self._metrics[name] = metric
            return metric

    def get(self, name: str) -> Metric | None:
        """등록된 메트릭 조회.

        Args:
            name: 메트릭 이름

        Returns:
            Metric 또는 None
        """
        with self._lock:
            return self._metrics.get(name)

    def unregister(self, name: str) -> bool:
        """메트릭 등록 해제.

        Args:
            name: 메트릭 이름

        Returns:
            해제 성공 여부
        """
        with self._lock:
            if name in self._metrics:
                del self._metrics[name]
                return True
            return False

    # =========================================================================
    # 집계
    # =========================================================================

    def snapshot_all(self) -> dict[str, MetricSnapshot]:
        """전체 메트릭 스냅샷.

        Returns:
            메트릭 이름 → 스냅샷 딕셔너리
        """
        with self._lock:
            return {
                name: metric.snapshot()
                for name, metric in self._metrics.items()
            }

    def snapshot(self, name: str) -> MetricSnapshot | None:
        """특정 메트릭 스냅샷.

        Args:
            name: 메트릭 이름

        Returns:
            MetricSnapshot 또는 None
        """
        with self._lock:
            metric = self._metrics.get(name)
            if metric is None:
                return None
            return metric.snapshot()

    # =========================================================================
    # 관리
    # =========================================================================

    def clear(self) -> int:
        """전체 메트릭 제거.

        Returns:
            제거된 메트릭 수
        """
        with self._lock:
            count = len(self._metrics)
            self._metrics.clear()
            return count

    @property
    def metric_count(self) -> int:
        """등록된 메트릭 수."""
        with self._lock:
            return len(self._metrics)

    @property
    def metric_names(self) -> list[str]:
        """등록된 메트릭 이름 목록."""
        with self._lock:
            return list(self._metrics.keys())

    def __repr__(self) -> str:
        return f"MetricsCollector(metrics={self.metric_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "MetricType",
    # 데이터 클래스
    "MetricPoint",
    "MetricSnapshot",
    # 메트릭
    "Metric",
    # 관리자
    "MetricsCollector",
    # 상수
    "DEFAULT_HISTORY_SIZE",
    "MAX_METRIC_COUNT",
    "DEFAULT_HISTOGRAM_BUCKETS",
]

__version__ = "1.0.0"
