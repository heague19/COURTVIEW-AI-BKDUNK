# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: reid_constants.py
설명: Re-Identification (재식별) 관련 상수 정의
      - 선수 외관 특징 추출, 갤러리 관리, 매칭 파라미터
      - 오클루전/프레임 아웃 후 동일 인물 재식별을 위한 설정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from enum import Enum, unique
from typing import Final


# =============================================================================
# 특징 벡터 상수
# =============================================================================

# 특징 벡터 차원 (Re-ID 모델 출력)
FEATURE_DIM: Final[int] = 512

# 고차원 특징 벡터 (고급 모델용)
FEATURE_DIM_HIGH: Final[int] = 1024

# 저차원 특징 벡터 (경량 모델용)
FEATURE_DIM_LOW: Final[int] = 256

# 특징 벡터 정규화 여부
NORMALIZE_FEATURES: Final[bool] = True

# 특징 벡터 L2 정규화 epsilon
FEATURE_NORMALIZE_EPS: Final[float] = 1e-12


# =============================================================================
# 유사도 및 거리 임계값
# =============================================================================

# 코사인 유사도 임계값 (0.0~1.0)
# - 이 값 이상이면 동일 인물로 판단
SIMILARITY_THRESHOLD: Final[float] = 0.7

# 높은 신뢰도 유사도 임계값
HIGH_SIMILARITY_THRESHOLD: Final[float] = 0.85

# 낮은 신뢰도 유사도 임계값 (후보 포함)
LOW_SIMILARITY_THRESHOLD: Final[float] = 0.5

# 동일 인물 확정 유사도
IDENTITY_CONFIRMED_SIMILARITY: Final[float] = 0.9

# 유클리드 거리 임계값 (정규화된 특징)
EUCLIDEAN_DISTANCE_THRESHOLD: Final[float] = 1.0

# 마할라노비스 거리 임계값
MAHALANOBIS_DISTANCE_THRESHOLD: Final[float] = 50.0


# =============================================================================
# 갤러리 관리 상수
# =============================================================================

# 갤러리 최대 크기 (인물당 저장할 특징 수)
GALLERY_MAX_SIZE: Final[int] = 100

# 갤러리 최소 크기 (안정적 매칭을 위한 최소 특징 수)
GALLERY_MIN_SIZE: Final[int] = 5

# 갤러리 업데이트 주기 (프레임)
GALLERY_UPDATE_INTERVAL: Final[int] = 5

# 갤러리 특징 최대 나이 (프레임)
# - 이 값 초과한 오래된 특징은 삭제
GALLERY_FEATURE_MAX_AGE: Final[int] = 300

# 갤러리 특징 삭제 비율 (오래된 것부터)
GALLERY_PRUNING_RATIO: Final[float] = 0.2

# 전역 갤러리 최대 인물 수
GLOBAL_GALLERY_MAX_PERSONS: Final[int] = 50


# =============================================================================
# EMA (지수이동평균) 상수
# =============================================================================

# EMA 모멘텀 (특징 벡터 업데이트용)
# - 높을수록 기존 특징 유지, 낮을수록 새 특징 반영
EMA_MOMENTUM: Final[float] = 0.9

# 빠른 적응을 위한 EMA 모멘텀
EMA_MOMENTUM_FAST: Final[float] = 0.7

# 안정적 유지를 위한 EMA 모멘텀
EMA_MOMENTUM_STABLE: Final[float] = 0.95

# 초기 특징 수집 기간 동안의 EMA 모멘텀
EMA_MOMENTUM_INITIAL: Final[float] = 0.5

# EMA 적용 최소 샘플 수
EMA_MIN_SAMPLES: Final[int] = 3


# =============================================================================
# 매칭 파라미터
# =============================================================================

# 1:N 매칭 최대 후보 수
MAX_MATCH_CANDIDATES: Final[int] = 10

# Top-K 매칭에서 K 값
TOPK_MATCHES: Final[int] = 5

# 매칭 신뢰도 최소값
MIN_MATCH_CONFIDENCE: Final[float] = 0.5

# 모호한 매칭 판정 유사도 차이
# - Top-1과 Top-2의 유사도 차이가 이 값 미만이면 모호
AMBIGUOUS_MATCH_DIFF: Final[float] = 0.1

# 리랭킹 활성화 임계값
# - Top-K 중 이 유사도 이상인 후보가 여러 개면 리랭킹 수행
RERANKING_THRESHOLD: Final[float] = 0.6

