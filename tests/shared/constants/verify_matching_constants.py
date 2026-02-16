# -*- coding: utf-8 -*-
"""matching_constants.py v1.1.0 검증 테스트"""

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
print("matching_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
        DEFAULT_EPIPOLAR_THRESHOLD, DEFAULT_APPEARANCE_THRESHOLD,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
        DEFAULT_EPIPOLAR_THRESHOLD, DEFAULT_APPEARANCE_THRESHOLD,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: MatchingStrategy 7 멤버
check(
    "T-03: MatchingStrategy 7 멤버",
    len(MatchingStrategy) == 7,
    f"실제: {len(MatchingStrategy)}",
)

# T-04: MatchingStatus 7 멤버
check(
    "T-04: MatchingStatus 7 멤버",
    len(MatchingStatus) == 7,
    f"실제: {len(MatchingStatus)}",
)

# T-05: MatchingTargetType 6 멤버
check(
    "T-05: MatchingTargetType 6 멤버",
    len(MatchingTargetType) == 6,
    f"실제: {len(MatchingTargetType)}",
)

# T-06: 기본 가중치 합 = 1.0
s = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
check("T-06: 기본 가중치 합 = 1.0", abs(s - 1.0) < 1e-9, f"합: {s}")

# T-07: 비용 행렬 가중치 합 = 1.0
from shared.constants.matching_constants import (
    COST_MATRIX_APPEARANCE_WEIGHT,
    COST_MATRIX_GEOMETRY_WEIGHT,
    COST_MATRIX_TEMPORAL_WEIGHT,
)
s2 = COST_MATRIX_APPEARANCE_WEIGHT + COST_MATRIX_GEOMETRY_WEIGHT + COST_MATRIX_TEMPORAL_WEIGHT
check("T-07: 비용 행렬 가중치 합 = 1.0", abs(s2 - 1.0) < 1e-9, f"합: {s2}")

# T-08: MatchingStrategy.is_optimal
check(
    "T-08: MatchingStrategy.is_optimal",
    MatchingStrategy.HUNGARIAN.is_optimal is True
    and MatchingStrategy.AUCTION.is_optimal is True
    and MatchingStrategy.GREEDY.is_optimal is False
    and MatchingStrategy.FUSION.is_optimal is False,
)

# T-09: MatchingStrategy.supports_partial_matching
check(
    "T-09: MatchingStrategy.supports_partial_matching",
    MatchingStrategy.GREEDY.supports_partial_matching is True
    and MatchingStrategy.HIERARCHICAL.supports_partial_matching is True
    and MatchingStrategy.FUSION.supports_partial_matching is True
    and MatchingStrategy.HUNGARIAN.supports_partial_matching is False,
)

# T-10: MatchingStrategy.default_threshold 모든 멤버
all_ok = True
for s in MatchingStrategy:
    t = s.default_threshold
    if not (isinstance(t, float) and 0.0 < t < 1.0):
        all_ok = False
check("T-10: MatchingStrategy.default_threshold", all_ok)

# T-11: MatchingStrategy.to_korean
check(
    "T-11: MatchingStrategy.to_korean",
    MatchingStrategy.HUNGARIAN.to_korean() == "헝가리안 알고리즘"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in MatchingStrategy),
)

# T-12: MatchingStatus.is_successful
check(
    "T-12: MatchingStatus.is_successful",
    MatchingStatus.MATCHED.is_successful is True
    and all(s.is_successful is False for s in MatchingStatus if s != MatchingStatus.MATCHED),
)

# T-13: MatchingStatus.needs_resolution
check(
    "T-13: MatchingStatus.needs_resolution",
    MatchingStatus.AMBIGUOUS.needs_resolution is True
    and MatchingStatus.CONFLICTED.needs_resolution is True
    and MatchingStatus.MATCHED.needs_resolution is False,
)

# T-14: MatchingStatus.can_retry
check(
    "T-14: MatchingStatus.can_retry",
    MatchingStatus.BELOW_THRESHOLD.can_retry is True
    and MatchingStatus.TEMPORAL_INCONSISTENT.can_retry is True
    and MatchingStatus.MATCHED.can_retry is False,
)

