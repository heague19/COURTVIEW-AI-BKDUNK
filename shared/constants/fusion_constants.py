# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: fusion_constants.py
설명: 멀티뷰 융합(Multi-View Fusion) 관련 상수 정의
      - 멀티카메라 3D 재구성을 위한 융합 파라미터
      - 삼각측량, 뷰 가중치, 신뢰도 임계값 등

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
- 다중 뷰 기하학 (Multiple View Geometry) 이론 기반
- 베이지안 센서 융합 (Bayesian Sensor Fusion) 원리 적용

사용 예시:
    >>> from shared.constants.fusion_constants import FusionStrategy, FusionQuality
    >>> strategy = FusionStrategy.BAYESIAN
    >>> strategy.is_probabilistic
    True
    >>> strategy.to_korean()
    '베이지안 융합'
    >>> quality = FusionQuality.from_score(0.82)
    >>> quality
    <FusionQuality.GOOD: ('good', 0.75, 0.9)>
    >>> quality.is_usable
    True
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final


# =============================================================================
# 뷰 요구사항 상수
# =============================================================================

# 융합을 위한 최소 뷰(카메라) 수
# - 최소 2개 뷰가 있어야 크로스뷰 검증 및 융합 가능
MIN_VIEWS_FOR_FUSION: Final[int] = 2

# 안정적인 융합을 위한 권장 뷰 수
RECOMMENDED_VIEWS_FOR_FUSION: Final[int] = 3

# 고정밀 융합을 위한 최적 뷰 수
OPTIMAL_VIEWS_FOR_FUSION: Final[int] = 4

# 삼각측량을 위한 최소 뷰 수
# - 3D 위치 추정에는 최소 2개의 서로 다른 뷰 필요
MIN_VIEWS_FOR_TRIANGULATION: Final[int] = 2

# 정확한 삼각측량을 위한 권장 뷰 수
RECOMMENDED_VIEWS_FOR_TRIANGULATION: Final[int] = 3

# 최대 처리 가능 동시 뷰 수 (성능 한계)
MAX_VIEWS_FOR_FUSION: Final[int] = 6


# =============================================================================
# 신뢰도 임계값 상수
# =============================================================================

# 융합 결과 신뢰도 임계값 (0.0 ~ 1.0)
# - 이 값 미만인 융합 결과는 신뢰할 수 없음으로 표시
FUSION_CONFIDENCE_THRESHOLD: Final[float] = 0.7

# 높은 신뢰도 임계값 (고품질 결과 판정)
FUSION_HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.85

# 낮은 신뢰도 임계값 (경고 수준)
FUSION_LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.5

# 삼각측량 신뢰도 임계값
# - 3D 위치 추정 결과의 최소 신뢰도
TRIANGULATION_CONFIDENCE_THRESHOLD: Final[float] = 0.8

# 뷰별 감지 신뢰도 최소값
# - 각 뷰의 감지 결과가 융합에 참여하기 위한 최소 신뢰도
VIEW_DETECTION_MIN_CONFIDENCE: Final[float] = 0.5

# 뷰별 감지 신뢰도 가중치 적용 임계값
# - 이 값 이상이면 가중치 1.0, 미만이면 비례 가중치
VIEW_DETECTION_WEIGHT_THRESHOLD: Final[float] = 0.7


# =============================================================================
# 가중치 상수 (융합 알고리즘용)
# =============================================================================

# 외관(Appearance) 특징 가중치
# - 색상, 텍스처, 형태 등 시각적 특징 기반 매칭
APPEARANCE_WEIGHT: Final[float] = 0.3

# 기하학(Geometry) 특징 가중치
# - 에피폴라 제약, 동차 좌표 등 기하학적 일관성 기반
GEOMETRY_WEIGHT: Final[float] = 0.5

# 위치(Position) 특징 가중치
# - 예측된 위치와 관측 위치 간 거리 기반
POSITION_WEIGHT: Final[float] = 0.2

