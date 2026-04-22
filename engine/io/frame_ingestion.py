# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/io
파일: frame_ingestion.py
설명: 멀티카메라 프레임 수집 + 동기화 + 전처리 연동
      - 8대 ASECAM RTSP 카메라 프레임 캡처
      - infrastructure/preprocessing 3개 모듈 실제 연동:
        1. VideoDecoder: RTSP/파일 디코딩 → FrameData
        2. FrameNormalizer: 해상도/색공간 정규화 (1920×1080 BGR)
        3. FrameAligner: 타임스탬프 기반 동기화 (tolerance 1ms)
      - 듀얼 스트림 (community_49 ASECAM 지시):
        - 분석용: 서브 스트림 1080p → GPU 파이프라인
        - 녹화용: 메인 스트림 4K → 콜백 위임 (SSD 직접 저장)
      - LIVE/BATCH 모드 분기:
        - LIVE: capture_and_align() — 단일 프레임 캡처 + 정렬
        - BATCH: decode_all() — 파일 전체 디코딩 + 정렬

      데이터 흐름:
        8cam RTSP → VideoDecoder.decode_next() → FrameData
            → FrameNormalizer.normalize() → FrameData(1920×1080)
            → FrameAligner.add_frame() → .try_align() → AlignedFrameSet
            → (소비자) gpu/batch_accumulator → GPU 추론

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: CameraConfig, EngineMode
    - shared/dto/video_dto.py: FrameData
    - infrastructure/preprocessing/video_decoder.py: VideoDecoder, DecoderState
    - infrastructure/preprocessing/video_normalizer.py: FrameNormalizer, NormalizationConfig
    - infrastructure/preprocessing/frame_aligner.py: FrameAligner, AlignmentConfig, AlignedFrameSet

소비자:
    - engine/pipeline/frame_pipeline.py: AlignedFrameSet 수신 → 추론
    - engine/gpu/batch_accumulator.py: AlignedFrameSet → FrameBatch 변환
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Callable, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CameraConfig

from infrastructure.preprocessing.frame_aligner import (
    AlignedFrameSet,
    AlignmentConfig,
    FrameAligner,
)
from infrastructure.preprocessing.video_decoder import (
    VideoDecoder,
)
from infrastructure.preprocessing.video_normalizer import (
    FrameNormalizer,
    NormalizationConfig,
)
from shared.dto.video_dto import FrameData

logger = logging.getLogger(__name__)


# =============================================================================
# 입력 소스 열거형
# =============================================================================
@unique
class IngestionSource(str, Enum):
    """
    프레임 입력 소스 열거형 (3종).

    Attributes:
        CAMERA: 실시간 카메라 (RTSP)
        FILE: 비디오 파일 (배치 분석)
        RTSP: RTSP 스트림 (CAMERA와 동일, 명시적 구분)
    """

    CAMERA = "camera"
    FILE = "file"
    RTSP = "rtsp"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 수집 통계
# =============================================================================
@dataclass(slots=True)
class IngestionStats:
    """
    프레임 수집 통계.

    Attributes:
        total_captured: 총 캡처 프레임 수
        total_normalized: 정규화 완료 프레임 수
        total_aligned_sets: 동기화 완료 세트 수
        total_dropped: 드롭 프레임 수
        total_recording_frames: 녹화 프레임 수
        total_decode_errors: 디코딩 에러 수
        total_normalize_errors: 정규화 에러 수
    """

    total_captured: int = 0
    total_normalized: int = 0
    total_aligned_sets: int = 0
    total_dropped: int = 0
    total_recording_frames: int = 0
    total_decode_errors: int = 0
    total_normalize_errors: int = 0


# =============================================================================
# 상수
# =============================================================================
# 카메라 버퍼 최대 크기 (오래된 프레임 자동 폐기)
_MAX_BUFFER_PER_CAMERA: Final[int] = 10

# 녹화 콜백 최대 등록 수
_MAX_RECORDING_CALLBACKS: Final[int] = 10

# 녹화 콜백 타입: (카메라ID, 4K 프레임, 타임스탬프) → None
RecordingCallback = Callable[[str, NDArray[np.uint8], float], None]


