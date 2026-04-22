# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: matching_constants.py
설명: 객체 매칭 관련 상수 정의
      - 멀티뷰 객체 대응 매칭 (에피폴라 기하학 기반)
      - 외관/기하학/위치 기반 융합 매칭
      - 헝가리안 알고리즘, 최적 할당 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
- 에피폴라 기하학 (Epipolar Geometry): 다중 뷰 간 대응점 관계
- 헝가리안 알고리즘 (Hungarian Algorithm): 최적 이분 매칭
- 농구 경기에서 선수/공/심판 객체 간 대응 매칭

사용 예시::

    >>> from shared.constants.matching_constants import (
    ...     MatchingStrategy, MatchingStatus, MatchingTargetType
    ... )
    >>> MatchingStrategy.HUNGARIAN.is_optimal
    True
    >>> MatchingStatus.AMBIGUOUS.needs_resolution
    True
    >>> MatchingTargetType.PLAYER.to_korean()
    '선수'
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final


# =============================================================================
# 기본 매칭 가중치 상수
# =============================================================================

# 외관 특징 가중치 (색상, 텍스처, Re-ID 특징 등)
APPEARANCE_WEIGHT: Final[float] = 0.3

# 기하학 특징 가중치 (에피폴라 거리, 삼각측량 오차 등)
GEOMETRY_WEIGHT: Final[float] = 0.5

# 위치 특징 가중치 (3D 위치 예측, 이동 예측 등)
POSITION_WEIGHT: Final[float] = 0.2

# 기본 가중치 합 검증 (외관 + 기하학 + 위치 = 1.0)
_WEIGHT_SUM_BASE: Final[float] = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
assert abs(_WEIGHT_SUM_BASE - 1.0) < 1e-9, (
    f"기본 매칭 가중치 합이 1.0이 아닙니다: {_WEIGHT_SUM_BASE}"
)


# =============================================================================
# 에피폴라 기하학 임계값
# =============================================================================

# 기본 에피폴라 거리 임계값 (픽셀)
# - 대응점이 에피폴라 선으로부터 이 거리 이내면 유효
DEFAULT_EPIPOLAR_THRESHOLD: Final[float] = 3.0

# 엄격한 에피폴라 거리 임계값 (고정밀 매칭용)
STRICT_EPIPOLAR_THRESHOLD: Final[float] = 1.5

# 완화된 에피폴라 거리 임계값 (초기 후보 선별용)
RELAXED_EPIPOLAR_THRESHOLD: Final[float] = 5.0

# 에피폴라 거리 최대 허용 값
MAX_EPIPOLAR_DISTANCE: Final[float] = 10.0

# 에피폴라 선 샘플링 포인트 수
EPIPOLAR_LINE_SAMPLES: Final[int] = 100


# =============================================================================
# 외관 유사도 임계값
# =============================================================================

# 기본 외관 유사도 임계값 (코사인 유사도, 0.0~1.0)
DEFAULT_APPEARANCE_THRESHOLD: Final[float] = 0.7

# 높은 신뢰도 외관 유사도 임계값
HIGH_APPEARANCE_THRESHOLD: Final[float] = 0.85

# 낮은 신뢰도 외관 유사도 임계값 (후보 포함용)
LOW_APPEARANCE_THRESHOLD: Final[float] = 0.5

# 동일 객체 확정 외관 유사도
IDENTITY_APPEARANCE_THRESHOLD: Final[float] = 0.95

# 색상 히스토그램 유사도 임계값
COLOR_HISTOGRAM_THRESHOLD: Final[float] = 0.6

# 텍스처 유사도 임계값
TEXTURE_SIMILARITY_THRESHOLD: Final[float] = 0.5


# =============================================================================
# 위치 기반 매칭 임계값
# =============================================================================

# 2D 위치 매칭 임계값 (픽셀)
POSITION_2D_THRESHOLD: Final[float] = 50.0

# 3D 위치 매칭 임계값 (미터)
POSITION_3D_THRESHOLD: Final[float] = 0.5

# 3D 위치 엄격 매칭 임계값 (미터)
POSITION_3D_STRICT_THRESHOLD: Final[float] = 0.2

# 속도 기반 위치 예측 가중치
VELOCITY_PREDICTION_WEIGHT: Final[float] = 0.7

# 최대 위치 예측 프레임 수
MAX_POSITION_PREDICTION_FRAMES: Final[int] = 5


# =============================================================================
# 헝가리안 알고리즘 파라미터
# =============================================================================

