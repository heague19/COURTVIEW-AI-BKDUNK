# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/preprocessing
파일: multi_video_sync.py
설명: 다중 영상 동기화
      - MultiVideoSync: 다중 비디오 파일의 동기화 디코딩
      - SyncSession: 동기화 세션 관리
      - SyncStats: 동기화 통계
      - HW 동기화 (±1ms Genlock), SW 동기화 (±10ms 타임스탬프)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from typing import Final, Generator

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.camera_constants import (
    MAX_CAMERAS,
    SYNC_TOLERANCE_MS,
)
from shared.dto.video_dto import (
    FrameData,
)

from infrastructure.preprocessing.video_decoder import VideoDecoder
from infrastructure.preprocessing.frame_aligner import (
    AlignedFrameSet,
    AlignmentConfig,
    FrameAligner,
)


# =============================================================================
# 상수 정의
# =============================================================================



# =============================================================================
# SyncStats: 동기화 통계
# =============================================================================

@dataclass(slots=True)
class SyncStats:
    """동기화 통계.

    Attributes:
        total_sets: 생성된 정렬 세트 수
        total_frames: 디코딩된 총 프레임 수
        dropped_frames: 드롭된 프레임 수
        drift_corrections: 드리프트 보정 횟수
        avg_sync_drift_ms: 평균 동기화 편차 (ms)
        max_sync_drift_ms: 최대 동기화 편차 (ms)
        sync_time_sec: 동기화 소요 시간
    """

    total_sets: int = 0
    total_frames: int = 0
    dropped_frames: int = 0
    drift_corrections: int = 0
    avg_sync_drift_ms: float = 0.0
    max_sync_drift_ms: float = 0.0
    sync_time_sec: float = 0.0

    @property
    def sync_rate(self) -> float:
        """동기화 성공률."""
        total = self.total_frames + self.dropped_frames
        if total == 0:
            return 0.0
        return self.total_frames / total

    def __repr__(self) -> str:
        return (
            f"SyncStats(sets={self.total_sets}, "
            f"frames={self.total_frames}, "
            f"dropped={self.dropped_frames}, "
            f"drift={self.avg_sync_drift_ms:.1f}ms)"
        )


# =============================================================================
# SyncSession: 동기화 세션
# =============================================================================

@dataclass(slots=True)
class SyncSession:
    """동기화 세션 정보.

    Attributes:
        session_id: 세션 ID
        camera_files: 카메라 ID → 파일 경로 매핑
        use_hardware_sync: 하드웨어 동기화 사용 여부
        offsets_ms: 카메라별 시간 오프셋 (ms)
    """

    session_id: str = ""
    camera_files: dict[str, str] = field(default_factory=dict)
    use_hardware_sync: bool = False
    offsets_ms: dict[str, float] = field(default_factory=dict)

    @property
    def camera_count(self) -> int:
        """카메라 수."""
        return len(self.camera_files)

    @property
    def camera_ids(self) -> list[str]:
        """카메라 ID 목록."""
        return list(self.camera_files.keys())

    def __repr__(self) -> str:
        sync_type = "HW" if self.use_hardware_sync else "SW"
        return (
            f"SyncSession(id='{self.session_id}', "
            f"cameras={self.camera_count}, "
            f"sync={sync_type})"
        )


# =============================================================================
# MultiVideoSync: 다중 영상 동기화
# =============================================================================

