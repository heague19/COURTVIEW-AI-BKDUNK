# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: tracking_constants.py
설명: 객체 추적(Object Tracking) 관련 상수 정의
      - DeepSORT, ByteTrack 등 추적 알고리즘 파라미터
      - 트랙 생명주기, 연관(Association) 임계값, 칼만 필터 설정 등

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final


# =============================================================================
# 트랙 생명주기 상수
# =============================================================================

# 트랙 최대 나이 (프레임 수)
# - 감지되지 않은 상태로 유지할 최대 프레임 수
# - 이 값 초과 시 트랙 삭제
MAX_TRACK_AGE: Final[int] = 30

# 트랙 최대 나이 (선수용) - 더 긴 유지
MAX_TRACK_AGE_PLAYER: Final[int] = 45

# 트랙 최대 나이 (공용) - 빠른 움직임으로 짧게 유지
MAX_TRACK_AGE_BALL: Final[int] = 15

# 트랙 확정을 위한 최소 연속 감지 횟수 (히트)
# - 이 횟수 이상 연속 감지되어야 확정 트랙으로 승격
MIN_TRACK_HITS: Final[int] = 3

# 선수 트랙 확정 최소 히트
MIN_TRACK_HITS_PLAYER: Final[int] = 3

# 공 트랙 확정 최소 히트 (빠른 확정 필요)
MIN_TRACK_HITS_BALL: Final[int] = 2

# 잠정 트랙 최대 유지 프레임
# - 확정되지 않은 트랙의 최대 생존 기간
TENTATIVE_TRACK_MAX_AGE: Final[int] = 5

# 트랙 삭제 전 유예 프레임 (소프트 삭제)
TRACK_DELETION_GRACE_PERIOD: Final[int] = 3


# =============================================================================
# IoU (Intersection over Union) 임계값
# =============================================================================

# IoU 연관 임계값
# - 바운딩 박스 간 IoU가 이 값 이상이어야 동일 객체로 연관
IOU_THRESHOLD: Final[float] = 0.3

# 높은 신뢰도 감지에 대한 IoU 임계값
IOU_THRESHOLD_HIGH_CONFIDENCE: Final[float] = 0.5

# 낮은 신뢰도 감지에 대한 IoU 임계값 (ByteTrack 2단계 연관)
IOU_THRESHOLD_LOW_CONFIDENCE: Final[float] = 0.2

# NMS (Non-Maximum Suppression) IoU 임계값
NMS_IOU_THRESHOLD: Final[float] = 0.4

# 선수 감지 NMS 임계값 (밀집 상황 고려)
NMS_IOU_THRESHOLD_PLAYER: Final[float] = 0.5

# 공 감지 NMS 임계값 (작은 객체)
NMS_IOU_THRESHOLD_BALL: Final[float] = 0.3


# =============================================================================
# 거리 임계값 (픽셀 단위)
# =============================================================================

# 중심점 거리 연관 임계값 (픽셀)
# - 바운딩 박스 중심 간 거리가 이 값 이하여야 연관
DISTANCE_THRESHOLD: Final[float] = 100.0

# 선수 거리 임계값 (더 넓은 범위)
DISTANCE_THRESHOLD_PLAYER: Final[float] = 150.0

# 공 거리 임계값 (빠른 움직임 고려)
DISTANCE_THRESHOLD_BALL: Final[float] = 200.0

# 마할라노비스 거리 임계값 (칼만 필터용)
MAHALANOBIS_THRESHOLD: Final[float] = 9.4877  # chi2inv95(4)

# 유클리드 거리 최대값 (정규화 후)
MAX_EUCLIDEAN_DISTANCE: Final[float] = 1.0


# =============================================================================
# 속도 및 움직임 상수
# =============================================================================

# 속도 스무딩 계수 (0.0~1.0)
# - EMA 계산에서 이전 속도의 가중치
VELOCITY_SMOOTHING: Final[float] = 0.3

# 선수 속도 스무딩 (더 부드러운 움직임)
VELOCITY_SMOOTHING_PLAYER: Final[float] = 0.4

# 공 속도 스무딩 (빠른 변화 추적)
VELOCITY_SMOOTHING_BALL: Final[float] = 0.2

# 최대 허용 속도 (픽셀/프레임)
MAX_VELOCITY_PX_PER_FRAME: Final[float] = 100.0