# 시간적 일관성 가중치
# - 이전 프레임과의 시간적 연속성 기반
TEMPORAL_CONSISTENCY_WEIGHT: Final[float] = 0.4

# 속도 일관성 가중치
# - 속도 벡터의 시간적 일관성 기반
VELOCITY_CONSISTENCY_WEIGHT: Final[float] = 0.3

# 크기 일관성 가중치
# - 객체 크기의 뷰 간 일관성 (원근 보정 후)
SIZE_CONSISTENCY_WEIGHT: Final[float] = 0.2

# 가중치 합계 검증 (외관 + 기하학 + 위치 = 1.0)
_WEIGHT_SUM_APPEARANCE_GEOMETRY_POSITION: Final[float] = (
    APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
)
assert abs(_WEIGHT_SUM_APPEARANCE_GEOMETRY_POSITION - 1.0) < 1e-9, (
    f"외관+기하학+위치 가중치 합이 1.0이 아닙니다: "
    f"{_WEIGHT_SUM_APPEARANCE_GEOMETRY_POSITION}"
)


# =============================================================================
# 삼각측량 파라미터
# =============================================================================

# 삼각측량 최대 재투영 오차 (픽셀)
# - 이 값 초과 시 삼각측량 결과 폐기
MAX_REPROJECTION_ERROR_PX: Final[float] = 5.0

# 권장 재투영 오차 (픽셀)
RECOMMENDED_REPROJECTION_ERROR_PX: Final[float] = 2.0

# 삼각측량 정규화 깊이 범위 (미터)
TRIANGULATION_MIN_DEPTH_M: Final[float] = 0.5   # 최소 깊이
TRIANGULATION_MAX_DEPTH_M: Final[float] = 50.0  # 최대 깊이

# 깊이 일관성 임계값 (미터)
# - 뷰 간 추정 깊이 차이 허용 범위
DEPTH_CONSISTENCY_THRESHOLD_M: Final[float] = 1.0

# 기선 길이 비율 임계값
# - 두 카메라 간 기선과 객체 거리의 최소 비율
MIN_BASELINE_RATIO: Final[float] = 0.1

# 광선 교차 최소 각도 (도)
# - 두 광선이 교차하는 최소 각도 (너무 평행하면 불안정)
MIN_RAY_INTERSECTION_ANGLE_DEG: Final[float] = 5.0


# =============================================================================
# 융합 알고리즘 파라미터
# =============================================================================

# RANSAC 반복 횟수 (아웃라이어 제거용)
RANSAC_ITERATIONS: Final[int] = 100

# RANSAC 인라이어 비율 임계값
RANSAC_INLIER_RATIO_THRESHOLD: Final[float] = 0.6

# 칼만 필터 프로세스 노이즈 (위치)
KALMAN_PROCESS_NOISE_POSITION: Final[float] = 0.1

# 칼만 필터 프로세스 노이즈 (속도)
KALMAN_PROCESS_NOISE_VELOCITY: Final[float] = 0.5

# 칼만 필터 측정 노이즈
KALMAN_MEASUREMENT_NOISE: Final[float] = 1.0

# EMA(지수이동평균) 스무딩 계수 (0.0~1.0)
# - 높을수록 최근 값에 가중치
EMA_SMOOTHING_FACTOR: Final[float] = 0.7

# 가중 평균 융합 시 최소 유효 뷰 가중치 합
MIN_TOTAL_VIEW_WEIGHT: Final[float] = 0.5


# =============================================================================
# 충돌 해결 파라미터
# =============================================================================

# 뷰 간 불일치 감지 임계값 (미터)
# - 두 뷰의 추정 위치 차이가 이 값 초과 시 불일치로 판정
VIEW_DISAGREEMENT_THRESHOLD_M: Final[float] = 1.0