# k-상호 인접 리랭킹 k1 값
RERANKING_K1: Final[int] = 20

# k-상호 인접 리랭킹 k2 값
RERANKING_K2: Final[int] = 6

# 리랭킹 람다 값
RERANKING_LAMBDA: Final[float] = 0.3


# =============================================================================
# 크로스뷰 Re-ID 파라미터
# =============================================================================

# 크로스뷰 매칭 최소 신뢰도
CROSS_VIEW_MIN_CONFIDENCE: Final[float] = 0.6

# 크로스뷰 일관성 임계값
# - 여러 뷰에서 동일 인물로 매칭된 비율
CROSS_VIEW_CONSISTENCY_THRESHOLD: Final[float] = 0.7

# 크로스뷰 특징 융합 가중치 (뷰 품질 기반)
CROSS_VIEW_FUSION_WEIGHT_QUALITY: Final[float] = 0.6

# 크로스뷰 특징 융합 가중치 (거리 기반)
CROSS_VIEW_FUSION_WEIGHT_DISTANCE: Final[float] = 0.4

# 크로스뷰 융합 가중치 합 검증 (품질 + 거리 = 1.0)
_CROSS_VIEW_FUSION_WEIGHT_SUM: Final[float] = (
    CROSS_VIEW_FUSION_WEIGHT_QUALITY + CROSS_VIEW_FUSION_WEIGHT_DISTANCE
)
assert abs(_CROSS_VIEW_FUSION_WEIGHT_SUM - 1.0) < 1e-9, (
    f"크로스뷰 융합 가중치 합이 1.0이 아닙니다: {_CROSS_VIEW_FUSION_WEIGHT_SUM}"
)


# =============================================================================
# 시간적 일관성 파라미터
# =============================================================================

# 시간적 일관성 윈도우 크기 (프레임)
TEMPORAL_WINDOW_SIZE: Final[int] = 15

# 시간적 일관성 최소 매칭 비율
TEMPORAL_CONSISTENCY_MIN_RATIO: Final[float] = 0.6

# 시간적 평활화 가중치
TEMPORAL_SMOOTHING_WEIGHT: Final[float] = 0.3

# 장기 특징 저장 간격 (프레임)
LONG_TERM_FEATURE_INTERVAL: Final[int] = 30


# =============================================================================
# 외관 특징 추출 파라미터
# =============================================================================

# 입력 이미지 크기 (높이, 너비)
REID_INPUT_SIZE: Final[tuple[int, int]] = (256, 128)

# 고해상도 입력 크기
REID_INPUT_SIZE_HIGH: Final[tuple[int, int]] = (384, 192)

# 최소 바운딩 박스 크기 (특징 추출 가능 최소 크기)
MIN_BBOX_SIZE: Final[tuple[int, int]] = (32, 64)

# 바운딩 박스 확장 비율 (컨텍스트 포함)
BBOX_EXPANSION_RATIO: Final[float] = 1.1

# 특징 추출 배치 크기
FEATURE_EXTRACTION_BATCH_SIZE: Final[int] = 32


# =============================================================================
# 유니폼/등번호 관련 상수 (농구 특화)
# =============================================================================

# 유니폼 색상 유사도 가중치
UNIFORM_COLOR_WEIGHT: Final[float] = 0.3

# 체형 특징 가중치
BODY_SHAPE_WEIGHT: Final[float] = 0.2

# 딥러닝 특징 가중치
DEEP_FEATURE_WEIGHT: Final[float] = 0.5

# 재식별 특징 가중치 합 검증 (유니폼 + 체형 + 딥러닝 = 1.0)
_REID_FEATURE_WEIGHT_SUM: Final[float] = (
    UNIFORM_COLOR_WEIGHT + BODY_SHAPE_WEIGHT + DEEP_FEATURE_WEIGHT
)
assert abs(_REID_FEATURE_WEIGHT_SUM - 1.0) < 1e-9, (
    f"재식별 특징 가중치 합이 1.0이 아닙니다: {_REID_FEATURE_WEIGHT_SUM}"
)

# 색상 히스토그램 빈 수
COLOR_HISTOGRAM_BINS: Final[int] = 32

# 색상 유사도 임계값
COLOR_SIMILARITY_THRESHOLD: Final[float] = 0.7


