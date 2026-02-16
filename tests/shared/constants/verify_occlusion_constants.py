# -*- coding: utf-8 -*-
"""occlusion_constants.py v1.1.0 검증 테스트"""

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
print("occlusion_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
        OVERLAP_THRESHOLD, MIN_VISIBLE_KEYPOINTS_RATIO,
        MAX_OCCLUSION_DURATION_FRAMES,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
        OVERLAP_THRESHOLD, MIN_VISIBLE_KEYPOINTS_RATIO,
        MAX_OCCLUSION_DURATION_FRAMES,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: OcclusionType 7 멤버
check(
    "T-03: OcclusionType 7 멤버",
    len(OcclusionType) == 7,
    f"실제: {len(OcclusionType)}",
)

# T-04: OcclusionSeverity 5 멤버
check(
    "T-04: OcclusionSeverity 5 멤버",
    len(OcclusionSeverity) == 5,
    f"실제: {len(OcclusionSeverity)}",
)

# T-05: ResolutionStrategy 7 멤버
check(
    "T-05: ResolutionStrategy 7 멤버",
    len(ResolutionStrategy) == 7,
    f"실제: {len(ResolutionStrategy)}",
)

# T-06: OcclusionType.is_recoverable
check(
    "T-06: OcclusionType.is_recoverable",
    OcclusionType.SELF.is_recoverable is True
    and OcclusionType.INTER_PLAYER.is_recoverable is True
    and OcclusionType.COURT_OBJECT.is_recoverable is True
    and OcclusionType.MOTION_BLUR.is_recoverable is True
    and OcclusionType.OUT_OF_VIEW.is_recoverable is False
    and OcclusionType.LIGHTING.is_recoverable is False
    and OcclusionType.UNKNOWN.is_recoverable is False,
)

# T-07: OcclusionType.typical_duration_frames
ok = True
for t in OcclusionType:
    d = t.typical_duration_frames
    if not (isinstance(d, tuple) and len(d) == 2 and d[0] < d[1]):
        ok = False
check("T-07: OcclusionType.typical_duration_frames", ok)

# T-08: OcclusionType.recommended_strategy (크로스 Enum 참조)
check(
    "T-08: OcclusionType.recommended_strategy",
    OcclusionType.SELF.recommended_strategy == ResolutionStrategy.INTERPOLATION
    and OcclusionType.INTER_PLAYER.recommended_strategy == ResolutionStrategy.CROSS_VIEW
    and isinstance(OcclusionType.UNKNOWN.recommended_strategy, ResolutionStrategy),
)

# T-09: OcclusionType.to_korean
check(
    "T-09: OcclusionType.to_korean",
    OcclusionType.SELF.to_korean() == "셀프 오클루전"
    and all(isinstance(t.to_korean(), str) and len(t.to_korean()) > 0 for t in OcclusionType),
)

# T-10: OcclusionSeverity tuple 값 구조
check(
    "T-10: OcclusionSeverity tuple 값 구조",
    OcclusionSeverity.NONE.severity_name == "none"
    and OcclusionSeverity.NONE.min_overlap == 0.0
    and OcclusionSeverity.TOTAL.max_overlap == 1.0,
)

# T-11: OcclusionSeverity.overlap_range
check(
    "T-11: OcclusionSeverity.overlap_range",
    OcclusionSeverity.PARTIAL.overlap_range == (0.2, 0.5)
    and OcclusionSeverity.SEVERE.overlap_range == (0.5, 0.8),
)

# T-12: OcclusionSeverity.is_trackable
check(
    "T-12: OcclusionSeverity.is_trackable",
    OcclusionSeverity.NONE.is_trackable is True
    and OcclusionSeverity.MINOR.is_trackable is True
    and OcclusionSeverity.PARTIAL.is_trackable is True
    and OcclusionSeverity.SEVERE.is_trackable is False
    and OcclusionSeverity.TOTAL.is_trackable is False,
)

# T-13: OcclusionSeverity.needs_recovery
check(
    "T-13: OcclusionSeverity.needs_recovery",
    OcclusionSeverity.PARTIAL.needs_recovery is True
    and OcclusionSeverity.SEVERE.needs_recovery is True
    and OcclusionSeverity.TOTAL.needs_recovery is True
    and OcclusionSeverity.NONE.needs_recovery is False
    and OcclusionSeverity.MINOR.needs_recovery is False,
)

# T-14: OcclusionSeverity.from_overlap 변환
check(
    "T-14: OcclusionSeverity.from_overlap",
    OcclusionSeverity.from_overlap(0.1) == OcclusionSeverity.MINOR
    and OcclusionSeverity.from_overlap(0.3) == OcclusionSeverity.PARTIAL
    and OcclusionSeverity.from_overlap(0.6) == OcclusionSeverity.SEVERE
    and OcclusionSeverity.from_overlap(0.9) == OcclusionSeverity.TOTAL
    and OcclusionSeverity.from_overlap(1.0) == OcclusionSeverity.TOTAL,
)

# T-15: OcclusionSeverity.to_korean
check(
    "T-15: OcclusionSeverity.to_korean",
    OcclusionSeverity.NONE.to_korean() == "없음"
    and OcclusionSeverity.TOTAL.to_korean() == "완전"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in OcclusionSeverity),
)

