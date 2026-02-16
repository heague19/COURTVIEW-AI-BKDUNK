# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: referee_rule_constants.py
설명: AI 심판 시스템 도메인 상수 정의
      - 리그 규정 세트 (FIBA/NBA/KBL/NBL/EUROLEAGUE)
      - 판정 유형, 심판 수신호 (FIBA 공식)
      - 리뷰 트리거, 결과, 심판 역할
      - 리그별 규칙 차이값 (쿼터 시간, 파울 퇴장 기준 등)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from enum import Enum, unique
from typing import Final


# =============================================================================
# 리그 규정 세트 (5종)
# =============================================================================
@unique
class RuleSet(str, Enum):
    """
    농구 규정 세트 열거형 (5종).

    전 세계 주요 농구 리그의 심판 규정.
    각 리그별 규칙 차이 (쿼터 시간, 3점 라인 거리, 타임아웃 수 등)를
    property로 제공하여 리그 전환 시 자동 적용.
    """

    FIBA = "fiba"
    NBA = "nba"
    KBL = "kbl"
    NBL = "nbl"
    EUROLEAGUE = "euroleague"

    @property
    def korean_name(self) -> str:
        """한글 규정명."""
        return _RULE_SET_KOREAN_MAP[self]

    @property
    def quarter_duration_sec(self) -> int:
        """쿼터 시간 (초)."""
        return _RULE_SET_QUARTER_DURATION_MAP[self]

    @property
    def shot_clock_seconds(self) -> int:
        """샷클락 제한시간 (초)."""
        return 24  # 모든 규정 공통

    @property
    def backcourt_seconds(self) -> int:
        """백코트 제한시간 (초)."""
        return _RULE_SET_BACKCOURT_SEC_MAP[self]

    @property
    def three_point_distance_meters(self) -> float:
        """3점 라인 거리 (미터)."""
        return _RULE_SET_THREE_POINT_DISTANCE_MAP[self]

    @property
    def max_personal_fouls(self) -> int:
        """개인 파울 퇴장 기준."""
        return _RULE_SET_MAX_PERSONAL_FOULS_MAP[self]

    @property
    def max_timeouts(self) -> int:
        """최대 타임아웃 수."""
        return _RULE_SET_MAX_TIMEOUTS_MAP[self]

    @property
    def has_defensive_three_seconds(self) -> bool:
        """수비 3초 룰 적용 여부."""
        return self in _RULE_SET_HAS_DEFENSIVE_THREE_SEC


# -- RuleSet 캐시 (직접 할당) --
_RULE_SET_KOREAN_MAP: Final[dict[RuleSet, str]] = {
    RuleSet.FIBA: "국제농구연맹",
    RuleSet.NBA: "미국 프로농구",
    RuleSet.KBL: "한국프로농구",
    RuleSet.NBL: "호주 프로농구",
    RuleSet.EUROLEAGUE: "유럽 농구리그",
}

_RULE_SET_QUARTER_DURATION_MAP: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 600,        # 10분
    RuleSet.NBA: 720,         # 12분
    RuleSet.KBL: 600,         # 10분 (FIBA 준용)
    RuleSet.NBL: 600,         # 10분 (FIBA 준용)
    RuleSet.EUROLEAGUE: 600,  # 10분 (FIBA 준용)
}

_RULE_SET_BACKCOURT_SEC_MAP: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 8,
    RuleSet.NBA: 8,
    RuleSet.KBL: 8,
    RuleSet.NBL: 8,
    RuleSet.EUROLEAGUE: 8,
}

_RULE_SET_THREE_POINT_DISTANCE_MAP: Final[dict[RuleSet, float]] = {
    RuleSet.FIBA: 6.75,
    RuleSet.NBA: 7.24,
    RuleSet.KBL: 6.75,       # FIBA 기준
    RuleSet.NBL: 6.75,       # FIBA 기준
    RuleSet.EUROLEAGUE: 6.75,  # FIBA 기준
}

_RULE_SET_MAX_PERSONAL_FOULS_MAP: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 5,
    RuleSet.NBA: 6,
    RuleSet.KBL: 5,
    RuleSet.NBL: 5,
    RuleSet.EUROLEAGUE: 5,
}

_RULE_SET_MAX_TIMEOUTS_MAP: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 5,
    RuleSet.NBA: 7,
    RuleSet.KBL: 5,
    RuleSet.NBL: 5,
    RuleSet.EUROLEAGUE: 5,
}