# 선수 최대 속도 (픽셀/프레임)
MAX_VELOCITY_PLAYER_PX_PER_FRAME: Final[float] = 50.0

# 공 최대 속도 (픽셀/프레임)
MAX_VELOCITY_BALL_PX_PER_FRAME: Final[float] = 150.0

# 정지 상태 판정 속도 임계값 (픽셀/프레임)
STATIONARY_VELOCITY_THRESHOLD: Final[float] = 2.0

# 급격한 방향 전환 각도 임계값 (도)
SUDDEN_DIRECTION_CHANGE_ANGLE_DEG: Final[float] = 90.0


# =============================================================================
# 칼만 필터 파라미터
# =============================================================================

# 상태 벡터 차원 (x, y, aspect_ratio, height, vx, vy, va, vh)
KALMAN_STATE_DIM: Final[int] = 8

# 측정 벡터 차원 (x, y, aspect_ratio, height)
KALMAN_MEASUREMENT_DIM: Final[int] = 4

# 프로세스 노이즈 표준편차 (위치)
KALMAN_STD_WEIGHT_POSITION: Final[float] = 1.0 / 20.0

# 프로세스 노이즈 표준편차 (속도)
KALMAN_STD_WEIGHT_VELOCITY: Final[float] = 1.0 / 160.0

# 측정 노이즈 표준편차
KALMAN_STD_WEIGHT_MEASUREMENT: Final[float] = 1.0 / 20.0

# 초기 공분산 스케일
KALMAN_INITIAL_COVARIANCE_SCALE: Final[float] = 10.0

# 칼만 이득 최소값 (수치 안정성)
KALMAN_GAIN_MIN: Final[float] = 0.01

# 칼만 이득 최대값
KALMAN_GAIN_MAX: Final[float] = 0.99


# =============================================================================
# 트랙 히스토리 상수
# =============================================================================

# 트랙 위치 히스토리 최대 길이
TRACK_HISTORY_MAX_LENGTH: Final[int] = 100

# 트랙 속도 히스토리 최대 길이
VELOCITY_HISTORY_MAX_LENGTH: Final[int] = 30

# 트랙 특징 히스토리 최대 길이 (Re-ID용)
FEATURE_HISTORY_MAX_LENGTH: Final[int] = 50

# 궤적 시각화용 히스토리 길이
TRAJECTORY_DISPLAY_LENGTH: Final[int] = 30


# =============================================================================
# 비용 행렬 및 연관 파라미터
# =============================================================================

# 연관 비용 상한값 (이 값 초과 시 연관 불가)
ASSOCIATION_COST_THRESHOLD: Final[float] = 0.8

# 외관 특징 비용 가중치
APPEARANCE_COST_WEIGHT: Final[float] = 0.5

# 움직임 비용 가중치
MOTION_COST_WEIGHT: Final[float] = 0.5

# 비용 가중치 합 검증 (외관 + 움직임 = 1.0)
_ASSOCIATION_COST_WEIGHT_SUM: Final[float] = APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT
assert abs(_ASSOCIATION_COST_WEIGHT_SUM - 1.0) < 1e-9, (
    f"비용 가중치 합이 1.0이 아닙니다: {_ASSOCIATION_COST_WEIGHT_SUM}"
)

# 게이트 비용 (범위 밖 연관 방지)
GATING_COST: Final[float] = 1e5

# 최대 연관 거리 (코사인 거리)
MAX_COSINE_DISTANCE: Final[float] = 0.4

# 최대 연관 거리 (Re-ID 특징)
MAX_REID_DISTANCE: Final[float] = 0.3


# =============================================================================
# ByteTrack 특화 파라미터
# =============================================================================

# 높은 신뢰도 감지 임계값
BYTETRACK_HIGH_THRESHOLD: Final[float] = 0.6

# 낮은 신뢰도 감지 임계값
BYTETRACK_LOW_THRESHOLD: Final[float] = 0.1

# 새 트랙 생성 신뢰도 임계값
BYTETRACK_NEW_TRACK_THRESHOLD: Final[float] = 0.7

# 2단계 연관 활성화 여부
BYTETRACK_SECOND_ASSOCIATION_ENABLED: Final[bool] = True


# =============================================================================
# 트랙 상태 열거형
# =============================================================================