class MultiVideoSync:
    """다중 비디오 파일 동기화 디코딩.

    여러 카메라 영상을 동시에 디코딩하고,
    타임스탬프 기반 프레임 정렬을 수행.

    사용 예시::

        sync = MultiVideoSync()
        session = SyncSession(
            session_id="game_001",
            camera_files={
                "cam_0": "cam0.mp4",
                "cam_1": "cam1.mp4",
            },
        )
        for aligned_set in sync.sync_decode(session, max_sets=100):
            process(aligned_set)
    """

    __slots__ = (
        "_lock",
        "_decoders",
        "_aligner",
        "_stats",
        "_active",
    )

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._decoders: dict[str, VideoDecoder] = {}
        self._aligner: FrameAligner | None = None
        self._stats = SyncStats()
        self._active: bool = False

    # =========================================================================
    # 프로퍼티
    # =========================================================================

    @property
    def is_active(self) -> bool:
        """활성 상태 여부."""
        with self._lock:
            return self._active

    @property
    def stats(self) -> SyncStats:
        """통계 (방어적 복사)."""
        with self._lock:
            return SyncStats(
                total_sets=self._stats.total_sets,
                total_frames=self._stats.total_frames,
                dropped_frames=self._stats.dropped_frames,
                drift_corrections=self._stats.drift_corrections,
                avg_sync_drift_ms=self._stats.avg_sync_drift_ms,
                max_sync_drift_ms=self._stats.max_sync_drift_ms,
                sync_time_sec=self._stats.sync_time_sec,
            )

    @property
    def camera_count(self) -> int:
        """활성 디코더 수."""
        with self._lock:
            return len(self._decoders)

    # =========================================================================
    # 동기화 디코딩
    # =========================================================================

    def sync_decode(
        self,
        session: SyncSession,
        max_sets: int | None = None,
    ) -> Generator[AlignedFrameSet, None, None]:
        """동기화 디코딩 제너레이터.

        Args:
            session: 동기화 세션
            max_sets: 최대 정렬 세트 수

        Yields:
            AlignedFrameSet
        """
        if session.camera_count == 0:
            return

        if session.camera_count > MAX_CAMERAS:
            return

        t0 = time.monotonic()

        # 디코더 초기화
        if not self._initialize_decoders(session):
            return

        try:
            with self._lock:
                self._active = True

            set_count = 0
            drift_sum = 0.0
            drift_count = 0

            while True:
                if max_sets is not None and set_count >= max_sets:
                    break

                # 각 카메라에서 프레임 디코딩 + 정렬기에 추가
                any_frame = False
                for cid, decoder in self._decoders.items():
                    frame_data = decoder.decode_next()
                    if frame_data is not None:
                        # 오프셋 적용
                        offset_sec = session.offsets_ms.get(cid, 0.0) / 1000.0
                        adjusted = FrameData(
                            image=frame_data.image,
                            index=frame_data.index,
                            timestamp=frame_data.timestamp + offset_sec,
                            status=frame_data.status,
                            camera_id=cid,
                        )
                        self._aligner.add_frame(cid, adjusted)
                        any_frame = True

                        with self._lock:
                            self._stats.total_frames += 1

                if not any_frame:
                    # 모든 디코더 EOF → 남은 버퍼 정렬 시도
                    remaining = self._aligner.align_batch(max_sets=100)
                    for aligned in remaining:
                        set_count += 1
                        with self._lock:
                            self._stats.total_sets += 1
                        yield aligned
                    break

                # 정렬 시도
                aligned = self._aligner.try_align()
                if aligned is not None:
                    set_count += 1
                    drift_sum += aligned.max_drift_ms
                    drift_count += 1

                    with self._lock:
                        self._stats.total_sets += 1
                        self._stats.max_sync_drift_ms = max(
                            self._stats.max_sync_drift_ms, aligned.max_drift_ms
                        )
                        if drift_count > 0:
                            self._stats.avg_sync_drift_ms = drift_sum / drift_count

                    yield aligned

        finally:
            self._cleanup()
            with self._lock:
                self._stats.sync_time_sec = time.monotonic() - t0
                self._active = False

    # =========================================================================
    # 단일 세트 동기화
    # =========================================================================

    def sync_single(
        self,
        session: SyncSession,
        frame_index: int,
    ) -> AlignedFrameSet | None:
        """특정 프레임 인덱스의 동기화 세트 생성.

        Args:
            session: 동기화 세션
            frame_index: 대상 프레임 인덱스

        Returns:
            AlignedFrameSet 또는 None
        """
        if session.camera_count == 0:
            return None

        if not self._initialize_decoders(session):
            return None

        try:
            frames: dict[str, FrameData] = {}
            max_drift = 0.0

            for cid, decoder in self._decoders.items():
                offset_sec = session.offsets_ms.get(cid, 0.0) / 1000.0
                # 오프셋을 고려한 프레임 인덱스 계산
                offset_frames = int(offset_sec * decoder.fps)
                target_idx = frame_index + offset_frames

                frame_data = decoder.decode_frame(max(0, target_idx))
                if frame_data is not None:
                    frames[cid] = FrameData(
                        image=frame_data.image,
                        index=frame_data.index,
                        timestamp=frame_data.timestamp + offset_sec,
                        status=frame_data.status,
                        camera_id=cid,
                    )

            if not frames:
                return None

            # 기준 타임스탬프 = 첫 프레임
            ref_ts = next(iter(frames.values())).timestamp
            for f in frames.values():
                drift = abs(f.timestamp - ref_ts) * 1000.0
                max_drift = max(max_drift, drift)

            return AlignedFrameSet(
                reference_timestamp=ref_ts,
                frames=frames,
                max_drift_ms=max_drift,
                frame_index=frame_index,
            )

        finally:
            self._cleanup()

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _initialize_decoders(self, session: SyncSession) -> bool:
        """세션의 모든 디코더 초기화.

        Args:
            session: 동기화 세션

        Returns:
            전체 성공 여부
        """
        self._cleanup()

        decoders: dict[str, VideoDecoder] = {}
        alignment_config = AlignmentConfig(
            use_hardware_sync=session.use_hardware_sync,
            min_cameras_required=min(2, session.camera_count),
        )

        for cid, file_path in session.camera_files.items():
            decoder = VideoDecoder(camera_id=cid)
            if not decoder.open(file_path):
                # 실패 시 이미 열린 디코더 정리
                for d in decoders.values():
                    d.close()
                return False
            decoders[cid] = decoder

        with self._lock:
            self._decoders = decoders
            self._aligner = FrameAligner(
                list(decoders.keys()), alignment_config
            )
            self._stats = SyncStats()

        return True

    def _cleanup(self) -> None:
        """디코더 정리."""
        with self._lock:
            for decoder in self._decoders.values():
                decoder.close()
            self._decoders.clear()
            self._aligner = None

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MultiVideoSync(decoders={len(self._decoders)}, "
                f"active={self._active})"
            )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 핵심 클래스
    "MultiVideoSync",
    # 데이터 클래스
    "SyncSession",
    "SyncStats",
]

__version__ = "1.0.0"