_RULE_SET_HAS_DEFENSIVE_THREE_SEC: Final[frozenset[RuleSet]] = frozenset({
    RuleSet.NBA,  # NBA 전용 규칙
})


# =============================================================================
# 판정 유형 (15종)
# =============================================================================
@unique
class CallType(str, Enum):
    """
    판정 유형 열거형 (15종).

    심판이 내릴 수 있는 모든 판정 유형.
    파울(5) + 바이올레이션(5) + 특수(5).
    """

    # 파울 관련 (5)
    PERSONAL_FOUL = "personal_foul"
    SHOOTING_FOUL = "shooting_foul"
    OFFENSIVE_FOUL = "offensive_foul"
    TECHNICAL_FOUL = "technical_foul"
    FLAGRANT_FOUL = "flagrant_foul"
    # 바이올레이션 관련 (5)
    TRAVELING = "traveling"
    DOUBLE_DRIBBLE = "double_dribble"
    OUT_OF_BOUNDS = "out_of_bounds"
    SHOT_CLOCK_VIOLATION = "shot_clock_violation"
    BACKCOURT_VIOLATION = "backcourt_violation"
    # 특수 판정 (5)
    JUMP_BALL = "jump_ball"
    TIMEOUT = "timeout"
    SUBSTITUTION = "substitution"
    NO_CALL = "no_call"
    REVIEW = "review"

    @property
    def korean_name(self) -> str:
        """한글 판정명."""
        return _CALL_TYPE_KOREAN_MAP[self]

    @property
    def stops_play(self) -> bool:
        """경기 중단 여부."""
        return self not in _CALL_TYPE_NO_STOP

    @property
    def is_foul(self) -> bool:
        """파울 판정 여부."""
        return self in _CALL_TYPE_IS_FOUL

    @property
    def is_violation(self) -> bool:
        """바이올레이션 판정 여부."""
        return self in _CALL_TYPE_IS_VIOLATION


# -- CallType 캐시 (직접 할당) --
_CALL_TYPE_IS_FOUL: Final[frozenset[CallType]] = frozenset({
    CallType.PERSONAL_FOUL, CallType.SHOOTING_FOUL, CallType.OFFENSIVE_FOUL,
    CallType.TECHNICAL_FOUL, CallType.FLAGRANT_FOUL,
})

_CALL_TYPE_IS_VIOLATION: Final[frozenset[CallType]] = frozenset({
    CallType.TRAVELING, CallType.DOUBLE_DRIBBLE, CallType.OUT_OF_BOUNDS,
    CallType.SHOT_CLOCK_VIOLATION, CallType.BACKCOURT_VIOLATION,
})

_CALL_TYPE_NO_STOP: Final[frozenset[CallType]] = frozenset({
    CallType.NO_CALL,
})

_CALL_TYPE_KOREAN_MAP: Final[dict[CallType, str]] = {
    CallType.PERSONAL_FOUL: "개인 파울",
    CallType.SHOOTING_FOUL: "슈팅 파울",
    CallType.OFFENSIVE_FOUL: "공격 파울",
    CallType.TECHNICAL_FOUL: "테크니컬 파울",
    CallType.FLAGRANT_FOUL: "플래그런트 파울",
    CallType.TRAVELING: "트래블링",
    CallType.DOUBLE_DRIBBLE: "더블 드리블",
    CallType.OUT_OF_BOUNDS: "아웃 오브 바운드",
    CallType.SHOT_CLOCK_VIOLATION: "샷클락 바이올레이션",
    CallType.BACKCOURT_VIOLATION: "백코트 바이올레이션",
    CallType.JUMP_BALL: "점프볼",
    CallType.TIMEOUT: "타임아웃",
    CallType.SUBSTITUTION: "교체",
    CallType.NO_CALL: "노콜",
    CallType.REVIEW: "리뷰",
}


