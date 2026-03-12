# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: profiler.py
설명: 성능 프로파일링 (CPU, 메모리, GPU, 함수 실행 시간) - Desktop Edition

작성자: SPOIN_COURTVIEW
버전: 1.0.0
최종 수정: 2026-03-11

주요 기능:
    - CPU 프로파일링 (cProfile 기반)
    - 메모리 프로파일링 (tracemalloc 기반)
    - GPU 프로파일링 (CUDA 메모리 추적)
    - 함수 실행 시간 측정
    - 시스템 리소스 모니터링 (psutil 기반)
    - 프로파일링 결과 분석 및 보고서 생성

설계 원칙:
    - 순환 참조 방지: 최소 의존성
    - 스레드 안전: RLock 사용
    - 메모리 효율: 프로파일 데이터 자동 정리
    - 확장성: 커스텀 프로파일러 지원
    - 농구 분석 특화: FPS, 정확도 프로파일링

농구 분석 특화 기능:
    - 프레임 처리 시간 프로파일링
    - 모델 추론 시간 측정
    - 메모리 사용량 추적
    - GPU 메모리 모니터링 (CUDA)

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    profiler = PerformanceProfiler(config_loader)

    # 함수 프로파일링
    @profile_function()
    def analyze_motion(video):
        ...

    # 컨텍스트 매니저로 프로파일링
    with profiling_context("motion_analysis"):
        result = analyze(video)

    # 수동 프로파일링
    profiler.start_profiling("cpu")
    process_video(video)
    result = profiler.stop_profiling()
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import cProfile
import io
import logging
import pstats
import threading
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Generator, TypeVar
import time

# ============================================================
# 서드파티 (선택적)
# ============================================================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

# CUDA 지원 (선택적)
try:
    import torch
    TORCH_AVAILABLE = torch.cuda.is_available()
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

# ============================================================
# shared 임포트
# ============================================================
# 참고: ServiceStatus는 이 모듈에서 직접 사용하지 않음
# 필요시 상위 모듈에서 임포트

# ============================================================
# utils 임포트
# ============================================================
# 참고: Timer, get_current_timestamp는 time.perf_counter() 직접 사용으로 대체
# 프로파일링 정밀도를 위해 perf_counter 직접 사용

# ============================================================
# core_foundation 내부 임포트
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
# 상수 정의
# ============================================================
# 프로파일링 설정 키 (YAML 파일의 키와 일치)
CONFIG_KEY_PROFILER: str = "performance_profiler"  # YAML: performance_profiler 섹션
CONFIG_KEY_ENABLED: str = "enabled"
CONFIG_KEY_PROFILE_TYPES: str = "profile_types"
CONFIG_KEY_FUNCTION_PROFILING: str = "function_profiling"
CONFIG_KEY_MEMORY_PROFILING: str = "memory_profiling"
CONFIG_KEY_GPU_PROFILING: str = "gpu_profiling"
CONFIG_KEY_STORAGE: str = "storage"
CONFIG_KEY_REPORTING: str = "reporting"

# 기본 설정값 (YAML에서 오버라이드 가능)
DEFAULT_MAX_PROFILES: int = 1000
DEFAULT_CLEANUP_INTERVAL: float = 300.0  # 5분
DEFAULT_TOP_FUNCTIONS: int = 20
DEFAULT_MEMORY_TRACE_LIMIT: int = 100  # YAML: trace_allocations
DEFAULT_MIN_DURATION_MS: float = 1.0  # YAML: min_duration_ms
DEFAULT_CALL_STACK_DEPTH: int = 20  # YAML: call_stack_depth
DEFAULT_SNAPSHOT_INTERVAL: float = 60.0  # YAML: snapshot_interval
DEFAULT_MAX_SNAPSHOTS: int = 100  # YAML: max_snapshots
DEFAULT_RETENTION_DAYS: int = 7  # YAML: retention_days

# CPU 프로파일링 설정
CPU_PROFILE_SORT_KEY: str = "cumulative"  # cumulative, time, calls
DEFAULT_SAMPLING_INTERVAL: float = 0.001  # YAML: sampling_interval

# 농구 분석 특화 임계값
FPS_WARNING_THRESHOLD: float = 25.0  # FPS 경고 임계값
FRAME_TIME_WARNING_MS: float = 40.0  # 프레임 처리 시간 경고 (40ms = 25fps)
MEMORY_WARNING_MB: float = 1024.0  # 메모리 경고 임계값 (1GB)


# ============================================================
# Enum 정의
# ============================================================
class ProfileType(Enum):
    """
    프로파일 타입.

    프로파일링 종류를 정의합니다.

    Attributes:
        CPU: CPU 사용량 프로파일링
        MEMORY: 메모리 사용량 프로파일링
        GPU: GPU 사용량 프로파일링
        TIME: 실행 시간 프로파일링
        COMBINED: 복합 프로파일링
    """

    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    TIME = "time"
    COMBINED = "combined"