# 뷰 간 불일치 해결 전략에서 사용하는 투표 임계값
# - 다수결 투표에서 최소 동의 뷰 비율
VOTING_CONSENSUS_RATIO: Final[float] = 0.5

# 모호성 해결을 위한 히스토리 프레임 수
AMBIGUITY_RESOLUTION_HISTORY_FRAMES: Final[int] = 5


# =============================================================================
# 3D 재구성 파라미터
# =============================================================================

# 3D 포인트 클라우드 최소 점 수
MIN_POINTS_FOR_3D_RECONSTRUCTION: Final[int] = 10

# 3D 재구성 복셀 크기 (미터)
VOXEL_SIZE_M: Final[float] = 0.1

# 3D 재구성 최대 거리 (미터)
MAX_RECONSTRUCTION_DISTANCE_M: Final[float] = 30.0

# 포인트 클라우드 다운샘플링 거리 (미터)
POINT_CLOUD_DOWNSAMPLE_DISTANCE_M: Final[float] = 0.05


# =============================================================================
# 뷰 선택 파라미터
# =============================================================================

# 뷰 품질 점수 최소값 (0.0~1.0)
MIN_VIEW_QUALITY_SCORE: Final[float] = 0.3

# 뷰 가시성 최소 비율
# - 객체가 뷰에서 최소 이 비율 이상 보여야 함
MIN_VISIBILITY_RATIO: Final[float] = 0.5

# 최적 뷰 각도 범위 (도)
# - 객체를 바라보는 최적 각도 범위
OPTIMAL_VIEW_ANGLE_MIN_DEG: Final[float] = 30.0
OPTIMAL_VIEW_ANGLE_MAX_DEG: Final[float] = 60.0

# 뷰 중복 억제 각도 (도)
# - 이 각도 이내의 뷰는 중복으로 간주
VIEW_REDUNDANCY_ANGLE_DEG: Final[float] = 15.0


# =============================================================================
# 융합 전략 열거형
# =============================================================================

@unique
class FusionStrategy(Enum):
    """
    멀티뷰 융합 전략 열거형.

    다양한 융합 알고리즘 전략을 정의합니다.
    """

    # 단순 평균 - 모든 뷰의 결과를 동일 가중치로 평균
    SIMPLE_AVERAGE = "simple_average"

    # 가중 평균 - 신뢰도 기반 가중치 적용
    WEIGHTED_AVERAGE = "weighted_average"

    # 베이지안 융합 - 확률적 융합
    BAYESIAN = "bayesian"

    # 칼만 필터 - 시계열 기반 융합
    KALMAN_FILTER = "kalman_filter"

    # 다수결 투표 - 가장 많은 동의를 받은 결과 선택
    MAJORITY_VOTING = "majority_voting"

    # 최고 신뢰도 선택 - 가장 높은 신뢰도의 단일 뷰 선택
    HIGHEST_CONFIDENCE = "highest_confidence"

    # RANSAC 기반 - 아웃라이어 제거 후 융합
    RANSAC = "ransac"

    # 학습 기반 - 딥러닝 모델을 통한 융합
    LEARNED = "learned"

    @property
    def requires_history(self) -> bool:
        """히스토리 데이터 필요 여부."""
        return self in _FUSION_STRATEGY_REQUIRES_HISTORY

    @property
    def is_probabilistic(self) -> bool:
        """확률적 방법 여부."""
        return self in _FUSION_STRATEGY_IS_PROBABILISTIC

    @property
    def default_weight_type(self) -> str:
        """기본 가중치 타입."""
        return _FUSION_STRATEGY_WEIGHT_TYPE_MAP[self]

    def to_korean(self) -> str:
        """한글 전략명 반환."""
        return _FUSION_STRATEGY_KOREAN_MAP[self]


# -- FusionStrategy 캐시 (직접 할당) --

_FUSION_STRATEGY_REQUIRES_HISTORY: frozenset[FusionStrategy] = frozenset({
    FusionStrategy.KALMAN_FILTER,
    FusionStrategy.LEARNED,
})

