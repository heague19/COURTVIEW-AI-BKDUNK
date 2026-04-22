# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/gpu
파일: batch_accumulator.py
설명: 멀티카메라 프레임 배치 누적기
      - 8카메라 CPU큐 동기화 프레임 → GPU 배치 텐서 변환
      - camera_id 정렬 → np.stack → (N, H, W, 3) 배치
      - 중복 camera_id 드롭 (flush 후 재시작)
      - 불완전 배치 강제 반환 (flush)
      - 프레임 드롭 카운터 추적

      데이터 흐름:
        io/frame_ingestion → CPU큐 (동기화된 N프레임)
            → batch_accumulator → (N, H, W, 3) numpy 배치
                → frame_pipeline에서 GPU 추론

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CameraConfig, GPUConfig

소비자:
    - engine/pipeline/frame_pipeline.py: 배치 수신 + 추론
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass
from threading import RLock
from typing import Final

# =============================================================================
# 서드파티
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CameraConfig, GPUConfig

logger = logging.getLogger(__name__)


# =============================================================================
# 프레임 메타데이터
# =============================================================================
@dataclass(frozen=True, slots=True)
class FrameMeta:
    """
    개별 프레임 메타데이터 (불변).

    Attributes:
        camera_id: 카메라 식별자
        frame_number: 프레임 번호
        timestamp: 타임스탬프 (초, monotonic)
        width: 가로 해상도
        height: 세로 해상도
    """

    camera_id: int
    frame_number: int
    timestamp: float
    width: int
    height: int


# =============================================================================
# 프레임 배치
# =============================================================================
@dataclass(slots=True)
class FrameBatch:
    """
    GPU 추론용 프레임 배치.

    Attributes:
        frames: (N, H, W, 3) uint8 numpy 배열
        metas: 프레임 메타데이터 튜플 (camera_id 순 정렬)
        batch_size: 배치 크기
        created_at: 생성 시각 (monotonic)
        is_complete: 모든 카메라 프레임 포함 여부
    """

    frames: NDArray[np.uint8]
    metas: tuple[FrameMeta, ...]
    batch_size: int
    created_at: float
    is_complete: bool


# =============================================================================
# 상수
# =============================================================================
_MAX_PENDING_FRAMES: Final[int] = 32
_BUILD_TIMEOUT_SEC: Final[float] = 0.5


