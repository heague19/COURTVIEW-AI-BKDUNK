# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: occlusion_constants.py
설명: 오클루전(Occlusion, 가림) 처리 관련 상수 정의
      - 오클루전 감지, 분류, 해결 전략
      - 깊이 추정, 가시성 판단, 보간/예측 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
- 농구 경기에서 선수 간 밀집 상황이 빈번하여 오클루전 처리가 중요
- 멀티뷰 시스템에서 크로스뷰 복구 전략 활용
"""

from enum import Enum, unique
from typing import Final


# =============================================================================
# 오버랩 감지 상수
# =============================================================================

# 바운딩 박스 오버랩 임계값
# - IoU가 이 값 이상이면 오클루전 발생으로 판단
OVERLAP_THRESHOLD: Final[float] = 0.3

# 심각한 오클루전 오버랩 임계값
SEVERE_OVERLAP_THRESHOLD: Final[float] = 0.6

# 완전 오클루전 오버랩 임계값
TOTAL_OVERLAP_THRESHOLD: Final[float] = 0.8

# 부분 오클루전 최소 오버랩
PARTIAL_OVERLAP_MIN_THRESHOLD: Final[float] = 0.15

# 오버랩 면적 비율 임계값 (작은 객체가 가려지는 비율)
AREA_OVERLAP_RATIO_THRESHOLD: Final[float] = 0.5


# =============================================================================
# 깊이 관련 상수
# =============================================================================

# 깊이 차이 임계값 (미터)
# - 두 객체 간 깊이 차이가 이 값 이내이면 같은 평면으로 간주
DEPTH_DIFFERENCE_THRESHOLD: Final[float] = 0.5

# 전경/배경 판단 깊이 차이 (미터)
FOREGROUND_BACKGROUND_DEPTH_DIFF_M: Final[float] = 1.0

# 깊이 추정 불확실성 허용 오차 (미터)
DEPTH_UNCERTAINTY_TOLERANCE_M: Final[float] = 0.3

# 깊이 정렬 최소 차이 (미터)
# - 이 값 미만 차이는 동일 깊이로 처리
DEPTH_SORTING_MIN_DIFF_M: Final[float] = 0.1

# 카메라로부터 최대 유효 깊이 (미터)
MAX_VALID_DEPTH_M: Final[float] = 40.0

# 카메라로부터 최소 유효 깊이 (미터)
MIN_VALID_DEPTH_M: Final[float] = 1.0


# =============================================================================
# 보간 및 예측 상수
# =============================================================================

# 최대 보간 프레임 수
# - 오클루전 중 위치 보간할 최대 프레임
INTERPOLATION_MAX_FRAMES: Final[int] = 10

# 선형 보간 최대 프레임
LINEAR_INTERPOLATION_MAX_FRAMES: Final[int] = 5

# 스플라인 보간 최소 필요 프레임
SPLINE_INTERPOLATION_MIN_FRAMES: Final[int] = 4

# 예측 최대 프레임 수
# - 오클루전 중 위치 예측할 최대 프레임
PREDICTION_MAX_FRAMES: Final[int] = 15

# 예측 신뢰도 감쇠 계수 (프레임당)
# - 각 예측 프레임마다 신뢰도에 이 값을 곱함
PREDICTION_CONFIDENCE_DECAY: Final[float] = 0.9

# 초기 예측 신뢰도
INITIAL_PREDICTION_CONFIDENCE: Final[float] = 0.95

# 최소 예측 신뢰도 (이 값 미만 시 예측 중단)
MIN_PREDICTION_CONFIDENCE: Final[float] = 0.3

# 속도 기반 예측 사용 최소 히스토리 프레임
VELOCITY_PREDICTION_MIN_HISTORY: Final[int] = 3


# =============================================================================
# 가시성 판단 상수
# =============================================================================

# 키포인트 가시성 임계값
# - 키포인트 신뢰도가 이 값 이상이면 가시
KEYPOINT_VISIBILITY_THRESHOLD: Final[float] = 0.5

# 최소 가시 키포인트 비율
# - 전체 키포인트 중 이 비율 이상이 가시여야 추적 유지
MIN_VISIBLE_KEYPOINTS_RATIO: Final[float] = 0.3

# 최소 가시 키포인트 수 (절대값)
MIN_VISIBLE_KEYPOINTS_COUNT: Final[int] = 5

# 신체 주요 키포인트 (반드시 가시여야 함)
# - 어깨, 엉덩이 중 최소 2개
CRITICAL_KEYPOINTS_MIN_VISIBLE: Final[int] = 2

# 바운딩 박스 가시 면적 최소 비율
MIN_VISIBLE_BBOX_RATIO: Final[float] = 0.2

# 완전 가시 판단 면적 비율
FULLY_VISIBLE_BBOX_RATIO: Final[float] = 0.9


# =============================================================================
# 멀티뷰 오클루전 해결 상수
# =============================================================================

# 크로스뷰 복구 최소 뷰 수
CROSS_VIEW_RECOVERY_MIN_VIEWS: Final[int] = 1

# 크로스뷰 복구 신뢰도 임계값
CROSS_VIEW_RECOVERY_CONFIDENCE: Final[float] = 0.6

# 크로스뷰 일치 거리 임계값 (미터)
CROSS_VIEW_MATCH_DISTANCE_M: Final[float] = 0.5

# 뷰 우선순위 결정 가중치 (가시성 기준)
VIEW_PRIORITY_VISIBILITY_WEIGHT: Final[float] = 0.6

# 뷰 우선순위 결정 가중치 (신뢰도 기준)
VIEW_PRIORITY_CONFIDENCE_WEIGHT: Final[float] = 0.4

# 뷰 우선순위 가중치 합 검증
_VIEW_PRIORITY_WEIGHT_SUM: Final[float] = (
    VIEW_PRIORITY_VISIBILITY_WEIGHT + VIEW_PRIORITY_CONFIDENCE_WEIGHT
)
assert abs(_VIEW_PRIORITY_WEIGHT_SUM - 1.0) < 1e-9, (
    f"뷰 우선순위 가중치 합이 1.0이 아닙니다: {_VIEW_PRIORITY_WEIGHT_SUM}"
)


# =============================================================================
# 오클루전 이벤트 상수
# =============================================================================

# 오클루전 시작 감지 연속 프레임
OCCLUSION_START_FRAMES: Final[int] = 2

# 오클루전 종료 감지 연속 프레임
OCCLUSION_END_FRAMES: Final[int] = 3

# 오클루전 최소 지속 시간 (프레임)
MIN_OCCLUSION_DURATION_FRAMES: Final[int] = 2

# 오클루전 최대 허용 지속 시간 (프레임)
# - 이 값 초과 시 트랙 손실로 처리
MAX_OCCLUSION_DURATION_FRAMES: Final[int] = 45

# 오클루전 이벤트 병합 간격 (프레임)
# - 짧은 간격의 오클루전은 하나로 병합
OCCLUSION_MERGE_GAP_FRAMES: Final[int] = 3


# =============================================================================
# 오클루전 유형 열거형
# =============================================================================

@unique
class OcclusionType(Enum):
    """
    오클루전 유형 열거형.

    발생할 수 있는 오클루전의 종류를 정의합니다.
    """

    # 셀프 오클루전 - 자신의 신체 부위가 다른 부위를 가림
    SELF = "self"

    # 선수 간 오클루전 - 다른 선수에 의해 가려짐
    INTER_PLAYER = "inter_player"

    # 코트 오브젝트 오클루전 - 골대, 백보드 등에 의해 가려짐
    COURT_OBJECT = "court_object"

    # 프레임 아웃 - 카메라 시야 밖으로 나감
    OUT_OF_VIEW = "out_of_view"

    # 모션 블러 - 빠른 움직임으로 인한 가림
    MOTION_BLUR = "motion_blur"

    # 조명 - 역광, 그림자 등으로 인한 가림
    LIGHTING = "lighting"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def is_recoverable(self) -> bool:
        """복구 가능한 오클루전 유형인지 여부."""
        return self in _OCCLUSION_TYPE_IS_RECOVERABLE

    @property
    def typical_duration_frames(self) -> tuple[int, int]:
        """일반적인 지속 시간 범위 (최소, 최대 프레임)."""
        return _OCCLUSION_TYPE_DURATION_MAP[self]

    @property
    def recommended_strategy(self) -> "ResolutionStrategy":
        """권장 해결 전략."""
        return _OCCLUSION_TYPE_STRATEGY_MAP[self]

    def to_korean(self) -> str:
        """한글 유형명 반환."""
        return _OCCLUSION_TYPE_KOREAN_MAP[self]


# -- OcclusionType 캐시 (직접 할당, ResolutionStrategy 무관 항목) --

_OCCLUSION_TYPE_IS_RECOVERABLE: frozenset = frozenset({
    OcclusionType.SELF,
    OcclusionType.INTER_PLAYER,
    OcclusionType.COURT_OBJECT,
    OcclusionType.MOTION_BLUR,
})

_OCCLUSION_TYPE_DURATION_MAP: dict[OcclusionType, tuple[int, int]] = {
    OcclusionType.SELF: (1, 10),
    OcclusionType.INTER_PLAYER: (3, 30),
    OcclusionType.COURT_OBJECT: (5, 45),
    OcclusionType.OUT_OF_VIEW: (10, 100),
    OcclusionType.MOTION_BLUR: (1, 5),
    OcclusionType.LIGHTING: (5, 60),
    OcclusionType.UNKNOWN: (1, 30),
}

_OCCLUSION_TYPE_KOREAN_MAP: dict[OcclusionType, str] = {
    OcclusionType.SELF: "셀프 오클루전",
    OcclusionType.INTER_PLAYER: "선수 간 오클루전",
    OcclusionType.COURT_OBJECT: "코트 오브젝트 오클루전",
    OcclusionType.OUT_OF_VIEW: "프레임 아웃",
    OcclusionType.MOTION_BLUR: "모션 블러",
    OcclusionType.LIGHTING: "조명 오클루전",
    OcclusionType.UNKNOWN: "미분류",
}


# =============================================================================
# 오클루전 심각도 열거형
# =============================================================================

@unique
class OcclusionSeverity(Enum):
    """
    오클루전 심각도 열거형.

    오클루전의 심각한 정도를 분류합니다.
    """

    # 없음 - 오클루전 없음
    NONE = ("none", 0.0, 0.0)

    # 경미 - 가장자리만 약간 가려짐
    MINOR = ("minor", 0.0, 0.2)

    # 부분 - 일부가 가려짐
    PARTIAL = ("partial", 0.2, 0.5)

    # 심각 - 대부분 가려짐
    SEVERE = ("severe", 0.5, 0.8)

    # 완전 - 완전히 가려짐
    TOTAL = ("total", 0.8, 1.0)

    def __init__(
        self,
        severity_name: str,
        min_overlap: float,
        max_overlap: float
    ) -> None:
        """심각도 초기화."""
        self._severity_name = severity_name
        self._min_overlap = min_overlap
        self._max_overlap = max_overlap

    @property
    def severity_name(self) -> str:
        """심각도 이름."""
        return self._severity_name

    @property
    def min_overlap(self) -> float:
        """최소 오버랩 비율."""
        return self._min_overlap

    @property
    def max_overlap(self) -> float:
        """최대 오버랩 비율."""
        return self._max_overlap

    @property
    def overlap_range(self) -> tuple[float, float]:
        """오버랩 범위."""
        return (self._min_overlap, self._max_overlap)

    @property
    def is_trackable(self) -> bool:
        """추적 유지 가능 여부."""
        return self in _OCCLUSION_SEVERITY_IS_TRACKABLE

    @property
    def needs_recovery(self) -> bool:
        """복구 필요 여부."""
        return self in _OCCLUSION_SEVERITY_NEEDS_RECOVERY

    @classmethod
    def from_overlap(cls, overlap: float) -> "OcclusionSeverity":
        """
        오버랩 비율에서 심각도로 변환.

        Args:
            overlap: 오버랩 비율 (0.0~1.0)

        Returns:
            해당 OcclusionSeverity enum
        """
        overlap = max(0.0, min(1.0, overlap))
        for severity in cls:
            if severity.min_overlap <= overlap < severity.max_overlap:
                return severity
            if severity == cls.TOTAL and overlap >= severity.min_overlap:
                return severity
        return cls.NONE

    def to_korean(self) -> str:
        """한글 심각도명 반환."""
        return _OCCLUSION_SEVERITY_KOREAN_MAP[self]


# -- OcclusionSeverity 캐시 (직접 할당) --

_OCCLUSION_SEVERITY_IS_TRACKABLE: frozenset = frozenset({
    OcclusionSeverity.NONE,
    OcclusionSeverity.MINOR,
    OcclusionSeverity.PARTIAL,
})

_OCCLUSION_SEVERITY_NEEDS_RECOVERY: frozenset = frozenset({
    OcclusionSeverity.PARTIAL,
    OcclusionSeverity.SEVERE,
    OcclusionSeverity.TOTAL,
})

_OCCLUSION_SEVERITY_KOREAN_MAP: dict[OcclusionSeverity, str] = {
    OcclusionSeverity.NONE: "없음",
    OcclusionSeverity.MINOR: "경미",
    OcclusionSeverity.PARTIAL: "부분",
    OcclusionSeverity.SEVERE: "심각",
    OcclusionSeverity.TOTAL: "완전",
}


# =============================================================================
# 오클루전 해결 전략 열거형
# =============================================================================

@unique
class ResolutionStrategy(Enum):
    """
    오클루전 해결 전략 열거형.

    오클루전 상황에서 객체 위치를 복구하는 전략을 정의합니다.
    """

    # 크로스뷰 - 다른 카메라 뷰에서 가져옴
    CROSS_VIEW = "cross_view"

    # 보간 - 이전/이후 프레임에서 보간
    INTERPOLATION = "interpolation"

    # 예측 - 움직임 모델로 예측
    PREDICTION = "prediction"

    # 칼만 필터 - 칼만 필터로 상태 추정
    KALMAN = "kalman"

    # 외관 매칭 - Re-ID로 재식별
    APPEARANCE_MATCHING = "appearance_matching"

    # 하이브리드 - 여러 전략 조합
    HYBRID = "hybrid"

    # 없음 - 복구하지 않음
    NONE = "none"

    @property
    def requires_multiview(self) -> bool:
        """멀티뷰 필요 여부."""
        return self in _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW

    @property
    def requires_history(self) -> bool:
        """히스토리 필요 여부."""
        return self in _RESOLUTION_STRATEGY_REQUIRES_HISTORY

    @property
    def requires_appearance(self) -> bool:
        """외관 특징 필요 여부."""
        return self in _RESOLUTION_STRATEGY_REQUIRES_APPEARANCE

    @property
    def priority(self) -> int:
        """전략 우선순위 (낮을수록 우선)."""
        return _RESOLUTION_STRATEGY_PRIORITY_MAP[self]

    def to_korean(self) -> str:
        """한글 전략명 반환."""
        return _RESOLUTION_STRATEGY_KOREAN_MAP[self]


# -- ResolutionStrategy 캐시 (직접 할당) --

_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW: frozenset = frozenset({
    ResolutionStrategy.CROSS_VIEW,
})

_RESOLUTION_STRATEGY_REQUIRES_HISTORY: frozenset = frozenset({
    ResolutionStrategy.INTERPOLATION,
    ResolutionStrategy.PREDICTION,
    ResolutionStrategy.KALMAN,
})

_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE: frozenset = frozenset({
    ResolutionStrategy.APPEARANCE_MATCHING,
    ResolutionStrategy.HYBRID,
})

_RESOLUTION_STRATEGY_PRIORITY_MAP: dict[ResolutionStrategy, int] = {
    ResolutionStrategy.CROSS_VIEW: 1,
    ResolutionStrategy.KALMAN: 2,
    ResolutionStrategy.INTERPOLATION: 3,
    ResolutionStrategy.PREDICTION: 4,
    ResolutionStrategy.APPEARANCE_MATCHING: 5,
    ResolutionStrategy.HYBRID: 6,
    ResolutionStrategy.NONE: 99,
}

_RESOLUTION_STRATEGY_KOREAN_MAP: dict[ResolutionStrategy, str] = {
    ResolutionStrategy.CROSS_VIEW: "크로스뷰 복구",
    ResolutionStrategy.INTERPOLATION: "보간",
    ResolutionStrategy.PREDICTION: "예측",
    ResolutionStrategy.KALMAN: "칼만 필터",
    ResolutionStrategy.APPEARANCE_MATCHING: "외관 매칭",
    ResolutionStrategy.HYBRID: "하이브리드",
    ResolutionStrategy.NONE: "없음",
}


# -- OcclusionType 캐시 (ResolutionStrategy 참조, 후방 배치) --

_OCCLUSION_TYPE_STRATEGY_MAP: dict[OcclusionType, ResolutionStrategy] = {
    OcclusionType.SELF: ResolutionStrategy.INTERPOLATION,
    OcclusionType.INTER_PLAYER: ResolutionStrategy.CROSS_VIEW,
    OcclusionType.COURT_OBJECT: ResolutionStrategy.CROSS_VIEW,
    OcclusionType.OUT_OF_VIEW: ResolutionStrategy.PREDICTION,
    OcclusionType.MOTION_BLUR: ResolutionStrategy.INTERPOLATION,
    OcclusionType.LIGHTING: ResolutionStrategy.CROSS_VIEW,
    OcclusionType.UNKNOWN: ResolutionStrategy.PREDICTION,
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 오버랩 감지
    "OVERLAP_THRESHOLD",
    "SEVERE_OVERLAP_THRESHOLD",
    "TOTAL_OVERLAP_THRESHOLD",
    "PARTIAL_OVERLAP_MIN_THRESHOLD",
    "AREA_OVERLAP_RATIO_THRESHOLD",

    # 깊이 관련
    "DEPTH_DIFFERENCE_THRESHOLD",
    "FOREGROUND_BACKGROUND_DEPTH_DIFF_M",
    "DEPTH_UNCERTAINTY_TOLERANCE_M",
    "DEPTH_SORTING_MIN_DIFF_M",
    "MAX_VALID_DEPTH_M",
    "MIN_VALID_DEPTH_M",

    # 보간 및 예측
    "INTERPOLATION_MAX_FRAMES",
    "LINEAR_INTERPOLATION_MAX_FRAMES",
    "SPLINE_INTERPOLATION_MIN_FRAMES",
    "PREDICTION_MAX_FRAMES",
    "PREDICTION_CONFIDENCE_DECAY",
    "INITIAL_PREDICTION_CONFIDENCE",
    "MIN_PREDICTION_CONFIDENCE",
    "VELOCITY_PREDICTION_MIN_HISTORY",

    # 가시성 판단
    "KEYPOINT_VISIBILITY_THRESHOLD",
    "MIN_VISIBLE_KEYPOINTS_RATIO",
    "MIN_VISIBLE_KEYPOINTS_COUNT",
    "CRITICAL_KEYPOINTS_MIN_VISIBLE",
    "MIN_VISIBLE_BBOX_RATIO",
    "FULLY_VISIBLE_BBOX_RATIO",

    # 멀티뷰 복구
    "CROSS_VIEW_RECOVERY_MIN_VIEWS",
    "CROSS_VIEW_RECOVERY_CONFIDENCE",
    "CROSS_VIEW_MATCH_DISTANCE_M",
    "VIEW_PRIORITY_VISIBILITY_WEIGHT",
    "VIEW_PRIORITY_CONFIDENCE_WEIGHT",

    # 오클루전 이벤트
    "OCCLUSION_START_FRAMES",
    "OCCLUSION_END_FRAMES",
    "MIN_OCCLUSION_DURATION_FRAMES",
    "MAX_OCCLUSION_DURATION_FRAMES",
    "OCCLUSION_MERGE_GAP_FRAMES",

    # 열거형
    "OcclusionType",
    "OcclusionSeverity",
    "ResolutionStrategy",
]

# 모듈 버전 정보
__version__ = "1.0.0"
