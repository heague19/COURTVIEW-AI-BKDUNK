"""
core_foundation/monitoring/profiler.py

엔터프라이즈급 프로파일링 시스템
- 시간 프로파일링: 함수 실행 시간 측정
- 메모리 프로파일링: 메모리 사용량 추적
- 호출 스택 추적: 함수 호출 계층 구조
- 핫스팟 탐지: 성능 병목 지점 식별
- 보고서 생성: Text, JSON 포맷

Author: COURTVIEW Team
Version: 1.0.0
"""

import time
import threading
import statistics
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from functools import wraps
from collections import defaultdict, deque
from datetime import datetime

# 메모리 프로파일링 (선택적)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from core_foundation.monitoring.logger import get_logger

logger = get_logger(__name__)


# ==================== 데이터 클래스 ====================
@dataclass
class FunctionProfile:
    """함수 프로파일 통계"""
    function_name: str              # 함수 이름
    module_name: str                # 모듈 이름

    # 시간 통계
    call_count: int = 0             # 호출 횟수
    total_time: float = 0.0         # 총 실행 시간 (ms)
    avg_time: float = 0.0           # 평균 실행 시간 (ms)
    min_time: float = float('inf')  # 최소 실행 시간 (ms)
    max_time: float = 0.0           # 최대 실행 시간 (ms)
    std_time: float = 0.0           # 표준편차 (ms)

    # 메모리 통계
    total_memory: float = 0.0       # 총 메모리 증가량 (MB)
    avg_memory: float = 0.0         # 평균 메모리 (MB)
    peak_memory: float = 0.0        # 피크 메모리 (MB)

    # 호출 관계
    callers: List[str] = field(default_factory=list)   # 호출자 목록
    callees: List[str] = field(default_factory=list)   # 피호출자 목록

    # 메타데이터
    first_call_time: float = 0.0    # 첫 호출 시각 (timestamp)
    last_call_time: float = 0.0     # 마지막 호출 시각 (timestamp)

    # 내부 데이터 (통계 계산용)
    _time_samples: List[float] = field(default_factory=list, repr=False)


@dataclass
class MemorySnapshot:
    """메모리 스냅샷"""
    function_name: str              # 함수 이름
    timestamp: float                # 측정 시각
    memory_before: float            # 실행 전 메모리 (MB)
    memory_after: float             # 실행 후 메모리 (MB)
    memory_delta: float             # 메모리 증가량 (MB)
    peak_memory: float              # 피크 메모리 (MB)


@dataclass
class CallFrame:
    """호출 프레임"""
    function_name: str              # 함수 이름
    depth: int                      # 호출 깊이
    start_time: float               # 시작 시각
    end_time: float = 0.0           # 종료 시각

    @property
    def elapsed_time(self) -> float:
        """경과 시간 (ms)"""
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@dataclass
class MemoryLeak:
    """메모리 누수 정보"""
    function_name: str              # 함수 이름
    memory_increase_mb: float       # 메모리 증가량 (MB)
    timestamp: float                # 탐지 시각


@dataclass
class CallGraph:
    """호출 그래프"""
    edges: Dict[str, List[str]]     # caller -> [callees]

    def to_text(self, indent: int = 2) -> str:
        """텍스트 형식으로 변환"""
        lines = []

        def build_tree(node: str, depth: int, visited: set):
            if node in visited:
                lines.append("  " * depth + f"{node} (recursive)")
                return

            visited.add(node)
            lines.append("  " * depth + node)

            if node in self.edges:
                for child in self.edges[node]:
                    build_tree(child, depth + 1, visited.copy())

        # 루트 노드 찾기 (호출되지 않는 노드)
        all_nodes = set(self.edges.keys())
        called_nodes = set()
        for callees in self.edges.values():
            called_nodes.update(callees)

        root_nodes = all_nodes - called_nodes

        for root in sorted(root_nodes):
            build_tree(root, 0, set())

        return "\n".join(lines)


