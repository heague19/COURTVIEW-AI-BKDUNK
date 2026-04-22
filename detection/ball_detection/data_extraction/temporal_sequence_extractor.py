# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: temporal_sequence_extractor.py
설명: 시간적 프레임 시퀀스 추출기
      - 연속 프레임 시퀀스를 수집하여 시간적 모델 학습에 활용
      - 이벤트 트리거 기반 시퀀스 캡처 (상태 전환, 속도 변화 등)
      - 프레임 시퀀스 + 감지 라벨 + 물리 정보 동시 저장
      - 공 감지 시간적 일관성 모델 재학습용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 상태/추적 파라미터
    - shared/dto/ball_dto.py: BallDetection DTO
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetMetadata
    - shared/dto/geometry_dto.py: BoundingBox

시퀀스 캡처 트리거:
    1. 상태 전환 (HELD → SHOOTING, DRIBBLING → PASSING 등)
    2. 급격한 속도/방향 변화 (가속도 임계값 초과)
    3. 가려짐 복구 (LOST → 재감지)
    4. 주기적 샘플링 (N 프레임마다)
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
from uuid import uuid4

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
    BALL_DETECTION_MIN_CONFIDENCE,
    BallState,
)
from shared.dto.ball_dto import BallDetection
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)


logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 시퀀스 길이 (프레임 수)
_SEQUENCE_LENGTH: Final[int] = 16

# 시퀀스 전후 컨텍스트 (프레임 수)
_CONTEXT_FRAMES: Final[int] = 4

# 주기적 샘플링 간격 (프레임)
_PERIODIC_INTERVAL: Final[int] = 300  # 10초 @30fps

# 가속도 임계값 (급변 감지용, 픽셀/프레임²)
_ACCELERATION_THRESHOLD: Final[float] = 20.0

# 프레임 리사이즈 크기 (시퀀스 저장용)
_FRAME_RESIZE: Final[tuple[int, int]] = (320, 240)

# JPEG 품질
_JPEG_QUALITY: Final[int] = 85

# 버퍼 자동 flush
_BUFFER_FLUSH_COUNT: Final[int] = 20
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 최대 버퍼 크기
_MAX_BUFFER_SIZE: Final[int] = 100

# ring buffer 크기 (시퀀스 + 컨텍스트 + 여유)
_RING_BUFFER_SIZE: Final[int] = _SEQUENCE_LENGTH + _CONTEXT_FRAMES * 2 + 10


# =============================================================================
# 시퀀스 트리거 유형
# =============================================================================

