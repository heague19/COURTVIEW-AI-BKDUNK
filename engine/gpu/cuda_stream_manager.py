# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/gpu
파일: cuda_stream_manager.py
설명: CUDA Stream 중앙 관리자
      - Stage1 (감지+포즈+ReID): CUDA Stream #1
      - Stage2 (ViTPose 정밀 추정): CUDA Stream #2
      - 각 스트림 독립 실행 (S1 실행 중 S2 시작 가능)
      - 실행 시간 프로파일링 (perf_counter 기반)
      - torch.cuda 미설치 시 시뮬레이션 폴백

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: GPUConfig

소비자:
    - engine/gpu/tensorrt_pool.py: 스트림 바인딩
    - engine/pipeline/frame_pipeline.py: 추론 실행 시 스트림 제어
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
from typing import Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import GPUConfig

logger = logging.getLogger(__name__)


# =============================================================================
# 스트림 식별자
# =============================================================================
@unique
class StreamID(str, Enum):
    """
    CUDA 스트림 식별자 (2종).

    Attributes:
        STAGE1: 감지 + YOLOv8-Pose + ReID (메인 추론)
        STAGE2: ViTPose 정밀 추정 (트리거 시에만)
    """

    STAGE1 = "stage1"
    STAGE2 = "stage2"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 스트림 상태
# =============================================================================
@unique
class StreamStatus(str, Enum):
    """
    스트림 실행 상태 (3종).

    Attributes:
        IDLE: 유휴 (실행 가능)
        RUNNING: 실행 중
        SYNCHRONIZING: 동기화 중
    """

    IDLE = "idle"
    RUNNING = "running"
    SYNCHRONIZING = "synchronizing"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 스트림 프로파일
# =============================================================================
@dataclass(slots=True)
class StreamProfile:
    """
    스트림 실행 성능 프로파일.

    Attributes:
        total_executions: 총 실행 횟수
        total_time_ms: 총 실행 시간 (ms)
        peak_time_ms: 최대 실행 시간 (ms)
        last_time_ms: 마지막 실행 시간 (ms)
    """

    total_executions: int = 0
    total_time_ms: float = 0.0
    peak_time_ms: float = 0.0
    last_time_ms: float = 0.0

    @property
    def avg_time_ms(self) -> float:
        """평균 실행 시간 (ms)."""
        if self.total_executions <= 0:
            return 0.0
        return self.total_time_ms / self.total_executions

    def record(self, elapsed_ms: float) -> None:
        """실행 시간 기록."""
        self.total_executions += 1
        self.total_time_ms += elapsed_ms
        self.last_time_ms = elapsed_ms
        if elapsed_ms > self.peak_time_ms:
            self.peak_time_ms = elapsed_ms


# =============================================================================
# 내부 스트림 래퍼
# =============================================================================
class _StreamWrapper:
    """
    개별 CUDA 스트림 래퍼.

    torch.cuda.Stream을 감싸며, 미설치 시 시뮬레이션.

    Attributes:
        _stream_id: 스트림 식별자
        _cuda_stream: torch.cuda.Stream 객체 (None=시뮬레이션)
        _status: 현재 상태
        _start_time: 실행 시작 시각 (perf_counter)
        _profile: 성능 프로파일
        _is_simulation: 시뮬레이션 모드
    """

    __slots__ = (
        "_stream_id",
        "_cuda_stream",
        "_status",
        "_start_time",
        "_profile",
        "_is_simulation",
    )

    def __init__(self, stream_id: StreamID) -> None:
        self._stream_id: StreamID = stream_id
        self._cuda_stream: Any = None
        self._status: StreamStatus = StreamStatus.IDLE
        self._start_time: float = 0.0
        self._profile: StreamProfile = StreamProfile()
        self._is_simulation: bool = True

        # torch.cuda 스트림 생성 시도
        try:
            import torch
            if torch.cuda.is_available():
                self._cuda_stream = torch.cuda.Stream()
                self._is_simulation = False
        except ImportError:
            pass

    @property
    def status(self) -> StreamStatus:
        """현재 스트림 상태."""
        return self._status

    @property
    def profile(self) -> StreamProfile:
        """성능 프로파일."""
        return self._profile

    @property
    def cuda_stream(self) -> Any:
        """내부 torch.cuda.Stream 객체 (시뮬레이션 시 None)."""
        return self._cuda_stream

    @property
    def is_simulation(self) -> bool:
        """시뮬레이션 모드 여부."""
        return self._is_simulation

    def begin(self) -> bool:
        """
        스트림 실행 시작.

        Returns:
            True = 실행 시작, False = 이미 실행 중
        """
        if self._status == StreamStatus.RUNNING:
            return False
        self._status = StreamStatus.RUNNING
        self._start_time = time.perf_counter()
        return True

    def end(self) -> float:
        """
        스트림 실행 종료.

        Returns:
            실행 시간 (ms), 실행 중이 아니면 0.0
        """
        if self._status != StreamStatus.RUNNING:
            return 0.0

        elapsed_ms = (time.perf_counter() - self._start_time) * 1000.0
        self._profile.record(elapsed_ms)
        self._status = StreamStatus.IDLE
        return elapsed_ms

    def synchronize(self) -> None:
        """스트림 동기화 (GPU 작업 완료 대기)."""
        if self._cuda_stream is not None:
            self._status = StreamStatus.SYNCHRONIZING
            try:
                self._cuda_stream.synchronize()
            except Exception:
                pass
        self._status = StreamStatus.IDLE