# T-16: ResolutionStrategy.requires_multiview
check(
    "T-16: ResolutionStrategy.requires_multiview",
    ResolutionStrategy.CROSS_VIEW.requires_multiview is True
    and ResolutionStrategy.INTERPOLATION.requires_multiview is False
    and ResolutionStrategy.NONE.requires_multiview is False,
)

# T-17: ResolutionStrategy.requires_history
check(
    "T-17: ResolutionStrategy.requires_history",
    ResolutionStrategy.INTERPOLATION.requires_history is True
    and ResolutionStrategy.PREDICTION.requires_history is True
    and ResolutionStrategy.KALMAN.requires_history is True
    and ResolutionStrategy.CROSS_VIEW.requires_history is False,
)

# T-18: ResolutionStrategy.requires_appearance
check(
    "T-18: ResolutionStrategy.requires_appearance",
    ResolutionStrategy.APPEARANCE_MATCHING.requires_appearance is True
    and ResolutionStrategy.HYBRID.requires_appearance is True
    and ResolutionStrategy.CROSS_VIEW.requires_appearance is False,
)

# T-19: ResolutionStrategy.priority (낮을수록 우선)
check(
    "T-19: ResolutionStrategy.priority",
    ResolutionStrategy.CROSS_VIEW.priority == 1
    and ResolutionStrategy.KALMAN.priority == 2
    and ResolutionStrategy.NONE.priority == 99
    and all(isinstance(s.priority, int) for s in ResolutionStrategy),
)

# T-20: ResolutionStrategy.to_korean
check(
    "T-20: ResolutionStrategy.to_korean",
    ResolutionStrategy.CROSS_VIEW.to_korean() == "크로스뷰 복구"
    and ResolutionStrategy.KALMAN.to_korean() == "칼만 필터"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in ResolutionStrategy),
)

# T-21: VIEW_PRIORITY 가중치 합 assert 존재
from shared.constants.occlusion_constants import (
    VIEW_PRIORITY_VISIBILITY_WEIGHT, VIEW_PRIORITY_CONFIDENCE_WEIGHT,
)
s = VIEW_PRIORITY_VISIBILITY_WEIGHT + VIEW_PRIORITY_CONFIDENCE_WEIGHT
check("T-21: VIEW_PRIORITY 가중치 합 = 1.0", abs(s - 1.0) < 1e-9, f"합: {s}")

# T-22: __all__ 개수 및 존재 확인
import shared.constants.occlusion_constants as oc
all_list = oc.__all__
all_exist = all(hasattr(oc, name) for name in all_list)
check(
    f"T-22: __all__ {len(all_list)}개 항목 모두 존재",
    len(all_list) == 38 and all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-23: .update() 패턴 부재
import inspect
source = inspect.getsource(oc)
check(
    "T-23: .update() 및 빈 선언 패턴 없음",
    ".update(" not in source
    and "= {}" not in source
    and "= frozenset()" not in source,
)

# T-24: frozenset 캐시 타입 검증
from shared.constants.occlusion_constants import (
    _OCCLUSION_TYPE_IS_RECOVERABLE,
    _OCCLUSION_SEVERITY_IS_TRACKABLE,
    _OCCLUSION_SEVERITY_NEEDS_RECOVERY,
    _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW,
    _RESOLUTION_STRATEGY_REQUIRES_HISTORY,
    _RESOLUTION_STRATEGY_REQUIRES_APPEARANCE,
)
check(
    "T-24: 6개 frozenset 캐시 타입",
    isinstance(_OCCLUSION_TYPE_IS_RECOVERABLE, frozenset)
    and isinstance(_OCCLUSION_SEVERITY_IS_TRACKABLE, frozenset)
    and isinstance(_OCCLUSION_SEVERITY_NEEDS_RECOVERY, frozenset)
    and isinstance(_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW, frozenset)
    and isinstance(_RESOLUTION_STRATEGY_REQUIRES_HISTORY, frozenset)
    and isinstance(_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE, frozenset),
)

# T-25: dict 캐시 완전성
from shared.constants.occlusion_constants import (
    _OCCLUSION_TYPE_DURATION_MAP,
    _OCCLUSION_TYPE_KOREAN_MAP,
    _OCCLUSION_TYPE_STRATEGY_MAP,
    _OCCLUSION_SEVERITY_KOREAN_MAP,
    _RESOLUTION_STRATEGY_PRIORITY_MAP,
    _RESOLUTION_STRATEGY_KOREAN_MAP,
)
check(
    "T-25: 6개 dict 캐시 완전성",
    len(_OCCLUSION_TYPE_DURATION_MAP) == len(OcclusionType)
    and len(_OCCLUSION_TYPE_KOREAN_MAP) == len(OcclusionType)
    and len(_OCCLUSION_TYPE_STRATEGY_MAP) == len(OcclusionType)
    and len(_OCCLUSION_SEVERITY_KOREAN_MAP) == len(OcclusionSeverity)
    and len(_RESOLUTION_STRATEGY_PRIORITY_MAP) == len(ResolutionStrategy)
    and len(_RESOLUTION_STRATEGY_KOREAN_MAP) == len(ResolutionStrategy),
)

# T-26: 버전 검증
check("T-26: 버전 1.1.0", oc.__version__ == "1.1.0", f"실제: {oc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