_FUSION_STRATEGY_IS_PROBABILISTIC: frozenset[FusionStrategy] = frozenset({
    FusionStrategy.BAYESIAN,
    FusionStrategy.KALMAN_FILTER,
})

_FUSION_STRATEGY_WEIGHT_TYPE_MAP: dict[FusionStrategy, str] = {
    FusionStrategy.SIMPLE_AVERAGE: "uniform",
    FusionStrategy.WEIGHTED_AVERAGE: "confidence",
    FusionStrategy.BAYESIAN: "posterior",
    FusionStrategy.KALMAN_FILTER: "kalman_gain",
    FusionStrategy.MAJORITY_VOTING: "vote_count",
    FusionStrategy.HIGHEST_CONFIDENCE: "max_confidence",
    FusionStrategy.RANSAC: "inlier_count",
    FusionStrategy.LEARNED: "learned_weight",
}

_FUSION_STRATEGY_KOREAN_MAP: dict[FusionStrategy, str] = {
    FusionStrategy.SIMPLE_AVERAGE: "단순 평균",
    FusionStrategy.WEIGHTED_AVERAGE: "가중 평균",
    FusionStrategy.BAYESIAN: "베이지안 융합",
    FusionStrategy.KALMAN_FILTER: "칼만 필터",
    FusionStrategy.MAJORITY_VOTING: "다수결 투표",
    FusionStrategy.HIGHEST_CONFIDENCE: "최고 신뢰도 선택",
    FusionStrategy.RANSAC: "RANSAC",
    FusionStrategy.LEARNED: "학습 기반",
}


# =============================================================================
# 융합 품질 레벨 열거형
# =============================================================================

