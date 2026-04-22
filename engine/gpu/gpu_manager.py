# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/gpu
파일: gpu_manager.py
설명: GPU 리소스 중앙 관리자
      - VRAM 할당/해제/잔여량 추적
      - 발열 모니터링 (85°C 경고 / 95°C 크리티컬 스로틀링)
      - OOM 위험 감지 + 긴급 정리 (오래된 할당부터 해제)
      - pynvml 연동 (미설치 시 시뮬레이션 폴백)
      - GPUSnapshot frozen 스냅샷 반환 (방어적 복사)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: GPUConfig

소비자:
    - engine/gpu/tensorrt_pool.py: VRAM allocate/deallocate 위임
    - engine/gpu/cuda_stream_manager.py: GPU 상태 참조
    - engine/orchestrator/game_orchestrator.py: 발열/OOM 체크
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final

# =============================================================================
# 서드파티 (조건부 import — pynvml 미설치 시 시뮬레이션 모드)
# =============================================================================
try:
    import pynvml  # type: ignore[import-untyped]
    _PYNVML_AVAILABLE: Final[bool] = True
except ImportError:
    pynvml = None  # type: ignore[assignment]
    _PYNVML_AVAILABLE = False

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import GPUConfig

logger = logging.getLogger(__name__)


# =============================================================================
# GPU 건강 상태 열거형
# =============================================================================
@unique
class GPUHealthStatus(str, Enum):
    """
    GPU 건강 상태 열거형 (5단계).

    Attributes:
        HEALTHY: 정상 (온도 양호, VRAM 여유)
        WARNING: 경고 (온도 85°C 이상 또는 VRAM 80%+ 사용)
        THROTTLED: 스로틀링 (온도 95°C 이상, 성능 제한)
        CRITICAL: 위험 (VRAM 95%+ 사용, OOM 임박)
        UNAVAILABLE: 사용 불가 (GPU 미감지 또는 드라이버 오류)
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    THROTTLED = "throttled"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# VRAM 할당 레코드
# =============================================================================
@dataclass(frozen=True, slots=True)
class VRAMAllocation:
    """
    VRAM 할당 레코드 (불변).

    Attributes:
        name: 할당 이름 (예: "yolov8_det")
        size_mb: 할당 크기 (MB)
        allocated_at: 할당 시각 (monotonic)
    """

    name: str
    size_mb: float
    allocated_at: float


# =============================================================================
# GPU 스냅샷
# =============================================================================
@dataclass(frozen=True, slots=True)
class GPUSnapshot:
    """
    GPU 상태 스냅샷 (불변, 방어적 복사용).

    Attributes:
        health: 건강 상태
        total_vram_mb: 총 VRAM (MB)
        used_vram_mb: 사용 중 VRAM (MB)
        free_vram_mb: 잔여 VRAM (MB)
        utilization_pct: VRAM 사용률 (0~100%)
        temperature_celsius: GPU 온도 (°C)
        allocation_count: 활성 할당 수
        is_simulation: 시뮬레이션 모드 여부
        timestamp: 스냅샷 시각 (monotonic)
    """

    health: GPUHealthStatus
    total_vram_mb: float
    used_vram_mb: float
    free_vram_mb: float
    utilization_pct: float
    temperature_celsius: float
    allocation_count: int
    is_simulation: bool
    timestamp: float


# =============================================================================
# 상수
# =============================================================================
_VRAM_WARNING_RATIO: Final[float] = 0.80
_VRAM_CRITICAL_RATIO: Final[float] = 0.95
_THERMAL_CHECK_INTERVAL_SEC: Final[float] = 5.0
_SIMULATION_TOTAL_VRAM_MB: Final[float] = 8192.0
_SIMULATION_TEMPERATURE: Final[float] = 45.0
_MAX_ALLOCATIONS: Final[int] = 100


# =============================================================================
# GPU 관리자
# =============================================================================
class GPUManager:
    """
    GPU 리소스 중앙 관리자.

    pynvml을 통해 실제 GPU 상태를 모니터링하며,
    pynvml 미설치 시 시뮬레이션 모드로 동작합니다.

    Attributes:
        _config: GPU 설정
        _lock: 스레드 안전 잠금
        _allocations: 활성 VRAM 할당 맵 (이름→레코드)
        _total_vram_mb: 총 VRAM (MB)
        _is_simulation: 시뮬레이션 모드
        _nvml_handle: pynvml GPU 핸들 (None=시뮬레이션)
        _nvml_initialized: pynvml 초기화 완료 여부
        _last_thermal_check: 마지막 발열 점검 시각
        _last_temperature: 마지막 측정 온도
        _initialized: 초기화 완료 여부
        _total_allocated_mb: 누적 할당량 (해제 미반영)
    """

    __slots__ = (
        "_config",
        "_lock",
        "_allocations",
        "_total_vram_mb",
        "_is_simulation",
        "_nvml_handle",
        "_nvml_initialized",
        "_last_thermal_check",
        "_last_temperature",
        "_initialized",
        "_total_allocated_mb",
    )

    def __init__(self, config: GPUConfig | None = None) -> None:
        self._config: GPUConfig = config or GPUConfig()
        self._lock: RLock = RLock()
        self._allocations: dict[str, VRAMAllocation] = {}
        self._total_vram_mb: float = 0.0
        self._is_simulation: bool = False
        self._nvml_handle: object | None = None
        self._nvml_initialized: bool = False
        self._last_thermal_check: float = 0.0
        self._last_temperature: float = 0.0
        self._initialized: bool = False
        self._total_allocated_mb: float = 0.0

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================
    def initialize(self) -> None:
        """
        GPU 초기화.

        pynvml 연동 시도 → 실패 시 시뮬레이션 모드.
        """
        with self._lock:
            if self._initialized:
                return

            if not _PYNVML_AVAILABLE:
                self._is_simulation = True
                self._nvml_handle = None
                self._nvml_initialized = False
                if self._config.vram_limit_mb > 0:
                    self._total_vram_mb = float(self._config.vram_limit_mb)
                else:
                    self._total_vram_mb = _SIMULATION_TOTAL_VRAM_MB
                logger.warning(
                    "pynvml 미설치 → 시뮬레이션 모드 (%.0fMB)",
                    self._total_vram_mb,
                )
                self._initialized = True
                return

            try:
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self._nvml_handle = handle
                self._nvml_initialized = True
                self._is_simulation = False

                # VRAM 상한: 설정값 또는 실제값
                actual_mb = mem_info.total / (1024 * 1024)
                if self._config.vram_limit_mb > 0:
                    self._total_vram_mb = min(
                        float(self._config.vram_limit_mb), actual_mb,
                    )
                else:
                    self._total_vram_mb = actual_mb

                logger.info(
                    "GPU 초기화 완료: %.0fMB VRAM (실제 %.0fMB)",
                    self._total_vram_mb, actual_mb,
                )

            except Exception as exc:
                # pynvml 미설치 또는 GPU 없음 → 시뮬레이션
                self._is_simulation = True
                self._nvml_handle = None
                self._nvml_initialized = False

                if self._config.vram_limit_mb > 0:
                    self._total_vram_mb = float(self._config.vram_limit_mb)
                else:
                    self._total_vram_mb = _SIMULATION_TOTAL_VRAM_MB

                logger.warning(
                    "pynvml 초기화 실패 → 시뮬레이션 모드 (%.0fMB): %s",
                    self._total_vram_mb, exc,
                )

            self._initialized = True

    def shutdown(self) -> None:
        """GPU 종료 및 자원 정리."""
        with self._lock:
            if self._nvml_initialized and _PYNVML_AVAILABLE:
                try:
                    pynvml.nvmlShutdown()
                except Exception:
                    pass
                self._nvml_initialized = False
                self._nvml_handle = None

            self._allocations.clear()
            self._total_allocated_mb = 0.0
            self._initialized = False
            logger.info("GPU 관리자 종료")

    # =========================================================================
    # VRAM 할당 / 해제
    # =========================================================================
    def allocate(self, name: str, size_mb: float) -> bool:
        """
        VRAM 할당 등록.

        Args:
            name: 할당 이름 (중복 시 기존 해제 후 재할당)
            size_mb: 할당 크기 (MB)

        Returns:
            할당 성공 여부 (잔여 VRAM 부족 시 False)
        """
        with self._lock:
            # 중복 이름 → 기존 해제
            if name in self._allocations:
                self._deallocate_internal(name)

            # 잔여 VRAM 체크
            used = self._used_vram_mb
            if used + size_mb > self._total_vram_mb:
                logger.error(
                    "VRAM 부족: %s %.0fMB 요청, 잔여 %.0fMB",
                    name, size_mb, self._total_vram_mb - used,
                )
                return False

            # 할당 수 제한
            if len(self._allocations) >= _MAX_ALLOCATIONS:
                logger.error("할당 수 상한 초과: %d", _MAX_ALLOCATIONS)
                return False

            self._allocations[name] = VRAMAllocation(
                name=name,
                size_mb=size_mb,
                allocated_at=time.monotonic(),
            )
            self._total_allocated_mb += size_mb

            logger.info(
                "VRAM 할당: %s %.0fMB (사용 %.0f/%.0fMB)",
                name, size_mb, self._used_vram_mb, self._total_vram_mb,
            )
            return True

    def deallocate(self, name: str) -> float:
        """
        VRAM 할당 해제.

        Args:
            name: 해제할 할당 이름

        Returns:
            해제된 크기 (MB, 미존재 시 0.0)
        """
        with self._lock:
            return self._deallocate_internal(name)

    def _deallocate_internal(self, name: str) -> float:
        """내부 할당 해제 (lock 보유 상태에서 호출)."""
        alloc = self._allocations.pop(name, None)
        if alloc is None:
            return 0.0
        self._total_allocated_mb -= alloc.size_mb
        logger.info("VRAM 해제: %s %.0fMB", name, alloc.size_mb)
        return alloc.size_mb

    # =========================================================================
    # VRAM 조회
    # =========================================================================
    @property
    def _used_vram_mb(self) -> float:
        """현재 사용 중 VRAM (MB)."""
        return sum(a.size_mb for a in self._allocations.values())

    @property
    def vram_utilization(self) -> float:
        """VRAM 사용률 (0.0~1.0)."""
        if self._total_vram_mb <= 0:
            return 0.0
        return self._used_vram_mb / self._total_vram_mb

    @property
    def free_vram_mb(self) -> float:
        """잔여 VRAM (MB)."""
        return max(0.0, self._total_vram_mb - self._used_vram_mb)

    # =========================================================================
    # 발열 모니터링
    # =========================================================================
    def check_thermal(self) -> GPUHealthStatus:
        """
        발열 점검 (주기 제어: _THERMAL_CHECK_INTERVAL_SEC).

        Returns:
            현재 GPU 건강 상태
        """
        now = time.monotonic()
        if now - self._last_thermal_check < _THERMAL_CHECK_INTERVAL_SEC:
            return self._current_health_status()

        self._last_thermal_check = now
        self._last_temperature = self._read_temperature()

        if self._last_temperature >= self._config.thermal_critical_celsius:
            logger.warning(
                "GPU 크리티컬: %.1f°C (임계 %.1f°C)",
                self._last_temperature,
                self._config.thermal_critical_celsius,
            )
        elif self._last_temperature >= self._config.thermal_warning_celsius:
            logger.warning(
                "GPU 경고: %.1f°C (경고 %.1f°C)",
                self._last_temperature,
                self._config.thermal_warning_celsius,
            )

        return self._current_health_status()

    def _read_temperature(self) -> float:
        """GPU 온도 읽기 (pynvml 실패 시 시뮬레이션 값)."""
        if (
            self._is_simulation
            or self._nvml_handle is None
            or not _PYNVML_AVAILABLE
        ):
            return _SIMULATION_TEMPERATURE

        try:
            temp = pynvml.nvmlDeviceGetTemperature(
                self._nvml_handle,
                pynvml.NVML_TEMPERATURE_GPU,
            )
            return float(temp)
        except Exception:
            return _SIMULATION_TEMPERATURE

    # =========================================================================
    # OOM 위험 감지 + 긴급 정리
    # =========================================================================
    def check_oom_risk(self) -> bool:
        """
        OOM 위험 여부 (VRAM 사용률 >= 95%).

        Returns:
            True = OOM 위험
        """
        return self.vram_utilization >= _VRAM_CRITICAL_RATIO

    def emergency_cleanup(self) -> float:
        """
        긴급 VRAM 정리 — 오래된 할당부터 해제.

        WARNING 수준(80%)까지 확보하거나 할당이 없을 때까지 반복.

        Returns:
            해제된 총 VRAM (MB)
        """
        with self._lock:
            if self.vram_utilization < _VRAM_WARNING_RATIO:
                return 0.0

            # 할당 시각 오름차순 정렬 (오래된 순)
            sorted_allocs = sorted(
                self._allocations.values(),
                key=lambda a: a.allocated_at,
            )

            freed_total = 0.0
            for alloc in sorted_allocs:
                if self.vram_utilization < _VRAM_WARNING_RATIO:
                    break
                freed = self._deallocate_internal(alloc.name)
                freed_total += freed
                logger.warning("긴급 해제: %s %.0fMB", alloc.name, freed)

            if freed_total > 0:
                logger.warning("긴급 정리 완료: %.0fMB 해제", freed_total)

            return freed_total

    # =========================================================================
    # 스냅샷
    # =========================================================================
    def snapshot(self) -> GPUSnapshot:
        """GPU 상태 스냅샷 (frozen dataclass, 방어적 복사)."""
        with self._lock:
            used = self._used_vram_mb
            total = self._total_vram_mb
            free = max(0.0, total - used)
            util = (used / total * 100.0) if total > 0 else 0.0

            return GPUSnapshot(
                health=self._current_health_status(),
                total_vram_mb=total,
                used_vram_mb=used,
                free_vram_mb=free,
                utilization_pct=round(util, 1),
                temperature_celsius=self._last_temperature,
                allocation_count=len(self._allocations),
                is_simulation=self._is_simulation,
                timestamp=time.monotonic(),
            )

    # =========================================================================
    # 내부: 건강 상태 판정
    # =========================================================================
    def _current_health_status(self) -> GPUHealthStatus:
        """5단계 건강 상태 판정 (우선순위: UNAVAILABLE > CRITICAL > THROTTLED > WARNING > HEALTHY)."""
        if not self._initialized:
            return GPUHealthStatus.UNAVAILABLE

        # 발열 기반
        if self._last_temperature >= self._config.thermal_critical_celsius:
            return GPUHealthStatus.THROTTLED

        # VRAM 기반
        util = self.vram_utilization
        if util >= _VRAM_CRITICAL_RATIO:
            return GPUHealthStatus.CRITICAL

        # 경고 (발열 또는 VRAM)
        if (
            self._last_temperature >= self._config.thermal_warning_celsius
            or util >= _VRAM_WARNING_RATIO
        ):
            return GPUHealthStatus.WARNING

        return GPUHealthStatus.HEALTHY

    def __repr__(self) -> str:
        used = self._used_vram_mb
        return (
            f"GPUManager(vram={used:.0f}/{self._total_vram_mb:.0f}MB, "
            f"health={self._current_health_status().value}, "
            f"sim={self._is_simulation})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "GPUHealthStatus",
    "VRAMAllocation",
    "GPUSnapshot",
    "GPUManager",
]

__version__ = "1.0.0"