class ResourceType(Enum):
    """
    리소스 타입.

    시스템 리소스 종류를 정의합니다.

    Attributes:
        CPU: CPU
        MEMORY: 시스템 메모리
        GPU: GPU
        DISK: 디스크
        NETWORK: 네트워크
    """

    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    DISK = "disk"
    NETWORK = "network"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class MemorySnapshot:
    """
    메모리 스냅샷.

    특정 시점의 메모리 사용량을 나타냅니다.

    Attributes:
        timestamp: 스냅샷 시각
        current_mb: 현재 메모리 사용량 (MB)
        peak_mb: 최대 메모리 사용량 (MB)
        allocated_mb: 할당된 메모리 (MB)
        available_mb: 가용 메모리 (MB)
        percent: 메모리 사용률 (%)
        top_allocations: 상위 메모리 할당 목록
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_mb: float = 0.0
    peak_mb: float = 0.0
    allocated_mb: float = 0.0
    available_mb: float = 0.0
    percent: float = 0.0
    top_allocations: list[tuple[str, int, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "current_mb": round(self.current_mb, 2),
            "peak_mb": round(self.peak_mb, 2),
            "allocated_mb": round(self.allocated_mb, 2),
            "available_mb": round(self.available_mb, 2),
            "percent": round(self.percent, 2),
            "top_allocations": [
                {"file": f, "line": l, "size_mb": round(s, 2)}
                for f, l, s in self.top_allocations
            ],
        }

    def is_warning(self) -> bool:
        """메모리 경고 상태 확인."""
        return self.current_mb >= MEMORY_WARNING_MB


@dataclass(slots=True)
class CPUSnapshot:
    """
    CPU 스냅샷.

    특정 시점의 CPU 사용량을 나타냅니다.

    Attributes:
        timestamp: 스냅샷 시각
        percent: CPU 사용률 (%)
        user_percent: 사용자 모드 CPU (%)
        system_percent: 시스템 모드 CPU (%)
        idle_percent: 유휴 CPU (%)
        core_count: CPU 코어 수
        frequency_mhz: CPU 주파수 (MHz)
        per_core_percent: 코어별 사용률
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    percent: float = 0.0
    user_percent: float = 0.0
    system_percent: float = 0.0
    idle_percent: float = 0.0
    core_count: int = 1
    frequency_mhz: float = 0.0
    per_core_percent: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "percent": round(self.percent, 2),
            "user_percent": round(self.user_percent, 2),
            "system_percent": round(self.system_percent, 2),
            "idle_percent": round(self.idle_percent, 2),
            "core_count": self.core_count,
            "frequency_mhz": round(self.frequency_mhz, 2),
            "per_core_percent": [round(p, 2) for p in self.per_core_percent],
        }