@unique
class SequenceTrigger(str, Enum):
    """시퀀스 캡처 트리거 유형."""

    STATE_TRANSITION = "state_transition"      # 상태 전환
    VELOCITY_CHANGE = "velocity_change"        # 급격한 속도 변화
    OCCLUSION_RECOVERY = "occlusion_recovery"  # 가려짐 복구
    PERIODIC = "periodic"                      # 주기적 샘플링

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class TemporalSequenceExtractorConfig:
    """
    시간적 시퀀스 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        sequence_length: 시퀀스 프레임 수
        context_frames: 전후 컨텍스트 프레임 수
        periodic_interval: 주기적 샘플링 간격 (프레임)
        acceleration_threshold: 가속도 급변 임계값
        frame_resize: 프레임 리사이즈 크기
        min_confidence: 최소 감지 신뢰도
        buffer_flush_count: 버퍼 flush 시퀀스 수
        buffer_flush_interval_sec: 버퍼 flush 간격
        max_buffer_size: 최대 버퍼 크기
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/ball_temporal"
    sequence_length: int = _SEQUENCE_LENGTH
    context_frames: int = _CONTEXT_FRAMES
    periodic_interval: int = _PERIODIC_INTERVAL
    acceleration_threshold: float = _ACCELERATION_THRESHOLD
    frame_resize: tuple[int, int] = _FRAME_RESIZE
    min_confidence: float = BALL_DETECTION_MIN_CONFIDENCE
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    max_buffer_size: int = _MAX_BUFFER_SIZE
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/ball_temporal"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _FrameRecord:
    """링 버퍼에 저장되는 프레임 레코드."""

    frame_index: int
    frame_data: bytes | None     # JPEG 인코딩된 리사이즈 프레임
    ball_detected: bool
    ball_position: tuple[float, float] | None  # (x, y)
    ball_bbox: tuple[float, float, float, float] | None  # (x, y, w, h)
    ball_confidence: float
    ball_state: str              # BallState.value
    velocity: tuple[float, float] | None  # (vx, vy)


@dataclass(slots=True)
class _CapturedSequence:
    """캡처된 시퀀스 (버퍼 저장용)."""

    sequence_id: str
    trigger_type: str
    trigger_detail: str
    center_frame: int
    frames: list[_FrameRecord]
    camera_id: str


# =============================================================================
# 시간적 시퀀스 추출기
# =============================================================================

class TemporalSequenceExtractor:
    """
    시간적 프레임 시퀀스 추출기.

    이벤트 트리거 기반으로 연속 프레임 시퀀스를 캡처하여
    시간적 일관성 모델 학습에 활용합니다.

    캡처 트리거:
        1. 상태 전환: HELD→SHOOTING, DRIBBLING→PASSING 등
        2. 속도 급변: 가속도 임계값 초과
        3. 가려짐 복구: LOST 상태 → 재감지
        4. 주기적: N 프레임마다 무조건 캡처

    사용 예시::

        >>> config = TemporalSequenceExtractorConfig()
        >>> extractor = TemporalSequenceExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> # 매 프레임
        >>> extractor.process(
        ...     frame=frame,
        ...     detection=ball_detection,
        ...     frame_index=42,
        ... )
        >>> result = extractor.finalize()
    """

    def __init__(self, config: TemporalSequenceExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None

        # 링 버퍼
        self._ring_buffer: deque[_FrameRecord] = deque(maxlen=_RING_BUFFER_SIZE)

        # 이전 상태 (트리거 감지용)
        self._prev_state: str = BallState.LOST.value
        self._prev_velocity: tuple[float, float] | None = None
        self._frames_since_last_periodic: int = 0
        self._was_lost: bool = False

        # 캡처 버퍼
        self._capture_buffer: list[_CapturedSequence] = []
        self._last_flush_time: float = 0.0

        # 중복 방지 (최근 캡처 프레임 인덱스)
        self._recent_captures: deque[int] = deque(maxlen=50)

        # 통계
        self._total_frames: int = 0
        self._total_captures: int = 0
        self._total_flushed: int = 0
        self._trigger_counts: dict[str, int] = {
            SequenceTrigger.STATE_TRANSITION.value: 0,
            SequenceTrigger.VELOCITY_CHANGE.value: 0,
            SequenceTrigger.OCCLUSION_RECOVERY.value: 0,
            SequenceTrigger.PERIODIC.value: 0,
        }

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

            self._ring_buffer.clear()
            self._prev_state = BallState.LOST.value
            self._prev_velocity = None
            self._frames_since_last_periodic = 0
            self._was_lost = False

            self._capture_buffer.clear()
            self._last_flush_time = time.monotonic()
            self._recent_captures.clear()

            self._total_frames = 0
            self._total_captures = 0
            self._total_flushed = 0
            self._trigger_counts = {
                SequenceTrigger.STATE_TRANSITION.value: 0,
                SequenceTrigger.VELOCITY_CHANGE.value: 0,
                SequenceTrigger.OCCLUSION_RECOVERY.value: 0,
                SequenceTrigger.PERIODIC.value: 0,
            }

            self._initialized = True
            logger.info(
                "TemporalSequenceExtractor 초기화: session=%s", session_id,
            )

    def process(
        self,
        frame: NDArray[np.uint8],
        detection: BallDetection,
        frame_index: int,
        camera_id: str = "cam_0",
    ) -> None:
        """
        매 프레임 처리.

        Args:
            frame: 원본 프레임 (BGR)
            detection: 공 감지 결과
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            self._total_frames += 1

            # 프레임 레코드 생성 → 링 버퍼 추가
            record = self._create_frame_record(frame, detection, frame_index)
            self._ring_buffer.append(record)

            # 버퍼가 충분히 채워지기 전에는 트리거 검사 안함
            min_required = self._config.sequence_length + self._config.context_frames
            if len(self._ring_buffer) < min_required:
                self._update_state(detection)
                return

            # 중복 방지 (최근 캡처 프레임과 겹치면 스킵)
            if self._is_recently_captured(frame_index):
                self._update_state(detection)
                return

            # 버퍼 크기 제한
            if len(self._capture_buffer) >= self._config.max_buffer_size:
                self._update_state(detection)
                return

            # 트리거 검사
            trigger = self._check_triggers(detection, frame_index)

            if trigger is not None:
                trigger_type, trigger_detail = trigger
                self._capture_sequence(
                    frame_index, camera_id, trigger_type, trigger_detail,
                )

            self._update_state(detection)

            # 자동 flush
            self._check_auto_flush()

    def finalize(self) -> ExtractionResult | None:
        """추출 세션 종료 및 결과 반환."""
        if not self._initialized or not self._config.enabled:
            return None

        with self._lock:
            try:
                start_time = time.monotonic()

                self._flush_buffer()
                self._write_metadata()

                total_size = self._compute_directory_size()
                processing_time_ms = (time.monotonic() - start_time) * 1000.0

                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                s3_key = (
                    f"{self._config.s3_prefix}/{date_str}/{self._session_id}"
                )

                ds_metadata = DatasetMetadata(
                    dataset_type=DatasetType.BALL_TEMPORAL,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id],
                    description=(
                        f"시간적 프레임 시퀀스 데이터 "
                        f"(session={self._session_id}, "
                        f"sequences={self._total_flushed})"
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
                    "TemporalSequenceExtractor 종료: "
                    "프레임=%d, 캡처=%d, 트리거=%s",
                    self._total_frames,
                    self._total_flushed,
                    self._trigger_counts,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 트리거 검사
    # =========================================================================

    def _check_triggers(
        self,
        detection: BallDetection,
        frame_index: int,
    ) -> tuple[str, str] | None:
        """
        캡처 트리거 검사.

        Returns:
            (trigger_type, trigger_detail) 또는 None
        """
        current_state = detection.state.value if detection.is_valid else BallState.LOST.value

        # 1. 가려짐 복구 트리거 (LOST → 유효 감지: STATE_TRANSITION보다 우선)
        if self._was_lost and detection.is_valid:
            detail = f"LOST → {current_state} (재감지)"
            return SequenceTrigger.OCCLUSION_RECOVERY, detail

        # 2. 상태 전환 트리거 (가려짐 복구 제외한 일반 전환)
        if current_state != self._prev_state:
            if self._prev_state != BallState.LOST.value or current_state != BallState.LOST.value:
                detail = f"{self._prev_state} → {current_state}"
                return SequenceTrigger.STATE_TRANSITION, detail

        # 3. 속도 급변 트리거
        if detection.is_valid and detection.position is not None:
            current_vel = self._compute_velocity(detection)
            if current_vel is not None and self._prev_velocity is not None:
                ax = current_vel[0] - self._prev_velocity[0]
                ay = current_vel[1] - self._prev_velocity[1]
                accel = float(np.sqrt(ax**2 + ay**2))
                if accel > self._config.acceleration_threshold:
                    detail = f"가속도={accel:.1f}"
                    return SequenceTrigger.VELOCITY_CHANGE, detail

        # 4. 주기적 샘플링 트리거
        self._frames_since_last_periodic += 1
        if self._frames_since_last_periodic >= self._config.periodic_interval:
            self._frames_since_last_periodic = 0
            return SequenceTrigger.PERIODIC, f"간격={self._config.periodic_interval}"

        return None

    def _update_state(self, detection: BallDetection) -> None:
        """이전 상태 갱신."""
        current_state = detection.state.value if detection.is_valid else BallState.LOST.value
        self._was_lost = (self._prev_state == BallState.LOST.value)
        self._prev_state = current_state

        if detection.is_valid and detection.position is not None:
            self._prev_velocity = self._compute_velocity(detection)

    def _compute_velocity(
        self,
        detection: BallDetection,
    ) -> tuple[float, float] | None:
        """감지 결과에서 2D 속도 추정."""
        if detection.velocity is not None:
            return (detection.velocity[0], detection.velocity[1])

        # 링 버퍼에서 이전 프레임과 비교
        if (
            len(self._ring_buffer) >= 2
            and detection.position is not None
        ):
            prev = self._ring_buffer[-2]
            if prev.ball_position is not None:
                dx = detection.position.x - prev.ball_position[0]
                dy = detection.position.y - prev.ball_position[1]
                return (dx, dy)

        return None

    def _is_recently_captured(self, frame_index: int) -> bool:
        """최근 캡처된 프레임과 겹치는지 확인."""
        half_seq = self._config.sequence_length // 2
        for captured_frame in self._recent_captures:
            if abs(frame_index - captured_frame) < half_seq:
                return True
        return False

    # =========================================================================
    # 시퀀스 캡처
    # =========================================================================

    def _capture_sequence(
        self,
        center_frame: int,
        camera_id: str,
        trigger_type: str,
        trigger_detail: str,
    ) -> None:
        """링 버퍼에서 시퀀스 추출."""
        seq_len = self._config.sequence_length
        ctx = self._config.context_frames
        total_needed = seq_len + ctx  # 시퀀스 + 후방 컨텍스트

        # 링 버퍼에서 최근 프레임 추출
        available = list(self._ring_buffer)
        if len(available) < seq_len:
            return

        # 시퀀스: 최근 seq_len 프레임
        frames = available[-total_needed:] if len(available) >= total_needed else available[-seq_len:]

        sequence_id = f"seq_{center_frame:08d}_{trigger_type}_{str(uuid4())[:8]}"

        captured = _CapturedSequence(
            sequence_id=sequence_id,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            center_frame=center_frame,
            frames=list(frames),
            camera_id=camera_id,
        )

        self._capture_buffer.append(captured)
        self._recent_captures.append(center_frame)
        self._total_captures += 1
        trigger_key = trigger_type.value if hasattr(trigger_type, "value") else trigger_type
        self._trigger_counts[trigger_key] = (
            self._trigger_counts.get(trigger_key, 0) + 1
        )

    # =========================================================================
    # 프레임 레코드 생성
    # =========================================================================

    def _create_frame_record(
        self,
        frame: NDArray[np.uint8],
        detection: BallDetection,
        frame_index: int,
    ) -> _FrameRecord:
        """프레임 레코드 생성."""
        ball_detected = detection.is_valid and detection.position is not None

        ball_position = None
        ball_bbox_tuple = None
        ball_confidence = 0.0
        ball_state = BallState.LOST.value
        velocity = None

        if ball_detected and detection.position is not None:
            ball_position = (detection.position.x, detection.position.y)
            ball_confidence = detection.confidence
            ball_state = detection.state.value

            if detection.bbox is not None:
                b = detection.bbox
                ball_bbox_tuple = (b.x, b.y, b.width, b.height)

            if detection.velocity is not None:
                velocity = (detection.velocity[0], detection.velocity[1])

        # 프레임 리사이즈 → JPEG
        frame_small = cv2.resize(
            frame, self._config.frame_resize, interpolation=cv2.INTER_LINEAR,
        )
        success, encoded = cv2.imencode(
            ".jpg", frame_small, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY],
        )
        frame_data = bytes(encoded) if success else None

        return _FrameRecord(
            frame_index=frame_index,
            frame_data=frame_data,
            ball_detected=ball_detected,
            ball_position=ball_position,
            ball_bbox=ball_bbox_tuple,
            ball_confidence=ball_confidence,
            ball_state=ball_state,
            velocity=velocity,
        )

    # =========================================================================
    # 버퍼 관리
    # =========================================================================

    def _check_auto_flush(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_flush_time

        if (
            len(self._capture_buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """캡처 버퍼를 디스크에 기록."""
        if not self._capture_buffer or self._session_dir is None:
            return

        for captured in self._capture_buffer:
            try:
                # 시퀀스 디렉토리 생성
                seq_dir = self._session_dir / captured.sequence_id
                frames_dir = seq_dir / "frames"
                frames_dir.mkdir(parents=True, exist_ok=True)

                # 프레임 이미지 저장
                labels: list[dict] = []
                for i, fr in enumerate(captured.frames):
                    if fr.frame_data is not None:
                        img_path = (
                            frames_dir
                            / f"{i:03d}_f{fr.frame_index:08d}.jpg"
                        )
                        img_path.write_bytes(fr.frame_data)

                    label = {
                        "seq_index": i,
                        "frame_index": fr.frame_index,
                        "ball_detected": fr.ball_detected,
                        "ball_position": (
                            list(fr.ball_position)
                            if fr.ball_position else None
                        ),
                        "ball_bbox": (
                            list(fr.ball_bbox)
                            if fr.ball_bbox else None
                        ),
                        "ball_confidence": fr.ball_confidence,
                        "ball_state": fr.ball_state,
                        "velocity": (
                            list(fr.velocity)
                            if fr.velocity else None
                        ),
                    }
                    labels.append(label)

                # 시퀀스 메타데이터
                seq_meta = {
                    "sequence_id": captured.sequence_id,
                    "trigger_type": captured.trigger_type,
                    "trigger_detail": captured.trigger_detail,
                    "center_frame": captured.center_frame,
                    "camera_id": captured.camera_id,
                    "frame_count": len(captured.frames),
                    "labels": labels,
                }

                meta_path = seq_dir / "sequence.json"
                meta_path.write_text(
                    json.dumps(seq_meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.error(
                    "TemporalSequenceExtractor 시퀀스 저장 실패 "
                    "(seq=%s): %s", captured.sequence_id, exc,
                )

        flushed = len(self._capture_buffer)
        self._total_flushed += flushed
        self._capture_buffer.clear()
        self._last_flush_time = time.monotonic()

        logger.debug(
            "TemporalSequenceExtractor flush: %d 시퀀스 저장 (누적: %d)",
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
            "extractor": "TemporalSequenceExtractor",
            "version": __version__,
            "config": {
                "sequence_length": self._config.sequence_length,
                "context_frames": self._config.context_frames,
                "periodic_interval": self._config.periodic_interval,
                "acceleration_threshold": self._config.acceleration_threshold,
                "frame_resize": list(self._config.frame_resize),
            },
            "statistics": {
                "total_frames": self._total_frames,
                "total_captures": self._total_captures,
                "total_flushed": self._total_flushed,
                "trigger_counts": dict(self._trigger_counts),
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
                "TemporalSequenceExtractor 메타데이터 저장 실패: %s", exc,
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
    def total_captures(self) -> int:
        return self._total_captures

    @property
    def total_flushed(self) -> int:
        return self._total_flushed

    @property
    def trigger_counts(self) -> dict[str, int]:
        return dict(self._trigger_counts)

    def __repr__(self) -> str:
        return (
            f"TemporalSequenceExtractor("
            f"session={self._session_id!r}, "
            f"captures={self._total_captures}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "TemporalSequenceExtractor",
    "TemporalSequenceExtractorConfig",
    "SequenceTrigger",
]

__version__ = "1.0.0"