# =============================================================================
# 배치 누적기
# =============================================================================
class BatchAccumulator:
    """
    멀티카메라 프레임 배치 누적기.

    N대 카메라의 프레임을 수집하여 camera_id 순으로 정렬한 후
    np.stack으로 (N, H, W, 3) 배치를 생성합니다.

    Attributes:
        _camera_config: 카메라 설정
        _gpu_config: GPU 설정
        _pending: 대기 중 프레임 (camera_id → (frame, meta))
        _expected_cameras: 예상 카메라 수
        _lock: 스레드 안전 잠금
        _total_batches: 누적 배치 수
        _total_dropped: 누적 드롭 프레임 수
        _last_batch_time_ms: 마지막 배치 생성 시간 (ms)
        _initialized: 초기화 여부
    """

    __slots__ = (
        "_camera_config",
        "_gpu_config",
        "_pending",
        "_expected_cameras",
        "_lock",
        "_total_batches",
        "_total_dropped",
        "_last_batch_time_ms",
        "_initialized",
    )

    def __init__(
        self,
        camera_config: CameraConfig | None = None,
        gpu_config: GPUConfig | None = None,
    ) -> None:
        self._camera_config: CameraConfig = camera_config or CameraConfig()
        self._gpu_config: GPUConfig = gpu_config or GPUConfig()
        self._pending: dict[int, tuple[NDArray[np.uint8], FrameMeta]] = {}
        self._expected_cameras: int = self._camera_config.num_cameras
        self._lock: RLock = RLock()
        self._total_batches: int = 0
        self._total_dropped: int = 0
        self._last_batch_time_ms: float = 0.0
        self._initialized: bool = True

    # =========================================================================
    # 프레임 추가
    # =========================================================================
    def add_frame(
        self,
        frame: NDArray[np.uint8],
        meta: FrameMeta,
    ) -> FrameBatch | None:
        """
        개별 프레임 추가.

        모든 카메라 프레임이 모이면 FrameBatch 반환.
        중복 camera_id 수신 시 기존 배치 flush + 드롭.

        Args:
            frame: (H, W, 3) uint8 프레임
            meta: 프레임 메타데이터

        Returns:
            FrameBatch (배치 완성 시) 또는 None
        """
        with self._lock:
            # 중복 camera_id → flush + drop
            if meta.camera_id in self._pending:
                logger.warning(
                    "중복 camera_id=%d → 기존 배치 flush+drop",
                    meta.camera_id,
                )
                self._total_dropped += len(self._pending)
                self._pending.clear()

            self._pending[meta.camera_id] = (frame, meta)

            # 배치 완성 확인
            if len(self._pending) >= self._expected_cameras:
                return self._build_batch(is_complete=True)

            return None

    def add_synchronized_frames(
        self,
        frames: list[NDArray[np.uint8]],
        metas: list[FrameMeta],
    ) -> FrameBatch | None:
        """
        동기화된 프레임 세트 일괄 추가.

        Args:
            frames: N개 (H, W, 3) 프레임 리스트
            metas: N개 메타데이터 리스트

        Returns:
            FrameBatch 또는 None (길이 불일치)
        """
        if len(frames) != len(metas):
            logger.error(
                "프레임/메타 길이 불일치: %d vs %d",
                len(frames), len(metas),
            )
            return None

        with self._lock:
            self._pending.clear()
            for frame, meta in zip(frames, metas):
                self._pending[meta.camera_id] = (frame, meta)

            is_complete = len(self._pending) >= self._expected_cameras
            return self._build_batch(is_complete=is_complete)

    # =========================================================================
    # 배치 생성
    # =========================================================================
    def _build_batch(self, is_complete: bool) -> FrameBatch:
        """
        대기 프레임으로 FrameBatch 생성.

        camera_id 오름차순 정렬 → np.stack.
        """
        t0 = time.perf_counter()

        # camera_id 순 정렬
        sorted_ids = sorted(self._pending.keys())
        sorted_frames = []
        sorted_metas = []

        for cam_id in sorted_ids:
            frame, meta = self._pending[cam_id]
            sorted_frames.append(frame)
            sorted_metas.append(meta)

        # np.stack → (N, H, W, 3)
        stacked = np.stack(sorted_frames, axis=0)

        batch = FrameBatch(
            frames=stacked,
            metas=tuple(sorted_metas),
            batch_size=len(sorted_frames),
            created_at=time.monotonic(),
            is_complete=is_complete,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._last_batch_time_ms = elapsed_ms
        self._total_batches += 1
        self._pending.clear()

        logger.debug(
            "배치 생성: %d프레임 (%.1fms, complete=%s)",
            batch.batch_size, elapsed_ms, is_complete,
        )
        return batch

    # =========================================================================
    # Flush (불완전 배치 강제 반환)
    # =========================================================================
    def flush(self) -> FrameBatch | None:
        """
        불완전 배치 강제 반환 (드롭 프레임 상황).

        Returns:
            FrameBatch (대기 프레임 있을 시) 또는 None
        """
        with self._lock:
            if not self._pending:
                return None
            return self._build_batch(is_complete=False)

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def pending_count(self) -> int:
        """대기 중 프레임 수."""
        return len(self._pending)

    @property
    def total_batches(self) -> int:
        """누적 배치 수."""
        return self._total_batches

    @property
    def total_dropped(self) -> int:
        """누적 드롭 프레임 수."""
        return self._total_dropped

    @property
    def last_batch_time_ms(self) -> float:
        """마지막 배치 생성 시간 (ms)."""
        return self._last_batch_time_ms

    # =========================================================================
    # 초기화
    # =========================================================================
    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._pending.clear()
            self._total_batches = 0
            self._total_dropped = 0
            self._last_batch_time_ms = 0.0

    def __repr__(self) -> str:
        return (
            f"BatchAccumulator(pending={self.pending_count}, "
            f"batches={self._total_batches}, "
            f"dropped={self._total_dropped})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "FrameMeta",
    "FrameBatch",
    "BatchAccumulator",
]

__version__ = "1.0.0"