# =============================================================================
# CUDA 스트림 관리자
# =============================================================================
class CUDAStreamManager:
    """
    CUDA 스트림 중앙 관리자.

    Stage1/Stage2 두 스트림을 독립적으로 관리합니다.
    S1 실행 중 S2 시작 가능 (같은 StreamID 중복만 차단).

    Attributes:
        _config: GPU 설정
        _streams: StreamID → _StreamWrapper 매핑
        _lock: 스레드 안전 잠금
        _initialized: 초기화 완료 여부
    """

    __slots__ = ("_config", "_streams", "_lock", "_initialized")

    def __init__(self, config: GPUConfig | None = None) -> None:
        self._config: GPUConfig = config or GPUConfig()
        self._streams: dict[StreamID, _StreamWrapper] = {}
        self._lock: RLock = RLock()
        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================
    def initialize(self) -> None:
        """StreamID별 스트림 생성."""
        with self._lock:
            if self._initialized:
                return
            for sid in StreamID:
                self._streams[sid] = _StreamWrapper(sid)
            self._initialized = True

            sim = self._streams[StreamID.STAGE1].is_simulation
            logger.info(
                "CUDA 스트림 초기화: %d개 (시뮬레이션=%s)",
                len(self._streams), sim,
            )

    def shutdown(self) -> None:
        """스트림 종료."""
        with self._lock:
            for wrapper in self._streams.values():
                wrapper.synchronize()
            self._streams.clear()
            self._initialized = False
            logger.info("CUDA 스트림 관리자 종료")

    # =========================================================================
    # 스트림 제어
    # =========================================================================
    def begin_stream(self, stream_id: StreamID) -> bool:
        """
        스트림 실행 시작.

        Args:
            stream_id: 대상 스트림

        Returns:
            True = 시작 성공, False = 이미 실행 중
        """
        with self._lock:
            wrapper = self._streams.get(stream_id)
            if wrapper is None:
                return False
            result = wrapper.begin()
            if result:
                logger.debug("스트림 시작: %s", stream_id.value)
            return result

    def end_stream(self, stream_id: StreamID) -> float:
        """
        스트림 실행 종료.

        Args:
            stream_id: 대상 스트림

        Returns:
            실행 시간 (ms)
        """
        with self._lock:
            wrapper = self._streams.get(stream_id)
            if wrapper is None:
                return 0.0
            elapsed = wrapper.end()
            if elapsed > 0:
                logger.debug(
                    "스트림 종료: %s (%.1fms)", stream_id.value, elapsed,
                )
            return elapsed

    def synchronize_stream(self, stream_id: StreamID) -> None:
        """특정 스트림 동기화."""
        with self._lock:
            wrapper = self._streams.get(stream_id)
            if wrapper is not None:
                wrapper.synchronize()

    def synchronize_all(self) -> None:
        """전체 스트림 동기화."""
        with self._lock:
            for wrapper in self._streams.values():
                wrapper.synchronize()

    # =========================================================================
    # 조회
    # =========================================================================
    def get_stream_status(self, stream_id: StreamID) -> StreamStatus:
        """스트림 상태 조회."""
        wrapper = self._streams.get(stream_id)
        if wrapper is None:
            return StreamStatus.IDLE
        return wrapper.status

    def get_cuda_stream(self, stream_id: StreamID) -> Any:
        """내부 torch.cuda.Stream 객체 반환 (추론 context manager용)."""
        wrapper = self._streams.get(stream_id)
        if wrapper is None:
            return None
        return wrapper.cuda_stream

    def get_profile(self, stream_id: StreamID) -> StreamProfile | None:
        """스트림 프로파일 조회."""
        wrapper = self._streams.get(stream_id)
        if wrapper is None:
            return None
        return wrapper.profile

    @property
    def stage1_avg_ms(self) -> float:
        """Stage1 평균 실행 시간 (ms)."""
        p = self.get_profile(StreamID.STAGE1)
        return p.avg_time_ms if p else 0.0

    @property
    def stage2_avg_ms(self) -> float:
        """Stage2 평균 실행 시간 (ms)."""
        p = self.get_profile(StreamID.STAGE2)
        return p.avg_time_ms if p else 0.0

    def __repr__(self) -> str:
        statuses = {
            sid.value: self.get_stream_status(sid).value
            for sid in StreamID
        }
        return f"CUDAStreamManager(streams={statuses})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "StreamID",
    "StreamStatus",
    "StreamProfile",
    "CUDAStreamManager",
]

__version__ = "1.0.0"