# =============================================================================
# Re-ID 모델 열거형
# =============================================================================

@unique
class ReIDModel(Enum):
    """
    Re-ID 모델 열거형.

    지원되는 Re-Identification 모델을 정의합니다.
    """

    # OSNet - 경량/고성능 균형
    OSNET = "osnet"

    # OSNet-AIN - Attention 강화
    OSNET_AIN = "osnet_ain"

    # ResNet50 - 일반적 백본
    RESNET50 = "resnet50"

    # ResNet50-IBN - Instance Batch Normalization
    RESNET50_IBN = "resnet50_ibn"

    # MGN - Multiple Granularity Network
    MGN = "mgn"

    # PCB - Part-based Convolutional Baseline
    PCB = "pcb"

    # AGW - Attention Guided Weighted
    AGW = "agw"

    # TransReID - Transformer 기반
    TRANSREID = "transreid"

    # 커스텀 모델
    CUSTOM = "custom"

    @property
    def feature_dim(self) -> int:
        """모델별 기본 특징 차원."""
        return _REID_MODEL_FEATURE_DIM_MAP[self]

    @property
    def input_size(self) -> tuple[int, int]:
        """모델별 입력 크기 (높이, 너비)."""
        return _REID_MODEL_INPUT_SIZE_MAP[self]

    @property
    def is_lightweight(self) -> bool:
        """경량 모델 여부."""
        return self in _REID_MODEL_IS_LIGHTWEIGHT

    def to_korean(self) -> str:
        """한글 모델명 반환."""
        return _REID_MODEL_KOREAN_MAP[self]


# -- ReIDModel 캐시 (직접 할당) --

_REID_MODEL_FEATURE_DIM_MAP: dict[ReIDModel, int] = {
    ReIDModel.OSNET: 512,
    ReIDModel.OSNET_AIN: 512,
    ReIDModel.RESNET50: 2048,
    ReIDModel.RESNET50_IBN: 2048,
    ReIDModel.MGN: 2048,
    ReIDModel.PCB: 1536,
    ReIDModel.AGW: 2048,
    ReIDModel.TRANSREID: 768,
    ReIDModel.CUSTOM: FEATURE_DIM,
}

_REID_MODEL_INPUT_SIZE_MAP: dict[ReIDModel, tuple[int, int]] = {
    ReIDModel.OSNET: (256, 128),
    ReIDModel.OSNET_AIN: (256, 128),
    ReIDModel.RESNET50: (256, 128),
    ReIDModel.RESNET50_IBN: (256, 128),
    ReIDModel.MGN: (384, 128),
    ReIDModel.PCB: (384, 128),
    ReIDModel.AGW: (256, 128),
    ReIDModel.TRANSREID: (256, 128),
    ReIDModel.CUSTOM: REID_INPUT_SIZE,
}

_REID_MODEL_IS_LIGHTWEIGHT: frozenset = frozenset({
    ReIDModel.OSNET,
    ReIDModel.OSNET_AIN,
})

_REID_MODEL_KOREAN_MAP: dict[ReIDModel, str] = {
    ReIDModel.OSNET: "OSNet",
    ReIDModel.OSNET_AIN: "OSNet-AIN",
    ReIDModel.RESNET50: "ResNet50",
    ReIDModel.RESNET50_IBN: "ResNet50-IBN",
    ReIDModel.MGN: "MGN",
    ReIDModel.PCB: "PCB",
    ReIDModel.AGW: "AGW",
    ReIDModel.TRANSREID: "TransReID",
    ReIDModel.CUSTOM: "커스텀",
}


# =============================================================================
# 매칭 상태 열거형
# =============================================================================

@unique
class MatchStatus(Enum):
    """
    매칭 상태 열거형.

    Re-ID 매칭 결과의 상태를 정의합니다.
    """

    # 매칭됨 - 기존 인물과 확실히 매칭
    MATCHED = "matched"

    # 새로운 인물 - 갤러리에 없는 새 인물
    NEW = "new"

    # 모호함 - 여러 후보가 비슷한 유사도
    AMBIGUOUS = "ambiguous"

    # 낮은 품질 - 특징 추출 품질 낮음
    LOW_QUALITY = "low_quality"

    # 실패 - 매칭 실패
    FAILED = "failed"

    @property
    def is_successful(self) -> bool:
        """성공적인 매칭 여부."""
        return self in _MATCH_STATUS_IS_SUCCESSFUL

    @property
    def needs_confirmation(self) -> bool:
        """추가 확인 필요 여부."""
        return self in _MATCH_STATUS_NEEDS_CONFIRMATION

    @property
    def should_retry(self) -> bool:
        """재시도 권장 여부."""
        return self in _MATCH_STATUS_SHOULD_RETRY

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _MATCH_STATUS_KOREAN_MAP[self]


