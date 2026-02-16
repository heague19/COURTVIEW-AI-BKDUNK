# -*- coding: utf-8 -*-
"""tracking_constants.py v1.1.0 검증 테스트"""

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
print("tracking_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.tracking_constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        MAX_TRACK_AGE, IOU_THRESHOLD, KALMAN_STATE_DIM,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        TrackState, TrackingTarget, TrackingAlgorithm,
        MAX_TRACK_AGE, IOU_THRESHOLD,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: TrackState 6 멤버
check(
    "T-03: TrackState 6 멤버",
    len(TrackState) == 6,
    f"실제: {len(TrackState)}",
)

# T-04: TrackingTarget 6 멤버
check(
    "T-04: TrackingTarget 6 멤버",
    len(TrackingTarget) == 6,
    f"실제: {len(TrackingTarget)}",
)

# T-05: TrackingAlgorithm 6 멤버
check(
    "T-05: TrackingAlgorithm 6 멤버",
    len(TrackingAlgorithm) == 6,
    f"실제: {len(TrackingAlgorithm)}",
)

# T-06: TrackState.is_active
check(
    "T-06: TrackState.is_active",
    TrackState.CONFIRMED.is_active is True
    and TrackState.TRACKED.is_active is True
    and TrackState.TENTATIVE.is_active is False
    and TrackState.LOST.is_active is False
    and TrackState.DELETED.is_active is False,
)

# T-07: TrackState.is_visible
check(
    "T-07: TrackState.is_visible",
    TrackState.CONFIRMED.is_visible is True
    and TrackState.TRACKED.is_visible is True
    and TrackState.TENTATIVE.is_visible is True
    and TrackState.LOST.is_visible is False
    and TrackState.OCCLUDED.is_visible is False,
)

# T-08: TrackState.can_associate
check(
    "T-08: TrackState.can_associate",
    TrackState.TENTATIVE.can_associate is True
    and TrackState.CONFIRMED.can_associate is True
    and TrackState.TRACKED.can_associate is True
    and TrackState.LOST.can_associate is True
    and TrackState.OCCLUDED.can_associate is True
    and TrackState.DELETED.can_associate is False,
)

# T-09: TrackState.needs_prediction
check(
    "T-09: TrackState.needs_prediction",
    TrackState.LOST.needs_prediction is True
    and TrackState.OCCLUDED.needs_prediction is True
    and TrackState.TRACKED.needs_prediction is False
    and TrackState.CONFIRMED.needs_prediction is False,
)

# T-10: TrackState.to_korean
check(
    "T-10: TrackState.to_korean",
    TrackState.TENTATIVE.to_korean() == "잠정"
    and TrackState.TRACKED.to_korean() == "추적 중"
    and TrackState.DELETED.to_korean() == "삭제"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in TrackState),
)

# T-11: TrackingTarget.is_person
check(
    "T-11: TrackingTarget.is_person",
    TrackingTarget.PLAYER.is_person is True
    and TrackingTarget.REFEREE.is_person is True
    and TrackingTarget.COACH.is_person is True
    and TrackingTarget.BALL.is_person is False
    and TrackingTarget.HOOP.is_person is False
    and TrackingTarget.UNKNOWN.is_person is False,
)

# T-12: TrackingTarget.is_dynamic
check(
    "T-12: TrackingTarget.is_dynamic",
    TrackingTarget.PLAYER.is_dynamic is True
    and TrackingTarget.BALL.is_dynamic is True
    and TrackingTarget.UNKNOWN.is_dynamic is True
    and TrackingTarget.HOOP.is_dynamic is False,
)

# T-13: TrackingTarget.default_max_age
from shared.constants.tracking_constants import (
    MAX_TRACK_AGE_PLAYER, MAX_TRACK_AGE_BALL,
)
check(
    "T-13: TrackingTarget.default_max_age",
    TrackingTarget.PLAYER.default_max_age == MAX_TRACK_AGE_PLAYER
    and TrackingTarget.BALL.default_max_age == MAX_TRACK_AGE_BALL
    and TrackingTarget.HOOP.default_max_age == 1000
    and all(isinstance(t.default_max_age, int) for t in TrackingTarget),
)

# T-14: TrackingTarget.default_min_hits
check(
    "T-14: TrackingTarget.default_min_hits",
    TrackingTarget.BALL.default_min_hits == 2
    and TrackingTarget.HOOP.default_min_hits == 5
    and all(isinstance(t.default_min_hits, int) for t in TrackingTarget),
)

# T-15: TrackingTarget.to_korean
check(
    "T-15: TrackingTarget.to_korean",
    TrackingTarget.PLAYER.to_korean() == "선수"
    and TrackingTarget.BALL.to_korean() == "공"
    and TrackingTarget.REFEREE.to_korean() == "심판"
    and all(isinstance(t.to_korean(), str) and len(t.to_korean()) > 0 for t in TrackingTarget),
)

# T-16: TrackingAlgorithm.uses_appearance
check(
    "T-16: TrackingAlgorithm.uses_appearance",
    TrackingAlgorithm.DEEPSORT.uses_appearance is True
    and TrackingAlgorithm.BOTSORT.uses_appearance is True
    and TrackingAlgorithm.STRONGSORT.uses_appearance is True
    and TrackingAlgorithm.SORT.uses_appearance is False
    and TrackingAlgorithm.BYTETRACK.uses_appearance is False,
)