# ==================== TimeProfiler ====================
class TimeProfiler:
    """시간 프로파일러"""

    def __init__(self, enabled: bool = True, max_samples: int = 10000):
        """
        Args:
            enabled: 프로파일링 활성화
            max_samples: 함수당 최대 샘플 수 (메모리 제한)
        """
        self.enabled = enabled
        self.max_samples = max_samples
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
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = (time.perf_counter() - start_time) * 1000  # ms
                    self._record(profile_name, elapsed, func.__module__)

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
            self._record("__context__", elapsed, "__main__")
            delattr(self, '_start_time')

    def _record(self, function_name: str, elapsed_ms: float, module_name: str = "") -> None:
        """프로파일 기록"""
        with self._lock:
            if function_name not in self._profiles:
                self._profiles[function_name] = FunctionProfile(
                    function_name=function_name,
                    module_name=module_name,
                    first_call_time=time.time()
                )

            profile = self._profiles[function_name]

            # 호출 횟수
            profile.call_count += 1
            profile.last_call_time = time.time()

            # 시간 통계
            profile.total_time += elapsed_ms
            profile.min_time = min(profile.min_time, elapsed_ms)
            profile.max_time = max(profile.max_time, elapsed_ms)

            # 샘플 저장 (최대 개수 제한)
            if len(profile._time_samples) < self.max_samples:
                profile._time_samples.append(elapsed_ms)

            # 평균 및 표준편차 계산
            if profile._time_samples:
                profile.avg_time = statistics.mean(profile._time_samples)
                if len(profile._time_samples) > 1:
                    profile.std_time = statistics.stdev(profile._time_samples)

    def get_stats(self) -> Dict[str, FunctionProfile]:
        """전체 통계 조회"""
        with self._lock:
            return self._profiles.copy()

    def get_profile(self, function_name: str) -> Optional[FunctionProfile]:
        """특정 함수 프로파일 조회"""
        with self._lock:
            return self._profiles.get(function_name)

    def get_hotspots(self, top_n: int = 10, sort_by: str = "total_time") -> List[FunctionProfile]:
        """
        핫스팟 탐지 (가장 느린 함수)

        Args:
            top_n: 반환할 함수 수
            sort_by: 정렬 기준 ("total_time", "avg_time", "call_count")

        Returns:
            상위 N개 함수 프로파일
        """
        with self._lock:
            profiles = list(self._profiles.values())

        if sort_by == "total_time":
            profiles.sort(key=lambda p: p.total_time, reverse=True)
        elif sort_by == "avg_time":
            profiles.sort(key=lambda p: p.avg_time, reverse=True)
        elif sort_by == "call_count":
            profiles.sort(key=lambda p: p.call_count, reverse=True)
        else:
            raise ValueError(f"Unknown sort_by: {sort_by}")

        return profiles[:top_n]

    def reset(self) -> None:
        """통계 초기화"""
        with self._lock:
            self._profiles.clear()


# ==================== MemoryProfiler ====================
class MemoryProfiler:
    """메모리 프로파일러"""

    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: 프로파일링 활성화
        """
        self.enabled = enabled
        self._snapshots: List[MemorySnapshot] = []
        self._profiles: Dict[str, FunctionProfile] = {}
        self._lock = threading.Lock()

    def profile(self, name: Optional[str] = None):
        """
        메모리 프로파일링 데코레이터

        Args:
            name: 프로파일 이름

        Usage:
            @profiler.profile()
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled or not PSUTIL_AVAILABLE:
                    return func(*args, **kwargs)

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
                        delta,
                        func.__module__
                    )

            return wrapper
        return decorator

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        if self.enabled and PSUTIL_AVAILABLE:
            self._start_memory = self._get_memory()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        if self.enabled and PSUTIL_AVAILABLE and hasattr(self, '_start_memory'):
            memory_after = self._get_memory()
            delta = memory_after - self._start_memory
            self._record_snapshot("__context__", self._start_memory, memory_after, delta, "__main__")
            delattr(self, '_start_memory')

    def _get_memory(self) -> float:
        """현재 프로세스 메모리 사용량 (MB)"""
        if not PSUTIL_AVAILABLE:
            return 0.0

        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0

    def _record_snapshot(
        self,
        function_name: str,
        memory_before: float,
        memory_after: float,
        delta: float,
        module_name: str = ""
    ) -> None:
        """메모리 스냅샷 기록"""
        with self._lock:
            # 스냅샷 저장
            snapshot = MemorySnapshot(
                function_name=function_name,
                timestamp=time.time(),
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=delta,
                peak_memory=memory_after
            )
            self._snapshots.append(snapshot)

            # 프로파일 업데이트
            if function_name not in self._profiles:
                self._profiles[function_name] = FunctionProfile(
                    function_name=function_name,
                    module_name=module_name
                )

            profile = self._profiles[function_name]
            profile.call_count += 1
            profile.total_memory += delta
            profile.avg_memory = profile.total_memory / profile.call_count
            profile.peak_memory = max(profile.peak_memory, memory_after)

    def get_snapshots(self) -> List[MemorySnapshot]:
        """모든 스냅샷 조회"""
        with self._lock:
            return self._snapshots.copy()

    def get_stats(self) -> Dict[str, FunctionProfile]:
        """메모리 통계 조회"""
        with self._lock:
            return self._profiles.copy()

    def detect_leaks(self, threshold_mb: float = 10.0) -> List[MemoryLeak]:
        """
        메모리 누수 탐지

        Args:
            threshold_mb: 누수 판정 임계값 (MB)

        Returns:
            메모리 누수 목록
        """
        leaks = []

        with self._lock:
            snapshots = self._snapshots.copy()

        for snapshot in snapshots:
            if snapshot.memory_delta > threshold_mb:
                leaks.append(MemoryLeak(
                    function_name=snapshot.function_name,
                    memory_increase_mb=snapshot.memory_delta,
                    timestamp=snapshot.timestamp
                ))

        return leaks

    def get_peak_memory(self) -> float:
        """피크 메모리 사용량 (MB)"""
        with self._lock:
            if not self._snapshots:
                return 0.0
            return max(s.peak_memory for s in self._snapshots)

    def reset(self) -> None:
        """통계 초기화"""
        with self._lock:
            self._snapshots.clear()
            self._profiles.clear()