@unique
class FusionQuality(Enum):
    """
    융합 결과 품질 레벨 열거형.

    융합 결과의 품질을 등급으로 분류합니다.
    """

    EXCELLENT = ("excellent", 0.9, 1.0)     # 우수: 90% 이상
    GOOD = ("good", 0.75, 0.9)              # 양호: 75-90%
    ACCEPTABLE = ("acceptable", 0.6, 0.75)  # 허용: 60-75%
    POOR = ("poor", 0.4, 0.6)               # 저조: 40-60%
    FAILED = ("failed", 0.0, 0.4)           # 실패: 40% 미만

    def __init__(self, level_name: str, min_score: float, max_score: float) -> None:
        """품질 레벨 초기화."""
        self._level_name = level_name
        self._min_score = min_score
        self._max_score = max_score

    @property
    def level_name(self) -> str:
        """레벨 이름."""
        return self._level_name

    @property
    def min_score(self) -> float:
        """최소 점수."""
        return self._min_score

    @property
    def max_score(self) -> float:
        """최대 점수."""
        return self._max_score

    @property
    def score_range(self) -> tuple[float, float]:
        """점수 범위."""
        return (self._min_score, self._max_score)

    @property
    def is_usable(self) -> bool:
        """사용 가능한 품질인지 여부."""
        return self in _FUSION_QUALITY_IS_USABLE

    @classmethod
    def from_score(cls, score: float) -> "FusionQuality":
        """
        점수에서 품질 레벨로 변환.

        Args:
            score: 융합 품질 점수 (0.0~1.0)

        Returns:
            해당 FusionQuality enum

        Raises:
            ValueError: 점수가 0.0~1.0 범위 밖인 경우
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError(
                f"융합 품질 점수는 0.0~1.0 범위여야 합니다: {score}"
            )

        if score >= 0.9:
            return cls.EXCELLENT
        if score >= 0.75:
            return cls.GOOD
        if score >= 0.6:
            return cls.ACCEPTABLE
        if score >= 0.4:
            return cls.POOR
        return cls.FAILED

    def to_korean(self) -> str:
        """한글 품질명 반환."""
        return _FUSION_QUALITY_KOREAN_MAP[self]


# -- FusionQuality 캐시 (직접 할당) --

_FUSION_QUALITY_IS_USABLE: frozenset[FusionQuality] = frozenset({
    FusionQuality.EXCELLENT,
    FusionQuality.GOOD,
    FusionQuality.ACCEPTABLE,
})

_FUSION_QUALITY_KOREAN_MAP: dict[FusionQuality, str] = {
    FusionQuality.EXCELLENT: "우수",
    FusionQuality.GOOD: "양호",
    FusionQuality.ACCEPTABLE: "허용",
    FusionQuality.POOR: "저조",
    FusionQuality.FAILED: "실패",
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 뷰 요구사항
    "MIN_VIEWS_FOR_FUSION",
    "RECOMMENDED_VIEWS_FOR_FUSION",
    "OPTIMAL_VIEWS_FOR_FUSION",
    "MIN_VIEWS_FOR_TRIANGULATION",
    "RECOMMENDED_VIEWS_FOR_TRIANGULATION",
    "MAX_VIEWS_FOR_FUSION",

    # 신뢰도 임계값
    "FUSION_CONFIDENCE_THRESHOLD",
    "FUSION_HIGH_CONFIDENCE_THRESHOLD",
    "FUSION_LOW_CONFIDENCE_THRESHOLD",
    "TRIANGULATION_CONFIDENCE_THRESHOLD",
    "VIEW_DETECTION_MIN_CONFIDENCE",
    "VIEW_DETECTION_WEIGHT_THRESHOLD",

    # 가중치
    "APPEARANCE_WEIGHT",
    "GEOMETRY_WEIGHT",
    "POSITION_WEIGHT",
    "TEMPORAL_CONSISTENCY_WEIGHT",
    "VELOCITY_CONSISTENCY_WEIGHT",
    "SIZE_CONSISTENCY_WEIGHT",

    # 삼각측량 파라미터
    "MAX_REPROJECTION_ERROR_PX",
    "RECOMMENDED_REPROJECTION_ERROR_PX",
    "TRIANGULATION_MIN_DEPTH_M",
    "TRIANGULATION_MAX_DEPTH_M",
    "DEPTH_CONSISTENCY_THRESHOLD_M",
    "MIN_BASELINE_RATIO",
    "MIN_RAY_INTERSECTION_ANGLE_DEG",

    # 융합 알고리즘 파라미터
    "RANSAC_ITERATIONS",
    "RANSAC_INLIER_RATIO_THRESHOLD",
    "KALMAN_PROCESS_NOISE_POSITION",
    "KALMAN_PROCESS_NOISE_VELOCITY",
    "KALMAN_MEASUREMENT_NOISE",
    "EMA_SMOOTHING_FACTOR",
    "MIN_TOTAL_VIEW_WEIGHT",

    # 충돌 해결 파라미터
    "VIEW_DISAGREEMENT_THRESHOLD_M",
    "VOTING_CONSENSUS_RATIO",
    "AMBIGUITY_RESOLUTION_HISTORY_FRAMES",

    # 3D 재구성 파라미터
    "MIN_POINTS_FOR_3D_RECONSTRUCTION",
    "VOXEL_SIZE_M",
    "MAX_RECONSTRUCTION_DISTANCE_M",
    "POINT_CLOUD_DOWNSAMPLE_DISTANCE_M",

    # 뷰 선택 파라미터
    "MIN_VIEW_QUALITY_SCORE",
    "MIN_VISIBILITY_RATIO",
    "OPTIMAL_VIEW_ANGLE_MIN_DEG",
    "OPTIMAL_VIEW_ANGLE_MAX_DEG",
    "VIEW_REDUNDANCY_ANGLE_DEG",

    # 열거형
    "FusionStrategy",
    "FusionQuality",
]

# 모듈 버전 정보
__version__ = "1.0.0"
