# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation/data_extraction
파일: wholebody_keypoint_extractor.py
설명: WholeBody 133 키포인트 데이터 추출기
      - COCO-WholeBody 133-keypoint 데이터셋 자동 추출
      - ViTPose-WholeBody / DWPose 모델 재학습용
      - 5개 서브 리전 (Body/Foot/Face/LeftHand/RightHand) 완전성 추적
      - 3단계 품질 필터 (프레임/인물/프레임집계) + Body 서브 리전 필터
      - 풀프레임 이미지 + YOLO Keypoint .txt 라벨 (133kp) + JSON 상세 어노테이션
      - pHash 기반 프레임 중복 방지
      - 배치 버퍼링 → 디스크 기록 → ExtractionResult 반환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

데이터 흐름:
    PlayerDetector.detect() → list[PlayerDetection] +
    WholeBodyEstimator.estimate() → List[NDArray(133,3)] →
    WholeBodyKeypointExtractor.extract_from_frame(detections, frame, keypoints_per_person) →
    3단계 필터 (+ Body 서브 리전 필터) → 프레임 리사이즈 + 키포인트 스케일링 →
    pHash 중복 확인 → JPEG 인코딩 →
    YOLO Keypoint 라벨 생성 (133kp) + JSON 어노테이션 (서브 리전 포함) → 버퍼 축적 →
    flush() → images/*.jpg + labels/*.txt + annotations/*.json →
    finalize() → metadata.json + ExtractionResult

COCO-WholeBody 133 키포인트 레이아웃:
    Body(0-16): 17개 — COCO-17 동일 (코, 눈, 귀, 어깨, 팔꿈치, 손목, 엉덩이, 무릎, 발목)
    Foot(17-22): 6개 — left_big_toe, left_small_toe, left_heel, right_big_toe, right_small_toe, right_heel
    Face(23-90): 68개 — dlib 68-point 얼굴 랜드마크
    LeftHand(91-111): 21개 — wrist + 5손가락 × 4관절
    RightHand(112-132): 21개 — wrist + 5손가락 × 4관절

참조:
    - detection/player_detection/models.py: PlayerDetection, BoundingBox, PlayerRole
    - shared/dto/dataset_dto.py: DatasetType.WHOLEBODY_KEYPOINT, ExtractionResult
    - shared/constants/pose_constants.py: NUM_KEYPOINTS_WHOLEBODY, KEYPOINT_* 인덱스
    - configs/pose/data_extraction.yaml: wholebody_extraction 섹션
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
# Direct Import (Layer 1 ~ Layer 2 내부)
# =============================================================================
from shared.interfaces.detector_interface import (
    BoundingBox,
    PlayerDetection,
    PlayerRole,
)
from shared.constants.error_codes import ErrorCode
from shared.constants.pose_constants import (
    JOINT_CONFIDENCE_THRESHOLD,
    KEYPOINT_LEFT_HIP,
    KEYPOINT_LEFT_SHOULDER,
    KEYPOINT_LEFT_WRIST,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_RIGHT_SHOULDER,
    KEYPOINT_RIGHT_WRIST,
    NUM_KEYPOINTS_WHOLEBODY,
    SKELETON_COMPLETENESS_THRESHOLD,
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
CONFIG_KEY_WHOLEBODY_EXTRACTION = "data_extraction.wholebody_extraction"

# 기본값 (YAML 미로드 시 폴백)
_DEFAULT_MIN_DETECTIONS: int = 1
_DEFAULT_MIN_DETECTION_CONFIDENCE: float = 0.70
_DEFAULT_MIN_BBOX_PIXELS: int = 400
_DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD: float = JOINT_CONFIDENCE_THRESHOLD  # 0.5
_DEFAULT_MIN_VISIBLE_KEYPOINTS: int = 40       # ~30% of 133
_DEFAULT_MIN_SKELETON_COMPLETENESS: float = 0.30
_DEFAULT_CRITICAL_KEYPOINT_INDICES: list[int] = [
    KEYPOINT_LEFT_SHOULDER,   # 5
    KEYPOINT_RIGHT_SHOULDER,  # 6
    KEYPOINT_LEFT_WRIST,      # 9
    KEYPOINT_RIGHT_WRIST,     # 10
    KEYPOINT_LEFT_HIP,        # 11
    KEYPOINT_RIGHT_HIP,       # 12
]
_DEFAULT_MIN_QUALIFYING_PERSONS: int = 1

# 서브 리전 필터 기본값
_DEFAULT_MIN_BODY_COMPLETENESS: float = 0.60
_DEFAULT_MIN_HAND_COMPLETENESS: float = 0.0
_DEFAULT_MIN_FOOT_COMPLETENESS: float = 0.0
_DEFAULT_MIN_FACE_COMPLETENESS: float = 0.0

# 이미지 / 배치 / 저장 / 중복
_DEFAULT_MAX_LONG_SIDE: int = 1280
_DEFAULT_JPEG_QUALITY: int = 95
_DEFAULT_BUFFER_SIZE: int = 30
_DEFAULT_MAX_HOLD_TIME_SECONDS: float = 600.0
_DEFAULT_MAX_TOTAL_SAMPLES: int = 3000
_DEFAULT_LOCAL_BASE_PATH: str = "extracted_data/pose/wholebody_keypoints"
_DEFAULT_S3_PREFIX: str = "pose/wholebody_keypoints"
_DEFAULT_S3_BUCKET: str = "courtview-learning"
_DEFAULT_SIMILARITY_THRESHOLD: int = 5
_DEFAULT_MAX_CACHE_SIZE: int = 2000

# pHash 내부 상수
_PHASH_RESIZE_DIM: int = 32
_PHASH_LOW_FREQ_DIM: int = 8
_PHASH_BIT_COUNT: int = _PHASH_LOW_FREQ_DIM * _PHASH_LOW_FREQ_DIM  # 64비트

# 서브 리전 인덱스 범위 (start inclusive, end exclusive)
_BODY_RANGE: tuple[int, int] = (0, 17)       # Body: 0~16 (17개)
_FOOT_RANGE: tuple[int, int] = (17, 23)      # Foot: 17~22 (6개)
_FACE_RANGE: tuple[int, int] = (23, 91)      # Face: 23~90 (68개)
_LEFT_HAND_RANGE: tuple[int, int] = (91, 112)   # LeftHand: 91~111 (21개)
_RIGHT_HAND_RANGE: tuple[int, int] = (112, 133)  # RightHand: 112~132 (21개)

# 서브 리전 정보 (이름, 시작, 끝, 개수)
_SUBREGION_DEFINITIONS: list[tuple[str, int, int]] = [
    ("body", _BODY_RANGE[0], _BODY_RANGE[1]),
    ("foot", _FOOT_RANGE[0], _FOOT_RANGE[1]),
    ("face", _FACE_RANGE[0], _FACE_RANGE[1]),
    ("left_hand", _LEFT_HAND_RANGE[0], _LEFT_HAND_RANGE[1]),
    ("right_hand", _RIGHT_HAND_RANGE[0], _RIGHT_HAND_RANGE[1]),
]

# 거부 사유 문자열
_REJECT_EMPTY_FRAME = "empty_frame"
_REJECT_TOO_FEW_DETECTIONS = "too_few_detections"
_REJECT_KEYPOINTS_MISMATCH = "keypoints_mismatch"
_REJECT_NOT_PLAYER = "not_player"
_REJECT_LOW_CONFIDENCE = "low_confidence"
_REJECT_BAD_BBOX_SIZE = "bad_bbox_size"
_REJECT_INSUFFICIENT_KEYPOINTS = "insufficient_keypoints"
_REJECT_MISSING_CRITICAL = "missing_critical_keypoint"
_REJECT_LOW_COMPLETENESS = "low_completeness"
_REJECT_LOW_BODY_COMPLETENESS = "low_body_completeness"
_REJECT_FEW_QUALIFYING = "few_qualifying_persons"
_REJECT_DUPLICATE = "duplicate_frame"

# COCO-WholeBody 133 키포인트 이름 (JSON 어노테이션용)
_WHOLEBODY_KEYPOINT_NAMES: list[str] = [
    # Body (0-16): COCO-17
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    # Foot (17-22)
    "left_big_toe", "left_small_toe", "left_heel",
    "right_big_toe", "right_small_toe", "right_heel",
    # Face (23-90): 68개 dlib 랜드마크
    *[f"face_{i}" for i in range(68)],
    # Left Hand (91-111): 21개
    "left_hand_wrist",
    *[f"left_hand_{f}_{j}" for f in ["thumb", "index", "middle", "ring", "pinky"] for j in range(1, 5)],
    # Right Hand (112-132): 21개
    "right_hand_wrist",
    *[f"right_hand_{f}_{j}" for f in ["thumb", "index", "middle", "ring", "pinky"] for j in range(1, 5)],
]

# 품질 등급 임계값 (133kp 기준)
_QUALITY_EXCELLENT_THRESHOLD: int = 120  # >= 120/133
_QUALITY_GOOD_THRESHOLD: int = 80        # >= 80/133


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass(frozen=True, slots=True)
class WholeBodyExtractionConfig:
    """
    WholeBody 133 키포인트 데이터 추출 설정 (Immutable).

    YAML configs/pose/data_extraction.yaml의 wholebody_extraction 섹션에서 로드.
    """

    # 활성화 여부
    enabled: bool = True

    # 3단계 품질 필터
    min_detections: int = _DEFAULT_MIN_DETECTIONS
    min_detection_confidence: float = _DEFAULT_MIN_DETECTION_CONFIDENCE
    min_bbox_pixels: int = _DEFAULT_MIN_BBOX_PIXELS
    keypoint_confidence_threshold: float = _DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD
    min_visible_keypoints: int = _DEFAULT_MIN_VISIBLE_KEYPOINTS
    min_skeleton_completeness: float = _DEFAULT_MIN_SKELETON_COMPLETENESS
    critical_keypoint_indices: tuple[int, ...] = (
        KEYPOINT_LEFT_SHOULDER,    # 5
        KEYPOINT_RIGHT_SHOULDER,   # 6
        KEYPOINT_LEFT_WRIST,       # 9
        KEYPOINT_RIGHT_WRIST,      # 10
        KEYPOINT_LEFT_HIP,         # 11
        KEYPOINT_RIGHT_HIP,        # 12
    )
    min_qualifying_persons: int = _DEFAULT_MIN_QUALIFYING_PERSONS

    # 서브 리전 필터
    min_body_completeness: float = _DEFAULT_MIN_BODY_COMPLETENESS
    min_hand_completeness: float = _DEFAULT_MIN_HAND_COMPLETENESS
    min_foot_completeness: float = _DEFAULT_MIN_FOOT_COMPLETENESS
    min_face_completeness: float = _DEFAULT_MIN_FACE_COMPLETENESS

    # 이미지 설정
    max_long_side: int = _DEFAULT_MAX_LONG_SIDE
    jpeg_quality: int = _DEFAULT_JPEG_QUALITY

    # 배치 처리
    buffer_size: int = _DEFAULT_BUFFER_SIZE
    max_hold_time_seconds: float = _DEFAULT_MAX_HOLD_TIME_SECONDS
    max_total_samples: int = _DEFAULT_MAX_TOTAL_SAMPLES

    # 저장 설정
    local_base_path: str = _DEFAULT_LOCAL_BASE_PATH
    s3_prefix: str = _DEFAULT_S3_PREFIX
    s3_bucket: str = _DEFAULT_S3_BUCKET

    # 중복 방지
    dedup_enabled: bool = True
    similarity_threshold: int = _DEFAULT_SIMILARITY_THRESHOLD
    max_cache_size: int = _DEFAULT_MAX_CACHE_SIZE

    @classmethod
    def from_config(
        cls, config_loader: ConfigLoader | None = None
    ) -> "WholeBodyExtractionConfig":
        """
        YAML 설정에서 Config 생성.

        Args:
            config_loader: ConfigLoader 인스턴스 (None이면 기본값)

        Returns:
            WholeBodyExtractionConfig 인스턴스
        """
        if config_loader is None:
            return cls()

        prefix = CONFIG_KEY_WHOLEBODY_EXTRACTION

        enabled = config_loader.get(f"{prefix}.enabled", True)

        # 품질 필터
        qf = f"{prefix}.quality_filter"
        min_det = config_loader.get(f"{qf}.min_detections", _DEFAULT_MIN_DETECTIONS)
        min_det_conf = config_loader.get(
            f"{qf}.min_detection_confidence", _DEFAULT_MIN_DETECTION_CONFIDENCE
        )
        min_px = config_loader.get(f"{qf}.min_bbox_pixels", _DEFAULT_MIN_BBOX_PIXELS)
        kp_conf = config_loader.get(
            f"{qf}.keypoint_confidence_threshold", _DEFAULT_KEYPOINT_CONFIDENCE_THRESHOLD
        )
        min_vis = config_loader.get(
            f"{qf}.min_visible_keypoints", _DEFAULT_MIN_VISIBLE_KEYPOINTS
        )
        min_comp = config_loader.get(
            f"{qf}.min_skeleton_completeness", _DEFAULT_MIN_SKELETON_COMPLETENESS
        )
        critical_raw = config_loader.get(
            f"{qf}.critical_keypoint_indices", _DEFAULT_CRITICAL_KEYPOINT_INDICES
        )
        critical_indices = tuple(int(x) for x in critical_raw)
        min_qual = config_loader.get(
            f"{qf}.min_qualifying_persons", _DEFAULT_MIN_QUALIFYING_PERSONS
        )

        # 서브 리전 필터
        sf = f"{prefix}.subregion_filter"
        min_body = config_loader.get(
            f"{sf}.min_body_completeness", _DEFAULT_MIN_BODY_COMPLETENESS
        )
        min_hand = config_loader.get(
            f"{sf}.min_hand_completeness", _DEFAULT_MIN_HAND_COMPLETENESS
        )
        min_foot = config_loader.get(
            f"{sf}.min_foot_completeness", _DEFAULT_MIN_FOOT_COMPLETENESS
        )
        min_face = config_loader.get(
            f"{sf}.min_face_completeness", _DEFAULT_MIN_FACE_COMPLETENESS
        )

        # 이미지
        img = f"{prefix}.image"
        max_side = config_loader.get(f"{img}.max_long_side", _DEFAULT_MAX_LONG_SIDE)
        jpeg_q = config_loader.get(f"{img}.jpeg_quality", _DEFAULT_JPEG_QUALITY)

        # 배치
        bat = f"{prefix}.batch"
        buf_size = config_loader.get(f"{bat}.buffer_size", _DEFAULT_BUFFER_SIZE)
        max_hold = config_loader.get(
            f"{bat}.max_hold_time_seconds", _DEFAULT_MAX_HOLD_TIME_SECONDS
        )
        max_samples = config_loader.get(
            f"{bat}.max_total_samples", _DEFAULT_MAX_TOTAL_SAMPLES
        )

        # 저장
        sto = f"{prefix}.storage"
        base_path = config_loader.get(f"{sto}.local_base_path", _DEFAULT_LOCAL_BASE_PATH)
        s3_pre = config_loader.get(f"{sto}.s3_prefix", _DEFAULT_S3_PREFIX)
        s3_bkt = config_loader.get(f"{sto}.s3_bucket", _DEFAULT_S3_BUCKET)

        # 중복 제거
        ded = f"{prefix}.deduplication"
        ded_en = config_loader.get(f"{ded}.enabled", True)
        sim_th = config_loader.get(
            f"{ded}.similarity_threshold", _DEFAULT_SIMILARITY_THRESHOLD
        )
        max_cache = config_loader.get(f"{ded}.max_cache_size", _DEFAULT_MAX_CACHE_SIZE)

        return cls(
            enabled=bool(enabled),
            min_detections=int(min_det),
            min_detection_confidence=float(min_det_conf),
            min_bbox_pixels=int(min_px),
            keypoint_confidence_threshold=float(kp_conf),
            min_visible_keypoints=int(min_vis),
            min_skeleton_completeness=float(min_comp),
            critical_keypoint_indices=critical_indices,
            min_qualifying_persons=int(min_qual),
            min_body_completeness=float(min_body),
            min_hand_completeness=float(min_hand),
            min_foot_completeness=float(min_foot),
            min_face_completeness=float(min_face),
            max_long_side=int(max_side),
            jpeg_quality=int(jpeg_q),
            buffer_size=int(buf_size),
            max_hold_time_seconds=float(max_hold),
            max_total_samples=int(max_samples),
            local_base_path=str(base_path),
            s3_prefix=str(s3_pre),
            s3_bucket=str(s3_bkt),
            dedup_enabled=bool(ded_en),
            similarity_threshold=int(sim_th),
            max_cache_size=int(max_cache),
        )


@dataclass(slots=True)
class WholeBodyExtractionSample:
    """
    단일 추출 샘플.

    3단계 필터를 통과한 프레임에서 생성된 WholeBody 133kp 학습 데이터.
    풀프레임 이미지(JPEG) + YOLO Keypoint 라벨(.txt, 133kp) + JSON 상세 어노테이션.
    """

    # 고유 ID (12자 hex)
    sample_id: str = ""

    # JPEG 이미지 바이트 (리사이즈된 풀프레임)
    image_data: bytes = b""

    # YOLO Keypoint format 라벨 문자열 (한 줄 = 한 사람, 133kp)
    yolo_label: str = ""

    # JSON 어노테이션 딕셔너리 (서브 리전 완전성 포함)
    annotation_data: dict[str, object] = field(default_factory=dict)

    # 메타데이터
    frame_index: int = 0
    timestamp_ms: float = 0.0
    person_count: int = 0
    avg_completeness: float = 0.0

    # 중복 방지
    image_hash: str = ""


@dataclass(slots=True)
class WholeBodyExtractionStats:
    """
    추출 통계.

    3단계 필터별 통과/거부 카운터 + 서브 리전 EWMA + 품질 분포.
    """

    # 입력 프레임 수
    total_input_frames: int = 0
    total_persons_seen: int = 0

    # 프레임 레벨 거부
    rejected_empty_frame: int = 0
    rejected_too_few_detections: int = 0
    rejected_keypoints_mismatch: int = 0
    rejected_few_qualifying: int = 0
    rejected_duplicate_frame: int = 0

    # 인물 레벨 거부
    rejected_not_player: int = 0
    rejected_low_confidence: int = 0
    rejected_bad_bbox_size: int = 0
    rejected_insufficient_keypoints: int = 0
    rejected_missing_critical: int = 0
    rejected_low_completeness: int = 0
    rejected_low_body_completeness: int = 0  # WholeBody 전용

    # 품질 등급 분포 (133kp 기준)
    quality_excellent: int = 0    # >= 120/133
    quality_good: int = 0         # >= 80/133
    quality_fair: int = 0         # >= 40/133

    # 추출 성공
    total_extracted: int = 0
    total_persons_extracted: int = 0
    total_flushed: int = 0
    total_flush_count: int = 0

    # EWMA 완전성 (전체 + 서브 리전)
    _ewma_completeness: float = 0.0
    _ewma_body_completeness: float = 0.0
    _ewma_hand_completeness: float = 0.0
    _ewma_foot_completeness: float = 0.0
    _ewma_face_completeness: float = 0.0
    _ewma_alpha: float = 0.02

    @property
    def pass_rate(self) -> float:
        """필터 통과율 (0.0~1.0)."""
        if self.total_input_frames == 0:
            return 0.0
        return self.total_extracted / self.total_input_frames

    @property
    def avg_completeness(self) -> float:
        """추출된 샘플의 평균 완전성 (EWMA)."""
        return self._ewma_completeness

    @property
    def avg_body_completeness(self) -> float:
        """Body 서브 리전 평균 완전성 (EWMA)."""
        return self._ewma_body_completeness

    @property
    def avg_hand_completeness(self) -> float:
        """Hand 서브 리전 평균 완전성 (EWMA)."""
        return self._ewma_hand_completeness

    @property
    def avg_foot_completeness(self) -> float:
        """Foot 서브 리전 평균 완전성 (EWMA)."""
        return self._ewma_foot_completeness

    @property
    def avg_face_completeness(self) -> float:
        """Face 서브 리전 평균 완전성 (EWMA)."""
        return self._ewma_face_completeness

    @property
    def total_rejected_frames(self) -> int:
        """프레임 레벨 총 거부 수."""
        return (
            self.rejected_empty_frame
            + self.rejected_too_few_detections
            + self.rejected_keypoints_mismatch
            + self.rejected_few_qualifying
            + self.rejected_duplicate_frame
        )

    @property
    def total_rejected_persons(self) -> int:
        """인물 레벨 총 거부 수."""
        return (
            self.rejected_not_player
            + self.rejected_low_confidence
            + self.rejected_bad_bbox_size
            + self.rejected_insufficient_keypoints
            + self.rejected_missing_critical
            + self.rejected_low_completeness
            + self.rejected_low_body_completeness
        )

    def update_completeness_ewma(self, completeness: float) -> None:
        """전체 EWMA 완전성 업데이트."""
        if self._ewma_completeness == 0.0:
            self._ewma_completeness = completeness
        else:
            alpha = self._ewma_alpha
            self._ewma_completeness = (
                alpha * completeness + (1.0 - alpha) * self._ewma_completeness
            )

    def update_subregion_ewma(self, subregion_comp: dict[str, float]) -> None:
        """서브 리전 EWMA 업데이트."""
        alpha = self._ewma_alpha

        body_val = subregion_comp.get("body", 0.0)
        if self._ewma_body_completeness == 0.0:
            self._ewma_body_completeness = body_val
        else:
            self._ewma_body_completeness = (
                alpha * body_val + (1.0 - alpha) * self._ewma_body_completeness
            )

        hand_val = subregion_comp.get("hands_combined", 0.0)
        if self._ewma_hand_completeness == 0.0:
            self._ewma_hand_completeness = hand_val
        else:
            self._ewma_hand_completeness = (
                alpha * hand_val + (1.0 - alpha) * self._ewma_hand_completeness
            )

        foot_val = subregion_comp.get("foot", 0.0)
        if self._ewma_foot_completeness == 0.0:
            self._ewma_foot_completeness = foot_val
        else:
            self._ewma_foot_completeness = (
                alpha * foot_val + (1.0 - alpha) * self._ewma_foot_completeness
            )

        face_val = subregion_comp.get("face", 0.0)
        if self._ewma_face_completeness == 0.0:
            self._ewma_face_completeness = face_val
        else:
            self._ewma_face_completeness = (
                alpha * face_val + (1.0 - alpha) * self._ewma_face_completeness
            )

    def to_dict(self) -> dict[str, object]:
        """통계를 딕셔너리로 변환."""
        return {
            "total_input_frames": self.total_input_frames,
            "total_persons_seen": self.total_persons_seen,
            "total_extracted": self.total_extracted,
            "total_persons_extracted": self.total_persons_extracted,
            "total_flushed": self.total_flushed,
            "total_flush_count": self.total_flush_count,
            "pass_rate": round(self.pass_rate, 4),
            "avg_completeness": round(self.avg_completeness, 4),
            "subregion_avg_completeness": {
                "body": round(self._ewma_body_completeness, 4),
                "hands": round(self._ewma_hand_completeness, 4),
                "foot": round(self._ewma_foot_completeness, 4),
                "face": round(self._ewma_face_completeness, 4),
            },
            "frame_rejections": {
                "empty_frame": self.rejected_empty_frame,
                "too_few_detections": self.rejected_too_few_detections,
                "keypoints_mismatch": self.rejected_keypoints_mismatch,
                "few_qualifying": self.rejected_few_qualifying,
                "duplicate_frame": self.rejected_duplicate_frame,
            },
            "person_rejections": {
                "not_player": self.rejected_not_player,
                "low_confidence": self.rejected_low_confidence,
                "bad_bbox_size": self.rejected_bad_bbox_size,
                "insufficient_keypoints": self.rejected_insufficient_keypoints,
                "missing_critical": self.rejected_missing_critical,
                "low_completeness": self.rejected_low_completeness,
                "low_body_completeness": self.rejected_low_body_completeness,
            },
            "quality_distribution": {
                "excellent": self.quality_excellent,
                "good": self.quality_good,
                "fair": self.quality_fair,
            },
        }


@dataclass(slots=True)
class WholeBodyExtractionMetadata:
    """
    추출 세션 메타데이터.

    finalize() 시 metadata.json으로 저장.
    """

    session_id: str = ""
    date: str = ""
    source_game_id: str = ""
    total_samples: int = 0
    total_persons: int = 0
    avg_completeness: float = 0.0
    keypoint_format: str = "coco_wholebody_133"
    config_snapshot: dict[str, object] = field(default_factory=dict)
    extraction_stats: dict[str, object] = field(default_factory=dict)
    output_directory: str = ""

    def to_dict(self) -> dict[str, object]:
        """메타데이터를 딕셔너리로 변환."""
        return {
            "session_id": self.session_id,
            "date": self.date,
            "source_game_id": self.source_game_id,
            "total_samples": self.total_samples,
            "total_persons": self.total_persons,
            "avg_completeness": round(self.avg_completeness, 4),
            "keypoint_format": self.keypoint_format,
            "num_keypoints": NUM_KEYPOINTS_WHOLEBODY,
            "training_target": "ViTPose-WholeBody/DWPose",
            "subregion_layout": {
                "body": {"start": _BODY_RANGE[0], "end": _BODY_RANGE[1] - 1, "count": _BODY_RANGE[1] - _BODY_RANGE[0]},
                "foot": {"start": _FOOT_RANGE[0], "end": _FOOT_RANGE[1] - 1, "count": _FOOT_RANGE[1] - _FOOT_RANGE[0]},
                "face": {"start": _FACE_RANGE[0], "end": _FACE_RANGE[1] - 1, "count": _FACE_RANGE[1] - _FACE_RANGE[0]},
                "left_hand": {"start": _LEFT_HAND_RANGE[0], "end": _LEFT_HAND_RANGE[1] - 1, "count": _LEFT_HAND_RANGE[1] - _LEFT_HAND_RANGE[0]},
                "right_hand": {"start": _RIGHT_HAND_RANGE[0], "end": _RIGHT_HAND_RANGE[1] - 1, "count": _RIGHT_HAND_RANGE[1] - _RIGHT_HAND_RANGE[0]},
            },
            "config": self.config_snapshot,
            "stats": self.extraction_stats,
            "output_directory": self.output_directory,
        }


# =============================================================================
# 메인 클래스
# =============================================================================
class WholeBodyKeypointExtractor:
    """
    WholeBody 133 키포인트 데이터 추출기.

    COCO-WholeBody 133-keypoint 모델(ViTPose-WholeBody / DWPose)
    농구 특화 재학습용 데이터셋을 자동 추출합니다.

    분석 중 고품질 WholeBody 키포인트를 3단계 품질 필터 + 서브 리전 필터로 선별하고,
    풀프레임 이미지 + YOLO Keypoint 라벨(133kp) + JSON 어노테이션(서브 리전 포함)을
    로컬에 저장합니다.

    사용법::

        extractor = WholeBodyKeypointExtractor()
        extractor.initialize()

        for frame, detections, keypoints in video_frames:
            extractor.extract_from_frame(detections, frame, keypoints)

        result = extractor.finalize("game_001")

    3단계 품질 필터:
        Stage 1 (프레임): 프레임 유효성, 최소 감지 수, keypoints 대응
        Stage 2 (인물): role, 신뢰도, bbox 크기, 가시 키포인트, 필수 키포인트,
                        완전성, Body 서브 리전 완전성
        Stage 3 (프레임 집계): 최소 적격 인물 수 + pHash 중복 방지

    스레드 안전성:
        내부 Lock으로 extract_from_frame/flush/finalize 동시 호출 보호.
    """

    def __init__(
        self,
        config: WholeBodyExtractionConfig | None = None,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        """
        추출기 생성.

        실제 초기화는 initialize()에서 수행합니다.

        Args:
            config: 추출 설정 (None이면 initialize()에서 로드)
            metrics_collector: 메트릭 수집기 (DI, 선택적)
        """
        self._config: WholeBodyExtractionConfig | None = config
        self._metrics_collector = metrics_collector
        self._initialized: bool = False

        # 상태
        self._stats: WholeBodyExtractionStats = WholeBodyExtractionStats()
        self._buffer: list[WholeBodyExtractionSample] = []
        self._hash_cache: OrderedDict[str, bool] = OrderedDict()
        self._last_flush_time: float = 0.0
        self._session_id: str = ""
        self._output_dir: str = ""
        self._images_dir: str = ""
        self._labels_dir: str = ""
        self._annotations_dir: str = ""

        # 스레드 안전
        self._lock: threading.Lock = threading.Lock()

    # =========================================================================
    # 초기화/종료
    # =========================================================================
    def initialize(
        self,
        config: WholeBodyExtractionConfig | None = None,
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
            ├── images/
            ├── labels/
            └── annotations/

        Args:
            config: 추출 설정 (최우선)
            config_loader: YAML 설정 로더 (config 없을 때 사용)
        """
        with self._lock:
            # 설정 로드
            if config is not None:
                self._config = config
            elif self._config is None:
                self._config = WholeBodyExtractionConfig.from_config(config_loader)

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
            self._images_dir = os.path.join(self._output_dir, "images")
            self._labels_dir = os.path.join(self._output_dir, "labels")
            self._annotations_dir = os.path.join(self._output_dir, "annotations")

            os.makedirs(self._images_dir, exist_ok=True)
            os.makedirs(self._labels_dir, exist_ok=True)
            os.makedirs(self._annotations_dir, exist_ok=True)

            # 상태 초기화
            self._stats = WholeBodyExtractionStats()
            self._buffer.clear()
            self._hash_cache.clear()
            self._last_flush_time = time.time()

            self._initialized = True

            logger.info(
                "WholeBodyKeypointExtractor 초기화 완료 "
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
            self._stats = WholeBodyExtractionStats()
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
    def stats(self) -> WholeBodyExtractionStats:
        """현재 추출 통계."""
        return self._stats

    @property
    def current_buffer_size(self) -> int:
        """현재 버퍼에 축적된 샘플 수."""
        return len(self._buffer)

    @property
    def is_buffer_full(self) -> bool:
        """버퍼가 가득 찼는지 여부."""
        if self._config is None:
            return False
        return len(self._buffer) >= self._config.buffer_size

    @property
    def is_max_samples_reached(self) -> bool:
        """세션 최대 추출 수 도달 여부."""
        if self._config is None:
            return False
        return self._stats.total_extracted >= self._config.max_total_samples

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
    def extract_from_frame(
        self,
        detections: list[PlayerDetection],
        frame: NDArray[np.uint8],
        keypoints_per_person: list[NDArray[np.float32]],
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> bool:
        """
        프레임의 WholeBody 133 키포인트 데이터 추출 시도.

        3단계 품질 필터 (+ Body 서브 리전 필터) → 프레임 리사이즈 + 키포인트 스케일링 →
        pHash 중복 확인 → JPEG 인코딩 → YOLO Keypoint 라벨 생성 (133kp) →
        JSON 어노테이션 (서브 리전 포함) → 버퍼 추가 → 자동 flush.

        Args:
            detections: 프레임 내 모든 선수 감지 결과
            frame: 원본 프레임 (BGR, H×W×3)
            keypoints_per_person: 각 detection의 WholeBody 133-point 키포인트
                각 원소: (133, 3) NDArray [x_pixel, y_pixel, confidence]
            frame_index: 프레임 번호
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            추출 성공 여부 (True = 버퍼에 추가됨)

        Raises:
            PoseEstimationException: 초기화되지 않은 상태에서 호출 시
        """
        if not self._initialized or self._config is None:
            raise PoseEstimationException(
                message="WholeBodyKeypointExtractor가 초기화되지 않았습니다",
                error_code=ErrorCode.POSE_ESTIMATION_ERROR,
            )

        if not self._config.enabled:
            return False

        with self._lock:
            self._stats.total_input_frames += 1

            # 최대 샘플 수 확인
            if self._stats.total_extracted >= self._config.max_total_samples:
                return False

            # Stage 1: 프레임 레벨 필터
            stage1_passed, stage1_reason = self._check_frame_validity(
                detections, frame, keypoints_per_person
            )
            if not stage1_passed:
                self._increment_frame_rejection(stage1_reason)
                return False

            self._stats.total_persons_seen += len(detections)
            orig_h, orig_w = frame.shape[:2]

            # Stage 2: 개별 인물 필터 → qualifying 인덱스 + 품질 등급 + 서브 리전
            qualifying_indices: list[int] = []
            qualifying_keypoints: list[NDArray[np.float32]] = []
            qualifying_grades: list[str] = []
            qualifying_subregions: list[dict[str, float]] = []

            for i, (det, kps) in enumerate(zip(detections, keypoints_per_person)):
                passed, reason = self._filter_person_quality(det, kps, orig_h, orig_w)
                if passed:
                    grade = self._compute_quality_grade(kps)
                    subregion = self._compute_subregion_completeness(kps)
                    qualifying_indices.append(i)
                    qualifying_keypoints.append(kps)
                    qualifying_grades.append(grade)
                    qualifying_subregions.append(subregion)
                else:
                    self._increment_person_rejection(reason)

            # Stage 3: 프레임 집계 필터
            if len(qualifying_indices) < self._config.min_qualifying_persons:
                self._stats.rejected_few_qualifying += 1
                return False

            # 프레임 리사이즈
            resized_frame, scale_x, scale_y = self._resize_frame_with_scale(frame)
            resized_h, resized_w = resized_frame.shape[:2]

            # pHash 중복 확인
            if self._config.dedup_enabled:
                phash = self._compute_phash(resized_frame)
                if self._is_duplicate(phash):
                    self._stats.rejected_duplicate_frame += 1
                    return False
                self._register_hash(phash)
            else:
                phash = ""

            # JPEG 인코딩
            image_data = self._encode_jpeg(resized_frame)
            if image_data is None:
                return False

            # 키포인트 스케일링 (리사이즈에 맞게)
            scaled_keypoints: list[NDArray[np.float32]] = []
            for kps in qualifying_keypoints:
                scaled_kps = self._scale_keypoints(kps, scale_x, scale_y)
                scaled_keypoints.append(scaled_kps)

            # YOLO Keypoint 라벨 생성 (.txt, 133kp)
            yolo_lines: list[str] = []
            for idx_pos, q_idx in enumerate(qualifying_indices):
                det = detections[q_idx]
                kps = scaled_keypoints[idx_pos]
                line = self._generate_yolo_keypoint_label(
                    det, kps, resized_h, resized_w, scale_x, scale_y
                )
                yolo_lines.append(line)

            yolo_label = "\n".join(yolo_lines)

            # JSON 어노테이션 생성 (서브 리전 포함)
            annotation = self._generate_json_annotation(
                detections, keypoints_per_person,
                qualifying_indices, qualifying_grades, qualifying_subregions,
                orig_h, orig_w, frame_index, timestamp_ms,
            )

            # 평균 완전성 계산
            completeness_values: list[float] = []
            for kps in qualifying_keypoints:
                visible = int(np.sum(kps[:, 2] >= self._config.keypoint_confidence_threshold))
                completeness_values.append(visible / NUM_KEYPOINTS_WHOLEBODY)

            avg_comp = (
                sum(completeness_values) / len(completeness_values)
                if completeness_values
                else 0.0
            )

            # 품질 등급 통계 업데이트
            for grade in qualifying_grades:
                if grade == "excellent":
                    self._stats.quality_excellent += 1
                elif grade == "good":
                    self._stats.quality_good += 1
                elif grade == "fair":
                    self._stats.quality_fair += 1

            # 서브 리전 EWMA 업데이트 (평균)
            if qualifying_subregions:
                avg_subregion: dict[str, float] = {}
                for key in ("body", "foot", "face", "left_hand", "right_hand", "hands_combined"):
                    vals = [sr.get(key, 0.0) for sr in qualifying_subregions]
                    avg_subregion[key] = sum(vals) / len(vals)
                self._stats.update_subregion_ewma(avg_subregion)

            # Sample 생성
            sample = WholeBodyExtractionSample(
                sample_id=uuid4().hex[:12],
                image_data=image_data,
                yolo_label=yolo_label,
                annotation_data=annotation,
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                person_count=len(qualifying_indices),
                avg_completeness=round(avg_comp, 4),
                image_hash=phash,
            )

            self._buffer.append(sample)
            self._stats.total_extracted += 1
            self._stats.total_persons_extracted += len(qualifying_indices)
            self._stats.update_completeness_ewma(avg_comp)

            # 메트릭 기록
            if self._metrics_collector is not None:
                try:
                    counter = self._metrics_collector.counter(
                        "wholebody_extraction_total",
                        help="총 추출된 WholeBody 133kp 프레임 수",
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
        버퍼의 샘플을 디스크에 기록.

        Returns:
            기록된 샘플 수
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
                dataset_type=DatasetType.WHOLEBODY_KEYPOINT,
                version="1.0.0",
                total_records=self._stats.total_flushed,
                split=DatasetSplit.TRAIN,
                source_game_ids=[source_game_id] if source_game_id else [],
                description=(
                    f"WholeBody 133kp extraction "
                    f"(session={self._session_id}, "
                    f"samples={self._stats.total_flushed}, "
                    f"persons={self._stats.total_persons_extracted})"
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
                "WholeBodyKeypointExtractor 종료 "
                "(session=%s, total_flushed=%d, persons=%d, "
                "pass_rate=%.2f%%, avg_completeness=%.4f, size=%d bytes)",
                self._session_id,
                self._stats.total_flushed,
                self._stats.total_persons_extracted,
                self._stats.pass_rate * 100,
                self._stats.avg_completeness,
                total_size,
            )

            return result

    # =========================================================================
    # Stage 1: 프레임 레벨 필터
    # =========================================================================
    def _check_frame_validity(
        self,
        detections: list[PlayerDetection],
        frame: NDArray[np.uint8],
        keypoints_per_person: list[NDArray[np.float32]],
    ) -> tuple[bool, str]:
        """
        프레임 레벨 유효성 검사.

        Args:
            detections: 감지 결과 리스트
            frame: 원본 프레임
            keypoints_per_person: 키포인트 배열 리스트 (각 (133, 3))

        Returns:
            (통과 여부, 거부 사유)
        """
        config = self._config
        if config is None:
            return False, "not_initialized"

        # 1a: 빈 프레임
        if frame.size == 0:
            return False, _REJECT_EMPTY_FRAME

        # 1b: 최소 감지 수
        if len(detections) < config.min_detections:
            return False, _REJECT_TOO_FEW_DETECTIONS

        # 1c: keypoints 대응 체크
        if len(keypoints_per_person) != len(detections):
            return False, _REJECT_KEYPOINTS_MISMATCH

        return True, ""

    # =========================================================================
    # Stage 2: 인물 레벨 필터
    # =========================================================================
    def _filter_person_quality(
        self,
        detection: PlayerDetection,
        keypoints: NDArray[np.float32],
        frame_h: int,
        frame_w: int,
    ) -> tuple[bool, str]:
        """
        개별 인물 품질 필터.

        Stage 2a: PLAYER role만
        Stage 2b: 감지 신뢰도
        Stage 2c: bbox 크기
        Stage 2d: 가시 키포인트 수 (133kp 중 >= min_visible_keypoints)
        Stage 2e: 필수 키포인트 (양 어깨 + 양 손목 + 양 엉덩이)
        Stage 2f: 전체 스켈레톤 완전성
        Stage 2g: Body 서브 리전 완전성 (NEW)

        Args:
            detection: 단일 감지 결과
            keypoints: WholeBody 133-point 키포인트 (133, 3)
            frame_h: 프레임 높이
            frame_w: 프레임 너비

        Returns:
            (통과 여부, 거부 사유)
        """
        config = self._config
        if config is None:
            return False, "not_initialized"

        # 2a: 선수만
        if detection.role != PlayerRole.PLAYER:
            return False, _REJECT_NOT_PLAYER

        # 2b: 감지 신뢰도
        if detection.confidence < config.min_detection_confidence:
            return False, _REJECT_LOW_CONFIDENCE

        # 2c: bbox 크기
        bbox = detection.bounding_box
        if bbox.width * bbox.height < config.min_bbox_pixels:
            return False, _REJECT_BAD_BBOX_SIZE

        # 2d: 가시 키포인트 수 (전체 133kp)
        kp_thresh = config.keypoint_confidence_threshold
        visible_count = int(np.sum(keypoints[:, 2] >= kp_thresh))
        if visible_count < config.min_visible_keypoints:
            return False, _REJECT_INSUFFICIENT_KEYPOINTS

        # 2e: 필수 키포인트 (양 어깨 + 양 손목 + 양 엉덩이)
        for idx in config.critical_keypoint_indices:
            if idx < len(keypoints) and keypoints[idx, 2] < kp_thresh:
                return False, _REJECT_MISSING_CRITICAL

        # 2f: 전체 스켈레톤 완전성
        completeness = visible_count / NUM_KEYPOINTS_WHOLEBODY
        if completeness < config.min_skeleton_completeness:
            return False, _REJECT_LOW_COMPLETENESS

        # 2g: Body 서브 리전 완전성 (NEW)
        body_start, body_end = _BODY_RANGE
        body_total = body_end - body_start  # 17
        body_visible = int(np.sum(keypoints[body_start:body_end, 2] >= kp_thresh))
        body_completeness = body_visible / body_total if body_total > 0 else 0.0
        if body_completeness < config.min_body_completeness:
            return False, _REJECT_LOW_BODY_COMPLETENESS

        return True, ""

    def _increment_person_rejection(self, reason: str) -> None:
        """인물 레벨 거부 사유별 카운터 증가."""
        if reason == _REJECT_NOT_PLAYER:
            self._stats.rejected_not_player += 1
        elif reason == _REJECT_LOW_CONFIDENCE:
            self._stats.rejected_low_confidence += 1
        elif reason == _REJECT_BAD_BBOX_SIZE:
            self._stats.rejected_bad_bbox_size += 1
        elif reason == _REJECT_INSUFFICIENT_KEYPOINTS:
            self._stats.rejected_insufficient_keypoints += 1
        elif reason == _REJECT_MISSING_CRITICAL:
            self._stats.rejected_missing_critical += 1
        elif reason == _REJECT_LOW_COMPLETENESS:
            self._stats.rejected_low_completeness += 1
        elif reason == _REJECT_LOW_BODY_COMPLETENESS:
            self._stats.rejected_low_body_completeness += 1

    def _increment_frame_rejection(self, reason: str) -> None:
        """프레임 레벨 거부 사유별 카운터 증가."""
        if reason == _REJECT_EMPTY_FRAME:
            self._stats.rejected_empty_frame += 1
        elif reason == _REJECT_TOO_FEW_DETECTIONS:
            self._stats.rejected_too_few_detections += 1
        elif reason == _REJECT_KEYPOINTS_MISMATCH:
            self._stats.rejected_keypoints_mismatch += 1

    # =========================================================================
    # 서브 리전 완전성
    # =========================================================================
    def _compute_subregion_completeness(
        self, keypoints: NDArray[np.float32]
    ) -> dict[str, float]:
        """
        서브 리전별 완전성 계산.

        Args:
            keypoints: (133, 3) 키포인트 배열

        Returns:
            서브 리전별 완전성 딕셔너리
            {"body": float, "foot": float, "face": float,
             "left_hand": float, "right_hand": float, "hands_combined": float}
        """
        if self._config is None:
            return {
                "body": 0.0, "foot": 0.0, "face": 0.0,
                "left_hand": 0.0, "right_hand": 0.0, "hands_combined": 0.0,
            }

        kp_thresh = self._config.keypoint_confidence_threshold
        result: dict[str, float] = {}

        for name, start, end in _SUBREGION_DEFINITIONS:
            total = end - start
            visible = int(np.sum(keypoints[start:end, 2] >= kp_thresh))
            result[name] = visible / total if total > 0 else 0.0

        # 양손 결합 완전성
        result["hands_combined"] = (
            result.get("left_hand", 0.0) + result.get("right_hand", 0.0)
        ) / 2.0

        return result

    # =========================================================================
    # 품질 등급
    # =========================================================================
    def _compute_quality_grade(self, keypoints: NDArray[np.float32]) -> str:
        """
        품질 등급 계산 (133kp 기준).

        Args:
            keypoints: (133, 3) 키포인트 배열

        Returns:
            "excellent" (>=120), "good" (>=80), "fair" (<80) 중 하나
        """
        if self._config is None:
            return "fair"

        visible = int(np.sum(keypoints[:, 2] >= self._config.keypoint_confidence_threshold))

        if visible >= _QUALITY_EXCELLENT_THRESHOLD:
            return "excellent"
        elif visible >= _QUALITY_GOOD_THRESHOLD:
            return "good"
        else:
            return "fair"

    # =========================================================================
    # YOLO Keypoint 라벨 생성 (133kp)
    # =========================================================================
    def _generate_yolo_keypoint_label(
        self,
        detection: PlayerDetection,
        keypoints: NDArray[np.float32],
        frame_h: int,
        frame_w: int,
        scale_x: float,
        scale_y: float,
    ) -> str:
        """
        YOLO Keypoint format 라벨 문자열 생성 (133kp).

        형식: ``class cx cy w h kp1_x kp1_y kp1_v ... kp133_x kp133_y kp133_v``
        모든 좌표 정규화 (0~1). 총 404 값/줄.

        Args:
            detection: 감지 결과
            keypoints: 스케일링된 (133, 3) 키포인트 (리사이즈 프레임 좌표)
            frame_h: 리사이즈된 프레임 높이
            frame_w: 리사이즈된 프레임 너비
            scale_x: X 스케일 계수
            scale_y: Y 스케일 계수

        Returns:
            YOLO Keypoint format 라벨 문자열 (404 값)
        """
        if self._config is None:
            return ""

        fw = float(frame_w) if frame_w > 0 else 1.0
        fh = float(frame_h) if frame_h > 0 else 1.0

        bbox = detection.bounding_box
        # bbox도 스케일링
        bx1 = bbox.x1 * scale_x
        by1 = bbox.y1 * scale_y
        bx2 = bbox.x2 * scale_x
        by2 = bbox.y2 * scale_y
        bw = bx2 - bx1
        bh = by2 - by1

        # 정규화
        cx = (bx1 + bx2) / 2.0 / fw
        cy = (by1 + by2) / 2.0 / fh
        nw = bw / fw
        nh = bh / fh

        # 클램핑
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        nw = max(0.0, min(1.0, nw))
        nh = max(0.0, min(1.0, nh))

        parts: list[str] = [f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"]

        kp_thresh = self._config.keypoint_confidence_threshold

        for i in range(NUM_KEYPOINTS_WHOLEBODY):
            if i < len(keypoints):
                conf = keypoints[i, 2]
                if conf < kp_thresh:
                    # 비가시: 0,0,0
                    parts.append("0.000000 0.000000 0")
                else:
                    kp_x = keypoints[i, 0] / fw
                    kp_y = keypoints[i, 1] / fh
                    kp_x = max(0.0, min(1.0, kp_x))
                    kp_y = max(0.0, min(1.0, kp_y))
                    parts.append(f"{kp_x:.6f} {kp_y:.6f} 2")
            else:
                parts.append("0.000000 0.000000 0")

        return " ".join(parts)

    # =========================================================================
    # JSON 어노테이션 생성 (서브 리전 포함)
    # =========================================================================
    def _generate_json_annotation(
        self,
        detections: list[PlayerDetection],
        keypoints_per_person: list[NDArray[np.float32]],
        qualifying_indices: list[int],
        qualifying_grades: list[str],
        qualifying_subregions: list[dict[str, float]],
        frame_h: int,
        frame_w: int,
        frame_index: int,
        timestamp_ms: float,
    ) -> dict[str, object]:
        """
        상세 JSON 어노테이션 생성 (서브 리전 완전성 포함).

        Args:
            detections: 전체 감지 결과
            keypoints_per_person: 원본 키포인트 (원본 프레임 좌표)
            qualifying_indices: 필터 통과한 인덱스
            qualifying_grades: 품질 등급 리스트
            qualifying_subregions: 서브 리전 완전성 리스트
            frame_h: 원본 프레임 높이
            frame_w: 원본 프레임 너비
            frame_index: 프레임 번호
            timestamp_ms: 타임스탬프

        Returns:
            JSON 어노테이션 딕셔너리
        """
        config = self._config
        if config is None:
            return {}

        w = float(frame_w) if frame_w > 0 else 1.0
        h = float(frame_h) if frame_h > 0 else 1.0
        kp_thresh = config.keypoint_confidence_threshold

        persons_data: list[dict[str, object]] = []
        total_completeness = 0.0

        for pos, q_idx in enumerate(qualifying_indices):
            det = detections[q_idx]
            kps = keypoints_per_person[q_idx]
            bbox = det.bounding_box

            # bbox 정규화 (cxcywh)
            cx_n = round((bbox.x1 + bbox.x2) / 2.0 / w, 6)
            cy_n = round((bbox.y1 + bbox.y2) / 2.0 / h, 6)
            bw_n = round(bbox.width / w, 6)
            bh_n = round(bbox.height / h, 6)

            # 키포인트 데이터 (133개)
            kp_data: list[dict[str, object]] = []
            visible_count = 0
            for ki in range(NUM_KEYPOINTS_WHOLEBODY):
                if ki < len(kps):
                    conf = float(kps[ki, 2])
                    vis = 2 if conf >= kp_thresh else 0
                    if vis == 2:
                        visible_count += 1
                    kp_name = (
                        _WHOLEBODY_KEYPOINT_NAMES[ki]
                        if ki < len(_WHOLEBODY_KEYPOINT_NAMES)
                        else f"kp_{ki}"
                    )
                    kp_data.append({
                        "index": ki,
                        "name": kp_name,
                        "x": round(float(kps[ki, 0]), 2),
                        "y": round(float(kps[ki, 1]), 2),
                        "confidence": round(conf, 4),
                        "visibility": vis,
                    })
                else:
                    kp_name = (
                        _WHOLEBODY_KEYPOINT_NAMES[ki]
                        if ki < len(_WHOLEBODY_KEYPOINT_NAMES)
                        else f"kp_{ki}"
                    )
                    kp_data.append({
                        "index": ki,
                        "name": kp_name,
                        "x": 0.0,
                        "y": 0.0,
                        "confidence": 0.0,
                        "visibility": 0,
                    })

            completeness = visible_count / NUM_KEYPOINTS_WHOLEBODY
            total_completeness += completeness

            # 필수 키포인트 가시 여부
            critical_visible = all(
                kps[idx, 2] >= kp_thresh
                for idx in config.critical_keypoint_indices
                if idx < len(kps)
            )

            grade = qualifying_grades[pos] if pos < len(qualifying_grades) else "fair"
            subregion = qualifying_subregions[pos] if pos < len(qualifying_subregions) else {}

            persons_data.append({
                "person_index": pos,
                "detection_confidence": round(det.confidence, 4),
                "role": det.role.value,
                "bbox": {
                    "x1": round(bbox.x1, 2),
                    "y1": round(bbox.y1, 2),
                    "x2": round(bbox.x2, 2),
                    "y2": round(bbox.y2, 2),
                },
                "bbox_normalized": [cx_n, cy_n, bw_n, bh_n],
                "keypoints_wholebody_133": kp_data,
                "quality": {
                    "visible_count": visible_count,
                    "total_count": NUM_KEYPOINTS_WHOLEBODY,
                    "completeness": round(completeness, 4),
                    "grade": grade,
                    "critical_keypoints_visible": critical_visible,
                    "subregion_completeness": {
                        k: round(v, 4) for k, v in subregion.items()
                    },
                },
            })

        avg_comp = (
            total_completeness / len(qualifying_indices)
            if qualifying_indices
            else 0.0
        )

        return {
            "frame_index": frame_index,
            "timestamp_ms": round(timestamp_ms, 2),
            "image_size": {"width": frame_w, "height": frame_h},
            "persons": persons_data,
            "frame_quality": {
                "total_persons": len(detections),
                "qualifying_persons": len(qualifying_indices),
                "avg_completeness": round(avg_comp, 4),
            },
        }

    # =========================================================================
    # 이미지 처리
    # =========================================================================
    def _resize_frame_with_scale(
        self, frame: NDArray[np.uint8]
    ) -> tuple[NDArray[np.uint8], float, float]:
        """
        프레임 리사이즈 + 스케일 계수 반환.

        Args:
            frame: 원본 프레임

        Returns:
            (리사이즈된 프레임, scale_x, scale_y)
        """
        if self._config is None:
            return frame.copy(), 1.0, 1.0

        h, w = frame.shape[:2]
        max_side = self._config.max_long_side

        if max(h, w) <= max_side:
            return frame.copy(), 1.0, 1.0

        scale = max_side / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        scale_x = new_w / w if w > 0 else 1.0
        scale_y = new_h / h if h > 0 else 1.0

        return resized, scale_x, scale_y

    def _scale_keypoints(
        self,
        keypoints: NDArray[np.float32],
        scale_x: float,
        scale_y: float,
    ) -> NDArray[np.float32]:
        """
        키포인트 좌표를 리사이즈 비율에 맞게 스케일링.

        Args:
            keypoints: 원본 (133, 3) 키포인트 [x, y, conf]
            scale_x: X 방향 스케일
            scale_y: Y 방향 스케일

        Returns:
            스케일링된 키포인트 (133, 3)
        """
        scaled = keypoints.copy()
        scaled[:, 0] *= scale_x
        scaled[:, 1] *= scale_y
        # confidence([:, 2])는 변경 안 함
        return scaled

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

        캐시 내 모든 해시와 Hamming distance 비교.

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
        pHash를 캐시에 등록.

        LRU 방식으로 최대 크기 유지.

        Args:
            phash: 16자 hex 해시
        """
        if self._config is None:
            return

        self._hash_cache[phash] = True

        # LRU: 최대 크기 초과 시 가장 오래된 항목 제거
        while len(self._hash_cache) > self._config.max_cache_size:
            self._hash_cache.popitem(last=False)

    # =========================================================================
    # 내부 Flush
    # =========================================================================
    def _flush_buffer_internal(self) -> int:
        """
        버퍼를 디스크에 기록 (Lock 내부 호출).

        Returns:
            기록된 샘플 수
        """
        if not self._buffer:
            return 0

        flushed = 0

        for sample in self._buffer:
            try:
                # 이미지: images/*.jpg
                img_path = os.path.join(
                    self._images_dir, f"{sample.sample_id}.jpg"
                )
                with open(img_path, "wb") as f:
                    f.write(sample.image_data)

                # YOLO 라벨: labels/*.txt (133kp)
                label_path = os.path.join(
                    self._labels_dir, f"{sample.sample_id}.txt"
                )
                with open(label_path, "w", encoding="utf-8") as f:
                    f.write(sample.yolo_label)

                # JSON 어노테이션: annotations/*.json (서브 리전 포함)
                ann_path = os.path.join(
                    self._annotations_dir, f"{sample.sample_id}.json"
                )
                with open(ann_path, "w", encoding="utf-8") as f:
                    json.dump(
                        sample.annotation_data, f, ensure_ascii=False, indent=2
                    )

                flushed += 1

            except OSError as e:
                logger.error(
                    "디스크 기록 실패 (sample=%s): %s",
                    sample.sample_id, e
                )

        self._buffer.clear()
        self._stats.total_flushed += flushed
        self._stats.total_flush_count += 1
        self._last_flush_time = time.time()

        if flushed > 0:
            logger.debug(
                "Flush 완료: %d 샘플 기록 (총 %d)",
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
    def _create_metadata(self, source_game_id: str) -> WholeBodyExtractionMetadata:
        """
        추출 세션 메타데이터 생성.

        Args:
            source_game_id: 소스 경기 ID

        Returns:
            WholeBodyExtractionMetadata
        """
        config = self._config
        config_dict: dict[str, object] = {}
        if config is not None:
            config_dict = {
                "min_detections": config.min_detections,
                "min_detection_confidence": config.min_detection_confidence,
                "min_bbox_pixels": config.min_bbox_pixels,
                "keypoint_confidence_threshold": config.keypoint_confidence_threshold,
                "min_visible_keypoints": config.min_visible_keypoints,
                "min_skeleton_completeness": config.min_skeleton_completeness,
                "critical_keypoint_indices": list(config.critical_keypoint_indices),
                "min_qualifying_persons": config.min_qualifying_persons,
                "min_body_completeness": config.min_body_completeness,
                "min_hand_completeness": config.min_hand_completeness,
                "min_foot_completeness": config.min_foot_completeness,
                "min_face_completeness": config.min_face_completeness,
                "max_long_side": config.max_long_side,
                "jpeg_quality": config.jpeg_quality,
                "buffer_size": config.buffer_size,
                "max_total_samples": config.max_total_samples,
                "dedup_enabled": config.dedup_enabled,
                "similarity_threshold": config.similarity_threshold,
            }

        return WholeBodyExtractionMetadata(
            session_id=self._session_id,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source_game_id=source_game_id,
            total_samples=self._stats.total_flushed,
            total_persons=self._stats.total_persons_extracted,
            avg_completeness=self._stats.avg_completeness,
            keypoint_format="coco_wholebody_133",
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
    "CONFIG_KEY_WHOLEBODY_EXTRACTION",
    "WholeBodyExtractionConfig",
    "WholeBodyExtractionSample",
    "WholeBodyExtractionStats",
    "WholeBodyExtractionMetadata",
    "WholeBodyKeypointExtractor",
]

__version__ = "1.0.0"