# 헝가리안 알고리즘 최대 비용 (매칭 불가 표시)
HUNGARIAN_MAX_COST: Final[float] = 1e6

# 헝가리안 알고리즘 비용 스케일링 팩터
HUNGARIAN_COST_SCALE: Final[float] = 1000.0

# 최소 매칭 비용 임계값 (이 이상이면 매칭 거부)
MIN_MATCHING_COST_THRESHOLD: Final[float] = 0.8

# 최적 할당 최대 반복 횟수
OPTIMAL_ASSIGNMENT_MAX_ITER: Final[int] = 1000


# =============================================================================
# 크로스뷰 매칭 파라미터
# =============================================================================

# 크로스뷰 매칭 최소 카메라 수
CROSS_VIEW_MIN_CAMERAS: Final[int] = 2

# 크로스뷰 매칭 최소 일관성 비율
CROSS_VIEW_CONSISTENCY_RATIO: Final[float] = 0.7

# 크로스뷰 매칭 최대 후보 수 (카메라당)
CROSS_VIEW_MAX_CANDIDATES: Final[int] = 5

# 크로스뷰 투표 가중치 (뷰 품질 기반)
CROSS_VIEW_VOTE_WEIGHT_QUALITY: Final[float] = 0.6

# 크로스뷰 투표 가중치 (거리 기반)
CROSS_VIEW_VOTE_WEIGHT_DISTANCE: Final[float] = 0.4


# =============================================================================
# 시간적 매칭 파라미터
# =============================================================================

# 시간적 매칭 윈도우 크기 (프레임)
TEMPORAL_MATCHING_WINDOW: Final[int] = 10

# 시간 동기화 허용 오차 (밀리초)
TEMPORAL_SYNC_TOLERANCE_MS: Final[float] = 33.0  # 약 1프레임 @30fps

# 시간적 일관성 가중치
TEMPORAL_CONSISTENCY_WEIGHT: Final[float] = 0.3

# 프레임 간 매칭 최대 시간 차이 (초)
MAX_FRAME_TIME_DIFF: Final[float] = 0.1


# =============================================================================
# 객체 유형별 매칭 파라미터
# =============================================================================

# 선수 매칭 가중치 (외관, 기하학, 위치)
PLAYER_MATCHING_WEIGHTS: Final[tuple[float, float, float]] = (0.35, 0.45, 0.20)

# 공 매칭 가중치 (외관, 기하학, 위치)
BALL_MATCHING_WEIGHTS: Final[tuple[float, float, float]] = (0.15, 0.60, 0.25)

# 심판 매칭 가중치 (외관, 기하학, 위치)
REFEREE_MATCHING_WEIGHTS: Final[tuple[float, float, float]] = (0.40, 0.40, 0.20)


# =============================================================================
# 농구 경기 특화 매칭 파라미터
# =============================================================================

# 같은 팀 선수 매칭 외관 부스트 (유니폼 색상 유사)
SAME_TEAM_APPEARANCE_BOOST: Final[float] = 0.1

# 다른 팀 선수 매칭 외관 페널티
DIFFERENT_TEAM_APPEARANCE_PENALTY: Final[float] = 0.2

# 등번호 일치 시 매칭 보너스
JERSEY_NUMBER_MATCH_BONUS: Final[float] = 0.3

# 등번호 불일치 시 매칭 페널티
JERSEY_NUMBER_MISMATCH_PENALTY: Final[float] = 0.5

# 코트 영역 기반 매칭 가중치
COURT_ZONE_MATCHING_WEIGHT: Final[float] = 0.1


# =============================================================================
# 매칭 품질 및 신뢰도 임계값
# =============================================================================

# 매칭 최소 신뢰도
MIN_MATCH_CONFIDENCE: Final[float] = 0.5

# 매칭 높은 신뢰도 임계값
HIGH_MATCH_CONFIDENCE: Final[float] = 0.85

# 모호한 매칭 판정 유사도 차이
# - Top-1과 Top-2의 차이가 이 값 미만이면 모호
AMBIGUOUS_MATCH_DIFF: Final[float] = 0.1

# 매칭 확정 신뢰도 임계값
CONFIRMED_MATCH_CONFIDENCE: Final[float] = 0.9

# 매칭 결과 캐시 유효 시간 (프레임)
MATCH_CACHE_VALIDITY_FRAMES: Final[int] = 5


# =============================================================================
# 배치 매칭 파라미터
# =============================================================================

# 배치 매칭 최대 객체 수
BATCH_MATCHING_MAX_OBJECTS: Final[int] = 100

