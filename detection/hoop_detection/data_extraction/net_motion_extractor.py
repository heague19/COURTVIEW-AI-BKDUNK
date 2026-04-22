# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection/data_extraction
파일: net_motion_extractor.py
설명: 네트 움직임 시퀀스 추출기
      - 득점 이벤트 전후 네트 ROI 프레임 시퀀스 수집
      - 광학 흐름 변위 벡터 시퀀스 저장
      - 득점 유형 라벨 생성 (swish/rim_in/rim_out)
      - 버퍼 축적 → 자동 flush
      - finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0

의존성:
    - shared/constants/hoop_constants.py: 네트 분석 상수
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - detection/hoop_detection/hoop_detector.py: ScoringType
    - detection/hoop_detection/net_analyzer.py: _ScoringEvent

데이터 흐름:
    NetAnalyzer.analyze() → _ScoringEvent
        ↓
    이벤트 전후 프레임 수집 (pre=10, post=5)
        ↓
    변위 벡터 + 프레임 시퀀스 → NPZ 저장
        ↓
    라벨: scoring_type + confidence + metadata
        ↓
    finalize() → sequences/*.npz + labels/*.json + metadata.json
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.hoop_constants import NET_ANALYSIS_HISTORY_SIZE
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from detection.hoop_detection.hoop_detector import ScoringType
from detection.hoop_detection.net_analyzer import _ScoringEvent

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

# 이벤트 전후 수집 프레임 수
_PRE_EVENT_FRAMES: Final[int] = 10
_POST_EVENT_FRAMES: Final[int] = 5

# 네트 ROI 크롭 크기
_NET_CROP_SIZE: Final[int] = 64

# 버퍼 자동 flush 임계값
_BUFFER_FLUSH_COUNT: Final[int] = 50
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 메모리 보호
_MAX_BUFFER_SIZE: Final[int] = 200
_MAX_RING_BUFFER: Final[int] = _PRE_EVENT_FRAMES + _POST_EVENT_FRAMES + 5

_METADATA_FILENAME: Final[str] = "metadata.json"


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class NetMotionExtractorConfig:
    """
    네트 움직임 시퀀스 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        pre_event_frames: 이벤트 전 수집 프레임 수
        post_event_frames: 이벤트 후 수집 프레임 수
        net_crop_size: 네트 ROI 크롭 크기
        min_event_confidence: 최소 이벤트 신뢰도
        buffer_flush_count: 버퍼 flush 시퀀스 수
        buffer_flush_interval_sec: 버퍼 flush 간격 (초)
        max_buffer_size: 최대 버퍼 크기
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/net_motion"
    pre_event_frames: int = _PRE_EVENT_FRAMES
    post_event_frames: int = _POST_EVENT_FRAMES
    net_crop_size: int = _NET_CROP_SIZE
    min_event_confidence: float = 0.3
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/net_motion"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _NetMotionSample:
    """버퍼에 저장되는 시퀀스 샘플."""

    sample_id: str
    frames: NDArray[np.uint8]     # (T, H, W) 그레이스케일 시퀀스
    displacements: NDArray[np.float32]  # (T-1, 2) 변위 벡터 시퀀스
    scoring_type: str             # 라벨 ("swish", "rim_in", "rim_out")
    confidence: float
    hoop_side: str
    frame_index: int
    camera_id: str
    metadata: dict[str, float] = field(default_factory=dict)


# =============================================================================
# 네트 움직임 시퀀스 추출기
# =============================================================================

class NetMotionExtractor:
    """
    네트 움직임 시퀀스 추출기.

    NetAnalyzer의 득점 이벤트 발생 시, 이벤트 전후
    프레임 시퀀스와 변위 벡터를 수집합니다.

    수집 데이터:
        - 그레이스케일 네트 ROI 프레임 시퀀스 (T, H, W)
        - 프레임 간 변위 벡터 시퀀스 (T-1, 2)
        - 득점 유형 라벨 + 메타데이터

    사용 예시::

        >>> config = NetMotionExtractorConfig()
        >>> extractor = NetMotionExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> extractor.feed_frame(net_roi_gray, displacement, frame_index=42)
        >>> # 이벤트 발생 시
        >>> extractor.on_event(event)
        >>> result = extractor.finalize()
    """

    def __init__(self, config: NetMotionExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None
        self._sequences_dir: Path | None = None
        self._labels_dir: Path | None = None

        # 링 버퍼 (이벤트 전 프레임 유지)
        ring_size = config.pre_event_frames + config.post_event_frames + 5
        self._frame_ring: deque[NDArray[np.uint8]] = deque(maxlen=ring_size)
        self._disp_ring: deque[tuple[float, float]] = deque(maxlen=ring_size)
        self._frame_indices: deque[int] = deque(maxlen=ring_size)

        # 이벤트 후 수집 상태
        self._collecting_post: bool = False
        self._post_frames_remaining: int = 0
        self._pending_event: _ScoringEvent | None = None

        # 결과 버퍼
        self._buffer: list[_NetMotionSample] = []
        self._last_flush_time: float = 0.0

        # 통계
        self._total_events: int = 0
        self._total_samples: int = 0
        self._total_flushed: int = 0

        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_samples(self) -> int:
        """총 수집 시퀀스 수."""
        return self._total_samples

    def initialize(self, session_id: str, game_id: str) -> None:
        """
        추출 세션 초기화.

        Args:
            session_id: 세션 식별자
            game_id: 경기 식별자
        """
        with self._lock:
            if not self._config.enabled:
                logger.info("NetMotionExtractor 비활성화 상태")
                return

            self._session_id = session_id
            self._game_id = game_id

            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._session_dir = (
                Path(self._config.output_dir) / date_str / session_id
            )
            self._sequences_dir = self._session_dir / "sequences"
            self._labels_dir = self._session_dir / "labels"
            self._sequences_dir.mkdir(parents=True, exist_ok=True)
            self._labels_dir.mkdir(parents=True, exist_ok=True)

            self._frame_ring.clear()
            self._disp_ring.clear()
            self._frame_indices.clear()
            self._collecting_post = False
            self._post_frames_remaining = 0
            self._pending_event = None
            self._buffer.clear()
            self._last_flush_time = time.monotonic()
            self._total_events = 0
            self._total_samples = 0
            self._total_flushed = 0

            self._initialized = True
            logger.info(
                "NetMotionExtractor 초기화: session=%s, dir=%s",
                session_id, self._session_dir,
            )

    def feed_frame(
        self,
        net_roi_gray: NDArray[np.uint8],
        displacement: tuple[float, float],
        frame_index: int,
    ) -> None:
        """
        매 프레임 네트 ROI와 변위 입력.

        Args:
            net_roi_gray: 네트 ROI 그레이스케일 이미지
            displacement: 프레임 간 변위 벡터 (dx, dy)
            frame_index: 프레임 인덱스
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            # 리사이즈
            crop_size = self._config.net_crop_size
            resized = cv2.resize(
                net_roi_gray, (crop_size, crop_size),
                interpolation=cv2.INTER_AREA,
            )

            self._frame_ring.append(resized)
            self._disp_ring.append(displacement)
            self._frame_indices.append(frame_index)

            # 이벤트 후 수집 중이면 카운트 감소
            if self._collecting_post:
                self._post_frames_remaining -= 1
                if self._post_frames_remaining <= 0:
                    self._finalize_sequence()

    def on_event(
        self,
        event: _ScoringEvent,
        camera_id: str | None = None,
    ) -> None:
        """
        득점 이벤트 발생 시 호출.

        이벤트 후 프레임 수집을 시작합니다.

        Args:
            event: 득점 이벤트
            camera_id: 카메라 식별자
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            if event.confidence < self._config.min_event_confidence:
                return

            self._total_events += 1
            self._pending_event = event
            self._collecting_post = True
            self._post_frames_remaining = self._config.post_event_frames

    def finalize(self) -> ExtractionResult | None:
        """
        추출 세션 종료.

        Returns:
            ExtractionResult 또는 None
        """
        if not self._initialized:
            return None

        with self._lock:
            try:
                # 진행 중인 시퀀스 완료
                if self._collecting_post and self._pending_event is not None:
                    self._finalize_sequence()

                # 잔여 버퍼 flush
                self._flush_buffer()

                metadata = DatasetMetadata(
                    dataset_type=DatasetType.NET_MOTION,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id] if self._game_id else [],
                    description=(
                        f"net_motion_classifier 시퀀스 추출 | "
                        f"session={self._session_id} | "
                        f"classes=swish,rim_in,rim_out | "
                        f"events={self._total_events} | "
                        f"samples={self._total_samples}"
                    ),
                )

                if self._session_dir is not None:
                    meta_path = self._session_dir / _METADATA_FILENAME
                    meta_dict = asdict(metadata)
                    # datetime/UUID → 문자열 변환
                    meta_dict["dataset_id"] = str(meta_dict["dataset_id"])
                    meta_dict["created_at"] = meta_dict["created_at"].isoformat()
                    meta_path.write_text(
                        json.dumps(meta_dict, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                result = ExtractionResult(
                    game_id=self._game_id or "",
                    metadata=metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._session_dir) if self._session_dir else "",
                    upload_status=UploadStatus.PENDING,
                    s3_key=f"{self._config.s3_prefix}/{self._session_id}/",
                )

                logger.info(
                    "NetMotionExtractor 종료: events=%d, samples=%d, flushed=%d",
                    self._total_events, self._total_samples, self._total_flushed,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _finalize_sequence(self) -> None:
        """현재 수집 중인 시퀀스를 샘플로 변환하여 버퍼에 추가."""
        event = self._pending_event
        if event is None:
            self._collecting_post = False
            return

        frames = list(self._frame_ring)
        disps = list(self._disp_ring)

        if len(frames) < self._config.pre_event_frames:
            # 프레임 부족
            self._collecting_post = False
            self._pending_event = None
            return

        # 시퀀스 구성
        frame_array = np.stack(frames, axis=0).astype(np.uint8)
        disp_array = np.array(disps, dtype=np.float32)

        sample_id = (
            f"net_{event.hoop_side}_{event.frame_index:08d}_"
            f"{event.scoring_type.value}"
        )

        sample = _NetMotionSample(
            sample_id=sample_id,
            frames=frame_array,
            displacements=disp_array,
            scoring_type=event.scoring_type.value,
            confidence=event.confidence,
            hoop_side=event.hoop_side,
            frame_index=event.frame_index,
            camera_id=event.camera_id or "cam_0",
            metadata={
                "vertical_displacement": event.vertical_displacement,
                "horizontal_displacement": event.horizontal_displacement,
                "oscillation_count": float(event.oscillation_count),
                "duration_frames": float(event.duration_frames),
            },
        )

        self._buffer.append(sample)
        self._total_samples += 1

        # 메모리 보호
        if len(self._buffer) > self._config.max_buffer_size:
            self._flush_buffer()

        self._collecting_post = False
        self._pending_event = None

        self._check_auto_flush()

    def _check_auto_flush(self) -> None:
        """버퍼 자동 flush 조건 확인."""
        elapsed = time.monotonic() - self._last_flush_time
        if (
            len(self._buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼 내 샘플을 디스크에 기록."""
        if not self._buffer or self._sequences_dir is None:
            return

        for sample in self._buffer:
            # NPZ로 시퀀스 저장
            npz_path = self._sequences_dir / f"{sample.sample_id}.npz"
            np.savez_compressed(
                str(npz_path),
                frames=sample.frames,
                displacements=sample.displacements,
            )

            # JSON 라벨 저장
            label_path = self._labels_dir / f"{sample.sample_id}.json"
            label_data = {
                "scoring_type": sample.scoring_type,
                "confidence": sample.confidence,
                "hoop_side": sample.hoop_side,
                "frame_index": sample.frame_index,
                "camera_id": sample.camera_id,
                "sequence_length": int(sample.frames.shape[0]),
                **sample.metadata,
            }
            label_path.write_text(
                json.dumps(label_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        self._total_flushed += len(self._buffer)
        logger.debug(
            "NetMotionExtractor flush: %d 시퀀스 기록", len(self._buffer),
        )
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"NetMotionExtractor(events={self._total_events}, "
            f"samples={self._total_samples}, flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "NetMotionExtractor",
    "NetMotionExtractorConfig",
]

__version__: str = "1.0.0"