# T-15: MatchingStatus.to_korean
check(
    "T-15: MatchingStatus.to_korean",
    MatchingStatus.MATCHED.to_korean() == "매칭됨"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in MatchingStatus),
)

# T-16: MatchingTargetType.matching_weights (합 = 1.0)
weights_ok = True
for t in MatchingTargetType:
    w = t.matching_weights
    if not (isinstance(w, tuple) and len(w) == 3 and abs(sum(w) - 1.0) < 1e-9):
        weights_ok = False
check("T-16: MatchingTargetType.matching_weights 합=1.0", weights_ok)

# T-17: MatchingTargetType.appearance_threshold
at_ok = all(isinstance(t.appearance_threshold, float) and 0.0 < t.appearance_threshold < 1.0 for t in MatchingTargetType)
check("T-17: MatchingTargetType.appearance_threshold", at_ok)

# T-18: MatchingTargetType.to_korean
check(
    "T-18: MatchingTargetType.to_korean",
    MatchingTargetType.PLAYER.to_korean() == "선수"
    and MatchingTargetType.BALL.to_korean() == "농구공"
    and all(isinstance(t.to_korean(), str) and len(t.to_korean()) > 0 for t in MatchingTargetType),
)

# T-19: __all__ 개수 및 존재 확인
import shared.constants.matching_constants as mc
all_list = mc.__all__
all_exist = all(hasattr(mc, name) for name in all_list)
check(
    f"T-19: __all__ {len(all_list)}개 항목 모두 존재",
    len(all_list) == 55 and all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-20: .update() 패턴 부재
import inspect
source = inspect.getsource(mc)
check(
    "T-20: .update() 및 _init 패턴 없음",
    ".update(" not in source and "def _init" not in source,
)

# T-21: frozenset 캐시 타입
from shared.constants.matching_constants import (
    _MATCHING_STRATEGY_IS_OPTIMAL,
    _MATCHING_STRATEGY_SUPPORTS_PARTIAL,
    _MATCHING_STATUS_NEEDS_RESOLUTION,
    _MATCHING_STATUS_CAN_RETRY,
)
check(
    "T-21: 4개 frozenset 캐시 타입",
    isinstance(_MATCHING_STRATEGY_IS_OPTIMAL, frozenset)
    and isinstance(_MATCHING_STRATEGY_SUPPORTS_PARTIAL, frozenset)
    and isinstance(_MATCHING_STATUS_NEEDS_RESOLUTION, frozenset)
    and isinstance(_MATCHING_STATUS_CAN_RETRY, frozenset),
)

# T-22: dict 캐시 완전성
from shared.constants.matching_constants import (
    _MATCHING_STRATEGY_THRESHOLD_MAP,
    _MATCHING_STRATEGY_KOREAN_MAP,
    _MATCHING_STATUS_KOREAN_MAP,
    _MATCHING_TARGET_WEIGHTS_MAP,
    _MATCHING_TARGET_APPEARANCE_THRESHOLD_MAP,
    _MATCHING_TARGET_KOREAN_MAP,
)
check(
    "T-22: 6개 dict 캐시 완전성",
    len(_MATCHING_STRATEGY_THRESHOLD_MAP) == len(MatchingStrategy)
    and len(_MATCHING_STRATEGY_KOREAN_MAP) == len(MatchingStrategy)
    and len(_MATCHING_STATUS_KOREAN_MAP) == len(MatchingStatus)
    and len(_MATCHING_TARGET_WEIGHTS_MAP) == len(MatchingTargetType)
    and len(_MATCHING_TARGET_APPEARANCE_THRESHOLD_MAP) == len(MatchingTargetType)
    and len(_MATCHING_TARGET_KOREAN_MAP) == len(MatchingTargetType),
)

# T-23: 버전 검증
check("T-23: 버전 1.1.0", mc.__version__ == "1.1.0", f"실제: {mc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