# =============================================================================
# 심판 수신호 (20종) — FIBA 공식
# =============================================================================
@unique
class SignalType(str, Enum):
    """심판 수신호 열거형 (20종). FIBA 공식 심판 수신호."""

    # 점수 관련 (5)
    ONE_POINT = "one_point"
    TWO_POINTS = "two_points"
    THREE_POINTS = "three_points"
    POINTS_COUNTED = "points_counted"
    POINTS_CANCELED = "points_canceled"
    # 시간 관련 (3)
    STOP_CLOCK = "stop_clock"
    START_CLOCK = "start_clock"
    TIMEOUT = "timeout"
    # 파울 관련 (5)
    PERSONAL_FOUL = "personal_foul"
    HOLDING = "holding"
    PUSHING = "pushing"
    BLOCKING = "blocking"
    TECHNICAL_FOUL = "technical_foul"
    # 바이올레이션 (3)
    TRAVELING = "traveling"
    DOUBLE_DRIBBLE = "double_dribble"
    ILLEGAL_DRIBBLE = "illegal_dribble"
    # 기타 (4)
    DIRECTION = "direction"
    JUMP_BALL = "jump_ball"
    SUBSTITUTION = "substitution"
    COMMUNICATION = "communication"

    @property
    def korean_name(self) -> str:
        """한글 수신호명."""
        return _SIGNAL_TYPE_KOREAN_MAP[self]


# -- SignalType 캐시 (직접 할당) --
_SIGNAL_TYPE_KOREAN_MAP: Final[dict[SignalType, str]] = {
    SignalType.ONE_POINT: "1점",
    SignalType.TWO_POINTS: "2점",
    SignalType.THREE_POINTS: "3점",
    SignalType.POINTS_COUNTED: "득점 인정",
    SignalType.POINTS_CANCELED: "득점 취소",
    SignalType.STOP_CLOCK: "시간 정지",
    SignalType.START_CLOCK: "시간 재개",
    SignalType.TIMEOUT: "타임아웃",
    SignalType.PERSONAL_FOUL: "개인 파울",
    SignalType.HOLDING: "홀딩",
    SignalType.PUSHING: "푸싱",
    SignalType.BLOCKING: "블로킹",
    SignalType.TECHNICAL_FOUL: "테크니컬 파울",
    SignalType.TRAVELING: "트래블링",
    SignalType.DOUBLE_DRIBBLE: "더블 드리블",
    SignalType.ILLEGAL_DRIBBLE: "불법 드리블",
    SignalType.DIRECTION: "방향 지시",
    SignalType.JUMP_BALL: "점프볼",
    SignalType.SUBSTITUTION: "교체",
    SignalType.COMMUNICATION: "의사소통",
}


# =============================================================================
# 리뷰 트리거 (8종)
# =============================================================================
@unique
class ReviewTrigger(str, Enum):
    """리뷰 발동 사유 열거형 (8종)."""

    COACH_CHALLENGE = "coach_challenge"
    AUTOMATIC = "automatic"
    CREW_CHIEF = "crew_chief"
    UNCLEAR_POSSESSION = "unclear_possession"
    SHOT_CLOCK = "shot_clock"
    OUT_OF_BOUNDS = "out_of_bounds"
    FLAGRANT_FOUL = "flagrant_foul"
    GOAL_TEND = "goal_tend"

    @property
    def korean_name(self) -> str:
        """한글 발동 사유명."""
        return _REVIEW_TRIGGER_KOREAN_MAP[self]


# -- ReviewTrigger 캐시 (직접 할당) --
_REVIEW_TRIGGER_KOREAN_MAP: Final[dict[ReviewTrigger, str]] = {
    ReviewTrigger.COACH_CHALLENGE: "코치 챌린지",
    ReviewTrigger.AUTOMATIC: "자동 리뷰",
    ReviewTrigger.CREW_CHIEF: "주심 요청",
    ReviewTrigger.UNCLEAR_POSSESSION: "볼 소유권 불명확",
    ReviewTrigger.SHOT_CLOCK: "샷클락 관련",
    ReviewTrigger.OUT_OF_BOUNDS: "아웃 오브 바운드",
    ReviewTrigger.FLAGRANT_FOUL: "플래그런트 파울",
    ReviewTrigger.GOAL_TEND: "골텐딩",
}


# =============================================================================
# 리뷰 결과 (5종)
# =============================================================================
@unique
class ReviewOutcome(str, Enum):
    """리뷰 결과 열거형 (5종)."""

    CALL_STANDS = "call_stands"
    CALL_OVERTURNED = "call_overturned"
    RULING_ADJUSTED = "ruling_adjusted"
    INCONCLUSIVE = "inconclusive"
    NO_REVIEW = "no_review"

    @property
    def korean_name(self) -> str:
        """한글 결과명."""
        return _REVIEW_OUTCOME_KOREAN_MAP[self]

    @property
    def changed_call(self) -> bool:
        """판정 변경 여부."""
        return self in _REVIEW_OUTCOME_CHANGED


