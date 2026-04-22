# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: occlusion_sample_extractor.py
설명: 가려짐(Occlusion) 샘플 추출기
      - 공이 선수/골대 등에 의해 가려진 프레임 수집
      - 가려짐 전후 프레임 쌍 (context window) 저장
      - 가려짐 패턴별 분류 (선수 가려짐/골대 가려짐/프레임 아웃)
      - 가려짐 인식 모델 재학습 시 활용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 추적/상태 파라미터
    - shared/dto/ball_dto.py: BallDetection DTO
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/tracking_dto.py: TrackState

가려짐 감지 기준:
    1. 추적 중이던 공이 갑자기 미감지됨 (track lost)
    2. 직전 프레임에서 선수 bbox와 공 bbox 중첩
    3. 칼만 필터 예측 위치 근처에 선수가 위치
    4. 연속 미감지 후 재출현 시 예측 위치와 일치
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
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, unique
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
from shared.constants.ball_constants import (
    BALL_DETECTION_INPUT_SIZE,
    BALL_TRACKING_MAX_MISSING_FRAMES,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from shared.dto.geometry_dto import BoundingBox


logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 가려짐 컨텍스트 윈도우 (전후 프레임 수)
_CONTEXT_WINDOW: Final[int] = 5

# 가려짐 최소 지속 프레임 (1프레임 미감지는 노이즈로 무시)
_MIN_OCCLUSION_FRAMES: Final[int] = 2

# 가려짐 최대 지속 프레임 (이 이상이면 LOST로 간주)
_MAX_OCCLUSION_FRAMES: Final[int] = BALL_TRACKING_MAX_MISSING_FRAMES

# 선수 bbox와 공 bbox 중첩 판정 IoU 임계값
_PLAYER_BALL_IOU_THRESHOLD: Final[float] = 0.1

# 크롭 출력 크기
_CROP_SIZE: Final[int] = BALL_DETECTION_INPUT_SIZE

# JPEG 인코딩 품질
_JPEG_QUALITY: Final[int] = 90

# 버퍼 자동 flush
_BUFFER_FLUSH_COUNT: Final[int] = 30
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 최대 버퍼 크기
_MAX_BUFFER_SIZE: Final[int] = 200


# =============================================================================
# 가려짐 유형
# =============================================================================

@unique
class OcclusionType(str, Enum):
    """가려짐 유형."""

    PLAYER = "player"        # 선수에 의한 가려짐
    HOOP = "hoop"            # 골대/백보드에 의한 가려짐
    FRAME_OUT = "frame_out"  # 프레임 밖으로 나감
    UNKNOWN = "unknown"      # 원인 불명

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class OcclusionSampleExtractorConfig:
    """
    가려짐 샘플 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        context_window: 가려짐 전후 프레임 수
        min_occlusion_frames: 최소 가려짐 지속 프레임
        max_occlusion_frames: 최대 가려짐 지속 프레임
        player_ball_iou_threshold: 선수-공 중첩 IoU 임계값
        crop_size: 크롭 이미지 크기
        buffer_flush_count: 버퍼 flush 샘플 수
        buffer_flush_interval_sec: 버퍼 flush 간격
        max_buffer_size: 최대 버퍼 크기
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/ball_occlusion"
    context_window: int = _CONTEXT_WINDOW
    min_occlusion_frames: int = _MIN_OCCLUSION_FRAMES
    max_occlusion_frames: int = _MAX_OCCLUSION_FRAMES
    player_ball_iou_threshold: float = _PLAYER_BALL_IOU_THRESHOLD
    crop_size: int = _CROP_SIZE
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/ball_occlusion"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _FrameSnapshot:
    """프레임 스냅샷 (컨텍스트 윈도우용)."""

    frame_index: int
    ball_detected: bool
    ball_position: tuple[float, float] | None  # (x, y)
    ball_bbox: tuple[float, float, float, float] | None  # (x, y, w, h)
    ball_confidence: float
    player_bboxes: list[tuple[float, float, float, float]]  # [(x,y,w,h), ...]
    frame_data: bytes | None  # JPEG 인코딩된 프레임 (메모리 절약: 리사이즈)


@dataclass(slots=True)
class _OcclusionEvent:
    """가려짐 이벤트."""

    event_id: str
    occlusion_type: OcclusionType
    start_frame: int
    end_frame: int
    duration_frames: int
    last_known_position: tuple[float, float] | None
    predicted_position: tuple[float, float] | None
    reappear_position: tuple[float, float] | None
    context_before: list[_FrameSnapshot]
    context_after: list[_FrameSnapshot]
    camera_id: str
    overlapping_player_count: int


# =============================================================================
# 가려짐 샘플 추출기
# =============================================================================

class OcclusionSampleExtractor:
    """
    가려짐 샘플 추출기.

    공이 가려진 프레임과 전후 컨텍스트를 수집하여
    가려짐 인식 모델 재학습에 활용합니다.

    가려짐 감지 흐름:
        1. 매 프레임 스냅샷 저장 (ring buffer)
        2. 공 미감지 시 가려짐 카운터 증가
        3. 미감지 → 재감지 전환 시 가려짐 이벤트 확정
        4. 컨텍스트 윈도우 (전후 N 프레임) 추출
        5. 가려짐 유형 분류 (선수/골대/프레임아웃)

    사용 예시::

        >>> config = OcclusionSampleExtractorConfig()
        >>> extractor = OcclusionSampleExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> # 매 프레임
        >>> extractor.process(
        ...     frame=frame,
        ...     detection=ball_detection,
        ...     player_bboxes=player_boxes,
        ...     predicted_position=(320.0, 240.0),
        ...     frame_index=42,
        ... )
        >>> result = extractor.finalize()
    """

    def __init__(self, config: OcclusionSampleExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None

        # Ring buffer (컨텍스트 윈도우, deque O(1) 양단 삽입/삭제)
        self._max_buffer_frames = _CONTEXT_WINDOW * 3  # 여유 포함
        self._frame_buffer: deque[_FrameSnapshot] = deque(
            maxlen=self._max_buffer_frames,
        )

        # 가려짐 상태 추적
        self._is_occluded: bool = False
        self._occlusion_start_frame: int = -1
        self._occlusion_miss_count: int = 0
        self._last_known_position: tuple[float, float] | None = None
        self._last_predicted_position: tuple[float, float] | None = None
        self._context_before_occlusion: list[_FrameSnapshot] = []
        self._overlapping_player_count: int = 0
        self._overlapping_hoop: bool = False
        self._frame_width: int = 0
        self._frame_height: int = 0

        # 완료된 이벤트 버퍼
        self._event_buffer: list[_OcclusionEvent] = []
        self._last_flush_time: float = 0.0

        # 통계
        self._total_frames: int = 0
        self._total_events: int = 0
        self._total_flushed: int = 0
        self._type_counts: dict[str, int] = {t.value: 0 for t in OcclusionType}

        self._initialized: bool = False

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, session_id: str, game_id: str) -> None:
        """추출 세션 초기화."""
        with self._lock:
            if not self._config.enabled:
                return

            self._session_id = session_id
            self._game_id = game_id

            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._session_dir = (
                Path(self._config.output_dir) / date_str / session_id
            )
            self._session_dir.mkdir(parents=True, exist_ok=True)

            self._frame_buffer.clear()
            self._is_occluded = False
            self._occlusion_start_frame = -1
            self._occlusion_miss_count = 0
            self._last_known_position = None
            self._last_predicted_position = None
            self._context_before_occlusion.clear()
            self._overlapping_player_count = 0

            self._event_buffer.clear()
            self._last_flush_time = time.monotonic()
            self._total_frames = 0
            self._total_events = 0
            self._total_flushed = 0
            self._type_counts = {t.value: 0 for t in OcclusionType}

            self._initialized = True
            logger.info(
                "OcclusionSampleExtractor 초기화: session=%s", session_id,
            )

    def process(
        self,
        frame: NDArray[np.uint8],
        detection: BallDetection | None,
        player_bboxes: list[BoundingBox] | None = None,
        hoop_bboxes: list[BoundingBox] | None = None,
        predicted_position: tuple[float, float] | None = None,
        frame_index: int = 0,
        camera_id: str = "cam_0",
    ) -> None:
        """
        매 프레임 처리.

        Args:
            frame: 원본 프레임 (BGR)
            detection: 공 감지 결과 (None이면 미감지)
            player_bboxes: 선수 바운딩박스 목록
            hoop_bboxes: 골대(림/백보드) 바운딩박스 목록
            predicted_position: 칼만 필터 예측 위치
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            self._total_frames += 1

            # 프레임 크기 추적 (실제 해상도)
            h, w = frame.shape[:2]
            self._frame_height = h
            self._frame_width = w

            # 프레임 스냅샷 생성
            snapshot = self._create_snapshot(
                frame, detection, player_bboxes, frame_index,
            )
            self._append_to_ring_buffer(snapshot)

            ball_detected = (
                detection is not None
                and detection.is_valid
                and detection.position is not None
            )

            if ball_detected and detection is not None and detection.position is not None:
                # 공 감지됨
                if self._is_occluded:
                    # 가려짐 → 재출현: 이벤트 확정
                    self._finalize_occlusion_event(
                        reappear_position=(
                            detection.position.x, detection.position.y
                        ),
                        reappear_frame=frame_index,
                        camera_id=camera_id,
                    )

                self._last_known_position = (
                    detection.position.x, detection.position.y,
                )
                self._occlusion_miss_count = 0
                self._is_occluded = False
            else:
                # 공 미감지
                self._occlusion_miss_count += 1
                self._last_predicted_position = predicted_position

                if (
                    not self._is_occluded
                    and self._occlusion_miss_count >= self._config.min_occlusion_frames
                ):
                    # 가려짐 시작
                    self._start_occlusion(frame_index, player_bboxes, hoop_bboxes)

            # 자동 flush
            self._check_auto_flush()

    def finalize(self) -> ExtractionResult | None:
        """추출 세션 종료 및 결과 반환."""
        if not self._initialized or not self._config.enabled:
            return None

        with self._lock:
            try:
                start_time = time.monotonic()

                # 진행 중인 가려짐 이벤트 강제 종료
                if self._is_occluded:
                    self._finalize_occlusion_event(
                        reappear_position=None,
                        reappear_frame=self._total_frames,
                        camera_id="cam_0",
                    )

                self._flush_buffer()
                self._write_metadata()

                total_size = self._compute_directory_size()
                processing_time_ms = (time.monotonic() - start_time) * 1000.0

                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                s3_key = (
                    f"{self._config.s3_prefix}/{date_str}/{self._session_id}"
                )

                ds_metadata = DatasetMetadata(
                    dataset_type=DatasetType.BALL_OCCLUSION,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id],
                    description=(
                        f"가려짐 샘플 데이터 "
                        f"(session={self._session_id}, "
                        f"events={self._total_flushed})"
                    ),
                )

                result = ExtractionResult(
                    game_id=self._game_id,
                    metadata=ds_metadata,
                    record_count=self._total_flushed,
                    file_path=str(self._session_dir) if self._session_dir else "",
                    file_size_bytes=total_size,
                    processing_time_ms=processing_time_ms,
                    s3_bucket=self._config.s3_bucket,
                    s3_key=s3_key,
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "OcclusionSampleExtractor 종료: "
                    "프레임=%d, 이벤트=%d, 유형=%s",
                    self._total_frames,
                    self._total_flushed,
                    self._type_counts,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 가려짐 상태 관리
    # =========================================================================

    def _start_occlusion(
        self,
        frame_index: int,
        player_bboxes: list[BoundingBox] | None,
        hoop_bboxes: list[BoundingBox] | None = None,
    ) -> None:
        """가려짐 시작 기록."""
        self._is_occluded = True
        self._occlusion_start_frame = frame_index - self._config.min_occlusion_frames + 1

        # 가려짐 직전 컨텍스트 저장
        window = self._config.context_window
        buf_len = len(self._frame_buffer)
        self._context_before_occlusion = list(self._frame_buffer)[max(0, buf_len - window):]

        # 선수 중첩 수 기록
        self._overlapping_player_count = self._count_overlapping_players(
            player_bboxes,
        )
        # 골대 중첩 확인
        self._overlapping_hoop = self._check_hoop_overlap(hoop_bboxes)

    def _finalize_occlusion_event(
        self,
        reappear_position: tuple[float, float] | None,
        reappear_frame: int,
        camera_id: str,
    ) -> None:
        """가려짐 이벤트 확정."""
        duration = reappear_frame - self._occlusion_start_frame

        # 최대 초과 시 LOST → 수집 대상 아님
        if duration > self._config.max_occlusion_frames:
            self._is_occluded = False
            self._occlusion_miss_count = 0
            return

        # 가려짐 유형 분류
        occlusion_type = self._classify_occlusion_type(
            reappear_position,
        )

        # 재출현 후 컨텍스트
        window = self._config.context_window
        buf_len = len(self._frame_buffer)
        context_after = list(self._frame_buffer)[max(0, buf_len - window):]

        event_id = (
            f"occ_{self._occlusion_start_frame:08d}_"
            f"{reappear_frame:08d}_{camera_id}"
        )

        event = _OcclusionEvent(
            event_id=event_id,
            occlusion_type=occlusion_type,
            start_frame=self._occlusion_start_frame,
            end_frame=reappear_frame,
            duration_frames=duration,
            last_known_position=self._last_known_position,
            predicted_position=self._last_predicted_position,
            reappear_position=reappear_position,
            context_before=list(self._context_before_occlusion),
            context_after=context_after,
            camera_id=camera_id,
            overlapping_player_count=self._overlapping_player_count,
        )

        self._event_buffer.append(event)
        self._total_events += 1
        self._type_counts[occlusion_type.value] = (
            self._type_counts.get(occlusion_type.value, 0) + 1
        )

        # 상태 초기화
        self._is_occluded = False
        self._occlusion_miss_count = 0

    def _classify_occlusion_type(
        self,
        reappear_position: tuple[float, float] | None,
    ) -> OcclusionType:
        """
        가려짐 유형 분류.

        분류 기준 (우선순위순):
            1. 골대 가려짐: 가려짐 시작 시 골대 bbox 중첩 존재
            2. 선수 가려짐: 가려짐 시작 시 선수 bbox 중첩 존재
            3. 프레임 아웃: 마지막 위치가 프레임 가장자리
            4. 미분류: 위 조건 모두 불충족
        """
        # 골대 중첩이 있으면 골대 가려짐
        if self._overlapping_hoop:
            return OcclusionType.HOOP

        # 선수 중첩이 있으면 선수 가려짐
        if self._overlapping_player_count > 0:
            return OcclusionType.PLAYER

        # 마지막 위치가 프레임 가장자리이면 프레임 아웃
        if self._last_known_position is not None:
            x, y = self._last_known_position
            # 실제 프레임 크기 기준 가장자리 판정 (5% 이내)
            fw = max(self._frame_width, 1)
            fh = max(self._frame_height, 1)
            margin_x = fw * 0.05
            margin_y = fh * 0.05
            if (
                x < margin_x or x > fw - margin_x
                or y < margin_y or y > fh - margin_y
            ):
                return OcclusionType.FRAME_OUT

        return OcclusionType.UNKNOWN

    def _check_hoop_overlap(
        self,
        hoop_bboxes: list[BoundingBox] | None,
    ) -> bool:
        """공 마지막 위치가 골대 bbox와 중첩되는지 확인."""
        if hoop_bboxes is None or self._last_known_position is None:
            return False

        bx, by = self._last_known_position
        for hb in hoop_bboxes:
            if (
                hb.x <= bx <= hb.x + hb.width
                and hb.y <= by <= hb.y + hb.height
            ):
                return True
        return False

    def _count_overlapping_players(
        self,
        player_bboxes: list[BoundingBox] | None,
    ) -> int:
        """공 마지막 위치와 중첩되는 선수 bbox 수."""
        if player_bboxes is None or self._last_known_position is None:
            return 0

        count = 0
        bx, by = self._last_known_position
        for pb in player_bboxes:
            # 공 위치가 선수 bbox 내부에 있는지 확인
            if (
                pb.x <= bx <= pb.x + pb.width
                and pb.y <= by <= pb.y + pb.height
            ):
                count += 1
        return count

    # =========================================================================
    # 프레임 스냅샷 관리
    # =========================================================================

    def _create_snapshot(
        self,
        frame: NDArray[np.uint8],
        detection: BallDetection | None,
        player_bboxes: list[BoundingBox] | None,
        frame_index: int,
    ) -> _FrameSnapshot:
        """프레임 스냅샷 생성."""
        ball_detected = (
            detection is not None and detection.is_valid
            and detection.position is not None
        )

        ball_position = None
        ball_bbox_tuple = None
        ball_confidence = 0.0

        if ball_detected and detection is not None:
            if detection.position is not None:
                ball_position = (detection.position.x, detection.position.y)
            if detection.bbox is not None:
                b = detection.bbox
                ball_bbox_tuple = (b.x, b.y, b.width, b.height)
            ball_confidence = detection.confidence

        # 선수 bbox 튜플 변환
        player_bbox_tuples: list[tuple[float, float, float, float]] = []
        if player_bboxes:
            for pb in player_bboxes:
                player_bbox_tuples.append(
                    (pb.x, pb.y, pb.width, pb.height)
                )

        # 프레임 리사이즈 → JPEG (메모리 절약)
        frame_small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
        success, encoded = cv2.imencode(
            ".jpg", frame_small, [cv2.IMWRITE_JPEG_QUALITY, 70],
        )
        frame_data = bytes(encoded) if success else None

        return _FrameSnapshot(
            frame_index=frame_index,
            ball_detected=ball_detected,
            ball_position=ball_position,
            ball_bbox=ball_bbox_tuple,
            ball_confidence=ball_confidence,
            player_bboxes=player_bbox_tuples,
            frame_data=frame_data,
        )

    def _append_to_ring_buffer(self, snapshot: _FrameSnapshot) -> None:
        """링 버퍼에 스냅샷 추가 (deque maxlen 자동 제거)."""
        self._frame_buffer.append(snapshot)

    # =========================================================================
    # 버퍼 관리
    # =========================================================================

    def _check_auto_flush(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_flush_time

        if (
            len(self._event_buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
            or len(self._event_buffer) >= self._config.max_buffer_size
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """이벤트 버퍼를 디스크에 기록."""
        if not self._event_buffer or self._session_dir is None:
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

        # 이벤트별 컨텍스트 이미지 + 메타데이터 저장
        events_data: list[dict] = []
        for event in self._event_buffer:
            try:
                # 컨텍스트 프레임 이미지 저장
                context_dir = self._session_dir / event.event_id
                context_dir.mkdir(exist_ok=True)

                for i, snap in enumerate(event.context_before):
                    if snap.frame_data is not None:
                        img_path = (
                            context_dir
                            / f"before_{i:02d}_f{snap.frame_index:08d}.jpg"
                        )
                        img_path.write_bytes(snap.frame_data)

                for i, snap in enumerate(event.context_after):
                    if snap.frame_data is not None:
                        img_path = (
                            context_dir
                            / f"after_{i:02d}_f{snap.frame_index:08d}.jpg"
                        )
                        img_path.write_bytes(snap.frame_data)
            except OSError as exc:
                logger.error(
                    "OcclusionSampleExtractor 이미지 저장 실패 "
                    "(event=%s): %s", event.event_id, exc,
                )

            event_dict = {
                "event_id": event.event_id,
                "occlusion_type": event.occlusion_type.value,
                "start_frame": event.start_frame,
                "end_frame": event.end_frame,
                "duration_frames": event.duration_frames,
                "last_known_position": (
                    list(event.last_known_position)
                    if event.last_known_position else None
                ),
                "predicted_position": (
                    list(event.predicted_position)
                    if event.predicted_position else None
                ),
                "reappear_position": (
                    list(event.reappear_position)
                    if event.reappear_position else None
                ),
                "camera_id": event.camera_id,
                "overlapping_player_count": event.overlapping_player_count,
                "context_before_count": len(event.context_before),
                "context_after_count": len(event.context_after),
            }
            events_data.append(event_dict)

        # JSONL 저장
        jsonl_path = self._session_dir / f"occlusion_events_{timestamp}.jsonl"
        try:
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for ed in events_data:
                    f.write(json.dumps(ed, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error(
                "OcclusionSampleExtractor JSONL 저장 실패: %s", exc,
            )

        flushed = len(self._event_buffer)
        self._total_flushed += flushed
        self._event_buffer.clear()
        self._last_flush_time = time.monotonic()

        logger.debug(
            "OcclusionSampleExtractor flush: %d 이벤트 저장 (누적: %d)",
            flushed, self._total_flushed,
        )

    def _write_metadata(self) -> None:
        """세션 메타데이터 기록."""
        if self._session_dir is None:
            return

        metadata = {
            "session_id": self._session_id,
            "game_id": self._game_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "OcclusionSampleExtractor",
            "version": __version__,
            "config": {
                "context_window": self._config.context_window,
                "min_occlusion_frames": self._config.min_occlusion_frames,
                "max_occlusion_frames": self._config.max_occlusion_frames,
            },
            "statistics": {
                "total_frames": self._total_frames,
                "total_events": self._total_events,
                "total_flushed": self._total_flushed,
                "type_counts": dict(self._type_counts),
            },
        }

        path = self._session_dir / "metadata.json"
        try:
            path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error(
                "OcclusionSampleExtractor 메타데이터 저장 실패: %s", exc,
            )

    def _compute_directory_size(self) -> int:
        if self._session_dir is None or not self._session_dir.exists():
            return 0
        total = 0
        for fp in self._session_dir.rglob("*"):
            if fp.is_file():
                total += fp.stat().st_size
        return total

    # =========================================================================
    # 상태 조회
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_occluded(self) -> bool:
        return self._is_occluded

    @property
    def total_events(self) -> int:
        return self._total_events

    @property
    def total_flushed(self) -> int:
        return self._total_flushed

    @property
    def type_counts(self) -> dict[str, int]:
        return dict(self._type_counts)

    def __repr__(self) -> str:
        return (
            f"OcclusionSampleExtractor("
            f"session={self._session_id!r}, "
            f"events={self._total_events}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "OcclusionSampleExtractor",
    "OcclusionSampleExtractorConfig",
    "OcclusionType",
]

__version__ = "1.0.0"
