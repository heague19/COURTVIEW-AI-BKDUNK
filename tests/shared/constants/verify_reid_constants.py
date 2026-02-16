# -*- coding: utf-8 -*-
"""reid_constants.py v1.1.0 검증 테스트"""

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
print("reid_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.reid_constants import (
        ReIDModel, MatchStatus,
        FEATURE_DIM, SIMILARITY_THRESHOLD,
        GALLERY_MAX_SIZE, EMA_MOMENTUM,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        ReIDModel, MatchStatus,
        FEATURE_DIM, SIMILARITY_THRESHOLD,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: ReIDModel 9 멤버
check(
    "T-03: ReIDModel 9 멤버",
    len(ReIDModel) == 9,
    f"실제: {len(ReIDModel)}",
)

# T-04: MatchStatus 5 멤버
check(
    "T-04: MatchStatus 5 멤버",
    len(MatchStatus) == 5,
    f"실제: {len(MatchStatus)}",
)

# T-05: ReIDModel.feature_dim
check(
    "T-05: ReIDModel.feature_dim",
    ReIDModel.OSNET.feature_dim == 512
    and ReIDModel.RESNET50.feature_dim == 2048
    and ReIDModel.TRANSREID.feature_dim == 768
    and ReIDModel.PCB.feature_dim == 1536
    and ReIDModel.CUSTOM.feature_dim == FEATURE_DIM
    and all(isinstance(m.feature_dim, int) for m in ReIDModel),
)

# T-06: ReIDModel.input_size
check(
    "T-06: ReIDModel.input_size",
    ReIDModel.OSNET.input_size == (256, 128)
    and ReIDModel.MGN.input_size == (384, 128)
    and all(isinstance(m.input_size, tuple) and len(m.input_size) == 2 for m in ReIDModel),
)

# T-07: ReIDModel.is_lightweight
check(
    "T-07: ReIDModel.is_lightweight",
    ReIDModel.OSNET.is_lightweight is True
    and ReIDModel.OSNET_AIN.is_lightweight is True
    and ReIDModel.RESNET50.is_lightweight is False
    and ReIDModel.MGN.is_lightweight is False
    and ReIDModel.TRANSREID.is_lightweight is False,
)

# T-08: ReIDModel.to_korean
check(
    "T-08: ReIDModel.to_korean",
    ReIDModel.CUSTOM.to_korean() == "커스텀"
    and ReIDModel.TRANSREID.to_korean() == "TransReID"
    and all(isinstance(m.to_korean(), str) and len(m.to_korean()) > 0 for m in ReIDModel),
)

# T-09: MatchStatus.is_successful
check(
    "T-09: MatchStatus.is_successful",
    MatchStatus.MATCHED.is_successful is True
    and MatchStatus.NEW.is_successful is True
    and MatchStatus.AMBIGUOUS.is_successful is False
    and MatchStatus.LOW_QUALITY.is_successful is False
    and MatchStatus.FAILED.is_successful is False,
)

# T-10: MatchStatus.needs_confirmation
check(
    "T-10: MatchStatus.needs_confirmation",
    MatchStatus.AMBIGUOUS.needs_confirmation is True
    and MatchStatus.LOW_QUALITY.needs_confirmation is True
    and MatchStatus.MATCHED.needs_confirmation is False
    and MatchStatus.NEW.needs_confirmation is False
    and MatchStatus.FAILED.needs_confirmation is False,
)

# T-11: MatchStatus.should_retry
check(
    "T-11: MatchStatus.should_retry",
    MatchStatus.LOW_QUALITY.should_retry is True
    and MatchStatus.FAILED.should_retry is True
    and MatchStatus.MATCHED.should_retry is False
    and MatchStatus.NEW.should_retry is False
    and MatchStatus.AMBIGUOUS.should_retry is False,
)

# T-12: MatchStatus.to_korean
check(
    "T-12: MatchStatus.to_korean",
    MatchStatus.MATCHED.to_korean() == "매칭됨"
    and MatchStatus.NEW.to_korean() == "새로운 인물"
    and MatchStatus.FAILED.to_korean() == "실패"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in MatchStatus),
)

