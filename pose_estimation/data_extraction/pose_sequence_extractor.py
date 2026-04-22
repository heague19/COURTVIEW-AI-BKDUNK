# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/data_extraction
파일: pose_sequence_extractor.py
설명: 포즈 시퀀스 데이터 추출기
      - LSTM/Transformer/ST-GCN 학습용 동작 시퀀스 자동 추출
      - 3단계 품질 필터 (시퀀스 유효성/프레임 키포인트 품질/시퀀스 레벨 품질)
      - per-sequence 출력: frames/ + keypoints.json + labels.json
      - 액션 타입별 디렉토리 분류 (shooting_sequences/ 등)
      - 페이즈 분할 라벨 + 성공 여부 + 품질 점수
      - pHash 기반 대표 프레임 중복 방지
      - 배치 버퍼링 → 디스크 기록 → ExtractionResult 반환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

데이터 흐름:
    MotionAnalysis 완료 → 동작 시퀀스 확정 →
    PoseSequenceExtractor.extract_sequence(frames, keypoints_per_frame, action_type, ...) →
    3단계 필터 → 프레임 리사이즈 + JPEG 인코딩 →
    pHash 중복 확인 → keypoints.json + labels.json 생성 → 버퍼 축적 →
    flush() → {action}_sequences/seq_{id}/frames/*.jpg + keypoints.json + labels.json →
    finalize() → metadata.json + ExtractionResult

참조:
    - pose_estimation/data_extraction/keypoint_extractor.py: 동일 패키지 per-frame 패턴
    - shared/dto/dataset_dto.py: DatasetType.POSE_SEQUENCE, ExtractionResult
    - shared/constants/pose_constants.py: NUM_KEYPOINTS_COCO, KEYPOINT_* 인덱스
    - shared/dto/motion_dto.py: ActionType 11종 (참조만, 직접 임포트 안함)
    - configs/pose/data_extraction.yaml: pose_sequence_extraction 섹션
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# Direct Import (shared)
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.constants.pose_constants import (
    JOINT_CONFIDENCE_THRESHOLD,
    KEYPOINT_LEFT_HIP,
    KEYPOINT_LEFT_SHOULDER,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_RIGHT_SHOULDER,
    NUM_KEYPOINTS_COCO,
)
from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetSplit,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)
from shared.exceptions.analysis_exceptions import PoseEstimationException

# =============================================================================
# DI (TYPE_CHECKING Guard)
# =============================================================================
if TYPE_CHECKING:
    from core_foundation.config.config_loader import ConfigLoader
    from core_foundation.monitoring.metrics_collector import MetricsCollector

# =============================================================================
# 로거
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
# YAML 설정 키
CONFIG_KEY_POSE_SEQUENCE_EXTRACTION = "data_extraction.pose_sequence_extraction"

# 기본값 (YAML 미로드 시 폴백)
DEFAULT_MIN_FRAMES: int = 10
DEFAULT_MAX_FRAMES: int = 150
DEFAULT_VALID_ACTION_TYPES: tuple[str, ...] = (
    "shooting", "dribbling", "passing", "defense_stance",
    "screen_set", "screen_use", "cutting", "driving",
    "rebounding", "blocking", "movement",
)
DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD: float = JOINT_CONFIDENCE_THRESHOLD  # 0.5
DEFAULT_MIN_VISIBLE_KEYPOINTS: int = 8
DEFAULT_MIN_SKELETON_COMPLETENESS: float = 0.47  # 8/17
DEFAULT_CRITICAL_KEYPOINT_INDICES: tuple[int, ...] = (
    KEYPOINT_LEFT_SHOULDER,   # 5
    KEYPOINT_RIGHT_SHOULDER,  # 6
    KEYPOINT_LEFT_HIP,        # 11
    KEYPOINT_RIGHT_HIP,       # 12
)
DEFAULT_MIN_VALID_FRAME_RATIO: float = 0.70
DEFAULT_MIN_AVG_COMPLETENESS: float = 0.50
DEFAULT_MAX_LONG_SIDE: int = 1280
DEFAULT_JPEG_QUALITY: int = 95
DEFAULT_BUFFER_SIZE: int = 10
DEFAULT_MAX_HOLD_TIME_SECONDS: float = 600.0
DEFAULT_MAX_TOTAL_SEQUENCES: int = 2000
DEFAULT_LOCAL_BASE_PATH: str = "extracted_data/pose/sequences"
DEFAULT_S3_PREFIX: str = "pose/sequences"
DEFAULT_S3_BUCKET: str = "courtview-learning"
DEFAULT_SIMILARITY_THRESHOLD: int = 3
DEFAULT_MAX_CACHE_SIZE: int = 1000

# pHash 내부 상수
_PHASH_RESIZE_DIM: int = 32
_PHASH_LOW_FREQ_DIM: int = 8

# 거부 사유 문자열
_REJECT_LENGTH_MISMATCH = "length_mismatch"
_REJECT_EMPTY_SEQUENCE = "empty_sequence"
_REJECT_TOO_FEW_FRAMES = "too_few_frames"
_REJECT_TOO_MANY_FRAMES = "too_many_frames"
_REJECT_INVALID_ACTION = "invalid_action_type"
_REJECT_INVALID_PHASES = "invalid_phase_range"
_REJECT_LOW_VALID_RATIO = "low_valid_frame_ratio"
_REJECT_LOW_AVG_COMPLETENESS = "low_avg_completeness"
_REJECT_DUPLICATE = "duplicate_sequence"

# COCO 키포인트 이름 (JSON용)
_COCO_KEYPOINT_NAMES: list[str] = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class PhaseSegment:
    """
    동작 단계 구간.

    시퀀스 내 특정 동작 페이즈의 시작/종료 프레임 인덱스.
    예: PhaseSegment("preparation", 0, 15) → 0~15번째 프레임이 준비 단계.
    """

    phase_name: str    # "preparation", "execution", "follow_through", "recovery"
    start_frame: int   # 시퀀스 내 시작 인덱스 (inclusive)
    end_frame: int     # 시퀀스 내 종료 인덱스 (inclusive)


@dataclass(frozen=True, slots=True)
class PoseSequenceConfig:
    """
    포즈 시퀀스 추출 설정 (Immutable).

    YAML configs/pose/data_extraction.yaml의 pose_sequence_extraction 섹션에서 로드.
    """

    # 활성화 여부
    enabled: bool = True

    # 시퀀스 설정
    min_frames: int = DEFAULT_MIN_FRAMES
    max_frames: int = DEFAULT_MAX_FRAMES
    valid_action_types: tuple[str, ...] = DEFAULT_VALID_ACTION_TYPES

    # 품질 필터
    keypoint_confidence_threshold: float = DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD
    min_visible_keypoints: int = DEFAULT_MIN_VISIBLE_KEYPOINTS
    min_skeleton_completeness: float = DEFAULT_MIN_SKELETON_COMPLETENESS
    critical_keypoint_indices: tuple[int, ...] = DEFAULT_CRITICAL_KEYPOINT_INDICES
    min_valid_frame_ratio: float = DEFAULT_MIN_VALID_FRAME_RATIO
    min_avg_completeness: float = DEFAULT_MIN_AVG_COMPLETENESS

    # 이미지 설정
    max_long_side: int = DEFAULT_MAX_LONG_SIDE
    jpeg_quality: int = DEFAULT_JPEG_QUALITY

    # 배치 처리
    buffer_size: int = DEFAULT_BUFFER_SIZE
    max_hold_time_seconds: float = DEFAULT_MAX_HOLD_TIME_SECONDS
    max_total_sequences: int = DEFAULT_MAX_TOTAL_SEQUENCES

    # 저장 설정
    local_base_path: str = DEFAULT_LOCAL_BASE_PATH
    s3_prefix: str = DEFAULT_S3_PREFIX
    s3_bucket: str = DEFAULT_S3_BUCKET

    # 중복 방지
    dedup_enabled: bool = True
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD
    max_cache_size: int = DEFAULT_MAX_CACHE_SIZE

    @classmethod
    def from_config(
        cls, config_loader: ConfigLoader | None = None
    ) -> "PoseSequenceConfig":
        """
        YAML 설정에서 Config 생성.

        Args:
            config_loader: ConfigLoader 인스턴스 (None이면 기본값)

        Returns:
            PoseSequenceConfig 인스턴스
        """
        if config_loader is None:
            return cls()

        prefix = CONFIG_KEY_POSE_SEQUENCE_EXTRACTION

        enabled = config_loader.get(f"{prefix}.enabled", True)

        # 시퀀스 설정
        seq = f"{prefix}.sequence"
        min_fr = config_loader.get(f"{seq}.min_frames", DEFAULT_MIN_FRAMES)
        max_fr = config_loader.get(f"{seq}.max_frames", DEFAULT_MAX_FRAMES)
        valid_raw = config_loader.get(
            f"{seq}.valid_action_types", list(DEFAULT_VALID_ACTION_TYPES)
        )
        valid_types = tuple(str(x) for x in valid_raw)

        # 품질 필터
        qf = f"{prefix}.quality_filter"
        kp_conf = config_loader.get(
            f"{qf}.keypoint_confidence_threshold",
            DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD,
        )
        min_vis = config_loader.get(
            f"{qf}.min_visible_keypoints", DEFAULT_MIN_VISIBLE_KEYPOINTS
        )
        min_comp = config_loader.get(
            f"{qf}.min_skeleton_completeness", DEFAULT_MIN_SKELETON_COMPLETENESS
        )
        critical_raw = config_loader.get(
            f"{qf}.critical_keypoint_indices",
            list(DEFAULT_CRITICAL_KEYPOINT_INDICES),
        )
        critical_indices = tuple(int(x) for x in critical_raw)
        min_vr = config_loader.get(
            f"{qf}.min_valid_frame_ratio", DEFAULT_MIN_VALID_FRAME_RATIO
        )
        min_ac = config_loader.get(
            f"{qf}.min_avg_completeness", DEFAULT_MIN_AVG_COMPLETENESS
        )

        # 이미지
        img = f"{prefix}.image"
        max_side = config_loader.get(f"{img}.max_long_side", DEFAULT_MAX_LONG_SIDE)
        jpeg_q = config_loader.get(f"{img}.jpeg_quality", DEFAULT_JPEG_QUALITY)

        # 배치
        bat = f"{prefix}.batch"
        buf_size = config_loader.get(f"{bat}.buffer_size", DEFAULT_BUFFER_SIZE)
        max_hold = config_loader.get(
            f"{bat}.max_hold_time_seconds", DEFAULT_MAX_HOLD_TIME_SECONDS
        )
        max_seq = config_loader.get(
            f"{bat}.max_total_sequences", DEFAULT_MAX_TOTAL_SEQUENCES
        )

        # 저장
        sto = f"{prefix}.storage"
        base_path = config_loader.get(
            f"{sto}.local_base_path", DEFAULT_LOCAL_BASE_PATH
        )
        s3_pre = config_loader.get(f"{sto}.s3_prefix", DEFAULT_S3_PREFIX)
        s3_bkt = config_loader.get(f"{sto}.s3_bucket", DEFAULT_S3_BUCKET)

        # 중복 제거
        ded = f"{prefix}.deduplication"
        ded_en = config_loader.get(f"{ded}.enabled", True)
        sim_th = config_loader.get(
            f"{ded}.similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
        )
        max_cache = config_loader.get(f"{ded}.max_cache_size", DEFAULT_MAX_CACHE_SIZE)

        return cls(
            enabled=bool(enabled),
            min_frames=int(min_fr),
            max_frames=int(max_fr),
            valid_action_types=valid_types,
            keypoint_confidence_threshold=float(kp_conf),
            min_visible_keypoints=int(min_vis),
            min_skeleton_completeness=float(min_comp),
            critical_keypoint_indices=critical_indices,
            min_valid_frame_ratio=float(min_vr),
            min_avg_completeness=float(min_ac),
            max_long_side=int(max_side),
            jpeg_quality=int(jpeg_q),
            buffer_size=int(buf_size),
            max_hold_time_seconds=float(max_hold),
            max_total_sequences=int(max_seq),
            local_base_path=str(base_path),
            s3_prefix=str(s3_pre),
            s3_bucket=str(s3_bkt),
            dedup_enabled=bool(ded_en),
            similarity_threshold=int(sim_th),
            max_cache_size=int(max_cache),
        )


@dataclass(slots=True)
class PoseSequenceSample:
    """
    단일 시퀀스 샘플.

    3단계 필터를 통과한 동작 시퀀스의 학습 데이터.
    N 프레임 JPEG + 시계열 keypoints.json + labels.json.
    """

    # 고유 ID (12자 hex)
    sequence_id: str = ""

    # 액션 타입
    action_type: str = ""

    # N 프레임 JPEG 바이트 리스트
    frame_jpegs: list[bytes] = field(default_factory=list)

    # keypoints.json 데이터
    keypoints_data: dict[str, object] = field(default_factory=dict)

    # labels.json 데이터
    labels_data: dict[str, object] = field(default_factory=dict)

    # 메타데이터
    frame_count: int = 0
    avg_completeness: float = 0.0

    # 대표 프레임 pHash
    representative_hash: str = ""


@dataclass(slots=True)
class PoseSequenceStats:
    """
    시퀀스 추출 통계.

    3단계 필터별 거부 카운터 + 액션 분포 + EWMA.
    """

    # 입력
    total_input_sequences: int = 0
    total_input_frames: int = 0

    # 시퀀스 레벨 거부
    rejected_length_mismatch: int = 0
    rejected_empty_sequence: int = 0
    rejected_too_few_frames: int = 0
    rejected_too_many_frames: int = 0
    rejected_invalid_action: int = 0
    rejected_invalid_phases: int = 0
    rejected_low_valid_ratio: int = 0
    rejected_low_avg_completeness: int = 0
    rejected_duplicate: int = 0

    # 프레임 레벨 통계
    total_valid_frames: int = 0
    total_invalid_frames: int = 0

    # 액션 타입 분포
    action_distribution: dict[str, int] = field(default_factory=dict)

    # 추출 성공
    total_extracted: int = 0
    total_frames_extracted: int = 0
    total_flushed: int = 0
    total_flush_count: int = 0

    # EWMA 완전성
    _ewma_completeness: float = 0.0
    _ewma_alpha: float = 0.02

    @property
    def pass_rate(self) -> float:
        """필터 통과율 (0.0~1.0)."""
        if self.total_input_sequences == 0:
            return 0.0
        return self.total_extracted / self.total_input_sequences

    @property
    def avg_completeness(self) -> float:
        """추출된 시퀀스의 평균 완전성 (EWMA)."""
        return self._ewma_completeness

    @property
    def total_rejected(self) -> int:
        """총 거부 수."""
        return (
            self.rejected_length_mismatch
            + self.rejected_empty_sequence
            + self.rejected_too_few_frames
            + self.rejected_too_many_frames
            + self.rejected_invalid_action
            + self.rejected_invalid_phases
            + self.rejected_low_valid_ratio
            + self.rejected_low_avg_completeness
            + self.rejected_duplicate
        )

    def update_completeness_ewma(self, completeness: float) -> None:
        """EWMA 완전성 업데이트."""
        if self._ewma_completeness == 0.0:
            self._ewma_completeness = completeness
        else:
            alpha = self._ewma_alpha
            self._ewma_completeness = (
                alpha * completeness + (1.0 - alpha) * self._ewma_completeness
            )

    def to_dict(self) -> dict[str, object]:
        """통계를 딕셔너리로 변환."""
        return {
            "total_input_sequences": self.total_input_sequences,
            "total_input_frames": self.total_input_frames,
            "total_extracted": self.total_extracted,
            "total_frames_extracted": self.total_frames_extracted,
            "total_flushed": self.total_flushed,
            "total_flush_count": self.total_flush_count,
            "pass_rate": round(self.pass_rate, 4),
            "avg_completeness": round(self.avg_completeness, 4),
            "rejections": {
                "length_mismatch": self.rejected_length_mismatch,
                "empty_sequence": self.rejected_empty_sequence,
                "too_few_frames": self.rejected_too_few_frames,
                "too_many_frames": self.rejected_too_many_frames,
                "invalid_action": self.rejected_invalid_action,
                "invalid_phases": self.rejected_invalid_phases,
                "low_valid_ratio": self.rejected_low_valid_ratio,
                "low_avg_completeness": self.rejected_low_avg_completeness,
                "duplicate": self.rejected_duplicate,
            },
            "frame_stats": {
                "total_valid": self.total_valid_frames,
                "total_invalid": self.total_invalid_frames,
            },
            "action_distribution": dict(self.action_distribution),
        }


@dataclass(slots=True)
class PoseSequenceMetadata:
    """
    시퀀스 추출 세션 메타데이터.

    finalize() 시 metadata.json으로 저장.
    """

    session_id: str = ""
    date: str = ""
    source_game_id: str = ""
    total_sequences: int = 0
    total_frames: int = 0
    avg_completeness: float = 0.0
    keypoint_format: str = "coco_17"
    config_snapshot: dict[str, object] = field(default_factory=dict)
    extraction_stats: dict[str, object] = field(default_factory=dict)
    output_directory: str = ""

    def to_dict(self) -> dict[str, object]:
        """메타데이터를 딕셔너리로 변환."""
        return {
            "session_id": self.session_id,
            "date": self.date,
            "source_game_id": self.source_game_id,
            "total_sequences": self.total_sequences,
            "total_frames": self.total_frames,
            "avg_completeness": round(self.avg_completeness, 4),
            "keypoint_format": self.keypoint_format,
            "num_keypoints": NUM_KEYPOINTS_COCO,
            "training_target": "LSTM/Transformer/ST-GCN",
            "config": self.config_snapshot,
            "stats": self.extraction_stats,
            "output_directory": self.output_directory,
        }


# =============================================================================
# 메인 클래스
# =============================================================================
class PoseSequenceExtractor:
    """
    포즈 시퀀스 데이터 추출기.

    LSTM/Transformer/ST-GCN 모델 학습용 동작 시퀀스를 자동 추출합니다.
    모션 분석에서 확정된 동작 시퀀스를 3단계 품질 필터로 선별하고,
    프레임 이미지 + 시계열 키포인트 + 액션/페이즈 라벨을 로컬에 저장합니다.

    사용법::

        extractor = PoseSequenceExtractor()
        extractor.initialize()

        for action in detected_actions:
            extractor.extract_sequence(
                frames=action.frames,
                keypoints_per_frame=action.keypoints,
                action_type="shooting",
                phases=[PhaseSegment("preparation", 0, 15), ...],
                success=True,
                quality_score=85.2,
            )

        result = extractor.finalize("game_001")

    3단계 품질 필터:
        Stage 1 (시퀀스): 길이 일치, min/max 프레임, 유효 액션 타입, phases 범위
        Stage 2 (프레임): 프레임별 키포인트 가시성, 필수 키포인트, 완전성
        Stage 3 (시퀀스 품질): 유효 프레임 비율, 평균 완전성, pHash 중복

    스레드 안전성:
        내부 Lock으로 extract_sequence/flush/finalize 동시 호출 보호.
    """

    def __init__(
        self,
        config: PoseSequenceConfig | None = None,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        """
        추출기 생성.

        실제 초기화는 initialize()에서 수행합니다.

        Args:
            config: 추출 설정 (None이면 initialize()에서 로드)
            metrics_collector: 메트릭 수집기 (DI, 선택적)
        """
        self._config: PoseSequenceConfig | None = config
        self._metrics_collector = metrics_collector
        self._initialized: bool = False

        # 상태
        self._stats: PoseSequenceStats = PoseSequenceStats()
        self._buffer: list[PoseSequenceSample] = []
        self._hash_cache: OrderedDict[str, bool] = OrderedDict()
        self._last_flush_time: float = 0.0
        self._session_id: str = ""
        self._output_dir: str = ""

        # 스레드 안전
        self._lock: threading.Lock = threading.Lock()

    # =========================================================================
    # 초기화/종료
    # =========================================================================
    def initialize(
        self,
        config: PoseSequenceConfig | None = None,
        config_loader: ConfigLoader | None = None,
    ) -> None:
        """
        추출기 초기화.

        설정 우선순위:
            1. 파라미터 config
            2. 생성자 config
            3. YAML (ConfigLoader)
            4. 기본값

        출력 디렉토리 구조::

            {local_base_path}/{YYYYMMDD}/{session_id}/

        시퀀스별 하위 디렉토리는 flush 시 동적 생성.

        Args:
            config: 추출 설정 (최우선)
            config_loader: YAML 설정 로더 (config 없을 때 사용)
        """
        with self._lock:
            # 설정 로드
            if config is not None:
                self._config = config
            elif self._config is None:
                self._config = PoseSequenceConfig.from_config(config_loader)

            # 세션 ID 생성 (16자 hex)
            self._session_id = uuid4().hex[:16]

            # 날짜 문자열
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

            # 출력 디렉토리 생성
            self._output_dir = os.path.join(
                self._config.local_base_path,
                date_str,
                self._session_id,
            )
            os.makedirs(self._output_dir, exist_ok=True)

            # 상태 초기화
            self._stats = PoseSequenceStats()
            self._buffer.clear()
            self._hash_cache.clear()
            self._last_flush_time = time.time()

            self._initialized = True

            logger.info(
                "PoseSequenceExtractor 초기화 완료 "
                "(session=%s, output=%s, enabled=%s)",
                self._session_id,
                self._output_dir,
                self._config.enabled,
            )

    def reset(self) -> None:
        """
        상태 초기화 (설정 유지, 데이터 리셋).

        버퍼, 통계, 해시 캐시를 초기화합니다.
        설정과 디렉토리는 유지됩니다.
        """
        with self._lock:
            self._stats = PoseSequenceStats()
            self._buffer.clear()
            self._hash_cache.clear()
            self._last_flush_time = time.time()

    # =========================================================================
    # Properties
    # =========================================================================
    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def stats(self) -> PoseSequenceStats:
        """현재 추출 통계."""
        return self._stats

    @property
    def current_buffer_size(self) -> int:
        """현재 버퍼에 축적된 시퀀스 수."""
        return len(self._buffer)

    @property
    def is_buffer_full(self) -> bool:
        """버퍼가 가득 찼는지 여부."""
        if self._config is None:
            return False
        return len(self._buffer) >= self._config.buffer_size

    @property
    def is_max_sequences_reached(self) -> bool:
        """세션 최대 시퀀스 수 도달 여부."""
        if self._config is None:
            return False
        return self._stats.total_extracted >= self._config.max_total_sequences

    @property
    def session_id(self) -> str:
        """현재 세션 ID."""
        return self._session_id

    @property
    def output_dir(self) -> str:
        """출력 디렉토리 경로."""
        return self._output_dir

    # =========================================================================
    # 메인 추출 메서드
    # =========================================================================
    def extract_sequence(
        self,
        frames: list[NDArray[np.uint8]],
        keypoints_per_frame: list[NDArray[np.float32]],
        action_type: str,
        phases: list[PhaseSegment] | None = None,
        success: bool | None = None,
        quality_score: float | None = None,
        player_id: str = "",
        start_frame_index: int = 0,
        start_timestamp_ms: float = 0.0,
    ) -> bool:
        """
        동작 시퀀스 추출 시도.

        3단계 품질 필터 → 프레임 리사이즈 + JPEG 인코딩 →
        pHash 중복 확인 → keypoints.json + labels.json 생성 →
        버퍼 추가 → 자동 flush.

        Args:
            frames: N 연속 프레임 (BGR, H×W×3)
            keypoints_per_frame: N × (17, 3) 단일 선수 키포인트
            action_type: 액션 타입 ("shooting", "dribbling", etc.)
            phases: 동작 단계 구간 (선택적)
            success: 동작 성공 여부 (선택적)
            quality_score: 동작 품질 점수 0~100 (선택적)
            player_id: 선수 식별자
            start_frame_index: 원본 영상 시작 프레임 번호
            start_timestamp_ms: 원본 영상 시작 타임스탬프 (ms)

        Returns:
            추출 성공 여부 (True = 버퍼에 추가됨)

        Raises:
            PoseEstimationException: 초기화되지 않은 상태에서 호출 시
        """
        if not self._initialized or self._config is None:
            raise PoseEstimationException(
                message="PoseSequenceExtractor가 초기화되지 않았습니다",
                error_code=ErrorCode.POSE_ESTIMATION_ERROR,
            )

        if not self._config.enabled:
            return False

        with self._lock:
            self._stats.total_input_sequences += 1
            self._stats.total_input_frames += len(frames) if frames else 0

            # 최대 시퀀스 수 확인
            if self._stats.total_extracted >= self._config.max_total_sequences:
                return False

            # Stage 1: 시퀀스 유효성 필터
            s1_pass, s1_reason = self._check_sequence_validity(
                frames, keypoints_per_frame, action_type, phases
            )
            if not s1_pass:
                self._increment_rejection(s1_reason)
                return False

            # Stage 2: 프레임별 키포인트 품질 평가
            valid_count = 0
            completeness_list: list[float] = []

            for kps in keypoints_per_frame:
                valid, comp = self._evaluate_frame_quality(kps)
                completeness_list.append(comp)
                if valid:
                    valid_count += 1

            self._stats.total_valid_frames += valid_count
            self._stats.total_invalid_frames += len(keypoints_per_frame) - valid_count

            # Stage 3: 시퀀스 레벨 품질
            s3_pass, s3_reason = self._check_sequence_quality(
                valid_count, len(keypoints_per_frame), completeness_list, frames
            )
            if not s3_pass:
                self._increment_rejection(s3_reason)
                return False

            # 프레임 리사이즈 + JPEG 인코딩
            frame_jpegs: list[bytes] = []
            for frame in frames:
                resized = self._resize_frame(frame)
                jpeg_data = self._encode_jpeg(resized)
                if jpeg_data is not None:
                    frame_jpegs.append(jpeg_data)
                else:
                    # 인코딩 실패 시 빈 바이트 (프레임 수 유지)
                    frame_jpegs.append(b"")

            # 평균 완전성
            avg_comp = (
                sum(completeness_list) / len(completeness_list)
                if completeness_list
                else 0.0
            )

            # keypoints.json 생성
            seq_id = uuid4().hex[:12]
            keypoints_data = self._generate_keypoints_json(
                keypoints_per_frame, seq_id, completeness_list
            )

            # labels.json 생성
            labels_data = self._generate_labels_json(
                seq_id, action_type, phases, success, quality_score,
                player_id, len(frames), start_frame_index, start_timestamp_ms,
            )

            # 대표 프레임 pHash 등록
            phash = ""
            if self._config.dedup_enabled:
                mid_idx = len(frames) // 2
                resized_mid = self._resize_frame(frames[mid_idx])
                phash = self._compute_phash(resized_mid)
                self._register_hash(phash)

            # Sample 생성
            sample = PoseSequenceSample(
                sequence_id=seq_id,
                action_type=action_type,
                frame_jpegs=frame_jpegs,
                keypoints_data=keypoints_data,
                labels_data=labels_data,
                frame_count=len(frames),
                avg_completeness=round(avg_comp, 4),
                representative_hash=phash,
            )

            self._buffer.append(sample)
            self._stats.total_extracted += 1
            self._stats.total_frames_extracted += len(frames)
            self._stats.update_completeness_ewma(avg_comp)

            # 액션 분포 업데이트
            if action_type in self._stats.action_distribution:
                self._stats.action_distribution[action_type] += 1
            else:
                self._stats.action_distribution[action_type] = 1

            # 메트릭 기록
            if self._metrics_collector is not None:
                try:
                    counter = self._metrics_collector.counter(
                        "pose_sequence_extraction_total",
                        help="총 추출된 시퀀스 수",
                    )
                    counter.increment()
                except Exception:
                    pass

            # 자동 flush 판정
            should_flush = (
                len(self._buffer) >= self._config.buffer_size
                or self._is_hold_time_exceeded()
            )
            if should_flush:
                self._flush_buffer_internal()

            return True

    # =========================================================================
    # Flush / Finalize
    # =========================================================================
    def flush(self) -> int:
        """
        버퍼의 시퀀스를 디스크에 기록.

        Returns:
            기록된 시퀀스 수
        """
        if not self._initialized:
            return 0

        with self._lock:
            return self._flush_buffer_internal()

    def finalize(self, source_game_id: str = "") -> ExtractionResult:
        """
        추출 세션 종료 및 결과 반환.

        잔여 버퍼 flush → 메타데이터 생성 → metadata.json 저장 →
        ExtractionResult 반환.

        Args:
            source_game_id: 소스 경기 ID

        Returns:
            ExtractionResult (shared/dto/dataset_dto.py)
        """
        if not self._initialized or self._config is None:
            return ExtractionResult(
                game_id=source_game_id,
                record_count=0,
                upload_status=UploadStatus.PENDING,
            )

        with self._lock:
            timer_start = time.time()

            # 잔여 버퍼 flush
            self._flush_buffer_internal()

            # 메타데이터 생성
            metadata_obj = self._create_metadata(source_game_id)

            # metadata.json 저장
            metadata_path = os.path.join(self._output_dir, "metadata.json")
            try:
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(
                        metadata_obj.to_dict(), f, ensure_ascii=False, indent=2
                    )
            except OSError as e:
                logger.error(
                    "메타데이터 저장 실패: %s (path=%s)", e, metadata_path
                )

            # 총 크기 계산
            total_size = self._calculate_directory_size(self._output_dir)
            processing_time_ms = (time.time() - timer_start) * 1000.0

            # DatasetMetadata 생성
            dataset_metadata = DatasetMetadata(
                dataset_type=DatasetType.POSE_SEQUENCE,
                version="1.0.0",
                total_records=self._stats.total_flushed,
                split=DatasetSplit.TRAIN,
                source_game_ids=[source_game_id] if source_game_id else [],
                description=(
                    f"Sequence extraction "
                    f"(session={self._session_id}, "
                    f"sequences={self._stats.total_flushed}, "
                    f"frames={self._stats.total_frames_extracted})"
                ),
            )

            # S3 키 생성
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            s3_key = (
                f"{self._config.s3_prefix}/{date_str}/{self._session_id}/"
            )

            # ExtractionResult 생성
            result = ExtractionResult(
                game_id=source_game_id,
                metadata=dataset_metadata,
                record_count=self._stats.total_flushed,
                file_path=self._output_dir,
                file_size_bytes=total_size,
                processing_time_ms=processing_time_ms,
                s3_bucket=self._config.s3_bucket,
                s3_key=s3_key,
                upload_status=UploadStatus.PENDING,
            )

            logger.info(
                "PoseSequenceExtractor 종료 "
                "(session=%s, total_flushed=%d, frames=%d, "
                "pass_rate=%.2f%%, avg_completeness=%.4f, size=%d bytes)",
                self._session_id,
                self._stats.total_flushed,
                self._stats.total_frames_extracted,
                self._stats.pass_rate * 100,
                self._stats.avg_completeness,
                total_size,
            )

            return result

    # =========================================================================
    # Stage 1: 시퀀스 유효성 필터
    # =========================================================================
    def _check_sequence_validity(
        self,
        frames: list[NDArray[np.uint8]],
        keypoints_per_frame: list[NDArray[np.float32]],
        action_type: str,
        phases: list[PhaseSegment] | None,
    ) -> tuple[bool, str]:
        """
        시퀀스 유효성 검사.

        Args:
            frames: 프레임 리스트
            keypoints_per_frame: 키포인트 리스트
            action_type: 액션 타입
            phases: 페이즈 구간 (선택적)

        Returns:
            (통과 여부, 거부 사유)
        """
        config = self._config
        if config is None:
            return False, "not_initialized"

        # 1a: frames/keypoints 길이 일치
        if len(frames) != len(keypoints_per_frame):
            return False, _REJECT_LENGTH_MISMATCH

        # 1b: 빈 시퀀스
        if len(frames) == 0:
            return False, _REJECT_EMPTY_SEQUENCE

        # 1c: 최소 프레임 수
        if len(frames) < config.min_frames:
            return False, _REJECT_TOO_FEW_FRAMES

        # 1d: 최대 프레임 수
        if len(frames) > config.max_frames:
            return False, _REJECT_TOO_MANY_FRAMES

        # 1e: 유효 액션 타입
        if action_type not in config.valid_action_types:
            return False, _REJECT_INVALID_ACTION

        # 1f: phases 유효성 (있으면)
        if phases:
            num_frames = len(frames)
            for ps in phases:
                if ps.start_frame < 0 or ps.end_frame >= num_frames:
                    return False, _REJECT_INVALID_PHASES
                if ps.start_frame > ps.end_frame:
                    return False, _REJECT_INVALID_PHASES

        return True, ""

    # =========================================================================
    # Stage 2: 프레임 레벨 키포인트 품질
    # =========================================================================
    def _evaluate_frame_quality(
        self,
        keypoints: NDArray[np.float32],
    ) -> tuple[bool, float]:
        """
        단일 프레임 키포인트 품질 평가.

        Args:
            keypoints: (17, 3) [x, y, confidence]

        Returns:
            (valid 여부, completeness)
        """
        if self._config is None:
            return False, 0.0

        kp_thresh = self._config.keypoint_confidence_threshold
        visible_count = int(np.sum(keypoints[:, 2] >= kp_thresh))
        completeness = visible_count / NUM_KEYPOINTS_COCO

        # 최소 가시 키포인트
        if visible_count < self._config.min_visible_keypoints:
            return False, completeness

        # 필수 키포인트 확인
        for idx in self._config.critical_keypoint_indices:
            if idx < len(keypoints) and keypoints[idx, 2] < kp_thresh:
                return False, completeness

        return True, completeness

    # =========================================================================
    # Stage 3: 시퀀스 레벨 품질
    # =========================================================================
    def _check_sequence_quality(
        self,
        valid_count: int,
        total_frames: int,
        completeness_list: list[float],
        frames: list[NDArray[np.uint8]],
    ) -> tuple[bool, str]:
        """
        시퀀스 레벨 품질 검사.

        Args:
            valid_count: 유효 프레임 수
            total_frames: 전체 프레임 수
            completeness_list: 프레임별 완전성 리스트
            frames: 프레임 리스트 (pHash용)

        Returns:
            (통과 여부, 거부 사유)
        """
        config = self._config
        if config is None:
            return False, "not_initialized"

        # 3a: 유효 프레임 비율
        if total_frames > 0:
            valid_ratio = valid_count / total_frames
            if valid_ratio < config.min_valid_frame_ratio:
                return False, _REJECT_LOW_VALID_RATIO

        # 3b: 평균 완전성
        if completeness_list:
            avg_comp = sum(completeness_list) / len(completeness_list)
            if avg_comp < config.min_avg_completeness:
                return False, _REJECT_LOW_AVG_COMPLETENESS

        # 3c: 대표 프레임 pHash 중복 확인
        if config.dedup_enabled and frames:
            mid_idx = len(frames) // 2
            resized_mid = self._resize_frame(frames[mid_idx])
            phash = self._compute_phash(resized_mid)
            if self._is_duplicate(phash):
                return False, _REJECT_DUPLICATE

        return True, ""

    # =========================================================================
    # 거부 카운터
    # =========================================================================
    def _increment_rejection(self, reason: str) -> None:
        """거부 사유별 카운터 증가."""
        if reason == _REJECT_LENGTH_MISMATCH:
            self._stats.rejected_length_mismatch += 1
        elif reason == _REJECT_EMPTY_SEQUENCE:
            self._stats.rejected_empty_sequence += 1
        elif reason == _REJECT_TOO_FEW_FRAMES:
            self._stats.rejected_too_few_frames += 1
        elif reason == _REJECT_TOO_MANY_FRAMES:
            self._stats.rejected_too_many_frames += 1
        elif reason == _REJECT_INVALID_ACTION:
            self._stats.rejected_invalid_action += 1
        elif reason == _REJECT_INVALID_PHASES:
            self._stats.rejected_invalid_phases += 1
        elif reason == _REJECT_LOW_VALID_RATIO:
            self._stats.rejected_low_valid_ratio += 1
        elif reason == _REJECT_LOW_AVG_COMPLETENESS:
            self._stats.rejected_low_avg_completeness += 1
        elif reason == _REJECT_DUPLICATE:
            self._stats.rejected_duplicate += 1

    # =========================================================================
    # JSON 생성
    # =========================================================================
    def _generate_keypoints_json(
        self,
        keypoints_per_frame: list[NDArray[np.float32]],
        sequence_id: str,
        completeness_list: list[float],
    ) -> dict[str, object]:
        """
        keypoints.json 데이터 생성.

        Args:
            keypoints_per_frame: N × (17, 3) 키포인트
            sequence_id: 시퀀스 ID
            completeness_list: 프레임별 완전성

        Returns:
            keypoints.json 딕셔너리
        """
        if self._config is None:
            return {}

        kp_thresh = self._config.keypoint_confidence_threshold
        frames_data: list[dict[str, object]] = []

        for fi, kps in enumerate(keypoints_per_frame):
            kp_list: list[dict[str, object]] = []
            visible_count = 0

            for ki in range(NUM_KEYPOINTS_COCO):
                if ki < len(kps):
                    conf = float(kps[ki, 2])
                    vis = 2 if conf >= kp_thresh else 0
                    if vis == 2:
                        visible_count += 1
                    kp_list.append({
                        "index": ki,
                        "name": (
                            _COCO_KEYPOINT_NAMES[ki]
                            if ki < len(_COCO_KEYPOINT_NAMES)
                            else f"kp_{ki}"
                        ),
                        "x": round(float(kps[ki, 0]), 2),
                        "y": round(float(kps[ki, 1]), 2),
                        "confidence": round(conf, 4),
                        "visibility": vis,
                    })
                else:
                    kp_list.append({
                        "index": ki,
                        "name": (
                            _COCO_KEYPOINT_NAMES[ki]
                            if ki < len(_COCO_KEYPOINT_NAMES)
                            else f"kp_{ki}"
                        ),
                        "x": 0.0,
                        "y": 0.0,
                        "confidence": 0.0,
                        "visibility": 0,
                    })

            comp = completeness_list[fi] if fi < len(completeness_list) else 0.0

            frames_data.append({
                "frame_offset": fi,
                "keypoints": kp_list,
                "visible_count": visible_count,
                "completeness": round(comp, 4),
            })

        return {
            "sequence_id": sequence_id,
            "num_frames": len(keypoints_per_frame),
            "keypoint_format": "coco_17",
            "frames": frames_data,
        }

    def _generate_labels_json(
        self,
        sequence_id: str,
        action_type: str,
        phases: list[PhaseSegment] | None,
        success: bool | None,
        quality_score: float | None,
        player_id: str,
        total_frames: int,
        start_frame_index: int,
        start_timestamp_ms: float,
    ) -> dict[str, object]:
        """
        labels.json 데이터 생성.

        Args:
            sequence_id: 시퀀스 ID
            action_type: 액션 타입
            phases: 페이즈 구간
            success: 성공 여부
            quality_score: 품질 점수
            player_id: 선수 ID
            total_frames: 총 프레임 수
            start_frame_index: 원본 시작 프레임
            start_timestamp_ms: 원본 시작 타임스탬프

        Returns:
            labels.json 딕셔너리
        """
        phases_data: list[dict[str, object]] = []
        if phases:
            for ps in phases:
                phases_data.append({
                    "phase": ps.phase_name,
                    "frames": [ps.start_frame, ps.end_frame],
                })

        result: dict[str, object] = {
            "sequence_id": sequence_id,
            "action": action_type,
            "phases": phases_data,
            "total_frames": total_frames,
            "start_frame_index": start_frame_index,
            "start_timestamp_ms": round(start_timestamp_ms, 2),
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if success is not None:
            result["success"] = success
        if quality_score is not None:
            result["score"] = round(quality_score, 2)
        if player_id:
            result["player_id"] = player_id

        return result

    # =========================================================================
    # 이미지 처리
    # =========================================================================
    def _resize_frame(self, frame: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """
        프레임 리사이즈 (긴 변 기준).

        Args:
            frame: 원본 프레임

        Returns:
            리사이즈된 프레임
        """
        if self._config is None:
            return frame.copy()

        h, w = frame.shape[:2]
        max_side = self._config.max_long_side

        if max(h, w) <= max_side:
            return frame.copy()

        scale = max_side / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)

        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _encode_jpeg(self, frame: NDArray[np.uint8]) -> bytes | None:
        """
        프레임을 JPEG 바이트로 인코딩.

        Args:
            frame: BGR 프레임

        Returns:
            JPEG 바이트 또는 None (실패 시)
        """
        if self._config is None:
            return None

        try:
            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._config.jpeg_quality]
            success, encoded = cv2.imencode(".jpg", frame, encode_params)
            if success:
                return encoded.tobytes()
            return None
        except Exception as e:
            logger.warning("JPEG 인코딩 실패: %s", e)
            return None

    # =========================================================================
    # pHash 중복 방지
    # =========================================================================
    def _compute_phash(self, frame: NDArray[np.uint8]) -> str:
        """프레임의 64비트 pHash 계산 — utils.image_utils 위임."""
        try:
            from utils.image_utils import compute_phash
            hash_int = compute_phash(frame, hash_size=_PHASH_LOW_FREQ_DIM)
            return f"{hash_int:016x}"
        except Exception as e:
            logger.warning("pHash 계산 실패: %s", e)
            return uuid4().hex[:16]

    def _is_duplicate(self, phash: str) -> bool:
        """
        pHash 기반 중복 확인.

        Args:
            phash: 16자 hex 해시

        Returns:
            중복 여부
        """
        if self._config is None:
            return False

        threshold = self._config.similarity_threshold

        try:
            hash_int = int(phash, 16)
        except ValueError:
            return False

        for cached_hex in self._hash_cache:
            try:
                cached_int = int(cached_hex, 16)
            except ValueError:
                continue

            xor_val = hash_int ^ cached_int
            hamming = bin(xor_val).count("1")

            if hamming <= threshold:
                return True

        return False

    def _register_hash(self, phash: str) -> None:
        """
        pHash를 캐시에 등록 (LRU).

        Args:
            phash: 16자 hex 해시
        """
        if self._config is None:
            return

        self._hash_cache[phash] = True

        while len(self._hash_cache) > self._config.max_cache_size:
            self._hash_cache.popitem(last=False)

    # =========================================================================
    # 내부 Flush
    # =========================================================================
    def _flush_buffer_internal(self) -> int:
        """
        버퍼를 디스크에 기록 (Lock 내부 호출).

        시퀀스별 디렉토리 구조:
            {output_dir}/{action}_sequences/seq_{id}/
            ├── frames/000000.jpg ~ 000N.jpg
            ├── keypoints.json
            └── labels.json

        Returns:
            기록된 시퀀스 수
        """
        if not self._buffer:
            return 0

        flushed = 0

        for sample in self._buffer:
            try:
                # 시퀀스 디렉토리 생성
                action_dir = f"{sample.action_type}_sequences"
                seq_dir = os.path.join(
                    self._output_dir, action_dir, f"seq_{sample.sequence_id}"
                )
                frames_dir = os.path.join(seq_dir, "frames")
                os.makedirs(frames_dir, exist_ok=True)

                # 프레임 이미지: frames/000000.jpg ~ 000N.jpg
                for i, jpeg_data in enumerate(sample.frame_jpegs):
                    if jpeg_data:
                        frame_path = os.path.join(frames_dir, f"{i:06d}.jpg")
                        with open(frame_path, "wb") as f:
                            f.write(jpeg_data)

                # keypoints.json
                kp_path = os.path.join(seq_dir, "keypoints.json")
                with open(kp_path, "w", encoding="utf-8") as f:
                    json.dump(
                        sample.keypoints_data, f, ensure_ascii=False, indent=2
                    )

                # labels.json
                labels_path = os.path.join(seq_dir, "labels.json")
                with open(labels_path, "w", encoding="utf-8") as f:
                    json.dump(
                        sample.labels_data, f, ensure_ascii=False, indent=2
                    )

                flushed += 1

            except OSError as e:
                logger.error(
                    "시퀀스 기록 실패 (seq=%s): %s",
                    sample.sequence_id, e
                )

        self._buffer.clear()
        self._stats.total_flushed += flushed
        self._stats.total_flush_count += 1
        self._last_flush_time = time.time()

        if flushed > 0:
            logger.debug(
                "Flush 완료: %d 시퀀스 기록 (총 %d)",
                flushed,
                self._stats.total_flushed,
            )

        return flushed

    def _is_hold_time_exceeded(self) -> bool:
        """버퍼 최대 보유 시간 초과 여부."""
        if self._config is None or self._last_flush_time == 0.0:
            return False
        elapsed = time.time() - self._last_flush_time
        return elapsed >= self._config.max_hold_time_seconds

    # =========================================================================
    # 메타데이터 생성
    # =========================================================================
    def _create_metadata(self, source_game_id: str) -> PoseSequenceMetadata:
        """
        추출 세션 메타데이터 생성.

        Args:
            source_game_id: 소스 경기 ID

        Returns:
            PoseSequenceMetadata
        """
        config = self._config
        config_dict: dict[str, object] = {}
        if config is not None:
            config_dict = {
                "min_frames": config.min_frames,
                "max_frames": config.max_frames,
                "valid_action_types": list(config.valid_action_types),
                "keypoint_confidence_threshold": config.keypoint_confidence_threshold,
                "min_visible_keypoints": config.min_visible_keypoints,
                "min_skeleton_completeness": config.min_skeleton_completeness,
                "critical_keypoint_indices": list(config.critical_keypoint_indices),
                "min_valid_frame_ratio": config.min_valid_frame_ratio,
                "min_avg_completeness": config.min_avg_completeness,
                "max_long_side": config.max_long_side,
                "jpeg_quality": config.jpeg_quality,
                "buffer_size": config.buffer_size,
                "max_total_sequences": config.max_total_sequences,
                "dedup_enabled": config.dedup_enabled,
                "similarity_threshold": config.similarity_threshold,
            }

        return PoseSequenceMetadata(
            session_id=self._session_id,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source_game_id=source_game_id,
            total_sequences=self._stats.total_flushed,
            total_frames=self._stats.total_frames_extracted,
            avg_completeness=self._stats.avg_completeness,
            keypoint_format="coco_17",
            config_snapshot=config_dict,
            extraction_stats=self._stats.to_dict(),
            output_directory=self._output_dir,
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================
    @staticmethod
    def _calculate_directory_size(directory: str) -> int:
        """
        디렉토리 총 크기 계산 (바이트).

        Args:
            directory: 디렉토리 경로

        Returns:
            총 바이트 수
        """
        total = 0
        try:
            for dirpath, _dirnames, filenames in os.walk(directory):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        total += os.path.getsize(fpath)
                    except OSError:
                        pass
        except OSError:
            pass
        return total


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "CONFIG_KEY_POSE_SEQUENCE_EXTRACTION",
    "PhaseSegment",
    "PoseSequenceConfig",
    "PoseSequenceSample",
    "PoseSequenceStats",
    "PoseSequenceMetadata",
    "PoseSequenceExtractor",
]

__version__ = "1.0.0"