@dataclass(slots=True)
class GPUSnapshot:
    """
    GPU 스냅샷.

    특정 시점의 GPU 사용량을 나타냅니다 (CUDA 지원 시).

    Attributes:
        timestamp: 스냅샷 시각
        available: GPU 사용 가능 여부
        device_count: GPU 장치 수
        current_device: 현재 GPU 장치 인덱스
        name: GPU 이름
        memory_allocated_mb: 할당된 GPU 메모리 (MB)
        memory_reserved_mb: 예약된 GPU 메모리 (MB)
        memory_total_mb: 전체 GPU 메모리 (MB)
        memory_percent: GPU 메모리 사용률 (%)
        utilization_percent: GPU 활용률 (%)
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    available: bool = False
    device_count: int = 0
    current_device: int = 0
    name: str = ""
    memory_allocated_mb: float = 0.0
    memory_reserved_mb: float = 0.0
    memory_total_mb: float = 0.0
    memory_percent: float = 0.0
    utilization_percent: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "available": self.available,
            "device_count": self.device_count,
            "current_device": self.current_device,
            "name": self.name,
            "memory_allocated_mb": round(self.memory_allocated_mb, 2),
            "memory_reserved_mb": round(self.memory_reserved_mb, 2),
            "memory_total_mb": round(self.memory_total_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "utilization_percent": round(self.utilization_percent, 2),
        }


@dataclass(slots=True)
class FunctionProfile:
    """
    함수 프로파일.

    개별 함수의 프로파일링 결과입니다.

    Attributes:
        name: 함수 이름
        module: 모듈 이름
        filename: 파일 경로
        line_number: 라인 번호
        call_count: 호출 횟수
        total_time_ms: 총 실행 시간 (ms)
        cumulative_time_ms: 누적 실행 시간 (ms)
        average_time_ms: 평균 실행 시간 (ms)
        min_time_ms: 최소 실행 시간 (ms)
        max_time_ms: 최대 실행 시간 (ms)
        memory_delta_mb: 메모리 변화량 (MB)
    """

    name: str
    module: str = ""
    filename: str = ""
    line_number: int = 0
    call_count: int = 0
    total_time_ms: float = 0.0
    cumulative_time_ms: float = 0.0
    average_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    memory_delta_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "name": self.name,
            "module": self.module,
            "filename": self.filename,
            "line_number": self.line_number,
            "call_count": self.call_count,
            "total_time_ms": round(self.total_time_ms, 3),
            "cumulative_time_ms": round(self.cumulative_time_ms, 3),
            "average_time_ms": round(self.average_time_ms, 3),
            "min_time_ms": round(self.min_time_ms, 3) if self.min_time_ms != float("inf") else 0.0,
            "max_time_ms": round(self.max_time_ms, 3),
            "memory_delta_mb": round(self.memory_delta_mb, 3),
        }

    def update(self, execution_time_ms: float, memory_delta_mb: float = 0.0) -> None:
        """실행 결과 업데이트."""
        self.call_count += 1
        self.total_time_ms += execution_time_ms
        self.cumulative_time_ms = self.total_time_ms
        self.average_time_ms = self.total_time_ms / self.call_count
        self.min_time_ms = min(self.min_time_ms, execution_time_ms)
        self.max_time_ms = max(self.max_time_ms, execution_time_ms)
        self.memory_delta_mb += memory_delta_mb

    def is_slow(self, threshold_ms: float = FRAME_TIME_WARNING_MS) -> bool:
        """느린 함수 여부 확인."""
        return self.average_time_ms > threshold_ms


@dataclass(slots=True)
class ProfileResult:
    """
    프로파일 결과.

    프로파일링 세션의 전체 결과입니다.

    Attributes:
        profile_id: 프로파일 고유 ID
        profile_type: 프로파일 타입
        name: 프로파일 이름
        start_time: 시작 시각
        end_time: 종료 시각
        duration_ms: 소요 시간 (ms)
        cpu_snapshot: CPU 스냅샷
        memory_snapshot: 메모리 스냅샷
        gpu_snapshot: GPU 스냅샷
        function_profiles: 함수별 프로파일 목록
        cprofile_stats: cProfile 통계 문자열
        warnings: 경고 메시지 목록
        metadata: 추가 메타데이터
    """

    profile_id: str
    profile_type: ProfileType
    name: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    duration_ms: float = 0.0
    cpu_snapshot: CPUSnapshot | None = None
    memory_snapshot: MemorySnapshot | None = None
    gpu_snapshot: GPUSnapshot | None = None
    function_profiles: list[FunctionProfile] = field(default_factory=list)
    cprofile_stats: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type.value,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 3),
            "cpu_snapshot": self.cpu_snapshot.to_dict() if self.cpu_snapshot else None,
            "memory_snapshot": self.memory_snapshot.to_dict() if self.memory_snapshot else None,
            "gpu_snapshot": self.gpu_snapshot.to_dict() if self.gpu_snapshot else None,
            "function_profiles": [fp.to_dict() for fp in self.function_profiles],
            "cprofile_stats": self.cprofile_stats,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

    def get_top_functions(self, limit: int = DEFAULT_TOP_FUNCTIONS) -> list[FunctionProfile]:
        """상위 함수 프로파일 반환 (총 시간 기준)."""
        return sorted(
            self.function_profiles,
            key=lambda fp: fp.total_time_ms,
            reverse=True,
        )[:limit]

    def has_warnings(self) -> bool:
        """경고 존재 여부."""
        return len(self.warnings) > 0


# ============================================================
# PerformanceProfiler 메인 클래스
# ============================================================
class PerformanceProfiler:
    """
    성능 프로파일러.

    시스템 전체의 성능을 프로파일링합니다.
    DI 컨테이너에 등록되어 주입받아 사용합니다.

    주요 기능:
        - CPU 프로파일링 (cProfile)
        - 메모리 프로파일링 (tracemalloc)
        - GPU 프로파일링 (CUDA)
        - 함수 실행 시간 측정
        - 시스템 리소스 모니터링

    Example:
        >>> profiler = PerformanceProfiler(config_loader)
        >>> profiler.start_profiling(ProfileType.COMBINED, "motion_analysis")
        >>> result = analyze_motion(video)
        >>> profile = profiler.stop_profiling()
        >>> print(profile.duration_ms)
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        enabled: bool | None = None,
        cpu_enabled: bool | None = None,
        memory_enabled: bool | None = None,
        gpu_enabled: bool | None = None,
        max_profiles: int | None = None,
    ) -> None:
        """
        PerformanceProfiler 초기화.

        Args:
            config_loader: 설정 로더 (None이면 싱글톤 사용)
            enabled: 프로파일러 활성화 여부
            cpu_enabled: CPU 프로파일링 활성화
            memory_enabled: 메모리 프로파일링 활성화
            gpu_enabled: GPU 프로파일링 활성화
            max_profiles: 최대 프로파일 저장 수
        """
        self._config_loader = config_loader or ConfigLoader.get_instance()

        # YAML 설정 로드
        config = self._load_profiler_config()

        # 파라미터 > YAML > 기본값 우선순위 (기본 설정)
        self._enabled = enabled if enabled is not None else config.get("enabled", True)
        self._cpu_enabled = cpu_enabled if cpu_enabled is not None else config.get("cpu_enabled", True)
        self._memory_enabled = memory_enabled if memory_enabled is not None else config.get("memory_enabled", True)
        self._gpu_enabled = gpu_enabled if gpu_enabled is not None else config.get("gpu_enabled", TORCH_AVAILABLE)
        self._max_profiles = max_profiles if max_profiles is not None else config.get("max_profiles", DEFAULT_MAX_PROFILES)
        self._auto_cleanup = config.get("auto_cleanup", True)
        self._cleanup_interval = config.get("cleanup_interval_seconds", DEFAULT_CLEANUP_INTERVAL)

        # CPU 프로파일링 설정 (YAML에서 로드)
        self._sampling_interval: float = config.get("sampling_interval", DEFAULT_SAMPLING_INTERVAL)

        # 메모리 프로파일링 설정 (YAML에서 로드)
        self._trace_allocations: int = config.get("trace_allocations", DEFAULT_MEMORY_TRACE_LIMIT)
        self._snapshot_interval: float = config.get("snapshot_interval", DEFAULT_SNAPSHOT_INTERVAL)
        self._max_snapshots: int = config.get("max_snapshots", DEFAULT_MAX_SNAPSHOTS)
        self._leak_detection: bool = config.get("leak_detection", True)

        # 함수 프로파일링 설정 (YAML에서 로드)
        self._function_profiling_enabled: bool = config.get("function_profiling_enabled", True)
        self._min_duration_ms: float = config.get("min_duration_ms", DEFAULT_MIN_DURATION_MS)
        self._call_stack_depth: int = config.get("call_stack_depth", DEFAULT_CALL_STACK_DEPTH)
        self._hotspot_detection: bool = config.get("hotspot_detection", True)

        # GPU 프로파일링 설정 (YAML에서 로드)
        self._cuda_profiling: bool = config.get("cuda_profiling", True)
        self._track_kernel_time: bool = config.get("track_kernel_time", True)
        self._track_memory_transfer: bool = config.get("track_memory_transfer", True)

        # 저장 설정 (YAML에서 로드)
        self._storage_enabled: bool = config.get("storage_enabled", True)
        self._storage_path: str = config.get("storage_path", "profiling")
        self._retention_days: int = config.get("retention_days", DEFAULT_RETENTION_DAYS)

        # 리포트 설정 (YAML에서 로드)
        self._reporting_enabled: bool = config.get("reporting_enabled", True)
        self._report_formats: list[str] = config.get("report_formats", ["json", "html"])
        self._auto_generate: bool = config.get("auto_generate", True)

        # 프로파일링 상태
        self._active_profile: ProfileResult | None = None
        self._cprofile: cProfile.Profile | None = None
        self._memory_tracing: bool = False
        self._profile_start_time: float = 0.0
        self._profile_start_memory: float = 0.0

        # 저장소
        self._profiles: dict[str, ProfileResult] = {}
        self._function_profiles: dict[str, FunctionProfile] = {}

        # 스레드 락
        self._lock = threading.RLock()

        # 생성 시각
        self._created_at = datetime.now(timezone.utc)
        self._profile_counter: int = 0

        # 마지막 정리 시각
        self._last_cleanup = time.time()

        logger.info(
            f"PerformanceProfiler 초기화 완료 "
            f"(enabled={self._enabled}, cpu={self._cpu_enabled}, "
            f"memory={self._memory_enabled}, gpu={self._gpu_enabled}, "
            f"trace_allocations={self._trace_allocations})"
        )

    def _load_profiler_config(self) -> dict[str, Any]:
        """
        YAML 설정에서 프로파일러 설정 로드.

        YAML 구조:
            performance_profiler:
                enabled: true
                profile_types:
                    cpu: { enabled: true, sampling_interval: 0.001 }
                    memory: { enabled: true, trace_allocations: 100 }
                    gpu: { enabled: true, cuda_profiling: true }
                function_profiling:
                    enabled: true
                    min_duration_ms: 1.0
                    call_stack_depth: 20
                memory_profiling:
                    snapshot_interval: 60
                    max_snapshots: 100
                storage:
                    path: "profiling"
                    retention_days: 7
        """
        try:
            profiler_config = self._config_loader.get(CONFIG_KEY_PROFILER, {})
            if not isinstance(profiler_config, dict):
                profiler_config = {}

            # profile_types 섹션
            profile_types = profiler_config.get(CONFIG_KEY_PROFILE_TYPES, {})
            cpu_config = profile_types.get("cpu", {})
            memory_config = profile_types.get("memory", {})
            gpu_config = profile_types.get("gpu", {})

            # function_profiling 섹션
            func_profiling = profiler_config.get(CONFIG_KEY_FUNCTION_PROFILING, {})

            # memory_profiling 섹션
            mem_profiling = profiler_config.get(CONFIG_KEY_MEMORY_PROFILING, {})

            # storage 섹션
            storage_config = profiler_config.get(CONFIG_KEY_STORAGE, {})

            # reporting 섹션
            reporting_config = profiler_config.get(CONFIG_KEY_REPORTING, {})

            return {
                # 전역 활성화
                "enabled": profiler_config.get(CONFIG_KEY_ENABLED, True),

                # 프로파일 타입별 활성화
                "cpu_enabled": cpu_config.get("enabled", True),
                "memory_enabled": memory_config.get("enabled", True),
                "gpu_enabled": gpu_config.get("enabled", TORCH_AVAILABLE),

                # CPU 프로파일링 설정
                "sampling_interval": cpu_config.get("sampling_interval", DEFAULT_SAMPLING_INTERVAL),

                # 메모리 프로파일링 설정
                "trace_allocations": memory_config.get("trace_allocations", DEFAULT_MEMORY_TRACE_LIMIT),
                "snapshot_interval": mem_profiling.get("snapshot_interval", DEFAULT_SNAPSHOT_INTERVAL),
                "max_snapshots": mem_profiling.get("max_snapshots", DEFAULT_MAX_SNAPSHOTS),
                "leak_detection": mem_profiling.get("leak_detection", True),

                # 함수 프로파일링 설정
                "function_profiling_enabled": func_profiling.get("enabled", True),
                "min_duration_ms": func_profiling.get("min_duration_ms", DEFAULT_MIN_DURATION_MS),
                "call_stack_depth": func_profiling.get("call_stack_depth", DEFAULT_CALL_STACK_DEPTH),
                "hotspot_detection": func_profiling.get("hotspot_detection", True),

                # GPU 프로파일링 설정
                "cuda_profiling": gpu_config.get("cuda_profiling", True),
                "track_kernel_time": profiler_config.get(CONFIG_KEY_GPU_PROFILING, {}).get("track_kernel_time", True),
                "track_memory_transfer": profiler_config.get(CONFIG_KEY_GPU_PROFILING, {}).get("track_memory_transfer", True),

                # 저장 설정
                "storage_enabled": storage_config.get("enabled", True),
                "storage_path": storage_config.get("path", "profiling"),
                "retention_days": storage_config.get("retention_days", DEFAULT_RETENTION_DAYS),

                # 리포트 설정
                "reporting_enabled": reporting_config.get("enabled", True),
                "report_formats": reporting_config.get("formats", ["json", "html"]),
                "auto_generate": reporting_config.get("auto_generate", True),

                # 자동 정리 (YAML에 없으면 기본값)
                "max_profiles": DEFAULT_MAX_PROFILES,
                "auto_cleanup": True,
                "cleanup_interval_seconds": DEFAULT_CLEANUP_INTERVAL,
            }
        except Exception as e:
            logger.warning(f"프로파일러 설정 로드 실패, 기본값 사용: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """기본 설정 반환."""
        return {
            "enabled": True,
            "cpu_enabled": True,
            "memory_enabled": True,
            "gpu_enabled": TORCH_AVAILABLE,
            "sampling_interval": DEFAULT_SAMPLING_INTERVAL,
            "trace_allocations": DEFAULT_MEMORY_TRACE_LIMIT,
            "snapshot_interval": DEFAULT_SNAPSHOT_INTERVAL,
            "max_snapshots": DEFAULT_MAX_SNAPSHOTS,
            "leak_detection": True,
            "function_profiling_enabled": True,
            "min_duration_ms": DEFAULT_MIN_DURATION_MS,
            "call_stack_depth": DEFAULT_CALL_STACK_DEPTH,
            "hotspot_detection": True,
            "cuda_profiling": True,
            "track_kernel_time": True,
            "track_memory_transfer": True,
            "storage_enabled": True,
            "storage_path": "profiling",
            "retention_days": DEFAULT_RETENTION_DAYS,
            "reporting_enabled": True,
            "report_formats": ["json", "html"],
            "auto_generate": True,
            "max_profiles": DEFAULT_MAX_PROFILES,
            "auto_cleanup": True,
            "cleanup_interval_seconds": DEFAULT_CLEANUP_INTERVAL,
        }

    def _generate_profile_id(self) -> str:
        """프로파일 ID 생성."""
        with self._lock:
            self._profile_counter += 1
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            return f"profile_{timestamp}_{self._profile_counter:06d}"

    def _check_max_profiles(self) -> None:
        """최대 프로파일 수 체크 및 정리."""
        with self._lock:
            if len(self._profiles) >= self._max_profiles:
                # 가장 오래된 프로파일 삭제
                oldest = sorted(
                    self._profiles.items(),
                    key=lambda x: x[1].start_time
                )
                to_remove = len(self._profiles) - self._max_profiles + 1
                for profile_id, _ in oldest[:to_remove]:
                    del self._profiles[profile_id]
                    logger.debug(f"오래된 프로파일 삭제: {profile_id}")

    def _maybe_cleanup(self) -> None:
        """자동 정리 실행 (필요 시)."""
        if not self._auto_cleanup:
            return

        # 최대 프로파일 수 초과 시 즉시 정리 (시간 간격 무관)
        if len(self._profiles) >= self._max_profiles:
            self._check_max_profiles()
            return

        # 주기적 정리 (시간 간격 기반)
        current_time = time.time()
        if current_time - self._last_cleanup >= self._cleanup_interval:
            self._check_max_profiles()
            self._last_cleanup = current_time

    # --------------------------------------------------------
    # CPU 스냅샷
    # --------------------------------------------------------
    def get_cpu_snapshot(self) -> CPUSnapshot:
        """현재 CPU 스냅샷 반환."""
        snapshot = CPUSnapshot()

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil이 설치되지 않아 CPU 스냅샷을 가져올 수 없습니다")
            return snapshot

        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_times = psutil.cpu_times_percent(interval=0.1)

            snapshot.percent = cpu_percent
            snapshot.user_percent = cpu_times.user
            snapshot.system_percent = cpu_times.system
            snapshot.idle_percent = cpu_times.idle
            snapshot.core_count = psutil.cpu_count()

            # CPU 주파수
            try:
                freq = psutil.cpu_freq()
                if freq:
                    snapshot.frequency_mhz = freq.current
            except Exception:
                pass

            # 코어별 사용률
            snapshot.per_core_percent = psutil.cpu_percent(percpu=True)

        except Exception as e:
            logger.error(f"CPU 스냅샷 생성 실패: {e}")

        return snapshot

    # --------------------------------------------------------
    # 메모리 스냅샷
    # --------------------------------------------------------
    def get_memory_snapshot(self) -> MemorySnapshot:
        """현재 메모리 스냅샷 반환."""
        snapshot = MemorySnapshot()

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil이 설치되지 않아 메모리 스냅샷을 가져올 수 없습니다")
            return snapshot

        try:
            # 시스템 메모리
            mem = psutil.virtual_memory()
            snapshot.available_mb = mem.available / (1024 * 1024)
            snapshot.percent = mem.percent

            # 프로세스 메모리
            process = psutil.Process()
            mem_info = process.memory_info()
            snapshot.current_mb = mem_info.rss / (1024 * 1024)

            # tracemalloc 정보 (활성화된 경우)
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                snapshot.allocated_mb = current / (1024 * 1024)
                snapshot.peak_mb = peak / (1024 * 1024)

                # 상위 메모리 할당 (YAML에서 설정된 trace_allocations 사용)
                snap = tracemalloc.take_snapshot()
                top_stats = snap.statistics("lineno")[:self._trace_allocations]
                snapshot.top_allocations = [
                    (str(stat.traceback), stat.count, stat.size / (1024 * 1024))
                    for stat in top_stats
                ]

        except Exception as e:
            logger.error(f"메모리 스냅샷 생성 실패: {e}")

        return snapshot

    # --------------------------------------------------------
    # GPU 스냅샷
    # --------------------------------------------------------
    def get_gpu_snapshot(self) -> GPUSnapshot:
        """현재 GPU 스냅샷 반환."""
        snapshot = GPUSnapshot()

        if not TORCH_AVAILABLE:
            return snapshot

        try:
            snapshot.available = True
            snapshot.device_count = torch.cuda.device_count()
            snapshot.current_device = torch.cuda.current_device()
            snapshot.name = torch.cuda.get_device_name(snapshot.current_device)

            # GPU 메모리
            snapshot.memory_allocated_mb = torch.cuda.memory_allocated() / (1024 * 1024)
            snapshot.memory_reserved_mb = torch.cuda.memory_reserved() / (1024 * 1024)

            # 전체 메모리
            props = torch.cuda.get_device_properties(snapshot.current_device)
            snapshot.memory_total_mb = props.total_memory / (1024 * 1024)

            if snapshot.memory_total_mb > 0:
                snapshot.memory_percent = (
                    snapshot.memory_allocated_mb / snapshot.memory_total_mb * 100
                )

        except Exception as e:
            logger.error(f"GPU 스냅샷 생성 실패: {e}")
            snapshot.available = False

        return snapshot

    # --------------------------------------------------------
    # 프로파일링 시작/중지
    # --------------------------------------------------------
    def start_profiling(
        self,
        profile_type: ProfileType | str = ProfileType.COMBINED,
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        프로파일링 시작.

        Args:
            profile_type: 프로파일 타입
            name: 프로파일 이름
            metadata: 추가 메타데이터

        Returns:
            프로파일 ID
        """
        if not self._enabled:
            return ""

        # 문자열을 Enum으로 변환
        if isinstance(profile_type, str):
            profile_type = ProfileType(profile_type)

        with self._lock:
            # 이미 활성 프로파일이 있으면 중지
            if self._active_profile:
                logger.warning("이미 활성 프로파일이 있습니다. 기존 프로파일을 중지합니다.")
                self.stop_profiling()

            profile_id = self._generate_profile_id()

            self._active_profile = ProfileResult(
                profile_id=profile_id,
                profile_type=profile_type,
                name=name or profile_id,
                metadata=metadata or {},
            )

            self._profile_start_time = time.perf_counter()

            # CPU 프로파일링 시작
            if self._cpu_enabled and profile_type in (ProfileType.CPU, ProfileType.COMBINED):
                self._cprofile = cProfile.Profile()
                self._cprofile.enable()

            # 메모리 프로파일링 시작
            if self._memory_enabled and profile_type in (ProfileType.MEMORY, ProfileType.COMBINED):
                if not tracemalloc.is_tracing():
                    tracemalloc.start()
                    self._memory_tracing = True
                self._profile_start_memory = self._get_current_memory_mb()

            logger.debug(f"프로파일링 시작: {profile_id} ({profile_type.value})")
            return profile_id

    def stop_profiling(self) -> ProfileResult | None:
        """
        프로파일링 중지.

        Returns:
            프로파일 결과 (활성 프로파일이 없으면 None)
        """
        if not self._enabled:
            return None

        with self._lock:
            if not self._active_profile:
                logger.warning("활성 프로파일이 없습니다")
                return None

            profile = self._active_profile
            profile.end_time = datetime.now(timezone.utc)
            profile.duration_ms = (time.perf_counter() - self._profile_start_time) * 1000

            # CPU 프로파일링 중지
            if self._cprofile:
                self._cprofile.disable()
                profile.cprofile_stats = self._get_cprofile_stats()
                profile.cpu_snapshot = self.get_cpu_snapshot()
                self._cprofile = None

            # 메모리 프로파일링 중지
            if self._memory_tracing:
                profile.memory_snapshot = self.get_memory_snapshot()
                tracemalloc.stop()
                self._memory_tracing = False

            # GPU 스냅샷
            if self._gpu_enabled:
                profile.gpu_snapshot = self.get_gpu_snapshot()

            # 경고 생성
            self._generate_warnings(profile)

            # 저장
            self._profiles[profile.profile_id] = profile
            self._active_profile = None

            # 자동 정리
            self._maybe_cleanup()

            logger.debug(f"프로파일링 완료: {profile.profile_id} ({profile.duration_ms:.2f}ms)")
            return profile

    def _get_cprofile_stats(self) -> str:
        """cProfile 통계 문자열 반환."""
        if not self._cprofile:
            return ""

        try:
            stream = io.StringIO()
            stats = pstats.Stats(self._cprofile, stream=stream)
            stats.sort_stats(CPU_PROFILE_SORT_KEY)
            stats.print_stats(DEFAULT_TOP_FUNCTIONS)
            return stream.getvalue()
        except Exception as e:
            logger.error(f"cProfile 통계 생성 실패: {e}")
            return ""

    def _get_current_memory_mb(self) -> float:
        """현재 프로세스 메모리 사용량 (MB)."""
        if not PSUTIL_AVAILABLE:
            return 0.0

        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def _generate_warnings(self, profile: ProfileResult) -> None:
        """프로파일 경고 생성."""
        # 실행 시간 경고
        if profile.duration_ms > FRAME_TIME_WARNING_MS:
            profile.warnings.append(
                f"실행 시간이 {profile.duration_ms:.2f}ms로 "
                f"임계값({FRAME_TIME_WARNING_MS}ms)을 초과했습니다"
            )

        # 메모리 경고
        if profile.memory_snapshot and profile.memory_snapshot.is_warning():
            profile.warnings.append(
                f"메모리 사용량이 {profile.memory_snapshot.current_mb:.2f}MB로 "
                f"임계값({MEMORY_WARNING_MB}MB)을 초과했습니다"
            )

        # GPU 메모리 경고
        if profile.gpu_snapshot and profile.gpu_snapshot.memory_percent > 90:
            profile.warnings.append(
                f"GPU 메모리 사용률이 {profile.gpu_snapshot.memory_percent:.1f}%로 높습니다"
            )

    # --------------------------------------------------------
    # 함수 프로파일링
    # --------------------------------------------------------
    def profile_function_call(
        self,
        func_name: str,
        execution_time_ms: float,
        memory_delta_mb: float = 0.0,
        module: str = "",
        filename: str = "",
        line_number: int = 0,
    ) -> FunctionProfile:
        """
        함수 호출 프로파일 기록.

        Args:
            func_name: 함수 이름
            execution_time_ms: 실행 시간 (ms)
            memory_delta_mb: 메모리 변화량 (MB)
            module: 모듈 이름
            filename: 파일 경로
            line_number: 라인 번호

        Returns:
            함수 프로파일
        """
        with self._lock:
            key = f"{module}.{func_name}" if module else func_name

            if key not in self._function_profiles:
                self._function_profiles[key] = FunctionProfile(
                    name=func_name,
                    module=module,
                    filename=filename,
                    line_number=line_number,
                )

            profile = self._function_profiles[key]
            profile.update(execution_time_ms, memory_delta_mb)
            return profile

    def get_function_profile(self, func_name: str, module: str = "") -> FunctionProfile | None:
        """함수 프로파일 조회."""
        key = f"{module}.{func_name}" if module else func_name
        return self._function_profiles.get(key)

    def get_all_function_profiles(self) -> list[FunctionProfile]:
        """모든 함수 프로파일 반환."""
        return list(self._function_profiles.values())

    def get_slow_functions(self, threshold_ms: float = FRAME_TIME_WARNING_MS) -> list[FunctionProfile]:
        """느린 함수 목록 반환."""
        return [
            fp for fp in self._function_profiles.values()
            if fp.is_slow(threshold_ms)
        ]

    # --------------------------------------------------------
    # 유틸리티 메서드
    # --------------------------------------------------------
    def get_profile(self, profile_id: str) -> ProfileResult | None:
        """프로파일 결과 조회."""
        return self._profiles.get(profile_id)

    def get_all_profiles(self) -> list[ProfileResult]:
        """모든 프로파일 반환."""
        return list(self._profiles.values())

    def get_recent_profiles(self, limit: int = 10) -> list[ProfileResult]:
        """최근 프로파일 반환."""
        profiles = sorted(
            self._profiles.values(),
            key=lambda p: p.start_time,
            reverse=True,
        )
        return profiles[:limit]

    def clear_profiles(self) -> int:
        """모든 프로파일 삭제."""
        with self._lock:
            count = len(self._profiles)
            self._profiles.clear()
            logger.info(f"{count}개 프로파일 삭제됨")
            return count

    def clear_function_profiles(self) -> int:
        """모든 함수 프로파일 삭제."""
        with self._lock:
            count = len(self._function_profiles)
            self._function_profiles.clear()
            logger.info(f"{count}개 함수 프로파일 삭제됨")
            return count

    def get_status(self) -> dict[str, Any]:
        """프로파일러 상태 조회 (모든 YAML 설정 포함)."""
        with self._lock:
            return {
                # 기본 상태
                "enabled": self._enabled,
                "cpu_enabled": self._cpu_enabled,
                "memory_enabled": self._memory_enabled,
                "gpu_enabled": self._gpu_enabled,
                "gpu_available": TORCH_AVAILABLE,
                "psutil_available": PSUTIL_AVAILABLE,

                # 프로파일 저장 상태
                "max_profiles": self._max_profiles,
                "profiles_count": len(self._profiles),
                "function_profiles_count": len(self._function_profiles),
                "active_profile": self._active_profile.profile_id if self._active_profile else None,
                "memory_tracing": self._memory_tracing,

                # CPU 프로파일링 설정
                "sampling_interval": self._sampling_interval,

                # 메모리 프로파일링 설정
                "trace_allocations": self._trace_allocations,
                "snapshot_interval": self._snapshot_interval,
                "max_snapshots": self._max_snapshots,
                "leak_detection": self._leak_detection,

                # 함수 프로파일링 설정
                "function_profiling_enabled": self._function_profiling_enabled,
                "min_duration_ms": self._min_duration_ms,
                "call_stack_depth": self._call_stack_depth,
                "hotspot_detection": self._hotspot_detection,

                # GPU 프로파일링 설정
                "cuda_profiling": self._cuda_profiling,
                "track_kernel_time": self._track_kernel_time,
                "track_memory_transfer": self._track_memory_transfer,

                # 저장 설정
                "storage_enabled": self._storage_enabled,
                "storage_path": self._storage_path,
                "retention_days": self._retention_days,

                # 리포트 설정
                "reporting_enabled": self._reporting_enabled,
                "report_formats": self._report_formats,
                "auto_generate": self._auto_generate,

                # 시간 정보
                "created_at": self._created_at.isoformat(),
            }

    def __repr__(self) -> str:
        """PerformanceProfiler 인스턴스 표현."""
        with self._lock:
            profiles_count = len(self._profiles)
            func_count = len(self._function_profiles)
        return (
            f"PerformanceProfiler(enabled={self._enabled}, "
            f"profiles={profiles_count}/{self._max_profiles}, "
            f"functions={func_count})"
        )

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
            logger.info(f"PerformanceProfiler 활성화 상태 변경: {old_value} -> {value}")


# ============================================================
# 싱글톤 인스턴스 관리
# ============================================================
_profiler_instance: PerformanceProfiler | None = None
_profiler_lock: threading.Lock = threading.Lock()


def _get_profiler() -> PerformanceProfiler:
    """전역 PerformanceProfiler 인스턴스 반환."""
    global _profiler_instance

    if _profiler_instance is None:
        with _profiler_lock:
            if _profiler_instance is None:
                _profiler_instance = PerformanceProfiler()

    return _profiler_instance


def _reset_profiler() -> None:
    """전역 PerformanceProfiler 인스턴스 리셋 (테스트용)."""
    global _profiler_instance

    with _profiler_lock:
        _profiler_instance = None


# ============================================================
# 데코레이터
# ============================================================
def profile_function(
    name: str | None = None,
    profile_memory: bool = False,
) -> Callable[[F], F]:
    """
    함수 프로파일링 데코레이터.

    함수 실행 시간과 호출 횟수를 자동으로 기록합니다.

    Args:
        name: 프로파일 이름 (None이면 함수 이름 사용)
        profile_memory: 메모리 변화량 추적 여부

    Returns:
        데코레이터 함수

    Example:
        >>> @profile_function()
        ... def process_frame(frame):
        ...     ...

        >>> @profile_function(name="motion_analysis", profile_memory=True)
        ... def analyze_motion(video):
        ...     ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            profiler = _get_profiler()

            if not profiler.enabled:
                return func(*args, **kwargs)

            func_name = name or func.__name__
            module = func.__module__ if hasattr(func, "__module__") else ""

            # 메모리 시작점
            start_memory = 0.0
            if profile_memory and PSUTIL_AVAILABLE:
                try:
                    start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                except Exception:
                    pass

            # 실행 시간 측정
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # 메모리 변화량
                memory_delta = 0.0
                if profile_memory and PSUTIL_AVAILABLE:
                    try:
                        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                        memory_delta = end_memory - start_memory
                    except Exception:
                        pass

                # 프로파일 기록
                profiler.profile_function_call(
                    func_name=func_name,
                    execution_time_ms=elapsed_ms,
                    memory_delta_mb=memory_delta,
                    module=module,
                )

        return wrapper  # type: ignore

    return decorator


def profile_memory(
    name: str | None = None,
) -> Callable[[F], F]:
    """
    메모리 프로파일링 데코레이터.

    함수 실행 전후의 메모리 변화를 추적합니다.

    Args:
        name: 프로파일 이름 (None이면 함수 이름 사용)

    Returns:
        데코레이터 함수

    Example:
        >>> @profile_memory()
        ... def load_model():
        ...     ...
    """
    return profile_function(name=name, profile_memory=True)


# ============================================================
# 컨텍스트 매니저
# ============================================================
@contextmanager
def profiling_context(
    name: str = "",
    profile_type: ProfileType | str = ProfileType.COMBINED,
    metadata: dict[str, Any] | None = None,
) -> Generator[str | None, None, None]:
    """
    프로파일링 컨텍스트 매니저.

    블록 내 코드를 자동으로 프로파일링합니다.

    Args:
        name: 프로파일 이름
        profile_type: 프로파일 타입
        metadata: 추가 메타데이터

    Yields:
        프로파일 ID

    Example:
        >>> with profiling_context("motion_analysis") as profile_id:
        ...     result = analyze_motion(video)
        >>> profile = profiler.get_profile(profile_id)
    """
    profiler = _get_profiler()

    if not profiler.enabled:
        yield None
        return

    profile_id = profiler.start_profiling(
        profile_type=profile_type,
        name=name,
        metadata=metadata,
    )

    try:
        yield profile_id
    finally:
        profiler.stop_profiling()


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum
    "ProfileType",
    "ResourceType",
    # 상수
    "DEFAULT_MAX_PROFILES",
    "DEFAULT_CLEANUP_INTERVAL",
    "DEFAULT_TOP_FUNCTIONS",
    "DEFAULT_MEMORY_TRACE_LIMIT",
    "FPS_WARNING_THRESHOLD",
    "FRAME_TIME_WARNING_MS",
    "MEMORY_WARNING_MB",
    # 데이터 클래스
    "ProfileResult",
    "MemorySnapshot",
    "CPUSnapshot",
    "GPUSnapshot",
    "FunctionProfile",
    # 메인 클래스
    "PerformanceProfiler",
    # 데코레이터
    "profile_function",
    "profile_memory",
    # 컨텍스트 매니저
    "profiling_context",
    # 내부 함수 (테스트용)
    "_get_profiler",
    "_reset_profiler",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