# -- ReviewOutcome 캐시 (직접 할당) --
_REVIEW_OUTCOME_CHANGED: Final[frozenset[ReviewOutcome]] = frozenset({
    ReviewOutcome.CALL_OVERTURNED, ReviewOutcome.RULING_ADJUSTED,
})

_REVIEW_OUTCOME_KOREAN_MAP: Final[dict[ReviewOutcome, str]] = {
    ReviewOutcome.CALL_STANDS: "원판정 유지",
    ReviewOutcome.CALL_OVERTURNED: "원판정 번복",
    ReviewOutcome.RULING_ADJUSTED: "판정 조정",
    ReviewOutcome.INCONCLUSIVE: "불명확 (원판정 유지)",
    ReviewOutcome.NO_REVIEW: "리뷰 불가",
}


# =============================================================================
# 심판 역할 (3종)
# =============================================================================
@unique
class RefereeRole(str, Enum):
    """심판 역할 열거형 (3종)."""

    CREW_CHIEF = "crew_chief"
    REFEREE = "referee"
    UMPIRE = "umpire"

    @property
    def korean_name(self) -> str:
        """한글 역할명."""
        return _REFEREE_ROLE_KOREAN_MAP[self]


# -- RefereeRole 캐시 (직접 할당) --
_REFEREE_ROLE_KOREAN_MAP: Final[dict[RefereeRole, str]] = {
    RefereeRole.CREW_CHIEF: "주심",
    RefereeRole.REFEREE: "부심",
    RefereeRole.UMPIRE: "심판",
}


# =============================================================================
# 심판 시스템 상수
# =============================================================================
MIN_DECISION_CONFIDENCE: Final[float] = 0.70
"""최소 판정 신뢰도 임계치."""

AUTO_CONFIRM_CONFIDENCE: Final[float] = 0.95
"""자동 확정 신뢰도 임계치."""

REVIEW_TIME_LIMIT_SEC: Final[int] = 120
"""리뷰 제한 시간 (초, 2분)."""

MAX_COACH_CHALLENGES_PER_GAME: Final[int] = 1
"""경기당 코치 챌린지 횟수 (FIBA/NBA 공통)."""

REFEREE_COUNT_STANDARD: Final[int] = 3
"""표준 심판 수 (3인제)."""

CONSISTENCY_WINDOW_FRAMES: Final[int] = 1800
"""판정 일관성 추적 윈도우 (프레임, 약 30초 @60fps)."""


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형 (6종)
    "RuleSet",
    "CallType",
    "SignalType",
    "ReviewTrigger",
    "ReviewOutcome",
    "RefereeRole",
    # 심판 시스템 상수
    "MIN_DECISION_CONFIDENCE",
    "AUTO_CONFIRM_CONFIDENCE",
    "REVIEW_TIME_LIMIT_SEC",
    "MAX_COACH_CHALLENGES_PER_GAME",
    "REFEREE_COUNT_STANDARD",
    "CONSISTENCY_WINDOW_FRAMES",
    # 캐시 (내부용이나 테스트 접근 허용)
    "_RULE_SET_KOREAN_MAP",
    "_RULE_SET_QUARTER_DURATION_MAP",
    "_RULE_SET_BACKCOURT_SEC_MAP",
    "_RULE_SET_THREE_POINT_DISTANCE_MAP",
    "_RULE_SET_MAX_PERSONAL_FOULS_MAP",
    "_RULE_SET_MAX_TIMEOUTS_MAP",
    "_RULE_SET_HAS_DEFENSIVE_THREE_SEC",
    "_CALL_TYPE_IS_FOUL",
    "_CALL_TYPE_IS_VIOLATION",
    "_CALL_TYPE_NO_STOP",
    "_CALL_TYPE_KOREAN_MAP",
    "_SIGNAL_TYPE_KOREAN_MAP",
    "_REVIEW_TRIGGER_KOREAN_MAP",
    "_REVIEW_OUTCOME_CHANGED",
    "_REVIEW_OUTCOME_KOREAN_MAP",
    "_REFEREE_ROLE_KOREAN_MAP",
]

__version__ = "1.0.0"
