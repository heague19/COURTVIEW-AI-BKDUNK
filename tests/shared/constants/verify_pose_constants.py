# -*- coding: utf-8 -*-
"""pose_constants.py v2.1.0 검증 테스트"""

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
print("pose_constants.py v2.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.pose_constants import (
        PoseQuality, SkeletonType, JointType,
        JOINT_CONFIDENCE_THRESHOLD, NUM_KEYPOINTS_COCO,
        KEYPOINT_NOSE, COCO_SKELETON_CONNECTIONS,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        PoseQuality, SkeletonType, JointType,
        JOINT_CONFIDENCE_THRESHOLD, NUM_KEYPOINTS_COCO,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: PoseQuality 4 멤버
check(
    "T-03: PoseQuality 4 멤버",
    len(PoseQuality) == 4,
    f"실제: {len(PoseQuality)}",
)

# T-04: SkeletonType 6 멤버
check(
    "T-04: SkeletonType 6 멤버",
    len(SkeletonType) == 6,
    f"실제: {len(SkeletonType)}",
)

# T-05: JointType 17 멤버
check(
    "T-05: JointType 17 멤버",
    len(JointType) == 17,
    f"실제: {len(JointType)}",
)

# T-06: PoseQuality tuple 값 구조
check(
    "T-06: PoseQuality tuple 값 구조",
    PoseQuality.HIGH.quality_name == "high"
    and PoseQuality.HIGH.min_completeness == 0.8
    and PoseQuality.HIGH.max_completeness == 1.0
    and PoseQuality.INVALID.quality_name == "invalid"
    and PoseQuality.INVALID.min_completeness == 0.0,
)

# T-07: PoseQuality.is_usable
check(
    "T-07: PoseQuality.is_usable",
    PoseQuality.HIGH.is_usable is True
    and PoseQuality.MEDIUM.is_usable is True
    and PoseQuality.LOW.is_usable is True
    and PoseQuality.INVALID.is_usable is False,
)

# T-08: PoseQuality.is_reliable (frozenset 캐시)
check(
    "T-08: PoseQuality.is_reliable",
    PoseQuality.HIGH.is_reliable is True
    and PoseQuality.MEDIUM.is_reliable is True
    and PoseQuality.LOW.is_reliable is False
    and PoseQuality.INVALID.is_reliable is False,
)

# T-09: PoseQuality.from_completeness
check(
    "T-09: PoseQuality.from_completeness",
    PoseQuality.from_completeness(0.9) == PoseQuality.HIGH
    and PoseQuality.from_completeness(0.7) == PoseQuality.MEDIUM
    and PoseQuality.from_completeness(0.5) == PoseQuality.LOW
    and PoseQuality.from_completeness(0.2) == PoseQuality.INVALID,
)

# T-10: PoseQuality.to_korean
check(
    "T-10: PoseQuality.to_korean",
    PoseQuality.HIGH.to_korean == "높음"
    and PoseQuality.INVALID.to_korean == "유효하지 않음"
    and all(isinstance(q.to_korean, str) and len(q.to_korean) > 0 for q in PoseQuality),
)

# T-11: SkeletonType.num_keypoints
from shared.constants.pose_constants import NUM_KEYPOINTS_MEDIAPIPE, NUM_KEYPOINTS_OPENPOSE
check(
    "T-11: SkeletonType.num_keypoints",
    SkeletonType.MEDIAPIPE.num_keypoints == NUM_KEYPOINTS_MEDIAPIPE
    and SkeletonType.COCO.num_keypoints == NUM_KEYPOINTS_COCO
    and SkeletonType.OPENPOSE_25.num_keypoints == NUM_KEYPOINTS_OPENPOSE
    and all(isinstance(s.num_keypoints, int) for s in SkeletonType),
)

# T-12: SkeletonType.has_hand_keypoints
check(
    "T-12: SkeletonType.has_hand_keypoints",
    SkeletonType.MEDIAPIPE.has_hand_keypoints is True
    and SkeletonType.COCO.has_hand_keypoints is False
    and SkeletonType.OPENPOSE_25.has_hand_keypoints is False,
)

# T-13: SkeletonType.has_face_keypoints
check(
    "T-13: SkeletonType.has_face_keypoints",
    SkeletonType.MEDIAPIPE.has_face_keypoints is True
    and SkeletonType.COCO.has_face_keypoints is False,
)

# T-14: SkeletonType.to_korean
check(
    "T-14: SkeletonType.to_korean",
    SkeletonType.CUSTOM.to_korean == "커스텀"
    and all(isinstance(s.to_korean, str) and len(s.to_korean) > 0 for s in SkeletonType),
)

# T-15: JointType IntEnum (정수 인덱싱)
check(
    "T-15: JointType IntEnum 정수값",
    JointType.NOSE == 0
    and JointType.LEFT_SHOULDER == 5
    and JointType.RIGHT_ANKLE == 16
    and isinstance(JointType.NOSE, int),
)

# T-16: JointType.is_left / is_right
check(
    "T-16: JointType.is_left / is_right",
    JointType.LEFT_SHOULDER.is_left is True
    and JointType.LEFT_SHOULDER.is_right is False
    and JointType.RIGHT_SHOULDER.is_right is True
    and JointType.RIGHT_SHOULDER.is_left is False
    and JointType.NOSE.is_left is False
    and JointType.NOSE.is_right is False,
)

# T-17: JointType.symmetric_joint
check(
    "T-17: JointType.symmetric_joint",
    JointType.LEFT_SHOULDER.symmetric_joint == JointType.RIGHT_SHOULDER
    and JointType.RIGHT_SHOULDER.symmetric_joint == JointType.LEFT_SHOULDER
    and JointType.NOSE.symmetric_joint == JointType.NOSE
    and JointType.LEFT_ANKLE.symmetric_joint == JointType.RIGHT_ANKLE,
)

# T-18: JointType.to_korean
check(
    "T-18: JointType.to_korean",
    JointType.NOSE.to_korean == "코"
    and JointType.LEFT_SHOULDER.to_korean == "왼쪽 어깨"
    and all(isinstance(j.to_korean, str) and len(j.to_korean) > 0 for j in JointType),
)

# T-19: symmetric_joint 완전성 (모든 JointType 매핑 존재)
check(
    "T-19: symmetric_joint 완전성",
    all(hasattr(j.symmetric_joint, 'value') for j in JointType)
    and len(set(j for j in JointType if j.symmetric_joint is not None)) == 17,
)

# T-20: COCO_SKELETON_CONNECTIONS 구조
check(
    "T-20: COCO_SKELETON_CONNECTIONS",
    len(COCO_SKELETON_CONNECTIONS) == 16
    and all(isinstance(c, tuple) and len(c) == 2 for c in COCO_SKELETON_CONNECTIONS),
)

# T-21: 키포인트 그룹 FrozenSet 타입
from shared.constants.pose_constants import (
    SHOOTING_CRITICAL_KEYPOINTS, DRIBBLING_CRITICAL_KEYPOINTS,
    UPPER_BODY_KEYPOINTS, LOWER_BODY_KEYPOINTS,
)
check(
    "T-21: 키포인트 그룹 FrozenSet",
    isinstance(SHOOTING_CRITICAL_KEYPOINTS, frozenset)
    and isinstance(DRIBBLING_CRITICAL_KEYPOINTS, frozenset)
    and isinstance(UPPER_BODY_KEYPOINTS, frozenset)
    and isinstance(LOWER_BODY_KEYPOINTS, frozenset),
)

# T-22: 각도 범위 일관성 (min < max)
from shared.constants.pose_constants import (
    ELBOW_ANGLE_MIN_DEG, ELBOW_ANGLE_MAX_DEG,
    KNEE_ANGLE_MIN_DEG, KNEE_ANGLE_MAX_DEG,
    SHOULDER_ANGLE_MIN_DEG, SHOULDER_ANGLE_MAX_DEG,
    HIP_ANGLE_MIN_DEG, HIP_ANGLE_MAX_DEG,
    ANKLE_ANGLE_MIN_DEG, ANKLE_ANGLE_MAX_DEG,
)
check(
    "T-22: 각도 범위 일관성 (min < max)",
    ELBOW_ANGLE_MIN_DEG < ELBOW_ANGLE_MAX_DEG
    and KNEE_ANGLE_MIN_DEG < KNEE_ANGLE_MAX_DEG
    and SHOULDER_ANGLE_MIN_DEG < SHOULDER_ANGLE_MAX_DEG
    and HIP_ANGLE_MIN_DEG < HIP_ANGLE_MAX_DEG
    and ANKLE_ANGLE_MIN_DEG < ANKLE_ANGLE_MAX_DEG,
)

# T-23: __all__ 개수 및 존재 확인
import shared.constants.pose_constants as pc
all_list = pc.__all__
all_exist = all(hasattr(pc, name) for name in all_list)
check(
    f"T-23: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-24: .update() 패턴 부재
import inspect
source = inspect.getsource(pc)
check(
    "T-24: .update() 및 빈 선언 패턴 없음",
    ".update(" not in source
    and "= {}" not in source
    and "= frozenset()" not in source,
)

# T-25: frozenset 캐시 타입 검증
from shared.constants.pose_constants import (
    _POSE_QUALITY_IS_RELIABLE,
    _SKELETON_TYPE_HAS_HAND,
    _SKELETON_TYPE_HAS_FACE,
    _JOINT_TYPE_IS_LEFT,
    _JOINT_TYPE_IS_RIGHT,
)
check(
    "T-25: 5개 frozenset 캐시 타입",
    isinstance(_POSE_QUALITY_IS_RELIABLE, frozenset)
    and isinstance(_SKELETON_TYPE_HAS_HAND, frozenset)
    and isinstance(_SKELETON_TYPE_HAS_FACE, frozenset)
    and isinstance(_JOINT_TYPE_IS_LEFT, frozenset)
    and isinstance(_JOINT_TYPE_IS_RIGHT, frozenset),
)

# T-26: dict 캐시 완전성
from shared.constants.pose_constants import (
    _POSE_QUALITY_KOREAN_MAP,
    _SKELETON_TYPE_NUM_KEYPOINTS_MAP,
    _SKELETON_TYPE_KOREAN_MAP,
    _JOINT_TYPE_SYMMETRIC_MAP,
    _JOINT_TYPE_KOREAN_MAP,
)
check(
    "T-26: 5개 dict 캐시 완전성",
    len(_POSE_QUALITY_KOREAN_MAP) == len(PoseQuality)
    and len(_SKELETON_TYPE_NUM_KEYPOINTS_MAP) == len(SkeletonType)
    and len(_SKELETON_TYPE_KOREAN_MAP) == len(SkeletonType)
    and len(_JOINT_TYPE_SYMMETRIC_MAP) == len(JointType)
    and len(_JOINT_TYPE_KOREAN_MAP) == len(JointType),
)

# T-27: i18n 맵 5개 언어 완전성
from shared.constants.pose_constants import (
    _POSE_QUALITY_I18N_MAP,
    _SKELETON_TYPE_I18N_MAP,
    _JOINT_TYPE_I18N_MAP,
)
EXPECTED_LANGS = {"ko", "en", "ja", "zh", "es"}
check(
    "T-27: i18n 3개 맵 × 5개 언어",
    set(_POSE_QUALITY_I18N_MAP.keys()) == EXPECTED_LANGS
    and set(_SKELETON_TYPE_I18N_MAP.keys()) == EXPECTED_LANGS
    and set(_JOINT_TYPE_I18N_MAP.keys()) == EXPECTED_LANGS
    and all(len(v) == len(PoseQuality) for v in _POSE_QUALITY_I18N_MAP.values())
    and all(len(v) == len(SkeletonType) for v in _SKELETON_TYPE_I18N_MAP.values())
    and all(len(v) == len(JointType) for v in _JOINT_TYPE_I18N_MAP.values()),
)

# T-28: 버전 검증
check("T-28: 버전 2.1.0", pc.__version__ == "2.1.0", f"실제: {pc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