# =============================================================================
# 프레임 수집기
# =============================================================================
class FrameIngestion:
    """
    멀티카메라 프레임 수집 + 동기화 + 전처리 연동.

    8대 ASECAM 카메라에서 RTSP로 프레임을 수신하고,
    infrastructure/preprocessing 3개 모듈을 거쳐 동기화된 AlignedFrameSet을 생성합니다.

    Attributes:
        _config: 카메라 설정
        _lock: 스레드 안전 잠금
        _camera_ids: 카메라 ID 목록
        _decoders: 카메라별 분석용 디코더
        _recording_decoders: 카메라별 녹화용 디코더
        _normalizer: 해상도 정규화기
        _aligner: 타임스탬프 정렬기
        _recording_callbacks: 녹화 콜백 목록
        _stats: 수집 통계
        _initialized: 초기화 완료 여부
        _frame_counter: 글로벌 프레임 카운터
    """

    __slots__ = (
        "_config",
        "_lock",
        "_camera_ids",
        "_decoders",
        "_recording_decoders",
        "_normalizer",
        "_aligner",
        "_recording_callbacks",
        "_stats",
        "_initialized",
        "_frame_counter",
    )

    def __init__(self, config: CameraConfig | None = None) -> None:
        self._config: CameraConfig = config or CameraConfig()
        self._lock: RLock = RLock()
        self._camera_ids: list[str] = [
            f"cam_{i}" for i in range(self._config.num_cameras)
        ]
        self._decoders: dict[str, VideoDecoder] = {}
        self._recording_decoders: dict[str, VideoDecoder] = {}
        self._normalizer: FrameNormalizer | None = None
        self._aligner: FrameAligner | None = None
        self._recording_callbacks: list[RecordingCallback] = []
        self._stats: IngestionStats = IngestionStats()
        self._initialized: bool = False
        self._frame_counter: int = 0

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================
    def initialize(self, source_urls: dict[str, str] | None = None) -> None:
        """
        프레임 수집기 초기화.

        카메라별 VideoDecoder 생성, FrameNormalizer 생성, FrameAligner 생성.

        Args:
            source_urls: 카메라ID → RTSP/파일 URL 매핑 (None이면 오프라인 모드)
        """
        with self._lock:
            if self._initialized:
                return

            # 1. 카메라별 분석용 디코더 생성 — 병렬 open (Phase 17 S1)
            from concurrent.futures import ThreadPoolExecutor

            def _open_analysis(cam_id: str) -> tuple[str, VideoDecoder, bool]:
                decoder = VideoDecoder()
                opened = False
                if source_urls and cam_id in source_urls:
                    opened = decoder.open(source_urls[cam_id])
                    if not opened:
                        logger.warning(
                            "카메라 %s 열기 실패: %s",
                            cam_id, source_urls.get(cam_id),
                        )
                return cam_id, decoder, opened

            cam_ids_list = list(self._camera_ids)
            if cam_ids_list:
                workers = min(len(cam_ids_list), 16)
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fi-init") as pool:
                    results = list(pool.map(_open_analysis, cam_ids_list))
                for cam_id, decoder, _opened in results:
                    self._decoders[cam_id] = decoder

            # 2. 녹화용 디코더 생성 (듀얼 스트림) — 병렬 open
            if self._config.recording_enabled and source_urls:
                rec_ids = [
                    cid for cid in self._camera_ids
                    if f"{cid}_recording" in source_urls
                ]
                if rec_ids:
                    def _open_recording(cam_id: str) -> tuple[str, VideoDecoder]:
                        rec_decoder = VideoDecoder()
                        rec_decoder.open(source_urls[f"{cam_id}_recording"])
                        return cam_id, rec_decoder

                    workers = min(len(rec_ids), 16)
                    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fi-rec") as pool:
                        rec_results = list(pool.map(_open_recording, rec_ids))
                    for cam_id, rec_decoder in rec_results:
                        self._recording_decoders[cam_id] = rec_decoder

            # 3. 정규화기: 분석 해상도로 정규화
            norm_config = NormalizationConfig(
                target_width=self._config.analysis_width,
                target_height=self._config.analysis_height,
            )
            self._normalizer = FrameNormalizer(norm_config)

            # 4. 정렬기: 타임스탬프 기반 동기화
            align_config = AlignmentConfig(
                tolerance_ms=self._config.sync_tolerance_ms,
            )
            self._aligner = FrameAligner(self._camera_ids, align_config)

            self._initialized = True
            logger.info(
                "FrameIngestion 초기화 완료: %d 카메라, %dx%d, tolerance=%.1fms",
                self._config.num_cameras,
                self._config.analysis_width,
                self._config.analysis_height,
                self._config.sync_tolerance_ms,
            )

    def shutdown(self) -> None:
        """프레임 수집기 종료. 모든 디코더 닫기."""
        with self._lock:
            for cam_id, decoder in self._decoders.items():
                try:
                    decoder.close()
                except Exception:
                    logger.exception("디코더 종료 실패: %s", cam_id)

            for cam_id, decoder in self._recording_decoders.items():
                try:
                    decoder.close()
                except Exception:
                    logger.exception("녹화 디코더 종료 실패: %s", cam_id)

            self._decoders.clear()
            self._recording_decoders.clear()
            self._normalizer = None
            self._aligner = None
            self._initialized = False
            logger.info("FrameIngestion 종료")

    # =========================================================================
    # LIVE 모드: 단일 사이클 캡처 + 정렬
    # =========================================================================
    def capture_and_align(self) -> AlignedFrameSet | None:
        """
        LIVE 모드: 8cam에서 1프레임씩 캡처 → 정규화 → 정렬.

        Returns:
            AlignedFrameSet (동기화 완료 시) 또는 None (미완료/에러)
        """
        if not self._initialized or self._normalizer is None or self._aligner is None:
            return None

        with self._lock:
            # 각 카메라에서 1프레임 디코딩 + 정규화 + 정렬기 투입
            for cam_id, decoder in self._decoders.items():
                try:
                    frame_data = decoder.decode_next()
                except Exception:
                    logger.exception("디코딩 에러: %s", cam_id)
                    self._stats.total_decode_errors += 1
                    continue

                if frame_data is None or not frame_data.is_valid:
                    self._stats.total_dropped += 1
                    continue

                self._stats.total_captured += 1

                # 정규화 (1920×1080)
                try:
                    normalized = self._normalizer.normalize(frame_data)
                except Exception:
                    logger.exception("정규화 에러: %s", cam_id)
                    self._stats.total_normalize_errors += 1
                    continue

                if not normalized.is_valid:
                    self._stats.total_dropped += 1
                    continue

                self._stats.total_normalized += 1

                # 정렬기에 투입
                self._aligner.add_frame(cam_id, normalized)

            # 정렬 시도
            aligned = self._aligner.try_align()
            if aligned is not None:
                self._stats.total_aligned_sets += 1
                self._frame_counter += 1

            return aligned

    # =========================================================================
    # BATCH 모드: 파일 전체 디코딩 + 정렬
    # =========================================================================
    def decode_all(self) -> list[AlignedFrameSet]:
        """
        BATCH 모드: 모든 디코더에서 전체 프레임 디코딩 → 정렬.

        Returns:
            동기화된 AlignedFrameSet 리스트
        """
        if not self._initialized or self._normalizer is None or self._aligner is None:
            return []

        results: list[AlignedFrameSet] = []

        with self._lock:
            exhausted: set[str] = set()

            while len(exhausted) < len(self._decoders):
                for cam_id, decoder in self._decoders.items():
                    if cam_id in exhausted:
                        continue

                    try:
                        frame_data = decoder.decode_next()
                    except Exception:
                        logger.exception("배치 디코딩 에러: %s", cam_id)
                        self._stats.total_decode_errors += 1
                        exhausted.add(cam_id)
                        continue

                    if frame_data is None:
                        exhausted.add(cam_id)
                        continue

                    if not frame_data.is_valid:
                        self._stats.total_dropped += 1
                        continue

                    self._stats.total_captured += 1

                    # 정규화
                    try:
                        normalized = self._normalizer.normalize(frame_data)
                    except Exception:
                        logger.exception("배치 정규화 에러: %s", cam_id)
                        self._stats.total_normalize_errors += 1
                        continue

                    if not normalized.is_valid:
                        self._stats.total_dropped += 1
                        continue

                    self._stats.total_normalized += 1
                    self._aligner.add_frame(cam_id, normalized)

                # 정렬 시도 (반복)
                while True:
                    aligned = self._aligner.try_align()
                    if aligned is None:
                        break
                    results.append(aligned)
                    self._stats.total_aligned_sets += 1
                    self._frame_counter += 1

        logger.info(
            "배치 디코딩 완료: %d 세트, 캡처=%d, 정규화=%d, 드롭=%d",
            len(results),
            self._stats.total_captured,
            self._stats.total_normalized,
            self._stats.total_dropped,
        )
        return results

    # =========================================================================
    # 듀얼 스트림: 녹화 프레임 캡처
    # =========================================================================
    def capture_recording_frames(self) -> None:
        """
        녹화용 4K 프레임 캡처 → 콜백 위임.

        분석 파이프라인에 투입하지 않고, 등록된 콜백으로만 전달합니다.
        SSD 직접 저장은 콜백 내부에서 처리합니다.
        """
        if not self._config.recording_enabled:
            return

        if not self._recording_callbacks:
            return

        with self._lock:
            for cam_id, decoder in self._recording_decoders.items():
                try:
                    frame_data = decoder.decode_next()
                except Exception:
                    logger.exception("녹화 디코딩 에러: %s", cam_id)
                    continue

                if frame_data is None or not frame_data.is_valid:
                    continue

                self._stats.total_recording_frames += 1

                # 콜백 위임 (try/except 보호)
                for cb in self._recording_callbacks:
                    try:
                        cb(cam_id, frame_data.image, frame_data.timestamp)
                    except Exception:
                        logger.exception("녹화 콜백 에러: %s", cam_id)

    def register_recording_callback(self, callback: RecordingCallback) -> bool:
        """
        녹화 프레임 콜백 등록.

        Args:
            callback: (카메라ID, 4K 프레임, 타임스탬프) → None

        Returns:
            등록 성공 여부 (상한 초과 시 False)
        """
        with self._lock:
            if len(self._recording_callbacks) >= _MAX_RECORDING_CALLBACKS:
                logger.warning("녹화 콜백 상한 초과: %d", _MAX_RECORDING_CALLBACKS)
                return False
            self._recording_callbacks.append(callback)
            return True

    # =========================================================================
    # AlignedFrameSet → 프레임/카메라ID 추출 유틸
    # =========================================================================
    @staticmethod
    def extract_frames(
        aligned: AlignedFrameSet,
    ) -> tuple[list[NDArray[np.uint8]], list[str]]:
        """
        AlignedFrameSet에서 프레임 배열 + 카메라 ID 목록 추출.

        batch_accumulator 연동용. camera_id 순 정렬.

        Args:
            aligned: 동기화된 프레임 세트

        Returns:
            (프레임 리스트, 카메라ID 리스트) — camera_id 오름차순 정렬
        """
        sorted_ids = sorted(aligned.frames.keys())
        frames: list[NDArray[np.uint8]] = []
        cam_ids: list[str] = []

        for cam_id in sorted_ids:
            fd = aligned.frames[cam_id]
            if fd.is_valid:
                frames.append(fd.image)
                cam_ids.append(cam_id)

        return frames, cam_ids

    # =========================================================================
    # 통계 / 프로퍼티
    # =========================================================================
    @property
    def stats(self) -> IngestionStats:
        """수집 통계 (복사본)."""
        with self._lock:
            return IngestionStats(
                total_captured=self._stats.total_captured,
                total_normalized=self._stats.total_normalized,
                total_aligned_sets=self._stats.total_aligned_sets,
                total_dropped=self._stats.total_dropped,
                total_recording_frames=self._stats.total_recording_frames,
                total_decode_errors=self._stats.total_decode_errors,
                total_normalize_errors=self._stats.total_normalize_errors,
            )

    @property
    def frame_counter(self) -> int:
        """글로벌 프레임 카운터."""
        return self._frame_counter

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def camera_ids(self) -> list[str]:
        """카메라 ID 목록."""
        return list(self._camera_ids)

    # =========================================================================
    # 초기화
    # =========================================================================
    def reset(self) -> None:
        """통계 및 카운터 초기화."""
        with self._lock:
            self._stats = IngestionStats()
            self._frame_counter = 0
            logger.info("FrameIngestion 통계 초기화")

    def __repr__(self) -> str:
        return (
            f"FrameIngestion("
            f"cameras={self._config.num_cameras}, "
            f"initialized={self._initialized}, "
            f"aligned={self._stats.total_aligned_sets}, "
            f"dropped={self._stats.total_dropped})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "IngestionSource",
    "IngestionStats",
    "FrameIngestion",
    "RecordingCallback",
]

__version__ = "1.0.0"
