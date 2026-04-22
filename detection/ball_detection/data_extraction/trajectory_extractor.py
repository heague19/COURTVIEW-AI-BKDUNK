# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection/data_extraction
파일: trajectory_extractor.py
설명: 공 궤적 시퀀스 추출기
      - 추적된 공 궤적을 시퀀스 단위로 수집
      - 궤적 유형별 분류 (슈팅/패스/드리블/리바운드)
      - 물리 검증 (속도/가속도/포물선 피팅)
      - ShotTrajectoryRecord 형태로 저장
      - finalize() → ExtractionResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 궤적 파라미터
    - shared/dto/ball_dto.py: BallDetection, BallTrajectory DTO
    - shared/dto/dataset_dto.py: ExtractionResult, ShotTrajectoryRecord
    - shared/dto/geometry_dto.py: Point2D, Point3D
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from uuid import uuid4

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.ball_constants import (
    BALL_DETECTION_MIN_CONFIDENCE,
    PASS_VELOCITY_MIN,
    SHOT_VELOCITY_MIN,
    TRAJECTORY_MAX_POINTS,
    TRAJECTORY_MIN_POINTS,
    TRAJECTORY_MIN_R_SQUARED,
)
from shared.dto.ball_dto import BallDetection, BallTrajectory, TrajectoryType
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    ShotTrajectoryRecord,
    UploadStatus,
)


logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 궤적 완료 판정: 연속 미감지 프레임 수
_TRAJECTORY_GAP_THRESHOLD: Final[int] = 10

# 궤적 최소 길이 (유효 궤적 판정)
_TRAJECTORY_MIN_LENGTH: Final[int] = TRAJECTORY_MIN_POINTS

# 궤적 최대 길이 (메모리 보호)
_TRAJECTORY_MAX_LENGTH: Final[int] = TRAJECTORY_MAX_POINTS

# 포물선 피팅 R² 최소값
_MIN_R_SQUARED: Final[float] = TRAJECTORY_MIN_R_SQUARED

# 버퍼 자동 flush 임계값
_BUFFER_FLUSH_COUNT: Final[int] = 50
_BUFFER_FLUSH_INTERVAL_SEC: Final[float] = 300.0

# 최대 동시 활성 궤적 수
_MAX_ACTIVE_TRAJECTORIES: Final[int] = 10


# =============================================================================
# 설정 데이터클래스
# =============================================================================

@dataclass(slots=True)
class TrajectoryExtractorConfig:
    """
    궤적 추출기 설정.

    Attributes:
        output_dir: 추출 데이터 저장 루트 경로
        min_trajectory_length: 유효 궤적 최소 포인트 수
        max_trajectory_length: 궤적 최대 포인트 수
        gap_threshold: 궤적 종료 판정 미감지 프레임 수
        min_r_squared: 포물선 피팅 최소 R² 값
        min_confidence: 궤적 포인트 최소 신뢰도
        buffer_flush_count: 버퍼 flush 궤적 수
        buffer_flush_interval_sec: 버퍼 flush 간격 (초)
        dataset_split: 데이터셋 분할
        s3_bucket: S3 업로드 대상 버킷
        s3_prefix: S3 키 접두사
        enabled: 추출 활성화 여부
    """

    output_dir: str = "extracted_data/detection/ball_trajectory"
    min_trajectory_length: int = _TRAJECTORY_MIN_LENGTH
    max_trajectory_length: int = _TRAJECTORY_MAX_LENGTH
    gap_threshold: int = _TRAJECTORY_GAP_THRESHOLD
    min_r_squared: float = _MIN_R_SQUARED
    min_confidence: float = BALL_DETECTION_MIN_CONFIDENCE
    buffer_flush_count: int = _BUFFER_FLUSH_COUNT
    buffer_flush_interval_sec: float = _BUFFER_FLUSH_INTERVAL_SEC
    dataset_split: DatasetSplit = DatasetSplit.TRAIN
    s3_bucket: str = "courtview-datasets"
    s3_prefix: str = "detection/ball_trajectory"
    enabled: bool = True


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ActiveTrajectory:
    """현재 추적 중인 궤적."""

    trajectory_id: str
    points: list[tuple[float, float, float]]  # (x, y, z)
    frame_indices: list[int]
    confidences: list[float]
    camera_id: str
    last_frame: int
    trajectory_type: str  # TrajectoryType.value