# T-17: TrackingAlgorithm.uses_motion_compensation
check(
    "T-17: TrackingAlgorithm.uses_motion_compensation",
    TrackingAlgorithm.BOTSORT.uses_motion_compensation is True
    and TrackingAlgorithm.OCSORT.uses_motion_compensation is True
    and TrackingAlgorithm.DEEPSORT.uses_motion_compensation is False
    and TrackingAlgorithm.SORT.uses_motion_compensation is False,
)

# T-18: TrackingAlgorithm.default_iou_threshold
check(
    "T-18: TrackingAlgorithm.default_iou_threshold",
    TrackingAlgorithm.BOTSORT.default_iou_threshold == 0.2
    and TrackingAlgorithm.SORT.default_iou_threshold == 0.3
    and all(isinstance(a.default_iou_threshold, float) for a in TrackingAlgorithm),
)

# T-19: TrackingAlgorithm.to_korean
check(
    "T-19: TrackingAlgorithm.to_korean",
    TrackingAlgorithm.DEEPSORT.to_korean() == "DeepSORT"
    and TrackingAlgorithm.BYTETRACK.to_korean() == "ByteTrack"
    and TrackingAlgorithm.BOTSORT.to_korean() == "BoT-SORT"
    and all(isinstance(a.to_korean(), str) and len(a.to_korean()) > 0 for a in TrackingAlgorithm),
)

# T-20: 비용 가중치 합 = 1.0
from shared.constants.tracking_constants import (
    APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT,
)
s = APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT
check("T-20: 비용 가중치 합 = 1.0", abs(s - 1.0) < 1e-9, f"합: {s}")

# T-21: 칼만 필터 차원 일관성
check(
    "T-21: 칼만 필터 차원",
    KALMAN_STATE_DIM == 8
    and KALMAN_STATE_DIM > 0,
)

# T-22: __all__ 개수 및 존재 확인
import shared.constants.tracking_constants as tc
all_list = tc.__all__
all_exist = all(hasattr(tc, name) for name in all_list)
check(
    f"T-22: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-23: 빈 선언 패턴 없음
import inspect
source = inspect.getsource(tc)
check(
    "T-23: 빈 선언 패턴 없음",
    "= {}" not in source
    and "= frozenset()" not in source,
)

# T-24: frozenset 캐시 타입 검증
from shared.constants.tracking_constants import (
    _TRACK_STATE_IS_ACTIVE,
    _TRACK_STATE_IS_VISIBLE,
    _TRACK_STATE_CAN_ASSOCIATE,
    _TRACK_STATE_NEEDS_PREDICTION,
    _TRACKING_TARGET_IS_PERSON,
    _TRACKING_TARGET_IS_DYNAMIC,
    _TRACKING_ALGORITHM_USES_APPEARANCE,
    _TRACKING_ALGORITHM_USES_MOTION_COMPENSATION,
)
check(
    "T-24: 8개 frozenset 캐시 타입",
    isinstance(_TRACK_STATE_IS_ACTIVE, frozenset)
    and isinstance(_TRACK_STATE_IS_VISIBLE, frozenset)
    and isinstance(_TRACK_STATE_CAN_ASSOCIATE, frozenset)
    and isinstance(_TRACK_STATE_NEEDS_PREDICTION, frozenset)
    and isinstance(_TRACKING_TARGET_IS_PERSON, frozenset)
    and isinstance(_TRACKING_TARGET_IS_DYNAMIC, frozenset)
    and isinstance(_TRACKING_ALGORITHM_USES_APPEARANCE, frozenset)
    and isinstance(_TRACKING_ALGORITHM_USES_MOTION_COMPENSATION, frozenset),
)

# T-25: dict 캐시 완전성
from shared.constants.tracking_constants import (
    _TRACK_STATE_KOREAN_MAP,
    _TRACKING_TARGET_KOREAN_MAP,
    _TRACKING_TARGET_MAX_AGE_MAP,
    _TRACKING_TARGET_MIN_HITS_MAP,
    _TRACKING_ALGORITHM_KOREAN_MAP,
    _TRACKING_ALGORITHM_IOU_MAP,
)
check(
    "T-25: 6개 dict 캐시 완전성",
    len(_TRACK_STATE_KOREAN_MAP) == len(TrackState)
    and len(_TRACKING_TARGET_KOREAN_MAP) == len(TrackingTarget)
    and len(_TRACKING_TARGET_MAX_AGE_MAP) == len(TrackingTarget)
    and len(_TRACKING_TARGET_MIN_HITS_MAP) == len(TrackingTarget)
    and len(_TRACKING_ALGORITHM_KOREAN_MAP) == len(TrackingAlgorithm)
    and len(_TRACKING_ALGORITHM_IOU_MAP) == len(TrackingAlgorithm),
)

# T-26: 버전 검증
check("T-26: 버전 1.1.0", tc.__version__ == "1.1.0", f"실제: {tc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