# ==================== CallStackProfiler ====================
class CallStackProfiler:
    """호출 스택 프로파일러"""

    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: 프로파일링 활성화
        """
        self.enabled = enabled
        self._call_stack: deque = deque()  # 현재 호출 스택
        self._call_graph: Dict[str, List[str]] = defaultdict(list)  # caller -> callees
        self._frames: List[CallFrame] = []  # 완료된 프레임들
        self._lock = threading.Lock()

    def profile(self, name: Optional[str] = None):
        """
        호출 스택 추적 데코레이터

        Args:
            name: 프로파일 이름

        Usage:
            @profiler.profile()
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                # 현재 스택에 푸시
                frame = CallFrame(
                    function_name=profile_name,
                    depth=len(self._call_stack),
                    start_time=time.perf_counter()
                )

                with self._lock:
                    # 호출 그래프 업데이트
                    if self._call_stack:
                        caller = self._call_stack[-1].function_name
                        if profile_name not in self._call_graph[caller]:
                            self._call_graph[caller].append(profile_name)

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
                            self._frames.append(frame)

            return wrapper
        return decorator

    def get_call_graph(self) -> CallGraph:
        """호출 그래프 조회"""
        with self._lock:
            return CallGraph(edges=dict(self._call_graph))

    def get_frames(self) -> List[CallFrame]:
        """모든 호출 프레임 조회"""
        with self._lock:
            return self._frames.copy()

    def get_max_depth(self) -> int:
        """최대 호출 깊이"""
        with self._lock:
            if not self._frames:
                return 0
            return max(f.depth for f in self._frames)

    def reset(self) -> None:
        """통계 초기화"""
        with self._lock:
            self._call_stack.clear()
            self._call_graph.clear()
            self._frames.clear()


