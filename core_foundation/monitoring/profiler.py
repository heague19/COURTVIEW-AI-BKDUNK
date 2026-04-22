# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: profiler.py
설명: CPU/메모리/GPU 프로파일링 엔진
      - 함수 실행 시간 측정 (컨텍스트 매니저 + 데코레이터)
      - 메모리 사용량 추적
      - 프로파일 결과 집계 (평균, 최소, 최대, 백분위)
      - 중첩 프로파일링 지원
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
import functools
import math
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Final, Generator


# =============================================================================
# 상수 정의
# =============================================================================

# 프로파일 이력 기본 크기
DEFAULT_PROFILE_HISTORY: Final[int] = 200

# 프로파일 등록 최대 수
MAX_PROFILE_COUNT: Final[int] = 500

# 메모리 측정 단위 변환 (bytes → MB)
BYTES_TO_MB: Final[float] = 1.0 / (1024.0 * 1024.0)


# =============================================================================
# 프로파일 결과 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ProfileEntry:
    """단일 프로파일 측정 결과.

    Attributes:
        name: 프로파일 대상 이름
        duration_sec: 실행 시간 (초)
        timestamp: 측정 시각 (monotonic)
        memory_mb: 메모리 사용량 (MB, None이면 미측정)
    """

    name: str
    duration_sec: float
    timestamp: float
    memory_mb: float | None = None

    @property
    def duration_ms(self) -> float:
        """실행 시간 (밀리초)."""
        return self.duration_sec * 1000.0

    def __repr__(self) -> str:
        mem = f", mem={self.memory_mb:.1f}MB" if self.memory_mb is not None else ""
        return (
            f"ProfileEntry("
            f"{self.name}: {self.duration_ms:.2f}ms{mem})"
        )


@dataclass(slots=True)
class ProfileSummary:
    """프로파일 집계 요약.

    Attributes:
        name: 프로파일 대상 이름
        call_count: 호출 횟수
        total_sec: 총 실행 시간 (초)
        mean_sec: 평균 실행 시간 (초)
        min_sec: 최소 실행 시간 (초)
        max_sec: 최대 실행 시간 (초)
        p50_sec: 중앙값 (초)
        p95_sec: 95th percentile (초)
        p99_sec: 99th percentile (초)
        mean_memory_mb: 평균 메모리 사용량 (MB)
    """

    name: str
    call_count: int
    total_sec: float
    mean_sec: float
    min_sec: float
    max_sec: float
    p50_sec: float
    p95_sec: float
    p99_sec: float
    mean_memory_mb: float | None

    @property
    def mean_ms(self) -> float:
        """평균 실행 시간 (밀리초)."""
        return self.mean_sec * 1000.0

    @property
    def p95_ms(self) -> float:
        """P95 실행 시간 (밀리초)."""
        return self.p95_sec * 1000.0

    def __repr__(self) -> str:
        return (
            f"ProfileSummary("
            f"{self.name}: calls={self.call_count}, "
            f"mean={self.mean_ms:.2f}ms, "
            f"p95={self.p95_ms:.2f}ms)"
        )


# =============================================================================
# 개별 프로파일 트래커
# =============================================================================

class ProfileTracker:
    """단일 대상에 대한 프로파일 이력 관리.

    Attributes:
        name: 프로파일 대상 이름
    """

    __slots__ = ("_name", "_history", "_lock")

    def __init__(
        self,
        name: str,
        *,
        history_size: int = DEFAULT_PROFILE_HISTORY,
    ) -> None:
        self._name = name
        self._history: collections.deque[ProfileEntry] = collections.deque(
            maxlen=history_size,
        )
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._history)

    def add(self, entry: ProfileEntry) -> None:
        """프로파일 엔트리 추가."""
        with self._lock:
            self._history.append(entry)

    def summary(self) -> ProfileSummary:
        """집계 요약 생성."""
        with self._lock:
            durations = [e.duration_sec for e in self._history]
            memories = [
                e.memory_mb for e in self._history
                if e.memory_mb is not None
            ]

            if not durations:
                return ProfileSummary(
                    name=self._name,
                    call_count=0,
                    total_sec=0.0,
                    mean_sec=0.0,
                    min_sec=0.0,
                    max_sec=0.0,
                    p50_sec=0.0,
                    p95_sec=0.0,
                    p99_sec=0.0,
                    mean_memory_mb=None,
                )

            sorted_dur = sorted(durations)
            n = len(sorted_dur)
            total = sum(sorted_dur)

            return ProfileSummary(
                name=self._name,
                call_count=n,
                total_sec=total,
                mean_sec=total / n,
                min_sec=sorted_dur[0],
                max_sec=sorted_dur[-1],
                p50_sec=_percentile(sorted_dur, 50),
                p95_sec=_percentile(sorted_dur, 95),
                p99_sec=_percentile(sorted_dur, 99),
                mean_memory_mb=(
                    sum(memories) / len(memories) if memories else None
                ),
            )

    def reset(self) -> None:
        """이력 초기화."""
        with self._lock:
            self._history.clear()

    def __repr__(self) -> str:
        return f"ProfileTracker(name='{self._name}', entries={self.count})"


# =============================================================================
# 핵심 클래스: Profiler
# =============================================================================