@dataclass(slots=True)
class _CompletedTrajectory:
    """완료된 궤적 레코드 (버퍼 저장용)."""

    trajectory_id: str
    record: ShotTrajectoryRecord
    trajectory_type: str
    avg_confidence: float
    r_squared: float  # 포물선 피팅 R²
    duration_frames: int


# =============================================================================
# 궤적 추출기
# =============================================================================

class TrajectoryExtractor:
    """
    공 궤적 시퀀스 추출기.

    BallTracker의 추적 결과에서 완성된 궤적을 수집하여
    궤적 예측 모델 재학습용 데이터셋을 생성합니다.

    궤적 분류:
        - 슈팅: 포물선 형태 + 속도 ≥ SHOT_VELOCITY_MIN
        - 패스: 수평 이동 + 속도 ≥ PASS_VELOCITY_MIN
        - 드리블: 수직 진동 패턴
        - 리바운드: 림 근처 하강 궤적

    사용 예시::

        >>> config = TrajectoryExtractorConfig()
        >>> extractor = TrajectoryExtractor(config)
        >>> extractor.initialize(session_id="sess_001", game_id="game_001")
        >>> # 프레임 루프 내에서
        >>> extractor.process(detection, frame_index=42, camera_id="cam_0")
        >>> # 분석 종료 시
        >>> result = extractor.finalize()
    """

    def __init__(self, config: TrajectoryExtractorConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        # 세션 상태
        self._session_id: str = ""
        self._game_id: str = ""
        self._session_dir: Path | None = None

        # 활성 궤적 (track_id → _ActiveTrajectory)
        self._active: dict[int, _ActiveTrajectory] = {}

        # 완료된 궤적 버퍼
        self._buffer: list[_CompletedTrajectory] = []
        self._last_flush_time: float = 0.0

        # 통계
        self._total_frames: int = 0
        self._total_completed: int = 0
        self._total_flushed: int = 0
        self._type_counts: dict[str, int] = {}

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

            self._active.clear()
            self._buffer.clear()
            self._last_flush_time = time.monotonic()
            self._total_frames = 0
            self._total_completed = 0
            self._total_flushed = 0
            self._type_counts.clear()

            self._initialized = True
            logger.info(
                "TrajectoryExtractor 초기화: session=%s, dir=%s",
                session_id, self._session_dir,
            )

    def process(
        self,
        detection: BallDetection,
        frame_index: int,
        camera_id: str = "cam_0",
        track_id: int = 0,
    ) -> None:
        """
        단일 프레임 감지 결과 처리.

        공이 감지되면 활성 궤적에 포인트를 추가하고,
        궤적이 종료되면 완료 처리합니다.

        Args:
            detection: 공 감지 결과
            frame_index: 프레임 인덱스
            camera_id: 카메라 ID
            track_id: 트랙 ID (BallTracker에서 할당)
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            self._total_frames += 1

            # 유효한 감지인 경우 궤적에 추가
            if (
                detection.is_valid
                and detection.confidence >= self._config.min_confidence
                and detection.position is not None
            ):
                self._add_point(detection, frame_index, camera_id, track_id)

            # 종료된 궤적 탐지
            self._check_completed_trajectories(frame_index)

            # 자동 flush 확인
            self._check_auto_flush()

    def process_trajectory(
        self,
        trajectory: BallTrajectory,
        camera_id: str = "cam_0",
    ) -> None:
        """
        완성된 BallTrajectory 직접 처리.

        BallTracker가 궤적 완료를 판정한 경우 직접 전달받아 처리.

        Args:
            trajectory: 완성된 궤적
            camera_id: 카메라 ID
        """
        if not self._initialized or not self._config.enabled:
            return

        with self._lock:
            if trajectory.length < self._config.min_trajectory_length:
                return

            # 3D 포인트 추출
            points_3d: list[tuple[float, float, float]] = []
            for det in trajectory.detections:
                if det.position_3d is not None:
                    points_3d.append((
                        det.position_3d.x,
                        det.position_3d.y,
                        det.position_3d.z,
                    ))
                elif det.position is not None:
                    points_3d.append((det.position.x, det.position.y, 0.0))

            frame_indices = [d.frame_index for d in trajectory.detections]
            confidences = [d.confidence for d in trajectory.detections]

            # ShotTrajectoryRecord 생성
            record = ShotTrajectoryRecord(
                trajectory_points=points_3d,
                ball_detected=True,
                shot_result=None,
                frame_indices=frame_indices,
                camera_id=camera_id,
            )

            # 궤적 유형 판정
            traj_type = trajectory.trajectory_type.value

            # 포물선 피팅 R²
            r_squared = self._compute_r_squared(points_3d)

            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            completed = _CompletedTrajectory(
                trajectory_id=str(trajectory.trajectory_id),
                record=record,
                trajectory_type=traj_type,
                avg_confidence=avg_conf,
                r_squared=r_squared,
                duration_frames=trajectory.duration_frames,
            )

            self._buffer.append(completed)
            self._total_completed += 1
            self._type_counts[traj_type] = self._type_counts.get(traj_type, 0) + 1

    def finalize(self) -> ExtractionResult | None:
        """추출 세션 종료 및 결과 반환."""
        if not self._initialized or not self._config.enabled:
            return None

        with self._lock:
            try:
                start_time = time.monotonic()

                # 남은 활성 궤적 강제 완료
                for track_id in list(self._active.keys()):
                    self._complete_trajectory(track_id)

                # 남은 버퍼 flush
                self._flush_buffer()

                # 메타데이터 기록
                self._write_metadata()

                total_size = self._compute_directory_size()
                processing_time_ms = (time.monotonic() - start_time) * 1000.0

                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                s3_key = (
                    f"{self._config.s3_prefix}/{date_str}/{self._session_id}"
                )

                ds_metadata = DatasetMetadata(
                    dataset_type=DatasetType.SHOT_TRAJECTORY,
                    total_records=self._total_flushed,
                    split=self._config.dataset_split,
                    source_game_ids=[self._game_id],
                    description=(
                        f"공 궤적 시퀀스 데이터 "
                        f"(session={self._session_id}, "
                        f"trajectories={self._total_flushed})"
                    ),
                )

                result = ExtractionResult(
                    game_id=self._game_id,
                    metadata=ds_metadata,
                    record_count=self._total_flushed,
                    file_path=(
                        str(self._session_dir) if self._session_dir else ""
                    ),
                    file_size_bytes=total_size,
                    processing_time_ms=processing_time_ms,
                    s3_bucket=self._config.s3_bucket,
                    s3_key=s3_key,
                    upload_status=UploadStatus.PENDING,
                )

                logger.info(
                    "TrajectoryExtractor 종료: "
                    "프레임=%d, 궤적=%d, 유형별=%s",
                    self._total_frames,
                    self._total_flushed,
                    self._type_counts,
                )

                return result
            finally:
                self._initialized = False

    # =========================================================================
    # 궤적 관리
    # =========================================================================

    def _add_point(
        self,
        detection: BallDetection,
        frame_index: int,
        camera_id: str,
        track_id: int,
    ) -> None:
        """감지 결과를 활성 궤적에 추가."""
        if detection.position is None:
            return

        # 3D 좌표 추출 (없으면 2D + z=0)
        if detection.position_3d is not None:
            point = (
                detection.position_3d.x,
                detection.position_3d.y,
                detection.position_3d.z,
            )
        else:
            point = (detection.position.x, detection.position.y, 0.0)

        # 최대 길이 도달 시 기존 궤적 완료 (새 궤적으로 현재 포인트 보존)
        if track_id in self._active:
            traj = self._active[track_id]
            if len(traj.points) >= self._config.max_trajectory_length:
                self._complete_trajectory(track_id)
                # track_id가 active에서 제거됨 → 아래 else 블록에서 새 궤적 생성

        if track_id in self._active:
            traj = self._active[track_id]
            traj.points.append(point)
            traj.frame_indices.append(frame_index)
            traj.confidences.append(detection.confidence)
            traj.last_frame = frame_index
        else:
            # 활성 궤적 수 제한
            if len(self._active) >= _MAX_ACTIVE_TRAJECTORIES:
                oldest_id = min(
                    self._active,
                    key=lambda k: self._active[k].last_frame,
                )
                self._complete_trajectory(oldest_id)

            # 새 궤적 생성
            traj_type = self._classify_initial(detection)
            self._active[track_id] = _ActiveTrajectory(
                trajectory_id=str(uuid4()),
                points=[point],
                frame_indices=[frame_index],
                confidences=[detection.confidence],
                camera_id=camera_id,
                last_frame=frame_index,
                trajectory_type=traj_type,
            )

    def _check_completed_trajectories(self, current_frame: int) -> None:
        """미감지 프레임 초과 궤적을 완료 처리."""
        completed_ids: list[int] = []
        for track_id, traj in self._active.items():
            gap = current_frame - traj.last_frame
            if gap >= self._config.gap_threshold:
                completed_ids.append(track_id)

        for track_id in completed_ids:
            self._complete_trajectory(track_id)

    def _complete_trajectory(self, track_id: int) -> None:
        """활성 궤적을 완료하여 버퍼에 추가."""
        traj = self._active.pop(track_id, None)
        if traj is None:
            return

        # 최소 길이 미달 시 폐기
        if len(traj.points) < self._config.min_trajectory_length:
            return

        # 궤적 유형 재분류 (전체 포인트 기반)
        traj_type = self._classify_trajectory(traj)

        # ShotTrajectoryRecord 생성
        record = ShotTrajectoryRecord(
            trajectory_points=list(traj.points),
            ball_detected=True,
            shot_result=None,
            frame_indices=list(traj.frame_indices),
            camera_id=traj.camera_id,
        )

        # 포물선 피팅 R²
        r_squared = self._compute_r_squared(traj.points)

        avg_conf = float(np.mean(traj.confidences)) if traj.confidences else 0.0
        duration = (
            traj.frame_indices[-1] - traj.frame_indices[0]
            if len(traj.frame_indices) >= 2
            else 0
        )

        completed = _CompletedTrajectory(
            trajectory_id=traj.trajectory_id,
            record=record,
            trajectory_type=traj_type,
            avg_confidence=avg_conf,
            r_squared=r_squared,
            duration_frames=duration,
        )

        self._buffer.append(completed)
        self._total_completed += 1
        self._type_counts[traj_type] = self._type_counts.get(traj_type, 0) + 1

    # =========================================================================
    # 궤적 분류
    # =========================================================================

    def _classify_initial(self, detection: BallDetection) -> str:
        """감지 결과 기반 초기 궤적 유형 추정."""
        if detection.velocity is not None:
            vx, vy, vz = detection.velocity
            speed = float(np.sqrt(vx**2 + vy**2 + vz**2))
            if speed >= SHOT_VELOCITY_MIN and vy < 0:
                return TrajectoryType.SHOT.value
            if speed >= PASS_VELOCITY_MIN:
                return TrajectoryType.PASS.value
        return TrajectoryType.UNKNOWN.value

    def _classify_trajectory(self, traj: _ActiveTrajectory) -> str:
        """
        전체 포인트 기반 궤적 유형 분류.

        분류 기준:
            - 슈팅: 포물선 형태 (R² ≥ 0.95) + 상승→하강
            - 패스: 수평 이동 우세 + 일정 속도
            - 드리블: y축 진동 패턴 (빈도 분석)
            - 리바운드: 림 근처 하강
        """
        if len(traj.points) < 3:
            return TrajectoryType.UNKNOWN.value

        points_arr = np.array(traj.points)
        y_vals = points_arr[:, 1]  # y 좌표 (수직)

        # 수직 이동 분석
        dy = np.diff(y_vals)
        ascending = np.sum(dy < 0)  # 화면 좌표: y↓ = 상승
        descending = np.sum(dy > 0)
        total_moves = len(dy)

        if total_moves == 0:
            return TrajectoryType.UNKNOWN.value

        # 진동 패턴 (드리블): 방향 전환 횟수
        sign_changes = np.sum(np.diff(np.sign(dy)) != 0)
        oscillation_ratio = sign_changes / max(total_moves, 1)

        # 드리블: 높은 진동 비율
        if oscillation_ratio > 0.4 and total_moves >= 6:
            return TrajectoryType.DRIBBLE.value

        # 슈팅: 상승 후 하강 (포물선)
        ascending_ratio = ascending / total_moves
        if ascending_ratio > 0.3 and descending / total_moves > 0.2:
            r_squared = self._compute_r_squared(traj.points)
            if r_squared >= self._config.min_r_squared:
                return TrajectoryType.SHOT.value

        # 패스: 수평 이동 우세
        x_range = float(np.ptp(points_arr[:, 0]))
        y_range = float(np.ptp(y_vals))
        if x_range > y_range * 1.5 and total_moves >= 3:
            return TrajectoryType.PASS.value

        # 리바운드: 주로 하강
        if descending / total_moves > 0.6:
            return TrajectoryType.REBOUND.value

        return TrajectoryType.UNKNOWN.value

    def _compute_r_squared(
        self,
        points: list[tuple[float, float, float]],
    ) -> float:
        """
        2차 포물선 피팅 R² 계산.

        y = ax² + bx + c 형태로 피팅하여 결정계수 계산.

        Args:
            points: (x, y, z) 좌표 목록

        Returns:
            R² 값 (0.0 ~ 1.0)
        """
        if len(points) < 3:
            return 0.0

        arr = np.array(points)
        x = arr[:, 0]
        y = arr[:, 1]

        # 2차 다항식 피팅
        try:
            coeffs = np.polyfit(x, y, 2)
            y_pred = np.polyval(coeffs, x)

            ss_res = float(np.sum((y - y_pred) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))

            if ss_tot < 1e-10:
                return 1.0  # 모든 점이 같은 y → 완벽한 피팅

            return float(max(0.0, 1.0 - ss_res / ss_tot))
        except (np.linalg.LinAlgError, ValueError):
            return 0.0

    # =========================================================================
    # 버퍼 관리
    # =========================================================================

    def _check_auto_flush(self) -> None:
        """버퍼 자동 flush 조건 확인."""
        now = time.monotonic()
        elapsed = now - self._last_flush_time

        if (
            len(self._buffer) >= self._config.buffer_flush_count
            or elapsed >= self._config.buffer_flush_interval_sec
        ):
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """버퍼의 궤적 레코드를 디스크에 기록."""
        if not self._buffer or self._session_dir is None:
            return

        records_data: list[dict] = []
        for completed in self._buffer:
            record_dict = {
                "trajectory_id": completed.trajectory_id,
                "trajectory_type": completed.trajectory_type,
                "trajectory_points": completed.record.trajectory_points,
                "frame_indices": completed.record.frame_indices,
                "camera_id": completed.record.camera_id,
                "ball_detected": completed.record.ball_detected,
                "shot_result": completed.record.shot_result,
                "avg_confidence": completed.avg_confidence,
                "r_squared": completed.r_squared,
                "duration_frames": completed.duration_frames,
                "point_count": len(completed.record.trajectory_points),
            }
            records_data.append(record_dict)

        # 파일명: 타임스탬프 기반
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        file_path = self._session_dir / f"trajectories_{timestamp}.jsonl"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for record in records_data:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("TrajectoryExtractor 디스크 저장 실패: %s", exc)
            self._buffer.clear()
            self._last_flush_time = time.monotonic()
            return

        flushed = len(self._buffer)
        self._total_flushed += flushed
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

        logger.debug(
            "TrajectoryExtractor flush: %d 궤적 저장 (누적: %d)",
            flushed, self._total_flushed,
        )

    def _write_metadata(self) -> None:
        """세션 메타데이터 JSON 기록."""
        if self._session_dir is None:
            return

        metadata = {
            "session_id": self._session_id,
            "game_id": self._game_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "TrajectoryExtractor",
            "version": __version__,
            "config": {
                "min_trajectory_length": self._config.min_trajectory_length,
                "gap_threshold": self._config.gap_threshold,
                "min_r_squared": self._config.min_r_squared,
                "min_confidence": self._config.min_confidence,
            },
            "statistics": {
                "total_frames": self._total_frames,
                "total_completed": self._total_completed,
                "total_flushed": self._total_flushed,
                "type_counts": dict(self._type_counts),
            },
        }

        metadata_path = self._session_dir / "metadata.json"
        try:
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("TrajectoryExtractor 메타데이터 저장 실패: %s", exc)

    def _compute_directory_size(self) -> int:
        """세션 디렉토리 전체 크기 (바이트)."""
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
    def active_trajectory_count(self) -> int:
        return len(self._active)

    @property
    def total_completed(self) -> int:
        return self._total_completed

    @property
    def total_flushed(self) -> int:
        return self._total_flushed

    @property
    def type_counts(self) -> dict[str, int]:
        return dict(self._type_counts)

    def __repr__(self) -> str:
        return (
            f"TrajectoryExtractor("
            f"session={self._session_id!r}, "
            f"active={len(self._active)}, "
            f"completed={self._total_completed}, "
            f"flushed={self._total_flushed})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "TrajectoryExtractor",
    "TrajectoryExtractorConfig",
]

__version__ = "1.0.0"