# 배치 매칭 청크 크기
BATCH_MATCHING_CHUNK_SIZE: Final[int] = 20

# 병렬 매칭 스레드 수
PARALLEL_MATCHING_THREADS: Final[int] = 4


# =============================================================================
# 비용 행렬 계산 파라미터
# =============================================================================

# 비용 행렬 외관 가중치
COST_MATRIX_APPEARANCE_WEIGHT: Final[float] = 0.3

# 비용 행렬 기하학 가중치
COST_MATRIX_GEOMETRY_WEIGHT: Final[float] = 0.4

# 비용 행렬 시간적 가중치
COST_MATRIX_TEMPORAL_WEIGHT: Final[float] = 0.3

# 비용 행렬 가중치 합 검증
_WEIGHT_SUM_COST_MATRIX: Final[float] = (
    COST_MATRIX_APPEARANCE_WEIGHT + COST_MATRIX_GEOMETRY_WEIGHT
    + COST_MATRIX_TEMPORAL_WEIGHT
)
assert abs(_WEIGHT_SUM_COST_MATRIX - 1.0) < 1e-9, (
    f"비용 행렬 가중치 합이 1.0이 아닙니다: {_WEIGHT_SUM_COST_MATRIX}"
)

# 비용 정규화 최소값 (0 방지)
COST_NORMALIZATION_EPS: Final[float] = 1e-6


# =============================================================================
# 매칭 전략 열거형
# =============================================================================

@unique
class MatchingStrategy(Enum):
    """
    매칭 전략 열거형.

    객체 매칭에 사용되는 알고리즘 전략을 정의합니다.
    """

    # 헝가리안 알고리즘 (최적 이분 매칭)
    HUNGARIAN = "hungarian"

    # 그리디 매칭 (가장 가까운 것부터 순차 매칭)
    GREEDY = "greedy"

    # 경매 알고리즘 (분산 최적화)
    AUCTION = "auction"

    # 에피폴라 우선 매칭 (기하학 제약 우선)
    EPIPOLAR_FIRST = "epipolar_first"

    # 외관 우선 매칭 (외관 유사도 우선)
    APPEARANCE_FIRST = "appearance_first"

    # 융합 매칭 (모든 특징 동시 고려)
    FUSION = "fusion"

    # 계층적 매칭 (다단계 필터링)
    HIERARCHICAL = "hierarchical"

    @property
    def is_optimal(self) -> bool:
        """최적해 보장 여부."""
        return self in _MATCHING_STRATEGY_IS_OPTIMAL

    @property
    def supports_partial_matching(self) -> bool:
        """부분 매칭 지원 여부."""
        return self in _MATCHING_STRATEGY_SUPPORTS_PARTIAL

    @property
    def default_threshold(self) -> float:
        """전략별 기본 임계값."""
        return _MATCHING_STRATEGY_THRESHOLD_MAP[self]

    def to_korean(self) -> str:
        """한글 전략명 반환."""
        return _MATCHING_STRATEGY_KOREAN_MAP[self]


# -- MatchingStrategy 캐시 (직접 할당) --

_MATCHING_STRATEGY_IS_OPTIMAL: frozenset[MatchingStrategy] = frozenset({
    MatchingStrategy.HUNGARIAN,
    MatchingStrategy.AUCTION,
})

_MATCHING_STRATEGY_SUPPORTS_PARTIAL: frozenset[MatchingStrategy] = frozenset({
    MatchingStrategy.GREEDY,
    MatchingStrategy.HIERARCHICAL,
    MatchingStrategy.FUSION,
})

_MATCHING_STRATEGY_THRESHOLD_MAP: dict[MatchingStrategy, float] = {
    MatchingStrategy.HUNGARIAN: 0.7,
    MatchingStrategy.GREEDY: 0.6,
    MatchingStrategy.AUCTION: 0.7,
    MatchingStrategy.EPIPOLAR_FIRST: 0.65,
    MatchingStrategy.APPEARANCE_FIRST: 0.7,
    MatchingStrategy.FUSION: 0.65,
    MatchingStrategy.HIERARCHICAL: 0.6,
}

_MATCHING_STRATEGY_KOREAN_MAP: dict[MatchingStrategy, str] = {
    MatchingStrategy.HUNGARIAN: "헝가리안 알고리즘",
    MatchingStrategy.GREEDY: "그리디 매칭",
    MatchingStrategy.AUCTION: "경매 알고리즘",
    MatchingStrategy.EPIPOLAR_FIRST: "에피폴라 우선",
    MatchingStrategy.APPEARANCE_FIRST: "외관 우선",
    MatchingStrategy.FUSION: "융합 매칭",
    MatchingStrategy.HIERARCHICAL: "계층적 매칭",
}