# ==================== ProfilerManager ====================
class ProfilerManager:
    """프로파일러 통합 관리 (싱글톤)"""

    def __init__(self):
        self.time_profiler = TimeProfiler(enabled=False)
        self.memory_profiler = MemoryProfiler(enabled=False)
        self.callstack_profiler = CallStackProfiler(enabled=False)
        self._enabled = False
        self._start_time = time.time()

    def enable(
        self,
        time_profile: bool = True,
        memory_profile: bool = False,
        callstack: bool = False
    ) -> None:
        """
        프로파일링 활성화

        Args:
            time_profile: 시간 프로파일링
            memory_profile: 메모리 프로파일링
            callstack: 호출 스택 추적
        """
        self._enabled = True
        self.time_profiler.enabled = time_profile
        self.memory_profiler.enabled = memory_profile and PSUTIL_AVAILABLE
        self.callstack_profiler.enabled = callstack
        self._start_time = time.time()

        logger.info(f"Profiling enabled: time={time_profile}, memory={memory_profile}, callstack={callstack}")

    def disable(self) -> None:
        """프로파일링 비활성화"""
        self._enabled = False
        self.time_profiler.enabled = False
        self.memory_profiler.enabled = False
        self.callstack_profiler.enabled = False

        logger.info("Profiling disabled")

    def is_enabled(self) -> bool:
        """프로파일링 활성화 여부"""
        return self._enabled

    def profile(
        self,
        name: Optional[str] = None,
        time_profile: bool = True,
        memory_profile: bool = False,
        callstack: bool = False
    ):
        """
        통합 프로파일링 데코레이터

        Args:
            name: 프로파일 이름
            time_profile: 시간 프로파일링
            memory_profile: 메모리 프로파일링
            callstack: 호출 스택 추적

        Usage:
            @profiler.profile(time=True, memory=True)
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            # 데코레이터 체인 (역순으로 적용)
            wrapped = func

            if callstack and self.callstack_profiler.enabled:
                wrapped = self.callstack_profiler.profile(name)(wrapped)

            if memory_profile and self.memory_profiler.enabled:
                wrapped = self.memory_profiler.profile(name)(wrapped)

            if time_profile and self.time_profiler.enabled:
                wrapped = self.time_profiler.profile(name)(wrapped)

            return wrapped

        return decorator

    def reset(self) -> None:
        """모든 통계 초기화"""
        self.time_profiler.reset()
        self.memory_profiler.reset()
        self.callstack_profiler.reset()
        self._start_time = time.time()

        logger.info("Profiling stats reset")

    def get_profiling_duration(self) -> float:
        """프로파일링 지속 시간 (초)"""
        return time.time() - self._start_time


# ==================== Reporter ====================
class Reporter:
    """보고서 생성 기본 클래스"""

    def generate(self, profiler: ProfilerManager) -> str:
        """
        보고서 생성

        Args:
            profiler: 프로파일러 매니저

        Returns:
            보고서 문자열
        """
        raise NotImplementedError


class TextReporter(Reporter):
    """텍스트 보고서"""

    def generate(self, profiler: ProfilerManager) -> str:
        """텍스트 형식 보고서 생성"""
        lines = []
        lines.append("=" * 70)
        lines.append("Performance Profiling Report")
        lines.append("=" * 70)
        lines.append("")

        # 프로파일링 기간
        duration = profiler.get_profiling_duration()
        lines.append(f"Profiling Duration: {duration:.2f} seconds")
        lines.append("")

        # 시간 프로파일링
        if profiler.time_profiler.enabled:
            lines.append("[Time Profiling]")
            lines.append("")

            # 상위 10개 핫스팟
            hotspots = profiler.time_profiler.get_hotspots(top_n=10)
            if hotspots:
                lines.append("Top 10 Hotspots (by Total Time):")
                for i, profile in enumerate(hotspots, 1):
                    lines.append(
                        f"  {i:2d}. {profile.function_name:50s} "
                        f"{profile.total_time:10.2f}ms  "
                        f"({profile.call_count:6d} calls, "
                        f"avg: {profile.avg_time:8.2f}ms)"
                    )
                lines.append("")

            # 함수별 상세 정보 (상위 5개)
            lines.append("Function Details (Top 5):")
            for profile in hotspots[:5]:
                lines.append(f"  {profile.function_name}")
                lines.append(f"    Module: {profile.module_name}")
                lines.append(f"    Calls:  {profile.call_count}")
                lines.append(f"    Total:  {profile.total_time:.2f}ms")
                lines.append(f"    Avg:    {profile.avg_time:.2f}ms (±{profile.std_time:.2f}ms)")
                lines.append(f"    Min:    {profile.min_time:.2f}ms")
                lines.append(f"    Max:    {profile.max_time:.2f}ms")
                lines.append("")

        # 메모리 프로파일링
        if profiler.memory_profiler.enabled and PSUTIL_AVAILABLE:
            lines.append("[Memory Profiling]")
            lines.append("")

            peak_memory = profiler.memory_profiler.get_peak_memory()
            lines.append(f"Peak Memory: {peak_memory:.2f} MB")
            lines.append("")

            # 메모리 사용량 상위 5개
            mem_stats = profiler.memory_profiler.get_stats()
            mem_profiles = sorted(mem_stats.values(), key=lambda p: p.total_memory, reverse=True)[:5]

            if mem_profiles:
                lines.append("Top Memory Consumers:")
                for i, profile in enumerate(mem_profiles, 1):
                    lines.append(
                        f"  {i}. {profile.function_name:50s} "
                        f"+{profile.total_memory:8.2f} MB  "
                        f"(avg: {profile.avg_memory:8.2f} MB, "
                        f"peak: {profile.peak_memory:8.2f} MB)"
                    )
                lines.append("")

            # 메모리 누수
            leaks = profiler.memory_profiler.detect_leaks(threshold_mb=10.0)
            if leaks:
                lines.append("Potential Memory Leaks:")
                for leak in leaks:
                    lines.append(f"  - {leak.function_name}: +{leak.memory_increase_mb:.2f} MB")
                lines.append("")

        # 호출 그래프
        if profiler.callstack_profiler.enabled:
            lines.append("[Call Graph]")
            lines.append("")

            call_graph = profiler.callstack_profiler.get_call_graph()
            graph_text = call_graph.to_text()
            if graph_text:
                lines.append(graph_text)
                lines.append("")

            max_depth = profiler.callstack_profiler.get_max_depth()
            lines.append(f"Maximum Call Depth: {max_depth}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


class JSONReporter(Reporter):
    """JSON 보고서"""

    def generate(self, profiler: ProfilerManager) -> str:
        """JSON 형식 보고서 생성"""
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "profiling_duration": profiler.get_profiling_duration(),
        }

        # 시간 프로파일링
        if profiler.time_profiler.enabled:
            time_stats = profiler.time_profiler.get_stats()
            report["time_profile"] = {}

            for func_name, profile in time_stats.items():
                report["time_profile"][func_name] = {
                    "module": profile.module_name,
                    "call_count": profile.call_count,
                    "total_time": profile.total_time,
                    "avg_time": profile.avg_time,
                    "min_time": profile.min_time,
                    "max_time": profile.max_time,
                    "std_time": profile.std_time,
                }

        # 메모리 프로파일링
        if profiler.memory_profiler.enabled and PSUTIL_AVAILABLE:
            mem_stats = profiler.memory_profiler.get_stats()
            report["memory_profile"] = {
                "peak_memory_mb": profiler.memory_profiler.get_peak_memory(),
                "functions": {}
            }

            for func_name, profile in mem_stats.items():
                report["memory_profile"]["functions"][func_name] = {
                    "call_count": profile.call_count,
                    "total_memory": profile.total_memory,
                    "avg_memory": profile.avg_memory,
                    "peak_memory": profile.peak_memory,
                }

        # 호출 그래프
        if profiler.callstack_profiler.enabled:
            call_graph = profiler.callstack_profiler.get_call_graph()
            report["call_graph"] = call_graph.edges
            report["max_call_depth"] = profiler.callstack_profiler.get_max_depth()

        return json.dumps(report, indent=2, ensure_ascii=False)


# ==================== 싱글톤 팩토리 ====================
_profiler_manager: Optional[ProfilerManager] = None
_profiler_lock = threading.Lock()


def get_profiler() -> ProfilerManager:
    """
    프로파일러 매니저 싱글톤 인스턴스

    Returns:
        ProfilerManager 인스턴스 (스레드 안전)
    """
    global _profiler_manager

    if _profiler_manager is None:
        with _profiler_lock:
            if _profiler_manager is None:
                _profiler_manager = ProfilerManager()

    return _profiler_manager


# ==================== 유틸리티 함수 ====================
def profile(
    name: Optional[str] = None,
    time_profile: bool = True,
    memory_profile: bool = False,
    callstack: bool = False
):
    """
    프로파일링 데코레이터 (전역 프로파일러 사용)

    Args:
        name: 프로파일 이름
        time_profile: 시간 프로파일링
        memory_profile: 메모리 프로파일링
        callstack: 호출 스택 추적

    Usage:
        @profile(time=True, memory=True)
        def my_function():
            pass
    """
    profiler = get_profiler()
    return profiler.profile(name, time_profile, memory_profile, callstack)


def enable_profiling(
    time_profile: bool = True,
    memory_profile: bool = False,
    callstack: bool = False
) -> None:
    """
    전역 프로파일링 활성화

    Args:
        time_profile: 시간 프로파일링
        memory_profile: 메모리 프로파일링
        callstack: 호출 스택 추적
    """
    profiler = get_profiler()
    profiler.enable(time_profile, memory_profile, callstack)


def disable_profiling() -> None:
    """전역 프로파일링 비활성화"""
    profiler = get_profiler()
    profiler.disable()


def get_profiling_report(format: str = "text") -> str:
    """
    프로파일링 보고서 생성

    Args:
        format: 보고서 형식 ("text", "json")

    Returns:
        보고서 문자열
    """
    profiler = get_profiler()

    if format == "text":
        reporter = TextReporter()
    elif format == "json":
        reporter = JSONReporter()
    else:
        raise ValueError(f"Unknown format: {format}")

    return reporter.generate(profiler)


def reset_profiling() -> None:
    """프로파일링 통계 초기화"""
    profiler = get_profiler()
    profiler.reset()