@unique
class TrackState(Enum):
    """
    트랙 상태 열거형.

    트랙의 생명주기 상태를 정의합니다.

    사용 예시::

        >>> state = TrackState.TRACKED
        >>> state.is_active
        True
        >>> state.to_korean()
        '추적 중'
        >>> TrackingTarget.BALL.default_max_age
        15
        >>> TrackingAlgorithm.DEEPSORT.uses_appearance
        True
    """

    # 잠정 - 아직 확정되지 않은 새 트랙
    TENTATIVE = "tentative"

    # 확정 - 충분한 히트로 확정된 트랙
    CONFIRMED = "confirmed"

    # 추적 중 - 현재 활발하게 추적 중
    TRACKED = "tracked"

    # 손실 - 일시적으로 감지되지 않음
    LOST = "lost"

    # 가려짐 - 오클루전으로 인해 보이지 않음
    OCCLUDED = "occluded"

    # 삭제 예정 - 곧 삭제될 트랙
    DELETED = "deleted"

    @property
    def is_active(self) -> bool:
        """활성 상태 여부 (추적 중이거나 확정됨)."""
        return self in _TRACK_STATE_IS_ACTIVE

    @property
    def is_visible(self) -> bool:
        """가시 상태 여부."""
        return self in _TRACK_STATE_IS_VISIBLE

    @property
    def can_associate(self) -> bool:
        """연관 가능 여부."""
        return self in _TRACK_STATE_CAN_ASSOCIATE

    @property
    def needs_prediction(self) -> bool:
        """예측 필요 여부."""
        return self in _TRACK_STATE_NEEDS_PREDICTION

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _TRACK_STATE_KOREAN_MAP[self]


# -- TrackState 캐시 (직접 할당) --

_TRACK_STATE_IS_ACTIVE: frozenset[TrackState] = frozenset({
    TrackState.CONFIRMED,
    TrackState.TRACKED,
})

_TRACK_STATE_IS_VISIBLE: frozenset[TrackState] = frozenset({
    TrackState.CONFIRMED,
    TrackState.TRACKED,
    TrackState.TENTATIVE,
})

_TRACK_STATE_CAN_ASSOCIATE: frozenset[TrackState] = frozenset({
    TrackState.TENTATIVE,
    TrackState.CONFIRMED,
    TrackState.TRACKED,
    TrackState.LOST,
    TrackState.OCCLUDED,
})

_TRACK_STATE_NEEDS_PREDICTION: frozenset[TrackState] = frozenset({
    TrackState.LOST,
    TrackState.OCCLUDED,
})

_TRACK_STATE_KOREAN_MAP: dict[TrackState, str] = {
    TrackState.TENTATIVE: "잠정",
    TrackState.CONFIRMED: "확정",
    TrackState.TRACKED: "추적 중",
    TrackState.LOST: "손실",
    TrackState.OCCLUDED: "가려짐",
    TrackState.DELETED: "삭제",
}


# =============================================================================
# 추적 대상 유형 열거형
# =============================================================================

@unique
class TrackingTarget(Enum):
    """
    추적 대상 유형 열거형.

    추적할 수 있는 객체 유형을 정의합니다.
    """

    PLAYER = "player"       # 선수
    BALL = "ball"           # 공
    REFEREE = "referee"     # 심판
    COACH = "coach"         # 코치
    HOOP = "hoop"           # 골대 (정적)
    UNKNOWN = "unknown"     # 알 수 없음

    @property
    def is_person(self) -> bool:
        """사람 여부."""
        return self in _TRACKING_TARGET_IS_PERSON

    @property
    def is_dynamic(self) -> bool:
        """동적 객체 여부."""
        return self in _TRACKING_TARGET_IS_DYNAMIC

    @property
    def default_max_age(self) -> int:
        """기본 최대 나이."""
        return _TRACKING_TARGET_MAX_AGE_MAP[self]

    @property
    def default_min_hits(self) -> int:
        """기본 최소 히트."""
        return _TRACKING_TARGET_MIN_HITS_MAP[self]

    def to_korean(self) -> str:
        """한글 대상명 반환."""
        return _TRACKING_TARGET_KOREAN_MAP[self]


# -- TrackingTarget 캐시 (직접 할당) --

_TRACKING_TARGET_IS_PERSON: frozenset[TrackingTarget] = frozenset({
    TrackingTarget.PLAYER,
    TrackingTarget.REFEREE,
    TrackingTarget.COACH,
})

