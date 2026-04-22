# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: models.py
설명: 선수 감지 모듈 내부 전용 데이터 클래스
      - _PlayerCandidate: YOLO 감지 후보 (내부 파이프라인 전달용)
      - _UniformROI: 유니폼 ROI 추출 결과
      - _JerseyRegion: 등번호 영역 정보
      - _TrackState: 추적 내부 상태
      - 각 서브모듈 Config 데이터 클래스

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/player_constants.py: 클래스 ID, ROI 파라미터
    - shared/constants/reid_constants.py: 특징 벡터 차원, 유사도 임계값
    - shared/constants/ocr_constants.py: OCR 프레임 간격, 신뢰도 임계값
    - shared/constants/matching_constants.py: 매칭 가중치
    - shared/dto/player_dto.py: Team, PlayerRole
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.matching_constants import (
    APPEARANCE_WEIGHT,
    GEOMETRY_WEIGHT,
    POSITION_WEIGHT,
)
from shared.constants.ocr_constants import (
    HIGH_OCR_CONFIDENCE,
    MIN_OCR_CONFIDENCE,
    OCR_FRAME_INTERVAL,
)
from shared.constants.player_constants import (
    CHEST_CROP_X_END,
    CHEST_CROP_X_START,
    CHEST_CROP_Y_END,
    CHEST_CROP_Y_START,
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_STAFF,
    TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
)
from shared.constants.reid_constants import (
    EMA_MOMENTUM,
    FEATURE_DIM,
    GALLERY_FEATURE_MAX_AGE,
    GALLERY_MAX_SIZE,
    GALLERY_UPDATE_INTERVAL,
    GLOBAL_GALLERY_MAX_PERSONS,
    SIMILARITY_THRESHOLD,
    ReIDModel,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# YOLO 모델 경로 상수
# =============================================================================

_DEFAULT_MODEL_PATH: Final[str] = "weights/COURTVIEW_player.pt"
_DEFAULT_ONNX_PATH: Final[str] = "weights/COURTVIEW_player.onnx"

# 감지 파라미터 기본값
_DEFAULT_INPUT_SIZE: Final[int] = 640
_DEFAULT_CONFIDENCE: Final[float] = 0.4
_DEFAULT_HIGH_CONFIDENCE: Final[float] = 0.75
_DEFAULT_NMS_IOU: Final[float] = 0.45
_DEFAULT_MAX_DETECTIONS: Final[int] = 30

# 선수 bbox 크기 필터 (프레임 비율)
_DEFAULT_MIN_SIZE_RATIO: Final[float] = 0.02
_DEFAULT_MAX_SIZE_RATIO: Final[float] = 0.5
_DEFAULT_MIN_ASPECT_RATIO: Final[float] = 0.25  # 세로로 긴 형태
_DEFAULT_MAX_ASPECT_RATIO: Final[float] = 0.8

# 추적 기본 파라미터
_DEFAULT_MAX_AGE: Final[int] = 360  # 미감지 허용 프레임 (3초@120fps, 12초@30fps — 가려짐 대응)
_DEFAULT_MIN_HITS: Final[int] = 3  # 트랙 확정 최소 감지 수
_DEFAULT_IOU_THRESHOLD: Final[float] = 0.3  # 추적 매칭 IoU 임계값

# 멀티뷰 기본 파라미터
_MIN_TRIANGULATION_VIEWS: Final[int] = 2
_MAX_CACHE_SIZE: Final[int] = 300


# =============================================================================
# 설정 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class PlayerDetectorConfig:
    """
    선수 감지기 설정.

    YOLO Primary + 패턴 보조 하이브리드 감지기 파라미터.

    Attributes:
        model_path: YOLO 모델 파일 경로 (.pt)
        onnx_path: ONNX 모델 경로 (TensorRT 변환용)
        input_size: 모델 입력 해상도 (정사각형)
        confidence_threshold: 최소 감지 신뢰도
        high_confidence_threshold: 높은 신뢰도 임계값 (패턴 검증 생략)
        nms_iou_threshold: NMS IoU 임계값
        max_detections: 프레임당 최대 감지 수
        device: 추론 장치 ("cuda", "cpu")
        half_precision: FP16 사용 여부
        enable_color_validation: 패턴 보조 색상 검증 활성화
        enable_shape_validation: 패턴 보조 형태 검증 활성화
        enable_multi_view: 멀티뷰 융합 활성화
        min_triangulation_views: 삼각측량 최소 뷰 수
        min_size_ratio: 최소 bbox 크기 비율 (프레임 대비)
        max_size_ratio: 최대 bbox 크기 비율 (프레임 대비)
        min_aspect_ratio: 최소 종횡비 (w/h)
        max_aspect_ratio: 최대 종횡비 (w/h)
    """

    model_path: str = _DEFAULT_MODEL_PATH
    onnx_path: str = _DEFAULT_ONNX_PATH
    input_size: int = _DEFAULT_INPUT_SIZE
    confidence_threshold: float = _DEFAULT_CONFIDENCE
    high_confidence_threshold: float = _DEFAULT_HIGH_CONFIDENCE
    nms_iou_threshold: float = _DEFAULT_NMS_IOU
    max_detections: int = _DEFAULT_MAX_DETECTIONS
    device: str = "cuda"
    half_precision: bool = True
    enable_color_validation: bool = True
    enable_shape_validation: bool = True
    enable_multi_view: bool = False
    min_triangulation_views: int = _MIN_TRIANGULATION_VIEWS
    min_size_ratio: float = _DEFAULT_MIN_SIZE_RATIO
    max_size_ratio: float = _DEFAULT_MAX_SIZE_RATIO
    min_aspect_ratio: float = _DEFAULT_MIN_ASPECT_RATIO
    max_aspect_ratio: float = _DEFAULT_MAX_ASPECT_RATIO

    def __repr__(self) -> str:
        return (
            f"PlayerDetectorConfig(model={self.model_path}, "
            f"input={self.input_size}, conf={self.confidence_threshold}, "
            f"device={self.device}, fp16={self.half_precision})"
        )


@dataclass(slots=True)
class TeamClassifierConfig:
    """
    팀 분류기 설정.

    유니폼 HSV 색상 분석 기반 팀 분류 파라미터.

    Attributes:
        confidence_threshold: 분류 최소 신뢰도
        chest_y_start: 가슴 ROI 상단 비율 (bbox 내)
        chest_y_end: 가슴 ROI 하단 비율
        chest_x_start: 가슴 ROI 좌측 비율
        chest_x_end: 가슴 ROI 우측 비율
        min_roi_pixels: ROI 최소 픽셀 수 (품질 필터)
        color_bins: HSV 히스토그램 빈 수
        dominant_color_ratio: 주색상 비율 임계값
        enable_multi_view: 멀티뷰 투표 활성화
    """

    confidence_threshold: float = TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD
    chest_y_start: float = CHEST_CROP_Y_START
    chest_y_end: float = CHEST_CROP_Y_END
    chest_x_start: float = CHEST_CROP_X_START
    chest_x_end: float = CHEST_CROP_X_END
    min_roi_pixels: int = 100
    color_bins: int = 16
    dominant_color_ratio: float = 0.3
    device: str = "cuda"
    enable_multi_view: bool = False

    def __repr__(self) -> str:
        return (
            f"TeamClassifierConfig(conf={self.confidence_threshold}, "
            f"roi=({self.chest_y_start:.2f}-{self.chest_y_end:.2f}), "
            f"device={self.device})"
        )


@dataclass(slots=True)
class JerseyOCRConfig:
    """
    등번호 OCR 설정.

    텍스트 감지 + 인식 + 다중 뷰 투표 파라미터.

    Attributes:
        frame_interval: OCR 실행 프레임 간격
        min_confidence: OCR 최소 신뢰도
        high_confidence: OCR 높은 신뢰도 (즉시 확정)
        min_observations_for_confirm: 등번호 확정 최소 관측 수
        consistency_ratio: 확정 일관성 비율 (예: 70%)
        jersey_roi_top: 등번호 ROI 상단 비율
        jersey_roi_bottom: 등번호 ROI 하단 비율
        jersey_roi_left: 등번호 ROI 좌측 비율
        jersey_roi_right: 등번호 ROI 우측 비율
        enable_multi_view_voting: 다중 뷰 투표 활성화
    """

    frame_interval: int = OCR_FRAME_INTERVAL
    min_confidence: float = MIN_OCR_CONFIDENCE
    high_confidence: float = HIGH_OCR_CONFIDENCE
    min_observations_for_confirm: int = 3
    consistency_ratio: float = 0.7
    jersey_roi_top: float = 0.15
    jersey_roi_bottom: float = 0.55
    jersey_roi_left: float = 0.2
    jersey_roi_right: float = 0.8
    enable_multi_view_voting: bool = False

    def __repr__(self) -> str:
        return (
            f"JerseyOCRConfig(interval={self.frame_interval}, "
            f"min_conf={self.min_confidence})"
        )


@dataclass(slots=True)
class ReIDConfig:
    """
    Re-ID 모듈 설정.

    외관 특징 추출 + 갤러리 관리 파라미터.

    Attributes:
        model: Re-ID 모델 유형
        feature_dim: 특징 벡터 차원 수
        similarity_threshold: 매칭 유사도 임계값 (코사인)
        gallery_max_size: 인물별 최대 갤러리 크기
        gallery_max_persons: 전체 최대 인물 수
        gallery_feature_max_age: 특징 최대 생존 프레임
        gallery_update_interval: 갤러리 갱신 프레임 간격
        ema_momentum: 특징 벡터 EMA 모멘텀
        device: 추론 장치
        enable_cross_view: 크로스뷰 Re-ID 활성화
    """

    model: ReIDModel = ReIDModel.OSNET
    feature_dim: int = FEATURE_DIM
    similarity_threshold: float = SIMILARITY_THRESHOLD
    gallery_max_size: int = GALLERY_MAX_SIZE
    gallery_max_persons: int = GLOBAL_GALLERY_MAX_PERSONS
    gallery_feature_max_age: int = GALLERY_FEATURE_MAX_AGE
    gallery_update_interval: int = GALLERY_UPDATE_INTERVAL
    ema_momentum: float = EMA_MOMENTUM
    device: str = "cuda"
    enable_cross_view: bool = False

    def __repr__(self) -> str:
        return (
            f"ReIDConfig(model={self.model.value}, dim={self.feature_dim}, "
            f"sim_thr={self.similarity_threshold})"
        )


@dataclass(slots=True)
class PlayerTrackerConfig:
    """
    선수 추적기 설정.

    칼만 필터 + 헝가리안 매칭 + 크로스뷰 ID 일관성 파라미터.

    Attributes:
        max_age: 미감지 허용 최대 프레임 수 (초과 시 트랙 삭제)
        min_hits: 트랙 확정 최소 연속 감지 수
        iou_threshold: 매칭 IoU 임계값
        appearance_weight: 외관 유사도 가중치
        geometry_weight: 기하학(위치) 가중치
        position_weight: 이전 위치 가중치
        enable_multi_view: 멀티뷰 추적 활성화
    """

    max_age: int = _DEFAULT_MAX_AGE
    min_hits: int = _DEFAULT_MIN_HITS
    iou_threshold: float = _DEFAULT_IOU_THRESHOLD
    appearance_weight: float = APPEARANCE_WEIGHT
    geometry_weight: float = GEOMETRY_WEIGHT
    position_weight: float = POSITION_WEIGHT
    enable_multi_view: bool = False

    def __repr__(self) -> str:
        return (
            f"PlayerTrackerConfig(max_age={self.max_age}, "
            f"min_hits={self.min_hits}, iou={self.iou_threshold})"
        )


@dataclass(slots=True)
class PlayerIDManagerConfig:
    """
    선수 ID 통합 관리 설정.

    OCR + ReID + 추적 결과를 융합하여 최종 선수 ID를 결정하는
    파라미터.

    Attributes:
        ocr_weight: OCR 식별 가중치
        reid_weight: ReID 유사도 가중치
        tracking_weight: 추적 연속성 가중치
        confirmation_threshold: ID 확정 최소 융합 신뢰도
        max_unconfirmed_frames: 미확정 ID 최대 유지 프레임
        max_managed_players: 최대 관리 선수 수
    """

    ocr_weight: float = 0.4
    reid_weight: float = 0.35
    tracking_weight: float = 0.25
    confirmation_threshold: float = 0.7
    max_unconfirmed_frames: int = 90  # 약 3초 (30fps 기준)
    max_managed_players: int = 30  # 선수 10 + 심판 3 + 코치 2 × 2팀 = 30

    def __repr__(self) -> str:
        return (
            f"PlayerIDManagerConfig(ocr_w={self.ocr_weight}, "
            f"reid_w={self.reid_weight}, trk_w={self.tracking_weight})"
        )


# =============================================================================
# 내부 데이터 클래스 — 파이프라인 단계 간 전달용
# =============================================================================

@dataclass(slots=True)
class _PlayerCandidate:
    """
    선수 후보 (내부용).

    YOLO 감지 결과 + 패턴 검증 점수를 결합한 내부 구조체.
    player_detector → team_classifier / jersey_ocr / reid 간 전달.
    """

    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    yolo_confidence: float
    class_id: int = PLAYER_CLASS_ID_PLAYER
    color_score: float = 0.0
    shape_score: float = 0.0
    combined_score: float = 0.0
    camera_id: str | None = None
    frame_index: int = 0

    @property
    def center_x(self) -> float:
        """중심 X 좌표."""
        return self.bbox_x + self.bbox_w / 2.0

    @property
    def center_y(self) -> float:
        """중심 Y 좌표."""
        return self.bbox_y + self.bbox_h / 2.0

    @property
    def aspect_ratio(self) -> float:
        """종횡비 (w/h). 선수는 세로로 긴 형태 (< 1.0)."""
        if self.bbox_h <= 0:
            return 0.0
        return self.bbox_w / self.bbox_h

    @property
    def area(self) -> float:
        """면적 (픽셀²)."""
        return max(0.0, self.bbox_w * self.bbox_h)

    @property
    def is_person_class(self) -> bool:
        """사람 클래스 여부 (선수/심판/코치/스태프)."""
        return self.class_id in (
            PLAYER_CLASS_ID_PLAYER,
            PLAYER_CLASS_ID_REFEREE,
            PLAYER_CLASS_ID_COACH,
            PLAYER_CLASS_ID_STAFF,
        )

    def to_xyxy(self) -> tuple[float, float, float, float]:
        """(x1, y1, x2, y2) 변환."""
        return (
            self.bbox_x,
            self.bbox_y,
            self.bbox_x + self.bbox_w,
            self.bbox_y + self.bbox_h,
        )

    def __repr__(self) -> str:
        return (
            f"_PlayerCandidate(center=({self.center_x:.1f}, {self.center_y:.1f}), "
            f"cls={self.class_id}, yolo={self.yolo_confidence:.3f}, "
            f"combined={self.combined_score:.3f})"
        )


@dataclass(slots=True)
class _UniformROI:
    """
    유니폼 ROI 추출 결과 (내부용).

    가슴 영역 크롭 + HSV 히스토그램 분석 결과.
    team_classifier 내부에서 생성하여 팀 판별에 사용.
    """

    # HSV 주색상 (히스토그램 피크)
    dominant_hue: float = 0.0
    dominant_saturation: float = 0.0
    dominant_value: float = 0.0

    # 색상 분포 통계
    hue_std: float = 0.0
    saturation_mean: float = 0.0
    value_mean: float = 0.0

    # 피부색 비율 (마스킹 제거용)
    skin_ratio: float = 0.0

    # ROI 품질
    roi_pixel_count: int = 0
    is_valid: bool = False

    def __repr__(self) -> str:
        return (
            f"_UniformROI(hsv=({self.dominant_hue:.0f}, "
            f"{self.dominant_saturation:.0f}, {self.dominant_value:.0f}), "
            f"valid={self.is_valid})"
        )


@dataclass(slots=True)
class _JerseyRegion:
    """
    등번호 영역 정보 (내부용).

    jersey_ocr 내부에서 생성. 등번호 텍스트 감지 영역 + 인식 결과.
    """

    # 인식된 등번호 (0~99, None이면 미인식)
    number: int | None = None
    confidence: float = 0.0

    # 텍스트 영역 bbox (크롭 이미지 내 상대 좌표)
    text_x: float = 0.0
    text_y: float = 0.0
    text_w: float = 0.0
    text_h: float = 0.0

    # 원본 프레임 내 bbox (절대 좌표)
    source_bbox_x: float = 0.0
    source_bbox_y: float = 0.0
    source_bbox_w: float = 0.0
    source_bbox_h: float = 0.0

    # 메타
    camera_id: str | None = None
    frame_index: int = 0

    @property
    def is_valid(self) -> bool:
        """유효한 등번호 인식 여부."""
        return (
            self.number is not None
            and 0 <= self.number <= 99
            and self.confidence >= MIN_OCR_CONFIDENCE
        )

    def __repr__(self) -> str:
        num_str = str(self.number) if self.number is not None else "?"
        return (
            f"_JerseyRegion(#{num_str}, conf={self.confidence:.3f}, "
            f"valid={self.is_valid})"
        )


@dataclass(slots=True)
class _TrackState:
    """
    추적 내부 상태 (내부용).

    player_tracker에서 관리하는 단일 트랙 상태.
    칼만 필터 상태 + 매칭 이력 + 생존 카운터.
    """

    track_id: int = 0

    # 최근 bbox (xywh)
    bbox_x: float = 0.0
    bbox_y: float = 0.0
    bbox_w: float = 0.0
    bbox_h: float = 0.0

    # 칼만 상태 벡터 [x, y, w, h, vx, vy, vw, vh]
    state: NDArray[np.float64] | None = None
    covariance: NDArray[np.float64] | None = None

    # 생존 카운터
    age: int = 0  # 총 생존 프레임
    hits: int = 0  # 연속 감지 프레임
    time_since_update: int = 0  # 마지막 감지 후 경과 프레임

    # 클래스 정보
    class_id: int = PLAYER_CLASS_ID_PLAYER
    confidence: float = 0.0

    # 3D 위치 (멀티뷰 삼각측량 시)
    position_3d: NDArray[np.float64] | None = None
    velocity_3d: NDArray[np.float64] | None = None

    @property
    def is_confirmed(self) -> bool:
        """트랙 확정 여부 (min_hits 이상 연속 감지)."""
        return self.hits >= _DEFAULT_MIN_HITS

    @property
    def is_dead(self) -> bool:
        """트랙 사망 여부 (max_age 초과 미감지)."""
        return self.time_since_update > _DEFAULT_MAX_AGE

    @property
    def center(self) -> tuple[float, float]:
        """중심 좌표."""
        return (
            self.bbox_x + self.bbox_w / 2.0,
            self.bbox_y + self.bbox_h / 2.0,
        )

    def __repr__(self) -> str:
        status = "confirmed" if self.is_confirmed else "tentative"
        return (
            f"_TrackState(id={self.track_id}, {status}, "
            f"age={self.age}, hits={self.hits}, "
            f"stale={self.time_since_update})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    # 설정 데이터 클래스 (외부 공개)
    "PlayerDetectorConfig",
    "TeamClassifierConfig",
    "JerseyOCRConfig",
    "ReIDConfig",
    "PlayerTrackerConfig",
    "PlayerIDManagerConfig",
]

__version__: str = "1.0.0"