# =============================================================================
# 매칭 상태 열거형
# =============================================================================

@unique
class MatchingStatus(Enum):
    """
    매칭 상태 열거형.

    객체 매칭 결과의 상태를 정의합니다.
    """

    # 성공적으로 매칭됨
    MATCHED = "matched"

    # 매칭 대상 없음
    UNMATCHED = "unmatched"

    # 모호한 매칭 (여러 후보 존재)
    AMBIGUOUS = "ambiguous"

    # 충돌 (같은 객체에 다중 매칭)
    CONFLICTED = "conflicted"

    # 임계값 미달
    BELOW_THRESHOLD = "below_threshold"

    # 기하학적 제약 위반
    GEOMETRY_VIOLATED = "geometry_violated"

    # 시간적 불일치
    TEMPORAL_INCONSISTENT = "temporal_inconsistent"

    @property
    def is_successful(self) -> bool:
        """성공적인 매칭 여부."""
        return self == MatchingStatus.MATCHED

    @property
    def needs_resolution(self) -> bool:
        """추가 해결 필요 여부."""
        return self in _MATCHING_STATUS_NEEDS_RESOLUTION

    @property
    def can_retry(self) -> bool:
        """재시도 가능 여부."""
        return self in _MATCHING_STATUS_CAN_RETRY

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _MATCHING_STATUS_KOREAN_MAP[self]


# -- MatchingStatus 캐시 (직접 할당) --

_MATCHING_STATUS_NEEDS_RESOLUTION: frozenset[MatchingStatus] = frozenset({
    MatchingStatus.AMBIGUOUS,
    MatchingStatus.CONFLICTED,
})

_MATCHING_STATUS_CAN_RETRY: frozenset[MatchingStatus] = frozenset({
    MatchingStatus.BELOW_THRESHOLD,
    MatchingStatus.TEMPORAL_INCONSISTENT,
})

_MATCHING_STATUS_KOREAN_MAP: dict[MatchingStatus, str] = {
    MatchingStatus.MATCHED: "매칭됨",
    MatchingStatus.UNMATCHED: "매칭 없음",
    MatchingStatus.AMBIGUOUS: "모호함",
    MatchingStatus.CONFLICTED: "충돌",
    MatchingStatus.BELOW_THRESHOLD: "임계값 미달",
    MatchingStatus.GEOMETRY_VIOLATED: "기하학 위반",
    MatchingStatus.TEMPORAL_INCONSISTENT: "시간적 불일치",
}


# =============================================================================
# 매칭 대상 유형 열거형
# =============================================================================

@unique
class MatchingTargetType(Enum):
    """
    매칭 대상 유형 열거형.

    매칭할 객체의 유형을 정의합니다.
    """

    # 선수
    PLAYER = "player"

    # 농구공
    BALL = "ball"

    # 심판
    REFEREE = "referee"

    # 코치/스태프
    COACH = "coach"

    # 일반 사람
    PERSON = "person"

    # 기타 객체
    OTHER = "other"

    @property
    def matching_weights(self) -> tuple[float, float, float]:
        """대상 유형별 매칭 가중치 (외관, 기하학, 위치)."""
        return _MATCHING_TARGET_WEIGHTS_MAP[self]

    @property
    def appearance_threshold(self) -> float:
        """대상 유형별 외관 유사도 임계값."""
        return _MATCHING_TARGET_APPEARANCE_THRESHOLD_MAP[self]

    def to_korean(self) -> str:
        """한글 유형명 반환."""
        return _MATCHING_TARGET_KOREAN_MAP[self]


# -- MatchingTargetType 캐시 (직접 할당) --

_MATCHING_TARGET_WEIGHTS_MAP: dict[MatchingTargetType, tuple[float, float, float]] = {
    MatchingTargetType.PLAYER: PLAYER_MATCHING_WEIGHTS,
    MatchingTargetType.BALL: BALL_MATCHING_WEIGHTS,
    MatchingTargetType.REFEREE: REFEREE_MATCHING_WEIGHTS,
    MatchingTargetType.COACH: (0.35, 0.45, 0.20),
    MatchingTargetType.PERSON: (0.30, 0.50, 0.20),
    MatchingTargetType.OTHER: (0.20, 0.60, 0.20),
}