# T-13: 크로스뷰 융합 가중치 합 = 1.0
from shared.constants.reid_constants import (
    CROSS_VIEW_FUSION_WEIGHT_QUALITY, CROSS_VIEW_FUSION_WEIGHT_DISTANCE,
)
s1 = CROSS_VIEW_FUSION_WEIGHT_QUALITY + CROSS_VIEW_FUSION_WEIGHT_DISTANCE
check("T-13: 크로스뷰 융합 가중치 합 = 1.0", abs(s1 - 1.0) < 1e-9, f"합: {s1}")

# T-14: 재식별 특징 가중치 합 = 1.0
from shared.constants.reid_constants import (
    UNIFORM_COLOR_WEIGHT, BODY_SHAPE_WEIGHT, DEEP_FEATURE_WEIGHT,
)
s2 = UNIFORM_COLOR_WEIGHT + BODY_SHAPE_WEIGHT + DEEP_FEATURE_WEIGHT
check("T-14: 재식별 특징 가중치 합 = 1.0", abs(s2 - 1.0) < 1e-9, f"합: {s2}")

# T-15: 유사도 임계값 순서 일관성
from shared.constants.reid_constants import (
    HIGH_SIMILARITY_THRESHOLD, LOW_SIMILARITY_THRESHOLD,
    IDENTITY_CONFIRMED_SIMILARITY,
)
check(
    "T-15: 유사도 임계값 순서",
    LOW_SIMILARITY_THRESHOLD < SIMILARITY_THRESHOLD
    < HIGH_SIMILARITY_THRESHOLD < IDENTITY_CONFIRMED_SIMILARITY,
)

# T-16: __all__ 개수 및 존재 확인
import shared.constants.reid_constants as rc
all_list = rc.__all__
all_exist = all(hasattr(rc, name) for name in all_list)
check(
    f"T-16: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-17: 빈 선언 패턴 없음
import inspect
source = inspect.getsource(rc)
check(
    "T-17: 빈 선언 패턴 없음",
    "= {}" not in source
    and "= frozenset()" not in source,
)

# T-18: frozenset 캐시 타입 검증
from shared.constants.reid_constants import (
    _REID_MODEL_IS_LIGHTWEIGHT,
    _MATCH_STATUS_IS_SUCCESSFUL,
    _MATCH_STATUS_NEEDS_CONFIRMATION,
    _MATCH_STATUS_SHOULD_RETRY,
)
check(
    "T-18: 4개 frozenset 캐시 타입",
    isinstance(_REID_MODEL_IS_LIGHTWEIGHT, frozenset)
    and isinstance(_MATCH_STATUS_IS_SUCCESSFUL, frozenset)
    and isinstance(_MATCH_STATUS_NEEDS_CONFIRMATION, frozenset)
    and isinstance(_MATCH_STATUS_SHOULD_RETRY, frozenset),
)

# T-19: dict 캐시 완전성
from shared.constants.reid_constants import (
    _REID_MODEL_FEATURE_DIM_MAP,
    _REID_MODEL_INPUT_SIZE_MAP,
    _REID_MODEL_KOREAN_MAP,
    _MATCH_STATUS_KOREAN_MAP,
)
check(
    "T-19: 4개 dict 캐시 완전성",
    len(_REID_MODEL_FEATURE_DIM_MAP) == len(ReIDModel)
    and len(_REID_MODEL_INPUT_SIZE_MAP) == len(ReIDModel)
    and len(_REID_MODEL_KOREAN_MAP) == len(ReIDModel)
    and len(_MATCH_STATUS_KOREAN_MAP) == len(MatchStatus),
)

# T-20: 버전 검증
check("T-20: 버전 1.1.0", rc.__version__ == "1.1.0", f"실제: {rc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
