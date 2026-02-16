# -*- coding: utf-8 -*-
"""referee_rule_constants.py v1.0.0 검증 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name} - {msg}")
        failed += 1


print("=" * 70)
print("referee_rule_constants.py v1.0.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.referee_rule_constants import (
        RuleSet, CallType, SignalType,
        ReviewTrigger, ReviewOutcome, RefereeRole,
        MIN_DECISION_CONFIDENCE, REFEREE_COUNT_STANDARD,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        RuleSet, CallType, SignalType,
        ReviewTrigger, ReviewOutcome, RefereeRole,
        MIN_DECISION_CONFIDENCE, REFEREE_COUNT_STANDARD,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: RuleSet 5 멤버
check(
    "T-03: RuleSet 5 멤버",
    len(RuleSet) == 5,
    f"실제: {len(RuleSet)}",
)

# T-04: CallType 15 멤버
check(
    "T-04: CallType 15 멤버",
    len(CallType) == 15,
    f"실제: {len(CallType)}",
)

# T-05: SignalType 20 멤버
check(
    "T-05: SignalType 20 멤버",
    len(SignalType) == 20,
    f"실제: {len(SignalType)}",
)

# T-06: ReviewTrigger 8 멤버
check(
    "T-06: ReviewTrigger 8 멤버",
    len(ReviewTrigger) == 8,
    f"실제: {len(ReviewTrigger)}",
)

# T-07: ReviewOutcome 5 멤버
check(
    "T-07: ReviewOutcome 5 멤버",
    len(ReviewOutcome) == 5,
    f"실제: {len(ReviewOutcome)}",
)

# T-08: RefereeRole 3 멤버
check(
    "T-08: RefereeRole 3 멤버",
    len(RefereeRole) == 3,
    f"실제: {len(RefereeRole)}",
)

# T-09: RuleSet.korean_name
check(
    "T-09: RuleSet.korean_name",
    RuleSet.FIBA.korean_name == "국제농구연맹"
    and RuleSet.NBA.korean_name == "미국 프로농구"
    and RuleSet.KBL.korean_name == "한국프로농구"
    and all(isinstance(r.korean_name, str) and len(r.korean_name) > 0 for r in RuleSet),
)

# T-10: RuleSet.quarter_duration_sec
check(
    "T-10: RuleSet.quarter_duration_sec",
    RuleSet.FIBA.quarter_duration_sec == 600
    and RuleSet.NBA.quarter_duration_sec == 720
    and RuleSet.KBL.quarter_duration_sec == 600,
)

# T-11: RuleSet.three_point_distance_meters
check(
    "T-11: RuleSet.three_point_distance_meters",
    abs(RuleSet.FIBA.three_point_distance_meters - 6.75) < 0.01
    and abs(RuleSet.NBA.three_point_distance_meters - 7.24) < 0.01,
)

# T-12: RuleSet.max_personal_fouls
check(
    "T-12: RuleSet.max_personal_fouls",
    RuleSet.FIBA.max_personal_fouls == 5
    and RuleSet.NBA.max_personal_fouls == 6
    and RuleSet.KBL.max_personal_fouls == 5,
)

# T-13: RuleSet.has_defensive_three_seconds
check(
    "T-13: RuleSet.has_defensive_three_seconds",
    RuleSet.NBA.has_defensive_three_seconds is True
    and RuleSet.FIBA.has_defensive_three_seconds is False
    and RuleSet.KBL.has_defensive_three_seconds is False,
)

# T-14: RuleSet.max_timeouts
check(
    "T-14: RuleSet.max_timeouts",
    RuleSet.FIBA.max_timeouts == 5
    and RuleSet.NBA.max_timeouts == 7,
)

# T-15: CallType.is_foul
check(
    "T-15: CallType.is_foul",
    CallType.PERSONAL_FOUL.is_foul is True
    and CallType.SHOOTING_FOUL.is_foul is True
    and CallType.FLAGRANT_FOUL.is_foul is True
    and CallType.TRAVELING.is_foul is False
    and CallType.JUMP_BALL.is_foul is False,
)

# T-16: CallType.is_violation
check(
    "T-16: CallType.is_violation",
    CallType.TRAVELING.is_violation is True
    and CallType.DOUBLE_DRIBBLE.is_violation is True
    and CallType.SHOT_CLOCK_VIOLATION.is_violation is True
    and CallType.PERSONAL_FOUL.is_violation is False,
)

# T-17: CallType.stops_play
check(
    "T-17: CallType.stops_play",
    CallType.PERSONAL_FOUL.stops_play is True
    and CallType.TRAVELING.stops_play is True
    and CallType.NO_CALL.stops_play is False,
)

# T-18: CallType.korean_name
check(
    "T-18: CallType.korean_name",
    CallType.PERSONAL_FOUL.korean_name == "개인 파울"
    and CallType.TRAVELING.korean_name == "트래블링"
    and CallType.NO_CALL.korean_name == "노콜"
    and all(isinstance(c.korean_name, str) and len(c.korean_name) > 0 for c in CallType),
)

# T-19: SignalType.korean_name
check(
    "T-19: SignalType.korean_name",
    SignalType.ONE_POINT.korean_name == "1점"
    and SignalType.STOP_CLOCK.korean_name == "시간 정지"
    and SignalType.TRAVELING.korean_name == "트래블링"
    and all(isinstance(s.korean_name, str) and len(s.korean_name) > 0 for s in SignalType),
)

# T-20: ReviewTrigger.korean_name
check(
    "T-20: ReviewTrigger.korean_name",
    ReviewTrigger.COACH_CHALLENGE.korean_name == "코치 챌린지"
    and ReviewTrigger.AUTOMATIC.korean_name == "자동 리뷰"
    and all(isinstance(r.korean_name, str) and len(r.korean_name) > 0 for r in ReviewTrigger),
)

# T-21: ReviewOutcome.changed_call
check(
    "T-21: ReviewOutcome.changed_call",
    ReviewOutcome.CALL_OVERTURNED.changed_call is True
    and ReviewOutcome.RULING_ADJUSTED.changed_call is True
    and ReviewOutcome.CALL_STANDS.changed_call is False
    and ReviewOutcome.INCONCLUSIVE.changed_call is False
    and ReviewOutcome.NO_REVIEW.changed_call is False,
)

# T-22: RefereeRole.korean_name
check(
    "T-22: RefereeRole.korean_name",
    RefereeRole.CREW_CHIEF.korean_name == "주심"
    and RefereeRole.REFEREE.korean_name == "부심"
    and RefereeRole.UMPIRE.korean_name == "심판",
)

# T-23: 심판 시스템 상수 검증
from shared.constants.referee_rule_constants import (
    AUTO_CONFIRM_CONFIDENCE, REVIEW_TIME_LIMIT_SEC,
    MAX_COACH_CHALLENGES_PER_GAME, CONSISTENCY_WINDOW_FRAMES,
)
check(
    "T-23: 심판 시스템 상수",
    abs(MIN_DECISION_CONFIDENCE - 0.70) < 1e-9
    and abs(AUTO_CONFIRM_CONFIDENCE - 0.95) < 1e-9
    and REVIEW_TIME_LIMIT_SEC == 120
    and MAX_COACH_CHALLENGES_PER_GAME == 1
    and REFEREE_COUNT_STANDARD == 3
    and CONSISTENCY_WINDOW_FRAMES == 1800,
)

# T-24: 신뢰도 임계값 순서
check(
    "T-24: 신뢰도 임계값 순서",
    MIN_DECISION_CONFIDENCE < AUTO_CONFIRM_CONFIDENCE,
)

# T-25: __all__ 개수 및 존재 확인
import shared.constants.referee_rule_constants as rrc
all_list = rrc.__all__
all_exist = all(hasattr(rrc, name) for name in all_list)
check(
    f"T-25: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-26: 빈 선언 패턴 없음
import inspect
source = inspect.getsource(rrc)
check(
    "T-26: 빈 선언 패턴 없음",
    "= {}" not in source
    and "= frozenset()" not in source,
)

# T-27: frozenset/dict 캐시 타입 검증
from shared.constants.referee_rule_constants import (
    _RULE_SET_KOREAN_MAP, _RULE_SET_QUARTER_DURATION_MAP,
    _RULE_SET_THREE_POINT_DISTANCE_MAP, _RULE_SET_MAX_PERSONAL_FOULS_MAP,
    _RULE_SET_MAX_TIMEOUTS_MAP, _RULE_SET_HAS_DEFENSIVE_THREE_SEC,
    _CALL_TYPE_IS_FOUL, _CALL_TYPE_IS_VIOLATION, _CALL_TYPE_NO_STOP,
    _CALL_TYPE_KOREAN_MAP, _SIGNAL_TYPE_KOREAN_MAP,
    _REVIEW_TRIGGER_KOREAN_MAP, _REVIEW_OUTCOME_CHANGED,
    _REVIEW_OUTCOME_KOREAN_MAP, _REFEREE_ROLE_KOREAN_MAP,
)
check(
    "T-27: dict/frozenset 캐시 타입",
    isinstance(_RULE_SET_KOREAN_MAP, dict)
    and isinstance(_RULE_SET_QUARTER_DURATION_MAP, dict)
    and isinstance(_RULE_SET_THREE_POINT_DISTANCE_MAP, dict)
    and isinstance(_RULE_SET_MAX_PERSONAL_FOULS_MAP, dict)
    and isinstance(_RULE_SET_MAX_TIMEOUTS_MAP, dict)
    and isinstance(_RULE_SET_HAS_DEFENSIVE_THREE_SEC, frozenset)
    and isinstance(_CALL_TYPE_IS_FOUL, frozenset)
    and isinstance(_CALL_TYPE_IS_VIOLATION, frozenset)
    and isinstance(_CALL_TYPE_NO_STOP, frozenset)
    and isinstance(_CALL_TYPE_KOREAN_MAP, dict)
    and isinstance(_SIGNAL_TYPE_KOREAN_MAP, dict)
    and isinstance(_REVIEW_TRIGGER_KOREAN_MAP, dict)
    and isinstance(_REVIEW_OUTCOME_CHANGED, frozenset)
    and isinstance(_REVIEW_OUTCOME_KOREAN_MAP, dict)
    and isinstance(_REFEREE_ROLE_KOREAN_MAP, dict),
)

# T-28: dict 캐시 완전성 (모든 멤버 커버)
check(
    "T-28: dict 캐시 완전성",
    len(_RULE_SET_KOREAN_MAP) == len(RuleSet)
    and len(_RULE_SET_QUARTER_DURATION_MAP) == len(RuleSet)
    and len(_RULE_SET_THREE_POINT_DISTANCE_MAP) == len(RuleSet)
    and len(_RULE_SET_MAX_PERSONAL_FOULS_MAP) == len(RuleSet)
    and len(_RULE_SET_MAX_TIMEOUTS_MAP) == len(RuleSet)
    and len(_CALL_TYPE_KOREAN_MAP) == len(CallType)
    and len(_SIGNAL_TYPE_KOREAN_MAP) == len(SignalType)
    and len(_REVIEW_TRIGGER_KOREAN_MAP) == len(ReviewTrigger)
    and len(_REVIEW_OUTCOME_KOREAN_MAP) == len(ReviewOutcome)
    and len(_REFEREE_ROLE_KOREAN_MAP) == len(RefereeRole),
)

# T-29: dto/referee_dto.py re-export 호환성
try:
    from shared.dto.referee_dto import (
        RuleSet as DtoRuleSet,
        CallType as DtoCallType,
        SignalType as DtoSignalType,
        ReviewTrigger as DtoReviewTrigger,
        ReviewOutcome as DtoReviewOutcome,
        RefereeRole as DtoRefereeRole,
    )
    check(
        "T-29: dto/referee_dto.py re-export 호환성",
        DtoRuleSet is RuleSet
        and DtoCallType is CallType
        and DtoSignalType is SignalType
        and DtoReviewTrigger is ReviewTrigger
        and DtoReviewOutcome is ReviewOutcome
        and DtoRefereeRole is RefereeRole,
    )
except Exception as e:
    check("T-29: dto/referee_dto.py re-export 호환성", False, str(e))

# T-30: 버전 검증
check("T-30: 버전 1.0.0", rrc.__version__ == "1.0.0", f"실제: {rrc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