_TRACKING_TARGET_IS_DYNAMIC: frozenset[TrackingTarget] = frozenset({
    TrackingTarget.PLAYER,
    TrackingTarget.BALL,
    TrackingTarget.REFEREE,
    TrackingTarget.COACH,
    TrackingTarget.UNKNOWN,
})

_TRACKING_TARGET_MAX_AGE_MAP: dict[TrackingTarget, int] = {
    TrackingTarget.PLAYER: MAX_TRACK_AGE_PLAYER,
    TrackingTarget.BALL: MAX_TRACK_AGE_BALL,
    TrackingTarget.REFEREE: MAX_TRACK_AGE_PLAYER,
    TrackingTarget.COACH: MAX_TRACK_AGE_PLAYER,
    TrackingTarget.HOOP: 1000,
    TrackingTarget.UNKNOWN: MAX_TRACK_AGE,
}

_TRACKING_TARGET_MIN_HITS_MAP: dict[TrackingTarget, int] = {
    TrackingTarget.PLAYER: MIN_TRACK_HITS_PLAYER,
    TrackingTarget.BALL: MIN_TRACK_HITS_BALL,
    TrackingTarget.REFEREE: MIN_TRACK_HITS_PLAYER,
    TrackingTarget.COACH: MIN_TRACK_HITS_PLAYER,
    TrackingTarget.HOOP: 5,
    TrackingTarget.UNKNOWN: MIN_TRACK_HITS,
}

_TRACKING_TARGET_KOREAN_MAP: dict[TrackingTarget, str] = {
    TrackingTarget.PLAYER: "선수",
    TrackingTarget.BALL: "공",
    TrackingTarget.REFEREE: "심판",
    TrackingTarget.COACH: "코치",
    TrackingTarget.HOOP: "골대",
    TrackingTarget.UNKNOWN: "미분류",
}


# =============================================================================
# 추적 알고리즘 열거형
# =============================================================================

@unique
class TrackingAlgorithm(Enum):
    """
    추적 알고리즘 열거형.

    지원되는 객체 추적 알고리즘을 정의합니다.
    """

    SORT = "sort"               # Simple Online Realtime Tracking
    DEEPSORT = "deepsort"       # Deep Association Metric 기반
    BYTETRACK = "bytetrack"     # 모든 감지 활용
    OCSORT = "ocsort"           # Observation-Centric SORT
    BOTSORT = "botsort"         # BoT-SORT (Camera Motion Compensation)
    STRONGSORT = "strongsort"   # StrongSORT (향상된 DeepSORT)

    @property
    def uses_appearance(self) -> bool:
        """외관 특징 사용 여부."""
        return self in _TRACKING_ALGORITHM_USES_APPEARANCE

    @property
    def uses_motion_compensation(self) -> bool:
        """카메라 움직임 보상 사용 여부."""
        return self in _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION

    @property
    def default_iou_threshold(self) -> float:
        """기본 IoU 임계값."""
        return _TRACKING_ALGORITHM_IOU_MAP[self]

    def to_korean(self) -> str:
        """한글 알고리즘명 반환."""
        return _TRACKING_ALGORITHM_KOREAN_MAP[self]


# -- TrackingAlgorithm 캐시 (직접 할당) --

_TRACKING_ALGORITHM_USES_APPEARANCE: frozenset[TrackingAlgorithm] = frozenset({
    TrackingAlgorithm.DEEPSORT,
    TrackingAlgorithm.BOTSORT,
    TrackingAlgorithm.STRONGSORT,
})

_TRACKING_ALGORITHM_USES_MOTION_COMPENSATION: frozenset[TrackingAlgorithm] = frozenset({
    TrackingAlgorithm.BOTSORT,
    TrackingAlgorithm.OCSORT,
})

_TRACKING_ALGORITHM_IOU_MAP: dict[TrackingAlgorithm, float] = {
    TrackingAlgorithm.SORT: 0.3,
    TrackingAlgorithm.DEEPSORT: 0.3,
    TrackingAlgorithm.BYTETRACK: 0.3,
    TrackingAlgorithm.OCSORT: 0.3,
    TrackingAlgorithm.BOTSORT: 0.2,
    TrackingAlgorithm.STRONGSORT: 0.3,
}