_MATCHING_TARGET_APPEARANCE_THRESHOLD_MAP: dict[MatchingTargetType, float] = {
    MatchingTargetType.PLAYER: 0.65,
    MatchingTargetType.BALL: 0.50,
    MatchingTargetType.REFEREE: 0.70,
    MatchingTargetType.COACH: 0.65,
    MatchingTargetType.PERSON: 0.60,
    MatchingTargetType.OTHER: 0.55,
}

_MATCHING_TARGET_KOREAN_MAP: dict[MatchingTargetType, str] = {
    MatchingTargetType.PLAYER: "선수",
    MatchingTargetType.BALL: "농구공",
    MatchingTargetType.REFEREE: "심판",
    MatchingTargetType.COACH: "코치",
    MatchingTargetType.PERSON: "일반인",
    MatchingTargetType.OTHER: "기타",
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 기본 매칭 가중치 (정의서 필수)
    "APPEARANCE_WEIGHT",
    "GEOMETRY_WEIGHT",
    "POSITION_WEIGHT",
    "DEFAULT_EPIPOLAR_THRESHOLD",
    "DEFAULT_APPEARANCE_THRESHOLD",

    # 에피폴라 기하학 임계값
    "STRICT_EPIPOLAR_THRESHOLD",
    "RELAXED_EPIPOLAR_THRESHOLD",
    "MAX_EPIPOLAR_DISTANCE",
    "EPIPOLAR_LINE_SAMPLES",

    # 외관 유사도 임계값
    "HIGH_APPEARANCE_THRESHOLD",
    "LOW_APPEARANCE_THRESHOLD",
    "IDENTITY_APPEARANCE_THRESHOLD",
    "COLOR_HISTOGRAM_THRESHOLD",
    "TEXTURE_SIMILARITY_THRESHOLD",

    # 위치 기반 매칭 임계값
    "POSITION_2D_THRESHOLD",
    "POSITION_3D_THRESHOLD",
    "POSITION_3D_STRICT_THRESHOLD",
    "VELOCITY_PREDICTION_WEIGHT",
    "MAX_POSITION_PREDICTION_FRAMES",

    # 헝가리안 알고리즘 파라미터
    "HUNGARIAN_MAX_COST",
    "HUNGARIAN_COST_SCALE",
    "MIN_MATCHING_COST_THRESHOLD",
    "OPTIMAL_ASSIGNMENT_MAX_ITER",

    # 크로스뷰 매칭 파라미터
    "CROSS_VIEW_MIN_CAMERAS",
    "CROSS_VIEW_CONSISTENCY_RATIO",
    "CROSS_VIEW_MAX_CANDIDATES",
    "CROSS_VIEW_VOTE_WEIGHT_QUALITY",
    "CROSS_VIEW_VOTE_WEIGHT_DISTANCE",

    # 시간적 매칭 파라미터
    "TEMPORAL_MATCHING_WINDOW",
    "TEMPORAL_SYNC_TOLERANCE_MS",
    "TEMPORAL_CONSISTENCY_WEIGHT",
    "MAX_FRAME_TIME_DIFF",

    # 객체 유형별 매칭 파라미터
    "PLAYER_MATCHING_WEIGHTS",
    "BALL_MATCHING_WEIGHTS",
    "REFEREE_MATCHING_WEIGHTS",

    # 농구 경기 특화 매칭 파라미터
    "SAME_TEAM_APPEARANCE_BOOST",
    "DIFFERENT_TEAM_APPEARANCE_PENALTY",
    "JERSEY_NUMBER_MATCH_BONUS",
    "JERSEY_NUMBER_MISMATCH_PENALTY",
    "COURT_ZONE_MATCHING_WEIGHT",

    # 매칭 품질 및 신뢰도 임계값
    "MIN_MATCH_CONFIDENCE",
    "HIGH_MATCH_CONFIDENCE",
    "AMBIGUOUS_MATCH_DIFF",
    "CONFIRMED_MATCH_CONFIDENCE",
    "MATCH_CACHE_VALIDITY_FRAMES",

    # 배치 매칭 파라미터
    "BATCH_MATCHING_MAX_OBJECTS",
    "BATCH_MATCHING_CHUNK_SIZE",
    "PARALLEL_MATCHING_THREADS",

    # 비용 행렬 계산 파라미터
    "COST_MATRIX_APPEARANCE_WEIGHT",
    "COST_MATRIX_GEOMETRY_WEIGHT",
    "COST_MATRIX_TEMPORAL_WEIGHT",
    "COST_NORMALIZATION_EPS",

    # 열거형
    "MatchingStrategy",
    "MatchingStatus",
    "MatchingTargetType",
]

# 모듈 버전 정보
__version__ = "1.0.0"