# -- MatchStatus 캐시 (직접 할당) --

_MATCH_STATUS_IS_SUCCESSFUL: frozenset = frozenset({
    MatchStatus.MATCHED,
    MatchStatus.NEW,
})

_MATCH_STATUS_NEEDS_CONFIRMATION: frozenset = frozenset({
    MatchStatus.AMBIGUOUS,
    MatchStatus.LOW_QUALITY,
})

_MATCH_STATUS_SHOULD_RETRY: frozenset = frozenset({
    MatchStatus.LOW_QUALITY,
    MatchStatus.FAILED,
})

_MATCH_STATUS_KOREAN_MAP: dict[MatchStatus, str] = {
    MatchStatus.MATCHED: "매칭됨",
    MatchStatus.NEW: "새로운 인물",
    MatchStatus.AMBIGUOUS: "모호함",
    MatchStatus.LOW_QUALITY: "낮은 품질",
    MatchStatus.FAILED: "실패",
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 특징 벡터
    "FEATURE_DIM",
    "FEATURE_DIM_HIGH",
    "FEATURE_DIM_LOW",
    "NORMALIZE_FEATURES",
    "FEATURE_NORMALIZE_EPS",

    # 유사도 및 거리 임계값
    "SIMILARITY_THRESHOLD",
    "HIGH_SIMILARITY_THRESHOLD",
    "LOW_SIMILARITY_THRESHOLD",
    "IDENTITY_CONFIRMED_SIMILARITY",
    "EUCLIDEAN_DISTANCE_THRESHOLD",
    "MAHALANOBIS_DISTANCE_THRESHOLD",

    # 갤러리 관리
    "GALLERY_MAX_SIZE",
    "GALLERY_MIN_SIZE",
    "GALLERY_UPDATE_INTERVAL",
    "GALLERY_FEATURE_MAX_AGE",
    "GALLERY_PRUNING_RATIO",
    "GLOBAL_GALLERY_MAX_PERSONS",

    # EMA
    "EMA_MOMENTUM",
    "EMA_MOMENTUM_FAST",
    "EMA_MOMENTUM_STABLE",
    "EMA_MOMENTUM_INITIAL",
    "EMA_MIN_SAMPLES",

    # 매칭 파라미터
    "MAX_MATCH_CANDIDATES",
    "TOPK_MATCHES",
    "MIN_MATCH_CONFIDENCE",
    "AMBIGUOUS_MATCH_DIFF",
    "RERANKING_THRESHOLD",
    "RERANKING_K1",
    "RERANKING_K2",
    "RERANKING_LAMBDA",

    # 크로스뷰
    "CROSS_VIEW_MIN_CONFIDENCE",
    "CROSS_VIEW_CONSISTENCY_THRESHOLD",
    "CROSS_VIEW_FUSION_WEIGHT_QUALITY",
    "CROSS_VIEW_FUSION_WEIGHT_DISTANCE",

    # 시간적 일관성
    "TEMPORAL_WINDOW_SIZE",
    "TEMPORAL_CONSISTENCY_MIN_RATIO",
    "TEMPORAL_SMOOTHING_WEIGHT",
    "LONG_TERM_FEATURE_INTERVAL",

    # 외관 특징 추출
    "REID_INPUT_SIZE",
    "REID_INPUT_SIZE_HIGH",
    "MIN_BBOX_SIZE",
    "BBOX_EXPANSION_RATIO",
    "FEATURE_EXTRACTION_BATCH_SIZE",

    # 유니폼/등번호 (농구 특화)
    "UNIFORM_COLOR_WEIGHT",
    "BODY_SHAPE_WEIGHT",
    "DEEP_FEATURE_WEIGHT",
    "COLOR_HISTOGRAM_BINS",
    "COLOR_SIMILARITY_THRESHOLD",

    # 열거형
    "ReIDModel",
    "MatchStatus",
]

# 모듈 버전 정보
__version__ = "1.0.0"