_TRACKING_ALGORITHM_KOREAN_MAP: dict[TrackingAlgorithm, str] = {
    TrackingAlgorithm.SORT: "SORT",
    TrackingAlgorithm.DEEPSORT: "DeepSORT",
    TrackingAlgorithm.BYTETRACK: "ByteTrack",
    TrackingAlgorithm.OCSORT: "OC-SORT",
    TrackingAlgorithm.BOTSORT: "BoT-SORT",
    TrackingAlgorithm.STRONGSORT: "StrongSORT",
}


# =============================================================================
# ID 관리 상수
# =============================================================================

# 최대 트랙 ID (순환 방지)
MAX_TRACK_ID: Final[int] = 1_000_000

# ID 재사용 대기 프레임
ID_REUSE_WAIT_FRAMES: Final[int] = 100

# 동시 최대 활성 트랙 수
MAX_ACTIVE_TRACKS: Final[int] = 50

# 동시 최대 선수 트랙 수
MAX_ACTIVE_PLAYER_TRACKS: Final[int] = 20


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 트랙 생명주기
    "MAX_TRACK_AGE",
    "MAX_TRACK_AGE_PLAYER",
    "MAX_TRACK_AGE_BALL",
    "MIN_TRACK_HITS",
    "MIN_TRACK_HITS_PLAYER",
    "MIN_TRACK_HITS_BALL",
    "TENTATIVE_TRACK_MAX_AGE",
    "TRACK_DELETION_GRACE_PERIOD",

    # IoU 임계값
    "IOU_THRESHOLD",
    "IOU_THRESHOLD_HIGH_CONFIDENCE",
    "IOU_THRESHOLD_LOW_CONFIDENCE",
    "NMS_IOU_THRESHOLD",
    "NMS_IOU_THRESHOLD_PLAYER",
    "NMS_IOU_THRESHOLD_BALL",

    # 거리 임계값
    "DISTANCE_THRESHOLD",
    "DISTANCE_THRESHOLD_PLAYER",
    "DISTANCE_THRESHOLD_BALL",
    "MAHALANOBIS_THRESHOLD",
    "MAX_EUCLIDEAN_DISTANCE",

    # 속도 및 움직임
    "VELOCITY_SMOOTHING",
    "VELOCITY_SMOOTHING_PLAYER",
    "VELOCITY_SMOOTHING_BALL",
    "MAX_VELOCITY_PX_PER_FRAME",
    "MAX_VELOCITY_PLAYER_PX_PER_FRAME",
    "MAX_VELOCITY_BALL_PX_PER_FRAME",
    "STATIONARY_VELOCITY_THRESHOLD",
    "SUDDEN_DIRECTION_CHANGE_ANGLE_DEG",

    # 칼만 필터
    "KALMAN_STATE_DIM",
    "KALMAN_MEASUREMENT_DIM",
    "KALMAN_STD_WEIGHT_POSITION",
    "KALMAN_STD_WEIGHT_VELOCITY",
    "KALMAN_STD_WEIGHT_MEASUREMENT",
    "KALMAN_INITIAL_COVARIANCE_SCALE",
    "KALMAN_GAIN_MIN",
    "KALMAN_GAIN_MAX",

    # 트랙 히스토리
    "TRACK_HISTORY_MAX_LENGTH",
    "VELOCITY_HISTORY_MAX_LENGTH",
    "FEATURE_HISTORY_MAX_LENGTH",
    "TRAJECTORY_DISPLAY_LENGTH",

    # 비용 행렬 및 연관
    "ASSOCIATION_COST_THRESHOLD",
    "APPEARANCE_COST_WEIGHT",
    "MOTION_COST_WEIGHT",
    "GATING_COST",
    "MAX_COSINE_DISTANCE",
    "MAX_REID_DISTANCE",

    # ByteTrack 파라미터
    "BYTETRACK_HIGH_THRESHOLD",
    "BYTETRACK_LOW_THRESHOLD",
    "BYTETRACK_NEW_TRACK_THRESHOLD",
    "BYTETRACK_SECOND_ASSOCIATION_ENABLED",

    # 열거형
    "TrackState",
    "TrackingTarget",
    "TrackingAlgorithm",

    # ID 관리
    "MAX_TRACK_ID",
    "ID_REUSE_WAIT_FRAMES",
    "MAX_ACTIVE_TRACKS",
    "MAX_ACTIVE_PLAYER_TRACKS",
]

# 모듈 버전 정보
__version__ = "1.0.0"