class Profiler:
    """CPU/메모리 프로파일링 관리자.

    컨텍스트 매니저와 데코레이터 두 가지 방식을 지원한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        profiler = Profiler.get_instance()

        # 컨텍스트 매니저
        with profiler.measure("detection.ball"):
            detect_ball(frame)

        # 데코레이터
        @profiler.profile("detection.player")
        def detect_player(frame):
            ...

        # 결과 조회
        summary = profiler.get_summary("detection.ball")
        print(f"평균: {summary.mean_ms:.2f}ms")
    """

    _instance: ClassVar[Profiler | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._trackers: dict[str, ProfileTracker] = {}

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> Profiler:
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 측정 API
    # =========================================================================

    @contextmanager
    def measure(
        self,
        name: str,
        *,
        track_memory: bool = False,
    ) -> Generator[None, None, None]:
        """컨텍스트 매니저 방식 프로파일링.

        Args:
            name: 프로파일 대상 이름
            track_memory: 메모리 사용량 추적 여부

        Yields:
            None
        """
        mem_before: int | None = None
        if track_memory:
            mem_before = _get_process_memory()

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start

            memory_mb: float | None = None
            if track_memory and mem_before is not None:
                mem_after = _get_process_memory()
                if mem_after is not None:
                    memory_mb = (mem_after - mem_before) * BYTES_TO_MB

            entry = ProfileEntry(
                name=name,
                duration_sec=elapsed,
                timestamp=time.monotonic(),
                memory_mb=memory_mb,
            )
            self._record(name, entry)

    def profile(
        self,
        name: str | None = None,
        *,
        track_memory: bool = False,
    ) -> Callable[..., Any]:
        """데코레이터 방식 프로파일링.

        Args:
            name: 프로파일 이름 (None이면 함수 이름 사용)
            track_memory: 메모리 추적 여부

        Returns:
            데코레이터
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            profile_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.measure(profile_name, track_memory=track_memory):
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def record_duration(self, name: str, duration_sec: float) -> None:
        """수동으로 실행 시간 기록.

        Args:
            name: 프로파일 이름
            duration_sec: 실행 시간 (초)
        """
        entry = ProfileEntry(
            name=name,
            duration_sec=duration_sec,
            timestamp=time.monotonic(),
        )
        self._record(name, entry)

    # =========================================================================
    # 조회
    # =========================================================================

    def get_summary(self, name: str) -> ProfileSummary | None:
        """특정 대상 프로파일 요약.

        Args:
            name: 프로파일 이름

        Returns:
            ProfileSummary 또는 None
        """
        with self._lock:
            tracker = self._trackers.get(name)
            if tracker is None:
                return None
            return tracker.summary()

    def get_all_summaries(self) -> dict[str, ProfileSummary]:
        """전체 프로파일 요약.

        Returns:
            이름 → ProfileSummary 딕셔너리
        """
        with self._lock:
            return {
                name: tracker.summary()
                for name, tracker in self._trackers.items()
            }

    @property
    def profile_names(self) -> list[str]:
        """등록된 프로파일 이름 목록."""
        with self._lock:
            return list(self._trackers.keys())

    @property
    def profile_count(self) -> int:
        """등록된 프로파일 수."""
        with self._lock:
            return len(self._trackers)

    # =========================================================================
    # 관리
    # =========================================================================

    def clear(self, name: str | None = None) -> int:
        """프로파일 이력 초기화.

        Args:
            name: 특정 프로파일만 초기화. None이면 전체.

        Returns:
            초기화된 프로파일 수
        """
        with self._lock:
            if name is not None:
                tracker = self._trackers.get(name)
                if tracker is not None:
                    tracker.reset()
                    return 1
                return 0

            count = len(self._trackers)
            self._trackers.clear()
            return count

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _record(self, name: str, entry: ProfileEntry) -> None:
        """프로파일 엔트리 기록."""
        with self._lock:
            if name not in self._trackers:
                if len(self._trackers) >= MAX_PROFILE_COUNT:
                    return  # 한도 초과 시 무시
                self._trackers[name] = ProfileTracker(name)
            self._trackers[name].add(entry)

    def __repr__(self) -> str:
        return f"Profiler(profiles={self.profile_count})"


# =============================================================================
# 내부 유틸리티
# =============================================================================

def _percentile(sorted_values: list[float], pct: float) -> float:
    """정렬된 리스트에서 백분위 계산 (선형 보간법)."""
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


def _get_process_memory() -> int | None:
    """현재 프로세스 메모리 사용량 (bytes).

    psutil 없이 /proc/self/status 또는 os 모듈로 측정.
    지원하지 않는 플랫폼에서는 None 반환.
    """
    try:
        # Windows: ctypes 또는 resource 미사용 — 단순 fallback
        import ctypes
        import ctypes.wintypes

        # Windows API: GetProcessMemoryInfo
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        psapi = ctypes.windll.psapi  # type: ignore[attr-defined]
        handle = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            ctypes.sizeof(counters),
        ):
            return counters.WorkingSetSize
    except (OSError, AttributeError, ImportError):
        pass

    # Linux / macOS fallback
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss: KB on Linux, bytes on macOS
        import platform
        if platform.system() == "Darwin":
            return usage.ru_maxrss
        return usage.ru_maxrss * 1024
    except (ImportError, AttributeError):
        pass

    return None


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터 클래스
    "ProfileEntry",
    "ProfileSummary",
    # 트래커
    "ProfileTracker",
    # 핵심 클래스
    "Profiler",
    # 상수
    "DEFAULT_PROFILE_HISTORY",
    "MAX_PROFILE_COUNT",
    "BYTES_TO_MB",
]

__version__ = "1.0.0"
