# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: frame_aligner.py
설명: 멀티카메라 프레임 정렬
      - FrameAligner: 다중 카메라 프레임을 타임스탬프 기준으로 정렬
      - AlignedFrameSet: 정렬된 프레임 그룹 (같은 시점의 다중 뷰)
      - AlignmentConfig: 정렬 설정 (허용 오차, 보간 전략)
      - AlignmentStats: 정렬 통계

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.camera_constants import (
    HARDWARE_SYNC_JITTER_MS,
    MAX_CAMERAS,
    SOFTWARE_SYNC_JITTER_MS,
    SYNC_TOLERANCE_MS,
)
from shared.dto.video_dto import (
    FrameData,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 정렬 버퍼 크기 (카메라당)
MAX_ALIGNMENT_BUFFER: Final[int] = 120



# =============================================================================
# AlignmentConfig: 정렬 설정
# =============================================================================

@dataclass(slots=True)
class AlignmentConfig:
    """프레임 정렬 설정.

    Attributes:
        tolerance_ms: 정렬 허용 오차 (ms)
        use_hardware_sync: 하드웨어 동기화 사용 여부
        min_cameras_required: 정렬에 필요한 최소 카메라 수
        drop_incomplete: 불완전한 세트 삭제 여부
    """

    tolerance_ms: float = SYNC_TOLERANCE_MS
    use_hardware_sync: bool = False
    min_cameras_required: int = 2
    drop_incomplete: bool = False

    def __post_init__(self) -> None:
        # 하드웨어 동기화 시 더 엄격한 허용 오차
        if self.use_hardware_sync:
            self.tolerance_ms = min(
                self.tolerance_ms, HARDWARE_SYNC_JITTER_MS * 2.0
            )
        else:
            self.tolerance_ms = max(
                self.tolerance_ms, SOFTWARE_SYNC_JITTER_MS
            )

        self.min_cameras_required = max(1, min(self.min_cameras_required, MAX_CAMERAS))

    def __repr__(self) -> str:
        sync_type = "HW" if self.use_hardware_sync else "SW"
        return (
            f"AlignmentConfig(tol={self.tolerance_ms:.1f}ms, "
            f"sync={sync_type}, "
            f"min_cams={self.min_cameras_required})"
        )


# =============================================================================
# AlignedFrameSet: 정렬된 프레임 그룹
# =============================================================================

@dataclass(slots=True)
class AlignedFrameSet:
    """같은 시점의 다중 뷰 프레임 그룹.

    Attributes:
        reference_timestamp: 기준 타임스탬프 (초)
        frames: 카메라 ID → FrameData 매핑
        max_drift_ms: 최대 시간 편차 (ms)
        frame_index: 정렬 세트 인덱스
    """

    reference_timestamp: float = 0.0
    frames: dict[str, FrameData] = field(default_factory=dict)
    max_drift_ms: float = 0.0
    frame_index: int = 0

    @property
    def camera_count(self) -> int:
        """포함된 카메라 수."""
        return len(self.frames)

    @property
    def camera_ids(self) -> list[str]:
        """포함된 카메라 ID 목록."""
        return list(self.frames.keys())

    @property
    def is_complete(self) -> bool:
        """모든 프레임이 유효한지."""
        return all(f.is_valid for f in self.frames.values())

    def get_frame(self, camera_id: str) -> FrameData | None:
        """카메라별 프레임 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            FrameData 또는 None
        """
        return self.frames.get(camera_id)

    def __repr__(self) -> str:
        return (
            f"AlignedFrameSet(ts={self.reference_timestamp:.3f}s, "
            f"cameras={self.camera_count}, "
            f"drift={self.max_drift_ms:.1f}ms)"
        )


# =============================================================================
# AlignmentStats: 정렬 통계
# =============================================================================

@dataclass(slots=True)
class AlignmentStats:
    """정렬 통계.

    Attributes:
        sets_created: 생성된 정렬 세트 수
        frames_aligned: 정렬된 총 프레임 수
        frames_dropped: 드롭된 프레임 수
        avg_drift_ms: 평균 시간 편차 (ms)
        max_drift_ms: 최대 시간 편차 (ms)
    """

    sets_created: int = 0
    frames_aligned: int = 0
    frames_dropped: int = 0
    avg_drift_ms: float = 0.0
    max_drift_ms: float = 0.0

    @property
    def alignment_rate(self) -> float:
        """정렬 성공률."""
        total = self.frames_aligned + self.frames_dropped
        if total == 0:
            return 0.0
        return self.frames_aligned / total

    def __repr__(self) -> str:
        return (
            f"AlignmentStats(sets={self.sets_created}, "
            f"aligned={self.frames_aligned}, "
            f"dropped={self.frames_dropped}, "
            f"avg_drift={self.avg_drift_ms:.1f}ms)"
        )


# =============================================================================
# FrameAligner: 멀티카메라 프레임 정렬
# =============================================================================

class FrameAligner:
    """다중 카메라 프레임 타임스탬프 기반 정렬.

    각 카메라에서 도착하는 프레임을 버퍼에 쌓고,
    tolerance 내 가장 가까운 타임스탬프끼리 그룹화.

    사용 예시::

        config = AlignmentConfig(tolerance_ms=33.33)
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2", "cam_3"], config)

        aligner.add_frame("cam_0", frame_0)
        aligner.add_frame("cam_1", frame_1)
        aligned = aligner.try_align()  # AlignedFrameSet 또는 None
    """

    __slots__ = (
        "_lock",
        "_config",
        "_camera_ids",
        "_buffers",
        "_stats",
        "_set_counter",
        "_drift_sum",
        "_drift_count",
    )

    def __init__(
        self,
        camera_ids: list[str],
        config: AlignmentConfig | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._config = config or AlignmentConfig()
        self._camera_ids = list(camera_ids[:MAX_CAMERAS])
        self._buffers: dict[str, list[FrameData]] = {
            cid: [] for cid in self._camera_ids
        }
        self._stats = AlignmentStats()
        self._set_counter: int = 0
        self._drift_sum: float = 0.0
        self._drift_count: int = 0

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def config(self) -> AlignmentConfig:
        """정렬 설정."""
        return self._config

    @property
    def camera_ids(self) -> list[str]:
        """등록된 카메라 ID 목록."""
        return list(self._camera_ids)

    @property
    def camera_count(self) -> int:
        """등록된 카메라 수."""
        return len(self._camera_ids)

    @property
    def stats(self) -> AlignmentStats:
        """통계 (방어적 복사)."""
        with self._lock:
            return AlignmentStats(
                sets_created=self._stats.sets_created,
                frames_aligned=self._stats.frames_aligned,
                frames_dropped=self._stats.frames_dropped,
                avg_drift_ms=self._stats.avg_drift_ms,
                max_drift_ms=self._stats.max_drift_ms,
            )

    @property
    def buffer_sizes(self) -> dict[str, int]:
        """카메라별 버퍼 크기."""
        with self._lock:
            return {cid: len(buf) for cid, buf in self._buffers.items()}

    # =========================================================================
    # 프레임 추가
    # =========================================================================

    def add_frame(self, camera_id: str, frame: FrameData) -> bool:
        """카메라 프레임 추가.

        Args:
            camera_id: 카메라 ID
            frame: FrameData

        Returns:
            추가 성공 여부
        """
        with self._lock:
            if camera_id not in self._buffers:
                return False

            buf = self._buffers[camera_id]

            # 버퍼 크기 제한
            if len(buf) >= MAX_ALIGNMENT_BUFFER:
                # 가장 오래된 프레임 드롭
                buf.pop(0)
                self._stats.frames_dropped += 1

            buf.append(frame)
            return True

    # =========================================================================
    # 정렬
    # =========================================================================

    def try_align(self) -> AlignedFrameSet | None:
        """정렬 세트 생성 시도.

        모든 카메라 버퍼에 프레임이 존재하면,
        타임스탬프가 가장 가까운 프레임들을 그룹화.

        Returns:
            AlignedFrameSet 또는 None (정렬 불가)
        """
        with self._lock:
            # 최소 카메라 수 체크
            non_empty = sum(1 for buf in self._buffers.values() if buf)
            if non_empty < self._config.min_cameras_required:
                return None

            # 기준 타임스탬프 = 첫 번째 비어있지 않은 버퍼의 가장 오래된 프레임
            ref_timestamp: float | None = None
            for buf in self._buffers.values():
                if buf:
                    if ref_timestamp is None:
                        ref_timestamp = buf[0].timestamp
                    break

            if ref_timestamp is None:
                return None

            tolerance_sec = self._config.tolerance_ms / 1000.0
            aligned_frames: dict[str, FrameData] = {}
            max_drift = 0.0

            for cid in self._camera_ids:
                buf = self._buffers[cid]
                if not buf:
                    continue

                # tolerance 내 가장 가까운 프레임 찾기
                best_frame: FrameData | None = None
                best_diff = float("inf")
                best_idx = -1

                for i, f in enumerate(buf):
                    diff = abs(f.timestamp - ref_timestamp)
                    if diff < best_diff:
                        best_diff = diff
                        best_frame = f
                        best_idx = i

                if best_frame is not None and best_diff <= tolerance_sec:
                    aligned_frames[cid] = best_frame
                    drift_ms = best_diff * 1000.0
                    max_drift = max(max_drift, drift_ms)

                    # 사용된 프레임까지 버퍼에서 제거
                    self._buffers[cid] = buf[best_idx + 1:]

            # 최소 카메라 수 체크
            if len(aligned_frames) < self._config.min_cameras_required:
                return None

            # 불완전 세트 드롭
            if (
                self._config.drop_incomplete
                and len(aligned_frames) < len(self._camera_ids)
            ):
                self._stats.frames_dropped += len(aligned_frames)
                return None

            # 통계 갱신
            self._set_counter += 1
            self._stats.sets_created += 1
            self._stats.frames_aligned += len(aligned_frames)
            self._drift_sum += max_drift
            self._drift_count += 1
            self._stats.max_drift_ms = max(self._stats.max_drift_ms, max_drift)
            if self._drift_count > 0:
                self._stats.avg_drift_ms = self._drift_sum / self._drift_count

            return AlignedFrameSet(
                reference_timestamp=ref_timestamp,
                frames=aligned_frames,
                max_drift_ms=max_drift,
                frame_index=self._set_counter,
            )

    def align_batch(self, max_sets: int = 10) -> list[AlignedFrameSet]:
        """여러 정렬 세트 일괄 생성.

        Args:
            max_sets: 최대 생성 세트 수

        Returns:
            AlignedFrameSet 리스트
        """
        results: list[AlignedFrameSet] = []
        for _ in range(max_sets):
            aligned = self.try_align()
            if aligned is None:
                break
            results.append(aligned)
        return results

    # =========================================================================
    # 관리
    # =========================================================================

    def clear(self) -> int:
        """모든 버퍼 클리어.

        Returns:
            드롭된 프레임 수
        """
        with self._lock:
            total = sum(len(buf) for buf in self._buffers.values())
            for buf in self._buffers.values():
                buf.clear()
            self._stats.frames_dropped += total
            return total

    def clear_camera(self, camera_id: str) -> int:
        """특정 카메라 버퍼 클리어.

        Args:
            camera_id: 카메라 ID

        Returns:
            드롭된 프레임 수
        """
        with self._lock:
            if camera_id not in self._buffers:
                return 0
            count = len(self._buffers[camera_id])
            self._buffers[camera_id].clear()
            self._stats.frames_dropped += count
            return count

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = AlignmentStats()
            self._drift_sum = 0.0
            self._drift_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"FrameAligner(cameras={len(self._camera_ids)}, "
                f"tol={self._config.tolerance_ms:.1f}ms, "
                f"sets={self._stats.sets_created})"
            )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "FrameAligner",
    # 데이터 클래스
    "AlignmentConfig",
    "AlignedFrameSet",
    "AlignmentStats",
    # 상수
    "MAX_ALIGNMENT_BUFFER",
]

__version__ = "1.0.0"
